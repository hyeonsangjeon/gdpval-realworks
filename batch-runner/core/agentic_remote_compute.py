"""Mutual-TLS transport for the split Agentic Sandbox compute plane."""

from __future__ import annotations

import base64
import http.client
import json
import os
import ssl
import math
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

    def exchange(self, envelope: Mapping[str, Any]) -> Mapping[str, Any]:
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
        connection = self.connection_factory(
            self.host,
            self.port,
            timeout=min(self.timeout_seconds, float(operation_timeout)),
            context=self.context,
        )
        try:
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
            response = connection.getresponse()
            if response.status != 200:
                response.read(min(self.max_result_bytes, 4096))
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
            payload = response.read(length + 1)
            if len(payload) != length:
                raise RuntimeError("compute response length mismatch")
            decoded = json.loads(payload)
            if not isinstance(decoded, dict):
                raise RuntimeError("compute response is not an object")
            return decoded
        finally:
            connection.close()


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