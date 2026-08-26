"""What marking the answers could cost, read from the marking settings.

:mod:`core.execution_envelope_cost` opens by saying that every number in it is
a ceiling and not a forecast. The half that prices *running* the tasks keeps
that promise: it reads how many times the model may be asked again inside one
attempt and charges the conversation as it grows.

The half that prices *marking* the answers does not. It rests on three numbers
an operator writes into the plan by hand, and two of those three can be checked
against limits this repository already states in its own marking settings:

===========================  =============================  ==================
plan assumption              limit the marking settings set  where
===========================  =============================  ==================
grading_calls_per_rubric_    ``max_iterations`` plus the     ``judge.tools.
item                         finalisation retry             read_deliverable``
                                                            and ``grader.
                                                            judge_max_retries``
grading_output_tokens_per_   ``max_output_tokens``           ``judge.
call                                                         generation``
(no assumption at all)       ``perception.visual.call_cap_   ``judge.
                             per_task`` and the audio one    perception``
===========================  =============================  ==================

So this module reads those limits out of the marking settings file that will
actually be used, and reports where a stated assumption sits below one of them.
A stated assumption that sits below a limit is not a ceiling. It is a forecast
wearing a ceiling's name, and the whole point of the cost check is that the
largest possible bill is known before anything starts.

**One number cannot be pinned this way and is not pretended otherwise.**
``grading_input_tokens_per_call`` depends on how long the answer being marked
turns out to be, and nothing in the settings caps that. It stays an observation
drawn from runs that really happened, and :func:`describe_grading_caps` says so
out loud rather than letting a reader assume the whole sum became a ceiling.

The perception gap is the one that can hide a model entirely.
:func:`core.execution_envelope_cost.check_cost_ceiling` already refuses to let a
run start when a model it will call has no published price, on the stated
grounds that "an unpriced model would otherwise be counted as free". The
marking half never names the picture-reading or sound-listening models, so that
refusal has never had the chance to fire for them — and at the time of writing
the sound model in ``default_v2.yaml`` is not in the price list at all.

Nothing here contacts a provider, marks anything, or spends anything. It reads
two files and compares numbers.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

import yaml

from core.execution_envelope_cost import CostAssumptions, ModelPrice
from core.tool_calling_judge import ToolCallingJudge

# Where core/grader.py reads each limit from, and what it falls back to when
# the settings file leaves it out. These paths and fallbacks mirror
# Grader._build_tool_calling_judge; test_execution_envelope_grading_cost.py
# builds the real judge from the real settings and fails if they ever diverge,
# so this is a mirror that cannot go stale quietly.
JUDGE_TOOL_SETTINGS_PATH = ("judge", "tools", "read_deliverable")
JUDGE_GENERATION_SETTINGS_PATH = ("judge", "generation")
VISUAL_SETTINGS_PATH = ("judge", "perception", "visual")
AUDIO_SETTINGS_PATH = ("judge", "perception", "audio")

DEFAULT_VISUAL_CALLS_PER_TASK = 5
DEFAULT_AUDIO_CALLS_PER_TASK = 3


def _judge_default(field_name: str) -> Any:
    """The judge's own default for one of its limits.

    Read off :class:`~core.tool_calling_judge.ToolCallingJudge` rather than
    typed again here, so that changing the judge's default moves the ceiling
    with it instead of leaving this module quoting a number that no longer
    applies.
    """
    for field in fields(ToolCallingJudge):
        if field.name == field_name:
            return field.default
    raise ValueError(f"the judge has no limit named {field_name!r}")


def _dig(document: Mapping[str, Any], path: tuple[str, ...]) -> dict[str, Any]:
    """Follow a path of keys, treating anything missing as empty."""
    current: Any = document
    for key in path:
        if not isinstance(current, Mapping):
            return {}
        current = current.get(key)
    return dict(current) if isinstance(current, Mapping) else {}


def _model_named_in(settings: Mapping[str, Any]) -> str | None:
    """The model a perception block will call, or ``None`` if it is switched off.

    ``Grader._build_tool_calling_judge`` only builds a perception sub-judge when
    the block names a model or a deployment, so a block that names neither
    cannot call anything and is not counted.
    """
    for key in ("deployment", "model"):
        value = settings.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


@dataclass(frozen=True)
class GradingCaps:
    """The limits the marking settings really impose, read from the file."""

    settings_path: str
    judge_model: str
    judge_calls_per_rubric_item: int
    """The most times the model may be asked about one scoring line.

    ``max_iterations`` bounds the tool loop, and one finalisation retry may add
    a further turn on top of it. The judge clamps the retry count to at most
    one, so this is the whole story.

    The SDK-signature fallback inside the judge can issue a second
    ``responses.create`` within a single turn, but only after the first raised
    ``TypeError`` from the client's own method signature — before any request
    leaves the machine — so it cannot appear on a bill and is not counted here.
    """

    tool_calls_per_rubric_item: int
    """The most tool dispatches allowed for one scoring line. Tool dispatches
    are not themselves billed, but each one adds its result to the conversation
    that the next turn re-sends, so the number is recorded."""

    output_tokens_per_call: int
    visual_model: str | None
    visual_calls_per_task: int
    audio_model: str | None
    audio_calls_per_task: int

    @property
    def models_the_marking_can_call(self) -> tuple[str, ...]:
        """Every model the marking path can reach, named once each."""
        named = [self.judge_model, self.visual_model, self.audio_model]
        seen: list[str] = []
        for model in named:
            if model and model not in seen:
                seen.append(model)
        return tuple(seen)

    def as_dict(self) -> dict[str, Any]:
        return {
            "settings_path": self.settings_path,
            "judge_model": self.judge_model,
            "most_judge_calls_per_scoring_line": self.judge_calls_per_rubric_item,
            "most_tool_calls_per_scoring_line": self.tool_calls_per_rubric_item,
            "most_output_tokens_per_call": self.output_tokens_per_call,
            "picture_reading_model": self.visual_model,
            "most_picture_reading_calls_per_task": self.visual_calls_per_task,
            "sound_listening_model": self.audio_model,
            "most_sound_listening_calls_per_task": self.audio_calls_per_task,
            "models_the_marking_can_call": list(self.models_the_marking_can_call),
        }


def read_grading_caps(path: str | Path) -> GradingCaps:
    """Read the limits out of a marking settings file.

    Every fallback matches what ``core/grader.py`` uses when the file leaves a
    setting out, so the limits reported here are the limits the marking run
    would really apply.
    """
    target = Path(path)
    if not target.is_file():
        raise ValueError(f"the marking settings are missing at {target}")
    loaded = yaml.safe_load(target.read_text(encoding="utf-8"))
    if not isinstance(loaded, Mapping):
        raise ValueError(f"the marking settings at {target} are not a mapping")
    document: Mapping[str, Any] = loaded

    judge = document.get("judge")
    judge = judge if isinstance(judge, Mapping) else {}
    judge_model = str(judge.get("deployment") or judge.get("model") or "").strip()
    if not judge_model:
        raise ValueError(
            f"the marking settings at {target} name no model to mark with"
        )

    tool_settings = _dig(document, JUDGE_TOOL_SETTINGS_PATH)
    generation = _dig(document, JUDGE_GENERATION_SETTINGS_PATH)
    grader_settings = document.get("grader")
    grader_settings = (
        grader_settings if isinstance(grader_settings, Mapping) else {}
    )

    max_iterations = int(
        tool_settings.get("max_iterations", _judge_default("max_iterations"))
    )
    # core/grader.py passes grader.judge_max_retries in as the finalisation
    # retry count, and ToolCallingJudge.__post_init__ clamps it to at most one.
    finalisation_retries = min(
        int(
            grader_settings.get(
                "judge_max_retries", _judge_default("finalization_retries")
            )
        ),
        1,
    )
    tool_call_cap = int(
        tool_settings.get(
            "per_item_call_cap", _judge_default("per_item_tool_call_cap")
        )
    )
    output_tokens = int(
        generation.get(
            "max_output_tokens", _judge_default("max_output_tokens")
        )
    )

    visual = _dig(document, VISUAL_SETTINGS_PATH)
    audio = _dig(document, AUDIO_SETTINGS_PATH)
    visual_model = _model_named_in(visual)
    audio_model = _model_named_in(audio)

    return GradingCaps(
        settings_path=str(target),
        judge_model=judge_model,
        judge_calls_per_rubric_item=max(max_iterations + finalisation_retries, 0),
        tool_calls_per_rubric_item=max(tool_call_cap, 0),
        output_tokens_per_call=max(output_tokens, 0),
        visual_model=visual_model,
        visual_calls_per_task=(
            int(visual.get("call_cap_per_task", DEFAULT_VISUAL_CALLS_PER_TASK))
            if visual_model
            else 0
        ),
        audio_model=audio_model,
        audio_calls_per_task=(
            int(audio.get("call_cap_per_task", DEFAULT_AUDIO_CALLS_PER_TASK))
            if audio_model
            else 0
        ),
    )


def check_assumptions_cover_the_caps(
    assumptions: CostAssumptions,
    caps: GradingCaps,
    *,
    prices: Mapping[str, ModelPrice] | None = None,
) -> list[str]:
    """Report every way the written cost sum sits below the real limits.

    An empty list means the marking half of the ceiling is a ceiling. Anything
    in the list means it is a forecast, and the largest possible bill is larger
    than the number the run is being checked against.
    """
    problems: list[str] = []

    if not assumptions.grading_required:
        # Nothing is being marked, so nothing is being under-counted. This is
        # not a silent pass: the caller asked about a plan that marks nothing.
        return problems

    if assumptions.grading_model != caps.judge_model:
        problems.append(
            "the cost sum prices marking against "
            f"{assumptions.grading_model!r}, but {caps.settings_path} marks "
            f"with {caps.judge_model!r}"
        )

    stated_calls = assumptions.grading_calls_per_rubric_item
    if stated_calls < Decimal(caps.judge_calls_per_rubric_item):
        problems.append(
            f"the cost sum allows {stated_calls} marking calls per scoring "
            f"line, but {caps.settings_path} lets the model be asked "
            f"{caps.judge_calls_per_rubric_item} times about one line, so the "
            "worked-out ceiling is below the largest bill that could arrive"
        )

    if assumptions.grading_output_tokens_per_call < caps.output_tokens_per_call:
        problems.append(
            "the cost sum allows "
            f"{assumptions.grading_output_tokens_per_call} tokens of reply per "
            f"marking call, but {caps.settings_path} lets one reply run to "
            f"{caps.output_tokens_per_call}"
        )

    for label, model, calls in (
        ("reading pictures", caps.visual_model, caps.visual_calls_per_task),
        ("listening to sound", caps.audio_model, caps.audio_calls_per_task),
    ):
        if not model or calls <= 0:
            continue
        problems.append(
            f"{caps.settings_path} lets marking call {model!r} for {label} up "
            f"to {calls} times per task, and the cost sum counts none of it"
        )
        if prices is not None and model not in prices:
            problems.append(
                f"{model!r} has no published price, so what it could cost "
                "cannot be worked out at all — it is not zero"
            )

    return problems


def describe_grading_caps(caps: GradingCaps) -> list[str]:
    """Readable lines a person can check the limits against."""
    lines = [
        f"marking settings read: {caps.settings_path}",
        f"marking model: {caps.judge_model}",
        (
            "most marking calls about one scoring line: "
            f"{caps.judge_calls_per_rubric_item}"
        ),
        (
            "most tool uses on one scoring line: "
            f"{caps.tool_calls_per_rubric_item} (each one is re-read by every "
            "later turn)"
        ),
        f"most tokens in one reply: {caps.output_tokens_per_call}",
    ]
    if caps.visual_model:
        lines.append(
            f"reading pictures: {caps.visual_model}, at most "
            f"{caps.visual_calls_per_task} calls per task"
        )
    else:
        lines.append("reading pictures: switched off")
    if caps.audio_model:
        lines.append(
            f"listening to sound: {caps.audio_model}, at most "
            f"{caps.audio_calls_per_task} calls per task"
        )
    else:
        lines.append("listening to sound: switched off")
    lines.append(
        "how long each marking call's input runs is not capped by these "
        "settings — it follows the answer being marked, so that one number "
        "stays an observation and is not a ceiling"
    )
    return lines
