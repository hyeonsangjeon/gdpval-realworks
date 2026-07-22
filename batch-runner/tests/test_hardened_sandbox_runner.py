"""Tests for current sandbox semantics on the common hardened substrate."""

from __future__ import annotations

import json
from types import SimpleNamespace

from core.agentic_budget import AgenticBudgetLedger
from core.hardened_sandbox_runner import HardenedSandboxRunner


SUBSTRATE = {
    "schema_version": "1.0",
    "task_image": "image@sha256:" + "a" * 64,
    "sha256": "b" * 64,
}


class ScriptedCompletions:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self.responses:
            raise AssertionError("completion script exhausted")
        return self.responses.pop(0)


class FakeProviderClient:
    def __init__(self, responses):
        self.chat = SimpleNamespace(
            completions=ScriptedCompletions(responses)
        )


def _response(code, description="generated"):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(
            content=f"```python\n{code}\n```\n{description}"
        ))],
        usage=SimpleNamespace(
            prompt_tokens=100,
            completion_tokens=20,
            prompt_tokens_details=SimpleNamespace(cached_tokens=5),
        ),
    )


class FakeBackend:
    def __init__(self, inspections, **options):
        self.inspections = list(inspections)
        self.options = options
        self.calls = []
        self.closed = False
        self._best = None

    def start(self, timeout_seconds=1200.0):
        self.calls.append("start")
        return {
            "ok": True,
            "data": {
                "input_merkle_root": "c" * 64,
                "selection_recomputation_sha256": "e" * 64,
                "provider_classification": "approved_public_gdpval",
                "substrate_manifest": SUBSTRATE,
            },
        }

    def reset_work(self, timeout_seconds=1200.0):
        self.calls.append("reset_work")
        return {"ok": True, "data": {}}

    def run_python(self, source, timeout_seconds):
        self.calls.append(("run_python", source, timeout_seconds))
        return {
            "ok": True,
            "data": {"returncode": 0, "stdout_tail": "", "stderr_tail": ""},
        }

    def inspect_artifacts(self, timeout_seconds=1200.0):
        self.calls.append("inspect_artifacts")
        return self.inspections.pop(0)

    def finalize(self, deliverables, summary, timeout_seconds=1200.0):
        self.calls.append(("finalize", list(deliverables)))
        self._best = {
            "success": True,
            "text": summary,
            "deliverable_text": summary,
            "files": [{"filename": "report.txt", "content": b"report"}],
        }
        return {"ok": True, "data": {"artifact_count": 1}}

    def best_result(self):
        return self._best

    def close(self):
        self.closed = True


def _inspection(ok):
    return {
        "ok": ok,
        "error_type": None if ok else "artifact_verification_failed",
        "data": {
            "artifacts": ([{
                "path": "report.txt",
                "size_bytes": 6,
                "sha256": "d" * 64,
                "kind": "text",
                "openable": True,
            }] if ok else []),
            "contract": {
                "ok": ok,
                "blocking_errors": [] if ok else ["missing report"],
                "warnings": [],
                "matched_primary": ["report.txt"] if ok else [],
                "generated_count": 1 if ok else 0,
            },
        },
    }


def _runner(tmp_path, responses, inspections):
    provider = FakeProviderClient(responses)
    backends = []

    def backend_factory(**kwargs):
        backend = FakeBackend(inspections, **kwargs)
        backends.append(backend)
        return backend

    authorization = []
    runner = HardenedSandboxRunner(
        client_factory=lambda: provider,
        backend_factory=backend_factory,
        budget_ledger=AgenticBudgetLedger(tmp_path / "budget.sqlite3"),
        authorize_request=lambda scope, request_id, context: authorization.append(
            (scope, request_id, context)
        ),
        run_id="paired-run",
        condition_name="baseline",
        model_name="model",
        limits={"max_api_attempts": 2, "max_model_iterations": 2},
        pricing={
            "input_per_million": "0",
            "output_per_million": "0",
            "cached_input_per_million": "0",
        },
        aggregate_budget={
            "paired_run_id": "paired-run",
            "condition": {
                "attempts": 40,
                "input_tokens": 1000000,
                "output_tokens": 100000,
                "cost_usd": "25",
            },
            "paired_run": {
                "attempts": 80,
                "input_tokens": 2000000,
                "output_tokens": 200000,
                "cost_usd": "50",
            },
        },
        image=SUBSTRATE["task_image"],
        metrics={"enabled": True},
        manifest={"enabled": True, "include_in_files": True},
    )
    return runner, provider, backends, authorization


def test_hardened_baseline_runs_once_on_verified_first_attempt(tmp_path):
    runner, provider, backends, authorization = _runner(
        tmp_path,
        [_response("open('report.txt', 'w').write('report')")],
        [_inspection(True), _inspection(True)],
    )

    result = runner.run(
        "Create report.txt",
        "model",
        run_id="paired-run",
        condition_name="baseline",
        task_id="task-1",
    )

    assert result["success"] is True
    assert result["final_status"] == "ok"
    assert result["substrate_manifest"] == SUBSTRATE
    assert [item["filename"] for item in result["files"]] == ["report.txt"]
    assert len(provider.chat.completions.calls) == 1
    assert provider.chat.completions.calls[0]["max_completion_tokens"] == 8192
    assert len(authorization) == 1
    assert authorization[0][2]["selection_recomputation_sha256"] == "e" * 64
    timing = result["budget_metrics"].pop("time_to_valid_artifact_ms")
    assert timing is not None and timing >= 0
    assert result["budget_metrics"] == {
        "schema_version": "1.0",
        "model_api_calls": 1,
        "input_tokens": 100,
        "output_tokens": 20,
        "cached_tokens": 5,
        "conservative_cost_usd": "0",
        "usage_complete": True,
    }
    assert backends[0].calls.count("reset_work") == 1
    assert backends[0].closed is True


def test_hardened_baseline_preserves_remote_reference_ids(tmp_path):
    runner, provider, backends, _ = _runner(
        tmp_path,
        [_response("open('report.txt', 'w').write('report')")],
        [_inspection(True), _inspection(True)],
    )
    reference_id = "reference_files/hash/input.xlsx"

    result = runner.run(
        "Create report.txt from input.xlsx",
        "model",
        reference_files=[reference_id],
        run_id="paired-run",
        condition_name="baseline",
        task_id="task-1",
    )

    assert result["success"] is True
    assert backends[0].options["reference_files"] == [reference_id]
    prompt = json.dumps(provider.chat.completions.calls[0]["messages"])
    assert "input.xlsx" in prompt
    assert "File not found" not in prompt


def test_hardened_baseline_regenerates_complete_solution_once(tmp_path):
    runner, provider, backends, authorization = _runner(
        tmp_path,
        [
            _response("open('bad.txt', 'w').write('bad')"),
            _response("open('report.txt', 'w').write('report')", "repaired"),
        ],
        [_inspection(False), _inspection(True), _inspection(True)],
    )

    result = runner.run(
        "Create report.txt",
        "model",
        run_id="paired-run",
        condition_name="baseline",
        task_id="task-1",
    )

    assert result["success"] is True
    assert result["final_status"] == "repaired_ok"
    assert len(provider.chat.completions.calls) == 2
    assert len(authorization) == 2
    assert backends[0].calls.count("reset_work") == 2
    assert len([call for call in backends[0].calls if isinstance(call, tuple) and call[0] == "run_python"]) == 2
    assert runner.budget_ledger.usage('["paired_run","paired-run"]').attempts == 2


def test_hardened_reconciliation_failure_marks_usage_incomplete(tmp_path):
    runner, _, _, _ = _runner(
        tmp_path,
        [_response("open('report.txt', 'w').write('report')")],
        [_inspection(True)],
    )

    def fail_reconciliation(**kwargs):
        raise ValueError("reservation mismatch")

    runner.budget_ledger.reconcile_many = fail_reconciliation
    result = runner.run(
        "Create report.txt",
        "model",
        run_id="paired-run",
        condition_name="baseline",
        task_id="task-1",
    )

    assert result["success"] is False
    assert result["budget_metrics"]["usage_complete"] is False


def test_hardened_finalize_failure_preserves_verified_candidate(tmp_path):
    runner, _, _, _ = _runner(tmp_path, [], [])

    class CandidateBackend(FakeBackend):
        def inspect_artifacts(self, timeout_seconds=1200.0):
            self.calls.append("inspect_artifacts")
            self._best = {
                "success": False,
                "text": "candidate",
                "deliverable_text": "candidate",
                "files": [{"filename": "report.txt", "content": b"candidate"}],
            }
            return _inspection(True)

        def finalize(self, deliverables, summary, timeout_seconds=1200.0):
            self.calls.append(("finalize", list(deliverables)))
            return {
                "ok": False,
                "error_type": "selected_deliverable_verification_failed",
            }

    backend = CandidateBackend([])
    runner._backend = backend
    runner._run_started = __import__("time").monotonic()
    runner._first_model_dispatch = runner._run_started

    _, result = runner._execute(
        "open('report.txt','w').write('report')", [], {}
    )

    assert result["success"] is False
    assert result["error"] == "selected_deliverable_verification_failed"
    assert result["files"] == [
        {"filename": "report.txt", "content": b"candidate"}
    ]


def test_hardened_start_and_close_failure_returns_structured_metrics(tmp_path):
    runner, _, _, _ = _runner(tmp_path, [], [])

    class StartCloseFailureBackend(FakeBackend):
        def start(self, timeout_seconds=1200.0):
            raise RuntimeError("startup exploded")

        def close(self):
            raise RuntimeError("cleanup exploded")

    runner.backend_factory = lambda **kwargs: StartCloseFailureBackend([])

    result = runner.run(
        "Create report.txt",
        "model",
        run_id="paired-run",
        condition_name="baseline",
        task_id="task-1",
    )

    assert result["success"] is False
    assert result["error"] == "compute_cleanup_failed"
    assert result["prior_error"] == "runner_internal_error"
    assert result["budget_metrics"]["usage_complete"] is False