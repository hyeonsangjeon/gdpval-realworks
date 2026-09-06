"""A criterion about 1:22 must not be failed from a clip that ends at 0:30.

Every audio call used to carry the first ``AUDIO_TRIM_SECONDS`` of the
deliverable and a system prompt saying so. On the 185-task gold run that cost
task ``38889c3b`` six points across three items, each asking about a region
the clip could not reach:

    "During 1:22-1:49 (+/- 10 s) of the Master track (the bridge), ..."
        -> 0/2 fail
    "From 1:49 (+/- 2 s) to the end of the Master track, the harmonies ..."
        -> 0/2 fail, evidence: "The clip only includes the first 30s,
           ending well before 1:49."
    "From the beginning of the Master track through 1:22 (+/- 10 s), ..."
        -> 0/2 fail

The second one is the whole bug written out by the model itself: it listened,
it reported honestly what the clip contained, and the harness recorded the
result as a property of the deliverable. These tests pin the two halves of the
fix -- the window follows the question, and whatever window is sent is what
the sub-judge is told it is hearing.

The three strings below are quoted from the graded run rather than invented,
because the parser is only worth anything against the sentences rubrics
actually use.
"""

from __future__ import annotations

import pytest

from core.perception.audio import (
    AUDIO_TRIM_SECONDS,
    AudioWindowUnavailable,
    _audio_prompt_header,
    _AUDIO_REGION_ABSENT_NOTE,
    _AUDIO_WINDOW_UNCUT_NOTE,
    criterion_listen_start,
)


# The criteria as graded, truncated only where the tail carries no timestamp.
BRIDGE = (
    "During 1:22-1:49 (+/- 10 s) of the Master track (the bridge), the "
    "arrangement thins to synths and drums."
)
OUTRO = (
    "From 1:49 (+/- 2 s) to the end of the Master track, the harmonies "
    "stack into a three-part chord."
)
THROUGH = (
    "From the beginning of the Master track through 1:22 (+/- 10 s), the "
    "key stays in D major."
)


# --------------------------------------------------------------------------
# The window follows the question
# --------------------------------------------------------------------------

def test_a_region_after_the_head_slice_moves_the_window():
    """1:22 with a 10s tolerance opens the clip at 1:12, not at 0:00."""
    assert criterion_listen_start(BRIDGE) == pytest.approx(72.0)


def test_the_stated_tolerance_is_read_rather_than_guessed():
    """1:49 +/- 2 s opens at 1:47. The number comes from the criterion."""
    assert criterion_listen_start(OUTRO) == pytest.approx(107.0)


def test_a_criterion_anchored_at_the_beginning_keeps_the_head():
    """"From the beginning ... through 1:22" wants 0:00, and names 1:22.

    Seeking to 1:22 here would take a clip that overlaps the question and
    replace it with one that does not -- a regression dressed as a fix.
    """
    assert criterion_listen_start(THROUGH) is None


def test_a_criterion_naming_no_time_keeps_the_head():
    assert criterion_listen_start(
        "The mix is free of clipping and the vocal sits above the drums."
    ) is None


def test_a_timestamp_inside_the_head_slice_keeps_the_head():
    """0:12 is already in the clip, so nothing moves and nothing is re-sent."""
    assert criterion_listen_start("At 0:12 the hi-hat enters.") is None


def test_the_boundary_belongs_to_the_head():
    """A window opening exactly at the end of the head slice is not a gap."""
    assert criterion_listen_start(
        f"At 0:{AUDIO_TRIM_SECONDS} the hi-hat enters."
    ) is None


def test_the_earliest_named_region_is_the_one_opened_on():
    """A span is entered at its start, not at its end."""
    assert criterion_listen_start(
        "Between 2:10 and 3:40 the bass drops out."
    ) == pytest.approx(130.0)


def test_a_longer_head_slice_swallows_a_later_timestamp():
    """The trigger is the clip we would otherwise send, not a fixed 30s."""
    assert criterion_listen_start(BRIDGE, trim_seconds=180) is None


@pytest.mark.parametrize("text", [
    "The team meets at 9:00 AM to review the mix.",
    "The meeting at 10:30 a.m. covers the vocal takes.",
    "Compression is applied at a 4:1 ratio on the bus.",
])
def test_things_that_look_like_timestamps_and_are_not(text):
    """A clock time and a ratio must not move the clip.

    A ratio cannot match at all -- the pattern needs two digits after the
    colon. A clock time is turned away by its own suffix.
    """
    assert criterion_listen_start(text) is None


def test_a_bare_clock_range_is_read_as_a_timestamp_and_that_is_contained():
    """The limit of this parser, pinned rather than papered over.

    "12:00-13:00" with no am/pm is a diary entry to a person and a timestamp
    to the pattern, and nothing in the criterion text can tell them apart --
    a 12-minute mark is perfectly ordinary in a recording. So it is read as a
    timestamp, and the *file* settles it: a deliverable that ends before 12:00
    raises :class:`AudioWindowUnavailable` with ``region_absent``, the head
    slice is sent as it always was, and the note appended to the prompt says
    only that the criterion names a point past the end of the deliverable --
    which is true of a diary entry too. The cost of being wrong here is one
    sentence of context, not a verdict.
    """
    assert criterion_listen_start(
        "The session ran 12:00-13:00 in the studio diary."
    ) == pytest.approx(720.0)


def test_an_empty_criterion_is_not_an_error():
    assert criterion_listen_start("") is None
    assert criterion_listen_start(None) is None  # type: ignore[arg-type]


# --------------------------------------------------------------------------
# Whatever is sent is what the sub-judge is told it is hearing
# --------------------------------------------------------------------------

def test_the_head_slice_still_says_head_only():
    header = _audio_prompt_header(start_seconds=0.0, trim_seconds=30)
    assert "head-only slice (first 30s)" in header


def test_a_moved_window_states_its_real_span():
    """The old prompt said "first 30s" of everything. That is the lie."""
    header = _audio_prompt_header(start_seconds=72.0, trim_seconds=30)
    assert "from 1:12 to 1:42" in header
    assert "head-only" not in header


def test_the_prompt_stops_hardcoding_thirty_seconds():
    """``trim_seconds`` is settings-overridable, so the sentence must move."""
    header = _audio_prompt_header(start_seconds=0.0, trim_seconds=90)
    assert "first 90s" in header
    assert "30s" not in header


def _header_without_the_shared_contract(**kwargs) -> str:
    """The header with the response contract stripped off the end.

    Every header now ends with ``AUDIO_RESPONSE_CONTRACT``, which names the
    whole verdict vocabulary -- ``judge_error`` included, because the parser
    accepts it and a vocabulary that omitted a legal value is the drift this
    contract exists to stop.

    That makes a bare ``"judge_error" in header`` true for every case and false
    for none, which would quietly retire the distinction the next two tests are
    here to hold: whether *this particular note* tells the sub-judge to answer
    ``judge_error``. So the shared part is removed and the per-case part is
    what gets asserted on.
    """
    from core.perception.audio import AUDIO_RESPONSE_CONTRACT

    header = _audio_prompt_header(**kwargs)
    assert header.endswith(AUDIO_RESPONSE_CONTRACT), (
        "the shared contract is no longer the tail of the header, so these "
        "tests are asserting on the wrong slice"
    )
    return header[: -len(AUDIO_RESPONSE_CONTRACT)]


def test_an_uncut_window_forbids_reading_silence_as_absence():
    """Not having listened is not having heard nothing."""
    note = _header_without_the_shared_contract(
        start_seconds=0.0, trim_seconds=30,
        window_note=_AUDIO_WINDOW_UNCUT_NOTE,
    )
    assert "judge_error" in note
    assert "have NOT observed it" in note


def test_a_deliverable_that_ends_early_is_still_gradeable():
    """A track that stops at 0:30 really does lack the bridge at 1:22.

    That is a fact about the work under test, so the note says so and leaves
    the verdict alone -- no ``judge_error`` instruction, unlike the case
    above where the failure is ours.

    The shared contract still *names* ``judge_error`` here, as it does on
    every call. Naming a legal value is not instructing its use, and the model
    has to know the value exists: the alternative is what run 34008840627
    measured, where a sub-judge with no word for "I could not tell" answered
    ``refuse`` and had it scored against the deliverable.
    """
    note = _header_without_the_shared_contract(
        start_seconds=0.0, trim_seconds=30,
        window_note=_AUDIO_REGION_ABSENT_NOTE,
    )
    assert "beyond the end of this deliverable" in note
    assert "judge_error" not in note


# --------------------------------------------------------------------------
# The main judge has to hand over the words the window is read from
# --------------------------------------------------------------------------

def _audio_tool_schema():
    from core.tool_calling_judge import ToolCallingJudge

    return ToolCallingJudge._audio_tool_schema()


def test_the_tool_stops_promising_the_head_of_the_file():
    """The description the main judge reads was "the head-30s slice"."""
    description = _audio_tool_schema()["description"]
    assert "head-30s" not in description
    assert "criterion" in description


def test_the_main_judge_is_asked_to_keep_the_timestamps():
    """Without this the fix cannot fire on a real run, only in tests.

    ``audio_judge`` grades whatever criterion string the main judge chooses to
    pass, and nothing obliged that string to be the rubric's. A summary --
    "check the bridge thins to synths" -- carries no time, so the window stays
    at the head and the item fails exactly as it did before. The parser reads
    the criterion, so the criterion has to arrive intact.
    """
    criterion = _audio_tool_schema()["parameters"]["properties"]["criterion"]
    assert "verbatim" in criterion.get("description", "")
    # Named, so that the instruction is about the thing that matters rather
    # than a general plea for fidelity.
    assert "timestamps" in criterion["description"]


# --------------------------------------------------------------------------
# The two failures are told apart, because they deserve opposite verdicts
# --------------------------------------------------------------------------

def test_a_missing_region_and_a_missing_decoder_are_different():
    absent = AudioWindowUnavailable("ends first", region_absent=True)
    undecodable = AudioWindowUnavailable("no decoder")
    assert absent.region_absent is True
    assert undecodable.region_absent is False


def test_a_window_past_the_end_of_the_file_is_refused_not_faked(tmp_path):
    """The head slice must never be handed back as if it were the segment."""
    av = pytest.importorskip("av")
    src = tmp_path / "short.wav"
    _write_silence(av, str(src), seconds=2)

    from core.perception.audio import _trim_audio_bytes

    with pytest.raises(AudioWindowUnavailable) as caught:
        _trim_audio_bytes(str(src), 30, 120.0)
    assert caught.value.region_absent is True


def test_a_window_inside_the_file_is_cut_and_is_not_the_head(tmp_path):
    av = pytest.importorskip("av")
    src = tmp_path / "tone.wav"
    _write_silence(av, str(src), seconds=8)

    from core.perception.audio import _trim_audio_bytes

    head, fmt_head = _trim_audio_bytes(str(src), 2, 0.0)
    later, fmt_later = _trim_audio_bytes(str(src), 2, 4.0)
    assert fmt_head == fmt_later == "wav"
    # Both are two seconds of the same file, so size alone proves nothing.
    # What proves the seek is that asking past the end of an 8s file fails
    # while asking at 4s does not.
    assert len(later) > 0
    with pytest.raises(AudioWindowUnavailable):
        _trim_audio_bytes(str(src), 2, 30.0)


def test_the_default_call_is_byte_for_byte_what_it_always_was(tmp_path):
    """``start_seconds=0`` must not be a new code path with a new result."""
    av = pytest.importorskip("av")
    src = tmp_path / "tone.wav"
    _write_silence(av, str(src), seconds=4)

    from core.perception.audio import _trim_audio_bytes

    assert _trim_audio_bytes(str(src), 2) == _trim_audio_bytes(str(src), 2, 0.0)


def _fake_av(frames):
    """An ``av`` module complete enough to reach the end-of-window check.

    Deliberately not a stub that throws: a fake that blows up early lands in
    the generic decode-failure branch, which reports ``region_absent=False``
    for its own reasons and would let this test pass no matter what the check
    under test decides. It has to survive as far as the loop.
    """
    import fractions

    class _OutStream:
        layout = None

        def encode(self, *_a):
            return []

    class _Out:
        def add_stream(self, *_a, **_k):
            return _OutStream()

        def mux(self, _packet):
            pass

        def close(self):
            pass

    class _Streams:
        audio = [object()]

    class _Container:
        duration = None
        streams = _Streams()

        def decode(self, **_kwargs):
            return iter(frames)

        def close(self):
            pass

    class _Resampler:
        def resample(self, _frame):
            return []

    def _open(_target, mode="r", **_kwargs):
        return _Out() if mode == "w" else _Container()

    return type("_AV", (), {
        "open": staticmethod(_open),
        "AudioResampler": staticmethod(lambda **_k: _Resampler()),
        "time_base": fractions.Fraction(1, 1),
    })


def _frame(seconds):
    """A decoded frame reporting ``seconds``, or nothing at all if ``None``."""
    import fractions

    return type("_Frame", (), {
        "pts": None if seconds is None else seconds,
        "time_base": fractions.Fraction(1, 1),
    })()


@pytest.mark.parametrize("frames, blames_the_deliverable, why", [
    (
        [_frame(1), _frame(2)],
        True,
        "timestamps advanced and ran out before the window: the deliverable "
        "really is shorter than the criterion assumes",
    ),
    (
        [_frame(None), _frame(None)],
        False,
        "no frame ever reported a time, so nothing here is evidence about "
        "how long the deliverable is",
    ),
])
def test_only_a_real_clock_may_blame_the_deliverable(
    tmp_path, frames, blames_the_deliverable, why
):
    """``region_absent`` decides which sentence reaches the sub-judge.

    One of the two says the deliverable stops early -- a claim about the work
    under test, which is exactly the kind of claim this whole change exists to
    stop the harness making without evidence.
    """
    import sys

    from core.perception.audio import _trim_audio_bytes

    src = tmp_path / "clip.wav"
    src.write_bytes(b"RIFF----WAVEfmt ")

    monkey = pytest.MonkeyPatch()
    monkey.setitem(sys.modules, "av", _fake_av(frames))
    try:
        with pytest.raises(AudioWindowUnavailable) as caught:
            _trim_audio_bytes(str(src), 30, 120.0)
    finally:
        monkey.undo()
    assert caught.value.region_absent is blames_the_deliverable, why


def _write_silence(av, path: str, *, seconds: int) -> None:
    """A mono 16 kHz WAV of ``seconds`` length, written with PyAV."""
    import numpy as np

    rate = 16_000
    out = av.open(path, mode="w", format="wav")
    stream = out.add_stream("pcm_s16le", rate=rate)
    stream.layout = "mono"
    samples = np.zeros((1, rate), dtype="int16")
    for index in range(seconds):
        frame = av.AudioFrame.from_ndarray(samples, format="s16", layout="mono")
        frame.sample_rate = rate
        frame.pts = index * rate
        frame.time_base = __import__("fractions").Fraction(1, rate)
        for packet in stream.encode(frame):
            out.mux(packet)
    for packet in stream.encode():
        out.mux(packet)
    out.close()
