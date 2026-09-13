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
    """The three fields that say what went wrong and whose fault it was.

    ``tool_errors`` is deliberately not one of them. This task's compute never
    started, so no tool was ever called -- and the field used to read ``1``
    here, which is the ending written into a field about tools. See
    :func:`test_a_tool_error_is_a_call_that_came_back_not_ok`.
    """
    metrics = build_agentic_v2_metrics(
        _failed_run("compute_start_failed"),
        standing=_standing(decision=DECISION_RUN),
        task_wall_time_ms=99.0,
        receipt=_receipt(),
    )
    assert metrics["terminal_error_category"] == "compute_start_failed"
    assert metrics["agentic_v2_disposition"] == "infrastructure"
    assert metrics["agentic_v2_attributable_to"] == "environment"
    assert metrics["tool_errors"] == 0


def test_a_success_names_no_error():
    metrics = _metrics()
    assert metrics["terminal_error_category"] == ""
    assert metrics["agentic_v2_disposition"] is None
    assert metrics["tool_errors"] == 0
    assert metrics["schema_version"] == AGENTIC_V2_METRICS_SCHEMA_VERSION


# ── tool_errors, which V1 writes into the same block ─────────────────────


def test_a_tool_error_is_a_call_that_came_back_not_ok():
    """V1's rule, because V1's rows are summed with these.

    ``step6_report`` divides ``total_tool_errors`` by ``total_tool_calls`` and
    publishes the quotient as a percentage. V1
    (:mod:`core.agentic_sandbox_runner`) increments the numerator once per
    dispatch whose result is not ``ok``, so a V2 row counting anything else
    makes a rate out of a numerator and a denominator that are not about the
    same events.
    """
    metrics = _metrics(
        tool_calls=[
            {"tool_name": "exec_run", "ok": True},
            {"tool_name": "exec_run", "ok": False},
            {"tool_name": "workspace_apply", "ok": False},
            {"tool_name": "finalize", "ok": True},
        ]
    )
    assert metrics["tool_calls"] == 4
    assert metrics["tool_errors"] == 2


def test_a_call_that_never_said_whether_it_worked_counts_as_not_ok():
    """Absent is not success. The rule is ``ok is not True``, as in V1."""
    metrics = _metrics(tool_calls=[{"tool_name": "exec_run"}])
    assert metrics["tool_errors"] == 1


def test_a_task_that_called_nothing_reports_no_tool_errors():
    """The denominator is zero here, so any numerator is unreadable.

    A compute that never started is a real failure and it is already reported,
    under ``terminal_error_category``. Writing it here as well put a task with
    no tool calls into the tool-error rate.
    """
    metrics = build_agentic_v2_metrics(
        _failed_run("compute_start_failed"),
        standing=_standing(decision=DECISION_RUN),
        task_wall_time_ms=99.0,
        tool_calls=(),
        receipt=_receipt(),
    )
    assert metrics["tool_calls"] == 0
    assert metrics["tool_errors"] == 0


def test_a_task_that_hit_a_tool_error_and_finished_anyway_recovered():
    """V1's field, at V1's moment: finalised, and something went wrong on the way.

    Step 6 divides ``recovered_tasks`` by ``tasks_with_tool_errors``. V2 wrote
    no value at all, so every V2 run read as a run in which nothing recovered.
    """
    metrics = _metrics(
        tool_calls=[
            {"tool_name": "browser_run", "ok": False},
            {"tool_name": "exec_run", "ok": True},
            {"tool_name": "finalize", "ok": True},
        ]
    )
    assert metrics["tool_errors"] == 1
    assert metrics["recovered_after_tool_error"] is True


def test_a_clean_success_recovered_from_nothing():
    metrics = _metrics(tool_calls=[{"tool_name": "finalize", "ok": True}])
    assert metrics["tool_errors"] == 0
    assert metrics["recovered_after_tool_error"] is False


def test_a_failed_task_did_not_recover_however_many_errors_it_met():
    metrics = build_agentic_v2_metrics(
        _failed_run("tool_budget_exhausted"),
        standing=_standing(decision=DECISION_RUN),
        task_wall_time_ms=99.0,
        tool_calls=[
            {"tool_name": "browser_run", "ok": False},
            {"tool_name": "browser_run", "ok": False},
        ],
        receipt=_receipt(),
    )
    assert metrics["tool_errors"] == 2
    assert metrics["recovered_after_tool_error"] is False


# ── refusals, counted beside the ending and never as one ─────────────────


def test_a_refused_call_is_counted_by_the_reason_the_desk_gave():
    """A refusal spends a turn and ends nothing, so it needs its own field.

    The desk hands ``capability_unavailable`` back and the loop carries on --
    :data:`core.agentic_v2_conversation._ENDS_THE_RUN` deliberately omits it.
    Two tasks that both end at the tool ceiling, one refused seven times and
    one that worked seven times, are identical in every other field here.

    Kept by reason rather than as one number because *what* was refused is the
    finding: a cohort refused thirty times for ``capability_unavailable`` is a
    closed tool, and thirty different reasons is a desk nobody configured.
    """
    metrics = _metrics(
        tool_calls=[
            {
                "tool_name": "browser_run",
                "ok": False,
                "error_type": "capability_unavailable",
            },
            {
                "tool_name": "browser_run",
                "ok": False,
                "error_type": "capability_unavailable",
            },
            {
                "tool_name": "environment_resolve",
                "ok": False,
                "error_type": "package_not_in_snapshot",
            },
            {"tool_name": "finalize", "ok": True},
        ]
    )
    assert metrics["agentic_v2_tool_refusals"] == 3
    assert metrics["agentic_v2_tool_refusals_by_kind"] == {
        "capability_unavailable": 2,
        "package_not_in_snapshot": 1,
    }
    # The refusals are inside `tool_errors` rather than added to it: three
    # calls came back not-ok and all three were the desk saying no.
    assert metrics["tool_errors"] == 3


def test_the_failure_that_ended_the_run_is_not_counted_as_a_refusal():
    """It is the ending, and ``terminal_error_category`` already holds it.

    A run stopped by ``compute_backend_error`` has a broken tool desk, not a
    model that was told no and chose something else. Counting it in both
    columns is how a harness defect gets published as a tool policy.
    """
    metrics = build_agentic_v2_metrics(
        _failed_run("compute_backend_error"),
        standing=_standing(decision=DECISION_RUN),
        task_wall_time_ms=99.0,
        tool_calls=[
            {
                "tool_name": "browser_run",
                "ok": False,
                "error_type": "capability_unavailable",
            },
            {
                "tool_name": "exec_run",
                "ok": False,
                "error_type": "compute_backend_error",
            },
        ],
        receipt=_receipt(),
    )
    assert metrics["terminal_error_category"] == "compute_backend_error"
    assert metrics["agentic_v2_tool_refusals"] == 1
    assert metrics["agentic_v2_tool_refusals_by_kind"] == {
        "capability_unavailable": 1
    }
    # `tool_errors` counts calls and so is the larger of the two here.
    assert metrics["tool_errors"] == 2


def test_a_run_that_met_no_refusal_says_so_with_an_empty_breakdown():
    metrics = _metrics(tool_calls=[{"tool_name": "exec_run", "ok": True}])
    assert metrics["agentic_v2_tool_refusals"] == 0
    assert metrics["agentic_v2_tool_refusals_by_kind"] == {}


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


def _row(
    status=STATUS_SUCCESS,
    disposition=None,
    abandoned=0,
    *,
    ending="",
    refusals=0,
    by_kind=None,
):
    return {
        "status": status,
        "observability": {
            "agentic_metrics": {
                "agentic_v2_disposition": disposition,
                "agentic_v2_abandoned_attempts": abandoned,
                "terminal_error_category": ending,
                "agentic_v2_tool_refusals": refusals,
                "agentic_v2_tool_refusals_by_kind": by_kind or {},
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


def test_the_endings_partition_the_run_and_refusals_are_not_added_to_them():
    """Thirty tasks with forty refusals still have thirty endings.

    The endings partition the run and the refusals do not join them, but not
    for the reason this docstring used to give. It said a refusal ends nothing
    -- the desk hands it back and the loop carries on -- which is not what the
    runner does. A refusal ends the attempt it is in, so in a real record it is
    the same event as that task's ending, and adding the two would count one
    event twice. The cross-tab splits each ending by whether a refusal was met
    on the way, which is the only thing that tells a tool ceiling spent on
    refused calls apart from one spent on work. Both tasks below ended
    ``tool_budget_exhausted`` and they are not the same result.
    """
    summary = summarise_v2_run(
        [
            _row(
                STATUS_ERROR,
                "semantic",
                ending="tool_budget_exhausted",
                refusals=7,
                by_kind={"capability_unavailable": 7},
            ),
            _row(STATUS_ERROR, "semantic", ending="tool_budget_exhausted"),
            _row(
                STATUS_ERROR,
                "semantic",
                ending="finalize_not_called",
                refusals=1,
                by_kind={"capability_unavailable": 1},
            ),
            _row(),
        ],
        manifest_size=4,
        receipt_ceiling=STATUS_COMPLETE,
    )
    assert summary["tool_refusals"] == 8
    assert summary["tasks_that_met_a_refusal"] == 2
    assert summary["tool_refusals_by_kind"] == {"capability_unavailable": 8}
    assert summary["endings_after_a_refusal"] == {
        "accepted": {"with_refusals": 0, "without": 1},
        "finalize_not_called": {"with_refusals": 1, "without": 0},
        "tool_budget_exhausted": {"with_refusals": 1, "without": 1},
    }

    # The two fields have different denominators and this is where that shows:
    # eight refusals across four tasks, two of which met one.
    counted = sum(
        bucket["with_refusals"] + bucket["without"]
        for bucket in summary["endings_after_a_refusal"].values()
    )
    assert counted == summary["executed"] == 4
    assert summary["tasks_that_met_a_refusal"] <= summary["executed"]


def test_a_failure_whose_category_was_never_recorded_is_named_not_dropped():
    """Otherwise the endings stop adding up to the run and nobody can tell."""
    summary = summarise_v2_run(
        [_row(STATUS_ERROR, "infrastructure")],
        manifest_size=1,
        receipt_ceiling=STATUS_COMPLETE,
    )
    assert summary["endings_after_a_refusal"] == {
        "unrecorded": {"with_refusals": 0, "without": 1}
    }


def test_a_run_that_met_no_refusal_reports_zero_rather_than_nothing():
    summary = summarise_v2_run(
        [_row(), _row()], manifest_size=2, receipt_ceiling=STATUS_COMPLETE
    )
    assert summary["tool_refusals"] == 0
    assert summary["tasks_that_met_a_refusal"] == 0
    assert summary["tool_refusals_by_kind"] == {}
    assert summary["endings_after_a_refusal"] == {
        "accepted": {"with_refusals": 0, "without": 2}
    }


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
