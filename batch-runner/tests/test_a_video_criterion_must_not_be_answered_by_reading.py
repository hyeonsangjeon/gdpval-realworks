"""A criterion about what is on screen must not be answered by reading bytes.

The sibling of ``test_a_reel_with_a_soundtrack_gets_listened_to``, and the same
defect one probe along. That one fixed ``has_audio_content``, which called
every video silent; this one fixes ``has_extractable_text``, which called every
video unknowable.

``resolve_runtime_routing`` has exactly one escalation: a criterion classified
TEXT or FORMATTING is promoted to VISUAL when the files it points at are
renderable *and* measured to hold no text. It is the only route from a
criterion whose wording carries no visual keyword to the vision path, and it
reads two signals -- ``selected_paths_have_text`` and
``some_selected_path_lacks_text`` -- both fed by ``has_extractable_text``.

That probe returned ``None`` for every video, and ``None`` changes nothing by
design. So both signals were ``None``, the escalation could not fire for a
video-only deliverable, and the criterion stayed on the reading path.

``None`` was the right answer once. While video could not be rendered, a
``False`` would have escalated the item to VISUAL, found no render target and
returned ``required_visual_render_target_unavailable``. Video is renderable now
-- ``_render_video_contact_sheet`` tiles twelve timestamped stills into one
image -- so the premise moved and the answer did not.

What that cost, measured on the two gold tasks that ship an ``.mp4``: 48
criteria routed to the reader, **38 of them scored fail**. Not excluded --
failed. "The visuals include at least one shot clearly depicting wind turbines"
went to a judge holding the container's metadata, which contains no turbine,
and the judge said so. An assertion of absence produced by the question rather
than by the work, and worse than the honest exclusion the four keyword-visual
items on the same tasks received.

(This paragraph said 47 until 2026-09-04. The set is ``fail`` 38, ``pass`` 9
and ``partial`` 1; the original total enumerated the first two and added them
up. Nothing in this file asserted the number, which is how it drifted -- it is
now recomputed from the committed payload in
``test_the_count_of_items_the_judge_was_holding.py``. See ``322`` §11.)

The distinction that matters is again ``False`` versus ``None``, but the burden
runs the other way here. ``False`` sends the item somewhere; the somewhere has
to exist. ``_render_video_contact_sheet`` needs the same PyAV this probe does
and raises on the same empty stream list, so the probe answers ``None``
wherever the renderer could not serve -- no decoder, and a container that is
sound only. Those two cases are pinned below as one property, because an
escalation into a render that cannot happen is the failure this shape exists to
avoid.

These tests encode real MP4 files with PyAV, pinned in ``requirements.txt``.
Nothing here calls a model or a network.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.grader_routing import (  # noqa: E402
    Modality,
    classify_criterion,
    resolve_runtime_routing,
)
from core.media_types import GRADER_VISUAL_RENDER_EXTENSIONS  # noqa: E402
from core.tools.read_deliverable import (  # noqa: E402
    ReadDeliverableError,
    _render_video_contact_sheet,
    _video_has_no_readable_text,
    has_audio_content,
    has_extractable_text,
)

av = pytest.importorskip("av", reason="PyAV is what the video probe uses")
np = pytest.importorskip("numpy")


# Criteria copied verbatim from the graded output of the two gold tasks that
# ship a video. Every one routed TEXT and was scored **fail**, against a
# deliverable whose entire content is pictures.
CRITERIA_THAT_WERE_SCORED_BLIND = (
    "The visuals include at least one shot clearly depicting wind turbines.",
    "Includes a shot of the Golden Gate Bridge.",
    "Includes a shot of restaurant workers in a kitchen or service setting.",
    "At least one shot shows Californians at work (any sector, e.g., office "
    "or restaurant).",
    "Exactly two full-screen text-only graphic cards are used (no underlying "
    "imagery visible).",
    "People reflect visible diversity in age, ethnicity, and gender.",
    "A water simulation shot is included.",
    "There are at least 15 cuts across the full runtime (for reels up to 80 "
    "seconds).",
    "No external watermarks, stock logos, or running timecode overlays are "
    "visible in the picture.",
    "The final logo_2.mp4 end card remains visible on screen for at least "
    "1.0 second.",
)

# The other nine flips. These pass today, they are about the container rather
# than about the picture, and they are the reason this change had to be checked
# rather than argued: a fix that answered them from twelve stills would trade
# 38 wrong failures for nine new ones.
CONTAINER_CRITERIA_THAT_ALREADY_PASS = (
    "Final deliverable is an MP4 file (.mp4 extension)",
    "Primary video codec in the file is H.264/AVC",
    "Video resolution is exactly 1920 x 1080 pixels.",
    "Total runtime is between 29.9 s and 30.1 s inclusive.",
    "The file plays from start to finish without decode errors or corruption.",
)


def _encode_mp4(path: Path, *, video: bool = True, audio: bool = False) -> Path:
    """Write a genuine, tiny MP4.

    Deliberately a copy of the helper in the audio sibling rather than an
    import from it. Test modules that import each other acquire a collection
    order, and the two files are meant to be readable one at a time.
    """
    container = av.open(str(path), mode="w")
    try:
        video_stream = None
        if video:
            video_stream = container.add_stream("mpeg4", rate=5)
            video_stream.width = video_stream.height = 32
            video_stream.pix_fmt = "yuv420p"
        audio_stream = container.add_stream("aac", rate=44100) if audio else None

        if video_stream is not None:
            for _ in range(3):
                container.mux(video_stream.encode(av.VideoFrame(32, 32, "yuv420p")))
            for packet in video_stream.encode(None):
                container.mux(packet)
        if audio_stream is not None:
            frame = av.AudioFrame.from_ndarray(
                np.zeros((1, 1024), dtype="int16"), format="s16", layout="mono"
            )
            frame.sample_rate = 44100
            for packet in audio_stream.encode(frame):
                container.mux(packet)
            for packet in audio_stream.encode(None):
                container.mux(packet)
    finally:
        container.close()
    return path


@pytest.fixture(scope="module")
def reel(tmp_path_factory) -> Path:
    """A video with a soundtrack -- the shape both failing deliverables ship."""
    return _encode_mp4(tmp_path_factory.mktemp("av") / "reel.mp4", audio=True)


@pytest.fixture(scope="module")
def silent_reel(tmp_path_factory) -> Path:
    return _encode_mp4(tmp_path_factory.mktemp("av") / "silent.mp4")


@pytest.fixture(scope="module")
def sound_only(tmp_path_factory) -> Path:
    """An ``.mp4`` carrying no picture. Renderable by extension, not in fact."""
    return _encode_mp4(
        tmp_path_factory.mktemp("av") / "score.mp4", video=False, audio=True
    )


def _no_pyav(monkeypatch) -> None:
    real_import = __import__

    def blocked(name, *args, **kwargs):
        if name == "av":
            raise ImportError("no PyAV here")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", blocked)


def _route(criterion: str, paths, *, probe=has_extractable_text, dir_=None):
    """Route one criterion the way ``core.grader`` does, probes and all."""
    names = [p.name for p in paths]
    lacking = [p.name for p in paths if probe(p) is False]
    answers = [probe(p) for p in paths]
    have_text = None
    if all(a is not None for a in answers):
        have_text = any(answers)
    return resolve_runtime_routing(
        criterion,
        names,
        selected_paths_have_text=have_text,
        selected_paths_have_audio=any(has_audio_content(p) is True for p in paths),
        selected_paths_are_source_code=False,
        some_selected_path_lacks_text=(True if lacking else None),
        paths_without_text=lacking or None,
    )


# ── what the probe says about a container ────────────────────────────────


def test_reading_a_video_answers_nothing_and_the_probe_now_says_so(reel):
    """The whole defect in one assertion."""
    assert has_extractable_text(reel) is False


def test_the_probe_never_claims_a_video_yields_text(reel, silent_reel, sound_only):
    """``True`` would be the same defect from the other side.

    A container can carry a subtitle stream, but no op in this module extracts
    one. Answering ``True`` would suppress the escalation and hand the
    criterion to a reader that comes back with nothing.
    """
    for path in (reel, silent_reel, sound_only):
        assert has_extractable_text(path) is not True, path.name


def test_a_video_that_is_only_sound_admits_it_does_not_know(sound_only):
    """Renderable by extension, and there is nothing to draw.

    ``False`` here would escalate a criterion into a contact sheet that cannot
    be built.
    """
    assert has_extractable_text(sound_only) is None


def test_an_unreadable_video_admits_it_does_not_know(tmp_path):
    corrupt = tmp_path / "truncated.mp4"
    corrupt.write_bytes(b"not a video at all")
    assert has_extractable_text(corrupt) is None


def test_a_missing_decoder_is_an_admission_not_a_claim(reel, monkeypatch):
    """A host without PyAV must not escalate anything.

    It is also the host that cannot render, so ``None`` keeps routing exactly
    where it is today rather than sending items at a renderer that is absent.
    """
    _no_pyav(monkeypatch)
    assert _video_has_no_readable_text(reel) is None
    assert has_extractable_text(reel) is None


def test_the_probe_is_unknown_exactly_where_the_renderer_cannot_serve(
    sound_only, tmp_path, monkeypatch
):
    """The property that makes ``None`` right, rather than a second opinion.

    ``False`` is permission to escalate. These are the states where the
    escalation would arrive at a render that raises, so the probe must not
    grant it -- checked by making the renderer fail rather than by asserting
    the two lists match from memory.
    """
    corrupt = tmp_path / "truncated.mp4"
    corrupt.write_bytes(b"not a video at all")

    for path in (sound_only, corrupt):
        assert has_extractable_text(path) is None, path.name
        with pytest.raises((ReadDeliverableError, Exception)):
            _render_video_contact_sheet(path, 12)

    reel = _encode_mp4(tmp_path / "ok.mp4")
    assert has_extractable_text(reel) is False
    _no_pyav(monkeypatch)
    assert has_extractable_text(reel) is None
    with pytest.raises(ImportError):
        _render_video_contact_sheet(reel, 12)


# ── and what routing does with that answer ───────────────────────────────


@pytest.mark.parametrize("criterion", CRITERIA_THAT_WERE_SCORED_BLIND)
def test_a_criterion_about_the_picture_reaches_the_vision_path(reel, criterion):
    """End to end, on the real criteria that were scored blind.

    Note what classification says: these route TEXT on their wording alone.
    None of them is fixed by adding a keyword -- the escalation is the
    mechanism, and the probe is what had disabled it.
    """
    assert classify_criterion(criterion).modality in (
        Modality.TEXT,
        Modality.FORMATTING,
    )
    decision = _route(criterion, [reel])
    assert decision.modality is Modality.VISUAL, (
        "a criterion about what is on screen was routed to a judge that can "
        "only read the container, and will be scored from its metadata"
    )


@pytest.mark.parametrize("criterion", CRITERIA_THAT_WERE_SCORED_BLIND[:3])
def test_the_escalation_was_unreachable_while_the_probe_said_nothing(reel, criterion):
    """The negative control: pin the defect, so the fix above can fail.

    With the probe restored to the answer it used to give, every one of these
    goes back to the reader. A test that only asserts the new behaviour cannot
    distinguish a working escalation from a criterion that was classified
    VISUAL all along.
    """
    decision = _route(criterion, [reel], probe=lambda _p: None)
    assert decision.modality is Modality.TEXT


def test_a_silent_video_escalates_too(silent_reel):
    """Text and sound are separate questions.

    A reel with no soundtrack still has pictures, and the escalation is about
    what can be read, not what can be heard.
    """
    assert has_extractable_text(silent_reel) is False
    decision = _route("Includes a shot of the Golden Gate Bridge.", [silent_reel])
    assert decision.modality is Modality.VISUAL


def test_a_criterion_about_sound_still_goes_to_the_listening_model(reel):
    """The audio fix must survive this one.

    Both probes now answer for a video container, and the escalation must not
    reach across and take a criterion the listening model owns.
    """
    criterion = (
        'The sound effect file "Mountain Audio - Electricity.mp3" is audible '
        "during the opening logos.mp4 shot."
    )
    assert has_audio_content(reel) is True
    assert _route(criterion, [reel]).modality is Modality.AUDIO


def test_only_the_file_that_cannot_be_read_is_rendered(reel, tmp_path):
    """A bundle is not collapsed to its worst member.

    The video is handed back as the render target; the readable sibling stays
    within reach of ``read_deliverable`` instead of being turned into pictures
    at a call apiece.
    """
    docx = pytest.importorskip("docx", reason="python-docx builds the sibling")
    script = tmp_path / "GreenEnergy-30_Script.docx"
    document = docx.Document()
    document.add_paragraph("Voiceover: Renewable, reliable, green energy.")
    document.save(str(script))

    assert has_extractable_text(script) is True
    decision = _route("Includes a shot of the Golden Gate Bridge.", [reel, script])
    assert decision.modality is Modality.VISUAL
    assert decision.render_targets([reel.name, script.name]) == [reel.name]


def test_a_video_beside_an_unrenderable_sibling_stays_on_the_reader(reel, tmp_path):
    """Existing behaviour, pinned rather than changed.

    The escalation requires every selected suffix to be renderable, so a reel
    delivered next to a ``.txt`` does not reach the vision path -- the bundle
    has something to read, and the rule declines to guess that reading it will
    not answer. Neither gold task ships this shape, so nothing measured here
    turns on it.

    Recorded because it is the remaining way a criterion about the picture can
    still be answered from prose, and because a later change to that guard
    should have to come past this line deliberately.
    """
    notes = tmp_path / "treatment.txt"
    notes.write_text("A thirty second spot about green energy.", encoding="utf-8")
    decision = _route("Includes a shot of the Golden Gate Bridge.", [reel, notes])
    assert decision.modality is Modality.TEXT


@pytest.mark.parametrize("criterion", CONTAINER_CRITERIA_THAT_ALREADY_PASS)
def test_a_container_criterion_keeps_the_reader_it_is_answered_from(reel, criterion):
    """The nine flips that already pass, and why they do not regress.

    Codec, resolution, runtime and decode integrity are properties of the
    container, not of twelve downscaled stills. They flip to VISUAL under this
    change, so the guarantee they need is that VISUAL adds a picture rather
    than replacing the reader: ``preflight_visual`` appends its findings to the
    main judge's prompt, and ``_build_tools_for`` hands every modality
    ``read_deliverable``.

    Pinned here as the tool list, because that is the thing whose change would
    break them.
    """
    from core.tool_calling_judge import ToolCallingJudge

    decision = _route(criterion, [reel])
    assert decision.modality is Modality.VISUAL
    tool_names = {
        tool["name"] if "name" in tool else tool.get("function", {}).get("name")
        for tool in ToolCallingJudge._build_tools_for(
            _StubJudge(), decision.modality.value
        )
    }
    assert "read_deliverable" in tool_names


class _StubJudge:
    """Just enough of the judge for ``_build_tools_for``, which reads two attrs."""

    model_read_ops = ("read_content", "inspect_formatting", "probe_video")
    audio_perception = None


# ── non-regression: every other kind answers exactly as before ───────────


def test_the_other_media_are_unchanged(tmp_path):
    """None of this may move the answers the probe already got right."""
    text = tmp_path / "notes.txt"
    text.write_text("hello", encoding="utf-8")
    empty = tmp_path / "empty.txt"
    empty.write_text("   ", encoding="utf-8")
    image = tmp_path / "poster.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
    sound = tmp_path / "sfx.mp3"
    sound.write_bytes(b"\x00" * 32)
    archive = tmp_path / "bundle.zip"
    archive.write_bytes(b"\x00" * 32)

    assert has_extractable_text(text) is True
    assert has_extractable_text(empty) is False
    assert has_extractable_text(image) is False
    assert has_extractable_text(sound) is None
    assert has_extractable_text(archive) is None
    assert has_extractable_text(tmp_path / "gone.mp4") is None


def test_video_is_renderable_which_is_what_makes_false_safe():
    """The premise, asserted rather than assumed.

    If ``.mp4`` ever leaves the render set, ``False`` becomes the wrong answer
    again and this line is where that gets said first.
    """
    assert ".mp4" in GRADER_VISUAL_RENDER_EXTENSIONS


def test_both_probes_now_answer_for_the_same_container(reel):
    """The asymmetry that was the finding.

    ``has_audio_content`` learned about video containers and
    ``has_extractable_text`` did not, so one of the two questions a routing
    decision asks about a reel was answerable and the other was not.
    """
    assert has_audio_content(reel) is not None
    assert has_extractable_text(reel) is not None
