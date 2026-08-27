"""What stage one of Agentic Sandbox V2 could cost, and how it is held to it.

Stage one is the first step described in
``tasks/0822_saturday/TASK_AGENTIC_SANDBOX_V2_FOUNDATION.md``: let the model
choose its own next action from the safe tools, with the command-running tool
``exec_run`` still shut. It is also the first step in that document that costs
money, because it calls the model again after every tool result instead of
once per task.

That changes the shape of the bill completely, and the difference is not small.
When the model is asked once, the cost of a task is roughly fixed by how long
the task is. When the model is asked again after each tool result, three things
happen at once:

* the number of calls rises to the number of tool calls allowed;
* every call may write a full-length answer, so the writing is charged once per
  turn rather than once per task;
* every turn re-reads the whole conversation so far, so what was written on the
  first turn is charged again on every turn after it.

The third is the one that catches people out. It means the bill does not grow
in step with the number of turns; it grows roughly with the square of it.
Doubling how many times the model may be asked roughly quadruples what the
earlier turns cost to re-read.

So this module does two separate jobs.

**Before anything runs**, :func:`stage_one_ceiling` works out the largest bill a
stage-one run could produce, using the same arithmetic as the rest of the
comparison. It takes the limits it needs from the dispatcher's own code rather
than from numbers copied into a document, so the figure cannot drift away from
what the code would actually allow.

**While something runs**, :class:`StageOneBudget` counts what has been spent and
refuses the next call once a ceiling is reached. Without it the worked-out
figure would be a hope rather than a limit.

Nothing in this module calls a model, opens ``exec_run``, or changes any of the
three blocks that keep Agentic Sandbox V2 out of the paid pipeline. It does
arithmetic and it counts.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_CEILING
from pathlib import Path
from typing import Any, Mapping

from core.agentic_v2_tools import AgenticV2ToolDispatcher
from core.execution_envelope_cost import (
    CostAssumptions,
    CostCeiling,
    ModelPrice,
    estimate_cost_ceiling,
)
from core.execution_envelope_tasks import CatalogTask
from core.execution_environment_readiness import (
    ENVIRONMENT_AGENTIC_SANDBOX_V2,
    SERVING_PATH_MICROSOFT_FOUNDRY_DEPLOYMENT,
    ModelRunConditions,
)


@dataclass(frozen=True)
class DispatcherLimits:
    """The ceilings the tool dispatcher applies, read from its own code.

    These are not restated here as numbers. They are read from
    :class:`core.agentic_v2_tools.AgenticV2ToolDispatcher` so that lowering or
    raising a limit in the dispatcher moves the worked-out bill with it, and a
    document cannot quietly disagree with the code.
    """

    max_total_calls: int
    """The most tool calls one run may make before the dispatcher refuses."""

    max_result_bytes: int
    """The most one tool result may weigh once written out."""


def read_dispatcher_limits() -> DispatcherLimits:
    """Read the two ceilings the dispatcher applies to every run."""
    defaults = {
        entry.name: entry.default
        for entry in dataclasses.fields(AgenticV2ToolDispatcher)
    }
    readable: dict[str, int] = {}
    missing: list[str] = []
    for name in ("max_total_calls", "max_result_bytes"):
        value = defaults.get(name)
        if isinstance(value, bool) or not isinstance(value, int):
            missing.append(name)
        else:
            readable[name] = value
    if missing:
        raise ValueError(
            "the tool dispatcher no longer states a plain number for: "
            + ", ".join(sorted(missing))
            + ". The stage-one bill is worked out from those numbers, so it "
            "cannot be worked out until they are readable again."
        )
    return DispatcherLimits(
        max_total_calls=readable["max_total_calls"],
        max_result_bytes=readable["max_result_bytes"],
    )


def tool_result_tokens_ceiling(
    limits: DispatcherLimits, *, characters_per_token: Decimal
) -> int:
    """The most one tool result could weigh, in tokens rather than bytes.

    The dispatcher measures a result in bytes, and a bill is measured in
    tokens, so the two have to be brought together somewhere. Dividing by the
    same characters-per-token figure the rest of the comparison uses keeps that
    conversion in one place and visible.
    """
    if characters_per_token <= 0:
        raise ValueError("characters_per_token must be greater than zero")
    tokens = Decimal(limits.max_result_bytes) / characters_per_token
    return int(tokens.to_integral_value(rounding=ROUND_CEILING))


@dataclass(frozen=True)
class StageOneConditions:
    """The settings a stage-one run would use.

    Deliberately smaller than the full comparison's conditions: stage one is
    not a scored comparison and does not need to match the other run places on
    every point. It needs to answer one question — does asking the model
    repeatedly help at all — for the least money that can answer it.
    """

    resource: str
    """The Microsoft Foundry resource the deployment lives in.

    A deployment name on its own does not name a model: the same name in a
    different resource is a different deployment. Read from the plan's own
    ``azure_connection`` block rather than written down a second time.
    """

    deployment: str
    resolved_model: str
    task_ids: tuple[str, ...]
    tool_calls_per_attempt: int
    """How many times the model may be asked again inside one attempt.

    Never more than the dispatcher's own ceiling: the dispatcher refuses
    further tool calls beyond it, so allowing more here would price turns that
    could never happen.
    """

    max_output_tokens_per_turn: int
    """The most the model may write in reply to one turn.

    This is a separate number from the one the three-place comparison uses.
    There, one answer is written per task, so a generous cap costs little.
    Here an answer may be written on every turn, so the same generous cap is
    multiplied by the number of turns. A turn that only picks a tool needs very
    little room.
    """

    retry_max_attempts: int
    per_task_timeout_seconds: int

    def validated(self, limits: DispatcherLimits) -> "StageOneConditions":
        """Refuse settings the dispatcher would not honour anyway."""
        if self.tool_calls_per_attempt < 1:
            raise ValueError(
                "a stage-one attempt asks the model at least once"
            )
        if self.tool_calls_per_attempt > limits.max_total_calls:
            raise ValueError(
                f"the settings allow {self.tool_calls_per_attempt} tool calls "
                f"in one attempt, but the dispatcher refuses anything past "
                f"{limits.max_total_calls}, so the extra turns would be priced "
                "but could never happen"
            )
        if self.max_output_tokens_per_turn < 1:
            raise ValueError(
                "a turn that may write nothing cannot produce an answer"
            )
        if self.retry_max_attempts < 0:
            raise ValueError("a task cannot be attempted a negative number of times")
        return self

    def as_run_conditions(self) -> ModelRunConditions:
        """Express these settings the way the shared cost arithmetic reads them.

        Reusing the comparison's own arithmetic rather than writing a second
        copy means a correction made in one place cannot be missed in the
        other.
        """
        return ModelRunConditions.from_mapping(
            {
                "provider": "azure",
                "resource": self.resource,
                "model_serving_path": (
                    SERVING_PATH_MICROSOFT_FOUNDRY_DEPLOYMENT
                ),
                "deployment": self.deployment,
                "resolved_model": self.resolved_model,
                "api_version": "2025-04-01-preview",
                "system_instruction": "",
                "task_instruction": "",
                "task_ids": list(self.task_ids),
                "input_file_versions": {},
                "max_output_tokens": self.max_output_tokens_per_turn,
                "per_task_timeout_seconds": self.per_task_timeout_seconds,
                # Stage one answers whether choosing tools helps. A second look
                # at the finished answer is a different question and would make
                # the result impossible to attribute, so it stays off.
                "self_review_enabled": False,
                "self_review_max_attempts": 0,
                "retry_reasons_allowed": ["infrastructure_error"],
                "retry_max_attempts": self.retry_max_attempts,
                "automatic_model_switch_allowed": False,
                # Stage one runs in one place only. Nothing may quietly take
                # that place's turn, and nothing may quietly answer for the
                # deployment named above.
                "automatic_fallback_allowed": False,
                "unsupported_runner_substitution_allowed": False,
            }
        )


def stage_one_ceiling(
    *,
    conditions: StageOneConditions,
    tasks_by_id: Mapping[str, CatalogTask],
    assumptions: CostAssumptions,
    limits: DispatcherLimits | None = None,
    prices: Mapping[str, ModelPrice] | None = None,
) -> CostCeiling:
    """The largest bill a stage-one run could produce.

    The tool-result size is not taken from the caller. It is read from the
    dispatcher, because that is the number that will actually be enforced when
    something runs.
    """
    dispatcher_limits = limits if limits is not None else read_dispatcher_limits()
    conditions = conditions.validated(dispatcher_limits)
    place = ENVIRONMENT_AGENTIC_SANDBOX_V2
    stage_one_assumptions = dataclasses.replace(
        assumptions,
        tool_loop_max_model_turns={
            place: conditions.tool_calls_per_attempt,
        },
        # Each turn is its own request with its own cap on how much may be
        # written, unlike the Azure code interpreter where one cap covers the
        # whole reply. So a full-length answer is possible on every turn.
        output_tokens_capped_per_attempt={place: False},
        max_tool_result_tokens_per_turn={
            place: tool_result_tokens_ceiling(
                dispatcher_limits,
                characters_per_token=assumptions.characters_per_token,
            ),
        },
    )
    return estimate_cost_ceiling(
        conditions_by_environment={place: conditions.as_run_conditions()},
        tasks_by_id=tasks_by_id,
        assumptions=stage_one_assumptions,
        prices=prices,
    )


class StageOneBudgetExceeded(RuntimeError):
    """Raised when a run has already spent more than it was allowed to."""


@dataclass
class StageOneBudget:
    """Counts what a stage-one run has spent and refuses to let it spend more.

    A worked-out ceiling that nothing enforces is a hope. This is the part that
    makes it a limit: a loop asks :meth:`refusal_before_next_call` before every
    call and stops when it gets an answer, and reports what each call actually
    used with :meth:`record`.

    Reporting more than was allowed raises rather than returning quietly. The
    reason is that a loop which has already overspent has lost the thread of
    what it is doing, and the only safe thing left is to stop loudly. Silently
    carrying on and reporting the overspend afterwards is how a small mistake
    becomes a large bill.
    """

    max_model_calls: int
    max_input_tokens: int
    max_output_tokens: int
    model_calls_made: int = 0
    input_tokens_used: int = 0
    output_tokens_used: int = 0

    def __post_init__(self) -> None:
        for name in ("max_model_calls", "max_input_tokens", "max_output_tokens"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{name} must be a plain whole number")
            if value < 0:
                raise ValueError(f"{name} cannot be below zero")

    def refusal_before_next_call(self) -> str | None:
        """Why the next call must not be made, or ``None`` if it may be.

        Checked before the call rather than after it, because after it the
        money is already spent.
        """
        if self.model_calls_made >= self.max_model_calls:
            return (
                f"this run has already made {self.model_calls_made} model "
                f"calls, which is all the {self.max_model_calls} it was allowed"
            )
        if self.input_tokens_used >= self.max_input_tokens:
            return (
                f"this run has already sent {self.input_tokens_used} tokens, "
                f"which is all the {self.max_input_tokens} it was allowed"
            )
        if self.output_tokens_used >= self.max_output_tokens:
            return (
                f"this run has already been sent back "
                f"{self.output_tokens_used} tokens, which is all the "
                f"{self.max_output_tokens} it was allowed"
            )
        return None

    def record(self, *, input_tokens: int, output_tokens: int) -> None:
        """Add what one call used, and refuse to go past any ceiling."""
        for name, value in (
            ("input_tokens", input_tokens),
            ("output_tokens", output_tokens),
        ):
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{name} must be a plain whole number")
            if value < 0:
                raise ValueError(f"{name} cannot be below zero")
        self.model_calls_made += 1
        self.input_tokens_used += input_tokens
        self.output_tokens_used += output_tokens
        passed = []
        if self.model_calls_made > self.max_model_calls:
            passed.append(
                f"{self.model_calls_made} model calls against a limit of "
                f"{self.max_model_calls}"
            )
        if self.input_tokens_used > self.max_input_tokens:
            passed.append(
                f"{self.input_tokens_used} tokens sent against a limit of "
                f"{self.max_input_tokens}"
            )
        if self.output_tokens_used > self.max_output_tokens:
            passed.append(
                f"{self.output_tokens_used} tokens received against a limit of "
                f"{self.max_output_tokens}"
            )
        if passed:
            raise StageOneBudgetExceeded(
                "a stage-one run has spent more than it was allowed: "
                + "; ".join(passed)
            )

    def as_dict(self) -> dict[str, Any]:
        return {
            "model_calls_allowed": self.max_model_calls,
            "model_calls_made": self.model_calls_made,
            "input_tokens_allowed": self.max_input_tokens,
            "input_tokens_used": self.input_tokens_used,
            "output_tokens_allowed": self.max_output_tokens,
            "output_tokens_used": self.output_tokens_used,
        }


def budget_for_one_task(ceiling: CostCeiling, task_id: str) -> StageOneBudget:
    """Build the running limit for one task from the worked-out ceiling.

    Taking the limit from the same figure that was approved, rather than from a
    number typed in beside it, means the two cannot drift apart. If the ceiling
    is recomputed the limit moves with it.
    """
    for environment in ceiling.environments:
        for task in environment.tasks:
            if task.task_id == task_id:
                return StageOneBudget(
                    max_model_calls=task.model_calls,
                    max_input_tokens=task.total_input_tokens,
                    max_output_tokens=task.total_output_tokens,
                )
    raise ValueError(
        f"the worked-out ceiling says nothing about task {task_id}, so there "
        "is no limit to hold it to"
    )


@dataclass(frozen=True)
class StageOneOption:
    """One candidate setting, with what it would cost at most.

    Running and marking are kept apart because they move for different
    reasons. Running the tasks is what these settings change; marking the
    answers costs the same whatever the settings are, and at the smaller
    settings it is most of the bill. Adding them into one figure would hide
    that, and would make a change to the settings look less effective than it
    is.
    """

    tool_calls_per_attempt: int
    max_output_tokens_per_turn: int
    most_running_model_calls: int
    most_grading_model_calls: int
    most_running_could_cost_usd: Decimal
    most_grading_could_cost_usd: Decimal
    most_it_could_cost_usd: Decimal

    def as_dict(self) -> dict[str, Any]:
        return {
            "tool_calls_per_attempt": self.tool_calls_per_attempt,
            "max_output_tokens_per_turn": self.max_output_tokens_per_turn,
            "most_running_model_calls": self.most_running_model_calls,
            "most_grading_model_calls": self.most_grading_model_calls,
            "most_running_could_cost_usd": _money(
                self.most_running_could_cost_usd
            ),
            "most_grading_could_cost_usd": _money(
                self.most_grading_could_cost_usd
            ),
            "most_it_could_cost_usd": _money(self.most_it_could_cost_usd),
        }


def _money(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_CEILING))


def price_the_options(
    *,
    base: StageOneConditions,
    tasks_by_id: Mapping[str, CatalogTask],
    assumptions: CostAssumptions,
    tool_call_choices: tuple[int, ...],
    output_token_choices: tuple[int, ...],
    limits: DispatcherLimits | None = None,
    prices: Mapping[str, ModelPrice] | None = None,
) -> list[StageOneOption]:
    """Work out what each candidate setting would cost at most.

    Presented as a list rather than a single figure on purpose. The decision
    stage one needs is not "may we spend the worked-out amount"; it is "which
    settings buy an answer worth having, for a price worth paying". That is a
    judgement, and a judgement needs the alternatives beside each other.

    Settings the dispatcher would refuse are left out rather than priced, so a
    reader is never offered a choice that could not be taken.
    """
    dispatcher_limits = limits if limits is not None else read_dispatcher_limits()
    options: list[StageOneOption] = []
    for tool_calls in sorted(set(tool_call_choices)):
        for output_tokens in sorted(set(output_token_choices)):
            candidate = dataclasses.replace(
                base,
                tool_calls_per_attempt=tool_calls,
                max_output_tokens_per_turn=output_tokens,
            )
            try:
                candidate.validated(dispatcher_limits)
            except ValueError:
                continue
            ceiling = stage_one_ceiling(
                conditions=candidate,
                tasks_by_id=tasks_by_id,
                assumptions=assumptions,
                limits=dispatcher_limits,
                prices=prices,
            )
            options.append(
                StageOneOption(
                    tool_calls_per_attempt=tool_calls,
                    max_output_tokens_per_turn=output_tokens,
                    most_running_model_calls=sum(
                        entry.model_calls for entry in ceiling.environments
                    ),
                    most_grading_model_calls=ceiling.grading_model_calls,
                    most_running_could_cost_usd=(
                        ceiling.running_usd * ceiling.safety_multiplier
                    ),
                    most_grading_could_cost_usd=(
                        ceiling.grading_usd * ceiling.safety_multiplier
                    ),
                    most_it_could_cost_usd=ceiling.total_usd,
                )
            )
    return options


# ── The free check that must pass before stage one spends anything ─────────

STAGE_ONE_PLAN_PATH = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "execution_envelope"
    / "agentic_stage_one_plan.yaml"
)

STAGE_ONE_PLAN_VERSION = "agentic-stage-one-v1"


@dataclass
class StageOnePreflight:
    """Whether stage one may start, and every reason it may not."""

    may_start: bool
    problems: list[str] = field(default_factory=list)
    options: list[StageOneOption] = field(default_factory=list)
    chosen: StageOneOption | None = None
    chosen_budget: dict[str, StageOneBudget] = field(default_factory=dict)
    """The limit each task would be held to, once a row has been chosen.

    Empty until a row is chosen, because until then there is no figure to hold
    anything to. Reported so that whoever approves an amount can see the limit
    that would actually stop a run, rather than only the amount.
    """

    approved_maximum_usd: Decimal | None = None
    dispatcher_limits: DispatcherLimits | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "may_start": self.may_start,
            "problems": list(self.problems),
            "options": [entry.as_dict() for entry in self.options],
            "chosen": self.chosen.as_dict() if self.chosen else None,
            "chosen_budget": {
                task_id: budget.as_dict()
                for task_id, budget in self.chosen_budget.items()
            },
            "approved_maximum_usd": (
                _money(self.approved_maximum_usd)
                if self.approved_maximum_usd is not None
                else None
            ),
            "dispatcher_limits": (
                dataclasses.asdict(self.dispatcher_limits)
                if self.dispatcher_limits
                else None
            ),
        }


def load_stage_one_plan(path: Any = None) -> dict:
    """Read the stage-one plan file."""
    import yaml

    target = Path(path) if path is not None else STAGE_ONE_PLAN_PATH
    if not target.is_file():
        raise ValueError(f"the stage-one plan is missing at {target}")
    raw = yaml.safe_load(target.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"the stage-one plan at {target} is not a mapping")
    if raw.get("plan_version") != STAGE_ONE_PLAN_VERSION:
        raise ValueError(
            "the stage-one plan was written for "
            f"{raw.get('plan_version')!r}, but this code reads "
            f"{STAGE_ONE_PLAN_VERSION!r}"
        )
    return raw


def check_stage_one_cannot_reach_a_model() -> list[str]:
    """Confirm nothing here can put a real model into the stage-one loop.

    The loop stage one is about now exists:
    :func:`core.agentic_v2_conversation.run_model_conversation` asks something,
    runs the tool it asked for, shows it what came back, and asks again. What
    does not exist is any way to reach a *real* model with it. The seam a real
    client would be plugged into refuses, because reaching one costs money in a
    loop and no amount has been approved for that.

    So stage one still cannot start, but for a different and much smaller
    reason than before, and the difference is worth stating rather than
    flattening into "not built yet".

    Everything below is established by running the code, not by reading it:
    the refusing seam is called and required to refuse, and the loop is run
    with a stand-in that declares itself paid and required to stop before
    asking it anything. A comment could say either of those and be wrong.
    """
    import inspect

    try:
        from core.agentic_v2_conversation import (
            GaveUp,
            LoopLimits,
            NoModelVoiceAvailable,
            ScriptedToolDesk,
            ScriptedVoice,
            StopReason,
            real_model_voice,
            run_model_conversation,
        )
    except ImportError as error:  # pragma: no cover - defensive
        return [
            "the Agentic Sandbox V2 model conversation could not be loaded, so "
            "whether a real model can be reached cannot be established: "
            f"{error}"
        ]

    problems: list[str] = []

    try:
        real_model_voice()
    except NoModelVoiceAvailable:
        pass
    except Exception as error:  # pragma: no cover - defensive
        problems.append(
            "asking for a real model failed in an unexpected way, so what "
            "would happen on a paid run is unknown: "
            f"{type(error).__name__}: {error}"
        )
    else:
        problems.append(
            "core.agentic_v2_conversation.real_model_voice now hands back a "
            "way to reach a real model. Stage one may be about to spend money "
            "in a loop, so before any paid run is allowed somebody must "
            "confirm the amount is approved here and that the loop still "
            "stops at the dispatcher's own tool-call ceiling"
        )

    would_be_charged_for = ScriptedVoice(
        replies=[GaveUp(note="never asked")], makes_paid_calls=True
    )
    refused = run_model_conversation(
        task_prompt="a check that spends nothing",
        voice=would_be_charged_for,
        desk=ScriptedToolDesk(),
        limits=LoopLimits(),
    )
    if refused.stop_reason is not StopReason.PAID_CALL_REFUSED:
        problems.append(
            "the stage-one loop no longer refuses a model that would be "
            "charged for: it stopped with "
            f"{refused.stop_reason.value!r} instead. That refusal is what "
            "keeps an unapproved paid run from starting by accident"
        )
    if would_be_charged_for.requests_seen:
        problems.append(
            "the stage-one loop asked a model that declares itself paid "
            "before refusing it, so the money would already have been spent "
            "by the time anything noticed"
        )

    try:
        from core.agentic_v2_runner import AgenticV2ScriptedRunner
    except ImportError as error:  # pragma: no cover - defensive
        problems.append(
            "the Agentic Sandbox V2 runner could not be loaded, so whether it "
            f"holds a model client cannot be established: {error}"
        )
    else:
        accepted = set(
            inspect.signature(AgenticV2ScriptedRunner.__init__).parameters
        )
        if accepted & {"model_client", "llm_client", "client"}:
            problems.append(
                "the Agentic Sandbox V2 runner now accepts a model client "
                "directly. That is a second route to a paid call which this "
                "check does not cover, and it must be reviewed before any "
                "stage-one run is allowed"
            )

    if problems:
        return problems
    return [
        "stage one cannot start because nothing here can reach a real model: "
        "the loop exists at core.agentic_v2_conversation.run_model_conversation "
        "and is proven against stand-ins that spend nothing, but "
        "real_model_voice refuses and the loop refuses any model that would be "
        "charged for. Approving an amount below is what removes this"
    ]


def run_stage_one_preflight(
    plan: Mapping[str, Any],
    *,
    tasks_by_id: Mapping[str, CatalogTask],
    assumptions: CostAssumptions,
    limits: DispatcherLimits | None = None,
    prices: Mapping[str, ModelPrice] | None = None,
) -> StageOnePreflight:
    """Work out what stage one could cost, and refuse to let it start.

    Every refusal is collected rather than the first one being returned, so a
    reader sees the whole list of what is missing instead of fixing one thing
    at a time.
    """
    from core.execution_environment_readiness import (
        check_agentic_sandbox_v2_blocks_are_intact,
    )

    problems: list[str] = []
    dispatcher_limits = limits if limits is not None else read_dispatcher_limits()

    if plan.get("safety_blocks_must_stay_closed") is not True:
        problems.append(
            "the stage-one plan no longer requires the three safety blocks to "
            "stay closed. Stage one does not open any of them, so this must "
            "stay true"
        )
    problems.extend(check_agentic_sandbox_v2_blocks_are_intact())
    problems.extend(check_stage_one_cannot_reach_a_model())

    fixed = dict(plan.get("fixed_settings") or {})
    if fixed.get("exec_run_open") is not False:
        problems.append(
            "the stage-one plan does not state that the command-running tool "
            "exec_run stays shut. Opening it is stage three and needs its own "
            "separate written approval"
        )
    if fixed.get("self_review_enabled") is not False:
        problems.append(
            "the stage-one plan switches self-review on. Stage one asks "
            "whether choosing tools helps; a second look at the finished "
            "answer is a different question and would make the result "
            "impossible to attribute to either"
        )
    if fixed.get("automatic_model_switch_allowed") is not False:
        problems.append(
            "the stage-one plan allows the run to change model or deployment "
            "on its own, which would leave a result no single model produced"
        )

    task_ids = tuple(str(value) for value in (plan.get("task_ids") or []))
    if not task_ids:
        problems.append("the stage-one plan names no task to run")

    model = dict(plan.get("model") or {})
    # The resource comes from the plan's own Azure block, which already names
    # it for the connection check. Asking the plan to write it twice would let
    # the two copies drift apart with nothing to notice.
    resource = str(
        (dict(plan.get("azure_connection") or {})).get("account") or ""
    )
    if not resource:
        problems.append(
            "the stage-one plan does not name the Microsoft Foundry resource "
            "its deployment lives in, so the deployment name on its own does "
            "not say which model would answer"
        )
    candidates = dict(plan.get("candidate_settings") or {})
    tool_call_choices = tuple(
        int(value) for value in (candidates.get("tool_calls_per_attempt") or [])
    )
    output_token_choices = tuple(
        int(value)
        for value in (candidates.get("max_output_tokens_per_turn") or [])
    )
    if not tool_call_choices or not output_token_choices:
        problems.append(
            "the stage-one plan offers no candidate settings to price, so "
            "there is nothing to choose between"
        )

    options: list[StageOneOption] = []
    if task_ids and tool_call_choices and output_token_choices:
        base = StageOneConditions(
            resource=resource,
            deployment=str(model.get("deployment") or ""),
            resolved_model=str(model.get("resolved_model") or ""),
            task_ids=task_ids,
            tool_calls_per_attempt=min(tool_call_choices),
            max_output_tokens_per_turn=min(output_token_choices),
            retry_max_attempts=int(fixed.get("retry_max_attempts", 0)),
            per_task_timeout_seconds=int(
                fixed.get("per_task_timeout_seconds", 1200)
            ),
        )
        options = price_the_options(
            base=base,
            tasks_by_id=tasks_by_id,
            assumptions=assumptions,
            tool_call_choices=tool_call_choices,
            output_token_choices=output_token_choices,
            limits=dispatcher_limits,
            prices=prices,
        )
        if not options:
            problems.append(
                "every candidate setting was refused by the dispatcher's own "
                f"ceiling of {dispatcher_limits.max_total_calls} tool calls, "
                "so there is nothing that could be run"
            )

    cost = dict(plan.get("cost") or {})
    chosen_raw = dict(cost.get("chosen_settings") or {})
    chosen_calls = chosen_raw.get("tool_calls_per_attempt")
    chosen_output = chosen_raw.get("max_output_tokens_per_turn")
    chosen: StageOneOption | None = None
    chosen_budget: dict[str, StageOneBudget] = {}
    if chosen_calls is None or chosen_output is None:
        problems.append(
            "no settings have been chosen for stage one. Pick one row from "
            "the table above and write its two numbers into "
            "cost.chosen_settings"
        )
    else:
        for option in options:
            if (
                option.tool_calls_per_attempt == int(chosen_calls)
                and option.max_output_tokens_per_turn == int(chosen_output)
            ):
                chosen = option
                break
        if chosen is None:
            problems.append(
                f"the chosen settings — {chosen_calls} tool calls and "
                f"{chosen_output} tokens per turn — are not one of the "
                "candidates that was priced, so nobody has seen what they "
                "would cost"
            )
        else:
            # Work out the limit each task would actually be stopped by, from
            # the same figures the price came from. Reported rather than only
            # computed, so an approver sees the limit and not just the amount.
            chosen_ceiling = stage_one_ceiling(
                conditions=StageOneConditions(
                    resource=resource,
                    deployment=str(model.get("deployment") or ""),
                    resolved_model=str(model.get("resolved_model") or ""),
                    task_ids=task_ids,
                    tool_calls_per_attempt=chosen.tool_calls_per_attempt,
                    max_output_tokens_per_turn=(
                        chosen.max_output_tokens_per_turn
                    ),
                    retry_max_attempts=int(fixed.get("retry_max_attempts", 0)),
                    per_task_timeout_seconds=int(
                        fixed.get("per_task_timeout_seconds", 1200)
                    ),
                ),
                tasks_by_id=tasks_by_id,
                assumptions=assumptions,
                limits=dispatcher_limits,
                prices=prices,
            )
            chosen_budget = {
                task_id: budget_for_one_task(chosen_ceiling, task_id)
                for task_id in task_ids
            }

    approved_raw = cost.get("approved_maximum_usd")
    approved: Decimal | None = None
    if approved_raw is None:
        problems.append(
            "nobody has written down the largest amount that may be spent on "
            "stage one. The 32.23 United States dollars approved for the "
            "three-place comparison was for that comparison and does not "
            "extend here"
        )
    else:
        try:
            approved = Decimal(str(approved_raw))
        except Exception:
            problems.append(
                f"the largest amount that may be spent, {approved_raw!r}, is "
                "not a number"
            )
        else:
            if approved <= 0:
                problems.append(
                    "the largest amount that may be spent must be greater "
                    "than zero"
                )
            elif chosen is not None and chosen.most_it_could_cost_usd > approved:
                problems.append(
                    "the most the chosen settings could cost, "
                    f"{_money(chosen.most_it_could_cost_usd)} United States "
                    f"dollars, is above the {_money(approved)} that was "
                    "approved"
                )

    return StageOnePreflight(
        may_start=not problems,
        problems=problems,
        options=options,
        chosen=chosen,
        chosen_budget=chosen_budget,
        approved_maximum_usd=approved,
        dispatcher_limits=dispatcher_limits,
    )


def describe_stage_one_preflight(result: StageOnePreflight) -> list[str]:
    """The report a person reads, with the table the decision needs."""
    lines: list[str] = []
    if result.dispatcher_limits is not None:
        lines.append(
            "The tool dispatcher refuses more than "
            f"{result.dispatcher_limits.max_total_calls} tool calls in one "
            "run, and cuts any single tool result off at "
            f"{result.dispatcher_limits.max_result_bytes} bytes. Both figures "
            "are read from core/agentic_v2_tools.py, not copied into a "
            "document."
        )
        lines.append("")
    if result.options:
        lines.append("What each candidate setting could cost at most")
        lines.append("-" * 74)
        lines.append(
            f"{'tool calls':>10}  {'write cap':>10}  {'running':>10}  "
            f"{'marking':>10}  {'total':>10}"
        )
        for option in result.options:
            written = option.as_dict()
            lines.append(
                f"{option.tool_calls_per_attempt:>10}  "
                f"{option.max_output_tokens_per_turn:>10}  "
                f"{'$' + written['most_running_could_cost_usd']:>10}  "
                f"{'$' + written['most_grading_could_cost_usd']:>10}  "
                f"{'$' + written['most_it_could_cost_usd']:>10}"
            )
        lines.append("")
        lines.append(
            "Marking costs the same whatever the settings are. Only the "
            "running column moves when the settings change."
        )
        lines.append("")
    if result.chosen is not None:
        written = result.chosen.as_dict()
        lines.append(
            f"Chosen: {result.chosen.tool_calls_per_attempt} tool calls, "
            f"{result.chosen.max_output_tokens_per_turn} tokens per turn, at "
            f"most ${written['most_it_could_cost_usd']} in total"
        )
        if result.chosen_budget:
            lines.append("")
            lines.append(
                "Each task would be stopped by these limits, whatever it is "
                "doing at the time:"
            )
            for task_id in sorted(result.chosen_budget):
                budget = result.chosen_budget[task_id]
                lines.append(
                    f"  {task_id}: at most {budget.max_model_calls} model "
                    f"calls, {budget.max_input_tokens} tokens sent, "
                    f"{budget.max_output_tokens} tokens received"
                )
        lines.append("")
    if result.problems:
        lines.append("Stage one must not start yet, because:")
        for note in result.problems:
            lines.append(f"  - {note}")
    else:
        lines.append("Every stage-one condition is met.")
    return lines
