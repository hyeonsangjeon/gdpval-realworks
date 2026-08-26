"""Work out the most the run-place comparison could ever cost, before it starts.

Every number here is a ceiling, not a forecast. The question it answers is: *if
everything that is allowed to be retried is retried, and every answer runs to
the full length the settings permit, what is the largest bill that could
arrive?* A run is only allowed to start once that ceiling is written down and
approved.

The ceiling is built from four things, all of them visible:

* the price list committed at :data:`PRICE_TABLE_PATH`;
* the fixed model run conditions, which cap how long an answer may be and how
  many times a task may be attempted;
* the task catalogue, which says how long each task's wording is and how many
  reference files it ships with;
* a small set of written assumptions, each of which has to be stated by the
  operator rather than guessed here.

Nothing in this module contacts a provider or spends anything.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_CEILING
from pathlib import Path
from typing import Any, Mapping

from core.execution_envelope_tasks import CatalogTask
from core.execution_environment_readiness import ModelRunConditions

PRICE_TABLE_PATH = (
    Path(__file__).resolve().parents[1]
    / "experiments"
    / "execution_envelope"
    / "model_price_table.json"
)

PRICE_TABLE_SCHEMA_VERSION = "execution-envelope-price-table-v1"

TOKENS_PER_MILLION = Decimal(1_000_000)

# core/file_reader.py cuts every reference file off at this many characters
# before it reaches the model, so no single reference file can push the input
# beyond this no matter how large the file on disk is.
REFERENCE_FILE_CHARACTER_CAP = 50_000


@dataclass(frozen=True)
class ModelPrice:
    """What one model costs per million tokens, read from the committed list."""

    model: str
    input_usd_per_million: Decimal
    output_usd_per_million: Decimal

    def cost_of(self, *, input_tokens: int, output_tokens: int) -> Decimal:
        return (
            Decimal(input_tokens) * self.input_usd_per_million
            + Decimal(output_tokens) * self.output_usd_per_million
        ) / TOKENS_PER_MILLION


def load_price_table(path: str | Path | None = None) -> dict[str, ModelPrice]:
    """Read the committed price list."""
    target = Path(path) if path is not None else PRICE_TABLE_PATH
    if not target.is_file():
        raise ValueError(f"the price list is missing at {target}")
    raw = json.loads(target.read_text(encoding="utf-8"))
    if raw.get("schema_version") != PRICE_TABLE_SCHEMA_VERSION:
        raise ValueError(
            "the price list was written for "
            f"{raw.get('schema_version')!r}, but this code reads "
            f"{PRICE_TABLE_SCHEMA_VERSION!r}"
        )
    if raw.get("currency") != "USD":
        raise ValueError("the price list must be in United States dollars")
    prices: dict[str, ModelPrice] = {}
    for model, entry in dict(raw.get("models") or {}).items():
        prices[str(model)] = ModelPrice(
            model=str(model),
            input_usd_per_million=Decimal(str(entry["input_usd_per_million"])),
            output_usd_per_million=Decimal(str(entry["output_usd_per_million"])),
        )
    if not prices:
        raise ValueError("the price list names no model")
    return prices


@dataclass(frozen=True)
class CostAssumptions:
    """The written guesses the ceiling rests on.

    Each one has to be stated on purpose. None of them is filled in here from
    thin air, because an unstated assumption is exactly how a cost ceiling ends
    up being wrong in the direction that costs money.
    """

    characters_per_token: Decimal
    """How many characters of wording are counted as one token. A smaller
    number produces a larger, safer ceiling."""

    instruction_character_count: int
    """The combined length of the system instruction and the task instruction
    that is sent with every call."""

    tool_loop_max_model_turns: Mapping[str, int]
    """For each run place, the most times the model may be asked again inside a
    single attempt while it is still talking to its tools. A place that never
    loops uses 1."""

    output_tokens_capped_per_attempt: Mapping[str, bool]
    """For each run place, whether the cap on how much the model may write
    applies to a whole attempt or to each turn inside it.

    Azure's Responses API caps the whole reply, tool turns included, with one
    number, so its answer length is counted once per attempt. A place that
    sends a fresh request per turn is counted once per turn."""

    max_tool_result_tokens_per_turn: Mapping[str, int]
    """For each run place, the most one tool result may add to the conversation.

    This only matters where the model is asked more than once inside an
    attempt. Each turn re-reads every tool result that came before it, so this
    number is charged again on every later turn of the same attempt. A place
    that asks the model once per attempt carries nothing forward and may state
    0."""

    safety_multiplier: Decimal
    """A final multiplier applied to the whole ceiling, to leave room for
    counting that turns out to be optimistic."""

    grading_required: bool
    grading_model: str
    grading_calls_per_rubric_item: Decimal
    grading_input_tokens_per_call: int
    grading_output_tokens_per_call: int

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "CostAssumptions":
        required = (
            "characters_per_token",
            "instruction_character_count",
            "tool_loop_max_model_turns",
            "output_tokens_capped_per_attempt",
            "max_tool_result_tokens_per_turn",
            "safety_multiplier",
            "grading_required",
            "grading_model",
            "grading_calls_per_rubric_item",
            "grading_input_tokens_per_call",
            "grading_output_tokens_per_call",
        )
        missing = sorted(set(required) - set(raw))
        if missing:
            raise ValueError(
                "the cost assumptions are missing: " + ", ".join(missing)
            )
        characters_per_token = Decimal(str(raw["characters_per_token"]))
        if characters_per_token <= 0:
            raise ValueError("characters_per_token must be greater than zero")
        safety_multiplier = Decimal(str(raw["safety_multiplier"]))
        if safety_multiplier < 1:
            raise ValueError(
                "safety_multiplier must be at least 1, so the ceiling is never "
                "lowered below what the counting produced"
            )
        turns = {
            str(key): int(value)
            for key, value in dict(raw["tool_loop_max_model_turns"]).items()
        }
        for place, value in turns.items():
            if value < 1:
                raise ValueError(
                    f"{place} allows {value} model turns inside one attempt; "
                    "every attempt asks the model at least once"
                )
        tool_result_tokens = {
            str(key): int(value)
            for key, value in dict(
                raw["max_tool_result_tokens_per_turn"]
            ).items()
        }
        for place, value in tool_result_tokens.items():
            if value < 0:
                raise ValueError(
                    f"{place} states {value} tokens per tool result; a tool "
                    "result cannot be shorter than nothing"
                )
        return cls(
            characters_per_token=characters_per_token,
            instruction_character_count=int(raw["instruction_character_count"]),
            tool_loop_max_model_turns=turns,
            output_tokens_capped_per_attempt={
                str(key): bool(value)
                for key, value in dict(
                    raw["output_tokens_capped_per_attempt"]
                ).items()
            },
            max_tool_result_tokens_per_turn=tool_result_tokens,
            safety_multiplier=safety_multiplier,
            grading_required=bool(raw["grading_required"]),
            grading_model=str(raw["grading_model"]),
            grading_calls_per_rubric_item=Decimal(
                str(raw["grading_calls_per_rubric_item"])
            ),
            grading_input_tokens_per_call=int(raw["grading_input_tokens_per_call"]),
            grading_output_tokens_per_call=int(
                raw["grading_output_tokens_per_call"]
            ),
        )


@dataclass(frozen=True)
class AttemptCounts:
    """How many times one task could be billed, split by what is billed.

    ``model_calls`` is how many times the model is asked in total.
    ``answer_lengths`` is how many times a full answer of the maximum permitted
    length could be produced, which is what the output side is billed for. The
    two differ wherever one request may loop through several tool turns under a
    single cap on answer length.

    The input side needs a third and fourth number, because a request that
    loops does not send the same thing every time. ``looping_attempts`` counts
    the attempts that run the whole tool loop, and ``single_turn_calls`` counts
    the calls that ask the model exactly once and carry nothing forward — today
    that is the call each self-review makes to look at a finished answer.
    """

    model_calls: int
    answer_lengths: int
    looping_attempts: int
    single_turn_calls: int


def max_attempt_counts(
    conditions: ModelRunConditions,
    *,
    tool_loop_max_model_turns: int,
    output_tokens_capped_per_attempt: bool,
) -> AttemptCounts:
    """The most one task could be billed for, if nothing goes right.

    Counted as:

    * one first attempt, plus one more for each retry the settings allow after
      a network failure, a server error, or a timeout;
    * each of those attempts may ask the model up to
      ``tool_loop_max_model_turns`` times while it is still working with its
      tools;
    * on top of that, each self-review the settings allow costs one call to
      look at the finished answer and one further attempt to replace it, and
      that replacement may itself loop.

    When the cap on answer length covers a whole attempt rather than each turn
    inside it, the answer is counted once per attempt.
    """
    if tool_loop_max_model_turns < 1:
        raise ValueError("every attempt asks the model at least once")
    attempts = 1 + max(conditions.retry_max_attempts, 0)
    reviews = (
        max(conditions.self_review_max_attempts, 0)
        if conditions.self_review_enabled
        else 0
    )
    answers_per_attempt = 1 if output_tokens_capped_per_attempt else tool_loop_max_model_turns

    model_calls = attempts * tool_loop_max_model_turns
    answer_lengths = attempts * answers_per_attempt
    # Each self-review asks the model to inspect the finished answer, then to
    # produce a replacement, and the replacement may loop like any attempt.
    model_calls += reviews * (1 + tool_loop_max_model_turns)
    answer_lengths += reviews * (1 + answers_per_attempt)
    return AttemptCounts(
        model_calls=model_calls,
        answer_lengths=answer_lengths,
        looping_attempts=attempts + reviews,
        single_turn_calls=reviews,
    )


def max_input_tokens_per_attempt(
    *,
    base_input_tokens: int,
    tool_loop_max_model_turns: int,
    max_output_tokens: int,
    output_tokens_capped_per_attempt: bool,
    max_tool_result_tokens_per_turn: int,
) -> int:
    """The most one attempt could send, counting the conversation as it grows.

    A place that asks the model once per attempt sends the same thing every
    time, so its input is just what the task and the standing instructions
    weigh. A place that asks the model again after each tool result does not:
    every later turn re-reads the whole conversation so far, so what was
    written on turn one is paid for again on turns two, three, and onwards.

    Multiplying one turn's input by the number of turns therefore undercounts
    any loop. The count below adds, for each turn, everything that could
    already be in front of the model when that turn starts:

    * the task and the standing instructions, once per turn;
    * everything the model has written so far. Where one cap covers the whole
      attempt, the largest that can be is the whole cap, and the worst case for
      the bill is that it was all written early, so every later turn re-reads
      all of it. Where the cap applies to each turn separately, turn *k* can
      have at most *k* full-length answers behind it;
    * every tool result so far, at the largest a single result may be.

    The last two both grow with the turn number, which is why a loop's input
    rises faster than the number of turns. Doubling the turns roughly
    quadruples what the tool results cost.

    At one turn per attempt every added term is zero, so this returns exactly
    the base input and nothing about the two single-turn run places changes.
    """
    if tool_loop_max_model_turns < 1:
        raise ValueError("every attempt asks the model at least once")
    if max_tool_result_tokens_per_turn < 0:
        raise ValueError("a tool result cannot be shorter than nothing")
    turns = tool_loop_max_model_turns
    output = max(max_output_tokens, 0)
    # 0 + 1 + ... + (turns - 1): how many earlier turns each turn re-reads,
    # summed over the whole attempt.
    earlier_turn_pairs = turns * (turns - 1) // 2
    if output_tokens_capped_per_attempt:
        # One cap covers the attempt. Worst case for the bill: it is spent on
        # the first turn, so each of the remaining turns re-reads all of it.
        written_so_far = (turns - 1) * output
    else:
        # A fresh cap per turn, so turn k can have k full answers behind it.
        written_so_far = earlier_turn_pairs * output
    tool_results_so_far = earlier_turn_pairs * max_tool_result_tokens_per_turn
    return turns * base_input_tokens + written_so_far + tool_results_so_far


def max_input_tokens_per_call(
    task: CatalogTask, assumptions: CostAssumptions
) -> int:
    """The most one call could send, for this task.

    The task wording and the standing instructions are counted at their real
    length. Every reference file is counted at the cap the file reader applies,
    whatever the file's real size, because that cap is what actually reaches
    the model.
    """
    characters = (
        assumptions.instruction_character_count
        + task.prompt_character_count
        + task.reference_file_count * REFERENCE_FILE_CHARACTER_CAP
    )
    tokens = Decimal(characters) / assumptions.characters_per_token
    return int(tokens.to_integral_value(rounding=ROUND_CEILING))


@dataclass
class TaskCostCeiling:
    """The most one task could cost in one run place."""

    task_id: str
    model_calls: int
    answer_lengths: int
    input_tokens_per_call: int
    input_tokens_per_attempt: int
    output_tokens_per_call: int
    total_input_tokens: int
    total_output_tokens: int
    usd: Decimal

    def as_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "most_model_calls": self.model_calls,
            "most_full_length_answers": self.answer_lengths,
            "most_input_tokens_in_the_first_turn": self.input_tokens_per_call,
            "most_input_tokens_across_one_attempt": (
                self.input_tokens_per_attempt
            ),
            "most_output_tokens_per_answer": self.output_tokens_per_call,
            "most_input_tokens_in_total": self.total_input_tokens,
            "most_output_tokens_in_total": self.total_output_tokens,
            "most_it_could_cost_usd": _money(self.usd),
        }


@dataclass
class EnvironmentCostCeiling:
    """The most one run place could cost across all its tasks."""

    environment: str
    deployment: str
    resolved_model: str
    model_calls: int
    usd: Decimal
    tasks: list[TaskCostCeiling] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "environment": self.environment,
            "deployment": self.deployment,
            "resolved_model": self.resolved_model,
            "most_model_calls": self.model_calls,
            "most_it_could_cost_usd": _money(self.usd),
            "tasks": [entry.as_dict() for entry in self.tasks],
        }


@dataclass
class CostCeiling:
    """The whole ceiling: every run place, plus grading if it is needed."""

    environments: list[EnvironmentCostCeiling]
    grading_usd: Decimal
    grading_model_calls: int
    safety_multiplier: Decimal
    unpriced_models: list[str] = field(default_factory=list)

    @property
    def running_usd(self) -> Decimal:
        return sum(
            (entry.usd for entry in self.environments), start=Decimal(0)
        )

    @property
    def total_before_safety_usd(self) -> Decimal:
        return self.running_usd + self.grading_usd

    @property
    def total_usd(self) -> Decimal:
        return self.total_before_safety_usd * self.safety_multiplier

    @property
    def total_model_calls(self) -> int:
        return (
            sum(entry.model_calls for entry in self.environments)
            + self.grading_model_calls
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "environments": [entry.as_dict() for entry in self.environments],
            "grading": {
                "most_model_calls": self.grading_model_calls,
                "most_it_could_cost_usd": _money(self.grading_usd),
            },
            "most_model_calls_in_total": self.total_model_calls,
            "most_running_could_cost_usd": _money(self.running_usd),
            "most_before_safety_multiplier_usd": _money(
                self.total_before_safety_usd
            ),
            "safety_multiplier": str(self.safety_multiplier),
            "most_the_whole_thing_could_cost_usd": _money(self.total_usd),
            "models_with_no_published_price": list(self.unpriced_models),
        }


def _money(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_CEILING))


def estimate_cost_ceiling(
    *,
    conditions_by_environment: Mapping[str, ModelRunConditions],
    tasks_by_id: Mapping[str, CatalogTask],
    assumptions: CostAssumptions,
    prices: Mapping[str, ModelPrice] | None = None,
) -> CostCeiling:
    """Work out the largest bill the comparison could produce.

    A model with no published price is not treated as free. It is listed in
    ``unpriced_models`` so the check that reads this refuses to start.
    """
    price_table = dict(prices) if prices is not None else load_price_table()
    unpriced: set[str] = set()
    environments: list[EnvironmentCostCeiling] = []

    for environment in sorted(conditions_by_environment):
        conditions = conditions_by_environment[environment]
        turns = assumptions.tool_loop_max_model_turns.get(environment)
        if turns is None:
            raise ValueError(
                f"{environment} has no written limit on how many times the "
                "model may be asked again inside one attempt"
            )
        price = price_table.get(conditions.resolved_model)
        if price is None:
            unpriced.add(conditions.resolved_model)
        capped = bool(
            assumptions.output_tokens_capped_per_attempt.get(environment, False)
        )
        tool_result_tokens = assumptions.max_tool_result_tokens_per_turn.get(
            environment
        )
        if tool_result_tokens is None:
            raise ValueError(
                f"{environment} has no written limit on how much one tool "
                "result may add to the conversation, so the input a looping "
                "attempt re-reads cannot be counted"
            )
        counts = max_attempt_counts(
            conditions,
            tool_loop_max_model_turns=turns,
            output_tokens_capped_per_attempt=capped,
        )
        entry = EnvironmentCostCeiling(
            environment=environment,
            deployment=conditions.deployment,
            resolved_model=conditions.resolved_model,
            model_calls=0,
            usd=Decimal(0),
        )
        for task_id in conditions.task_ids:
            task = tasks_by_id.get(task_id)
            if task is None:
                raise ValueError(
                    f"{environment} lists task {task_id}, which is not in the "
                    "task catalogue"
                )
            input_tokens = max_input_tokens_per_call(task, assumptions)
            output_tokens = max(conditions.max_output_tokens, 0)
            attempt_input = max_input_tokens_per_attempt(
                base_input_tokens=input_tokens,
                tool_loop_max_model_turns=turns,
                max_output_tokens=output_tokens,
                output_tokens_capped_per_attempt=capped,
                max_tool_result_tokens_per_turn=tool_result_tokens,
            )
            # Attempts that run the whole loop are charged the growing
            # conversation. The calls that ask the model once and carry nothing
            # forward are charged the base input on its own.
            total_input = (
                attempt_input * counts.looping_attempts
                + input_tokens * counts.single_turn_calls
            )
            total_output = output_tokens * counts.answer_lengths
            cost = (
                price.cost_of(
                    input_tokens=total_input, output_tokens=total_output
                )
                if price is not None
                else Decimal(0)
            )
            entry.tasks.append(
                TaskCostCeiling(
                    task_id=task_id,
                    model_calls=counts.model_calls,
                    answer_lengths=counts.answer_lengths,
                    input_tokens_per_call=input_tokens,
                    input_tokens_per_attempt=attempt_input,
                    output_tokens_per_call=output_tokens,
                    total_input_tokens=total_input,
                    total_output_tokens=total_output,
                    usd=cost,
                )
            )
            entry.model_calls += counts.model_calls
            entry.usd += cost
        environments.append(entry)

    grading_usd = Decimal(0)
    grading_calls = 0
    if assumptions.grading_required:
        grading_price = price_table.get(assumptions.grading_model)
        if grading_price is None:
            unpriced.add(assumptions.grading_model)
        graded_task_ids: set[str] = set()
        for conditions in conditions_by_environment.values():
            graded_task_ids.update(conditions.task_ids)
        # Every run place produces its own answer, and each answer is graded on
        # its own, so grading is counted once per run place per task.
        runs_to_grade = len(conditions_by_environment)
        for task_id in sorted(graded_task_ids):
            task = tasks_by_id[task_id]
            calls = int(
                (
                    Decimal(task.rubric_item_count)
                    * assumptions.grading_calls_per_rubric_item
                ).to_integral_value(rounding=ROUND_CEILING)
            )
            calls *= runs_to_grade
            grading_calls += calls
            if grading_price is not None:
                grading_usd += grading_price.cost_of(
                    input_tokens=calls * assumptions.grading_input_tokens_per_call,
                    output_tokens=calls
                    * assumptions.grading_output_tokens_per_call,
                )

    return CostCeiling(
        environments=environments,
        grading_usd=grading_usd,
        grading_model_calls=grading_calls,
        safety_multiplier=assumptions.safety_multiplier,
        unpriced_models=sorted(unpriced),
    )


def check_cost_ceiling(
    ceiling: CostCeiling, *, approved_maximum_usd: Any | None
) -> list[str]:
    """Refuse the run unless an approved amount covers the whole ceiling.

    A missing amount is a refusal, not a pass. So is a model whose price is not
    published, because an unpriced model would otherwise be counted as free.
    """
    problems: list[str] = []
    if ceiling.unpriced_models:
        problems.append(
            "no published price was found for these models, so the most this "
            "could cost cannot be worked out: "
            + ", ".join(ceiling.unpriced_models)
        )
    if approved_maximum_usd is None:
        problems.append(
            "nobody has written down the largest amount that may be spent, so "
            "there is nothing for the worked-out ceiling of "
            f"{_money(ceiling.total_usd)} United States dollars to be checked "
            "against"
        )
        return problems
    try:
        approved = Decimal(str(approved_maximum_usd))
    except Exception:
        problems.append(
            f"the largest amount that may be spent, {approved_maximum_usd!r}, "
            "is not a number"
        )
        return problems
    if approved <= 0:
        problems.append(
            "the largest amount that may be spent must be greater than zero"
        )
        return problems
    if ceiling.total_usd > approved:
        problems.append(
            "the most this could cost, "
            f"{_money(ceiling.total_usd)} United States dollars, is above the "
            f"{_money(approved)} that was approved"
        )
    return problems


def describe_cost_ceiling(ceiling: CostCeiling) -> list[str]:
    """A few readable lines a person can check the arithmetic against."""
    lines: list[str] = []
    for entry in ceiling.environments:
        lines.append(
            f"{entry.environment}: at most {entry.model_calls} model calls, "
            f"at most {_money(entry.usd)} United States dollars "
            f"(deployment {entry.deployment}, model {entry.resolved_model})"
        )
    if ceiling.grading_model_calls:
        lines.append(
            f"grading: at most {ceiling.grading_model_calls} model calls, "
            f"at most {_money(ceiling.grading_usd)} United States dollars"
        )
    lines.append(
        f"before the safety multiplier: "
        f"{_money(ceiling.total_before_safety_usd)} United States dollars"
    )
    lines.append(
        f"after multiplying by {ceiling.safety_multiplier}: "
        f"{_money(ceiling.total_usd)} United States dollars"
    )
    return lines
