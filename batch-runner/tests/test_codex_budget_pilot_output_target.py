"""Offline target-inspection CLI contracts, not live access or a workflow run.

The compiler and metadata SDK/HTTP guard are real. CI identity/source admission
and provider replies are explicitly synthetic; sockets, input, model, grading
subprocesses and publication are forbidden. Workflow routing checks are static.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import inspect
import json
import logging
import os
from pathlib import Path
import signal
import socket
import subprocess
import tempfile
import time
from types import SimpleNamespace

import httpx
from huggingface_hub import HfApi, constants
from huggingface_hub.utils import _auth, _headers, _http
import pytest
import yaml

import codex_budget_pilot as pilot
import codex_budget_pilot_ci as ci
import codex_budget_pilot_output as output
import codex_ci_input_intake as intake

SOURCE = "1" * 40  # Synthetic reviewed source/CI context, not a live review.
CELL = "02aa1805-c658-4069-8a6a-02dec146063a_A_r1"
HEAD = "9" * 40  # Synthetic provider HEAD, distinct from source/input revisions.
TOKEN = "hf_SYNTHETIC_METADATA_ONLY"
RAW = "Bearer synthetic-secret https://signed.invalid/?secret=value /private/auth/cache.json"
NAME_SHA = "88c9f1ba301718d90f8d59d8ddb681ee0c5e8ae7c2cbfd1b9ad246c10e15cccf"
FIELDS = {
    "role", "repository_name_sha256", "exact_identity_match", "private", "head", "http_status",
    "observed_at", "eligible_private_target", "write_access", "publication_authorized", "model_requested", "reason",
}


def forbidden(*args, **kwargs):
    raise AssertionError("offline target inspection crossed an excluded boundary")


class SourceOnly(pilot.LocalTransport):
    """Only clean-source capability is substituted, never compiler/HTTP gates."""

    def __init__(self):
        self.source_checks = 0
        self.after_source = None

    def require_source(self, plan, parent):
        assert plan["reviewed_source_sha"] == SOURCE
        assert plan["ci"]["selected_cell_id"] == CELL
        assert len(plan["cells"]) == 30 and parent is not None
        self.source_checks += 1
        if self.after_source is not None:
            self.after_source()
        return {"tree_sha": "2" * 40, "common": "synthetic-source-capability"}


@pytest.fixture
def case(monkeypatch, caplog):
    excluded_calls = []

    def blocked(*args, **kwargs):
        excluded_calls.append(True)
        forbidden()

    for target, names in (
        (subprocess, ("Popen", "run", "check_call", "check_output")),
        (socket, ("create_connection",)), (socket.socket, ("connect", "connect_ex")),
        (time, ("sleep",)), (_auth, ("get_token",)), (_headers, ("get_token",)),
        (pilot.LocalTransport, ("require_execution", "inputs", "checkout", "child", "process")),
        (ci, ("_inputs",)), (output, ("prepare", "publish", "_write_no_clobber")),
        (intake, ("intake", "intake_hf_originals", "_hf_origins", "_hf_read")),
        (HfApi, ("create_commit", "create_repo", "get_paths_info", "list_repo_files")),
    ):
        for name in names:
            monkeypatch.setattr(target, name, blocked)
    for key, value in {
        "GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": ci.REPOSITORY,
        "GITHUB_REF": "refs/heads/main", "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_SHA": SOURCE, "PILOT_WORKFLOW_SHA": SOURCE, "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_WORKFLOW_REF": ci.REPOSITORY + "/" + ci.WORKFLOW + "@refs/heads/main",
        "RUNNER_OS": "Linux", "ImageOS": "ubuntu22", "GITHUB_RUN_ID": "1234",
        "GITHUB_JOB": "cell", "RUNNER_NAME": "synthetic-metadata-host",
        "HF_HUB_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1", "HF_HUB_DISABLE_TELEMETRY": "1",
        "HF_TOKEN": TOKEN, "HUGGING_FACE_HUB_TOKEN": "synthetic-ambient-hf",
        "GITHUB_TOKEN": "synthetic-ambient-github",
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(constants, "HF_HUB_OFFLINE", True)
    real_version = ci.importlib.metadata.version
    monkeypatch.setattr(ci.importlib.metadata, "version", lambda name:
                        "0.147.0" if name in {"openai-codex", "openai-codex-cli-bin"} else real_version(name))
    # This is not a native SDK installation/capability test.
    repo = pilot.load_plan(pilot.ROOT / pilot.CODEX_TEMPLATE)["data"]["source"]
    assert hashlib.sha256(repo.encode()).hexdigest() == NAME_SHA
    state = SimpleNamespace(
        transport=SourceOnly(), repo=repo, requests=[], sdk_calls=[], status=200, logs=caplog,
        failure=None, metadata={"id": repo, "private": True, "sha": HEAD,
                                "siblings": [{"rfilename": RAW}], "raw_private": RAW},
        argv=["--campaign-id", ci.CAMPAIGN, "--cell", CELL, "--reviewed-source-sha", SOURCE],
    )
    real_repo_info = HfApi.repo_info

    def repo_info(api, **kwargs):
        state.sdk_calls.append(kwargs)
        valid = (kwargs["repo_id"] == repo and kwargs["repo_type"] == "dataset"
                 and kwargs["revision"] == "main" and kwargs["token"] == TOKEN
                 and 0 < kwargs["timeout"] <= 20)
        if not valid:
            raise AssertionError("fixed_explicit_metadata_request_required")
        return real_repo_info(api, **kwargs)

    class Broken(httpx.SyncByteStream):
        def __iter__(self):
            raise httpx.ReadError(RAW)
            yield b""  # pragma: no cover

    def request(transport, message):
        state.requests.append(message)
        valid = (message.method == "GET"
                 and str(message.url) == f"https://huggingface.co/api/datasets/{repo}/revision/main"
                 and message.headers.get("authorization") == "Bearer " + TOKEN)
        if not valid:
            raise AssertionError("exact_single_metadata_get_required")
        assert all(0 < number <= 20 for number in message.extensions["timeout"].values())
        assert 0 < signal.getitimer(signal.ITIMER_REAL)[0] <= 20
        assert constants.HF_HUB_OFFLINE is False and os.environ["HF_HUB_OFFLINE"] == "0"
        assert os.environ["HF_DATASETS_OFFLINE"] == "1"
        assert all(name not in os.environ for name in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "GITHUB_TOKEN"))
        if state.failure == "connect":
            raise httpx.ConnectError(RAW)
        if state.failure == "timeout":
            signal.raise_signal(signal.SIGALRM)
        if state.failure == "interrupt":
            raise KeyboardInterrupt(RAW)
        if state.failure == "body":
            return httpx.Response(200, stream=Broken())
        if state.failure == "json":
            return httpx.Response(200, content=RAW.encode())
        if state.failure == "size":
            # Like HTTPTransport, expose an unread stream so the real byte
            # guard sees it before the SDK's JSON parser. Prebuffered content
            # would bypass Response.read(), unlike a network response.
            return httpx.Response(200, stream=httpx.ByteStream(b"x" * (output.MAX_RECORD_BYTES + 1)))
        return httpx.Response(state.status, json=state.metadata, headers={"location": "https://signed.invalid/?secret=value"})

    monkeypatch.setattr(HfApi, "repo_info", repo_info)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", request)
    with tempfile.TemporaryDirectory(prefix=".output-target-offline-", dir=pilot.ROOT.parent) as scratch:
        state.root = Path(scratch)
        monkeypatch.setenv("GDPVAL_CODEX_RUN_ROOT", str(state.root / "unrelated-native"))
        yield state
        assert excluded_calls == []  # A caught refusal must not hide a forbidden operation.


def invoke(case, capsys, *options):
    old_factory, old_logging = _http._GLOBAL_CLIENT_FACTORY, logging.root.manager.disable
    env = {key: os.environ.get(key) for key in
           ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "GITHUB_TOKEN", "HF_HUB_OFFLINE", "HF_DATASETS_OFFLINE")}
    code = ci.main([*case.argv, "--output-target-check", *options], _test_transport=case.transport)
    captured = capsys.readouterr()
    assert all(value not in captured.out + captured.err + case.logs.text for value in (case.repo, TOKEN, RAW, str(case.root)))
    assert _http._GLOBAL_CLIENT_FACTORY is old_factory and logging.root.manager.disable == old_logging
    assert constants.HF_HUB_OFFLINE is True
    assert {key: os.environ.get(key) for key in env} == env
    assert signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)
    if not captured.out:
        return code, None
    assert len(captured.out.encode()) <= 2048
    record = json.loads(captured.out)
    assert set(record) == FIELDS and record["role"] == "exp033_submission_result"
    assert record["repository_name_sha256"] == NAME_SHA
    assert record["write_access"] == "not_established"
    assert record["publication_authorized"] is record["model_requested"] is False
    assert datetime.fromisoformat(record["observed_at"]).utcoffset().total_seconds() == 0
    assert not list(case.root.iterdir())  # Metadata mode creates no state or receipt.
    return code, record


def test_output_target_default_plan_has_no_token_lookup_or_network(case, monkeypatch, capsys):
    class NoToken(dict):
        def get(self, key, *args):
            if key in {"HF_TOKEN", "GITHUB_TOKEN", "HUGGING_FACE_HUB_TOKEN"}:
                forbidden()
            return super().get(key, *args)

    monkeypatch.setattr(os, "environ", NoToken(os.environ))
    monkeypatch.setattr(output, "_hf_client", forbidden)
    root, completion = case.root / "plan", case.root / "completion.json"
    assert ci.main([*case.argv, "--output", str(root), "--completion-out", str(completion)],
                   _test_transport=case.transport) == 0
    record = ci.validate_completion(pilot._load(completion))
    assert record["execution_requested"] is False and record["status"] == "pending"
    assert record["verified_inputs_sha256"] is None and record["child_invocations"] == 0
    assert record["artifacts"] == {"result": None, "ledger": None, "deliverables": []}
    assert case.sdk_calls == case.requests == [] and capsys.readouterr().out == ""


@pytest.mark.parametrize("options", [
    ["--execute"], ["--check-inputs"], ["--execute", "--check-inputs"], ["--resume"],
    ["--verify-envelope", RAW], ["--dataset-parquet", RAW], ["--reference-root", RAW],
    ["--step0-manifest", RAW], ["--output", RAW], ["--completion-out", RAW],
    ["--unrecognized", RAW],
])
def test_output_target_incompatible_and_unknown_arguments_stop_before_source_or_token(case, monkeypatch, capsys, options):
    monkeypatch.setattr(output, "inspect_output_target", forbidden)
    assert invoke(case, capsys, *options) == (2, None)
    assert case.transport.source_checks == 0 and case.sdk_calls == case.requests == []


@pytest.mark.parametrize("failure", ["rerun", "source", "cell", "campaign", "host", "clean_source"])
def test_output_target_genuine_ci_and_cell_gates_precede_metadata(case, monkeypatch, capsys, failure):
    if failure == "rerun":
        monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")
    elif failure == "source":
        monkeypatch.setenv("PILOT_WORKFLOW_SHA", "2" * 40)
    elif failure in {"cell", "campaign"}:
        option = "--cell" if failure == "cell" else "--campaign-id"
        case.argv[case.argv.index(option) + 1] = "foreign-" + RAW
    elif failure == "host":
        monkeypatch.setenv("ImageOS", "ubuntu24")
    else:
        def fail():
            raise OSError(RAW)
        case.transport.after_source = fail
    assert invoke(case, capsys) == (2, None)
    assert case.sdk_calls == case.requests == []


@pytest.mark.parametrize("token", [None, "", "contains space", "x" * 4097])
def test_output_target_missing_or_invalid_explicit_token_never_uses_cache(case, monkeypatch, capsys, token):
    if token is None:
        monkeypatch.delenv("HF_TOKEN")
    else:
        monkeypatch.setenv("HF_TOKEN", token)
    code, record = invoke(case, capsys)
    assert code == 2 and record["reason"] == "explicit_hf_token_required"
    assert record["private"] is record["head"] is record["http_status"] is None
    assert record["exact_identity_match"] is record["eligible_private_target"] is False
    assert case.sdk_calls == case.requests == []


def test_output_target_registered_name_mismatch_stops_before_token(case, monkeypatch, capsys):
    def after_source():
        monkeypatch.setattr(pilot, "load_plan", lambda path: {"data": {"source": "synthetic/foreign-target"}})
        monkeypatch.delenv("HF_TOKEN")
    case.transport.after_source = after_source
    # This intentionally changes only the local target-read boundary after the
    # real compiler/source gates, not the registered production source or pin.
    code = ci.main([*case.argv, "--output-target-check"], _test_transport=case.transport)
    captured = capsys.readouterr()
    record = json.loads(captured.out)
    assert code == 2 and record["reason"] == "registered_output_target_mismatch"
    assert "synthetic/foreign-target" not in captured.out + captured.err
    assert case.sdk_calls == case.requests == []


@pytest.mark.parametrize("private", [True, False, None, "true", 1])
def test_output_target_privacy_is_observed_not_approved(case, capsys, private):
    case.metadata["private"] = private
    code, record = invoke(case, capsys)
    assert len(case.sdk_calls) == len(case.requests) == 1
    assert record["exact_identity_match"] is True and record["http_status"] == 200
    assert record["head"] == HEAD
    assert record["private"] is (private if type(private) is bool else None)
    assert record["eligible_private_target"] is (private is True)
    assert code == (0 if private is True else 2)
    assert record["reason"] == (None if private is True else "private_output_target_required"
                                if private is False else "output_target_privacy_unavailable")


@pytest.mark.parametrize("head", [None, "main", "9" * 39, "Z" * 40, 9])
def test_output_target_no_fabricated_or_invalid_head(case, capsys, head):
    case.metadata["sha"] = head
    code, record = invoke(case, capsys)
    assert code == 2 and record["reason"] == "output_target_head_unavailable"
    assert record["private"] is True and record["head"] is None and record["http_status"] == 200


def test_output_target_foreign_response_is_not_attributed_to_registered_target(case, capsys):
    case.metadata["id"] = "synthetic/foreign-output"
    code, record = invoke(case, capsys)
    assert code == 2 and record["reason"] == "output_target_identity_mismatch"
    assert record["exact_identity_match"] is record["eligible_private_target"] is False
    assert record["private"] is record["head"] is None and record["http_status"] == 200


@pytest.mark.parametrize("status", [201, 204, 301, 307, 401, 403, 404, 429, 500, 503])
def test_output_target_http_refusal_retains_actual_status_without_retry_or_redirect(case, capsys, status):
    case.status = status
    code, record = invoke(case, capsys)
    assert code == 2 and record["http_status"] == status
    assert record["private"] is record["head"] is None and record["eligible_private_target"] is False
    assert len(case.sdk_calls) == len(case.requests) == 1
    assert record["reason"] == ("hf_http_failed" if status >= 400 else "hf_metadata_redirect_refused"
                                if status >= 300 else "hf_metadata_response_refused")


@pytest.mark.parametrize("failure,status,reason", [
    ("connect", None, "hf_transport_failed"), ("body", 200, "hf_transport_failed"),
    ("json", 200, "output_target_check_failed"), ("size", 200, "hf_response_bytes_exceeded"),
    ("timeout", None, "output_target_check_timeout"), ("interrupt", None, "output_target_check_interrupted"),
])
def test_output_target_no_response_and_parse_failure_never_invent_status(case, monkeypatch, capsys, failure, status, reason):
    case.failure = failure
    if failure == "size":
        monkeypatch.setattr(output, "MAX_RECORD_BYTES", 64)
    code, record = invoke(case, capsys)
    assert code == 2 and record["http_status"] == status and record["reason"] == reason
    assert len(case.requests) == 1 and record["eligible_private_target"] is False


def test_output_target_request_limit_spans_recreated_clients(case, monkeypatch, capsys):
    original = HfApi.repo_info
    def twice(api, **kwargs):
        original(api, **kwargs)
        _http.set_client_factory(_http._GLOBAL_CLIENT_FACTORY)
        return original(api, **kwargs)
    monkeypatch.setattr(HfApi, "repo_info", twice)
    code, record = invoke(case, capsys)
    assert code == 2 and record["reason"] == "hf_metadata_request_refused"
    assert record["http_status"] == 200 and len(case.requests) == 1


@pytest.mark.parametrize("change", ["host", "revision", "query", "method"])
def test_output_target_client_rejects_every_noncanonical_request_before_transport(case, monkeypatch, capsys, change):
    def unexpected(api, **kwargs):
        url = f"https://huggingface.co/api/datasets/{case.repo}/revision/main"
        if change == "host":
            url = url.replace("huggingface.co", "arbitrary.invalid")
        if change == "revision":
            url = url.removesuffix("main") + HEAD
        if change == "query":
            url += "?token=synthetic-secret"
        return _http.get_session().request("POST" if change == "method" else "GET", url,
                                           headers={"authorization": "Bearer " + TOKEN})
    monkeypatch.setattr(HfApi, "repo_info", unexpected)
    code, record = invoke(case, capsys)
    assert code == 2 and record["reason"] == "hf_metadata_request_refused"
    assert record["http_status"] is None and case.requests == []


def test_output_target_terminal_error_prevents_sdk_backoff(case, monkeypatch, capsys):
    case.status = 503
    def backoff(api, **kwargs):
        return _http.http_backoff("GET", f"https://huggingface.co/api/datasets/{case.repo}/revision/main",
                                  headers={"authorization": "Bearer " + TOKEN})
    monkeypatch.setattr(HfApi, "repo_info", backoff)
    code, record = invoke(case, capsys)
    assert code == 2 and record["http_status"] == 503 and len(case.requests) == 1


def test_output_target_shared_publication_defaults_are_unchanged():
    assert output.REQUEST_SECONDS == 30 and output.PUBLICATION_SECONDS == 120
    assert inspect.signature(output._time_bound).parameters["seconds"].default == 120
    assert inspect.signature(output._hf_client).parameters["metadata_repo"].default is None
    assert output.TARGET_CHECK_SECONDS == 20 and output.OUTPUT_TARGET_REPO_SHA256 == NAME_SHA


def test_output_target_optional_guard_does_not_change_default_publisher_http(case, monkeypatch):
    requests = []

    def respond(transport, request):
        requests.append(request)
        assert all(0 < number <= 30 for number in request.extensions["timeout"].values())
        if len(requests) == 1:
            return httpx.Response(307, headers={"location": "/api/synthetic-second"})
        return httpx.Response(200, json={})

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", respond)
    with output._time_bound() as deadline, intake._hf_environment(online=True):
        assert 20 < signal.getitimer(signal.ITIMER_REAL)[0] <= 120
        with output._hf_client(TOKEN, deadline):
            for _ in range(2):
                _http.get_session().get("https://huggingface.co/api/synthetic", headers={"authorization": "Bearer " + TOKEN})
    assert len(requests) == 3  # Default publication HTTP remains multi-request/redirect-capable.
    assert constants.HF_HUB_OFFLINE is True


def test_output_target_workflow_contract_is_static_not_an_actions_execution():
    document = yaml.safe_load((pilot.ROOT / ci.WORKFLOW).read_text())
    triggers = document.get("on", document.get(True))
    for entry in triggers.values():
        for mode in ("execute", "input_check", "output_target_check"):
            assert entry["inputs"][mode]["default"] is False
    assert document["permissions"] == {"contents": "read", "id-token": "write"}
    assert document["concurrency"] == {"group": "codex-budget-pilot-ci-20260923-01", "cancel-in-progress": False}
    job = document["jobs"]["cell"]
    assert job["timeout-minutes"] == 240 and job["runs-on"] == "ubuntu-22.04"
    assert job["env"]["HF_HUB_OFFLINE"] == job["env"]["HF_DATASETS_OFFLINE"] == "1"
    steps = job["steps"]
    boundary = steps[0]["run"]
    assert '"${OUTPUT_TARGET_CHECK_REQUESTED:-false}" == true' in boundary
    assert '"$EXECUTE_REQUESTED" == true || "$INPUT_CHECK_REQUESTED" == true' in boundary
    assert all(guard in boundary for guard in ("GITHUB_RUN_ATTEMPT", "GITHUB_SHA", "PILOT_WORKFLOW_SHA", "workflow_dispatch"))
    metadata = next(step for step in steps if step.get("id") == "output_target")
    intake_step = next(step for step in steps if step.get("id") == "intake")
    assert metadata["if"] == "inputs.output_target_check" and metadata["timeout-minutes"] == 1
    assert metadata["env"] == {"HF_TOKEN": "${{ secrets.HF_TOKEN }}"}
    assert "timeout --signal=TERM --kill-after=5s 30s" in metadata["run"]
    assert "--output-target-check" in metadata["run"] and "codex_budget_pilot_ci.py" in metadata["run"]
    assert all(word not in metadata["run"] for word in ("--execute", "--check-inputs", "--publish", "step8", "intake.py"))
    assert intake_step["if"] == "(inputs.execute || inputs.input_check) && !inputs.output_target_check"
    assert intake_step["timeout-minutes"] == 3 and "kill-after=5s 120s" in intake_step["run"]
    admission = "success() && inputs.execute && !inputs.input_check && !inputs.output_target_check && steps.intake.outputs.verified == 'true'"
    assert len([step for step in steps if step.get("if") == admission]) == 4
    assert all(not {"HF_TOKEN", "GITHUB_TOKEN"}.intersection(step.get("env", {}))
               for step in steps if step not in (intake_step, metadata))
    assert "HF_TOKEN" not in job["env"] and "GITHUB_TOKEN" not in job["env"]
    uploads = [step for step in steps if step.get("uses", "").startswith("actions/upload-artifact@")]
    assert len(uploads) == 1 and uploads[0]["with"]["path"] == "${{ runner.temp }}/budget-pilot-ci-completion.json"
