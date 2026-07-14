"""Tests for ``core.grader_routing`` (PR2 task 204).

Kept separate from ``tests/test_grader_routing.py`` which covers the
**legacy tier routing** baked into ``core.grader``. Different concern,
different module — easier to delete the legacy file in task 207 without
losing the perception-routing tests.
"""

from __future__ import annotations

import pytest

from core.grader_routing import (
    Modality,
    RoutingDecision,
    classify_criterion,
    inventory,
    is_overall_style_criterion,
    resolve_runtime_routing,
)


# Twelve representative criterion phrasings — covers all four buckets
# and a couple of "tricky" cases (visual + formatting in same sentence,
# audio with formatting word, content with no signal).
CASES = [
    # visual
    ("Chart is clearly labeled and easy to read", Modality.VISUAL),
    ("The graph uses an appropriate color scheme", Modality.VISUAL),
    ("Overall visual polish of the rendered slide", Modality.VISUAL),
    ("Layout of the diagram is symmetric and clean", Modality.VISUAL),
    # audio
    ("Audio mix avoids clipping on loud passages", Modality.AUDIO),
    ("Voice recording has minimal silence between phrases", Modality.AUDIO),
    ("Music maintains consistent loudness across tracks", Modality.AUDIO),
    # overall style is a visual-quality judgment; plain structure stays formatting
    ("Overall formatting and style of the deliverable", Modality.VISUAL),
    ("Document structure follows the requested template", Modality.FORMATTING),
    # text (default)
    ("All required columns are present in the data table", Modality.TEXT),
    ("Includes a summary paragraph of at least 100 words", Modality.TEXT),
    ("References the correct date range in the analysis", Modality.TEXT),
]


@pytest.mark.parametrize("text,expected", CASES)
def test_classifier_matrix(text: str, expected: Modality):
    assert classify_criterion(text).modality is expected


def test_visual_beats_formatting_when_both_present():
    """A criterion that mentions both visual and formatting words must
    route VISUAL — visual judgment subsumes the formatting check."""
    d = classify_criterion("Chart formatting and color scheme are clean")
    assert d.modality is Modality.VISUAL
    assert "chart" in d.matched_keywords
    # the 'formatting' word is present but the visual hit wins by priority
    assert d.preferred_op == "render_to_image"


@pytest.mark.parametrize(
    "text",
    [
        "Overall Style",
        "Overall formatting and style of the deliverable",
        "The overall presentation and professional polish",
    ],
)
def test_overall_style_routes_visual(text: str):
    assert is_overall_style_criterion(text) is True
    decision = classify_criterion(text)
    assert decision.modality is Modality.VISUAL
    assert decision.preferred_op == "render_to_image"


def test_docx_only_overall_style_runtime_route_uses_formatting():
    criterion = "Overall formatting and style of the deliverable"

    assert classify_criterion(criterion).modality is Modality.VISUAL
    decision = resolve_runtime_routing(criterion, ["reports/brief.docx"])

    assert decision.modality is Modality.FORMATTING
    assert decision.preferred_op == "inspect_formatting"


def test_explicit_visual_docx_criterion_remains_visual_at_runtime():
    decision = resolve_runtime_routing(
        "The document color and page layout are visually polished",
        ["reports/brief.docx"],
    )

    assert decision.modality is Modality.VISUAL
    assert decision.preferred_op == "render_to_image"


def test_mixed_overall_style_target_remains_visual_at_parent_level():
    decision = resolve_runtime_routing(
        "Overall Style", ["brief.docx", "appendix.pdf"]
    )

    assert decision.modality is Modality.VISUAL


def test_routing_decision_to_prompt_hint_keys():
    d = classify_criterion("audio mix")
    hint = d.to_prompt_hint()
    assert hint == {
        "routing_modality": "audio",
        "routing_preferred_op": "probe_audio",
    }


def test_empty_or_none_criterion_defaults_to_text():
    assert classify_criterion("").modality is Modality.TEXT
    assert classify_criterion(None).modality is Modality.TEXT  # type: ignore[arg-type]


def test_case_insensitive_match():
    assert classify_criterion("CHART quality").modality is Modality.VISUAL
    assert classify_criterion("Audio Mix").modality is Modality.AUDIO


def test_word_boundary_avoids_substring_false_match():
    # 'formatted' should hit FORMATTING, but a stray substring like
    # 'platform' must not — it contains no whole word.
    assert classify_criterion("The platform stores data").modality is Modality.TEXT
    assert classify_criterion("The output is formatted nicely").modality is Modality.FORMATTING


def test_preferred_op_one_of_known_set():
    allowed = {"render_to_image", "probe_audio", "inspect_formatting", "read_content"}
    for text, _ in CASES:
        assert classify_criterion(text).preferred_op in allowed


def test_inventory_counts():
    counts = inventory([c for c, _ in CASES])
    # 5 visual, 3 audio, 1 formatting, 3 text per the CASES table
    assert counts == {"visual": 5, "audio": 3, "formatting": 1, "text": 3}
