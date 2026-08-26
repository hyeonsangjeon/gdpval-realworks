"""What the container's second question carries is read from the runner.

The cost sum charges ``max_tool_result_tokens_per_turn`` for everything that
sits in front of the model on a later turn without being the task or the
model's own words. For the container the plan writes ``0``, and justifies it in
its own sentence: the model "is asked once and nothing is carried forward".

That sentence is true only while ``experiments/execution_envelope/
exp031_envelope_docker_container.yaml`` says ``repair: enabled: false``. It is
one line, nothing outside it holds it in place, and ``core/sandbox_runner.py``
builds its repair settings as ``{"enabled": True, "max_attempts": 1, **(repair
or {})}`` — so deleting the block turns the loop on rather than off. Task #27
made the turn count itself readable and refused a plan that priced too few
turns. Nothing priced what the extra turn *carries*.

``SandboxRunner._build_reflection`` carries three things of a stated width:

* the last 800 characters of what the code printed;
* the last 800 characters of what it printed as an error;
* the 600-character tail of the failure that stopped it, inserted at the head
  of the blocking errors by ``run``.

2,200 characters is 734 tokens at the plan's three-characters-per-token ratio,
and the plan charges nothing for any of it. Measured against the committed
plan with repair switched on at one attempt, the whole ceiling moves from
368.95 United States dollars to 368.97 — about two pennies. That is small, and
saying so is part of the finding: what is wrong here is a written sentence that
is false in a reachable setting, not a large sum. The amount rises with the
repair budget, because every later turn re-reads every earlier result: 734
tokens an attempt at two turns, 2,202 at three, 4,404 at four.

The prior code is deliberately left out, although the reflection carries up to
4,000 characters of it, because that code is the model's own earlier answer and
``max_input_tokens_per_attempt`` already charges a full ``max_output_tokens``
for every earlier answer. Counting it here would bill the same words twice.

What is counted is a floor, not the largest. The reflection also carries up to
twelve blocking-error lines, up to six warnings, whatever repair guidance the
prompt spec holds, and the whole contract section — none with a fixed width.

Nothing here calls a model, runs a container, or spends anything.
"""

from __future__ import annotations

import copy
import math
import sys
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core.execution_envelope_preflight import (  # noqa: E402
    _check_the_plan_counts_what_the_container_carries_forward,
    _container_carried_forward_characters,
    check_experiment_files_match_conditions,
    conditions_from_plan,
    load_plan,
    run_envelope_preflight,
)
from core.sandbox_runner import (  # noqa: E402
    EXECUTION_ERROR_TAIL_CHARS,
    REFLECTION_STDERR_TAIL_CHARS,
    REFLECTION_STDOUT_TAIL_CHARS,
    SandboxRunner,
    _sanitize_tail,
)

PLAN_PATH = (
    BATCH_RUNNER_ROOT
    / "experiments"
    / "execution_envelope"
    / "advance_check_plan.yaml"
)
CONTAINER_FILE = (
    BATCH_RUNNER_ROOT
    / "experiments"
    / "execution_envelope"
    / "exp031_envelope_docker_container.yaml"
)

WIDTHS_IN_SOURCE = 800 + 800 + 600
FLOOR_AT_THREE_CHARACTERS_A_TOKEN = math.ceil(WIDTHS_IN_SOURCE / 3.0)


def _plan(**assumption_overrides) -> dict:
    plan = load_plan(PLAN_PATH)
    plan["cost"]["assumptions"].update(assumption_overrides)
    return plan


def _container_settings(**sandbox_overrides) -> dict:
    settings = yaml.safe_load(CONTAINER_FILE.read_text(encoding="utf-8"))
    settings = copy.deepcopy(settings)
    settings["execution"]["sandbox"].update(sandbox_overrides)
    return settings


def _repairing_container(max_attempts: int = 1) -> dict:
    return _container_settings(
        repair={"enabled": True, "max_attempts": max_attempts}
    )


def _refusals(settings: dict, plan: dict | None = None) -> list[str]:
    return _check_the_plan_counts_what_the_container_carries_forward(
        {"docker_container": settings}, plan if plan is not None else _plan()
    )


# ── The widths come from the runner, and the runner really applies them ───


def test_the_widths_are_the_runners_own_and_not_typed_again_here():
    """A number quoted in two places is a number that can disagree with itself."""
    widths = _container_carried_forward_characters()
    assert sorted(widths.values()) == sorted(
        [
            REFLECTION_STDOUT_TAIL_CHARS,
            REFLECTION_STDERR_TAIL_CHARS,
            EXECUTION_ERROR_TAIL_CHARS,
        ]
    )


def test_the_three_widths_are_the_ones_the_source_states():
    assert REFLECTION_STDOUT_TAIL_CHARS == 800
    assert REFLECTION_STDERR_TAIL_CHARS == 800
    assert EXECUTION_ERROR_TAIL_CHARS == 600
    assert sum(_container_carried_forward_characters().values()) == 2200


def test_each_width_is_described_so_a_reader_knows_what_it_is():
    """The refusal quotes these, so they have to read as English."""
    for what in _container_carried_forward_characters():
        assert what == what.lower()
        assert len(what.split()) >= 4


def test_the_runner_really_trims_what_the_code_printed_to_that_width():
    """Behaviour, not a string search: hand it too much and count what survives."""
    runner = SandboxRunner(llm_client=None)
    reflection = runner._build_reflection(
        _ContractStub(),
        ["something went wrong"],
        "",
        {"text": "o" * 50_000, "error": ""},
        {"warnings": []},
    )
    assert "o" * REFLECTION_STDOUT_TAIL_CHARS in reflection
    assert "o" * (REFLECTION_STDOUT_TAIL_CHARS + 1) not in reflection


def test_the_runner_really_trims_what_it_printed_as_an_error_to_that_width():
    runner = SandboxRunner(llm_client=None)
    reflection = runner._build_reflection(
        _ContractStub(),
        ["something went wrong"],
        "",
        {"text": "", "error": "e" * 50_000},
        {"warnings": []},
    )
    assert "e" * REFLECTION_STDERR_TAIL_CHARS in reflection
    assert "e" * (REFLECTION_STDERR_TAIL_CHARS + 1) not in reflection


def test_the_failure_that_stopped_it_is_trimmed_to_its_own_width():
    """``run`` puts this at the head of the blocking errors before reflecting."""
    trimmed = _sanitize_tail("x" * 50_000, limit=EXECUTION_ERROR_TAIL_CHARS)
    assert len(trimmed) == EXECUTION_ERROR_TAIL_CHARS


def test_the_default_trim_width_is_the_failure_tail_and_not_a_loose_number():
    assert len(_sanitize_tail("x" * 50_000)) == EXECUTION_ERROR_TAIL_CHARS


# ── The arithmetic ────────────────────────────────────────────────────────


def test_the_floor_is_the_three_widths_divided_by_the_plans_ratio():
    problem = _refusals(_repairing_container())[0]
    assert str(WIDTHS_IN_SOURCE) in problem
    assert str(FLOOR_AT_THREE_CHARACTERS_A_TOKEN) in problem
    assert FLOOR_AT_THREE_CHARACTERS_A_TOKEN == 734


def test_a_part_token_is_charged_as_a_whole_one():
    """2200 / 3 is 733.33, and 733 would be a ceiling that is too low."""
    assert FLOOR_AT_THREE_CHARACTERS_A_TOKEN == 734
    assert "734" in _refusals(_repairing_container())[0]


def test_a_kinder_ratio_lowers_the_floor_rather_than_being_ignored():
    problem = _refusals(
        _repairing_container(), _plan(characters_per_token="4.0")
    )[0]
    assert str(math.ceil(WIDTHS_IN_SOURCE / 4.0)) in problem


def test_a_ratio_that_makes_no_sense_is_left_to_the_rule_that_owns_it():
    """The cost reader already refuses these; saying it twice helps nobody."""
    for nonsense in ("0", "-1", "not a number", None):
        assert (
            _refusals(_repairing_container(), _plan(characters_per_token=nonsense))
            == []
        )


# ── When it fires, and when it stays quiet ────────────────────────────────


def test_a_container_that_asks_once_carries_nothing_and_is_left_alone():
    assert _refusals(_container_settings()) == []


def test_a_container_whose_repair_loop_is_on_is_refused_at_zero():
    problems = _refusals(_repairing_container())
    assert len(problems) == 1
    assert "charges 0 tokens for what a later turn carries" in problems[0]


def test_deleting_the_repair_block_is_enough_to_make_it_fire():
    """The runner turns repair on when the block is absent, not off."""
    settings = _container_settings()
    settings["execution"]["sandbox"].pop("repair")
    assert len(_refusals(settings)) == 1


def test_pricing_it_at_the_floor_settles_the_rule():
    plan = _plan(
        max_tool_result_tokens_per_turn={
            "host_python_process": 0,
            "docker_container": FLOOR_AT_THREE_CHARACTERS_A_TOKEN,
            "azure_code_interpreter": 5000,
        }
    )
    assert _refusals(_repairing_container(), plan) == []


def test_pricing_it_above_the_floor_is_allowed():
    """A plan may be more careful than the settings; it may not be less."""
    plan = _plan(
        max_tool_result_tokens_per_turn={
            "host_python_process": 0,
            "docker_container": 50_000,
            "azure_code_interpreter": 5000,
        }
    )
    assert _refusals(_repairing_container(), plan) == []


def test_pricing_it_one_token_short_is_not_allowed():
    plan = _plan(
        max_tool_result_tokens_per_turn={
            "host_python_process": 0,
            "docker_container": FLOOR_AT_THREE_CHARACTERS_A_TOKEN - 1,
            "azure_code_interpreter": 5000,
        }
    )
    assert len(_refusals(_repairing_container(), plan)) == 1


def test_switching_repair_off_again_is_a_real_way_to_satisfy_the_check():
    """Two ways out, and turning the loop off is the honest one for this run."""
    assert _refusals(_container_settings(repair={"enabled": False})) == []


def test_a_bigger_repair_budget_still_gets_one_refusal_naming_its_turns():
    problems = _refusals(_repairing_container(max_attempts=3))
    assert len(problems) == 1
    assert "ask for the code 4 times" in problems[0]


def test_a_run_place_that_is_not_a_container_is_not_looked_at():
    settings = _container_settings()
    settings["execution"]["mode"] = "subprocess"
    assert _refusals(settings) == []


def test_a_place_the_plan_prices_nothing_for_is_left_to_the_cost_reader():
    plan = _plan(
        max_tool_result_tokens_per_turn={
            "host_python_process": 0,
            "azure_code_interpreter": 5000,
        }
    )
    assert _refusals(_repairing_container(), plan) == []


# ── What is deliberately not counted ──────────────────────────────────────


def test_the_prior_code_is_not_added_to_the_figure():
    """It is the model's own earlier answer, already charged as output.

    ``max_input_tokens_per_attempt`` bills a full ``max_output_tokens`` for
    every answer an earlier turn wrote. The reflection's copy of that code is
    those same words coming back, so adding its 4,000 characters here would
    charge for them twice and make the ceiling look better founded than it is.
    """
    assert 4000 not in _container_carried_forward_characters().values()
    assert sum(_container_carried_forward_characters().values()) == 2200
    assert "4000" not in _refusals(_repairing_container())[0]


def test_the_source_still_carries_the_prior_code_at_that_width():
    """If this ever stopped being true the reasoning above would need redoing."""
    source = (BATCH_RUNNER_ROOT / "core" / "sandbox_runner.py").read_text(
        encoding="utf-8"
    )
    assert "if code and len(code) <= 4000:" in source


def test_a_full_earlier_answer_is_worth_more_than_the_code_the_prompt_carries():
    """The reason the code may be left out: output already covers it, and more."""
    plan = load_plan(PLAN_PATH)
    conditions = plan["model_run_conditions"]["shared"]
    ratio = Decimal(str(plan["cost"]["assumptions"]["characters_per_token"]))
    assert int(conditions["max_output_tokens"]) > math.ceil(4000 / float(ratio))


def test_the_refusal_says_out_loud_that_it_is_only_a_floor():
    problem = _refusals(_repairing_container())[0]
    assert "that is a floor" in problem
    for unbounded in ("blocking-error", "warnings", "repair guidance", "contract"):
        assert unbounded in problem


def test_the_unbounded_parts_are_really_in_the_prompt_the_runner_builds():
    """The floor caveat has to name things that are there, not things imagined."""
    source = (BATCH_RUNNER_ROOT / "core" / "sandbox_runner.py").read_text(
        encoding="utf-8"
    )
    assert "blocking_errors[:12]" in source
    assert "warnings[:6]" in source
    assert "repair_guidance" in source
    assert "contract.to_prompt_section()" in source


# ── The committed plan and the committed container file ───────────────────


def test_the_committed_plan_and_container_file_pass_this_rule_today():
    """Because repair is off in the file, not because the plan priced it."""
    settings = yaml.safe_load(CONTAINER_FILE.read_text(encoding="utf-8"))
    assert settings["execution"]["sandbox"]["repair"]["enabled"] is False
    assert _refusals(settings) == []


def test_the_plan_still_prices_the_container_at_nothing():
    plan = load_plan(PLAN_PATH)
    carried = plan["cost"]["assumptions"]["max_tool_result_tokens_per_turn"]
    assert carried["docker_container"] == 0


def test_the_whole_free_check_is_unchanged_by_this_rule_today():
    result = run_envelope_preflight(load_plan(PLAN_PATH), root=BATCH_RUNNER_ROOT)
    assert not any(
        "what a later turn carries" in problem for problem in result.all_problems
    )
    assert result.may_start is False


def test_the_rule_is_reached_by_the_free_check_and_not_only_by_this_file(tmp_path):
    """A rule nobody calls refuses nothing.

    Every other test here calls the rule directly, which proves the rule works
    and proves nothing about whether the free check runs it. So this one copies
    the plan's own settings files somewhere writable, switches the container's
    repair loop on there, and asks the free check the way a person would.
    """
    plan = load_plan(PLAN_PATH)
    copied = tmp_path / "experiments" / "execution_envelope"
    copied.mkdir(parents=True)
    for relative in plan["experiment_files"].values():
        source = BATCH_RUNNER_ROOT / relative
        (tmp_path / relative).write_text(
            source.read_text(encoding="utf-8"), encoding="utf-8"
        )

    container = tmp_path / plan["experiment_files"]["docker_container"]
    settings = yaml.safe_load(container.read_text(encoding="utf-8"))
    settings["execution"]["sandbox"]["repair"] = {
        "enabled": True,
        "max_attempts": 1,
    }
    container.write_text(yaml.safe_dump(settings), encoding="utf-8")

    problems = check_experiment_files_match_conditions(
        plan, conditions_from_plan(plan), root=tmp_path
    )
    assert any("what a later turn carries" in problem for problem in problems)


def test_the_free_check_stays_quiet_on_the_same_files_left_alone(tmp_path):
    """The other half of the test above: it is the repair line that fires it."""
    plan = load_plan(PLAN_PATH)
    (tmp_path / "experiments" / "execution_envelope").mkdir(parents=True)
    for relative in plan["experiment_files"].values():
        (tmp_path / relative).write_text(
            (BATCH_RUNNER_ROOT / relative).read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    problems = check_experiment_files_match_conditions(
        plan, conditions_from_plan(plan), root=tmp_path
    )
    assert not any("what a later turn carries" in problem for problem in problems)


def test_the_plan_no_longer_says_nothing_is_carried_forward():
    """The sentence that talked the reader out of checking is gone."""
    text = PLAN_PATH.read_text(encoding="utf-8")
    assert "the model is asked once and nothing is carried forward" not in text


def test_the_plan_says_what_makes_the_zero_true_and_what_would_end_it():
    text = PLAN_PATH.read_text(encoding="utf-8")
    for expected in ("repair", "sandbox_runner.py", "800", "600", "734"):
        assert expected in text


class _ContractStub:
    """Stands in for a deliverable contract, which this rule never reads."""

    def to_prompt_section(self) -> str:
        return "[CONTRACT]"


@pytest.mark.parametrize("budget,expected_turns", [(1, 2), (2, 3), (3, 4)])
def test_the_refusal_names_the_turn_count_the_settings_really_allow(
    budget, expected_turns
):
    problems = _refusals(_repairing_container(max_attempts=budget))
    assert f"ask for the code {expected_turns} times" in problems[0]
