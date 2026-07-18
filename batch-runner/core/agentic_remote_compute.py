"""Mutual-TLS transport for the split Agentic Sandbox compute plane."""

from __future__ import annotations

import base64
import http.client
import json
import os
import ssl
import math
import sys
import time
import ijson
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, cast
from urllib.parse import urlsplit

from core.agentic_channel import (
    AuthenticatedComputeBackend,
    ChannelScope,
    EnvelopeAuthority,
)


MAX_COMMAND_BYTES = 256 * 1024
MAX_RESULT_BYTES = 384 * 1024 * 1024
MAX_JSON_DEPTH = 32
MAX_JSON_NODES = 200_000
MAX_JSON_STRING_BYTES = 512 * 1024
MAX_JSON_MATERIALIZED_BYTES = 384 * 1024 * 1024


class MutualTLSComputeTransport:
    """One-request HTTPS transport with mandatory server and client identity."""

    def __init__(
        self,
        *,
        endpoint: str,
        ca_path: str | Path,
        client_cert_path: str | Path,
        client_key_path: str | Path,
        timeout_seconds: float = 1200,
        max_result_bytes: int = MAX_RESULT_BYTES,
        connection_factory=None,
    ):
        parsed = urlsplit(endpoint)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("compute endpoint must be a plain HTTPS origin/path")
        self.host = parsed.hostname
        self.port = parsed.port or 443
        self.path = parsed.path or "/v1/agentic/compute"
        if not self.path.startswith("/"):
            raise ValueError("compute endpoint path is invalid")
        for path in (ca_path, client_cert_path, client_key_path):
            if not Path(path).is_file():
                raise ValueError("compute mTLS material is missing")
        self.context = ssl.create_default_context(
            ssl.Purpose.SERVER_AUTH, cafile=str(ca_path)
        )
        self.context.minimum_version = ssl.TLSVersion.TLSv1_2
        self.context.check_hostname = True
        self.context.verify_mode = ssl.CERT_REQUIRED
        self.context.load_cert_chain(
            certfile=str(client_cert_path), keyfile=str(client_key_path)
        )
        self.timeout_seconds = timeout_seconds
        self.max_result_bytes = max_result_bytes
        self.connection_factory = (
            connection_factory or http.client.HTTPSConnection
        )

    def exchange(
        self,
        envelope: Mapping[str, Any],
        *,
        timeout_seconds: float | None = None,
        monotonic_deadline: float | None = None,
    ) -> Mapping[str, Any]:
        body = json.dumps(
            dict(envelope),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        if len(body) > MAX_COMMAND_BYTES:
            raise ValueError("compute command exceeds byte cap")
        payload = envelope.get("payload")
        operation_timeout = (
            payload.get("timeout_seconds")
            if isinstance(payload, Mapping)
            else None
        )
        if (
            isinstance(operation_timeout, bool)
            or not isinstance(operation_timeout, (int, float))
            or not math.isfinite(float(operation_timeout))
            or not 0 < float(operation_timeout) <= 1200
        ):
            raise ValueError("compute operation timeout is invalid")
        attempt_timeout = min(
            self.timeout_seconds,
            float(operation_timeout),
            (
                float(timeout_seconds)
                if timeout_seconds is not None
                else float(operation_timeout)
            ),
        )
        if not math.isfinite(attempt_timeout) or attempt_timeout <= 0:
            raise ValueError("compute transport timeout is invalid")
        now = time.monotonic()
        relative_deadline = now + attempt_timeout
        if monotonic_deadline is not None:
            if (
                isinstance(monotonic_deadline, bool)
                or not isinstance(monotonic_deadline, (int, float))
                or not math.isfinite(float(monotonic_deadline))
                or float(monotonic_deadline) <= now
            ):
                raise TimeoutError("compute transport deadline exhausted")
            deadline = min(relative_deadline, float(monotonic_deadline))
        else:
            deadline = relative_deadline
        connection = self.connection_factory(
            self.host,
            self.port,
            timeout=attempt_timeout,
            context=self.context,
        )
        try:
            _set_deadline_timeout(connection, deadline)
            connect = getattr(connection, "connect", None)
            if callable(connect):
                connect()
            _set_deadline_timeout(connection, deadline)
            connection.request(
                "POST",
                self.path,
                body=body,
                headers={
                    "Content-Type": "application/json",
                    "Content-Length": str(len(body)),
                    "Connection": "close",
                },
            )
            _set_deadline_timeout(connection, deadline)
            response = connection.getresponse()
            if response.status != 200:
                _read_bounded_response(
                    connection,
                    response,
                    min(self.max_result_bytes, 4096),
                    deadline,
                )
                raise RuntimeError("compute transport rejected request")
            content_length = response.getheader("Content-Length")
            if content_length is None:
                raise RuntimeError("compute response length is required")
            try:
                length = int(content_length)
            except ValueError as exc:
                raise RuntimeError("compute response length is invalid") from exc
            if length < 0 or length > self.max_result_bytes:
                raise RuntimeError("compute response exceeds byte cap")
            reader = _DeadlineResponseReader(
                connection, response, length, deadline
            )
            try:
                decoded = _json_load_before_deadline(reader, deadline)
            except RuntimeError as exc:
                if reader.bytes_read != length:
                    raise RuntimeError(
                        "compute response length mismatch"
                    ) from exc
                raise
            if reader.bytes_read != length:
                raise RuntimeError("compute response length mismatch")
            if not isinstance(decoded, dict):
                raise RuntimeError("compute response is not an object")
            return decoded
        finally:
            connection.close()


def _remaining_attempt(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("compute transport deadline exhausted")
    return max(0.001, remaining)


def _set_deadline_timeout(connection: Any, deadline: float) -> None:
    remaining = _remaining_attempt(deadline)
    if hasattr(connection, "timeout"):
        connection.timeout = remaining
    sock = getattr(connection, "sock", None)
    if sock is not None:
        sock.settimeout(remaining)


def _read_bounded_response(
    connection: Any,
    response: Any,
    maximum: int,
    deadline: float,
) -> bytes:
    chunks = []
    total = 0
    while total < maximum:
        _set_deadline_timeout(connection, deadline)
        chunk = response.read(min(64 * 1024, maximum - total))
        _remaining_attempt(deadline)
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
    return b"".join(chunks)


class _DeadlineResponseReader:
    def __init__(
        self,
        connection: Any,
        response: Any,
        expected_bytes: int,
        deadline: float,
    ):
        self.connection = connection
        self.response = response
        self.expected_bytes = expected_bytes
        self.deadline = deadline
        self.bytes_read = 0

    def read(self, size: int = -1) -> bytes:
        _set_deadline_timeout(self.connection, self.deadline)
        if size == 0 or self.bytes_read >= self.expected_bytes:
            return b""
        bounded = 64 * 1024 if size < 0 else min(size, 64 * 1024)
        bounded = min(bounded, self.expected_bytes - self.bytes_read)
        chunk = self.response.read(bounded)
        _remaining_attempt(self.deadline)
        if len(chunk) > bounded:
            raise RuntimeError("compute response exceeded declared length")
        self.bytes_read += len(chunk)
        return chunk


class _DeadlineBytesReader:
    def __init__(self, payload: bytes, deadline: float):
        self.payload = memoryview(payload)
        self.deadline = deadline
        self.offset = 0

    def read(self, size: int = -1) -> bytes:
        _remaining_attempt(self.deadline)
        if size == 0:
            return b""
        bounded = 64 * 1024 if size < 0 else min(size, 64 * 1024)
        end = min(len(self.payload), self.offset + bounded)
        chunk = self.payload[self.offset:end].tobytes()
        self.offset = end
        _remaining_attempt(self.deadline)
        return chunk


def _json_loads_before_deadline(payload: bytes, deadline: float) -> Any:
    reader = _DeadlineBytesReader(payload, deadline)
    return _json_load_before_deadline(reader, deadline)


def _json_load_before_deadline(reader: Any, deadline: float) -> Any:
    stack: list[dict[str, Any]] = []
    root: Any = None
    root_set = False
    nodes = 0
    materialized_bytes = 0

    def charge(value: Any) -> None:
        nonlocal materialized_bytes
        materialized_bytes += sys.getsizeof(value)
        if materialized_bytes > MAX_JSON_MATERIALIZED_BYTES:
            raise RuntimeError("compute response materialized byte cap exceeded")

    def count_node() -> None:
        nonlocal nodes
        nodes += 1
        if nodes > MAX_JSON_NODES:
            raise RuntimeError("compute response node cap exceeded")

    def validate_string(value: Any) -> str:
        if not isinstance(value, str):
            raise RuntimeError("compute response string is invalid")
        if (
            len(value) > MAX_JSON_STRING_BYTES
            or len(value.encode("utf-8")) > MAX_JSON_STRING_BYTES
        ):
            raise RuntimeError("compute response string cap exceeded")
        return value

    def attach(value: Any) -> None:
        nonlocal root, root_set, materialized_bytes
        if not stack:
            if root_set:
                raise RuntimeError("compute response contains multiple values")
            root = value
            root_set = True
            return
        frame = stack[-1]
        container = frame["container"]
        before = sys.getsizeof(container)
        if isinstance(container, list):
            container.append(value)
        else:
            key = frame.get("key")
            if not isinstance(key, str):
                raise RuntimeError("compute response map key is missing")
            if key in container:
                raise RuntimeError("compute response contains duplicate keys")
            container[key] = value
            frame["key"] = None
        materialized_bytes += max(0, sys.getsizeof(container) - before)
        if materialized_bytes > MAX_JSON_MATERIALIZED_BYTES:
            raise RuntimeError("compute response materialized byte cap exceeded")

    try:
        for event, raw_value in ijson.basic_parse(
            reader, use_float=False
        ):
            _remaining_attempt(deadline)
            if event in {"start_map", "start_array"}:
                if len(stack) + 1 > MAX_JSON_DEPTH:
                    raise RuntimeError("compute response depth cap exceeded")
                value: Any = {} if event == "start_map" else []
                count_node()
                charge(value)
                attach(value)
                stack.append({"container": value, "key": None})
            elif event == "map_key":
                if not stack or not isinstance(stack[-1]["container"], dict):
                    raise RuntimeError("compute response map key is misplaced")
                key = validate_string(raw_value)
                count_node()
                charge(key)
                if stack[-1].get("key") is not None:
                    raise RuntimeError("compute response map value is missing")
                stack[-1]["key"] = key
            elif event in {"end_map", "end_array"}:
                if not stack:
                    raise RuntimeError("compute response container is unbalanced")
                frame = stack.pop()
                container = frame["container"]
                if (
                    event == "end_map" and not isinstance(container, dict)
                ) or (
                    event == "end_array" and not isinstance(container, list)
                ):
                    raise RuntimeError("compute response container is unbalanced")
                if isinstance(container, dict) and frame.get("key") is not None:
                    raise RuntimeError("compute response map value is missing")
            else:
                if event == "string":
                    value = validate_string(raw_value)
                elif event in {"number", "integer", "double"}:
                    if isinstance(raw_value, Decimal):
                        value = float(raw_value)
                        if not math.isfinite(value):
                            raise RuntimeError(
                                "compute response number is not finite"
                            )
                    elif type(raw_value) is int:
                        value = raw_value
                    else:
                        raise RuntimeError("compute response number is invalid")
                elif event == "boolean":
                    if type(raw_value) is not bool:
                        raise RuntimeError("compute response boolean is invalid")
                    value = raw_value
                elif event == "null":
                    value = None
                else:
                    raise RuntimeError("compute response event is invalid")
                count_node()
                charge(value)
                attach(value)
    except TimeoutError:
        raise
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError("compute response JSON is invalid") from exc
    if stack or not root_set:
        raise RuntimeError("compute response JSON is incomplete")
    _remaining_attempt(deadline)
    return root


class RemoteBackendFactory:
    def __init__(
        self,
        *,
        endpoint: str,
        ca_path: str,
        client_cert_path: str,
        client_key_path: str,
        channel_key: bytes,
        run_id: str,
        condition_name: str,
        timeout_seconds: float = 1200,
        transport_factory=MutualTLSComputeTransport,
    ):
        self.endpoint = endpoint
        self.ca_path = ca_path
        self.client_cert_path = client_cert_path
        self.client_key_path = client_key_path
        self.channel_key = channel_key
        self.run_id = run_id
        self.condition_name = condition_name
        self.timeout_seconds = timeout_seconds
        self.transport_factory = transport_factory

    def __call__(
        self,
        *,
        task_prompt: str,
        reference_files: list,
        occupation: str,
        run_id: str,
        condition_name: str,
        task_id: str,
    ):
        if run_id != self.run_id or condition_name != self.condition_name:
            raise ValueError("remote compute scope mismatch")
        if not all(isinstance(path, str) and path for path in reference_files):
            raise ValueError("remote compute reference IDs must be strings")
        scope = ChannelScope(run_id, condition_name, task_id)
        authority = EnvelopeAuthority(self.channel_key, scope)
        transport = self.transport_factory(
            endpoint=self.endpoint,
            ca_path=self.ca_path,
            client_cert_path=self.client_cert_path,
            client_key_path=self.client_key_path,
            timeout_seconds=self.timeout_seconds,
        )
        return AuthenticatedComputeBackend(
            authority=authority,
            transport=transport,
            task_spec={
                "task_prompt": task_prompt,
                "reference_ids": list(reference_files),
                "occupation": occupation,
                "task_id": task_id,
            },
        )


def remote_backend_factory_from_environment(
    *,
    run_id: str,
    condition_name: str,
) -> RemoteBackendFactory:
    required = {
        "endpoint": os.getenv("AGENTIC_COMPUTE_ENDPOINT"),
        "ca_path": os.getenv("AGENTIC_COMPUTE_CA_PATH"),
        "client_cert_path": os.getenv("AGENTIC_COMPUTE_CLIENT_CERT_PATH"),
        "client_key_path": os.getenv("AGENTIC_COMPUTE_CLIENT_KEY_PATH"),
        "channel_key": os.getenv("AGENTIC_COMPUTE_CHANNEL_KEY_B64"),
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise ValueError(f"remote compute environment is incomplete: {missing}")
    endpoint = cast(str, required["endpoint"])
    ca_path = cast(str, required["ca_path"])
    client_cert_path = cast(str, required["client_cert_path"])
    client_key_path = cast(str, required["client_key_path"])
    encoded_key = cast(str, required["channel_key"])
    try:
        key = base64.b64decode(encoded_key, validate=True)
    except Exception as exc:
        raise ValueError("remote compute channel key is invalid") from exc
    return RemoteBackendFactory(
        endpoint=endpoint,
        ca_path=ca_path,
        client_cert_path=client_cert_path,
        client_key_path=client_key_path,
        channel_key=key,
        run_id=run_id,
        condition_name=condition_name,
    )