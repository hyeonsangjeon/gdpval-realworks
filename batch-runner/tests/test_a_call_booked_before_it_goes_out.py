"""What the ledger holds when the run does not survive the call it made.

Every other thing this run records about a model call is written after the
reply is in hand: what it used, what it cost, which tool it asked for, whether
the tool answered. That is fine for a run that finishes. It is worth nothing to
a run that stops between the request leaving and the reply arriving, and three
ordinary things do exactly that:

* a shard that exceeds its ``timeout-minutes`` is killed where it stands,
* an exception between the two unwinds past every recorder,
* a resumed run starts a fresh journal that knows nothing of the attempt that
  died.

In all three the provider was asked and will bill. Before this, all three left
the ledger empty for that call, and an empty ledger reads as *no call was
made* — the same sentence a run that genuinely made none would write.

So the call is booked before it goes out. The reservation carries no amount and
claims none; it says *a call left and this run never found out what happened to
it*, which is :data:`~core.cost_receipts.REASON_CALL_REACHABILITY_UNKNOWN`, and
it holds the receipt at ``partial``. A run that comes back settles the same row
by the same id — :func:`~core.agentic_v2_conversation_runner.ledger_call_id`
builds it for both, because two spellings would mean every paid call appeared
twice, once open and once priced, with each row looking right on its own.

The path exercised here is the paid one, function for function::

    reserve_before_each_call  →  run_model_conversation(before_model_call=…)
                              →  model_turns_of  →  settle_into_a_receipt

``open_the_ledger`` and ``settle_into_a_receipt`` are imported from the paid
script rather than reimplemented. Nothing spends anything: the model is a
stand-in, the tool desk is a list written in advance, and the ledger is a
sqlite file in a temporary directory.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from core.agentic_v2_conversation import (
    AskForTool,
    GaveUp,
    LoopLimits,
    ScriptedToolDesk,
    ScriptedVoice,
    StopReason,
    ToolOutcome,
    run_model_conversation,
)
from core.agentic_v2_conversation_runner import (
    ledger_call_id,
    model_turns_of,
    reserve_before_each_call,
)
from core.agentic_v2_stage_one_budget import StageOneBudget
from core.cost_receipts import (
    BUCKET_PROBLEM_SOLVING,
    REASON_CALL_REACHABILITY_UNKNOWN,
    STATE_RESERVED,
    STATE_SETTLED,
    STATUS_PARTIAL,
    STATUS_UNAVAILABLE,
)


BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
for _path in (BATCH_RUNNER_ROOT, BATCH_RUNNER_ROOT / "scripts"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import run_agentic_v2_stage as stage  # noqa: E402


RUN_ID = "run-booked-1"
DEPLOYMENT = "gpt-5.4"
INPUT_TOKENS = 1_000
OUTPUT_TOKENS = 100


# ── the paid path's own pieces ───────────────────────────────────────────


@pytest.fixture()
def ledger(tmp_path):
    opened = stage.open_the_ledger(tmp_path, run_id=RUN_ID)
    try:
        yield opened
    finally:
        opened.close()


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


def booking(ledger, *, task_id: str, attempt: int = 1):
    """The hook the paid stage hands the loop, built the way the stage builds it."""
    return reserve_before_each_call(
        ledger,
        run_id=RUN_ID,
        task_id=task_id,
        attempt=attempt,
        provider="azure",
        requested_model=DEPLOYMENT,
        deployment=DEPLOYMENT,
    )


def converse(ledger, *, task_id: str, voice, desk=None, attempt: int = 1, **changes):
    # ``cancel_requested`` and ``clock`` belong to the loop, everything else to
    # its limits. Splitting here rather than at each call site keeps the tests
    # below reading as what the run did, not as how the run was wired.
    loop_only = {
        name: changes.pop(name)
        for name in ("cancel_requested", "clock")
        if name in changes
    }
    return run_model_conversation(
        task_prompt="write a short report",
        voice=voice,
        desk=desk if desk is not None else ScriptedToolDesk(),
        limits=limits(**changes),
        before_model_call=booking(ledger, task_id=task_id, attempt=attempt),
        **loop_only,
    )


def settle(ledger, outcome, *, task_id: str, attempt: int = 1):
    """The second half, exactly as the stage's ``receipt_for`` runs it."""
    return stage.settle_into_a_receipt(
        ledger,
        task_id=task_id,
        model_turns=model_turns_of(
            outcome,
            run_id=RUN_ID,
            task_id=task_id,
            attempt=attempt,
            provider="azure",
            requested_model=DEPLOYMENT,
            deployment=DEPLOYMENT,
            resolved_model=DEPLOYMENT,
        ),
    )


def rows_in(ledger, task_id: str) -> dict[str, dict]:
    return {
        row["call_id"]: row
        for row in ledger.calls_for(task_id, bucket=BUCKET_PROBLEM_SOLVING)
    }


def a_receipt_over(ledger, task_id: str) -> dict:
    """What the task's receipt says, with nothing settled into it first.

    ``when_empty`` matches the stage's, so a task with no rows at all is
    ``unavailable`` rather than a ``$0`` the run never measured.
    """
    return ledger.receipt_for(
        task_id, bucket=BUCKET_PROBLEM_SOLVING, when_empty=STATUS_UNAVAILABLE
    ).as_dict()


def two_calls_then_finish() -> ScriptedVoice:
    return ScriptedVoice(
        replies=[
            ask("call-1", "capabilities_query", kind="commands"),
            ask("call-2", "finalize", deliverables=["r.txt"], summary="ok"),
        ]
    )


def a_desk_that_answers_then_commits() -> ScriptedToolDesk:
    return ScriptedToolDesk(
        answers=[
            ToolOutcome.worked(commands=[]),
            ToolOutcome.committed({"deliverables": ["r.txt"]}),
        ]
    )


# ── the ordering claim, which is the whole point ─────────────────────────


def test_the_row_exists_before_the_request_leaves(ledger):
    """Checked from inside the request, which is the only honest place.

    A test that looks afterwards cannot tell a row written before the call from
    one written after it, and "after" is the defect. So the stand-in model looks
    the ledger up from inside ``next_turn`` — it has been asked, the hook has
    run, and nothing else has.
    """
    seen: list[tuple[str, str]] = []

    class AVoiceThatChecksItsOwnBooking:
        makes_paid_calls = False

        def next_turn(self, request):
            call_id = ledger_call_id(
                run_id=RUN_ID, task_id="task-checked", attempt=1, turn=request.turn
            )
            row = rows_in(ledger, "task-checked").get(call_id)
            assert row is not None, "the call went out before it was booked"
            seen.append((call_id, row["state"]))
            return GaveUp(note="that is all I needed to know")

    outcome = converse(
        ledger, task_id="task-checked", voice=AVoiceThatChecksItsOwnBooking()
    )

    assert outcome.stop_reason is StopReason.MODEL_STOPPED_WITHOUT_FINISHING
    assert seen == [(f"{RUN_ID}:task-checked:1:turn-1", STATE_RESERVED)]


# ── the three ways a run does not come back ──────────────────────────────


class TheShardRanOutOfWallClock(BaseException):
    """Not an ``Exception``, so the loop cannot catch it.

    That is the point. A shard killed by ``timeout-minutes`` does not get a
    handler, does not return an outcome, and does not reach a single line of
    the accounting that runs after the loop. Anything the ledger holds
    afterwards was written before the call.
    """


def test_a_run_killed_mid_call_still_has_both_calls_in_the_ledger(ledger):
    class AVoiceTheProcessDiesIn:
        makes_paid_calls = False

        def next_turn(self, request):
            if request.turn == 1:
                return ask("call-1", "capabilities_query", kind="commands")
            raise TheShardRanOutOfWallClock()

    with pytest.raises(TheShardRanOutOfWallClock):
        converse(
            ledger,
            task_id="task-killed",
            voice=AVoiceTheProcessDiesIn(),
            desk=ScriptedToolDesk(answers=[ToolOutcome.worked(commands=[])]),
        )

    rows = rows_in(ledger, "task-killed")
    assert set(rows) == {
        f"{RUN_ID}:task-killed:1:turn-1",
        f"{RUN_ID}:task-killed:1:turn-2",
    }
    # Both still open. Turn one's reply arrived and was priceable, but pricing
    # happens after the loop returns and the loop never returned — so even the
    # call that went well is an unknown, which is the true reading.
    assert [row["state"] for row in rows.values()] == [STATE_RESERVED] * 2
    assert all(row["model_cost_usd"] is None for row in rows.values())


def test_the_receipt_over_a_killed_run_says_it_never_found_out(ledger):
    """``partial`` and a reason, not ``complete`` and not ``$0``."""

    class AVoiceTheProcessDiesIn:
        makes_paid_calls = False

        def next_turn(self, request):
            raise TheShardRanOutOfWallClock()

    with pytest.raises(TheShardRanOutOfWallClock):
        converse(ledger, task_id="task-killed", voice=AVoiceTheProcessDiesIn())

    receipt = a_receipt_over(ledger, "task-killed")
    assert receipt["status"] == STATUS_PARTIAL
    assert REASON_CALL_REACHABILITY_UNKNOWN in receipt["missing_reasons"]
    assert receipt["model_calls"] == 1
    assert receipt["estimated_cost_usd"] is None


def test_an_exception_in_the_voice_leaves_the_call_open_not_absent(ledger):
    """The loop catches this one, and the row is still the honest shape.

    ``next_turn`` raising might mean the request never left — a client that
    could not be built — or that it left and the reply could not be read. This
    process cannot tell, and the ledger has a word for each: ``abandoned``
    claims the call never went out, and its own docstring restricts it to
    failures *known* to precede the request. This is not one of those, so the
    row stays reserved and says so.
    """

    class AVoiceThatFallsOver:
        makes_paid_calls = False

        def next_turn(self, request):
            if request.turn == 1:
                return ask("call-1", "capabilities_query", kind="commands")
            raise RuntimeError("the client fell over")

    outcome = converse(
        ledger,
        task_id="task-raised",
        voice=AVoiceThatFallsOver(),
        desk=ScriptedToolDesk(answers=[ToolOutcome.worked(commands=[])]),
    )
    assert outcome.stop_reason is StopReason.MODEL_REPLY_UNUSABLE

    receipt = settle(ledger, outcome, task_id="task-raised")
    rows = rows_in(ledger, "task-raised")

    # Turn one came back and is priced. Turn two went out and never answered.
    assert rows[f"{RUN_ID}:task-raised:1:turn-1"]["state"] == STATE_SETTLED
    assert rows[f"{RUN_ID}:task-raised:1:turn-2"]["state"] == STATE_RESERVED
    assert receipt["status"] == STATUS_PARTIAL
    assert REASON_CALL_REACHABILITY_UNKNOWN in receipt["missing_reasons"]
    # The half that is known is still published, as a floor rather than a total.
    assert receipt["known_cost_usd"] > 0
    assert receipt["model_calls"] == 2


def test_a_cancelled_run_settles_the_calls_it_already_made(ledger):
    """Cancellation returns, so the run settles — and must settle the same rows.

    Two ids for one call would put every cancelled call in the ledger twice,
    once open and once priced, and the doubled total would be made of rows that
    each look correct.
    """
    stops = iter([False, True])
    outcome = converse(
        ledger,
        task_id="task-cancelled",
        voice=two_calls_then_finish(),
        desk=a_desk_that_answers_then_commits(),
        cancel_requested=lambda: next(stops, True),
    )
    assert outcome.stop_reason is StopReason.CANCELLED

    receipt = settle(ledger, outcome, task_id="task-cancelled")
    rows = rows_in(ledger, "task-cancelled")

    assert set(rows) == {f"{RUN_ID}:task-cancelled:1:turn-1"}
    assert rows[f"{RUN_ID}:task-cancelled:1:turn-1"]["state"] == STATE_SETTLED
    assert receipt["model_calls"] == 1
    assert receipt["known_cost_usd"] > 0


def test_a_resumed_attempt_neither_doubles_the_bill_nor_drops_a_call(ledger):
    """The third way a run does not come back: it comes back as a new process.

    The resumed round re-runs the same attempt and re-books the same turns. The
    ids are the run's own and derived from the turn number, so a second pass
    finds the rows it left rather than writing new ones. Anything derived from
    a timestamp or a list position would bill the dead attempt twice, and
    neither pass would look wrong on its own.
    """
    first = converse(
        ledger,
        task_id="task-resumed",
        voice=two_calls_then_finish(),
        desk=a_desk_that_answers_then_commits(),
    )
    settle(ledger, first, task_id="task-resumed")
    before = a_receipt_over(ledger, "task-resumed")

    second = converse(
        ledger,
        task_id="task-resumed",
        voice=two_calls_then_finish(),
        desk=a_desk_that_answers_then_commits(),
    )
    settle(ledger, second, task_id="task-resumed")
    after = a_receipt_over(ledger, "task-resumed")

    assert len(rows_in(ledger, "task-resumed")) == 2
    assert before["model_calls"] == after["model_calls"] == 2
    assert before["known_cost_usd"] == after["known_cost_usd"]


def test_a_retry_of_a_killed_attempt_keeps_the_dead_attempt_open(ledger):
    """A second attempt is more spend, and does not settle the first's unknown.

    This is the shape a resumed run actually has: attempt one died mid-call,
    attempt two ran to the end. The task's receipt has to carry both, because
    both were charged — and it has to stay ``partial``, because what attempt
    one cost is still not known.
    """

    class AVoiceTheProcessDiesIn:
        makes_paid_calls = False

        def next_turn(self, request):
            raise TheShardRanOutOfWallClock()

    with pytest.raises(TheShardRanOutOfWallClock):
        converse(
            ledger,
            task_id="task-retried",
            voice=AVoiceTheProcessDiesIn(),
            attempt=1,
        )

    second = converse(
        ledger,
        task_id="task-retried",
        voice=two_calls_then_finish(),
        desk=a_desk_that_answers_then_commits(),
        attempt=2,
    )
    receipt = settle(ledger, second, task_id="task-retried", attempt=2)

    rows = rows_in(ledger, "task-retried")
    assert set(rows) == {
        f"{RUN_ID}:task-retried:1:turn-1",
        f"{RUN_ID}:task-retried:2:turn-1",
        f"{RUN_ID}:task-retried:2:turn-2",
    }
    assert rows[f"{RUN_ID}:task-retried:1:turn-1"]["state"] == STATE_RESERVED
    assert receipt["model_calls"] == 3
    assert receipt["status"] == STATUS_PARTIAL
    assert REASON_CALL_REACHABILITY_UNKNOWN in receipt["missing_reasons"]


# ── the booking and the settlement have to be one row ────────────────────


def test_the_booking_and_the_settlement_name_the_same_row(ledger):
    """One call, one row, both halves. The id function is why."""
    outcome = converse(
        ledger,
        task_id="task-whole",
        voice=two_calls_then_finish(),
        desk=a_desk_that_answers_then_commits(),
    )
    assert outcome.stop_reason is StopReason.FINISHED_NORMALLY

    booked = set(rows_in(ledger, "task-whole"))
    receipt = settle(ledger, outcome, task_id="task-whole")
    after = rows_in(ledger, "task-whole")

    assert booked == set(after)
    assert len(after) == 2
    assert [row["state"] for row in after.values()] == [STATE_SETTLED] * 2
    assert receipt["status"] == "complete"
    assert receipt["missing_reasons"] == []


def test_a_booking_that_cannot_be_written_stops_the_run_before_the_call(ledger):
    """If the run cannot write down what it is about to spend, it does not spend it.

    The inverse of everything above. A hook that fails means the reservation is
    not there, and making the call anyway would recreate exactly the gap this
    change closes — a charge with no row.
    """
    asked: list[int] = []

    class AVoiceThatMustNotBeAsked:
        makes_paid_calls = False

        def next_turn(self, request):  # pragma: no cover - the point is it is not
            asked.append(request.turn)
            return GaveUp(note="should never get here")

    def a_ledger_that_will_not_take_it(turn: int) -> None:
        raise RuntimeError("the ledger is not writable")

    outcome = run_model_conversation(
        task_prompt="write a short report",
        voice=AVoiceThatMustNotBeAsked(),
        desk=ScriptedToolDesk(),
        limits=limits(),
        before_model_call=a_ledger_that_will_not_take_it,
    )

    assert outcome.stop_reason is StopReason.PAID_CALL_REFUSED
    assert asked == []
    assert outcome.turns == ()
    assert "not writable" in outcome.detail


def test_a_run_with_no_booking_still_works(ledger):
    """The hook is optional, and a caller without a ledger is not broken by it.

    The rehearsal path passes nothing — it asks no model, so there is nothing
    to book and a reserved row would be the one line claiming otherwise.
    """
    outcome = run_model_conversation(
        task_prompt="write a short report",
        voice=two_calls_then_finish(),
        desk=a_desk_that_answers_then_commits(),
        limits=limits(),
    )

    assert outcome.stop_reason is StopReason.FINISHED_NORMALLY
    assert rows_in(ledger, "task-whole") == {}
