"""Private intake CLI with fake GitHub I/O and explicitly synthetic provenance.

The importer, archive/current-byte/reference/Step0 readers, reservations and
publication checks are real. Workflow checks parse YAML and exercise its bash
blocks with fake commands; they are not GitHub, OIDC or draft-access evidence.
"""

from __future__ import annotations

import copy
from email.message import Message
import io
import json
import os
from pathlib import Path
import stat
import subprocess
from types import SimpleNamespace
import urllib.error
import urllib.request

import pytest
import yaml

import codex_budget_pilot_ci as ci
import codex_ci_input_bundle as bundle
import codex_ci_input_intake as intake
from .test_codex_budget_pilot import REAL_POPEN, offline  # noqa: F401
from .test_codex_ci_input_bundle import originals, reservation  # noqa: F401

SHELL_RUN = subprocess.run
SYNTHETIC_TOKEN = "synthetic_github_token_never_publish"
SIGNED_TARGET = ("https://release-assets.githubusercontent.com/github-production-release-asset/123/"
                 "12345678-1234-1234-1234-123456789abc?sig=synthetic_private_signature")


class Response(io.BytesIO):
    def __init__(self, data=b"", *, status=200, headers=None, url=None, content_type="application/octet-stream"):
        super().__init__(data)
        self.status, self.url, self.reads = status, url, []
        self.headers = Message()
        for name, value in (headers if headers is not None else [
            ("Content-Length", str(len(data))), ("Content-Type", content_type),
        ]):
            self.headers[name] = value

    def geturl(self):
        return self.url

    def read1(self, amount):
        self.reads.append(amount)
        return super().read1(amount)


class GitHub:
    """Only the HTTP open boundary is fake; Requests/policy stay real."""

    def __init__(self, responses):
        self.responses, self.calls = list(responses), []
        self.before_response = None

    def open(self, request, *, timeout):
        self.calls.append((request, timeout))
        if self.before_response:
            self.before_response(len(self.calls))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        if response.url is None:
            response.url = request.full_url
        return response


@pytest.fixture
def intake_case(originals, monkeypatch):
    case = originals
    # Only provenance is synthetic: the real production SHA/size are not test
    # CLI flags, and no original parquet, private handoff or bundle is opened.
    manifest = bundle._manifest(case.revision, case.specs, case.files)
    case.archive = bundle._archive({bundle.MANIFEST: bundle._canonical_json(manifest).encode(), **case.files})
    case.identity = bundle._identity(case.archive)
    monkeypatch.setattr(intake, "BUNDLE_SIZE", case.identity["size"])
    monkeypatch.setattr(intake, "BUNDLE_SHA256", case.identity["sha256"])
    monkeypatch.setenv("GITHUB_REPOSITORY", intake.REPOSITORY)
    monkeypatch.setenv("GITHUB_TOKEN", SYNTHETIC_TOKEN)
    case.stage, case.installed = case.parent / "private-stage.tar", case.parent / "private-inputs"
    case.argv = ["--input-check", "--release-id", "101", "--asset-id", "202", "--expected-sha256",
                 case.identity["sha256"], "--bundle-out", str(case.stage), "--out", str(case.installed)]
    case.metadata = {
        "id": 101, "url": intake.API_ROOT + "101", "draft": True,
        "assets": [{"id": 202, "url": intake.API_ROOT + "assets/202", "state": "uploaded",
                    "name": "synthetic-originals.tar", "content_type": "application/x-tar",
                    "size": len(case.archive), "browser_download_url": "https://forbidden.example/never-use"}],
    }
    return case


def github(case, *, payload=None, metadata=None, status=200):
    return GitHub([Response(json.dumps(case.metadata if metadata is None else metadata).encode(),
                            status=status, content_type="application/json"),
                   Response(case.archive if payload is None else payload)])


def invoke(case, transport, argv=None):
    return intake.main(case.argv if argv is None else argv, _test_github=transport, _test_transport=case.transport)


def assert_no_install(case):
    assert not case.stage.exists() and not case.installed.exists()
    assert case.transport.calls == []


def workflow():
    return yaml.safe_load((ci.pilot.ROOT / ci.WORKFLOW).read_text())


def test_ci_input_intake_registered_anchor_is_external_and_unchanged():
    assert intake.BUNDLE_SIZE == 2519040
    assert intake.BUNDLE_SHA256 == "757603585405da5d7f6817a6a0a23bd530d4b5e4e38b2fd4dc6f318053d240e3"
    assert intake.REPOSITORY == ci.REPOSITORY == "hyeonsangjeon/gdpval-realworks"


def test_ci_input_intake_default_plan_never_reads_token_or_transfers(intake_case, monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        pytest.fail("plan constructed transport or imported originals")

    monkeypatch.delenv("GITHUB_TOKEN")
    monkeypatch.setattr(urllib.request, "build_opener", forbidden)
    monkeypatch.setattr(bundle, "import_bundle", forbidden)
    assert intake.main([]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "mode": "plan_only", "transfer_attempted": False, "draft_access": "not_observed",
        "oidc_requested": False, "model_requested": False,
    }
    assert_no_install(intake_case)


@pytest.mark.parametrize("redirect", [None, 302, 307])
def test_ci_input_intake_real_import_and_roles_without_credential_forwarding(intake_case, capsys, redirect):
    case = intake_case
    http = github(case)
    if redirect is not None:
        http.responses.insert(1, Response(b"unread redirect body", status=redirect, headers=[("Location", SIGNED_TARGET)]))
    handles = list(http.responses)
    assert invoke(case, http) == 0
    report = json.loads(capsys.readouterr().out)
    assert report == {"mode": "input_check", "repository": intake.REPOSITORY, "release_id": 101, "asset_id": 202,
                      "bundle": case.identity, "original_inputs_verified": True,
                      "draft_observed_at_metadata_read": True, "publication_authorized": False,
                      "oidc_requested": False, "model_requested": False}
    assert case.stage.read_bytes() == case.archive
    for role, data in case.files.items():
        assert (case.installed / role).read_bytes() == data
        assert stat.S_IMODE((case.installed / role).stat().st_mode) == 0o600
    assert stat.S_IMODE(case.installed.stat().st_mode) == 0o700
    assert stat.S_IMODE(case.stage.stat().st_mode) == 0o600
    assert json.loads((case.installed / bundle.READY).read_bytes())["bundle"] == case.identity
    assert case.transport.calls == [bundle.InputSources(case.installed / bundle.PARQUET,
                                                       case.installed / bundle.REFERENCES,
                                                       case.installed / bundle.STEP0)]
    assert [call[0].full_url for call in http.calls[:2]] == [intake.API_ROOT + "101", intake.API_ROOT + "assets/202"]
    for request, timeout in http.calls[:2]:
        assert request.get_method() == "GET" and request.get_header("Authorization") == "Bearer " + SYNTHETIC_TOKEN
        assert 0 < timeout <= intake.REQUEST_TIMEOUT_SECONDS
    if redirect is not None:
        request = http.calls[2][0]
        assert request.full_url == SIGNED_TARGET
        assert {key.lower() for key, _ in request.header_items()} == {"accept", "accept-encoding", "user-agent"}
        assert handles[1].reads == []
    assert all(response.closed for response in handles)
    assert reservation(case.stage).exists() and reservation(case.installed).exists()
    assert all(secret not in json.dumps(report) for secret in (SYNTHETIC_TOKEN, SIGNED_TARGET, str(case.parent)))


@pytest.mark.parametrize("flag,value", [
    ("--release-id", None), ("--asset-id", None), ("--release-id", "0"), ("--asset-id", "-1"),
    ("--release-id", "1e2"), ("--expected-sha256", None), ("--expected-sha256", "f" * 64), ("--out", None),
])
def test_ci_input_intake_explicit_selection_refused_before_network(intake_case, caplog, flag, value):
    case = intake_case
    argv = list(case.argv)
    index = argv.index(flag)
    if value is None:
        del argv[index:index + 2]
    else:
        argv[index + 1] = value
    http = github(case)
    assert invoke(case, http, argv) == 2
    assert "required" in caplog.text
    assert http.calls == [] and not reservation(case.stage).exists()
    assert_no_install(case)


@pytest.mark.parametrize("key,value", [("GITHUB_REPOSITORY", "someone/else"), ("GITHUB_TOKEN", "")])
def test_ci_input_intake_repository_and_existing_token_required(intake_case, monkeypatch, key, value):
    monkeypatch.setenv(key, value)
    http = github(intake_case)
    assert invoke(intake_case, http) == 2
    assert http.calls == []
    assert_no_install(intake_case)


@pytest.mark.parametrize("defect,reason", [
    ("repository", "release_ownership_or_identity"), ("release_id", "release_ownership_or_identity"),
    ("published", "private_draft"), ("draft_type", "private_draft"),
    ("membership", "selected_asset_membership"), ("duplicate", "selected_asset_membership"),
    ("asset_repository", "asset_ownership_or_state"), ("state", "asset_ownership_or_state"),
    ("size_type", "file_type_or_size"), ("oversized", "file_type_or_size"),
    ("type", "file_type_or_size"), ("name", "file_type_or_size"),
])
def test_ci_input_intake_metadata_must_bind_the_private_uploaded_asset(intake_case, caplog, defect, reason):
    case = intake_case
    meta = copy.deepcopy(case.metadata)
    asset = meta["assets"][0]
    if defect == "repository":
        meta["url"] = "https://api.github.com/repos/someone/else/releases/101"
    elif defect == "release_id":
        meta["id"] = True
    elif defect == "published":
        meta["draft"] = False
    elif defect == "draft_type":
        meta["draft"] = "true"
    elif defect == "membership":
        meta["assets"] = []
    elif defect == "duplicate":
        meta["assets"].append(copy.deepcopy(asset))
    elif defect == "asset_repository":
        asset["url"] = "https://api.github.com/repos/someone/else/releases/assets/202"
    elif defect == "state":
        asset["state"] = "new"
    elif defect == "size_type":
        asset["size"] = True
    elif defect == "oversized":
        asset["size"] += 1
    elif defect == "type":
        asset["content_type"] = "application/gzip"
    else:
        asset["name"] = "../private.tar"
    http = github(case, metadata=meta)
    assert invoke(case, http) == 2
    assert reason in caplog.text and len(http.calls) == 1
    assert reservation(case.stage).exists()
    assert_no_install(case)


@pytest.mark.parametrize("stage,status", [(0, 403), (0, 404), (1, 401)])
def test_ci_input_intake_draft_access_is_observed_not_assumed(intake_case, caplog, stage, status):
    case = intake_case
    http = github(case)
    secret_body = Response(b"synthetic token or private resource reason must stay unread")
    error = urllib.error.HTTPError(intake.API_ROOT + ("101" if stage == 0 else "assets/202"), status,
                                   "sensitive remote error", Message(), secret_body)
    http.responses[stage] = error
    assert invoke(case, http) == 2
    assert "github_draft_or_asset_inaccessible" in caplog.text
    assert "sensitive remote" not in caplog.text and secret_body.reads == [] and secret_body.closed
    assert len(http.calls) == stage + 1
    assert_no_install(case)


@pytest.mark.parametrize("defect", ["bytes", "assets", "invalid_json", "duplicate_key"])
def test_ci_input_intake_metadata_limits_and_parser_remain_real(intake_case, caplog, defect):
    case = intake_case
    http = github(case)
    if defect == "bytes":
        http.responses[0] = Response(b"x" * (intake.MAX_METADATA_BYTES + 1),
                                     headers=[("Content-Type", "application/json")])
    elif defect == "assets":
        meta = copy.deepcopy(case.metadata)
        meta["assets"] *= intake.MAX_ASSETS + 1
        http = github(case, metadata=meta)
    elif defect == "invalid_json":
        http.responses[0] = Response(b'{"draft":', content_type="application/json")
    else:
        http.responses[0] = Response(b'{"draft":true,"draft":false}', content_type="application/json")
    assert invoke(case, http) == 2
    assert len(http.calls) == 1 and "refused" in caplog.text
    assert_no_install(case)


@pytest.mark.parametrize("defect", ["short", "extra", "encoded", "missing_length", "duplicate_length", "digest"])
def test_ci_input_intake_payload_limits_and_external_digest_precede_staging(intake_case, caplog, defect):
    case = intake_case
    http = github(case)
    payload = case.archive[:-1] if defect == "short" else case.archive + b"x" if defect == "extra" else case.archive
    if defect == "digest":
        payload = bytes([payload[0] ^ 1]) + payload[1:]
    headers = [("Content-Type", "application/octet-stream")]
    if defect != "missing_length":
        headers.append(("Content-Length", str(len(case.archive))))
    if defect == "encoded":
        headers.append(("Content-Encoding", "gzip"))
    if defect == "duplicate_length":
        headers.append(("Content-Length", str(len(case.archive))))
    http.responses[1] = Response(payload, headers=headers)
    assert invoke(case, http) == 2
    expected = "external_bundle_digest_mismatch" if defect == "digest" else (
        "github_duplicate_response_header" if defect == "duplicate_length" else "response_")
    assert expected in caplog.text
    assert len(http.calls) == 2 and reservation(case.stage).exists()
    assert_no_install(case)


@pytest.mark.parametrize("target", [
    SIGNED_TARGET.replace("release-assets.githubusercontent.com", "evil.example"),
    SIGNED_TARGET.replace("https://", "http://"),
    SIGNED_TARGET.replace("https://", "https://user:password@"),
    SIGNED_TARGET.replace(".com/", ".com:443/"),
    SIGNED_TARGET.replace("/github-production-release-asset/", "/other/"),
    SIGNED_TARGET + "#fragment", SIGNED_TARGET.split("?")[0],
])
def test_ci_input_intake_hostile_redirect_never_receives_request_or_auth(intake_case, caplog, target):
    http = github(intake_case)
    response = Response(b"unread", status=302, headers=[("Location", target)])
    http.responses[1] = response
    assert invoke(intake_case, http) == 2
    assert "github_asset_redirect_target_refused" in caplog.text
    assert len(http.calls) == 2 and response.closed and response.reads == []
    assert target not in caplog.text and SYNTHETIC_TOKEN not in caplog.text
    assert_no_install(intake_case)


@pytest.mark.parametrize("stage", ["metadata", "second_hop", "automatic"])
def test_ci_input_intake_redirect_budget_cannot_be_bypassed(intake_case, caplog, stage):
    http = github(intake_case)
    redirect = Response(status=302, headers=[("Location", SIGNED_TARGET)])
    if stage == "metadata":
        http.responses[0] = redirect
    elif stage == "second_hop":
        http.responses[1] = redirect
        http.responses.append(Response(status=302, headers=[("Location", SIGNED_TARGET)]))
    else:
        http.responses[1].url = "https://unexpected.example/private"
    assert invoke(intake_case, http) == 2
    assert "redirect_refused" in caplog.text
    assert len(http.calls) == {"metadata": 1, "second_hop": 3, "automatic": 2}[stage]
    assert_no_install(intake_case)


def test_ci_input_intake_real_opener_disables_proxy_and_automatic_redirects(intake_case, monkeypatch):
    http = github(intake_case)
    handlers = []

    def build(*given):
        handlers.extend(given)
        return http

    monkeypatch.setattr(urllib.request, "build_opener", build)
    assert intake.main(intake_case.argv, _test_transport=intake_case.transport) == 0
    assert len(handlers) == 2
    assert isinstance(handlers[0], urllib.request.ProxyHandler) and handlers[0].proxies == {}
    assert isinstance(handlers[1], urllib.request.HTTPRedirectHandler)
    assert handlers[1].redirect_request(None, None, 302, "", {}, "https://evil.example") is None


def test_ci_input_intake_transport_errors_never_print_remote_or_private_fields(intake_case, capsys, caplog):
    secret = SYNTHETIC_TOKEN + " https://private.example/?sig=hidden /synthetic/private/auth"
    http = GitHub([urllib.error.URLError(secret)])
    assert invoke(intake_case, http) == 2
    assert "private_input_verification_or_transport_failed" in caplog.text
    assert secret not in caplog.text + capsys.readouterr().out
    assert_no_install(intake_case)


@pytest.mark.parametrize("role", ["staging", "reservation", "installed"])
def test_ci_input_intake_never_adopts_existing_or_partial_destinations(intake_case, role):
    case = intake_case
    path = {"staging": case.stage, "reservation": reservation(case.stage), "installed": case.installed}[role]
    path.write_bytes(b"retain this earlier private partial")
    http = github(case)
    for _ in range(2):
        assert invoke(case, http) == 2
        assert http.calls == [] and path.read_bytes() == b"retain this earlier private partial"
    assert case.transport.calls == []


def test_ci_input_intake_time_budget_is_shared_and_stops_next_request(intake_case, monkeypatch, caplog):
    clock = SimpleNamespace(now=100.0)
    monkeypatch.setattr(intake, "time", SimpleNamespace(monotonic=lambda: clock.now))
    http = github(intake_case)
    http.before_response = lambda count: setattr(clock, "now", 100.0 + intake.TRANSFER_TIMEOUT_SECONDS)
    assert invoke(intake_case, http) == 2
    assert "github_transfer_time_limit_exceeded" in caplog.text
    assert len(http.calls) == 1 and http.calls[0][1] == intake.REQUEST_TIMEOUT_SECONDS
    assert_no_install(intake_case)


def test_ci_input_intake_linked_parent_refuses_before_network(intake_case):
    case = intake_case
    alias = case.parent / "linked-input-parent"
    alias.symlink_to(case.root, target_is_directory=True)
    argv = list(case.argv)
    argv[argv.index("--out") + 1] = str(alias / "new-inputs")
    http = github(case)
    assert invoke(case, http, argv) == 2
    assert http.calls == [] and not reservation(case.stage).exists()
    assert_no_install(case)


def test_ci_input_intake_rejected_real_installed_reader_retains_partial_reservation(intake_case, monkeypatch):
    case = intake_case
    # Synthetic archive provenance accepts these bytes, but the unchanged real
    # canonical Step0 reader must reject them against its independent pin.
    case.files[bundle.STEP0] = bundle._canonical_json({"_schema_version": 3, "tasks": {}}).encode()
    case.specs[bundle.STEP0].update(bundle._identity(case.files[bundle.STEP0]))
    manifest = bundle._manifest(case.revision, case.specs, case.files)
    case.archive = bundle._archive({bundle.MANIFEST: bundle._canonical_json(manifest).encode(), **case.files})
    digest = bundle._identity(case.archive)["sha256"]
    monkeypatch.setattr(intake, "BUNDLE_SHA256", digest)
    monkeypatch.setattr(intake, "BUNDLE_SIZE", len(case.archive))
    case.metadata["assets"][0]["size"] = len(case.archive)
    case.argv[case.argv.index("--expected-sha256") + 1] = digest
    http = github(case)
    assert invoke(case, http) == 2
    assert len(case.transport.calls) == 1  # The real installed-input boundary was reached.
    assert case.installed.is_dir() and case.stage.is_file()
    assert not (case.installed / bundle.READY).exists()
    assert reservation(case.installed).exists() and reservation(case.stage).exists()
    before = case.stage.read_bytes(), (case.installed / bundle.PARQUET).read_bytes()
    assert invoke(case, http) == 2 and len(http.calls) == 2
    assert before == (case.stage.read_bytes(), (case.installed / bundle.PARQUET).read_bytes())


def test_ci_input_intake_external_anchor_does_not_replace_archive_validation(intake_case, monkeypatch):
    case = intake_case
    payload = b"X" * len(case.archive)
    digest = bundle._identity(payload)["sha256"]
    monkeypatch.setattr(intake, "BUNDLE_SHA256", digest)
    case.argv[case.argv.index("--expected-sha256") + 1] = digest
    assert invoke(case, github(case, payload=payload)) == 2
    assert case.stage.read_bytes() == payload and not case.installed.exists()
    assert case.transport.calls == [] and reservation(case.stage).exists()


def shell_block(text, *, monkeypatch, tmp_path, extra_env=None, prefix=""):
    # Only controlled harmless bash builtins run. No Python, token, provider or
    # network command is executed by this workflow-contract instrument.
    environment = {
        "PATH": os.environ["PATH"], "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REPOSITORY": ci.REPOSITORY,
        "GITHUB_REF": "refs/heads/main", "GITHUB_RUN_ATTEMPT": "1", "REVIEWED_SOURCE_SHA": "1" * 40,
        "GITHUB_SHA": "1" * 40, "PILOT_WORKFLOW_SHA": "1" * 40, "SELECTED_CELL": "synthetic-cell",
        "RUNNER_TEMP": str(tmp_path), "GITHUB_OUTPUT": str(tmp_path / "step-output"),
        "EXECUTE_REQUESTED": "false", "INPUT_CHECK_REQUESTED": "false", "INPUT_RELEASE_ID": "101",
        "INPUT_ASSET_ID": "202", "INPUT_BUNDLE_SHA256": "a" * 64,
        **(extra_env or {}),
    }
    with monkeypatch.context() as scoped:
        scoped.setattr(subprocess, "Popen", REAL_POPEN)
        return SHELL_RUN(["bash", "-c", prefix + "\n" + text], env=environment, cwd=tmp_path,
                         capture_output=True, text=True, timeout=5, check=False)


@pytest.mark.parametrize("execute,input_check,allowed", [
    ("false", "false", True), ("false", "true", True), ("true", "false", True), ("true", "true", False),
])
def test_ci_input_intake_workflow_modes_fail_before_credentials(monkeypatch, tmp_path, execute, input_check, allowed):
    result = shell_block(workflow()["jobs"]["cell"]["steps"][0]["run"], monkeypatch=monkeypatch, tmp_path=tmp_path,
                         extra_env={"EXECUTE_REQUESTED": execute, "INPUT_CHECK_REQUESTED": input_check})
    assert (result.returncode == 0) == allowed
    if not allowed:
        assert result.stdout.strip() == "input_check_and_execute_are_mutually_exclusive"


@pytest.mark.parametrize("failure", ["intake", "installed_check", None])
def test_ci_input_intake_workflow_verified_output_requires_both_real_intake_and_check(intake_case, monkeypatch, tmp_path, failure):
    case = intake_case
    http = github(case, status=403 if failure == "intake" else 200)
    actual_intake_status = invoke(case, http)
    check_status = 2 if failure == "installed_check" else 0
    step = next(row for row in workflow()["jobs"]["cell"]["steps"] if row.get("id") == "intake")
    prefix = f'''\
timeout() {{ shift 4; python3 "$@"; }}
python3() {{
  if [[ "$1" == batch-runner/codex_ci_input_intake.py ]]; then
    return {actual_intake_status}
  fi
  [[ "$1" == batch-runner/codex_budget_pilot_ci.py ]] || return 99
  [[ "$*" == *"--resume --check-inputs"* ]] || return 99
  [[ "$*" != *"--execute"* ]] || return 99
  echo "installed check reached"
  return {check_status}
}}
'''
    result = shell_block(step["run"], monkeypatch=monkeypatch, tmp_path=tmp_path, prefix=prefix)
    output = tmp_path / "step-output"
    assert (result.returncode == 0) == (failure is None)
    assert output.exists() == (failure is None)
    if failure is None:
        assert output.read_text() == "verified=true\n"
    if failure == "intake":
        assert "installed check reached" not in result.stdout
    job = workflow()["jobs"]["cell"]
    runtime_steps = [row for row in job["steps"] if row["name"] in {
        "Require the existing native sandbox prerequisite", "Azure Login (OIDC)",
        "Verify existing Azure OIDC session identity", "Execute only the selected cell on this live host",
    }]
    assert len(runtime_steps) == 4
    assert all(row["if"] == "success() && inputs.execute && !inputs.input_check && steps.intake.outputs.verified == 'true'"
               for row in runtime_steps)
    # Static GitHub condition contract: false execute/input-check or no verified
    # output closes every native/OIDC stage. No Actions runner is being executed.
