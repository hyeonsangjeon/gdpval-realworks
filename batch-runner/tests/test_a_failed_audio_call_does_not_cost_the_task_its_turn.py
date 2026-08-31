"""A cap that bounds spending, being spent by calls that cost nothing.

The paid smoke on run ``33363059548`` routed all 21 damaged criteria to the
listening model, exactly as PR #276 intended, and then produced two evidence
strings and no verdicts::

    audio_perception_failed:provider_error:BadRequestError   x3 per task
    audio_perception_failed:cap_exceeded                     everything after

The second line is the defect this module is about. ``AUDIO_CALL_CAP = 3`` is
a per-task budget, ``_calls_used`` was incremented before the request, and a
request that raised never gave the slot back. So three rejections exhausted a
task's entire audio budget and every remaining criterion was refused without
being attempted: ``e222075d`` got one of its seven criteria tried, and the
other six were marked against a budget that had bought nothing.

Two things are wrong there and they are worth separating.

**The accounting is wrong.** The cap exists to bound what a task spends, and
a request the provider refused before running the model spent nothing. It is
also, per ``305-resume-granularity.md``, a fairness instrument -- every task
gets the same number of listens so every task is marked with the same
instrument -- and a task that listened zero times has not used its three.

**The report is wrong, which is worse.** ``cap_exceeded`` says the task used
its budget. Read off the artifact it means "we listened three times and
stopped", and someone tuning the cap upward would have been acting on a
number that described nothing. What was true is that the model was never
usable at all.

So the fix is two-sided, and both sides are held here:

* a rejection that provably predates inference gives the slot back, while a
  timeout or a 5xx -- which may have been billed for work nobody saw -- stays
  charged;
* a rejection that will recur identically for the rest of the task stops it
  once, by name, instead of after two more identical bounces.

The refund alone would be a regression. Handing the slot back on every
failure turns a flaky endpoint into fourteen doomed requests where there were
three, so the refund only exists alongside a bounded failure budget and the
short-circuit. The negative controls below are the ones that matter most:
successes must still hit the cap, or the fairness property the cap was for is
gone.

Nothing here calls a model.

Spec: tasks/rebuilding_grading_task/307-audio-smoke-result.md
"""

from __future__ import annotations

import struct
import sys
import wave
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.perception.audio import (  # noqa: E402
    AUDIO_CALL_CAP,
    AUDIO_FAILURE_BUDGET,
    AUDIO_MAX_REQUEST_BYTES,
    AudioPerception,
)


class ProviderError(Exception):
    """A provider exception carrying a status, the way the SDK's do.

    ``openai``'s errors expose ``status_code``; this reproduces that surface
    without importing the SDK's exception hierarchy, because the class under
    test reads the attribute defensively and must keep working for any client
    that was injected into it.
    """

    def __init__(self, status_code: int | None) -> None:
        super().__init__(f"provider said {status_code}")
        if status_code is not None:
            self.status_code = status_code


class BadRequestError(ProviderError):
    """Named to match the smoke's evidence string. See the sibling module."""

    def __init__(self) -> None:
        super().__init__(400)


class _Responses:
    """Answers ``n_ok`` requests, then raises ``error_factory`` forever.

    Defaults to raising immediately, which is the smoke's endpoint.
    """

    def __init__(self, *, n_ok: int = 0, error_factory=BadRequestError) -> None:
        self.calls: list[dict] = []
        self._n_ok = n_ok
        self._error_factory = error_factory

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) <= self._n_ok:
            return _Reply()
        raise self._error_factory()


class _Reply:
    output_text = (
        '{"verdict": "pass", "partial_score": 1.0, "evidence": "clear",'
        ' "confidence": 0.9, "reasoning": "audible"}'
    )
    usage = None


class _Client:
    def __init__(self, responses) -> None:
        self.responses = responses


@pytest.fixture
def wav_file(tmp_path: Path) -> Path:
    p = tmp_path / "stem.wav"
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(
            b"".join(struct.pack("<h", (i % 50) * 300) for i in range(8000))
        )
    return p


def _judge_n(perception: AudioPerception, path: Path, n: int) -> list:
    """Mark ``n`` criteria on one task, the way a rubric would."""
    return [
        perception.judge(criterion=f"criterion {i}", audio_path=str(path))
        for i in range(n)
    ]


# ── the refund, and the case it must not cover ───────────────────────


def test_a_provider_rejection_gives_the_call_slot_back(wav_file):
    """A 400 is not a listen, so it does not spend one."""
    responses = _Responses()
    perception = AudioPerception(client=_Client(responses))

    verdict = perception.judge(criterion="c", audio_path=str(wav_file))

    assert verdict.judge_error == "provider_error:BadRequestError"
    assert len(responses.calls) == 1, "the call was made"
    assert perception.calls_used == 0, (
        "a request the provider refused before running the model spent "
        "nothing; charging it against a spending cap takes a criterion's "
        "turn away to pay for a bill that does not exist"
    )


@pytest.mark.parametrize("status", [None, 500, 502, 503, 504])
def test_a_failure_that_may_have_been_billed_stays_charged(wav_file, status):
    """The negative control on the refund, and the reason it is narrow.

    A 5xx or a dropped connection can arrive *after* the model ran. There is
    no way in-process to tell a server error from a lost reply to work that
    was done and billed, so the slot stays spent. Over-charging costs the task
    one criterion; under-charging costs money that never reaches the ledger,
    and only one of those two errors is recoverable.
    """
    responses = _Responses(error_factory=lambda: ProviderError(status))
    perception = AudioPerception(client=_Client(responses))

    perception.judge(criterion="c", audio_path=str(wav_file))

    assert perception.calls_used == 1, (
        f"status {status} cannot be shown to predate inference and must not "
        "be refunded"
    )


# ── the short-circuit ────────────────────────────────────────────────


def test_the_smoke_scenario_now_names_what_actually_happened(wav_file):
    """The headline: replay ``75401f7c``'s fourteen criteria against a 400.

    Before, this produced three requests and eleven ``cap_exceeded`` -- a
    report of a budget spent, on a task that never heard anything. Now it
    produces one request and thirteen refusals that say the model was
    unavailable, which is what was true.
    """
    responses = _Responses()
    perception = AudioPerception(client=_Client(responses))

    verdicts = _judge_n(perception, wav_file, 14)

    assert len(responses.calls) == 1, (
        "the same clip in the same shape gets the same 400; the other "
        "thirteen requests buy nothing but wall-clock"
    )
    assert verdicts[0].judge_error == "provider_error:BadRequestError"
    assert all(v.judge_error == "audio_unavailable:provider_400"
               for v in verdicts[1:])
    assert not any(v.judge_error == "cap_exceeded" for v in verdicts), (
        "no criterion may be told the budget ran out on a task that never "
        "spent any of it"
    )
    assert all(v.verdict == "judge_error" for v in verdicts), (
        "an unanswered criterion is an error, never a fault in the "
        "deliverable"
    )
    assert perception.calls_used == 0


def test_a_missing_deployment_stops_the_task_the_same_way(wav_file):
    """404 is deterministic for the same reason 400 is: it will not change."""
    responses = _Responses(error_factory=lambda: ProviderError(404))
    perception = AudioPerception(client=_Client(responses))

    verdicts = _judge_n(perception, wav_file, 5)

    assert len(responses.calls) == 1
    assert all(v.judge_error == "audio_unavailable:provider_404"
               for v in verdicts[1:])


def test_a_rate_limit_is_worth_retrying_but_not_forever(wav_file):
    """429 is the one rejection that might succeed next time.

    So it is refunded like the others but does not stop the task -- and the
    failure budget is what keeps "does not stop the task" from meaning
    "retries once per criterion for the rest of the rubric".
    """
    responses = _Responses(error_factory=lambda: ProviderError(429))
    perception = AudioPerception(client=_Client(responses))

    verdicts = _judge_n(perception, wav_file, 12)

    assert len(responses.calls) == AUDIO_FAILURE_BUDGET, (
        "a throttled endpoint gets a bounded number of attempts, not one per "
        "criterion"
    )
    assert perception.calls_used == 0, "no 429 was billed"
    assert verdicts[-1].judge_error == "audio_unavailable:repeated_failure"
    assert not any(v.judge_error == "cap_exceeded" for v in verdicts)


def test_the_task_boundary_clears_the_block(wav_file):
    """A block is about one task's clip, so it dies with that task.

    ``reset`` is called from ``reset_perception`` at every task boundary. If
    the block outlived it, one bad deliverable would silence the audio path
    for a whole shard.
    """
    responses = _Responses()
    perception = AudioPerception(client=_Client(responses))
    _judge_n(perception, wav_file, 3)
    assert len(responses.calls) == 1

    perception.reset()
    perception.judge(criterion="next task", audio_path=str(wav_file))

    assert len(responses.calls) == 2, "the next task gets its own attempt"


# ── the negative controls: what must not have been weakened ──────────


def test_successful_listens_still_stop_at_the_cap(wav_file):
    """The fairness property the cap exists for, unchanged.

    This is the control that matters. Everything above hands slots back, and
    a refund written one line too broadly would hand back the successful ones
    too -- at which point a task with fourteen audio criteria listens fourteen
    times while its neighbour listens three, and the two are no longer marked
    with the same instrument. ``305`` states that invariant as B-1.
    """
    responses = _Responses(n_ok=99)
    perception = AudioPerception(client=_Client(responses))

    verdicts = _judge_n(perception, wav_file, 8)

    assert len(responses.calls) == AUDIO_CALL_CAP == 3
    assert perception.calls_used == 3
    assert [v.verdict for v in verdicts[:3]] == ["pass", "pass", "pass"]
    assert all(v.judge_error == "cap_exceeded" for v in verdicts[3:]), (
        "a task that really did use its listens is told exactly that; "
        "cap_exceeded keeps its meaning by only ever being true"
    )


def test_a_recovered_endpoint_still_owes_its_earlier_failures_nothing(wav_file):
    """Refunded failures must not add up to extra listens.

    Two 429s then successes: the task still gets three listens, not five. The
    failure budget and the call cap are separate counters precisely so that
    spending one cannot top up the other.
    """
    responses = _Responses()

    def create(**kwargs):
        responses.calls.append(kwargs)
        if len(responses.calls) <= 2:
            raise ProviderError(429)
        return _Reply()

    responses.create = create  # type: ignore[method-assign]
    perception = AudioPerception(client=_Client(responses))

    verdicts = _judge_n(perception, wav_file, 9)

    assert perception.calls_used == AUDIO_CALL_CAP
    assert sum(1 for v in verdicts if v.verdict == "pass") == 3, (
        "three listens, the same as a task whose endpoint never faltered"
    )


# ── the size candidate, named rather than guessed at ─────────────────


def test_an_oversized_payload_is_refused_by_name_and_never_sent(
    wav_file, monkeypatch
):
    """The second 400 candidate, made distinguishable from the first.

    A 400 body is not readable without buying a call, so the smoke could not
    say whether ``temperature`` or request size caused it. After this, the
    next smoke has three distinguishable outcomes rather than one ambiguous
    one: a verdict, this named refusal, or a 400 that is neither.
    """
    monkeypatch.setattr(
        "core.perception.audio.AUDIO_MAX_REQUEST_BYTES", 128
    )
    responses = _Responses(n_ok=99)
    perception = AudioPerception(client=_Client(responses))

    verdicts = _judge_n(perception, wav_file, 4)

    assert responses.calls == [], "nothing oversized goes on the wire"
    assert verdicts[0].judge_error == "audio_payload_too_large"
    assert "128" in verdicts[0].reasoning, "the refusal states the limit it hit"
    assert all(v.judge_error == "audio_unavailable:payload_too_large"
               for v in verdicts[1:]), (
        "the next criterion sends the same clip, so re-measuring it three "
        "more times answers a question already answered"
    )
    assert perception.calls_used == 0


def test_the_size_limit_leaves_an_ordinary_clip_alone(wav_file):
    """Negative control: the guard must not become the failure it prevents.

    Thirty seconds of 48 kHz stereo is ~7.3 MB base64. A limit set anywhere
    near real payloads would refuse every clip and look, from the artifact,
    exactly like the outage it was written to rule out.
    """
    assert AUDIO_MAX_REQUEST_BYTES >= 16 * 1024 * 1024

    responses = _Responses(n_ok=99)
    perception = AudioPerception(client=_Client(responses))

    verdict = perception.judge(criterion="c", audio_path=str(wav_file))

    assert verdict.verdict == "pass"
    assert len(responses.calls) == 1


def test_no_sampling_parameter_reaches_the_audio_model(wav_file):
    """The convention the rest of the grading path already follows.

    Neither the main judge nor ``VisionPerception`` sends ``temperature`` or
    ``seed`` to the Responses API. Audio was the only caller that did, and it
    is the only caller whose every request was rejected. Pinned here as well
    as in ``test_perception_audio`` because that module checks the shape of
    the content part and this one checks what the call is allowed to carry
    around it.
    """
    responses = _Responses(n_ok=99)
    perception = AudioPerception(client=_Client(responses))

    perception.judge(criterion="c", audio_path=str(wav_file))

    sent = responses.calls[0]
    assert "temperature" not in sent
    assert "seed" not in sent
    assert "top_p" not in sent
