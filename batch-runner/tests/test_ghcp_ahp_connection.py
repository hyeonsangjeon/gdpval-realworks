"""Synthetic connection events ONLY. No host, sockets, real auth or model calls."""

from contextlib import contextmanager
import base64
import copy
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
from types import SimpleNamespace

import pytest
import yaml

import ghcp_ahp_connection as connection
import ghcp_ahp_connection_transport as transport
import ghcp_ahp_probe as probe

ROOT = Path(__file__).resolve().parents[2]
SESSION, CHAT = "ahp-session:/fixture", "ahp-chat:/fixture"
CANARY = "SYNTHETIC_CONNECTION_AUTH_987654_NOT_REAL"


@pytest.fixture(autouse=True)
def offline_only(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("synthetic connection test attempted a real process or network")
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(probe.urllib.request, "build_opener", forbidden)


class Clock:
    value = 0.0

    def __call__(self):
        return self.value


class Port:
    session, chat = SESSION, CHAT

    def __init__(self, stream=(), clock=None):
        self.stream, self.sent = iter(stream), []
        self.clock = clock or Clock()
        self.turns_sent, self.stopped = 0, False

    def send(self, message, timeout):
        self.sent.append(copy.deepcopy(message))
        self.turns_sent += message.get("params", {}).get("action", {}).get("type") == "chat/turnStarted"

    def receive(self, timeout):
        try:
            return next(self.stream)
        except StopIteration:
            self.clock.value += timeout
            raise TimeoutError from None

    def terminate(self, timeout):
        self.stopped = True
        return True

    def handshake_capture(self):
        return {"fixture": True, "authentication": "[REDACTED]"}


def event(seq, kind, **fields):
    return {"jsonrpc": "2.0", "method": "action", "params": {
        "channel": CHAT, "serverSeq": seq, "origin": None,
        "action": {"type": kind, "turnId": connection.TURN, **fields}}}


def stream(*, context=1_000_000, usage=True, reply="CONNECTED", fixture_observed=None):
    rows = [event(1, "chat/turnStarted", message={"text": connection.PROMPT, "model": probe.DESIRED_MODEL}),
            event(2, "chat/responsePart", part={"kind": "markdown", "id": "answer", "content": ""}),
            event(3, "chat/delta", partId="answer", content=reply)]
    if usage:
        rows.append(event(4, "chat/usage", usage={"model": probe.DESIRED_MODEL["id"],
            "inputTokens": 12, "outputTokens": 2, "cacheReadTokens": 0,
            "_meta": {"modelContextWindow": context, "reasoningOutputTokens": 1,
                      "fixture_only_observations": fixture_observed}}))
    rows.append(event(5, "chat/turnComplete", duration=10))
    return rows


def setup(rows=(), *, authenticated=True):
    clock = Clock()
    port = Port(rows, clock)
    client = connection.ConnectionSession(port, SESSION, CHAT, authenticated=authenticated,
                                         credential=CANARY, clock=clock)
    return client, port, clock


def complete(client, output):
    assert client.send_turn(connection.TURN, connection.PROMPT)
    client.run()
    capture = client.capture(output)
    return client.result(capture), capture


@pytest.mark.parametrize("case", ["pass", "mismatch", "not_reported"])
def test_synthetic_attestation_events_exercise_all_three_decisions_without_enabling_live_mapper(tmp_path, case):
    observed = {"served_model": "gpt-5.6-sol", "thinking_level": "max", "context_size": 1_000_000,
                "usage": [{"inputTokens": 12, "outputTokens": 2}]}
    if case == "mismatch":
        observed["thinking_level"] = "high"
    if case == "not_reported":
        observed["served_model"] = "not_reported"

    class AttestingFixture(connection.ConnectionSession):
        # A hypothetical response-side evidence reader, injected IN THIS TEST
        # ONLY. No production parser/flag accepts this fixture metadata.
        def _action(self, channel, action):
            super()._action(channel, action)
            if action["type"] == "chat/usage":
                self.observed.update(action["usage"]["_meta"]["fixture_only_observations"])
                self.provenance.update({key: "synthetic_test_only" for key in connection.FIELDS})

    port = Port(stream(fixture_observed=observed))
    client = AttestingFixture(port, SESSION, CHAT, authenticated=True, clock=port.clock)
    result, capture = complete(client, tmp_path / "capture.json")
    assert result["connection_verified"] is (case == "pass")
    assert result["status"] == ("connected" if case == "pass" else "refused")
    assert result["reason_codes"] == {"pass": [], "mismatch": ["thinking_level_mismatch"],
                                      "not_reported": ["served_model_not_reported"]}[case]
    assert result["requested"] == connection.REQUESTED
    assert result["observed"] == observed
    assert port.turns_sent == 1 and port.stopped
    assert capture["counts"]["observed_tool_calls"] == 0
    assert not result["five_task_allowed"] and not result["gate_ready"]


def test_pinned_wire_never_promotes_model_echo_or_fixture_metadata_to_served_evidence(tmp_path):
    client, port, _ = setup(stream(fixture_observed=connection.REQUESTED))
    result, capture = complete(client, tmp_path / "capture.json")
    assert result["reason_codes"] == ["served_model_not_reported", "thinking_level_not_reported"]
    assert result["observed"]["served_model"] == result["observed"]["thinking_level"] == "not_reported"
    assert result["observed"]["context_size"] == 1_000_000
    assert result["observed"]["usage"][0]["inputTokens"] == 12
    assert result["limits"] == {"turns": 1, "tool_calls": 0, "seconds": 120}
    assert capture["counts"]["model_requests"] == "not_reported"
    assert port.turns_sent == 1 and not result["connection_verified"]


def test_context_only_usage_frame_does_not_invent_token_usage(tmp_path):
    rows = stream()
    rows[3]["params"]["action"]["usage"] = {"_meta": {"modelContextWindow": 1000000}}
    client, _, _ = setup(rows)
    result, _ = complete(client, tmp_path / "capture.json")
    assert result["observed"]["context_size"] == 1000000
    assert result["observed"]["usage"] == "not_reported"


@pytest.mark.parametrize("value", [-1, True, 1.5, "12", None])
def test_invalid_token_usage_is_not_accepted(tmp_path, value):
    rows = stream()
    rows[3]["params"]["action"]["usage"]["inputTokens"] = value
    client, _, _ = setup(rows)
    result, _ = complete(client, tmp_path / "capture.json")
    assert "connection_usage_invalid" in result["reason_codes"]
    assert result["observed"]["usage"] == "not_reported"


@pytest.mark.parametrize("field", ["served_model", "thinking_level", "context_size"])
@pytest.mark.parametrize("value", [None, "not_reported", "", False, 0, "wrong"])
def test_every_missing_or_mismatched_observation_refuses(field, value):
    observed = copy.deepcopy(connection.REQUESTED)
    observed[field] = value
    verdict = connection.settings_verdict(observed)
    assert not verdict["settings_verified"]
    assert verdict["reason_codes"] == [field + ("_not_reported" if value in (None, "not_reported", "") else "_mismatch")]


def test_single_admitted_turn_finishes_instead_of_cancelling_it_at_admission(tmp_path):
    client, port, _ = setup(stream())
    result, capture = complete(client, tmp_path / "capture.json")
    assert client.status == "completed" and client.completed == {connection.TURN}
    assert capture["cleanup"]["cancel_attempts"] == 0
    assert capture["cleanup"]["dispose_attempts"] == 1
    assert not client.send_turn("second", "must not send")
    assert port.turns_sent == 1 and result["reply_exact"]


def test_second_turn_is_refused_even_while_first_is_still_active():
    client, port, _ = setup()
    assert client.send_turn(connection.TURN, connection.PROMPT)
    assert client.status == "open"
    assert not client.send_turn("second", "must not send")
    assert client.reason == "turn_limit_reached" and port.turns_sent == 1 and port.stopped


@pytest.mark.parametrize("elapsed", [120, 120.01, 999])
def test_connection_deadline_prevents_first_turn_and_cancels_active_turn(elapsed):
    client, port, clock = setup()
    clock.value = elapsed
    assert not client.send_turn(connection.TURN, connection.PROMPT)
    assert port.turns_sent == 0 and client.reason == "time_limit_reached"
    client, port, clock = setup()
    assert client.send_turn(connection.TURN, connection.PROMPT)
    clock.value = elapsed
    assert not client.tick()
    assert client.reason == "time_limit_reached" and port.stopped and port.turns_sent == 1


@pytest.mark.parametrize("kind", ["chat/toolCallStart", "chat/toolCallReady", "chat/toolCallComplete"])
def test_zero_tool_budget_cancels_on_first_tool_without_approval_or_second_work(tmp_path, kind):
    client, port, _ = setup([event(1, kind, toolCallId="tool", confirmed="auto")])
    result, capture = complete(client, tmp_path / "capture.json")
    assert "connection_tool_forbidden" in result["reason_codes"]
    assert capture["counts"]["observed_tool_calls"] == 1
    assert capture["observed_overshoot"]["tool_calls"] == 1
    assert result["overshoot_boundary"]["server_internal_tool_calls"] == "no_finite_bound_proven"
    assert port.turns_sent == 1 and port.stopped
    assert not any(m.get("params", {}).get("action", {}).get("type") == "chat/toolCallConfirmed" for m in port.sent)


@pytest.mark.parametrize("change", ["missing_usage", "wrong_context", "wrong_reply", "foreign_turn", "late_tool", "history"])
def test_failure_cases_never_allow_five_tasks(tmp_path, change):
    rows = stream(usage=change != "missing_usage", context=258400 if change == "wrong_context" else 1000000,
                  reply="not connected" if change == "wrong_reply" else "CONNECTED")
    if change == "foreign_turn":
        rows[1]["params"]["action"]["turnId"] = "foreign"
    if change == "history":
        rows.insert(0, {"jsonrpc": "2.0", "id": "history", "result": {"snapshot": {
            "resource": CHAT, "fromSeq": 0, "state": {"turns": [{"id": "old"}]}}}})
    client, _, _ = setup(rows)
    result, _ = complete(client, tmp_path / "capture.json")
    if change == "late_tool":
        assert not client.accept(event(6, "chat/toolCallStart", toolCallId="late"))
        result = client.result(client.capture(tmp_path / "late.json"))
        assert "connection_tool_forbidden" in result["reason_codes"]
    assert not result["connection_verified"] and not result["five_task_allowed"]
    if change == "missing_usage":
        assert result["observed"] == connection.empty_observed()


def test_missing_authentication_in_session_sends_zero_turns(tmp_path):
    client, port, _ = setup(authenticated=False)
    assert not client.send_turn(connection.TURN, connection.PROMPT)
    assert client.reason == "authentication_required" and port.turns_sent == 0
    capture = client.capture(tmp_path / "capture.json")
    assert not client.result(capture)["connection_verified"]


@pytest.fixture
def dispatch(monkeypatch, github_hosted_ubuntu_2404):
    for key, value in {"GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_RUN_ID": "100", "GITHUB_RUN_ATTEMPT": "1",
                       "GITHUB_SHA": "a" * 40, "RUNNER_ARCH": "X64", "GHCP_PAID_EXECUTION": "true",
                       "GHCP_CONNECTION_ONLY": "true", "COPILOT_GITHUB_TOKEN": CANARY}.items():
        monkeypatch.setenv(key, value)


@pytest.mark.parametrize("value", [None, "", " "])
def test_runtime_missing_auth_refuses_before_opener_or_host(dispatch, monkeypatch, tmp_path, value):
    if value is None:
        monkeypatch.delenv("COPILOT_GITHUB_TOKEN")
    else:
        monkeypatch.setenv("COPILOT_GITHUB_TOKEN", value)
    def forbidden(*args):
        pytest.fail("missing authentication reached transport")
    result = connection.execute(tmp_path / "prepared", tmp_path / "evidence", tmp_path / "state",
                                tmp_path / "output", open_port=forbidden)
    assert result["reason_codes"] == ["auth_source_unavailable"]
    assert result["client_turns_sent"] == 0 and not (tmp_path / "state").exists()
    assert json.loads((tmp_path / "output/connection.json").read_text()) == result


@pytest.mark.parametrize("field,value", [("GITHUB_EVENT_NAME", "push"), ("GITHUB_EVENT_NAME", "pull_request"),
    ("GHCP_CONNECTION_ONLY", "false"), ("GHCP_PAID_EXECUTION", "false"), ("GITHUB_RUN_ATTEMPT", "2"),
    ("ImageOS", "ubuntu22"), ("RUNNER_ENVIRONMENT", "self-hosted"), ("GITHUB_ACTIONS", "false")])
def test_runtime_requires_hosted_dispatch_before_auth(dispatch, monkeypatch, tmp_path, field, value):
    import ghcp_sol_execution_adapter as adapter
    monkeypatch.setenv(field, value)
    monkeypatch.setattr(adapter, "_selected_auth_environment", lambda *a, **k: pytest.fail("reached auth"))
    result = connection.execute(*(tmp_path / name for name in ("prepared", "evidence", "state", "output")))
    assert not result["connection_verified"] and result["client_turns_sent"] == 0


def test_runtime_captures_redacted_not_reported_receipt_and_digest(dispatch, monkeypatch, tmp_path):
    port = Port(stream(reply="CONNECTED" + CANARY))
    @contextmanager
    def fake(*args):
        yield port
    original = connection.run_connection
    monkeypatch.setattr(connection, "run_connection", lambda *args, **kwargs: original(*args, **kwargs, clock=port.clock))
    result = connection.execute(*(tmp_path / name for name in ("prepared", "evidence", "state", "output")), open_port=fake)
    assert result["status"] == "refused" and result["client_turns_sent"] == 1
    assert result["capture_sha256"] == probe.digest(tmp_path / "output/capture.json")
    assert result["handshake_sha256"] == probe.digest(tmp_path / "output/handshake.json")
    assert result["runner"]["image_os"] == "ubuntu24"
    for path in (tmp_path / "output").glob("*.json"):
        assert CANARY not in path.read_text()


def test_capture_failure_cannot_create_connected_receipt(dispatch, monkeypatch, tmp_path):
    port = Port(stream())
    @contextmanager
    def fake(*args):
        yield port
    monkeypatch.setattr(connection.ConnectionSession, "capture", lambda *a, **k: (_ for _ in ()).throw(OSError("fixture")))
    result = connection.execute(*(tmp_path / name for name in ("prepared", "evidence", "state", "output")), open_port=fake)
    assert not result["connection_verified"] and result["reason_codes"] == ["connection_execution_refused"]
    assert result["client_turns_sent"] == 1


@pytest.mark.parametrize("change", ["absent", "not_reported", "wrong_run", "tampered_capture", "synthetic_success"])
def test_receipt_handoff_cannot_bypass_live_attestation(dispatch, tmp_path, change):
    if change == "absent":
        with pytest.raises(probe.Refused, match="connection_verification_required"):
            connection.require_verified_connection(None)
        return
    capture, handshake = tmp_path / "capture.json", tmp_path / "handshake.json"
    probe.save_json(capture, {"synthetic": True})
    probe.save_json(handshake, {"synthetic": True})
    record = {"schema_version": "ghcp-ahp-connection-v1", "status": "connected", "connection_verified": True,
              "requested": connection.REQUESTED, "observed": copy.deepcopy(connection.REQUESTED),
              "limits": asdict(connection.LIMITS), "reply_exact": True, "client_turns_sent": 1,
              "runner": probe.require_runner(), "reason_codes": [], "capture_sha256": probe.digest(capture),
              "handshake_sha256": probe.digest(handshake)}
    if change == "not_reported": record["observed"]["served_model"] = "not_reported"
    if change == "wrong_run": record["runner"]["github_run_id"] = "99"
    if change == "tampered_capture": record["capture_sha256"] = "0" * 64
    probe.save_json(tmp_path / "connection.json", record)
    with pytest.raises(probe.Refused, match="connection_(verification_required|capture_unverified|served_attestation_unavailable)"):
        connection.require_verified_connection(tmp_path / "connection.json")


def workflow():
    return yaml.load((ROOT / ".github/workflows/agentic-v2-ghcp-sol-gate.yml").read_text(), Loader=yaml.BaseLoader)


def test_connection_job_is_single_protected_dispatch_only_and_task_waits_for_receipt():
    value = workflow()
    job = value["jobs"]["ahp-connection"]
    assert job["if"] == "${{ github.event_name == 'workflow_dispatch' && inputs.execute_paid == true && inputs.dry_run == false && inputs.execution_adapter == 'ahp-draft' }}"
    assert job["environment"] == "ghcp-sol-gate" and job["runs-on"] == "ubuntu-24.04"
    assert "strategy" not in job and job["timeout-minutes"] == "10"
    assert job["outputs"] == {"verified": "${{ steps.connection.outputs.verified }}"}
    selected = [step for step in job["steps"] if "secrets." in yaml.dump(step)]
    assert len(selected) == 1
    assert selected[0]["env"] == {"COPILOT_GITHUB_TOKEN": "${{ secrets.COPILOT_GITHUB_TOKEN }}",
                                   "GHCP_PAID_EXECUTION": "true", "GHCP_CONNECTION_ONLY": "true"}
    assert "ghcp_ahp_connection.py" in selected[0]["run"] and "unshare --mount --pid" in selected[0]["run"]
    assert "--kill-child=KILL" in selected[0]["run"] and "130s" in selected[0]["run"]
    assert '--preserve-env=COPILOT_GITHUB_TOKEN,' in selected[0]["run"]
    assert '$COPILOT_GITHUB_TOKEN' not in selected[0]["run"]  # Never interpolate a value into argv.
    assert all("continue-on-error" not in step for step in job["steps"])
    task = value["jobs"]["paid-task"]
    assert task["needs"] == ["plan", "ahp-connection"]
    assert "inputs.connection_only != true" in task["if"]
    assert "needs.ahp-connection.result == 'success'" in task["if"]
    assert "needs.ahp-connection.outputs.verified == 'true'" in task["if"]
    runtime = next(step for step in task["steps"] if "secrets." in yaml.dump(step))
    assert "--connection-receipt" in runtime["run"]
    for name in ("offline-ci", "plan", "task", "grader-contract"):
        assert "secrets." not in yaml.dump(value["jobs"][name])


@pytest.mark.parametrize("event_name", ["push", "pull_request", "workflow_dispatch"])
@pytest.mark.parametrize("paid,dry", [(False, False), (False, True), (True, True), (True, False)])
@pytest.mark.parametrize("connection_only", [True, False])
@pytest.mark.parametrize("verified", [True, False])
def test_ahp_dispatch_routing_truth_table(event_name, paid, dry, connection_only, verified):
    admitted = event_name == "workflow_dispatch" and paid and not dry
    connect_job = admitted
    task_job = admitted and not connection_only and verified
    if event_name != "workflow_dispatch" or not paid or dry:
        assert not connect_job and not task_job
    if connection_only or not verified:
        assert not task_job
    # Exact YAML terms are asserted above, not an unconstrained expression eval.
    assert "inputs.connection_only" not in workflow()["jobs"]["ahp-connection"]["if"]


def test_push_probe_remains_credential_free_no_live_rpc_or_connection_entry():
    text = (ROOT / ".github/workflows/ghcp-ahp-model-free-probe.yml").read_text()
    assert "tests/test_ghcp_ahp_connection.py" in text
    assert "secrets." not in text and "COPILOT_GITHUB_TOKEN" not in text
    assert "ghcp_ahp_connection.py" not in text.replace("tests/test_ghcp_ahp_connection.py", "")
    assert "workflow_dispatch" not in text
    assert probe.ALLOWED_METHODS == {"initialize", "resolveSessionConfig", "createSession", "subscribe", "disposeSession"}


class Wire:
    def __init__(self):
        self.sent, self.replies = [], []

    def send(self, message):
        self.sent.append(copy.deepcopy(message))

    def receive(self):
        return self.replies.pop(0)


def test_handshake_authenticates_only_advertised_codex_resource_and_subscribes_fresh_chat(monkeypatch):
    port = transport.ConnectionPort(Wire(), SimpleNamespace(), 999999999999, CANARY)
    calls = []
    def fake_rpc(method, params):
        calls.append((method, copy.deepcopy(params)))
        if method == "initialize":
            return {"protocolVersion": "1.1.0", "snapshots": [{"resource": probe.ROOT_CHANNEL,
                "state": {"agents": [{"provider": "codex", "protectedResources": [{"resource": transport.RESOURCE}]}]}}]}
        if method == "resolveSessionConfig":
            return {"schema": {"properties": {key: {} for key in transport.CONFIG}}, "values": transport.CONFIG}
        if method == "subscribe":
            return {"snapshot": {"resource": params["channel"], "fromSeq": 0,
                "state": {"defaultChat": CHAT, "chats": [{"resource": CHAT}]} if params["channel"] == port.session else {"turns": []}}}
        return {}
    monkeypatch.setattr(port, "rpc", fake_rpc)
    monkeypatch.setattr(port, "_read", lambda: None)
    port.initialize("file:///synthetic-empty")
    assert [name for name, _ in calls] == ["initialize", "authenticate", "resolveSessionConfig", "createSession", "subscribe", "subscribe"]
    assert calls[1][1] == {"channel": probe.ROOT_CHANNEL, "resource": transport.RESOURCE, "token": CANARY}
    assert calls[3][1]["provider"] == "codex" and calls[3][1]["activeClient"]["tools"] == []
    assert port.turns_sent == 0 and port.chat == CHAT


def test_handshake_frame_redaction_masks_known_and_keyed_values():
    port = transport.ConnectionPort(Wire(), SimpleNamespace(), 999999999999, CANARY)
    port._capture("client", {"method": "authenticate", "params": {"token": CANARY}})
    port._capture("server", {"result": {"message": CANARY}})
    assert CANARY not in json.dumps(port.handshake_capture())


@pytest.mark.parametrize("method", ["createChat", "fetchTurns", "dispatchAction", "resourceWrite", "reconnect"])
def test_connection_transport_rejects_non_handshake_rpc(method):
    port = transport.ConnectionPort(Wire(), SimpleNamespace(), 999999999999, CANARY)
    with pytest.raises(probe.Refused, match="connection_rpc_refused"):
        port.rpc(method, {})
    assert port.wire.sent == []


@pytest.mark.parametrize("action", ["chat/toolCallConfirmed", "chat/turnResume", "chat/pendingMessageSet", "session/activeClientSet"])
def test_connection_transport_never_sends_tool_approval_resume_or_queued_work(action):
    port = transport.ConnectionPort(Wire(), SimpleNamespace(), 999999999999, CANARY)
    port.chat = CHAT
    with pytest.raises(probe.Refused, match="connection_work_not_allowed"):
        port.send({"method": "dispatchAction", "params": {"channel": CHAT, "action": {"type": action}}}, timeout=1)
    assert port.wire.sent == []


def test_connection_transport_reserves_exactly_one_fixed_prompt_even_if_send_fails(monkeypatch):
    client, _, _ = setup()
    assert client.send_turn(connection.TURN, connection.PROMPT)
    request = client.transport.sent[0]
    port = transport.ConnectionPort(Wire(), SimpleNamespace(), 999999999999, CANARY)
    port.chat = CHAT
    port.send(request, timeout=1)
    with pytest.raises(probe.Refused, match="connection_prompt_refused"):
        port.send(request, timeout=1)
    assert port.turns_sent == len(port.wire.sent) == 1


def test_live_transport_requires_pid_namespace_before_process_or_prepared_bytes(dispatch, monkeypatch, tmp_path):
    monkeypatch.delenv("GHCP_CONNECTION_OUTSIDE_PIDNS", raising=False)
    with pytest.raises(probe.Refused, match="connection_pid_isolation_required"):
        with transport.open_connection_port(tmp_path / "prepared", tmp_path / "evidence", tmp_path / "state", CANARY):
            pytest.fail("unisolated process admitted")
    assert not (tmp_path / "state").exists()


@pytest.mark.parametrize("uid,privileges", [(0, "NoNewPrivs:\t1\nCapEff:\t0000\n"),
    (1001, "NoNewPrivs:\t0\nCapEff:\t0000\n"), (1001, "NoNewPrivs:\t1\nCapEff:\t0001\n")])
def test_pid_namespace_alone_does_not_prove_dropped_privileges(monkeypatch, uid, privileges):
    monkeypatch.setenv("GHCP_CONNECTION_OUTSIDE_PIDNS", "pid:[1]")
    monkeypatch.setattr(transport.os, "getpid", lambda: 1)
    monkeypatch.setattr(transport.os, "geteuid", lambda: uid)
    monkeypatch.setattr(transport.os, "readlink", lambda _: "pid:[2]")
    monkeypatch.setattr(transport.Path, "read_text", lambda _: privileges)
    with pytest.raises(probe.Refused, match="connection_privilege_drop_required"):
        transport.require_namespace()


@pytest.mark.parametrize("token", ["", "arbitrary-token", "a" * 63, "A" * 64, "a" * 64 + "\r\n"])
def test_invalid_transport_token_refuses_before_socket_creation(token):
    with pytest.raises(probe.Refused, match="invalid_local_connection_token"):
        probe.WebSocket(1234, 99999999999, connection_token=token)


def test_transport_token_is_on_loopback_upgrade_only_not_copilot_credential(monkeypatch):
    class Socket:
        def sendall(self, request):
            self.request = request
        def settimeout(self, timeout):
            pass
        def recv(self, size):
            nonce = self.request.decode().split("Sec-WebSocket-Key: ")[1].split("\r\n")[0]
            accept = base64.b64encode(hashlib.sha1((nonce + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest())
            return b"HTTP/1.1 101 Switching Protocols\r\nSec-WebSocket-Accept: " + accept + b"\r\n\r\n"
        def close(self):
            pass
    peer = Socket()
    calls = []
    def fake_connection(address, timeout):
        calls.append(address)
        return peer
    monkeypatch.setattr(socket, "create_connection", fake_connection)
    ws = probe.WebSocket(1234, 99999999999, connection_token="a" * 64)
    assert peer.request.startswith(b"GET /?tkn=" + b"a" * 64 + b" HTTP/1.1\r\n")
    assert CANARY.encode() not in peer.request and calls == [("127.0.0.1", 1234)]
    ws.close()
