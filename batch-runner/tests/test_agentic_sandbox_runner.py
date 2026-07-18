"""Scripted, model-free tests for the agentic solver state machine."""

from __future__ import annotations

import json
from types import SimpleNamespace

from core.agentic_budget import AgenticBudgetLedger
from core.agentic_sandbox_runner import AgenticPricing, AgenticSandboxRunner


def _usage(input_tokens=100, output_tokens=20, cached_tokens=5):
    return SimpleNamespace(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        input_tokens_details=SimpleNamespace(cached_tokens=cached_tokens),
    )


def _response(*items, usage=True):
    return SimpleNamespace(
        output=list(items),
        usage=_usage() if usage else None,
    )


def _call(call_id, name, arguments):
    return {
        "type": "function_call",
        "call_id": call_id,
        "name": name,
        "arguments": json.dumps(arguments),
    }


def _message(text="done"):
    return {
        "type": "message",
        "role": "assistant",
        "content": [{"type": "output_text", "text": text}],
    }


class ScriptedResponses:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self.responses:
            raise AssertionError("script exhausted")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class FakeClient:
    def __init__(self, responses):
        self.responses = responses


class FakeBackend:
    def __init__(self, **_):
        self.calls = []
        self.closed = False
        self.result = None

    def start(self, timeout_seconds=1200.0):
        return {
            "ok": True,
            "data": {
                "input_count": 1,
                "substrate_manifest": {
                    "schema_version": "1.0",
                    "sha256": "a" * 64,
                },
            },
        }

    def inspect_workspace(self, timeout_seconds=1200.0):
        self.calls.append("inspect_workspace")
        return {"ok": True, "data": {"input_count": 1, "work_count": 0}}

    def inspect_environment(self, timeout_seconds=1200.0):
        self.calls.append("inspect_environment")
        return {"ok": True, "data": {"python": "3.11"}}

    def run_python(self, source, timeout_seconds):
        self.calls.append("run_python")
        return {"ok": True, "data": {"returncode": 0}}

    def run_ffmpeg(self, operation, timeout_seconds):
        self.calls.append("run_ffmpeg")
        return {"ok": True, "data": {"returncode": 0}}

    def inspect_artifacts(self, timeout_seconds=1200.0):
        self.calls.append("inspect_artifacts")
        self.result = {
            "success": False,
            "text": "",
            "deliverable_text": "",
            "files": [{"filename": "report.txt", "content": b"verified"}],
        }
        return {"ok": True, "data": {"verified_count": 1}}

    def finalize(self, deliverables, summary, timeout_seconds=1200.0):
        self.calls.append("finalize")
        self.result = {
            "success": True,
            "text": summary,
            "deliverable_text": summary,
            "files": [{"filename": deliverables[0], "content": b"ok"}],
        }
        return {"ok": True, "data": {"verified_count": 1}}

    def best_result(self):
        return self.result

    def close(self):
        self.closed = True


def _runner(
    tmp_path, responses, backend_class=FakeBackend, **limit_overrides
):
    scripted = ScriptedResponses(responses)
    backends = []

    def backend_factory(**kwargs):
        backend = backend_class(**kwargs)
        backends.append(backend)
        return backend

    runner = AgenticSandboxRunner(
        FakeClient(scripted),
        non_paid_test_mode=True,
        backend_factory=backend_factory,
        budget_ledger=AgenticBudgetLedger(tmp_path / "budget.sqlite3"),
        authorize_request=lambda scope, request_id, context: None,
        limits=limit_overrides,
        pricing={
            "input_per_million": "0",
            "output_per_million": "0",
            "cached_input_per_million": "0",
        },
    )
    return runner, scripted, backends


def test_inspect_run_inspect_finalize_success(tmp_path):
    runner, scripted, backends = _runner(tmp_path, [
        _response(_call("c1", "inspect_workspace", {})),
        _response(_call("c2", "run_python", {
            "source": "print('ok')", "timeout_seconds": 5,
        })),
        _response(_call("c3", "inspect_artifacts", {})),
        _response(_call("c4", "finalize", {
            "deliverables": ["report.txt"], "summary": "complete",
        })),
    ])

    result = runner.run("Create a report", "model", task_id="task-1")

    assert result["success"] is True
    assert result["text"] == "complete"
    assert result["agentic_metrics"]["model_api_calls"] == 4
    assert result["agentic_metrics"]["tool_calls"] == 4
    assert backends[0].calls == [
        "inspect_workspace", "run_python", "inspect_artifacts", "finalize",
    ]
    assert backends[0].closed is True
    assert all(call["parallel_tool_calls"] is False for call in scripted.calls)


def test_plain_final_gets_one_finalize_required_correction(tmp_path):
    runner, scripted, _ = _runner(tmp_path, [
        _response(_message()),
        _response(_call("c1", "finalize", {
            "deliverables": ["report.txt"], "summary": "complete",
        })),
    ])

    result = runner.run("Create a report", "model", task_id="task-1")

    assert result["success"] is True
    assert result["agentic_metrics"]["finalize_required_corrections"] == 1
    assert "successful finalize tool call" in scripted.calls[1]["input"][-1]["content"]


def test_missing_usage_fails_closed_and_keeps_reservation(tmp_path):
    runner, _, _ = _runner(tmp_path, [_response(_message(), usage=False)])

    result = runner.run("Create a report", "model", task_id="task-1")

    assert result["success"] is False
    assert result["error"] == "usage_incomplete"
    assert result["agentic_metrics"]["usage_complete"] is False
    usage = runner.ledger.usage('["local-nonpaid","condition_a","task-1"]')
    assert usage.attempts == 1
    assert usage.output_tokens == 8192


def test_resume_after_unreconciled_reservation_reports_ledger_cost(tmp_path):
    runner, scripted, _ = _runner(
        tmp_path, [_response(_message(), usage=False)]
    )
    runner.pricing = AgenticPricing.from_options({
        "input_per_million": "1",
        "output_per_million": "10",
        "cached_input_per_million": "1",
    })

    first = runner.run("Create a report", "model", task_id="task-1")
    second = runner.run("Create a report", "model", task_id="task-1")

    assert first["agentic_metrics"]["conservative_cost_usd"] != "0"
    assert second["error"] == "authorization_or_reservation_failed"
    assert second["agentic_metrics"]["conservative_cost_usd"] == first[
        "agentic_metrics"
    ]["conservative_cost_usd"]
    assert second["agentic_metrics"]["usage_complete"] is False
    assert len(scripted.calls) == 1


def test_repeated_identical_tool_error_stops_loop(tmp_path):
    duplicate = _call("c1", "run_python", {
        "source": "print('ok')", "timeout_seconds": 5,
    })
    runner, _, _ = _runner(tmp_path, [
        _response(duplicate),
        _response({**duplicate, "call_id": "c2"}),
        _response({**duplicate, "call_id": "c3"}),
        _response({**duplicate, "call_id": "c4"}),
    ])

    result = runner.run("Create a report", "model", task_id="task-1")

    assert result["success"] is False
    assert result["error"] == "duplicate_tool_request"


def test_normalized_identical_errors_stop_after_second_dispatch(tmp_path):
    class ErrorBackend(FakeBackend):
        def run_python(self, source, timeout_seconds):
            self.calls.append("run_python")
            suffix = "123 at /tmp/first" if len(self.calls) == 1 else "999 at /tmp/second"
            return {
                "ok": False,
                "error_type": "python_execution_failed",
                "retryable": True,
                "data": {"stderr_tail": f"ValueError item {suffix}"},
            }

    runner, scripted, backends = _runner(
        tmp_path,
        [
            _response(_call("c1", "run_python", {
                "source": "raise ValueError('first')", "timeout_seconds": 5,
            })),
            _response(_call("c2", "run_python", {
                "source": "raise ValueError('second')", "timeout_seconds": 5,
            })),
        ],
        backend_class=ErrorBackend,
    )

    result = runner.run("Create a report", "model", task_id="task-1")

    assert result["error"] == "repeated_error_limit"
    assert result["agentic_metrics"]["tool_calls"] == 2
    assert result["agentic_metrics"]["model_api_calls"] == 2
    assert backends[0].calls == ["run_python", "run_python"]
    assert len(scripted.calls) == 2


def test_invalid_tool_batch_executes_nothing(tmp_path):
    runner, _, backends = _runner(tmp_path, [
        _response(
            _call("c1", "inspect_workspace", {}),
            _call("c2", "unexpected_tool", {}),
        ),
    ])

    result = runner.run("Create a report", "model", task_id="task-1")

    assert result["success"] is False
    assert result["error"] == "unknown_tool"
    assert backends[0].calls == []


def test_duplicate_function_call_ids_execute_nothing(tmp_path):
    runner, _, backends = _runner(tmp_path, [
        _response(
            _call("same", "inspect_workspace", {}),
            _call("same", "inspect_environment", {}),
        ),
    ])

    result = runner.run("Create a report", "model", task_id="task-1")

    assert result["error"] == "invalid_function_call_id"
    assert backends[0].calls == []


def test_authorization_failure_occurs_before_api_call(tmp_path):
    scripted = ScriptedResponses([_response(_message())])
    backend = FakeBackend()
    runner = AgenticSandboxRunner(
        FakeClient(scripted),
        non_paid_test_mode=True,
        backend_factory=lambda **_: backend,
        budget_ledger=AgenticBudgetLedger(tmp_path / "budget.sqlite3"),
        authorize_request=lambda scope, request_id, context: (_ for _ in ()).throw(
            PermissionError("not approved")
        ),
        pricing={
            "input_per_million": "0", "output_per_million": "0",
            "cached_input_per_million": "0",
        },
    )

    result = runner.run("Create a report", "model", task_id="task-1")

    assert result["error"] == "authorization_or_reservation_failed"
    assert scripted.calls == []
    assert runner.ledger.usage(
        '["local-nonpaid","condition_a","task-1"]'
    ).attempts == 1


def test_authorization_happens_before_deferred_client_factory(tmp_path):
    events = []
    scripted = ScriptedResponses([_response(_message())])
    backend = FakeBackend()

    def authorize(scope, request_id, context):
        events.append("authorize")
        assert context["runtime_preflight_passed"] is True

    def client_factory():
        events.append("client_factory")
        return FakeClient(scripted)

    ledger = AgenticBudgetLedger(tmp_path / "budget.sqlite3")
    original_reserve_many = ledger.reserve_many

    def reserve_many(**kwargs):
        events.append("reserve")
        return original_reserve_many(**kwargs)

    ledger.reserve_many = reserve_many
    runner = AgenticSandboxRunner(
        client_factory=client_factory,
        backend_factory=lambda **_: backend,
        budget_ledger=ledger,
        authorize_request=authorize,
        pricing={
            "input_per_million": "0", "output_per_million": "0",
            "cached_input_per_million": "0",
        },
    )

    result = runner.run("Create a report", "model", task_id="task-1")

    assert events[:3] == ["reserve", "authorize", "client_factory"]
    assert scripted.calls
    assert result["success"] is False


def test_later_model_failure_preserves_best_verified_files(tmp_path):
    runner, _, _ = _runner(tmp_path, [
        _response(_call("c1", "inspect_artifacts", {})),
        RuntimeError("upstream failed"),
    ])

    result = runner.run("Create a report", "model", task_id="task-1")

    assert result["success"] is False
    assert result["error"] == "model_api_error"
    assert result["files"] == [
        {"filename": "report.txt", "content": b"verified"}
    ]
    assert result["agentic_metrics"]["usage_complete"] is False
    assert result["agentic_metrics"]["time_to_valid_artifact_ms"] is not None


def test_success_is_not_returned_when_compute_cleanup_fails(tmp_path):
    class CleanupFailureBackend(FakeBackend):
        def close(self):
            raise RuntimeError("remote close failed")

    runner, _, _ = _runner(
        tmp_path,
        [_response(_call("c1", "finalize", {
            "deliverables": ["report.txt"], "summary": "complete",
        }))],
        backend_class=CleanupFailureBackend,
    )

    result = runner.run("Create a report", "model", task_id="task-1")

    assert result["success"] is False
    assert result["error"] == "compute_cleanup_failed"
    assert result["prior_error"] is None
    assert result["files"] == [
        {"filename": "report.txt", "content": b"ok"}
    ]


def test_model_failure_and_cleanup_failure_preserve_sealed_evidence(tmp_path):
    class CleanupFailureBackend(FakeBackend):
        def close(self):
            raise RuntimeError("remote close failed")

    runner, _, _ = _runner(
        tmp_path,
        [
            _response(_call("c1", "inspect_artifacts", {})),
            RuntimeError("upstream failed"),
        ],
        backend_class=CleanupFailureBackend,
    )

    result = runner.run("Create a report", "model", task_id="task-1")

    assert result["success"] is False
    assert result["error"] == "compute_cleanup_failed"
    assert result["prior_error"] == "model_api_error"
    assert result["files"] == [
        {"filename": "report.txt", "content": b"verified"}
    ]
    assert result["agentic_metrics"]["usage_complete"] is False