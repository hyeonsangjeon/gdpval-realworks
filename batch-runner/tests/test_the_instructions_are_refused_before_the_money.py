"""The five refusals in :mod:`core.agentic_v2_instructions`, run.

The module exists to stop a cohort before it starts, and it was shipped with
none of its refusals pinned. Every other check in this branch is held to its own
behaviour; this one was held to its docstring, which is the kind of gap that is
only visible once it has cost something.

Each refusal here is the last thing standing between a plan and a paid run:

* an unknown backend -- the run record would name a class whose refusals nobody
  has checked, and the model would be handed a list inferred from a
  similar-looking one;
* a hand-written tool paragraph on a backend nobody measured it against -- the
  one refusal here whose absence has no symptom, because a model told there is
  no shell does not ask for one and the cohort completes;
* a plan that derives its list and then contradicts it in prose -- the mistake
  the refusal above invites, since the quickest way to add the placeholder is
  to paste it under the paragraph that was already there;
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
from pathlib import Path

import pytest

from core.agentic_v2_fixture_backend import AgenticV2FixtureBackend
from core.agentic_v2_instructions import InstructionsRefused, resolve_instructions
from core.agentic_v2_stage_one_budget import load_stage_one_plan
from core.agentic_v2_tool_availability import (
    DESCRIBED_BY_HAND_AND_CHECKED,
    PLACEHOLDER,
    backend_name,
    contradicted_sentences,
)

#: Short enough that the width check is never what refuses these, so a test
#: about the missing key cannot pass for the wrong reason.
A_PARAGRAPH = "Do the work and leave the deliverables in your working directory."

#: The backend the isolated stage really mounts, named as a string so that
#: reading this file does not import it -- the class needs a host.
THE_MICROVM = "AgenticV2MicroVMBackend"

ENVELOPE = Path(__file__).resolve().parents[1] / "experiments" / "execution_envelope"
THE_PLAN_THAT_RAN = ENVELOPE / "agentic_stage_one_plan.yaml"
THE_CORRECTED_PLAN = ENVELOPE / "agentic_corrected_harness_plan.yaml"


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
# A paragraph written by hand, on a backend nobody held it against
# ---------------------------------------------------------------------------


def test_a_hand_written_paragraph_is_refused_on_the_microvm():
    """The refusal with no symptom, which is why it has to be a refusal.

    Every other check here stops something that would visibly go wrong. This one
    stops something that would go *right*: the cohort completes, every task has
    a deliverable, and the deliverables are what a model produces when it has
    been told it cannot run anything.
    """
    plan = {"instructions": A_PARAGRAPH}
    assert PLACEHOLDER not in plan["instructions"]

    with pytest.raises(InstructionsRefused) as refusal:
        resolve_instructions(plan, THE_MICROVM)

    said = str(refusal.value)
    assert "writes its own tool paragraph" in said
    assert THE_MICROVM in said


def test_the_same_paragraph_is_allowed_on_the_backend_it_was_measured_against():
    """trial_30 ran on the fixture with this exact plan, and is not refused now.

    A guard that retroactively refuses a run that already happened is a guard
    that will be turned off. The fixture is in the set because someone held the
    paragraph against its real methods, sentence by sentence, in
    ``test_the_standing_instructions_fit_neither_backend.py``.
    """
    resolved = resolve_instructions({"instructions": A_PARAGRAPH}, AgenticV2FixtureBackend)
    assert resolved.derived is False
    assert resolved.text == A_PARAGRAPH


def test_being_in_the_set_is_not_a_claim_that_the_paragraph_is_right():
    """The fact a reader trips over, pinned so it reads as intended.

    ``contradicted_sentences`` flags the plan's paragraph on *both* backends --
    it names ``exec_run`` among the tools that refuse, and on the fixture
    ``exec_run`` serves one argv. So the set does not mean "correct here". It
    means someone measured it here and found the error runs in the cheap
    direction: a model told a working tool refuses will not reach for it, which
    costs the fixture nothing it was going to produce. On the microVM the same
    error removes the only tool that runs anything, which is the run's whole
    subject. Same paragraph, same wrongness, opposite consequence -- and the
    consequence is what the set is keyed on.
    """
    raw = load_stage_one_plan(THE_PLAN_THAT_RAN)["instructions"]

    assert contradicted_sentences(raw, "AgenticV2FixtureBackend"), (
        "if this is empty the paragraph has been edited and the set now needs "
        "a different justification than the one in this test"
    )
    assert contradicted_sentences(raw, THE_MICROVM)

    resolve_instructions({"instructions": raw}, AgenticV2FixtureBackend)
    with pytest.raises(InstructionsRefused):
        resolve_instructions({"instructions": raw}, THE_MICROVM)


def test_a_plan_that_asks_for_a_derived_list_is_allowed_on_either_backend():
    """The way through, and the reason the refusal is not simply a ban.

    A plan carrying the placeholder makes no claim of its own. The list is built
    from whichever backend is mounted, so the same plan file is correct on both
    and would be correct on a third nobody has written yet.
    """
    plan = {"instructions": A_PARAGRAPH + "\n\n" + PLACEHOLDER}

    for backend in (AgenticV2FixtureBackend, THE_MICROVM):
        resolved = resolve_instructions(plan, backend)
        assert resolved.derived is True
        assert PLACEHOLDER not in resolved.text

    on_fixture = resolve_instructions(plan, AgenticV2FixtureBackend).text
    on_microvm = resolve_instructions(plan, THE_MICROVM).text
    assert on_fixture != on_microvm, (
        "the two backends disagree about exec_run and browser_run, so a "
        "derived list that came out identical would mean it was not derived"
    )


# ---------------------------------------------------------------------------
# A plan that derives its list and then argues with it
# ---------------------------------------------------------------------------


def test_a_derived_plan_that_contradicts_its_own_list_is_refused():
    """The mistake the refusal above invites, made exactly as it would be made.

    The message tells an operator to put the placeholder in. The quickest way
    to do that is to paste it under the paragraph that is already there, which
    produces a plan that says both things at once -- and says the wrong one
    first, in prose, where it reads as the more specific of the two.
    """
    plan = {
        "instructions": (
            "exec_run refuses in this run, every time. No commands run here.\n\n"
            + PLACEHOLDER
        )
    }

    with pytest.raises(InstructionsRefused) as refusal:
        resolve_instructions(plan, THE_MICROVM)

    said = str(refusal.value)
    assert "contradicts it in its own words" in said
    assert "writes its own tool paragraph" not in said, (
        "this plan does carry the placeholder, so the hand-written refusal is "
        "the wrong one to raise and would send the reader to the wrong fix"
    )
    assert "exec_run refuses in this run, every time." in said


def test_the_contradiction_refusal_says_to_delete_the_prose_not_the_placeholder():
    """Two halves, and only one of them is checked against the real methods.

    An operator reading "these two disagree" can resolve it either way. The
    derived half is the one a test holds against the backend's actual methods,
    so the message has to say which half goes.
    """
    plan = {"instructions": "exec_run refuses here.\n\n" + PLACEHOLDER}

    with pytest.raises(InstructionsRefused) as refusal:
        resolve_instructions(plan, THE_MICROVM)

    assert "Delete them." in str(refusal.value)


def test_a_backends_own_derived_paragraph_never_trips_the_contradiction_check():
    """Otherwise the way through closes and no plan can be dispatched at all.

    The check reads the plan as written, before substitution, and this pins
    that. A version that read the finished text would be asking the derived
    paragraph whether it contradicts itself, and the answer is only "no" today
    because of where the full stops happen to fall in the notes -- ``partly``
    tools are in the served set and their notes end with the word "refuses".
    Reword one of those notes and every derived plan becomes undispatchable.
    """
    plan = {"instructions": PLACEHOLDER}

    for backend in (AgenticV2FixtureBackend, THE_MICROVM):
        resolved = resolve_instructions(plan, backend)
        assert resolved.derived is True
        assert contradicted_sentences(resolved.text, backend) == (), (
            f"{backend_name(backend)}'s own paragraph reads as contradicting "
            "itself, so a check placed one line later would refuse every plan"
        )


def test_the_corrected_plan_passes_the_contradiction_check_on_both_backends():
    """The real file, both ways, because it is the one a dispatch names."""
    raw = load_stage_one_plan(THE_CORRECTED_PLAN)["instructions"]
    assert PLACEHOLDER in raw

    for backend in (AgenticV2FixtureBackend, THE_MICROVM):
        assert contradicted_sentences(raw, backend) == ()


def test_the_refusal_quotes_the_sentence_that_would_have_gone_to_the_model():
    """An operator about to spend needs the words, not a list of identifiers.

    The claim this was written for straddles two line breaks in the plan file,
    so the quoting flattens whitespace first. The assertion below is deliberately
    a span that crosses one of them: a shorter one sits inside a single source
    line and passes whether or not anything was flattened, which is how this
    test first shipped unable to see its own subject.
    """
    raw = (
        "You have eight tools.\n"
        "Three of them refuse in this run, every time, with\n"
        "capability_unavailable: exec_run, environment_resolve and\n"
        "environment_activate. No commands run here."
    )

    with pytest.raises(InstructionsRefused) as refusal:
        resolve_instructions({"instructions": raw}, THE_MICROVM)

    said = str(refusal.value)
    assert "What it would send, and what this backend does:" in said
    assert (
        "Three of them refuse in this run, every time, with "
        "capability_unavailable: exec_run, environment_resolve and "
        "environment_activate." in said
    ), "the sentence came back with the plan file's line breaks still in it"


def test_the_refusal_names_both_ways_out():
    """A refusal that does not say what to do instead gets worked around.

    The two ways out are not equivalent and the message says both: dispatch the
    plan that derives its list, or measure this paragraph against the backend
    and put the name in the set. The second is real work; the first is a file
    that already exists and prices the same stages at the same amounts.
    """
    with pytest.raises(InstructionsRefused) as refusal:
        resolve_instructions({"instructions": A_PARAGRAPH}, THE_MICROVM)

    said = str(refusal.value)
    assert PLACEHOLDER in said
    assert "agentic_corrected_harness_plan" in said
    assert "DESCRIBED_BY_HAND_AND_CHECKED" in said


def test_the_set_is_not_a_place_to_put_a_backend_to_get_past_the_refusal():
    """The one thing that would quietly undo all of this.

    Adding a name here is cheaper than measuring the paragraph, and produces a
    green suite either way. The fixture is the only member because it is the
    only backend whose refusals were held against those words; the microVM's
    absence is the finding, not an omission waiting to be tidied up.
    """
    assert DESCRIBED_BY_HAND_AND_CHECKED == {"AgenticV2FixtureBackend"}


def test_the_hand_written_paragraph_is_refused_before_the_width_is_measured():
    """Order, because a plan can fail both and only one refusal is read.

    Being over the priced width is a spending problem and is fixed by editing
    the plan. Being wrong about the backend is fixed by dispatching the other
    plan -- which is also inside the priced width, so the refusal that arrives
    first is the one whose fix resolves both.
    """
    plan = {"instructions": "x" * 401}

    with pytest.raises(InstructionsRefused) as refusal:
        resolve_instructions(plan, THE_MICROVM, priced_characters=400)

    said = str(refusal.value)
    assert "writes its own tool paragraph" in said
    assert "401 characters" not in said


# ---------------------------------------------------------------------------
# The two real plan files, through the real check
# ---------------------------------------------------------------------------


def test_the_plan_that_runs_by_default_is_refused_on_the_isolated_backend():
    """The finding, stated as the thing that stops it.

    ``--plan`` defaults to the stage-one plan, which carries no placeholder and
    tells the model that ``exec_run`` refuses every time and that no commands
    run here. On the microVM ``exec_run`` boots a machine and runs the command.
    A same-host dispatch of that plan is a paid cohort whose pass condition --
    a real command, run in a guest -- the model has been told is impossible.
    """
    plan = load_stage_one_plan(THE_PLAN_THAT_RAN)
    assert PLACEHOLDER not in plan["instructions"]

    with pytest.raises(InstructionsRefused) as refusal:
        resolve_instructions(plan, THE_MICROVM)

    assert (
        "Three of them refuse in this run, every time, with "
        "capability_unavailable: exec_run, environment_resolve and "
        "environment_activate." in str(refusal.value)
    ), (
        "the refusal should quote the real sentence out of the real plan, "
        "flattened, not only the ones a test wrote"
    )


def test_the_same_plan_still_resolves_on_the_fixture_it_ran_on():
    """trial_30's conditions, unchanged. The guard is about where it is sent."""
    plan = load_stage_one_plan(THE_PLAN_THAT_RAN)
    resolved = resolve_instructions(plan, AgenticV2FixtureBackend)
    assert resolved.text == plan["instructions"]


def test_the_corrected_plan_resolves_on_the_isolated_backend_within_its_price():
    """The way through, exercised on the file a dispatch would actually name.

    Both halves matter. A plan that gets past the hand-written refusal and then
    fails the width check is not a way through, and the derived list is longer
    than the placeholder it replaces -- which is the whole reason the width is
    measured after substitution rather than on the plan file.
    """
    from scripts.run_agentic_v2_stage import shared_assumptions

    plan = load_stage_one_plan(THE_CORRECTED_PLAN)
    priced = shared_assumptions(plan).instruction_character_count

    resolved = resolve_instructions(plan, THE_MICROVM, priced_characters=priced)

    assert resolved.derived is True
    assert resolved.characters > resolved.plan_characters
    assert resolved.characters <= priced


def test_the_quoting_does_not_fire_on_a_sentence_about_the_reader():
    """A wrong quote is worse than no quote, and this is where one came from.

    Both plans say "If you cannot do the task, say why in the summary and call
    finalize anyway". It contains a word of inability and names a tool the
    backend serves, and it denies nothing about that tool -- the inability is
    the model's. An operator who checked a refusal quoting this would conclude
    the check was broken, which is a worse outcome than a refusal with no
    examples attached.
    """
    for path in (THE_PLAN_THAT_RAN, THE_CORRECTED_PLAN):
        raw = load_stage_one_plan(path)["instructions"]
        assert "call finalize anyway" in raw, (
            f"{path.name} no longer contains the sentence this test is about; "
            "check whether the quoting still needs to exclude it"
        )
        for quoted in contradicted_sentences(raw, THE_MICROVM):
            assert "call finalize anyway" not in quoted


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
