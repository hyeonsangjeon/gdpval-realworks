"""Whether an unpriceable call reaches the receipt, or stops one step short.

The first Agentic Sandbox V2 stage that reached a real model made 24 calls,
filed 18, and published five receipts every one of which read ``complete`` with
an empty ``missing_reasons``. Six calls — a fifth of the bill — were simply not
in the account, and nothing in the output said so.

`#552 <https://github.com/hyeonsangjeon/gdpval-realworks/pull/552>`_ closed the
larger half: a reply that reported its usage is now filed as a turn whatever
the run does next. It left a smaller half open on purpose. A reply that arrives
with *no* usable count was still charged for and still cannot be priced, and
that was kept as a number beside the account — ``model_calls_not_counted`` —
with no consumer anywhere. A count nobody reads does not change a receipt, so
such a run could still make a call it could not price and publish ``complete``
for the calls it could.

This module pins the other end of that wire. The chain it walks is the paid
one, function for function:

    run_model_conversation  →  model_turns_of  →  bind_run_to_ledger
                            →  CostReceiptLedger.receipt_for

``settle_into_a_receipt`` and ``open_the_ledger`` are imported from the paid
script rather than reimplemented, because a copy of the paid path is exactly
what stops being the paid path. Nothing here spends anything: the model is a
stand-in, the tool desk is a list written in advance, and the ledger is a
sqlite file in a temporary directory.

Four numbers have to agree, and the run that prompted this had them disagreeing
in silence:

1. replies the provider sent      (``model_replied`` events)
2. rows in the ledger             (``cost_calls``)
3. calls on the task's receipt    (``receipt["model_calls"]``)
4. the sum of the per-task totals (the grand total)
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest

from core.agentic_v2_conversation import (
    AskForTool,
    ConversationOutcome,
    GaveUp,
    LoopLimits,
    LoopStep,
    ScriptedToolDesk,
    ScriptedVoice,
    StopReason,
    ToolOutcome,
    run_model_conversation,
)
from core.agentic_v2_conversation_runner import model_turns_of
from core.agentic_v2_run_report import STATUS_SUCCESS, summarise_v2_run
from core.agentic_v2_stage_one_budget import StageOneBudget
from core.cost_receipts import (
    BUCKET_PROBLEM_SOLVING,
    REASON_USAGE_ABSENT,
    STATE_SETTLED,
    STATUS_COMPLETE,
    STATUS_PARTIAL,
    build_receipt,
)


BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
for _path in (BATCH_RUNNER_ROOT, BATCH_RUNNER_ROOT / "scripts"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import run_agentic_v2_stage as stage  # noqa: E402


RUN_ID = "run-receipts-1"
INPUT_TOKENS = 1_000
OUTPUT_TOKENS = 100

#: The model the plan pins, and the one the committed price list prices. A
#: made-up name would settle ``price_missing`` on every row and turn every
#: receipt ``partial`` for a reason that has nothing to do with what is being
#: tested here.
DEPLOYMENT = "gpt-5.4"


# ── the stand-in conversation ────────────────────────────────────────────


def limits(**changes) -> LoopLimits:
    settings = {
        "max_model_turns": 6,
        "max_written_tokens_per_turn": 2048,
        "max_seconds": 60.0,
        "max_repeats_of_one_request": 2,
        "budget": StageOneBudget(
            max_model_calls=16,
            max_input_tokens=1_000_000,
            max_output_tokens=200_000,
        ),
    }
    settings.update(changes)
    return LoopLimits(**settings)


def ask(call_id: str, tool_name: str, /, **arguments) -> AskForTool:
    return AskForTool(
        call_id=call_id,
        tool_name=tool_name,
        arguments=arguments,
        why=f"stand-in model asked for {tool_name}",
        input_tokens=INPUT_TOKENS,
        output_tokens=OUTPUT_TOKENS,
    )


def a_run(voice, desk, **limit_changes) -> ConversationOutcome:
    return run_model_conversation(
        task_prompt="write a short report",
        voice=voice,
        desk=desk,
        limits=limits(**limit_changes),
    )


def a_conversation_that_reports_everything() -> ConversationOutcome:
    """Two calls, both counted, both answered. The clean case."""
    return a_run(
        ScriptedVoice(
            replies=[
                ask("call-1", "capabilities_query", kind="commands"),
                ask("call-2", "finalize", deliverables=["r.txt"], summary="ok"),
            ]
        ),
        ScriptedToolDesk(
            answers=[
                ToolOutcome.worked(commands=[]),
                # `committed` rather than `worked`: this is what ends the run.
                # A `worked` finalize leaves the loop asking, the stand-in
                # voice runs out of written replies, and the extra turn is a
                # third call that was never meant to be part of the fixture.
                ToolOutcome.committed({"deliverables": ["r.txt"]}),
            ]
        ),
    )


def a_conversation_with_one_uncounted_reply() -> ConversationOutcome:
    """Two calls, the second of which came back without a usage.

    This is what the real voice does: when a response arrives carrying no
    ``usage`` block it walks away with a note, and the walk-away's token fields
    default to zero. Both calls were served and both will be billed.
    """
    return a_run(
        ScriptedVoice(
            replies=[
                ask("call-1", "capabilities_query", kind="commands"),
                GaveUp(note="the model answered without saying what it used"),
            ]
        ),
        ScriptedToolDesk(answers=[ToolOutcome.worked(commands=[])]),
    )


def replies_the_provider_sent(outcome: ConversationOutcome) -> int:
    """Straight off the event log, which is the half that was always right."""
    return sum(
        1 for event in outcome.events if event.step is LoopStep.MODEL_REPLIED
    )


# ── the paid accounting path, run for real ───────────────────────────────


@pytest.fixture()
def ledger(tmp_path):
    opened = stage.open_the_ledger(tmp_path, run_id=RUN_ID)
    try:
        yield opened
    finally:
        opened.close()


def file_it(ledger, outcome: ConversationOutcome, *, task_id: str, attempt=1):
    """One task's conversation through the exact calls the paid stage makes."""
    turns = model_turns_of(
        outcome,
        run_id=RUN_ID,
        task_id=task_id,
        attempt=attempt,
        provider="azure",
        requested_model=DEPLOYMENT,
        deployment=DEPLOYMENT,
        resolved_model=DEPLOYMENT,
    )
    return stage.settle_into_a_receipt(ledger, task_id=task_id, model_turns=turns)


def rows_in(ledger, task_id: str):
    return ledger.calls_for(task_id, bucket=BUCKET_PROBLEM_SOLVING)


# ── the clean case, so the failing one means something ───────────────────


def test_a_run_that_counted_everything_gets_a_complete_receipt(ledger):
    outcome = a_conversation_that_reports_everything()
    receipt = file_it(ledger, outcome, task_id="task-clean")

    assert outcome.model_calls_not_counted == 0
    assert receipt["status"] == STATUS_COMPLETE
    assert receipt["missing_reasons"] == []
    assert receipt["model_calls"] == replies_the_provider_sent(outcome) == 2
    assert receipt["estimated_cost_usd"] > 0


# ── the case this module exists for ──────────────────────────────────────


def test_an_uncounted_call_makes_the_receipt_say_partial(ledger):
    """The wire, end to end: a count that used to stop at the outcome.

    Before this, the second call was missing from the ledger entirely and the
    receipt reported one call, one price and ``complete``. The bill was 50%
    short and said nothing.
    """
    outcome = a_conversation_with_one_uncounted_reply()
    receipt = file_it(ledger, outcome, task_id="task-short")

    assert outcome.model_calls_not_counted == 1
    assert receipt["status"] == STATUS_PARTIAL
    assert REASON_USAGE_ABSENT in receipt["missing_reasons"]


def test_the_uncounted_call_is_counted_even_though_it_is_not_priced(ledger):
    """A call with no amount is still a call. Both halves matter.

    Counting it is what makes the receipt's ``model_calls`` match the event
    log, which is the check that catches this class of gap. Not pricing it is
    what keeps the total honest — an amount nobody measured must not appear.
    """
    outcome = a_conversation_with_one_uncounted_reply()
    receipt = file_it(ledger, outcome, task_id="task-short")

    assert receipt["model_calls"] == replies_the_provider_sent(outcome) == 2
    assert receipt["known_cost_usd"] == pytest.approx(
        float(one_call_at_list_price()), rel=1e-9
    )


def one_call_at_list_price() -> Decimal:
    """What the single counted call costs, from the committed price list.

    Read rather than written down, so that a price change moves this test with
    the repository instead of against it.
    """
    from core.cost_receipts import load_receipt_price_table

    price = load_receipt_price_table().lookup("azure", DEPLOYMENT)
    assert price is not None, "the committed list prices azure:gpt-5.4"
    return (
        Decimal(INPUT_TOKENS) * price.input_usd_per_million
        + Decimal(OUTPUT_TOKENS) * price.output_usd_per_million
    ) / Decimal(1_000_000)


def test_the_unpriceable_row_holds_no_amount_and_says_why(ledger):
    """What is actually written to sqlite, not just what the receipt says."""
    outcome = a_conversation_with_one_uncounted_reply()
    file_it(ledger, outcome, task_id="task-short")

    rows = rows_in(ledger, "task-short")
    assert len(rows) == 2
    (unpriced,) = [row for row in rows if row["model_cost_usd"] is None]

    assert unpriced["state"] == STATE_SETTLED
    assert REASON_USAGE_ABSENT in unpriced["missing_reasons"]
    # Absent, never zero. A zero here is the defect this whole module is about.
    assert unpriced["input_tokens"] is None
    assert unpriced["output_tokens"] is None
    assert "reported no usage" in (unpriced["note"] or "")


def test_the_receipt_names_the_call_rather_than_hiding_it_in_a_total(ledger):
    """A reader has to be able to find which call is missing, not just how many."""
    outcome = a_conversation_with_one_uncounted_reply()
    receipt = file_it(ledger, outcome, task_id="task-short")

    (short,) = [
        component
        for component in receipt["components"]
        if component["status"] == STATUS_PARTIAL
    ]
    assert REASON_USAGE_ABSENT in short["missing_reasons"]

    # Which turn, by name. Every call in the conversation has a row and the
    # rows are named by the run's own turn counter, so "the second call is the
    # one that cannot be priced" is a readable fact rather than a subtraction.
    rows = {row["call_id"]: row for row in rows_in(ledger, "task-short")}
    assert set(rows) == {
        f"{RUN_ID}:task-short:1:turn-1",
        f"{RUN_ID}:task-short:1:turn-2",
    }
    assert rows[f"{RUN_ID}:task-short:1:turn-2"]["model_cost_usd"] is None
    assert rows[f"{RUN_ID}:task-short:1:turn-1"]["model_cost_usd"] is not None


# ── the four numbers that have to agree ──────────────────────────────────


def test_events_rows_receipt_and_grand_total_all_agree(ledger):
    """The reconciliation the paid run could not do, over a mixed cohort.

    Three tasks: one clean, one short a count, one short a count on a retry.
    Every number is derived from a different object, which is the point — the
    24-vs-18 run had each of these computed from the same short list, so they
    agreed with each other and with nothing that happened.
    """
    work = {
        "task-a": a_conversation_that_reports_everything(),
        "task-b": a_conversation_with_one_uncounted_reply(),
        "task-c": a_conversation_with_one_uncounted_reply(),
    }
    receipts = {
        task_id: file_it(ledger, outcome, task_id=task_id)
        for task_id, outcome in work.items()
    }

    replies = sum(replies_the_provider_sent(o) for o in work.values())
    rows = sum(len(rows_in(ledger, task_id)) for task_id in work)
    on_receipts = sum(receipt["model_calls"] for receipt in receipts.values())
    assert replies == rows == on_receipts == 6

    per_task = sum(
        Decimal(str(receipt["known_cost_usd"])) for receipt in receipts.values()
    )
    whole_run = build_receipt(
        [
            row
            for task_id in ledger.task_ids()
            for row in rows_in(ledger, task_id)
        ]
    )
    assert per_task == whole_run.known_cost_usd
    assert whole_run.model_calls == replies

    # And the run as a whole refuses to call itself settled.
    assert {receipts["task-b"]["status"], receipts["task-c"]["status"]} == {
        STATUS_PARTIAL
    }
    assert receipts["task-a"]["status"] == STATUS_COMPLETE
    assert whole_run.status == STATUS_PARTIAL


def test_the_run_summary_will_not_call_a_short_bill_fully_accounted():
    """The top of the chain, which was reading only half its evidence.

    ``receipt_ceiling`` comes from the journal, and the journal knows about
    attempts that vanished. It cannot know about a call the provider billed
    and did not count — that is a fact about a ledger row. So a run whose every
    receipt said ``partial`` could still publish
    ``cost_is_fully_accounted: true``, which is exactly what the first paid
    stage published over a bill that was a fifth short.
    """
    settled = {
        "status": STATUS_SUCCESS,
        "problem_solving_cost": {"status": STATUS_COMPLETE},
        "observability": {"agentic_metrics": {}},
    }
    short = {
        "status": STATUS_SUCCESS,
        "problem_solving_cost": {
            "status": STATUS_PARTIAL,
            "missing_reasons": [REASON_USAGE_ABSENT],
        },
        "observability": {"agentic_metrics": {}},
    }

    clean = summarise_v2_run(
        [settled, settled], manifest_size=2, receipt_ceiling=STATUS_COMPLETE
    )
    assert clean["cost_is_fully_accounted"] is True
    assert clean["unsettled_receipts"] == {}

    # One short receipt is enough, and the journal is happy in both runs.
    mixed = summarise_v2_run(
        [settled, short], manifest_size=2, receipt_ceiling=STATUS_COMPLETE
    )
    assert mixed["cost_is_fully_accounted"] is False
    assert mixed["unsettled_receipts"] == {STATUS_PARTIAL: 1}
    # The journal's own answer is reported unchanged beside it, so a reader can
    # tell which of the two lowered the verdict.
    assert mixed["receipt_ceiling"] == STATUS_COMPLETE


def test_a_row_with_no_receipt_is_not_read_as_a_complaint():
    """Absent is not partial. The journal's ceiling already covers that case."""
    bare = {"status": STATUS_SUCCESS, "observability": {"agentic_metrics": {}}}
    summary = summarise_v2_run(
        [bare], manifest_size=1, receipt_ceiling=STATUS_COMPLETE
    )
    assert summary["unsettled_receipts"] == {}
    assert summary["cost_is_fully_accounted"] is True


def test_filing_the_same_conversation_twice_does_not_double_the_bill(ledger):
    """A resumed round re-offers rows it already wrote. Ids are what stop it.

    The invented id for an uncounted call is derived from the turn number, so
    it is the same id on the second pass. An id derived from anything mutable —
    a position in a list, a timestamp — would make a resumed run bill the same
    uncounted call twice, and neither pass would look wrong on its own.
    """
    outcome = a_conversation_with_one_uncounted_reply()

    first = file_it(ledger, outcome, task_id="task-resumed")
    second = file_it(ledger, outcome, task_id="task-resumed")

    assert len(rows_in(ledger, "task-resumed")) == 2
    assert first["model_calls"] == second["model_calls"] == 2
    assert first["known_cost_usd"] == second["known_cost_usd"]


def test_two_attempts_at_one_task_are_two_sets_of_rows(ledger):
    """A retry is more spend, not a correction of the first attempt's spend."""
    outcome = a_conversation_with_one_uncounted_reply()

    file_it(ledger, outcome, task_id="task-retried", attempt=1)
    receipt = file_it(ledger, outcome, task_id="task-retried", attempt=2)

    assert len(rows_in(ledger, "task-retried")) == 4
    assert receipt["model_calls"] == 4
    assert receipt["status"] == STATUS_PARTIAL


# ── the shape of the claim, checked against the loop itself ──────────────


def test_every_reply_the_loop_saw_becomes_exactly_one_ledger_row(ledger):
    """No reply is filed twice and none is dropped, across both kinds.

    Stated against the event log rather than against ``turns``, because
    ``turns`` is the list that was wrong.
    """
    for name, outcome in (
        ("counted", a_conversation_that_reports_everything()),
        ("uncounted", a_conversation_with_one_uncounted_reply()),
    ):
        turns = model_turns_of(
            outcome,
            run_id=RUN_ID,
            task_id=name,
            attempt=1,
            provider="azure",
            requested_model=DEPLOYMENT,
            deployment=DEPLOYMENT,
            resolved_model=DEPLOYMENT,
        )
        assert len(turns) == replies_the_provider_sent(outcome)
        assert len({turn.call_id for turn in turns}) == len(turns)


def test_a_reply_that_never_named_its_usage_at_all_is_also_filed(ledger):
    """The other way a count goes missing: a reply with no usage to read.

    ``GaveUp`` above defaults its counts to zero. This one has no readable
    usage whatsoever, which the loop stops on — and the reply still arrived,
    so the provider still billed for it.
    """

    class AVoiceThatSaysNothingAboutUsage:
        # Every voice has to declare whether asking it costs anything; a voice
        # that does not is refused before the first call. Declared here so the
        # run reaches the usage check this test is about.
        makes_paid_calls = False

        def next_turn(self, request):
            return AskForTool(
                call_id="call-1",
                tool_name="capabilities_query",
                arguments={"kind": "commands"},
                why="no counts",
                input_tokens=-1,
                output_tokens=OUTPUT_TOKENS,
            )

    outcome = a_run(AVoiceThatSaysNothingAboutUsage(), ScriptedToolDesk())
    assert outcome.stop_reason is StopReason.MODEL_REPLY_UNUSABLE

    receipt = file_it(ledger, outcome, task_id="task-unreadable")
    assert receipt["model_calls"] == replies_the_provider_sent(outcome) == 1
    assert receipt["status"] == STATUS_PARTIAL
    assert REASON_USAGE_ABSENT in receipt["missing_reasons"]
