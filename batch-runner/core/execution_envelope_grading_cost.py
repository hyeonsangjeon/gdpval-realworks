"""What marking the answers could cost, read from the marking settings.

:mod:`core.execution_envelope_cost` opens by saying that every number in it is
a ceiling and not a forecast. The half that prices *running* the tasks keeps
that promise: it reads how many times the model may be asked again inside one
attempt and charges the conversation as it grows.

The half that prices *marking* the answers does not. It rests on three numbers
an operator writes into the plan by hand, and every one of the three can be
checked against a limit this repository already states somewhere:

===========================  =============================  ==================
plan assumption              limit that is already stated    where
===========================  =============================  ==================
grading_calls_per_rubric_    ``max_iterations`` plus the     ``judge.tools.
item                         finalisation retry             read_deliverable``
                                                            and ``grader.
                                                            judge_max_retries``
grading_output_tokens_per_   ``max_output_tokens``           ``judge.
call                                                         generation``
grading_input_tokens_per_    ``per_item_call_cap`` results,  ``judge.tools.
call                         each of at most                 read_deliverable``
                             ``MAX_CONTENT_CHARS``           and ``core/tools/
                             characters, plus what the       read_deliverable``
                             conversation opens with: the    and ``prompt.
                             standing instruction file and   tool_template``
                             the width the task preview is   and the judge's
                             cut to                          own default
(no assumption at all)       ``perception.visual.call_cap_   ``judge.
                             per_task`` and the audio one    perception``
===========================  =============================  ==================

So this module reads those limits out of the marking settings file that will
actually be used, and reports where a stated assumption sits below one of them.
A stated assumption that sits below a limit is not a ceiling. It is a forecast
wearing a ceiling's name, and the whole point of the cost check is that the
largest possible bill is known before anything starts.

**The third row is the one this module used to get wrong.** It said in its own
words that how much a marking call sends "depends on how long the answer being
marked turns out to be, and nothing in the settings caps that". Something does.
The judge never sees the answer whole: it asks for pieces through the
``read_deliverable`` tool, that tool refuses to hand back more than
``MAX_CONTENT_CHARS`` in one result, and ``per_item_call_cap`` — which this
module already reads, and already describes as a number where each result "is
re-read by every later turn" — says how many results can pile up in the
conversation. Multiply the two and divide by the characters-per-token ratio and
you have the most one marking call can be asked to re-read. Nothing was doing
that multiplication, so the plan priced 10,000 tokens a call where the settings
permit some fifty times that.

**The same row was wrong a second time, about the opening.** It said the
wording a marking conversation *starts* with — the standing instructions, the
scoring line being judged, and the first 500 characters of the task — "is not
capped by anything", and wrote one of those caps down in prose in the very
sentence that denied it. Two of the three are pinned by this repository and can
be read rather than described. The standing instructions are a committed file
named by ``prompt.tool_template``; the judge splits it in two and sends both
halves on every call, one as the ``instructions=`` argument and one inside the
message. The task preview is cut to
``ToolCallingJudge.task_prompt_truncate`` characters. Both are counted now,
from the places the marking run itself reads them, so a longer instruction file
raises the demanded figure by itself instead of leaving this module quoting a
number that has stopped being true.

**The third piece was the contradiction this module printed in its own report.**
It said the scoring line being judged "is not capped by anything", and in the
same breath the advance check headed the total it fed "the largest possible
bill". Both cannot be true: if one part of a sum is unbounded the sum has no
maximum, so either the ceiling was not a ceiling or the part was not unbounded.
The part was not unbounded. The scoring line comes from ``rubric_json`` in the
pinned dataset the check already locates and already verifies to all 64
characters of its fingerprint, and nothing anywhere truncates it — the judge
substitutes it whole into its template. It was never capped by a *setting*,
which is a different thing from not being bounded, and the sentence quietly
traded one for the other. It is measured now: the catalogue records how long
each task's longest scoring line is, and
:func:`core.execution_envelope_tasks.widest_scoring_line_characters` hands the
widest of them to :class:`GradingCaps`. Across the 220 tasks the longest is
1,203 characters.

When that measurement is absent, this module does not fall back to leaving it
out. :func:`check_assumptions_cover_the_caps` refuses, because leaving it out
is what produced a figure that called itself a maximum while omitting one of
its parts. A number nobody measured is not a small number.

``grader.task_prompt_truncate_chars`` earns its own warning. Nine settings
files carry it, every one of them saying 500, and no module reads it:
``core/grader.py`` builds the judge without passing it, so the judge applies
its own default and the setting has never done anything at all. This module
therefore counts the default, which is what the run applies, and reports the
setting as ignored when the two disagree — because a width an operator can edit
without effect is exactly how a number stops describing the run it is written
next to.

The perception gap is the one that can hide a model entirely.
:func:`core.execution_envelope_cost.check_cost_ceiling` already refuses to let a
run start when a model it will call has no published price, on the stated
grounds that "an unpriced model would otherwise be counted as free". The
marking half never names the picture-reading or sound-listening models, so that
refusal has never had the chance to fire for them — and at the time of writing
the sound model in ``default_v2.yaml`` is not in the price list at all.

**The perception caps were the same defect again, in three copies.** How many
picture-reading and sound-listening calls one task gets when the settings name
no number was written by hand in ``core/perception/vision.py``, written again
in ``core/grader.py``, and written a third time here; ``AUDIO_TRIM_SECONDS``
made a fourth. Nothing bound them together, and both perception constants were
labelled a hard per-task ceiling, which the settings have always been able to
raise. The note above this module's settings paths named the real-judge
comparison as what kept the fallbacks honest, but every committed settings file
names its own caps, so that comparison never reached a fallback on either side
of itself. Raising what the run falls back to without raising this copy would
have understated the perception line of any run whose settings stayed quiet,
and understating is the direction that costs more than it says. There is one
copy now, in the perception modules, and every reader imports it.

Nothing here contacts a provider, marks anything, or spends anything. It reads
two files and compares numbers.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from decimal import Decimal, ROUND_CEILING
from pathlib import Path
from typing import Any, Mapping

import yaml

from core.execution_envelope_cost import CostAssumptions, ModelPrice
from core.perception.audio import AUDIO_CALL_CAP
from core.perception.vision import VISION_CALL_CAP
from core.tool_calling_judge import ToolCallingJudge
from core.tools.read_deliverable import MAX_CONTENT_CHARS

# Where core/grader.py reads each limit from, and what it falls back to when
# the settings file leaves it out. These paths mirror
# Grader._build_tool_calling_judge; test_execution_envelope_grading_cost.py
# builds the real judge from the real settings and fails if they ever diverge.
#
# That comparison only ever sees what the committed settings say, and every
# one of them names its own perception caps. The fallbacks were therefore
# never reached on either side of it, so citing it as the thing that keeps
# them honest claimed more than it checked. They are no longer copied here at
# all: they are imported from the modules that define them, and
# test_perception_caps_have_one_source.py runs the same comparison against
# settings that name no cap, which is the only case that reaches them.
JUDGE_TOOL_SETTINGS_PATH = ("judge", "tools", "read_deliverable")
JUDGE_GENERATION_SETTINGS_PATH = ("judge", "generation")
VISUAL_SETTINGS_PATH = ("judge", "perception", "visual")
AUDIO_SETTINGS_PATH = ("judge", "perception", "audio")

#: Where ``core/grader.py:resolve_tool_prompt_path`` looks for the standing
#: instruction file, in the order it looks. ``prompt.template`` is the fallback
#: and is used with its filename swapped, which is mirrored below.
PROMPT_SETTINGS_PATH = ("prompt",)
FALLBACK_TOOL_TEMPLATE_NAME = "grader_judge_v2.md"

#: The setting that names how much of the task wording the judge is shown.
#: Read to be compared against what the judge really applies, not to be used:
#: nothing passes it to the judge, so it has never taken effect.
TASK_PROMPT_TRUNCATE_SETTING = ("grader", "task_prompt_truncate_chars")

#: Settings name the instruction file as a path relative to ``batch-runner``,
#: which is where the marking run is started from.
BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]

#: How many perception calls one task gets when the marking settings name no
#: number. Imported, never typed: the check refuses a plan that allows fewer
#: calls than the settings permit, so whenever a settings file leaves
#: ``call_cap_per_task`` out, this is the figure it refuses against. A second
#: copy here would let someone raise what the run falls back to and leave the
#: ceiling behind, understating the perception line of every such run -- the
#: direction that costs more than it says.
DEFAULT_VISUAL_CALLS_PER_TASK = VISION_CALL_CAP
DEFAULT_AUDIO_CALLS_PER_TASK = AUDIO_CALL_CAP


def resolve_standing_instructions_path(
    document: Mapping[str, Any], settings_path: str | Path = "the marking settings"
) -> Path:
    """Which file the settings name as the standing instructions.

    Mirrors ``core.grader.resolve_tool_prompt_path`` exactly, including its
    fallback of taking ``prompt.template`` and swapping the filename, and
    including returning the path as the settings write it rather than as an
    absolute location. Reports name it, and where this check happens to be
    running from is nobody else's business.

    It is mirrored rather than imported because importing ``core.grader`` pulls
    in the whole marking stack, and this module's promise is that it reads two
    files and spends nothing.
    ``test_execution_envelope_grading_cost.py`` puts the two side by side and
    fails if they ever disagree, so the mirror cannot go stale quietly.
    """
    prompt_settings = _dig(document, PROMPT_SETTINGS_PATH)
    configured = prompt_settings.get("tool_template")
    if configured:
        return Path(str(configured))
    template = prompt_settings.get("template")
    if not template:
        raise ValueError(
            f"{settings_path} names no standing instruction file under "
            "prompt.tool_template or prompt.template, so what every marking "
            "call opens with cannot be measured — and leaving it out would "
            "price the opening at nothing"
        )
    return Path(str(template)).with_name(FALLBACK_TOOL_TEMPLATE_NAME)


def standing_instructions_characters(
    named: Path, settings_path: str | Path = "the marking settings"
) -> int:
    """How long that file is, in characters rather than bytes.

    Characters, because the ratio it is divided by is characters per token. The
    v2 instruction file holds a handful of multi-byte characters, so counting
    bytes would quietly overstate it.

    A relative name is taken from ``batch-runner``, which is where the marking
    run is started from.
    """
    on_disk = named if named.is_absolute() else BATCH_RUNNER_ROOT / named
    if not on_disk.is_file():
        raise ValueError(
            f"{settings_path} names {named} as the standing instructions sent "
            f"on every marking call, and there is no file at {on_disk}. Its "
            "length cannot be guessed: leaving it out would price the opening "
            "of every marking conversation at nothing"
        )
    return len(on_disk.read_text(encoding="utf-8"))


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

    characters_per_tool_result: int
    """The most characters one tool result can hand back.

    Read from ``core/tools/read_deliverable.py`` rather than typed again here.
    That module ends every content read with ``text[:MAX_CONTENT_CHARS]``, so
    whatever the format-specific readers do on the way, this is the width of
    the door.

    The result is put into the conversation as JSON, which escapes quotes and
    newlines and so can only make it longer. Counting the characters before
    escaping keeps this a floor rather than an overstatement.
    """

    output_tokens_per_call: int

    standing_instructions_path: str
    """The file the judge sends as its standing instructions on every call.

    Named by ``prompt.tool_template``. Recorded so the reported figure can be
    traced back to a file someone can open and count, rather than to a number
    typed into this module.
    """

    characters_of_standing_instructions: int
    """How long that file is, in characters.

    The judge splits the template at its marker and sends the head as the
    ``instructions=`` argument and the tail inside the message, on every single
    call, so the whole file is on the wire every time.

    Counting the template as written is a floor rather than an overstatement in
    the case that matters: its placeholders are replaced by real content — the
    scoring line, the file names — which is longer than the placeholder text far
    more often than it is shorter, and no placeholder's replacement is bounded
    by anything this module can read.
    """

    characters_of_task_prompt_preview: int
    """How much of the task wording the judge is shown.

    Read off :class:`~core.tool_calling_judge.ToolCallingJudge` because that is
    where the run reads it. Every task in the committed catalogue is longer
    than this cut, so on the real dataset this width is always used in full.
    """

    task_prompt_preview_setting: int | None
    """What ``grader.task_prompt_truncate_chars`` says, if the file says it.

    Recorded only to be compared against the field above. Nothing passes this
    setting to the judge, so on its own it describes nothing.
    """

    visual_model: str | None
    visual_calls_per_task: int
    audio_model: str | None
    audio_calls_per_task: int
    characters_of_widest_scoring_line: int | None = None
    """How long the longest scoring line in the benchmark is, in characters.

    Every marking call carries the scoring line it is judging, so this sits on
    the wire beside the standing instructions and the task preview on all of
    the calls the cap allows.

    It does not come from the settings file — it comes from the dataset, via
    :func:`core.execution_envelope_tasks.widest_scoring_line_characters` — so
    :func:`read_grading_caps` cannot read it and the caller has to supply it.
    ``None`` therefore means *nobody measured it*, and that is deliberately not
    the same as zero: :func:`check_assumptions_cover_the_caps` refuses on
    ``None`` rather than working out an opening that leaves this part out. The
    figure that omitted it used to be printed under a heading calling it the
    largest possible bill. A width of zero or below is refused too, because no
    scoring line in this benchmark is blank, so a zero is a reading that failed
    rather than a line with no wording in it.
    """

    def input_tokens_carried_by_tool_results(
        self, characters_per_token: Decimal
    ) -> int:
        """The most one marking call can be asked to re-read, in tokens.

        Every tool result stays in the conversation, and every later turn sends
        the conversation again. So by the last turn a single call can be
        carrying every result the cap allowed, all at full width.

        This counts the tool results only. What the conversation opens with is
        counted by :meth:`input_tokens_the_conversation_opens_with`, and the
        two are added together by
        :meth:`input_tokens_one_call_must_cover`, which is the figure a plan
        has to reach.
        """
        characters = Decimal(self.tool_calls_per_rubric_item) * Decimal(
            self.characters_per_tool_result
        )
        tokens = characters / characters_per_token
        # Round up: a fraction of a token is still charged as a token. Decimal's
        # ``//`` truncates towards zero rather than flooring, so it would round
        # this number *down* and quietly lower the very ceiling being worked out.
        return int(tokens.to_integral_value(rounding=ROUND_CEILING))

    def input_tokens_the_conversation_opens_with(
        self, characters_per_token: Decimal
    ) -> int:
        """The most one marking call's opening can be, in tokens.

        Every marking call, including the very first one, carries the standing
        instruction file, the preview of the task wording, and the scoring line
        it is judging. None of the three depends on how the marking goes, so
        all three are on the wire for all of the calls the cap allows.

        The scoring line's width is not read from the settings — no setting
        bounds it — but it is not therefore unbounded. It is read from the
        dataset, where it is fixed at the pinned revision, and passed in.

        Adding it on top of the whole instruction file counts the template's
        own ``{{criterion}}`` placeholder twice, some fourteen characters. That
        is an overstatement of fourteen characters in a figure that is meant to
        be an upper bound, which is the direction an upper bound may be wrong
        in, and correcting it would mean this method assuming a placeholder
        spelling it cannot see.

        Raises :class:`ValueError` when the scoring line was never measured,
        rather than leaving it out. Leaving it out is what let the total call
        itself a maximum while one of its parts was described as uncapped. It
        raises on a width of zero for the same reason: no scoring line in this
        benchmark is blank, so a zero is a reading that failed, and treating it
        as a width would price the wording on every marking call at nothing.
        """
        if self.characters_of_widest_scoring_line is None:
            raise ValueError(
                "how wide the scoring line being judged can be was never "
                "measured, so what a marking call opens with cannot be worked "
                "out. It is not zero: every marking call carries the scoring "
                "line. Pass the width from the task catalogue "
                "(core.execution_envelope_tasks.widest_scoring_line_characters)"
            )
        if self.characters_of_widest_scoring_line <= 0:
            raise ValueError(
                "the widest scoring line in the benchmark came out as "
                f"{self.characters_of_widest_scoring_line} characters. No "
                "scoring line here is blank, so that is a reading that failed "
                "rather than a narrow line, and using it would price the "
                "wording every marking call carries at nothing"
            )
        characters = (
            Decimal(self.characters_of_standing_instructions)
            + Decimal(self.characters_of_task_prompt_preview)
            + Decimal(self.characters_of_widest_scoring_line)
        )
        tokens = characters / characters_per_token
        return int(tokens.to_integral_value(rounding=ROUND_CEILING))

    def input_tokens_one_call_must_cover(
        self, characters_per_token: Decimal
    ) -> int:
        """The figure a plan's input-per-call number has to reach.

        The two parts are rounded up separately and then added, rather than
        added and rounded once. That can demand one token more than the single
        rounding would, and it is worth the token: a person reading the report
        sees both parts and can add them up and get this number, instead of
        finding it a token off and wondering which of the three is wrong.

        This is now a ceiling on what one marking call can be asked to carry,
        not a floor under it. Everything on the wire is counted: the tool
        results the settings let pile up, the standing instructions, the task
        preview, and the scoring line. It raises rather than under-reports when
        the last of those was never measured.
        """
        return self.input_tokens_carried_by_tool_results(
            characters_per_token
        ) + self.input_tokens_the_conversation_opens_with(characters_per_token)

    @property
    def task_prompt_preview_setting_is_ignored(self) -> bool:
        """Whether the settings name a preview width the run will not apply."""
        return (
            self.task_prompt_preview_setting is not None
            and self.task_prompt_preview_setting
            != self.characters_of_task_prompt_preview
        )

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
            "most_characters_one_tool_result_returns": (
                self.characters_per_tool_result
            ),
            "most_output_tokens_per_call": self.output_tokens_per_call,
            "standing_instructions_read_from": self.standing_instructions_path,
            "characters_of_standing_instructions": (
                self.characters_of_standing_instructions
            ),
            "characters_of_task_wording_shown": (
                self.characters_of_task_prompt_preview
            ),
            "characters_of_widest_scoring_line": (
                self.characters_of_widest_scoring_line
            ),
            "task_wording_width_named_by_the_settings": (
                self.task_prompt_preview_setting
            ),
            "the_settings_width_is_ignored": (
                self.task_prompt_preview_setting_is_ignored
            ),
            "picture_reading_model": self.visual_model,
            "most_picture_reading_calls_per_task": self.visual_calls_per_task,
            "sound_listening_model": self.audio_model,
            "most_sound_listening_calls_per_task": self.audio_calls_per_task,
            "models_the_marking_can_call": list(self.models_the_marking_can_call),
        }


def read_grading_caps(
    path: str | Path,
    *,
    widest_scoring_line_characters: int | None = None,
) -> GradingCaps:
    """Read the limits out of a marking settings file.

    Every fallback matches what ``core/grader.py`` uses when the file leaves a
    setting out, so the limits reported here are the limits the marking run
    would really apply.

    ``widest_scoring_line_characters`` is the one figure that is not in this
    file and cannot be. It belongs to the dataset, and the caller reads it from
    the task catalogue. It defaults to ``None`` — meaning *not measured* — on
    purpose: a default number here would be a number nobody read, which is the
    shape of every understatement this module has had to be corrected for.
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

    instructions_path = resolve_standing_instructions_path(document, target)

    # What the settings say the task preview is cut to, and what the run really
    # cuts it to. They are read from different places on purpose: nothing
    # carries the setting to the judge, so only the second one is applied.
    named_width = grader_settings.get("task_prompt_truncate_chars")
    applied_width = int(_judge_default("task_prompt_truncate"))

    return GradingCaps(
        settings_path=str(target),
        judge_model=judge_model,
        judge_calls_per_rubric_item=max(max_iterations + finalisation_retries, 0),
        tool_calls_per_rubric_item=max(tool_call_cap, 0),
        characters_per_tool_result=MAX_CONTENT_CHARS,
        output_tokens_per_call=max(output_tokens, 0),
        standing_instructions_path=str(instructions_path),
        characters_of_standing_instructions=standing_instructions_characters(
            instructions_path, target
        ),
        characters_of_task_prompt_preview=max(applied_width, 0),
        task_prompt_preview_setting=(
            int(named_width) if named_width is not None else None
        ),
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
        characters_of_widest_scoring_line=(
            int(widest_scoring_line_characters)
            if widest_scoring_line_characters is not None
            else None
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

    carried = caps.input_tokens_carried_by_tool_results(
        assumptions.characters_per_token
    )
    if caps.characters_of_widest_scoring_line is None or (
        caps.characters_of_widest_scoring_line <= 0
    ):
        # Fail closed. The figure that can be worked out without this — tool
        # results plus instructions plus task preview — is the figure that used
        # to be printed under a heading calling it the largest possible bill
        # while the report said in its own words that this part of it was not
        # capped by anything. Reporting a smaller number with a caveat attached
        # is what that was. A number nobody measured is not a small number.
        how_it_failed = (
            "was never measured"
            if caps.characters_of_widest_scoring_line is None
            else "came out as nothing, which no scoring line in this "
            "benchmark is"
        )
        problems.append(
            f"how wide the scoring line being judged can be {how_it_failed}, "
            "so nothing checked whether the cost sum's "
            f"{assumptions.grading_input_tokens_per_call} tokens of input per "
            "marking call cover what one call really carries. Every marking "
            "call carries the scoring line, so leaving it out does not make it "
            "free — it makes the marking total smaller than the bill. The "
            "width is in the task catalogue, next to the count of scoring "
            "lines this same sum already uses"
        )
    else:
        opening = caps.input_tokens_the_conversation_opens_with(
            assumptions.characters_per_token
        )
        must_cover = caps.input_tokens_one_call_must_cover(
            assumptions.characters_per_token
        )
        if assumptions.grading_input_tokens_per_call < must_cover:
            problems.append(
                f"the cost sum allows "
                f"{assumptions.grading_input_tokens_per_call} tokens of input "
                f"per marking call, but {caps.settings_path} lets "
                f"{caps.tool_calls_per_rubric_item} tool results pile up in "
                "the conversation for one scoring line, each up to "
                f"{caps.characters_per_tool_result} characters, and every "
                f"later turn sends them all again — {carried} tokens — on top "
                f"of the {opening} tokens every call opens with, being the "
                f"{caps.characters_of_standing_instructions} characters of "
                f"{caps.standing_instructions_path}, the "
                f"{caps.characters_of_task_prompt_preview} characters of the "
                "task the judge is shown, and the "
                f"{caps.characters_of_widest_scoring_line} characters of the "
                "widest scoring line in the benchmark. So one call can carry "
                f"{must_cover} tokens"
            )

    if caps.task_prompt_preview_setting_is_ignored:
        problems.append(
            f"{caps.settings_path} says the judge is shown "
            f"{caps.task_prompt_preview_setting} characters of the task "
            "wording, but nothing carries that setting to the judge, which "
            f"applies its own {caps.characters_of_task_prompt_preview}. The "
            "figure above counts what is applied. Either wire the setting up "
            "or take it out, because a width that can be edited without "
            "effect will be read as describing this run"
        )

    for modality, label, model, calls in (
        (
            "vision",
            "reading pictures",
            caps.visual_model,
            caps.visual_calls_per_task,
        ),
        (
            "audio",
            "listening to sound",
            caps.audio_model,
            caps.audio_calls_per_task,
        ),
    ):
        if not model or calls <= 0:
            continue
        stated = assumptions.grading_perception.get(modality)
        if stated is None:
            problems.append(
                f"{caps.settings_path} lets marking call {model!r} for {label} "
                f"up to {calls} times per task, and the cost sum counts none "
                "of it"
            )
        else:
            if stated.model != model:
                problems.append(
                    f"the cost sum prices {label} against {stated.model!r}, "
                    f"but {caps.settings_path} uses {model!r}"
                )
            if stated.calls_per_task < calls:
                problems.append(
                    f"the cost sum allows {stated.calls_per_task} calls per "
                    f"task for {label}, but {caps.settings_path} lets it "
                    f"happen {calls} times"
                )
            if not stated.size_is_known:
                problems.append(
                    f"how much one {label} call sends and writes back has "
                    "never been measured, so its cost is unknown rather than "
                    "nothing"
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
        (
            "most characters one tool use hands back: "
            f"{caps.characters_per_tool_result}"
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
        "so one marking call can be carrying "
        f"{caps.tool_calls_per_rubric_item * caps.characters_per_tool_result} "
        "characters of the answer by the last turn, which is what the cost "
        "sum's input-per-call figure has to cover"
    )
    lines.append(
        "and every call opens with "
        f"{caps.characters_of_standing_instructions} characters of standing "
        f"instructions, read from {caps.standing_instructions_path}, plus the "
        f"{caps.characters_of_task_prompt_preview} characters of the task "
        "wording the judge is shown — both on the wire every single call"
    )
    if caps.task_prompt_preview_setting_is_ignored:
        lines.append(
            "note: the settings say that task wording is cut to "
            f"{caps.task_prompt_preview_setting} characters, and nothing "
            "carries that setting to the judge, so the applied width above is "
            "the one that counts"
        )
    if caps.characters_of_widest_scoring_line is None or (
        caps.characters_of_widest_scoring_line <= 0
    ):
        how_it_failed = (
            "was never measured"
            if caps.characters_of_widest_scoring_line is None
            else "came out as nothing, which no scoring line here is"
        )
        lines.append(
            f"WARNING: how wide the scoring line being judged can be "
            f"{how_it_failed}, so the opening above is missing a part that is "
            "on the wire for every single marking call. The figures here are "
            "below what one call carries, by an unknown amount"
        )
    else:
        lines.append(
            "and each call also carries the scoring line it is judging, at "
            f"most {caps.characters_of_widest_scoring_line} characters — the "
            "widest in the benchmark, read from the task catalogue. With that "
            "counted, every part of one marking call is accounted for, so the "
            "input-per-call figure above is a ceiling rather than a floor"
        )
    return lines
