"""Session-owned receipts for the pinned Codex app-server transport.

The SDK's stdio settings are not served identity. An attempt-owned loopback
observer can additionally count forwarded native HTTP attempts and read the
provider response body's model, with a snapshot-bound per-attempt request cap.
It neither attests a deployment/version nor clears a launch or billing gate.
No private body is retained. A saved document cannot recreate the in-process
witness for task acceptance.
"""

from __future__ import annotations

import json
import os
import re
import signal
import socket
import threading
import time
import uuid
from contextlib import contextmanager
from http.client import HTTPSConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml

import gpt56_pilot_input_capture as capture
import gpt56_pilot_deployment_binding as deployment
import gpt56_sol_codex_pilot_preflight as pilot
from core.cost_receipts import make_call_id
from core.azure_ai_clients import EndpointKind, classify_endpoint
from gpt54_codex_input_capture import _write_no_clobber
from gpt54_run_config_bundle import _held_parents, _path, _root
from gpt54_v2_grading_input import _read_bytes

DIRECTORY = "pilot-wire-receipts"
READY_PATH = "pilot-wire-receipts-ready.json"
RESERVATION = DIRECTORY + ".reservation.json"
BOUNDARY = "codex_app_server_transport_not_foundry_http_or_served_identity"
REFUSAL = "pilot_wire_receipt_refused"
_bytes, _digest = capture._bytes, capture._digest
_USAGE_FIELDS = {"inputTokens", "cachedInputTokens", "cacheWriteInputTokens",
                 "outputTokens", "reasoningOutputTokens", "totalTokens"}
PROVIDER_OBSERVATION_SOURCE = "attempt_owned_loopback_forward_attempts_and_response_body"
NATIVE_REQUEST_CAP_EXCEEDED = "native_request_cap_exceeded"
NATIVE_INPUT_CAP_EXCEEDED = "native_input_token_cap_exceeded"
NATIVE_OUTPUT_CAP_EXCEEDED = "native_output_token_cap_exceeded"
NATIVE_DEADLINE_EXCEEDED = "native_attempt_deadline_exceeded"
NATIVE_TASK_CAP_EXCEEDED = "native_task_request_cap_exceeded"
NATIVE_PILOT_CAP_EXCEEDED = "native_pilot_request_cap_exceeded"
NATIVE_USAGE_UNVERIFIED = "native_token_usage_unverified"
NATIVE_INPUT_PRECHECK_EXCEEDED = "native_input_token_precheck_exceeded"
NATIVE_OUTPUT_PRECHECK_EXCEEDED = "native_output_token_precheck_exceeded"
NATIVE_TOKEN_REQUEST_UNVERIFIED = "native_token_request_unverified"
NATIVE_OUTPUT_LIMIT_UNAVAILABLE = "native_output_token_limit_unavailable"
_TOKEN_PRECHECK_STOPS = {NATIVE_INPUT_PRECHECK_EXCEEDED, NATIVE_OUTPUT_PRECHECK_EXCEEDED,
                         NATIVE_TOKEN_REQUEST_UNVERIFIED, NATIVE_OUTPUT_LIMIT_UNAVAILABLE,
                         NATIVE_USAGE_UNVERIFIED}
_CAP_STOPS = {NATIVE_REQUEST_CAP_EXCEEDED, NATIVE_INPUT_CAP_EXCEEDED, NATIVE_OUTPUT_CAP_EXCEEDED,
              NATIVE_DEADLINE_EXCEEDED, NATIVE_TASK_CAP_EXCEEDED, NATIVE_PILOT_CAP_EXCEEDED,
              *_TOKEN_PRECHECK_STOPS}
_TOKEN_BOUNDARY = "client_estimate_precheck_and_usage_stop_not_server_hard_limit"
_INPUT_ESTIMATOR = "serialized_json_utf8_bytes_one_byte_per_estimated_token_not_a_tokenizer"
NATIVE_CAPS_SHA256 = "7c3c139bb96333e939b4dc43939c05c2f848313d907c8cade052afde18855fb6"
_NATIVE_CAPS_PATH = Path(__file__).resolve().parent / "experiments/execution_envelope/gpt56_sol_native_caps_draft_20261024.yaml"
_MODEL = re.compile(r"gpt-5\.6-sol(?:-fast)?(?:-20[0-9]{2}-[0-9]{2}-[0-9]{2})?\Z")
_CAPTURE_BYTES = 256 * 1024  # Observation memory, not a request/output quota.
_REQUEST_CAPTURE_BYTES = 1024 * 1024  # Bounded inspection, not native tokens.
_CHUNK_BYTES = 64 * 1024
_HOP_HEADERS = {"host", "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
                "te", "trailer", "transfer-encoding", "upgrade", "cookie", "set-cookie"}
_OBSERVATION_REASONS = {
    None, "observer_not_installed", "observer_start_failed", "observer_not_closed",
    "unsupported_native_route", "no_provider_requests", "response_model_not_returned",
    "response_model_not_allowlisted", "response_models_differ", "response_capture_incomplete",
    "response_capture_limit", "malformed_response", "encoded_response", "provider_response_error",
    "redirect_refused", "transport_failed", "deadline_exceeded", "invalid_observation",
}


def _provider_summary(reason="observer_not_installed") -> dict:
    return {"source": PROVIDER_OBSERVATION_SOURCE,
            "native_request_count": None, "native_request_count_reason": reason,
            "served_model": None, "served_model_reason": reason,
            "served_model_version": None, "served_model_version_reason": "not_observed",
            "provider_receipt_confirmed": False, "native_cap_enforced": False,
            "native_request_limit": None, "native_request_limit_sha256": None,
            "native_request_blocked_count": None, "native_request_cap_reason": None,
            "runtime_caps": None}


def _native_request_limit() -> int:
    """Read the unchanged caps snapshot, not a default or a launch permission.

    The registration still has null native caps. The owner's bounded enforcement
    direction selects this exact draft's per-attempt value, not new plan bytes.
    """
    return _native_caps()["per_attempt"]["native_model_calls"]


def _native_caps() -> dict:
    """Read all thresholds from the same sealed, unchanged draft."""
    with _closed():
        data = _read_bytes(_NATIVE_CAPS_PATH, size=7343, sha256=NATIVE_CAPS_SHA256)
        caps = yaml.safe_load(data)
        # The sealed caps draft still names the unchanged 2026-10-23 profile.
        _require(caps["registered_plan"] == pilot.SOURCE_PROFILE_PREVIOUS)
        fields = {"per_attempt": ("native_model_calls", "input_tokens", "output_tokens", "wall_clock_seconds"),
                  "per_task": ("native_model_calls",), "per_pilot": ("native_model_calls",)}
        result = {scope: {key: caps[scope][key] for key in keys} for scope, keys in fields.items()}
        _require(all(type(value) is int and 0 < value < 2 ** 63
                     for limits in result.values() for value in limits.values()))
        return result


class _NativeRequestBudget:
    """Run-owned forward reservations. Failures are counted and never refunded.

    This object is created with the existing non-adoptable wire session, not
    from a saved receipt, a new runner, or an infrastructure retry.
    """

    def __init__(self, task_ids):
        _require(type(task_ids) in (list, tuple) and len(task_ids) == len(set(task_ids)) == 5)
        self.limits = _native_caps()
        self.lock = threading.Lock()
        self.counts = {task_id: 0 for task_id in task_ids}
        self.total = 0

    def _reason(self, task_id):
        _require(task_id in self.counts)
        if self.total >= self.limits["per_pilot"]["native_model_calls"]:
            return NATIVE_PILOT_CAP_EXCEEDED
        if self.counts[task_id] >= self.limits["per_task"]["native_model_calls"]:
            return NATIVE_TASK_CAP_EXCEEDED
        return None

    def require_available(self, task_id):
        with self.lock:
            _require(self._reason(task_id) is None)

    def reserve(self, task_id):
        with self.lock:
            reason = self._reason(task_id)
            if reason is None:
                self.counts[task_id] += 1
                self.total += 1
            return reason

    def snapshot(self, task_id):
        with self.lock:
            return {"task_requests": self.counts[task_id], "pilot_requests": self.total}


def _checked_runtime_caps(raw, *, count):
    if type(raw) is not dict:
        return False
    caps = _native_caps()
    expected = {"sha256", "input_token_limit", "output_token_limit", "input_tokens", "output_tokens",
                "token_boundary", "token_hard_limit_enforced", "wall_seconds_limit", "effective_wall_seconds",
                "task_request_limit", "pilot_request_limit", "task_requests", "pilot_requests", "stop_reason",
                "client_token_precheck"}
    if (set(raw) != expected or raw["sha256"] != NATIVE_CAPS_SHA256
            or raw["token_boundary"] != _TOKEN_BOUNDARY or raw["token_hard_limit_enforced"] is not False
            or type(raw["stop_reason"]) not in (str, type(None))
            or raw["stop_reason"] not in _CAP_STOPS | {None}):
        return False
    for field, scope, key in (("input_token_limit", "per_attempt", "input_tokens"),
                              ("output_token_limit", "per_attempt", "output_tokens"),
                              ("wall_seconds_limit", "per_attempt", "wall_clock_seconds"),
                              ("task_request_limit", "per_task", "native_model_calls"),
                              ("pilot_request_limit", "per_pilot", "native_model_calls")):
        if type(raw[field]) is not int or raw[field] != caps[scope][key]:
            return False
    duration = raw["effective_wall_seconds"]
    if type(duration) not in (int, float) or not 0 < duration <= raw["wall_seconds_limit"]:
        return False
    for field in ("input_tokens", "output_tokens", "task_requests", "pilot_requests"):
        if raw[field] is not None and not (type(raw[field]) is int and 0 <= raw[field] < 2 ** 63):
            return False
    if (raw["input_tokens"] is None) != (raw["output_tokens"] is None):
        return False
    task, total = raw["task_requests"], raw["pilot_requests"]
    if (task is None) != (total is None):
        return False
    if task is not None and (not 0 <= task <= raw["task_request_limit"]
                             or not task <= total <= raw["pilot_request_limit"]
                             or count is not None and count > task):
        return False
    reason = raw["stop_reason"]
    if reason == NATIVE_TASK_CAP_EXCEEDED and task != raw["task_request_limit"]:
        return False
    if reason == NATIVE_PILOT_CAP_EXCEEDED and total != raw["pilot_request_limit"]:
        return False
    for field, stop in (("input_tokens", NATIVE_INPUT_CAP_EXCEEDED), ("output_tokens", NATIVE_OUTPUT_CAP_EXCEEDED)):
        if reason == stop and (raw[field] is None or raw[field] <= raw[field[:-1] + "_limit"]):
            return False
    if reason is None and any(raw[field] is not None and raw[field] > raw[field[:-1] + "_limit"]
                              for field in ("input_tokens", "output_tokens")):
        return False
    check = raw["client_token_precheck"]
    fields = {"enabled", "input_estimator", "server_hard_limit_verified", "checked_requests",
              "blocked_requests", "usage_known", "accounted_input_tokens", "accounted_output_tokens",
              "remaining_input_tokens", "remaining_output_tokens", "last_input_estimate",
              "last_output_limit"}
    if (type(check) is not dict or set(check) != fields or check["enabled"] is not True
            or check["input_estimator"] != _INPUT_ESTIMATOR
            or check["server_hard_limit_verified"] is not False or type(check["usage_known"]) is not bool):
        return False
    for name in fields - {"enabled", "input_estimator", "server_hard_limit_verified", "usage_known"}:
        value = check[name]
        if value is not None and not (type(value) is int and 0 <= value < 2 ** 63):
            return False
    if (type(check["checked_requests"]) is not int or type(check["blocked_requests"]) is not int
            or not 0 <= check["blocked_requests"] <= check["checked_requests"]):
        return False
    for kind in ("input", "output"):
        accounted, remaining = check[f"accounted_{kind}_tokens"], check[f"remaining_{kind}_tokens"]
        if check["usage_known"]:
            if type(accounted) is not int or type(remaining) is not int:
                return False
            floor = max(accounted, raw[f"{kind}_tokens"] or 0)
            if remaining != max(0, raw[f"{kind}_token_limit"] - floor):
                return False
        elif accounted is not None or remaining is not None:
            return False
    return True


def bounded_provider_observation(raw: Any) -> dict:
    """A closed projection shared by the wire receipt and persisted Step 2 row."""
    invalid = _provider_summary("invalid_observation")
    if type(raw) is not dict or set(raw) != set(invalid) or raw["source"] != PROVIDER_OBSERVATION_SOURCE:
        return invalid
    count, model = raw["native_request_count"], raw["served_model"]
    if not (count is None or type(count) is int and 0 <= count < 2 ** 63):
        return invalid
    if not (model is None or type(model) is str and _MODEL.fullmatch(model)):
        return invalid
    for field, value in (("native_request_count_reason", count), ("served_model_reason", model)):
        reason = raw[field]
        if not (reason is None or type(reason) is str) or reason not in _OBSERVATION_REASONS:
            return invalid
        if (value is None) != (reason is not None):
            return invalid
    if (raw["served_model_version"] is not None or raw["served_model_version_reason"] != "not_observed"
            or raw["provider_receipt_confirmed"] is not False or type(raw["native_cap_enforced"]) is not bool):
        return invalid
    if raw["native_cap_enforced"]:
        try:
            limit = _native_request_limit()
        except PilotWireReceiptRefused:
            return invalid
        blocked = raw["native_request_blocked_count"]
        if (type(raw["native_request_limit"]) is not int or raw["native_request_limit"] != limit
                or raw["native_request_limit_sha256"] != NATIVE_CAPS_SHA256
                or type(blocked) is not int or not 0 <= blocked < 2 ** 63
                or count is not None and count > limit):
            return invalid
        if blocked:
            reason = raw["native_request_cap_reason"]
            if (type(reason) is not str
                    or reason not in {NATIVE_REQUEST_CAP_EXCEEDED, NATIVE_TASK_CAP_EXCEEDED, NATIVE_PILOT_CAP_EXCEEDED}
                    or reason == NATIVE_REQUEST_CAP_EXCEEDED and count != limit
                    or reason != NATIVE_REQUEST_CAP_EXCEEDED
                    and (type(raw["runtime_caps"]) is not dict or raw["runtime_caps"].get("stop_reason") != reason)):
                return invalid
        elif raw["native_request_cap_reason"] is not None:
            return invalid
    elif any(raw[field] is not None for field in (
            "native_request_limit", "native_request_limit_sha256", "native_request_blocked_count",
            "native_request_cap_reason")):
        return invalid
    try:
        if raw["runtime_caps"] is not None and (not raw["native_cap_enforced"]
                or not _checked_runtime_caps(raw["runtime_caps"], count=count)):
            return invalid
    except PilotWireReceiptRefused:
        return invalid
    return json.loads(_bytes(raw))


def _unique_json(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate_key")
        value[key] = item
    return value


class _TokenPrecheckRefused(Exception):
    def __init__(self, reason):
        self.reason = reason


def _finite_json(_value):
    raise ValueError("non_finite_json")


def _text_input(value):
    """Only locally visible text. Remote/opaque multimodal context is unknown."""
    if type(value) is str:
        return True
    if type(value) is not list:
        return False
    for item in value:
        if type(item) is not dict:
            return False
        if any(item.get(key) is not None for key in
               ("encrypted_content", "image_url", "file_id", "file_data", "file_url", "audio")):
            return False
        kind = item.get("type")
        if kind in (None, "message"):
            content = item.get("content")
            if type(content) is str:
                continue
            if (type(content) is not list or any(type(part) is not dict
                    or part.get("type") not in {"input_text", "output_text"}
                    or type(part.get("text")) is not str for part in content)):
                return False
        elif kind in ("function_call", "custom_tool_call"):
            if type(item.get("arguments" if kind == "function_call" else "input")) is not str:
                return False
        elif kind in ("function_call_output", "custom_tool_call_output"):
            if type(item.get("output")) is not str:
                return False
        else:
            return False
    return True


class _ResponseModel:
    """Bounded, in-memory JSON/SSE inspection; never interpret rollout settings."""

    def __init__(self, content_type: str, encoding: str, status: int):
        self.sse = content_type.split(";", 1)[0].strip().lower() == "text/event-stream"
        self.buffer = bytearray()
        self.model = None
        self.terminal = False
        self.completed_usage = None
        self.usage_terminals = 0
        self.reason = ("provider_response_error" if not 200 <= status < 300 else
                       "encoded_response" if encoding.lower() not in ("", "identity") else None)

    def _document(self, data: bytes):
        if self.usage_terminals:
            # Any further data event makes completion/accounting ambiguous.
            self.completed_usage = None
        try:
            document = json.loads(data, object_pairs_hook=_unique_json)
            if self.sse:
                if type(document) is not dict:
                    raise ValueError("shape")
                kind = document.get("type")
                if kind not in {"response.created", "response.completed", "response.failed", "response.incomplete"}:
                    return
                self.terminal |= kind != "response.created"
                document = document.get("response")
            else:
                kind = "response.completed"
                self.terminal = True
            if type(document) is not dict or document.get("object") != "response":
                raise ValueError("shape")
            if kind != "response.created":
                self.usage_terminals += 1
                self.completed_usage = None
                usage = document.get("usage")
                if (self.usage_terminals == 1 and kind == "response.completed"
                        and document.get("status") == "completed" and type(usage) is dict
                        and all(type(usage.get(field)) is int and 0 <= usage[field] < 2 ** 63
                                for field in ("input_tokens", "output_tokens", "total_tokens"))
                        and usage["total_tokens"] == usage["input_tokens"] + usage["output_tokens"]):
                    self.completed_usage = (usage["input_tokens"], usage["output_tokens"])
            model = document.get("model")
            if model is None:
                if self.terminal:
                    self.reason = "response_model_not_returned"
            elif type(model) is not str or not _MODEL.fullmatch(model):
                self.reason = "response_model_not_allowlisted"
            elif self.model is not None and self.model != model:
                self.reason = "response_models_differ"
            else:
                self.model = model
        except (ValueError, TypeError, UnicodeError, RecursionError):
            self.reason = "malformed_response"

    def feed(self, data: bytes):
        if self.reason is not None:
            return
        self.buffer.extend(data)
        if self.sse:
            # SSE permits LF and CRLF, and data split across arbitrary TCP reads.
            while True:
                match = re.search(b"\r?\n\r?\n", self.buffer)
                if match is None:
                    break
                event = bytes(self.buffer[:match.start()])
                del self.buffer[:match.end()]
                if len(event) > _CAPTURE_BYTES:
                    self.reason = "response_capture_limit"
                    break
                lines = [line[5:].lstrip(b" ") for line in event.splitlines() if line.startswith(b"data:")]
                payload = b"\n".join(lines)
                if payload and payload != b"[DONE]":
                    self._document(payload)
                if self.reason is not None:
                    break
        if len(self.buffer) > _CAPTURE_BYTES:
            self.reason = "response_capture_limit"
        if self.reason is not None:
            self.buffer.clear()

    def finish(self) -> tuple[str | None, str | None]:
        if self.reason is None:
            if not self.sse:
                self._document(bytes(self.buffer))
            elif self.buffer.strip() or not self.terminal:
                self.reason = "response_capture_incomplete"
        self.buffer.clear()
        reason = self.reason or (None if self.model is not None else "response_model_not_returned")
        return (self.model if reason is None else None), reason


class _ProviderHTTPObservation:
    """A fixed-upstream, no-retry HTTP observer owned by one CLI process.

    Counts include failed forward attempts and remote compaction, not logical
    turns or confirmed arrivals/bills. No headers, paths, request/response bodies
    or raw exceptions leave this object. HTTPS credentials pass only to the
    already-checked account; there is no auth discovery or redirect following.
    """

    def __init__(self, base_url: str, timeout: float):
        target = urlsplit(base_url)
        _require(target.scheme == "https" and target.hostname is not None
                 and target.port in (None, 443) and target.username is target.password is None
                 and not target.query and not target.fragment and target.path == "/openai/v1"
                 and classify_endpoint(base_url).kind is EndpointKind.DIRECT_V1
                 and type(timeout) in (int, float) and 0 < timeout < float("inf"))
        self.target = target
        self.limits = _native_caps()
        self.request_limit = self.limits["per_attempt"]["native_model_calls"]
        self.timeout = min(timeout, self.limits["per_attempt"]["wall_clock_seconds"])
        self.deadline = time.monotonic() + self.timeout
        self.lock = threading.RLock()
        self.request_lock = threading.Lock()
        self.close_lock = threading.Lock()
        self.closed = False
        self.requests = self.finished = 0
        self.blocked_requests = 0
        self.cap_exceeded = False
        self.stop_reason = None
        self.wakeup = threading.Event()
        self.budget = self.budget_task = self.closed_budget = None
        self.input_tokens = self.output_tokens = None
        self.precheck_inputs = self.precheck_outputs = 0
        self.precheck_usage_known = True
        self.precheck_checked = self.precheck_blocked = 0
        self.precheck_last_input = self.precheck_last_output = None
        self.stop_runtime = None
        self.model = self.model_reason = self.count_reason = None
        self.connections = set()
        self.inbound = set()
        self.route = "/" + uuid.uuid4().hex
        owner = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *_args):
                pass

            def do_POST(self):
                owner.forward(self)

            def send_error(self, *_args, **_kwargs):
                owner.unsupported(self)

            def finish(self):
                try:
                    super().finish()
                finally:
                    with owner.lock:
                        owner.inbound.discard(self.connection)

        class Server(ThreadingHTTPServer):
            daemon_threads = True
            block_on_close = False

            def get_request(self):
                connection, address = super().get_request()
                try:
                    with owner.lock:
                        connection.settimeout(owner.remaining())
                        owner.inbound.add(connection)
                except Exception:
                    connection.close()
                    raise OSError("observer_unavailable") from None
                return connection, address

            def handle_error(self, *_args):
                # socketserver's default prints raw request exceptions.
                with owner.lock:
                    if not owner.closed:
                        owner.count_reason = "unsupported_native_route"

        self.server = Server(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       kwargs={"poll_interval": 0.05}, daemon=True)
        self.timer = threading.Timer(self.timeout, self.check_deadline)
        self.timer.daemon = True
        try:
            self.thread.start()
            self.timer.start()
        except BaseException:
            if self.thread.is_alive():
                self.close()
            else:
                self.server.server_close()
            raise

    @property
    def base_url(self):
        return f"http://127.0.0.1:{self.server.server_port}{self.route}"

    def remaining(self):
        if self.closed:
            raise RuntimeError("observer_closed")
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            self.request_stop(NATIVE_DEADLINE_EXCEEDED)
            raise TimeoutError("deadline_exceeded")
        return remaining

    def bind_budget(self, budget, task_id):
        with self.lock:
            _require(type(budget) is _NativeRequestBudget and budget.limits == self.limits
                     and task_id in budget.counts and self.budget is None
                     and not self.closed and self.requests == 0)
            self.budget, self.budget_task = budget, task_id

    def check_deadline(self):
        with self.lock:
            if self.closed:
                return
            remaining = self.deadline - time.monotonic()
            if remaining > 0:
                self.timer = threading.Timer(remaining, self.check_deadline)
                self.timer.daemon = True
                self.timer.start()
                return
        self.request_stop(NATIVE_DEADLINE_EXCEEDED)

    def request_stop(self, reason, *, defer_cleanup=False):
        """Latch a closed reason before cleanup, including from the SDK reader.

        SDK.close joins its reader. Never call it while that reader holds the
        transport/usage lock; the owned cleanup worker and runner serialize it.
        """
        _require(reason in _CAP_STOPS)
        with self.lock:
            if self.closed or self.stop_reason is not None:
                return
            self.stop_reason = reason
            if not defer_cleanup:
                self.wakeup.set()
        if not defer_cleanup:
            threading.Thread(target=self._close_stopped_runtime, daemon=True).start()

    def _close_stopped_runtime(self):
        self.wakeup.set()
        self.close()
        if self.stop_runtime is not None:
            self.stop_runtime()

    def report_usage(self, total):
        """Stop on observed totals, without claiming a pre-request token cap.

        Usage arrives after provider work. Cached/reasoning subcounts are not
        added again; unknown usage is never silently converted to zero.
        """
        with self.lock:
            limits = self.limits["per_attempt"]
            if self.closed:
                # A late reader must not bypass the old threshold check or
                # upgrade an immutable closed summary into a successful overage.
                _require(total["inputTokens"] <= limits["input_tokens"]
                         and total["outputTokens"] <= limits["output_tokens"])
                return
            if self.stop_reason is not None:
                return
            self.input_tokens, self.output_tokens = total["inputTokens"], total["outputTokens"]
            reason = (NATIVE_INPUT_CAP_EXCEEDED if self.input_tokens > limits["input_tokens"] else
                      NATIVE_OUTPUT_CAP_EXCEEDED if self.output_tokens > limits["output_tokens"] else None)
            if reason is not None:
                self.request_stop(reason)

    def _remaining_tokens(self):
        if not self.precheck_usage_known:
            return None, None
        limits = self.limits["per_attempt"]
        return (max(0, limits["input_tokens"] - max(self.precheck_inputs, self.input_tokens or 0)),
                max(0, limits["output_tokens"] - max(self.precheck_outputs, self.output_tokens or 0)))

    def _token_request(self, body, suffix):
        """Called under the attempt lock immediately before upstream admission.

        A byte-based TEXT estimate is not a Sol tokenizer or a server guarantee.
        Account complete provider responses once; an SDK cumulative total is a
        conservative floor, never added a second time and never a reset.
        """
        self.precheck_last_input = self.precheck_last_output = None
        remaining_input, remaining_output = self._remaining_tokens()
        if remaining_input is None:
            raise _TokenPrecheckRefused(NATIVE_USAGE_UNVERIFIED)
        if suffix != "/responses":  # No verified output-limit field for compact.
            raise _TokenPrecheckRefused(NATIVE_OUTPUT_LIMIT_UNAVAILABLE)
        try:
            document = json.loads(body.decode("utf-8"), object_pairs_hook=_unique_json,
                                  parse_constant=_finite_json)
            if (type(document) is not dict or not _text_input(document.get("input"))
                    or any(document.get(key) is not None for key in
                           ("previous_response_id", "conversation", "prompt", "context_management"))
                    or document.get("background", False) is not False
                    or type(document.get("stream", False)) is not bool
                    or document.get("instructions") is not None and type(document["instructions"]) is not str
                    or type(document.get("tools", [])) is not list
                    or any(type(tool) is not dict or tool.get("type") not in {"function", "custom"}
                           for tool in document.get("tools", []))):
                raise ValueError("unbounded_input")
        except (ValueError, TypeError, UnicodeError, RecursionError):
            raise _TokenPrecheckRefused(NATIVE_TOKEN_REQUEST_UNVERIFIED) from None
        if any(key in document for key in ("max_tokens", "max_completion_tokens", "model_max_output_tokens",
                                           "maxOutputTokens")):
            raise _TokenPrecheckRefused(NATIVE_OUTPUT_LIMIT_UNAVAILABLE)
        if remaining_output == 0:
            raise _TokenPrecheckRefused(NATIVE_OUTPUT_PRECHECK_EXCEEDED)
        insert_maximum = "max_output_tokens" not in document
        if insert_maximum:
            document["max_output_tokens"] = remaining_output
        try:
            encoded = json.dumps(document, ensure_ascii=False, allow_nan=False,
                                 separators=(",", ":")).encode("utf-8")
        except (ValueError, UnicodeError, RecursionError):
            raise _TokenPrecheckRefused(NATIVE_TOKEN_REQUEST_UNVERIFIED) from None
        if insert_maximum:
            body = encoded
        maximum = document["max_output_tokens"]
        if type(maximum) is not int or not 0 < maximum < 2 ** 63:
            raise _TokenPrecheckRefused(NATIVE_OUTPUT_LIMIT_UNAVAILABLE)
        self.precheck_last_input, self.precheck_last_output = len(body), maximum
        if len(body) > remaining_input:
            raise _TokenPrecheckRefused(NATIVE_INPUT_PRECHECK_EXCEEDED)
        if maximum > remaining_output:
            raise _TokenPrecheckRefused(NATIVE_OUTPUT_PRECHECK_EXCEEDED)
        return body

    @staticmethod
    def _empty(handler, status=502):
        handler.close_connection = True
        try:
            handler.send_response_only(status)
            handler.send_header("Content-Length", "0")
            handler.send_header("Connection", "close")
            handler.end_headers()
        except Exception:
            pass

    def unsupported(self, handler):
        with self.lock:
            if not self.closed:
                self.count_reason = "unsupported_native_route"
        self._empty(handler, 400)

    def forward(self, handler):
        suffix = handler.path.removeprefix(self.route)
        lengths = handler.headers.get_all("Content-Length", [])
        if (handler.path != self.route + suffix or suffix not in ("/responses", "/responses/compact")
                or len(lengths) != 1 or not re.fullmatch(r"[0-9]{1,19}", lengths[0])
                or handler.headers.get("Transfer-Encoding") or handler.headers.get("Upgrade")):
            self.unsupported(handler)
            return
        connection = upstream = None
        started = False
        serialized = False
        response_started = False
        reason, model = "transport_failed", None
        try:
            while not self.request_lock.acquire(timeout=min(0.05, self.remaining())):
                if self.stop_reason is not None:
                    raise RuntimeError("stopped")
            serialized = True
            with self.lock:
                if self.closed or self.stop_reason is not None:
                    raise RuntimeError("closed")
                self.remaining()
                # Reserve under the same lock, before constructing/connecting
                # upstream. Concurrent requests cannot both take the last slot.
                if self.requests >= self.request_limit:
                    self.blocked_requests += 1
                    self.cap_exceeded = True
                    self.request_stop(NATIVE_REQUEST_CAP_EXCEEDED, defer_cleanup=True)
            if self.stop_reason is not None:
                self._empty(handler, 400)
                self._close_stopped_runtime()
                return
            with self.lock:
                self.precheck_checked += 1
            content_types = handler.headers.get_all("Content-Type", [])
            encodings = handler.headers.get_all("Content-Encoding", [])
            if (len(content_types) != 1 or content_types[0].lower().replace(" ", "") not in
                    {"application/json", "application/json;charset=utf-8"}
                    or len(encodings) > 1 or encodings and encodings[0].lower() != "identity"
                    or int(lengths[0]) > _REQUEST_CAPTURE_BYTES):
                raise _TokenPrecheckRefused(NATIVE_TOKEN_REQUEST_UNVERIFIED)
            body = bytearray()
            left = int(lengths[0])
            while left:
                handler.connection.settimeout(self.remaining())
                data = handler.rfile.read(min(left, _CHUNK_BYTES))
                if not data:
                    raise _TokenPrecheckRefused(NATIVE_TOKEN_REQUEST_UNVERIFIED)
                body.extend(data)
                left -= len(data)
            with self.lock:
                self.remaining()
                if self.stop_reason is not None:
                    raise RuntimeError("stopped")
                body = self._token_request(bytes(body), suffix)
                if not self.closed:
                    reason = self.budget.reserve(self.budget_task) if self.budget is not None else None
                    if reason is not None:
                        self.blocked_requests += 1
                        self.request_stop(reason, defer_cleanup=True)
                    else:
                        # A failed connection is still a spent forward reservation.
                        self.requests += 1
                        started = True
                        connection = HTTPSConnection(self.target.hostname, timeout=self.remaining())
                        self.connections.add((connection, handler.connection))
            if not started:
                self._empty(handler, 400)  # Not 429: this is not provider throttling.
                self._close_stopped_runtime()
                return
            connection.connect()
            upstream = connection.sock
            with self.lock:
                self.remaining()
                self.connections.discard((connection, handler.connection))
                self.connections.add((connection, handler.connection, upstream))
            connection.putrequest("POST", self.target.path + suffix, skip_accept_encoding=True)
            excluded = _HOP_HEADERS | {"content-length", "content-type"}
            excluded |= {item.strip().lower() for item in handler.headers.get("Connection", "").split(",")}
            for name, value in handler.headers.items():
                if name.lower() not in excluded:
                    connection.putheader(name, value)
            connection.putheader("Content-Type", "application/json")
            connection.putheader("Content-Length", str(len(body)))
            connection.endheaders()
            for offset in range(0, len(body), _CHUNK_BYTES):
                upstream.settimeout(self.remaining())
                connection.send(body[offset:offset + _CHUNK_BYTES])
            upstream.settimeout(self.remaining())
            response = connection.getresponse()
            if 300 <= response.status < 400:
                reason = "redirect_refused"
                self._response_finished(None, reason)
                started = False
                self._empty(handler)
                return
            parser = _ResponseModel(response.getheader("Content-Type", ""),
                                    response.getheader("Content-Encoding", ""), response.status)
            handler.send_response_only(response.status)
            excluded = _HOP_HEADERS | {"content-length"}
            excluded |= {item.strip().lower() for item in response.getheader("Connection", "").split(",")}
            for name, value in response.getheaders():
                if name.lower() not in excluded:
                    handler.send_header(name, value)
            handler.send_header("Transfer-Encoding", "chunked")
            handler.send_header("Connection", "close")
            handler.end_headers()
            response_started = True
            handler.close_connection = True
            while True:
                handler.connection.settimeout(self.remaining())
                upstream.settimeout(self.remaining())
                data = response.read1(_CHUNK_BYTES)
                self.remaining()
                if not data:
                    if response.length not in (None, 0):
                        raise ValueError("incomplete_response")
                    break
                parser.feed(data)
                handler.wfile.write(f"{len(data):x}\r\n".encode() + data + b"\r\n")
            model, reason = parser.finish()
            # Publish the observation before EOF lets the CLI complete its turn.
            self._response_finished(model, reason, usage=parser.completed_usage)
            started = False
            handler.wfile.write(b"0\r\n\r\n")
        except _TokenPrecheckRefused as error:
            with self.lock:
                self.precheck_blocked += 1
                self.request_stop(error.reason, defer_cleanup=True)
            self._empty(handler, 400)
            self._close_stopped_runtime()
        except Exception as error:
            reason = "deadline_exceeded" if isinstance(error, TimeoutError) else "transport_failed"
            before_upstream = not started and connection is None
            if started:
                self._response_finished(None, reason)
                started = False
            if response_started:
                handler.close_connection = True
            else:
                self._empty(handler)
            if before_upstream and self.stop_reason is None:
                self.request_stop(NATIVE_DEADLINE_EXCEEDED if isinstance(error, TimeoutError)
                                  else NATIVE_TOKEN_REQUEST_UNVERIFIED, defer_cleanup=True)
                self._close_stopped_runtime()
        finally:
            try:
                if started:
                    self._response_finished(None, reason)
                if connection is not None:
                    connection.close()
                    with self.lock:
                        self.connections.discard((connection, handler.connection))
                        self.connections.discard((connection, handler.connection, upstream))
            finally:
                if serialized:
                    self.request_lock.release()

    def _response_finished(self, model, reason, *, usage=None):
        with self.lock:
            if self.closed:
                return  # A late worker cannot upgrade an already-closed report.
            self.finished += 1
            if self.precheck_usage_known and reason is None and usage is not None:
                inputs, outputs = self.precheck_inputs + usage[0], self.precheck_outputs + usage[1]
                if inputs < 2 ** 63 and outputs < 2 ** 63:
                    self.precheck_inputs, self.precheck_outputs = inputs, outputs
                else:
                    self.precheck_usage_known = False
            else:
                self.precheck_usage_known = False
            if not self.precheck_usage_known:
                self.precheck_inputs = self.precheck_outputs = None
            if reason is not None:
                self.model_reason = reason
            elif self.model is not None and self.model != model:
                self.model_reason = "response_models_differ"
            else:
                self.model = model

    def close(self):
        with self.close_lock:
            with self.lock:
                if self.closed:
                    return
                self.closed = True
                if self.requests != self.finished:
                    self.precheck_usage_known = False
                    self.precheck_inputs = self.precheck_outputs = None
                self.timer.cancel()
                self.closed_budget = self.budget.snapshot(self.budget_task) if self.budget is not None else None
                connections = tuple(self.connections)
                inbound = tuple(self.inbound)
            for stream in inbound:
                try:
                    stream.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                stream.close()
            for connection, inbound, *upstream in connections:
                for stream in (connection.sock, inbound, *upstream):
                    if stream is not None:
                        try:
                            stream.shutdown(socket.SHUT_RDWR)
                        except OSError:
                            pass
                connection.close()
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(timeout=1)
        if self.timer.ident is not None and self.timer is not threading.current_thread():
            self.timer.join(timeout=1)

    def _runtime_caps(self):
        attempt = self.limits["per_attempt"]
        remaining_input, remaining_output = self._remaining_tokens()
        return {"sha256": NATIVE_CAPS_SHA256,
                "input_token_limit": attempt["input_tokens"], "output_token_limit": attempt["output_tokens"],
                "input_tokens": self.input_tokens, "output_tokens": self.output_tokens,
                "token_boundary": _TOKEN_BOUNDARY, "token_hard_limit_enforced": False,
                "client_token_precheck": {
                    "enabled": True, "input_estimator": _INPUT_ESTIMATOR,
                    "server_hard_limit_verified": False, "checked_requests": self.precheck_checked,
                    "blocked_requests": self.precheck_blocked, "usage_known": self.precheck_usage_known,
                    "accounted_input_tokens": self.precheck_inputs,
                    "accounted_output_tokens": self.precheck_outputs,
                    "remaining_input_tokens": remaining_input, "remaining_output_tokens": remaining_output,
                    "last_input_estimate": self.precheck_last_input, "last_output_limit": self.precheck_last_output},
                "wall_seconds_limit": attempt["wall_clock_seconds"], "effective_wall_seconds": self.timeout,
                "task_request_limit": self.limits["per_task"]["native_model_calls"],
                "pilot_request_limit": self.limits["per_pilot"]["native_model_calls"],
                **(self.closed_budget or {"task_requests": None, "pilot_requests": None}),
                "stop_reason": self.stop_reason}

    def summary(self):
        with self.lock:
            if not self.closed:
                return _provider_summary("observer_not_closed")
            result = _provider_summary()
            result.update(native_cap_enforced=True, native_request_limit=self.request_limit,
                          native_request_limit_sha256=NATIVE_CAPS_SHA256,
                          native_request_blocked_count=self.blocked_requests,
                          native_request_cap_reason=self.stop_reason if self.blocked_requests else None,
                          runtime_caps=self._runtime_caps())
            result["native_request_count"] = self.requests if self.count_reason is None or self.cap_exceeded else None
            result["native_request_count_reason"] = None if self.cap_exceeded else self.count_reason
            reason = self.count_reason or ("deadline_exceeded" if self.stop_reason == NATIVE_DEADLINE_EXCEEDED else
                      "response_capture_incomplete" if self.finished != self.requests else
                      "no_provider_requests" if not self.requests else self.model_reason)
            result["served_model"] = self.model if reason is None else None
            result["served_model_reason"] = reason or ("response_model_not_returned" if self.model is None else None)
            return bounded_provider_observation(result)


class PilotWireReceiptRefused(ValueError):
    def __init__(self) -> None:
        super().__init__(REFUSAL)


def _require(value: bool) -> None:
    if not value:
        raise PilotWireReceiptRefused()


@contextmanager
def _closed():
    try:
        yield
    except Exception:
        raise PilotWireReceiptRefused() from None


def _correlation(value: Any) -> str:
    _require(type(value) is str and 0 < len(value) <= 256)
    return _digest(value.encode("utf-8"))["sha256"]


def _unavailable() -> dict:
    return {"state": "not_available", "reason": "not_exposed_by_pinned_codex_route"}


class _TransportObservation:
    """One fresh task attempt. Private inputs never enter the receipt shape."""

    def __init__(self, requested: dict) -> None:
        self.requested = requested
        self.lock = threading.RLock()
        self.invalid = False
        self.installed = False
        self.sealed = False
        self.task_text = None
        self.runtime = None
        self.requests: dict[str, dict] = {}
        self.responses: set[str] = set()
        self.thread = None
        self.turn = None
        self.settings = None
        self.usage: list[dict] = []
        self.completion = None
        self.caps_usage_observer = None
        self.approved_base_url = None
        self.provider_capture = None
        self.provider_capture_reason = "observer_not_installed"
        self.provider_runtime = None
        self.provider_runtime_close_returned = False
        self.provider_runtime_lock = threading.Lock()
        self.native_budget = self.native_budget_task = None
        self.startup_attempted = self.startup_timed_out = False
        self.startup_process = None

    def require_startup_supervision(self):
        """Do not start an SDK we cannot interrupt, or borrow another alarm."""
        with self.guard():
            _require(not self.startup_attempted and not self.installed
                     and threading.current_thread() is threading.main_thread()
                     and hasattr(signal, "setitimer")
                     and signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0))

    @contextmanager
    def supervise_provider_startup(self, codex=None):
        """Interrupt the synchronous SDK constructor on the SAME deadline.

        Codex 0.147.0 catches Exception during start/initialize and closes its
        client. A main-thread TimeoutError reaches that cleanup; timing out a
        worker future would leave its constructor running. No SDK globals or
        background constructor are installed. The existing listener watchdog
        continues after this short-lived alarm is restored.
        """
        self.require_startup_supervision()
        with self.guard():
            _require(self.provider_capture is not None and self.provider_runtime is None)
            self.startup_attempted = True
        capture = self.provider_capture

        def expired(_signum=None, _frame=None):
            remaining = capture.deadline - time.monotonic()
            if remaining > 0 and capture.stop_reason != NATIVE_DEADLINE_EXCEEDED:
                signal.setitimer(signal.ITIMER_REAL, remaining)
                return
            self.startup_timed_out = True
            # Keep the actual partial constructor's process before SDK.close
            # clears _proc. Its SIGKILL fallback does not wait/reap the child.
            self.startup_process = getattr(getattr(codex, "_client", None), "_proc", None)
            capture.request_stop(NATIVE_DEADLINE_EXCEEDED)
            # An Exception, deliberately: the pinned SDK's constructor owns
            # its partially initialized client and closes it before rethrowing.
            raise TimeoutError(NATIVE_DEADLINE_EXCEEDED)

        previous = signal.signal(signal.SIGALRM, expired)
        try:
            expired()  # Arm remaining time, or refuse an already-expired attempt.
            yield
            if capture.deadline <= time.monotonic() or capture.stop_reason == NATIVE_DEADLINE_EXCEEDED:
                expired()  # A raced constructor return cannot become success.
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0.0)
            signal.signal(signal.SIGALRM, previous)

    def close_startup_process(self):
        process = self.startup_process
        if process is not None:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=1)  # Cleanup only; never renew the attempt deadline.

    def require_startup_timeout(self):
        """Only a local pre-thread timeout can have an empty wire receipt."""
        _require(self.startup_attempted and self.startup_timed_out and not self.installed
                 and self.cap_stop_reason == NATIVE_DEADLINE_EXCEEDED
                 and self.provider_capture.closed and self.provider_capture.requests == 0
                 and self.provider_runtime is None and not self.requests and not self.responses
                 and self.thread is self.turn is self.settings is self.completion is None
                 and not self.usage
                 and (self.startup_process is None or self.startup_process.poll() is not None))

    def configure_provider_observer(self, provider, overrides, *, timeout):
        """Replace only this process's checked provider URL; never mutate settings."""
        from core.codex_runtime_config import _toml_literal

        with self.guard():
            _require(self.provider_capture is None and not self.installed
                     and self.approved_base_url == provider.base_url
                     and provider.provider_id == self.requested["provider_id"])
            key = f"model_providers.{provider.provider_id}.base_url="
            expected = key + _toml_literal(provider.base_url)
            _require([item for item in overrides if item.startswith(key)] == [expected])
            try:
                self.provider_capture = _ProviderHTTPObservation(provider.base_url, timeout)
            except OSError:
                # A missing listener must not bypass the request-cap boundary.
                self.provider_capture_reason = "observer_start_failed"
                raise PilotWireReceiptRefused() from None
            if self.native_budget is not None:
                self.provider_capture.bind_budget(self.native_budget, self.native_budget_task)
            return tuple(key + _toml_literal(self.provider_capture.base_url) if item == expected else item
                         for item in overrides)

    def close_provider_observer(self):
        if self.provider_capture is not None:
            self.provider_capture.close()

    def bind_provider_runtime(self, codex):
        with self.guard():
            _require(self.installed and self.provider_capture is not None and self.provider_runtime is None)
            if self.caps_usage_observer is not None:
                with self.caps_usage_observer._guard():
                    limits = self.provider_capture.limits["per_attempt"]
                    _require(self.caps_usage_observer.limits == {
                        "model_calls": limits["native_model_calls"], "input_tokens": limits["input_tokens"],
                        "output_tokens": limits["output_tokens"]})
            with self.provider_capture.lock:
                _require(not self.provider_capture.closed and self.provider_capture.requests == 0)
                self.provider_runtime = codex
                self.provider_capture.stop_runtime = self.close_provider_runtime

    def close_provider_runtime(self):
        # Both the denied HTTP worker and the runner's finally use this owner.
        # The second caller waits for closure instead of racing SDK.close().
        with self.provider_runtime_lock:
            if self.provider_runtime is not None:
                try:
                    self.provider_runtime.close()
                    self.provider_runtime_close_returned = True
                finally:
                    self.provider_runtime = None

    def require_pending_start_stop(self):
        """A closed local stop may retain missing RPC acknowledgements, never success.

        Only the two actually flushed start shapes are eligible. Other missing,
        mismatched or poisoned observations still fail the existing guards.
        """
        _require(self.installed and not self.startup_timed_out
                 and self.cap_stop_reason in _CAP_STOPS and self.provider_capture.closed
                 and self.provider_runtime is None and self.provider_runtime_close_returned
                 and self.turn is self.completion is None and not self.usage)
        if self.thread is None:
            _require(set(self.requests) == {"thread/start"} and not self.responses
                     and self.settings is None)
        else:
            _require(set(self.requests) == {"thread/start", "turn/start"}
                     and self.responses == {self.requests["thread/start"]["request_id_sha256"]}
                     and self.settings is not None)

    @property
    def native_request_cap_exceeded(self):
        return self.provider_capture is not None and self.provider_capture.cap_exceeded

    @property
    def cap_stop_reason(self):
        return self.provider_capture.stop_reason if self.provider_capture is not None else None

    def terminal_correlation(self):
        if self.completion is not None:
            return self.completion
        _require(self.cap_stop_reason is not None)
        # A local stop is not a fabricated app-server terminal acknowledgement.
        return {"thread_id_sha256": self.thread, "turn_id_sha256": self.turn, "status": None}

    def provider_observation(self):
        return (self.provider_capture.summary() if self.provider_capture is not None else
                _provider_summary(self.provider_capture_reason))

    @contextmanager
    def guard(self):
        with self.lock, _closed():
            try:
                _require(not self.invalid and not self.sealed)
                yield
            except Exception:
                self.invalid = True
                raise PilotWireReceiptRefused() from None

    def bind_task_text(self, text: str) -> None:
        with self.guard():
            _require(self.task_text is None and type(text) is str and bool(text))
            self.task_text = text

    def bind_runtime(self, *, workspace: Path, developer_instructions: str | None) -> None:
        with self.guard():
            _require(self.runtime is None and self.task_text is not None)
            self.runtime = {"cwd": str(workspace), "developerInstructions": developer_instructions}

    def request(self, data: str) -> tuple[str, dict]:
        """Validate the actual serialized line, not a second serialization."""
        _require(type(data) is str and data.endswith("\n") and self.runtime is not None)
        message = json.loads(data)
        _require(type(message) is dict and set(message) == {"id", "method", "params"})
        method, params = message["method"], message["params"]
        _require(method in ("thread/start", "turn/start", "turn/interrupt") and method not in self.requests)
        rpc_id = _correlation(message["id"])
        _require(rpc_id not in {entry["request_id_sha256"] for entry in self.requests.values()})
        if method == "thread/start":
            expected = {"model": self.requested["deployment"], "modelProvider": self.requested["provider_id"],
                        "cwd": self.runtime["cwd"], "sandbox": "workspace-write", "approvalPolicy": "never"}
            if self.runtime["developerInstructions"] is not None:
                expected["developerInstructions"] = self.runtime["developerInstructions"]
            _require(params == expected and not self.requests)
        elif method == "turn/start":
            _require(self.thread is not None and type(params) is dict and set(params) == {"threadId", "input"})
            _require(_correlation(params["threadId"]) == self.thread
                     and params["input"] == [{"type": "text", "text": self.task_text}])
        else:
            _require(self.turn is not None and type(params) is dict and set(params) == {"threadId", "turnId"})
            _require(_correlation(params["threadId"]) == self.thread and _correlation(params["turnId"]) == self.turn)
        return method, {"request_id_sha256": rpc_id, "serialized_utf8": _digest(data.encode("utf-8"))}

    def response(self, message: dict) -> None:
        with self.guard():
            rpc_id = _correlation(message.get("id"))
            methods = [method for method, request in self.requests.items() if request["request_id_sha256"] == rpc_id]
            _require(len(methods) == 1 and rpc_id not in self.responses and "error" not in message)
            self.responses.add(rpc_id)
            result, method = message["result"], methods[0]
            if method == "thread/start":
                _require(result["model"] == self.requested["deployment"]
                         and result["modelProvider"] == self.requested["provider_id"]
                         and result.get("reasoningEffort") in (None, self.requested["reasoning_effort"]))
                self.thread = _correlation(result["thread"]["id"])
                self.settings = {"source": "app_server_thread_settings_not_served_identity",
                                 "model": result["model"], "provider_id": result["modelProvider"],
                                 "reasoning_effort": result.get("reasoningEffort")}
            elif method == "turn/start":
                self.turn = _correlation(result["turn"]["id"])

    def notification(self, method: str, params: Any) -> None:
        if method not in ("model/rerouted", "thread/tokenUsage/updated", "turn/completed"):
            return  # Never retain free-form output, error messages or tool events.
        with self.guard():
            _require(method != "model/rerouted" and type(params) is dict)
            thread = _correlation(params["threadId"])
            if method == "turn/completed":
                _require(self.completion is None)
                status = params["turn"]["status"]
                _require(status in ("completed", "failed", "interrupted"))
                self.completion = {"thread_id_sha256": thread, "turn_id_sha256": _correlation(params["turn"]["id"]),
                                   "status": status}
                if self.caps_usage_observer is not None and not self.usage and self.provider_capture is not None:
                    self.provider_capture.request_stop(NATIVE_USAGE_UNVERIFIED)
            else:
                usage = params["tokenUsage"]
                _require(type(usage) is dict and set(usage) <= {"total", "last", "modelContextWindow"})
                for role in ("total", "last"):
                    if role in usage:
                        _require(type(usage[role]) is dict and set(usage[role]) <= _USAGE_FIELDS)
                        _require(all(value is None or type(value) is int and value >= 0 for value in usage[role].values()))
                if "modelContextWindow" in usage:
                    value = usage["modelContextWindow"]
                    _require(value is None or type(value) is int and value > 0)
                snapshot = {"thread_id_sha256": thread, "turn_id_sha256": _correlation(params["turnId"]),
                            "native": json.loads(_bytes(usage))}
                if self.caps_usage_observer is not None:
                    self.caps_usage_observer.observe(snapshot)
                self.usage.append(snapshot)

    def finish(self, *, success: bool, thread_id: str | None, turn_id: str | None) -> dict:
        with self.guard():
            stopped = self.cap_stop_reason is not None
            pending_start = stopped and not self.startup_timed_out and self.turn is None
            _require(type(success) is bool)
            if self.startup_timed_out:
                self.require_startup_timeout()
                _require(not success and thread_id is turn_id is None)
            elif pending_start:
                self.require_pending_start_stop()
                _require(not success and turn_id is None
                         and self.thread == (None if thread_id is None else _correlation(thread_id)))
            else:
                _require(self.installed and (self.completion is not None or stopped))
                _require(self.thread == _correlation(thread_id) and self.turn == _correlation(turn_id)
                         and {"thread/start", "turn/start"} <= set(self.requests)
                         and self.responses == {entry["request_id_sha256"] for entry in self.requests.values()})
            _require(all(row["thread_id_sha256"] == self.thread and row["turn_id_sha256"] == self.turn
                         for row in [self.terminal_correlation(), *self.usage]))
            _require(not success if stopped else success == (self.completion["status"] == "completed"))
            if self.caps_usage_observer is not None:
                self.caps_usage_observer.finish(self)
            result = {"scope": ("codex_app_server_startup_deadline_before_thread" if self.startup_timed_out else
                                "codex_app_server_local_stop_before_turn_ack" if pending_start else
                                "codex_app_server_stdio_utf8_after_initialize"),
                      "requests": self.requests, "correlation": self.terminal_correlation(),
                      "app_server_settings": self.settings,
                      "usage": {"state": "observed" if self.usage else "not_available", "unit": "tokens",
                                "source": "app_server_thread_usage_not_provider_billing",
                                "snapshots": self.usage, "model_call_count": _unavailable(), "pricing": _unavailable()},
                      "foundry_http_payload": _unavailable(), "foundry_request_id": _unavailable(),
                      "served_model": _unavailable(), "served_model_version": _unavailable(),
                      "served_deployment": _unavailable()}
            result["provider_observation"] = self.provider_observation()
            if self.provider_capture is not None:
                observed = result["provider_observation"]
                result["served_model"] = {
                    "state": "observed" if observed["served_model"] is not None else "not_available",
                    "value": observed["served_model"], "reason": observed["served_model_reason"],
                    "source": "provider_response_body_model_not_deployment_or_version_attestation",
                }
            self.sealed = True
            self.task_text = self.runtime = None
            return json.loads(_bytes(result))


class _ObservedPipe:
    def __init__(self, pipe, observer: _TransportObservation):
        self.pipe, self.observer, self.pending = pipe, observer, None

    def write(self, data):
        with self.observer.guard():
            _require(self.pending is None)
            pending = self.observer.request(data)
            count = self.pipe.write(data)
            _require(type(count) is int and count == len(data))
            self.pending = pending
            return count

    def flush(self):
        with self.observer.guard():
            self.pipe.flush()
            _require(self.pending is not None)
            method, record = self.pending
            self.observer.requests[method] = record
            self.pending = None

    def __getattr__(self, name):
        return getattr(self.pipe, name)


def install_runtime_observer(codex, observer: _TransportObservation) -> None:
    """Instance-local pass-through hooks for openai-codex==0.147.0 only.

    Holding the observation lock across the SDK's write+flush prevents its
    reader from correlating an early response before the write is committed.
    No HTTP interception, second client, auth lookup or SDK defaulted usage.
    """
    with observer.guard():
        _require(not observer.installed)
        client = codex._client
        pipe = client._proc.stdin
        _require(pipe.encoding.lower().replace("-", "") == "utf8" and not isinstance(pipe, _ObservedPipe))
        write, response, notification = client._write_message, client._router.route_response, client._coerce_notification

        def observed_write(payload):
            with observer.guard():
                return write(payload)

        def observed_response(message):
            observer.response(message)
            return response(message)

        def observed_notification(method, params):
            observer.notification(method, params)
            return notification(method, params)

        client._proc.stdin = _ObservedPipe(pipe, observer)
        client._write_message = observed_write
        client._router.route_response = observed_response
        client._coerce_notification = observed_notification
        observer.installed = True


class PilotWireReceiptSession:
    """One run, exclusive files and a non-serializable in-process witness.

    The initial linkage is from Step 2's real capture gate. Publication and
    result acceptance re-run that verifier; no cached verdict waives drift.
    Disk-only receipts cannot be adopted, and there is no offline preflight
    option that can turn a synthetic transcript into live identity evidence.
    """

    def __init__(self, *, sources: capture.PilotCaptureSources, workspace: Path,
                 dataset_root: Path, verified_capture: dict):
        with _closed():
            self.sources, self.workspace, self.dataset_root = sources, capture._workspace(workspace, sources), dataset_root
            self.linkage = json.loads(_bytes(verified_capture))
            self.capture_data = _read_bytes(self.workspace / capture.CAPTURE_PATH,
                                           size=self.linkage["size"], sha256=self.linkage["sha256"])
            self.document = json.loads(self.capture_data)
            self.prepared = json.loads(_read_bytes(self.workspace / capture.PREPARED_PATH,
                                                   sha256=self.linkage["prepared_sha256"]))
            _require(self.linkage["run_id"] == pilot.RUN_ID == self.document["run_id"]
                     and self.document["task_ids"] == [row["task_id"] for row in self.prepared["tasks"]])
            self.root = self.workspace / DIRECTORY
            self.reserved = self.workspace / RESERVATION
            self.lock = threading.RLock()
            self.failed = False
            self.armed: dict[str, int] = {}
            self.active: dict[str, _TransportObservation] = {}
            self.thread_ids: set[str] = set()
            self.files: dict[str, bytes] = {}
            self.attempts: dict[str, list[dict]] = {task_id: [] for task_id in self.document["task_ids"]}
            self.native_budget = _NativeRequestBudget(self.document["task_ids"])
            self.ready: bytes | None = None
            self.reservation = _bytes({"reservation_version": "pilot-wire-reservation-v1", "run_id": pilot.RUN_ID,
                                       "prepared_capture": self.linkage, "launch_allowed": False, "full_220_allowed": False})
            with _held_parents(self.workspace, (DIRECTORY, RESERVATION)) as check:
                _require(not os.path.lexists(self.root) and not os.path.lexists(self.reserved))
                check()
                _write_no_clobber(self.reserved, self.reservation)
                check()
                parent_fd = os.open(self.workspace, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                try:
                    check()
                    os.mkdir(DIRECTORY, mode=0o700, dir_fd=parent_fd)
                finally:
                    os.close(parent_fd)
                check()
            metadata = self.root.stat()
            self.root_identity = (metadata.st_dev, metadata.st_ino)

    @contextmanager
    def _guard(self):
        with self.lock, _closed():
            try:
                _require(not self.failed)
                yield
            except Exception:
                self.failed = True
                raise PilotWireReceiptRefused() from None

    def _current(self) -> None:
        _require(type(self.native_budget) is _NativeRequestBudget and self.native_budget.limits == _native_caps()
                 and set(self.native_budget.counts) == set(self.document["task_ids"]))
        _require(capture.verify_pilot_input_capture(self.sources, workspace=self.workspace,
                                                  dataset_root=self.dataset_root) == self.linkage)
        _read_bytes(self.workspace / capture.CAPTURE_PATH, **_digest(self.capture_data))
        _read_bytes(self.reserved, **_digest(self.reservation))
        root = _root(self.root)
        metadata = root.stat()
        _require((metadata.st_dev, metadata.st_ino) == self.root_identity)
        expected = set(self.files) | ({READY_PATH} if self.ready is not None else set())
        _require({path.name for path in root.iterdir()} == expected)
        for name, data in self.files.items():
            _read_bytes(_path(root, name), **_digest(data))
        if self.ready is not None:
            _read_bytes(root / READY_PATH, **_digest(self.ready))

    def arm_task(self, task_id: str, attempt_index: int) -> None:
        """Use Step 2's actual zero-based infrastructure attempt, before auth."""
        with self._guard():
            _require(self.ready is None and task_id in self.attempts and task_id not in self.armed
                     and task_id not in self.active and type(attempt_index) is int
                     and attempt_index == len(self.attempts[task_id])
                     and 0 <= attempt_index <= self.prepared["execution"]["max_retries"])
            previous = self.attempts[task_id]
            _require(not previous or previous[-1]["accepted"] and not previous[-1]["success"])
            self._current()
            self.native_budget.require_available(task_id)
            if getattr(self, "native_host", None) is not None:
                from gpt56_pilot_runtime_caps_usage import runtime_caps_usage_for

                runtime_caps_usage_for(self).arm_task(task_id, attempt_index)
            self.armed[task_id] = attempt_index

    def begin_task(self, *, task_id, run_id, condition_name, task_prompt, occupation,
                   experiment_prompt, perception_text, reference_files, provider) -> _TransportObservation:
        with self._guard():
            _require(run_id == pilot.RUN_ID and condition_name == "condition_a" and task_id in self.armed
                     and task_id not in self.active and perception_text is None)
            row = next(row for row in self.prepared["tasks"] if row["task_id"] == task_id)
            prompt = self.prepared["condition_a"]["prompt"]
            _require(task_prompt == row["instruction"] and occupation == row["occupation"]
                     and experiment_prompt == {"system": prompt.get("system", "You are a helpful assistant."),
                                                **{key: prompt.get(key) for key in ("prefix", "body", "suffix")}})
            requested = self.document["requested"]
            # Keep the resource bytes private. The endpoint account must be
            # the account sealed by the capture, not a same-named deployment
            # on a different resource selected through environment settings.
            ready = json.loads(_read_bytes(
                _path(_root(self.sources.deployment_binding), deployment.READY_PATH),
                **self.document["upstream_bundles"]["deployment"]["ready"],
            ))
            account = deployment._resource_bytes(deployment._resource_path(self.sources.account_resource_id_file))
            _require(_digest(account) == {key: ready["resource_files"]["account"][key] for key in ("size", "sha256")})
            account_leaf = deployment._resource_parts(account, "account")[-1]
            endpoint = classify_endpoint(provider.endpoint)
            _require(provider.model == requested["deployment"] and provider.provider_id == requested["provider_id"]
                     and provider.reasoning_effort == requested["reasoning_effort"]
                     and provider.model_context_window == requested["context_tokens"]
                     and provider.request_max_retries == provider.stream_max_retries == 0
                     and provider.auth_module == pilot.DEFAULT_AUTH_MODULE and not provider.query_params
                     and provider.auth_scope == pilot.DIRECT_TOKEN_SCOPE
                     and endpoint.kind is EndpointKind.DIRECT_V1 and endpoint.account == account_leaf
                     and os.environ.get("AZURE_AI_ROUTE_PROFILE") == "direct-v1")
            references = reference_files or []
            _require(len(references) == len(row["reference_file_records"]))
            for path, record in zip(references, row["reference_file_records"]):
                path = Path(path)
                _require(path.name == Path(record["path"]).name)
                _root(path.parent)
                _read_bytes(path, size=record["size"], sha256=record["sha256"])
            observer = _TransportObservation(json.loads(_bytes(requested)))
            observer.native_budget, observer.native_budget_task = self.native_budget, task_id
            observer.approved_base_url = provider.endpoint.rstrip("/")
            self.active[task_id] = observer
            if getattr(self, "native_host", None) is not None:
                from gpt56_pilot_runtime_caps_usage import runtime_caps_usage_for

                runtime_caps_usage_for(self).bind_observer(task_id, self.armed[task_id], observer)
            return observer

    def finish_task(self, observer, *, success, thread_id, turn_id) -> dict:
        with self._guard():
            task_ids = [task_id for task_id, held in self.active.items() if held is observer]
            _require(type(observer) is _TransportObservation and len(task_ids) == 1)
            task_id = task_ids[0]
            index = self.armed[task_id]
            transport = observer.finish(success=success, thread_id=thread_id, turn_id=turn_id)
            thread_digest = transport["correlation"]["thread_id_sha256"]
            _require(thread_digest is None or thread_digest not in self.thread_ids)
            call_id = make_call_id(run_id=pilot.RUN_ID, task_id=task_id, stage="codex_app_server_turn",
                                   retry_kind="initial" if index == 0 else "infrastructure", attempt_index=index, sequence=0)
            name = call_id + ".json"
            task = next(row for row in self.document["tasks"] if row["task_id"] == task_id)
            data = _bytes({"receipt_version": "pilot-wire-receipt-v1", "evidence_boundary": BOUNDARY,
                           "run_id": pilot.RUN_ID, "condition": "codex_foundry", "task_order": self.document["task_ids"],
                           "task": task, "attempt_index": index, "retry_kind": "initial" if index == 0 else "infrastructure",
                           "repeat": 1, "logical_turn": 1, "call_id": call_id, "success": success,
                           "prepared_capture": self.linkage, "requested": {**self.document["requested"], "profile": "direct-v1"},
                           "transport": transport, "launch_allowed": False, "full_220_allowed": False})
            with _held_parents(self.workspace, (RESERVATION, DIRECTORY + "/" + name)) as check:
                self._current()
                check()
                _write_no_clobber(self.root / name, data)
                self.files[name] = data
                self._current()
                check()
            linkage = {"path": DIRECTORY + "/" + name, **_digest(data), "attempt_index": index,
                       "evidence_boundary": BOUNDARY}
            self.attempts[task_id].append({"linkage": linkage, "success": success, "accepted": False})
            if thread_digest is not None:
                self.thread_ids.add(thread_digest)
            del self.active[task_id], self.armed[task_id]
            return json.loads(_bytes(linkage))

    def accept_task(self, *, task_id: str, attempt_index: int, result: dict) -> None:
        """Reject forged/missing/stale results before deliverables are accepted."""
        with self._guard():
            rows = self.attempts[task_id]
            _require(type(attempt_index) is int and attempt_index == len(rows) - 1 and bool(rows))
            latest = rows[-1]
            _require(not latest["accepted"] and result.get("pilot_wire_receipt") == latest["linkage"]
                     and result.get("success") is latest["success"])
            self._current()
            latest["accepted"] = True

    def finalize(self, ordered_task_ids: list[str]) -> dict:
        with self._guard():
            _require(self.ready is None and not self.armed and not self.active and ordered_task_ids == self.document["task_ids"])
            _require(all(rows and all(row["accepted"] for row in rows) for rows in self.attempts.values()))
            data = _bytes({"bundle_version": "pilot-wire-receipts-ready-v1", "evidence_boundary": BOUNDARY,
                           "run_id": pilot.RUN_ID, "task_ids": ordered_task_ids, "prepared_capture": self.linkage,
                           "reservation": _digest(self.reservation),
                           "receipts": {task_id: [row["linkage"] for row in self.attempts[task_id]] for task_id in ordered_task_ids},
                           "live_inference_identity_and_wire_unverified": True,
                           "launch_allowed": False, "full_220_allowed": False})
            with _held_parents(self.workspace, (RESERVATION, DIRECTORY + "/" + READY_PATH)) as check:
                self._current()
                check()
                _write_no_clobber(self.root / READY_PATH, data)
                self.ready = data
                self._current()
                check()
            return {"path": DIRECTORY + "/" + READY_PATH, **_digest(data), "evidence_boundary": BOUNDARY,
                    "launch_allowed": False, "full_220_allowed": False}


def verify_pilot_wire_receipts(session: PilotWireReceiptSession) -> dict:
    """A live witness is mandatory: never adopt a disk-only or partial bundle."""
    with _closed():
        _require(type(session) is PilotWireReceiptSession and session.ready is not None)
        with session._guard():
            session._current()
            return json.loads(session.ready)
