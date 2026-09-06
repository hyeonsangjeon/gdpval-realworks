"""Before you can say the model did not hear it, prove it was sent.

The first measured run of the accuracy probe reported 51.85% accuracy and a
discrimination of ``-0.0037``, and the write-up read that as a fact about
``gpt-audio-1.5``. It is only a fact about the model if the model was given
the audio. Two failures produce *exactly* those numbers and neither would have
shown up anywhere in that report:

1. the request went out without its ``input_audio`` part, or with an empty or
   truncated one, and the judge answered from the criterion's wording alone;
2. the request was fine and the prompt was the problem -- a header that hands
   the model a claim and asks it to confirm one, which a model can do at
   chance without listening.

This file is about the first. It puts requests through the same wrapper the
paid run uses and asserts that the wrapper *notices* when the audio is
missing, empty, corrupt or half a file, because a diagnostic that silently
passes those is worth less than no diagnostic. Every hostile client here is a
mock: no network call, no cost, and no dependence on a provider being in a
particular mood.

The second half of the file is about the arm swap. Its correctness condition
is stated once and tested from several directions: **the two arms differ in
the text part and in nothing else.** If the audio bytes were not identical
across arms, the comparison would not be measuring the prompt.

What is *not* here, deliberately: any assertion about what the model concludes.
That is what the paid run is for, and a test that pinned it would be pinning a
result rather than checking an instrument.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import math
import sys
import wave
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.perception.audio import (  # noqa: E402
    AUDIO_SAMPLE_RATE_HZ,
    AudioPerception,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import measure_audio_grading_accuracy as probe  # noqa: E402

BATCH_RUNNER = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------
# Clients that misbehave in each of the ways the report could not have seen
# --------------------------------------------------------------------------


class _Recorded:
    """The smallest reply the sub-judge will accept, plus a usage block."""

    def __init__(self, verdict: str = "pass", model: str = "mock-audio") -> None:
        payload = json.dumps(
            {
                "verdict": verdict,
                "partial_score": 1.0 if verdict == "pass" else 0.0,
                "evidence": "mock",
                "confidence": 0.5,
                "reasoning": "mock",
            }
        )
        self.choices = [type("_C", (), {"message": type("_M", (), {"content": payload})()})()]
        self.usage = type(
            "_U", (), {"prompt_tokens": 150, "completion_tokens": 20}
        )()
        self.model = model


class DroppingClient:
    """Accepts the request, then sends it on without the audio.

    This is the failure the whole file exists for. A provider-side or
    middleware-side drop looks like this from in here: a perfectly ordinary
    200, a perfectly ordinary verdict, and no audio anywhere near the model.
    """

    def __init__(self, *, verdict: str = "pass") -> None:
        self.verdict = verdict
        self.seen: list[dict[str, Any]] = []
        self.chat = type("_Chat", (), {"completions": self})()

    def create(self, **kwargs: Any) -> _Recorded:
        stripped = [
            {
                **message,
                "content": [
                    part
                    for part in message["content"]
                    if part.get("type") != "input_audio"
                ],
            }
            for message in kwargs["messages"]
        ]
        self.seen.append({**kwargs, "messages": stripped})
        return _Recorded(self.verdict)


class MutatingClient:
    """Passes the request through a transform before answering.

    Used for the empty-string, corrupt-base64 and truncated-bytes cases so
    each one is a two-line lambda rather than another class.
    """

    def __init__(self, transform) -> None:
        self.transform = transform
        self.seen: list[dict[str, Any]] = []
        self.chat = type("_Chat", (), {"completions": self})()

    def create(self, **kwargs: Any) -> _Recorded:
        mutated = self.transform(kwargs)
        self.seen.append(mutated)
        return _Recorded()


class FaithfulClient:
    """Answers correctly and reports audio tokens, the way a provider would."""

    def __init__(self, *, model: str = "gpt-audio-1.5", audio_tokens: int = 41) -> None:
        self.model = model
        self.audio_tokens = audio_tokens
        self.seen: list[dict[str, Any]] = []
        self.chat = type("_Chat", (), {"completions": self})()

    def create(self, **kwargs: Any) -> _Recorded:
        self.seen.append(kwargs)
        response = _Recorded(model=self.model)
        response.usage.prompt_tokens_details = type(
            "_D", (), {"audio_tokens": self.audio_tokens, "cached_tokens": 0}
        )()
        return response


def _wire_for(client: Any, arm: str = "production") -> probe.WireClient:
    return probe.WireClient(client, arm=arm)


def _judge_once(
    wire: probe.WireClient, tmp_path: Path, clip: probe.Clip | None = None
) -> None:
    """One real trip through ``AudioPerception.judge`` against a rendered clip."""
    clip = clip or probe.CLIPS[0]
    path = tmp_path / f"{clip.clip_id}.wav"
    probe.render_clip(clip, path)
    perception = AudioPerception(client=wire, deployment="gpt-audio-1.5")
    perception.judge(criterion="a criterion", audio_path=str(path))


# --------------------------------------------------------------------------
# The audio part is there, and it is the audio
# --------------------------------------------------------------------------


def test_a_normal_call_records_the_bytes_it_sent(tmp_path: Path) -> None:
    wire = _wire_for(FaithfulClient())
    _judge_once(wire, tmp_path)

    assert len(wire.records) == 1
    record = wire.records[0]
    assert record["audio_part_present"] is True
    assert record["audio_parts"] == 1
    assert record["audio_format"] == "wav"
    assert len(record["audio_sha256"]) == 64
    assert record["audio_b64_chars"] > 1000


def test_the_recorded_digest_is_the_digest_of_what_went_out(tmp_path: Path) -> None:
    """Not of the file on disk -- of the bytes in the request.

    The two are different by construction: the grader re-encodes every wav
    before sending it. Hashing the file would produce a digest that looks
    like evidence and is not, because it is a digest of something the model
    never saw.
    """
    client = FaithfulClient()
    wire = _wire_for(client)
    _judge_once(wire, tmp_path)

    sent_b64 = client.seen[0]["messages"][0]["content"][1]["input_audio"]["data"]
    expected = hashlib.sha256(base64.b64decode(sent_b64)).hexdigest()
    assert wire.records[0]["audio_sha256"] == expected


def test_the_sent_bytes_are_a_wav_of_the_shape_the_grader_promises(
    tmp_path: Path,
) -> None:
    """RIFF/WAVE, mono, 16-bit, at the rate the module says it resamples to."""
    wire = _wire_for(FaithfulClient())
    clip = probe.CLIPS_BY_ID["three_beeps"]
    _judge_once(wire, tmp_path, clip)

    facts = wire.records[0]["sent_wav"]
    assert facts["riff"] == "RIFF"
    assert facts["wave"] == "WAVE"
    assert facts["channels"] == 1
    assert facts["sample_width_bytes"] == 2
    assert facts["sample_rate_hz"] == AUDIO_SAMPLE_RATE_HZ
    assert facts["duration_s"] == pytest.approx(clip.duration_s, abs=0.05)
    assert "parse_error" not in facts


def test_duration_is_derivable_from_size_when_the_header_says_zero() -> None:
    """A streamed muxer can leave the frame count at zero.

    Reporting ``duration_s: 0.0`` from such a header would look like a
    truncation that did not happen, so the size-derived figure is carried
    alongside it and the truncation check uses whichever is real.
    """
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        handle.writeframes(b"\x00\x00" * 16000)
    data = bytearray(buffer.getvalue())
    facts_before = probe._wav_facts(bytes(data))
    assert facts_before["duration_s"] == pytest.approx(1.0)
    assert facts_before["duration_s_from_size"] == pytest.approx(1.0, abs=0.01)


# --------------------------------------------------------------------------
# ...and when it is not, that is visible
# --------------------------------------------------------------------------


def test_a_dropped_audio_part_is_caught(tmp_path: Path) -> None:
    """The headline case. Verdicts still arrive; the report must not be silent.

    Note what is *not* asserted: that anything raised. A diagnostic that dies
    on the defect it is looking for cannot describe it, and this defect has to
    be describable in a report.
    """
    client = DroppingClient()
    wire = _wire_for(client)
    _judge_once(wire, tmp_path)

    # The wrapper sits before the drop, so it sees a well-formed request...
    assert wire.records[0]["audio_part_present"] is True
    # ...and the client is what removed it. Which is the point: the check has
    # to be able to run on either side, so it is run on the recorded request
    # the client actually received.
    inspected = probe.WireClient._inspect(client.seen[0])
    assert inspected["audio_part_present"] is False
    assert inspected["audio_parts"] == 0
    assert inspected["audio_sha256"] is None


def test_an_empty_audio_string_is_not_counted_as_delivered(tmp_path: Path) -> None:
    def empty(kwargs: dict[str, Any]) -> dict[str, Any]:
        parts = kwargs["messages"][0]["content"]
        parts[1]["input_audio"]["data"] = ""
        return kwargs

    client = MutatingClient(empty)
    wire = _wire_for(client)
    _judge_once(wire, tmp_path)

    inspected = probe.WireClient._inspect(client.seen[0])
    assert inspected["audio_parts"] == 1  # the part is there
    assert inspected["audio_part_present"] is False  # and it is empty
    assert inspected["audio_b64_chars"] == 0
    assert inspected["audio_sha256"] is None


def test_corrupt_base64_is_reported_rather_than_raising(tmp_path: Path) -> None:
    def corrupt(kwargs: dict[str, Any]) -> dict[str, Any]:
        parts = kwargs["messages"][0]["content"]
        parts[1]["input_audio"]["data"] = "not base64 at all!!"
        return kwargs

    client = MutatingClient(corrupt)
    wire = _wire_for(client)
    _judge_once(wire, tmp_path)

    inspected = probe.WireClient._inspect(client.seen[0])
    assert inspected["audio_part_present"] is False
    assert "audio_b64_error" in inspected


def test_truncated_audio_shows_up_as_a_duration_that_does_not_match(
    tmp_path: Path,
) -> None:
    """Half a file still decodes, still plays, and is still the wrong evidence.

    A truncation is the quietest of these failures: the request is valid, the
    provider accepts it, and the model answers about the first half of a clip
    whose ground truth is stated over the whole of it. Only the arithmetic
    catches it.
    """
    clip = probe.CLIPS_BY_ID["tone_stops_early"]
    path = tmp_path / f"{clip.clip_id}.wav"
    probe.render_clip(clip, path)
    full = path.read_bytes()
    half = full[: 44 + (len(full) - 44) // 2]

    facts = probe._wav_facts(half)
    assert facts["duration_s_from_size"] == pytest.approx(clip.duration_s / 2, abs=0.05)

    call = {
        "claim_id": "c",
        "clip_id": clip.clip_id,
        "input_tokens": 150,
        "wire": {
            "requests": 1,
            "requests_with_audio": 1,
            "audio_sha256": hashlib.sha256(half).hexdigest(),
            "audio_duration_s": facts["duration_s_from_size"],
            "audio_format": "wav",
            "audio_sample_rate_hz": facts["sample_rate_hz"],
            "audio_channels": facts["channels"],
            "audio_bytes": len(half),
            "response_model": "gpt-audio-1.5",
            "audio_tokens": 20,
        },
    }
    section = probe.delivery_section([call], measured=True)
    assert section is not None
    assert section["clips_whose_sent_duration_differs"] == [clip.clip_id]


def test_a_transport_failure_is_recorded_and_re_raised(tmp_path: Path) -> None:
    class Exploding:
        def __init__(self) -> None:
            self.chat = type("_Chat", (), {"completions": self})()

        def create(self, **kwargs: Any):
            raise TimeoutError("no answer")

    wire = _wire_for(Exploding())
    _judge_once(wire, tmp_path)  # the sub-judge catches it and returns judge_error
    assert wire.records[-1]["transport_error"] == "TimeoutError"
    assert wire.records[-1]["audio_part_present"] is True


# --------------------------------------------------------------------------
# What the reply says about itself
# --------------------------------------------------------------------------


def test_the_model_the_reply_names_is_recorded_not_the_one_we_asked_for(
    tmp_path: Path,
) -> None:
    """A deployment alias and the model behind it can differ.

    ``core/perception/audio.py`` records neither; the first run's report could
    not say which model answered it. It can now, and the value comes from the
    reply rather than from the request, or it would just be the alias again.
    """
    wire = _wire_for(FaithfulClient(model="gpt-audio-1.5-2026-02-11"))
    _judge_once(wire, tmp_path)
    assert wire.records[0]["requested_model"] == "gpt-audio-1.5"
    assert wire.records[0]["response_model"] == "gpt-audio-1.5-2026-02-11"


def test_audio_tokens_are_read_from_the_usage_details(tmp_path: Path) -> None:
    """The provider's own statement that it read the part as audio.

    ``core.cost_metering.extract_usage`` reads the cached breakdown out of
    this same block and stops, because the audio count is not part of a price
    lookup. It is the most direct delivery evidence there is, so the probe
    reads it even though the ledger does not.
    """
    wire = _wire_for(FaithfulClient(audio_tokens=57))
    _judge_once(wire, tmp_path)
    assert wire.records[0]["audio_tokens"] == 57
    assert wire.records[0]["audio_tokens_source"] == "prompt_tokens_details"


def test_no_audio_token_field_is_reported_as_unknown_not_zero(
    tmp_path: Path,
) -> None:
    """A provider that says nothing has not said zero.

    The distinction matters here more than usual: ``0`` would read as "the
    audio was accepted and not charged for", which is a finding, and absence
    is not that finding.
    """
    wire = _wire_for(MutatingClient(lambda kwargs: kwargs))
    _judge_once(wire, tmp_path)
    assert wire.records[0]["usage_present"] is True
    assert wire.records[0]["audio_tokens"] is None


# --------------------------------------------------------------------------
# The arms differ in the prompt and in nothing else
# --------------------------------------------------------------------------


def test_the_split_marker_is_what_core_actually_emits(tmp_path: Path) -> None:
    """Pinned against the real module, not against a copy of it.

    If ``core/perception/audio.py`` renames the separator, the observation arm
    can no longer find the criterion inside the assembled text. The dangerous
    outcome is not a crash -- it is silently sending the production prompt
    under the other arm's label, which would make the two arms identical and
    the comparison a fabrication. This is what stops that.
    """
    client = FaithfulClient()
    wire = _wire_for(client)
    _judge_once(wire, tmp_path)

    text = client.seen[0]["messages"][0]["content"][0]["text"]
    assert probe.PRODUCTION_CRITERION_MARKER in text
    header, criterion = probe.split_production_text(text)
    assert criterion == "a criterion"
    assert "audio sub-judge" in header


def test_a_renamed_marker_refuses_instead_of_silently_passing_through() -> None:
    with pytest.raises(ValueError, match="does not carry"):
        probe.split_production_text("no marker here")


def test_the_observation_arm_rewrites_only_the_text_part(tmp_path: Path) -> None:
    clip = probe.CLIPS_BY_ID["three_beeps"]
    path = tmp_path / "c.wav"
    probe.render_clip(clip, path)

    production = FaithfulClient()
    observation = FaithfulClient()
    for client, arm in ((production, "production"), (observation, "observation")):
        wire = _wire_for(client, arm)
        perception = AudioPerception(client=wire, deployment="gpt-audio-1.5")
        perception.judge(criterion="three beeps sound", audio_path=str(path))

    left = production.seen[0]["messages"][0]["content"]
    right = observation.seen[0]["messages"][0]["content"]
    assert [part["type"] for part in left] == [part["type"] for part in right]
    # The audio is the same object's worth of bytes, to the character.
    assert left[1]["input_audio"] == right[1]["input_audio"]
    # Everything outside the messages is untouched too.
    assert production.seen[0]["model"] == observation.seen[0]["model"]
    assert production.seen[0]["modalities"] == observation.seen[0]["modalities"]
    # And the text is not.
    assert left[0]["text"] != right[0]["text"]
    assert right[0]["text"].startswith("You are an audio analyst")


def test_the_criterion_survives_the_swap_word_for_word(tmp_path: Path) -> None:
    """The arms must ask the same question, differently framed.

    Rewriting the criterion as well would make this a comparison of two
    corpora rather than of two prompts, and the ground truth is stated about
    this wording.
    """
    clip = probe.CLIPS[0]
    path = tmp_path / "c.wav"
    probe.render_clip(clip, path)
    criterion = probe.CLAIMS[0].criterion

    client = FaithfulClient()
    wire = _wire_for(client, "observation")
    perception = AudioPerception(client=wire, deployment="gpt-audio-1.5")
    perception.judge(criterion=criterion, audio_path=str(path))

    text = client.seen[0]["messages"][0]["content"][0]["text"]
    assert text.endswith(criterion)
    assert probe.OBSERVATION_HEADER in text


def test_the_observation_header_never_hints_at_an_answer() -> None:
    """No per-item hint, and no base rate.

    "Ten of these twenty are true" would let a model score well by counting,
    and any fragment of a claim's own justification would be handing over the
    answer. The header has to work for all twenty without knowing any of them.
    """
    header = probe.OBSERVATION_HEADER.lower()
    for claim in probe.CLAIMS:
        assert claim.criterion.lower() not in header
        assert claim.because.lower() not in header
    for leak in ("ten of", "half of", "10 of the 20", "usually true", "most of these"):
        assert leak not in header
    # It must not tell the model which way to lean, in either direction.
    assert "likely to be true" not in header
    assert "likely to be false" not in header
    # It does have to say the claim is not a given -- that is the change under
    # test, and a header that dropped it would be the production prompt again.
    assert "may be true or it may be false" in header


def test_the_alternative_prompt_exists_only_in_the_probe() -> None:
    """Rule for this PR: the production grader is not edited to run a probe.

    The observation header is an experiment. If a copy of it appears under
    ``core/``, the thing being measured and the thing doing the measuring have
    merged, and the grader's fingerprint has moved for the sake of a
    diagnostic.
    """
    needle = "You are an audio analyst."
    hits = [
        path
        for path in (BATCH_RUNNER / "core").rglob("*.py")
        if needle in path.read_text(encoding="utf-8")
    ]
    assert hits == []


def test_an_unknown_arm_is_refused() -> None:
    with pytest.raises(ValueError, match="unknown prompt arm"):
        probe.apply_arm({"messages": []}, "whatever")


def test_a_non_production_arm_without_a_wrapper_is_refused(tmp_path: Path) -> None:
    """Failing loudly beats measuring the wrong thing.

    Without the wrapper there is nothing to rewrite the prompt, so the request
    would go out under the production header and be recorded under the other
    arm's name. That is not a weaker measurement; it is a false one.
    """
    perception = AudioPerception(client=FaithfulClient(), deployment="gpt-audio-1.5")
    with pytest.raises(ValueError, match="needs a WireClient"):
        probe.run_measurement(
            perception=perception,
            clip_dir=tmp_path,
            repeats=1,
            claims=probe.CLAIMS[:1],
            clips=probe.CLIPS[:1],
            arms=("observation",),
        )


def test_the_arms_are_interleaved_not_run_one_after_the_other(
    tmp_path: Path,
) -> None:
    """Time drift has to hit both arms, or it becomes the effect.

    Run production's sixty calls and then observation's sixty, and any change
    in the deployment over that hour lands entirely on the second arm. The
    corpus pairs true against false for the same reason; this pairs the arms
    against the clock.
    """
    stub = probe.TruthfulStub(probe.CLAIMS)
    wire = probe.WireClient(stub)
    perception = AudioPerception(client=wire, deployment="gpt-audio-1.5")
    result = probe.run_measurement(
        perception=perception,
        clip_dir=tmp_path,
        repeats=2,
        arms=probe.PROMPT_ARMS,
        wire=wire,
    )
    arms = [call["arm"] for call in result["calls"]]
    assert arms[:4] == ["production", "observation", "production", "observation"]
    ids = [call["claim_id"] for call in result["calls"]]
    assert ids[0] == ids[1] and ids[2] == ids[3]
    assert len(result["calls"]) == 2 * 2 * len(probe.CLAIMS)


def test_both_arms_are_given_byte_identical_audio(tmp_path: Path) -> None:
    """The condition the whole comparison rests on, asserted on the digests."""
    stub = probe.TruthfulStub(probe.CLAIMS)
    wire = probe.WireClient(stub)
    perception = AudioPerception(client=wire, deployment="gpt-audio-1.5")
    result = probe.run_measurement(
        perception=perception,
        clip_dir=tmp_path,
        repeats=1,
        arms=probe.PROMPT_ARMS,
        wire=wire,
    )
    section = probe.delivery_section(result["calls"], measured=False)
    assert section is not None
    assert section["clips_with_more_than_one_digest"] == []
    for digests in section["digests_per_clip"].values():
        assert len(digests) == 1


def test_the_two_arms_send_different_prompts(tmp_path: Path) -> None:
    """The other half of the same condition: they must not be identical either."""
    stub = probe.TruthfulStub(probe.CLAIMS)
    wire = probe.WireClient(stub)
    perception = AudioPerception(client=wire, deployment="gpt-audio-1.5")
    result = probe.run_measurement(
        perception=perception,
        clip_dir=tmp_path,
        repeats=1,
        arms=probe.PROMPT_ARMS,
        wire=wire,
    )
    by_arm: dict[str, set[str]] = {}
    for call in result["calls"]:
        by_arm.setdefault(call["arm"], set()).add(call["wire"]["prompt_sha256"])
    assert by_arm["production"].isdisjoint(by_arm["observation"])


# --------------------------------------------------------------------------
# The paired comparison
# --------------------------------------------------------------------------


def _pair(claim_id: str, repeat: int, arm: str, outcome: str, holds: bool) -> dict:
    verdict = {
        probe.OUTCOME_CORRECT: "pass" if holds else "fail",
        probe.OUTCOME_FALSE_FAIL: "fail",
        probe.OUTCOME_FALSE_PASS: "pass",
        probe.OUTCOME_HEDGED: "partial",
        probe.OUTCOME_UNANSWERED: "judge_error",
    }[outcome]
    return {
        "claim_id": claim_id,
        "pair_id": f"pair_{claim_id}",
        "family": "synthetic",
        "repeat": repeat,
        "arm": arm,
        "holds": holds,
        "verdict": verdict,
        "outcome": outcome,
        "confidence": 1.0,
    }


def test_mcnemar_is_exact_at_the_counts_this_corpus_produces() -> None:
    """Checked against the binomial by hand, not against another library.

    Ten discordant calls all falling one way is 2/1024. A chi-square
    approximation would put it somewhere near 0.0016 and be wrong in the
    direction that matters.
    """
    assert probe.mcnemar_exact(10, 0) == pytest.approx(2 / 1024)
    assert probe.mcnemar_exact(5, 0) == pytest.approx(2 / 32)
    assert probe.mcnemar_exact(0, 5) == pytest.approx(2 / 32)
    assert probe.mcnemar_exact(3, 3) == pytest.approx(1.0)
    assert probe.mcnemar_exact(7, 3) == pytest.approx(
        2 * sum(math.comb(10, i) for i in range(4)) / 1024
    )


def test_mcnemar_is_symmetric_in_its_two_arguments() -> None:
    for b, c in ((1, 4), (2, 9), (0, 3), (6, 6)):
        assert probe.mcnemar_exact(b, c) == probe.mcnemar_exact(c, b)


def test_no_discordant_calls_is_none_rather_than_p_equals_one() -> None:
    """``p = 1.0`` reads as a measurement of sameness. There was no test."""
    assert probe.mcnemar_exact(0, 0) is None


def test_the_comparison_reading_refuses_to_call_a_null_result_equivalence() -> None:
    calls = [
        _pair("a", 1, arm, probe.OUTCOME_CORRECT, True)
        for arm in probe.PROMPT_ARMS
    ]
    comparison = probe.compare_arms(calls)
    assert comparison is not None
    assert "does NOT mean the prompts are equivalent" in comparison["reading"]


def test_only_calls_with_a_partner_on_the_other_side_are_paired() -> None:
    calls = [
        _pair("a", 1, "production", probe.OUTCOME_CORRECT, True),
        _pair("a", 1, "observation", probe.OUTCOME_FALSE_FAIL, True),
        # No observation partner: dropped rather than averaged in.
        _pair("b", 1, "production", probe.OUTCOME_CORRECT, True),
    ]
    comparison = probe.compare_arms(calls)
    assert comparison is not None
    assert comparison["pairs"] == 1
    assert comparison["discordant"]["control_only_correct"] == 1
    assert comparison["discordant"]["treatment_only_correct"] == 0


def test_a_hedge_is_not_an_improvement() -> None:
    """An arm that stopped committing has not got better at the task."""
    calls = [
        _pair("a", 1, "production", probe.OUTCOME_FALSE_FAIL, True),
        _pair("a", 1, "observation", probe.OUTCOME_HEDGED, True),
    ]
    comparison = probe.compare_arms(calls)
    assert comparison is not None
    assert comparison["discordant"]["neither_correct"] == 1
    assert comparison["observation"]["correct"] == 0


def test_a_non_answer_lowers_the_response_rate_and_not_the_accuracy() -> None:
    """Both numbers, always, because either alone can be read the wrong way."""
    calls = [
        _pair("a", 1, "observation", probe.OUTCOME_CORRECT, True),
        _pair("b", 1, "observation", probe.OUTCOME_UNANSWERED, False),
        _pair("a", 1, "production", probe.OUTCOME_CORRECT, True),
        _pair("b", 1, "production", probe.OUTCOME_CORRECT, False),
    ]
    comparison = probe.compare_arms(calls)
    assert comparison is not None
    side = comparison["observation"]
    assert side["attempts"] == 2
    assert side["answered"] == 1
    assert side["accuracy_of_answered"] == pytest.approx(1.0)
    assert side["response_rate"] == pytest.approx(0.5)


def test_one_arm_alone_has_nothing_to_compare() -> None:
    calls = [_pair("a", 1, "production", probe.OUTCOME_CORRECT, True)]
    assert probe.compare_arms(calls) is None


def test_every_tally_reports_the_denominator_the_accuracy_hides() -> None:
    """Accuracy divides by the calls that answered. This divides by all of them.

    Without it, a model that returned ``judge_error`` to nineteen criteria and
    got the twentieth right reports 100% accuracy, and the report contains no
    number that contradicts it. The pre-registration commits to publishing
    both, so both have to be in the object the report is built from -- not
    only in the arm comparison, which a single-arm run does not produce.
    """
    calls = [
        _pair("a", 1, "production", probe.OUTCOME_CORRECT, True),
        _pair("b", 1, "production", probe.OUTCOME_UNANSWERED, False),
        _pair("c", 1, "production", probe.OUTCOME_UNANSWERED, True),
        _pair("d", 1, "production", probe.OUTCOME_UNANSWERED, False),
    ]
    summary = probe.summarise(calls)
    assert summary["overall"]["accuracy"] == pytest.approx(1.0)
    assert summary["overall"]["response_rate"] == pytest.approx(0.25)
    # Present on every slice, not only the headline one.
    assert summary["on_true_claims"]["response_rate"] is not None
    assert summary["on_false_claims"]["response_rate"] == pytest.approx(0.0)


def test_the_report_carries_the_response_rate_beside_the_accuracy(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert probe.main(["--dry-run", "--repeats", "1", "--quiet"]) == 0
    report = json.loads(capsys.readouterr().out)
    overall = report["accuracy"]["overall"]
    assert overall["response_rate"] == pytest.approx(
        overall["answered"] / overall["calls"]
    )
    for family in report["accuracy"]["by_family"].values():
        assert "response_rate" in family


def test_a_call_with_no_arm_field_counts_as_production() -> None:
    """Older reports, and every synthetic call in the older test file.

    The field was added with the second arm; a log written before it exists
    is a production log and must not silently drop out of the summary.
    """
    assert probe._arm_of({"verdict": "pass"}) == "production"
    assert probe._arm_of({"arm": None}) == "production"
    assert probe._arm_of({"arm": "observation"}) == "observation"


# --------------------------------------------------------------------------
# The correlation that shows the audio was understood, not merely accepted
# --------------------------------------------------------------------------


def test_correlation_is_one_for_a_straight_line_and_minus_one_reversed() -> None:
    assert probe.pearson_r([1, 2, 3, 4], [2, 4, 6, 8]) == pytest.approx(1.0)
    assert probe.pearson_r([1, 2, 3, 4], [8, 6, 4, 2]) == pytest.approx(-1.0)


def test_correlation_refuses_a_constant_or_a_short_series() -> None:
    """Zero variance has no correlation, and 0.0 would read as "no relationship"."""
    assert probe.pearson_r([1, 2, 3], [5, 5, 5]) is None
    assert probe.pearson_r([1, 2], [3, 4]) is None
    assert probe.pearson_r([1, 2, 3], [1, 2]) is None


def test_the_delivery_section_is_absent_when_nothing_was_recorded() -> None:
    assert probe.delivery_section([{"claim_id": "a", "clip_id": "x"}], measured=True) is None


def test_a_dry_run_labels_its_delivery_evidence_as_not_measured(
    tmp_path: Path,
) -> None:
    """The one artifact most likely to be quoted out of context.

    A stub produces a near-perfect token/duration correlation because it bills
    by size. That figure is true of the stub and says nothing about a
    provider, so the section carries ``measured: false``, names the stub as
    the responding model, and reports no audio tokens at all.
    """
    stub = probe.TruthfulStub(probe.CLAIMS)
    wire = probe.WireClient(stub)
    perception = AudioPerception(client=wire, deployment="gpt-audio-1.5")
    result = probe.run_measurement(
        perception=perception, clip_dir=tmp_path, repeats=1, wire=wire
    )
    report = probe.build_report(
        identity=probe.pinned_identity(), measured=False, repeats=1, result=result
    )
    delivery = report["delivery"]
    assert delivery["measured"] is False
    assert delivery["response_models"] == ["stub-not-a-model"]
    assert delivery["audio_tokens_reported"] == 0
    assert "proves the plumbing, not the delivery" in delivery["not_covered"]


def test_every_call_of_a_wired_run_is_accounted_for(tmp_path: Path) -> None:
    stub = probe.TruthfulStub(probe.CLAIMS)
    wire = probe.WireClient(stub)
    perception = AudioPerception(client=wire, deployment="gpt-audio-1.5")
    result = probe.run_measurement(
        perception=perception, clip_dir=tmp_path, repeats=1, wire=wire
    )
    section = probe.delivery_section(result["calls"], measured=False)
    assert section is not None
    assert section["calls_inspected"] == len(probe.CLAIMS)
    assert section["calls_carrying_audio"] == len(probe.CLAIMS)
    assert section["calls_without_audio"] == []
    assert section["sent_formats"] == ["wav"]
    assert section["sent_sample_rates_hz"] == [AUDIO_SAMPLE_RATE_HZ]
    assert section["sent_channels"] == [1]


def test_a_run_where_the_audio_never_arrived_names_the_claims(
    tmp_path: Path,
) -> None:
    """The report the first run should have been able to produce and could not."""
    calls = [
        {
            "claim_id": f"claim_{i}",
            "clip_id": probe.CLIPS[0].clip_id,
            "input_tokens": 150,
            "wire": {
                "requests": 1,
                "requests_with_audio": 0,
                "audio_sha256": None,
                "audio_duration_s": None,
                "audio_format": None,
                "response_model": "gpt-audio-1.5",
                "audio_tokens": None,
            },
        }
        for i in range(3)
    ]
    section = probe.delivery_section(calls, measured=True)
    assert section is not None
    assert section["calls_carrying_audio"] == 0
    assert section["calls_without_audio"] == ["claim_0", "claim_1", "claim_2"]
    assert section["audio_tokens_reported"] == 0


# --------------------------------------------------------------------------
# What may not leave this process
# --------------------------------------------------------------------------


def test_no_record_ever_holds_the_audio_or_the_prompt(tmp_path: Path) -> None:
    """Hashes and counts. Not bytes, not text, not reasoning.

    An artifact that carried the base64 would be a megabyte per call and, on
    a real deliverable rather than a synthesised clip, would be a copy of
    someone's file sitting in a CI log.
    """
    client = FaithfulClient()
    wire = _wire_for(client)
    _judge_once(wire, tmp_path)

    sent = client.seen[0]["messages"][0]["content"]
    b64 = sent[1]["input_audio"]["data"]
    text = sent[0]["text"]
    blob = json.dumps(wire.records)
    assert b64[:64] not in blob
    assert text[:64] not in blob
    assert "reasoning" not in blob
    for value in wire.records[0].values():
        assert not (isinstance(value, str) and len(value) > 128)


def test_the_delivery_artifact_carries_no_prompt_and_no_audio(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "delivery.json"
    assert (
        probe.main(
            [
                "--dry-run",
                "--repeats",
                "1",
                "--quiet",
                "--delivery-out",
                str(out),
            ]
        )
        == 0
    )
    written = out.read_text(encoding="utf-8")
    payload = json.loads(written)
    assert payload["measured"] is False
    assert payload["delivery"]["calls_carrying_audio"] == len(probe.CLAIMS)
    # No criterion text, no prompt, no base64 of any length worth having.
    for claim in probe.CLAIMS:
        assert claim.criterion not in written
    assert "You are an audio" not in written
    assert "evidence" not in payload["delivery"]


def test_the_arm_flag_reaches_the_run(capsys: pytest.CaptureFixture[str]) -> None:
    assert probe.main(["--dry-run", "--repeats", "1", "--quiet",
                       "--prompt-arm", "both"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["pins"]["prompt_arms"] == ["production", "observation"]
    assert set(report["arms"]) == set(probe.PROMPT_ARMS)
    assert report["arm_comparison"]["pairs"] == len(probe.CLAIMS)
    # 20 criteria under two prompts.
    assert report["cost"]["model_calls"] == 2 * len(probe.CLAIMS)


def test_the_headline_accuracy_stays_the_production_prompts(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Averaging the arms would report a number no prompt actually produced.

    ``accuracy`` is what the grader does. The alternative's figures live under
    ``arms`` and are never folded in.
    """
    assert probe.main(["--dry-run", "--repeats", "1", "--quiet",
                       "--prompt-arm", "both"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["accuracy"]["overall"]["calls"] == len(probe.CLAIMS)
    assert report["arms"]["production"] == report["accuracy"]


def test_a_single_arm_run_still_reports_delivery(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The cheap run must not be the one that cannot say whether audio arrived."""
    assert probe.main(["--dry-run", "--repeats", "1", "--quiet"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["pins"]["prompt_arms"] == ["production"]
    assert "arms" not in report
    assert report["delivery"]["calls_carrying_audio"] == len(probe.CLAIMS)
