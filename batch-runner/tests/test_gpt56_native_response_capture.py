"""Synthetic provider responses only; no auth/model call or live evidence."""

import hashlib
import json
import os
import socket
import subprocess
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.usefixtures("native_hosted_runner")

import gpt56_native_response_capture as evidence
import gpt56_pilot_wire_receipt as wire
import step2_run_inference as step2
from core import codex_runner
from core.codex_runtime_config import CodexProviderSettings
from scripts import diagnose_codex_foundry_connection as diagnostic
from .test_gpt56_pilot_provider_observation import CANARY, MODEL, UPSTREAM, _body, _post, _upstream, loopback_only


def _response(**changes):
    value = json.loads(_body())
    value.update(model_version="2026-07-09", reasoning={"effort": "max"}, context_window=1_000_000)
    value.update(changes)
    return value


def _payload(value, kind="json"):
    if kind == "json":
        return json.dumps(value, ensure_ascii=False).encode()
    return (b"data: " + json.dumps({"type": "response.created", "response": {"object": "response", "model": MODEL}}).encode()
            + b"\r\n\r\ndata: " + json.dumps({"type": "response.completed", "response": value}).encode() + b"\r\n\r\n")


def _record(monkeypatch, tmp_path, value, *, kind="json", row_changes=None):
    store = evidence.NativeResponseArtifacts(tmp_path, "synthetic-responses")
    body = _payload(value, kind)
    row = {"body": body, "type": "application/json" if kind == "json" else "text/event-stream",
           "headers": {"Set-Cookie": CANARY, "x-echo": CANARY, "x-request-id": "synthetic-request-id"},
           **(row_changes or {})}
    stop = threading.Event()
    with _upstream(monkeypatch, [row]) as (received, _):
        observer = wire._ProviderHTTPObservation(UPSTREAM, 60, artifacts=store)
        observer.stop_runtime = stop.set
        address = ("127.0.0.1", observer.server.server_port)
        try:
            result = _post(observer.base_url)
            if store.reason is not None:
                assert stop.wait(2), "refusal must close the owned runtime"
        finally:
            observer.close()
        assert len(received) == 1
    with socket.socket() as check:
        assert check.connect_ex(address) != 0
    assert not observer.thread.is_alive() and not observer.timer.is_alive()
    return result, observer, store, body


@pytest.mark.parametrize("kind", ["json", "sse"])
def test_complete_raw_response_is_masked_durable_and_hash_bound(monkeypatch, tmp_path, capsys, kind):
    value = _response(metadata={"api_key": CANARY, "access_token": "secret-not-shaped-like-a-token"},
                      other={"text": "Bearer " + CANARY, "url": UPSTREAM})
    result, observer, store, body = _record(monkeypatch, tmp_path, value, kind=kind)
    assert result == (200, body)  # The CLI sees original bytes only after durable validation.
    report = store.report()
    assert report["state"] == "observed" and report["reason"] is None
    assert report["served_model"] == MODEL and report["served_model_version"] == "2026-07-09"
    assert report["reasoning_effort"] == "max" and report["context_tokens"] == 1_000_000
    assert report["context_fields"] == {"context_window": 1_000_000}
    assert report["launch_allowed"] is False
    binding = report["responses"][0]["artifact"]
    path = tmp_path / binding["path"]
    raw = path.read_bytes()
    assert binding["sha256"] == hashlib.sha256(raw).hexdigest() and binding["size"] == len(raw)
    assert path.stat().st_mode & 0o777 == 0o600 and store.root.stat().st_mode & 0o777 == 0o700
    assert path.stat().st_nlink == 1 and not path.is_symlink()
    document = json.loads(raw)
    assert ["Set-Cookie", "[REDACTED]"] in document["headers"]
    assert ["x-request-id", "synthetic-request-id"] in document["headers"]
    assert document["body_utf8"].endswith("\r\n\r\n") is (kind == "sse")
    assert all(secret not in raw.decode() for secret in (CANARY, UPSTREAM, "secret-not-shaped-like-a-token"))
    evidence.verify_artifact_bundle(tmp_path, report)
    public = observer.summary()
    assert public["response_evidence"] == report
    assert public["runtime_caps"]["token_hard_limit_enforced"] is False
    assert step2._bounded_codex_diagnostics({"provider_observation": public})["provider_observation"] == public
    output = capsys.readouterr()
    assert CANARY not in output.out + output.err + json.dumps(public)


@pytest.mark.parametrize("changes,reason", [
    ({"model": None}, "served_model_unverified"),
    ({"model": "gpt-4o"}, "served_model_mismatch"),
    ({"model": "gpt-5.6-sol-fast"}, "served_model_mismatch"),
    ({"model": "gpt-5.6-sol-2026-07-09"}, "served_model_mismatch"),
    ({"reasoning": {}}, "reasoning_effort_unverified"),
    ({"reasoning": {"effort": "high"}}, "reasoning_effort_mismatch"),
    ({"context_window": None}, "context_window_unverified"),
    ({"context_window": 258400}, "context_window_mismatch"),
    ({"context_window": "1000000"}, "context_window_unverified"),
    ({"context_window": True}, "context_window_unverified"),
    ({"modelContextWindow": 258400}, "context_window_unverified"),
])
def test_missing_or_mismatched_response_fields_stop_before_cli_effect(monkeypatch, tmp_path, changes, reason):
    result, observer, store, body = _record(monkeypatch, tmp_path, _response(**changes))
    assert result == (502, b"") and body
    report = store.report()
    assert report["state"] == "unverified" and report["reason"] == reason
    assert len(report["responses"]) == 1
    assert observer.stop_reason == reason
    assert observer.summary()["runtime_caps"]["stop_reason"] == reason
    assert store.rows[0]["artifact"]["sha256"] != evidence.NOT_REPORTED


def test_absent_version_is_not_inferred_from_alias_or_inventory(monkeypatch, tmp_path):
    result, _, store, _ = _record(monkeypatch, tmp_path, _response(model_version=None))
    assert result[0] == 200 and store.report()["served_model_version"] == "not_reported"
    # Version proof is a separate remaining preflight blocker, not inferred here.


def test_raw_store_failure_stops_and_never_leaks_exception_or_body(monkeypatch, tmp_path, capsys):
    def fail(*args):
        raise OSError(CANARY)
    monkeypatch.setattr(evidence, "_write_no_clobber", fail)
    result, observer, store, _ = _record(monkeypatch, tmp_path, _response())
    assert result == (502, b"")
    assert observer.stop_reason == store.report()["reason"] == "native_response_artifact_failed"
    assert store.report()["responses"] == []
    assert list(store.root.iterdir()) == []
    output = capsys.readouterr()
    assert CANARY not in output.out + output.err + json.dumps(observer.summary())


@pytest.mark.parametrize("damage", ["truncated", "encoded", "capture-limit", "two-terminals"])
def test_incomplete_or_uninspectable_response_is_never_delivered(monkeypatch, tmp_path, damage):
    changes = {}
    if damage == "truncated":
        changes["missing"] = 11
    elif damage == "encoded":
        changes["headers"] = {"Content-Encoding": "gzip"}
    elif damage == "capture-limit":
        monkeypatch.setattr(evidence, "MAX_RESPONSE_BYTES", 40)
    elif damage == "two-terminals":
        changes["type"] = "text/event-stream"
        changes["body"] = _payload(_response(), "sse") * 2
    result, observer, store, _ = _record(monkeypatch, tmp_path, _response(), row_changes=changes)
    assert result == (502, b"")
    assert store.report()["state"] == "unverified" and observer.stop_reason in evidence.STOPS


@pytest.mark.parametrize("damage", ["missing", "drift", "symlink", "hardlink", "extra-file"])
def test_artifact_rechecks_reject_post_capture_changes(monkeypatch, tmp_path, damage):
    _, _, store, _ = _record(monkeypatch, tmp_path, _response())
    report = store.report()
    path = tmp_path / report["responses"][0]["artifact"]["path"]
    if damage == "missing":
        path.unlink()
    elif damage == "drift":
        path.write_bytes(path.read_bytes() + b" ")
    elif damage == "symlink":
        saved = tmp_path / "saved.json"
        path.rename(saved)
        path.symlink_to(saved)
    elif damage == "hardlink":
        os.link(path, tmp_path / "saved.json")
    else:
        (store.root / "unlisted.json").write_bytes(b"{}")
    assert store.report()["state"] == "unverified"
    assert store.report()["reason"] == "native_response_artifact_failed"
    with pytest.raises(evidence.ResponseCaptureRefused):
        evidence.verify_artifact_bundle(tmp_path, report)


def test_response_versions_cannot_change_between_calls(monkeypatch, tmp_path):
    store = evidence.NativeResponseArtifacts(tmp_path, "synthetic-responses")
    with _upstream(monkeypatch, [{"body": _payload(_response())},
                                {"body": _payload(_response(model_version="2026-07-10"))}]) as (received, _):
        observer = wire._ProviderHTTPObservation(UPSTREAM, 60, artifacts=store)
        try:
            assert _post(observer.base_url)[0] == 200
            assert _post(observer.base_url) == (502, b"")
        finally:
            observer.close()
        assert len(received) == 2
    assert store.report()["reason"] == "native_response_fields_inconsistent"


def test_unmasked_arbitrary_token_cannot_enter_body_header_or_receipt(tmp_path):
    token = "fake-unshaped-auth-secret-1234567"
    store = evidence.NativeResponseArtifacts(tmp_path, "synthetic-responses")
    response = store.begin(200, [("Content-Type", "application/json"), ("Authorization", token)],
                           [("Authorization", "Bearer " + token)])
    value = _response(output=[{"text": token}], metadata={"password": "another-unshaped-secret"})
    raw = json.dumps(value).replace(token, "".join("\\u%04x" % ord(c) for c in token)).encode()
    for offset in range(0, len(raw), 7):
        response.feed(raw[offset:offset + 7])
    assert response.finish(evidence.response_fields(value), complete=True) is None
    store.seal(1, 1)
    report = store.report()
    artifact = (tmp_path / report["responses"][0]["artifact"]["path"]).read_text()
    assert token not in artifact and "another-unshaped-secret" not in artifact
    assert "\\u0066\\u0061\\u006b\\u0065" not in artifact
    evidence.verify_artifact_bundle(tmp_path, report)


@pytest.mark.parametrize("case", ["valid", "missing-model", "mismatch", "save-failure", "missing-max", "missing-1m"])
def test_real_diagnostic_and_runner_require_shared_response_evidence(monkeypatch, tmp_path, case):
    import openai_codex
    from openai_codex.generated.v2_all import TurnCompletedNotification
    from .test_codex_foundry_connection_probe import _agent_message, _event, _turn, _probe

    value = _response()
    if case == "missing-model":
        value.pop("model")
    elif case == "mismatch":
        value["model"] = "gpt-4o"
    elif case == "missing-max":
        value.pop("reasoning")
    elif case == "missing-1m":
        value.pop("context_window")
    if case == "save-failure":
        def fail(*args):
            raise OSError(CANARY)
        monkeypatch.setattr(evidence, "_write_no_clobber", fail)
    runtimes = []

    class FakeCodex:
        def __init__(self, config):
            self.config, self.closed = config, False
            runtimes.append(self)

        def close(self):
            self.closed = True

        def thread_start(self, **kwargs):
            def stream():
                override = next(item for item in self.config.config_overrides if item.startswith("model_providers.gdpval-foundry.base_url="))
                base_url = json.loads(override.split("=", 1)[1])
                _post(base_url)
                # Even an SDK that says completed cannot override missing HTTP evidence.
                yield _event(TurnCompletedNotification(thread_id="thread-1", turn=_turn([_agent_message("CONNECTED")])))
            return SimpleNamespace(turn=lambda prompt: SimpleNamespace(id="turn-1", stream=stream))

    original_init = codex_runner.CodexAgentRunner.__init__
    def offline_init(self, settings, **kwargs):
        original_init(self, settings, verify_runtime=False, **kwargs)
    monkeypatch.setattr(codex_runner.CodexAgentRunner, "__init__", offline_init)
    monkeypatch.setattr(codex_runner.CodexAgentRunner, "preflight_auth_command", lambda *a: _probe())
    monkeypatch.setattr(codex_runner.CodexAgentRunner, "require_a_usable_auth_command", lambda *a: None)
    monkeypatch.setattr(codex_runner.CodexAgentRunner, "_build_environment", lambda *a: {})
    monkeypatch.setattr(codex_runner, "resolve_run_root_base", lambda: tmp_path / "runtime")
    monkeypatch.setattr(openai_codex, "Codex", FakeCodex)
    settings = CodexProviderSettings(endpoint=UPSTREAM, model=MODEL, reasoning_effort="max", model_context_window=1_000_000)
    with _upstream(monkeypatch, [{"body": _payload(value)}]) as (received, _):
        record = diagnostic.probe(settings, timeout=30, response_artifact_parent=tmp_path)
        assert len(received) == 1
    assert record["schema"] == "codex_foundry_connection/4"
    assert (record["verdict"] == diagnostic.VERDICT_CONNECTED) is (case == "valid")
    proof = record["observed"]["provider_response_evidence"]
    assert proof["state"] == ("observed" if case == "valid" else "unverified")
    if case == "missing-model":
        assert record["observed"]["served_model"] == "not_reported"
    assert runtimes and all(runtime.closed for runtime in runtimes)
    assert not any((tmp_path / "runtime").glob("**/workspace"))
    assert CANARY not in json.dumps(record)


def test_sol_diagnostic_requires_artifact_destination_before_any_effect(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("no SDK/auth effect allowed")
    monkeypatch.setattr(codex_runner, "CodexAgentRunner", forbidden)
    settings = CodexProviderSettings(endpoint=UPSTREAM, model=MODEL)
    result = diagnostic.probe(settings)
    assert result["verdict"] == diagnostic.VERDICT_RESPONSE_EVIDENCE_REFUSED
    assert result["observed"]["provider_response_evidence"]["reason"] == "native_response_artifact_failed"
    assert result["observed"]["turn_sent"] is False


@pytest.mark.parametrize("field,value", [
    ("reason", {"private": CANARY}), ("state", [CANARY]), ("context_fields", CANARY),
    ("context_tokens", True), ("responses", [{"headers": {"Authorization": CANARY}}]),
    ("served_model", "Bearer " + CANARY),
])
def test_public_projection_refuses_malformed_or_private_fields(field, value):
    report = evidence.empty_evidence()
    report[field] = value
    projected = evidence.bounded_evidence(report)
    assert projected == evidence.empty_evidence("native_response_fields_invalid")
    assert CANARY not in json.dumps(projected)


def test_arbitrary_sensitive_header_names_are_masked(tmp_path):
    store = evidence.NativeResponseArtifacts(tmp_path, "synthetic-responses")
    response = store.begin(200, [("x-ms-session-token", "opaque-sensitive-server-value")], [])
    value = _response(metadata={"accessToken": "opaque-body-value"})
    response.feed(_payload(value))
    assert response.finish(evidence.response_fields(value), complete=True) is None
    store.seal(1, 1)
    report = store.report()
    data = (tmp_path / report["responses"][0]["artifact"]["path"]).read_text()
    assert "opaque-sensitive-server-value" not in data and "opaque-body-value" not in data
    evidence.verify_artifact_bundle(tmp_path, report)


@pytest.mark.parametrize("damage", [None, "sha-drift", "unlisted", "missing-receipt"])
def test_actual_workflow_verifies_artifacts_before_upload(tmp_path, damage):
    from .test_codex_foundry_connection_probe import CLEAN_RECORD, _run_redaction_check, _steps

    store = evidence.NativeResponseArtifacts(tmp_path, "codex-foundry-connection-responses")
    response = store.begin(200, [("Set-Cookie", CANARY)], [])
    value = _response()
    response.feed(_payload(value))
    assert response.finish(evidence.response_fields(value), complete=True) is None
    store.seal(1, 1)
    report = store.report()
    record = {**CLEAN_RECORD, "schema": "codex_foundry_connection/4",
              "observed": {**CLEAN_RECORD["observed"], "provider_response_evidence": report}}
    if damage == "sha-drift":
        (tmp_path / report["responses"][0]["artifact"]["path"]).write_text(CANARY)
    elif damage == "unlisted":
        (store.root / "unlisted.json").write_text(CANARY)
    elif damage == "missing-receipt":
        record = CLEAN_RECORD
    result = _run_redaction_check(tmp_path, record)
    assert result.returncode == (0 if damage is None else 1), result.stdout + result.stderr
    assert CANARY not in result.stdout + result.stderr
    upload = _steps()["Keep the record"]
    assert "/tmp/codex-foundry-connection-responses/*.json" in upload["with"]["path"]
    assert "steps.leak_check.conclusion == 'success'" in upload["if"]


@pytest.mark.parametrize("case", ["missing-model", "save-failure"])
def test_pilot_runner_keeps_failure_receipt_and_closes_sdk_child(monkeypatch, tmp_path, case):
    """Real runner/SDK close, harmless Python child; no Rust/auth/provider."""
    from openai_codex.client import CodexClient, CodexConfig
    from .test_gpt56_pilot_wire_receipt import REQUESTED, _start

    observer = wire._TransportObservation(dict(REQUESTED))
    observer.approved_base_url = UPSTREAM
    observer.bind_task_text(CANARY)
    observer.response_artifacts = evidence.NativeResponseArtifacts(tmp_path, "synthetic-responses")
    expected = "served_model_unverified" if case == "missing-model" else "native_response_artifact_failed"
    if case == "save-failure":
        def fail(*args):
            raise OSError(CANARY)
        monkeypatch.setattr(evidence, "_write_no_clobber", fail)
    value = _response(model=None) if case == "missing-model" else _response()
    runner = object.__new__(codex_runner.CodexAgentRunner)
    runner.timeout, runner.cost_ledger = 10, None
    monkeypatch.setattr(codex_runner, "_load_turn_collector", lambda: None)
    provider = SimpleNamespace(base_url=UPSTREAM, provider_id=REQUESTED["provider_id"])
    with _upstream(monkeypatch, [{"body": _payload(value)}]) as (received, _), subprocess.Popen(
        [sys.executable, "-I", "-u", "-c", "import signal; print('ready', flush=True); signal.pause()"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", env={},
    ) as process:
        assert process.stdout.readline() == "ready\n"
        client = CodexClient(CodexConfig())
        client._proc = process  # Never start/initialize a real Codex CLI.
        client._router.route_response = lambda value: "original-response"
        client._coerce_notification = lambda *a: "original-notification"
        codex = SimpleNamespace(_client=client, close=client.close)
        fake = SimpleNamespace(observer=observer, codex=codex, client=client,
                               thread_id="thread-private", turn_id="turn-private")
        observer.configure_provider_observer(provider,
            ('model_providers.gdpval-foundry.base_url=' + json.dumps(UPSTREAM),), timeout=10)

        def open_runtime(workspace, *, pilot_wire_observer):
            assert pilot_wire_observer is observer
            wire.install_runtime_observer(codex, observer)
            observer.bind_provider_runtime(codex)
            return codex

        def run():
            assert _post(observer.provider_capture.base_url) == (502, b"")
            client._coerce_notification("turn/completed", {
                "threadId": fake.thread_id, "turn": {"id": fake.turn_id, "status": "completed"}})
            return SimpleNamespace(final_response="CONNECTED", id=fake.turn_id, usage=None)

        def turn(text):
            client._write_message({"id": "rpc-turn", "method": "turn/start", "params": {
                "threadId": fake.thread_id, "input": [{"type": "text", "text": text}]}})
            client._router.route_response({"id": "rpc-turn", "result": {"turn": {"id": fake.turn_id}}})
            return SimpleNamespace(id=fake.turn_id, run=run)

        def start_thread(*args, **kwargs):
            _start(fake)
            return SimpleNamespace(id=fake.thread_id, turn=turn)

        def collect():
            assert process.poll() is not None and observer.provider_runtime is None
            assert observer.provider_capture.closed and observer.provider_capture.server.socket.fileno() == -1
            return []

        monkeypatch.setattr(runner, "open_runtime", open_runtime)
        monkeypatch.setattr(runner, "start_thread", start_thread)
        try:
            outcome = runner._run_one_turn(workspace=SimpleNamespace(workspace=tmp_path, collect_deliverables=collect),
                task_text=CANARY, experiment_prompt={"system": "private developer text"},
                task_id="synthetic-task", pilot_wire_observer=observer)
            assert outcome.success is False and outcome.error_category == outcome.error == expected
            receipt = observer.finish(success=False, thread_id=outcome.thread_id, turn_id=outcome.turn_id)
            assert receipt["provider_observation"]["response_evidence"]["reason"] == expected
            assert len(received) == 1 and process.wait(timeout=1) is not None
        finally:
            observer.close_provider_observer()
            observer.close_provider_runtime()
            if process.poll() is None:
                process.kill()
                process.wait(timeout=1)


def test_stalled_artifact_write_cannot_hold_deadline_cleanup(monkeypatch, tmp_path):
    blocked, release, stopped = (threading.Event() for _ in range(3))
    original = evidence._write_no_clobber

    def stalled(path, data):
        blocked.set()
        assert release.wait(5)
        original(path, data)

    monkeypatch.setattr(evidence, "_write_no_clobber", stalled)
    store = evidence.NativeResponseArtifacts(tmp_path, "stalled-response")
    with _upstream(monkeypatch, [{"body": _payload(_response())}]) as (received, _):
        observer = wire._ProviderHTTPObservation(UPSTREAM, 0.5, artifacts=store)
        observer.stop_runtime = stopped.set
        results = []

        def client():
            try:
                results.append(_post(observer.base_url))
            except Exception:
                results.append("closed")

        worker = threading.Thread(target=client, daemon=True)
        worker.start()
        try:
            assert blocked.wait(2)
            assert stopped.wait(1.5), "artifact write must not block the SDK deadline cleanup"
            assert observer.stop_reason == wire.NATIVE_DEADLINE_EXCEEDED
            assert observer.closed and store.report()["state"] == "unverified"
            assert store.report()["responses"] == []  # No invented retained hash.
            with pytest.raises(evidence.ResponseCaptureRefused):
                store.verify()
        finally:
            release.set()
            worker.join(5)
            observer.close()
    assert len(received) == 1 and not worker.is_alive()
    assert store.report()["state"] == "unverified"  # Late fsync cannot revive success.
