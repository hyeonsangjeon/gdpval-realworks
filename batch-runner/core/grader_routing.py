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
    #: Which of the selected files this decision wants looked at, when that
    #: is narrower than all of them. ``None`` -- the ordinary case -- means
    #: all of them, and is what every criterion that names something visual
    #: gets: a question about a chart's colours is a question about the
    #: whole deliverable. Only the unreadable-file escalation below sets
    #: this, because only it is grounded in a property of particular files.
    render_paths: tuple[str, ...] | None = None

    def to_prompt_hint(self) -> dict[str, str]:
        """Render into the placeholders consumed by ``grader_judge_v2.md``."""
        return {
            "routing_modality": self.modality.value,
            "routing_preferred_op": self.preferred_op,
        }

    def render_targets(self, selected_paths: Iterable[str]) -> list[str]:
        """The files to render for this decision, in selection order.

        Every caller that turns a VISUAL decision into pictures goes through
        here -- the task budget, the per-item cap check, the free preflight
        and the prepass the judge actually runs. They have to agree: the
        judge cross-checks what it rendered against what was planned, and a
        budget that counts a file nobody renders is not a budget.
        """
        return list(self.render_paths) if self.render_paths else list(selected_paths)


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
    selected_paths_are_source_code: bool | None = None,
    some_selected_path_lacks_text: bool | None = None,
    paths_without_text: Iterable[str] | None = None,
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

    ``paths_without_text`` names *which* files those are. It decides nothing on
    its own; it is what the escalation below hands back as ``render_paths`` so
    that only the unreadable files are looked at.

    ``selected_paths_have_audio`` is the same shape of answer to "is there
    anything here to listen to", and is used only defensively: a measured
    ``True`` stops the demotion below from stripping the listening model off a
    criterion about sound. It can never promote a criterion on its own.

    ``selected_paths_are_source_code`` answers "is every selected file program
    text, with nothing anywhere in it that could be turned into a picture".
    Only a measured ``True`` acts, and what it does is demote -- so an
    unreadable archive or a probe that cannot speak leaves the item exactly
    where it is, which is failing closed.
    """
    decision = classify_criterion(criterion_text)
    paths = [path for path in selected_paths if isinstance(path, str) and path]
    suffixes = {
        suffix
        for path in paths
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
    # The one place an *explicitly* visual criterion may demote, and it does
    # not weaken the rule above so much as name the case that rule was never
    # arguing about.
    #
    # The objection to demoting "document color and page layout are visually
    # polished" is that the ``.csv`` has an appearance and the characters do
    # not carry it, so a text verdict would be invented. Source code inverts
    # that. "The rendered DOM includes an element with role=status" is a
    # question about a page that does not exist yet and is not in the
    # submission at all -- it exists only once something builds and runs the
    # code. The JSX is not a substitute for looking at that page. It is the
    # only place the answer is written down, and rendering is not an option
    # that was passed over, it is not an option.
    #
    # Task 7de33b48 is five items and eight points on one ``.zip`` of two
    # ``.tsx`` files, a ``.css``, a ``README.md`` and a ``package.json``: no
    # picture in it anywhere, every criterion naming a source file or a code
    # construct, and all five excluded as
    # ``required_visual_render_target_unavailable``. They were sorted by the
    # words ``render``, ``layout`` and ``visual`` in their text, which is the
    # right default and the wrong answer here.
    #
    # Two locks, either of which alone would do. The measured probe is the
    # real one: it is ``True`` only when every selected file was examined and
    # none of it -- nor any member of any archive in it -- can be turned into
    # an image, and it withholds ``True`` rather than guess. The suffix test
    # is the second, so that a suffix added to the render set tomorrow cannot
    # be demoted here by a probe that had not heard about it.
    elif (
        decision.modality is Modality.VISUAL
        and selected_paths_are_source_code is True
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
    #
    # What escalates and what gets looked at are two different sets, and
    # conflating them cost a whole task its score. Stage 3's task 43dc9778
    # delivers a two-page scan next to a 17-page readable return, and all 67 of
    # its rubric items select both. Escalating on the scan and then rendering
    # the bundle asks for 67x2 = 134 pictures against a task budget of 72: over
    # budget, every item excluded, 87.36% to 0.00%. The escalation was right and
    # the render scope was wrong. The reason a file escalates is a fact about
    # that file, so that file is what gets rendered -- 67 calls, inside the
    # budget, and the readable sibling is still handed to the judge to read.
    if (
        (selected_paths_have_text is False or some_selected_path_lacks_text is True)
        and decision.modality in (Modality.TEXT, Modality.FORMATTING)
        and suffixes
        and suffixes.issubset(GRADER_VISUAL_RENDER_EXTENSIONS)
    ):
        unreadable = set(paths_without_text or ())
        narrowed = tuple(path for path in paths if path in unreadable)
        return RoutingDecision(
            modality=Modality.VISUAL,
            preferred_op="render_to_image",
            matched_keywords=decision.matched_keywords,
            # Narrower or nothing. An unnamed set, or one covering every
            # selected file, is the default the field already means, and
            # saying it twice is a second thing to keep in step.
            render_paths=(
                narrowed if 0 < len(narrowed) < len(paths) else None
            ),
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
