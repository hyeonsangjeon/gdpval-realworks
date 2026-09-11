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
    price_one_stage,
    price_the_options,
    read_dispatcher_limits,
    run_stage_one_preflight,
    stage_one_amount_note,
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


def test_the_shared_plan_records_cost_without_a_per_run_threshold(
    shared_plan, assumptions, catalog
):
    """The 2026-08-28 owner decision removes only the dollar refusal."""
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

    assert shared_plan["cost"]["approved_maximum_usd"] is None
    assert shared_plan["cost"]["policy"] == "record_cost_findings_only"
    assert (
        "available_monthly_credit_usd"
        not in shared_plan["cost"]["owner_approval"]
    )
    assert ceiling.total_usd > 0

    findings = check_cost_ceiling(
        ceiling,
        approved_maximum_usd=None,
        approved_maximum_required=False,
    )
    assert not any("largest amount that may be spent" in note for note in findings)


def test_the_plan_says_cost_findings_are_recorded_after_owner_approval():
    """A reader sees the current decision instead of the superseded amount."""
    text = SHARED_PLAN_PATH.read_text(encoding="utf-8")
    assert 'policy: "record_cost_findings_only"' in text
    assert "paid_model_calls: true" in text
    assert "unpriced_audio_measurement: true" in text


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


def test_the_committed_stage_one_plan_may_start(
    stage_one_plan, catalog, assumptions
):
    """Stage one is approved, and the shipped file is what says so.

    This test used to assert the opposite, and the change is worth naming
    rather than quietly rewriting. Until 2026-09-11 nobody had written down an
    amount, so the honest answer was a refusal that said which figure was
    missing. Two amounts have since been written into the plan under the
    standing approval, and the gate now passes.

    What did not change is where the answer comes from. This reads the
    committed plan, not a copy with something helpful added, so if either
    amount is removed or a ceiling grows past it, this fails.
    """
    result = _preflight(stage_one_plan, catalog, assumptions)

    assert result.problems == []
    assert result.may_start is True


@pytest.mark.parametrize(
    "key, names",
    [
        ("running_approved_maximum_usd", "running stage one's five tasks"),
        ("grading_approved_maximum_usd", "marking stage one's five answers"),
    ],
)
def test_removing_either_approved_amount_refuses_and_names_that_one(
    stage_one_plan, catalog, assumptions, key, names
):
    """Half an approval is not an approval, and the refusal says which half.

    The machinery that refuses a missing amount can no longer be seen through
    the shipped plan, because the shipped plan now has both. So it is
    established by taking one away at a time. A reader who gets this refusal
    must be able to tell which of the two decisions has not been made, since
    they are made by different reasoning and one is a hundred times the other.
    """
    plan = copy.deepcopy(stage_one_plan)
    plan["cost"].pop(key)

    result = _preflight(plan, catalog, assumptions)

    assert result.may_start is False
    assert any(
        f"largest amount that may be spent on {names}" in note
        and f"cost.{key}" in note
        for note in result.problems
    )
    # And the other half is not dragged down with it.
    assert not any("largest amount" in note and names not in note
                   for note in result.problems)


def test_the_amount_note_follows_the_plan_rather_than_a_constant(tmp_path):
    """The sentence that used to be unconditional, now read from the file.

    It said "no amount has been approved" for as long as it existed, and would
    have gone on saying it after the amounts were written down — printed as a
    blocker by the readiness report, where somebody deciding what to do next
    would read it. Both directions are checked here: silence on the committed
    plan, and the full sentence on a plan with the figures taken out.
    """
    assert check_stage_one_cannot_reach_a_model() == []
    assert stage_one_amount_note() == []

    raw = yaml.safe_load(STAGE_ONE_PLAN_PATH.read_text(encoding="utf-8"))
    raw["cost"].pop("running_approved_maximum_usd")
    stripped = tmp_path / "one_amount_missing.yaml"
    stripped.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    problems = stage_one_amount_note(stripped)

    assert len(problems) == 1
    assert "no amount has been approved" in problems[0]
    assert "core.agentic_v2_model_voice.AzureFoundryVoice" in problems[0]
    # And it names the half that is missing rather than both.
    assert "cost.running_approved_maximum_usd" in problems[0]
    assert "cost.grading_approved_maximum_usd" not in problems[0]


def test_an_unreadable_plan_counts_as_unapproved(tmp_path):
    """The safe direction when the question cannot be answered.

    Treating a plan nobody can read as approved would turn a corrupted file
    into permission. It reports the failure instead, which is a blocker either
    way, and names what went wrong so it can be fixed rather than puzzled over.
    """
    broken = tmp_path / "not_a_plan.yaml"
    broken.write_text("plan_version: something-else\n", encoding="utf-8")

    problems = stage_one_amount_note(broken)

    assert len(problems) == 1
    assert "has to be treated as unapproved" in problems[0]


def test_the_check_reports_it_if_the_seam_stops_asking_for_an_amount(
    monkeypatch,
):
    """The answer must change by itself the day the seam stops refusing."""
    import core.agentic_v2_conversation as conversation

    monkeypatch.setattr(
        conversation,
        "real_model_voice",
        lambda *args, **kwargs: conversation.ScriptedVoice(replies=[]),
    )

    problems = check_stage_one_cannot_reach_a_model()

    assert any("now hands back a way to reach a real model" in note
               for note in problems)


def test_the_check_reports_it_if_an_undeclared_model_is_let_through(
    monkeypatch,
):
    """An approved amount must not become permission to ask anything.

    The loop refuses a voice that never said whether asking it costs money,
    and it refuses it on a budgeted run too. If that stops being true, this
    check has to say so rather than pass because the money question was
    settled.
    """
    import core.agentic_v2_conversation as conversation

    real_loop = conversation.run_model_conversation

    def lets_the_undeclared_one_through(*, voice, **kwargs):
        if getattr(voice, "makes_paid_calls", None) is None:
            # What the loop would produce if it no longer refused: an ordinary
            # run that stops for an ordinary reason.
            return real_loop(
                voice=conversation.ScriptedVoice(
                    replies=[conversation.GaveUp(note="asked and answered")]
                ),
                **kwargs,
            )
        return real_loop(voice=voice, **kwargs)

    monkeypatch.setattr(
        conversation, "run_model_conversation", lets_the_undeclared_one_through
    )

    problems = check_stage_one_cannot_reach_a_model()

    assert any(
        "no longer refuses a model that does not say" in note
        for note in problems
    )


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


def test_the_committed_stage_one_plan_approves_two_amounts_and_settings(
    stage_one_plan,
):
    """The exact figures in the file, read back, and the old key gone.

    Pinned rather than left to the gate because these four numbers are the
    decision. A change to any of them is somebody deciding something different
    about what stage one may cost or what the model is given room to do, and
    that should have to edit this test and say why.

    The absence of ``approved_maximum_usd`` is asserted too. A plan carrying
    both the old total and the two parts would be read one way by the gate and
    another way by a person, and the person would be reading a number that
    nothing enforces.
    """
    cost = stage_one_plan["cost"]

    assert "approved_maximum_usd" not in cost
    assert Decimal(str(cost["running_approved_maximum_usd"])) == Decimal("50.00")
    assert Decimal(str(cost["grading_approved_maximum_usd"])) == Decimal("2600.00")
    assert cost["chosen_settings"]["tool_calls_per_attempt"] == 8
    assert cost["chosen_settings"]["max_output_tokens_per_turn"] == 8_192


def test_the_three_place_approval_does_not_extend_to_stage_one(
    stage_one_plan, catalog, assumptions
):
    """The 32.23 approved on 2026-08-25 was for that comparison and no other.

    Seen by removing stage one's own amounts, which is the only state in which
    the question arises. Stage one was approved separately and on its own
    figures; the point being kept alive here is that it had to be, and that a
    plan with nothing written down is not quietly covered by the older, smaller
    approval sitting next to it in the same repository.
    """
    plan = copy.deepcopy(stage_one_plan)
    plan["cost"].pop("running_approved_maximum_usd")
    plan["cost"].pop("grading_approved_maximum_usd")

    result = _preflight(plan, catalog, assumptions)

    assert any("does not extend here" in note for note in result.problems)


def test_choosing_a_row_reports_the_limit_each_task_would_be_stopped_by(
    stage_one_plan, catalog, assumptions
):
    """An approver must see the limit, not only the amount.

    The amount says what could be spent. The limit says what would actually
    stop a run, and it is built from the same figures the amount came from, so
    the two cannot drift apart.

    The approved amount here is asked for rather than typed, and that is the
    point of this paragraph. It used to be a flat 1,000 — comfortably above the
    115.81 this row priced at while the shared assumptions still claimed a
    marking call sends a flat 10,000 tokens of input. When that claim was
    replaced by the 536,191 the committed marking settings actually permit one
    call to carry, this row went to 2,530.53 and the flat 1,000 started
    refusing it. Nothing about stage one had changed; a number written down by
    hand had simply stopped describing the thing it was chosen to clear.

    So they are derived instead: price the row, approve exactly what it prices
    at, and the money question is settled by construction however the
    assumptions move next. Exactly the price is enough because the refusal is
    written ``>``, not ``>=`` — an approver who signs off the quoted figure has
    signed off the run.

    Two amounts are derived, not one, because the two halves move for
    unrelated reasons. Running follows the row; marking is the same flat figure
    on every row. Approving the total would let a change in one be absorbed by
    headroom in the other.
    """
    plan = copy.deepcopy(stage_one_plan)
    plan["cost"]["chosen_settings"] = {
        "tool_calls_per_attempt": 4,
        "max_output_tokens_per_turn": 2_048,
    }

    priced = _preflight(plan, catalog, assumptions)
    assert priced.chosen is not None
    plan["cost"]["running_approved_maximum_usd"] = (
        priced.chosen.most_running_could_cost_usd
    )
    plan["cost"]["grading_approved_maximum_usd"] = (
        priced.chosen.most_grading_could_cost_usd
    )

    result = _preflight(plan, catalog, assumptions)

    assert set(result.chosen_budget) == set(plan["task_ids"])
    for budget in result.chosen_budget.values():
        # Four turns across a first attempt and one retry.
        assert budget.max_model_calls == 4 * 2
        assert budget.max_output_tokens == 2_048 * 4 * 2
        assert budget.max_input_tokens > 0
        assert budget.refusal_before_next_call() is None

    # And with the row chosen and exactly its price approved for each half,
    # nothing is left standing. That is the whole shape of this gate: the
    # amounts are the last thing, so supplying them here empties the list
    # rather than shortening it.
    #
    # Nothing starts because of this. The check is a verdict, not a switch —
    # the safety blocks it just confirmed are separate code and are still shut.
    # The shipped plan clears the same gate on different figures, which the
    # test above runs to see; this one shows the gate would still be passable
    # at a row nobody chose, so what passed up there was the arithmetic and not
    # a number picked to be comfortable.
    assert result.problems == []
    assert result.may_start is True


def test_nothing_chosen_means_no_limit_is_reported(
    stage_one_plan, catalog, assumptions
):
    """No settings, no per-task limit — and nothing invented to stand in.

    The plan now names a chosen row, so this is seen by taking it away. What
    matters is the empty dictionary rather than a refusal: a gate that helpfully
    supplied a default limit here would be choosing the settings itself, and
    the settings are the thing stage one exists to decide.
    """
    plan = copy.deepcopy(stage_one_plan)
    plan["cost"]["chosen_settings"] = {
        "tool_calls_per_attempt": None,
        "max_output_tokens_per_turn": None,
    }

    result = _preflight(plan, catalog, assumptions)

    assert result.chosen is None
    assert result.chosen_budget == {}
    assert result.may_start is False


def test_the_committed_plan_reports_a_limit_for_every_task(
    stage_one_plan, catalog, assumptions
):
    """The other side of the same coin, on the figures that will really run."""
    result = _preflight(stage_one_plan, catalog, assumptions)

    assert set(result.chosen_budget) == set(stage_one_plan["task_ids"])
    for budget in result.chosen_budget.values():
        # Nine turns — eight tool calls and the turn that finishes — across a
        # first attempt and one retry.
        assert budget.max_model_calls == 8 * 2
        assert budget.max_output_tokens == 8_192 * 8 * 2


def test_the_reported_limit_stops_a_run_that_reaches_it(
    stage_one_plan, catalog, assumptions
):
    """Follow the reported limit to the point where it refuses."""
    plan = copy.deepcopy(stage_one_plan)
    plan["cost"]["chosen_settings"] = {
        "tool_calls_per_attempt": 4,
        "max_output_tokens_per_turn": 2_048,
    }
    plan["cost"]["running_approved_maximum_usd"] = 1_000
    plan["cost"]["grading_approved_maximum_usd"] = 10_000

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

    result = _preflight(plan, catalog, assumptions)

    assert result.may_start is False
    assert any("not one of the candidates" in note for note in result.problems)


def test_a_plan_still_carrying_the_old_single_amount_is_refused(
    stage_one_plan, catalog, assumptions
):
    """The retired key is refused out loud, not read as either half.

    An approval given for a total is not an approval of a part of it. The
    danger being closed is the quiet reading: a gate that saw 2,600 under the
    old name and took it as the running ceiling would wave through a run
    seventy times larger than the one the approver had in mind, and would print
    a line saying it was within budget.
    """
    plan = copy.deepcopy(stage_one_plan)
    plan["cost"]["approved_maximum_usd"] = 2_600

    result = _preflight(plan, catalog, assumptions)

    assert result.may_start is False
    assert any(
        "one figure covering both running and marking" in note
        for note in result.problems
    )


@pytest.mark.parametrize(
    "key, half",
    [
        ("running_approved_maximum_usd", "running the five tasks"),
        ("grading_approved_maximum_usd", "marking the five answers"),
    ],
)
def test_an_approved_amount_below_the_chosen_setting_is_refused(
    stage_one_plan, catalog, assumptions, key, half
):
    """Either half being too small refuses the whole, and says which half.

    Run against both because they fail differently. Running is what the chosen
    row moves, so it is the half an ambitious setting breaks. Marking is flat,
    so it is the half that breaks when the marking assumptions are corrected
    and nobody revisits the amount — which has already happened once.
    """
    plan = copy.deepcopy(stage_one_plan)
    plan["cost"]["chosen_settings"] = {
        "tool_calls_per_attempt": 32,
        "max_output_tokens_per_turn": 32_768,
    }
    plan["cost"][key] = "1.00"

    result = _preflight(plan, catalog, assumptions)

    assert result.may_start is False
    assert any(
        f"the most {half} could cost" in note and "is above the" in note
        for note in result.problems
    )
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


# ── Stage A: a second verdict on the same gate ────────────────────────────
#
# Stage A asks one paid question before the five-task run: can a real
# deployment be reached, does it choose a tool, and does the turn after that
# arrive holding the first turn's answer. It runs one task and marks nothing.
#
# What these hold in place is that it is a second *verdict* and not a second
# *gate*. The safety checks are shared and refuse both together; only the
# amount, the settings and the task count are decided separately. So stage A
# passing must never make stage one's answer true, and stage one's missing
# amount must never be the reason stage A cannot go.


def test_both_verdicts_pass_on_the_shipped_plan(
    stage_one_plan, catalog, assumptions
):
    """The two verdicts as the shipped plan now leaves them: both green.

    They used to disagree, and that disagreement was doing the work of showing
    they were reached separately. It no longer can, so the separation is shown
    by the test below instead, which takes stage one's amounts away and watches
    stage A carry on unaffected.
    """
    result = _preflight(stage_one_plan, catalog, assumptions)

    assert result.may_start is True
    assert result.probe is not None
    assert result.probe.may_start is True
    assert result.probe.problems == []


def test_stage_ones_money_question_does_not_reach_the_probe(
    stage_one_plan, catalog, assumptions
):
    """Stage one losing its approval must not stop stage A, or vice versa.

    Each is held to its own amount. Stage A's is one dollar for a single
    unmarked task; stage one's is two figures covering five tasks and their
    marking. A gate that let one answer the other would either block the cheap
    question over the expensive one's paperwork, or — far worse in the other
    direction — let the expensive one ride on the cheap one's approval.
    """
    without_stage_one = copy.deepcopy(stage_one_plan)
    without_stage_one["cost"].pop("running_approved_maximum_usd")
    without_stage_one["cost"].pop("grading_approved_maximum_usd")

    result = _preflight(without_stage_one, catalog, assumptions)
    assert result.may_start is False
    assert result.probe is not None and result.probe.may_start is True

    without_the_probe = copy.deepcopy(stage_one_plan)
    without_the_probe["cost"]["stage_a_probe"]["approved_maximum_usd"] = None

    other = _preflight(without_the_probe, catalog, assumptions)
    assert other.probe is not None and other.probe.may_start is False
    assert other.may_start is True


def test_a_safety_block_opening_refuses_the_probe_as_well(
    stage_one_plan, catalog, assumptions
):
    """The shared half is really shared, established by breaking it.

    A gate where the cheap purchase quietly answers on fewer checks than the
    expensive one is worse than no gate, because the cheap one is the one that
    runs first.
    """
    plan = copy.deepcopy(stage_one_plan)
    plan["fixed_settings"]["exec_run_open"] = True

    result = _preflight(plan, catalog, assumptions)

    assert result.probe is not None
    assert result.probe.may_start is False
    assert any("exec_run" in note for note in result.probe.problems)
    assert any("exec_run" in note for note in result.problems)


def test_the_probe_is_priced_on_one_task_with_no_marking(
    stage_one_plan, catalog, assumptions
):
    """Marking is nearly the whole of stage one's cost, and is not bought here.

    Priced through the same arithmetic as the table rather than a second copy
    of it, so a correction to stage one's pricing reaches this figure too.
    """
    result = _preflight(stage_one_plan, catalog, assumptions)
    probe = result.probe

    assert probe.task_id == stage_one_plan["task_ids"][0]
    assert probe.ceiling.grading_usd == 0
    assert probe.ceiling.total_usd > 0
    assert probe.most_it_could_cost_usd <= probe.approved_maximum_usd

    # And it really is a fraction of the same row run five times and marked.
    cheapest_stage_one = min(
        (
            option
            for option in result.options
            if option.tool_calls_per_attempt == probe.tool_calls_per_attempt
            and option.max_output_tokens_per_turn
            == probe.max_output_tokens_per_turn
        ),
        key=lambda option: option.most_it_could_cost_usd,
    )
    assert probe.most_it_could_cost_usd < cheapest_stage_one.most_it_could_cost_usd


def test_the_probe_reports_the_limit_that_would_stop_it(
    stage_one_plan, catalog, assumptions
):
    """An amount says what could be spent; the limit says what stops a run."""
    probe = _preflight(stage_one_plan, catalog, assumptions).probe

    assert probe.budget is not None
    # Four tool calls across a first attempt and one retry.
    assert probe.budget.max_model_calls == 4 * 2
    assert probe.budget.max_output_tokens == 2_048 * 4 * 2
    assert probe.budget.refusal_before_next_call() is None


def test_an_amount_below_what_the_probe_could_cost_is_refused(
    stage_one_plan, catalog, assumptions
):
    plan = copy.deepcopy(stage_one_plan)
    plan["cost"]["stage_a_probe"]["approved_maximum_usd"] = Decimal("0.01")

    result = _preflight(plan, catalog, assumptions)

    assert result.probe.may_start is False
    assert any("is above the" in note for note in result.probe.problems)


def test_no_amount_for_the_probe_is_refused_rather_than_borrowed(
    stage_one_plan, catalog, assumptions
):
    """Approval for one purchase is not approval for the other, either way."""
    plan = copy.deepcopy(stage_one_plan)
    plan["cost"]["stage_a_probe"]["approved_maximum_usd"] = None
    plan["cost"]["running_approved_maximum_usd"] = Decimal("10000")
    plan["cost"]["grading_approved_maximum_usd"] = Decimal("10000")

    result = _preflight(plan, catalog, assumptions)

    assert result.probe.may_start is False
    assert any(
        "largest amount that may be spent on the stage A probe" in note
        for note in result.probe.problems
    )


def test_one_tool_call_cannot_answer_the_question_and_is_refused(
    stage_one_plan, catalog, assumptions
):
    """A single call has no second turn, and the second turn is the question."""
    plan = copy.deepcopy(stage_one_plan)
    plan["candidate_settings"]["tool_calls_per_attempt"] = [1, 4]
    plan["cost"]["stage_a_probe"]["chosen_settings"][
        "tool_calls_per_attempt"
    ] = 1

    result = _preflight(plan, catalog, assumptions)

    assert result.probe.may_start is False
    assert any(
        "arrives holding that call's answer" in note
        for note in result.probe.problems
    )


def test_settings_nobody_priced_are_refused(
    stage_one_plan, catalog, assumptions
):
    plan = copy.deepcopy(stage_one_plan)
    plan["cost"]["stage_a_probe"]["chosen_settings"][
        "max_output_tokens_per_turn"
    ] = 3_000

    result = _preflight(plan, catalog, assumptions)

    assert result.probe.may_start is False
    assert any(
        "not among the candidates" in note for note in result.probe.problems
    )


def test_the_offered_tools_are_read_from_the_probe_and_not_from_the_plan(
    stage_one_plan, catalog, assumptions, monkeypatch
):
    """A list in a document is a claim; the tuple in the code is what is sent.

    Established by changing the code and leaving the document alone. The plan
    says where the tools come from and nothing more, so a probe that gained
    ``finalize`` fails this check even though nobody edited the plan.
    """
    import core.agentic_v2_stage_a_probe as probe_module

    assert (
        stage_one_plan["cost"]["stage_a_probe"]["tools_come_from"]
        == "core/agentic_v2_stage_a_probe.py PROBE_TOOLS"
    )

    clean = _preflight(stage_one_plan, catalog, assumptions).probe
    assert clean.tools_offered == probe_module.PROBE_TOOLS

    monkeypatch.setattr(
        probe_module,
        "PROBE_TOOLS",
        ("capabilities_query", "finalize"),
    )
    widened = _preflight(stage_one_plan, catalog, assumptions).probe

    assert widened.may_start is False
    assert any("finalize" in note for note in widened.problems)


def test_the_probe_cannot_be_pointed_at_a_task_the_plan_did_not_fix(
    stage_one_plan, catalog, assumptions
):
    """Its task is taken by position, so nobody can choose the easy one."""
    from core.agentic_v2_stage_one_budget import stage_a_probe_ceiling

    with pytest.raises(ValueError, match="not one of the tasks"):
        stage_a_probe_ceiling(
            conditions=StageOneConditions(
                resource="hjeon-fdpo-foundry-eus2",
                deployment="gpt-5.4",
                resolved_model="gpt-5.4",
                task_ids=tuple(stage_one_plan["task_ids"]),
                tool_calls_per_attempt=4,
                max_output_tokens_per_turn=2_048,
                retry_max_attempts=1,
                per_task_timeout_seconds=1_200,
            ),
            task_id="a-task-nobody-fixed",
            tasks_by_id=catalog.by_task_id(),
            assumptions=assumptions,
        )


def test_the_probe_verdict_survives_being_written_down(
    stage_one_plan, catalog, assumptions
):
    written = _preflight(stage_one_plan, catalog, assumptions).as_dict()
    probe = written["stage_a_probe"]

    assert probe["may_start"] is True
    assert probe["tools_offered"] == ["capabilities_query", "workspace_apply"]
    assert probe["most_marking_could_cost_usd"] == "0.00"
    assert Decimal(probe["most_it_could_cost_usd"]) <= Decimal(
        probe["approved_maximum_usd"]
    )

    # Stage one's own verdict is written alongside, against two amounts rather
    # than one. The probe keeps a single figure on purpose: it marks nothing,
    # so a second amount there would be an approval for work it does not do.
    assert written["may_start"] is True
    assert written["running_approved_maximum_usd"] == "50.00"
    assert written["grading_approved_maximum_usd"] == "2600.00"
    assert "approved_maximum_usd" not in written


# ── The tool a person actually runs ────────────────────────────────────────


@pytest.mark.parametrize(
    "relative",
    [
        "batch-runner/scripts/check_agentic_stage_one_ceiling.py",
        "batch-runner/core/agentic_v2_stage_one_budget.py",
        "batch-runner/core/agentic_v2_stage_a_probe.py",
        "batch-runner/scripts/run_agentic_stage_a_probe.py",
        "batch-runner/experiments/execution_envelope/agentic_stage_one_plan.yaml",
        ".github/workflows/agentic-v2-stage-a-probe.yml",
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


def _plan_without_stage_ones_amounts(tmp_path: Path) -> Path:
    """The committed plan with only the two approved figures taken out.

    Written for the command-line tests, which need a plan the tool refuses now
    that the shipped one passes. Everything else is copied through untouched,
    so what the tool is reacting to is the missing money and nothing else.
    """
    raw = yaml.safe_load(STAGE_ONE_PLAN_PATH.read_text(encoding="utf-8"))
    raw["cost"].pop("running_approved_maximum_usd")
    raw["cost"].pop("grading_approved_maximum_usd")
    written = tmp_path / "plan_without_amounts.yaml"
    written.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return written


def test_running_the_tool_passes_and_prints_the_table():
    """Run it exactly as a person would, and require the numbers with the verdict.

    The table matters more now than when this refused. A zero exit is the point
    at which somebody could stop reading, so the figures the approval rests on
    have to be in the same output rather than only in the refusal that used to
    carry them.
    """
    finished = subprocess.run(
        [sys.executable, str(STAGE_ONE_SCRIPT)],
        cwd=BATCH_RUNNER_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )

    assert finished.returncode == 0, finished.stdout + finished.stderr
    assert "What each candidate setting could cost at most" in finished.stdout
    # Both halves of the approval, each against its own ceiling.
    assert "50.00" in finished.stdout
    assert "2600.00" in finished.stdout
    # The dispatcher's real ceiling, read from code, must reach the report.
    assert str(read_dispatcher_limits().max_total_calls) in finished.stdout


def test_the_tool_still_refuses_a_plan_with_no_amounts(tmp_path):
    """The refusal path, kept alive on a plan that has had its figures removed.

    This is the state the repository was in until stage one was approved, and
    it is the state any future stage starts in. Losing the test with the
    approval would mean the next stage's gate was never seen to refuse.
    """
    finished = subprocess.run(
        [
            sys.executable,
            str(STAGE_ONE_SCRIPT),
            "--plan",
            str(_plan_without_stage_ones_amounts(tmp_path)),
        ],
        cwd=BATCH_RUNNER_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )

    assert finished.returncode == 1, finished.stdout + finished.stderr
    assert (
        "nobody has written down the largest amount that may be spent on "
        "running stage one's five tasks" in finished.stdout
    )
    assert (
        "nobody has written down the largest amount that may be spent on "
        "marking stage one's five answers" in finished.stdout
    )


def test_the_probe_flag_follows_the_probe_and_not_stage_one(tmp_path):
    """``--probe`` answers about stage A even when stage one is refused.

    Two verdicts in one place is the risk this covers, and the direction of the
    risk has flipped. It used to be that a zero exit from ``--probe`` might be
    read as permission to run the five tasks. Now that the default form also
    exits zero, the thing worth holding is that ``--probe`` is still *not*
    reading stage one's verdict — shown on a plan where the two disagree.
    """
    without_amounts = str(_plan_without_stage_ones_amounts(tmp_path))
    probed = subprocess.run(
        [sys.executable, str(STAGE_ONE_SCRIPT), "--probe", "--plan", without_amounts],
        cwd=BATCH_RUNNER_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )
    default = subprocess.run(
        [sys.executable, str(STAGE_ONE_SCRIPT), "--plan", without_amounts],
        cwd=BATCH_RUNNER_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )

    assert probed.returncode == 0, probed.stdout + probed.stderr
    assert default.returncode == 1
    assert "Every stage A condition is met" in probed.stdout
    assert "separate purchase" in probed.stdout
    # The refusal of the larger purchase is printed by the same run.
    assert (
        "nobody has written down the largest amount that may be spent on "
        "running stage one's five tasks" in probed.stdout
    )


def test_the_probe_is_reported_whichever_form_of_the_command_is_run():
    """The figures are the same either way; only the exit code follows a side."""
    default = subprocess.run(
        [sys.executable, str(STAGE_ONE_SCRIPT), "--json"],
        cwd=BATCH_RUNNER_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )
    probed = subprocess.run(
        [sys.executable, str(STAGE_ONE_SCRIPT), "--json", "--probe"],
        cwd=BATCH_RUNNER_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )

    # Both pass on the shipped plan, so this no longer shows the exit codes
    # coming from different places. That is the test above. What it does show
    # is that the report itself does not change with the flag.
    assert default.returncode == 0
    assert probed.returncode == 0
    assert default.stdout == probed.stdout

    import json

    probe = json.loads(default.stdout)["stage_a_probe"]
    assert probe["may_start"] is True
    assert probe["task_id"] == load_stage_one_plan(STAGE_ONE_PLAN_PATH)[
        "task_ids"
    ][0]


def test_the_tool_can_report_itself_as_json():
    finished = subprocess.run(
        [sys.executable, str(STAGE_ONE_SCRIPT), "--json"],
        cwd=BATCH_RUNNER_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )

    assert finished.returncode == 0
    import json

    written = json.loads(finished.stdout)
    assert written["may_start"] is True
    assert written["running_approved_maximum_usd"] == "50.00"
    assert written["grading_approved_maximum_usd"] == "2600.00"
    assert written["chosen"] is not None
    assert len(written["options"]) > 0


# ── Pricing a stage by name ────────────────────────────────────────────────
#
# The guard these cover replaced one that compared two task counts. The
# counting version had the failure mode that matters here backwards: it refused
# a larger stage even when that stage had been priced, and it would have passed
# a cohort of the approved *size* whose tasks had grown more expensive. These
# ask the only question worth asking — does the amount approved for this stage
# cover the cohort that is about to run.


def _priced_plan(**stage_overrides) -> dict:
    """The committed plan, with its `stages` block swapped for a given one."""
    plan = dict(load_stage_one_plan(STAGE_ONE_PLAN_PATH))
    plan["stages"] = dict(stage_overrides)
    return plan


def test_every_registered_stage_in_the_committed_plan_is_priced_for_running(
    catalog, assumptions, stage_one_plan
):
    """All three rungs, priced. An escalation with a gap cannot be climbed.

    Read from the committed plan rather than a fixture, because the thing being
    checked is that the real file carries the approvals — a fixture would pass
    happily while the file that actually gates the run did not.
    """
    from core.agentic_v2_preregistration import ESCALATION, cohorts

    groups = cohorts(catalog)
    for stage in ESCALATION:
        pricing = price_one_stage(
            stage_one_plan,
            stage=stage,
            task_ids=groups[stage],
            tasks_by_id=catalog.by_task_id(),
            assumptions=assumptions,
        )
        assert pricing.may_run, (stage, pricing.problems)
        assert pricing.approved_running_usd is not None
        assert pricing.most_running_could_cost_usd <= pricing.approved_running_usd
        assert pricing.headroom_usd >= 0


def test_marking_is_approved_for_the_five_and_refused_with_a_reason_beyond_them(
    catalog, assumptions, stage_one_plan
):
    """The asymmetry is the finding, so it is asserted rather than assumed.

    Running two hundred and twenty tasks costs a few hundred dollars. Marking
    them costs six figures, because the grader asks hundreds of questions per
    answer. Those are two decisions and only one of them has been made.
    """
    from core.agentic_v2_preregistration import cohorts

    groups = cohorts(catalog)

    five = price_one_stage(
        stage_one_plan, stage="advance_check_5", task_ids=groups["advance_check_5"],
        tasks_by_id=catalog.by_task_id(), assumptions=assumptions,
    )
    assert five.approved_grading_usd is not None
    assert five.grading_not_approved_because is None

    for stage in ("trial_30", "full_220"):
        bigger = price_one_stage(
            stage_one_plan, stage=stage, task_ids=groups[stage],
            tasks_by_id=catalog.by_task_id(), assumptions=assumptions,
        )
        assert bigger.approved_grading_usd is None, stage
        # Refused *and* explained. A null with no reason is indistinguishable
        # from a figure somebody forgot to write, and the two want opposite
        # responses from whoever reads it next.
        assert bigger.grading_not_approved_because, stage
        assert bigger.may_run, (stage, bigger.problems)


def test_the_five_task_amounts_are_one_figure_and_not_two_copies(stage_one_plan):
    """``cost`` and ``stages.advance_check_5`` must not be able to disagree.

    They are written as a YAML anchor and an alias, so they cannot. This holds
    that property against somebody later replacing the alias with a literal
    that looks identical on the day it is written.
    """
    cost = stage_one_plan["cost"]
    entry = stage_one_plan["stages"]["advance_check_5"]

    assert entry["running_approved_maximum_usd"] == cost["running_approved_maximum_usd"]
    assert entry["grading_approved_maximum_usd"] == cost["grading_approved_maximum_usd"]


def test_a_cohort_larger_than_its_approval_is_refused_with_the_shortfall(
    catalog, assumptions
):
    """The number is the point. "Not priced" invites someone to wave it through."""
    from core.agentic_v2_preregistration import cohorts

    plan = _priced_plan(
        full_220={
            "running_approved_maximum_usd": 50.00,
            "grading_approved_maximum_usd": None,
            "grading_not_approved_because": "not asked for",
        }
    )

    pricing = price_one_stage(
        plan, stage="full_220", task_ids=cohorts(catalog)["full_220"],
        tasks_by_id=catalog.by_task_id(), assumptions=assumptions,
    )

    assert not pricing.may_run
    trouble = " ".join(pricing.problems)
    assert "short by $" in trouble
    assert "nothing here may scale an approved amount on its own" in trouble


def test_a_stage_the_plan_never_mentions_is_refused_by_name(catalog, assumptions):
    plan = _priced_plan(advance_check_5={"running_approved_maximum_usd": 50.00,
                                         "grading_approved_maximum_usd": 2600.00})

    pricing = price_one_stage(
        plan, stage="trial_30", task_ids=("a", "b"),
        tasks_by_id=catalog.by_task_id(), assumptions=assumptions,
    )

    assert not pricing.may_run
    trouble = " ".join(pricing.problems)
    assert "'trial_30'" in trouble
    assert "whatever their relative sizes" in trouble


def test_silence_about_marking_is_refused_but_a_reasoned_refusal_is_not(
    catalog, assumptions
):
    """Absent and null are different answers, and only one is a mistake.

    Marking costs many times what running does, so a stage block that simply
    never mentions it is the one shape this may not take: it reads as approved
    to anybody who does not already know the number.
    """
    from core.agentic_v2_preregistration import cohorts

    ids = cohorts(catalog)["advance_check_5"]
    silent = price_one_stage(
        _priced_plan(advance_check_5={"running_approved_maximum_usd": 50.00}),
        stage="advance_check_5", task_ids=ids,
        tasks_by_id=catalog.by_task_id(), assumptions=assumptions,
    )
    assert not silent.may_run
    assert "says nothing about marking" in " ".join(silent.problems)

    unexplained = price_one_stage(
        _priced_plan(advance_check_5={
            "running_approved_maximum_usd": 50.00,
            "grading_approved_maximum_usd": None,
        }),
        stage="advance_check_5", task_ids=ids,
        tasks_by_id=catalog.by_task_id(), assumptions=assumptions,
    )
    assert not unexplained.may_run
    assert "gives no reason" in " ".join(unexplained.problems)

    explained = price_one_stage(
        _priced_plan(advance_check_5={
            "running_approved_maximum_usd": 50.00,
            "grading_approved_maximum_usd": None,
            "grading_not_approved_because": "nobody has asked for the answers "
                                            "to be marked yet",
        }),
        stage="advance_check_5", task_ids=ids,
        tasks_by_id=catalog.by_task_id(), assumptions=assumptions,
    )
    assert explained.may_run, explained.problems


def test_a_plan_with_no_stages_block_refuses_rather_than_passing_by_default(
    catalog, assumptions
):
    """The state the file was in before any stage was priced by name.

    A guard whose absent configuration means "allow" is not a guard.
    """
    plan = dict(load_stage_one_plan(STAGE_ONE_PLAN_PATH))
    plan.pop("stages", None)

    pricing = price_one_stage(
        plan, stage="advance_check_5", task_ids=("a",),
        tasks_by_id=catalog.by_task_id(), assumptions=assumptions,
    )

    assert not pricing.may_run
    assert "no `stages` block" in " ".join(pricing.problems)


# ── What the model is actually told, and what that costs ───────────────────
#
# Until 2026-09-11 the plan had no `instructions` key at all, so the runner sent
# the empty string on every turn while this repository's own notes said the
# standing instructions "describe the V2 tool contract". The model was told
# nothing: not that three of its eight tools refuse, not that its input files
# exist, not where they are.
#
# The text is now in the plan, which puts it in two places at once. It is the
# thing most likely to be edited casually, and it is billed on every turn of
# every task -- so it is tested as both.


@pytest.fixture
def stage_one_instructions(stage_one_plan):
    return stage_one_plan["instructions"]


def test_the_runner_has_something_to_send(stage_one_instructions):
    """`scripts/run_agentic_v2_stage.py` reads `plan.get("instructions") or ""`.

    That expression cannot fail, which is exactly the problem: an absent key
    reads as an empty instruction and the run still goes ahead, costing the same
    money and producing a model that was never told anything.
    """
    assert isinstance(stage_one_instructions, str)
    assert stage_one_instructions.strip()


def test_the_instructions_fit_what_they_were_priced_at(
    stage_one_instructions, assumptions
):
    """Named in the plan file's own comment, and this is that test.

    Every figure under `cost:` was worked out at the width borrowed from
    `advance_check_plan.yaml`. Wording longer than that is not a matter of
    style: it is spending against an approval computed for something else, once
    per turn, for every task in the cohort.
    """
    assert len(stage_one_instructions) <= assumptions.instruction_character_count


def test_the_instructions_name_every_tool_the_model_is_given(
    stage_one_instructions
):
    """Read from the dispatcher's vocabulary, so the two cannot drift apart.

    A tool the model holds but is never told about is one it finds by guessing,
    and a tool named here that does not exist is an instruction to call
    something that will be refused as unknown.
    """
    from core.agentic_v2_tools import TOOL_SCHEMAS

    missing = [name for name in TOOL_SCHEMAS if name not in stage_one_instructions]
    assert missing == []


def test_the_instructions_claim_only_the_refusals_that_were_measured(
    stage_one_instructions, tmp_path
):
    """The sentence "these three refuse" is checked by asking them.

    An earlier draft also said `browser_run` and `verify_public` refuse because
    nothing here reaches the network. Probing them disproved it -- `browser_run`
    opens local files and `verify_public` checks deliverables, both answering
    ``ok: True``. Telling a model a working tool is shut costs it the tool.
    """
    from core.agentic_v2_contract import AgenticV2Profile
    from core.agentic_v2_fixture_backend import AgenticV2FixtureBackend

    backend = AgenticV2FixtureBackend(
        root=tmp_path / "task",
        profile=AgenticV2Profile(
            tool_contract_version="2.0",
            policy_profile_id="offline-full-v1",
            foundation_only=True,
        ),
    )

    for name in ("exec_run", "environment_resolve", "environment_activate"):
        answer = getattr(backend, name)({"argv": ["true"]})
        assert answer["ok"] is False
        assert answer["error_type"] == "capability_unavailable"

    assert "capability_unavailable" in stage_one_instructions
    for working in ("browser_run", "verify_public"):
        assert f"{working} refuse" not in stage_one_instructions


def test_the_instructions_point_at_the_file_that_lists_the_inputs(
    stage_one_instructions
):
    """Bound to the staging constants rather than to a typed-out path.

    The guide is written by `core.agentic_v2_reference_staging`. If its name or
    its directory moves and this text does not, the model is sent to look for a
    file that is not there -- and it has no other way to learn its inputs exist,
    because the task wording is dataset-supplied and sealed.
    """
    from core.agentic_v2_reference_staging import INPUTS_GUIDE, MODEL_INPUT_PREFIX

    assert f"{MODEL_INPUT_PREFIX}/{INPUTS_GUIDE}" in stage_one_instructions
    assert f"{MODEL_INPUT_PREFIX}/extracted" in stage_one_instructions


def test_the_instructions_say_a_format_failure_is_not_the_model_s_fault(
    stage_one_instructions
):
    """The distinction step five of the goal asks for, at the point it bites.

    258 of the 261 reference files do not decode as UTF-8, and
    `workspace_apply(read)` decodes UTF-8. A model that reads this and keeps
    retrying the spreadsheet is failing; one that was never told and keeps
    retrying is being failed by the environment. Only the first is evidence
    about the model.
    """
    assert "not a mistake" in stage_one_instructions
    assert "is not the file" in stage_one_instructions


def test_the_instructions_carry_the_size_rule_that_stops_every_write(
    stage_one_instructions
):
    """A deliverable over 1 MiB does not fail on its own -- it fails the rest.

    The backend applies the limit during a walk over the whole workspace, and
    the walk runs on write, so one oversized file makes every later write raise.
    The model is told the rule because it is the one it can break by accident
    and cannot diagnose from what it is shown.
    """
    assert "1 MiB" in stage_one_instructions
    assert "later write fail" in stage_one_instructions
