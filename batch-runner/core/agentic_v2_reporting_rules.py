"""How this run gets written up, and the one rule that can be enforced.

Two short reports, Korean and English, on the same six headings. Short is the
rule and not a preference: a long report about 30 tasks fills the space between
the numbers with sentences nobody measured, and those sentences are what gets
quoted later.

**The skill chains are fixed**, because the order changes the result. Korean:
``experiment-report-ko`` for the structure, then ``humanize-korean`` in strict
mode over bounded passages. English: ``experiment-report-en``, then
``humanize-english`` for conservative de-mechanisation, then ``im-not-ai-en``
as a last copy-edit. Each stage keeps the one before it; the editors are not
allowed to rewrite a claim, only the sentence carrying it.

**Nothing is filled in with a predicted result.** That is the rule this module
exists to enforce rather than state. Before the run there is no draft: an
outline with blanks is what a pre-registered report looks like, and a blank is
not a finding. After the run, every figure in the draft has to be a figure that
is in the run record.

:func:`check_every_figure` is what checks it. It pulls the numbers out of the
prose and looks for each one in the record, and it is honest about its own
reach:

* ``found`` -- the number is literally in the record.
* ``derived`` -- it is ``a/b`` of two numbers that are, as a percentage. The
  pair is named so a person can see whether it is the *right* pair.
* ``unsourced`` -- it is in neither. The draft is not ready while any figure is
  unsourced.

What it cannot catch is a true number in a false sentence. "11 of 30 finished"
and "only 11 of 30 finished, because the replay format confused the model" use
the same figures and make different claims, and no counter can tell them apart.
This check removes one failure -- a number with nothing behind it -- and leaves
the rest to reading.

Offline. Prose in, a run record in, a verdict out. No model, no cost.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Optional, Sequence

#: The headings, in order, in both languages. Six, and the same six, so a
#: reader of one can find the paragraph in the other. Longer than this and the
#: report starts explaining itself.
THE_OUTLINE_EN = (
    "What was run",
    "What changed and what did not",
    "What happened",
    "What it does not say",
    "What was spent",
    "What is next",
)

THE_OUTLINE_KO = (
    "무엇을 돌렸는가",
    "무엇이 바뀌고 무엇이 그대로인가",
    "무엇이 나왔는가",
    "이 결과가 말하지 않는 것",
    "비용",
    "다음",
)

#: In order. The structure skill first, the editors after, and the editors do
#: not re-open a claim the structure skill placed.
THE_KO_CHAIN = ("experiment-report-ko", "humanize-korean:strict")
THE_EN_CHAIN = ("experiment-report-en", "humanize-english", "im-not-ai-en")

#: Roughly a page each. A count rather than a feeling, so that "short" is
#: something a check can fail on.
THE_LENGTH_CEILING_KO_CHARACTERS = 4000
THE_LENGTH_CEILING_EN_WORDS = 900

#: Digits, with thousands separators and decimals, and with a currency sign or
#: a percent sign kept out of the captured value.
_A_NUMBER = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(?![\w])")

#: Figures that are never a finding: a year inside a date. Small integers get
#: no such allowance. "2 tasks hit the wall clock" is a measurement and needs a
#: source like any other; a count that is genuinely just prose gets spelled as
#: a word, and a word is not scanned at all.
_AN_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


@dataclass(frozen=True)
class Figure:
    """One number as it appears in a draft, with where it came from."""

    value: float
    text: str
    context: str
    status: str
    because: str = ""

    @property
    def is_accounted_for(self) -> bool:
        return self.status in ("found", "derived")

    def as_row(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "text": self.text,
            "context": self.context,
            "status": self.status,
            "because": self.because,
        }


def _numbers_in_record(record: Any, seen: Optional[set[float]] = None) -> set[float]:
    """Every numeric leaf, however deep, including ones inside strings.

    Strings are read too because a receipt's status line and a run id carry
    figures a report legitimately quotes.
    """
    found: set[float] = set() if seen is None else seen
    if isinstance(record, bool):
        return found
    if isinstance(record, (int, float)):
        found.add(float(record))
        return found
    if isinstance(record, str):
        for match in _A_NUMBER.finditer(record):
            found.add(float(match.group(1).replace(",", "")))
        return found
    if isinstance(record, Mapping):
        for key, value in record.items():
            _numbers_in_record(key, found)
            _numbers_in_record(value, found)
        return found
    if isinstance(record, (list, tuple)):
        for value in record:
            _numbers_in_record(value, found)
    return found


def _as_a_percentage_of_two(value: float, pool: Iterable[float]) -> Optional[str]:
    """``value`` as ``100 * a / b`` for some pair in `pool`, or ``None``.

    Named rather than just allowed: a percentage that is right to one decimal
    place and computed from the wrong pair is still wrong, and the only way to
    see that is to be told which pair it was.
    """
    numbers = sorted({one for one in pool if one > 0})
    for below in numbers:
        for above in numbers:
            if above <= 0 or below > above:
                continue
            if abs(round(100.0 * below / above, 1) - round(value, 1)) < 0.05:
                return f"{below:g}/{above:g}"
    return None


def _context_of(text: str, start: int, end: int, width: int = 40) -> str:
    opening = max(0, start - width)
    closing = min(len(text), end + width)
    return " ".join(text[opening:closing].split())


def _claims_a_percentage(draft: str, end: int) -> bool:
    """Whether the figure is written as a percentage in the draft itself.

    The derivation allowance is only offered to figures that ask for it. A
    record with a dozen numbers in it has a hundred-odd pairs, and some pair is
    almost always within a tenth of any small integer -- ``2`` is 6.131815/305
    to one decimal place. Without this, "2 tasks hit the wall clock" would be
    waved through as a percentage of two figures nobody was talking about.
    """
    tail = draft[end : end + 10].lstrip()
    return tail.startswith("%") or tail.lower().startswith(("percent", "퍼센트"))


def check_every_figure(draft: str, record: Mapping[str, Any]) -> dict[str, Any]:
    """Each number in `draft`, against the numbers in `record`.

    A draft with no figures at all is not ready either -- a report about a run
    that quotes nothing from it has not been written yet.
    """
    pool = _numbers_in_record(record)
    dates = [(match.start(), match.end()) for match in _AN_ISO_DATE.finditer(draft)]

    figures: list[Figure] = []
    for match in _A_NUMBER.finditer(draft):
        start, end = match.span(1)
        if any(opening <= start < closing for opening, closing in dates):
            continue

        text = match.group(1)
        value = float(text.replace(",", ""))
        context = _context_of(draft, start, end)

        if value in pool:
            figures.append(Figure(value, text, context, "found"))
            continue
        derivation = (
            _as_a_percentage_of_two(value, pool)
            if _claims_a_percentage(draft, end)
            else None
        )
        if derivation is not None:
            figures.append(
                Figure(value, text, context, "derived", f"{derivation} as a percentage")
            )
            continue
        figures.append(
            Figure(value, text, context, "unsourced", "not in the run record")
        )

    unsourced = [one for one in figures if one.status == "unsourced"]
    return {
        "figures": len(figures),
        "found": sum(1 for one in figures if one.status == "found"),
        "derived": sum(1 for one in figures if one.status == "derived"),
        "unsourced": len(unsourced),
        "ready": bool(figures) and not unsourced,
        "not_ready_because": (
            ""
            if figures
            else "the draft quotes no figure from the run, so it is not a report of it"
        ),
        "rows": [one.as_row() for one in figures],
        "what_this_cannot_catch": (
            "a true figure in a false sentence. Every number here can be in "
            "the record and the claim built on them still be wrong"
        ),
    }


def the_outline(language: str) -> tuple[str, ...]:
    if language == "ko":
        return THE_OUTLINE_KO
    if language == "en":
        return THE_OUTLINE_EN
    raise ValueError(f"the report is written in ko and en, not {language!r}")


def blank_outline(language: str) -> str:
    """What exists before the run: headings, and under each one, nothing.

    Deliberately not a template with example numbers in it. A placeholder
    figure is the thing this module is against, and one left in by accident
    reads exactly like a result.
    """
    marker = "(비어 있음 — 실행 전)" if language == "ko" else "(empty — before the run)"
    return "\n\n".join(f"## {heading}\n\n{marker}" for heading in the_outline(language))


def is_short_enough(draft: str, language: str) -> dict[str, Any]:
    if language == "ko":
        size, ceiling, unit = len(draft), THE_LENGTH_CEILING_KO_CHARACTERS, "characters"
    else:
        size, ceiling, unit = len(draft.split()), THE_LENGTH_CEILING_EN_WORDS, "words"
    return {
        "size": size,
        "ceiling": ceiling,
        "unit": unit,
        "within": size <= ceiling,
    }


def the_rules() -> dict[str, Any]:
    """The whole of it, for a plan file or a job log to quote."""
    return {
        "outline_en": list(THE_OUTLINE_EN),
        "outline_ko": list(THE_OUTLINE_KO),
        "chain_ko": list(THE_KO_CHAIN),
        "chain_en": list(THE_EN_CHAIN),
        "ceiling_ko_characters": THE_LENGTH_CEILING_KO_CHARACTERS,
        "ceiling_en_words": THE_LENGTH_CEILING_EN_WORDS,
        "before_the_run": (
            "an outline with empty sections. No figure is written down before "
            "it has been measured, including as an example"
        ),
        "after_the_run": (
            "every figure in the draft is in the run record, or is a named "
            "derivation of two figures that are. check_every_figure decides it"
        ),
        "the_two_reports_say_the_same_thing": (
            "the same six headings in both languages, and the editors may "
            "change a sentence but not a claim"
        ),
    }


def describe(verdict: Mapping[str, Any]) -> str:
    lines = [
        f"figures: {verdict['figures']} "
        f"({verdict['found']} in the record, {verdict['derived']} derived, "
        f"{verdict['unsourced']} unsourced)"
    ]
    for row in verdict["rows"]:
        if row["status"] == "unsourced":
            lines.append(f"  {row['text']} — {row['context']}")
    if verdict["not_ready_because"]:
        lines.append(f"  {verdict['not_ready_because']}")
    return "\n".join(lines)


def figures_in(draft: str) -> Sequence[str]:
    """Just the numbers, for a caller that wants to look itself."""
    dates = [(match.start(), match.end()) for match in _AN_ISO_DATE.finditer(draft)]
    return tuple(
        match.group(1)
        for match in _A_NUMBER.finditer(draft)
        if not any(opening <= match.start(1) < closing for opening, closing in dates)
    )
