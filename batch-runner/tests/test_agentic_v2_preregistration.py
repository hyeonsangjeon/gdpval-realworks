"""The pre-registration, held to being a promise rather than a description.

A record written before a run is only worth something if it cannot be quietly
rewritten to agree with the run afterwards, and if the claims it forbids stay
forbidden when the results are disappointing. Those are the two things tested
here.

Nothing here runs a task, calls a model, boots a guest or spends.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import yaml

from core.agentic_v2_contract import TOOL_NAMES
from core.agentic_v2_preregistration import (
    CODEX_TRIAL_PLAN,
    Comparison,
    DIFFERS,
    ESCALATION,
    MATCHES,
    NOT_STOP_RULES,
    PREREGISTRATION_ARTEFACT as ARTEFACT,
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


class TestTheRecordSaysWhatItIsNot:
    def test_it_does_not_claim_the_environment_is_ready(self):
        disclaimed = " ".join(record()["what_this_is_not"])
        assert "not a statement that the environment is ready" in disclaimed
        assert "role assignment" in disclaimed

    def test_it_does_not_approve_any_spending(self):
        disclaimed = " ".join(record()["what_this_is_not"])
        assert "not an approval to spend" in disclaimed

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
