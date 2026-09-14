"""A task that ran out of turns and a task that went quiet record the same word.

``experiment-design`` §5 is about who validates the judge, and the corrected-
harness plan promises to separate three failures: a tool the desk refuses, a run
that exhausts its turns, and a model that talks and stops without finalising.
The first is separated. The other two are not.

:data:`~core.agentic_v2_runner.ERROR_TYPE_FOR_A_CONVERSATION_THAT_STOPPED` maps
six of :class:`~core.agentic_v2_conversation.StopReason`'s thirteen members.
Everything else takes the default, ``finalize_not_called`` -- including
``turn_limit_reached``, which the loop raises itself at
``max_model_turns = tool_calls_per_attempt + 1``. So a task that worked steadily
to its last allowed turn and a task that said one thing and stopped are the same
string in the run record, and they are opposite findings: one says the ceiling
was too low, the other says the model could not do the task.

**Two things made this hard to see.**

:mod:`core.agentic_v2_outcome` said the opposite in two places. Its
``FINALIZE_ENDED_FIRST`` comment said a turn-limit task and a talked-itself-out
task "are different failures and get counted separately", and ``ending_label``
said it covered "a turn ceiling, a wall clock and a broken desk". Both named the
turn ceiling specifically, and the turn ceiling is the one case that does not
reach either of them.

And the ceiling the map *does* name is a different ceiling.
``tool_call_limit_reached`` is never raised by the loop -- it arrives only when a
tool desk returns ``tool_budget_exhausted`` about itself -- so the tests that
pin the separation, which hand-build the string ``tool_budget_exhausted`` and
pass it to :func:`~core.agentic_v2_outcome.read_outcome`, exercise an ending no
conversation produces and never touch the map. Before this file the map had no
test at all: it appeared in one file, the one that defines it.

**What is not claimed.** No published number changes.
:func:`~core.agentic_v2_outcome.read_outcome`, ``count_separately`` and
``ending_label`` have no production caller, and the exact reason survives in the
run record at ``conversations[task#attempt].stop_reason``, which is pinned
below. This is a summary field that answers the wrong question, not lost data.

**What is not fixed.** Giving the turn ceiling a name of its own means a new
member in :data:`core.agentic_v2_contract.ERROR_TYPES` and a disposition for it
in :data:`core.agentic_v2_cost_binding.ERROR_DISPOSITION`, which decides what is
retried and therefore what a run costs. That is a paid-path schema change and is
out of scope here. What this file does instead is make the omission explicit and
unable to grow: every ending is mapped or is listed in
:data:`~core.agentic_v2_runner.STOP_REASONS_WITH_NO_ERROR_TYPE_TO_NAME_THEM`,
and a new one can be neither.

Offline, free, model-free. The conversations below run the real loop against
the in-repository stand-in voice and desk.
"""

from __future__ import annotations

import inspect

import pytest

from core.agentic_v2_conversation import (
    AskForTool,
    ConversationOutcome,
    GaveUp,
    ScriptedToolDesk,
    ScriptedVoice,
    StopReason,
    ToolOutcome,
    run_model_conversation,
)
from core.agentic_v2_conversation_runner import ceilings_from
from core.agentic_v2_outcome import FINALIZE_ENDED_FIRST, FINALIZE_NOT_CALLED, ending_label
from core.agentic_v2_runner import (
    ERROR_TYPE_FOR_A_CONVERSATION_THAT_STOPPED,
    STOP_REASONS_WITH_NO_ERROR_TYPE_TO_NAME_THEM,
)
from core import agentic_v2_outcome, agentic_v2_runner

#: What an unmapped ending is recorded as.
THE_DEFAULT = "finalize_not_called"

#: The ceiling the map names. Kept as a constant because the point below is
#: that it is *not* the ceiling a conversation reaches.
THE_DESK_SIDE_CEILING = "tool_call_limit_reached"

#: The ceiling a conversation actually reaches.
THE_LOOP_SIDE_CEILING = "turn_limit_reached"

#: The one ending that is not a failure, and so never reaches the error map.
THE_SUCCESS = "finished_normally"


def _recorded_error(stop_reason: str) -> str:
    """What the runner writes for an ending, through the real map."""
    return ERROR_TYPE_FOR_A_CONVERSATION_THAT_STOPPED.get(stop_reason, THE_DEFAULT)


# ── the map covers every ending, or says it does not ──────────────────────


def test_every_ending_is_either_mapped_or_knowingly_unnamed():
    """The check that would have caught this when the ending was added.

    ``turn_limit_reached`` did not arrive with a decision to leave it unnamed;
    it arrived and nothing noticed. Either half of this union is a place
    somebody has to write something, which is the whole difference.

    ``finished_normally`` is excluded rather than classified: the map is only
    consulted for a conversation that never committed an answer, so a success
    has no error type to be given and is not a fall-through.
    """
    every_failure = {reason.value for reason in StopReason} - {THE_SUCCESS}
    accounted_for = (
        set(ERROR_TYPE_FOR_A_CONVERSATION_THAT_STOPPED)
        | set(STOP_REASONS_WITH_NO_ERROR_TYPE_TO_NAME_THEM)
    )
    assert every_failure - accounted_for == set(), (
        "a conversation can now end in a way nobody has classified; either map "
        "it to a contract error type or add it to the unnamed set with a reason"
    )


def test_the_success_ending_never_reaches_the_error_map():
    """Excluding it above is only safe if the runner really does not map it."""
    assert THE_SUCCESS not in ERROR_TYPE_FOR_A_CONVERSATION_THAT_STOPPED
    assert THE_SUCCESS not in STOP_REASONS_WITH_NO_ERROR_TYPE_TO_NAME_THEM
    assert not StopReason.FINISHED_NORMALLY.is_a_limit


def test_the_unnamed_set_holds_no_ending_that_does_not_exist():
    """A stale entry would make the union above pass while covering nothing."""
    every_ending = {reason.value for reason in StopReason}
    assert STOP_REASONS_WITH_NO_ERROR_TYPE_TO_NAME_THEM <= every_ending


def test_an_ending_is_not_both_named_and_unnamed():
    assert not (
        set(ERROR_TYPE_FOR_A_CONVERSATION_THAT_STOPPED)
        & set(STOP_REASONS_WITH_NO_ERROR_TYPE_TO_NAME_THEM)
    )


def test_the_turn_ceiling_is_among_the_unnamed():
    """Stated directly, so the finding cannot be lost in a set operation."""
    assert THE_LOOP_SIDE_CEILING in STOP_REASONS_WITH_NO_ERROR_TYPE_TO_NAME_THEM
    assert THE_LOOP_SIDE_CEILING not in ERROR_TYPE_FOR_A_CONVERSATION_THAT_STOPPED
    assert _recorded_error(THE_LOOP_SIDE_CEILING) == THE_DEFAULT


def test_four_of_the_six_unnamed_endings_are_ceilings_not_a_silent_model():
    """``finalize_not_called`` is accurate for exactly one of the six.

    ``model_reply_unusable`` is this harness failing to read a reply, which is
    a defect here rather than a model that declined to answer.
    """
    from core.agentic_v2_conversation import _LIMIT_REASONS

    limits = {reason.value for reason in _LIMIT_REASONS}
    are_ceilings = STOP_REASONS_WITH_NO_ERROR_TYPE_TO_NAME_THEM & limits
    assert are_ceilings == {
        "turn_limit_reached",
        "cost_limit_reached",
        "writing_limit_reached",
        "repeated_request",
    }
    assert "model_stopped_without_finishing" not in limits


# ── the two ceilings are not the same ceiling ─────────────────────────────


def test_the_ceiling_the_map_names_is_not_one_the_loop_can_raise():
    """``tool_call_limit_reached`` needs a desk to report it about itself.

    Asserted on the loop's source because the claim is an absence: there is no
    branch that ends a conversation this way. It is reachable only through
    ``_ENDS_THE_RUN``, when a tool result carries ``tool_budget_exhausted``.
    """
    from core import agentic_v2_conversation

    loop = inspect.getsource(agentic_v2_conversation.run_model_conversation)
    assert "TOOL_CALL_LIMIT_REACHED" not in loop
    assert "TURN_LIMIT_REACHED" in loop

    assert agentic_v2_conversation._ENDS_THE_RUN["tool_budget_exhausted"] is (
        StopReason.TOOL_CALL_LIMIT_REACHED
    )


def test_the_separation_tests_exercise_the_ceiling_that_is_mapped():
    """Why a green suite did not catch this.

    ``read_outcome`` is given an error string that a runner produces. Handed
    ``tool_budget_exhausted`` it labels it faithfully -- and that string is what
    the *mapped* ceiling produces. The unmapped one never arrives as anything
    but ``finalize_not_called``, so no assertion on ``ending_label`` can see it.
    """
    from core.agentic_v2_outcome import read_outcome

    failed = {
        "success": False,
        "text": "",
        "deliverable_text": "",
        "files": [],
        "error": ERROR_TYPE_FOR_A_CONVERSATION_THAT_STOPPED[THE_DESK_SIDE_CEILING],
    }
    assert ending_label(read_outcome("desk_ceiling", failed)) == "tool_budget_exhausted"

    ran_out_of_turns = dict(failed, error=_recorded_error(THE_LOOP_SIDE_CEILING))
    assert ending_label(read_outcome("turn_ceiling", ran_out_of_turns)) == (
        FINALIZE_NOT_CALLED
    )


# ── the real loop, at the real ceilings ───────────────────────────────────


class _Chosen:
    tool_calls_per_attempt = 3
    max_output_tokens_per_turn = 512


@pytest.fixture
def ceilings():
    """The ceilings a trial task really runs under, not invented ones."""
    return ceilings_from(
        {"fixed_settings": {"per_task_timeout_seconds": 600.0}}, _Chosen()
    )


def _keeps_working(ceilings) -> ConversationOutcome:
    """A model that asks for a different tool call every turn and never stops.

    Every turn's arguments differ, or the loop would stop it at
    ``max_repeats_of_one_request`` -- a different unmapped ending, and not the
    one under test.

    Takes ``ceilings`` rather than ``LoopLimits`` because ``LoopLimits`` carries
    a :class:`StageOneBudget` that accumulates. Two conversations sharing one
    would put the second under the first one's spending, which is what
    ``fresh_limits`` is named for.
    """
    return run_model_conversation(
        task_prompt="keep working",
        voice=ScriptedVoice(
            replies=[
                AskForTool(
                    call_id=f"c{n}", tool_name="browser_run", arguments={"step": n}
                )
                for n in range(1, 12)
            ]
        ),
        desk=ScriptedToolDesk(
            answers=[ToolOutcome.worked(step=n) for n in range(1, 12)]
        ),
        limits=ceilings.fresh_limits(),
    )


def test_the_ceiling_a_working_task_reaches_is_the_turn_ceiling(ceilings):
    """``max_model_turns`` and ``max_model_calls`` are both ``calls + 1``.

    The turn check runs before the budget check, so a model that keeps working
    stops on turns. This is why the unmapped ceiling is the reachable one.
    """
    assert ceilings.max_model_turns == _Chosen.tool_calls_per_attempt + 1
    assert ceilings.max_model_calls == _Chosen.tool_calls_per_attempt + 1

    assert _keeps_working(ceilings).stop_reason is StopReason.TURN_LIMIT_REACHED


def test_running_out_of_turns_and_going_quiet_record_the_same_error(ceilings):
    """The pair the plan promises to separate, run rather than described."""
    worked_to_the_end = _keeps_working(ceilings)
    went_quiet = run_model_conversation(
        task_prompt="keep working",
        voice=ScriptedVoice(replies=[GaveUp(note="not sure how")]),
        desk=ScriptedToolDesk(),
        limits=ceilings.fresh_limits(),
    )

    assert worked_to_the_end.stop_reason is StopReason.TURN_LIMIT_REACHED
    assert went_quiet.stop_reason is StopReason.MODEL_STOPPED_WITHOUT_FINISHING
    assert worked_to_the_end.stop_reason.is_a_limit
    assert not went_quiet.stop_reason.is_a_limit

    # Different endings, different severity, one recorded word.
    assert (
        _recorded_error(worked_to_the_end.stop_reason.value)
        == _recorded_error(went_quiet.stop_reason.value)
        == THE_DEFAULT
    )


def test_the_exact_reason_survives_in_the_conversation_record(ceilings):
    """The bound on this. Read this field, not the summary one.

    ``ConversationOutcome.as_dict`` is what the ledger stores per attempt and
    what ``run_agentic_v2_stage.py`` writes into the run record under
    ``conversations``. It keeps both the reason and the sentence explaining it.
    """
    recorded = _keeps_working(ceilings).as_dict()
    assert recorded["stop_reason"] == THE_LOOP_SIDE_CEILING
    assert str(ceilings.max_model_turns) in recorded["detail"]


# ── the prose that said otherwise ─────────────────────────────────────────


def test_the_outcome_module_no_longer_claims_the_turn_ceiling_is_separated():
    """Asserted as an absence: the claim was specific and specifically wrong."""
    source = inspect.getsource(agentic_v2_outcome)
    assert "get counted separately" not in source
    assert "covers a turn ceiling, a wall clock and a broken desk" not in source


def test_both_corrected_places_send_the_reader_to_the_field_that_answers():
    for source in (
        inspect.getsource(agentic_v2_outcome),
        inspect.getsource(agentic_v2_runner),
    ):
        assert "stop_reason" in source


def test_the_runner_names_the_unnamed_endings_rather_than_summarising_them():
    """The old comment paraphrased two of the six and named none of them."""
    source = inspect.getsource(agentic_v2_runner)
    for unnamed in STOP_REASONS_WITH_NO_ERROR_TYPE_TO_NAME_THEM:
        assert unnamed in source, (
            f"{unnamed} falls through to {THE_DEFAULT} and the module never "
            "says so"
        )


def test_the_finalize_ended_first_constant_still_means_what_it_says():
    """The correction is to the comment; the value is load-bearing elsewhere."""
    assert FINALIZE_ENDED_FIRST == "ended_before_it_could_be"
    assert FINALIZE_NOT_CALLED == "not_called"
