"""The ledger's promise: a call that happened stays recorded.

Costs are not the record of what worked. A task that failed after four
attempts was billed for four attempts, and a run that threw its first answer
away and generated a second one paid for both. These tests hold the ledger to
that — and to the other half of the promise, that a call which never left the
process is not charged for.
"""

import json
from decimal import Decimal

import pytest

from core.cost_receipts import (
    BUCKET_GRADING,
    BUCKET_PROBLEM_SOLVING,
    COMPONENT_NAMES,
    COMPONENT_RETRY,
    REASON_CALL_REACHABILITY_UNKNOWN,
    RETRY_INFRASTRUCTURE,
    RETRY_NONE,
    RETRY_SEMANTIC,
    STAGE_GENERATION,
    STAGE_GRADING,
    STAGE_SELF_QA,
    STATUS_COMPLETE,
    STATUS_PARTIAL,
    CallUsage,
    CostReceiptLedger,
    LedgerIntegrityError,
    load_receipt_price_table,
    make_call_id,
    verify_export,
)

PRICE_TABLE = {
    "cost_receipt_schema_version": "cost-receipt-price-table-v1",
    "providers": {
        "azure:test-model": {
            "input_usd_per_million": "10",
            "cached_input_usd_per_million": "1",
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


@pytest.fixture
def ledger(tmp_path, price_table):
    with CostReceiptLedger(
        tmp_path / "cost.sqlite3", run_id="run-1", price_table=price_table
    ) as opened:
        yield opened


def _spend(ledger, task_id, *, stage, retry_kind, sequence, usage=None):
    call_id = make_call_id(
        run_id=ledger.run_id,
        task_id=task_id,
        stage=stage,
        retry_kind=retry_kind,
        attempt_index=0,
        sequence=sequence,
    )
    ledger.reserve(
        call_id=call_id,
        task_id=task_id,
        stage=stage,
        retry_kind=retry_kind,
        provider="azure",
        requested_model="test-deployment",
    )
    if usage is not None:
        ledger.settle(call_id, usage=usage, resolved_model="test-model")
    return call_id


def _usage(input_tokens=100_000, output_tokens=10_000, cached=0):
    return CallUsage(
        input_tokens=input_tokens,
        cached_input_tokens=cached,
        output_tokens=output_tokens,
        reasoning_tokens=0,
    )


def test_a_task_that_failed_still_shows_what_it_cost(ledger):
    """Four attempts, no usable answer, and a bill for all four."""
    for sequence in range(4):
        _spend(
            ledger,
            "task-a",
            stage=STAGE_GENERATION,
            retry_kind=RETRY_NONE if sequence == 0 else RETRY_INFRASTRUCTURE,
            sequence=sequence,
            usage=_usage(),
        )

    receipt = ledger.receipt_for("task-a", BUCKET_PROBLEM_SOLVING)

    assert receipt.status == STATUS_COMPLETE
    assert receipt.model_calls == 4
    # 100k in at $10/M plus 10k out at $20/M is $1.20 a call.
    assert receipt.estimated_cost_usd == Decimal("4.80")


def test_a_regenerated_answer_does_not_erase_what_the_first_one_cost(ledger):
    """The discarded attempt is still on the bill."""
    _spend(
        ledger,
        "task-a",
        stage=STAGE_GENERATION,
        retry_kind=RETRY_NONE,
        sequence=0,
        usage=_usage(),
    )
    first = ledger.receipt_for("task-a", BUCKET_PROBLEM_SOLVING)

    _spend(
        ledger,
        "task-a",
        stage=STAGE_GENERATION,
        retry_kind=RETRY_SEMANTIC,
        sequence=0,
        usage=_usage(),
    )
    second = ledger.receipt_for("task-a", BUCKET_PROBLEM_SOLVING)

    assert second.known_cost_usd == first.known_cost_usd * 2
    assert second.model_calls == 2
    assert {component.retry_kind for component in second.components} == {
        RETRY_NONE,
        RETRY_SEMANTIC,
    }


# ── the name a reader shows for each line ────────────────────────────────
#
# ``(stage, retry_kind)`` is the honest shape, but a breakdown with one row per
# line needs one word. Deriving it here rather than leaving each reader to
# invent its own is what keeps two displays of the same receipt from disagreeing
# about what a line is called.


def test_every_line_is_named_from_the_published_vocabulary(ledger):
    for sequence, (stage, retry_kind) in enumerate((
        (STAGE_GENERATION, RETRY_NONE),
        (STAGE_GENERATION, RETRY_SEMANTIC),
        (STAGE_SELF_QA, RETRY_NONE),
    )):
        _spend(
            ledger,
            "task-a",
            stage=stage,
            retry_kind=retry_kind,
            sequence=sequence,
            usage=_usage(),
        )

    receipt = ledger.receipt_for("task-a", BUCKET_PROBLEM_SOLVING)

    assert receipt.components
    assert all(
        component.name in COMPONENT_NAMES for component in receipt.components
    )
    assert all(
        entry["name"] in COMPONENT_NAMES
        for entry in receipt.as_dict()["components"]
    )


def test_first_work_is_named_for_its_stage_and_a_repeat_is_named_retry(ledger):
    """"What did retrying cost" is the question, so retries share a name.

    Which stage a retry belonged to is not lost — ``stage`` sits on the same
    line — but a reader that shows one row per name gets the answer without
    having to sum across rows itself.
    """
    for sequence, (stage, retry_kind) in enumerate((
        (STAGE_GENERATION, RETRY_NONE),
        (STAGE_GENERATION, RETRY_SEMANTIC),
        (STAGE_SELF_QA, RETRY_INFRASTRUCTURE),
    )):
        _spend(
            ledger,
            "task-a",
            stage=stage,
            retry_kind=retry_kind,
            sequence=sequence,
            usage=_usage(),
        )

    by_name: dict[str, list] = {}
    for component in ledger.receipt_for(
        "task-a", BUCKET_PROBLEM_SOLVING
    ).components:
        by_name.setdefault(component.name, []).append(component)

    assert set(by_name) == {STAGE_GENERATION, COMPONENT_RETRY}
    # Both retries land on the one name, and each still says which stage it
    # was a retry of.
    assert {
        component.stage for component in by_name[COMPONENT_RETRY]
    } == {STAGE_GENERATION, STAGE_SELF_QA}


def test_a_runtime_fee_does_not_become_a_line_that_gets_counted_twice(tmp_path):
    """Runtime is reported once, as its own field, and never as a line.

    A reader that sums the lines and then adds ``runtime_cost_usd`` — the
    obvious way to show a breakdown and a total together — would charge the
    container twice if it appeared in both.

    This one builds its own ledger: the price list shared by the rest of the
    file prices no runtime at all, which would leave the fee unpriced and prove
    nothing about where a priced fee lands.
    """
    path = tmp_path / "with-runtime.json"
    path.write_text(
        json.dumps({
            **PRICE_TABLE,
            "runtime": {
                "own-container": {
                    "usd_per_hour": "3.60",
                    "attribution": "per_task",
                    "source": "fixture",
                    "last_reviewed": "2026-08-28",
                    "currency": "USD",
                }
            },
        }),
        encoding="utf-8",
    )
    with CostReceiptLedger(
        tmp_path / "runtime.sqlite3",
        run_id="run-1",
        price_table=load_receipt_price_table(path),
    ) as ledger:
        _spend(
            ledger,
            "task-a",
            stage=STAGE_GENERATION,
            retry_kind=RETRY_NONE,
            sequence=0,
            usage=_usage(),
        )
        ledger.record_runtime_cost(
            entry_id="task-a:own",
            task_id="task-a",
            bucket=BUCKET_PROBLEM_SOLVING,
            runtime_kind="own-container",
            seconds=3600,
        )
        receipt = ledger.receipt_for("task-a", BUCKET_PROBLEM_SOLVING)

    assert receipt.runtime_cost_usd == Decimal("3.60")
    assert "runtime" not in {component.name for component in receipt.components}
    assert sum(
        (component.known_cost_usd for component in receipt.components),
        Decimal(0),
    ) == receipt.model_cost_usd


def test_settling_the_same_call_twice_bills_it_once(ledger):
    """A retried write must not double the bill."""
    call_id = _spend(
        ledger,
        "task-a",
        stage=STAGE_GENERATION,
        retry_kind=RETRY_NONE,
        sequence=0,
        usage=_usage(),
    )
    ledger.settle(call_id, usage=_usage(), resolved_model="test-model")

    receipt = ledger.receipt_for("task-a", BUCKET_PROBLEM_SOLVING)

    assert receipt.model_calls == 1
    assert receipt.estimated_cost_usd == Decimal("1.20")


def test_settling_the_same_call_with_different_numbers_is_refused(ledger):
    """Two beliefs about one call's cost is a fault, not a merge."""
    call_id = _spend(
        ledger,
        "task-a",
        stage=STAGE_GENERATION,
        retry_kind=RETRY_NONE,
        sequence=0,
        usage=_usage(),
    )

    with pytest.raises(LedgerIntegrityError):
        ledger.settle(
            call_id, usage=_usage(input_tokens=999), resolved_model="test-model"
        )


def test_a_call_that_never_left_the_process_costs_nothing(ledger):
    """Failing to build a request is not spending money."""
    call_id = _spend(
        ledger,
        "task-a",
        stage=STAGE_GENERATION,
        retry_kind=RETRY_NONE,
        sequence=0,
    )
    ledger.abandon(call_id, note="prompt could not be assembled")
    _spend(
        ledger,
        "task-a",
        stage=STAGE_GENERATION,
        retry_kind=RETRY_INFRASTRUCTURE,
        sequence=0,
        usage=_usage(),
    )

    receipt = ledger.receipt_for("task-a", BUCKET_PROBLEM_SOLVING)

    assert receipt.status == STATUS_COMPLETE
    assert receipt.model_calls == 1
    assert receipt.estimated_cost_usd == Decimal("1.20")


def test_an_abandoned_call_cannot_later_report_usage(ledger):
    """Recording a call as never sent is a claim, and it has to stay true."""
    call_id = _spend(
        ledger,
        "task-a",
        stage=STAGE_GENERATION,
        retry_kind=RETRY_NONE,
        sequence=0,
    )
    ledger.abandon(call_id)

    with pytest.raises(LedgerIntegrityError):
        ledger.settle(call_id, usage=_usage(), resolved_model="test-model")


def test_a_settled_call_cannot_later_be_called_unsent(ledger):
    call_id = _spend(
        ledger,
        "task-a",
        stage=STAGE_GENERATION,
        retry_kind=RETRY_NONE,
        sequence=0,
        usage=_usage(),
    )

    with pytest.raises(LedgerIntegrityError):
        ledger.abandon(call_id)


def test_a_call_that_was_never_reserved_cannot_be_settled(ledger):
    """Settlement without a reservation means a call went out unrecorded."""
    with pytest.raises(LedgerIntegrityError):
        ledger.settle("0" * 64, usage=_usage(), resolved_model="test-model")


def test_a_request_that_never_came_back_holds_the_receipt_open(ledger):
    """A timeout may still have been billed, so it is not written off."""
    _spend(
        ledger,
        "task-a",
        stage=STAGE_GENERATION,
        retry_kind=RETRY_NONE,
        sequence=0,
        usage=_usage(),
    )
    _spend(
        ledger,
        "task-a",
        stage=STAGE_GENERATION,
        retry_kind=RETRY_INFRASTRUCTURE,
        sequence=0,
    )

    receipt = ledger.receipt_for("task-a", BUCKET_PROBLEM_SOLVING)

    assert receipt.status == STATUS_PARTIAL
    assert receipt.estimated_cost_usd is None
    assert REASON_CALL_REACHABILITY_UNKNOWN in receipt.missing_reasons
    # What is known is still reported — as a floor, not a total.
    assert receipt.known_cost_usd == Decimal("1.20")


def test_the_ledger_records_no_prompt_text(ledger):
    """The ledger is written to be publishable."""
    ledger.reserve(
        call_id="a" * 64,
        task_id="task-a",
        stage=STAGE_GENERATION,
        retry_kind=RETRY_NONE,
        provider="azure",
        requested_model="test-deployment",
        request_sha256="b" * 64,
    )

    stored = ledger.calls_for("task-a")[0]

    assert stored["request_sha256"] == "b" * 64
    assert not any(
        "prompt" in str(key) and key != "request_sha256" for key in stored
    )


def test_a_request_identifier_is_only_accepted_as_a_digest(ledger):
    with pytest.raises(ValueError):
        ledger.reserve(
            call_id="a" * 64,
            task_id="task-a",
            stage=STAGE_GENERATION,
            retry_kind=RETRY_NONE,
            provider="azure",
            requested_model="test-deployment",
            request_sha256="write the prompt here",
        )


def test_an_export_can_be_checked_against_its_published_digest(ledger, tmp_path):
    _spend(
        ledger,
        "task-a",
        stage=STAGE_GENERATION,
        retry_kind=RETRY_NONE,
        sequence=0,
        usage=_usage(),
    )
    _spend(
        ledger,
        "task-a",
        stage=STAGE_GRADING,
        retry_kind=RETRY_NONE,
        sequence=0,
        usage=_usage(),
    )

    export = tmp_path / "cost_ledger.jsonl"
    digest = ledger.export_jsonl(export)

    assert verify_export(export, digest)
    assert not verify_export(export, "0" * 64)
    assert len(export.read_text(encoding="utf-8").strip().splitlines()) == 2


def test_two_exports_of_one_ledger_are_byte_identical(ledger, tmp_path):
    """A digest beside a result only means something if it is reproducible."""
    for sequence in range(3):
        _spend(
            ledger,
            f"task-{sequence}",
            stage=STAGE_GENERATION,
            retry_kind=RETRY_NONE,
            sequence=sequence,
            usage=_usage(),
        )

    first = ledger.export_jsonl(tmp_path / "one.jsonl")
    second = ledger.export_jsonl(tmp_path / "two.jsonl")

    assert first == second


def test_reopening_the_ledger_finds_everything_still_there(tmp_path, price_table):
    """A crash between rounds must not lose what was already spent."""
    path = tmp_path / "cost.sqlite3"
    with CostReceiptLedger(path, run_id="run-1", price_table=price_table) as first:
        _spend(
            first,
            "task-a",
            stage=STAGE_GENERATION,
            retry_kind=RETRY_NONE,
            sequence=0,
            usage=_usage(),
        )

    with CostReceiptLedger(path, run_id="run-1", price_table=price_table) as second:
        receipt = second.receipt_for("task-a", BUCKET_PROBLEM_SOLVING)

    assert receipt.estimated_cost_usd == Decimal("1.20")


def test_reserving_a_call_twice_does_not_reset_what_it_reported(ledger):
    """A resumed round re-walking its own history must not erase it."""
    call_id = _spend(
        ledger,
        "task-a",
        stage=STAGE_GENERATION,
        retry_kind=RETRY_NONE,
        sequence=0,
        usage=_usage(),
    )
    ledger.reserve(
        call_id=call_id,
        task_id="task-a",
        stage=STAGE_GENERATION,
        retry_kind=RETRY_NONE,
        provider="azure",
        requested_model="test-deployment",
    )

    receipt = ledger.receipt_for("task-a", BUCKET_PROBLEM_SOLVING)

    assert receipt.status == STATUS_COMPLETE
    assert receipt.estimated_cost_usd == Decimal("1.20")


def test_grading_calls_do_not_appear_on_the_solving_receipt(ledger):
    _spend(
        ledger,
        "task-a",
        stage=STAGE_GENERATION,
        retry_kind=RETRY_NONE,
        sequence=0,
        usage=_usage(),
    )
    _spend(
        ledger,
        "task-a",
        stage=STAGE_GRADING,
        retry_kind=RETRY_NONE,
        sequence=0,
        usage=_usage(input_tokens=200_000),
    )

    solving = ledger.receipt_for("task-a", BUCKET_PROBLEM_SOLVING)
    grading = ledger.receipt_for("task-a", BUCKET_GRADING)

    assert solving.model_calls == 1
    assert grading.model_calls == 1
    assert solving.estimated_cost_usd == Decimal("1.20")
    assert grading.estimated_cost_usd == Decimal("2.20")
