"""Synthetic caps only: no provider, credential, preparation or launch proof."""

import json
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

import gpt56_pilot_wire_receipt as wire
import step2_run_inference as step2
from core import codex_runner
from gpt56_pilot_runtime_caps_usage import _UsageObservation
from .test_gpt56_pilot_provider_observation import (
    CANARY, MODEL, UPSTREAM, _body, _post, _upstream, loopback_only,
)
from .test_gpt56_pilot_wire_receipt import REQUESTED, _finish, _start, _transport, _turn

TASKS = [f"synthetic-task-{index}" for index in range(5)]


def _usage(inputs, outputs):
    return {"total": {"inputTokens": inputs, "outputTokens": outputs, "totalTokens": inputs + outputs,
                      "cachedInputTokens": inputs, "reasoningOutputTokens": outputs},
            "modelContextWindow": REQUESTED["context_tokens"]}


def _observer(*, budget=None, task=TASKS[0]):
    observer = wire._TransportObservation(dict(REQUESTED))
    observer.approved_base_url = UPSTREAM
    observer.native_budget, observer.native_budget_task = budget, task if budget is not None else None
    caps = wire._native_caps()["per_attempt"]
    owner = SimpleNamespace(failed=False, approved_limits={"model_calls": caps["native_model_calls"],
                            "input_tokens": caps["input_tokens"], "output_tokens": caps["output_tokens"]},
                            wire=SimpleNamespace(document={"requested": dict(REQUESTED)}))
    owner._poison = lambda: setattr(owner, "failed", True)
    observer.caps_usage_observer = _UsageObservation(owner, observer)
    return observer


def _configure(observer, timeout=60):
    provider = SimpleNamespace(base_url=UPSTREAM, provider_id=REQUESTED["provider_id"])
    observer.configure_provider_observer(
        provider, ('model_providers.gdpval-foundry.base_url=' + json.dumps(UPSTREAM),), timeout=timeout)
    return observer.provider_capture


@pytest.mark.parametrize("field", ["input_tokens", "output_tokens"])
@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_reported_token_boundary_keeps_exact_counts_and_stops(monkeypatch, capsys, field, offset):
    observer = _observer()
    capture = _configure(observer)
    fake = _transport(observer)
    limits = wire._native_caps()["per_attempt"]
    inputs = limits[field] + offset if field == "input_tokens" else 7
    outputs = limits[field] + offset if field == "output_tokens" else 3
    stop = threading.Event()
    capture.stop_runtime = stop.set
    expected = (wire.NATIVE_INPUT_CAP_EXCEEDED if field == "input_tokens" else wire.NATIVE_OUTPUT_CAP_EXCEEDED)
    try:
        _start(fake)
        _turn(fake, usage=_usage(inputs, outputs))
        if offset > 0:
            assert stop.wait(1)
            assert observer.cap_stop_reason == expected
        else:
            assert not stop.is_set() and observer.cap_stop_reason is None
        capture.close()
        receipt = _finish(fake, success=offset <= 0)
        verified = observer.caps_usage_observer.verified()
        assert verified["snapshots"] == receipt["usage"]["snapshots"]
        assert observer.invalid is observer.caps_usage_observer.failed is False
    finally:
        capture.close()
    result = receipt["provider_observation"]["runtime_caps"]
    assert result["input_tokens"] == inputs and result["output_tokens"] == outputs
    assert result["input_token_limit"] == 300000 and result["output_token_limit"] == 10000
    assert result["token_hard_limit_enforced"] is False  # Reporting is after provider work.
    assert result["stop_reason"] == (expected if offset > 0 else None)
    assert receipt["provider_observation"]["native_request_count"] == 0
    projected = step2._bounded_codex_diagnostics({"provider_observation": receipt["provider_observation"]})
    assert projected["provider_observation"] == receipt["provider_observation"]
    output = capsys.readouterr()
    assert CANARY not in json.dumps(receipt) + json.dumps(projected) + output.out + output.err


@pytest.mark.parametrize("scope", ["task", "pilot"])
def test_aggregate_caps_reserve_actual_forwards_across_fresh_attempts(monkeypatch, scope):
    budget = wire._NativeRequestBudget(TASKS)
    limit = wire._native_caps()["per_" + scope]["native_model_calls"]
    observations = []
    # All five tasks/four attempts share ONE owner; failure responses still count.
    with _upstream(monkeypatch, [{"body": _body(), "status": 503}] * limit) as (received, timeouts):
        for index in range(limit // 32):
            task = TASKS[index // 4]
            observer = _observer(budget=budget, task=task)
            capture = _configure(observer)
            try:
                for _ in range(32):
                    assert _post(capture.base_url)[0] == 503
            finally:
                capture.close()
            observations.append(capture.summary())
        final = observations[-1]["runtime_caps"]
        assert final["task_requests"] == 128 and final["pilot_requests"] == limit
        assert final["stop_reason"] is None
        # Direct seam invocation exercises defense in depth past arm_task's
        # existing four-attempt guard; it does not authorize a fifth attempt.
        denied = _observer(budget=budget, task=task)
        capture = _configure(denied)
        try:
            assert _post(capture.base_url) == (400, b"")
        finally:
            capture.close()
        result = capture.summary()
    assert len(received) == len(timeouts) == limit
    assert result["native_request_count"] == 0 and result["native_request_blocked_count"] == 1
    expected = wire.NATIVE_TASK_CAP_EXCEEDED if scope == "task" else wire.NATIVE_PILOT_CAP_EXCEEDED
    assert result["runtime_caps"]["stop_reason"] == result["native_request_cap_reason"] == expected
    assert result["runtime_caps"]["pilot_requests"] == limit
    assert observations[0]["runtime_caps"]["pilot_requests"] == 32  # Closed receipts do not float.
    with pytest.raises(wire.PilotWireReceiptRefused):
        budget.require_available(task)
    if scope == "task":
        budget.require_available(TASKS[1])
    else:
        for candidate in TASKS:
            with pytest.raises(wire.PilotWireReceiptRefused):
                budget.require_available(candidate)


@pytest.mark.parametrize("scope", ["task", "pilot"])
def test_aggregate_last_slot_is_atomic_and_failed_connections_are_not_refunded(monkeypatch, scope):
    budget = wire._NativeRequestBudget(TASKS)
    if scope == "pilot":
        for task in TASKS[:-1]:
            for _ in range(128):
                assert budget.reserve(task) is None
    task = TASKS[-1]
    for _ in range(127):
        assert budget.reserve(task) is None
    observers = [_observer(budget=budget, task=task) for _ in range(4)]
    captures = [_configure(observer) for observer in observers]
    calls = []

    def refused(*args, **kwargs):
        calls.append(1)
        raise OSError(CANARY)

    monkeypatch.setattr(wire, "HTTPSConnection", refused)
    barrier = threading.Barrier(4)

    def request(capture):
        barrier.wait(timeout=2)
        return _post(capture.base_url)

    try:
        with ThreadPoolExecutor(max_workers=4) as executor:
            replies = list(executor.map(request, captures))
    finally:
        for capture in captures:
            capture.close()
    assert len(calls) == 1 and sorted(code for code, _body in replies) == [400, 400, 400, 502]
    assert budget.snapshot(task) == {"task_requests": 128, "pilot_requests": 128 if scope == "task" else 640}
    assert sum(capture.summary()["native_request_count"] for capture in captures) == 1


def test_attempt_deadline_uses_the_draft_not_a_larger_runner_timeout(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(wire.time, "monotonic", lambda: clock[0])
    with _upstream(monkeypatch, [{"body": _body()}]) as (received, timeouts):
        capture = wire._ProviderHTTPObservation(UPSTREAM, 3600)
        stop = threading.Event()
        capture.stop_runtime = stop.set
        try:
            assert capture.deadline == 2800.0 and capture.timeout == 1800
            clock[0] = 2799.0
            assert _post(capture.base_url)[0] == 200
            assert capture.stop_reason is None
            clock[0] = 2800.0
            capture.check_deadline()
            assert stop.wait(1)
            assert capture.closed and not capture.thread.is_alive()
        finally:
            capture.close()
    assert len(received) == 1 and timeouts == [1.0]
    result = capture.summary()["runtime_caps"]
    assert result["wall_seconds_limit"] == result["effective_wall_seconds"] == 1800
    assert result["stop_reason"] == wire.NATIVE_DEADLINE_EXCEEDED


@pytest.mark.parametrize("reason", [wire.NATIVE_INPUT_CAP_EXCEEDED, wire.NATIVE_OUTPUT_CAP_EXCEEDED,
                                  wire.NATIVE_DEADLINE_EXCEEDED, wire.NATIVE_TASK_CAP_EXCEEDED,
                                  wire.NATIVE_PILOT_CAP_EXCEEDED, wire.NATIVE_USAGE_UNVERIFIED])
def test_cap_stop_closes_real_sdk_child_before_receipt_and_rejects_raced_success(monkeypatch, tmp_path, capsys, reason):
    """Installed SDK.close on harmless child; provider, turns and host are synthetic."""
    from openai_codex.client import CodexClient, CodexConfig

    budget = wire._NativeRequestBudget(TASKS)
    task = TASKS[-1]
    if reason in (wire.NATIVE_TASK_CAP_EXCEEDED, wire.NATIVE_PILOT_CAP_EXCEEDED):
        for identity in (TASKS if reason == wire.NATIVE_PILOT_CAP_EXCEEDED else [task]):
            for _ in range(128):
                assert budget.reserve(identity) is None
    observer = _observer(budget=budget, task=task)
    observer.bind_task_text(CANARY)
    runner = object.__new__(codex_runner.CodexAgentRunner)
    runner.timeout, runner.cost_ledger = 5, None
    monkeypatch.setattr(codex_runner, "_load_turn_collector", lambda: None)
    capture = _configure(observer)
    with subprocess.Popen([sys.executable, "-I", "-u", "-c",
                           "import signal; print('ready', flush=True); signal.pause()"],
                          stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True, encoding="utf-8", env={}) as process:
        assert process.stdout.readline() == "ready\n"
        client = CodexClient(CodexConfig())
        client._proc = process
        client._router.route_response = lambda _message: "original-response"
        client._coerce_notification = lambda *_args: "original-notification"
        codex = SimpleNamespace(_client=client, close=client.close)
        fake = SimpleNamespace(observer=observer, client=client, codex=codex,
                               thread_id="thread-private", turn_id="turn-private")

        def open_runtime(_workspace, *, pilot_wire_observer):
            assert pilot_wire_observer is observer
            wire.install_runtime_observer(codex, observer)
            observer.bind_provider_runtime(codex)
            return codex

        def run_turn():
            if reason in (wire.NATIVE_INPUT_CAP_EXCEEDED, wire.NATIVE_OUTPUT_CAP_EXCEEDED):
                usage = _usage(300001 if reason == wire.NATIVE_INPUT_CAP_EXCEEDED else 7,
                               10001 if reason == wire.NATIVE_OUTPUT_CAP_EXCEEDED else 3)
                client._coerce_notification("thread/tokenUsage/updated", {
                    "threadId": fake.thread_id, "turnId": fake.turn_id, "tokenUsage": usage})
            elif reason == wire.NATIVE_DEADLINE_EXCEEDED:
                # Drive the installed watchdog, not an invented timeout result.
                monkeypatch.setattr(wire.time, "monotonic", lambda: capture.deadline)
                capture.check_deadline()
                assert process.wait(timeout=2) is not None
            elif reason in (wire.NATIVE_TASK_CAP_EXCEEDED, wire.NATIVE_PILOT_CAP_EXCEEDED):
                assert _post(capture.base_url) == (400, b"")
            client._coerce_notification("turn/completed", {
                "threadId": fake.thread_id, "turn": {"id": fake.turn_id, "status": "completed"}})
            return SimpleNamespace(final_response=CANARY, id=fake.turn_id, usage=None)

        def turn(text):
            client._write_message({"id": "rpc-turn", "method": "turn/start", "params": {
                "threadId": fake.thread_id, "input": [{"type": "text", "text": text}]}})
            client._router.route_response({"id": "rpc-turn", "result": {"turn": {"id": fake.turn_id}}})
            return SimpleNamespace(id=fake.turn_id, run=run_turn)

        def start_thread(*_args, **_kwargs):
            _start(fake)
            return SimpleNamespace(id=fake.thread_id, turn=turn)

        def collect():
            assert capture.closed and not capture.thread.is_alive()
            assert capture.server.socket.fileno() == -1 and process.poll() is not None
            assert observer.provider_runtime is None
            return []

        monkeypatch.setattr(runner, "open_runtime", open_runtime)
        monkeypatch.setattr(runner, "start_thread", start_thread)
        monkeypatch.setattr(wire, "HTTPSConnection", lambda *_args, **_kwargs: pytest.fail("unexpected_upstream"))
        workspace = SimpleNamespace(workspace=tmp_path, collect_deliverables=collect)
        try:
            outcome = runner._run_one_turn(workspace=workspace, task_text=CANARY,
                experiment_prompt={"system": "private developer text"}, task_id=task, pilot_wire_observer=observer)
            assert not outcome.success and outcome.text == "" and outcome.error == outcome.error_category == reason
            receipt = observer.finish(success=False, thread_id=outcome.thread_id, turn_id=outcome.turn_id)
            usage = observer.caps_usage_observer.verified()
        finally:
            observer.close_provider_observer()
            observer.close_provider_runtime()
            if process.poll() is None:
                process.kill()
                process.wait(timeout=1)
    result = receipt["provider_observation"]
    assert result["runtime_caps"]["stop_reason"] == reason
    assert usage["threshold_observation"] == reason + "_usage_may_be_partial"
    assert step2.infra_retry_category({"status": "error", "observability": {"error_category": reason}}) is None
    assert step2._bounded_codex_diagnostics({"provider_observation": result}) == {"provider_observation": result}
    output = capsys.readouterr()
    assert all(value not in json.dumps(receipt) + output.out + output.err
               for value in (CANARY, UPSTREAM, "Bearer", capture.route))


def test_watchdog_expires_without_any_http_request(monkeypatch):
    capture = wire._ProviderHTTPObservation(UPSTREAM, 0.05)
    stop = threading.Event()
    capture.stop_runtime = stop.set
    try:
        assert stop.wait(1)
        assert capture.closed and capture.requests == 0 and capture.stop_reason == wire.NATIVE_DEADLINE_EXCEEDED
        assert capture.server.socket.fileno() == -1
    finally:
        capture.close()


@pytest.mark.parametrize("field", ["input_tokens", "output_tokens"])
def test_late_over_limit_usage_cannot_bypass_a_closed_observer(field):
    observer = _observer()
    capture = _configure(observer)
    fake = _transport(observer)
    try:
        _start(fake)
        capture.close()
        frozen = capture.summary()
        with pytest.raises(wire.PilotWireReceiptRefused, match="^pilot_wire_receipt_refused$"):
            _turn(fake, usage=_usage(300001 if field == "input_tokens" else 7,
                                    10001 if field == "output_tokens" else 3))
        assert observer.invalid and observer.caps_usage_observer.failed
        assert capture.summary() == frozen
        with pytest.raises(wire.PilotWireReceiptRefused):
            _finish(fake)
    finally:
        capture.close()


@pytest.mark.parametrize("damage", ["limit", "digest", "unknown_reason", "hard_claim", "task_total",
                                   "pilot_total", "token_bool", "hidden_overage", "false_exceeded", "extra"])
def test_runtime_cap_projection_excludes_unverified_values_and_secret_canaries(monkeypatch, capsys, damage):
    capture = _configure(_observer(budget=wire._NativeRequestBudget(TASKS)))
    capture.close()
    raw = capture.summary()
    caps = raw["runtime_caps"]
    if damage == "limit":
        caps["input_token_limit"] += 1
    elif damage == "digest":
        caps["sha256"] = "0" * 64
    elif damage == "unknown_reason":
        caps["stop_reason"] = CANARY
    elif damage == "hard_claim":
        caps["token_hard_limit_enforced"] = True
    elif damage == "task_total":
        caps["task_requests"] = 129
    elif damage == "pilot_total":
        caps["pilot_requests"] = 641
    elif damage == "token_bool":
        caps["input_tokens"] = True
    elif damage == "hidden_overage":
        caps.update(input_tokens=300001, output_tokens=0)
    elif damage == "false_exceeded":
        caps.update(input_tokens=300000, output_tokens=0, stop_reason=wire.NATIVE_INPUT_CAP_EXCEEDED)
    else:
        caps["private"] = CANARY
    projected = step2._bounded_codex_diagnostics({"provider_observation": raw})
    assert projected == {"provider_observation": wire._provider_summary("invalid_observation")}
    output = capsys.readouterr()
    assert CANARY not in json.dumps(projected) + output.out + output.err
