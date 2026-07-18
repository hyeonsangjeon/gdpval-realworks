"""Tests for authenticated control/compute command envelopes."""

from __future__ import annotations

import time
import threading

import pytest

from core.agentic_channel import (
    AuthenticatedComputeBackend,
    ChannelError,
    ChannelScope,
    ComputeChannelServer,
    EnvelopeAuthority,
    InMemoryComputeTransport,
)


KEY = b"k" * 32
SCOPE = ChannelScope("run-1", "treatment", "task-1")


class FakeBackend:
    def __init__(self, **task_spec):
        self.task_spec = task_spec
        self.calls = []
        self.closed = False
        self.terminal = None

    def start(self, timeout_seconds=1200.0):
        self.calls.append("start")
        return {"ok": True, "data": {"substrate_manifest": {"sha256": "a" * 64}}}

    def inspect_workspace(self, timeout_seconds=1200.0):
        self.calls.append("inspect_workspace")
        return {"ok": True, "data": {"work": []}}

    def inspect_environment(self, timeout_seconds=1200.0):
        self.calls.append("inspect_environment")
        return {"ok": True, "data": {"python": "3.11"}}

    def reset_work(self, timeout_seconds=1200.0):
        self.calls.append("reset_work")
        return {"ok": True, "data": {}}

    def run_python(self, source, timeout_seconds):
        self.calls.append(("run_python", source, timeout_seconds))
        return {"ok": True, "data": {"returncode": 0}}

    def run_ffmpeg(self, operation, timeout_seconds):
        self.calls.append(("run_ffmpeg", operation["operation"], timeout_seconds))
        return {"ok": True, "data": {"returncode": 0}}

    def inspect_artifacts(self, timeout_seconds=1200.0):
        self.calls.append("inspect_artifacts")
        return {"ok": True, "data": {"artifacts": [{"path": "report.txt"}]}}

    def finalize(self, deliverables, summary, timeout_seconds=1200.0):
        self.calls.append(("finalize", deliverables, summary))
        self.terminal = {
            "success": True,
            "text": summary,
            "files": [{"filename": deliverables[0], "content": b"bytes"}],
        }
        return {"ok": True, "data": {"artifact_count": 1}}

    def best_result(self):
        return self.terminal

    def close(self):
        self.closed = True


def _channel():
    client_authority = EnvelopeAuthority(KEY, SCOPE)
    server_authority = EnvelopeAuthority(KEY, SCOPE)
    backends = []

    def factory(**task_spec):
        backend = FakeBackend(**task_spec)
        backends.append(backend)
        return backend

    server = ComputeChannelServer(server_authority, factory)
    transport = InMemoryComputeTransport(server)
    client = AuthenticatedComputeBackend(
        authority=client_authority,
        transport=transport,
        task_spec={"task_prompt": "task", "reference_ids": ["input-1"]},
    )
    return client, transport, client_authority, server_authority, backends


def test_authenticated_backend_roundtrip_preserves_bytes_and_order():
    client, _, client_auth, server_auth, backends = _channel()

    assert client.start()["ok"] is True
    assert client.run_python("print('ok')", 2.5)["ok"] is True
    assert client.finalize(["report.txt"], "done")["ok"] is True
    assert client.best_result()["files"][0]["content"] == b"bytes"
    client.close()

    assert backends[0].calls == [
        "start",
        ("run_python", "print('ok')", 2.5),
        ("finalize", ["report.txt"], "done"),
    ]
    assert backends[0].closed is True
    assert client_auth.expected_sequence == 5
    assert server_auth.expected_sequence == 5


def test_tampered_payload_is_rejected_before_backend_creation():
    _, transport, _, server_auth, backends = _channel()
    command = EnvelopeAuthority(KEY, SCOPE).command(
        sequence=1,
        operation="start",
        payload={"task_spec": {"task_prompt": "task"}},
        expires_at=int(time.time()) + 60,
    )
    command["payload"]["task_spec"]["task_prompt"] = "tampered"

    with pytest.raises(ChannelError, match="payload_digest_mismatch"):
        transport.exchange(command)

    assert backends == []
    assert server_auth.expected_sequence == 1


def test_cross_scope_and_expired_commands_do_not_mutate_server():
    _, transport, _, server_auth, backends = _channel()
    other = EnvelopeAuthority(
        KEY, ChannelScope("run-2", "treatment", "task-1")
    )
    cross_scope = other.command(
        sequence=1,
        operation="start",
        payload={"task_spec": {}, "timeout_seconds": 60},
        expires_at=int(time.time()) + 60,
    )
    with pytest.raises(ChannelError, match="cross_scope"):
        transport.exchange(cross_scope)

    expired = EnvelopeAuthority(KEY, SCOPE).command(
        sequence=1,
        operation="start",
        payload={"task_spec": {}, "timeout_seconds": 60},
        expires_at=int(time.time()) - 1,
    )
    with pytest.raises(ChannelError, match="expired"):
        transport.exchange(expired)

    assert backends == []
    assert server_auth.expected_sequence == 1


def test_out_of_order_and_reused_nonce_are_rejected_without_dispatch():
    _, transport, _, server_auth, backends = _channel()
    signer = EnvelopeAuthority(KEY, SCOPE)
    future = signer.command(
        sequence=2,
        operation="start",
        payload={"task_spec": {}},
        expires_at=int(time.time()) + 60,
    )
    with pytest.raises(ChannelError, match="out_of_order"):
        transport.exchange(future)

    first = signer.command(
        sequence=1,
        operation="start",
        payload={"task_spec": {}, "timeout_seconds": 60},
        expires_at=int(time.time()) + 60,
        nonce="n" * 48,
    )
    assert transport.exchange(first)
    reused = signer.command(
        sequence=2,
        operation="inspect_workspace",
        payload={},
        expires_at=int(time.time()) + 60,
        nonce="n" * 48,
    )
    with pytest.raises(ChannelError, match="replayed"):
        transport.exchange(reused)

    assert backends[0].calls == ["start"]
    assert server_auth.expected_sequence == 2


def test_result_must_bind_the_exact_outstanding_command():
    client_auth = EnvelopeAuthority(KEY, SCOPE)
    server_auth = EnvelopeAuthority(KEY, SCOPE)
    command = client_auth.command(
        sequence=1,
        operation="inspect_workspace",
        payload={},
        expires_at=int(time.time()) + 60,
    )
    other_command = client_auth.command(
        sequence=1,
        operation="inspect_environment",
        payload={},
        expires_at=int(time.time()) + 60,
    )
    result = server_auth.result(
        command=other_command,
        payload={"ok": True, "data": {}},
        expires_at=int(time.time()) + 60,
    )

    with pytest.raises(ChannelError, match="result_command_mismatch"):
        client_auth.verify_result(result, command=command)

    assert client_auth.expected_sequence == 1


def test_compute_command_cap_stops_before_dispatch():
    client_auth = EnvelopeAuthority(KEY, SCOPE)
    server_auth = EnvelopeAuthority(KEY, SCOPE)
    backends = []

    def factory(**task_spec):
        backend = FakeBackend(**task_spec)
        backends.append(backend)
        return backend

    server = ComputeChannelServer(server_auth, factory, max_commands=1)
    transport = InMemoryComputeTransport(server)
    start = client_auth.command(
        sequence=1,
        operation="start",
        payload={"task_spec": {}, "timeout_seconds": 60},
        expires_at=int(time.time()) + 60,
    )
    assert transport.exchange(start)
    second = client_auth.command(
        sequence=2,
        operation="inspect_workspace",
        payload={},
        expires_at=int(time.time()) + 60,
    )

    with pytest.raises(ChannelError, match="command_cap"):
        transport.exchange(second)

    assert backends[0].calls == ["start"]
    assert server_auth.expected_sequence == 2


def test_long_running_command_gets_fresh_result_expiry(monkeypatch):
    current_time = [1_000]
    monkeypatch.setattr(
        "core.agentic_channel.time.time", lambda: current_time[0]
    )
    client_auth = EnvelopeAuthority(KEY, SCOPE)
    server_auth = EnvelopeAuthority(KEY, SCOPE)

    class LongRunningBackend(FakeBackend):
        def run_python(self, source, timeout_seconds):
            current_time[0] += 1_201
            return super().run_python(source, timeout_seconds)

    server = ComputeChannelServer(server_auth, LongRunningBackend)
    client = AuthenticatedComputeBackend(
        authority=client_auth,
        transport=InMemoryComputeTransport(server),
        task_spec={"task_prompt": "task"},
        ttl_seconds=60,
    )

    assert client.start()["ok"] is True
    assert client.run_python("print('done')", 1_200)["ok"] is True
    assert client_auth.expected_sequence == 3
    assert server_auth.expected_sequence == 3


def test_transport_retry_returns_cached_result_without_redispatch():
    client_auth = EnvelopeAuthority(KEY, SCOPE)
    server_auth = EnvelopeAuthority(KEY, SCOPE)
    backends = []

    def factory(**task_spec):
        backend = FakeBackend(**task_spec)
        backends.append(backend)
        return backend

    server = ComputeChannelServer(server_auth, factory)

    class LostFirstResponse:
        attempts = 0

        def exchange(self, envelope):
            self.attempts += 1
            result = server.handle(envelope)
            if self.attempts == 1:
                raise TimeoutError("response lost")
            return result

    transport = LostFirstResponse()
    client = AuthenticatedComputeBackend(
        authority=client_auth,
        transport=transport,
        task_spec={"task_prompt": "task"},
    )

    assert client.start()["ok"] is True
    assert transport.attempts == 2
    assert backends[0].calls == ["start"]
    server.close()


def test_backend_idle_lease_closes_without_client_close():
    closed = threading.Event()

    class LeaseBackend(FakeBackend):
        def close(self):
            super().close()
            closed.set()

    client_auth = EnvelopeAuthority(KEY, SCOPE)
    server = ComputeChannelServer(
        EnvelopeAuthority(KEY, SCOPE),
        lambda **task_spec: LeaseBackend(**task_spec),
        backend_lease_seconds=0.01,
    )
    transport = InMemoryComputeTransport(server)
    command = client_auth.command(
        sequence=1,
        operation="start",
        payload={"task_spec": {}, "timeout_seconds": 60},
        expires_at=int(time.time()) + 60,
    )

    assert transport.exchange(command)
    assert closed.wait(timeout=1)
    assert server.backend is None