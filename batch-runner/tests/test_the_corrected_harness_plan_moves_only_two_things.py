"""The corrected-harness plan against the plan it was copied from.

``agentic_stage_one_plan.yaml`` ran trial_30 (GitHub run 34671538199): 30 tasks,
11 finished, 19 did not, $6.13 charged. Two defects in that harness end tasks
for reasons unrelated to anything the plan was testing -- an instruction
paragraph that is wrong about which tools refuse, and a replay format the model
imitates instead of calling a tool. ``agentic_corrected_harness_plan.yaml``
fixes both, in a new file with its own run id.

That makes two files whose relationship is the whole point, and this holds it.

**Nothing moves in the plan that already ran.** Its parsed content and its
instruction text are pinned by digest. A plan describing a run that happened is
a record of what happened; editing it makes the run unreadable afterwards, and
the comparison this one exists to support would be against a condition nobody
can reconstruct. The digest is over the *parsed* mapping, so a comment or a
reflow is allowed and a changed value is not.

**Exactly three things differ in the new one**, and each is accounted for: the
instruction text, one new key in ``fixed_settings``, and the experiment record.
The cost block, the stage figures, the model, the connection and the cohort are
identical objects -- so this plan cannot quietly raise its own ceiling, and
"the same conditions except the harness" is checkable rather than asserted.

**The record answers the questions the design asks**, including the ones whose
honest answer is that nobody knows. This paragraph used to end "``repeats`` is
``undecided`` with the consequence written out, rather than a number with
nothing behind it", and half of that is now wrong: leaving the slot open meant
the design had no stated end and nobody could say in advance what would be
spent. ``repeats`` is ``3`` with what three does not buy written beside it, and
the questions that really have no answer are gathered in ``open_questions``
instead of being spread through the fields that do.

Offline. Two YAML files, a digest and a string builder. Nothing here calls a
model, resolves a cohort or costs anything.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from core.agentic_v2_call_agreement import describe, the_stop_rule
from core.agentic_v2_fixture_backend import AgenticV2FixtureBackend
from core.agentic_v2_instructions import file_digest, resolve_instructions
from core.agentic_v2_manifest_binding import STAGE_FIVE, STAGE_SIZES, STAGE_THIRTY
from core.agentic_v2_model_voice import REPLAY_FORMATS, AzureFoundryVoice
from core.agentic_v2_reporting_rules import THE_EN_CHAIN, THE_KO_CHAIN
from core.agentic_v2_tool_availability import PLACEHOLDER
from core.execution_envelope_cost import CostAssumptions

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
ENVELOPE = BATCH_RUNNER_ROOT / "experiments" / "execution_envelope"

THE_PLAN_THAT_RAN = ENVELOPE / "agentic_stage_one_plan.yaml"
THE_CORRECTED_PLAN = ENVELOPE / "agentic_corrected_harness_plan.yaml"

#: sha256 of ``THE_PLAN_THAT_RAN``'s parsed content, canonically encoded.
#: Changing a value under it changes what trial_30 is recorded as having run
#: under. The fix when this fails is a new plan file, which is what the file
#: beside it already is.
THE_PLAN_THAT_RAN_PARSES_TO = (
    "d128b034065353ad4af510768d7945f44514d88cdf7636fcdf9410ba64db4b3b"
)

#: sha256 of the exact instruction bytes trial_30 sent, before anything derived
#: a list. Pinned separately because this is the one field that reached the
#: model on every turn of every task.
TRIAL_30_SENT_THESE_INSTRUCTIONS = (
    "222d0ffaa43e1156c305c1ff0164c0f7dd3544b0f06b565d0ff2475c4e2d51f8"
)

#: The headings ``experiment-design`` §11 asks an experiment to answer before
#: it runs, in this repository's names for them. The comment above this tuple
#: used to say "the eight headings" while the tuple held twelve, which is the
#: same lag this file exists to catch one level up; the count is left to the
#: tuple now.
THE_DESIGN_RECORD_ASKS = (
    "decision",
    "falsification",
    "moving",
    "fixed",
    "denominator",
    "adjudication",
    "units",
    "inputs",
    "repeats",
    "run_list",
    "stop_rules",
    "known_confounds",
    # Not one of §11's rows. §11 asks what the design knows; the skill's ten
    # questions are about what it does not, and an answer that does not exist
    # is only recorded if there is somewhere to record it.
    "open_questions",
)

#: Settings that would decide whether a repeat is a repeat. Checked against the
#: request that is actually built rather than against the plan alone, because a
#: plan that pins none and a voice that sends none are two different silences.
THE_SAMPLING_CONTROLS = ("temperature", "top_p", "seed")

#: trial_30's settled charge, as it is written in ``run_list_note``. A string
#: rather than a float: the test asks whether the note quotes this figure, not
#: whether some number is close to it.
PAST_CHARGE = "6.131815"


def _load(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), f"{path.name} is not a mapping"
    return loaded


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@pytest.fixture(scope="module")
def ran() -> dict[str, Any]:
    return _load(THE_PLAN_THAT_RAN)


@pytest.fixture(scope="module")
def corrected() -> dict[str, Any]:
    return _load(THE_CORRECTED_PLAN)


# ---------------------------------------------------------------------------
# The plan that already ran
# ---------------------------------------------------------------------------


def test_the_plan_that_ran_trial_30_still_parses_to_what_it_ran(ran):
    assert _canonical_digest(ran) == THE_PLAN_THAT_RAN_PARSES_TO, (
        "a value in the plan trial_30 ran under has changed. Whatever the new "
        "value is, run 34671538199 did not use it, and every comparison "
        "against that run now describes conditions it was not run in. Put the "
        "change in a new plan file with its own run id"
    )


def test_what_trial_30_sent_the_model_is_unchanged(ran):
    text = str(ran["instructions"])
    assert hashlib.sha256(text.encode("utf-8")).hexdigest() == (
        TRIAL_30_SENT_THESE_INSTRUCTIONS
    )
    assert PLACEHOLDER not in text, (
        "the plan that ran does not ask for a derived list and must not start; "
        "it is a record of a hand-written paragraph that was sent 305 times"
    )


# ---------------------------------------------------------------------------
# What the new plan moves
# ---------------------------------------------------------------------------


def test_exactly_three_things_differ(ran, corrected):
    """Named one at a time, so a fourth appearing has to be argued for."""
    differing = {
        key
        for key in set(ran) | set(corrected)
        if ran.get(key) != corrected.get(key)
    }
    assert differing == {"instructions", "fixed_settings", "experiment_record"}


def test_the_ceiling_the_cohort_and_the_model_are_the_same_objects(ran, corrected):
    """This plan cannot raise its own approval, or quietly bind a smaller run.

    ``cost`` carries the approved amounts and the shared assumptions they were
    worked out from; ``stages`` carries the per-stage figures the gate reads.
    Both identical means the corrected run is priced by the arithmetic that
    priced the one it is compared against.
    """
    for key in (
        "cost",
        "stages",
        "model",
        "azure_connection",
        "candidate_settings",
        "task_ids",
        "safety_blocks_must_stay_closed",
        "after_stage_one",
        "plan_version",
    ):
        assert ran[key] == corrected[key], f"{key} moved and it should not have"


def test_the_only_new_setting_is_the_replay_format(ran, corrected):
    before, after = ran["fixed_settings"], corrected["fixed_settings"]
    assert set(after) - set(before) == {"replay_format"}
    assert {key: after[key] for key in before} == before, (
        "a setting that both plans carry has a different value in the new one"
    )
    assert after["replay_format"] == "faithful"
    assert after["replay_format"] in REPLAY_FORMATS


def test_the_new_plan_asks_for_a_derived_list(corrected):
    assert PLACEHOLDER in str(corrected["instructions"])


def test_the_derived_paragraph_names_the_tool_twelve_tasks_called(corrected):
    """``browser_run`` is absent from the paragraph trial_30 sent.

    Twelve of its nineteen failures called it. What the derived list says about
    it on this backend -- open for three local operations, refusing the two
    that need a network -- is the substance of the first fix, so it is checked
    rather than assumed to follow from the placeholder being present.
    """
    resolved = resolve_instructions(corrected, AgenticV2FixtureBackend)
    assert "browser_run" in resolved.text
    assert "open_local" in resolved.text
    assert resolved.derived is True
    assert resolved.backend == "AgenticV2FixtureBackend"


def test_the_derived_text_fits_the_width_it_was_priced_at(corrected):
    """The check the runner makes before spending, made here for free.

    A derived list is longer than the placeholder it replaces, so the literal
    plan text is not a safe thing to measure. Every figure under ``cost:`` was
    worked out at ``instruction_character_count``, and the text goes out once
    per turn on every task in the cohort.
    """
    shared = _load(BATCH_RUNNER_ROOT / str(corrected["cost"]["assumptions_come_from"]))
    priced = CostAssumptions.from_mapping(shared["cost"]["assumptions"])

    resolved = resolve_instructions(
        corrected,
        AgenticV2FixtureBackend,
        priced_characters=priced.instruction_character_count,
    )
    assert resolved.plan_characters < resolved.characters
    assert resolved.characters <= priced.instruction_character_count


def test_the_record_names_the_file_it_read(corrected):
    """Two digests, and they are different facts.

    ``file_digest`` says which file was on disk. The instruction digest says
    what left the machine. The preregistration seals only the default plan, so
    a ``--plan`` run is described by its own run record and nothing else.
    """
    resolved = resolve_instructions(corrected, AgenticV2FixtureBackend)
    identity = resolved.identity()

    assert file_digest(THE_CORRECTED_PLAN) != identity["sha256"]
    assert identity["characters"] == len(resolved.text)
    assert identity["derived_for_backend"] == "AgenticV2FixtureBackend"
    assert identity["declared_but_never_run_here"] == [], (
        "the fixture's tools are all called for real in "
        "test_the_declared_refusals_match_what_the_backends_do.py"
    )


# ---------------------------------------------------------------------------
# The experiment record
# ---------------------------------------------------------------------------


def test_the_record_answers_every_heading_before_the_run(corrected):
    record = corrected["experiment_record"]
    missing = [key for key in THE_DESIGN_RECORD_ASKS if not record.get(key)]
    assert missing == [], f"the design record has nothing under {missing}"


def test_repeats_is_a_decision_that_states_what_it_does_not_buy(corrected):
    """``experiment-design`` §4 asks for the spread before the comparison.

    This field used to read ``undecided``, on the reasoning that trial_30 ran
    once and any number would have nothing behind it. Half of that still
    holds and is why this test exists in its present form: no number here is
    justified by a power calculation, and the note has to say so in the same
    breath as the number, or the number will be read as one that was.

    The other half was a mistake. Leaving it open meant the design had no
    stated end and nobody could say in advance what would be spent, which is
    not caution. So the slot carries a concrete count, and the guard moves
    from "refuse a number" to "refuse an unqualified number".
    """
    record = corrected["experiment_record"]
    repeats = record["repeats"]

    assert isinstance(repeats, int), "an operational choice, not a word"
    assert repeats >= 2, "one run has no spread to estimate"

    note = record["repeats_note"].lower()
    assert "not statistical power" in note or "not statistical power" in note.replace(
        ",", ""
    )
    for disclaimed in ("confidence interval", "significance"):
        assert disclaimed in note, (
            f"the note must say the three repeats do not buy a {disclaimed}"
        )


def test_the_run_list_is_finite_and_says_which_entries_spend(corrected):
    """The list is the only thing bounding how many times the gate is paid.

    The per-stage ceiling has no memory: it cannot tell a first trial_30 from
    a third, and each run passes it on its own. So a list that grew by one
    entry unnoticed would spend one more approval unnoticed, and this test is
    what makes that a failure rather than a surprise.
    """
    record = corrected["experiment_record"]
    runs = record["run_list"]

    assert isinstance(runs, list) and runs
    assert all(set(run) >= {"id", "what", "paid"} for run in runs)
    assert len({run["id"] for run in runs}) == len(runs)

    paid = [run for run in runs if run["paid"]]
    assert [run["id"] for run in runs if not run["paid"]] == ["rehearsal"]

    # One compatibility run and exactly `repeats` runs of the cohort. Spelled
    # out rather than counted loosely, so a fourth repeat has to be written
    # here as well as there.
    repeats = record["repeats"]
    assert len(paid) == 1 + repeats, (
        "the paid entries are one compatibility run plus the declared repeats; "
        "any other count is an approval nobody wrote down"
    )

    at_stage = [run["stage"] for run in paid]
    assert at_stage.count(STAGE_FIVE) == 1
    assert at_stage.count(STAGE_THIRTY) == repeats

    for run in paid:
        assert run["stage"] in STAGE_SIZES
        assert run["stage"] in corrected["stages"]

    # Every repeat after the first is conditional, and says on what.
    cohort_runs = [run for run in paid if run["stage"] == STAGE_THIRTY]
    for run in cohort_runs:
        assert run.get("requires"), f"{run['id']} spends without naming its gate"


def test_the_scale_expectation_names_the_format_it_was_measured_under(corrected):
    """A bill rung up under the old format cannot be quoted at the new one.

    ``run_list_note`` reaches for trial_30's actual charge to say what three
    repeats will cost. That charge was rung up under ``paraphrase``; this plan
    sets ``replay_format`` to ``faithful``, and six hundred lines above, the
    same file puts the difference between them at +719,526 input tokens. The
    first version of this note carried the figure across without mentioning
    that anything had moved, which left the expectation short by about a
    third -- the two sentences are far enough apart that nobody reading
    either one alone would see it.

    **The ceilings are not what this guards, and are not affected.** They
    were always computed as though every past argument were re-sent at full
    length, so the format change does not move them and none is re-derived.
    The one sentence that says "for scale" is the whole of it.

    The old format is read from the plan that ran rather than spelled here,
    so that if the default ever changes under it, this fails instead of
    quietly comparing the wrong pair.
    """
    note = corrected["experiment_record"]["run_list_note"]

    if PAST_CHARGE not in note:
        return  # the note stopped quoting it; there is nothing to reconcile

    default_format = next(
        field.default
        for field in dataclasses.fields(AzureFoundryVoice)
        if field.name == "replay_format"
    )
    ran_under = _load(THE_PLAN_THAT_RAN)["fixed_settings"].get(
        "replay_format", default_format
    )
    runs_under = corrected["fixed_settings"]["replay_format"]

    assert ran_under in REPLAY_FORMATS and runs_under in REPLAY_FORMATS
    if ran_under == runs_under:
        return  # same axis; the figure carries across unadjusted after all

    assert ran_under in note, (
        f"the note quotes {PAST_CHARGE} USD but never says it was measured "
        f"under {ran_under!r}, so it reads as this plan's own expectation"
    )
    assert runs_under in note, (
        f"the note has to name the format this plan actually sets "
        f"({runs_under!r}) beside the one the figure came from"
    )
    assert "ceiling" in note.lower(), (
        "an adjusted expectation sitting alone reads as a raised limit; the "
        "note must keep saying the ceilings are elsewhere and unchanged"
    )


def test_the_repeats_are_gated_on_compatibility_ledger_and_source(corrected):
    """Three gates, checked before each dispatch rather than argued after.
    Named here because a gate that exists only in a sentence somewhere gets
    skipped by whoever is in a hurry.
    """
    gates = corrected["experiment_record"]["run_list_gates"].lower()
    assert "compatibility" in gates
    assert "ledger" in gates and "receipt" in gates
    assert "source integrity" in gates and "sha256" in gates
    assert "model_calls_not_counted" in gates, (
        "the ledger gate must be the invariant the stop rules use, not equality"
    )


def test_the_confounds_include_the_one_that_is_easiest_to_forget(corrected):
    """That the hypothesis and its evidence come from the same 9 cases.

    trial_30's text-only endings are what suggested the replay format was
    being imitated. A run designed from them is a test of a hypothesis formed
    on the data it is being tested against, which is a real limit on what the
    result can say and is not visible anywhere in the numbers.
    """
    confounds = corrected["experiment_record"]["known_confounds"]
    assert "same data" in confounds
    assert "not independent evidence" in confounds
    assert "concurrent control" in confounds


def test_the_refusal_count_is_written_down_as_a_ceiling_not_a_measurement(
    corrected,
):
    """The confound the corrected plan could not have had when it was drafted.

    A refused call ends the task before the model is asked again, so the
    tasks counted under ``falsification`` (c) are not the tasks the tool
    policy cost anything. They are those *plus* every task that would have
    read the refusal and got on with something else, and nothing in the run
    separates the two because neither is given the turn that would. Reported
    as a measurement it overstates the policy's effect by an unknown amount;
    reported as a ceiling it is honest and still useful.

    Pinned here because the plan is the artefact a reader reaches for, and a
    limit that lives only in a test file is a limit nobody reads.
    """
    confounds = corrected["experiment_record"]["known_confounds"]

    assert "upper bound" in confounds
    assert "not a measure of it" in confounds
    assert "one_failed_tool_call_ends_the_task" in confounds
    assert "test_one_failed_tool_call_ends_the_task.py" in confounds


def test_the_frozen_success_criterion_is_read_with_the_refusal_in_mind(
    ran, corrected
):
    """``after_stage_one`` is identical in both plans, and has to stay that way.

    Its criterion asks for a test showing the model was asked again with a
    tool result in front of it. Read loosely that is refusal recovery, which
    no run produces. The fix is not to edit the criterion -- moving it would
    break the one property this plan is built on, that it differs from the
    plan trial_30 ran under in exactly two places -- but to say in the record
    which reading is the live one.
    """
    assert ran["after_stage_one"] == corrected["after_stage_one"], (
        "the criterion is frozen; the clarification belongs in the record"
    )

    confounds = corrected["experiment_record"]["known_confounds"]
    assert "after_stage_one" in confounds
    assert "ok one" in confounds


def test_the_ending_is_checked_against_the_paid_run_and_not_only_the_fixture(
    corrected,
):
    """The same finding, read off trial_30's record instead of a scripted one.

    ``test_one_failed_tool_call_ends_the_task.py`` proves the rule against the
    real runner, but with a scripted voice and the offline backend, and the
    plan's own line about fixture results being harness diagnostics applies to
    it as much as to anything else. trial_30 is the counterpart: 296 requests,
    282 answers, every answer ok, and a 14-call gap that is the 14 attempts
    which stopped on a tool call. A not-ok result was never handed back in a
    run that was paid for.

    The arithmetic is in the record rather than the counts alone, because
    "0 refusals were handed back" and "no refusal can be handed back" read the
    same and only one of them is what happened.
    """
    confounds = corrected["experiment_record"]["known_confounds"]

    assert "296" in confounds and "282" in confounds
    assert "_EndTheRun" in confounds
    assert "was ever handed a not-ok result" in confounds


def test_the_record_separates_ending_the_attempt_from_ending_the_task(
    corrected,
):
    """Because trial_30 contains a task that was refused and finished anyway.

    Not the behaviour the plan wants to measure -- the model never read the
    refusal -- but a second attempt did the task. The attempt is what a tool
    call ends. The task ends because ``capability_unavailable`` closes as
    ``terminal_capability_absent`` and that disposition is not retried, which
    is a retry policy and not the dispatcher's rule. Written down separately
    so that a change to the retry policy is not mistaken for a change to the
    dispatcher.
    """
    confounds = corrected["experiment_record"]["known_confounds"]

    assert "What ends is the attempt" in confounds
    assert "terminal_capability_absent" in confounds
    assert "invalid_arguments" in confounds
    assert "fixture_backend_error" in confounds
    assert "tool_desk_broke" in confounds


def test_the_record_says_which_tool_count_belongs_to_which_attempt(corrected):
    """The metrics field that would have been quoted as a per-task count.

    ``agentic_metrics.tool_calls`` is the last attempt's number on all 30 of
    trial_30's tasks. Summed it reads 155 against 296 actual calls, and the
    rows where it is wrong are the rows that retried -- the same rows whose
    cost figure *does* cover every attempt. A table mixing the two would
    divide a whole-task cost by a last-attempt call count and read as a
    per-call price.
    """
    confounds = corrected["experiment_record"]["known_confounds"]

    assert "agentic_metrics.tool_calls" in confounds
    assert "155" in confounds
    assert "conservative_cost_usd" in confounds
    assert "tool_errors is not a refusal count" in confounds


def test_the_denominator_is_all_thirty_and_the_subset_is_labelled(corrected):
    record = corrected["experiment_record"]
    assert "All 30 tasks" in record["denominator"]
    assert "exploratory" in record["denominator"]


def test_finalize_being_called_is_not_recorded_as_work_done(corrected):
    """Three questions, reported separately and never summed.

    A file saying the model could not do the task is a called ``finalize`` and
    a collected deliverable, and it is not a task done well. Nothing in this
    run measures the third thing, and the record says so rather than leaving
    the first two to be read as it.
    """
    adjudication = corrected["experiment_record"]["adjudication"]
    assert "never summed" in adjudication
    assert "no judge is run" in adjudication


def test_the_disclaimer_case_is_named_from_a_run_and_not_described(corrected):
    """A rule with an example in it is harder to read past.

    "A file saying the model could not do the task" is abstract enough to be
    agreed with and then not applied. trial_30 has one: a task filed as a
    success whose two deliverables are named ``README_LIMITATION.txt`` and
    ``DELIVERABLE_NOTE.txt``. Naming it puts a number on the reader's screen
    that the success count cannot separate.
    """
    adjudication = corrected["experiment_record"]["adjudication"]

    assert "38889c3b" in adjudication
    assert "README_LIMITATION.txt" in adjudication
    assert "no way to say how many" in adjudication


def test_a_cause_is_not_read_off_the_stop_reason(corrected):
    """The units line said to count causes by ``stop_reason``. It cannot be.

    ``tool_desk_broke`` is what the conversation loop files a refusal, a
    malformed call and a broken backend under, and trial_30 contains one of
    each. Counting causes that way reports a policy refusal and a defect of
    ours as the same event -- the exact error the refusal column was added to
    prevent, reintroduced one field lower down.
    """
    units = corrected["experiment_record"]["units"]

    assert "not from the conversation's stop_reason" in units
    assert "tool_desk_broke" in units
    assert "error_type and disposition" in units
    assert "agentic_metrics.tool_calls" in units


def test_the_stop_rule_about_the_bill_names_a_check_that_exists(corrected):
    """And the check it names behaves the way the plan says it does.

    The first draft of this rule said "stop if the cost ledger and the voice's
    own call count disagree", which is a rule no run should obey. A reply that
    comes back without usable token counts leaves the voice no row and still
    reaches the bill, so plain equality halts a healthy run at the first
    unreported usage -- and the wording is the whole of the rule, because
    nothing reads it but a person.

    So the sentence is held to the module it names, and the module is run on
    the case that would have tripped the old wording.
    """
    rules = corrected["experiment_record"]["stop_rules"]
    assert "core.agentic_v2_call_agreement.the_stop_rule" in rules
    assert "model_calls_not_counted" in rules, (
        "the term that makes the two counts differ legitimately is the rule"
    )

    one_reply_never_said_what_it_used = {
        "model_calls": {
            "per_attempt": [
                {
                    "task_id": "a-task",
                    "attempt": 1,
                    "calls": [{"input_tokens": 400, "output_tokens": 31}],
                }
            ]
        },
        "conversations": {
            "conversations": {"a-task#1": {"model_calls_not_counted": 1}}
        },
        "run": {
            "results": [
                {
                    "task_id": "a-task",
                    "problem_solving_cost": {
                        "status": "complete",
                        "model_calls": 2,
                        "usage": {"input_tokens": 400, "output_tokens": 31},
                    },
                }
            ]
        },
    }

    verdict = the_stop_rule(one_reply_never_said_what_it_used)
    assert verdict["agree"] is True, (
        "the rule as written must not stop this run: " + describe(verdict)
    )
    # ... and the wording it replaced would have.
    row = verdict["rows"][0]
    assert row["voice_counted"] != row["ledger_counted"]


def test_the_stop_rule_says_the_earliest_it_can_fire(corrected):
    """Because "stop" reads as halting the next call, and it cannot.

    A receipt is written when a task settles. Anything this check sees is
    already paid for, so what it can stop is the next task.
    """
    rules = corrected["experiment_record"]["stop_rules"]
    assert "after a task settles" in rules
    assert "never the next call" in rules


def test_the_reporting_rule_names_the_chains_in_the_order_they_run(corrected):
    """And names them as the module has them, not as prose remembers them.

    The order is the rule: the structure skill places the claims and the
    editors smooth the sentences carrying them. Reversed, the copy-edit is
    thrown away by the rewrite that follows it.
    """
    reporting = corrected["experiment_record"]["reporting"]
    for skill in THE_KO_CHAIN + THE_EN_CHAIN:
        assert skill.split(":")[0] in reporting, f"{skill} is not in the record"

    korean = [reporting.index(one.split(":")[0]) for one in THE_KO_CHAIN]
    english = [reporting.index(one.split(":")[0]) for one in THE_EN_CHAIN]
    assert korean == sorted(korean)
    assert english == sorted(english)


def test_the_reporting_rule_forbids_a_figure_before_it_is_measured(corrected):
    """The half of the rule that a person can get wrong without noticing.

    An outline pre-filled with the numbers the writer expects is the ordinary
    way this fails, and it is invisible afterwards -- the draft reads like a
    report of a run. So the record says the pre-run artefact carries no figure
    at all, and names the check that holds the post-run one.
    """
    reporting = corrected["experiment_record"]["reporting"]
    assert "not even as examples" in reporting
    assert "check_every_figure" in reporting
    assert "true figure in a false sentence" in reporting, (
        "the record has to say what the check cannot do, or passing it reads "
        "as the report being right"
    )


# ---------------------------------------------------------------------------
# The header, which is a comment and so is read by nothing else
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def header() -> str:
    """The plan's opening comment block, as text.

    Every other test in this file reads parsed YAML, so the twenty-four lines
    a person actually reads first are the only part of the plan nothing holds
    to anything. They carry the two figures that motivate the run.
    """
    raw = THE_CORRECTED_PLAN.read_text(encoding="utf-8")
    return raw.split("# ── What this run can and cannot say")[0]


def test_the_two_motivating_figures_each_carry_their_denominator(header):
    """Twelve and nine count different things, and sit four lines apart.

    Twelve is tasks out of thirty. Nine is attempts, across five tasks, and
    an attempt is not a task here: the retry layer decides the task, and only
    a `capability_unavailable` disposition is certain to carry its attempt's
    ending through to it. A reader who takes nine as a task count reads 30%
    of the cohort where the tasks affected were 17% of it.

    This is the conflation `experiment_record.falsification` and `units`
    already correct further down the same file, so the header getting it
    wrong would be the plan disagreeing with itself.
    """
    assert "Twelve of trial_30's thirty tasks" in header
    assert "Nine\n#    attempts in trial_30, across five of its thirty tasks" in header, (
        "the attempt figure lost its denominator; beside a task count four "
        "lines above, nine then reads as nine tasks"
    )


def test_the_caveat_is_the_section_directly_after_the_two_changes(header):
    """The one claim this run is not allowed to make, in the place it would be made.

    The header is where a combined change gets described as two improvements,
    and a reader who stops after the numbered list would carry that away. So
    the list is not allowed to end the reading: the section that says the two
    axes cannot be told apart has to be the next thing on the page, not a
    paragraph further down that a skimmer never reaches.
    """
    raw = THE_CORRECTED_PLAN.read_text(encoding="utf-8")
    after = raw[len(header):]
    assert after.startswith("# ── What this run can and cannot say")
    assert "Two axes move at once" in after[:600], (
        "the caveat moved away from the change list it qualifies"
    )
    # And the header itself must not have made the claim first.
    assert "improvement" not in header.lower()


# ---------------------------------------------------------------------------
# What the record cannot answer
#
# ``experiment-design`` ends by asking which of its ten questions have no
# answer. A design that never writes that down does not stop having the gaps;
# it stops being able to see them, and every gap then gets discovered in the
# report instead, where it reads as a result being walked back.
# ---------------------------------------------------------------------------


def _payload_keys_the_voice_sends() -> list[str]:
    """The request body, read out of the source rather than listed here.

    Built by parsing rather than by importing and calling, because calling it
    needs a client and a live route, and this file is offline. What matters is
    that the plan's sentence about the request cannot drift from the request:
    add a key in ``agentic_v2_model_voice.py`` and the assertion below is the
    thing that notices.
    """
    import ast

    source = (BATCH_RUNNER_ROOT / "core" / "agentic_v2_model_voice.py").read_text(
        encoding="utf-8"
    )
    for node in ast.walk(ast.parse(source)):
        is_payload = (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "payload"
            and isinstance(node.value, ast.Dict)
        )
        if is_payload:
            return [key.value for key in node.value.keys]
    raise AssertionError("the voice no longer builds a literal payload mapping")


def test_the_record_says_what_it_cannot_answer_instead_of_answering_it(corrected):
    """The rule the field is written under, kept in the field.

    Without it the slot is a place to put a guess. An unanswered question that
    has been given a plausible answer is worse than one left blank, because
    the blank is visible from the outside and the guess is not.
    """
    questions = corrected["experiment_record"]["open_questions"]

    assert "recorded as unanswered" in questions
    assert "invented" in questions
    # Each gap has to say what would close it, or it is a complaint.
    assert questions.count("What would answer it") >= 3


def test_the_sampling_question_is_read_off_the_request_that_is_actually_sent(
    corrected,
):
    """Three repeats of "the identical condition", and nothing pins the sampling.

    The plan sets no temperature, no ``top_p`` and no seed, and neither does
    the voice -- so there is no setting whose effect could be checked, which is
    a different situation from a setting that was set and ignored. The keys are
    derived from the source so that adding one lands here: a ``temperature``
    appearing in that payload would make the plan's sentence false and would
    also change what the three repeats measure.
    """
    record = corrected["experiment_record"]
    questions = record["open_questions"]
    sent = _payload_keys_the_voice_sends()

    for control in THE_SAMPLING_CONTROLS:
        assert control not in sent, (
            f"the voice now sends {control}; the open question about repeats "
            "is stated on the basis that it does not"
        )
        assert control not in corrected["fixed_settings"]
        assert control not in corrected["model"]
        assert control in questions, (
            f"{control} is one of the settings whose absence the question is "
            "about, and the question does not name it"
        )

    for key in sent:
        assert key in questions, (
            f"the request carries {key} and the record's description of it "
            "does not; a list that is nearly the request is worse than none"
        )
    assert "agentic_v2_model_voice.py" in questions


def test_the_repeat_count_is_the_number_of_repeat_entries_on_the_list(corrected):
    """``repeats: 3`` and three entries are one decision written twice.

    They are in different fields and a reader takes whichever they read first,
    so a fourth entry added without touching ``repeats`` would put a fourth
    paid run behind a number that still says three.
    """
    record = corrected["experiment_record"]
    repeats = [
        entry for entry in record["run_list"] if entry.get("stage") == STAGE_THIRTY
    ]

    assert len(repeats) == record["repeats"]
    assert all(entry["paid"] for entry in repeats)
    # And each waits on the one before it, so three is a sequence and not a fan.
    assert all("requires" in entry for entry in repeats)


def test_the_denominator_is_the_cohort_size_the_binding_enforces(corrected):
    """The headline denominator, taken from the code that refuses a wrong one.

    ``bind_stage`` raises if a stage resolves to a different number of tasks
    than ``STAGE_SIZES`` fixes, so the 30 in the record is not a hope about how
    many tasks will run. Derived here rather than typed, because the value of
    the sentence is that the two agree.
    """
    record = corrected["experiment_record"]
    denominator = " ".join(record["denominator"].split())

    assert denominator.startswith(f"All {STAGE_SIZES[STAGE_THIRTY]} tasks")
    assert f"out of {STAGE_SIZES[STAGE_THIRTY]}" in " ".join(record["units"].split())

    compatibility = [
        entry for entry in record["run_list"] if entry.get("stage") == STAGE_FIVE
    ]
    assert len(compatibility) == 1
    # The entry writes its size into its own name and its prose spells it out;
    # the name is the half a machine can check, so that renaming the entry
    # without moving the stage is caught here.
    assert compatibility[0]["id"].endswith(str(STAGE_SIZES[STAGE_FIVE]))
    assert compatibility[0]["what"].startswith("five tasks")


def test_the_one_sided_spread_is_named_as_a_limit_and_not_as_a_confound(corrected):
    """Three repeats measure one side. The comparator ran once and stays once.

    Nothing on the closed list re-runs the old harness, so after three repeats
    the comparison is still a range against a point. That is not fixed by
    running the corrected side more times, which is exactly why it belongs
    here rather than in ``known_confounds``.
    """
    record = corrected["experiment_record"]
    questions = record["open_questions"]

    assert "trial_30 ran once" in questions
    assert "range against a point" in questions
    assert "repeats_note" in questions

    old_harness_again = [
        entry
        for entry in record["run_list"]
        if "trial_30's harness" in entry["what"] or "old harness" in entry["what"]
    ]
    assert old_harness_again == [], (
        "something on the list re-runs the old harness and the open question "
        "says nothing does"
    )


def test_the_permissions_question_points_at_the_survey_instead_of_summarising_it(
    corrected,
):
    """The shorthand is how a stale count survives being corrected.

    ``HOST_PERMISSIONS.md`` is regenerated from a survey and held to it by its
    own test. A number copied out of it into this plan is a number that stops
    being checked, and the two versions of that shorthand that have already
    been in circulation are both wrong now.
    """
    questions = corrected["experiment_record"]["open_questions"]
    repo_root = BATCH_RUNNER_ROOT.parent

    assert (repo_root / "tasks" / "0822_saturday" / "HOST_PERMISSIONS.md").is_file()
    assert (
        BATCH_RUNNER_ROOT
        / "tests"
        / "test_the_host_permissions_report_matches_its_survey.py"
    ).is_file()
    assert "HOST_PERMISSIONS.md" in questions
    assert "not summarised here" in questions

    for stale in ("three permissions", "twelve roles", "12 roles"):
        assert stale not in questions.lower()


def test_the_disclaimer_case_is_the_same_task_in_both_fields(corrected):
    """Two fields naming one past task, and no way to tell if they diverge.

    ``adjudication`` cites it as the run's own instance of an answer that
    passes both checkable tests and says nothing about quality;
    ``open_questions`` cites it as what grading would be for. A typo in either
    turns a real case into an unfindable one.
    """
    record = corrected["experiment_record"]
    import re

    def cited(field: str) -> set[str]:
        return set(re.findall(r"\b[0-9a-f]{8}\b", record[field]))

    shared = cited("adjudication") & cited("open_questions")
    assert len(shared) == 1, f"the two fields cite {shared or 'no'} task in common"
    assert "README_LIMITATION.txt" in record["open_questions"]
    assert "README_LIMITATION.txt" in record["adjudication"]
