"""Authenticated, ordered command channel between control and compute planes."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol


PROTOCOL_VERSION = "agentic-compute-v1"


class ChannelError(RuntimeError):
    pass


class ComputeTransport(Protocol):
    def exchange(self, envelope: Mapping[str, Any]) -> Mapping[str, Any]: ...


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
    ) -> dict:
        encoded_payload = _encode_value(dict(payload))
        envelope = {
            "protocol_version": PROTOCOL_VERSION,
            "run_id": command["run_id"],
            "condition": command["condition"],
            "task_id": command["task_id"],
            "sequence": command["sequence"],
            "nonce": command["nonce"],
            "expires_at": expires_at,
            "command_sha256": _digest(_without_mac(command)),
            "payload": encoded_payload,
            "payload_sha256": _digest(encoded_payload),
        }
        envelope["mac"] = self._mac(envelope)
        return envelope

    def verify_command(
        self, envelope: Mapping[str, Any], *, now: int | None = None
    ) -> dict:
        self._verify_common(envelope, now=now)
        required = {
            "protocol_version", "run_id", "condition", "task_id", "sequence",
            "nonce", "expires_at", "operation", "payload", "payload_sha256",
            "mac",
        }
        if set(envelope) != required:
            raise ChannelError("command_fields_invalid")
        if not isinstance(envelope.get("operation"), str) or not envelope["operation"]:
            raise ChannelError("command_operation_invalid")
        self._consume(envelope)
        return _decode_value(envelope["payload"])

    def verify_result(
        self,
        envelope: Mapping[str, Any],
        *,
        command: Mapping[str, Any],
        now: int | None = None,
    ) -> dict:
        self._verify_common(envelope, now=now)
        required = {
            "protocol_version", "run_id", "condition", "task_id", "sequence",
            "nonce", "expires_at", "command_sha256", "payload",
            "payload_sha256", "mac",
        }
        if set(envelope) != required:
            raise ChannelError("result_fields_invalid")
        if envelope.get("command_sha256") != _digest(_without_mac(command)):
            raise ChannelError("result_command_mismatch")
        if envelope.get("nonce") != command.get("nonce"):
            raise ChannelError("result_nonce_mismatch")
        self._consume(envelope)
        return _decode_value(envelope["payload"])

    def _verify_common(
        self, envelope: Mapping[str, Any], *, now: int | None
    ) -> None:
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
        if expires_at > current + self.max_clock_skew_seconds + 300:
            raise ChannelError("envelope_expiry_too_far")
        if envelope.get("payload_sha256") != _digest(envelope.get("payload")):
            raise ChannelError("payload_digest_mismatch")
        supplied_mac = envelope.get("mac")
        if not isinstance(supplied_mac, str) or not hmac.compare_digest(
            supplied_mac, self._mac(envelope)
        ):
            raise ChannelError("envelope_mac_invalid")

    def _consume(self, envelope: Mapping[str, Any]) -> None:
        self.used_nonces.add(str(envelope["nonce"]))
        self.expected_sequence += 1

    def _mac(self, envelope: Mapping[str, Any]) -> str:
        return hmac.new(
            self.key,
            _canonical(_without_mac(envelope)),
            hashlib.sha256,
        ).hexdigest()


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
        self._last_command_sha256: str | None = None
        self._last_result: dict | None = None

    def handle(self, envelope: Mapping[str, Any]) -> dict:
        with self.lock:
            command_sha256 = _digest(_without_mac(envelope))
            if (
                command_sha256 == self._last_command_sha256
                and self._last_result is not None
            ):
                return dict(self._last_result)
            if self.command_count >= self.max_commands:
                raise ChannelError("compute_command_cap_exhausted")
            payload = self.authority.verify_command(envelope)
            operation = envelope["operation"]
            try:
                if operation == "start":
                    if self.backend is not None:
                        raise ChannelError("backend_already_started")
                    task_spec = payload.get("task_spec")
                    if not isinstance(task_spec, dict):
                        raise ChannelError("task_spec_invalid")
                    self.backend = self.backend_factory(**task_spec)
                    result = self.backend.start(payload["timeout_seconds"])
                else:
                    if self.backend is None:
                        raise ChannelError("backend_not_started")
                    result = self._dispatch(operation, payload)
            except Exception:
                if operation == "start":
                    self._close_backend_locked()
                raise
            self.command_count += 1
            signed_result = self.authority.result(
                command=envelope,
                payload=dict(result),
                expires_at=int(time.time()) + self.result_ttl_seconds,
            )
            self._last_command_sha256 = command_sha256
            self._last_result = dict(signed_result)
            if operation == "close":
                self._cancel_lease_locked()
            else:
                self._arm_lease_locked()
            return signed_result

    def _dispatch(self, operation: str, payload: Mapping[str, Any]):
        if operation == "inspect_workspace":
            return self.backend.inspect_workspace(payload["timeout_seconds"])
        if operation == "inspect_environment":
            return self.backend.inspect_environment(payload["timeout_seconds"])
        if operation == "reset_work":
            return self.backend.reset_work(payload["timeout_seconds"])
        if operation == "run_python":
            return self.backend.run_python(
                payload["source"], payload["timeout_seconds"]
            )
        if operation == "run_ffmpeg":
            return self.backend.run_ffmpeg(
                payload["operation"], payload["timeout_seconds"]
            )
        if operation == "inspect_artifacts":
            return self.backend.inspect_artifacts(payload["timeout_seconds"])
        if operation == "finalize":
            result = self.backend.finalize(
                payload["deliverables"], payload["summary"],
                payload["timeout_seconds"],
            )
            terminal = self.backend.best_result()
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
            self._close_backend_locked()
            self._lease_timer = None

    def _close_backend_locked(self) -> None:
        backend = self.backend
        self.backend = None
        if backend is not None:
            backend.close()


class InMemoryComputeTransport:
    """Model-free transport used to falsify the envelope protocol."""

    def __init__(self, server: ComputeChannelServer):
        self.server = server

    def exchange(self, envelope: Mapping[str, Any]) -> Mapping[str, Any]:
        return self.server.handle(envelope)


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
        return self._exchange("inspect_artifacts", {
            "timeout_seconds": timeout_seconds,
        })

    def finalize(self, deliverables, summary, timeout_seconds=1200.0):
        result = self._exchange("finalize", {
            "deliverables": list(deliverables),
            "summary": summary,
            "timeout_seconds": timeout_seconds,
        })
        self._best_result = result.pop("terminal_result", None)
        return result

    def best_result(self):
        return self._best_result

    def close(self):
        try:
            self._exchange("close", {})
        except Exception:
            pass

    def _exchange(self, operation: str, payload: Mapping[str, Any]) -> dict:
        self.sequence += 1
        expires_at = int(time.time()) + self.ttl_seconds
        command = self.authority.command(
            sequence=self.sequence,
            operation=operation,
            payload=payload,
            expires_at=expires_at,
        )
        last_error: Exception | None = None
        decoded = None
        for _ in range(self.max_transport_retries + 1):
            try:
                raw_result = self.transport.exchange(command)
                decoded = self.authority.verify_result(
                    raw_result,
                    command=command,
                )
                break
            except Exception as exc:
                last_error = exc
        if decoded is None:
            assert last_error is not None
            raise last_error
        if not isinstance(decoded, dict):
            raise ChannelError("compute_result_not_object")
        return decoded


def _encode_value(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"$bytes": base64.b64encode(value).decode("ascii")}
    if isinstance(value, Mapping):
        return {str(key): _encode_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_encode_value(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"channel value is not serializable: {type(value).__name__}")


def _decode_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        if set(value) == {"$bytes"}:
            return base64.b64decode(value["$bytes"], validate=True)
        return {str(key): _decode_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_decode_value(item) for item in value]
    return value


def _without_mac(value: Mapping[str, Any]) -> dict:
    return {key: item for key, item in value.items() if key != "mac"}


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()