"""Real local fake processes, never a GHCP CLI, authentication or model call."""

import builtins
import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

import ghcp_sol_actions_gate as gate
import ghcp_sol_execution_adapter as adapter


CANARY = "SYNTHETIC_PRIVATE_ADAPTER_CANARY"
PROGRAM = r'''
import json
import os
import signal
import subprocess
import sys
from pathlib import Path

CANARY = "SYNTHETIC_PRIVATE_ADAPTER_CANARY"
mode = sys.argv[1]
amount = int(sys.argv[2])
descendant = None
stubborn = mode.endswith("_stubborn")

def stop(signum, frame):
    if descendant is not None:
        descendant.wait(timeout=3)
    raise SystemExit(0)

signal.signal(signal.SIGTERM, signal.SIG_IGN if stubborn else stop)

def spawn(role):
    return subprocess.Popen(
        [sys.executable, __file__, role + ("_stubborn" if stubborn else ""), "0"],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )

if mode.startswith("grandchild"):
    Path("grandchild.pid").write_text(str(os.getpid()))
    print("ready", flush=True)
    signal.pause()
elif mode.startswith("child"):
    Path("child.pid").write_text(str(os.getpid()))
    descendant = spawn("grandchild")
    assert descendant.stdout.readline() == b"ready\n"
    print("ready", flush=True)
    signal.pause()
else:
    Path("leader.pid").write_text(str(os.getpid()))
    Path("partial.txt").write_text(CANARY)
    if mode.startswith("tree"):
        descendant = spawn("child")
        assert descendant.stdout.readline() == b"ready\n"

    def emit(kind, data, **envelope):
        print(json.dumps({"type": kind, "data": data, **envelope}), flush=True)

    if mode == "empty":
        raise SystemExit(0)
    emit("session.start", {"sessionId": CANARY})
    emit("session.usage_info", {"tokenLimit": 1000000})
    emit("assistant.usage", {"model": "gpt-5.6-sol", "reasoningEffort": "max",
                            "prompt": CANARY, "headers": {"Authorization": CANARY}}, id=CANARY)
    print(CANARY, file=sys.stderr, flush=True)
    if mode == "missing_turn":
        raise SystemExit(0)
    if "turn_cap" in mode or mode == "turns":
        for n in range(amount):
            emit("assistant.turn_start", {"turnId": str(n)})
    else:
        emit("assistant.turn_start", {"turnId": "0"})
    if "tool_cap" in mode or mode == "tools":
        for n in range(amount):
            emit("tool.execution_start", {"toolCallId": str(n), "arguments": CANARY})
            emit("tool.execution_complete", {"toolCallId": str(n), "result": CANARY})
    if mode == "mixed_agents":
        emit("assistant.turn_start", {"turnId": "0"}, agentId=CANARY)
        emit("tool.execution_start", {"toolCallId": "same"})
        emit("tool.execution_start", {"toolCallId": "same"}, agentId=CANARY)
    if mode == "duplicate_turn":
        emit("assistant.turn_start", {"turnId": "0"})
    if mode == "duplicate_tool":
        for _ in range(2):
            emit("tool.execution_start", {"toolCallId": "same"})
    if mode == "bad_turn":
        emit("assistant.turn_start", {"turnId": []})
    if mode == "bad_tool":
        emit("tool.execution_start", {"toolCallId": True})
    if mode == "unbound_tool":
        emit("tool.execution_start", {"toolCallId": "1", "parentToolCallId": CANARY})
    if mode == "bad_agent":
        emit("tool.execution_start", {"toolCallId": "1"}, agentId=[])
    if mode == "malformed":
        print(CANARY, flush=True)
    if mode == "duplicate_json":
        print('{"type":"tool.execution_start","data":{},"data":{}}', flush=True)
    if mode == "oversize":
        print(CANARY * 3000, flush=True)
    if mode == "nan":
        print('{"type":"ignored","data":{"secret":NaN}}', flush=True)
    if mode == "wrong_model":
        emit("assistant.usage", {"model": CANARY, "reasoningEffort": "max"}, id="2")
    if mode == "clock":
        emit("fixture.clock", {})
    if mode == "stderr_flood":
        sys.stderr.write(CANARY * 100000)
        sys.stderr.flush()
    if mode == "nonzero":
        raise SystemExit(7)
    if mode == "split_line_hang":
        os.write(1, b'{"type":"private-incomplete')
    if mode == "closed_pipe_hang":
        os.close(1)
    if mode == "tree_leader_exit":
        os._exit(0)
    if "hang" in mode or mode.startswith("tree"):
        signal.pause()
'''


@pytest.fixture(autouse=True)
def offline_only(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "synthetic-user")

    def forbidden(*args, **kwargs):
        pytest.fail("adapter fixture attempted a network/provider/credential operation")

    real_import = builtins.__import__

    def imports(name, *args, **kwargs):
        if name.split(".")[0] in {"azure", "openai", "huggingface_hub", "httpx", "requests", "copilot"}:
            forbidden()
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", imports)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(os, "system", forbidden)


@pytest.fixture
def fake_program(tmp_path, monkeypatch):
    script = tmp_path / "fake-runtime.py"
    script.write_text(PROGRAM)
    real_popen = subprocess.Popen
    owned = []

    def start(command, **kwargs):
        assert command[:2] == [sys.executable, str(script)]
        assert kwargs["start_new_session"] is True
        assert kwargs["close_fds"] is True
        assert kwargs["stdin"] == subprocess.DEVNULL
        assert kwargs["stderr"] == subprocess.DEVNULL
        assert kwargs["env"] == {"PATH": os.defpath, "LANG": "C.UTF-8", "PYTHONUNBUFFERED": "1"}
        process = real_popen(command, **kwargs)
        owned.append(process)
        return process

    monkeypatch.setattr(subprocess, "Popen", start)
    yield lambda mode, amount=0: [sys.executable, str(script), mode, str(amount)]
    for process in owned:
        if process.returncode is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=5)
        if process.stdout is not None:
            process.stdout.close()


def _run(tmp_path, fake_program, mode, amount=0, *, cap=3):
    tmp_path.mkdir(parents=True, exist_ok=True)
    root = tmp_path / "state"
    result = adapter.run_task(
        gate.TASK_IDS[0], fake_program(mode, amount), root,
        execution_enabled=True, execution_config={"tool_calls_per_task": cap},
    )
    disk = json.loads((root / gate.TASK_IDS[0] / "execution-receipt.json").read_text())
    assert disk == result
    serialized = json.dumps(result)
    assert CANARY not in serialized and str(tmp_path) not in serialized
    assert result["usage"] is result["cost"] is result["grade"] is None
    assert result["usage_status"] == result["cost_status"] == "not available"
    for key in ("paid_execution_allowed", "retry_allowed", "ghcp_command_binding_verified",
                "live_source_verified", "stream_completeness_verified", "pre_effect_limits_verified"):
        assert result[key] is False
    assert result["limits"]["timeout_seconds"] == 1200
    assert result["limits"]["max_turns"] == 64
    assert result["limits"]["max_tool_calls"] == cap
    assert result["cleanup"]["status"] == "group_signalled_leader_reaped"
    assert result["cleanup"]["leader_reaped"] is True
    assert result["cleanup"]["stdout_closed"] is True
    files = root / gate.TASK_IDS[0] / "private" / "files"
    assert (files / "partial.txt").read_text() == CANARY
    return result, files


def test_execution_is_disabled_by_default_before_any_effect(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("default-disabled adapter crossed a pre-launch boundary")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(gate, "check_selection", forbidden)
    monkeypatch.setattr(gate, "fixed_task_ids", forbidden)
    result = adapter.run_task(gate.TASK_IDS[0], [], tmp_path / "state")
    assert result["reason_codes"] == ["execution_disabled"]
    assert result["subprocess_started"] is False
    assert not (tmp_path / "state").exists()


@pytest.mark.parametrize("flag", [False, None, "true", 1])
def test_nontrue_execution_flags_refuse(tmp_path, monkeypatch, flag):
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: pytest.fail("disabled process launch"))
    result = adapter.run_task(gate.TASK_IDS[0], [], tmp_path / "state",
                              execution_enabled=flag, execution_config={"tool_calls_per_task": 3})
    assert result["reason_codes"] == ["execution_disabled"]
    assert not (tmp_path / "state").exists()


@pytest.mark.parametrize("config,reason", [
    (None, "tool_call_cap_missing"), ({}, "tool_call_cap_missing"),
    ({"tool_calls_per_task": None}, "tool_call_cap_missing"),
    *[({"tool_calls_per_task": value}, "tool_call_cap_invalid")
      for value in (0, -1, True, False, "3", 3.0, [], 2**31)],
    ([], "tool_call_cap_invalid"),
])
def test_tool_cap_is_required_before_launch(tmp_path, monkeypatch, config, reason):
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: pytest.fail("missing cap launched"))
    monkeypatch.setattr(gate, "check_selection", lambda *a, **k: pytest.fail("missing cap read configuration"))
    result = adapter.run_task(gate.TASK_IDS[0], [], tmp_path / "state",
                              execution_enabled=True, execution_config=config)
    assert result["reason_codes"] == [reason]
    assert result["subprocess_started"] is False
    assert not (tmp_path / "state").exists()


@pytest.mark.parametrize("kwargs,reason", [
    ({"model": "auto"}, "auto_model_refused"),
    ({"model": CANARY}, "model_selection_refused"),
    ({"byok": True}, "custom_provider_refused"),
    ({"provider_config": CANARY}, "custom_provider_refused"),
])
def test_adapter_preserves_auto_byok_refusal(tmp_path, monkeypatch, kwargs, reason):
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: pytest.fail("routing refusal launched"))
    result = adapter.run_task(gate.TASK_IDS[0], [], tmp_path / "state", execution_enabled=True,
                              execution_config={"tool_calls_per_task": 3}, **kwargs)
    assert result["reason_codes"] == [reason]
    assert CANARY not in json.dumps(result)
    assert not (tmp_path / "state").exists()


@pytest.mark.parametrize("count", [63, 64, 65])
def test_turn_boundary_with_real_fake_process(tmp_path, fake_program, count):
    result, _ = _run(tmp_path, fake_program, "turns", count)
    assert result["limits"]["observed_turn_starts"] == count
    assert result["reason_codes"] == (["turn_cap_exceeded"] if count == 65 else [])
    assert result["exit_status"] == (2 if count == 65 else 0)


@pytest.mark.parametrize("cap,count", [(1, 0), (1, 1), (1, 2), (3, 2), (3, 3), (3, 4)])
def test_tool_boundary_uses_only_explicit_setting(tmp_path, fake_program, cap, count):
    result, _ = _run(tmp_path, fake_program, "tools", count, cap=cap)
    assert result["limits"]["observed_tool_starts"] == count
    assert result["reason_codes"] == (["tool_call_cap_exceeded"] if count > cap else [])
    assert result["exit_status"] == (2 if count > cap else 0)


def test_subagents_are_counted_without_publishing_identities(tmp_path, fake_program):
    result, _ = _run(tmp_path, fake_program, "mixed_agents")
    assert result["reason_codes"] == []
    assert result["limits"]["observed_turn_starts"] == 2
    assert result["limits"]["observed_tool_starts"] == 2


@pytest.mark.parametrize("mode,reason", [
    ("duplicate_turn", "turn_count_unverified"), ("bad_turn", "turn_count_unverified"),
    ("duplicate_tool", "tool_call_count_unverified"), ("bad_tool", "tool_call_count_unverified"),
    ("unbound_tool", "tool_call_count_unverified"), ("bad_agent", "tool_call_count_unverified"),
    ("malformed", "session_event_stream_refused"), ("duplicate_json", "session_event_stream_refused"),
    ("oversize", "session_event_stream_refused"), ("nan", "session_event_stream_refused"),
    ("missing_turn", "turn_count_unverified"), ("wrong_model", "served_model_mismatch"),
    ("empty", "served_model_unverified"), ("nonzero", "subprocess_exit_nonzero"),
])
def test_stream_and_exit_failures_keep_safe_partial_receipt(tmp_path, fake_program, mode, reason):
    result, _ = _run(tmp_path, fake_program, mode)
    assert result["status"] == "failed"
    assert result["exit_status"] == 2
    assert reason in result["reason_codes"]


@pytest.mark.parametrize("elapsed", [1199.0, 1200.0, 1201.0])
def test_deadline_boundary_has_a_fixed_clock_origin(tmp_path, fake_program, monkeypatch, elapsed):
    now = [1000.0]
    original = adapter._count_start

    def count(event, *args):
        original(event, *args)
        if event["type"] == "fixture.clock":
            now[0] = 1000.0 + elapsed

    monkeypatch.setattr(adapter, "monotonic", lambda: now[0])
    monkeypatch.setattr(adapter, "_count_start", count)
    result, _ = _run(tmp_path, fake_program, "clock")
    assert result["elapsed_seconds"] == elapsed
    assert result["reason_codes"] == (["task_timeout_exceeded"] if elapsed >= 1200 else [])


def _accelerate_after_ready(monkeypatch):
    # Keep 1200 unchanged; accelerate only the fixture clock after process setup.
    ready_at = []
    original = adapter._count_start

    def count(event, *args):
        original(event, *args)
        if event["type"] == "session.start" and not ready_at:
            ready_at.append(time.monotonic())

    monkeypatch.setattr(adapter, "_count_start", count)
    monkeypatch.setattr(adapter, "monotonic", lambda: 1000.0 if not ready_at else
                        1000.0 + (time.monotonic() - ready_at[0]) * 4000)


@pytest.mark.parametrize("mode", ["hang", "split_line_hang", "closed_pipe_hang"])
def test_wall_clock_stops_blocked_or_closed_stdout(tmp_path, fake_program, monkeypatch, mode):
    _accelerate_after_ready(monkeypatch)
    result, _ = _run(tmp_path, fake_program, mode)
    assert result["reason_codes"] == ["task_timeout_exceeded"]
    assert result["elapsed_seconds"] >= 1200
    assert result["session_event_receipt"]["observed_usage_events"] == 1


def _not_running(pid):
    try:
        # Only known synthetic PIDs; a zombie has exited, but is not called reaped.
        state = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
        return state in {"Z", "X"}
    except FileNotFoundError:
        return True


@pytest.mark.parametrize("mode,amount,reason", [
    ("tree_turn_cap", 65, "turn_cap_exceeded"),
    ("tree_tool_cap", 4, "tool_call_cap_exceeded"),
    ("tree_timeout", 0, "task_timeout_exceeded"),
    ("tree_timeout_stubborn", 0, "task_timeout_exceeded"),
    ("tree_leader_exit", 0, None),
])
def test_owned_child_and_grandchild_group_cleanup(tmp_path, fake_program, monkeypatch, mode, amount, reason):
    if "timeout" in mode:
        _accelerate_after_ready(monkeypatch)
    result, files = _run(tmp_path, fake_program, mode, amount)
    assert result["reason_codes"] == ([] if reason is None else [reason])
    assert "TERM" in result["cleanup"]["signals_sent"]
    assert "KILL" in result["cleanup"]["signals_sent"]
    # SIGKILL delivery and scheduler exit are asynchronous. This bounded fixture
    # wait is not an adapter retry; no new runtime is launched.
    pids = [int((files / f"{role}.pid").read_text()) for role in ("leader", "child", "grandchild")]
    until = time.monotonic() + 2
    while not all(_not_running(pid) for pid in pids) and time.monotonic() < until:
        time.sleep(0.01)
    assert all(_not_running(pid) for pid in pids)
    assert result["cleanup"]["leader_reaped"] is True


def test_stderr_and_environment_never_enter_receipt(tmp_path, fake_program, monkeypatch, capsys):
    monkeypatch.setenv("HF_TOKEN", CANARY)  # Synthetic, never inspect an existing value.
    result, _ = _run(tmp_path, fake_program, "stderr_flood")
    assert result["status"] == "completed_process_only"
    assert result["session_event_receipt"]["calls"][0]["model"] == gate.SOL_MODEL
    assert result["session_event_receipt"]["evidence_level"] == "settings_only"
    assert capsys.readouterr() == ("", "")


def test_fresh_attempt_counters_and_no_local_reuse(tmp_path, fake_program):
    first, _ = _run(tmp_path / "one", fake_program, "tools", 3)
    second, _ = _run(tmp_path / "two", fake_program, "tools", 3)
    assert first["limits"]["observed_tool_starts"] == second["limits"]["observed_tool_starts"] == 3
    path = tmp_path / "one" / "state" / gate.TASK_IDS[0] / "execution-receipt.json"
    original = path.read_bytes()
    refused = adapter.run_task(gate.TASK_IDS[0], fake_program("tools", 3), tmp_path / "one" / "state",
                               execution_enabled=True, execution_config={"tool_calls_per_task": 3})
    assert refused["reason_codes"] == ["execution_state_refused"]
    assert refused["subprocess_started"] is False
    assert path.read_bytes() == original


def test_start_failure_has_receipt_and_no_raw_exception(tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        raise OSError(CANARY)

    monkeypatch.setattr(subprocess, "Popen", fail)
    root = tmp_path / "state"
    result = adapter.run_task(gate.TASK_IDS[0], [sys.executable], root,
                              execution_enabled=True, execution_config={"tool_calls_per_task": 3})
    assert result["reason_codes"] == ["subprocess_start_failed"]
    assert result["cleanup"]["status"] == "not_started"
    assert result["subprocess_started"] is False
    assert json.loads((root / gate.TASK_IDS[0] / "execution-receipt.json").read_text()) == result
    assert CANARY not in json.dumps(result)


@pytest.mark.parametrize("command", [[], "copilot", ["copilot"], ["/no/such/program", "\0"]])
def test_argv_validation_refuses_before_launch(tmp_path, monkeypatch, command):
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: pytest.fail("invalid argv launched"))
    result = adapter.run_task(gate.TASK_IDS[0], command, tmp_path / "state",
                              execution_enabled=True, execution_config={"tool_calls_per_task": 3})
    assert result["reason_codes"] == ["execution_command_refused"]
    assert not (tmp_path / "state").exists()


def test_existing_timer_is_not_stolen_or_followed_by_spawn(tmp_path, monkeypatch):
    monkeypatch.setattr(signal, "getitimer", lambda *a: (10.0, 0.0))
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: pytest.fail("unowned timer launched"))
    result = adapter.run_task(gate.TASK_IDS[0], [sys.executable], tmp_path / "state",
                              execution_enabled=True, execution_config={"tool_calls_per_task": 3})
    assert result["reason_codes"] == ["task_timeout_guard_unavailable"]
    assert not (tmp_path / "state").exists()
