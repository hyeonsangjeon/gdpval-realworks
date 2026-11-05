"""Inert protocol/host-policy fixtures, never an installed agent host on NAS."""

import copy
import hashlib
import io
import json
import os
from pathlib import Path
import socket
import struct
import tarfile
from types import SimpleNamespace

import pytest
import yaml

import ghcp_ahp_probe as probe

ROOT = Path(__file__).resolve().parents[2]
SESSION = "ahp-session:/aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa"
WORKSPACE = "file:///synthetic-empty-workspace"
CANARY = "SYNTHETIC_CREDENTIAL_NOT_REAL_987654"


@pytest.fixture(autouse=True)
def deny_external_effects(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("offline fixture crossed a process or network boundary")
    monkeypatch.setattr(probe.subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(probe.urllib.request, "build_opener", forbidden)


def test_workflow_only_runs_on_the_named_branch_push_and_has_no_authentication_reference():
    text = (ROOT / ".github/workflows/ghcp-ahp-model-free-probe.yml").read_text()
    value = yaml.load(text, Loader=yaml.BaseLoader)
    assert value["on"] == {"push": {"branches": ["leader/ghcp-ahp-probe-20261030"]}}
    assert value["permissions"] == {"contents": "read"}
    assert set(value["jobs"]) == {"probe"}
    job = value["jobs"]["probe"]
    assert job["runs-on"] == "ubuntu-24.04"
    assert job["if"] == "github.event_name == 'push' && github.ref == 'refs/heads/leader/ghcp-ahp-probe-20261030'"
    assert "environment" not in job and "secrets" not in text.lower()
    assert "GITHUB_TOKEN" not in text and "COPILOT_GITHUB_TOKEN" not in text
    assert "workflow_dispatch" not in text and "pull_request" not in value["on"]
    assert job["timeout-minutes"] == "15"
    checkout = job["steps"][0]
    assert checkout["with"]["persist-credentials"] == "false"
    for step in job["steps"]:
        if "uses" in step:
            assert len(step["uses"].split("@")[-1]) == 40


@pytest.mark.parametrize("required", [
    "sudo unshare --mount --net --pid --fork --mount-proc --kill-child=KILL",
    "ip link set lo up", "--reuid=", "--regid=", "--bounding-set=-all",
    "--inh-caps=-all", "--ambient-caps=-all", "--no-new-privs", "/usr/bin/env -i",
    "--outside-netns", "--outside-pidns", "timeout --signal=TERM --kill-after=10s 240s",
    "RUNNER_ARCH=", "ImageVersion=", "GITHUB_RUN_ATTEMPT=",
])
def test_workflow_enforces_kernel_and_process_boundaries(required):
    assert required in (ROOT / ".github/workflows/ghcp-ahp-model-free-probe.yml").read_text()


def test_every_archive_has_a_fixed_version_and_hash_and_no_floating_runtime_download():
    manifest = probe.load_manifest()
    assert manifest["vscode_version"] == "1.144.0"
    assert manifest["vscode_commit"] == "2c33b50b16c472efe58357d1d2a8a5414bc23fbf"
    assert manifest["codex_sdk_version"] == "0.163.0"
    assert manifest["protocol_versions"] == ["1.1.0", "1.0.0"]
    for name, artifact in manifest["artifacts"].items():
        assert "latest" not in artifact["url"]
        assert len(artifact["sha256"]) == 64
        assert (manifest["codex_sdk_version"] if name == "codex_sdk" else manifest["vscode_commit"]) in artifact["url"]


@pytest.mark.parametrize("url", ["http://example.com/file", "https://example.com/file", "https://user:pass@codeload.github.com/file", "https://codeload.github.com/file?token=x", "https://codeload.github.com/file#fragment"])
def test_manifest_refuses_unapproved_or_credential_bearing_downloads(tmp_path, url):
    manifest = probe.load_manifest()
    manifest["artifacts"]["cli"]["url"] = url
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    with pytest.raises(probe.Refused, match="unsafe_download_url"):
        probe.load_manifest(path)


@pytest.mark.parametrize("key", ["token", "access_token", "refreshToken", "idToken", "connectionToken", "Authorization", "password", "api_key", "credentials"])
def test_sensitive_fields_never_survive_receipt_serialization(tmp_path, key):
    path = tmp_path / "receipt.json"
    probe.save_json(path, {key: CANARY, "tokenLimit": 1_000_000, "usage": {"input_tokens": 12}})
    text = path.read_text()
    assert CANARY not in text
    assert json.loads(text)["tokenLimit"] == 1_000_000
    assert json.loads(text)["usage"] == {"input_tokens": 12}


@pytest.mark.parametrize("text", [
    "access_token=" + CANARY, "refresh_token=" + CANARY, "idToken=" + CANARY,
    "OPENAI_API_KEY=" + CANARY, "COPILOT_GITHUB_TOKEN=" + CANARY,
    "connection_token: " + CANARY, "ws://127.0.0.1/?tkn=" + CANARY,
    "Authorization: Basic " + CANARY, "Bearer " + CANARY,
    "github_pat_" + CANARY, "gho_" + CANARY, "sk-" + CANARY,
])
def test_stdout_stderr_and_protocol_string_redaction(text):
    record = probe.redact({"stdout": text, "stderr": text, "rpc_received": [{"message": text}]})
    assert CANARY not in json.dumps(record)


def test_receipt_refuses_clobber(tmp_path):
    path = tmp_path / "receipt.json"
    probe.save_json(path, {"first": True})
    with pytest.raises(FileExistsError):
        probe.save_json(path, {"second": True})
    assert json.loads(path.read_text()) == {"first": True}


def test_child_environment_is_created_from_scratch_not_parent_values(tmp_path, monkeypatch):
    for key in ("COPILOT_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN", "OPENAI_API_KEY", "AZURE_CLIENT_SECRET", "ACTIONS_RUNTIME_TOKEN"):
        monkeypatch.setenv(key, CANARY)
    environment = probe.child_environment(tmp_path / "prepared", tmp_path)
    assert CANARY not in json.dumps(environment)
    assert not set(environment) & {"COPILOT_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN", "OPENAI_API_KEY", "AZURE_CLIENT_SECRET", "ACTIONS_RUNTIME_TOKEN", "CODEX_HOME"}
    assert environment["HOME"] == str(tmp_path / "home")
    assert environment["VSCODE_AGENT_HOST_CODEX_AGENT_ENABLED"] == "true"
    assert environment["VSCODE_AGENT_HOST_CLAUDE_AGENT_ENABLED"] == "false"


@pytest.mark.parametrize("mode", ["prepare", "probe"])
def test_real_entries_refuse_nas_before_any_file_or_network_or_process(tmp_path, monkeypatch, capsys, mode):
    monkeypatch.setattr(probe.runner, "observe", lambda: {"eligible_for_execution": False})
    result = probe.main([mode, "--prepared", str(tmp_path / "uncreated"), "--evidence", str(tmp_path / "uncreated-evidence")])
    assert result == 2
    assert "execution_environment_refused" in capsys.readouterr().out
    assert list(tmp_path.iterdir()) == []


def test_invalid_arguments_and_exception_messages_do_not_echo_values(capsys):
    assert probe.main(["--token", CANARY]) == 2
    output = capsys.readouterr()
    assert CANARY not in output.out + output.err
    assert str(probe.Refused(CANARY)) == "internal_probe_refusal"


@pytest.mark.parametrize("name", ["/absolute", "../escape", "a/../../escape", "windows\\escape", ""])
def test_unsafe_archive_names_are_refused(name):
    with pytest.raises(probe.Refused, match="unsafe_archive_member"):
        probe.checked_member(name)


def test_tar_special_file_cannot_be_extracted(tmp_path):
    path = tmp_path / "fixture.tgz"
    with tarfile.open(path, "w:gz") as archive:
        info = tarfile.TarInfo("pipe")
        info.type = tarfile.FIFOTYPE
        archive.addfile(info)
    with pytest.raises(probe.Refused, match="archive_special_file"):
        probe.extract_archive(path, tmp_path / "out")


def test_source_citations_are_computed_from_actual_pinned_bytes(tmp_path):
    path = tmp_path / "file.ts"
    path.write_text("header\nknownAnchor\nfooter\n")
    manifest = {"vscode_commit": "a" * 40, "citations": [{"id": "fixture", "path": "file.ts", "anchors": ["knownAnchor"]}]}
    report = probe.source_contract(manifest, tmp_path)
    citation = report["citations"][0]
    assert citation["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert citation["excerpts"][0]["line_start"] == 1
    assert "knownAnchor" in citation["excerpts"][0]["text"]
    assert report["applied_settings"] == {"served_model": "not_reported", "reasoning_effort": "not_reported", "context_window": "not_reported"}
    path.write_text("different source")
    with pytest.raises(probe.Refused, match="source_contract_anchor_missing"):
        probe.source_contract(manifest, tmp_path)


class FakeTransport:
    def __init__(self, overrides=None):
        self.sent = []
        self.overrides = overrides or {}

    def send(self, value):
        self.sent.append(copy.deepcopy(value))

    def receive(self):
        request = self.sent[-1]
        content = self.overrides.get(request["method"], {"result": {"protocolVersion": "1.1.0"} if request["method"] == "initialize" else None})
        return {"jsonrpc": "2.0", "id": request["id"], **copy.deepcopy(content)}


def test_empty_session_success_has_five_safe_requests_and_no_prompt_or_auth():
    transport = FakeTransport()
    rpc = probe.Rpc(transport, SESSION, WORKSPACE)
    results = probe.exercise_rpc(rpc)
    assert [r["method"] for r in transport.sent] == ["initialize", "resolveSessionConfig", "createSession", "subscribe", "disposeSession"]
    assert probe.classify_rpc(results)["session_created_without_auth"] is True
    assert probe.classify_rpc(results)["authentication"] == "not_reached_without_turn"
    for request in transport.sent:
        assert "model" not in request["params"] and "initialMessage" not in request["params"] and "prompt" not in request["params"]


def policy_transport(creation=None):
    import ghcp_ahp_thread_policy as policy
    return FakeTransport({"resolveSessionConfig": {"result": {"schema": {"properties": {}},
        "values": copy.deepcopy(policy.POLICY)}}, "createSession": creation or {"result": None}})


def test_session_policy_exact_hidden_keys_use_config_and_model_uses_native_launch_not_guessed_ahp_field():
    import ghcp_ahp_thread_policy as policy
    from ghcp_ahp_connection_transport import CONFIG

    transport = policy_transport()
    rpc = probe.Rpc(transport, SESSION, WORKSPACE, session_policy=True)
    observations = []
    result = policy.exercise(rpc, lambda: observations.append(True) or {"status": "fixture_only"})
    assert policy.POLICY == CONFIG
    assert [row["method"] for row in rpc.sent] == list(policy.METHODS)
    for row in rpc.sent[1:3]:
        assert row["params"]["config"] == CONFIG
        assert "codex.permissionsPreset" not in row["params"]["config"]
    assert set(rpc.sent[2]["params"]) == {"channel", "provider", "workingDirectories", "config"}
    assert 'model="gpt-5.6-sol"' in policy.NATIVE_ARGS
    assert 'model_provider="vscode-proxy"' in policy.NATIVE_ARGS
    assert 'model_reasoning_effort="max"' in policy.NATIVE_ARGS
    assert "model_context_window=1000000" in policy.NATIVE_ARGS
    assert observations == [True] and "disposeSession" in result
    assert all(row["method"] not in {"dispatchAction", "authenticate", "turn/start"} for row in rpc.sent)


def test_session_policy_upstream_auth_refusal_is_preserved_without_turn_or_retry():
    import ghcp_ahp_thread_policy as policy

    transport = policy_transport({"error": {"code": -32007, "message": "Authentication is required to use Codex"}})
    rpc = probe.Rpc(transport, SESSION, WORKSPACE, session_policy=True)
    def forbidden():
        pytest.fail("must not observe/prewarm after a refused session creation")
    result = policy.exercise(rpc, forbidden)
    assert result["createSession"]["error"]["code"] == -32007
    assert [row["method"] for row in rpc.sent] == list(policy.METHODS[:3])
    with pytest.raises(probe.Refused, match="session_policy_rpc_order_refused"):
        rpc.request("createSession", copy.deepcopy(rpc.sent[-1]["params"]))


@pytest.mark.parametrize("field,bad", [("codex.approvalPolicy", "never"), ("codex.sandboxMode", "workspace-write"),
    ("codex.networkAccessEnabled", 0), ("codex.webSearchMode", "cached"), ("codex.modelReasoningEffort", "xhigh"),
    ("codex.permissionsPreset", "default"), ("approvalPolicy", "untrusted")])
def test_session_policy_values_and_keys_cannot_be_substituted(field, bad):
    import ghcp_ahp_thread_policy as policy

    transport = policy_transport()
    rpc = probe.Rpc(transport, SESSION, WORKSPACE, session_policy=True)
    rpc.sent.append({"method": "initialize"})
    params = {"channel": probe.ROOT_CHANNEL, "provider": "codex", "workingDirectory": WORKSPACE,
              "config": {**policy.POLICY, field: bad}}
    with pytest.raises(probe.Refused, match="session_policy_config_refused"):
        rpc.request("resolveSessionConfig", params)
    assert transport.sent == []


@pytest.mark.parametrize("method", ["authenticate", "dispatchAction", "sendMessage", "turn/start", "thread/start", "createChat"])
def test_session_policy_other_ahp_methods_never_reach_transport(method):
    transport = policy_transport()
    rpc = probe.Rpc(transport, SESSION, WORKSPACE, session_policy=True)
    with pytest.raises(probe.Refused, match="session_policy_rpc_order_refused"):
        rpc.request(method, {})
    assert transport.sent == []


def test_session_policy_rejects_an_unsupported_model_key_in_create_session():
    import ghcp_ahp_thread_policy as policy

    transport = policy_transport()
    rpc = probe.Rpc(transport, SESSION, WORKSPACE, session_policy=True)
    rpc.sent.extend([{"method": "initialize"}, {"method": "resolveSessionConfig"}])
    with pytest.raises(probe.Refused, match="model_free_rpc_allowlist_refused"):
        rpc.request("createSession", {"channel": SESSION, "provider": "codex", "workingDirectories": [WORKSPACE],
            "config": policy.POLICY, "model": probe.DESIRED_MODEL})
    assert transport.sent == []


def test_session_policy_changed_resolver_echo_stops_before_creation():
    import ghcp_ahp_thread_policy as policy

    transport = policy_transport()
    transport.overrides["resolveSessionConfig"]["result"]["values"]["codex.sandboxMode"] = "workspace-write"
    rpc = probe.Rpc(transport, SESSION, WORKSPACE, session_policy=True)
    with pytest.raises(probe.Refused, match="session_policy_resolver_changed_request"):
        policy.exercise(rpc)
    assert [row["method"] for row in transport.sent] == ["initialize", "resolveSessionConfig"]


def test_session_policy_does_not_weaken_original_capability_only_or_default_allowlist():
    with pytest.raises(probe.Refused, match="invalid_capability_mode"):
        probe.Rpc(FakeTransport(), SESSION, WORKSPACE, capability_only=True, session_policy=True)
    for options in ({"capability_only": True}, {}):
        rpc = probe.Rpc(FakeTransport(), SESSION, WORKSPACE, **options)
        with pytest.raises(probe.Refused):
            rpc.request("createSession", {"channel": SESSION, "provider": "codex", "workingDirectories": [WORKSPACE], "config": {}})


@pytest.mark.parametrize("code", [-32007, -32002, -32602, -32603])
def test_auth_or_provider_errors_are_retained_without_login_or_model_retry(code):
    transport = FakeTransport({"createSession": {"error": {"code": code, "message": "synthetic refusal"}}})
    rpc = probe.Rpc(transport, SESSION, WORKSPACE)
    result = probe.classify_rpc(probe.exercise_rpc(rpc))
    assert len(transport.sent) == 3
    assert result["errors"] == [{"stage": "createSession", "code": code, "message": "synthetic refusal"}]
    assert result["authentication"] == ("authentication_required_reported" if code == -32007 else "not_reached_without_turn")
    assert result["session_created_without_auth"] is False


@pytest.mark.parametrize("method", ["authenticate", "dispatchAction", "sendMessage", "turn/start", "createChat", "resourceWrite", "tcpConnect", "runCommand"])
def test_other_rpc_methods_never_reach_transport(method):
    transport = FakeTransport()
    with pytest.raises(probe.Refused, match="model_free_rpc_allowlist_refused"):
        probe.Rpc(transport, SESSION, WORKSPACE).request(method, {"channel": SESSION})
    assert transport.sent == []


@pytest.mark.parametrize("extra", ["prompt", "initialMessage", "config", "model", "_meta", "credentials"])
def test_creation_extra_fields_cannot_smuggle_a_turn_or_credentials(extra):
    transport = FakeTransport()
    params = {"channel": SESSION, "provider": "codex", "workingDirectories": [WORKSPACE], extra: CANARY}
    with pytest.raises(probe.Refused, match="model_free_rpc_allowlist_refused"):
        probe.Rpc(transport, SESSION, WORKSPACE).request("createSession", params)
    assert transport.sent == []


def test_rpc_budget_blocks_before_sending():
    transport = FakeTransport()
    rpc = probe.Rpc(transport, SESSION, WORKSPACE)
    for _ in range(probe.MAX_RPCS):
        rpc.request("subscribe", {"channel": SESSION})
    with pytest.raises(probe.Refused, match="rpc_count_limit"):
        rpc.request("subscribe", {"channel": SESSION})
    assert len(transport.sent) == probe.MAX_RPCS


@pytest.mark.parametrize("reply,reason", [
    ({"id": True, "result": None}, "rpc_response_identity_mismatch"),
    ({"id": 99, "result": None}, "rpc_response_identity_mismatch"),
    ({"result": None, "error": {}}, "rpc_response_identity_mismatch"),
    ({"error": None}, "malformed_rpc_error"),
    ({"method": "authenticate", "params": {}}, "server_request_not_authorized"),
    ({"method": "notification", "params": {"action": {"type": "chat/turnStarted"}}}, "unexpected_turn_or_tool_activity"),
])
def test_invalid_or_active_turn_messages_stop_the_probe(reply, reason):
    transport = FakeTransport({"subscribe": reply})
    with pytest.raises(probe.Refused, match=reason):
        probe.Rpc(transport, SESSION, WORKSPACE).request("subscribe", {"channel": SESSION})


def test_client_websocket_frames_are_masked_and_preserve_json_bytes():
    payload = b'{"jsonrpc":"2.0","method":"subscribe"}'
    frame = probe.encode_frame(payload, mask=b"abcd")
    assert frame[:2] == bytes([0x81, 0x80 | len(payload)])
    assert bytes(v ^ frame[2 + i % 4] for i, v in enumerate(frame[6:])) == payload


@pytest.mark.parametrize("length", [126, 65536])
def test_large_client_frame_length_encoding(length):
    frame = probe.encode_frame(b"x" * length, mask=b"abcd")
    assert frame[1] == (0xFE if length == 126 else 0xFF)
    assert struct.unpack("!H" if length == 126 else "!Q", frame[2:4] if length == 126 else frame[2:10])[0] == length


def test_oversized_frame_refused_before_any_socket_write():
    with pytest.raises(probe.Refused, match="websocket_frame_limit"):
        probe.encode_frame(b"x" * (probe.MAX_FRAME_BYTES + 1))


def fixture_websocket(frames):
    ws = probe.WebSocket.__new__(probe.WebSocket)
    ws.buffer = bytearray(frames)
    ws.total = 0
    ws.deadline = probe.time.monotonic() + 1
    ws.socket = SimpleNamespace(sendall=lambda _: None)
    return ws


def test_server_frame_and_fragmented_message_are_decoded_without_network():
    payload = b'{"result":null}'
    assert fixture_websocket(bytes([0x81, len(payload)]) + payload).receive() == {"result": None}
    first, second = payload[:5], payload[5:]
    frames = bytes([0x01, len(first)]) + first + bytes([0x80, len(second)]) + second
    assert fixture_websocket(frames).receive() == {"result": None}


@pytest.mark.parametrize("frames,reason", [
    (bytes([0x81, 0x80]), "unsupported_websocket_frame"),
    (bytes([0xC1, 0]), "unsupported_websocket_frame"),
    (bytes([0x82, 0]), "unexpected_websocket_opcode"),
    (bytes([0x88, 0]), "websocket_closed"),
    (bytes([0x81, 127]) + struct.pack("!Q", probe.MAX_FRAME_BYTES + 1), "websocket_frame_limit"),
])
def test_invalid_server_frames_fail_closed(frames, reason):
    with pytest.raises(probe.Refused, match=reason):
        fixture_websocket(frames).receive()


@pytest.mark.parametrize("changes,reason", [
    ({"netns": "net:[1]"}, "network_namespace_not_isolated"),
    ({"pidns": "pid:[1]"}, "pid_namespace_not_isolated"),
    ({"pid": 100}, "pid_namespace_not_isolated"),
    ({"uid": 0}, "root_runtime_refused"),
    ({"interfaces": [(1, "lo"), (2, "eth0")]}, "external_network_interface_present"),
    ({"status": "NoNewPrivs:\t0\nCapEff:\t0000\n"}, "privilege_drop_not_verified"),
    ({"status": "NoNewPrivs:\t1\nCapEff:\t0001\n"}, "privilege_drop_not_verified"),
])
def test_isolation_cannot_be_claimed_from_just_a_flag(monkeypatch, changes, reason):
    facts = {"netns": "net:[2]", "pidns": "pid:[2]", "pid": 1, "uid": 1001, "interfaces": [(1, "lo")], "status": "NoNewPrivs:\t1\nCapEff:\t0000\n", **changes}
    monkeypatch.setattr(probe.os, "readlink", lambda p: facts["netns"] if p.endswith("/net") else facts["pidns"])
    monkeypatch.setattr(probe.os, "getpid", lambda: facts["pid"])
    monkeypatch.setattr(probe.os, "geteuid", lambda: facts["uid"])
    monkeypatch.setattr(probe.socket, "if_nameindex", lambda: facts["interfaces"])
    monkeypatch.setattr(probe.Path, "read_text", lambda self: facts["status"])
    with pytest.raises(probe.Refused, match=reason):
        probe.require_isolation("net:[1]", "pid:[1]")


def test_runtime_contains_no_direct_provider_client_or_completion_path():
    source = (ROOT / "batch-runner/ghcp_ahp_probe.py").read_text()
    assert "import openai" not in source and "DefaultAzureCredential" not in source
    assert probe.ALLOWED_METHODS == {"initialize", "resolveSessionConfig", "createSession", "subscribe", "disposeSession"}
    assert probe.DESIRED_MODEL == {"id": "@provider=vscode-proxy:gpt-5.6-sol", "config": {"thinkingLevel": "max", "contextSize": 1_000_000}}


@pytest.mark.parametrize("text,reason", [
    ('{"id":1,"id":2}', "duplicate_json_key"),
    ('{"value":NaN}', "invalid_json_number"),
    ('{"value":Infinity}', "invalid_json_number"),
    ('{"value":-Infinity}', "invalid_json_number"),
])
def test_ambiguous_json_is_not_protocol_evidence(text, reason):
    with pytest.raises(probe.Refused, match=reason):
        probe.strict_json(text)


@pytest.mark.parametrize("provider", ["copilot", "claude", "openai", ""])
def test_wrong_provider_is_refused_before_sending(provider):
    transport = FakeTransport()
    with pytest.raises(probe.Refused, match="foreign_provider_refused"):
        probe.Rpc(transport, SESSION, WORKSPACE).request("createSession", {"channel": SESSION, "provider": provider, "workingDirectories": [WORKSPACE]})
    assert transport.sent == []


def synthetic_preparation(tmp_path):
    manifest = probe.load_manifest()
    root = tmp_path / "root"
    evidence = tmp_path / "evidence"
    server = f"cli-data/servers/Stable-{manifest['vscode_commit']}/server"
    files = {"cli": "cli/code", "node": server + "/node", "server_launcher": server + "/bin/code-server"}
    for name, relative in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(("inert bytes, never execute " + name).encode())
    probe.save_json(evidence / "source-evidence.json", {"status": "synthetic_only"})
    prepared = {"vscode_commit": manifest["vscode_commit"], "runner": {"github_sha": "f" * 40},
                "artifacts": manifest["artifacts"], "source_evidence_sha256": probe.digest(evidence / "source-evidence.json"),
                "binary_sha256": {name: {"relative_path": path, "sha256": probe.digest(root / path)} for name, path in files.items()}}
    return manifest, root, evidence, prepared


def test_preparation_binding_is_consistency_not_execution(tmp_path):
    manifest, root, evidence, prepared = synthetic_preparation(tmp_path)
    probe.save_json(evidence / "prepared.json", prepared)
    assert probe.verify_prepared(manifest, root, evidence, {"github_sha": "f" * 40})[0] == prepared


@pytest.mark.parametrize("change,reason", [
    ("commit", "prepared_identity_mismatch"),
    ("artifact", "prepared_artifact_identity_mismatch"),
    ("set", "prepared_binary_set_mismatch"),
    ("path", "prepared_binary_path_mismatch"),
    ("bytes", "prepared_binary_drift"),
    ("source", "source_evidence_drift"),
])
def test_tampered_preparation_is_rejected_before_a_process(tmp_path, change, reason):
    manifest, root, evidence, prepared = synthetic_preparation(tmp_path)
    if change == "commit":
        prepared["runner"]["github_sha"] = "0" * 40
    elif change == "artifact":
        prepared["artifacts"] = copy.deepcopy(prepared["artifacts"])
        prepared["artifacts"]["cli"]["sha256"] = "0" * 64
    elif change == "set":
        del prepared["binary_sha256"]["node"]
    elif change == "path":
        prepared["binary_sha256"]["cli"]["relative_path"] = "../private"
    elif change == "bytes":
        (root / "cli/code").write_bytes(b"changed")
    elif change == "source":
        (evidence / "source-evidence.json").write_text("{}")
    probe.save_json(evidence / "prepared.json", prepared)
    with pytest.raises(probe.Refused, match=reason):
        probe.verify_prepared(manifest, root, evidence, {"github_sha": "f" * 40})


@pytest.fixture
def backend_probe_fixture(tmp_path, monkeypatch):
    """Exercise the real cleanup path with no host, SDK, provider or socket peer."""
    import ghcp_ahp_wire_capture as wire

    manifest = probe.load_manifest()
    calls = {"commands": [], "stops": 0}
    sockets = []
    monkeypatch.setattr(probe, "require_runner", lambda: {"synthetic": True})
    monkeypatch.setattr(probe, "require_isolation", lambda *args: {"synthetic": True})
    monkeypatch.setattr(probe, "verify_prepared", lambda *args: (
        {"artifacts": {}, "binary_sha256": {}, "source_evidence_sha256": "0" * 64}, {}))
    monkeypatch.setattr(wire, "install", lambda root, scratch, environment, **kwargs: environment)
    monkeypatch.setattr(wire, "export", lambda *args: {"capture_status": "observer_not_started"})

    def stop():
        calls["stops"] += 1

    def fake_process(command, environment, cwd=None):
        calls["commands"].append(command)
        if command[-1] in {"--version", "--help"}:
            text = (manifest["vscode_version"] + " " + manifest["vscode_commit"] if command[-1] == "--version"
                    else "--foreground --new-instance --without-connection-token --log")
            return SimpleNamespace(finish=lambda: {"exit_code": 0, "stdout": text})
        calls["scratch"] = Path(environment["HOME"]).parent
        fixture_socket = synthetic_backend_signal(calls["scratch"], calls["readiness"])
        if fixture_socket is not None:
            sockets.append(fixture_socket)
        return SimpleNamespace(
            process=SimpleNamespace(pid=999999999, poll=lambda: None), check=lambda: None, stop=stop,
            record=lambda: {"command": command, "exit_code": -15 if calls["stops"] else None,
                            "stdout": "backend synthetic stdout", "stderr": "backend synthetic stderr"})

    monkeypatch.setattr(probe, "CapturedProcess", fake_process)

    def run(error=None, *, readiness="ready", session_policy=False, session_reply=None,
            authenticated_zero_turn=False, transport_factory=None):
        calls["readiness"] = readiness
        def refused_transport(*args):
            if error is None:
                transport = (transport_factory() if transport_factory else
                             policy_transport(session_reply) if session_policy else FakeTransport())
                transport.close = lambda: None
                return transport
            raise error
        monkeypatch.setattr(probe, "WebSocket", refused_transport)
        output = tmp_path / "evidence"
        calls["exit_code"] = probe.run_probe(manifest, tmp_path / "prepared", output, "fixture", "fixture",
            **({"session_policy": True, "authenticated_zero_turn": True, "credential": "SYNTHETIC_AuthZeroTurn_NotACredential_123456"}
               if authenticated_zero_turn else {"session_policy": True} if session_policy else {"capability_only": True}))
        return json.loads((output / "probe.json").read_text()), calls, output

    try:
        yield run
    finally:
        for fixture_socket in sockets:
            fixture_socket.close()


def synthetic_backend_signal(scratch, mode):
    """Filesystem-only readiness evidence; no server or socket peer is run."""
    folder = scratch / "tmp"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "agent"
    fixture_socket = None
    if mode != "missing_socket":
        fixture_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        fixture_socket.bind(str(target))
    if mode == "missing_log":
        return fixture_socket
    log = scratch / "home/.vscode-server/cli/agent-host-stable.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"debug [2c33b50 stdout]: [AgentHostChannel] Registered IPC channel 'agentHostProxy' (upstream: {target})"]
    if mode in {"ready", "missing_socket", "conflict", "truncated"}:
        lines.append(f"debug [2c33b50 stdout]: Agent host server listening on {target}")
    if mode == "wrong_socket":
        lines.append(f"debug [2c33b50 stdout]: Agent host server listening on {folder / 'other'}")
    if mode == "conflict":
        lines.append(f"debug [2c33b50 stdout]: Agent host server listening on {folder / 'other'}")
    if mode == "timeout":
        lines.append("warn [2c33b50]: Server did not become ready within 30s")
    lines.append("info [2c33b50]: Server ready")
    if mode == "truncated":
        lines.append("x" * (128 * 1024))
    log.write_text("\n".join(lines) + "\n")
    return fixture_socket


def test_timeout_ready_banner_cannot_admit_fake_handshake(backend_probe_fixture, monkeypatch):
    import ghcp_ahp_wire_capture as wire

    monkeypatch.setattr(wire, "export", lambda *args: {"capture_status": "captured"})
    receipt, calls, output = backend_probe_fixture(readiness="timeout")
    assert calls["exit_code"] == 2
    assert receipt["headless_started"] is False
    assert receipt.get("rpc_sent", []) == []
    assert receipt["reason_codes"][0] == "agent_host_backend_not_ready"


@pytest.mark.parametrize("mode", ["banner_only", "missing_socket", "missing_log", "wrong_socket", "conflict", "truncated"])
def test_missing_or_unbound_backend_readiness_blocks_before_first_rpc(backend_probe_fixture, monkeypatch, mode):
    import ghcp_ahp_wire_capture as wire

    monkeypatch.setattr(wire, "export", lambda *args: {"capture_status": "captured"})
    receipt, calls, output = backend_probe_fixture(readiness=mode)
    assert calls["exit_code"] == 2
    assert receipt["backend_readiness"]["ready"] is False
    assert receipt["reason_codes"] == ["agent_host_backend_not_ready"]
    assert receipt.get("rpc_sent", []) == []
    assert receipt["model_calls"] == receipt["session_create_requests"] == 0


@pytest.mark.parametrize("damage", ["socket_symlink", "log_symlink", "outside_target", "late_ready"])
def test_backend_readiness_never_follows_aliases_or_accepts_post_timeout_signal(tmp_path, damage):
    import ghcp_ahp_backend_diagnostics as backend

    scratch = tmp_path / "owned"
    fixture_socket = synthetic_backend_signal(scratch, "ready")
    try:
        log = scratch / "home/.vscode-server/cli/agent-host-stable.log"
        target = scratch / "tmp/agent"
        if damage == "socket_symlink":
            target.rename(scratch / "tmp/alias")
            target.symlink_to(scratch / "tmp/alias")
        elif damage == "log_symlink":
            log.rename(log.with_name("alias"))
            log.symlink_to(log.with_name("alias"))
        elif damage == "outside_target":
            log.write_text(log.read_text().replace(str(target), "/outside/invocation/socket"))
        else:
            log.write_text("Server did not become ready within 30s\n" + log.read_text())
        assert backend.readiness(scratch)["ready"] is False
    finally:
        fixture_socket.close()


@pytest.mark.parametrize("error,code", [
    (probe.Refused("websocket_handshake_rejected"), "websocket_handshake_rejected"),
    (RuntimeError(CANARY), "RuntimeError"),
])
def test_backend_failure_is_not_replaced_by_observer_cleanup(backend_probe_fixture, error, code):
    receipt, calls, output = backend_probe_fixture(error)
    assert receipt["reason_codes"] == [code, "wire_observer_not_started"]
    assert calls["exit_code"] == 2
    assert receipt["session_create_requests"] == receipt["model_calls"] == 0
    assert calls["stops"] == 1 and not calls["scratch"].exists()
    assert CANARY not in (output / "probe.json").read_text()


def test_backend_receipt_preserves_pre_cleanup_state_and_does_not_inflate_exit_evidence(backend_probe_fixture):
    import ghcp_ahp_backend_diagnostics as backend

    receipt, calls, output = backend_probe_fixture(probe.Refused("websocket_closed"))
    assert calls["commands"][-1][-2:] == ["--log", "debug"]
    assert probe.MAX_RUNTIME_SECONDS == 180  # No timeout inflation.
    assert receipt["backend_startup"]["sha256"] == probe.digest(output / "backend-startup.json")
    diagnostics = json.loads((output / "backend-startup.json").read_text())
    assert diagnostics["primary_error_code"] == "websocket_closed"
    assert diagnostics["before_cleanup"]["supervisor"]["exit_code"] is None
    assert diagnostics["after_cleanup"]["supervisor"]["exit_code"] == -15
    assert diagnostics["before_cleanup"]["supervisor"]["stdout"] == "backend synthetic stdout"
    assert diagnostics["after_cleanup"]["supervisor"]["stderr"] == "backend synthetic stderr"
    assert diagnostics["environment_contract"]["authentication_supplied"] is False
    assert diagnostics["environment_contract"]["display_present"] is False
    assert diagnostics["admission_allowed"] is False
    assert diagnostics["session_create_requests"] == diagnostics["model_calls"] == 0
    assert not calls["scratch"].exists()
    assert backend.MAX_FILE_BYTES <= probe.MAX_LOG_BYTES


@pytest.mark.parametrize("secondary", ["snapshot", "export", "wire_export"])
def test_backend_diagnostic_error_cannot_skip_cleanup_or_hide_primary(backend_probe_fixture, monkeypatch, secondary):
    import ghcp_ahp_backend_diagnostics as backend
    import ghcp_ahp_wire_capture as wire

    def refused(*args, **kwargs):
        raise probe.Refused("backend_diagnostic_fixture_refused")
    monkeypatch.setattr(wire if secondary == "wire_export" else backend,
                        "export" if secondary == "wire_export" else secondary, refused)
    receipt, calls, output = backend_probe_fixture(probe.Refused("websocket_closed"))
    assert receipt["reason_codes"][0] == "websocket_closed"
    assert "backend_diagnostic_fixture_refused" in receipt["reason_codes"]
    assert calls["stops"] == 1 and calls["exit_code"] == 2
    assert not calls["scratch"].exists()
    assert receipt["session_create_requests"] == receipt["model_calls"] == 0


def test_stop_error_is_secondary_and_never_reported_as_confirmed_cleanup(backend_probe_fixture, monkeypatch):
    original = probe.CapturedProcess

    def process(command, *args, **kwargs):
        value = original(command, *args, **kwargs)
        if command[-1] not in {"--version", "--help"}:
            def stop():
                raise probe.Refused("fixture_stop_unconfirmed")
            value.stop = stop
        return value
    monkeypatch.setattr(probe, "CapturedProcess", process)
    receipt, calls, output = backend_probe_fixture(probe.Refused("websocket_closed"))
    assert receipt["reason_codes"] == ["websocket_closed", "fixture_stop_unconfirmed", "wire_observer_not_started"]
    assert receipt["cleanup"] == "process_group_stop_unconfirmed_pid_namespace_exit_remains_cleanup_boundary"
    assert calls["exit_code"] == 2


def test_observer_absence_alone_still_refuses_after_successful_fake_handshake(backend_probe_fixture):
    receipt, calls, output = backend_probe_fixture()
    assert receipt["reason_codes"] == ["wire_observer_not_started"]
    assert calls["exit_code"] == 2
    assert receipt["headless_started"] is True
    assert [row["method"] for row in receipt["rpc_sent"]] == ["initialize", "resolveSessionConfig"]
    assert receipt["session_create_requests"] == receipt["model_calls"] == 0


def test_successful_fake_observer_still_cannot_admit_paid_execution(backend_probe_fixture, monkeypatch):
    import ghcp_ahp_wire_capture as wire

    monkeypatch.setattr(wire, "export", lambda *args: {"capture_status": "captured"})
    receipt, calls, output = backend_probe_fixture()
    assert calls["exit_code"] == 0 and receipt["reason_codes"] == []
    assert receipt["status"] == "probe_completed"
    assert receipt["launch_allowed"] is receipt["gate_ready"] is False
    assert receipt["session_create_requests"] == receipt["model_calls"] == 0


@pytest.mark.parametrize("created,safety_violation", [(False, False), (True, False), (True, True)])
def test_full_session_policy_probe_exports_refusal_or_native_missing_without_admission(backend_probe_fixture, monkeypatch, created, safety_violation):
    import ghcp_ahp_wire_capture as wire
    import ghcp_ahp_thread_policy as policy

    def exported(state, output):
        captured = wire.analyze([], synthetic=True)
        captured.update(capture_status="captured", bootstrap={"session_policy": True})
        if safety_violation:
            captured["capture_errors"].append("session_policy_http_refused")
        probe.save_json(output / "wire-capture.json", captured)
        return {"capture_status": "captured", "synthetic": True}
    monkeypatch.setattr(wire, "export", exported)
    monkeypatch.setattr(policy, "await_native_thread", lambda *args: {"status": "fixture_no_thread", "replies": 0})
    reply = {"result": None} if created else {"error": {"code": -32007, "message": "Authentication is required to use Codex"}}
    receipt, calls, output = backend_probe_fixture(session_policy=True, session_reply=reply)
    assert calls["exit_code"] == (2 if safety_violation else 0)
    assert receipt["session_create_requests"] == 1 and receipt["model_calls"] == 0
    assert [row["method"] for row in receipt["rpc_sent"]] == list(policy.METHODS if created else policy.METHODS[:3])
    result = json.loads((output / "thread-policy.json").read_text())
    assert result["session_created"] is created
    assert result["native_thread_responses"] == 0 and result["admission_allowed"] is False
    assert set(result["observed"].values()) == {"not_reported"}
    assert receipt["thread_policy"]["sha256"] == probe.digest(output / "thread-policy.json")
    if not created:
        assert result["session_error"]["code"] == -32007
    assert not calls["scratch"].exists()


def test_spawn_failure_still_exports_diagnostics_without_inventing_a_process(backend_probe_fixture, monkeypatch):
    original = probe.CapturedProcess

    def process(command, *args, **kwargs):
        if command[-1] not in {"--version", "--help"}:
            raise PermissionError(CANARY)
        return original(command, *args, **kwargs)
    monkeypatch.setattr(probe, "CapturedProcess", process)
    receipt, calls, output = backend_probe_fixture()
    assert receipt["reason_codes"][0] == "PermissionError"
    assert calls["stops"] == 0 and calls["exit_code"] == 2
    diagnostics = json.loads((output / "backend-startup.json").read_text())
    assert diagnostics["before_cleanup"]["supervisor"] is None
    assert diagnostics["after_cleanup"]["processes"] is None
    assert CANARY not in (output / "backend-startup.json").read_text()


def test_startup_tree_captures_sockets_and_only_allowed_logs_without_following_symlinks(tmp_path, monkeypatch):
    import ghcp_ahp_backend_diagnostics as backend

    scratch = tmp_path / "owned"
    logs = scratch / "server-data/logs/fixture"
    logs.mkdir(parents=True)
    token = "ghp_SYNTHETIC_0123456789"
    (logs / "remoteagent.log").write_text(f"backend stderr Authorization: Bearer {token}\nfixture@example.invalid\n")
    (logs / "account.json").write_text(CANARY)
    external = tmp_path / "external"
    external.mkdir()
    (external / "remoteagent.log").write_text(CANARY)
    (logs / "agenthost.log").symlink_to(external / "remoteagent.log")
    (scratch / "outside").symlink_to(external, target_is_directory=True)
    os.mkfifo(logs / "agentHost.log")
    reads = []
    original = backend._read

    def read(path, *args):
        reads.append(path)
        return original(path, *args)
    monkeypatch.setattr(backend, "_read", read)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as fixture_socket:
        fixture_socket.bind(str(scratch / "backend.sock"))
        report = backend.snapshot(scratch, None)
    assert reads == [logs / "remoteagent.log"]
    inventory = {row["path"]: row for row in report["filesystem"]["entries"]}
    assert inventory["backend.sock"]["kind"] == "socket"
    assert inventory["outside"]["kind"] == "symlink"
    assert inventory["server-data/logs/fixture/agentHost.log"]["kind"] == "other"
    retained = json.dumps(report)
    assert token not in retained and CANARY not in retained and "fixture@example.invalid" not in retained
    assert "[REDACTED]" in retained


def test_startup_diagnostic_limits_are_explicit_not_silent_success(tmp_path, monkeypatch):
    import ghcp_ahp_backend_diagnostics as backend

    scratch = tmp_path / "owned"
    logs = scratch / "server-data/logs/fixture"
    logs.mkdir(parents=True)
    (logs / "remoteagent.log").write_text("x" * (backend.MAX_FILE_BYTES + 10))
    report = backend.snapshot(scratch, None)
    assert report["filesystem"]["logs"][0]["truncated"] is True
    assert len(report["filesystem"]["logs"][0]["content"]) == backend.MAX_FILE_BYTES
    monkeypatch.setattr(backend, "MAX_ENTRIES", 1)
    report = backend.snapshot(scratch, None)
    assert report["filesystem"]["truncated"] is True
    assert len(report["filesystem"]["entries"]) == 1


def test_log_read_race_cannot_expand_the_diagnostic_inventory_budget(tmp_path, monkeypatch):
    import ghcp_ahp_backend_diagnostics as backend

    scratch = tmp_path / "owned"
    logs = scratch / "server-data/logs"
    logs.mkdir(parents=True)
    (logs / "remoteagent.log").write_text("inert fixture")
    (logs / "agenthost.log").write_text("inert fixture")
    monkeypatch.setattr(backend, "MAX_ENTRIES", 3)

    def raced(*args):
        raise FileNotFoundError("fixture log removed between listing and read")
    monkeypatch.setattr(backend, "_read", raced)
    inventory = backend.snapshot(scratch, None)["filesystem"]
    assert len(inventory["entries"]) + len(inventory["errors"]) <= 3
    assert inventory["truncated"] is True


@pytest.mark.parametrize("state,raw_status,expected_exit", [("S", 0, None), ("Z", 0, 0), ("Z", 7 << 8, 7), ("Z", 15, -15)])
def test_owned_process_exit_and_socket_arguments_are_not_fabricated(tmp_path, state, raw_status, expected_exit):
    import ghcp_ahp_backend_diagnostics as backend

    scratch = tmp_path / "owned"
    scratch.mkdir()
    proc = tmp_path / "proc"
    for pid, parent, children in [(100, 1, "101"), (101, 100, "")]:
        path = proc / str(pid)
        (path / "task" / str(pid)).mkdir(parents=True)
        tail = [state, str(parent)] + ["0"] * 47 + [str(raw_status)]
        (path / "stat").write_text(f"{pid} (inert ) fixture) " + " ".join(tail))
        (path / "cmdline").write_text("\0".join(["/fixture/node", "inline-code-" + CANARY,
            "--agent-host-path", str(scratch / "tmp/agent.sock"), "--socket-path", "/outside/forbidden", ""]))
        (path / "task" / str(pid) / "children").write_text(children)
        (path / "environ").write_text(CANARY)
    process = SimpleNamespace(process=SimpleNamespace(pid=100), record=lambda: {"exit_code": None})
    report = backend.snapshot(scratch, process, proc_root=proc)
    rows = report["processes"]["entries"]
    assert [row["pid"] for row in rows] == [100, 101]
    assert all(row["exit_code"] == expected_exit for row in rows)
    assert rows[1]["parent_pid"] == 100
    assert rows[0]["socket_arguments"] == {"--agent-host-path": "tmp/agent.sock", "--socket-path": "outside_invocation_tree"}
    assert CANARY not in json.dumps(report)
