"""Inert protocol/host-policy fixtures, never an installed agent host on NAS."""

import copy
import hashlib
import io
import json
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
