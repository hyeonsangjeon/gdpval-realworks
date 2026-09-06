"""The one thing this comparison holds still is measured, not read back.

``same_generated_code_rerun`` reports its result as a difference the run place
made. That reading is only available if the run place is the only thing that
differs. Until now the check of that claim was
``check_model_run_conditions``, which compares each place's
``system_instruction`` and ``task_instruction``. Two things were wrong with it,
and either one on its own would have been enough:

* Both values are written **once**, under ``model_run_conditions.shared``, and
  every place inherits them. So the comparison held three copies of one string
  against each other. There is no edit to the plan that could make it fail.
* The plan says in its own words that the first of the two is never sent.
  ``core/prompt_loader.render_prompt`` lets a committed prompt file's own
  ``system_message`` win whenever it has one, and all three committed files have
  one. So the wording being compared was wording no model reads.

Meanwhile the wording every model does read — the committed prompt file, that
file's own standing instruction, the wrapping each run place's settings add, and
whatever the runner builds before any of it is rendered — was compared by
nothing at all. Measured through the same builders a real attempt uses, the
three come to 3,533, 3,867 and 7,307 characters, and they are three differently
**named** files. On 2026-09-01 the three places ran five tasks each and the
container's requests carried 350 to 400 more input tokens than the host
process's on every one of them; that is this gap seen from outside.

No test in this file types 3,533, 3,867 or 7,307. Every figure is rendered from
the committed files, so editing a prompt moves the tests with it.

Nothing here calls a model, starts a container, or spends anything.
"""

from __future__ import annotations

import copy
import sys
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core.execution_envelope_preflight import (  # noqa: E402
    _check_every_run_place_is_asked_the_same_thing,
    _measure_first_requests,
    _prompt_files_a_run_place_might_send,
    conditions_from_plan,
    load_plan,
    run_envelope_preflight,
)
from core.execution_envelope_tasks import (  # noqa: E402
    load_task_catalog,
    widest_occupation,
)
from core.execution_environment_readiness import (  # noqa: E402
    COMPARISON_NATIVE_PRODUCT_BUNDLE,
    COMPARISON_SAME_GENERATED_CODE,
    COMPARISON_TOOL_BUILT_IN_FEATURES,
    RUNNER_CLASS_BY_ENVIRONMENT,
    check_model_run_conditions,
)
from core.first_request_sections import first_request_section_budget  # noqa: E402
from core.prompt_loader import fixed_prompt_characters, load_prompt  # noqa: E402

PLAN_PATH = (
    BATCH_RUNNER_ROOT
    / "experiments"
    / "execution_envelope"
    / "advance_check_plan.yaml"
)
CATALOG = load_task_catalog()
WIDEST_OCCUPATION = widest_occupation(CATALOG)

THE_THREE_RUN_PLACES = (
    "host_python_process",
    "docker_container",
    "azure_code_interpreter",
)

#: A run place this repository has no runner for.
A_RUN_PLACE_NO_RUNNER_SERVES = "somewhere_nobody_wired_up"


@pytest.fixture
def plan():
    return load_plan(PLAN_PATH)


def _problems(plan, *, comparison=None, root=BATCH_RUNNER_ROOT, catalog=None):
    """Run the rule alone, the way ``run_envelope_preflight`` runs it."""
    return _check_every_run_place_is_asked_the_same_thing(
        conditions_from_plan(plan),
        comparison=(
            str(plan.get("comparison") or COMPARISON_SAME_GENERATED_CODE)
            if comparison is None
            else comparison
        ),
        plan=plan,
        root=root,
        catalog=CATALOG if catalog is None else catalog,
    )


def _measured(plan, *, root=BATCH_RUNNER_ROOT):
    return _measure_first_requests(
        conditions_from_plan(plan), plan=plan, root=root, catalog=CATALOG
    )


def _settings(environment):
    relative = load_plan(PLAN_PATH)["experiment_files"][environment]
    return yaml.safe_load((BATCH_RUNNER_ROOT / relative).read_text(encoding="utf-8"))


def _sent(environment):
    """What one run place's first request comes to, worked out a second way.

    Built here from the same production functions rather than read off the
    rule's own answer, so the two have to agree or one of them is wrong.
    """
    settings = _settings(environment)
    sandbox = (settings.get("execution") or {}).get("sandbox") or {}
    name = _prompt_files_a_run_place_might_send(environment, settings)[0]
    from core.execution_envelope_preflight import _runner_first_request_extra_sections

    declared = _runner_first_request_extra_sections(environment)
    assert declared is not None, environment
    rendered = sum(
        fixed_prompt_characters(
            load_prompt(name),
            experiment_prompt=(settings.get("condition_a") or {}).get("prompt"),
            occupation=WIDEST_OCCUPATION,
        ).values()
    )
    built = first_request_section_budget(
        declared,
        prompt_name=name,
        max_skills=sandbox.get("max_skills", 5),
        contract_config=sandbox.get("contract"),
    ).characters
    return rendered + built


# ── The check this replaces could not fail ────────────────────────────────────


def test_the_wording_the_old_check_compared_is_one_value_every_place_inherits(plan):
    """The regression, stated as a fact about the plan rather than as prose."""
    shared = plan["model_run_conditions"]["shared"]
    assert "system_instruction" in shared
    assert "task_instruction" in shared

    by_place = plan["model_run_conditions"].get("by_environment") or {}
    for environment, overrides in by_place.items():
        assert "system_instruction" not in (overrides or {}), environment
        assert "task_instruction" not in (overrides or {}), environment

    conditions = conditions_from_plan(plan)
    assert len({c.system_instruction for c in conditions.values()}) == 1
    assert len({c.task_instruction for c in conditions.values()}) == 1


def test_the_old_check_passes_the_committed_plan_it_cannot_see_the_gap_in(plan):
    """It is not being replaced for being wrong. It is being joined."""
    conditions = conditions_from_plan(plan)
    assert (
        check_model_run_conditions(
            conditions, comparison=COMPARISON_SAME_GENERATED_CODE
        )
        == []
    )
    # And the new rule, on the same plan, does find something.
    assert _problems(plan)


def test_the_committed_prompt_files_each_carry_their_own_standing_instruction(plan):
    """Which is why the plan's ``system_instruction`` reaches nobody."""
    for environment in THE_THREE_RUN_PLACES:
        settings = _settings(environment)
        name = _prompt_files_a_run_place_might_send(environment, settings)[0]
        assert load_prompt(name).get("system_message", "").strip(), environment


# ── What is measured ──────────────────────────────────────────────────────────


def test_the_three_places_send_three_differently_named_prompt_files(plan):
    measured, unmeasurable = _measured(plan)
    assert unmeasurable == {}
    assert set(measured) == set(THE_THREE_RUN_PLACES)
    assert len({request.prompt_name for request in measured.values()}) == 3


def test_each_measured_width_is_what_the_production_builders_produce(plan):
    """Worked out a second way, so the rule cannot mark its own homework."""
    measured, _ = _measured(plan)
    for environment, request in measured.items():
        assert request.characters == _sent(environment), environment
        assert request.characters == sum(width for _, width in request.parts)


def test_the_widest_first_request_is_the_containers_and_it_is_not_close(plan):
    measured, _ = _measured(plan)
    widths = {name: request.characters for name, request in measured.items()}
    assert max(widths, key=widths.get) == "docker_container"
    assert widths["docker_container"] > 2 * min(widths.values())


def test_the_containers_extra_width_is_what_its_runner_builds_beforehand(plan):
    """Not a longer prompt file alone: sections the render never sees."""
    measured, _ = _measured(plan)
    built = dict(measured["docker_container"].parts)
    beforehand = {
        what: width for what, width in built.items() if "before the render" in what
    }
    assert beforehand, "the container's runner declares sections it builds"
    assert sum(beforehand.values()) > 0

    for other in ("host_python_process", "azure_code_interpreter"):
        assert not any(
            "before the render" in what for what, _ in measured[other].parts
        ), other


# ── What the rule does with it ────────────────────────────────────────────────


def test_the_committed_plan_is_refused_and_the_refusal_names_all_three(plan):
    problems = _problems(plan)
    assert len(problems) == 1
    refusal = problems[0]
    for environment in THE_THREE_RUN_PLACES:
        assert environment in refusal
        assert f"{_sent(environment)} characters" in refusal


def test_the_refusal_states_the_difference_carried_on_every_call(plan):
    measured, _ = _measured(plan)
    widths = [request.characters for request in measured.values()]
    refusal = _problems(plan)[0]
    assert f"a difference of {max(widths) - min(widths)} characters" in refusal
    assert "on every call" in refusal


def test_the_refusal_offers_both_exits_and_takes_neither(plan):
    """Which one is right is a decision about the experiment, not about code."""
    refusal = _problems(plan)[0]
    assert "made to send one first request" in refusal
    assert "recorded as something other than same_generated_code_rerun" in refusal


def test_no_two_run_places_share_a_runner_so_no_two_share_a_default_prompt():
    """Why the finding cannot be cleared by editing one settings file.

    Which prompt file a place sends is chosen by its runner class, not by its
    settings, and ``RUNNER_CLASS_BY_ENVIRONMENT`` gives each of the three a
    different class. So as long as each keeps its runner's default, the three
    are asked three different things no matter what the plan says.
    """
    runners = {
        environment: RUNNER_CLASS_BY_ENVIRONMENT[environment]
        for environment in THE_THREE_RUN_PLACES
    }
    assert len(set(runners.values())) == 3
    assert all(runner is not None for runner in runners.values())

    defaults = {
        environment: _prompt_files_a_run_place_might_send(
            environment, _settings(environment)
        )
        for environment in THE_THREE_RUN_PLACES
    }
    assert len({names[0] for names in defaults.values()}) == 3


def test_two_places_pinned_to_one_prompt_file_are_passed(plan, tmp_path):
    """The pass path, reached the only way it can be reached.

    Both places are pinned to one prompt file, wider than either runner's own
    default so the pin is what gets charged, and given the same wrapping. The
    container is deliberately not one of them: its runner builds sections
    before the render that no pin can take away, which is the difference this
    rule exists to see.
    """
    pinned_to = "sandbox_occupation_codegen"
    (tmp_path / "experiments").mkdir()
    for environment in ("host_python_process", "azure_code_interpreter"):
        settings = copy.deepcopy(_settings("host_python_process"))
        settings.setdefault("execution", {}).setdefault("sandbox", {})[
            "prompt_name"
        ] = pinned_to
        (tmp_path / "experiments" / f"{environment}.yaml").write_text(
            yaml.safe_dump(settings), encoding="utf-8"
        )

    plan = copy.deepcopy(plan)
    plan["experiment_files"] = {
        environment: f"experiments/{environment}.yaml"
        for environment in ("host_python_process", "azure_code_interpreter")
    }
    conditions = conditions_from_plan(plan)
    both = {
        environment: conditions[environment]
        for environment in ("host_python_process", "azure_code_interpreter")
    }

    measured, unmeasurable = _measure_first_requests(
        both, plan=plan, root=tmp_path, catalog=CATALOG
    )
    assert unmeasurable == {}
    assert {request.prompt_name for request in measured.values()} == {pinned_to}

    assert (
        _check_every_run_place_is_asked_the_same_thing(
            both,
            comparison=COMPARISON_SAME_GENERATED_CODE,
            plan=plan,
            root=tmp_path,
            catalog=CATALOG,
        )
        == []
    )


def test_one_added_sentence_in_a_shared_prompt_is_enough_to_be_refused(
    plan, tmp_path
):
    """The boundary: one prompt file pinned for both, one place's wrapping wider."""
    pinned_to = "sandbox_occupation_codegen"
    (tmp_path / "experiments").mkdir()
    base = copy.deepcopy(_settings("host_python_process"))
    base.setdefault("execution", {}).setdefault("sandbox", {})[
        "prompt_name"
    ] = pinned_to
    (tmp_path / "experiments" / "same.yaml").write_text(
        yaml.safe_dump(base), encoding="utf-8"
    )
    widened = copy.deepcopy(base)
    widened["condition_a"]["prompt"]["suffix"] = (
        widened["condition_a"]["prompt"]["suffix"].rstrip() + " One more sentence."
    )
    (tmp_path / "experiments" / "wider.yaml").write_text(
        yaml.safe_dump(widened), encoding="utf-8"
    )

    plan = copy.deepcopy(plan)
    plan["experiment_files"] = {
        "host_python_process": "experiments/same.yaml",
        "azure_code_interpreter": "experiments/wider.yaml",
    }
    conditions = conditions_from_plan(plan)
    both = {
        environment: conditions[environment]
        for environment in ("host_python_process", "azure_code_interpreter")
    }
    problems = _check_every_run_place_is_asked_the_same_thing(
        both,
        comparison=COMPARISON_SAME_GENERATED_CODE,
        plan=plan,
        root=tmp_path,
        catalog=CATALOG,
    )
    assert len(problems) == 1
    assert " One more sentence." not in problems[0], "the wording is not quoted back"
    assert "a difference of " in problems[0]


# ── Which comparison is judged ────────────────────────────────────────────────


@pytest.mark.parametrize(
    "comparison",
    (COMPARISON_TOOL_BUILT_IN_FEATURES, COMPARISON_NATIVE_PRODUCT_BUNDLE),
)
def test_the_other_two_comparisons_are_not_judged_here(plan, comparison):
    """``tool_built_in_features`` lets each tool keep its own features, and its
    own prompt is one of them. What it should hold still is its own decision to
    record, and this rule does not make it. The whole-product comparison does
    not even pin the model."""
    assert _problems(plan, comparison=comparison) == []


def test_a_plan_that_names_no_comparison_is_judged_as_the_strict_one(plan):
    """Same default the call site applies, so a missing key cannot buy silence."""
    plan = copy.deepcopy(plan)
    del plan["comparison"]
    assert _problems(plan)


# ── Fail closed ───────────────────────────────────────────────────────────────


def test_a_place_whose_request_cannot_be_built_is_refused_not_skipped(plan):
    plan = copy.deepcopy(plan)
    plan["experiment_files"]["docker_container"] = "experiments/nothing_here.yaml"
    problems = _problems(plan)
    unbuildable = [
        note
        for note in problems
        if note.startswith("whether docker_container is asked")
    ]
    assert len(unbuildable) == 1
    assert "cannot be built here" in unbuildable[0]


def test_a_place_the_plan_names_no_settings_file_for_is_refused(plan):
    plan = copy.deepcopy(plan)
    del plan["experiment_files"]["azure_code_interpreter"]
    problems = _problems(plan)
    assert any(
        "names no experiment settings file for azure_code_interpreter" in note
        for note in problems
    )


def test_a_place_no_runner_serves_is_refused_rather_than_left_out(plan, tmp_path):
    (tmp_path / "experiments").mkdir()
    (tmp_path / "experiments" / "nowhere.yaml").write_text(
        yaml.safe_dump(_settings("docker_container")), encoding="utf-8"
    )
    plan = copy.deepcopy(plan)
    conditions = conditions_from_plan(plan)
    plan["experiment_files"] = {
        A_RUN_PLACE_NO_RUNNER_SERVES: "experiments/nowhere.yaml"
    }
    problems = _check_every_run_place_is_asked_the_same_thing(
        {A_RUN_PLACE_NO_RUNNER_SERVES: conditions["docker_container"]},
        comparison=COMPARISON_SAME_GENERATED_CODE,
        plan=plan,
        root=tmp_path,
        catalog=CATALOG,
    )
    assert len(problems) == 1
    assert "no runner is registered for this run place" in problems[0]


def test_a_single_measurable_place_is_not_reported_as_agreement(plan, tmp_path):
    """One place on its own is a measurement, not a comparison."""
    plan = copy.deepcopy(plan)
    kept = plan["experiment_files"]["host_python_process"]
    plan["experiment_files"] = {"host_python_process": kept}
    conditions = conditions_from_plan(plan)

    problems = _check_every_run_place_is_asked_the_same_thing(
        {"host_python_process": conditions["host_python_process"]},
        comparison=COMPARISON_SAME_GENERATED_CODE,
        plan=plan,
        root=BATCH_RUNNER_ROOT,
        catalog=CATALOG,
    )
    assert problems == []

    # But the two that could not be built are named, rather than the one that
    # could being reported as the three agreeing.
    named = _problems(plan)
    assert len(named) == 2
    assert all(note.startswith("whether ") for note in named)


def test_an_empty_catalogue_is_refused_rather_than_compared_without_an_occupation(
    plan,
):
    problems = _problems(plan, catalog=replace(CATALOG, tasks=()))
    assert len(problems) == 1
    assert "the widest one cannot be taken from the task catalogue" in problems[0]
    assert "cannot be worked out" in problems[0]


# ── The whole free check ──────────────────────────────────────────────────────


def test_the_whole_free_check_reaches_this_rule_and_will_not_start(plan):
    result = run_envelope_preflight(plan, root=BATCH_RUNNER_ROOT)
    reached = [
        note
        for note in result.all_problems
        if "these places are not asked the same thing" in note
    ]
    assert len(reached) == 1
    assert result.may_start is False


def test_the_finding_is_a_technical_inconsistency_and_not_a_cost_finding(plan):
    """A cost policy can wave money aside. It has never been able to wave this
    aside, and recording it as a cost finding would let it."""
    result = run_envelope_preflight(plan, root=BATCH_RUNNER_ROOT)
    assert not any(
        "these places are not asked the same thing" in note
        for note in result.cost_findings
    )
