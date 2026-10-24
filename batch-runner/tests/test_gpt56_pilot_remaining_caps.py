"""Synthetic caps only: no provider, credential, preparation or launch proof."""

import json
import signal
import subprocess
import sys
import threading
import time
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


@pytest.mark.parametrize("case", ["ready", "stuck", "term_ignored", "late_return", "already_expired",
                                 "startup_error", "existing_alarm", "worker_thread"])
def test_startup_deadline_supervises_real_sdk_initialization(monkeypatch, tmp_path, capsys, case):
    """Real SDK initialize/cleanup on a local JSON-RPC child; no Rust/provider/auth."""
    import openai_codex
    from openai_codex.client import CodexClient, CodexConfig
    import gpt56_pilot_native_result_host as native

    before_handler = signal.getsignal(signal.SIGALRM)
    assert signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)
    budget = wire._NativeRequestBudget(TASKS)
    observer = _observer(budget=budget)
    observer.bind_task_text(CANARY)
    session = object.__new__(wire.PilotWireReceiptSession)
    session.native_budget, session.active = budget, {TASKS[0]: observer}
    host = SimpleNamespace()

    def checked_host(value):
        assert value is session
        return host

    monkeypatch.setattr(native, "native_result_host_for", checked_host)
    runner = object.__new__(codex_runner.CodexAgentRunner)
    runner.run_id = codex_runner.PilotInputCapture.RUN_ID
    runner.pilot_wire_receipts, runner.cost_ledger = session, None
    runner.timeout = 0.5 if case in ("stuck", "term_ignored") else 1800
    runner.codex_bin = "unused-by-synthetic-launch-override"
    overrides = ('model_providers.gdpval-foundry.base_url=' + json.dumps(UPSTREAM),)
    runner.provider = SimpleNamespace(base_url=UPSTREAM, provider_id=REQUESTED["provider_id"],
                                      config_overrides=lambda: overrides)
    auth_calls, processes, clients, initialize_calls, effects = [], [], [], [], []
    runner.require_a_usable_auth_command = lambda _workspace: auth_calls.append("synthetic-auth-boundary")
    runner._build_environment = lambda _workspace: {}

    def forbidden(*_args, **_kwargs):
        effects.append("forbidden")
        raise AssertionError("startup must not start a thread/turn, reserve a call, or collect files")

    runner.start_thread = runner.resume_thread = runner._reserve_call = forbidden
    workspace = SimpleNamespace(workspace=tmp_path, collect_deliverables=forbidden)
    monkeypatch.setattr(wire, "HTTPSConnection", forbidden)
    # Codex itself, its JSON-RPC initializer and its close method are unchanged.
    # Only the CLI process is substituted, with no credentials or private input.
    child = (
        "import json, signal, sys\n"
        + ("signal.signal(signal.SIGTERM, signal.SIG_IGN)\n" if case == "term_ignored" else "")
        + "request = json.loads(sys.stdin.readline())\nassert request['method'] == 'initialize'\n"
        + ("signal.pause()\n" if case in ("stuck", "term_ignored") else
           "print(json.dumps({'id':request['id'],'result':{'userAgent':'fixture/0.147.0',"
           "'serverInfo':{'name':'fixture','version':'0.147.0'}}}), flush=True)\n"
           "for line in sys.stdin:\n assert json.loads(line)['method'] == 'initialized'\n")
    )
    clock = [1000.0]
    if case in ("late_return", "already_expired"):
        monkeypatch.setattr(wire.time, "monotonic", lambda: clock[0])

    def config(**kwargs):
        assert kwargs["env"] == {} and kwargs["cwd"] == str(tmp_path)
        value = CodexConfig(**kwargs, launch_args_override=(sys.executable, "-I", "-u", "-c", child))
        if case == "already_expired":
            clock[0] = observer.provider_capture.deadline
        return value

    real_start, real_initialize, real_codex = CodexClient.start, CodexClient.initialize, openai_codex.Codex

    def start(client):
        real_start(client)
        clients.append(client)
        processes.append(client._proc)

    def initialize(client):
        initialize_calls.append("initialize")
        if case == "startup_error":
            raise ValueError(CANARY)
        return real_initialize(client)

    def late_return(config):
        value = real_codex(config)
        clock[0] = observer.provider_capture.deadline
        return value

    monkeypatch.setattr("openai_codex.client.CodexConfig", config)
    monkeypatch.setattr(CodexClient, "start", start)
    monkeypatch.setattr(CodexClient, "initialize", initialize)
    if case == "late_return":
        monkeypatch.setattr(openai_codex, "Codex", late_return)
    started = time.perf_counter()
    try:
        if case in ("stuck", "term_ignored", "late_return", "already_expired"):
            outcome = runner._run_one_turn(workspace=workspace, task_text=CANARY, experiment_prompt=None,
                task_id=TASKS[0], pilot_wire_observer=observer, pilot_host_witness=object())
            assert not outcome.success and outcome.text == ""
            assert outcome.error == outcome.error_category == wire.NATIVE_DEADLINE_EXCEEDED
            assert outcome.thread_id is outcome.turn_id is None
            assert observer.provider_capture.closed and not observer.provider_capture.thread.is_alive()
            assert observer.provider_capture.server.socket.fileno() == -1
            assert all(process.poll() is not None for process in processes)
            receipt = observer.finish(success=False, thread_id=None, turn_id=None)
            usage = observer.caps_usage_observer.verified()
            assert receipt["scope"] == "codex_app_server_startup_deadline_before_thread"
            assert receipt["requests"] == {} and receipt["app_server_settings"] is None
            assert receipt["correlation"] == {"thread_id_sha256": None, "turn_id_sha256": None, "status": None}
            assert receipt["usage"]["state"] == "not_available" and receipt["usage"]["snapshots"] == []
            assert usage["snapshots"] == [] and usage["threshold_observation"] == (
                wire.NATIVE_DEADLINE_EXCEEDED + "_usage_may_be_partial")
            observed = receipt["provider_observation"]
            assert observed["native_request_count"] == 0 and observed["served_model"] is None
            caps = observed["runtime_caps"]
            assert caps["stop_reason"] == wire.NATIVE_DEADLINE_EXCEEDED
            assert caps["input_tokens"] is caps["output_tokens"] is None
            assert caps["wall_seconds_limit"] == 1800 and caps["effective_wall_seconds"] == runner.timeout
            assert caps["task_requests"] == caps["pilot_requests"] == 0
            assert caps["token_hard_limit_enforced"] is False
            assert step2._bounded_codex_diagnostics({"provider_observation": observed}) == {"provider_observation": observed}
            assert step2.infra_retry_category({"status": "error", "observability": {
                "error_category": outcome.error_category}}) is None
            output = capsys.readouterr()
            assert all(secret not in json.dumps(receipt) + json.dumps(usage) + output.out + output.err
                       for secret in (CANARY, UPSTREAM, "Bearer", str(tmp_path), observer.provider_capture.route))
            assert len(processes) == len(initialize_calls) == (0 if case == "already_expired" else 1)
        elif case == "ready":
            codex = runner.open_runtime(workspace, pilot_wire_observer=observer)
            assert type(codex) is real_codex and codex.metadata.serverInfo.version == "0.147.0"
            assert observer.installed and observer.startup_attempted and not observer.startup_timed_out
            assert observer.provider_runtime is codex and observer.cap_stop_reason is None
            assert observer.provider_capture.timeout == 1800
            assert 0 < observer.provider_capture.remaining() <= 1800
            observer.close_provider_runtime()
            observer.close_provider_observer()
        elif case == "startup_error":
            with pytest.raises(ValueError) as raised:
                runner.open_runtime(workspace, pilot_wire_observer=observer)
            assert raised.value.args == (CANARY,)
            assert not observer.startup_timed_out and observer.cap_stop_reason is None
            with pytest.raises(wire.PilotWireReceiptRefused):
                observer.finish(success=False, thread_id=None, turn_id=None)
        elif case == "existing_alarm":
            signal.setitimer(signal.ITIMER_REAL, 30)
            try:
                with pytest.raises(wire.PilotWireReceiptRefused):
                    runner.open_runtime(workspace, pilot_wire_observer=observer)
                assert signal.getsignal(signal.SIGALRM) == before_handler
                assert signal.getitimer(signal.ITIMER_REAL)[0] > 0
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0.0)
            assert auth_calls == [] and observer.provider_capture is None
        else:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(runner.open_runtime, workspace, pilot_wire_observer=observer)
                with pytest.raises(wire.PilotWireReceiptRefused):
                    future.result(timeout=2)
            assert auth_calls == [] and observer.provider_capture is None
        assert signal.getsignal(signal.SIGALRM) == before_handler
        assert signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)
        assert effects == [] and all(process.poll() is not None for process in processes)
        assert all(client._proc is None and not client._reader_thread.is_alive()
                   and not client._stderr_thread.is_alive() for client in clients)
        assert time.perf_counter() - started < 5  # Includes the SDK's existing 2s TERM grace.
    finally:
        observer.close_provider_runtime()
        observer.close_provider_observer()
        for process in processes:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=1)
            for stream in (process.stdin, process.stdout, process.stderr):
                stream.close()


@pytest.mark.parametrize("damage", ["not_started", "not_expired", "installed", "requests", "native_request",
                                   "thread", "usage", "success"])
def test_empty_startup_receipt_cannot_bypass_the_existing_wire_guards(monkeypatch, damage):
    clock = [1000.0]
    monkeypatch.setattr(wire.time, "monotonic", lambda: clock[0])
    observer = _observer()
    capture = _configure(observer, timeout=1800)
    try:
        with pytest.raises(TimeoutError, match="^native_attempt_deadline_exceeded$"):
            with observer.supervise_provider_startup():
                clock[0] = capture.deadline
    finally:
        capture.close()
    if damage == "not_started":
        observer.startup_attempted = False
    elif damage == "not_expired":
        observer.startup_timed_out = False
    elif damage == "installed":
        observer.installed = True
    elif damage == "requests":
        observer.requests["thread/start"] = {"request_id_sha256": "a" * 64}
    elif damage == "native_request":
        capture.requests = 1
    elif damage == "thread":
        observer.thread = "a" * 64
    elif damage == "usage":
        observer.usage.append({"native": _usage(1, 1)})
    with pytest.raises(wire.PilotWireReceiptRefused):
        observer.finish(success=damage == "success", thread_id=None, turn_id=None)


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
        malformed = capture.summary()
        malformed.update(native_request_count=32, native_request_blocked_count=1,
                         native_request_cap_reason=[CANARY])
        assert wire.bounded_provider_observation(malformed) == wire._provider_summary("invalid_observation")
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
