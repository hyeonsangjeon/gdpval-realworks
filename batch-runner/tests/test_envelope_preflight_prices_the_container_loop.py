"""The container's loop is read from its settings, not from a number in the plan.

The cost sum is the last thing standing between a plan and a bill. It prices one
attempt as ``tool_loop_max_model_turns`` calls to a model, and that number is
written into the plan by hand, one entry per run place.

For two of the three run places it has to be a written number. A separate Python
process on the server has no loop at all — ``core/subprocess_runner.py`` asks
once and runs the code itself. What Azure's own tool loop does inside itself is
not readable from this repository, so 8 is a limit somebody chose and is
honestly labelled as one.

The container is the third, and it is different: the real number is sitting in a
file in this repository, and nothing was reading it. Two settings move it.
``repair`` asks the model for the code again, as many times as its budget
allows. ``output_qa.vision`` sends rendered pages to a vision model, once per go
at the code. The plan says 1. That is true only while the committed file happens
to say ``repair: enabled: false`` — and ``core/sandbox_runner.py`` builds its
settings as ``{"enabled": True, ...}``, so deleting those two lines turns the
loop on and the plan goes on saying 1.

Measured before this was written, deleting them moved the container's quoted
cost not at all: 20 calls and 3.47 United States dollars, unchanged. Under the
comparison that re-runs one model's own code a different rule refused the run
and hid the staleness. Under ``tool_built_in_features`` — a comparison this same
plan names, with a scoreboard of its own — nothing refused at all, and the
ceiling was simply too low.

So the rule tested here holds under both comparisons. A ceiling is a ceiling
either way, and the comparison that leaves each tool its own features running is
exactly the one where the container's loop is meant to be on.

Nothing here calls a model, runs a container, or spends anything.
"""

from __future__ import annotations

import inspect
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core.execution_envelope_preflight import (  # noqa: E402
    ContainerAttemptShape,
    _check_the_plan_counts_every_call_the_container_makes,
    _container_loop_defaults,
    check_experiment_files_match_conditions,
    conditions_from_plan,
    container_attempt_shape,
)
from core.execution_environment_readiness import (  # noqa: E402
    ENVIRONMENT_AZURE_CODE_INTERPRETER,
    ENVIRONMENT_DOCKER_CONTAINER,
    ENVIRONMENT_HOST_PYTHON_PROCESS,
    EXECUTION_MODE_BY_ENVIRONMENT,
)
from core.sandbox_runner import SandboxRunner  # noqa: E402

ENVELOPE_DIRECTORY = BATCH_RUNNER_ROOT / "experiments" / "execution_envelope"
PLAN_PATH = ENVELOPE_DIRECTORY / "advance_check_plan.yaml"

RUN_MODEL = "the-model-being-compared"


@pytest.fixture
def plan() -> dict:
    return yaml.safe_load(PLAN_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def copied_root(tmp_path: Path) -> Path:
    """A throwaway copy of the settings files, so a test can change one."""
    destination = tmp_path / "experiments" / "execution_envelope"
    destination.parent.mkdir(parents=True)
    shutil.copytree(ENVELOPE_DIRECTORY, destination)
    return tmp_path


def _container_settings(**sandbox) -> dict:
    """One run place that is a container, named the way the runner names it."""
    return {
        ENVIRONMENT_DOCKER_CONTAINER: {
            "execution": {
                "mode": EXECUTION_MODE_BY_ENVIRONMENT[ENVIRONMENT_DOCKER_CONTAINER],
                "sandbox": sandbox,
            }
        }
    }


def _conditions(model: str = RUN_MODEL) -> dict:
    """Only the one field this rule reads, so the test says what it depends on."""
    return {ENVIRONMENT_DOCKER_CONTAINER: SimpleNamespace(resolved_model=model)}


def _plan_pricing(**turns) -> dict:
    return {"cost": {"assumptions": {"tool_loop_max_model_turns": turns}}}


def _refusals(settings: dict, priced: int | None, model: str = RUN_MODEL) -> list[str]:
    written = {} if priced is None else {ENVIRONMENT_DOCKER_CONTAINER: priced}
    return _check_the_plan_counts_every_call_the_container_makes(
        settings, _conditions(model), _plan_pricing(**written)
    )


# ── The arithmetic, read out of the container's own settings ──────────────


def test_a_container_that_writes_the_code_once_asks_once():
    shape = container_attempt_shape({"repair": {"enabled": False}})
    assert (shape.code_turns, shape.picture_check_turns, shape.model_turns) == (1, 0, 1)


def test_the_committed_container_file_really_does_ask_once(plan):
    """1 in the plan is right today, and this is the reason it is right."""
    document = yaml.safe_load(
        (BATCH_RUNNER_ROOT / str(plan["experiment_files"][ENVIRONMENT_DOCKER_CONTAINER]))
        .read_text(encoding="utf-8")
    )
    sandbox = document["execution"]["sandbox"]
    assert sandbox["repair"]["enabled"] is False, "the load-bearing line"
    assert container_attempt_shape(sandbox).model_turns == 1


@pytest.mark.parametrize(
    "sandbox",
    [
        pytest.param({}, id="the whole repair block deleted"),
        pytest.param({"repair": {}}, id="the enabled setting deleted"),
        pytest.param({"output_qa": {"enabled": False}}, id="only the picture check off"),
    ],
)
def test_leaving_repair_out_asks_twice_because_absent_means_on(sandbox):
    """The case the plan's written 1 gets wrong, and gets wrong silently."""
    assert container_attempt_shape(sandbox).model_turns == 2


def test_a_bigger_repair_budget_is_more_turns():
    shape = container_attempt_shape({"repair": {"enabled": True, "max_attempts": 3}})
    assert shape.model_turns == 4


def test_a_budget_written_next_to_repair_switched_off_buys_nothing():
    """``core/sandbox_runner.py`` reads the budget as 0 when repair is off."""
    shape = container_attempt_shape({"repair": {"enabled": False, "max_attempts": 9}})
    assert shape.model_turns == 1


def test_the_picture_check_asks_once_for_each_go_at_the_code():
    shape = container_attempt_shape(
        {
            "repair": {"enabled": True, "max_attempts": 1},
            "output_qa": {"vision": {"enabled": True}},
        }
    )
    assert (shape.code_turns, shape.picture_check_turns, shape.model_turns) == (2, 2, 4)


@pytest.mark.parametrize(
    "output_qa",
    [
        pytest.param({"vision": {"enabled": True}}, id="all three gates open"),
        pytest.param(
            {"enabled": True, "render": True, "vision": {"enabled": True}},
            id="all three written out",
        ),
    ],
)
def test_the_picture_check_counts_when_every_gate_it_needs_is_open(output_qa):
    shape = container_attempt_shape({"repair": {"enabled": False}, "output_qa": output_qa})
    assert shape.picture_check_turns == 1


@pytest.mark.parametrize(
    "output_qa",
    [
        pytest.param({}, id="vision left out, which core/output_qa.py reads as off"),
        pytest.param({"vision": {"enabled": False}}, id="vision switched off"),
        pytest.param(
            {"enabled": False, "vision": {"enabled": True}},
            id="the whole picture check off, so run_output_qa returns at once",
        ),
        pytest.param(
            {"render": False, "vision": {"enabled": True}},
            id="nothing rendered, so there are no pages to send",
        ),
    ],
)
def test_the_picture_check_does_not_count_when_any_gate_is_shut(output_qa):
    shape = container_attempt_shape({"repair": {"enabled": False}, "output_qa": output_qa})
    assert (shape.picture_check_turns, shape.model_turns) == (0, 1)


def test_the_sum_is_spelled_out_so_a_reader_can_check_it():
    shape = container_attempt_shape(
        {"output_qa": {"vision": {"enabled": True, "deployment": "some-vision-model"}}}
    )
    assert shape.in_words() == (
        "2 to write the code and 2 to some-vision-model for the picture check"
    )


# ── The values are read off the runner, not typed again here ──────────────


def test_the_defaults_this_check_assumes_are_the_ones_the_runner_really_uses():
    """Read from the runner, not from a sentence about the runner.

    This is the difference between a check that is right and a check that was
    right on the day somebody wrote it.
    """
    repair, picture = _container_loop_defaults()
    built_with_nothing_written = SandboxRunner(llm_client=None)
    assert repair == built_with_nothing_written.repair_cfg
    assert picture == built_with_nothing_written.output_qa_cfg


def test_no_default_is_typed_into_this_check_by_hand():
    """The numbers that decide the sum must not appear as literals here.

    ``container_attempt_shape`` may write the 1 for the first go at the code,
    because asking once is what an attempt *is*. Everything else — whether
    repair starts on, how many repairs it allows, whether pages are rendered —
    has to come from the runner.
    """
    source = inspect.getsource(container_attempt_shape)
    assert "True" not in source and "False" not in source
    for typed in ("max_attempts\", 1", "max_attempts=1"):
        assert typed not in source


def test_the_runner_is_reached_for_only_when_the_check_runs():
    """The free check must import on a machine with no container libraries.

    Importing the runner at module scope would make a check whose whole point
    is that it costs nothing depend on the container being installed.
    """
    assert "from core.sandbox_runner import SandboxRunner" in inspect.getsource(
        _container_loop_defaults
    )
    module_source = inspect.getsource(sys.modules["core.execution_envelope_preflight"])
    import_block = module_source.split("\ndef ", 1)[0]
    assert "sandbox_runner" not in import_block


# ── The refusal itself ────────────────────────────────────────────────────


def test_a_plan_that_prices_the_real_number_is_left_alone():
    assert _refusals(_container_settings(repair={"enabled": False}), 1) == []


def test_a_plan_that_prices_fewer_calls_than_the_settings_make_is_refused():
    problems = _refusals(_container_settings(), 1)
    assert len(problems) == 1
    assert "ask a model 2 times inside one attempt" in problems[0]
    assert "prices 1" in problems[0]
    assert "approved maximum" in problems[0]


def test_a_plan_that_prices_more_than_the_settings_make_is_allowed():
    """A plan may be more careful than its settings. It may not be less.

    That is what keeps the number a stated assumption where it has to be one —
    Azure's own tool loop is not readable from here, and 8 is a choice.
    """
    assert _refusals(_container_settings(repair={"enabled": False}), 8) == []


def test_the_refusal_counts_the_picture_check_too():
    problems = _refusals(
        _container_settings(
            repair={"enabled": False},
            output_qa={"vision": {"enabled": True, "model": RUN_MODEL}},
        ),
        1,
    )
    assert len(problems) == 1
    assert "ask a model 2 times inside one attempt" in problems[0]
    assert "for the picture check" in problems[0]


def test_a_picture_check_at_another_model_is_said_rather_than_folded_in():
    """Counting the call and pricing it wrong is still a wrong sum."""
    problems = _refusals(
        _container_settings(
            repair={"enabled": False},
            output_qa={"vision": {"enabled": True, "deployment": "some-vision-model"}},
        ),
        2,
    )
    assert len(problems) == 1
    assert "picture check calls some-vision-model" in problems[0]
    assert RUN_MODEL in problems[0]


def test_a_picture_check_naming_no_model_is_reported_as_unreadable():
    """``core/output_qa.py`` passes the name straight through, even as None."""
    problems = _refusals(
        _container_settings(repair={"enabled": False}, output_qa={"vision": {"enabled": True}}),
        2,
    )
    assert len(problems) == 1
    assert "names no model for it" in problems[0]
    assert "cannot be read" in problems[0]


def test_both_things_wrong_are_both_reported():
    problems = _refusals(
        _container_settings(output_qa={"vision": {"enabled": True, "model": "elsewhere"}}),
        1,
    )
    assert len(problems) == 2
    assert any("4 times inside one attempt" in problem for problem in problems)
    assert any("picture check calls elsewhere" in problem for problem in problems)


def test_a_run_place_the_plan_prices_nothing_for_is_left_to_the_cost_sum():
    """``estimate_cost_ceiling`` refuses that already. Saying it twice helps nobody."""
    assert _refusals(_container_settings(), None) == []


@pytest.mark.parametrize(
    "environment",
    [ENVIRONMENT_HOST_PYTHON_PROCESS, ENVIRONMENT_AZURE_CODE_INTERPRETER],
)
def test_the_run_places_with_no_container_are_not_asked(environment):
    """Neither of the other two has a sandbox block, and neither is guessed at."""
    settings = {
        environment: {
            "execution": {"mode": EXECUTION_MODE_BY_ENVIRONMENT[environment]}
        }
    }
    problems = _check_the_plan_counts_every_call_the_container_makes(
        settings,
        {environment: SimpleNamespace(resolved_model=RUN_MODEL)},
        _plan_pricing(**{environment: 1}),
    )
    assert problems == []


def test_a_container_with_no_sandbox_block_at_all_is_still_asked():
    """The state where every value is the absent one, which is the worst state."""
    settings = {
        ENVIRONMENT_DOCKER_CONTAINER: {
            "execution": {
                "mode": EXECUTION_MODE_BY_ENVIRONMENT[ENVIRONMENT_DOCKER_CONTAINER]
            }
        }
    }
    problems = _check_the_plan_counts_every_call_the_container_makes(
        settings, _conditions(), _plan_pricing(**{ENVIRONMENT_DOCKER_CONTAINER: 1})
    )
    assert len(problems) == 1
    assert "2 times inside one attempt" in problems[0]


# ── It holds under both comparisons, which is the gap it was written for ──


@pytest.mark.parametrize(
    "comparison",
    ["same_generated_code_rerun", "tool_built_in_features"],
)
def test_the_refusal_holds_whichever_comparison_is_being_run(
    plan, copied_root, comparison
):
    """The measured gap: under one comparison a different rule hid this.

    Under the other — named by this same plan, with a scoreboard of its own —
    nothing refused, and the ceiling was simply too low.
    """
    changed = dict(plan)
    changed["comparison"] = comparison
    target = copied_root / str(plan["experiment_files"][ENVIRONMENT_DOCKER_CONTAINER])
    document = yaml.safe_load(target.read_text(encoding="utf-8"))
    del document["execution"]["sandbox"]["repair"]
    target.write_text(
        yaml.safe_dump(document, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )

    problems = check_experiment_files_match_conditions(
        changed, conditions_from_plan(changed), root=copied_root
    )
    assert any("inside one attempt" in problem for problem in problems), comparison


def test_the_committed_files_are_reported_clean(plan, copied_root):
    problems = check_experiment_files_match_conditions(
        plan, conditions_from_plan(plan), root=copied_root
    )
    assert [p for p in problems if "inside one attempt" in p] == []


def test_the_rule_is_reached_from_the_check_that_gates_the_spend():
    """A rule nothing calls refuses nothing."""
    source = inspect.getsource(check_experiment_files_match_conditions)
    assert "_check_the_plan_counts_every_call_the_container_makes" in source


def test_the_shape_says_what_it_counted_and_not_only_how_many():
    """A total nobody can take apart is a number to be trusted, not checked."""
    shape = ContainerAttemptShape(
        code_turns=2, picture_check_turns=2, picture_check_model="a-vision-model"
    )
    assert shape.model_turns == 4
    assert "2 to write the code" in shape.in_words()
    assert "a-vision-model" in shape.in_words()
