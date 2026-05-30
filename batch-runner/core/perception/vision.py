"""Vision perception sub-judge — task 205.

Used when ``core.grader_routing.classify_criterion`` returns
``Modality.VISUAL``. The main tool-calling judge calls
``VisionPerception.judge(criterion, image_b64, ...)`` after invoking
``read_deliverable(op='render_to_image', ...)``; the returned dict is
appended to the judge's evidence chain.

Design notes (task 205):

* Same Azure deployment as the main judge — gpt-5.4 with vision
  enabled. No separate model key.
* The client is **injected**, never constructed inside this class. The
  main judge owns the Responses API client and shares it; tests pass a
  ``FakeClient``.
* Image cache: ``(path, page)`` rendered once per task and reused —
  prevents the judge from burning tokens re-rendering the same chart
  on a second item.
* Per-task call cap = 5. A sixth ``judge`` call short-circuits with a
  ``judge_error="cap_exceeded"`` verdict so the main judge can fall
  back to text+formatting evidence.
* Graceful degradation on dependency errors: a corrupt PNG or a
  Responses-API exception returns ``judge_error`` rather than raising.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verdict": self.verdict,
            "partial_score": self.partial_score,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "judge_error": self.judge_error,
        }


# Prompt shown to the vision sub-judge. Kept inline (small, scoped) —
# not in prompts/ because it has no harness placeholders.
_VISION_PROMPT_HEADER = (
    "You are a vision sub-judge for the GDPval grading pipeline. The "
    "image below is a rendered page/sheet from the LLM-under-test's "
    "deliverable. Grade ONE rubric criterion against what you SEE in "
    "the image only. Return the same JSON envelope as the main judge: "
    "{verdict, partial_score, evidence, confidence, reasoning}. The "
    "evidence MUST describe a visible feature (e.g., 'x-axis labels "
    "truncated', 'no chart title'); do not invent text not present in "
    "the image. Keep evidence <= 200 chars. Return JSON only."
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


@dataclass
class VisionPerception:
    """Thin Responses-API wrapper for image-grounded item judgment.

    Args:
        client:       any object exposing ``responses.create(**kwargs)`` ->
                      ``response.output_text`` (Azure OpenAI Responses API
                      shape; tests pass a fake with the same shape).
        deployment:   Azure deployment name (e.g. ``"gpt-5.4"`` with
                      vision enabled).
        call_cap:     optional override (default ``VISION_CALL_CAP``).
        reasoning_effort: optional ``"low" | "medium" | "high"``.
    """

    client: Any
    deployment: str = "gpt-5.4"
    call_cap: int = VISION_CALL_CAP
    reasoning_effort: str = "medium"

    _calls_used: int = field(default=0, init=False)
    _cache: Dict[str, VisionVerdict] = field(default_factory=dict, init=False)

    @property
    def calls_used(self) -> int:
        return self._calls_used

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
            return self._cache[cache_key]

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

        self._calls_used += 1
        try:
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
                temperature=0,
            )
            text = getattr(response, "output_text", "") or ""
            payload = _parse_json_envelope(text)
            verdict = VisionVerdict(
                verdict=str(payload.get("verdict", "fail")),
                partial_score=float(payload.get("partial_score", 0.0)),
                evidence=str(payload.get("evidence", ""))[:200],
                confidence=float(payload.get("confidence", 0.0)),
                reasoning=str(payload.get("reasoning", ""))[:300],
            )
        except Exception as exc:  # noqa: BLE001
            verdict = VisionVerdict(
                verdict="judge_error",
                partial_score=0.0,
                evidence="",
                confidence=0.0,
                reasoning=f"vision call failed: {type(exc).__name__}",
                judge_error=f"{type(exc).__name__}: {exc}",
            )
        if cache_key is not None:
            self._cache[cache_key] = verdict
        return verdict
