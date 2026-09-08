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

import base64
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
    AUDIO_RESPONSE_CONTRACT,
    AUDIO_SAMPLE_RATE_HZ,
    AUDIO_TRIM_SECONDS,
    AUDIO_VERDICT_VOCABULARY,
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
    and several places in it say how big the corpus is: the header comment, the
    ``repeats`` input description a dispatcher reads, and the approval record.
    None of them can read ``CLAIMS`` -- the gate job has no checkout, and a
    comment cannot compute -- so all of them are restatements.

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

    # The approval record. Both of its numbers come out of a shell `case` now,
    # because 337 narrows the manifest to five criteria and one literal cannot
    # be right for both sizes. What is pinned here is the branch that covers
    # this corpus -- the fallback -- plus the fact that the call count is
    # computed from the criteria count rather than restated beside it. The
    # narrowed branch is pinned against 337's own document, further down.
    fallback = re.search(
        r"\*\)\n\s*CRITERIA=(\d+); TRUE_CRITERIA=(\d+); FALSE_CRITERIA=(\d+)",
        text,
    )
    assert fallback, "the approval record no longer states the criteria count"
    assert int(fallback.group(1)) == claims
    assert int(fallback.group(2)) == true_claims
    assert int(fallback.group(3)) == false_claims

    assert re.search(r"calls\s+= \$\(\(CRITERIA \* PROBE_REPEATS\)\)", text), (
        "the call count no longer follows the criteria count"
    )
    # A literal put back alongside the variable would survive review, because
    # the line still reads correctly on a default dispatch -- and would be
    # wrong only on the one corpus that is a different size.
    assert not re.search(r"calls\s+= \$\(\(\d+ \* PROBE_REPEATS\)\)", text)

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


def test_whether_the_audio_arrived_is_printed_above_the_accuracy() -> None:
    """324's failure survives every rule this file has so far.

    §3's stop rule fires on audio metered at a real ``0``. It does not fire on
    a request that carried no audio part at all, and not on a clip that is not
    the pinned length -- ``WireClient`` records both and deliberately does not
    raise, because a diagnostic that crashes on the defect it is looking for
    cannot describe it. So the run completes all sixty calls and prints an
    accuracy, with ``calls_carrying_audio: 0`` in a section sixty lines below.

    §2 puts these checks before the accuracy for that reason. The detail can
    stay where it is; the line that says whether to read on cannot.
    """
    summary = _step("measure", "Summarise")["run"]
    banner = summary.index("Read this before the accuracy below")
    arrived = summary.index("| audio actually sent |")
    accuracy = summary.index("| accuracy (answered calls) |")
    assert banner < accuracy, "the warning prints under the number it is about"
    assert arrived < accuracy, "the arrival count prints under the accuracy"

    # Both conditions, not just the missing-audio one: a clip of the wrong
    # length is audio that arrived and was not the pinned audio.
    assert "calls_carrying_audio" in summary
    assert "clips_whose_sent_duration_differs" in summary[:accuracy]


def _summarise_body(job: str = "measure") -> str:
    """The python a Summarise step actually runs, on its own.

    Extracted rather than re-implemented: a copy in this file would drift and
    then pass while the workflow failed, which is the whole failure mode.
    """
    lines = _step(job, "Summarise")["run"].splitlines()
    start = next(
        i for i, line in enumerate(lines) if line.startswith("python - <<")
    )
    end = next(i for i in range(start + 1, len(lines)) if lines[i] == "PY")
    return "\n".join(lines[start + 1 : end])


def _stamped_identity() -> dict:
    """The pins a real run writes, not the ones ``pinned_identity`` returns.

    ``main`` reads the config into an identity and then *stamps the grader
    fingerprint onto it*, because after the run that string stops being a
    promise and becomes the record of which grader produced the numbers. Every
    report this script has ever written therefore carries
    ``pins.grader_source_sha256``; a report built straight off
    ``pinned_identity()`` does not, and is a shape nothing emits.

    Which mattered the moment the summary started printing the field: four
    tests handed it a report no run could produce and got a ``KeyError`` that
    said nothing about the summary. Fixtures that are the wrong shape do not
    fail honestly -- they fail somewhere else.
    """
    return {
        **probe.pinned_identity(),
        "grader_source_sha256": probe.grader_source_hash(),
    }


def _render_summary(
    job: str,
    report_name: str,
    report: dict,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> str:
    """Run a Summarise step over a report and return what it printed.

    Executing it is the point. A grep over the workflow text cannot see a
    ``TypeError``, and every defect this file has caught in the summary was a
    line that rendered fine on the shape its author had in mind.
    """
    workspace = tmp_path / f"ws{len(list(tmp_path.iterdir()))}"
    workspace.mkdir()
    (workspace / report_name).write_text(json.dumps(report), encoding="utf-8")
    monkeypatch.setenv("GITHUB_WORKSPACE", str(workspace))
    exec(  # noqa: S102 - running the workflow's own code is the point
        compile(_summarise_body(job), f"<{job} Summarise>", "exec"),
        {"__name__": "__main__"},
    )
    return capsys.readouterr().out


def _render_paid_summary(
    report: dict,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> str:
    return _render_summary(
        "measure",
        "audio-accuracy-measured.json",
        report,
        tmp_path,
        monkeypatch,
        capsys,
    )


def test_the_free_page_says_when_the_audio_did_not_go_out_as_pinned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """The free run exists to find for nothing what a paid dispatch would.

    §3 deliberately lets a run finish when a request carried no audio part, or
    when a clip is not its pinned length: a diagnostic that dies on the defect
    it hunts cannot describe that defect. The paid summary therefore banners
    both conditions above the accuracy. The free page banners neither -- it
    printed the arrival count and the digest list and stopped there.

    That page is what a dispatcher reads *before* deciding to buy. When defect
    1 was live -- durations compared against the tone corpus, so all ten speech
    clips were off their pinned length -- this page said "60/60 requests
    carried audio; clips sending more than one digest: `[]`" and nothing else.
    It read clean. The defect was found by reading a JSON file by hand.

    Executed, not grepped: the free step is python too.
    """
    manifest_path, clip_dir = _speech_fixture(tmp_path, clips=5)
    out = tmp_path / "dry.json"
    assert probe.main([
        "--dry-run", "--quiet", "--repeats", "1",
        "--speech-set", str(manifest_path),
        "--speech-clips", str(clip_dir),
        "--out", str(out),
    ]) == 0
    healthy = json.loads(out.read_text(encoding="utf-8"))
    delivery = healthy["delivery"]
    assert delivery["calls_carrying_audio"] == delivery["calls_inspected"]
    assert delivery["clips_whose_sent_duration_differs"] == []

    def _page(report: dict) -> str:
        return _render_summary(
            "dry-run", "audio-accuracy-dry-run.json", report,
            tmp_path, monkeypatch, capsys,
        )

    # A healthy rehearsal must stay quiet. A warning on every run is decoration.
    assert "Do not dispatch" not in _page(healthy)

    wrong_length = json.loads(json.dumps(healthy))
    named = sorted(delivery["digests_per_clip"])[:1]
    wrong_length["delivery"]["clips_whose_sent_duration_differs"] = named
    printed = _page(wrong_length)
    assert "Do not dispatch" in printed, (
        "the free page is silent about a clip that is not the pinned clip, so "
        "the paid dispatch is what finds out"
    )
    assert named[0] in printed, "it does not say which clip"

    no_audio = json.loads(json.dumps(healthy))
    no_audio["delivery"]["calls_carrying_audio"] = 0
    assert "Do not dispatch" in _page(no_audio)


def test_the_threshold_line_is_about_the_test_the_document_calls_primary() -> None:
    """The two tests have different floors and only one of them is primary.

    The permutation's floor is fixed by the pair count -- ten pairs, 1/1024,
    forever. The binomial's is 1/2**n and it *moves*: every hedged majority
    leaves n, and at n = 4 the floor is 0.0625, so the pre-registered primary
    cannot reach 0.05 however well the model does. A threshold line computed
    from the permutation announces 0.05, 0.01 and 0.001 on exactly that run.
    """
    summary = _step("measure", "Summarise")["run"]
    assert 'binom_floor = binom["smallest_attainable_p"]' in summary
    assert (
        "reachable = [t for t in (0.05, 0.01, 0.001) if binom_floor < t]"
        in summary
    ), "the thresholds are computed from the secondary test's floor"
    assert "Thresholds the **pre-registered primary** can reach" in summary
    # §4 promises n and the reason it shrank appear together.
    assert "hedged_majorities_excluded" in summary
    assert "claims_with_a_majority" in summary


def test_the_family_table_says_its_rows_are_calls() -> None:
    """"6 answered, 6 correct" for a two-claim family reads as six items.

    It is two claims asked three times, about the same two clips. §4 already
    forbids treating repeats as independent trials -- this is the one table
    where the counts invite it, so the table says so itself rather than
    relying on a reader having got as far as §4.
    """
    summary = _step("measure", "Summarise")["run"]
    section = summary.index("### By family")
    caption = summary[section:]
    assert "**Calls, not claims.**" in caption
    # Derived from the run's own repeat count: a hard-coded "three" is wrong
    # on any dispatch that changes it, and this file has published a
    # hard-coded corpus count that went stale once already.
    assert 'int(report["pins"]["repeats"])' in caption
    assert "two coin flips" in caption


def test_the_summary_says_something_when_there_was_no_report(
    tmp_path: Path
) -> None:
    """The step is ``if: always()``, so it also runs on the runs that stopped.

    It began with ``test -f report || exit 0``: no report, no page, under a red
    job. That silence was already wrong -- the failure lands in an annotation,
    which is the one place this repository has learned people do not look --
    and this PR adds another way to reach it, since the grader-pin check
    refuses before writing anything.

    It matters more than tidiness because the two ways to get here differ by
    money. A pre-flight refusal happens before the first call and costs
    nothing; a failure after the calls started bought them and still writes no
    report, because the report is written at the end. An empty page reads like
    the first one.

    Executed, not grepped: the guard is shell, and shell that is never run is
    a suggestion.
    """
    prologue = _step("measure", "Summarise")["run"].split("python - <<", 1)[0]
    workspace = tmp_path / "ws"
    workspace.mkdir()
    summary = tmp_path / "summary.md"

    def _run() -> str:
        summary.write_text("", encoding="utf-8")
        done = subprocess.run(
            ["bash", "-c", prologue],
            env={
                **os.environ,
                "GITHUB_WORKSPACE": str(workspace),
                "GITHUB_STEP_SUMMARY": str(summary),
            },
            capture_output=True,
            text=True,
        )
        assert done.returncode == 0, done.stderr
        return summary.read_text(encoding="utf-8")

    printed = _run()
    assert printed.strip(), (
        "no report and no page either: the run that most needs explaining is "
        "the one that gets none"
    )
    assert "annotation" in printed, (
        "it has to send the reader where the reason actually is"
    )
    assert "nothing was bought" in printed and "were billed" in printed, (
        "both ways of getting here have to be named; they differ by money, "
        "and an empty page reads like the free one"
    )
    assert "%" not in printed, (
        "no report means no figures; a page here that carries one is quoting "
        "something it does not have"
    )

    (workspace / "audio-accuracy-measured.json").write_text(
        "{}", encoding="utf-8"
    )
    assert _run() == "", (
        "with a report present the prologue must stay out of the way and let "
        "the real summary write the page"
    )


def test_the_paid_summary_survives_a_run_where_nothing_answered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """328's arm answered nothing usable, and that is a pre-registered outcome.

    §3's second stop rule exists to produce this run on purpose: zero usable
    verdicts in the first ten calls, stop, report. So the summary has to
    render it -- and it did not. With nothing answered both tests return a
    null floor, the page printed "the floor is 1/0" and then died comparing
    ``None`` to 0.05, taking the delivery, cost and family sections with it.
    The one run whose summary has to explain itself was the one that had no
    summary.

    Executed rather than grepped: only running it catches a TypeError.
    """
    manifest_path, clip_dir = _speech_fixture(tmp_path, clips=5)
    corpus = probe.load_speech_corpus(manifest_path, clip_dir)

    class _NeverAnswers:
        def reset(self) -> None:
            return None

        def judge(self, **_kwargs: object) -> probe.AudioVerdict:
            return probe.AudioVerdict(
                verdict="judge_error",
                partial_score=0.0,
                evidence="",
                confidence=0.0,
                reasoning="",
                judge_error="format_error:unparseable",
            )

    result = probe.run_measurement(
        perception=_NeverAnswers(),
        clip_dir=tmp_path / "unused",
        repeats=3,
        claims=corpus.claims,
        prerendered=corpus,
    )
    report = probe.build_report(
        identity=_stamped_identity(),
        measured=True,
        repeats=3,
        result=result,
        speech=corpus,
    )
    assert report["accuracy"]["overall"]["answered"] == 0
    assert report["accuracy"]["permutation"]["smallest_attainable_p"] is None

    printed = _render_paid_summary(report, tmp_path, monkeypatch, capsys)
    assert "No verdict was usable" in printed
    assert "1/0" not in printed, "a floor of one-over-zero is not a floor"
    # Everything downstream of the p-values used to be lost with the crash.
    assert "### Cost" in printed
    assert "### By family" in printed
    # And the pair banner must not fire here: nothing was resolved, so the
    # judge did not "give both sides the same verdict" -- it gave none.
    assert "separated nothing" not in printed


def test_a_judge_that_separated_nothing_says_so_above_the_accuracy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """A judge answering `pass` to everything scores 50%, and 50% reads as close.

    330 §4 names this by hand -- "10쌍 전부 pass여도 정확도가 50%로 나온다.
    정확도만 보면 아깝게 못 넘었다로 읽히는 자리다" -- because on a balanced
    corpus the accuracy cannot tell a listener from a coin. The summary had
    the right words for it and printed them in the subjunctive, under the
    table: "J = 0 *would* mean the verdict does not depend on the audio." On
    the run where it is the indicative, that paragraph reads as boilerplate.

    So the observation goes above the number it qualifies, next to the
    arrival banner, and it fires only on the shape it describes.
    """
    manifest_path, clip_dir = _speech_fixture(tmp_path, clips=5)
    corpus = probe.load_speech_corpus(manifest_path, clip_dir)
    by_criterion = {claim.criterion: claim for claim in corpus.claims}

    def _run(verdict_for) -> dict:
        class _Judge:
            def reset(self) -> None:
                return None

            def judge(self, *, criterion: str, **_kwargs: object) -> probe.AudioVerdict:
                return probe.AudioVerdict(
                    verdict=verdict_for(by_criterion[criterion]),
                    partial_score=0.0,
                    evidence="",
                    confidence=0.9,
                    reasoning="",
                )

        return probe.build_report(
            identity=_stamped_identity(),
            measured=True,
            repeats=3,
            result=probe.run_measurement(
                perception=_Judge(),
                clip_dir=tmp_path / "unused",
                repeats=3,
                claims=corpus.claims,
                prerendered=corpus,
            ),
            speech=corpus,
        )

    everything_passes = _run(lambda _claim: "pass")
    consistency = everything_passes["accuracy"]["pair_consistency"]
    assert consistency["answered_differently"] == 0
    assert consistency["answered_identically"] == consistency["pairs"]
    assert everything_passes["accuracy"]["overall"]["accuracy"] == 0.5

    printed = _render_paid_summary(everything_passes, tmp_path, monkeypatch, capsys)
    banner = printed.index("separated nothing")
    accuracy = printed.index("| accuracy (answered calls) |")
    assert banner < accuracy, "the warning prints under the number it is about"
    assert '`{"pass": 5}`' in printed, "which verdict it gave to everything"

    # The half that makes the banner worth having: it stays quiet when the
    # judge did separate the pairs. A warning on every run is decoration.
    heard = _run(lambda claim: "pass" if claim.holds else "fail")
    assert heard["accuracy"]["pair_consistency"]["answered_differently"] == 5
    assert "separated nothing" not in _render_paid_summary(
        heard, tmp_path, monkeypatch, capsys
    )


def test_the_arrival_banner_fires_on_the_shape_it_exists_for(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """The line 330 §3 calls the fix for 324 had never been rendered.

    The test above it checks that the banner's *text* sits earlier in the
    workflow source than the accuracy row. That is an ordering check over a
    string, and it holds whether or not the condition beneath it is right --
    the branch that prints the banner has only ever run on healthy reports,
    where it prints nothing.

    Which is the wrong way round. The banner exists for the unhealthy run:
    ``WireClient`` deliberately does not raise when a request carried no audio
    or a clip was the wrong length, so that shape completes all sixty calls and
    prints a headline number. If the banner throws there, the summary dies on
    the one run it was added for -- which is what the null-floor crash did, on
    the one run §3's second stop rule exists to produce.

    So: render all three shapes and read what came out.
    """
    manifest_path, clip_dir = _speech_fixture(tmp_path, clips=5)
    out = tmp_path / "healthy.json"
    assert probe.main([
        "--dry-run", "--quiet", "--repeats", "3",
        "--speech-set", str(manifest_path),
        "--speech-clips", str(clip_dir),
        "--out", str(out),
    ]) == 0
    healthy = json.loads(out.read_text(encoding="utf-8"))

    delivered = healthy["delivery"]
    assert delivered["calls_carrying_audio"] == delivered["calls_inspected"]
    assert delivered["clips_whose_sent_duration_differs"] == []

    printed = _render_paid_summary(healthy, tmp_path, monkeypatch, capsys)
    assert "Read this before the accuracy below" not in printed, (
        "a banner that prints on a clean run is decoration"
    )
    assert "### Did the audio arrive" in printed, "the detail section still runs"

    def _mutated(**delivery: object) -> str:
        report = json.loads(json.dumps(healthy))
        report["delivery"].update(delivery)
        return _render_paid_summary(report, tmp_path, monkeypatch, capsys)

    # 324: the calls that carried no audio at all. Not caught by §3's stop
    # rule, which fires on audio metered at a real 0 rather than absent.
    inspected = delivered["calls_inspected"]
    printed = _mutated(calls_carrying_audio=0, calls_without_audio=list(range(inspected)))
    banner = printed.index("Read this before the accuracy below")
    accuracy = printed.index("| accuracy (answered calls) |")
    assert banner < accuracy, "the warning prints under the number it is about"
    assert f"{inspected} of {inspected} requests carried no audio" in printed
    assert "it is not this model hearing these clips" in printed

    # The other half of the condition: audio arrived, and was not the pinned
    # audio. The accuracy is about a corpus §2 did not fingerprint.
    printed = _mutated(clips_whose_sent_duration_differs=["boxes", "crate"])
    assert printed.index("Read this before the accuracy below") < printed.index(
        "| accuracy (answered calls) |"
    )
    assert "2 clip(s) were not the pinned length" in printed
    assert "requests carried no audio" not in printed, (
        "it should name the fault it found, not both"
    )


# --------------------------------------------------------------------------
# The lines that first ran against money
#
# `331` §10 lists five branches of the paid summary that no test executed.
# Four of them printed for the first time during run 34038371185 -- the paid
# one -- and the fifth prints only when a comparison ran. A branch whose only
# exercising input is the purchase is a branch that gets debugged with the
# receipt in hand, and every one of these is on the page a reader uses to
# decide whether the number above it means anything.
#
# Rendered, not grepped, for the reason `_render_summary` gives: a grep over
# the workflow text cannot see a KeyError, and `test_the_paid_summary_names_
# the_arm_its_table_describes` above is exactly such a grep -- it proves the
# sentence is in the file and not that the branch holding it ever runs.
# --------------------------------------------------------------------------


def _tones_dry_run(tmp_path: Path, *, arm: str = "production") -> dict:
    """A real report off the tone corpus, through the script's own CLI."""
    out = tmp_path / f"tones-{arm}.json"
    assert probe.main([
        "--dry-run", "--quiet", "--repeats", "1",
        "--prompt-arm", arm,
        "--out", str(out),
    ]) == 0
    return json.loads(out.read_text(encoding="utf-8"))


def test_the_paid_summary_prints_the_grader_it_ran_under(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """`330` §2 pins a grader fingerprint; the page never showed one.

    The run computes it, ``--expect-grader-pin`` refuses to start when it
    disagrees with the pre-registration, and the value has sat in
    ``pins.grader_source_sha256`` of every report since. None of that reaches
    the person reading the summary: the header named the model, the corpus and
    the call count, and stopped. So "the grader was the pre-registered one"
    was checkable only by downloading the JSON -- which is the position the
    delivery evidence was in before §2 moved it up.

    Whole, not abbreviated: the comparison it exists for is against a
    64-character constant in a table.
    """
    report = _tones_dry_run(tmp_path)
    fingerprint = report["pins"]["grader_source_sha256"]
    assert re.fullmatch(r"[0-9a-f]{64}", fingerprint), fingerprint

    printed = _render_paid_summary(report, tmp_path, monkeypatch, capsys)
    assert fingerprint in printed, "the summary still does not say which grader"
    assert printed.index(fingerprint) < printed.index(
        "| accuracy (answered calls) |"
    ), "provenance under the number it qualifies is provenance nobody reads"

    # A different fingerprint has to print differently, or the line is a
    # constant that happens to match today's checkout.
    moved = json.loads(json.dumps(report))
    moved["pins"]["grader_source_sha256"] = "b" * 64
    assert "b" * 64 in _render_paid_summary(
        moved, tmp_path, monkeypatch, capsys
    )


def test_the_arrival_row_carries_the_counts_it_was_handed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """`331` §5's first row, executed.

    The row above the accuracy that says how many requests carried audio. The
    banner beside it is covered by the arrival-banner test above, but the
    banner only fires when something is wrong; this row prints on every run,
    including the clean one, and nothing asserted the two numbers were the
    right way round.
    """
    report = _tones_dry_run(tmp_path)
    inspected = report["delivery"]["calls_inspected"]
    printed = _render_paid_summary(report, tmp_path, monkeypatch, capsys)
    assert f"| audio actually sent | **{inspected} / {inspected}** requests |" in printed

    partial = json.loads(json.dumps(report))
    partial["delivery"]["calls_carrying_audio"] = 3
    printed = _render_paid_summary(partial, tmp_path, monkeypatch, capsys)
    assert f"| audio actually sent | **3 / {inspected}** requests |" in printed, (
        "carried and inspected must not be swapped, and neither may be the "
        "other's value"
    )


class _NonAnswersOfEveryKind:
    """Three different non-answers, in known and unequal numbers.

    The markers are the ones ``core.perception.audio`` actually writes, so
    ``unanswered_kind`` reads them rather than being told. Unequal on purpose:
    at 10/10/10 a page that printed the three rows in the wrong order, or read
    one key three times, would still look right.
    """

    def __init__(self, *, declined: int, read_failures: int) -> None:
        self._declined = declined
        self._read_failures = read_failures
        self._seen = 0

    def reset(self) -> None:
        return None

    def judge(self, **_kwargs: object) -> probe.AudioVerdict:
        self._seen += 1
        if self._seen <= self._declined:
            marker = "sub_judge_declined"
        elif self._seen <= self._declined + self._read_failures:
            marker = "format_error:unparseable_json"
        else:
            marker = "provider_error:TimeoutError"
        return probe.AudioVerdict(
            verdict="judge_error",
            partial_score=0.0,
            evidence="",
            confidence=0.0,
            reasoning="",
            judge_error=marker,
        )


def test_the_three_kinds_of_non_answer_print_under_their_own_labels(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """`331` §10.1. The split exists because run 34008840627 did not have it.

    That run published all 52 of its non-answers as ``provider_error:
    JSONDecodeError`` and so could not tell an outage from a prompt defect --
    opposite problems, one fixed by waiting and one by editing text. The
    counting was fixed and tested; the three rows that *show* it were not, and
    they printed for the first time on the paid run.

    Distinct counts are the point. The failure this catches is not a crash,
    it is 5 and 16 appearing under each other's labels, which reads as an
    outage when it was a prompt.
    """
    manifest_path, clip_dir = _speech_fixture(tmp_path, clips=5)
    corpus = probe.load_speech_corpus(manifest_path, clip_dir)
    result = probe.run_measurement(
        perception=_NonAnswersOfEveryKind(declined=5, read_failures=9),
        clip_dir=tmp_path / "unused",
        repeats=3,
        claims=corpus.claims,
        prerendered=corpus,
    )
    report = probe.build_report(
        identity=_stamped_identity(),
        measured=True,
        repeats=3,
        result=result,
        speech=corpus,
    )
    overall = report["accuracy"]["overall"]
    assert overall["unanswered"] == 30
    assert overall["unanswered_by_kind"] == {
        "declined_to_judge": 5,
        "read_failure": 9,
        "provider_failure": 16,
    }

    printed = _render_paid_summary(report, tmp_path, monkeypatch, capsys)
    assert "| unanswered (`judge_error`) | 30 |" in printed
    assert "| &nbsp;&nbsp;· model declined to judge | 5 |" in printed
    assert "| &nbsp;&nbsp;· reply broke the response contract | 9 |" in printed
    assert "| &nbsp;&nbsp;· the call itself failed | 16 |" in printed


def test_two_arms_get_the_note_and_the_paired_table_one_arm_must_not(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """`331` §10.2, both halves: the multi-arm note and the comparison block.

    Neither has ever rendered under a test. The pre-registered speech run is
    single-arm, so the branches sat behind a condition every rehearsal in this
    file makes false -- and the note exists precisely to stop a reader taking
    the single table below it for the whole run.
    """
    one = _tones_dry_run(tmp_path, arm="production")
    two = _tones_dry_run(tmp_path, arm="both")
    assert one["pins"]["prompt_arms"] == ["production"]
    assert two["pins"]["prompt_arms"] == ["production", "observation"]
    assert "arm_comparison" not in one and two["arm_comparison"]

    single = _render_paid_summary(one, tmp_path, monkeypatch, capsys)
    assert "production arm alone" not in single, (
        "a note about which of two arms this is, on a run that had one arm"
    )
    assert "### Prompt arms, paired" not in single

    paired = _render_paid_summary(two, tmp_path, monkeypatch, capsys)
    assert "production arm alone" in paired
    assert paired.index("production arm alone") < paired.index(
        "| accuracy (answered calls) |"
    ), "the note has to reach the reader before the table it qualifies"

    # The comparison block itself: every row of it, because it is the section
    # a prompt A/B is bought for.
    assert "### Prompt arms, paired" in paired
    assert f"Pairing is on (criterion, repeat): {two['arm_comparison']['pairs']} pairs" in paired
    for name in ("production", "observation"):
        side = two["arm_comparison"][name]
        assert f"| {name} | " in paired
        assert f"{side['correct']}/{side['attempts']} |" in paired
    discordant = two["arm_comparison"]["discordant"]
    assert f"both `{discordant['both_correct']}`" in paired
    assert "exact two-sided McNemar p" in paired
    assert two["arm_comparison"]["reading"] in paired
    # And the per-arm non-answer split under it, which is the other half of
    # "one arm may decline the hard criteria and score better on what is left".
    assert "| | declined | read failure | provider failure |" in paired


def test_a_clip_that_sent_two_digests_banners_above_the_comparison(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """`331` §10.2's third branch. It only fires when the arms heard different bytes.

    Which is the one condition that makes a prompt comparison meaningless: two
    digests for one clip means the two arms were not asked about the same
    audio, so whatever the table below shows, it is not the prompts differing.
    Unreachable in a rehearsal -- the stub re-encodes deterministically -- so
    it is reached here by saying so in the report.
    """
    report = _tones_dry_run(tmp_path, arm="both")
    clean = _render_paid_summary(report, tmp_path, monkeypatch, capsys)
    assert "A clip sent more than one digest" not in clean, (
        "a banner that fires on a run where every clip sent one digest"
    )

    split = json.loads(json.dumps(report))
    split["delivery"]["clips_with_more_than_one_digest"] = ["three_beeps"]
    printed = _render_paid_summary(split, tmp_path, monkeypatch, capsys)
    assert "**A clip sent more than one digest.**" in printed
    assert "the comparison below is not a prompt comparison" in printed
    assert printed.index("A clip sent more than one digest") < printed.index(
        "### Prompt arms, paired"
    ), "the reason not to read the table has to arrive before the table"


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


def _classify_error(claim: probe.Claim, verdict: str) -> str:
    with pytest.raises(ValueError) as caught:
        probe.classify(claim, verdict)
    return str(caught.value)


def test_a_verdict_outside_the_contract_vocabulary_is_never_scored() -> None:
    """`331` §10.4. The scorer's ``fail`` arm was a plain ``else``.

    ``said_pass = verdict == "pass"`` is false for ``pass`` misspelt, for
    ``true``, ``false``, ``refuse`` and ``analyze_audio`` -- the four
    out-of-vocabulary strings run ``34008840627`` actually produced -- and
    every one of them then scored as a
    confident ``fail``: correct on all thirty false claims, which is the exact
    shape of the constant-``fail`` baseline `331` §4 warns about. A reply
    nobody validated would have arrived as a result nobody could tell from one.

    ``core.perception.audio`` rejects these before they reach here, which is
    why nothing has ever hit this branch and why the check is worth having:
    the two halves are one rule, and the second half is the one that would
    still be standing if the first were edited.

    The vocabulary is core's object, asserted rather than assumed -- a
    duplicated frozenset here would drift and then agree with itself.
    """
    assert probe.AUDIO_VERDICT_VOCABULARY is AUDIO_VERDICT_VOCABULARY

    claim = next(c for c in probe.CLAIMS if not c.holds)
    for verdict in sorted(AUDIO_VERDICT_VOCABULARY):
        assert probe.classify(claim, verdict) in {
            probe.OUTCOME_CORRECT,
            probe.OUTCOME_FALSE_FAIL,
            probe.OUTCOME_FALSE_PASS,
            probe.OUTCOME_HEDGED,
            probe.OUTCOME_UNANSWERED,
        }

    for verdict in ("true", "false", "refuse", "analyze_audio", "Pass", "", "FAIL"):
        with pytest.raises(ValueError) as caught:
            probe.classify(claim, verdict)
        assert "vocabulary" in str(caught.value)

    # Model output, so the message is bounded by core's own renderer rather
    # than by an f-string here: a token survives, a sentence does not.
    assert "analyze_audio" in _classify_error(claim, "analyze_audio")
    assert "<non-token>" in _classify_error(claim, "the audio was ambiguous")


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


def test_a_grader_the_document_does_not_pin_stops_the_run(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    """The pre-registration pins a grader fingerprint and nothing checked it.

    It is the hash of the grader source and config the paid run will use, and
    it is the field that decides whether the run describes the same grader the
    19.35% came off. Written by hand and never recomputed, it says whatever it
    said on the day it was typed: edit anything the hash covers --
    ``core/**.py``, ``step8_grade.py``, the schema, the requirements closure,
    the prompt template -- and the document still claims the old one, for a run
    that is no longer the run it describes. Same shape as every other defect in
    this file: the document names a safeguard, and the safeguard is a sentence.

    The check does **not** live in a unit test. What the hash covers is mostly
    files this workstream does not own, so it moves when somebody else merges
    something perfectly correct -- and an equality asserted here would turn
    that into a red build on their PR. It already did move once, which is how
    this was found.

    So it is enforced where it protects something: at dispatch, before a call
    goes out, next to the clip-digest check that works the same way. A run
    whose grader is not the pinned one stops, and stopping costs a dispatch;
    discovering it afterwards costs the run's meaning.
    """
    computed = probe.grader_source_hash()

    wrong = tmp_path / "prereg-wrong.md"
    wrong.write_text(f"| 채점기 지문 | `{'a' * 64}` |\n", encoding="utf-8")
    manifest_path, clip_dir = _speech_fixture(tmp_path, clips=2)
    args = [
        "--dry-run", "--quiet", "--repeats", "1",
        "--speech-set", str(manifest_path),
        "--speech-clips", str(clip_dir),
        "--out", str(tmp_path / "out.json"),
    ]

    assert probe.main([*args, "--expect-grader-pin", str(wrong)]) == 3
    stderr = capsys.readouterr().err
    assert "a" * 64 in stderr and computed in stderr, (
        "a refusal has to name both fingerprints, or the reader cannot tell "
        "which end moved"
    )
    assert not (tmp_path / "out.json").exists(), (
        "it stopped after writing a report, which is not stopping"
    )

    right = tmp_path / "prereg-right.md"
    right.write_text(f"| 채점기 지문 | `{computed}` |\n", encoding="utf-8")
    assert probe.main([*args, "--expect-grader-pin", str(right)]) == 0
    assert (tmp_path / "out.json").exists()


def test_the_run_records_the_grader_it_actually_used(tmp_path: Path) -> None:
    """Checking the pin is not the same as keeping it.

    After the run the fingerprint stops being a promise and becomes the record
    of which grader produced these numbers. If that record lives only in a
    markdown file somebody typed, it is the state this check exists to end.
    """
    manifest_path, clip_dir = _speech_fixture(tmp_path, clips=2)
    out = tmp_path / "out.json"
    assert probe.main([
        "--dry-run", "--quiet", "--repeats", "1",
        "--speech-set", str(manifest_path),
        "--speech-clips", str(clip_dir),
        "--out", str(out),
    ]) == 0
    pins = json.loads(out.read_text(encoding="utf-8"))["pins"]
    assert pins["grader_source_sha256"] == probe.grader_source_hash()


def test_a_document_that_pins_no_grader_is_not_a_pin(tmp_path: Path) -> None:
    """Two ways the document can fail to say which grader, both refusals.

    Neither is hypothetical: §2 is a markdown table, and tables get edited.
    Silently skipping the check when the row is missing would make deleting
    the row the way to make the check pass.
    """
    empty = tmp_path / "silent.md"
    empty.write_text("# 330\n\nno fingerprint here\n", encoding="utf-8")
    with pytest.raises(ValueError, match="states no grader fingerprint"):
        probe.grader_pin_stated_in(empty)

    two = tmp_path / "two.md"
    two.write_text(
        f"| 채점기 지문 | `{'a' * 64}` |\n| 채점기 지문 | `{'b' * 64}` |\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="2 different grader fingerprints"):
        probe.grader_pin_stated_in(two)

    real = (
        probe.REPO_ROOT / "tasks" / "rebuilding_grading_task"
        / "330-speech-diagnostic-prereg.md"
    )
    pinned = probe.grader_pin_stated_in(real)
    assert re.fullmatch(r"[0-9a-f]{64}", pinned), (
        "330 §2 no longer states a grader fingerprint the run can be held to"
    )


def test_both_jobs_hold_a_speech_run_to_the_document_it_belongs_to() -> None:
    """The gate is only a gate if the speech run goes through it.

    Including the free job. The whole reason the fingerprint check is at
    dispatch rather than in a test is that it should be discovered without
    buying anything, and that only works if ``dry_run`` carries it too.
    """
    text = (
        probe.REPO_ROOT / ".github" / "workflows" / "audio-accuracy-probe.yml"
    ).read_text(encoding="utf-8")
    # Both documents, because there are two speech runs now and each is held
    # to its own. A workflow that named only one would leave the other's
    # dispatch unpinned while still looking checked.
    for row in ("SPEECH_PREREG", "SPEECH_AB_PREREG"):
        prereg = re.search(rf"^  {row}: .*/(\S+\.md)$", text, re.MULTILINE)
        assert prereg, f"the workflow no longer names {row}"
        assert (
            probe.REPO_ROOT / "tasks" / "rebuilding_grading_task" / prereg.group(1)
        ).is_file(), f"{row} points at a file that is not in the repo"

    invocations = [
        block for block in text.split("\n\n")
        if "measure_audio_grading_accuracy.py" in block
        and "ARGS=(" in block
    ]
    assert len(invocations) == 2, (
        f"expected the free and paid measure steps, found {len(invocations)}"
    )
    for block in invocations:
        assert "--speech-set" in block
        # The condition is written the other way round now -- everything that
        # is not tones needs a speech document -- so a third speech corpus
        # cannot arrive unpinned by being absent from a list of names.
        corpus_branch = block.index('!= "tones"')
        for flag, document in (
            ("--expect-grader-pin", "$SPEECH_PREREG"),
            ("--speech-prompt-ab", "$SPEECH_AB_PREREG"),
        ):
            assert flag in block, (
                f"a speech run without {flag} is pinned to no grader; the "
                f"document just says it is"
            )
            assert block.index(flag) > corpus_branch, (
                "the pin is passed outside the speech branch, so the published "
                "tone runs would be re-gated on a document they predate"
            )
            assert document in block[block.index(flag):], (
                f"{flag} is not handed {document}, so the run would be held "
                f"to the wrong document"
            )
        # And never both at once: two documents pinning one run is the state
        # the measurer exits 2 on, and discovering that from a dispatch is
        # discovering it later than here. This was an if/else and is a `case`
        # now that there are three two-arm documents to route, so what is
        # checked is that the single-arm pin is the fallback arm and appears
        # once -- a second one anywhere would be reachable alongside a
        # document flag. Comments are dropped first; they name both flags.
        code = "\n".join(
            line for line in block.splitlines()
            if not line.lstrip().startswith("#")
        )
        assert code.count("--expect-grader-pin") == 1
        fallback = code.index("--expect-grader-pin")
        arm = code.rindex("*)", 0, fallback)
        assert ";;" in code[code.rindex("--speech-prompt-ab", 0, arm):arm], (
            "the document arms do not close before the fallback, so a run "
            "could be handed two documents"
        )


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
        identity=_stamped_identity(),
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
        identity=_stamped_identity(),
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
        identity=_stamped_identity(), measured=False, repeats=1, result=result
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


def test_the_judge_is_handed_the_criterion_and_nothing_else(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """330 §2: the model sees one line. The answer is in the same process.

    ``load_speech_corpus`` reads a manifest that carries the sentence eSpeak
    was given and the reason each claim holds -- both have to be committed for
    the set to be reproducible. So the ground truth is one attribute access
    away from the prompt for the whole run, and the failure mode is not a
    crash: a judge handed ``because`` answers every claim correctly, and the
    report says the model hears words.

    This pins the argument list rather than the prompt text because the wire
    recorder keeps only a digest of the prompt (§6 -- the prompt is not
    published), so the boundary that can be checked is this one.
    """
    manifest_path, clip_dir = _speech_fixture(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for clip in manifest["clips"]:
        clip["command"] = ["espeak-ng", "-w", "x.wav", "SENTENCE-NOT-FOR-SENDING"]
    for claim in manifest["claims"]:
        claim["because"] = "GROUND-TRUTH-NOT-FOR-SENDING"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    corpus = probe.load_speech_corpus(manifest_path, clip_dir)
    seen: list[dict[str, object]] = []

    class _Recorder:
        def reset(self) -> None:
            return None

        def judge(self, **kwargs: object) -> probe.AudioVerdict:
            seen.append(kwargs)
            return probe.AudioVerdict(
                verdict="pass",
                partial_score=0.0,
                evidence="",
                confidence=1.0,
                reasoning="",
            )

    def _explode_renderer(*_args: object, **_kwargs: object) -> str:
        raise AssertionError("the tone renderer must not run for speech")

    monkeypatch.setattr(probe, "render_clip", _explode_renderer)
    probe.run_measurement(
        perception=_Recorder(),
        clip_dir=tmp_path / "unused",
        repeats=1,
        claims=corpus.claims,
        prerendered=corpus,
    )

    assert len(seen) == len(corpus.claims)
    criteria = {claim.criterion for claim in corpus.claims}
    for call in seen:
        # Not a subset check: a new keyword is exactly how the answer would
        # arrive, so anything beyond these two fails here rather than after
        # the money is spent.
        assert set(call) == {"criterion", "audio_path"}
        assert call["criterion"] in criteria
        blob = " ".join(str(value) for value in call.values())
        assert "GROUND-TRUTH-NOT-FOR-SENDING" not in blob
        assert "SENTENCE-NOT-FOR-SENDING" not in blob

    # The transcript is in the manifest and must not survive loading it.
    assert not any(
        "SENTENCE-NOT-FOR-SENDING" in str(vars(clip)) for clip in corpus.clips
    )


def test_the_published_criteria_do_not_answer_themselves() -> None:
    """A criterion that quotes the sentence is answerable without listening.

    The pair design is what keeps this honest: both sides ask about the same
    clip in the same shape, and differ by the one confusable word. If one side
    named its own truth value -- or restated the sentence -- a reader with no
    audio would score 100% and the run would be reported as hearing.
    """
    published = json.loads(
        PUBLISHED_SPEECH_MANIFEST.read_text(encoding="utf-8")
    )
    transcripts = {
        clip["clip_id"]: clip["command"][-1] for clip in published["clips"]
    }
    by_pair: dict[str, list[dict[str, object]]] = {}
    for claim in published["claims"]:
        criterion = str(claim["criterion"])
        lowered = criterion.lower()
        assert str(claim["because"]).lower() not in lowered
        assert transcripts[claim["clip_id"]].lower() not in lowered
        for marker in ("true", "false", "correct", "incorrect", "the answer"):
            assert marker not in lowered, f"{claim['claim_id']}: {marker!r}"
        by_pair.setdefault(str(claim["pair_id"]), []).append(claim)

    assert len(by_pair) == 10
    for pair_id, sides in by_pair.items():
        assert len(sides) == 2, pair_id
        first, second = sides
        assert first["clip_id"] == second["clip_id"], pair_id
        assert first["family"] == second["family"], pair_id
        # Identical criteria would make the pair one question asked twice, and
        # the permutation test would be swapping a label between duplicates.
        assert first["criterion"] != second["criterion"], pair_id


def test_the_document_states_the_family_sizes_the_corpus_has() -> None:
    """A family of two claims can only score 0, 50 or 100 per cent.

    ``negation: 100%`` on two claims is two coin flips landing heads -- one
    time in four -- and it reads as a finding. 330 §4 hangs "hears words but
    not sentences" on three families, and two of them are that size, so the
    document states every family's count beside the accuracies it can produce.
    Those counts are the corpus's, and a claim added or moved without the
    table following would leave the reading attached to the wrong denominator.
    """
    published = json.loads(
        PUBLISHED_SPEECH_MANIFEST.read_text(encoding="utf-8")
    )
    sizes: dict[str, int] = {}
    for claim in published["claims"]:
        family = str(claim["family"])
        sizes[family] = sizes.get(family, 0) + 1

    doc = (
        PUBLISHED_SPEECH_MANIFEST.parent / "330-speech-diagnostic-prereg.md"
    ).read_text(encoding="utf-8")
    section = doc.split("#### 종류별 숫자는", 1)
    assert len(section) == 2, "the family-size subsection is gone"
    # Cut at the bullet that follows the subsection so the rows come from
    # this table and not from some other one further down the document.
    table = section[1].split("\n* ", 1)[0]

    stated = dict(
        re.findall(r"^\|\s*`([a-z_]+)`\s*\|\s*(\d+)\s*\|", table, re.M)
    )
    assert {k: int(v) for k, v in stated.items()} == sizes
    assert sum(sizes.values()) == 20

    # The three families §4 reasons from have to be in the corpus at all --
    # naming a family that is not there is the failure this file keeps finding.
    for family in ("order", "binding", "negation"):
        assert family in sizes, family


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
        identity=_stamped_identity(),
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
        identity=_stamped_identity(),
        measured=False,
        repeats=3,
        result=result,
        speech=corpus,
    )
    # The estimate has to describe the audio the run *sends*, and the run
    # sends one clip per call. Comparing it against the corpus length was the
    # defect: this fixture asks two criteria of each clip, exactly as the
    # published set does, so the two formulas differ by 2x and only one of
    # them is what gets billed.
    sent = sum(corpus.durations[call["clip_id"]] for call in result["calls"])
    assert report["speech_set"]["audio_seconds_sent"] == pytest.approx(sent)
    assert report["speech_set"]["expected_audio_tokens"] == round(
        probe.AUDIO_TOKENS_PER_SECOND * sent
    )
    assert report["speech_set"]["expected_audio_tokens"] != round(
        probe.AUDIO_TOKENS_PER_SECOND * corpus.total_seconds * 3
    ), "counting clips again instead of calls"


def test_the_document_and_the_code_agree_on_what_the_run_sends() -> None:
    """330 §2's token block is read out of the document, not typed in here.

    The number it holds is the only pre-dispatch estimate of what this run
    costs on a model with no published price, and it is what the +/-10%
    delivery band is measured against. It said 937 -- the corpus length times
    the repeats -- and the run sends 1,874, because a call carries the clip
    its criterion is about and twenty criteria share ten clips. A healthy run
    would have landed 82% above the band, and the summary would have printed
    *"the billed audio is more than 10% away from the pre-registered figure"*
    in bold on a run where nothing was wrong. A check that fires on every run
    is worse than no check: it is the one that would have caught a real
    delivery failure, spent.

    Reading the block rather than restating it is the point. The old pair of
    tests asserted the code's formula against itself and the document's number
    against the same formula, so both were green on the wrong answer.
    """
    doc = (
        probe.REPO_ROOT / "tasks" / "rebuilding_grading_task"
        / "330-speech-diagnostic-prereg.md"
    ).read_text(encoding="utf-8")

    def _stated(name: str) -> float:
        found = re.search(rf"^{name}\s*=\s*([0-9.]+)", doc, re.MULTILINE)
        assert found, f"330 no longer states {name}"
        return float(found.group(1))

    band = re.search(r"^band_10pct\s*=\s*(\d+) \.\. (\d+)", doc, re.MULTILINE)
    assert band, "330 no longer states the +/-10% band"

    published = json.loads(PUBLISHED_SPEECH_MANIFEST.read_text(encoding="utf-8"))
    seconds = {c["clip_id"]: c["sent"]["seconds"] for c in published["clips"]}
    # What the run sends: one clip per call, every claim, every repeat.
    sent = round(
        sum(seconds[claim["clip_id"]] for claim in published["claims"]) * 3, 4
    )
    tokens = round(probe.AUDIO_TOKENS_PER_SECOND * sent)

    assert _stated("audio_seconds_sent") == sent
    assert _stated("expected_audio_tokens") == tokens
    assert int(band.group(1)) == round(tokens * 0.9)
    assert int(band.group(2)) == round(tokens * 1.1)

    # And the corpus length is still in there, named as the thing it is, so
    # the two cannot be read as the same number again.
    assert _stated("클립 길이 합") == round(sum(seconds.values()), 4)
    assert _stated("클립 길이 합") * 2 == _stated("한 바퀴에 나가는 소리")

    # Every place the document states the figure has to state the same one.
    # The block above was not the only copy: the rehearsal table two sections
    # up carried 937 as well, and correcting one of them is how a document
    # ends up disagreeing with itself about what a run costs. The paragraph
    # explaining that it *used* to be 937 is prose and is not a statement of
    # the figure, which is why the pattern is the labelled form.
    stated = {
        int(found.replace(",", ""))
        for found in re.findall(r"예상 오디오 토큰[^\d]{0,4}\*\*([\d,]+)\*\*", doc)
    }
    assert stated == {tokens}, f"330 states more than one token figure: {stated}"


def test_the_billed_audio_line_says_which_of_the_three_things_happened(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """The +/-10% band's own branch had never been executed anywhere.

    The test above fixes the *number* the band is measured against. It does not
    render the line that does the measuring, and nothing else did either: every
    rehearsal report has ``delivery.audio_tokens_total = None``, because no free
    call reports the field, so the whole block was skipped in each of the six
    tests that execute this summary. Defect 14's shape a fourth time -- a guard
    exercised only on the input where it does nothing -- and here the input where
    it does something is *the paid run*. It would have run for the first time
    against money.

    And the skip was itself the defect. The measurer is careful about three
    states: ``None`` is recorded when no call reported the field, deliberately
    not ``0``, because ``0`` is a claim about metering. The summary collapsed it
    back to two by printing nothing -- so a reader checking whether the band held
    saw identical blank space whether it held, or was never measured at all.
    That is the same silence that made the free page useless against defect 1.
    """
    manifest_path, clip_dir = _speech_fixture(tmp_path, clips=5)
    out = tmp_path / "billed.json"
    assert probe.main([
        "--dry-run", "--quiet", "--repeats", "3",
        "--speech-set", str(manifest_path),
        "--speech-clips", str(clip_dir),
        "--out", str(out),
    ]) == 0
    base = json.loads(out.read_text(encoding="utf-8"))
    expected = base["speech_set"]["expected_audio_tokens"]
    assert base["delivery"]["audio_tokens_total"] is None, (
        "the rehearsal now reports billed audio, so this test no longer covers "
        "the branch the paid run takes first"
    )

    def _rendered(total: object) -> str:
        report = json.loads(json.dumps(base))
        report["delivery"]["audio_tokens_total"] = total
        return _render_paid_summary(report, tmp_path, monkeypatch, capsys)

    BANNER = "billed audio is more than 10% away"

    silent = _rendered(None)
    assert "not reported" in silent, "no call reported the field and the page said nothing"
    assert "did not run" in silent, "silence reads as agreement with the expected figure"
    assert BANNER not in silent, "a band that was not measured cannot have been missed"

    exact = _rendered(expected)
    assert f"actually billed: {expected}" in exact
    assert "(0.0% from expected)" in exact
    assert BANNER not in exact, "the banner fires on a run that matched exactly"
    assert "not reported" not in exact

    inside = _rendered(round(expected * 1.09))
    assert BANNER not in inside, "9% drift is inside the pre-registered band"

    outside = _rendered(round(expected * 1.11))
    assert BANNER in outside, "11% drift is outside the band and the page stayed quiet"

    # Metered at a real zero: §3's fourth stop rule ends the run, but a run
    # stopped after some calls still writes a report and still gets summarised.
    # 100% away is the loudest case the band has, so it must not be the case
    # that gets rounded into silence.
    zeroed = _rendered(0)
    assert "actually billed: 0" in zeroed
    assert BANNER in zeroed


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


# ── The speech prompt A/B: a second door, and what has to hold behind it ──
#
# 331 could not say whether the judge's near-constant ``fail`` came from the
# audio or from the wording of the prompt asking about it. Answering that
# needs two prompts on the same clips -- which is exactly what the block
# above refuses. So the refusal stays and a separately registered door is
# added beside it, and these are the tests that the door leads somewhere
# honest: same audio, same question, same response contract, one difference.


def _pair_discriminating_tokens() -> set[str]:
    """The words that separate one half of a pinned pair from the other.

    Derived from the published manifest, not listed here. A list would be a
    second copy of the corpus that stops being true the moment a claim is
    edited, and the thing being guarded -- "the alternative prompt does not
    hand the model an answer" -- is a property of the corpus that ran.

    The symmetric difference is what makes this work without a stopword list:
    both halves of a pair ask about the same clip in the same shape, so ``the``
    and ``speaker`` cancel and ``seventeen``/``seventy`` do not.
    """
    manifest = json.loads(
        (
            probe.REPO_ROOT / "tasks" / "rebuilding_grading_task"
            / "330-speech-verification-manifest.json"
        ).read_text(encoding="utf-8")
    )
    by_pair: dict[str, list[str]] = {}
    for claim in manifest["claims"]:
        by_pair.setdefault(claim["pair_id"], []).append(claim["criterion"])
    tokens: set[str] = set()
    for criteria in by_pair.values():
        assert len(criteria) == 2, "the corpus stopped being paired"
        first, second = (set(re.findall(r"[a-z]+", c.lower())) for c in criteria)
        tokens |= first ^ second
    return tokens


def _intervention(header: str) -> str:
    """The header without core's response contract.

    The contract is appended verbatim to both arms and to production, so it
    is not part of what the A/B varies. Guards that ask "what does this arm
    say" mean this string; asking them of the whole header measures core's
    wording instead of ours.
    """
    assert header.endswith(AUDIO_RESPONSE_CONTRACT)
    return header[: -len(AUDIO_RESPONSE_CONTRACT)]


def test_the_speech_observation_header_leaks_no_answer() -> None:
    """The alternative prompt must not name either side of any pair.

    A header carrying ``seventeen`` would make the true half of that pair
    answerable without listening, and the arm would win for a reason that has
    nothing to do with observation-first prompting.

    **What is checked is the intervention**, meaning the header without the
    response contract. Not a convenience: core's contract says ``"verdict"
    MUST be one of these four strings``, and ``four`` is one half of the
    binding pair. It is core's string, it is frozen, it went out identically
    in 331's paid run, and it is appended to *both* arms -- so it cannot tilt
    one arm against the other, which is the question an A/B asks. It is
    recorded here rather than filtered silently, because "the corpus shares a
    number word with the response contract" is a real observation about the
    corpus and belongs in a list somebody reads.

    **What this cannot cover.** One pair -- the word-order pair -- differs by
    ordering alone, so its two criteria use the same words and contribute
    nothing to the guarded set. That is a real gap and it is not closable by
    a token check; it is why the header is also read by a person.
    """
    discriminating = _pair_discriminating_tokens()
    assert len(discriminating) >= 18, (
        "the corpus stopped distinguishing its pairs by wording, which would "
        "make this guard vacuous rather than passing"
    )

    header_tokens = set(
        re.findall(
            r"[a-z]+", _intervention(probe.SPEECH_OBSERVATION_HEADER).lower()
        )
    )
    leaked = sorted(header_tokens & discriminating)
    assert not leaked, f"the observation header hands over: {leaked}"

    # And the same guard against the header the tone corpus uses, because
    # nothing stops someone pointing the speech run at it.
    assert not set(
        re.findall(r"[a-z]+", _intervention(probe.OBSERVATION_HEADER).lower())
    ) & discriminating

    # The one token the contract does share, pinned so that it stays the only
    # one: a second word appearing here should stop a build, not pass quietly.
    assert sorted(
        set(re.findall(r"[a-z]+", AUDIO_RESPONSE_CONTRACT.lower()))
        & discriminating
    ) == ["four"]


def test_the_speech_arm_asks_about_speech_and_keeps_everything_else() -> None:
    """One difference between the corpora, and it is the observation list.

    The tone header asks for pitches, intervals, harmonic content, a tempo and
    a key. A spoken sentence has none of those to report, so sending it with
    speech would handicap the alternative arm and the run would measure the
    mismatch instead of the intervention.

    The rest has to stay word-for-word identical or the two corpora are no
    longer testing the same change.
    """
    speech = probe.SPEECH_OBSERVATION_HEADER
    tone = probe.OBSERVATION_HEADER
    assert speech != tone

    for word in ("pitch", "interval", "harmonic", "tempo", "key", "beep"):
        # The intervention, not the whole header: core's contract names the
        # JSON "keys" it wants, and that is not this arm asking about a
        # musical key.
        assert word not in _intervention(speech).lower(), (
            f"the speech arm asks about {word!r}, which is not in a sentence"
        )
        assert word in _intervention(tone).lower() or word in ("beep",), (
            f"the tone arm stopped asking about {word!r}, so this guard is "
            f"no longer separating the two corpora"
        )

    opening = (
        "You are an audio analyst. A short audio clip has been supplied to "
        "you as audio input. Work only from that audio. Nothing you have been "
        "told about the clip is a substitute for listening to it."
    )
    for header in (speech, tone):
        assert header.startswith(opening)
        assert header.endswith(AUDIO_RESPONSE_CONTRACT)
        # The response contract is not part of the intervention. Writing a
        # second one is what made run 34008840627 measure which paragraph
        # described JSON better; it is core's string or it is nothing.
        assert header.count(AUDIO_RESPONSE_CONTRACT) == 1
        assert "may be true or it may be false" in header
        assert '"judge_error"' in header


def _prompt_ab_doc(tmp_path: Path, *, kind: str = "speech-prompt-ab",
                   pin: str | None = None, name: str = "prereg.md") -> Path:
    doc = tmp_path / name
    lines = [f"| 진단 종류 | `{kind}` |"] if kind else []
    if pin is None:
        pin = probe.grader_source_hash()
    if pin:
        lines.append(f"| 채점기 지문 | `{pin}` |")
    doc.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return doc


def _speech_ab_args(tmp_path: Path, manifest_path: Path, clip_dir: Path,
                    out: Path) -> list[str]:
    return [
        "--dry-run", "--quiet", "--repeats", "1",
        "--speech-set", str(manifest_path),
        "--speech-clips", str(clip_dir),
        "--out", str(out),
    ]


def test_the_prompt_ab_door_only_opens_for_a_document_that_registered_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A path on a command line is not consent.

    Every refusal here is a way the door could otherwise have become "the
    single-arm rule, with a flag that turns it off" -- which is the thing the
    line above it exists to prevent.
    """
    manifest_path, clip_dir = _speech_fixture(tmp_path, clips=2)
    out = tmp_path / "out.json"
    args = _speech_ab_args(tmp_path, manifest_path, clip_dir, out)

    # Without a speech set there is nothing to compare two prompts on.
    with pytest.raises(SystemExit):
        probe.main([
            "--dry-run", "--quiet",
            "--speech-prompt-ab", str(_prompt_ab_doc(tmp_path)),
        ])

    # A document that declares nothing has agreed to nothing.
    silent = tmp_path / "silent.md"
    silent.write_text("# just a file\n", encoding="utf-8")
    assert probe.main([*args, "--speech-prompt-ab", str(silent)]) == 3
    assert "declares no diagnostic kind" in capsys.readouterr().err

    # A document that registered some other diagnostic. The refusal names
    # what the document said and lists what would have been accepted -- there
    # is more than one registered two-arm kind now, so naming a single
    # expected string would tell a reader the wrong thing.
    other = _prompt_ab_doc(tmp_path, kind="tone-sweep", name="other.md")
    assert probe.main([*args, "--speech-prompt-ab", str(other)]) == 3
    err = capsys.readouterr().err
    assert "registers 'tone-sweep'" in err
    assert "not a two-arm speech comparison" in err
    for kind in probe.SPEECH_TWO_ARM_REGISTRATIONS:
        assert kind in err

    # Declaring itself is not enough: it still has to pin the grader, and the
    # pin is checked by the same code --expect-grader-pin uses.
    unpinned = _prompt_ab_doc(tmp_path, pin="", name="unpinned.md")
    assert probe.main([*args, "--speech-prompt-ab", str(unpinned)]) == 3
    assert "states no grader fingerprint" in capsys.readouterr().err

    stale = _prompt_ab_doc(tmp_path, pin="a" * 64, name="stale.md")
    assert probe.main([*args, "--speech-prompt-ab", str(stale)]) == 3
    assert probe.grader_source_hash() in capsys.readouterr().err

    # Two documents naming different graders is a run filed under one
    # fingerprint while held to another.
    good = _prompt_ab_doc(tmp_path)
    with pytest.raises(SystemExit):
        probe.main([
            *args, "--speech-prompt-ab", str(good),
            "--expect-grader-pin", str(_prompt_ab_doc(tmp_path, name="second.md")),
        ])

    assert not out.exists(), "a refused run wrote a report"

    # And --prompt-arm still cannot reach the second arm, door or no door.
    with pytest.raises(SystemExit):
        probe.main([*args, "--prompt-arm", "both",
                    "--speech-prompt-ab", str(good)])

    assert probe.main([*args, "--speech-prompt-ab", str(good)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["pins"][
        "prompt_arms"
    ] == list(probe.PROMPT_ARMS)


def _requests_from_an_ab_dry_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, doc: Path | None = None
) -> tuple[list[dict], dict]:
    """Run the door end to end against a stub API and keep what went out.

    ``TruthfulStub`` already records every ``create`` call verbatim -- it is
    the mock API this needs -- so the only thing added is a handle on the
    instance ``main`` built. Nothing about the request path is faked: core
    assembles the prompt, ``WireClient`` swaps the arm, and what lands in
    ``requests`` is the payload a paid run would post.

    ``doc`` picks which registration opens the door, so the same end-to-end
    path can be measured for a second registered header without a second
    copy of this function -- and without either measurement being taken from
    a hand-built request that no ``main`` ever sent.
    """
    manifest_path, clip_dir = _speech_fixture(tmp_path, clips=3)
    out = tmp_path / "out.json"
    made: list[probe.TruthfulStub] = []

    class _Handle(probe.TruthfulStub):
        def __init__(self, claims: Sequence[probe.Claim]) -> None:
            super().__init__(claims)
            made.append(self)

    monkeypatch.setattr(probe, "TruthfulStub", _Handle)
    assert probe.main([
        *_speech_ab_args(tmp_path, manifest_path, clip_dir, out),
        "--speech-prompt-ab", str(doc or _prompt_ab_doc(tmp_path)),
    ]) == 0
    assert len(made) == 1
    return made[0].requests, json.loads(out.read_text(encoding="utf-8"))


def test_the_two_speech_arms_differ_by_the_header_and_by_nothing_else(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The claim the A/B rests on, checked against the wire.

    If the arms differ anywhere but the header, the run measures that
    difference too and cannot attribute anything to the prompt. Each of these
    is a way that has actually gone wrong before: 328 sent a home-written
    response contract, and the two-digest banner exists because audio can
    stop being identical without anything raising.
    """
    requests, report = _requests_from_an_ab_dry_run(tmp_path, monkeypatch)

    by_arm: dict[str, dict[str, dict]] = {"production": {}, "observation": {}}
    for kwargs in requests:
        text = ""
        audio: list[dict] = []
        for part in kwargs["messages"][0]["content"]:
            if part.get("type") == "text":
                text = part["text"]
            elif part.get("type") == "input_audio":
                audio.append(part["input_audio"])

        assert kwargs["modalities"] == ["text"]
        # 332 §4: not until the provider is on record that this model accepts
        # it alongside input_audio. A flag that appears here for one arm would
        # also be a difference between the arms.
        assert "response_format" not in kwargs
        assert len(audio) == 1 and audio[0]["format"] in SUPPORTED_AUDIO_FORMATS

        if probe.PRODUCTION_CRITERION_MARKER in text:
            arm, header, criterion = (
                "production", *probe.split_production_text(text)
            )
        else:
            header, _, criterion = text.partition("\n\nStatement:\n")
            arm = "observation"
            assert header == probe.SPEECH_OBSERVATION_HEADER
        digest = hashlib.sha256(
            base64.b64decode(audio[0]["data"], validate=True)
        ).hexdigest()
        by_arm[arm][criterion] = {"digest": digest, "header": header}

    assert len(by_arm["production"]) == 6
    assert set(by_arm["production"]) == set(by_arm["observation"]), (
        "the arms were asked different questions, so nothing pairs"
    )
    for criterion, sent in by_arm["production"].items():
        other = by_arm["observation"][criterion]
        assert sent["digest"] == other["digest"], (
            f"{criterion!r} was judged on different audio in the two arms; "
            f"this is a comparison of clips, not of prompts"
        )
        assert sent["header"] != other["header"]
        for header in (sent["header"], other["header"]):
            assert header.endswith(AUDIO_RESPONSE_CONTRACT)

    # And the report says which alternative prompt those observation calls
    # carried, so the run can be checked against the header the
    # pre-registration pinned rather than against this file.
    assert report["pins"]["observation_header_sha256"] == hashlib.sha256(
        probe.SPEECH_OBSERVATION_HEADER.encode("utf-8")
    ).hexdigest()


def test_a_single_arm_run_does_not_claim_an_alternative_prompt(
    tmp_path: Path
) -> None:
    """A fingerprint for a prompt nothing sent is a fact about the source
    file, not about the run -- and a reader would take it for the latter."""
    manifest_path, clip_dir = _speech_fixture(tmp_path, clips=2)
    out = tmp_path / "out.json"
    assert probe.main(
        _speech_ab_args(tmp_path, manifest_path, clip_dir, out)
    ) == 0
    assert "observation_header_sha256" not in json.loads(
        out.read_text(encoding="utf-8")
    )["pins"]


# ── The paid entry point has to be able to ask for the speech corpus ─────
#
# Everything above is about the script. These are about the only file that
# can spend money with it: a corpus the workflow cannot select is a corpus
# nobody can buy, and a corpus it selects without verifying is worse.


SPEECH_MANIFEST_REPO_PATH = (
    "tasks/rebuilding_grading_task/330-speech-verification-manifest.json"
)


def test_the_workflow_can_ask_for_either_corpus() -> None:
    """A choice input, defaulting to the cheap and already-run one.

    ``speech`` installs a synthesiser and rebuilds ten clips before it calls
    anything, so it is a deliberate selection rather than something inherited
    from a default nobody looked at.

    The full option list is not restated here. Three of the entries are
    two-arm diagnostics that each need their own document, and holding the
    list and the routing apart let them drift; both are asserted together in
    ``test_every_two_arm_corpus_is_offered_and_routed_to_its_own_document``.
    """
    inputs = _workflow()[True]["workflow_dispatch"]["inputs"]
    corpus = inputs["corpus"]
    assert corpus["type"] == "choice"
    assert {"tones", "speech"} <= set(corpus["options"])
    assert corpus["default"] == "tones"


@pytest.mark.parametrize("job", ["dry-run", "measure"])
def test_both_jobs_rebuild_the_speech_set_against_the_committed_pin(
    job: str,
) -> None:
    """The check is the point, not the rebuild.

    Regenerating clips is easy and proves nothing on its own -- a newer eSpeak
    regenerates them happily, into different bytes, and the run would measure
    audio the pre-registration does not describe. ``--expect-manifest`` is
    what turns the rebuild into evidence, and it has to be on both jobs: the
    free one so the failure is found before a reviewer is asked, the paid one
    so the audio actually sent is the audio that was checked.
    """
    step = _step(job, "Build and verify the pinned speech set")
    # Every corpus that is not tones needs the clips, and the condition says so
    # that way round on purpose: a third speech corpus arriving must not
    # silently skip the rebuild and measure whatever was left in the directory.
    assert step["if"].strip() == "${{ inputs.corpus != 'tones' }}"
    assert "--expect-manifest" in step["run"]
    assert "$SPEECH_MANIFEST" in step["run"]
    assert "--out-dir" in step["run"]
    assert "$SPEECH_CLIPS" in step["run"]
    assert "espeak-ng" in step["run"]


def test_the_manifest_path_the_workflow_names_is_the_committed_one() -> None:
    """A path typed into a workflow is not checked by anything until it runs.

    If it were wrong, the failure would land after the espeak install, on the
    paid job, having already passed the gate.
    """
    workflow = _workflow()
    manifest = workflow["env"]["SPEECH_MANIFEST"]
    assert manifest.endswith(SPEECH_MANIFEST_REPO_PATH)
    assert (probe.REPO_ROOT / SPEECH_MANIFEST_REPO_PATH).is_file()


@pytest.mark.parametrize("job,step_name", [
    ("dry-run", "Dry run"),
    ("measure", "Measure"),
])
def test_both_runs_forward_the_speech_flags_together(
    job: str, step_name: str
) -> None:
    """The script refuses a lone flag, so a half-forwarded pair fails loudly.

    What it would not catch is a run step that forwards neither: that one
    silently measures tones under an approval record that says speech.
    """
    run = _step(job, step_name)["run"]
    assert "--speech-set" in run
    assert "--speech-clips" in run
    assert "inputs.corpus" in run


@pytest.mark.parametrize("corpus", ["tones", "speech", "speech-prompt-ab"])
def test_the_approval_record_names_the_corpus_it_authorised(corpus: str) -> None:
    """Run the gate's own shell, as the call-count test does.

    Both corpora hold twenty criteria, so the call count alone cannot tell a
    reader which sounds were bought. The clip count can, and it is the one
    number that differs.

    Every number here is read from a corpus rather than typed in. The criteria
    count is the one that sets the call count on the record -- the record
    computes ``20 * PROBE_REPEATS`` -- and it was pinned against ``CLAIMS``
    alone, which is the corpus this run does *not* buy. That the speech set
    also holds twenty was a sentence in a comment.

    330 §5 says twenty claims is few, so growing the speech set is a change
    somebody will reasonably make, and it is the newer of the two corpora. With
    the count typed in here, adding four claims would leave the gate recording
    ``calls = 60`` for a run that makes 72 and the assertion would still pass:
    ``calls = 36`` again, on the dispatch that spends the money.
    """
    published = json.loads(
        (probe.REPO_ROOT / SPEECH_MANIFEST_REPO_PATH).read_text(encoding="utf-8")
    )
    criteria = {"tones": len(probe.CLAIMS), "speech": len(published["claims"])}
    true_claims = {
        "tones": sum(1 for claim in probe.CLAIMS if claim.holds),
        "speech": sum(1 for claim in published["claims"] if claim["holds"]),
    }
    clips = {"tones": len(probe.CLIPS), "speech": len(published["clips"])}
    # The A/B buys the same clips and the same criteria; only the arm count
    # differs, and that is the next test.
    for table in (criteria, true_claims, clips):
        table["speech-prompt-ab"] = table["speech"]

    assert criteria["tones"] == criteria["speech"], (
        "the corpora no longer hold the same number of criteria, so the "
        "record's one `criteria` line and its `20 * PROBE_REPEATS` call count "
        "cannot serve both. Branch them on $CORPUS the way CLIPS is branched"
    )

    bash = shutil.which("bash")
    if bash is None:  # pragma: no cover - CI and dev boxes both have bash
        pytest.skip("no bash to run the gate's own script with")

    result = subprocess.run(
        [bash, "-c", _step("approve-paid", "Record approved request")["run"]],
        env={
            **os.environ,
            "PROBE_REPEATS": "3",
            "PROBE_ARM": "production",
            "PROBE_CORPUS": corpus,
        },
        capture_output=True,
        text=True,
        check=True,
    )
    assert f"corpus     = {corpus} ({clips[corpus]} clips)" in result.stdout
    # Still the same criteria count, which is why the clip count had to be
    # added rather than relied upon to differ.
    assert (
        f"criteria   = {criteria[corpus]} ({true_claims[corpus]} true / "
        f"{criteria[corpus] - true_claims[corpus]} false)"
    ) in result.stdout
    assert f"calls      = {criteria[corpus] * 3} per arm" in result.stdout


def test_the_gate_counts_the_second_arm_the_document_opens() -> None:
    """``prompt_arm`` stays ``production`` and the run still makes two arms.

    Every previous version of this record read the arm count off
    ``prompt_arm`` alone. That was right while ``both`` was the only way to a
    second arm. The speech A/B opens one from its pre-registration instead, so
    a record that still read the flag would authorise 60 calls for a run that
    makes 120 -- the ``calls = 36`` failure, on the dispatch that spends.
    """
    bash = shutil.which("bash")
    if bash is None:  # pragma: no cover - CI and dev boxes both have bash
        pytest.skip("no bash to run the gate's own script with")

    published = json.loads(
        (probe.REPO_ROOT / SPEECH_MANIFEST_REPO_PATH).read_text(encoding="utf-8")
    )
    criteria = len(published["claims"])
    arms = len(probe.PROMPT_ARMS)

    result = subprocess.run(
        [bash, "-c", _step("approve-paid", "Record approved request")["run"]],
        env={
            **os.environ,
            "PROBE_REPEATS": "3",
            "PROBE_ARM": "production",
            "PROBE_CORPUS": "speech-prompt-ab",
        },
        capture_output=True,
        text=True,
        check=True,
    )
    assert "prompt_arm = production (2 arm(s))" in result.stdout
    assert (
        f"calls      = {criteria * 3} per arm, {criteria * 3 * arms} in total"
    ) in result.stdout

    # And the single-arm speech run is unchanged by that branch existing.
    single = subprocess.run(
        [bash, "-c", _step("approve-paid", "Record approved request")["run"]],
        env={
            **os.environ,
            "PROBE_REPEATS": "3",
            "PROBE_ARM": "production",
            "PROBE_CORPUS": "speech",
        },
        capture_output=True,
        text=True,
        check=True,
    )
    assert "prompt_arm = production (1 arm(s))" in single.stdout
    assert f"calls      = {criteria * 3} per arm, {criteria * 3} in total" in single.stdout


def test_the_gate_states_the_clip_counts_the_corpora_actually_have() -> None:
    """The gate has no checkout, so those two numbers are restatements.

    Same failure mode as ``calls = 36``: a record that says what was
    authorised, disagreeing with what exists.
    """
    run = _step("approve-paid", "Record approved request")["run"]
    tone_clips = re.search(r"case \"\$CORPUS\" in speech\*\) CLIPS=\d+ ;; \*\) CLIPS=(\d+)", run)
    speech_clips = re.search(r"case \"\$CORPUS\" in speech\*\) CLIPS=(\d+)", run)
    assert tone_clips and speech_clips
    assert int(tone_clips.group(1)) == len(probe.CLIPS)
    published = json.loads(
        (probe.REPO_ROOT / SPEECH_MANIFEST_REPO_PATH).read_text(encoding="utf-8")
    )
    assert int(speech_clips.group(1)) == len(published["clips"])


def test_the_paid_summary_refuses_to_pool_the_two_corpora() -> None:
    """Two capabilities, one heading, is how a beep count becomes a claim
    about speech. The summary has to say they are separate where it prints
    them, not only in a document."""
    summary = _step("measure", "Summarise")["run"]
    assert "not comparable" in summary
    assert "speech_set" in summary
    assert "expected_audio_tokens" in summary


def _wire_call(clip_id: str, *, seconds: float, tokens: object = "absent") -> dict:
    """A call log entry shaped like the one ``summarise_wire`` produces."""
    wire: dict[str, Any] = {
        "requests": 1,
        "requests_with_audio": 1,
        "audio_sha256": f"sha-{clip_id}",
        "audio_duration_s": seconds,
        "audio_format": "wav",
        "audio_sample_rate_hz": AUDIO_SAMPLE_RATE_HZ,
        "audio_channels": 1,
        "response_model": "gpt-audio-1.5",
    }
    if tokens != "absent":
        wire["audio_tokens"] = tokens
        wire["audio_tokens_billed"] = tokens
    return {
        "repeat": 1,
        "claim_id": f"{clip_id}_claim",
        "clip_id": clip_id,
        "input_tokens": 100 + int(seconds * 10),
        "wire": wire,
    }


def test_billed_audio_is_null_when_nobody_reported_it() -> None:
    """Zero is a claim. Silence is not.

    A total of zero is what a request that never carried the sound looks
    like, and 330 stops the run on it. If a provider that simply does not
    report the field produced the same zero, the stop rule would fire on
    every run against such a provider -- or, read the other way, a real zero
    would be dismissed as a quiet provider.
    """
    calls = [_wire_call("a", seconds=1.0), _wire_call("b", seconds=2.0)]
    delivery = probe.delivery_section(
        calls, measured=False, durations={"a": 1.0, "b": 2.0}
    )
    assert delivery["audio_tokens_reported"] == 0
    assert delivery["audio_tokens_total"] is None


def test_billed_audio_totals_what_was_reported() -> None:
    """And when it is reported, it is a sum rather than a count."""
    calls = [
        _wire_call("a", seconds=1.0, tokens=30),
        _wire_call("a", seconds=1.0, tokens=32),
        _wire_call("b", seconds=2.0),
    ]
    delivery = probe.delivery_section(
        calls, measured=True, durations={"a": 1.0, "b": 2.0}
    )
    assert delivery["audio_tokens_reported"] == 2
    assert delivery["audio_tokens_total"] == 62


def test_a_retried_envelope_is_billed_twice_and_counted_twice() -> None:
    """One verdict, two requests, two clips' worth of audio on the invoice.

    ``summarise_wire`` exists because a judge call can make more than one
    request -- it keeps ``requests`` for exactly that reason -- and every other
    field it collapses takes the *last* one, correctly: ``audio_sha256`` and
    ``response_model`` describe the request that produced the verdict.

    ``audio_tokens`` was collapsed the same way, and it is not that kind of
    field. Billing counts requests. Six retries in sixty calls is 10% more
    audio bought than planned, which is the entire width of the pre-registered
    band -- and the summary would have printed ``0.0% from expected`` while it
    happened, because the number it compares was structurally incapable of
    including the retry. The band exists to notice exactly this.
    """
    def _request(tokens: int) -> dict[str, Any]:
        return {
            "audio_part_present": True,
            "audio_sha256": "a" * 64,
            "audio_format": "wav",
            "prompt_sha256": "b" * 64,
            "prompt_chars": 10,
            "response_model": "gpt-audio-1.5",
            "audio_tokens": tokens,
            "sent_wav": {
                "bytes": 1,
                "sample_rate_hz": AUDIO_SAMPLE_RATE_HZ,
                "channels": 1,
                "duration_s": 3.1,
            },
        }

    once = probe.summarise_wire([_request(31)])
    assert once["requests"] == 1
    assert once["audio_tokens"] == 31
    assert once["audio_tokens_billed"] == 31, "no retry, so the two agree"

    retried = probe.summarise_wire([_request(31), _request(31)])
    assert retried["requests"] == 2
    assert retried["audio_tokens"] == 31, (
        "the verdict's own meter reading is still the last request's, like the "
        "digest and the model name it sits beside"
    )
    assert retried["audio_tokens_billed"] == 62, (
        "the clip went out twice and was billed twice"
    )

    # The fixture helper below has to keep producing what this function does,
    # or the delivery tests pass against a shape the measurer never emits. A
    # subset check is not enough: the fixture omitted ``requests`` entirely and
    # `delivery_section` read it as 0, so a run of sixty calls reported twelve.
    fixture = _wire_call("a", seconds=1.0, tokens=1)["wire"]
    assert set(fixture) <= set(retried), (
        "_wire_call invented a wire field summarise_wire does not produce"
    )
    for field in (
        "requests", "requests_with_audio", "audio_tokens", "audio_tokens_billed"
    ):
        assert field in fixture, (
            f"delivery_section reads {field!r} and the fixture does not have it, "
            f"so its tests measure a call shape that never reaches the report"
        )


def test_the_delivery_total_is_the_bill_not_the_verdict_count() -> None:
    """Sixty calls, six of which retried, against the +/-10% band.

    The reported total used to be 1,860 with 2,046 billed -- inside the band,
    on a run that bought 10% more audio than pre-registered.
    """
    calls = [_wire_call(f"c{i}", seconds=1.0, tokens=31) for i in range(54)]
    for i in range(6):
        call = _wire_call(f"r{i}", seconds=1.0, tokens=31)
        call["wire"]["requests"] = 2
        call["wire"]["requests_with_audio"] = 2
        call["wire"]["audio_tokens_billed"] = 62
        calls.append(call)

    durations = {call["clip_id"]: 1.0 for call in calls}
    delivery = probe.delivery_section(calls, measured=True, durations=durations)

    assert delivery["audio_tokens_total"] == 54 * 31 + 6 * 62 == 2046
    assert delivery["audio_tokens_total"] != 60 * 31, "the retries fell off the bill"
    # And the count that explains why, so a reader seeing the band exceeded is
    # not left guessing between "a retry" and "different sound went out".
    assert delivery["requests_total"] == 66
    assert delivery["calls_inspected"] == 60


def test_the_summary_says_when_more_requests_went_out_than_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """A drift line with no cause is a line that gets argued with, not acted on."""
    manifest_path, clip_dir = _speech_fixture(tmp_path, clips=5)
    out = tmp_path / "retried.json"
    assert probe.main([
        "--dry-run", "--quiet", "--repeats", "3",
        "--speech-set", str(manifest_path),
        "--speech-clips", str(clip_dir),
        "--out", str(out),
    ]) == 0
    base = json.loads(out.read_text(encoding="utf-8"))
    assert base["delivery"]["requests_total"] == base["delivery"]["calls_inspected"]

    clean = _render_paid_summary(base, tmp_path, monkeypatch, capsys)
    assert "retried envelope" not in clean, "a line that prints when nothing retried"

    report = json.loads(json.dumps(base))
    report["delivery"]["requests_total"] = report["delivery"]["calls_inspected"] + 6
    printed = _render_paid_summary(report, tmp_path, monkeypatch, capsys)
    assert "6 retried envelope(s), each billed again" in printed
    assert f"requests sent: **{report['delivery']['requests_total']}**" in printed


def test_a_real_zero_still_reads_as_zero() -> None:
    """The other half of the distinction, and the one the stop rule needs."""
    calls = [_wire_call("a", seconds=1.0, tokens=0)]
    delivery = probe.delivery_section(
        calls, measured=True, durations={"a": 1.0}
    )
    assert delivery["audio_tokens_total"] == 0


def test_the_delivery_record_measures_speech_against_speech_lengths() -> None:
    """The bug this pins produced a full page of red on a healthy run.

    ``delivery_section`` defaulted to the tone clips for its duration table.
    Given speech calls, every lookup missed, every clip landed in
    ``clips_whose_sent_duration_differs``, and the correlation between prompt
    tokens and clip seconds -- the line that says the audio was charged for --
    had nothing to correlate. A reader following the instruction to check
    delivery before accuracy would have concluded the audio never arrived.
    """
    calls = [
        _wire_call("crate", seconds=3.0151),
        _wire_call("valve", seconds=3.2219),
    ]
    durations = {"crate": 3.0151, "valve": 3.2219}

    honest = probe.delivery_section(calls, measured=False, durations=durations)
    assert honest["clips_whose_sent_duration_differs"] == []
    assert honest["prompt_token_vs_clip_seconds"]["n"] == 2

    # The default, which is what the defect used: tone clip ids, so every
    # speech clip misses and is reported as a mismatch.
    wrong = probe.delivery_section(calls, measured=False)
    assert sorted(wrong["clips_whose_sent_duration_differs"]) == ["crate", "valve"]
    assert wrong["prompt_token_vs_clip_seconds"]["n"] == 0


def test_the_speech_run_picks_the_right_durations_without_being_told(
    tmp_path: Path,
) -> None:
    """End to end through the CLI, because that is what CI runs."""
    manifest_path, clip_dir = _speech_fixture(tmp_path, clips=3)
    out = tmp_path / "report.json"
    delivery_out = tmp_path / "delivery.json"
    assert probe.main([
        "--dry-run", "--quiet",
        "--speech-set", str(manifest_path),
        "--speech-clips", str(clip_dir),
        "--repeats", "1",
        "--out", str(out),
        "--delivery-out", str(delivery_out),
    ]) == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["corpus"] == "speech"
    delivery = report["delivery"]
    assert delivery["clips_whose_sent_duration_differs"] == []
    assert delivery["calls_carrying_audio"] == delivery["calls_inspected"]


def test_a_clip_with_no_pinned_length_is_left_out_rather_than_guessed(
    tmp_path: Path,
) -> None:
    """A placeholder length disagrees with every real one."""
    manifest_path, clip_dir = _speech_fixture(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    del manifest["clips"][0]["sent"]["seconds"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    corpus = probe.load_speech_corpus(manifest_path, clip_dir)
    assert "clip0" not in corpus.durations
    assert "clip1" in corpus.durations


# ── Stop rules, which only exist if code obeys them ──────────────────────
#
# 330 section 3 names four. A rule that lives only in a document is
# reconsidered at the exact moment obeying it would cost something.


def _rule_calls(n: int, **overrides: Any) -> list[dict]:
    calls = []
    for index in range(n):
        call = _wire_call("a", seconds=1.0, tokens=10)
        call["claim_id"] = f"c{index}"
        call["unanswered_kind"] = None
        call.update(overrides)
        calls.append(call)
    return calls


def test_the_pre_registered_rules_are_the_ones_the_document_names() -> None:
    """Four numbers in two files. This is the one that keeps them equal."""
    rules = probe.SPEECH_STOP_RULES
    assert rules.wall_clock_seconds == 20 * 60
    assert rules.zero_response_after == 10
    assert rules.max_provider_failures == 10
    assert rules.stop_on_undelivered_audio is True

    doc = (
        probe.REPO_ROOT / "tasks" / "rebuilding_grading_task"
        / "330-speech-diagnostic-prereg.md"
    ).read_text(encoding="utf-8")
    assert "20분" in doc
    assert "10번" in doc


def test_nothing_stops_a_healthy_run() -> None:
    assert probe._stop_reason(
        probe.SPEECH_STOP_RULES, calls=_rule_calls(30), elapsed_s=10.0
    ) is None


def test_the_clock_stops_the_run() -> None:
    fired = probe._stop_reason(
        probe.SPEECH_STOP_RULES, calls=_rule_calls(5), elapsed_s=20 * 60 + 1
    )
    assert fired["rule"] == "wall_clock_seconds"
    assert fired["after_calls"] == 5


def test_ten_calls_with_no_usable_verdict_stop_the_run() -> None:
    """This is the rule that would have ended 328's observation arm at ten.

    That run bought all sixty, none of which parsed, and published an
    accuracy computed over the seventeen replies that happened to contain a
    word the reader accepted.
    """
    calls = _rule_calls(10, unanswered_kind="read_failure")
    fired = probe._stop_reason(
        probe.SPEECH_STOP_RULES, calls=calls, elapsed_s=5.0
    )
    assert fired["rule"] == "zero_response_after"

    # One usable verdict among the ten is enough to keep going: the question
    # is whether the format is broken, not whether it is perfect.
    calls[3]["unanswered_kind"] = None
    assert probe._stop_reason(
        probe.SPEECH_STOP_RULES, calls=calls, elapsed_s=5.0
    ) is None


def test_one_silent_arm_is_not_hidden_by_the_other_arm_answering() -> None:
    """The rule counts per arm, because 334 proved a run-wide count cannot fire.

    334 interleaved ``production`` and ``observation`` one call apart. Call 1
    was production and it answered, so a run-wide ``answered == 0`` was false
    from the first call onward and stayed false while the observation arm went
    27 calls in a row without a readable verdict. All 120 were bought.
    """
    calls = []
    for index in range(10):
        good = _rule_calls(1, arm="production")[0]
        good["claim_id"] = f"c{index}"
        calls.append(good)
        bad = _rule_calls(1, arm="observation", unanswered_kind="read_failure")[0]
        bad["claim_id"] = f"c{index}"
        calls.append(bad)

    fired = probe._stop_reason(
        probe.SPEECH_STOP_RULES, calls=calls, elapsed_s=5.0
    )
    assert fired is not None, "the silent arm was hidden by the healthy one"
    assert fired["rule"] == "zero_response_after"
    assert fired["arm"] == "observation"
    # Both counts are reported: the arm's, which tripped it, and the run's,
    # which is what was actually paid for by that point.
    assert fired["after_calls_in_arm"] == 10
    assert fired["after_calls"] == 20


def test_the_response_rate_rule_is_what_finally_stops_a_334_shaped_arm() -> None:
    """The replacement the test that used to stand here asked for.

    Its predecessor asserted that no rule stopped a 334-shaped arm, and said
    in its own docstring that whoever added the missing rule should delete it.
    336 added it, so this is the same scenario with the opposite expectation.

    334's observation arm answered once, on its fourth call, and failed the
    rest. ``answered == 0`` is false from that fourth call onward, so the
    per-arm zero-response rule cannot catch it -- that part of the old test
    was right and is asserted below rather than dropped. What catches it is
    the response-rate rule, and it catches it while the run still has most of
    its money.
    """
    calls = []
    for index in range(30):
        good = _rule_calls(1, arm="production")[0]
        good["claim_id"] = f"c{index}"
        calls.append(good)
        bad = _rule_calls(1, arm="observation", unanswered_kind="read_failure")[0]
        bad["claim_id"] = f"c{index}"
        # The single reply that landed on the observation arm's fourth call.
        if index == 3:
            bad["unanswered_kind"] = None
        calls.append(bad)

    fired = probe._stop_reason(
        probe.SPEECH_STOP_RULES, calls=calls, elapsed_s=5.0
    )
    assert fired is not None, "the rule 334 section 10 asked for is missing"
    assert fired["rule"] == "min_response_rate"
    assert fired["arm"] == "observation"

    # And the older rule still does not fire here, which is why this one had
    # to exist. Asserting it keeps the reason on the record.
    silent_only = probe.StopRules(
        wall_clock_seconds=probe.SPEECH_STOP_RULES.wall_clock_seconds,
        zero_response_after=probe.SPEECH_STOP_RULES.zero_response_after,
        max_provider_failures=probe.SPEECH_STOP_RULES.max_provider_failures,
        stop_on_undelivered_audio=True,
    )
    assert probe._stop_reason(
        silent_only, calls=calls, elapsed_s=5.0
    ) is None


def test_the_stop_lands_early_enough_to_matter_on_the_real_334_log() -> None:
    """Replayed against the bought calls, not a reconstruction of them.

    The point of a stop rule is money, so the figure that matters is where in
    the 120 it would have landed. This reads the committed 334 log, feeds the
    calls in the order they were made, and checks the rule after each one --
    exactly what the runner does.

    334 itself is not re-analysed here and its file is opened read-only.
    """
    source = (
        Path(__file__).resolve().parents[2]
        / "tasks"
        / "rebuilding_grading_task"
        / "334-audio-accuracy-measured.json"
    )
    calls = json.loads(source.read_text(encoding="utf-8"))["calls"]
    assert len(calls) == 120

    seen: list[dict] = []
    fired = None
    for call in calls:
        seen.append(call)
        fired = probe._stop_reason(
            probe.SPEECH_STOP_RULES, calls=seen, elapsed_s=0.0
        )
        if fired is not None:
            break

    assert fired is not None
    assert fired["rule"] == "min_response_rate"
    assert fired["arm"] == "observation"
    assert fired["after_calls"] == 26
    assert fired["after_calls_in_arm"] == 13
    assert fired["answered_in_arm"] == 1
    assert fired["p_if_the_arm_met_the_limit"] < 0.05

    # The healthy arm is never touched. A rule that also stopped the arm that
    # was answering 98% of the time would be a rule about run length, not
    # about response rate.
    production = [c for c in calls if c["arm"] == "production"]
    seen = []
    for call in production:
        seen.append(call)
        assert probe._stop_reason(
            probe.SPEECH_STOP_RULES, calls=seen, elapsed_s=0.0
        ) is None


def test_ten_provider_failures_stop_the_run() -> None:
    calls = _rule_calls(12)
    for call in calls[:10]:
        call["unanswered_kind"] = "provider_failure"
    fired = probe._stop_reason(
        probe.SPEECH_STOP_RULES, calls=calls, elapsed_s=5.0
    )
    assert fired["rule"] == "max_provider_failures"


def test_a_request_that_carried_no_audio_stops_the_run_at_once() -> None:
    """One call, not ten. Everything after it would measure nothing."""
    calls = _rule_calls(1)
    calls[-1]["wire"]["requests_with_audio"] = 0
    fired = probe._stop_reason(
        probe.SPEECH_STOP_RULES, calls=calls, elapsed_s=1.0
    )
    assert fired["rule"] == "stop_on_undelivered_audio"


def test_a_reported_zero_and_an_unreported_field_are_not_the_same() -> None:
    """The distinction the null total exists to preserve, applied.

    A provider that never reports audio tokens must not trip a rule about
    audio never arriving; a provider that reports zero must.
    """
    silent = _rule_calls(1)
    silent[-1]["wire"].pop("audio_tokens", None)
    assert probe._audio_was_delivered(silent[-1]) is True
    assert probe._stop_reason(
        probe.SPEECH_STOP_RULES, calls=silent, elapsed_s=1.0
    ) is None

    zero = _rule_calls(1)
    zero[-1]["wire"]["audio_tokens"] = 0
    assert probe._audio_was_delivered(zero[-1]) is False
    assert probe._stop_reason(
        probe.SPEECH_STOP_RULES, calls=zero, elapsed_s=1.0
    )["rule"] == "stop_on_undelivered_audio"


def test_a_stopped_run_keeps_what_it_bought(tmp_path: Path) -> None:
    """Stopping is not discarding. 330: the partial result is still reported.

    A stop that threw away the calls would make obeying the rule expensive,
    which is how a stop rule stops being obeyed.
    """
    manifest_path, clip_dir = _speech_fixture(tmp_path, clips=3)
    corpus = probe.load_speech_corpus(manifest_path, clip_dir)
    perception = probe.AudioPerception(
        client=probe.TruthfulStub(corpus.claims),
        deployment="gpt-audio-1.5",
        call_cap=AUDIO_CALL_CAP,
        trim_seconds=AUDIO_TRIM_SECONDS,
    )
    ticks = iter([0.0] + [10_000.0] * 500)
    result = probe.run_measurement(
        perception=perception,
        clip_dir=tmp_path / "unused",
        repeats=3,
        claims=corpus.claims,
        prerendered=corpus,
        stop_rules=probe.StopRules(wall_clock_seconds=60),
        clock=lambda: next(ticks),
    )
    assert result["stopped"]["rule"] == "wall_clock_seconds"
    # One call made, kept, and the plan it fell short of is recorded.
    assert len(result["calls"]) == 1
    assert result["planned_calls"] == 3 * len(corpus.claims)

    report = probe.build_report(
        identity=_stamped_identity(),
        measured=False,
        repeats=3,
        result=result,
        speech=corpus,
    )
    assert report["stopped"]["rule"] == "wall_clock_seconds"
    assert report["calls_planned"] == 3 * len(corpus.claims)
    json.dumps(report)


def test_a_finished_run_says_so_rather_than_leaving_the_field_out(
    tmp_path: Path,
) -> None:
    """``stopped: null`` beside a full count is a statement. A missing key is
    something a reader has to interpret."""
    out = tmp_path / "report.json"
    assert probe.main(
        ["--dry-run", "--quiet", "--repeats", "1", "--out", str(out)]
    ) == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert "stopped" in report
    assert report["stopped"] is None
    assert report["calls_planned"] == len(probe.CLAIMS)


def test_the_tone_corpus_runs_without_stop_rules(tmp_path: Path) -> None:
    """Its numbers are published. Adding rules now would change the design a
    published result was produced under, after the fact."""
    source = (
        probe.REPO_ROOT / "batch-runner" / "scripts"
        / "measure_audio_grading_accuracy.py"
    ).read_text(encoding="utf-8")
    assert "stop_rules=SPEECH_STOP_RULES if speech else None" in source


def test_the_paid_summary_says_a_stopped_run_stopped() -> None:
    """A partial run that looks complete in the summary is how a stop rule
    turns into a quietly worse result."""
    step = _step("measure", "Summarise")
    body = step["run"]
    assert 'stopped = report.get("stopped")' in body
    assert "stopped early on the pre-registered rule" in body
    # The plan it fell short of has to be next to the count it reached,
    # or "made 12 calls" reads as the design rather than as a shortfall.
    assert "report['calls_planned']" in body
    assert "partial run" in body


def test_the_stop_banner_is_executed_and_not_merely_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """The test above greps. A grep cannot see a ``KeyError``.

    Every rehearsal finishes, so ``stopped`` is ``None`` on every report the
    free run has ever produced and this branch is skipped. The input that does
    enter it is a paid run that aborted -- the run whose summary matters most,
    written after the money is gone. That is defect 14's shape and defect 19's:
    a branch whose first execution is the expensive one.

    So the report here is built the way the measurer builds one -- the stop
    dict comes from ``_stop_reason``, not from a literal -- and rendered
    through the workflow's own code. What it is checking is that the two
    numbers stay distinguishable: ``after_calls`` is what was bought and
    ``calls_planned`` is what was designed, and a summary that prints the
    same figure twice says a partial run went to plan.
    """
    manifest_path, clip_dir = _speech_fixture(tmp_path, clips=3)
    corpus = probe.load_speech_corpus(manifest_path, clip_dir)
    perception = probe.AudioPerception(
        client=probe.TruthfulStub(corpus.claims),
        deployment="gpt-audio-1.5",
        call_cap=AUDIO_CALL_CAP,
        trim_seconds=AUDIO_TRIM_SECONDS,
    )
    ticks = iter([0.0] + [10_000.0] * 500)
    result = probe.run_measurement(
        perception=perception,
        clip_dir=tmp_path / "unused",
        repeats=3,
        claims=corpus.claims,
        prerendered=corpus,
        stop_rules=probe.StopRules(wall_clock_seconds=60),
        clock=lambda: next(ticks),
    )
    stopped = probe.build_report(
        identity=_stamped_identity(),
        measured=False,
        repeats=3,
        result=result,
        speech=corpus,
    )
    planned = 3 * len(corpus.claims)
    assert stopped["stopped"]["rule"] == "wall_clock_seconds"
    assert stopped["calls_planned"] == planned
    assert len(stopped["calls"]) == 1 < planned, (
        "the fixture no longer produces a partial run, so this test would pass "
        "on a summary that cannot tell a shortfall from a full run"
    )

    # A run that finished must stay quiet, or the banner is decoration and
    # this test proves nothing about the branch.
    finished = json.loads(json.dumps(stopped))
    finished["stopped"] = None
    BANNER = "stopped early on the pre-registered rule"
    assert BANNER not in _render_paid_summary(
        finished, tmp_path, monkeypatch, capsys
    )

    printed = _render_paid_summary(stopped, tmp_path, monkeypatch, capsys)
    assert BANNER in printed
    assert "`wall_clock_seconds`" in printed
    assert f"made 1 of {planned} planned calls" in printed
    # The rule's own reading, so the page says why it stopped and not only
    # that it did.
    assert "exceeded its pre-registered time limit" in printed
    # Above the numbers it qualifies. A caveat printed under a table of rates
    # is read after the rates have been believed.
    assert printed.index(BANNER) < printed.index("accuracy (answered calls)")


def test_the_stop_banner_names_what_was_left_unpaired(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """The census, on the page, not only in the artifact.

    A stop lands between calls and the arms interleave inside a claim, so the
    last claim can hold a production call and no observation one. The run does
    not buy the partner call to even the record up -- that would spend the
    money the rule just declined -- so what is unpaired has to be said.

    Whoever is about to quote a figure off a stopped run is reading this page,
    not the JSON. The sentence that matters is the one forbidding a p-value
    over the pairs that survived: a stop makes n depend on the data, so the
    surviving pairs are not the sample the pre-registration described. It is
    the easiest mistake to make from a summary that shows a clean table and
    says nothing about how the table came to be that size.

    ``run_measurement`` folding the census in is pinned separately, in
    ``test_silence_is_not_agreement.py``; this is the rendering half, and the
    census here is the real function's output over a two-arm log so the shape
    is not one this test invented.
    """
    manifest_path, clip_dir = _speech_fixture(tmp_path, clips=3)
    corpus = probe.load_speech_corpus(manifest_path, clip_dir)
    perception = probe.AudioPerception(
        client=probe.TruthfulStub(corpus.claims),
        deployment="gpt-audio-1.5",
        call_cap=AUDIO_CALL_CAP,
        trim_seconds=AUDIO_TRIM_SECONDS,
    )
    ticks = iter([0.0] + [10_000.0] * 500)
    result = probe.run_measurement(
        perception=perception,
        clip_dir=tmp_path / "unused",
        repeats=3,
        claims=corpus.claims,
        prerendered=corpus,
        stop_rules=probe.StopRules(wall_clock_seconds=60),
        clock=lambda: next(ticks),
    )
    # The measurer attaches it; a report without it would render the banner
    # and drop the half that says what the banner costs.
    assert "left_behind" in result["stopped"]

    report = probe.build_report(
        identity=_stamped_identity(),
        measured=False,
        repeats=3,
        result=result,
        speech=corpus,
    )
    # A single-arm run leaves nothing unpaired -- there is no partner arm to
    # be missing -- so the two-arm shape is built from the real census over a
    # log that stops mid-claim, which is the case the fields exist for.
    two_arm_log = [
        {"claim_id": "c1", "arm": "production"},
        {"claim_id": "c1", "arm": "observation"},
        {"claim_id": "c2", "arm": "production"},
        {"claim_id": "c2", "arm": "observation"},
        {"claim_id": "c3", "arm": "production"},
    ]
    census = probe._stop_census(two_arm_log, ["production", "observation"])
    assert census["claims_missing_an_arm_entirely"] == ["c3"]
    assert census["claims_with_unequal_calls_across_arms"] == ["c3"]
    report["stopped"]["left_behind"] = census

    printed = _render_paid_summary(report, tmp_path, monkeypatch, capsys)
    assert "Left unpaired: 1 claim(s) missing an arm entirely" in printed
    assert "`c3`" in printed
    # The instruction, verbatim from the artifact rather than paraphrased on
    # the page -- two wordings of the same rule drift apart, and the one that
    # is read is not always the one that is maintained.
    assert census["inference"] in printed
    assert "Do not report a p-value computed over the pairs that survived" in (
        census["inference"]
    )
    # And it stays above the table it is about.
    assert printed.index("Left unpaired") < printed.index(
        "accuracy (answered calls)"
    )


def test_a_run_that_answered_nothing_does_not_print_a_discrimination_of_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """``**None**`` in the bold cell that should hold Youden's J.

    Nothing measured is not a measurement of nothing, and this is the one row
    where the difference is the whole finding. The card this diagnostic feeds
    already says "discrimination 0" as its headline -- that is what a judge
    whose verdict ignores the audio scores. A run where no call was answered
    has an undefined J, and the summary printed the bare value, so that cell
    read ``None``: one glance from the number it is the opposite of. The same
    line printed ``None`` beside "p -- pre-registered primary", which is not a
    p-value and is not a null result either.

    Rehearsals answer every call, so these rows had only ever rendered with
    real numbers in them. The shape that reaches them is a paid run whose
    replies broke the response contract -- which is exactly what run
    34008840627 did, 52 times.
    """
    manifest_path, clip_dir = _speech_fixture(tmp_path, clips=5)
    corpus = probe.load_speech_corpus(manifest_path, clip_dir)

    class _NeverAnswers:
        def reset(self) -> None:
            return None

        def judge(self, **_kwargs: object) -> probe.AudioVerdict:
            return probe.AudioVerdict(
                verdict="judge_error",
                partial_score=0.0,
                evidence="",
                confidence=0.0,
                reasoning="",
                judge_error="format_error:missing_field",
            )

    report = probe.build_report(
        identity=_stamped_identity(),
        measured=True,
        repeats=3,
        result=probe.run_measurement(
            perception=_NeverAnswers(),
            clip_dir=tmp_path / "unused",
            repeats=3,
            claims=corpus.claims,
            prerendered=corpus,
        ),
        speech=corpus,
    )
    overall = report["accuracy"]["overall"]
    assert overall["answered"] == 0 and overall["accuracy"] is None
    assert report["accuracy"]["discrimination_j"]["per_call"] is None, (
        "the fixture now yields a computable J, so this test no longer covers "
        "the branch it exists for"
    )

    printed = _render_paid_summary(report, tmp_path, monkeypatch, capsys)
    # Not the word, anywhere. A bare repr in a rendered table is a defect
    # wherever it lands, and the two cells below are where it landed.
    assert "None" not in printed, (
        "a Python repr reached the summary: "
        + repr([line for line in printed.splitlines() if "None" in line])
    )
    assert "| **discrimination (Youden's J)** | **not measured** |" in printed
    assert "(binomial, n=0) | **not measured** |" in printed
    # One vocabulary. "n/a" on the accuracy row and something else two rows
    # down, for the identical condition, is a table a reader has to translate.
    assert "| accuracy (answered calls) | not measured |" in printed
    assert "n/a" not in printed

    # And the other half: a run that did answer must print its numbers, or
    # the fix is a summary that says "not measured" about everything.
    out = tmp_path / "healthy.json"
    assert probe.main([
        "--dry-run", "--quiet", "--repeats", "3",
        "--speech-set", str(manifest_path),
        "--speech-clips", str(clip_dir),
        "--out", str(out),
    ]) == 0
    healthy = _render_paid_summary(
        json.loads(out.read_text(encoding="utf-8")), tmp_path, monkeypatch, capsys
    )
    assert "not measured" not in healthy
    assert "| **discrimination (Youden's J)** | **1.0** |" in healthy


def test_the_dry_run_summary_shows_the_field_exists() -> None:
    step = _step("dry-run", "Summarise")
    assert "stopped early" in step["run"]


def test_the_dispatch_the_document_names_is_a_dispatch_the_workflow_accepts() -> None:
    """A pre-registered input set that the workflow would reject is not a
    pre-registration; it is a plan that gets edited at dispatch time."""
    doc = (
        probe.REPO_ROOT / "tasks" / "rebuilding_grading_task"
        / "330-speech-diagnostic-prereg.md"
    ).read_text(encoding="utf-8")
    inputs = _workflow()[True]["workflow_dispatch"]["inputs"]

    for name, value in [
        ("dry_run", "`false`"),
        ("paid_approval", "`true`"),
        ("repeats", "`3`"),
        ("prompt_arm", "`production`"),
        ("corpus", "`speech`"),
    ]:
        assert f"| `{name}` | {value} |" in doc, name
        assert name in inputs, name

    assert "production" in inputs["prompt_arm"]["options"]
    assert "speech" in inputs["corpus"]["options"]
    # 60 calls, and the document's arithmetic has to be the workflow's.
    assert int(inputs["repeats"]["default"]) == 3
    assert "20 × 3 × 1 = 60" in doc


def test_the_column_saying_which_inputs_must_be_typed_is_derived() -> None:
    """§0's third column is the one the operator acts on, and it was prose.

    The table has a "does this differ from the default?" column. Three rows say
    yes, two say no, and the two that say no are the two the operator will not
    type -- that is what the column is *for*. So a default moving underneath it
    does not produce a wrong document so much as a wrong dispatch.

    Neither 같음 row is a spending risk on its own. ``repeats`` is pinned by the
    test above, and if ``prompt_arm``'s default became ``both`` the measurer
    refuses that combination with a speech set before it resolves the identity,
    so the run stops rather than buying 120 calls. But it stops, and stopping is
    not what §0 describes: "아래 다섯 개 말고 다른 조합은 이 사전등록이 아니다."

    The 다름 rows carry the other half. ``dry_run`` defaults to ``true``, and
    that default is what makes a careless dispatch free; if it ever became
    ``false`` this column would still be telling the operator to type something
    the workflow no longer needs telling.

    Every row is right today. Nothing checked that, which is the whole shape:
    a true sentence with no guard is only true until someone edits elsewhere.
    """
    doc = (
        probe.REPO_ROOT / "tasks" / "rebuilding_grading_task"
        / "330-speech-diagnostic-prereg.md"
    ).read_text(encoding="utf-8")
    inputs = _workflow()[True]["workflow_dispatch"]["inputs"]

    rows = re.findall(
        r"^\| `([a-z_]+)` \| `([^`]+)` \| (✅ 다름|같음) \|$", doc, re.MULTILINE
    )
    assert [name for name, _, _ in rows] == [
        "dry_run",
        "paid_approval",
        "repeats",
        "prompt_arm",
        "corpus",
    ], "§0's dispatch table is no longer the five inputs it pre-registers"

    for name, stated_value, stated_verdict in rows:
        default = str(inputs[name]["default"]).lower()
        differs = default != stated_value.lower()
        assert differs == (stated_verdict == "✅ 다름"), (
            f"§0 says `{name}` is {stated_verdict!r} from the default, but the "
            f"workflow's default is {inputs[name]['default']!r} and the "
            f"pre-registered value is {stated_value!r}. The column tells the "
            f"operator which inputs to type; re-derive it, do not re-word it."
        )


def test_the_prompt_ab_document_names_a_dispatch_the_workflow_accepts() -> None:
    """333's §0 table, checked the same two ways 330's is.

    The row that matters is ``prompt_arm``. It stays ``production`` while the
    run makes two arms, because the second arm is opened by the document and
    not by that flag. It is the one line in this table an operator is most
    likely to "correct" on the way to dispatching, and correcting it costs a
    run: ``observation`` and ``both`` are both refused with a speech set.
    """
    doc = (
        probe.REPO_ROOT / "tasks" / "rebuilding_grading_task"
        / "333-speech-prompt-ab-prereg.md"
    ).read_text(encoding="utf-8")
    inputs = _workflow()[True]["workflow_dispatch"]["inputs"]

    rows = re.findall(
        r"^\| `([a-z_]+)` \| `([^`]+)` \| (✅ 다름|같음) \|$", doc, re.MULTILINE
    )
    assert [name for name, _, _ in rows] == [
        "dry_run",
        "paid_approval",
        "repeats",
        "prompt_arm",
        "corpus",
    ], "333's dispatch table is no longer the five inputs it pre-registers"

    stated = dict((name, value) for name, value, _ in rows)
    assert stated["prompt_arm"] == "production"
    assert stated["corpus"] == "speech-prompt-ab"
    assert stated["corpus"] in inputs["corpus"]["options"]

    for name, stated_value, stated_verdict in rows:
        default = str(inputs[name]["default"]).lower()
        differs = default != stated_value.lower()
        assert differs == (stated_verdict == "✅ 다름"), (
            f"333 §0 says `{name}` is {stated_verdict!r} from the default, but "
            f"the workflow's default is {inputs[name]['default']!r}"
        )

    # The document's arithmetic has to be the workflow's, and it is the count
    # the approval record will authorise.
    published = json.loads(
        (probe.REPO_ROOT / SPEECH_MANIFEST_REPO_PATH).read_text(encoding="utf-8")
    )
    criteria = len(published["claims"])
    repeats = int(inputs["repeats"]["default"])
    arms = len(probe.PROMPT_ARMS)
    assert f"{criteria} × {repeats} × {arms} = {criteria * repeats * arms}" in doc
    assert f"| 진단 종류 | `{probe.SPEECH_PROMPT_AB_KIND}` |" in doc


def test_the_prompt_ab_document_pins_the_grader_this_checkout_computes() -> None:
    """The pinned fingerprint is this tree's, not a value copied from 330.

    The first draft of this test asserted 333 and 330 pinned the same grader.
    They no longer do: ``compute_grader_source_hash`` hashes every ``core/**``
    module by content, so a commit that only touched cost accounting moved it.
    Asserting the old equality would have held the A/B to a fingerprint the
    run can no longer produce -- the probe would have refused at dispatch,
    after the job started, instead of here.

    So the check is against what this checkout actually computes. While 333
    says it has not run, a core change turns this red and the document has to
    be re-pinned before anything is bought. Once it has run the pin is history
    and must not be edited, which is what the status line gates.
    """
    prereg = probe.REPO_ROOT / "tasks" / "rebuilding_grading_task"
    document = prereg / "333-speech-prompt-ab-prereg.md"
    if "상태: 아직 실행하지 않음" not in document.read_text(encoding="utf-8"):
        pytest.skip("333 has run; its pin records what was bought, not this tree")
    assert probe.grader_pin_stated_in(document) == probe.grader_source_hash()


def test_the_prompt_ab_document_says_where_it_parted_from_the_single_arm_run() -> None:
    """A fingerprint that differs from 330's has to be explained in the document.

    Silence here would read as "same grader as 331" to anyone putting the two
    result sets side by side. The divergence is fine -- the A/B's control arm
    runs inside the same job -- but only because that is written down.
    """
    prereg = probe.REPO_ROOT / "tasks" / "rebuilding_grading_task"
    document = prereg / "333-speech-prompt-ab-prereg.md"
    text = document.read_text(encoding="utf-8")
    single_arm = probe.grader_pin_stated_in(prereg / "330-speech-diagnostic-prereg.md")
    if probe.grader_pin_stated_in(document) == single_arm:
        return
    assert single_arm[:8] in text, (
        "333 pins a different grader from 330 and does not name 330's, so the "
        "difference is invisible to whoever reads the two results together"
    )
    assert "core/cost_metering.py" in text and "#444" in text, (
        "the document has to say which commit moved the fingerprint; "
        "'it changed' is not a record"
    )


# ── The per-claim table, which is where the primary analysis lives ───────
#
# Third instance of one bug: an analysis function defaulting to the tone
# corpus while the speech corpus runs. The per-call figures stay healthy,
# so nothing looks wrong until someone asks for the number 330 called
# primary and finds it was never computed.


def test_every_claim_that_ran_has_a_row(tmp_path: Path) -> None:
    manifest_path, clip_dir = _speech_fixture(tmp_path, clips=4)
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
        identity=_stamped_identity(),
        measured=False,
        repeats=3,
        result=result,
        speech=corpus,
    )
    acc = report["accuracy"]
    assert set(acc["by_claim"]) == {c.claim_id for c in corpus.claims}
    assert acc["stability"]["claims"] == len(corpus.claims)
    # Not merely present: actually usable. A table of rows whose majority is
    # None would satisfy a count and still leave the primary test empty.
    assert acc["discrimination_j"]["per_claim_majority"] is not None
    assert acc["pre_registered_binomial"]["n"] == len(corpus.claims)


def test_a_tone_claim_id_does_not_stand_in_for_a_speech_one(
    tmp_path: Path,
) -> None:
    """The failure was silent because the ids simply did not intersect."""
    manifest_path, clip_dir = _speech_fixture(tmp_path, clips=2)
    corpus = probe.load_speech_corpus(manifest_path, clip_dir)
    assert not ({c.claim_id for c in corpus.claims}
                & {c.claim_id for c in probe.CLAIMS})
    calls = [
        {
            "claim_id": claim.claim_id,
            "holds": claim.holds,
            "family": claim.family,
            "pair_id": claim.pair_id,
            "verdict": "pass" if claim.holds else "fail",
            "outcome": probe.OUTCOME_CORRECT,
            "confidence": None,
            "unanswered_kind": None,
        }
        for claim in corpus.claims
    ]
    assert probe.summarise(calls)["by_claim"] == {}
    assert probe.summarise(calls, claims=corpus.claims)["by_claim"]


def test_the_published_speech_set_fills_the_primary_analysis() -> None:
    """Against the real manifest, not a fixture: 20 claims, 20 rows."""
    manifest = probe.REPO_ROOT / SPEECH_MANIFEST_REPO_PATH
    claims = json.loads(manifest.read_text(encoding="utf-8"))["claims"]
    assert len(claims) == 20
    doc = (
        probe.REPO_ROOT / "tasks" / "rebuilding_grading_task"
        / "330-speech-diagnostic-prereg.md"
    ).read_text(encoding="utf-8")
    assert "`accuracy.pre_registered_binomial`" in doc


# ── Two tests, both named before either has a value ──────────────────────


def test_the_primary_test_is_the_one_the_document_calls_primary() -> None:
    doc = (
        probe.REPO_ROOT / "tasks" / "rebuilding_grading_task"
        / "330-speech-diagnostic-prereg.md"
    ).read_text(encoding="utf-8")
    # ``n <= 20``, not ``n = 20``. The hedged-majority exclusion was always in
    # the document; the label was not, and a table cell reading "n = 20" is
    # what a run with n = 14 gets written up as.
    assert "이항검정 (n ≤ 20, p = 0.5)" in doc
    assert "이항검정 (n = 20" not in doc
    assert "`accuracy.permutation`" in doc
    step = _step("measure", "Summarise")
    assert "pre-registered primary" in step["run"]
    assert "pre-specified secondary" in step["run"]


@pytest.mark.parametrize(
    "correct, n, expected",
    [
        (20, 20, 1 / 2 ** 20),
        (10, 20, 0.5880985260009766),
        (0, 20, 1.0),
        (1, 1, 0.5),
    ],
)
def test_the_binomial_is_the_binomial(correct: int, n: int, expected: float) -> None:
    by_claim = {
        f"c{i}": {
            "holds": True,
            "majority": "pass",
            "majority_outcome": (
                probe.OUTCOME_CORRECT if i < correct else probe.OUTCOME_FALSE_FAIL
            ),
        }
        for i in range(n)
    }
    got = probe.binomial_majority_test(by_claim)
    assert got["n"] == n
    assert got["correct"] == correct
    assert got["p_one_sided"] == pytest.approx(expected)


def test_a_hedged_majority_is_not_scored_either_way() -> None:
    """`partial` is a refusal to answer a binary question, so it leaves the
    denominator rather than being rounded into whichever side is convenient."""
    by_claim = {
        "a": {"majority": "pass", "majority_outcome": probe.OUTCOME_CORRECT},
        "b": {"majority": "partial", "majority_outcome": probe.OUTCOME_HEDGED},
        "c": {"majority": None, "majority_outcome": None},
    }
    got = probe.binomial_majority_test(by_claim)
    assert got["claims_with_a_majority"] == 2
    assert got["hedged_majorities_excluded"] == 1
    assert got["n"] == 1 and got["correct"] == 1


def test_a_test_with_nothing_to_test_returns_null_not_one() -> None:
    got = probe.binomial_majority_test({})
    assert got["n"] == 0
    assert got["p_one_sided"] is None
    assert got["smallest_attainable_p"] is None


def test_the_repeats_are_collapsed_before_the_test_not_after() -> None:
    """60 calls are not 60 trials. Three calls about one clip ask one
    question, and counting them separately manufactures significance."""
    source = (
        probe.REPO_ROOT / "batch-runner" / "scripts"
        / "measure_audio_grading_accuracy.py"
    ).read_text(encoding="utf-8")
    assert "binomial_majority_test(by_claim)" in source
    doc = (
        probe.REPO_ROOT / "tasks" / "rebuilding_grading_task"
        / "330-speech-diagnostic-prereg.md"
    ).read_text(encoding="utf-8")
    assert "반복 3회를 독립 시행으로 세면" in doc


def test_every_analysis_field_the_document_names_exists_in_a_real_report(
    tmp_path: Path,
) -> None:
    """The general form of the bug this file keeps catching.

    Each specific case -- the primary binomial, the pair census, the flip
    rate's denominator -- was a field 330 promised and the report did not
    write. A named field that does not exist is how "the analysis I
    pre-registered" quietly becomes "the analysis I did", and the substring
    assertions elsewhere only guard the paths someone thought to list.

    So: resolve every ``accuracy.*`` path the document names against a report
    the script actually produced. A renamed field breaks this whether or not
    anyone remembers to update a test. Scope is the analysis section because
    that is where all of those defects were; the delivery evidence needs a
    wired run and is checked against the published clips instead.
    """
    doc = (
        probe.REPO_ROOT / "tasks" / "rebuilding_grading_task"
        / "330-speech-diagnostic-prereg.md"
    ).read_text(encoding="utf-8")
    named = sorted(set(re.findall(r"`(accuracy(?:\.[a-z_]+)+)`", doc)))
    assert named, "the document names no analysis fields at all"

    out = tmp_path / "report.json"
    probe.main(["--dry-run", "--quiet", "--repeats", "3", "--out", str(out)])
    report = json.loads(out.read_text(encoding="utf-8"))
    for path in named:
        node = report
        for part in path.split("."):
            assert isinstance(node, dict) and part in node, (
                f"330 names `{path}`, but the report has no `{part}` there"
            )
            node = node[part]


def test_the_accuracy_never_appears_without_its_denominator() -> None:
    """328 published 47.1% on 17 answers out of 60 and the 17 was nowhere near
    the number. 330 §4 requires both figures side by side, so the summary a
    person reads has to carry the rate, not only the artifact."""
    body = _step("measure", "Summarise")["run"]
    assert "response rate" in body
    assert "answers it was computed from" in body
    # This arm's rate, beside this arm's accuracy. The run's call count is a
    # different number and stays sourced from the cost block.
    assert "acc['overall']['response_rate']" in body
    assert "acc['overall']['calls']" not in body
    doc = (
        probe.REPO_ROOT / "tasks" / "rebuilding_grading_task"
        / "330-speech-diagnostic-prereg.md"
    ).read_text(encoding="utf-8")
    assert "두 숫자를 항상 같이 낸다" in doc
    # And the fields the summary prints are ones the report actually writes.
    summary = probe.summarise(_calls(lambda claim: "judge_error"))
    assert summary["overall"]["response_rate"] == 0.0
    assert summary["overall"]["answered"] == 0


def test_a_judge_that_never_listened_is_visible_as_a_count() -> None:
    """Ten pairs of `pass` scores 50% on a balanced corpus. Accuracy alone
    reads that as a near miss; the pair census reads it as zero pairs told
    apart."""
    by_claim = {}
    for index in range(10):
        for holds in (True, False):
            by_claim[f"p{index}_{holds}"] = {
                "holds": holds,
                "pair_id": f"p{index}",
                "majority": "pass",
            }
    got = probe.pair_consistency(by_claim)
    assert got["pairs"] == 10
    assert got["answered_differently"] == 0
    assert got["answered_identically"] == 10
    assert got["identical_by_verdict"] == {"pass": 10}
    assert got["incomplete"] == 0


def test_a_pair_told_apart_counts_as_told_apart() -> None:
    by_claim = {
        "a_t": {"holds": True, "pair_id": "a", "majority": "pass"},
        "a_f": {"holds": False, "pair_id": "a", "majority": "fail"},
        # Same verdict on both sides, and it is not `pass`.
        "b_t": {"holds": True, "pair_id": "b", "majority": "fail"},
        "b_f": {"holds": False, "pair_id": "b", "majority": "fail"},
    }
    got = probe.pair_consistency(by_claim)
    assert got["answered_differently"] == 1
    assert got["identical_by_verdict"] == {"fail": 1}


def test_a_pair_missing_a_side_is_neither_told_apart_nor_confused() -> None:
    """Counting it as separated would credit a pair that was never answered;
    counting it as identical would blame one."""
    by_claim = {
        "a_t": {"holds": True, "pair_id": "a", "majority": None},
        "a_f": {"holds": False, "pair_id": "a", "majority": "fail"},
    }
    got = probe.pair_consistency(by_claim)
    assert got["incomplete"] == 1
    assert got["answered_differently"] == 0
    assert got["answered_identically"] == 0


def test_the_pair_census_covers_every_pair_of_the_speech_set() -> None:
    """Ten clips, ten pairs, read from the committed manifest. A census that
    silently saw fewer would understate how much of the corpus was never
    separated."""
    manifest = probe.REPO_ROOT / SPEECH_MANIFEST_REPO_PATH
    claims = json.loads(manifest.read_text(encoding="utf-8"))["claims"]
    by_claim = {
        claim["claim_id"]: {
            "holds": claim["holds"],
            "pair_id": claim["pair_id"],
            # Answered correctly on both sides, so every pair is separated.
            "majority": "pass" if claim["holds"] else "fail",
        }
        for claim in claims
    }
    got = probe.pair_consistency(by_claim)
    assert got["pairs"] == 10
    assert got["answered_differently"] == 10
    assert got["answered_identically"] == 0
    assert got["incomplete"] == 0


def test_the_summary_prints_the_pairs_it_told_apart() -> None:
    body = _step("measure", "Summarise")["run"]
    assert "pairs told apart" in body
    assert "both sides the same verdict" in body
    doc = (
        probe.REPO_ROOT / "tasks" / "rebuilding_grading_task"
        / "330-speech-diagnostic-prereg.md"
    ).read_text(encoding="utf-8")
    assert "accuracy.pair_consistency" in doc
    assert "answered_differently" in doc


def test_the_flip_rate_uses_the_denominator_it_is_compared_against() -> None:
    """19.35% was flips over *pairs of runs*. Three repeats give three pairs
    per claim, so a claim that flips once is one third of that figure and all
    of the claim-level one."""
    by_claim = {
        "steady": {"verdicts": ["pass", "pass", "pass"]},
        "one_flip": {"verdicts": ["pass", "pass", "fail"]},
    }
    got = probe.repeat_flip_rate(by_claim)
    # 6 pairs, 2 of them disagree (pass/fail twice within `one_flip`).
    assert got["comparable_pairs"] == 6
    assert got["flips"] == 2
    assert got["flip_rate_pct"] == pytest.approx(100.0 * 2 / 6)
    # The other denominator, kept beside it and labelled, not instead of it.
    assert got["claims_that_ever_flipped"] == 1
    assert got["prior_audio_cohort_pct"] == pytest.approx(19.3548, abs=1e-3)


def test_the_earlier_figure_quoted_here_is_the_earlier_figure() -> None:
    """The comparison is only worth printing if the number it is set against
    is the one the repeat study actually produced."""
    prior = (
        probe.REPO_ROOT / "batch-runner" / "tests"
        / "test_audio_repeat_variation_bounds_what_it_can.py"
    ).read_text(encoding="utf-8")
    assert "19.3548" in prior
    assert "verdict_flip_rate_pct" in prior
    got = probe.repeat_flip_rate({})
    assert got["prior_audio_cohort_pct"] == pytest.approx(19.3548, abs=1e-3)


def test_a_pair_missing_an_answer_is_not_an_agreement() -> None:
    """An unanswered repeat did not agree with its partner and did not
    disagree; folding it in either direction reports steadiness that was
    never measured."""
    by_claim = {
        "half_answered": {"verdicts": ["pass", "judge_error", "fail"]},
        "silent": {"verdicts": ["judge_error", "judge_error", "judge_error"]},
    }
    got = probe.repeat_flip_rate(by_claim)
    assert got["comparable_pairs"] == 1
    assert got["flips"] == 1
    assert got["pairs_dropped_for_a_missing_answer"] == 5
    assert got["flip_rate_pct"] == pytest.approx(100.0)


def test_a_run_with_nothing_to_compare_reports_null_not_zero() -> None:
    got = probe.repeat_flip_rate({"silent": {"verdicts": ["judge_error"]}})
    assert got["comparable_pairs"] == 0
    assert got["flip_rate_pct"] is None
    assert got["flips"] == 0


def test_the_flip_rate_travels_with_the_report() -> None:
    """It has to be in the artifact, not left as a division a reader might do
    with the wrong two fields."""
    # One claim answered three times, disagreeing once: three pairs, two of
    # which are pass/fail.
    calls = []
    for index, verdict in enumerate(("fail", "pass", "pass")):
        call = dict(_calls(lambda claim: verdict)[0])
        call["repeat"] = index + 1
        calls.append(call)
    summary = probe.summarise(calls, claims=probe.CLAIMS[:1])
    flips = summary["stability"]["repeat_flips"]
    assert flips["unit"] == "one pair of repeats for one claim"
    assert flips["comparable_pairs"] == 3
    assert flips["flips"] == 2
    assert flips["claims_that_ever_flipped"] == 1


def test_the_summary_prints_both_denominators_and_says_which_is_which() -> None:
    """Printing one alone is how the units got confused in the first place."""
    body = _step("measure", "Summarise")["run"]
    assert "repeat flip rate" in body
    assert "claims that ever flipped" in body
    assert "different denominator" in body
    assert "prior_audio_cohort_pct" in body


def test_the_document_names_the_field_the_comparison_uses() -> None:
    """A pre-registration that says "comparable" without saying to which
    number leaves the choice for after the numbers exist."""
    doc = (
        probe.REPO_ROOT / "tasks" / "rebuilding_grading_task"
        / "330-speech-diagnostic-prereg.md"
    ).read_text(encoding="utf-8")
    assert "accuracy.stability.repeat_flips.flip_rate_pct" in doc
    assert "claims_that_ever_flipped" in doc
    assert "pairs_dropped_for_a_missing_answer" in doc
    # And the field the document names is the field the report writes.
    summary = probe.summarise(_calls(lambda claim: "pass"))
    assert "flip_rate_pct" in summary["stability"]["repeat_flips"]


def test_a_foreign_model_answering_is_bannered_and_not_merely_listed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """The summary printed both halves of an identity check and did neither.

    Its header states the pinned model. Four hundred lines later a table row
    lists what actually answered. Nothing compared them, so a deployment
    repointed at a different model behind the same name would have produced a
    summary that reads clean and reports somebody else's answers under `330`
    §2's pin.

    Ground truth for the comparison is the real paid run `34008840627`, whose
    delivery block reads `"response_models": ["gpt-audio-1.5"]` -- exactly the
    pinned deployment, no version suffix. That is why an exact match is safe
    here and why the check is gated on `measured`: a rehearsal answers with
    `stub-not-a-model` by design and must stay quiet.

    Executed in both directions, plus the two ways a naive comparison would
    cry wolf.
    """
    manifest_path, clip_dir = _speech_fixture(tmp_path, clips=3)
    out = tmp_path / "probe.json"
    assert probe.main([
        "--dry-run", "--quiet", "--repeats", "1",
        "--speech-set", str(manifest_path),
        "--speech-clips", str(clip_dir),
        "--out", str(out),
    ]) == 0
    rehearsal = json.loads(out.read_text(encoding="utf-8"))
    pinned = rehearsal["pins"]["audio_deployment"]
    assert rehearsal["delivery"]["response_models"] == ["stub-not-a-model"], (
        "the rehearsal no longer answers with the stub, so the gate below is "
        "not being exercised on the shape it was written for"
    )

    def _page(report: dict) -> str:
        return _render_paid_summary(report, tmp_path, monkeypatch, capsys)

    BANNER = "A model other than the pinned"

    # A rehearsal answers with a name that is not the pin, on purpose. Warning
    # on every dry run would train a reader to scroll past the banner.
    assert BANNER not in _page(rehearsal)

    def _measured(models: list) -> dict:
        report = json.loads(json.dumps(rehearsal))
        report["measured"] = True
        report["delivery"]["measured"] = True
        report["delivery"]["response_models"] = models
        return report

    # The pinned model, and nothing else: silence.
    assert BANNER not in _page(_measured([pinned]))

    # Nothing answered at all. That is a real condition with its own reporting
    # -- "not measured" in the accuracy rows -- and it is not a foreign model.
    # A whole-list comparison would have called `[]` an impostor.
    assert BANNER not in _page(_measured([]))

    # A foreign model, alone.
    printed = _page(_measured(["gpt-4o-audio-preview"]))
    assert BANNER in printed
    assert f"`{pinned}`" in printed
    assert "gpt-4o-audio-preview" in printed
    assert "not the" in printed and "pre-registered run" in printed
    assert printed.index(BANNER) < printed.index("### By family"), (
        "the banner has to precede the numbers it disqualifies"
    )

    # A foreign model mixed in with the pinned one. Some calls being right does
    # not make the run the registered one.
    mixed = _page(_measured([pinned, "gpt-4o-audio-preview"]))
    assert BANNER in mixed
    assert "gpt-4o-audio-preview" in mixed


# ── The 334 report against the bytes it was written from ─────────────────
#
# 334 quotes about thirty figures out of a run that will never happen again.
# Nothing else in this repository checks a report against its own raw file,
# which is how a number in a document drifts from the number that was bought.
# This is not a parser for the document; it is the headline set, pinned.


def _report_334() -> tuple[str, dict]:
    here = probe.REPO_ROOT / "tasks" / "rebuilding_grading_task"
    text = (here / "334-the-arm-that-broke-the-format.md").read_text(
        encoding="utf-8"
    )
    raw = json.loads(
        (here / "334-audio-accuracy-measured.json").read_text(encoding="utf-8")
    )
    return text, raw


def test_the_334_report_quotes_the_run_it_preserved() -> None:
    """Every headline figure in 334 comes out of 334's own JSON."""
    text, raw = _report_334()
    per_call = raw["arm_comparison"]
    per_claim = per_call["per_claim_majority"]

    # The run itself.
    assert raw["calls_planned"] == 120 and len(raw["calls"]) == 120
    assert "120" in text
    assert raw["stopped"] is None
    assert "`stopped: null`" in text
    assert raw["pins"]["grader_source_sha256"].startswith("7506ce5008bd")
    assert "7506ce5008bd" in text

    # The finding: the treatment arm stopped answering.
    obs = per_call["observation"]
    assert obs["unanswered_by_kind"]["read_failure"] == 51
    assert "51" in text
    assert obs["response_rate"] == 0.15
    assert "15%" in text or "15.0%" in text
    assert obs["unanswered_by_kind"]["provider_failure"] == 0
    assert obs["unanswered_by_kind"]["declined_to_judge"] == 0

    # The pre-registered primary metric, and the claim counts under it.
    assert per_claim["unit"] == "claim" and per_claim["pairs"] == 20
    assert round(per_claim["mcnemar_exact_p"], 4) == 0.0654
    assert "0.0654" in text
    assert per_claim["production"]["settled"] == 20
    assert per_claim["production"]["correct"] == 12
    assert per_claim["observation"]["settled"] == 7
    assert per_claim["observation"]["correct"] == 5
    assert per_claim["observation"]["unsettled"]["no_answer_at_all"] == 13
    assert "13" in text
    assert per_claim["constant_fail_baseline"]["accuracy"] == 0.5

    # Cost stays unmeasured rather than zero.
    assert raw["cost"]["estimated_cost_usd"] is None
    assert raw["cost"]["pricing_complete"] is False
    assert "`null`" in text
    assert "0달러가 아니다" in text


def test_the_334_report_does_not_overwrite_what_331_bought() -> None:
    """331's numbers are quoted as history and are still 331's numbers."""
    text, _ = _report_334()
    here = probe.REPO_ROOT / "tasks" / "rebuilding_grading_task"
    prior = json.loads(
        (here / "331-audio-accuracy-measured.json").read_text(encoding="utf-8")
    )
    overall = prior["accuracy"]["overall"]
    assert overall["correct"] == 36 and overall["answered"] == 59
    assert round(overall["accuracy"], 4) == 0.6102
    assert "0.610" in text
    # And the document says out loud what 333 section 7 required of it.
    assert "역사적 참고치" in text


# ── 337: the format-safe candidate, and the doors only it opens ──
#
# 334's observation arm returned no readable JSON on 51 of 60 calls; 335
# bought three of those bodies and found no braces at all, a parser that
# stopped on character zero and ``finish_reason: stop``. The model did not
# break the envelope -- it never wrote one, because the header's first
# instruction told it to write down what it heard and named nowhere to write
# it. These tests hold the candidate that names a destination, and the doors
# that only a document can open.


_PILOT_DOC = (
    probe.REPO_ROOT / "tasks" / "rebuilding_grading_task"
    / "337-format-safe-observation-pilot.md"
)


def _doc_sha256(text: str, constant: str) -> str:
    """The digest a pre-registration pins for ``constant``."""
    match = re.search(
        rf"`{re.escape(constant)}`,\s*sha256\s*`([0-9a-f]{{64}})`", text
    )
    assert match, f"the document pins no sha256 for {constant}"
    return match.group(1)


def test_the_candidate_is_the_bought_header_plus_exactly_one_sentence() -> None:
    """"One sentence" is a claim, so it is checked rather than asserted in prose.

    The candidate is reconstructed *backwards*: delete the added sentence
    from V2 and what is left has to be V1 byte for byte. Comparing forwards
    -- building V1 + sentence and checking it equals V2 -- would pass even if
    V2 had been edited somewhere else, because both sides would carry the
    edit. This direction cannot.

    V1 is pinned to the digest 333 registered and 334 paid for. If that moves,
    the candidate is no longer "the bought header plus a sentence" and the
    comparison in 338 would be measuring two changes at once.
    """
    v1 = probe.SPEECH_OBSERVATION_HEADER
    v2 = probe.SPEECH_OBSERVATION_HEADER_V2
    sentence = probe.SPEECH_OBSERVATION_DESTINATION_SENTENCE

    assert hashlib.sha256(v1.encode("utf-8")).hexdigest() == (
        "b9bfaaa2e5f68d43ceb1116fe86eafc052716232d018eda3efaa1aa6412d066c"
    ), "the header 334 bought has changed; 337 is no longer a one-sentence delta"

    assert v2.count(sentence) == 1
    assert v2.replace(" " + sentence, "", 1) == v1
    assert len(v2) - len(v1) == len(sentence) + 1

    # And the document pins what this checkout builds, so a header edited
    # after the pre-registration was written cannot be dispatched under it.
    text = _PILOT_DOC.read_text(encoding="utf-8")
    assert _doc_sha256(text, "SPEECH_OBSERVATION_HEADER_V2") == (
        hashlib.sha256(v2.encode("utf-8")).hexdigest()
    )


def test_the_candidate_names_a_destination_and_does_not_weaken_the_contract(
) -> None:
    """What 335 diagnosed, and the narrowest thing that answers it.

    The failure was an instruction with no destination sitting in front of a
    contract that forbids prose. The fix has to add a destination *without*
    softening the contract, because a candidate that also relaxed "no prose"
    would pass the pilot for a reason nobody registered.
    """
    v1 = probe.SPEECH_OBSERVATION_HEADER
    v2 = probe.SPEECH_OBSERVATION_HEADER_V2
    sentence = probe.SPEECH_OBSERVATION_DESTINATION_SENTENCE

    # The unbound imperative 335 found is still there -- the candidate does
    # not stop asking for the transcript, it says where to put it.
    assert "write down what it actually contains" in _intervention(v1)
    assert "write down what it actually contains" in _intervention(v2)
    assert '"reasoning"' in sentence
    assert "nowhere else" in sentence

    # core's contract is the last word in both arms, byte for byte and once.
    for header in (v1, v2):
        assert header.endswith(AUDIO_RESPONSE_CONTRACT)
        assert header.count(AUDIO_RESPONSE_CONTRACT) == 1

    # And the destination is stated where the instruction that needs it is --
    # at the end of the FIRST paragraph, which is the one that asks for the
    # transcript. Stated after the contract instead, it would be a second
    # instruction about the reply arriving after the reply has been described.
    paragraphs = v2.split("\n\n")
    assert paragraphs[1].startswith("FIRST,")
    assert paragraphs[1].endswith(sentence)
    assert paragraphs[-1] == AUDIO_RESPONSE_CONTRACT

    # The added sentence lands in the intervention, not inside core's string.
    assert sentence not in AUDIO_RESPONSE_CONTRACT


def test_the_candidate_leaks_no_answer_either() -> None:
    """The same guard 333 wrote, run against the new header.

    A guard that only covers the header it was written for stops being a
    guard the moment a second one exists.
    """
    discriminating = _pair_discriminating_tokens()
    assert len(discriminating) >= 18

    tokens = set(
        re.findall(
            r"[a-z]+", _intervention(probe.SPEECH_OBSERVATION_HEADER_V2).lower()
        )
    )
    leaked = sorted(tokens & discriminating)
    assert not leaked, f"the candidate header hands over: {leaked}"

    # The added sentence on its own, so a future edit to the rest of the
    # header cannot mask a leak introduced here.
    added = set(
        re.findall(
            r"[a-z]+", probe.SPEECH_OBSERVATION_DESTINATION_SENTENCE.lower()
        )
    )
    assert not added & discriminating

    # The gap 333 recorded is still the gap: the word-order pair contributes
    # nothing, so this guard cannot speak for it. Pinned so that it stays a
    # known hole rather than becoming an unnoticed one.
    manifest = json.loads(
        (
            probe.REPO_ROOT / "tasks" / "rebuilding_grading_task"
            / "330-speech-verification-manifest.json"
        ).read_text(encoding="utf-8")
    )
    by_pair: dict[str, list[str]] = {}
    for claim in manifest["claims"]:
        by_pair.setdefault(claim["pair_id"], []).append(claim["criterion"])
    empty = sorted(
        pair for pair, criteria in by_pair.items()
        if not set(re.findall(r"[a-z]+", criteria[0].lower()))
        ^ set(re.findall(r"[a-z]+", criteria[1].lower()))
    )
    assert empty == ["powder_order"], (
        "the set of pairs this guard cannot cover changed; 337 section 3 "
        "names powder_order and only powder_order"
    )


def test_the_candidate_needs_no_change_to_the_parser(tmp_path: Path) -> None:
    """The reason ``reasoning`` was chosen, checked against core's parser.

    337 section 3 requires that routing the transcript needs no edit to
    ``core/perception/audio.py`` -- the instruction not to make the parser
    lenient in order to make the candidate pass. So the claim is tested
    against the real parser: a verdict whose ``reasoning`` is far longer than
    any transcript still comes back as a verdict, with no ``judge_error``.

    ``evidence`` is the field this rules out: core slices it to 200
    characters, so a transcript sent there would be fighting a length limit
    that has nothing to do with the question.
    """
    _, clip_dir = _speech_fixture(tmp_path, clips=1)
    audio = next(clip_dir.glob("*.sent.wav"))

    transcript = "the speaker said seventeen crates " * 200

    class _LongReasoning:
        def __init__(self) -> None:
            self.chat = type("_Chat", (), {"completions": self})()

        def create(self, **kwargs: object) -> object:
            return probe._StubResponse(
                json.dumps({
                    "verdict": "pass",
                    "partial_score": 1.0,
                    "evidence": "heard it",
                    "confidence": 0.9,
                    "reasoning": transcript,
                }),
                b64_chars=0,
            )

    perception = AudioPerception(
        client=_LongReasoning(),
        deployment="gpt-audio-1.5",
        call_cap=AUDIO_CALL_CAP,
        trim_seconds=AUDIO_TRIM_SECONDS,
    )
    verdict = perception.judge(criterion="anything", audio_path=str(audio))
    assert verdict.verdict == "pass"
    assert verdict.judge_error is None
    assert verdict.api_call_count == 1

    # And the parser is not being asked to accept anything new: the same
    # response with a *bad* verdict word is still refused.
    class _BadVerdict(_LongReasoning):
        def create(self, **kwargs: object) -> object:
            return probe._StubResponse(
                json.dumps({
                    "verdict": "probably",
                    "partial_score": 1.0,
                    "evidence": "heard it",
                    "confidence": 0.9,
                    "reasoning": transcript,
                }),
                b64_chars=0,
            )

    strict = AudioPerception(
        client=_BadVerdict(),
        deployment="gpt-audio-1.5",
        call_cap=AUDIO_CALL_CAP,
        trim_seconds=AUDIO_TRIM_SECONDS,
    )
    refused = strict.judge(criterion="anything", audio_path=str(audio))
    assert refused.judge_error is not None


def test_the_pilot_sample_is_what_the_rule_selects() -> None:
    """337 section 4 states a rule and then applies it. This applies it again.

    The rule is positional on purpose -- clips in published order, first
    claim from odd-numbered clips and second from even -- so that no result
    from 334 can reach the sample. Re-deriving it here is what makes that
    checkable: a table typed into a document is a claim about a rule, not the
    rule.
    """
    manifest = json.loads(
        (
            probe.REPO_ROOT / "tasks" / "rebuilding_grading_task"
            / "330-speech-verification-manifest.json"
        ).read_text(encoding="utf-8")
    )
    by_clip: dict[str, list[dict]] = {}
    for claim in manifest["claims"]:
        by_clip.setdefault(claim["clip_id"], []).append(claim)

    selected = []
    for position, clip in enumerate(manifest["clips"][:5], start=1):
        pair = by_clip[clip["clip_id"]]
        assert len(pair) == 2, "the corpus stopped being paired"
        selected.append(pair[0 if position % 2 else 1])

    assert [c["claim_id"] for c in selected] == list(
        probe.pilot_claims_stated_in(_PILOT_DOC)
    )

    # The balance the document reports, recomputed rather than quoted.
    assert sum(1 for c in selected if c["holds"]) == 3
    assert sum(1 for c in selected if not c["holds"]) == 2
    assert len({c["family"] for c in selected}) == 4
    assert len({c["clip_id"] for c in selected}) == 5


def test_the_pilot_document_pins_what_this_checkout_would_dispatch() -> None:
    """Plan, ceiling and repeat count, read out of the document.

    Each of these is a number the run reads from somewhere else at dispatch
    time. Where the document and the code disagree, the run is not the
    registered run, and the disagreement is only visible if something
    compares them.
    """
    text = _PILOT_DOC.read_text(encoding="utf-8")

    assert probe.diagnostic_kind_stated_in(_PILOT_DOC) == (
        probe.SPEECH_FORMAT_PILOT_KIND
    )
    assert probe.SPEECH_NARROWED_KINDS[probe.SPEECH_FORMAT_PILOT_KIND] == 1
    assert "| 반복 | **1** |" in text

    claims = probe.pilot_claims_stated_in(_PILOT_DOC)
    planned = len(claims) * 1 * len(probe.PROMPT_ARMS)
    assert planned == 10
    assert f"**{len(claims)} × 1 × {len(probe.PROMPT_ARMS)} = {planned}**" in text

    cap = probe.SPEECH_REQUEST_CAPS[probe.SPEECH_FORMAT_PILOT_KIND]
    assert cap == 12
    assert f"| **요청 상한** | **{cap}**" in text
    assert planned <= cap

    # The header the registry hands this kind is the one the document pins.
    name, header = probe.SPEECH_TWO_ARM_REGISTRATIONS[
        probe.SPEECH_FORMAT_PILOT_KIND
    ]
    assert name == "SPEECH_OBSERVATION_HEADER_V2"
    assert header is probe.SPEECH_OBSERVATION_HEADER_V2

    # And the grader fingerprint, which moves without anyone here touching it.
    assert probe.grader_source_hash() in text


def _pilot_doc(
    tmp_path: Path,
    *,
    kind: str = probe.SPEECH_FORMAT_PILOT_KIND,
    claims: Sequence[str] | None = ("clip0_yes", "clip1_no"),
    name: str = "pilot.md",
    pin: str | None = None,
) -> Path:
    doc = tmp_path / name
    lines = [f"| 진단 종류 | `{kind}` |"]
    lines.append(f"| 채점기 지문 | `{pin or probe.grader_source_hash()}` |")
    if claims is not None:
        row = ", ".join(f"`{c}`" for c in claims)
        lines.append(f"| 시험 문항 | {row} |")
    doc.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return doc


def test_the_pilot_door_refuses_every_way_of_running_something_else(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A narrowed registration fixes a sample and a repeat count.

    Each refusal here is a way the narrowed run could otherwise have become a
    different run wearing this document's name -- and after the fact, a run
    that measured five claims under a document that fixed a different five is
    indistinguishable from one that did as it said.
    """
    manifest_path, clip_dir = _speech_fixture(tmp_path, clips=3)
    out = tmp_path / "out.json"
    args = _speech_ab_args(tmp_path, manifest_path, clip_dir, out)

    # A kind nobody registered.
    unknown = _pilot_doc(tmp_path, kind="speech-format-pilot-v9", name="u.md")
    assert probe.main([*args, "--speech-prompt-ab", str(unknown)]) == 3
    assert "not a two-arm speech comparison" in capsys.readouterr().err

    # A whole-manifest registration carrying a claim row: the document names
    # a subset the run would ignore.
    whole = _pilot_doc(tmp_path, kind="speech-prompt-ab", name="w.md")
    assert probe.main([*args, "--speech-prompt-ab", str(whole)]) == 3
    assert "carries a claim row" in capsys.readouterr().err

    # The repeat count is the document's, and a mismatch is reported rather
    # than corrected -- correcting it is how a dispatch stops matching a plan
    # without anybody noticing.
    good = _pilot_doc(tmp_path)
    assert probe.main([
        *_speech_ab_args(tmp_path, manifest_path, clip_dir, out)[:2],
        "--repeats", "3",
        "--speech-set", str(manifest_path), "--speech-clips", str(clip_dir),
        "--out", str(out), "--speech-prompt-ab", str(good),
    ]) == 3
    assert "registers 1 repeat(s)" in capsys.readouterr().err

    # A claim the manifest cannot supply.
    absent = _pilot_doc(tmp_path, claims=("clip0_yes", "no_such_claim"),
                        name="a.md")
    assert probe.main([*args, "--speech-prompt-ab", str(absent)]) == 3
    assert "no claim named no_such_claim" in capsys.readouterr().err

    # A claim listed twice is a repeat count written in the wrong place.
    twice = _pilot_doc(tmp_path, claims=("clip0_yes", "clip0_yes"), name="t.md")
    assert probe.main([*args, "--speech-prompt-ab", str(twice)]) == 3
    assert "twice" in capsys.readouterr().err

    # A narrowed kind with no claim row fixes no sample at all.
    empty = _pilot_doc(tmp_path, claims=None, name="e.md")
    assert probe.main([*args, "--speech-prompt-ab", str(empty)]) == 3
    assert "fixes no claims" in capsys.readouterr().err

    assert not out.exists(), "a refused run wrote a report"

    # And the plan is counted against the ceiling before a client exists, so
    # a document whose plan does not fit is refused without spending.
    assert probe.main([*args, "--speech-prompt-ab", str(good)]) == 0
    out.unlink()


def test_a_plan_that_does_not_fit_its_ceiling_is_refused_before_the_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The arithmetic runs before anything is built, let alone sent.

    The ceiling is registered next to the kind, so this cannot be tripped by
    a bad dispatch -- only by a document whose own plan is bigger than the
    number it registered. Checking it early is the difference between finding
    that out for free and finding it out four calls in.
    """
    manifest_path, clip_dir = _speech_fixture(tmp_path, clips=3)
    out = tmp_path / "out.json"
    monkeypatch.setitem(
        probe.SPEECH_REQUEST_CAPS, probe.SPEECH_FORMAT_PILOT_KIND, 3
    )
    built: list[object] = []
    monkeypatch.setattr(
        probe, "TruthfulStub",
        lambda claims: built.append(claims) or pytest.fail("a client was built"),
    )
    doc = _pilot_doc(tmp_path)
    assert probe.main([
        *_speech_ab_args(tmp_path, manifest_path, clip_dir, out),
        "--speech-prompt-ab", str(doc),
    ]) == 3
    err = capsys.readouterr().err
    assert "plans 4 call(s) against a ceiling of 3" in err
    assert not built and not out.exists()


def test_the_two_arms_of_the_candidate_differ_by_the_candidate_and_nothing_else(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Measured off the wire, not off the constants.

    333 checked this for V1 and it is not inherited: the arm swap happens in
    ``apply_arm``, which is shared, but *which* header it swaps in comes from
    the registry, and a registry entry pointing at the wrong string would
    produce a run labelled ``observation`` that sent something else.
    """
    doc = _pilot_doc(
        tmp_path, claims=("clip0_yes", "clip0_no", "clip1_yes"), name="wire.md"
    )
    requests, report = _requests_from_an_ab_dry_run(tmp_path, monkeypatch, doc)

    assert report["pins"]["observation_header_name"] == (
        "SPEECH_OBSERVATION_HEADER_V2"
    )
    assert report["pins"]["observation_header_sha256"] == hashlib.sha256(
        probe.SPEECH_OBSERVATION_HEADER_V2.encode("utf-8")
    ).hexdigest()

    def _parts(request: dict) -> tuple[str, str]:
        text = audio = ""
        for part in request["messages"][0]["content"]:
            if part.get("type") == "text":
                text = part["text"]
            elif part.get("type") == "input_audio":
                audio = (part.get("input_audio") or {}).get("data") or ""
        return text, audio

    assert len(requests) == 6
    pairs = [(requests[i], requests[i + 1]) for i in range(0, 6, 2)]
    deltas = set()
    for production, observation in pairs:
        p_text, p_audio = _parts(production)
        o_text, o_audio = _parts(observation)
        # Same clip, byte for byte. An A/B whose audio moved is not an A/B.
        assert p_audio == o_audio and p_audio
        assert production["model"] == observation["model"]
        assert production.get("modalities") == observation.get("modalities")
        # And no structured-output parameter crept in on either side: 335
        # bought the 400s that say this deployment refuses it.
        assert "response_format" not in production
        assert "response_format" not in observation
        deltas.add(len(o_text) - len(p_text))
        # The contract is not the last thing on the wire -- core appends the
        # criterion after it -- so this checks it is present verbatim and once
        # on both sides. An arm that reworded the contract would still pass a
        # length check.
        for text in (p_text, o_text):
            assert text.count(AUDIO_RESPONSE_CONTRACT) == 1
        assert probe.SPEECH_OBSERVATION_DESTINATION_SENTENCE in o_text
        assert probe.SPEECH_OBSERVATION_DESTINATION_SENTENCE not in p_text

        # The criterion sentence itself is byte-identical, and the *label* in
        # front of it is not: ``apply_arm`` writes "Statement:" where core
        # wrote "Criterion:". That is deliberate -- the observation header
        # calls it "the statement below" -- and it has been in both 333 and
        # 334. It is pinned here because it is invisible to every check those
        # runs made: both words are ten characters, so the "exactly 739
        # characters differ" measurement in 334 section 1 could not have seen
        # it, and no document names it. It is a second difference between the
        # arms, and 337 section 3 now says so.
        _, _, p_tail = p_text.partition(probe.PRODUCTION_CRITERION_MARKER)
        _, _, o_tail = o_text.partition("\n\nStatement:\n")
        assert p_tail and o_tail
        assert p_tail == o_tail, "the criterion itself moved between the arms"
        assert probe.PRODUCTION_CRITERION_MARKER not in o_text
        assert "\n\nStatement:\n" not in p_text
        assert len(probe.PRODUCTION_CRITERION_MARKER) == len("\n\nStatement:\n")

    # One number for every claim: the delta is the header, not the criterion.
    assert len(deltas) == 1
    # 334 measured 739 characters for V1; the candidate adds its one sentence
    # to that and nothing else reaches the wire.
    assert deltas.pop() == 739 + len(
        probe.SPEECH_OBSERVATION_DESTINATION_SENTENCE
    ) + 1


# ── The request ceiling: what it counts, and what a stop keeps ──


def test_a_request_is_counted_before_it_leaves_and_even_if_it_raises() -> None:
    """A request that vanished may well have run.

    Counting on the way back would miss exactly the requests most likely to
    have been billed without an answer, so the counter moves first and a
    failing inner call does not give the slot back.
    """
    class _Angry:
        def __init__(self) -> None:
            self.chat = type("_Chat", (), {"completions": self})()
            self.seen = 0

        def create(self, **kwargs: object) -> object:
            self.seen += 1
            raise RuntimeError("connection reset")

    inner = _Angry()
    wire = probe.WireClient(inner, request_cap=2)
    for _ in range(2):
        with pytest.raises(RuntimeError):
            wire.chat.completions.create(messages=[], model="m")
    assert wire.requests == 2 and inner.seen == 2

    # The third is refused before the inner client is touched at all.
    with pytest.raises(probe.RequestCapReached):
        wire.chat.completions.create(messages=[], model="m")
    assert inner.seen == 2, "a refused request still went out"
    assert wire.requests == 3, (
        "the refused request is counted; the count is 'asked for', and "
        "wire.requests - 1 is 'sent'"
    )


def test_the_ceiling_is_not_swallowed_by_the_judge(tmp_path: Path) -> None:
    """``RequestCapReached`` is a ``BaseException`` for a reason.

    ``AudioPerception.judge`` turns any ``Exception`` into a ``judge_error``
    and the caller moves on to the next claim. A ceiling caught that way
    would become a quiet stream of failures that each still cost a request --
    the opposite of a ceiling.
    """
    _, clip_dir = _speech_fixture(tmp_path, clips=1)
    audio = next(clip_dir.glob("*.sent.wav"))

    class _Never:
        def __init__(self) -> None:
            self.chat = type("_Chat", (), {"completions": self})()

        def create(self, **kwargs: object) -> object:  # pragma: no cover
            raise AssertionError("the ceiling let a request through")

    wire = probe.WireClient(_Never(), request_cap=0)
    perception = AudioPerception(
        client=wire,
        deployment="gpt-audio-1.5",
        call_cap=AUDIO_CALL_CAP,
        trim_seconds=AUDIO_TRIM_SECONDS,
    )
    with pytest.raises(probe.RequestCapReached):
        perception.judge(criterion="anything", audio_path=str(audio))

    assert not issubclass(probe.RequestCapReached, Exception)


def test_a_run_stopped_by_the_ceiling_keeps_what_it_bought(
    tmp_path: Path,
) -> None:
    """Stopping is not discarding -- the same rule 333 section 6 wrote.

    ``calls`` is a local inside ``run_measurement``. Letting the ceiling
    raise past the loop would drop every call already paid for in order to
    report a ceiling the exit code reports anyway, and on a 120-call
    comparison that is the whole run.

    In this script one call is one counted request, so a plan that fits its
    ceiling should never reach here. That is the point: this is what happens
    if it does.
    """
    manifest_path, clip_dir = _speech_fixture(tmp_path, clips=3)
    corpus = probe.load_speech_corpus(manifest_path, clip_dir)
    wire = probe.WireClient(
        probe.TruthfulStub(corpus.claims),
        observation_header=probe.SPEECH_OBSERVATION_HEADER_V2,
        request_cap=2,
    )
    perception = AudioPerception(
        client=wire,
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
        wire=wire,
        arms=probe.PROMPT_ARMS,
    )

    stopped = result["stopped"]
    assert stopped["rule"] == "request_cap"
    assert stopped["limit"] == 2
    assert stopped["observed"] == 2, "'observed' is what was sent, not asked"
    assert stopped["after_calls"] == 2
    assert "partial" in stopped["reading"]

    # The paid calls survived, and the plan they fell short of is recorded.
    assert len(result["calls"]) == 2
    assert result["planned_calls"] == len(corpus.claims) * 2

    # Same census every other stop rule gets: what is left unpaired is stated
    # rather than quietly evened up.
    assert "left_behind" in stopped

    report = probe.build_report(
        identity=_stamped_identity(),
        measured=True,
        repeats=1,
        result=result,
        speech=corpus,
    )
    assert report["stopped"]["rule"] == "request_cap"
    json.dumps(report)


def test_a_ceiling_stop_reports_the_ceiling_and_not_the_symptom(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Exit 3 with the report on disk.

    The file is worth keeping -- the requests in it were paid for -- but it
    is a partial run under a filename a whole one also uses, and a zero exit
    is how the two stop being told apart. The unanswered-claims exit would
    also fire here and would name the symptom; the cause is the ceiling.
    """
    real = probe.run_measurement

    def _stopped_at_the_ceiling(**kwargs: object) -> dict:
        result = real(**kwargs)
        result["stopped"] = {
            "rule": "request_cap",
            "limit": 12,
            "observed": 12,
            "after_calls": len(result["calls"]),
            "reading": "partial",
        }
        result["calls"] = result["calls"][:1]
        return result

    monkeypatch.setattr(probe, "run_measurement", _stopped_at_the_ceiling)
    out = tmp_path / "report.json"
    assert probe.main(
        ["--dry-run", "--quiet", "--repeats", "1", "--out", str(out)]
    ) == 3
    err = capsys.readouterr().err
    assert "request ceiling of 12" in err
    assert "no verdict was reached" not in err, (
        "the run reported the symptom instead of the cause"
    )
    assert out.exists(), "the paid calls were thrown away"
    assert json.loads(out.read_text(encoding="utf-8"))["stopped"]["rule"] == (
        "request_cap"
    )


_MAIN_DOC = (
    probe.REPO_ROOT / "tasks" / "rebuilding_grading_task"
    / "338-format-safe-observation-ab.md"
)


def test_the_main_comparison_document_pins_what_this_checkout_would_dispatch(
) -> None:
    """338 registers the size 333 registered and 334 bought -- and no more.

    The instruction for this comparison is that it does not grow past 120
    calls. A ceiling is how that survives contact with a dispatch form: the
    plan is counted before a client exists and refused if it is bigger. So
    the number in the document and the number in the registry have to be the
    same number, and this is the thing that says so.
    """
    text = _MAIN_DOC.read_text(encoding="utf-8")

    assert probe.diagnostic_kind_stated_in(_MAIN_DOC) == (
        probe.SPEECH_PROMPT_AB_V2_KIND
    )
    assert probe.grader_pin_stated_in(_MAIN_DOC) == probe.grader_source_hash()

    # Whole-manifest: it must NOT narrow, and it must not fix repeats. Both
    # are checked through the registries the door actually reads, not through
    # the prose.
    assert probe.SPEECH_PROMPT_AB_V2_KIND not in probe.SPEECH_NARROWED_KINDS
    with pytest.raises(ValueError):
        probe.pilot_claims_stated_in(_MAIN_DOC)

    manifest = json.loads(
        (
            probe.REPO_ROOT / "tasks" / "rebuilding_grading_task"
            / "330-speech-verification-manifest.json"
        ).read_text(encoding="utf-8")
    )
    planned = len(manifest["claims"]) * 3 * len(probe.PROMPT_ARMS)
    assert planned == 120, "the corpus changed size; 338 registers 120"
    assert f"**{len(manifest['claims'])} × 3 × {len(probe.PROMPT_ARMS)} = " \
           f"{planned}**" in text

    cap = probe.SPEECH_REQUEST_CAPS[probe.SPEECH_PROMPT_AB_V2_KIND]
    assert cap == 126
    assert f"| **요청 상한** | **{cap}**" in text
    assert planned <= cap

    # The headroom is deliberately too small for another repeat. If someone
    # raises this later, that sentence in the document stops being true, and
    # the run it would allow is the one the instruction forbids.
    assert len(manifest["claims"]) * 4 * len(probe.PROMPT_ARMS) > cap

    name, header = probe.SPEECH_TWO_ARM_REGISTRATIONS[
        probe.SPEECH_PROMPT_AB_V2_KIND
    ]
    assert header is probe.SPEECH_OBSERVATION_HEADER_V2
    assert _doc_sha256(text, "SPEECH_OBSERVATION_HEADER_V2") == hashlib.sha256(
        header.encode("utf-8")
    ).hexdigest()
    # Both pre-registrations run the same candidate, so a pilot that passes
    # is a pilot of the thing 338 will buy.
    assert _doc_sha256(_PILOT_DOC.read_text(encoding="utf-8"),
                       "SPEECH_OBSERVATION_HEADER_V2") == _doc_sha256(
        text, "SPEECH_OBSERVATION_HEADER_V2")


def test_the_whole_manifest_kind_refuses_a_document_that_fixes_claims(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """338's door is narrower than 337's, in the one way that matters.

    A claim row here would name a subset the run ignores -- it walks the whole
    manifest -- and afterwards a document that listed five claims is
    indistinguishable from one that agreed to twenty.
    """
    manifest_path, clip_dir = _speech_fixture(tmp_path, clips=3)
    out = tmp_path / "out.json"
    args = _speech_ab_args(tmp_path, manifest_path, clip_dir, out)

    fixed = _pilot_doc(
        tmp_path, kind=probe.SPEECH_PROMPT_AB_V2_KIND, name="v2fixed.md"
    )
    assert probe.main([*args, "--speech-prompt-ab", str(fixed)]) == 3
    assert "carries a claim row" in capsys.readouterr().err
    assert not out.exists()

    # Without the row it opens, walks everything, and sends the candidate.
    whole = _pilot_doc(
        tmp_path, kind=probe.SPEECH_PROMPT_AB_V2_KIND, claims=None,
        name="v2whole.md",
    )
    assert probe.main([*args, "--speech-prompt-ab", str(whole)]) == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["pins"]["observation_header_name"] == (
        "SPEECH_OBSERVATION_HEADER_V2"
    )
    corpus = probe.load_speech_corpus(manifest_path, clip_dir)
    assert len(report["calls"]) == len(corpus.claims) * len(probe.PROMPT_ARMS)


# ---------------------------------------------------------------------------
# The dispatch form is where a document gets chosen, and it is the one place
# the measurer's own checks cannot help. It refuses a file that does not name
# a diagnostic; it cannot refuse the *wrong* file, because a file that says
# `speech-prompt-ab` is a perfectly valid answer to a dispatch that asked for
# 337. That mapping is workflow YAML, so these tests read the YAML.
# ---------------------------------------------------------------------------


_CORPUS_DOCUMENTS = {
    probe.SPEECH_PROMPT_AB_KIND: (
        "SPEECH_AB_PREREG", "333-speech-prompt-ab-prereg.md",
    ),
    probe.SPEECH_FORMAT_PILOT_KIND: (
        "SPEECH_PILOT_PREREG", _PILOT_DOC.name,
    ),
    probe.SPEECH_PROMPT_AB_V2_KIND: (
        "SPEECH_AB_V2_PREREG", _MAIN_DOC.name,
    ),
}


def test_every_two_arm_corpus_is_offered_and_routed_to_its_own_document(
) -> None:
    """A dropdown entry and a document, held together in both jobs.

    Three things can drift apart here and none of them is visible at dispatch
    time. A corpus the script knows and the form does not offer cannot be run
    at all. A corpus the form offers and neither job routes falls through to
    ``--expect-grader-pin``, which runs one arm under 330 -- a dispatch that
    asked for a comparison would quietly buy half of it and report an accuracy
    for the control arm. And a corpus routed to the *wrong* document runs a
    size nobody registered: 337's five criteria under 333, or 338's twenty
    under 337's ceiling of twelve.

    The measurer cannot catch any of these. It checks that the document names
    a diagnostic it knows, not that the diagnostic is the one the dispatcher
    picked -- so the check has to live where the pick is made.

    The free job is checked with the same list as the paid one. It is the run
    that is supposed to discover a broken mapping before the money.
    """
    inputs = _workflow()[True]["workflow_dispatch"]["inputs"]
    options = inputs["corpus"]["options"]

    # Every registered two-arm diagnostic is dispatchable, and the option is
    # spelled exactly as the document spells the kind.
    for kind in probe.SPEECH_TWO_ARM_REGISTRATIONS:
        assert kind in options, f"{kind} cannot be dispatched"
        assert kind in _CORPUS_DOCUMENTS, f"{kind} has no document in this test"

    # The single-arm settings stay, and nothing else has appeared. A new
    # option not in this list is one nobody has decided the routing for.
    assert set(options) == {"tones", "speech", *_CORPUS_DOCUMENTS}
    assert inputs["corpus"]["default"] == "tones", (
        "the default dispatch must be the one that spends least"
    )

    env = _workflow()["env"]
    for job, step_name in (("dry-run", "Dry run"), ("measure", "Measure")):
        run = _step(job, step_name)["run"]
        for kind, (var, filename) in _CORPUS_DOCUMENTS.items():
            # `case` arm, then the flag it adds, then the variable it names.
            branch = re.search(
                rf"^\s*{re.escape(kind)}\)\n"
                rf"\s*ARGS\+=\(--speech-prompt-ab \"\$(\w+)\"\) ;;",
                run,
                re.MULTILINE,
            )
            assert branch, f"{job} does not route {kind}"
            assert branch.group(1) == var, (
                f"{job} routes {kind} to ${branch.group(1)}, not ${var}"
            )
            assert env[var].endswith(f"/{filename}"), (
                f"{var} does not point at {filename}"
            )

        # The fallback is the single-arm path, and it is still reached by
        # `speech` -- which is what makes the routing above load-bearing.
        assert '--expect-grader-pin "$SPEECH_PREREG"' in run

    # Distinct documents. One file reused across two kinds would pass every
    # assertion above and still describe one experiment as another.
    named = [env[var] for var, _ in _CORPUS_DOCUMENTS.values()]
    assert len(set(named)) == len(named)
    for path in named:
        on_disk = probe.REPO_ROOT / path.split("workspace }}/", 1)[1]
        assert on_disk.is_file(), f"{path} is not in the checkout"


def test_the_approval_record_counts_the_pilot_as_five_and_not_as_twenty(
) -> None:
    """The gate cannot read 337, so it restates 337 -- and this checks it.

    Every other corpus asks twenty criteria; this one asks the five its own
    document names. The old record said twenty unconditionally, which on a
    337 dispatch would have authorised 40 calls for a run that makes 10.

    That error is in the direction that costs nothing, and it is still the
    error this workflow has already made once in the other direction. An
    approval record is a claim about what was bought; a claim that is four
    times the truth is not made safe by being an overestimate.

    The five and the split are not written down here either. They are
    re-derived from the document the run will actually be handed.
    """
    text = (
        probe.REPO_ROOT / ".github" / "workflows" / "audio-accuracy-probe.yml"
    ).read_text(encoding="utf-8")

    stated = probe.pilot_claims_stated_in(_PILOT_DOC)
    manifest = json.loads(
        (
            probe.REPO_ROOT / "tasks" / "rebuilding_grading_task"
            / "330-speech-verification-manifest.json"
        ).read_text(encoding="utf-8")
    )
    by_id = {claim["claim_id"]: claim for claim in manifest["claims"]}
    claims = [by_id[claim_id] for claim_id in stated]
    true_claims = sum(1 for claim in claims if claim["holds"])

    branch = re.search(
        rf"{re.escape(probe.SPEECH_FORMAT_PILOT_KIND)}\)\n"
        r"\s*CRITERIA=(\d+); TRUE_CRITERIA=(\d+); FALSE_CRITERIA=(\d+)",
        text,
    )
    assert branch, "the approval record does not size the pilot separately"
    assert int(branch.group(1)) == len(claims)
    assert int(branch.group(2)) == true_claims
    assert int(branch.group(3)) == len(claims) - true_claims

    # And it says so in words, because a reader of the record has no way to
    # tell a five-criterion run from a twenty-criterion one that went wrong.
    assert "narrowed   = yes, to the 5 criteria named in 337" in text
    assert "narrowed   = no. Every criterion in the corpus" in text


def test_the_approval_record_doubles_for_every_corpus_that_runs_two_arms(
) -> None:
    """``prompt_arm`` is not how these get their second arm, so it is not the test.

    334 is the reason this is a list rather than a comparison against one
    name. The record read ``prompt_arm`` alone, the A/B corpus opened its
    second arm from its document, and the approval line said 60 calls for a
    run that made 120. Two more corpora do the same thing now.

    The shell is executed rather than pattern-matched: the arithmetic is what
    is being checked, and a regex over a ``case`` statement would agree with a
    branch that never runs.
    """
    record = _step("approve-paid", "Record approved request")["run"]

    def approved(corpus: str, arm: str, repeats: str) -> str:
        return subprocess.run(
            ["bash", "-c", record],
            env={
                **os.environ,
                "PROBE_CORPUS": corpus,
                "PROBE_ARM": arm,
                "PROBE_REPEATS": repeats,
            },
            capture_output=True, text=True, check=True,
        ).stdout

    # Two arms with the flag left alone, for each corpus that carries its own
    # second arm -- and the totals they authorise.
    for kind, criteria, repeats, total in (
        (probe.SPEECH_PROMPT_AB_KIND, 20, "3", 120),
        (probe.SPEECH_FORMAT_PILOT_KIND, 5, "1", 10),
        (probe.SPEECH_PROMPT_AB_V2_KIND, 20, "3", 120),
    ):
        out = approved(kind, "production", repeats)
        assert "(2 arm(s))" in out, kind
        assert f"criteria   = {criteria} " in out, kind
        assert f"{criteria * int(repeats)} per arm, {total} in total" in out

    # The single-arm settings did not become two-arm on the way past.
    for kind in ("tones", "speech"):
        assert "(1 arm(s))" in approved(kind, "production", "3")
        assert "60 per arm, 60 in total" in approved(kind, "production", "3")

    # `both` still doubles a corpus that has no second arm of its own.
    both = approved("speech", "both", "3")
    assert "(2 arm(s))" in both
    assert "60 per arm, 120 in total" in both

