"""Dispatch-only authentication admission and immediate zero-turn cancellation.

No secret store, model, SDK or network is accessed here. Authentication is an
in-memory AHP RPC; the original session-only observer and kernel deny egress.
"""

from __future__ import annotations

import json
import os
import threading

from ghcp_ahp_errors import Refused


def require_context():
    expected = {"GITHUB_EVENT_NAME": "workflow_dispatch", "GHCP_AUTHENTICATED_ZERO_TURN": "true",
                "GHCP_PAID_EXECUTION": "false", "GHCP_CONNECTION_ONLY": "false"}
    if any(os.environ.get(key) != value for key, value in expected.items()):
        raise Refused("zero_turn_dispatch_opt_in_required")


def validate_credential(credential):
    if (type(credential) is not str or not 1 <= len(credential) <= 16384
            or any(character.isspace() or ord(character) < 33 or ord(character) > 126 for character in credential)):
        raise Refused("zero_turn_auth_source_unavailable")


class Watchdog:
    """Cancel the owned host on an observer refusal, including during auth I/O.

    The observer refuses BEFORE forwarding. This watchdog additionally stops
    the owned process group; it never retries a request or starts another host.
    """

    def __init__(self, state, cancel):
        self.state, self.cancel = state, cancel
        self.reason = None
        self.lock = threading.Lock()
        self.done = threading.Event()
        self.worker = threading.Thread(target=self._run, daemon=True)

    def poll(self):
        try:
            files = sorted((self.state / "wire").glob("wire-*.jsonl"))
            if len(files) > 16:
                raise Refused("zero_turn_observer_file_limit")
            total = 0
            for file in files:
                if file.is_symlink():
                    raise Refused("zero_turn_observer_path_refused")
                total += file.stat().st_size
                if total > 16 * 1024 * 1024:
                    raise Refused("zero_turn_observer_size_limit")
                for line in file.read_text().splitlines(keepends=True):
                    if not line.endswith("\n"):
                        continue
                    row = json.loads(line)
                    kind = row.get("kind")
                    method = str((row.get("value") or {}).get("method", ""))
                    if kind in {"blocked", "wire_parse_error"}:
                        raise Refused("zero_turn_observer_boundary_refused")
                    if kind in {"capi_request", "capi_headers", "capi_event", "capi_body"}:
                        raise Refused("zero_turn_capi_activity_refused")
                    if kind in {"ipc_request", "ipc_response"} and method.startswith(("turn/", "item/")):
                        raise Refused("zero_turn_native_work_refused")
        except Exception as error:
            with self.lock:
                first = self.reason is None
                if first:
                    self.reason = str(error) if isinstance(error, Refused) else "zero_turn_observer_invalid"
            if first:
                self.cancel()
            return False
        return True

    def _run(self):
        while not self.done.is_set() and self.poll():
            self.done.wait(0.05)

    def start(self):
        self.worker.start()

    def check(self):
        if self.reason:
            raise Refused(self.reason)

    def enforce(self):
        self.poll()
        self.check()

    def close(self):
        self.done.set()
        self.worker.join(timeout=10)
        if self.worker.is_alive():
            raise Refused("zero_turn_cancellation_not_completed")
