"""A cap that bounds spending, being spent by calls that cost nothing.

The paid smoke on run ``33363059548`` routed all 21 damaged criteria to the
listening model, exactly as PR #276 intended, and then produced two evidence
strings and no verdicts::

    audio_perception_failed:provider_error:BadRequestError   x3 per task
    audio_perception_failed:cap_exceeded                     everything after

The first line has since been explained and removed at its source: audio was
being sent to the Responses API, whose content union is text, image and file
and has no audio member, so every request was malformed at any size and no
model ever heard a second of the corpus. That fix lives in
``core/perception/audio.py`` and is guarded by
``tests/test_audio_goes_to_the_endpoint_that_accepts_it.py``.

The second line is the defect this module is about, and it survives the
explanation of the first. ``AUDIO_CALL_CAP`` is a per-task budget,
``_calls_used`` was incremented before the request, and a request that raised
never gave the slot back. So three rejections exhausted a task's entire audio
budget and every remaining criterion was refused without being attempted:
``e222075d`` got one of its seven criteria tried, and the other six were
marked against a budget that had bought nothing. Nothing in that accounting
depends on *why* the three failed, which is why correcting the endpoint
retires none of it.

Two things are wrong there and they are worth separating.

**The accounting is wrong.** The cap exists to bound what a task spends, and
a request the provider refused before running the model spent nothing. It is
also, per ``305-resume-granularity.md``, a fairness instrument -- every task
gets the same number of listens so every task is marked with the same
instrument -- and a task that listened zero times has not used its budget.

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
  once, by name, instead of after 31 more identical bounces.

The refund alone would be a regression. Handing the slot back on every
failure turns a flaky endpoint into a doomed request per criterion, so the
refund only exists alongside a bounded failure budget and the short-circuit.
Raising the cap from three to 32 is what makes that pairing load-bearing
rather than merely tidy: the worst case it prevents grew by the same factor
the cap did. The negative controls below are the ones that matter most:
successes must still stop at the cap, or the fairness property the cap was
for is gone.

Nothing here calls a model.

Spec: tasks/rebuilding_grading_task/307-audio-smoke-result.md
"""

from __future__ import annotations

import struct
import sys
import wave
from pathlib import Path
from types import SimpleNamespace

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


def _reply():
    """A Chat Completions reply, in the shape ``_first_choice_text`` reads.

    Not the flattened ``output_text`` the Responses API offers. Spelling it
    out this way is deliberate: a double that answered both shapes would let a
    return to the wrong endpoint go on passing here, which is exactly how the
    suite missed the defect the first time.
    """
    body = (
        '{"verdict": "pass", "partial_score": 1.0, "evidence": "clear",'
        ' "confidence": 0.9, "reasoning": "audible"}'
    )
    message = SimpleNamespace(content=body, audio=None)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)],
                           usage=None)


class _Completions:
    """Answers ``n_ok`` requests, then raises ``error_factory`` forever.

    Defaults to raising immediately, which is what the smoke saw.
    """

    def __init__(self, *, n_ok: int = 0, error_factory=BadRequestError) -> None:
        self.calls: list[dict] = []
        self._n_ok = n_ok
        self._error_factory = error_factory

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) <= self._n_ok:
            return _reply()
        raise self._error_factory()


class _Client:
    """Offers Chat Completions and nothing else.

    It carries no ``responses`` attribute on purpose, so a call routed back to
    the endpoint that cannot accept audio raises ``AttributeError`` here
    rather than being quietly answered by a fake.
    """

    def __init__(self, completions) -> None:
        self.chat = SimpleNamespace(completions=completions)


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
    completions = _Completions()
    perception = AudioPerception(client=_Client(completions))

    verdict = perception.judge(criterion="c", audio_path=str(wav_file))

    assert verdict.judge_error == "provider_error:BadRequestError"
    assert len(completions.calls) == 1, "the call was made"
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
    completions = _Completions(error_factory=lambda: ProviderError(status))
    perception = AudioPerception(client=_Client(completions))

    perception.judge(criterion="c", audio_path=str(wav_file))

    assert perception.calls_used == 1, (
        f"status {status} cannot be shown to predate inference and must not "
        "be refunded"
    )


# ── the short-circuit ────────────────────────────────────────────────


def test_the_smoke_scenario_now_names_what_actually_happened(wav_file):
    """The headline: replay ``75401f7c``'s fourteen criteria against a 400.

    Under the cap of three in force at the time, this produced three requests
    and eleven ``cap_exceeded`` -- a report of a budget spent, on a task that
    never heard anything. Now it produces one request and thirteen refusals
    that say the model was unavailable, which is what was true.

    The cap that replaced it is 32, so the arithmetic of the old failure is
    worth restating at the new size: without the short-circuit this task would
    make fourteen doomed requests instead of three, and ``ff85ee58``, which
    has 32 listening criteria, would make 32.
    """
    completions = _Completions()
    perception = AudioPerception(client=_Client(completions))

    verdicts = _judge_n(perception, wav_file, 14)

    assert len(completions.calls) == 1, (
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
    completions = _Completions(error_factory=lambda: ProviderError(404))
    perception = AudioPerception(client=_Client(completions))

    verdicts = _judge_n(perception, wav_file, 5)

    assert len(completions.calls) == 1
    assert all(v.judge_error == "audio_unavailable:provider_404"
               for v in verdicts[1:])


def test_a_rate_limit_is_worth_retrying_but_not_forever(wav_file):
    """429 is the one rejection that might succeed next time.

    So it is refunded like the others but does not stop the task -- and the
    failure budget is what keeps "does not stop the task" from meaning
    "retries once per criterion for the rest of the rubric". At a cap of 32
    that difference is 32 attempts against three.
    """
    completions = _Completions(error_factory=lambda: ProviderError(429))
    perception = AudioPerception(client=_Client(completions))

    verdicts = _judge_n(perception, wav_file, 12)

    assert len(completions.calls) == AUDIO_FAILURE_BUDGET, (
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
    completions = _Completions()
    perception = AudioPerception(client=_Client(completions))
    _judge_n(perception, wav_file, 3)
    assert len(completions.calls) == 1

    perception.reset()
    perception.judge(criterion="next task", audio_path=str(wav_file))

    assert len(completions.calls) == 2, "the next task gets its own attempt"


# ── the negative controls: what must not have been weakened ──────────


def test_successful_listens_still_stop_at_the_cap(wav_file):
    """The fairness property the cap exists for, unchanged.

    This is the control that matters. Everything above hands slots back, and
    a refund written one line too broadly would hand back the successful ones
    too -- at which point a task with 40 audio criteria listens 40 times while
    its neighbour listens twice, and the two are no longer marked with the
    same instrument. ``305`` states that invariant as B-1.

    The cap is read from the constant rather than written out, because what
    this pins is that the number is honoured. The number itself is pinned
    against the corpus that chose it in ``test_perception_audio``.
    """
    completions = _Completions(n_ok=99)
    perception = AudioPerception(client=_Client(completions))

    verdicts = _judge_n(perception, wav_file, AUDIO_CALL_CAP + 2)

    assert len(completions.calls) == AUDIO_CALL_CAP
    assert perception.calls_used == AUDIO_CALL_CAP
    assert all(v.verdict == "pass" for v in verdicts[:AUDIO_CALL_CAP])
    assert all(v.judge_error == "cap_exceeded"
               for v in verdicts[AUDIO_CALL_CAP:]), (
        "a task that really did use its listens is told exactly that; "
        "cap_exceeded keeps its meaning by only ever being true"
    )


def test_a_recovered_endpoint_still_owes_its_earlier_failures_nothing(wav_file):
    """Refunded failures must not add up to extra listens.

    Two 429s then successes: the task still gets its cap, not its cap plus
    two. The failure budget and the call cap are separate counters precisely
    so that spending one cannot top up the other.
    """
    completions = _Completions()

    def create(**kwargs):
        completions.calls.append(kwargs)
        if len(completions.calls) <= 2:
            raise ProviderError(429)
        return _reply()

    completions.create = create  # type: ignore[method-assign]
    perception = AudioPerception(client=_Client(completions))

    verdicts = _judge_n(perception, wav_file, AUDIO_CALL_CAP + 4)

    assert perception.calls_used == AUDIO_CALL_CAP
    assert sum(1 for v in verdicts if v.verdict == "pass") == AUDIO_CALL_CAP, (
        "the same number of listens as a task whose endpoint never faltered"
    )


# ── the size candidate, ruled out rather than guarded against ────────


def test_an_oversized_payload_is_refused_by_name_and_never_sent(
    wav_file, monkeypatch
):
    """The other candidate for the smoke's 400, kept as a guard once ruled out.

    A 400 body is not readable without buying a call, so at the time the smoke
    ran, request size and the endpoint both fitted the evidence. The endpoint
    is now known to be the cause -- the Responses content union has no audio
    member, so the request was malformed at any size -- and this check earns
    its place on a different argument: a payload the class can measure on its
    own side of the wire should be named here rather than sent and refused,
    because a provider's 400 will not say which of the two it was.
    """
    monkeypatch.setattr(
        "core.perception.audio.AUDIO_MAX_REQUEST_BYTES", 128
    )
    completions = _Completions(n_ok=99)
    perception = AudioPerception(client=_Client(completions))

    verdicts = _judge_n(perception, wav_file, 4)

    assert completions.calls == [], "nothing oversized goes on the wire"
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

    A limit set anywhere near real payloads would refuse every clip and look,
    from the artifact, exactly like the outage it was written to rule out.
    Thirty seconds re-encoded to 16 kHz mono is ~1.28 MB of base64, and the
    untouched studio stems that shape replaced were ~7.7 MB, so the limit sits
    an order of magnitude clear of both.
    """
    assert AUDIO_MAX_REQUEST_BYTES >= 16 * 1024 * 1024

    completions = _Completions(n_ok=99)
    perception = AudioPerception(client=_Client(completions))

    verdict = perception.judge(criterion="c", audio_path=str(wav_file))

    assert verdict.verdict == "pass"
    assert len(completions.calls) == 1


def test_no_sampling_parameter_reaches_the_audio_model(wav_file):
    """The convention the rest of the grading path already follows.

    Neither the main judge nor ``VisionPerception`` sends ``temperature`` or
    ``seed``, and audio was the only caller that did. It was suspected of
    being a third defect and it was not one: Chat Completions accepts
    ``temperature`` on an audio-capable deployment, and the requests were
    failing for a reason that had nothing to do with it. Dropping it is a
    consistency argument rather than a fix -- a path with no successful call
    anywhere in its history should send the smallest request that can do the
    job.

    Pinned here as well as in ``test_perception_audio`` because that module
    checks the shape of the content part and this one checks what the call is
    allowed to carry around it.
    """
    completions = _Completions(n_ok=99)
    perception = AudioPerception(client=_Client(completions))

    perception.judge(criterion="c", audio_path=str(wav_file))

    sent = completions.calls[0]
    assert "temperature" not in sent
    assert "seed" not in sent
    assert "top_p" not in sent
