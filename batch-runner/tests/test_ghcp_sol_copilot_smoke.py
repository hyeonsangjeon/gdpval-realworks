"""Pinned fake executables only; no installed CLI, credentials or network."""

import hashlib
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

CANARY = "SYNTHETIC_PRIVATE_SMOKE_CANARY"
PROGRAM = r'''
import json, os, signal, subprocess, sys
from pathlib import Path
mode = MODE
turns = TURNS
tools = TOOLS
canary = "SYNTHETIC_PRIVATE_SMOKE_CANARY"
args = sys.argv[1:]
assert args[args.index("-p") + 1] == "Reply with exactly CONNECTED"
assert args[args.index("--model") + 1] == "gpt-5.6-sol"
assert args[args.index("--reasoning-effort") + 1] == "max"
assert args[args.index("--context") + 1] == "long_context"
assert args[args.index("--output-format") + 1] == "json"
assert args[args.index("--available-tools") + 1] == "--deny-tool=shell"
for flag in ("--no-auto-update", "--disable-client-telemetry", "--no-custom-instructions",
             "--disable-builtin-mcps", "--allow-all-tools", "--deny-tool=write", "--disallow-temp-dir"):
    assert flag in args
assert "COPILOT_ALLOW_ALL" not in os.environ
assert "AZURE_OPENAI_API_KEY" not in os.environ
assert "HF_TOKEN" not in os.environ
assert "COPILOT_PROVIDER_BASE_URL" not in os.environ
locations = {name: os.environ[name] for name in (
    "HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "TMPDIR",
)}
assert len(set(locations.values())) == 6
assert all(Path(value).is_dir() for value in locations.values())
assert all(Path(value).parent == Path.cwd().parent for value in locations.values())
Path("isolation-proof.json").write_text(json.dumps(locations))
Path("leader.pid").write_text(str(os.getpid()))
if mode == "auth":
    print("No authentication information found " + canary, file=sys.stderr, flush=True)
    raise SystemExit(1)
if mode == "auth_check":
    assert os.environ.get("COPILOT_GITHUB_TOKEN") == canary
    assert "GH_TOKEN" not in os.environ and "GITHUB_TOKEN" not in os.environ
if mode == "tree":
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    child = r"""
import os, signal, subprocess, sys
from pathlib import Path
signal.signal(signal.SIGTERM, signal.SIG_IGN)
Path('child.pid').write_text(str(os.getpid()))
grand = subprocess.Popen([sys.executable, '-c', "import os,signal; from pathlib import Path; signal.signal(signal.SIGTERM, signal.SIG_IGN); Path('grandchild.pid').write_text(str(os.getpid())); signal.pause()"])
signal.pause()
"""
    subprocess.Popen([sys.executable, "-c", child])
usage_path = Path(args[args.index("--usage-output-file") + 1])
if mode == "usage_symlink":
    Path("private-canary.json").write_text(json.dumps({"inputTokens": 999}))
    usage_path.symlink_to(Path.cwd() / "private-canary.json")
elif mode == "usage_duplicate":
    usage_path.write_text('{"inputTokens":1,"inputTokens":2}')
elif mode == "timing_only":
    usage_path.write_text(json.dumps({"totalApiDurationMs": 0, "totalSessionDurationMs": 17}))
elif mode != "no_usage":
    usage_path.write_text(json.dumps({"inputTokens": 4, "outputTokens": 1,
                                      "headers": {"Authorization": canary}, "files": [canary]}))
def emit(kind, data, **more):
    print(json.dumps({"type": kind, "data": data, **more}), flush=True)
emit("session.start", {"sessionId": "synthetic-session", "selectedModel": "gpt-5.6-sol"})
context = {"tokenLimit": 1000000}
if mode == "context_alternative":
    context = {"modelContextWindow": 1000000}
if mode == "context_mismatch":
    context["tokenLimit"] = 258400
if mode != "missing_context":
    emit("session.usage_info", context)
for index in range(turns):
    emit("assistant.turn_start", {"turnId": str(index)})
for index in range(tools):
    emit("tool.execution_start", {"toolCallId": str(index), "arguments": canary})
emit("assistant.message", {"content": "CONNECTED"})
data = {"model": "gpt-5.6-sol", "reasoningEffort": "max", "prompt": canary}
if mode not in {"no_usage", "timing_only"}:
    data.update(inputTokens=4, outputTokens=1)
if mode == "model_mismatch":
    data["model"] = "gpt-5.4"
if mode == "missing_model":
    del data["model"]
if mode == "missing_effort":
    del data["reasoningEffort"]
if mode == "effort_mismatch":
    data["reasoningEffort"] = "high"
if mode != "missing_events":
    emit("assistant.usage", data, id="call-1")
if mode == "second_mismatch":
    emit("assistant.usage", dict(data, model="gpt-5.4"), id="call-2")
if mode in {"hang", "tree"}:
    signal.pause()
if mode != "missing_result":
    print(json.dumps({"type": "result", "timestamp": "2026-10-26T00:00:00Z",
        "sessionId": "synthetic-session", "exitCode": 0,
        "usage": {} if mode == "no_usage" else {"totalApiDurationMs": 0} if mode == "timing_only"
                 else {"inputTokens": 4, "outputTokens": 1}}), flush=True)
'''


@pytest.fixture(autouse=True)
def offline_only(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "synthetic-parent-home")

    def forbidden(*args, **kwargs):
        pytest.fail("offline smoke test attempted network or external execution")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(os, "system", forbidden)


@pytest.fixture
def fake_cli(tmp_path, monkeypatch):
    real_popen = subprocess.Popen
    programs = set()
    owned = []

    def spawn(command, **kwargs):
        assert command[0] in programs, "an installed CLI or other command was attempted"
        assert kwargs["stdin"] == subprocess.DEVNULL
        assert kwargs["start_new_session"] is True
        process = real_popen(command, **kwargs)
        owned.append(process)
        return process

    monkeypatch.setattr(subprocess, "Popen", spawn)

    def create(mode="normal", *, turns=1, tools=0):
        path = tmp_path / f"fake-cli-{len(programs)}"
        text = f"#!{sys.executable}\n" + PROGRAM.replace("MODE", repr(mode)).replace("TURNS", str(turns)).replace("TOOLS", str(tools))
        path.write_text(text)
        path.chmod(0o700)
        monkeypatch.setattr(adapter, "COPILOT_CLI_SHA256", hashlib.sha256(path.read_bytes()).hexdigest())
        programs.add(str(path))
        return path

    yield create
    for process in owned:
        if process.returncode is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=5)
        for stream in (process.stdout, process.stderr):
            if stream is not None:
                stream.close()


def run_fake(tmp_path, fake_cli, mode="normal", *, turns=1, tools=0):
    root = tmp_path / "capture"
    receipt = adapter.run_copilot_smoke(
        fake_cli(mode, turns=turns, tools=tools), root, execution_enabled=True,
    )
    disk = json.loads((root / adapter.SMOKE_TASK_ID / "execution-receipt.json").read_text())
    assert disk == receipt
    assert CANARY not in json.dumps(receipt)
    assert str(tmp_path) not in json.dumps(receipt)
    assert receipt["row_name"] == "GHCP Copilot CLI agent + GPT-5.6 Sol"
    assert receipt["five_task_gate_allowed"] is receipt["full_220_allowed"] is False
    assert receipt["limits"]["max_tool_calls"] == 32
    assert receipt["limits"]["timeout_seconds"] == 1200
    assert receipt["limits"]["max_turns"] == 64
    assert receipt["cleanup"]["leader_reaped"] is True
    assert receipt["cleanup"]["stdout_closed"] is True
    assert receipt["cleanup"]["stderr_closed"] is True
    assert receipt["session_event_receipt"]["applied_settings_verified"] is False
    return receipt, root / adapter.SMOKE_TASK_ID / "private"


def test_smoke_disabled_before_binary_auth_or_files(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("disabled smoke crossed an execution boundary")

    monkeypatch.setattr(adapter, "_verify_copilot_binary", forbidden)
    monkeypatch.setattr(adapter, "_smoke_environment", forbidden)
    result = adapter.run_copilot_smoke(tmp_path / "unread", tmp_path / "capture")
    assert result["reason_codes"] == ["execution_disabled"]
    assert result["subprocess_started"] is False
    assert not (tmp_path / "capture").exists()


@pytest.mark.parametrize("variant", ["missing", "drift", "symlink"])
def test_smoke_pins_actual_installed_bytes_before_launch(tmp_path, fake_cli, variant):
    binary = fake_cli()
    if variant == "missing":
        binary = tmp_path / "missing"
    elif variant == "drift":
        binary.write_text("changed, not executed")
    else:
        link = tmp_path / "link"
        link.symlink_to(binary)
        binary = link
    receipt = adapter.run_copilot_smoke(binary, tmp_path / "capture", execution_enabled=True)
    assert receipt["reason_codes"] == ["copilot_binary_unverified"]
    assert not (tmp_path / "capture").exists()


@pytest.mark.parametrize("task_id", gate.TASK_IDS)
def test_bound_route_cannot_start_any_of_the_five_tasks(tmp_path, fake_cli, task_id):
    receipt = adapter.run_task(task_id, [], tmp_path / "capture", execution_enabled=True,
                               execution_config={"tool_calls_per_task": 32}, copilot_cli=fake_cli())
    assert receipt["reason_codes"] == ["copilot_smoke_scope_refused"]
    assert receipt["subprocess_started"] is False


@pytest.mark.parametrize("mode", ["normal", "context_alternative", "no_usage", "auth_check", "timing_only"])
def test_fixed_command_isolation_original_fields_and_usage(tmp_path, fake_cli, monkeypatch, mode):
    monkeypatch.setenv("COPILOT_GITHUB_TOKEN", CANARY)
    monkeypatch.setenv("GH_TOKEN", "SHOULD_NOT_BE_COPIED")
    monkeypatch.setenv("GITHUB_TOKEN", "SHOULD_NOT_BE_COPIED")
    monkeypatch.setenv("HF_TOKEN", "SHOULD_NOT_BE_COPIED")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "SHOULD_NOT_BE_COPIED")
    receipt, private = run_fake(tmp_path, fake_cli, mode)
    assert receipt["exit_status"] == 0 and receipt["reason_codes"] == []
    assert receipt["settings_verification"] == "verified"
    assert receipt["observed_event_fields"] == [{
        "model": "gpt-5.6-sol", "reasoningEffort": "max",
        "tokenLimit": None if mode == "context_alternative" else 1000000,
        "modelContextWindow": 1000000 if mode == "context_alternative" else None,
    }]
    assert receipt["smoke_reply_exact"] is True
    if mode in {"no_usage", "timing_only"}:
        assert receipt["usage"] is None and receipt["usage_status"] == "not available"
    else:
        assert receipt["usage"]["usage_output_file"] == {"inputTokens": 4, "outputTokens": 1}
        assert receipt["usage"]["result.usage"] == {"inputTokens": 4, "outputTokens": 1}
        assert receipt["usage"]["assistant.usage"] == [{"inputTokens": 4, "outputTokens": 1}]
    assert (private / "files" / "isolation-proof.json").is_file()


@pytest.mark.parametrize("mode,reason", [
    ("model_mismatch", "served_model_mismatch"), ("second_mismatch", "served_model_mismatch"),
    ("missing_model", "served_model_unverified"), ("missing_effort", "reasoning_effort_unverified"),
    ("effort_mismatch", "reasoning_effort_mismatch"), ("context_mismatch", "context_limit_mismatch"),
    ("missing_context", "context_limit_unverified"), ("missing_events", "served_model_unverified"),
    ("missing_result", "cli_result_unverified"), ("auth", "copilot_authentication_failed"),
    ("usage_symlink", "usage_output_file_refused"), ("usage_duplicate", "usage_output_file_refused"),
])
def test_smoke_missing_or_conflicting_evidence_refuses(tmp_path, fake_cli, mode, reason):
    receipt, _ = run_fake(tmp_path, fake_cli, mode)
    assert receipt["exit_status"] == 2 and reason in receipt["reason_codes"]
    assert receipt["settings_verification"] == "unverified"
    assert receipt["metadata_gate_passed"] is False
    if mode in {"model_mismatch", "second_mismatch"}:
        assert receipt["observed_event_fields"][-1]["model"] == "gpt-5.4"
    if mode == "context_mismatch":
        assert receipt["observed_event_fields"][0]["tokenLimit"] == 258400
    if mode == "auth":
        assert receipt["diagnostic"]["message"] == "No authentication information found"
        assert receipt["observed_event_fields"] == []


@pytest.mark.parametrize("turns,tools,reason", [
    (63, 31, None), (64, 32, None), (65, 0, "turn_cap_exceeded"),
    (1, 33, "tool_call_cap_exceeded"),
])
def test_bound_cli_limit_boundaries(tmp_path, fake_cli, turns, tools, reason):
    receipt, _ = run_fake(tmp_path, fake_cli, turns=turns, tools=tools)
    if reason is None:
        assert receipt["exit_status"] == 0
    else:
        assert receipt["exit_status"] == 2 and reason in receipt["reason_codes"]


@pytest.mark.parametrize("mode", ["hang", "tree"])
def test_bound_timeout_cleans_process_group_and_stderr(tmp_path, fake_cli, monkeypatch, mode):
    real_clock = time.monotonic
    origin = real_clock()
    # Keep the 1,200-second policy unchanged; only the fixture clock advances.
    monkeypatch.setattr(adapter, "monotonic", lambda: (real_clock() - origin) * 2400)
    receipt, private = run_fake(tmp_path, fake_cli, mode)
    assert receipt["exit_status"] == 2 and "task_timeout_exceeded" in receipt["reason_codes"]
    assert receipt["elapsed_seconds"] >= 1200
    for name in ("leader", "child", "grandchild") if mode == "tree" else ("leader",):
        pid = int((private / "files" / f"{name}.pid").read_text())
        proc = Path(f"/proc/{pid}/stat")
        if proc.exists():
            assert proc.read_text().split(")", 1)[1].split()[0] == "Z"


@pytest.mark.parametrize("context", [
    {"tokenLimit": 1000000, "modelContextWindow": 258400},
    {"tokenLimit": "1000000", "modelContextWindow": 1000000},
    {"tokenLimit": True}, {"tokenLimit": "1000000"}, {},
])
def test_runtime_projection_never_infers_or_coerces_context(context):
    receipt = gate.collect_session_events([
        {"type": "session.usage_info", "data": context},
        {"type": "assistant.usage", "id": "one", "data": {
            "model": gate.SOL_MODEL, "reasoningEffort": "max", "headers": CANARY,
        }},
    ], runtime_projection=True)
    assert receipt["status"] == "failed"
    assert receipt["calls"][0]["verification"] == "unverified"
    assert CANARY not in json.dumps(receipt)


def test_usage_projection_preserves_reported_zero_but_never_invents_it():
    assert gate.reported_usage({}) is None
    assert gate.reported_usage({"totalApiDurationMs": 0, "totalSessionDurationMs": 17}) is None
    assert gate.reported_usage({"inputTokens": True, "outputTokens": "5"}) is None
    assert gate.reported_usage({"inputTokens": 0, "outputTokens": 2, "Authorization": CANARY}) == {
        "inputTokens": 0, "outputTokens": 2,
    }


def test_isolated_smoke_does_not_reuse_a_task_directory(tmp_path, fake_cli):
    binary = fake_cli()
    first = adapter.run_copilot_smoke(binary, tmp_path / "one", execution_enabled=True)
    before = (tmp_path / "one" / adapter.SMOKE_TASK_ID / "execution-receipt.json").read_bytes()
    repeated = adapter.run_copilot_smoke(binary, tmp_path / "one", execution_enabled=True)
    assert first["exit_status"] == 0
    assert repeated["subprocess_started"] is False
    assert repeated["reason_codes"] == ["execution_state_refused"]
    assert (tmp_path / "one" / adapter.SMOKE_TASK_ID / "execution-receipt.json").read_bytes() == before
    other = adapter.run_copilot_smoke(binary, tmp_path / "two", execution_enabled=True)
    assert other["exit_status"] == 0
    assert (tmp_path / "one" / adapter.SMOKE_TASK_ID / "private" / "home") != (
        tmp_path / "two" / adapter.SMOKE_TASK_ID / "private" / "home"
    )
