"""Read-side contract tests for per-task cost receipts (``cost-receipt-v1``).

The distinctions these tests defend are the ones a reader of the dashboard
depends on: a run with no instrumentation must never render as a run that cost
nothing, a partial receipt must never be totalled as if it were whole, and the
cost of failed work must stay visible instead of being netted away.
"""

import hashlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import step6_report
from core.cost_projection import (
    COST_LEDGER_PUBLICATION_PATH,
    COST_RECEIPT_SCHEMA_VERSION,
    ESTIMATE_BASIS,
    build_cost_summaries,
    project_cost_ledger_reference,
    project_cost_receipt,
    stage_cost_ledger,
    successful_deliverable_count,
    summarize_cost_receipts,
    verify_cost_ledger,
)
from core.result_projection import project_result_row


def _component(**overrides) -> dict:
    """One receipt line in the shape ``core/cost_receipts.py`` writes it.

    Note what is *not* here: no ``estimated_cost_usd``. The producer puts an
    estimate on the receipt and nowhere else, so a line only ever reports what
    was confirmed.
    """
    component = {
        "name": "generation",
        "stage": "generation",
        "retry_kind": "none",
        "status": "complete",
        "known_cost_usd": 0.25,
        "model_calls": 3,
        "usage": {"input_tokens": 1200},
        "missing_reasons": [],
    }
    component.update(overrides)
    return component


def _receipt(**overrides) -> dict:
    receipt = {
        "schema_version": COST_RECEIPT_SCHEMA_VERSION,
        "currency": "USD",
        "status": "complete",
        "estimated_cost_usd": 0.25,
        "known_cost_usd": 0.25,
        "model_cost_usd": 0.2,
        "runtime_cost_usd": 0.05,
        "model_calls": 3,
        "usage": {"input_tokens": 1200, "output_tokens": 400},
        "components": [_component()],
        "price_table_sha256": "a" * 64,
        "missing_reasons": [],
    }
    receipt.update(overrides)
    return receipt


def _unmeasured(status: str, **overrides) -> dict:
    """A receipt with no amount, in the shape the producer actually writes.

    ``core/cost_receipts.py`` fills every money field on every status, so an
    ``unavailable`` receipt arrives carrying ``0.0`` rather than ``None``. A
    test that passed ``None`` here would go green against a payload that never
    occurs, and the placeholder zero would reach the screen as ``$0.0000``.
    """
    receipt = _receipt(
        status=status,
        estimated_cost_usd=None,
        known_cost_usd=0.0,
        model_cost_usd=0.0,
        runtime_cost_usd=0.0,
        components=[],
        missing_reasons=[] if status == "not_run" else ["usage_absent"],
    )
    receipt.update(overrides)
    return receipt


def _row(task_id: str, **overrides) -> dict:
    row = {
        "task_id": task_id,
        "status": "success",
        "deliverable_files": [f"{task_id}/report.xlsx"],
        "deliverable_text": "",
    }
    row.update(overrides)
    return row


# ── Receipt projection ────────────────────────────────────────────────────


def test_absent_receipt_projects_to_none_not_zero():
    assert project_cost_receipt(None) is None


def test_complete_receipt_round_trips_without_inventing_fields():
    projected = project_cost_receipt(_receipt())
    assert projected["status"] == "complete"
    assert projected["known_cost_usd"] == 0.25
    # The producer's schema is closed (``additionalProperties: false``), so the
    # estimate-basis disclaimer rides on the summary this module builds, never
    # on a receipt this module merely relays.
    assert "estimate_basis" not in projected


def test_a_component_keeps_its_stage_and_retry_kind():
    projected = project_cost_receipt(
        _receipt(
            components=[
                _component(name="retry", stage="self_qa", retry_kind="semantic"),
            ]
        )
    )
    component = projected["components"][0]
    # Which stage a retry belonged to is what makes the charge readable. The
    # displayed label collapses it; the record must not.
    assert component == {
        "name": "retry",
        "stage": "self_qa",
        "retry_kind": "semantic",
        "status": "complete",
        "known_cost_usd": 0.25,
        "model_calls": 3,
        "usage": {"input_tokens": 1200},
        "missing_reasons": [],
        # This line was written before identity was recorded. It reads back
        # unattributed rather than defaulted — the truthful answer, and the one
        # that keeps an old receipt from being credited to whatever ran last.
        "provider": None,
        "deployment": None,
        "requested_model": None,
        "resolved_model": None,
        "api_version": None,
    }


def test_a_genuine_zero_is_a_complete_receipt():
    projected = project_cost_receipt(
        _receipt(
            estimated_cost_usd=0.0,
            known_cost_usd=0.0,
            model_cost_usd=0.0,
            runtime_cost_usd=0.0,
            components=[],
        )
    )
    assert projected["status"] == "complete"
    assert projected["known_cost_usd"] == 0.0


@pytest.mark.parametrize("status", ["unavailable", "not_run"])
def test_the_placeholder_zero_of_an_unmeasured_receipt_becomes_no_record(status):
    projected = project_cost_receipt(_unmeasured(status))
    assert projected["status"] == status
    # Every money field arrived as 0.0. None of them survives as a number: a
    # receipt that recorded nothing must not read as a run that cost nothing.
    assert projected["known_cost_usd"] is None
    assert projected["model_cost_usd"] is None
    assert projected["runtime_cost_usd"] is None
    assert projected["estimated_cost_usd"] is None


def test_a_partial_receipt_that_confirmed_nothing_reports_no_floor():
    projected = project_cost_receipt(
        _receipt(
            status="partial",
            estimated_cost_usd=None,
            known_cost_usd=0.0,
            model_cost_usd=0.0,
            runtime_cost_usd=0.0,
            components=[_component(status="partial", known_cost_usd=0.0)],
            missing_reasons=["price_missing"],
        )
    )
    # "At least $0" is true of every run ever made and tells the reader nothing.
    assert projected["known_cost_usd"] is None
    assert projected["components"][0]["known_cost_usd"] is None


def test_a_partial_receipt_keeps_the_part_it_did_confirm():
    projected = project_cost_receipt(
        _receipt(
            status="partial",
            estimated_cost_usd=None,
            known_cost_usd=0.12,
            model_cost_usd=0.12,
            runtime_cost_usd=0.0,
            components=[_component(status="partial", known_cost_usd=0.12)],
            missing_reasons=["runtime_cost_unpriced"],
        )
    )
    assert projected["known_cost_usd"] == 0.12
    assert projected["runtime_cost_usd"] is None


@pytest.mark.parametrize(
    "overrides,message",
    [
        ({"schema_version": "cost-receipt-v2"}, "schema_version"),
        ({"currency": "KRW"}, "denominated"),
        ({"status": "unknown"}, "must be one of"),
        (
            {"status": "complete", "estimated_cost_usd": None, "known_cost_usd": None},
            "complete without an amount",
        ),
        (
            {"status": "complete", "missing_reasons": ["price_missing"]},
            "reports missing components",
        ),
        (
            {
                "status": "partial",
                "estimated_cost_usd": None,
                "known_cost_usd": 0.1,
                "missing_reasons": [],
            },
            "partial without a reason code",
        ),
        (
            {
                "status": "unavailable",
                "estimated_cost_usd": None,
                "known_cost_usd": 0.0,
                "model_cost_usd": 0.0,
                "runtime_cost_usd": 0.0,
                "components": [],
                "missing_reasons": [],
            },
            "unavailable without a reason code",
        ),
        # An estimate is the one thing only a complete receipt may name.
        (
            {"status": "partial", "missing_reasons": ["price_missing"]},
            "partial but carries an estimate",
        ),
        (
            {
                "status": "not_run",
                "known_cost_usd": None,
                "model_cost_usd": None,
                "runtime_cost_usd": None,
                "components": [],
                "missing_reasons": [],
            },
            "not_run but carries an estimate",
        ),
        # …and a non-zero amount under a status that recorded nothing is not a
        # placeholder, it is a receipt contradicting itself.
        (
            {
                "status": "not_run",
                "estimated_cost_usd": None,
                "known_cost_usd": 0.4,
                "components": [],
                "missing_reasons": [],
            },
            "is not_run but carries an amount",
        ),
        ({"known_cost_usd": 0.9}, "complete but its known amount differs"),
        ({"estimated_cost_usd": float("inf")}, "finite"),
        ({"estimated_cost_usd": -1.0}, "out of range"),
        ({"model_cost_usd": 0.9}, "exceeds the known amount"),
        ({"missing_reasons": ["the price table was not loaded"]}, "reason codes only"),
        ({"usage": {"Input Tokens": 5}}, "invalid key"),
        ({"price_table_sha256": "not-a-digest"}, "sha256"),
    ],
)
def test_malformed_receipts_raise_rather_than_publish(overrides, message):
    with pytest.raises(ValueError, match=message):
        project_cost_receipt(_receipt(**overrides))


def test_two_retries_from_different_stages_are_two_lines():
    # Both derive the name ``retry`` from the producer. Rejecting the second as
    # a duplicate would drop a call that really was billed.
    projected = project_cost_receipt(
        _receipt(
            estimated_cost_usd=0.2,
            known_cost_usd=0.2,
            model_cost_usd=0.2,
            runtime_cost_usd=None,
            components=[
                _component(
                    name="retry", stage="generation", retry_kind="infrastructure",
                    known_cost_usd=0.1, model_calls=1,
                ),
                _component(
                    name="retry", stage="self_qa", retry_kind="semantic",
                    known_cost_usd=0.1, model_calls=1,
                ),
            ],
        )
    )
    assert [component["stage"] for component in projected["components"]] == [
        "generation",
        "self_qa",
    ]


def test_the_same_stage_and_retry_kind_twice_is_rejected():
    component = _component(known_cost_usd=0.1, model_calls=1)
    with pytest.raises(ValueError, match="duplicate component keys"):
        project_cost_receipt(
            _receipt(
                estimated_cost_usd=0.2,
                known_cost_usd=0.2,
                model_cost_usd=0.2,
                runtime_cost_usd=None,
                components=[component, dict(component)],
            )
        )


# ── Row projection ────────────────────────────────────────────────────────


def test_row_without_a_receipt_gains_no_cost_key():
    row = project_result_row({}, {"task_id": "task-a", "status": "success"})
    assert "problem_solving_cost" not in row


def test_row_carries_a_projected_receipt():
    row = project_result_row(
        {},
        {"task_id": "task-a", "status": "success", "problem_solving_cost": _receipt()},
    )
    assert row["problem_solving_cost"]["known_cost_usd"] == 0.25


def test_row_projection_names_the_task_in_its_error():
    with pytest.raises(ValueError, match="task-a"):
        project_result_row(
            {},
            {
                "task_id": "task-a",
                "status": "success",
                "problem_solving_cost": _receipt(currency="KRW"),
            },
        )


# ── Run summaries ─────────────────────────────────────────────────────────


def test_a_run_with_no_receipts_summarizes_to_none():
    rows = [_row("task-a"), _row("task-b")]
    assert summarize_cost_receipts(rows, "problem_solving_cost") is None
    assert build_cost_summaries(rows) == {}


def test_complete_run_reports_a_total_and_a_per_deliverable_figure():
    rows = [
        _row("task-a", problem_solving_cost=project_cost_receipt(_receipt())),
        _row(
            "task-b",
            problem_solving_cost=project_cost_receipt(
                _receipt(
                    estimated_cost_usd=0.75,
                    known_cost_usd=0.75,
                    model_cost_usd=0.75,
                    runtime_cost_usd=None,
                    components=[],
                )
            ),
        ),
    ]
    summary = summarize_cost_receipts(
        rows,
        "problem_solving_cost",
        successful_deliverables=successful_deliverable_count(rows),
    )
    assert summary["status"] == "complete"
    assert summary["known_cost_usd"] == 1.0
    assert summary["estimated_cost_usd"] == 1.0
    assert summary["avg_cost_usd"] == 0.5
    assert summary["median_cost_usd"] == 0.5
    assert summary["max_cost_usd"] == 0.75
    assert summary["cost_per_successful_deliverable_usd"] == 0.5
    assert summary["coverage_pct"] == 100.0
    # The disclaimer lives on the summary, which is the payload a reader sees a
    # headline number in. It is not a field of the receipt itself.
    assert summary["estimate_basis"] == ESTIMATE_BASIS


def test_one_partial_receipt_makes_the_run_total_a_floor():
    rows = [
        _row("task-a", problem_solving_cost=project_cost_receipt(_receipt())),
        _row(
            "task-b",
            problem_solving_cost=project_cost_receipt(
                _receipt(
                    status="partial",
                    estimated_cost_usd=None,
                    known_cost_usd=0.1,
                    model_cost_usd=0.1,
                    runtime_cost_usd=None,
                    components=[],
                    missing_reasons=["runtime_cost_unpriced"],
                )
            ),
        ),
    ]
    summary = summarize_cost_receipts(
        rows,
        "problem_solving_cost",
        successful_deliverables=successful_deliverable_count(rows),
    )
    assert summary["status"] == "partial"
    assert summary["known_cost_usd"] == 0.35
    # A floor is not a total, and it is not divided into a per-unit headline.
    assert summary["estimated_cost_usd"] is None
    assert summary["cost_per_successful_deliverable_usd"] is None
    assert summary["missing_reasons"] == ["runtime_cost_unpriced"]


def test_unavailable_receipts_are_counted_but_never_priced():
    unavailable = project_cost_receipt(_unmeasured("unavailable"))
    summary = summarize_cost_receipts(
        [_row("task-a", problem_solving_cost=unavailable)],
        "problem_solving_cost",
    )
    assert summary["status"] == "unavailable"
    assert summary["measured_tasks"] == 0
    assert summary["unavailable_tasks"] == 1
    assert summary["avg_cost_usd"] is None
    assert summary["known_cost_usd"] == 0.0


def test_failed_task_cost_is_reported_beside_the_total_not_removed_from_it():
    rows = [
        _row("task-a", problem_solving_cost=project_cost_receipt(_receipt())),
        _row(
            "task-b",
            status="error",
            deliverable_files=[],
            problem_solving_cost=project_cost_receipt(
                _receipt(
                    estimated_cost_usd=0.4,
                    known_cost_usd=0.4,
                    model_cost_usd=0.4,
                    runtime_cost_usd=None,
                    components=[],
                )
            ),
        ),
    ]
    summary = summarize_cost_receipts(
        rows,
        "problem_solving_cost",
        successful_deliverables=successful_deliverable_count(rows),
    )
    assert summary["known_cost_usd"] == 0.65
    assert summary["failed_task_count"] == 1
    assert summary["failed_task_cost_usd"] == 0.4
    # Every failure here was priced, so the amount is the amount.
    assert summary["failed_measured_tasks"] == 1
    assert summary["successful_deliverables"] == 1


def test_a_failure_billed_against_an_unpriced_model_is_not_counted_as_measured():
    """The count that makes ``failed_task_cost_usd`` readable.

    A failure billed against a model the price table has no entry for arrives
    with no amount, so it contributes nothing to the sum. The sum it never
    joined stays ``0.0`` -- which is also what a failure that asked no model
    leaves behind. The amount alone cannot tell those apart; the count of
    failures that could be priced is what does.
    """
    unpriced = project_cost_receipt(
        _unmeasured("partial", missing_reasons=["price_missing"])
    )
    summary = summarize_cost_receipts(
        [
            _row("task-a", status="error", problem_solving_cost=unpriced),
            _row("task-b", status="error", problem_solving_cost=unpriced),
        ],
        "problem_solving_cost",
    )
    assert summary["failed_task_count"] == 2
    assert summary["failed_measured_tasks"] == 0
    # The zero is still published -- it is the sum of nothing -- but it is no
    # longer the only thing a reader has to go on.
    assert summary["failed_task_cost_usd"] == 0.0


def test_a_genuinely_free_failure_stays_apart_from_one_that_was_never_priced():
    """The discrimination the count exists for, asserted as a pair.

    ``CostReceipt.free()`` is the one honest ``$0``: a verdict reached by rule,
    with no model asked. It and the unpriced failure above both report
    ``failed_task_cost_usd == 0.0``. Only ``failed_measured_tasks`` separates
    them, and if it ever stops doing so a paid failure reads as a free one.
    """
    free = project_cost_receipt(
        _receipt(
            status="complete",
            estimated_cost_usd=0.0,
            known_cost_usd=0.0,
            model_cost_usd=0.0,
            runtime_cost_usd=0.0,
            model_calls=0,
            components=[],
        )
    )
    unpriced = project_cost_receipt(
        _unmeasured("partial", missing_reasons=["price_missing"])
    )

    free_summary = summarize_cost_receipts(
        [_row("task-a", status="error", problem_solving_cost=free)],
        "problem_solving_cost",
    )
    unpriced_summary = summarize_cost_receipts(
        [_row("task-a", status="error", problem_solving_cost=unpriced)],
        "problem_solving_cost",
    )

    assert free_summary["failed_task_cost_usd"] == 0.0
    assert unpriced_summary["failed_task_cost_usd"] == 0.0
    assert free_summary["failed_task_count"] == unpriced_summary["failed_task_count"] == 1
    assert free_summary["failed_measured_tasks"] == 1
    assert unpriced_summary["failed_measured_tasks"] == 0


def test_a_partly_priced_set_of_failures_reports_how_much_of_it_was_priced():
    """One priced failure and one not: the amount is a floor, and says so."""
    priced = project_cost_receipt(
        _receipt(estimated_cost_usd=0.4, known_cost_usd=0.4, model_cost_usd=0.4)
    )
    unpriced = project_cost_receipt(
        _unmeasured("partial", missing_reasons=["price_missing"])
    )
    summary = summarize_cost_receipts(
        [
            _row("task-a", status="error", problem_solving_cost=priced),
            _row("task-b", status="error", problem_solving_cost=unpriced),
        ],
        "problem_solving_cost",
    )
    assert summary["failed_task_count"] == 2
    assert summary["failed_measured_tasks"] == 1
    assert summary["failed_task_cost_usd"] == 0.4


def test_a_run_with_no_failures_reports_zero_measured_failures():
    """Zero failures did cost zero, and nothing about that changed."""
    summary = summarize_cost_receipts(
        [_row("task-a", problem_solving_cost=project_cost_receipt(_receipt()))],
        "problem_solving_cost",
    )
    assert summary["failed_task_count"] == 0
    assert summary["failed_measured_tasks"] == 0
    assert summary["failed_task_cost_usd"] == 0.0


def test_a_failure_that_never_ran_is_not_counted_as_a_free_one():
    """``not_run`` is not zero, and the failed-task row must not say it is.

    ``CostReceipt.not_run`` is documented as "This pipeline did not run. Not
    free -- it did not happen." Its money fields still arrive as ``0.0``, so
    before the count existed this row printed ``1 ($0.0000)`` and claimed a
    task the producer refuses to call free was free.
    """
    summary = summarize_cost_receipts(
        [
            _row(
                "task-a",
                status="error",
                problem_solving_cost=project_cost_receipt(_unmeasured("not_run")),
            )
        ],
        "problem_solving_cost",
    )
    assert summary["failed_task_count"] == 1
    assert summary["failed_measured_tasks"] == 0
    assert step6_report._failed_task_cost(summary) == "1 (no record)"


def test_a_success_with_nothing_to_grade_is_not_a_deliverable():
    rows = [
        _row("task-a"),
        _row("task-b", deliverable_files=[], deliverable_text="   "),
    ]
    assert successful_deliverable_count(rows) == 1


def test_both_cost_fields_summarize_independently():
    rows = [
        _row(
            "task-a",
            problem_solving_cost=project_cost_receipt(_receipt()),
            grading_cost=project_cost_receipt(
                _receipt(
                    estimated_cost_usd=0.02,
                    known_cost_usd=0.02,
                    model_cost_usd=0.02,
                    runtime_cost_usd=None,
                    components=[],
                )
            ),
        ),
    ]
    summaries = build_cost_summaries(rows)
    assert summaries["problem_solving_cost"]["known_cost_usd"] == 0.25
    assert summaries["grading_cost"]["known_cost_usd"] == 0.02


def test_components_aggregate_across_tasks():
    rows = [
        _row("task-a", problem_solving_cost=project_cost_receipt(_receipt())),
        _row("task-b", problem_solving_cost=project_cost_receipt(_receipt())),
    ]
    summary = summarize_cost_receipts(rows, "problem_solving_cost")
    assert summary["components"] == [
        {
            "name": "generation",
            "stage": "generation",
            "retry_kind": "none",
            "provider": None,
            "deployment": None,
            "requested_model": None,
            "resolved_model": None,
            "api_version": None,
            "tasks": 2,
            "known_cost_usd": 0.5,
            "complete_tasks": 2,
            "model_calls": 6,
            "missing_reasons": [],
            "status": "complete",
        },
    ]


def test_two_retries_in_one_task_are_one_task_in_the_component_total():
    # `tasks` sits beside the amount as "how many tasks paid this". A task that
    # retried twice paid each of these once; counting the lines would make that
    # column exceed the number of tasks in the run.
    #
    # They are two rows, not one. Generation's retry and Self-QA's retry both
    # display as 재시도, and folding them by that label summed a $0.15 charge
    # into a $0.05 one and published `retry | $0.20 | 3 calls` — a row over two
    # stages that no reader can take apart again.
    receipt = project_cost_receipt(
        _receipt(
            estimated_cost_usd=0.2,
            known_cost_usd=0.2,
            model_cost_usd=0.2,
            runtime_cost_usd=None,
            components=[
                _component(
                    name="retry", stage="generation", retry_kind="infrastructure",
                    known_cost_usd=0.15, model_calls=2, usage={},
                ),
                _component(
                    name="retry", stage="self_qa", retry_kind="semantic",
                    known_cost_usd=0.05, model_calls=1, usage={},
                ),
            ],
        )
    )
    summary = summarize_cost_receipts(
        [_row("task-a", problem_solving_cost=receipt)], "problem_solving_cost"
    )
    assert summary["components"] == [
        {
            "name": "retry",
            "stage": "generation",
            "retry_kind": "infrastructure",
            "provider": None,
            "deployment": None,
            "requested_model": None,
            "resolved_model": None,
            "api_version": None,
            "tasks": 1,
            "known_cost_usd": 0.15,
            "complete_tasks": 1,
            "model_calls": 2,
            "missing_reasons": [],
            "status": "complete",
        },
        {
            "name": "retry",
            "stage": "self_qa",
            "retry_kind": "semantic",
            "provider": None,
            "deployment": None,
            "requested_model": None,
            "resolved_model": None,
            "api_version": None,
            "tasks": 1,
            "known_cost_usd": 0.05,
            "complete_tasks": 1,
            "model_calls": 1,
            "missing_reasons": [],
            "status": "complete",
        },
    ]
    # The guard this test was written for still holds: one task, and no row
    # claiming more tasks paid it than the run contains.
    assert all(row["tasks"] == 1 for row in summary["components"])


# ── Ledger reference ──────────────────────────────────────────────────────


def test_ledger_reference_normalises_path_and_digest():
    reference = project_cost_ledger_reference(
        {"path": "cost_ledger.jsonl", "sha256": "b" * 64}
    )
    assert reference == {"path": "cost_ledger.jsonl", "sha256": "b" * 64}


@pytest.mark.parametrize(
    "value",
    [
        {"path": "../secrets.jsonl", "sha256": "b" * 64},
        {"path": "/etc/passwd", "sha256": "b" * 64},
        {"path": "cost_ledger.jsonl", "sha256": "short"},
        {"sha256": "b" * 64},
    ],
)
def test_ledger_reference_rejects_unusable_pointers(value):
    with pytest.raises(ValueError, match="cost_ledger"):
        project_cost_ledger_reference(value)


def test_ledger_verification_accepts_a_matching_file(tmp_path):
    ledger = tmp_path / "cost_ledger.jsonl"
    ledger.write_bytes(b'{"task_id": "task-a"}\n')
    digest = hashlib.sha256(ledger.read_bytes()).hexdigest()
    reference = {"path": "cost_ledger.jsonl", "sha256": digest}
    assert verify_cost_ledger(reference, ledger) == reference


def test_ledger_verification_rejects_drifted_bytes(tmp_path):
    ledger = tmp_path / "cost_ledger.jsonl"
    ledger.write_bytes(b'{"task_id": "task-a"}\n')
    with pytest.raises(ValueError, match="does not match the recorded sha256"):
        verify_cost_ledger({"path": "cost_ledger.jsonl", "sha256": "c" * 64}, ledger)


def test_ledger_verification_tolerates_a_pointer_without_the_file(tmp_path):
    reference = {"path": "cost_ledger.jsonl", "sha256": "c" * 64}
    assert verify_cost_ledger(reference, tmp_path / "cost_ledger.jsonl") == reference


# ── Staging the ledger for publication ────────────────────────────────────
#
# Step 2 names its export after the condition it recorded. Publication pins
# one name for the whole repository. These two facts have to be reconciled
# somewhere, and it is here, on the way into the upload directory.


def _workspace_ledger(tmp_path, name="cost_ledger_condition_a.jsonl"):
    """A Step 2 export sitting where Step 2 leaves it, plus its pointer."""
    source = tmp_path / "workspace"
    source.mkdir()
    export = source / name
    export.write_bytes(b'{"call_id": "task-a:generation:0"}\n')
    digest = hashlib.sha256(export.read_bytes()).hexdigest()
    return source, tmp_path / "upload", {"path": name, "sha256": digest}


def test_staging_publishes_the_producer_export_under_the_pinned_name(tmp_path):
    source, upload, reference = _workspace_ledger(tmp_path)

    staged = stage_cost_ledger(reference, source, upload)

    assert staged == {
        "path": COST_LEDGER_PUBLICATION_PATH,
        "sha256": reference["sha256"],
    }
    published = upload / COST_LEDGER_PUBLICATION_PATH
    assert published.read_bytes() == (source / reference["path"]).read_bytes()


def test_staging_publishes_no_pointer_when_the_export_is_absent(tmp_path):
    source, upload, reference = _workspace_ledger(tmp_path)
    (source / reference["path"]).unlink()

    # A pointer with nothing behind it is worse than no pointer: publication
    # rejects it, and a reader who got past that would chase a missing file.
    assert stage_cost_ledger(reference, source, upload) is None
    assert not upload.exists()


def test_staging_refuses_an_export_edited_since_the_run(tmp_path):
    source, upload, reference = _workspace_ledger(tmp_path)
    (source / reference["path"]).write_bytes(b'{"call_id": "task-b:grading:0"}\n')

    with pytest.raises(ValueError, match="digest does not match"):
        stage_cost_ledger(reference, source, upload)
    assert not (upload / COST_LEDGER_PUBLICATION_PATH).exists()


def test_staging_of_nothing_stages_nothing(tmp_path):
    assert stage_cost_ledger(None, tmp_path, tmp_path / "upload") is None


# ── Step 6 report ─────────────────────────────────────────────────────────
#
# ``self_report.json`` is a byte copy of ``report_data.json``, so whatever
# Step 6 puts in the report is what the dashboard and the Hub both read.


def _report_input(*rows) -> dict:
    return {"experiment_id": "exp998", "results": list(rows)}


def _narrative() -> dict:
    return {
        "overview": "",
        "quality_analysis": "",
        "failure_patterns": "",
        "recommendations": "",
    }


def _report_data(data: dict) -> dict:
    task_results, error_tasks = step6_report._build_task_results(data)
    return step6_report._build_report_data(
        data,
        _narrative(),
        step6_report._compute_summary(data),
        [],
        task_results,
        error_tasks,
        cost_summaries=step6_report._compute_cost_summaries(data),
        cost_ledger=None,
    )


def test_report_omits_cost_keys_for_an_uninstrumented_run():
    report = _report_data(_report_input(_row("task-a")))
    assert "cost_summary" not in report
    assert "cost_ledger" not in report
    assert "problem_solving_cost" not in report["task_results"][0]


def test_report_carries_receipts_and_a_summary():
    data = _report_input(_row("task-a", problem_solving_cost=_receipt()))
    report = _report_data(data)
    assert report["task_results"][0]["problem_solving_cost"]["known_cost_usd"] == 0.25
    assert report["cost_summary"]["problem_solving_cost"]["status"] == "complete"


def test_report_rejects_a_receipt_it_cannot_read():
    data = _report_input(_row("task-a", problem_solving_cost=_receipt(currency="KRW")))
    with pytest.raises(ValueError, match="task-a"):
        step6_report._compute_cost_summaries(data)


def _step6_workspace(tmp_path, monkeypatch, name="cost_ledger_condition_a.jsonl"):
    """A workspace holding a Step 2 export and an upload area to stage into."""
    (tmp_path / "upload").mkdir(parents=True)
    export = tmp_path / name
    export.write_bytes(b'{"call_id": "task-a:generation:0"}\n')
    monkeypatch.setattr(step6_report, "WORKSPACE_DIR", tmp_path)
    digest = hashlib.sha256(export.read_bytes()).hexdigest()
    return {"cost_ledger": {"path": name, "sha256": digest}}


def test_report_publishes_the_ledger_under_the_name_the_upload_expects(
    tmp_path, monkeypatch
):
    # Step 2 names the export after its condition; the Hub repository holds
    # one, under the name the publication allowlist already knows.
    data = _step6_workspace(tmp_path, monkeypatch)

    ledger = step6_report._report_cost_ledger(data, publishing=True)

    assert ledger["path"] == "cost_ledger.jsonl"
    assert ledger["sha256"] == data["cost_ledger"]["sha256"]
    assert (tmp_path / "upload" / "cost_ledger.jsonl").is_file()


def test_report_drops_a_pointer_it_cannot_stage(tmp_path, monkeypatch, capsys):
    data = _step6_workspace(tmp_path, monkeypatch)
    (tmp_path / data["cost_ledger"]["path"]).unlink()

    assert step6_report._report_cost_ledger(data, publishing=True) is None
    assert "publishing no ledger pointer" in capsys.readouterr().out


def test_report_leaves_the_pointer_alone_when_it_is_not_publishing(
    tmp_path, monkeypatch
):
    # Reporting over someone else's result: nothing is being uploaded, so the
    # pointer describes the file it always described.
    data = _step6_workspace(tmp_path, monkeypatch)

    ledger = step6_report._report_cost_ledger(data, publishing=False)

    assert ledger == data["cost_ledger"]
    assert not (tmp_path / "upload" / "cost_ledger.jsonl").exists()


def test_report_refuses_a_ledger_edited_since_the_run(tmp_path, monkeypatch):
    data = _step6_workspace(tmp_path, monkeypatch)
    (tmp_path / data["cost_ledger"]["path"]).write_bytes(b'{"call_id": "other"}\n')

    with pytest.raises(ValueError, match="digest does not match"):
        step6_report._report_cost_ledger(data, publishing=True)


def test_markdown_labels_every_amount_as_an_estimate():
    report = _report_data(_report_input(_row("task-a", problem_solving_cost=_receipt())))
    markdown = step6_report._build_markdown(report)
    assert "## Problem-Solving Cost" in markdown
    assert "Usage-based estimate, not an Azure invoice amount." in markdown
    assert "$0.2500" in markdown


def test_markdown_says_no_record_rather_than_zero_for_an_unpriced_figure():
    unavailable = _unmeasured("unavailable", missing_reasons=["usage_not_recorded"])
    report = _report_data(_report_input(_row("task-a", problem_solving_cost=unavailable)))
    markdown = step6_report._build_markdown(report)
    assert "| Average per task | no record |" in markdown
    assert "unavailable — nothing was recorded" in markdown
    # The headline row is the one a reader takes as *the* number, so it is held
    # to the same standard as the rows beneath it.
    assert "| Recorded so far | no record |" in markdown


def test_markdown_does_not_head_a_run_that_priced_nothing_with_a_zero():
    """A run that paid for two model calls must not head its table with $0.

    Run 33302056462 -- the exp026c cost smoke -- called the model twice against
    `gpt-5.4-2026-03-05`, a snapshot the price table had no entry for. Every
    component came back a placeholder zero, the projector nulled them all, and
    the summariser's `known_cost_usd` fell out as a sum over an empty set: 0.0.

    Every other money row in that table is None and prints "no record". This
    one printed "$0.0000" -- the same string a genuinely free run prints -- in
    the single row a reader reads as the answer. Two paid calls read as free,
    directly beside "Not priced | price_missing".

    Held here rather than in the producer because `known_cost_usd` is published
    and consumed elsewhere; only how this row reads it changes.
    """
    unpriceable = _unmeasured("partial", missing_reasons=["price_missing"])
    report = _report_data(_report_input(_row("task-a", problem_solving_cost=unpriceable)))
    markdown = step6_report._build_markdown(report)

    assert "| Recorded so far | no record |" in markdown
    assert "| Recorded so far | $0.0000 |" not in markdown
    # `Failed tasks | 0 ($0.0000)` is left alone: zero failed tasks did cost
    # zero. Its unpriced variant -- failures whose receipts carry no amount --
    # is the same defect as this one, and is now resolved the same way, by
    # `failed_measured_tasks` on the summary. See the four rendering cases in
    # `test_markdown_failed_task_cost_*` below.
    # Coverage counts receipts, not amounts, so on its own it reads as a fully
    # accounted run. The row that disambiguates it must be present.
    assert "| Coverage | 1 / 1 tasks (100.0%) |" in markdown
    assert "| Priced | 0 / 1 receipts |" in markdown
    assert "| Not priced | price_missing |" in markdown


def _failed_row(task_id: str, receipt: dict) -> dict:
    return _row(
        task_id,
        status="error",
        deliverable_files=[],
        problem_solving_cost=project_cost_receipt(receipt),
    )


def _failed_markdown(*rows) -> str:
    return step6_report._build_markdown(_report_data(_report_input(*rows)))


def test_markdown_failed_task_cost_prints_the_amount_when_every_failure_was_priced():
    """The unchanged case. A priced failure printed its amount and still does."""
    priced = _receipt(estimated_cost_usd=0.4, known_cost_usd=0.4, model_cost_usd=0.4)
    markdown = _failed_markdown(_failed_row("task-a", priced))
    assert "| Failed tasks | 1 ($0.4000) |" in markdown


def test_markdown_failed_task_cost_says_no_record_when_none_could_be_priced():
    """The defect, in the row a reader reads as the answer.

    Two failures billed against a model with no price entry printed
    ``2 ($0.0000)`` -- indistinguishable from two failures that were free.
    """
    unpriced = _unmeasured("partial", missing_reasons=["price_missing"])
    markdown = _failed_markdown(
        _failed_row("task-a", unpriced), _failed_row("task-b", unpriced)
    )
    assert "| Failed tasks | 2 (no record) |" in markdown
    assert "| Failed tasks | 2 ($0.0000) |" not in markdown


def test_markdown_failed_task_cost_discloses_how_much_of_a_mixed_row_was_priced():
    """One priced, one not: an amount that is a floor says how far it reaches."""
    priced = _receipt(estimated_cost_usd=0.4, known_cost_usd=0.4, model_cost_usd=0.4)
    unpriced = _unmeasured("partial", missing_reasons=["price_missing"])
    markdown = _failed_markdown(
        _failed_row("task-a", priced), _failed_row("task-b", unpriced)
    )
    assert "| Failed tasks | 2 ($0.4000, 1 / 2 priced) |" in markdown


def test_markdown_keeps_a_genuinely_free_failure_reading_as_zero():
    """The other half of the discrimination, at the rendering layer.

    ``CostReceipt.free()`` is the one honest ``$0``. It must keep printing
    ``$0.0000`` while the unpriced failure above prints ``no record`` -- before
    this change both printed the same string, one of them falsely.
    """
    free = _receipt(
        estimated_cost_usd=0.0,
        known_cost_usd=0.0,
        model_cost_usd=0.0,
        runtime_cost_usd=0.0,
        model_calls=0,
        components=[],
    )
    markdown = _failed_markdown(_failed_row("task-a", free))
    assert "| Failed tasks | 1 ($0.0000) |" in markdown


def test_markdown_failed_task_row_is_unchanged_for_a_run_with_no_failures():
    """Zero failures did cost zero, and this change must not dress that up."""
    markdown = _failed_markdown(_row("task-a", problem_solving_cost=_receipt()))
    assert "| Failed tasks | 0 ($0.0000) |" in markdown


def test_markdown_reads_a_report_published_before_the_measured_count_existed():
    """Back-compatibility, in the direction that cannot lie.

    ``problem_solving_cost`` summaries are read from an already-published
    ``report_data.json``, so old payloads have no ``failed_measured_tasks``. A
    fully priced run cannot contain an unpriced failure, so there the amount is
    exact; anything less than fully priced is treated as unmeasured rather than
    as a zero.
    """
    priced = _receipt(estimated_cost_usd=0.4, known_cost_usd=0.4, model_cost_usd=0.4)
    summary = summarize_cost_receipts(
        [_failed_row("task-a", priced)], "problem_solving_cost"
    )
    legacy = {k: v for k, v in summary.items() if k != "failed_measured_tasks"}
    assert legacy["measured_tasks"] == legacy["receipt_tasks"]
    assert step6_report._failed_task_cost(legacy) == "1 ($0.4000)"

    # Same row on a run that was not fully priced: the amount is not trusted.
    unpriced = _unmeasured("partial", missing_reasons=["price_missing"])
    mixed = summarize_cost_receipts(
        [_failed_row("task-a", priced), _row("task-b", problem_solving_cost=project_cost_receipt(unpriced))],
        "problem_solving_cost",
    )
    legacy_mixed = {k: v for k, v in mixed.items() if k != "failed_measured_tasks"}
    assert legacy_mixed["measured_tasks"] != legacy_mixed["receipt_tasks"]
    assert step6_report._failed_task_cost(legacy_mixed) == "1 (no record)"


def test_markdown_leaves_a_fully_priced_report_exactly_as_it_was():
    """The unpriced-run fix must not add a row to reports that were already fine.

    `Priced` exists to resolve a contradiction between coverage and the amounts.
    A run with nothing to contradict must print what it printed before, so that
    an existing experiment's report does not change because of this change.
    """
    report = _report_data(_report_input(_row("task-a", problem_solving_cost=_receipt())))
    markdown = step6_report._build_markdown(report)

    assert "| Total | $0.2500 |" in markdown
    assert "| Priced |" not in markdown


def test_markdown_omits_the_cost_section_for_an_uninstrumented_run():
    markdown = step6_report._build_markdown(_report_data(_report_input(_row("task-a"))))
    assert "Problem-Solving Cost" not in markdown
