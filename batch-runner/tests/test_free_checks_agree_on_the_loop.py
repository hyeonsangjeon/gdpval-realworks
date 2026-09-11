"""The two free checks must not give different answers to the same question.

Both of these are printed to whoever is deciding what to do next:

  scripts/check_agentic_stage_one_ceiling.py said the loop exists, that it is
  proven against stand-ins, and that what is missing is a way to reach a real
  model.

  scripts/check_execution_envelope_advance_check.py said "the model never sees
  a tool result and never chooses a next action".

Both ran in the same repository on the same day and only one of them had looked.
The first establishes its answer by running the loop; the second carried a
sentence written before the loop existed, and a sentence is not checked against
anything. A reader had two answers and no way to tell which had been looked up
— and the wrong one pointed at work that was already finished.

These tests hold the two together: they require the answer printed by the
readiness report to be the answer the other check produced, rather than a
second telling of it.

Nothing here calls a model, runs a command, or spends money. The blocks that
keep Agentic Sandbox V2 shut are asserted to still be shut rather than
loosened for the convenience of a test.
"""

from __future__ import annotations

from core.agentic_v2_stage_one_budget import check_stage_one_cannot_reach_a_model
from core.execution_environment_readiness import (
    ENVIRONMENT_AGENTIC_SANDBOX_V2,
    STATUS_STRUCTURE_CHECK_ONLY,
    check_agentic_sandbox_v2_blocks_are_intact,
    inspect_environment_support,
)
import core.execution_environment_readiness as readiness


def _agentic_entry():
    return next(
        entry
        for entry in inspect_environment_support()
        if entry.environment == ENVIRONMENT_AGENTIC_SANDBOX_V2
    )


# ── The two checks agree ──────────────────────────────────────────────────


def test_the_two_free_checks_give_the_same_answer_about_reaching_a_model():
    """Not "agree in substance" — the same words, because it is one answer.

    Matching on the sentence itself is deliberate. Two checks that reach the
    same conclusion by separate routes can drift apart the moment one of the
    routes changes, which is what happened here. One of them now asks the
    other, and this is what says so.

    Checked in both directions, and the second direction is the one that
    matters now. The stage-one check returns nothing today — a real model can
    be reached and the amounts are approved — so requiring the readiness report
    to print what it said would pass on an empty list without looking at
    anything. What is required instead is that the report says nothing about
    reaching a real model *except* what the other check produced. An empty
    answer copied faithfully is still one answer; a sentence the report made up
    on its own is the drift this file exists to stop.
    """
    settled = check_stage_one_cannot_reach_a_model()
    blockers = _agentic_entry().blockers

    for sentence in settled:
        assert sentence in blockers, (
            "the readiness report no longer prints what the stage-one check "
            f"established; it is missing {sentence!r}"
        )
    invented = [
        note
        for note in blockers
        if "reach a real model" in note or "no amount has been approved" in note
        if note not in settled
    ]
    assert invented == [], (
        "the readiness report is making its own claim about reaching a real "
        f"model instead of asking: {invented!r}"
    )


def test_the_report_does_not_say_the_loop_is_missing_while_the_loop_exists():
    """The exact claim that went stale, named so a return of it fails here."""
    from core.agentic_v2_conversation import run_model_conversation

    assert callable(run_model_conversation)

    entry = _agentic_entry()
    for note in list(entry.blockers) + list(entry.evidence):
        assert "never sees a tool result" not in note, (
            f"the report says the loop does not exist: {note!r}"
        )
        assert "never chooses a next action" not in note, (
            f"the report says the loop does not exist: {note!r}"
        )


# ── Three claims, three blockers ──────────────────────────────────────────


def test_the_three_claims_are_three_blockers_rather_than_one_sentence():
    """One sentence holding three claims hides which of the three moved.

    Opening the command tool, reaching a real model and obtaining an approval
    are three different pieces of work with three different people behind them.
    While they shared a sentence, finishing one of them changed nothing in the
    report — which is how the finished one went on being listed as outstanding.

    Two of the three have since been finished, and the report shows it by
    saying less: the model sentence is gone entirely, and the approval sentence
    narrowed to the pipeline route that really is still shut. That is the
    behaviour being pinned. A blocker that reappears without the fact behind it
    coming back fails here, and so does a blocker that stays flat while the
    fact under it moves — which is what this test was written about.
    """
    entry = _agentic_entry()
    blockers = entry.blockers

    holding_the_command_tool = [note for note in blockers if "exec_run" in note]
    holding_the_model = [note for note in blockers if "real model" in note]
    holding_the_approval = [note for note in blockers if "not approved" in note]

    assert len(holding_the_command_tool) == 1
    # Nothing stands between this environment and a real model any more, so
    # there is no sentence for it. Established by asking rather than by the
    # absence itself: if the other check starts finding something again, the
    # test above requires the report to carry it and this one to see it.
    assert holding_the_model == check_stage_one_cannot_reach_a_model()
    assert len(holding_the_approval) == 1

    # Still separate sentences, which is the original point.
    assert len(set(blockers)) == len(blockers)
    assert not any(
        "no approval exists to use this environment in a real experiment" in note
        for note in blockers
    ), "the approval blocker went back to the wording that outlived its fact"


def test_the_approval_blocker_names_the_route_that_is_shut_and_the_one_that_is_not():
    """An approval that exists must not be reported as though it does not.

    Stage one is approved — two amounts, written in the plan. What is still
    shut is reaching this environment through an experiment YAML. A blocker
    that said neither was approved would send somebody to ask for permission
    they already have, which is how the old sentence read for the whole of the
    day after the approval landed.
    """
    blocker = next(note for note in _agentic_entry().blockers if "not approved" in note)

    assert "ordinary experiment pipeline" in blocker
    assert "step2_run_inference" in blocker
    assert "core.executor" in blocker
    # And it points at where the approval that does exist lives.
    assert "agentic_stage_one_plan.yaml" in blocker
    assert "run_agentic_v2_stage.py" in blocker


def test_the_command_tool_blocker_says_it_was_called_rather_than_described():
    blocker = next(note for note in _agentic_entry().blockers if "exec_run" in note)

    assert "called here" in blocker
    assert "capability is unavailable" in blocker


# ── What happens when an observation comes back wrong ─────────────────────


def test_a_block_that_opened_is_reported_instead_of_the_reassuring_sentence(
    monkeypatch,
):
    """The point of observing rather than asserting, stated as a test.

    A sentence would have gone on saying the tool was closed. What is there now
    reports what it found, so a block that opened reaches the report.
    """
    monkeypatch.setattr(
        readiness,
        "check_agentic_sandbox_v2_blocks_are_intact",
        lambda: ["the exec_run command tool accepted an ordinary command"],
    )
    blockers = _agentic_entry().blockers

    assert "the exec_run command tool accepted an ordinary command" in blockers
    assert not any("exec_run is closed" in note for note in blockers)


def test_an_unanswerable_question_is_reported_rather_than_passed_over(monkeypatch):
    """Not being able to check is not the same as there being nothing to find.

    If the module that settles this cannot be loaded, the honest report is that
    a real model has to be treated as reachable until somebody looks — not
    silence, which reads as though the question was asked and came back clear.
    """

    def cannot_load(module_name, attribute):
        raise ImportError(f"no module named {module_name}")

    monkeypatch.setattr(readiness, "_import_attribute", cannot_load)
    problems = readiness._why_a_real_model_is_out_of_reach()

    assert len(problems) == 1
    assert "has to be treated as reachable until somebody checks" in problems[0]


def test_a_determination_that_raises_is_reported_rather_than_passed_over(
    monkeypatch,
):
    def explodes():
        raise RuntimeError("something changed underneath")

    monkeypatch.setattr(
        readiness,
        "_import_attribute",
        lambda module_name, attribute: explodes,
    )
    problems = readiness._why_a_real_model_is_out_of_reach()

    assert len(problems) == 1
    assert "has to be treated as reachable until somebody checks" in problems[0]
    assert "RuntimeError" in problems[0]


# ── Nothing was opened to make any of the above true ──────────────────────


def test_this_run_place_is_still_structure_check_only_and_still_shut():
    """Reporting a blocker more accurately must not remove one."""
    assert check_agentic_sandbox_v2_blocks_are_intact() == []
    assert _agentic_entry().status == STATUS_STRUCTURE_CHECK_ONLY


def test_the_evidence_says_the_blocks_were_run_rather_than_read():
    evidence = _agentic_entry().evidence

    assert any("run rather than read" in note for note in evidence)
    assert any("exec_run" in note for note in evidence)
    assert any(
        "check_stage_one_cannot_reach_a_model" in note for note in evidence
    )
