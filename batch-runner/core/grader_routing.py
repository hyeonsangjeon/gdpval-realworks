"""Perception-modality routing for the v2 tool-calling grader.

Given a rubric criterion text, decide which **perception modality** the
judge should focus on. The routing decision is fed to the judge prompt
as `{{routing_modality}}` and `{{routing_preferred_op}}` hints so the
judge knows the cheapest read_deliverable op likely to ground a verdict.

Rationale (SPEC §4.3 + task 204): we do NOT run every criterion through
the full agentic loop with vision/audio sub-judges. We classify cheaply
first (keyword based) and only escalate the items whose criterion text
actually demands visual or audio judgment. Everything else stays on the
text+formatting cold path.

This module is **pure functional** — no I/O, no model calls, no state —
which is why it lives outside ``grader.py``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable

from core.media_types import (
    GRADER_AUDIO_EXTENSIONS,
    GRADER_VISUAL_RENDER_EXTENSIONS,
)


class Modality(str, Enum):
    """Coarse classification of what a rubric criterion is actually
    asking the judge to look at."""

    VISUAL = "visual"          # chart polish, layout, color, render
    AUDIO = "audio"            # mix, loudness, voice quality, silence
    FORMATTING = "formatting"  # docx/xlsx style/structure, no visual ask
    TEXT = "text"              # default — content/values/columns/text


@dataclass(frozen=True)
class RoutingDecision:
    modality: Modality
    preferred_op: str
    matched_keywords: tuple[str, ...]

    def to_prompt_hint(self) -> dict[str, str]:
        """Render into the placeholders consumed by ``grader_judge_v2.md``."""
        return {
            "routing_modality": self.modality.value,
            "routing_preferred_op": self.preferred_op,
        }


# Ordered: visual > audio > formatting > text. First hit wins.
#
# Keyword lists are intentionally short and high-precision. They are
# matched as whole-word patterns (case-insensitive) against the
# criterion text. Add new keywords only with evidence that the current
# set under-routes (see task 204 inventory in the PR2 report).
_VISUAL_KEYWORDS: tuple[str, ...] = (
    "chart", "charts", "graph", "graphs", "visual", "visualization",
    "visualisations", "appearance", "render", "rendered", "color", "colour",
    "font", "fonts", "layout", "image", "images", "diagram", "diagrams",
    "screenshot", "icon", "icons", "logo",
)
_AUDIO_KEYWORDS: tuple[str, ...] = (
    "audio", "sound", "music", "musical", "voice", "vocal", "mix", "mixing",
    "loudness", "loud", "silence", "silent", "clipping", "noise",
    "instrumentation",
    # Added on stage-1 evidence, not on taste. Task 38889c3b delivers a
    # 180 MB archive of music stems and is graded on tempo, key, vocals and
    # effects; it scored 41.8/62 with ``perception_call_count: 0``. Every
    # criterion below matched nothing above and was judged by reading a zip.
    #
    # The bar for adding one is that it names a property of sound and would
    # be odd in a rubric about a report. "instrumental", "stem" and "track"
    # were considered and rejected: "was instrumental in", "the delay stems
    # from" and "on track" are ordinary business English. "key" was rejected
    # outright. A word that slips through anyway is cheap -- a criterion that
    # routes AUDIO against files holding no audio is demoted back to TEXT by
    # ``resolve_runtime_routing`` before any model sees it.
    "vocals", "tempo", "bpm", "harmonic", "harmony", "harmonies",
    "melody", "melodic", "timbre", "audible", "audibly", "reverb",
    "synth", "synths", "synthesizer", "synthesizers",
    "waveform", "octave", "chord", "chords",
)
_FORMATTING_KEYWORDS: tuple[str, ...] = (
    "format", "formatted", "formatting", "style", "styles", "styling",
    "structure", "structured", "presentation", "polish", "polished",
    "template",
)


def _make_re(words: Iterable[str]) -> re.Pattern[str]:
    return re.compile(r"\b(" + "|".join(re.escape(w) for w in words) + r")\b",
                      flags=re.IGNORECASE)


_VIS_RE = _make_re(_VISUAL_KEYWORDS)
_AUD_RE = _make_re(_AUDIO_KEYWORDS)
_FMT_RE = _make_re(_FORMATTING_KEYWORDS)
_OVERALL_STYLE_RE = re.compile(
    r"\boverall\b(?:\W+\w+){0,4}\W+"
    r"(?:style|styling|format(?:ted|ting)?|presentation|polish)\b",
    flags=re.IGNORECASE,
)
_NONVISUAL_CHART_RE = re.compile(
    r"\bchart(?:\s*[-–—]\s*|\s+)of(?:\s*[-–—]\s*|\s+)accounts?\b",
    flags=re.IGNORECASE,
)


def _hits(rx: re.Pattern[str], text: str) -> tuple[str, ...]:
    return tuple(sorted({m.group(1).lower() for m in rx.finditer(text)}))


def is_overall_style_criterion(criterion_text: str) -> bool:
    """Return whether a criterion asks for deliverable-wide visual polish."""
    return bool(_OVERALL_STYLE_RE.search(criterion_text or ""))


def classify_criterion(criterion_text: str) -> RoutingDecision:
    """Decide a routing for one rubric criterion.

    The priority is: VISUAL > AUDIO > FORMATTING > TEXT. A criterion
    that mentions both visual and formatting words is routed VISUAL —
    visual judgment subsumes the formatting check.
    """
    text = criterion_text or ""

    if is_overall_style_criterion(text):
        return RoutingDecision(
            modality=Modality.VISUAL,
            preferred_op="render_to_image",
            matched_keywords=_hits(_FMT_RE, text),
        )

    visual_text = _NONVISUAL_CHART_RE.sub("", text)
    vis = _hits(_VIS_RE, visual_text)
    if vis:
        return RoutingDecision(
            modality=Modality.VISUAL,
            preferred_op="render_to_image",
            matched_keywords=vis,
        )
    aud = _hits(_AUD_RE, text)
    if aud:
        return RoutingDecision(
            modality=Modality.AUDIO,
            preferred_op="probe_audio",
            matched_keywords=aud,
        )
    fmt = _hits(_FMT_RE, text)
    if fmt:
        return RoutingDecision(
            modality=Modality.FORMATTING,
            preferred_op="inspect_formatting",
            matched_keywords=fmt,
        )
    return RoutingDecision(
        modality=Modality.TEXT,
        preferred_op="read_content",
        matched_keywords=(),
    )


def resolve_runtime_routing(
    criterion_text: str,
    selected_paths: Iterable[str],
    *,
    selected_paths_have_text: bool | None = None,
    selected_paths_have_audio: bool | None = None,
    some_selected_path_lacks_text: bool | None = None,
) -> RoutingDecision:
    """Apply target-aware policy without changing criterion classification.

    ``selected_paths_have_text`` is the caller's answer to "does any selected
    file yield a single character of text". The caller reads the files; this
    module stays pure. ``None`` means unknown and changes nothing -- only a
    measured ``False`` escalates.

    ``some_selected_path_lacks_text`` answers the narrower question "is any one
    of these files unreadable", which the first signal cannot express: it
    collapses a bundle to a single yes the moment one file yields a character,
    so a picture delivered alongside a readable sibling reports as readable.
    Same rules -- only a measured ``True`` escalates, ``None`` changes nothing.

    ``selected_paths_have_audio`` is the same shape of answer to "is there
    anything here to listen to", and is used only defensively: a measured
    ``True`` stops the demotion below from stripping the listening model off a
    criterion about sound. It can never promote a criterion on its own.
    """
    decision = classify_criterion(criterion_text)
    suffixes = {
        suffix
        for path in selected_paths
        if isinstance(path, str) and path
        if (suffix := Path(path).suffix.lower())
    }
    if (
        is_overall_style_criterion(criterion_text)
        and suffixes
        and suffixes.issubset({".doc", ".docx"})
    ):
        decision = RoutingDecision(
            modality=Modality.FORMATTING,
            preferred_op="inspect_formatting",
            matched_keywords=decision.matched_keywords,
        )
    # A criterion about a mix has no meaning against a spreadsheet, so an
    # AUDIO classification whose files carry no audio is demoted to the path
    # that can actually answer it.
    #
    # Until now that test was the file extension alone, which reads a
    # container as if it were a medium. A folder of stems delivered as one
    # ``.zip`` is audio; ``.zip`` is disjoint from the audio extensions; and
    # so every listening criterion on stage-1 task 38889c3b was demoted to
    # TEXT and answered by reading an archive. The measured probe is what the
    # extension was standing in for, so where it speaks it wins, and where it
    # says nothing the extension test is unchanged.
    elif (
        decision.modality is Modality.AUDIO
        and selected_paths_have_audio is not True
        and suffixes
        and suffixes.isdisjoint(GRADER_AUDIO_EXTENSIONS)
    ):
        decision = RoutingDecision(
            modality=Modality.TEXT,
            preferred_op="read_content",
            matched_keywords=decision.matched_keywords,
        )
    # A narrower cousin of the audio rule above. Audio can demote wholesale
    # because a criterion about a mix has no meaning at all against a
    # spreadsheet. Visual cannot: the two kinds of visual criterion differ in
    # whether text is an acceptable substitute.
    #
    # "Overall formatting and style of the deliverable" against a lone ``.txt``
    # is answerable from the text -- headings, spacing, structure and line
    # breaks *are* the formatting of a plain-text file. Today it routes VISUAL,
    # finds no render target, and returns
    # ``required_visual_render_target_unavailable``: a guaranteed
    # ``judge_error`` on work the judge could have read. Three of the eight
    # remaining harness errors on the sol-220 rerun are this, and under
    # ``split_children`` one such child collapses every sibling with it
    # (``grader.py`` fails the whole item on the first child error).
    #
    # An explicitly visual criterion must NOT demote. "Document color and page
    # layout are visually polished" against a ``.csv`` is unanswerable from the
    # characters in the file, and a text verdict there would be invented rather
    # than merely absent. Failing closed is the correct outcome and
    # ``test_explicit_visual_item_fails_closed_without_render_target`` pins it.
    # ``is_overall_style_criterion`` is the same predicate the ``.docx`` rule
    # above already uses to draw this line.
    #
    # This cannot change an item that renders today: it fires only when *no*
    # selected file is renderable, which is exactly the set that currently
    # errors out. Nor can it answer from a partial view the way raising the
    # file cap would -- the text is handed over whole.
    elif (
        decision.modality is Modality.VISUAL
        and is_overall_style_criterion(criterion_text)
        and suffixes
        and suffixes.isdisjoint(GRADER_VISUAL_RENDER_EXTENSIONS)
    ):
        decision = RoutingDecision(
            modality=Modality.TEXT,
            preferred_op="read_content",
            matched_keywords=decision.matched_keywords,
        )

    # The mirror image of the demotions above, and the last rule because it
    # judges the outcome of all of them: a file with no text in it answers
    # nothing from its text.
    #
    # One stage-1 gold answer is a two-page scan. Ten rubric items about its
    # contents routed TEXT, read zero characters, and were failed as "that
    # content is absent" -- from a document that says all ten things, on pages
    # the harness had already rendered for the task's other items. Reading is
    # not the only way to see a page, so an item whose only files cannot be
    # read goes to the path that looks at them.
    #
    # Three conditions keep this narrow. Only a measured ``False`` counts, so
    # an unreadable or unsupported file cannot escalate on a guess. Only TEXT
    # and FORMATTING escalate, because AUDIO and VISUAL already name what they
    # need. And every selected file must be renderable, so escalating never
    # trades a readable file for one nothing can look at.
    #
    # The bundle question and the file question are both asked, because one
    # readable file used to answer for all of them. A stage-3 task selected a
    # two-page flowchart holding zero characters -- one full-page image -- next
    # to a readable memo; the bundle reported "yes, there is text here", the
    # item stayed TEXT, and the flowchart was never rendered or looked at. A
    # sibling that can be read is not evidence about the file that cannot.
    if (
        (selected_paths_have_text is False or some_selected_path_lacks_text is True)
        and decision.modality in (Modality.TEXT, Modality.FORMATTING)
        and suffixes
        and suffixes.issubset(GRADER_VISUAL_RENDER_EXTENSIONS)
    ):
        return RoutingDecision(
            modality=Modality.VISUAL,
            preferred_op="render_to_image",
            matched_keywords=decision.matched_keywords,
        )
    return decision


def inventory(criteria: Iterable[str]) -> dict[str, int]:
    """Aggregate modality counts across a collection of criteria.

    Useful for the PR2 report ("how many of exp003's critical items are
    visual vs formatting vs text?") without instantiating a full grader.
    """
    out = {m.value: 0 for m in Modality}
    for c in criteria:
        out[classify_criterion(c).modality.value] += 1
    return out
