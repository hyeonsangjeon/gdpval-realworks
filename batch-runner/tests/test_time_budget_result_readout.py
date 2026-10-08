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
def source_repository(tmp_path_factory, request):
    workspace = tmp_path_factory.mktemp("readout-ordinary-bootstrap")
    roles = subject.SOURCE_ROLES | {subject.registration.CODEX_TEMPLATE} | {
        path.relative_to(ROOT).as_posix() for path in (ROOT / "batch-runner/core").rglob("*.py")
    }
    for role in sorted(roles):
        destination = workspace / role
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / role, destination)
    registration_path = workspace / subject.registration.REGISTRATION_PATH
    compiler_path = workspace / "batch-runner/gpt54_time_budget_comparison.py"
    current_registration, current_compiler = registration_path.read_bytes(), compiler_path.read_bytes()
    result_plan = subject.registration.load_registration(registration_path)
    if getattr(request, "param", None) == "historical_runtime":
        # R differs from C only in its legitimate runtime/compiler bindings.
        # This historical compiler blob is never imported or executed.
        compiler_path.write_bytes(current_compiler + b"\n# Synthetic historical runtime binding.\n")
        historical_hash = subject._identity(compiler_path.read_bytes())["sha256"]
        result_plan["source_basis"]["registration_compiler"]["sha256"] = historical_hash
        result_plan["source_pins"]["batch-runner/gpt54_time_budget_comparison.py"] = historical_hash
        registration_path.write_text(yaml.safe_dump(result_plan, sort_keys=False))
    deadline = time.monotonic() + 30
    _git(workspace, "init", "--quiet", deadline=deadline)
    _git(workspace, "add", ".", deadline=deadline)
    _git(workspace, "commit", "--quiet", "-m", "Synthetic retained runtime R", deadline=deadline)
    result_source = {"sha": _git(workspace, "rev-parse", "HEAD", deadline=deadline),
                     "tree": _git(workspace, "rev-parse", "HEAD^{tree}", deadline=deadline)}
    registration_path.write_bytes(current_registration)
    compiler_path.write_bytes(current_compiler)
    (workspace / "synthetic-controller-only.txt").write_text("C is distinct from retained R.\n")
    _git(workspace, "add", ".", deadline=deadline)
    _git(workspace, "commit", "--quiet", "-m", "Synthetic reviewed readout controller C", deadline=deadline)
    sha, tree = (_git(workspace, "rev-parse", revision, deadline=deadline) for revision in ("HEAD", "HEAD^{tree}"))
    _git(workspace, "switch", "--quiet", "--detach", sha, deadline=deadline)
    return SimpleNamespace(workspace=workspace, sha=sha, tree=tree,
                           result_source=result_source, result_plan=result_plan)


@pytest.fixture
def source(source_repository, tmp_path, monkeypatch):
    repository = source_repository
    runner_temp = tmp_path / "runner-temp"
    runner_temp.mkdir()
    root = runner_temp / subject.SOURCE_BASENAME
    deadline = time.monotonic() + 30
    # Only the fixture's ordinary temporary repo; retain existing failed worktrees.
    assert repository.workspace.resolve().parent == tmp_path.parent.resolve()
    assert (repository.workspace / ".git").is_dir() and not (repository.workspace / ".git").is_symlink()
    _git(repository.workspace, "worktree", "prune", "--expire", "now", deadline=deadline)
    _git(repository.workspace, "worktree", "add", "--quiet", "--detach", str(root), repository.sha,
         deadline=deadline)
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
        (subject.native_execution.observation, ("run_codex_observation",)),
        (subject.native_execution, ("prepare_and_claim", "execute", "retain")),
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
    plan = copy.deepcopy(source.result_plan)
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


@pytest.mark.parametrize("source_repository", ["historical_runtime"], indirect=True)
@pytest.mark.parametrize("failure", [None, "tree", "registration", "missing_R"],
                         ids=["historical_R_new_C", "wrong_R_tree", "wrong_registration", "missing_R"])
def test_time_budget_result_readout_historical_registration(case, transport, monkeypatch, capsys, failure):
    current = subject.registration.load_registration(case.source.root / subject.registration.REGISTRATION_PATH)
    expected = copy.deepcopy(case.plan)
    compiler = "batch-runner/gpt54_time_budget_comparison.py"
    current_hash = current["source_basis"]["registration_compiler"]["sha256"]
    expected["source_basis"]["registration_compiler"]["sha256"] = current_hash
    expected["source_pins"][compiler] = current_hash
    assert expected == current and subject.seal(case.plan) != subject.seal(current)
    assert current_hash == subject._identity((case.source.root / compiler).read_bytes())["sha256"]
    assert case.request["registration_sha256"] == subject.seal(case.plan)
    assert case.payload["time_budget_observation"]["identity"]["registration_sha256"] == subject.seal(case.plan)
    if failure == "tree":
        case.request["completion"]["source"] = {**case.source.result_source, "tree": "0" * 40}
    elif failure == "registration":
        case.request["registration_sha256"] = subject.seal(current)
    elif failure == "missing_R":
        case.request["completion"]["source"] = {**case.source.result_source, "sha": "0" * 40}
    credential_steps = []
    if failure is not None:
        def forbidden(*args, **kwargs):
            credential_steps.append(True)
            raise AssertionError("invalid historical R reached the credentialed read step")
        monkeypatch.setattr(subject, "_read_result", forbidden)
    assert _invoke(case) == (0 if failure is None else 2)
    assert credential_steps == []
    output = capsys.readouterr()
    assert output.err == "" and TOKEN not in output.out and PRIVATE not in output.out
    if failure is not None:
        assert output.out == "result_readout_refused\n"
        assert transport.calls == [] and not case.source.destination.exists()
        return
    assert len(transport.calls) == 2 and subject.SECONDS == 60
    assert all(request.method == "GET" and request.headers["accept-encoding"] == "identity"
               and 0 < request.extensions["timeout"]["read"] <= 30 for request in transport.calls)
    value = json.loads(case.source.destination.read_bytes())
    subject.validate_envelope(value, _context(case))
    assert json.loads(output.out) == value and value["outcome"] == "read"
    assert value["controller"] == {"sha": case.source.sha, "tree": case.source.tree}
    assert value["result_source"] == case.source.result_source != value["controller"]
    assert value["result_identity"] == case.request["completion"]["result_identity"]
    assert value["result_fingerprint"] == case.payload["result_fingerprint"]
    assert value["summary"]["status"] == "error" and value["summary"]["runner_error"] == "finalize_not_called"
    assert value["summary"]["usage"] == case.request["completion"]["usage"]
    assert value["retry_allowed"] is False and value["grading_performed"] is False
    assert all(secret not in output.out for secret in ("PRIVATE_FILENAME", "deliverable_text", subject.metadata.TARGET))


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


def _native_capture_payload(case, *, success):
    """Real capture of synthetic returned data; no native run/admission occurs."""
    native = subject.native_execution.observation
    basis = _payload(case.source, case.plan, case.cell, available=False)
    captured, control = basis["observation_execution"], basis["time_budget_observation"]
    inputs = {**captured["inputs"], "needs_files": True,
              "step0_manifest": subject._identity(b"synthetic unread Step0 declaration")}
    control["identity"]["input_sha256"] = subject.seal(inputs)
    control["terminal_reason"] = "completed" if success else "failed"
    preparation = captured["preparation_identity"]
    template = case.plan["conditions"]["codex"]["template"]
    marker = {"observation": control["identity"], "inputs": inputs,
              "runtime_source": captured["runtime_source"], "frozen_grader": captured["frozen_grader"],
              "condition_template": {"path": template, **subject._identity((case.source.root / template).read_bytes())},
              "files": {subject.registration.HANDOFF_CONFIG: captured["configuration"]}}
    direction = SimpleNamespace(expected=captured["direction_sha256"], host=captured["host"],
        paths={"synthetic_unread_path": PRIVATE}, binding=SimpleNamespace(
            preparation_sha256=preparation["sha256"], preparation_size=preparation["size"]))
    raw = {"success": success, "text": PRIVATE, "error": None if success else PRIVATE + TOKEN,
           "files": [{"filename": "PRIVATE_FILENAME.txt", "content": b"synthetic deliverable"}] if success else [],
           "time_budget_observation": control, "handoff_preparation_identity": preparation,
           "codex_diagnostics": {"items_seen": 2, "http_status_code": None, "rate_limit_kind": None}}
    payload, files = native._capture(raw, marker, direction, provider_binding={
        "settings_sha256": "4" * 64, "config_overrides_sha256": "5" * 64,
        "sdk_version": native.PINNED_CODEX_SDK_VERSION, "cli_version": native.PINNED_CODEX_CLI_VERSION})
    assert payload["condition"] == "codex" and payload["execution_mode"] == "codex_foundry"
    assert payload["results"][0]["usage"] is None
    assert len(files) == (1 if success else 0)
    return payload


@pytest.mark.parametrize("scenario", [
    "native_success", "native_error", "cell", "R", "digest", "fingerprint", "mode",
    "unsafe_field", "unsafe_error", "unsafe_diagnostics", "counter", "wrong_R_tree",
    "registration", "r2", "unregistered_task", "cumulative_bound", "gzip_metadata", "gzip_result",
    "canonical_v2", "fixed_uncertainty",
])
def test_time_budget_native_canonical_readout(case, transport, monkeypatch, capsys, scenario):
    """One selected native result object, never claim/inputs/files or a runtime."""
    native = subject.native_execution
    compatible = scenario in {"canonical_v2", "fixed_uncertainty"}
    if not compatible:
        case.cell = {**native.CELL, "task_id": case.plan["shared"]["dataset"]["tasks"][2]["task_id"]}
        assert case.cell["task_id"] == "2ea2e5b5-257f-42e6-a7dc-93763f28b19d"
        case.request.update(format=subject.NATIVE_REQUEST_FORMAT, purpose=subject.NATIVE_PURPOSE, cell=case.cell)
        case.payload = _native_capture_payload(case, success=scenario not in {"native_error", "unsafe_error"})
        row = case.payload["results"][0]
        case.request["completion"].update(**case.cell, format=native.ENVELOPE_VERSION, usage=None,
            status=row["status"], terminal_reason=case.payload["time_budget_observation"]["terminal_reason"])
        if scenario == "cell":
            case.payload["time_budget_observation"]["identity"]["task_id"] = case.plan["shared"]["dataset"]["tasks"][1]["task_id"]
        elif scenario == "R":
            case.payload["observation_execution"]["runtime_source"]["source_sha"] = "0" * 40
        elif scenario == "mode":
            case.payload["execution_mode"] = "codex"  # Not a native producer alias.
        elif scenario == "unsafe_field":
            row["observability"]["runner_error"] = PRIVATE + TOKEN
        elif scenario == "unsafe_error":
            row["error"] = PRIVATE + TOKEN
        elif scenario == "unsafe_diagnostics":
            row["observability"]["codex_diagnostics"]["rate_limit_kind"] = PRIVATE
        elif scenario == "counter":
            row["observability"]["native_measurements"]["model_attempt_count"] = 0
        # Coherent negative byte identities expose the semantic checks, not
        # merely the outer hash guard. Positive capture bytes stay untouched.
        if scenario in {"cell", "R", "mode", "unsafe_field", "unsafe_error", "unsafe_diagnostics", "counter"}:
            case.payload["result_fingerprint"] = inference_result_fingerprint(case.payload)
        elif scenario == "fingerprint":
            case.payload["result_fingerprint"] = "0" * 64
        transport.data = subject._bytes(case.payload)
        case.request["completion"].update(result_identity=subject._identity(transport.data),
                                         result_fingerprint=case.payload["result_fingerprint"])
        if scenario == "digest":
            transport.data += b" "
        elif scenario == "wrong_R_tree":
            case.request["completion"]["source"] = {**case.source.result_source, "tree": "0" * 40}
        elif scenario == "registration":
            case.request["registration_sha256"] = "0" * 64
        elif scenario in {"r2", "unregistered_task"}:
            selection = ({"run_id": "gpt54_time_budget_v1_codex_r2", "repeat": 2} if scenario == "r2"
                         else {"task_id": "00000000-0000-4000-8000-000000000000"})
            case.cell.update(selection)
            case.request["completion"].update(selection)
        elif scenario == "cumulative_bound":
            now = [time.monotonic()]
            monkeypatch.setattr(time, "monotonic", lambda: now[0])
            transport.hook = lambda number: now.__setitem__(0, now[0] + 35)
        elif scenario in {"gzip_metadata", "gzip_result"}:
            transport.gzip_at = 1 if scenario == "gzip_metadata" else 2
    elif scenario == "fixed_uncertainty":
        case.cell = dict(native.CELL)
        request_identity = subject._identity(b"synthetic unread execution request")
        case.request.update(format=subject.UNCERTAINTY_REQUEST_FORMAT, purpose=subject.UNCERTAINTY_PURPOSE,
                            cell=case.cell, execution_request_identity=request_identity)
        case.request["completion"].update(**case.cell, format=native.ENVELOPE_VERSION,
            request_sha256=request_identity["sha256"], status="uncertain", result_identity=None,
            result_fingerprint=None, terminal_reason=None, usage=None, cleanup_complete=None, host_reusable=None)
        manifest = {"format": subject.UNCERTAINTY_MANIFEST_FORMAT,
            "observation": subject.asdict(subject.ObservationIdentity(**case.cell,
                reviewed_source_sha=case.source.result_source["sha"], reviewed_source_tree=case.source.result_source["tree"],
                registration_sha256=subject.seal(case.plan), input_sha256="1" * 64)),
            "request_identity": request_identity, "claim_commit": case.request["completion"]["claim_commit"],
            "claim_identity": subject._identity(b"synthetic unread claim"),
            "execution_receipt": subject.execution._execution_failure("observation_callable", ValueError(PRIVATE + TOKEN)),
            "result": "unavailable_no_fabricated_study_row", "files": {}, "grading_performed": False}
        transport.data = native._encoded(manifest)

    before_credentials = scenario in {"wrong_R_tree", "registration", "r2", "unregistered_task"}
    success = scenario in {"native_success", "native_error", "canonical_v2", "fixed_uncertainty"}
    assert _invoke(case) == (0 if success else 2)
    output = capsys.readouterr()
    assert output.err == "" and all(secret not in output.out for secret in (PRIVATE, TOKEN, "PRIVATE_FILENAME"))
    if before_credentials:
        assert transport.calls == [] and not case.source.destination.exists()
        assert output.out == "result_readout_refused\n"
        return
    assert subject.SECONDS == 60 and len(transport.calls) == (1 if scenario == "gzip_metadata" else 2)
    first = transport.calls[0]
    assert first.url.path == f"/api/datasets/{subject.metadata.TARGET}/revision/{OUTPUT_COMMIT}"
    assert parse_qs(first.url.query.decode()) == {"expand": ["private", "sha"]}
    if len(transport.calls) == 2:
        second = transport.calls[1]
        member = (native.MANIFEST if scenario == "fixed_uncertainty" else
                  subject.execution._namespace(case.cell)[0] + "/result/" + native.observation.RESULT)
        assert second.url.path == f"/datasets/{subject.metadata.TARGET}/raw/{OUTPUT_COMMIT}/{member}"
        assert not second.url.query
        if scenario == "cumulative_bound":
            assert second.extensions["timeout"]["read"] == 25
    assert all(call.method == "GET" and call.headers["accept-encoding"] == "identity"
               and 0 < call.extensions["timeout"]["read"] <= 30 for call in transport.calls)
    value = json.loads(case.source.destination.read_bytes())
    subject.validate_envelope(value, _context(case))
    assert json.loads(output.out) == value and value["outcome"] == ("read" if success else "refused")
    assert value["verified_private"] is (None if scenario == "gzip_metadata" else True)
    assert value["retry_allowed"] is value["grading_performed"] is False
    if scenario in {"native_success", "native_error"}:
        row, control = case.payload["results"][0], case.payload["time_budget_observation"]
        assert value["format"] == subject.NATIVE_FORMAT
        assert value["result_source"] == case.source.result_source != value["controller"]
        assert value["registration_sha256"] == subject.seal(case.plan)
        assert value["claim_commit"] == case.request["completion"]["claim_commit"]
        assert value["result_identity"] == subject._identity(transport.data) == case.request["completion"]["result_identity"]
        assert value["result_fingerprint"] == case.payload["result_fingerprint"]
        assert value["summary"] == {
            "status": row["status"], "error": None if scenario == "native_success" else "time_budget_observation_non_success",
            "runner_success": scenario == "native_success", "required_deliverable_missing": scenario == "native_error",
            "control": {name: control[name] for name in subject.CONTROL_FLAGS | set(subject.CONTROL_STATIC) | {"terminal_reason"}},
            "usage": None, "served_model_identity": None,
            "usage_availability": {"usage_complete": False, "reason": "consumer_does_not_export_native_usage"},
            "native_measurements": {name: None for name in (
                "model_attempt_count", "repeated_request_count", "input_tokens", "output_tokens", "written_tokens", "native_retries", "cost_usd")},
            "codex_diagnostics": {"items_seen": 2, "http_status_code": None, "rate_limit_kind": None},
            "deliverables": {"declared_count": 1 if scenario == "native_success" else 0,
                "declared_bytes": len(b"synthetic deliverable") if scenario == "native_success" else 0,
                "basis": "declared_from_verified_result_metadata", "contents_fetched": False, "contents_verified": False},
        }
        for extra in ({"runner_error": PRIVATE}, {"served_model_identity": PRIVATE}):
            with pytest.raises(ValueError):
                subject.validate_envelope({**value, "summary": {**value["summary"], **extra}}, _context(case))
    elif scenario == "canonical_v2":
        assert value["format"] == subject.FORMAT and value["summary"]["runner_result_verified"] is True
        assert value["summary"]["runner_error"] == "finalize_not_called"
        assert "native_measurements" not in value["summary"]
    elif scenario == "fixed_uncertainty":
        assert value["format"] == subject.UNCERTAINTY_FORMAT and value["cell"] == native.CELL
        assert value["result_identity"] is value["result_fingerprint"] is None
        assert value["summary"] == {**subject.UNCERTAINTY_SUMMARY,
            "failure": {"stage": "observation_callable", "category": "validation_refused", "reason": "execution_refused_or_uncertain"},
            "observed_manifest_identity": subject._identity(transport.data)}
    else:
        assert value["summary"] is None
    if success:
        monkeypatch.delenv("HF_TOKEN")
        assert _invoke(case, "verify-envelope") == 0 and len(transport.calls) == 2
    public = case.source.destination.read_text() + output.out + output.err + capsys.readouterr().out
    assert all(secret not in public for secret in (TOKEN, PRIVATE, "PRIVATE_FILENAME", "deliverable_text",
        "runner_error_sha256", "provider_binding", "execution_receipt", "source_repo_id", subject.metadata.TARGET))
    assert set(case.source.runner_temp.iterdir()) == {case.source.root, case.source.destination}
    assert case.source.destination.stat().st_mode & 0o777 == 0o600


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
    now = [1000.0]
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
    assert checkout["with"] == {"ref": "${{ inputs.reviewed_source_sha }}", "fetch-depth": 0, "persist-credentials": False}
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


@pytest.mark.parametrize("scenario", [
    "native_uncertain", "manifest_source", "manifest_cell", "manifest_registration",
    "manifest_request_hash", "manifest_request_size", "manifest_claim", "refused_receipt",
    "missing_receipt", "missing_failure", "extra_private_field", "extra_failure_field",
    "wrong_R_tree", "wrong_execution_request", "manifest_encoding", "cumulative_bound", "canonical_v2",
])
def test_time_budget_native_uncertainty_readout(case, transport, monkeypatch, capsys, scenario):
    """One immutable manifest, no invented expected manifest hash or native run."""
    formatted, expected_error = [], None
    native = subject.native_execution
    if scenario != "canonical_v2":
        class PrivateConstructionError(TypeError):
            def __str__(self):
                formatted.append(True)
                raise AssertionError("private exception must not be formatted")

        case.cell = dict(native.CELL)
        original_request = subject._bytes({"format": native.REQUEST_VERSION, "cell": case.cell,
                                          "source": case.source.result_source, "synthetic_unissued": True})
        request_identity = subject._identity(original_request)
        case.request.update(format=subject.UNCERTAINTY_REQUEST_FORMAT, purpose=subject.UNCERTAINTY_PURPOSE,
                            cell=case.cell, execution_request_identity=request_identity)
        case.request["completion"].update(**case.cell, format=native.ENVELOPE_VERSION,
            request_sha256=request_identity["sha256"], status="uncertain", result_identity=None,
            result_fingerprint=None, terminal_reason=None, usage=None, cleanup_complete=None, host_reusable=None)
        observation = subject.asdict(subject.ObservationIdentity(**case.cell,
            reviewed_source_sha=case.source.result_source["sha"], reviewed_source_tree=case.source.result_source["tree"],
            registration_sha256=subject.seal(case.plan), input_sha256=subject.seal({"synthetic_unread_input": True})))
        manifest = {"format": subject.UNCERTAINTY_MANIFEST_FORMAT, "observation": observation,
            "request_identity": dict(request_identity), "claim_commit": case.request["completion"]["claim_commit"],
            "claim_identity": subject._identity(b"synthetic unread permanent claim"),
            "execution_receipt": subject.execution._execution_failure(
                "observation_callable", PrivateConstructionError(PRIVATE + TOKEN)),
            "result": "unavailable_no_fabricated_study_row", "files": {}, "grading_performed": False}
        assert manifest["execution_receipt"]["failure"] == {
            "stage": "observation_callable", "category": "type_error", "reason": "execution_refused_or_uncertain"}
        native.validate_envelope(case.request["completion"])
        if scenario == "manifest_source":
            manifest["observation"]["reviewed_source_sha"] = "0" * 40
            expected_error = "manifest R mismatch"
        elif scenario == "manifest_cell":
            manifest["observation"]["task_id"] = case.plan["shared"]["dataset"]["tasks"][1]["task_id"]
            expected_error = "manifest cell mismatch"
        elif scenario == "manifest_registration":
            manifest["observation"]["registration_sha256"] = "0" * 64
            expected_error = "manifest registration mismatch"
        elif scenario in {"manifest_request_hash", "manifest_request_size"}:
            manifest["request_identity"].update(
                {"sha256": "0" * 64} if scenario == "manifest_request_hash" else {"size": request_identity["size"] + 1})
            expected_error = "manifest execution request mismatch"
        elif scenario == "manifest_claim":
            manifest["claim_commit"] = "0" * 40
            expected_error = "manifest claim commit mismatch"
        elif scenario == "refused_receipt":
            manifest["execution_receipt"] = {"outcome": "returned", "returned": None}
            expected_error = "execution_receipt_schema"
        elif scenario == "missing_receipt":
            manifest["execution_receipt"] = None
            expected_error = "retained_failure_receipt_required"
        elif scenario == "missing_failure":
            manifest["execution_receipt"].pop("failure")
            expected_error = "retained_failure_codes_unavailable"
        elif scenario == "extra_private_field":
            manifest["provider_message"] = PRIVATE + TOKEN
            expected_error = "readout_schema_refused"
        elif scenario == "extra_failure_field":
            manifest["execution_receipt"]["failure"]["message"] = PRIVATE + TOKEN
            expected_error = "execution_failure_schema"
        elif scenario == "wrong_R_tree":
            case.request["completion"]["source"] = {**case.source.result_source, "tree": "0" * 40}
        elif scenario == "wrong_execution_request":
            case.request["execution_request_identity"] = {**request_identity, "sha256": "0" * 64}
        elif scenario == "manifest_encoding":
            transport.gzip_at = 2
        elif scenario == "cumulative_bound":
            now = [time.monotonic()]
            monkeypatch.setattr(time, "monotonic", lambda: now[0])
            transport.hook = lambda number: now.__setitem__(0, now[0] + 35)
        transport.data = native._encoded(manifest)
        if expected_error:
            # There is no expected manifest hash to recompute. These real
            # semantic validators, not a fabricated outer identity, refuse.
            with pytest.raises(ValueError, match="^" + expected_error + "$"):
                subject.project_uncertainty_manifest(transport.data, _context(case))

    before_credentials = scenario in {"wrong_R_tree", "wrong_execution_request"}
    success = scenario in {"native_uncertain", "canonical_v2"}
    credential_steps = []
    if before_credentials:
        def forbidden(*args, **kwargs):
            credential_steps.append(True)
            raise AssertionError("invalid source/request reached credentialed read")
        monkeypatch.setattr(subject, "_read_result", forbidden)
    assert _invoke(case) == (0 if success else 2)
    assert credential_steps == formatted == []
    output = capsys.readouterr()
    assert output.err == "" and all(item not in output.out for item in (TOKEN, PRIVATE, "PrivateConstructionError"))
    if before_credentials:
        assert output.out == "result_readout_refused\n"
        assert transport.calls == [] and not case.source.destination.exists()
        return
    assert len(transport.calls) == 2 and subject.SECONDS == 60
    first, second = transport.calls
    assert first.url.path == f"/api/datasets/{subject.metadata.TARGET}/revision/{OUTPUT_COMMIT}"
    assert parse_qs(first.url.query.decode()) == {"expand": ["private", "sha"]}
    member = native.MANIFEST if scenario != "canonical_v2" else (
        subject.execution._namespace(case.cell)[0] + "/result/" + subject.execution.observation.RESULT)
    assert second.url.path == f"/datasets/{subject.metadata.TARGET}/raw/{OUTPUT_COMMIT}/{member}"
    assert not second.url.query
    assert all(call.method == "GET" and call.headers["accept-encoding"] == "identity"
               and 0 < call.extensions["timeout"]["read"] <= 30 for call in transport.calls)
    if scenario == "cumulative_bound":
        assert second.extensions["timeout"]["read"] == 25
    value = json.loads(case.source.destination.read_bytes())
    subject.validate_envelope(value, _context(case))
    assert json.loads(output.out) == value and value["verified_private"] is True
    assert value["outcome"] == ("read" if success else "refused")
    assert value["retry_allowed"] is False and value["grading_performed"] is False
    if scenario == "canonical_v2":
        assert value["format"] == subject.FORMAT and value["result_source"] == case.source.result_source
        assert value["result_identity"] == case.request["completion"]["result_identity"]
        assert value["result_fingerprint"] == case.payload["result_fingerprint"]
        assert value["summary"]["runner_error"] == "finalize_not_called"
        assert "observed_manifest_identity" not in value["summary"] and "execution_request_identity" not in value
    else:
        assert set(value) == {"format", "controller", "ci", "request_sha256", "target_identity_sha256", "cell",
            "observation_source", "execution_request_sha256", "execution_request_identity", "registration_sha256",
            "output_commit", "claim_commit", "host_sha256", "result_identity", "result_fingerprint",
            "retry_allowed", "grading_performed", "timestamp_utc", "verified_private", "outcome", "summary"}
        assert value["format"] == subject.UNCERTAINTY_FORMAT
        assert value["observation_source"] == case.source.result_source != value["controller"]
        assert value["execution_request_identity"] == case.request["execution_request_identity"]
        assert value["claim_commit"] == case.request["completion"]["claim_commit"]
        assert value["registration_sha256"] == subject.seal(case.plan)
        assert value["result_identity"] is value["result_fingerprint"] is None
        assert "manifest_identity" not in case.request and "manifest_identity" not in case.request["completion"]
        if success:
            assert value["summary"] == {**subject.UNCERTAINTY_SUMMARY,
                "failure": {"stage": "observation_callable", "category": "type_error",
                            "reason": "execution_refused_or_uncertain"},
                "observed_manifest_identity": subject._identity(transport.data)}
            for mutation in ({"provider_message": PRIVATE}, {"manifest_identity_basis": "independently_expected"},
                             {"failure": {**value["summary"]["failure"], "message": PRIVATE}}):
                with pytest.raises(ValueError):
                    subject.validate_envelope({**value, "summary": {**value["summary"], **mutation}}, _context(case))
        else:
            assert value["summary"] is None
    if success:
        assert _invoke(case, "verify-envelope") == 0 and len(transport.calls) == 2
    public = case.source.destination.read_text() + output.out + output.err + capsys.readouterr().out
    assert all(item not in public for item in (TOKEN, PRIVATE, "PRIVATE_FILENAME", "deliverable_text",
        "PrivateConstructionError", "provider_message", "output-manifest.json", "claim_identity",
        "execution_receipt", subject.metadata.TARGET))
    assert set(case.source.runner_temp.iterdir()) == {case.source.root, case.source.destination}
    assert case.source.destination.stat().st_mode & 0o777 == 0o600
