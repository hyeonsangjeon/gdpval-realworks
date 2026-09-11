"""The free stand-in that proves the path before anything is charged for it.

A paid run of 220 tasks is not the place to discover that the workspace was
empty, that the guide was never written, or that a finished task gets thrown
away by the verifier. All three of those were true at some point, all three
were found by this stand-in, and all three would have been paid for first.

So :class:`RehearsalVoice` is a voice in the same slot the Azure one occupies,
answering from a script instead of from a model. It works a real task against a
real backend on real staged bytes -- read the guide, list the workspace, write a
file, commit it -- and reports which of those four actually worked.

The tests here are about the two ways a stand-in like this becomes dangerous.
It must never be mistaken for a result: a file it wrote is not an answer, and a
grade over one would be a grade of this module's wording. And it must never be
mistaken for a measurement: no call was made, which is not the same as a call
that cost nothing, and the difference is the whole of what a cost record is
worth.
"""

from __future__ import annotations

import sys
from pathlib import Path

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core.agentic_v2_conversation import (  # noqa: E402
    AskForTool,
    GaveUp,
    ModelRequest,
    ToolExchange,
)
from core.agentic_v2_rehearsal_voice import (  # noqa: E402
    GUIDE_PATH,
    REHEARSAL_DELIVERABLE,
    RehearsalVoice,
    rehearsal_is_not_a_run,
)

PROMPT = "work this task"
TOOLS = ("workspace_apply", "exec_run", "finalize")


def _request(turn: int, history, *, turns_left: int = 8, prompt: str = PROMPT):
    return ModelRequest(
        turn=turn,
        task_prompt=prompt,
        tools_available=TOOLS,
        history=tuple(history),
        turns_left=turns_left,
    )


def _ok(operation: str, data: dict, *, tool_name: str = "workspace_apply"):
    return ToolExchange(
        call_id="c",
        tool_name=tool_name,
        arguments={"operation": operation},
        ok=True,
        data=data,
        error_type=None,
    )


def _not_ok(operation: str, error_type: str):
    return ToolExchange(
        call_id="c",
        tool_name="workspace_apply",
        arguments={"operation": operation},
        ok=False,
        data={},
        error_type=error_type,
    )


def _work_a_whole_task(voice: RehearsalVoice, *, prompt: str = PROMPT) -> list:
    """Drive one task end to end, answering each request as the backend would.

    Stops at ``finalize``, which is what ends a task in the real loop -- the
    voice is never asked for a turn after it.
    """
    replies = []
    history: list[ToolExchange] = []
    answers = {
        "read": _ok("read", {"content": "# Your input files\n"}),
        "list": _ok("list", {"entries": ["inputs", "notes.md"]}),
        "write": _ok("write", {}),
    }
    for turn in range(1, 6):
        reply = voice.next_turn(_request(turn, history, prompt=prompt))
        replies.append(reply)
        if not isinstance(reply, AskForTool) or reply.tool_name == "finalize":
            break
        history.append(answers[reply.arguments["operation"]])
    return replies


# ── what it does ──────────────────────────────────────────────────────────


def test_it_opens_the_guide_first_because_that_is_what_the_model_is_told_to_do():
    """The first call is the one that was failing for 95 of the 220 tasks."""
    reply = RehearsalVoice().next_turn(_request(1, []))

    assert isinstance(reply, AskForTool)
    assert reply.arguments == {"operation": "read", "path": GUIDE_PATH}


def test_it_reads_lists_writes_and_commits_in_four_calls():
    voice = RehearsalVoice()

    replies = _work_a_whole_task(voice)

    assert all(isinstance(one, AskForTool) for one in replies)
    assert [one.tool_name for one in replies] == [
        "workspace_apply",
        "workspace_apply",
        "workspace_apply",
        "finalize",
    ]
    assert [
        one.arguments["operation"] for one in replies[:3]
    ] == ["read", "list", "write"]
    assert replies[-1].arguments["deliverables"] == [REHEARSAL_DELIVERABLE]


def test_the_file_it_writes_says_it_is_not_an_answer():
    """In the file itself, not only in the record beside it.

    A deliverable is collected onto disk and can be read long after the record
    that framed it has been lost. If the disclaimer lives only in the record,
    the file on disk is indistinguishable from work.
    """
    voice = RehearsalVoice()
    history = [_ok("read", {"content": "the guide"}), _ok("list", {"entries": []})]

    reply = voice.next_turn(_request(3, history))

    assert isinstance(reply, AskForTool)
    assert reply.arguments["path"] == REHEARSAL_DELIVERABLE
    written = reply.arguments["content"]
    assert "not by a model" in written
    assert "must not be scored as one" in written


def test_it_quotes_what_the_guide_actually_returned():
    """So a guide that was written but says nothing useful is still visible."""
    voice = RehearsalVoice()
    history = [_ok("read", {"content": "# Your input files\n\n- inputs/sheet.xlsx"})]

    voice.next_turn(_request(2, history))
    history.append(_ok("list", {"entries": []}))
    reply = voice.next_turn(_request(3, history))

    assert "inputs/sheet.xlsx" in reply.arguments["content"]


# ── what it refuses to paper over ─────────────────────────────────────────


def test_a_refused_write_stops_the_task_and_names_the_error():
    """The 1 MiB case. A real model is told only ``fixture_backend_error``.

    It would retry until its budget was gone and the record would show a model
    that could not save a file. The stand-in stops on the first refusal and puts
    the error type where the fault belongs.
    """
    voice = RehearsalVoice()
    history = [
        _ok("read", {"content": "the guide"}),
        _ok("list", {"entries": []}),
        _not_ok("write", "fixture_backend_error"),
    ]

    reply = voice.next_turn(_request(4, history))

    assert isinstance(reply, GaveUp)
    assert "fixture_backend_error" in reply.note
    # Keyed by the task, not counted -- which task could not save its file is
    # the thing worth knowing, and a count of two says nothing about whether
    # it was the same fault twice.
    assert list(voice.as_dict()["writes_refused"].values()) == [
        "fixture_backend_error"
    ]


def test_a_guide_that_could_not_be_read_is_recorded_as_not_readable():
    voice = RehearsalVoice()
    history = [_not_ok("read", "path_not_found")]

    voice.next_turn(_request(2, history))

    assert voice.as_dict()["guide_was_readable_in"] == 0
    assert voice.as_dict()["tasks_worked"] == 1


def test_running_out_of_turns_before_writing_says_the_ceiling_is_too_low():
    """Rather than committing nothing and looking like a model that gave up."""
    reply = RehearsalVoice().next_turn(_request(8, [], turns_left=1))

    assert isinstance(reply, GaveUp)
    assert "turn ceiling" in reply.note


# ── what it must never be taken for ───────────────────────────────────────


def test_it_declares_that_it_makes_no_paid_calls():
    """The flag the budget code reads. It is not a comment."""
    assert RehearsalVoice().makes_paid_calls is False


def test_its_summary_says_a_grade_over_these_files_would_be_meaningless():
    voice = RehearsalVoice()
    _work_a_whole_task(voice)

    summary = voice.as_dict()

    assert summary["tasks_worked"] == 1
    assert summary["guide_was_readable_in"] == 1
    assert summary["wrote_a_file_in"] == 1
    assert "grade" in summary["this_is_not_a_result"]
    assert "No model was asked" in summary["what_this_is"]


def test_spending_nothing_is_reported_as_no_call_and_not_as_zero_dollars():
    """The distinction the whole cost ledger rests on.

    "$0.00" is a measurement. "nothing was asked" is the absence of one, and a
    run that reports the first when it means the second has put a false number
    into a ledger that other numbers are compared against.
    """
    said = rehearsal_is_not_a_run()

    assert "no call was made" in said["cost"]
    assert "not the same as $0 measured" in said["cost"]


def test_two_tasks_are_counted_separately():
    """A fresh request with no history starts a task; the count must follow."""
    voice = RehearsalVoice()

    _work_a_whole_task(voice, prompt="the first task")
    _work_a_whole_task(voice, prompt="the second task")

    assert voice.as_dict()["tasks_worked"] == 2
