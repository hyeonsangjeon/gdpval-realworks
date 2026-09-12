"""The model calls a run pays for and used to leave out of its own account.

Measured, not supposed. The first Agentic Sandbox V2 stage that reached a real
model made **24** model calls across its five tasks and put **18** of them in
the cost ledger. The missing six carried 17,775 input and 292 output tokens —
about 20% of what the stage actually cost — and every receipt still read
``complete`` with an empty ``missing_reasons``. The account was not merely
short; it was short *and* confident, which is the combination that makes a
number unusable, because nothing in the output says to distrust it.

The cause was structural rather than arithmetic. ``run_model_conversation``
records a turn by appending a :class:`TurnRecord` *after* the tool desk has
answered, and ten different stops sit between the model's reply arriving and
that append. Each of those is a call the provider has already charged for and
the record never mentions. The loop's own event log got this right from the
start — ``MODEL_REPLIED`` is written the moment the reply lands — so the two
halves of the same run disagreed, and only the half that carries the money was
wrong.

What is pinned here
-------------------

* every stop between the reply and the tool result still files the turn,
* the turn says which tool the money was spent asking for, where the run got
  far enough to know,
* a turn is filed exactly once, never twice,
* the calls that genuinely cannot be priced — a reply that never said what it
  used, and a reply whose counts came back zero — reach the ledger as rows
  with no usage rather than as turns carrying zeros that would settle to
  ``$0.00``,
* what reaches the ledger, through ``model_turns_of``, matches what was asked.

Nothing here spends anything: the model is a stand-in and the tool desk is a
list written in advance.
"""

from __future__ import annotations

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
from core.agentic_v2_stage_one_budget import StageOneBudget


INPUT_TOKENS = 100
OUTPUT_TOKENS = 20


def a_budget(**changes) -> StageOneBudget:
    settings = {
        "max_model_calls": 16,
        "max_input_tokens": 1_000_000,
        "max_output_tokens": 200_000,
    }
    settings.update(changes)
    return StageOneBudget(**settings)


def limits(**changes) -> LoopLimits:
    settings = {
        "max_model_turns": 6,
        "max_written_tokens_per_turn": 2048,
        "max_seconds": 60.0,
        "max_repeats_of_one_request": 2,
        "budget": a_budget(),
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


def look_around(call_id: str = "call-1") -> AskForTool:
    return ask(call_id, "capabilities_query", kind="commands")


def browse(call_id: str = "call-1") -> AskForTool:
    return ask(call_id, "browser_run", url="https://example.invalid", action="open")


def commit(call_id: str = "call-9") -> AskForTool:
    return ask(call_id, "finalize", deliverables=["report.txt"], summary="done")


def a_run(voice, desk, **limit_changes) -> ConversationOutcome:
    changes = dict(limit_changes)
    cancel = changes.pop("cancel_requested", None)
    clock = changes.pop("clock", None)
    extra = {}
    if cancel is not None:
        extra["cancel_requested"] = cancel
    if clock is not None:
        extra["clock"] = clock
    return run_model_conversation(
        task_prompt="write a short report",
        voice=voice,
        desk=desk,
        limits=limits(**changes),
        **extra,
    )


def calls_the_model_answered(outcome: ConversationOutcome) -> int:
    """How many replies the provider sent, straight off the event log.

    The event log is the half of the record that was already right, so it is
    the reference the account is checked against rather than a second opinion.
    """
    return sum(
        1 for event in outcome.events if event.step is LoopStep.MODEL_REPLIED
    )


# ---------------------------------------------------------------------------
# The shape that was measured
# ---------------------------------------------------------------------------


class ARaisingDesk:
    """A tool desk that falls over, which is one of the ten lost paths."""

    def run_one(self, *, call_id, tool_name, arguments):
        raise RuntimeError("the desk fell over")


class ADeskThatAnswersWithRubbish:
    def run_one(self, *, call_id, tool_name, arguments):
        return {"ok": True}


def a_clock_that_runs_away():
    """Zero on the first look, well past any ceiling afterwards."""
    ticks = iter([0.0, 0.0, 0.0, 10_000.0, 10_000.0, 10_000.0])

    def clock() -> float:
        try:
            return next(ticks)
        except StopIteration:
            return 10_000.0

    return clock


STOPS_BETWEEN_THE_REPLY_AND_THE_TOOL_RESULT = [
    pytest.param(
        ScriptedVoice(replies=[GaveUp(note="I cannot", input_tokens=INPUT_TOKENS,
                                      output_tokens=OUTPUT_TOKENS)]),
        ScriptedToolDesk(),
        {},
        StopReason.MODEL_STOPPED_WITHOUT_FINISHING,
        "",
        id="the model walked away",
    ),
    pytest.param(
        ScriptedVoice(replies=[look_around()]),
        ScriptedToolDesk(),
        {"max_written_tokens_per_turn": OUTPUT_TOKENS - 1},
        StopReason.WRITING_LIMIT_REACHED,
        "capabilities_query",
        id="it wrote past the per-turn ceiling",
    ),
    pytest.param(
        ScriptedVoice(replies=[look_around()]),
        ScriptedToolDesk(),
        {"budget": a_budget(max_output_tokens=OUTPUT_TOKENS - 1)},
        StopReason.COST_LIMIT_REACHED,
        "capabilities_query",
        id="the budget refused the reply it had already been sent",
    ),
    pytest.param(
        ScriptedVoice(replies=[ask("", "capabilities_query", kind="commands")]),
        ScriptedToolDesk(),
        {},
        StopReason.MODEL_REPLY_UNUSABLE,
        "",
        id="the reply was not a usable request",
    ),
    pytest.param(
        ScriptedVoice(replies=[look_around(), look_around(), look_around()]),
        ScriptedToolDesk(
            answers=[ToolOutcome.refused("capability_unavailable")] * 3
        ),
        {"max_repeats_of_one_request": 1},
        StopReason.REPEATED_REQUEST,
        "capabilities_query",
        id="it went in circles",
    ),
    pytest.param(
        ScriptedVoice(replies=[look_around()]),
        ARaisingDesk(),
        {},
        StopReason.TOOL_DESK_BROKE,
        "capabilities_query",
        id="the tool desk fell over",
    ),
    pytest.param(
        ScriptedVoice(replies=[look_around()]),
        ADeskThatAnswersWithRubbish(),
        {},
        StopReason.TOOL_DESK_BROKE,
        "capabilities_query",
        id="the tool desk answered with something else",
    ),
]


@pytest.mark.parametrize(
    "voice,desk,changes,expected_stop,expected_tool",
    STOPS_BETWEEN_THE_REPLY_AND_THE_TOOL_RESULT,
)
def test_every_stop_after_the_reply_still_files_the_call(
    voice, desk, changes, expected_stop, expected_tool
):
    outcome = a_run(voice, desk, **changes)

    assert outcome.stop_reason is expected_stop
    answered = calls_the_model_answered(outcome)
    assert answered >= 1
    assert len(outcome.turns) == answered, (
        f"{answered} reply(ies) arrived and {len(outcome.turns)} were filed; "
        "the difference is money the run spent and did not write down"
    )
    last = outcome.turns[-1]
    assert last.input_tokens == INPUT_TOKENS
    assert last.output_tokens == OUTPUT_TOKENS
    assert last.tool_name == expected_tool
    assert last.ok is False
    assert last.error_type == expected_stop.value


def test_a_cancelled_run_still_files_the_reply_it_paid_for():
    """Cancellation is the stop most likely to be read as costing nothing."""
    stops = iter([False, True])
    outcome = a_run(
        ScriptedVoice(replies=[look_around()]),
        ScriptedToolDesk(),
        cancel_requested=lambda: next(stops, True),
    )

    assert outcome.stop_reason is StopReason.CANCELLED
    assert len(outcome.turns) == calls_the_model_answered(outcome) == 1
    assert outcome.turns[0].output_tokens == OUTPUT_TOKENS
    assert outcome.turns[0].error_type == StopReason.CANCELLED.value


def test_running_out_of_time_mid_turn_still_files_the_reply():
    outcome = a_run(
        ScriptedVoice(replies=[look_around()]),
        ScriptedToolDesk(),
        clock=a_clock_that_runs_away(),
    )

    assert outcome.stop_reason is StopReason.TIME_LIMIT_REACHED
    assert len(outcome.turns) == calls_the_model_answered(outcome) == 1
    assert outcome.turns[0].tool_name == "capabilities_query"


def test_the_filed_turn_names_the_tool_the_money_was_spent_asking_for():
    """Three of the five tasks in the first paid stage died on ``browser_run``.

    Which tool is the whole finding there — a stage that reports six anonymous
    charged turns says the run was expensive, and a stage that reports six
    charged ``browser_run`` requests says the backend has no browser.
    """
    outcome = a_run(ScriptedVoice(replies=[browse()]), ARaisingDesk())

    assert outcome.turns[-1].tool_name == "browser_run"
    assert outcome.turns[-1].argument_names == ("action", "url")
    assert outcome.turns[-1].call_id == "call-1"
    assert outcome.tools_asked_for == ("browser_run",)


def test_a_turn_that_never_named_a_tool_is_not_reported_as_one():
    """It is still filed — the money is real — but it is not a tool call."""
    outcome = a_run(
        ScriptedVoice(replies=[GaveUp(note="", input_tokens=INPUT_TOKENS,
                                      output_tokens=OUTPUT_TOKENS)]),
        ScriptedToolDesk(),
    )

    assert len(outcome.turns) == 1
    assert outcome.turns[0].tool_name == ""
    assert outcome.turns[0].call_id == "turn-1-no-tool-result"
    assert outcome.tools_asked_for == ()


# ---------------------------------------------------------------------------
# The other direction: never twice
# ---------------------------------------------------------------------------


def test_a_turn_the_tool_answered_is_filed_once_and_only_once():
    """A flush that did not clear itself would double-bill the last turn."""
    desk = ScriptedToolDesk(
        answers=[
            ToolOutcome.worked(commands=[]),
            ToolOutcome.worked(commands=[]),
        ]
    )
    outcome = a_run(
        ScriptedVoice(replies=[look_around("call-1"), look_around("call-2")]),
        desk,
        max_model_turns=2,
    )

    assert outcome.stop_reason is StopReason.TURN_LIMIT_REACHED
    assert len(outcome.turns) == calls_the_model_answered(outcome) == 2
    assert [record.call_id for record in outcome.turns] == ["call-1", "call-2"]
    assert [record.ok for record in outcome.turns] == [True, True]


def test_a_run_that_finishes_normally_files_exactly_its_replies():
    desk = ScriptedToolDesk(
        answers=[
            ToolOutcome.worked(commands=[]),
            ToolOutcome.committed({"deliverables": ["report.txt"]}),
        ]
    )
    outcome = a_run(
        ScriptedVoice(replies=[look_around("call-1"), commit("call-2")]), desk
    )

    assert outcome.stop_reason is StopReason.FINISHED_NORMALLY
    assert len(outcome.turns) == calls_the_model_answered(outcome) == 2
    assert outcome.tools_asked_for == ("capabilities_query", "finalize")


def test_a_run_refused_before_the_model_was_asked_files_nothing():
    """Nothing was sent, so there is nothing to charge and nothing to file."""
    outcome = run_model_conversation(
        task_prompt="write a short report",
        voice=ScriptedVoice(replies=[look_around()]),
        desk=ScriptedToolDesk(),
        limits=limits(max_model_turns=None),
    )

    assert outcome.stop_reason is StopReason.LIMIT_MISSING
    assert outcome.turns == ()
    assert calls_the_model_answered(outcome) == 0


# ---------------------------------------------------------------------------
# The one gap that stays a gap
# ---------------------------------------------------------------------------


class AVoiceThatDoesNotSayWhatItUsed:
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


def test_a_reply_that_never_said_what_it_used_is_left_out_not_zeroed():
    """The honest gap, now open in the ledger instead of outside it.

    A reply with no usable counts was charged for like any other, and the run
    has no figure for it. Filing it as a turn with zeros would put the one
    number in the account that reads as a measurement, so it is not a turn. It
    is a ledger row with no usage at all, which is a different sentence: *this
    was charged and cannot be priced*. The receipt built over it says
    ``partial`` rather than quietly reading ``complete`` for the calls it did
    manage to price.
    """
    outcome = a_run(AVoiceThatDoesNotSayWhatItUsed(), ScriptedToolDesk())

    assert outcome.stop_reason is StopReason.MODEL_REPLY_UNUSABLE
    assert outcome.turns == ()
    assert calls_the_model_answered(outcome) == 1
    assert outcome.model_calls_not_counted == 1
    assert "how much it used" in outcome.detail

    (entry,) = a_ledger_entry_per_turn(outcome)
    assert entry.usage.is_empty
    assert entry.usage.input_tokens is None
    assert entry.usage.output_tokens is None


def test_a_reply_reporting_no_input_tokens_is_counted_but_not_priced():
    """The other half of the same gap, and the one that nearly became a zero.

    The real voice walks away when a response arrives with no ``usage``, and a
    walk-away's token fields default to zero. Nothing calls a model for nothing
    on the way in — the task prompt alone is thousands of tokens — so a zero
    input count is a reply that was never counted, not a reply that was free.
    Filing it as a turn would settle to ``$0.00`` on a ``complete`` receipt,
    which reads as a measurement of a call nobody measured; so it reaches the
    ledger with its usage absent instead, and absent does not add up to
    anything.
    """
    outcome = a_run(
        ScriptedVoice(replies=[GaveUp(note="the model answered without saying "
                                           "what it used")]),
        ScriptedToolDesk(),
    )

    assert outcome.stop_reason is StopReason.MODEL_STOPPED_WITHOUT_FINISHING
    assert outcome.turns == ()
    assert outcome.model_calls_not_counted == 1
    assert calls_the_model_answered(outcome) == 1
    assert outcome.as_dict()["model_calls_not_counted"] == 1

    # In the account, and in it as an unknown rather than as a zero.
    (entry,) = a_ledger_entry_per_turn(outcome)
    assert entry.usage.is_empty
    assert entry.call_id == "run-1:task-1:1:turn-1"
    assert "reported no usage" in (entry.note or "")


def test_a_counted_reply_does_not_show_up_as_uncounted():
    outcome = a_run(ScriptedVoice(replies=[browse()]), ARaisingDesk())

    assert outcome.model_calls_not_counted == 0
    assert len(outcome.turns) == 1


# ---------------------------------------------------------------------------
# What actually reaches the ledger
# ---------------------------------------------------------------------------


def a_ledger_entry_per_turn(outcome: ConversationOutcome):
    return model_turns_of(
        outcome,
        run_id="run-1",
        task_id="task-1",
        attempt=1,
        provider="azure",
        requested_model="gpt-5.4",
        deployment="gpt-5.4",
        api_version="2025-04-01-preview",
        resolved_model="gpt-5.4",
    )


def test_the_ledger_gets_one_entry_for_every_call_the_model_answered():
    """The 24-vs-18 shape, in miniature and in the object that carries money."""
    outcome = a_run(ScriptedVoice(replies=[browse()]), ARaisingDesk())

    entries = a_ledger_entry_per_turn(outcome)
    assert len(entries) == calls_the_model_answered(outcome) == 1
    assert entries[0].usage.input_tokens == INPUT_TOKENS
    assert entries[0].usage.output_tokens == OUTPUT_TOKENS
    # Named by the run's own turn counter, not by the id the model chose. The
    # model's id is still on the turn record beside the run; what the ledger
    # needs is a key it can write before the reply exists, because that is what
    # a reservation is.
    assert entries[0].call_id == "run-1:task-1:1:turn-1"


def test_no_two_ledger_entries_from_one_run_share_a_call_id():
    """Call ids are the ledger's primary key, including the invented ones."""
    desk = ScriptedToolDesk(answers=[ToolOutcome.worked(commands=[])])
    outcome = a_run(
        ScriptedVoice(
            replies=[
                look_around("call-1"),
                GaveUp(note="", input_tokens=INPUT_TOKENS,
                       output_tokens=OUTPUT_TOKENS),
            ]
        ),
        desk,
    )

    assert outcome.stop_reason is StopReason.MODEL_STOPPED_WITHOUT_FINISHING
    entries = a_ledger_entry_per_turn(outcome)
    assert len(entries) == calls_the_model_answered(outcome) == 2
    assert len({entry.call_id for entry in entries}) == 2
