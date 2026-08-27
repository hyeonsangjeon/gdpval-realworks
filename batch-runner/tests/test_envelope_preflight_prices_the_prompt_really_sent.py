"""The first request is priced at what it renders to, not at what the plan kept.

``instruction_character_count`` pays for everything a request carries besides
the task's own words and its reference files. It is charged on every call every
run place makes, so a figure below what is really sent understates the running
half of the bill once per call, for as long as the plan stands.

The plan charged 1,068 characters, and reached that figure by adding up the two
wording blocks it keeps in ``model_run_conditions``. Both halves of that were
wrong, in the same direction:

* The ``system_instruction`` block it counted is never sent. ``render_prompt``
  lets a committed prompt file's own ``system_message`` win whenever it has one,
  and all three committed files have one — so a run place's own ``system`` block
  is a fallback that never comes up. 345 characters were being charged for
  wording no model reads.
* The committed prompt file itself was not counted at all. Neither its standing
  instruction nor the several thousand characters of wording it wraps every task
  in, which is the great majority of what is sent.

So the figure is a render now. Each run place's prompt file is resolved the way
``core/executor.py`` resolves it, rendered through ``fixed_prompt_characters``
with that place's own ``condition_a.prompt`` block and the widest occupation
name in the committed catalogue, and the plan is refused where it charges less
than came back. The container's request comes to 5,020 characters — not 1,068.
No test in this file types 5,020, 3,867 or 3,533: every one of them renders.

Where a settings file names a prompt and the runner declares a different
default, both are rendered and the longer charged. That is not indecision:
``executor.py`` follows ``execution.sandbox.prompt_name`` on the sandbox branch
and reaches straight past it on the subprocess branch, so which one a run place
takes is settled by wiring this cannot read back.

One thing stays outside the figure, and stays named rather than implied.
``SandboxRunner._augment_prompt`` adds a deliverable contract section, a
dependency hint and a skills manual the committed settings switch off to the
container's first request. Those are outside what ``render_prompt`` produces, so
the demand made of the container is smaller than the container's real request.
This rule under-demands there; it never lets a plan claim more than the render
proved.

Nothing here calls a model, runs a container, or spends anything.
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

from core.execution_envelope_cost import CostAssumptions  # noqa: E402
from core.execution_envelope_preflight import (  # noqa: E402
    _check_instruction_length,
    _prompt_files_a_run_place_might_send,
    _runner_default_prompt_name,
    conditions_from_plan,
    load_plan,
    run_envelope_preflight,
)
from core.execution_envelope_tasks import (  # noqa: E402
    load_task_catalog,
    widest_occupation,
)
from core.prompt_loader import (  # noqa: E402
    fixed_prompt_characters,
    load_prompt,
    render_prompt,
)

PLAN_PATH = (
    BATCH_RUNNER_ROOT
    / "experiments"
    / "execution_envelope"
    / "advance_check_plan.yaml"
)
CATALOG = load_task_catalog()
WIDEST_OCCUPATION = widest_occupation(CATALOG)

#: A committed prompt file that is not one of the three: it has neither of the
#: two keys ``load_prompt`` requires, so naming it is a real, unfaked way for the
#: measurement to fail.
A_COMMITTED_FILE_THAT_IS_NOT_A_PROMPT = "agentic_sandbox_solver"

#: A run place this repository has no runner for. Used to prove the rule refuses
#: rather than guessing when nothing declares which prompt file gets sent.
A_RUN_PLACE_NO_RUNNER_SERVES = "somewhere_nobody_wired_up"


def _plan(**assumption_overrides) -> dict:
    plan = load_plan(PLAN_PATH)
    plan["cost"]["assumptions"].update(assumption_overrides)
    return plan


def _priced_at(characters: int) -> dict:
    return _plan(instruction_character_count=characters)


def _problems(plan: dict, *, root: Path = BATCH_RUNNER_ROOT, catalog=None) -> list[str]:
    """Run the rule alone, the way ``run_envelope_preflight`` runs it."""
    return _check_instruction_length(
        conditions_from_plan(plan),
        CostAssumptions.from_mapping(plan["cost"]["assumptions"]),
        plan=plan,
        root=root,
        catalog=CATALOG if catalog is None else catalog,
    )


def _problems_for(
    environment: str, plan: dict, *, root: Path = BATCH_RUNNER_ROOT
) -> list[str]:
    """The same rule, asked about one run place, so the others cannot answer."""
    conditions = conditions_from_plan(load_plan(PLAN_PATH))
    return _check_instruction_length(
        {environment: conditions["docker_container"]},
        CostAssumptions.from_mapping(plan["cost"]["assumptions"]),
        plan=plan,
        root=root,
        catalog=CATALOG,
    )


def _settings(environment: str) -> dict:
    relative = load_plan(PLAN_PATH)["experiment_files"][environment]
    return yaml.safe_load((BATCH_RUNNER_ROOT / relative).read_text(encoding="utf-8"))


def _wrapping(environment: str) -> dict | None:
    """The ``condition_a.prompt`` block a run place wraps the prompt file in."""
    return (_settings(environment).get("condition_a") or {}).get("prompt")


def _prompt_data(environment: str) -> dict:
    settings = _settings(environment)
    names = _prompt_files_a_run_place_might_send(environment, settings)
    assert names, environment
    return load_prompt(names[0])


def _sent(environment: str) -> int:
    """What this run place's first request renders to, task aside."""
    return sum(
        fixed_prompt_characters(
            _prompt_data(environment),
            experiment_prompt=_wrapping(environment),
            occupation=WIDEST_OCCUPATION,
        ).values()
    )


THE_THREE_RUN_PLACES = (
    "host_python_process",
    "docker_container",
    "azure_code_interpreter",
)


# ── What the measurement is ───────────────────────────────────────────────────


@pytest.mark.parametrize("environment", THE_THREE_RUN_PLACES)
def test_the_figure_is_a_render_and_not_a_tally_of_written_down_lengths(environment):
    """Every part added up comes to a string ``render_prompt`` really produced."""
    task = "q" * 4000
    rendered = render_prompt(
        _prompt_data(environment),
        occupation=WIDEST_OCCUPATION,
        task_prompt=task,
        experiment_prompt=_wrapping(environment),
    )
    whole = len(rendered["system_message"]) + len(rendered["user_prompt"])
    assert _sent(environment) == whole - len(task)


@pytest.mark.parametrize("environment", THE_THREE_RUN_PLACES)
def test_the_tasks_own_words_are_left_out_however_long_they_are(environment):
    """The task is charged per task elsewhere; counting it here would bill twice."""
    figures = set()
    for length in (0, 40, 4000):
        rendered = render_prompt(
            _prompt_data(environment),
            occupation=WIDEST_OCCUPATION,
            task_prompt="q" * length,
            experiment_prompt=_wrapping(environment),
        )
        whole = len(rendered["system_message"]) + len(rendered["user_prompt"])
        figures.add(whole - length)
    assert figures == {_sent(environment)}


@pytest.mark.parametrize("environment", THE_THREE_RUN_PLACES)
def test_wording_added_to_the_committed_prompt_file_moves_the_figure(environment):
    """Edit ``prompts/<name>.yaml`` and the demand follows, with no test edited."""
    added = "  and mind the units." * 9
    widened = copy.deepcopy(_prompt_data(environment))
    widened["user_prompt"] = widened["user_prompt"] + added
    after = sum(
        fixed_prompt_characters(
            widened,
            experiment_prompt=_wrapping(environment),
            occupation=WIDEST_OCCUPATION,
        ).values()
    )
    assert after == _sent(environment) + len(added)


@pytest.mark.parametrize("environment", THE_THREE_RUN_PLACES)
def test_wording_added_to_a_run_places_own_settings_moves_the_figure(environment):
    """Widen the ``suffix`` in ``condition_a.prompt`` and the demand follows."""
    added = " Check every figure against the source file before you write it."
    wrapping = dict(_wrapping(environment) or {})
    wrapping["suffix"] = wrapping["suffix"].strip() + added
    after = sum(
        fixed_prompt_characters(
            _prompt_data(environment),
            experiment_prompt=wrapping,
            occupation=WIDEST_OCCUPATION,
        ).values()
    )
    assert after == _sent(environment) + len(added)


@pytest.mark.parametrize("environment", THE_THREE_RUN_PLACES)
def test_the_settings_wording_is_counted_stripped_and_joined_on(environment):
    """How ``render_prompt`` attaches it is part of the figure, not rounded off."""
    wrapping = _wrapping(environment) or {}
    assert not wrapping.get("prefix") and not wrapping.get("body"), (
        "the committed file wraps the prompt in a suffix alone"
    )
    widths = fixed_prompt_characters(
        _prompt_data(environment),
        experiment_prompt=wrapping,
        occupation=WIDEST_OCCUPATION,
    )
    joined_on_with = len("\n\n")
    assert widths["the wording this run place's own settings add around it"] == (
        len(wrapping["suffix"].strip()) + joined_on_with
    )


@pytest.mark.parametrize("environment", THE_THREE_RUN_PLACES)
def test_a_run_places_own_system_block_is_reported_as_reaching_nobody(environment):
    """The regression: the block the old figure was built from is never sent."""
    wrapping = _wrapping(environment) or {}
    assert wrapping.get("system", "").strip(), "the file does keep such a block"

    widths = fixed_prompt_characters(
        _prompt_data(environment),
        experiment_prompt=wrapping,
        occupation=WIDEST_OCCUPATION,
    )
    assert widths["the standing instruction this run place's own settings add"] == 0

    # What is counted instead is the prompt file's own standing instruction, and
    # that is what a run really sends: render_prompt lets the file win.
    file_side = widths["the standing instruction the committed prompt file holds"]
    assert file_side > 0
    rendered = render_prompt(
        _prompt_data(environment),
        occupation=WIDEST_OCCUPATION,
        task_prompt="",
        experiment_prompt=wrapping,
    )
    assert len(rendered["system_message"]) == file_side
    assert rendered["system_message"] != wrapping["system"].strip()


@pytest.mark.parametrize("environment", THE_THREE_RUN_PLACES)
def test_a_wider_occupation_name_makes_a_wider_prompt(environment):
    """Which is why the widest name in the catalogue is what they render with."""
    narrow = sum(
        fixed_prompt_characters(
            _prompt_data(environment),
            experiment_prompt=_wrapping(environment),
            occupation="x",
        ).values()
    )
    grew_by = _sent(environment) - narrow
    per_mention = len(WIDEST_OCCUPATION) - len("x")
    assert grew_by > 0
    assert grew_by % per_mention == 0, "the name goes in a whole number of times"


def test_a_template_that_will_not_render_is_raised_rather_than_guessed_at():
    """No reading of an unrenderable template returns a smaller answer instead."""
    broken = copy.deepcopy(_prompt_data("docker_container"))
    broken["user_prompt"] = broken["user_prompt"] + "\n{no_such_variable}"
    with pytest.raises(KeyError):
        fixed_prompt_characters(broken, occupation=WIDEST_OCCUPATION)


# ── Which prompt file a run place could send ──────────────────────────────────


@pytest.mark.parametrize("environment", THE_THREE_RUN_PLACES)
def test_each_run_place_falls_back_to_its_own_runners_prompt(environment):
    """None of the three names a prompt, so each gets its runner's declared one."""
    settings = _settings(environment)
    assert not (settings.get("execution", {}).get("sandbox", {}) or {}).get(
        "prompt_name"
    )
    assert _prompt_files_a_run_place_might_send(environment, settings) == (
        _runner_default_prompt_name(environment),
    )


def test_a_prompt_named_in_the_settings_is_priced_alongside_the_default():
    """Both, because ``executor.py`` follows the setting in one branch only."""
    settings = copy.deepcopy(_settings("docker_container"))
    settings["execution"]["sandbox"]["prompt_name"] = "subprocess_occupation_codegen"
    candidates = _prompt_files_a_run_place_might_send("docker_container", settings)
    assert set(candidates) == {
        "subprocess_occupation_codegen",
        _runner_default_prompt_name("docker_container"),
    }


def test_a_run_place_no_runner_serves_names_no_prompt_file():
    assert _runner_default_prompt_name(A_RUN_PLACE_NO_RUNNER_SERVES) is None
    assert (
        _prompt_files_a_run_place_might_send(A_RUN_PLACE_NO_RUNNER_SERVES, {}) == ()
    )


def test_the_widest_candidate_prompt_file_is_the_one_charged(tmp_path):
    """Two candidates, and the demand is the longer — worked out here, not read."""
    a_narrower_prompt = "code_interpreter_occupation_codegen"
    wrapping = _wrapping("docker_container")
    narrower, its_own = (
        sum(
            fixed_prompt_characters(
                load_prompt(name),
                experiment_prompt=wrapping,
                occupation=WIDEST_OCCUPATION,
            ).values()
        )
        for name in (a_narrower_prompt, _runner_default_prompt_name("docker_container"))
    )
    assert narrower < its_own, "the two candidates have to differ for this to prove it"

    settings = copy.deepcopy(_settings("docker_container"))
    settings["execution"]["sandbox"]["prompt_name"] = a_narrower_prompt
    (tmp_path / "experiments").mkdir()
    (tmp_path / "experiments" / "container.yaml").write_text(
        yaml.safe_dump(settings), encoding="utf-8"
    )
    plan = _priced_at(narrower)
    plan["experiment_files"] = {"docker_container": "experiments/container.yaml"}

    refusals = _problems_for("docker_container", plan, root=tmp_path)
    assert len(refusals) == 1, "charging the narrower of the two is not enough"
    assert f"renders to {its_own} characters" in refusals[0]
    assert its_own - narrower == int(
        refusals[0].split(" characters short")[0].split("— ")[-1]
    )


def test_the_widest_occupation_is_the_widest_one_in_the_catalogue():
    """Worked out a second way here, so the rule cannot mark its own homework."""
    every_name = [task.occupation for task in CATALOG.tasks]
    assert WIDEST_OCCUPATION in every_name
    assert len(WIDEST_OCCUPATION) == max(len(name) for name in every_name)


# ── What the rule does with it ────────────────────────────────────────────────


def test_the_committed_plan_charges_enough_for_every_run_place():
    assert _problems(load_plan(PLAN_PATH)) == []


def test_the_plan_charges_at_least_what_the_widest_run_place_sends():
    charged = load_plan(PLAN_PATH)["cost"]["assumptions"][
        "instruction_character_count"
    ]
    assert charged >= max(_sent(place) for place in THE_THREE_RUN_PLACES)


@pytest.mark.parametrize("environment", THE_THREE_RUN_PLACES)
def test_one_character_below_what_a_run_place_sends_is_refused(environment):
    """The boundary, taken from the render rather than from a number typed here."""
    sends = _sent(environment)
    assert _problems_for(environment, _priced_at(sends)) == []

    refusals = _problems_for(environment, _priced_at(sends - 1))
    assert len(refusals) == 1
    assert refusals[0].startswith(environment)
    assert f"renders to {sends} characters" in refusals[0]
    assert f"charges {sends - 1} characters" in refusals[0]
    assert "1 characters short" in refusals[0]


def test_a_plan_more_careful_than_its_prompts_is_left_alone():
    """Only the cheap direction is refused."""
    assert _problems(_priced_at(max(_sent(p) for p in THE_THREE_RUN_PLACES) * 4)) == []


def test_the_figure_this_replaces_is_refused_for_every_run_place():
    """The two wording blocks the plan keeps come to less than any of the three."""
    conditions = conditions_from_plan(load_plan(PLAN_PATH))
    for environment, condition in conditions.items():
        the_old_way = len(condition.system_instruction) + len(
            condition.task_instruction
        )
        assert the_old_way < _sent(environment), environment

    refused = _problems(
        _priced_at(
            max(
                len(condition.system_instruction) + len(condition.task_instruction)
                for condition in conditions.values()
            )
        )
    )
    assert {problem.split()[0] for problem in refused} == set(THE_THREE_RUN_PLACES)


def test_a_refusal_names_the_prompt_file_and_says_what_the_figure_is_made_of():
    refused = _problems(_priced_at(1))
    container = next(p for p in refused if p.startswith("docker_container"))
    assert "prompts/sandbox_occupation_codegen.yaml" in container
    assert f"renders to {_sent('docker_container')} characters" in container
    assert "the wording the committed prompt file wraps the task in" in container
    assert "the standing instruction the committed prompt file holds" in container
    assert "the wording this run place's own settings add around it" in container
    # The part that reaches nobody is not listed as though it were sent.
    assert (
        "the standing instruction this run place's own settings add"
        not in container
    )


# ── Fail closed ───────────────────────────────────────────────────────────────


def test_a_run_place_whose_settings_file_the_plan_does_not_name_is_refused():
    plan = _priced_at(1_000_000)
    del plan["experiment_files"]["docker_container"]
    problems = _problems(plan)
    assert len(problems) == 1
    assert "names no experiment settings file for docker_container" in problems[0]


def test_a_settings_file_that_is_not_there_is_refused():
    plan = _priced_at(1_000_000)
    plan["experiment_files"]["docker_container"] = "experiments/nothing_here.yaml"
    problems = _problems(plan)
    assert len(problems) == 1
    assert problems[0].startswith("docker_container's cost is charged")
    assert "cannot be built here and so cannot be priced" in problems[0]


def test_a_settings_file_that_holds_no_mapping_is_refused(tmp_path):
    (tmp_path / "experiments").mkdir()
    (tmp_path / "experiments" / "not_a_mapping.yaml").write_text(
        "just a line of prose\n", encoding="utf-8"
    )
    plan = _priced_at(1_000_000)
    plan["experiment_files"] = {
        "docker_container": "experiments/not_a_mapping.yaml"
    }
    problems = _problems_for("docker_container", plan, root=tmp_path)
    assert len(problems) == 1
    assert "does not hold a mapping at the top level" in problems[0]


def test_a_named_prompt_that_is_not_a_prompt_is_refused(tmp_path):
    """A committed file missing the keys ``load_prompt`` requires stops the sum."""
    settings = copy.deepcopy(_settings("docker_container"))
    settings["execution"]["sandbox"][
        "prompt_name"
    ] = A_COMMITTED_FILE_THAT_IS_NOT_A_PROMPT
    (tmp_path / "experiments").mkdir()
    (tmp_path / "experiments" / "container.yaml").write_text(
        yaml.safe_dump(settings), encoding="utf-8"
    )
    plan = _priced_at(1_000_000)
    plan["experiment_files"] = {"docker_container": "experiments/container.yaml"}
    problems = _problems_for("docker_container", plan, root=tmp_path)
    assert len(problems) == 1
    assert "missing required keys" in problems[0]
    assert "cannot be built here and so cannot be priced" in problems[0]


def test_a_run_place_no_runner_serves_is_refused_rather_than_priced(tmp_path):
    (tmp_path / "experiments").mkdir()
    (tmp_path / "experiments" / "nowhere.yaml").write_text(
        yaml.safe_dump(_settings("docker_container")), encoding="utf-8"
    )
    plan = _priced_at(1_000_000)
    conditions = conditions_from_plan(plan)
    invented = {
        A_RUN_PLACE_NO_RUNNER_SERVES: conditions["docker_container"],
    }
    plan["experiment_files"] = {
        A_RUN_PLACE_NO_RUNNER_SERVES: "experiments/nowhere.yaml"
    }
    problems = _check_instruction_length(
        invented,
        CostAssumptions.from_mapping(plan["cost"]["assumptions"]),
        plan=plan,
        root=tmp_path,
        catalog=CATALOG,
    )
    assert len(problems) == 1
    assert "no runner is registered for this run place" in problems[0]


def test_an_empty_catalogue_is_refused_rather_than_priced_with_no_occupation():
    """An occupation of ``""`` would price a prompt that names nobody."""
    problems = _problems(_priced_at(1_000_000), catalog=replace(CATALOG, tasks=()))
    assert len(problems) == 1
    assert "the widest one cannot be taken from the task catalogue" in problems[0]


# ── The whole free check ──────────────────────────────────────────────────────


def test_the_whole_free_check_reaches_this_rule():
    """The committed plan clears it, and a plan back at the old figure does not."""
    passing = run_envelope_preflight(load_plan(PLAN_PATH), root=BATCH_RUNNER_ROOT)
    assert not any(
        "characters for that part of every request" in problem
        for problem in passing.all_problems
    )

    failing = run_envelope_preflight(_priced_at(1068), root=BATCH_RUNNER_ROOT)
    refused = [
        problem
        for problem in failing.all_problems
        if "characters for that part of every request" in problem
    ]
    assert {problem.split()[0] for problem in refused} == set(THE_THREE_RUN_PLACES)
    assert failing.may_start is False
