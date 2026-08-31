"""A criterion about sound must not be answered by a judge that cannot hear.

``resolve_runtime_routing`` demotes an AUDIO criterion to TEXT when the files
it is pointed at carry no audio, and that rule is right: "the mix is balanced"
has no meaning against a spreadsheet, and sending it to a listening model
would cost money to learn nothing. The rule reads the file extension, with a
measured probe -- ``has_audio_content`` -- allowed to overrule it.

The probe answered ``False`` for every video container. ``False`` is not "I
don't know"; it is a positive claim that the file was examined and holds no
audio. So a reel delivered as ``.mp4`` was declared silent, every listening
criterion on it was demoted, and a judge holding nothing but the file's
metadata scored them. On gold task ``75401f7c`` that produced eleven items of
the form "the sound effect is audible during the opening shot", each marked
**fail, 0 of 2**, on evidence reading ``"audio_tracks": 1`` -- the container's
own count of the audio it was said not to have.

The distinction that matters is between ``False`` and ``None``. A failed or
impossible perception must not become a deliverable-quality failure: where the
grader cannot look, it excludes the item rather than scoring it zero. Demotion
to TEXT is not exclusion -- it is scoring by another route -- so a probe that
guesses ``False`` converts "we did not listen" into "the work is bad". That is
why the no-decoder and unreadable cases below assert ``None``.

These tests encode real MP4 files with PyAV, which is pinned in
``requirements.txt`` and used by the video probe itself. Nothing here calls a
model or a network.
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
from core.tools.read_deliverable import (  # noqa: E402
    _video_audio_track_count,
    has_audio_content,
)

av = pytest.importorskip("av", reason="PyAV is what the video probe uses")
np = pytest.importorskip("numpy")


# Criteria copied verbatim from the graded output of gold task 75401f7c,
# where each one was scored fail 0/2 without a single listening call.
CRITERIA_THAT_WERE_SCORED_DEAF = (
    'The sound effect file "Mountain Audio - Electricity.mp3" is audible '
    "during the opening logos.mp4 shot.",
    "A music track is present in the mix (separate from SFX and any allowed "
    "embedded audio).",
    "The music track exhibits a high-energy rock or electronic style "
    "consistent with the prompt's intent.",
)


def _encode_mp4(path: Path, *, audio: bool, video: bool = True) -> Path:
    """Write a genuine, tiny MP4 -- roughly 2 KB and a few milliseconds.

    Every stream is declared before anything is muxed: adding one after the
    first packet is written raises ``Cannot rebase to zero time``.
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
    """A video that has a soundtrack, like the deliverable that failed."""
    return _encode_mp4(tmp_path_factory.mktemp("av") / "reel.mp4", audio=True)


@pytest.fixture(scope="module")
def silent_reel(tmp_path_factory) -> Path:
    return _encode_mp4(tmp_path_factory.mktemp("av") / "silent.mp4", audio=False)


# ── what the probe now says about a container ────────────────────────────


def test_a_video_with_a_soundtrack_reports_audio(reel):
    """The whole defect in one assertion."""
    assert has_audio_content(reel) is True


def test_a_genuinely_silent_video_still_reports_no_audio(silent_reel):
    """The demotion rule is correct and must survive the fix.

    Over-correcting to "every video might have sound" would send listening
    calls at silent renders and pay for them.
    """
    assert has_audio_content(silent_reel) is False


def test_a_video_that_is_only_sound_reports_audio(tmp_path):
    """Why the probe counts audio streams rather than reusing the video probe.

    ``_probe_video_impl`` returns early when a container holds no video
    stream, so borrowing it would report ``None`` for a file that is nothing
    but audio.
    """
    only_sound = _encode_mp4(tmp_path / "score.mp4", audio=True, video=False)
    assert has_audio_content(only_sound) is True


def test_an_unreadable_video_admits_it_does_not_know(tmp_path):
    """``None``, never ``False`` -- see the module docstring."""
    corrupt = tmp_path / "truncated.mp4"
    corrupt.write_bytes(b"not a video at all")
    assert has_audio_content(corrupt) is None


def test_a_missing_decoder_is_an_admission_not_a_denial(reel, monkeypatch):
    """A machine without PyAV must not silently mark every reel silent.

    ``False`` here would reintroduce the defect on exactly the hosts least
    able to notice it.
    """
    real_import = __import__

    def no_av(name, *args, **kwargs):
        if name == "av":
            raise ImportError("no PyAV here")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", no_av)
    assert _video_audio_track_count(reel) is None
    assert has_audio_content(reel) is None


# ── and what routing does with that answer ───────────────────────────────


@pytest.mark.parametrize("criterion", CRITERIA_THAT_WERE_SCORED_DEAF)
def test_a_listening_criterion_on_a_reel_is_not_demoted_to_text(reel, criterion):
    """End to end, on the real criteria that were scored deaf.

    Classification was never the problem -- the criterion routes AUDIO on its
    text alone. It was the target-aware pass that overruled it.
    """
    assert classify_criterion(criterion).modality is Modality.AUDIO

    decision = resolve_runtime_routing(
        criterion,
        [reel.name],
        selected_paths_have_audio=has_audio_content(reel),
    )
    assert decision.modality is Modality.AUDIO, (
        "a criterion about sound was routed away from the listening model "
        "and will be scored by a judge that cannot hear it"
    )


@pytest.mark.parametrize("criterion", CRITERIA_THAT_WERE_SCORED_DEAF)
def test_a_listening_criterion_on_a_silent_reel_is_still_demoted(
    silent_reel, criterion
):
    """The saving that justifies the rule, preserved."""
    decision = resolve_runtime_routing(
        criterion,
        [silent_reel.name],
        selected_paths_have_audio=has_audio_content(silent_reel),
    )
    assert decision.modality is Modality.TEXT


def test_a_mix_criterion_against_a_spreadsheet_is_still_demoted(tmp_path):
    """Non-regression on the case the rule was written for."""
    sheet = tmp_path / "budget.xlsx"
    sheet.write_bytes(b"\x00" * 32)
    decision = resolve_runtime_routing(
        "A music track is present in the mix.",
        [sheet.name],
        selected_paths_have_audio=has_audio_content(sheet),
    )
    assert has_audio_content(sheet) is False
    assert decision.modality is Modality.TEXT


def test_an_audio_file_is_unchanged(tmp_path):
    """Non-regression: the plain case the probe always got right."""
    track = tmp_path / "sfx.mp3"
    track.write_bytes(b"\x00" * 32)
    assert has_audio_content(track) is True
