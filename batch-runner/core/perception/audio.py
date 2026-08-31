"""Audio perception sub-judge — task 206.

Used when ``core.grader_routing.classify_criterion`` returns
``Modality.AUDIO``. The main tool-calling judge calls
``AudioPerception.judge(criterion, audio_bytes, ...)`` after invoking
``read_deliverable(op='probe_audio', ...)``.

Design notes (task 206):

* Model: ``gpt-audio-1.5`` deployed on Azure OpenAI. The deployment
  must exist in the same resource group as the main judge endpoint;
  see ``tasks/rebuilding_grading_task/PR2_ENV_AUDIT.md`` for the
  deferred verification (we check on first call rather than at import
  time so missing-deployment failures are isolated to audio items).
* The client is injected from the typed grader route like in
    ``VisionPerception`` — no endpoint lookup or client construction occurs
    inside this class.
* Duration trim: only the first 30 seconds of the file are sent. If
  the audio is longer than 30 s the head-only slice keeps cost
  bounded; the main judge still has access to full-clip statistics
  via ``read_deliverable(op='probe_audio', ...)``.
* Per-task call cap = 3 (audio items are rarer than visual; smaller
  cap is safer). The cap counts *listens*, not attempts: a request the
  provider refused before running the model gives its slot back, because
  the cap bounds what a task spends and a refused request spent nothing.
  A separate failure budget is what keeps that refund from turning a bad
  endpoint into one doomed request per criterion. See
  ``tests/test_a_failed_audio_call_does_not_cost_the_task_its_turn.py``
  for why the distinction is load-bearing -- the paid smoke on run
  ``33363059548`` reported ``cap_exceeded`` on tasks that had never
  successfully listened to anything.
* Graceful fallback: missing deployment, decode error, or Responses
  API exception all return ``judge_error`` rather than raising.
* No sampling parameters. Neither the main judge nor ``VisionPerception``
  sends ``temperature`` or ``seed``; this module used to be the single
  exception, and was also the only caller whose every request came back
  400.
"""

from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Tuple

from core.cost_metering import read_reported_usage
from core.public_error import public_provider_error_text, public_task_error_text

#: How many audio sub-judge calls one task gets when the marking settings
#: name no number of their own. Not a hard ceiling: ``call_cap_per_task``
#: under ``judge.perception.audio`` replaces it, and the grader passes
#: whatever it finds there on every construction. The free cost check reads
#: it from here too, so moving it moves the ceiling with it.
AUDIO_CALL_CAP = 3

#: Seconds of audio sent to the model per call when the marking settings name
#: no ``trim_seconds`` of their own. A longer clip costs more to send, so this
#: is a price as much as a limit, and the grader reads it from here rather
#: than keeping a second copy.
AUDIO_TRIM_SECONDS = 30

#: The only container formats the Responses API accepts on an ``input_audio``
#: content part (``openai.types.responses.response_input_audio_param.InputAudio``
#: types ``format`` as ``Literal["mp3", "wav"]``). Anything else is rejected
#: with a 400 before the model is reached, so a clip that cannot be presented
#: as one of these is refused here rather than paid for and bounced.
SUPPORTED_AUDIO_FORMATS = ("mp3", "wav")

#: Largest base64 payload this class will put on the wire.
#:
#: The paid smoke on run ``33363059548`` had every audio request bounce with a
#: 400 and left two candidates standing, because a 400 body is not visible
#: without buying another call. One was ``temperature``, now gone. The other is
#: request size, and this is what rules it out: 30 s of 48 kHz stereo PCM is
#: ~5.5 MB raw and ~7.3 MB base64, so a clip anywhere near this limit is
#: already anomalous. Refused here rather than sent, on the same reasoning as
#: the format check below it -- a request that will bounce still costs the
#: wall-clock of bouncing, and the refusal names itself where a 400 does not.
#:
#: The point is not that this fires. It is that after it exists, the next
#: smoke has three distinguishable outcomes -- a verdict (it was
#: ``temperature``), ``audio_payload_too_large`` (it was size), or a 400 still
#: (it was neither, and the guessing stops).
AUDIO_MAX_REQUEST_BYTES = 20 * 1024 * 1024

#: How many failed attempts one task will make before it stops trying.
#:
#: Separate from ``call_cap`` because the two bound different things. The call
#: cap bounds *spend*, and a request the provider rejected without running the
#: model did not spend anything. This bounds *wall-clock*, which a refunded
#: call would otherwise leave unbounded: without it, a task with fourteen
#: audio criteria facing a flaky endpoint makes fourteen doomed requests
#: instead of three.
#:
#: In practice this is only ever reached by 429s. Every other rejection is
#: deterministic for the task -- same clip, same request shape, same answer --
#: and short-circuits on the first one.
AUDIO_FAILURE_BUDGET = 3

#: Provider rejections that happened before the model ran, and so were not
#: billed. Only these give a call slot back; anything else -- a timeout, a
#: 5xx, a dropped connection -- may have been billed for work we never saw,
#: and is counted as spent. The asymmetry is deliberate and points the safe
#: way: over-counting a call costs one criterion, under-counting it costs
#: money the ledger never learns about.
_UNBILLED_STATUS = frozenset({400, 401, 403, 404, 413, 415, 422, 429})

#: Rejections that will recur identically for every remaining criterion on
#: this task. The clip is the same file and the request is the same shape, so
#: a malformed request stays malformed and a missing deployment stays missing.
#: Retrying buys another identical bounce; 429 is the one that is worth
#: waiting out, which is why it is in the set above and not this one.
_DETERMINISTIC_STATUS = frozenset({400, 401, 403, 404, 413, 415, 422})


def _provider_status_code(exc: object) -> Optional[int]:
    """HTTP status behind a provider exception, or ``None`` if it is not one.

    Read defensively rather than by catching a typed exception: this module
    takes its client by injection and must not assume which SDK built it.
    """
    for probe in (
        getattr(exc, "status_code", None),
        getattr(getattr(exc, "response", None), "status_code", None),
    ):
        if isinstance(probe, int):
            return probe
    return None


@dataclass(frozen=True)
class AudioVerdict:
    verdict: str
    partial_score: float
    evidence: str
    confidence: float
    reasoning: str
    judge_error: Optional[str] = None
    api_call_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    latency_ms: float = 0.0
    usage_complete: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verdict": self.verdict,
            "partial_score": self.partial_score,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "judge_error": self.judge_error,
            "api_call_count": self.api_call_count,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cached_tokens": self.cached_tokens,
            "latency_ms": self.latency_ms,
            "usage_complete": self.usage_complete,
        }


_AUDIO_PROMPT_HEADER = (
    "You are an audio sub-judge for the GDPval grading pipeline. The "
    "clip is a head-only slice (first 30s) of the LLM-under-test's "
    "audio deliverable. Grade ONE rubric criterion against what you "
    "HEAR. Return the same JSON envelope as the main judge: "
    "{verdict, partial_score, evidence, confidence, reasoning}. The "
    "evidence MUST describe an audible feature; do not invent. Keep "
    "evidence <= 200 chars. Return JSON only."
)


def _parse_json_envelope(text: str) -> Dict[str, Any]:
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t.lower().startswith("json"):
            t = t[4:]
        t = t.strip()
    return json.loads(t)


def _trim_audio_bytes(path: str, max_seconds: int = AUDIO_TRIM_SECONDS
                      ) -> Tuple[bytes, str]:
    """Read a file and return ``(bytes, format)`` trimmed to ``max_seconds``.

    Uses PyAV (wheel bundles ffmpeg per env audit). Falls back to
    sending the raw file if PyAV cannot decode (e.g. exotic codec).

    The file is only handed over untouched when it is *known* to be short
    enough and already carries a format the API accepts. A clip whose
    duration the container does not report is re-encoded rather than sent
    whole: "no duration" is not "short", and a studio stem that declines to
    say how long it is would otherwise go out at its full size.
    """
    fmt = _guess_format(path)

    def raw() -> Tuple[bytes, str]:
        with open(path, "rb") as fh:
            return fh.read(), fmt

    try:
        import av  # type: ignore
    except ImportError:
        return raw()

    try:
        container = av.open(path)
        try:
            stream = container.streams.audio[0]
            duration_s = (float(container.duration) / 1_000_000.0
                          if container.duration else None)
            if (
                duration_s is not None
                and duration_s <= max_seconds
                and fmt in SUPPORTED_AUDIO_FORMATS
            ):
                return raw()
            # Re-encode head slice to WAV in memory.
            import io
            buf = io.BytesIO()
            out = av.open(buf, mode="w", format="wav")
            out_stream = out.add_stream("pcm_s16le", rate=stream.sample_rate)
            out_stream.layout = stream.layout
            for frame in container.decode(audio=0):
                t = float(frame.pts * frame.time_base) if frame.pts else 0.0
                if t > max_seconds:
                    break
                for packet in out_stream.encode(frame):
                    out.mux(packet)
            for packet in out_stream.encode():
                out.mux(packet)
            out.close()
            return buf.getvalue(), "wav"
        finally:
            container.close()
    except Exception:
        return raw()


def _guess_format(path: str) -> str:
    ext = os.path.splitext(path)[1].lstrip(".").lower()
    return ext or "wav"


@dataclass
class AudioPerception:
    client: Any
    deployment: str = "gpt-audio-1.5"
    call_cap: int = AUDIO_CALL_CAP
    trim_seconds: int = AUDIO_TRIM_SECONDS
    #: Zero-argument rate-limit guard, invoked immediately before every
    #: request. The grader passes its own TPM spacer here, the same one the
    #: main judge and the vision sub-judge get. Audio went without it for as
    #: long as this class has existed, which was invisible because a mistyped
    #: content part meant no audio request ever reached a model to be
    #: throttled; with the shape corrected, an unguarded reader is a reader
    #: that can spend a shard's remaining budget on 429s.
    before_upstream_call: Optional[Callable[[], None]] = None

    #: Attempts, not measurements. See :data:`AUDIO_FAILURE_BUDGET`.
    failure_budget: int = AUDIO_FAILURE_BUDGET

    _calls_used: int = field(default=0, init=False)
    _failures_used: int = field(default=0, init=False)
    #: Set when a rejection tells us every later criterion on this task will
    #: get the same one. Cleared at the task boundary with everything else.
    _blocked_reason: Optional[str] = field(default=None, init=False)

    @property
    def calls_used(self) -> int:
        return self._calls_used

    def reset(self) -> None:
        self._calls_used = 0
        self._failures_used = 0
        self._blocked_reason = None

    def _refuse(self, reason: str, judge_error: str) -> "AudioVerdict":
        """A verdict for a criterion no call was made for.

        Every early return in :meth:`judge` goes through here so they cannot
        drift apart: nothing was sent, so nothing is billed, and the usage
        this reports -- zero -- is complete rather than merely unknown.
        """
        return AudioVerdict(
            verdict="judge_error",
            partial_score=0.0,
            evidence="",
            confidence=0.0,
            reasoning=reason,
            judge_error=judge_error,
        )

    def judge(
        self,
        *,
        criterion: str,
        audio_path: str,
    ) -> AudioVerdict:
        if self._blocked_reason is not None:
            # Distinct from ``cap_exceeded`` on purpose. That one means the
            # task listened its three times; this one means the task never
            # got to listen at all. The paid smoke reported the first while
            # the second was true, and the difference is the whole reading of
            # the artifact: a budget spent, or a model that was never usable.
            return self._refuse(
                f"audio unavailable for this task: {self._blocked_reason}",
                f"audio_unavailable:{self._blocked_reason}",
            )
        if self._calls_used >= self.call_cap:
            return self._refuse(
                f"audio call cap {self.call_cap} exceeded",
                "cap_exceeded",
            )
        if self._failures_used >= self.failure_budget:
            return self._refuse(
                f"audio failure budget {self.failure_budget} exhausted",
                "audio_unavailable:repeated_failure",
            )
        try:
            data, fmt = _trim_audio_bytes(audio_path, self.trim_seconds)
        except Exception as exc:  # noqa: BLE001
            return AudioVerdict(
                verdict="judge_error",
                partial_score=0.0,
                evidence="",
                confidence=0.0,
                reasoning=f"audio preparation failed: {type(exc).__name__}",
                judge_error=public_task_error_text(exc),
            )
        if fmt not in SUPPORTED_AUDIO_FORMATS:
            # Refused before the call, not after it. The API rejects an
            # unsupported container outright, so sending it spends a slot from
            # ``call_cap`` and buys a 400. No call goes out, so nothing is
            # billed and the usage this verdict reports — zero — is complete.
            return self._refuse(
                f"unsupported audio format: {fmt}",
                "unsupported_audio_format",
            )
        b64 = base64.b64encode(data).decode("ascii")
        if len(b64) > AUDIO_MAX_REQUEST_BYTES:
            # The size candidate, named rather than guessed at. This is the
            # one shape of 400 the class can recognise on its own side of the
            # wire, so it says so instead of letting the provider say
            # ``BadRequestError`` and leaving the reader to pick between two
            # explanations. Deterministic for the task -- the next criterion
            # sends the same clip -- so it blocks the rest rather than
            # re-measuring the same file thirteen more times.
            self._blocked_reason = "payload_too_large"
            return self._refuse(
                f"audio payload {len(b64)} bytes exceeds "
                f"{AUDIO_MAX_REQUEST_BYTES}",
                "audio_payload_too_large",
            )
        if self.before_upstream_call is not None:
            self.before_upstream_call()
        # Counted before the call and given back only for rejections that
        # provably predate inference. A call that vanished into a timeout is
        # counted as spent because it may well have been.
        self._calls_used += 1
        call_started = time.perf_counter()
        input_tokens = 0
        output_tokens = 0
        cached_tokens = 0
        usage_complete = False
        try:
            response = self.client.responses.create(
                model=self.deployment,
                input=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text",
                             "text": f"{_AUDIO_PROMPT_HEADER}\n\nCriterion:\n{criterion}"},
                            {"type": "input_audio",
                             "input_audio": {"data": b64, "format": fmt}},
                        ],
                    }
                ],
            )
            latency_ms = (time.perf_counter() - call_started) * 1000.0
            reported = read_reported_usage(response)
            input_tokens = reported.input_tokens
            output_tokens = reported.output_tokens
            cached_tokens = reported.cached_tokens
            usage_complete = reported.usage_complete
            text = getattr(response, "output_text", "") or ""
            payload = _parse_json_envelope(text)
            return AudioVerdict(
                verdict=str(payload.get("verdict", "fail")),
                partial_score=float(payload.get("partial_score", 0.0)),
                evidence=str(payload.get("evidence", ""))[:200],
                confidence=float(payload.get("confidence", 0.0)),
                reasoning=str(payload.get("reasoning", ""))[:300],
                api_call_count=1,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cached_tokens=cached_tokens,
                latency_ms=latency_ms,
                usage_complete=usage_complete,
            )
        except Exception as exc:  # noqa: BLE001
            latency_ms = (time.perf_counter() - call_started) * 1000.0
            status = _provider_status_code(exc)
            if status in _UNBILLED_STATUS:
                # Give the slot back. ``call_cap`` is there to bound what a
                # task spends and to make every task spend it on the same
                # scale; a request the provider refused before running the
                # model spent nothing and measured nothing, so charging it
                # does neither job. It only takes the criterion's turn away.
                self._calls_used -= 1
                self._failures_used += 1
            if status in _DETERMINISTIC_STATUS:
                # The rest of this task's criteria would send the same clip in
                # the same shape and get the same answer. Recorded once, and
                # the remainder refused honestly by name rather than after two
                # more identical bounces.
                self._blocked_reason = f"provider_{status}"
            return AudioVerdict(
                verdict="judge_error",
                partial_score=0.0,
                evidence="",
                confidence=0.0,
                reasoning=(
                    f"audio call failed: {type(exc).__name__}"
                    f" (status={status}, format={fmt}, b64_bytes={len(b64)})"
                ),
                judge_error=public_provider_error_text(exc),
                api_call_count=1,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cached_tokens=cached_tokens,
                latency_ms=latency_ms,
                usage_complete=usage_complete,
            )
