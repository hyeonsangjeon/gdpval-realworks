"""How much one marking call carries is read from the tool, not assumed away.

The cost sum prices marking as a flat ``grading_input_tokens_per_call``
multiplied by how many calls there are. Until this was written, that number was
an average of runs that had happened, and both the plan and
``core/execution_envelope_grading_cost.py`` said in writing that no settings
file could pin it down — that it "depends on how long the answer being marked
turns out to be, and nothing in the settings caps that".

Something does. The judge never sees the answer whole. It asks for pieces
through ``read_deliverable``, and:

* ``core/tools/read_deliverable.py`` ends every content read with
  ``text[:MAX_CONTENT_CHARS]``, so one result is at most 200,000 characters;
* ``judge.tools.read_deliverable.per_item_call_cap`` says how many results may
  be fetched for one scoring line — 8 in the committed settings;
* ``core/tool_calling_judge.py`` appends each result to ``messages`` as
  ``json.dumps(result)`` with no truncation, and every later turn sends
  ``messages`` again.

So one call can be carrying 8 × 200,000 characters — 533,334 tokens at the
plan's three-characters-per-token ratio. The plan priced 10,000, which is 1.87
per cent of it. Measured before this was written: leaving the flat number in
place puts the whole ceiling at 363.58 United States dollars, and raising it to
what the settings permit puts it at 7,568.42 — 7,204.84 dollars the plan called
impossible and the settings allow.

What is *not* counted here is the wording the conversation opens with. Nothing
caps that, so the figure this rule demands is a floor on the true largest, and
the tests below pin that it is described as a floor rather than as the answer.

Nothing here calls a model, marks anything, or spends anything.
"""

from __future__ import annotations

import inspect
import math
import sys
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core.execution_envelope_cost import CostAssumptions  # noqa: E402
from core.execution_envelope_grading_cost import (  # noqa: E402
    GradingCaps,
    check_assumptions_cover_the_caps,
    read_grading_caps,
)
from core.execution_envelope_preflight import (  # noqa: E402
    load_plan,
    run_envelope_preflight,
)
from core.tool_calling_judge import ToolCallingJudge  # noqa: E402
from core.tools.read_deliverable import MAX_CONTENT_CHARS  # noqa: E402

PLAN_PATH = (
    BATCH_RUNNER_ROOT / "experiments" / "execution_envelope" / "advance_check_plan.yaml"
)
COMMITTED_MARKING_SETTINGS = (
    BATCH_RUNNER_ROOT / "grading_configs" / "default_v2.yaml"
)

THREE = Decimal("3.0")


def _caps(**overrides) -> GradingCaps:
    base = GradingCaps(
        settings_path="marking.yaml",
        judge_model="a-marking-model",
        judge_calls_per_rubric_item=11,
        tool_calls_per_rubric_item=8,
        characters_per_tool_result=MAX_CONTENT_CHARS,
        output_tokens_per_call=2400,
        standing_instructions_path="prompts/grader_judge_v2.md",
        characters_of_standing_instructions=6000,
        characters_of_task_prompt_preview=500,
        task_prompt_preview_setting=500,
        visual_model=None,
        visual_calls_per_task=0,
        audio_model=None,
        audio_calls_per_task=0,
    )
    return GradingCaps(**{**base.__dict__, **overrides})


def _assumptions(**overrides) -> CostAssumptions:
    raw = {
        "characters_per_token": "3.0",
        "instruction_character_count": 100,
        "tool_loop_max_model_turns": {"host_python_process": 1},
        "output_tokens_capped_per_attempt": {"host_python_process": False},
        "max_tool_result_tokens_per_turn": {"host_python_process": 0},
        "safety_multiplier": "1.25",
        "grading_required": True,
        "grading_model": "a-marking-model",
        "grading_calls_per_rubric_item": 11,
        "grading_input_tokens_per_call": _caps().input_tokens_one_call_must_cover(
            THREE
        ),
        "grading_output_tokens_per_call": 2400,
    }
    raw.update(overrides)
    return CostAssumptions.from_mapping(raw)


def _refusals(caps: GradingCaps, **assumption_overrides) -> list[str]:
    return [
        problem
        for problem in check_assumptions_cover_the_caps(
            _assumptions(**assumption_overrides), caps
        )
        if "input per marking call" in problem
    ]


# ── The arithmetic, read off the tool and the settings ────────────────────


def test_the_results_that_can_pile_up_are_counted_at_full_width():
    """Eight results, each the width of the door, all still in the last call."""
    carried = _caps().input_tokens_carried_by_tool_results(THREE)
    assert carried == math.ceil(8 * MAX_CONTENT_CHARS / 3.0)


def test_a_lower_tool_call_cap_carries_less():
    """The settings lever an operator actually has."""
    assert _caps(tool_calls_per_rubric_item=1).input_tokens_carried_by_tool_results(
        THREE
    ) == math.ceil(MAX_CONTENT_CHARS / 3.0)


def test_a_setting_that_allows_no_tool_calls_carries_nothing():
    assert _caps(tool_calls_per_rubric_item=0).input_tokens_carried_by_tool_results(
        THREE
    ) == 0


def test_a_fatter_token_carries_fewer_of_them():
    """The ratio is the plan's, so the check moves when the plan's ratio does."""
    at_three = _caps().input_tokens_carried_by_tool_results(THREE)
    at_six = _caps().input_tokens_carried_by_tool_results(Decimal("6.0"))
    assert at_six == math.ceil(at_three / 2)


def test_a_part_token_is_charged_as_a_whole_one():
    """Decimal's ``//`` truncates towards zero, which would round a ceiling down."""
    carried = _caps(
        tool_calls_per_rubric_item=1, characters_per_tool_result=10
    ).input_tokens_carried_by_tool_results(THREE)
    assert carried == 4, "10 / 3 is 3.33, and a third of a token still costs one"


# ── The numbers come from the source, not from this file ──────────────────


def test_the_width_of_one_result_is_read_from_the_tool_that_returns_it():
    read = read_grading_caps(COMMITTED_MARKING_SETTINGS)
    assert read.characters_per_tool_result == MAX_CONTENT_CHARS


def test_the_tool_really_does_cut_content_at_that_width():
    """The cap is only a cap because the tool applies it. This is that line.

    Read out of the source rather than exercised, because exercising it would
    mean building a 200,000-character document on disk for no extra certainty.
    """
    source = inspect.getsource(
        sys.modules["core.tools.read_deliverable"]
    )
    assert "text = text[:MAX_CONTENT_CHARS]" in source


def test_the_judge_puts_the_whole_result_into_the_conversation():
    """If the judge trimmed results, the pile-up would not be the real ceiling."""
    source = inspect.getsource(ToolCallingJudge._function_call_output_message)
    assert "json.dumps(result)" in source
    assert "[:" not in source, "a slice here would mean the result is trimmed"


def test_how_many_results_may_pile_up_is_the_settings_own_number():
    read = read_grading_caps(COMMITTED_MARKING_SETTINGS)
    document = yaml.safe_load(
        COMMITTED_MARKING_SETTINGS.read_text(encoding="utf-8")
    )
    written = document["judge"]["tools"]["read_deliverable"]["per_item_call_cap"]
    assert read.tool_calls_per_rubric_item == written


# ── The refusal itself ────────────────────────────────────────────────────


def test_a_sum_that_covers_the_pile_up_is_left_alone():
    assert _refusals(_caps()) == []


def test_a_sum_below_the_pile_up_is_refused():
    problems = _refusals(_caps(), grading_input_tokens_per_call=10_000)
    assert len(problems) == 1
    assert "allows 10000 tokens of input" in problems[0]
    assert "8 tool results" in problems[0]
    assert str(MAX_CONTENT_CHARS) in problems[0]
    assert "533334" in problems[0]


def test_the_refusal_says_what_is_still_missing_from_that_number():
    """A reader must not take the demanded figure for the whole story.

    The instructions and the task preview are in the figure now. The scoring
    line being judged is not, because nothing caps it, and the refusal has to
    keep saying so — otherwise a plan that clears the figure reads as proved
    when it has only cleared a floor.
    """
    problems = _refusals(_caps(), grading_input_tokens_per_call=1)
    assert "still a floor" in problems[0]
    assert "the scoring line being judged is not capped by anything" in problems[0]


def test_a_sum_above_the_pile_up_is_allowed():
    """A plan may be more careful than its settings. It may not be less."""
    assert _refusals(_caps(), grading_input_tokens_per_call=10_000_000) == []


def test_lowering_the_tool_call_cap_is_a_real_way_to_satisfy_the_check():
    """The complaint is answerable by bounding the run, not only by paying more.

    An operator who cannot afford the ceiling can shrink what marking is
    allowed to fetch. That has to actually work, or the check is a wall rather
    than a choice.
    """
    at_eight = _refusals(_caps(), grading_input_tokens_per_call=70_000)
    at_one = _refusals(
        _caps(tool_calls_per_rubric_item=1), grading_input_tokens_per_call=70_000
    )
    assert len(at_eight) == 1
    assert at_one == []


def test_a_plan_that_marks_nothing_is_not_asked():
    assert _refusals(_caps(), grading_required=False) == []


# ── The committed plan, and the amount that was hidden ────────────────────


def test_the_committed_plan_is_refused_by_this_rule_today():
    """The finding this task exists for. It is open, and it is meant to be."""
    plan = load_plan(PLAN_PATH)
    result = run_envelope_preflight(plan, root=BATCH_RUNNER_ROOT)

    matching = [p for p in result.problems if "input per marking call" in p]
    assert len(matching) == 1
    assert "533334" in matching[0]


@pytest.mark.parametrize("raised_to", [535_589, 1_000_000])
def test_raising_the_number_to_the_limit_settles_this_rule(raised_to):
    """535589 is the whole demand: 533334 of tool results, 2255 of opening."""
    plan = load_plan(PLAN_PATH)
    plan["cost"]["assumptions"]["grading_input_tokens_per_call"] = raised_to
    result = run_envelope_preflight(plan, root=BATCH_RUNNER_ROOT)

    assert [p for p in result.problems if "input per marking call" in p] == []


def test_what_the_flat_number_was_keeping_off_the_ceiling():
    """Not a complaint about tidiness. It is thousands of dollars.

    The plan's own approved maximum is 32.23. The figures here are what the
    check would put in front of somebody being asked to approve a run.
    """
    plan = load_plan(PLAN_PATH)
    as_written = run_envelope_preflight(plan, root=BATCH_RUNNER_ROOT).cost.total_usd

    plan["cost"]["assumptions"]["grading_input_tokens_per_call"] = (
        read_grading_caps(COMMITTED_MARKING_SETTINGS)
        .input_tokens_carried_by_tool_results(THREE)
    )
    at_the_limit = run_envelope_preflight(
        plan, root=BATCH_RUNNER_ROOT
    ).cost.total_usd

    assert at_the_limit > as_written * 20, (
        f"as written {as_written}, at the limit {at_the_limit}"
    )


def test_the_plan_no_longer_claims_the_number_cannot_be_pinned():
    """The sentence that was wrong must not survive next to the fix.

    A comment saying no settings file can pin this down, sitting above a number
    a settings file pins down, is how the next reader gets talked out of
    checking.
    """
    text = PLAN_PATH.read_text(encoding="utf-8")
    assert "no settings file can pin down" not in text
