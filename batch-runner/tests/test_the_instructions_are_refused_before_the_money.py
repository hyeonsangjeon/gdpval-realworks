"""The three refusals in :mod:`core.agentic_v2_instructions`, run.

The module exists to stop a cohort before it starts, and it was shipped with
none of its refusals pinned. Every other check in this branch is held to its own
behaviour; this one was held to its docstring, which is the kind of gap that is
only visible once it has cost something.

Each refusal here is the last thing standing between a plan and a paid run:

* an unknown backend -- the run record would name a class whose refusals nobody
  has checked, and the model would be handed a list inferred from a
  similar-looking one;
* instructions that are missing or blank -- ``plan.get("instructions") or ""``
  cannot fail, so the cohort runs at full price with the model told nothing;
* text wider than it was priced at -- charged once per turn on every task,
  against an approval computed for something else.

The last test is about *where* they fire. A refusal that arrives after the
ledger is open is a refusal that has already been paid for, which is the shape
of the defect that killed run 34651982737.

Offline. A mapping in, an exception out. No model, no network, no cost.
"""
from __future__ import annotations

import inspect

import pytest

from core.agentic_v2_fixture_backend import AgenticV2FixtureBackend
from core.agentic_v2_instructions import InstructionsRefused, resolve_instructions
from core.agentic_v2_tool_availability import PLACEHOLDER

#: Short enough that the width check is never what refuses these, so a test
#: about the missing key cannot pass for the wrong reason.
A_PARAGRAPH = "Do the work and leave the deliverables in your working directory."


# ---------------------------------------------------------------------------
# An unknown backend
# ---------------------------------------------------------------------------


def test_a_backend_nobody_has_written_a_list_for_is_refused():
    with pytest.raises(KeyError, match="no refusal list has been written for"):
        resolve_instructions(
            {"instructions": A_PARAGRAPH + PLACEHOLDER},
            "AgenticV2BackendNobodyHasChecked",
        )


def test_an_unknown_backend_is_refused_even_when_no_list_was_asked_for():
    """The case that is easy to argue out of, and shouldn't be.

    "The plan didn't ask for a derived list, so it doesn't matter what backend
    this is" is a guess wearing a different hat. The run record would still name
    the class, and a reader would still take that name as saying which refusals
    the tasks met.
    """
    plan = {"instructions": A_PARAGRAPH}
    assert PLACEHOLDER not in plan["instructions"]

    with pytest.raises(KeyError, match="AgenticV2BackendNobodyHasChecked"):
        resolve_instructions(plan, "AgenticV2BackendNobodyHasChecked")


# ---------------------------------------------------------------------------
# Nothing to send
# ---------------------------------------------------------------------------


def test_a_plan_with_no_instructions_key_is_refused():
    with pytest.raises(InstructionsRefused) as refusal:
        resolve_instructions({}, AgenticV2FixtureBackend)

    said = str(refusal.value)
    assert "no `instructions` key" in said
    assert "cannot fail" in said, (
        "the refusal has to name the expression, because the reader's next "
        "question is why an empty instruction was ever sendable"
    )


@pytest.mark.parametrize("nothing", ["", "   ", "\n\n", "\t"])
def test_instructions_that_are_blank_are_refused(nothing):
    """Whitespace is not text. It costs a turn and says nothing."""
    with pytest.raises(InstructionsRefused, match="empty of"):
        resolve_instructions({"instructions": nothing}, AgenticV2FixtureBackend)


@pytest.mark.parametrize("wrong", [["a", "b"], 7, {"text": "hello"}, True])
def test_instructions_that_are_not_text_are_refused_by_their_type(wrong):
    """A YAML edit that drops the ``|`` turns a paragraph into a list."""
    with pytest.raises(InstructionsRefused) as refusal:
        resolve_instructions({"instructions": wrong}, AgenticV2FixtureBackend)
    assert type(wrong).__name__ in str(refusal.value)


# ---------------------------------------------------------------------------
# Wider than it was priced at
# ---------------------------------------------------------------------------


def test_nothing_is_measured_when_nothing_was_priced():
    """``None`` is for a caller that is only reporting, and turns the check off.

    Worth pinning because the off switch is a default argument, and a default
    that silently disables a spending check is worth being deliberate about.
    """
    resolved = resolve_instructions(
        {"instructions": "x" * 50_000}, AgenticV2FixtureBackend
    )
    assert resolved.characters == 50_000


def test_text_exactly_at_the_priced_width_is_allowed():
    resolved = resolve_instructions(
        {"instructions": "x" * 400}, AgenticV2FixtureBackend, priced_characters=400
    )
    assert resolved.characters == 400


def test_one_character_over_is_refused_and_the_refusal_does_the_arithmetic():
    with pytest.raises(InstructionsRefused) as refusal:
        resolve_instructions(
            {"instructions": "x" * 401},
            AgenticV2FixtureBackend,
            priced_characters=400,
        )

    said = str(refusal.value)
    assert "401 characters" in said and "400" in said
    assert "1 over" in said
    assert "once per turn" in said, (
        "one character sounds like rounding until the refusal says how many "
        "times it is sent"
    )


def test_the_width_is_measured_after_the_list_goes_in_not_before():
    """The reason the check exists, rather than a check on the plan file.

    A derived list is longer than the placeholder it replaces. This plan is
    comfortably inside the priced width as written on disk, and over it by the
    time it leaves the machine -- which is the only width anyone is billed for.
    """
    plan = {"instructions": PLACEHOLDER}
    priced = len(PLACEHOLDER) + 20

    with pytest.raises(InstructionsRefused) as refusal:
        resolve_instructions(plan, AgenticV2FixtureBackend, priced_characters=priced)

    assert "after the tool list was substituted in" in str(refusal.value)
    loose = resolve_instructions(plan, AgenticV2FixtureBackend)
    assert loose.plan_characters < loose.characters


def test_a_plan_that_asks_for_no_list_is_refused_as_written():
    """Because the two cases want different fixes, and say so differently."""
    with pytest.raises(InstructionsRefused, match="as written in the plan"):
        resolve_instructions(
            {"instructions": "x" * 401},
            AgenticV2FixtureBackend,
            priced_characters=400,
        )


# ---------------------------------------------------------------------------
# Where they fire
# ---------------------------------------------------------------------------


def test_the_refusal_is_a_value_error_so_an_older_caller_still_stops():
    """A new exception class nobody catches turns a refusal into a crash.

    The stage runner names it explicitly, but it is not the only caller this
    module will ever have, and the ones that do not know about it should stop
    rather than continue.
    """
    assert issubclass(InstructionsRefused, ValueError)


def test_the_runner_resolves_the_instructions_before_it_opens_the_ledger():
    """Order, not presence. A refusal after the ledger has already been paid for.

    This is exactly how run 34651982737 ended: the thing that stopped it was
    correct, and it ran after the model had been called and charged. Everything
    ``resolve_instructions`` can refuse is knowable from a file on disk, so
    there is no reason for it to be discovered late.
    """
    from scripts.run_agentic_v2_stage import main

    source = inspect.getsource(main)
    resolved_at = source.index("resolve_instructions(")
    ledger_at = source.index("open_the_ledger(")
    caught_at = source.index("InstructionsRefused")

    assert resolved_at < ledger_at, (
        "the instructions are resolved after the ledger is opened, so a plan "
        "this module would have refused for free now gets refused for money"
    )
    assert caught_at < ledger_at, (
        "the refusal is raised before the ledger and caught after it, which "
        "means it escapes the pre-flight handler and crashes instead"
    )
