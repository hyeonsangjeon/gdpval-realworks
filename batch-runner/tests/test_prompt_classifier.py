"""Tests for core.prompt_classifier.

Unit tests cover the four confidence classes with three fixture prompts each.
The integration test runs the classifier over all 220 Gold Subset prompts and
checks the confidence distribution against HF_PROMPT_ANALYSIS_REPORT.md within
a ±5 task tolerance.  The integration test is opt-in (``-m integration``) and
skips when the HF dataset is unavailable.

Usage:
    pytest tests/test_prompt_classifier.py -v
    pytest tests/test_prompt_classifier.py -m integration -v   # needs HF_TOKEN
"""

import pytest

from core.prompt_classifier import PromptClassification, classify_prompt


# ── Unit fixtures (3 per confidence class) ────────────────────────────────

EXPLICIT_PROMPTS = [
    "Please save your final output as report.docx and submit it by EOD.",
    "Generate a PDF named summary.pdf with the analysis and a chart.png.",
    "Create the deliverable as financial_summary.xlsx and share with the team.",
]

INFERRED_PROMPTS = [
    "Create a comprehensive report covering Q3 performance and risks.",
    "Prepare a slide deck for the board meeting outlining the new strategy.",
    "Generate a spreadsheet that tabulates the survey results by region.",
]

AMBIGUOUS_PROMPTS = [
    # producer_language_no_specific_noun: verb + no recognized noun
    "Please create a comprehensive solution that addresses the customer's concern.",
    # noun_without_producer_verb: noun + no producer verb
    "The report is attached for your reference; review it and reply.",
    # verb with non-recognized noun
    "Build out the complete strategy and walk me through your reasoning.",
]

TEXT_ONLY_PROMPTS = [
    "What is the capital of France?",
    "Explain how photosynthesis works in detail.",
    "How do you feel about climate change overall?",
]


# ── Helper ─────────────────────────────────────────────────────────────────


def _assert_classification(result: PromptClassification, expected_confidence: str):
    assert isinstance(result, PromptClassification)
    assert result.confidence == expected_confidence, (
        f"expected {expected_confidence!r}, got {result.confidence!r}\n"
        f"  explicit_exts={result.explicit_exts}\n"
        f"  inferred_exts={result.inferred_exts}"
    )
    if expected_confidence == "text_only":
        assert result.requires_file is False
    else:
        assert result.requires_file is True


# ── Confidence-class unit tests ────────────────────────────────────────────


@pytest.mark.parametrize("prompt", EXPLICIT_PROMPTS)
def test_classify_explicit(prompt):
    result = classify_prompt(prompt)
    _assert_classification(result, "explicit")
    assert len(result.explicit_exts) >= 1


@pytest.mark.parametrize("prompt", INFERRED_PROMPTS)
def test_classify_inferred(prompt):
    result = classify_prompt(prompt)
    _assert_classification(result, "inferred")
    assert result.explicit_exts == []
    assert len(result.inferred_exts) >= 1


@pytest.mark.parametrize("prompt", AMBIGUOUS_PROMPTS)
def test_classify_ambiguous(prompt):
    result = classify_prompt(prompt)
    _assert_classification(result, "ambiguous")
    assert result.explicit_exts == []
    assert result.inferred_exts == []


@pytest.mark.parametrize("prompt", TEXT_ONLY_PROMPTS)
def test_classify_text_only(prompt):
    result = classify_prompt(prompt)
    _assert_classification(result, "text_only")
    assert result.explicit_exts == []
    assert result.inferred_exts == []


# ── Edge cases ────────────────────────────────────────────────────────────


def test_classify_empty_string():
    result = classify_prompt("")
    _assert_classification(result, "text_only")


def test_classify_none_input():
    result = classify_prompt(None)  # type: ignore[arg-type]
    _assert_classification(result, "text_only")


def test_explicit_extensions_are_lowercased():
    result = classify_prompt("Save as REPORT.DOCX and FIGURE.PNG please.")
    assert ".docx" in result.explicit_exts
    assert ".png" in result.explicit_exts
    assert result.confidence == "explicit"


def test_explicit_dedupes_repeated_extensions():
    result = classify_prompt("Output a.docx and b.docx and c.docx for me.")
    assert result.explicit_exts == [".docx"]


def test_inferred_extension_dedupes_nouns():
    result = classify_prompt(
        "Create a report and another report summarising the data."
    )
    assert result.confidence == "inferred"
    assert result.inferred_exts == [".docx"]


def test_explicit_beats_inferred():
    # Has both an explicit .pdf and a noun "report" with a producer verb.
    result = classify_prompt(
        "Create a report and save it as summary.pdf for review."
    )
    assert result.confidence == "explicit"
    assert ".pdf" in result.explicit_exts


def test_extension_in_filename_not_matched_as_word():
    # ".pdfs" must NOT match .pdf because of trailing word char.
    result = classify_prompt("Discuss PDFs in general and the topic of pdfs.")
    # "pdfs" is a recognized noun mapping to .pdf but without producer verb
    # the confidence is ambiguous (noun_without_producer_verb).
    assert ".pdf" not in result.explicit_exts


# ── Integration test against full Gold Subset (220 prompts) ───────────────


@pytest.mark.integration
def test_distribution_against_hf_report():
    """Validate confidence distribution within ±5 of HF_PROMPT_ANALYSIS_REPORT.

    Report values (Gold Subset, 220 tasks):
        file_required (explicit + inferred): 207
        ambiguous: 10
        text_only: 3
    """
    pd = pytest.importorskip("pandas")
    try:
        from datasets import load_dataset  # type: ignore
    except ImportError:
        pytest.skip("datasets library not installed")

    try:
        ds = load_dataset("openai/gdpval", split="train")
    except Exception as e:  # pragma: no cover - network / auth dependent
        pytest.skip(f"openai/gdpval unavailable: {e}")

    prompts = list(ds["prompt"])
    assert len(prompts) == 220, f"expected 220 prompts, got {len(prompts)}"

    counts = {"explicit": 0, "inferred": 0, "ambiguous": 0, "text_only": 0}
    for p in prompts:
        c = classify_prompt(p).confidence
        counts[c] += 1

    file_required = counts["explicit"] + counts["inferred"]
    # Report: file_required=207, ambiguous=10, text_only=3 (±5 tolerance).
    assert abs(file_required - 207) <= 5, counts
    assert abs(counts["ambiguous"] - 10) <= 5, counts
    assert abs(counts["text_only"] - 3) <= 5, counts
