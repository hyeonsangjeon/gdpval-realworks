"""Explicit authenticated connection-only transport; NEVER imported by the probe.

No retries of authentication, session creation or work. Only the owning
GitHub-hosted dispatch PID namespace may launch this transport. This is not
an AHP native tool/request cap; any delivered tool event closes the client.
"""

from __future__ import annotations

from contextlib import contextmanager
import copy
import errno
import json
import os
from pathlib import Path
import queue
import re
import secrets
import socket
import threading
import time
import uuid

from ghcp_ahp_probe import (CapturedProcess, Refused, ROOT_CHANNEL, WebSocket, child_environment,
                            load_manifest, redact, require_runner, save_json, verify_prepared)

CONFIG = {"codex.approvalPolicy": "untrusted", "codex.sandboxMode": "read-only",
          "codex.networkAccessEnabled": False, "codex.webSearchMode": "disabled",
          "codex.modelReasoningEffort": "max"}
RESOURCE = "https://api.github.com"


def require_namespace():
    outside = os.environ.get("GHCP_CONNECTION_OUTSIDE_PIDNS", "")
    if (not re.fullmatch(r"pid:\[[0-9]+\]", outside) or os.getpid() != 1
            or os.readlink("/proc/self/ns/pid") == outside):
        raise Refused("connection_pid_isolation_required")
    status = Path("/proc/self/status").read_text()
    if (os.geteuid() == 0 or not re.search(r"^NoNewPrivs:\s+1$", status, re.M)
            or not re.search(r"^CapEff:\s+0+$", status, re.M)):
        raise Refused("connection_privilege_drop_required")


class ConnectionPort:
    def __init__(self, wire, process, deadline, credential):
        self.wire, self.process, self.deadline, self.credential = wire, process, deadline, credential
        self.session = "ahp-session:/" + str(uuid.uuid4())
        self.chat = None
        self.turns_sent = 0
        self.closed = False
        self.rpc_id = 0
        self.handshake = []
        self.events = queue.Queue(maxsize=256)
        self.reader = None
        self.failure = None
        self.send_lock = threading.Lock()
        self.stop_lock = threading.Lock()
        self.capture_lock = threading.Lock()

    def _remaining(self):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise Refused("connection_deadline_exceeded")
        return remaining

    def _safe(self, value):
        if isinstance(value, dict):
            return redact({self._safe(str(k)): self._safe(v) for k, v in value.items()})
        if isinstance(value, list):
            return [self._safe(v) for v in value]
        if isinstance(value, str):
            value = value.replace(self.credential, "[REDACTED]").replace(
                json.dumps(self.credential)[1:-1], "[REDACTED]")
        return redact(value)

    def _capture(self, direction, message):
        # Keep no credential-bearing copy, even in the retained handshake list.
        with self.capture_lock:
            self.handshake.append({"direction": direction, "message": self._safe(message)})
            if len(self.handshake) > 256 or len(json.dumps(self.handshake)) > 8 * 1024 * 1024:
                raise Refused("connection_handshake_size_limit")

    def rpc(self, method, params):
        if method not in {"initialize", "authenticate", "resolveSessionConfig", "createSession", "subscribe"}:
            raise Refused("connection_rpc_refused")
        if self.turns_sent or self.rpc_id >= 6:
            raise Refused("connection_rpc_limit")
        self._remaining()
        self.rpc_id += 1
        message = {"jsonrpc": "2.0", "id": self.rpc_id, "method": method, "params": params}
        self._capture("client", message)
        self.wire.send(message)
        for _ in range(256):
            self._remaining()
            reply = self.wire.receive()
            self._capture("server", reply)
            if not isinstance(reply, dict) or reply.get("jsonrpc") != "2.0":
                raise Refused("connection_rpc_invalid")
            action = reply.get("params", {}).get("action", {})
            if action.get("type", "").startswith(("chat/turn", "chat/toolCall")):
                raise Refused("connection_work_before_prompt")
            if "id" in reply:
                if ("method" in reply or type(reply["id"]) is not int or reply["id"] != self.rpc_id
                        or ("error" in reply) == ("result" in reply)):
                    raise Refused("connection_rpc_identity_refused")
                if "error" in reply:
                    raise Refused("authentication_required" if reply["error"].get("code") == -32007
                                  else "connection_rpc_error")
                return reply["result"]
        raise Refused("connection_rpc_event_limit")

    def initialize(self, workspace):
        client_id = str(uuid.uuid4())
        initialized = self.rpc("initialize", {"channel": ROOT_CHANNEL, "protocolVersions": ["1.1.0"],
            "clientId": client_id, "clientInfo": {"name": "ghcp-ahp-connection-only", "version": "1"},
            "initialSubscriptions": [ROOT_CHANNEL], "locale": "en-US"})
        if initialized.get("protocolVersion") != "1.1.0":
            raise Refused("connection_protocol_refused")
        roots = [s for s in initialized.get("snapshots", []) if s.get("resource") == ROOT_CHANNEL]
        agents = [a for s in roots for a in s.get("state", {}).get("agents", []) if a.get("provider") == "codex"]
        if len(agents) != 1 or RESOURCE not in {r.get("resource") for r in agents[0].get("protectedResources", [])}:
            raise Refused("connection_auth_resource_refused")
        self.rpc("authenticate", {"channel": ROOT_CHANNEL, "resource": RESOURCE, "token": self.credential})
        resolved = self.rpc("resolveSessionConfig", {"channel": ROOT_CHANNEL, "provider": "codex",
                            "workingDirectory": workspace, "config": copy.deepcopy(CONFIG)})
        properties = resolved.get("schema", {}).get("properties", {})
        if any(key not in properties or resolved.get("values", {}).get(key) != value for key, value in CONFIG.items()):
            raise Refused("connection_requested_policy_unavailable")
        # These are requested restrictions, NOT proof of a server-native 0-tool
        # budget. No active client tools/customizations/approvals are supplied.
        self.rpc("createSession", {"channel": self.session, "provider": "codex", "workingDirectories": [workspace],
            "config": copy.deepcopy(CONFIG), "activeClient": {"clientId": client_id, "tools": [], "customizations": []}})
        subscribed = self.rpc("subscribe", {"channel": self.session})
        snapshot = subscribed.get("snapshot", {})
        state = snapshot.get("state", {})
        chats = state.get("chats", [])
        chat = state.get("defaultChat")
        if (snapshot.get("resource") != self.session or len(chats) != 1
                or chats[0].get("resource") != chat or not isinstance(chat, str)
                or not re.fullmatch(r"ahp-chat:/[A-Za-z0-9-]+", chat)):
            raise Refused("connection_fresh_chat_refused")
        self.chat = chat
        initial = self.rpc("subscribe", {"channel": chat}).get("snapshot", {})
        chat_state = initial.get("state", {})
        if (initial.get("resource") != chat or chat_state.get("turns") or chat_state.get("activeTurn")
                or chat_state.get("turnsNextCursor") or chat_state.get("queuedMessages")):
            raise Refused("connection_fresh_chat_refused")
        self.events.put({"jsonrpc": "2.0", "id": "initial", "result": {"snapshots": [snapshot, initial]}})
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()

    def _read(self):
        try:
            while not self.closed:
                value = self.wire.receive()
                # The root subscription is for discovery; retain those unrelated
                # catalog updates without treating them as chat evidence.
                if value.get("method") == "action" and value.get("params", {}).get("channel") == ROOT_CHANNEL:
                    self._capture("server", value)
                    continue
                self.events.put_nowait(value)
        except Exception:
            if not self.closed:
                self.failure = "connection_event_stream_lost"
            try:
                self.events.put_nowait({"jsonrpc": "2.0", "error": {"code": -32000}})
            except queue.Full:
                self.terminate(timeout=4.0)

    def send(self, message, timeout):
        from ghcp_ahp_connection import PROMPT, TURN
        from ghcp_ahp_probe import DESIRED_MODEL
        with self.send_lock:
            if self.closed:
                raise Refused("connection_closed")
            kind = message.get("params", {}).get("action", {}).get("type")
            if kind == "chat/turnStarted":
                action = message["params"]["action"]
                if (self.turns_sent or message["params"].get("channel") != self.chat or action.get("turnId") != TURN
                        or action.get("message", {}).get("text") != PROMPT
                        or action.get("message", {}).get("model") != DESIRED_MODEL):
                    raise Refused("connection_prompt_refused")
                self._remaining()
                self.turns_sent = 1  # Reserve even when the send subsequently fails.
            elif kind == "chat/turnCancelled":
                if message["params"].get("channel") != self.chat or message["params"]["action"].get("turnId") != TURN:
                    raise Refused("connection_cancel_refused")
            elif message.get("method") == "disposeSession":
                if message.get("params") != {"channel": self.session}:
                    raise Refused("connection_dispose_refused")
            else:
                raise Refused("connection_work_not_allowed")
            # A send timeout must not mutate the concurrently reading socket's
            # receive timeout. sendall is bounded by the outer PID-1 deadline.
            self.wire.send(message)

    def receive(self, timeout):
        self.process.check()
        self._remaining()
        if self.failure:
            raise Refused(self.failure)
        try:
            return self.events.get(timeout=timeout)
        except queue.Empty:
            raise TimeoutError from None

    def terminate(self, timeout):
        with self.stop_lock:
            if not self.closed:
                self.closed = True
                try:
                    self.wire.socket.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                self.wire.close()
                self.process.stop()
            return self.process.process.poll() is not None

    def handshake_capture(self):
        with self.capture_lock:
            return self._safe({"schema_version": "ghcp-ahp-connection-handshake-v1", "frames": self.handshake,
                               "requested_session_policy": CONFIG, "policy_is_native_zero_tool_proof": False})


@contextmanager
def open_connection_port(prepared, evidence, state, credential):
    from ghcp_sol_paid_gate import require_dispatch
    require_dispatch()
    identity = require_runner()
    require_namespace()
    manifest = load_manifest()
    verify_prepared(manifest, prepared, evidence, identity)
    if (not state.is_absolute() or state.exists() or ".." in state.parts
            or any(p.is_symlink() for p in (state, *state.parents))):
        raise Refused("connection_state_refused")
    state.mkdir(mode=0o700)
    environment = child_environment(prepared, state)  # No inherited auth or login.
    workspace = state / "workspace"
    workspace.mkdir(mode=0o700)
    # Disable optional host integrations in this fresh user's host config.
    save_json(state / "user-data/User/globalStorage/agent-host-config.json",
              {"githubMcpServerEnabled": False, "artifactTools": False, "mcpServers": {}})
    local_token = secrets.token_hex(32)
    token_file = state / "local-transport-token"
    with os.fdopen(os.open(token_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "w") as stream:
        stream.write(local_token)
    deadline = time.monotonic() + 120
    process = wire = port = None
    try:
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            number = reservation.getsockname()[1]
        command = [str(prepared / "cli/code"), "agent", "host", "--foreground", "--new-instance",
                   "--connection-token-file", str(token_file), "--host", "127.0.0.1", "--port", str(number),
                   "--server-data-dir", str(state / "server-data"), "--user-data-dir", str(state / "user-data"),
                   "--disable-telemetry"]
        process = CapturedProcess(command, environment, cwd=workspace)
        while time.monotonic() < deadline:
            process.check()
            if process.process.poll() is not None:
                raise Refused("connection_host_exited")
            try:
                wire = WebSocket(number, deadline, connection_token=local_token)
                break
            except OSError as error:
                if error.errno not in (errno.ECONNREFUSED, errno.ECONNRESET):
                    raise
                time.sleep(0.05)
        if wire is None:
            raise Refused("connection_startup_deadline")
        port = ConnectionPort(wire, process, deadline, credential)
        port.initialize(workspace.as_uri())
        yield port
    finally:
        if port is not None:
            port.terminate(timeout=4.0)
        else:
            if wire is not None:
                wire.close()
            if process is not None:
                process.stop()
        # No auth state, host logs, token file or raw workspace is published.
        # Outer --kill-child PID namespace closes any detached descendants.
