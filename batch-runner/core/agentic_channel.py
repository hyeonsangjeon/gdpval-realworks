"""Authenticated, ordered command channel between control and compute planes."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import threading
import time
import math
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol


PROTOCOL_VERSION = "agentic-compute-v1"
MAX_CHANNEL_DEPTH = 32
MAX_CHANNEL_NODES = 200_000
MAX_CHANNEL_TEXT_BYTES = 256 * 1024
MAX_CHANNEL_BYTE_STRING_BYTES = 512 * 1024
MAX_CHANNEL_TOTAL_STRING_BYTES = 384 * 1024 * 1024
CHANNEL_RAW_BYTE_CHUNK = 384 * 1024


class ChannelError(RuntimeError):
    pass


class ComputeTransport(Protocol):
    def exchange(
        self,
        envelope: Mapping[str, Any],
        *,
        timeout_seconds: float | None = None,
        monotonic_deadline: float | None = None,
    ) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class ChannelScope:
    run_id: str
    condition: str
    task_id: str

    def __post_init__(self) -> None:
        if any(not isinstance(value, str) or not value for value in (
            self.run_id, self.condition, self.task_id
        )):
            raise ValueError("channel scope fields are required")


class EnvelopeAuthority:
    """Sign and consume one ordered envelope stream for one task scope."""

    def __init__(
        self,
        key: bytes,
        scope: ChannelScope,
        *,
        max_clock_skew_seconds: int = 30,
    ):
        if not isinstance(key, bytes) or len(key) < 32:
            raise ValueError("channel key must contain at least 32 bytes")
        self.key = key
        self.scope = scope
        self.max_clock_skew_seconds = max_clock_skew_seconds
        self.expected_sequence = 1
        self.used_nonces: set[str] = set()

    def command(
        self,
        *,
        sequence: int,
        operation: str,
        payload: Mapping[str, Any],
        expires_at: int,
        nonce: str | None = None,
    ) -> dict:
        encoded_payload = _encode_value(dict(payload))
        envelope = {
            "protocol_version": PROTOCOL_VERSION,
            "run_id": self.scope.run_id,
            "condition": self.scope.condition,
            "task_id": self.scope.task_id,
            "sequence": sequence,
            "nonce": nonce or secrets.token_hex(24),
            "expires_at": expires_at,
            "operation": operation,
            "payload": encoded_payload,
            "payload_sha256": _digest(encoded_payload),
        }
        envelope["mac"] = self._mac(envelope)
        return envelope

    def result(
        self,
        *,
        command: Mapping[str, Any],
        payload: Mapping[str, Any],
        expires_at: int,
        deadline_at: float | None = None,
    ) -> dict:
        _check_wall_deadline(deadline_at)
        encoded_payload = _encode_value(
            dict(payload), deadline_at=deadline_at
        )
        _check_wall_deadline(deadline_at)
        envelope = {
            "protocol_version": PROTOCOL_VERSION,
            "run_id": command["run_id"],
            "condition": command["condition"],
            "task_id": command["task_id"],
            "sequence": command["sequence"],
            "nonce": command["nonce"],
            "expires_at": expires_at,
            "command_sha256": _digest(
                _without_mac(command), deadline_at=deadline_at
            ),
            "payload": encoded_payload,
            "payload_sha256": _digest(
                encoded_payload, deadline_at=deadline_at
            ),
        }
        envelope["mac"] = self._mac(
            envelope, deadline_at=deadline_at
        )
        _check_wall_deadline(deadline_at)
        return envelope

    def verify_command(
        self, envelope: Mapping[str, Any], *, now: int | None = None
    ) -> dict:
        self._verify_common(envelope, now=now, max_future_seconds=330)
        required = {
            "protocol_version", "run_id", "condition", "task_id", "sequence",
            "nonce", "expires_at", "operation", "payload", "payload_sha256",
            "mac",
        }
        if set(envelope) != required:
            raise ChannelError("command_fields_invalid")
        if not isinstance(envelope.get("operation"), str) or not envelope["operation"]:
            raise ChannelError("command_operation_invalid")
        return _decode_value(envelope["payload"])

    def commit_command(self, envelope: Mapping[str, Any]) -> None:
        sequence = envelope.get("sequence")
        nonce = envelope.get("nonce")
        if sequence != self.expected_sequence or nonce in self.used_nonces:
            raise ChannelError("command_commit_state_mismatch")
        self._consume(envelope)

    def verify_cached_retry(
        self,
        envelope: Mapping[str, Any],
        *,
        original: Mapping[str, Any],
        cache_expires_at: int,
        now: int | None = None,
    ) -> None:
        if not isinstance(envelope, Mapping) or dict(envelope) != dict(original):
            raise ChannelError("cached_command_mismatch")
        expected = {
            "run_id": self.scope.run_id,
            "condition": self.scope.condition,
            "task_id": self.scope.task_id,
        }
        if (
            envelope.get("protocol_version") != PROTOCOL_VERSION
            or any(envelope.get(key) != value for key, value in expected.items())
        ):
            raise ChannelError("cached_command_scope_mismatch")
        if envelope.get("sequence") != self.expected_sequence - 1:
            raise ChannelError("cached_command_sequence_mismatch")
        nonce = envelope.get("nonce")
        if not isinstance(nonce, str) or nonce not in self.used_nonces:
            raise ChannelError("cached_command_nonce_mismatch")
        current = int(time.time()) if now is None else now
        if type(cache_expires_at) is not int or cache_expires_at < current:
            raise ChannelError("cached_result_expired")
        if envelope.get("payload_sha256") != _digest(envelope.get("payload")):
            raise ChannelError("payload_digest_mismatch")
        supplied_mac = envelope.get("mac")
        if not isinstance(supplied_mac, str) or not hmac.compare_digest(
            supplied_mac, self._mac(envelope)
        ):
            raise ChannelError("envelope_mac_invalid")

    def verify_result(
        self,
        envelope: Mapping[str, Any],
        *,
        command: Mapping[str, Any],
        now: int | None = None,
        deadline_at: float | None = None,
        monotonic_deadline: float | None = None,
    ) -> dict:
        self._verify_common(
            envelope,
            now=now,
            max_future_seconds=1500,
            deadline_at=deadline_at,
            monotonic_deadline=monotonic_deadline,
        )
        required = {
            "protocol_version", "run_id", "condition", "task_id", "sequence",
            "nonce", "expires_at", "command_sha256", "payload",
            "payload_sha256", "mac",
        }
        if set(envelope) != required:
            raise ChannelError("result_fields_invalid")
        if envelope.get("command_sha256") != _digest(
            _without_mac(command),
            deadline_at=deadline_at,
            monotonic_deadline=monotonic_deadline,
        ):
            raise ChannelError("result_command_mismatch")
        if envelope.get("nonce") != command.get("nonce"):
            raise ChannelError("result_nonce_mismatch")
        decoded = _decode_value(
            envelope["payload"],
            deadline_at=deadline_at,
            monotonic_deadline=monotonic_deadline,
        )
        if not isinstance(decoded, dict):
            raise ChannelError("compute_result_not_object")
        _check_wall_deadline(deadline_at, monotonic_deadline)
        self._consume(envelope)
        return decoded

    def _verify_common(
        self,
        envelope: Mapping[str, Any],
        *,
        now: int | None,
        max_future_seconds: int,
        deadline_at: float | None = None,
        monotonic_deadline: float | None = None,
    ) -> None:
        _check_wall_deadline(deadline_at, monotonic_deadline)
        if not isinstance(envelope, Mapping):
            raise ChannelError("envelope_not_object")
        if envelope.get("protocol_version") != PROTOCOL_VERSION:
            raise ChannelError("protocol_mismatch")
        expected = {
            "run_id": self.scope.run_id,
            "condition": self.scope.condition,
            "task_id": self.scope.task_id,
        }
        if any(envelope.get(key) != value for key, value in expected.items()):
            raise ChannelError("cross_scope_envelope")
        sequence = envelope.get("sequence")
        if type(sequence) is not int or sequence != self.expected_sequence:
            raise ChannelError("out_of_order_envelope")
        nonce = envelope.get("nonce")
        if not isinstance(nonce, str) or len(nonce) < 32:
            raise ChannelError("nonce_invalid")
        if nonce in self.used_nonces:
            raise ChannelError("replayed_envelope")
        expires_at = envelope.get("expires_at")
        current = int(time.time()) if now is None else now
        if type(expires_at) is not int or expires_at < current:
            raise ChannelError("expired_envelope")
        if expires_at > current + self.max_clock_skew_seconds + max_future_seconds:
            raise ChannelError("envelope_expiry_too_far")
        if envelope.get("payload_sha256") != _digest(
            envelope.get("payload"),
            deadline_at=deadline_at,
            monotonic_deadline=monotonic_deadline,
        ):
            raise ChannelError("payload_digest_mismatch")
        supplied_mac = envelope.get("mac")
        if not isinstance(supplied_mac, str) or not hmac.compare_digest(
            supplied_mac,
            self._mac(
                envelope,
                deadline_at=deadline_at,
                monotonic_deadline=monotonic_deadline,
            ),
        ):
            raise ChannelError("envelope_mac_invalid")
        _check_wall_deadline(deadline_at, monotonic_deadline)

    def _consume(self, envelope: Mapping[str, Any]) -> None:
        self.used_nonces.add(str(envelope["nonce"]))
        self.expected_sequence += 1

    def _mac(
        self,
        envelope: Mapping[str, Any],
        *,
        deadline_at: float | None = None,
        monotonic_deadline: float | None = None,
    ) -> str:
        digest = hmac.new(self.key, digestmod=hashlib.sha256)
        for chunk in _canonical_chunks(
            _without_mac(envelope),
            deadline_at=deadline_at,
            monotonic_deadline=monotonic_deadline,
        ):
            digest.update(chunk)
        return digest.hexdigest()


class ComputeChannelServer:
    """Uncredentialed server-side dispatcher for one authenticated task."""

    def __init__(
        self,
        authority: EnvelopeAuthority,
        backend_factory: Callable[..., Any],
        max_commands: int = 16,
        result_ttl_seconds: int = 60,
        backend_lease_seconds: float = 1260.0,
    ):
        if not 1 <= result_ttl_seconds <= 300:
            raise ValueError("result TTL must be between 1 and 300 seconds")
        if not 0 < backend_lease_seconds <= 1800:
            raise ValueError("backend lease must be in (0, 1800] seconds")
        self.authority = authority
        self.backend_factory = backend_factory
        self.backend: Any = None
        self.max_commands = max_commands
        self.result_ttl_seconds = result_ttl_seconds
        self.backend_lease_seconds = backend_lease_seconds
        self.command_count = 0
        self.lock = threading.Lock()
        self._lease_timer: threading.Timer | None = None
        self._last_command: dict | None = None
        self._last_result: dict | None = None

    def handle(self, envelope: Mapping[str, Any]) -> dict:
        with self.lock:
            if (
                self._last_command is not None
                and self._last_result is not None
                and _without_mac(envelope) == _without_mac(self._last_command)
            ):
                self.authority.verify_cached_retry(
                    envelope,
                    original=self._last_command,
                    cache_expires_at=int(self._last_result["expires_at"]),
                )
                return dict(self._last_result)
            if self.command_count >= self.max_commands:
                raise ChannelError("compute_command_cap_exhausted")
            payload = self.authority.verify_command(envelope)
            timeout = _payload_timeout(payload, require_deadline=True)
            operation = envelope["operation"]
            try:
                if operation == "start":
                    if self.backend is not None:
                        raise ChannelError("backend_already_started")
                    task_spec = payload.get("task_spec")
                    if not isinstance(task_spec, dict):
                        raise ChannelError("task_spec_invalid")
                    self.backend = self.backend_factory(**task_spec)
                    self._arm_lease_locked()
                    result = self.backend.start(timeout)
                else:
                    if self.backend is None:
                        raise ChannelError("backend_not_started")
                    result = self._dispatch(operation, payload)
            except Exception:
                error_type = "compute_dispatch_failed"
                if operation == "start":
                    error_type = "compute_start_failed"
                    try:
                        self._close_backend_locked()
                    except Exception:
                        error_type = "compute_start_cleanup_failed"
                        self._arm_lease_locked()
                result = {
                    "ok": False,
                    "error_type": error_type,
                    "retryable": False,
                }
            self.command_count += 1
            result_expires_at = int(time.time()) + self.result_ttl_seconds
            if payload.get("deadline_at") is not None:
                result_expires_at = max(
                    result_expires_at,
                    math.ceil(float(payload["deadline_at"]))
                    + self.result_ttl_seconds,
                )
            try:
                signed_result = self.authority.result(
                    command=envelope,
                    payload=dict(result),
                    expires_at=result_expires_at,
                    deadline_at=(
                        float(payload["deadline_at"])
                        if payload.get("deadline_at") is not None
                        else None
                    ),
                )
            except Exception:
                cleanup_failed = False
                try:
                    self._close_backend_locked()
                except Exception:
                    cleanup_failed = True
                signed_result = self.authority.result(
                    command=envelope,
                    payload={
                        "ok": False,
                        "error_type": (
                            "post_dispatch_cleanup_failed"
                            if cleanup_failed
                            else "post_dispatch_result_failed"
                        ),
                        "retryable": False,
                    },
                    expires_at=result_expires_at,
                )
            self.authority.commit_command(envelope)
            self._last_command = dict(envelope)
            self._last_result = dict(signed_result)
            if self.backend is None:
                self._cancel_lease_locked()
            else:
                self._arm_lease_locked()
            return signed_result

    def _dispatch(self, operation: str, payload: Mapping[str, Any]):
        timeout = _payload_timeout(payload, require_deadline=True)
        if operation == "inspect_workspace":
            return self.backend.inspect_workspace(timeout)
        if operation == "inspect_environment":
            return self.backend.inspect_environment(timeout)
        if operation == "reset_work":
            return self.backend.reset_work(timeout)
        if operation == "run_python":
            return self.backend.run_python(
                payload["source"], timeout
            )
        if operation == "run_ffmpeg":
            return self.backend.run_ffmpeg(
                payload["operation"], timeout
            )
        if operation == "inspect_artifacts":
            return self.backend.inspect_artifacts(timeout)
        if operation == "export_best_snapshot":
            terminal = self.backend.best_result(timeout)
            if terminal is None:
                return {
                    "ok": False,
                    "error_type": "best_snapshot_unavailable",
                    "retryable": False,
                }
            return {
                "ok": True,
                "data": {"sealed": True},
                "terminal_result": terminal,
            }
        if operation == "finalize":
            result = self.backend.finalize(
                payload["deliverables"], payload["summary"],
                timeout,
            )
            terminal = self.backend.best_result(_payload_timeout(
                payload, require_deadline=True
            ))
            return {**dict(result), "terminal_result": terminal}
        if operation == "close":
            self._close_backend_locked()
            return {"ok": True, "data": {}}
        raise ChannelError("unknown_compute_operation")

    def close(self) -> None:
        with self.lock:
            self._close_backend_locked()
            self._cancel_lease_locked()

    def _arm_lease_locked(self) -> None:
        self._cancel_lease_locked()
        timer = threading.Timer(
            self.backend_lease_seconds, self._expire_backend
        )
        timer.daemon = True
        self._lease_timer = timer
        timer.start()

    def _cancel_lease_locked(self) -> None:
        if self._lease_timer is not None:
            self._lease_timer.cancel()
            self._lease_timer = None

    def _expire_backend(self) -> None:
        with self.lock:
            try:
                self._close_backend_locked()
                self._lease_timer = None
            except Exception:
                timer = threading.Timer(30.0, self._expire_backend)
                timer.daemon = True
                self._lease_timer = timer
                timer.start()

    def _close_backend_locked(self) -> None:
        backend = self.backend
        if backend is not None:
            backend.close()
            self.backend = None


class InMemoryComputeTransport:
    """Model-free transport used to falsify the envelope protocol."""

    def __init__(self, server: ComputeChannelServer):
        self.server = server

    def exchange(
        self,
        envelope: Mapping[str, Any],
        *,
        timeout_seconds: float | None = None,
        monotonic_deadline: float | None = None,
    ) -> Mapping[str, Any]:
        if (
            monotonic_deadline is not None
            and time.monotonic() >= monotonic_deadline
        ):
            raise TimeoutError("compute transport deadline exhausted")
        result = self.server.handle(envelope)
        if (
            monotonic_deadline is not None
            and time.monotonic() >= monotonic_deadline
        ):
            raise TimeoutError("compute transport deadline exhausted")
        return result


class AuthenticatedComputeBackend:
    """Control-plane proxy; transport must provide mTLS outside this module."""

    def __init__(
        self,
        *,
        authority: EnvelopeAuthority,
        transport: ComputeTransport,
        task_spec: Mapping[str, Any],
        ttl_seconds: int = 60,
        max_transport_retries: int = 1,
    ):
        self.authority = authority
        self.transport = transport
        self.task_spec = dict(task_spec)
        self.ttl_seconds = ttl_seconds
        if max_transport_retries not in (0, 1):
            raise ValueError("compute transport retries must be 0 or 1")
        self.max_transport_retries = max_transport_retries
        self.sequence = 0
        self._best_result = None
        self._pending_exchange: dict[str, Any] | None = None

    def start(self, timeout_seconds=1200.0):
        return self._exchange("start", {
            "task_spec": self.task_spec,
            "timeout_seconds": timeout_seconds,
        })

    def inspect_workspace(self, timeout_seconds=1200.0):
        return self._exchange("inspect_workspace", {
            "timeout_seconds": timeout_seconds,
        })

    def inspect_environment(self, timeout_seconds=1200.0):
        return self._exchange("inspect_environment", {
            "timeout_seconds": timeout_seconds,
        })

    def reset_work(self, timeout_seconds=1200.0):
        return self._exchange("reset_work", {"timeout_seconds": timeout_seconds})

    def run_python(self, source, timeout_seconds):
        return self._exchange("run_python", {
            "source": source,
            "timeout_seconds": timeout_seconds,
        })

    def run_ffmpeg(self, operation, timeout_seconds):
        return self._exchange("run_ffmpeg", {
            "operation": dict(operation),
            "timeout_seconds": timeout_seconds,
        })

    def inspect_artifacts(self, timeout_seconds=1200.0):
        deadline = _deadline(timeout_seconds)
        result = self._exchange("inspect_artifacts", {
            "timeout_seconds": _remaining(deadline),
        }, deadline=deadline)
        if result.get("ok") is True:
            sealed = self._exchange("export_best_snapshot", {
                "timeout_seconds": _remaining(deadline),
            }, deadline=deadline)
            terminal = sealed.pop("terminal_result", None)
            if (
                sealed.get("ok") is False
                and sealed.get("error_type") == "best_snapshot_unavailable"
            ):
                return result
            if sealed.get("ok") is not True or terminal is None:
                raise ChannelError("best_snapshot_export_failed")
            self._best_result = terminal
        return result

    def finalize(self, deliverables, summary, timeout_seconds=1200.0):
        result = self._exchange("finalize", {
            "deliverables": list(deliverables),
            "summary": summary,
            "timeout_seconds": timeout_seconds,
        })
        terminal = result.pop("terminal_result", None)
        if terminal is not None:
            self._best_result = terminal
        return result

    def best_result(self):
        return self._best_result

    def close(self):
        result = self._exchange("close", {"timeout_seconds": 30.0})
        if result.get("ok") is not True:
            raise ChannelError(
                str(result.get("error_type") or "compute_close_failed")
            )
        return result

    def _exchange(
        self,
        operation: str,
        payload: Mapping[str, Any],
        *,
        deadline: float | None = None,
    ) -> dict:
        requested_payload = dict(payload)
        pending = self._pending_exchange
        if pending is not None:
            if (
                pending["operation"] != operation
                or pending["requested_payload"] != requested_payload
            ):
                raise ChannelError("compute_channel_state_indeterminate")
            deadline = float(pending["deadline"])
            command_deadline_at = float(pending["command_deadline_at"])
            command = dict(pending["command"])
            candidate_sequence = int(pending["sequence"])
        else:
            deadline = deadline or _deadline(
                float(payload.get("timeout_seconds", self.ttl_seconds))
            )
            remaining = _remaining(deadline)
            command_payload = dict(payload)
            command_payload["timeout_seconds"] = remaining
            command_payload["deadline_at"] = time.time() + remaining
            command_deadline_at = float(command_payload["deadline_at"])
            candidate_sequence = self.sequence + 1
            expires_at = int(time.time()) + self.ttl_seconds
            command = self.authority.command(
                sequence=candidate_sequence,
                operation=operation,
                payload=command_payload,
                expires_at=expires_at,
            )
            self._pending_exchange = {
                "operation": operation,
                "requested_payload": requested_payload,
                "deadline": deadline,
                "command_deadline_at": command_deadline_at,
                "command": dict(command),
                "sequence": candidate_sequence,
            }
        last_error: Exception | None = None
        decoded = None
        for _ in range(self.max_transport_retries + 1):
            try:
                remaining = _remaining(deadline)
                raw_result = self.transport.exchange(
                    command,
                    timeout_seconds=remaining,
                    monotonic_deadline=deadline,
                )
                decoded = self.authority.verify_result(
                    raw_result,
                    command=command,
                    deadline_at=command_deadline_at,
                    monotonic_deadline=deadline,
                )
                break
            except Exception as exc:
                last_error = exc
        if decoded is None:
            assert last_error is not None
            raise last_error
        if not isinstance(decoded, dict):
            raise ChannelError("compute_result_not_object")
        self.sequence = candidate_sequence
        self._pending_exchange = None
        return decoded


def _deadline(timeout_seconds: float) -> float:
    if (
        isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, (int, float))
        or not math.isfinite(float(timeout_seconds))
        or not 0 < float(timeout_seconds) <= 1200
    ):
        raise ValueError("compute timeout must be in (0, 1200]")
    return time.monotonic() + float(timeout_seconds)


def _remaining(deadline: float) -> float:
    value = deadline - time.monotonic()
    if value <= 0:
        raise TimeoutError("compute task deadline exhausted")
    return max(0.001, min(1200.0, value))


def _payload_timeout(
    payload: Mapping[str, Any], *, require_deadline: bool = False
) -> float:
    raw_timeout = payload.get("timeout_seconds")
    raw_deadline = payload.get("deadline_at")
    if (
        isinstance(raw_timeout, bool)
        or not isinstance(raw_timeout, (int, float))
        or not math.isfinite(float(raw_timeout))
        or not 0 < float(raw_timeout) <= 1200
    ):
        raise ChannelError("compute_timeout_invalid")
    if raw_deadline is None and require_deadline:
        raise ChannelError("compute_deadline_missing")
    if raw_deadline is None:
        return float(raw_timeout)
    if (
        isinstance(raw_deadline, bool)
        or not isinstance(raw_deadline, (int, float))
        or not math.isfinite(float(raw_deadline))
    ):
        raise ChannelError("compute_deadline_invalid")
    remaining = float(raw_deadline) - time.time()
    if remaining <= 0:
        raise ChannelError("compute_deadline_exhausted")
    return max(0.001, min(float(raw_timeout), remaining))


def _encode_value(
    value: Any, *, deadline_at: float | None = None
) -> Any:
    _preflight_raw_channel_value(value, deadline_at=deadline_at)
    return _encode_value_unchecked(value, deadline_at=deadline_at)


def _encode_value_unchecked(
    value: Any, *, deadline_at: float | None = None
) -> Any:
    _check_wall_deadline(deadline_at)
    if isinstance(value, bytes):
        chunks = []
        for offset in range(0, len(value), CHANNEL_RAW_BYTE_CHUNK):
            _check_wall_deadline(deadline_at)
            chunks.append(base64.b64encode(
                value[offset:offset + CHANNEL_RAW_BYTE_CHUNK]
            ).decode("ascii"))
        return {"$bytes_chunks": chunks}
    if isinstance(value, Mapping):
        return {
            key: _encode_value_unchecked(item, deadline_at=deadline_at)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [
            _encode_value_unchecked(item, deadline_at=deadline_at)
            for item in value
        ]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"channel value is not serializable: {type(value).__name__}")


def _preflight_raw_channel_value(
    value: Any, *, deadline_at: float | None = None
) -> None:
    nodes = 0
    total_string_bytes = 0
    stack: list[tuple[Any, int]] = [(value, 1)]

    def charge_nodes(count: int) -> None:
        nonlocal nodes
        nodes += count
        if nodes > MAX_CHANNEL_NODES:
            raise ChannelError("channel_value_node_cap_exceeded")

    def charge_string_size(size: int, maximum: int) -> None:
        nonlocal total_string_bytes
        if size > maximum:
            raise ChannelError("channel_value_string_cap_exceeded")
        total_string_bytes += size
        if total_string_bytes > MAX_CHANNEL_TOTAL_STRING_BYTES:
            raise ChannelError("channel_value_total_string_cap_exceeded")

    def charge_text(item: str, maximum: int) -> None:
        if len(item) > maximum:
            raise ChannelError("channel_value_string_cap_exceeded")
        try:
            size = len(item.encode("utf-8"))
        except UnicodeEncodeError as exc:
            raise ChannelError("channel_value_string_invalid") from exc
        charge_string_size(size, maximum)

    while stack:
        _check_wall_deadline(deadline_at)
        item, depth = stack.pop()
        if depth > MAX_CHANNEL_DEPTH:
            raise ChannelError("channel_value_depth_cap_exceeded")
        if isinstance(item, bytes):
            chunk_count = (
                math.ceil(len(item) / CHANNEL_RAW_BYTE_CHUNK)
                if item else 0
            )
            deepest = depth + (2 if chunk_count else 1)
            if deepest > MAX_CHANNEL_DEPTH:
                raise ChannelError("channel_value_depth_cap_exceeded")
            charge_nodes(3 + chunk_count)
            charge_string_size(
                len("$bytes_chunks".encode("utf-8")),
                MAX_CHANNEL_TEXT_BYTES,
            )
            encoded_size = 4 * math.ceil(len(item) / 3) if item else 0
            if item:
                maximum_chunk_size = 4 * math.ceil(
                    min(len(item), CHANNEL_RAW_BYTE_CHUNK) / 3
                )
                if maximum_chunk_size > MAX_CHANNEL_BYTE_STRING_BYTES:
                    raise ChannelError(
                        "channel_value_string_cap_exceeded"
                    )
            total_string_bytes += encoded_size
            if total_string_bytes > MAX_CHANNEL_TOTAL_STRING_BYTES:
                raise ChannelError(
                    "channel_value_total_string_cap_exceeded"
                )
            continue
        charge_nodes(1)
        if isinstance(item, str):
            charge_text(item, MAX_CHANNEL_TEXT_BYTES)
        elif isinstance(item, Mapping):
            for key, child in item.items():
                if not isinstance(key, str):
                    raise ChannelError("channel_value_key_invalid")
                if depth + 1 > MAX_CHANNEL_DEPTH:
                    raise ChannelError("channel_value_depth_cap_exceeded")
                charge_nodes(1)
                charge_text(key, MAX_CHANNEL_TEXT_BYTES)
                stack.append((child, depth + 1))
        elif isinstance(item, (list, tuple)):
            stack.extend(
                (child, depth + 1) for child in reversed(item)
            )
        elif item is None or isinstance(item, (bool, int)):
            continue
        elif isinstance(item, float) and math.isfinite(item):
            continue
        else:
            raise ChannelError("channel_value_type_invalid")


def _check_wall_deadline(
    deadline_at: float | None,
    monotonic_deadline: float | None = None,
) -> None:
    if deadline_at is not None and time.time() >= deadline_at:
        raise ChannelError("compute_deadline_exhausted")
    if (
        monotonic_deadline is not None
        and time.monotonic() >= monotonic_deadline
    ):
        raise ChannelError("compute_deadline_exhausted")


def _decode_value(
    value: Any,
    *,
    deadline_at: float | None = None,
    monotonic_deadline: float | None = None,
) -> Any:
    _check_wall_deadline(deadline_at, monotonic_deadline)
    if isinstance(value, Mapping):
        if set(value) == {"$bytes"}:
            return _decode_base64_text(
                value["$bytes"], deadline_at, monotonic_deadline
            )
        if set(value) == {"$bytes_chunks"}:
            chunks = value["$bytes_chunks"]
            if not isinstance(chunks, list) or any(
                not isinstance(chunk, str) for chunk in chunks
            ):
                raise ChannelError("byte_chunks_invalid")
            output = bytearray()
            for chunk in chunks:
                output.extend(_decode_base64_text(
                    chunk, deadline_at, monotonic_deadline
                ))
            _check_wall_deadline(deadline_at, monotonic_deadline)
            return bytes(output)
        return {
            str(key): _decode_value(
                item,
                deadline_at=deadline_at,
                monotonic_deadline=monotonic_deadline,
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            _decode_value(
                item,
                deadline_at=deadline_at,
                monotonic_deadline=monotonic_deadline,
            )
            for item in value
        ]
    return value


def _decode_base64_text(
    value: Any,
    deadline_at: float | None,
    monotonic_deadline: float | None,
) -> bytes:
    if not isinstance(value, str):
        raise ChannelError("byte_chunks_invalid")
    output = bytearray()
    encoded_chunk_size = 4 * 1024 * 1024
    for offset in range(0, len(value), encoded_chunk_size):
        _check_wall_deadline(deadline_at, monotonic_deadline)
        output.extend(base64.b64decode(
            value[offset:offset + encoded_chunk_size], validate=True
        ))
    _check_wall_deadline(deadline_at, monotonic_deadline)
    return bytes(output)


def _without_mac(value: Mapping[str, Any]) -> dict:
    return {key: item for key, item in value.items() if key != "mac"}


def _canonical_chunks(
    value: Any,
    *,
    deadline_at: float | None = None,
    monotonic_deadline: float | None = None,
):
    _validate_channel_value_limits(
        value,
        deadline_at=deadline_at,
        monotonic_deadline=monotonic_deadline,
    )
    encoder = json.JSONEncoder(
        sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    for chunk in encoder.iterencode(value):
        _check_wall_deadline(deadline_at, monotonic_deadline)
        yield chunk.encode("utf-8")
    _check_wall_deadline(deadline_at, monotonic_deadline)


def _validate_channel_value_limits(
    value: Any,
    *,
    deadline_at: float | None,
    monotonic_deadline: float | None,
) -> None:
    nodes = 0
    total_string_bytes = 0
    stack: list[tuple[Any, int, int]] = [
        (value, 1, MAX_CHANNEL_TEXT_BYTES)
    ]
    while stack:
        _check_wall_deadline(deadline_at, monotonic_deadline)
        item, depth, string_limit = stack.pop()
        if depth > MAX_CHANNEL_DEPTH:
            raise ChannelError("channel_value_depth_cap_exceeded")
        nodes += 1
        if nodes > MAX_CHANNEL_NODES:
            raise ChannelError("channel_value_node_cap_exceeded")
        if isinstance(item, str):
            if len(item) > string_limit:
                raise ChannelError("channel_value_string_cap_exceeded")
            try:
                encoded_size = len(item.encode("utf-8"))
            except UnicodeEncodeError as exc:
                raise ChannelError("channel_value_string_invalid") from exc
            if encoded_size > string_limit:
                raise ChannelError("channel_value_string_cap_exceeded")
            total_string_bytes += encoded_size
            if total_string_bytes > MAX_CHANNEL_TOTAL_STRING_BYTES:
                raise ChannelError(
                    "channel_value_total_string_cap_exceeded"
                )
        elif isinstance(item, Mapping):
            marker = set(item)
            byte_marker = marker in ({"$bytes"}, {"$bytes_chunks"})
            for key, child in reversed(list(item.items())):
                if not isinstance(key, str):
                    raise ChannelError("channel_value_key_invalid")
                if byte_marker and key == "$bytes" and not isinstance(
                    child, str
                ):
                    raise ChannelError("byte_chunks_invalid")
                if byte_marker and key == "$bytes_chunks":
                    if not isinstance(child, list) or any(
                        not isinstance(chunk, str) for chunk in child
                    ):
                        raise ChannelError("byte_chunks_invalid")
                child_limit = (
                    MAX_CHANNEL_BYTE_STRING_BYTES
                    if byte_marker else MAX_CHANNEL_TEXT_BYTES
                )
                stack.append((child, depth + 1, child_limit))
                stack.append((key, depth + 1, MAX_CHANNEL_TEXT_BYTES))
        elif isinstance(item, (list, tuple)):
            stack.extend(
                (child, depth + 1, string_limit)
                for child in reversed(item)
            )
        elif item is None or isinstance(item, (bool, int)):
            continue
        elif isinstance(item, float) and math.isfinite(item):
            continue
        else:
            raise ChannelError("channel_value_type_invalid")


def _canonical(value: Any) -> bytes:
    return b"".join(_canonical_chunks(value))


def _digest(
    value: Any,
    *,
    deadline_at: float | None = None,
    monotonic_deadline: float | None = None,
) -> str:
    digest = hashlib.sha256()
    for chunk in _canonical_chunks(
        value,
        deadline_at=deadline_at,
        monotonic_deadline=monotonic_deadline,
    ):
        digest.update(chunk)
    return digest.hexdigest()