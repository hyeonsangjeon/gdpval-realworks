"""The receipts have to survive the two places a run stops being one run.

The ledger tests elsewhere in this directory prove the bookkeeping is sound in
isolation. This file is about the seams: the point where step 8 turns rows into
a published grade, and the point where step 9 turns eight of those grades back
into one. Both seams rewrite the artifact, and a seam that rewrites money is
where money goes missing.

Nothing here calls a provider. Every figure comes from a fixture price list and
a synthetic usage block.
"""

import hashlib
import json
from decimal import Decimal
from pathlib import Path

import pytest

import step8_grade as s8
import step9_merge_shards as s9
from core.cost_receipts import (
    BUCKET_GRADING,
    REASON_USAGE_ABSENT,
    RETRY_NONE,
    STAGE_GRADING,
    STATUS_COMPLETE,
    STATUS_PARTIAL,
    STATUS_UNAVAILABLE,
    CallUsage,
    CostReceipt,
    CostReceiptLedger,
    load_receipt_price_table,
    make_call_id,
    verify_export,
)
from core.grade_payload import validate_grade_payload


PRICE_TABLE = {
    "cost_receipt_schema_version": "cost-receipt-price-table-v1",
    "providers": {
        "azure:test-model": {
            "input_usd_per_million": "10",
            "cached_input_usd_per_million": "10",
            "output_usd_per_million": "20",
            "reasoning_billed_as": "output",
            "source": "fixture",
            "last_reviewed": "2026-08-28",
            "currency": "USD",
            "unit": "per 1,000,000 tokens",
        }
    },
    "runtime": {},
}


@pytest.fixture
def price_table(tmp_path):
    path = tmp_path / "prices.json"
    path.write_text(json.dumps(PRICE_TABLE), encoding="utf-8")
    return load_receipt_price_table(path)


def _ledger(tmp_path, name, price_table, run_id="run-1"):
    return CostReceiptLedger(
        tmp_path / name, run_id=run_id, price_table=price_table
    )


def _grade_one(ledger, task_id, *, sequence=0, settle=True):
    """Record one judge call for ``task_id`` and return its identifier."""
    call_id = make_call_id(
        run_id=ledger.run_id,
        task_id=task_id,
        stage=STAGE_GRADING,
        retry_kind=RETRY_NONE,
        attempt_index=0,
        sequence=sequence,
    )
    ledger.reserve(
        call_id=call_id,
        task_id=task_id,
        stage=STAGE_GRADING,
        retry_kind=RETRY_NONE,
        provider="azure",
        requested_model="a-deployment",
    )
    if settle:
        ledger.settle(
            call_id,
            usage=CallUsage(
                input_tokens=100_000,
                cached_input_tokens=0,
                output_tokens=10_000,
                reasoning_tokens=0,
            ),
            resolved_model="test-model",
        )
    return call_id


# ── step 9: folding many audit trails into one ───────────────────────────
#
# Each shard published a grade file and, beside it, the ledger that grade was
# read from. The merged grade may only point at a trail that holds all of them.


def _shard_on_disk(tmp_path, price_table, index, task_ids):
    """Write one shard grade file plus the ledger export it points at."""
    directory = tmp_path / f"shard{index}"
    directory.mkdir()
    ledger = _ledger(directory, "ledger.sqlite3", price_table, run_id=f"run-{index}")
    try:
        for sequence, task_id in enumerate(task_ids):
            _grade_one(ledger, task_id, sequence=sequence)
        digest = ledger.export_jsonl(directory / "grade.cost_ledger.jsonl")
    finally:
        ledger.close()
    payload = {"cost_ledger": {"path": "grade.cost_ledger.jsonl", "sha256": digest}}
    shard_path = directory / "grade.json"
    shard_path.write_text(json.dumps(payload), encoding="utf-8")
    return shard_path, payload


def _merged_rows(export: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in export.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_the_merged_trail_holds_every_shards_calls(tmp_path, price_table):
    first = _shard_on_disk(tmp_path, price_table, 0, ["task-a", "task-b"])
    second = _shard_on_disk(tmp_path, price_table, 1, ["task-c"])
    out = tmp_path / "merged.json"

    warnings: list[str] = []
    pointer = s9.merge_shard_cost_ledgers(
        [first[0], second[0]],
        [first[1], second[1]],
        out,
        warn=warnings.append,
    )

    assert warnings == []
    assert pointer is not None
    export = out.with_name(pointer["path"])
    calls = [row for row in _merged_rows(export) if row.get("call_id")]
    assert {row["task_id"] for row in calls} == {"task-a", "task-b", "task-c"}


def test_the_merged_pointer_can_be_checked_against_the_file_it_names(
    tmp_path, price_table
):
    first = _shard_on_disk(tmp_path, price_table, 0, ["task-a"])
    second = _shard_on_disk(tmp_path, price_table, 1, ["task-b"])
    out = tmp_path / "merged.json"

    pointer = s9.merge_shard_cost_ledgers(
        [first[0], second[0]], [first[1], second[1]], out, warn=lambda _m: None
    )

    assert pointer is not None
    assert verify_export(out.with_name(pointer["path"]), pointer["sha256"])


def test_the_same_shard_folded_in_twice_is_still_one_bill(tmp_path, price_table):
    """A retried merge must not double what the shard actually spent."""
    shard = _shard_on_disk(tmp_path, price_table, 0, ["task-a", "task-b"])
    out = tmp_path / "merged.json"

    once = s9.merge_shard_cost_ledgers(
        [shard[0]], [shard[1]], out, warn=lambda _m: None
    )
    twice = s9.merge_shard_cost_ledgers(
        [shard[0], shard[0]],
        [shard[1], shard[1]],
        tmp_path / "merged2.json",
        warn=lambda _m: None,
    )

    assert once is not None and twice is not None
    assert once["sha256"] == twice["sha256"]


def test_a_shard_with_no_pointer_stops_the_merged_trail(tmp_path, price_table):
    """Silence about one shard must not be published as a complete trail."""
    good = _shard_on_disk(tmp_path, price_table, 0, ["task-a"])
    blind = tmp_path / "shard-blind.json"
    blind.write_text(json.dumps({"cost_ledger": None}), encoding="utf-8")

    warnings: list[str] = []
    pointer = s9.merge_shard_cost_ledgers(
        [good[0], blind],
        [good[1], {"cost_ledger": None}],
        tmp_path / "merged.json",
        warn=warnings.append,
    )

    assert pointer is None
    assert any("shard-blind.json" in message for message in warnings)


def test_a_pointer_to_a_file_that_is_gone_stops_the_merged_trail(
    tmp_path, price_table
):
    shard_path, payload = _shard_on_disk(tmp_path, price_table, 0, ["task-a"])
    shard_path.with_name(payload["cost_ledger"]["path"]).unlink()

    warnings: list[str] = []
    pointer = s9.merge_shard_cost_ledgers(
        [shard_path], [payload], tmp_path / "merged.json", warn=warnings.append
    )

    assert pointer is None
    assert any("not beside it" in message for message in warnings)


def test_a_trail_that_no_longer_matches_its_digest_stops_the_merge(
    tmp_path, price_table
):
    """An edited audit trail is worth less than no audit trail at all."""
    shard_path, payload = _shard_on_disk(tmp_path, price_table, 0, ["task-a"])
    export = shard_path.with_name(payload["cost_ledger"]["path"])
    rows = _merged_rows(export)
    for row in rows:
        if row.get("call_id"):
            row["model_cost_usd"] = 0.0
    export.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )

    warnings: list[str] = []
    pointer = s9.merge_shard_cost_ledgers(
        [shard_path], [payload], tmp_path / "merged.json", warn=warnings.append
    )

    assert pointer is None
    assert any("does not match the digest" in message for message in warnings)


def test_two_shards_that_disagree_about_one_call_stop_the_merged_trail(
    tmp_path, price_table
):
    """Same identifier, different money: one of the two is wrong, so stop.

    Deduplication by identifier is what makes an overlapping merge safe. It is
    only safe while the identifier means the same call; a collision carrying a
    different figure is a contradiction, and picking either number would be
    publishing a guess. The grade itself still publishes — the per-task receipts
    travel in the rows — but it publishes without claiming an audit trail.
    """
    first_path, first = _shard_on_disk(tmp_path, price_table, 0, ["task-a"])
    second_path, second = _shard_on_disk(tmp_path, price_table, 1, ["task-a"])
    # Same run identity on both sides, so the call identifiers collide.
    forged = second_path.with_name(second["cost_ledger"]["path"])
    rows = _merged_rows(first_path.with_name(first["cost_ledger"]["path"]))
    for row in rows:
        if row.get("call_id"):
            row["output_tokens"] = 999_999
    forged.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    second["cost_ledger"]["sha256"] = hashlib.sha256(
        forged.read_bytes()
    ).hexdigest()

    warnings: list[str] = []
    pointer = s9.merge_shard_cost_ledgers(
        [first_path, second_path],
        [first, second],
        tmp_path / "merged.json",
        warn=warnings.append,
    )

    assert pointer is None
    assert any("LedgerIntegrityError" in message for message in warnings)


# ── step 9: the arithmetic-free cross-check ──────────────────────────────


def _summary(calls):
    return {BUCKET_GRADING: {"model_calls": calls}}


def test_shard_call_counts_must_add_up_to_the_merged_count():
    s9._check_grading_call_sums(
        [{"summary": _summary(3)}, {"summary": _summary(4)}],
        ["shard-0", "shard-1"],
        _summary(7),
    )


def test_a_shard_whose_receipts_did_not_arrive_is_caught():
    with pytest.raises(s9.ShardMergeError) as excinfo:
        s9._check_grading_call_sums(
            [{"summary": _summary(3)}, {"summary": _summary(4)}],
            ["shard-0", "shard-1"],
            _summary(3),
        )
    assert "shard_sum=7" in str(excinfo.value)


def test_a_shard_that_carries_no_receipt_cannot_be_checked_and_is_refused():
    with pytest.raises(s9.ShardMergeError) as excinfo:
        s9._check_grading_call_sums(
            [{"summary": _summary(3)}, {"summary": {}}],
            ["shard-0", "shard-1"],
            _summary(3),
        )
    assert "shard-1" in str(excinfo.value)


def test_a_call_count_that_is_not_a_count_is_refused():
    with pytest.raises(s9.ShardMergeError) as excinfo:
        s9._check_grading_call_sums(
            [{"summary": _summary(3.0)}],
            ["shard-0"],
            _summary(3),
        )
    assert "must be an integer" in str(excinfo.value)


# ── the ledger seam: an import that closes an open question ──────────────


def test_an_open_reservation_is_closed_by_the_settlement_that_arrives(
    tmp_path, price_table
):
    """One process saw the request go out; another saw how it ended.

    Before the merge the local row can only say ``call_reachability_unknown``,
    which holds the whole task's receipt at ``partial`` forever. Taking the
    outcome from the arriving export resolves a doubt rather than overwriting a
    figure.
    """
    sender = _ledger(tmp_path, "sender.sqlite3", price_table)
    try:
        _grade_one(sender, "task-a")
        digest = sender.export_jsonl(tmp_path / "settled.jsonl")
    finally:
        sender.close()
    assert digest

    local = _ledger(tmp_path, "local.sqlite3", price_table)
    try:
        _grade_one(local, "task-a", settle=False)
        assert local.receipt_for("task-a", bucket=BUCKET_GRADING).status == (
            STATUS_PARTIAL
        )

        local.import_jsonl(tmp_path / "settled.jsonl")

        receipt = local.receipt_for("task-a", bucket=BUCKET_GRADING)
        assert receipt.status == STATUS_COMPLETE
        assert receipt.model_calls == 1
        assert receipt.estimated_cost_usd == Decimal("1.2")
    finally:
        local.close()


def test_a_settled_call_is_not_reopened_by_a_reservation_that_arrives(
    tmp_path, price_table
):
    """The reverse direction is a demotion, and a bill does not become a doubt."""
    opener = _ledger(tmp_path, "opener.sqlite3", price_table)
    try:
        _grade_one(opener, "task-a", settle=False)
        opener.export_jsonl(tmp_path / "reserved.jsonl")
    finally:
        opener.close()

    local = _ledger(tmp_path, "local.sqlite3", price_table)
    try:
        _grade_one(local, "task-a")
        local.import_jsonl(tmp_path / "reserved.jsonl")

        receipt = local.receipt_for("task-a", bucket=BUCKET_GRADING)
        assert receipt.status == STATUS_COMPLETE
        assert receipt.estimated_cost_usd == Decimal("1.2")
    finally:
        local.close()


# ── step 8: the published rows are what the run total is made of ─────────


def _graded_row(task_id, receipt, *, pct=100.0):
    return {
        "task_id": task_id,
        "pct": pct,
        "total_awarded": 1,
        "total_max": 1,
        "items": [{"target_id": "c1", "verdict": "pass", "decided_by": "rule"}],
        BUCKET_GRADING: receipt.as_dict(),
    }


def _receipt(status, **overrides):
    """A one-call receipt, built through the real type rather than by hand.

    Going through :class:`CostReceipt` means the row these tests publish is
    exactly the shape ``from_dict`` will read back — a literal dict here would
    drift from the type the moment either side gained a field.
    """
    fields = {
        "status": status,
        "known_cost_usd": Decimal("1.2"),
        "model_cost_usd": Decimal("1.2"),
        "model_calls": 1,
        "usage": {
            "input_tokens": 100_000,
            "cached_input_tokens": 0,
            "output_tokens": 10_000,
            "reasoning_tokens": 0,
        },
        "missing_reasons": (
            () if status == STATUS_COMPLETE else (REASON_USAGE_ABSENT,)
        ),
    }
    fields.update(overrides)
    return CostReceipt(**fields)


def test_a_run_total_is_summed_from_the_rows_that_were_published():
    summary = s8._compute_summary(
        [
            _graded_row("task-a", _receipt(STATUS_COMPLETE)),
            _graded_row("task-b", _receipt(STATUS_COMPLETE)),
        ],
        unpriced_models=["gpt-5.4"],
    )

    assert summary[BUCKET_GRADING]["status"] == STATUS_COMPLETE
    assert summary[BUCKET_GRADING]["model_calls"] == 2
    assert summary[BUCKET_GRADING]["estimated_cost_usd"] == pytest.approx(2.4)


def test_one_unknown_row_turns_the_run_total_into_a_floor():
    """A total is only a total when every part behind it is known."""
    summary = s8._compute_summary(
        [
            _graded_row("task-a", _receipt(STATUS_COMPLETE)),
            _graded_row("task-b", _receipt(STATUS_PARTIAL)),
        ],
        unpriced_models=["gpt-5.4"],
    )

    receipt = summary[BUCKET_GRADING]
    assert receipt["status"] == STATUS_PARTIAL
    assert receipt["estimated_cost_usd"] is None
    assert receipt["known_cost_usd"] == pytest.approx(2.4)


def test_rows_from_before_receipts_existed_do_not_read_as_free():
    summary = s8._compute_summary(
        [_graded_row("task-a", CostReceipt.unavailable())],
        unpriced_models=["gpt-5.4"],
    )

    receipt = summary[BUCKET_GRADING]
    assert receipt["status"] == STATUS_UNAVAILABLE
    assert receipt["estimated_cost_usd"] is None
    assert receipt["known_cost_usd"] == 0.0


def test_a_row_marked_entirely_by_rule_really_did_cost_nothing():
    """The one honest zero: no judge was asked, so there is nothing to pay."""
    summary = s8._compute_summary(
        [_graded_row("task-a", CostReceipt.free())],
        unpriced_models=["gpt-5.4"],
    )

    receipt = summary[BUCKET_GRADING]
    assert receipt["status"] == STATUS_COMPLETE
    assert receipt["estimated_cost_usd"] == 0.0
    assert receipt["model_calls"] == 0


# ── the published invariant: a summary cannot outrun its rows ────────────


def _grade_payload(rows, run_receipt, schema_version="1.4"):
    """A minimal 1.4 payload that carries the receipt fields under test."""
    task_ids = [row["task_id"] for row in rows]
    fingerprint = "a" * 64
    return {
        "schema_version": schema_version,
        "run_status": "final",
        "expected_task_count": len(rows),
        "expected_ordered_task_ids_sha256": s8._ordered_task_ids_sha256(task_ids),
        "azure_ai_routes": [
            {
                "endpoint_kind": "direct-v1",
                "profile": "direct-v1",
                "runtime_fingerprint": fingerprint,
                "workload": "grader",
            }
        ],
        "azure_ai_runtime_fingerprint": fingerprint,
        "judge": {"model": "gpt-5.4"},
        "cost_ledger": None,
        "tasks": rows,
        "summary": {
            "total_tasks": len(rows),
            "graded_tasks": len(rows),
            "error_tasks": 0,
            "openai_compat": {"avg_score_pct": 100.0},
            "wow": {"judge_error_rate": 0.0},
            "cost": {
                "estimated_cost_usd": None,
                "pricing_complete": False,
                "unpriced_models": ["gpt-5.4"],
            },
            BUCKET_GRADING: run_receipt.as_dict(),
        },
    }


def test_a_summary_claiming_a_complete_bill_over_an_unknown_row_is_refused():
    payload = _grade_payload(
        [
            _graded_row("task-a", _receipt(STATUS_COMPLETE)),
            _graded_row("task-b", _receipt(STATUS_PARTIAL)),
        ],
        _receipt(STATUS_COMPLETE),
    )

    with pytest.raises(ValueError, match="complete cost over an incomplete task"):
        validate_grade_payload(payload, {})


def test_a_row_that_was_never_graded_does_not_spoil_the_shards_bill():
    """A shard that graded ten of two hundred has a complete bill for ten."""
    payload = _grade_payload(
        [
            _graded_row("task-a", _receipt(STATUS_COMPLETE)),
            _graded_row("task-b", CostReceipt.not_run()),
        ],
        _receipt(STATUS_COMPLETE),
    )

    validate_grade_payload(payload, {})


def test_a_1_4_row_without_a_receipt_at_all_is_refused():
    rows = [_graded_row("task-a", _receipt(STATUS_COMPLETE))]
    rows[0].pop(BUCKET_GRADING)
    payload = _grade_payload(rows, _receipt(STATUS_COMPLETE))

    with pytest.raises(ValueError, match="task is missing its cost receipt"):
        validate_grade_payload(payload, {})


def test_a_1_3_grade_is_not_asked_for_receipts_it_never_had():
    """Read compatibility: older grades stay valid and stay readable."""
    rows = [_graded_row("task-a", _receipt(STATUS_COMPLETE))]
    rows[0].pop(BUCKET_GRADING)
    payload = _grade_payload(rows, _receipt(STATUS_COMPLETE), schema_version="1.3")
    payload["summary"].pop(BUCKET_GRADING)
    payload.pop("cost_ledger")

    validate_grade_payload(payload, {})
