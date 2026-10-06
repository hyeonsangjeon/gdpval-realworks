"""Immutable synthetic result bytes through real source/schema/HF transport guards."""

from __future__ import annotations

import copy
import gzip
import json
import os
from pathlib import Path
import shlex
import shutil
import socket
import subprocess
import time
from types import SimpleNamespace
from urllib.parse import parse_qs

import httpx
from huggingface_hub import HfApi, constants
import pytest
import yaml

import gpt54_time_budget_result_readout as subject
from core import azure_ai_clients
from core.result_fingerprint import inference_result_fingerprint

ROOT = Path(__file__).resolve().parents[2]
TOKEN = "hf_SYNTHETIC_READOUT_NOT_A_CREDENTIAL"
PRIVATE = "PRIVATE_SYNTHETIC_RESULT_TEXT"
OUTPUT_COMMIT = "d" * 40
_REAL_RUN, _REAL_POPEN = subprocess.run, subprocess.Popen


def _git(root, *arguments, deadline):
    remaining = deadline - time.monotonic()
    assert remaining > 0, "synthetic Git setup exceeded its existing 30-second bound"
    return subprocess.check_output(
        ["git", "-c", "user.name=Synthetic readout fixture", "-c", "user.email=fixture@example.invalid",
         "-C", str(root), *arguments], stderr=subprocess.PIPE, text=True, timeout=min(10, remaining),
        env={"PATH": os.defpath, "LANG": "C.UTF-8", "GIT_CONFIG_NOSYSTEM": "1",
             "GIT_CONFIG_GLOBAL": os.devnull, "GIT_NO_LAZY_FETCH": "1", "GIT_ALLOW_PROTOCOL": ""},
    ).strip()


@pytest.fixture(scope="module")
def source_repository(tmp_path_factory):
    workspace = tmp_path_factory.mktemp("readout-ordinary-bootstrap")
    roles = subject.SOURCE_ROLES | {
        path.relative_to(ROOT).as_posix() for path in (ROOT / "batch-runner/core").rglob("*.py")
    }
    for role in sorted(roles):
        destination = workspace / role
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / role, destination)
    deadline = time.monotonic() + 30
    _git(workspace, "init", "--quiet", deadline=deadline)
    _git(workspace, "add", ".", deadline=deadline)
    _git(workspace, "commit", "--quiet", "-m", "Synthetic retained runtime R", deadline=deadline)
    result_source = {"sha": _git(workspace, "rev-parse", "HEAD", deadline=deadline),
                     "tree": _git(workspace, "rev-parse", "HEAD^{tree}", deadline=deadline)}
    (workspace / "synthetic-controller-only.txt").write_text("C is distinct from retained R.\n")
    _git(workspace, "add", ".", deadline=deadline)
    _git(workspace, "commit", "--quiet", "-m", "Synthetic reviewed readout controller C", deadline=deadline)
    sha, tree = (_git(workspace, "rev-parse", revision, deadline=deadline) for revision in ("HEAD", "HEAD^{tree}"))
    _git(workspace, "switch", "--quiet", "--detach", sha, deadline=deadline)
    return SimpleNamespace(workspace=workspace, sha=sha, tree=tree, result_source=result_source)


@pytest.fixture
def source(source_repository, tmp_path, monkeypatch):
    repository = source_repository
    runner_temp = tmp_path / "runner-temp"
    runner_temp.mkdir()
    root = runner_temp / subject.SOURCE_BASENAME
    _git(repository.workspace, "worktree", "add", "--quiet", "--detach", str(root), repository.sha,
         deadline=time.monotonic() + 30)
    for name in tuple(os.environ):
        if name.startswith(("AZURE_", "FOUNDRY_", "OPENAI_", "HF_", "HUGGING_FACE_", "GITHUB_", "ACTIONS_")):
            monkeypatch.delenv(name)
    environment = {
        "GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": subject.metadata.REPOSITORY, "GITHUB_REF": "refs/heads/main",
        "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_ACTOR": subject.metadata.OWNER,
        "GITHUB_TRIGGERING_ACTOR": subject.metadata.OWNER, "GITHUB_RUN_ATTEMPT": "1", "GITHUB_JOB": subject.JOB,
        "GITHUB_SHA": repository.sha, "READOUT_WORKFLOW_SHA": repository.sha,
        "GITHUB_RUN_ID": "123456789", "GITHUB_RUN_NUMBER": "1",
        "GITHUB_WORKFLOW_REF": subject.metadata.REPOSITORY + "/" + subject.WORKFLOW + "@refs/heads/main",
        "RUNNER_ENVIRONMENT": "github-hosted", "RUNNER_OS": "Linux", "RUNNER_ARCH": "X64", "ImageOS": "ubuntu22",
        "GITHUB_WORKSPACE": str(repository.workspace), "RUNNER_TEMP": str(runner_temp),
        "HF_HUB_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1", "HF_HUB_DISABLE_TELEMETRY": "1", "DO_NOT_TRACK": "1",
        "HF_TOKEN": TOKEN,
    }
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    return SimpleNamespace(**vars(repository), root=root, runner_temp=runner_temp,
                           destination=runner_temp / subject.BASENAME)


@pytest.fixture(autouse=True)
def offline(source, monkeypatch):
    denied, ordinary_sleep = [], time.sleep

    def forbidden(*args, **kwargs):
        denied.append("forbidden_effect")
        raise AssertionError("readout crossed its network/write/model boundary")

    for owner, names in (
        (socket, ("create_connection",)), (socket.socket, ("connect", "connect_ex")),
        (HfApi, ("create_repo", "create_commit", "upload_file", "delete_file", "delete_repo")),
        (azure_ai_clients, ("OpenAI", "AzureOpenAI", "DefaultAzureCredential")),
        (subject.execution.observation, ("run_first_v2_observation",)),
        (subject.execution, ("prepare_and_claim", "execute", "retain")),
        (subprocess, ("Popen", "check_call", "check_output")), (os, ("system",)),
    ):
        for name in names:
            monkeypatch.setattr(owner, name, forbidden)
    import step8_grade
    from core.time_budget_observation_deadline import TimeBudgetObservation

    monkeypatch.setattr(step8_grade.Grader, "__init__", forbidden)
    monkeypatch.setattr(TimeBudgetObservation, "__init__", forbidden)
    monkeypatch.setattr(constants, "HF_HUB_OFFLINE", True)
    # This represents the workflow's pre-import telemetry setting, not a
    # verdict or credential stub. The socket sentinel stays installed.
    monkeypatch.setattr(constants, "HF_HUB_DISABLE_TELEMETRY", True)
    workflow = yaml.safe_load((ROOT / subject.WORKFLOW).read_text())
    bash_guard = workflow["jobs"][subject.JOB]["steps"][0]["run"]

    def local_process(command, **kwargs):
        if command[:2] == ["/usr/bin/git", "--no-replace-objects"]:
            position = command.index("-C")
            assert Path(command[position + 1]) in {source.workspace, source.root}
            assert command[position + 2] in {"rev-parse", "config", "ls-tree", "cat-file"}
            assert kwargs["env"]["GIT_ALLOW_PROTOCOL"] == "" and kwargs["env"]["GIT_NO_LAZY_FETCH"] == "1"
            assert "HF_TOKEN" not in kwargs["env"]
        elif command == ["/bin/bash", "--noprofile", "--norc", "-c", bash_guard]:
            assert "HF_TOKEN" not in kwargs["env"] and kwargs["timeout"] == 5
        else:
            return forbidden()
        with monkeypatch.context() as process:
            process.setattr(subprocess, "Popen", _REAL_POPEN)
            return _REAL_RUN(command, **kwargs)

    def no_online_sleep(seconds):
        if not constants.HF_HUB_OFFLINE:
            forbidden()
        ordinary_sleep(seconds)

    monkeypatch.setattr(subprocess, "run", local_process)
    monkeypatch.setattr(time, "sleep", no_online_sleep)
    yield
    assert denied == []  # A swallowed forbidden effect is still a failure.


def _payload(source, plan, cell, *, available):
    inputs = {"task_id": cell["task_id"], "verification": "synthetic_metadata_not_originals"}
    usage = {"input_tokens": 2913, "output_tokens": 326} if available else None
    availability = {
        "client_construction_attempts": 1, "responses_create_invocations": 1, "completed_responses": 1,
        "response_records": [{"response_returned": True, "usage": None if usage is None else {
            **usage, "cached_input_tokens": None, "reasoning_output_tokens": 100}, "model_binding": "matched"}],
        "usage_complete": available, "reported_token_subtotals": usage,
        "native_model_attempts": None, "repeated_request_count": None, "written_tokens": None,
        "unavailable_counters_are_not_zero": True, "cached_and_reasoning_tokens_are_subsets": True,
        "money_hard_cap": False, "route_fingerprint": "8" * 64,
    }
    control = {
        "policy": "time_budget_observation_deadline_v1",
        "identity": {**cell, "reviewed_source_sha": source.result_source["sha"],
                     "reviewed_source_tree": source.result_source["tree"],
                     "registration_sha256": subject.seal(plan), "input_sha256": subject.seal(inputs)},
        "admitted": True, "first_start_monotonic": 1.0, "terminal_reason": "failed",
        "generation_elapsed_seconds": 2.0, "cleanup_deadline_monotonic": 23.0,
        "cleanup_finished_monotonic": 4.0, "cleanup_elapsed_seconds": 1.0,
        "interruption_attempted": False, "interruption_acknowledged": False,
        "interruption_acknowledgement_scope": "local_runtime_only_not_remote_cancellation",
        "cleanup_complete": True, "cleanup_expired": False,
        "process_ownership": "linux_exclusive_subreaper_pidfd_waitid", "owned_processes_stopped": True,
        "host_reusable": True, "remote_cancellation_confirmed": False, "remote_billing_bound": False,
    }
    filename = "deliverable_files/" + cell["task_id"] + "/PRIVATE_FILENAME.txt"
    row = {
        "task_id": cell["task_id"], "status": "error", "error": "finalize_not_called",
        "content": PRIVATE, "deliverable_text": PRIVATE, "deliverable_files": [filename],
        "deliverable_file_records": [{"path": filename, **subject._identity(b"synthetic deliverable")}],
        "model": "gpt-5.4", "usage": usage,
        "observability": {"runner_success": False, "runner_result_verified": True,
                          "runner_error": "finalize_not_called", "runner_error_sha256": "7" * 64,
                          "v2_audit_sha256": "6" * 64, "usage_availability": availability,
                          "required_deliverable_missing": False},
        "latency_ms": 2000.0, "timestamp": "2026-10-07T00:00:00+00:00", "retried": False, "resume_round": None,
    }
    payload = {
        "experiment_id": cell["run_id"], "condition": "sandbox_v2", "execution_mode": "agentic_sandbox_v2",
        "model": "gpt-5.4", "source": "openai/gdpval", "results": [row], "time_budget_observation": control,
        "observation_execution": {
            "direction_sha256": "1" * 64,
            "host": {"policy": "linux-boot-namespace-user-ci-instance-v1", "instance_sha256": "2" * 64,
                     "ci_instance_sha256": "3" * 64, "ownership_confirmed": False},
            "preparation_identity": subject._identity(b"synthetic preparation"),
            "runtime_source": {"source_sha": source.result_source["sha"], "source_tree": source.result_source["tree"]},
            "frozen_grader": {"source_sha": subject.registration.ACCEPTED_BASE_SHA,
                              "source_tree": subject.registration.ACCEPTED_BASE_TREE,
                              "template_source_sha256": subject.registration.FROZEN_TEMPLATE_SHA256,
                              "template_config_path": subject.registration.GRADER, "materialized_config_path": None,
                              "materialized_grader_source_sha256": None, "execution_source": "frozen_source_only_not_runtime_root"},
            "inputs": inputs, "condition_template": {"path": plan["conditions"]["sandbox_v2"]["template"],
                                                       "sha256": "4" * 64, "size": 1},
            "configuration": subject._identity(b"synthetic configuration"),
            "resolved_instructions": {"synthetic": True}, "entrypoint": subject.execution.observation.ENTRYPOINT,
            "paths_sha256": "5" * 64, "grading_performed": False, "upload_performed": False,
        },
    }
    payload["result_fingerprint"] = inference_result_fingerprint(payload)
    return payload


@pytest.fixture
def case(source):
    plan = subject.registration.load_registration(source.root / subject.registration.REGISTRATION_PATH)
    cell = {"study_id": subject.registration.STUDY_ID, "run_id": "gpt54_time_budget_v1_v2_r1",
            "condition": "sandbox_v2", "repeat": 1, "task_id": plan["shared"]["dataset"]["tasks"][2]["task_id"]}
    payload = _payload(source, plan, cell, available=True)
    completion = {"format": subject.execution.ENVELOPE_VERSION, **cell, "source": source.result_source,
        "ci": {"run_id": "987654321", "run_number": 3, "job": "observation", "attempt": 1},
        "request_sha256": "a" * 64, "host_sha256": "2" * 64, "claim_commit": "c" * 40,
        "output_commit": OUTPUT_COMMIT, "retention": "acknowledged", "result_identity": subject._identity(subject._bytes(payload)),
        "result_fingerprint": payload["result_fingerprint"], "status": "error", "usage": payload["results"][0]["usage"],
        "terminal_reason": "failed", "cleanup_complete": True, "host_reusable": True,
        "grading_performed": False, "retry_allowed": False, "other_cells_executed": 0}
    request = {"format": subject.REQUEST_FORMAT, "purpose": subject.PURPOSE,
        "controller": {"sha": source.sha, "tree": source.tree}, "cell": cell,
        "ci": {"repository": subject.metadata.REPOSITORY, "workflow": subject.WORKFLOW, "ref": "refs/heads/main",
               "actor": subject.metadata.OWNER, "job": subject.JOB, "attempt": 1, "run_number": 1,
               "runner": "ubuntu-22.04", "runner_os": "Linux", "runner_arch": "X64"},
        "registration_sha256": subject.seal(plan), "completion": completion}
    return SimpleNamespace(source=source, plan=plan, cell=cell, request=request, payload=payload)


def _arguments(case):
    raw = subject._bytes(case.request).decode()
    return {"request_json": raw, "expected_request_sha256": subject._identity(raw.encode())["sha256"],
            "reviewed_source_sha": case.source.sha, "reviewed_source_tree": case.source.tree, "runtime_root": case.source.root}


def _invoke(case, operation="read", **changes):
    arguments = {**_arguments(case), **changes}
    return subject.main([operation, *(part for name, value in arguments.items() for part in (
        "--" + name.replace("_", "-"), str(value)))])


def _context(case):
    return {"request": case.request, "request_sha256": _arguments(case)["expected_request_sha256"], "plan": case.plan,
            "ci": {"run_id": "123456789", "run_number": 1, "job": subject.JOB, "attempt": 1}}


@pytest.fixture
def transport(case, monkeypatch):
    state = SimpleNamespace(calls=[], head={"id": subject.metadata.TARGET, "private": True, "sha": OUTPUT_COMMIT},
                            data=subject._bytes(case.payload), failure=None, hook=None, formatted=[], gzip_at=None)

    class SecretTimeout(httpx.ReadTimeout):
        def __str__(self):
            state.formatted.append(True)
            raise AssertionError("secret transport exception must never be formatted")

    class Transport(httpx.BaseTransport):
        def __init__(self, **kwargs):
            assert kwargs == {"retries": 0, "trust_env": False}

        def handle_request(self, request):
            state.calls.append(request)
            assert "HF_TOKEN" not in os.environ and request.headers["authorization"] == "Bearer " + TOKEN
            assert len(state.calls) <= 2 and request.method == "GET"
            number = len(state.calls)
            if state.hook:
                state.hook(number)
            if state.failure == "timeout" and number == 2:
                raise SecretTimeout(PRIVATE + TOKEN, request=request)
            status = 403 if state.failure == "denied" else 200
            data = PRIVATE.encode() if status != 200 else subject._bytes(state.head) if number == 1 else state.data
            headers = {"content-type": "application/json"}
            if number == state.gzip_at:
                headers["content-encoding"] = "gzip"
                data = gzip.compress(data, mtime=0)
            return httpx.Response(status, headers=headers,
                                  stream=httpx.ByteStream(data), request=request)

    monkeypatch.setattr(httpx, "HTTPTransport", Transport)
    yield state
    assert state.formatted == []


@pytest.mark.parametrize("gzip_at", [None, 1, 2], ids=["uncompressed", "gzip_metadata", "gzip_result"])
def test_time_budget_result_readout_identity_encoding(case, transport, capsys, gzip_at):
    transport.gzip_at = gzip_at
    assert _invoke(case) == (0 if gzip_at is None else 2)
    assert len(transport.calls) == (1 if gzip_at == 1 else 2)
    assert all(request.method == "GET" and request.headers["accept-encoding"] == "identity"
               for request in transport.calls)
    assert subject.SECONDS == 60
    assert all(0 < request.extensions["timeout"]["read"] <= 30 for request in transport.calls)
    value = json.loads(case.source.destination.read_bytes())
    subject.validate_envelope(value, _context(case))
    assert value["verified_private"] is (None if gzip_at == 1 else True)
    assert value["outcome"] == ("read" if gzip_at is None else "refused")
    assert value["retry_allowed"] is False and value["grading_performed"] is False
    if gzip_at is None:
        assert value["summary"]["status"] == "error"
        assert value["summary"]["usage"] == case.request["completion"]["usage"]
        assert value["result_identity"] == case.request["completion"]["result_identity"]
    else:
        assert value["summary"] is None
    output = capsys.readouterr()
    assert output.err == "" and json.loads(output.out) == value
    public = case.source.destination.read_text() + output.out + output.err
    assert all(secret not in public for secret in (
        TOKEN, PRIVATE, "PRIVATE_FILENAME", "deliverable_text", subject.metadata.TARGET))


@pytest.mark.parametrize("available", [True, False], ids=["reported", "unavailable"])
def test_time_budget_result_readout_roundtrip(case, transport, capsys, available):
    if not available:
        case.payload = _payload(case.source, case.plan, case.cell, available=False)
        transport.data = subject._bytes(case.payload)
        case.request["completion"].update(result_identity=subject._identity(transport.data),
            result_fingerprint=case.payload["result_fingerprint"], usage=None)
    assert _invoke(case, "validate-request") == 0 and transport.calls == []
    assert _invoke(case) == 0
    value = json.loads(case.source.destination.read_bytes())
    subject.validate_envelope(value, _context(case))
    assert value["controller"] != value["result_source"]
    assert value["summary"] == {
        "status": "error", "error": "finalize_not_called", "runner_success": False,
        "runner_result_verified": True, "runner_error": "finalize_not_called", "required_deliverable_missing": False,
        "control": {"policy": "time_budget_observation_deadline_v1", "admitted": True, "terminal_reason": "failed",
            "interruption_attempted": False, "interruption_acknowledged": False,
            "interruption_acknowledgement_scope": "local_runtime_only_not_remote_cancellation", "cleanup_complete": True,
            "cleanup_expired": False, "process_ownership": "linux_exclusive_subreaper_pidfd_waitid",
            "owned_processes_stopped": True, "host_reusable": True, "remote_cancellation_confirmed": False,
            "remote_billing_bound": False},
        "usage": {"input_tokens": 2913, "output_tokens": 326} if available else None,
        "usage_availability": copy.deepcopy(case.payload["results"][0]["observability"]["usage_availability"]),
        "deliverables": {"count": 1, "bytes": len(b"synthetic deliverable")},
    }
    assert set(value) == {"format", "controller", "ci", "request_sha256", "target_identity_sha256", "cell",
        "result_source", "execution_request_sha256", "output_commit", "result_identity", "result_fingerprint",
        "retry_allowed", "grading_performed", "timestamp_utc", "verified_private", "outcome", "summary"}
    assert value["verified_private"] is True and value["outcome"] == "read"
    assert value["retry_allowed"] is False and value["grading_performed"] is False
    assert _invoke(case, "verify-envelope") == 0
    original = case.source.destination.read_bytes()
    assert _invoke(case) == 2 and case.source.destination.read_bytes() == original
    assert len(transport.calls) == 2
    first, second = transport.calls
    assert first.url.path == f"/api/datasets/{subject.metadata.TARGET}/revision/{OUTPUT_COMMIT}"
    assert parse_qs(first.url.query.decode()) == {"expand": ["private", "sha"]}
    assert second.url.path == (f"/datasets/{subject.metadata.TARGET}/raw/{OUTPUT_COMMIT}/time-budget/"
        "gpt54_sandboxv2_codex_time_budget_v1/gpt54_time_budget_v1_v2_r1/"
        "2ea2e5b5-257f-42e6-a7dc-93763f28b19d/result/step2_inference_results.json")
    assert not second.url.query
    assert all(0 < request.extensions["timeout"]["read"] <= 30 for request in transport.calls)
    public = original.decode() + capsys.readouterr().out
    assert all(secret not in public for secret in (TOKEN, PRIVATE, "PRIVATE_FILENAME", "deliverable_text", "source_repo_id"))
    assert set(case.source.runner_temp.iterdir()) == {case.source.root, case.source.destination}
    assert case.source.destination.stat().st_mode & 0o777 == 0o600
    for mutation in ({"raw_exception": TOKEN}, {"outcome": "refused"}, {"verified_private": 1}):
        with pytest.raises(ValueError):
            subject.validate_envelope({**value, **mutation}, _context(case))
    bad = copy.deepcopy(value)
    bad["summary"]["usage_availability"]["response_records"][0]["served_model"] = PRIVATE
    with pytest.raises(ValueError):
        subject.validate_envelope(bad, _context(case))


@pytest.mark.parametrize("failure", ["request_digest", "actor", "source", "task", "attempt"])
def test_time_budget_result_readout_refuses_before_credentials(case, transport, monkeypatch, failure):
    changes = {}
    if failure == "request_digest":
        changes["expected_request_sha256"] = "0" * 64
    elif failure == "task":
        case.request["cell"]["task_id"] = "unregistered"
    else:
        name, value = {"actor": ("GITHUB_ACTOR", "other"), "source": ("READOUT_WORKFLOW_SHA", "0" * 40),
                       "attempt": ("GITHUB_RUN_ATTEMPT", "2")}[failure]
        monkeypatch.setenv(name, value)
    assert _invoke(case, **changes) == 2
    assert transport.calls == [] and not case.source.destination.exists()


@pytest.mark.parametrize("failure", ["bytes", "canonical", "fingerprint", "result_source", "result_task", "private_field"])
def test_time_budget_result_readout_refuses_untrusted_result(case, transport, capsys, failure):
    if failure == "bytes":
        transport.data += b" "
    elif failure == "canonical":
        transport.data += b"\n"
        case.request["completion"]["result_identity"] = subject._identity(transport.data)
    else:
        if failure == "result_source":
            case.payload["observation_execution"]["runtime_source"]["source_sha"] = "0" * 40
        elif failure == "result_task":
            task1 = case.plan["shared"]["dataset"]["tasks"][0]["task_id"]
            row = case.payload["results"][0]
            row["task_id"] = task1
            row["deliverable_files"] = []
            row["deliverable_file_records"] = []
        elif failure == "private_field":
            case.payload["results"][0]["observability"]["provider_message"] = PRIVATE + TOKEN
        case.payload["result_fingerprint"] = "0" * 64 if failure == "fingerprint" else inference_result_fingerprint(case.payload)
        transport.data = subject._bytes(case.payload)
        # Independently expected bytes now authenticate the malformed fixture;
        # real binding/schema validators, not the outer byte check, must refuse.
        case.request["completion"].update(result_identity=subject._identity(transport.data),
                                          result_fingerprint=case.payload["result_fingerprint"])
    assert _invoke(case) == 2
    value = json.loads(case.source.destination.read_bytes())
    assert value["outcome"] == "refused" and value["summary"] is None and value["verified_private"] is True
    assert len(transport.calls) == 2
    public = case.source.destination.read_text() + capsys.readouterr().out
    assert TOKEN not in public and PRIVATE not in public


@pytest.mark.parametrize("failure", ["missing_token", "nonprivate", "wrong_target", "denied", "timeout"])
def test_time_budget_result_readout_transport_refusal(case, transport, monkeypatch, capsys, failure):
    if failure == "missing_token":
        monkeypatch.delenv("HF_TOKEN")
    elif failure == "nonprivate":
        transport.head["private"] = False
    elif failure == "wrong_target":
        transport.head["id"] = "other/private"
    else:
        transport.failure = failure
    assert _invoke(case) == 2
    value = json.loads(case.source.destination.read_bytes())
    subject.validate_envelope(value, _context(case))
    assert value["outcome"] == "refused" and value["summary"] is None and value["retry_allowed"] is False
    assert len(transport.calls) == (0 if failure == "missing_token" else 2 if failure == "timeout" else 1)
    assert value["verified_private"] is (True if failure == "timeout" else None)
    assert TOKEN not in capsys.readouterr().out and PRIVATE not in case.source.destination.read_text()


def test_time_budget_result_readout_cumulative_bound(case, transport, monkeypatch):
    now = [time.monotonic()]
    monkeypatch.setattr(time, "monotonic", lambda: now[0])
    transport.hook = lambda number: now.__setitem__(0, now[0] + 35)
    assert _invoke(case) == 2
    assert subject.SECONDS == 60 and len(transport.calls) == 2
    assert transport.calls[1].extensions["timeout"]["read"] == 25
    assert json.loads(case.source.destination.read_bytes())["summary"] is None


def test_time_budget_result_readout_final_source_reread(case, transport):
    path = case.source.root / subject.WORKFLOW
    original = path.read_bytes()

    def changed(number):
        if number == 2:
            path.write_bytes(original + b"\n# Unreviewed source change\n")

    transport.hook = changed
    try:
        assert _invoke(case) == 2
        assert len(transport.calls) == 2 and not case.source.destination.exists()
    finally:
        path.write_bytes(original)


def test_time_budget_result_readout_workflow_binding(case, monkeypatch):
    workflow = yaml.safe_load((ROOT / subject.WORKFLOW).read_text())
    trigger = workflow.get("on", workflow.get(True))
    assert set(trigger) == {"workflow_dispatch"}
    assert set(trigger["workflow_dispatch"]["inputs"]) == {
        "reviewed_source_sha", "reviewed_source_tree", "request_json", "request_sha256"}
    assert workflow["permissions"] == {"contents": "read"} and set(workflow["jobs"]) == {"readout"}
    job = workflow["jobs"]["readout"]
    assert job["runs-on"] == "ubuntu-22.04" and job["timeout-minutes"] == 10
    assert "permissions" not in job and "HF_TOKEN" not in job["env"]
    assert job["env"]["HF_HUB_DISABLE_TELEMETRY"] == job["env"]["DO_NOT_TRACK"] == "1"
    steps = job["steps"]
    secrets = [step for step in steps if "secrets." in json.dumps(step)]
    assert len(secrets) == 1 and secrets[0]["id"] == "readout"
    assert secrets[0]["env"] == {"HF_TOKEN": "${{ secrets.HF_TOKEN }}"}
    assert "timeout --signal=TERM --kill-after=5s 60s" in secrets[0]["run"]
    checkout = next(step for step in steps if step.get("uses", "").startswith("actions/checkout@"))
    assert checkout["with"] == {"ref": "${{ inputs.reviewed_source_sha }}", "fetch-depth": 1, "persist-credentials": False}
    linked = next(step for step in steps if "git worktree add --detach" in step.get("run", ""))
    assert '[[ ! -e "$RUNNER_TEMP/time-budget-readout-source" && ! -L "$RUNNER_TEMP/time-budget-readout-source" ]]' in linked["run"]
    assert (case.source.workspace / ".git").is_dir() and (case.source.root / ".git").is_file()
    source_step = next(step for step in steps if step.get("id") == "source")
    assert steps.index(linked) < steps.index(source_step) < steps.index(secrets[0])
    arguments = _arguments(case)
    for name, value in {"REVIEWED_SOURCE_SHA": case.source.sha, "REVIEWED_SOURCE_TREE": case.source.tree,
                        "READOUT_REQUEST_JSON": arguments["request_json"],
                        "READOUT_REQUEST_SHA256": arguments["expected_request_sha256"]}.items():
        monkeypatch.setenv(name, value)
    block = source_step["run"]
    command = block[block.index("python3 "):block.index("\necho ")].replace("\\\n", "")
    argv = [os.path.expandvars(part) for part in shlex.split(command)]
    assert argv == ["python3", str(case.source.root / subject.HELPER), "validate-request",
        "--request-json", arguments["request_json"], "--expected-request-sha256", arguments["expected_request_sha256"],
        "--reviewed-source-sha", case.source.sha, "--reviewed-source-tree", case.source.tree,
        "--runtime-root", str(case.source.root)]
    assert subject.main(argv[2:]) == 0
    guard_environment = {name: value for name, value in os.environ.items() if name != "HF_TOKEN"}
    guard_command = ["/bin/bash", "--noprofile", "--norc", "-c", steps[0]["run"]]
    assert subprocess.run(guard_command, env=guard_environment, capture_output=True, timeout=5).returncode == 0
    assert subprocess.run(guard_command, env={**guard_environment, "GITHUB_RUN_ATTEMPT": "2"},
                          capture_output=True, timeout=5).returncode != 0
    assert "verify-envelope" in next(step for step in steps if step.get("id") == "envelope")["run"]
    assert steps[-1]["with"]["path"] == "${{ runner.temp }}/" + subject.BASENAME
    assert steps[-1]["with"]["retention-days"] == 7 and steps[-1]["with"]["if-no-files-found"] == "error"
    assert not any(word in json.dumps(workflow) for word in ("id-token", "azure/login", "step2_run_inference", "step8_grade"))
