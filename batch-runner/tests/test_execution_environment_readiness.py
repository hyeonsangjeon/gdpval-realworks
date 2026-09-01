"""Tests for the free readiness check on the eight run places.

Nothing in this file calls a model, contacts a provider, or spends money.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from core.execution_environment_readiness import (
    COMPARISON_SAME_GENERATED_CODE,
    COMPARISONS,
    COMPARISON_NATIVE_PRODUCT_BUNDLE,
    COMPARISON_TOOL_BUILT_IN_FEATURES,
    ENVIRONMENT_AGENTIC_SANDBOX_V2,
    ENVIRONMENT_AZURE_CODE_INTERPRETER,
    ENVIRONMENT_CODEX_BUILT_IN_AGENT,
    ENVIRONMENT_DOCKER_CONTAINER,
    ENVIRONMENT_HOST_PYTHON_PROCESS,
    ENVIRONMENTS,
    PAID_RUN_APPROVAL_VARIABLE,
    REQUIRED_RUN_RECORD_FIELDS,
    RETRY_INFRASTRUCTURE_ERROR,
    RETRY_MODEL_SELF_REVIEW,
    RETRY_REASONS,
    RETRY_TOOL_LOOP_INTERNAL_RECOVERY,
    RUN_SIZE_TASK_COUNTS,
    SAME_MODEL_COMPARISONS,
    SERVING_PATH_MICROSOFT_FOUNDRY_DEPLOYMENT,
    STATUS_BLOCKED_REQUIREMENT_UNMET,
    STATUS_CAN_RUN_REAL_EXPERIMENT,
    STATUS_EVIDENCE_INSUFFICIENT,
    STATUS_NOT_IMPLEMENTED_HERE,
    STATUS_STRUCTURE_CHECK_ONLY,
    STATUSES,
    ModelRunConditions,
    build_readiness_report,
    check_agentic_sandbox_v2_blocks_are_intact,
    check_comparisons_are_scored_apart,
    check_model_run_conditions,
    check_run_record_fields,
    check_run_size_plan,
    describe_environment,
    inspect_environment_support,
    registered_execution_modes,
)
import core.execution_environment_readiness as readiness

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]

APPROVED = {PAID_RUN_APPROVAL_VARIABLE: "yes"}


def _conditions(**overrides) -> ModelRunConditions:
    base = {
        "provider": "azure",
        "resource": "fixed-foundry-resource",
        "deployment": "fixed-deployment",
        "resolved_model": "fixed-model-2026-01-01",
        "api_version": "2025-04-01-preview",
        "model_serving_path": SERVING_PATH_MICROSOFT_FOUNDRY_DEPLOYMENT,
        "system_instruction": "You complete professional tasks.",
        "task_instruction": "Produce the requested deliverable files.",
        "task_ids": ("task-1", "task-2"),
        "input_file_versions": {"reference_files/a.xlsx": "a" * 64},
        "max_output_tokens": 16384,
        "per_task_timeout_seconds": 570,
        "self_review_enabled": False,
        "self_review_max_attempts": 0,
        "retry_reasons_allowed": (RETRY_INFRASTRUCTURE_ERROR,),
        "retry_max_attempts": 3,
        "automatic_model_switch_allowed": False,
        "automatic_fallback_allowed": False,
        "unsupported_runner_substitution_allowed": False,
    }
    base.update(overrides)
    return ModelRunConditions.from_mapping(base)


def _ready_container_arguments() -> dict:
    return {
        "docker_daemon_available": True,
        "docker_image_available": True,
        "docker_run_setting": "always",
        "azure_route_profile": "project-ci",
        "azure_route_served": True,
    }


# ── The eight run places and the five states ───────────────────────────────


def test_exactly_eight_run_places_are_graded_into_the_five_known_states():
    entries = inspect_environment_support()
    assert [entry.environment for entry in entries] == list(ENVIRONMENTS)
    assert len(ENVIRONMENTS) == 8
    assert len(STATUSES) == 5
    for entry in entries:
        assert entry.status in STATUSES
        assert entry.evidence, f"{entry.environment} was graded with no evidence"


def test_every_run_place_has_a_plain_description():
    for environment in ENVIRONMENTS:
        description = describe_environment(environment)
        assert len(description.split()) >= 8, (
            f"{environment} needs a description a reader can act on"
        )


@pytest.mark.parametrize("environment", ENVIRONMENTS)
def test_descriptions_and_evidence_avoid_private_jargon(environment):
    banned = (
        "model wave",
        "arm ",
        "runtime-only",
        "native bundle",
        "harness",
        "provenance",
        "fail closed",
        "envelope",
    )
    entry = _entry(inspect_environment_support(), environment)
    text = " ".join(
        [describe_environment(environment), *entry.evidence, *entry.blockers]
    ).lower()
    for word in banned:
        assert word not in text, (
            f"{environment} is described with the in-house term {word!r}; a "
            "reader should not need a word list"
        )


def test_host_python_process_can_run_a_real_experiment_today():
    entry = _entry(inspect_environment_support(), ENVIRONMENT_HOST_PYTHON_PROCESS)
    assert entry.status == STATUS_CAN_RUN_REAL_EXPERIMENT
    assert any("subprocess" in note for note in entry.evidence)


def test_codex_is_reported_as_absent_from_this_repository():
    entry = _entry(inspect_environment_support(), ENVIRONMENT_CODEX_BUILT_IN_AGENT)
    assert entry.status == STATUS_NOT_IMPLEMENTED_HERE
    assert entry.blockers
    assert all(
        "codex" not in mode for mode in registered_execution_modes()
    ), "a Codex run mode appeared; the recorded state must be refreshed"


def test_agentic_sandbox_v2_is_structure_check_only():
    entry = _entry(inspect_environment_support(), ENVIRONMENT_AGENTIC_SANDBOX_V2)
    assert entry.status == STATUS_STRUCTURE_CHECK_ONLY
    assert any("exec_run" in note for note in entry.evidence)
    assert any("exec_run" in note for note in entry.blockers)


def _entry(entries, environment):
    return next(entry for entry in entries if entry.environment == environment)


# ── The Agentic Sandbox V2 blocks must stay closed ─────────────────────────


def test_agentic_sandbox_v2_blocks_are_intact_in_this_repository():
    assert check_agentic_sandbox_v2_blocks_are_intact() == []


def test_a_reopened_inference_pipeline_block_is_reported(monkeypatch):
    import step2_run_inference

    monkeypatch.setattr(
        step2_run_inference,
        "_require_runnable_execution_mode",
        lambda mode: None,
    )
    problems = check_agentic_sandbox_v2_blocks_are_intact()
    assert any("no longer refuses" in problem for problem in problems)


def test_a_dispatcher_that_builds_v2_for_a_paid_run_is_reported(monkeypatch):
    class PermissiveExecutor:
        def __init__(self, **_kwargs):
            pass

    import core.executor

    monkeypatch.setattr(core.executor, "TaskExecutor", PermissiveExecutor)
    problems = check_agentic_sandbox_v2_blocks_are_intact()
    assert any(
        "declared to make paid model calls" in problem for problem in problems
    )


def test_an_exec_run_tool_that_accepts_commands_is_reported(monkeypatch):
    class PermissiveBackend:
        def __init__(self, **_kwargs):
            pass

        def exec_run(self, _arguments):
            return {"ok": True, "data": {"returncode": 0}}

    import core.agentic_v2_fixture_backend as fixture_backend

    monkeypatch.setattr(
        fixture_backend, "AgenticV2FixtureBackend", PermissiveBackend
    )
    problems = check_agentic_sandbox_v2_blocks_are_intact()
    assert any("accepted an ordinary command" in problem for problem in problems)


def test_the_real_exec_run_tool_refuses_an_ordinary_command():
    from core.agentic_v2_contract import AgenticV2Profile
    from core.agentic_v2_fixture_backend import AgenticV2FixtureBackend

    problems = readiness._check_exec_run_stays_unavailable(
        AgenticV2FixtureBackend
    )
    assert problems == []
    assert AgenticV2Profile.from_mapping(
        dict(readiness.STRUCTURE_CHECK_PROFILE)
    ).foundation_only is True


def test_a_dispatcher_that_refuses_for_the_wrong_reason_is_reported():
    """Deleting the paid-run block must not hide behind a later complaint.

    The dispatcher raises for seven different reasons in this branch. If the
    check accepted any of them, removing the paid-run block would go unnoticed
    because a missing-argument complaint would take its place.
    """

    class WrongReasonExecutor:
        def __init__(self, **kwargs):
            raise ValueError(
                "agentic_sandbox_v2 foundation requires a fixture root"
            )

    problems = readiness._check_dispatcher_refuses_a_paid_v2_run(
        WrongReasonExecutor
    )
    assert any("unexpected reason" in problem for problem in problems)
    assert any("may have been removed" in problem for problem in problems)


def test_a_dispatcher_missing_only_the_paid_run_block_is_reported():
    """Reproduce the real branch with just the paid-run block deleted."""

    class GateRemovedExecutor:
        def __init__(self, **kwargs):
            if kwargs.get("llm_client") is not None:
                raise ValueError("agentic_sandbox_v2 foundation refuses model clients")
            if kwargs.get("agentic_v2_fixture_root") is None:
                raise ValueError(
                    "agentic_sandbox_v2 foundation requires a fixture root"
                )
            if not isinstance(kwargs.get("agentic_v2_scripted_calls"), (list, tuple)):
                raise ValueError(
                    "agentic_sandbox_v2 foundation requires scripted calls"
                )

    problems = readiness._check_dispatcher_refuses_a_paid_v2_run(
        GateRemovedExecutor
    )
    assert any(
        "declared to make paid model calls" in problem for problem in problems
    )


def test_the_real_dispatcher_refuses_a_paid_v2_run_by_name():
    from core.executor import TaskExecutor

    assert readiness._check_dispatcher_refuses_a_paid_v2_run(TaskExecutor) == []


# ── The container run place must not be swapped for the host machine ───────


def test_container_run_place_is_blocked_when_it_may_fall_back_to_the_host():
    entries = inspect_environment_support(
        docker_daemon_available=True,
        docker_image_available=True,
        docker_run_setting="auto",
    )
    entry = _entry(entries, ENVIRONMENT_DOCKER_CONTAINER)
    assert entry.status == STATUS_BLOCKED_REQUIREMENT_UNMET
    assert any("'always'" in note for note in entry.blockers)


def test_container_run_place_is_blocked_when_docker_is_missing():
    entries = inspect_environment_support(
        docker_daemon_available=False,
        docker_image_available=False,
        docker_run_setting="always",
    )
    entry = _entry(entries, ENVIRONMENT_DOCKER_CONTAINER)
    assert entry.status == STATUS_BLOCKED_REQUIREMENT_UNMET
    assert any("Docker service" in note for note in entry.blockers)


def test_container_run_place_is_blocked_when_the_image_is_missing():
    entries = inspect_environment_support(
        docker_daemon_available=True,
        docker_image_available=False,
        docker_run_setting="always",
    )
    entry = _entry(entries, ENVIRONMENT_DOCKER_CONTAINER)
    assert entry.status == STATUS_BLOCKED_REQUIREMENT_UNMET
    assert any("image" in note for note in entry.blockers)


def test_unmeasured_container_support_is_not_reported_as_ready():
    entries = inspect_environment_support(docker_run_setting="always")
    entry = _entry(entries, ENVIRONMENT_DOCKER_CONTAINER)
    assert entry.status == STATUS_EVIDENCE_INSUFFICIENT


def test_container_run_place_is_ready_when_the_container_is_required_and_present():
    entries = inspect_environment_support(
        docker_daemon_available=True,
        docker_image_available=True,
        docker_run_setting="always",
    )
    entry = _entry(entries, ENVIRONMENT_DOCKER_CONTAINER)
    assert entry.status == STATUS_CAN_RUN_REAL_EXPERIMENT


# ── The Azure run place needs its route setting ────────────────────────────


def test_azure_code_interpreter_is_blocked_without_the_required_route():
    entries = inspect_environment_support(azure_route_profile="direct")
    entry = _entry(entries, ENVIRONMENT_AZURE_CODE_INTERPRETER)
    assert entry.status == STATUS_BLOCKED_REQUIREMENT_UNMET


def test_azure_code_interpreter_is_ready_with_the_required_route():
    entries = inspect_environment_support(
        azure_route_profile="project-ci", azure_route_served=True
    )
    entry = _entry(entries, ENVIRONMENT_AZURE_CODE_INTERPRETER)
    assert entry.status == STATUS_CAN_RUN_REAL_EXPERIMENT


def test_the_required_azure_route_name_comes_from_the_shipped_code():
    from core.azure_ai_clients import RouteProfile

    entries = inspect_environment_support(
        azure_route_profile=RouteProfile.PROJECT_CI.value,
        azure_route_served=True,
    )
    entry = _entry(entries, ENVIRONMENT_AZURE_CODE_INTERPRETER)
    assert entry.status == STATUS_CAN_RUN_REAL_EXPERIMENT


# ── No paid model call without an approval ─────────────────────────────────


def test_no_run_place_is_ready_while_paid_calls_are_unapproved():
    report = build_readiness_report(environ={}, **_ready_container_arguments())
    assert report.paid_model_calls_approved is False
    for entry in report.environments:
        assert entry.status != STATUS_CAN_RUN_REAL_EXPERIMENT


def test_an_unapproved_run_names_the_approval_setting():
    report = build_readiness_report(environ={}, **_ready_container_arguments())
    entry = _entry(report.environments, ENVIRONMENT_HOST_PYTHON_PROCESS)
    assert any(PAID_RUN_APPROVAL_VARIABLE in note for note in entry.blockers)


def test_an_approval_makes_only_the_supported_run_places_ready():
    report = build_readiness_report(
        environ=APPROVED, **_ready_container_arguments()
    )
    assert report.paid_model_calls_approved is True
    assert (
        report.status_of(ENVIRONMENT_HOST_PYTHON_PROCESS)
        == STATUS_CAN_RUN_REAL_EXPERIMENT
    )
    assert (
        report.status_of(ENVIRONMENT_DOCKER_CONTAINER)
        == STATUS_CAN_RUN_REAL_EXPERIMENT
    )
    assert (
        report.status_of(ENVIRONMENT_AZURE_CODE_INTERPRETER)
        == STATUS_CAN_RUN_REAL_EXPERIMENT
    )


def test_an_approval_never_upgrades_an_unsupported_run_place():
    report = build_readiness_report(
        environ=APPROVED, **_ready_container_arguments()
    )
    assert (
        report.status_of(ENVIRONMENT_AGENTIC_SANDBOX_V2)
        == STATUS_STRUCTURE_CHECK_ONLY
    )
    assert (
        report.status_of(ENVIRONMENT_CODEX_BUILT_IN_AGENT)
        == STATUS_NOT_IMPLEMENTED_HERE
    )


def test_an_unsupported_run_place_is_never_swapped_for_a_supported_one():
    report = build_readiness_report(
        environ=APPROVED, **_ready_container_arguments()
    )
    graded = {entry.environment for entry in report.environments}
    assert graded == set(ENVIRONMENTS)
    for environment in (
        ENVIRONMENT_AGENTIC_SANDBOX_V2,
        ENVIRONMENT_CODEX_BUILT_IN_AGENT,
    ):
        entry = _entry(report.environments, environment)
        assert entry.blockers, (
            f"{environment} cannot run yet, so the reason must be written down "
            "rather than replaced by another run place"
        )


@pytest.mark.parametrize("value", ["", "no", "true", "YES ", "1"])
def test_only_an_explicit_yes_approves_paid_calls(value):
    report = build_readiness_report(
        environ={PAID_RUN_APPROVAL_VARIABLE: value},
        **_ready_container_arguments(),
    )
    assert report.paid_model_calls_approved is (value.strip().lower() == "yes")


# ── One fixed set of model run conditions for every run place ──────────────


def test_matching_model_run_conditions_pass():
    assert check_model_run_conditions(
        {
            ENVIRONMENT_HOST_PYTHON_PROCESS: _conditions(),
            ENVIRONMENT_DOCKER_CONTAINER: _conditions(),
        }
    ) == []


def test_a_different_deployment_in_one_run_place_is_reported():
    problems = check_model_run_conditions(
        {
            ENVIRONMENT_HOST_PYTHON_PROCESS: _conditions(),
            ENVIRONMENT_DOCKER_CONTAINER: _conditions(deployment="other"),
        }
    )
    assert any("do not share one fixed set" in problem for problem in problems)


@pytest.mark.parametrize(
    "field,value",
    [
        ("provider", "openai"),
        ("resource", "another-foundry-resource"),
        ("resolved_model", "another-model"),
        ("api_version", "2024-01-01"),
        ("system_instruction", "different"),
        ("task_instruction", "different"),
        ("task_ids", ("task-1",)),
        ("input_file_versions", {"reference_files/a.xlsx": "b" * 64}),
        ("max_output_tokens", 4096),
        ("per_task_timeout_seconds", 60),
    ],
)
def test_any_difference_in_the_shared_conditions_is_reported(field, value):
    for comparison in SAME_MODEL_COMPARISONS:
        problems = check_model_run_conditions(
            {
                ENVIRONMENT_HOST_PYTHON_PROCESS: _conditions(),
                ENVIRONMENT_DOCKER_CONTAINER: _conditions(**{field: value}),
            },
            comparison=comparison,
        )
        assert any(
            "do not share one fixed set" in problem for problem in problems
        ), f"{field} went unreported in {comparison}"


@pytest.mark.parametrize(
    "field,value",
    [
        ("system_instruction", "different"),
        ("task_instruction", "different"),
        ("task_ids", ("task-1",)),
        ("input_file_versions", {"reference_files/a.xlsx": "b" * 64}),
        ("max_output_tokens", 4096),
        ("per_task_timeout_seconds", 60),
    ],
)
def test_the_whole_product_comparison_still_fixes_the_question_and_the_budget(
    field, value
):
    """Products may answer from their own model. They may not be asked
    different questions, given different files, or allowed different budgets —
    otherwise the score says as much about the plan as about the product."""
    problems = check_model_run_conditions(
        {
            ENVIRONMENT_HOST_PYTHON_PROCESS: _conditions(),
            ENVIRONMENT_DOCKER_CONTAINER: _conditions(**{field: value}),
        },
        comparison=COMPARISON_NATIVE_PRODUCT_BUNDLE,
    )
    assert any(
        "not being asked the same thing for the same money" in problem
        for problem in problems
    ), f"{field} went unreported in {COMPARISON_NATIVE_PRODUCT_BUNDLE}"


@pytest.mark.parametrize(
    "field,value",
    [
        ("provider", "openai"),
        ("resource", "another-foundry-resource"),
        ("deployment", "another-deployment"),
        ("resolved_model", "another-model"),
        ("api_version", "2024-01-01"),
    ],
)
def test_the_whole_product_comparison_lets_the_model_route_differ(field, value):
    """That is the whole point of it: each product answers from wherever it
    normally answers, which is why its score may never be read as a statement
    about a run place."""
    assert check_model_run_conditions(
        {
            ENVIRONMENT_HOST_PYTHON_PROCESS: _conditions(),
            ENVIRONMENT_DOCKER_CONTAINER: _conditions(**{field: value}),
        },
        comparison=COMPARISON_NATIVE_PRODUCT_BUNDLE,
    ) == []


@pytest.mark.parametrize(
    "overrides",
    [
        {"self_review_enabled": True, "self_review_max_attempts": 9},
        {"retry_reasons_allowed": RETRY_REASONS},
        {"retry_max_attempts": 25},
    ],
)
def test_differing_review_and_retry_settings_break_the_first_comparison(
    overrides,
):
    problems = check_model_run_conditions(
        {
            ENVIRONMENT_HOST_PYTHON_PROCESS: _conditions(),
            ENVIRONMENT_DOCKER_CONTAINER: _conditions(**overrides),
        },
        comparison=COMPARISON_SAME_GENERATED_CODE,
    )
    assert problems, f"{overrides} may not differ when the same code is re-run"


@pytest.mark.parametrize(
    "overrides",
    [
        {"self_review_enabled": True, "self_review_max_attempts": 9},
        {"retry_reasons_allowed": RETRY_REASONS},
        {"retry_max_attempts": 25},
    ],
)
def test_differing_review_and_retry_settings_are_fine_in_the_second_comparison(
    overrides,
):
    assert check_model_run_conditions(
        {
            ENVIRONMENT_HOST_PYTHON_PROCESS: _conditions(),
            ENVIRONMENT_DOCKER_CONTAINER: _conditions(**overrides),
        },
        comparison=COMPARISON_TOOL_BUILT_IN_FEATURES,
    ) == []


def test_the_first_comparison_refuses_self_review():
    problems = check_model_run_conditions(
        {
            ENVIRONMENT_HOST_PYTHON_PROCESS: _conditions(
                self_review_enabled=True, self_review_max_attempts=1
            )
        },
        comparison=COMPARISON_SAME_GENERATED_CODE,
    )
    assert any("must leave it off" in problem for problem in problems)


def test_the_second_comparison_allows_self_review():
    assert check_model_run_conditions(
        {
            ENVIRONMENT_HOST_PYTHON_PROCESS: _conditions(
                self_review_enabled=True, self_review_max_attempts=1
            )
        },
        comparison=COMPARISON_TOOL_BUILT_IN_FEATURES,
    ) == []


def test_an_unknown_comparison_name_is_reported():
    problems = check_model_run_conditions(
        {ENVIRONMENT_HOST_PYTHON_PROCESS: _conditions()},
        comparison="one_combined_score",
    )
    assert any("not one of the three comparisons" in problem for problem in problems)


def test_automatic_model_switching_is_refused():
    problems = check_model_run_conditions(
        {
            ENVIRONMENT_HOST_PYTHON_PROCESS: _conditions(
                automatic_model_switch_allowed=True
            )
        }
    )
    assert any("switching to another model" in problem for problem in problems)


def test_an_unknown_retry_reason_is_refused():
    problems = check_model_run_conditions(
        {
            ENVIRONMENT_HOST_PYTHON_PROCESS: _conditions(
                retry_reasons_allowed=("whenever_it_feels_like_it",)
            )
        }
    )
    assert any("retry reasons that are not one" in problem for problem in problems)


def test_all_three_retry_reasons_are_accepted():
    assert check_model_run_conditions(
        {
            ENVIRONMENT_HOST_PYTHON_PROCESS: _conditions(
                retry_reasons_allowed=RETRY_REASONS
            )
        }
    ) == []


def test_every_fixed_condition_field_is_required():
    complete = dict(
        provider="azure",
        resource="r",
        deployment="d",
        resolved_model="m",
        api_version="v",
        model_serving_path=SERVING_PATH_MICROSOFT_FOUNDRY_DEPLOYMENT,
        system_instruction="s",
        task_instruction="t",
        task_ids=["task-1"],
        input_file_versions={},
        max_output_tokens=1,
        per_task_timeout_seconds=1,
        self_review_enabled=False,
        self_review_max_attempts=0,
        retry_reasons_allowed=[],
        retry_max_attempts=0,
        automatic_model_switch_allowed=False,
        automatic_fallback_allowed=False,
        unsupported_runner_substitution_allowed=False,
    )
    assert set(complete) == set(ModelRunConditions.field_names())
    assert len(complete) == 19
    for name in complete:
        incomplete = {key: value for key, value in complete.items() if key != name}
        with pytest.raises(ValueError, match="missing required entries"):
            ModelRunConditions.from_mapping(incomplete)


def test_self_review_settings_must_agree_with_each_other():
    turned_on_with_no_attempts = check_model_run_conditions(
        {
            ENVIRONMENT_HOST_PYTHON_PROCESS: _conditions(
                self_review_enabled=True, self_review_max_attempts=0
            )
        },
        comparison=COMPARISON_TOOL_BUILT_IN_FEATURES,
    )
    assert any("zero attempts" in problem for problem in turned_on_with_no_attempts)

    turned_off_with_attempts = check_model_run_conditions(
        {
            ENVIRONMENT_HOST_PYTHON_PROCESS: _conditions(
                self_review_enabled=False, self_review_max_attempts=2
            )
        }
    )
    assert any("still allows" in problem for problem in turned_off_with_attempts)


def test_an_empty_task_list_is_refused():
    problems = check_model_run_conditions(
        {ENVIRONMENT_HOST_PYTHON_PROCESS: _conditions(task_ids=())}
    )
    assert any("empty fixed task list" in problem for problem in problems)


@pytest.mark.parametrize(
    "field,message",
    [
        ("max_output_tokens", "how much text"),
        ("per_task_timeout_seconds", "how long"),
    ],
)
def test_missing_limits_are_refused(field, message):
    problems = check_model_run_conditions(
        {ENVIRONMENT_HOST_PYTHON_PROCESS: _conditions(**{field: 0})}
    )
    assert any(message in problem for problem in problems)


def test_a_run_place_outside_the_comparison_is_reported():
    problems = check_model_run_conditions({"some_other_place": _conditions()})
    assert any("not part of the comparison" in problem for problem in problems)


def test_no_conditions_at_all_is_reported():
    assert check_model_run_conditions({}) == [
        "no run place was given fixed model run conditions"
    ]


# ── The 5, 30, and 220 task stages ─────────────────────────────────────────


def _stage(count: int) -> dict:
    return {
        "task_ids": [f"task-{index}" for index in range(count)],
        "task_selection_method": "fixed list recorded before the run",
        "success_criteria": "every task produces the required files",
        "stop_conditions": "stop if any run place changes model",
        "advance_conditions": "all run places finish without a blocked task",
        "maximum_expected_cost": "USD 20",
        "allowed_retry_reasons": [RETRY_INFRASTRUCTURE_ERROR],
        "allowed_self_review_attempts": 0,
    }


def _full_plan() -> dict:
    return {stage: _stage(count) for stage, count in RUN_SIZE_TASK_COUNTS.items()}


def test_the_three_stages_are_five_thirty_and_two_hundred_twenty():
    assert RUN_SIZE_TASK_COUNTS == {
        "advance_check": 5,
        "trial_run": 30,
        "full_run": 220,
    }


def test_a_complete_stage_plan_passes():
    assert check_run_size_plan(_full_plan()) == []


def test_a_missing_stage_is_reported():
    plan = _full_plan()
    del plan["trial_run"]
    problems = check_run_size_plan(plan)
    assert any("trial_run stage has no plan" in problem for problem in problems)


def test_a_stage_with_the_wrong_task_count_is_reported():
    plan = _full_plan()
    plan["advance_check"] = _stage(4)
    problems = check_run_size_plan(plan)
    assert any("fixes 4 tasks but must fix 5" in problem for problem in problems)


def test_a_stage_that_repeats_a_task_is_reported():
    plan = _full_plan()
    plan["advance_check"]["task_ids"] = ["task-1"] * 5
    problems = check_run_size_plan(plan)
    assert any("repeats a task" in problem for problem in problems)


@pytest.mark.parametrize(
    "field",
    [
        "task_ids",
        "task_selection_method",
        "success_criteria",
        "stop_conditions",
        "advance_conditions",
        "maximum_expected_cost",
        "allowed_retry_reasons",
        "allowed_self_review_attempts",
    ],
)
def test_every_stage_field_must_be_fixed_before_the_run(field):
    plan = _full_plan()
    plan["full_run"][field] = None
    problems = check_run_size_plan(plan)
    assert any(
        problem.startswith("the full_run stage is missing") and field in problem
        for problem in problems
    )


def test_a_stage_may_not_allow_an_unknown_retry_reason():
    plan = _full_plan()
    plan["full_run"]["allowed_retry_reasons"] = ["anything_goes"]
    problems = check_run_size_plan(plan)
    assert any("does not count" in problem for problem in problems)


def test_turning_self_review_and_retries_off_is_a_real_answer():
    """The first comparison needs both switched off, which is 0 and [].

    Treating those as "missing" would make the document's own first comparison
    impossible to express.
    """
    plan = _full_plan()
    for stage in plan:
        plan[stage]["allowed_retry_reasons"] = []
        plan[stage]["allowed_self_review_attempts"] = 0
    assert check_run_size_plan(plan) == []


def test_a_stage_flagged_as_incomplete_is_still_counted():
    """A missing field must not stop the task-count check from running."""
    plan = _full_plan()
    plan["advance_check"]["success_criteria"] = None
    plan["advance_check"]["task_ids"] = ["task-1", "task-2"]
    problems = check_run_size_plan(plan)
    assert any("success_criteria" in problem for problem in problems)
    assert any("fixes 2 tasks but must fix 5" in problem for problem in problems)


def test_a_non_numeric_self_review_allowance_is_reported():
    plan = _full_plan()
    plan["trial_run"]["allowed_self_review_attempts"] = "a few"
    problems = check_run_size_plan(plan)
    assert any("whole number" in problem for problem in problems)


# ── What every finished run must write down ────────────────────────────────


def _run_record() -> dict:
    record = {name: "recorded" for name in REQUIRED_RUN_RECORD_FIELDS}
    record["retry_counts_by_reason"] = {reason: 0 for reason in RETRY_REASONS}
    return record


def test_a_complete_run_record_passes():
    assert check_run_record_fields(_run_record()) == []


def test_the_run_record_covers_every_required_item():
    assert len(REQUIRED_RUN_RECORD_FIELDS) == len(set(REQUIRED_RUN_RECORD_FIELDS))
    for name in (
        "model_and_deployment",
        "system_instruction",
        "task_instruction",
        "task_ids",
        "input_file_versions",
        "executed_code_version",
        "started_at",
        "finished_at",
        "total_seconds",
        "model_call_count",
        "tool_run_count",
        "retry_counts_by_reason",
        "produced_files",
        "produced_file_check_results",
        "task_completed",
        "external_grade",
        "model_cost",
        "isolation_and_security",
        "failure_stage_and_reason",
    ):
        assert name in REQUIRED_RUN_RECORD_FIELDS


@pytest.mark.parametrize("field", REQUIRED_RUN_RECORD_FIELDS)
def test_a_missing_run_record_item_is_reported(field):
    record = _run_record()
    del record[field]
    problems = check_run_record_fields(record)
    assert any(field in problem for problem in problems)


@pytest.mark.parametrize(
    "reason",
    [
        RETRY_INFRASTRUCTURE_ERROR,
        RETRY_MODEL_SELF_REVIEW,
        RETRY_TOOL_LOOP_INTERNAL_RECOVERY,
    ],
)
def test_each_retry_reason_must_be_counted_separately(reason):
    record = _run_record()
    del record["retry_counts_by_reason"][reason]
    problems = check_run_record_fields(record)
    assert any(reason in problem for problem in problems)


def test_a_single_lumped_retry_count_is_refused():
    record = _run_record()
    record["retry_counts_by_reason"] = 7
    problems = check_run_record_fields(record)
    assert any("three reasons" in problem for problem in problems)


# ── The two comparisons must never share one score ─────────────────────────


def _scoreboards() -> dict:
    return {
        COMPARISON_SAME_GENERATED_CODE: {
            "comparison": COMPARISON_SAME_GENERATED_CODE,
            "results": [],
        },
        COMPARISON_TOOL_BUILT_IN_FEATURES: {
            "comparison": COMPARISON_TOOL_BUILT_IN_FEATURES,
            "results": [],
        },
    }


def test_two_separate_scoreboards_pass():
    assert check_comparisons_are_scored_apart(_scoreboards()) == []


def test_a_single_shared_scoreboard_is_refused():
    boards = _scoreboards()
    del boards[COMPARISON_TOOL_BUILT_IN_FEATURES]
    problems = check_comparisons_are_scored_apart(boards)
    assert any(
        COMPARISON_TOOL_BUILT_IN_FEATURES in problem for problem in problems
    )


def test_a_mislabelled_scoreboard_is_refused():
    boards = _scoreboards()
    boards[COMPARISON_SAME_GENERATED_CODE]["comparison"] = (
        COMPARISON_TOOL_BUILT_IN_FEATURES
    )
    problems = check_comparisons_are_scored_apart(boards)
    assert any("added together by mistake" in problem for problem in problems)


def test_an_unknown_scoreboard_is_refused():
    boards = _scoreboards()
    boards["combined_total"] = {"comparison": "combined_total"}
    problems = check_comparisons_are_scored_apart(boards)
    assert any("belong to no known comparison" in problem for problem in problems)


# ── The whole report ───────────────────────────────────────────────────────


def test_a_report_with_a_problem_is_not_ready():
    report = build_readiness_report(
        environ=APPROVED,
        conditions_by_environment={
            ENVIRONMENT_HOST_PYTHON_PROCESS: _conditions(),
            ENVIRONMENT_DOCKER_CONTAINER: _conditions(deployment="other"),
        },
        **_ready_container_arguments(),
    )
    assert report.ready is False
    assert report.problems


def test_a_report_with_no_problem_is_ready():
    report = build_readiness_report(
        environ=APPROVED,
        conditions_by_environment={
            ENVIRONMENT_HOST_PYTHON_PROCESS: _conditions(),
            ENVIRONMENT_DOCKER_CONTAINER: _conditions(),
        },
        run_size_plan=_full_plan(),
        scoreboards=_scoreboards(),
        **_ready_container_arguments(),
    )
    assert report.problems == []
    assert report.blocked_environments == []
    assert report.ready is True


def test_an_unapproved_report_is_never_ready():
    report = build_readiness_report(
        environ={},
        conditions_by_environment={
            ENVIRONMENT_HOST_PYTHON_PROCESS: _conditions(),
            ENVIRONMENT_DOCKER_CONTAINER: _conditions(),
        },
        **_ready_container_arguments(),
    )
    assert report.problems == []
    assert report.ready is False, (
        "a report with no approval must not be green; a check wired to this "
        "would let an unapproved paid run start"
    )
    assert set(report.blocked_environments) == {
        ENVIRONMENT_HOST_PYTHON_PROCESS,
        ENVIRONMENT_DOCKER_CONTAINER,
    }


def test_comparing_all_five_places_is_not_ready_today():
    report = build_readiness_report(
        environ=APPROVED, **_ready_container_arguments()
    )
    assert report.compared_environments == ENVIRONMENTS
    assert report.ready is False
    assert ENVIRONMENT_CODEX_BUILT_IN_AGENT in report.blocked_environments
    assert ENVIRONMENT_AGENTIC_SANDBOX_V2 in report.blocked_environments


def test_a_blocked_place_outside_the_comparison_does_not_block_the_report():
    report = build_readiness_report(
        environ=APPROVED,
        conditions_by_environment={
            ENVIRONMENT_HOST_PYTHON_PROCESS: _conditions(),
        },
        **_ready_container_arguments(),
    )
    assert report.compared_environments == (ENVIRONMENT_HOST_PYTHON_PROCESS,)
    assert report.ready is True
    assert (
        report.status_of(ENVIRONMENT_CODEX_BUILT_IN_AGENT)
        == STATUS_NOT_IMPLEMENTED_HERE
    )


def test_a_place_in_the_comparison_that_cannot_run_blocks_the_report():
    report = build_readiness_report(
        environ=APPROVED,
        conditions_by_environment={
            ENVIRONMENT_HOST_PYTHON_PROCESS: _conditions(),
            ENVIRONMENT_AGENTIC_SANDBOX_V2: _conditions(),
        },
        **_ready_container_arguments(),
    )
    assert report.ready is False
    assert report.blocked_environments == [ENVIRONMENT_AGENTIC_SANDBOX_V2]


def test_the_report_can_be_written_out_as_plain_data():
    report = build_readiness_report(environ={}, **_ready_container_arguments())
    payload = json.loads(json.dumps(report.as_dict(), ensure_ascii=False))
    assert payload["paid_model_calls_approved"] is False
    assert payload["ready"] is False
    assert len(payload["environments"]) == 8
    assert payload["blocked_environments"]


def test_asking_about_an_unknown_run_place_raises():
    report = build_readiness_report(environ={})
    with pytest.raises(KeyError):
        report.status_of("somewhere_else")


# ── The command-line tool ──────────────────────────────────────────────────


def test_the_command_line_tool_runs_without_calling_a_model():
    finished = subprocess.run(
        [
            sys.executable,
            "scripts/check_execution_environment_readiness.py",
            "--skip-docker-probe",
            "--json",
        ],
        cwd=BATCH_RUNNER_ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert finished.returncode == 1, (
        "with no paid-run approval the tool must not exit 0, or a check wired "
        f"to it would green-light an unapproved run: {finished.stderr}"
    )
    payload = json.loads(finished.stdout)
    assert payload["paid_model_calls_approved"] is False
    assert payload["ready"] is False
    graded = {entry["environment"]: entry["status"] for entry in payload["environments"]}
    assert graded[ENVIRONMENT_CODEX_BUILT_IN_AGENT] == STATUS_NOT_IMPLEMENTED_HERE
    assert graded[ENVIRONMENT_AGENTIC_SANDBOX_V2] == STATUS_STRUCTURE_CHECK_ONLY


def test_the_command_line_tool_reports_a_broken_plan(tmp_path: Path):
    plan = tmp_path / "plan.yaml"
    plan.write_text(
        "model_run_conditions:\n"
        "  shared:\n"
        "    provider: azure\n"
        "    resource: fixed-foundry-resource\n"
        "    deployment: fixed-deployment\n"
        "    resolved_model: fixed-model\n"
        "    api_version: '2025-04-01-preview'\n"
        "    model_serving_path: microsoft_foundry_deployment\n"
        "    system_instruction: s\n"
        "    task_instruction: t\n"
        "    task_ids: [task-1]\n"
        "    input_file_versions: {}\n"
        "    max_output_tokens: 1024\n"
        "    per_task_timeout_seconds: 570\n"
        "    self_review_enabled: false\n"
        "    self_review_max_attempts: 0\n"
        "    retry_reasons_allowed: [infrastructure_error]\n"
        "    retry_max_attempts: 3\n"
        "    automatic_model_switch_allowed: false\n"
        "    automatic_fallback_allowed: false\n"
        "    unsupported_runner_substitution_allowed: false\n"
        "  by_environment:\n"
        "    host_python_process: {}\n"
        "    docker_container:\n"
        "      deployment: a-different-deployment\n",
        encoding="utf-8",
    )
    finished = subprocess.run(
        [
            sys.executable,
            "scripts/check_execution_environment_readiness.py",
            "--skip-docker-probe",
            "--plan",
            str(plan),
            "--json",
        ],
        cwd=BATCH_RUNNER_ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert finished.returncode == 1
    payload = json.loads(finished.stdout)
    assert any(
        "do not share one fixed set" in problem for problem in payload["problems"]
    )


def test_the_command_line_tool_reports_a_plan_naming_no_run_place(tmp_path: Path):
    """A plan that fixes conditions for nobody must not pass silently."""
    plan = tmp_path / "plan.yaml"
    plan.write_text(
        "model_run_conditions:\n"
        "  shared: {}\n"
        "  by_environment: {}\n",
        encoding="utf-8",
    )
    finished = subprocess.run(
        [
            sys.executable,
            "scripts/check_execution_environment_readiness.py",
            "--skip-docker-probe",
            "--plan",
            str(plan),
            "--json",
        ],
        cwd=BATCH_RUNNER_ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert finished.returncode == 1
    payload = json.loads(finished.stdout)
    assert any(
        "no run place was given" in problem for problem in payload["problems"]
    )
