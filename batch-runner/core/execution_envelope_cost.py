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
  reference files it ships with — a file is billed for what a preview of it
  can add to the prompt, not for its size on disk, since no run place sends
  the file itself as text;
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

# How much of one reference file may reach the model's prompt. The module that
# decides this is core/file_preview.py, which every run place goes through —
# not core/file_reader.py, whose 50,000-character cut is only reachable through
# PromptBuilder, and PromptBuilder is not built anywhere the pipeline runs.
#
# The previews really are capped, and far below this: 3,000 characters per file
# and 10,000 across all of them. Two things are not capped there — the column
# headers in the structure summary, and the file names in the headers written
# after the cut — so this figure is deliberately left far above the readable
# caps to cover them, and is required to stay above them. It is held against
# core/file_preview.py's own arithmetic by
# _check_the_plan_prices_what_the_files_add_to_the_prompt in
# core/execution_envelope_preflight.py, which refuses only if it drops below.
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
class PerceptionAssumptions:
    """What one kind of perception call is taken to cost, per call.

    Marking does not only read words. It can send a picture of the answer to a
    model that looks at pictures, and a sound clip to a model that listens. Each
    is a separate model, separately billed, and neither shows up anywhere in the
    text-marking numbers.

    ``input_tokens_per_call`` and ``output_tokens_per_call`` may be ``None``,
    which means **nobody has established them**. That is a refusal, not a zero.
    A picture whose size was never measured does not cost nothing; it costs an
    amount this repository cannot state, and the difference matters.
    """

    modality: str
    """Which kind of perception this is — ``vision`` or ``audio`` today."""

    model: str
    """The deployment marking would call for this kind of perception."""

    calls_per_task: int
    """The most times this may be called while marking one task's answer.

    Read from the marking settings, not chosen here. The free check compares
    this against the settings and refuses if it is lower.
    """

    input_tokens_per_call: int | None
    """How much one call is taken to send, or ``None`` if it is not known.

    Neither a picture's size nor a sound clip's length is fixed by any setting
    in this repository, so no settings file can bound this. Where a number is
    given it has to come from measurement, and where no measurement exists the
    honest value is ``None``.
    """

    output_tokens_per_call: int | None
    """How much one call is taken to write back, or ``None`` if not known.

    Worth reading twice: **nothing in this repository caps a perception reply.**
    ``core/perception/vision.py`` and ``core/perception/audio.py`` both call the
    Responses API without ``max_output_tokens``, so the only real limit is
    whatever the model itself will write. A number here is a measurement of what
    replies have been, never a promise about what they can be.
    """

    def as_dict(self) -> dict[str, Any]:
        return {
            "modality": self.modality,
            "model": self.model,
            "calls_per_task": self.calls_per_task,
            "input_tokens_per_call": self.input_tokens_per_call,
            "output_tokens_per_call": self.output_tokens_per_call,
        }

    @property
    def size_is_known(self) -> bool:
        return (
            self.input_tokens_per_call is not None
            and self.output_tokens_per_call is not None
        )


def _perception_from_mapping(
    raw: Mapping[str, Any],
) -> dict[str, PerceptionAssumptions]:
    """Read the optional per-modality perception block.

    Absent means the plan states nothing about perception. That is deliberately
    **not** read as "there is no perception" — whether marking would use it is
    settled by the marking settings, and
    :func:`core.execution_envelope_grading_cost.check_assumptions_cover_the_caps`
    is what compares the two and refuses on a mismatch.
    """
    block = raw.get("grading_perception")
    if block is None:
        return {}
    if not isinstance(block, Mapping):
        raise ValueError(
            "grading_perception must name each kind of perception separately"
        )
    parsed: dict[str, PerceptionAssumptions] = {}
    for modality, entry in block.items():
        if not isinstance(entry, Mapping):
            raise ValueError(
                f"grading_perception.{modality} must be a block of settings"
            )
        missing = sorted(
            {
                "model",
                "calls_per_task",
                "input_tokens_per_call",
                "output_tokens_per_call",
            }
            - set(entry)
        )
        if missing:
            raise ValueError(
                f"grading_perception.{modality} is missing: "
                + ", ".join(missing)
            )
        calls = int(entry["calls_per_task"])
        if calls < 0:
            raise ValueError(
                f"grading_perception.{modality} states {calls} calls per task; "
                "a call cannot happen fewer than no times"
            )
        def _size(key: str) -> int | None:
            value = entry[key]
            if value is None:
                return None
            number = int(value)
            if number < 0:
                raise ValueError(
                    f"grading_perception.{modality}.{key} is {number}; a call "
                    "cannot send or write less than nothing"
                )
            return number

        parsed[str(modality)] = PerceptionAssumptions(
            modality=str(modality),
            model=str(entry["model"]),
            calls_per_task=calls,
            input_tokens_per_call=_size("input_tokens_per_call"),
            output_tokens_per_call=_size("output_tokens_per_call"),
        )
    return parsed


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

    grading_perception: Mapping[str, PerceptionAssumptions] = field(
        default_factory=dict
    )
    """What each kind of perception call is taken to cost, keyed by modality.

    Optional, because a plan that marks nothing has nothing to say here. It is
    **not** optional in the sense that leaving it out makes perception free —
    the marking settings decide whether perception happens, and the free check
    compares the two and refuses when this is short.
    """

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
            grading_perception=_perception_from_mapping(raw),
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
    length. Every reference file is counted at
    :data:`REFERENCE_FILE_CHARACTER_CAP`, whatever the file's real size,
    because what reaches the model is a preview and a structure summary rather
    than the file — see the note on that constant for which module decides how
    much of one file gets through.
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
    perception_usd: Decimal = Decimal(0)
    perception_model_calls: int = 0
    perception_of_unknown_size: list[str] = field(default_factory=list)
    """Kinds of perception that would happen but whose size nobody has stated.

    Separate from ``unpriced_models`` because it is a different failure. There
    the price is missing; here the price is known but how much would be sent is
    not, so the multiplication has no second number. Both end in a refusal, and
    both must, since a missing number is not a zero.
    """

    perception_of_unknown_price: list[str] = field(default_factory=list)
    """Kinds of perception whose model has no published price.

    The sibling of :attr:`perception_of_unknown_size`, and the other way to
    reach the same zero: there the price is known and the size is not, here the
    size may well be known and the price is not. A kind can be in both, and
    then it is named in both, because being told only that the size was never
    measured invites the reader to think measuring it would produce a figure.
    """

    grading_model_with_no_price: str | None = None
    """The marking model, when no published price was found for it.

    ``None`` means marking's figure has nothing missing from it. The name is
    carried rather than worked out from ``grading_usd == 0``, because a figure
    of zero is exactly the thing this is here to stop anyone reading as a fact.
    """

    @property
    def running_usd(self) -> Decimal:
        return sum(
            (entry.usd for entry in self.environments), start=Decimal(0)
        )

    @property
    def total_before_safety_usd(self) -> Decimal:
        return self.running_usd + self.grading_usd + self.perception_usd

    @property
    def total_usd(self) -> Decimal:
        return self.total_before_safety_usd * self.safety_multiplier

    @property
    def total_model_calls(self) -> int:
        return (
            sum(entry.model_calls for entry in self.environments)
            + self.grading_model_calls
            + self.perception_model_calls
        )

    def what_the_totals_leave_out(self) -> list[str]:
        """Why the two totals are lower than the most this could cost.

        Empty means nothing is missing from them. Otherwise each entry names
        one thing that was counted in :attr:`total_model_calls` and put into no
        dollar figure anywhere — a call with no money against it.

        Both the readable lines and the written-out answer are built from this
        one list, so a reader and a machine cannot be told different things
        about the same totals.
        """
        reasons: list[str] = []
        if self.unpriced_models:
            reasons.append(
                "no published price was found for "
                + ", ".join(self.unpriced_models)
            )
        if self.perception_of_unknown_size:
            reasons.append(
                "how much "
                + ", ".join(self.perception_of_unknown_size)
                + " sends and writes back was never measured"
            )
        return reasons

    def as_dict(self) -> dict[str, Any]:
        return {
            "environments": [entry.as_dict() for entry in self.environments],
            "grading": {
                "most_model_calls": self.grading_model_calls,
                "most_it_could_cost_usd": _money(self.grading_usd),
                "model_with_no_published_price": self.grading_model_with_no_price,
            },
            "grading_perception": {
                "most_model_calls": self.perception_model_calls,
                "most_it_could_cost_usd": _money(self.perception_usd),
                "kinds_whose_size_is_unknown": list(
                    self.perception_of_unknown_size
                ),
                "kinds_whose_price_is_unknown": list(
                    self.perception_of_unknown_price
                ),
            },
            "most_model_calls_in_total": self.total_model_calls,
            "most_running_could_cost_usd": _money(self.running_usd),
            "most_before_safety_multiplier_usd": _money(
                self.total_before_safety_usd
            ),
            "safety_multiplier": str(self.safety_multiplier),
            "most_the_whole_thing_could_cost_usd": _money(self.total_usd),
            "models_with_no_published_price": list(self.unpriced_models),
            # Beside the totals rather than only in the parts, because a reader
            # who takes the total and nothing else is exactly the reader this
            # is for.
            "what_the_totals_leave_out": self.what_the_totals_leave_out(),
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
    perception_usd = Decimal(0)
    perception_calls = 0
    perception_unknown: list[str] = []
    perception_unpriced: list[str] = []
    grading_model_with_no_price: str | None = None
    if assumptions.grading_required:
        grading_price = price_table.get(assumptions.grading_model)
        if grading_price is None:
            unpriced.add(assumptions.grading_model)
            grading_model_with_no_price = assumptions.grading_model
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

        # Perception is charged per task rather than per scoring line: the
        # marking settings cap it that way, and one picture may answer several
        # scoring lines at once.
        for modality in sorted(assumptions.grading_perception):
            perception = assumptions.grading_perception[modality]
            if perception.calls_per_task <= 0:
                continue
            calls = (
                perception.calls_per_task * len(graded_task_ids) * runs_to_grade
            )
            perception_calls += calls
            price = price_table.get(perception.model)
            if price is None:
                unpriced.add(perception.model)
                # Named here as well as in ``unpriced_models`` so the line that
                # prints this figure can say which kind of perception the
                # missing money belongs to. "gpt-audio-1.5 has no price" does
                # not tell a reader that the listening calls are the ones with
                # nothing against them.
                perception_unpriced.append(
                    f"{perception.modality} ({perception.model})"
                )
            if not perception.size_is_known:
                # Say which kind, not just which model. A reader who is told
                # "gpt-5.4" learns nothing about which of its two jobs is the
                # one nobody measured.
                perception_unknown.append(
                    f"{perception.modality} ({perception.model})"
                )
                continue
            if price is not None:
                perception_usd += price.cost_of(
                    input_tokens=calls
                    * int(perception.input_tokens_per_call or 0),
                    output_tokens=calls
                    * int(perception.output_tokens_per_call or 0),
                )

    return CostCeiling(
        environments=environments,
        grading_usd=grading_usd,
        grading_model_calls=grading_calls,
        safety_multiplier=assumptions.safety_multiplier,
        unpriced_models=sorted(unpriced),
        perception_usd=perception_usd,
        perception_model_calls=perception_calls,
        perception_of_unknown_size=perception_unknown,
        perception_of_unknown_price=perception_unpriced,
        grading_model_with_no_price=grading_model_with_no_price,
    )


def read_approved_maximum(value: Any) -> tuple[Decimal | None, list[str]]:
    """Turn a written approved amount into a number, or say why it is not one.

    Shared so that two callers looking at the same written value cannot come to
    different conclusions about it. The missing case is deliberately left to the
    caller, because what is worth saying about a missing amount depends on
    whether there is a worked-out ceiling to say it against.

    ``.inf`` and ``.nan`` are ordinary YAML, so both reach here as real values.
    Neither is an amount anyone approved: an infinite limit permits every bill,
    and comparing a not-a-number against zero raises rather than answers. Both
    are refused by name instead of being allowed to pass or to crash.
    """
    try:
        approved = Decimal(str(value))
    except Exception:
        return None, [
            f"the largest amount that may be spent, {value!r}, is not a number"
        ]
    if not approved.is_finite():
        return None, [
            f"the largest amount that may be spent, {value!r}, is not a "
            "definite amount of money"
        ]
    if approved <= 0:
        return None, [
            "the largest amount that may be spent must be greater than zero"
        ]
    return approved, []


def check_approved_maximum(approved_maximum_usd: Any | None) -> list[str]:
    """Faults in the approved amount itself, with no ceiling to compare it to.

    ``check_cost_ceiling`` already does this on the way to comparing the amount
    against a worked-out ceiling. It is separated out for the case where no
    ceiling could be worked out at all: a policy that stops a run on cost still
    has to say whether the figure it would stop at is usable, and skipping the
    question because the other half of the sum failed is how a run with no
    approved amount, a negative one, or an infinite one gets to start.

    Missing, not a number, not a definite amount, and not above zero are all
    faults. None of them is read as zero dollars.
    """
    if approved_maximum_usd is None:
        return [
            "nobody has written down the largest amount that may be spent, and "
            "no ceiling could be worked out to check one against, so this "
            "run's only cost limit is missing"
        ]
    _, faults = read_approved_maximum(approved_maximum_usd)
    return faults


def check_cost_ceiling(
    ceiling: CostCeiling,
    *,
    approved_maximum_usd: Any | None,
    approved_maximum_required: bool = True,
) -> list[str]:
    """Report incomplete pricing and, when required, enforce an approved amount.

    Strict callers keep ``approved_maximum_required`` true, so a missing amount,
    an unpriced model, and an unmeasured perception call all become refusals.
    An explicitly owner-approved measurement run may set it false and treat the
    returned list as findings rather than blockers. The unknowns are still
    returned and are never priced as zero.
    """
    problems: list[str] = []
    if ceiling.unpriced_models:
        problems.append(
            "no published price was found for these models, so the most this "
            "could cost cannot be worked out: "
            + ", ".join(ceiling.unpriced_models)
        )
    if ceiling.perception_of_unknown_size:
        problems.append(
            "marking would call these, but how much each call sends and writes "
            "back has never been measured, so their cost is unknown rather "
            "than nothing: "
            + ", ".join(ceiling.perception_of_unknown_size)
        )
    if approved_maximum_usd is None:
        if not approved_maximum_required:
            return problems
        problems.append(
            "nobody has written down the largest amount that may be spent, so "
            "there is nothing for the worked-out ceiling of "
            f"{_money(ceiling.total_usd)} United States dollars to be checked "
            "against"
        )
        return problems
    approved, faults = read_approved_maximum(approved_maximum_usd)
    if approved is None:
        problems.extend(faults)
        return problems
    if ceiling.total_usd > approved:
        problems.append(
            "the most this could cost, "
            f"{_money(ceiling.total_usd)} United States dollars, is above the "
            f"{_money(approved)} that was approved"
        )
    return problems


def describe_cost_ceiling(ceiling: CostCeiling) -> list[str]:
    """A few readable lines a person can check the arithmetic against.

    Every money line here is headed "at most". Where a figure had calls counted
    against it that could not be turned into money, the line says so beside the
    figure. Two things can do that — a model nobody has published a price for,
    and a perception call nobody has measured — and both come out as the same
    zero, which is why neither may be left to speak for itself.
    """
    lines: list[str] = []
    for entry in ceiling.environments:
        line = (
            f"{entry.environment}: at most {entry.model_calls} model calls, "
            f"at most {_money(entry.usd)} United States dollars "
            f"(deployment {entry.deployment}, model {entry.resolved_model})"
        )
        if entry.resolved_model in ceiling.unpriced_models:
            line += (
                " — but no published price was found for "
                f"{entry.resolved_model}, so every one of those calls is in "
                "the count and in no figure"
            )
        lines.append(line)
    if ceiling.grading_model_calls:
        line = (
            f"grading: at most {ceiling.grading_model_calls} model calls, "
            f"at most {_money(ceiling.grading_usd)} United States dollars"
        )
        if ceiling.grading_model_with_no_price is not None:
            line += (
                " — but no published price was found for "
                f"{ceiling.grading_model_with_no_price}, so every one of those "
                "calls is in the count and in no figure"
            )
        lines.append(line)
    if ceiling.perception_model_calls:
        line = (
            "grading, looking and listening: at most "
            f"{ceiling.perception_model_calls} model calls, at most "
            f"{_money(ceiling.perception_usd)} United States dollars"
        )
        if ceiling.perception_of_unknown_size:
            # Without this the reader sees a dollar figure on the same line as a
            # call count that is larger than the figure accounts for, and has no
            # way to tell that some of those calls were priced at nothing.
            line += (
                " — but "
                + ", ".join(ceiling.perception_of_unknown_size)
                + " is not in that figure at all, because how much it sends was "
                "never measured"
            )
        if ceiling.perception_of_unknown_price:
            # The other way to the same zero. Said separately because a kind
            # that is missing both would otherwise leave a reader thinking a
            # measurement is all that stands between here and a figure.
            if ceiling.perception_of_unknown_size:
                line += (
                    " — and no published price was found for "
                    + ", ".join(ceiling.perception_of_unknown_price)
                    + ", so measuring it would not produce a figure either"
                )
            else:
                line += (
                    " — but no published price was found for "
                    + ", ".join(ceiling.perception_of_unknown_price)
                    + ", so every one of those calls is in the count and in "
                    "no figure"
                )
        lines.append(line)
    lines.append(
        f"before the safety multiplier: "
        f"{_money(ceiling.total_before_safety_usd)} United States dollars"
    )
    lines.append(
        f"after multiplying by {ceiling.safety_multiplier}: "
        f"{_money(ceiling.total_usd)} United States dollars"
    )
    left_out = ceiling.what_the_totals_leave_out()
    if left_out:
        # The parts already say this on their own lines. It is repeated on the
        # totals because the totals are what gets quoted, and a reader who
        # takes the last line and stops is the reader who most needs telling.
        lines.append(
            "WARNING: both totals above are lower than the most this could "
            "cost, because " + "; and ".join(left_out) + ". Those calls are "
            "counted in the model-call figures above "
            f"({ceiling.total_model_calls} in total) and in none of the money"
        )
    return lines
