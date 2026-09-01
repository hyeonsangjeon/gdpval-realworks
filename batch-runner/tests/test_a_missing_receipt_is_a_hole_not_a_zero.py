"""A task the cost record never mentions is a hole, not a task that cost zero.

``summarize_cost_receipts`` walked the run's rows and dropped every row that
carried no receipt for the field being summarised. The dropped row still
counted in ``total_tasks`` and in the coverage denominator, so the run knew
perfectly well that it had happened -- it just stopped counting it everywhere
else. Three figures went wrong at once, from one ``continue``:

* ``failed_task_count`` lost the failure, so a run could print
  ``Failed tasks | 0`` beside ``Coverage | 1 / 2 tasks (50.0%)``.
* completeness was judged as ``counts["complete"] == len(receipts)``, which asks
  only "is what I kept consistent?" -- a question the rows that were thrown away
  can never answer. So the run announced ``Receipt status | complete`` and
  headed its money row ``Total``, over half a run.
* ``cost_per_successful_deliverable_usd`` rides on that same flag, so an
  understated per-unit figure was published as if it were settled.

A receiptless row is the ordinary shape, not an edge case.
``core/result_projection.py`` *drops* the key rather than writing a null when a
run predates cost instrumentation, resume re-uses rows written by an earlier
build, and ``costReceiptsByTask`` in ``scripts/aggregate-grades.mjs`` hands the
JavaScript twin a null receipt for every graded task with no ``grading_cost``.

Receipts here are built by ``core.cost_receipts.build_receipt`` -- the same
factory the run itself calls -- so the numbers under test are the producer's,
not this file's.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import step6_report
from core.cost_projection import (
    build_cost_summaries,
    project_cost_receipt,
    successful_deliverable_count,
    summarize_cost_receipts,
)
from core.cost_receipts import STATE_SETTLED, build_receipt
from core.result_projection import project_result_row
from tests.test_cost_projection import (
    _receipt,
    _report_data,
    _report_input,
    _row,
    _unmeasured,
)

FIELD = "problem_solving_cost"


def _priced(amount: str = "0.4200") -> dict:
    """A settled receipt straight out of the producer's own factory."""
    receipt = build_receipt(
        [
            {
                "stage": "generation",
                "retry_kind": "none",
                "state": STATE_SETTLED,
                "model_cost_usd": amount,
                "input_tokens": 1000,
                "output_tokens": 200,
                "missing_reasons": [],
            }
        ],
        price_table_sha256="c" * 64,
    )
    return project_cost_receipt(receipt.as_dict())


def _recorded(task_id: str, **overrides) -> dict:
    return _row(task_id, **{FIELD: _priced(), **overrides})


def _hole(task_id: str, **overrides) -> dict:
    """A row with no receipt key at all -- what the projection layer writes."""
    row = _row(task_id, **overrides)
    assert FIELD not in row
    return row


def _summary(*rows) -> dict | None:
    return summarize_cost_receipts(list(rows), FIELD)


# ── The hole is real: the projection layer drops the key ──────────────────


def test_the_projection_layer_omits_the_field_rather_than_nulling_it():
    """Why a receiptless row reaches the summariser in the first place.

    ``project_result_row`` writes the cost key only when a receipt exists, so
    the absence this module has to survive is produced by shipped code, not
    constructed by this test.
    """
    projected = project_result_row(
        {"sector": "s", "occupation": "o", "instruction": "do it"},
        {
            "task_id": "t-lost",
            "status": "error",
            "error": "the sandbox went away",
            "deliverable_text": "",
            "deliverable_files": [],
        },
    )
    assert FIELD not in projected


# ── The headline: a failure with no receipt is still a failure ────────────


def test_a_failed_row_with_no_receipt_is_counted_as_a_failure():
    summary = _summary(_recorded("t-ok"), _hole("t-lost", status="error"))
    assert summary["failed_task_count"] == 1
    # Nothing is invented about what it cost. It could not be priced, so it
    # joins neither the amount nor the count of failures that could be.
    assert summary["failed_measured_tasks"] == 0
    assert summary["failed_task_cost_usd"] == 0.0


def test_a_successful_row_with_no_receipt_is_not_counted_as_a_failure():
    """The negative control. The hole is a hole in the *cost* record only.

    Missing money says nothing about whether the work succeeded, so a
    successful task whose receipt was never written must not be conjured into
    a failure by the same branch that rescues the failing one.
    """
    summary = _summary(_recorded("t-ok"), _hole("t-quiet"))
    assert summary["failed_task_count"] == 0
    assert summary["total_tasks"] == 2
    assert summary["receipt_tasks"] == 1


def test_the_receipts_and_the_holes_account_for_every_task():
    """Coverage already reported the hole; nothing else did. Now they agree."""
    summary = _summary(
        _recorded("t-ok"), _hole("t-lost", status="error"), _hole("t-quiet")
    )
    assert summary["total_tasks"] == 3
    assert summary["receipt_tasks"] == 1
    assert summary["coverage_pct"] == 33.3
    assert summary["failed_task_count"] == 1


# ── A hole stops the run calling itself whole ─────────────────────────────


def test_a_hole_stops_the_run_reading_as_complete():
    summary = _summary(_recorded("t-ok"), _hole("t-lost", status="error"))
    assert summary["status"] == "partial"


def test_a_hole_withholds_the_estimated_total():
    """``estimated_cost_usd`` is the run's answer, and it is not known yet."""
    summary = _summary(_recorded("t-ok"), _hole("t-lost", status="error"))
    assert summary["estimated_cost_usd"] is None
    # What *was* recorded is still published, as a floor.
    assert summary["known_cost_usd"] == 0.42


def test_a_hole_withholds_the_per_deliverable_figure():
    """Dividing a partial total by the full deliverable count understates it."""
    rows = [_recorded("t-ok"), _hole("t-second")]
    summary = summarize_cost_receipts(
        rows, FIELD, successful_deliverables=successful_deliverable_count(rows)
    )
    assert summary["successful_deliverables"] == 2
    assert summary["cost_per_successful_deliverable_usd"] is None


# ── Only ``complete`` moves ───────────────────────────────────────────────
#
# The other three statuses already decline to claim the run is whole, so the
# downgrade has nothing to add to them. Pinning each one keeps a later edit
# from widening the branch into runs it was never meant to touch.


def test_a_hole_beside_a_partial_receipt_stays_partial():
    summary = _summary(
        _row("t-ok", **{FIELD: _unmeasured("partial", known_cost_usd=0.1)}),
        _hole("t-lost", status="error"),
    )
    assert summary["status"] == "partial"


def test_a_hole_beside_an_unavailable_receipt_stays_unavailable():
    summary = _summary(
        _row("t-ok", **{FIELD: _unmeasured("unavailable")}),
        _hole("t-lost", status="error"),
    )
    assert summary["status"] == "unavailable"


def test_a_hole_beside_a_not_run_receipt_stays_not_run():
    summary = _summary(
        _row("t-ok", **{FIELD: _unmeasured("not_run")}),
        _hole("t-lost", status="error"),
    )
    assert summary["status"] == "not_run"


# ── Runs that were already whole are untouched ────────────────────────────


def test_a_run_where_every_row_carries_a_receipt_is_unchanged():
    """The published-experiment guarantee.

    With no hole the new branch is unreachable, so a fully recorded run keeps
    saying ``complete``, keeps publishing its estimate, and keeps publishing
    its per-deliverable figure.
    """
    rows = [_recorded("t-ok"), _recorded("t-also-ok")]
    summary = summarize_cost_receipts(
        rows, FIELD, successful_deliverables=successful_deliverable_count(rows)
    )
    assert summary["status"] == "complete"
    assert summary["estimated_cost_usd"] == 0.84
    assert summary["cost_per_successful_deliverable_usd"] == 0.42
    assert summary["failed_task_count"] == 0


def test_a_fully_recorded_run_with_a_failure_is_unchanged():
    """A recorded failure counted before and still counts exactly once."""
    priced = _receipt(estimated_cost_usd=0.4, known_cost_usd=0.4, model_cost_usd=0.4)
    summary = _summary(
        _recorded("t-ok"),
        _row("t-bad", status="error", deliverable_files=[], **{FIELD: priced}),
    )
    assert summary["failed_task_count"] == 1
    assert summary["failed_measured_tasks"] == 1
    assert summary["failed_task_cost_usd"] == 0.4
    assert summary["status"] == "complete"


def test_a_run_where_no_row_carries_a_receipt_still_reads_as_no_record():
    """Pre-instrumentation runs must not gain a summary out of nowhere.

    Every row is a hole here, and the answer stays ``None`` -- which is what
    keeps an experiment that ran before receipts existed rendering as "no
    record" rather than as a partial run that cost nothing.
    """
    assert _summary(_hole("t-a"), _hole("t-b", status="error")) is None


def test_a_run_of_no_rows_at_all_is_still_no_record():
    assert _summary() is None


# ── What the report prints ────────────────────────────────────────────────


def _markdown(*rows) -> str:
    return step6_report._build_markdown(_report_data(_report_input(*rows)))


def test_markdown_no_longer_heads_half_a_run_with_total():
    markdown = _markdown(_recorded("t-ok"), _hole("t-lost", status="error"))
    assert "| Coverage | 1 / 2 tasks (50.0%) |" in markdown
    assert "| Receipt status | partial — the figures below are a floor |" in markdown
    assert "| Recorded so far | $0.4200 |" in markdown
    assert "| Total | $0.4200 |" not in markdown


def test_markdown_names_the_failure_that_left_no_receipt():
    markdown = _markdown(_recorded("t-ok"), _hole("t-lost", status="error"))
    assert "| Failed tasks | 1 (no record) |" in markdown
    assert "| Failed tasks | 0 ($0.0000) |" not in markdown


def test_markdown_discloses_how_much_of_a_mixed_failure_row_was_priced():
    """One failure priced, one never recorded: the amount is a floor, and says so."""
    priced = _receipt(estimated_cost_usd=0.4, known_cost_usd=0.4, model_cost_usd=0.4)
    markdown = _markdown(
        _row("t-bad", status="error", deliverable_files=[], **{FIELD: priced}),
        _hole("t-lost", status="error"),
    )
    assert "| Failed tasks | 2 ($0.4000, 1 / 2 priced) |" in markdown


def test_markdown_withholds_the_per_deliverable_figure_for_a_run_with_a_hole():
    markdown = _markdown(_recorded("t-ok"), _hole("t-second"))
    assert "| Per successful deliverable | no record |" in markdown


def test_markdown_for_a_fully_recorded_run_still_says_total():
    """The control, at the rendering layer."""
    markdown = _markdown(_recorded("t-ok"), _recorded("t-also-ok"))
    assert "| Coverage | 2 / 2 tasks (100.0%) |" in markdown
    assert "| Receipt status | complete |" in markdown
    assert "| Total | $0.8400 |" in markdown
    assert "| Per successful deliverable | $0.4200 |" in markdown


# ── Both cost fields, not just the one under the microscope ───────────────


def test_the_grading_field_gets_the_same_treatment():
    """``build_cost_summaries`` runs the same function over ``grading_cost``.

    The dashboard's aggregator is the one that routinely produces holes, and
    it produces them on the grading side.
    """
    summaries = build_cost_summaries(
        [
            _row("t-ok", grading_cost=_priced()),
            _row("t-lost", status="error", deliverable_files=[]),
        ]
    )
    assert FIELD not in summaries
    grading = summaries["grading_cost"]
    assert grading["failed_task_count"] == 1
    assert grading["status"] == "partial"
    assert grading["estimated_cost_usd"] is None
