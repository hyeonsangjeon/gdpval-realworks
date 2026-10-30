"""AHP 1.1 client-side admission and loss-explicit capture, tested with fake I/O.

This module installs/launches/authenticates nothing. The existing paid workflow
exposes a *refusing draft*, not a live transport for this controller.

Worst-case boundary (not a provider request/billing ceiling): 0 further client
work notifications after closure; at most 1 already-admitted client turn.
Server-internal model/tool overshoot has NO finite proven bound. AHP's
toolCallReady can already be confirmed, and one turn can contain many requests.
The 50ms receive timeout is a polling target, NOT a worst-case stop latency.
"""

from __future__ import annotations

import base64
import copy
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import threading
import time

from ghcp_ahp_probe import DESIRED_MODEL, Refused, redact, save_json

NOT_REPORTED = "not_reported"
POLL_SECONDS = 0.05
CONTROL_TIMEOUT_SECONDS = 1.0
TERMINATE_TIMEOUT_SECONDS = 4.0
MAX_EVENT_BYTES = 2 * 1024 * 1024
MAX_CAPTURE_BYTES = 64 * 1024 * 1024
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_FILES = 256
OVERSHOOT = {
    "client_work_notifications_after_stop": 0,
    "already_admitted_client_turns": 1,
    "server_internal_model_requests": "no_finite_bound_proven",
    "server_internal_tool_calls": "no_finite_bound_proven",
    "wall_clock_stop_latency_seconds": "no_finite_bound_proven",
    "receive_poll_target_seconds": POLL_SECONDS,
}


@dataclass(frozen=True)
class Limits:
    turns: int = 64
    tool_calls: int = 32
    seconds: int = 1200

    def __post_init__(self):
        # Tests may tighten the limits, never relax the fixed gate values.
        if any(type(value) is not int or not minimum <= value <= maximum for value, minimum, maximum in
               ((self.turns, 1, 64), (self.tool_calls, 0, 32), (self.seconds, 1, 1200))):
            raise Refused("invalid_client_limits")


def draft_receipt():
    """Called only AFTER dispatch/runner/auth admission in the existing gate.

    Authentication alone must not open this path: server-side admission,
    live transport/auth mapping and actual Sol/Max/1M evidence remain unproved.
    """
    return {"schema_version": "ghcp-ahp-client-v1", "adapter": "ahp-draft",
            "status": "refused", "launch_allowed": False, "gate_ready": False,
            "reason_codes": ["ahp_paid_contract_unverified"], "model_calls": 0,
            "limits": asdict(Limits()), "overshoot_boundary": dict(OVERSHOOT),
            "reported": {key: NOT_REPORTED for key in
                         ("served_model", "model_version", "reasoning_effort", "context_window")}}


def _encoded(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()


def _identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9._:-]{1,160}", value):
        raise Refused("invalid_event_identifier")
    return value


def workspace_files(root):
    """Bounded, no-follow regular-file inventory after the owned host is stopped.

    Caller must provide its isolated task workspace, never HOME or the repo.
    Raw bytes are memory-only until redaction/exposure checks in capture().
    """
    root = Path(root)
    if (not root.is_absolute() or ".." in root.parts or root == Path("/")
            or any(p.is_symlink() for p in (root, *root.parents)) or not root.is_dir()):
        raise Refused("capture_workspace_refused")
    result, total, entries = {}, 0, 0
    def walk_error(error):
        raise Refused("capture_path_refused") from None
    try:
        for directory, dirs, names, descriptor in os.fwalk(root, follow_symlinks=False, onerror=walk_error):
            entries += len(dirs) + len(names)
            if entries > 4096:
                raise Refused("capture_file_limit")
            for name in dirs:
                if not stat.S_ISDIR(os.stat(name, dir_fd=descriptor, follow_symlinks=False).st_mode):
                    raise Refused("capture_path_refused")
            for name in sorted(names):
                if len(result) >= MAX_FILES:
                    raise Refused("capture_file_limit")
                flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
                with os.fdopen(os.open(name, flags, dir_fd=descriptor), "rb") as stream:
                    before = os.fstat(stream.fileno())
                    if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
                            or before.st_size > MAX_FILE_BYTES):
                        raise Refused("capture_file_refused")
                    raw = stream.read(MAX_FILE_BYTES + 1)
                    after = os.fstat(stream.fileno())
                    selected = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
                    identity = lambda info: (info.st_ino, info.st_dev, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
                    if identity(before) != identity(after) or identity(after) != identity(selected) or len(raw) != before.st_size:
                        raise Refused("capture_file_changed")
                total += len(raw)
                if total > MAX_CAPTURE_BYTES:
                    raise Refused("capture_file_limit")
                result[(Path(directory) / name).relative_to(root).as_posix()] = raw
    except OSError:
        raise Refused("capture_path_refused") from None
    return result


class SessionClient:
    """Single-chat controller with serialized admission and an injected I/O port.

    The port implements send(message, timeout), receive(timeout), and
    terminate(timeout)->bool (owned host/process group, never another process).
    There is deliberately no concrete live port in this draft. Offline tests
    use a fake port and fake authentication; they are not paid runtime proof.
    No resume, steer, queued messages, tool approvals or automatic retries.
    """

    def __init__(self, transport, session, chat, *, authenticated=False,
                 limits=Limits(), clock=time.monotonic, credential=None, finish_admitted_turn=False):
        if (not isinstance(session, str) or not re.fullmatch(r"ahp-session:/[A-Za-z0-9-]+", session)
                or not isinstance(chat, str) or not re.fullmatch(r"ahp-chat:/[A-Za-z0-9-]+", chat)
                or type(authenticated) is not bool or type(limits) is not Limits
                or type(finish_admitted_turn) is not bool
                or (credential is not None and (not isinstance(credential, str) or not credential))):
            raise Refused("invalid_session_binding")
        self.transport, self.session, self.chat = transport, session, chat
        self.authenticated, self.limits, self.clock = authenticated, limits, clock
        self.finish_admitted_turn = finish_admitted_turn
        self.started = clock()
        self.credential = credential
        self.lock = threading.RLock()
        self.done = threading.Event()
        self.turns, self.tools, self.active = set(), set(), set()
        self.turn_started = {}
        self.completed, self.sequences, self.channel_seq = set(), {}, {}
        self.wire, self.tool_events, self.commands, self.files_reported = [], [], [], []
        self.snapshots, self.settings, self.history = [], [], []
        self.text = {}
        self.bytes = self.client_seq = 0
        self.status, self.reason = "open", None
        self.cleanup = {"cancel_attempts": 0, "dispose_attempts": 0,
                        "cancel_acknowledged": False, "dispose_acknowledged": False,
                        "host_terminated": NOT_REPORTED, "control_errors": []}
        self.reported = {key: NOT_REPORTED for key in
                         ("model_id", "reasoning_effort", "context_window", "served_model", "model_version")}
        self.history_pending = False
        self.observed_turns = set()
        self.terminal_channels = set()

    def _safe(self, value):
        if isinstance(value, dict):
            if value.get("type") == "embeddedResource" and isinstance(value.get("data"), str):
                try:
                    decoded = base64.b64decode(value["data"], validate=True).decode("latin1")
                except (ValueError, UnicodeError):
                    decoded = ""
                if self._safe(decoded) != decoded:
                    value = {**value, "data": "[REDACTED_BINARY]"}
            return redact({self._safe(str(k)): self._safe(v) for k, v in value.items()})
        if isinstance(value, list):
            return [self._safe(item) for item in value]
        if isinstance(value, str) and self.credential:
            for form in (self.credential, json.dumps(self.credential)[1:-1]):
                value = value.replace(form, "[REDACTED]")
        return redact(value)

    def _record(self, direction, message):
        raw = _encoded(message)
        if len(raw) > MAX_EVENT_BYTES or self.bytes + len(raw) > MAX_CAPTURE_BYTES:
            raise Refused("capture_size_limit")
        self.bytes += len(raw)
        self.wire.append({"direction": direction, "after_stop": self.status != "open",
                          "elapsed_seconds": self.clock() - self.started, "message": copy.deepcopy(message)})

    def _dispatch(self, action):
        self.client_seq += 1
        return {"jsonrpc": "2.0", "method": "dispatchAction", "params": {
            "channel": self.chat, "clientSeq": self.client_seq, "action": action}}

    def _stop(self, reason, *, completed=False):
        # Close admission before ANY potentially blocking cancellation I/O.
        if self.status != "open":
            return
        self.status, self.reason = ("completed" if completed else "stopped"), reason
        self.done.set()
        controls = [self._dispatch({"type": "chat/turnCancelled", "turnId": turn,
                                  "duration": max(0, int((self.clock() - self.turn_started[turn]) * 1000))})
                    for turn in sorted(self.active)]
        controls.append({"jsonrpc": "2.0", "id": "dispose", "method": "disposeSession",
                         "params": {"channel": self.session}})
        for message in controls:
            key = "dispose_attempts" if message["method"] == "disposeSession" else "cancel_attempts"
            self.cleanup[key] += 1
            try:
                self._record("client_control", message)
            except Refused:
                self.cleanup["control_errors"].append("control_capture_limit")
            try:
                self.transport.send(message, timeout=CONTROL_TIMEOUT_SECONDS)
            except Exception:
                self.cleanup["control_errors"].append("control_send_failed")
        try:
            self.cleanup["host_terminated"] = self.transport.terminate(timeout=TERMINATE_TIMEOUT_SECONDS) is True
        except Exception:
            self.cleanup["host_terminated"] = False

    def _check(self):
        if self.status == "open":
            if self.clock() - self.started >= self.limits.seconds:
                self._stop("time_limit_reached")
            elif (len(self.turns) > self.limits.turns
                  or (len(self.turns) == self.limits.turns and not self.finish_admitted_turn)):
                self._stop("turn_limit_reached")
            elif self.tools and len(self.tools) >= self.limits.tool_calls:
                self._stop("tool_limit_reached")
        return self.status == "open"

    def tick(self):
        with self.lock:
            return self._check()

    def send_turn(self, turn_id, text):
        """The only work-producing client operation; never retry a failed send."""
        with self.lock:
            if not self._check():
                return False
            if not self.authenticated:
                self._stop("authentication_required")
                return False
            # A connection-only turn must finish before evidence can be checked.
            # Draining that one admitted turn NEVER admits a second notification.
            if len(self.turns) >= self.limits.turns:
                self._stop("turn_limit_reached")
                return False
            try:
                turn_id = _identifier(turn_id)
                if self.active or turn_id in self.turns or not isinstance(text, str) or not text:
                    raise Refused("turn_admission_refused")
                message = self._dispatch({"type": "chat/turnStarted", "turnId": turn_id,
                    "startedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "message": {"text": text, "origin": {"kind": "user"}, "model": copy.deepcopy(DESIRED_MODEL)}})
                self._record("client_work", message)
                # Reserve BEFORE send; missing echoes can never free a slot.
                self.turns.add(turn_id)
                self.active.add(turn_id)
                self.turn_started[turn_id] = self.clock()
                remaining = self.limits.seconds - (self.clock() - self.started)
                if remaining <= 0:
                    self._stop("time_limit_reached")
                    return False
                self.transport.send(message, timeout=min(CONTROL_TIMEOUT_SECONDS, remaining))
                self._check()
                return True
            except Exception:
                self._stop("client_send_refused")
                return False

    def _tool(self, turn, tool):
        self.tools.add((_identifier(turn), _identifier(tool)))

    def _tool_content(self, contents):
        for content in contents:
            if content.get("type") == "fileEdit":
                self.files_reported.append(copy.deepcopy(content))
            elif content.get("type") == "terminal":
                resource = content["resource"]
                # AHP types this as an opaque URI, not a mandated scheme. Only
                # bind it to this chat; never dereference it as an external URL.
                if not isinstance(resource, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9+.-]*:[^\x00-\x20]{1,2048}", resource):
                    raise Refused("terminal_resource_refused")
                self.terminal_channels.add(resource)
            elif content.get("type") == "subagent":
                raise Refused("autonomous_work_refused")

    def _part(self, turn_id, part):
        # ResponsePart uses `kind`; ToolResultContent uses `type` in AHP 1.1.
        if not isinstance(part.get("kind"), str):
            raise Refused("invalid_response_part")
        if part["kind"] == "toolCall":
            tool = part["toolCall"]
            self._tool(turn_id, tool["toolCallId"])
            self.tool_events.append({"source": "response_part_tool_state", "turn_id": turn_id,
                                     "tool_call": copy.deepcopy(tool)})
            self.commands.append({"source": "tool_input_not_execution_proof", "tool_call_id": tool["toolCallId"],
                                  "input": tool.get("toolInput", NOT_REPORTED)})
            self._tool_content(tool.get("content", []))
        elif part["kind"] in {"markdown", "reasoning"}:
            self.text[(_identifier(turn_id), _identifier(part["id"]))] = part["content"]
        elif part["kind"] == "contentRef":
            raise Refused("external_content_not_collected")

    def _snapshot(self, snapshot):
        if snapshot.get("resource") not in {self.chat, self.session}:
            raise Refused("snapshot_channel_refused")
        self.snapshots.append(copy.deepcopy(snapshot))
        seq = snapshot.get("fromSeq")
        if type(seq) is not int or seq < self.channel_seq.get(snapshot["resource"], -1):
            raise Refused("snapshot_sequence_refused")
        self.channel_seq[snapshot["resource"]] = seq
        state = snapshot["state"]
        if "config" in state:
            self.settings.append({"source": "server_snapshot_config", "config": state["config"]})
        if snapshot["resource"] != self.chat:
            return
        self.history_pending = bool(state.get("turnsNextCursor"))
        for turn in state.get("turns", []) + ([state["activeTurn"]] if state.get("activeTurn") else []):
            turn_id = _identifier(turn["id"])
            self.turns.add(turn_id)
            self.observed_turns.add(turn_id)
            if turn is state.get("activeTurn"):
                self.active.add(turn_id)
                self.turn_started.setdefault(turn_id, self.clock())
                if len(self.active) > 1:
                    raise Refused("concurrent_turn_refused")
            self.history.append(copy.deepcopy(turn))
            for part in turn.get("responseParts", []):
                self._part(turn_id, part)
            # Only retained historical messages, not request/echo/default/catalog.
            selection = turn.get("message", {}).get("model")
            if turn in state.get("turns", []) and isinstance(selection, dict):
                self.settings.append({"source": "server_historical_message_model", "turn_id": turn_id,
                                      "selection": copy.deepcopy(selection)})
                config = selection.get("config") or {}
                self.reported.update(model_id=selection.get("id") or NOT_REPORTED,
                    reasoning_effort=config.get("thinkingLevel") or NOT_REPORTED,
                    context_window=config.get("contextSize") or NOT_REPORTED)
                if any(actual not in (NOT_REPORTED, expected) for actual, expected in
                       ((self.reported["model_id"], DESIRED_MODEL["id"]),
                        (self.reported["reasoning_effort"], "max"), (self.reported["context_window"], 1_000_000))):
                    raise Refused("reported_setting_mismatch")
        if self.history_pending:
            # No silent history truncation. A future live port must page fetchTurns.
            raise Refused("history_pagination_required")

    def accept(self, message):
        """Retain every delivered frame, including late frames after cancellation.

        serverSeq is global, so gaps for unsubscribed channels are NOT losses.
        Identical replays are captured but not counted twice; divergent replays
        and per-channel reordering refuse. No automatic reconnect/resume.
        """
        with self.lock:
            try:
                self._record("server", message)
                if message.get("jsonrpc") != "2.0":
                    raise Refused("invalid_jsonrpc_version")
                if message.get("error"):
                    raise Refused("authentication_required" if message["error"].get("code") == -32007 else "ahp_error")
                if "result" in message:
                    result = message["result"] or {}
                    if message.get("id") == "dispose":
                        self.cleanup["dispose_acknowledged"] = True
                    for snapshot in result.get("snapshots", []) + ([result["snapshot"]] if result.get("snapshot") else []):
                        self._snapshot(snapshot)
                elif message.get("method") == "action":
                    envelope = message["params"]
                    channel, seq, action = envelope["channel"], envelope["serverSeq"], envelope["action"]
                    if type(seq) is not int or seq < 0:
                        raise Refused("invalid_server_sequence")
                    identity = _encoded(envelope)
                    if seq in self.sequences:
                        if self.sequences[seq] != identity:
                            raise Refused("divergent_event_replay")
                        return self._check()
                    if seq <= self.channel_seq.get(channel, -1):
                        raise Refused("event_order_refused")
                    self.sequences[seq], self.channel_seq[channel] = identity, seq
                    if envelope.get("rejectionReason"):
                        raise Refused("action_rejected")
                    self._action(channel, action)
                else:
                    raise Refused("unsupported_protocol_message")
                return self._check()
            except Exception as error:
                self._stop(str(error) if isinstance(error, Refused) else "invalid_ahp_event")
                return False

    def _action(self, channel, action):
        kind = action["type"]
        if kind.startswith("chat/") and channel != self.chat:
            raise Refused("additional_chat_refused")
        if kind.startswith("session/") and channel != self.session:
            raise Refused("foreign_session_refused")
        if kind.startswith("terminal/") and channel not in self.terminal_channels:
            raise Refused("unbound_terminal_refused")
        if kind == "chat/turnStarted":
            turn = _identifier(action["turnId"])
            self.turns.add(turn)
            self.observed_turns.add(turn)
            self.active.add(turn)
            self.turn_started.setdefault(turn, self.clock())
            if len(self.active) > 1:
                raise Refused("concurrent_turn_refused")
        elif kind.startswith("chat/toolCall"):
            if action["turnId"] not in self.turns:
                raise Refused("unknown_tool_turn")
            self._tool(action["turnId"], action["toolCallId"])
            self.tool_events.append(copy.deepcopy(action))
            if kind == "chat/toolCallDelta" and "content" in action:
                key = (_identifier(action["turnId"]), "tool:" + _identifier(action["toolCallId"]))
                self.text[key] = self.text.get(key, "") + action["content"]
            if kind == "chat/toolCallReady":
                self.commands.append({"source": "tool_input_not_execution_proof", "tool_call_id": action["toolCallId"],
                                      "input": action.get("toolInput", NOT_REPORTED)})
            if kind == "chat/toolCallComplete":
                self._tool_content(action.get("result", {}).get("content", []))
        elif kind in {"chat/turnComplete", "chat/turnCancelled", "chat/error"}:
            turn = _identifier(action["turnId"])
            if turn not in self.turns:
                raise Refused("unknown_terminal_turn")
            self.active.discard(turn)
            if kind == "chat/turnComplete":
                self.completed.add(turn)
            elif kind == "chat/turnCancelled":
                self.cleanup["cancel_acknowledged"] = True
                self._stop("server_cancelled")
            else:
                self._stop("server_turn_error")
        elif kind in {"chat/delta", "chat/reasoning"}:
            key = (_identifier(action["turnId"]), str(action.get("partId", kind)))
            self.text[key] = self.text.get(key, "") + action.get("content", "")
        elif kind == "chat/responsePart":
            self._part(_identifier(action["turnId"]), action["part"])
        elif kind in {"chat/configChanged", "session/configChanged"}:
            self.settings.append({"source": kind, "config": action["config"]})
        elif kind == "terminal/data":
            key = ("terminal", channel)
            self.text[key] = self.text.get(key, "") + action["data"]
        elif kind == "terminal/commandExecuted" or kind == "terminal/commandFinished":
            self.commands.append({"source": "terminal_event", **copy.deepcopy(action)})
        elif kind == "chat/turnsLoaded":
            self._snapshot({"resource": self.chat, "state": {"turns": action["turns"],
                            "turnsNextCursor": action.get("turnsNextCursor")},
                            "fromSeq": self.channel_seq[self.chat]})
        elif kind == "session/chatAdded" and action.get("summary", {}).get("resource") == self.chat:
            pass
        elif kind in {"chat/pendingMessageSet", "chat/turnResume", "chat/backgroundWorkSet", "session/chatAdded"}:
            raise Refused("autonomous_work_refused")
        # Other delivered actions (text/usage/terminal output/changesets) remain
        # intact in wire. They never become guessed counts or served settings.

    def run(self):
        """Pump with a separate deadline watchdog, including a silent connection."""
        def watch():
            while not self.done.wait(max(0, self.limits.seconds - (self.clock() - self.started))):
                if not self.tick():
                    return
        watchdog = threading.Thread(target=watch, daemon=True)
        watchdog.start()
        try:
            while self.tick():
                remaining = self.limits.seconds - (self.clock() - self.started)
                if remaining <= 0:
                    self.tick()
                    continue
                try:
                    message = self.transport.receive(timeout=min(POLL_SECONDS, remaining))
                except TimeoutError:
                    continue
                except Exception:
                    with self.lock:
                        if self._check():
                            self._stop("event_stream_lost")
                    break
                self.accept(message)
                if self.completed and not self.active and self.status == "open":
                    self.finish()
        finally:
            with self.lock:
                if self.status == "open":
                    self._stop("client_interrupted")
            watchdog.join(timeout=CONTROL_TIMEOUT_SECONDS)

    def finish(self):
        with self.lock:
            if self._check():
                complete = bool(self.completed) and not self.active and not self.history_pending
                self._stop("completed" if complete else "incomplete_transcript", completed=complete)

    def capture(self, path, *, workspace=None, baseline=None):
        """One exclusive, redacted JSON; never upload the raw state/workspace."""
        with self.lock:
            if self.status == "open" or self.cleanup["host_terminated"] is not True:
                raise Refused("capture_host_not_stopped")
            generated = []
            for name, raw in (workspace_files(workspace).items() if workspace is not None else []):
                digest = hashlib.sha256(raw).hexdigest()
                if (baseline or {}).get(name) == digest:
                    continue
                try:
                    text = raw.decode("utf-8")
                except UnicodeDecodeError:
                    # Check bytes BEFORE base64 can conceal a credential.
                    text = raw.decode("latin1")
                    if self._safe(text) != text:
                        raise Refused("binary_credential_exposure_refused")
                    value, encoding = base64.b64encode(raw).decode("ascii"), "base64"
                else:
                    value, encoding = self._safe(text), "utf-8"
                generated.append({"path": self._safe(name), "source_sha256": digest, "source_bytes": len(raw),
                                  "encoding": encoding, "content": value,
                                  "redacted": encoding == "utf-8" and value != text})
            # Split deltas can spell a secret only when reassembled. In that case
            # redact every string in the affected raw frames, not just the join.
            unsafe_stream = any(self._safe(text) != text for text in self.text.values())
            wire = copy.deepcopy(self.wire)
            tool_events = copy.deepcopy(self.tool_events)
            if unsafe_stream:
                for frame in wire:
                    action = frame["message"].get("params", {}).get("action", {})
                    if action.get("type") in {"chat/delta", "chat/reasoning", "chat/toolCallDelta"}:
                        action["content"] = "[REDACTED_STREAM]"
                    elif action.get("type") == "terminal/data":
                        action["data"] = "[REDACTED_STREAM]"
                    elif action.get("type") == "chat/responsePart" and action.get("part", {}).get("kind") in {"markdown", "reasoning"}:
                        action["part"]["content"] = "[REDACTED_STREAM]"
                for action in tool_events:
                    if action.get("type") == "chat/toolCallDelta":
                        action["content"] = "[REDACTED_STREAM]"
            result = self._safe({"schema_version": "ghcp-ahp-client-v1", "status": self.status,
                "reason_codes": [self.reason], "gate_ready": False, "limits": asdict(self.limits),
                "elapsed_seconds": self.clock() - self.started, "overshoot_boundary": dict(OVERSHOOT),
                "counts": {"admitted_or_observed_turns": len(self.turns), "observed_turns": len(self.observed_turns),
                           "observed_tool_calls": len(self.tools), "model_requests": NOT_REPORTED,
                           "premium_requests": NOT_REPORTED},
                "observed_overshoot": {"turns": max(0, len(self.turns) - self.limits.turns),
                                       "tool_calls": max(0, len(self.tools) - self.limits.tool_calls)},
                "requested_model": DESIRED_MODEL, "reported": self.reported, "reported_settings": self.settings,
                "transcript": {"wire": wire, "snapshots": self.snapshots, "history": self.history,
                               "text": [{"turn_id": key[0], "part_id": key[1], "text": text}
                                        for key, text in self.text.items()]},
                "tool_calls": tool_events, "commands": self.commands,
                "reported_file_edits": self.files_reported,
                "generated_files": generated if workspace is not None else NOT_REPORTED,
                "cleanup": self.cleanup, "capture_boundary": "all_delivered_frames_not_unseen_server_work",
                "workspace_collected": workspace is not None})
            save_json(path, result)
            return result
