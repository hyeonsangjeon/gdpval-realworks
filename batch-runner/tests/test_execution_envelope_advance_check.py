"""The free checks that stand between the run-place comparison and a bill.

Every test here is about one of two things: that the five tasks were settled by
a rule rather than by taste, and that the check refuses to let anything start
while a condition is missing, inconsistent, or unaffordable.

Nothing here calls a model, signs in to a cloud account, or spends anything.
"""

from __future__ import annotations

import copy
import json
import os
import re
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BATCH_RUNNER_ROOT.parent
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core.execution_envelope_cost import (  # noqa: E402
    CostAssumptions,
    REFERENCE_FILE_CHARACTER_CAP,
    check_cost_ceiling,
    estimate_cost_ceiling,
    load_price_table,
    max_attempt_counts,
    max_input_tokens_per_call,
)
from core.execution_envelope_preflight import (  # noqa: E402
    COMPARABLE_ENVIRONMENTS,
    PLAN_VERSION,
    conditions_from_plan,
    load_plan,
    run_envelope_preflight,
)
from core.execution_envelope_tasks import (  # noqa: E402
    ADVANCE_CHECK_FORMAT_ORDER,
    ADVANCE_CHECK_TASK_COUNT,
    CATALOG_PATH,
    DATASET_REVISION,
    FORMAT_TEXT_ONLY,
    FULL_RUN_TASK_COUNT,
    TRIAL_RUN_TASK_COUNT,
    catalog_sha256,
    check_catalog_carries_no_scores,
    check_input_file_versions,
    full_run_tasks,
    load_task_catalog,
    reference_files_for,
    select_advance_check_tasks,
    select_trial_run_tasks,
    selection_matches,
)
from core.execution_environment_readiness import ModelRunConditions  # noqa: E402

PLAN_PATH = (
    BATCH_RUNNER_ROOT
    / "experiments"
    / "execution_envelope"
    / "advance_check_plan.yaml"
)

# The five tasks the fixed rule produces. Written out here as a separate copy
# so that changing the rule, or changing the plan, is not enough on its own to
# change which tasks run: this line has to be changed too, deliberately, in a
# reviewed change.
EXPECTED_ADVANCE_CHECK_TASKS = (
    "02aa1805-c658-4069-8a6a-02dec146063a",  # spreadsheet
    "0112fc9b-c3b2-4084-8993-5a4abb1f54f1",  # document
    "2ea2e5b5-257f-42e6-a7dc-93763f28b19d",  # presentation
    "3baa0009-5a60-4ae8-ae99-4955cb328ff3",  # picture
    "0818571f-5ff7-4d39-9d2c-ced5ae44299e",  # text answer only
)

APPROVED_ENOUGH = 100

# The Azure resource this comparison is pinned to, matching the plan. Used to
# build a settings environment in which the Azure run place is correctly
# configured, so tests can tell "everything is in order" apart from "one thing
# was changed on purpose".
PINNED_AZURE_ACCOUNT = "hjeon-fdpo-foundry-eus2"
PINNED_AZURE_PROJECT = "gdpval-realworks"
PINNED_PROJECT_ENDPOINT = (
    f"https://{PINNED_AZURE_ACCOUNT}.services.ai.azure.com"
    f"/api/projects/{PINNED_AZURE_PROJECT}"
)

FULLY_READY_ENVIRON = {
    "EXECUTION_COMPARISON_PAID_RUN_APPROVED": "yes",
    "AZURE_AI_ROUTE_PROFILE": "project-ci",
    "FOUNDRY_PROJECT_ENDPOINT": PINNED_PROJECT_ENDPOINT,
}


@pytest.fixture(scope="module")
def catalog():
    return load_task_catalog()


@pytest.fixture
def plan():
    return load_plan(PLAN_PATH)


def _ready_preflight(plan, **overrides):
    """Run the check with every outside condition satisfied."""
    settings = {
        "root": BATCH_RUNNER_ROOT,
        "docker_daemon_available": True,
        "docker_image_available": True,
        "azure_route_profile": "project-ci",
        "environ": FULLY_READY_ENVIRON,
    }
    settings.update(overrides)
    return run_envelope_preflight(plan, **settings)


def _approved(plan, amount=APPROVED_ENOUGH):
    plan = copy.deepcopy(plan)
    plan["cost"]["approved_maximum_usd"] = amount
    return plan


# ── The task catalogue holds nothing that could follow a score ────────────


def test_the_catalogue_holds_no_score(catalog):
    assert check_catalog_carries_no_scores() == []


def test_the_catalogue_describes_the_pinned_dataset(catalog):
    assert catalog.dataset_revision == DATASET_REVISION
    assert len(catalog.tasks) == FULL_RUN_TASK_COUNT


def test_the_catalogue_has_no_word_that_looks_like_a_result():
    """A blunt second look for anything result-shaped anywhere in the file."""
    text = CATALOG_PATH.read_text(encoding="utf-8").lower()
    for word in ("awarded", "verdict", "passed", "pct", "judge"):
        assert not re.search(rf'"[^"]*{word}[^"]*"\s*:', text), (
            f"the catalogue holds a field containing {word!r}"
        )


# ── The five tasks come from the rule, not from taste ─────────────────────


def test_the_rule_picks_the_five_tasks_written_down(catalog):
    selection = select_advance_check_tasks(catalog)
    assert selection.task_ids == EXPECTED_ADVANCE_CHECK_TASKS


def test_the_rule_gives_the_same_answer_every_time(catalog):
    first = select_advance_check_tasks(catalog)
    second = select_advance_check_tasks(catalog)
    assert first.task_ids == second.task_ids


def test_the_five_cover_five_different_deliverable_formats(catalog):
    selection = select_advance_check_tasks(catalog)
    formats = [entry[0] for entry in selection.reasons]
    assert formats == list(ADVANCE_CHECK_FORMAT_ORDER)
    assert len(set(formats)) == ADVANCE_CHECK_TASK_COUNT


def test_the_five_cover_five_different_jobs(catalog):
    selection = select_advance_check_tasks(catalog)
    by_id = catalog.by_task_id()
    jobs = [by_id[task_id].occupation for task_id in selection.task_ids]
    assert len(set(jobs)) == ADVANCE_CHECK_TASK_COUNT


def test_each_chosen_task_really_hands_in_the_format_it_was_chosen_for(catalog):
    by_id = catalog.by_task_id()
    selection = select_advance_check_tasks(catalog)
    for deliverable_format, task_id, _ in selection.reasons:
        task = by_id[task_id]
        if deliverable_format == FORMAT_TEXT_ONLY:
            assert task.deliverable_file_extensions == ()
        else:
            assert task.any_format_is(deliverable_format)


def test_the_selection_records_fingerprints_that_match_the_files(catalog):
    selection = select_advance_check_tasks(catalog)
    assert selection.catalog_sha256 == catalog_sha256()
    assert selection.dataset_file_sha256 == catalog.dataset_file_sha256
    assert len(selection.catalog_sha256) == 64


def test_a_changed_task_list_is_reported(catalog):
    selection = select_advance_check_tasks(catalog)
    swapped = list(selection.task_ids)
    swapped[0], swapped[1] = swapped[1], swapped[0]

    problems = selection_matches(swapped, selection)

    assert problems
    assert "does not match" in problems[0]


def test_the_plan_writes_down_exactly_what_the_rule_produced(plan, catalog):
    written = plan["model_run_conditions"]["shared"]["task_ids"]
    assert tuple(written) == select_advance_check_tasks(catalog).task_ids


def test_the_three_stages_hold_five_thirty_and_all_tasks(plan, catalog):
    sizes = plan["run_sizes"]
    assert len(sizes["advance_check"]["task_ids"]) == ADVANCE_CHECK_TASK_COUNT
    assert len(sizes["trial_run"]["task_ids"]) == TRIAL_RUN_TASK_COUNT
    assert len(sizes["full_run"]["task_ids"]) == FULL_RUN_TASK_COUNT
    assert sizes["trial_run"]["task_ids"] == list(select_trial_run_tasks(catalog))
    assert sizes["full_run"]["task_ids"] == list(full_run_tasks(catalog))


def test_the_thirty_keep_the_industry_mix(catalog):
    chosen = select_trial_run_tasks(catalog)
    by_id = catalog.by_task_id()
    industries = {by_id[task_id].sector for task_id in chosen}
    every_industry = {task.sector for task in catalog.tasks}
    assert industries == every_industry


# ── The input fingerprints describe the real inputs ───────────────────────


def test_the_plan_pins_every_reference_file_the_five_tasks_use(plan, catalog):
    conditions = conditions_from_plan(plan)
    for environment, entry in conditions.items():
        assert check_input_file_versions(
            entry.input_file_versions, entry.task_ids, catalog
        ) == [], environment


def test_a_reference_file_left_unpinned_is_reported(plan, catalog):
    conditions = conditions_from_plan(plan)
    entry = conditions["host_python_process"]
    trimmed = dict(entry.input_file_versions)
    dropped = sorted(reference_files_for(entry.task_ids, catalog))[0]
    trimmed.pop(dropped)

    problems = check_input_file_versions(trimmed, entry.task_ids, catalog)

    assert any("no written fingerprint" in note for note in problems)


def test_a_fingerprint_that_belongs_to_another_file_is_reported(plan, catalog):
    conditions = conditions_from_plan(plan)
    entry = conditions["host_python_process"]
    tampered = dict(entry.input_file_versions)
    target = sorted(reference_files_for(entry.task_ids, catalog))[0]
    tampered[target] = "0" * 64

    problems = check_input_file_versions(tampered, entry.task_ids, catalog)

    assert any("describes some other file" in note for note in problems)


def test_a_dataset_fingerprint_that_does_not_match_is_reported(plan, catalog):
    conditions = conditions_from_plan(plan)
    entry = conditions["host_python_process"]
    tampered = dict(entry.input_file_versions)
    key = f"{catalog.dataset_repo_id}@{catalog.dataset_revision}"
    tampered[key] = "1" * 64

    problems = check_input_file_versions(tampered, entry.task_ids, catalog)

    assert any("but the catalogue was built from" in note for note in problems)


# ── The price list stays in step with the rest of the repository ──────────


def test_the_price_list_matches_the_one_already_used_for_grading():
    """One price list, not two that quietly drift apart."""
    source = (REPOSITORY_ROOT / "scripts" / "analyze_grade_run.py").read_text(
        encoding="utf-8"
    )
    block = re.search(
        r"PRICING_USD_PER_M_TOKENS\s*=\s*\{(.*?)\}", source, re.S
    )
    assert block, "the grading price list could not be found"
    existing = {
        name: (Decimal(first), Decimal(second))
        for name, first, second in re.findall(
            r'"([^"]+)":\s*\(\s*([\d.]+)\s*,\s*([\d.]+)\s*\)', block.group(1)
        )
    }
    assert existing

    committed = load_price_table()
    for model, (input_price, output_price) in existing.items():
        assert model in committed, f"{model} is missing from the committed list"
        assert committed[model].input_usd_per_million == input_price
        assert committed[model].output_usd_per_million == output_price


def test_the_model_the_plan_uses_has_a_published_price(plan):
    conditions = conditions_from_plan(plan)
    prices = load_price_table()
    for entry in conditions.values():
        assert entry.resolved_model in prices


# ── The worst case is counted, and counted conservatively ─────────────────


def _conditions(**overrides):
    base = {
        "provider": "azure",
        "deployment": "gpt-5.4",
        "resolved_model": "gpt-5.4",
        "api_version": "2025-04-01-preview",
        "system_instruction": "a",
        "task_instruction": "b",
        "task_ids": ["02aa1805-c658-4069-8a6a-02dec146063a"],
        "input_file_versions": {},
        "max_output_tokens": 1000,
        "per_task_timeout_seconds": 60,
        "self_review_enabled": False,
        "self_review_max_attempts": 0,
        "retry_reasons_allowed": ["infrastructure_error"],
        "retry_max_attempts": 0,
        "automatic_model_switch_allowed": False,
    }
    base.update(overrides)
    return ModelRunConditions.from_mapping(base)


def test_one_attempt_with_no_retries_is_one_call():
    counts = max_attempt_counts(
        _conditions(),
        tool_loop_max_model_turns=1,
        output_tokens_capped_per_attempt=False,
    )
    assert counts.model_calls == 1
    assert counts.answer_lengths == 1


def test_every_allowed_retry_is_counted():
    counts = max_attempt_counts(
        _conditions(retry_max_attempts=3),
        tool_loop_max_model_turns=1,
        output_tokens_capped_per_attempt=False,
    )
    assert counts.model_calls == 4


def test_a_tool_loop_multiplies_the_calls_but_not_a_capped_answer():
    looping = max_attempt_counts(
        _conditions(retry_max_attempts=3),
        tool_loop_max_model_turns=8,
        output_tokens_capped_per_attempt=True,
    )
    assert looping.model_calls == 32
    assert looping.answer_lengths == 4


def test_self_review_adds_a_look_and_a_replacement():
    counts = max_attempt_counts(
        _conditions(self_review_enabled=True, self_review_max_attempts=2),
        tool_loop_max_model_turns=1,
        output_tokens_capped_per_attempt=False,
    )
    # One attempt, plus for each review: one look and one replacement.
    assert counts.model_calls == 1 + 2 * 2


def test_self_review_that_is_switched_off_costs_nothing():
    counts = max_attempt_counts(
        _conditions(self_review_enabled=False, self_review_max_attempts=0),
        tool_loop_max_model_turns=1,
        output_tokens_capped_per_attempt=False,
    )
    assert counts.model_calls == 1


def test_a_reference_file_is_counted_at_the_cap_the_reader_applies(catalog):
    assumptions = CostAssumptions.from_mapping(
        {
            "characters_per_token": 3,
            "instruction_character_count": 0,
            "tool_loop_max_model_turns": {"host_python_process": 1},
            "output_tokens_capped_per_attempt": {"host_python_process": False},
            "max_tool_result_tokens_per_turn": {"host_python_process": 0},
            "safety_multiplier": 1,
            "grading_required": False,
            "grading_model": "gpt-5.4",
            "grading_calls_per_rubric_item": 1,
            "grading_input_tokens_per_call": 1,
            "grading_output_tokens_per_call": 1,
        }
    )
    by_id = catalog.by_task_id()
    with_reference = by_id["2ea2e5b5-257f-42e6-a7dc-93763f28b19d"]
    assert with_reference.reference_file_count == 1

    tokens = max_input_tokens_per_call(with_reference, assumptions)

    expected = (with_reference.prompt_character_count + REFERENCE_FILE_CHARACTER_CAP) / 3
    assert tokens == pytest.approx(expected, abs=1)


def test_a_model_with_no_published_price_is_not_treated_as_free(catalog):
    assumptions = CostAssumptions.from_mapping(
        {
            "characters_per_token": 3,
            "instruction_character_count": 0,
            "tool_loop_max_model_turns": {"host_python_process": 1},
            "output_tokens_capped_per_attempt": {"host_python_process": False},
            "max_tool_result_tokens_per_turn": {"host_python_process": 0},
            "safety_multiplier": 1,
            "grading_required": False,
            "grading_model": "gpt-5.4",
            "grading_calls_per_rubric_item": 1,
            "grading_input_tokens_per_call": 1,
            "grading_output_tokens_per_call": 1,
        }
    )
    ceiling = estimate_cost_ceiling(
        conditions_by_environment={
            "host_python_process": _conditions(resolved_model="a-model-nobody-priced")
        },
        tasks_by_id=catalog.by_task_id(),
        assumptions=assumptions,
    )

    assert ceiling.unpriced_models == ["a-model-nobody-priced"]
    problems = check_cost_ceiling(ceiling, approved_maximum_usd=1000)
    assert any("no published price" in note for note in problems)


def test_a_missing_approved_amount_is_a_refusal(plan, catalog):
    """Removing the approved amount must stop the run, whatever else is right.

    The committed plan now records an approved amount, so this clears it on
    purpose rather than relying on it being absent.
    """
    plan = _approved(plan, None)

    result = _ready_preflight(plan)

    assert result.may_start is False
    assert any(
        "largest amount that may be spent" in note
        for note in result.all_problems
    )


def test_the_committed_plan_records_the_approved_amount(plan):
    """The amount that was approved, to the cent, and no more."""
    assert str(plan["cost"]["approved_maximum_usd"]) == "32.23"


def test_an_approved_amount_below_the_ceiling_is_a_refusal(plan):
    result = _ready_preflight(_approved(plan, "0.01"))
    assert result.may_start is False
    assert any("is above the" in note for note in result.all_problems)


def test_an_approved_amount_that_covers_the_ceiling_is_accepted(plan):
    result = _ready_preflight(_approved(plan))
    assert result.all_problems == []
    assert result.may_start is True


def test_the_worked_out_ceiling_is_reported_in_full(plan):
    result = _ready_preflight(_approved(plan))
    assert result.cost is not None
    written = result.cost.as_dict()
    assert {entry["environment"] for entry in written["environments"]} == set(
        COMPARABLE_ENVIRONMENTS
    )
    assert Decimal(written["most_the_whole_thing_could_cost_usd"]) > 0
    assert written["grading"]["most_model_calls"] > 0


def test_grading_is_counted_once_for_every_run_place(plan, catalog):
    result = _ready_preflight(_approved(plan))
    by_id = catalog.by_task_id()
    scoring_lines = sum(
        by_id[task_id].rubric_item_count for task_id in EXPECTED_ADVANCE_CHECK_TASKS
    )
    assert result.cost is not None
    assert result.cost.grading_model_calls == scoring_lines * len(
        COMPARABLE_ENVIRONMENTS
    )


def test_the_cost_sum_uses_the_wording_that_is_actually_sent(plan):
    plan = _approved(plan)
    plan["cost"]["assumptions"]["instruction_character_count"] = 1

    result = _ready_preflight(plan)

    assert any("but " in note and "sends" in note for note in result.all_problems)


# ── The check refuses every way the comparison could go wrong ─────────────


def test_no_approval_on_record_blocks_every_run_place(plan):
    result = _ready_preflight(_approved(plan), environ={})
    assert result.may_start is False
    assert set(result.readiness.blocked_environments) == set(
        COMPARABLE_ENVIRONMENTS
    )


def test_a_run_place_that_uses_a_different_deployment_is_refused(plan):
    plan = _approved(plan)
    plan["model_run_conditions"]["by_environment"]["docker_container"] = {
        "deployment": "gpt-5.4-mini"
    }

    result = _ready_preflight(plan)

    assert result.may_start is False
    assert any("deployment" in note for note in result.all_problems)


def test_a_run_place_that_uses_a_different_model_is_refused(plan):
    plan = _approved(plan)
    plan["model_run_conditions"]["by_environment"]["azure_code_interpreter"] = {
        "resolved_model": "gpt-5.4-mini"
    }

    result = _ready_preflight(plan)

    assert result.may_start is False


def test_a_run_place_allowed_to_change_model_on_its_own_is_refused(plan):
    plan = _approved(plan)
    plan["model_run_conditions"]["shared"]["automatic_model_switch_allowed"] = True

    result = _ready_preflight(plan)

    assert result.may_start is False
    # The reason has to reach the reader, not only the verdict. This one is
    # found by the readiness check rather than by the envelope check, so it
    # only appears if the two lists are shown together.
    assert any(
        "switching to another" in note for note in result.all_problems
    )


def test_every_refusal_says_why(plan):
    """A refusal with no stated reason is not usable by whoever has to fix it."""
    plan = _approved(plan)
    plan["model_run_conditions"]["shared"]["automatic_model_switch_allowed"] = True

    result = _ready_preflight(plan)

    assert result.may_start is False
    assert result.all_problems
    assert result.as_dict()["problems"] == result.all_problems


def test_a_run_place_with_different_wording_is_refused(plan):
    plan = _approved(plan)
    plan["model_run_conditions"]["by_environment"]["host_python_process"] = {
        "system_instruction": "Something else entirely.\n"
    }

    result = _ready_preflight(plan)

    assert result.may_start is False


def test_a_run_place_with_a_different_task_list_is_refused(plan):
    plan = _approved(plan)
    plan["model_run_conditions"]["by_environment"]["docker_container"] = {
        "task_ids": list(EXPECTED_ADVANCE_CHECK_TASKS[:4])
    }

    result = _ready_preflight(plan)

    assert result.may_start is False


def test_switching_self_review_on_for_this_comparison_is_refused(plan):
    plan = _approved(plan)
    plan["model_run_conditions"]["shared"]["self_review_enabled"] = True
    plan["model_run_conditions"]["shared"]["self_review_max_attempts"] = 2

    result = _ready_preflight(plan)

    assert result.may_start is False


def test_a_run_place_this_repository_cannot_score_is_refused(plan):
    plan = _approved(plan)
    plan["model_run_conditions"]["by_environment"]["agentic_sandbox_v2"] = {}

    result = _ready_preflight(plan)

    assert result.may_start is False
    assert any(
        "cannot run a scored comparison" in note for note in result.problems
    )


def test_a_plan_written_for_another_version_is_refused(plan):
    plan = _approved(plan)
    plan["plan_version"] = "something-else"

    result = _ready_preflight(plan)

    assert result.may_start is False


def test_a_missing_azure_connection_setting_blocks_that_run_place(plan):
    result = _ready_preflight(_approved(plan), azure_route_profile=None)

    assert result.may_start is False
    assert "azure_code_interpreter" in result.readiness.blocked_environments


def test_a_missing_docker_service_blocks_that_run_place(plan):
    result = _ready_preflight(_approved(plan), docker_daemon_available=False)

    assert result.may_start is False
    assert "docker_container" in result.readiness.blocked_environments


def test_a_missing_container_image_blocks_that_run_place(plan):
    result = _ready_preflight(_approved(plan), docker_image_available=False)

    assert result.may_start is False
    assert "docker_container" in result.readiness.blocked_environments


def test_an_experiment_settings_file_that_drifts_is_refused(plan, tmp_path):
    plan = _approved(plan)
    root = tmp_path / "batch-runner"
    (root / "experiments" / "execution_envelope").mkdir(parents=True)
    for environment, relative in plan["experiment_files"].items():
        settings = yaml.safe_load(
            (BATCH_RUNNER_ROOT / relative).read_text(encoding="utf-8")
        )
        if environment == "host_python_process":
            settings["condition_a"]["model"]["deployment"] = "gpt-5.4-mini"
        (root / relative).write_text(
            yaml.safe_dump(settings, sort_keys=False), encoding="utf-8"
        )

    result = run_envelope_preflight(
        plan,
        root=root,
        docker_daemon_available=True,
        docker_image_available=True,
        azure_route_profile="project-ci",
        environ=FULLY_READY_ENVIRON,
    )

    assert result.may_start is False
    assert any("gpt-5.4-mini" in note for note in result.all_problems)


def test_a_missing_experiment_settings_file_is_refused(plan, tmp_path):
    plan = _approved(plan)
    root = tmp_path / "batch-runner"
    (root / "experiments" / "execution_envelope").mkdir(parents=True)

    result = run_envelope_preflight(
        plan,
        root=root,
        docker_daemon_available=True,
        docker_image_available=True,
        azure_route_profile="project-ci",
        environ=FULLY_READY_ENVIRON,
    )

    assert result.may_start is False
    assert any("does not exist" in note for note in result.all_problems)


def _preflight_with_edited_settings(plan, tmp_path, environment, edit):
    """Copy the three settings files, change one, and run the check on them."""
    root = tmp_path / "batch-runner"
    (root / "experiments" / "execution_envelope").mkdir(parents=True)
    for name, relative in plan["experiment_files"].items():
        settings = yaml.safe_load(
            (BATCH_RUNNER_ROOT / relative).read_text(encoding="utf-8")
        )
        if name == environment:
            edit(settings)
        (root / relative).write_text(
            yaml.safe_dump(settings, sort_keys=False), encoding="utf-8"
        )
    return run_envelope_preflight(
        plan,
        root=root,
        docker_daemon_available=True,
        docker_image_available=True,
        azure_route_profile="project-ci",
        environ=FULLY_READY_ENVIRON,
    )


def test_a_settings_file_that_omits_the_answer_length_cap_is_refused(
    plan, tmp_path
):
    """Silence is not agreement: a missing cap falls back to a different one."""

    def drop_the_cap(settings):
        settings["execution"].pop("tokens", None)

    result = _preflight_with_edited_settings(
        _approved(plan), tmp_path, "host_python_process", drop_the_cap
    )

    assert result.may_start is False
    assert any(
        "does not say how much the model may write" in note
        for note in result.all_problems
    )


@pytest.mark.parametrize(
    "setting, value",
    [
        ("reasoning_effort", "high"),
        ("temperature", 0.7),
        ("seed", 99),
    ],
)
def test_run_places_that_disagree_on_an_unfixed_setting_are_refused(
    plan, tmp_path, setting, value
):
    """A setting the plan never mentions still has to be the same everywhere."""

    def change_it(settings):
        settings["condition_a"]["model"][setting] = value

    result = _preflight_with_edited_settings(
        _approved(plan), tmp_path, "docker_container", change_it
    )

    assert result.may_start is False
    assert any(
        f"({setting})" in note for note in result.all_problems
    ), result.all_problems


def test_the_three_settings_files_agree_on_the_unfixed_settings(plan):
    """Today they do, and nothing may quietly change that."""

    result = _ready_preflight(_approved(plan))

    assert result.all_problems == []


def test_the_committed_files_agree_with_the_committed_plan(plan):
    """The three settings files and the plan say the same thing today."""
    result = _ready_preflight(_approved(plan))
    assert result.all_problems == []


def test_the_plan_names_the_version_this_check_reads(plan):
    assert plan["plan_version"] == PLAN_VERSION


def test_the_two_comparisons_keep_separate_score_tables(plan):
    boards = plan["scoreboards"]
    assert set(boards) == {"same_generated_code_rerun", "tool_built_in_features"}
    for name, board in boards.items():
        assert board["comparison"] == name


# ── The Agentic Sandbox V2 guards are still shut ──────────────────────────


def test_the_agentic_sandbox_v2_guards_are_not_worked_around(plan):
    """The check exercises all three guards; none may have been opened."""
    result = _ready_preflight(_approved(plan))
    assert result.all_problems == []
    assert result.readiness.status_of("agentic_sandbox_v2") == "structure_check_only"


def test_the_codex_run_place_is_still_reported_as_absent(plan):
    result = _ready_preflight(_approved(plan))
    assert (
        result.readiness.status_of("codex_built_in_agent")
        == "not_implemented_in_this_repository"
    )


def test_neither_absent_run_place_is_quietly_replaced(plan):
    """An empty slot stays empty; it is never filled with a working place."""
    result = _ready_preflight(_approved(plan))
    assert set(result.readiness.compared_environments) == set(
        COMPARABLE_ENVIRONMENTS
    )
    assert "agentic_sandbox_v2" not in result.readiness.compared_environments
    assert "codex_built_in_agent" not in result.readiness.compared_environments


# ── The committed catalogue still describes the pinned dataset ────────────


def test_the_committed_catalogue_is_internally_consistent(catalog):
    raw = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    assert raw["dataset_revision"] == DATASET_REVISION
    assert len(raw["tasks"]) == FULL_RUN_TASK_COUNT
    assert [entry["task_id"] for entry in raw["tasks"]] == sorted(
        entry["task_id"] for entry in raw["tasks"]
    )
    for entry in raw["tasks"]:
        assert len(entry["prompt_sha256"]) == 64
        assert entry["reference_file_count"] == len(entry["reference_file_paths"])


# ── The tool a person actually runs is present and refuses today ──────────


CHECK_SCRIPT = (
    BATCH_RUNNER_ROOT / "scripts" / "check_execution_envelope_advance_check.py"
)
CATALOG_SCRIPT = (
    BATCH_RUNNER_ROOT / "scripts" / "build_gdpval_task_catalog.py"
)


@pytest.mark.parametrize("script", [CHECK_SCRIPT, CATALOG_SCRIPT])
def test_the_scripts_are_in_the_repository(script):
    """A check nobody can run is not a check.

    `batch-runner/scripts/` is ignored by default with a per-file allow list,
    so a new tool there is invisible in a fresh clone unless it is added to
    that list. This fails if that step is ever missed.
    """
    assert script.is_file(), f"{script.name} is missing from a fresh checkout"
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", str(script)],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
    )
    assert tracked.returncode == 0, (
        f"{script.name} exists here but git does not track it. Add it to the "
        "allow list in .gitignore under batch-runner/scripts/."
    )


def test_the_check_refuses_today_and_says_why():
    """Run the tool exactly as a person would, and require a refusal.

    Two separate things are wrong today and the report must name both. The
    Azure run place is not reachable from an ordinary checkout, and the amount
    approved on 2026-08-25 no longer covers the worked-out ceiling, because it
    was agreed while a looping request was undercounted.
    """
    finished = subprocess.run(
        [sys.executable, str(CHECK_SCRIPT)],
        cwd=BATCH_RUNNER_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
        env={
            **{
                key: value
                for key, value in os.environ.items()
                if key
                not in {
                    "AZURE_AI_ROUTE_PROFILE",
                    "FOUNDRY_PROJECT_ENDPOINT",
                    "AZURE_OPENAI_V1_ENDPOINT",
                }
            },
            "EXECUTION_COMPARISON_PAID_RUN_APPROVED": "",
        },
    )

    assert finished.returncode == 1, finished.stdout + finished.stderr
    assert "no model was called" in finished.stdout
    assert "AZURE_AI_ROUTE_PROFILE is not set" in finished.stdout
    assert "FOUNDRY_PROJECT_ENDPOINT is not set" in finished.stdout
    assert "is above the" in finished.stdout


# ── The Azure run place must reach the deployment that was pinned ─────────
#
# A deployment name does not identify a deployment. The tenant this comparison
# was first attempted from held two Azure AI Foundry accounts that each exposed
# a deployment named exactly "gpt-5.4". Pinning the name alone would let the
# comparison run against a resource nobody intended and report success.


def _environ_with(**overrides):
    settings = dict(FULLY_READY_ENVIRON)
    for key, value in overrides.items():
        if value is None:
            settings.pop(key, None)
        else:
            settings[key] = value
    return settings


def test_the_plan_pins_the_azure_account_and_project(plan):
    pinned = plan["azure_connection"]
    assert pinned["account"] == PINNED_AZURE_ACCOUNT
    assert pinned["project"] == PINNED_AZURE_PROJECT
    assert pinned["route_profile"] == "project-ci"


def test_a_correctly_pointed_azure_setup_is_accepted(plan):
    result = _ready_preflight(_approved(plan))

    assert result.azure is not None
    assert result.azure.problems == []
    assert result.azure.observed_account == PINNED_AZURE_ACCOUNT
    assert result.azure.observed_project == PINNED_AZURE_PROJECT
    assert result.may_start is True


def test_the_same_deployment_name_on_another_account_is_refused(plan):
    """The exact hole this block was added to close.

    The settings are well formed, the route is right, and the deployment name
    is unchanged. Only the account differs — which is precisely the case that
    used to pass.
    """
    other = (
        "https://some-other-account.services.ai.azure.com"
        f"/api/projects/{PINNED_AZURE_PROJECT}"
    )
    result = _ready_preflight(
        _approved(plan),
        environ=_environ_with(FOUNDRY_PROJECT_ENDPOINT=other),
    )

    assert result.may_start is False
    assert any(
        "is not unique across accounts" in note for note in result.all_problems
    )


def test_another_project_on_the_right_account_is_refused(plan):
    other = (
        f"https://{PINNED_AZURE_ACCOUNT}.services.ai.azure.com"
        "/api/projects/some-other-project"
    )
    result = _ready_preflight(
        _approved(plan),
        environ=_environ_with(FOUNDRY_PROJECT_ENDPOINT=other),
    )

    assert result.may_start is False
    assert any("names the project" in note for note in result.all_problems)


def test_a_missing_project_address_says_what_it_should_look_like(plan):
    result = _ready_preflight(
        _approved(plan), environ=_environ_with(FOUNDRY_PROJECT_ENDPOINT=None)
    )

    assert result.may_start is False
    assert any(
        PINNED_AZURE_ACCOUNT in note and "services.ai.azure.com" in note
        for note in result.all_problems
    )


def test_a_missing_route_profile_is_told_apart_from_a_wrong_one(plan):
    """"Not set" and "set to the wrong thing" need different fixes."""
    missing = _ready_preflight(
        _approved(plan), environ=_environ_with(AZURE_AI_ROUTE_PROFILE=None)
    )
    wrong = _ready_preflight(
        _approved(plan),
        environ=_environ_with(AZURE_AI_ROUTE_PROFILE="direct-v1"),
    )

    assert any("is not set" in note for note in missing.all_problems)
    assert any("'direct-v1'" in note for note in wrong.all_problems)


def test_the_deprecated_endpoint_setting_is_refused(plan):
    result = _ready_preflight(
        _approved(plan),
        environ=_environ_with(
            AZURE_OPENAI_ENDPOINT="https://something.openai.azure.com/"
        ),
    )

    assert result.may_start is False
    assert any(
        "does not say which kind of endpoint" in note
        for note in result.all_problems
    )


@pytest.mark.parametrize(
    "variable", ["AZURE_OPENAI_API_KEY", "AZURE_CLIENT_SECRET"]
)
def test_a_fixed_credential_is_refused_up_front(plan, variable):
    """Say so during the free check, not after the run has been scheduled."""
    result = _ready_preflight(
        _approved(plan), environ=_environ_with(**{variable: "value-not-read"})
    )

    assert result.may_start is False
    assert any(variable in note for note in result.all_problems)


def test_a_direct_address_on_another_account_is_refused(plan):
    result = _ready_preflight(
        _approved(plan),
        environ=_environ_with(
            AZURE_OPENAI_V1_ENDPOINT=(
                "https://some-other-account.services.ai.azure.com/openai/v1/"
            )
        ),
    )

    assert result.may_start is False
    assert any(
        "AZURE_OPENAI_V1_ENDPOINT" in note for note in result.all_problems
    )


def test_a_plan_that_forgets_to_pin_the_account_is_refused(plan):
    plan = _approved(plan)
    plan.pop("azure_connection")

    result = _ready_preflight(plan)

    assert result.may_start is False
    assert any(
        "not unique across accounts" in note for note in result.all_problems
    )


def test_the_azure_check_is_skipped_when_azure_does_not_take_part(plan):
    """A plan without the Azure run place has no Azure resource to get wrong."""
    plan = _approved(plan)
    plan["model_run_conditions"]["by_environment"].pop("azure_code_interpreter")
    plan["experiment_files"].pop("azure_code_interpreter")
    plan.pop("azure_connection")

    result = _ready_preflight(plan, environ=_environ_with(
        AZURE_AI_ROUTE_PROFILE=None, FOUNDRY_PROJECT_ENDPOINT=None
    ))

    assert result.azure is None
    assert not any("AZURE" in note for note in result.all_problems)


# ── The written specifications must survive a fresh checkout ─────────────
#
# Both `batch-runner/scripts/` and `tasks/0822_saturday/` are ignored by
# default with a per-file allow list. A document added to either without being
# added to that list is invisible to anyone who clones the repository, which
# makes it useless exactly when someone needs it.

SPECIFICATION_FILES = (
    "tasks/0822_saturday/TASK_GPT_EXECUTION_ENVELOPE_BENCHMARK.md",
    "tasks/0822_saturday/TASK_PIN_AZURE_RESOURCE_IDENTITY.md",
    "tasks/0822_saturday/TASK_AGENTIC_SANDBOX_V2_FOUNDATION.md",
    "tasks/0822_saturday/TASK_NATIVE_CODEX_RUN_PATH.md",
)


@pytest.mark.parametrize("relative", SPECIFICATION_FILES)
def test_the_specifications_are_in_the_repository(relative):
    path = REPOSITORY_ROOT / relative
    assert path.is_file(), f"{relative} is missing"
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", relative],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
    )
    assert tracked.returncode == 0, (
        f"{relative} exists here but git does not track it, so a fresh clone "
        "would not have it. Add it to the allow list in .gitignore."
    )
