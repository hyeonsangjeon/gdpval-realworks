"""The accuracy probe has to know its own answers before it can grade anyone.

``measure_audio_grading_accuracy.py`` exists to say whether the audio
sub-judge is *right*. That claim rests entirely on the probe's ground truth
being right, and a ground truth written in a docstring is not evidence -- it
is a second opinion from the same author.

So this file does not read the corpus's claims about itself. It renders every
clip to bytes, **decodes those bytes back**, and measures the waveform:
where the energy is, how many bursts there are, how far apart they fall, and
which way the pitch moves. If ``three_beeps`` says three and the decoded audio
has four, this fails. The probe and the description of the probe are checked
against each other, off the same samples the model will hear.

The other half is the scorer. A measurement instrument that reports a good
number when handed garbage is worse than no instrument, so the negative
controls here are as load-bearing as the positive ones: a model that answers
``pass`` to every criterion scores 50% accuracy on this balanced corpus, and
the test that matters is the one asserting its discrimination is **zero**.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import wave
from pathlib import Path
from typing import Sequence

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.perception.audio import (  # noqa: E402
    AUDIO_CALL_CAP,
    AUDIO_SAMPLE_RATE_HZ,
    AUDIO_TRIM_SECONDS,
    SUPPORTED_AUDIO_FORMATS,
    AudioPerception,
    criterion_listen_start,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import measure_audio_grading_accuracy as probe  # noqa: E402


# --------------------------------------------------------------------------
# Decoding the rendered bytes back
# --------------------------------------------------------------------------


def decode(clip: probe.Clip, tmp_path: Path) -> tuple[list[float], int]:
    """Render a clip to a real file and read the samples back out of it.

    Deliberately round-tripped through ``wave`` rather than taken from
    :func:`probe.clip_samples`, so a bug in the packing, the scaling or the
    header is caught here instead of being shared by the renderer and its own
    test.
    """
    path = tmp_path / f"{clip.clip_id}.wav"
    probe.render_clip(clip, path)
    with wave.open(str(path), "rb") as handle:
        assert handle.getnchannels() == 1
        assert handle.getsampwidth() == 2
        rate = handle.getframerate()
        frames = handle.readframes(handle.getnframes())
    count = len(frames) // 2
    values = struct.unpack(f"<{count}h", frames)
    return [value / 32768.0 for value in values], rate


def rms_windows(
    samples: Sequence[float], rate: int, window_s: float = 0.01
) -> list[tuple[float, float]]:
    """``(window_start_seconds, rms)`` over non-overlapping windows."""
    size = max(1, int(round(window_s * rate)))
    out: list[tuple[float, float]] = []
    for start in range(0, len(samples) - size + 1, size):
        chunk = samples[start : start + size]
        energy = math.sqrt(sum(value * value for value in chunk) / len(chunk))
        out.append((start / rate, energy))
    return out


def loud_runs(
    samples: Sequence[float], rate: int, threshold: float = 0.05
) -> list[tuple[float, float]]:
    """Contiguous stretches of audible energy, as ``(start_s, end_s)``.

    This is what "how many beeps" means when you are not allowed to look at
    the segment list.
    """
    runs: list[tuple[float, float]] = []
    open_at: float | None = None
    last: float = 0.0
    for start, energy in rms_windows(samples, rate):
        if energy > threshold:
            if open_at is None:
                open_at = start
            last = start
        elif open_at is not None:
            runs.append((open_at, last + 0.01))
            open_at = None
    if open_at is not None:
        runs.append((open_at, last + 0.01))
    return runs


def zero_crossing_hz(samples: Sequence[float], rate: int) -> float:
    """Rough fundamental frequency, from sign changes.

    Two sign changes per cycle, so crossings per second over two. Crude, and
    entirely sufficient to tell 220 Hz from 880 Hz.
    """
    crossings = sum(
        1
        for first, second in zip(samples, samples[1:])
        if (first < 0) != (second < 0)
    )
    return crossings / (len(samples) / rate) / 2.0


def magnitude_at(samples: Sequence[float], rate: int, frequency_hz: float) -> float:
    """Amplitude of one frequency component, by quadrature correlation.

    :func:`zero_crossing_hz` answers "what note is this" and is enough for a
    beep, but it is meaningless the moment two notes sound at once: a triad
    crosses zero at a rate that is not any of its three pitches, and a bass
    note carrying five overtones crosses far more often than its fundamental.
    Every musical claim in this corpus is about *simultaneous* content, so the
    measurement has to be per-frequency.

    This correlates the signal against a sine and a cosine at the frequency
    asked about and takes the magnitude, which is one bin of a DFT evaluated
    where it is wanted rather than on a grid. For a pure tone of amplitude A
    at exactly this frequency it returns A; for a frequency that is not in the
    signal it returns leakage, which over these window lengths is two orders
    of magnitude smaller. Standard library only, and no third bin is computed
    that nothing asks for.

    Absence is the harder half of every claim here -- the false criteria are
    what the model must *not* confirm -- so a helper that could only find
    things would leave each pair half-checked.
    """
    if not samples:  # pragma: no cover - a window that decoded to nothing
        return 0.0
    step = 2.0 * math.pi * frequency_hz / rate
    real = sum(value * math.cos(step * index) for index, value in enumerate(samples))
    imag = sum(value * math.sin(step * index) for index, value in enumerate(samples))
    return 2.0 * math.sqrt(real * real + imag * imag) / len(samples)


def window(
    samples: Sequence[float], rate: int, start_s: float, end_s: float
) -> list[float]:
    """The samples between two times, so a claim is measured where it applies."""
    return list(samples[int(start_s * rate) : int(end_s * rate)])


# --------------------------------------------------------------------------
# The clips really contain what the corpus says they contain
# --------------------------------------------------------------------------


def test_clips_render_at_the_rate_the_grader_resamples_to() -> None:
    """The model hears these samples, not a resampled approximation of them.

    If the clips were written at 44.1 kHz the grader would downsample them on
    the way out, and every measurement here would be of a waveform this file
    never inspected.
    """
    assert probe.CLIP_SAMPLE_RATE_HZ == AUDIO_SAMPLE_RATE_HZ


def test_wav_is_a_format_the_audio_path_accepts() -> None:
    """Otherwise every call is refused before it is made and nothing is measured."""
    assert "wav" in SUPPORTED_AUDIO_FORMATS


def test_rendered_file_round_trips_at_the_declared_rate(tmp_path: Path) -> None:
    for clip in probe.CLIPS:
        samples, rate = decode(clip, tmp_path)
        assert rate == probe.CLIP_SAMPLE_RATE_HZ, clip.clip_id
        expected = int(round(clip.duration_s * rate))
        assert abs(len(samples) - expected) <= 1, clip.clip_id


def test_tone_stops_early_really_stops_early(tmp_path: Path) -> None:
    """The timing family's true claim, checked against the waveform.

    This is the shape of the contradiction the card opens with -- one verdict
    saying the music ends exactly at 30 s, another saying there is no music at
    all, both at high confidence. Here the answer is not in dispute.
    """
    clip = probe.CLIPS_BY_ID["tone_stops_early"]
    samples, rate = decode(clip, tmp_path)
    runs = loud_runs(samples, rate)
    assert len(runs) == 1
    start, end = runs[0]
    assert start < 0.05
    assert 1.9 < end < 2.1
    # And the tail is genuinely silent, not merely quieter.
    tail = samples[int(2.2 * rate) :]
    assert max(abs(value) for value in tail) == 0.0


def test_pure_silence_is_digitally_silent(tmp_path: Path) -> None:
    """Not "quiet". Every sample exactly zero, so no encoder can disagree."""
    clip = probe.CLIPS_BY_ID["pure_silence"]
    samples, _ = decode(clip, tmp_path)
    assert samples
    assert max(abs(value) for value in samples) == 0.0


def test_three_beeps_has_exactly_three_beeps(tmp_path: Path) -> None:
    clip = probe.CLIPS_BY_ID["three_beeps"]
    samples, rate = decode(clip, tmp_path)
    runs = loud_runs(samples, rate)
    assert len(runs) == 3, runs
    for (start, end), expected in zip(runs, (0.5, 2.0, 3.5)):
        assert abs(start - expected) < 0.05
        assert 0.10 < end - start < 0.20


def test_clicks_are_at_120_bpm_and_not_60_or_132(tmp_path: Path) -> None:
    """Both tempo families depend on this one measurement.

    ``tempo_coarse`` asks 120-vs-60, which is a factor of two. ``tempo_fine``
    asks 120-vs-132 at +/-1 BPM, which is the resolution the gold run's
    "140 BPM" criterion needed and got a 70-token answer for. The interval has
    to be tight enough that the fine claim is genuinely decidable from the
    audio -- otherwise a false-fail there would be the probe's fault, not the
    model's.
    """
    clip = probe.CLIPS_BY_ID["clicks_120bpm"]
    samples, rate = decode(clip, tmp_path)
    runs = loud_runs(samples, rate)
    assert len(runs) == 16, len(runs)
    gaps = [b[0] - a[0] for a, b in zip(runs, runs[1:])]
    assert gaps
    for gap in gaps:
        assert abs(gap - 0.5) < 0.02, gaps
    bpm = 60.0 / (sum(gaps) / len(gaps))
    assert abs(bpm - 120.0) < 1.0
    assert abs(bpm - 60.0) > 1.0
    assert abs(bpm - 132.0) > 1.0


def test_low_then_high_goes_low_then_high(tmp_path: Path) -> None:
    clip = probe.CLIPS_BY_ID["low_then_high"]
    samples, rate = decode(clip, tmp_path)
    first = zero_crossing_hz(samples[int(0.2 * rate) : int(1.8 * rate)], rate)
    second = zero_crossing_hz(samples[int(3.2 * rate) : int(4.8 * rate)], rate)
    assert abs(first - 220.0) < 10.0, first
    assert abs(second - 880.0) < 20.0, second
    assert second > first * 3


# --------------------------------------------------------------------------
# The musical clips, where the ground truth is a frequency rather than a count
# --------------------------------------------------------------------------


def test_the_scale_really_is_g_major_and_really_is_not_e_flat(
    tmp_path: Path,
) -> None:
    """``key``: eight notes, and the one note that settles the question.

    G major and E-flat major share nothing useful to argue over; what decides
    it in one note is F-sharp, which G major has and E-flat major does not.
    So the assertion is not "the melody sounds like G major" -- that is taste
    -- but that 739.99 Hz is in the waveform and 698.46 Hz is not, measured in
    the window where the seventh note sounds.

    The peak is also located rather than merely detected: of the three
    candidate semitones around it, F-sharp is the loudest by a wide margin. A
    threshold alone could be met by spectral leakage from a neighbour; a peak
    cannot.
    """
    clip = probe.CLIPS_BY_ID["g_major_scale"]
    samples, rate = decode(clip, tmp_path)

    runs = loud_runs(samples, rate)
    assert len(runs) == 8, runs
    for index, (start, end) in enumerate(runs):
        assert abs(start - index * 0.4) < 0.05, runs
        assert 0.30 < end - start < 0.40, runs

    # The seventh note, index 6, sounds from 2.4 s to 2.75 s.
    seventh = window(samples, rate, 2.45, 2.70)
    f_sharp = magnitude_at(seventh, rate, probe.hz("Fs5"))
    f_natural = magnitude_at(seventh, rate, probe.hz("F5"))
    assert f_sharp > 0.4, f_sharp
    assert f_natural < 0.05, f_natural
    assert f_sharp > f_natural * 8
    assert f_sharp > magnitude_at(seventh, rate, probe.hz("G5"))

    # Every scale degree, in the window where it sounds, at full amplitude.
    for index, name in enumerate(("G4", "A4", "B4", "C5", "D5", "E5", "Fs5", "G5")):
        note = window(samples, rate, index * 0.4 + 0.05, index * 0.4 + 0.30)
        assert magnitude_at(note, rate, probe.hz(name)) > 0.4, name


def test_the_triad_is_three_notes_at_once_and_the_third_is_major(
    tmp_path: Path,
) -> None:
    """``triad``: major against minor is B4 against B-flat4, and it is measurable.

    This is the claim that could not be posed at all before -- a chord needs
    simultaneous frequencies, and every earlier clip was one voice at a time.
    The false criterion says the chord is minor, so the test has to show both
    that the major third is present and that the minor third is absent;
    showing only the first would leave the model free to be right by accident.

    The three voices are also checked to be equal and simultaneous. A chord
    whose fifth was twice as loud as its third, or which arpeggiated instead
    of sustaining, would be a different musical claim than the criterion makes.
    """
    clip = probe.CLIPS_BY_ID["major_triad"]
    samples, rate = decode(clip, tmp_path)
    body = window(samples, rate, 0.3, 2.7)

    root = magnitude_at(body, rate, probe.hz("G4"))
    third = magnitude_at(body, rate, probe.hz("B4"))
    fifth = magnitude_at(body, rate, probe.hz("D5"))
    minor_third = magnitude_at(body, rate, probe.hz("Bb4"))

    for name, value in (("G4", root), ("B4", third), ("D5", fifth)):
        assert value > 0.15, (name, value)
    assert minor_third < 0.02, minor_third
    assert third > minor_third * 10

    # Equal voices: normalisation divides by the weight total, so no one note
    # dominates and the chord is a chord rather than a note with two ghosts.
    assert max(root, third, fifth) - min(root, third, fifth) < 0.02

    # Sustained, not arpeggiated: all three are present in the first tenth of
    # the chord and in the last tenth of it.
    for start, end in ((0.3, 0.55), (2.45, 2.7)):
        slice_ = window(samples, rate, start, end)
        for name in ("G4", "B4", "D5"):
            assert magnitude_at(slice_, rate, probe.hz(name)) > 0.12, (name, start)

    # And it never clips, so the encoder is not deciding what the model hears.
    assert max(abs(value) for value in samples) < 0.95


def test_the_arpeggio_changes_key_by_exactly_one_semitone(tmp_path: Path) -> None:
    """``modulation``: the ground truth is a ratio, not a key signature.

    "The key changes partway through" is decidable without naming either key:
    the second four notes are the first four multiplied by the same constant,
    and that constant is the twelfth root of two. Measuring the ratio rather
    than the keys keeps the test on ground the waveform actually settles.

    The constant also has to be the *same* for all four, which is what makes
    it a transposition rather than four unrelated notes. A drift there would
    mean the second half is in no key at all.
    """
    clip = probe.CLIPS_BY_ID["modulating_arpeggio"]
    samples, rate = decode(clip, tmp_path)

    runs = loud_runs(samples, rate)
    assert len(runs) == 8, runs

    first_half = ("G4", "B4", "D5", "G5")
    second_half = ("Ab4", "C5", "Eb5", "Ab5")
    ratios = []
    for index, (low, high) in enumerate(zip(first_half, second_half)):
        before = window(samples, rate, index * 0.6 + 0.05, index * 0.6 + 0.45)
        after = window(
            samples, rate, (index + 4) * 0.6 + 0.05, (index + 4) * 0.6 + 0.45
        )
        assert magnitude_at(before, rate, probe.hz(low)) > 0.4, low
        assert magnitude_at(after, rate, probe.hz(high)) > 0.4, high
        # The transposed note is genuinely a different pitch, not the same one.
        assert magnitude_at(after, rate, probe.hz(low)) < 0.05, (low, high)
        ratios.append(probe.hz(high) / probe.hz(low))

    for ratio in ratios:
        assert ratio == pytest.approx(2.0 ** (1.0 / 12.0)), ratios
    assert max(ratios) - min(ratios) < 1e-9


def test_the_bass_carries_overtones_a_plain_sine_does_not(tmp_path: Path) -> None:
    """``timbre``: "bass synth" reduced to something a spectrum settles.

    The false criterion calls this a plain sine, so the test needs a plain
    sine to compare against. It builds one -- same pitch, same duration, same
    renderer, no partials -- and shows that the five overtones present in one
    are absent from the other. Without the control, "the second harmonic is
    present" would be a claim about the measurement rather than the clip.

    The falling 1/n weights are checked too. A synth whose sixth harmonic was
    as loud as its second would still be buzzy, but it would not be the
    sawtooth-like tone the criterion describes.
    """
    clip = probe.CLIPS_BY_ID["buzzy_bass"]
    samples, rate = decode(clip, tmp_path)
    body = window(samples, rate, 0.3, 2.7)

    control_clip = probe.Clip(
        clip_id="control_pure_sine",
        duration_s=clip.duration_s,
        segments=(probe.Segment(0.2, 2.8, probe.hz("C2")),),
        description="Not part of the corpus: a control this test renders itself.",
    )
    control, control_rate = decode(control_clip, tmp_path)
    control_body = window(control, control_rate, 0.3, 2.7)

    fundamental = probe.hz("C2")
    assert magnitude_at(body, rate, fundamental) > 0.2
    assert magnitude_at(control_body, control_rate, fundamental) > 0.5

    strengths = []
    for harmonic in probe.BASS_HARMONICS:
        here = magnitude_at(body, rate, fundamental * harmonic)
        there = magnitude_at(control_body, control_rate, fundamental * harmonic)
        assert here > 0.03, (harmonic, here)
        assert there < 0.01, (harmonic, there)
        assert here > there * 5, (harmonic, here, there)
        strengths.append(here)

    # 1/n, so each overtone is quieter than the one below it.
    assert strengths == sorted(strengths, reverse=True), strengths
    assert strengths[0] > strengths[-1] * 2

    # Louder is not the difference: normalisation keeps the two comparable.
    assert max(abs(value) for value in samples) < 0.95


def test_the_original_five_clips_render_byte_for_byte_as_they_did(
    tmp_path: Path,
) -> None:
    """The published "discrimination 0" was measured on these. It must stay re-derivable.

    Adding partials meant touching the renderer every clip goes through, and a
    renderer that quietly changed the old waveforms would leave the earlier
    result describing audio that no longer exists. The report publishes a
    sha256 per clip precisely so a reader can re-derive it; a shifted sample
    breaks that without breaking anything that would be noticed.

    So this recomputes the five single-voice clips the way the renderer worked
    *before* partials existed -- one sine, amplitude ``TONE_AMPLITUDE``,
    assigned rather than accumulated -- and demands exact equality. Local
    recomputation rather than a hard-coded digest, because ``math.sin`` is the
    platform's libm and a pinned hash would fail on a different CI host for a
    reason that has nothing to do with this change.

    The mechanism that makes it hold is arithmetic, not care: with no partials
    the scale is ``TONE_AMPLITUDE / 1.0``, which is ``TONE_AMPLITUDE``, and
    the loop that adds partials runs zero times.
    """
    original = (
        "tone_stops_early",
        "pure_silence",
        "three_beeps",
        "clicks_120bpm",
        "low_then_high",
    )
    for clip_id in original:
        clip = probe.CLIPS_BY_ID[clip_id]
        assert all(not segment.partials for segment in clip.segments), clip_id

        total = int(round(clip.duration_s * probe.CLIP_SAMPLE_RATE_HZ))
        expected = [0.0] * total
        for segment in clip.segments:
            if segment.frequency_hz is None:
                continue
            start = int(round(segment.start_s * probe.CLIP_SAMPLE_RATE_HZ))
            stop = min(
                total, int(round(segment.end_s * probe.CLIP_SAMPLE_RATE_HZ))
            )
            step = (
                2.0
                * math.pi
                * segment.frequency_hz
                / probe.CLIP_SAMPLE_RATE_HZ
            )
            for index in range(start, stop):
                expected[index] = probe.TONE_AMPLITUDE * math.sin(step * index)

        assert probe.clip_samples(clip) == expected, clip_id

    # The same statement one level down, where the amplitude default lives.
    assert list(probe._tone_samples(440.0, 5, 0)) == list(
        probe._tone_samples(440.0, 5, 0, probe.TONE_AMPLITUDE)
    )


def test_a_partial_free_segment_is_normalised_by_exactly_one(tmp_path: Path) -> None:
    """Why the clip above is safe, stated as the property rather than the result.

    ``weight_total`` is the divisor. If it were ever anything but 1.0 for a
    segment with no partials, every previously published clip would come out
    at a different amplitude -- and the test above would fail for a reason
    that is hard to read off a sample mismatch.
    """
    assert probe.Segment(0.0, 1.0, 440.0).weight_total == 1.0
    assert probe.Segment(0.0, 1.0, None).weight_total == 1.0
    assert probe.Segment(0.0, 1.0, 440.0).frequencies_hz == (440.0,)
    assert probe.Segment(0.0, 1.0, None).frequencies_hz == ()

    chord = probe.Segment(0.0, 1.0, 100.0, partials=((200.0, 1.0), (300.0, 0.5)))
    assert chord.weight_total == 2.5
    assert chord.frequencies_hz == (100.0, 200.0, 300.0)


def test_equal_temperament_is_the_ratio_it_claims_to_be() -> None:
    """``pitch_hz`` underwrites every musical claim, so it is checked directly."""
    assert probe.pitch_hz(probe.A4_MIDI) == pytest.approx(440.0)
    assert probe.hz("A4") == pytest.approx(440.0)
    assert probe.hz("G4") == pytest.approx(391.995, abs=0.01)
    assert probe.hz("B4") == pytest.approx(493.883, abs=0.01)
    assert probe.hz("Bb4") == pytest.approx(466.164, abs=0.01)
    assert probe.hz("C2") == pytest.approx(65.406, abs=0.01)
    # An octave doubles, and twelve semitones make an octave.
    assert probe.hz("G5") == pytest.approx(probe.hz("G4") * 2.0)
    assert probe.hz("Ab4") / probe.hz("G4") == pytest.approx(probe.SEMITONE_RATIO)


def test_the_notes_the_false_claims_need_are_never_played() -> None:
    """``Bb4`` and ``F5`` exist in the table only to be shown absent.

    A false criterion is only false if the corpus does not accidentally
    contain what it asks for. These two are the pitches the minor-chord and
    E-flat-major claims would require, and no segment anywhere sounds them.
    """
    sounding: set[float] = set()
    for clip in probe.CLIPS:
        for segment in clip.segments:
            sounding.update(segment.frequencies_hz)
    for absent in ("Bb4", "F5"):
        for played in sounding:
            assert abs(played - probe.hz(absent)) > 1.0, (absent, played)


def test_every_clip_fits_the_window_the_grader_would_cut() -> None:
    """No clip is long enough to be trimmed, so nothing is measured on a stub.

    A clip longer than ``trim_seconds`` would have its tail cut off before the
    model heard it, and a criterion about that tail would be false for the
    probe's reasons rather than the model's.
    """
    for clip in probe.CLIPS:
        assert clip.duration_s < AUDIO_TRIM_SECONDS, clip.clip_id


def _decode_bytes(payload: bytes) -> tuple[list[float], int]:
    with wave.open(io.BytesIO(payload), "rb") as handle:
        rate = handle.getframerate()
        channels = handle.getnchannels()
        frames = handle.readframes(handle.getnframes())
    count = len(frames) // 2
    values = struct.unpack(f"<{count}h", frames)
    if channels > 1:  # pragma: no cover - the grader downmixes to mono
        values = values[::channels]
    return [value / 32768.0 for value in values], rate


def test_the_ground_truth_survives_the_graders_own_re_encode(
    tmp_path: Path,
) -> None:
    """The strongest form of the claim: measured on the bytes that go out.

    A ``.wav`` is never handed over untouched -- ``COMPRESSED_AUDIO_FORMATS``
    is ``("mp3",)`` -- so every clip here is decoded and re-encoded to 16 kHz
    mono by the same ``_trim_audio_bytes`` the grading run uses. Checking the
    waveform *before* that step would leave a gap where a resampler could
    smear a 30 ms click or shift an onset, and the model would then be marked
    wrong about a clip that no longer said what this file thinks it says.

    So the check runs on the encoder's output: three beeps still three, the
    clicks still 120 BPM, the silence still silent.

    The musical clips need this more than the beeps did, not less. A count of
    beeps survives almost any resampler; a chord does not have to. The minor
    third the ``triad`` pair turns on is 27.7 Hz from the major third, and the
    bass overtones run up to 392 Hz on a 65 Hz fundamental -- both are things
    a resampler can smear, and neither is visible in a beep count. Every clip
    is therefore re-measured here at the frequency its criterion names, on the
    bytes the model is actually sent.

    The trailing ``else`` is the point of the branch structure. A clip added
    to the corpus without a branch here would be encoded, sent, judged and
    never checked, which is the failure this whole file exists to prevent.
    """
    from core.perception.audio import _trim_audio_bytes

    for clip in probe.CLIPS:
        path = tmp_path / f"{clip.clip_id}.wav"
        probe.render_clip(clip, path)
        payload, fmt = _trim_audio_bytes(str(path), AUDIO_TRIM_SECONDS)
        assert fmt in SUPPORTED_AUDIO_FORMATS, clip.clip_id
        samples, rate = _decode_bytes(payload)
        assert rate == AUDIO_SAMPLE_RATE_HZ, clip.clip_id

        if clip.clip_id == "pure_silence":
            assert max(abs(v) for v in samples) < 1e-3
        elif clip.clip_id == "three_beeps":
            assert len(loud_runs(samples, rate)) == 3
        elif clip.clip_id == "clicks_120bpm":
            runs = loud_runs(samples, rate)
            assert len(runs) == 16, len(runs)
            gaps = [b[0] - a[0] for a, b in zip(runs, runs[1:])]
            assert abs(60.0 / (sum(gaps) / len(gaps)) - 120.0) < 1.0
        elif clip.clip_id == "tone_stops_early":
            runs = loud_runs(samples, rate)
            assert len(runs) == 1
            assert 1.9 < runs[0][1] < 2.1
        elif clip.clip_id == "low_then_high":
            low = zero_crossing_hz(
                samples[int(0.2 * rate) : int(1.8 * rate)], rate
            )
            high = zero_crossing_hz(
                samples[int(3.2 * rate) : int(4.8 * rate)], rate
            )
            assert high > low * 3, (low, high)
        elif clip.clip_id == "g_major_scale":
            assert len(loud_runs(samples, rate)) == 8
            seventh = window(samples, rate, 2.45, 2.70)
            assert magnitude_at(seventh, rate, probe.hz("Fs5")) > 0.4
            assert magnitude_at(seventh, rate, probe.hz("F5")) < 0.05
        elif clip.clip_id == "major_triad":
            body = window(samples, rate, 0.3, 2.7)
            for name in ("G4", "B4", "D5"):
                assert magnitude_at(body, rate, probe.hz(name)) > 0.15, name
            assert magnitude_at(body, rate, probe.hz("Bb4")) < 0.02
        elif clip.clip_id == "modulating_arpeggio":
            assert len(loud_runs(samples, rate)) == 8
            for index, (low_name, high_name) in enumerate(
                zip(("G4", "B4", "D5", "G5"), ("Ab4", "C5", "Eb5", "Ab5"))
            ):
                before = window(
                    samples, rate, index * 0.6 + 0.05, index * 0.6 + 0.45
                )
                after = window(
                    samples,
                    rate,
                    (index + 4) * 0.6 + 0.05,
                    (index + 4) * 0.6 + 0.45,
                )
                assert magnitude_at(before, rate, probe.hz(low_name)) > 0.4
                assert magnitude_at(after, rate, probe.hz(high_name)) > 0.4
                assert magnitude_at(after, rate, probe.hz(low_name)) < 0.05
        elif clip.clip_id == "buzzy_bass":
            body = window(samples, rate, 0.3, 2.7)
            fundamental = probe.hz("C2")
            assert magnitude_at(body, rate, fundamental) > 0.2
            for harmonic in probe.BASS_HARMONICS:
                assert (
                    magnitude_at(body, rate, fundamental * harmonic) > 0.03
                ), harmonic
        else:  # pragma: no cover - reached only by an unchecked new clip
            pytest.fail(
                f"{clip.clip_id} is sent to the model but nothing here checks "
                f"that its ground truth survives the re-encode"
            )


# --------------------------------------------------------------------------
# The criteria are balanced, paired, and free of accidental listening windows
# --------------------------------------------------------------------------


def test_corpus_is_balanced_and_paired() -> None:
    """Ten true, ten false, matched one-of-each on the same clip.

    Balance is what makes Youden's J readable; pairing is what makes the
    permutation null contain only corpora that could actually have existed.

    The pair count is also the whole p-floor: ten pairs is what puts the best
    attainable p below 0.01, and six could not. Asserting it here means the
    floor cannot be lowered by deleting a pair without a test saying so.
    """
    assert sum(1 for c in probe.CLAIMS if c.holds) == 10
    assert sum(1 for c in probe.CLAIMS if not c.holds) == 10
    pairs: dict[str, list[probe.Claim]] = {}
    for claim in probe.CLAIMS:
        pairs.setdefault(claim.pair_id, []).append(claim)
    assert len(pairs) == 10
    for pair_id, members in pairs.items():
        assert len(members) == 2, pair_id
        assert {m.holds for m in members} == {True, False}, pair_id
        assert len({m.clip_id for m in members}) == 1, pair_id
        assert len({m.family for m in members}) == 1, pair_id


def test_every_claim_points_at_a_clip_that_exists() -> None:
    for claim in probe.CLAIMS:
        assert claim.clip_id in probe.CLIPS_BY_ID, claim.claim_id


def test_every_clip_carries_at_least_one_claim() -> None:
    """A clip nothing asks about is rendered, encoded, and never heard."""
    used = {claim.clip_id for claim in probe.CLAIMS}
    assert used == set(probe.CLIPS_BY_ID)


def test_no_criterion_accidentally_asks_for_a_listening_window() -> None:
    """``criterion_listen_start`` parses ``M:SS``, and these clips have no 1:30.

    A criterion containing something that scans as a timestamp would move the
    slice off the head of a five-second clip, and the model would be asked
    about a window the file does not have. Every claim here must leave the
    window at the head.
    """
    for claim in probe.CLAIMS:
        start = criterion_listen_start(
            claim.criterion, trim_seconds=AUDIO_TRIM_SECONDS
        )
        assert not start, (claim.claim_id, start)


def test_claim_ids_are_unique() -> None:
    ids = [claim.claim_id for claim in probe.CLAIMS]
    assert len(ids) == len(set(ids))


def test_no_criterion_is_a_substring_of_another() -> None:
    """``TruthfulStub`` matches on the first ``criterion in text`` hit.

    That is fine while the criteria are distinct strings and silently wrong
    the moment one contains another: the stub would answer the shorter claim's
    ground truth for the longer claim, and a dry run would go green while
    measuring the wrong thing. The corpus doubled in this change and the two
    ``triad`` criteria differ by one word, so the property is worth asserting
    rather than assuming.

    This constrains the *fixture*, not the model. A real judge reads the whole
    prompt; only the stub matches by substring.
    """
    criteria = [claim.criterion for claim in probe.CLAIMS]
    assert len(criteria) == len(set(criteria))
    for outer in criteria:
        for inner in criteria:
            if inner != outer:
                assert inner not in outer, (inner, outer)


def test_the_workflow_states_the_corpus_it_actually_has() -> None:
    """The paid entry point restates these counts, so they have to be checked.

    ``audio-accuracy-probe.yml`` is the only way this measurement gets bought,
    and four places in it say how big the corpus is: the header comment, the
    ``repeats`` input description a dispatcher reads, and two lines of the
    approval record. None of them can read ``CLAIMS`` -- the gate job has no
    checkout, and a comment cannot compute -- so all four are restatements.

    They rotted once already. The corpus went from twelve criteria to twenty
    and the workflow kept saying twelve, which put ``calls = 36`` on the
    approval record for a run that would make sixty. A wrong call count on a
    paid gate is the specific kind of wrong this repository cares about: the
    record that says what was authorised disagreed with what was spent.

    So the restatements are pinned rather than trusted. This test is the
    reason it is safe to restate them at all.
    """
    text = (
        probe.REPO_ROOT / ".github" / "workflows" / "audio-accuracy-probe.yml"
    ).read_text(encoding="utf-8")

    claims = len(probe.CLAIMS)
    true_claims = sum(1 for claim in probe.CLAIMS if claim.holds)
    false_claims = claims - true_claims
    clips = len(probe.CLIPS)

    words = {
        "five": 5,
        "six": 6,
        "nine": 9,
        "ten": 10,
        "twelve": 12,
        "twenty": 20,
    }

    # The header comment: "Twenty criteria, ten true and ten false, matched in
    # pairs on nine clips".
    header = re.search(
        r"(\w+) criteria, (\w+) true and\n#\s*(\w+) false, matched in pairs on "
        r"(\w+) clips",
        text,
    )
    assert header, "the header comment no longer states the corpus size"
    assert words[header.group(1).lower()] == claims
    assert words[header.group(2).lower()] == true_claims
    assert words[header.group(3).lower()] == false_claims
    assert words[header.group(4).lower()] == clips

    # The dispatch input description, which is what someone reads before
    # deciding whether to spend.
    formula = re.search(r"Total calls = (\d+) criteria x repeats", text)
    assert formula, "the repeats input no longer states the call formula"
    assert int(formula.group(1)) == claims

    # The approval record, both lines of it.
    record = re.search(r"criteria\s+= (\d+) \((\d+) true / (\d+) false\)", text)
    assert record, "the approval record no longer states the criteria count"
    assert int(record.group(1)) == claims
    assert int(record.group(2)) == true_claims
    assert int(record.group(3)) == false_claims

    calls = re.search(r"calls\s+= \$\(\((\d+) \* PROBE_REPEATS\)\)", text)
    assert calls, "the approval record no longer computes the call count"
    assert int(calls.group(1)) == claims

    # The permutation figures in the paid summary are *derived* from the
    # report rather than restated, which is why they are not checked above.
    # This asserts they stayed derived: a literal here would be the next thing
    # to rot, and it would misdescribe what the design can support.
    for stale in ("six pairs", "64 relabellings", "0.01 is out of reach"):
        assert stale not in text, stale


def _workflow() -> dict:
    return yaml.safe_load(
        (
            probe.REPO_ROOT / ".github" / "workflows" / "audio-accuracy-probe.yml"
        ).read_text(encoding="utf-8")
    )


def _step(job: str, name: str) -> dict:
    for step in _workflow()["jobs"][job]["steps"]:
        if step.get("name") == name:
            return step
    raise AssertionError(f"{job} has no step named {name!r}")


def test_the_workflow_offers_exactly_the_arms_the_script_accepts() -> None:
    """A dispatch that cannot ask for both arms cannot buy the comparison.

    The paired analysis in ``326-prompt-arm-prereg.md`` needs the two prompts
    interleaved against the same audio in one process. If the workflow can
    only ask for the production arm, the only way to get a treatment arm is a
    second dispatch -- which is the design the pre-registration rejected,
    because a gap between the two halves lets a deployment change masquerade
    as a prompt effect.
    """
    # `on` parses as the boolean True in YAML 1.1, which is why this is not
    # spelled workflow["on"].
    inputs = _workflow()[True]["workflow_dispatch"]["inputs"]
    arm = inputs["prompt_arm"]

    assert arm["type"] == "choice"
    assert sorted(arm["options"]) == sorted((*probe.PROMPT_ARMS, "both"))
    # Default to the cheap half. `both` doubles the spend, so it has to be
    # something a dispatcher chose rather than something they inherited.
    assert arm["default"] == "production"
    assert arm["default"] in probe.PROMPT_ARMS


@pytest.mark.parametrize("job,step_name", [
    ("dry-run", "Dry run"),
    ("measure", "Measure"),
])
def test_both_runs_forward_the_arm_and_keep_the_delivery_record(
    job: str, step_name: str
) -> None:
    """The input has to reach the script, and the evidence has to come back.

    Two failures this catches, both silent. An arm input the run never
    forwards means a reviewer approves 120 calls and the run buys 60 of one
    prompt -- the approval record and the spend disagree again, in the other
    direction. A missing ``--delivery-out`` means the run that exists to prove
    the audio arrived does not write down whether it did.
    """
    run = _step(job, step_name)["run"]
    assert "--prompt-arm" in run, f"{job} does not forward the arm"
    assert "inputs.prompt_arm" in run
    assert "--delivery-out" in run, f"{job} keeps no delivery record"


@pytest.mark.parametrize("job", ["dry-run", "measure"])
def test_the_summaries_report_the_whole_run_not_one_arm(job: str) -> None:
    """``accuracy`` covers the production arm alone. The call count must not.

    ``build_report`` deliberately scores the control arm only, so that the
    headline number keeps meaning what it meant before there was a second
    prompt. That makes ``accuracy.overall.calls`` half of a ``both`` run, and
    a summary that printed it as the call count would understate a paid run --
    the same class of error as the approval record that said 36.

    The free summary is checked too. It costs nothing to produce, but it is
    what a dispatcher reads *before* deciding to buy, so a call count that is
    half the truth there is the more expensive of the two.
    """
    summary = _step(job, "Summarise")["run"]
    assert "report['cost']['model_calls']" in summary
    assert "acc['overall']['calls']" not in summary
    assert "prompt_arms" in summary, "the summary does not say which arms ran"


def test_the_paid_summary_names_the_arm_its_table_describes() -> None:
    """A per-arm table under an unqualified heading reads as the whole run."""
    assert "production arm alone" in _step("measure", "Summarise")["run"]


@pytest.mark.parametrize("arm,arms", [
    ("production", 1),
    ("observation", 1),
    ("both", 2),
])
@pytest.mark.parametrize("repeats", [1, 3])
def test_the_approval_record_counts_the_calls_both_arms_will_make(
    arm: str, arms: int, repeats: int
) -> None:
    """Run the gate's own shell and read what it would put on the record.

    This is the line that says what was authorised. It is shell arithmetic in
    a job with no checkout, so nothing in the script can constrain it -- which
    is precisely why it was wrong before. Executing it is the only check that
    does not amount to reading it twice.
    """
    bash = shutil.which("bash")
    if bash is None:  # pragma: no cover - CI and dev boxes both have bash
        pytest.skip("no bash to run the gate's own script with")

    result = subprocess.run(
        [bash, "-c", _step("approve-paid", "Record approved request")["run"]],
        env={**os.environ, "PROBE_REPEATS": str(repeats), "PROBE_ARM": arm},
        capture_output=True,
        text=True,
        check=True,
    )
    line = re.search(
        r"calls\s+= (\d+) per arm, (\d+) in total", result.stdout
    )
    assert line, result.stdout
    claims = len(probe.CLAIMS)
    assert int(line.group(1)) == claims * repeats
    assert int(line.group(2)) == claims * repeats * arms
    assert f"prompt_arm = {arm}" in result.stdout


# --------------------------------------------------------------------------
# The scorer, including the ways it must refuse to flatter
# --------------------------------------------------------------------------


def _calls(verdict_for) -> list[dict]:
    return [
        {
            "repeat": 1,
            "claim_id": claim.claim_id,
            "pair_id": claim.pair_id,
            "clip_id": claim.clip_id,
            "family": claim.family,
            "holds": claim.holds,
            "verdict": verdict_for(claim),
            "outcome": probe.classify(claim, verdict_for(claim)),
            "confidence": 1.0,
            "evidence": "",
            "judge_error": None,
            "api_call_count": 1,
            "input_tokens": 0,
            "output_tokens": 0,
            "latency_ms": 0.0,
            "usage_complete": False,
        }
        for claim in probe.CLAIMS
    ]


def test_classify_maps_each_verdict_to_the_error_it_is() -> None:
    true_claim = next(c for c in probe.CLAIMS if c.holds)
    false_claim = next(c for c in probe.CLAIMS if not c.holds)
    assert probe.classify(true_claim, "pass") == probe.OUTCOME_CORRECT
    assert probe.classify(true_claim, "fail") == probe.OUTCOME_FALSE_FAIL
    assert probe.classify(false_claim, "pass") == probe.OUTCOME_FALSE_PASS
    assert probe.classify(false_claim, "fail") == probe.OUTCOME_CORRECT


def test_a_hedge_is_never_counted_as_correct() -> None:
    """These criteria are arithmetic. ``partial`` is a refusal, not a near-miss.

    Folding hedges into ``correct`` would let a model that never committed to
    anything report a good accuracy; folding them into the errors would
    overstate a failure it did not commit either.
    """
    for claim in probe.CLAIMS:
        assert probe.classify(claim, "partial") == probe.OUTCOME_HEDGED


def test_judge_error_is_not_an_answer_in_either_direction() -> None:
    for claim in probe.CLAIMS:
        assert probe.classify(claim, "judge_error") == probe.OUTCOME_UNANSWERED
    summary = probe.summarise(_calls(lambda claim: "judge_error"))
    assert summary["overall"]["answered"] == 0
    # Not 0.0. There is no accuracy to report, and printing zero would read as
    # "got everything wrong" rather than "measured nothing".
    assert summary["overall"]["accuracy"] is None
    assert summary["discrimination_j"]["per_call"] is None


def test_a_model_that_always_says_pass_scores_zero_discrimination() -> None:
    """The control this whole metric exists for.

    Accuracy is 50% -- it got every true claim right -- and that 50% is
    worth nothing, because the same answer was given without listening. J is
    what says so.
    """
    summary = probe.summarise(_calls(lambda claim: "pass"))
    assert summary["overall"]["accuracy"] == pytest.approx(0.5)
    assert summary["discrimination_j"]["per_call"] == pytest.approx(0.0)
    assert summary["on_true_claims"]["false_fail_rate"] == pytest.approx(0.0)
    assert summary["on_false_claims"]["false_pass_rate"] == pytest.approx(1.0)


def test_a_model_that_always_says_fail_also_scores_zero_discrimination() -> None:
    """The mirror image, and the one the gold run's 5-of-7 failures would look like."""
    summary = probe.summarise(_calls(lambda claim: "fail"))
    assert summary["overall"]["accuracy"] == pytest.approx(0.5)
    assert summary["discrimination_j"]["per_call"] == pytest.approx(0.0)
    assert summary["on_true_claims"]["false_fail_rate"] == pytest.approx(1.0)
    assert summary["on_false_claims"]["false_pass_rate"] == pytest.approx(0.0)


def test_a_perfect_listener_scores_one() -> None:
    summary = probe.summarise(_calls(lambda claim: "pass" if claim.holds else "fail"))
    assert summary["overall"]["accuracy"] == pytest.approx(1.0)
    assert summary["discrimination_j"]["per_call"] == pytest.approx(1.0)
    assert summary["on_true_claims"]["false_fail_rate"] == pytest.approx(0.0)
    assert summary["on_false_claims"]["false_pass_rate"] == pytest.approx(0.0)


def test_an_inverted_listener_scores_minus_one() -> None:
    """Heard it and got it backwards. Distinguishable from not listening at all."""
    summary = probe.summarise(_calls(lambda claim: "fail" if claim.holds else "pass"))
    assert summary["discrimination_j"]["per_call"] == pytest.approx(-1.0)


def test_rates_are_none_not_zero_when_there_is_nothing_to_divide_by() -> None:
    assert probe._rate(0, 0) is None
    assert probe._rate(0, 4) == pytest.approx(0.0)


# --------------------------------------------------------------------------
# The permutation test, and the bound it cannot escape
# --------------------------------------------------------------------------


def test_permutation_is_exhaustive_over_one_thousand_relabellings() -> None:
    result = probe.permute_within_pairs(_calls(lambda c: "pass" if c.holds else "fail"))
    assert result["pairs"] == 10
    assert result["assignments"] == 1024


def test_the_best_possible_p_now_clears_one_percent_and_says_so() -> None:
    """The design's own ceiling, published with the number rather than after it.

    This assertion used to run the other way. Six pairs gave 64 assignments
    and a floor of 1/64 = 0.015625, so *nothing* the first version of this
    experiment could produce reached 0.01 -- however well the model listened,
    and however many repeats were bought. Repeats never touched it; only pairs
    could, because the floor is 1 / 2**pairs and repeats are not in it.

    Four musical pairs is what removed the bound. Both numbers are asserted,
    the live one and the one it replaced, so that the arithmetic linking them
    is on the record rather than in a commit message: a pair deleted from the
    corpus puts the floor back above 0.01 and this test says which side of the
    line it landed on.

    Publishing the floor beside the p is the same discipline as
    ``is_informative: false`` on the repeat-variation interval: the reader is
    told what the measurement *cannot* support at the moment they are told
    what it found.
    """
    result = probe.permute_within_pairs(_calls(lambda c: "pass" if c.holds else "fail"))
    assert result["smallest_attainable_p"] == pytest.approx(1.0 / 1024.0)
    assert result["p_one_sided"] == pytest.approx(1.0 / 1024.0)
    assert result["smallest_attainable_p"] < 0.01
    # The floor this replaced, and the reason it could not be fixed by paying
    # for more repeats: 2 ** 6 == 64, and 1/64 is on the wrong side of 0.01.
    assert 1.0 / (2.0 ** 6) > 0.01
    assert result["smallest_attainable_p"] == pytest.approx(1.0 / (2.0 ** 10))


def test_a_constant_answer_is_not_significant() -> None:
    """J = 0 must come back with a p that refuses to call it a finding."""
    result = probe.permute_within_pairs(_calls(lambda claim: "pass"))
    assert result["observed_j"] == pytest.approx(0.0)
    assert result["p_one_sided"] == pytest.approx(1.0)


def test_permutation_is_deterministic() -> None:
    """Exhaustive, so there is no seed to pin and no run-to-run drift."""
    calls = _calls(lambda c: "pass" if c.holds else "fail")
    first = probe.permute_within_pairs(calls)
    second = probe.permute_within_pairs(calls)
    assert first == second


def test_labels_are_swapped_within_pairs_not_across_the_corpus() -> None:
    """Every relabelling must leave the corpus balanced, and 1024 of them exist.

    A free shuffle over twenty labels would build null corpora that could not
    have existed -- both criteria about the silent clip true at once -- and
    would enumerate C(20,10) = 184,756 of them, putting the p-floor two orders
    of magnitude lower and quietly claiming a resolution the design does not
    have. That temptation grew with the corpus rather than shrinking: at six
    pairs a free shuffle bought 924 against 64, and at ten it buys 184,756
    against 1024, so the gap between the honest floor and the flattering one
    is now 180x. Two observable consequences pin the within-pair scheme: the
    assignment count is exactly 1024, and a perfect listener's p is exactly
    1/1024 rather than 1/184,756.

    The count also has to be 1024 *including* degenerate answers -- if any
    relabelling produced an all-true corpus, J would be ``None`` there and the
    denominator would silently shrink.
    """
    for verdict_for in (
        lambda c: "pass" if c.holds else "fail",
        lambda c: "pass",
        lambda c: "fail" if c.holds else "pass",
    ):
        result = probe.permute_within_pairs(_calls(verdict_for))
        assert result["assignments"] == 1024
        assert 1 <= result["at_least_observed"] <= 1024
        assert result["p_one_sided"] == pytest.approx(
            result["at_least_observed"] / 1024
        )
    # The free-shuffle count, spelled out so the comparison above is checkable
    # rather than asserted: 184,756 is not what this enumerates.
    assert math.comb(20, 10) == 184756


def test_the_perfect_and_inverted_ends_of_the_null_are_where_they_should_be() -> None:
    """One assignment beats a perfect listener; all 1024 beat an inverted one."""
    perfect = probe.permute_within_pairs(
        _calls(lambda c: "pass" if c.holds else "fail")
    )
    assert perfect["at_least_observed"] == 1
    inverted = probe.permute_within_pairs(
        _calls(lambda c: "fail" if c.holds else "pass")
    )
    assert inverted["at_least_observed"] == 1024
    assert inverted["p_one_sided"] == pytest.approx(1.0)


# --------------------------------------------------------------------------
# Majority and stability
# --------------------------------------------------------------------------


def test_a_tie_has_no_majority_rather_than_the_first_answer() -> None:
    """Three repeats that all disagree is exactly the 19.35% this card measured.

    Breaking the tie by order would hide that instability inside the accuracy
    number, which is the one place it must not be.
    """
    assert probe.majority_verdict(["pass", "fail", "partial"]) is None
    assert probe.majority_verdict(["pass", "fail"]) is None
    assert probe.majority_verdict(["pass", "pass", "fail"]) == "pass"


def test_majority_ignores_unanswered_calls() -> None:
    assert probe.majority_verdict(["judge_error", "pass", "judge_error"]) == "pass"
    assert probe.majority_verdict(["judge_error"]) is None


# --------------------------------------------------------------------------
# The identity is borrowed, not restated
# --------------------------------------------------------------------------


def test_identity_comes_from_the_config_the_repeat_runs_used() -> None:
    """If the config moves, this measurement is of a different model.

    The accuracy figure is only an explanation of the 19.35% while it
    describes the same deployment at the same clip length and the same cap.
    """
    assert probe.PINNED_CONFIG.exists(), probe.PINNED_CONFIG
    identity = probe.pinned_identity()
    assert identity["audio_deployment"] == "gpt-audio-1.5"
    assert identity["audio_model"] == "gpt-audio-1.5"
    assert identity["audio_clip_seconds"] == AUDIO_TRIM_SECONDS
    assert identity["audio_call_cap_per_task"] == AUDIO_CALL_CAP


def test_pinned_config_is_the_audio_repeat_config() -> None:
    assert probe.PINNED_CONFIG.name == "gold_audio_repeat_v2_sol_max.yaml"


# --------------------------------------------------------------------------
# The dry run: whole path, no network, no cost
# --------------------------------------------------------------------------


def test_dry_run_exercises_the_real_audio_path(tmp_path: Path) -> None:
    """Everything but the model: render, trim, base64, prompt, parse, tally.

    The point is that the shape of the report is proven on every commit rather
    than first observed on the run being paid for.
    """
    stub = probe.TruthfulStub(probe.CLAIMS)
    perception = AudioPerception(client=stub, deployment="gpt-audio-1.5")
    result = probe.run_measurement(
        perception=perception, clip_dir=tmp_path, repeats=2
    )
    assert len(result["calls"]) == 2 * len(probe.CLAIMS)
    assert len(stub.requests) == 2 * len(probe.CLAIMS)
    for request in stub.requests:
        parts = request["messages"][0]["content"]
        kinds = [part["type"] for part in parts]
        assert kinds == ["text", "input_audio"]
        assert request["modalities"] == ["text"]
        assert request["model"] == "gpt-audio-1.5"
        audio = parts[1]["input_audio"]
        assert audio["format"] in SUPPORTED_AUDIO_FORMATS
        assert audio["data"]


def test_dry_run_reports_a_perfect_score_and_says_it_measured_nothing(
    tmp_path: Path,
) -> None:
    """The stub answers from the segment list, so 100% here means nothing.

    ``measured: false`` is what stops a green CI line from being read as a
    result about ``gpt-audio-1.5``.
    """
    stub = probe.TruthfulStub(probe.CLAIMS)
    perception = AudioPerception(client=stub, deployment="gpt-audio-1.5")
    result = probe.run_measurement(
        perception=perception, clip_dir=tmp_path, repeats=1
    )
    report = probe.build_report(
        identity=probe.pinned_identity(),
        measured=False,
        repeats=1,
        result=result,
    )
    assert report["measured"] is False
    assert report["accuracy"]["overall"]["accuracy"] == pytest.approx(1.0)
    assert report["accuracy"]["discrimination_j"]["per_call"] == pytest.approx(1.0)
    assert report["cost"]["estimated_cost_usd"] is None
    assert report["cost"]["pricing_complete"] is True
    assert report["cost"]["unpriced_models"] == []
    # 20 calls went out to the stub and none of them were billed. A report
    # that said "billable_calls: 20" here is the figure someone copies.
    assert report["cost"]["model_calls"] == 20
    assert report["cost"]["billable_calls"] == 0


def test_a_measured_run_records_cost_as_unknown_not_zero(tmp_path: Path) -> None:
    """``gpt-audio-1.5`` is not in the price table, so the money is null.

    This is the rule the cost card has been enforcing since the first paid
    run: an unpriced model costs an unknown amount, and writing ``$0`` would
    be a claim nobody can support.
    """
    stub = probe.TruthfulStub(probe.CLAIMS)
    perception = AudioPerception(client=stub, deployment="gpt-audio-1.5")
    result = probe.run_measurement(
        perception=perception, clip_dir=tmp_path, repeats=1
    )
    report = probe.build_report(
        identity=probe.pinned_identity(),
        measured=True,
        repeats=1,
        result=result,
    )
    assert report["cost"]["model_calls"] == len(probe.CLAIMS)
    assert report["cost"]["billable_calls"] == len(probe.CLAIMS)
    assert report["cost"]["estimated_cost_usd"] is None
    assert report["cost"]["pricing_complete"] is False
    assert report["cost"]["unpriced_models"] == ["gpt-audio-1.5"]
    assert "null" in report["cost"]["note"]


def test_report_is_json_serialisable_and_carries_the_clip_digests(
    tmp_path: Path,
) -> None:
    """The clips are not committed, so the digests are how a reader re-derives them."""
    stub = probe.TruthfulStub(probe.CLAIMS)
    perception = AudioPerception(client=stub, deployment="gpt-audio-1.5")
    result = probe.run_measurement(
        perception=perception, clip_dir=tmp_path, repeats=1
    )
    report = probe.build_report(
        identity=probe.pinned_identity(), measured=False, repeats=1, result=result
    )
    encoded = json.loads(json.dumps(report, ensure_ascii=False))
    assert set(encoded["clip_sha256"]) == set(probe.CLIPS_BY_ID)
    for digest in encoded["clip_sha256"].values():
        assert len(digest) == 64


def test_rendering_is_reproducible(tmp_path: Path) -> None:
    """Same segments, same bytes. No timestamps, no randomness, no dither."""
    clip = probe.CLIPS_BY_ID["three_beeps"]
    first = probe.render_clip(clip, tmp_path / "a.wav")
    second = probe.render_clip(clip, tmp_path / "b.wav")
    assert first == second


def test_per_claim_call_cap_is_reset_so_the_tail_is_not_refused(
    tmp_path: Path,
) -> None:
    """A corpus-wide counter would turn later claims into ``cap_exceeded``.

    The cap bounds what one graded *task* spends. Here each criterion is its
    own unit of work, and letting the counter run would fabricate refusals
    that look like model behaviour.
    """
    stub = probe.TruthfulStub(probe.CLAIMS)
    perception = AudioPerception(
        client=stub, deployment="gpt-audio-1.5", call_cap=2
    )
    result = probe.run_measurement(
        perception=perception, clip_dir=tmp_path, repeats=1
    )
    verdicts = {call["verdict"] for call in result["calls"]}
    assert verdicts <= {"pass", "fail"}, verdicts
    assert not probe.unanswered_claims(result["calls"])


# --------------------------------------------------------------------------
# Exit codes
# --------------------------------------------------------------------------


def test_unanswered_claims_are_named(tmp_path: Path) -> None:
    calls = _calls(lambda claim: "judge_error")
    assert probe.unanswered_claims(calls) == sorted(
        c.claim_id for c in probe.CLAIMS
    )


def test_a_claim_answered_once_out_of_three_is_not_unanswered() -> None:
    """One verdict is a thin measurement, not a missing one."""
    calls = _calls(lambda claim: "judge_error")
    calls[0] = {**calls[0], "verdict": "pass"}
    missing = probe.unanswered_claims(calls)
    assert calls[0]["claim_id"] not in missing
    assert len(missing) == len(probe.CLAIMS) - 1


def test_main_dry_run_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    code = probe.main(["--dry-run", "--repeats", "1", "--quiet"])
    assert code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["measured"] is False
    assert report["pins"]["claims"] == 20
    assert report["pins"]["true_claims"] == 10
    assert report["pins"]["false_claims"] == 10
    assert len(report["calls"]) == 20


def test_main_rejects_a_repeat_count_below_one() -> None:
    with pytest.raises(SystemExit):
        probe.main(["--dry-run", "--repeats", "0"])


def test_main_writes_the_report_where_it_is_told(tmp_path: Path) -> None:
    out = tmp_path / "nested" / "report.json"
    assert probe.main(["--dry-run", "--repeats", "1", "--quiet", "--out", str(out)]) == 0
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["accuracy"]["overall"]["calls"] == 20


def test_main_refuses_a_config_whose_model_and_deployment_disagree(
    tmp_path: Path,
) -> None:
    """Exit 3: whatever that would have measured, it was not the pinned path."""
    config = tmp_path / "mismatched.yaml"
    config.write_text(
        "grader:\n"
        "  judge:\n"
        "    perception:\n"
        "      audio:\n"
        "        model: gpt-audio-1.5\n"
        "        deployment: some-other-deployment\n",
        encoding="utf-8",
    )
    assert probe.main(["--dry-run", "--quiet", "--config", str(config)]) == 3


def test_pinned_identity_refuses_a_config_with_no_audio_block(
    tmp_path: Path,
) -> None:
    config = tmp_path / "no_audio.yaml"
    config.write_text("judge: {}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="judge.perception.audio"):
        probe.pinned_identity(config)


def test_identity_is_resolved_by_the_graders_own_rule(tmp_path: Path) -> None:
    """Not a second implementation of the model/deployment check.

    ``canonical_deployment`` is what ``grader.py`` calls on this exact config
    path. Borrowing it means a config this probe accepts is a config the
    grading run would accept, and there is no way for the two to drift apart.
    """
    config = tmp_path / "mismatched.yaml"
    config.write_text(
        "judge:\n"
        "  perception:\n"
        "    audio:\n"
        "      model: gpt-audio-1.5\n"
        "      deployment: some-other-deployment\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="must match"):
        probe.pinned_identity(config)


# --------------------------------------------------------------------------
# The script does not change what it measures
# --------------------------------------------------------------------------


def test_a_new_file_under_scripts_does_not_move_a_grader_fingerprint() -> None:
    """Measured, not assumed: add a file to ``scripts/`` and the hash holds.

    ``compute_grader_source_hash`` takes exactly one file from ``scripts/`` --
    ``download_inference_from_hf.py``. Everything else there is outside the
    set, which is what lets this probe land without invalidating a grading
    approval already given for something else.

    Asserting that from the source listing would only restate it. So the test
    creates a real file beside this script, recomputes the fingerprint of the
    config the repeat runs used, and requires the digest to be byte-identical.
    """
    import yaml

    from step8_grade import compute_grader_source_hash  # noqa: E402

    with probe.PINNED_CONFIG.open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle)

    before = compute_grader_source_hash(probe.PINNED_CONFIG, config)

    intruder = Path(probe.__file__).with_name("_fingerprint_probe_tmp.py")
    assert not intruder.exists()
    try:
        intruder.write_text("# transient, for one assertion\n", encoding="utf-8")
        after = compute_grader_source_hash(probe.PINNED_CONFIG, config)
    finally:
        intruder.unlink(missing_ok=True)

    assert after == before
    assert len(before) == 64


def test_the_probe_itself_is_one_of_those_files() -> None:
    """Same directory, same exemption. Named so a move gets caught here."""
    assert Path(probe.__file__).parent.name == "scripts"
    assert Path(probe.__file__).name == "measure_audio_grading_accuracy.py"


def test_stub_refuses_a_criterion_it_was_not_given() -> None:
    """The stub answers from the corpus, so an unknown criterion is a bug.

    Silently returning ``fail`` would make a dry run that lost half its
    prompts look like a model that got half of them wrong.
    """
    stub = probe.TruthfulStub(probe.CLAIMS[:1])
    with pytest.raises(AssertionError, match="does not know"):
        stub.create(
            model="gpt-audio-1.5",
            messages=[
                {
                    "role": "user",
                    "content": [{"type": "text", "text": "something else entirely"}],
                }
            ],
            modalities=["text"],
        )


# ── The speech corpus arrives instead of being rendered ──────────────
#
# The tone corpus is generated here and checked against its own waveform. The
# speech set cannot be: eSpeak NG does not install on this host, so the clips
# come from CI as an artifact and the repository keeps a manifest. That makes
# the loader, not the renderer, the thing standing between "measured the
# pinned set" and "measured whatever was in that folder".


PUBLISHED_SPEECH_MANIFEST = (
    Path(__file__).resolve().parents[2]
    / "tasks"
    / "rebuilding_grading_task"
    / "330-speech-verification-manifest.json"
)


def _speech_fixture(tmp_path: Path, *, clips: int = 2) -> tuple[Path, Path]:
    """A miniature manifest with real files behind it.

    Built here rather than copied from the published set so the tests do not
    depend on the artifact being downloaded, and so a digest can be corrupted
    without editing a committed file.
    """
    clip_dir = tmp_path / "clips"
    clip_dir.mkdir()
    entries = []
    claims = []
    for index in range(clips):
        clip_id = f"clip{index}"
        path = clip_dir / f"{clip_id}.sent.wav"
        with wave.open(str(path), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(16_000)
            handle.writeframes(struct.pack("<800h", *([0] * 800)))
        data = path.read_bytes()
        entries.append({
            "clip_id": clip_id,
            "source": {"file": f"{clip_id}.source.wav", "sha256": "0" * 64},
            "sent": {
                "file": path.name,
                "sha256": hashlib.sha256(data).hexdigest(),
                "seconds": 0.05,
                "sample_rate_hz": 16_000,
            },
        })
        for suffix, holds in (("yes", True), ("no", False)):
            claims.append({
                "claim_id": f"{clip_id}_{suffix}",
                "pair_id": f"{clip_id}_pair",
                "clip_id": clip_id,
                "family": "confusable_number",
                "criterion": f"criterion {suffix} for {clip_id}",
                "holds": holds,
                "because": "fixture",
            })
    manifest = {
        "clips": entries,
        "claims": claims,
        "provenance": {"tool": "espeak-ng", "version_string": "fixture"},
        "encoder": {"library": "PyAV"},
        "limits": {"reading": "a pass is strong, a failure is weak"},
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path, clip_dir


def test_the_pairing_is_read_from_the_set_and_not_guessed_from_the_name() -> None:
    """The tone corpus's naming rule is wrong for the speech set, silently.

    ``claim_id.rsplit("_", 1)[0]`` recovers the pair for ``timing_true`` /
    ``timing_false``. Applied to the published speech set it produces
    **thirteen** groups instead of ten, six of them holding a single claim --
    and a permutation test that swaps labels within a pair of size one does
    not swap anything. The corpus would still report an accuracy; only the
    null distribution it was compared against would be a straight line.
    """
    published = json.loads(PUBLISHED_SPEECH_MANIFEST.read_text(encoding="utf-8"))
    derived: dict[str, list[bool]] = {}
    for entry in published["claims"]:
        derived.setdefault(
            entry["claim_id"].rsplit("_", 1)[0], []
        ).append(entry["holds"])
    singletons = [k for k, v in derived.items() if len(v) == 1]
    assert len(derived) == 13, "the naming rule is expected to mis-group"
    assert len(singletons) == 6, singletons

    # The explicit field is what makes it ten again.
    real = {entry["pair_id"] for entry in published["claims"]}
    assert len(real) == 10


def test_an_explicit_pair_id_wins_and_absence_falls_back() -> None:
    """Both halves, because the tone corpus depends on the fallback."""
    speech = probe.Claim(
        claim_id="crate_seventeen",
        clip_id="crate",
        family="confusable_number",
        criterion="x",
        holds=True,
        because="y",
        explicit_pair_id="crate_number",
    )
    assert speech.pair_id == "crate_number"
    assert speech.to_dict()["pair_id"] == "crate_number"

    tone = probe.Claim(
        claim_id="timing_true",
        clip_id="tone_stops_early",
        family="timing",
        criterion="x",
        holds=True,
        because="y",
    )
    assert tone.pair_id == "timing"


def test_audio_that_is_not_the_pinned_audio_is_refused(tmp_path: Path) -> None:
    """The failure this guards against is mundane and produces a real number.

    An artifact from a different run, a partial download, a clip regenerated
    by a newer eSpeak: each yields a folder of plausible WAVs and an accuracy
    that cannot be attributed to any published set.
    """
    manifest_path, clip_dir = _speech_fixture(tmp_path)
    target = clip_dir / "clip0.sent.wav"
    target.write_bytes(target.read_bytes() + b"\x00\x00")

    with pytest.raises(ValueError, match="Refusing to measure audio"):
        probe.load_speech_corpus(manifest_path, clip_dir)


def test_a_missing_clip_says_where_to_get_it(tmp_path: Path) -> None:
    """The clips are deliberately not committed, so 'missing' is the normal
    first experience of this flag and the message has to be actionable."""
    manifest_path, clip_dir = _speech_fixture(tmp_path)
    (clip_dir / "clip0.sent.wav").unlink()

    with pytest.raises(FileNotFoundError, match="speech-verification-set"):
        probe.load_speech_corpus(manifest_path, clip_dir)


def test_the_delivered_file_is_the_one_loaded(tmp_path: Path) -> None:
    """``sent``, not ``source``.

    eSpeak writes 22050 Hz and the grading path delivers 16 kHz. Loading the
    file the model never hears would be a digest check that passes while
    describing the wrong bytes -- the exact defect the two digests exist to
    make visible.
    """
    manifest_path, clip_dir = _speech_fixture(tmp_path)
    corpus = probe.load_speech_corpus(manifest_path, clip_dir)
    for clip in corpus.clips:
        assert clip.path.name.endswith(".sent.wav")
        assert clip.sample_rate_hz == AUDIO_SAMPLE_RATE_HZ


def test_an_unbalanced_speech_set_is_refused(tmp_path: Path) -> None:
    """Balance is what makes 50% the chance line.

    A set that had drifted would still produce an accuracy, and it would be
    compared against a baseline nobody recomputed.
    """
    manifest_path, clip_dir = _speech_fixture(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["claims"][1]["holds"] = True
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="not balanced"):
        probe.load_speech_corpus(manifest_path, clip_dir)


def test_a_pair_that_does_not_disagree_with_itself_is_refused(
    tmp_path: Path,
) -> None:
    """Balanced overall and still broken.

    The pair is the unit the permutation test shuffles within. Two clips, one
    all-true and one all-false, is ten-true-of-twenty at the corpus level --
    the balance check passes -- while every within-pair swap is a no-op. The
    corpus would be graded against a null distribution with no spread in it.
    """
    manifest_path, clip_dir = _speech_fixture(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    # clip0: both true. clip1: both false. Still 2 of 4.
    manifest["claims"][1]["holds"] = True
    manifest["claims"][2]["holds"] = False
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="not one true and one false"):
        probe.load_speech_corpus(manifest_path, clip_dir)


def test_a_claim_about_a_clip_that_is_not_pinned_is_refused(
    tmp_path: Path,
) -> None:
    """Otherwise the run would fail at the call, having already spent."""
    manifest_path, clip_dir = _speech_fixture(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["claims"][0]["clip_id"] = "not_a_clip"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="does not pin"):
        probe.load_speech_corpus(manifest_path, clip_dir)


def test_the_published_set_loads_when_its_clips_are_present(
    tmp_path: Path,
) -> None:
    """The committed manifest has to be loadable by the thing that reads it.

    The clips are not committed, so this reconstructs the parts that do not
    need audio and checks the corpus-level shape the pre-registration counted
    on: ten clips, twenty claims, ten pairs, balanced.
    """
    published = json.loads(PUBLISHED_SPEECH_MANIFEST.read_text(encoding="utf-8"))
    assert len(published["clips"]) == 10
    assert len(published["claims"]) == 20
    assert sum(1 for c in published["claims"] if c["holds"]) == 10
    by_pair: dict[str, list[bool]] = {}
    for entry in published["claims"]:
        by_pair.setdefault(entry["pair_id"], []).append(entry["holds"])
    assert len(by_pair) == 10
    assert all(sorted(v) == [False, True] for v in by_pair.values())


def test_a_prerendered_corpus_is_not_re_rendered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Re-deriving the digests here would pin what was downloaded.

    The point of the manifest is that the digest was published by the build.
    If the runner recomputed it, a corrupted download would be reported as its
    own pin and the check would be circular.
    """
    manifest_path, clip_dir = _speech_fixture(tmp_path)
    corpus = probe.load_speech_corpus(manifest_path, clip_dir)

    def _explode(*_args: object, **_kwargs: object) -> str:
        raise AssertionError("the tone renderer must not run for speech")

    monkeypatch.setattr(probe, "render_clip", _explode)
    perception = probe.AudioPerception(
        client=probe.TruthfulStub(corpus.claims),
        deployment="gpt-audio-1.5",
        call_cap=AUDIO_CALL_CAP,
        trim_seconds=AUDIO_TRIM_SECONDS,
    )
    result = probe.run_measurement(
        perception=perception,
        clip_dir=tmp_path / "unused",
        repeats=1,
        claims=corpus.claims,
        prerendered=corpus,
    )
    assert result["clip_sha256"] == corpus.digests
    assert len(result["calls"]) == len(corpus.claims)


def test_the_report_describes_the_corpus_that_ran(tmp_path: Path) -> None:
    """Reporting the tone corpus's counts beside a speech run's calls would be
    a mislabel of exactly the kind this file exists to stop."""
    manifest_path, clip_dir = _speech_fixture(tmp_path, clips=3)
    corpus = probe.load_speech_corpus(manifest_path, clip_dir)
    perception = probe.AudioPerception(
        client=probe.TruthfulStub(corpus.claims),
        deployment="gpt-audio-1.5",
        call_cap=AUDIO_CALL_CAP,
        trim_seconds=AUDIO_TRIM_SECONDS,
    )
    result = probe.run_measurement(
        perception=perception,
        clip_dir=tmp_path / "unused",
        repeats=1,
        claims=corpus.claims,
        prerendered=corpus,
    )
    report = probe.build_report(
        identity=probe.pinned_identity(),
        measured=False,
        repeats=1,
        result=result,
        speech=corpus,
    )
    assert report["corpus"] == "speech"
    assert report["pins"]["clips"] == 3
    assert report["pins"]["claims"] == 6
    assert report["pins"]["clips"] != len(probe.CLIPS)
    assert [c["clip_id"] for c in report["clips"]] == [
        c.clip_id for c in corpus.clips
    ]
    assert "hears words" in report["what_this_measures"]
    # The asymmetry is a field, not a caveat in a document nobody opens.
    assert report["speech_set"]["limits"]["reading"]
    json.dumps(report)


def test_the_expected_token_count_is_written_down_before_the_run(
    tmp_path: Path,
) -> None:
    """A corpus that never reached the model produces a plausible accuracy.

    The only cheap way to notice is a usage figure that is nowhere near what
    the audio should have cost, and that comparison needs a number recorded
    beforehand rather than reconstructed afterwards.
    """
    manifest_path, clip_dir = _speech_fixture(tmp_path, clips=2)
    corpus = probe.load_speech_corpus(manifest_path, clip_dir)
    perception = probe.AudioPerception(
        client=probe.TruthfulStub(corpus.claims),
        deployment="gpt-audio-1.5",
        call_cap=AUDIO_CALL_CAP,
        trim_seconds=AUDIO_TRIM_SECONDS,
    )
    result = probe.run_measurement(
        perception=perception,
        clip_dir=tmp_path / "unused",
        repeats=3,
        claims=corpus.claims,
        prerendered=corpus,
    )
    report = probe.build_report(
        identity=probe.pinned_identity(),
        measured=False,
        repeats=3,
        result=result,
        speech=corpus,
    )
    assert report["speech_set"]["expected_audio_tokens"] == round(
        probe.AUDIO_TOKENS_PER_SECOND * corpus.total_seconds * 3
    )


def test_the_published_set_predicts_the_pre_registered_token_count() -> None:
    """330 states ~937 tokens for three repeats. The code has to agree.

    Two places carrying the same number is how a stop rule quietly stops
    matching the run it governs.
    """
    published = json.loads(PUBLISHED_SPEECH_MANIFEST.read_text(encoding="utf-8"))
    seconds = round(sum(c["sent"]["seconds"] for c in published["clips"]), 4)
    assert seconds == 31.2350
    assert round(probe.AUDIO_TOKENS_PER_SECOND * seconds * 3) == 937


def test_the_speech_flags_travel_together() -> None:
    """A manifest with no clips is a run that cannot start, not one that
    quietly falls back to tones."""
    with pytest.raises(SystemExit):
        probe.main(["--dry-run", "--speech-set", "x.json"])
    with pytest.raises(SystemExit):
        probe.main(["--dry-run", "--speech-clips", "somewhere"])


def test_the_speech_run_refuses_a_second_prompt_arm(tmp_path: Path) -> None:
    """330 pre-registers one arm. Two questions in one run is what left 328
    unable to answer either of them."""
    manifest_path, clip_dir = _speech_fixture(tmp_path)
    with pytest.raises(SystemExit):
        probe.main([
            "--dry-run", "--quiet",
            "--speech-set", str(manifest_path),
            "--speech-clips", str(clip_dir),
            "--prompt-arm", "both",
        ])


def test_a_speech_set_that_cannot_be_loaded_exits_three_not_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Same exit code as an unreadable identity, for the same reason: a run
    that cannot say what it sent has nothing to report."""
    manifest_path, clip_dir = _speech_fixture(tmp_path)
    (clip_dir / "clip0.sent.wav").unlink()
    assert probe.main([
        "--dry-run", "--quiet",
        "--speech-set", str(manifest_path),
        "--speech-clips", str(clip_dir),
    ]) == 3
    assert "::error::" in capsys.readouterr().err
