"""Not knowing how many calls a turn made is not the same as not knowing its cost.

Every dollar column in the ledger run 34571840967 uploaded is empty — all 88 of
them — and not one is empty for want of a price. The table was loaded, the run
recorded its fingerprint, and `price_call` computed a figure for each of the 75
turns that reported usage. `settle` then threw every one of them away, because
it discarded the cost whenever *any* reason was attached:

    cost = None if reasons else priced.cost_usd

and the Codex path attaches `call_reachability_unknown` to every turn
unconditionally: Codex will not say how many model requests it made inside one
turn, so the count is never known.

Those are two different unknowns and they were being treated as one. Token
billing is additive — a turn's reported totals price to the same amount however
many requests produced them — so the request count can stay unknown while the
amount is perfectly determined. The reason is still true and still travels; it
just never described the money.

The cost of conflating them was not a rounding error. A completed run published
`known_cost_usd: 0` across the board, and every surface downstream had to be
taught not to read that as free: the dashboard falls back to `미확정`, the
report prints `no record`, and the run record carries a section explaining why
`0.0` is not zero. The receipt was already built for the honest answer — a
partial receipt's `known_cost_usd` is documented as *"the sum of what was
confirmed ... a floor [that] must never be displayed as a total"* — and the
floor was simply always empty.

So this file pins the narrowing, in both directions:

  * a turn whose usage was reported in full now settles with its real figure,
    while `call_reachability_unknown` stays on the row and the receipt built
    over it stays `partial` with no `estimated_cost_usd`. The number that
    appears is a floor, labelled as one;
  * a reason that genuinely concerns the amount — no usage, no rate, partial
    usage, a refusal with nothing to price — still deletes it, alone or
    alongside the reachability doubt. If any of those started producing a
    figure, the fix would have reached past the thing it was for.

Nothing here contacts a provider.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from core.cost_receipts import (
    BUCKET_PROBLEM_SOLVING,
    MISSING_REASONS,
    REASON_CALL_REACHABILITY_UNKNOWN,
    REASON_CALL_REFUSED_UNPRICED,
    REASON_PRICE_MISSING,
    REASON_USAGE_ABSENT,
    REASON_USAGE_PARTIAL,
    REASONS_LEAVING_THE_AMOUNT_DETERMINED,
    RETRY_NONE,
    STAGE_GENERATION,
    STATUS_PARTIAL,
    CallUsage,
    CostReceiptLedger,
    load_receipt_price_table,
    price_call,
)

#: The table the pipeline actually ships and prices runs with.
SHIPPED_PRICE_TABLE = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "execution_envelope"
    / "model_price_table.json"
)


def _usage_of(row: dict) -> CallUsage:
    """A recorded ledger row, back in the shape `price_call` takes."""
    return CallUsage(
        input_tokens=row["input_tokens"],
        cached_input_tokens=row["cached_input_tokens"],
        output_tokens=row["output_tokens"],
        reasoning_tokens=row["reasoning_tokens"],
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

# Reported inclusive of cache, the way a provider reports it: 60k at the full
# rate, 40k at the cache rate, 10k out with the reasoning already inside it.
FULL_USAGE = CallUsage(
    input_tokens=100_000,
    cached_input_tokens=40_000,
    output_tokens=10_000,
    reasoning_tokens=3_000,
)
EXPECTED = Decimal("0.84")  # 60k*$10/M + 40k*$1/M + 10k*$20/M


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


def _turn(ledger, *, task_id="task-a", usage=FULL_USAGE, reasons=()):
    """Settle one turn the way the Codex path does, and hand back its row."""
    call_id = ledger.reserve(
        call_id=f"{task_id}-1",
        task_id=task_id,
        stage=STAGE_GENERATION,
        retry_kind=RETRY_NONE,
        provider="azure",
        requested_model="test-model",
    )
    priced = ledger.settle(call_id, usage=usage, extra_reasons=reasons)
    return priced, ledger.calls_for(task_id)[-1]


# ── the narrowing ────────────────────────────────────────────────────────


def test_a_turn_that_reported_its_tokens_now_records_what_they_priced_to(ledger):
    """The defect, stated as the value that used to be thrown away."""
    priced, row = _turn(ledger, reasons=[REASON_CALL_REACHABILITY_UNKNOWN])

    assert priced.cost_usd == EXPECTED, (
        "a turn with complete usage settled without a figure. Its tokens were "
        "reported and its rate was loaded; nothing about the amount was in "
        "doubt."
    )
    assert Decimal(str(row["model_cost_usd"])) == EXPECTED
    assert row["input_tokens"] == 100_000


def test_the_doubt_that_is_real_still_travels_with_the_row(ledger):
    """Pricing the turn must not amount to claiming the call count is known."""
    priced, row = _turn(ledger, reasons=[REASON_CALL_REACHABILITY_UNKNOWN])

    assert REASON_CALL_REACHABILITY_UNKNOWN in priced.missing_reasons
    assert REASON_CALL_REACHABILITY_UNKNOWN in row["missing_reasons"]


def test_the_receipt_is_still_partial_and_still_refuses_to_call_it_a_total(ledger):
    """A figure appearing must not promote the receipt to a complete one."""
    _turn(ledger, reasons=[REASON_CALL_REACHABILITY_UNKNOWN])
    receipt = ledger.receipt_for("task-a", BUCKET_PROBLEM_SOLVING)

    assert receipt.status == STATUS_PARTIAL
    assert receipt.estimated_cost_usd is None, (
        "the one field that claims to be a total must stay empty while a "
        "reason is outstanding"
    )
    # The floor the receipt was always documented to carry, no longer empty.
    assert receipt.known_cost_usd == EXPECTED
    assert receipt.model_cost_usd == EXPECTED
    assert receipt.missing_reasons == (REASON_CALL_REACHABILITY_UNKNOWN,)


# ── and the other direction ──────────────────────────────────────────────


@pytest.mark.parametrize(
    "reason",
    [REASON_USAGE_PARTIAL, REASON_PRICE_MISSING, REASON_CALL_REFUSED_UNPRICED],
)
def test_a_doubt_about_the_amount_still_deletes_the_amount(ledger, reason):
    """These say the money itself is unknown. A figure here would be invented."""
    priced, row = _turn(ledger, reasons=[reason])

    assert priced.cost_usd is None
    assert row["model_cost_usd"] is None


def test_usage_that_never_arrived_is_still_not_priced(ledger):
    """`price_call` raises the reason itself; the exemption must not reach it."""
    priced, row = _turn(ledger, usage=CallUsage())

    assert REASON_USAGE_ABSENT in priced.missing_reasons
    assert priced.cost_usd is None
    assert row["model_cost_usd"] is None


def test_the_exemption_does_not_survive_a_real_gap_beside_it(ledger):
    """The common case: a Codex turn that also lost part of its usage."""
    priced, row = _turn(
        ledger,
        reasons=[REASON_CALL_REACHABILITY_UNKNOWN, REASON_USAGE_PARTIAL],
    )

    assert priced.cost_usd is None, (
        "one reason concerns the count and one concerns the money; the second "
        "still decides"
    )
    assert row["model_cost_usd"] is None
    assert set(priced.missing_reasons) == {
        REASON_CALL_REACHABILITY_UNKNOWN,
        REASON_USAGE_PARTIAL,
    }


def test_exactly_one_reason_is_exempt_and_it_is_a_known_reason(ledger):
    """A later reason added to this set would silence a real doubt.

    Membership means "this does not concern the amount". Every other reason in
    `MISSING_REASONS` does concern it, so growing this set is how a gap in the
    money starts publishing a number.
    """
    assert REASONS_LEAVING_THE_AMOUNT_DETERMINED == frozenset(
        {REASON_CALL_REACHABILITY_UNKNOWN}
    )
    assert REASONS_LEAVING_THE_AMOUNT_DETERMINED <= set(MISSING_REASONS)


# ── how the figure that now appears has to be read ───────────────────────


REAL_LEDGER = (
    Path(__file__).parent / "fixtures" / "run_record" / "exp034_turn_ledger.json"
)
CONTEXT_TIER_SPLIT = 272_000


def _settled_turns():
    rows = json.loads(REAL_LEDGER.read_text(encoding="utf-8"))["rows"]
    return [row for row in rows if row["state"] == "settled"]


def test_every_turn_this_run_settled_was_one_the_old_code_could_have_priced():
    """The defect measured on a real run rather than on a fixture of my own.

    Fifty-three turns from run 34540053904, verbatim. Every one of them has a
    rate in the shipped table and usage complete enough to charge, so every one
    of them had a figure computed and discarded. None of the ledger's dollar
    columns is empty for want of a price.
    """
    price = load_receipt_price_table(SHIPPED_PRICE_TABLE).lookup("azure", "gpt-5.4")
    turns = _settled_turns()

    unpriceable = [
        row
        for row in turns
        if price_call(price, _usage_of(row)).cost_usd is None
    ]

    assert len(turns) == 53
    assert unpriceable == [], (
        "these turns would still settle empty after the fix, which would mean "
        "the discarded figures were never the whole story"
    )
    assert all(row["missing_reasons"] == [REASON_CALL_REACHABILITY_UNKNOWN] for row in turns)


def test_the_figure_is_a_floor_for_a_second_reason_the_ledger_cannot_settle():
    """The price table's own premise is unverifiable *because* of this unknown.

    The table states a premise beside the 5.4 entry and says where to check it:

        No single request sends more than 272,000 input tokens. Azure prices
        5.4 in two context tiers split at that figure ... It CAN be read off
        the per-call cost ledger, which the inference workflow does publish.
        If a request crosses 272k the correct meters are 5.00 input, 0.50
        cached input, 22.50 output.

    Read off that ledger, twelve of the fifty-three turns report more than
    272,000 input tokens, the largest 819,968 — three times the split.

    That does not refute the premise, and this test does not claim it does. A
    ledger row is one *turn*; the premise is about one *request*; and how many
    requests a turn contains is the exact thing
    `call_reachability_unknown` exists to say nobody knows. A turn of 819,968
    tokens may be a dozen ordinary requests. The ledger cannot confirm the
    premise either, and no artifact this pipeline publishes can.

    What follows is only about how to read the number. Every component of the
    higher tier costs more -- 5.00 against 2.50 in, 0.50 against 0.25 cached,
    22.50 against 15.00 out -- so charging the whole run at the lower tier is
    the least it can have cost under either. The figure the fix now publishes
    is a lower bound twice over: once because unsettled reservations are
    outside it, and once because of this. `known_cost_usd` is documented as a
    floor, so it is the honest field for it; `estimated_cost_usd` stays empty,
    which is what stops it being read as the total it is not.
    """
    turns = _settled_turns()
    over = [row for row in turns if row["input_tokens"] > CONTEXT_TIER_SPLIT]

    assert len(over) == 12
    assert max(row["input_tokens"] for row in turns) == 819_968

    entry = json.loads(SHIPPED_PRICE_TABLE.read_text(encoding="utf-8"))
    premise = entry["providers"]["azure:gpt-5.4"]["premises"][1]
    assert "272,000" in premise and "cannot be read off the receipt" in premise

    # The tier actually charged is the cheaper one, so the total is a floor.
    cheap = load_receipt_price_table(SHIPPED_PRICE_TABLE).lookup("azure", "gpt-5.4")
    assert cheap.input_usd_per_million == Decimal("2.50")
    assert cheap.output_usd_per_million == Decimal("15.00")
