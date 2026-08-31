"""A criterion failed on a number the file states plainly and was not asked for.

The paid smoke on run ``33363059548`` graded gold task ``75401f7c`` and marked
this item **fail**::

    criterion:  The audio sample rate is 44.1 kHz or 48 kHz.
    evidence:   "audio_tracks": 1, "video_tracks": 1
    routing:    audio          perception_called: False

The routing was right and the listening path was unavailable, so the judge fell
back to the container probe -- and the container probe, on a ``.mp4``, answers
with two track counts and nothing else. The rate is in the file. ``ffprobe``
prints it. ``_probe_audio_impl`` returns it. ``_probe_video_impl`` simply never
looked, and the judge, holding a count of streams, marked a deliverable as
failing to meet a specification it very possibly met.

This is the same defect PR #276 fixed one field over. There, ``"audio_tracks":
1`` was the evidence for "there is no audio here"; the count was on screen and
unusable. Here the count is on screen and the *rate* is missing. Fixing the
routing while leaving this would have moved the bug into the next field
rather than removing it, which is why the two travel together.

Two properties are load-bearing and both are pinned below.

**The vocabulary is shared.** ``sample_rate``, ``channels`` and ``codec`` mean
the same thing and are spelled the same way whether the sound arrived in a
``.wav`` or inside an ``.mp4``. A judge writing evidence should not have to
know which container it was handed.

**Absence stays absent.** A silent video reports ``None``, not zeros. ``0`` is
a measurement; a rate of zero is not a fact about any file. The distinction is
the one ``305`` keeps making -- where the grader cannot look it excludes the
item rather than scoring it -- and a probe that invents a number takes that
choice away from every reader downstream.

Real MP4s, encoded with PyAV. Nothing here calls a model or a network.

Spec: tasks/rebuilding_grading_task/307-audio-smoke-result.md
"""

from __future__ import annotations

import sys
import wave
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.tools.read_deliverable import (  # noqa: E402
    _audio_stream_summary,
    _probe_audio_impl,
    _probe_video_impl,
    read_deliverable,
)

av = pytest.importorskip("av", reason="PyAV is what the probes use")
np = pytest.importorskip("numpy")


#: Copied verbatim from the graded output of gold task 75401f7c, where it was
#: scored fail on evidence that did not mention a sample rate.
CRITERION_THAT_FAILED_ON_A_STATED_FACT = (
    "The audio sample rate is 44.1 kHz or 48 kHz."
)

#: The evidence string the judge was given for it, also verbatim.
EVIDENCE_IT_WAS_GIVEN = '"audio_tracks": 1, "video_tracks": 1'


def _encode_mp4(path: Path, *, audio: bool, rate: int = 44100) -> Path:
    """A genuine, tiny MP4. Streams are declared before anything is muxed."""
    container = av.open(str(path), mode="w")
    try:
        video_stream = container.add_stream("mpeg4", rate=5)
        video_stream.width = video_stream.height = 32
        video_stream.pix_fmt = "yuv420p"
        audio_stream = container.add_stream("aac", rate=rate) if audio else None

        for _ in range(3):
            container.mux(video_stream.encode(av.VideoFrame(32, 32, "yuv420p")))
        for packet in video_stream.encode(None):
            container.mux(packet)
        if audio_stream is not None:
            frame = av.AudioFrame.from_ndarray(
                np.zeros((1, 1024), dtype="int16"), format="s16", layout="mono"
            )
            frame.sample_rate = rate
            for packet in audio_stream.encode(frame):
                container.mux(packet)
            for packet in audio_stream.encode(None):
                container.mux(packet)
    finally:
        container.close()
    return path


@pytest.fixture(scope="module")
def reel(tmp_path_factory) -> Path:
    """A 44.1 kHz soundtrack in an MP4, like the deliverable that failed."""
    return _encode_mp4(tmp_path_factory.mktemp("av") / "reel.mp4", audio=True)


@pytest.fixture(scope="module")
def silent_reel(tmp_path_factory) -> Path:
    return _encode_mp4(tmp_path_factory.mktemp("av") / "silent.mp4", audio=False)


# ── the criterion, answerable ────────────────────────────────────────


def test_the_probe_now_answers_the_question_that_was_asked(reel):
    """The whole defect in one assertion.

    44100 is what the encoder wrote and what ``ffprobe`` reads back. Before
    this, the judge was handed a stream count and asked whether the rate was
    44.1 or 48 kHz.
    """
    info = _probe_video_impl(reel)

    assert info["audio"] is not None, (
        "a container with a soundtrack must describe it; the criterion "
        f"{CRITERION_THAT_FAILED_ON_A_STATED_FACT!r} was scored fail against "
        f"the evidence {EVIDENCE_IT_WAS_GIVEN!r}, which cannot answer it"
    )
    assert info["audio"]["sample_rate"] == 44100


def test_the_answer_survives_the_public_entrypoint(reel, tmp_path):
    """What the judge actually calls, not the helper underneath it.

    The tool dispatches through ``read_deliverable``, and a field that exists
    in ``_probe_video_impl`` but is dropped on the way out would leave the
    evidence exactly as unhelpful as it was.
    """
    staged = tmp_path / reel.name
    staged.write_bytes(reel.read_bytes())

    result = read_deliverable("probe_video", staged.name, base_dir=str(tmp_path))

    payload = result.get("data", result)
    assert payload["kind"] == "video"
    assert payload["audio"]["sample_rate"] == 44100


def test_a_forty_eight_kilohertz_reel_is_not_reported_as_forty_four(tmp_path):
    """The probe reads the file rather than repeating a default.

    Both rates satisfy the criterion, so a hard-coded 44100 would have passed
    the test above while telling every reader the same thing about every file.
    """
    reel_48 = _encode_mp4(tmp_path / "broadcast.mp4", audio=True, rate=48000)

    assert _probe_video_impl(reel_48)["audio"]["sample_rate"] == 48000


# ── absence stays absent ─────────────────────────────────────────────


def test_a_silent_video_reports_nothing_rather_than_zero(silent_reel):
    """``None`` is "there is no audio stream"; ``0`` would be a measurement.

    A rate of zero is not a fact about any file, and a criterion about sound
    marked against one would be failed on a number the probe made up.
    """
    info = _probe_video_impl(silent_reel)

    assert info["audio"] is None
    assert info["audio_tracks"] == 0


def test_the_track_counts_are_still_there(reel, silent_reel):
    """Negative control: the summary is additive.

    ``audio_tracks`` and ``video_tracks`` are what the routing probe and the
    existing evidence strings are written against. A change that replaced them
    would fix this criterion by breaking the one PR #276 fixed.
    """
    with_sound = _probe_video_impl(reel)
    without = _probe_video_impl(silent_reel)

    assert (with_sound["audio_tracks"], with_sound["video_tracks"]) == (1, 1)
    assert (without["audio_tracks"], without["video_tracks"]) == (0, 1)
    for key in ("backend", "codec", "width", "height", "fps", "duration_s"):
        assert key in with_sound, f"{key} disappeared from the video probe"


# ── one vocabulary, two containers ───────────────────────────────────


def test_the_field_names_match_the_audio_probe(reel, tmp_path):
    """The same three questions, spelled the same way, either way in.

    A judge asked "what is the sample rate" should not need to know whether
    the sound arrived as a ``.wav`` or inside an ``.mp4``. Two spellings for
    one fact is how a criterion ends up unanswerable in one container and
    routine in the other.
    """
    clip = tmp_path / "stem.wav"
    with wave.open(str(clip), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(44100)
        w.writeframes(b"\x00\x00" * 4410)

    from_audio_file = _probe_audio_impl(clip, basic=True)
    from_video_file = _probe_video_impl(reel)["audio"]

    assert set(from_video_file) <= set(from_audio_file), (
        f"the video probe describes audio with {sorted(from_video_file)}, "
        f"which the audio probe does not recognise as "
        f"{sorted(from_audio_file)}"
    )
    for field in ("sample_rate", "channels", "codec"):
        assert from_audio_file[field] is not None
        assert from_video_file[field] is not None
    assert from_audio_file["sample_rate"] == from_video_file["sample_rate"]


# ── a container that will not describe itself ────────────────────────


class _Streams:
    def __init__(self, audio):
        self._audio = audio

    @property
    def audio(self):
        if isinstance(self._audio, Exception):
            raise self._audio
        return self._audio


class _Container:
    def __init__(self, audio):
        self.streams = _Streams(audio)


class _Stream:
    """A stream that answers some questions and raises on others."""

    def __init__(self, **answers):
        self._answers = answers

    def __getattr__(self, name):
        if name not in self._answers:
            raise AttributeError(name)
        value = self._answers[name]
        if isinstance(value, Exception):
            raise value
        return value


def test_a_container_that_refuses_to_list_its_streams_is_not_an_error():
    """A probe that raises would cost the whole video its evidence.

    The other fields -- resolution, duration, codec -- are still worth having
    for a file whose audio metadata is unreadable, so an unreadable summary is
    ``None`` and the probe returns.
    """
    assert _audio_stream_summary(_Container(RuntimeError("closed"))) is None


def test_one_unreadable_field_does_not_discard_the_readable_ones():
    """Each read is guarded on its own.

    A container can state its rate and decline to describe its channel
    layout. Collapsing to ``None`` on the first missing attribute would put
    back the silence this replaced, for a file that was answering.
    """
    stream = _Stream(
        sample_rate=48000,
        channels=ValueError("no layout"),
        codec=None,
    )

    summary = _audio_stream_summary(_Container([stream]))

    assert summary == {"sample_rate": 48000, "channels": None, "codec": None}


def test_an_empty_stream_list_is_none_not_a_dict_of_nones():
    """"No audio" and "audio I could not measure" must stay distinguishable.

    A dict of ``None`` values would read, downstream, as a stream that exists
    and would not describe itself -- which is a different finding and would
    keep a listening criterion routed at a file that has nothing to listen to.
    """
    assert _audio_stream_summary(_Container([])) is None
