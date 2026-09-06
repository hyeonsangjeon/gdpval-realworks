"""The audio sub-judge's reply contract, and what happens when it is broken.

Written against a specific, measured failure. The 2026-09-06 prompt A/B
(run 34008840627, `tasks/rebuilding_grading_task/328-*.md`) bought 120 audio
calls to compare two prompts. Of the 60 in the treatment arm, 43 came back as
`provider_error:JSONDecodeError` and the surviving 17 answered `true`, `false`,
`refuse` or `analyze_audio` -- never `pass`. The measurement code counts
"not `pass`" as "the criterion does not hold", so all 17 folded to one side and
the arm's discrimination came out at exactly 0.0.

None of that was about hearing. Two defects in this module made a
prompt-versus-capability experiment unable to measure either:

1. A malformed reply raised out of `json.loads` into the same `except` that
   catches a provider outage, so `judge_error` said `provider_error:...` for a
   failure the provider had nothing to do with.
2. `verdict=str(payload.get("verdict", "fail"))` accepted whatever string
   arrived, and turned a reply with *no* verdict into a `fail` -- a grade
   against the deliverable, invented by a default argument.

These tests pin both halves: the envelope validator in isolation, and the same
shapes driven through `AudioPerception.judge` with a fake client, which is the
path production actually takes.
"""

from __future__ import annotations

import json
import struct
import sys
import wave
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from core.perception import AudioPerception, AudioVerdict
from core.perception.audio import (
    AUDIO_FORMAT_ERROR_KINDS,
    AUDIO_RESPONSE_CONTRACT,
    AUDIO_VERDICT_VOCABULARY,
    AudioEnvelopeError,
    _audio_prompt_header,
    _parse_json_envelope,
    _validated_audio_envelope,
)

# The A/B probe is a script rather than a package module, so its directory has
# to be on the path before it can be imported. Done here rather than inside
# each test: relying on some other test file having done it first makes the
# result depend on collection order.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import measure_audio_grading_accuracy as probe  # noqa: E402


# ── Doubles ──────────────────────────────────────────────────────────


def _usage() -> SimpleNamespace:
    return SimpleNamespace(
        prompt_tokens=70,
        completion_tokens=12,
        prompt_tokens_details=SimpleNamespace(cached_tokens=5),
    )


class _Completions:
    def __init__(self, text: str) -> None:
        self.text = text
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=self.text, audio=None)
                )
            ],
            usage=_usage(),
        )


class _Client:
    def __init__(self, text: str) -> None:
        self.chat = SimpleNamespace(completions=_Completions(text))

    @property
    def calls(self) -> list[dict[str, Any]]:
        return self.chat.completions.calls


@pytest.fixture
def wav_file(tmp_path: Path) -> Path:
    p = tmp_path / "clip.wav"
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(
            b"".join(struct.pack("<h", (i % 100) * 200) for i in range(8000))
        )
    return p


def _judge(wav: Path, text: str) -> tuple[AudioVerdict, _Client]:
    client = _Client(text)
    verdict = AudioPerception(client=client).judge(
        criterion="the clip contains a rising tone", audio_path=str(wav)
    )
    return verdict, client


def _envelope(
    verdict: object = "pass",
    partial: object = 1.0,
    confidence: object = 0.9,
    **extra: object,
) -> str:
    body: dict[str, object] = {
        "verdict": verdict,
        "partial_score": partial,
        "confidence": confidence,
        "evidence": "a tone rises from 220Hz to 440Hz",
        "reasoning": "heard it",
    }
    body.update(extra)
    return json.dumps(body)


# ── The validator, in isolation ──────────────────────────────────────


@pytest.mark.parametrize("verdict", sorted(AUDIO_VERDICT_VOCABULARY))
def test_every_vocabulary_verdict_is_accepted(verdict: str) -> None:
    """All four, including ``judge_error``.

    ``judge_error`` is in the sub-judge's vocabulary and not the main judge's
    because this module's own prompt asks for it: when a criterion names a
    region the clip does not carry, ``_AUDIO_WINDOW_UNCUT_NOTE`` instructs the
    model to answer ``judge_error`` rather than fail the deliverable for
    something nobody listened to. A validator copied from the main judge would
    reject the reply this module asked for.
    """
    got, partial, confidence = _validated_audio_envelope(
        json.loads(_envelope(verdict=verdict, partial=0.5, confidence=0.5))
    )
    assert got == verdict
    assert (partial, confidence) == (0.5, 0.5)


def test_case_and_padding_are_normalised_not_rejected() -> None:
    got, _, _ = _validated_audio_envelope(
        json.loads(_envelope(verdict="  PASS  "))
    )
    assert got == "pass"


@pytest.mark.parametrize(
    "bad, kind, detail",
    [
        ("true", "verdict_not_in_vocabulary", "true"),
        ("false", "verdict_not_in_vocabulary", "false"),
        ("refuse", "verdict_not_in_vocabulary", "refuse"),
        ("analyze_audio", "verdict_not_in_vocabulary", "analyze_audio"),
        ("no", "verdict_not_in_vocabulary", "no"),
        ("yes", "verdict_not_in_vocabulary", "yes"),
    ],
)
def test_the_verdicts_the_ab_actually_produced_are_named_not_swallowed(
    bad: str, kind: str, detail: str
) -> None:
    """The six strings observed in run 34008840627, and what each is now called.

    Every one of these used to be accepted verbatim and carried downstream as
    a verdict. ``true`` is the one that mattered: 13 of the treatment arm's 17
    answers, all of them scored as "the criterion does not hold" because the
    scorer's rule is ``said_pass = verdict == "pass"``.
    """
    with pytest.raises(AudioEnvelopeError) as caught:
        _validated_audio_envelope(json.loads(_envelope(verdict=bad)))
    assert caught.value.kind == kind
    assert caught.value.detail == detail


def test_a_reply_with_no_verdict_is_not_a_fail() -> None:
    """The regression this file exists for.

    ``payload.get("verdict", "fail")`` returned a judgement against the
    deliverable for a reply that contained no judgement, and nothing
    downstream could tell it apart from a criterion the sub-judge listened to
    and rejected. It has to fail *closed* -- to ``judge_error``, which is
    excluded from the score -- and not *against*.
    """
    payload = json.loads(_envelope())
    del payload["verdict"]
    with pytest.raises(AudioEnvelopeError) as caught:
        _validated_audio_envelope(payload)
    assert caught.value.kind == "verdict_missing"


@pytest.mark.parametrize(
    "raw, kind",
    [
        ("", "empty_text"),
        ("   \n ", "empty_text"),
        ("I listened to the clip and it seems fine.", "unparseable_json"),
        ('{"verdict": "pass",', "unparseable_json"),
        ("[1, 2, 3]", "not_an_object"),
        ('"pass"', "not_an_object"),
        ("null", "not_an_object"),
    ],
)
def test_unparseable_and_non_object_replies_are_separated(
    raw: str, kind: str
) -> None:
    with pytest.raises(AudioEnvelopeError) as caught:
        _validated_audio_envelope(_parse_json_envelope(raw))
    assert caught.value.kind == kind


def test_a_fenced_envelope_is_still_read() -> None:
    """Code fences are stripped, as before -- strictness is about values."""
    fenced = "```json\n" + _envelope() + "\n```"
    got, _, _ = _validated_audio_envelope(_parse_json_envelope(fenced))
    assert got == "pass"


@pytest.mark.parametrize(
    "value, kind",
    [
        (True, "partial_score_not_a_number"),
        (False, "partial_score_not_a_number"),
        ("1.0", "partial_score_not_a_number"),
        (None, "partial_score_not_a_number"),
        ({"n": 1}, "partial_score_not_a_number"),
        (7, "partial_score_out_of_range"),
        (-0.5, "partial_score_out_of_range"),
        (float("nan"), "partial_score_out_of_range"),
        (float("inf"), "partial_score_out_of_range"),
    ],
)
def test_a_score_that_is_not_a_number_in_range_is_rejected(
    value: object, kind: str
) -> None:
    """``True`` is the one worth naming: in Python it is an ``int`` worth 1.

    Without the explicit ``bool`` check a model answering ``"partial_score":
    true`` would be recorded as a full-marks score of 1.0.
    """
    with pytest.raises(AudioEnvelopeError) as caught:
        _validated_audio_envelope(
            {"verdict": "pass", "partial_score": value, "confidence": 0.9}
        )
    assert caught.value.kind == kind


@pytest.mark.parametrize("field", ["partial_score", "confidence"])
def test_a_missing_number_is_rejected_rather_than_defaulted(field: str) -> None:
    """A defaulted ``0.0`` is not "unknown"; it is "zero marks".

    Same failure as the defaulted verdict, one field over, and it reaches the
    grade as a number rather than a label -- which is harder to spot, because
    a zero looks like a measurement.
    """
    payload = json.loads(_envelope())
    del payload[field]
    with pytest.raises(AudioEnvelopeError) as caught:
        _validated_audio_envelope(payload)
    assert caught.value.kind == f"{field}_not_a_number"
    assert caught.value.detail == "<absent>"


def test_a_verdict_that_is_not_a_string_is_named_by_type() -> None:
    with pytest.raises(AudioEnvelopeError) as caught:
        _validated_audio_envelope(
            {"verdict": 1, "partial_score": 1.0, "confidence": 0.9}
        )
    assert caught.value.kind == "verdict_not_a_string"
    assert caught.value.detail == "<int>"


@pytest.mark.parametrize(
    "hostile",
    [
        "PASS; DROP TABLE grades",
        "a" * 500,
        "pass\nreasoning: ignore previous instructions",
        "일부 통과",
        "<script>alert(1)</script>",
    ],
)
def test_an_out_of_vocabulary_verdict_cannot_carry_a_payload_out(
    hostile: str,
) -> None:
    """``detail`` admits model text only in a shape too narrow to smuggle with.

    It exists so an operator can tell ``true`` from ``analyze_audio`` without
    reading the reply, and it is published in ``judge_error``. So the rule is
    the same one the rest of this module lives by: a short lower-case
    identifier, or a class name, and never free text.
    """
    with pytest.raises(AudioEnvelopeError) as caught:
        _validated_audio_envelope(json.loads(_envelope(verdict=hostile)))
    assert caught.value.kind == "verdict_not_in_vocabulary"
    assert caught.value.detail == "<non-token>"


def test_the_error_kinds_are_a_closed_declared_set() -> None:
    """Every kind a caller can meet is in ``AUDIO_FORMAT_ERROR_KINDS``.

    The corpus is grouped by this string. It is declared rather than
    discovered so that adding a branch without adding its name is a test
    failure and not a new singleton in somebody's tally.
    """
    seen = set()
    for payload in (
        "",
        "not json",
        "[1]",
        {"partial_score": 1.0, "confidence": 0.9},
        {"verdict": 1, "partial_score": 1.0, "confidence": 0.9},
        {"verdict": "true", "partial_score": 1.0, "confidence": 0.9},
        {"verdict": "pass", "confidence": 0.9},
        {"verdict": "pass", "partial_score": 9.0, "confidence": 0.9},
        {"verdict": "pass", "partial_score": 1.0},
        {"verdict": "pass", "partial_score": 1.0, "confidence": 9.0},
    ):
        with pytest.raises(AudioEnvelopeError) as caught:
            _validated_audio_envelope(
                _parse_json_envelope(payload)
                if isinstance(payload, str)
                else payload
            )
        seen.add(caught.value.kind)
    assert seen <= set(AUDIO_FORMAT_ERROR_KINDS)
    assert seen == set(AUDIO_FORMAT_ERROR_KINDS)


# ── The production path, through AudioPerception.judge ───────────────


def test_a_good_envelope_still_reaches_the_caller(wav_file: Path) -> None:
    verdict, _ = _judge(wav_file, _envelope(verdict="partial", partial=0.4))
    assert verdict.verdict == "partial"
    assert verdict.partial_score == 0.4
    assert verdict.judge_error is None
    assert verdict.failure_detail is None
    assert verdict.usage_complete is True


@pytest.mark.parametrize(
    "reply, kind",
    [
        (_envelope(verdict="true"), "verdict_not_in_vocabulary"),
        ("the tone rises", "unparseable_json"),
        ("", "empty_text"),
        ('{"verdict": "pass", "partial_score": true, "confidence": 1}',
         "partial_score_not_a_number"),
    ],
)
def test_a_broken_reply_is_a_format_error_not_a_provider_error(
    wav_file: Path, reply: str, kind: str
) -> None:
    """The separation the A/B needed and did not have.

    ``provider_error:JSONDecodeError`` told an operator to look at the
    provider. The provider was fine: it answered, it billed, and the tokens
    came back. What was wrong was the shape of the answer, which is fixed by
    editing a prompt -- so it has to say so in the field a corpus is grouped
    by.
    """
    verdict, _ = _judge(wav_file, reply)
    assert verdict.verdict == "judge_error"
    assert verdict.judge_error == f"format_error:{kind}"
    assert "provider_error" not in (verdict.judge_error or "")
    assert verdict.failure_detail is not None
    assert kind in verdict.failure_detail


def test_a_format_error_still_reports_the_tokens_it_spent(
    wav_file: Path,
) -> None:
    """A malformed reply is a paid call and the ledger has to show it.

    43 of these went unpriced-looking in the A/B because they read as
    provider failures; the usage was in the record all along. If this
    regressed, a run's token total would quietly under-count every call the
    model answered badly.
    """
    verdict, _ = _judge(wav_file, "not json")
    assert verdict.api_call_count == 1
    assert verdict.input_tokens == 70
    assert verdict.output_tokens == 12
    assert verdict.cached_tokens == 5
    assert verdict.usage_complete is True


def test_a_format_error_does_not_block_the_rest_of_the_task(
    wav_file: Path,
) -> None:
    """Only the wire gets to stop a task early.

    ``_blocked_reason`` short-circuits the remaining criteria because a 400
    on this clip will be a 400 on the next one. A model that answered in the
    wrong shape may well answer the next criterion correctly, and refusing
    the rest of the rubric on its behalf would turn one bad reply into
    thirteen ungraded criteria.
    """
    client = _Client("not json")
    ap = AudioPerception(client=client)
    first = ap.judge(criterion="one", audio_path=str(wav_file))
    second = ap.judge(criterion="two", audio_path=str(wav_file))
    assert first.verdict == "judge_error"
    assert second.verdict == "judge_error"
    assert len(client.calls) == 2, "the second criterion was never asked"
    assert ap.calls_used == 2


def test_a_model_shaped_judge_error_says_why(wav_file: Path) -> None:
    """A refusal to judge is not a blank.

    ``judge_error`` from the model is a legitimate answer to
    ``_AUDIO_WINDOW_UNCUT_NOTE``, but it is not a *judgement*, so the field
    that explains unanswered items has to be filled -- otherwise the item
    reads downstream as a verdict nobody can account for.
    """
    verdict, _ = _judge(
        wav_file, _envelope(verdict="judge_error", partial=0.0, confidence=0.0)
    )
    assert verdict.verdict == "judge_error"
    assert verdict.judge_error == "sub_judge_declined"
    assert verdict.failure_detail is None, "it answered; nothing failed"


def test_a_provider_failure_is_still_a_provider_failure(
    wav_file: Path,
) -> None:
    """The other half of the separation, held from the far side.

    Tightening the parse must not reclassify a genuine outage as a format
    problem, or the same conflation reappears pointing the other way.
    """

    class _Boom:
        calls: list[dict[str, Any]] = []

        def create(self, **kwargs: Any) -> Any:
            raise RuntimeError("connection reset")

    client = SimpleNamespace(chat=SimpleNamespace(completions=_Boom()))
    verdict = AudioPerception(client=client).judge(
        criterion="x", audio_path=str(wav_file)
    )
    assert verdict.verdict == "judge_error"
    assert (verdict.judge_error or "").startswith("provider_error")
    assert "format_error" not in (verdict.judge_error or "")


# ── The contract as sent ─────────────────────────────────────────────


def test_the_prompt_states_the_vocabulary_the_parser_enforces(
    wav_file: Path,
) -> None:
    """The model is told exactly what the validator will accept.

    A strict parser and a vague prompt is a worse pairing than the lax parser
    it replaced: it converts model replies into ``judge_error`` for a rule
    the model was never given. Every accepted value has to appear in the text
    that goes out.
    """
    _, client = _judge(wav_file, _envelope())
    sent = client.calls[0]["messages"][0]["content"][0]["text"]
    for allowed in AUDIO_VERDICT_VOCABULARY:
        assert f'"{allowed}"' in sent, f"{allowed} is accepted but never asked for"
    assert '"true"' in sent and '"false"' in sent, "the observed wrong answers"
    assert "partial_score" in sent and "confidence" in sent


def test_every_prompt_variant_carries_the_identical_contract() -> None:
    """One paragraph, byte-identical, whatever else the header says.

    The point of an A/B is that one thing changes. When the response contract
    is written inline it travels with the variant, and a difference in
    response *rate* between arms stops being attributable to the thing under
    test -- which is exactly what happened on 2026-09-06.
    """
    variants = [
        _audio_prompt_header(),
        _audio_prompt_header(start_seconds=82.0, trim_seconds=30),
        _audio_prompt_header(window_note="Note: something about the window."),
        _audio_prompt_header(start_seconds=5.0, window_note="Another note."),
    ]
    for text in variants:
        assert text.count(AUDIO_RESPONSE_CONTRACT) == 1
    assert len({v.split(AUDIO_RESPONSE_CONTRACT)[-1] for v in variants}) == 1


def test_the_window_note_asks_for_a_verdict_the_parser_admits() -> None:
    """The module's own instruction has to survive its own validator.

    ``_AUDIO_WINDOW_UNCUT_NOTE`` tells the model to answer ``judge_error``.
    If a later tightening dropped that value from the vocabulary, this module
    would be asking for a reply it then discards, and every un-cuttable window
    would become a format error instead of the honest "not heard" it is.
    """
    from core.perception.audio import _AUDIO_WINDOW_UNCUT_NOTE

    asked = {
        word.strip('"')
        for word in _AUDIO_WINDOW_UNCUT_NOTE.split()
        if word.strip('"') in {"pass", "fail", "partial", "judge_error"}
    }
    assert asked, "the note names no verdict at all"
    assert asked <= AUDIO_VERDICT_VOCABULARY


def test_no_structured_output_is_requested_until_it_is_verified(
    wav_file: Path,
) -> None:
    """The contract is carried in the prompt, not in an unverified API flag.

    ``response_format`` would enforce this server-side and is the better
    answer -- but only if ``gpt-audio-1.5`` accepts it alongside
    ``input_audio``, which nobody has observed. Sending it on a deployment
    that rejects it turns every audio call into a 400, so it stays out until
    a probe says otherwise. This test is the marker for that decision, not an
    argument against the feature.
    """
    _, client = _judge(wav_file, _envelope())
    assert "response_format" not in client.calls[0]
    assert client.calls[0]["modalities"] == ["text"]


# ── Both arms of the comparison ask for the same shape ───────────────


def test_both_ab_arms_carry_the_byte_identical_contract() -> None:
    """The confound that made run 34008840627 unreadable.

    The treatment arm used to end with its own hand-written "Return the same
    JSON envelope as the main judge ... Return JSON only." paragraph, written
    separately from the one production sent. Two prompts asking for JSON in
    two different sets of words is a difference in the *instruction*, so a gap
    in response rate between the arms could not be attributed to the thing
    under test -- and the gap was total: 60 of 60 versus 10 of 60.

    Both arms now end with the same constant, so whatever else the arms
    differ on, the shape being asked for is not it.
    """
    assert probe.OBSERVATION_HEADER.endswith(AUDIO_RESPONSE_CONTRACT)
    assert probe.OBSERVATION_HEADER.count(AUDIO_RESPONSE_CONTRACT) == 1
    # The production arm gets it from the module under test, not from a copy.
    assert AUDIO_RESPONSE_CONTRACT in _audio_prompt_header()


def test_the_treatment_arm_no_longer_invents_its_own_envelope_wording() -> None:
    """The old paragraph is gone, not merely appended to.

    Leaving both in would be worse than either: the model would be given two
    descriptions of the reply format in one prompt, and the looser one names
    no vocabulary at all.
    """
    assert "Return JSON only." not in probe.OBSERVATION_HEADER
    assert "Return the same JSON envelope" not in probe.OBSERVATION_HEADER


def test_the_treatment_arm_still_says_the_thing_it_is_testing() -> None:
    """Parity on the contract must not quietly become parity on everything.

    The arm exists to test whether telling the model to observe first, and
    warning it that the statement may be false, changes what it hears. If a
    tidy-up ever removed that, the A/B would compare a prompt with itself and
    still report a p-value.
    """
    assert "observe the clip" in probe.OBSERVATION_HEADER
    assert "may be true or it may be false" in probe.OBSERVATION_HEADER
    assert probe.OBSERVATION_HEADER != _audio_prompt_header()


# ── The three non-answers, told apart ────────────────────────────────


@pytest.mark.parametrize(
    "verdict, marker, expected",
    [
        ("pass", None, None),
        ("fail", None, None),
        ("partial", None, None),
        ("judge_error", "sub_judge_declined", "declined_to_judge"),
        ("judge_error", "format_error:unparseable_json", "read_failure"),
        ("judge_error", "format_error:verdict_not_in_vocabulary",
         "read_failure"),
        ("judge_error", "provider_error:APIConnectionError",
         "provider_failure"),
    ],
)
def test_each_non_answer_is_named_by_what_actually_happened(
    verdict: str, marker: object, expected: object
) -> None:
    assert probe.unanswered_kind(verdict, marker) == expected  # type: ignore[arg-type]


def test_an_unlabelled_non_answer_is_not_credited_as_an_honest_decline() -> None:
    """The conservative default, and why it points that way.

    ``declined_to_judge`` is the one of the three that reads as the model
    behaving well. A non-answer with no marker is one nobody has explained, so
    it goes to the bucket that claims least.
    """
    assert probe.unanswered_kind("judge_error", None) == "provider_failure"
    assert probe.unanswered_kind("judge_error", "") == "provider_failure"


def test_the_split_does_not_move_a_single_accuracy_figure() -> None:
    """Separating the three must not quietly re-weight the score.

    All three are calls that measured nothing, so all three stay out of the
    accuracy denominator exactly as before. If this ever changed, an arm could
    improve its published accuracy by failing differently.
    """
    claim = probe.CLAIMS[0]
    for marker in ("sub_judge_declined", "format_error:empty_text",
                   "provider_error:Timeout", None):
        assert (
            probe.classify(claim, "judge_error") == probe.OUTCOME_UNANSWERED
        ), marker


def test_a_tally_reports_the_breakdown_and_it_sums_to_the_total() -> None:
    tally = probe.Tally()
    tally.add(probe.OUTCOME_CORRECT)
    tally.add(probe.OUTCOME_UNANSWERED, probe.UNANSWERED_READ_FAILURE)
    tally.add(probe.OUTCOME_UNANSWERED, probe.UNANSWERED_READ_FAILURE)
    tally.add(probe.OUTCOME_UNANSWERED, probe.UNANSWERED_DECLINED)
    got = tally.to_dict()

    assert got["unanswered"] == 3
    assert got["unanswered_by_kind"] == {
        "declined_to_judge": 1,
        "read_failure": 2,
        "provider_failure": 0,
    }
    assert sum(got["unanswered_by_kind"].values()) == got["unanswered"]
    assert got["accuracy"] == 1.0, "one answer, and it was right"
    assert got["response_rate"] == pytest.approx(0.25), "over all four calls"


def test_an_unknown_kind_is_refused_rather_than_counted_somewhere() -> None:
    """A typo must not create a silent fourth bucket that nobody reads."""
    with pytest.raises(ValueError):
        probe.Tally().add(probe.OUTCOME_UNANSWERED, "formaterror")


def test_an_older_call_log_summarises_without_a_breakdown_or_a_crash() -> None:
    """Re-reading a result written before the split is not an error.

    The stored 2026-09-06 log has no ``unanswered_kind`` key. Summarising it
    has to report an empty breakdown -- not invent one, and not refuse.
    """
    claim = probe.CLAIMS[0]
    calls = [
        {
            "claim_id": claim.claim_id,
            "pair_id": claim.pair_id,
            "family": claim.family,
            "holds": claim.holds,
            "verdict": "judge_error",
            "outcome": probe.OUTCOME_UNANSWERED,
            "confidence": None,
        }
    ]
    summary = probe.summarise(calls)
    assert summary["overall"]["unanswered"] == 1
    assert summary["overall"]["unanswered_by_kind"] == {
        "declined_to_judge": 0,
        "read_failure": 0,
        "provider_failure": 0,
    }


def test_the_probe_records_the_kind_the_grader_reported(wav_file: Path) -> None:
    """End to end: a broken reply arrives in the call log as a read failure.

    This is the join that makes the separation real. ``core`` labels the
    failure, the probe stores the label, and the report divides by it -- so
    the next A/B answers "was it the prompt or the wire?" from its own output
    instead of from a re-analysis months later.
    """
    verdict, _ = _judge(wav_file, "not json at all")
    assert verdict.judge_error == "format_error:unparseable_json"
    assert (
        probe.unanswered_kind(verdict.verdict, verdict.judge_error)
        == probe.UNANSWERED_READ_FAILURE
    )

