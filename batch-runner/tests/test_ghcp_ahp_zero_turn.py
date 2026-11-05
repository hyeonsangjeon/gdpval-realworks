"""Authenticated session fixtures only: no installed host, SDK or provider."""

import copy
import json
from pathlib import Path
import re
import socket
import threading

import pytest
import yaml

import ghcp_ahp_probe as probe
import ghcp_ahp_thread_policy as policy
import ghcp_ahp_wire_capture as wire_capture
import ghcp_ahp_zero_turn as zero
from .test_ghcp_ahp_probe import backend_probe_fixture  # Shared fake process/loopback fixture only.

REAL_EXPORT = wire_capture.export

ROOT = Path(__file__).resolve().parents[2]
CANARY = "SYNTHETIC_AuthZeroTurn_NotACredential_123456"
SESSION = "ahp-session:/aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa"
WORKSPACE = "file:///synthetic-empty-workspace"


@pytest.fixture(autouse=True)
def deny_external_effects(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("zero-turn fixture crossed a process or network boundary")
    monkeypatch.setattr(probe.subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(probe.urllib.request, "build_opener", forbidden)


@pytest.fixture
def context(monkeypatch):
    values = {"GITHUB_EVENT_NAME": "workflow_dispatch", "GHCP_AUTHENTICATED_ZERO_TURN": "true",
              "GHCP_PAID_EXECUTION": "false", "GHCP_CONNECTION_ONLY": "false"}
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    return values


class Wire:
    def __init__(self, *, auth_error=False, session_error=False, advertised=True, event=None):
        self.sent = []
        self.auth_error, self.session_error = auth_error, session_error
        self.advertised, self.event = advertised, event

    def send(self, value):
        self.sent.append(copy.deepcopy(value))

    def receive(self):
        if self.event is not None:
            value, self.event = self.event, None
            return {"jsonrpc": "2.0", "method": "notification", "params": {"action": {"type": value}}}
        request = self.sent[-1]
        method = request["method"]
        reply = {"jsonrpc": "2.0", "id": request["id"], "result": {}}
        if method == "initialize":
            reply["result"] = {"protocolVersion": "1.1.0", "snapshots": [{"resource": probe.ROOT_CHANNEL,
                "state": {"agents": [{"provider": "codex", "protectedResources":
                    [{"resource": policy.AUTH_RESOURCE}] if self.advertised else []}]}}]}
        elif method == "resolveSessionConfig":
            reply["result"] = {"values": copy.deepcopy(policy.POLICY), "schema": {"properties": {}}}
        elif method == "authenticate" and self.auth_error or method == "createSession" and self.session_error:
            del reply["result"]
            reply["error"] = {"code": -32007, "message": "synthetic failure echo " + CANARY}
        else:
            reply["result"] = {"message": "synthetic echo " + CANARY}
        return reply

    def close(self):
        pass


def test_authenticated_sequence_has_one_auth_one_session_and_no_turn_or_capi():
    wire = Wire()
    rpc = probe.Rpc(wire, SESSION, WORKSPACE, session_policy=True, credential=CANARY)
    observed = []
    results = policy.exercise(rpc, lambda: observed.append(True) or {"replies": 1})
    assert [row["method"] for row in wire.sent] == list(policy.AUTH_METHODS)
    assert wire.sent[1]["params"] == {"channel": probe.ROOT_CHANNEL, "resource": policy.AUTH_RESOURCE, "token": CANARY}
    assert wire.sent[3]["params"]["config"] == policy.POLICY
    assert set(wire.sent[3]["params"]) == {"channel", "provider", "workingDirectories", "config"}
    assert observed == [True] and "disposeSession" in results
    assert CANARY not in json.dumps([rpc.sent, rpc.received, results])
    assert rpc.sent[1]["params"]["token"] == "[REDACTED]"
    with pytest.raises(probe.Refused, match="session_policy_rpc_order_refused"):
        rpc.request("createSession", wire.sent[3]["params"])
    assert len(wire.sent) == 6


@pytest.mark.parametrize("auth_error,session_error,count", [(True, False, 2), (False, True, 4)])
def test_auth_or_session_refusal_has_no_retry_subscription_or_work(auth_error, session_error, count):
    wire = Wire(auth_error=auth_error, session_error=session_error)
    rpc = probe.Rpc(wire, SESSION, WORKSPACE, session_policy=True, credential=CANARY)
    results = policy.exercise(rpc, lambda: pytest.fail("observer started after refusal"))
    assert len(wire.sent) == count
    stage = "authenticate" if auth_error else "createSession"
    assert results[stage]["error"]["code"] == -32007
    assert CANARY not in json.dumps([results, rpc.sent, rpc.received])


def test_protected_resource_must_be_advertised_before_sending_credential():
    wire = Wire(advertised=False)
    rpc = probe.Rpc(wire, SESSION, WORKSPACE, session_policy=True, credential=CANARY)
    with pytest.raises(probe.Refused, match="zero_turn_auth_resource_refused"):
        policy.exercise(rpc)
    assert [row["method"] for row in wire.sent] == ["initialize"]
    assert CANARY not in json.dumps(wire.sent)


@pytest.mark.parametrize("field,value", [("channel", SESSION), ("resource", "https://evil.invalid"),
    ("token", "OTHER_SYNTHETIC_VALUE"), ("model", "gpt-5.6-sol"), ("initialMessage", "forbidden")])
def test_auth_parameters_are_exact_and_cannot_smuggle_work(field, value):
    wire = Wire()
    rpc = probe.Rpc(wire, SESSION, WORKSPACE, session_policy=True, credential=CANARY)
    rpc.sent.append({"method": "initialize"})
    params = {"channel": probe.ROOT_CHANNEL, "resource": policy.AUTH_RESOURCE, "token": CANARY, field: value}
    with pytest.raises(probe.Refused, match="zero_turn_auth_rpc_refused"):
        rpc.request("authenticate", params)
    assert wire.sent == []


@pytest.mark.parametrize("method", ["turn/start", "dispatchAction", "sendMessage", "thread/resume", "thread/fork", "command/exec"])
def test_authenticated_mode_still_refuses_work_before_wire_send(method):
    wire = Wire()
    rpc = probe.Rpc(wire, SESSION, WORKSPACE, session_policy=True, credential=CANARY)
    with pytest.raises(probe.Refused, match="session_policy_rpc_order_refused"):
        rpc.request(method, {})
    assert wire.sent == []


@pytest.mark.parametrize("event", ["chat/turnStarted", "chat/turnDelta", "chat/turnFinished", "chat/toolCallStart", "chat/toolCallEnd", "turn/started", "item/tool/call"])
def test_incoming_work_is_fatal_even_during_authentication(event):
    wire = Wire(event=event)
    rpc = probe.Rpc(wire, SESSION, WORKSPACE, session_policy=True, credential=CANARY)
    with pytest.raises(probe.Refused, match="unexpected_turn_or_tool_activity"):
        policy.exercise(rpc)
    assert len(wire.sent) == 1


@pytest.mark.parametrize("key", ["GITHUB_EVENT_NAME", "GHCP_AUTHENTICATED_ZERO_TURN", "GHCP_PAID_EXECUTION", "GHCP_CONNECTION_ONLY"])
@pytest.mark.parametrize("value", [None, "wrong"])
def test_dispatch_context_is_mandatory_before_secret_or_process_access(context, monkeypatch, key, value):
    if value is None:
        monkeypatch.delenv(key)
    else:
        monkeypatch.setenv(key, value)
    with pytest.raises(probe.Refused, match="zero_turn_dispatch_opt_in_required"):
        zero.require_context()


@pytest.mark.parametrize("value", ["", None, False, "a\nb", "a b", "a\x00b", "한글", "a" * 16385])
def test_empty_or_malformed_auth_fails_without_exposing_its_value(value):
    with pytest.raises(probe.Refused, match="^zero_turn_auth_source_unavailable$"):
        zero.validate_credential(value)


@pytest.mark.parametrize("row", [
    {"kind": "blocked", "reason": "session_policy_http_refused"},
    {"kind": "wire_parse_error"}, {"kind": "capi_request"}, {"kind": "capi_headers"},
    {"kind": "capi_event"}, {"kind": "capi_body"},
    {"kind": "ipc_request", "value": {"method": "turn/start"}},
    {"kind": "ipc_response", "value": {"method": "turn/started"}},
    {"kind": "ipc_response", "value": {"method": "item/tool/call"}},
])
def test_watchdog_cancels_owned_host_once_on_any_forbidden_boundary(tmp_path, row):
    directory = tmp_path / "wire"
    directory.mkdir()
    (directory / "wire-1.jsonl").write_text(json.dumps(row) + "\n")
    cancelled = []
    watchdog = zero.Watchdog(tmp_path, lambda: cancelled.append(True))
    assert watchdog.poll() is False
    assert watchdog.poll() is False
    assert cancelled == [True]
    with pytest.raises(probe.Refused, match="zero_turn_"):
        watchdog.check()


def test_watchdog_allows_only_inert_or_thread_records_and_stops_cleanly(tmp_path):
    directory = tmp_path / "wire"
    directory.mkdir()
    (directory / "wire-1.jsonl").write_text(json.dumps({"kind": "ipc_request", "value": {"method": "thread/start"}}) + "\n")
    watchdog = zero.Watchdog(tmp_path, lambda: pytest.fail("safe thread request was cancelled"))
    assert watchdog.poll() is True
    watchdog.start()
    watchdog.close()
    assert not watchdog.worker.is_alive()


def test_watchdog_racing_rpc_and_background_checks_cancel_once(tmp_path):
    directory = tmp_path / "wire"
    directory.mkdir()
    (directory / "wire-1.jsonl").write_text('{"kind":"blocked"}\n')
    cancelled = []
    watchdog = zero.Watchdog(tmp_path, lambda: cancelled.append(True))
    workers = [threading.Thread(target=watchdog.poll) for _ in range(8)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=2)
        assert not worker.is_alive()
    assert cancelled == [True]


def test_rpc_does_not_send_next_request_after_watchdog_denial():
    wire = Wire()
    def deny():
        raise probe.Refused("zero_turn_observer_boundary_refused")
    rpc = probe.Rpc(wire, SESSION, WORKSPACE, session_policy=True, credential=CANARY, boundary_check=deny)
    with pytest.raises(probe.Refused, match="zero_turn_observer_boundary_refused"):
        policy.exercise(rpc)
    assert wire.sent == []


def test_local_entry_refuses_before_reading_secret_or_starting_any_process(monkeypatch, tmp_path, capsys):
    def deny():
        raise probe.Refused("synthetic_local_runner_refused")
    monkeypatch.setattr(probe, "require_runner", deny)
    monkeypatch.setenv("COPILOT_GITHUB_TOKEN", CANARY)
    assert probe.main(["probe", "--prepared", str(tmp_path / "prepared"), "--evidence", str(tmp_path / "evidence"),
                       "--authenticated-zero-turn"]) == 2
    assert not (tmp_path / "evidence").exists()
    assert CANARY not in capsys.readouterr().out
    assert probe.os.environ["COPILOT_GITHUB_TOKEN"] == CANARY  # Not popped/read by admission.


def test_dispatch_with_missing_secret_fails_before_prepared_files(context, monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(probe, "require_runner", lambda: {"synthetic": True})
    monkeypatch.delenv("COPILOT_GITHUB_TOKEN", raising=False)
    monkeypatch.setattr(probe, "load_manifest", lambda: pytest.fail("must reject missing auth before preparation"))
    assert probe.main(["probe", "--prepared", str(tmp_path / "prepared"), "--evidence", str(tmp_path / "evidence"),
                       "--authenticated-zero-turn"]) == 2
    assert "zero_turn_auth_source_unavailable" in capsys.readouterr().out


def test_default_push_rejects_authentication_rpc_even_with_environment_opt_in(context):
    rpc = probe.Rpc(Wire(), SESSION, WORKSPACE, session_policy=True)
    with pytest.raises(probe.Refused, match="session_policy_rpc_order_refused"):
        rpc.request("authenticate", {"channel": probe.ROOT_CHANNEL, "resource": policy.AUTH_RESOURCE, "token": CANARY})
    assert rpc.transport.sent == []


def workflow():
    return yaml.load((ROOT / ".github/workflows/agentic-v2-ghcp-sol-gate.yml").read_text(), Loader=yaml.BaseLoader)


def evaluate(condition, event, inputs):
    text = condition.removeprefix("${{").removesuffix("}}").strip()
    for name, value in inputs.items():
        text = text.replace("inputs." + name, repr(value))
    text = text.replace("github.event_name", repr(event))
    text = re.sub(r"needs\.[a-z-]+\.result", "'success'", text)
    text = text.replace("needs.ahp-connection.outputs.verified", "'true'")
    text = text.replace("always()", "True").replace("cancelled()", "False")
    text = text.replace(" == true", " == True").replace(" != true", " != True")
    text = text.replace(" == false", " == False").replace(" != false", " != False")
    return eval(text.replace("&&", " and ").replace("||", " or ").replace("!", "not ")
                .replace("not =", "!="), {"__builtins__": {}}, {})


@pytest.mark.parametrize("event", ["push", "pull_request", "workflow_dispatch"])
@pytest.mark.parametrize("paid,dry", [(False, False), (False, True), (True, False), (True, True)])
@pytest.mark.parametrize("connection,capability", [(False, False), (False, True), (True, False), (True, True)])
@pytest.mark.parametrize("adapter", ["ahp-draft", "copilot-cli"])
def test_actual_workflow_expressions_cannot_enter_any_other_job_in_zero_turn_mode(event, paid, dry, connection, capability, adapter):
    jobs = workflow()["jobs"]
    inputs = {"authenticated_zero_turn": True, "execute_paid": paid, "dry_run": dry,
              "connection_only": connection, "capability_only": capability, "execution_adapter": adapter}
    assert evaluate(jobs["ahp-zero-turn"]["if"], event, inputs) == (
        event == "workflow_dispatch" and not paid and dry and not connection and not capability and adapter == "ahp-draft")
    for job in ("plan", "task", "paid-task", "ahp-connection", "grader-contract"):
        assert evaluate(jobs[job]["if"], event, inputs) is False
    inputs["authenticated_zero_turn"] = False
    assert evaluate(jobs["ahp-zero-turn"]["if"], event, inputs) is False


def test_zero_turn_job_is_protected_and_tokens_are_never_in_commands_or_artifact_globs():
    value = workflow()
    assert value["on"]["workflow_dispatch"]["inputs"]["authenticated_zero_turn"] == {
        "type": "boolean", "default": "false", "required": "true",
        "description": "One authenticated session/thread with bounded metadata GETs; no inference, fixed five or grader"}
    job = value["jobs"]["ahp-zero-turn"]
    assert job["environment"] == "ghcp-sol-gate" and job["runs-on"] == "ubuntu-24.04"
    assert job["needs"] == "offline-ci" and "strategy" not in job and "outputs" not in job
    setup = next(step for step in job["steps"] if step.get("id") == "python")
    assert setup["with"]["python-version"] == "3.12.11"
    auth_steps = [step for step in job["steps"] if "secrets." in yaml.dump(step)]
    assert len(auth_steps) == 1
    step = auth_steps[0]
    assert step["env"] == {"COPILOT_GITHUB_TOKEN": "${{ secrets.COPILOT_GITHUB_TOKEN }}",
        "GHCP_AUTHENTICATED_ZERO_TURN": "true", "GHCP_PAID_EXECUTION": "false", "GHCP_CONNECTION_ONLY": "false"}
    # Namespace/privilege argv now live in the broker's exact launcher contract.
    for fragment in ("ghcp_ahp_metadata_broker.py", "--prepared", "--evidence", "150s"):
        assert fragment in step["run"]
    assert "$COPILOT_GITHUB_TOKEN" not in step["run"]
    assert "ghcp_ahp_connection.py" not in step["run"] and "execute-paid" not in step["run"]
    upload = job["steps"][-1]
    assert upload["if"] == "always()" and upload["with"]["path"].endswith("/evidence/*.json")
    assert not any("continue-on-error" in step for step in job["steps"])
    push = (ROOT / ".github/workflows/ghcp-ahp-model-free-probe.yml").read_text()
    assert "test_ghcp_ahp_zero_turn.py" in push
    assert "secrets." not in push and "--authenticated-zero-turn" not in push


@pytest.mark.parametrize("outcome", ["reported", "auth_refused", "session_refused", "no_thread", "http_blocked", "wrong_model"])
def test_full_authenticated_probe_exports_real_receipt_contract_and_always_cleans_up(
        backend_probe_fixture, context, monkeypatch, outcome):
    """Fake process/AHP/native bytes; real RPC/observer parsing/assessment/export."""
    def export(state, evidence, *, credential):
        assert credential == CANARY
        directory = state / "wire"
        directory.mkdir(exist_ok=True)
        rows = [{"kind": "observer_installed", "entrypoint": "vs/platform/agentHost/node/agentHostMain",
                 "model_free": True, "session_only": True, "observer_sha256": probe.digest(wire_capture.PRELOAD)}]
        if outcome in {"reported", "wrong_model"}:
            rows.extend([
                {"kind": "ipc_request", "stream": "ipc-1", "value": {"id": 2, "method": "thread/start", "params": {}}},
                {"kind": "ipc_response", "stream": "ipc-1", "value": {"id": 2, "result": {
                    "thread": {"id": "synthetic-thread"}, "model": "gpt-5.6-sol" if outcome == "reported" else "gpt-5.6-sol-fast",
                    "modelProvider": "vscode-proxy", "approvalPolicy": "untrusted", "reasoningEffort": "max",
                    "sandbox": {"type": "readOnly", "networkAccess": False}, "message": CANARY}}},
            ])
        if outcome == "http_blocked":
            rows.append({"kind": "blocked", "reason": "session_policy_http_refused", "boundary": "capi_or_http"})
        (directory / "wire-1.jsonl").write_text("".join(json.dumps({**row, "sequence": index, "synthetic": True}) + "\n"
                                                    for index, row in enumerate(rows, 1)))
        probe.save_json(directory / "bootstrap.json", {"session_policy": True, "authenticated_zero_turn": True,
            "observer_sha256": probe.digest(wire_capture.PRELOAD), "vscode_commit": wire_capture.PIN})
        probe.save_json(directory / "sources.json", {"synthetic": True})
        return REAL_EXPORT(state, evidence, credential=credential)

    monkeypatch.setattr(wire_capture, "export", export)
    monkeypatch.setattr(policy, "await_native_thread", lambda *args: {"replies": 0 if outcome == "no_thread" else 1})
    rpc_wire = Wire(auth_error=outcome == "auth_refused", session_error=outcome == "session_refused")
    receipt, calls, output = backend_probe_fixture(authenticated_zero_turn=True, transport_factory=lambda: rpc_wire)
    assert calls["stops"] >= 1
    assert receipt["authentication_supplied"] is True
    assert receipt["headless_started"] is True  # Auth/session denial does not erase the successful initialize.
    assert receipt["credential_environment_inherited"] is False
    assert receipt["model_calls"] == 0 and receipt["launch_allowed"] is False
    assert calls["exit_code"] == (0 if outcome in {"reported", "wrong_model"} else 2)
    if outcome == "auth_refused":
        assert receipt["reason_codes"][0] == "zero_turn_authentication_refused"
        assert len(rpc_wire.sent) == 2
    if outcome == "session_refused":
        assert receipt["reason_codes"][0] == "zero_turn_session_refused"
        assert len(rpc_wire.sent) == 3
        assert [row["op"] for row in receipt["management_sent"]] == ["configure", "readback", "create"]
    if outcome == "no_thread":
        assert "zero_turn_native_thread_not_reported" in receipt["reason_codes"]
    if outcome == "http_blocked":
        assert "session_policy_forbidden_activity" in receipt["reason_codes"]
    handshake = json.loads((output / "handshake.json").read_text())
    assert handshake["schema"] == "ghcp-ahp-authenticated-zero-turn-v1"
    assert handshake["admission_allowed"] is False
    assert handshake["auth_rpc_sent"] is True
    assert handshake["auth_rpc_succeeded"] is (outcome != "auth_refused")
    assert handshake["capi_requests"] == handshake["model_turn_start_requests"] == handshake["model_turn_events"] == 0
    assert handshake["observed"]["served_model"] == handshake["observed"]["web_search"] == "not_reported"
    if outcome in {"reported", "wrong_model"}:
        assert handshake["observed"]["approval"] == "untrusted"
        assert handshake["observed"]["reasoning_effort"] == "max"
        assert handshake["observed"]["context_window"] == "not_reported"
        assert handshake["verdicts"]["model"] == ("matches" if outcome == "reported" else "mismatch")
    for path in output.glob("*.json"):
        assert CANARY not in path.read_text(), path.name
    diagnostics = json.loads((output / "backend-startup.json").read_text())
    assert diagnostics["environment_contract"]["authentication_supplied"] is True
    assert diagnostics["session_create_requests"] == (0 if outcome == "auth_refused" else 1)
    assert not any("GHCP_AHP_WIRE_SEEDS" in " ".join(command) or CANARY in " ".join(command)
                   for command in calls["commands"])
