"""A receipt has to name the price table that actually priced it.

The fingerprint is not decoration. ``load_receipt_price_table`` says what it is
for in as many words -- "a receipt that records it can be checked against the
exact bytes that priced it" -- and two tests in
``test_receipt_prices_match_the_published_meters.py`` already state the danger:
"the fingerprint has to be the bytes on disk, or it traces to nothing", and
"otherwise a receipt could name a table whose numbers had since moved".

The ledger was naming the table *this process* opened it with. Rows settled by
an earlier process, under an earlier price file, got stamped with today's
fingerprint on the way out, and ``summarise_receipts`` then took the first
non-null fingerprint it happened to see and put that on the experiment. So a
$30 charge computed at $10/$20 per million was published as having been priced
by a table that charges $100/$200 -- a claim the named bytes disprove, and one
that flipped depending on which task the loop reached first.

Nothing here is asserted about money: each amount was correct under the table
in force when it settled, and stays exactly what it was. The only thing that
changes is whether the receipt names a table it cannot support.

Every number below comes from a real ``CostReceiptLedger`` priced by a real
``load_receipt_price_table``, so the arithmetic under test is the producer's.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.cost_projection import project_cost_receipt, summarize_cost_receipts
from core.cost_receipts import (
    BUCKET_PROBLEM_SOLVING,
    REASON_PRICE_MISSING,
    STATE_ABANDONED,
    STATE_RESERVED,
    STATE_SETTLED,
    STATUS_COMPLETE,
    CallUsage,
    CostReceiptLedger,
    build_receipt,
    load_receipt_price_table,
    make_call_id,
    summarise_receipts,
)


def _price_document(input_rate: str, output_rate: str) -> dict:
    return {
        "cost_receipt_schema_version": "cost-receipt-price-table-v1",
        "providers": {
            "azure:m": {
                "input_usd_per_million": input_rate,
                "cached_input_usd_per_million": input_rate,
                "output_usd_per_million": output_rate,
                "reasoning_billed_as": "output",
                "source": "fixture",
                "last_reviewed": "2026-08-31",
                "currency": "USD",
                "unit": "per 1,000,000 tokens",
            }
        },
        "runtime": {},
    }


def _table(tmp_path, name, input_rate, output_rate):
    path = tmp_path / name
    path.write_text(json.dumps(_price_document(input_rate, output_rate)), "utf-8")
    return load_receipt_price_table(path)


@pytest.fixture
def january(tmp_path):
    """The price file as it stood when the first round ran."""
    return _table(tmp_path, "prices_january.json", "10", "20")


@pytest.fixture
def february(tmp_path):
    """The same file after a rate review. Ten times the money, new digest."""
    return _table(tmp_path, "prices_february.json", "100", "200")


def _charge(ledger, task_id, *, sequence=0):
    """One settled call through the ledger's own reserve/settle pair."""
    call_id = make_call_id(
        run_id=ledger.run_id,
        task_id=task_id,
        stage="generation",
        retry_kind="none",
        attempt_index=0,
        sequence=sequence,
    )
    ledger.reserve(
        call_id=call_id,
        task_id=task_id,
        stage="generation",
        retry_kind="none",
        provider="azure",
        requested_model="m",
    )
    return ledger.settle(
        call_id, usage=CallUsage(input_tokens=1_000_000, output_tokens=1_000_000)
    )


def _resumed_run(tmp_path, january, february):
    """Round one under January's prices; the file is revised; round two resumes.

    One ledger file, two processes, two price tables -- which is a resume, or a
    shard started after a rate review, not a contrivance.
    """
    path = tmp_path / "cost.sqlite3"
    with CostReceiptLedger(path, run_id="run-1", price_table=january) as first:
        _charge(first, "t-january")
    with CostReceiptLedger(path, run_id="run-1", price_table=february) as second:
        _charge(second, "t-february")
        receipts = (
            second.receipt_for("t-january", BUCKET_PROBLEM_SOLVING),
            second.receipt_for("t-february", BUCKET_PROBLEM_SOLVING),
        )
    return receipts


# ── Through the ledger, on a resumed run ──────────────────────────────────


def test_a_row_keeps_the_table_it_was_settled_under(tmp_path, january, february):
    older, _ = _resumed_run(tmp_path, january, february)
    assert older.price_table_sha256 == january.sha256
    assert older.price_table_sha256 != february.sha256


def test_the_new_rows_still_name_the_table_that_priced_them(
    tmp_path, january, february
):
    """The control. Today's table is right for the calls it did price."""
    _, newer = _resumed_run(tmp_path, january, february)
    assert newer.price_table_sha256 == february.sha256


def test_the_fingerprint_and_the_amount_agree_with_each_other(
    tmp_path, january, february
):
    """The whole point: fetch the named bytes, re-price, get the same money.

    A million input and a million output at $10/$20 is $30, and at $100/$200 is
    $300. Before, the older receipt paired $30 with February's digest, and any
    reader who checked found a tenfold gap with no way to tell whether the
    money or the provenance was wrong.
    """
    older, newer = _resumed_run(tmp_path, january, february)
    assert (older.known_cost_usd, older.price_table_sha256) == (30, january.sha256)
    assert (newer.known_cost_usd, newer.price_table_sha256) == (300, february.sha256)


def test_the_money_does_not_move(tmp_path, january, february):
    """Negative control. This is a provenance fix, not a repricing."""
    older, newer = _resumed_run(tmp_path, january, february)
    assert older.known_cost_usd == 30
    assert newer.known_cost_usd == 300
    assert older.status == newer.status == STATUS_COMPLETE
    assert older.missing_reasons == newer.missing_reasons == ()


def test_an_experiment_over_two_tables_names_neither(tmp_path, january, february):
    older, newer = _resumed_run(tmp_path, january, february)
    rolled = summarise_receipts([older, newer])
    assert rolled.price_table_sha256 is None
    # The total is still the total, and still says it is complete.
    assert rolled.known_cost_usd == 330
    assert rolled.status == STATUS_COMPLETE


def test_the_answer_no_longer_depends_on_which_task_came_first(
    tmp_path, january, february
):
    """``sha = sha or ...`` published whichever task the loop reached first.

    Two orderings of the same run gave two different provenance claims, both
    stated with the same confidence.
    """
    older, newer = _resumed_run(tmp_path, january, february)
    forwards = summarise_receipts([older, newer]).price_table_sha256
    backwards = summarise_receipts([newer, older]).price_table_sha256
    assert forwards == backwards is None


# ── A run that never changed tables is untouched ──────────────────────────


def test_an_ordinary_single_table_run_names_that_table(tmp_path, january):
    """The published-experiment guarantee, end to end through the ledger."""
    path = tmp_path / "cost.sqlite3"
    with CostReceiptLedger(path, run_id="run-1", price_table=january) as ledger:
        for index, task_id in enumerate(("t-a", "t-b", "t-c")):
            _charge(ledger, task_id, sequence=index)
        receipts = [
            ledger.receipt_for(task_id, BUCKET_PROBLEM_SOLVING)
            for task_id in ("t-a", "t-b", "t-c")
        ]
    assert [r.price_table_sha256 for r in receipts] == [january.sha256] * 3
    rolled = summarise_receipts(receipts)
    assert rolled.price_table_sha256 == january.sha256
    assert rolled.known_cost_usd == 90
    assert rolled.status == STATUS_COMPLETE


def test_a_task_with_no_calls_still_reports_the_open_table(tmp_path, january):
    """Nothing was priced, so there is no row to ask; the ledger's own is all
    there is, and a run that cost nothing by rule keeps saying which prices it
    was measured against."""
    path = tmp_path / "cost.sqlite3"
    with CostReceiptLedger(path, run_id="run-1", price_table=january) as ledger:
        free = ledger.receipt_for(
            "t-none", BUCKET_PROBLEM_SOLVING, when_empty=STATUS_COMPLETE
        )
    assert free.price_table_sha256 == january.sha256
    assert free.known_cost_usd == 0


def test_a_ledger_with_no_price_list_names_no_table(tmp_path):
    path = tmp_path / "cost.sqlite3"
    with CostReceiptLedger(path, run_id="run-1", price_table=None) as ledger:
        _charge(ledger, "t-a")
        receipt = ledger.receipt_for("t-a", BUCKET_PROBLEM_SOLVING)
    assert receipt.price_table_sha256 is None
    assert REASON_PRICE_MISSING in receipt.missing_reasons


# ── build_receipt, on rows the ledger is not the only source of ───────────


def _row(sha, *, state=STATE_SETTLED, cost="1.00"):
    row = {
        "state": state,
        "stage": "generation",
        "retry_kind": "none",
        "model_cost_usd": cost,
        "missing_reasons": "[]",
        "input_tokens": 10,
        "output_tokens": 10,
    }
    if sha is not None:
        row["price_table_sha256"] = sha
    return row


def test_rows_that_name_nothing_leave_the_callers_table_standing():
    """Ledgers written before the column was populated say nothing at all.

    There is no disagreement to report, and blanking the fingerprint would
    lose provenance every older run still has. ``build_receipt`` is also called
    directly with rows that never carried the column, and those callers keep
    their answer.
    """
    receipt = build_receipt([_row(None), _row(None)], price_table_sha256="a" * 64)
    assert receipt.price_table_sha256 == "a" * 64


def test_a_row_that_names_a_table_outranks_the_caller():
    receipt = build_receipt([_row("b" * 64)], price_table_sha256="a" * 64)
    assert receipt.price_table_sha256 == "b" * 64


def test_one_named_table_beside_silence_is_not_a_disagreement():
    """A run half of whose rows predate the column still has one known table."""
    receipt = build_receipt(
        [_row("b" * 64), _row(None)], price_table_sha256="a" * 64
    )
    assert receipt.price_table_sha256 == "b" * 64


def test_two_rows_naming_different_tables_name_neither():
    receipt = build_receipt(
        [_row("b" * 64), _row("c" * 64)], price_table_sha256="a" * 64
    )
    assert receipt.price_table_sha256 is None
    # The money and the status are the rows', and are not touched by the doubt.
    assert receipt.known_cost_usd == 2
    assert receipt.status == STATUS_COMPLETE


def test_a_call_that_never_went_out_cannot_change_the_provenance():
    """An abandoned call was never sent, so it was never priced by anything.

    It contributes no money, and it must not be able to turn a single-table
    receipt into a disagreement either.
    """
    receipt = build_receipt(
        [_row("b" * 64), _row("c" * 64, state=STATE_ABANDONED)],
        price_table_sha256="a" * 64,
    )
    assert receipt.price_table_sha256 == "b" * 64
    assert receipt.known_cost_usd == 1


def test_a_reserved_call_names_no_table_and_disturbs_none():
    receipt = build_receipt(
        [_row("b" * 64), _row(None, state=STATE_RESERVED, cost=None)],
        price_table_sha256="a" * 64,
    )
    assert receipt.price_table_sha256 == "b" * 64


# ── summarise_receipts, over receipts from anywhere ───────────────────────


def test_a_summary_over_one_table_keeps_it():
    receipts = [
        build_receipt([_row("b" * 64)]),
        build_receipt([_row("b" * 64)]),
    ]
    assert summarise_receipts(receipts).price_table_sha256 == "b" * 64


def test_a_summary_ignores_tasks_that_named_no_table_at_all():
    """One unpriced task does not erase the provenance of the priced ones."""
    receipts = [
        build_receipt([_row("b" * 64)]),
        build_receipt([_row(None, cost=None)]),
    ]
    assert summarise_receipts(receipts).price_table_sha256 == "b" * 64


# ── The projection layer already said this; now both layers agree ─────────


def _projected(receipt):
    return {
        "task_id": "t",
        "status": "success",
        "deliverable_files": ["a.txt"],
        "problem_solving_cost": project_cost_receipt(receipt.as_dict()),
    }


def test_the_run_summary_and_the_receipt_now_give_the_same_answer(
    tmp_path, january, february
):
    """``summarize_cost_receipts`` has always refused to pick between tables.

    It collects the distinct fingerprints and reports one only when there is
    one, so the fix is not a new rule -- it is the ledger being held to the rule
    the run summary already followed. Left alone, the two disagreed about the
    same run.
    """
    older, newer = _resumed_run(tmp_path, january, february)
    summary = summarize_cost_receipts(
        [_projected(older), _projected(newer)], "problem_solving_cost"
    )
    assert summary["price_table_sha256"] is None
    assert summarise_receipts([older, newer]).price_table_sha256 is None


def test_a_single_table_run_agrees_across_both_layers(tmp_path, january):
    path = tmp_path / "cost.sqlite3"
    with CostReceiptLedger(path, run_id="run-1", price_table=january) as ledger:
        _charge(ledger, "t-a")
        receipt = ledger.receipt_for("t-a", BUCKET_PROBLEM_SOLVING)
    summary = summarize_cost_receipts([_projected(receipt)], "problem_solving_cost")
    assert summary["price_table_sha256"] == january.sha256
    assert summarise_receipts([receipt]).price_table_sha256 == january.sha256
