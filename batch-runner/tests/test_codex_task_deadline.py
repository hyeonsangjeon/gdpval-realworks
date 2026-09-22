"""Cumulative cell time through the real retry/runner path, with no provider."""

from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

# Import real classes before guards; never replace a type with a function.
import step8_grade as step8
import step1_prepare_tasks as step1
import step2_run_inference as step2
import gpt54_comparison_preflight as comparison
import gpt56_sol_codex_pilot_preflight as pilot
import gpt56_pilot_identity_plan as identity
from core import azure_ai_clients, codex_azure_token, codex_runner
from core.codex_runtime_config import CodexProviderSettings
from core.codex_task_deadline import (
    ATTEMPT_SECONDS, ATTEMPTS_EXHAUSTED, EXHAUSTED, STATE_REFUSED, TOTAL_SECONDS,
    CodexTaskDeadlineControl, CodexTaskDeadlineStore, TaskDeadlineRefused,
    validate_deadline_execution,
)
from core.cost_receipts import (
    BUCKET_PROBLEM_SOLVING, REASON_CALL_REACHABILITY_UNKNOWN, CostReceiptLedger,
)
from core.executor import TaskExecutor
from core.experiment_config import ExperimentConfig
from .test_a_refused_turn_still_reports_what_it_spent import (
    _usage_event, _turn_event, _failed_turn,
)

ROOT = Path(__file__).resolve().parents[2]
TASK = "02aa1805-c658-4069-8a6a-02dec146063a"
TASK2 = "0112fc9b-c3b2-4084-8993-5a4abb1f54f1"
CONDITION = {"name": "synthetic budget cell", "model": {"provider": "azure", "deployment": "test-model"},
             "prompt": {"system": "Synthetic control-flow test."}}
SETTINGS = CodexProviderSettings(
    endpoint="https://example-account.openai.azure.com/openai/v1/", model="test-model",
)


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    calls = []

    def forbidden(*args, **kwargs):
        calls.append("forbidden boundary")
        raise AssertionError("deadline regression crossed a live boundary")

    for name in ("Popen", "run", "check_call", "check_output"):
        monkeypatch.setattr(subprocess, name, forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    monkeypatch.setattr(step2.time, "sleep", forbidden)
    for constructor in (azure_ai_clients.AzureAIClientFactory, azure_ai_clients.OpenAI,
                        azure_ai_clients.AzureOpenAI, azure_ai_clients.DefaultAzureCredential):
        monkeypatch.setattr(constructor, "__init__", forbidden)
    monkeypatch.setattr(codex_azure_token, "acquire_token", forbidden)
    monkeypatch.setattr(codex_azure_token, "get_bearer_token_provider", forbidden)
    monkeypatch.setattr(azure_ai_clients, "get_bearer_token_provider", forbidden)
    monkeypatch.setattr(step8.Grader, "__init__", forbidden)
    monkeypatch.setattr(step8, "RubricLoader", forbidden)
    monkeypatch.setattr(codex_runner, "require_pinned_runtime", lambda: None)
    monkeypatch.setattr(codex_runner, "_descendant_pids", lambda _: set())
    monkeypatch.setattr(codex_runner, "sweep_orphans", lambda _: ())
    yield calls
    assert calls == []


class Clock:
    def __init__(self):
        self.now = 1_000_000.0
        self.waits = []

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds

    def sleep(self, seconds):
        self.waits.append(seconds)
        self.advance(seconds)


@pytest.fixture
def host(monkeypatch):
    # State cannot live under /tmp: that is a real Codex writable carve-out.
    # Only synthetic test-owned files are created and removed in this directory.
    with tempfile.TemporaryDirectory(prefix=".deadline-test-", dir=ROOT) as directory:
        root = Path(directory)
        monkeypatch.setenv("GDPVAL_CODEX_RUN_ROOT", str(root / "agent-work"))
        monkeypatch.setenv("TMPDIR", str(root / "agent-temp"))
        yield root


def store_at(host, clock, *, condition="B", repetition=1, initialize=True, name="state", **overrides):
    options = dict(run_id="offline-cell-run", experiment_id="exp_deadline_test",
                   condition_key="condition_a", control=CodexTaskDeadlineControl(condition, repetition),
                   task_ids=[TASK, TASK2], prepared_fingerprint="a" * 64,
                   initialize=initialize, clock=clock)
    options.update(overrides)
    return CodexTaskDeadlineStore(host / name, **options)


class Runtime:
    """SDK-shaped stream and worker. Join advances fake time, never sleeps."""

    def __init__(self, monkeypatch, clock, scripts):
        self.clock, self.scripts = clock, list(scripts)
        self.calls, self.joins, self.workspaces = [], [], []
        self.current = None
        self.interrupts = 0
        outer = self

        def open_runtime(runner, workspace):
            outer.workspaces.append(workspace)
            outer.workspace = workspace
            return SimpleNamespace(close=lambda: None)

        def start_thread(runner, client, workspace, **kwargs):
            return SimpleNamespace(id="synthetic-thread", turn=outer.turn)

        def collect(events, **kwargs):
            usage = None
            for event in events:
                if event.method == "thread/tokenUsage/updated":
                    usage = event.payload.token_usage
                elif event.method == "turn/completed" and event.payload.turn.error:
                    raise RuntimeError("HTTP 429 Too Many Requests")
            return SimpleNamespace(id="synthetic-turn", final_response="synthetic result", usage=usage)

        class Worker:
            def __init__(self, *, target, **kwargs):
                self.target, self.remaining = target, outer.current["seconds"]
                self.joined = False

            def start(self):
                self.target()

            def join(self, seconds):
                outer.joins.append(seconds)
                if not self.joined:
                    elapsed = min(self.remaining, seconds)
                    outer.clock.advance(elapsed)
                    self.remaining -= elapsed
                    self.joined = True

            def is_alive(self):
                return self.remaining > 0

        monkeypatch.setattr(codex_runner.CodexAgentRunner, "open_runtime", open_runtime)
        monkeypatch.setattr(codex_runner.CodexAgentRunner, "start_thread", start_thread)
        monkeypatch.setattr(codex_runner, "_load_turn_collector", lambda: collect)
        monkeypatch.setattr(codex_runner, "threading", SimpleNamespace(Thread=Worker))

    def turn(self, text):
        self.current = self.scripts.pop(0)
        self.calls.append(self.current)

        def stream():
            (self.workspace.workspace / "partial.txt").write_bytes(b"synthetic partial")
            yield _usage_event(input_tokens=17, output_tokens=3)
            if self.current.get("rate_limited"):
                yield _turn_event(_failed_turn())

        def interrupt():
            self.interrupts += 1

        return SimpleNamespace(id="synthetic-turn", stream=stream, interrupt=interrupt)


def executor_for(store=None, ledger=None):
    return TaskExecutor(
        mode="codex_foundry", timeout=ATTEMPT_SECONDS,
        codex_options={"provider_settings": SETTINGS, **({"task_deadline_store": store} if store else {})},
        codex_cost_ledger=ledger, run_id="offline-cell-run", condition_name="condition_a",
    )


def execute(executor, host, task=TASK):
    return step2._execute_single_task(
        {"task_id": task, "instruction": "Synthetic task; not benchmark input.", "reference_files": [],
         "needs_files": False}, CONDITION, executor, "codex_foundry", None, SETTINGS.model,
        run_id="offline-cell-run", condition_name="condition_a", upload_root=host / "upload",
    )


@pytest.mark.parametrize("condition", ["B", "C"])
def test_cumulative_task_deadline_retry_and_process_resume_do_not_reset(host, monkeypatch, condition):
    clock = Clock()
    store = store_at(host, clock, condition=condition)
    ledger = CostReceiptLedger(host / "cost.sqlite", run_id="offline-cell-run")
    try:
        runtime = Runtime(monkeypatch, clock, [{"seconds": 300, "rate_limited": True}, {"seconds": 10}])
        executor = executor_for(store, ledger)
        deadline = store.for_task(TASK)

        def interrupted(index):
            if index:
                raise InterruptedError("synthetic process interruption during recovery")
            return execute(executor, host)

        with pytest.raises(InterruptedError):
            step2.run_with_infra_retries(interrupted, max_attempts=4, task_deadline=deadline, sleep=clock.sleep)
        expiry = deadline.as_record()["expires_unix"]
        assert clock.waits == [60.0]
        assert deadline.as_record()["wait_seconds"] == 60.0
        retained = runtime.workspaces[0].workspace / "partial.txt"
        assert retained.read_bytes() == b"synthetic partial"
        store.close()
        clock.advance(600)  # downtime belongs to the same budget
        store = store_at(host, clock, condition=condition, initialize=False)
        executor = executor_for(store, ledger)
        result = step2.run_with_infra_retries(
            lambda _: execute(executor, host), max_attempts=4,
            task_deadline=store.for_task(TASK), sleep=clock.sleep,
        )
        record = result["observability"]["task_deadline"]
        assert result["status"] == "success"
        assert record["expires_unix"] == expiry
        assert record["remaining_seconds"] == TOTAL_SECONDS - 970
        assert record["attempts_admitted"] == 2
        assert retained.read_bytes() == b"synthetic partial"
        assert len(ledger.calls_for(TASK, bucket=BUCKET_PROBLEM_SOLVING)) == 2
        assert len({row["call_id"] for row in ledger.calls_for(TASK, bucket=BUCKET_PROBLEM_SOLVING)}) == 2
    finally:
        store.close()
        ledger.close()


def test_cumulative_task_deadline_bounds_native_join_retains_partials_and_usage(host, monkeypatch):
    clock = Clock()
    store = store_at(host, clock)
    ledger = CostReceiptLedger(host / "cost.sqlite", run_id="offline-cell-run")
    try:
        deadline = store.for_task(TASK)
        assert deadline.remaining_seconds() == TOTAL_SECONDS
        clock.advance(TOTAL_SECONDS - 17)
        runtime = Runtime(monkeypatch, clock, [{"seconds": 1000}])
        executor = executor_for(store, ledger)
        result = execute(executor, host)
        assert result["status"] == "error"
        assert result["observability"]["error_category"] == EXHAUSTED
        assert runtime.joins == [17, 0]
        assert runtime.interrupts == 1
        assert (runtime.workspaces[0].workspace / "partial.txt").read_bytes() == b"synthetic partial"
        record = result["observability"]["task_deadline"]
        assert record["remaining_seconds"] == 0 and record["retained_attempts"] == 1
        assert str(host) not in json.dumps(record)
        receipt = ledger.receipt_for(TASK, BUCKET_PROBLEM_SOLVING)
        assert receipt.status == "partial"
        assert REASON_CALL_REACHABILITY_UNKNOWN in receipt.missing_reasons
        assert ledger.calls_for(TASK, bucket=BUCKET_PROBLEM_SOLVING)[0]["input_tokens"] == 17
        again = execute(executor, host)
        assert again["observability"]["error_category"] == EXHAUSTED
        assert len(runtime.calls) == 1
        assert step2._get_failed_task_ids({"results": [again]}) == []
    finally:
        store.close()
        ledger.close()


def test_cumulative_task_deadline_backoff_cannot_sleep_through_expiry(host, monkeypatch):
    clock = Clock()
    store = store_at(host, clock)
    try:
        deadline = store.for_task(TASK)
        deadline.remaining_seconds()
        clock.advance(TOTAL_SECONDS - 25)
        runtime = Runtime(monkeypatch, clock, [{"seconds": 5, "rate_limited": True}])
        executor = executor_for(store)
        result = step2.run_with_infra_retries(
            lambda _: execute(executor, host), max_attempts=4, task_deadline=deadline, sleep=clock.sleep,
        )
        assert clock.waits == [20]
        assert result["observability"]["error_category"] == EXHAUSTED
        assert result["observability"]["task_deadline"]["wait_seconds"] == 20
        assert len(runtime.calls) == 1
        assert (runtime.workspaces[0].workspace / "partial.txt").exists()
    finally:
        store.close()


def test_cumulative_task_deadline_expiry_during_reservation_cannot_start_a_turn(host, monkeypatch):
    clock = Clock()
    store = store_at(host, clock)
    ledger = CostReceiptLedger(host / "cost.sqlite", run_id="offline-cell-run")
    reserve = codex_runner.CodexAgentRunner._reserve_call

    def expires_while_reserving(runner, *args, **kwargs):
        call_id = reserve(runner, *args, **kwargs)
        clock.advance(TOTAL_SECONDS)
        return call_id

    monkeypatch.setattr(codex_runner.CodexAgentRunner, "_reserve_call", expires_while_reserving)
    try:
        runtime = Runtime(monkeypatch, clock, [])
        result = execute(executor_for(store, ledger), host)
        assert result["observability"]["error_category"] == EXHAUSTED
        assert runtime.calls == []
        assert runtime.workspaces[0].root.exists()
    finally:
        store.close()
        ledger.close()


@pytest.mark.parametrize("condition,expected", [("A", 4), ("B", 5), ("C", 5)])
def test_cumulative_task_deadline_attempt_policy_and_single_turn_bound(host, monkeypatch, condition, expected):
    clock = Clock()
    store = store_at(host, clock, condition=condition)
    try:
        runtime = Runtime(monkeypatch, clock, [
            *[{"seconds": 1, "rate_limited": True} for _ in range(4)], {"seconds": 1},
        ])
        executor = executor_for(store)
        result = step2.run_with_infra_retries(
            lambda _: execute(executor, host), max_attempts=4,
            task_deadline=store.for_task(TASK), sleep=clock.sleep,
        )
        assert len(runtime.calls) == expected
        assert all(timeout == ATTEMPT_SECONDS for timeout in runtime.joins)
        assert result["status"] == ("error" if condition == "A" else "success")
        if condition == "A":
            assert result["observability"]["error_category"] == ATTEMPTS_EXHAUSTED
            store.close()
            store = store_at(host, clock, condition=condition, initialize=False)
            assert execute(executor_for(store), host)["observability"]["error_category"] == ATTEMPTS_EXHAUSTED
            assert len(runtime.calls) == 4
        assert all((workspace.workspace / "partial.txt").exists() for workspace in runtime.workspaces)
    finally:
        store.close()


def test_cumulative_task_deadline_new_cell_has_its_own_clock(host):
    clock = Clock()
    store = store_at(host, clock)
    try:
        first = store.for_task(TASK)
        first.remaining_seconds()
        clock.advance(120)
        second = store.for_task(TASK2)
        assert second.remaining_seconds() == TOTAL_SECONDS
        assert first.remaining_seconds() == TOTAL_SECONDS - 120
        repeat = store_at(host, clock, repetition=2, name="repeat2")
        try:
            assert repeat.for_task(TASK).remaining_seconds() == TOTAL_SECONDS
            assert repeat.for_task(TASK).as_record()["repetition"] == 2
        finally:
            repeat.close()
        for name, options in (("condition-a", {"condition": "A"}),
                              ("another-run", {"run_id": "another-declared-run"})):
            other = store_at(host, clock, name=name, **options)
            try:
                assert other.for_task(TASK).remaining_seconds() == TOTAL_SECONDS
                assert first.as_record()["expires_unix"] != other.for_task(TASK).as_record()["expires_unix"]
            finally:
                other.close()
    finally:
        store.close()


@pytest.mark.parametrize("change", ["missing", "tampered", "symlink", "hardlink", "identity", "policy", "clock"])
def test_cumulative_task_deadline_restore_refuses_without_a_new_start(host, change):
    clock = Clock()
    store = store_at(host, clock)
    store.for_task(TASK).remaining_seconds()
    path = store.path
    original = path.read_bytes()
    store.close()
    options = {}
    if change == "missing":
        path.unlink()
    elif change == "tampered":
        document = json.loads(original)
        document["payload"]["cells"][TASK]["expires_unix"] += 100
        path.write_text(json.dumps(document))
    elif change == "symlink":
        path.rename(path.with_suffix(".original"))
        path.symlink_to(path.with_suffix(".original"))
    elif change == "hardlink":
        os.link(path, path.with_suffix(".linked"))
    elif change == "identity":
        options["run_id"] = "another-declared-run"
    elif change == "policy":
        options["condition"] = "A"
    else:
        clock.advance(-1)
    with pytest.raises(TaskDeadlineRefused):
        store_at(host, clock, initialize=False, **options)
    if change in {"identity", "policy", "clock"}:
        assert path.read_bytes() == original
    elif change == "missing":
        assert not path.exists()


def test_cumulative_task_deadline_missing_root_collision_and_live_lock_refuse(host):
    clock = Clock()
    with pytest.raises(TaskDeadlineRefused):
        store_at(host, clock, initialize=False)
    assert not (host / "state").exists()
    store = store_at(host, clock)
    try:
        original = store.path.read_bytes()
        for initialize in (True, False):
            with pytest.raises(TaskDeadlineRefused):
                store_at(host, clock, initialize=initialize)
        assert store.path.read_bytes() == original
    finally:
        store.close()


@pytest.mark.parametrize("name", ["agent-work/state", "agent-temp/state"])
def test_cumulative_task_deadline_state_is_not_agent_writable(host, name):
    with pytest.raises(TaskDeadlineRefused, match="agent-writable"):
        store_at(host, Clock(), name=name)
    assert not (host / name).exists()


def test_cumulative_task_deadline_legacy_retry_and_cleanup_unchanged(host, monkeypatch):
    clock = Clock()
    runtime = Runtime(monkeypatch, clock, [
        {"seconds": 1, "rate_limited": True} for _ in range(4)
    ])
    executor = executor_for()
    result = step2.run_with_infra_retries(
        lambda _: execute(executor, host), max_attempts=4, sleep=clock.sleep,
    )
    assert len(runtime.calls) == 4 and clock.waits == [60, 120, 240]
    assert result["observability"]["error_category"] == "rate_limited"
    assert "task_deadline" not in result["observability"]
    assert all(not workspace.root.exists() for workspace in runtime.workspaces)
    legacy = ExperimentConfig.from_yaml(ROOT / "batch-runner/experiments/exp035_codex_foundry_full220.yaml")
    assert "task_deadline" not in legacy.execution.codex
    assert legacy.execution.timeout == 1800 and legacy.execution.max_retries == 3
    assert legacy.validate() == []


@pytest.mark.parametrize("change", ["current", "bad_repetition", "extra_field", "timeout", "mode", "qa"])
def test_cumulative_task_deadline_config_and_step1_projection(host, change):
    config = ExperimentConfig.from_yaml(ROOT / "batch-runner/experiments/exp035_codex_foundry_full220.yaml")
    document = config.to_dict()
    document["experiment"]["id"] = "exp_deadline_test"
    block = {"condition": "B", "repetition": 1}
    document["execution"]["codex"]["task_deadline"] = block
    if change == "bad_repetition":
        block["repetition"] = True
    elif change == "extra_field":
        block["reset_on_retry"] = True
    elif change == "timeout":
        document["execution"]["timeout"] = 1801
    elif change == "mode":
        document["execution"]["mode"] = "subprocess"
    elif change == "qa":
        document["condition_a"]["qa"] = {"enabled": True}
    parsed = ExperimentConfig.from_dict(document)
    assert bool(parsed.validate()) is (change != "current")
    if change == "current":
        assert step1._public_codex_config(parsed.execution.codex)["task_deadline"] == block
        assert validate_deadline_execution(parsed.to_dict()["execution"], document["condition_a"]).max_attempts is None


def test_cumulative_task_deadline_cli_routes_explicit_state_without_execution(host, monkeypatch):
    received = []
    monkeypatch.setattr(step2, "run_inference", lambda **kwargs: received.append(kwargs))
    monkeypatch.setattr(step2.sys, "argv", ["step2_run_inference.py", "--codex-deadline-state", str(host / "state"),
                                         "--initialize-codex-deadlines"])
    step2.main()
    assert received[0]["codex_deadline_state"] == host / "state"
    assert received[0]["initialize_codex_deadlines"] is True


def test_cumulative_task_deadline_lazy_persistence_helpers_initialize_and_restore(host, monkeypatch):
    from core import hf_publication

    calls = []
    for role, name in (("path", "_assert_no_symlink_ancestors"),
                       ("read", "_load_private_json_object"),
                       ("write", "_write_private_json")):
        original = getattr(hf_publication, name)

        def observed(*args, _original=original, _role=role, **kwargs):
            calls.append(_role)
            return _original(*args, **kwargs)

        monkeypatch.setattr(hf_publication, name, observed)
    clock = Clock()
    store = store_at(host, clock)
    try:
        deadline = store.for_task(TASK)
        assert deadline.remaining_seconds() == TOTAL_SECONDS
        expiry = deadline.as_record()["expires_unix"]
        assert {"path", "read", "write"} <= set(calls)
    finally:
        store.close()
    calls.clear()
    clock.advance(120)
    restored = store_at(host, clock, initialize=False)
    try:
        assert {"path", "read"} <= set(calls)
        assert "write" not in calls  # restore reads, never reinvents start time
        record = restored.for_task(TASK).as_record()
        assert record["expires_unix"] == expiry
        assert record["remaining_seconds"] == TOTAL_SECONDS - 120
        assert "write" in calls
    finally:
        restored.close()


@pytest.mark.parametrize("stale", [None, "selector", "deadline"],
                         ids=["current", "selector_only", "deadline_only"])
def test_cumulative_task_deadline_active_grader_bindings(stale):
    previous = {
        "selector": ("c92bf13696fa506c84dbee649d5ba3c03fb33244810f30e2be4a05630ca204e1",
                     "785352daa052b105f0dfce08d8de7b3f41633a8e6b312111bec5bdbc8806144b"),
        "deadline": ("fdfb7b9160635859d2c46ee9a79d5d908bc4ad546f9d240893da98159752258d",
                     "c85f5b7ac5a723266172fedae39d38a69bd93cebae25888c63469f038c97ef01"),
    }
    plans = [(comparison, comparison.load_plan()), (pilot, pilot.load_plan(pilot.PLAN))]
    for index, (module, plan) in enumerate(plans):
        template = ROOT / module.GRADER
        current = step8.compute_grader_source_hash(template, yaml.safe_load(template.read_bytes()), batch_root=ROOT / "batch-runner")
        assert all(current != hashes[index] for hashes in previous.values())
        old_hash = previous[stale][index] if stale else None
        if module is comparison:
            assert plan["shared"]["grading"]["template_source_sha256"] == current
            if stale:
                plan["shared"]["grading"]["template_source_sha256"] = old_hash
        else:
            assert plan["dispatch_grading_identity"]["grader_template_source_hash"] == current
            assert pilot.DISPATCH_GRADING_IDENTITY["grader_template_source_hash"] == current
            if stale:
                plan["dispatch_grading_identity"]["grader_template_source_hash"] = old_hash
                with pytest.raises(ValueError, match="grader_template_source_drift"):
                    identity._grader_identity(plan)
            else:
                assert identity._grader_identity(plan)["template_source_hash"] == current
        report = module.inspect_plan(plan)
        assert report["configuration_valid"] is (stale is None)
        assert report["launch_allowed"] is report["full_220_allowed"] is False
        assert report["launch_blockers"] == list(module.LAUNCH_BLOCKERS)
