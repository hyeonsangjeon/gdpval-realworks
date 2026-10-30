"""Pinned, credential-free AHP discovery. Real processes: hosted Ubuntu 24.04 only.

No prompt/turn/authentication RPC exists in this driver. Runtime additionally
requires a loopback-only network namespace and an unprivileged PID-1 process.
This is a capability probe, not a benchmark, billing meter or paid gate.
"""

from __future__ import annotations

import argparse
import base64
import errno
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import signal
import socket
import struct
import subprocess
import tarfile
import tempfile
import threading
import time
import urllib.parse
import urllib.request
import uuid

import ghcp_sol_runner_environment as runner

MANIFEST = Path(__file__).with_name("ghcp_ahp_probe_manifest.json")
ALLOWED_METHODS = frozenset({"initialize", "resolveSessionConfig", "createSession", "subscribe", "disposeSession"})
MAX_RPCS = 5
MAX_RUNTIME_SECONDS = 180
MAX_FRAME_BYTES = 2 * 1024 * 1024
MAX_WIRE_BYTES = 8 * 1024 * 1024
MAX_LOG_BYTES = 256 * 1024
ROOT_CHANNEL = "ahp-root://"
DESIRED_MODEL = {"id": "@provider=vscode-proxy:gpt-5.6-sol", "config": {"thinkingLevel": "max", "contextSize": 1_000_000}}
_SECRET_KEYS = {"token", "accesstoken", "refreshtoken", "idtoken", "connectiontoken", "authorization", "password", "secret", "apikey", "credential", "credentials"}
_CREDENTIAL = re.compile(r"\b(?:github_pat_|gh[o_pusr]_|sk-)[A-Za-z0-9_-]{8,}|\bBearer\s+[^\s\"<>]+", re.I)
_TOKEN_ASSIGNMENT = re.compile(r"((?:[?&]tkn=)|(?:\b(?:[a-z_]*(?:token|api_key|secret|password)|accessToken|refreshToken|idToken|connectionToken|apiKey)\b\s*[:=]\s*))[\"']?[^\s\"'&,<>]+", re.I)
_AUTH_HEADER = re.compile(r"(\bauthorization\s*[:=]\s*)[^\r\n]+", re.I)


class Refused(RuntimeError):
    def __init__(self, code):
        super().__init__(code if re.fullmatch(r"[a-z_]{1,80}", str(code)) else "internal_probe_refusal")


def redact(value):
    if isinstance(value, dict):
        return {str(k): "[REDACTED]" if re.sub(r"[^a-z]", "", str(k).lower()) in _SECRET_KEYS else redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, str):
        return _AUTH_HEADER.sub(r"\1[REDACTED]", _TOKEN_ASSIGNMENT.sub(r"\1[REDACTED]", _CREDENTIAL.sub("[REDACTED]", value)))
    return value


def digest(path):
    total = hashlib.sha256()
    with Path(path).open("rb") as source:
        for part in iter(lambda: source.read(1024 * 1024), b""):
            total.update(part)
    return total.hexdigest()


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(redact(value), indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as output:
        output.write(encoded)


def strict_json(text):
    def pairs(entries):
        result = {}
        for key, value in entries:
            if key in result:
                raise Refused("duplicate_json_key")
            result[key] = value
        return result

    def invalid_number(value):
        raise Refused("invalid_json_number")
    return json.loads(text, object_pairs_hook=pairs, parse_constant=invalid_number)


def load_manifest(path=MANIFEST):
    value = json.loads(Path(path).read_text())
    if value.get("schema") != "ghcp-ahp-model-free-probe-v1" or not re.fullmatch(r"[0-9a-f]{40}", value.get("vscode_commit", "")):
        raise Refused("invalid_probe_manifest")
    if set(value.get("artifacts", {})) != {"cli", "server", "codex_sdk", "source"}:
        raise Refused("invalid_artifact_set")
    for artifact in value["artifacts"].values():
        parsed = urllib.parse.urlsplit(artifact["url"])
        if parsed.scheme != "https" or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.hostname not in {"vscode.download.prss.microsoft.com", "main.vscode-cdn.net", "codeload.github.com"}:
            raise Refused("unsafe_download_url")
        if not re.fullmatch(r"[0-9a-f]{64}", artifact["sha256"]) or type(artifact["maximum_bytes"]) is not int or not 0 < artifact["maximum_bytes"] <= 512 * 1024 * 1024:
            raise Refused("invalid_artifact_bound")
    for citation in value["citations"]:
        checked_member(citation["path"])
    return value


def require_runner():
    identity = runner.observe()
    if not identity["eligible_for_execution"]:
        raise Refused(runner.REFUSAL)
    if os.environ.get("RUNNER_ARCH") != "X64" or runner.platform.machine() != "x86_64":
        raise Refused("runner_architecture_refused")
    identity["runner_arch"] = "X64"
    for key in ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT"):
        if not re.fullmatch(r"[1-9][0-9]*", os.environ.get(key, "")):
            raise Refused("runner_run_identity_missing")
        identity[key.lower()] = os.environ[key]
    commit = os.environ.get("GITHUB_SHA", "")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise Refused("runner_commit_identity_missing")
    identity["github_sha"] = commit
    return identity


def checked_member(name):
    parsed = PurePosixPath(name)
    if not name or parsed.is_absolute() or ".." in parsed.parts or "\\" in name:
        raise Refused("unsafe_archive_member")
    return parsed


def extract_archive(path, destination):
    """Only pinned archives; additionally use the stdlib data extraction filter."""
    if not hasattr(tarfile, "data_filter"):
        raise Refused("safe_tar_filter_unavailable")
    with tarfile.open(path, "r:gz") as archive:
        members = archive.getmembers()
        if len(members) > 100_000 or sum(m.size for m in members) > 2 * 1024**3:
            raise Refused("archive_expansion_limit")
        for member in members:
            checked_member(member.name)
            if not (member.isdir() or member.isfile() or member.issym() or member.islnk()):
                raise Refused("archive_special_file")
        archive.extractall(destination, members=members, filter="data")


def download(artifact, target):
    # No credential manager, netrc, token, or inherited proxy is consulted.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    request = urllib.request.Request(artifact["url"], headers={"User-Agent": "ghcp-ahp-model-free-probe/1"})
    size = 0
    total = hashlib.sha256()
    with opener.open(request, timeout=30) as response, Path(target).open("xb") as output:
        if urllib.parse.urlsplit(response.url).scheme != "https":
            raise Refused("insecure_download_redirect")
        while part := response.read(1024 * 1024):
            size += len(part)
            if size > artifact["maximum_bytes"]:
                raise Refused("download_size_exceeded")
            total.update(part)
            output.write(part)
    if total.hexdigest() != artifact["sha256"]:
        raise Refused("artifact_sha256_mismatch")
    return {"sha256": total.hexdigest(), "bytes": size, "url": artifact["url"], "hash_source": artifact["hash_source"]}


def source_contract(manifest, source_root):
    citations = []
    for entry in manifest["citations"]:
        path = Path(source_root) / entry["path"]
        text = path.read_text()
        lines = text.splitlines()
        excerpts = []
        for anchor in entry["anchors"]:
            matching = [i for i, line in enumerate(lines) if anchor in line]
            if not matching:
                raise Refused("source_contract_anchor_missing")
            at = matching[0]
            start, end = max(0, at - 3), min(len(lines), at + 7)
            excerpts.append({"anchor": anchor, "line_start": start + 1, "line_end": end, "text": "\n".join(lines[start:end]), "url": f"https://github.com/microsoft/vscode/blob/{manifest['vscode_commit']}/{entry['path']}#L{start + 1}-L{end}"})
        citations.append({"id": entry["id"], "path": entry["path"], "sha256": digest(path), "excerpts": excerpts})
    return {"status": "source_verified_only", "vscode_commit": manifest["vscode_commit"], "citations": citations,
            "desired_model_selection_not_sent": DESIRED_MODEL,
            "applied_settings": {"served_model": "not_reported", "reasoning_effort": "not_reported", "context_window": "not_reported"},
            "limits": {"turns": "not_verified_in_exposed_codex_config", "tool_calls": "not_verified_in_exposed_codex_config", "model_requests": "not_verified_in_exposed_codex_config", "active_session_deadline": "not_verified", "cli_idle_timeout": "supported_but_does_not_cut_active_sessions"},
            "capture": {"snapshot_subscription": "source_verified", "ordered_chat_and_tool_actions": "source_verified", "history_fetchTurns": "source_verified", "complete_paid_transcript": "not_verified"},
            "caveats": ["A model/config field is not a served-setting attestation.", "Context is forwarded only when the model advertises the requested size.", "Restored unknown models may fall back within their provider; a paid adapter must reject mismatches.", "No schema-absence claim extends beyond this pinned source review."]}


def prepare(manifest, root, evidence):
    identity = require_runner()
    root.mkdir(parents=True, exist_ok=False)
    evidence.mkdir(parents=True, exist_ok=True)
    downloads = root / "downloads"
    downloads.mkdir()
    records = {}
    for name, spec in manifest["artifacts"].items():
        records[name] = download(spec, downloads / (name + ".tgz"))
    cli_root = root / "cli"
    cli_root.mkdir()
    extract_archive(downloads / "cli.tgz", cli_root)
    cache_entry = root / "cli-data" / "servers" / ("Stable-" + manifest["vscode_commit"])
    cache_entry.mkdir(parents=True)
    extract_archive(downloads / "server.tgz", cache_entry)
    (cache_entry / "vscode-server-linux-x64").rename(cache_entry / "server")
    save_json(cache_entry.parent / "lru.json", [cache_entry.name])
    sdk_root = root / "codex-sdk"
    sdk_root.mkdir()
    extract_archive(downloads / "codex_sdk.tgz", sdk_root)
    product = json.loads((cache_entry / "server/product.json").read_text())
    sdk_config = product.get("agentSdks", {}).get("codex", {})
    if product.get("commit") != manifest["vscode_commit"] or sdk_config.get("version") != manifest["codex_sdk_version"] or sdk_config.get("urlTemplate", "").replace("{sdkTarget}", "linux-x64") != manifest["artifacts"]["codex_sdk"]["url"]:
        raise Refused("server_sdk_identity_mismatch")
    sdk_package = json.loads((sdk_root / "node_modules/@openai/codex/package.json").read_text())
    if sdk_package.get("version") != manifest["codex_sdk_version"]:
        raise Refused("codex_sdk_version_mismatch")
    source_root = root / "source"
    prefix = "vscode-" + manifest["vscode_commit"] + "/"
    with tarfile.open(downloads / "source.tgz", "r:gz") as archive:
        for entry in manifest["citations"]:
            member = archive.getmember(prefix + entry["path"])
            if not member.isfile() or member.size > 8 * 1024**2:
                raise Refused("invalid_source_member")
            target = source_root / entry["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            # Some citations intentionally reuse the same source file.
            if not target.exists():
                with archive.extractfile(member) as source, target.open("xb") as output:
                    output.write(source.read())
    contract = source_contract(manifest, source_root)
    save_json(evidence / "source-evidence.json", contract)
    binaries = {"cli": cli_root / "code", "node": cache_entry / "server/node", "server_launcher": cache_entry / "server/bin/code-server"}
    for binary in binaries.values():
        if not binary.is_file() or binary.is_symlink() or not os.access(binary, os.X_OK):
            raise Refused("required_binary_missing")
    record = {"status": "prepared_without_process_execution", "runner": identity, "artifacts": records,
              "vscode_version": manifest["vscode_version"], "vscode_commit": manifest["vscode_commit"], "codex_sdk_version": manifest["codex_sdk_version"],
              "binary_sha256": {k: {"relative_path": str(v.relative_to(root)), "sha256": digest(v)} for k, v in binaries.items()},
              "source_evidence_sha256": digest(evidence / "source-evidence.json"),
              "model_calls": 0, "authentication_supplied": False}
    save_json(evidence / "prepared.json", record)


def require_isolation(outside_netns, outside_pidns):
    current_netns = os.readlink("/proc/self/ns/net")
    current_pidns = os.readlink("/proc/self/ns/pid")
    if not re.fullmatch(r"net:\[[0-9]+\]", outside_netns) or current_netns == outside_netns:
        raise Refused("network_namespace_not_isolated")
    if not re.fullmatch(r"pid:\[[0-9]+\]", outside_pidns) or current_pidns == outside_pidns or os.getpid() != 1:
        raise Refused("pid_namespace_not_isolated")
    if os.geteuid() == 0:
        raise Refused("root_runtime_refused")
    interfaces = sorted(name for _, name in socket.if_nameindex())
    if interfaces != ["lo"]:
        raise Refused("external_network_interface_present")
    status = Path("/proc/self/status").read_text()
    if not re.search(r"^NoNewPrivs:\s+1$", status, re.M) or not re.search(r"^CapEff:\s+0+$", status, re.M):
        raise Refused("privilege_drop_not_verified")
    return {"network_namespace": current_netns, "outside_network_namespace": outside_netns, "pid_namespace": current_pidns,
            "interfaces": interfaces, "pid_one": True, "unprivileged": True, "no_new_privileges": True,
            "external_egress": "kernel_loopback_only", "cleanup_boundary": "all_descendants_die_when_pid_namespace_init_exits"}


def child_environment(root, scratch):
    # Do not inspect or copy any credential source. HOME is an isolated child
    # process setting, never a shell scratch variable or the operator's HOME.
    dirs = {name: scratch / name for name in ("home", "config", "cache", "data", "tmp")}
    for path in dirs.values():
        path.mkdir(mode=0o700)
    return {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "HOME": str(dirs["home"]),
            "XDG_CONFIG_HOME": str(dirs["config"]), "XDG_CACHE_HOME": str(dirs["cache"]), "XDG_DATA_HOME": str(dirs["data"]), "TMPDIR": str(dirs["tmp"]),
            "VSCODE_CLI_DATA_DIR": str(root / "cli-data"), "VSCODE_AGENT_HOST_CODEX_AGENT_ENABLED": "true",
            "VSCODE_AGENT_HOST_CLAUDE_AGENT_ENABLED": "false", "VSCODE_AGENT_HOST_CODEX_SDK_ROOT": str(root / "codex-sdk"),
            "DO_NOT_TRACK": "1", "VSCODE_TELEMETRY_LEVEL": "off"}


def verify_prepared(manifest, root, evidence, identity):
    prepared = strict_json((evidence / "prepared.json").read_text())
    if prepared["vscode_commit"] != manifest["vscode_commit"] or prepared["runner"]["github_sha"] != identity["github_sha"]:
        raise Refused("prepared_identity_mismatch")
    if set(prepared["artifacts"]) != set(manifest["artifacts"]) or any(prepared["artifacts"][key]["sha256"] != value["sha256"] for key, value in manifest["artifacts"].items()):
        raise Refused("prepared_artifact_identity_mismatch")
    server = f"cli-data/servers/Stable-{manifest['vscode_commit']}/server"
    paths = {"cli": "cli/code", "node": server + "/node", "server_launcher": server + "/bin/code-server"}
    if set(prepared["binary_sha256"]) != set(paths):
        raise Refused("prepared_binary_set_mismatch")
    for name, expected in paths.items():
        entry = prepared["binary_sha256"][name]
        if entry["relative_path"] != expected:
            raise Refused("prepared_binary_path_mismatch")
        binary = root / expected
        if binary.is_symlink() or not binary.resolve().is_relative_to(root.resolve()) or digest(binary) != entry["sha256"]:
            raise Refused("prepared_binary_drift")
    if digest(evidence / "source-evidence.json") != prepared["source_evidence_sha256"]:
        raise Refused("source_evidence_drift")
    return prepared, strict_json((evidence / "source-evidence.json").read_text())


class CapturedProcess:
    def __init__(self, command, environment, cwd=None):
        self.command = command
        self.buffers = {"stdout": bytearray(), "stderr": bytearray()}
        self.overflow = threading.Event()
        self.process = subprocess.Popen(command, env=environment, cwd=cwd, stdin=subprocess.DEVNULL,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        self.threads = []
        for name in self.buffers:
            stream = getattr(self.process, name)
            thread = threading.Thread(target=self._read, args=(name, stream), daemon=True)
            thread.start()
            self.threads.append(thread)

    def _read(self, name, stream):
        try:
            while part := stream.read(4096):
                available = MAX_LOG_BYTES - len(self.buffers[name])
                self.buffers[name].extend(part[:available])
                if len(part) > available:
                    self.overflow.set()
                    break
        finally:
            stream.close()

    def check(self):
        if self.overflow.is_set():
            raise Refused("process_output_limit_exceeded")

    def finish(self, timeout=10):
        try:
            self.process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            raise Refused("command_timeout") from None
        finally:
            self.stop()
        self.check()
        return self.record()

    def stop(self):
        # Own start_new_session process group only; PID namespace is the outer
        # guarantee for any detached descendants. Never inspect other processes.
        try:
            os.killpg(self.process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(self.process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            self.process.wait(timeout=3)
        for thread in self.threads:
            thread.join(timeout=1)

    def record(self):
        return redact({"command": self.command, "exit_code": self.process.poll(), "output_limit_exceeded": self.overflow.is_set(),
                       **{k: bytes(v).decode("utf-8", errors="replace") for k, v in self.buffers.items()}})


def encode_frame(payload, opcode=1, mask=None):
    if len(payload) > MAX_FRAME_BYTES:
        raise Refused("websocket_frame_limit")
    mask = os.urandom(4) if mask is None else mask
    length = len(payload)
    size = bytes([0x80 | length]) if length < 126 else bytes([0xFE]) + struct.pack("!H", length) if length < 65536 else bytes([0xFF]) + struct.pack("!Q", length)
    return bytes([0x80 | opcode]) + size + mask + bytes(v ^ mask[i % 4] for i, v in enumerate(payload))


class WebSocket:
    def __init__(self, port, deadline):
        self.deadline = deadline
        self.buffer = bytearray()
        self.total = 0
        self.socket = socket.create_connection(("127.0.0.1", port), timeout=5)
        try:
            nonce = base64.b64encode(os.urandom(16)).decode()
            request = f"GET / HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {nonce}\r\nSec-WebSocket-Version: 13\r\n\r\n"
            self.socket.sendall(request.encode("ascii"))
            while b"\r\n\r\n" not in self.buffer:
                self._receive()
                if len(self.buffer) > 16384:
                    raise Refused("websocket_header_limit")
            raw, remaining = self.buffer.split(b"\r\n\r\n", 1)
            self.buffer = bytearray(remaining)
            lines = raw.decode("ascii").split("\r\n")
            fields = dict(line.split(":", 1) for line in lines[1:] if ":" in line)
            headers = {k.lower(): v.strip() for k, v in fields.items()}
            expected = base64.b64encode(hashlib.sha1((nonce + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
            if not lines[0].startswith("HTTP/1.1 101 ") or headers.get("sec-websocket-accept") != expected:
                raise Refused("websocket_upgrade_refused")
        except BaseException:
            self.socket.close()
            raise

    def _receive(self):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise Refused("probe_deadline_exceeded")
        self.socket.settimeout(min(30, remaining))
        part = self.socket.recv(65536)
        if not part:
            raise Refused("websocket_closed")
        self.total += len(part)
        if self.total > MAX_WIRE_BYTES:
            raise Refused("websocket_total_limit")
        self.buffer.extend(part)

    def _take(self, length):
        while len(self.buffer) < length:
            self._receive()
        value = bytes(self.buffer[:length])
        del self.buffer[:length]
        return value

    def send(self, value):
        self.socket.sendall(encode_frame(json.dumps(value, allow_nan=False).encode()))

    def receive(self):
        fragments = bytearray()
        while True:
            first, second = self._take(2)
            if first & 0x70 or second & 0x80:
                raise Refused("unsupported_websocket_frame")
            final, opcode = bool(first & 0x80), first & 0x0F
            size = second & 0x7F
            if size == 126:
                size = struct.unpack("!H", self._take(2))[0]
            elif size == 127:
                size = struct.unpack("!Q", self._take(8))[0]
            if size > MAX_FRAME_BYTES or len(fragments) + size > MAX_FRAME_BYTES:
                raise Refused("websocket_frame_limit")
            payload = self._take(size)
            if opcode == 8:
                raise Refused("websocket_closed")
            if opcode in (9, 10):
                if not final or size > 125:
                    raise Refused("invalid_websocket_control")
                if opcode == 9:
                    self.socket.sendall(encode_frame(payload, opcode=10))
                continue
            if opcode not in (0, 1) or (opcode == 0 and not fragments) or (opcode == 1 and fragments):
                raise Refused("unexpected_websocket_opcode")
            fragments.extend(payload)
            if final:
                return strict_json(fragments.decode())

    def close(self):
        self.socket.close()


def validate_request(method, params, session, workspace):
    allowed = {
        "initialize": {"channel", "protocolVersions", "clientId", "clientInfo", "initialSubscriptions", "locale"},
        "resolveSessionConfig": {"channel", "provider", "workingDirectory"},
        "createSession": {"channel", "provider", "workingDirectories"},
        "subscribe": {"channel"}, "disposeSession": {"channel"},
    }
    if method not in ALLOWED_METHODS or type(params) is not dict or set(params) != allowed[method]:
        raise Refused("model_free_rpc_allowlist_refused")
    expected_channel = ROOT_CHANNEL if method in {"initialize", "resolveSessionConfig"} else session
    if params.get("channel") != expected_channel:
        raise Refused("foreign_rpc_channel_refused")
    if method in {"resolveSessionConfig", "createSession"} and params["provider"] != "codex":
        raise Refused("foreign_provider_refused")
    if method == "resolveSessionConfig" and params["workingDirectory"] != workspace:
        raise Refused("foreign_workspace_refused")
    if method == "createSession" and params["workingDirectories"] != [workspace]:
        raise Refused("foreign_workspace_refused")
    if method == "initialize" and (params["protocolVersions"] != ["1.1.0", "1.0.0"] or params["initialSubscriptions"] != [ROOT_CHANNEL] or params["clientInfo"] != {"name": "ghcp-ahp-model-free-probe", "version": "1"} or params["locale"] != "en-US" or not re.fullmatch(r"[0-9a-f-]{36}", params["clientId"])):
        raise Refused("invalid_initialize_request")


class Rpc:
    def __init__(self, transport, session, workspace):
        parsed = urllib.parse.urlsplit(workspace)
        if not re.fullmatch(r"ahp-session:/[0-9a-f-]{36}", session) or parsed.scheme != "file" or parsed.netloc or not parsed.path.startswith("/") or parsed.query or parsed.fragment:
            raise Refused("unsafe_rpc_scope")
        self.transport, self.session, self.workspace = transport, session, workspace
        self.sent = []
        self.received = []

    def request(self, method, params):
        validate_request(method, params, self.session, self.workspace)
        if len(self.sent) >= MAX_RPCS:
            raise Refused("rpc_count_limit")
        request = {"jsonrpc": "2.0", "id": len(self.sent) + 1, "method": method, "params": params}
        self.sent.append(request)
        self.transport.send(request)
        while len(self.received) < 256:
            value = self.transport.receive()
            if not isinstance(value, dict) or value.get("jsonrpc") != "2.0":
                raise Refused("invalid_rpc_response")
            self.received.append(value)
            serialized = json.dumps(value)
            if re.search(r'"(?:type|method)"\s*:\s*"(?:chat/turnStarted|chat/toolCallStart|turn/start|sendMessage)"', serialized):
                raise Refused("unexpected_turn_or_tool_activity")
            if "id" in value:
                if "method" in value:
                    raise Refused("server_request_not_authorized")
                if type(value["id"]) is not int or value["id"] != request["id"] or ("result" in value) == ("error" in value):
                    raise Refused("rpc_response_identity_mismatch")
                if "error" in value and (not isinstance(value["error"], dict) or type(value["error"].get("code")) is not int or not isinstance(value["error"].get("message"), str)):
                    raise Refused("malformed_rpc_error")
                return value
        raise Refused("rpc_event_limit")


def exercise_rpc(rpc):
    results = {}
    results["initialize"] = rpc.request("initialize", {"channel": ROOT_CHANNEL, "protocolVersions": ["1.1.0", "1.0.0"],
        "clientId": str(uuid.uuid4()), "clientInfo": {"name": "ghcp-ahp-model-free-probe", "version": "1"}, "initialSubscriptions": [ROOT_CHANNEL], "locale": "en-US"})
    initialized = results["initialize"].get("result", {})
    if not isinstance(initialized, dict) or initialized.get("protocolVersion") not in {"1.1.0", "1.0.0"}:
        return results
    results["resolveSessionConfig"] = rpc.request("resolveSessionConfig", {"channel": ROOT_CHANNEL, "provider": "codex", "workingDirectory": rpc.workspace})
    results["createSession"] = rpc.request("createSession", {"channel": rpc.session, "provider": "codex", "workingDirectories": [rpc.workspace]})
    if "error" not in results["createSession"]:
        results["subscribe"] = rpc.request("subscribe", {"channel": rpc.session})
        results["disposeSession"] = rpc.request("disposeSession", {"channel": rpc.session})
    return results


def classify_rpc(results):
    errors = [{"stage": name, **reply["error"]} for name, reply in results.items() if isinstance(reply.get("error"), dict)]
    created = results.get("createSession", {})
    return {"provider_requested": "codex", "session_created_without_auth": "result" in created,
            "authentication": "authentication_required_reported" if any(e.get("code") == -32007 for e in errors) else "not_reached_without_turn",
            "errors": errors, "prompt_or_turn_sent": False, "model_settings_sent": False,
            "evidence_boundary": "empty_session_only_not_authenticated_model_execution"}


def run_probe(manifest, root, evidence, outside_netns, outside_pidns):
    identity = require_runner()
    isolation = require_isolation(outside_netns, outside_pidns)
    prepared, source_evidence = verify_prepared(manifest, root, evidence, identity)
    deadline = time.monotonic() + MAX_RUNTIME_SECONDS
    record = {"schema": "ghcp-ahp-probe-receipt-v1", "runner": identity, "isolation": isolation,
              "vscode_version": manifest["vscode_version"], "vscode_commit": manifest["vscode_commit"], "codex_sdk_version": manifest["codex_sdk_version"],
              "artifacts": prepared["artifacts"], "binary_sha256": prepared["binary_sha256"],
              "source_contract": source_evidence, "source_evidence_sha256": prepared["source_evidence_sha256"],
              "authentication_supplied": False, "credential_environment_inherited": False, "headless_started": False,
              "model_calls": 0, "model_call_evidence_boundary": "no_prompt_rpc_and_kernel_denied_external_egress_not_a_billing_receipt",
              "launch_allowed": False, "gate_ready": False, "served_model": "not_reported", "reasoning_effort": "not_reported", "context_window": "not_reported",
              "probe_limits": {"wall_seconds": MAX_RUNTIME_SECONDS, "rpc_requests": MAX_RPCS, "prompt_turns": 0, "wire_bytes": MAX_WIRE_BYTES},
              "reason_codes": [], "status": "incomplete"}
    transport = process = rpc = None
    try:
        with tempfile.TemporaryDirectory(prefix="ahp-") as temporary:
            scratch = Path(temporary)
            environment = child_environment(root, scratch)
            workspace = scratch / "workspace"
            workspace.mkdir()
            cli = str(root / "cli/code")
            version = CapturedProcess([cli, "--version"], environment, cwd=scratch).finish()
            record["cli_version"] = version
            if version["exit_code"] != 0 or manifest["vscode_version"] not in version["stdout"] or manifest["vscode_commit"] not in version["stdout"]:
                raise Refused("cli_version_not_verified")
            help_result = CapturedProcess([cli, "agent", "host", "--help"], environment, cwd=scratch).finish()
            record["cli_host_help"] = help_result
            if help_result["exit_code"] != 0 or any(flag not in help_result["stdout"] for flag in ("--foreground", "--new-instance", "--without-connection-token")):
                raise Refused("headless_cli_contract_not_available")
            with socket.socket() as port_reservation:
                port_reservation.bind(("127.0.0.1", 0))
                port = port_reservation.getsockname()[1]
            command = [cli, "agent", "host", "--foreground", "--new-instance", "--without-connection-token", "--host", "127.0.0.1", "--port", str(port),
                       "--server-data-dir", str(scratch / "server-data"), "--user-data-dir", str(scratch / "user-data"), "--disable-telemetry"]
            process = CapturedProcess(command, environment, cwd=workspace)
            try:
                while time.monotonic() < deadline:
                    process.check()
                    if process.process.poll() is not None:
                        raise Refused("agent_host_exited_before_handshake")
                    try:
                        transport = WebSocket(port, deadline)
                        break
                    except OSError as error:
                        if error.errno not in (errno.ECONNREFUSED, errno.ECONNRESET):
                            raise
                        time.sleep(0.1)
                if transport is None:
                    raise Refused("agent_host_startup_deadline")
                rpc = Rpc(transport, "ahp-session:/" + str(uuid.uuid4()), workspace.as_uri())
                results = exercise_rpc(rpc)
                record["rpc_results"] = results
                record["codex_session"] = classify_rpc(results)
                record["headless_started"] = isinstance(results.get("initialize", {}).get("result"), dict) and results["initialize"]["result"].get("protocolVersion") in {"1.1.0", "1.0.0"}
                record["status"] = "probe_completed" if record["headless_started"] else "protocol_initialization_refused"
            finally:
                if transport is not None:
                    transport.close()
                process.stop()
                record["host_process"] = process.record()
                record["cleanup"] = "owned_process_group_stopped_pid_namespace_exit_cleans_detached_children"
    except Exception as error:
        record["status"] = "probe_refused"
        record["reason_codes"].append(str(error) if isinstance(error, Refused) else type(error).__name__)
    finally:
        if rpc is not None:
            record["rpc_sent"] = rpc.sent
            record["rpc_received"] = rpc.received
        save_json(evidence / "probe.json", record)
    return 0 if record["status"] == "probe_completed" else 2


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise Refused("invalid_probe_arguments")


def main(argv=None):
    parser = SafeArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "probe"))
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--outside-netns", default="")
    parser.add_argument("--outside-pidns", default="")
    args = None
    admitted = False
    try:
        args = parser.parse_args(argv)
        # NAS/local refusal happens before manifests, files, downloads or processes.
        require_runner()
        admitted = True
        manifest = load_manifest()
        if args.mode == "prepare":
            prepare(manifest, args.prepared, args.evidence)
            print('{"status":"prepared","model_calls":0}')
            return 0
        result = run_probe(manifest, args.prepared, args.evidence, args.outside_netns, args.outside_pidns)
        print(json.dumps({"probe_exit": result, "model_calls": 0, "launch_allowed": False}))
        return result
    except Exception as error:
        # Never echo arbitrary exception text, environment or credential material.
        code = str(error) if isinstance(error, Refused) else type(error).__name__
        failure = {"status": "refused", "reason_code": code, "model_calls": 0}
        if admitted:
            save_json(args.evidence / ("failure-" + args.mode + ".json"), failure)
        print(json.dumps(failure))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
