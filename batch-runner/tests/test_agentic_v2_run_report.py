"""Whether a V2 run's report says what happened, and refuses to say more.

Most of these tests are about the things that would be easy to state wrongly: a
zero where a number is unknown, a graded count where nothing was graded, a
deliverable list that came from the model rather than from the disk. The
mismatch between V1's tool names and V2's is asserted here rather than merely
noted: the summary now offers a bucket for both vocabularies, and these tests
are what stops the two lists drifting apart again.
"""

from __future__ import annotations

import pytest

from core.agentic_v2_contract import TOOL_NAMES
from core.agentic_v2_run_report import (
    AGENTIC_V2_METRICS_SCHEMA_VERSION,
    SHARED_TOOL_NAMES,
    STATUS_ERROR,
    STATUS_SUCCESS,
    TOOL_NAMES_THE_REPORT_BUCKETS,
    TOOL_NAMES_THE_REPORT_KNOWS,
    ReportRowRefused,
    build_agentic_v2_metrics,
    build_result_row,
    finished_tasks,
    summarise_v2_run,
)
from core.agentic_v2_task_journal import (
    DECISION_RUN,
    DECISION_SKIP_FINISHED,
    TaskStanding,
)
from core.cost_receipts import (
    STATUS_COMPLETE,
    STATUS_NOT_RUN,
    STATUS_PARTIAL,
    STATUS_UNAVAILABLE,
)


TASK = "task-0001"


def _standing(
    *,
    attempts=1,
    abandoned=0,
    decision=DECISION_SKIP_FINISHED,
    task_id=TASK,
):
    return TaskStanding(
        task_id=task_id,
        attempts=attempts,
        abandoned_attempts=abandoned,
        last_closed=None,
        decision=decision,
        reason="for the test",
    )


def _ok_run(**extra):
    record = {"success": True, "deliverable_text": "the answer"}
    record.update(extra)
    return record


def _failed_run(error="compute_start_failed"):
    return {"success": False, "error": error}


def _receipt(status=STATUS_COMPLETE, total=1.25):
    return {
        "status": status,
        "estimated_cost_usd": total if status == STATUS_COMPLETE else None,
        "known_cost_usd": total,
        "currency": "USD",
    }


def _metrics(**kwargs):
    defaults = {
        "standing": _standing(),
        "task_wall_time_ms": 1234.0,
        "receipt": _receipt(),
    }
    defaults.update(kwargs)
    return build_agentic_v2_metrics(_ok_run(), **defaults)


# ── the two tool vocabularies ────────────────────────────────────────────


def test_the_report_s_tool_names_and_v2_s_share_only_finalize():
    """If this fails the report has changed and this module must follow it."""
    overlap = set(TOOL_NAMES) & set(TOOL_NAMES_THE_REPORT_KNOWS)
    assert overlap == {"finalize"}
    assert SHARED_TOOL_NAMES == ("finalize",)


def test_the_breakdown_has_a_bucket_for_every_name_either_runner_uses():
    """Seven of V2's eight had nowhere to land, so they were dropped.

    Including ``browser_run``, which three of the five tasks in the first paid
    stage ended on. The summary showed a lone non-zero ``finalize``.
    """
    assert set(TOOL_NAMES_THE_REPORT_BUCKETS) == set(TOOL_NAMES) | set(
        TOOL_NAMES_THE_REPORT_KNOWS
    )
    assert len(TOOL_NAMES_THE_REPORT_BUCKETS) == len(
        set(TOOL_NAMES_THE_REPORT_BUCKETS)
    )
    # V1's order, unchanged, at the front: an existing report's breakdown gains
    # keys rather than reordering.
    assert (
        TOOL_NAMES_THE_REPORT_BUCKETS[: len(TOOL_NAMES_THE_REPORT_KNOWS)]
        == TOOL_NAMES_THE_REPORT_KNOWS
    )


def test_the_report_buckets_under_exactly_these_names():
    """The constant and the summary that reads it, checked against each other.

    ``step6_report`` used to hold its own copy of the list. A copy is how the
    two came to disagree in the first place.
    """
    import step6_report

    row = {
        "task_wall_time_ms": 1.0,
        "tool_calls": 2,
        "tool_calls_by_name": {"browser_run": 1, "finalize": 1},
    }
    summary = step6_report._compute_agentic_metrics(
        {"results": [{"observability": {"agentic_metrics": row}}]}
    )

    assert set(summary["tool_calls_by_name"]) == set(TOOL_NAMES_THE_REPORT_BUCKETS)
    assert summary["tool_calls_by_name"]["browser_run"] == 1
    assert summary["total_tool_calls"] == 2


def test_every_v2_tool_gets_a_bucket_even_when_unused():
    metrics = _metrics()
    assert set(metrics["tool_calls_by_name"]) == set(TOOL_NAMES)
    assert metrics["tool_calls"] == 0


def test_v2_calls_are_counted_under_v2_names():
    metrics = _metrics(
        tool_calls=[
            {"tool_name": "exec_run"},
            {"tool_name": "exec_run"},
            {"tool_name": "finalize"},
        ]
    )
    assert metrics["tool_calls_by_name"]["exec_run"] == 2
    assert metrics["tool_calls_by_name"]["finalize"] == 1
    assert metrics["tool_calls"] == 3


def test_a_tool_the_contract_does_not_have_is_refused():
    with pytest.raises(ReportRowRefused, match="does not have"):
        _metrics(tool_calls=[{"tool_name": "run_python"}])


# ── money ────────────────────────────────────────────────────────────────


def test_a_complete_receipt_puts_its_total_in_the_headline():
    metrics = _metrics(receipt=_receipt(total=2.5))
    assert metrics["conservative_cost_usd"] == 2.5
    assert metrics["usage_complete"] is True


@pytest.mark.parametrize(
    "status", [STATUS_PARTIAL, STATUS_UNAVAILABLE, STATUS_NOT_RUN]
)
def test_an_unpriced_run_writes_no_amount_at_all(status):
    """Absent, never zero: the report sums this field as a float."""
    metrics = _metrics(receipt=_receipt(status=status))
    assert "conservative_cost_usd" not in metrics
    assert metrics["usage_complete"] is False
    assert metrics["agentic_v2_cost_receipt_status"] == status


def test_no_receipt_at_all_is_not_run_rather_than_free():
    metrics = _metrics(receipt=None)
    assert metrics["agentic_v2_cost_receipt_status"] == STATUS_NOT_RUN
    assert "conservative_cost_usd" not in metrics


def test_an_abandoned_attempt_keeps_the_amount_out_even_on_a_complete_receipt():
    """The retry was priced. The attempt that vanished was not."""
    metrics = _metrics(standing=_standing(attempts=2, abandoned=1))
    assert "conservative_cost_usd" not in metrics
    assert metrics["usage_complete"] is False
    assert metrics["agentic_v2_abandoned_attempts"] == 1


def test_a_receipt_status_the_vocabulary_does_not_have_is_refused():
    with pytest.raises(ReportRowRefused, match="not a receipt status"):
        _metrics(receipt={"status": "probably_fine"})


def test_a_receipt_whose_total_is_not_a_number_writes_nothing():
    metrics = _metrics(
        receipt={"status": STATUS_COMPLETE, "estimated_cost_usd": "1.25"}
    )
    assert "conservative_cost_usd" not in metrics


# ── what the report needs to see the task at all ─────────────────────────


def test_a_task_with_no_measured_time_is_refused():
    with pytest.raises(ReportRowRefused, match="invisible to the report"):
        build_agentic_v2_metrics(
            _ok_run(), standing=_standing(), task_wall_time_ms=None
        )


def test_token_counts_are_written_as_ints_the_report_will_accept():
    metrics = _metrics(input_tokens=1000, output_tokens=250)
    assert metrics["input_tokens"] == 1000
    assert type(metrics["input_tokens"]) is int
    assert type(metrics["output_tokens"]) is int


def test_absent_token_counts_stay_absent():
    metrics = _metrics()
    assert "input_tokens" not in metrics
    assert "output_tokens" not in metrics


def test_a_failure_carries_its_error_category_and_who_it_points_at():
    metrics = build_agentic_v2_metrics(
        _failed_run("compute_start_failed"),
        standing=_standing(decision=DECISION_RUN),
        task_wall_time_ms=99.0,
        receipt=_receipt(),
    )
    assert metrics["terminal_error_category"] == "compute_start_failed"
    assert metrics["agentic_v2_disposition"] == "infrastructure"
    assert metrics["agentic_v2_attributable_to"] == "environment"
    assert metrics["tool_errors"] == 1


def test_a_success_names_no_error():
    metrics = _metrics()
    assert metrics["terminal_error_category"] == ""
    assert metrics["agentic_v2_disposition"] is None
    assert metrics["tool_errors"] == 0
    assert metrics["schema_version"] == AGENTIC_V2_METRICS_SCHEMA_VERSION


# ── the row ──────────────────────────────────────────────────────────────


def test_a_successful_row_carries_the_collected_paths():
    row = build_result_row(
        _ok_run(),
        task_id=TASK,
        standing=_standing(),
        sector="Finance",
        occupation="Analyst",
        instruction="do the thing",
        deliverable_files=[f"deliverable_files/{TASK}/report.xlsx"],
        latency_ms=1234.0,
        metrics=_metrics(),
        receipt=_receipt(),
    )
    assert row["status"] == STATUS_SUCCESS
    assert row["deliverable_files_count"] == 1
    assert row["deliverable_text"] == "the answer"
    assert row["sector"] == "Finance"
    assert row["retried"] is False
    assert "error" not in row
    assert row["problem_solving_cost"]["status"] == STATUS_COMPLETE


def test_a_success_with_nothing_collected_is_refused():
    with pytest.raises(ReportRowRefused, match="produced nothing"):
        build_result_row(
            _ok_run(),
            task_id=TASK,
            standing=_standing(),
            deliverable_files=[],
            metrics=_metrics(),
        )


def test_a_failure_carrying_files_is_refused():
    """A half-collected answer is not the task's answer."""
    with pytest.raises(ReportRowRefused, match="not its answer"):
        build_result_row(
            _failed_run(),
            task_id=TASK,
            standing=_standing(decision=DECISION_RUN),
            deliverable_files=[f"deliverable_files/{TASK}/half.xlsx"],
            metrics=_metrics(),
        )


def test_a_failed_row_records_the_error_and_no_files():
    row = build_result_row(
        _failed_run("finalize_not_called"),
        task_id=TASK,
        standing=_standing(attempts=2, decision=DECISION_RUN),
        metrics=_metrics(),
    )
    assert row["status"] == STATUS_ERROR
    assert row["error"] == "finalize_not_called"
    assert row["deliverable_files"] == []
    assert row["retried"] is True


def test_a_row_without_a_receipt_gains_no_cost_key():
    row = build_result_row(
        _failed_run(),
        task_id=TASK,
        standing=_standing(decision=DECISION_RUN),
        metrics=_metrics(),
    )
    assert "problem_solving_cost" not in row


def test_the_metrics_are_copied_rather_than_shared():
    metrics = _metrics()
    row = build_result_row(
        _failed_run(),
        task_id=TASK,
        standing=_standing(decision=DECISION_RUN),
        metrics=metrics,
    )
    metrics["tool_calls"] = 999
    assert row["observability"]["agentic_metrics"]["tool_calls"] == 0


# ── the run ──────────────────────────────────────────────────────────────


def _row(status=STATUS_SUCCESS, disposition=None, abandoned=0):
    return {
        "status": status,
        "observability": {
            "agentic_metrics": {
                "agentic_v2_disposition": disposition,
                "agentic_v2_abandoned_attempts": abandoned,
            }
        },
    }


def test_a_run_that_did_not_reach_every_task_says_so():
    summary = summarise_v2_run(
        [_row(), _row(STATUS_ERROR, "infrastructure")],
        manifest_size=220,
        receipt_ceiling=STATUS_COMPLETE,
    )
    assert summary["executed"] == 2
    assert summary["succeeded"] == 1
    assert summary["failed"] == 1
    assert summary["not_reached"] == 218
    assert summary["manifest_size"] == 220


def test_grading_is_never_reported_as_zero():
    """Nothing graded and grading not attempted are different facts."""
    summary = summarise_v2_run([_row()], manifest_size=1, receipt_ceiling=STATUS_COMPLETE)
    assert summary["graded"] is None
    assert "separate run" in summary["graded_reason"]


def test_dispositions_are_counted_across_the_run():
    summary = summarise_v2_run(
        [
            _row(STATUS_ERROR, "infrastructure"),
            _row(STATUS_ERROR, "infrastructure"),
            _row(STATUS_ERROR, "semantic"),
            _row(),
        ],
        manifest_size=4,
        receipt_ceiling=STATUS_PARTIAL,
    )
    assert summary["dispositions"] == {"infrastructure": 2, "semantic": 1}


def test_a_partial_ceiling_makes_the_run_s_cost_not_fully_accounted():
    summary = summarise_v2_run(
        [_row(abandoned=1)], manifest_size=1, receipt_ceiling=STATUS_PARTIAL
    )
    assert summary["cost_is_fully_accounted"] is False
    assert summary["abandoned_attempts"] == 1


def test_a_complete_ceiling_says_the_cost_is_accounted():
    summary = summarise_v2_run(
        [_row()], manifest_size=1, receipt_ceiling=STATUS_COMPLETE
    )
    assert summary["cost_is_fully_accounted"] is True


def test_an_over_long_run_never_reports_a_negative_remainder():
    summary = summarise_v2_run(
        [_row(), _row()], manifest_size=1, receipt_ceiling=STATUS_COMPLETE
    )
    assert summary["not_reached"] == 0


def test_finished_tasks_keeps_manifest_order():
    standings = [
        _standing(task_id="task-one", decision=DECISION_SKIP_FINISHED),
        _standing(task_id="task-two", decision=DECISION_RUN),
        _standing(task_id="task-three", decision=DECISION_SKIP_FINISHED),
    ]
    assert finished_tasks(standings) == ("task-one", "task-three")
