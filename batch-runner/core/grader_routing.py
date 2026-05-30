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
from typing import Iterable


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


def _hits(rx: re.Pattern[str], text: str) -> tuple[str, ...]:
    return tuple(sorted({m.group(1).lower() for m in rx.finditer(text)}))


def classify_criterion(criterion_text: str) -> RoutingDecision:
    """Decide a routing for one rubric criterion.

    The priority is: VISUAL > AUDIO > FORMATTING > TEXT. A criterion
    that mentions both visual and formatting words is routed VISUAL —
    visual judgment subsumes the formatting check.
    """
    text = criterion_text or ""

    vis = _hits(_VIS_RE, text)
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


def inventory(criteria: Iterable[str]) -> dict[str, int]:
    """Aggregate modality counts across a collection of criteria.

    Useful for the PR2 report ("how many of exp003's critical items are
    visual vs formatting vs text?") without instantiating a full grader.
    """
    out = {m.value: 0 for m in Modality}
    for c in criteria:
        out[classify_criterion(c).modality.value] += 1
    return out
