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
honest answer is that nobody knows: ``repeats`` is ``undecided`` with the
consequence written out, rather than a number with nothing behind it.

Offline. Two YAML files, a digest and a string builder. Nothing here calls a
model, resolves a cohort or costs anything.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from core.agentic_v2_call_agreement import describe, the_stop_rule
from core.agentic_v2_fixture_backend import AgenticV2FixtureBackend
from core.agentic_v2_instructions import file_digest, resolve_instructions
from core.agentic_v2_manifest_binding import STAGE_SIZES
from core.agentic_v2_model_voice import REPLAY_FORMATS
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

#: The eight headings ``experiment-design`` §11 asks an experiment to answer
#: before it runs, in this repository's names for them.
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
)


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


def test_repeats_is_recorded_as_undecided_rather_than_invented(corrected):
    """Because the spread of one condition has never been measured here.

    ``experiment-design`` §4 asks for the spread before the comparison, and the
    honest answer is that trial_30 ran once. A number here would be a figure
    with nothing behind it, so the slot carries the word and the note carries
    the consequence: a single run cannot support a causal claim.
    """
    record = corrected["experiment_record"]
    assert str(record["repeats"]).strip().lower() == "undecided"
    assert "causal" in record["repeats_note"]


def test_the_run_list_is_finite_and_says_which_entries_spend(corrected):
    record = corrected["experiment_record"]
    runs = record["run_list"]

    assert isinstance(runs, list) and runs
    assert all(set(run) >= {"id", "what", "paid"} for run in runs)
    assert len({run["id"] for run in runs}) == len(runs)

    paid = [run for run in runs if run["paid"]]
    assert len(paid) == 1, "more than one paid run is more than one approval"
    assert [run["id"] for run in runs if not run["paid"]] == ["rehearsal"]

    for run in paid:
        assert run["stage"] in STAGE_SIZES
        assert run["stage"] in corrected["stages"]


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
