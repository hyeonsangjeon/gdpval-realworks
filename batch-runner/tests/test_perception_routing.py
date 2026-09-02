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


# ── Source code: the one explicitly-visual criterion that may demote ──
#
# The five items and eight points of task 7de33b48, on one
# ``screen_reader_status_message.zip`` holding two ``.tsx``, a ``.css``, a
# ``README.md`` and a ``package.json``. Every one was sorted visual by the
# words ``render``, ``layout`` and ``visual`` in its text, and every one was
# excluded as ``required_visual_render_target_unavailable`` -- against a
# submission with no picture in it anywhere, whose appearance is not a
# property of the submission at all but of something that builds and runs it.

SOURCE_CRITERIA = [
    'Before any status message occurs, the rendered DOM includes an element '
    'with role="status".',
    'When a status message is triggered, its content is rendered inside the '
    'element with role="status".',
    "ScreenReaderStatusMessage.css defines a class to visually hide the live "
    "region while keeping it in the accessibility tree (no visual impact on "
    "layout).",
    "Tests verify that enabling visible does not change the surrounding "
    "rendered text content or layout.",
    "ScreenReaderStatusMessage.test.tsx uses React Testing Library to render "
    "and query the component.",
]


@pytest.mark.parametrize("criterion", SOURCE_CRITERIA)
def test_a_source_archive_answers_its_own_visual_criteria(criterion: str):
    # Classification is untouched -- these really do name rendering, and a
    # ``.png`` beside them would still be looked at. What changes is where an
    # item goes when the only place the answer is written down is the source.
    assert classify_criterion(criterion).modality is Modality.VISUAL

    decision = resolve_runtime_routing(
        criterion,
        ["screen_reader_status_message.zip"],
        selected_paths_are_source_code=True,
    )

    assert decision.modality is Modality.TEXT
    assert decision.preferred_op == "read_content"


def test_a_csv_is_still_not_source_and_still_fails_closed():
    # The rule directly above this one, unchanged. The probe answers ``False``
    # for a ``.csv`` -- data has a look a reader sees on opening it -- so the
    # item stays visual and a missing verdict is not traded for an invented
    # one.
    decision = resolve_runtime_routing(
        "Document color and page layout are visually polished.",
        ["Summary.csv"],
        selected_paths_are_source_code=False,
    )

    assert decision.modality is Modality.VISUAL


@pytest.mark.parametrize("answer", [None, False])
def test_only_a_measured_yes_demotes_an_explicitly_visual_item(answer):
    # ``None`` is the unreadable archive, the missing file and the member list
    # cut short. Demoting on any of those is the guess the tri-state exists to
    # refuse, so silence leaves the item exactly where it was.
    decision = resolve_runtime_routing(
        SOURCE_CRITERIA[0],
        ["screen_reader_status_message.zip"],
        selected_paths_are_source_code=answer,
    )

    assert decision.modality is Modality.VISUAL


def test_the_suffix_test_is_the_second_lock_on_the_source_demotion():
    # Either lock alone would do, and this is the one that survives the probe
    # falling behind: put ``.html`` in the render set tomorrow and a file the
    # prepass had just learned to draw cannot be demoted here, whatever a
    # stale probe says about it.
    decision = resolve_runtime_routing(
        SOURCE_CRITERIA[0],
        ["component.png"],
        selected_paths_are_source_code=True,
    )

    assert decision.modality is Modality.VISUAL
    assert decision.preferred_op == "render_to_image"


def test_a_source_demotion_cannot_be_undone_by_the_unreadable_escalation():
    # The last rule in the module promotes a text item whose files hold no
    # characters. A ``.zip`` is not in the render set, so the item it just
    # demoted stays demoted rather than bouncing back to a render that would
    # error -- and ``has_extractable_text`` answers ``None`` for an archive
    # anyway, so the signal never fires here in the first place.
    decision = resolve_runtime_routing(
        SOURCE_CRITERIA[0],
        ["screen_reader_status_message.zip"],
        selected_paths_are_source_code=True,
        selected_paths_have_text=False,
        some_selected_path_lacks_text=True,
        paths_without_text=["screen_reader_status_message.zip"],
    )

    assert decision.modality is Modality.TEXT
    assert decision.render_paths is None


VIDEO_CRITERIA = [
    "Both graphic cards use white text on a solid black background in a "
    "clean sans-serif font.",
    "The first non-logo content shot begins within 7.0 seconds of the start.",
    "The image is not stretched or squashed; aspect ratio is preserved for "
    "all included shots.",
    "The image fills the 1920x1080 frame without unintended letterboxing or "
    "pillarboxing.",
]


@pytest.mark.parametrize("criterion", VIDEO_CRITERIA)
def test_the_video_items_this_rule_does_not_reach_are_left_alone(criterion):
    # The other four of the nine items that cannot be judged today, and the
    # reason this change is not claimed as a fix for all nine. A reel really
    # does have to be watched; ``_kind_of`` gives it its own kind rather than
    # ``zip``, the probe answers ``False``, and the item stays visual and stays
    # excluded -- which is the honest outcome, not a gap. Deciding otherwise
    # would mean sampling a frame and turning "could not see it" into a
    # verdict about the frame that happened to be picked.
    decision = resolve_runtime_routing(
        criterion, ["reel.mp4"], selected_paths_are_source_code=False
    )

    assert decision.modality is Modality.VISUAL


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


# ── A file with no text answers nothing from its text ────────────────
#
# Stage 1 graded one gold answer that is a two-page scan. Ten rubric items
# about its contents routed TEXT, read zero characters, and were failed as
# "that content is absent" -- about a document that says all ten things, on
# pages the harness had already rendered for the same task's other items.
#
# The escalation below is the fix, and these tests pin the three conditions
# that keep it from doing harm: it fires only on a measured ``False``, only
# from the two modalities that were asking for text, and only when every
# selected file can actually be rendered.


def test_a_text_criterion_escalates_when_no_selected_file_has_text():
    decision = resolve_runtime_routing(
        "The memo states the total contract value",
        ["scan.pdf"],
        selected_paths_have_text=False,
    )

    assert decision.modality is Modality.VISUAL
    assert decision.preferred_op == "render_to_image"


def test_a_formatting_criterion_escalates_on_the_same_evidence():
    # FORMATTING escalates for the same reason TEXT does: `inspect_formatting`
    # on a scan reports the page box and nothing about the layout drawn on it.
    decision = resolve_runtime_routing(
        "The document structure follows the required template",
        ["scan.pdf"],
        selected_paths_have_text=False,
    )

    assert decision.modality is Modality.VISUAL


def test_an_unknown_text_layer_escalates_nothing():
    # ``None`` is what the probe returns for a file it could not examine in
    # full -- unsupported kind, read error, page cap. Escalating on it would
    # trade a readable file for a render on a guess.
    decision = resolve_runtime_routing(
        "The memo states the total contract value",
        ["report.pdf"],
        selected_paths_have_text=None,
    )

    assert decision.modality is Modality.TEXT
    assert decision.preferred_op == "read_content"


def test_a_file_that_has_text_is_never_escalated():
    decision = resolve_runtime_routing(
        "The memo states the total contract value",
        ["report.pdf"],
        selected_paths_have_text=True,
    )

    assert decision.modality is Modality.TEXT


def test_escalation_needs_every_selected_file_to_be_renderable():
    # ``.txt`` has no renderer. Escalating a set containing one would promise
    # a render the prepass refuses, which is a guaranteed harness error --
    # strictly worse than the empty read this rule exists to replace.
    decision = resolve_runtime_routing(
        "The memo states the total contract value",
        ["scan.pdf", "appendix.txt"],
        selected_paths_have_text=False,
    )

    assert decision.modality is Modality.TEXT


def test_escalation_needs_a_selected_file_at_all():
    decision = resolve_runtime_routing(
        "The memo states the total contract value",
        [],
        selected_paths_have_text=False,
    )

    assert decision.modality is Modality.TEXT


def test_an_audio_criterion_on_its_own_medium_is_not_escalated():
    # ``.wav`` is not renderable, so the escalation cannot reach an item that
    # is already pointed at the sense that answers it.
    decision = resolve_runtime_routing(
        "The mix has no clipping",
        ["stems.wav"],
        selected_paths_have_text=False,
    )

    assert decision.modality is Modality.AUDIO
    assert decision.preferred_op == "probe_audio"


def test_an_escalated_decision_keeps_its_matched_keywords():
    # Mirrors ``test_downgraded_visual_keeps_its_matched_keywords``: moving an
    # item changes where the judge looks, not what the criterion was found to
    # be asking for.
    criterion = "The document structure follows the required template"
    decision = resolve_runtime_routing(
        criterion, ["scan.pdf"], selected_paths_have_text=False
    )

    assert decision.modality is Modality.VISUAL
    assert decision.matched_keywords == classify_criterion(criterion).matched_keywords
    assert decision.matched_keywords != ()


@pytest.mark.parametrize("criterion,_expected", CASES)
@pytest.mark.parametrize(
    "paths",
    [[], ["deliverable"], ["notes.txt"], ["report.pdf"], ["mix.wav"],
     ["book.xlsx", "slides.pptx"]],
)
def test_omitting_the_probe_is_identical_to_not_knowing(criterion, _expected, paths):
    """The new argument's default must be inert.

    The three pre-existing rules were rewritten from separate ``return``
    statements into one ``if``/``elif`` chain to make room for the escalation.
    That is only safe if no two of them could ever have fired together, which
    is an argument about code rather than a fact about it -- so it is asserted
    here across every criterion and target shape the module is tested with.
    """
    assert resolve_runtime_routing(criterion, paths) == resolve_runtime_routing(
        criterion, paths, selected_paths_have_text=None
    )


# ── An archive of stems is audio ─────────────────────────────────────
#
# ``resolve_runtime_routing`` demotes an AUDIO criterion whose files carry no
# audio, because a question about a mix has no meaning against a spreadsheet.
# The test for that was the file extension, which reads a container as if it
# were a medium: the stage-1 music task ships one ``.zip``, ``.zip`` is not an
# audio extension, and so all ten of its listening criteria were demoted to
# TEXT and answered by reading an archive. ``selected_paths_have_audio`` is the
# measured fact the extension was standing in for.

_STEMS = ["DEJA VU  STEMS .zip"]
_MIX_CRITERION = "The Master track contains no vocals (instrumental-only)."


def test_an_archive_that_holds_audio_keeps_its_listening_route():
    decision = resolve_runtime_routing(
        _MIX_CRITERION, _STEMS, selected_paths_have_audio=True
    )

    assert decision.modality is Modality.AUDIO
    assert decision.preferred_op == "probe_audio"


def test_an_archive_with_no_audio_in_it_is_still_demoted():
    decision = resolve_runtime_routing(
        _MIX_CRITERION, _STEMS, selected_paths_have_audio=False
    )

    assert decision.modality is Modality.TEXT


def test_an_archive_it_could_not_open_is_still_demoted():
    """``None`` is an admission and must not be read as a yes.

    One gold deliverable is a ``.zip`` that will not open. Promoting on that
    would hand the listening model a file nothing can extract.
    """
    decision = resolve_runtime_routing(
        _MIX_CRITERION, _STEMS, selected_paths_have_audio=None
    )

    assert decision.modality is Modality.TEXT


def test_a_wav_never_needed_the_probe_and_still_does_not():
    for probe in (True, False, None):
        decision = resolve_runtime_routing(
            _MIX_CRITERION, ["master.wav"], selected_paths_have_audio=probe
        )
        assert decision.modality is Modality.AUDIO


def test_finding_audio_cannot_promote_a_criterion_that_is_not_about_sound():
    """The probe is defensive only. It stops a demotion; it never routes.

    Otherwise every item on a music task -- including "the filename is
    correct" -- would be sent to a listening model.
    """
    decision = resolve_runtime_routing(
        "The deliverable is named DEJA VU STEMS.",
        _STEMS,
        selected_paths_have_audio=True,
    )

    assert decision.modality is Modality.TEXT


def test_finding_audio_does_not_disturb_a_visual_criterion():
    decision = resolve_runtime_routing(
        "The chart colors are legible.",
        ["deck.pptx", "master.wav"],
        selected_paths_have_audio=True,
    )

    assert decision.modality is Modality.VISUAL


@pytest.mark.parametrize("criterion", [
    "The Master track contains no vocals (instrumental-only).",
    "The Master track tempo is 140 BPM (± 1 BPM).",
    "From the beginning through 1:22, the harmonic key centers on G major.",
    "At least one time-based effect is audibly evident in the tails.",
    "The Bass sound is created using one of the referenced synth families.",
])
def test_the_music_criteria_that_matched_nothing_now_classify_audio(criterion):
    """Verbatim from the stage-1 rubric that scored 0 on every one of them."""
    assert classify_criterion(criterion).modality is Modality.AUDIO


@pytest.mark.parametrize("criterion", [
    "The delay stems from a supplier issue.",
    "She was instrumental in closing the deal.",
    "Revenue is on track for Q3.",
    "The report lists the key findings.",
    "The chord of the argument is consistent",
])
def test_ordinary_business_english_is_not_mistaken_for_music(criterion):
    """The words rejected while choosing the additions, kept as a guard.

    The last one is deliberate: "chord" IS an audio keyword, and this shows
    what happens when one slips through. It classifies AUDIO and is then
    demoted by the file it points at, which is why a stray hit costs nothing.
    """
    assert resolve_runtime_routing(
        criterion, ["report.docx"], selected_paths_have_audio=False
    ).modality is not Modality.AUDIO


@pytest.mark.parametrize("criterion,_expected", CASES)
@pytest.mark.parametrize("paths", [[], ["deliverable"], ["stems.zip"],
                                   ["master.wav"], ["report.pdf"]])
def test_omitting_the_audio_probe_is_identical_to_not_knowing(
    criterion, _expected, paths
):
    assert resolve_runtime_routing(criterion, paths) == resolve_runtime_routing(
        criterion, paths, selected_paths_have_audio=None
    )


# ── One readable file stops answering for the rest (task 79) ─────────
#
# The escalation above asks the bundle a single question -- "is there any text
# here" -- and a bundle answers yes the moment one file yields a character.
# A stage-3 task selected two PDFs: a two-page Loss Prevention flowchart
# holding zero characters, page one being a single full-page image, and a
# readable Missing Bank Deposits memo of 1,756 characters. The memo answered
# for both. The item stayed TEXT, `perception_called` was false, the render
# count was zero, and the flowchart -- which is a picture, and is what the
# criterion was about -- was never looked at by anything. The task scored
# 40.00%.
#
# A sibling that can be read is not evidence about the file that cannot, so
# the file question is now asked alongside the bundle question. The same three
# conditions still bound it.


def test_a_picture_beside_a_readable_file_still_reaches_the_eyes():
    decision = resolve_runtime_routing(
        "The flowchart shows the escalation path for a suspected theft",
        ["flowchart.pdf", "memo.pdf"],
        selected_paths_have_text=True,
        some_selected_path_lacks_text=True,
    )

    assert decision.modality is Modality.VISUAL
    assert decision.preferred_op == "render_to_image"


def test_a_bundle_whose_files_can_all_be_read_is_left_alone():
    """The common case must not be dragged to vision by the new question."""
    decision = resolve_runtime_routing(
        "The memo states the total contract value",
        ["memo.pdf", "appendix.pdf"],
        selected_paths_have_text=True,
        some_selected_path_lacks_text=False,
    )

    assert decision.modality is Modality.TEXT


def test_an_unanswerable_file_does_not_escalate_on_a_guess():
    """``None`` is an admission, not a no. It must change nothing."""
    decision = resolve_runtime_routing(
        "The memo states the total contract value",
        ["memo.pdf", "mystery.bin"],
        selected_paths_have_text=True,
        some_selected_path_lacks_text=None,
    )

    assert decision.modality is Modality.TEXT


def test_the_new_question_still_obeys_the_renderable_condition():
    """Escalating must never trade a readable file for an unviewable one."""
    decision = resolve_runtime_routing(
        "The notes state the total contract value",
        ["memo.pdf", "recording.wav"],
        selected_paths_have_text=True,
        some_selected_path_lacks_text=True,
    )

    assert decision.modality is not Modality.VISUAL


def test_omitting_the_new_question_changes_no_existing_decision():
    """Every caller that never passes it must route exactly as before."""
    for criterion, paths in (
        ("The memo states the total contract value", ["memo.pdf"]),
        ("The chart uses the brand colour palette", ["deck.pptx"]),
        ("The narration is free of clipping", ["take.wav"]),
        ("The document structure follows the template", ["report.docx"]),
    ):
        assert resolve_runtime_routing(criterion, paths) == resolve_runtime_routing(
            criterion, paths, some_selected_path_lacks_text=None
        )
