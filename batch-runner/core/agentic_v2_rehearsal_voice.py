"""A stand-in that works a real task, so the assembly is proven before it costs.

:class:`~core.agentic_v2_conversation.ScriptedVoice` answers from a list written
in advance. That is right for testing the loop -- a written list is the only way
to put the loop in an exact state -- and wrong for testing everything *around*
the loop, because a list of replies has to be written against a known workspace
and so cannot be pointed at a task nobody has looked at yet.

This is the other stand-in. It has no list. It reads what came back and chooses
the next call from that, the way the standing instructions tell a real model to:
open the guide, look at what is there, write something, commit it. Pointed at
any of the 220 tasks it does the same four things, so the whole production path
-- binding, staging, the fixture backend, the driver, deliverable collection,
the record -- can be run end to end on real bytes without asking a model
anything.

**It is not a model and its output is not a result.** It cannot do the task; it
writes a deliverable that says what it found and nothing more. What it proves is
narrower and is the thing worth proving before money is spent: that a task's
files arrive, that they can be opened, that a write lands, and that ``finalize``
is accepted. A wiring fault in any of those looks, in a paid run, exactly like a
model that could not do the work -- which is the confusion the whole
pre-registration exists to prevent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from core.agentic_v2_conversation import (
    AskForTool,
    GaveUp,
    ModelReply,
    ModelRequest,
    ToolExchange,
)
from core.agentic_v2_reference_staging import INPUTS_GUIDE, MODEL_INPUT_PREFIX


#: What the rehearsal writes, and the only file it ever writes.
#:
#: Named so that a rehearsal's output cannot be mistaken for a task's. A file
#: called `report.docx` sitting in a deliverables directory is something
#: somebody will eventually read as an answer.
REHEARSAL_DELIVERABLE = "rehearsal-notes.md"

#: Where the guide staging leaves the list of a task's inputs.
GUIDE_PATH = f"{MODEL_INPUT_PREFIX}/{INPUTS_GUIDE}"

#: How much of what was read is quoted back into the deliverable.
#:
#: Enough to tell a real rendering from an empty one by eye, short enough that a
#: rehearsal over 220 tasks does not write a copy of the dataset.
QUOTED_CHARACTERS = 400


@dataclass
class TaskRehearsal:
    """What the stand-in found while working one task."""

    guide_was_readable: bool = False
    entries_seen: int = 0
    wrote_a_file: bool = False
    write_refused: str = ""
    quoted: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "guide_was_readable": self.guide_was_readable,
            "entries_seen": self.entries_seen,
            "wrote_a_file": self.wrote_a_file,
            "write_refused": self.write_refused,
        }


def _last(history: tuple[ToolExchange, ...]) -> ToolExchange | None:
    return history[-1] if history else None


def _was(exchange: ToolExchange, operation: str) -> bool:
    return exchange.tool_name == "workspace_apply" and (
        str(exchange.arguments.get("operation")) == operation
    )


@dataclass
class RehearsalVoice:
    """Works the task in four calls, choosing each from what came back.

    Deterministic, and deliberately so: two rehearsals of the same stage differ
    only where the workspace differs, which is what makes a difference worth
    looking at. It spends nothing, and says so -- the loop refuses a voice that
    does not declare which it is.
    """

    makes_paid_calls: bool = False
    seen: dict[str, TaskRehearsal] = field(default_factory=dict)
    _current: TaskRehearsal | None = field(default=None, init=False)

    # The loop hands one voice to one task at a time, and a fresh request with
    # an empty history is the start of a task. Keyed by prompt rather than by
    # task id because the loop does not tell a voice which task it is on -- a
    # model is not told either.
    def _found(self, request: ModelRequest) -> TaskRehearsal:
        key = request.task_prompt[:120]
        if not request.history:
            self._current = TaskRehearsal()
            self.seen[key] = self._current
        if self._current is None:  # a resumed run, or a history we did not start
            self._current = self.seen.setdefault(key, TaskRehearsal())
        return self._current

    def next_turn(self, request: ModelRequest) -> ModelReply:
        found = self._found(request)
        call_id = f"rehearsal-{request.turn}"
        last = _last(request.history)

        # Running out of turns while still holding an unwritten answer is the
        # one thing a real model must not do, so the stand-in does not model it:
        # it commits what it has, or says plainly that it has nothing.
        if request.turns_left <= 1 and not found.wrote_a_file:
            return GaveUp(
                note=(
                    "the rehearsal ran out of turns before it wrote anything, "
                    "which means the loop's turn ceiling is lower than the four "
                    "calls the standing instructions ask for"
                )
            )

        if last is None:
            return AskForTool(
                call_id=call_id,
                tool_name="workspace_apply",
                arguments={"operation": "read", "path": GUIDE_PATH},
                why="the instructions say to open the guide to the inputs first",
            )

        if _was(last, "read"):
            found.guide_was_readable = bool(last.ok)
            if last.ok:
                found.quoted = str(last.data.get("content") or "")[:QUOTED_CHARACTERS]
            return AskForTool(
                call_id=call_id,
                tool_name="workspace_apply",
                arguments={"operation": "list", "path": "."},
                why="look at what is actually in the workspace",
            )

        if _was(last, "list"):
            entries = last.data.get("entries")
            found.entries_seen = len(entries) if isinstance(entries, list) else 0
            return AskForTool(
                call_id=call_id,
                tool_name="workspace_apply",
                arguments={
                    "operation": "write",
                    "path": REHEARSAL_DELIVERABLE,
                    "content": self._notes(found),
                },
                why="write the one file this stand-in has to write",
            )

        if _was(last, "write"):
            if not last.ok:
                # The 1 MiB case, and the reason this rehearsal exists. A real
                # model is told only `fixture_backend_error` and would retry
                # until its budget was gone; the stand-in stops and names it, so
                # the fault is in the record rather than in the model's column.
                found.write_refused = str(last.error_type or "unknown")
                return GaveUp(
                    note=(
                        "the workspace refused the write with "
                        f"{found.write_refused}. Nothing the model could have "
                        "done differently would have changed that"
                    )
                )
            found.wrote_a_file = True
            return AskForTool(
                call_id=call_id,
                tool_name="finalize",
                arguments={
                    "deliverables": [REHEARSAL_DELIVERABLE],
                    "summary": "rehearsal only: the workspace was reachable",
                },
                why="commit the one file, which is what ends a task",
            )

        return GaveUp(
            note=(
                f"the rehearsal has no next step after {last.tool_name}, which "
                "means the loop returned something it was not built to expect"
            )
        )

    def _notes(self, found: TaskRehearsal) -> str:
        quoted = found.quoted.strip() or "(nothing -- the guide could not be read)"
        return (
            "# Rehearsal notes\n\n"
            "This file was written by a stand-in, not by a model. It is not an "
            "answer to the task and must not be scored as one.\n\n"
            f"- the guide at `{GUIDE_PATH}` was "
            f"{'readable' if found.guide_was_readable else 'NOT readable'}\n"
            f"- what the first read returned, first {QUOTED_CHARACTERS} "
            "characters:\n\n"
            "```\n"
            f"{quoted}\n"
            "```\n"
        )

    def as_dict(self) -> dict[str, Any]:
        """What the rehearsal found, per task, for the record it writes."""
        readable = sum(1 for one in self.seen.values() if one.guide_was_readable)
        wrote = sum(1 for one in self.seen.values() if one.wrote_a_file)
        refused = {
            key: one.write_refused
            for key, one in self.seen.items()
            if one.write_refused
        }
        return {
            "what_this_is": (
                "a stand-in that opens the guide, lists the workspace, writes "
                "one file and commits it. No model was asked anything and "
                "nothing was spent"
            ),
            "tasks_worked": len(self.seen),
            "guide_was_readable_in": readable,
            "wrote_a_file_in": wrote,
            "writes_refused": refused,
            "this_is_not_a_result": (
                "the deliverable is a note about the workspace. A grade "
                "computed over these files would be a grade of this file's "
                "wording"
            ),
        }


def rehearsal_is_not_a_run() -> Mapping[str, Any]:
    """The sentence a rehearsal record carries where a run carries a route.

    Written here rather than at the call site so that the two cannot drift, and
    so that anything reading a rehearsal record finds the disclaimer in the
    place it would look for the model.
    """
    return {
        "model": "none",
        "why": (
            "this was a rehearsal. The loop, the staging, the workspace and "
            "the collection all ran; the model did not, because none was asked"
        ),
        "what_it_does_not_show": (
            "whether a model can do these tasks. It shows only that a model "
            "asked to do them would have had files to open and somewhere to "
            "write"
        ),
        "cost": "none -- no call was made, which is not the same as $0 measured",
    }
