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
  cap is safer).
* Graceful fallback: missing deployment, decode error, or Responses
  API exception all return ``judge_error`` rather than raising.
"""

from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

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
    """
    try:
        import av  # type: ignore
    except ImportError:
        with open(path, "rb") as fh:
            return fh.read(), _guess_format(path)

    try:
        container = av.open(path)
        try:
            stream = container.streams.audio[0]
            duration_s = (float(container.duration) / 1_000_000.0
                          if container.duration else None)
            if duration_s is None or duration_s <= max_seconds:
                with open(path, "rb") as fh:
                    return fh.read(), _guess_format(path)
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
        with open(path, "rb") as fh:
            return fh.read(), _guess_format(path)


def _guess_format(path: str) -> str:
    ext = os.path.splitext(path)[1].lstrip(".").lower()
    return ext or "wav"


@dataclass
class AudioPerception:
    client: Any
    deployment: str = "gpt-audio-1.5"
    call_cap: int = AUDIO_CALL_CAP
    trim_seconds: int = AUDIO_TRIM_SECONDS

    _calls_used: int = field(default=0, init=False)

    @property
    def calls_used(self) -> int:
        return self._calls_used

    def reset(self) -> None:
        self._calls_used = 0

    def judge(
        self,
        *,
        criterion: str,
        audio_path: str,
    ) -> AudioVerdict:
        if self._calls_used >= self.call_cap:
            return AudioVerdict(
                verdict="judge_error",
                partial_score=0.0,
                evidence="",
                confidence=0.0,
                reasoning=f"audio call cap {self.call_cap} exceeded",
                judge_error="cap_exceeded",
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
        b64 = base64.b64encode(data).decode("ascii")
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
                             "audio": {"data": b64, "format": fmt}},
                        ],
                    }
                ],
                temperature=0,
            )
            latency_ms = (time.perf_counter() - call_started) * 1000.0
            usage = getattr(response, "usage", None)
            usage_complete = usage is not None and all(
                hasattr(usage, field_name)
                for field_name in ("input_tokens", "output_tokens")
            )
            input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
            output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
            details = getattr(usage, "input_tokens_details", None)
            cached_tokens = int(getattr(details, "cached_tokens", 0) or 0)
            if details is None or not hasattr(details, "cached_tokens"):
                usage_complete = False
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
            return AudioVerdict(
                verdict="judge_error",
                partial_score=0.0,
                evidence="",
                confidence=0.0,
                reasoning=f"audio call failed: {type(exc).__name__}",
                judge_error=public_provider_error_text(exc),
                api_call_count=1,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cached_tokens=cached_tokens,
                latency_ms=latency_ms,
                usage_complete=usage_complete,
            )
