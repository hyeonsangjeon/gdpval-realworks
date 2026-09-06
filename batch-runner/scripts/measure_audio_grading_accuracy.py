#!/usr/bin/env python3
"""Measure whether the audio sub-judge is *right*, not merely consistent.

Step 4 of the audio-confidence card, and the last one. Steps 1-3 pinned an
audio cohort, bought three gradings of it at one fingerprint, and measured how
often the verdicts disagree with each other: 19.35% of pairs, against 2.12% on
text items. That is a *consistency* figure. It says the audio path is unsteady.
It does not say which of the two answers was the right one, and it cannot:
every item in that corpus is scored against an expert deliverable whose own
correctness is one of the two open interpretations the card names.

    1. the expert answer really did miss the spec, or
    2. ``gpt-audio-1.5`` is not accurate enough to check a claim like that.

Nothing measured so far separates those, because nothing measured so far had a
ground truth that did not depend on a human. A repeat run tells you the model
agrees with itself. It does not tell you the model is listening.

So this script builds its own corpus, out of nothing but arithmetic.

Every clip here is synthesised from a segment list -- a start time, an end
time, and either silence or a frequency, optionally with further frequencies
sounding alongside it -- by :func:`render_clip`, using only ``wave`` and
``math`` from the standard library. There is no recording, no asset, no
download, and nothing committed as bytes. What is in the clip is what the
segment list says is in it, and the accompanying test decodes the rendered
samples back and checks that the waveform really has the onsets, the gaps, the
beep count, the pitch order, the scale degrees, the chord tones, the overtones
and the semitone transposition the segments claim. **The ground truth is not
asserted in prose; it is measured off the same bytes the model hears.**

Against those clips it puts twenty criteria, ten of which are true and ten of
which are false, matched in pairs so that each pair sits on one clip and
carries one of each. The criteria are written the way the gold rubric writes
them, and the families they fall into are the families that actually failed on
the gold run:

* ``timing``       -- a tone stops partway through; a criterion says it does
                      not. This is the exact shape of the 0.95-vs-0.96
                      contradiction quoted on the card.
* ``presence``     -- a silent clip, and a criterion claiming speech.
* ``count``        -- three beeps, and a criterion claiming seven.
* ``tempo_coarse`` -- a 120 BPM click track, and a criterion claiming 60.
* ``tempo_fine``   -- the same track, and a criterion claiming 132 +/- 1 BPM.
  The gold run failed an expert deliverable on a "140 BPM" criterion off a
  61-89 token answer. Whether a claim at that resolution is answerable at all
  is a question this family exists to answer.
* ``pitch_order``  -- low then high, and a criterion claiming high then low.

Those six are beeps, and beeps were the first version's admitted limit: the
gold run's audio criteria are about film and music tracks, and what this
corpus could get wrong was "how many beeps" rather than anything musical. Four
more families answer that. Three of them are the questions the gold run's
failed criteria actually asked -- a key (G major), a modulation (an A-flat
bridge) and a timbre ("bass synth") -- and the fourth, chord quality, is what
a key claim rests on and the only one of the four that needs two notes to
sound at the same instant:

* ``key``        -- an ascending G major scale, and a criterion placing it in
                    E-flat major. Decidable on one note: the melody plays
                    F-sharp, which E-flat major does not have.
* ``triad``      -- three notes sounding at once, and a criterion calling a
                    major chord minor. The difference is B4 against B-flat4,
                    493.88 Hz against 466.16 Hz, and it is in the spectrum.
* ``modulation`` -- an arpeggio that transposes up a semitone halfway, and a
                    criterion saying the key never changes. The ground truth
                    is a frequency *ratio*, 2 ** (1/12), measured off the two
                    halves of the decoded waveform.
* ``timbre``     -- a low note carrying its first five overtones, and a
                    criterion calling it a plain sine. This is "bass synth"
                    reduced to something a spectrum settles.

These are music, not speech, and the distinction is worth stating plainly:
intelligible speech cannot be synthesised from ``wave`` and ``math``, so a
speech corpus would need a committed recording, which is exactly what this
script refuses to have. The speech half of "speech or music with certain
ground truth" is therefore still open, and nothing here should be read as
having closed it.

What comes out is not one number but three, and the third is the one that
matters:

``false_fail_rate``
    How often a criterion that is *true of the clip* is marked ``fail``. This
    is the error that makes a correct deliverable look wrong, and it is the
    direct test of interpretation 2 above.

``false_pass_rate``
    How often a criterion that is *false of the clip* is marked ``pass``.
    This is the error that inflates a score.

``discrimination_j``
    ``P(pass | true) - P(pass | false)``. Youden's J. **Zero means the verdict
    does not depend on the audio at all** -- a model answering "pass" to
    everything scores 50% accuracy on a balanced set and J = 0, and this is
    the number that refuses to let that read as half-right. Accuracy alone
    cannot tell a listener from a coin, and a balanced corpus is exactly where
    that failure hides.

The significance of J is taken by *exhaustive* enumeration of the 1024 ways
the ten true/false labels could be swapped within their pairs -- not sampling,
so the p-value is exact and the script has no random state to pin. That design
has a floor, and the floor is reported rather than left for a reader to
discover: with ten pairs the smallest p this can ever produce is 1/1024 =
0.000977. The first version of this corpus had six pairs and a floor of 1/64 =
0.015625, which could never reach 0.01 however well the model did; four more
pairs is what removed that bound, and they are musical pairs, so the two
limits the card recorded are lifted by the same change. Saying so here is the
same discipline as ``is_informative: false`` on the repeat-variation interval
-- the number is published *with* the bound on what it can support.

The identity is not chosen here. It is read out of the grading config the
repeat runs used, so the accuracy figure is measured on the same deployment,
the same clip length and the same call cap as the 19.35% it exists to explain.
A test asserts that; if the config moves, this refuses rather than quietly
measuring a different model.

**What the first measured run could not tell you.** It reported 51.85%
accuracy and a discrimination of ``-0.0037`` at ``p = 0.5215``, and the
write-up read that as a statement about what the model can hear. It is only
that if two things hold, and the run checked neither: that the audio actually
reached the provider, and that the prompt asked a question a listening model
would answer differently from a guessing one. A request that assembled the
text and dropped the audio produces the same numbers. So does a prompt that
hands the model a claim and invites it to agree. Two things were added here:

``delivery``
    What each request actually carried, taken off the wire by
    :class:`WireClient`: whether an ``input_audio`` part was present, the
    SHA-256 and length of the bytes inside it, what the WAV header says about
    itself, the model the *reply* names, whether the provider reported any
    audio tokens, and whether prompt tokens track clip duration. Hashes and
    counts only -- no audio, no prompt text, no reasoning, is written to an
    artifact.

``--prompt-arm both``
    The same twenty criteria, against byte-identical audio, under the
    production header and under an alternative that requires the model to
    observe the clip before judging the claim. Interleaved rather than run in
    sequence, so drift moves both arms together, and compared with an exact
    McNemar test on the pairs. This separates "the prompt did not ask well"
    from "the model cannot hear", which the first run could not.

Neither is a defence of the first run's conclusion or an attack on it. They
are the two alternative explanations it left open, made measurable.

Usage::

    python3 scripts/measure_audio_grading_accuracy.py --dry-run
    python3 scripts/measure_audio_grading_accuracy.py --repeats 3 --out report.json
    python3 scripts/measure_audio_grading_accuracy.py --prompt-arm both --repeats 3

``--dry-run`` runs the whole path -- render, encode, prompt, parse, score,
aggregate -- against a stub that answers from the segment list instead of a
model. It makes no network call and costs nothing. It exists so the shape of
this report is proven in CI on every commit, rather than first observed on the
run that is being paid for.

Exit status:

    0   the measurement was made and is reportable
    2   at least one criterion got no answer at all, so a family cell of the
        breakdown would be computed from an empty denominator
    3   the pinned identity does not match the grading config it claims to
        share, so whatever was measured was not measured on the audio path
        under test
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import hashlib
import io
import itertools
import json
import math
import os
import struct
import sys
import tempfile
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.cost_metering import resolved_model_of  # noqa: E402
from core.perception.audio import (  # noqa: E402
    AUDIO_CALL_CAP,
    AUDIO_RESPONSE_CONTRACT,
    AUDIO_SAMPLE_RATE_HZ,
    AUDIO_TRIM_SECONDS,
    AudioPerception,
    AudioVerdict,
    criterion_listen_start,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

#: The grading config whose audio identity this measurement borrows. Steps 2
#: and 3 of the card bought three runs of this config; the whole point of step
#: 4 is to describe *that* model, so the deployment, the clip length and the
#: per-task cap are read out of it rather than restated here.
PINNED_CONFIG = (
    REPO_ROOT
    / "batch-runner"
    / "grading_configs"
    / "gold_audio_repeat_v2_sol_max.yaml"
)

#: What the repeat runs measured, quoted so a reader of this report does not
#: have to go and find it. Consistency, not accuracy -- which is why this file
#: exists.
REPEAT_FLIP_RATE_PCT = 19.35
REPEAT_TEXT_FLIP_RATE_PCT = 2.12

#: Amplitude of a rendered tone, as a fraction of full scale. Loud enough that
#: no plausible re-encode loses it, quiet enough not to clip when PyAV
#: resamples.
TONE_AMPLITUDE = 0.6

#: Every clip is rendered at exactly the rate the grader re-encodes to, so the
#: resample on the way out is a no-op in substance and the model hears the
#: waveform this file wrote. A test pins the equality.
CLIP_SAMPLE_RATE_HZ = AUDIO_SAMPLE_RATE_HZ


# --------------------------------------------------------------------------
# The corpus: segments in, waveform out, ground truth in between
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Segment:
    """One stretch of a clip and what is objectively inside it.

    ``frequency_hz`` of ``None`` means digital silence -- samples of exactly
    zero, not low-level noise, so "is anything audible here" has an answer
    that survives any encoder.

    ``partials`` is what makes a chord and a timbre expressible, and it is the
    whole difference between a beep and music. Each entry is
    ``(frequency_hz, weight)`` and sounds *at the same time* as the
    fundamental: a triad is three frequencies at once, and a synth bass is a
    fundamental plus its harmonics. Weights are relative -- the fundamental is
    1.0 -- and their total is normalised back to :data:`TONE_AMPLITUDE` when
    the segment is rendered, so a six-voice segment is as loud as a one-voice
    one and neither clips.

    A segment with no partials renders through exactly the path it always did,
    at exactly the amplitude it always did: the normaliser divides by 1.0 and
    the addition loop never runs. That is deliberate rather than incidental.
    The published "discrimination 0" result was measured on five clips that
    carry no partials, and it stays re-derivable only if those clips still
    render to the same bytes. A test decodes them and checks sample by sample.
    """

    start_s: float
    end_s: float
    frequency_hz: Optional[float]
    partials: tuple[tuple[float, float], ...] = ()

    @property
    def duration_s(self) -> float:
        return self.end_s - self.start_s

    @property
    def is_silent(self) -> bool:
        return self.frequency_hz is None

    @property
    def frequencies_hz(self) -> tuple[float, ...]:
        """Every frequency sounding here at once, fundamental first."""
        if self.frequency_hz is None:
            return ()
        return (self.frequency_hz, *(freq for freq, _weight in self.partials))

    @property
    def weight_total(self) -> float:
        """Fundamental (1.0) plus every partial, for loudness normalisation."""
        return 1.0 + sum(weight for _freq, weight in self.partials)

    def to_dict(self) -> dict[str, Any]:
        return {
            "start_s": round(self.start_s, 6),
            "end_s": round(self.end_s, 6),
            "frequency_hz": self.frequency_hz,
            "partials": [[freq, weight] for freq, weight in self.partials],
        }


@dataclass(frozen=True)
class Clip:
    """A synthesised clip whose contents are known by construction."""

    clip_id: str
    duration_s: float
    segments: tuple[Segment, ...]
    #: One plain sentence a human can check the segment list against. Not used
    #: in scoring -- the segments are the truth -- but carried into the report
    #: so a reader does not have to reconstruct the clip in their head.
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "clip_id": self.clip_id,
            "duration_s": self.duration_s,
            "description": self.description,
            "segments": [segment.to_dict() for segment in self.segments],
        }


def _tone_samples(
    frequency_hz: float,
    count: int,
    phase_offset: int,
    amplitude: float = TONE_AMPLITUDE,
) -> Iterator[float]:
    """A sine at ``frequency_hz``, continuous across segment boundaries.

    ``phase_offset`` is the sample index this segment starts at within the
    whole clip, so a segment that repeats a frequency picks the wave up where
    the previous one left it instead of restarting at zero. Restarting would
    put a click at every boundary, and a click is an audible event this corpus
    has not declared.

    ``amplitude`` defaults to the value every single-voice segment has always
    used, so a caller that does not ask for anything else gets the identical
    float back.
    """
    step = 2.0 * math.pi * frequency_hz / CLIP_SAMPLE_RATE_HZ
    for index in range(count):
        yield amplitude * math.sin(step * (phase_offset + index))


def clip_samples(clip: Clip) -> list[float]:
    """Render a clip to floats in [-1, 1], gaps included.

    Anything the segment list does not cover is silence. That is deliberate:
    a clip is defined by what it *contains*, and the space between two beeps
    should not need its own entry to be quiet.

    The fundamental is *assigned* into the buffer and the partials are *added*
    to it, so a one-voice segment takes the same statement it always took. In
    IEEE-754 the accumulating form would give bit-identical results here --
    ``x * 1.0`` and ``0.0 + x`` are both exact -- so this is a readability
    choice rather than a correctness one, and it is worth being exact about
    which: the single-voice path being visibly unchanged is what makes the
    byte-identity test a check rather than a hope.

    The identity itself does not rest on that choice. It rests on the scale:
    with no partials ``weight_total`` is 1.0, so the scale is
    ``TONE_AMPLITUDE / 1.0``, and the loop over partials runs zero times. The
    published "discrimination 0" result was measured on five clips that go
    down this path, and a test recomputes all five the pre-partials way and
    demands exact equality.
    """
    total = int(round(clip.duration_s * CLIP_SAMPLE_RATE_HZ))
    samples = [0.0] * total
    for segment in clip.segments:
        if segment.is_silent:
            continue
        start = int(round(segment.start_s * CLIP_SAMPLE_RATE_HZ))
        stop = min(total, int(round(segment.end_s * CLIP_SAMPLE_RATE_HZ)))
        if stop <= start:
            continue
        assert segment.frequency_hz is not None
        scale = TONE_AMPLITUDE / segment.weight_total
        for offset, value in enumerate(
            _tone_samples(segment.frequency_hz, stop - start, start, scale)
        ):
            samples[start + offset] = value
        for frequency_hz, weight in segment.partials:
            for offset, value in enumerate(
                _tone_samples(frequency_hz, stop - start, start, scale * weight)
            ):
                samples[start + offset] += value
    return samples


def render_clip(clip: Clip, path: Path) -> str:
    """Write ``clip`` to ``path`` as 16-bit mono PCM. Returns its sha256.

    The digest is reported so the clip a verdict was reached on can be
    re-derived and re-checked later without trusting this run.
    """
    frames = b"".join(
        struct.pack("<h", max(-32768, min(32767, int(round(value * 32767)))))
        for value in clip_samples(clip)
    )
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(CLIP_SAMPLE_RATE_HZ)
        handle.writeframes(frames)
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --------------------------------------------------------------------------
# Pitches, so a musical claim is arithmetic rather than taste
# --------------------------------------------------------------------------

#: Equal temperament, A4 = MIDI 69 = 440 Hz.
A4_HZ = 440.0
A4_MIDI = 69

#: The ratio one semitone is. Every musical claim below reduces to this
#: number or to a membership test over :data:`NOTE`, which is the point: "the
#: bridge modulates up a semitone" is checkable off the waveform as a
#: frequency ratio, and "taste" never enters it.
SEMITONE_RATIO = 2.0 ** (1.0 / 12.0)


def pitch_hz(midi_note: int) -> float:
    """Frequency of an equal-tempered MIDI note number."""
    return A4_HZ * (2.0 ** ((midi_note - A4_MIDI) / 12.0))


#: MIDI numbers for the notes used below, so the segment lists read as music
#: and the frequencies are derived rather than typed. ``Fs`` is F-sharp, ``b``
#: is flat. ``Bb4`` and ``F5`` are never played -- they are here because they
#: are what the *false* claims would require, and the test asserts they are
#: absent from the waveform.
NOTE = {
    "C2": 36,
    "G4": 67,
    "Ab4": 68,
    "A4": 69,
    "Bb4": 70,
    "B4": 71,
    "C5": 72,
    "D5": 74,
    "Eb5": 75,
    "E5": 76,
    "F5": 77,
    "Fs5": 78,
    "G5": 79,
    "Ab5": 80,
}


def hz(name: str) -> float:
    """Frequency of a named note, e.g. ``hz("Fs5")``."""
    return pitch_hz(NOTE[name])


#: The overtones the buzzy bass carries, and the falling strengths that make
#: it read as a synth rather than a sine. 1/n is the sawtooth series.
BASS_HARMONICS = (2, 3, 4, 5, 6)


CLIPS: tuple[Clip, ...] = (
    Clip(
        clip_id="tone_stops_early",
        duration_s=6.0,
        segments=(Segment(0.0, 2.0, 1000.0),),
        description=(
            "A 1000 Hz tone for the first two seconds, then four seconds of "
            "silence."
        ),
    ),
    Clip(
        clip_id="pure_silence",
        duration_s=6.0,
        segments=(),
        description="Six seconds of digital silence; every sample is zero.",
    ),
    Clip(
        clip_id="three_beeps",
        duration_s=5.0,
        segments=(
            Segment(0.5, 0.65, 1000.0),
            Segment(2.0, 2.15, 1000.0),
            Segment(3.5, 3.65, 1000.0),
        ),
        description=(
            "Three 150 ms beeps at 1000 Hz, at 0.5 s, 2.0 s and 3.5 s, "
            "silence in between."
        ),
    ),
    Clip(
        clip_id="clicks_120bpm",
        duration_s=8.0,
        segments=tuple(
            Segment(index * 0.5, index * 0.5 + 0.03, 1000.0)
            for index in range(16)
        ),
        description=(
            "Sixteen 30 ms clicks spaced exactly 0.5 s apart across eight "
            "seconds, which is 120 beats per minute."
        ),
    ),
    Clip(
        clip_id="low_then_high",
        duration_s=5.0,
        segments=(
            Segment(0.0, 2.0, 220.0),
            Segment(3.0, 5.0, 880.0),
        ),
        description=(
            "A 220 Hz tone for two seconds, one second of silence, then a "
            "880 Hz tone for two seconds -- two octaves up."
        ),
    ),
    # ----------------------------------------------------------------------
    # Musical material. Everything above is a beep; the criteria that actually
    # failed on the gold run were about key, chord quality, tempo and timbre,
    # and a corpus of beeps cannot ask those. These four clips are still
    # arithmetic -- every frequency comes out of pitch_hz -- but they are
    # arithmetic arranged as music.
    # ----------------------------------------------------------------------
    Clip(
        clip_id="g_major_scale",
        duration_s=3.4,
        segments=tuple(
            Segment(index * 0.4, index * 0.4 + 0.35, hz(name))
            for index, name in enumerate(
                ("G4", "A4", "B4", "C5", "D5", "E5", "Fs5", "G5")
            )
        ),
        description=(
            "Eight notes rising -- G4 A4 B4 C5 D5 E5 F-sharp5 G5 -- each 350 "
            "ms with a 50 ms gap. That is the G major scale, and the F-sharp "
            "is what makes it G major rather than any flat key."
        ),
    ),
    Clip(
        clip_id="major_triad",
        duration_s=3.0,
        segments=(
            Segment(
                0.2,
                2.8,
                hz("G4"),
                partials=((hz("B4"), 1.0), (hz("D5"), 1.0)),
            ),
        ),
        description=(
            "One sustained chord: G4, B4 and D5 sounding together for 2.6 "
            "seconds, which is a G major triad. The minor version of this "
            "chord would put B-flat4 where the B4 is."
        ),
    ),
    Clip(
        clip_id="modulating_arpeggio",
        duration_s=5.0,
        segments=tuple(
            Segment(index * 0.6, index * 0.6 + 0.5, hz(name))
            for index, name in enumerate(
                ("G4", "B4", "D5", "G5", "Ab4", "C5", "Eb5", "Ab5")
            )
        ),
        description=(
            "A G major arpeggio -- G4 B4 D5 G5 -- for the first 2.4 seconds, "
            "then the same shape one semitone higher in A-flat major. The key "
            "changes exactly halfway through."
        ),
    ),
    Clip(
        clip_id="buzzy_bass",
        duration_s=3.0,
        segments=(
            Segment(
                0.2,
                2.8,
                hz("C2"),
                partials=tuple(
                    (hz("C2") * harmonic, 1.0 / harmonic)
                    for harmonic in BASS_HARMONICS
                ),
            ),
        ),
        description=(
            "One low note -- C2, about 65.4 Hz -- carrying its first five "
            "overtones at falling strength, which is what makes a synth bass "
            "buzz instead of hum. A pure sine at the same pitch has none of "
            "them."
        ),
    ),
)

CLIPS_BY_ID = {clip.clip_id: clip for clip in CLIPS}


# --------------------------------------------------------------------------
# The criteria
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Claim:
    """One rubric-shaped criterion whose truth is decided by the segments."""

    claim_id: str
    clip_id: str
    family: str
    criterion: str
    #: Whether the criterion is true of the clip. This is the ground truth,
    #: and it is checkable against the rendered waveform by the test suite.
    holds: bool
    #: The arithmetic that settles it, for a reader who does not want to
    #: reconstruct the segment list.
    because: str

    @property
    def pair_id(self) -> str:
        """The claim_id without its ``_true`` / ``_false`` suffix.

        Claims come in matched pairs on the same clip, and the permutation
        test swaps labels *within* a pair. That is what keeps a relabelling
        from producing a corpus that could not have existed -- two true
        criteria about one clip and none about another.
        """
        return self.claim_id.rsplit("_", 1)[0]

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "clip_id": self.clip_id,
            "family": self.family,
            "criterion": self.criterion,
            "holds": self.holds,
            "because": self.because,
            "pair_id": self.pair_id,
        }


CLAIMS: tuple[Claim, ...] = (
    Claim(
        claim_id="timing_true",
        clip_id="tone_stops_early",
        family="timing",
        criterion=(
            "A sustained tone is audible from the beginning of the clip and "
            "stops before the clip ends, leaving an audible stretch of "
            "silence at the end."
        ),
        holds=True,
        because="the tone occupies 0.0-2.0 s of a 6.0 s clip",
    ),
    Claim(
        claim_id="timing_false",
        clip_id="tone_stops_early",
        family="timing",
        criterion=(
            "A sustained tone is audible continuously for the whole clip, "
            "with no stretch of silence anywhere in it."
        ),
        holds=False,
        because="4.0 s of the 6.0 s clip is digital silence",
    ),
    Claim(
        claim_id="presence_true",
        clip_id="pure_silence",
        family="presence",
        criterion=(
            "Nothing is audible in the clip: no speech, music, tone or noise."
        ),
        holds=True,
        because="every sample in the clip is exactly zero",
    ),
    Claim(
        claim_id="presence_false",
        clip_id="pure_silence",
        family="presence",
        criterion="A human voice speaking is audible in the clip.",
        holds=False,
        because="every sample in the clip is exactly zero",
    ),
    Claim(
        claim_id="count_true",
        clip_id="three_beeps",
        family="count",
        criterion=(
            "Exactly three short beeps are audible, each separated from the "
            "next by silence."
        ),
        holds=True,
        because="the segment list has three tone bursts",
    ),
    Claim(
        claim_id="count_false",
        clip_id="three_beeps",
        family="count",
        criterion=(
            "Exactly seven short beeps are audible, each separated from the "
            "next by silence."
        ),
        holds=False,
        because="the segment list has three tone bursts, not seven",
    ),
    Claim(
        claim_id="tempo_coarse_true",
        clip_id="clicks_120bpm",
        family="tempo_coarse",
        criterion=(
            "The clicks are evenly spaced at a tempo of about 120 beats per "
            "minute."
        ),
        holds=True,
        because="clicks are 0.5 s apart, which is exactly 120 BPM",
    ),
    Claim(
        claim_id="tempo_coarse_false",
        clip_id="clicks_120bpm",
        family="tempo_coarse",
        criterion=(
            "The clicks are evenly spaced at a tempo of about 60 beats per "
            "minute."
        ),
        holds=False,
        because="60 BPM would be 1.0 s apart; these are 0.5 s apart",
    ),
    Claim(
        claim_id="tempo_fine_true",
        clip_id="clicks_120bpm",
        family="tempo_fine",
        criterion=(
            "The tempo of the clicks is 120 beats per minute, within a "
            "tolerance of one beat per minute."
        ),
        holds=True,
        because="clicks are 0.5 s apart, which is exactly 120 BPM",
    ),
    Claim(
        claim_id="tempo_fine_false",
        clip_id="clicks_120bpm",
        family="tempo_fine",
        criterion=(
            "The tempo of the clicks is 132 beats per minute, within a "
            "tolerance of one beat per minute."
        ),
        holds=False,
        because="132 BPM would be 0.4545 s apart; these are 0.5 s apart",
    ),
    Claim(
        claim_id="pitch_order_true",
        clip_id="low_then_high",
        family="pitch_order",
        criterion=(
            "The clip opens with a lower-pitched tone and closes with a "
            "higher-pitched one."
        ),
        holds=True,
        because="220 Hz precedes 880 Hz",
    ),
    Claim(
        claim_id="pitch_order_false",
        clip_id="low_then_high",
        family="pitch_order",
        criterion=(
            "The clip opens with a higher-pitched tone and closes with a "
            "lower-pitched one."
        ),
        holds=False,
        because="220 Hz precedes 880 Hz, so the order is the other way round",
    ),
    # ----------------------------------------------------------------------
    # The musical families. Three of them are shapes the gold run actually
    # failed on -- the criteria it marked wrong named a key (G major), a
    # modulation (an A-flat bridge) and a timbre ("bass synth"). The fourth,
    # chord quality, is what a key claim rests on. The tempo the gold run also
    # named is already asked above, of the click track. Each pair here is one
    # of those questions put to a waveform that answers it.
    # ----------------------------------------------------------------------
    Claim(
        claim_id="key_true",
        clip_id="g_major_scale",
        family="key",
        criterion="Every note in the melody belongs to the G major scale.",
        holds=True,
        because=(
            "the eight notes are G4 A4 B4 C5 D5 E5 F-sharp5 G5, which is "
            "exactly the G major scale"
        ),
    ),
    Claim(
        claim_id="key_false",
        clip_id="g_major_scale",
        family="key",
        criterion="Every note in the melody belongs to the E-flat major scale.",
        holds=False,
        because=(
            "E-flat major has E-flat, A-flat and B-flat and no F-sharp; this "
            "melody plays B natural and F-sharp"
        ),
    ),
    Claim(
        claim_id="triad_true",
        clip_id="major_triad",
        family="triad",
        criterion="The clip is one sustained chord, and that chord is major.",
        holds=True,
        because=(
            "the chord is G4 + B4 + D5, and B4 is four semitones above G4, "
            "which is a major third"
        ),
    ),
    Claim(
        claim_id="triad_false",
        clip_id="major_triad",
        family="triad",
        criterion="The clip is one sustained chord, and that chord is minor.",
        holds=False,
        because=(
            "a minor chord would sound B-flat4 at 466.16 Hz where this one "
            "sounds B4 at 493.88 Hz"
        ),
    ),
    Claim(
        claim_id="modulation_true",
        clip_id="modulating_arpeggio",
        family="modulation",
        criterion=(
            "The music changes key partway through, so the second half is in "
            "a different key from the first."
        ),
        holds=True,
        because=(
            "the first four notes spell G major and the last four spell "
            "A-flat major, one semitone higher"
        ),
    ),
    Claim(
        claim_id="modulation_false",
        clip_id="modulating_arpeggio",
        family="modulation",
        criterion=(
            "The music stays in one key from beginning to end, with no change "
            "of key anywhere in it."
        ),
        holds=False,
        because="the second half is transposed up a semitone from the first",
    ),
    Claim(
        claim_id="timbre_true",
        clip_id="buzzy_bass",
        family="timbre",
        criterion=(
            "The bass note is a bright, buzzy synth tone with clearly audible "
            "overtones above its fundamental."
        ),
        holds=True,
        because=(
            "the segment sounds harmonics 2 through 6 of its 65.4 Hz "
            "fundamental at falling strength"
        ),
    ),
    Claim(
        claim_id="timbre_false",
        clip_id="buzzy_bass",
        family="timbre",
        criterion=(
            "The bass note is a plain sine tone with nothing sounding above "
            "its fundamental."
        ),
        holds=False,
        because=(
            "harmonics 2 through 6 of the fundamental are all present in the "
            "segment"
        ),
    ),
)


# --------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------

#: What a single verdict on a single claim was.
OUTCOME_CORRECT = "correct"
OUTCOME_FALSE_FAIL = "false_fail"
OUTCOME_FALSE_PASS = "false_pass"
OUTCOME_HEDGED = "hedged"
OUTCOME_UNANSWERED = "unanswered"

#: Why a call produced no judgement. Three different events, and the reason
#: they are named apart is that they call for three different responses:
#:
#: * ``declined_to_judge`` -- the model followed the contract and said it could
#:   not hear enough to decide. That is a *result*: it is the sub-judge working
#:   as designed, and it says something about the clip.
#: * ``read_failure`` -- the model answered, and the answer did not meet the
#:   response contract. That is a prompt defect, fixed by editing text.
#: * ``provider_failure`` -- the call itself did not complete. That is an
#:   outage, fixed by nobody here.
#:
#: Run 34008840627 published all of its 52 non-answers as
#: ``provider_error:JSONDecodeError`` and so could not distinguish any of the
#: three; re-read under the contract, every one of them was the second kind.
#: None of these enters the accuracy: a call that measured nothing is not
#: evidence either way, whichever of the three it was.
UNANSWERED_DECLINED = "declined_to_judge"
UNANSWERED_READ_FAILURE = "read_failure"
UNANSWERED_PROVIDER_FAILURE = "provider_failure"
UNANSWERED_KINDS = (
    UNANSWERED_DECLINED,
    UNANSWERED_READ_FAILURE,
    UNANSWERED_PROVIDER_FAILURE,
)


def unanswered_kind(verdict: str, judge_error: Optional[str]) -> Optional[str]:
    """Which of the three non-answers this was, or ``None`` if it answered.

    Reads the marker ``core.perception.audio`` writes rather than guessing from
    the text: ``format_error:<kind>`` for a reply that broke the contract,
    ``sub_judge_declined`` for a model that answered ``judge_error`` on
    purpose, anything else for a call that failed on the wire.

    A ``judge_error`` carrying no marker at all is called a provider failure,
    which is the conservative reading: it is the one of the three that says
    least about the model, so an unlabelled non-answer is never credited as
    the model having honestly declined.
    """
    if verdict != "judge_error":
        return None
    marker = judge_error or ""
    if marker.startswith("format_error:"):
        return UNANSWERED_READ_FAILURE
    if marker == "sub_judge_declined":
        return UNANSWERED_DECLINED
    return UNANSWERED_PROVIDER_FAILURE


def classify(claim: Claim, verdict: str) -> str:
    """Turn one verdict into one outcome.

    ``partial`` is its own outcome rather than being folded into either error.
    These criteria are binary statements about arithmetic -- a clip either has
    three beeps or it does not -- so a hedge is not a near-miss, it is a
    refusal to answer the question that was asked, and burying it in the
    accuracy rate would hide it in whichever direction happened to be
    convenient.

    ``judge_error`` is not an answer at all. It never counts as correct and it
    never counts as wrong; it counts as a call that measured nothing, and the
    denominators below exclude it. Which *kind* of non-answer it was is a
    separate question, answered by ``unanswered_kind`` and reported beside
    this outcome -- deliberately not folded in here, because the scoring
    treats all three identically and only the diagnosis differs.
    """
    if verdict == "judge_error":
        return OUTCOME_UNANSWERED
    if verdict == "partial":
        return OUTCOME_HEDGED
    said_pass = verdict == "pass"
    if claim.holds:
        return OUTCOME_CORRECT if said_pass else OUTCOME_FALSE_FAIL
    return OUTCOME_FALSE_PASS if said_pass else OUTCOME_CORRECT


def _rate(numerator: int, denominator: int) -> Optional[float]:
    """A rate, or ``None`` when there is nothing to divide by.

    Never zero for an empty denominator. Zero is a measurement; this is the
    absence of one, and the two must not print the same.
    """
    if denominator <= 0:
        return None
    return numerator / denominator


@dataclass
class Tally:
    """Outcome counts over some slice of the calls."""

    correct: int = 0
    false_fail: int = 0
    false_pass: int = 0
    hedged: int = 0
    unanswered: int = 0
    #: The non-answers, split three ways. Kept beside ``unanswered`` rather
    #: than replacing it, because the three are one thing to the arithmetic
    #: and three things to a reader deciding what to fix.
    unanswered_by_kind: dict[str, int] = field(
        default_factory=lambda: {kind: 0 for kind in UNANSWERED_KINDS}
    )

    def add(self, outcome: str, kind: Optional[str] = None) -> None:
        setattr(self, outcome, getattr(self, outcome) + 1)
        if kind is not None:
            if kind not in self.unanswered_by_kind:
                raise ValueError(f"unknown unanswered kind: {kind!r}")
            self.unanswered_by_kind[kind] += 1

    @property
    def answered(self) -> int:
        """Calls that produced a verdict, hedges included.

        A hedge answered; it just did not decide. Excluding it from the
        denominator would let a model that hedged nineteen times out of twenty
        and guessed the last one report 100% accuracy.
        """
        return self.correct + self.false_fail + self.false_pass + self.hedged

    @property
    def calls(self) -> int:
        return self.answered + self.unanswered

    def to_dict(self) -> dict[str, Any]:
        return {
            "calls": self.calls,
            "answered": self.answered,
            "correct": self.correct,
            "false_fail": self.false_fail,
            "false_pass": self.false_pass,
            "hedged": self.hedged,
            "unanswered": self.unanswered,
            # The same non-answers, told apart. A run whose unanswered count
            # is all read_failure needs a prompt edit; one that is all
            # provider_failure needs an operator; one that is all
            # declined_to_judge is the sub-judge doing its job on audio that
            # does not support a verdict. Reporting only the total was how a
            # prompt defect came to be published as an outage 52 times.
            "unanswered_by_kind": dict(self.unanswered_by_kind),
            "accuracy": _rate(self.correct, self.answered),
            # Reported beside the accuracy, never folded into it. The accuracy
            # divides by the calls that answered; on its own that lets a model
            # which refused nine times out of ten look excellent on the tenth.
            # This is the denominator that would have been hidden.
            "response_rate": _rate(self.answered, self.calls),
        }


def discrimination(
    labelled: Sequence[tuple[bool, str]],
) -> Optional[float]:
    """Youden's J over ``(holds, verdict)`` pairs: P(pass|true) - P(pass|false).

    The point of this number is that accuracy on a balanced corpus cannot
    distinguish a listener from a constant. Answer ``pass`` to all twenty
    criteria and accuracy is 50%; answer ``fail`` to all twenty and accuracy
    is 50%. Both give J = 0. Only a verdict that moves with the audio gives
    J > 0.

    ``None`` when either side has no answered call, for the reason in
    :func:`_rate`.
    """
    true_side = [v for holds, v in labelled if holds and v != "judge_error"]
    false_side = [v for holds, v in labelled if not holds and v != "judge_error"]
    if not true_side or not false_side:
        return None
    pass_given_true = sum(1 for v in true_side if v == "pass") / len(true_side)
    pass_given_false = sum(1 for v in false_side if v == "pass") / len(false_side)
    return pass_given_true - pass_given_false


def permute_within_pairs(
    calls: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    """Exact p-value for J, by swapping the labels inside each matched pair.

    Ten pairs, so 2^10 = 1024 relabellings, enumerated in full rather than
    sampled. Exhaustive enumeration is what makes the p exact and what leaves
    this script with no random state to seed -- the same input gives the same
    number, forever, which is what the repeat-variation work needed and did
    not get for free.

    Swapping *within* a pair rather than across the whole corpus is the same
    stratification the flip-rate permutation used. A free-for-all shuffle
    would generate corpora that could not exist, such as two true criteria
    about the silent clip, and a null built from impossible worlds is not the
    null anyone wants to reject.

    The floor is reported alongside the p, because it is a property of the
    design and not of the result: the smallest value obtainable from 1024
    assignments is 1/1024 = 0.000977. The first version of this corpus had six
    pairs, a floor of 1/64 = 0.015625, and could not produce evidence at the
    0.01 level however well the model did. Adding repeats never changed that
    -- only more pairs could, and four more pairs is what this now has. The
    floor is still published rather than assumed: a reader is told what the
    design can support at the same moment they are told what it found.
    """
    pairs = sorted({call["pair_id"] for call in calls})
    observed = discrimination([(c["holds"], c["verdict"]) for c in calls])
    if observed is None:
        return {
            "scheme": "within_pair",
            "pairs": len(pairs),
            "assignments": 0,
            "observed_j": None,
            "at_least_observed": None,
            "p_one_sided": None,
            "smallest_attainable_p": None,
        }
    at_least = 0
    assignments = 0
    for flips in itertools.product((False, True), repeat=len(pairs)):
        flipped = dict(zip(pairs, flips))
        relabelled = [
            (
                call["holds"] != flipped[call["pair_id"]],
                call["verdict"],
            )
            for call in calls
        ]
        candidate = discrimination(relabelled)
        assignments += 1
        if candidate is not None and candidate >= observed - 1e-12:
            at_least += 1
    return {
        "scheme": "within_pair",
        "pairs": len(pairs),
        "assignments": assignments,
        "observed_j": observed,
        "at_least_observed": at_least,
        "p_one_sided": at_least / assignments if assignments else None,
        "smallest_attainable_p": 1.0 / assignments if assignments else None,
    }


def majority_verdict(verdicts: Sequence[str]) -> Optional[str]:
    """The verdict a claim gave most often, or ``None`` on a tie.

    Ties are left as ``None`` rather than broken by order. A claim that
    answered ``pass``, ``fail``, ``partial`` across three repeats has no
    majority answer, and inventing one out of whichever came first would put
    the flip rate this whole card is about inside the accuracy number without
    saying so.
    """
    answered = [v for v in verdicts if v != "judge_error"]
    if not answered:
        return None
    counts: dict[str, int] = {}
    for verdict in answered:
        counts[verdict] = counts.get(verdict, 0) + 1
    best = max(counts.values())
    winners = [v for v, n in counts.items() if n == best]
    return winners[0] if len(winners) == 1 else None


# --------------------------------------------------------------------------
# Comparing two arms
# --------------------------------------------------------------------------


def mcnemar_exact(b: int, c: int) -> Optional[float]:
    """Two-sided exact p for ``b`` wins one way against ``c`` the other.

    The arms are run on the same twenty criteria against the same clip bytes,
    so the comparison is *paired* and an unpaired test would throw away the
    pairing and answer a question nobody asked. McNemar's test looks only at
    the discordant calls -- the ones where exactly one arm was right -- and
    asks whether they split more lopsidedly than a coin would. Exact, by
    summing the binomial rather than leaning on a chi-square approximation
    that is not trustworthy at the counts this corpus can produce.

    ``None`` when nothing was discordant: the arms agreed on every call, and
    "no evidence of a difference" is the honest reading of that rather than
    ``p = 1.0`` dressed up as a measurement.
    """
    n = b + c
    if n == 0:
        return None
    tail = sum(math.comb(n, i) for i in range(min(b, c) + 1))
    return min(1.0, 2 * tail / (2 ** n))


def pearson_r(xs: Sequence[float], ys: Sequence[float]) -> Optional[float]:
    """Correlation, for the one place it is evidence rather than decoration.

    Prompt tokens against clip seconds. If the audio never reached the model,
    the count cannot track the duration of a file the request did not carry.
    """
    if len(xs) != len(ys) or len(xs) < 3:
        return None
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0:
        return None
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return sxy / math.sqrt(sxx * syy)


def _arm_of(call: dict[str, Any]) -> str:
    """The arm a call belongs to, defaulting to the arm that has no wrapper."""
    return str(call.get("arm") or "production")


def compare_arms(
    calls: Sequence[dict[str, Any]],
    *,
    control: str = "production",
    treatment: str = "observation",
) -> Optional[dict[str, Any]]:
    """The paired difference between two prompts, or ``None`` if one is absent.

    Pairing is on ``(claim, repeat)``: the same criterion, the same clip, the
    same repeat index, put twice in immediate succession under two prompts.
    Only calls with a partner on the other side are counted, because a call
    whose partner failed to come back is not a pair and averaging it in would
    quietly compare different corpora.
    """
    by_key: dict[tuple[str, int], dict[str, dict[str, Any]]] = {}
    for call in calls:
        arm = _arm_of(call)
        if arm not in (control, treatment):
            continue
        key = (call["claim_id"], int(call["repeat"]))
        by_key.setdefault(key, {})[arm] = call
    paired = [v for v in by_key.values() if control in v and treatment in v]
    if not paired:
        return None

    b = c = both = neither = 0
    for pair in paired:
        # A hedge and a non-answer are both "not correct" here. The arms are
        # being compared on whether they got the criterion right, and a model
        # that stopped answering has not improved.
        ctl = pair[control]["outcome"] == OUTCOME_CORRECT
        trt = pair[treatment]["outcome"] == OUTCOME_CORRECT
        if ctl and trt:
            both += 1
        elif ctl and not trt:
            b += 1
        elif trt and not ctl:
            c += 1
        else:
            neither += 1

    def _side(arm: str) -> dict[str, Any]:
        rows = [pair[arm] for pair in paired]
        answered = [r for r in rows if r["outcome"] != OUTCOME_UNANSWERED]
        return {
            "correct": sum(1 for r in rows if r["outcome"] == OUTCOME_CORRECT),
            "answered": len(answered),
            "attempts": len(rows),
            "accuracy_of_answered": _rate(
                sum(1 for r in rows if r["outcome"] == OUTCOME_CORRECT),
                len(answered),
            ),
            "response_rate": _rate(len(answered), len(rows)),
            # Why this arm did not answer, when it did not. An arm can lose a
            # comparison on response rate alone; whether that is the prompt's
            # fault or the wire's is the whole difference between "the change
            # under test made the model stop replying properly" and "the
            # region had a bad afternoon".
            "unanswered_by_kind": {
                kind: sum(1 for r in rows if r.get("unanswered_kind") == kind)
                for kind in UNANSWERED_KINDS
            },
            "discrimination_j": discrimination(
                [(r["holds"], r["verdict"]) for r in rows]
            ),
        }

    p_value = mcnemar_exact(b, c)
    return {
        "pairs": len(paired),
        "control": control,
        "treatment": treatment,
        control: _side(control),
        treatment: _side(treatment),
        "discordant": {
            "control_only_correct": b,
            "treatment_only_correct": c,
            "both_correct": both,
            "neither_correct": neither,
        },
        "mcnemar_exact_p": p_value,
        "reading": (
            "Exact two-sided McNemar on the discordant calls. A large p means "
            "this corpus did not detect a difference between the prompts; it "
            "does NOT mean the prompts are equivalent. With "
            f"{b + c} discordant calls out of {len(paired)}, only a large "
            "effect could have shown up at all, and the interval on the "
            "difference is correspondingly wide."
        ),
    }


# --------------------------------------------------------------------------
# Identity
# --------------------------------------------------------------------------


def _read_yaml(path: Path) -> dict[str, Any]:
    import yaml  # local import: keeps --help working without the dependency

    with path.open(encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle)
    if not isinstance(loaded, dict):
        raise ValueError(f"{path} is not a mapping")
    return loaded


def pinned_identity(config_path: Path = PINNED_CONFIG) -> dict[str, Any]:
    """The audio identity this measurement borrows, read from the config.

    Not restated as constants. The figure produced here is only an
    explanation of the 19.35% if it describes the same deployment at the same
    clip length; reading it out of the file the repeat runs used is what makes
    that true by construction instead of by a comment.

    The identity is resolved with :func:`canonical_deployment` -- the same
    call ``grader.py`` makes on the same config path -- rather than by pulling
    the fields out here. A config whose ``model`` and ``deployment`` disagree
    is rejected by the grader's own rule, not by a second implementation of it
    that could drift.
    """
    from core.azure_ai_clients import canonical_deployment

    config = _read_yaml(config_path)
    judge = config.get("judge")
    perception = judge.get("perception") if isinstance(judge, dict) else None
    audio = perception.get("audio") if isinstance(perception, dict) else None
    if not isinstance(audio, dict) or not audio:
        raise ValueError(f"{config_path} has no judge.perception.audio")
    deployment = canonical_deployment(audio, "judge.perception.audio")
    return {
        "config": config_path.name,
        "audio_model": audio.get("model"),
        "audio_deployment": deployment,
        "audio_clip_seconds": int(audio.get("trim_seconds", AUDIO_TRIM_SECONDS)),
        "audio_call_cap_per_task": int(
            audio.get("call_cap_per_task", AUDIO_CALL_CAP)
        ),
        "provider": (
            judge.get("provider", "azure_openai")
            if isinstance(judge, dict)
            else "azure_openai"
        ),
    }


# --------------------------------------------------------------------------
# The stub, for the free run
# --------------------------------------------------------------------------


class _StubChoice:
    def __init__(self, content: str) -> None:
        self.message = type("_M", (), {"content": content})()


class _StubUsage:
    """A token count derived from what the stub was actually sent.

    Not invented: ``prompt_tokens`` is a function of the base64 the request
    carried, so a longer clip really does produce a larger count and the
    delivery section's token-against-duration line has genuine variance to
    work on in a free run. What the stub will *not* fabricate is
    ``audio_tokens``. That field is a provider's statement that it read the
    part as audio, and there is no provider here to make it.
    """

    def __init__(self, b64_chars: int, completion_tokens: int) -> None:
        self.prompt_tokens = 100 + b64_chars // 1000
        self.completion_tokens = completion_tokens
        self.total_tokens = self.prompt_tokens + completion_tokens


class _StubResponse:
    def __init__(self, content: str, *, b64_chars: int = 0) -> None:
        self.choices = [_StubChoice(content)]
        self.usage = _StubUsage(b64_chars, max(1, len(content) // 4))
        #: The stub answers as itself. A dry run's report then names
        #: ``stub-not-a-model`` where a paid one names the deployment, so a
        #: free artifact cannot be read as describing ``gpt-audio-1.5``.
        self.model = "stub-not-a-model"


class TruthfulStub:
    """A stand-in that answers from the segment list instead of listening.

    It exists so ``--dry-run`` exercises every line between here and the
    scorer -- render, trim, base64, prompt assembly, envelope parse, tally,
    permutation -- without a network call. It answers *correctly*, which makes
    it a shape check and emphatically not a measurement: a dry run reporting
    100% accuracy says the pipeline works, and says nothing whatsoever about
    ``gpt-audio-1.5``. The report marks itself ``"measured": false`` for
    exactly this reason.
    """

    def __init__(self, claims: Sequence[Claim]) -> None:
        self._by_criterion = {claim.criterion: claim for claim in claims}
        self.requests: list[dict[str, Any]] = []
        self.chat = type("_Chat", (), {"completions": self})()

    def create(self, **kwargs: Any) -> _StubResponse:
        self.requests.append(kwargs)
        text = ""
        b64_chars = 0
        for part in kwargs["messages"][0]["content"]:
            if part.get("type") == "text":
                text = part["text"]
            elif part.get("type") == "input_audio":
                b64_chars = len((part.get("input_audio") or {}).get("data") or "")
        claim = None
        for criterion, candidate in self._by_criterion.items():
            if criterion in text:
                claim = candidate
                break
        if claim is None:  # pragma: no cover - defended by a test
            raise AssertionError("stub was sent a criterion it does not know")
        return _StubResponse(
            json.dumps(
                {
                    "verdict": "pass" if claim.holds else "fail",
                    "partial_score": 1.0 if claim.holds else 0.0,
                    "evidence": claim.because[:200],
                    "confidence": 1.0,
                    "reasoning": "stub: answered from the segment list",
                }
            ),
            b64_chars=b64_chars,
        )


# --------------------------------------------------------------------------
# What actually went on the wire
# --------------------------------------------------------------------------
#
# The first measured run reported 51.85% accuracy and a discrimination of
# essentially zero, and the write-up read that as a statement about the model.
# It is only a statement about the model if the model was given the audio. A
# request that assembled the text part and dropped the ``input_audio`` part
# would produce exactly the same numbers -- a judge answering from the
# criterion's wording alone is precisely what near-zero J looks like -- and
# nothing in the report could tell the two apart.
#
# So the wire is recorded. Not the audio: a hash of it, its length, and the
# facts a WAV header states about itself. Enough to prove bytes went out and
# to prove they were the bytes rendered, without putting a megabyte of base64
# into an artifact or a log.
#
# This lives here rather than in ``core/perception/audio.py`` on purpose. The
# production sub-judge is what is under investigation; instrumenting the thing
# you are measuring changes what you are measuring, and a diagnostic has no
# business editing the grader while a fingerprint freeze is in force.


#: The separator ``AudioPerception.judge`` puts between its system header and
#: the criterion. The observation arm has to split the outgoing text there to
#: swap the header while keeping the criterion byte-identical. If core ever
#: renames it, the split fails loudly rather than silently shipping the
#: production prompt under the observation arm's name -- which would make the
#: two arms identical and the comparison a fabrication. A test pins it against
#: the real module.
PRODUCTION_CRITERION_MARKER = "\n\nCriterion:\n"

#: The alternative prompt. It is a *bundle*, and the pre-registration says so:
#: it (i) demands observation before judgement, (ii) states outright that the
#: claim may be false and that its wording is the thing under test rather than
#: a fact, (iii) offers ``judge_error`` as the honest answer when the audio
#: does not decide it, (iv) drops the production header's "head-only slice
#: (first 30s)" framing -- which is true of a graded deliverable and false of
#: a 6-second clip, and which the first run's evidence strings echoed back --
#: and (v) says "Statement" where production says "Criterion".
#:
#: A difference between the arms cannot be attributed to any one of those
#: five. That is the cost of testing a realistic alternative rather than five
#: separate one-word edits, and it is a limit on the reading, not a defect in
#: the design.
#:
#: What it deliberately does NOT do is tell the model anything about the
#: answer: no per-item hint, and no statement of how many claims are true.
#:
#: **The response contract is not part of the bundle.** It used to be: this
#: string carried its own "Return the same JSON envelope as the main judge"
#: paragraph, written separately from the one core sent, and the two drifted.
#: Run 34008840627 is what that costs -- 60 of this arm's 60 replies failed
#: the format, 43 unparseably and 17 in a ``true``/``false`` vocabulary, so
#: the arm's measured response rate was 0.000 and the comparison measured
#: which paragraph described JSON better rather than which prompt heard
#: better. ``AUDIO_RESPONSE_CONTRACT`` is now appended verbatim to both arms,
#: so whatever else differs, the shape being asked for does not.
OBSERVATION_HEADER = (
    "You are an audio analyst. A short audio clip has been supplied to you as "
    "audio input. Work only from that audio. Nothing you have been told about "
    "the clip is a substitute for listening to it.\n\n"
    "FIRST, before treating the statement below as anything but words, "
    "observe the clip and note what you can actually measure from it: how "
    "long it runs; whether any sound is present at all; how many discrete "
    "sound events occur and at what times; what pitches, intervals and "
    "harmonic content are present.\n\n"
    "THEN judge the statement against those observations. The statement may "
    "be true or it may be false. Do not assume it is true, and do not let its "
    "wording tell you what you heard: if it names a count, a tempo, a key or "
    "an interval, that number is the claim under test, not a fact about the "
    "clip. If the audio does not let you decide, return verdict "
    "\"judge_error\" rather than guessing.\n\n"
    "In \"evidence\", state the value you observed before you state whether "
    "the statement holds.\n\n"
) + AUDIO_RESPONSE_CONTRACT

#: Arm identifiers. ``production`` forwards the request untouched, so the
#: control arm is the real grading prompt and not a re-implementation of it.
PROMPT_ARMS = ("production", "observation")


def _wav_facts(data: bytes) -> dict[str, Any]:
    """What the bytes on the wire say about themselves.

    Read back out of the payload rather than assumed from the render: the
    clip is written at :data:`CLIP_SAMPLE_RATE_HZ` and the grader re-encodes
    it to :data:`AUDIO_SAMPLE_RATE_HZ` mono before sending, so the file on
    disk and the bytes in the request are not the same bytes and do not have
    the same digest. Only one of them is evidence about what the model heard.
    """
    facts: dict[str, Any] = {
        "riff": data[:4].decode("ascii", "replace"),
        "wave": data[8:12].decode("ascii", "replace"),
        "bytes": len(data),
    }
    try:
        with contextlib.closing(wave.open(io.BytesIO(data), "rb")) as handle:
            channels = handle.getnchannels()
            width = handle.getsampwidth()
            rate = handle.getframerate()
            frames = handle.getnframes()
            facts.update(
                channels=channels,
                sample_width_bytes=width,
                sample_rate_hz=rate,
                frames=frames,
                duration_s=round(frames / rate, 4) if rate else None,
            )
            # A muxer that streams its output can leave the frame count at
            # zero in the header. Deriving it from the payload size keeps the
            # duration check honest when that happens instead of reporting a
            # confident 0.0 seconds.
            per_frame = channels * width
            if per_frame and rate:
                facts["duration_s_from_size"] = round(
                    max(len(data) - 44, 0) / (per_frame * rate), 4
                )
    except Exception as exc:  # noqa: BLE001 - a malformed payload is a finding
        facts["parse_error"] = f"{type(exc).__name__}: {exc}"
    return facts


def _audio_usage_facts(response: Any) -> dict[str, Any]:
    """Whether the reply accounted for any *audio* tokens.

    ``core.cost_metering.extract_usage`` reads the input, output and cached
    counts and stops; the audio breakdown is not part of a price lookup and
    so was never pulled. It is the single most direct piece of evidence that
    a request was understood as carrying audio, so the diagnostic reads it
    even though the ledger does not.
    """
    usage = getattr(response, "usage", None)
    out: dict[str, Any] = {
        "usage_present": usage is not None,
        "audio_tokens": None,
        "audio_tokens_source": None,
    }
    if usage is None:
        return out
    for name in ("prompt_tokens_details", "input_tokens_details"):
        details = getattr(usage, name, None)
        if details is None and isinstance(usage, dict):
            details = usage.get(name)
        if details is None:
            continue
        value = getattr(details, "audio_tokens", None)
        if value is None and isinstance(details, dict):
            value = details.get("audio_tokens")
        if value is not None:
            out["audio_tokens"] = int(value)
            out["audio_tokens_source"] = name
            break
    return out


def split_production_text(text: str) -> tuple[str, str]:
    """``(header, criterion)`` from the text part the grader assembled."""
    index = text.find(PRODUCTION_CRITERION_MARKER)
    if index < 0:
        raise ValueError(
            "the outgoing text part does not carry "
            f"{PRODUCTION_CRITERION_MARKER!r}; core/perception/audio.py has "
            "changed its prompt assembly and the observation arm cannot swap "
            "the header without also rewriting the criterion"
        )
    return text[:index], text[index + len(PRODUCTION_CRITERION_MARKER):]


def apply_arm(kwargs: dict[str, Any], arm: str) -> dict[str, Any]:
    """Rewrite the outgoing request for ``arm``, touching only the text part.

    Everything that is not the prompt -- model, modalities, and above all the
    ``input_audio`` part -- is passed through by reference. The two arms
    therefore send byte-identical audio by construction rather than by
    assertion, and a test still asserts it.
    """
    if arm == "production":
        return kwargs
    if arm != "observation":
        raise ValueError(f"unknown prompt arm: {arm}")
    messages = []
    for message in kwargs["messages"]:
        content = []
        for part in message["content"]:
            if part.get("type") == "text":
                _, criterion = split_production_text(part["text"])
                content.append({
                    "type": "text",
                    "text": f"{OBSERVATION_HEADER}\n\nStatement:\n{criterion}",
                })
            else:
                content.append(part)
        messages.append({**message, "content": content})
    return {**kwargs, "messages": messages}


class WireClient:
    """Wraps the grader's client to record the request and switch the arm.

    Two jobs in one wrapper because they are the same interception point, and
    splitting them would mean the arm swap happened somewhere the recorder
    could not see -- leaving the report unable to say which prompt each call
    actually carried.
    """

    def __init__(self, inner: Any, *, arm: str = "production") -> None:
        self._inner = inner
        self.arm = arm
        self.records: list[dict[str, Any]] = []
        self.chat = type("_Chat", (), {"completions": self})()

    def create(self, **kwargs: Any) -> Any:
        record: dict[str, Any] = {"arm": self.arm}
        record.update(self._inspect(kwargs))
        sent = apply_arm(kwargs, self.arm)
        # Recorded after the swap: the point of the record is what went out,
        # and under the observation arm that is not what came in.
        for message in sent["messages"]:
            for part in message["content"]:
                if part.get("type") == "text":
                    text = part["text"]
                    record["prompt_chars"] = len(text)
                    record["prompt_sha256"] = hashlib.sha256(
                        text.encode("utf-8")
                    ).hexdigest()
        record["requested_model"] = sent.get("model")
        try:
            response = self._inner.chat.completions.create(**sent)
        except Exception as exc:  # noqa: BLE001 - recorded, then re-raised
            record["transport_error"] = type(exc).__name__
            self.records.append(record)
            raise
        record["response_model"] = resolved_model_of(
            response, str(sent.get("model") or "")
        )
        record.update(_audio_usage_facts(response))
        self.records.append(record)
        return response

    @staticmethod
    def _inspect(kwargs: dict[str, Any]) -> dict[str, Any]:
        """Facts about the audio part, or its absence.

        ``audio_part_present: false`` is the finding this whole class exists
        to be able to report. Nothing raises on it -- a diagnostic that
        crashes on the defect it is looking for cannot describe it.
        """
        found: dict[str, Any] = {
            "audio_part_present": False,
            "audio_parts": 0,
            "audio_b64_chars": 0,
            "audio_sha256": None,
            "audio_format": None,
        }
        for message in kwargs.get("messages", []):
            for part in message.get("content", []):
                if part.get("type") != "input_audio":
                    continue
                found["audio_parts"] += 1
                blob = part.get("input_audio") or {}
                b64 = blob.get("data") or ""
                found["audio_format"] = blob.get("format")
                found["audio_b64_chars"] = len(b64)
                if not b64:
                    continue
                try:
                    data = base64.b64decode(b64, validate=True)
                except Exception as exc:  # noqa: BLE001
                    found["audio_b64_error"] = f"{type(exc).__name__}: {exc}"
                    continue
                found["audio_part_present"] = True
                found["audio_sha256"] = hashlib.sha256(data).hexdigest()
                found["sent_wav"] = _wav_facts(data)
        return found


def summarise_wire(records: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """The per-call digest that goes in the report next to the verdict.

    One judge call can make more than one request -- the sub-judge retries a
    malformed envelope -- so this collapses however many there were into the
    facts that matter per verdict, and keeps the count so a reader can see
    that it did.
    """
    sent = [r for r in records if r.get("audio_part_present")]
    wav = (sent[-1].get("sent_wav") or {}) if sent else {}
    tokens = [
        r["audio_tokens"] for r in records if r.get("audio_tokens") is not None
    ]
    return {
        "requests": len(records),
        "requests_with_audio": len(sent),
        "audio_sha256": sent[-1]["audio_sha256"] if sent else None,
        "audio_bytes": wav.get("bytes"),
        "audio_sample_rate_hz": wav.get("sample_rate_hz"),
        "audio_channels": wav.get("channels"),
        "audio_duration_s": wav.get("duration_s"),
        "audio_format": sent[-1]["audio_format"] if sent else None,
        "prompt_sha256": records[-1].get("prompt_sha256") if records else None,
        "prompt_chars": records[-1].get("prompt_chars") if records else None,
        "response_model": records[-1].get("response_model") if records else None,
        "audio_tokens": tokens[-1] if tokens else None,
    }


def delivery_section(
    calls: Sequence[dict[str, Any]],
    *,
    measured: bool,
    clips: Sequence[Clip] = CLIPS,
) -> Optional[dict[str, Any]]:
    """Did the audio reach the model, and did it reach it intact?

    The first run could not answer this, and the accuracy it reported is only
    a fact about ``gpt-audio-1.5`` if the answer is yes. Four independent
    lines are reported rather than one, because each fails differently:

    * the request carried a decodable ``input_audio`` part at all;
    * the bytes in it parse as a WAV of the sample rate, channel count and
      duration the clip was rendered at, so nothing truncated them;
    * every arm and repeat of a given clip sent the *same* digest, so the two
      prompts were compared against identical audio;
    * prompt tokens track clip duration, which is the one line that depends
      on the provider having understood the part rather than merely accepted
      it. A request whose audio was dropped on the far side would still show
      the first three.
    """
    wired = [c for c in calls if isinstance(c.get("wire"), dict)]
    if not wired:
        return None
    durations = {clip.clip_id: clip.duration_s for clip in clips}

    by_clip: dict[str, set[str]] = {}
    for call in wired:
        digest = call["wire"].get("audio_sha256")
        if digest:
            by_clip.setdefault(call["clip_id"], set()).add(digest)

    mismatched_duration = sorted(
        {
            call["clip_id"]
            for call in wired
            if call["wire"].get("audio_duration_s") is not None
            and abs(
                float(call["wire"]["audio_duration_s"])
                - durations.get(call["clip_id"], -1.0)
            )
            > 0.05
        }
    )
    paired = [
        (durations[c["clip_id"]], float(c["input_tokens"]))
        for c in wired
        if c.get("input_tokens") is not None and c["clip_id"] in durations
    ]
    models = sorted({
        str(c["wire"]["response_model"])
        for c in wired
        if c["wire"].get("response_model")
    })
    return {
        "measured": measured,
        "calls_inspected": len(wired),
        "calls_carrying_audio": sum(
            1 for c in wired if c["wire"].get("requests_with_audio")
        ),
        "calls_without_audio": sorted(
            c["claim_id"]
            for c in wired
            if not c["wire"].get("requests_with_audio")
        ),
        "sent_formats": sorted(
            {str(c["wire"]["audio_format"]) for c in wired
             if c["wire"].get("audio_format")}
        ),
        "sent_sample_rates_hz": sorted(
            {int(c["wire"]["audio_sample_rate_hz"]) for c in wired
             if c["wire"].get("audio_sample_rate_hz")}
        ),
        "sent_channels": sorted(
            {int(c["wire"]["audio_channels"]) for c in wired
             if c["wire"].get("audio_channels")}
        ),
        "digests_per_clip": {
            clip_id: sorted(digests) for clip_id, digests in sorted(by_clip.items())
        },
        "clips_with_more_than_one_digest": sorted(
            clip_id for clip_id, digests in by_clip.items() if len(digests) > 1
        ),
        "clips_whose_sent_duration_differs": mismatched_duration,
        "response_models": models,
        "audio_tokens_reported": sum(
            1 for c in wired if c["wire"].get("audio_tokens") is not None
        ),
        "prompt_token_vs_clip_seconds": {
            "n": len(paired),
            "pearson_r": pearson_r([d for d, _ in paired], [t for _, t in paired]),
            "meaning": (
                "Prompt tokens against clip duration. Near 1 means the count "
                "scales with the audio, which a request that did not carry it "
                "cannot do. Near 0 with audio parts present would mean the "
                "part was accepted and not charged for -- a different and "
                "worse failure than never sending it."
            ),
        },
        "not_covered": (
            "This shows the bytes left this process correctly and were billed "
            "as audio. It cannot show what the model did with them."
            if measured
            else "No provider was called. Every figure here describes the "
            "stub, which reports no audio tokens and answers as "
            "'stub-not-a-model'. It proves the plumbing, not the delivery."
        ),
    }


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------


def run_measurement(
    *,
    perception: AudioPerception,
    clip_dir: Path,
    repeats: int,
    claims: Sequence[Claim] = CLAIMS,
    clips: Sequence[Clip] = CLIPS,
    on_call: Optional[Callable[[int, int, Claim, AudioVerdict], None]] = None,
    arms: Sequence[str] = ("production",),
    wire: Optional[WireClient] = None,
) -> dict[str, Any]:
    """Render the clips, put every claim to the sub-judge, and tally.

    The per-task call cap is reset between claims on purpose. The cap exists
    to bound what one graded task spends; here each criterion is its own unit
    of work against its own clip, and letting a corpus-wide counter run into
    the cap would silently turn the tail of the corpus into ``cap_exceeded``
    refusals that look like model behaviour and are not.

    When two arms are given, they are **interleaved** rather than run one
    after the other: the same criterion goes out under both prompts back to
    back, then the next criterion. A model whose behaviour drifts over an
    hour, or a deployment that is rerouted mid-run, then moves both arms
    together instead of landing entirely on whichever one was scheduled
    second. It is the same reason the pairing exists in the corpus, applied to
    time instead of to truth value.
    """
    for arm in arms:
        if arm not in PROMPT_ARMS:
            raise ValueError(f"unknown prompt arm: {arm}")
    if wire is None and tuple(arms) != ("production",):
        # The arm swap happens inside the wrapper. Without one, the request
        # would go out under the production prompt and be labelled with the
        # other arm's name, which is not a weaker measurement but a false one.
        raise ValueError("a non-production arm needs a WireClient to rewrite it")

    digests: dict[str, str] = {}
    paths: dict[str, Path] = {}
    for clip in clips:
        path = clip_dir / f"{clip.clip_id}.wav"
        digests[clip.clip_id] = render_clip(clip, path)
        paths[clip.clip_id] = path

    calls: list[dict[str, Any]] = []
    for repeat in range(1, repeats + 1):
        for claim in claims:
            for arm in arms:
                if wire is not None:
                    wire.arm = arm
                    first_record = len(wire.records)
                perception.reset()
                verdict = perception.judge(
                    criterion=claim.criterion,
                    audio_path=str(paths[claim.clip_id]),
                )
                if on_call is not None:
                    on_call(repeat, len(calls) + 1, claim, verdict)
                call = {
                    "repeat": repeat,
                    "arm": arm,
                    "claim_id": claim.claim_id,
                    "pair_id": claim.pair_id,
                    "clip_id": claim.clip_id,
                    "family": claim.family,
                    "holds": claim.holds,
                    "verdict": verdict.verdict,
                    "outcome": classify(claim, verdict.verdict),
                    "unanswered_kind": unanswered_kind(
                        verdict.verdict, verdict.judge_error
                    ),
                    "confidence": verdict.confidence,
                    "evidence": verdict.evidence,
                    "judge_error": verdict.judge_error,
                    "api_call_count": verdict.api_call_count,
                    "input_tokens": verdict.input_tokens,
                    "output_tokens": verdict.output_tokens,
                    "latency_ms": round(verdict.latency_ms, 3),
                    "usage_complete": verdict.usage_complete,
                }
                if wire is not None:
                    call["wire"] = summarise_wire(wire.records[first_record:])
                calls.append(call)
    return {"calls": calls, "clip_sha256": digests}


def summarise(calls: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Turn the call log into the three numbers the card asked for."""
    overall = Tally()
    on_true = Tally()
    on_false = Tally()
    by_family: dict[str, Tally] = {}
    for call in calls:
        # ``.get`` rather than ``[...]``: a call log written before the split
        # existed has no such key, and re-summarising an older result must
        # report an empty breakdown rather than crash or invent one.
        kind = call.get("unanswered_kind")
        overall.add(call["outcome"], kind)
        (on_true if call["holds"] else on_false).add(call["outcome"], kind)
        by_family.setdefault(call["family"], Tally()).add(call["outcome"], kind)

    by_claim: dict[str, Any] = {}
    for claim in CLAIMS:
        verdicts = [c["verdict"] for c in calls if c["claim_id"] == claim.claim_id]
        if not verdicts:
            continue
        majority = majority_verdict(verdicts)
        by_claim[claim.claim_id] = {
            "holds": claim.holds,
            "family": claim.family,
            "verdicts": verdicts,
            "majority": majority,
            "stable": len(set(verdicts)) == 1,
            "majority_outcome": (
                classify(claim, majority) if majority is not None else None
            ),
        }

    per_call = discrimination([(c["holds"], c["verdict"]) for c in calls])
    majority_labelled = [
        (entry["holds"], entry["majority"])
        for entry in by_claim.values()
        if entry["majority"] is not None
    ]
    confidences = {
        key: [
            c["confidence"]
            for c in calls
            if c["outcome"] == key and c["confidence"] is not None
        ]
        for key in (OUTCOME_CORRECT, OUTCOME_FALSE_FAIL, OUTCOME_FALSE_PASS)
    }
    return {
        "overall": overall.to_dict(),
        "on_true_claims": {
            **on_true.to_dict(),
            "false_fail_rate": _rate(on_true.false_fail, on_true.answered),
        },
        "on_false_claims": {
            **on_false.to_dict(),
            "false_pass_rate": _rate(on_false.false_pass, on_false.answered),
        },
        "by_family": {
            name: tally.to_dict() for name, tally in sorted(by_family.items())
        },
        "by_claim": by_claim,
        "discrimination_j": {
            "per_call": per_call,
            "per_claim_majority": discrimination(majority_labelled),
            "meaning": (
                "P(pass|true) - P(pass|false). 0 means the verdict does not "
                "depend on the audio; accuracy alone cannot show that."
            ),
        },
        "permutation": permute_within_pairs(calls),
        "mean_confidence": {
            key: (sum(values) / len(values) if values else None)
            for key, values in confidences.items()
        },
        "stability": {
            "claims": len(by_claim),
            "identical_across_repeats": sum(
                1 for entry in by_claim.values() if entry["stable"]
            ),
            "no_majority": sum(
                1 for entry in by_claim.values() if entry["majority"] is None
            ),
        },
    }


def unanswered_claims(calls: Sequence[dict[str, Any]]) -> list[str]:
    """Claims for which no call produced a verdict at all."""
    seen: dict[str, bool] = {}
    for call in calls:
        answered = call["verdict"] != "judge_error"
        seen[call["claim_id"]] = seen.get(call["claim_id"], False) or answered
    return sorted(claim_id for claim_id, ok in seen.items() if not ok)


def build_report(
    *,
    identity: dict[str, Any],
    measured: bool,
    repeats: int,
    result: dict[str, Any],
) -> dict[str, Any]:
    calls = result["calls"]
    model_calls = sum(int(call["api_call_count"]) for call in calls)
    billable = model_calls if measured else 0
    # Execution order, not alphabetical: which arm went first is a fact about
    # the run, and "observation, production" would misdescribe an interleave
    # that always puts the control first.
    arms_present = list(dict.fromkeys(_arm_of(call) for call in calls))

    control_calls = [c for c in calls if _arm_of(c) == "production"] or list(calls)
    report = {
        "what_this_measures": (
            "Whether the audio sub-judge's verdict is correct, on clips whose "
            "contents are known by construction. The repeat runs measured "
            f"consistency ({REPEAT_FLIP_RATE_PCT}% of audio verdict pairs "
            f"disagree, against {REPEAT_TEXT_FLIP_RATE_PCT}% on text). "
            "Consistency is not correctness and neither implies the other."
        ),
        "measured": measured,
        "pins": {
            **identity,
            "clip_sample_rate_hz": CLIP_SAMPLE_RATE_HZ,
            "grader_resample_rate_hz": AUDIO_SAMPLE_RATE_HZ,
            "repeats": repeats,
            "claims": len(CLAIMS),
            "clips": len(CLIPS),
            "true_claims": sum(1 for c in CLAIMS if c.holds),
            "false_claims": sum(1 for c in CLAIMS if not c.holds),
            "prompt_arms": arms_present,
        },
        "clips": [clip.to_dict() for clip in CLIPS],
        "clip_sha256": result["clip_sha256"],
        "claims": [claim.to_dict() for claim in CLAIMS],
        "calls": calls,
        # Always the production prompt, so this number keeps meaning what it
        # meant before there was a second arm: how the *grader* behaves. The
        # alternative prompt's figures live under "arms" and are never folded
        # in, because averaging the two would describe a prompt nothing runs.
        "accuracy": summarise(control_calls),
        "cost": {
            # Two numbers, because a dry run makes 60 calls and is billed for
            # none of them. Collapsing them would put a "billable_calls: 60"
            # into a free run's report, and that is exactly the figure someone
            # copies into a cost record.
            "model_calls": model_calls,
            "billable_calls": billable,
            "models": [identity["audio_deployment"]] if billable else [],
            "pricing_complete": not billable,
            "unpriced_models": (
                [identity["audio_deployment"]] if billable else []
            ),
            "estimated_cost_usd": None,
            "note": (
                "gpt-audio-1.5 is absent from the price table, so the cost of "
                "this run is unknown rather than zero. null, not $0."
                if billable
                else "No model was called; this run cost nothing."
            ),
        },
    }

    delivery = delivery_section(calls, measured=measured)
    if delivery is not None:
        report["delivery"] = delivery

    if len(arms_present) > 1:
        report["arms"] = {
            arm: summarise([c for c in calls if _arm_of(c) == arm])
            for arm in arms_present
        }
        report["arm_comparison"] = compare_arms(calls)
    return report


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--repeats",
        type=int,
        default=3,
        help=(
            "How many times to put each criterion. Three by default, matching "
            "the repeat runs, so a claim's stability here is comparable with "
            "the flip rate there."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Run the whole path against a stub that answers from the segment "
            "list. No network call, no cost, and no measurement of the model."
        ),
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=PINNED_CONFIG,
        help="Grading config to read the audio identity from.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write the JSON report here as well as to stdout.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress the per-call progress lines.",
    )
    parser.add_argument(
        "--prompt-arm",
        choices=(*PROMPT_ARMS, "both"),
        default="production",
        help=(
            "Which prompt to put the criteria under. 'production' is the "
            "grader's own header, unchanged. 'observation' swaps the header "
            "for one that demands the model measure the clip before judging "
            "the claim. 'both' runs them interleaved on identical audio, "
            "which is the only setting that supports a paired comparison -- "
            "and doubles the call count."
        ),
    )
    parser.add_argument(
        "--delivery-out",
        type=Path,
        default=None,
        help=(
            "Write just the delivery evidence here: what the requests "
            "carried, hashed rather than dumped. Never contains audio, "
            "prompt text or model reasoning."
        ),
    )
    args = parser.parse_args(argv)

    if args.repeats < 1:
        parser.error("--repeats must be at least 1")
    arms = PROMPT_ARMS if args.prompt_arm == "both" else (args.prompt_arm,)

    try:
        identity = pinned_identity(args.config)
    except ValueError as exc:
        # Exit 3, not a traceback. Whatever this would have measured, it was
        # not the audio path the repeat runs used, and a run that cannot say
        # which model it is describing has nothing to report.
        print(f"::error::{exc}", file=sys.stderr)
        return 3
    if identity["audio_clip_seconds"] != AUDIO_TRIM_SECONDS:
        # Not fatal to the arithmetic, but it means the clips the model hears
        # here are cut to a different length than the ones it heard in the
        # runs this is meant to explain.
        print(
            f"::warning::config clip length {identity['audio_clip_seconds']}s "
            f"differs from the module default {AUDIO_TRIM_SECONDS}s",
            file=sys.stderr,
        )

    def progress(repeat: int, index: int, claim: Claim, verdict: AudioVerdict) -> None:
        if args.quiet:
            return
        print(
            f"  [{index:>3}] repeat {repeat} {claim.claim_id:<20} "
            f"holds={str(claim.holds):<5} -> {verdict.verdict}"
            f" ({classify(claim, verdict.verdict)})",
            file=sys.stderr,
        )

    managed = None
    if args.dry_run:
        client: Any = TruthfulStub(CLAIMS)
    else:
        from core.azure_ai_clients import AzureAIWorkload  # noqa: E402
        from core.llm_client import create_typed_azure_client  # noqa: E402

        managed = create_typed_azure_client(
            AzureAIWorkload.GRADER, identity["audio_deployment"]
        )
        client = managed.client

    # Always wrapped, even for a single production arm: the delivery evidence
    # is the reason this run exists, and making it conditional would mean the
    # cheap runs are the ones that cannot say whether the audio arrived.
    wire = WireClient(client, arm=arms[0])

    try:
        perception = AudioPerception(
            client=wire,
            deployment=identity["audio_deployment"],
            call_cap=identity["audio_call_cap_per_task"],
            trim_seconds=identity["audio_clip_seconds"],
        )
        with tempfile.TemporaryDirectory(prefix="audio-accuracy-") as tmp:
            result = run_measurement(
                perception=perception,
                clip_dir=Path(tmp),
                repeats=args.repeats,
                on_call=progress,
                arms=arms,
                wire=wire,
            )
    finally:
        if managed is not None:
            managed.close()

    report = build_report(
        identity=identity,
        measured=not args.dry_run,
        repeats=args.repeats,
        result=result,
    )
    text = json.dumps(report, indent=2, ensure_ascii=False)
    print(text)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    if args.delivery_out is not None:
        args.delivery_out.parent.mkdir(parents=True, exist_ok=True)
        args.delivery_out.write_text(
            json.dumps(
                {
                    "measured": report["measured"],
                    "pins": report["pins"],
                    "clip_sha256": report["clip_sha256"],
                    "delivery": report.get("delivery"),
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

    missing = unanswered_claims(result["calls"])
    if missing:
        print(
            "::error::no verdict was reached for: " + ", ".join(missing),
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
