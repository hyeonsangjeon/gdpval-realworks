"""Four-source intake, with synthetic provenance and a fake Hub stream only.

No original payload, token or network is used. The CLI, role derivation, Hub URL
and header helpers, archive serializer/importer, canonical Step0/current-byte
readers, no-clobber publication and workflow routing checks remain real.
"""

from __future__ import annotations

from contextlib import contextmanager
import copy
import hashlib
import json
import logging
import os
from types import SimpleNamespace
from urllib.parse import quote, urlsplit

import httpx
import pytest
from huggingface_hub import constants, hf_hub_url

import codex_budget_pilot_ci as ci
import codex_ci_input_bundle as bundle
import codex_ci_input_intake as intake
from .test_codex_budget_pilot import offline  # noqa: F401
from .test_codex_ci_input_bundle import originals, reservation  # noqa: F401
from .test_codex_ci_input_intake import GitHub, Response, shell_block, workflow

HF_TOKEN = "synthetic_hf_input_token_never_publish"
PRIVATE = "sensitive-body https://secret.example/file?sig=private /synthetic/private/auth"
STEP0_REPO = "synthetic-owner/submissions-not-originals"
CDN = "https://cas-bridge.xethub.hf.co/synthetic-file?sig=private"


class HubResponse:
    def __init__(self, data=b"", *, status=200, headers=None, failure=None):
        self.data, self.status_code, self.failure = data, status, failure
        self.headers = httpx.Headers({"content-length": str(len(data))} if headers is None else headers)
        self.closed, self.reads = False, []

    def iter_raw(self, *, chunk_size):
        self.reads.append(chunk_size)
        if self.failure:
            raise self.failure
        for offset in range(0, len(self.data), chunk_size):
            yield self.data[offset:offset + chunk_size]


class Hub:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), []
        self.before_response = None

    @contextmanager
    def __call__(self, method, url, **options):
        assert os.environ["HF_HUB_OFFLINE"] == "0" and constants.HF_HUB_OFFLINE is False
        assert not any(name in os.environ for name in ("HF_TOKEN", "GITHUB_TOKEN", "HUGGING_FACE_HUB_TOKEN"))
        self.calls.append((method, url, options))
        logging.getLogger("huggingface_hub").warning("%s %s %s", HF_TOKEN, PRIVATE, url)
        if self.before_response:
            self.before_response(len(self.calls))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        try:
            yield response
        finally:
            response.closed = True


@pytest.fixture
def hf_case(originals, monkeypatch):
    case = originals
    old_plan, _, _ = bundle._registered()
    # Only these provenance suppliers/pins are synthetic, not the role builder,
    # archive integrity checks, installed reader or public transport arguments.
    case.revision = intake.HF_ORIGINAL_REVISION
    case.plan = SimpleNamespace(dispatch=SimpleNamespace(controls_json=json.dumps({
        "dataset": {"repo_id": intake.HF_ORIGINAL_REPO, "revision": case.revision},
    })))
    monkeypatch.setattr(bundle, "_registered", lambda: (case.plan, case.revision, copy.deepcopy(case.specs)))
    monkeypatch.setattr(bundle, "load_plan", lambda path: {"data": {"source": STEP0_REPO}})
    monkeypatch.setattr(intake, "HF_STEP0_REPO_SHA256", hashlib.sha256(STEP0_REPO.encode()).hexdigest())
    original_inputs = case.transport.inputs

    def inputs(plan, sources):
        assert plan is case.plan
        assert os.environ["HF_HUB_OFFLINE"] == "1" and constants.HF_HUB_OFFLINE is True
        assert not any(name in os.environ for name in ("HF_TOKEN", "GITHUB_TOKEN", "HUGGING_FACE_HUB_TOKEN"))
        return original_inputs(old_plan, sources)

    case.transport.inputs = inputs
    manifest = bundle._manifest(case.revision, case.specs, case.files)
    case.archive = bundle._archive({bundle.MANIFEST: bundle._canonical_json(manifest).encode(), **case.files})
    case.identity = bundle._identity(case.archive)
    monkeypatch.setattr(intake, "BUNDLE_SIZE", case.identity["size"])
    monkeypatch.setattr(intake, "BUNDLE_SHA256", case.identity["sha256"])
    monkeypatch.setenv("GITHUB_REPOSITORY", intake.REPOSITORY)
    monkeypatch.setenv("HF_TOKEN", HF_TOKEN)
    monkeypatch.setenv("GITHUB_TOKEN", "synthetic_other_transport_token")
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setattr(constants, "HF_HUB_OFFLINE", True)
    case.stage, case.installed = case.parent / "hf-private.tar", case.parent / "hf-inputs"
    case.argv = ["--input-check", "--input-transport", "hf_originals", "--expected-sha256",
                 case.identity["sha256"], "--bundle-out", str(case.stage), "--out", str(case.installed)]
    case.origins = intake._hf_origins()[2]
    case.hub = Hub([HubResponse(data) for data in case.files.values()])
    return case


def invoke(case, *, argv=None, hub=None):
    return intake.main(case.argv if argv is None else argv, _test_hf=case.hub if hub is None else hub,
                       _test_transport=case.transport)


def assert_refused(case, caplog, capsys, code):
    output = capsys.readouterr()
    assert output.out == "" and code in caplog.text
    for value in (HF_TOKEN, PRIVATE, STEP0_REPO, CDN, str(case.parent), "synthetic_other_transport_token"):
        assert value not in output.out + output.err + caplog.text
    assert not (case.installed / bundle.READY).exists()


def test_hf_originals_real_registered_origins_keep_submission_parquet_out():
    revision, specs, origins = intake._hf_origins()
    assert revision == "11e7900cdcac61bc4daf59e65feb238acda98fbf"
    assert [row[4] for row in origins] == list(intake.HFRole)
    assert len(origins) == len(specs) == 4
    assert all(row[1:3] == ("openai/gdpval", revision) for row in origins[:3])
    assert origins[0][3] == "data/train-00000-of-00001.parquet"
    assert all(row[3].startswith("reference_files/") for row in origins[1:3])
    assert origins[3][2:4] == ("6c7e07ee7365f145dfcf898263365b5c8c97b224", "step0_needs_files_manifest.json")
    assert hashlib.sha256(origins[3][1].encode()).hexdigest() == intake.HF_STEP0_REPO_SHA256
    assert origins[3][1] != origins[0][1]
    assert specs[bundle.PARQUET] == {"role": "normalized_original_parquet", **bundle.PARQUET_PIN}
    assert specs[bundle.STEP0] == {"role": "canonical_schema4_deliverable_only_step0", **bundle.STEP0_PIN}
    assert intake.BUNDLE_SIZE == 2519040
    assert intake.BUNDLE_SHA256 == "757603585405da5d7f6817a6a0a23bd530d4b5e4e38b2fd4dc6f318053d240e3"


@pytest.mark.parametrize("redirect", [None, "cache", "cdn"])
def test_hf_originals_real_cli_archive_import_and_token_isolation(hf_case, capsys, caplog, redirect):
    case = hf_case
    if redirect:
        origin = hf_hub_url(case.origins[0][1], case.origins[0][3], repo_type="dataset", revision=case.revision)
        target = CDN if redirect == "cdn" else origin.replace("/datasets/", "/api/resolve-cache/datasets/").replace("/resolve/", "/")
        case.hub.responses.insert(0, HubResponse(status=302, headers={"location": target}))
    handles = list(case.hub.responses)
    assert invoke(case) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["input_transport"] == "hf_originals" and report["bundle"] == case.identity
    assert report["original_inputs_verified"] is True
    assert report["oidc_requested"] is report["model_requested"] is report["publication_authorized"] is False
    assert [row["role"] for row in report["members"]] == [role.value for role in intake.HFRole]
    assert case.stage.read_bytes() == case.archive
    assert all((case.installed / name).read_bytes() == data for name, data in case.files.items())
    assert (case.installed / bundle.READY).is_file() and len(case.transport.calls) == 1
    assert all(handle.closed for handle in handles)
    expected_urls = [hf_hub_url(repo, member, repo_type="dataset", revision=revision)
                     for _, repo, revision, member, _ in case.origins]
    actual_urls = [url for _, url, _ in case.hub.calls]
    assert actual_urls == ([expected_urls[0], target, *expected_urls[1:]] if redirect else expected_urls)
    for _, url, options in case.hub.calls:
        assert options["follow_redirects"] is False and options["max_retries"] == 0
        assert options["retry_on_status_codes"] == options["retry_on_exceptions"] == ()
        assert 0 < options["timeout"] <= intake.REQUEST_TIMEOUT_SECONDS
        assert options["headers"]["Accept-Encoding"] == "identity"
        assert options["headers"].get("authorization") == (None if url == CDN else "Bearer " + HF_TOKEN)
    assert HF_TOKEN not in json.dumps(report) + caplog.text and STEP0_REPO not in json.dumps(report)
    assert constants.HF_HUB_OFFLINE is True and os.environ["HF_HUB_OFFLINE"] == "1"
    assert os.environ["HF_TOKEN"] == HF_TOKEN  # Caller environment restored, not changed globally.


def test_hf_originals_real_hub_stream_helper_never_retries_or_uses_cached_token(hf_case, monkeypatch):
    from huggingface_hub.utils import _headers, _http

    def forbidden(*args, **kwargs):
        pytest.fail("cached token or implicit transport was used")

    monkeypatch.setattr(_headers, "get_token", forbidden)
    monkeypatch.setattr(_http, "get_session", lambda: SimpleNamespace(stream=hf_case.hub))
    # This invocation does not substitute the Hub helper, only its HTTP session.
    assert intake.main(hf_case.argv, _test_transport=hf_case.transport) == 0
    assert len(hf_case.hub.calls) == 4


@pytest.mark.parametrize("selected", ["github_draft", "hf_originals"])
def test_hf_originals_default_plan_has_no_token_registration_or_fetch(hf_case, monkeypatch, capsys, selected):
    def forbidden(*args, **kwargs):
        pytest.fail("plan crossed the intake boundary")

    monkeypatch.delenv("HF_TOKEN")
    monkeypatch.delenv("GITHUB_TOKEN")
    monkeypatch.setattr(intake, "_hf_origins", forbidden)
    monkeypatch.setattr(intake, "intake", forbidden)
    monkeypatch.setattr(bundle, "import_bundle", forbidden)
    assert intake.main(["--input-transport", selected], _test_hf=forbidden, _test_github=forbidden) == 0
    record = json.loads(capsys.readouterr().out)
    assert record["mode"] == "plan_only" and record["transfer_attempted"] is False
    assert record["oidc_requested"] is record["model_requested"] is False
    assert hf_case.hub.calls == [] and not reservation(hf_case.stage).exists()


@pytest.mark.parametrize("option", ["--release-id", "--asset-id"])
@pytest.mark.parametrize("checking", [False, True])
def test_hf_originals_rejects_contradictory_github_ids_before_fetch(hf_case, caplog, capsys, option, checking):
    args = hf_case.argv if checking else ["--input-transport", "hf_originals"]
    assert invoke(hf_case, argv=[*args, option, "123"]) == 2
    assert_refused(hf_case, caplog, capsys, "hf_originals_rejects_github_ids")
    assert hf_case.hub.calls == []


@pytest.mark.parametrize("token", [None, "", "bad\nheader", "x" * 4097])
def test_hf_originals_missing_or_invalid_credential_has_no_cache_fallback(hf_case, monkeypatch, caplog, capsys, token):
    if token is None:
        monkeypatch.delenv("HF_TOKEN")
    else:
        monkeypatch.setenv("HF_TOKEN", token)
    assert invoke(hf_case) == 2
    assert_refused(hf_case, caplog, capsys, "existing_hf_read_token_required")
    assert hf_case.hub.calls == [] and not reservation(hf_case.stage).exists()


@pytest.mark.parametrize("drift", ["original_repo", "revision", "step0_repo"])
def test_hf_originals_source_identity_drift_refuses_before_credentials(hf_case, monkeypatch, caplog, capsys, drift):
    case = hf_case
    if drift == "original_repo":
        case.plan.dispatch.controls_json = json.dumps({"dataset": {"repo_id": STEP0_REPO}})
    elif drift == "revision":
        case.revision = "a" * 40
    else:
        monkeypatch.setattr(bundle, "load_plan", lambda path: {"data": {"source": "synthetic/wrong-target"}})
    monkeypatch.delenv("HF_TOKEN")  # Identity refusal must precede token lookup.
    assert invoke(case) == 2
    assert_refused(case, caplog, capsys, "registered_hf_step0_target_mismatch" if drift == "step0_repo"
                   else "registered_hf_original_identity_mismatch")
    assert case.hub.calls == [] and not reservation(case.stage).exists()


@pytest.mark.parametrize("index", range(4))
def test_hf_originals_each_hash_drift_stops_before_next_role(hf_case, caplog, capsys, index):
    case = hf_case
    data = case.hub.responses[index].data
    case.hub.responses[index] = HubResponse(b"X" + data[1:])
    assert invoke(case) == 2
    assert_refused(case, caplog, capsys, "hf_original_size_or_digest_mismatch")
    assert f"stage={case.origins[index][4].value}, http_status=200" in caplog.text
    assert len(case.hub.calls) == index + 1 and not case.stage.exists()
    assert reservation(case.stage).exists() and case.transport.calls == []


@pytest.mark.parametrize("drift", ["missing_argument", "external_argument", "archive_digest", "archive_size"])
def test_hf_originals_external_canonical_bundle_binding_is_required(hf_case, monkeypatch, caplog, capsys, drift):
    case = hf_case
    if drift == "missing_argument":
        position = case.argv.index("--expected-sha256")
        del case.argv[position:position + 2]
    if drift in ("external_argument", "archive_digest"):
        case.argv[case.argv.index("--expected-sha256") + 1] = "f" * 64
    if drift == "archive_digest":
        monkeypatch.setattr(intake, "BUNDLE_SHA256", "f" * 64)
    elif drift == "archive_size":
        monkeypatch.setattr(intake, "BUNDLE_SIZE", case.identity["size"] + 10240)
    assert invoke(case) == 2
    assert_refused(case, caplog, capsys, "registered_external_bundle_sha256_required"
                   if drift in ("missing_argument", "external_argument") else "external_bundle_digest_mismatch")
    assert len(case.hub.calls) == (0 if drift in ("missing_argument", "external_argument") else 4)
    assert not case.stage.exists() and not case.installed.exists()


@pytest.mark.parametrize("failure", ["declared_size", "stream_size", "truncated", "encoded", "invalid_length"])
def test_hf_originals_bounded_raw_stream_refusals(hf_case, caplog, capsys, failure):
    case = hf_case
    data = case.files[bundle.PARQUET]
    response = {
        "declared_size": HubResponse(data, headers={"content-length": str(len(data) + 1)}),
        "stream_size": HubResponse(data + b"x", headers={}),
        "truncated": HubResponse(data[:-1], headers={"content-length": str(len(data))}),
        "encoded": HubResponse(data, headers={"content-encoding": "gzip"}),
        "invalid_length": HubResponse(data, headers={"content-length": "unknown"}),
    }[failure]
    case.hub.responses[0] = response
    assert invoke(case) == 2
    assert_refused(case, caplog, capsys, "hf_original_")
    assert len(case.hub.calls) == 1 and response.closed and not case.stage.exists()
    if failure in ("declared_size", "encoded", "invalid_length"):
        assert response.reads == []


@pytest.mark.parametrize("index", range(4))
@pytest.mark.parametrize("status", [401, 403, 404])
def test_hf_originals_safe_http_status_and_logical_role_survive_cli(hf_case, caplog, capsys, index, status):
    case = hf_case
    response = HubResponse(PRIVATE.encode(), status=status)
    case.hub.responses[index] = response
    assert invoke(case) == 2
    assert_refused(case, caplog, capsys, "hf_original_inaccessible")
    assert f"stage={case.origins[index][4].value}, http_status={status}" in caplog.text
    assert len(case.hub.calls) == index + 1 and response.closed and response.reads == []


@pytest.mark.parametrize("index", range(4))
def test_hf_originals_no_response_preserves_null_status_and_no_private_error(hf_case, caplog, capsys, index):
    case = hf_case
    case.hub.responses[index] = httpx.ConnectError(PRIVATE + HF_TOKEN)
    assert invoke(case) == 2
    assert_refused(case, caplog, capsys, "hf_original_transport_failed")
    assert f"stage={case.origins[index][4].value}, http_status=null" in caplog.text
    assert len(case.hub.calls) == index + 1


@pytest.mark.parametrize("location", [
    "https://unapproved.example/file?sig=private", "http://huggingface.co/data",
    "https://token@cas-bridge.xethub.hf.co/file", "https://huggingface.co/datasets/other/repo/resolve/main/file",
    "/datasets/openai/gdpval/resolve/main/data/train-00000-of-00001.parquet",
])
def test_hf_originals_wrong_origin_or_revision_redirect_never_receives_auth(hf_case, caplog, capsys, location):
    hf_case.hub.responses[0] = HubResponse(status=302, headers={"location": location})
    assert invoke(hf_case) == 2
    assert_refused(hf_case, caplog, capsys, "hf_original_redirect_refused")
    assert len(hf_case.hub.calls) == 1


def reference_cache_redirect(case):
    """Synthetic member with the observed %2F/literal-parenthesis cache shape."""
    _, repo, revision, member, role = case.origins[1]
    assert role == intake.HFRole.REFERENCE_1 and "(" in member
    original = hf_hub_url(repo, member, repo_type="dataset", revision=revision)
    prefix = f"/api/resolve-cache/datasets/{repo}/{revision}/"
    return original, prefix, quote(member, safe="()")


@pytest.mark.parametrize("originals", [
    ("reference_files/first/one (1).txt", "reference_files/second/two.txt"),
], indirect=True, ids=["synthetic-escaped-reference"])
@pytest.mark.parametrize("form", ["observed", "lowercase_escapes", "literal_path", "cdn_hop"])
def test_hf_originals_redirect_equivalent_reference_survives_real_cli(hf_case, caplog, capsys, form):
    case = hf_case
    original, prefix, member = reference_cache_redirect(case)
    if form == "lowercase_escapes":
        member = member.replace("%2F", "%2f")
    elif form == "literal_path":
        member = urlsplit(original).path.split("/resolve/" + case.revision + "/", 1)[1]
    location = prefix + member + "?synthetic-query=private"
    target = "https://huggingface.co" + location
    first = HubResponse(PRIVATE.encode(), status=307, headers={"location": location})
    redirects = [first]
    if form == "cdn_hop":
        redirects.append(HubResponse(PRIVATE.encode(), status=302, headers={"location": CDN}))
    case.hub.responses[1:1] = redirects
    handles = list(case.hub.responses)
    assert invoke(case) == 0
    output = capsys.readouterr()
    report = json.loads(output.out)
    assert report["original_inputs_verified"] is True and report["bundle"] == case.identity
    assert report["oidc_requested"] is report["model_requested"] is report["publication_authorized"] is False
    assert case.stage.read_bytes() == case.archive
    assert all((case.installed / name).read_bytes() == data for name, data in case.files.items())
    assert (case.installed / bundle.READY).is_file() and len(case.transport.calls) == 1
    assert len(case.hub.calls) == 4 + len(redirects)
    assert [call[1] for call in case.hub.calls[1:3]] == [original, target]
    for _, url, options in case.hub.calls:
        assert options["headers"].get("authorization") == (None if url == CDN else "Bearer " + HF_TOKEN)
        assert options["follow_redirects"] is False and options["max_retries"] == 0
        assert options["retry_on_status_codes"] == options["retry_on_exceptions"] == ()
    assert all(response.closed for response in handles)
    assert all(response.reads == [] for response in redirects)
    assert not any(value in output.out + output.err + caplog.text
                   for value in (HF_TOKEN, PRIVATE, STEP0_REPO, CDN, str(case.parent), location, original))


@pytest.mark.parametrize("originals", [
    ("reference_files/first/one (1).txt", "reference_files/second/two.txt"),
], indirect=True, ids=["synthetic-escaped-reference"])
@pytest.mark.parametrize("defect", [
    "repository", "revision", "mutable_revision", "host", "encoded_prefix", "wrong_member",
    "double_slash_escape", "double_parenthesis_escape", "malformed_escape", "literal_traversal",
    "encoded_traversal", "encoded_dot", "encoded_empty_component", "encoded_backslash",
    "encoded_control", "encoded_del", "literal_control",
])
def test_hf_originals_redirect_reference_identity_or_encoding_refuses_in_cli(hf_case, caplog, capsys, defect):
    case = hf_case
    original, prefix, member = reference_cache_redirect(case)
    location = prefix + member
    changes = {
        "repository": prefix.replace("/openai/gdpval/", "/other/gdpval/") + member,
        "revision": prefix.replace(case.revision, "a" * 40) + member,
        "mutable_revision": prefix.replace(case.revision, "main") + member,
        "host": "https://huggingface.co.unapproved.example" + location,
        "encoded_prefix": prefix.replace("/openai/gdpval/", "/openai%2Fgdpval/") + member,
        "wrong_member": location.replace("one", "two"),
        "double_slash_escape": location.replace("%2F", "%252F"),
        "double_parenthesis_escape": location.replace("(", "%2528"),
        "malformed_escape": location.replace("%2F", "%2G", 1),
        # urljoin alone would erase the literal traversal, yielding the exact
        # expected path. Both literal and encoded traversal must be rejected.
        "literal_traversal": prefix + "unregistered/../" + member,
        "encoded_traversal": prefix + "unregistered%2F%2e%2e%2F" + member,
        "encoded_dot": prefix + "%2e%2F" + member,
        "encoded_empty_component": location.replace("%2F", "%2F%2F", 1),
        "encoded_backslash": location.replace("%2F", "%5C", 1),
        "encoded_control": location.replace("one", "one%00"),
        "encoded_del": location.replace("one", "one%7F"),
        "literal_control": location.replace("one", "one\t"),
    }
    location = changes[defect] + "?synthetic-query=private"
    response = HubResponse(PRIVATE.encode(), status=307, headers={"location": location})
    case.hub.responses.insert(1, response)
    assert invoke(case) == 2
    assert_refused(case, caplog, capsys, "hf_original_redirect_refused")
    assert "stage=hf_reference_1, http_status=307" in caplog.text
    assert len(case.hub.calls) == 2 and case.hub.calls[-1][1] == original
    assert response.closed and response.reads == []
    assert not case.stage.exists() and reservation(case.stage).exists() and case.transport.calls == []
    assert location not in caplog.text and original not in caplog.text


def test_hf_originals_shared_clock_is_bounded(hf_case, monkeypatch, caplog, capsys):
    clock = SimpleNamespace(now=10.0)
    monkeypatch.setattr(intake, "time", SimpleNamespace(monotonic=lambda: clock.now))
    hf_case.hub.before_response = lambda count: setattr(clock, "now", 10.0 + intake.TRANSFER_TIMEOUT_SECONDS)
    assert invoke(hf_case) == 2
    assert_refused(hf_case, caplog, capsys, "hf_originals_time_limit_exceeded")
    assert len(hf_case.hub.calls) == 1 and not hf_case.stage.exists()


def test_hf_originals_redirect_loop_is_bounded_without_extra_fetch(hf_case, caplog, capsys):
    responses = [HubResponse(status=302, headers={"location": CDN}) for _ in range(4)]
    hf_case.hub = Hub(responses)
    assert invoke(hf_case) == 2
    assert_refused(hf_case, caplog, capsys, "hf_original_redirect_refused")
    assert len(hf_case.hub.calls) == 4 and all(response.closed for response in responses)


def test_hf_originals_redirect_open_failure_does_not_inherit_prior_status(hf_case, caplog, capsys):
    first = HubResponse(status=302, headers={"location": CDN})
    hf_case.hub = Hub([first, httpx.ConnectError(PRIVATE)])
    assert invoke(hf_case) == 2
    assert_refused(hf_case, caplog, capsys, "hf_original_transport_failed")
    assert "stage=hf_original_parquet, http_status=null" in caplog.text
    assert first.closed and len(hf_case.hub.calls) == 2
    assert "authorization" not in hf_case.hub.calls[1][2]["headers"]


def test_hf_originals_failed_attempt_reservation_is_never_adopted(hf_case, caplog, capsys):
    hf_case.hub.responses[0] = HubResponse(status=403)
    assert invoke(hf_case) == 2
    before = reservation(hf_case.stage).read_bytes()
    assert invoke(hf_case) == 2
    assert_refused(hf_case, caplog, capsys, "private_input_verification_or_transport_failed")
    assert len(hf_case.hub.calls) == 1 and reservation(hf_case.stage).read_bytes() == before


@pytest.mark.parametrize("role", ["bundle", "reservation", "installed", "linked_parent"])
def test_hf_originals_no_clobber_refuses_before_fetch(hf_case, caplog, capsys, role):
    case = hf_case
    if role == "linked_parent":
        alias = case.parent / "alias"
        alias.symlink_to(case.root, target_is_directory=True)
        case.argv[case.argv.index("--out") + 1] = str(alias / "new-inputs")
    else:
        path = {"bundle": case.stage, "reservation": reservation(case.stage), "installed": case.installed}[role]
        path.write_bytes(b"retained earlier state")
    assert invoke(case) == 2
    assert_refused(case, caplog, capsys, "private_input_verification_or_transport_failed")
    assert case.hub.calls == [] and case.transport.calls == []
    if role != "linked_parent":
        assert path.read_bytes() == b"retained earlier state"


def test_hf_originals_failed_real_step0_reader_does_not_publish_ready(hf_case, monkeypatch, caplog, capsys):
    case = hf_case
    case.files[bundle.STEP0] = bundle._canonical_json({"_schema_version": 3, "tasks": {}}).encode()
    case.specs[bundle.STEP0].update(bundle._identity(case.files[bundle.STEP0]))
    manifest = bundle._manifest(case.revision, case.specs, case.files)
    archive = bundle._archive({bundle.MANIFEST: bundle._canonical_json(manifest).encode(), **case.files})
    monkeypatch.setattr(intake, "BUNDLE_SHA256", bundle._identity(archive)["sha256"])
    monkeypatch.setattr(intake, "BUNDLE_SIZE", len(archive))
    case.argv[case.argv.index("--expected-sha256") + 1] = bundle._identity(archive)["sha256"]
    case.hub = Hub([HubResponse(data) for data in case.files.values()])
    assert invoke(case) == 2
    assert_refused(case, caplog, capsys, "private_input_verification_or_transport_failed")
    assert case.stage.read_bytes() == archive and case.installed.is_dir()
    assert len(case.transport.calls) == 1 and reservation(case.installed).exists()
    assert constants.HF_HUB_OFFLINE is True


def test_hf_originals_github_403_never_selects_hf_implicitly(hf_case, caplog, capsys):
    case = hf_case
    github = GitHub([Response(PRIVATE.encode(), status=403)])
    args = [value if value != "hf_originals" else "github_draft" for value in case.argv]
    assert intake.main([*args, "--release-id", "101", "--asset-id", "202"],
                       _test_github=github, _test_hf=case.hub, _test_transport=case.transport) == 2
    assert_refused(case, caplog, capsys, "github_draft_or_asset_inaccessible")
    assert len(github.calls) == 1 and case.hub.calls == []


def test_hf_originals_workflow_route_and_publication_contract():
    document = workflow()
    triggers = document.get("on", document.get(True))
    assert triggers["workflow_dispatch"]["inputs"]["input_transport"]["options"] == ["github_draft", "hf_originals"]
    assert all(trigger["inputs"]["input_transport"]["default"] == "github_draft" for trigger in triggers.values())
    assert triggers["workflow_call"]["secrets"]["HF_TOKEN"] == {"required": False}
    assert document["permissions"] == {"contents": "read", "id-token": "write"}
    job = document["jobs"]["cell"]
    assert job["env"]["HF_HUB_OFFLINE"] == job["env"]["HF_DATASETS_OFFLINE"] == "1"
    assert "HF_TOKEN" not in job["env"] and "GITHUB_TOKEN" not in job["env"]
    steps = job["steps"]
    selected = next(step for step in steps if step.get("id") == "intake")
    assert selected["if"] == "(inputs.execute || inputs.input_check) && !inputs.output_target_check && !inputs.output_target_setup" and selected["timeout-minutes"] == 3
    assert selected["env"]["HF_TOKEN"] == "${{ inputs.input_transport == 'hf_originals' && secrets.HF_TOKEN || '' }}"
    assert selected["env"]["GITHUB_TOKEN"] == "${{ inputs.input_transport != 'hf_originals' && github.token || '' }}"
    metadata = next(step for step in steps if step.get("id") == "output_target")
    assert metadata["env"] == {"HF_TOKEN": "${{ secrets.HF_TOKEN }}"}
    setup = next(step for step in steps if step.get("id") == "output_setup")
    assert setup["env"] == {"HF_TOKEN": "${{ secrets.HF_TOKEN }}"}
    assert all(not {"HF_TOKEN", "GITHUB_TOKEN"}.intersection(step.get("env", {}))
               for step in steps if step not in (selected, metadata, setup)
               and step.get("id") not in {"admission", "retention"})
    assert '--input-transport "${INPUT_TRANSPORT:-github_draft}"' in selected["run"]
    assert selected["run"].index("unset GITHUB_TOKEN HF_TOKEN") < selected["run"].index("--resume --check-inputs")
    assert "HF_HUB_OFFLINE=0" not in selected["run"]
    upload = next(step for step in steps if step.get("uses", "").startswith("actions/upload-artifact@"))
    assert upload["with"]["path"] == "${{ runner.temp }}/budget-pilot-ci-completion.json"
    assert "budget-pilot-ci-input" not in json.dumps(upload)
    assert len([step for step in steps if "uses" in step and "upload-artifact" in step["uses"]]) == 1


@pytest.mark.parametrize("selected,release,allowed", [
    ("github_draft", "101", True), ("hf_originals", "", True),
    ("hf_originals", "101", False), ("unregistered", "", False),
])
def test_hf_originals_real_workflow_source_guard_routing(monkeypatch, tmp_path, selected, release, allowed):
    result = shell_block(workflow()["jobs"]["cell"]["steps"][0]["run"], monkeypatch=monkeypatch, tmp_path=tmp_path,
                         extra_env={"INPUT_TRANSPORT": selected, "INPUT_RELEASE_ID": release, "INPUT_ASSET_ID": ""})
    assert (result.returncode == 0) == allowed


@pytest.mark.parametrize("failure", ["fetch", "installed_check", None])
def test_hf_originals_actual_cli_failure_cannot_open_workflow_oidc_gate(hf_case, monkeypatch, tmp_path, failure):
    case = hf_case
    if failure == "fetch":
        case.hub.responses[0] = HubResponse(status=403)
    intake_status = invoke(case)
    check_status = 2 if failure == "installed_check" else 0
    selected = next(step for step in workflow()["jobs"]["cell"]["steps"] if step.get("id") == "intake")
    prefix = f'''\
timeout() {{ shift 4; python3 "$@"; }}
python3() {{
  if [[ "$1" == batch-runner/codex_ci_input_intake.py ]]; then
    [[ "$*" == *"--input-transport hf_originals"* ]] || return 99
    return {intake_status}
  fi
  [[ "$1" == batch-runner/codex_budget_pilot_ci.py ]] || return 99
  [[ "$*" == *"--resume --check-inputs"* && "$*" != *"--execute"* ]] || return 99
  [[ -z "${{HF_TOKEN:-}}" && -z "${{GITHUB_TOKEN:-}}" ]] || return 99
  echo "installed check reached"
  return {check_status}
}}
'''
    result = shell_block(selected["run"], monkeypatch=monkeypatch, tmp_path=tmp_path, prefix=prefix,
                         extra_env={"INPUT_TRANSPORT": "hf_originals", "INPUT_RELEASE_ID": "", "INPUT_ASSET_ID": "",
                                    "HF_TOKEN": HF_TOKEN, "GITHUB_TOKEN": "synthetic_other_transport_token"})
    assert (result.returncode == 0) == (failure is None)
    assert (tmp_path / "step-output").exists() == (failure is None)
    if failure == "fetch":
        assert "installed check reached" not in result.stdout
    admission = "success() && inputs.execute && !inputs.input_check && !inputs.output_target_check && !inputs.output_target_setup && steps.intake.outputs.verified == 'true'"
    downstream = [step for step in workflow()["jobs"]["cell"]["steps"] if step.get("if") == admission]
    assert len(downstream) == 4
    assert {step["name"] for step in downstream} == {
        "Install the existing native sandbox prerequisite", "Require the existing native sandbox prerequisite",
        "Require the existing native sandbox capability", "Claim only the next canonical cell before inference",
    }
    assert len([step for step in workflow()["jobs"]["cell"]["steps"]
                if step.get("if") == admission + " && steps.admission.outputs.admitted == 'true'"]) == 3
    # Static Actions condition check plus real local bash with fake commands;
    # not an executed workflow or evidence of HF/OIDC/model access.
