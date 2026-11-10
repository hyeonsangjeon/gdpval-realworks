"""Inert AHP/metadata servers, real adapters/validators; never a live auth receipt."""

import copy
import json
import socket
from pathlib import Path
from types import SimpleNamespace

import pytest

import ghcp_ahp_auth_smoke as smoke
import ghcp_ahp_auth_publication as pub
import ghcp_ahp_metadata_broker as broker
import ghcp_ahp_probe as probe
import ghcp_ahp_thread_policy as policy
import ghcp_ahp_wire_capture as wire
from ghcp_ahp_errors import Refused

CANARY = "SYNTHETIC_AuthSmoke_NotACredential_123456"
IDENTITY = {"github_run_id": "123", "github_run_attempt": "1", "github_sha": "a" * 40}
SESSION = "ahp-session:/aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa"
WORKSPACE = "file:///synthetic-empty-workspace"
MODEL_URL = "https://api.individual.githubcopilot.com/models"


@pytest.fixture(autouse=True)
def deny_real_effects(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("auth smoke unit fixture crossed a process/authentication/network boundary")
    monkeypatch.setattr(probe.subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(probe.urllib.request, "build_opener", forbidden)
    monkeypatch.setattr(broker.http.client, "HTTPSConnection", forbidden)


class FakeServers:
    def __init__(self):
        self.sent, self.fetches = [], []
        self.metadata = broker.Broker(CANARY, fetch=self.fetch)
        self.settings = None
        self.model_calls = self.turns = self.creates = 0

    def fetch(self, url, headers):
        assert headers["authorization"] == "Bearer " + CANARY
        self.fetches.append(url)
        data = {"endpoints": {"api": MODEL_URL.removesuffix("/models")}} if url == broker.USER_URL else {"data": [{"id": "gpt-5.6-sol"}]}
        return 200, {"content-type": "application/json"}, json.dumps(data).encode()

    def send(self, value):
        self.sent.append(copy.deepcopy(value))

    def receive(self):
        request = self.sent[-1]
        method = request["method"]
        result = {"message": "fake server echo " + CANARY}
        if method == "initialize":
            result = {"protocolVersion": "1.1.0", "snapshots": [{"resource": probe.ROOT_CHANNEL,
                "state": {"agents": [{"provider": "codex", "protectedResources": [{"resource": policy.AUTH_RESOURCE}]}]}}]}
        elif method == "authenticate":
            assert request["params"]["token"] == CANARY
            for url in (broker.USER_URL, MODEL_URL):
                response = self.metadata.request({"method": "GET", "url": url,
                    "headers": {"authorization": "Bearer " + CANARY, "accept": "application/json"}})
                assert response["status"] == 200
        elif method == "resolveSessionConfig":
            result = {"values": copy.deepcopy(policy.POLICY), "schema": {"properties": {}}}
        assert method in {"initialize", "authenticate", "resolveSessionConfig", "subscribe", "disposeSession"}
        return {"jsonrpc": "2.0", "id": request["id"], "result": result}

    def prepare(self, session, workspace, config):
        assert config == policy.POLICY
        self.settings = {"session": session, "workspace": workspace, "model": copy.deepcopy(probe.DESIRED_MODEL), "config": copy.deepcopy(config)}
        return {"settings": self.settings, "resolved_policy": copy.deepcopy(config), "derived_permissions": "vscode-workspace-read-only",
                "evidence": smoke.management.EVIDENCE, "admission_allowed": False}

    def create(self):
        assert self.settings and self.creates == 0
        self.creates += 1
        return {"result": {"scheme": "ahp-session", "path": SESSION.removeprefix("ahp-session:")},
                "transport": "vscode-child-ipc", "method": "createSessionWithExtensions"}


def refresh(values):
    """Rebuild redundant fields so mutations exercise the semantic rejection too."""
    previous = values["wire-capture.json"]
    capture = wire.analyze(previous["records"], synthetic=False)
    capture.update(bootstrap=previous["bootstrap"], capture_status=previous["capture_status"])
    values["wire-capture.json"] = capture
    h, p = values["handshake.json"], values["probe.json"]
    assessment = probe.redact(policy.assess(capture, h["rpc_results"]))
    values["thread-policy.json"] = assessment
    h.update(observed=assessment["observed"], origins=assessment["origins"], verdicts=assessment["verdicts"])
    for row in (h, p):
        row["thread_policy"] = {"path": "thread-policy.json", "sha256": pub.sha(pub.encoded(assessment))}
        row["wire_capture"] = {"path": "wire-capture.json", "sha256": pub.sha(pub.encoded(capture))}
    p["rpc_results"] = copy.deepcopy(h["rpc_results"])
    return {name: pub.encoded(value) for name, value in values.items()}


@pytest.fixture
def evidence():
    servers = FakeServers()
    rpc = probe.Rpc(servers, SESSION, WORKSPACE, session_policy=True, credential=CANARY)
    rpc.management = servers
    results = policy.exercise(rpc, lambda: {"replies": 1})
    rows = [{"kind": "observer_installed", "entrypoint": "vs/platform/agentHost/node/agentHostMain", "model_free": True,
             "session_only": True, "observer_sha256": probe.digest(wire.PRELOAD)}]
    for address in (broker.coordinates(broker.USER_URL), broker.coordinates(MODEL_URL)):
        rows.extend([{"kind": "metadata_request", "method": "GET", **address},
                     {"kind": "metadata_response", "method": "GET", **address, "status": 200, "external_request": True}])
    rows.extend([
        {"kind": "ipc_request", "stream": "ipc-1", "value": {"id": 2, "method": "thread/start", "params": {
            "model": "gpt-5.6-sol", "modelProvider": "vscode-proxy", "approvalPolicy": "untrusted",
            "permissions": "vscode-workspace-read-only", "config": {"web_search": "disabled", "mcp_servers": {},
                "model_context_window": 1000000, "model_reasoning_effort": "max"}}}},
        {"kind": "ipc_response", "stream": "ipc-1", "value": {"id": 2, "result": {"thread": {"id": "fixture-thread"},
            "model": "gpt-5.6-sol", "modelProvider": "vscode-proxy", "approvalPolicy": "untrusted", "reasoningEffort": "max",
            "sandbox": {"type": "readOnly", "networkAccess": False}}}},
    ])
    # Simulated runner bytes. These are never uploaded or claimed as real observations.
    rows = [{**row, "sequence": index, "process": "wire-1.jsonl", "synthetic": False} for index, row in enumerate(rows, 1)]
    capture = wire.analyze(rows, synthetic=False)
    capture.update(capture_status="captured", bootstrap={"vscode_commit": wire.PIN, "sdk_version": "0.163.0",
        "observer_sha256": probe.digest(wire.PRELOAD), "metadata_client_sha256": probe.digest(wire.METADATA_CLIENT),
        "management_bridge_sha256": probe.digest(wire.MANAGEMENT_BRIDGE), "model_free": True,
        "session_policy": True, "authenticated_zero_turn": True, "metadata_reads": True})
    handshake = {"schema": "ghcp-ahp-authenticated-zero-turn-v1", "runner": dict(IDENTITY), "status": "probe_completed",
        "reason_codes": [], "auth_rpc_sent": True, "auth_rpc_succeeded": True, "session_created": True, "metadata_reads": True,
        "admission_allowed": False, "requested_policy": copy.deepcopy(policy.POLICY), "requested_native_launch_args": list(policy.NATIVE_ARGS),
        "model_turn_start_requests": 0, "model_turn_events": 0, "capi_requests": 0, "rpc_sent": copy.deepcopy(rpc.sent),
        "rpc_results": results, "limits": {"turns": 0, "capi_inference_requests": 0, "metadata_gets": 2, "sessions": 1,
            "native_threads": 1, "wall_seconds": 120}}
    record = {"schema": "ghcp-ahp-probe-receipt-v1", "runner": dict(IDENTITY), "status": "probe_completed", "reason_codes": [],
        "vscode_commit": wire.PIN, "codex_sdk_version": "0.163.0", "authentication_supplied": True, "headless_started": True,
        "authenticated_zero_turn": True, "session_policy_probe": True, "metadata_reads": True, "credential_environment_inherited": False,
        "launch_allowed": False, "gate_ready": False, "model_calls": 0, "session_create_requests": 1,
        "cleanup": "owned_process_group_stopped_pid_namespace_exit_cleans_detached_children", "backend_readiness": {"ready": True},
        "rpc_sent": copy.deepcopy(rpc.sent), "isolation": {"interfaces": ["lo"], "pid_one": True, "unprivileged": True,
            "no_new_privileges": True, "network_namespace": "net:[2]", "outside_network_namespace": "net:[1]", "pid_namespace": "pid:[2]",
            "external_egress": "kernel_loopback_only", "cleanup_boundary": "all_descendants_die_when_pid_namespace_init_exits"}}
    values = {"probe.json": record, "handshake.json": handshake, "wire-capture.json": capture, "metadata-http.json": servers.metadata.receipt()}
    refresh(values)
    return values, servers, rpc


def test_fake_servers_traverse_real_auth_metadata_rpc_and_receipt_adapters(evidence):
    values, servers, rpc = evidence
    details = smoke.validate_evidence(refresh(values), IDENTITY)
    assert servers.fetches == [broker.USER_URL, MODEL_URL] and servers.creates == 1
    assert servers.model_calls == servers.turns == details["turns_sent"] == details["capi_inference_requests"] == 0
    assert details["authentication_transport_verified"] is True
    assert details["observed"]["served_model"] == details["observed"]["context_window"] == "not_reported"
    assert values["thread-policy.json"]["admission_allowed"] is False
    assert CANARY not in json.dumps([rpc.sent, rpc.received, values])


@pytest.mark.parametrize("method", ["turn/start", "item/start", "dispatchAction", "sendMessage", "thread/fork", "command/exec"])
def test_prompt_and_tool_work_is_refused_before_fake_server_send(evidence, method):
    _values, servers, rpc = evidence
    before = len(servers.sent)
    with pytest.raises(Refused):
        rpc.request(method, {"channel": SESSION, "text": "must never leave client"})
    assert len(servers.sent) == before and servers.model_calls == servers.turns == 0


@pytest.mark.parametrize("url,method", [("https://api.individual.githubcopilot.com/responses", "POST"),
    ("https://api.githubcopilot.com/chat/completions", "POST"), ("https://api.github.com/copilot_internal/v2/token", "GET"),
    (MODEL_URL + "?extra=1", "GET"), ("https://evil.invalid/models", "GET")])
def test_inference_exchange_and_non_exact_urls_never_reach_fake_fetch(evidence, url, method):
    _values, servers, _rpc = evidence
    assert "error" in servers.metadata.request({"method": method, "url": url, "headers": {"authorization": "Bearer " + CANARY}})
    assert servers.fetches == [broker.USER_URL, MODEL_URL]


@pytest.mark.parametrize("damage", ["http403", "http_missing", "http_extra", "http_redirect", "http_origin", "http_denial", "retry",
    "auth_missing", "session_missing", "thread_missing", "thread_duplicate", "turn", "item", "capi", "boundary_refusal",
    "model", "effort", "sandbox", "network", "approval", "request_model", "web_search", "context", "fallback",
    "observer_missing", "observer_hash", "sequence", "synthetic", "patched", "head", "isolation", "cleanup", "readback",
    "requested_policy", "bool_zero", "admission", "declared_hidden_turn"])
def test_missing_forged_or_unsafe_observations_cannot_pass_even_after_rehash(evidence, damage):
    values, _servers, _rpc = evidence
    p, h, w, m = (values[name] for name in ("probe.json", "handshake.json", "wire-capture.json", "metadata-http.json"))
    rows, request, response = w["records"], w["records"][-2]["value"]["params"], w["records"][-1]["value"]["result"]
    if damage == "http403": m["external_requests"][0]["status"] = 403
    elif damage == "http_missing": m["external_requests"].pop()
    elif damage == "http_extra": m["external_requests"].append(copy.deepcopy(m["external_requests"][0]))
    elif damage == "http_redirect": m["external_requests"][0]["status"] = 302
    elif damage == "http_origin": m["bound_models_url"] = "https://evil.invalid/models"
    elif damage == "http_denial": m["denials"].append({"reason": "refused"})
    elif damage == "retry": m["limits"]["retries"] = 1
    elif damage == "auth_missing": del h["rpc_results"]["authenticate"]
    elif damage == "session_missing": h["rpc_results"]["createSession"] = {"error": {"code": -32007}}
    elif damage == "thread_missing": del rows[-2:]
    elif damage == "thread_duplicate": rows.extend(copy.deepcopy(rows[-2:]))
    elif damage in {"turn", "item", "declared_hidden_turn"}: rows[-2]["value"]["method"] = "item/start" if damage == "item" else "turn/start"
    elif damage == "capi": rows.append({"kind": "capi_request", "stream": "http-1", "value": {"model": "gpt-5.6-sol"}})
    elif damage == "boundary_refusal": rows.append({"kind": "blocked", "reason": "session_policy_http_refused"})
    elif damage == "model": response["model"] = "gpt-5.6-sol-fast"
    elif damage == "effort": response["reasoningEffort"] = "xhigh"
    elif damage == "sandbox": response["sandbox"]["type"] = "workspaceWrite"
    elif damage == "network": response["sandbox"]["networkAccess"] = True
    elif damage == "approval": response["approvalPolicy"] = "on-request"
    elif damage == "request_model": request["model"] = "gpt-5.3-codex"
    elif damage == "web_search": request["config"]["web_search"] = "enabled"
    elif damage == "context": request["config"]["model_context_window"] = 999999
    elif damage == "fallback": request["allowProviderModelFallback"] = True
    elif damage == "observer_missing": rows[0]["kind"] = "not_an_observer"
    elif damage == "observer_hash": w["bootstrap"]["observer_sha256"] = "b" * 64
    elif damage == "sequence": rows[0]["sequence"] = 9
    elif damage == "synthetic": rows[0]["synthetic"] = True
    elif damage == "patched": w["bootstrap"]["patched_runtime_requested"] = True
    elif damage == "head": p["runner"]["github_sha"] = "b" * 40
    elif damage == "isolation": p["isolation"]["interfaces"].append("eth0")
    elif damage == "cleanup": p["cleanup"] = "unconfirmed"
    elif damage == "readback": h["rpc_results"]["management_initialize"]["derived_permissions"] = "vscode-workspace"
    elif damage == "requested_policy": h["requested_policy"]["codex.sandboxMode"] = "workspace-write"
    elif damage == "bool_zero": h["model_turn_start_requests"] = False
    elif damage == "admission": h["admission_allowed"] = True
    for index, row in enumerate(rows, 1):
        row.setdefault("process", "wire-1.jsonl")
        row.setdefault("sequence", index)
        row.setdefault("synthetic", False)
    with pytest.raises(Refused):
        smoke.validate_evidence(refresh(values), IDENTITY)


@pytest.fixture
def directories(tmp_path):
    prepared, preparation, output = (tmp_path / name for name in ("prepared", "preparation", "published"))
    prepared.mkdir()
    preparation.mkdir()
    for name in ("prepared.json", "source-evidence.json"):
        (preparation / name).write_bytes(b"{}\n")
    return prepared, preparation, output


def fake_runner(payloads, log=None):
    def run(prepared, evidence, credential):
        assert credential == CANARY and prepared.is_dir()
        for name, raw in payloads.items():
            (evidence / name).write_bytes(raw)
        return log or {"exit_code": 0, "stdout": "fake echo " + CANARY, "stderr": ""}
    return run


def test_full_fake_broker_boundary_publishes_only_scanned_non_admitting_receipt(evidence, directories):
    values, _servers, _rpc = evidence
    code, digest = smoke.execute(*directories, CANARY, IDENTITY, runner=fake_runner(refresh(values)))
    assert code == 0
    report = smoke.verify_publication(directories[2], digest, IDENTITY)
    assert report["authentication_transport_verified"] is True
    assert report["admission_allowed"] is report["execution_allowed"] is report["patched_ghcp"] is False
    assert all(CANARY not in p.read_text() for p in directories[2].iterdir())
    assert json.loads((directories[2] / "process-log.json").read_text())["stdout"] == "fake echo [REDACTED]"


@pytest.mark.parametrize("damage", ["child_failed", "raw_artifact_leak", "redactor_disabled", "encoded_log_leak", "partial_artifacts"])
def test_failures_publish_no_unvalidated_core_or_secret_and_do_not_claim_zero(evidence, directories, monkeypatch, damage):
    values, _servers, _rpc = evidence
    payloads = refresh(values)
    logs = {"exit_code": 0, "stdout": "fake echo " + CANARY, "stderr": ""}
    if damage == "child_failed": logs["exit_code"] = 2
    elif damage == "raw_artifact_leak": payloads["wire-capture.json"] = pub.encoded({"secret_echo": CANARY})
    elif damage == "redactor_disabled": monkeypatch.setattr(smoke.DiagnosticRedactor, "clean", lambda self, value: value)
    elif damage == "encoded_log_leak": logs["stdout"] = CANARY.encode().hex()
    else: del payloads["handshake.json"]
    code, digest = smoke.execute(*directories, CANARY, IDENTITY, runner=fake_runner(payloads, logs))
    assert code == 2
    report = smoke.verify_publication(directories[2], digest, IDENTITY)
    assert report["authentication_transport_verified"] is False and report["turns_sent"] == "not_reported"
    assert not {p.name for p in directories[2].iterdir()} & pub.CORE_FILES
    assert all(CANARY not in p.read_text() and CANARY.encode().hex() not in p.read_text() for p in directories[2].iterdir())


@pytest.fixture
def hosted_context(monkeypatch):
    values = {"GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REPOSITORY": smoke.REPOSITORY, "GITHUB_REF": smoke.BRANCH,
        "GITHUB_WORKFLOW_REF": smoke.WORKFLOW, "GITHUB_WORKFLOW_SHA": IDENTITY["github_sha"], "GHCP_AUTH_SMOKE_CONFIRM": "true",
        "GHCP_AUTHENTICATED_ZERO_TURN": "true", "GHCP_PAID_EXECUTION": "false", "GHCP_CONNECTION_ONLY": "false"}
    for key, value in values.items(): monkeypatch.setenv(key, value)
    monkeypatch.setattr(probe, "require_runner", lambda: dict(IDENTITY))
    return values


@pytest.mark.parametrize("key", ["GITHUB_EVENT_NAME", "GITHUB_REPOSITORY", "GITHUB_REF", "GITHUB_WORKFLOW_REF", "GITHUB_WORKFLOW_SHA",
    "GHCP_AUTH_SMOKE_CONFIRM", "GHCP_AUTHENTICATED_ZERO_TURN", "GHCP_PAID_EXECUTION", "GHCP_CONNECTION_ONLY"])
def test_context_mismatch_refuses_before_reading_or_launching(hosted_context, monkeypatch, key):
    monkeypatch.setenv(key, "mismatch")
    with pytest.raises(Refused): smoke.context(running=True)


def test_main_refuses_nas_and_invalid_arguments_without_echoing_secret(monkeypatch, capsys, tmp_path):
    def refuse(): raise Refused("not_hosted")
    monkeypatch.setattr(probe, "require_runner", refuse)
    monkeypatch.setenv("COPILOT_GITHUB_TOKEN", CANARY)
    assert smoke.main(["run", "--published", str(tmp_path / "out")]) == 2
    assert smoke.main(["--invalid", CANARY]) == 2
    assert probe.os.environ["COPILOT_GITHUB_TOKEN"] == CANARY
    assert capsys.readouterr() == ("", "")
    assert not (tmp_path / "out").exists()


def test_main_consumes_only_fake_env_and_writes_only_public_scan_digest(hosted_context, directories, monkeypatch, tmp_path, capsys):
    digest_file = tmp_path / "step-output"
    digest_file.touch()
    monkeypatch.setenv("COPILOT_GITHUB_TOKEN", CANARY)
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path))
    monkeypatch.setenv("GITHUB_OUTPUT", str(digest_file))
    def execute(prepared, preparation, published, credential, identity):
        assert credential == CANARY and identity == IDENTITY
        assert "COPILOT_GITHUB_TOKEN" not in probe.os.environ
        return 2, "c" * 64
    monkeypatch.setattr(smoke, "execute", execute)
    assert smoke.main(["run", "--prepared", str(directories[0]), "--preparation", str(directories[1]), "--published", str(directories[2])]) == 2
    assert digest_file.read_text() == "scan_sha256=" + "c" * 64 + "\n"
    assert capsys.readouterr() == ("", "")


def test_real_launcher_contract_is_bounded_and_never_puts_token_in_argv(hosted_context, directories, monkeypatch):
    calls = []
    class Process:
        def __init__(self, command, environment):
            calls.append((command, environment))
            self.process = SimpleNamespace(poll=lambda: 0)
        def check(self): pass
        def stop(self): calls.append("stopped")
        def record(self): return {"exit_code": 0, "stdout": "", "stderr": ""}
    monkeypatch.setattr(probe, "CapturedProcess", Process)
    assert smoke.run_broker(directories[0], directories[1], CANARY)["exit_code"] == 0
    command, environment = calls[0]
    assert CANARY not in json.dumps(command) and command[2].endswith("ghcp_ahp_metadata_broker.py")
    assert environment["COPILOT_GITHUB_TOKEN"] == CANARY
    assert not {"GH_TOKEN", "GITHUB_TOKEN", "OPENAI_API_KEY", "NODE_OPTIONS", "HTTP_PROXY", "HTTPS_PROXY"} & environment.keys()
    assert calls[-1] == "stopped"


@pytest.mark.parametrize("failure", ["timeout", "overflow"])
def test_captured_child_is_stopped_on_output_or_wall_limit(hosted_context, directories, monkeypatch, failure):
    calls = []
    class Process:
        def __init__(self, command, environment): self.process = SimpleNamespace(poll=lambda: None)
        def check(self):
            if failure == "overflow": raise Refused("process_output_limit_exceeded")
        def stop(self): calls.append("stopped")
        def record(self): pytest.fail("failed process was accepted")
    clock = iter([0, 166])
    monkeypatch.setattr(probe, "CapturedProcess", Process)
    monkeypatch.setattr(smoke.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(smoke.time, "sleep", lambda seconds: pytest.fail("continued after bound violation"))
    with pytest.raises(Refused):
        smoke.run_broker(directories[0], directories[1], CANARY)
    assert calls == ["stopped"]


def test_secret_free_verify_mode_never_consumes_the_environment_credential(hosted_context, monkeypatch, tmp_path):
    calls = []
    monkeypatch.setenv("COPILOT_GITHUB_TOKEN", CANARY)
    monkeypatch.setattr(smoke, "verify_publication", lambda directory, digest, identity: calls.append((directory, digest, identity)))
    assert smoke.main(["verify", "--published", str(tmp_path), "--scan-sha256", "d" * 64]) == 0
    assert calls == [(tmp_path, "d" * 64, IDENTITY)]
    assert probe.os.environ["COPILOT_GITHUB_TOKEN"] == CANARY


@pytest.mark.parametrize("damage", ["symlink", "outside_temp", "non_digest"])
def test_step_output_cannot_be_redirected_or_carry_arbitrary_text(monkeypatch, tmp_path, damage):
    owned = tmp_path / "owned"
    owned.mkdir()
    target = tmp_path / "outside"
    target.write_text("unchanged")
    output = owned / "output"
    output.touch()
    if damage == "symlink":
        output.unlink()
        output.symlink_to(target)
    elif damage == "outside_temp":
        output = target
    monkeypatch.setenv("RUNNER_TEMP", str(owned))
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    with pytest.raises(Refused):
        smoke.output_digest(CANARY if damage == "non_digest" else "f" * 64)
    assert target.read_text() == "unchanged"
