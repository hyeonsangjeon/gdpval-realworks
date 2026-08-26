"""Every way the Agentic Sandbox V2 model conversation can end, fixed in place.

The loop is worth having only if it stops when it should. These tests spend
nothing: the model is a stand-in that says what it was told to say, and the
tool desk is either a stand-in or the real dispatcher with commands still shut.
"""

from __future__ import annotations

import ast
import json
import pathlib

import pytest

from core.agentic_v2_contract import (
    TOOL_NAMES,
    AgenticV2Lifecycle,
    AgenticV2Profile,
    LifecycleState,
)
from core.agentic_v2_conversation import (
    MOST_CHARACTERS_IN_A_STATED_REASON,
    AskForTool,
    ConversationOutcome,
    DispatcherToolDesk,
    GaveUp,
    LoopLimits,
    LoopStep,
    ModelRequest,
    NoModelVoiceAvailable,
    ScriptedToolDesk,
    ScriptedVoice,
    StopReason,
    ToolOutcome,
    real_model_voice,
    run_model_conversation,
)
from core.agentic_v2_fixture_backend import AgenticV2FixtureBackend
from core.agentic_v2_stage_one_budget import StageOneBudget
from core.agentic_v2_tools import AgenticV2ToolDispatcher


PROFILE = {
    "tool_contract_version": "2.0",
    "policy_profile_id": "offline-full-v1",
    "foundation_only": True,
}


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
        input_tokens=100,
        output_tokens=20,
    )


def look_around(call_id: str = "call-1") -> AskForTool:
    return ask(call_id, "capabilities_query", kind="commands")


def run_a_command(call_id: str = "call-1") -> AskForTool:
    return ask(
        call_id,
        "exec_run",
        argv=["python", "-c", "print(1)"],
        cwd=".",
        timeout_seconds=60,
    )


def write_a_file(call_id: str = "call-2", path: str = "report.txt") -> AskForTool:
    return ask(
        call_id, "workspace_apply", operation="write", path=path, content="hello"
    )


def commit(call_id: str = "call-3", path: str = "report.txt") -> AskForTool:
    return ask(call_id, "finalize", deliverables=[path], summary="done")


def a_run(voice, desk, **limit_changes) -> ConversationOutcome:
    return run_model_conversation(
        task_prompt="write a short report",
        voice=voice,
        desk=desk,
        limits=limits(**limit_changes),
    )


# ---------------------------------------------------------------------------
# The behaviour stage one exists to measure
# ---------------------------------------------------------------------------


def test_the_model_is_asked_again_with_the_failure_in_front_of_it():
    """The one thing stage one is for: react to a refusal, do not stop at it."""
    voice = ScriptedVoice(replies=[
        run_a_command("call-1"),
        write_a_file("call-2"),
        commit("call-3"),
    ])
    desk = ScriptedToolDesk(answers=[
        ToolOutcome.refused("capability_unavailable"),
        ToolOutcome.worked(bytes_written=5),
        ToolOutcome.committed({"success": True, "text": "done", "files": []}),
    ])

    outcome = a_run(voice, desk)

    assert outcome.stop_reason is StopReason.FINISHED_NORMALLY
    assert outcome.produced_an_answer is True
    second_request = voice.requests_seen[1]
    assert second_request.history[0].error_type == "capability_unavailable"
    assert second_request.history[0].ok is False
    assert second_request.turn == 2


def test_a_refusal_the_model_could_work_around_does_not_end_the_run():
    voice = ScriptedVoice(replies=[
        write_a_file("call-1", path="nowhere/report.txt"),
        write_a_file("call-2"),
        commit("call-3"),
    ])
    desk = ScriptedToolDesk(answers=[
        ToolOutcome.refused("path_not_directory"),
        ToolOutcome.worked(bytes_written=5),
        ToolOutcome.committed({"success": True, "text": "done", "files": []}),
    ])

    outcome = a_run(voice, desk)

    assert outcome.stop_reason is StopReason.FINISHED_NORMALLY
    assert len(outcome.turns) == 3


def test_asking_to_run_a_command_is_refused_and_the_command_never_runs():
    """The unsupported capability, end to end, against the real dispatcher."""
    voice = ScriptedVoice(replies=[run_a_command(), GaveUp(note="nothing left")])
    desk = ScriptedToolDesk(answers=[ToolOutcome.refused("capability_unavailable")])

    outcome = a_run(voice, desk)

    assert outcome.turns[0].tool_name == "exec_run"
    assert outcome.turns[0].ok is False
    assert outcome.turns[0].error_type == "capability_unavailable"
    assert outcome.stop_reason is StopReason.MODEL_STOPPED_WITHOUT_FINISHING
    assert outcome.produced_an_answer is False
    assert outcome.final_result is None


# ---------------------------------------------------------------------------
# The ceilings
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "absent, expected_phrase",
    [
        ("max_model_turns", "how many times the model may be asked"),
        ("max_written_tokens_per_turn", "how much one reply may run to"),
        ("max_seconds", "how long the whole run may take"),
        ("budget", "what this run may cost"),
        ("max_repeats_of_one_request", "how often the same request"),
    ],
)
def test_a_missing_ceiling_refuses_the_run_before_anything_is_asked(
    absent, expected_phrase
):
    """Missing is treated as exceeded. A default would only ever be consulted
    on the run where somebody forgot, which is the run that must not go
    unbounded."""
    voice = ScriptedVoice(replies=[look_around()])
    desk = ScriptedToolDesk()

    outcome = a_run(voice, desk, **{absent: None})

    assert outcome.stop_reason is StopReason.LIMIT_MISSING
    assert expected_phrase in outcome.detail
    assert voice.requests_seen == []
    assert desk.calls == []


def test_every_missing_ceiling_is_named_at_once():
    outcome = run_model_conversation(
        task_prompt="anything",
        voice=ScriptedVoice(replies=[look_around()]),
        desk=ScriptedToolDesk(),
        limits=LoopLimits(),
    )

    assert outcome.stop_reason is StopReason.LIMIT_MISSING
    assert outcome.detail.count(";") == 4


@pytest.mark.parametrize("bad", [0, -1, True, "8", 8.5])
def test_a_ceiling_that_is_not_a_positive_whole_number_is_missing(bad):
    outcome = a_run(
        ScriptedVoice(replies=[look_around()]),
        ScriptedToolDesk(),
        max_model_turns=bad,
    )

    assert outcome.stop_reason is StopReason.LIMIT_MISSING


@pytest.mark.parametrize("bad", [0, -1.0, True, "60"])
def test_a_time_ceiling_that_is_not_a_positive_number_is_missing(bad):
    outcome = a_run(
        ScriptedVoice(replies=[look_around()]),
        ScriptedToolDesk(),
        max_seconds=bad,
    )

    assert outcome.stop_reason is StopReason.LIMIT_MISSING


def test_a_budget_that_is_not_a_budget_is_missing():
    outcome = a_run(
        ScriptedVoice(replies=[look_around()]),
        ScriptedToolDesk(),
        budget={"max_model_calls": 4},
    )

    assert outcome.stop_reason is StopReason.LIMIT_MISSING
    assert "what this run may cost" in outcome.detail


def test_the_run_stops_when_the_model_has_been_asked_all_the_times_allowed():
    voice = ScriptedVoice(replies=[look_around(f"call-{n}") for n in range(10)])
    desk = ScriptedToolDesk(
        answers=[ToolOutcome.worked(kinds=[str(n)]) for n in range(10)]
    )

    outcome = a_run(voice, desk, max_model_turns=3, max_repeats_of_one_request=99)

    assert outcome.stop_reason is StopReason.TURN_LIMIT_REACHED
    assert outcome.stop_reason.is_a_limit is True
    assert outcome.model_turns_used == 3
    assert len(voice.requests_seen) == 3
    assert "3 times, which is all the 3" in outcome.detail


def test_a_reply_longer_than_one_turn_allows_stops_the_run():
    voice = ScriptedVoice(replies=[
        AskForTool(
            call_id="call-1",
            tool_name="capabilities_query",
            arguments={"kind": "commands"},
            input_tokens=100,
            output_tokens=9000,
        )
    ])
    desk = ScriptedToolDesk()

    outcome = a_run(voice, desk, max_written_tokens_per_turn=2048)

    assert outcome.stop_reason is StopReason.WRITING_LIMIT_REACHED
    assert "9000 tokens in one turn" in outcome.detail
    assert desk.calls == []


def test_the_overlong_reply_is_still_charged_for_because_it_was_written():
    budget = a_budget()
    voice = ScriptedVoice(replies=[
        AskForTool(
            call_id="call-1",
            tool_name="capabilities_query",
            arguments={"kind": "commands"},
            input_tokens=700,
            output_tokens=9000,
        )
    ])

    outcome = a_run(
        voice, ScriptedToolDesk(), budget=budget, max_written_tokens_per_turn=2048
    )

    assert outcome.stop_reason is StopReason.WRITING_LIMIT_REACHED
    assert budget.output_tokens_used == 9000
    assert budget.input_tokens_used == 700


def test_the_run_stops_when_it_has_taken_all_the_time_it_was_allowed():
    ticks = iter([0.0, 0.0, 0.5, 9.0])
    voice = ScriptedVoice(replies=[look_around("call-1"), look_around("call-2")])
    desk = ScriptedToolDesk(answers=[ToolOutcome.worked(kinds=["a"])])

    outcome = run_model_conversation(
        task_prompt="anything",
        voice=voice,
        desk=desk,
        limits=limits(max_seconds=5.0),
        clock=lambda: next(ticks),
    )

    assert outcome.stop_reason is StopReason.TIME_LIMIT_REACHED
    assert "which is all the 5.000 it was allowed" in outcome.detail
    assert len(voice.requests_seen) == 1
    assert len(desk.calls) == 1


def test_running_out_of_time_between_the_reply_and_the_tool_stops_the_run():
    """The tool is not run once the clock has gone, even though it was asked
    for."""
    ticks = iter([0.0, 0.0, 9.0])
    voice = ScriptedVoice(replies=[look_around("call-1")])
    desk = ScriptedToolDesk(answers=[ToolOutcome.worked(kinds=["a"])])

    outcome = run_model_conversation(
        task_prompt="anything",
        voice=voice,
        desk=desk,
        limits=limits(max_seconds=5.0),
        clock=lambda: next(ticks),
    )

    assert outcome.stop_reason is StopReason.TIME_LIMIT_REACHED
    assert len(voice.requests_seen) == 1
    assert desk.calls == []


def test_the_run_stops_before_a_call_it_can_no_longer_afford():
    budget = a_budget(max_model_calls=2)
    voice = ScriptedVoice(replies=[look_around(f"call-{n}") for n in range(5)])
    desk = ScriptedToolDesk(
        answers=[ToolOutcome.worked(kinds=[str(n)]) for n in range(5)]
    )

    outcome = a_run(voice, desk, budget=budget, max_repeats_of_one_request=99)

    assert outcome.stop_reason is StopReason.COST_LIMIT_REACHED
    assert len(voice.requests_seen) == 2
    assert "all the 2 it was allowed" in outcome.detail


def test_a_single_reply_that_overspends_stops_the_run_rather_than_reporting_it():
    budget = a_budget(max_output_tokens=100)
    voice = ScriptedVoice(replies=[
        AskForTool(
            call_id="call-1",
            tool_name="capabilities_query",
            arguments={"kind": "commands"},
            input_tokens=10,
            output_tokens=90,
        ),
        AskForTool(
            call_id="call-2",
            tool_name="capabilities_query",
            arguments={"kind": "runtimes"},
            input_tokens=10,
            output_tokens=90,
        ),
    ])
    desk = ScriptedToolDesk(answers=[ToolOutcome.worked(kinds=["a"])])

    outcome = a_run(voice, desk, budget=budget)

    assert outcome.stop_reason is StopReason.COST_LIMIT_REACHED
    assert "180 tokens received against a limit of 100" in outcome.detail
    assert len(desk.calls) == 1


def test_the_cost_ceiling_is_checked_before_the_call_not_after_it():
    budget = a_budget(max_input_tokens=100)
    voice = ScriptedVoice(replies=[look_around("call-1"), look_around("call-2")])
    desk = ScriptedToolDesk(answers=[ToolOutcome.worked(kinds=["a"])])

    outcome = a_run(voice, desk, budget=budget)

    assert outcome.stop_reason is StopReason.COST_LIMIT_REACHED
    assert budget.model_calls_made == 1
    assert "already sent 100 tokens" in outcome.detail


# ---------------------------------------------------------------------------
# Going in circles
# ---------------------------------------------------------------------------


def test_asking_for_the_same_thing_over_and_over_stops_the_run():
    voice = ScriptedVoice(replies=[
        ask("call-1", "capabilities_query", kind="commands"),
        ask("call-2", "capabilities_query", kind="commands"),
        ask("call-3", "capabilities_query", kind="commands"),
    ])
    desk = ScriptedToolDesk(
        answers=[ToolOutcome.worked(kinds=["a"]) for _ in range(3)]
    )

    outcome = a_run(voice, desk, max_repeats_of_one_request=2)

    assert outcome.stop_reason is StopReason.REPEATED_REQUEST
    assert "going in circles" in outcome.detail
    assert len(desk.calls) == 2


def test_a_fresh_call_identifier_does_not_disguise_the_same_request():
    """Counted on what was asked, not on the label attached to it."""
    voice = ScriptedVoice(replies=[
        ask("first", "capabilities_query", kind="commands"),
        ask("second", "capabilities_query", kind="commands"),
    ])
    desk = ScriptedToolDesk(answers=[ToolOutcome.worked(kinds=["a"])])

    outcome = a_run(voice, desk, max_repeats_of_one_request=1)

    assert outcome.stop_reason is StopReason.REPEATED_REQUEST
    assert len(desk.calls) == 1


def test_different_arguments_are_not_a_repeat():
    voice = ScriptedVoice(replies=[
        ask("call-1", "capabilities_query", kind="commands"),
        ask("call-2", "capabilities_query", kind="runtimes"),
        commit("call-3"),
    ])
    desk = ScriptedToolDesk(answers=[
        ToolOutcome.worked(kinds=["a"]),
        ToolOutcome.worked(kinds=["b"]),
        ToolOutcome.committed({"success": True, "text": "done", "files": []}),
    ])

    outcome = a_run(voice, desk, max_repeats_of_one_request=1)

    assert outcome.stop_reason is StopReason.FINISHED_NORMALLY


def test_a_repeat_the_dispatcher_replayed_is_recorded_as_replayed():
    voice = ScriptedVoice(replies=[
        ask("call-1", "capabilities_query", kind="commands"),
        ask("call-1", "capabilities_query", kind="commands"),
        GaveUp(note="stuck"),
    ])
    desk = ScriptedToolDesk(answers=[
        ToolOutcome.worked(kinds=["a"]),
        ToolOutcome(ok=True, data={"kinds": ["a"]}, replayed=True),
    ])

    outcome = a_run(voice, desk, max_repeats_of_one_request=2)

    assert [record.replayed for record in outcome.turns] == [False, True]


# ---------------------------------------------------------------------------
# Cancellation
# ---------------------------------------------------------------------------


def test_a_run_asked_to_stop_never_asks_the_model():
    voice = ScriptedVoice(replies=[look_around()])
    desk = ScriptedToolDesk()

    outcome = run_model_conversation(
        task_prompt="anything",
        voice=voice,
        desk=desk,
        limits=limits(),
        cancel_requested=lambda: True,
    )

    assert outcome.stop_reason is StopReason.CANCELLED
    assert voice.requests_seen == []
    assert outcome.turns == ()


def test_a_run_asked_to_stop_mid_turn_does_not_run_the_tool():
    answers = iter([False, True])
    voice = ScriptedVoice(replies=[look_around()])
    desk = ScriptedToolDesk(answers=[ToolOutcome.worked(kinds=["a"])])

    outcome = run_model_conversation(
        task_prompt="anything",
        voice=voice,
        desk=desk,
        limits=limits(),
        cancel_requested=lambda: next(answers),
    )

    assert outcome.stop_reason is StopReason.CANCELLED
    assert len(voice.requests_seen) == 1
    assert desk.calls == []
    assert "before the tool was run" in outcome.detail


def test_a_tool_desk_reporting_cancellation_ends_the_run():
    voice = ScriptedVoice(replies=[look_around(), look_around("call-2")])
    desk = ScriptedToolDesk(answers=[ToolOutcome.refused("cancelled")])

    outcome = a_run(voice, desk)

    assert outcome.stop_reason is StopReason.CANCELLED
    assert len(voice.requests_seen) == 1


# ---------------------------------------------------------------------------
# Replies that cannot be used
# ---------------------------------------------------------------------------


class BrokenVoice:
    makes_paid_calls = False

    def __init__(self, reply):
        self.reply = reply
        self.times_asked = 0

    def next_turn(self, request: ModelRequest):
        self.times_asked += 1
        return self.reply


@pytest.mark.parametrize(
    "reply",
    [
        None,
        "capabilities_query",
        {"tool_name": "capabilities_query"},
        42,
        [],
    ],
)
def test_a_reply_that_is_not_a_reply_at_all_stops_the_run(reply):
    voice = BrokenVoice(reply)
    desk = ScriptedToolDesk()

    outcome = a_run(voice, desk)

    assert outcome.stop_reason is StopReason.MODEL_REPLY_UNUSABLE
    assert desk.calls == []


@pytest.mark.parametrize(
    "usage",
    [
        {"input_tokens": -1, "output_tokens": 10},
        {"input_tokens": 10, "output_tokens": -5},
        {"input_tokens": True, "output_tokens": 10},
        {"input_tokens": 1.5, "output_tokens": 10},
        {"input_tokens": "100", "output_tokens": 10},
    ],
)
def test_a_reply_that_does_not_say_what_it_used_stops_the_run(usage):
    voice = BrokenVoice(AskForTool(
        call_id="call-1",
        tool_name="capabilities_query",
        arguments={"kind": "commands"},
        **usage,
    ))

    outcome = a_run(voice, ScriptedToolDesk())

    assert outcome.stop_reason is StopReason.MODEL_REPLY_UNUSABLE
    assert "cannot be charged for" in outcome.detail


@pytest.mark.parametrize(
    "changes",
    [
        {"call_id": ""},
        {"call_id": None},
        {"call_id": 7},
        {"tool_name": ""},
        {"tool_name": None},
        {"tool_name": ["capabilities_query"]},
        {"arguments": None},
        {"arguments": "kind=commands"},
        {"arguments": [("kind", "commands")]},
        {"arguments": {1: "commands"}},
    ],
)
def test_a_tool_request_missing_what_it_needs_stops_the_run(changes):
    settings = {
        "call_id": "call-1",
        "tool_name": "capabilities_query",
        "arguments": {"kind": "commands"},
        "input_tokens": 10,
        "output_tokens": 10,
    }
    settings.update(changes)

    outcome = a_run(BrokenVoice(AskForTool(**settings)), ScriptedToolDesk())

    assert outcome.stop_reason is StopReason.MODEL_REPLY_UNUSABLE
    assert "not a usable tool request" in outcome.detail


def test_a_model_that_raises_stops_the_run_rather_than_the_process():
    class ExplodingVoice:
        makes_paid_calls = False

        def next_turn(self, request):
            raise TimeoutError("the model never answered")

    outcome = a_run(ExplodingVoice(), ScriptedToolDesk())

    assert outcome.stop_reason is StopReason.MODEL_REPLY_UNUSABLE
    assert "TimeoutError" in outcome.detail


def test_a_model_that_walks_away_is_not_recorded_as_a_success():
    voice = ScriptedVoice(replies=[GaveUp(note="I cannot do this")])

    outcome = a_run(voice, ScriptedToolDesk())

    assert outcome.stop_reason is StopReason.MODEL_STOPPED_WITHOUT_FINISHING
    assert outcome.produced_an_answer is False
    assert "I cannot do this" in outcome.detail


def test_a_model_that_runs_out_of_things_to_say_ends_the_run():
    voice = ScriptedVoice(replies=[])

    outcome = a_run(voice, ScriptedToolDesk())

    assert outcome.stop_reason is StopReason.MODEL_STOPPED_WITHOUT_FINISHING
    assert "ran out of written replies" in outcome.detail


# ---------------------------------------------------------------------------
# A tool desk that is not working
# ---------------------------------------------------------------------------


class BrokenDesk:
    def __init__(self, answer=None, raises=None):
        self.answer = answer
        self.raises = raises
        self.calls: list = []

    def run_one(self, *, call_id, tool_name, arguments):
        self.calls.append((call_id, tool_name, dict(arguments)))
        if self.raises is not None:
            raise self.raises
        return self.answer


def test_a_tool_desk_that_raises_stops_the_run():
    desk = BrokenDesk(raises=OSError("the workspace disappeared"))

    outcome = a_run(ScriptedVoice(replies=[look_around()]), desk)

    assert outcome.stop_reason is StopReason.TOOL_DESK_BROKE
    assert "OSError" in outcome.detail


@pytest.mark.parametrize("answer", [None, {"ok": True}, "ok", 1])
def test_a_tool_desk_answering_with_something_else_stops_the_run(answer):
    outcome = a_run(ScriptedVoice(replies=[look_around()]), BrokenDesk(answer))

    assert outcome.stop_reason is StopReason.TOOL_DESK_BROKE
    assert "not a tool outcome" in outcome.detail


@pytest.mark.parametrize(
    "error_type",
    [
        "compute_backend_error",
        "compute_cleanup_failed",
        "compute_start_failed",
        "fixture_backend_error",
        "invalid_backend_result",
        "invalid_backend_state",
        "invalid_lifecycle_transition",
        "invalid_result_envelope",
        "runner_internal_error",
        "substrate_manifest_missing",
    ],
)
def test_a_broken_desk_is_not_something_the_model_is_asked_to_work_around(
    error_type,
):
    voice = ScriptedVoice(replies=[look_around(), look_around("call-2")])
    desk = ScriptedToolDesk(answers=[ToolOutcome.refused(error_type)])

    outcome = a_run(voice, desk)

    assert outcome.stop_reason is StopReason.TOOL_DESK_BROKE
    assert len(voice.requests_seen) == 1


def test_a_committed_answer_with_nothing_in_it_is_refused():
    voice = ScriptedVoice(replies=[commit("call-1")])
    desk = ScriptedToolDesk(answers=[ToolOutcome(ok=True, finished=True)])

    outcome = a_run(voice, desk)

    assert outcome.stop_reason is StopReason.TOOL_DESK_BROKE
    assert "no answer" in outcome.detail
    assert outcome.final_result is None


def test_the_desk_running_out_of_its_own_call_budget_ends_the_run():
    voice = ScriptedVoice(replies=[look_around(), look_around("call-2")])
    desk = ScriptedToolDesk(answers=[ToolOutcome.refused("tool_budget_exhausted")])

    outcome = a_run(voice, desk)

    assert outcome.stop_reason is StopReason.TOOL_CALL_LIMIT_REACHED
    assert outcome.stop_reason.is_a_limit is True


# ---------------------------------------------------------------------------
# Nothing paid, nothing switched on, nothing swapped out
# ---------------------------------------------------------------------------


def test_there_is_no_way_to_reach_a_real_model():
    with pytest.raises(NoModelVoiceAvailable) as raised:
        real_model_voice()

    assert "no amount has been approved" in str(raised.value)


def test_a_model_that_would_be_charged_for_is_refused_before_being_asked():
    voice = ScriptedVoice(replies=[look_around()], makes_paid_calls=True)

    outcome = a_run(voice, ScriptedToolDesk())

    assert outcome.stop_reason is StopReason.PAID_CALL_REFUSED
    assert voice.requests_seen == []


def test_a_model_that_does_not_say_whether_it_is_paid_is_refused():
    """Fail shut. A voice that forgot to declare itself is treated as paid."""

    class SilentVoice:
        def next_turn(self, request):  # pragma: no cover - never reached
            raise AssertionError("the loop must not ask an undeclared model")

    outcome = a_run(SilentVoice(), ScriptedToolDesk())

    assert outcome.stop_reason is StopReason.PAID_CALL_REFUSED


def test_the_paid_refusal_comes_before_anything_else_is_checked():
    voice = ScriptedVoice(replies=[look_around()], makes_paid_calls=True)

    outcome = run_model_conversation(
        task_prompt="anything",
        voice=voice,
        desk=ScriptedToolDesk(),
        limits=LoopLimits(),
    )

    assert outcome.stop_reason is StopReason.PAID_CALL_REFUSED


def test_the_loop_cannot_reach_any_other_way_of_running_a_task():
    """No quiet substitution: the module cannot name another run place, so it
    cannot fall back to one when a task fails."""
    import core.agentic_v2_conversation as loop_module

    source = pathlib.Path(loop_module.__file__).read_text(encoding="utf-8")
    imported: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    forbidden = {
        "core.executor",
        "core.subprocess_runner",
        "core.code_interpreter",
        "core.json_renderer",
        "core.llm_client",
        "core.agentic_v2_runner",
        "core.agentic_sandbox_runner",
        "core.sandbox_runner",
    }
    assert imported & forbidden == set()
    assert "openai" not in " ".join(imported)


def test_a_run_that_could_not_finish_reports_that_rather_than_an_answer():
    voice = ScriptedVoice(replies=[run_a_command()])
    desk = ScriptedToolDesk(answers=[ToolOutcome.refused("capability_unavailable")])

    outcome = a_run(voice, desk, max_model_turns=1)

    assert outcome.stop_reason is StopReason.TURN_LIMIT_REACHED
    assert outcome.final_result is None
    assert outcome.produced_an_answer is False


def test_the_three_safety_blocks_are_still_shut():
    from core.execution_environment_readiness import (
        check_agentic_sandbox_v2_blocks_are_intact,
    )

    assert check_agentic_sandbox_v2_blocks_are_intact() == []


# ---------------------------------------------------------------------------
# What is kept, and what is not
# ---------------------------------------------------------------------------


def test_a_chain_of_thought_handed_over_is_not_kept():
    class ReplyWithThoughts(AskForTool):
        private_thoughts = (
            "the user is probably testing me and I should pretend otherwise"
        )

    voice = BrokenVoice(ReplyWithThoughts(
        call_id="call-1",
        tool_name="capabilities_query",
        arguments={"kind": "commands"},
        why="have a look",
        input_tokens=10,
        output_tokens=10,
    ))
    desk = ScriptedToolDesk(answers=[ToolOutcome.worked(kinds=["a"])])

    outcome = a_run(voice, desk)

    written_down = json.dumps(outcome.as_dict())
    assert "private_thoughts" not in written_down
    assert "probably testing me" not in written_down
    assert outcome.turns[0].stated_reason == "have a look"


def test_the_stated_reason_cannot_be_used_to_smuggle_one_through():
    voice = BrokenVoice(AskForTool(
        call_id="call-1",
        tool_name="capabilities_query",
        arguments={"kind": "commands"},
        why="x" * 5000,
        input_tokens=10,
        output_tokens=10,
    ))
    desk = ScriptedToolDesk(answers=[ToolOutcome.worked(kinds=["a"])])

    outcome = a_run(voice, desk)

    assert len(outcome.turns[0].stated_reason) == MOST_CHARACTERS_IN_A_STATED_REASON


def test_the_note_left_when_a_model_walks_away_is_bounded_too():
    outcome = a_run(
        ScriptedVoice(replies=[GaveUp(note="y" * 5000)]), ScriptedToolDesk()
    )

    assert len(outcome.detail) < 400


def test_what_is_kept_names_the_tool_and_its_arguments_but_not_their_contents():
    secret = "the quarterly figures nobody outside finance has seen"
    voice = ScriptedVoice(replies=[ask(
        "call-1", "workspace_apply", operation="write", path="a.txt",
        content=secret,
    )])
    desk = ScriptedToolDesk(answers=[ToolOutcome.worked(bytes_written=len(secret))])

    outcome = a_run(voice, desk)

    record = outcome.turns[0]
    assert record.tool_name == "workspace_apply"
    assert record.argument_names == ("content", "operation", "path")
    assert secret not in json.dumps(outcome.as_dict())


def test_the_model_is_shown_the_contents_even_though_they_are_not_kept():
    """The two are different on purpose: a model that cannot see the result
    cannot react to it."""
    voice = ScriptedVoice(replies=[
        look_around("call-1"), look_around("call-2"), GaveUp(note="enough")
    ])
    desk = ScriptedToolDesk(answers=[ToolOutcome.worked(kinds=["python", "bash"])])

    a_run(voice, desk, max_repeats_of_one_request=2)

    assert voice.requests_seen[1].history[0].data == {"kinds": ["python", "bash"]}


def test_every_point_the_run_passed_through_is_written_down_in_order():
    voice = ScriptedVoice(replies=[
        run_a_command("call-1"), write_a_file("call-2"), commit("call-3")
    ])
    desk = ScriptedToolDesk(answers=[
        ToolOutcome.refused("capability_unavailable"),
        ToolOutcome.worked(bytes_written=5),
        ToolOutcome.committed({"success": True, "text": "done", "files": []}),
    ])

    outcome = a_run(voice, desk)

    steps = [event.step for event in outcome.events]
    assert steps[:5] == [
        LoopStep.MODEL_ASKED,
        LoopStep.MODEL_REPLIED,
        LoopStep.TOOL_REQUESTED,
        LoopStep.TOOL_ANSWERED,
        LoopStep.NEXT_TURN,
    ]
    assert steps[-1] is LoopStep.STOPPED
    assert steps.count(LoopStep.NEXT_TURN) == 2
    assert outcome.events[-1].detail["stop_reason"] == "finished_normally"


def test_a_reply_that_arrived_is_written_down_even_when_it_ends_the_run():
    budget = a_budget(max_output_tokens=5)
    voice = ScriptedVoice(replies=[look_around()])

    outcome = a_run(voice, ScriptedToolDesk(), budget=budget)

    assert outcome.stop_reason is StopReason.COST_LIMIT_REACHED
    steps = [event.step for event in outcome.events]
    assert steps == [
        LoopStep.MODEL_ASKED, LoopStep.MODEL_REPLIED, LoopStep.STOPPED
    ]


def test_every_ending_is_named_and_only_one_of_them_is_an_answer():
    answers = [
        reason for reason in StopReason if reason.produced_an_answer
    ]
    assert answers == [StopReason.FINISHED_NORMALLY]
    assert StopReason.FINISHED_NORMALLY.is_a_limit is False
    assert StopReason.TOOL_DESK_BROKE.is_a_limit is False


def test_what_is_kept_can_be_written_out_as_it_stands():
    voice = ScriptedVoice(replies=[look_around(), commit("call-2")])
    desk = ScriptedToolDesk(answers=[
        ToolOutcome.worked(kinds=["a"]),
        ToolOutcome.committed({"success": True, "text": "done", "files": []}),
    ])

    outcome = a_run(voice, desk)
    written = json.loads(json.dumps(outcome.as_dict()))

    assert written["stop_reason"] == "finished_normally"
    assert written["model_turns_used"] == 2
    assert len(written["turns"]) == 2
    assert written["budget_after"]["model_calls_made"] == 2


# ---------------------------------------------------------------------------
# Against the real dispatcher, with commands still shut
# ---------------------------------------------------------------------------


def a_real_desk(tmp_path, **changes) -> DispatcherToolDesk:
    backend = AgenticV2FixtureBackend(
        root=tmp_path, profile=AgenticV2Profile.from_mapping(PROFILE)
    )
    settings = {"max_total_calls": 8}
    settings.update(changes)
    return DispatcherToolDesk(AgenticV2ToolDispatcher(
        backend, AgenticV2Lifecycle(LifecycleState.ACTIVE), **settings
    ))


def test_the_real_dispatcher_still_refuses_to_run_a_command(tmp_path):
    voice = ScriptedVoice(replies=[run_a_command(), GaveUp(note="nothing else")])

    outcome = a_run(voice, a_real_desk(tmp_path))

    assert outcome.turns[0].error_type == "capability_unavailable"
    assert outcome.stop_reason is StopReason.MODEL_STOPPED_WITHOUT_FINISHING


def test_the_real_dispatcher_checks_the_arguments_it_is_given(tmp_path):
    voice = ScriptedVoice(replies=[
        ask("call-1", "capabilities_query", kind="nonsense"),
        GaveUp(note="that was wrong"),
    ])

    outcome = a_run(voice, a_real_desk(tmp_path))

    assert outcome.turns[0].error_type == "invalid_arguments"


def test_a_tool_the_contract_does_not_have_is_refused(tmp_path):
    voice = ScriptedVoice(replies=[
        ask("call-1", "delete_everything", path="/"),
        GaveUp(note="not allowed then"),
    ])

    outcome = a_run(voice, a_real_desk(tmp_path))

    assert outcome.turns[0].error_type == "unknown_tool"
    assert outcome.turns[0].ok is False


def test_the_run_stops_at_the_dispatchers_own_call_ceiling(tmp_path):
    """The second test section 9 of the specification asks for."""
    voice = ScriptedVoice(replies=[
        ask(f"call-{n}", "capabilities_query", kind=kind)
        for n, kind in enumerate(
            ["commands", "runtimes", "packages", "formats", "budgets"]
        )
    ])

    outcome = a_run(voice, a_real_desk(tmp_path, max_total_calls=2))

    assert outcome.stop_reason is StopReason.TOOL_CALL_LIMIT_REACHED
    assert len(outcome.turns) == 3
    assert [record.ok for record in outcome.turns] == [True, True, False]


def test_a_real_run_writes_a_file_and_commits_it(tmp_path):
    voice = ScriptedVoice(replies=[
        run_a_command("call-1"),
        write_a_file("call-2"),
        commit("call-3"),
    ])

    outcome = a_run(voice, a_real_desk(tmp_path))

    assert outcome.stop_reason is StopReason.FINISHED_NORMALLY
    assert outcome.final_result is not None
    assert outcome.final_result["success"] is True
    assert outcome.final_result["deliverable_text"] == "done"
    assert [file["filename"] for file in outcome.final_result["files"]] == [
        "report.txt"
    ]
    assert all(record.result_sha256 for record in outcome.turns)


def test_a_real_repeat_is_replayed_rather_than_run_twice(tmp_path):
    voice = ScriptedVoice(replies=[
        write_a_file("call-1"),
        write_a_file("call-1"),
        GaveUp(note="done poking"),
    ])

    outcome = a_run(voice, a_real_desk(tmp_path), max_repeats_of_one_request=2)

    assert [record.replayed for record in outcome.turns] == [False, True]
    assert outcome.turns[0].result_sha256 == outcome.turns[1].result_sha256


def test_the_tools_offered_are_the_ones_the_contract_publishes():
    voice = ScriptedVoice(replies=[GaveUp(note="just looking")])

    a_run(voice, ScriptedToolDesk())

    assert voice.requests_seen[0].tools_available == tuple(TOOL_NAMES)
