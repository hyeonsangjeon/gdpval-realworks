"""Native continuation through the real SDK facade/adapter, with no process or provider."""

from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
from contextlib import nullcontext
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from openai_codex import Codex, Sandbox
from openai_codex._sandbox import _sandbox_policy
from openai_codex.client import CodexClient
from openai_codex.generated.v2_all import (
    ThreadResumeParams, ThreadStartParams, ThreadTokenUsageUpdatedNotification,
    TurnCompletedNotification, TurnStartParams,
)
from openai_codex.models import Notification

import step2_run_inference as step2
import step8_grade as step8
import gpt54_comparison_preflight as comparison
import gpt56_sol_codex_pilot_preflight as pilot
import gpt56_pilot_identity_plan as identity
import ghcp_vm_gate_preflight as ghcp_gate
from core import azure_ai_clients, codex_azure_token, codex_runner, codex_runtime_config
from core import reference_integrity
from core.codex_task_deadline import (
    ATTEMPT_SECONDS, EXHAUSTED, STATE_REFUSED, TOTAL_SECONDS,
    CodexTaskDeadline, TaskDeadlineRefused,
)
from core.cost_receipts import BUCKET_PROBLEM_SOLVING, CallUsage, CostReceiptLedger
from core.executor import TaskExecutor
from .test_codex_task_deadline import (
    Clock, CONDITION, ROOT, SETTINGS, TASK, TASK2, execute, host, store_at,
)
from .test_ghcp_vm_gate_contract import FOUNDRY, FOUNDRY_SHA256, WORKFLOW, WORKFLOW_SHA256


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    """Installed types are real; every process, credential and network edge is forbidden."""
    calls = []

    def forbidden(*args, **kwargs):
        calls.append("forbidden")
        raise AssertionError("native resume regression crossed a live boundary")

    for name in ("Popen", "run", "check_call", "check_output"):
        monkeypatch.setattr(subprocess, name, forbidden)
    for name in ("connect", "connect_ex"):
        monkeypatch.setattr(socket.socket, name, forbidden)
    for name in ("create_connection", "getaddrinfo"):
        monkeypatch.setattr(socket, name, forbidden)
    monkeypatch.setattr(os, "system", forbidden)
    monkeypatch.setattr(step2.time, "sleep", forbidden)
    for constructor in (azure_ai_clients.AzureAIClientFactory, azure_ai_clients.OpenAI,
                        azure_ai_clients.AzureOpenAI, azure_ai_clients.DefaultAzureCredential,
                        Codex, CodexClient, step8.Grader):
        monkeypatch.setattr(constructor, "__init__", forbidden)
    monkeypatch.setattr(codex_azure_token, "acquire_token", forbidden)
    monkeypatch.setattr(codex_azure_token, "get_bearer_token_provider", forbidden)
    monkeypatch.setattr(azure_ai_clients, "get_bearer_token_provider", forbidden)
    monkeypatch.setattr(codex_runtime_config, "discover_azure_cli_config_dir", forbidden)
    monkeypatch.setattr(codex_runner, "_descendant_pids", lambda _: set())
    monkeypatch.setattr(codex_runner, "sweep_orphans", lambda _: ())
    yield
    assert calls == []


class SDKTransport:
    """Replace only JSON-RPC transport/clock, not start/resume/turn or the collector.

    Real pinned SDK request/response models validate the synthetic messages.
    No Codex/client constructor, app-server, socket or local model is started.
    """

    def __init__(self, monkeypatch, clock, scripts):
        self.clock, self.scripts = clock, list(scripts)
        self.requests, self.workspaces, self.joins = [], [], []
        self.sessions, self.queues = {}, {}
        self.current = None
        self.start_error = self.resume_error = self.wrong_resume_id = False
        self.runtime_error = False
        self.stage_calls = 0
        self.on_turn = None
        original_stage = codex_runner.CodexWorkspace.stage_references

        def stage(workspace, references):
            self.stage_calls += 1
            return original_stage(workspace, references)

        def open_runtime(runner, workspace):
            self.workspace = workspace
            self.workspaces.append(workspace)
            if self.runtime_error:
                self.runtime_error = False
                raise RuntimeError("synthetic pre-thread runtime failure")
            # __new__ cannot spawn the app-server; the constructor is forbidden.
            client = object.__new__(CodexClient)
            client.request = self.request
            client._thread_start_lock = lambda _: nullcontext()
            client._router = SimpleNamespace(has_goal=lambda _: False)
            client.register_turn_notifications = lambda _: None
            client.unregister_turn_notifications = lambda _: None
            client.next_turn_notification = lambda turn_id: next(self.queues[turn_id])
            client.close = lambda: None
            codex = object.__new__(Codex)
            codex._client = client
            return codex

        outer = self

        class Worker:
            def __init__(self, *, target, **kwargs):
                self.target = target
                self.remaining = outer.current.get("seconds", 1)
                self.joined = False

            def start(self):
                self.target()

            def join(self, timeout):
                outer.joins.append(timeout)
                if not self.joined:
                    elapsed = min(self.remaining, timeout)
                    outer.clock.advance(elapsed)
                    self.remaining -= elapsed
                    self.joined = True

            def is_alive(self):
                return self.remaining > 0

        monkeypatch.setattr(codex_runner.CodexWorkspace, "stage_references", stage)
        monkeypatch.setattr(codex_runner.CodexAgentRunner, "open_runtime", open_runtime)
        monkeypatch.setattr(codex_runner, "threading", SimpleNamespace(Thread=Worker))

    def request(self, method, params, *, response_model):
        self.requests.append((method, params))
        if method in {"thread/start", "thread/resume"}:
            model = ThreadStartParams if method == "thread/start" else ThreadResumeParams
            params = model.model_validate(params).model_dump(mode="json", by_alias=True, exclude_none=True)
            if method == "thread/start":
                if self.start_error:
                    raise RuntimeError("synthetic lost thread/start response")
                thread_id = f"synthetic-native-{len(self.sessions)}"
                self.sessions[thread_id] = self.workspace.continuation_binding()
                (self.workspace.codex_home / "synthetic-session-marker").write_text(thread_id)
            else:
                if self.resume_error:
                    raise RuntimeError("synthetic native resume refusal")
                thread_id = params["threadId"]
                assert self.sessions[thread_id] == self.workspace.continuation_binding()
                assert (self.workspace.codex_home / "synthetic-session-marker").read_text() == thread_id
                if self.wrong_resume_id:
                    thread_id = "synthetic-wrong-thread"
            assert params["cwd"] == str(self.workspace.workspace)
            thread = {
                "id": thread_id, "cliVersion": "0.147.0", "createdAt": 1, "updatedAt": 1,
                "cwd": params["cwd"], "ephemeral": False, "modelProvider": params["modelProvider"],
                "preview": "synthetic", "sessionId": thread_id, "source": "exec",
                "status": {"type": "idle"}, "turns": [],
            }
            return response_model.model_validate({
                "thread": thread, "cwd": params["cwd"], "model": params["model"],
                "modelProvider": params["modelProvider"], "approvalPolicy": params["approvalPolicy"],
                "approvalsReviewer": params.get("approvalsReviewer", "user"),
                "sandbox": _sandbox_policy(Sandbox.workspace_write),
            })
        if method == "turn/interrupt":
            return response_model.model_validate({})
        assert method == "turn/start"
        TurnStartParams.model_validate(params)
        thread_id = params["threadId"]
        assert thread_id in self.sessions
        if self.on_turn is not None:
            self.on_turn(thread_id)
        self.current = script = self.scripts.pop(0)
        # A live partial is extended, not restaged/overwritten by the adapter.
        with (self.workspace.workspace / "partial.txt").open("ab") as output:
            output.write(b"synthetic partial\n")
        if script.get("turn_error"):
            raise RuntimeError(script["turn_error"])
        turn_id = f"synthetic-turn-{len(self.queues)}"
        error = script.get("error")
        turn = {"id": turn_id, "items": [], "status": "failed" if error else "completed",
                "error": {"message": error} if error else None}
        if error and "http_status_code" in script:
            turn["error"]["codexErrorInfo"] = {
                "responseStreamDisconnected": {"httpStatusCode": script["http_status_code"]},
            }
            turn["error"]["additionalDetails"] = script.get("additional_details")
        events = []
        if script.get("tokens") is not None:
            count = script["tokens"]
            total = {"inputTokens": count, "cachedInputTokens": 0, "cacheWriteInputTokens": 0,
                     "outputTokens": count // 5, "reasoningOutputTokens": 0, "totalTokens": count + count // 5}
            events.append(Notification("thread/tokenUsage/updated", ThreadTokenUsageUpdatedNotification.model_validate({
                "threadId": thread_id, "turnId": turn_id, "tokenUsage": {"total": total, "last": total},
            })))
        events.append(Notification("turn/completed", TurnCompletedNotification.model_validate({
            "threadId": thread_id, "turn": turn,
        })))
        self.queues[turn_id] = iter(events)
        return response_model.model_validate({"turn": {**turn, "status": "inProgress", "error": None}})

    def count(self, method):
        return sum(name == method for name, _ in self.requests)


def executor_for(store, ledger=None, settings=SETTINGS):
    return TaskExecutor(
        mode="codex_foundry", timeout=ATTEMPT_SECONDS,
        codex_options={"provider_settings": settings, "task_deadline_store": store},
        codex_cost_ledger=ledger, run_id=store.identity["run_id"], condition_name="condition_a",
    )


RATE = "HTTP 429 Too Many Requests"


@pytest.mark.parametrize("condition", ["B", "C"])
def test_native_resume_failure_retry_and_process_restore_keep_thread_workspace_clock_and_usage(host, monkeypatch, condition):
    assert codex_runtime_config.require_pinned_runtime() == ("0.147.0", "0.147.0")
    clock = Clock()
    store = store_at(host, clock, condition=condition)
    ledger = CostReceiptLedger(host / "cost.sqlite", run_id="offline-cell-run")
    transport = SDKTransport(monkeypatch, clock, [
        {"tokens": 100, "seconds": 10, "error": RATE},
        {"tokens": 135, "seconds": 20, "error": RATE}, {"tokens": 170, "seconds": 5},
    ])
    try:
        executor = executor_for(store, ledger)
        transport.on_turn = lambda thread_id: (
            pytest.fail("thread was not bound before turn/start")
            if store._read()["cells"][TASK]["continuation"]["thread_id"] != thread_id else None
        )

        def attempt(index):
            if index == 2:
                raise InterruptedError("synthetic host restart")
            return execute(executor, host)

        with pytest.raises(InterruptedError):
            step2.run_with_infra_retries(attempt, max_attempts=4, task_deadline=store.for_task(TASK), sleep=clock.sleep)
        expiry = store.for_task(TASK).as_record()["expires_unix"]
        assert clock.waits == [60, 120]
        retained = transport.workspaces[0].continuation_binding()
        store.close()
        ledger.close()
        clock.advance(300)
        store = store_at(host, clock, condition=condition, initialize=False)
        ledger = CostReceiptLedger(host / "cost.sqlite", run_id="offline-cell-run")
        result = step2.run_with_infra_retries(
            lambda _: execute(executor_for(store, ledger), host), max_attempts=4,
            task_deadline=store.for_task(TASK), sleep=clock.sleep,
        )
        assert result["status"] == "success"
        record = result["observability"]["task_deadline"]
        assert record["expires_unix"] == expiry
        assert record["remaining_seconds"] == TOTAL_SECONDS - 515
        assert record["attempts_admitted"] == 3 and record["native_resumes"] == 2
        assert record["session_policy"] == "retained_native_thread"
        assert str(host) not in json.dumps(record)
        assert transport.count("thread/start") == 1 and transport.count("thread/resume") == 2
        assert transport.stage_calls == 1 and len(transport.scripts) == 0
        assert all(workspace.continuation_binding() == retained for workspace in transport.workspaces)
        assert (transport.workspaces[0].workspace / "partial.txt").read_bytes() == b"synthetic partial\n" * 3
        calls = ledger.calls_for(TASK, bucket=BUCKET_PROBLEM_SOLVING)
        assert len(calls) == len({row["call_id"] for row in calls}) == 3
        assert sorted(row["input_tokens"] for row in calls) == [35, 35, 100]
        assert ledger.receipt_for(TASK, BUCKET_PROBLEM_SOLVING).status == "partial"
    finally:
        store.close()
        ledger.close()


def test_native_resume_a_keeps_fresh_sessions_and_four_attempt_policy(host, monkeypatch):
    clock = Clock()
    store = store_at(host, clock, condition="A")
    transport = SDKTransport(monkeypatch, clock, [{"tokens": 100, "error": RATE}, {"tokens": 135}])
    try:
        executor = executor_for(store)
        result = step2.run_with_infra_retries(lambda _: execute(executor, host), max_attempts=4,
                                            task_deadline=store.for_task(TASK), sleep=clock.sleep)
        assert result["status"] == "success" and store.control.max_attempts == 4
        assert transport.count("thread/start") == 2 and transport.count("thread/resume") == 0
        assert len({workspace.root for workspace in transport.workspaces}) == 2
        assert transport.stage_calls == 2
        assert store._read()["cells"][TASK]["continuation"] is None
        assert result["observability"]["task_deadline"]["session_policy"] == "fresh_session"
    finally:
        store.close()


@pytest.mark.parametrize("change", ["provider", "model", "effort", "context", "prompt", "rendered_request", "ledger"])
def test_native_resume_changed_target_or_request_refuses(host, monkeypatch, change):
    clock = Clock()
    store = store_at(host, clock)
    transport = SDKTransport(monkeypatch, clock, [{"tokens": 100, "error": RATE}])
    try:
        assert execute(executor_for(store), host)["observability"]["error_category"] == "rate_limited"
        settings = SETTINGS
        if change == "provider":
            settings = replace(settings, endpoint="https://another-account.openai.azure.com/openai/v1/")
        elif change == "model":
            settings = replace(settings, model="other-model")
        elif change == "effort":
            settings = replace(settings, reasoning_effort="high")
        elif change == "context":
            settings = replace(settings, model_context_window=64000)
        elif change == "rendered_request":
            original = codex_runner.CodexAgentRunner.build_task_text
            monkeypatch.setattr(codex_runner.CodexAgentRunner, "build_task_text",
                                lambda *args, **kwargs: original(*args, **kwargs) + " altered")
        ledger = CostReceiptLedger(host / "changed.sqlite", run_id="offline-cell-run") if change == "ledger" else None
        try:
            executor = executor_for(store, ledger, settings)
            result = step2._execute_single_task(
                {"task_id": TASK, "instruction": "changed request" if change == "prompt" else
                 "Synthetic task; not benchmark input.", "reference_files": [], "needs_files": False},
                CONDITION, executor, "codex_foundry", None, settings.model,
                run_id="offline-cell-run", condition_name="condition_a", upload_root=host / "upload",
            )
            assert result["observability"]["error_category"] == STATE_REFUSED
            assert transport.count("turn/start") == 1 and transport.count("thread/resume") == 0
            assert (transport.workspaces[0].workspace / "partial.txt").exists()
        finally:
            if ledger is not None:
                ledger.close()
    finally:
        store.close()


@pytest.mark.parametrize("change", ["repetition", "prepared", "run", "condition", "cross_task"])
def test_native_resume_cross_cell_restore_refuses(host, monkeypatch, change):
    clock = Clock()
    store = store_at(host, clock)
    transport = SDKTransport(monkeypatch, clock, [{"tokens": 100, "error": RATE}])
    try:
        execute(executor_for(store), host)
        if change == "cross_task":
            data = store._read()
            data["cells"][TASK2] = data["cells"][TASK]
            store._write(data)  # valid checksum still cannot authorize a different cell
            result = execute(executor_for(store), host, task=TASK2)
            assert result["observability"]["error_category"] == STATE_REFUSED
        else:
            store.close()
            options = {"repetition": {"repetition": 2}, "prepared": {"prepared_fingerprint": "b" * 64},
                       "run": {"run_id": "different-run"}, "condition": {"condition": "C"}}[change]
            with pytest.raises(TaskDeadlineRefused):
                store_at(host, clock, initialize=False, **options)
        assert transport.count("turn/start") == 1 and transport.count("thread/resume") == 0
    finally:
        store.close()


@pytest.mark.parametrize("change", ["missing_binding", "missing_thread", "checksum", "missing_state",
                                    "linked_state", "hardlinked_state", "linked_workspace", "missing_home", "replaced_home"])
def test_native_resume_missing_corrupt_or_linked_state_never_falls_back(host, monkeypatch, change):
    clock = Clock()
    store = store_at(host, clock)
    transport = SDKTransport(monkeypatch, clock, [{"tokens": 100, "error": RATE}])
    try:
        execute(executor_for(store), host)
        workspace = transport.workspaces[0]
        if change in {"missing_binding", "missing_thread"}:
            data = store._read()
            if change == "missing_binding":
                data["cells"][TASK]["continuation"] = None
            else:
                data["cells"][TASK]["continuation"]["thread_id"] = None
            store._write(data)
        elif change == "checksum":
            with store.path.open("ab") as output:
                output.write(b"damaged")
        elif change in {"missing_state", "linked_state"}:
            store.path.rename(store.path.with_suffix(".retained"))
            if change == "linked_state":
                store.path.symlink_to(store.path.with_suffix(".retained"))
        elif change == "hardlinked_state":
            os.link(store.path, store.path.with_suffix(".linked"))
        elif change == "linked_workspace":
            workspace.workspace.rename(workspace.root / "retained-workspace")
            workspace.workspace.symlink_to(workspace.root / "retained-workspace", target_is_directory=True)
        else:
            workspace.home.rename(workspace.root / "retained-home")
            if change == "replaced_home":
                workspace.home.mkdir()
        result = execute(executor_for(store), host)
        assert result["observability"]["error_category"] == STATE_REFUSED
        assert transport.count("turn/start") == 1 and transport.count("thread/resume") == 0
        partial = (workspace.root / "retained-workspace" if change == "linked_workspace" else workspace.workspace) / "partial.txt"
        assert partial.read_bytes() == b"synthetic partial\n"
    finally:
        store.close()


@pytest.mark.parametrize("failure", ["pre_thread", "uncertain_start", "resume_refused", "wrong_response_id"])
def test_native_resume_distinguishes_pre_thread_and_bound_failures(host, monkeypatch, failure):
    clock = Clock()
    store = store_at(host, clock)
    transport = SDKTransport(monkeypatch, clock, [{"tokens": 100, "error": RATE}, {"tokens": 120}])
    try:
        transport.runtime_error = failure == "pre_thread"
        transport.start_error = failure == "uncertain_start"
        execute(executor_for(store), host)
        binding = store._read()["cells"][TASK]["continuation"]
        if failure == "pre_thread":
            assert binding["phase"] == "pre_thread" and binding["thread_id"] is None
            assert execute(executor_for(store), host)["observability"]["error_category"] == "rate_limited"
            assert transport.count("thread/start") == 1 and transport.stage_calls == 1
        else:
            transport.resume_error = failure == "resume_refused"
            transport.wrong_resume_id = failure == "wrong_response_id"
            result = execute(executor_for(store), host)
            assert result["observability"]["error_category"] == STATE_REFUSED
            assert transport.count("thread/start") == 1
            assert transport.count("turn/start") == (0 if failure == "uncertain_start" else 1)
            assert store._read()["cells"][TASK]["continuation"]["thread_id"] == binding["thread_id"]
    finally:
        store.close()


@pytest.mark.parametrize("gap", ["lost_response", "missing_usage"])
def test_native_resume_missing_usage_gap_is_not_billed_as_new_tokens(host, monkeypatch, gap):
    clock = Clock()
    store = store_at(host, clock)
    ledger = CostReceiptLedger(host / "cost.sqlite", run_id="offline-cell-run")
    transport = SDKTransport(monkeypatch, clock, [
        ({"turn_error": "synthetic response lost after turn/start"} if gap == "lost_response" else {"error": RATE}),
        {"tokens": 200, "error": RATE}, {"tokens": 230},
    ])
    try:
        first = execute(executor_for(store, ledger), host)
        assert first["observability"]["error_category"] == ("turn_start_failed" if gap == "lost_response" else "rate_limited")
        store.close()
        store = store_at(host, clock, initialize=False)
        result = step2.run_with_infra_retries(
            lambda _: execute(executor_for(store, ledger), host), max_attempts=4,
            task_deadline=store.for_task(TASK), sleep=clock.sleep,
        )
        assert result["status"] == "success" and transport.count("thread/start") == 1
        calls = ledger.calls_for(TASK)
        assert len(calls) == 3
        assert sorted(row["input_tokens"] for row in calls if row["input_tokens"] is not None) == [30]
        assert sum(row["input_tokens"] is None for row in calls) == 2
        assert ledger.receipt_for(TASK, BUCKET_PROBLEM_SOLVING).status == "partial"
    finally:
        store.close()
        ledger.close()


def test_native_resume_settlement_crash_replays_same_receipt_without_double_charge(host, monkeypatch):
    clock = Clock()
    store = store_at(host, clock)
    ledger = CostReceiptLedger(host / "cost.sqlite", run_id="offline-cell-run")
    transport = SDKTransport(monkeypatch, clock, [{"tokens": 100, "error": RATE}, {"tokens": 130}])
    try:
        with monkeypatch.context() as patch:
            def interrupted(*args):
                raise SystemExit("synthetic interruption after ledger commit")
            patch.setattr(CodexTaskDeadline, "acknowledge_usage", interrupted)
            with pytest.raises(SystemExit):
                execute(executor_for(store, ledger), host)
        assert store._read()["cells"][TASK]["continuation"]["turns"][0]["phase"] == "observed"
        store.close()
        store = store_at(host, clock, initialize=False)
        assert execute(executor_for(store, ledger), host)["status"] == "success"
        calls = ledger.calls_for(TASK)
        assert len(calls) == len({row["call_id"] for row in calls}) == 2
        assert sum(row["input_tokens"] for row in calls) == 130
        assert transport.count("thread/resume") == 1
    finally:
        store.close()
        ledger.close()


def _restore_through_retry(executor, host, clock, store, *, task=TASK, instruction=None,
                           task_info=None):
    """Use the production host-only task projection before the outer gate."""
    attempts = []

    def forbidden_attempt(index):
        attempts.append(index)
        pytest.fail("terminal/expired restore reached an execution attempt")

    def reconcile():
        assert step2._execute_single_task(
            task_info if task_info is not None else {
                "task_id": task, "instruction": instruction or "Synthetic task; not benchmark input.",
                "reference_files": [], "needs_files": False},
            CONDITION, executor, "codex_foundry", None, SETTINGS.model,
            run_id="offline-cell-run", condition_name="condition_a",
            upload_root=host / "upload", accounting_only=True,
        ) is None

    result = step2.run_with_infra_retries(
        forbidden_attempt, max_attempts=4, task_deadline=store.for_task(task),
        reconcile_accounting=reconcile, sleep=clock.sleep,
    )
    assert attempts == []
    return result


@pytest.fixture
def reference_task(host, monkeypatch):
    """Real declared records and staging; observe only the runner's public boundary."""
    root = host / "inputs"
    paths = ["reference_files/specification/terms.txt", "reference_files/tabular/data.csv"]
    for relative, content in zip(paths, (b"approved", b"id,value\n1,2\n"), strict=True):
        source = root / relative
        source.parent.mkdir(parents=True)
        source.write_bytes(content)
    records = [{"path": path, **reference_integrity.reference_manifest_record(root, path)} for path in paths]
    task = SimpleNamespace(
        root=root, staged=[],
        info={"task_id": TASK, "instruction": "Synthetic task; not benchmark input.",
              "reference_files": paths, "reference_file_records": records, "needs_files": False},
    )
    monkeypatch.setattr(step2, "DEFAULT_LOCAL_PATH", root)
    original = codex_runner.CodexAgentRunner.reconcile_task_accounting

    def observe(runner, *args, **kwargs):
        references = tuple(kwargs["reference_files"])
        assert all(isinstance(path, reference_integrity.VerifiedReferencePath) for path in references)
        task.staged.append(references)
        # No replacement of resolution, staging, byte checks or continuation identity.
        return original(runner, *args, **kwargs)

    monkeypatch.setattr(codex_runner.CodexAgentRunner, "reconcile_task_accounting", observe)
    return task


def _execute_reference_task(executor, host, task):
    # strict_inputs is deliberately omitted: exercise Step 2's default verified-copy path.
    return step2._execute_single_task(
        task.info, CONDITION, executor, "codex_foundry", None, SETTINGS.model,
        run_id="offline-cell-run", condition_name="condition_a", upload_root=host / "upload",
    )


def _assert_distinct_staging_with_same_declared_inputs(task, count):
    assert len(task.staged) == count
    parents = [Path(paths[0]).parent for paths in task.staged]
    assert len(set(parents)) == count
    for parent, paths in zip(parents, task.staged, strict=True):
        assert parent.name.startswith("gdpval-reference-")
        assert all(Path(path).parent == parent for path in paths)
        assert [{"path": path.declared_path, "sha256": path.sha256, "size": path.size}
                for path in paths] == task.info["reference_file_records"]
        assert not parent.exists()  # Step 2 cleaned only its invocation-local copies.


@pytest.mark.parametrize("condition", ["B", "C"])
def test_native_resume_stable_reference_retry_and_process_restore(host, monkeypatch, reference_task, condition):
    clock = Clock()
    store = store_at(host, clock, condition=condition)
    ledger = CostReceiptLedger(host / "cost.sqlite", run_id="offline-cell-run")
    transport = SDKTransport(monkeypatch, clock, [
        {"tokens": 100, "seconds": 10, "error": RATE},
        {"tokens": 135, "seconds": 20, "error": RATE}, {"tokens": 170, "seconds": 5},
    ])
    try:
        executor = executor_for(store, ledger)

        def attempt(index):
            if index == 2:
                raise InterruptedError("synthetic host restart")
            result = _execute_reference_task(executor, host, reference_task)
            assert result["observability"]["error_category"] == "rate_limited"
            if index == 0:
                retained_input = transport.workspaces[0].workspace / "terms.txt"
                retained_input.chmod(0o600)
                retained_input.write_bytes(b"retained agent edit")
            return result

        with pytest.raises(InterruptedError):
            step2.run_with_infra_retries(attempt, max_attempts=4,
                                        task_deadline=store.for_task(TASK), sleep=clock.sleep)
        expiry = store.for_task(TASK).as_record()["expires_unix"]
        retained = transport.workspaces[0].continuation_binding()
        store.close()
        ledger.close()
        clock.advance(300)
        store = store_at(host, clock, condition=condition, initialize=False)
        ledger = CostReceiptLedger(host / "cost.sqlite", run_id="offline-cell-run")
        result = step2.run_with_infra_retries(
            lambda _: _execute_reference_task(executor_for(store, ledger), host, reference_task),
            max_attempts=4, task_deadline=store.for_task(TASK), sleep=clock.sleep,
        )
        assert result["status"] == "success"
        record = result["observability"]["task_deadline"]
        assert record["expires_unix"] == expiry
        assert record["remaining_seconds"] == TOTAL_SECONDS - 515
        assert record["attempts_admitted"] == 3 and record["native_resumes"] == 2
        assert clock.waits == [60, 120] and transport.joins == [ATTEMPT_SECONDS] * 3
        assert transport.count("thread/start") == 1 and transport.count("thread/resume") == 2
        assert transport.count("turn/start") == 3 and transport.stage_calls == 1
        assert all(workspace.continuation_binding() == retained for workspace in transport.workspaces)
        assert (transport.workspaces[0].workspace / "partial.txt").read_bytes() == b"synthetic partial\n" * 3
        assert (transport.workspaces[0].workspace / "terms.txt").read_bytes() == b"retained agent edit"
        assert (reference_task.root / reference_task.info["reference_files"][0]).read_bytes() == b"approved"
        calls = ledger.calls_for(TASK)
        assert len(calls) == len({row["call_id"] for row in calls}) == 3
        assert sorted(row["input_tokens"] for row in calls) == [35, 35, 100]
        assert ledger.receipt_for(TASK, BUCKET_PROBLEM_SOLVING).status == "partial"
        _assert_distinct_staging_with_same_declared_inputs(reference_task, 3)
    finally:
        store.close()
        ledger.close()


def test_native_resume_stable_reference_a_stays_fresh(host, monkeypatch, reference_task):
    clock = Clock()
    store = store_at(host, clock, condition="A")
    transport = SDKTransport(monkeypatch, clock, [{"tokens": 100, "error": RATE}, {"tokens": 135}])
    try:
        executor = executor_for(store)
        result = step2.run_with_infra_retries(
            lambda _: _execute_reference_task(executor, host, reference_task), max_attempts=4,
            task_deadline=store.for_task(TASK), sleep=clock.sleep,
        )
        assert result["status"] == "success" and store.control.max_attempts == 4
        assert transport.count("thread/start") == 2 and transport.count("thread/resume") == 0
        assert len({workspace.root for workspace in transport.workspaces}) == 2
        assert transport.stage_calls == 2 and transport.joins == [ATTEMPT_SECONDS] * 2
        cell = store._read()["cells"][TASK]
        assert cell["continuation"] is None and len(cell["attempts"]) == 2
        assert cell["expires_unix"] == cell["started_unix"] + TOTAL_SECONDS
        _assert_distinct_staging_with_same_declared_inputs(reference_task, 2)
    finally:
        store.close()


@pytest.mark.parametrize("condition", ["B", "C"])
@pytest.mark.parametrize("window", ["before_ledger", "before_ack"])
@pytest.mark.parametrize("stop", ["completed", "content_filter", "expired"])
def test_native_resume_stable_reference_terminal_accounting(
    host, monkeypatch, reference_task, condition, window, stop,
):
    clock = Clock()
    store = store_at(host, clock, condition=condition)
    ledger_path = host / "cost.sqlite"
    ledger = CostReceiptLedger(ledger_path, run_id="offline-cell-run")
    script = {"tokens": 100}
    if stop != "completed":
        script["error"] = "reason: content_filter" if stop == "content_filter" else RATE
    transport = SDKTransport(monkeypatch, clock, [script])
    try:
        with monkeypatch.context() as patch:
            def interrupted(*args, **kwargs):
                raise SystemExit("synthetic settlement interruption")
            owner, name = ((codex_runner.CodexAgentRunner, "_settle_call") if window == "before_ledger"
                           else (CodexTaskDeadline, "acknowledge_usage"))
            patch.setattr(owner, name, interrupted)
            with pytest.raises(SystemExit):
                _execute_reference_task(executor_for(store, ledger), host, reference_task)

        expected_cell = store._read()["cells"][TASK]
        turn = expected_cell["continuation"]["turns"][0]
        assert turn["phase"] == "observed" and turn["after"]["input_tokens"] == 100
        assert expected_cell["continuation"]["terminal_reason"] == (None if stop == "expired" else stop)
        assert expected_cell["terminal_reason"] == ("content_filtered" if stop == "content_filter" else None)
        assert len(expected_cell["attempts"]) == 1
        assert expected_cell["expires_unix"] == expected_cell["started_unix"] + TOTAL_SECONDS
        assert ledger.calls_for(TASK)[0]["state"] == ("reserved" if window == "before_ledger" else "settled")
        turn["phase"] = "settled"  # Only the validated acknowledgment may change.
        requests = list(transport.requests)
        first_receipt = None
        for _ in range(2):
            store.close()
            ledger.close()
            clock.advance(TOTAL_SECONDS if stop == "expired" else 10)
            store = store_at(host, clock, condition=condition, initialize=False)
            ledger = CostReceiptLedger(ledger_path, run_id="offline-cell-run")
            changes = ledger._connection.total_changes
            result = _restore_through_retry(
                executor_for(store, ledger), host, clock, store, task_info=reference_task.info,
            )
            assert result["status"] == "error"  # No completed-result reconstruction.
            assert result["observability"]["error_category"] == (EXHAUSTED if stop == "expired" else STATE_REFUSED)
            assert store._read()["cells"][TASK] == expected_cell
            calls = ledger.calls_for(TASK)
            assert len(calls) == 1 and calls[0]["call_id"] == turn["call_id"]
            assert calls[0]["state"] == "settled"
            assert (calls[0]["input_tokens"], calls[0]["output_tokens"]) == (100, 20)
            assert ledger._connection.total_changes - changes == (
                1 if first_receipt is None and window == "before_ledger" else 0)
            if first_receipt is None:
                first_receipt = calls[0]
            else:
                assert calls[0] == first_receipt
            assert ledger.receipt_for(TASK, BUCKET_PROBLEM_SOLVING).status == "partial"
            assert transport.requests == requests and len(transport.workspaces) == 1
            assert transport.stage_calls == 1 and clock.waits == []
            assert (transport.workspaces[0].workspace / "partial.txt").read_bytes() == b"synthetic partial\n"
        _assert_distinct_staging_with_same_declared_inputs(reference_task, 3)
    finally:
        store.close()
        ledger.close()


@pytest.mark.parametrize("entry", ["retry", "accounting_only"])
@pytest.mark.parametrize("change", ["declared", "content", "size", "unverified_content",
                                    "unverified_size", "order", "missing", "symlink", "collision"])
def test_native_resume_stable_reference_drift_refuses_before_request_or_settlement(
    host, monkeypatch, reference_task, entry, change,
):
    clock = Clock()
    store = store_at(host, clock)
    ledger = CostReceiptLedger(host / "cost.sqlite", run_id="offline-cell-run")
    transport = SDKTransport(monkeypatch, clock, [{"tokens": 100, "error": RATE}])
    try:
        with monkeypatch.context() as patch:
            def interrupted(*args, **kwargs):
                raise SystemExit("synthetic interruption before ledger commit")
            patch.setattr(codex_runner.CodexAgentRunner, "_settle_call", interrupted)
            with pytest.raises(SystemExit):
                _execute_reference_task(executor_for(store, ledger), host, reference_task)
        info = reference_task.info
        relative = info["reference_files"][0]
        source = reference_task.root / relative
        if change == "declared":
            relative = "reference_files/different_role/terms.txt"
            target = reference_task.root / relative
            target.parent.mkdir()
            source.rename(target)
            info["reference_files"][0] = relative
            info["reference_file_records"][0]["path"] = relative
        elif change in {"content", "size", "unverified_content"}:
            source.write_bytes(b"changed!" if change != "size" else b"approved\n")
            if change != "unverified_content":
                info["reference_file_records"][0].update(
                    reference_integrity.reference_manifest_record(reference_task.root, relative))
        elif change == "unverified_size":
            info["reference_file_records"][0]["size"] += 1
        elif change == "order":
            info["reference_files"].reverse()
            info["reference_file_records"].reverse()
        elif change == "missing":
            source.unlink()
        elif change == "symlink":
            retained = source.with_suffix(".retained")
            source.rename(retained)
            source.symlink_to(retained)
        else:
            relative = "reference_files/collision/terms.txt"
            target = reference_task.root / relative
            target.parent.mkdir()
            target.write_bytes(b"approved")
            info["reference_files"].append(relative)
            info["reference_file_records"].append({
                "path": relative, **reference_integrity.reference_manifest_record(reference_task.root, relative)})

        expected_cell = store._read()["cells"][TASK]
        before_calls = ledger.calls_for(TASK)
        before_requests = list(transport.requests)
        store.close()
        if entry == "accounting_only":
            clock.advance(TOTAL_SECONDS)
        store = store_at(host, clock, initialize=False)
        executor = executor_for(store, ledger)
        result = (_execute_reference_task(executor, host, reference_task) if entry == "retry" else
                  _restore_through_retry(executor, host, clock, store, task_info=info))
        assert result["status"] == "error"
        if entry == "accounting_only" or change in {"declared", "content", "size", "order"}:
            assert result["observability"]["error_category"] == STATE_REFUSED
        else:
            assert result["error"].startswith("reference_input_integrity_failed:")
        assert store._read()["cells"][TASK] == expected_cell
        assert ledger.calls_for(TASK) == before_calls
        assert before_calls[0]["state"] == "reserved" and before_calls[0]["input_tokens"] is None
        assert transport.requests == before_requests and len(transport.workspaces) == 1
        assert transport.stage_calls == 1 and clock.waits == []
        assert (transport.workspaces[0].workspace / "partial.txt").read_bytes() == b"synthetic partial\n"
    finally:
        store.close()
        ledger.close()


@pytest.mark.parametrize("gap", ["unobserved", "missing_usage"])
def test_native_resume_stable_reference_unknown_usage_remains_partial(host, monkeypatch, reference_task, gap):
    clock = Clock()
    store = store_at(host, clock)
    ledger = CostReceiptLedger(host / "cost.sqlite", run_id="offline-cell-run")
    transport = SDKTransport(monkeypatch, clock, [{"tokens": 100 if gap == "unobserved" else None, "error": RATE}])
    try:
        with monkeypatch.context() as patch:
            def interrupted(*args, **kwargs):
                raise SystemExit("synthetic interruption with unknown usage")
            owner, name = ((CodexTaskDeadline, "observe_turn") if gap == "unobserved" else
                           (codex_runner.CodexAgentRunner, "_settle_call"))
            patch.setattr(owner, name, interrupted)
            with pytest.raises(SystemExit):
                _execute_reference_task(executor_for(store, ledger), host, reference_task)
        expiry = store._read()["cells"][TASK]["expires_unix"]
        for _ in range(2):
            store.close()
            clock.advance(TOTAL_SECONDS)
            store = store_at(host, clock, initialize=False)
            result = _restore_through_retry(
                executor_for(store, ledger), host, clock, store, task_info=reference_task.info,
            )
            assert result["observability"]["error_category"] == EXHAUSTED
            cell = store._read()["cells"][TASK]
            assert cell["expires_unix"] == expiry and len(cell["attempts"]) == 1
            assert cell["continuation"]["turns"][0]["phase"] == ("in_flight" if gap == "unobserved" else "settled")
            calls = ledger.calls_for(TASK)
            assert len(calls) == 1 and calls[0]["input_tokens"] is calls[0]["output_tokens"] is None
            assert calls[0]["state"] == ("reserved" if gap == "unobserved" else "settled")
            assert ledger.receipt_for(TASK, BUCKET_PROBLEM_SOLVING).status == "partial"
            assert transport.count("turn/start") == 1 and transport.count("thread/resume") == 0
            assert len(transport.workspaces) == 1 and transport.stage_calls == 1 and clock.waits == []
            assert (transport.workspaces[0].workspace / "partial.txt").read_bytes() == b"synthetic partial\n"
        _assert_distinct_staging_with_same_declared_inputs(reference_task, 3)
    finally:
        store.close()
        ledger.close()


@pytest.mark.parametrize("condition", ["B", "C"])
@pytest.mark.parametrize("entry", ["runner", "outer_retry"])
@pytest.mark.parametrize("window", ["before_ledger", "before_ack"])
@pytest.mark.parametrize("stop", ["completed", "content_filter", "expired"])
def test_native_resume_crash_reconciliation_terminal_and_expired(
    host, monkeypatch, condition, entry, window, stop,
):
    clock = Clock()
    store = store_at(host, clock, condition=condition)
    ledger_path = host / "cost.sqlite"
    ledger = CostReceiptLedger(ledger_path, run_id="offline-cell-run")
    script = {"tokens": 100}
    if stop != "completed":
        script["error"] = "reason: content_filter" if stop == "content_filter" else RATE
    transport = SDKTransport(monkeypatch, clock, [script])
    try:
        with monkeypatch.context() as patch:
            def interrupted(*args, **kwargs):
                raise SystemExit("synthetic settlement interruption")

            owner, name = ((codex_runner.CodexAgentRunner, "_settle_call") if window == "before_ledger"
                           else (CodexTaskDeadline, "acknowledge_usage"))
            patch.setattr(owner, name, interrupted)
            with pytest.raises(SystemExit):
                execute(executor_for(store, ledger), host)

        cell = store._read()["cells"][TASK]
        turn = cell["continuation"]["turns"][0]
        assert turn["phase"] == "observed" and turn["after"]["input_tokens"] == 100
        assert cell["continuation"]["terminal_reason"] == (None if stop == "expired" else stop)
        assert cell["terminal_reason"] == ("content_filtered" if stop == "content_filter" else None)
        assert len(cell["attempts"]) == 1 and cell["expires_unix"] == cell["started_unix"] + TOTAL_SECONDS
        row = ledger.calls_for(TASK)[0]
        assert row["call_id"] == turn["call_id"]
        assert row["state"] == ("reserved" if window == "before_ledger" else "settled")
        assert row["input_tokens"] == (None if window == "before_ledger" else 100)
        partial = transport.workspaces[0].workspace / "partial.txt"
        original_partial = partial.read_bytes()
        native_requests = list(transport.requests)
        turn["phase"] = "settled"  # the only allowed change to the cell
        first_settlement = None

        for _ in range(3):
            store.close()
            ledger.close()
            clock.advance(TOTAL_SECONDS if stop == "expired" else 10)
            store = store_at(host, clock, condition=condition, initialize=False)
            ledger = CostReceiptLedger(ledger_path, run_id="offline-cell-run")
            executor = executor_for(store, ledger)
            ledger_changes = ledger._connection.total_changes
            result = (execute(executor, host) if entry == "runner" else
                      _restore_through_retry(executor, host, clock, store))
            assert result["status"] == "error"  # completion metadata is not a reconstructed result
            assert result["observability"]["error_category"] == (EXHAUSTED if stop == "expired" else STATE_REFUSED)
            assert store._read()["cells"][TASK] == cell
            calls = ledger.calls_for(TASK)
            assert len(calls) == 1 and calls[0]["call_id"] == row["call_id"]
            assert calls[0]["state"] == "settled"
            assert calls[0]["input_tokens"] == 100 and calls[0]["output_tokens"] == 20
            assert ledger._connection.total_changes - ledger_changes == (
                1 if first_settlement is None and window == "before_ledger" else 0
            )
            if first_settlement is None:
                first_settlement = calls[0]
            else:
                assert calls[0] == first_settlement  # equality guard, no second ledger commit
            assert ledger.receipt_for(TASK, BUCKET_PROBLEM_SOLVING).status == "partial"
            assert partial.read_bytes() == original_partial
            assert transport.requests == native_requests and len(transport.workspaces) == 1
            assert transport.stage_calls == 1 and clock.waits == []
    finally:
        store.close()
        ledger.close()


@pytest.mark.parametrize("change", [
    "missing_state", "checksum", "linked_state", "linked_workspace", "cross_task",
    "request", "provider", "settings", "ledger", "no_ledger", "missing_receipt",
    "conflicting_receipt", "rendered_request",
])
def test_native_resume_crash_reconciliation_refuses_unvalidated_state(host, monkeypatch, change):
    clock = Clock()
    store = store_at(host, clock)
    ledger_path = host / "cost.sqlite"
    ledger = CostReceiptLedger(ledger_path, run_id="offline-cell-run")
    other_ledger = None
    transport = SDKTransport(monkeypatch, clock, [{"tokens": 100}])
    try:
        with monkeypatch.context() as patch:
            def interrupted(*args, **kwargs):
                raise SystemExit("synthetic interruption before ledger commit")
            patch.setattr(codex_runner.CodexAgentRunner, "_settle_call", interrupted)
            with pytest.raises(SystemExit):
                execute(executor_for(store, ledger), host)
        partial = transport.workspaces[0].workspace / "partial.txt"
        original_partial = partial.read_bytes()
        task, instruction, settings, selected_ledger = TASK, None, SETTINGS, ledger
        if change == "cross_task":
            data = store._read()
            data["cells"][TASK2] = data["cells"][TASK]
            store._write(data)
            task = TASK2
        elif change == "rendered_request":
            data = store._read()
            data["cells"][TASK]["continuation"]["request_sha256"] = "0" * 64
            store._write(data)
        elif change in {"missing_state", "linked_state"}:
            store.path.rename(store.path.with_suffix(".retained"))
            if change == "linked_state":
                store.path.symlink_to(store.path.with_suffix(".retained"))
        elif change == "checksum":
            with store.path.open("ab") as output:
                output.write(b"damaged")
        elif change == "linked_workspace":
            workspace = transport.workspaces[0]
            retained = workspace.root / "retained-workspace"
            workspace.workspace.rename(retained)
            workspace.workspace.symlink_to(retained, target_is_directory=True)
            partial = retained / "partial.txt"
        elif change == "request":
            instruction = "Changed synthetic request."
        elif change == "provider":
            settings = replace(SETTINGS, provider_id="different-provider")
        elif change == "settings":
            settings = replace(SETTINGS, reasoning_effort="low")
        elif change == "ledger":
            other_ledger = CostReceiptLedger(host / "different.sqlite", run_id="offline-cell-run")
            selected_ledger = other_ledger
        elif change == "no_ledger":
            selected_ledger = None
        elif change == "missing_receipt":
            ledger.close()
            retained = host / "retained.sqlite"
            ledger_path.rename(retained)
            ledger = CostReceiptLedger(retained, run_id="offline-cell-run")
            other_ledger = CostReceiptLedger(ledger_path, run_id="offline-cell-run")
            selected_ledger = other_ledger
        elif change == "conflicting_receipt":
            ledger.settle(ledger.calls_for(TASK)[0]["call_id"],
                          usage=CallUsage(input_tokens=999, output_tokens=20), resolved_model=SETTINGS.model)

        before_calls = ledger.calls_for(TASK)
        before_requests = list(transport.requests)
        store.close()
        clock.advance(TOTAL_SECONDS)
        if change in {"missing_state", "checksum", "linked_state"}:
            with pytest.raises(TaskDeadlineRefused):
                store_at(host, clock, initialize=False)
        else:
            store = store_at(host, clock, initialize=False)
            expected_cell = store._read()["cells"][task]
            result = _restore_through_retry(
                executor_for(store, selected_ledger, settings=settings), host, clock, store,
                task=task, instruction=instruction,
            )
            assert result["observability"]["error_category"] == STATE_REFUSED
            assert store._read()["cells"][task] == expected_cell
        assert ledger.calls_for(TASK) == before_calls
        assert partial.read_bytes() == original_partial
        assert transport.requests == before_requests and len(transport.workspaces) == 1
        assert clock.waits == []
    finally:
        store.close()
        ledger.close()
        if other_ledger is not None:
            other_ledger.close()


@pytest.mark.parametrize("gap", ["unobserved", "missing_usage"])
def test_native_resume_crash_reconciliation_keeps_unknown_usage_partial(host, monkeypatch, gap):
    clock = Clock()
    store = store_at(host, clock)
    ledger_path = host / "cost.sqlite"
    ledger = CostReceiptLedger(ledger_path, run_id="offline-cell-run")
    transport = SDKTransport(monkeypatch, clock, [{"tokens": 100 if gap == "unobserved" else None, "error": RATE}])
    try:
        with monkeypatch.context() as patch:
            def interrupted(*args, **kwargs):
                raise SystemExit("synthetic interruption with unknown usage")
            owner, name = ((CodexTaskDeadline, "observe_turn") if gap == "unobserved"
                           else (codex_runner.CodexAgentRunner, "_settle_call"))
            patch.setattr(owner, name, interrupted)
            with pytest.raises(SystemExit):
                execute(executor_for(store, ledger), host)
        expiry = store._read()["cells"][TASK]["expires_unix"]
        partial = transport.workspaces[0].workspace / "partial.txt"
        original_partial = partial.read_bytes()
        for _ in range(2):
            store.close()
            ledger.close()
            clock.advance(TOTAL_SECONDS)
            store = store_at(host, clock, initialize=False)
            ledger = CostReceiptLedger(ledger_path, run_id="offline-cell-run")
            result = _restore_through_retry(executor_for(store, ledger), host, clock, store)
            assert result["observability"]["error_category"] == EXHAUSTED
            cell = store._read()["cells"][TASK]
            assert cell["expires_unix"] == expiry and len(cell["attempts"]) == 1
            assert cell["continuation"]["turns"][0]["phase"] == ("in_flight" if gap == "unobserved" else "settled")
            calls = ledger.calls_for(TASK)
            assert len(calls) == 1 and calls[0]["input_tokens"] is calls[0]["output_tokens"] is None
            assert calls[0]["state"] == ("reserved" if gap == "unobserved" else "settled")
            assert ledger.receipt_for(TASK, BUCKET_PROBLEM_SOLVING).status == "partial"
            assert partial.read_bytes() == original_partial
            assert transport.count("turn/start") == 1 and transport.count("thread/resume") == 0
            assert len(transport.workspaces) == 1 and clock.waits == []
    finally:
        store.close()
        ledger.close()


def test_native_resume_decreasing_cumulative_usage_refuses(host, monkeypatch):
    clock = Clock()
    store = store_at(host, clock)
    ledger = CostReceiptLedger(host / "cost.sqlite", run_id="offline-cell-run")
    transport = SDKTransport(monkeypatch, clock, [{"tokens": 100, "error": RATE}, {"tokens": 50}])
    try:
        execute(executor_for(store, ledger), host)
        result = execute(executor_for(store, ledger), host)
        assert result["observability"]["error_category"] == STATE_REFUSED
        assert transport.count("thread/start") == 1 and transport.count("thread/resume") == 1
        calls = ledger.calls_for(TASK)
        assert sorted(row["input_tokens"] for row in calls if row["input_tokens"] is not None) == [100]
        assert len(calls) == 2 and sum(row["input_tokens"] is None for row in calls) == 1
    finally:
        store.close()
        ledger.close()


@pytest.mark.parametrize("case", ["expired_restart", "in_flight_expiry", "single_attempt_bound", "new_cell", "new_repeat"])
def test_native_resume_deadline_admission_and_new_cell_identity(host, monkeypatch, case):
    clock = Clock()
    store = store_at(host, clock)
    transport = SDKTransport(monkeypatch, clock, [{"tokens": 100, "error": RATE}, {"tokens": 120, "seconds": 3000}])
    try:
        execute(executor_for(store), host)
        first_expiry = store.for_task(TASK).as_record()["expires_unix"]
        if case == "expired_restart":
            clock.advance(TOTAL_SECONDS)
            store.close()
            store = store_at(host, clock, initialize=False)
            result = execute(executor_for(store), host)
            assert result["observability"]["error_category"] == EXHAUSTED
            assert transport.count("thread/resume") == 0 and transport.count("turn/start") == 1
        elif case in {"new_cell", "new_repeat"}:
            clock.advance(20)
            task = TASK2
            if case == "new_repeat":
                store.close()
                store = store_at(host, clock, name="repeat2", repetition=2)
                task = TASK
            execute(executor_for(store), host, task=task)
            assert transport.count("thread/start") == 2 and transport.count("thread/resume") == 0
            assert store.for_task(task).as_record()["expires_unix"] > first_expiry
            assert len({workspace.root for workspace in transport.workspaces}) == 2
        else:
            if case == "in_flight_expiry":
                clock.advance(first_expiry - clock.now - 7)
            result = execute(executor_for(store), host)
            assert result["observability"]["error_category"] == (EXHAUSTED if case == "in_flight_expiry" else "timeout")
            assert transport.joins[1] == (7 if case == "in_flight_expiry" else ATTEMPT_SECONDS)
            assert transport.count("turn/interrupt") == 1
        assert (transport.workspaces[0].workspace / "partial.txt").exists()
    finally:
        store.close()


@pytest.mark.parametrize("phase", ["turn_start", "stream"])
@pytest.mark.parametrize("condition", ["A", "B", "C"])
def test_native_resume_content_filter_is_terminal_across_restart(host, monkeypatch, phase, condition):
    clock = Clock()
    store = store_at(host, clock, condition=condition)
    script = ({"turn_error": "reason: content_filter"} if phase == "turn_start" else
              {"tokens": 100, "error": "reason: content_filter"})
    transport = SDKTransport(monkeypatch, clock, [script])
    try:
        result = step2.run_with_infra_retries(
            lambda _: execute(executor_for(store), host), max_attempts=4,
            task_deadline=store.for_task(TASK), sleep=clock.sleep,
        )
        assert result["observability"]["error_category"] == "content_filtered" and clock.waits == []
        assert result["observability"]["task_deadline"]["terminal_reason"] == "content_filtered"
        store.close()
        store = store_at(host, clock, condition=condition, initialize=False)
        assert execute(executor_for(store), host)["observability"]["error_category"] == STATE_REFUSED
        assert transport.count("turn/start") == 1 and transport.count("thread/resume") == 0
    finally:
        store.close()


@pytest.mark.parametrize("stale", [False, True], ids=["current", "pre_resume"])
def test_native_resume_active_grader_template_source_bindings(stale):
    # The actual pre-resume identities are populated from the immutable baseline,
    # never from the closure under test.
    previous = (
        "dd970ba3f5fff8ae4d8e006dfc33c023804e3e32d32123681fb76feadd5f10df",
        "ec77798f9c2fba1043bc1015c855f3f75a96920e78e6b64c007e33785f2e2170",
    )
    for index, (module, plan) in enumerate(((comparison, comparison.load_plan()), (pilot, pilot.load_plan(pilot.PLAN)))):
        template = ROOT / module.GRADER
        current = step8.compute_grader_source_hash(template, yaml.safe_load(template.read_bytes()), batch_root=ROOT / "batch-runner")
        assert current != previous[index]
        if module is comparison:
            assert plan["shared"]["grading"]["template_source_sha256"] == current
            if stale:
                plan["shared"]["grading"]["template_source_sha256"] = previous[index]
        else:
            assert plan["dispatch_grading_identity"]["grader_template_source_hash"] == current
            assert pilot.DISPATCH_GRADING_IDENTITY["grader_template_source_hash"] == current
            if stale:
                plan["dispatch_grading_identity"]["grader_template_source_hash"] = previous[index]
                with pytest.raises(ValueError, match="grader_template_source_drift"):
                    identity._grader_identity(plan)
            else:
                assert identity._grader_identity(plan)["template_source_hash"] == current
        report = module.inspect_plan(plan)
        assert report["configuration_valid"] is not stale
        assert report["launch_allowed"] is report["full_220_allowed"] is False
        assert report["launch_blockers"] == list(module.LAUNCH_BLOCKERS)
    assert hashlib.sha256((ROOT / FOUNDRY).read_bytes()).hexdigest() == FOUNDRY_SHA256
    assert hashlib.sha256((ROOT / WORKFLOW).read_bytes()).hexdigest() == WORKFLOW_SHA256
    gate_plan = ghcp_gate.load_plan()
    reference_source = "batch-runner/core/reference_integrity.py"
    current_reference = hashlib.sha256((ROOT / reference_source).read_bytes()).hexdigest()
    assert gate_plan["source_pins"][reference_source] == ghcp_gate.PINNED_SOURCES[reference_source] == current_reference
    if stale:
        gate_plan["source_pins"][reference_source] = "13198897c189a9276494b78ea3359fc2e623211ab2f32554b81ab9b12d9cf19e"
    gate_report = ghcp_gate.inspect_plan(gate_plan)
    assert gate_report["configuration_valid"] is not stale
    assert all(gate_report[flag] is False for flag in ghcp_gate.FALSE_FLAGS)
    assert gate_report["launch_blockers"] == list(ghcp_gate.LAUNCH_BLOCKERS)
