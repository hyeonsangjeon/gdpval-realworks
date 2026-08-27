"""Tests for the stage-one cost ceiling and the limit that enforces it.

Two separate things are being held in place here.

The first is a correction. The shared cost arithmetic used to charge one turn's
input once per model call, which is right when each attempt is a fresh request
and wrong when the model is asked again after each tool result. These tests
require the corrected count to leave the single-turn run places untouched, and
to charge a loop more than the old count did.

The second is the stage-one work itself: what a run where the model chooses its
own next action could cost, where the limits it is priced against come from,
and the refusals that keep it from starting.
"""

from __future__ import annotations

import copy
import dataclasses
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

from core.agentic_v2_stage_one_budget import (  # noqa: E402
    STAGE_ONE_PLAN_PATH,
    DispatcherLimits,
    StageOneBudget,
    StageOneBudgetExceeded,
    StageOneConditions,
    budget_for_one_task,
    check_stage_one_cannot_reach_a_model,
    load_stage_one_plan,
    price_the_options,
    read_dispatcher_limits,
    run_stage_one_preflight,
    stage_one_ceiling,
    tool_result_tokens_ceiling,
)
from core.agentic_v2_tools import AgenticV2ToolDispatcher  # noqa: E402
from core.execution_envelope_cost import (  # noqa: E402
    CostAssumptions,
    ModelPrice,
    estimate_cost_ceiling,
    max_attempt_counts,
    max_input_tokens_per_attempt,
)
from core.execution_envelope_preflight import (  # noqa: E402
    conditions_from_plan,
    load_plan,
)
from core.execution_envelope_tasks import load_task_catalog  # noqa: E402
from core.execution_environment_readiness import (  # noqa: E402
    SERVING_PATH_MICROSOFT_FOUNDRY_DEPLOYMENT,
    ModelRunConditions,
)

SHARED_PLAN_PATH = (
    BATCH_RUNNER_ROOT
    / "experiments"
    / "execution_envelope"
    / "advance_check_plan.yaml"
)
STAGE_ONE_SCRIPT = (
    BATCH_RUNNER_ROOT / "scripts" / "check_agentic_stage_one_ceiling.py"
)

ONLY_TASK = "02aa1805-c658-4069-8a6a-02dec146063a"


@pytest.fixture(scope="module")
def catalog():
    return load_task_catalog()


@pytest.fixture(scope="module")
def shared_plan():
    return load_plan(SHARED_PLAN_PATH)


@pytest.fixture(scope="module")
def assumptions(shared_plan):
    return CostAssumptions.from_mapping(shared_plan["cost"]["assumptions"])


@pytest.fixture
def stage_one_plan():
    return load_stage_one_plan(STAGE_ONE_PLAN_PATH)


def _assumptions(**overrides) -> CostAssumptions:
    base = {
        "characters_per_token": 3,
        "instruction_character_count": 0,
        "tool_loop_max_model_turns": {"a_place": 1},
        "output_tokens_capped_per_attempt": {"a_place": False},
        "max_tool_result_tokens_per_turn": {"a_place": 0},
        "safety_multiplier": 1,
        "grading_required": False,
        "grading_model": "gpt-5.4",
        "grading_calls_per_rubric_item": 1,
        "grading_input_tokens_per_call": 1,
        "grading_output_tokens_per_call": 1,
    }
    base.update(overrides)
    return CostAssumptions.from_mapping(base)


def _conditions(**overrides) -> ModelRunConditions:
    base = {
        "provider": "azure",
        "resource": "hjeon-fdpo-foundry-eus2",
        "deployment": "gpt-5.4",
        "resolved_model": "gpt-5.4",
        "api_version": "2025-04-01-preview",
        "model_serving_path": SERVING_PATH_MICROSOFT_FOUNDRY_DEPLOYMENT,
        "system_instruction": "a",
        "task_instruction": "b",
        "task_ids": [ONLY_TASK],
        "input_file_versions": {},
        "max_output_tokens": 1000,
        "per_task_timeout_seconds": 60,
        "self_review_enabled": False,
        "self_review_max_attempts": 0,
        "retry_reasons_allowed": ["infrastructure_error"],
        "retry_max_attempts": 0,
        "automatic_model_switch_allowed": False,
        "automatic_fallback_allowed": False,
        "unsupported_runner_substitution_allowed": False,
    }
    base.update(overrides)
    return ModelRunConditions.from_mapping(base)


# ── The correction: a conversation that grows is charged as one ────────────


def test_one_turn_per_attempt_still_sends_only_the_base_input():
    """The correction must not move the two single-turn run places at all.

    They send the same thing every time they are asked, so every term the
    correction adds has to come out as nothing. If this ever fails, a change
    meant for loops has leaked into places that do not loop.
    """
    for capped in (True, False):
        for tool_result_tokens in (0, 21846):
            assert (
                max_input_tokens_per_attempt(
                    base_input_tokens=17_000,
                    tool_loop_max_model_turns=1,
                    max_output_tokens=32_768,
                    output_tokens_capped_per_attempt=capped,
                    max_tool_result_tokens_per_turn=tool_result_tokens,
                )
                == 17_000
            )


def test_a_loop_is_charged_more_than_one_turn_times_the_number_of_turns():
    """The old count multiplied a constant. The new one must exceed it.

    This is the whole correction in one line: eight turns of a conversation
    cost more than eight copies of its first turn, because the later turns
    re-read what the earlier ones produced.
    """
    base = 17_000
    turns = 8
    old_count = base * turns

    new_count = max_input_tokens_per_attempt(
        base_input_tokens=base,
        tool_loop_max_model_turns=turns,
        max_output_tokens=32_768,
        output_tokens_capped_per_attempt=True,
        max_tool_result_tokens_per_turn=5_000,
    )

    assert new_count > old_count
    # Seven later turns re-read the whole answer, and the tool results build up
    # over twenty-eight turn pairs.
    assert new_count == old_count + 7 * 32_768 + 28 * 5_000


def test_doubling_the_turns_more_than_doubles_what_tool_results_cost():
    """Tool results build up, so their cost grows faster than the turn count.

    This is the property that makes a long loop expensive in a way people do
    not expect, and the reason the stage-one table exists.
    """

    def tool_result_part(turns: int) -> int:
        with_results = max_input_tokens_per_attempt(
            base_input_tokens=1_000,
            tool_loop_max_model_turns=turns,
            max_output_tokens=0,
            output_tokens_capped_per_attempt=True,
            max_tool_result_tokens_per_turn=5_000,
        )
        without = max_input_tokens_per_attempt(
            base_input_tokens=1_000,
            tool_loop_max_model_turns=turns,
            max_output_tokens=0,
            output_tokens_capped_per_attempt=True,
            max_tool_result_tokens_per_turn=0,
        )
        return with_results - without

    assert tool_result_part(16) > 2 * tool_result_part(8)
    assert tool_result_part(16) == pytest.approx(
        4 * tool_result_part(8), rel=0.2
    )


def test_a_fresh_cap_each_turn_costs_more_than_one_cap_for_the_attempt():
    """Where each turn may write a full answer, each turn's answer is re-read."""
    per_attempt = max_input_tokens_per_attempt(
        base_input_tokens=1_000,
        tool_loop_max_model_turns=8,
        max_output_tokens=4_096,
        output_tokens_capped_per_attempt=True,
        max_tool_result_tokens_per_turn=0,
    )
    per_turn = max_input_tokens_per_attempt(
        base_input_tokens=1_000,
        tool_loop_max_model_turns=8,
        max_output_tokens=4_096,
        output_tokens_capped_per_attempt=False,
        max_tool_result_tokens_per_turn=0,
    )
    assert per_turn > per_attempt


def test_a_turn_count_below_one_is_refused():
    with pytest.raises(ValueError, match="at least once"):
        max_input_tokens_per_attempt(
            base_input_tokens=1,
            tool_loop_max_model_turns=0,
            max_output_tokens=1,
            output_tokens_capped_per_attempt=True,
            max_tool_result_tokens_per_turn=0,
        )


def test_a_negative_tool_result_size_is_refused():
    with pytest.raises(ValueError, match="shorter than nothing"):
        max_input_tokens_per_attempt(
            base_input_tokens=1,
            tool_loop_max_model_turns=2,
            max_output_tokens=1,
            output_tokens_capped_per_attempt=True,
            max_tool_result_tokens_per_turn=-1,
        )
    with pytest.raises(ValueError, match="shorter than nothing"):
        _assumptions(max_tool_result_tokens_per_turn={"a_place": -1})


def test_a_run_place_with_no_written_tool_result_size_is_refused(catalog):
    """An unstated guess is how a ceiling ends up wrong in the costly direction.

    Leaving the number out must stop the count rather than quietly standing in
    a zero, which would price a loop as though nothing were carried forward.
    """
    assumptions = _assumptions(
        tool_loop_max_model_turns={"a_place": 4},
        output_tokens_capped_per_attempt={"a_place": True},
        max_tool_result_tokens_per_turn={"a_different_place": 0},
    )
    with pytest.raises(ValueError, match="how much one tool result may add"):
        estimate_cost_ceiling(
            conditions_by_environment={"a_place": _conditions()},
            tasks_by_id=catalog.by_task_id(),
            assumptions=assumptions,
        )


def test_the_attempt_count_separates_looping_attempts_from_single_calls():
    """The input side needs to know which calls carry a conversation forward.

    A self-review's first call looks at a finished answer and starts nothing,
    so it must not be charged as though it were a whole loop.
    """
    counts = max_attempt_counts(
        _conditions(
            retry_max_attempts=3,
            self_review_enabled=True,
            self_review_max_attempts=2,
        ),
        tool_loop_max_model_turns=8,
        output_tokens_capped_per_attempt=True,
    )
    assert counts.looping_attempts == 4 + 2
    assert counts.single_turn_calls == 2
    assert counts.model_calls == 4 * 8 + 2 * (1 + 8)


def test_the_single_turn_places_in_the_committed_plan_are_unchanged(
    shared_plan, assumptions, catalog
):
    """The two places that ask once must cost exactly what they always did.

    Guarded against the committed plan rather than a made-up one, because the
    committed plan is what would actually be billed.
    """
    shared = shared_plan["model_run_conditions"]["shared"]
    conditions = conditions_from_plan(shared_plan)["host_python_process"]
    ceiling = estimate_cost_ceiling(
        conditions_by_environment={"host_python_process": conditions},
        tasks_by_id=catalog.by_task_id(),
        assumptions=assumptions,
    )
    entry = ceiling.environments[0]
    for task in entry.tasks:
        # One turn per attempt, so what one attempt sends is what one call
        # sends, and the total is simply that once per call.
        assert task.input_tokens_per_attempt == task.input_tokens_per_call
        assert task.total_input_tokens == (
            task.input_tokens_per_call * task.model_calls
        )


def test_the_committed_plan_no_longer_fits_inside_the_approved_amount(
    shared_plan, assumptions, catalog
):
    """The approved amount was worked out with the mistake in place.

    32.23 United States dollars was approved on 2026-08-25, when the Azure run
    place was priced by charging its first turn's input eight times. Counting
    the conversation as it grows raises the whole run above that line, so the
    free check must now refuse.

    Nothing was spent under the wrong figure — the Azure run place has never
    been reachable — but the run could have been allowed to start and then
    billed more than was approved.

    This test exists so that the correction cannot be undone quietly. If the
    ceiling ever drops back below the approved amount, either the arithmetic
    was reverted or the plan was changed, and both deserve to be noticed.
    """
    from core.execution_envelope_cost import check_cost_ceiling

    conditions = conditions_from_plan(shared_plan)["host_python_process"]
    ceiling = estimate_cost_ceiling(
        conditions_by_environment={
            place: conditions
            for place in (
                "host_python_process",
                "docker_container",
                "azure_code_interpreter",
            )
        },
        tasks_by_id=catalog.by_task_id(),
        assumptions=assumptions,
    )

    approved = Decimal(str(shared_plan["cost"]["approved_maximum_usd"]))
    assert approved == Decimal("32.23")
    assert ceiling.total_usd > approved

    problems = check_cost_ceiling(ceiling, approved_maximum_usd=approved)
    assert any("is above the" in note for note in problems)


def test_the_plan_says_the_approved_amount_no_longer_covers_the_ceiling():
    """A reader of the plan must be told, not left to work it out."""
    text = SHARED_PLAN_PATH.read_text(encoding="utf-8")
    assert "no longer covers the worked-out ceiling" in text


# ── Where the stage-one limits come from ───────────────────────────────────


def test_the_dispatcher_limits_are_read_from_the_dispatcher():
    """Read from the code, not restated, so the two cannot disagree."""
    limits = read_dispatcher_limits()
    defaults = {
        entry.name: entry.default
        for entry in dataclasses.fields(AgenticV2ToolDispatcher)
    }
    assert limits.max_total_calls == defaults["max_total_calls"]
    assert limits.max_result_bytes == defaults["max_result_bytes"]


def test_a_tool_result_is_priced_at_the_size_the_dispatcher_allows():
    limits = DispatcherLimits(max_total_calls=32, max_result_bytes=65_536)
    assert (
        tool_result_tokens_ceiling(limits, characters_per_token=Decimal(3))
        == 21_846
    )


def test_a_lower_dispatcher_ceiling_lowers_the_bill(catalog, assumptions):
    """Tightening the dispatcher must show up in the price without an edit here."""

    def cost_with(max_result_bytes: int) -> Decimal:
        return stage_one_ceiling(
            conditions=_stage_one_conditions(),
            tasks_by_id=catalog.by_task_id(),
            assumptions=assumptions,
            limits=DispatcherLimits(
                max_total_calls=32, max_result_bytes=max_result_bytes
            ),
        ).total_usd

    assert cost_with(8_192) < cost_with(65_536)


def _stage_one_conditions(**overrides) -> StageOneConditions:
    base = {
        "deployment": "gpt-5.4",
        "resource": "hjeon-fdpo-foundry-eus2",
        "resolved_model": "gpt-5.4",
        "task_ids": (ONLY_TASK,),
        "tool_calls_per_attempt": 8,
        "max_output_tokens_per_turn": 4_096,
        "retry_max_attempts": 1,
        "per_task_timeout_seconds": 1_200,
    }
    base.update(overrides)
    return StageOneConditions(**base)


def test_more_tool_calls_than_the_dispatcher_allows_is_refused():
    limits = DispatcherLimits(max_total_calls=32, max_result_bytes=65_536)
    with pytest.raises(ValueError, match="could never happen"):
        _stage_one_conditions(tool_calls_per_attempt=33).validated(limits)


def test_a_turn_that_may_write_nothing_is_refused():
    limits = DispatcherLimits(max_total_calls=32, max_result_bytes=65_536)
    with pytest.raises(ValueError, match="cannot produce an answer"):
        _stage_one_conditions(max_output_tokens_per_turn=0).validated(limits)


def test_stage_one_never_switches_self_review_on():
    """Stage one asks one question, so nothing else may be running beside it."""
    conditions = _stage_one_conditions().as_run_conditions()
    assert conditions.self_review_enabled is False
    assert conditions.self_review_max_attempts == 0
    assert conditions.automatic_model_switch_allowed is False


def test_candidates_the_dispatcher_would_refuse_are_left_out(
    catalog, assumptions
):
    """A reader must never be offered a setting that could not be taken."""
    options = price_the_options(
        base=_stage_one_conditions(),
        tasks_by_id=catalog.by_task_id(),
        assumptions=assumptions,
        tool_call_choices=(4, 64),
        output_token_choices=(2_048,),
        limits=DispatcherLimits(max_total_calls=32, max_result_bytes=65_536),
    )
    assert [entry.tool_calls_per_attempt for entry in options] == [4]


def test_more_turns_cost_more_and_marking_stays_the_same(catalog, assumptions):
    """Only the running column may move when the settings change."""
    options = price_the_options(
        base=_stage_one_conditions(),
        tasks_by_id=catalog.by_task_id(),
        assumptions=dataclasses.replace(assumptions, grading_required=True),
        tool_call_choices=(4, 8),
        output_token_choices=(2_048,),
    )
    cheap, dear = options
    assert dear.most_running_could_cost_usd > cheap.most_running_could_cost_usd
    assert (
        dear.most_grading_could_cost_usd == cheap.most_grading_could_cost_usd
    )


def test_the_dispatcher_default_settings_are_far_dearer_than_a_small_run(
    catalog, assumptions
):
    """The finding that makes the table worth printing.

    Running stage one at the dispatcher's own default of thirty-two tool calls,
    with the answer-length cap the three-place comparison uses, costs many
    times what a short loop with a small cap costs. Somebody who did not look
    would reasonably assume the defaults were a sensible starting point.
    """
    options = price_the_options(
        base=_stage_one_conditions(),
        tasks_by_id=catalog.by_task_id(),
        assumptions=assumptions,
        tool_call_choices=(4, 32),
        output_token_choices=(2_048, 32_768),
    )
    by_setting = {
        (entry.tool_calls_per_attempt, entry.max_output_tokens_per_turn): entry
        for entry in options
    }
    small = by_setting[(4, 2_048)].most_running_could_cost_usd
    defaults = by_setting[(32, 32_768)].most_running_could_cost_usd
    assert defaults > small * 20


# ── The limit that is enforced while something runs ────────────────────────


def test_a_budget_permits_a_call_while_it_has_room():
    budget = StageOneBudget(
        max_model_calls=2, max_input_tokens=100, max_output_tokens=100
    )
    assert budget.refusal_before_next_call() is None
    budget.record(input_tokens=10, output_tokens=10)
    assert budget.refusal_before_next_call() is None


@pytest.mark.parametrize(
    "limits,used,expected",
    [
        ({"max_model_calls": 1}, {}, "model calls"),
        ({"max_input_tokens": 10}, {"input_tokens": 10}, "already sent"),
        ({"max_output_tokens": 10}, {"output_tokens": 10}, "already been sent back"),
    ],
)
def test_a_budget_refuses_the_next_call_at_each_ceiling(limits, used, expected):
    """Refused before the call, because after it the money is gone."""
    settings = {
        "max_model_calls": 100,
        "max_input_tokens": 1_000,
        "max_output_tokens": 1_000,
    }
    settings.update(limits)
    budget = StageOneBudget(**settings)
    budget.record(
        input_tokens=used.get("input_tokens", 0),
        output_tokens=used.get("output_tokens", 0),
    )

    refusal = budget.refusal_before_next_call()

    assert refusal is not None
    assert expected in refusal


def test_spending_more_than_allowed_raises_rather_than_reporting_quietly():
    """A loop that has overspent has lost the thread; the safe move is to stop."""
    budget = StageOneBudget(
        max_model_calls=10, max_input_tokens=100, max_output_tokens=100
    )
    with pytest.raises(StageOneBudgetExceeded, match="tokens sent against"):
        budget.record(input_tokens=101, output_tokens=0)


def test_a_budget_refuses_settings_that_are_not_whole_numbers():
    with pytest.raises(ValueError, match="whole number"):
        StageOneBudget(
            max_model_calls=True, max_input_tokens=1, max_output_tokens=1
        )
    budget = StageOneBudget(
        max_model_calls=1, max_input_tokens=1, max_output_tokens=1
    )
    with pytest.raises(ValueError, match="whole number"):
        budget.record(input_tokens=1.5, output_tokens=0)


def test_the_running_limit_comes_from_the_worked_out_ceiling(
    catalog, assumptions
):
    """The limit and the approved figure must not be able to drift apart."""
    ceiling = stage_one_ceiling(
        conditions=_stage_one_conditions(),
        tasks_by_id=catalog.by_task_id(),
        assumptions=assumptions,
    )
    priced = ceiling.environments[0].tasks[0]

    budget = budget_for_one_task(ceiling, ONLY_TASK)

    assert budget.max_model_calls == priced.model_calls
    assert budget.max_input_tokens == priced.total_input_tokens
    assert budget.max_output_tokens == priced.total_output_tokens


def test_a_task_the_ceiling_says_nothing_about_has_no_limit(
    catalog, assumptions
):
    ceiling = stage_one_ceiling(
        conditions=_stage_one_conditions(),
        tasks_by_id=catalog.by_task_id(),
        assumptions=assumptions,
    )
    with pytest.raises(ValueError, match="no limit to hold it to"):
        budget_for_one_task(ceiling, "a-task-that-was-never-priced")


# ── The refusals that keep stage one from starting ─────────────────────────


def _preflight(plan, catalog, assumptions):
    return run_stage_one_preflight(
        plan, tasks_by_id=catalog.by_task_id(), assumptions=assumptions
    )


def test_stage_one_is_refused_today_and_says_no_model_can_be_reached(
    stage_one_plan, catalog, assumptions
):
    """The honest first answer is still not about money.

    The loop stage one is about now exists and is proven against stand-ins.
    What does not exist is any way to put a real model into it, so stage one
    could not start even with an amount approved — and saying which of the two
    is missing is more useful than letting the money question stand in for it.
    """
    result = _preflight(stage_one_plan, catalog, assumptions)

    assert result.may_start is False
    assert any(
        "nothing here can reach a real model" in note
        for note in result.problems
    )


def test_the_missing_model_is_established_by_running_the_code():
    """Established by calling the refusing seam, not by reading a comment."""
    problems = check_stage_one_cannot_reach_a_model()
    assert len(problems) == 1
    assert "real_model_voice refuses" in problems[0]
    assert "core.agentic_v2_conversation.run_model_conversation" in problems[0]


def test_the_check_reports_it_if_a_way_to_reach_a_model_appears(monkeypatch):
    """The answer must change by itself the day somebody builds one."""
    import core.agentic_v2_conversation as conversation

    monkeypatch.setattr(
        conversation,
        "real_model_voice",
        lambda *args, **kwargs: conversation.ScriptedVoice(replies=[]),
    )

    problems = check_stage_one_cannot_reach_a_model()

    assert any("now hands back a way to reach a real model" in note
               for note in problems)
    assert any("dispatcher's own tool-call ceiling" in note
               for note in problems)


def test_the_check_reports_it_if_the_loop_stops_refusing_paid_models(
    monkeypatch,
):
    """The refusal is what keeps an unapproved paid run from starting."""
    import core.agentic_v2_conversation as conversation

    def a_loop_that_asks_anyway(*, voice, **_kwargs):
        voice.next_turn(
            conversation.ModelRequest(
                turn=1,
                task_prompt="",
                tools_available=(),
                history=(),
                turns_left=0,
            )
        )
        return conversation.ConversationOutcome(
            stop_reason=conversation.StopReason.MODEL_STOPPED_WITHOUT_FINISHING,
            detail="",
            turns=(),
            events=(),
        )

    monkeypatch.setattr(
        conversation, "run_model_conversation", a_loop_that_asks_anyway
    )

    problems = check_stage_one_cannot_reach_a_model()

    assert any(
        "no longer refuses a model that would be charged for" in note
        for note in problems
    )
    assert any("before refusing it" in note for note in problems)


def test_the_check_reports_it_if_the_runner_gains_a_model_client(monkeypatch):
    """A second route to a paid call this check does not otherwise cover."""
    from core.agentic_v2_runner import AgenticV2ScriptedRunner

    def __init__(self, *, model_client=None, **kwargs):  # pragma: no cover
        raise AssertionError("only the signature is read")

    monkeypatch.setattr(AgenticV2ScriptedRunner, "__init__", __init__)

    problems = check_stage_one_cannot_reach_a_model()

    assert any("now accepts a model client" in note for note in problems)


def test_the_committed_stage_one_plan_approves_nothing(stage_one_plan):
    """Nothing has been approved for stage one, and the file must say so."""
    cost = stage_one_plan["cost"]
    assert cost["approved_maximum_usd"] is None
    assert cost["chosen_settings"]["tool_calls_per_attempt"] is None
    assert cost["chosen_settings"]["max_output_tokens_per_turn"] is None


def test_the_three_place_approval_does_not_extend_to_stage_one(
    stage_one_plan, catalog, assumptions
):
    """The 32.23 approved on 2026-08-25 was for that comparison and no other."""
    result = _preflight(stage_one_plan, catalog, assumptions)
    assert any("does not extend here" in note for note in result.problems)


def test_choosing_a_row_reports_the_limit_each_task_would_be_stopped_by(
    stage_one_plan, catalog, assumptions
):
    """An approver must see the limit, not only the amount.

    The amount says what could be spent. The limit says what would actually
    stop a run, and it is built from the same figures the amount came from, so
    the two cannot drift apart.
    """
    plan = copy.deepcopy(stage_one_plan)
    plan["cost"]["chosen_settings"] = {
        "tool_calls_per_attempt": 4,
        "max_output_tokens_per_turn": 2_048,
    }
    plan["cost"]["approved_maximum_usd"] = 1_000

    result = _preflight(plan, catalog, assumptions)

    assert set(result.chosen_budget) == set(plan["task_ids"])
    for budget in result.chosen_budget.values():
        # Four turns across a first attempt and one retry.
        assert budget.max_model_calls == 4 * 2
        assert budget.max_output_tokens == 2_048 * 4 * 2
        assert budget.max_input_tokens > 0
        assert budget.refusal_before_next_call() is None

    # The money is settled and the settings are chosen, so the only thing left
    # standing between here and a run is that no real model can be reached.
    assert result.may_start is False
    assert [
        note
        for note in result.problems
        if "nothing here can reach a real model" in note
    ] == result.problems


def test_nothing_is_chosen_so_no_limit_is_reported(
    stage_one_plan, catalog, assumptions
):
    result = _preflight(stage_one_plan, catalog, assumptions)
    assert result.chosen_budget == {}


def test_the_reported_limit_stops_a_run_that_reaches_it(
    stage_one_plan, catalog, assumptions
):
    """Follow the reported limit to the point where it refuses."""
    plan = copy.deepcopy(stage_one_plan)
    plan["cost"]["chosen_settings"] = {
        "tool_calls_per_attempt": 4,
        "max_output_tokens_per_turn": 2_048,
    }
    plan["cost"]["approved_maximum_usd"] = 1_000

    result = _preflight(plan, catalog, assumptions)
    budget = result.chosen_budget[plan["task_ids"][0]]

    for _ in range(budget.max_model_calls):
        assert budget.refusal_before_next_call() is None
        budget.record(input_tokens=0, output_tokens=0)

    assert budget.refusal_before_next_call() is not None


def test_choosing_settings_nobody_priced_is_refused(
    stage_one_plan, catalog, assumptions
):
    plan = copy.deepcopy(stage_one_plan)
    plan["cost"]["chosen_settings"] = {
        "tool_calls_per_attempt": 5,
        "max_output_tokens_per_turn": 3_000,
    }
    plan["cost"]["approved_maximum_usd"] = 1_000

    result = _preflight(plan, catalog, assumptions)

    assert result.may_start is False
    assert any("not one of the candidates" in note for note in result.problems)


def test_an_approved_amount_below_the_chosen_setting_is_refused(
    stage_one_plan, catalog, assumptions
):
    plan = copy.deepcopy(stage_one_plan)
    plan["cost"]["chosen_settings"] = {
        "tool_calls_per_attempt": 32,
        "max_output_tokens_per_turn": 32_768,
    }
    plan["cost"]["approved_maximum_usd"] = "1.00"

    result = _preflight(plan, catalog, assumptions)

    assert result.may_start is False
    assert any("is above the" in note for note in result.problems)
    assert result.chosen is not None


def test_letting_the_safety_blocks_open_is_refused(
    stage_one_plan, catalog, assumptions
):
    plan = copy.deepcopy(stage_one_plan)
    plan["safety_blocks_must_stay_closed"] = False

    result = _preflight(plan, catalog, assumptions)

    assert result.may_start is False
    assert any("stay closed" in note for note in result.problems)


def test_opening_the_command_tool_in_stage_one_is_refused(
    stage_one_plan, catalog, assumptions
):
    """Opening exec_run is stage three and needs its own written approval."""
    plan = copy.deepcopy(stage_one_plan)
    plan["fixed_settings"]["exec_run_open"] = True

    result = _preflight(plan, catalog, assumptions)

    assert result.may_start is False
    assert any("stage three" in note for note in result.problems)


def test_switching_self_review_on_in_stage_one_is_refused(
    stage_one_plan, catalog, assumptions
):
    plan = copy.deepcopy(stage_one_plan)
    plan["fixed_settings"]["self_review_enabled"] = True

    result = _preflight(plan, catalog, assumptions)

    assert result.may_start is False
    assert any("impossible to attribute" in note for note in result.problems)


def test_allowing_the_run_to_change_model_on_its_own_is_refused(
    stage_one_plan, catalog, assumptions
):
    plan = copy.deepcopy(stage_one_plan)
    plan["fixed_settings"]["automatic_model_switch_allowed"] = True

    result = _preflight(plan, catalog, assumptions)

    assert result.may_start is False
    assert any("no single model produced" in note for note in result.problems)


def test_a_plan_that_names_no_task_is_refused(
    stage_one_plan, catalog, assumptions
):
    plan = copy.deepcopy(stage_one_plan)
    plan["task_ids"] = []

    result = _preflight(plan, catalog, assumptions)

    assert result.may_start is False
    assert any("names no task" in note for note in result.problems)


def test_a_plan_offering_no_candidates_is_refused(
    stage_one_plan, catalog, assumptions
):
    plan = copy.deepcopy(stage_one_plan)
    plan["candidate_settings"]["tool_calls_per_attempt"] = []

    result = _preflight(plan, catalog, assumptions)

    assert result.may_start is False
    assert any("nothing to choose between" in note for note in result.problems)


def test_every_candidate_being_impossible_is_refused(
    stage_one_plan, catalog, assumptions
):
    plan = copy.deepcopy(stage_one_plan)
    plan["candidate_settings"]["tool_calls_per_attempt"] = [1_000]

    result = _preflight(plan, catalog, assumptions)

    assert result.may_start is False
    assert any(
        "refused by the dispatcher's own ceiling" in note
        for note in result.problems
    )


def test_a_plan_written_for_another_version_is_refused(tmp_path):
    target = tmp_path / "plan.yaml"
    target.write_text(
        yaml.safe_dump({"plan_version": "something-else"}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="was written for"):
        load_stage_one_plan(target)


def test_the_stage_one_plan_pins_the_same_azure_resource(stage_one_plan):
    """A stage-one result is only worth having beside the other run places.

    That needs the same deployment in the same account, so the same pinning
    applies here as in the three-place plan.
    """
    shared = load_plan(SHARED_PLAN_PATH)
    assert stage_one_plan["azure_connection"] == shared["azure_connection"]
    assert (
        stage_one_plan["model"]["deployment"]
        == shared["model_run_conditions"]["shared"]["deployment"]
    )


def test_the_stage_one_plan_uses_the_same_five_tasks(stage_one_plan):
    shared = load_plan(SHARED_PLAN_PATH)
    assert (
        stage_one_plan["task_ids"]
        == shared["model_run_conditions"]["shared"]["task_ids"]
    )


# ── The tool a person actually runs ────────────────────────────────────────


@pytest.mark.parametrize(
    "relative",
    [
        "batch-runner/scripts/check_agentic_stage_one_ceiling.py",
        "batch-runner/core/agentic_v2_stage_one_budget.py",
        "batch-runner/experiments/execution_envelope/agentic_stage_one_plan.yaml",
    ],
)
def test_the_new_files_are_in_the_repository(relative):
    """This directory hides new files unless they are allowed in by name.

    Without this, everything here would pass on the machine it was written on
    and be missing from a fresh clone.
    """
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


def test_running_the_tool_refuses_and_prints_the_table():
    """Run it exactly as a person would, and require a refusal with the numbers."""
    finished = subprocess.run(
        [sys.executable, str(STAGE_ONE_SCRIPT)],
        cwd=BATCH_RUNNER_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )

    assert finished.returncode == 1, finished.stdout + finished.stderr
    assert "What each candidate setting could cost at most" in finished.stdout
    assert "nothing here can reach a real model" in finished.stdout
    # The dispatcher's real ceiling, read from code, must reach the report.
    assert str(read_dispatcher_limits().max_total_calls) in finished.stdout


def test_the_tool_can_report_itself_as_json():
    finished = subprocess.run(
        [sys.executable, str(STAGE_ONE_SCRIPT), "--json"],
        cwd=BATCH_RUNNER_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )

    assert finished.returncode == 1
    import json

    written = json.loads(finished.stdout)
    assert written["may_start"] is False
    assert written["approved_maximum_usd"] is None
    assert written["chosen"] is None
    assert len(written["options"]) > 0
