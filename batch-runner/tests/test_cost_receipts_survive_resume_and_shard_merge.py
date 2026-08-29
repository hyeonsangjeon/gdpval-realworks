"""Costs survive the things that replace results: resuming and merging.

A run that stops halfway and starts again produces one set of deliverables and
two sets of bills. A grading job split across eight shards produces eight
ledgers for one experiment. Both cases end with the earlier record being
folded into the later one, and in both the temptation is to let the newest
write win — which would quietly discard money that was really spent.

These tests fix the opposite behaviour: the union, deduplicated by an
identifier that two processes can compute without talking to each other.
"""

import json
from decimal import Decimal

import pytest

from core.cost_metering import CostRecorder
from core.cost_receipts import (
    BUCKET_GRADING,
    BUCKET_PROBLEM_SOLVING,
    RETRY_NONE,
    RETRY_RESUME,
    STAGE_GENERATION,
    STAGE_GRADING,
    STAGE_PERCEPTION,
    STAGE_PREPROCESSING,
    STAGE_SELF_QA,
    STATUS_COMPLETE,
    CallUsage,
    CostReceiptLedger,
    LedgerIntegrityError,
    load_receipt_price_table,
    make_call_id,
    summarise_receipts,
)

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


def _open(tmp_path, name, price_table, run_id="run-1"):
    return CostReceiptLedger(
        tmp_path / name, run_id=run_id, price_table=price_table
    )


def _usage(input_tokens=100_000, output_tokens=10_000):
    return CallUsage(
        input_tokens=input_tokens,
        cached_input_tokens=0,
        output_tokens=output_tokens,
        reasoning_tokens=0,
    )


def _spend(ledger, task_id, *, stage, retry_kind=RETRY_NONE, attempt=0, sequence=0):
    call_id = make_call_id(
        run_id=ledger.run_id,
        task_id=task_id,
        stage=stage,
        retry_kind=retry_kind,
        attempt_index=attempt,
        sequence=sequence,
    )
    ledger.reserve(
        call_id=call_id,
        task_id=task_id,
        stage=stage,
        retry_kind=retry_kind,
        provider="azure",
        requested_model="a-deployment",
    )
    ledger.settle(call_id, usage=_usage(), resolved_model="test-model")
    return call_id


# ── resume ───────────────────────────────────────────────────────────────


def test_a_resumed_round_adds_to_the_earlier_bill_instead_of_replacing_it(
    tmp_path, price_table
):
    with _open(tmp_path, "round1.sqlite3", price_table) as first:
        _spend(first, "task-a", stage=STAGE_GENERATION)
        export = tmp_path / "round1.jsonl"
        first.export_jsonl(export)
        before = first.receipt_for("task-a", BUCKET_PROBLEM_SOLVING)

    with _open(tmp_path, "round2.sqlite3", price_table) as second:
        assert second.import_jsonl(export) == 1
        _spend(
            second,
            "task-a",
            stage=STAGE_GENERATION,
            retry_kind=RETRY_RESUME,
            attempt=1,
        )
        after = second.receipt_for("task-a", BUCKET_PROBLEM_SOLVING)

    assert before.model_calls == 1
    assert after.model_calls == 2
    assert after.known_cost_usd == before.known_cost_usd * 2
    assert after.status == STATUS_COMPLETE


def test_a_second_round_does_not_collide_with_the_first_rounds_identifiers(
    tmp_path, price_table
):
    """Numbering the round is what keeps two first-calls apart."""
    with _open(tmp_path, "cost.sqlite3", price_table) as ledger:
        first_round = CostRecorder(ledger, round_index=0)
        second_round = CostRecorder(ledger, round_index=1)

        with first_round.attributed(task_id="task-a", stage=STAGE_GENERATION) as one:
            first_id = first_round._next_call_id(one)
        with second_round.attributed(task_id="task-a", stage=STAGE_GENERATION) as two:
            second_id = second_round._next_call_id(two)

    assert first_id != second_id


def test_importing_the_same_round_twice_does_not_double_the_bill(
    tmp_path, price_table
):
    """Re-running a merge step must be safe."""
    with _open(tmp_path, "round1.sqlite3", price_table) as first:
        _spend(first, "task-a", stage=STAGE_GENERATION)
        export = tmp_path / "round1.jsonl"
        first.export_jsonl(export)

    with _open(tmp_path, "round2.sqlite3", price_table) as second:
        assert second.import_jsonl(export) == 1
        assert second.import_jsonl(export) == 0
        receipt = second.receipt_for("task-a", BUCKET_PROBLEM_SOLVING)

    assert receipt.model_calls == 1
    assert receipt.estimated_cost_usd == Decimal("1.20")


def test_an_import_that_contradicts_a_recorded_cost_is_refused(
    tmp_path, price_table
):
    with _open(tmp_path, "one.sqlite3", price_table) as first:
        call_id = _spend(first, "task-a", stage=STAGE_GENERATION)
        export = tmp_path / "one.jsonl"
        first.export_jsonl(export)

    tampered = tmp_path / "tampered.jsonl"
    record = json.loads(export.read_text(encoding="utf-8").splitlines()[0])
    record["input_tokens"] = 1
    record["model_cost_usd"] = "0.00001"
    tampered.write_text(json.dumps(record) + "\n", encoding="utf-8")

    with _open(tmp_path, "two.sqlite3", price_table) as second:
        second.import_jsonl(export)
        with pytest.raises(LedgerIntegrityError):
            second.import_jsonl(tampered)
        assert second.calls_for("task-a")[0]["call_id"] == call_id


# ── shard merge ──────────────────────────────────────────────────────────


def test_shards_merge_into_the_union_of_what_they_each_spent(
    tmp_path, price_table
):
    exports = []
    for shard in range(3):
        with _open(tmp_path, f"shard{shard}.sqlite3", price_table) as ledger:
            _spend(ledger, f"task-{shard}", stage=STAGE_GRADING)
            _spend(ledger, f"task-{shard}", stage=STAGE_PERCEPTION)
            export = tmp_path / f"shard{shard}.jsonl"
            ledger.export_jsonl(export)
            exports.append(export)

    with _open(tmp_path, "merged.sqlite3", price_table) as merged:
        added = sum(merged.import_jsonl(export) for export in exports)
        receipts = [
            merged.receipt_for(task_id, BUCKET_GRADING)
            for task_id in merged.task_ids()
        ]
        summary = summarise_receipts(receipts)

    assert added == 6
    assert len(receipts) == 3
    assert summary.model_calls == 6
    assert summary.status == STATUS_COMPLETE
    assert summary.estimated_cost_usd == Decimal("7.20")


def test_overlapping_shards_count_a_shared_call_once(tmp_path, price_table):
    """Two shards that both handled a task must not bill it twice."""
    exports = []
    for shard in range(2):
        with _open(tmp_path, f"shard{shard}.sqlite3", price_table) as ledger:
            _spend(ledger, "task-a", stage=STAGE_GRADING)
            export = tmp_path / f"shard{shard}.jsonl"
            ledger.export_jsonl(export)
            exports.append(export)

    with _open(tmp_path, "merged.sqlite3", price_table) as merged:
        for export in exports:
            merged.import_jsonl(export)
        receipt = merged.receipt_for("task-a", BUCKET_GRADING)

    assert receipt.model_calls == 1
    assert receipt.estimated_cost_usd == Decimal("1.20")


def test_a_merged_ledger_exports_a_digest_a_reader_can_check(
    tmp_path, price_table
):
    with _open(tmp_path, "shard.sqlite3", price_table) as shard:
        _spend(shard, "task-a", stage=STAGE_GRADING)
        shard_export = tmp_path / "shard.jsonl"
        shard.export_jsonl(shard_export)

    with _open(tmp_path, "merged.sqlite3", price_table) as merged:
        merged.import_jsonl(shard_export)
        digest = merged.export_jsonl(tmp_path / "merged.jsonl")

    assert len(digest) == 64
    assert int(digest, 16) >= 0


# ── the two pipelines stay apart ─────────────────────────────────────────


def test_the_two_totals_are_built_from_disjoint_sets_of_calls(
    tmp_path, price_table
):
    with _open(tmp_path, "cost.sqlite3", price_table) as ledger:
        for stage in (STAGE_PREPROCESSING, STAGE_GENERATION, STAGE_SELF_QA):
            _spend(ledger, "task-a", stage=stage)
        for stage in (STAGE_GRADING, STAGE_PERCEPTION):
            _spend(ledger, "task-a", stage=stage)

        solving = ledger.receipt_for("task-a", BUCKET_PROBLEM_SOLVING)
        grading = ledger.receipt_for("task-a", BUCKET_GRADING)
        every_call = ledger.calls_for("task-a")

    assert solving.model_calls == 3
    assert grading.model_calls == 2
    assert solving.model_calls + grading.model_calls == len(every_call)
    assert {component.stage for component in solving.components}.isdisjoint(
        {component.stage for component in grading.components}
    )


def test_the_solving_total_is_the_sum_of_its_stages_and_retries(
    tmp_path, price_table
):
    """The arithmetic the contract promises, to the last cent."""
    with _open(tmp_path, "cost.sqlite3", price_table) as ledger:
        _spend(ledger, "task-a", stage=STAGE_PREPROCESSING)
        _spend(ledger, "task-a", stage=STAGE_GENERATION)
        _spend(ledger, "task-a", stage=STAGE_SELF_QA, sequence=0)
        _spend(ledger, "task-a", stage=STAGE_SELF_QA, sequence=1)
        _spend(
            ledger,
            "task-a",
            stage=STAGE_GENERATION,
            retry_kind=RETRY_RESUME,
            attempt=1,
        )
        receipt = ledger.receipt_for("task-a", BUCKET_PROBLEM_SOLVING)

    parts = sum(
        (component.known_cost_usd for component in receipt.components), Decimal(0)
    )

    assert receipt.model_calls == 5
    assert parts == receipt.known_cost_usd == Decimal("6.00")
    assert receipt.estimated_cost_usd == Decimal("6.00")


def test_an_experiment_summary_is_not_complete_if_one_task_is_not(
    tmp_path, price_table
):
    """A headline that silently drops a task reads as if it had not."""
    with _open(tmp_path, "cost.sqlite3", price_table) as ledger:
        _spend(ledger, "task-a", stage=STAGE_GENERATION)
        unfinished = make_call_id(
            run_id=ledger.run_id,
            task_id="task-b",
            stage=STAGE_GENERATION,
            retry_kind=RETRY_NONE,
            attempt_index=0,
            sequence=0,
        )
        ledger.reserve(
            call_id=unfinished,
            task_id="task-b",
            stage=STAGE_GENERATION,
            retry_kind=RETRY_NONE,
            provider="azure",
            requested_model="a-deployment",
        )
        summary = summarise_receipts(
            [
                ledger.receipt_for(task_id, BUCKET_PROBLEM_SOLVING)
                for task_id in ledger.task_ids()
            ]
        )

    assert summary.status == "partial"
    assert summary.estimated_cost_usd is None
    assert summary.known_cost_usd == Decimal("1.20")


def test_a_summary_over_tasks_that_never_ran_says_so(tmp_path, price_table):
    with _open(tmp_path, "cost.sqlite3", price_table) as ledger:
        summary = summarise_receipts(
            [
                ledger.receipt_for("task-a", BUCKET_GRADING),
                ledger.receipt_for("task-b", BUCKET_GRADING),
            ]
        )

    assert summary.status == "not_run"
    assert summary.as_dict()["estimated_cost_usd"] is None
