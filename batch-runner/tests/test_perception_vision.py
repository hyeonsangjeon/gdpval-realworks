"""Tests for ``core.perception.vision`` (PR2 task 205)."""

from __future__ import annotations

import base64
import importlib
import io
import json
from types import SimpleNamespace
from typing import Any

import pytest

from core.perception import VISION_CALL_CAP, VisionPerception, VisionVerdict

vision_module = importlib.import_module("core.perception.vision")


# ── Fakes ────────────────────────────────────────────────────────────


def _png_b64() -> str:
    pytest.importorskip("PIL")
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), color="green").save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


class FakeResponses:
    def __init__(self, *, text: str = '{"verdict":"pass","partial_score":1.0,'
                 '"evidence":"chart title visible","confidence":0.9,'
                 '"reasoning":"clean"}', raise_with: Exception | None = None):
        self.text = text
        self.raise_with = raise_with
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self.raise_with is not None:
            raise self.raise_with
        return SimpleNamespace(
            output_text=self.text,
            usage=SimpleNamespace(
                input_tokens=123,
                output_tokens=17,
                input_tokens_details=SimpleNamespace(cached_tokens=11),
            ),
        )


class FakeClient:
    def __init__(self, responses: FakeResponses):
        self.responses = responses


# ── Tests ────────────────────────────────────────────────────────────


def test_happy_path_parses_verdict():
    client = FakeClient(FakeResponses())
    vp = VisionPerception(client=client)
    v = vp.judge(criterion="chart is labeled", image_b64=_png_b64())
    assert isinstance(v, VisionVerdict)
    assert v.verdict == "pass"
    assert v.partial_score == 1.0
    assert "chart" in v.evidence.lower()
    assert vp.calls_used == 1
    assert v.api_call_count == 1
    assert v.input_tokens == 123
    assert v.output_tokens == 17
    assert v.cached_tokens == 11
    assert v.usage_complete is True


def test_usage_latency_and_guard_are_recorded_exactly(monkeypatch):
    ticks = iter([10.0, 10.25])
    monkeypatch.setattr(vision_module.time, "perf_counter", lambda: next(ticks))
    guarded = []
    vp = VisionPerception(
        client=FakeClient(FakeResponses()),
        before_upstream_call=lambda: guarded.append("guard"),
    )

    verdict = vp.judge(criterion="chart", image_b64=_png_b64())

    assert guarded == ["guard"]
    assert verdict.api_call_count == 1
    assert verdict.input_tokens == 123
    assert verdict.output_tokens == 17
    assert verdict.cached_tokens == 11
    assert verdict.latency_ms == 250.0
    assert verdict.usage_complete is True


def test_request_shape_includes_image_and_model():
    client = FakeClient(FakeResponses())
    vp = VisionPerception(client=client, deployment="gpt-5.4")
    vp.judge(criterion="x", image_b64=_png_b64())
    sent = client.responses.calls[0]
    assert sent["model"] == "gpt-5.4"
    assert "temperature" not in sent
    assert "seed" not in sent
    # The user content must include an input_image block with a data URL.
    content = sent["input"][0]["content"]
    kinds = {block["type"] for block in content}
    assert {"input_text", "input_image"}.issubset(kinds)
    prompt = next(b["text"] for b in content if b["type"] == "input_text")
    assert "partial_score must be 1.0 for pass" in prompt
    assert "confidence must be a number from 0.0 through 1.0" in prompt
    assert "reasoning within 300 characters" in prompt
    image_block = next(b for b in content if b["type"] == "input_image")
    assert image_block["image_url"].startswith("data:image/png;base64,")


def test_semantic_strings_are_normalized_and_bounded():
    payload = {
        "verdict": " PASS ",
        "partial_score": 1.0,
        "evidence": "e" * 220,
        "confidence": 0.9,
        "reasoning": "r" * 350,
    }
    client = FakeClient(FakeResponses(text=json.dumps(payload)))

    verdict = VisionPerception(client=client).judge(
        criterion="chart", image_b64=_png_b64()
    )

    assert verdict.verdict == "pass"
    assert len(verdict.evidence) == 200
    assert len(verdict.reasoning) == 300


def test_call_cap_short_circuits_after_limit():
    client = FakeClient(FakeResponses())
    vp = VisionPerception(client=client, call_cap=2)
    img = _png_b64()
    vp.judge(criterion="a", image_b64=img)
    vp.judge(criterion="b", image_b64=img)
    over = vp.judge(criterion="c", image_b64=img)
    assert over.verdict == "judge_error"
    assert over.judge_error == "cap_exceeded"
    assert over.api_call_count == 0
    # Only 2 actual upstream calls made.
    assert len(client.responses.calls) == 2


def test_cache_key_skips_upstream_call():
    client = FakeClient(FakeResponses())
    vp = VisionPerception(client=client)
    img = _png_b64()
    v1 = vp.judge(criterion="x", image_b64=img, cache_key="report.pdf#p1")
    v2 = vp.judge(criterion="x", image_b64=img, cache_key="report.pdf#p1")
    assert v1.api_call_count == 1
    assert v2.api_call_count == 0
    assert v2.input_tokens == 0
    assert len(client.responses.calls) == 1


def test_corrupt_image_returns_judge_error():
    client = FakeClient(FakeResponses())
    vp = VisionPerception(client=client)
    bad = base64.b64encode(b"not-an-image").decode("ascii")
    v = vp.judge(criterion="x", image_b64=bad)
    assert v.verdict == "judge_error"
    assert v.judge_error == "bad_image"
    assert v.api_call_count == 0
    assert vp.calls_used == 0  # cap counter NOT incremented for bad payload


def test_upstream_exception_returns_judge_error():
    sensitive = "https://private.services.ai.azure.com/ deployment=private"
    client = FakeClient(FakeResponses(raise_with=RuntimeError(sensitive)))
    vp = VisionPerception(client=client)
    v = vp.judge(criterion="x", image_b64=_png_b64())
    assert v.verdict == "judge_error"
    assert v.judge_error == "provider_error:RuntimeError"
    assert sensitive not in v.judge_error
    assert v.api_call_count == 1
    assert v.usage_complete is False
    # The cap counter SHOULD increment because we actually issued the
    # request (the failure happened upstream).
    assert vp.calls_used == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"verdict": "judge_error", "partial_score": 0.0,
         "evidence": "visible issue", "confidence": 0.5, "reasoning": "x"},
        {"verdict": "pass", "partial_score": 0.5,
         "evidence": "visible issue", "confidence": 0.5, "reasoning": "x"},
        {"verdict": "partial", "partial_score": 1.0,
         "evidence": "visible issue", "confidence": 0.5, "reasoning": "x"},
        {"verdict": "fail", "partial_score": 0.0,
         "evidence": "", "confidence": 0.5, "reasoning": "x"},
        {"verdict": "fail", "partial_score": 0.0,
         "evidence": "visible issue", "confidence": 1.5, "reasoning": "x"},
        {"verdict": "fail", "partial_score": 0.0,
         "evidence": "visible issue", "confidence": float("nan"), "reasoning": "x"},
        ["not", "an", "object"],
    ],
)
def test_invalid_semantic_envelope_is_fail_closed(payload):
    client = FakeClient(FakeResponses(text=json.dumps(payload)))
    verdict = VisionPerception(client=client).judge(
        criterion="chart", image_b64=_png_b64()
    )

    assert verdict.verdict == "judge_error"
    assert verdict.judge_error == "invalid_vision_envelope"
    assert verdict.api_call_count == 1
    assert verdict.input_tokens == 123
    assert verdict.output_tokens == 17


def test_invalid_semantic_envelope_logs_only_validation_reason(caplog):
    payload = {
        "verdict": "pass",
        "partial_score": 0.5,
        "evidence": "visible issue",
        "confidence": 0.5,
        "reasoning": "private model text",
    }
    client = FakeClient(FakeResponses(text=json.dumps(payload)))

    with caplog.at_level("WARNING", logger="core.perception.vision"):
        verdict = VisionPerception(client=client).judge(
            criterion="chart", image_b64=_png_b64()
        )

    assert verdict.judge_error == "invalid_vision_envelope"
    assert "InvalidVisionEnvelope" in caplog.text
    assert "verdict and partial_score are inconsistent" not in caplog.text
    assert "private model text" not in caplog.text


def test_reset_clears_counter_and_cache():
    client = FakeClient(FakeResponses())
    vp = VisionPerception(client=client)
    vp.judge(criterion="a", image_b64=_png_b64(), cache_key="k")
    assert vp.calls_used == 1
    vp.reset()
    assert vp.calls_used == 0
    # cache cleared too — second call to same key now hits upstream again
    vp.judge(criterion="a", image_b64=_png_b64(), cache_key="k")
    assert len(client.responses.calls) == 2


def test_default_call_cap_constant():
    assert VISION_CALL_CAP == 5
