"""The ledger says *when* each call happened, not only what it cost.

Why this file exists
--------------------
Run ``34540053904`` was dispatched to answer one question: of the four things
that could be refusing our calls -- request rate, a token-per-minute
reservation, the deployment's throughput, or the interval between calls --
which one is it. Its artifact ruled out two. It could not touch the other two,
and the reason was not subtle: **every row in the cost ledger recorded how many
tokens a call used, and not one recorded when.**

Separating a token ceiling from a throughput ceiling means asking how many
tokens had settled in the minute *before* a refusal. That is a rolling window,
and a window needs a clock. Thirty tasks' worth of token counts with no times
attached cannot be put on one, however many of them there are.

So these tests fix a clock to the ledger's writes. They are not about cost.
They are about making the next run able to answer a question this one could
only describe.

What the two columns mean
-------------------------
``reserved_at`` is when the request went out. That is the stamp a token
reservation scheme keys off, because the reservation is taken at admission.

``concluded_at`` is when this process stopped waiting -- by a reply, a refusal,
a discovery that the call never left, or by giving up. On the giving-up path it
is emphatically *not* a reply time, and a test below pins that the row stays
open so no reader can mistake it for one.
"""

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from core.cost_receipts import (
    BUCKET_PROBLEM_SOLVING,
    RETRY_NONE,
    STAGE_GENERATION,
    STATE_REFUSED,
    STATE_RESERVED,
    STATE_SETTLED,
    CallUsage,
    CostReceiptLedger,
    LedgerIntegrityError,
    load_receipt_price_table,
    make_call_id,
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
            "last_reviewed": "2026-09-11",
            "currency": "USD",
            "unit": "per 1,000,000 tokens",
        }
    },
    "runtime": {},
}

#: A fixed starting moment. Chosen rather than ``now`` so that a failure names
#: the same instants every time it is read.
START = datetime(2026, 9, 11, 3, 0, 0, tzinfo=timezone.utc)


class Clock:
    """A clock the test drives, one second at a time unless told otherwise."""

    def __init__(self, start=START):
        self.moment = start

    def __call__(self):
        return self.moment

    def advance(self, seconds):
        self.moment = self.moment + timedelta(seconds=seconds)
        return self.moment


@pytest.fixture
def price_table(tmp_path):
    path = tmp_path / "prices.json"
    path.write_text(json.dumps(PRICE_TABLE), encoding="utf-8")
    return load_receipt_price_table(path)


def _open(tmp_path, name, price_table, *, clock=None, run_id="run-1"):
    return CostReceiptLedger(
        tmp_path / name,
        run_id=run_id,
        price_table=price_table,
        **({} if clock is None else {"clock": clock}),
    )


def _usage(input_tokens=100_000, output_tokens=10_000):
    return CallUsage(
        input_tokens=input_tokens,
        cached_input_tokens=0,
        output_tokens=output_tokens,
        reasoning_tokens=0,
    )


def _reserve(ledger, task_id, *, attempt=0, sequence=0):
    call_id = make_call_id(
        run_id=ledger.run_id,
        task_id=task_id,
        stage=STAGE_GENERATION,
        retry_kind=RETRY_NONE,
        attempt_index=attempt,
        sequence=sequence,
    )
    ledger.reserve(
        call_id=call_id,
        task_id=task_id,
        stage=STAGE_GENERATION,
        retry_kind=RETRY_NONE,
        provider="azure",
        requested_model="a-deployment",
    )
    return call_id


def _row(ledger, call_id):
    return ledger._connection.execute(
        "SELECT * FROM cost_calls WHERE call_id = ?", (call_id,)
    ).fetchone()


# ── the two stamps ───────────────────────────────────────────────────────


def test_a_reservation_records_when_the_request_went_out(tmp_path, price_table):
    clock = Clock()
    with _open(tmp_path, "l.sqlite3", price_table, clock=clock) as ledger:
        call_id = _reserve(ledger, "task-a")
        row = _row(ledger, call_id)

    assert row["reserved_at"] == "2026-09-11T03:00:00.000+00:00"
    # Nothing has concluded yet, and an absent conclusion must read as absent
    # rather than as "concluded at the moment it was reserved" -- the second
    # would make every open call look like it returned instantly.
    assert row["concluded_at"] is None


def test_a_settled_call_records_when_the_reply_came_back(tmp_path, price_table):
    clock = Clock()
    with _open(tmp_path, "l.sqlite3", price_table, clock=clock) as ledger:
        call_id = _reserve(ledger, "task-a")
        clock.advance(94)
        ledger.settle(call_id, usage=_usage(), resolved_model="test-model")
        row = _row(ledger, call_id)

    assert row["reserved_at"] == "2026-09-11T03:00:00.000+00:00"
    assert row["concluded_at"] == "2026-09-11T03:01:34.000+00:00"
    assert row["state"] == STATE_SETTLED


def test_a_refusal_records_when_the_refusal_came_back(tmp_path, price_table):
    """The stamp that matters most.

    A refusal is the event the rolling window is drawn backwards from. Without
    its moment there is nothing to draw from.
    """
    clock = Clock()
    with _open(tmp_path, "l.sqlite3", price_table, clock=clock) as ledger:
        call_id = _reserve(ledger, "task-a")
        clock.advance(3)
        ledger.refuse(call_id, status=429)
        row = _row(ledger, call_id)

    assert row["state"] == STATE_REFUSED
    assert row["concluded_at"] == "2026-09-11T03:00:03.000+00:00"


def test_a_call_that_never_left_records_when_we_found_that_out(
    tmp_path, price_table
):
    clock = Clock()
    with _open(tmp_path, "l.sqlite3", price_table, clock=clock) as ledger:
        call_id = _reserve(ledger, "task-a")
        clock.advance(2)
        ledger.abandon(call_id, note="client_not_built")
        row = _row(ledger, call_id)

    assert row["concluded_at"] == "2026-09-11T03:00:02.000+00:00"


def test_giving_up_is_stamped_without_being_called_an_answer(
    tmp_path, price_table
):
    """A timeout gets a moment and keeps its open state.

    The moment bounds the call: whatever happened, it happened before then. The
    state is what stops a reader treating the bound as a reply time -- which
    would turn "we never found out" into a measured latency, and a request that
    may have been billed into one that demonstrably was not.
    """
    clock = Clock()
    with _open(tmp_path, "l.sqlite3", price_table, clock=clock) as ledger:
        call_id = _reserve(ledger, "task-a")
        clock.advance(1800)
        ledger.leave_unresolved(call_id, note="request_timed_out")
        row = _row(ledger, call_id)

    assert row["concluded_at"] == "2026-09-11T03:30:00.000+00:00"
    assert row["state"] == STATE_RESERVED


# ── a stamp is written once ──────────────────────────────────────────────


def test_re_reserving_a_call_does_not_move_the_moment_it_left(
    tmp_path, price_table
):
    """A resumed round re-reserves calls it already recorded.

    Letting the second reservation win would restamp a call that went out hours
    earlier with the resume's clock, and every window drawn around it would be
    drawn in the wrong place.
    """
    clock = Clock()
    with _open(tmp_path, "l.sqlite3", price_table, clock=clock) as ledger:
        call_id = _reserve(ledger, "task-a")
        clock.advance(7200)
        _reserve(ledger, "task-a")
        row = _row(ledger, call_id)

    assert row["reserved_at"] == "2026-09-11T03:00:00.000+00:00"


def test_settling_the_same_call_twice_does_not_move_its_conclusion(
    tmp_path, price_table
):
    clock = Clock()
    with _open(tmp_path, "l.sqlite3", price_table, clock=clock) as ledger:
        call_id = _reserve(ledger, "task-a")
        clock.advance(10)
        ledger.settle(call_id, usage=_usage(), resolved_model="test-model")
        clock.advance(600)
        ledger.settle(call_id, usage=_usage(), resolved_model="test-model")
        row = _row(ledger, call_id)

    assert row["concluded_at"] == "2026-09-11T03:00:10.000+00:00"


def test_refusing_the_same_call_twice_does_not_move_its_conclusion(
    tmp_path, price_table
):
    clock = Clock()
    with _open(tmp_path, "l.sqlite3", price_table, clock=clock) as ledger:
        call_id = _reserve(ledger, "task-a")
        clock.advance(5)
        ledger.refuse(call_id, status=429)
        clock.advance(500)
        ledger.refuse(call_id, status=429)
        row = _row(ledger, call_id)

    assert row["concluded_at"] == "2026-09-11T03:00:05.000+00:00"


def test_a_call_we_gave_up_on_and_later_settled_takes_the_real_moment(
    tmp_path, price_table
):
    """Settling after giving up is the one case where the stamp should move.

    ``leave_unresolved`` wrote a bound; a reply is the thing the bound was
    standing in for. The rule is not "first write wins" but "an answer beats a
    bound", and only the settle path can tell the difference.
    """
    clock = Clock()
    with _open(tmp_path, "l.sqlite3", price_table, clock=clock) as ledger:
        call_id = _reserve(ledger, "task-a")
        clock.advance(1800)
        ledger.leave_unresolved(call_id, note="request_timed_out")
        clock.advance(30)
        ledger.settle(call_id, usage=_usage(), resolved_model="test-model")
        row = _row(ledger, call_id)

    # COALESCE keeps the bound, which is the conservative reading: the ledger
    # never claims a reply arrived later than the moment it stopped waiting.
    assert row["concluded_at"] == "2026-09-11T03:30:00.000+00:00"
    assert row["state"] == STATE_SETTLED


# ── the clock itself ─────────────────────────────────────────────────────


def test_a_clock_with_no_timezone_is_refused_rather_than_assumed_to_be_utc(
    tmp_path, price_table
):
    """The failure this guard exists for is invisible in the output.

    A naive datetime stores as a perfectly well-formed timestamp. If the box
    runs on local time, every stamp is off by the offset, the text gives no
    sign of it, and a one-minute window drawn from a set of them is wrong by
    hours. Refusing at the write is the only place the error is still visible.
    """
    naive = lambda: datetime(2026, 9, 11, 3, 0, 0)  # noqa: E731
    with _open(tmp_path, "l.sqlite3", price_table, clock=naive) as ledger:
        with pytest.raises(LedgerIntegrityError) as caught:
            _reserve(ledger, "task-a")

    assert "timezone" in str(caught.value)


def test_a_clock_in_another_zone_is_stored_as_utc(tmp_path, price_table):
    """Shards may run anywhere. Two rows must be comparable as written."""
    elsewhere = timezone(timedelta(hours=9))
    clock = lambda: datetime(2026, 9, 11, 12, 0, 0, tzinfo=elsewhere)  # noqa: E731
    with _open(tmp_path, "l.sqlite3", price_table, clock=clock) as ledger:
        call_id = _reserve(ledger, "task-a")
        row = _row(ledger, call_id)

    assert row["reserved_at"] == "2026-09-11T03:00:00.000+00:00"


def test_the_default_clock_is_the_wall_clock_in_utc(tmp_path, price_table):
    """No injection in production. The default has to be right on its own."""
    before = datetime.now(timezone.utc)
    with _open(tmp_path, "l.sqlite3", price_table) as ledger:
        call_id = _reserve(ledger, "task-a")
        row = _row(ledger, call_id)
    after = datetime.now(timezone.utc)

    stamped = datetime.fromisoformat(row["reserved_at"])
    assert stamped.tzinfo is not None
    assert before - timedelta(seconds=1) <= stamped <= after + timedelta(seconds=1)


# ── the stamps survive the journey to the artifact ───────────────────────


def test_the_moments_reach_the_export_a_run_uploads(tmp_path, price_table):
    """The analysis reads the exported JSONL months later, not this SQLite file."""
    clock = Clock()
    with _open(tmp_path, "l.sqlite3", price_table, clock=clock) as ledger:
        call_id = _reserve(ledger, "task-a")
        clock.advance(60)
        ledger.settle(call_id, usage=_usage(), resolved_model="test-model")
        export = tmp_path / "ledger.jsonl"
        ledger.export_jsonl(export)

    rows = [json.loads(line) for line in export.read_text().splitlines() if line]
    call = [row for row in rows if row.get("call_id") == call_id][0]
    assert call["reserved_at"] == "2026-09-11T03:00:00.000+00:00"
    assert call["concluded_at"] == "2026-09-11T03:01:00.000+00:00"


def test_a_merged_shard_keeps_the_moments_it_was_written_with(
    tmp_path, price_table
):
    clock = Clock()
    with _open(tmp_path, "shard.sqlite3", price_table, clock=clock) as shard:
        call_id = _reserve(shard, "task-a")
        clock.advance(45)
        shard.settle(call_id, usage=_usage(), resolved_model="test-model")
        export = tmp_path / "shard.jsonl"
        shard.export_jsonl(export)

    later = Clock(START + timedelta(days=1))
    with _open(tmp_path, "merged.sqlite3", price_table, clock=later) as merged:
        merged.import_jsonl(export)
        row = _row(merged, call_id)

    assert row["reserved_at"] == "2026-09-11T03:00:00.000+00:00"
    assert row["concluded_at"] == "2026-09-11T03:00:45.000+00:00"


def test_an_export_from_before_these_columns_does_not_erase_a_local_moment(
    tmp_path, price_table
):
    """An older build's export carries no times. Its blanks must not win.

    The local row was reserved here, so it knows when the request left. An
    arriving export that predates the columns knows how the call ended and
    nothing about when. Taking the whole arriving row would trade a recorded
    fact for the absence of one -- the same trap the identity columns already
    guard against.
    """
    clock = Clock()
    with _open(tmp_path, "local.sqlite3", price_table, clock=clock) as ledger:
        call_id = _reserve(ledger, "task-a")

        old_export = tmp_path / "old.jsonl"
        old_export.write_text(
            json.dumps(
                {
                    "record_type": "call",
                    "call_id": call_id,
                    "run_id": ledger.run_id,
                    "task_id": "task-a",
                    "stage": STAGE_GENERATION,
                    "retry_kind": RETRY_NONE,
                    "provider": "azure",
                    "requested_model": "a-deployment",
                    "resolved_model": "test-model",
                    "state": STATE_SETTLED,
                    "input_tokens": 100_000,
                    "cached_input_tokens": 0,
                    "output_tokens": 10_000,
                    "reasoning_tokens": 0,
                    "missing_reasons": [],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        ledger.import_jsonl(old_export)
        row = _row(ledger, call_id)

    assert row["state"] == STATE_SETTLED
    assert row["reserved_at"] == "2026-09-11T03:00:00.000+00:00"


def test_a_ledger_written_before_these_columns_still_opens(tmp_path, price_table):
    """And its old rows say "not recorded", not a guessed time.

    Resume reopens the previous round's file. A round-2 process that could not
    read a round-1 ledger would be a worse failure than the missing timestamps
    -- and backfilling the old rows with anything at all would be inventing the
    measurement this whole change exists to start taking.
    """
    path = tmp_path / "old.sqlite3"
    connection = sqlite3.connect(str(path))
    connection.executescript(
        """
        CREATE TABLE cost_calls (
            call_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, task_id TEXT NOT NULL,
            stage TEXT NOT NULL, retry_kind TEXT NOT NULL, provider TEXT NOT NULL,
            requested_model TEXT NOT NULL, state TEXT NOT NULL,
            missing_reasons TEXT NOT NULL DEFAULT '[]'
        );
        """
    )
    connection.execute(
        "INSERT INTO cost_calls (call_id, run_id, task_id, stage, retry_kind, "
        "provider, requested_model, state) VALUES "
        "('old-call', 'run-1', 'task-a', ?, ?, 'azure', 'a-deployment', ?)",
        (STAGE_GENERATION, RETRY_NONE, STATE_SETTLED),
    )
    connection.commit()
    connection.close()

    clock = Clock()
    with CostReceiptLedger(
        path, run_id="run-1", price_table=price_table, clock=clock
    ) as ledger:
        old = _row(ledger, "old-call")
        fresh = _reserve(ledger, "task-b")
        fresh_row = _row(ledger, fresh)

    assert old["reserved_at"] is None
    assert old["concluded_at"] is None
    assert fresh_row["reserved_at"] == "2026-09-11T03:00:00.000+00:00"


# ── what the stamps were added for ───────────────────────────────────────


def test_the_tokens_settled_before_a_refusal_can_now_be_counted(
    tmp_path, price_table
):
    """The question run 34540053904 could not answer, answered on a fixture.

    Four calls settle inside one minute and a fifth is refused. Separating a
    token-per-minute ceiling from a deployment's throughput needs the sum of
    tokens that landed in the window ending at the refusal -- and needs to
    *exclude* the one that settled outside it. This is the whole reason the two
    columns exist, so it is checked end to end from the exported artifact
    rather than from the live ledger.

    The number itself proves nothing about Azure. What it proves is that the
    artifact now carries enough to compute it, which is what was missing.
    """
    clock = Clock()
    with _open(tmp_path, "l.sqlite3", price_table, clock=clock) as ledger:
        long_ago = _reserve(ledger, "task-old", sequence=0)
        ledger.settle(long_ago, usage=_usage(500_000), resolved_model="test-model")

        clock.advance(300)
        for index in range(1, 5):
            call_id = _reserve(ledger, f"task-{index}", sequence=index)
            clock.advance(10)
            ledger.settle(
                call_id, usage=_usage(200_000), resolved_model="test-model"
            )

        refused = _reserve(ledger, "task-refused", sequence=9)
        clock.advance(1)
        ledger.refuse(refused, status=429)

        export = tmp_path / "ledger.jsonl"
        ledger.export_jsonl(export)

    rows = [json.loads(line) for line in export.read_text().splitlines() if line]
    calls = {row["call_id"]: row for row in rows if row.get("record_type") == "call"}

    refusal_at = datetime.fromisoformat(calls[refused]["concluded_at"])
    window_opens = refusal_at - timedelta(minutes=1)

    tokens_in_window = sum(
        (row.get("input_tokens") or 0) + (row.get("output_tokens") or 0)
        for row in calls.values()
        if row.get("state") == STATE_SETTLED
        and window_opens
        <= datetime.fromisoformat(row["concluded_at"])
        <= refusal_at
    )

    # The four recent calls, and not the one from five minutes earlier.
    assert tokens_in_window == 4 * 210_000
    assert calls[long_ago]["state"] == STATE_SETTLED
    assert datetime.fromisoformat(calls[long_ago]["concluded_at"]) < window_opens


def test_the_receipt_is_unchanged_by_any_of_this(tmp_path, price_table):
    """Timing is new evidence, not a new claim about money.

    A change to the ledger that moved a dollar figure would be a change to what
    the run says it spent, which is not what this is.
    """
    clock = Clock()
    with _open(tmp_path, "l.sqlite3", price_table, clock=clock) as ledger:
        call_id = _reserve(ledger, "task-a")
        ledger.settle(call_id, usage=_usage(), resolved_model="test-model")
        receipt = ledger.receipt_for("task-a", BUCKET_PROBLEM_SOLVING)

    assert receipt.status == "complete"
    assert receipt.model_calls == 1
    # 100,000 input at $10/M plus 10,000 output at $20/M.
    assert receipt.estimated_cost_usd == Decimal("1.20")
