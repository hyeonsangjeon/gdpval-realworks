"""Reading a V2 task's ending as three questions instead of one word.

The report row carries ``status: success | error``, and that one word is asked
to carry three separate facts that routinely disagree:

1. **``finalize`` was called and the tool desk accepted it.**
2. **A file came back, and it is a real file** -- present, non-empty, and
   openable by whatever owns its format.
3. **The work is any good.**

A task can have (1) and not (2): ``finalize`` names paths and the collection
short-writes one. It can have (1) and (2) and not (3), and that is the case
worth naming, because it is common and it looks like success from every angle a
pipeline can see. A model that cannot do a task and writes ``I was unable to
complete this analysis`` into ``answer.md`` has called ``finalize``, produced a
non-empty file that opens cleanly as text, and done none of the work. Counting
it as a task done is the specific error this module exists to stop.

**Nothing here measures (3).** No judge is run, no rubric is applied, and no
score is produced; marking thirty answers is a separate approval that this run
does not have. :attr:`Outcome.quality` is therefore always ``None`` and says why.
:attr:`Outcome.reads_like_a_refusal_notice` is not a quality measure either --
it is a flag that says *do not read (1) and (2) as (3) for this one*, it names
the phrase it matched so a person can check, and it undercounts on purpose.

**The three cannot be summed.** :class:`Outcome` has no truth value: asking
``if outcome:`` raises rather than quietly answering one of the three questions
the caller did not name. A denominator of thirty is reported three times over,
once per question, and a task is never moved from one column into another.

Offline. Reads a run record that already exists and the files already on disk.
No model, no network, no cost.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from core.artifact_verifier import verify_one

#: ``finalize`` was called and the desk gave back a terminal result.
FINALIZE_ACCEPTED = "accepted"

#: The run ended and ``finalize`` was never called. The runner names this
#: ending itself: ``error: finalize_not_called``.
FINALIZE_NOT_CALLED = "not_called"

#: The run ended some other way -- a ceiling, a broken desk, a refused call --
#: before any terminal result existed. Distinct from "not called" on purpose:
#: a task stopped at its turn limit and a task that talked until it ran out of
#: things to say are different failures and get counted separately.
FINALIZE_ENDED_FIRST = "ended_before_it_could_be"

#: What the runner calls the ending where nothing was ever finalised.
_NOT_CALLED_ERROR = "finalize_not_called"

#: Phrases that mean the file is the model saying it could not do the work.
#: Deliberately short and literal. A longer list would catch more and would
#: start making judgements about content, which is question 3 and is not
#: measured here. Matched case-insensitively against the first part of the
#: deliverable text only -- a refusal is at the top or it is not what the file
#: is about.
_REFUSAL_PHRASES = (
    "i am unable to",
    "i was unable to",
    "i cannot complete",
    "i can't complete",
    "i do not have access",
    "i don't have access",
    "unable to complete this task",
    "cannot be completed",
    "no files were provided",
    "as an ai",
)

#: How much of the deliverable text is looked at. A refusal notice is the whole
#: file; a real answer that happens to contain one of these phrases in passing
#: is not, and reading only the opening is what keeps the second from being
#: flagged as the first.
_OPENING_CHARACTERS = 600


@dataclass(frozen=True)
class FileVerdict:
    """One collected file, on question 2 only.

    ``openable`` is three-valued and stays that way. ``None`` means no library
    for that format was installed, which is *not checked* rather than *good* --
    folding it into either would put a guess in a count.
    """

    path: str
    exists: bool
    size_bytes: int
    openable: Optional[bool]
    problems: tuple[str, ...]

    @property
    def is_usable(self) -> bool:
        """Present, non-empty, opened cleanly, and nothing complained."""
        return (
            self.exists
            and self.size_bytes > 0
            and self.openable is True
            and not self.problems
        )


@dataclass(frozen=True)
class Outcome:
    """One task's ending, with the three questions kept apart."""

    task_id: str
    finalize: str
    files: tuple[FileVerdict, ...]
    reads_like_a_refusal_notice: Optional[str]
    error_type: Optional[str]

    quality: None = None
    """Not measured. See the module docstring; this is a slot, not a result."""

    quality_not_measured_because: str = (
        "no judge is run in this experiment and marking the answers is not "
        "approved. A task can reach every green in this record and be wrong."
    )

    def __bool__(self) -> bool:
        raise TypeError(
            f"{self.task_id}: an outcome has three answers and no single one. "
            "Ask finalize_was_accepted, produced_a_usable_file, or quality -- "
            "the third of which is always None here"
        )

    @property
    def finalize_was_accepted(self) -> bool:
        return self.finalize == FINALIZE_ACCEPTED

    @property
    def produced_a_usable_file(self) -> bool:
        return any(verdict.is_usable for verdict in self.files)

    @property
    def files_not_checked(self) -> tuple[FileVerdict, ...]:
        """Collected, non-empty, and no validator was installed for the format.

        Reported rather than counted either way. A run with many of these has a
        thin venv, not a bad model.
        """
        return tuple(
            verdict
            for verdict in self.files
            if verdict.exists and verdict.size_bytes > 0 and verdict.openable is None
        )

    def as_row(self) -> dict[str, Any]:
        """Three answers side by side, none derived from another."""
        return {
            "task_id": self.task_id,
            "finalize": self.finalize,
            "files_collected": len(self.files),
            "files_usable": sum(1 for verdict in self.files if verdict.is_usable),
            "files_not_checked": len(self.files_not_checked),
            "reads_like_a_refusal_notice": self.reads_like_a_refusal_notice,
            "error_type": self.error_type,
            "quality": None,
            "quality_not_measured_because": self.quality_not_measured_because,
        }


def _finalize_verdict(record: Mapping[str, Any]) -> str:
    if record.get("success") is True:
        return FINALIZE_ACCEPTED
    if str(record.get("error") or "") == _NOT_CALLED_ERROR:
        return FINALIZE_NOT_CALLED
    return FINALIZE_ENDED_FIRST


def refusal_phrase_in(text: str) -> Optional[str]:
    """The first refusal phrase in the opening of `text`, or ``None``.

    Not a quality judgement in either direction. A hit means the file should
    not be read as work done without someone looking; a miss means nothing at
    all, because a model can fail a task in fluent prose.
    """
    opening = str(text or "")[:_OPENING_CHARACTERS].lower()
    for phrase in _REFUSAL_PHRASES:
        if phrase in opening:
            return phrase
    return None


def read_outcome(
    task_id: str,
    record: Mapping[str, Any],
    *,
    collected_paths: Sequence[str | Path] = (),
    collection_root: Optional[str | Path] = None,
) -> Outcome:
    """Answer the three questions about one task, separately.

    `record` is the V2 result envelope the runner wrote. `collected_paths` are
    the files as they landed on the host -- ``Collection.submission_paths`` --
    rather than the paths ``finalize`` named, because question 2 is about what
    is on disk and not about what was claimed.
    """
    verdicts: list[FileVerdict] = []
    for candidate in collected_paths:
        report = verify_one(candidate, workdir=collection_root)
        verdicts.append(
            FileVerdict(
                path=str(candidate),
                exists=report.exists,
                size_bytes=report.size_bytes,
                openable=report.openable,
                problems=tuple(report.errors),
            )
        )

    return Outcome(
        task_id=task_id,
        finalize=_finalize_verdict(record),
        files=tuple(verdicts),
        reads_like_a_refusal_notice=refusal_phrase_in(
            str(record.get("deliverable_text") or record.get("text") or "")
        ),
        error_type=(record.get("error") or None) if not record.get("success") else None,
    )


def count_separately(outcomes: Sequence[Outcome]) -> dict[str, Any]:
    """The three tallies over one denominator, never folded together.

    ``tasks`` is the denominator for all three and is every task handed in,
    including ones that never ran. Nothing here returns a success rate: which
    of the three a rate would be about is exactly what gets lost.
    """
    return {
        "tasks": len(outcomes),
        "finalize_accepted": sum(1 for one in outcomes if one.finalize_was_accepted),
        "finalize_not_called": sum(
            1 for one in outcomes if one.finalize == FINALIZE_NOT_CALLED
        ),
        "finalize_ended_first": sum(
            1 for one in outcomes if one.finalize == FINALIZE_ENDED_FIRST
        ),
        "produced_a_usable_file": sum(
            1 for one in outcomes if one.produced_a_usable_file
        ),
        "files_not_checked": sum(len(one.files_not_checked) for one in outcomes),
        "read_like_a_refusal_notice": sum(
            1 for one in outcomes if one.reads_like_a_refusal_notice
        ),
        "quality_measured": 0,
        "quality_note": (
            "no judge was run. The three counts above are about whether an "
            "answer exists, not whether it is right"
        ),
    }
