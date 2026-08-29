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
    assert summary["successful_deliverables"] == 1


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
            "tasks": 2,
            "known_cost_usd": 0.5,
            "complete_tasks": 2,
            "model_calls": 6,
            "status": "complete",
        },
    ]


def test_two_retries_in_one_task_are_one_task_in_the_component_total():
    # `tasks` sits beside the amount as "how many tasks paid this". A task that
    # retried twice paid it once; counting the lines would make that column
    # exceed the number of tasks in the run.
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
            "tasks": 1,
            "known_cost_usd": 0.2,
            "complete_tasks": 1,
            "model_calls": 3,
            "status": "complete",
        },
    ]


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


def test_markdown_omits_the_cost_section_for_an_uninstrumented_run():
    markdown = step6_report._build_markdown(_report_data(_report_input(_row("task-a"))))
    assert "Problem-Solving Cost" not in markdown
