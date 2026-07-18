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
    _digest,
    _encode_value,
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
        self.terminal = {
            "success": False,
            "text": "",
            "files": [{"filename": "report.txt", "content": b"candidate"}],
        }
        return {"ok": True, "data": {"artifacts": [{"path": "report.txt"}]}}

    def finalize(self, deliverables, summary, timeout_seconds=1200.0):
        self.calls.append(("finalize", deliverables, summary))
        self.terminal = {
            "success": True,
            "text": summary,
            "files": [{"filename": deliverables[0], "content": b"bytes"}],
        }
        return {"ok": True, "data": {"artifact_count": 1}}

    def best_result(self, timeout_seconds=1200.0):
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

    assert backends[0].calls[0] == "start"
    assert backends[0].calls[1][0:2] == ("run_python", "print('ok')")
    assert backends[0].calls[1][2] == pytest.approx(2.5, abs=0.01)
    assert backends[0].calls[2] == (
        "finalize", ["report.txt"], "done"
    )
    assert backends[0].closed is True
    assert client_auth.expected_sequence == 5
    assert server_auth.expected_sequence == 5


def test_authenticated_inspection_seals_best_snapshot_before_close():
    client, _, client_auth, server_auth, backends = _channel()

    assert client.start()["ok"] is True
    inspected = client.inspect_artifacts()
    candidate = client.best_result()
    client.close()

    assert inspected["ok"] is True
    assert candidate["success"] is False
    assert candidate["files"] == [
        {"filename": "report.txt", "content": b"candidate"}
    ]
    assert backends[0].closed is True
    assert client_auth.expected_sequence == 5
    assert server_auth.expected_sequence == 5


def test_unavailable_full_snapshot_still_allows_subset_finalize():
    class OversizedCandidateBackend(FakeBackend):
        def inspect_artifacts(self, timeout_seconds=1200.0):
            self.calls.append("inspect_artifacts")
            self.terminal = None
            return {
                "ok": True,
                "data": {
                    "artifacts": [
                        {"path": "large.bin", "size_bytes": 200 << 20},
                        {"path": "report.txt", "size_bytes": 1},
                    ]
                },
            }

    server = ComputeChannelServer(
        EnvelopeAuthority(KEY, SCOPE), OversizedCandidateBackend
    )
    client = AuthenticatedComputeBackend(
        authority=EnvelopeAuthority(KEY, SCOPE),
        transport=InMemoryComputeTransport(server),
        task_spec={"task_prompt": "task"},
    )

    assert client.start()["ok"] is True
    assert client.inspect_artifacts()["ok"] is True
    assert client.best_result() is None
    assert client.finalize(["report.txt"], "done")["ok"] is True
    assert client.best_result()["files"] == [
        {"filename": "report.txt", "content": b"bytes"}
    ]
    client.close()


def test_finalize_result_signing_failure_preserves_sealed_candidate():
    class FailingFinalizeResultAuthority(EnvelopeAuthority):
        failed = False

        def result(self, *, command, payload, expires_at, deadline_at=None):
            if command["operation"] == "finalize" and not self.failed:
                self.failed = True
                raise RuntimeError("result signing failed")
            return super().result(
                command=command,
                payload=payload,
                expires_at=expires_at,
                deadline_at=deadline_at,
            )

    server = ComputeChannelServer(
        FailingFinalizeResultAuthority(KEY, SCOPE), FakeBackend
    )
    client = AuthenticatedComputeBackend(
        authority=EnvelopeAuthority(KEY, SCOPE),
        transport=InMemoryComputeTransport(server),
        task_spec={"task_prompt": "task"},
    )
    assert client.start()["ok"] is True
    assert client.inspect_artifacts()["ok"] is True
    previous = client.best_result()

    result = client.finalize(["report.txt"], "done")

    assert result["ok"] is False
    assert result["error_type"] == "post_dispatch_result_failed"
    assert client.best_result() == previous
    assert server.backend is None


def test_large_bytes_use_bounded_chunks_and_roundtrip():
    client_authority = EnvelopeAuthority(KEY, SCOPE)
    server_authority = EnvelopeAuthority(KEY, SCOPE)
    command = client_authority.command(
        sequence=1,
        operation="export_best_snapshot",
        payload={"timeout_seconds": 60, "deadline_at": time.time() + 60},
        expires_at=int(time.time()) + 60,
    )
    content = b"x" * (7 * 1024 * 1024)

    result = server_authority.result(
        command=command,
        payload={"ok": True, "content": content},
        expires_at=int(time.time()) + 60,
        deadline_at=time.time() + 60,
    )

    encoded = result["payload"]["content"]
    assert set(encoded) == {"$bytes_chunks"}
    assert len(encoded["$bytes_chunks"]) == 19
    assert max(
        len(chunk.encode("utf-8"))
        for chunk in encoded["$bytes_chunks"]
    ) <= 512 * 1024
    assert client_authority.verify_result(
        result, command=command
    )["content"] == content


def test_canonical_digest_checks_deadline_between_chunks(monkeypatch):
    checks = []

    def expire_after_several_chunks(deadline_at, monotonic_deadline=None):
        checks.append((deadline_at, monotonic_deadline))
        if len(checks) == 5:
            raise ChannelError("compute_deadline_exhausted")

    monkeypatch.setattr(
        "core.agentic_channel._check_wall_deadline",
        expire_after_several_chunks,
    )

    with pytest.raises(ChannelError, match="deadline_exhausted"):
        _digest(
            {"chunks": ["a" * 1024 for _ in range(100)]},
            deadline_at=1.0,
        )

    assert len(checks) == 5


def test_client_result_verification_stops_at_exchange_deadline(monkeypatch):
    client_authority = EnvelopeAuthority(KEY, SCOPE)
    server_authority = EnvelopeAuthority(KEY, SCOPE)
    command = client_authority.command(
        sequence=1,
        operation="export_best_snapshot",
        payload={"timeout_seconds": 60, "deadline_at": 1_060.0},
        expires_at=1_060,
    )
    result = server_authority.result(
        command=command,
        payload={"ok": True, "items": ["x" * 1024 for _ in range(100)]},
        expires_at=1_060,
    )
    current = [100.0]

    def monotonic():
        value = current[0]
        current[0] += 0.2
        return value

    monkeypatch.setattr("core.agentic_channel.time.time", lambda: 1_000.0)
    monkeypatch.setattr("core.agentic_channel.time.monotonic", monotonic)

    with pytest.raises(ChannelError, match="deadline_exhausted"):
        client_authority.verify_result(
            result,
            command=command,
            deadline_at=1_060.0,
            monotonic_deadline=100.8,
        )

    assert client_authority.expected_sequence == 1


def test_client_base64_decode_stops_at_exchange_deadline(monkeypatch):
    client_authority = EnvelopeAuthority(KEY, SCOPE)
    server_authority = EnvelopeAuthority(KEY, SCOPE)
    command = client_authority.command(
        sequence=1,
        operation="export_best_snapshot",
        payload={"timeout_seconds": 60, "deadline_at": 1_060.0},
        expires_at=1_060,
    )
    result = server_authority.result(
        command=command,
        payload={"ok": True, "content": b"x" * (7 * 1024 * 1024)},
        expires_at=1_060,
    )
    original_digest = client_authority._mac(result)
    assert original_digest == result["mac"]
    checks = [0]
    original_decode = __import__("base64").b64decode

    def advancing_decode(value, validate=False):
        checks[0] += 1
        decoded = original_decode(value, validate=validate)
        if checks[0] == 1:
            current[0] = 101.0
        return decoded

    current = [100.0]
    monkeypatch.setattr("core.agentic_channel.time.time", lambda: 1_000.0)
    monkeypatch.setattr("core.agentic_channel.time.monotonic", lambda: current[0])
    monkeypatch.setattr("core.agentic_channel.base64.b64decode", advancing_decode)

    with pytest.raises(ChannelError, match="deadline_exhausted"):
        client_authority.verify_result(
            result,
            command=command,
            deadline_at=1_060.0,
            monotonic_deadline=100.5,
        )

    assert checks[0] == 1
    assert client_authority.expected_sequence == 1


def test_large_result_signing_stops_when_deadline_expires(monkeypatch):
    client_authority = EnvelopeAuthority(KEY, SCOPE)
    server_authority = EnvelopeAuthority(KEY, SCOPE)
    command = client_authority.command(
        sequence=1,
        operation="export_best_snapshot",
        payload={"timeout_seconds": 60, "deadline_at": time.time() + 60},
        expires_at=int(time.time()) + 60,
    )
    current = [1_000.0]

    def advancing_time():
        value = current[0]
        current[0] += 0.2
        return value

    monkeypatch.setattr("core.agentic_channel.time.time", advancing_time)

    with pytest.raises(ChannelError, match="deadline_exhausted"):
        server_authority.result(
            command=command,
            payload={"ok": True, "content": b"x" * (7 * 1024 * 1024)},
            expires_at=1_060,
            deadline_at=1_000.8,
        )


def test_legacy_byte_string_has_a_strict_canonical_cap():
    with pytest.raises(ChannelError, match="string_cap_exceeded"):
        _digest({"content": {"$bytes": "A" * (512 * 1024 + 4)}})


def test_raw_tree_depth_is_rejected_before_recursive_encoding(monkeypatch):
    monkeypatch.setattr("core.agentic_channel.MAX_CHANNEL_DEPTH", 4)
    value = "leaf"
    for index in range(5):
        value = {f"level-{index}": value}

    with pytest.raises(ChannelError, match="depth_cap_exceeded"):
        _encode_value(value)


def test_raw_bytes_total_is_rejected_before_base64_allocation(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "core.agentic_channel.MAX_CHANNEL_TOTAL_STRING_BYTES", 32
    )
    monkeypatch.setattr(
        "core.agentic_channel.base64.b64encode",
        lambda value: calls.append(value),
    )

    with pytest.raises(ChannelError, match="total_string_cap_exceeded"):
        _encode_value({"content": b"x" * 100})

    assert calls == []


def test_raw_text_is_rejected_before_tree_copy(monkeypatch):
    monkeypatch.setattr("core.agentic_channel.MAX_CHANNEL_TEXT_BYTES", 8)

    with pytest.raises(ChannelError, match="string_cap_exceeded"):
        _encode_value({"content": "x" * 9})


def test_byte_marker_list_counts_toward_canonical_depth(monkeypatch):
    monkeypatch.setattr("core.agentic_channel.MAX_CHANNEL_DEPTH", 2)

    with pytest.raises(ChannelError, match="depth_cap_exceeded"):
        _digest({"outer": {"$bytes_chunks": []}})


def test_empty_byte_markers_count_toward_raw_and_canonical_nodes(
    monkeypatch
):
    monkeypatch.setattr("core.agentic_channel.MAX_CHANNEL_NODES", 6)

    with pytest.raises(ChannelError, match="node_cap_exceeded"):
        _encode_value([b"", b""])
    with pytest.raises(ChannelError, match="node_cap_exceeded"):
        _digest([
            {"$bytes_chunks": []},
            {"$bytes_chunks": []},
        ])


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


def test_missing_signed_deadline_rejects_before_backend_creation():
    client_auth = EnvelopeAuthority(KEY, SCOPE)
    backends = []
    server = ComputeChannelServer(
        EnvelopeAuthority(KEY, SCOPE),
        lambda **kwargs: backends.append(FakeBackend(**kwargs)),
    )
    command = client_auth.command(
        sequence=1,
        operation="start",
        payload={"task_spec": {}, "timeout_seconds": 60},
        expires_at=int(time.time()) + 60,
    )

    with pytest.raises(ChannelError, match="deadline_missing"):
        server.handle(command)

    assert backends == []


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
        payload={
            "task_spec": {}, "timeout_seconds": 60,
            "deadline_at": time.time() + 60,
        },
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


def test_signed_non_object_result_does_not_consume_sequence():
    client_auth = EnvelopeAuthority(KEY, SCOPE)
    server_auth = EnvelopeAuthority(KEY, SCOPE)
    command = client_auth.command(
        sequence=1,
        operation="inspect_workspace",
        payload={"timeout_seconds": 60, "deadline_at": time.time() + 60},
        expires_at=int(time.time()) + 60,
    )
    result = server_auth.result(
        command=command,
        payload={"ok": True},
        expires_at=int(time.time()) + 60,
    )
    result["payload"] = ["not", "an", "object"]
    result["payload_sha256"] = _digest(result["payload"])
    result["mac"] = server_auth._mac(result)

    with pytest.raises(ChannelError, match="result_not_object"):
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
        payload={
            "task_spec": {}, "timeout_seconds": 60,
            "deadline_at": time.time() + 60,
        },
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
            current_time[0] += 61
            return super().run_python(source, timeout_seconds)

    server = ComputeChannelServer(server_auth, LongRunningBackend)
    client = AuthenticatedComputeBackend(
        authority=client_auth,
        transport=InMemoryComputeTransport(server),
        task_spec={"task_prompt": "task"},
        ttl_seconds=60,
    )

    assert client.start()["ok"] is True
    assert client.run_python("print('done')", 120)["ok"] is True
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
        timeouts = []

        def exchange(
            self, envelope, *, timeout_seconds=None,
            monotonic_deadline=None,
        ):
            self.attempts += 1
            self.timeouts.append(timeout_seconds)
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
    assert transport.timeouts[1] <= transport.timeouts[0]
    assert backends[0].calls == ["start"]
    server.close()


def test_cached_retry_requires_exact_valid_mac_and_unexpired_command():
    client_auth = EnvelopeAuthority(KEY, SCOPE)
    server_auth = EnvelopeAuthority(KEY, SCOPE)
    backends = []

    def factory(**task_spec):
        backend = FakeBackend(**task_spec)
        backends.append(backend)
        return backend

    server = ComputeChannelServer(server_auth, factory)
    command = client_auth.command(
        sequence=1,
        operation="start",
        payload={
            "task_spec": {}, "timeout_seconds": 60,
            "deadline_at": time.time() + 60,
        },
        expires_at=int(time.time()) + 60,
    )
    assert server.handle(command)
    tampered = dict(command)
    tampered["mac"] = "0" * 64

    with pytest.raises(ChannelError, match="cached_command_mismatch"):
        server.handle(tampered)
    with pytest.raises(ChannelError, match="cached_result_expired"):
        server_auth.verify_cached_retry(
            command,
            original=command,
            cache_expires_at=int(command["expires_at"]),
            now=int(command["expires_at"]) + 1,
        )

    assert backends[0].calls == ["start"]
    server.close()


def test_long_command_lost_response_uses_fresh_cached_result_ttl(monkeypatch):
    current_time = [1_000]
    monkeypatch.setattr(
        "core.agentic_channel.time.time", lambda: current_time[0]
    )
    client_auth = EnvelopeAuthority(KEY, SCOPE)
    server_auth = EnvelopeAuthority(KEY, SCOPE)

    class LongBackend(FakeBackend):
        def run_python(self, source, timeout_seconds):
            current_time[0] += 61
            return super().run_python(source, timeout_seconds)

    server = ComputeChannelServer(server_auth, LongBackend)

    class LostResponse:
        attempts = 0

        def exchange(
            self, envelope, *, timeout_seconds=None,
            monotonic_deadline=None,
        ):
            self.attempts += 1
            result = server.handle(envelope)
            if self.attempts == 2:
                raise TimeoutError("long command response lost")
            return result

    transport = LostResponse()
    client = AuthenticatedComputeBackend(
        authority=client_auth,
        transport=transport,
        task_spec={"task_prompt": "task"},
        ttl_seconds=60,
    )

    assert client.start()["ok"] is True
    assert client.run_python("print('done')", 120)["ok"] is True
    assert transport.attempts == 3
    assert server.backend.calls[0] == "start"
    assert server.backend.calls[1][0:2] == ("run_python", "print('done')")
    assert server.backend.calls[1][2] == pytest.approx(120, abs=0.01)


def test_failed_close_retains_backend_and_sequence_for_exact_retry():
    close_attempts = []

    class RetryCloseBackend(FakeBackend):
        def close(self):
            close_attempts.append("close")
            if len(close_attempts) == 1:
                raise RuntimeError("transient cleanup failure")
            super().close()

    client_auth = EnvelopeAuthority(KEY, SCOPE)
    server_auth = EnvelopeAuthority(KEY, SCOPE)
    server = ComputeChannelServer(
        server_auth, lambda **task_spec: RetryCloseBackend(**task_spec)
    )
    start = client_auth.command(
        sequence=1,
        operation="start",
        payload={
            "task_spec": {}, "timeout_seconds": 60,
            "deadline_at": time.time() + 60,
        },
        expires_at=int(time.time()) + 60,
    )
    start_result = server.handle(start)
    assert client_auth.verify_result(start_result, command=start)["ok"] is True
    close = client_auth.command(
        sequence=2,
        operation="close",
        payload={
            "timeout_seconds": 30,
            "deadline_at": time.time() + 30,
        },
        expires_at=int(time.time()) + 60,
    )

    first_result = server.handle(close)
    first_decoded = client_auth.verify_result(first_result, command=close)

    assert first_decoded["ok"] is False
    assert first_decoded["error_type"] == "compute_dispatch_failed"
    assert server.backend is not None
    assert server_auth.expected_sequence == 3
    retry_close = client_auth.command(
        sequence=3,
        operation="close",
        payload={
            "timeout_seconds": 30,
            "deadline_at": time.time() + 30,
        },
        expires_at=int(time.time()) + 60,
    )
    result = server.handle(retry_close)
    decoded = client_auth.verify_result(result, command=retry_close)

    assert decoded["ok"] is True
    assert server.backend is None
    assert server_auth.expected_sequence == 4
    assert close_attempts == ["close", "close"]


def test_pre_dispatch_failure_reuses_exact_pending_sequence():
    server = ComputeChannelServer(
        EnvelopeAuthority(KEY, SCOPE), FakeBackend
    )

    class FailBeforeDispatchOnce:
        envelopes = []
        attempts = 0

        def exchange(
            self, envelope, *, timeout_seconds=None,
            monotonic_deadline=None,
        ):
            self.envelopes.append(dict(envelope))
            self.attempts += 1
            if self.attempts == 1:
                raise TimeoutError("connect failed before dispatch")
            return server.handle(envelope)

    transport = FailBeforeDispatchOnce()
    client = AuthenticatedComputeBackend(
        authority=EnvelopeAuthority(KEY, SCOPE),
        transport=transport,
        task_spec={"task_prompt": "task"},
        max_transport_retries=0,
    )

    with pytest.raises(TimeoutError, match="before dispatch"):
        client.start(10)

    assert client.sequence == 0
    assert server.authority.expected_sequence == 1
    assert client.start(10)["ok"] is True
    assert transport.envelopes[0] == transport.envelopes[1]
    assert transport.envelopes[0]["sequence"] == 1
    assert client.sequence == 1
    assert server.authority.expected_sequence == 2
    client.close()


def test_pending_exchange_blocks_a_different_operation():
    class AlwaysFailsBeforeDispatch:
        attempts = 0

        def exchange(
            self, envelope, *, timeout_seconds=None,
            monotonic_deadline=None,
        ):
            self.attempts += 1
            raise TimeoutError("connect failed before dispatch")

    transport = AlwaysFailsBeforeDispatch()
    client = AuthenticatedComputeBackend(
        authority=EnvelopeAuthority(KEY, SCOPE),
        transport=transport,
        task_spec={"task_prompt": "task"},
        max_transport_retries=0,
    )
    with pytest.raises(TimeoutError):
        client.start(10)

    with pytest.raises(ChannelError, match="state_indeterminate"):
        client.inspect_workspace(10)

    assert transport.attempts == 1
    assert client.sequence == 0


def test_proxy_close_raises_signed_cleanup_failure():
    class RetryCloseBackend(FakeBackend):
        attempts = 0

        def close(self):
            self.attempts += 1
            if self.attempts == 1:
                raise RuntimeError("transient cleanup failure")
            super().close()

    server = ComputeChannelServer(
        EnvelopeAuthority(KEY, SCOPE), RetryCloseBackend
    )
    client = AuthenticatedComputeBackend(
        authority=EnvelopeAuthority(KEY, SCOPE),
        transport=InMemoryComputeTransport(server),
        task_spec={"task_prompt": "task"},
    )

    assert client.start()["ok"] is True
    with pytest.raises(ChannelError, match="compute_dispatch_failed"):
        client.close()

    assert server.backend is not None
    server.close()
    assert server.backend is None


def test_failed_explicit_close_rearms_cleanup_lease():
    cleaned = threading.Event()

    class RetryCloseBackend(FakeBackend):
        attempts = 0

        def close(self):
            self.attempts += 1
            if self.attempts == 1:
                raise RuntimeError("transient cleanup failure")
            super().close()
            cleaned.set()

    server = ComputeChannelServer(
        EnvelopeAuthority(KEY, SCOPE),
        RetryCloseBackend,
        backend_lease_seconds=0.05,
    )
    client = AuthenticatedComputeBackend(
        authority=EnvelopeAuthority(KEY, SCOPE),
        transport=InMemoryComputeTransport(server),
        task_spec={"task_prompt": "task"},
    )

    assert client.start()["ok"] is True
    with pytest.raises(ChannelError, match="compute_dispatch_failed"):
        client.close()

    assert cleaned.wait(timeout=1)
    assert server.backend is None


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
        payload={
            "task_spec": {}, "timeout_seconds": 60,
            "deadline_at": time.time() + 60,
        },
        expires_at=int(time.time()) + 60,
    )

    assert transport.exchange(command)
    assert closed.wait(timeout=1)
    assert server.backend is None


def test_start_cleanup_failure_commits_result_and_lease_retries_cleanup():
    closed = threading.Event()
    close_attempts = []

    class FailingStartBackend(FakeBackend):
        def start(self, timeout_seconds=1200.0):
            raise RuntimeError("start failed")

        def close(self):
            close_attempts.append("close")
            if len(close_attempts) == 1:
                raise RuntimeError("first cleanup failed")
            self.closed = True
            closed.set()

    client_auth = EnvelopeAuthority(KEY, SCOPE)
    server_auth = EnvelopeAuthority(KEY, SCOPE)
    server = ComputeChannelServer(
        server_auth,
        lambda **kwargs: FailingStartBackend(**kwargs),
        backend_lease_seconds=0.01,
    )
    command = client_auth.command(
        sequence=1,
        operation="start",
        payload={
            "task_spec": {},
            "timeout_seconds": 60,
            "deadline_at": time.time() + 60,
        },
        expires_at=int(time.time()) + 60,
    )

    result = server.handle(command)
    decoded = client_auth.verify_result(result, command=command)

    assert decoded["ok"] is False
    assert decoded["error_type"] == "compute_start_cleanup_failed"
    assert server_auth.expected_sequence == 2
    assert closed.wait(timeout=1)
    assert server.backend is None
    assert close_attempts == ["close", "close"]


def test_inspection_and_snapshot_export_share_one_deadline(monkeypatch):
    monotonic = [100.0]
    monkeypatch.setattr(
        "core.agentic_channel.time.monotonic", lambda: monotonic[0]
    )
    client_auth = EnvelopeAuthority(KEY, SCOPE)
    server_auth = EnvelopeAuthority(KEY, SCOPE)
    backend = FakeBackend()

    class TimeAdvancingTransport:
        timeouts = []

        def exchange(
            self, envelope, *, timeout_seconds=None,
            monotonic_deadline=None,
        ):
            self.timeouts.append(timeout_seconds)
            result = server.handle(envelope)
            monotonic[0] += 3.0
            return result

    server = ComputeChannelServer(server_auth, lambda **kwargs: backend)
    transport = TimeAdvancingTransport()
    client = AuthenticatedComputeBackend(
        authority=client_auth,
        transport=transport,
        task_spec={"task_prompt": "task"},
        max_transport_retries=0,
    )
    assert client.start(10)["ok"] is True

    inspected = client.inspect_artifacts(10)

    assert inspected["ok"] is True
    inspect_timeout, export_timeout = transport.timeouts[-2:]
    assert inspect_timeout == pytest.approx(10, abs=0.01)
    assert export_timeout == pytest.approx(7, abs=0.01)
    client.close()


def test_finalize_and_candidate_export_share_one_deadline(monkeypatch):
    current_time = [1_000.0]
    monkeypatch.setattr(
        "core.agentic_channel.time.time", lambda: current_time[0]
    )

    class FinalizeBackend(FakeBackend):
        finalize_timeout = None
        export_timeout = None

        def finalize(
            self, deliverables, summary, timeout_seconds=1200.0
        ):
            self.finalize_timeout = timeout_seconds
            self.terminal = {
                "success": True,
                "text": summary,
                "files": [
                    {"filename": deliverables[0], "content": b"bytes"}
                ],
            }
            current_time[0] += 3.0
            return {"ok": True, "data": {"artifact_count": 1}}

        def best_result(self, timeout_seconds=1200.0):
            self.export_timeout = timeout_seconds
            return self.terminal

    server = ComputeChannelServer(
        EnvelopeAuthority(KEY, SCOPE), FinalizeBackend
    )
    client = AuthenticatedComputeBackend(
        authority=EnvelopeAuthority(KEY, SCOPE),
        transport=InMemoryComputeTransport(server),
        task_spec={"task_prompt": "task"},
    )
    assert client.start(10)["ok"] is True

    result = client.finalize(["report.txt"], "done", 10)

    assert result["ok"] is True
    assert server.backend.finalize_timeout == pytest.approx(10, abs=0.01)
    assert server.backend.export_timeout == pytest.approx(7, abs=0.01)
    client.close()


def test_post_dispatch_result_deadline_commits_failure_and_cleans_backend(
    monkeypatch
):
    current = [1_000.0]
    monkeypatch.setattr("core.agentic_channel.time.time", lambda: current[0])
    client_auth = EnvelopeAuthority(KEY, SCOPE)
    server_auth = EnvelopeAuthority(KEY, SCOPE)
    backend = FakeBackend()

    class ExpiringBackend(FakeBackend):
        def start(self, timeout_seconds=1200.0):
            result = super().start(timeout_seconds)
            current[0] += 2
            return result

    backend = ExpiringBackend()
    server = ComputeChannelServer(server_auth, lambda **kwargs: backend)
    command = client_auth.command(
        sequence=1,
        operation="start",
        payload={
            "task_spec": {},
            "timeout_seconds": 1,
            "deadline_at": current[0] + 1,
        },
        expires_at=int(current[0]) + 60,
    )

    result_envelope = server.handle(command)
    decoded = client_auth.verify_result(result_envelope, command=command)

    assert decoded["ok"] is False
    assert decoded["error_type"] == "post_dispatch_result_failed"
    assert backend.closed is True
    assert server.backend is None
    assert server_auth.expected_sequence == 2