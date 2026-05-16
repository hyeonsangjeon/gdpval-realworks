"""Prompt-based file-requirement classifier.

Heuristic translation of Appendix A of
``tasks/HF_PROMPT_ANALYSIS_REPORT.md`` into Python.  Step 0 manifest generation
combines this *prompt signal* with the *deliverable signal* (presence of
``deliverable_files`` rows in the source HF dataset) to drive the V2 manifest.

Calibration target (HF Gold Subset, 220 prompts):
    explicit + inferred  ≈ 207   (file_required)
    ambiguous            ≈  10
    text_only            ≈   3

Key heuristic refinements vs. a naive regex match (see HF report sec. 2):
* **Explicit** extensions are only counted when they appear in a *deliverable*
  context — preceded by an output verb (``save/export/submit/output/deliver``
  / ``format`` / ``named``) within the same sentence, wrapped in parentheses
  like ``(.docx)``, or immediately followed by a deliverable noun
  (``format`` / ``file`` / ``document`` / ``deliverable`` / ``output``).
  Bare filename mentions of *input* files (e.g. ``Aurisic_Q3.xlsx`` inside a
  list of attached reference files) are *not* explicit deliverables.  URLs are
  masked before scanning so that ``foo.pdf`` inside ``https://…/foo.pdf`` is
  ignored.
* **Producer verbs** include the Appendix-A list plus a few common synonyms
  observed in HF prompts (``write/develop/provide/compose/compile/design``).
* **Specific deliverable nouns** include common HF phrasings such as
  ``Word document`` / ``Excel spreadsheet`` / ``PowerPoint deck`` /
  ``guide`` / ``plan`` / ``article`` / ``agreement``, in addition to the
  Appendix-A list.

Usage:
    from core.prompt_classifier import classify_prompt

    result = classify_prompt(prompt_text)
    if result.requires_file:
        ...

Public API:
    PromptClassification — dataclass with classification details.
    classify_prompt(prompt: str) -> PromptClassification
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, List, Sequence


# ── Recognized extensions ─────────────────────────────────────────────────
_EXPLICIT_EXTENSIONS: Sequence[str] = (
    ".docx", ".xlsx", ".pptx", ".pdf", ".csv",
    ".png", ".jpg", ".jpeg", ".wav", ".mp3", ".mp4",
    ".zip", ".html", ".md", ".txt", ".json", ".ipynb", ".dwg",
)

# Raw extension token scanner.  Word-boundary on the trailing side ensures
# that e.g. ``.pdfs`` does NOT match ``.pdf``.  The leading side is *not*
# anchored — we want to find every ``.ext`` occurrence (filename or otherwise)
# and then apply context filtering in :func:`_find_explicit_exts`.
_RAW_EXT_RE = re.compile(
    r"\.(?:" + "|".join(ext.lstrip(".") for ext in _EXPLICIT_EXTENSIONS)
    + r")(?![A-Za-z0-9_])",
    flags=re.IGNORECASE,
)

_URL_RE = re.compile(r"https?://\S+", flags=re.IGNORECASE)

# Deliverable verbs/keywords searched *inside the current sentence* preceding
# the extension.  Narrower than the producer-verb list — limited to words that
# strongly indicate a delivery destination/format.  Restricting to these
# avoids treating filenames in INPUT-file lists as explicit deliverables.
_DELIVERABLE_VERB_RE = re.compile(
    r"\b(?:"
    r"sav(?:e|es|ed|ing)"
    r"|export(?:|s|ed|ing)"
    r"|submit(?:|s|ted|ting)"
    r"|submission(?:|s)"
    r"|output(?:|s|ted|ting)"
    r"|deliver(?:|s|ed|ing|able|ables|y|ies)"
    r"|format(?:|s|ted|ting)"
    r"|named?|titled?"
    r")\b",
    flags=re.IGNORECASE,
)

# Preposition immediately before an extension (with optional article), e.g.
# ``in .pdf``, ``as a .docx``, ``in an .mp4``.  Must end right at the dot.
_DELIVERABLE_PREP_BEFORE_RE = re.compile(
    r"\b(?:as|in|into|to)(?:\s+(?:a|an|the))?\s*$",
    flags=re.IGNORECASE,
)

# Deliverable noun immediately after an extension, e.g. ``.pdf format``,
# ``.docx file``, ``.mp4 movie``.
_DELIVERABLE_AFTER_RE = re.compile(
    r"^\s*(?:format|file|document|deliverable|deliverables|deliver(?:y|ables?)"
    r"|output|version|movie|image)\b",
    flags=re.IGNORECASE,
)

# Sentence break inside the cleaned before-window.  Matches ``.``, ``!``, ``?``
# followed by whitespace, or a newline.  Used to constrain the verb search to
# the *current* sentence.
_SENTENCE_BREAK_RE = re.compile(r"[.!?]\s|\n")


# ── Producer verbs ─────────────────────────────────────────────────────────
# Per Appendix A: create/produce/generate/deliver/prepare/build/draft/output/
# submit/save as/export to.  Plus high-frequency synonyms observed in HF
# prompts: write, develop, provide, compose, compile, design.
_PRODUCER_VERB_RE = re.compile(
    r"\b(?:"
    r"creat(?:e|es|ed|ing)"
    r"|produc(?:e|es|ed|ing)"
    r"|generat(?:e|es|ed|ing)"
    r"|deliver(?:|s|ed|ing)"
    r"|prepar(?:e|es|ed|ing)"
    r"|build(?:|s|ing)"
    r"|built"
    r"|draft(?:|s|ed|ing)"
    r"|output(?:|s|ted|ting)"
    r"|submit(?:|s|ted|ting)"
    r"|writ(?:e|es|ing|ten)|wrote"
    r"|develop(?:|s|ed|ing)"
    r"|provid(?:e|es|ed|ing)"
    r"|compos(?:e|es|ed|ing)"
    r"|compil(?:e|es|ed|ing)"
    r"|design(?:|s|ed|ing)"
    r"|fill(?:|s|ed|ing)\s+(?:in|out)"
    r")\b",
    flags=re.IGNORECASE,
)

_PRODUCER_PHRASE_RE = re.compile(
    r"\b(?:"
    r"sav(?:e|es|ed|ing)\s+(?:it\s+|this\s+|them\s+|the\s+\w+\s+)?as"
    r"|export(?:|s|ed|ing)\s+(?:it\s+|this\s+|them\s+|the\s+\w+\s+)?(?:to|as)"
    r")\b",
    flags=re.IGNORECASE,
)


# ── Deliverable nouns ──────────────────────────────────────────────────────
# Format-specific nouns map to an inferred extension.
#
# Multi-word phrases (e.g. "word document", "excel spreadsheet") are matched
# first via _SPECIFIC_NOUNS_SORTED so they beat their single-word components.
_SPECIFIC_NOUN_TO_EXT: dict[str, str] = {
    # .docx family
    "report": ".docx",
    "reports": ".docx",
    "memo": ".docx",
    "memos": ".docx",
    "letter": ".docx",
    "letters": ".docx",
    "word document": ".docx",
    "microsoft word document": ".docx",
    "word doc": ".docx",
    "word docs": ".docx",
    "word file": ".docx",
    "guide": ".docx",
    "guides": ".docx",
    "plan": ".docx",
    "plans": ".docx",
    "article": ".docx",
    "articles": ".docx",
    "agreement": ".docx",
    "agreements": ".docx",
    # .xlsx family
    "spreadsheet": ".xlsx",
    "spreadsheets": ".xlsx",
    "workbook": ".xlsx",
    "workbooks": ".xlsx",
    "excel spreadsheet": ".xlsx",
    "excel sheet": ".xlsx",
    "excel sheets": ".xlsx",
    "excel workbook": ".xlsx",
    "excel worksheet": ".xlsx",
    "excel worksheets": ".xlsx",
    "excel file": ".xlsx",
    "excel files": ".xlsx",
    "excel output": ".xlsx",
    "excel table": ".xlsx",
    "excel-based": ".xlsx",
    # .pptx family
    "slide deck": ".pptx",
    "slide decks": ".pptx",
    "slidedeck": ".pptx",
    "presentation": ".pptx",
    "presentations": ".pptx",
    "slides": ".pptx",
    "slide": ".pptx",
    "powerpoint": ".pptx",
    "powerpoint deck": ".pptx",
    "powerpoint presentation": ".pptx",
    "powerpoint format": ".pptx",
    # .png family
    "chart": ".png",
    "charts": ".png",
    "image": ".png",
    "images": ".png",
    "diagram": ".png",
    "diagrams": ".png",
    # .wav / .mp4
    "audio": ".wav",
    "video": ".mp4",
    "videos": ".mp4",
    # other
    "csv": ".csv",
    "csv file": ".csv",
    "pdf": ".pdf",
    "pdfs": ".pdf",
    "notebook": ".ipynb",
    "notebooks": ".ipynb",
    "archive": ".zip",
    "archives": ".zip",
    "cad drawing": ".dwg",
    "cad drawings": ".dwg",
}

# Longest noun phrases first so multi-word terms win over single-word matches.
_SPECIFIC_NOUNS_SORTED: List[str] = sorted(
    _SPECIFIC_NOUN_TO_EXT.keys(), key=lambda n: -len(n)
)
_SPECIFIC_NOUN_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?:"
    + "|".join(re.escape(n) for n in _SPECIFIC_NOUNS_SORTED)
    + r")(?![A-Za-z0-9_])",
    flags=re.IGNORECASE,
)

# Generic nouns indicate "a deliverable is expected" without fixing a format.
_GENERIC_NOUNS: Sequence[str] = (
    "file", "files",
    "document", "documents",
    "dataset", "datasets",
    "deliverable", "deliverables",
)
_GENERIC_NOUN_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(n) for n in _GENERIC_NOUNS) + r")\b",
    flags=re.IGNORECASE,
)


# ── Public API ─────────────────────────────────────────────────────────────


@dataclass
class PromptClassification:
    """Result of classifying a single prompt.

    Attributes:
        requires_file: True if classification is anything but ``"text_only"``.
        explicit_exts: Extensions directly written in the prompt (e.g. ``.docx``).
        inferred_exts: Extensions inferred from deliverable nouns; non-empty
            only when a producer verb and a format-specific noun co-occur.
        confidence: One of ``"explicit"``, ``"inferred"``, ``"ambiguous"``,
            ``"text_only"``.
    """

    requires_file: bool
    explicit_exts: List[str] = field(default_factory=list)
    inferred_exts: List[str] = field(default_factory=list)
    confidence: str = "text_only"


def _dedupe_preserve_order(items: Iterable[str]) -> List[str]:
    return list(dict.fromkeys(items))


def _last_sentence_window(cleaned_before: str) -> str:
    """Return the tail of ``cleaned_before`` after the last sentence break.

    Uses :data:`_SENTENCE_BREAK_RE`.  The caller is expected to have stripped
    other ``.ext`` tokens so they don't masquerade as sentence terminators.
    """
    last_idx = 0
    for sm in _SENTENCE_BREAK_RE.finditer(cleaned_before):
        last_idx = sm.end()
    return cleaned_before[last_idx:] if last_idx else cleaned_before


def _find_explicit_exts(text: str) -> List[str]:
    """Extract extensions that appear in a *deliverable* context.

    An extension occurrence is considered explicit if any of:
      A. wrapped in parentheses like ``(.docx)``;
      B. immediately followed by a deliverable noun (``format``, ``file``,
         ``document``, ``deliverable``, ``output``, ``version``, ``movie``,
         ``image``);
      C. preceded — within the current sentence — by a deliverable verb
         (``save``, ``export``, ``submit``, ``output``, ``deliver``,
         ``format``, ``named``, ``titled``);
      D. preceded immediately by ``in``/``as``/``into``/``to`` (with optional
         article) right before the dot.

    Filename mentions inside URLs are ignored via :data:`_URL_RE` masking.
    """
    if not text:
        return []

    # Mask URLs so that http URLs ending in `.pdf` etc. don't register.
    masked = _URL_RE.sub(lambda m: " " * len(m.group()), text)

    found: List[str] = []
    for m in _RAW_EXT_RE.finditer(masked):
        ext = m.group(0).lower()
        start, end = m.start(), m.end()

        # (A) paren-wrapped, e.g. "(.docx)"
        if start >= 1 and masked[start - 1] == "(" and end < len(masked) \
                and masked[end] == ")":
            found.append(ext)
            continue

        # (B) followed by deliverable noun like " format" / " file"
        after = masked[end:end + 30]
        if _DELIVERABLE_AFTER_RE.match(after):
            found.append(ext)
            continue

        # Build a cleaned before-window: strip other ``.ext`` tokens to keep
        # sentence boundaries honest (so e.g. ``REPORT.DOCX and FIGURE.PNG``
        # is treated as one sentence, not two).
        raw_before = masked[max(0, start - 80):start]
        cleaned_before = _RAW_EXT_RE.sub(
            lambda mm: " " * len(mm.group()), raw_before
        )
        window = _last_sentence_window(cleaned_before)

        # (C) deliverable verb anywhere in the current sentence preceding ext
        if _DELIVERABLE_VERB_RE.search(window):
            found.append(ext)
            continue

        # (D) preposition (with optional article) right before the dot
        if _DELIVERABLE_PREP_BEFORE_RE.search(window):
            found.append(ext)
            continue

    return _dedupe_preserve_order(found)


def _find_specific_nouns(text: str) -> List[str]:
    """Return list of inferred extensions from specific deliverable nouns."""
    found = [
        _SPECIFIC_NOUN_TO_EXT[m.group(0).lower()]
        for m in _SPECIFIC_NOUN_RE.finditer(text)
    ]
    return _dedupe_preserve_order(found)


def _has_producer_verb(text: str) -> bool:
    return bool(_PRODUCER_VERB_RE.search(text)) or bool(_PRODUCER_PHRASE_RE.search(text))


def _has_generic_noun(text: str) -> bool:
    return bool(_GENERIC_NOUN_RE.search(text))


def classify_prompt(prompt: str) -> PromptClassification:
    """Classify a single prompt's file-output requirement.

    Returns a :class:`PromptClassification` capturing explicit/inferred
    extensions and a confidence label.  Always non-throwing — invalid input
    (``None``, ``""``) yields a ``"text_only"`` result.
    """
    text = prompt or ""

    explicit_exts = _find_explicit_exts(text)
    specific_inferred = _find_specific_nouns(text)
    has_verb = _has_producer_verb(text)
    has_specific_noun = bool(specific_inferred)
    has_generic_noun = _has_generic_noun(text)
    has_any_noun = has_specific_noun or has_generic_noun

    if has_verb and has_specific_noun:
        inferred_exts = specific_inferred
    else:
        inferred_exts = []

    if explicit_exts:
        confidence = "explicit"
    elif inferred_exts:
        confidence = "inferred"
    elif has_verb or has_any_noun:
        confidence = "ambiguous"
    else:
        confidence = "text_only"

    requires_file = confidence in {"explicit", "inferred", "ambiguous"}

    return PromptClassification(
        requires_file=requires_file,
        explicit_exts=explicit_exts,
        inferred_exts=inferred_exts,
        confidence=confidence,
    )


__all__ = ["PromptClassification", "classify_prompt"]
