"""Free plan/capture checks; no dataset, handoff, model or network access."""

import json
import os
import signal
import socket
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

import ghcp_sol_actions_gate as gate


@pytest.fixture(autouse=True)
def synthetic_user_configuration(tmp_path, monkeypatch):
    """Never examine the real user's Copilot directory, even its metadata."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "user-config")


@pytest.fixture
def no_runtime(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("event capture attempted network or a runtime process")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(os, "system", forbidden)


def test_fixed_plan_and_all_five_captures(tmp_path, monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        pytest.fail("network or child process attempted")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    read_bytes = Path.read_bytes

    def public_only(path):
        assert path == gate.CATALOG_PATH, "non-catalog input read attempted"
        return read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", public_only)
    assert gate.main(["--matrix"]) == 0
    matrix = json.loads(capsys.readouterr().out)
    assert matrix == {"task_id": list(gate.TASK_IDS)}
    root = tmp_path / "capture"
    for task_id in matrix["task_id"]:
        assert gate.main(["--task-id", task_id, "--state-root", str(root)]) == 0
        task_root = root / task_id
        envelope = json.loads((task_root / "capture.json").read_text())
        assert envelope["requested"] == gate.REQUESTED
        assert set(envelope["actual_served"].values()) == {"not available"}
        assert envelope["model_calls"] == envelope["grader_calls"] == 0
        assert envelope["paid_execution_allowed"] is False
        assert envelope["session_event_receipt"]["status"] == "not_collected"
        assert envelope["session_event_receipt"]["calls"] == []
        assert envelope["session_event_receipt"]["applied_settings_verified"] is False
        assert envelope["limits"]["proposed_paid_timeout_seconds_per_task"] == 1200
        assert envelope["limits"]["proposed_paid_max_turns_per_task"] == 64
        assert envelope["limits"]["dry_run_max_model_turns"] == 0
        assert envelope["versions"]["ghcp_cli"] == "not available"
        assert envelope["versions"]["codex_cli"] == "not available"
        assert envelope["versions"]["python"]
        assert envelope["usage"] is envelope["cost"] is envelope["grade"] is None
        assert envelope["usage_status"] == envelope["cost_status"] == "not available"
        capture = envelope["capture"]
        assert capture["artifact_allowlist"] == ["capture.json"]
        assert capture["private_inputs_read"] is False
        assert capture["private_capture_upload_allowed"] is False
        assert capture["files_captured"] == 0
        for name, relative in capture["private_task_relative_paths"].items():
            path = task_root / relative
            assert path.exists() and not Path(relative).is_absolute()
            if name in ("transcript", "tool_calls", "commands"):
                assert path.read_text() == ""
        assert json.loads((task_root / gate.PRIVATE_PATHS["input_file_hashes"]).read_text()) == []
        assert json.loads((task_root / gate.PRIVATE_PATHS["output_file_hashes"]).read_text()) == []
        assert json.loads((task_root / gate.PRIVATE_PATHS["exit_status"]).read_text()) == {
            "dry_run": True, "model_started": False, "exit_status": 0,
        }
        # Synthetic private streams must never be copied into the public envelope.
        canary = "SYNTHETIC_PRIVATE_CANARY_DO_NOT_UPLOAD"
        (task_root / gate.PRIVATE_PATHS["transcript"]).write_text(canary)
        assert canary not in (task_root / "capture.json").read_text()
        assert str(tmp_path) not in (task_root / "capture.json").read_text()
    streams = capsys.readouterr()
    assert streams.out == "ghcp_sol_dry_capture_complete\n" * 5
    assert streams.err == ""


@pytest.mark.parametrize("matrix", [False, True])
def test_paid_mode_refuses_before_reads_or_writes(tmp_path, monkeypatch, matrix):
    def forbidden():
        pytest.fail("paid mode reached catalogue")

    monkeypatch.setattr(gate, "fixed_task_ids", forbidden)
    root = tmp_path / "must-not-exist"
    args = ["--matrix"] if matrix else [
        "--task-id", gate.TASK_IDS[0], "--state-root", str(root),
    ]
    with pytest.raises(SystemExit) as error:
        gate.main(["--dry-run", "false", *args])
    assert error.value.code == 2
    assert not root.exists()


def test_capture_refuses_reuse_and_symlink(tmp_path, capsys):
    root = tmp_path / "state"
    args = ["--task-id", gate.TASK_IDS[0], "--state-root", str(root)]
    assert gate.main(args) == 0
    capture = root / gate.TASK_IDS[0] / "capture.json"
    before = capture.read_text()
    with pytest.raises(SystemExit) as error:
        gate.main(args)
    assert error.value.code == 2
    assert capture.read_text() == before
    link = tmp_path / "link"
    link.symlink_to(root, target_is_directory=True)
    with pytest.raises(SystemExit):
        gate.main(["--task-id", gate.TASK_IDS[1], "--state-root", str(link)])
    assert capsys.readouterr().err == "ghcp_sol_dry_capture_refused\n" * 2


def test_catalog_drift_refuses(tmp_path, monkeypatch):
    catalog = tmp_path / "public-catalog.json"
    catalog.write_text("{}")
    monkeypatch.setattr(gate, "CATALOG_PATH", catalog)
    with pytest.raises(ValueError, match="public_catalog_identity_refused"):
        gate.fixed_task_ids()


def test_workflow_contract():
    path = Path(__file__).resolve().parents[2] / ".github/workflows/agentic-v2-ghcp-sol-gate.yml"
    text = path.read_text()
    workflow = yaml.load(text, Loader=yaml.BaseLoader)
    assert set(workflow["on"]) == {"push", "workflow_dispatch"}
    assert workflow["on"]["push"]["branches"] == ["leader/ghcp-sol-gate-actions-20261024"]
    assert workflow["on"]["push"]["paths"] == [
        ".github/workflows/agentic-v2-ghcp-sol-gate.yml", "batch-runner/ghcp*.py",
        "batch-runner/requirements-ghcp-sol-gate.txt", "batch-runner/tests/test_ghcp*.py",
        "batch-runner/tests/conftest.py", "batch-runner/tests/fixtures/ghcp*",
    ]
    assert workflow["on"]["workflow_dispatch"]["inputs"]["dry_run"]["default"] == "true"
    assert workflow["permissions"] == {"contents": "read"}
    jobs = workflow["jobs"]
    assert set(jobs) == {"offline-ci", "plan", "task"}
    assert jobs["plan"]["needs"] == "offline-ci"
    for name, job in jobs.items():
        assert job["runs-on"] == "ubuntu-24.04"
        assert job["timeout-minutes"] == ("15" if name == "offline-ci" else "5")
        assert "if" not in job and "continue-on-error" not in job
        guard = job["steps"][0]
        assert guard["name"] == "Refuse paid mode before checkout"
        assert guard["env"] == {"DRY_RUN": "${{ github.event_name == 'push' && 'true' || inputs.dry_run }}"}
        assert guard == jobs["plan"]["steps"][0]
        for step in job["steps"]:
            assert "continue-on-error" not in step
            if name == "offline-ci" and step.get("uses", "").startswith("actions/upload-artifact@"):
                assert step["if"] == "always()"
            else:
                assert "if" not in step
            if step.get("uses", "").startswith("actions/checkout@"):
                assert step["with"]["persist-credentials"] == "false"
    task = jobs["task"]
    assert task["needs"] == "plan"
    assert task["strategy"] == {
        "fail-fast": "false", "matrix": "${{ fromJSON(needs.plan.outputs.matrix) }}",
    }
    assert "Paid execution is not implemented or approved." in jobs["plan"]["steps"][0]["run"]
    upload = task["steps"][-1]["with"]
    assert upload["path"] == "${{ runner.temp }}/ghcp-sol-gate/${{ matrix.task_id }}/capture.json"
    assert upload["include-hidden-files"] == "false"
    assert upload["if-no-files-found"] == "error"
    assert "60s" in task["steps"][-2]["run"]
    ci = jobs["offline-ci"]
    installer = next(step for step in ci["steps"] if step.get("name", "").startswith("Install and verify"))
    assert "v1.0.103/copilot-linux-x64.tar.gz" in installer["run"]
    assert "9aeb4430e9ac9523546db07b227c7aba179a4710a55f9ac29ad143b0f9e1b325" in installer["run"]
    assert "f19b3554a6b62605db3a26d5255ebe2a3ee39fcd6a357edb18301ea5037f6f0d" in installer["run"]
    assert "--no-auto-update --disable-client-telemetry --version" in installer["run"]
    assert "env -i PATH=/usr/bin:/bin" in installer["run"]
    testing = next(step for step in ci["steps"] if step.get("name") == "Run the whole offline gate suite once")
    for target in ("actions_gate", "execution_adapter", "copilot_smoke", "runner_environment"):
        assert f"tests/test_ghcp_sol_{target}.py" in testing["run"]
    assert "tests/test_ghcp_vm_gate_contract.py" in testing["run"]
    assert "tests/test_ghcp_vm_input_bundle.py" in testing["run"]
    assert "env -i" in testing["run"] and "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1" in testing["run"]
    for forbidden in ("secrets.", "id-token:", "/dev/kvm", "azure/login", "hf download",
                      "--execute-smoke", "copilot -p", "run_copilot_smoke(", "--allow-all-tools"):
        assert forbidden not in text
    installs = [step["run"] for step in ci["steps"] if "pip install" in step.get("run", "")]
    assert installs == ["python -m pip install --disable-pip-version-check -r batch-runner/requirements-ghcp-sol-gate.txt"]


def test_model_free_workflow_shells_parse_without_execution():
    path = Path(__file__).resolve().parents[2] / ".github/workflows/agentic-v2-ghcp-sol-gate.yml"
    workflow = yaml.load(path.read_text(), Loader=yaml.BaseLoader)
    for job in workflow["jobs"].values():
        for step in job["steps"]:
            if "run" in step:
                result = subprocess.run(["bash", "--noprofile", "--norc", "-n"],
                                        input=step["run"], capture_output=True, text=True,
                                        env={"PATH": os.defpath}, timeout=5)
                assert result.returncode == 0, result.stderr


def test_ci_fake_token_preflight_never_calls_a_runtime():
    root = Path(__file__).resolve().parents[2]
    workflow = yaml.load((root / ".github/workflows/agentic-v2-ghcp-sol-gate.yml").read_text(), Loader=yaml.BaseLoader)
    step = next(row for row in workflow["jobs"]["offline-ci"]["steps"]
                if row.get("name") == "Fake-token projection only - never launch a CLI")
    result = subprocess.run(["bash", "--noprofile", "--norc", "-c", step["run"]], cwd=root,
                            env={"PATH": os.defpath, "PYTHON_EXECUTABLE": sys.executable},
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"fake_auth_preflight": "passed", "model_calls": 0,
                                       "auth_source": "COPILOT_GITHUB_TOKEN"}
    assert "SYNTHETIC_CI_NOT_A_CREDENTIAL" not in result.stdout + result.stderr


@pytest.mark.parametrize("version,accepted", [
    ("GitHub Copilot CLI 1.0.103.\nRun 'copilot update' to check for updates.\n", True),
    ("GitHub Copilot CLI 1.0.103.\n", True),
    ("GitHub Copilot CLI 1.0.104.\n", False),
    ("GitHub Copilot CLI 1.0.103.\nUNEXPECTED_EXTRA_OUTPUT\n", False),
])
def test_ci_checks_the_retained_cli_version_format(tmp_path, version, accepted):
    root = Path(__file__).resolve().parents[2]
    workflow = yaml.load((root / ".github/workflows/agentic-v2-ghcp-sol-gate.yml").read_text(), Loader=yaml.BaseLoader)
    step = next(row for row in workflow["jobs"]["offline-ci"]["steps"]
                if row.get("name", "").startswith("Install and verify Copilot CLI"))
    check = step["run"].split("<<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]
    (tmp_path / "ghcp-model-free").mkdir()
    (tmp_path / "ghcp-model-free/copilot-version.txt").write_text(version)
    result = subprocess.run([sys.executable, "-c", check], env={"PATH": os.defpath, "RUNNER_TEMP": str(tmp_path)},
                            capture_output=True, text=True, timeout=10)
    assert (result.returncode == 0) is accepted
    if not accepted:
        assert "copilot_version_mismatch" in result.stderr


@pytest.mark.parametrize("job_name", ["offline-ci", "plan", "task"])
@pytest.mark.parametrize("dry_run", [
    "true", "false", "", "True", "TRUE", "1", "0", " true", "true\n", "true false",
])
def test_each_job_guard_executes_fail_closed_before_checkout(job_name, dry_run, tmp_path):
    path = Path(__file__).resolve().parents[2] / ".github/workflows/agentic-v2-ghcp-sol-gate.yml"
    workflow = yaml.load(path.read_text(), Loader=yaml.BaseLoader)
    guard = workflow["jobs"][job_name]["steps"][0]
    assert guard.get("env") == {"DRY_RUN": "${{ github.event_name == 'push' && 'true' || inputs.dry_run }}"}
    result = subprocess.run(
        ["bash", "--noprofile", "--norc", "-c", guard["run"]],
        cwd=tmp_path,
        env={"PATH": os.defpath, "DRY_RUN": dry_run},
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    assert result.returncode == (0 if dry_run == "true" else 2)
    assert result.stdout == (
        "" if dry_run == "true"
        else "::error::Paid execution is not implemented or approved.\n"
    )
    assert result.stderr == ""
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("dry_run", [
    "false", "", "True", "TRUE", "1", "0", " true", "true\n", "true false",
])
@pytest.mark.parametrize("matrix", [False, True])
def test_runner_refuses_nontrue_modes_before_catalogue(tmp_path, monkeypatch, dry_run, matrix):
    def forbidden():
        pytest.fail("invalid mode reached catalogue")

    monkeypatch.setattr(gate, "fixed_task_ids", forbidden)
    root = tmp_path / "must-not-exist"
    args = ["--matrix"] if matrix else [
        "--task-id", gate.TASK_IDS[0], "--state-root", str(root),
    ]
    with pytest.raises(SystemExit) as error:
        gate.main(["--dry-run", dry_run, *args])
    assert error.value.code == 2
    assert not root.exists()


CANARY = "SYNTHETIC_PRIVATE_EVENT_CANARY_NOT_FOR_RECEIPTS"


def _usage(call=1, **overrides):
    # Documented JSON event envelope, not an actual captured GHCP response.
    return {
        "id": f"00000000-0000-4000-8000-{call:012d}",
        "type": "assistant.usage", "ephemeral": True,
        "data": {"model": "gpt-5.6-sol", "reasoningEffort": "max", **overrides},
    }


def _context(limit=1_000_000, **envelope):
    return {
        "type": "session.usage_info", "ephemeral": True,
        "data": {"tokenLimit": limit, "currentTokens": 25, "messagesLength": 1},
        **envelope,
    }


def _captured(tmp_path, events, capsys):
    source = tmp_path / "synthetic-events.jsonl"
    source.write_text("".join(json.dumps(event) + "\n" for event in events))
    root = tmp_path / "capture"
    args = ["--task-id", gate.TASK_IDS[0], "--state-root", str(root),
            "--session-events", str(source)]
    try:
        exit_code = gate.main(args)
    except SystemExit as error:
        exit_code = error.code
    capture = json.loads((root / gate.TASK_IDS[0] / "capture.json").read_text())
    private_exit = json.loads((root / gate.TASK_IDS[0] / gate.PRIVATE_PATHS["exit_status"]).read_text())
    assert capture["exit_status"] == private_exit["exit_status"] == exit_code
    assert private_exit["model_started"] is False
    streams = capsys.readouterr()
    assert CANARY not in json.dumps(capture) + streams.out + streams.err
    assert str(tmp_path) not in json.dumps(capture) + streams.out + streams.err
    assert streams.out == ("ghcp_sol_dry_capture_complete\n" if exit_code == 0 else "")
    assert streams.err == ("" if exit_code == 0 else "ghcp_sol_session_evidence_refused\n")
    assert capture["paid_execution_allowed"] is False
    assert set(capture["actual_served"].values()) == {"not available"}
    assert capture["model_calls"] == capture["grader_calls"] == 0
    assert capture["usage"] is capture["cost"] is capture["grade"] is None
    assert capture["usage_status"] == capture["cost_status"] == "not available"
    receipt = capture["session_event_receipt"]
    assert receipt["evidence_level"] == "settings_only"
    for field in ("paid_execution_allowed", "applied_settings_verified", "live_source_verified",
                  "stream_completeness_verified", "retry_allowed"):
        assert receipt[field] is False
    assert receipt["observed_usage_events"] == len(receipt["calls"])
    assert (receipt["status"] == "failed") == (exit_code == 2)
    for name in ("transcript", "tool_calls", "commands"):
        assert (root / gate.TASK_IDS[0] / gate.PRIVATE_PATHS[name]).read_text() == ""
    return receipt


def test_session_events_capture_documented_fields_without_promoting_evidence(tmp_path, capsys, no_runtime):
    first = _usage(prompt=CANARY, headers={"Authorization": CANARY}, apiCallId=CANARY)
    second = _usage(2)
    second["agentId"] = CANARY
    events = [
        {"type": "session.start", "data": {"sessionId": CANARY}},
        _context(), first,
        {"type": "assistant.message", "data": {"content": CANARY}},
        _context(agentId=CANARY), second,
    ]
    receipt = _captured(tmp_path, events, capsys)
    assert receipt["status"] == "consistent_settings_only"
    assert receipt["reason_codes"] == []
    assert receipt["observed_usage_events"] == 2
    for index, call in enumerate(receipt["calls"], 1):
        assert call == {
            "call_index": index, "event_index": 3 if index == 1 else 6,
            "agent_scope": "main" if index == 1 else "subagent",
            "model": "gpt-5.6-sol", "reasoningEffort": "max", "tokenLimit": 1_000_000,
            "modelContextWindow": None, "context_event_index": 2 if index == 1 else 5,
            "context_binding": "preceding_same_agent_session_snapshot_not_call_attestation",
            "modelContextWindow_status": "not_in_documented_ghcp_event_contract",
            "reason_codes": [],
        }


@pytest.mark.parametrize("change,reason", [
    ({"model": "gpt-5.4"}, "served_model_mismatch"),
    ({"model": "gpt-5.6-sol-fast"}, "served_model_mismatch"),
    ({"model": CANARY}, "served_model_mismatch"),
    ({"model": None}, "served_model_unverified"),
    ({"model": []}, "served_model_unverified"),
    ({"model": ""}, "served_model_unverified"),
    ({"reasoningEffort": "high"}, "reasoning_effort_mismatch"),
    ({"reasoningEffort": "xhigh"}, "reasoning_effort_mismatch"),
    ({"reasoningEffort": None}, "reasoning_effort_unverified"),
    ({"reasoningEffort": CANARY}, "reasoning_effort_unverified"),
    ({"reasoningEffort": {}}, "reasoning_effort_unverified"),
])
def test_session_events_every_call_fails_closed(tmp_path, capsys, no_runtime, change, reason):
    receipt = _captured(tmp_path, [_context(), _usage(), _usage(2, **change)], capsys)
    assert receipt["status"] == "failed"
    assert receipt["observed_usage_events"] == 2
    assert receipt["calls"][0]["reason_codes"] == []
    assert reason in receipt["calls"][1]["reason_codes"]
    assert reason in receipt["reason_codes"]
    assert "call_metadata_conflict" in receipt["reason_codes"]


@pytest.mark.parametrize("field,reason", [
    ("model", "served_model_unverified"),
    ("reasoningEffort", "reasoning_effort_unverified"),
])
def test_session_events_missing_fields_are_not_filled_from_requests(tmp_path, capsys, no_runtime, field, reason):
    call = _usage()
    del call["data"][field]
    receipt = _captured(tmp_path, [_context(), call], capsys)
    assert receipt["reason_codes"] == [reason]
    assert receipt["calls"][0][field] is None


@pytest.mark.parametrize("limit,reason", [
    (258400, "context_limit_mismatch"), (1_050_000, "context_limit_mismatch"),
    (None, "context_limit_unverified"), (True, "context_limit_unverified"),
    (0, "context_limit_unverified"), (-1, "context_limit_unverified"),
    (1_000_000.0, "context_limit_unverified"), ("1000000", "context_limit_unverified"),
    (CANARY, "context_limit_unverified"), (2**100, "context_limit_unverified"),
])
def test_session_context_changes_are_not_hidden(tmp_path, capsys, no_runtime, limit, reason):
    receipt = _captured(tmp_path, [_context(), _usage(), _context(limit), _usage(2)], capsys)
    assert reason in receipt["reason_codes"]
    assert "call_metadata_conflict" in receipt["reason_codes"]
    assert receipt["calls"][0]["tokenLimit"] == 1_000_000
    assert receipt["calls"][1]["context_event_index"] == 3


@pytest.mark.parametrize("variant", ["late", "subagent", "missing_limit", "codex_metadata"])
def test_context_is_not_backfilled_or_borrowed(tmp_path, capsys, no_runtime, variant):
    events = [_context(), _usage()]
    if variant == "late":
        events.reverse()
    elif variant == "subagent":
        events[1]["agentId"] = CANARY
    elif variant == "missing_limit":
        events[0]["data"] = {"modelContextWindow": 1_000_000}
    else:
        # Codex's different harness has no bound GHCP per-call context here.
        events[0] = {"type": "thread.tokenUsage.updated", "data": {
            "tokenUsage": {"modelContextWindow": 1_000_000},
        }}
    receipt = _captured(tmp_path, events, capsys)
    assert receipt["reason_codes"] == ["context_limit_unverified"]
    assert receipt["calls"][0]["tokenLimit"] is None
    assert receipt["calls"][0]["modelContextWindow"] is None


@pytest.mark.parametrize("origin", [{"initiator": "sub-agent"}, {"parentToolCallId": CANARY}])
def test_subagent_without_agent_id_cannot_borrow_main_context(tmp_path, capsys, no_runtime, origin):
    receipt = _captured(tmp_path, [_context(), _usage(**origin)], capsys)
    assert receipt["reason_codes"] == ["session_event_identity_unverified", "context_limit_unverified"]
    assert receipt["calls"][0]["agent_scope"] == "unbound_subagent"
    assert receipt["calls"][0]["tokenLimit"] is None
    assert receipt["calls"][0]["context_event_index"] is None


@pytest.mark.parametrize("variant,reason", [
    ("duplicate", "session_event_duplicate"), ("missing_id", "session_event_identity_unverified"),
    ("malformed", "session_event_stream_refused"), ("resume", "session_event_stream_refused"),
    ("new_session", "session_event_stream_refused"), ("invalid_agent", "session_event_stream_refused"),
])
def test_session_event_identity_and_stream_refusals(tmp_path, capsys, no_runtime, variant, reason):
    events = [_context(), _usage()]
    if variant == "duplicate":
        events.append(deepcopy(events[-1]))
    elif variant == "missing_id":
        del events[-1]["id"]
    elif variant == "malformed":
        events.append({"type": "assistant.usage", "data": CANARY})
    elif variant in ("resume", "new_session"):
        events.append({"type": "session.resume" if variant == "resume" else "session.start", "data": {}})
    else:
        events[-1]["agentId"] = []
    receipt = _captured(tmp_path, events, capsys)
    assert reason in receipt["reason_codes"]


def test_empty_event_stream_is_unknown_not_success(tmp_path, capsys, no_runtime):
    receipt = _captured(tmp_path, [], capsys)
    assert receipt["status"] == "failed"
    assert receipt["reason_codes"] == [
        "served_model_unverified", "reasoning_effort_unverified", "context_limit_unverified",
    ]


@pytest.mark.parametrize("variant", ["malformed", "duplicate_key", "nan", "line_bound", "file_bound", "symlink", "missing"])
def test_event_file_failure_keeps_only_a_safe_receipt(tmp_path, capsys, no_runtime, variant):
    source = tmp_path / "synthetic-events.jsonl"
    contents = CANARY
    if variant == "duplicate_key":
        contents = '{"type":"assistant.usage","data":{"model":"gpt-5.6-sol","model":"' + CANARY + '"}}'
    elif variant == "nan":
        contents = '{"type":"session.usage_info","data":{"tokenLimit":NaN}}'
    elif variant == "line_bound":
        contents = " " * (gate.MAX_EVENT_LINE_BYTES + 1)
    elif variant == "file_bound":
        contents = " " * (gate.MAX_EVENT_BYTES + 1)
    if variant == "symlink":
        target = tmp_path / "do-not-read"
        target.write_text(CANARY)
        source.symlink_to(target)
    elif variant != "missing":
        source.write_text(contents)
    root = tmp_path / "capture"
    with pytest.raises(SystemExit) as error:
        gate.main(["--task-id", gate.TASK_IDS[0], "--state-root", str(root), "--session-events", str(source)])
    assert error.value.code == 2
    data = (root / gate.TASK_IDS[0] / "capture.json").read_text()
    receipt = json.loads(data)["session_event_receipt"]
    assert receipt["status"] == "failed"
    assert "session_event_stream_refused" in receipt["reason_codes"]
    streams = capsys.readouterr()
    assert streams.out == "" and streams.err == "ghcp_sol_session_evidence_refused\n"
    assert CANARY not in data + streams.out + streams.err
    assert str(tmp_path) not in data + streams.out + streams.err


def test_event_iterator_failure_and_bound_preserve_partial_metadata(no_runtime, monkeypatch):
    def failing():
        yield _context()
        yield _usage()
        raise RuntimeError(CANARY)

    receipt = gate.collect_session_events(failing())
    assert receipt["observed_usage_events"] == 1
    assert receipt["reason_codes"] == ["session_event_stream_refused"]
    assert CANARY not in json.dumps(receipt)
    monkeypatch.setattr(gate, "MAX_EVENTS", 2)
    bounded = gate.collect_session_events([_context(), _usage(), _usage(2)])
    assert bounded["observed_usage_events"] == 1
    assert bounded["reason_codes"] == ["session_event_stream_refused"]


@pytest.mark.parametrize("args,reason", [
    (["--model", "auto"], "auto_model_refused"),
    (["--model", " Auto "], "auto_model_refused"),
    (["--model", "gpt-5.6-sol-fast"], "model_selection_refused"),
    (["--model", CANARY], "model_selection_refused"),
    (["--byok"], "custom_provider_refused"),
    (["--provider-config", CANARY], "custom_provider_refused"),
])
@pytest.mark.parametrize("matrix", [False, True])
def test_dry_run_selection_refuses_before_capture_or_reads(tmp_path, monkeypatch, capsys, no_runtime, args, reason, matrix):
    def forbidden(*args, **kwargs):
        pytest.fail("selection refusal reached catalogue or event reads")

    monkeypatch.setattr(gate, "fixed_task_ids", forbidden)
    monkeypatch.setattr(gate, "read_session_events", forbidden)
    root = tmp_path / "not-created"
    target = ["--matrix"] if matrix else ["--task-id", gate.TASK_IDS[0], "--state-root", str(root),
                                         "--session-events", CANARY]
    with pytest.raises(SystemExit) as error:
        gate.main([*target, *args])
    assert error.value.code == 2
    assert not root.exists()
    streams = capsys.readouterr()
    assert streams.out == "" and streams.err == reason + "\n"


@pytest.mark.parametrize("key,reason", [
    ("COPILOT_PROVIDER_API_KEY", "custom_provider_refused"),
    ("COPILOT_PROVIDER_API_KEY_COMMAND", "custom_provider_refused"),
    ("COPILOT_PROVIDER_BASE_URL", "custom_provider_refused"),
    ("COPILOT_PROVIDER_HEADERS", "custom_provider_refused"),
    ("COPILOT_PROVIDERS_CONFIG", "custom_provider_refused"),
    ("COPILOT_MODEL", "model_selection_unverified"),
    ("COPILOT_HOME", "provider_configuration_unverified"),
])
def test_inherited_routing_is_refused_without_reading_values(monkeypatch, no_runtime, key, reason):
    class NamesOnly(dict):
        def __getitem__(self, key):
            pytest.fail("environment value read")

        def get(self, *args):
            pytest.fail("environment value read")

    monkeypatch.setattr(os, "environ", NamesOnly({key: CANARY}))
    with pytest.raises(gate.GateRefused) as error:
        gate.check_selection()
    assert error.value.code == reason


@pytest.mark.parametrize("kind", ["empty", "private_contents", "symlink", "config_dir_symlink"])
def test_default_provider_registry_is_refused_without_opening_it(tmp_path, monkeypatch, no_runtime, kind):
    config_dir = Path.home() / ".copilot"
    config_dir.parent.mkdir()
    if kind == "config_dir_symlink":
        config_dir.symlink_to(tmp_path, target_is_directory=True)
    else:
        config_dir.mkdir()
        registry = config_dir / "providers.json"
        if kind == "symlink":
            registry.symlink_to(tmp_path / "missing")
        else:
            registry.write_text("" if kind == "empty" else CANARY)

    def forbidden(*args, **kwargs):
        pytest.fail("provider registry or credential contents read")

    monkeypatch.setattr(Path, "open", forbidden)
    with pytest.raises(gate.GateRefused) as error:
        gate.check_selection()
    assert error.value.code == ("provider_configuration_unverified" if kind == "config_dir_symlink" else "custom_provider_refused")


def test_direct_capture_and_cli_errors_cannot_bypass_or_leak(tmp_path, monkeypatch, capsys, no_runtime):
    def forbidden(*args, **kwargs):
        pytest.fail("refusal reached an input read")

    monkeypatch.setattr(gate, "fixed_task_ids", forbidden)
    with pytest.raises(gate.GateRefused, match="^auto_model_refused$"):
        gate.dry_capture(gate.TASK_IDS[0], tmp_path / "unused", model="auto")
    assert not (tmp_path / "unused").exists()
    with pytest.raises(SystemExit) as error:
        gate.main(["--unknown-option", CANARY])
    assert error.value.code == 2
    assert capsys.readouterr().err == "ghcp_sol_dry_capture_refused\n"
    assert str(gate.GateRefused(CANARY)) == "model_selection_unverified"


def _turn(number, **envelope):
    # Documented logical turn start, not a native request or a usage response.
    return {"type": "assistant.turn_start", "data": {"turnId": str(number)}, **envelope}


@pytest.mark.parametrize("turns", [63, 64, 65])
def test_task_turn_capture_boundary_and_receipt(tmp_path, capsys, no_runtime, turns):
    receipt = _captured(tmp_path, [_context(), _usage(), *(_turn(i) for i in range(turns))], capsys)
    limits = receipt["collection_limits"]
    assert limits["max_turns"] == 64
    assert limits["observed_turn_starts"] == turns
    assert receipt["observed_usage_events"] == 1  # Not counted as turns.
    assert receipt["reason_codes"] == (["turn_cap_exceeded"] if turns > 64 else [])
    assert limits["event_stream_cleanup"] == "closed"
    assert limits["live_enforcement_verified"] is False
    assert limits["scope"] == "offline_collection_not_live_task_execution"


def test_turn_cap_stops_consumption_and_closes_stream(no_runtime):
    closed = []

    def events():
        try:
            yield _context()
            yield _usage()
            for i in range(65):
                # Repeated turn numbers in different agents still count.
                yield _turn(i // 2, agentId=f"{CANARY}-{i % 2}")
            pytest.fail("capture consumed events after exceeding the turn cap")
        finally:
            closed.append(True)

    receipt = gate.collect_session_events(events())
    assert receipt["reason_codes"] == ["turn_cap_exceeded"]
    assert receipt["collection_limits"]["observed_turn_starts"] == 65
    assert closed == [True]
    assert CANARY not in json.dumps(receipt)
    # A fresh task has its own counter, never a continuation of the old one.
    fresh = gate.collect_session_events([_context(), _usage(), _turn(1)])
    assert fresh["reason_codes"] == []
    assert fresh["collection_limits"]["observed_turn_starts"] == 1


@pytest.mark.parametrize("bad", [None, "", 1, True, [], CANARY * 20, "duplicate", "bad_agent"])
def test_turn_count_cannot_be_hidden_by_bad_identity(no_runtime, bad):
    event = _turn(1)
    if bad == "bad_agent":
        event["agentId"] = []
    elif bad != "duplicate":
        event["data"]["turnId"] = bad
    receipt = gate.collect_session_events([_context(), _usage(), _turn(1), event])
    assert receipt["reason_codes"] == ["turn_count_unverified"]
    assert receipt["collection_limits"]["observed_turn_starts"] == 1
    assert CANARY not in json.dumps(receipt)


@pytest.mark.parametrize("elapsed", [1199.0, 1200.0, 1201.0])
def test_task_capture_deadline_is_cumulative_and_closes(no_runtime, monkeypatch, elapsed):
    now = [1000.0]
    monkeypatch.setattr(gate, "monotonic", lambda: now[0])
    closed = []

    def events():
        try:
            yield _context()
            yield _usage()
            now[0] += elapsed
            # An event timestamp cannot reset the local monotonic deadline.
            yield {"type": "assistant.message", "timestamp": 0, "data": {"content": CANARY}}
            if elapsed >= 1200:
                pytest.fail("capture resumed after its deadline")
        finally:
            closed.append(True)

    before = signal.getsignal(signal.SIGALRM)
    receipt = gate.collect_session_events(events())
    assert receipt["reason_codes"] == (["task_timeout_exceeded"] if elapsed >= 1200 else [])
    assert receipt["collection_limits"]["timeout_seconds"] == 1200
    assert receipt["collection_limits"]["event_stream_cleanup"] == "closed"
    assert receipt["observed_usage_events"] == 1
    assert closed == [True]
    assert signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)
    assert signal.getsignal(signal.SIGALRM) is before
    assert CANARY not in json.dumps(receipt)


def test_task_capture_checks_deadline_on_eof(no_runtime, monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(gate, "monotonic", lambda: now[0])

    def events():
        yield _context()
        yield _usage()
        now[0] += 1200

    receipt = gate.collect_session_events(events())
    assert receipt["reason_codes"] == ["task_timeout_exceeded"]
    assert receipt["collection_limits"]["event_stream_cleanup"] == "closed"


def test_timeout_persists_failed_capture_and_exit_receipt(tmp_path, no_runtime, monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(gate, "monotonic", lambda: now[0])

    def events():
        yield _context()
        yield _usage()
        now[0] += 1200
        yield _turn(1)

    root = tmp_path / "capture"
    task_id = gate.TASK_IDS[0]
    assert gate.dry_capture(task_id, root, session_events=events()) == 2
    capture = json.loads((root / task_id / "capture.json").read_text())
    private_exit = json.loads((root / task_id / gate.PRIVATE_PATHS["exit_status"]).read_text())
    assert capture["status"] == "failed"
    assert capture["session_event_receipt"]["reason_codes"] == ["task_timeout_exceeded"]
    assert capture["exit_status"] == private_exit["exit_status"] == 2
    assert private_exit["model_started"] is False
    assert capture["paid_execution_allowed"] is False
    assert capture["session_event_receipt"]["collection_limits"]["event_stream_cleanup"] == "closed"


def test_task_capture_timer_interrupts_blocked_next(no_runtime, monkeypatch):
    real_setitimer = signal.setitimer
    armed = []
    closed = []
    monkeypatch.setattr(gate, "monotonic", lambda: 1000.0)

    def accelerated_timer(which, seconds, interval=0):
        # Keep the draft value intact; only accelerate the OS timer fixture.
        if seconds:
            armed.append(seconds)
            assert seconds == 1200
            return (0.0, 0.0)
        return real_setitimer(which, 0, interval)

    monkeypatch.setattr(signal, "setitimer", accelerated_timer)

    def events():
        try:
            yield _context()
            yield _usage()
            # Arm only at the blocking point, avoiding a scheduling race while
            # setting up the known-good metadata events.
            real_setitimer(signal.ITIMER_REAL, 0.02)
            signal.pause()
            pytest.fail("blocked iterator resumed instead of refusing")
        finally:
            closed.append(True)

    before = signal.getsignal(signal.SIGALRM)
    receipt = gate.collect_session_events(events())
    assert receipt["reason_codes"] == ["task_timeout_exceeded"]
    assert armed == [1200]
    assert closed == [True]
    assert signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)
    assert signal.getsignal(signal.SIGALRM) is before


@pytest.mark.parametrize("unsupported", ["owned_timer", "worker_thread"])
def test_task_capture_refuses_without_stealing_timer_or_reading(no_runtime, monkeypatch, unsupported):
    def forbidden(*args, **kwargs):
        pytest.fail("unsupported capture read events or modified a timer")

    if unsupported == "owned_timer":
        monkeypatch.setattr(signal, "getitimer", lambda which: (30.0, 0.0))
    else:
        monkeypatch.setattr(gate.threading, "current_thread", lambda: object())
    monkeypatch.setattr(signal, "setitimer", forbidden)

    def events():
        forbidden()
        yield

    receipt = gate.collect_session_events(events())
    assert receipt["status"] == "failed"
    assert receipt["reason_codes"][0] == "task_timeout_guard_unavailable"
    assert receipt["collection_limits"]["event_stream_cleanup"] == "not_opened"
    assert receipt["calls"] == []


def test_capture_cleanup_failure_is_not_success_or_raw_error(no_runtime):
    class Stream:
        def __iter__(self):
            return self

        def __init__(self):
            self.events = iter([_context(), _usage()])

        def __next__(self):
            return next(self.events)

        def close(self):
            raise RuntimeError(CANARY)

    receipt = gate.collect_session_events(Stream())
    assert receipt["status"] == "failed"
    assert receipt["reason_codes"] == ["session_event_cleanup_refused"]
    assert receipt["collection_limits"]["event_stream_cleanup"] == "failed"
    assert CANARY not in json.dumps(receipt)


def test_turn_cap_closes_actual_synthetic_file(tmp_path, monkeypatch, capsys, no_runtime):
    real_fdopen = gate.os.fdopen
    opened = []

    def tracked_fdopen(*args, **kwargs):
        stream = real_fdopen(*args, **kwargs)
        opened.append(stream)
        return stream

    monkeypatch.setattr(gate.os, "fdopen", tracked_fdopen)
    receipt = _captured(tmp_path, [_context(), _usage(), *(_turn(i) for i in range(65))], capsys)
    assert receipt["reason_codes"] == ["turn_cap_exceeded"]
    assert len(opened) == 1 and opened[0].closed


@pytest.mark.parametrize("events", [None, [], [_context(), _usage()]])
def test_unavailable_usage_and_undefined_tool_cap_are_explicit(no_runtime, events):
    envelope = gate.capture_envelope(gate.TASK_IDS[0], session_events=events)
    assert envelope["usage"] is envelope["cost"] is None
    assert envelope["usage_status"] == envelope["cost_status"] == "not available"
    assert envelope["usage_reason"] == "native_ghcp_usage_not_collected"
    assert envelope["cost_reason"] == "native_ghcp_cost_not_collected"
    assert envelope["limits"]["proposed_paid_max_tool_calls_per_task"] is None
    limits = envelope["session_event_receipt"]["collection_limits"]
    assert limits["max_tool_calls"] is None
    assert limits["tool_call_cap_status"] == "value_not_defined"
    assert limits["subprocess_cleanup"] == "not_applicable_no_subprocess_started"
    assert envelope["limits"]["paid_limits_approved_or_verified"] is False
    assert envelope["paid_execution_allowed"] is False
