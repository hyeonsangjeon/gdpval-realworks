"""The refusals: where a number cannot be established, none is produced.

Every test here is about the difference between ``0`` and *unknown*. A run
whose provider returned no usage block, a model nobody has published a price
for, a container shared by fifty tasks — each of these is a place where a
plausible number could be produced and where producing one would be a lie
dressed as a measurement.

The one real ``$0`` also lives here: a marking path that reaches a verdict by
rule and never calls a model at all.
"""

import json
from decimal import Decimal

import pytest

from core.cost_receipts import (
    BUCKET_GRADING,
    BUCKET_PROBLEM_SOLVING,
    REASON_LEDGER_ABSENT,
    REASON_PRICE_MISSING,
    REASON_RUNTIME_UNATTRIBUTABLE,
    REASON_RUNTIME_UNPRICED,
    REASON_USAGE_ABSENT,
    REASON_USAGE_PARTIAL,
    RETRY_NONE,
    STAGE_GENERATION,
    STAGE_GRADING,
    STATUS_COMPLETE,
    STATUS_NOT_RUN,
    STATUS_PARTIAL,
    STATUS_UNAVAILABLE,
    CallUsage,
    CostReceipt,
    CostReceiptLedger,
    load_receipt_price_table,
    make_call_id,
    price_call,
    summarise_receipts,
)

PRICE_TABLE = {
    "cost_receipt_schema_version": "cost-receipt-price-table-v1",
    "providers": {
        "azure:cheap-cache": {
            "input_usd_per_million": "10",
            "cached_input_usd_per_million": "1",
            "output_usd_per_million": "20",
            "reasoning_billed_as": "output",
            "source": "fixture",
            "last_reviewed": "2026-08-28",
            "currency": "USD",
            "unit": "per 1,000,000 tokens",
        },
        "azure:thinks-on-the-side": {
            "input_usd_per_million": "10",
            "cached_input_usd_per_million": "10",
            "output_usd_per_million": "20",
            "reasoning_billed_as": "separate",
            "reasoning_usd_per_million": "40",
            "source": "fixture",
            "last_reviewed": "2026-08-28",
            "currency": "USD",
            "unit": "per 1,000,000 tokens",
        },
        "azure:unclear-thinker": {
            "input_usd_per_million": "10",
            "cached_input_usd_per_million": "10",
            "output_usd_per_million": "20",
            "reasoning_billed_as": "unknown",
            "source": "fixture",
            "last_reviewed": "2026-08-28",
            "currency": "USD",
            "unit": "per 1,000,000 tokens",
        },
    },
    "runtime": {
        "own-container": {
            "usd_per_hour": "3.60",
            "attribution": "per_task",
            "source": "fixture",
            "last_reviewed": "2026-08-28",
            "currency": "USD",
        },
        "shared-pool": {
            "usd_per_hour": "7.20",
            "attribution": "shared",
            "source": "fixture",
            "last_reviewed": "2026-08-28",
            "currency": "USD",
        },
    },
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


def _call(ledger, task_id, *, stage=STAGE_GENERATION, sequence=0):
    call_id = make_call_id(
        run_id=ledger.run_id,
        task_id=task_id,
        stage=stage,
        retry_kind=RETRY_NONE,
        attempt_index=0,
        sequence=sequence,
    )
    ledger.reserve(
        call_id=call_id,
        task_id=task_id,
        stage=stage,
        retry_kind=RETRY_NONE,
        provider="azure",
        requested_model="a-deployment-name",
    )
    return call_id


# ── missing usage ────────────────────────────────────────────────────────


def test_a_reply_with_no_usage_block_is_not_treated_as_free(ledger):
    call_id = _call(ledger, "task-a")
    ledger.settle(call_id, usage=CallUsage(), resolved_model="cheap-cache")

    receipt = ledger.receipt_for("task-a", BUCKET_PROBLEM_SOLVING)

    assert receipt.status == STATUS_PARTIAL
    assert receipt.estimated_cost_usd is None
    assert REASON_USAGE_ABSENT in receipt.missing_reasons
    assert receipt.known_cost_usd == Decimal(0)
    assert receipt.model_calls == 1


def test_a_reply_missing_only_its_output_count_is_still_incomplete(ledger):
    call_id = _call(ledger, "task-a")
    ledger.settle(
        call_id,
        usage=CallUsage(input_tokens=1000, output_tokens=None),
        resolved_model="cheap-cache",
    )

    receipt = ledger.receipt_for("task-a", BUCKET_PROBLEM_SOLVING)

    assert receipt.status == STATUS_PARTIAL
    assert REASON_USAGE_PARTIAL in receipt.missing_reasons


# ── missing price ────────────────────────────────────────────────────────


def test_a_model_with_no_published_price_is_not_priced_from_a_similar_one(ledger):
    """``cheap-cache-v2`` is not ``cheap-cache``, and is not billed as it."""
    call_id = _call(ledger, "task-a")
    ledger.settle(
        call_id,
        usage=CallUsage(input_tokens=100_000, output_tokens=10_000),
        resolved_model="cheap-cache-v2",
    )

    receipt = ledger.receipt_for("task-a", BUCKET_PROBLEM_SOLVING)

    assert receipt.status == STATUS_PARTIAL
    assert receipt.missing_reasons == (REASON_PRICE_MISSING,)
    assert receipt.known_cost_usd == Decimal(0)
    # The usage is still reported. Only the money is withheld.
    assert receipt.usage["input_tokens"] == 100_000


def test_the_model_that_answered_is_priced_not_the_one_that_was_asked_for(ledger):
    """A deployment alias is a routing detail; the bill names the model."""
    call_id = _call(ledger, "task-a")
    ledger.settle(
        call_id,
        usage=CallUsage(input_tokens=100_000, output_tokens=10_000, cached_input_tokens=0),
        resolved_model="cheap-cache",
    )

    receipt = ledger.receipt_for("task-a", BUCKET_PROBLEM_SOLVING)

    assert receipt.status == STATUS_COMPLETE
    assert ledger.calls_for("task-a")[0]["resolved_model"] == "cheap-cache"
    assert ledger.calls_for("task-a")[0]["requested_model"] == "a-deployment-name"


def test_a_ledger_with_no_price_list_at_all_prices_nothing(tmp_path):
    with CostReceiptLedger(
        tmp_path / "cost.sqlite3", run_id="run-1", price_table=None
    ) as ledger:
        call_id = _call(ledger, "task-a")
        ledger.settle(
            call_id,
            usage=CallUsage(input_tokens=100, output_tokens=10),
            resolved_model="cheap-cache",
        )
        receipt = ledger.receipt_for("task-a", BUCKET_PROBLEM_SOLVING)

    assert receipt.status == STATUS_PARTIAL
    assert REASON_PRICE_MISSING in receipt.missing_reasons


# ── double billing ───────────────────────────────────────────────────────


def test_cached_input_is_charged_once_not_twice(price_table):
    """The provider counts cache hits inside the input it reports."""
    price = price_table.lookup("azure", "cheap-cache")
    priced = price_call(
        price,
        CallUsage(
            input_tokens=1_000_000,
            cached_input_tokens=900_000,
            output_tokens=0,
        ),
    )

    # 100k fresh at $10/M plus 900k cached at $1/M.
    assert priced.cost_usd == Decimal("1.90")
    # Not the $10.90 that charging the full input and the cache again gives.
    assert priced.cost_usd != Decimal("10.90")


def test_more_cache_than_input_is_a_contradiction_not_a_bargain(price_table):
    price = price_table.lookup("azure", "cheap-cache")
    priced = price_call(
        price,
        CallUsage(input_tokens=1000, cached_input_tokens=5000, output_tokens=10),
    )

    assert priced.cost_usd is None
    assert REASON_USAGE_PARTIAL in priced.missing_reasons


def test_reasoning_inside_the_output_count_is_not_charged_again(price_table):
    """These tokens are already inside ``output_tokens``."""
    price = price_table.lookup("azure", "cheap-cache")
    priced = price_call(
        price,
        CallUsage(
            input_tokens=0,
            cached_input_tokens=0,
            output_tokens=100_000,
            reasoning_tokens=80_000,
        ),
    )

    assert priced.cost_usd == Decimal("2.00")


def test_reasoning_billed_separately_is_charged_at_its_own_rate(price_table):
    price = price_table.lookup("azure", "thinks-on-the-side")
    priced = price_call(
        price,
        CallUsage(
            input_tokens=0,
            cached_input_tokens=0,
            output_tokens=100_000,
            reasoning_tokens=100_000,
        ),
    )

    # $2 of output plus $4 of reasoning.
    assert priced.cost_usd == Decimal("6.00")


def test_reasoning_nobody_has_pinned_down_leaves_the_call_unpriced(price_table):
    price = price_table.lookup("azure", "unclear-thinker")
    priced = price_call(
        price,
        CallUsage(
            input_tokens=1000,
            cached_input_tokens=0,
            output_tokens=1000,
            reasoning_tokens=500,
        ),
    )

    assert priced.cost_usd is None
    assert REASON_USAGE_PARTIAL in priced.missing_reasons


def test_a_model_that_did_no_reasoning_is_unaffected_by_the_unknown_rule(price_table):
    """Only reasoning that actually happened can be mis-billed."""
    price = price_table.lookup("azure", "unclear-thinker")
    priced = price_call(
        price,
        CallUsage(
            input_tokens=1_000_000,
            cached_input_tokens=0,
            output_tokens=0,
            reasoning_tokens=0,
        ),
    )

    assert priced.cost_usd == Decimal("10")


# ── runtime fees ─────────────────────────────────────────────────────────


def test_a_container_started_for_one_task_is_billed_to_that_task(ledger):
    call_id = _call(ledger, "task-a")
    ledger.settle(
        call_id,
        usage=CallUsage(input_tokens=0, cached_input_tokens=0, output_tokens=0, reasoning_tokens=0),
        resolved_model="cheap-cache",
    )
    ledger.record_runtime_cost(
        entry_id="task-a:own",
        task_id="task-a",
        bucket=BUCKET_PROBLEM_SOLVING,
        runtime_kind="own-container",
        seconds=600,
    )

    receipt = ledger.receipt_for("task-a", BUCKET_PROBLEM_SOLVING)

    assert receipt.status == STATUS_COMPLETE
    # Ten minutes of a $3.60/hour container.
    assert receipt.runtime_cost_usd == Decimal("0.60")
    assert receipt.known_cost_usd == receipt.model_cost_usd + receipt.runtime_cost_usd


def test_a_shared_pool_is_not_divided_between_the_tasks_that_used_it(ledger):
    """An invented split reads exactly like a measurement, so none is made."""
    ledger.record_runtime_cost(
        entry_id="task-a:pool",
        task_id="task-a",
        bucket=BUCKET_PROBLEM_SOLVING,
        runtime_kind="shared-pool",
        seconds=3600,
    )

    receipt = ledger.receipt_for("task-a", BUCKET_PROBLEM_SOLVING)

    assert receipt.status == STATUS_PARTIAL
    assert receipt.runtime_cost_usd == Decimal(0)
    assert REASON_RUNTIME_UNATTRIBUTABLE in receipt.missing_reasons
    assert receipt.estimated_cost_usd is None


def test_a_runtime_nobody_has_priced_is_recorded_as_unpriced(ledger):
    ledger.record_runtime_cost(
        entry_id="task-a:mystery",
        task_id="task-a",
        bucket=BUCKET_PROBLEM_SOLVING,
        runtime_kind="a-runtime-with-no-rate",
        seconds=3600,
    )

    receipt = ledger.receipt_for("task-a", BUCKET_PROBLEM_SOLVING)

    assert receipt.status == STATUS_PARTIAL
    assert REASON_RUNTIME_UNPRICED in receipt.missing_reasons


# ── nothing happened ─────────────────────────────────────────────────────


def test_marking_that_never_ran_is_not_marking_that_was_free(ledger):
    receipt = ledger.receipt_for("task-a", BUCKET_GRADING)

    assert receipt.status == STATUS_NOT_RUN
    assert receipt.estimated_cost_usd is None
    assert receipt.as_dict()["estimated_cost_usd"] is None


def test_marking_by_rule_alone_really_did_cost_nothing(ledger):
    """The single honest zero: a verdict reached without asking a model."""
    receipt = ledger.receipt_for(
        "task-a", BUCKET_GRADING, when_empty=STATUS_COMPLETE
    )

    assert receipt.status == STATUS_COMPLETE
    assert receipt.estimated_cost_usd == Decimal(0)
    assert receipt.model_calls == 0


def test_a_run_that_kept_no_record_says_so_rather_than_reporting_zero(ledger):
    receipt = ledger.receipt_for(
        "task-a", BUCKET_PROBLEM_SOLVING, when_empty=STATUS_UNAVAILABLE
    )

    assert receipt.status == STATUS_UNAVAILABLE
    assert receipt.missing_reasons == (REASON_LEDGER_ABSENT,)
    assert receipt.estimated_cost_usd is None


def test_the_three_kinds_of_silence_do_not_look_alike(ledger):
    """Never ran, ran free, ran unrecorded — three different sentences."""
    statuses = {
        ledger.receipt_for("t", BUCKET_GRADING).status,
        ledger.receipt_for("t", BUCKET_GRADING, when_empty=STATUS_COMPLETE).status,
        ledger.receipt_for(
            "t", BUCKET_GRADING, when_empty=STATUS_UNAVAILABLE
        ).status,
    }

    assert statuses == {STATUS_NOT_RUN, STATUS_COMPLETE, STATUS_UNAVAILABLE}


def test_a_summary_over_nothing_knowable_stays_unknowable():
    """Rolling up silence must not turn it into a floor of ``$0``.

    ``partial`` carries a real claim — part of this is known, and
    ``known_cost_usd`` is a genuine lower bound. A run where no task could be
    priced has no lower bound, and publishing one of zero is how a summary comes
    to be read as "so far it has cost nothing".
    """
    summary = summarise_receipts(
        [CostReceipt.unavailable(), CostReceipt.unavailable()]
    )

    assert summary.status == STATUS_UNAVAILABLE
    assert summary.estimated_cost_usd is None
    assert summary.missing_reasons == (REASON_LEDGER_ABSENT,)


def test_one_priced_task_among_unpriceable_ones_gives_a_real_floor(ledger):
    """The moment any part is known, the summary has something to bound."""
    priced = CostReceipt(
        status=STATUS_COMPLETE,
        known_cost_usd=Decimal("1.50"),
        model_cost_usd=Decimal("1.50"),
        model_calls=1,
    )

    summary = summarise_receipts([priced, CostReceipt.unavailable()])

    assert summary.status == STATUS_PARTIAL
    assert summary.estimated_cost_usd is None
    assert summary.known_cost_usd == Decimal("1.50")


def test_an_execution_path_with_no_metering_is_reported_as_unsupported():
    """No confirmed model call means no invented cost."""
    receipt = CostReceipt.unavailable(reasons=("stage_unsupported",))

    assert receipt.status == STATUS_UNAVAILABLE
    assert receipt.as_dict()["missing_reasons"] == ["stage_unsupported"]
    assert receipt.as_dict()["estimated_cost_usd"] is None


# ── the contract's own arithmetic ────────────────────────────────────────


def test_a_partial_receipt_never_publishes_a_total(ledger):
    _call(ledger, "task-a")  # reserved and never settled
    settled = _call(ledger, "task-a", sequence=1)
    ledger.settle(
        settled,
        usage=CallUsage(
            input_tokens=100_000, cached_input_tokens=0, output_tokens=0, reasoning_tokens=0
        ),
        resolved_model="cheap-cache",
    )

    payload = ledger.receipt_for("task-a", BUCKET_PROBLEM_SOLVING).as_dict()

    assert payload["status"] == STATUS_PARTIAL
    assert payload["estimated_cost_usd"] is None
    assert payload["known_cost_usd"] == 1.0
    assert payload["schema_version"] == "cost-receipt-v1"


def test_the_parts_of_a_receipt_add_up_to_its_known_cost(ledger):
    for sequence, stage in enumerate((STAGE_GRADING, STAGE_GRADING)):
        call_id = _call(ledger, "task-a", stage=stage, sequence=sequence)
        ledger.settle(
            call_id,
            usage=CallUsage(
                input_tokens=100_000,
                cached_input_tokens=0,
                output_tokens=10_000,
                reasoning_tokens=0,
            ),
            resolved_model="cheap-cache",
        )
    ledger.record_runtime_cost(
        entry_id="task-a:own",
        task_id="task-a",
        bucket=BUCKET_GRADING,
        runtime_kind="own-container",
        seconds=60,
    )

    receipt = ledger.receipt_for("task-a", BUCKET_GRADING)

    assert receipt.model_cost_usd + receipt.runtime_cost_usd == receipt.known_cost_usd
    assert sum(
        (component.known_cost_usd for component in receipt.components),
        Decimal(0),
    ) == receipt.model_cost_usd
