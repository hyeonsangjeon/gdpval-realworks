"""Tests for mutual-TLS remote compute wiring without network calls."""

from __future__ import annotations

import hashlib
import json
import tempfile
import threading
import ijson
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from core.agentic_channel import (
    ChannelScope,
    ComputeChannelServer,
    EnvelopeAuthority,
)
from core.agentic_compute_service import ApprovedDockerBackendFactory
from core.agentic_compute_service import (
    ComputeHTTPServer,
    _command_deadline,
    _encode_response_before_deadline,
)
from core.agentic_remote_compute import (
    MutualTLSComputeTransport,
    _json_loads_before_deadline,
    remote_backend_factory_from_environment,
)


class FakeSSLContext:
    def __init__(self):
        self.minimum_version = None
        self.check_hostname = None
        self.verify_mode = None
        self.cert_chain = None

    def load_cert_chain(self, certfile, keyfile):
        self.cert_chain = (certfile, keyfile)


class FakeResponse:
    def __init__(self, body, status=200, declared_length=None):
        self.body = body
        self.status = status
        self.offset = 0
        self.declared_length = (
            len(body) if declared_length is None else declared_length
        )

    def getheader(self, name):
        return str(self.declared_length) if name == "Content-Length" else None

    def read(self, length):
        chunk = self.body[self.offset:self.offset + length]
        self.offset += len(chunk)
        return chunk


class FakeConnection:
    response = None
    calls = []

    def __init__(self, host, port, **kwargs):
        self.host = host
        self.port = port
        self.kwargs = kwargs

    def request(self, method, path, body, headers):
        self.calls.append((method, path, body, headers))

    def getresponse(self):
        return self.response

    def close(self):
        pass


def _transport(tmp_path, monkeypatch, response):
    for name in ("ca.pem", "client.pem", "client.key"):
        (tmp_path / name).write_text("fixture", encoding="utf-8")
    context = FakeSSLContext()
    monkeypatch.setattr(
        "core.agentic_remote_compute.ssl.create_default_context",
        lambda purpose, cafile: context,
    )
    FakeConnection.response = response
    FakeConnection.calls = []
    return MutualTLSComputeTransport(
        endpoint="https://compute.example.test/v1/agentic/compute",
        ca_path=tmp_path / "ca.pem",
        client_cert_path=tmp_path / "client.pem",
        client_key_path=tmp_path / "client.key",
        connection_factory=FakeConnection,
    ), context


def test_mtls_transport_requires_https_and_exact_response_length(
    tmp_path, monkeypatch
):
    body = json.dumps({"ok": True}).encode("utf-8")
    transport, context = _transport(
        tmp_path, monkeypatch, FakeResponse(body)
    )

    result = transport.exchange({
        "command": "fixture",
        "payload": {"timeout_seconds": 7.5},
    })

    assert result == {"ok": True}
    assert context.cert_chain == (
        str(tmp_path / "client.pem"), str(tmp_path / "client.key")
    )
    assert FakeConnection.calls[0][0:2] == (
        "POST", "/v1/agentic/compute"
    )
    assert FakeConnection.calls

    with pytest.raises(ValueError, match="plain HTTPS"):
        MutualTLSComputeTransport(
            endpoint="http://compute.example.test/path",
            ca_path=tmp_path / "ca.pem",
            client_cert_path=tmp_path / "client.pem",
            client_key_path=tmp_path / "client.key",
        )


def test_mtls_transport_rejects_oversized_declared_result(
    tmp_path, monkeypatch
):
    transport, _ = _transport(
        tmp_path,
        monkeypatch,
        FakeResponse(b"{}", declared_length=999),
    )
    transport.max_result_bytes = 100

    with pytest.raises(RuntimeError, match="exceeds byte cap"):
        transport.exchange({
            "command": "fixture",
            "payload": {"timeout_seconds": 10},
        })


def test_compute_response_encoding_stops_at_signed_deadline(monkeypatch):
    current = [100.0]

    def now():
        current[0] += 0.4
        return current[0]

    monkeypatch.setattr("core.agentic_compute_service.time.time", now)

    with pytest.raises(TimeoutError, match="encoding deadline"):
        _encode_response_before_deadline(
            {"payload": ["x"] * 100}, deadline_at=100.5
        )


def test_compute_service_requires_bounded_deadline_before_dispatch(monkeypatch):
    monkeypatch.setattr("core.agentic_compute_service.time.time", lambda: 100.0)

    with pytest.raises(ValueError, match="deadline is invalid"):
        _command_deadline({"payload": {"timeout_seconds": 60}})
    with pytest.raises(ValueError, match="deadline is invalid"):
        _command_deadline({
            "payload": {"timeout_seconds": 60, "deadline_at": 1_301.0}
        })
    assert _command_deadline({
        "payload": {"timeout_seconds": 60, "deadline_at": 160.0}
    }) == 160.0


def test_mtls_chunked_read_enforces_one_attempt_deadline(
    tmp_path, monkeypatch
):
    body = json.dumps({"value": "x" * 70_000}).encode("utf-8")
    response = FakeResponse(body)
    transport, _ = _transport(tmp_path, monkeypatch, response)
    current = [0.0]

    def monotonic():
        return current[0]

    original_read = response.read

    def slow_read(length):
        chunk = original_read(length)
        current[0] += 0.6
        return chunk

    response.read = slow_read
    monkeypatch.setattr(
        "core.agentic_remote_compute.time.monotonic", monotonic
    )

    with pytest.raises(TimeoutError, match="transport deadline"):
        transport.exchange(
            {
                "payload": {"timeout_seconds": 1},
            },
            timeout_seconds=1,
        )


def test_mtls_json_parse_enforces_one_attempt_deadline(monkeypatch):
    payload = json.dumps({"value": "x" * 200_000}).encode("utf-8")
    current = [0.0]

    def monotonic():
        current[0] += 0.2
        return current[0]

    monkeypatch.setattr(
        "core.agentic_remote_compute.time.monotonic", monotonic
    )

    with pytest.raises(TimeoutError, match="transport deadline"):
        _json_loads_before_deadline(payload, 1.0)


def test_streaming_json_preserves_numbers_and_byte_encodings():
    client = EnvelopeAuthority(
        b"k" * 32, ChannelScope("run", "condition", "task")
    )
    server = EnvelopeAuthority(
        b"k" * 32, ChannelScope("run", "condition", "task")
    )
    command = client.command(
        sequence=1,
        operation="export_best_snapshot",
        payload={"timeout_seconds": 60, "deadline_at": 10_060.0},
        expires_at=10_060,
    )
    result = server.result(
        command=command,
        payload={
            "ok": True,
            "huge_integer": 2 ** 100,
            "fraction": 1.25,
            "legacy": {"$bytes": "eA=="},
            "current": b"y",
        },
        expires_at=10_060,
    )
    payload = json.dumps(
        result, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")

    parsed = _json_loads_before_deadline(
        payload, __import__("time").monotonic() + 10
    )
    decoded = client.verify_result(parsed, command=command, now=10_000)

    assert decoded["huge_integer"] == 2 ** 100
    assert type(decoded["huge_integer"]) is int
    assert decoded["fraction"] == 1.25
    assert type(decoded["fraction"]) is float
    assert decoded["legacy"] == b"x"
    assert decoded["current"] == b"y"
    assert isinstance(ijson.backend, str) and ijson.backend


@pytest.mark.parametrize(
    ("constant", "value", "payload", "match"),
    [
        (
            "MAX_JSON_DEPTH",
            3,
            json.dumps({"a": [[[[1]]]]}).encode("utf-8"),
            "depth cap",
        ),
        (
            "MAX_JSON_NODES",
            8,
            json.dumps({"a": list(range(20))}).encode("utf-8"),
            "node cap",
        ),
        (
            "MAX_JSON_STRING_BYTES",
            8,
            json.dumps({"a": "x" * 20}).encode("utf-8"),
            "string cap",
        ),
        (
            "MAX_JSON_MATERIALIZED_BYTES",
            256,
            json.dumps({"a": ["value"] * 20}).encode("utf-8"),
            "materialized byte cap",
        ),
    ],
)
def test_streaming_json_rejects_amplification_shapes(
    monkeypatch, constant, value, payload, match
):
    monkeypatch.setattr(
        f"core.agentic_remote_compute.{constant}", value
    )

    with pytest.raises(RuntimeError, match=match):
        _json_loads_before_deadline(
            payload, __import__("time").monotonic() + 10
        )


def test_streaming_json_rejects_duplicate_keys():
    with pytest.raises(RuntimeError, match="duplicate keys"):
        _json_loads_before_deadline(
            b'{"value":1,"value":2}',
            __import__("time").monotonic() + 10,
        )


def test_mtls_transport_does_not_reset_callers_absolute_deadline(
    tmp_path, monkeypatch
):
    body = json.dumps({"ok": True}).encode("utf-8")
    response = FakeResponse(body)
    transport, _ = _transport(tmp_path, monkeypatch, response)
    current = [100.8]
    original_read = response.read

    def slow_read(length):
        current[0] += 0.3
        return original_read(length)

    response.read = slow_read
    monkeypatch.setattr(
        "core.agentic_remote_compute.time.monotonic",
        lambda: current[0],
    )

    with pytest.raises(TimeoutError, match="transport deadline"):
        transport.exchange(
            {"payload": {"timeout_seconds": 10}},
            timeout_seconds=10,
            monotonic_deadline=101.0,
        )


def test_remote_factory_environment_is_fail_closed(monkeypatch):
    for name in (
        "AGENTIC_COMPUTE_ENDPOINT", "AGENTIC_COMPUTE_CA_PATH",
        "AGENTIC_COMPUTE_CLIENT_CERT_PATH", "AGENTIC_COMPUTE_CLIENT_KEY_PATH",
        "AGENTIC_COMPUTE_CHANNEL_KEY_B64",
    ):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(ValueError, match="environment is incomplete"):
        remote_backend_factory_from_environment(
            run_id="run", condition_name="treatment"
        )


def test_approved_compute_factory_maps_only_frozen_reference_ids(
    tmp_path, monkeypatch
):
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    source = dataset / "source.txt"
    source.write_text("approved", encoding="utf-8")
    metadata = source.stat()
    record = {
        "reference_id": "ref-1",
        "source_path": "source.txt",
        "relative_path": "inputs/source.txt",
        "path": "inputs/source.txt",
        "type": "regular",
        "link_count": 1,
        "size_bytes": metadata.st_size,
        "source_allocated_bytes": metadata.st_blocks * 512,
        "staged_allocated_bytes": metadata.st_blocks * 512,
        "sha256": "a" * 64,
        "provider_classification": "approved_public_gdpval",
    }
    manifest = tmp_path / "inputs.json"
    manifest_body = {
        "schema_version": "agentic-input-manifest-v1",
        "selection_recomputation_sha256": "e" * 64,
        "provider_classification": "approved_public_gdpval",
        "staging_filesystem_device": Path(tempfile.gettempdir()).stat().st_dev,
        "tasks": {
            "task-1": {
                "reference_ids": ["ref-1"],
                "files": [record],
                "input_merkle_root": "b" * 64,
            }
        },
    }
    manifest_document = {
        **manifest_body,
        "sha256": hashlib.sha256(json.dumps(
            manifest_body, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")).hexdigest(),
    }
    manifest.write_text(json.dumps(manifest_document), encoding="utf-8")
    captured = {}

    class FakeBackend:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def start(self, timeout_seconds=1200.0):
            return {"ok": True, "data": {"input_merkle_root": "b" * 64}}

        def close(self):
            pass

    monkeypatch.setattr(
        "core.agentic_compute_service.AgenticDockerBackend", FakeBackend
    )
    factory = ApprovedDockerBackendFactory(
        input_manifest_path=manifest,
        dataset_root=dataset,
        image="image@sha256:" + "c" * 64,
        verifier_image="image@sha256:" + "c" * 64,
        seccomp_profile="seccomp.json",
        apparmor_profile="agentic-profile",
        sbom_sha256="d" * 64,
    )

    backend = factory(
        task_prompt="task",
        reference_ids=["ref-1"],
        occupation="Analyst",
        task_id="task-1",
    )

    assert backend.start()["ok"] is True
    assert captured["reference_files"] == [{
        "source_root": str(dataset),
        "source_path": "source.txt",
        "relative_path": "inputs/source.txt",
    }]
    assert captured["approved_input_manifest"] == {
        "inputs/source.txt": {
            key: record[key]
            for key in (
                "path", "type", "link_count", "size_bytes",
                "source_allocated_bytes", "sha256",
                "provider_classification",
            )
        }
    }
    assert captured["selection_recomputation_sha256"] == "e" * 64
    assert captured["provider_classification"] == "approved_public_gdpval"

    with pytest.raises(ValueError, match="reference IDs differ"):
        factory(
            task_prompt="task",
            reference_ids=[],
            occupation="Analyst",
            task_id="task-1",
        )


def test_approved_compute_factory_rejects_mixed_provider_classification(
    tmp_path, monkeypatch
):
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    source = dataset / "source.txt"
    source.write_text("approved", encoding="utf-8")
    metadata = source.stat()
    body = {
        "schema_version": "agentic-input-manifest-v1",
        "selection_recomputation_sha256": "e" * 64,
        "provider_classification": "approved_public_gdpval",
        "staging_filesystem_device": Path(tempfile.gettempdir()).stat().st_dev,
        "tasks": {
            "task-1": {
                "reference_ids": ["ref-1"],
                "files": [{
                    "reference_id": "ref-1",
                    "source_path": "source.txt",
                    "relative_path": "source.txt",
                    "path": "source.txt",
                    "type": "regular",
                    "link_count": 1,
                    "size_bytes": metadata.st_size,
                    "source_allocated_bytes": metadata.st_blocks * 512,
                    "staged_allocated_bytes": metadata.st_blocks * 512,
                    "sha256": "a" * 64,
                    "provider_classification": "different_classification",
                }],
                "input_merkle_root": "b" * 64,
            }
        },
    }
    document = {
        **body,
        "sha256": hashlib.sha256(json.dumps(
            body, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")).hexdigest(),
    }
    path = tmp_path / "inputs.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    factory = ApprovedDockerBackendFactory(
        input_manifest_path=path,
        dataset_root=dataset,
        image="image@sha256:" + "c" * 64,
        verifier_image="image@sha256:" + "c" * 64,
        seccomp_profile="seccomp.json",
        apparmor_profile="agentic-profile",
        sbom_sha256="d" * 64,
    )

    with pytest.raises(ValueError, match="classification differs"):
        factory(
            task_prompt="task",
            reference_ids=["ref-1"],
            occupation="Analyst",
            task_id="task-1",
        )


def test_approved_compute_factory_uses_manifest_classification_for_empty_task(
    tmp_path, monkeypatch
):
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    body = {
        "schema_version": "agentic-input-manifest-v1",
        "selection_recomputation_sha256": "e" * 64,
        "provider_classification": "approved_zero_input",
        "staging_filesystem_device": Path(tempfile.gettempdir()).stat().st_dev,
        "tasks": {
            "task-empty": {
                "reference_ids": [],
                "files": [],
                "input_merkle_root": "b" * 64,
            }
        },
    }
    document = {
        **body,
        "sha256": hashlib.sha256(json.dumps(
            body, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")).hexdigest(),
    }
    path = tmp_path / "inputs.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    captured = {}

    class FakeBackend:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(
        "core.agentic_compute_service.AgenticDockerBackend", FakeBackend
    )
    factory = ApprovedDockerBackendFactory(
        input_manifest_path=path,
        dataset_root=dataset,
        image="image@sha256:" + "c" * 64,
        verifier_image="image@sha256:" + "c" * 64,
        seccomp_profile="seccomp.json",
        apparmor_profile="agentic-profile",
        sbom_sha256="d" * 64,
    )

    factory(
        task_prompt="task",
        reference_ids=[],
        occupation="Analyst",
        task_id="task-empty",
    )

    assert captured["reference_files"] == []
    assert captured["approved_input_manifest"] == {}
    assert captured["provider_classification"] == "approved_zero_input"


def _certificate_fixture(tmp_path):
    now = datetime.now(timezone.utc)
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Agentic Test CA")])
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(hours=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .sign(ca_key, hashes.SHA256())
    )

    def issue(name, usage, dns_name=None):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        builder = (
            x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)]))
            .issuer_name(ca_name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=1))
            .not_valid_after(now + timedelta(hours=1))
            .add_extension(x509.ExtendedKeyUsage([usage]), critical=False)
        )
        if dns_name:
            builder = builder.add_extension(
                x509.SubjectAlternativeName([x509.DNSName(dns_name)]),
                critical=False,
            )
        return key, builder.sign(ca_key, hashes.SHA256())

    server_key, server_cert = issue(
        "localhost", ExtendedKeyUsageOID.SERVER_AUTH, "localhost"
    )
    client_key, client_cert = issue(
        "agentic-control", ExtendedKeyUsageOID.CLIENT_AUTH
    )
    ca_path = tmp_path / "ca.pem"
    server_cert_path = tmp_path / "server.pem"
    server_key_path = tmp_path / "server.key"
    client_cert_path = tmp_path / "client.pem"
    client_key_path = tmp_path / "client.key"
    ca_path.write_bytes(ca_cert.public_bytes(serialization.Encoding.PEM))
    for path, value in (
        (server_cert_path, server_cert),
        (client_cert_path, client_cert),
    ):
        path.write_bytes(value.public_bytes(serialization.Encoding.PEM))
    for path, value in (
        (server_key_path, server_key),
        (client_key_path, client_key),
    ):
        path.write_bytes(value.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ))
    return (
        ca_path, server_cert_path, server_key_path,
        client_cert_path, client_key_path,
    )


def test_real_mutual_tls_authenticated_roundtrip(tmp_path):
    (
        ca_path, server_cert_path, server_key_path,
        client_cert_path, client_key_path,
    ) = _certificate_fixture(tmp_path)
    scope = ChannelScope("run", "treatment", "task")
    key = b"m" * 32

    backends = []

    class Backend:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.closed = False
            backends.append(self)

        def start(self, timeout_seconds=1200.0):
            return {"ok": True, "data": {"started": True}}

        def close(self):
            self.closed = True

    compute = ComputeChannelServer(
        EnvelopeAuthority(key, scope), lambda **kwargs: Backend(**kwargs)
    )
    server = ComputeHTTPServer(("127.0.0.1", 0), compute)
    context = __import__("ssl").SSLContext(__import__("ssl").PROTOCOL_TLS_SERVER)
    context.load_cert_chain(server_cert_path, server_key_path)
    context.load_verify_locations(ca_path)
    context.verify_mode = __import__("ssl").CERT_REQUIRED
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        authority = EnvelopeAuthority(key, scope)
        command = authority.command(
            sequence=1,
            operation="start",
            payload={
                "task_spec": {"task_prompt": "task"},
                "timeout_seconds": 60,
                "deadline_at": datetime.now(timezone.utc).timestamp() + 60,
            },
            expires_at=int(datetime.now(timezone.utc).timestamp()) + 60,
        )
        transport = MutualTLSComputeTransport(
            endpoint=(
                f"https://localhost:{server.server_address[1]}"
                "/v1/agentic/compute"
            ),
            ca_path=ca_path,
            client_cert_path=client_cert_path,
            client_key_path=client_key_path,
        )
        response = transport.exchange(command)
        decoded = authority.verify_result(response, command=command)

        assert decoded == {"ok": True, "data": {"started": True}}
        close_command = authority.command(
            sequence=2,
            operation="close",
            payload={
                "timeout_seconds": 30.0,
                "deadline_at": datetime.now(timezone.utc).timestamp() + 30,
            },
            expires_at=int(datetime.now(timezone.utc).timestamp()) + 60,
        )
        close_response = transport.exchange(close_command)
        close_decoded = authority.verify_result(
            close_response, command=close_command
        )
        assert close_decoded == {"ok": True, "data": {}}
        assert backends[0].closed is True
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)