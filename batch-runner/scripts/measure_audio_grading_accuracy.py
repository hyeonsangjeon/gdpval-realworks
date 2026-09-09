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
import re
import struct
import sys
import tempfile
import time
import wave
from dataclasses import dataclass, field, replace as dataclass_replace
from pathlib import Path
from typing import (
    Any, Callable, Iterable, Iterator, Mapping, Optional, Sequence,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# The production metering path, used rather than reimplemented. 337 spent ten
# paid calls and left no ledger row behind them, because this script wrote its
# own cost block out of constants instead of reaching for the code every graded
# run already uses. Nothing below is a second implementation of that code: the
# recorder reserves and settles, the price table prices, the receipt totals,
# and this file only decides which task the calls belong to and where the
# ledger lives. See 340 for what the absence of these imports cost.
from core.cost_metering import open_cost_recorder, resolved_model_of  # noqa: E402
from core.cost_receipts import (  # noqa: E402
    BUCKET_GRADING,
    PRICE_TABLE_PATH,
    REASON_PRICE_MISSING,
    REASON_USAGE_ABSENT,
    REASON_USAGE_PARTIAL,
    STAGE_GRADING,
    STAGE_PERCEPTION,
    CostReceipt,
    CostReceiptLedger,
    ReceiptPriceTable,
    ledger_reference,
    load_receipt_price_table,
)
from core.perception.audio import (  # noqa: E402
    AUDIO_CALL_CAP,
    AUDIO_FAILURE_BUDGET,
    AUDIO_RESPONSE_CONTRACT,
    AUDIO_SAMPLE_RATE_HZ,
    AUDIO_TRIM_SECONDS,
    AUDIO_VERDICT_VOCABULARY,
    AudioPerception,
    AudioVerdict,
    _offending_token,
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

#: The task every call this script makes is filed under, in the ledger and in
#: the receipt.
#:
#: Not a GDPval task id, and deliberately not shaped like one. These calls
#: grade nothing: they put synthesised clips to the audio sub-judge to find out
#: whether it hears them. Borrowing a real task's identifier would put this
#: diagnostic's spend inside that task's receipt, which is the exact defect
#: 340 section 6.2 condition 5 exists to catch -- and it would be caught in a
#: run nobody is looking at, months later, as an unexplained few cents on a
#: task that was graded in March.
#:
#: One constant rather than a flag. Two runs filing under two names would put
#: one diagnostic's spend in two receipts that each look complete.
COST_TASK_ID = "audio_accuracy_diagnostic"

#: The run identity every call id is derived from, with the kind of run
#: appended. Stable rather than stamped with a clock, because the ledger is
#: appended to and ``continue_rounds`` numbers each new round off the rows
#: already in the file -- so two dispatches into one ledger cannot collide even
#: with the same run id, and a run id that changed every time would make the
#: rows of one diagnostic unrecognisable as belonging together.
COST_RUN_ID_PREFIX = "audio-accuracy-diagnostic"

#: What the stub answers when asked which model replied. Hoisted out of
#: ``_StubResponse`` because the ledger guard below compares against it: a
#: rehearsal's rows carry this string in ``resolved_model``, and that is what
#: keeps a free run's ledger from being appended to a paid one's.
STUB_MODEL = "stub-not-a-model"

#: The provider recorded against a rehearsal's rows. ``azure`` would be a
#: false statement about where the request went, in the one column a reader
#: summing a month's Azure spend would filter on.
STUB_PROVIDER = "stub"

#: Audio tokens the provider billed per second of clip in run 34008840627 --
#: exactly 10.00, across every call. Kept as a constant so that a speech run's
#: expected usage can be written down *before* the run, which is what makes a
#: silent delivery failure detectable: a corpus that never reached the model
#: produces a plausible-looking accuracy and a token count nowhere near this.
AUDIO_TOKENS_PER_SECOND = 10.0

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
    #: Set only when the pairing cannot be read off the ``claim_id``. The tone
    #: corpus names its claims ``<pair>_true`` / ``<pair>_false``, so stripping
    #: the last segment recovers the pair. A corpus that names them any other
    #: way -- the speech set pairs ``crate_seventeen`` with ``crate_seventy``
    #: under ``crate_number`` -- would have that rule silently invent one pair
    #: per claim, and the permutation test would then swap labels within pairs
    #: of size one, which is not a swap at all. Carrying the pairing explicitly
    #: is the difference between a null distribution and a straight line.
    explicit_pair_id: Optional[str] = None

    @property
    def pair_id(self) -> str:
        """The pairing this claim belongs to.

        Claims come in matched pairs on the same clip, and the permutation
        test swaps labels *within* a pair. That is what keeps a relabelling
        from producing a corpus that could not have existed -- two true
        criteria about one clip and none about another.
        """
        if self.explicit_pair_id is not None:
            return self.explicit_pair_id
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
# The other corpus: speech
# --------------------------------------------------------------------------
#
# Everything above is tones. That corpus answers "does the verdict depend on
# the audio at all", and it answered. It cannot answer the question the graded
# corpus turns on, because none of the 31 audio deliverables is a sine wave.
#
# The speech set is not built here. It is synthesised in CI by
# ``build_speech_verification_set.py`` -- eSpeak NG does not install on the dev
# host -- and arrives as an artifact plus a manifest that is committed. So the
# clips are *loaded* rather than rendered, and the loading is where the
# safety property lives: what is measured has to be what was pinned.


@dataclass(frozen=True)
class LoadedClip:
    """A clip that already exists as a file, described by its manifest entry."""

    clip_id: str
    path: Path
    sha256: str
    seconds: Optional[float]
    sample_rate_hz: Optional[int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "clip_id": self.clip_id,
            "file": self.path.name,
            "sha256": self.sha256,
            "seconds": self.seconds,
            "sample_rate_hz": self.sample_rate_hz,
        }


@dataclass(frozen=True)
class SpeechCorpus:
    """A pinned speech set, verified against the bytes on disk."""

    manifest_path: Path
    clips: tuple[LoadedClip, ...]
    claims: tuple[Claim, ...]
    provenance: dict[str, Any]
    encoder: dict[str, Any]
    limits: dict[str, Any]

    @property
    def paths(self) -> dict[str, Path]:
        return {clip.clip_id: clip.path for clip in self.clips}

    @property
    def digests(self) -> dict[str, str]:
        return {clip.clip_id: clip.sha256 for clip in self.clips}

    @property
    def durations(self) -> dict[str, float]:
        """Clip id to delivered length, for the delivery record.

        Clips whose manifest entry carries no length are left out rather than
        given a placeholder: an absent duration cannot disagree with what was
        sent, and a placeholder would disagree with everything.
        """
        return {
            clip.clip_id: float(clip.seconds)
            for clip in self.clips
            if clip.seconds is not None
        }

    @property
    def total_seconds(self) -> float:
        return round(sum(c.seconds or 0.0 for c in self.clips), 4)

    @property
    def seconds_per_pass(self) -> float:
        """Audio one pass over the corpus sends. Not ``total_seconds``.

        Every call carries the clip its criterion is about, and this set asks
        two criteria of each clip, so one pass sends each clip twice. The
        corpus is 31.235 s of audio and a pass sends 62.47 s of it.

        The difference is not academic: the expected token count is what the
        pre-registered +/-10% delivery band is measured against, and counting
        clips instead of calls halves it. A healthy run would then land 100%
        above the band and be reported as "the audio was delivered
        differently" -- the false alarm arriving in place of the check that
        was supposed to catch a real delivery change.
        """
        durations = self.durations
        return round(
            sum(
                durations[claim.clip_id]
                for claim in self.claims
                if claim.clip_id in durations
            ),
            4,
        )


def narrow_speech_corpus(
    corpus: SpeechCorpus, claim_ids: Sequence[str]
) -> SpeechCorpus:
    """The same verified corpus, cut down to ``claim_ids``.

    The digests were checked on load, for all ten clips, before anything was
    narrowed: this cuts the sample, not the verification. What it does drop
    is the clips no claim in the sample names, so the report's
    ``clip_sha256`` lists what was sent rather than what was available. A
    run that says it sent ten clips and sent five is a run whose audio
    cannot be identified afterwards, which is the failure
    :func:`load_speech_corpus` exists to prevent.
    """
    by_claim = {claim.claim_id: claim for claim in corpus.claims}
    missing = [c for c in claim_ids if c not in by_claim]
    if missing:
        raise KeyError(
            f"{corpus.manifest_path.name} has no claim named "
            f"{', '.join(missing)}; the document fixes a sample this "
            f"manifest cannot supply"
        )
    claims = tuple(by_claim[c] for c in claim_ids)
    wanted = {claim.clip_id for claim in claims}
    return dataclass_replace(
        corpus,
        claims=claims,
        clips=tuple(clip for clip in corpus.clips if clip.clip_id in wanted),
    )


def load_speech_corpus(manifest_path: Path, clip_dir: Path) -> SpeechCorpus:
    """Load the pinned speech set, refusing anything that is not what it says.

    The digest is checked against the file that will actually be sent, and a
    mismatch raises. This is the whole reason the manifest is committed: a
    measurement whose audio cannot be identified afterwards is not a
    measurement, and the failure mode being guarded against is mundane -- an
    artifact from a different run, a partial download, a clip regenerated by a
    newer eSpeak. Each of those produces a number that looks exactly like a
    real one.

    The ``sent`` file is used, not ``source``. eSpeak writes 22050 Hz and the
    grading path delivers 16 kHz; pinning the file the model never hears would
    be a check that passes while describing the wrong bytes.
    """
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    clips: list[LoadedClip] = []
    for entry in manifest["clips"]:
        sent = entry["sent"]
        path = clip_dir / sent["file"]
        if not path.is_file():
            raise FileNotFoundError(
                f"{entry['clip_id']}: {path} is missing. The clips are a CI "
                f"artifact and are not committed; download "
                f"'speech-verification-set' from the run that produced "
                f"{manifest_path.name} and point --speech-clips at it."
            )
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != sent["sha256"]:
            raise ValueError(
                f"{entry['clip_id']}: {path.name} is sha256 {actual[:16]}..., "
                f"but the manifest pins {sent['sha256'][:16]}.... Refusing to "
                f"measure audio that is not the audio that was pinned."
            )
        clips.append(
            LoadedClip(
                clip_id=entry["clip_id"],
                path=path,
                sha256=actual,
                seconds=sent.get("seconds"),
                sample_rate_hz=sent.get("sample_rate_hz"),
            )
        )

    known = {clip.clip_id for clip in clips}
    claims: list[Claim] = []
    for entry in manifest["claims"]:
        if entry["clip_id"] not in known:
            raise ValueError(
                f"{entry['claim_id']}: asks about clip "
                f"'{entry['clip_id']}', which the manifest does not pin"
            )
        claims.append(
            Claim(
                claim_id=entry["claim_id"],
                clip_id=entry["clip_id"],
                family=entry["family"],
                criterion=entry["criterion"],
                holds=bool(entry["holds"]),
                because=entry.get("because", ""),
                # Read, never derived: see Claim.explicit_pair_id.
                explicit_pair_id=entry["pair_id"],
            )
        )

    # Balance is a property of the corpus, and it is what makes 50% the
    # chance line. A set that had drifted off balance would still produce an
    # accuracy, against a baseline nobody had recomputed.
    true_claims = sum(1 for c in claims if c.holds)
    if true_claims * 2 != len(claims):
        raise ValueError(
            f"{true_claims} true of {len(claims)} claims: the set is not "
            f"balanced, so guessing does not score 50% and the binomial test "
            f"against 0.5 would be against the wrong number."
        )
    by_pair: dict[str, list[bool]] = {}
    for claim in claims:
        by_pair.setdefault(claim.pair_id, []).append(claim.holds)
    for pair_id, holds in sorted(by_pair.items()):
        if sorted(holds) != [False, True]:
            raise ValueError(
                f"pair '{pair_id}' is {holds}, not one true and one false. "
                f"The permutation test swaps labels within pairs and cannot "
                f"do that here."
            )

    return SpeechCorpus(
        manifest_path=manifest_path,
        clips=tuple(clips),
        claims=tuple(claims),
        provenance=manifest.get("provenance", {}),
        encoder=manifest.get("encoder", {}),
        limits=manifest.get("limits", {}),
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

    A verdict outside :data:`AUDIO_VERDICT_VOCABULARY` raises rather than
    scoring. The vocabulary is core's, not a second copy: ``core.perception.
    audio`` already rejects an out-of-vocabulary reply as
    ``verdict_not_in_vocabulary`` before it can reach here, so this is the
    second half of one check and not a new rule. It is unreachable today for
    exactly that reason -- and the branch it guards was the silent one. The
    ``fail`` arm below is a plain ``else``: ``verdict == "pass"`` being false
    made ``true``, ``false``, ``refuse`` and ``analyze_audio`` -- the four
    out-of-vocabulary strings run ``34008840627`` actually produced -- score as
    confident ``fail`` verdicts, correct on every false claim. Raising is the
    same answer ``Tally.add`` gives an unknown kind, and it fails closed: no
    number gets published from a reply nobody validated.
    """
    if verdict not in AUDIO_VERDICT_VOCABULARY:
        # Named through core's own bounded renderer, because this string came
        # from a model. ``_offending_token`` admits ``true`` and ``refuse``
        # and collapses anything that could carry a payload.
        raise ValueError(
            f"verdict outside the response contract's vocabulary: "
            f"{_offending_token(verdict)}"
        )
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


def _majority_by_claim(
    calls: Sequence[dict[str, Any]], claims: Sequence[Claim]
) -> dict[str, dict[str, Any]]:
    """One collapsed answer per claim: the two steps :func:`summarise` uses.

    ``majority_verdict`` over the repeats, then ``classify``. Not a second
    scoring rule -- the same two functions in the same order -- because a
    claim-level accuracy computed any other way here would silently disagree
    with the per-arm table printed beside it.

    ``majority`` and ``outcome`` are ``None`` together when the repeats
    produced no majority. That is a claim this arm did not settle, not a claim
    it got wrong, and the counts below keep the two apart.
    """
    verdicts_by_claim: dict[str, list[str]] = {}
    for call in calls:
        verdicts_by_claim.setdefault(call["claim_id"], []).append(call["verdict"])
    collapsed: dict[str, dict[str, Any]] = {}
    for claim in claims:
        verdicts = verdicts_by_claim.get(claim.claim_id)
        if not verdicts:
            continue
        majority = majority_verdict(verdicts)
        collapsed[claim.claim_id] = {
            "holds": claim.holds,
            "majority": majority,
            "outcome": classify(claim, majority) if majority is not None else None,
            # Which of the two ways a claim can fail to settle. An arm that
            # never answered and an arm that answered three different things
            # are both "no majority" and are not the same failure.
            "answered_calls": sum(1 for v in verdicts if v != "judge_error"),
        }
    return collapsed


def compare_arms(
    calls: Sequence[dict[str, Any]],
    *,
    claims: Sequence[Claim],
    control: str = "production",
    treatment: str = "observation",
) -> Optional[dict[str, Any]]:
    """The paired difference between two prompts, or ``None`` if one is absent.

    Two pairings, reported side by side and labelled, because they answer
    different questions and the wrong one read as the headline overstates the
    evidence:

    ``pairs`` / ``mcnemar_exact_p`` pair on ``(claim, repeat)`` -- the same
    criterion, the same clip, the same repeat index, put twice in immediate
    succession under two prompts. Twenty criteria at three repeats make sixty
    of these, and they are *not* sixty independent items: the three repeats of
    one criterion are the same question asked again, so this p is anti-
    conservative as a test of the prompt and is kept because it is the finest
    grain at which a delivery difference shows up.

    ``per_claim_majority`` collapses each arm's repeats to one verdict per
    claim first, giving one pair per criterion. That is the unit a
    pre-registration can name as primary without counting a repeat as a new
    question.

    ``claims`` is required rather than defaulted. The default that would be
    convenient here -- the tone corpus -- matches no claim id on a speech run,
    and the whole claim-level block would come back empty while the per-call
    block looked healthy.

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
        "unit": "call",
        "reading": (
            "Exact two-sided McNemar on the discordant calls. A large p means "
            "this corpus did not detect a difference between the prompts; it "
            "does NOT mean the prompts are equivalent. With "
            f"{b + c} discordant calls out of {len(paired)}, only a large "
            "effect could have shown up at all, and the interval on the "
            "difference is correspondingly wide."
        ),
        "per_claim_majority": _compare_majorities(
            calls, claims, control=control, treatment=treatment
        ),
    }


def _compare_majorities(
    calls: Sequence[dict[str, Any]],
    claims: Sequence[Claim],
    *,
    control: str,
    treatment: str,
) -> Optional[dict[str, Any]]:
    """The same comparison with each arm's repeats collapsed to one answer.

    One pair per criterion instead of one per repeat. ``None`` when no
    criterion was settled by both arms, which is the honest reading of "there
    was nothing to pair" rather than a table of zeroes.
    """
    ctl = _majority_by_claim(
        [c for c in calls if _arm_of(c) == control], claims
    )
    trt = _majority_by_claim(
        [c for c in calls if _arm_of(c) == treatment], claims
    )
    shared = sorted(set(ctl) & set(trt))
    if not shared:
        return None

    b = c = both = neither = 0
    for claim_id in shared:
        ctl_ok = ctl[claim_id]["outcome"] == OUTCOME_CORRECT
        trt_ok = trt[claim_id]["outcome"] == OUTCOME_CORRECT
        if ctl_ok and trt_ok:
            both += 1
        elif ctl_ok:
            b += 1
        elif trt_ok:
            c += 1
        else:
            neither += 1

    def _side(collapsed: dict[str, dict[str, Any]]) -> dict[str, Any]:
        rows = [collapsed[claim_id] for claim_id in shared]
        settled = [r for r in rows if r["majority"] is not None]
        correct = sum(1 for r in rows if r["outcome"] == OUTCOME_CORRECT)
        return {
            "claims": len(rows),
            "settled": len(settled),
            "correct": correct,
            "accuracy_of_settled": _rate(correct, len(settled)),
            "settled_rate": _rate(len(settled), len(rows)),
            # A tie and a silence are both "no majority" and mean opposite
            # things about the model. Split, never summed into one number.
            "unsettled": {
                "no_answer_at_all": sum(
                    1
                    for r in rows
                    if r["majority"] is None and r["answered_calls"] == 0
                ),
                "answered_without_a_majority": sum(
                    1
                    for r in rows
                    if r["majority"] is None and r["answered_calls"] > 0
                ),
            },
            "discrimination_j": discrimination(
                [(r["holds"], r["majority"]) for r in settled]
            ),
        }

    # What a machine that says "fail" to everything scores on these same
    # criteria. Printed beside the accuracies because on a corpus that is half
    # false, refusing to ever agree is worth 50% and no discrimination at all,
    # and an accuracy near that number is not evidence of hearing anything.
    always_fail = [(ctl[claim_id]["holds"], "fail") for claim_id in shared]
    return {
        "unit": "claim",
        "pairs": len(shared),
        "control": control,
        "treatment": treatment,
        control: _side(ctl),
        treatment: _side(trt),
        "discordant": {
            "control_only_correct": b,
            "treatment_only_correct": c,
            "both_correct": both,
            "neither_correct": neither,
        },
        "mcnemar_exact_p": mcnemar_exact(b, c),
        "constant_fail_baseline": {
            "correct": sum(1 for holds, _ in always_fail if not holds),
            "of": len(always_fail),
            "accuracy": _rate(
                sum(1 for holds, _ in always_fail if not holds), len(always_fail)
            ),
            "discrimination_j": discrimination(always_fail),
        },
        "reading": (
            "Exact two-sided McNemar with the repeats collapsed to one verdict "
            f"per criterion, so {len(shared)} pairs and not "
            f"{len(shared)} x repeats. A large p means this corpus did not "
            "detect a difference between the prompts; it does NOT mean the "
            "prompts are equivalent. Compare each accuracy against "
            "constant_fail_baseline before reading it as skill."
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


#: The row a pre-registration writes its grader fingerprint into. Read rather
#: than restated here: the operator reads that table before dispatching, and a
#: constant in this file would be a second place for the value to live and a
#: second place for it to go stale.
_GRADER_PIN_ROW = re.compile(
    r"^\|\s*채점기 지문\s*\|\s*`([0-9a-f]{64})`\s*\|", re.MULTILINE
)


def grader_source_hash(config_path: Path = PINNED_CONFIG) -> str:
    """What this checkout's grader fingerprints as, computed not quoted.

    ``step8_grade``'s own function, on the config this measurement borrows.
    It covers the grading entry point, every ``core/**`` module, the grade
    schema, the requirements closure, the prompt template and the config
    file, so any of them moving changes the answer.
    """
    from step8_grade import compute_grader_source_hash

    return compute_grader_source_hash(config_path, _read_yaml(config_path))


def grader_pin_stated_in(doc_path: Path) -> str:
    """The fingerprint a pre-registration pins, taken out of its own table."""
    found = set(_GRADER_PIN_ROW.findall(doc_path.read_text(encoding="utf-8")))
    if not found:
        raise ValueError(
            f"{doc_path} states no grader fingerprint, so there is nothing to "
            f"hold this run to. A pre-registration that does not name a "
            f"grader is not pinning one."
        )
    if len(found) > 1:
        raise ValueError(
            f"{doc_path} states {len(found)} different grader fingerprints; "
            f"which one this run is supposed to be is not decidable"
        )
    return found.pop()


#: The row a pre-registration writes the price table's fingerprint into.
#:
#: The grader fingerprint does not cover it. ``compute_grader_source_hash``
#: digests ``core/**``, the grading entry point, the schema, the requirements
#: closure, the prompt template and the config -- the things that decide what
#: the model is asked. The price table decides what the answer is said to have
#: cost, and it can be edited without moving the grader pin by one bit.
#:
#: For a run whose whole question is "was the spend recorded", an unpinned
#: price table is the gap: add a rate for ``gpt-audio-1.5`` between the
#: pre-registration and the dispatch and the run reports a number, complete
#: and unremarkable, that no reviewer agreed to. Pinned here, that edit stops
#: the run instead.
_PRICE_TABLE_PIN_ROW = re.compile(
    r"^\|\s*가격표 지문\s*\|\s*`([0-9a-f]{64})`\s*\|", re.MULTILINE
)


def price_table_pin_stated_in(doc_path: Path) -> str:
    """The price-table fingerprint a pre-registration pins."""
    found = set(_PRICE_TABLE_PIN_ROW.findall(doc_path.read_text(encoding="utf-8")))
    if not found:
        raise ValueError(
            f"{doc_path} states no price table fingerprint. A run that asks "
            f"whether cost was recorded has to say which rates it was going "
            f"to be recorded against; without that row, a table edited "
            f"between registration and dispatch is invisible."
        )
    if len(found) > 1:
        raise ValueError(
            f"{doc_path} states {len(found)} different price table "
            f"fingerprints; which one this run is supposed to use is not "
            f"decidable"
        )
    return found.pop()


#: The row a pre-registration writes the speech manifest's fingerprint into.
#:
#: :func:`load_speech_corpus` already checks every clip against the digest
#: beside it in the manifest -- but the manifest is the thing making the
#: claim, so on its own that check is a file attesting to itself. Any
#: self-consistent manifest passes it, including one written this morning
#: naming clips rendered by a newer eSpeak.
#:
#: This row is what makes it identity rather than internal consistency: the
#: document names the manifest it agreed to, the run hashes the file it was
#: handed, and a substitution stops the run instead of producing a number
#: that looks exactly like the pinned corpus's.
_MANIFEST_PIN_ROW = re.compile(
    r"^\|\s*매니페스트 지문\s*\|\s*`([0-9a-f]{64})`\s*\|", re.MULTILINE
)


def manifest_pin_stated_in(doc_path: Path) -> str:
    """The speech-manifest fingerprint a pre-registration pins."""
    found = set(_MANIFEST_PIN_ROW.findall(doc_path.read_text(encoding="utf-8")))
    if not found:
        raise ValueError(
            f"{doc_path} states no speech manifest fingerprint. Checking the "
            f"clips against the manifest that ships with them only shows the "
            f"manifest agrees with itself; this row is what says the manifest "
            f"is the one this document agreed to."
        )
    if len(found) > 1:
        raise ValueError(
            f"{doc_path} states {len(found)} different speech manifest "
            f"fingerprints; which corpus this run is supposed to send is not "
            f"decidable"
        )
    return found.pop()


#: The row a two-arm pre-registration writes its candidate header's digest
#: into.
#:
#: Optional, and read as ``None`` when absent, because 333, 337 and 338 were
#: dispatched before this row existed and re-pinning a finished document to
#: satisfy a check written later would be editing history to pass a test.
#: A document that does carry the row is held to it.
#:
#: The gap it closes: 337 stated ``SPEECH_OBSERVATION_HEADER_V2, sha256
#: 93239fe7...`` in its own table and nothing compared that string to the
#: string the run would send. Which header a kind sends is decided by
#: :data:`SPEECH_TWO_ARM_REGISTRATIONS`, one table away, and the two could
#: have disagreed without anything saying so.
_CANDIDATE_PIN_ROW = re.compile(
    r"^\|\s*후보 머리말 지문\s*\|\s*`([0-9a-f]{64})`\s*\|", re.MULTILINE
)


def candidate_pin_stated_in(doc_path: Path) -> Optional[str]:
    """The candidate header's digest a pre-registration pins, if it pins one."""
    found = set(_CANDIDATE_PIN_ROW.findall(doc_path.read_text(encoding="utf-8")))
    if not found:
        return None
    if len(found) > 1:
        raise ValueError(
            f"{doc_path} states {len(found)} different candidate header "
            f"fingerprints; which prompt this run is supposed to send is not "
            f"decidable"
        )
    return found.pop()

#: Same shape and same reason as :data:`_GRADER_PIN_ROW`: a visible table row
#: the operator reads before dispatching, parsed rather than restated. A file
#: path on a command line says nothing about what the file agreed to; this
#: makes the document itself the thing that opts in.
_DIAGNOSTIC_KIND_ROW = re.compile(
    r"^\|\s*진단 종류\s*\|\s*`([a-z0-9-]{1,40})`\s*\|", re.MULTILINE
)

#: What a speech prompt-A/B pre-registration has to call itself.
SPEECH_PROMPT_AB_KIND = "speech-prompt-ab"

#: The small format pre-trial that has to clear before the full comparison is
#: bought again. A separate kind and not a flag on the existing one: 333's
#: document registered 120 calls under the V1 header and is finished, and a
#: run that reuses its name would be filed against a plan it does not follow.
SPEECH_FORMAT_PILOT_KIND = "speech-format-pilot"

#: The full comparison under the format-safe header. Same shape as
#: :data:`SPEECH_PROMPT_AB_KIND` -- 20 claims, 3 repeats, 2 arms, 120 calls --
#: and a different document, because the header it sends is different.
SPEECH_PROMPT_AB_V2_KIND = "speech-prompt-ab-v2"

#: 344's re-run of the format pre-trial under a third header.
#:
#: A third kind rather than a second dispatch of ``speech-format-pilot``.
#: 337's document pins a different candidate, a different ceiling and a
#: different set of pass criteria, and it is finished: it registered
#: :data:`SPEECH_OBSERVATION_HEADER_V2`, bought ten calls, and 339 recorded
#: the result. Re-using its name would file a run against a plan it does not
#: follow and would put a second, different answer under a document that
#: already has one.
#:
#: The five claims and their order are 337's, unchanged and deliberately so.
#: The one thing this run varies is the header; holding the sample fixed is
#: what keeps "the candidate changed" from being confounded with "the
#: questions changed", and re-picking items after seeing 339's results is the
#: exact move a pre-registration exists to prevent.
SPEECH_FORMAT_PILOT_V3_KIND = "speech-format-pilot-v3"

#: The metering trial 341 asks for: does a paid audio call reach the ledger.
#:
#: A separate kind, and deliberately not a flag on the accuracy diagnostics.
#: What it measures is the bookkeeping path, not the sub-judge -- a run in
#: which every verdict is unreadable passes it, and a run whose verdicts are
#: perfect fails it if the rows are missing. Filing that question under
#: ``speech-format-pilot`` would put an answer about the ledger in a document
#: that registered an answer about prompts.
#:
#: It is not in :data:`SPEECH_TWO_ARM_REGISTRATIONS`. One arm, production,
#: because there is nothing here to compare: two headers would double the
#: spend to answer the same question twice.
#:
#: 337 and 338 are untouched by this. Their kinds, ceilings, repeats and
#: failure criteria are exactly what they were.
AUDIO_COST_METERING_KIND = "audio-cost-metering"

#: How many criteria that kind is registered to put to the model.
#:
#: Two, and checked rather than assumed. The pair is what makes a ledger
#: worth reading: one row proves a row can be written, and two prove the
#: second was not the first counted twice -- which is the duplicate defect
#: ``verify_audio_metering_run.py`` condition 1 exists to catch and could not
#: catch in a one-row run.
AUDIO_COST_METERING_CLAIMS = 2

#: The wall clock this kind stops at, in seconds.
#:
#: Ten minutes against the speech corpus's twenty. Two calls do not need
#: twenty minutes, and the shorter clock is what makes a hung request end the
#: run instead of holding the operator there: the thing being tested is the
#: record a finished run leaves, and there is nothing to read while it hangs.
AUDIO_COST_METERING_WALL_CLOCK_SECONDS = 10 * 60

#: The failure budget this kind runs with. **One, and one is the "no retries"
#: setting** -- zero is not.
#:
#: :data:`~core.perception.audio.AUDIO_FAILURE_BUDGET` is compared with
#: ``>=`` before a request goes out, so ``failure_budget=0`` refuses the
#: first call and every call after it: the run would send nothing and report
#: two refusals. One lets the first request go and blocks the task the moment
#: an unbilled rejection comes back, which is the behaviour "재시도 0" is
#: asking for -- one attempt per criterion, no second bite.
AUDIO_COST_METERING_FAILURE_BUDGET = 1

#: SDK-level retries for this kind. Zero, and this is the one that matters.
#:
#: Everywhere else in this script ``max_retries`` is left unset, so the
#: openai default of two applies and a 408/409/429/5xx is retried *inside* a
#: single ``chat.completions.create``. The meter wraps ``create``, so those
#: retries share one ledger row: up to three HTTP requests, one row, and a
#: run that under-reports what it sent by two thirds while every count in it
#: agrees with every other.
#:
#: That is survivable for an accuracy diagnostic and fatal for this one,
#: whose entire claim is that the rows match the requests. Off, so one row is
#: one request. The cost is that a single 429 loses a criterion instead of
#: retrying it, which is the right trade for a two-call run.
AUDIO_COST_METERING_SDK_RETRIES = 0

#: The row a pre-registration writes to fix *which* claims a narrowed run
#: puts to the model. Only the pilot uses it; the full comparisons take the
#: whole manifest and must not carry this row at all.
#:
#: Parsed out of the document for the same reason the fingerprint and the
#: kind are: a subset chosen on the command line is a subset nobody agreed
#: to, and after the fact there is no way to tell it from one that was.
_PILOT_CLAIMS_ROW = re.compile(r"^\|\s*시험 문항\s*\|([^|]*)\|", re.MULTILINE)

#: Claim ids inside that row, one per pair of backticks.
_BACKTICKED_CLAIM_ID = re.compile(r"`([a-z0-9_]{1,40})`")


def diagnostic_kind_stated_in(doc_path: Path) -> str:
    """Which diagnostic a pre-registration declares itself to be."""
    found = set(_DIAGNOSTIC_KIND_ROW.findall(doc_path.read_text(encoding="utf-8")))
    if not found:
        raise ValueError(
            f"{doc_path} declares no diagnostic kind, so it has not agreed to "
            f"anything. Pointing a run at a document does not make that "
            f"document its pre-registration."
        )
    if len(found) > 1:
        raise ValueError(
            f"{doc_path} declares {len(found)} different diagnostic kinds; "
            f"which run it registers is not decidable"
        )
    return found.pop()


def pilot_claims_stated_in(doc_path: Path) -> tuple[str, ...]:
    """The claim ids a narrowed pre-registration fixes, in document order.

    Order is kept rather than sorted: the document lists them in the order it
    means them to run, and re-sorting here would make the run's order a
    property of this function instead of of the plan.
    """
    text = doc_path.read_text(encoding="utf-8")
    rows = _PILOT_CLAIMS_ROW.findall(text)
    if not rows:
        raise ValueError(
            f"{doc_path} fixes no claims, so there is no narrowed sample to "
            f"run. A pre-registration for a subset has to say which subset."
        )
    if len(rows) > 1:
        raise ValueError(
            f"{doc_path} states {len(rows)} different claim rows; which one "
            f"the run is supposed to use is not decidable"
        )
    claim_ids = tuple(_BACKTICKED_CLAIM_ID.findall(rows[0]))
    if not claim_ids:
        raise ValueError(
            f"{doc_path} has a claim row with no backticked claim id in it"
        )
    seen: set[str] = set()
    for claim_id in claim_ids:
        if claim_id in seen:
            raise ValueError(
                f"{doc_path} lists {claim_id} twice; a repeated claim is a "
                f"repeat count written in the wrong place"
            )
        seen.add(claim_id)
    return claim_ids


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
        self.model = STUB_MODEL


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

#: The observation arm's header for the *speech* corpus.
#:
#: A separate constant rather than a reuse, because
#: :data:`OBSERVATION_HEADER` asks for "pitches, intervals and harmonic
#: content" and says "if it names a count, a tempo, a key or an interval".
#: None of that exists in a spoken sentence. Sending it with speech would put
#: the alternative arm at a disadvantage this corpus never meant to test, and
#: the resulting difference would be "we asked the wrong question of one arm",
#: not "observation-first helps or does not".
#:
#: Everything else is deliberately word-for-word the same as the tone arm's:
#: the opening framing, the "may be true or may be false" clause, the offer of
#: ``judge_error``, the evidence-before-verdict instruction, the "Statement"
#: label, and the verbatim :data:`AUDIO_RESPONSE_CONTRACT`. Only the
#: observation list is rewritten, so the two corpora are testing the same
#: intervention.
#:
#: It leaks no answer: it names no token that separates either half of a
#: pinned pair, and ``test_the_speech_observation_header_leaks_no_answer``
#: derives that token set from the manifest rather than from a list here.
#:
#: **A limit, stated where the string lives.** Asking for a verbatim
#: transcript is itself the kind of attention this corpus rewards. If this arm
#: wins, one available reading is "a prompt that names the observable helped",
#: which is not the same claim as "observation-first prompts hear better". The
#: pre-registration carries this; a reader of the code should not have to go
#: find it.
SPEECH_OBSERVATION_HEADER = (
    "You are an audio analyst. A short audio clip has been supplied to you as "
    "audio input. Work only from that audio. Nothing you have been told about "
    "the clip is a substitute for listening to it.\n\n"
    "FIRST, before treating the statement below as anything but words, listen "
    "to the clip and write down what it actually contains: whether any speech "
    "is present at all; the words you hear, in the sequence you hear them, as "
    "close to verbatim as you can manage; and, where a word is easy to "
    "mishear, what you believe was actually said rather than what would make "
    "the most sense.\n\n"
    "THEN judge the statement against that transcript. The statement may be "
    "true or it may be false. Do not assume it is true, and do not let its "
    "wording tell you what you heard: whatever it names is the claim under "
    "test, not a fact about the clip. If the audio does not let you decide, "
    "return verdict \"judge_error\" rather than guessing.\n\n"
    "In \"evidence\", quote the words you heard before you state whether the "
    "statement is supported.\n\n"
) + AUDIO_RESPONSE_CONTRACT

#: The one sentence that separates :data:`SPEECH_OBSERVATION_HEADER_V2` from
#: :data:`SPEECH_OBSERVATION_HEADER`.
#:
#: 334 bought the V1 header and got 9 readable replies out of 60. 335 bought
#: three of the failures and found no JSON at all in them: zero braces, the
#: parser stopping on the first character, ``finish_reason: stop``. The model
#: had not broken the envelope, it had not written one.
#:
#: Reading the two strings side by side says why. V1's most emphatic
#: instruction -- "FIRST ... write down what it actually contains" -- is an
#: order to produce text with **no destination named**, and the response
#: contract that follows says "no prose before or after". A model that obeys
#: the first instruction literally has nowhere to put the result except the
#: reply, and then the reply is not the object.
#:
#: So the sentence names a destination. It does not weaken the contract, it
#: does not soften the transcript request, and it changes nothing else: it
#: says where the thing V1 already asked for is supposed to go.
#:
#: ``"reasoning"`` is chosen because it is one of the five keys the contract
#: already requires and one of the two the parser does not type-check, so
#: routing a transcript there needs no change to
#: ``core.perception.audio``'s parsing and no ``response_format`` -- which
#: this deployment rejects with a 400 either way (335 §11).
SPEECH_OBSERVATION_DESTINATION_SENTENCE = (
    "Write that transcript into the \"reasoning\" field of the single JSON "
    "object described below, and write it nowhere else: that object is the "
    "whole of your reply."
)

#: The format-safe candidate. Byte-for-byte :data:`SPEECH_OBSERVATION_HEADER`
#: plus :data:`SPEECH_OBSERVATION_DESTINATION_SENTENCE`, inserted at the end
#: of the FIRST paragraph.
#:
#: Written out in full rather than derived with ``.replace`` so that a
#: reviewer reads the prompt that ships, not a recipe for it.
#: ``test_the_v2_header_is_v1_plus_exactly_one_sentence`` reconstructs V1 by
#: deleting the sentence and compares byte-for-byte, so "one sentence" is
#: checked rather than claimed.
#:
#: **What it cannot do.** Naming a destination is a format fix. If the arm
#: still loses, this string is not evidence about whether observation-first
#: attention helps; and if it wins on format, that is a fact about envelopes
#: and not about hearing. The two rates are reported separately for that
#: reason.
SPEECH_OBSERVATION_HEADER_V2 = (
    "You are an audio analyst. A short audio clip has been supplied to you as "
    "audio input. Work only from that audio. Nothing you have been told about "
    "the clip is a substitute for listening to it.\n\n"
    "FIRST, before treating the statement below as anything but words, listen "
    "to the clip and write down what it actually contains: whether any speech "
    "is present at all; the words you hear, in the sequence you hear them, as "
    "close to verbatim as you can manage; and, where a word is easy to "
    "mishear, what you believe was actually said rather than what would make "
    "the most sense. "
    "Write that transcript into the \"reasoning\" field of the single JSON "
    "object described below, and write it nowhere else: that object is the "
    "whole of your reply.\n\n"
    "THEN judge the statement against that transcript. The statement may be "
    "true or it may be false. Do not assume it is true, and do not let its "
    "wording tell you what you heard: whatever it names is the claim under "
    "test, not a fact about the clip. If the audio does not let you decide, "
    "return verdict \"judge_error\" rather than guessing.\n\n"
    "In \"evidence\", quote the words you heard before you state whether the "
    "statement is supported.\n\n"
) + AUDIO_RESPONSE_CONTRACT

#: The two words that separate :data:`SPEECH_OBSERVATION_HEADER_V3` from
#: :data:`SPEECH_OBSERVATION_HEADER_V2`, and what they are for.
#:
#: Read V2's docstring above and then read what it shipped. The diagnosis it
#: states is that V1's first imperative "is an order to produce text with no
#: destination named". The fix it shipped **names a destination and leaves the
#: order standing**: V2's first paragraph now contains two output orders, an
#: unaddressed "write down what it actually contains" followed by an addressed
#: "Write that transcript into the \"reasoning\" field". A model that executes
#: them in the order given writes the transcript first, and 335 saw exactly
#: that shape -- one sentence of prose, no braces, ``finish_reason: stop``.
#:
#: So V3 does to the first order what V2 did not: it takes the emission out.
#: "write down" becomes "work out", which asks for the same determination and
#: does not ask for a second piece of writing. Everything the observation
#: asks the model to attend to -- speech present at all, the words in
#: sequence, verbatim where it can manage, the mishearing caveat -- is
#: untouched, and so is the destination sentence, which is now the paragraph's
#: only output order.
#:
#: **This candidate is the last one this theory gets.** V1 and V2 both failed;
#: if a header with no unaddressed emission order fails too, then "the model
#: is obeying an order to write prose" is not what is happening, and the next
#: step is whatever 344's recorded response facts say instead -- not a fourth
#: rewording of the same paragraph.
SPEECH_OBSERVATION_EMISSION_VERB = ("write down", "work out")

#: The candidate 344 registers: V2 with its unaddressed emission order removed.
#:
#: Written out in full rather than derived with ``.replace`` for the same
#: reason V2 is -- a reviewer should read the prompt that ships, not a recipe
#: for it. ``test_the_v3_header_is_v2_with_the_emission_order_removed``
#: reconstructs V2 by putting the two words back and compares byte-for-byte,
#: so "one substitution, nothing else" is checked rather than claimed.
#:
#: **What it cannot do.** This is a format candidate. If it holds the envelope
#: that is a fact about envelopes, not about hearing; five items cannot say
#: anything about accuracy and 344 does not ask them to. If it loses, it is
#: not evidence about whether observation-first attention helps either.
SPEECH_OBSERVATION_HEADER_V3 = (
    "You are an audio analyst. A short audio clip has been supplied to you as "
    "audio input. Work only from that audio. Nothing you have been told about "
    "the clip is a substitute for listening to it.\n\n"
    "FIRST, before treating the statement below as anything but words, listen "
    "to the clip and work out what it actually contains: whether any speech "
    "is present at all; the words you hear, in the sequence you hear them, as "
    "close to verbatim as you can manage; and, where a word is easy to "
    "mishear, what you believe was actually said rather than what would make "
    "the most sense. "
    "Write that transcript into the \"reasoning\" field of the single JSON "
    "object described below, and write it nowhere else: that object is the "
    "whole of your reply.\n\n"
    "THEN judge the statement against that transcript. The statement may be "
    "true or it may be false. Do not assume it is true, and do not let its "
    "wording tell you what you heard: whatever it names is the claim under "
    "test, not a fact about the clip. If the audio does not let you decide, "
    "return verdict \"judge_error\" rather than guessing.\n\n"
    "In \"evidence\", quote the words you heard before you state whether the "
    "statement is supported.\n\n"
) + AUDIO_RESPONSE_CONTRACT

#: Arm identifiers. ``production`` forwards the request untouched, so the
#: control arm is the real grading prompt and not a re-implementation of it.
PROMPT_ARMS = ("production", "observation")

#: Which two-arm pre-registrations exist, and what each one sends opposite
#: production: ``kind -> (constant name, the string itself)``.
#:
#: The name travels with the string so the report can say *which* header a
#: ``prompt_sha256`` is, rather than leaving a reader to hash candidates
#: until one matches.
#:
#: Adding a row here is the only way to open the second arm, and a document
#: still has to name its own kind to reach it. ``--prompt-arm`` reaches none
#: of them; that door stayed shut when 333 opened this one and it stays shut
#: now.
SPEECH_TWO_ARM_REGISTRATIONS: dict[str, tuple[str, str]] = {
    SPEECH_PROMPT_AB_KIND: (
        "SPEECH_OBSERVATION_HEADER",
        SPEECH_OBSERVATION_HEADER,
    ),
    SPEECH_FORMAT_PILOT_KIND: (
        "SPEECH_OBSERVATION_HEADER_V2",
        SPEECH_OBSERVATION_HEADER_V2,
    ),
    SPEECH_PROMPT_AB_V2_KIND: (
        "SPEECH_OBSERVATION_HEADER_V2",
        SPEECH_OBSERVATION_HEADER_V2,
    ),
    SPEECH_FORMAT_PILOT_V3_KIND: (
        "SPEECH_OBSERVATION_HEADER_V3",
        SPEECH_OBSERVATION_HEADER_V3,
    ),
}

#: Which kinds narrow the corpus to a document-fixed claim list, and how many
#: repeats each one is registered for.
#:
#: The repeat count is checked, never applied: a dispatch that asks for a
#: different number is refused rather than quietly corrected, so the number
#: in the run log is the number a person typed and the number the document
#: pinned at the same time.
SPEECH_NARROWED_KINDS: dict[str, int] = {
    SPEECH_FORMAT_PILOT_KIND: 1,
    SPEECH_FORMAT_PILOT_V3_KIND: 1,
    AUDIO_COST_METERING_KIND: 1,
}

#: The hard ceiling on model requests, per kind.
#:
#: What it counts, exactly: invocations of ``chat.completions.create`` made
#: through this wrapper. ``AudioPerception.judge`` makes exactly one of those
#: per call and reports ``api_call_count=1`` on every branch it can return
#: from, so for this script one call is one counted request.
#:
#: What it does not count, and cannot: the SDK's own retries. ``max_retries``
#: is left unset all the way down (``create_typed_azure_client`` ->
#: ``AzureAIClientFactory.create`` only forwards it when it is not ``None``),
#: so the openai default of two applies, and a 408/409/429/5xx or a connection
#: error is retried *inside* a single ``create`` invocation. Up to three HTTP
#: requests can therefore sit under one tick of this counter. Those retries
#: mostly follow answers that were never billed -- but a request that timed
#: out may have run and been billed, and this ceiling would not have seen it.
#:
#: Counted before the request leaves, and a request that raises still counts,
#: because a request that vanished may well have run.
#:
#: This is a scope bound, not a budget: the number of requests the plan needs
#: plus headroom. Reaching it means the plan was wrong, and the run stops
#: rather than growing to fit.
SPEECH_REQUEST_CAPS: dict[str, int] = {
    SPEECH_FORMAT_PILOT_KIND: 12,
    #: 344: five claims x one repeat x two arms = ten calls, against a ceiling
    #: of **ten**. No headroom at all, and that is the point: the approval
    #: this run has is for at most ten calls, so a ceiling of twelve would be
    #: a ceiling nobody agreed to. 337 could afford two spare because its SDK
    #: retries were the openai default and a stray retry was invisible to the
    #: counter anyway; here :data:`SPEECH_LEDGERED_KINDS` pins them to zero,
    #: so one create is one HTTP request and the plan and the ceiling can be
    #: the same number honestly.
    SPEECH_FORMAT_PILOT_V3_KIND: 10,
    #: 338: the whole manifest, 20 claims x 3 repeats x 2 arms = 120, which is
    #: the size 333 registered and 334 bought. The instruction for this
    #: comparison is that it does not grow past that, so the headroom here is
    #: six -- enough that a run is not lost to a couple of stray requests,
    #: nowhere near enough to fit a fourth repeat (which would need 160).
    SPEECH_PROMPT_AB_V2_KIND: 126,
    #: 341: two criteria, one repeat, one arm -- two calls planned against a
    #: ceiling of six. Threefold headroom on a two-call run is not generosity,
    #: it is the number that makes the ceiling readable: if six requests go
    #: out for two criteria then something retried, and the run stops and says
    #: so rather than quietly buying a fourth and fifth attempt. With
    #: :data:`AUDIO_COST_METERING_SDK_RETRIES` at zero the only way past two
    #: is a defect, so this ceiling is expected never to fire.
    AUDIO_COST_METERING_KIND: 6,
}

#: Accuracy kinds that run under the metering trial's request discipline.
#:
#: Three things travel together here, and they are one decision rather than
#: three: the openai SDK's ``max_retries`` pinned to
#: :data:`AUDIO_COST_METERING_SDK_RETRIES`, a failure budget of one, and a
#: cost ledger the run refuses to start without.
#:
#: Why an accuracy run wants them. 337 bought ten calls and reported ten, but
#: it ran on the SDK default of two retries, so "ten calls" bounded
#: ``create`` invocations and not HTTP requests -- a 429 inside any of them
#: would have sent a second and a third under one tick of the counter, and
#: 340 later found that none of the ten reached the shared ledger at all. A
#: run whose approval is written as a request count has to be able to say
#: what the request count was, and 337 could not.
#:
#: :data:`AUDIO_COST_METERING_KIND` is not listed. It does not need to be --
#: ``--metering-run`` already sets all three for its own reasons, and adding
#: it here would give one behaviour two switches.
SPEECH_LEDGERED_KINDS: frozenset[str] = frozenset({
    SPEECH_FORMAT_PILOT_V3_KIND,
})


class RequestCapReached(BaseException):
    """The pre-registered request ceiling was hit; nothing further goes out.

    Deliberately a ``BaseException``. ``AudioPerception.judge`` turns any
    ``Exception`` into a ``judge_error`` and carries on to the next claim,
    which would turn a ceiling into a quiet stream of failures that each
    still cost a request. This one has to reach ``main``.
    """


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


def apply_arm(
    kwargs: dict[str, Any],
    arm: str,
    *,
    observation_header: str = OBSERVATION_HEADER,
) -> dict[str, Any]:
    """Rewrite the outgoing request for ``arm``, touching only the text part.

    Everything that is not the prompt -- model, modalities, and above all the
    ``input_audio`` part -- is passed through by reference. The two arms
    therefore send byte-identical audio by construction rather than by
    assertion, and a test still asserts it.

    ``observation_header`` is a parameter and not a lookup because the caller
    is the only thing that knows which corpus is being measured, and a table
    in here would be a second place for that decision to live.
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
                    "text": f"{observation_header}\n\nStatement:\n{criterion}",
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

    def __init__(
        self,
        inner: Any,
        *,
        arm: str = "production",
        observation_header: str = OBSERVATION_HEADER,
        request_cap: Optional[int] = None,
    ) -> None:
        self._inner = inner
        self.arm = arm
        self.observation_header = observation_header
        self.request_cap = request_cap
        self.requests = 0
        self.records: list[dict[str, Any]] = []
        self.chat = type("_Chat", (), {"completions": self})()

    def create(self, **kwargs: Any) -> Any:
        # Counted here, before anything leaves. Counting on the way back
        # would not count the requests that never came back, and those are
        # the ones most likely to have run anyway.
        self.requests += 1
        if self.request_cap is not None and self.requests > self.request_cap:
            raise RequestCapReached(
                f"request {self.requests} would exceed the pre-registered "
                f"ceiling of {self.request_cap}; stopping before it goes out"
            )
        record: dict[str, Any] = {"arm": self.arm}
        record.update(self._inspect(kwargs))
        sent = apply_arm(
            kwargs, self.arm, observation_header=self.observation_header
        )
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
        # How many of those requests came back as an exception rather than a
        # reply. Recorded because it is the one fact that tells a verdict
        # broken by an unreadable *answer* apart from a verdict missing
        # because the request was refused or never came back at all, and the
        # two have to end up in different ledger states. The checker compares
        # this count against those states; without it, a refusal reads as a
        # reply whose usage went missing.
        #
        # A count and not the error, deliberately. ``str(exc)`` from a provider
        # SDK routinely quotes the request URL and can quote a header, this
        # report is committed, and the ledger's own ``note`` already carries
        # the shape of the failure -- built there from a status number rather
        # than from a message.
        "requests_that_raised": sum(
            1 for r in records if r.get("transport_error") is not None
        ),
        "audio_sha256": sent[-1]["audio_sha256"] if sent else None,
        "audio_bytes": wav.get("bytes"),
        "audio_sample_rate_hz": wav.get("sample_rate_hz"),
        "audio_channels": wav.get("channels"),
        "audio_duration_s": wav.get("duration_s"),
        "audio_format": sent[-1]["audio_format"] if sent else None,
        "prompt_sha256": records[-1].get("prompt_sha256") if records else None,
        "prompt_chars": records[-1].get("prompt_chars") if records else None,
        "response_model": records[-1].get("response_model") if records else None,
        # Two token fields, because the question has two answers whenever a
        # call retried. The last request is the one that produced the verdict,
        # and it is the one ``audio_sha256`` and ``response_model`` above
        # describe, so ``audio_tokens`` stays last-request: it is the meter
        # reading for *this verdict*.
        "audio_tokens": tokens[-1] if tokens else None,
        # What the retry also cost. Billing counts requests, and a judge that
        # retries a malformed envelope sends the clip again. Summing the
        # last-request figure over sixty calls understates the bill by exactly
        # the retries -- six of them is 10%, which is the whole width of the
        # pre-registered delivery band, reported as "0.0% from expected".
        "audio_tokens_billed": sum(tokens) if tokens else None,
    }


def delivery_section(
    calls: Sequence[dict[str, Any]],
    *,
    measured: bool,
    clips: Sequence[Clip] = CLIPS,
    durations: Optional[Mapping[str, float]] = None,
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
    # ``durations`` overrides ``clips`` because the speech corpus is not made
    # of ``Clip``. Without it the tone durations would be compared against
    # speech clip ids, every lookup would miss, and every clip would be
    # reported as "sent duration differs" -- a false alarm on the one line a
    # reader is told to check before reading the accuracy.
    if durations is None:
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
        # Requests, not calls. A judge that retries a malformed envelope makes
        # two of these for one verdict and is billed for both, so this is the
        # number that explains a delivery total above the pre-registered one.
        # Equal to the call count on a run where nothing had to be retried.
        "requests_total": sum(c["wire"].get("requests") or 0 for c in wired),
        # Null, not zero, when nothing reported it. Zero is a claim -- "the
        # provider metered no audio", which is how a request that never
        # carried the sound looks -- and it must not be indistinguishable
        # from "the provider did not tell us". The pre-registered stop rule
        # in 330 fires on a real zero, so the two have to stay apart.
        #
        # Summed from ``audio_tokens_billed``, which counts every request the
        # call made. The last-request figure beside it is the meter for the
        # verdict; this line is labelled "actually billed" in the summary and
        # has to be that.
        "audio_tokens_total": (
            sum(
                c["wire"]["audio_tokens_billed"] for c in wired
                if c["wire"].get("audio_tokens_billed") is not None
            )
            if any(c["wire"].get("audio_tokens_billed") is not None for c in wired)
            else None
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


def _binomial_at_most(k: int, n: int, p: float) -> float:
    """``P(X <= k)`` for ``X ~ Binomial(n, p)``. Exact, no approximation."""
    if k < 0:
        return 0.0
    if k >= n:
        return 1.0
    return sum(
        math.comb(n, i) * (p ** i) * ((1.0 - p) ** (n - i)) for i in range(k + 1)
    )


def minimum_settled_claims(alpha: float = 0.05) -> int:
    """How many settled claims the primary test needs before it *can* pass.

    330 section 4's primary analysis is an exact one-sided binomial against
    p = 0.5, so a perfect score on ``n`` claims produces ``1 / 2**n`` and
    nothing smaller. Below the ``n`` returned here no result the design can
    produce clears ``alpha``, however well the model does.

    This is arithmetic about the test, not about any run. ``binomial_majority_test``
    already publishes the same quantity per run as ``smallest_attainable_p``.
    """
    n = 1
    while 1 / (2 ** n) > alpha:
        n += 1
    return n


def required_response_rate(
    *, claims: int, repeats: int, settled_claims_needed: int
) -> float:
    """The per-call answer rate this *design* needs, derived from the design.

    A claim earns a place in both of 330's claim-level figures -- the majority
    the binomial test scores, and the stability count -- only when at least two
    of its repeats answered. One answer gives a majority that is a single draw
    and no comparable pair at all; zero gives neither.

    So: with ``claims`` criteria asked ``repeats`` times each, and calls that
    answer independently with probability ``r``, the expected number of claims
    with two or more answers is ``claims * P(X >= 2)`` for ``X ~ B(repeats, r)``.
    The rate returned is the smallest ``r`` at which that expectation reaches
    ``settled_claims_needed``.

    Every input is a property of the design and none of them is a measurement.
    Feed it 330's corpus -- 20 claims, 3 repeats, 5 settled claims from
    :func:`minimum_settled_claims` -- and it answers 0.3264 without having seen
    a run. That is the point: a threshold read off an arm's observed failure
    rate is a threshold fitted to the run it is meant to judge.

    Independence is an assumption and it is the optimistic one. If failures
    cluster by claim -- one criterion the model will not answer for, whatever
    the repeat -- the same overall rate yields *fewer* claims with two answers
    than this formula says. Treat the result as a floor.
    """
    if repeats < 2:
        raise ValueError(
            "a claim needs two answered repeats to be comparable, so a design "
            f"with repeats={repeats} has no response rate that satisfies it"
        )
    if not 0 < settled_claims_needed <= claims:
        raise ValueError(
            f"settled_claims_needed={settled_claims_needed} is not reachable "
            f"with claims={claims}"
        )
    target = settled_claims_needed / claims
    low, high = 0.0, 1.0
    for _ in range(200):  # bisection: the expectation is increasing in r
        mid = (low + high) / 2
        # P(X >= 2) = 1 - P(X <= 1)
        if 1.0 - _binomial_at_most(1, repeats, mid) < target:
            low = mid
        else:
            high = mid
    return high


#: 330's corpus: 20 criteria, 3 repeats. :func:`minimum_settled_claims` puts
#: the floor at 5 settled claims (1/2**5 = 0.03125, the first that clears
#: 0.05), and :func:`required_response_rate` turns that into 0.3264. Rounded
#: **up** to a third, which is the direction that protects the design's sample
#: requirement rather than the arm's benefit of the doubt; the evidence gate
#: below is what keeps that from stopping a healthy arm on noise.
#:
#: Derived before the counterfactual in 336 section 6 was computed, and pinned
#: by ``test_the_response_rate_threshold_comes_from_the_design_not_from_334``,
#: which recomputes it from the corpus rather than reading this literal.
MIN_RESPONSE_RATE = 1 / 3


@dataclass(frozen=True)
class StopRules:
    """When to walk away from a paid run, decided before it starts.

    Pre-registered in ``330-speech-diagnostic-prereg.md`` section 3, and
    extended once, in ``336-silence-is-not-agreement.md`` section 3. They are
    written here rather than left to a person watching the log because a rule
    that only exists in a document is a rule that gets reconsidered at the
    moment it would cost something -- which is when "just a bit more" wins.

    Stopping is not a failure and not a discarded run. Whatever was collected
    is reported, with ``stopped`` saying which rule fired and where, so a
    reader can see the run is partial rather than inferring it from a count.

    ``None`` on any field disables that rule. The tone corpus runs with every
    rule off, because its results are already published and turning these on
    for it would change a methodology after the fact.
    """

    #: Wall clock, seconds. Checked after each call, so a single very slow
    #: call can overshoot it; the alternative is killing a call mid-flight
    #: and paying for a response nobody reads.
    wall_clock_seconds: Optional[float] = None
    #: If the first N calls of *one arm* yield no usable verdict at all, stop.
    #: Sixty calls of a broken response format cost the same as sixty good
    #: ones and teach nothing; this is the rule that would have ended the
    #: observation arm of 328 after ten. Per arm rather than per run because
    #: a two-arm run interleaves them and the healthy arm otherwise hides the
    #: silent one -- see ``_stop_reason`` and 334 section 6, which also says
    #: why this scoping alone would not have stopped 334.
    zero_response_after: Optional[int] = None
    #: Cumulative provider failures. Infrastructure, not capability -- there
    #: is nothing to learn about the model by retrying it into a wall.
    max_provider_failures: Optional[int] = None
    #: Stop on the first call the provider says carried no audio. Measuring
    #: comprehension of sound that was never delivered produces a number that
    #: looks exactly like a real one.
    stop_on_undelivered_audio: bool = False
    #: The answer rate the design needs from an arm, as a share of its calls.
    #: The rule above cannot reach an arm that answers *sometimes*: 334's
    #: observation arm answered on its fourth call and then failed 27 in a
    #: row, so "no answer at all in the leading window" was false from call
    #: four and all 120 were bought. This is the rate below which the run has
    #: no design left; see :data:`MIN_RESPONSE_RATE` for where the number
    #: comes from, which is the corpus and not that arm.
    min_response_rate: Optional[float] = None
    #: Calls in one arm before the rate rule may fire at all. Nine answers out
    #: of nine calls and zero out of two are the same evidence about a rate.
    response_rate_min_observations: Optional[int] = None
    #: The rule fires when ``P(answers this few | the arm meets the rate)``
    #: falls to or below this. A point comparison would stop a healthy arm
    #: sitting exactly at the requirement more than half the time on a short
    #: window; this asks for evidence instead. Checked after every call, so the
    #: run-level false-stop rate is higher than this figure -- 336 section 5
    #: measures it rather than waving at it.
    response_rate_alpha: float = 0.05


#: The rules named in 330 section 3, in the order that document lists them,
#: plus the response-rate rule 334 section 10 item 2 asked for and 336 section
#: 3 pins. The four values 330 registered are unchanged; the new rule can only
#: stop runs that have not happened yet, and no published figure moves.
SPEECH_STOP_RULES = StopRules(
    wall_clock_seconds=20 * 60,
    zero_response_after=10,
    max_provider_failures=10,
    stop_on_undelivered_audio=True,
    min_response_rate=MIN_RESPONSE_RATE,
    response_rate_min_observations=10,
    response_rate_alpha=0.05,
)

#: The same rules on a shorter clock, for :data:`AUDIO_COST_METERING_KIND`.
#:
#: Derived from :data:`SPEECH_STOP_RULES` with ``replace`` rather than
#: restated, so a rule added to the speech run arrives here too and cannot be
#: forgotten in one of two lists.
#:
#: The other rules are left exactly as they are even though a two-call run
#: can never reach most of them -- ``zero_response_after=10`` needs ten calls
#: and this run makes two. They stay because a rule that cannot fire costs
#: nothing and a rule quietly dropped from a derived config is how the
#: derived config stops being the one that was reviewed.
#:
#: ``stop_on_undelivered_audio`` is the one that can fire here, and it should:
#: a run that recorded two ledger rows for two requests that carried no sound
#: has metered something, but not the thing this is about.
AUDIO_COST_METERING_STOP_RULES = dataclass_replace(
    SPEECH_STOP_RULES,
    wall_clock_seconds=AUDIO_COST_METERING_WALL_CLOCK_SECONDS,
)


def stop_rules_for(
    *, metering: bool, speech: Optional[SpeechCorpus]
) -> Optional[StopRules]:
    """Which stop rules a run gets, as a function rather than an expression.

    Three inputs, three answers, and the one that matters is the last: the
    **tone corpus gets none**. Its numbers are published, and switching rules
    on for that path now would change the design a reported result was
    produced under, after the fact.

    This is a function so the guard on that property can *run* it instead of
    grepping for the line that used to hold it. The grep version broke the
    moment the metering branch was added -- while the property it was
    defending was still true -- which is the failure mode of a test that
    reads source instead of calling it.
    """
    if metering:
        return AUDIO_COST_METERING_STOP_RULES
    return SPEECH_STOP_RULES if speech else None


def _audio_was_delivered(call: dict[str, Any]) -> Optional[bool]:
    """Did this call carry sound? ``None`` when the provider did not say.

    Three states, not two. A provider that reports nothing is not a provider
    reporting zero, and only the second is evidence of non-delivery.
    """
    wire = call.get("wire")
    if not isinstance(wire, dict):
        return None
    carried = wire.get("requests_with_audio")
    if carried is not None and not carried:
        return False
    tokens = wire.get("audio_tokens")
    if tokens is not None:
        return bool(tokens)
    if carried:
        return True
    return None


def _stop_reason(
    rules: StopRules,
    *,
    calls: Sequence[dict[str, Any]],
    elapsed_s: float,
) -> Optional[dict[str, Any]]:
    """The first rule that fires, or ``None``. Evaluated after every call."""
    if rules.wall_clock_seconds is not None and elapsed_s > rules.wall_clock_seconds:
        return {
            "rule": "wall_clock_seconds",
            "limit": rules.wall_clock_seconds,
            "observed": round(elapsed_s, 3),
            "after_calls": len(calls),
            "reading": (
                "The run exceeded its pre-registered time limit. What is "
                "below is a partial run and its counts are not the design's."
            ),
        }

    if rules.stop_on_undelivered_audio and calls:
        if _audio_was_delivered(calls[-1]) is False:
            return {
                "rule": "stop_on_undelivered_audio",
                "limit": None,
                "observed": calls[-1].get("claim_id"),
                "after_calls": len(calls),
                "reading": (
                    "The provider reported a request that carried no audio. "
                    "Nothing measured after this point would be about "
                    "hearing, so the run stops rather than producing a "
                    "number that looks like an accuracy."
                ),
            }

    if rules.max_provider_failures is not None:
        failures = sum(
            1 for c in calls if c.get("unanswered_kind") == "provider_failure"
        )
        if failures >= rules.max_provider_failures:
            return {
                "rule": "max_provider_failures",
                "limit": rules.max_provider_failures,
                "observed": failures,
                "after_calls": len(calls),
                "reading": (
                    "Infrastructure, not capability. Retrying into a wall "
                    "buys nothing and says nothing about the model."
                ),
            }

    if rules.zero_response_after is not None:
        # Counted per arm, not over the whole run. A two-arm run interleaves
        # production and observation, so a whole-run count is satisfied by
        # the healthy arm answering and the rule can never fire -- which is
        # exactly what happened in 334: the observation arm went 27 calls in
        # a row without a readable verdict and nothing stopped it, because
        # call 1 was production and it answered.
        #
        # A single-arm run has one group holding every call, so this is the
        # same rule it has always been for the runs already published.
        #
        # This is necessary and NOT sufficient. The shape of the rule is
        # "no answer at all in the leading window", and 334's observation arm
        # answered once on its fourth call, so even per-arm this would not
        # have fired there. Stopping an arm that answers 15% of the time
        # needs a response-rate rule, and its threshold has to be pinned
        # before a run rather than chosen after seeing one. See 334 section 6.
        by_arm: dict[Any, list[dict[str, Any]]] = {}
        for call in calls:
            by_arm.setdefault(call.get("arm"), []).append(call)
        for arm, arm_calls in by_arm.items():
            if len(arm_calls) < rules.zero_response_after:
                continue
            answered = sum(
                1 for c in arm_calls if c.get("unanswered_kind") is None
            )
            if answered == 0:
                return {
                    "rule": "zero_response_after",
                    "limit": rules.zero_response_after,
                    "observed": 0,
                    "arm": arm,
                    "after_calls": len(calls),
                    "after_calls_in_arm": len(arm_calls),
                    "reading": (
                        "No usable verdict in the first "
                        f"{len(arm_calls)} calls of arm {arm!r}. On "
                        "2026-09-06 a run in this state went on to buy all "
                        "sixty and reported an accuracy over the seventeen "
                        "replies that happened to parse. This stops instead."
                    ),
                }

    if (
        rules.min_response_rate is not None
        and rules.response_rate_min_observations is not None
    ):
        # The rule the one above cannot be: an arm that answers *sometimes*.
        # Checked per arm for the same reason, and placed after it so that a
        # window with no answers at all is still reported under the older,
        # simpler name rather than being re-described in terms of a p-value.
        #
        # Not a point comparison. An arm whose true rate is exactly the
        # requirement lands below it on about half of short windows, and
        # stopping on that would be stopping on noise. What fires here is
        # evidence: the probability of seeing this few answers *if the arm
        # met the requirement*. At the minimum window of ten that reduces to
        # "zero answers" -- P(<=1 | 10, 1/3) is 0.104, above alpha -- so the
        # new rule starts exactly where the old one already was and gains its
        # reach only as calls accumulate. It cannot have been tuned to make
        # any particular run stop early, because at its first opportunity it
        # does nothing the pre-existing rule did not already do.
        by_arm_rate: dict[Any, list[dict[str, Any]]] = {}
        for call in calls:
            by_arm_rate.setdefault(call.get("arm"), []).append(call)
        for arm, arm_calls in by_arm_rate.items():
            n = len(arm_calls)
            if n < rules.response_rate_min_observations:
                continue
            answered = sum(
                1 for c in arm_calls if c.get("unanswered_kind") is None
            )
            p_value = _binomial_at_most(answered, n, rules.min_response_rate)
            if p_value <= rules.response_rate_alpha:
                return {
                    "rule": "min_response_rate",
                    "limit": rules.min_response_rate,
                    "observed": answered / n,
                    "answered_in_arm": answered,
                    "arm": arm,
                    "after_calls": len(calls),
                    "after_calls_in_arm": n,
                    "p_if_the_arm_met_the_limit": p_value,
                    "alpha": rules.response_rate_alpha,
                    "reading": (
                        f"Arm {arm!r} answered {answered} of {n}. If it were "
                        f"answering at the rate the design needs "
                        f"({rules.min_response_rate:.4f}), a window this thin "
                        f"would happen with probability {p_value:.5f}. The "
                        "remaining calls would buy an arm that cannot reach "
                        "the minimum sample the primary test needs. This is a "
                        "spending rule, not a finding about the model: it "
                        "says the run has no design left, not that the arm is "
                        "worse."
                    ),
                }

    return None


def _stop_census(
    calls: Sequence[dict[str, Any]], arms: Sequence[str]
) -> dict[str, Any]:
    """What a stop left half-finished, and what that does to the analysis.

    A stop lands between calls, and the arms are interleaved within a claim,
    so the last claim can hold a production call and no observation one. The
    run does not buy the partner call to tidy the record -- that would spend
    money after the decision to stop spending it -- so the imbalance is
    reported instead, by name, for every analysis downstream that assumes the
    arms are paired.
    """
    per_arm: dict[str, dict[str, int]] = {}
    for call in calls:
        per_arm.setdefault(str(call["claim_id"]), {})
        arm = str(call.get("arm"))
        per_arm[str(call["claim_id"])][arm] = (
            per_arm[str(call["claim_id"])].get(arm, 0) + 1
        )
    names = [str(a) for a in arms]
    missing = sorted(
        claim_id
        for claim_id, counts in per_arm.items()
        if any(name not in counts for name in names)
    )
    unequal = sorted(
        claim_id
        for claim_id, counts in per_arm.items()
        if len({counts.get(name, 0) for name in names}) > 1
    )
    return {
        "claims_missing_an_arm_entirely": missing,
        "claims_with_unequal_calls_across_arms": unequal,
        "inference": (
            "A stop makes the sample size depend on the data, so this run's "
            "pre-registered tests are no longer the tests that were "
            "registered -- their n was chosen by the rule. Report the counts "
            "and the stop. Do not report a p-value computed over the pairs "
            "that survived as though the design had produced them, and do not "
            "compare a stopped arm's accuracy with a complete one's: the "
            "calls it did not make are not missing at random."
        ),
    }


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
    prerendered: Optional[SpeechCorpus] = None,
    stop_rules: Optional[StopRules] = None,
    clock: Callable[[], float] = time.monotonic,
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

    With ``prerendered``, the tone synthesiser is not used at all: the clips
    are files that already exist and whose digests were checked on load. The
    speech set has to arrive this way because it cannot be built on this host,
    and re-deriving its digests here would pin whatever was downloaded rather
    than what was published.
    """
    for arm in arms:
        if arm not in PROMPT_ARMS:
            raise ValueError(f"unknown prompt arm: {arm}")
    if wire is None and tuple(arms) != ("production",):
        # The arm swap happens inside the wrapper. Without one, the request
        # would go out under the production prompt and be labelled with the
        # other arm's name, which is not a weaker measurement but a false one.
        raise ValueError("a non-production arm needs a WireClient to rewrite it")

    if prerendered is not None:
        digests = dict(prerendered.digests)
        paths = dict(prerendered.paths)
    else:
        digests = {}
        paths = {}
        for clip in clips:
            path = clip_dir / f"{clip.clip_id}.wav"
            digests[clip.clip_id] = render_clip(clip, path)
            paths[clip.clip_id] = path

    calls: list[dict[str, Any]] = []
    stopped: Optional[dict[str, Any]] = None
    started_at = clock()
    for repeat in range(1, repeats + 1):
        if stopped is not None:
            break
        for claim in claims:
            if stopped is not None:
                break
            for arm in arms:
                if stopped is not None:
                    break
                if wire is not None:
                    wire.arm = arm
                    first_record = len(wire.records)
                perception.reset()
                try:
                    verdict = perception.judge(
                        criterion=claim.criterion,
                        audio_path=str(paths[claim.clip_id]),
                    )
                except RequestCapReached as exc:
                    # Recorded in the same shape as the other stop rules, and
                    # for the same reason: the run stops here, and what it
                    # already bought stays in the record. Letting this raise
                    # past the loop would drop ``calls`` -- a local -- and
                    # throw away paid measurements in order to report a
                    # ceiling that the exit code reports anyway.
                    #
                    # ``requests`` was incremented before the check, so one of
                    # them is the request that was refused and never left.
                    sent = (wire.requests - 1) if wire is not None else None
                    stopped = {
                        "rule": "request_cap",
                        "limit": wire.request_cap if wire is not None else None,
                        "observed": sent,
                        "after_calls": len(calls),
                        "reading": (
                            "The pre-registered request ceiling was reached "
                            "and the next request was not sent. What is below "
                            "is a partial run and its counts are not the "
                            f"design's. ({exc})"
                        ),
                    }
                    break
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
                if stop_rules is not None:
                    # After appending, so the call that tripped the rule is
                    # in the record rather than dropped from it.
                    stopped = _stop_reason(
                        stop_rules, calls=calls, elapsed_s=clock() - started_at
                    )
    if stopped is not None:
        # The stop is not bought out of by finishing the claim in flight. The
        # partner call would cost money the rule just decided not to spend,
        # so the record says what is unpaired instead of quietly evening it up.
        stopped = dict(stopped)
        stopped["left_behind"] = _stop_census(calls, [str(a) for a in arms])
    return {
        "calls": calls,
        "clip_sha256": digests,
        "stopped": stopped,
        "planned_calls": repeats * len(claims) * len(arms),
    }


def pair_consistency(by_claim: Mapping[str, Any]) -> dict[str, Any]:
    """330 section 4's first secondary metric: did each pair get told apart.

    Every pair is the same clip asked the same kind of question twice, once
    where the answer is yes and once where it is no. A judge that heard the
    clip answers them differently. A judge that answered without listening
    gives both sides the same verdict, and ten pairs of ``pass`` score 50% on
    this balanced corpus -- an accuracy figure that looks like a coin and
    reads like a near miss.

    Youden's J already summarises this as a difference of rates, but it
    cannot say *how many* pairs were never separated, and the document
    promises that count. Computing it here rather than deriving it from the
    per-claim table afterwards keeps it a pre-registered number.
    """
    sides: dict[str, dict[bool, Optional[str]]] = {}
    for entry in by_claim.values():
        pair_id = entry.get("pair_id")
        if pair_id is None:
            continue
        sides.setdefault(pair_id, {})[bool(entry["holds"])] = entry["majority"]

    identical_by_verdict: dict[str, int] = {}
    differently = identical = incomplete = 0
    for verdicts in sides.values():
        true_side = verdicts.get(True)
        false_side = verdicts.get(False)
        if true_side is None or false_side is None:
            incomplete += 1
        elif true_side != false_side:
            differently += 1
        else:
            identical += 1
            identical_by_verdict[true_side] = (
                identical_by_verdict.get(true_side, 0) + 1
            )
    return {
        "unit": "one true/false pair, on majority verdicts",
        "pairs": len(sides),
        "answered_differently": differently,
        "answered_identically": identical,
        "identical_by_verdict": dict(sorted(identical_by_verdict.items())),
        "incomplete": incomplete,
        "meaning": (
            "A pair answered identically was not told apart. Both sides "
            "'pass' on every pair is what a judge that never heard the clip "
            "produces, and on this balanced corpus it still scores 50%. "
            "'incomplete' pairs had no majority on one side and are neither."
        ),
    }


def repeat_flip_rate(by_claim: Mapping[str, Any]) -> dict[str, Any]:
    """Disagreement between repeats, in the denominator the earlier study used.

    The repeat run this script's header quotes reported 19.35%: verdict flips
    divided by *pairs of runs*, three such pairs per item at three repeats.
    ``stability`` below counts something else -- claims whose repeats were all
    identical -- and one minus that share is the share of claims that flipped
    *at all*. On three repeats a claim that flips once is 100% of the second
    figure and 33% of the first, so setting them beside each other reads as a
    change in steadiness that never happened. 330 section 4 promises the
    comparison, so the comparable number has to exist.

    Pairs where either side never answered are not disagreements about the
    audio; they leave the denominator and are counted where a reader can see
    how much of the run they were.
    """
    pairs = 0
    flips = 0
    dropped = 0
    ever_flipped = 0
    claims_compared = 0
    for entry in by_claim.values():
        verdicts = entry["verdicts"]
        flipped_here = False
        pairs_here = 0
        for left in range(len(verdicts)):
            for right in range(left + 1, len(verdicts)):
                a, b = verdicts[left], verdicts[right]
                if a == "judge_error" or b == "judge_error":
                    dropped += 1
                    continue
                pairs += 1
                pairs_here += 1
                if a != b:
                    flips += 1
                    flipped_here = True
        # A claim with no comparable pair neither flipped nor held steady.
        # Counting it as "did not flip" is the same mistake as calling three
        # unanswered repeats identical, and 334 published both at once: its
        # observation arm reported ``claims_that_ever_flipped: 0`` beside
        # ``comparable_pairs: 2`` and 58 pairs dropped, which reads as twenty
        # steady claims and describes two. 330 section 4 already fixed the rule
        # for the pair denominator -- "한쪽이라도 답이 안 온 쌍은 분모에서
        # 뺀다. 안 온 답은 일치도 불일치도 아니다" -- and this is the same
        # sentence applied to the claim denominator it also has to hold for.
        if pairs_here:
            claims_compared += 1
            ever_flipped += int(flipped_here)
    return {
        "unit": "one pair of repeats for one claim",
        "comparable_pairs": pairs,
        "pairs_dropped_for_a_missing_answer": dropped,
        "flips": flips,
        # Null, not zero, on a run with nothing to compare. Zero would say the
        # repeats agreed.
        "flip_rate_pct": (100.0 * flips / pairs) if pairs else None,
        "claims_that_ever_flipped": ever_flipped,
        # The denominator that figure belongs to. Without it a reader divides
        # by the corpus size and gets a steadiness that includes every claim
        # the arm never answered.
        "claims_compared": claims_compared,
        "claims_with_no_comparable_pair": len(by_claim) - claims_compared,
        "prior_audio_cohort_pct": 19.3548,
        "meaning": (
            "Share of repeat pairs that answered differently, the same "
            "denominator as the 19.35% measured on the graded audio cohort. "
            "'claims_that_ever_flipped' is the other denominator, is out of "
            "'claims_compared' rather than out of the corpus, and is not "
            "comparable with that figure. Claims with fewer than two answered "
            "repeats are in neither count."
        ),
    }


def binomial_majority_test(
    by_claim: Mapping[str, Any],
) -> dict[str, Any]:
    """330 section 4's *primary* analysis, computed rather than described.

    One verdict per claim by majority of the repeats, then an exact one-sided
    binomial test against p = 0.5. Chance is 50% because the corpus is
    balanced -- ten true claims and ten false ones.

    This is reported *beside* the within-pair permutation test, and both are
    named in the pre-registration before any of them has a value. Computing
    only one and choosing which to call primary after seeing them is the
    failure this whole document exists to avoid, and having two numbers where
    one is labelled primary is the only arrangement in which that choice
    cannot be made later.

    The repeats are collapsed by majority on purpose. Counting 60 calls as 60
    independent trials inflates the denominator threefold and manufactures a
    significance the design cannot support: the three calls for one claim ask
    the same question about the same audio.
    """
    outcomes = [
        entry["majority_outcome"]
        for entry in by_claim.values()
        if entry["majority"] is not None
    ]
    # A hedge is not a correct answer and it is not an incorrect one either.
    # Dropping it shrinks n honestly; scoring it either way would not.
    scored = [o for o in outcomes if o != OUTCOME_HEDGED]
    n = len(scored)
    correct = sum(1 for o in scored if o == OUTCOME_CORRECT)
    p_value = (
        sum(math.comb(n, i) for i in range(correct, n + 1)) / (2 ** n)
        if n
        else None
    )
    return {
        "test": "exact one-sided binomial, p = 0.5",
        "unit": "one majority verdict per claim",
        "claims_with_a_majority": len(outcomes),
        "hedged_majorities_excluded": len(outcomes) - n,
        "n": n,
        "correct": correct,
        "p_one_sided": p_value,
        # The floor a perfect score can reach. Below n = 5 nothing this test
        # can produce clears 0.05, and a reader deserves to know that before
        # reading the p rather than after.
        "smallest_attainable_p": (1 / (2 ** n)) if n else None,
        "meaning": (
            "P(at least this many correct | the judge is guessing). The "
            "repeats are collapsed to one verdict per claim first; treating "
            "them as independent trials would triple the denominator and "
            "invent significance the design cannot support."
        ),
    }


def summarise(
    calls: Sequence[dict[str, Any]],
    *,
    claims: Sequence[Claim] = CLAIMS,
) -> dict[str, Any]:
    """Turn the call log into the three numbers the card asked for.

    ``claims`` is the corpus that ran, not the tone corpus. The per-claim
    table below is keyed by claim id, so a default of ``CLAIMS`` matches
    nothing on a speech run and every per-claim figure -- the majority vote,
    the stability count, the per-claim discrimination -- comes back empty
    while the per-call figures look perfectly healthy. 330's *primary*
    analysis is the majority vote, so that is the number that would have
    gone missing after the money was spent.
    """
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
    for claim in claims:
        verdicts = [c["verdict"] for c in calls if c["claim_id"] == claim.claim_id]
        if not verdicts:
            continue
        majority = majority_verdict(verdicts)
        answered = [v for v in verdicts if v != "judge_error"]
        by_claim[claim.claim_id] = {
            "holds": claim.holds,
            "family": claim.family,
            # Carried so the pair census below reads it from here rather than
            # from a second pass over the calls that could drift out of step.
            "pair_id": claim.pair_id,
            "verdicts": verdicts,
            "majority": majority,
            "repeats": len(verdicts),
            "answered_repeats": len(answered),
            # Three states, not two. ``None`` is "there was nothing to
            # compare", and it is not ``False`` either: a claim answered once
            # did not disagree with itself.
            #
            # This used to be ``len(set(verdicts)) == 1``, which made three
            # unanswered repeats collapse to a one-element set and report as
            # perfectly consistent. 334's observation arm published
            # ``identical_across_repeats: 13`` under that rule, and all
            # thirteen of those claims had never produced a verdict at all --
            # the count of consistently *answered* claims was zero. 330
            # section 4 had already written the rule for the pair denominator;
            # this is the same rule where it was missing.
            "stable": (
                (len(set(answered)) == 1) if len(answered) >= 2 else None
            ),
            "majority_outcome": (
                classify(claim, majority) if majority is not None else None
            ),
        }

    per_call = discrimination([(c["holds"], c["verdict"]) for c in calls])
    comparable_claims = sum(
        1 for entry in by_claim.values() if entry["stable"] is not None
    )
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
        # Both, always, and labelled. The pre-registration names the binomial
        # as primary; the permutation is the pre-specified secondary. Neither
        # is chosen after the numbers exist.
        "pre_registered_binomial": binomial_majority_test(by_claim),
        "permutation": permute_within_pairs(calls),
        # The count J cannot give: how many pairs were never separated at all.
        "pair_consistency": pair_consistency(by_claim),
        "mean_confidence": {
            key: (sum(values) / len(values) if values else None)
            for key, values in confidences.items()
        },
        "stability": {
            "claims": len(by_claim),
            # The denominator, printed beside the count rather than left for a
            # reader to assume is ``claims``. A claim needs two answered
            # repeats before "did they agree" is a question with an answer.
            "claims_with_two_or_more_answers": comparable_claims,
            "identical_across_repeats": sum(
                1 for entry in by_claim.values() if entry["stable"] is True
            ),
            "differed_across_repeats": sum(
                1 for entry in by_claim.values() if entry["stable"] is False
            ),
            "claims_without_two_answers": sum(
                1 for entry in by_claim.values() if entry["stable"] is None
            ),
            # Null, not zero, when nothing was comparable -- the same rule
            # ``flip_rate_pct`` follows two fields down.
            "identical_share_of_comparable": _rate(
                sum(1 for entry in by_claim.values() if entry["stable"] is True),
                comparable_claims,
            ),
            "no_majority": sum(
                1 for entry in by_claim.values() if entry["majority"] is None
            ),
            # The figure 330 promises to set against the earlier 19.35%. It
            # lives here rather than being left for a reader to divide,
            # because the obvious division of the fields above answers a
            # different question and looks like the same one.
            "repeat_flips": repeat_flip_rate(by_claim),
            "meaning": (
                "'identical_across_repeats' counts claims whose *answered* "
                "repeats all agreed, out of 'claims_with_two_or_more_answers' "
                "and not out of 'claims'. Before 336 it counted a claim whose "
                "repeats were every one of them unanswered as identical, "
                "which is how 334's observation arm published 13 of 20 while "
                "the number of consistently answered claims was 0. Runs "
                "published before 336 carry the older count and are not "
                "comparable with this field."
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


# --------------------------------------------------------------------------
# What it cost
# --------------------------------------------------------------------------
#
# Until 340 this section was four hand-written constants. ``pricing_complete``
# was ``not billable`` -- the run's own answer to "did anyone pay for this",
# dressed up as an answer to "does every model on this bill have a rate". A
# free run therefore announced that its pricing was complete, for a model that
# has no price at all, and a paid run announced the opposite for exactly the
# same reason. Neither sentence had been anywhere near the price table.
#
# So none of it is written here any more. The models come off the ledger rows,
# the rates come off the shared price table, the total comes off the receipt
# the shared code builds from those rows, and this file's remaining job is to
# say which task the calls belong to and where the ledger is. The four
# constants are gone rather than corrected, because a constant that happens to
# be right is still not a measurement.


#: Reasons a receipt can be partial, split by which half of the question they
#: fall in. The two are not interchangeable and the report says which is which:
#: a missing *price* is a gap in the table and costs nothing to fix later,
#: because the tokens are recorded and can be multiplied by a rate whenever one
#: is published. A missing *usage* is a reply nobody kept, and no later table
#: brings it back. Reporting them as one "incomplete" hides the difference
#: between a run that can be priced tomorrow and one that never can.
PRICE_REASONS = (REASON_PRICE_MISSING,)
USAGE_REASONS = (REASON_USAGE_ABSENT, REASON_USAGE_PARTIAL)


def split_missing_reasons(reasons: Iterable[str]) -> dict[str, list[str]]:
    """Partition a receipt's reasons into price, usage and everything else."""
    listed = [str(reason) for reason in reasons]
    return {
        "price": sorted({r for r in listed if r in PRICE_REASONS}),
        "usage": sorted({r for r in listed if r in USAGE_REASONS}),
        "other": sorted(
            {r for r in listed if r not in PRICE_REASONS and r not in USAGE_REASONS}
        ),
    }


def ledger_models(rows: Sequence[Mapping[str, Any]]) -> list[tuple[str, str]]:
    """The ``(provider, model)`` pairs a set of ledger rows actually reached.

    ``resolved_model`` and not ``requested_model``: the reply says which model
    answered, the request says which alias was asked for, and the price table
    is keyed on the first. A row that has not been settled has no resolved
    model yet and falls back to what it asked for, flagged as such by being
    unsettled rather than by being dropped -- a row left out here is spend left
    out of the models list.
    """
    pairs: set[tuple[str, str]] = set()
    for row in rows:
        model = row.get("resolved_model") or row.get("requested_model")
        if not model:
            continue
        pairs.add((str(row.get("provider") or ""), str(model)))
    return sorted(pairs)


def unpriced_models(
    pairs: Sequence[tuple[str, str]], price_table: Optional[ReceiptPriceTable]
) -> list[str]:
    """Which of these models the table publishes no rate for.

    With no table at all every model is unpriced, which is the honest reading:
    a lookup that could not be performed did not succeed. The alternative --
    an empty list, meaning "nothing was found to be unpriced" -- reads as
    completeness and is how a missing file becomes a clean bill.
    """
    if price_table is None:
        return sorted({model for _, model in pairs})
    return sorted(
        {model for provider, model in pairs if price_table.lookup(provider, model) is None}
    )


def _price_table_or_none(
    path: Optional[Path] = None,
) -> tuple[Optional[ReceiptPriceTable], Optional[str]]:
    """Load the shared price table, or say why not -- but never raise.

    A price table that will not load is a reason to report an unknown cost, not
    a reason to lose the run. The rows are already bought by the time anything
    here is priced, and a crash at this point would throw away the record of
    what they were while leaving the charge exactly where it was.

    The failure is returned as a sentence rather than swallowed, because the
    caller puts it in the report: ``unpriced_models`` will list every model in
    the run, and without this note a reader has no way to tell "no published
    rate for gpt-audio-1.5" from "the file that holds the rates was
    unreadable". Those two lead to different next actions.
    """
    target = path or PRICE_TABLE_PATH
    try:
        return load_receipt_price_table(target), None
    except Exception as exc:  # noqa: BLE001 - any failure here means "no rates"
        return None, (
            f"The price table at {target} could not be read ({exc}), so no "
            f"model in this run could be priced. Every model is listed as "
            f"unpriced for that reason and not because it has no rate."
        )


def record_kind_of(row: Mapping[str, Any]) -> str:
    """Whether a ledger row was bought or rehearsed.

    Read off ``provider``, which the stub sets to something no billing system
    has ever heard of. Putting ``azure`` on a row nothing was charged for
    would be a false statement in the one column a monthly-spend query filters
    on, and the row would be indistinguishable from a real one the moment it
    left this script.
    """
    return "rehearsal" if str(row.get("provider")) == STUB_PROVIDER else "measured"


def ledger_record_kinds(ledger: CostReceiptLedger) -> set[str]:
    """Which kinds of run have already written rows into this ledger."""
    kinds: set[str] = set()
    for task_id in ledger.task_ids():
        for row in ledger.calls_for(task_id):
            kinds.add(record_kind_of(row))
    return kinds


def close_cost_record(
    recorder: Optional[Any],
    *,
    identity: Mapping[str, Any],
    measured: bool,
    model_calls: int,
    export_to: Optional[Path] = None,
    price_table_path: Optional[Path] = None,
    notes: Sequence[str] = (),
) -> dict[str, Any]:
    """Close the books on a run and return its cost block.

    Called from a ``finally``, so it runs on the paths that end badly as well
    as the one that ends well. A run that hit its request ceiling, or whose
    replies would not parse, has still bought every request it sent; the
    sidecar is how those rows leave this process, and skipping the export on
    the unhappy path would delete the record of exactly the spend nobody
    planned for.

    The price table is taken off the ledger rather than re-read, because the
    rows were priced by *that* table and a second read could pick up a
    different file.
    """
    if recorder is None:
        table, table_note = _price_table_or_none(price_table_path)
        return cost_section(
            identity=identity,
            measured=measured,
            model_calls=model_calls,
            price_table=table,
            price_table_path=price_table_path,
            notes=[*notes, *([table_note] if table_note else [])],
        )

    ledger = recorder.ledger
    extra = list(notes)
    reference: Optional[dict[str, Any]] = None
    receipt: Optional[CostReceipt] = None
    rows: Sequence[Mapping[str, Any]] = ()
    try:
        rows = ledger.calls_for(COST_TASK_ID, bucket=BUCKET_GRADING)
        receipt = recorder.receipt_for(COST_TASK_ID, BUCKET_GRADING)
        if export_to is not None:
            digest = ledger.export_jsonl(export_to)
            reference = {
                **ledger_reference(export_to, digest),
                "rows": len(
                    [
                        line
                        for line in export_to.read_text(
                            encoding="utf-8"
                        ).splitlines()
                        if line.strip()
                    ]
                ),
            }
    except Exception as exc:  # noqa: BLE001 - reported, never swallowed
        # The rows are in the database whatever happened here; what is lost is
        # the published copy of them. Saying so is the difference between a
        # reader going to look for the sidecar and a reader assuming the run
        # made none.
        extra.append(
            f"The ledger at {getattr(ledger, 'path', '?')} was written, but "
            f"reading it back failed ({type(exc).__name__}: {exc}). The rows "
            f"are still in the database; the published sidecar and the "
            f"receipt below may be incomplete or absent."
        )
    finally:
        table = ledger.price_table
        ledger.close()

    return cost_section(
        identity=identity,
        measured=measured,
        model_calls=model_calls,
        receipt=receipt,
        rows=rows,
        ledger=reference,
        price_table=table,
        price_table_path=price_table_path,
        notes=extra,
    )


def cost_section(
    *,
    identity: Mapping[str, Any],
    measured: bool,
    model_calls: int,
    receipt: Optional[CostReceipt] = None,
    rows: Sequence[Mapping[str, Any]] = (),
    ledger: Optional[Mapping[str, Any]] = None,
    price_table: Optional[ReceiptPriceTable] = None,
    price_table_path: Optional[Path] = None,
    notes: Sequence[str] = (),
) -> dict[str, Any]:
    """The cost block, computed rather than declared.

    Every field here is derived from something outside this file: the rows the
    metering wrapper wrote, the table the pipeline prices everything else with,
    and the receipt the shared code builds from the two. Called with no ledger
    -- which is what happens when a ledger could not be opened, and what the
    older tests do -- it still prices through the same table, and says plainly
    that it has no receipt rather than filling the gap with a constant.
    """
    billable = model_calls if measured else 0
    pairs = ledger_models(rows)
    if not pairs and billable:
        # No ledger to read the models off, but requests certainly went out.
        # The configured deployment is the best available statement of where,
        # and it is marked as coming from the configuration by the absence of
        # a receipt beside it.
        pairs = [("azure", str(identity["audio_deployment"]))]
    unpriced = unpriced_models(pairs, price_table)

    if not pairs:
        # Nothing was called, so there is no bill and no claim to make about
        # whether it is fully priced. ``true`` here is the sentence 340
        # section 2.2 caught: vacuously right, and read by everyone as "this
        # run's costs are fully accounted for".
        pricing_complete: Optional[bool] = None
    else:
        pricing_complete = not unpriced

    reasons = split_missing_reasons(
        receipt.missing_reasons if receipt is not None else ()
    )
    total = None if receipt is None else receipt.estimated_cost_usd

    sentences = list(notes)
    if not measured:
        # First, so it is the first thing read. Every other sentence in this
        # block describes the shape of a bill, and the shape of a bill is very
        # easy to mistake for one.
        sentences.append(
            "Rehearsal, not a bill. Every call above went to a local stub, so "
            "nothing here was charged and no figure below is money. The rows "
            "exist to show the metering path runs end to end; provider says "
            f"'{STUB_PROVIDER}' on every one of them."
        )
    if unpriced and measured:
        sentences.append(
            f"{', '.join(unpriced)} {'is' if len(unpriced) == 1 else 'are'} "
            f"absent from the price table, so the cost of this run is unknown "
            f"rather than zero. null, not $0."
        )
    elif unpriced:
        sentences.append(
            f"{', '.join(unpriced)} has no published rate, which is correct: "
            f"it is not a model and nothing was bought from it."
        )
    if not pairs:
        sentences.append("No model was called; this run cost nothing.")
    if receipt is None:
        sentences.append(
            "No ledger was opened for this run, so there is no receipt and no "
            "audit trail -- the figures above are counts of calls, not a "
            "record of spend."
        )
    if reasons["usage"]:
        sentences.append(
            "Usage is missing on at least one call "
            f"({', '.join(reasons['usage'])}), which no later price table can "
            "repair: a reply nobody kept cannot be re-counted."
        )

    block: dict[str, Any] = {
        # Which kind of record this is, inside the cost block rather than
        # beside it, so a block copied into a summary cannot arrive without
        # it. A rehearsal's numbers are the shape of a bill and not a bill.
        "record_kind": "measured" if measured else "rehearsal",
        "task_id": COST_TASK_ID if receipt is not None else None,
        # Two numbers, because a dry run makes 60 calls and is billed for
        # none of them. Collapsing them would put a "billable_calls: 60"
        # into a free run's report, and that is exactly the figure someone
        # copies into a cost record.
        "model_calls": model_calls,
        "billable_calls": billable,
        "models": [model for _, model in pairs],
        "price_table": (
            None
            if price_table is None
            else {
                "path": str(price_table_path or PRICE_TABLE_PATH),
                "sha256": price_table.sha256,
            }
        ),
        "pricing_complete": pricing_complete,
        "unpriced_models": unpriced,
        # Whether the *usage* landed, kept apart from whether a price exists.
        # ``None`` where there is no receipt to ask.
        "usage_complete": None if receipt is None else not reasons["usage"],
        "missing_reasons": reasons,
        "estimated_cost_usd": None if total is None else float(total),
        "receipt": None if receipt is None else receipt.as_dict(),
        "ledger": None if ledger is None else dict(ledger),
        "note": " ".join(sentences),
    }
    return block


def _digest_of(path: Optional[Path]) -> Optional[str]:
    """sha256 of a file, or ``None`` if it cannot be read.

    Never raises. This is called while assembling a report, and a report that
    cannot be written because one of its provenance fields was unreadable
    loses the whole run to describe a missing digest.
    """
    if path is None:
        return None
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None


def metering_section(
    *,
    document: Optional[Path],
    config_path: Path,
    speech_manifest: Optional[Path],
    claims: int,
    repeats: int,
    arms: int,
    request_cap: Optional[int],
) -> dict[str, Any]:
    """What the metering trial was registered as, and against what.

    Deliberately does **not** repeat the fingerprints that already have a
    home. The clip digests are ``report["clip_sha256"]``, the model and
    deployment and grader hash are ``report["pins"]``, and the price table is
    ``report["cost"]["price_table"]``. Copying them here would give a reader
    two fields to compare and, eventually, two fields that disagree -- and the
    one that is wrong would be indistinguishable from the one that is right.

    What it does carry is everything else the run was held to: which document
    opened the door, which config the identity was read out of, which
    manifest the audio came from, and the four settings that make this run
    different from an accuracy run. Those settings are recorded rather than
    left to the reader to infer from the constants in this file, because the
    constants can change and the run cannot.
    """
    return {
        "diagnostic_kind": AUDIO_COST_METERING_KIND,
        "preregistration": (
            None
            if document is None
            else {"file": Path(document).name, "sha256": _digest_of(document)}
        ),
        "grading_config": {
            "path": str(config_path),
            "sha256": _digest_of(config_path),
        },
        "speech_manifest": (
            None
            if speech_manifest is None
            else {
                "file": Path(speech_manifest).name,
                "sha256": _digest_of(speech_manifest),
            }
        ),
        "registered": {
            "claims": claims,
            "repeats": repeats,
            "arms": arms,
            "planned_calls": claims * repeats * arms,
            "request_cap": request_cap,
            "wall_clock_seconds": AUDIO_COST_METERING_WALL_CLOCK_SECONDS,
            # Both retry knobs, named apart, because "재시도 0" means a
            # different number at each layer and a single field would have to
            # pick one and mislead about the other.
            "sdk_max_retries": AUDIO_COST_METERING_SDK_RETRIES,
            "failure_budget": AUDIO_COST_METERING_FAILURE_BUDGET,
        },
        "what_this_is_not": (
            "This block says what the run was registered to do. Whether it "
            "did it is the ledger's answer, not this one -- read it with "
            "scripts/verify_audio_metering_run.py."
        ),
    }


def build_report(
    *,
    identity: dict[str, Any],
    measured: bool,
    repeats: int,
    result: dict[str, Any],
    speech: Optional[SpeechCorpus] = None,
    cost: Optional[Mapping[str, Any]] = None,
    metering: Optional[Mapping[str, Any]] = None,
) -> dict[str, Any]:
    calls = result["calls"]
    model_calls = sum(int(call["api_call_count"]) for call in calls)
    # Built here only when the caller has nothing better -- an unmetered run,
    # or a test calling this function directly. ``main`` builds it from the
    # ledger and passes it in, because a receipt is a fact about rows this
    # function cannot see.
    if cost is not None:
        cost_block = dict(cost)
    else:
        table, table_note = _price_table_or_none()
        cost_block = cost_section(
            identity=identity,
            measured=measured,
            model_calls=model_calls,
            price_table=table,
            notes=[table_note] if table_note else (),
        )
    # Execution order, not alphabetical: which arm went first is a fact about
    # the run, and "observation, production" would misdescribe an interleave
    # that always puts the control first.
    arms_present = list(dict.fromkeys(_arm_of(call) for call in calls))

    # The corpus that actually ran, not the module globals. Reporting the tone
    # corpus's counts beside a speech run's calls would be a mislabel of
    # exactly the kind this whole file exists to stop.
    report_claims: Sequence[Claim] = speech.claims if speech else CLAIMS
    clip_dicts = (
        [clip.to_dict() for clip in speech.clips]
        if speech
        else [clip.to_dict() for clip in CLIPS]
    )
    corpus_name = "speech" if speech else "tones"

    control_calls = [c for c in calls if _arm_of(c) == "production"] or list(calls)
    report = {
        "what_this_measures": (
            "Whether the audio sub-judge hears words. The clips are "
            "synthesised speech with a known transcript, and the criteria come "
            "in matched true/false pairs on the same clip, so guessing scores "
            "50%. Synthesised speech is harder to follow than a human voice: a "
            "pass is strong evidence, a failure is weak. This is a different "
            "question from the tone corpus and its numbers are not comparable."
            if speech
            else
            "Whether the audio sub-judge's verdict is correct, on clips whose "
            "contents are known by construction. The repeat runs measured "
            f"consistency ({REPEAT_FLIP_RATE_PCT}% of audio verdict pairs "
            f"disagree, against {REPEAT_TEXT_FLIP_RATE_PCT}% on text). "
            "Consistency is not correctness and neither implies the other."
        ),
        "corpus": corpus_name,
        "measured": measured,
        # Null on a run that finished. When it is not null the counts below
        # are a partial run's, and a reader must not compare them with a
        # complete one as though the design had been the same.
        "stopped": result.get("stopped"),
        "calls_planned": result.get("planned_calls"),
        "pins": {
            **identity,
            "clip_sample_rate_hz": (
                speech.clips[0].sample_rate_hz
                if speech and speech.clips
                else CLIP_SAMPLE_RATE_HZ
            ),
            "grader_resample_rate_hz": AUDIO_SAMPLE_RATE_HZ,
            "repeats": repeats,
            "claims": len(report_claims),
            "clips": len(clip_dicts),
            "true_claims": sum(1 for c in report_claims if c.holds),
            "false_claims": sum(1 for c in report_claims if not c.holds),
            "prompt_arms": arms_present,
        },
        "clips": clip_dicts,
        "clip_sha256": result["clip_sha256"],
        "claims": [claim.to_dict() for claim in report_claims],
        "calls": calls,
        # Always the production prompt, so this number keeps meaning what it
        # meant before there was a second arm: how the *grader* behaves. The
        # alternative prompt's figures live under "arms" and are never folded
        # in, because averaging the two would describe a prompt nothing runs.
        "accuracy": summarise(control_calls, claims=report_claims),
        "cost": cost_block,
    }

    delivery = delivery_section(
        calls, measured=measured, durations=speech.durations if speech else None
    )
    if delivery is not None:
        report["delivery"] = delivery

    # Only on the metering trial. An accuracy run has no registered ceiling,
    # no pinned price table and no reason to carry an empty block saying so.
    if metering is not None:
        report["metering"] = dict(metering)

    if speech is not None:
        # What was heard, and what it would and would not mean. Carried in the
        # report rather than left in the write-up, because the number and the
        # caveat get copied separately otherwise.
        #
        # Passes over the corpus is repeats x arms, but it is taken from the
        # same planned-call number the report prints rather than recomputed,
        # so the estimate and the plan cannot disagree.
        planned = result.get("planned_calls") or 0
        passes = planned // len(speech.claims) if speech.claims else 0
        seconds_sent = round(speech.seconds_per_pass * passes, 4)
        report["speech_set"] = {
            "manifest": speech.manifest_path.name,
            "provenance": speech.provenance,
            "encoder": speech.encoder,
            "limits": speech.limits,
            "total_seconds": speech.total_seconds,
            "audio_seconds_per_pass": speech.seconds_per_pass,
            "audio_seconds_sent": seconds_sent,
            # 328 saw exactly 10.00 audio tokens per second of clip. Written
            # down before the run so that a delivery failure is checkable
            # against a prediction rather than explained after the fact.
            "expected_audio_tokens": round(
                AUDIO_TOKENS_PER_SECOND * seconds_sent
            ),
            "expected_audio_tokens_basis": (
                f"{AUDIO_TOKENS_PER_SECOND:.2f} tokens/s x "
                f"{speech.seconds_per_pass} s per pass x {passes} passes "
                f"(repeats x arms) = {seconds_sent} s, from run 34008840627. "
                f"The corpus is {speech.total_seconds} s long, but a pass "
                f"sends more than that: every call carries the clip its "
                f"criterion is about, and {len(speech.claims)} criteria share "
                f"{len(speech.clips)} clips. A measured total outside +/-10% "
                f"of this is itself a finding: the audio was delivered "
                f"differently, or billing changed."
            ),
        }

    if len(arms_present) > 1:
        report["arms"] = {
            arm: summarise(
                [c for c in calls if _arm_of(c) == arm], claims=report_claims
            )
            for arm in arms_present
        }
        report["arm_comparison"] = compare_arms(calls, claims=report_claims)
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
        "--speech-set",
        type=Path,
        default=None,
        help=(
            "Measure the pinned speech set instead of the tone corpus. Takes "
            "the path to a published manifest.json. The clips themselves are "
            "not committed -- they are GPL-3.0-or-later output and arrive as "
            "a CI artifact -- so --speech-clips must point at the downloaded "
            "directory. Every clip's digest is checked against the manifest "
            "before a single call goes out."
        ),
    )
    parser.add_argument(
        "--speech-clips",
        type=Path,
        default=None,
        help=(
            "Directory holding the .sent.wav files the manifest names. "
            "Required with --speech-set."
        ),
    )
    parser.add_argument(
        "--expect-grader-pin",
        type=Path,
        default=None,
        help=(
            "Path to the pre-registration this run belongs to. Its grader "
            "fingerprint is compared against the one this checkout computes, "
            "and a mismatch stops the run before a single call goes out."
        ),
    )
    parser.add_argument(
        "--speech-prompt-ab",
        type=Path,
        default=None,
        help=(
            "Run the speech set as a two-arm prompt comparison, under the "
            "pre-registration at this path. The document must declare a "
            "diagnostic-kind row naming one of the registered two-arm "
            "comparisons -- which is also what decides which alternative "
            "header goes out -- and must pin the grader fingerprint, which "
            "is then checked exactly as --expect-grader-pin checks it. A "
            "narrowed registration additionally fixes its own claim list and "
            "repeat count in the document, and a dispatch that disagrees "
            "with either is refused rather than corrected. This does not "
            "relax the single-arm rule the published speech run was "
            "registered under: these are different, separately registered "
            "runs, and --prompt-arm still cannot reach any of them."
        ),
    )
    parser.add_argument(
        "--metering-run",
        type=Path,
        default=None,
        help=(
            "Run the cost-metering trial under the pre-registration at this "
            "path. The document must declare the 'audio-cost-metering' "
            "diagnostic kind, fix exactly two claims, and pin both the "
            "grader fingerprint and the price-table fingerprint; a dispatch "
            "that disagrees with any of them is refused rather than "
            "corrected. One production arm, one repeat, SDK retries off so "
            "one ledger row is one HTTP request, and --cost-ledger is "
            "required: the run exists to produce a cost record, and one that "
            "cannot write it has nothing to report. Mutually exclusive with "
            "--speech-prompt-ab, which asks a different question."
        ),
    )
    parser.add_argument(
        "--cost-ledger",
        type=Path,
        default=None,
        help=(
            "Meter this run into the sqlite cost ledger at this path, through "
            "the same recorder every graded run uses. Without it the calls go "
            "out unmetered and the report says so -- which is what 337 did, "
            "and why nobody could say afterwards what its ten calls cost. The "
            "file is appended to, not replaced: an existing ledger's rows are "
            "kept and this run is numbered after them."
        ),
    )
    parser.add_argument(
        "--cost-ledger-out",
        type=Path,
        default=None,
        help=(
            "Export the ledger as JSONL here. This is the publishable half -- "
            "the sqlite file is a local working copy and is gitignored -- and "
            "its sha256 goes in the report so the two can be checked against "
            "each other. Defaults to the --cost-ledger path with a .jsonl "
            "suffix."
        ),
    )
    parser.add_argument(
        "--price-table",
        type=Path,
        default=None,
        help=(
            "Price the ledger rows with this table instead of the committed "
            "one. The digest of whichever file is used is recorded in the "
            "report. A model the table has no rate for stays unpriced: the "
            "cost comes out null, never zero."
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
    if (args.speech_set is None) != (args.speech_clips is None):
        parser.error("--speech-set and --speech-clips go together")
    if args.cost_ledger_out is not None and args.cost_ledger is None:
        parser.error(
            "--cost-ledger-out names where to export a ledger this run would "
            "not have; add --cost-ledger, or drop both and accept an "
            "unmetered run"
        )
    if args.speech_prompt_ab is not None and args.speech_set is None:
        parser.error(
            "--speech-prompt-ab compares two prompts on the pinned speech "
            "set; without --speech-set there is no speech to compare them on"
        )
    if args.metering_run is not None:
        if args.speech_prompt_ab is not None:
            parser.error(
                "--metering-run and --speech-prompt-ab are two different "
                "diagnostics with two different documents. Running them "
                "together would file one set of calls against both, and "
                "neither result would be the one its document registered"
            )
        if args.speech_set is None:
            parser.error(
                "--metering-run sends the pinned speech clips, so it needs "
                "--speech-set and --speech-clips; there is no synthetic "
                "audio to meter without them"
            )
        if args.cost_ledger is None:
            # The one place a missing ledger is fatal rather than a warning.
            # Elsewhere an unmetered run still answers its question and says
            # in its report that it was not metered. Here the ledger *is* the
            # question, and a run without one would spend money to produce a
            # report whose only finding is that nobody was writing anything
            # down -- which is 337, again, at 337's price.
            parser.error(
                "--metering-run needs --cost-ledger. The whole result of "
                "this run is the ledger it writes; without one it buys "
                "audio calls to answer a question it then cannot answer"
            )

    # The document the grader fingerprint is checked against. Two flags can
    # name it, so it is resolved to one variable before the check rather than
    # the check being written twice.
    pin_doc: Optional[Path] = args.expect_grader_pin

    # Which alternative header the speech arm would send, and what it is
    # called. Defaulted here and overwritten only by a registration, so the
    # single-arm speech path keeps the header 330 shipped with.
    header_name = "SPEECH_OBSERVATION_HEADER"
    speech_observation_header = SPEECH_OBSERVATION_HEADER
    request_cap: Optional[int] = None

    #: Set by --metering-run, read where the client and the perception object
    #: are built. Kept as one flag rather than three settings threaded
    #: separately, so "this is the metering trial" is decided once, at the
    #: document, and everything downstream is that decision applied.
    metering = False
    price_table_pin: Optional[str] = None

    #: Set by a document whose kind is in :data:`SPEECH_LEDGERED_KINDS`, and
    #: read at the same two places ``metering`` is. Separate from ``metering``
    #: because the questions are different -- this run is an accuracy pilot
    #: and writes no metering section -- but the request discipline is the
    #: same, and giving it its own flag is what stops "no hidden retries"
    #: from being a claim the report makes about a setting it did not apply.
    ledgered = False

    speech: Optional[SpeechCorpus] = None
    if args.speech_set is not None:
        try:
            speech = load_speech_corpus(args.speech_set, args.speech_clips)
        except (OSError, ValueError, KeyError) as exc:
            # Exit 3, like an unreadable identity: a run that cannot say which
            # audio it sent has nothing to report, and the digest check is the
            # only thing standing between "measured the pinned set" and
            # "measured whatever was in that folder".
            print(f"::error::{exc}", file=sys.stderr)
            return 3
        if args.prompt_arm != "production":
            # 330 pre-registers one arm. Two questions in one run is what made
            # 328 unable to answer either.
            parser.error(
                "the speech set is pre-registered as a single production arm; "
                "--prompt-arm would make it a different, unregistered run"
            )
        if args.speech_prompt_ab is not None:
            # That different, unregistered run, made registered. The block
            # above stays exactly as it was -- this is a second door with its
            # own document, not the same door with the lock taken off. The
            # arms are set here and not chosen on the command line, so
            # "which prompts ran" is a property of the pre-registration.
            try:
                kind = diagnostic_kind_stated_in(args.speech_prompt_ab)
            except (OSError, ValueError) as exc:
                print(f"::error::{exc}", file=sys.stderr)
                return 3
            if kind not in SPEECH_TWO_ARM_REGISTRATIONS:
                known = ", ".join(sorted(SPEECH_TWO_ARM_REGISTRATIONS))
                print(
                    f"::error::{args.speech_prompt_ab.name} registers "
                    f"'{kind}', which is not a two-arm speech comparison. A "
                    f"document that registered some other diagnostic has not "
                    f"agreed to this one. Known: {known}.",
                    file=sys.stderr,
                )
                return 3
            header_name, speech_observation_header = (
                SPEECH_TWO_ARM_REGISTRATIONS[kind]
            )
            arms = PROMPT_ARMS
            if pin_doc is None:
                pin_doc = args.speech_prompt_ab
            elif pin_doc != args.speech_prompt_ab:
                parser.error(
                    "--expect-grader-pin and --speech-prompt-ab name "
                    "different documents; the run would be held to one "
                    "document's fingerprint while filed under another's"
                )

            # A narrowed registration fixes its own sample and its own repeat
            # count. Both are read out of the document and neither is
            # silently applied over what was dispatched: a mismatch is a
            # dispatch that does not match its plan, and correcting it here
            # would hide that.
            registered_repeats = SPEECH_NARROWED_KINDS.get(kind)
            if registered_repeats is None:
                if _PILOT_CLAIMS_ROW.search(
                    args.speech_prompt_ab.read_text(encoding="utf-8")
                ):
                    print(
                        f"::error::{args.speech_prompt_ab.name} registers "
                        f"'{kind}', which runs the whole manifest, but it "
                        f"carries a claim row. A document that names a "
                        f"subset and a run that ignores it disagree about "
                        f"what was measured.",
                        file=sys.stderr,
                    )
                    return 3
            else:
                if args.repeats != registered_repeats:
                    print(
                        f"::error::{args.speech_prompt_ab.name} registers "
                        f"{registered_repeats} repeat(s); this dispatch asks "
                        f"for {args.repeats}. Dispatch it as registered.",
                        file=sys.stderr,
                    )
                    return 3
                try:
                    claim_ids = pilot_claims_stated_in(args.speech_prompt_ab)
                    speech = narrow_speech_corpus(speech, claim_ids)
                except (OSError, ValueError, KeyError) as exc:
                    print(f"::error::{exc}", file=sys.stderr)
                    return 3

            # Arithmetic, before the client exists. The ceiling bounds
            # requests and the plan is counted in calls, so this cannot prove
            # the run fits -- it can only catch a plan that already does not.
            request_cap = SPEECH_REQUEST_CAPS.get(kind)
            planned = len(speech.claims) * args.repeats * len(arms)
            if request_cap is not None and planned > request_cap:
                print(
                    f"::error::{args.speech_prompt_ab.name} plans {planned} "
                    f"call(s) against a ceiling of {request_cap} request(s). "
                    f"The plan does not fit the ceiling it registered.",
                    file=sys.stderr,
                )
                return 3

            # The candidate this document says it is sending, checked against
            # the string that is actually registered for its kind. 337 wrote
            # its candidate's digest into a table and nothing read it, so the
            # row was a claim; here a document that names the wrong header
            # stops the run instead of buying calls under a prompt its
            # reviewers did not read.
            try:
                candidate_pin = candidate_pin_stated_in(args.speech_prompt_ab)
            except (OSError, ValueError) as exc:
                print(f"::error::{exc}", file=sys.stderr)
                return 3
            if candidate_pin is not None:
                actual = hashlib.sha256(
                    speech_observation_header.encode("utf-8")
                ).hexdigest()
                if candidate_pin != actual:
                    print(
                        f"::error::{args.speech_prompt_ab.name} pins candidate "
                        f"header {candidate_pin[:16]}..., but '{kind}' is "
                        f"registered to send {header_name}, which is "
                        f"{actual[:16]}.... The document and the code disagree "
                        f"about which prompt this run sends.",
                        file=sys.stderr,
                    )
                    return 3

            # Kinds whose approval is written as a request count run under the
            # metering trial's discipline: no SDK retries, no second attempt,
            # and a ledger. See :data:`SPEECH_LEDGERED_KINDS`.
            if kind in SPEECH_LEDGERED_KINDS:
                if args.cost_ledger is None:
                    print(
                        f"::error::{args.speech_prompt_ab.name} registers "
                        f"'{kind}', which runs with SDK retries pinned to "
                        f"zero so that one request is one ledger row. Without "
                        f"--cost-ledger there is no row, and the run cannot "
                        f"say afterwards how many requests it sent -- which "
                        f"is the accounting 337 could not produce.",
                        file=sys.stderr,
                    )
                    return 3
                ledgered = True

        if args.metering_run is not None:
            # A third door, with its own document and its own question. It
            # reuses every check the block above uses -- kind, claim list,
            # repeat count, grader pin -- because the checks are what make a
            # dispatch match its plan, and a new diagnostic that re-implements
            # them loosely is a new diagnostic nobody has to agree with.
            #
            # What it adds is the price-table pin. Nothing above needs one:
            # a prompt comparison is unaffected by what the rates say. This
            # run's entire output is a cost record, so the table those costs
            # would be looked up in is part of what it is being held to.
            try:
                kind = diagnostic_kind_stated_in(args.metering_run)
            except (OSError, ValueError) as exc:
                print(f"::error::{exc}", file=sys.stderr)
                return 3
            if kind != AUDIO_COST_METERING_KIND:
                print(
                    f"::error::{args.metering_run.name} registers '{kind}', "
                    f"not '{AUDIO_COST_METERING_KIND}'. A document that "
                    f"registered some other diagnostic has not agreed to this "
                    f"one, and this run would be filed under its name.",
                    file=sys.stderr,
                )
                return 3
            if pin_doc is None:
                pin_doc = args.metering_run
            elif pin_doc != args.metering_run:
                parser.error(
                    "--expect-grader-pin and --metering-run name different "
                    "documents; the run would be held to one document's "
                    "fingerprint while filed under another's"
                )

            registered_repeats = SPEECH_NARROWED_KINDS[AUDIO_COST_METERING_KIND]
            if args.repeats != registered_repeats:
                print(
                    f"::error::{args.metering_run.name} registers "
                    f"{registered_repeats} repeat(s); this dispatch asks for "
                    f"{args.repeats}. Dispatch it as registered.",
                    file=sys.stderr,
                )
                return 3
            try:
                claim_ids = pilot_claims_stated_in(args.metering_run)
                price_table_pin = price_table_pin_stated_in(args.metering_run)
                manifest_pin = manifest_pin_stated_in(args.metering_run)
            except (OSError, ValueError) as exc:
                print(f"::error::{exc}", file=sys.stderr)
                return 3
            local_manifest = _digest_of(args.speech_set)
            if local_manifest != manifest_pin:
                print(
                    f"::error::this is not the speech manifest "
                    f"{args.metering_run.name} pins. It names {manifest_pin}, "
                    f"{args.speech_set} hashes to {local_manifest}. The clips "
                    f"would still check out -- against this manifest's own "
                    f"digests, which is the check a substituted corpus "
                    f"passes. Point --speech-set at the pinned manifest, or "
                    f"re-pin the document and say what changed.",
                    file=sys.stderr,
                )
                return 3
            if len(claim_ids) != AUDIO_COST_METERING_CLAIMS:
                # Two, exactly. Not "at most": one row cannot show that the
                # second was not the first counted twice, and three would buy
                # a call to learn nothing the second did not already show.
                print(
                    f"::error::{args.metering_run.name} fixes "
                    f"{len(claim_ids)} claim(s); this diagnostic is "
                    f"registered for exactly {AUDIO_COST_METERING_CLAIMS}. "
                    f"One row cannot tell a second request from the first "
                    f"one counted twice, and a third buys a call that shows "
                    f"nothing the second did not.",
                    file=sys.stderr,
                )
                return 3
            try:
                speech = narrow_speech_corpus(speech, claim_ids)
            except (OSError, ValueError, KeyError) as exc:
                print(f"::error::{exc}", file=sys.stderr)
                return 3

            # Checked here, before the client, for the same reason the grader
            # pin is: after the run the table can be put back and nothing in
            # the report would say it had moved.
            try:
                local_table = load_receipt_price_table(args.price_table)
            except (OSError, ValueError, KeyError) as exc:
                print(
                    f"::error::{args.metering_run.name} pins a price table "
                    f"fingerprint and this checkout cannot read the table to "
                    f"compare it ({type(exc).__name__}: {exc}).",
                    file=sys.stderr,
                )
                return 3
            if local_table.sha256 != price_table_pin:
                print(
                    f"::error::this is not the price table "
                    f"{args.metering_run.name} pins. It names "
                    f"{price_table_pin}, this checkout computes "
                    f"{local_table.sha256}. A rate was added, removed or "
                    f"edited since the document was written -- which changes "
                    f"what this run would report as its cost. Re-pin the "
                    f"document to the computed value and say what moved, or "
                    f"run against the table it names.",
                    file=sys.stderr,
                )
                return 3

            metering = True
            request_cap = SPEECH_REQUEST_CAPS[AUDIO_COST_METERING_KIND]
            planned = len(speech.claims) * args.repeats * len(arms)
            if planned > request_cap:
                print(
                    f"::error::{args.metering_run.name} plans {planned} "
                    f"call(s) against a ceiling of {request_cap} request(s). "
                    f"The plan does not fit the ceiling it registered.",
                    file=sys.stderr,
                )
                return 3

    # Before the identity, before the client, before anything is bought: is
    # the grader this checkout would use the one the pre-registration names?
    # The fingerprint is what makes "we measured the grader in §2" a checkable
    # sentence, and it covers files this workstream does not own -- so it
    # moves without anyone here touching it. Finding that at dispatch time
    # costs a stopped run; finding it afterwards costs the run's meaning.
    if pin_doc is not None:
        try:
            pinned = grader_pin_stated_in(pin_doc)
            computed = grader_source_hash(args.config)
        except (OSError, ValueError, KeyError) as exc:
            print(f"::error::{exc}", file=sys.stderr)
            return 3
        if pinned != computed:
            print(
                f"::error::this is not the grader "
                f"{pin_doc.name} pins. It names "
                f"{pinned}, this checkout computes {computed}. Something the "
                f"fingerprint covers moved -- core/**, step8_grade.py, the "
                f"grade schema, the requirements closure, the prompt template "
                f"or {args.config.name}. Re-pin the document to the computed "
                f"value and record what moved, or run this on the grader it "
                f"names. Filing the result under a fingerprint that was not "
                f"the one that ran is the one option that is not available.",
                file=sys.stderr,
            )
            return 3

    try:
        identity = pinned_identity(args.config)
    except ValueError as exc:
        # Exit 3, not a traceback. Whatever this would have measured, it was
        # not the audio path the repeat runs used, and a run that cannot say
        # which model it is describing has nothing to report.
        print(f"::error::{exc}", file=sys.stderr)
        return 3
    # Recorded, not just checked. After the run this string stops being a
    # promise and becomes the record of which grader produced these numbers,
    # and a record that lives only in a markdown file someone typed is the
    # thing this whole check exists to replace.
    identity["grader_source_sha256"] = grader_source_hash(args.config)
    # Which alternative prompt this run put opposite production, recorded the
    # same way and for the same reason. The per-call ``prompt_sha256`` already
    # says what went out, but nothing in the report says which *named* header
    # that hash is, so a reader could not check the run against the header the
    # pre-registration pinned. Only stamped when a second arm actually ran:
    # a fingerprint for a prompt nothing sent is a fact about this file, not
    # about the run.
    observation_header = (
        speech_observation_header if speech else OBSERVATION_HEADER
    )
    if len(arms) > 1:
        identity["observation_header_sha256"] = hashlib.sha256(
            observation_header.encode("utf-8")
        ).hexdigest()
        # The name next to the hash. Without it a reader has to guess which
        # of two headers a digest belongs to, and the whole point of two
        # candidates is that they are easy to confuse.
        identity["observation_header_name"] = (
            header_name if speech else "OBSERVATION_HEADER"
        )
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

    # ── the meter ───────────────────────────────────────────────────────
    #
    # Opened before the client, so the thing that records a call is already in
    # place when the first one goes out. 337 put ten paid calls on the wire
    # with nothing between them and the network, and the cost block in its
    # report was four constants this file wrote afterwards. None of them had
    # been near a ledger, which is why that run can be described but not
    # audited -- and why the fix is to reach for the recorder every graded run
    # already uses rather than to write a better constant.
    #
    # A ledger that will not open is a warning and not an exit. A diagnostic
    # that refuses to run because its bookkeeping file is unwritable has
    # turned a bookkeeping problem into a lost run. What it must never do is
    # go quiet: the failure is printed here and written into the report, where
    # `receipt: null` and a sentence saying why take the place of a total.
    run_kind = "rehearsal" if args.dry_run else "measured"
    recorder: Optional[Any] = None
    cost_notes: list[str] = []
    ledger_out: Optional[Path] = args.cost_ledger_out
    if args.cost_ledger is not None:
        recorder, ledger_note = open_cost_recorder(
            args.cost_ledger,
            run_id=f"{COST_RUN_ID_PREFIX}-{run_kind}",
            continue_rounds=True,
            price_table_path=args.price_table,
        )
        if ledger_note:
            print(f"::warning::cost ledger: {ledger_note}", file=sys.stderr)
            cost_notes.append(ledger_note)
        if recorder is None:
            cost_notes.append(
                f"The cost ledger at {args.cost_ledger} could not be opened, "
                f"so these calls went out unmetered and there is no receipt "
                f"for them."
            )
        else:
            # One ledger, one kind of run. A rehearsal row and a paid row
            # differ in nothing a reader sees except `provider`, and a file
            # holding both has a total that is an invoice plus a dress
            # rehearsal. Refused rather than partitioned, because a reader who
            # has to remember to filter is a reader who will one day not.
            foreign = ledger_record_kinds(recorder.ledger) - {run_kind}
            if foreign:
                recorder.ledger.close()
                print(
                    f"::error::{args.cost_ledger} already holds "
                    f"{', '.join(sorted(foreign))} rows and this is a "
                    f"{run_kind} run. Mixing the two gives that file a total "
                    f"that is part invoice and part dress rehearsal. Point "
                    f"--cost-ledger at a separate file for this run; the "
                    f"existing rows are left exactly as they are.",
                    file=sys.stderr,
                )
                return 3
        if ledger_out is None:
            ledger_out = args.cost_ledger.with_suffix(".jsonl")
    elif not args.dry_run:
        unmetered = (
            "This run was dispatched without --cost-ledger, so its calls were "
            "not metered and no receipt exists for them. The call counts "
            "below are counts; they are not a record of spend."
        )
        print(f"::warning::{unmetered}", file=sys.stderr)
        cost_notes.append(unmetered)

    managed = None
    if args.dry_run:
        client: Any = TruthfulStub(speech.claims if speech else CLAIMS)
    else:
        from core.azure_ai_clients import AzureAIWorkload  # noqa: E402
        from core.llm_client import create_typed_azure_client  # noqa: E402

        managed = create_typed_azure_client(
            AzureAIWorkload.GRADER,
            identity["audio_deployment"],
            # Left unset on every other path, which means the openai default
            # of two applies and one ``create`` can be three HTTP requests.
            # The meter wraps ``create``, so those three would share one
            # ledger row. For the run whose finding is "the rows match the
            # requests" that is not a rounding error, it is the finding being
            # wrong. See :data:`AUDIO_COST_METERING_SDK_RETRIES`.
            max_retries=(
                AUDIO_COST_METERING_SDK_RETRIES
                if (metering or ledgered)
                else None
            ),
        )
        client = managed.client

    if recorder is not None:
        # Inside WireClient, not outside it. WireClient rewrites the request
        # before sending it -- that is how the observation arm gets its header
        # -- and only then calls ``self._inner.chat.completions.create``. A
        # meter wrapped around the outside would digest a payload that was
        # never sent, and ``request_sha256`` would be a fingerprint of
        # something no provider ever saw. The order of these two lines is the
        # difference between a ledger row that can be matched to a request and
        # one that only looks like it can.
        client = recorder.meter(
            client,
            provider=STUB_PROVIDER if args.dry_run else "azure",
            model=identity["audio_deployment"],
            # Pinned, so these land in the perception component of the receipt
            # regardless of the scope they run inside. They are perception
            # reads: the sub-judge listening to a clip.
            stage=STAGE_PERCEPTION,
            deployment=identity["audio_deployment"],
        )

    # Always wrapped, even for a single production arm: the delivery evidence
    # is the reason this run exists, and making it conditional would mean the
    # cheap runs are the ones that cannot say whether the audio arrived.
    wire = WireClient(
        client,
        arm=arms[0],
        observation_header=observation_header,
        request_cap=request_cap,
    )

    # Set on the way out of the block below, read after it. The cap is not an
    # error to return from inside a ``try`` whose ``finally`` still has to
    # close the books.
    result: Optional[dict[str, Any]] = None
    cap_failure: Optional[str] = None
    cost: Optional[dict[str, Any]] = None
    try:
        perception = AudioPerception(
            client=wire,
            deployment=identity["audio_deployment"],
            call_cap=identity["audio_call_cap_per_task"],
            trim_seconds=identity["audio_clip_seconds"],
            # One attempt per criterion on the metering trial. Note that the
            # "no retries" setting is 1 and not 0: the budget is compared
            # with ``>=`` before the first request, so zero would refuse
            # every call and the run would send nothing.
            failure_budget=(
                AUDIO_COST_METERING_FAILURE_BUDGET
                if (metering or ledgered)
                else AUDIO_FAILURE_BUDGET
            ),
        )
        # One task, one stage, for everything inside. Without a scope in
        # place the metered client passes calls straight through unrecorded
        # -- deliberately, so that out-of-band work cannot be filed under
        # somebody's task -- which means forgetting this line does not fail
        # loudly. It produces an empty ledger and a report that says so.
        attribution = (
            recorder.attributed(task_id=COST_TASK_ID, stage=STAGE_GRADING)
            if recorder is not None
            else contextlib.nullcontext()
        )
        with tempfile.TemporaryDirectory(prefix="audio-accuracy-") as tmp:
            with attribution:
                result = run_measurement(
                    perception=perception,
                    clip_dir=Path(tmp),
                    repeats=args.repeats,
                    claims=speech.claims if speech else CLAIMS,
                    on_call=progress,
                    arms=arms,
                    wire=wire,
                    prerendered=speech,
                    # Only the speech corpus. The tone results are published
                    # and turning these on for that path would change a
                    # methodology after its numbers were reported.
                    stop_rules=stop_rules_for(metering=metering, speech=speech),
                )
    except RequestCapReached as exc:
        # A backstop, not the normal path. ``run_measurement`` catches this
        # around the call it wraps and records it as a stop, so a ceiling hit
        # during the measurement keeps the requests already paid for. Reaching
        # here means the ceiling fired somewhere outside that loop, where
        # there is no partial record to keep -- so no report is written, and
        # the count goes on the error line below instead. The ledger is a
        # separate question and is still exported: those requests went out.
        cap_failure = str(exc)
    finally:
        if managed is not None:
            managed.close()
        # In the ``finally``, so it runs on the paths that end badly too. A
        # run stopped by its ceiling, or one whose replies would not parse,
        # has still bought every request it sent. Exporting only on success
        # would delete the record of exactly the spend nobody planned for --
        # which is the same mistake as not recording it in the first place,
        # arrived at from the other end.
        cost = close_cost_record(
            recorder,
            identity=identity,
            measured=not args.dry_run,
            model_calls=(
                sum(int(call["api_call_count"]) for call in result["calls"])
                if result is not None
                # No result to count judge calls from. Requests are the next
                # best thing and are not the same number -- one judge call can
                # retry -- so this is an approximation on a path that has
                # already gone wrong, and the ledger rows beside it are exact.
                else max(0, wire.requests - (1 if cap_failure else 0))
            ),
            export_to=ledger_out,
            price_table_path=args.price_table,
            notes=cost_notes,
        )

    if cap_failure is not None:
        where = (cost or {}).get("ledger") or {}
        print(
            f"::error::{cap_failure}. Sent {wire.requests - 1} request(s) "
            f"before stopping; the ceiling was {request_cap}. This fired "
            f"outside the measurement loop, so no report was written. The "
            f"requests that did go out are recorded"
            + (f" in {where['path']}" if where.get("path") else " nowhere")
            + ". Record the cause and re-plan -- raising the ceiling to fit "
            "the run it just refused is the one repair that is not available.",
            file=sys.stderr,
        )
        return 3
    assert result is not None  # the only other way out of the block is a raise

    report = build_report(
        identity=identity,
        measured=not args.dry_run,
        repeats=args.repeats,
        result=result,
        speech=speech,
        cost=cost,
        metering=(
            metering_section(
                document=args.metering_run,
                config_path=args.config,
                speech_manifest=args.speech_set,
                claims=len(speech.claims) if speech else 0,
                repeats=args.repeats,
                arms=len(arms),
                request_cap=request_cap,
            )
            if metering
            else None
        ),
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

    stopped = result.get("stopped")
    if stopped is not None and stopped.get("rule") == "request_cap":
        # Checked before the unanswered-claims exit below, which would also
        # fire here and would name the wrong thing: claims are missing
        # *because* the ceiling stopped the run, and a run that reports the
        # symptom leaves the reader to guess the cause.
        #
        # Non-zero even though the report was written. The file is worth
        # keeping -- the requests in it were paid for -- but it is a partial
        # run under a filename that a whole one also uses, and a green exit
        # is how the two stop being told apart.
        print(
            f"::error::the pre-registered request ceiling of "
            f"{stopped.get('limit')} was reached after "
            f"{stopped.get('after_calls')} call(s); the report above is a "
            f"partial run. Record the cause and re-plan -- raising the "
            f"ceiling to fit the run it just refused is the one repair that "
            f"is not available.",
            file=sys.stderr,
        )
        return 3

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
