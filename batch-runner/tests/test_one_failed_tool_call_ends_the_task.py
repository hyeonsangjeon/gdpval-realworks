"""The registered condition, run rather than asserted in prose.

``core.agentic_v2_preregistration`` declares
``one_failed_tool_call_ends_the_task``: the first tool result that is not ``ok``
ends the task, the model is told nothing, and it is not asked for another turn.
Three other places in this codebase said the opposite -- that a refusal is handed
back and the run carries on -- and they said it for long enough to have a metrics
column built on top of them. Prose could not settle that. This file runs it.

What it pins, in both of the runner's modes:

* a refused call is the **last** tool event in the trace, so a task gets one
  tool mistake and no second chance;
* the *run record* names the refusal correctly, which is what the report reads;
* the *conversation outcome* does not -- it says ``tool_desk_broke``, the same
  word a genuinely broken desk gets, which is why the refusal column exists at
  all;
* the enforcing rule is the trace schema, not the loop's table of endings, so
  it cannot be lifted by editing that table.

Nothing here calls a model, reaches a network, or spends anything: the voice is
scripted and the backend is the offline fixture.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core.agentic_v2_conversation import (  # noqa: E402
    AskForTool,
    ScriptedVoice,
    StopReason,
    ends_the_run,
)
from core.agentic_v2_conversation_runner import (  # noqa: E402
    PerTaskCeilings,
    TaskConversations,
    conversation_seam,
)
from core.agentic_v2_fixture_backend import AgenticV2FixtureBackend  # noqa: E402
from core.agentic_v2_outcome import refusals_the_desk_gave  # noqa: E402
from core.agentic_v2_preregistration import _run_conditions  # noqa: E402
from core.agentic_v2_provenance import (  # noqa: E402
    EVENT_TOOL_PUBLIC,
    verify_agentic_v2_failure_result,
)
from core.agentic_v2_run_driver import _tool_calls_of  # noqa: E402
from core.agentic_v2_runner import AgenticV2ScriptedRunner  # noqa: E402

PROFILE = {
    "tool_contract_version": "2.0",
    "policy_profile_id": "offline-full-v1",
    "foundation_only": True,
}

CEILINGS = PerTaskCeilings(
    max_model_turns=8,
    max_written_tokens_per_turn=4096,
    max_seconds=60.0,
    max_model_calls=8,
    max_input_tokens=100_000,
    max_output_tokens=20_000,
    max_repeats_of_one_request=2,
)

#: What the offline profile will not grant, and the reason it gives.
#: ``browser_run`` search is the one that mattered: it is what three of the five
#: tasks in the first paid stage ended on.
REFUSED_SEARCH = AskForTool(
    call_id="b-1",
    tool_name="browser_run",
    arguments={"operation": "search", "query": "three comparable sites"},
    why="look it up",
)

WRITE = AskForTool(
    call_id="w-1",
    tool_name="workspace_apply",
    arguments={
        "operation": "write",
        "path": "report.txt",
        "content": "wrote it from what I already knew",
    },
    why="write it anyway",
)

FINALIZE = AskForTool(
    call_id="f-1",
    tool_name="finalize",
    arguments={"deliverables": ["report.txt"], "summary": "done"},
    why="hand it in",
)

REFUSAL = "capability_unavailable"


def _as_scripted(ask: AskForTool) -> dict:
    return {
        "call_id": ask.call_id,
        "name": ask.tool_name,
        "arguments": dict(ask.arguments),
    }


@pytest.fixture
def refused_conversation(tmp_path):
    """A model that is refused, tries something else, and hands in anyway.

    Scripted as three replies. The interesting number is how many of them are
    ever read.
    """
    held = TaskConversations(CEILINGS)
    voice = ScriptedVoice(replies=[REFUSED_SEARCH, WRITE, FINALIZE])
    runner = AgenticV2ScriptedRunner(
        backend_factory=lambda **kwargs: AgenticV2FixtureBackend(
            root=tmp_path, **kwargs
        ),
        conversation=conversation_seam(
            voice=voice,
            limits=held.limits_for("task-1", 1),
            on_outcome=lambda outcome: held.record("task-1", 1, outcome),
        ),
        profile=PROFILE,
    )
    result = runner.run("Write the report", task_id="task-1")
    return result, held.outcome_of("task-1", 1), voice


@pytest.fixture
def refused_scripted(tmp_path):
    """The same three calls with no model in the loop at all."""
    return AgenticV2ScriptedRunner(
        backend_factory=lambda **kwargs: AgenticV2FixtureBackend(
            root=tmp_path, **kwargs
        ),
        scripted_calls=[_as_scripted(REFUSED_SEARCH), _as_scripted(WRITE),
                        _as_scripted(FINALIZE)],
        profile=PROFILE,
    ).run("Write the report", task_id="task-1")


# ---------------------------------------------------------------------------
# The condition itself
# ---------------------------------------------------------------------------


def test_the_run_ends_on_the_refusal_and_the_model_is_not_asked_again(
    refused_conversation,
):
    """Two replies were scripted after the refusal and neither was read.

    This is the whole finding. A model that would have recovered never got the
    chance to, so no run under this schema is evidence about whether it would
    have.
    """
    result, _, voice = refused_conversation

    assert result["success"] is False
    assert result["error"] == REFUSAL
    assert len(voice.replies) == 3, (
        "the voice still holds every reply it was given, so exactly one turn "
        "was taken"
    )


def test_a_scripted_run_stops_in_the_same_place(refused_scripted):
    """No model, same ending. It is the dispatcher, not the conversation loop."""
    assert refused_scripted["success"] is False
    assert refused_scripted["error"] == REFUSAL


@pytest.mark.parametrize("fixture", ["refused_conversation", "refused_scripted"])
def test_the_refused_call_is_the_last_tool_event_in_the_trace(fixture, request):
    """One tool mistake per task, as a property of the record.

    The later ``workspace_apply`` and ``finalize`` are absent from the trace
    entirely -- not recorded as skipped, not recorded as failed. They did not
    happen.
    """
    got = request.getfixturevalue(fixture)
    result = got[0] if isinstance(got, tuple) else got
    verify_agentic_v2_failure_result(result)

    calls = _tool_calls_of(result)
    assert [call["tool_name"] for call in calls] == ["browser_run"]
    assert calls[-1]["ok"] is False
    assert calls[-1]["error_type"] == REFUSAL

    events = result["agentic_v2"]["public_trace"]["events"]
    kinds = [event["kind"] for event in events]
    assert kinds == ["started", EVENT_TOOL_PUBLIC, "failure"]


def test_the_schema_is_what_forbids_a_second_call_not_the_loops_table(
    refused_conversation,
):
    """So the condition cannot be lifted by editing ``_ENDS_THE_RUN``.

    ``capability_unavailable`` is deliberately *not* one of the reasons the
    conversation loop ends on -- ``ends_the_run`` says so -- and the run ends on
    it regardless. Anyone reading that table as the answer to "what stops a
    task" will get this wrong, which is what happened.
    """
    result, _, _ = refused_conversation

    assert ends_the_run(REFUSAL) is False
    assert result["error"] == REFUSAL


# ---------------------------------------------------------------------------
# Why the refusal column exists, given that the refusal is the ending
# ---------------------------------------------------------------------------


def test_the_loop_calls_a_refusal_a_broken_desk(refused_conversation):
    """The reason a separate column is still worth carrying.

    The conversation outcome is what a reader classifying failures reaches for
    first, and it files "the desk was working and said no" under the same word
    as "the desk fell over". The run record does not, and the report is built
    from the run record.
    """
    result, outcome, _ = refused_conversation

    assert outcome.stop_reason is StopReason.TOOL_DESK_BROKE
    assert result["error"] == REFUSAL, (
        "the run record keeps the real cause; agentic_v2_runner overrides the "
        "loop's verdict with the desk's own"
    )


def test_the_refusal_is_counted_and_is_the_same_event_as_the_ending(
    refused_conversation,
):
    """Counted, and never added to the ending it duplicates."""
    result, _, _ = refused_conversation
    refusals = refusals_the_desk_gave(_tool_calls_of(result))

    assert refusals == (REFUSAL,)
    assert refusals[0] == result["error"], (
        "one event, two fields; summing them would double-count every refused "
        "task"
    )


def test_a_broken_desk_is_not_counted_as_a_refusal():
    """The distinction the column is for, on the two reasons side by side."""
    assert ends_the_run("compute_backend_error") is True
    assert ends_the_run(REFUSAL) is False

    both = [
        {"ok": False, "error_type": REFUSAL},
        {"ok": False, "error_type": "compute_backend_error"},
    ]
    assert refusals_the_desk_gave(both) == (REFUSAL,)


# ---------------------------------------------------------------------------
# The condition is registered, and says the same thing
# ---------------------------------------------------------------------------


def test_the_preregistration_already_declares_this(refused_conversation):
    """The one place that had it right, held to what the runner does.

    It was written down as a condition of the run rather than fixed before it,
    which is the correct call -- lifting it changes what a trace may contain.
    The point of checking it here is that a registered condition which stops
    being true is worse than no registration at all.
    """
    registered = _run_conditions()["one_failed_tool_call_ends_the_task"]
    result, outcome, voice = refused_conversation

    assert registered["holds"] is True
    assert registered["the_model_is_told"] == (
        "nothing, and is not asked for another turn"
    )
    assert len(voice.replies) == 3, "and indeed it was not asked again"
    assert registered["recorded_as"] == (
        f"stop_reason {StopReason.TOOL_DESK_BROKE.value}"
    )
    assert outcome.stop_reason is StopReason.TOOL_DESK_BROKE
    assert "dispatch_one" in registered["comes_from"]
    assert result["error"] == REFUSAL
