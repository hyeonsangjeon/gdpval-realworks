"""The gate prices eight turns an attempt. The run takes nine.

Two places decide how long one attempt may be, and they are meant to agree.

``ceilings_from`` in `agentic_v2_conversation_runner.py` builds what the run
actually enforces, and it says ``calls + 1`` -- "one model call per tool call,
plus the turn that finalises". Its own comment, three lines below, says the
input is "priced that way in price_the_options; bounded the same way here".

``stage_one_ceiling`` in `agentic_v2_stage_one_budget.py` builds the figure the
gate compares against the approved amount, and it passes
``tool_calls_per_attempt`` straight through as ``tool_loop_max_model_turns``.
No ``+ 1``. So the two are not bounded the same way: the price is worked out
for an attempt one turn shorter than the one that runs.

Which is right is settled by trial_30 itself (run 34671538199). Sixteen of its
attempts stopped with ``turn_limit_reached``, and the conversation record's own
words for it are *"the model has been asked 9 times, which is all the 9 this
run was allowed"* -- nine, at ``tool_calls_per_attempt: 8``. The runner is
describing the run. The pricer is a turn behind it.

It matters more than one turn sounds, because the input of a looping attempt is
quadratic in its length: each turn re-reads everything before it. Going from
eight turns to nine adds 8 to the 28 re-read pairs, not 1 to 8. Observed on
2026-09-12, priced against the real cohorts through the gate's own arithmetic:

    advance_check_5    $18.47  ->  $22.88   (+24%)   against $50 approved
    trial_30          $114.60  ->  $141.60  (+24%)   against $200 approved
    full_220          $884.61  -> $1088.12  (+23%)   against $1400 approved

**No stage's verdict changes**, which is the part worth being clear about. Every
one of those is still inside its approved amount, and the rows the design
document reports as closed -- 12, 16 and 32 tool calls on thirty tasks -- were
already over before the correction and are further over after it. Nothing ran
that should not have, and nothing here loosens a ceiling; the number the gate
prints is wrong in the direction of looking cheaper than the run is, and that is
worth fixing for the next approval rather than this one.

Nothing here calls a model, opens a connection, or spends anything: both sides
are arithmetic over a plan file and a task catalogue.
"""
from __future__ import annotations

import dataclasses
from decimal import Decimal
from pathlib import Path

import pytest

from core.agentic_v2_conversation_runner import ceilings_from
from core.agentic_v2_stage_one_budget import (
    STAGE_ONE_PLAN_PATH,
    StageOneConditions,
    budget_for_one_task,
    load_stage_one_plan,
    read_dispatcher_limits,
    run_stage_one_preflight,
    stage_one_ceiling,
    tool_result_tokens_ceiling,
)
from core.execution_envelope_cost import CostAssumptions, estimate_cost_ceiling
from core.execution_envelope_preflight import load_plan
from core.execution_envelope_tasks import (
    full_run_tasks,
    load_task_catalog,
    select_trial_run_tasks,
)
from core.execution_environment_readiness import ENVIRONMENT_AGENTIC_SANDBOX_V2

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def plan() -> dict:
    return load_stage_one_plan(STAGE_ONE_PLAN_PATH)


@pytest.fixture(scope="module")
def assumptions(plan) -> CostAssumptions:
    shared = load_plan(BATCH_RUNNER_ROOT / str(plan["cost"]["assumptions_come_from"]))
    return CostAssumptions.from_mapping(shared["cost"]["assumptions"])


@pytest.fixture(scope="module")
def catalog():
    return load_task_catalog()


@pytest.fixture(scope="module")
def chosen(plan, assumptions, catalog):
    """The settings row the run would actually take, from the gate itself.

    Read out of the preflight rather than off the plan, because that is what
    `scripts/run_agentic_v2_stage.py` hands to `ceilings_from`.
    """
    verdict = run_stage_one_preflight(
        plan, tasks_by_id=catalog.by_task_id(), assumptions=assumptions
    )
    assert verdict.chosen is not None, "the plan names no chosen settings"
    return verdict.chosen


def _conditions(plan, chosen, task_ids) -> StageOneConditions:
    fixed = dict(plan.get("fixed_settings") or {})
    return StageOneConditions(
        resource=str((plan.get("azure_connection") or {}).get("account") or ""),
        deployment=str((plan.get("model") or {}).get("deployment") or ""),
        resolved_model=str((plan.get("model") or {}).get("resolved_model") or ""),
        task_ids=tuple(task_ids),
        tool_calls_per_attempt=chosen.tool_calls_per_attempt,
        max_output_tokens_per_turn=chosen.max_output_tokens_per_turn,
        retry_max_attempts=int(fixed.get("retry_max_attempts") or 0),
        per_task_timeout_seconds=int(fixed.get("per_task_timeout_seconds") or 0),
    )


def _priced(plan, chosen, assumptions, catalog, task_ids, *, turns) -> Decimal:
    """The running ceiling, with the turns-per-attempt forced to `turns`.

    Everything else is what `stage_one_ceiling` does, copied from it rather
    than called through it, because the one line under test is the one that
    decides `turns`.
    """
    limits = read_dispatcher_limits()
    conditions = _conditions(plan, chosen, task_ids).validated(limits)
    forced = dataclasses.replace(
        assumptions,
        tool_loop_max_model_turns={ENVIRONMENT_AGENTIC_SANDBOX_V2: turns},
        output_tokens_capped_per_attempt={ENVIRONMENT_AGENTIC_SANDBOX_V2: False},
        max_tool_result_tokens_per_turn={
            ENVIRONMENT_AGENTIC_SANDBOX_V2: tool_result_tokens_ceiling(
                limits, characters_per_token=assumptions.characters_per_token
            )
        },
    )
    ceiling = estimate_cost_ceiling(
        conditions_by_environment={
            ENVIRONMENT_AGENTIC_SANDBOX_V2: conditions.as_run_conditions()
        },
        tasks_by_id=catalog.by_task_id(),
        assumptions=forced,
    )
    return ceiling.running_usd * ceiling.safety_multiplier


def test_the_run_gives_an_attempt_one_turn_more_than_it_has_tool_calls(plan, chosen):
    """The finalising turn is a model call and the runner counts it."""
    ceilings = ceilings_from(plan, chosen)
    assert ceilings.max_model_turns == chosen.tool_calls_per_attempt + 1
    assert ceilings.max_model_calls == chosen.tool_calls_per_attempt + 1


def test_the_price_is_worked_out_without_that_turn(plan, chosen, assumptions, catalog):
    """`stage_one_ceiling` passes the tool-call count through unchanged.

    Read off the priced result rather than the source: model calls come out as
    tool calls times attempts, with nothing added for finalising.
    """
    fixed = dict(plan.get("fixed_settings") or {})
    attempts = 1 + int(fixed.get("retry_max_attempts") or 0)
    task_ids = select_trial_run_tasks(catalog)

    ceiling = stage_one_ceiling(
        conditions=_conditions(plan, chosen, task_ids),
        tasks_by_id=catalog.by_task_id(),
        assumptions=assumptions,
    )
    priced_calls = sum(entry.model_calls for entry in ceiling.environments)
    assert priced_calls == chosen.tool_calls_per_attempt * attempts * len(task_ids)

    # What the run would take, by the runner's own figure.
    would_take = ceilings_from(plan, chosen).max_model_calls * attempts * len(task_ids)
    assert would_take == priced_calls + attempts * len(task_ids)


def test_the_per_task_line_the_gate_prints_is_short_by_one_attempt_of_turns(
    plan, chosen, assumptions, catalog
):
    """"at most 16 model calls" is printed where the run allows 18.

    `budget_for_one_task` is what that line is built from. It is only reached
    from the preflight -- the run enforces `PerTaskCeilings` instead -- so the
    two never meet at runtime and cannot disagree loudly.
    """
    task_ids = select_trial_run_tasks(catalog)
    ceiling = stage_one_ceiling(
        conditions=_conditions(plan, chosen, task_ids),
        tasks_by_id=catalog.by_task_id(),
        assumptions=assumptions,
    )
    attempts = 1 + int((plan.get("fixed_settings") or {}).get("retry_max_attempts") or 0)
    printed = budget_for_one_task(ceiling, task_ids[0]).max_model_calls
    enforced = ceilings_from(plan, chosen).max_model_calls * attempts

    assert printed == chosen.tool_calls_per_attempt * attempts
    assert enforced == printed + attempts
    assert enforced > printed


def test_one_more_turn_costs_far_more_than_one_turn_of_input(
    plan, chosen, assumptions, catalog
):
    """Because every turn re-reads the ones before it.

    Nine turns re-read 36 earlier-turn pairs where eight re-read 28, so the
    growing part of the bill rises by 29% for a 12.5% rise in turns. Asserted
    as a band rather than a figure: the dollar amounts move whenever the shared
    price table or the task catalogue does, and neither is this test's subject.
    """
    task_ids = select_trial_run_tasks(catalog)
    calls = chosen.tool_calls_per_attempt
    as_priced = _priced(plan, chosen, assumptions, catalog, task_ids, turns=calls)
    as_run = _priced(plan, chosen, assumptions, catalog, task_ids, turns=calls + 1)

    assert as_run > as_priced
    ratio = as_run / as_priced
    # Observed 1.236 on 2026-09-12. Bounded well clear of the 1.125 that
    # counting turns alone would give, which is the point being pinned.
    assert Decimal("1.15") < ratio < Decimal("1.35")


@pytest.mark.parametrize(
    "stage,task_ids_of",
    [
        ("advance_check_5", lambda plan, catalog: tuple(plan["task_ids"])),
        ("trial_30", lambda plan, catalog: select_trial_run_tasks(catalog)),
        ("full_220", lambda plan, catalog: full_run_tasks(catalog)),
    ],
)
def test_correcting_the_turn_count_changes_no_stage_verdict(
    plan, chosen, assumptions, catalog, stage, task_ids_of
):
    """The gate is wrong about the amount and right about the answer.

    This is the assertion that keeps the finding from being read as a reason to
    revisit an approval. Every stage is inside its approved amount at the
    corrected turn count as well as at the priced one, so no run was let
    through that should have been refused.

    If a stage ever fails here it means the correction has started to matter to
    a decision, and the plan needs a larger approved figure -- not a smaller
    turn count.
    """
    approved = (plan.get("stages") or {}).get(stage, {}).get(
        "running_approved_maximum_usd"
    )
    if approved is None:
        pytest.skip(f"{stage} has no approved running amount to check against")

    task_ids = task_ids_of(plan, catalog)
    calls = chosen.tool_calls_per_attempt
    as_priced = _priced(plan, chosen, assumptions, catalog, task_ids, turns=calls)
    as_run = _priced(plan, chosen, assumptions, catalog, task_ids, turns=calls + 1)
    limit = Decimal(str(approved))

    assert as_priced <= limit, f"{stage} is over its approval before the correction"
    assert as_run <= limit, (
        f"{stage} is inside ${limit} as priced (${as_priced:.2f}) but over it at "
        f"the turn count the run actually takes (${as_run:.2f}). The approval "
        "needs raising; the turn count is not the thing to change."
    )
