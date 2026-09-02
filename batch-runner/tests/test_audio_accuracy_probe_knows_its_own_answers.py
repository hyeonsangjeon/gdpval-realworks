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
``pass`` to all twelve criteria scores 50% accuracy on this balanced corpus,
and the test that matters is the one asserting its discrimination is **zero**.
"""

from __future__ import annotations

import io
import json
import math
import struct
import sys
import wave
from pathlib import Path
from typing import Sequence

import pytest

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


# --------------------------------------------------------------------------
# The criteria are balanced, paired, and free of accidental listening windows
# --------------------------------------------------------------------------


def test_corpus_is_balanced_and_paired() -> None:
    """Six true, six false, matched one-of-each on the same clip.

    Balance is what makes Youden's J readable; pairing is what makes the
    permutation null contain only corpora that could actually have existed.
    """
    assert sum(1 for c in probe.CLAIMS if c.holds) == 6
    assert sum(1 for c in probe.CLAIMS if not c.holds) == 6
    pairs: dict[str, list[probe.Claim]] = {}
    for claim in probe.CLAIMS:
        pairs.setdefault(claim.pair_id, []).append(claim)
    assert len(pairs) == 6
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

    Accuracy is 50% -- it got all six true claims right -- and that 50% is
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


def test_permutation_is_exhaustive_over_sixty_four_relabellings() -> None:
    result = probe.permute_within_pairs(_calls(lambda c: "pass" if c.holds else "fail"))
    assert result["pairs"] == 6
    assert result["assignments"] == 64


def test_the_best_possible_p_is_reported_and_is_worse_than_one_percent() -> None:
    """The design's own ceiling, published with the number rather than after it.

    Six pairs give 64 assignments, so nothing this experiment can produce
    reaches 0.01. Stating it here is the same discipline as
    ``is_informative: false`` on the repeat-variation interval: the reader is
    told what the measurement *cannot* support at the moment they are told
    what it found.
    """
    result = probe.permute_within_pairs(_calls(lambda c: "pass" if c.holds else "fail"))
    assert result["smallest_attainable_p"] == pytest.approx(1.0 / 64.0)
    assert result["p_one_sided"] == pytest.approx(1.0 / 64.0)
    assert result["smallest_attainable_p"] > 0.01
    assert result["smallest_attainable_p"] < 0.05


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
    """Every relabelling must leave the corpus balanced, and 64 of them exist.

    A free shuffle over twelve labels would build null corpora that could not
    have existed -- both criteria about the silent clip true at once -- and
    would enumerate C(12,6) = 924 of them, putting the p-floor at 1/924 and
    quietly claiming a resolution the design does not have. Two observable
    consequences pin the within-pair scheme: the assignment count is exactly
    64, and a perfect listener's p is exactly 1/64 rather than 1/924.

    The count also has to be 64 *including* degenerate answers -- if any
    relabelling produced an all-true corpus, J would be ``None`` there and the
    denominator would silently shrink.
    """
    for verdict_for in (
        lambda c: "pass" if c.holds else "fail",
        lambda c: "pass",
        lambda c: "fail" if c.holds else "pass",
    ):
        result = probe.permute_within_pairs(_calls(verdict_for))
        assert result["assignments"] == 64
        assert 1 <= result["at_least_observed"] <= 64
        assert result["p_one_sided"] == pytest.approx(
            result["at_least_observed"] / 64
        )


def test_the_perfect_and_inverted_ends_of_the_null_are_where_they_should_be() -> None:
    """One assignment beats a perfect listener; all 64 beat an inverted one."""
    perfect = probe.permute_within_pairs(
        _calls(lambda c: "pass" if c.holds else "fail")
    )
    assert perfect["at_least_observed"] == 1
    inverted = probe.permute_within_pairs(
        _calls(lambda c: "fail" if c.holds else "pass")
    )
    assert inverted["at_least_observed"] == 64
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
    # 12 calls went out to the stub and none of them were billed. A report
    # that said "billable_calls: 12" here is the figure someone copies.
    assert report["cost"]["model_calls"] == 12
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
    assert report["pins"]["claims"] == 12
    assert report["pins"]["true_claims"] == 6
    assert report["pins"]["false_claims"] == 6
    assert len(report["calls"]) == 12


def test_main_rejects_a_repeat_count_below_one() -> None:
    with pytest.raises(SystemExit):
        probe.main(["--dry-run", "--repeats", "0"])


def test_main_writes_the_report_where_it_is_told(tmp_path: Path) -> None:
    out = tmp_path / "nested" / "report.json"
    assert probe.main(["--dry-run", "--repeats", "1", "--quiet", "--out", str(out)]) == 0
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["accuracy"]["overall"]["calls"] == 12


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
