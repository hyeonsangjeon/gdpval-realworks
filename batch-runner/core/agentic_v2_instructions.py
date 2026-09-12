"""The instruction text as the model actually receives it, and a name for it.

The stage runner used to have three separate opinions about what the model was
told. The plan file held a paragraph; the runner substituted into it for a
backend named in the call; the factory built a backend named somewhere else;
and the run record wrote down a third string. Nothing compared them. A run that
described the fixture's refusals to a model sitting on the microVM would have
passed every check in the repository, and the failures it caused would have read
as the model's.

This module is the one answer. :func:`resolve_instructions` takes the plan and
the backend class that will really be constructed, and returns the exact bytes
that go out, with their digest. The runner sends ``resolved.text``, prints
``resolved.sha256``, and writes :meth:`ResolvedInstructions.identity` into the
run record. There is no second path, so there is nothing to drift.

Three refusals live here, all of them before any money is spent.

**An unknown backend is refused, whether or not the plan asks for a derived
list.** Guessing is the failure this whole mechanism exists to stop, and
"the plan didn't ask, so it doesn't matter what backend this is" is a guess
wearing a different hat: the run record would still name a class whose refusals
nobody has checked. :func:`core.agentic_v2_tool_availability.availability_for`
raises, and that raise is allowed through.

**Empty instructions are refused when the plan meant to have some.** The runner
reads ``plan.get("instructions") or ""``, an expression that cannot fail. Until
2026-09-11 it silently sent the empty string on every turn of every task.

**Text wider than it was priced at is refused.** Every figure under ``cost:``
was worked out at a character width. A derived list is longer than the
placeholder it replaces, so the literal plan text is no longer a safe thing to
measure -- a plan could be well inside the priced width on disk and go out over
it, once per turn, for every task in the cohort.

Nothing here asks a model, touches a network, or builds a backend. It is given
a class and reads its name.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

from core.agentic_v2_tool_availability import (
    PLACEHOLDER,
    apply_tool_availability,
    backend_name,
    unverified_claims,
)


class InstructionsRefused(ValueError):
    """Raised before the run starts, when what would be sent is not sendable.

    A ``ValueError`` rather than a bespoke hierarchy because the stage runner
    already stops on one, and a new exception class that some caller forgets to
    catch turns a refusal into a crash halfway through a paid cohort.
    """


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def file_digest(path: Path) -> str:
    """The plan file's own bytes, so the record names the file it read.

    Not the same fact as :attr:`ResolvedInstructions.sha256`. This says which
    file was on disk; that says what left the machine. A run under ``--plan``
    needs both, because the preregistration document seals only the default
    plan's digest and cannot describe a run that used another.
    """
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True)
class ResolvedInstructions:
    """What the model is sent, named by its digest.

    ``text`` is the string handed to the provider verbatim. ``sha256`` is over
    its UTF-8 bytes, so two runs claiming the same conditions can be held
    against each other by comparing one hex string instead of two paragraphs.
    """

    text: str
    backend: str
    derived: bool
    plan_characters: int
    unverified: tuple[str, ...]

    @property
    def characters(self) -> int:
        return len(self.text)

    @property
    def sha256(self) -> str:
        return _digest(self.text)

    def identity(self) -> dict[str, Any]:
        """The run record's copy. The text itself is deliberately not in it.

        A run record is read by people looking for what a run did, and pasting
        seven thousand characters of model-facing prose into it buries that.
        The digest names the text exactly, and the plan file it came from is
        named beside it, so the text is one ``git show`` away rather than
        inline.
        """
        return {
            "sha256": self.sha256,
            "characters": self.characters,
            "derived_for_backend": self.backend,
            "derived": self.derived,
            "plan_characters": self.plan_characters,
            "declared_but_never_run_here": list(self.unverified),
        }


def resolve_instructions(
    plan: Mapping[str, Any],
    backend: Any,
    *,
    priced_characters: Optional[int] = None,
) -> ResolvedInstructions:
    """The exact instruction bytes for `backend`, or a refusal.

    `backend` may be the class, an instance or the class name; the name is all
    that is read, so this can be called before anything is constructed -- which
    is the point, because the refusals below are worth having before a cohort
    starts rather than during it.

    `priced_characters` is the width the plan's cost figures were worked out
    at. Passing it turns on the width check. Passing ``None`` leaves it off and
    is the right thing for a caller that is only reporting.
    """
    name = backend_name(backend)
    # Raises KeyError, naming the backend, if no list has been written for it.
    # Deliberately called even when the text below turns out not to ask for a
    # derived list: an unchecked backend is an unchecked backend either way.
    unverified = tuple(entry.tool for entry in unverified_claims(name))

    raw = plan.get("instructions")
    if raw is None:
        raise InstructionsRefused(
            "the plan has no `instructions` key. The runner reads "
            '`plan.get("instructions") or ""`, which cannot fail: the run '
            "would go ahead at full price with the model told nothing"
        )
    if not isinstance(raw, str) or not raw.strip():
        raise InstructionsRefused(
            f"the plan's `instructions` is {type(raw).__name__} and empty of "
            "text. See above: an empty instruction costs the same as a full one"
        )

    text = apply_tool_availability(raw, name)
    resolved = ResolvedInstructions(
        text=text,
        backend=name,
        derived=PLACEHOLDER in raw,
        plan_characters=len(raw),
        unverified=unverified,
    )

    if priced_characters is not None and resolved.characters > priced_characters:
        over = resolved.characters - priced_characters
        how = (
            "after the tool list was substituted in"
            if resolved.derived
            else "as written in the plan"
        )
        raise InstructionsRefused(
            f"the instructions are {resolved.characters} characters {how}, and "
            f"the cost figures were worked out at {priced_characters}: "
            f"{over} over. This is charged once per turn on every task, so it "
            "is spending against an approval computed for something else. "
            "Shorten the wording, or re-price the plan and say in it that the "
            "width moved"
        )

    return resolved


def unverified_note(resolved: ResolvedInstructions) -> str:
    """A line for the console when a declared tool has never been run here.

    Empty when there is nothing to say, so the caller can print it or not
    without asking twice.
    """
    if not resolved.unverified:
        return ""
    tools = ", ".join(resolved.unverified)
    return (
        f"{resolved.backend} is declared to serve {tools}, and nothing here "
        "has run it. The declaration was read out of the class, not observed. "
        "If this run needs that tool to work, the thing to check first is "
        "whether it does."
    )
