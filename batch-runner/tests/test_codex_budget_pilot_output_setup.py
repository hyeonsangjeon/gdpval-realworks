"""Offline fixed-target setup CLI/HTTP contracts; no real account or mutation.

CI/source/runtime-version capabilities and all provider replies are synthetic.
The compiler, SDK, bounded HTTP guard and private no-clobber files are real.
Workflow assertions are static, not an Actions run or destination approval.
"""

from datetime import datetime
import hashlib
import json
import logging
import os
from pathlib import Path
import signal
import socket
import stat
import subprocess
import tempfile
import time
from types import SimpleNamespace

import httpx
from huggingface_hub import HfApi, RepoUrl, constants, hf_api
from huggingface_hub.utils import _auth, _headers, _http
import pytest
import yaml

import codex_budget_pilot as pilot
import codex_budget_pilot_ci as ci
import codex_budget_pilot_output as output
import codex_ci_input_intake as intake

SOURCE = "1" * 40
HEAD = "9" * 40  # Synthetic HF HEAD, never the declared execution-source SHA.
CELL = "02aa1805-c658-4069-8a6a-02dec146063a_A_r1"
TOKEN = "hf_SYNTHETIC_SETUP_ONLY"
RAW = "Bearer synthetic-secret https://signed.invalid/?secret=value /private/auth/cache.json"
FIELDS = {"role", "repository_name_sha256", "private", "head", "http_status", "outcome", "stage",
          "reason", "recorded_at", "write_access", "prefix_readiness", "publication_authorized",
          "model_requested", "grading_launched"}


class SourceOnly(pilot.LocalTransport):
    def __init__(self):
        self.checks = 0

    def require_source(self, plan, parent):
        assert plan["reviewed_source_sha"] == SOURCE and plan["ci"]["selected_cell_id"] == CELL
        assert len(plan["cells"]) == 30 and parent is not None
        self.checks += 1
        return {"tree_sha": "2" * 40, "common": "synthetic-source-capability"}


@pytest.fixture
def case(monkeypatch, caplog):
    excluded = []

    def blocked(*args, **kwargs):
        excluded.append(True)
        raise AssertionError("setup crossed an excluded offline boundary")

    for target, names in (
        (subprocess, ("Popen", "run", "check_call", "check_output")),
        (socket, ("create_connection",)), (socket.socket, ("connect", "connect_ex")),
        (time, ("sleep",)), (_auth, ("get_token",)), (_headers, ("get_token",)),
        (hf_api, ("_get_token_from_file", "_get_token_from_environment", "_get_token_from_google_colab")),
        (pilot.LocalTransport, ("require_execution", "inputs", "checkout", "child", "process")),
        (ci, ("_inputs",)), (output, ("prepare", "publish", "inspect_output_target")),
        (intake, ("intake", "intake_hf_originals", "_hf_origins", "_hf_read")),
        (HfApi, ("create_commit", "upload_file", "upload_folder", "delete_repo",
                 "update_repo_settings", "get_paths_info", "list_repo_files")),
    ):
        for name in names:
            monkeypatch.setattr(target, name, blocked)
    for key, value in {
        "GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": ci.REPOSITORY,
        "GITHUB_REF": "refs/heads/main", "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_SHA": SOURCE, "PILOT_WORKFLOW_SHA": SOURCE, "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_WORKFLOW_REF": ci.REPOSITORY + "/" + ci.WORKFLOW + "@refs/heads/main",
        "RUNNER_OS": "Linux", "ImageOS": "ubuntu22", "GITHUB_RUN_ID": "1234",
        "GITHUB_JOB": "cell", "RUNNER_NAME": "synthetic-setup-host",
        "HF_HUB_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1", "HF_HUB_DISABLE_TELEMETRY": "1",
        "HF_TOKEN": TOKEN, "HUGGING_FACE_HUB_TOKEN": "synthetic-ambient-hf",
        "GITHUB_TOKEN": "synthetic-ambient-github",
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(constants, "HF_HUB_OFFLINE", True)
    real_version = ci.importlib.metadata.version
    monkeypatch.setattr(ci.importlib.metadata, "version", lambda name:
                        "0.147.0" if name in {"openai-codex", "openai-codex-cli-bin"} else real_version(name))
    historical = pilot.load_plan(pilot.ROOT / pilot.CODEX_TEMPLATE)["data"]["source"]
    assert hashlib.sha256(historical.encode()).hexdigest() == output.OUTPUT_TARGET_REPO_SHA256
    namespace = historical.split("/")[0]
    repo = namespace + "/gdpval-codex-budget-pilot-ci-20260923"
    state = SimpleNamespace(
        historical=historical, namespace=namespace, repo=repo, source=SourceOnly(), requests=[], sdk=[],
        dispatches=[], status={"account": 200, "candidate_absence": 404, "create": 200, "created_metadata": 200},
        account={"type": "user", "name": namespace, "auth": RAW},
        existing={"id": repo, "private": True, "sha": HEAD},
        created={"url": output.HF_ENDPOINT + "/datasets/" + repo},
        metadata={"id": repo, "private": True, "sha": HEAD, "siblings": [{"rfilename": RAW}]},
        failures={}, hook=None, logs=caplog,
        argv=["--campaign-id", ci.CAMPAIGN, "--cell", CELL, "--reviewed-source-sha", SOURCE],
    )
    real_dispatch = pilot.dispatch

    def dispatch(*args, **kwargs):
        state.dispatches.append(True)
        return real_dispatch(*args, **kwargs)

    monkeypatch.setattr(pilot, "dispatch", dispatch)
    real_whoami, real_info, real_create = HfApi.whoami, HfApi.repo_info, HfApi.create_repo

    def whoami(api, **kwargs):
        assert kwargs == {"token": TOKEN, "cache": False}
        state.sdk.append("account")
        return real_whoami(api, **kwargs)

    def info(api, **kwargs):
        valid = (kwargs["repo_id"] == repo and kwargs["repo_type"] == "dataset"
                 and kwargs["token"] == TOKEN and 0 < kwargs["timeout"] <= 30
                 and kwargs.get("revision") in (None, "main"))
        if not valid:
            raise AssertionError("fixed explicit metadata request required")
        state.sdk.append("metadata")
        return real_info(api, **kwargs)

    def create(api, **kwargs):
        valid = kwargs == {"repo_id": repo, "repo_type": "dataset", "token": TOKEN,
                           "private": True, "exist_ok": False}
        if not valid:
            raise AssertionError("exact private non-adopting creation required")
        state.sdk.append("create")
        return real_create(api, **kwargs)

    def request(transport, message):
        routes = {("GET", output.HF_ENDPOINT + "/api/whoami-v2"): "account",
                  ("GET", output.HF_ENDPOINT + "/api/datasets/" + repo): "candidate_absence",
                  ("POST", output.HF_ENDPOINT + "/api/repos/create"): "create",
                  ("GET", output.HF_ENDPOINT + "/api/datasets/" + repo + "/revision/main"): "created_metadata"}
        stage = routes.get((message.method, str(message.url)))
        if stage is None or message.headers.get("authorization") != "Bearer " + TOKEN:
            raise AssertionError("noncanonical setup request escaped guard")
        state.requests.append(stage)
        assert all(0 < value <= 30 for value in message.extensions["timeout"].values())
        assert 0 < signal.getitimer(signal.ITIMER_REAL)[0] <= 120
        assert constants.HF_HUB_OFFLINE is False and os.environ["HF_HUB_OFFLINE"] == "0"
        assert os.environ["HF_DATASETS_OFFLINE"] == "1"
        assert all(key not in os.environ for key in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "GITHUB_TOKEN"))
        reservation = state.attempt / output.SETUP_RESERVATION
        pilot._regular_private(reservation)
        assert json.loads(reservation.read_bytes())["outcome"] == "unresolved"
        if stage == "create":
            body = json.loads(message.content)
            common = {"organization": namespace, "name": output.OUTPUT_SETUP_BASENAME, "type": "dataset"}
            assert body in ({**common, "visibility": "private"}, {**common, "private": True})
        if state.hook is not None:
            state.hook(stage)
        failure = state.failures.get(stage)
        if failure == "lost":
            raise httpx.ReadError(RAW)
        if failure == "timeout":
            signal.raise_signal(signal.SIGALRM)
        if failure == "interrupt":
            raise KeyboardInterrupt(RAW)
        if failure == "json":
            return httpx.Response(200, content=RAW.encode())
        if failure == "size":
            return httpx.Response(200, stream=httpx.ByteStream(b"x" * (output.MAX_RECORD_BYTES + 1)))
        payload = {"account": state.account, "candidate_absence": state.existing,
                   "create": state.created, "created_metadata": state.metadata}[stage]
        if state.status[stage] >= 400:
            return httpx.Response(state.status[stage], content=(
                "Cannot create repo: another conflicting operation is in progress " + RAW).encode())
        return httpx.Response(state.status[stage], json=payload, headers={"location": RAW})

    monkeypatch.setattr(HfApi, "whoami", whoami)
    monkeypatch.setattr(HfApi, "repo_info", info)
    monkeypatch.setattr(HfApi, "create_repo", create)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", request)
    with tempfile.TemporaryDirectory(prefix=".output-setup-offline-", dir=pilot.ROOT.parent) as scratch:
        state.root, state.attempt = Path(scratch), Path(scratch) / "attempt"
        monkeypatch.setenv("GDPVAL_CODEX_RUN_ROOT", str(state.root / "unrelated-native"))
        yield state
        assert excluded == []  # Caught exceptions must not hide an excluded operation.


def invoke(case, capsys, *options, create=True):
    factory, disabled = _http._GLOBAL_CLIENT_FACTORY, logging.root.manager.disable
    env = {name: os.environ.get(name) for name in
           ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "GITHUB_TOKEN", "HF_HUB_OFFLINE", "HF_DATASETS_OFFLINE")}
    args = [*case.argv, "--output-target-setup"]
    if create:
        args += ["--create-output-target", "--setup-state", str(case.attempt)]
    code = ci.main([*args, *options], _test_transport=case.source)
    captured = capsys.readouterr()
    for private in (case.repo, case.historical, case.namespace, TOKEN, RAW, str(case.root)):
        if private in captured.out + captured.err + case.logs.text:
            raise AssertionError("setup output exposed a private field")
    assert _http._GLOBAL_CLIENT_FACTORY is factory and logging.root.manager.disable == disabled
    assert constants.HF_HUB_OFFLINE is True and signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)
    assert {name: os.environ.get(name) for name in env} == env
    assert case.dispatches == []
    if not captured.out:
        return code, None
    assert len(captured.out.encode()) < 2048
    record = json.loads(captured.out)
    assert set(record) == FIELDS and record["role"] == "pilot_private_output_candidate"
    assert record["repository_name_sha256"] in (None, hashlib.sha256(case.repo.encode()).hexdigest())
    assert record["publication_authorized"] is record["model_requested"] is record["grading_launched"] is False
    assert record["write_access"] == record["prefix_readiness"] == "not_established"
    assert datetime.fromisoformat(record["recorded_at"]).utcoffset().total_seconds() == 0
    return code, record


def forbid_token_lookup(monkeypatch):
    class NoToken(dict):
        def get(self, name, *args):
            if name in {"HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "GITHUB_TOKEN"}:
                raise AssertionError("plan inspected a credential")
            return super().get(name, *args)

    monkeypatch.setattr(os, "environ", NoToken(os.environ))


def test_setup_default_cell_plan_has_no_token_or_network(case, monkeypatch, capsys):
    forbid_token_lookup(monkeypatch)
    completion = case.root / "completion.json"
    assert ci.main([*case.argv, "--output", str(case.root / "plan"), "--completion-out", str(completion)],
                   _test_transport=case.source) == 0
    record = ci.validate_completion(pilot._load(completion))
    assert record["status"] == "pending" and record["child_invocations"] == 0
    assert record["execution_requested"] is False and record["verified_inputs_sha256"] is None
    assert case.requests == case.sdk == [] and capsys.readouterr().out == ""


def test_setup_selected_plan_has_no_token_network_or_private_files(case, monkeypatch, capsys):
    forbid_token_lookup(monkeypatch)
    assert ci.main([*case.argv, "--output-target-setup"], _test_transport=case.source) == 0
    record = json.loads(capsys.readouterr().out)
    assert record["outcome"] == "plan_only" and record["private"] is record["head"] is record["http_status"] is None
    assert record["repository_name_sha256"] == hashlib.sha256(case.repo.encode()).hexdigest()
    assert not case.attempt.exists() and case.requests == case.sdk == case.dispatches == []


@pytest.mark.parametrize("options", [["--output-target-check"], ["--execute"], ["--check-inputs"], ["--resume"],
    ["--verify-envelope", RAW], ["--dataset-parquet", RAW], ["--reference-root", RAW],
    ["--step0-manifest", RAW], ["--output", RAW], ["--completion-out", RAW], ["--unknown", RAW]])
def test_setup_conflicts_fail_before_source_or_token(case, capsys, options):
    assert invoke(case, capsys, *options) == (2, None)
    assert case.source.checks == 0 and case.requests == case.sdk == [] and not case.attempt.exists()


@pytest.mark.parametrize("options", [["--create-output-target"], ["--setup-state", RAW],
    ["--output-target-setup", "--create-output-target"], ["--output-target-setup", "--setup-state", RAW]])
def test_setup_requires_explicit_mode_and_new_state_together(case, capsys, options):
    assert ci.main([*case.argv, *options], _test_transport=case.source) == 2
    assert RAW not in capsys.readouterr().err and case.source.checks == 0 and case.requests == []


@pytest.mark.parametrize("failure", ["attempt", "source", "cell", "campaign"])
def test_setup_genuine_source_cell_and_attempt_gates(case, monkeypatch, capsys, failure):
    if failure == "attempt":
        monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")
    elif failure == "source":
        monkeypatch.setenv("PILOT_WORKFLOW_SHA", "0" * 40)
    else:
        case.argv[1 if failure == "campaign" else 3] = "foreign"
    assert invoke(case, capsys) == (2, None)
    assert case.requests == [] and not case.attempt.exists()


@pytest.mark.parametrize("token", ["", "bad token", "bad\nvalue", "x" * 4097])
def test_setup_missing_invalid_auth_does_not_search_cache(case, monkeypatch, capsys, token):
    monkeypatch.setenv("HF_TOKEN", token)
    code, record = invoke(case, capsys)
    assert code == 2 and record["reason"] == "explicit_hf_token_required"
    assert record["http_status"] is None and case.requests == [] and not case.attempt.exists()


def test_setup_profile_fingerprint_precedes_credentials(case, monkeypatch, capsys):
    original = pilot.load_plan

    def changed(path):
        data = original(path)
        if path == pilot.ROOT / pilot.CODEX_TEMPLATE:
            data["data"]["source"] = "synthetic/foreign"
        return data

    # Derivation runs after the genuine compiler/source gate, not a fake matrix.
    original_source = case.source.require_source

    def source(plan, parent):
        original_source(plan, parent)
        monkeypatch.setattr(pilot, "load_plan", changed)

    monkeypatch.setattr(case.source, "require_source", source)
    code, record = invoke(case, capsys)
    assert code == 2 and record["reason"] == "registered_output_target_mismatch"
    assert record["repository_name_sha256"] is None and case.requests == [] and not case.attempt.exists()


@pytest.mark.parametrize("kind", ["foreign_user", "organization", "missing_type", "org_membership"])
def test_setup_only_current_exact_user_namespace_qualifies(case, capsys, kind):
    case.account = {"type": "user", "name": "synthetic-foreign"}
    if kind == "organization":
        case.account = {"type": "org", "name": case.namespace}
    elif kind == "missing_type":
        case.account = {"name": case.namespace}
    elif kind == "org_membership":
        case.account["orgs"] = [{"name": case.namespace}]
    code, record = invoke(case, capsys)
    assert code == 2 and record["reason"] == "authenticated_output_namespace_mismatch"
    assert record["outcome"] == "refused" and record["http_status"] == 200
    assert case.requests == ["account"]


@pytest.mark.parametrize("private", [True, False, None])
def test_setup_existing_target_is_never_adopted_or_changed(case, capsys, private):
    case.status["candidate_absence"] = 200
    case.existing["private"] = private
    case.existing["sha"] = None  # Repository-level existence, even without main.
    code, record = invoke(case, capsys)
    assert code == 2 and record["reason"] == "output_target_already_exists"
    assert record["private"] is private and record["head"] is None
    assert case.requests == ["account", "candidate_absence"]


def test_setup_foreign_existing_metadata_is_not_attributed_to_candidate(case, capsys):
    case.status["candidate_absence"] = 200
    case.existing["id"] = "synthetic/foreign"
    code, record = invoke(case, capsys)
    assert code == 2 and record["reason"] == "output_target_identity_mismatch"
    assert record["private"] is record["head"] is None and len(case.requests) == 2


@pytest.mark.parametrize("stage,status", [("account", 401), ("account", 403), ("account", 429),
    ("candidate_absence", 403), ("candidate_absence", 500), ("candidate_absence", 307),
    ("create", 409), ("create", 403), ("created_metadata", 404)])
def test_setup_http_failures_preserve_actual_stage_status_without_retry(case, capsys, stage, status):
    case.status[stage] = status
    code, record = invoke(case, capsys)
    assert code == 2 and record["stage"] == stage and record["http_status"] == status
    assert record["outcome"] == ("unresolved" if stage in {"create", "created_metadata"} else "refused")
    assert case.requests[-1] == stage and case.requests.count(stage) == 1
    receipt = json.loads((case.attempt / output.SETUP_RECEIPT).read_bytes())
    assert receipt["http_status"] == status and receipt["outcome"] == record["outcome"]


@pytest.mark.parametrize("status", [200, 201])
def test_setup_exact_private_create_and_actual_head_receipt(case, capsys, status):
    case.status["create"] = status
    code, record = invoke(case, capsys)
    assert code == 0 and record["outcome"] == "created" and record["private"] is True
    assert record["head"] == HEAD and record["head"] != SOURCE and record["http_status"] == 200
    assert case.requests == ["account", "candidate_absence", "create", "created_metadata"]
    reservation = json.loads((case.attempt / output.SETUP_RESERVATION).read_bytes())
    receipt = json.loads((case.attempt / output.SETUP_RECEIPT).read_bytes())
    assert reservation["outcome"] == "unresolved" and "head" not in reservation
    assert receipt["output_repository"] == case.repo and receipt["create_acknowledged"] is True
    assert receipt["head"] == HEAD and receipt["privacy_atomic_with_create"] is False
    assert receipt["responses"] == [{"stage": phase, "http_status": code} for phase, code in
        (("account", 200), ("candidate_absence", 404), ("create", status), ("created_metadata", 200))]
    for file in (case.attempt / output.SETUP_RESERVATION, case.attempt / output.SETUP_RECEIPT):
        assert stat.S_IMODE(file.stat().st_mode) == 0o600 and file.stat().st_nlink == 1
        assert TOKEN not in file.read_text() and RAW not in file.read_text()
    assert stat.S_IMODE(case.attempt.stat().st_mode) == 0o700
    before = [file.read_bytes() for file in (case.attempt / output.SETUP_RESERVATION, case.attempt / output.SETUP_RECEIPT)]
    code, second = invoke(case, capsys)
    assert code == 2 and second["reason"] == "output_target_setup_already_reserved"
    assert len(case.requests) == 4 and before == [file.read_bytes() for file in
        (case.attempt / output.SETUP_RESERVATION, case.attempt / output.SETUP_RECEIPT)]


@pytest.mark.parametrize("field,value,reason", [
    ("id", "synthetic/foreign", "output_target_identity_mismatch"),
    ("private", False, "private_output_target_required"), ("private", 1, "private_output_target_required"),
    ("sha", None, "setup_head_unavailable"), ("sha", "main", "setup_head_unavailable"),
])
def test_setup_postcreate_failure_is_unresolved_without_marker(case, capsys, field, value, reason):
    case.metadata[field] = value
    code, record = invoke(case, capsys)
    assert code == 2 and record["reason"] == reason and record["outcome"] == "unresolved"
    assert len(case.requests) == 4
    receipt = json.loads((case.attempt / output.SETUP_RECEIPT).read_bytes())
    assert receipt["create_acknowledged"] is True and receipt["marker_upload"] is False
    if field == "id":
        assert record["private"] is record["head"] is None


@pytest.mark.parametrize("foreign", ["https://huggingface.co/datasets/synthetic/foreign", "https://signed.invalid/foreign"])
def test_setup_foreign_create_acknowledgment_stops_before_verification(case, capsys, foreign):
    case.created["url"] = foreign
    code, record = invoke(case, capsys)
    assert code == 2 and record["outcome"] == "unresolved" and record["head"] is None
    assert case.requests == ["account", "candidate_absence", "create"]


@pytest.mark.parametrize("stage,failure,status", [("account", "lost", None), ("create", "lost", None),
    ("create", "timeout", None), ("create", "interrupt", None), ("created_metadata", "json", 200),
    ("created_metadata", "size", 200)])
def test_setup_transport_interruption_and_parse_failures_retain_evidence(case, capsys, stage, failure, status):
    case.failures[stage] = failure
    code, record = invoke(case, capsys)
    assert code == 2 and record["stage"] == stage and record["http_status"] == status
    assert record["outcome"] == ("refused" if stage == "account" else "unresolved")
    assert case.requests.count(stage) == 1
    count = len(case.requests)
    assert invoke(case, capsys)[1]["reason"] == "output_target_setup_already_reserved"
    assert len(case.requests) == count


@pytest.mark.parametrize("suffix", ["?secret=synthetic", "/extra", "#fragment", "foreign_host", "insecure"])
def test_setup_rejects_noncanonical_requests_before_transport(case, monkeypatch, capsys, suffix):
    def whoami(api, **kwargs):
        url = ("https://signed.invalid/api/whoami-v2" if suffix == "foreign_host"
               else "http://huggingface.co/api/whoami-v2" if suffix == "insecure"
               else output.HF_ENDPOINT + "/api/whoami-v2" + suffix)
        return _http.get_session().get(url,
                                       headers={"authorization": "Bearer " + TOKEN})

    monkeypatch.setattr(HfApi, "whoami", whoami)
    code, record = invoke(case, capsys)
    assert code == 2 and record["reason"] == "hf_setup_request_refused"
    assert record["http_status"] is None and case.requests == []


def test_setup_attempt_counter_spans_recreated_sdk_clients(case, monkeypatch, capsys):
    original = HfApi.whoami

    def repeat(api, **kwargs):
        original(api, **kwargs)
        _http.close_session()
        return original(api, **kwargs)

    monkeypatch.setattr(HfApi, "whoami", repeat)
    code, record = invoke(case, capsys)
    assert code == 2 and record["reason"] == "hf_setup_request_refused" and record["http_status"] is None
    assert case.requests == ["account"]


@pytest.mark.parametrize("change", ["public", "old_target", "foreign_namespace", "extra", "legacy", "numeric_private"])
def test_setup_transport_validates_exact_creation_body(case, monkeypatch, capsys, change):
    body = {"organization": case.namespace, "name": output.OUTPUT_SETUP_BASENAME,
            "type": "dataset", "visibility": "private"}
    if change == "public":
        body["visibility"] = "public"
    elif change == "old_target":
        body["name"] = case.historical.split("/")[1]
    elif change == "foreign_namespace":
        body["organization"] = "openai"
    elif change == "extra":
        body["resourceGroupId"] = RAW
    else:
        del body["visibility"]
        body["private"] = True if change == "legacy" else 1

    def create(api, **kwargs):
        response = _http.get_session().post(output.HF_ENDPOINT + "/api/repos/create", json=body,
                                            headers={"authorization": "Bearer " + TOKEN})
        return RepoUrl(response.json()["url"], endpoint=output.HF_ENDPOINT)

    monkeypatch.setattr(HfApi, "create_repo", create)
    code, record = invoke(case, capsys)
    assert code == (0 if change == "legacy" else 2)
    assert len(case.requests) == (4 if change == "legacy" else 2)
    if change != "legacy":
        assert record["reason"] == "hf_setup_create_body_refused" and record["http_status"] is None


@pytest.mark.parametrize("kind", ["directory", "file", "symlink"])
def test_setup_existing_or_unsafe_state_is_never_adopted(case, capsys, kind):
    if kind == "directory":
        case.attempt.mkdir()
    elif kind == "file":
        case.attempt.write_bytes(b"synthetic retained evidence")
    else:
        case.attempt.symlink_to(case.root, target_is_directory=True)
    code, record = invoke(case, capsys)
    assert code == 2 and record["outcome"] == "refused" and case.requests == []
    assert os.path.lexists(case.attempt)


@pytest.mark.parametrize("change", ["bytes", "hardlink"])
def test_setup_changed_reservation_refuses_create_at_transport_boundary(case, capsys, change):
    def tamper(stage):
        if stage == "candidate_absence":
            reservation = case.attempt / output.SETUP_RESERVATION
            if change == "bytes":
                reservation.write_bytes(b"synthetic altered reservation")
            else:
                os.link(reservation, case.attempt / "synthetic-second-link")

    case.hook = tamper
    code, record = invoke(case, capsys)
    assert code == 2 and record["outcome"] == "unresolved" and record["http_status"] is None
    assert case.requests == ["account", "candidate_absence"]


def test_setup_atomic_reservation_race_preserves_winner_and_never_calls_hf(case, monkeypatch, capsys):
    original = output._write_no_clobber

    def race(path, data):
        if path.name == output.SETUP_RESERVATION:
            path.write_bytes(b"synthetic concurrent reservation")
            path.chmod(0o600)
        original(path, data)

    monkeypatch.setattr(output, "_write_no_clobber", race)
    code, record = invoke(case, capsys)
    assert code == 2 and record["outcome"] == "refused" and case.requests == []
    assert (case.attempt / output.SETUP_RESERVATION).read_bytes() == b"synthetic concurrent reservation"
    assert not (case.attempt / output.SETUP_RECEIPT).exists()


def test_setup_receipt_failure_retains_unresolved_reservation_without_replay(case, monkeypatch, capsys):
    original = output._write_no_clobber

    def write(path, data):
        if path.name == output.SETUP_RECEIPT:
            raise OSError(RAW)
        original(path, data)

    monkeypatch.setattr(output, "_write_no_clobber", write)
    code, record = invoke(case, capsys)
    assert code == 2 and record["reason"] == "output_target_setup_receipt_unavailable"
    assert record["outcome"] == "unresolved" and record["head"] == HEAD
    assert json.loads((case.attempt / output.SETUP_RESERVATION).read_bytes())["outcome"] == "unresolved"
    assert not (case.attempt / output.SETUP_RECEIPT).exists()
    assert invoke(case, capsys)[1]["reason"] == "output_target_setup_already_reserved"
    assert len(case.requests) == 4


def test_setup_workflow_routing_is_static_and_keeps_model_input_and_publication_closed():
    document = yaml.safe_load((pilot.ROOT / ci.WORKFLOW).read_text())
    triggers = document.get("on", document.get(True))
    assert len(triggers["workflow_dispatch"]["inputs"]) == 10
    assert all(entry["inputs"]["output_target_setup"] == {
        **({"description": "Later authorized creation of the fixed private output dataset only; no inputs/OIDC/model"}
           if name == "workflow_dispatch" else {}), "required": False, "default": False, "type": "boolean"}
        for name, entry in triggers.items())
    assert document["permissions"] == {"contents": "read", "id-token": "write"}
    assert document["concurrency"] == {"group": "codex-budget-pilot-ci-20260923-01", "cancel-in-progress": False}
    job = document["jobs"]["cell"]
    assert job["timeout-minutes"] == 240 and job["runs-on"] == "ubuntu-22.04"
    assert job["env"]["HF_HUB_OFFLINE"] == job["env"]["HF_DATASETS_OFFLINE"] == "1"
    steps = job["steps"]
    boundary = steps[0]["run"]
    assert "output_target_setup_mode_conflict" in boundary
    assert all(name in boundary for name in ("GITHUB_RUN_ATTEMPT", "GITHUB_SHA", "PILOT_WORKFLOW_SHA", "workflow_dispatch"))
    setup = next(step for step in steps if step.get("id") == "output_setup")
    assert setup["if"] == "inputs.output_target_setup && !inputs.output_target_check && !inputs.execute && !inputs.input_check"
    assert setup["env"] == {"HF_TOKEN": "${{ secrets.HF_TOKEN }}"} and setup["timeout-minutes"] == 3
    assert "timeout --signal=TERM --kill-after=5s 130s" in setup["run"]
    assert "--output-target-setup --create-output-target" in setup["run"] and "--setup-state" in setup["run"]
    assert all(name not in setup["run"] for name in ("--execute", "--check-inputs", "--publish", "step8"))
    selected = [step for step in steps if step.get("id") in {"output_target", "intake"}
                or "inputs.execute" in step.get("if", "") and step is not setup]
    assert len(selected) == 6 and all("!inputs.output_target_setup" in step["if"] for step in selected)
    token_steps = [step.get("id") for step in steps if "HF_TOKEN" in step.get("env", {})]
    assert token_steps == ["output_target", "output_setup", "intake"]
    assert "HF_TOKEN" not in job["env"] and "GITHUB_TOKEN" not in job["env"]
    uploads = [step for step in steps if step.get("uses", "").startswith("actions/upload-artifact@")]
    assert len(uploads) == 1 and uploads[0]["with"]["path"] == "${{ runner.temp }}/budget-pilot-ci-completion.json"
    assert "setup" not in json.dumps(uploads) and output.PUBLICATION_SECONDS == 120 and output.REQUEST_SECONDS == 30
