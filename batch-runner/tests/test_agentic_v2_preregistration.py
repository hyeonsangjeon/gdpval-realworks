"""The pre-registration, held to being a promise rather than a description.

A record written before a run is only worth something if it cannot be quietly
rewritten to agree with the run afterwards, and if the claims it forbids stay
forbidden when the results are disappointing. Those are the two things tested
here.

Nothing here runs a task, calls a model, boots a guest or spends.
"""

from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path
from unittest import mock

import pytest
import yaml

from core.agentic_v2_contract import TOOL_NAMES
from core.agentic_v2_conversation import run_model_conversation
from core.agentic_v2_conversation_runner import build_runner_factory, ceilings_from
from core.agentic_v2_stage_one_budget import load_stage_one_plan
from core.agentic_v2_preregistration import (
    CODEX_TRIAL_PLAN,
    Comparison,
    DIFFERS,
    ESCALATION,
    MATCHES,
    NOT_STOP_RULES,
    PREREGISTRATION_ARTEFACT as ARTEFACT,
    REPOSITORY_ROOT,
    STAGE_FIVE,
    STAGE_THIRTY,
    STAGE_TWO_TWENTY,
    STOP_RULES,
    UNKNOWN,
    cohorts,
    compare_with_codex_run,
    escalation_shape,
    manifest,
    may_attribute_difference_to_environment,
    record,
    residual_after_alignment,
    seal,
    verify_seal,
)

#: The one task the advance-check rule holds and the trial rule does not. Named
#: here so that a change to either rule fails loudly with the identifier in the
#: message, rather than flipping a boolean somewhere.
DROPPED_BETWEEN_FIVE_AND_THIRTY = "2ea2e5b5-257f-42e6-a7dc-93763f28b19d"


@pytest.fixture(scope="module")
def shape() -> dict:
    return escalation_shape()


@pytest.fixture(scope="module")
def comparisons() -> tuple:
    return compare_with_codex_run()


class TestTheManifestIsDerivedAndSealed:
    def test_the_three_cohorts_are_the_declared_sizes(self):
        chosen = cohorts()
        assert [len(chosen[name]) for name in ESCALATION] == [5, 30, 220]

    def test_it_pins_the_catalogue_and_the_dataset(self):
        pinned = manifest()
        assert len(pinned["catalog_sha256"]) == 64
        assert pinned["dataset_revision"]
        assert pinned["dataset_repo_id"] == "openai/gdpval"

    def test_it_names_the_rule_rather_than_only_the_answer(self):
        # A list of identifiers can be edited; a named rule can be re-run.
        rules = manifest()["selection_rules"]
        assert set(rules) == set(ESCALATION)
        assert all("execution_envelope_tasks" in value for value in rules.values())

    def test_the_seal_moves_when_anything_moves(self):
        first = record()
        edited = json.loads(json.dumps(first))
        edited["manifest"]["task_ids"][STAGE_FIVE].pop()
        assert seal(edited) != first["seal"]

    def test_an_edited_record_fails_against_the_seal_it_was_given(self):
        original = record()
        recorded_seal = original.pop("seal")
        assert verify_seal(original, recorded_seal) == []

        original["stop_rules"].append("whatever turns out to be inconvenient")
        problems = verify_seal(original, recorded_seal)
        assert len(problems) == 1
        assert "cannot be described as pre-registered" in problems[0]


class TestTheEscalationIsNotClaimedToBeNested:
    """Five, then thirty, then two hundred and twenty is not three circles."""

    def test_the_five_are_not_all_in_the_thirty(self, shape):
        assert shape["five_inside_thirty"] is False
        assert shape["dropped_between_five_and_thirty"] == [
            DROPPED_BETWEEN_FIVE_AND_THIRTY
        ]

    def test_only_four_carry_across_the_first_two_stages(self, shape):
        assert len(shape["comparable_across_the_first_two_stages"]) == 4

    def test_the_later_two_really_are_nested(self, shape):
        assert shape["thirty_inside_two_twenty"] is True
        assert shape["five_inside_two_twenty"] is True

    def test_the_gap_is_not_blamed_on_a_choice_somebody_made(self, shape):
        # Both rules predate every run and read only the catalogue. Saying so
        # matters: a task dropping out looks like score-chasing until it is
        # clear that neither rule can see a score.
        assert "not of anything chosen" in shape["what_that_means"]

    def test_codexs_own_file_names_the_same_missing_task(self):
        # Independent corroboration rather than agreement by construction: A
        # wrote its thirty out in full, so the absence can be read off a file
        # this module does not produce.
        plan = yaml.safe_load(CODEX_TRIAL_PLAN.read_text(encoding="utf-8"))
        written = plan["data"]["filter"]["task_ids"]
        assert DROPPED_BETWEEN_FIVE_AND_THIRTY not in written
        assert len(written) == 30


class TestADifferenceIsNotAnEnvironmentEffect:
    def test_it_refuses_today_and_says_what_blocks_it(self, comparisons):
        allowed, blockers = may_attribute_difference_to_environment(comparisons)
        assert allowed is False
        assert blockers

    def test_a_single_difference_is_enough_to_block(self):
        allowed, blockers = may_attribute_difference_to_environment(
            [
                Comparison("a", 1, 1, MATCHES, True, ""),
                Comparison("b", 1, 2, DIFFERS, True, "the one that differs"),
            ]
        )
        assert allowed is False
        assert len(blockers) == 1
        assert "the one that differs" in blockers[0]

    def test_an_unchecked_field_blocks_just_like_a_differing_one(self):
        # The failure mode this exists for: a field nobody could read being
        # counted as a field that agreed.
        allowed, blockers = may_attribute_difference_to_environment(
            [Comparison("a", 1, None, UNKNOWN, True, "nobody read it")]
        )
        assert allowed is False
        assert "unknown" in blockers[0]

    def test_it_would_allow_the_claim_if_everything_really_matched(self):
        # Not a rule that can never be satisfied -- which would make it a
        # decoration rather than a check.
        allowed, blockers = may_attribute_difference_to_environment(
            [Comparison("a", 1, 1, MATCHES, True, "")]
        )
        assert allowed is True
        assert blockers == []

    def test_a_missing_source_file_reads_as_unknown_and_not_as_agreement(
        self, tmp_path
    ):
        absent = tmp_path / "no-such-plan.yaml"
        compared = compare_with_codex_run(codex_plan=absent)
        readable = [item for item in compared if item.verdict == MATCHES]
        assert readable == []
        allowed, _ = may_attribute_difference_to_environment(compared)
        assert allowed is False

    def test_the_two_runs_do_agree_on_the_things_they_agree_on(self, comparisons):
        # The check is worth having only because it is not uniformly negative.
        agreeing = {item.field for item in comparisons if item.verdict == MATCHES}
        assert "deployment" in agreeing
        assert "task_cohort_thirty" in agreeing

    def test_attempts_are_compared_as_attempts_and_not_as_retries(
        self, comparisons
    ):
        # A counts retries and B counts attempts. Comparing the raw numbers
        # would invent a difference of one, or hide a real one.
        attempts = next(
            item for item in comparisons if item.field == "attempts_per_task"
        )
        plan = yaml.safe_load(CODEX_TRIAL_PLAN.read_text(encoding="utf-8"))
        assert attempts.theirs == plan["execution"]["max_retries"] + 1


class TestTheResidualIsNamedRatherThanHandwaved:
    def test_the_irreducible_pair_is_the_tool_surface_and_its_wording(self):
        residual = residual_after_alignment()
        assert residual["irreducible"] == ["tool_surface", "standing_instructions"]

    def test_the_alignable_ones_are_settings_and_not_design(self):
        residual = residual_after_alignment()
        assert set(residual["alignable_now"]) <= {
            "attempts_per_task",
            "per_task_wall_clock_seconds",
            "deployment",
            "task_cohort_thirty",
            "self_review_enabled",
            "resume_rounds",
        }

    def test_the_tool_surface_is_the_contracts_own_list(self, comparisons):
        surface = next(
            item for item in comparisons if item.field == "tool_surface"
        )
        assert surface.ours == list(TOOL_NAMES)
        assert surface.removable is False

    def test_even_a_fully_aligned_comparison_is_not_isolation_alone(self):
        residual = residual_after_alignment()
        assert "not an effect of the isolation alone" in (
            residual["what_the_comparison_can_be"]
        )


class TestThereIsNoSuccessQuota:
    """Nothing in the record says how well the run has to go."""

    FORBIDDEN = ("pass rate", "min_score", "target score", "accuracy", "5/5")

    def test_no_stop_rule_is_keyed_on_how_well_the_model_did(self):
        joined = " ".join(STOP_RULES).lower()
        for word in self.FORBIDDEN:
            assert word not in joined

    def test_a_bad_result_is_written_down_as_a_result(self):
        joined = " ".join(NOT_STOP_RULES)
        assert "scoring zero" in joined
        assert "no target pass rate" in joined

    def test_disagreeing_with_the_other_run_is_not_a_fault(self):
        assert any("disagreeing with A" in rule for rule in NOT_STOP_RULES)

    def test_the_known_capability_gaps_point_at_their_evidence(self):
        joined = " ".join(NOT_STOP_RULES)
        assert "guest_command_absences_explained.json" in joined

    def test_every_stop_rule_is_about_a_record_that_cannot_be_trusted(self):
        # Each one names an integrity failure. If a rule ever reads as "the
        # numbers look bad", it belongs in the other list.
        assert len(STOP_RULES) == 8
        assert all(isinstance(rule, str) and rule for rule in STOP_RULES)


class TestTheConditionsAreRecordedBeforeTheRun:
    """Model, prompt, tools, ceilings, retries — written down ahead of time.

    A pre-registration whose conditions are written by hand is a description of
    a run somebody intended. Each test below asks the thing that would actually
    execute, and fails if the record and the executable disagree — which is the
    only way the record stays worth reading a month after it was sealed.
    """

    def test_the_conditions_are_read_from_the_plan_and_the_plan_is_sealed(self):
        conditions = record()["run_conditions"]

        plan_path = REPOSITORY_ROOT / conditions["read_from"]
        assert plan_path.is_file()
        assert (
            conditions["read_from_sha256"]
            == hashlib.sha256(plan_path.read_bytes()).hexdigest()
        )

    def test_the_model_and_the_resource_both_appear(self):
        """A deployment name alone does not identify a model.

        The same name in another Foundry resource is another deployment, so a
        record naming only ``gpt-5.4`` would not distinguish this run from one
        against a different account's deployment of the same name.
        """
        model = record()["run_conditions"]["model"]
        plan = load_stage_one_plan()

        assert model["deployment"] == plan["model"]["deployment"]
        assert model["resolved_model"] == plan["model"]["resolved_model"]
        assert model["account"] == plan["azure_connection"]["account"]
        assert model["project"] == plan["azure_connection"]["project"]
        assert model["route_profile"] == plan["azure_connection"]["route_profile"]
        assert model["automatic_model_switch_allowed"] is False

    def test_the_recorded_tool_list_is_the_one_the_model_will_be_offered(self):
        """The record said seven tools before this test was written.

        It excluded ``exec_run`` on the reasoning that a shut tool is not
        offered. Nothing in the run narrows the list: ``tools_available``
        defaults to the whole contract and no caller overrides it, so the model
        is offered all eight and ``exec_run`` answers ``capability_unavailable``
        when it is chosen. Which is the more interesting run — how a model
        reacts to a refused capability is a finding — but either way the record
        has to say what happens rather than what sounds tidier.
        """
        tools = record()["run_conditions"]["tools"]

        # Both ends of the path the stage run takes: the factory it builds
        # its runner with, and the loop that loop actually runs.
        for built in (build_runner_factory, run_model_conversation):
            offered = inspect.signature(built).parameters["tools_available"].default
            assert tuple(tools["offered"]) == tuple(offered), built.__name__

        assert tools["offered"] == list(TOOL_NAMES)
        assert tools["offered_but_refuses_everything"] == ["exec_run"]
        assert tools["exec_run_open"] is False
        assert tools["narrowed_by_the_run"] is False

    def test_the_recorded_ceilings_are_the_ones_that_will_be_enforced(self):
        """Derived by the runner's own function, not by a second copy of it.

        The ceilings are the one part of the conditions the plan does not
        contain — they are arithmetic on it. Worked out twice, a correction to
        the enforcing copy would leave the promised copy describing a run that
        did not happen, and nothing would say so.
        """
        conditions = record()["run_conditions"]
        plan = load_stage_one_plan()
        chosen = plan["cost"]["chosen_settings"]

        class _Chosen:
            tool_calls_per_attempt = chosen["tool_calls_per_attempt"]
            max_output_tokens_per_turn = chosen["max_output_tokens_per_turn"]

        assert conditions["per_task_ceilings"] == ceilings_from(plan, _Chosen).as_dict()
        assert conditions["how_the_ceilings_were_derived"]["chosen_settings"] == chosen

    def test_no_ceiling_is_left_unset(self):
        """A ceiling nobody set is not a ceiling, and nulls read as "no limit"."""
        ceilings = record()["run_conditions"]["per_task_ceilings"]

        assert ceilings
        assert all(value is not None for value in ceilings.values())
        assert all(
            value > 0 for value in ceilings.values() if isinstance(value, (int, float))
        )

    def test_the_three_kinds_of_retry_stay_apart(self):
        """Collapsed into one count, a flaky endpoint reads as an unsure model.

        The distinction is the fourth ordered step's, and it has to be fixed
        before the run rather than reconstructed from logs afterwards.
        """
        retry = record()["run_conditions"]["retry"]

        assert retry["kinds_recorded_separately"] == [
            "infrastructure",
            "semantic",
            "internal",
        ]
        assert retry["reasons_allowed"] == ["infrastructure_error"]
        assert retry["max_attempts"] == 1

    def test_the_conditions_carry_no_prediction_of_the_outcome(self):
        """Pre-registering an expectation invites reading the result against it.

        What a good result would be is in ``after_stage_one.success_criteria``
        in the plan, which is a criterion. A guess at the outcome is not, and
        the words below are the ones such a guess arrives wearing.
        """
        written = json.dumps(record()["run_conditions"]).lower()

        for guess in ("we expect", "should succeed", "likely", "probably"):
            assert guess not in written

    def test_a_changed_setting_changes_the_seal(self):
        """The record is only a commitment if editing the plan invalidates it."""
        before = record()["seal"]
        plan = load_stage_one_plan()
        moved = json.loads(json.dumps(plan))
        moved["cost"]["chosen_settings"]["tool_calls_per_attempt"] = 4

        with mock.patch(
            "core.agentic_v2_stage_one_budget.load_stage_one_plan",
            return_value=moved,
        ):
            after = record()["seal"]

        assert after != before


class TestTheRecordSaysWhatItIsNot:
    def test_it_does_not_claim_the_environment_is_ready(self):
        """Named, not diagnosed — and the diagnosis it used to carry is barred.

        This assertion used to be ``"role assignment" in disclaimed``, which
        pinned a *cause*: that the run was blocked by a missing role in the
        subscription holding the model. That reading came from a 401 which was
        later shown to have arrived from past the authentication gate, and
        stage A has since reached a real deployment and been charged for it. A
        disclaimer naming a cause that has been disproved is worse than none,
        because it sends the next reader to ask for permission nobody needs.

        So the assertion is inverted. What is still missing is named — the
        isolation, which the pre-registration itself fixes shut — and the
        retired cause is held out, so bringing the sentence back fails here.
        """
        disclaimed = " ".join(record()["what_this_is_not"])

        assert "not a statement that the environment is ready" in disclaimed
        assert "No V2 task has run" in disclaimed
        assert "exec_run shut and no guest booted" in disclaimed
        assert "no result from it is evidence that the sandbox contains anything" in disclaimed
        assert "role assignment" not in disclaimed

    def test_it_does_not_approve_any_spending(self):
        disclaimed = " ".join(record()["what_this_is_not"])
        assert "not an approval to spend" in disclaimed

    def test_the_money_disclaimer_is_read_from_the_plan_rather_than_stated(self):
        """The other sentence that went stale, and why it cannot again.

        It used to say the amount was the owner's to fill in. On 2026-09-11
        they filled in two, and the sentence carried on saying otherwise. It
        now asks :func:`stage_one_amount_note`, so the record follows the plan
        in both directions: an approval that is withdrawn turns the disclaimer
        back by itself.

        The assertions are about *scope*, not about the figures. The two
        amounts are whole-run ones for the five tasks the plan pins, so a
        record that read as a general approval would be read as pricing 220.
        """
        disclaimed = " ".join(record()["what_this_is_not"])

        assert "five-task cohort" in disclaimed
        assert "whole-run figures for those five" in disclaimed
        assert "thirty and the two hundred and twenty are not priced" in disclaimed
        assert "scripts/run_agentic_v2_stage.py refuses them until they are" in disclaimed
        # The stale shape: an amount nobody has approved yet.
        assert "the owner's to fill in" not in disclaimed

    def test_the_committed_comparison_is_carried_in_the_record(self):
        carried = record()["comparison_with_codex"]
        assert carried["may_call_a_difference_an_environment_effect"] is False
        assert carried["why_not"]
        assert carried["source"].endswith("exp034_codex_foundry_trial30.yaml")


class TestTheCommittedCopyIsTheOneThatCounts:
    """A pre-registration that lives only in code is not pre-registered.

    If this class fails, read *why* before regenerating. Two different things
    produce the same failure: this repository's own inputs moved (a rule, the
    catalogue, a stop rule), or A's experiment file moved and the comparison now
    describes a configuration that is gone. The first needs the artefact
    regenerated in the same commit; the second needs someone to decide whether
    the two runs are still comparable at all.
    """

    def test_the_artefact_is_committed_rather_than_derived_at_read_time(self):
        assert ARTEFACT.is_file(), (
            "the pre-registration has no committed copy, so nothing fixes what "
            "was promised before the run"
        )

    def test_the_committed_copy_still_equals_what_the_code_derives(self):
        committed = json.loads(ARTEFACT.read_text(encoding="utf-8"))
        assert committed == record(), (
            "the committed pre-registration and the derived one disagree. "
            "Regenerate with: python batch-runner/scripts/"
            "write_v2_preregistration.py"
        )

    def test_the_committed_seal_verifies_against_its_own_body(self):
        # Independent of the equality above: even a stale artefact has to be
        # internally consistent, or it was hand-edited.
        committed = json.loads(ARTEFACT.read_text(encoding="utf-8"))
        recorded_seal = committed.pop("seal")
        assert verify_seal(committed, recorded_seal) == []

    def test_it_records_the_fingerprint_of_the_file_it_compares_against(self):
        # Without this, A's file could change and the comparison would go stale
        # with nothing in the record saying which version it read.
        carried = record()["comparison_with_codex"]
        assert carried["source_sha256"] == hashlib.sha256(
            CODEX_TRIAL_PLAN.read_bytes()
        ).hexdigest()

    def test_a_missing_comparison_source_is_recorded_as_absent_not_as_a_digest(
        self, monkeypatch
    ):
        monkeypatch.setattr(
            "core.agentic_v2_preregistration.CODEX_TRIAL_PLAN",
            CODEX_TRIAL_PLAN.with_name("no-such-experiment.yaml"),
        )
        assert record()["comparison_with_codex"]["source_sha256"] is None


class TestItOnlyReads:
    def test_it_reaches_for_no_network_and_writes_nothing(self):
        source = (
            Path(__file__).resolve().parents[1]
            / "core"
            / "agentic_v2_preregistration.py"
        ).read_text(encoding="utf-8")
        for forbidden in (
            "requests", "httpx", "urllib", "socket", "subprocess",
            "write_text", "write_bytes", "mkdir", "os.system",
        ):
            assert forbidden not in source, f"unexpected reach: {forbidden}"
