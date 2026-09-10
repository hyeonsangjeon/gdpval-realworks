"""Tests for the three whole-product run places added to the comparison.

Two of them drive the work with their own program but ask the same named
deployment in the same Microsoft Foundry resource every other place asks, so
what changes is the program and nothing else. The third asks a model GitHub
picks, which is not a difference in run place at all.

Two of the three still have no code behind them at all. The Codex place now
does — see ``core.codex_runner`` and ``tests/test_codex_runtime_end_to_end.py``
— but having code is not the same as having reached the deployment, and these
tests keep that distinction from collapsing. For all three, the reasons stay
written down, stay checkable against the code they cite, and cannot be quietly
turned into "it works" by a plan that says so.

Nothing here calls a model, contacts a provider, or spends money.
"""

from __future__ import annotations

import pytest

from core.azure_ai_clients import (
    FORBIDDEN_STATIC_AZURE_CREDENTIAL_ENV,
    classify_endpoint,
)
from core.execution_environment_readiness import (
    COMPARISON_NATIVE_PRODUCT_BUNDLE,
    COMPARISON_SAME_GENERATED_CODE,
    COMPARISON_TOOL_BUILT_IN_FEATURES,
    COMPARISONS,
    DOCUMENTED_BLOCKERS_BY_ENVIRONMENT,
    ENVIRONMENT_AZURE_CODE_INTERPRETER,
    ENVIRONMENT_CODEX_COMMAND_LINE_TOOL_FOUNDRY,
    ENVIRONMENT_COPILOT_COMMAND_LINE_TOOL_FOUNDRY,
    ENVIRONMENT_COPILOT_COMMAND_LINE_TOOL_GITHUB_SERVED,
    ENVIRONMENT_DOCKER_CONTAINER,
    ENVIRONMENT_HOST_PYTHON_PROCESS,
    ENVIRONMENTS,
    EXECUTION_MODE_BY_ENVIRONMENT,
    MODEL_SERVING_PATHS,
    PRODUCT_CHOOSES_THE_MODEL,
    REQUIRED_SCOREBOARDS,
    RETRY_INFRASTRUCTURE_ERROR,
    RUNNER_CLASS_BY_ENVIRONMENT,
    SAME_MODEL_COMPARISONS,
    SERVING_PATH_FIXED_BY_ENVIRONMENT,
    SERVING_PATH_GITHUB_SERVED_COPILOT,
    SERVING_PATH_MICROSOFT_FOUNDRY_DEPLOYMENT,
    STATUS_CAN_RUN_REAL_EXPERIMENT,
    STATUS_NOT_IMPLEMENTED_HERE,
    STATUS_STRUCTURE_CHECK_ONLY,
    ModelRunConditions,
    build_readiness_report,
    check_comparisons_are_scored_apart,
    check_model_run_conditions,
    describe_environment,
    inspect_environment_support,
)

THE_THREE = (
    ENVIRONMENT_CODEX_COMMAND_LINE_TOOL_FOUNDRY,
    ENVIRONMENT_COPILOT_COMMAND_LINE_TOOL_FOUNDRY,
    ENVIRONMENT_COPILOT_COMMAND_LINE_TOOL_GITHUB_SERVED,
)

#: The two of the three that still have no code behind them. Kept as its own
#: list rather than expressed as "the three minus Codex", so that implementing
#: one of the Copilot places is a deliberate edit here and not a test that
#: silently stops covering it.
STILL_UNIMPLEMENTED = (
    ENVIRONMENT_COPILOT_COMMAND_LINE_TOOL_FOUNDRY,
    ENVIRONMENT_COPILOT_COMMAND_LINE_TOOL_GITHUB_SERVED,
)

# The address GitHub's own-key documentation gives for an Azure provider.
COPILOT_DOCUMENTED_AZURE_ADDRESS = (
    "https://hjeon-fdpo-foundry-eus2.openai.azure.com/openai/deployments/gpt-5.4"
)


def _conditions(**overrides) -> ModelRunConditions:
    base = {
        "provider": "azure",
        "resource": "hjeon-fdpo-foundry-eus2",
        "deployment": "gpt-5.4",
        "resolved_model": "gpt-5.4",
        "api_version": "2025-04-01-preview",
        "model_serving_path": SERVING_PATH_MICROSOFT_FOUNDRY_DEPLOYMENT,
        "system_instruction": "You complete professional tasks.",
        "task_instruction": "Produce the requested deliverable files.",
        "task_ids": ("task-1",),
        "input_file_versions": {},
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


def _entry(environment: str):
    return next(
        entry
        for entry in inspect_environment_support()
        if entry.environment == environment
    )


# ── The three places exist, and none of them can run anything here ─────────


@pytest.mark.parametrize("environment", THE_THREE)
def test_the_new_place_is_part_of_the_comparison(environment):
    assert environment in ENVIRONMENTS
    assert len(describe_environment(environment).split()) >= 8


@pytest.mark.parametrize("environment", STILL_UNIMPLEMENTED)
def test_the_new_place_has_no_way_to_run_a_task_here(environment):
    """Graded from the absence of code, not from an opinion written down."""
    assert EXECUTION_MODE_BY_ENVIRONMENT[environment] is None
    assert RUNNER_CLASS_BY_ENVIRONMENT[environment] is None
    assert _entry(environment).status == STATUS_NOT_IMPLEMENTED_HERE


def test_the_codex_place_has_code_but_is_still_not_a_place_that_can_run():
    """Reachability is not runnability, and the grade must say so.

    This test used to rest on "none of that is a request a Foundry deployment
    answered". Run 34461522053 was answered, so that reason is retired and the
    grade has to survive without it. It does: what the place still lacks is an
    experiment that asks for it, a way for the settings to reach the executor,
    and a single deliverable produced through it. A model saying one word back
    is not a task being done, and the grade must not read as if it were.
    """
    environment = ENVIRONMENT_CODEX_COMMAND_LINE_TOOL_FOUNDRY
    assert EXECUTION_MODE_BY_ENVIRONMENT[environment] == "codex_foundry"
    assert RUNNER_CLASS_BY_ENVIRONMENT[environment] == (
        "core.codex_runner",
        "CodexAgentRunner",
    )

    entry = _entry(environment)
    assert entry.status == STATUS_STRUCTURE_CHECK_ONLY
    assert entry.status != STATUS_CAN_RUN_REAL_EXPERIMENT
    # The evidence names the code it is claiming about, so a reader can check
    # the claim instead of taking it.
    assert any("core.codex_runner" in line for line in entry.evidence)
    assert any(
        "tests/test_codex_runtime_end_to_end.py" in line
        for line in entry.evidence
    )
    # The answered turn is named by its run id for the same reason: it is the
    # one claim here that cannot be checked by reading this repository, so it
    # has to point at the record that can be downloaded and read instead.
    assert any("34461522053" in line for line in entry.evidence)
    # And the reasons it still cannot run are all still reported.
    for reason in DOCUMENTED_BLOCKERS_BY_ENVIRONMENT[environment]:
        assert reason in entry.blockers


def test_the_codex_blockers_are_about_the_task_not_about_the_connection():
    """The reasons must move on once the thing they named has happened.

    Three times now this list has kept a reason past its expiry: first
    documentation objections the product had already answered, then connection
    questions run 34461522053 answered, then wiring that has since been built.
    Every time the effect was the same — a solved problem reading as
    unsolvable. This pins the shape of the list rather than its wording:
    nothing may claim the connection is unproven or the wiring absent, and each
    reason must name the code that would have to change for it to clear.
    """
    reasons = DOCUMENTED_BLOCKERS_BY_ENVIRONMENT[
        ENVIRONMENT_CODEX_COMMAND_LINE_TOOL_FOUNDRY
    ]
    retired = (
        "has not been observed",
        "has not been shown to be compatible",
        "a turn on a runner has not yet been answered",
        # Cleared by the change that added exp033 and wired step 2. Kept here
        # so that neither can come back as a reason after being built.
        "no experiment asks for this place",
        "the configuration cannot reach the runner",
        # Cleared by the change that added the codex_foundry_confirmed
        # dispatch input. The gate is still shut by default and a person still
        # opens it, which is why a blocker still describes it -- but "there is
        # no way to open it" is a different claim and it is no longer true.
        "batch-run.yml does not set it",
    )
    for reason in reasons:
        for phrase in retired:
            assert phrase not in reason, (
                f"a blocker still says {phrase!r}, which has since been "
                "settled"
            )
    named = ("step2_run_inference", "batch-run.yml", "test_codex_runtime")
    for module in named:
        assert any(module in reason for reason in reasons), (
            f"no blocker names {module}, so a reader cannot check any of them"
        )


def test_a_batch_run_still_refuses_to_start_the_codex_mode():
    """The grade above is advice; this is the block that actually stops a run.

    Run rather than read: the guard is called, and it raises. The gate is an
    explicit setting so that opening it is somebody deciding the connection is
    confirmed, rather than this repository concluding it from its own code.
    """
    import step2_run_inference

    with pytest.raises(ValueError) as refused:
        step2_run_inference._require_runnable_execution_mode("codex_foundry")
    assert "CODEX_FOUNDRY_CONNECTION_CONFIRMED" in str(refused.value)


@pytest.mark.parametrize("environment", THE_THREE)
def test_the_new_place_reports_its_documented_reasons(environment):
    """The published reasons must reach the report, not sit in a constant."""
    blockers = _entry(environment).blockers
    for reason in DOCUMENTED_BLOCKERS_BY_ENVIRONMENT[environment]:
        assert reason in blockers


def test_each_of_the_three_has_more_than_one_reason_where_that_is_true():
    """One cleared blocker must not read as a cleared place.

    The GitHub-served place fails for three separate reasons, the own-key place
    and the Codex program for two each. Recording only the first would let
    somebody solve one and believe the way was open.

    Codex was three until the wiring was built. Two of those three named code
    that now exists — an experiment file that asks for the mode, and a step 2
    that reaches the runner — so they are gone rather than reworded, and the
    count moves with them. What is left is a decision a person must make and a
    thing that has never happened; inventing a third to hold the number would
    be padding a list whose whole purpose is to be true.
    """
    counted = {
        environment: len(DOCUMENTED_BLOCKERS_BY_ENVIRONMENT[environment])
        for environment in THE_THREE
    }
    assert counted == {
        ENVIRONMENT_CODEX_COMMAND_LINE_TOOL_FOUNDRY: 2,
        ENVIRONMENT_COPILOT_COMMAND_LINE_TOOL_FOUNDRY: 2,
        ENVIRONMENT_COPILOT_COMMAND_LINE_TOOL_GITHUB_SERVED: 3,
    }
    for environment, count in counted.items():
        assert count > 1, environment


# ── The written reasons are checked against the code they name ─────────────


def test_the_static_key_conflict_the_blockers_cite_is_real():
    """Copilot own-key hands a provider a static key. This repository refuses.

    Checked against the list itself rather than against a copy of it, so a
    later decision to allow one of these names would fail here rather than
    leave the blocker text quietly wrong.

    Codex used to be checked here too, and no longer is. The rule still binds
    it — no static Azure key is allowed for any place — but for Codex the
    conflict was *resolved* rather than merely stated: core.codex_azure_token
    mints an Entra token instead, and run 34461522053 was answered using it.
    Requiring the blocker list to keep citing a conflict that has been settled
    would force a solved problem to be written down as an obstacle forever.
    """
    assert FORBIDDEN_STATIC_AZURE_CREDENTIAL_ENV
    assert "AZURE_OPENAI_API_KEY" in FORBIDDEN_STATIC_AZURE_CREDENTIAL_ENV
    assert any(
        "FORBIDDEN_STATIC_AZURE_CREDENTIAL_ENV" in reason
        for reason in DOCUMENTED_BLOCKERS_BY_ENVIRONMENT[
            ENVIRONMENT_COPILOT_COMMAND_LINE_TOOL_FOUNDRY
        ]
    )


def test_the_address_the_copilot_documentation_gives_is_really_refused():
    """The second own-key blocker, proved by calling the function it names."""
    with pytest.raises(ValueError):
        classify_endpoint(COPILOT_DOCUMENTED_AZURE_ADDRESS)


def test_an_address_this_repository_does_accept_still_works():
    """So the test above is a statement about that shape, not about the call."""
    accepted = classify_endpoint(
        "https://hjeon-fdpo-foundry-eus2.openai.azure.com/openai/v1/"
    )
    assert accepted.account == "hjeon-fdpo-foundry-eus2"


# ── Where the answer comes from ────────────────────────────────────────────


def test_every_run_place_says_where_its_model_could_come_from():
    assert set(SERVING_PATH_FIXED_BY_ENVIRONMENT) == set(ENVIRONMENTS)
    for fixed in SERVING_PATH_FIXED_BY_ENVIRONMENT.values():
        assert fixed is None or fixed in MODEL_SERVING_PATHS


def test_only_the_github_served_place_lets_a_product_choose():
    assert PRODUCT_CHOOSES_THE_MODEL == (
        ENVIRONMENT_COPILOT_COMMAND_LINE_TOOL_GITHUB_SERVED,
    )


def test_the_product_chooses_list_is_read_from_the_table_not_written_twice():
    """A place added to the table must appear here without a second edit.

    This is the shape that has gone wrong before: a hand-written second copy
    of something already recorded, which agrees today and diverges later.
    """
    assert PRODUCT_CHOOSES_THE_MODEL == tuple(
        environment
        for environment, path in SERVING_PATH_FIXED_BY_ENVIRONMENT.items()
        if path is not None
        and path != SERVING_PATH_MICROSOFT_FOUNDRY_DEPLOYMENT
    )


def test_the_two_foundry_products_ask_the_same_place_the_azure_run_place_asks():
    """That is what makes them a comparison of programs rather than of models."""
    for environment in (
        ENVIRONMENT_CODEX_COMMAND_LINE_TOOL_FOUNDRY,
        ENVIRONMENT_COPILOT_COMMAND_LINE_TOOL_FOUNDRY,
    ):
        assert SERVING_PATH_FIXED_BY_ENVIRONMENT[environment] == (
            SERVING_PATH_FIXED_BY_ENVIRONMENT[ENVIRONMENT_AZURE_CODE_INTERPRETER]
        )


def test_a_serving_path_nobody_defined_is_refused():
    problems = check_model_run_conditions(
        {
            ENVIRONMENT_HOST_PYTHON_PROCESS: _conditions(
                model_serving_path="wherever_it_ends_up"
            )
        }
    )
    assert any("is not one of the ways" in problem for problem in problems)


def test_a_plan_cannot_rename_where_a_product_gets_its_model():
    problems = check_model_run_conditions(
        {
            ENVIRONMENT_COPILOT_COMMAND_LINE_TOOL_GITHUB_SERVED: _conditions(
                model_serving_path=SERVING_PATH_MICROSOFT_FOUNDRY_DEPLOYMENT
            ),
            ENVIRONMENT_HOST_PYTHON_PROCESS: _conditions(),
        },
        comparison=COMPARISON_NATIVE_PRODUCT_BUNDLE,
    )
    assert any(
        "cannot change where a product gets its model" in problem
        for problem in problems
    )


@pytest.mark.parametrize("comparison", SAME_MODEL_COMPARISONS)
def test_a_product_that_picks_its_own_model_cannot_join_a_same_model_score(
    comparison,
):
    problems = check_model_run_conditions(
        {
            ENVIRONMENT_COPILOT_COMMAND_LINE_TOOL_GITHUB_SERVED: _conditions(
                model_serving_path=SERVING_PATH_GITHUB_SERVED_COPILOT
            )
        },
        comparison=comparison,
    )
    assert any(
        COMPARISON_NATIVE_PRODUCT_BUNDLE in problem for problem in problems
    )


def test_that_same_product_is_welcome_in_the_whole_product_comparison():
    assert check_model_run_conditions(
        {
            ENVIRONMENT_COPILOT_COMMAND_LINE_TOOL_GITHUB_SERVED: _conditions(
                model_serving_path=SERVING_PATH_GITHUB_SERVED_COPILOT
            ),
            ENVIRONMENT_CODEX_COMMAND_LINE_TOOL_FOUNDRY: _conditions(),
        },
        comparison=COMPARISON_NATIVE_PRODUCT_BUNDLE,
    ) == []


def test_one_product_on_its_own_is_not_a_comparison():
    problems = check_model_run_conditions(
        {ENVIRONMENT_CODEX_COMMAND_LINE_TOOL_FOUNDRY: _conditions()},
        comparison=COMPARISON_NATIVE_PRODUCT_BUNDLE,
    )
    assert any("needs at least two" in problem for problem in problems)


# ── The three things a run place is never allowed to decide for itself ─────


@pytest.mark.parametrize("comparison", COMPARISONS)
@pytest.mark.parametrize(
    "field,expected",
    [
        (
            "automatic_model_switch_allowed",
            "switching to another model",
        ),
        (
            "automatic_fallback_allowed",
            "carrying on with a substitute",
        ),
        (
            "unsupported_runner_substitution_allowed",
            "run somewhere other than",
        ),
    ],
)
def test_each_prohibition_is_refused_in_every_comparison(
    comparison, field, expected
):
    """Three different things go wrong, so they are three different answers.

    Switching model changes what answered. Falling back changes what ran.
    Substituting a runner changes where it ran. A plan that says "no" to one
    has said nothing about the other two.
    """
    problems = check_model_run_conditions(
        {
            ENVIRONMENT_HOST_PYTHON_PROCESS: _conditions(**{field: True}),
            ENVIRONMENT_DOCKER_CONTAINER: _conditions(**{field: True}),
        },
        comparison=comparison,
    )
    assert any(expected in problem for problem in problems)


@pytest.mark.parametrize(
    "field",
    [
        "resource",
        "model_serving_path",
        "automatic_fallback_allowed",
        "unsupported_runner_substitution_allowed",
    ],
)
def test_a_plan_that_stays_silent_about_a_new_field_is_refused(field):
    """Silence is not consent. A default here would be a permission nobody gave."""
    complete = {
        name: getattr(_conditions(), name)
        for name in ModelRunConditions.field_names()
    }
    complete.pop(field)
    with pytest.raises(ValueError, match="missing required entries"):
        ModelRunConditions.from_mapping(complete)


# ── The whole-product score is kept away from the other two ────────────────


def test_the_whole_product_board_is_allowed_to_be_absent():
    """An operator may decide that comparison is not worth its money."""
    assert COMPARISON_NATIVE_PRODUCT_BUNDLE not in REQUIRED_SCOREBOARDS
    assert check_comparisons_are_scored_apart(
        {
            name: {"comparison": name, "results": []}
            for name in REQUIRED_SCOREBOARDS
        }
    ) == []


def test_the_whole_product_board_is_allowed_to_be_present():
    assert check_comparisons_are_scored_apart(
        {name: {"comparison": name, "results": []} for name in COMPARISONS}
    ) == []


def test_a_whole_product_board_labelled_as_something_else_is_refused():
    boards = {name: {"comparison": name, "results": []} for name in COMPARISONS}
    boards[COMPARISON_NATIVE_PRODUCT_BUNDLE] = {
        "comparison": COMPARISON_TOOL_BUILT_IN_FEATURES,
        "results": [],
    }
    problems = check_comparisons_are_scored_apart(boards)
    assert any("added together by mistake" in problem for problem in problems)


def test_a_same_model_board_that_counts_a_product_chosen_model_is_refused():
    boards = {name: {"comparison": name, "results": []} for name in COMPARISONS}
    boards[COMPARISON_SAME_GENERATED_CODE] = {
        "comparison": COMPARISON_SAME_GENERATED_CODE,
        "environments": [
            ENVIRONMENT_HOST_PYTHON_PROCESS,
            ENVIRONMENT_COPILOT_COMMAND_LINE_TOOL_GITHUB_SERVED,
        ],
    }
    problems = check_comparisons_are_scored_apart(boards)
    assert any(
        ENVIRONMENT_COPILOT_COMMAND_LINE_TOOL_GITHUB_SERVED in problem
        for problem in problems
    )


def test_the_whole_product_board_may_list_that_same_place():
    boards = {name: {"comparison": name, "results": []} for name in COMPARISONS}
    boards[COMPARISON_NATIVE_PRODUCT_BUNDLE] = {
        "comparison": COMPARISON_NATIVE_PRODUCT_BUNDLE,
        "environments": [
            ENVIRONMENT_CODEX_COMMAND_LINE_TOOL_FOUNDRY,
            ENVIRONMENT_COPILOT_COMMAND_LINE_TOOL_GITHUB_SERVED,
        ],
    }
    assert check_comparisons_are_scored_apart(boards) == []


# ── A plan cannot name a place this repository cannot run ──────────────────


@pytest.mark.parametrize("environment", STILL_UNIMPLEMENTED)
def test_a_plan_naming_a_place_with_no_code_behind_it_is_refused(environment):
    """Otherwise a place that does exist would stand in for one that does not,
    and the score would be filed under the name of the place that never ran."""
    report = build_readiness_report(
        environ={},
        conditions_by_environment={
            ENVIRONMENT_HOST_PYTHON_PROCESS: _conditions(),
            environment: _conditions(
                model_serving_path=SERVING_PATH_FIXED_BY_ENVIRONMENT[environment]
            ),
        },
        comparison=COMPARISON_NATIVE_PRODUCT_BUNDLE,
        docker_daemon_available=True,
        docker_image_available=True,
        docker_run_setting="always",
        azure_route_profile="project-ci",
    )
    assert report.ready is False
    assert any(
        environment in problem and "must stop rather than let" in problem
        for problem in report.problems
    )


@pytest.mark.parametrize("environment", STILL_UNIMPLEMENTED)
def test_the_refusal_repeats_what_is_missing_rather_than_just_saying_no(
    environment,
):
    report = build_readiness_report(
        environ={},
        conditions_by_environment={
            ENVIRONMENT_HOST_PYTHON_PROCESS: _conditions(),
            environment: _conditions(
                model_serving_path=SERVING_PATH_FIXED_BY_ENVIRONMENT[environment]
            ),
        },
        comparison=COMPARISON_NATIVE_PRODUCT_BUNDLE,
        docker_daemon_available=True,
        docker_image_available=True,
        docker_run_setting="always",
        azure_route_profile="project-ci",
    )
    refusal = next(
        problem
        for problem in report.problems
        if environment in problem and "must stop rather than let" in problem
    )
    for reason in DOCUMENTED_BLOCKERS_BY_ENVIRONMENT[environment]:
        assert reason in refusal


def test_a_plan_naming_the_codex_place_does_not_make_it_ready():
    """The refusal above is about missing code, which Codex no longer has.

    What must not change is the answer to "may this run": the report still
    grades the place structure-only and still carries every reason it cannot
    reach its deployment, so a plan naming it cannot be read as a green light.
    """
    environment = ENVIRONMENT_CODEX_COMMAND_LINE_TOOL_FOUNDRY
    report = build_readiness_report(
        environ={},
        conditions_by_environment={
            ENVIRONMENT_HOST_PYTHON_PROCESS: _conditions(),
            environment: _conditions(
                model_serving_path=SERVING_PATH_FIXED_BY_ENVIRONMENT[environment]
            ),
        },
        comparison=COMPARISON_NATIVE_PRODUCT_BUNDLE,
        docker_daemon_available=True,
        docker_image_available=True,
        docker_run_setting="always",
        azure_route_profile="project-ci",
    )
    graded = next(
        entry
        for entry in report.environments
        if entry.environment == environment
    )
    assert graded.status == STATUS_STRUCTURE_CHECK_ONLY
    for reason in DOCUMENTED_BLOCKERS_BY_ENVIRONMENT[environment]:
        assert reason in graded.blockers
