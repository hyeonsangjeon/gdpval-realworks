"""One fixed local management transaction; no auth, HTTP or model transport.

Staged-model readback and upstream policy resolution are NOT thread-applied
evidence. Only the unchanged native observer may establish that boundary.
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import socket
import stat
import struct
import time

from ghcp_ahp_errors import Refused
from ghcp_ahp_probe import DESIRED_MODEL, digest, redact, strict_json

BRIDGE = Path(__file__).with_name("ghcp_ahp_management_bridge.cjs")
EVIDENCE = "staged_model_and_upstream_policy_resolution_not_thread_applied"
MAX_REPLY = 2 * 1024 * 1024


class ManagementBridge:
    def __init__(self, state, deadline, *, owned_pid=None, boundary_check=None, sanitize=redact, admission_profile=None):
        if admission_profile not in (None, "default_policy_unpatched"):
            raise Refused("management_admission_profile_refused")
        self.admission_profile = admission_profile
        self.directory = Path(state) / "wire"
        self.deadline = deadline
        self.owned_pid = owned_pid
        self.boundary_check = boundary_check
        self.sanitize = sanitize
        self.index = 0
        self.failed = False
        self.sent = []
        self.received = []
        self.settings = None
        self.readback = None
        self.peer = None

    def _boundary(self):
        if self.boundary_check is not None:
            self.boundary_check()
        if time.monotonic() >= self.deadline:
            raise Refused("management_init_deadline")

    def _exchange(self, request):
        directory = self.directory
        if (not directory.is_absolute() or directory.resolve() != directory
                or any(p.is_symlink() for p in (directory, *directory.parents))
                or directory.stat().st_uid != os.getuid()
                or stat.S_IMODE(directory.stat().st_mode) != 0o700):
            raise Refused("management_directory_refused")
        owner_file, endpoint = directory / "management-owner.json", directory / "management.sock"
        for path, is_socket in ((owner_file, False), (endpoint, True)):
            info = path.lstat()
            if (info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600
                    or not (stat.S_ISSOCK(info.st_mode) if is_socket else stat.S_ISREG(info.st_mode))):
                raise Refused("management_socket_identity_refused")
        if owner_file.stat().st_size > 2048:
            raise Refused("management_owner_size_refused")
        owner = strict_json(owner_file.read_text())
        if owner.get("admission_profile") != self.admission_profile:
            raise Refused("management_admission_profile_refused")
        if (owner.get("schema") != "ghcp-ahp-management-owner-v1"
                or owner.get("bridge_sha256") != digest(BRIDGE)
                or type(owner.get("server_pid")) is not int or owner["server_pid"] <= 0
                or type(owner.get("agent_pid")) is not int or owner["agent_pid"] <= 0
                or type(owner.get("uid")) is not int or owner["uid"] != os.getuid()):
            raise Refused("management_owner_identity_refused")
        # AF_UNIX only. The server is the exact hash/fork-verified parent inside
        # the same isolated namespace, not a caller-selected management endpoint.
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as transport:
            transport.settimeout(min(20, max(0.001, self.deadline - time.monotonic())))
            transport.connect(str(endpoint))
            pid, uid, _gid = struct.unpack("3i", transport.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
            if (pid != owner["server_pid"] or uid != os.getuid()
                    or not self._owned_peer(pid)
                    or self.peer is not None and self.peer != (pid, uid, owner["agent_pid"])):
                raise Refused("management_peer_identity_refused")
            self.peer = (pid, uid, owner["agent_pid"])
            self._boundary()
            transport.sendall((json.dumps(request, allow_nan=False) + "\n").encode())
            response = bytearray()
            while True:
                part = transport.recv(65536)
                if not part:
                    break
                response.extend(part)
                self._boundary()
                if len(response) > MAX_REPLY:
                    raise Refused("management_reply_size_refused")
            if not response.endswith(b"\n"):
                raise Refused("management_reply_truncated")
            return strict_json(response.decode())

    def _owned_peer(self, pid):
        """Only the exact launched supervisor or its still-owned descendants.

        Read process IDs only, never another process's argv or environment.
        Missing/reparented processes and cycles fail closed before any IPC write.
        """
        if type(self.owned_pid) is not int or self.owned_pid <= 0:
            return False
        seen = set()
        try:
            for _ in range(16):
                if pid == self.owned_pid:
                    return True
                if pid <= 1 or pid in seen:
                    return False
                seen.add(pid)
                fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
                pid = int(fields[1])  # state, PPid; do not read cmdline/environ
        except (OSError, ValueError, IndexError):
            return False
        return False

    def _request(self, op, params):
        self._boundary()
        if self.failed or self.index >= 3 or op != ("configure", "readback", "create")[self.index]:
            raise Refused("management_init_order_refused")
        self.index += 1  # consume before IPC, including ambiguous/lost replies
        request = {"id": self.index, "op": op, "params": copy.deepcopy(params)}
        self.sent.append(request)
        try:
            response = self.sanitize(self._exchange(request))
            self._boundary()
            self.received.append(response)
            if (type(response) is not dict or type(response.get("id")) is not int
                    or response["id"] != self.index or type(response.get("ok")) is not bool):
                raise Refused("management_reply_identity_refused")
            if response["ok"] is not True:
                reason = response.get("reason", "")
                if not isinstance(reason, str) or not reason.startswith("management_") or not reason.replace("_", "").isalpha():
                    reason = "management_init_refused"
                raise Refused(reason)
            return response["result"]
        except Exception:
            self.failed = True
            raise

    def prepare(self, session, workspace, policy):
        from ghcp_ahp_thread_policy import POLICY, same

        default = None
        if self.admission_profile is not None:
            import ghcp_ahp_default_policy as default
            POLICY = default.POLICY

        expected = {"session": session, "workspace": workspace, "model": copy.deepcopy(DESIRED_MODEL), "config": copy.deepcopy(POLICY)}
        if not same(policy, POLICY):
            raise Refused("management_init_settings_refused")
        try:
            configured = self._request("configure", expected)
            if not same(configured, {"configured": True}):
                raise Refused("management_init_configure_unconfirmed")
            readback = self._request("readback", {})
            if default is not None:
                if (type(readback) is not dict or set(readback) != {"settings", "resolved_policy", "derived_permissions",
                        "evidence", "admission_allowed", "admission_profile"}
                        or not same(readback["settings"], expected) or readback["admission_profile"] != default.PROFILE
                        or readback["derived_permissions"] != "vscode-workspace" or readback["evidence"] != EVIDENCE
                        or readback["admission_allowed"] is not False):
                    raise Refused("management_init_readback_refused")
                if not same(default.validate_resolved(readback["resolved_policy"]), readback["resolved_policy"]):
                    raise Refused("management_init_readback_refused")
            elif not same(readback, {"settings": expected, "resolved_policy": POLICY,
                                  "derived_permissions": "vscode-workspace-read-only",
                                  "evidence": EVIDENCE, "admission_allowed": False}):
                raise Refused("management_init_readback_refused")
            self.settings, self.readback = copy.deepcopy(expected), copy.deepcopy(readback)
            return copy.deepcopy(readback)
        except Exception:
            self.failed = True
            raise

    def create(self):
        if self.readback is None or self.settings is None:
            raise Refused("management_init_readback_required")
        response = self._request("create", {})
        if type(response) is not dict or ("result" in response) == ("error" in response):
            self.failed = True
            raise Refused("management_create_reply_refused")
        if "result" in response:
            result = response["result"]
            if (type(result) is not dict or result.get("scheme") != "ahp-session"
                    or "ahp-session:" + result.get("path", "") != self.settings["session"]
                    or any(result.get(key) for key in ("authority", "query", "fragment"))):
                self.failed = True
                raise Refused("management_init_created_identity_refused")
        # IPC errors need not carry the AHP -32007 code. Preserve their original
        # fields; do not manufacture a JSON-RPC response or a native receipt.
        return {**response, "transport": "vscode-child-ipc", "method": "createSessionWithExtensions"}
