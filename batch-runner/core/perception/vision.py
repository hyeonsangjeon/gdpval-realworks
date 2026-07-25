"""Vision perception sub-judge — task 205.

Used when ``core.grader_routing.classify_criterion`` returns
``Modality.VISUAL``. The main tool-calling judge calls
``VisionPerception.judge(criterion, image_b64, ...)`` after invoking
``read_deliverable(op='render_to_image', ...)``; the returned dict is
appended to the judge's evidence chain.

Design notes (task 205):

* Config-selected Azure deployment. Production uses GPT-5.6 Sol Max and
    historical comparison configs retain their original model identities.
* The client is **injected**, never constructed inside this class. The
  main judge owns the Responses API client and shares it; tests pass a
  ``FakeClient``.
* Image cache: ``(path, page)`` rendered once per task and reused —
  prevents the judge from burning tokens re-rendering the same chart
  on a second item.
* The generic wrapper default cap is 5; production config explicitly raises it
    to 72 after checking the 220-task visual inventory. The harness preflights
    the full bounded plan before rendering.
* Graceful degradation on dependency errors: a corrupt PNG or a
  Responses-API exception returns ``judge_error`` rather than raising.
"""

from __future__ import annotations

import base64
import json
import logging
import math
import time
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Dict, Optional

from core.public_error import public_provider_error_text

logger = logging.getLogger(__name__)

#: Hard per-task ceiling on vision sub-judge invocations.
VISION_CALL_CAP = 5


@dataclass(frozen=True)
class VisionVerdict:
    verdict: str            # 'pass' | 'partial' | 'fail' | 'judge_error'
    partial_score: float
    evidence: str           # <=200 chars, model-supplied observation
    confidence: float
    reasoning: str
    judge_error: Optional[str] = None  # set when verdict == 'judge_error'
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


# Prompt shown to the vision sub-judge. Kept inline (small, scoped) —
# not in prompts/ because it has no harness placeholders.
_VISION_PROMPT_HEADER = (
    "You are a vision sub-judge for the GDPval grading pipeline. The "
    "image below is a rendered page/sheet from the LLM-under-test's "
    "deliverable. Grade ONE rubric criterion against what you SEE in "
    "the image only. Return exactly one JSON object with these keys: "
    "verdict, partial_score, evidence, confidence, reasoning. verdict "
    "must be one of the lowercase strings pass, partial, or fail. "
    "partial_score must be 1.0 for pass, 0.0 for fail, or strictly "
    "between 0.0 and 1.0 for partial. confidence must be a number from "
    "0.0 through 1.0. evidence MUST describe a visible feature (for "
    "example, 'x-axis labels truncated' or 'no chart title'); do not "
    "invent text not present in the image. Keep evidence within 200 "
    "characters and reasoning within 300 characters. Return JSON only, "
    "without Markdown fences or extra text."
)


def _parse_json_envelope(text: str) -> Dict[str, Any]:
    """Strip code fences, parse JSON, raise ValueError on malformed."""
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t.lower().startswith("json"):
            t = t[4:]
        t = t.strip()
    return json.loads(t)


class InvalidVisionEnvelope(ValueError):
    """Raised when the vision model returns a syntactically valid bad grade."""


def _validate_vision_envelope(text: str) -> Dict[str, Any]:
    try:
        parsed = _parse_json_envelope(text)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise InvalidVisionEnvelope("response is not valid JSON") from exc
    if not isinstance(parsed, Mapping):
        raise InvalidVisionEnvelope("response must be a JSON object")

    verdict_raw = parsed.get("verdict")
    verdict = (
        verdict_raw.strip().lower()
        if isinstance(verdict_raw, str)
        else verdict_raw
    )
    if verdict not in {"pass", "partial", "fail"}:
        raise InvalidVisionEnvelope("verdict must be pass, partial, or fail")

    partial_raw = parsed.get("partial_score")
    confidence_raw = parsed.get("confidence")
    if isinstance(partial_raw, bool) or not isinstance(partial_raw, (int, float)):
        raise InvalidVisionEnvelope("partial_score must be a number")
    if isinstance(confidence_raw, bool) or not isinstance(
        confidence_raw, (int, float)
    ):
        raise InvalidVisionEnvelope("confidence must be a number")
    partial = float(partial_raw)
    confidence = float(confidence_raw)
    if not math.isfinite(partial) or not 0.0 <= partial <= 1.0:
        raise InvalidVisionEnvelope("partial_score must be within [0, 1]")
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        raise InvalidVisionEnvelope("confidence must be within [0, 1]")
    if (
        (verdict == "pass" and partial != 1.0)
        or (verdict == "fail" and partial != 0.0)
        or (verdict == "partial" and not 0.0 < partial < 1.0)
    ):
        raise InvalidVisionEnvelope("verdict and partial_score are inconsistent")

    evidence = parsed.get("evidence")
    reasoning = parsed.get("reasoning")
    if not isinstance(evidence, str) or not evidence.strip():
        raise InvalidVisionEnvelope("evidence must be a non-empty string")
    if not isinstance(reasoning, str) or not reasoning.strip():
        raise InvalidVisionEnvelope("reasoning must be a non-empty string")

    return {
        "verdict": verdict,
        "partial_score": partial,
        "evidence": evidence.strip()[:200],
        "confidence": confidence,
        "reasoning": reasoning.strip()[:300],
    }


@dataclass
class VisionPerception:
    """Thin Responses-API wrapper for image-grounded item judgment.

    Args:
        client:       any object exposing ``responses.create(**kwargs)`` ->
                      ``response.output_text`` (Azure OpenAI Responses API
                      shape; tests pass a fake with the same shape).
        deployment:   Azure deployment name (e.g. ``"gpt-5.6-sol"`` with
                      vision enabled).
        call_cap:     optional override (default ``VISION_CALL_CAP``).
        reasoning_effort: optional Responses API reasoning effort.
    """

    client: Any
    deployment: str = "gpt-5.4"
    call_cap: int = VISION_CALL_CAP
    reasoning_effort: str = "medium"
    before_upstream_call: Optional[Callable[[], None]] = None

    _calls_used: int = field(default=0, init=False)
    _cache: Dict[str, VisionVerdict] = field(default_factory=dict, init=False)

    @property
    def calls_used(self) -> int:
        return self._calls_used

    @property
    def remaining_calls(self) -> int:
        return max(0, self.call_cap - self._calls_used)

    def reset(self) -> None:
        """Clear per-task call counter and image cache."""
        self._calls_used = 0
        self._cache.clear()

    def judge(
        self,
        *,
        criterion: str,
        image_b64: str,
        cache_key: Optional[str] = None,
    ) -> VisionVerdict:
        """Run the vision sub-judge against a single criterion."""
        if cache_key is not None and cache_key in self._cache:
            return replace(
                self._cache[cache_key],
                api_call_count=0,
                input_tokens=0,
                output_tokens=0,
                cached_tokens=0,
                latency_ms=0.0,
            )

        if self._calls_used >= self.call_cap:
            verdict = VisionVerdict(
                verdict="judge_error",
                partial_score=0.0,
                evidence="",
                confidence=0.0,
                reasoning=f"vision call cap {self.call_cap} exceeded",
                judge_error="cap_exceeded",
            )
            if cache_key is not None:
                self._cache[cache_key] = verdict
            return verdict

        # Best-effort sanity on the base64 payload — corrupt input is
        # a graceful judge_error, not an unhandled exception.
        try:
            raw = base64.b64decode(image_b64, validate=True)
            if not raw.startswith((b"\x89PNG", b"\xff\xd8", b"GIF8", b"RIFF")):
                raise ValueError("not a recognized image header")
        except Exception as exc:  # noqa: BLE001
            return VisionVerdict(
                verdict="judge_error",
                partial_score=0.0,
                evidence="",
                confidence=0.0,
                reasoning=f"corrupt image payload: {exc}",
                judge_error="bad_image",
            )

        call_started = 0.0
        api_attempted = False
        input_tokens = 0
        output_tokens = 0
        cached_tokens = 0
        usage_complete = False
        try:
            if self.before_upstream_call is not None:
                self.before_upstream_call()
            call_started = time.perf_counter()
            api_attempted = True
            self._calls_used += 1
            response = self.client.responses.create(
                model=self.deployment,
                input=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text",
                             "text": f"{_VISION_PROMPT_HEADER}\n\nCriterion:\n{criterion}"},
                            {"type": "input_image",
                             "image_url": f"data:image/png;base64,{image_b64}"},
                        ],
                    }
                ],
                reasoning={"effort": self.reasoning_effort},
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
            payload = _validate_vision_envelope(text)
            verdict = VisionVerdict(
                verdict=payload["verdict"],
                partial_score=payload["partial_score"],
                evidence=payload["evidence"],
                confidence=payload["confidence"],
                reasoning=payload["reasoning"],
                api_call_count=1,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cached_tokens=cached_tokens,
                latency_ms=latency_ms,
                usage_complete=usage_complete,
            )
        except InvalidVisionEnvelope as exc:
            logger.warning(
                "Vision response failed envelope validation (%s)",
                type(exc).__name__,
            )
            latency_ms = (
                (time.perf_counter() - call_started) * 1000.0
                if call_started else 0.0
            )
            verdict = VisionVerdict(
                verdict="judge_error",
                partial_score=0.0,
                evidence="",
                confidence=0.0,
                reasoning="invalid vision response envelope",
                judge_error="invalid_vision_envelope",
                api_call_count=int(api_attempted),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cached_tokens=cached_tokens,
                latency_ms=latency_ms,
                usage_complete=usage_complete,
            )
        except Exception as exc:  # noqa: BLE001
            latency_ms = (
                (time.perf_counter() - call_started) * 1000.0
                if call_started else 0.0
            )
            verdict = VisionVerdict(
                verdict="judge_error",
                partial_score=0.0,
                evidence="",
                confidence=0.0,
                reasoning=f"vision call failed: {type(exc).__name__}",
                judge_error=public_provider_error_text(exc),
                api_call_count=int(api_attempted),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cached_tokens=cached_tokens,
                latency_ms=latency_ms,
                usage_complete=usage_complete,
            )
        if cache_key is not None:
            self._cache[cache_key] = verdict
        return verdict
