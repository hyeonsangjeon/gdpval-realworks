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
from core.media_types import GRADER_VISUAL_RENDER_EXTENSIONS


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


def test_chart_of_accounts_is_not_a_visual_chart():
    decision = classify_criterion(
        "Expense classification uses chart-of-accounts numbers consistent "
        "with COA.xlsx."
    )

    assert decision.modality is Modality.TEXT
    assert decision.preferred_op == "read_content"


def test_chart_of_accounts_with_explicit_layout_stays_visual():
    decision = classify_criterion(
        "The chart of accounts layout is visually clear."
    )

    assert decision.modality is Modality.VISUAL
    assert decision.matched_keywords == ("layout",)


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


def test_audio_keyword_with_xlsx_target_downgrades_to_text():
    criterion = (
        "Band and Crew includes Sound Technician fees attributed to the tour "
        "manager."
    )

    assert classify_criterion(criterion).modality is Modality.AUDIO
    decision = resolve_runtime_routing(criterion, ["tour_budget.xlsx"])

    assert decision.modality is Modality.TEXT
    assert decision.preferred_op == "read_content"
    assert decision.matched_keywords == ("sound",)


def test_audio_keyword_with_extensionless_target_stays_audio():
    decision = resolve_runtime_routing(
        "Audio mix avoids clipping", ["recording"]
    )

    assert decision.modality is Modality.AUDIO
    assert decision.preferred_op == "probe_audio"


def test_audio_keyword_with_known_unsupported_target_downgrades_to_text():
    decision = resolve_runtime_routing(
        "Audio mix avoids clipping", ["recording.wma"]
    )

    assert decision.modality is Modality.TEXT
    assert decision.preferred_op == "read_content"


@pytest.mark.parametrize("suffix", [".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac"])
def test_audio_keyword_with_supported_audio_target_remains_audio(suffix: str):
    decision = resolve_runtime_routing(
        "Audio mix avoids clipping and excessive noise",
        [f"deliverable{suffix}"],
    )

    assert decision.modality is Modality.AUDIO
    assert decision.preferred_op == "probe_audio"


def test_runtime_audio_resolution_is_target_specific():
    criterion = "The sound is clear and free from clipping"

    audio_child = resolve_runtime_routing(criterion, ["mix.wav"])
    text_child = resolve_runtime_routing(criterion, ["budget.xlsx"])

    assert audio_child.modality is Modality.AUDIO
    assert text_child.modality is Modality.TEXT


# ── visual with nothing renderable ──────────────────────────────────────────
# A criterion that asks for a channel none of the selected files can supply
# has to go somewhere. Where depends on whether text is an honest substitute,
# which is why this is narrower than the audio rule above.


def test_overall_style_criterion_with_only_plain_text_downgrades_to_text():
    # The whole of task 2c249e0f on the sol-220 rerun: one ``data_flow.txt``,
    # graded on "Overall formatting and style". There is no visual form of
    # this file anywhere, so visual routing was unanswerable by construction —
    # while the text in front of the judge shows its formatting directly.
    criterion = "Overall formatting and style of the deliverable"

    assert classify_criterion(criterion).modality is Modality.VISUAL
    decision = resolve_runtime_routing(criterion, ["data_flow.txt"])

    assert decision.modality is Modality.TEXT
    assert decision.preferred_op == "read_content"


def test_explicitly_visual_criterion_with_nothing_renderable_stays_visual():
    # The line this rule must not cross, and the reason it is not a
    # straight copy of the audio fallback. Colour and page layout cannot be
    # read out of the characters in a file: demoting here would trade a
    # missing verdict for an invented one, which is strictly worse.
    # ``test_explicit_visual_item_fails_closed_without_render_target`` in
    # tests/test_grader_selector_integration.py pins the same property
    # end to end.
    decision = resolve_runtime_routing(
        "Document color and page layout are visually polished", ["Summary.csv"]
    )

    assert decision.modality is Modality.VISUAL
    assert decision.preferred_op == "render_to_image"


def test_one_renderable_file_keeps_the_item_visual():
    # The guard that makes this change safe. A mixed bundle still routes
    # visual, so no item that renders today is diverted to text.
    decision = resolve_runtime_routing(
        "Overall formatting and style of the deliverable",
        ["summary.txt", "plan.xlsx"],
    )

    assert decision.modality is Modality.VISUAL
    assert decision.preferred_op == "render_to_image"


def test_split_children_route_the_text_child_away_from_visual():
    # Task bf68f2ad, at the granularity ``grader.py`` actually routes at.
    # Before this rule the ``.txt`` child errored, and because a split_children
    # item fails whole on its first child error, the ``.xlsx`` sibling was
    # dragged down with it — the published item has visual_provenance == [].
    criterion = "Overall formatting and style of the deliverable"

    xlsx_child = resolve_runtime_routing(criterion, ["MIG_Welding_Catch_Up_Plan.xlsx"])
    txt_child = resolve_runtime_routing(criterion, ["MIG_Welding_Catch_Up_Summary.txt"])

    assert xlsx_child.modality is Modality.VISUAL
    assert txt_child.modality is Modality.TEXT


def test_overall_style_with_extensionless_target_stays_visual():
    # Mirrors ``test_audio_keyword_with_extensionless_target_stays_audio``.
    # No suffix means no evidence either way, and demoting on absence of
    # evidence would silently strip vision from anything oddly named.
    decision = resolve_runtime_routing(
        "Overall formatting and style of the deliverable", ["deliverable"]
    )

    assert decision.modality is Modality.VISUAL
    assert decision.preferred_op == "render_to_image"


@pytest.mark.parametrize("suffix", sorted(GRADER_VISUAL_RENDER_EXTENSIONS))
def test_every_renderable_suffix_still_routes_visual(suffix: str):
    decision = resolve_runtime_routing(
        "Chart is clearly labeled and easy to read", [f"deliverable{suffix}"]
    )

    assert decision.modality is Modality.VISUAL


def test_visual_render_extensions_match_the_renderer():
    """Hold the routing set equal to what the prepass can actually render.

    ``GRADER_VISUAL_RENDER_EXTENSIONS`` is a copy of the keys of
    ``tool_calling_judge._VISUAL_RENDER_SCOPES``; the original cannot be
    imported into ``grader_routing`` without pulling the grading stack into a
    module that is deliberately pure. A suffix added to one and not the other
    fails in silence -- either routing sends a renderable file to text, or it
    promises a render the prepass will refuse -- so the equality is asserted
    rather than trusted.
    """
    from core.tool_calling_judge import _VISUAL_RENDER_SCOPES

    assert set(_VISUAL_RENDER_SCOPES) == set(GRADER_VISUAL_RENDER_EXTENSIONS)


def test_downgraded_visual_keeps_its_matched_keywords():
    # The demotion changes where the judge looks, not what the criterion was
    # found to be asking for. Losing the keywords would make a downgraded item
    # indistinguishable from one that never matched anything.
    criterion = "Overall formatting and style of the deliverable"
    decision = resolve_runtime_routing(criterion, ["notes.txt"])

    assert decision.modality is Modality.TEXT
    assert decision.matched_keywords == classify_criterion(criterion).matched_keywords
    assert decision.matched_keywords != ()


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
