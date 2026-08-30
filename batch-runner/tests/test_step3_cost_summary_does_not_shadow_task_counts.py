"""The cost summary must not overwrite the task counts in the Step 3 report.

Why this exists
---------------
`format_results()` binds ``summary = inference["summary"]`` near the top and
still needs it far below, for the success rate and the report's count table.
Between those two points sat::

    for field, summary in cost_summaries.items():
        final_json.setdefault("cost_summary", {})[field] = summary

The loop variable rebound the same name. From there on, every read of
``summary`` returned a *cost receipt* instead of the task counts.

The loop body only runs when the experiment actually produced a receipt, so
every run before cost instrumentation existed skipped it and the report was
fine. The first run that produced one -- the exp026c cost smoke, GitHub run
33302056462 -- died in Step 3 with ``KeyError: 'total'`` after the paid
inference had already succeeded.

The crash was the lucky outcome. A receipt carries ``model_calls`` and
``usage``, not ``total``/``success``/``error``; had it happened to share a key
name, Step 3 would have written a receipt's numbers into the report's task
table and published them as if they were task counts. So this test does not
just check that formatting survives -- it checks the printed numbers are the
task counts, which is the property that was actually at risk.
"""

from __future__ import annotations

import json

import pytest

import step3_format_results as step3
from core.prepared_fingerprint import prepared_fingerprint
from core.result_fingerprint import inference_result_fingerprint

# Deliberately unlike anything a receipt carries, so a wrong-source number is
# recognisable on sight rather than merely unequal.
TOTAL_TASKS = 7
SUCCESS_TASKS = 5
ERROR_TASKS = 2

# Copied field-for-field from the receipt Step 2 wrote in run 33302056462 --
# one task, a generation call and a Self-QA call, both against a model the
# price table had no entry for -- so the fixture cannot drift into a shape the
# producer never emits. Only `price_table_sha256` is substituted, since the
# real digest pins a file this test has no reason to depend on.
RECEIPT = {
    "schema_version": "cost-receipt-v1",
    "status": "partial",
    "currency": "USD",
    "estimated_cost_usd": None,
    "known_cost_usd": 0.0,
    "model_cost_usd": 0.0,
    "runtime_cost_usd": 0.0,
    "model_calls": 2,
    "usage": {
        "input_tokens": 5794,
        "cached_input_tokens": 0,
        "output_tokens": 7000,
        "reasoning_tokens": 1775,
    },
    "components": [
        {
            "name": "generation",
            "stage": "generation",
            "retry_kind": "none",
            "status": "partial",
            "model_calls": 1,
            "known_cost_usd": 0.0,
            "usage": {
                "input_tokens": 3949,
                "cached_input_tokens": 0,
                "output_tokens": 6910,
                "reasoning_tokens": 1775,
            },
            "missing_reasons": ["price_missing"],
        },
        {
            "name": "self_qa",
            "stage": "self_qa",
            "retry_kind": "none",
            "status": "partial",
            "model_calls": 1,
            "known_cost_usd": 0.0,
            "usage": {
                "input_tokens": 1845,
                "cached_input_tokens": 0,
                "output_tokens": 90,
                "reasoning_tokens": 0,
            },
            "missing_reasons": ["price_missing"],
        },
    ],
    "price_table_sha256": "d" * 64,
    "missing_reasons": ["price_missing"],
}


def _task_ids() -> list[str]:
    return [f"task-{i}" for i in range(TOTAL_TASKS)]


def _write_workspace(workspace, *, with_receipt: bool) -> None:
    task_ids = _task_ids()
    prepared = {
        "experiment_id": "exp998",
        "experiment_name": "shadowing regression",
        "publication_generation": "exp998:100:1",
        "source": "student/exp998",
        "task_scope": {"task_ids": task_ids},
        "tasks": [
            {"task_id": tid, "sector": "Finance", "occupation": "Accountants"}
            for tid in task_ids
        ],
    }
    prepared["prepared_fingerprint"] = prepared_fingerprint(prepared)

    results = []
    for index, tid in enumerate(task_ids):
        succeeded = index < SUCCESS_TASKS
        row = {
            "task_id": tid,
            "status": "success" if succeeded else "error",
            "deliverable_text": "a deliverable" if succeeded else "",
            "deliverable_files": [],
            "latency_ms": 1000,
        }
        if with_receipt and succeeded:
            row["problem_solving_cost"] = json.loads(json.dumps(RECEIPT))
        results.append(row)

    inference = {
        "experiment_id": "exp998",
        "experiment_name": "shadowing regression",
        "publication_generation": "exp998:100:1",
        "source": "student/exp998",
        "prepared_fingerprint": prepared["prepared_fingerprint"],
        "ordered_task_ids": task_ids,
        "condition": "condition_a",
        "execution_mode": "sandbox",
        "model": "gpt-5.4",
        "started_at": "2026-08-30T08:00:00Z",
        "completed_at": "2026-08-30T08:10:00Z",
        "resume_rounds_used": 0,
        "results": results,
        "summary": {
            "total": TOTAL_TASKS,
            "success": SUCCESS_TASKS,
            "error": ERROR_TASKS,
            "qa_failed": 0,
        },
    }
    inference["result_fingerprint"] = inference_result_fingerprint(inference)

    (workspace / "step1_tasks_prepared.json").write_text(
        json.dumps(prepared), encoding="utf-8"
    )
    (workspace / "step2_inference_results.json").write_text(
        json.dumps(inference), encoding="utf-8"
    )


def _run(tmp_path, monkeypatch, *, with_receipt: bool) -> str:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    root = tmp_path / "batch-runner"
    root.mkdir()
    _write_workspace(workspace, with_receipt=with_receipt)
    monkeypatch.setattr(step3, "WORKSPACE_DIR", workspace)
    monkeypatch.setattr(step3, "BATCH_RUNNER_ROOT", root)
    step3.format_results()
    return (root / "results" / "exp998" / "exp998.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("with_receipt", [False, True], ids=["no_receipt", "with_receipt"])
def test_report_counts_come_from_the_inference_summary(tmp_path, monkeypatch, with_receipt):
    """The same counts must print whether or not a cost receipt is present.

    Running both ways is the point: the uninstrumented case is what always
    worked, so it pins the expected output independently of the fix, and the
    instrumented case is the one that used to crash.
    """
    report = _run(tmp_path, monkeypatch, with_receipt=with_receipt)

    assert f"| Total tasks | {TOTAL_TASKS} |" in report, report
    assert f"| Error | {ERROR_TASKS} |" in report, report
    # 5/7 -> 71%. A receipt-sourced numerator would not land here.
    assert f"| Success | {SUCCESS_TASKS} (71%) |" in report, report


def test_the_receipt_is_still_published_under_its_own_key(tmp_path, monkeypatch):
    """Guard the guard: renaming the loop variable must not drop the summary."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    root = tmp_path / "batch-runner"
    root.mkdir()
    _write_workspace(workspace, with_receipt=True)
    monkeypatch.setattr(step3, "WORKSPACE_DIR", workspace)
    monkeypatch.setattr(step3, "BATCH_RUNNER_ROOT", root)
    step3.format_results()

    payload = json.loads(
        (root / "results" / "exp998" / "exp998.json").read_text(encoding="utf-8")
    )
    receipt = payload["cost_summary"]["problem_solving_cost"]
    assert receipt["schema_version"] == "cost-receipt-v1"
    # Both task counts, from the two sides of the same run: 7 tasks were run,
    # 5 of them carried a receipt. Asserting the pair is what catches a summary
    # that reached the file with one of its two sources overwritten.
    assert receipt["total_tasks"] == TOTAL_TASKS
    assert receipt["receipt_tasks"] == SUCCESS_TASKS
    # The report's task table and the receipt are separate facts about the same
    # run; publishing one must not have consumed the other.
    assert payload["summary"]["total_tasks"] == TOTAL_TASKS


# The run-level `status` this summary carries is deliberately not asserted here.
# On this commit a run whose every receipt is `partial` still rolls up as
# `not_run`, because the roll-up derives its status from whether any amount was
# confirmed rather than from the receipts themselves. That is a real defect --
# the exp026c smoke reproduced it on a run that made two paid model calls -- but
# it lives in core/cost_projection.py, which is an input to the grader source
# hash and therefore cannot be changed while grading shards are in flight. It is
# fixed separately, against the rule already carried by core/cost_receipts.py
# `_summary_status` and scripts/cost-receipt.mjs. Pinning today's wrong value
# here would only have to be un-pinned by that change.
