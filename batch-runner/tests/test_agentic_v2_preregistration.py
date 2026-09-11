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
from core.agentic_compute import (
    MAX_INPUT_FILES,
    MAX_INPUT_SINGLE,
    MAX_INPUT_TOTAL,
)
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
    FILES_NAMED_BY_THE_TASKS,
    FILES_THE_MODEL_COULD_OPEN_UNAIDED,
    OVER_THE_WORKSPACE_FILE_LIMIT,
    RENDERING_OUTCOMES,
    TASKS_WORKING_FROM_THE_PROMPT_ALONE,
    UNDELIVERABLE_INPUTS,
    UNKNOWN,
    WORKSPACE_FILE_LIMIT,
    cohorts,
    compare_with_codex_run,
    escalation_shape,
    input_disposition,
    manifest,
    may_attribute_difference_to_environment,
    record,
    residual_after_alignment,
    seal,
    verify_input_disposition,
    verify_reader_reach,
    verify_rendering_reach,
    verify_seal,
)
from core.execution_envelope_tasks import full_run_tasks, load_task_catalog

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

    def test_the_desk_closing_on_one_bad_call_is_registered_not_fixed(self):
        """It ends a task on turn one and it is still here on purpose.

        ``dispatch_one`` ends a task on the first tool call that comes back
        not-ok, and the model is told nothing and asked nothing further. Fixing
        it would change what a trace contains, so it is registered instead --
        and registering it is only worth anything if the record says what it
        costs and says the result is not about the model. A run where this fires
        often has to be readable as a run under this condition.
        """
        condition = record()["run_conditions"]["one_failed_tool_call_ends_the_task"]

        assert condition["holds"] is True
        assert "dispatch_one" in condition["comes_from"]
        assert condition["is_not"].startswith("evidence about the model")
        assert "tool_desk_broke" in condition["recorded_as"]

    def test_registering_that_condition_moved_the_seal(self):
        """A condition added without the seal moving is a condition added after.

        The seal is the whole reason a pre-registration is worth more than a
        note. This asserts the new entry is inside it rather than beside it.
        """
        without = json.loads(json.dumps(record()))
        del without["seal"]
        del without["run_conditions"]["one_failed_tool_call_ends_the_task"]

        assert seal(without) != record()["seal"]

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


#: The one file in the pinned revision that no cohort can be handed, and the
#: task it belongs to. Written out here rather than read from the module under
#: test, so that a change to the record is a failure with the identifier in the
#: message instead of a test that agrees with whatever it is shown.
UNDELIVERABLE_TASK = "a941b6d8-4289-4500-b45a-f8e4fc94a724"
UNDELIVERABLE_PATH = (
    "reference_files/67469cf2a7509f149c095cf4f6542f6d/TWT_A001_03.mp4"
)
UNDELIVERABLE_SIZE = 689_061_330


def _fake_snapshot(root: Path, sizes: dict[str, int] | None = None) -> Path:
    """A dataset-shaped tree with the right names and made-up sizes.

    Every file the two hundred and twenty name, one byte each unless `sizes`
    says otherwise, and every file the record calls oversized at its recorded
    size. Written sparse: nothing here allocates 689 MB, and `st_size` -- the
    only thing the check reads -- is the same either way.

    The oversized ones are taken from the record rather than typed out again.
    Typed out, this fixture would be a second copy of the same list, and a test
    that a record matches a hand-maintained duplicate of itself is a test of
    nothing. What stops it agreeing with whatever it is shown is that the check
    also re-derives the band from the limit: a file dropped out of the record
    reappears here as an unrecorded file over the limit.
    """
    sizes = dict(sizes or {})
    sizes.setdefault(UNDELIVERABLE_PATH, UNDELIVERABLE_SIZE)
    for one in OVER_THE_WORKSPACE_FILE_LIMIT:
        sizes.setdefault(str(one["path"]), int(one["size_bytes"]))
    catalog = load_task_catalog()
    by_id = catalog.by_task_id()
    for task_id in full_run_tasks(catalog):
        for name in by_id[str(task_id)].reference_file_paths:
            made = root / name
            made.parent.mkdir(parents=True, exist_ok=True)
            with made.open("wb") as handle:
                handle.truncate(sizes.get(name, 1))
    return root


class TestWhatEachCohortCanBeHanded:
    """The inputs half of the pre-registration.

    A run where the model is not given a file it was told to open produces the
    same artefact as a run where the model ignored one, and by the time anybody
    is reading results the difference is unrecoverable. So it is written down
    first: which cohort loses what, and to which limit.
    """

    def test_the_first_two_stages_have_nothing_refused(self):
        """Not a convenience. It decides what the early stages can show.

        Five tasks and then thirty are where a failure gets diagnosed, and a
        missing input there would be the first explanation to reach for and the
        hardest to rule out. Neither cohort contains the one task that loses a
        file, so for those two stages that explanation is closed off in advance
        rather than argued about afterwards.
        """
        disposition = input_disposition()["per_stage"]

        assert disposition[STAGE_FIVE]["files_that_cannot_be_delivered"] == []
        assert disposition[STAGE_THIRTY]["files_that_cannot_be_delivered"] == []

    def test_the_two_hundred_and_twenty_loses_exactly_one_named_file(self):
        refused = input_disposition()["per_stage"][STAGE_TWO_TWENTY][
            "files_that_cannot_be_delivered"
        ]

        assert [one["path"] for one in refused] == [UNDELIVERABLE_PATH]
        assert refused[0]["task_id"] == UNDELIVERABLE_TASK
        assert refused[0]["size_bytes"] == UNDELIVERABLE_SIZE
        assert refused[0]["size_bytes"] > MAX_INPUT_SINGLE

    def test_the_task_that_loses_it_keeps_its_other_file(self):
        """Which is the outcome worth recording, not the softer one.

        An empty workspace is obvious in a result. Half the footage is not: the
        model has something to work from, produces an edit, and the edit is
        judged as an edit. The record has to carry the shortfall because the
        deliverable will not show it.
        """
        catalog = load_task_catalog()
        task = catalog.by_task_id()[UNDELIVERABLE_TASK]

        assert task.reference_file_count == 2
        assert UNDELIVERABLE_PATH in task.reference_file_paths
        kept = [one for one in task.reference_file_paths if one != UNDELIVERABLE_PATH]
        assert len(kept) == 1, "the task is supposed to name a second clip"

    def test_the_counts_cover_every_task_in_every_cohort(self):
        disposition = input_disposition()["per_stage"]
        chosen = cohorts()
        for stage in ESCALATION:
            assert disposition[stage]["tasks"] == len(chosen[stage])
            assert (
                disposition[stage]["tasks_naming_reference_files"]
                <= disposition[stage]["tasks"]
            )

    def test_the_limits_are_read_from_the_contract_and_not_restated(self):
        """Two copies of a number is one chance for them to disagree.

        If these were typed into the record, raising a limit in the compute
        contract would leave the pre-registration describing a narrower run
        than the one that happened -- and the record is the thing a reader
        trusts when the results are confusing.
        """
        limits = input_disposition()["limits"]

        assert limits["max_files_per_task"] == MAX_INPUT_FILES
        assert limits["max_bytes_per_file"] == MAX_INPUT_SINGLE
        assert limits["max_bytes_per_task"] == MAX_INPUT_TOTAL
        assert limits["come_from"] == "core/agentic_compute.py"

    def test_nothing_is_quietly_put_in_the_missing_file_s_place(self):
        disposition = input_disposition()

        assert "Nothing is put in its place" in disposition["no_substitute_is_made"]
        assert "is not evidence about the model" in (
            disposition["what_a_failure_there_does_not_show"]
        )

    def test_the_disposition_is_carried_in_the_sealed_record(self):
        body = record()
        assert body["inputs"] == input_disposition()
        recorded_seal = body.pop("seal")
        assert verify_seal(body, recorded_seal) == []


class TestTheDispositionIsCheckedAgainstDiskRatherThanTrusted:
    """A recorded size is a claim until something measures it.

    The first direction catches an edit to the record. The second is the one
    worth having: a file nobody wrote down that has grown past a limit, which a
    cohort would silently lose and which would then read as bad work.
    """

    def test_a_snapshot_matching_the_record_reports_nothing(self, tmp_path):
        assert verify_input_disposition(_fake_snapshot(tmp_path)) == []

    def test_a_recorded_size_that_no_longer_matches_is_reported(self, tmp_path):
        root = _fake_snapshot(tmp_path, {UNDELIVERABLE_PATH: UNDELIVERABLE_SIZE - 1})
        wrong = verify_input_disposition(root)

        assert any(UNDELIVERABLE_PATH in one for one in wrong)
        assert any("the record was edited" in one for one in wrong)

    def test_a_recorded_file_that_now_fits_is_reported(self, tmp_path):
        """The refusal outliving its reason, which is the same bug class.

        Raise the per-file limit past 689 MB and the record would carry on
        saying a deliverable file cannot be delivered. Nothing else in the
        repository would notice.
        """
        root = _fake_snapshot(tmp_path)
        with mock.patch(
            "core.agentic_v2_preregistration.MAX_INPUT_SINGLE", UNDELIVERABLE_SIZE * 2
        ):
            wrong = verify_input_disposition(root)

        assert any("within the" in one for one in wrong)

    def test_an_unrecorded_file_over_the_limit_is_reported(self, tmp_path):
        """The case the record could not have anticipated, which is the point."""
        catalog = load_task_catalog()
        by_id = catalog.by_task_id()
        victim = next(
            (task_id, by_id[str(task_id)].reference_file_paths[0])
            for task_id in full_run_tasks(catalog)
            if by_id[str(task_id)].reference_file_paths
            and by_id[str(task_id)].reference_file_paths[0] != UNDELIVERABLE_PATH
        )
        root = _fake_snapshot(tmp_path, {victim[1]: MAX_INPUT_SINGLE + 1})
        wrong = verify_input_disposition(root)

        assert any(victim[1] in one and "no record says so" in one for one in wrong)

    def test_a_named_file_missing_from_the_snapshot_is_reported(self, tmp_path):
        root = _fake_snapshot(tmp_path)
        catalog = load_task_catalog()
        by_id = catalog.by_task_id()
        gone = next(
            by_id[str(task_id)].reference_file_paths[0]
            for task_id in full_run_tasks(catalog)
            if by_id[str(task_id)].reference_file_paths
        )
        (root / gone).unlink()

        assert any(
            gone in one and "not in the snapshot" in one
            for one in verify_input_disposition(root)
        )

    def test_an_empty_root_does_not_pass_by_finding_nothing(self, tmp_path):
        """A check that says nothing when handed nothing is not a check."""
        wrong = verify_input_disposition(tmp_path)

        assert any("is not present" in one for one in wrong)
        assert len(wrong) > 1

    def test_an_unrecorded_file_over_the_workspace_limit_is_reported(
        self, tmp_path
    ):
        """The second limit, and the worse one.

        A file over the compute contract's limit costs its task that file. A
        file over the workspace's costs the task every deliverable, because the
        limit is applied while walking the whole workspace and the walk runs on
        write. The model sees only `fixture_backend_error`, so it retries until
        its budget is gone and the record afterwards shows a model that produced
        nothing.
        """
        catalog = load_task_catalog()
        by_id = catalog.by_task_id()
        recorded = {str(one["path"]) for one in OVER_THE_WORKSPACE_FILE_LIMIT}
        victim = next(
            path
            for task_id in full_run_tasks(catalog)
            for path in by_id[str(task_id)].reference_file_paths
            if path not in recorded
        )
        root = _fake_snapshot(tmp_path, {victim: WORKSPACE_FILE_LIMIT + 1})

        wrong = verify_input_disposition(root)

        assert any(
            victim in one and "could write nothing at all" in one for one in wrong
        )

    def test_a_recorded_oversized_file_that_now_fits_is_reported(self, tmp_path):
        """The same bug class as the per-file one, one limit down.

        If the workspace limit is ever raised, the record would carry on
        refusing files that fit -- handing the model less than it could have had
        and calling that a measurement.
        """
        root = _fake_snapshot(tmp_path)
        with mock.patch(
            "core.agentic_v2_preregistration.WORKSPACE_FILE_LIMIT",
            UNDELIVERABLE_SIZE * 2,
        ):
            wrong = verify_input_disposition(root)

        assert len(wrong) == len(OVER_THE_WORKSPACE_FILE_LIMIT)
        assert all(
            "recorded as over the workspace file limit but" in one for one in wrong
        )

    def test_every_recorded_oversized_file_is_over_the_limit(self):
        """Read from the record, checked against the limit it claims to apply.

        Nothing on disk is needed for this one, which is the point: it fails in
        CI, where the dataset is absent, if an entry is ever added that the
        limit would not actually have refused.
        """
        too_small = [
            one["path"]
            for one in OVER_THE_WORKSPACE_FILE_LIMIT
            if int(one["size_bytes"]) <= WORKSPACE_FILE_LIMIT
        ]
        assert too_small == []
        assert len({one["path"] for one in OVER_THE_WORKSPACE_FILE_LIMIT}) == len(
            OVER_THE_WORKSPACE_FILE_LIMIT
        )


class TestWhatTheModelCanOpenWithoutHelp:
    """The figure that decides whether a V2 result is about the model at all.

    `workspace_apply(read)` decodes UTF-8 and `exec_run` is shut, so a file that
    does not decode cannot be opened by any means the model has. Measured rather
    than assumed, because the assumption everybody makes -- "it is a text file,
    the model can read it" -- is true of three of the two hundred and sixty-one.
    """

    def test_the_record_says_how_many_and_out_of_how_many(self):
        disposition = input_disposition()["what_the_model_can_open_by_itself"]

        assert disposition["files_named_by_the_tasks"] == FILES_NAMED_BY_THE_TASKS
        assert disposition["files_that_decode_as_utf8"] == (
            FILES_THE_MODEL_COULD_OPEN_UNAIDED
        )
        assert "workspace_apply(read)" in disposition["how_that_was_measured"]

    def test_the_renderings_are_recorded_as_a_difference_and_not_a_fix(self):
        """Step five's rule, at the place it would be broken.

        A text rendering is a thing A's run does not have and does not need. A
        V2 score on a task that needed a chart is not comparable to A's on the
        same task, and the record has to say so before either runs -- afterwards
        it reads as an excuse for whichever number came out lower.
        """
        renderings = input_disposition()["text_renderings"]

        assert "never presented as the file" in renderings["never_a_replacement"]
        assert "not comparable" in (
            renderings["this_is_a_difference_from_the_codex_run"]
        )

    def test_the_two_figures_agree_with_the_sentence_that_explains_them(self):
        """The arithmetic anchor, and the only one CI can run.

        Both the number and the record that reports it come from the same
        constant, so comparing them proves nothing on its own -- move the
        constant and the pair moves together. What does not move is the prose
        that says how many files failed, so the subtraction is checked here.
        On a machine with the dataset the real anchor is the test below; on one
        without, this is what stops the figure drifting quietly.
        """
        disposition = input_disposition()
        measured = disposition["what_the_model_can_open_by_itself"][
            "how_that_was_measured"
        ]
        unreadable = FILES_NAMED_BY_THE_TASKS - FILES_THE_MODEL_COULD_OPEN_UNAIDED

        assert f"the other {unreadable} do not" in measured
        # The denominator used to sit in ``what_they_are``, inside a sentence
        # claiming all 261 extract without error. That sentence was wrong, so
        # the figure now anchors to the one that replaced it -- which carries
        # the same denominator and, unlike its predecessor, a true numerator.
        assert str(FILES_NAMED_BY_THE_TASKS) in (
            disposition["text_renderings"]["not_all_of_them_open"]
        )
        assert sum(
            disposition["text_renderings"]["what_the_reader_got_out_of_them"].values()
        ) == FILES_NAMED_BY_THE_TASKS

    def test_the_pinned_snapshot_still_gives_the_recorded_reach(self):
        """The measurement itself, where the bytes exist to make it.

        Skipped rather than faked when they do not. A fixture cannot answer
        this question -- sparse files are NUL bytes and NUL decodes -- so a
        version of this test that ran everywhere would be measuring its own
        fixture and reporting the answer as the dataset's.
        """
        pinned = manifest()
        root = (
            Path.home()
            / ".cache"
            / "huggingface"
            / "hub"
            / f"datasets--{pinned['dataset_repo_id'].replace('/', '--')}"
            / "snapshots"
            / pinned["dataset_revision"]
        )
        if not (root / "reference_files").is_dir():
            pytest.skip(f"the pinned snapshot is not on this machine: {root}")

        assert verify_reader_reach(root) == []

    def test_a_tree_of_readable_files_is_reported_rather_than_accepted(
        self, tmp_path
    ):
        """Sparse files are all NUL bytes, and NUL decodes as UTF-8.

        Which makes the empty fixture the exact shape of the mistake worth
        catching: a check that measured sizes and inferred readability would
        call this snapshot fine and report that the model can open all 261.
        """
        wrong = verify_reader_reach(_fake_snapshot(tmp_path))

        assert any("decode as UTF-8" in one for one in wrong)

    def test_a_snapshot_missing_a_named_file_is_reported(self, tmp_path):
        root = _fake_snapshot(tmp_path)
        catalog = load_task_catalog()
        by_id = catalog.by_task_id()
        gone = next(
            by_id[str(task_id)].reference_file_paths[0]
            for task_id in full_run_tasks(catalog)
            if by_id[str(task_id)].reference_file_paths
        )
        (root / gone).unlink()

        assert any(
            gone in one and "not in the snapshot" in one
            for one in verify_reader_reach(root)
        )

    def test_an_empty_root_does_not_pass_by_finding_nothing(self, tmp_path):
        wrong = verify_reader_reach(tmp_path)

        assert any("not in the snapshot" in one for one in wrong)
        assert any("were measured and the record is written about" in one for one in wrong)


class TestTheTasksThatGetNothingReadable:
    """Nine tasks, and a record that used to say all 261 files opened fine."""

    def test_the_record_no_longer_says_every_file_extracts_without_error(self):
        """Two do not open. The old sentence said none failed.

        Small, and in the direction that flatters the environment -- which is
        the direction a pre-registration exists to guard, because a record
        overstating what reached the model turns an input the model never had
        into an answer the model got wrong.
        """
        renderings = input_disposition()["text_renderings"]
        assert "All 261 files extract without error" not in renderings[
            "what_they_are"
        ]
        assert RENDERING_OUTCOMES["the_reader_could_not_open_it"] == 2
        assert RENDERING_OUTCOMES["the_reader_found_no_text_in_it"] == 5

    def test_the_outcomes_account_for_every_named_file(self):
        assert sum(RENDERING_OUTCOMES.values()) == FILES_NAMED_BY_THE_TASKS

    def test_the_record_carries_the_outcomes_and_not_only_a_summary(self):
        renderings = input_disposition()["text_renderings"]
        assert renderings["what_the_reader_got_out_of_them"] == RENDERING_OUTCOMES
        assert "2 of 261" in renderings["not_all_of_them_open"]

    def test_the_nine_are_named_rather_than_counted(self):
        """A count cannot be checked against a result. A task id can.

        Reading a result for one of these as the model's would be scoring a gap
        this environment introduced, so the record has to survive being carried
        to the grading table, and a bare nine does not.
        """
        assert len(TASKS_WORKING_FROM_THE_PROMPT_ALONE) == 9
        assert len(set(TASKS_WORKING_FROM_THE_PROMPT_ALONE)) == 9

    def test_every_one_of_them_is_a_task_the_run_will_actually_reach(self):
        catalog = load_task_catalog()
        everything = {str(one) for one in full_run_tasks(catalog)}
        for task_id in TASKS_WORKING_FROM_THE_PROMPT_ALONE:
            assert task_id in everything, f"{task_id} is not in the 220"

    def test_the_smaller_stages_carry_their_own_share(self):
        """Nought of five, one of thirty, nine of 220.

        Worth pinning because the escalation is what decides whether the
        problem is seen before the money is spent: an advance check of five
        would have passed clean and said nothing about it.
        """
        per_stage = input_disposition()["per_stage"]
        assert per_stage[STAGE_FIVE]["tasks_that_worked_from_the_prompt_alone"] == []
        assert per_stage[STAGE_THIRTY][
            "tasks_that_worked_from_the_prompt_alone"
        ] == ["38889c3b-e3d4-49c8-816a-3cc8e5313aba"]
        assert sorted(
            per_stage[STAGE_TWO_TWENTY]["tasks_that_worked_from_the_prompt_alone"]
        ) == sorted(TASKS_WORKING_FROM_THE_PROMPT_ALONE)

    def test_a_stage_can_never_report_more_of_them_than_it_has_tasks(self):
        for stage, section in input_disposition()["per_stage"].items():
            assert len(
                section["tasks_that_worked_from_the_prompt_alone"]
            ) <= section["tasks_naming_reference_files"], stage

    def test_the_disclaimer_covers_the_case_that_was_invisible(self):
        """The six whose every file was refused, which both old checks passed.

        ``could_open_nothing`` asks about the files that arrived, so a task
        with none arrived answers no -- the same answer a task given everything
        gives. The sentence had two cases in it and needed the third.
        """
        said = input_disposition()["what_a_failure_there_does_not_show"]
        assert "every file was refused" in said
        assert "tasks_that_worked_from_the_prompt_alone" in said


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
    #: The substring list below would have kept passing after
    #: ``verify_rendering_reach`` was added, because writing through
    #: ``tempfile`` and ``stage_task_reference_files`` spells none of these
    #: words. A green bar on a claim that had stopped being true is worse than
    #: a red one, so the claim is split instead: the network ban still covers
    #: the whole module, and the writing ban now says where writing is allowed.
    def test_it_reaches_for_no_network(self):
        for forbidden in (
            "requests", "httpx", "urllib", "socket", "subprocess", "os.system",
        ):
            assert forbidden not in _source(), f"unexpected reach: {forbidden}"

    def test_deriving_the_record_writes_nothing(self):
        for forbidden in ("write_text", "write_bytes", "mkdir"):
            assert forbidden not in _source(), f"unexpected write: {forbidden}"

    def test_the_only_writing_is_into_a_directory_it_removes(self):
        """The verifiers stage real files, which cannot be done without writing.

        Staging is how the outcomes are measured at all -- re-implementing the
        extraction here to avoid the disk would measure a second reader and
        report it as the first. So it writes, and what this pins is where: a
        temporary directory the function creates and the context manager
        removes, never a path in the repository or the snapshot it was given.
        """
        source = _source()
        assert "tempfile.TemporaryDirectory" in source
        assert source.count("tempfile.TemporaryDirectory") == source.count(
            "with tempfile.TemporaryDirectory"
        ), "a temporary directory was made without a block that removes it"

    def test_the_snapshot_it_is_given_is_never_written_into(self):
        into = inspect.getsource(verify_rendering_reach)
        assert "into=Path(scratch)" in into
        assert "into=snapshot_root" not in into


def _source() -> str:
    return (
        Path(__file__).resolve().parents[1]
        / "core"
        / "agentic_v2_preregistration.py"
    ).read_text(encoding="utf-8")
