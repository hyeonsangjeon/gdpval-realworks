"""Synthetic AHP event streams only; no host, process, network or credentials."""

import base64
import copy
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import threading

import pytest
import yaml

import ghcp_ahp_client as client

ROOT = Path(__file__).resolve().parents[2]
SESSION, CHAT = "ahp-session:/fixture", "ahp-chat:/fixture"
CANARY = "SYNTHETIC_AHP_CREDENTIAL_0123456789"


@pytest.fixture(autouse=True)
def offline_only(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("fixture attempted real process or network")
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)


class Clock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        return self.value


class FakePort:
    def __init__(self, clock, stream=()):
        self.clock, self.stream = clock, iter(stream)
        self.sent, self.stopped = [], 0
        self.send_error = self.kill_error = False
        self.kill_result = True

    def send(self, message, timeout):
        assert 0 < timeout <= client.CONTROL_TIMEOUT_SECONDS
        self.sent.append(copy.deepcopy(message))
        if self.send_error:
            raise RuntimeError(CANARY)

    def receive(self, timeout):
        assert 0 < timeout <= client.POLL_SECONDS
        value = next(self.stream, None)
        if value is None:
            self.clock.value += timeout
            raise TimeoutError
        return value

    def terminate(self, timeout):
        assert timeout == client.TERMINATE_TIMEOUT_SECONDS
        self.stopped += 1
        if self.kill_error:
            raise RuntimeError(CANARY)
        return self.kill_result


def setup(*, limits=client.Limits(), authenticated=True, stream=()):
    clock = Clock()
    port = FakePort(clock, stream)
    session = client.SessionClient(port, SESSION, CHAT, authenticated=authenticated,
                                   limits=limits, clock=clock, credential=CANARY)
    return session, port, clock


def event(seq, kind, *, channel=CHAT, **fields):
    return {"jsonrpc": "2.0", "method": "action", "params": {
        "channel": channel, "serverSeq": seq, "origin": None, "action": {"type": kind, **fields}}}


def start(session, turn="turn1", seq=1):
    assert session.send_turn(turn, "synthetic input")
    return session.accept(event(seq, "chat/turnStarted", turnId=turn,
                                message={"text": "synthetic input", "model": client.DESIRED_MODEL}))


def finish(session, turn="turn1", seq=100):
    session.accept(event(seq, "chat/turnComplete", turnId=turn, duration=12))
    session.finish()


def work_messages(port):
    return [message for message in port.sent if message.get("params", {}).get("action", {}).get("type") == "chat/turnStarted"]


@pytest.mark.parametrize("field,maximum", [("turns", 64), ("tool_calls", 32), ("seconds", 1200)])
@pytest.mark.parametrize("kind", ["zero", "negative", "bool", "float", "str", "relaxed"])
def test_invalid_or_relaxed_limits_refuse(field, maximum, kind):
    value = {"zero": 0, "negative": -1, "bool": True, "float": 1.0, "str": "1", "relaxed": maximum + 1}[kind]
    with pytest.raises(client.Refused, match="invalid_client_limits"):
        client.Limits(**{field: value})


def test_default_limits_and_bound_are_exact_not_premium_request_claims():
    record = client.draft_receipt()
    assert record["limits"] == {"turns": 64, "tool_calls": 32, "seconds": 1200}
    assert record["overshoot_boundary"]["client_work_notifications_after_stop"] == 0
    assert record["overshoot_boundary"]["already_admitted_client_turns"] == 1
    assert record["overshoot_boundary"]["server_internal_model_requests"] == "no_finite_bound_proven"
    assert record["reason_codes"] == ["ahp_paid_contract_unverified"]
    assert record["model_calls"] == 0 and not record["launch_allowed"] and not record["gate_ready"]


def test_turn_65_never_reaches_transport_even_when_echo_is_missing(tmp_path):
    session, port, _ = setup()
    for i in range(64):
        assert session.send_turn(f"turn{i}", "fixture")
        if i < 63:
            session.accept(event(i + 1, "chat/turnComplete", turnId=f"turn{i}", duration=1))
    assert len(work_messages(port)) == 64
    assert session.reason == "turn_limit_reached"
    assert not session.send_turn("turn65", "fixture")
    assert len(work_messages(port)) == 64
    record = session.capture(tmp_path / "capture.json")
    assert record["counts"]["admitted_or_observed_turns"] == 64
    assert record["counts"]["observed_turns"] == 0
    assert record["cleanup"]["cancel_attempts"] == record["cleanup"]["dispose_attempts"] == 1


@pytest.mark.parametrize("tool_cap", [1, 2, 32])
def test_tool_limit_closes_before_another_client_request(tool_cap, tmp_path):
    session, port, _ = setup(limits=client.Limits(tool_calls=tool_cap))
    start(session)
    for i in range(tool_cap):
        session.accept(event(i + 2, "chat/toolCallStart", turnId="turn1", toolCallId=f"tool{i}", toolName="fixture"))
    assert session.reason == "tool_limit_reached"
    before = len(work_messages(port))
    assert not session.send_turn("turn2", "fixture") and len(work_messages(port)) == before
    # A late server event is NOT prevented by a client-side counter.
    session.accept(event(tool_cap + 3, "chat/toolCallStart", turnId="turn1", toolCallId="late", toolName="fixture"))
    record = session.capture(tmp_path / "capture.json")
    assert record["observed_overshoot"]["tool_calls"] == 1
    assert record["counts"]["model_requests"] == record["counts"]["premium_requests"] == "not_reported"
    assert port.stopped == 1


@pytest.mark.parametrize("elapsed", [1200, 1200.001, 9999])
def test_deadline_is_checked_before_work_even_without_events(elapsed):
    session, port, clock = setup()
    clock.value = elapsed
    assert not session.send_turn("t", "fixture")
    assert not work_messages(port) and session.reason == "time_limit_reached"


def test_just_below_deadline_can_send_but_idle_stream_still_stops():
    session, port, clock = setup()
    clock.value = 1199.99
    assert session.send_turn("t", "fixture")
    session.run()
    assert session.reason == "time_limit_reached" and port.stopped == 1
    assert len(work_messages(port)) == 1


def test_independent_watchdog_terminates_even_if_receive_waits_without_events():
    unblocked = threading.Event()
    entered = threading.Event()
    class SilentPort:
        def send(self, message, timeout):
            pass
        def receive(self, timeout):
            entered.set()
            assert unblocked.wait(4), "deadline did not request host termination"
            raise TimeoutError
        def terminate(self, timeout):
            unblocked.set()
            return True
    session = client.SessionClient(SilentPort(), SESSION, CHAT, authenticated=True,
                                   limits=client.Limits(seconds=1))
    assert session.send_turn("t", "fixture")
    session.run()
    assert entered.is_set() and unblocked.is_set()
    assert session.reason == "time_limit_reached" and session.cleanup["host_terminated"] is True


def test_limit_state_is_closed_before_cancel_transport_is_called():
    session, port, _ = setup(limits=client.Limits(turns=1))
    original = port.send
    checked = []
    def callback(message, timeout):
        if message.get("params", {}).get("action", {}).get("type") == "chat/turnCancelled":
            checked.append(not session.send_turn("reentrant", "must not send"))
        original(message, timeout)
    port.send = callback
    assert session.send_turn("t", "fixture")
    assert checked == [True] and len(work_messages(port)) == 1


def test_cancel_duration_is_local_active_turn_time_not_whole_session_time():
    session, port, clock = setup(limits=client.Limits(seconds=20))
    clock.value = 19
    assert session.send_turn("t", "fixture")
    clock.value = 20
    assert not session.tick()
    action = next(message["params"]["action"] for message in port.sent
                  if message.get("params", {}).get("action", {}).get("type") == "chat/turnCancelled")
    assert action["duration"] == 1000


def test_concurrent_client_requests_cannot_create_two_active_turns():
    session, port, _ = setup()
    barrier = threading.Barrier(3)
    results = []
    def send(turn):
        barrier.wait(timeout=2)
        results.append(session.send_turn(turn, "fixture"))
    workers = [threading.Thread(target=send, args=(f"t{i}",)) for i in range(2)]
    for worker in workers:
        worker.start()
    barrier.wait(timeout=2)
    for worker in workers:
        worker.join(timeout=2)
        assert not worker.is_alive()
    assert sorted(results) == [False, True] and len(work_messages(port)) == 1


@pytest.mark.parametrize("authenticated", [False, True])
def test_auth_error_and_missing_auth_never_send_or_retry_model_work(authenticated):
    session, port, _ = setup(authenticated=authenticated)
    if authenticated:
        session.accept({"jsonrpc": "2.0", "id": 2, "error": {"code": -32007, "message": CANARY}})
    assert not session.send_turn("t", "fixture")
    assert not work_messages(port) and session.reason == "authentication_required"
    assert all(message["method"] != "authenticate" for message in port.sent)


def test_event_replay_and_multiple_tool_phases_count_once():
    session, _, _ = setup()
    start(session)
    opening = event(2, "chat/toolCallStart", turnId="turn1", toolCallId="x", toolName="fixture")
    assert session.accept(opening) and session.accept(copy.deepcopy(opening))
    assert session.accept(event(3, "chat/toolCallReady", turnId="turn1", toolCallId="x", toolInput="echo ok", confirmed="not-needed"))
    assert len(session.tools) == 1 and len(session.turns) == 1


@pytest.mark.parametrize("change,reason", [
    ("divergent", "divergent_event_replay"), ("reorder", "event_order_refused"),
    ("bad_seq", "invalid_server_sequence"), ("rejection", "action_rejected"),
    ("foreign_chat", "additional_chat_refused"), ("foreign_session", "foreign_session_refused"),
    ("unknown_turn", "unknown_tool_turn"), ("terminal", "unbound_terminal_refused"),
])
def test_ambiguous_or_foreign_events_fail_closed(change, reason):
    session, port, _ = setup()
    start(session, seq=5)
    value = event(6, "chat/toolCallStart", turnId="turn1", toolCallId="x", toolName="fixture")
    if change == "divergent": value["params"]["serverSeq"] = 5
    if change == "reorder": value["params"]["serverSeq"] = 4
    if change == "bad_seq": value["params"]["serverSeq"] = True
    if change == "rejection": value["params"]["rejectionReason"] = "denied"
    if change == "foreign_chat": value["params"]["channel"] = "ahp-chat:/other"
    if change == "foreign_session": value = event(6, "session/ready", channel="ahp-session:/other")
    if change == "unknown_turn": value["params"]["action"]["turnId"] = "unknown"
    if change == "terminal": value = event(6, "terminal/data", channel="ahp-terminal:/other", data="unknown")
    assert not session.accept(value) and session.reason == reason
    assert port.stopped == 1 and not session.send_turn("later", "fixture")


@pytest.mark.parametrize("kind", ["chat/pendingMessageSet", "chat/turnResume", "chat/backgroundWorkSet", "session/chatAdded"])
def test_queued_resume_and_other_autonomous_work_are_not_implicitly_approved(kind):
    session, _, _ = setup()
    start(session)
    session.accept(event(2, kind, channel=SESSION if kind.startswith("session/") else CHAT))
    assert session.reason == "autonomous_work_refused"


def test_cancel_send_failure_still_terminates_and_does_not_log_error_text(tmp_path):
    session, port, _ = setup(limits=client.Limits(turns=1))
    port.send_error = True
    assert not session.send_turn("t", "fixture")
    record = session.capture(tmp_path / "capture.json")
    assert record["cleanup"]["host_terminated"] is True
    assert record["cleanup"]["control_errors"] == ["control_send_failed", "control_send_failed"]
    assert CANARY not in (tmp_path / "capture.json").read_text()


@pytest.mark.parametrize("failure", ["exception", "false", "not_stopped"])
def test_unconfirmed_cleanup_refuses_file_export(failure, tmp_path):
    session, port, _ = setup()
    start(session)
    if failure != "not_stopped":
        port.kill_error = failure == "exception"
        port.kill_result = False
        finish(session)
    with pytest.raises(client.Refused, match="capture_host_not_stopped"):
        session.capture(tmp_path / "capture.json")
    assert not (tmp_path / "capture.json").exists()


def test_full_delivered_capture_commands_outputs_and_unreported_settings(tmp_path):
    workspace = tmp_path / "work"
    workspace.mkdir()
    (workspace / "input.txt").write_text("unchanged input")
    baseline = {name: hashlib.sha256(raw).hexdigest() for name, raw in client.workspace_files(workspace).items()}
    (workspace / "answer.txt").write_text("synthetic answer")
    (workspace / "binary.bin").write_bytes(b"\xff\x00\x01")
    session, _, _ = setup()
    start(session)
    session.accept(event(2, "chat/responsePart", turnId="turn1", part={"kind": "markdown", "id": "p", "content": ""}))
    session.accept(event(3, "chat/delta", turnId="turn1", partId="p", content="answer"))
    session.accept(event(4, "chat/toolCallStart", turnId="turn1", toolCallId="x", toolName="terminal"))
    session.accept(event(5, "chat/toolCallReady", turnId="turn1", toolCallId="x", toolInput="printf answer", confirmed="not-needed"))
    session.accept(event(6, "chat/toolCallComplete", turnId="turn1", toolCallId="x", result={"success": True, "content": [
        {"type": "fileEdit", "after": {"uri": "file:///work/answer.txt"}},
        {"type": "terminal", "resource": "ahp-terminal:/fixture", "title": "fixture"}]}))
    session.accept(event(7, "terminal/commandExecuted", channel="ahp-terminal:/fixture", commandId="command1", commandLine="printf answer"))
    session.accept(event(8, "terminal/data", channel="ahp-terminal:/fixture", data="answer\n"))
    session.accept(event(9, "terminal/commandFinished", channel="ahp-terminal:/fixture", commandId="command1", exitCode=0))
    finish(session)
    record = session.capture(tmp_path / "capture.json", workspace=workspace, baseline=baseline)
    assert record == json.loads((tmp_path / "capture.json").read_text())
    assert record["status"] == "completed" and not record["gate_ready"]
    assert record["reported"] == {key: "not_reported" for key in session.reported}
    assert len(record["tool_calls"]) == 3 and len(record["commands"]) == 3
    assert len(record["transcript"]["wire"]) == 12
    assert {item["path"] for item in record["generated_files"]} == {"answer.txt", "binary.bin"}
    assert record["reported_file_edits"] and record["workspace_collected"]
    assert (tmp_path / "capture.json").stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        session.capture(tmp_path / "capture.json")


def history_snapshot(*, model=None, cursor=None):
    message = {"text": "fixture"}
    if model is not None:
        message["model"] = model
    return {"jsonrpc": "2.0", "id": 8, "result": {"snapshot": {
        "resource": CHAT, "fromSeq": 2, "state": {"turns": [{"id": "t", "message": message,
        "responseParts": [], "state": "complete"}], "turnsNextCursor": cursor}}}}


def test_historical_model_config_is_reported_but_not_served_attestation(tmp_path):
    session, _, _ = setup()
    assert session.accept(history_snapshot(model=client.DESIRED_MODEL))
    finish(session, "t")
    record = session.capture(tmp_path / "capture.json")
    assert record["reported"]["model_id"] == client.DESIRED_MODEL["id"]
    assert record["reported"]["reasoning_effort"] == "max"
    assert record["reported"]["context_window"] == 1_000_000
    assert record["reported"]["served_model"] == record["reported"]["model_version"] == "not_reported"
    assert record["reported_settings"][0]["source"] == "server_historical_message_model"


@pytest.mark.parametrize("model", [None, {}, {"id": None}, {"config": {"thinkingLevel": None, "contextSize": None}}])
def test_absent_reported_values_are_explicit_not_reported(model):
    session, _, _ = setup()
    assert session.accept(history_snapshot(model=model))
    assert set(session.reported.values()) == {"not_reported"}


@pytest.mark.parametrize("field,value", [("id", "other"), ("thinkingLevel", "low"), ("contextSize", 258400)])
def test_explicit_reported_setting_mismatch_stops(field, value):
    selection = copy.deepcopy(client.DESIRED_MODEL)
    (selection if field == "id" else selection["config"])[field] = value
    session, _, _ = setup()
    assert not session.accept(history_snapshot(model=selection))
    assert session.reason == "reported_setting_mismatch"


def test_unfetched_history_refuses_instead_of_claiming_full_transcript():
    session, _, _ = setup()
    assert not session.accept(history_snapshot(cursor="next-page"))
    assert session.reason == "history_pagination_required"


@pytest.mark.parametrize("source", ["snapshot", "response_part"])
def test_protocol_kind_tool_parts_are_counted_without_start_events(source):
    session, _, _ = setup(limits=client.Limits(tool_calls=1))
    part = {"kind": "toolCall", "toolCall": {"toolCallId": "x", "toolName": "fixture", "status": "completed"}}
    if source == "snapshot":
        value = history_snapshot()
        value["result"]["snapshot"]["state"]["turns"][0]["responseParts"] = [part]
    else:
        start(session)
        value = event(2, "chat/responsePart", turnId="turn1", part=part)
    assert not session.accept(value)
    assert session.reason == "tool_limit_reached" and len(session.tools) == 1


def test_wrong_part_discriminant_is_not_silently_ignored():
    session, _, _ = setup()
    start(session)
    assert not session.accept(event(2, "chat/responsePart", turnId="turn1", part={"type": "toolCall", "toolCall": {"toolCallId": "x"}}))
    assert session.reason == "invalid_response_part"


def test_unresolved_content_reference_is_not_a_complete_transcript():
    session, _, _ = setup()
    start(session)
    assert not session.accept(event(2, "chat/responsePart", turnId="turn1", part={"kind": "contentRef", "uri": "fixture:/large"}))
    assert session.reason == "external_content_not_collected"


def test_embedded_tool_resource_credential_is_masked_before_json_export(tmp_path):
    session, _, _ = setup()
    start(session)
    encoded = base64.b64encode(b"\xff" + CANARY.encode()).decode()
    session.accept(event(2, "chat/toolCallComplete", turnId="turn1", toolCallId="x",
                         result={"success": True, "content": [{"type": "embeddedResource", "data": encoded}]}))
    finish(session)
    session.capture(tmp_path / "capture.json")
    output = (tmp_path / "capture.json").read_text()
    assert encoded not in output and CANARY not in output and "[REDACTED_BINARY]" in output


def test_tool_input_fragments_are_redacted_in_both_wire_and_tool_collection(tmp_path):
    session, _, _ = setup()
    start(session)
    for seq, content in enumerate((CANARY[:9], CANARY[9:]), 2):
        session.accept(event(seq, "chat/toolCallDelta", turnId="turn1", toolCallId="x", content=content))
    finish(session)
    session.capture(tmp_path / "capture.json")
    output = (tmp_path / "capture.json").read_text()
    assert CANARY[:9] not in output and CANARY[9:] not in output


def test_unreadable_directory_does_not_silently_disappear_from_capture(tmp_path, monkeypatch):
    workspace = tmp_path / "work"
    workspace.mkdir()
    def failed_walk(root, *, follow_symlinks, onerror):
        onerror(PermissionError("fixture"))
        return iter(())
    monkeypatch.setattr(client.os, "fwalk", failed_walk)
    with pytest.raises(client.Refused, match="capture_path_refused"):
        client.workspace_files(workspace)


@pytest.mark.parametrize("mode", ["whole", "split", "binary", "initial_part"])
def test_credentials_never_survive_artifact_serialization(tmp_path, mode):
    session, _, _ = setup()
    start(session)
    values = [CANARY] if mode not in {"split", "initial_part"} else [CANARY[:9], CANARY[9:]]
    for i, value in enumerate(values, 2):
        if mode == "initial_part" and i == 2:
            session.accept(event(i, "chat/responsePart", turnId="turn1", part={"kind": "markdown", "id": "p", "content": value}))
        else:
            session.accept(event(i, "chat/delta", turnId="turn1", partId="p", content=value))
    workspace = tmp_path / "work"
    workspace.mkdir()
    (workspace / "file").write_bytes((b"\xff" if mode == "binary" else b"") + CANARY.encode())
    finish(session)
    if mode == "binary":
        with pytest.raises(client.Refused, match="binary_credential_exposure_refused"):
            session.capture(tmp_path / "capture.json", workspace=workspace)
        assert not (tmp_path / "capture.json").exists()
    else:
        record = session.capture(tmp_path / "capture.json", workspace=workspace)
        text = (tmp_path / "capture.json").read_text()
        assert CANARY not in text
        if mode in {"split", "initial_part"}:
            assert CANARY[:9] not in text and CANARY[9:] not in text
        assert record["generated_files"][0]["content"] == "[REDACTED]"
        assert record["generated_files"][0]["redacted"]


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "fifo", "directory_link", "too_large"])
def test_generated_special_or_unbounded_files_refuse(tmp_path, kind, monkeypatch):
    import os
    workspace = tmp_path / "work"
    workspace.mkdir()
    outside = tmp_path / "outside"
    outside.write_bytes(b"fixture")
    path = workspace / "output"
    if kind == "symlink": path.symlink_to(outside)
    if kind == "hardlink": os.link(outside, path)
    if kind == "fifo": os.mkfifo(path)
    if kind == "directory_link": path.symlink_to(tmp_path, target_is_directory=True)
    if kind == "too_large":
        path.write_bytes(b"fixture")
        monkeypatch.setattr(client, "MAX_FILE_BYTES", 2)
    with pytest.raises(client.Refused):
        client.workspace_files(workspace)


def test_size_limit_terminates_without_silently_truncating(monkeypatch):
    session, port, _ = setup()
    start(session)
    monkeypatch.setattr(client, "MAX_EVENT_BYTES", 100)
    assert not session.accept(event(2, "chat/delta", turnId="turn1", partId="p", content="x" * 101))
    assert session.reason == "capture_size_limit" and port.stopped == 1


@pytest.mark.parametrize("version", [None, "1.0", "2.1", 2])
def test_wrong_jsonrpc_version_refuses(version):
    session, _, _ = setup()
    value = event(1, "chat/turnStarted", turnId="t", message={"text": "fixture"})
    value["jsonrpc"] = version
    assert not session.accept(value) and session.reason == "invalid_jsonrpc_version"


def test_fake_stream_runs_to_completion_without_model_calls():
    session, port, _ = setup(stream=[event(1, "chat/turnStarted", turnId="t", message={"text": "fixture"}),
                                    event(2, "chat/turnComplete", turnId="t", duration=1)])
    assert session.send_turn("t", "fixture")
    session.run()
    assert session.status == "completed" and port.stopped == 1


def test_existing_workflow_has_one_protected_dispatch_only_adapter_switch():
    workflow = yaml.load((ROOT / ".github/workflows/agentic-v2-ghcp-sol-gate.yml").read_text(), Loader=yaml.BaseLoader)
    choice = workflow["on"]["workflow_dispatch"]["inputs"]["execution_adapter"]
    assert choice == {"description": "AHP is a fail-closed draft until native hard caps and served settings are proved",
                      "type": "choice", "options": ["copilot-cli", "ahp-draft"], "default": "copilot-cli", "required": "true"}
    job = workflow["jobs"]["paid-task"]
    assert job["if"] == "${{ github.event_name == 'workflow_dispatch' && inputs.execute_paid == true && inputs.dry_run == false }}"
    assert job["environment"] == "ghcp-sol-gate" and job["runs-on"] == "ubuntu-24.04"
    assert [name for name, body in workflow["jobs"].items() if "secrets." in yaml.dump(body)] == ["paid-task"]
    steps = job["steps"]
    runtime = next(step for step in steps if "secrets." in yaml.dump(step))
    assert '--adapter "$GHCP_EXECUTION_ADAPTER"' in runtime["run"]
    for name in ("Prepare only hash-pinned public original inputs without authentication", "Install the pinned CLI without launching it"):
        assert next(step for step in steps if step.get("name") == name)["if"] == "inputs.execution_adapter != 'ahp-draft'"


def test_existing_push_probe_runs_collector_fixtures_without_enabling_work_rpc():
    text = (ROOT / ".github/workflows/ghcp-ahp-model-free-probe.yml").read_text()
    assert "tests/test_ghcp_ahp_client.py" in text
    assert "secrets." not in text and "workflow_dispatch" not in text
    from ghcp_ahp_probe import ALLOWED_METHODS
    assert "dispatchAction" not in ALLOWED_METHODS and "authenticate" not in ALLOWED_METHODS
    assert ALLOWED_METHODS == {"initialize", "resolveSessionConfig", "createSession", "subscribe", "disposeSession"}
