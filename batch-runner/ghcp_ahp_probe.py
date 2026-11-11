"""Pinned AHP discovery. Real processes: hosted Ubuntu 24.04 only.

No prompt/turn RPC exists. Authentication requires the protected zero-turn mode.
The ordinary push path remains credential-free. Runtime additionally
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
from ghcp_ahp_errors import Refused

MANIFEST = Path(__file__).with_name("ghcp_ahp_probe_manifest.json")
ALLOWED_METHODS = frozenset({"initialize", "resolveSessionConfig", "createSession", "subscribe", "disposeSession"})
MAX_RPCS = 5
MAX_RUNTIME_SECONDS = 180
MAX_FRAME_BYTES = 2 * 1024 * 1024
MAX_WIRE_BYTES = 8 * 1024 * 1024
MAX_LOG_BYTES = 256 * 1024
MAX_ARCHIVE_EXPANSION_BYTES = 2 * 1024**3
ROOT_CHANNEL = "ahp-root://"
DESIRED_MODEL = {"id": "@provider=vscode-proxy:gpt-5.6-sol", "config": {"thinkingLevel": "max", "contextSize": 1_000_000}}
_SECRET_KEYS = {"token", "accesstoken", "refreshtoken", "idtoken", "connectiontoken", "authorization", "password", "secret", "apikey", "credential", "credentials"}
_CREDENTIAL = re.compile(r"\b(?:github_pat_|gh[o_pusr]_|sk-)[A-Za-z0-9_-]{8,}|\bBearer\s+[^\s\"<>]+", re.I)
_TOKEN_ASSIGNMENT = re.compile(r"((?:[?&]tkn=)|(?:\b(?:[a-z_]*(?:token|api_key|secret|password)|accessToken|refreshToken|idToken|connectionToken|apiKey)\b\s*[:=]\s*))[\"']?[^\s\"'&,<>]+", re.I)
_AUTH_HEADER = re.compile(r"(\bauthorization\s*[:=]\s*)[^\r\n]+", re.I)


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
        if len(members) > 100_000 or sum(m.size for m in members) > MAX_ARCHIVE_EXPANSION_BYTES:
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
    def __init__(self, port, deadline, *, connection_token=None):
        # Optional local-transport credential, NOT the Copilot credential. The
        # model-free probe never supplies it and keeps its RPC allowlist intact.
        if connection_token is not None and not re.fullmatch(r"[0-9a-f]{64}", connection_token):
            raise Refused("invalid_local_connection_token")
        self.deadline = deadline
        self.buffer = bytearray()
        self.total = 0
        self.socket = socket.create_connection(("127.0.0.1", port), timeout=5)
        try:
            nonce = base64.b64encode(os.urandom(16)).decode()
            target = "/" if connection_token is None else "/?tkn=" + connection_token
            request = f"GET {target} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {nonce}\r\nSec-WebSocket-Version: 13\r\n\r\n"
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


def select_thread_policy(admission_profile=None):
    if admission_profile is None:
        import ghcp_ahp_thread_policy as policy
    elif admission_profile == "default_policy_unpatched":
        import ghcp_ahp_default_policy as policy
    else:
        raise Refused("admission_profile_refused")
    return policy


class Rpc:
    def __init__(self, transport, session, workspace, *, capability_only=False, session_policy=False, credential="", boundary_check=None, require_mcp_disabled=False,
                 admission_profile=None):
        parsed = urllib.parse.urlsplit(workspace)
        if not re.fullmatch(r"ahp-session:/[0-9a-f-]{36}", session) or parsed.scheme != "file" or parsed.netloc or not parsed.path.startswith("/") or parsed.query or parsed.fragment:
            raise Refused("unsafe_rpc_scope")
        self.transport, self.session, self.workspace = transport, session, workspace
        if type(capability_only) is not bool or type(session_policy) is not bool or capability_only and session_policy:
            raise Refused("invalid_capability_mode")
        self.capability_only = capability_only
        self.session_policy = session_policy
        if admission_profile is not None and (admission_profile != "default_policy_unpatched" or not session_policy or not credential):
            raise Refused("default_policy_mode_refused")
        self.admission_profile = admission_profile
        if credential and not session_policy:
            raise Refused("zero_turn_auth_requires_session_policy")
        self.credential = credential
        self.boundary_check = boundary_check
        self.require_mcp_disabled = require_mcp_disabled
        self.mask = None
        if credential:
            from ghcp_ahp_diagnostics import DiagnosticRedactor
            from ghcp_ahp_zero_turn import validate_credential
            validate_credential(credential)
            self.mask = DiagnosticRedactor(credential)
        self.sent = []
        self.received = []

    def request(self, method, params):
        if self.boundary_check is not None:
            self.boundary_check()
        if self.capability_only and (method not in {"initialize", "resolveSessionConfig"}
                                     or len(self.sent) >= 2):
            raise Refused("zero_session_probe_rpc_refused")
        if self.session_policy:
            thread_policy = select_thread_policy(self.admission_profile)
            thread_policy.validate(method, params, self)
        else:
            validate_request(method, params, self.session, self.workspace)
        if len(self.sent) >= MAX_RPCS + bool(self.credential):
            raise Refused("rpc_count_limit")
        request = {"jsonrpc": "2.0", "id": len(self.sent) + 1, "method": method, "params": params}
        self.sent.append(self.mask.clean(request) if self.mask else request)
        self.transport.send(request)
        while len(self.received) < 256:
            value = self.transport.receive()
            if self.boundary_check is not None:
                self.boundary_check()
            if not isinstance(value, dict) or value.get("jsonrpc") != "2.0":
                raise Refused("invalid_rpc_response")
            self.received.append(self.mask.clean(value) if self.mask else value)
            serialized = json.dumps(value)
            if re.search(r'"(?:type|method)"\s*:\s*"(?:chat/turn[^"\s]*|chat/toolCall[^"\s]*|turn/[^"\s]*|item/[^"\s]*|sendMessage)"', serialized):
                raise Refused("unexpected_turn_or_tool_activity")
            if "id" in value:
                if "method" in value:
                    raise Refused("server_request_not_authorized")
                if type(value["id"]) is not int or value["id"] != request["id"] or ("result" in value) == ("error" in value):
                    raise Refused("rpc_response_identity_mismatch")
                if "error" in value and (not isinstance(value["error"], dict) or type(value["error"].get("code")) is not int or not isinstance(value["error"].get("message"), str)):
                    raise Refused("malformed_rpc_error")
                return self.mask.clean(value) if self.mask else value
        raise Refused("rpc_event_limit")


def exercise_rpc(rpc):
    results = {}
    results["initialize"] = rpc.request("initialize", {"channel": ROOT_CHANNEL, "protocolVersions": ["1.1.0", "1.0.0"],
        "clientId": str(uuid.uuid4()), "clientInfo": {"name": "ghcp-ahp-model-free-probe", "version": "1"}, "initialSubscriptions": [ROOT_CHANNEL], "locale": "en-US"})
    initialized = results["initialize"].get("result", {})
    if not isinstance(initialized, dict) or initialized.get("protocolVersion") not in {"1.1.0", "1.0.0"}:
        return results
    results["resolveSessionConfig"] = rpc.request("resolveSessionConfig", {"channel": ROOT_CHANNEL, "provider": "codex", "workingDirectory": rpc.workspace})
    if rpc.capability_only:
        return results
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
            "errors": errors, "prompt_or_turn_sent": False,
            "model_settings_sent": created.get("transport") == "vscode-child-ipc",
            "evidence_boundary": "empty_session_only_not_authenticated_model_execution"}


def session_create_requests(rpc):
    if rpc is None:
        return 0
    managed = getattr(rpc, "management", None)
    return (sum(row["method"] == "createSession" for row in rpc.sent)
            + sum(row.get("op") == "create" for row in getattr(managed, "sent", [])))


def run_probe(manifest, root, evidence, outside_netns, outside_pidns, *, capability_only=False, session_policy=False,
              authenticated_zero_turn=False, credential="", metadata_socket=None, patched_request=None,
              prewarm_preparation=None, admission_profile=None):
    if type(capability_only) is not bool or type(session_policy) is not bool or capability_only and session_policy:
        raise Refused("invalid_capability_mode")
    if patched_request is not None:
        import ghcp_ahp_patched_runtime as patched
        if not session_policy or capability_only:
            raise Refused("patched_runtime_requires_zero_turn_mode")
        patched.require_activation()
    identity = require_runner()
    isolation = require_isolation(outside_netns, outside_pidns)
    thread_policy = select_thread_policy(admission_profile)
    if admission_profile is not None:
        if (not authenticated_zero_turn or not session_policy or capability_only or metadata_socket is None
                or patched_request is not None or prewarm_preparation is not None):
            raise Refused("default_policy_mode_refused")
        thread_policy.require_context(evidence)
    if type(authenticated_zero_turn) is not bool or bool(credential) != authenticated_zero_turn:
        raise Refused("zero_turn_auth_mode_mismatch")
    if metadata_socket is not None and not authenticated_zero_turn:
        raise Refused("metadata_requires_authenticated_zero_turn")
    if authenticated_zero_turn:
        from ghcp_ahp_diagnostics import DiagnosticRedactor
        import ghcp_ahp_zero_turn as zero_turn
        zero_turn.require_context()
        zero_turn.validate_credential(credential)
        if not session_policy or capability_only:
            raise Refused("zero_turn_auth_requires_session_policy")
    if prewarm_preparation is not None:
        import ghcp_ahp_prewarm_zero_turn as prewarm
        import ghcp_ahp_patched_runtime as patched
        # A separate, exact authenticated preparation scope. The generic/paying
        # activation path above remains locked, including direct Python callers.
        patched_request = prewarm.require_run(prewarm_preparation, root, evidence,
            authenticated_zero_turn=authenticated_zero_turn, session_policy=session_policy,
            capability_only=capability_only, metadata_socket=metadata_socket)
    mask = DiagnosticRedactor(credential) if authenticated_zero_turn else None
    prepared, source_evidence = verify_prepared(manifest, root, evidence, identity)
    wall_seconds = 120 if authenticated_zero_turn else MAX_RUNTIME_SECONDS
    deadline = time.monotonic() + wall_seconds
    record = {"schema": "ghcp-ahp-probe-receipt-v1", "runner": identity, "isolation": isolation,
              "vscode_version": manifest["vscode_version"], "vscode_commit": manifest["vscode_commit"], "codex_sdk_version": manifest["codex_sdk_version"],
              "artifacts": prepared["artifacts"], "binary_sha256": prepared["binary_sha256"],
              "source_contract": source_evidence, "source_evidence_sha256": prepared["source_evidence_sha256"],
              "authentication_supplied": authenticated_zero_turn, "credential_environment_inherited": False, "headless_started": False,
              "model_calls": 0, "model_call_evidence_boundary": "no_prompt_rpc_and_kernel_denied_external_egress_not_a_billing_receipt",
              "launch_allowed": False, "gate_ready": False, "served_model": "not_reported", "reasoning_effort": "not_reported", "context_window": "not_reported",
              "capability_only": capability_only, "session_policy_probe": session_policy, "session_create_requests": 0,
              "authenticated_zero_turn": authenticated_zero_turn,
              "metadata_reads": metadata_socket is not None,
              "backend_readiness": {"ready": False, "reason": "not_checked"},
              "probe_limits": {"wall_seconds": wall_seconds, "rpc_requests": 2 if capability_only else MAX_RPCS + authenticated_zero_turn, "prompt_turns": 0, "wire_bytes": MAX_WIRE_BYTES},
              "reason_codes": [], "status": "incomplete"}
    profile_options = {"admission_profile": admission_profile} if admission_profile is not None else {}
    if admission_profile is not None:
        record.update(thread_policy.LABELS)
    transport = process = rpc = watchdog = None
    try:
        with tempfile.TemporaryDirectory(prefix="ahp-") as temporary:
            scratch = Path(temporary)
            environment = child_environment(root, scratch)
            if metadata_socket is not None:
                # Pinned agentHostBootstrap.ts:136 + common/environmentService.ts:56.
                # Supported root config disables MCP attachment, NOT auth discovery.
                config = scratch / "server-data/data/User/globalStorage/agent-host-config.json"
                save_json(config, {"githubMcpServerEnabled": False})
                record["requested_root_config"] = {"githubMcpServerEnabled": False}
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
            if capability_only or session_policy:
                import ghcp_ahp_backend_diagnostics as backend_diagnostics
                import ghcp_ahp_wire_capture as wire_capture
                if session_policy:
                    environment["VSCODE_AGENT_HOST_CODEX_APP_SERVER_ARGS"] = json.dumps(thread_policy.NATIVE_ARGS)
                options = {"session_policy": True} if session_policy else {}
                if authenticated_zero_turn:
                    options.update(credential=credential, authenticated_zero_turn=True)
                    if metadata_socket is not None:
                        options["metadata_socket"] = metadata_socket
                if patched_request is not None:
                    options["patched_request"] = patched_request
                environment = wire_capture.install(root, scratch, environment, model_free=True, **options, **profile_options)
                if "--log" not in help_result["stdout"]:
                    raise Refused("backend_diagnostic_log_flag_unavailable")
            with socket.socket() as port_reservation:
                port_reservation.bind(("127.0.0.1", 0))
                port = port_reservation.getsockname()[1]
            command = [cli, "agent", "host", "--foreground", "--new-instance", "--without-connection-token", "--host", "127.0.0.1", "--port", str(port),
                       "--server-data-dir", str(scratch / "server-data"), "--user-data-dir", str(scratch / "user-data"), "--disable-telemetry"]
            if capability_only or session_policy:
                # The pinned supervisor forwards backend stdout/stderr only at
                # debug level (agent_host.rs:389,405). No timeout/ready change.
                command.extend(["--log", "debug"])
            primary_error = None
            try:
                process = CapturedProcess(command, environment, cwd=workspace)
                if authenticated_zero_turn:
                    watchdog = zero_turn.Watchdog(scratch, process.stop)
                    watchdog.start()
                while time.monotonic() < deadline:
                    if watchdog is not None:
                        watchdog.check()
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
                if capability_only or session_policy:
                    record["backend_readiness"] = backend_diagnostics.readiness(scratch)
                    if not record["backend_readiness"]["ready"]:
                        raise Refused("agent_host_backend_not_ready")
                if patched_request is not None:
                    # Loaded-byte evidence is mandatory BEFORE auth/session RPC.
                    # Pre-copy hashes and successful bootstrap alone are insufficient.
                    patched.verify_live_ready(scratch)
                if admission_profile is not None:
                    thread_policy.verify_live_ready(scratch)
                rpc = Rpc(transport, "ahp-session:/" + str(uuid.uuid4()), workspace.as_uri(),
                          capability_only=capability_only, session_policy=session_policy, credential=credential,
                          boundary_check=watchdog.enforce if watchdog is not None else None, require_mcp_disabled=metadata_socket is not None,
                          **profile_options)
                if session_policy:
                    from ghcp_ahp_management import ManagementBridge
                    # Mandatory for BOTH hosted session-policy entrypoints.
                    # Construction/readback failures never fall back to AHP creation.
                    rpc.management = ManagementBridge(scratch, deadline, owned_pid=process.process.pid,
                        boundary_check=watchdog.enforce if watchdog is not None else None,
                        sanitize=mask.clean if mask is not None else redact, **profile_options)
                results = (thread_policy.exercise(rpc, lambda: thread_policy.await_native_thread(scratch, deadline))
                           if session_policy else exercise_rpc(rpc))
                record["rpc_results"] = results
                record["codex_session"] = classify_rpc(results)
                if capability_only:
                    record["codex_session"]["evidence_boundary"] = "capability_only_zero_session_requests"
                if session_policy:
                    record["codex_session"]["evidence_boundary"] = "one_session_request_zero_turns_not_admission"
                if authenticated_zero_turn:
                    record["codex_session"] = {"provider_requested": "codex",
                        "authentication_rpc_succeeded": "result" in results.get("authenticate", {}),
                        "session_created": "result" in results.get("createSession", {}),
                        "evidence_boundary": "authenticated_session_only_not_model_or_gate_admission"}
                    if "result" not in results.get("authenticate", {}):
                        raise Refused("zero_turn_authentication_refused")
                    if "result" not in results.get("createSession", {}):
                        raise Refused("zero_turn_session_refused")
                    native_wait = results.get("native_wait", {})
                    if native_wait.get("error_replies", 0) or native_wait.get("invalid_replies", 0):
                        raise Refused("zero_turn_native_thread_failed")
                    if results.get("native_wait", {}).get("replies", 0) != 1:
                        raise Refused("zero_turn_native_thread_not_reported")
                record["headless_started"] = isinstance(results.get("initialize", {}).get("result"), dict) and results["initialize"]["result"].get("protocolVersion") in {"1.1.0", "1.0.0"}
                record["status"] = "probe_completed" if record["headless_started"] else "protocol_initialization_refused"
            except Exception as error:
                primary_error = Refused(watchdog.reason) if watchdog is not None and watchdog.reason else error
                raise primary_error
            finally:
                secondary_errors = []

                def retain_or_note(action):
                    try:
                        return action()
                    except Exception as error:
                        secondary_errors.append(error)
                        return None

                if watchdog is not None:
                    retain_or_note(watchdog.close)
                    if watchdog.reason and primary_error is None:
                        secondary_errors.append(Refused(watchdog.reason))

                # Snapshot before TERM and before TemporaryDirectory removes the
                # socket/log tree. Diagnostic failure must not skip cleanup or
                # replace the original transport/bootstrap refusal.
                if (capability_only or session_policy) and record["backend_readiness"]["reason"] == "not_checked":
                    record["backend_readiness"] = retain_or_note(lambda: backend_diagnostics.readiness(scratch))
                before = retain_or_note(lambda: backend_diagnostics.snapshot(scratch, process)) if capability_only or session_policy else None
                if transport is not None:
                    retain_or_note(transport.close)
                stopped = False
                if process is not None:
                    errors_before_stop = len(secondary_errors)
                    retain_or_note(process.stop)
                    stopped = len(secondary_errors) == errors_before_stop
                    record["host_process"] = retain_or_note(process.record)
                record["cleanup"] = ("owned_process_group_stopped_pid_namespace_exit_cleans_detached_children" if stopped
                    else "process_group_stop_unconfirmed_pid_namespace_exit_remains_cleanup_boundary")
                if capability_only or session_policy:
                    after = retain_or_note(lambda: backend_diagnostics.snapshot(scratch, process))
                    diagnostic_auth = {"credential": credential, "session_create_requests": session_create_requests(rpc)} if authenticated_zero_turn else {}
                    record["backend_startup"] = retain_or_note(lambda: backend_diagnostics.export(evidence, before=before, after=after,
                        primary_error_code=(str(primary_error) if isinstance(primary_error, Refused) else type(primary_error).__name__) if primary_error else None,
                        environment=environment, vscode_commit=manifest["vscode_commit"], **diagnostic_auth))
                    record["host_process"] = retain_or_note(lambda: backend_diagnostics.DiagnosticRedactor(credential).clean(record.get("host_process")))
                    export_auth = {"credential": credential} if authenticated_zero_turn else {}
                    if patched_request is not None:
                        export_auth["patched_request"] = patched_request
                    record["wire_capture"] = retain_or_note(lambda: wire_capture.export(scratch, evidence, **export_auth))
                    if record["wire_capture"] is not None and record["wire_capture"]["capture_status"] != "captured":
                        secondary_errors.append(Refused("wire_observer_not_started"))
                    if session_policy and record["wire_capture"] is not None:
                        if rpc is not None:
                            record["rpc_results"] = getattr(rpc, "policy_results", record.get("rpc_results", {}))
                        initialized = record.get("rpc_results", {}).get("initialize", {}).get("result", {})
                        record["headless_started"] = isinstance(initialized, dict) and initialized.get("protocolVersion") in {"1.1.0", "1.0.0"}
                        record["thread_policy"] = retain_or_note(lambda: thread_policy.export(evidence, record.get("rpc_results", {})))
                        if record["thread_policy"] is not None and record["thread_policy"]["safety_violation"]:
                            secondary_errors.append(Refused("session_policy_forbidden_activity"))
                        # A completed protocol exchange is not admission. Keep
                        # exporting observations even when zero-turn cannot
                        # establish served model/context/web-search evidence.
                        if authenticated_zero_turn and (record["thread_policy"] is None
                                or record["thread_policy"].get("admission_allowed") is not True):
                            secondary_errors.append(Refused("zero_turn_admission_refused"))
                errors_to_record = secondary_errors if primary_error is not None else secondary_errors[1:]
                record["reason_codes"].extend(str(error) if isinstance(error, Refused) else type(error).__name__ for error in errors_to_record)
                if primary_error is None and secondary_errors:
                    raise secondary_errors[0]
    except Exception as error:
        record["status"] = "probe_refused"
        record["reason_codes"].insert(0, str(error) if isinstance(error, Refused) else type(error).__name__)
        if isinstance(error, Refused) and hasattr(error, "native_binary_discovery"):
            record["native_binary_discovery"] = redact(error.native_binary_discovery)
    finally:
        if rpc is not None:
            record["rpc_sent"] = rpc.sent
            record["rpc_received"] = rpc.received
            record["session_create_requests"] = session_create_requests(rpc)
            managed = getattr(rpc, "management", None)
            if managed is not None:
                record["management_sent"] = managed.sent
                record["management_received"] = managed.received
        if mask is not None:
            mask.clean(record)
            record = mask.clean(record)
        if patched_request is not None:
            provenance = (record.get("wire_capture") or {}).get("patched_runtime")
            if provenance is None or provenance.get("runtime_load_status") != "measured":
                provenance = patched.refusal_fields(patched_request)
                record["status"] = "probe_refused"
                record["reason_codes"].append("patched_runtime_load_unmeasured_or_duplicate")
            record = patched.stamp(record, provenance)
            record["source_contract_scope"] = "upstream_only_overlay_identified_by_patched_receipt"
        if admission_profile is not None:
            record["admission_allowed"] = (record.get("thread_policy") or {}).get("admission_allowed", False)
        save_json(evidence / "probe.json", record)
        if authenticated_zero_turn:
            policy_path = evidence / getattr(thread_policy, "POLICY_FILE", "thread-policy.json")
            policy_record = strict_json(policy_path.read_text()) if policy_path.is_file() else {}
            # Separate schema: never accepted as a paid connection receipt.
            handshake = {"schema": "ghcp-ahp-authenticated-zero-turn-v1",
                "status": record["status"], "reason_codes": record["reason_codes"], "admission_allowed": False,
                "runner": identity, "requested_policy": thread_policy.POLICY,
                "auth_rpc_sent": any(row["method"] == "authenticate" for row in record.get("rpc_sent", [])),
                "auth_rpc_succeeded": "result" in record.get("rpc_results", {}).get("authenticate", {}),
                "requested_native_launch_args": thread_policy.NATIVE_ARGS,
                "observed": policy_record.get("observed", dict.fromkeys(thread_policy.EXPECTED, "not_reported")),
                "origins": policy_record.get("origins", {}), "verdicts": policy_record.get("verdicts", {}),
                "session_created": policy_record.get("session_created", False),
                "model_turn_start_requests": policy_record.get("model_turn_start_requests", "not_reported"),
                "model_turn_events": policy_record.get("model_turn_events", "not_reported"),
                "capi_requests": policy_record.get("capi_requests", "not_reported"),
                "capi_count_scope": "inference_only_metadata_gets_separate", "metadata_reads": metadata_socket is not None,
                "rpc_sent": record.get("rpc_sent", []), "rpc_results": record.get("rpc_results", {}),
                "thread_policy": record.get("thread_policy"), "wire_capture": record.get("wire_capture"),
                "limits": {"turns": 0, "capi_inference_requests": 0, "metadata_gets": 2 if metadata_socket is not None else 0,
                           "sessions": 1, "native_threads": 1, "wall_seconds": 120}}
            if admission_profile is not None:
                FIELDS = thread_policy.FIELDS
                handshake.update(schema="ghcp-default-unpatched-handshake-v1", **thread_policy.LABELS)
                handshake.update({key: policy_record[key] for key in FIELDS})
            elif "admission_scope" in policy_record:
                from ghcp_ahp_zero_turn_admission import FIELDS
                handshake.update({key: policy_record[key] for key in FIELDS})
            if patched_request is not None:
                handshake = patched.stamp(handshake, provenance)
            save_json(evidence / getattr(thread_policy, "HANDSHAKE_FILE", "handshake.json"), handshake)
            if admission_profile is not None:
                thread_policy.write_summary(evidence, handshake)
        if patched_request is not None:
            summary = {"schema": "ghcp-ahp-patched-summary-v1", "status": record["status"],
                "probe_exit": 0 if record["status"] == "probe_completed" else 2,
                "model_calls": 0, "launch_allowed": False, "reason_codes": record["reason_codes"]}
            if authenticated_zero_turn and "admission_scope" in policy_record:
                summary.update({key: policy_record[key] for key in FIELDS})
            summary = patched.stamp(summary, provenance)
            save_json(evidence / "summary.json", summary)
            if provenance["runtime_load_status"] == "measured":
                patched.write_summary(evidence, handshake=authenticated_zero_turn, policy=session_policy)
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
    parser.add_argument("--metadata-socket", type=Path)
    parser.add_argument("--patched-build-receipt", type=Path, help="Preparation only; activation remains locked pending owner decision")
    parser.add_argument("--patched-build-receipt-sha256")
    parser.add_argument("--prewarm-zero-turn-preparation", type=Path,
                        help="Same-HEAD tested build, brokered authenticated zero-turn preparation only")
    parser.add_argument("--admission-profile", choices=("default_policy_unpatched",),
                        help="Separate unpatched default-policy zero-turn observation; never read-only or paid admission")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--capability-only", action="store_true", help="No createSession RPC; observe native/CAPI boundaries without model work")
    modes.add_argument("--session-policy-probe", action="store_true", help="One exact Codex session; zero turns and zero outbound HTTP")
    modes.add_argument("--authenticated-zero-turn", action="store_true", help="Protected dispatch only: authenticate once, one session, no turns or HTTP")
    args = None
    patched_request = None
    admitted = False
    try:
        args = parser.parse_args(argv)
        if args.patched_build_receipt is not None or args.patched_build_receipt_sha256 is not None:
            import ghcp_ahp_patched_runtime as patched
            patched_request = {"path": args.patched_build_receipt, "sha256": args.patched_build_receipt_sha256}
            if args.patched_build_receipt is None or args.patched_build_receipt_sha256 is None:
                raise Refused("patched_build_request_refused")
        # NAS/local refusal happens before manifests, files, downloads or processes.
        require_runner()
        admitted = True
        if args.admission_profile is not None:
            if (args.mode != "probe" or not args.authenticated_zero_turn or args.metadata_socket is None
                    or patched_request is not None or args.prewarm_zero_turn_preparation is not None):
                raise Refused("default_policy_mode_refused")
            select_thread_policy(args.admission_profile).require_context(args.evidence)
        if patched_request is not None:
            # Do not read credentials or launch even a zero-turn host before the
            # pending owner decision. No flag/environment variable opens this.
            patched.require_activation()
        if args.metadata_socket is not None and not args.authenticated_zero_turn:
            raise Refused("metadata_requires_authenticated_zero_turn")
        if args.prewarm_zero_turn_preparation is not None:
            import ghcp_ahp_prewarm_zero_turn as prewarm
            if args.mode != "probe":
                raise Refused("prewarm_requires_brokered_zero_turn")
            prewarm.require_run(args.prewarm_zero_turn_preparation, args.prepared, args.evidence,
                authenticated_zero_turn=args.authenticated_zero_turn, session_policy=args.authenticated_zero_turn,
                capability_only=args.capability_only, metadata_socket=args.metadata_socket)
        credential = ""
        if args.authenticated_zero_turn:
            import ghcp_ahp_zero_turn as zero_turn
            zero_turn.require_context()
            if args.mode != "probe":
                raise Refused("zero_turn_probe_mode_required")
            credential = os.environ.pop("COPILOT_GITHUB_TOKEN", "")
            zero_turn.validate_credential(credential)
        manifest = load_manifest()
        if args.mode == "prepare":
            prepare(manifest, args.prepared, args.evidence)
            print('{"status":"prepared","model_calls":0}')
            return 0
        options = ({"capability_only": True} if args.capability_only else
                   {"session_policy": True, "authenticated_zero_turn": True, "credential": credential} if args.authenticated_zero_turn else
                   {"session_policy": True} if args.session_policy_probe else {})
        if args.metadata_socket is not None:
            options["metadata_socket"] = args.metadata_socket
        if patched_request is not None:
            options["patched_request"] = patched_request
        if args.prewarm_zero_turn_preparation is not None:
            options["prewarm_preparation"] = args.prewarm_zero_turn_preparation
        if args.admission_profile is not None:
            options["admission_profile"] = args.admission_profile
        result = run_probe(manifest, args.prepared, args.evidence, args.outside_netns, args.outside_pidns, **options)
        if args.prewarm_zero_turn_preparation is not None:
            import ghcp_ahp_patched_runtime as patched
            patched.verify_artifact_chain(args.evidence, handshake=True, policy=True)
        summary = ({"probe_exit": result, "model_calls": 0, "launch_allowed": False} if patched_request is None else
                   patched.verify_artifact_chain(args.evidence, handshake=args.authenticated_zero_turn, policy=True))
        if args.admission_profile is not None:
            selected = select_thread_policy(args.admission_profile).verify_chain(args.evidence)
            summary.update(admission_profile=args.admission_profile, admission_allowed=selected["admission_allowed"], execution_allowed=False)
        print(json.dumps(summary))
        return result
    except Exception as error:
        # Never echo arbitrary exception text, environment or credential material.
        code = str(error) if isinstance(error, Refused) else type(error).__name__
        failure = {"status": "refused", "reason_code": code, "model_calls": 0}
        if patched_request is not None:
            failure = patched.stamp(failure, patched.refusal_fields(patched_request))
        if isinstance(error, Refused) and hasattr(error, "native_binary_discovery"):
            failure["native_binary_discovery"] = redact(error.native_binary_discovery)
        if admitted:
            save_json(args.evidence / ("failure-" + args.mode + ".json"), failure)
        print(json.dumps(failure))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
