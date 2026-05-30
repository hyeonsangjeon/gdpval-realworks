"""Tests for ``core.perception.vision`` (PR2 task 205)."""

from __future__ import annotations

import base64
import io
import json
from types import SimpleNamespace
from typing import Any

import pytest

from core.perception import VISION_CALL_CAP, VisionPerception, VisionVerdict


# ── Fakes ────────────────────────────────────────────────────────────


def _png_b64() -> str:
    PIL = pytest.importorskip("PIL")
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
        return SimpleNamespace(output_text=self.text)


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


def test_request_shape_includes_image_and_model():
    client = FakeClient(FakeResponses())
    vp = VisionPerception(client=client, deployment="gpt-5.4")
    vp.judge(criterion="x", image_b64=_png_b64())
    sent = client.responses.calls[0]
    assert sent["model"] == "gpt-5.4"
    # The user content must include an input_image block with a data URL.
    content = sent["input"][0]["content"]
    kinds = {block["type"] for block in content}
    assert {"input_text", "input_image"}.issubset(kinds)
    image_block = next(b for b in content if b["type"] == "input_image")
    assert image_block["image_url"].startswith("data:image/png;base64,")


def test_call_cap_short_circuits_after_limit():
    client = FakeClient(FakeResponses())
    vp = VisionPerception(client=client, call_cap=2)
    img = _png_b64()
    vp.judge(criterion="a", image_b64=img)
    vp.judge(criterion="b", image_b64=img)
    over = vp.judge(criterion="c", image_b64=img)
    assert over.verdict == "judge_error"
    assert over.judge_error == "cap_exceeded"
    # Only 2 actual upstream calls made.
    assert len(client.responses.calls) == 2


def test_cache_key_skips_upstream_call():
    client = FakeClient(FakeResponses())
    vp = VisionPerception(client=client)
    img = _png_b64()
    v1 = vp.judge(criterion="x", image_b64=img, cache_key="report.pdf#p1")
    v2 = vp.judge(criterion="x", image_b64=img, cache_key="report.pdf#p1")
    assert v1 is v2
    assert len(client.responses.calls) == 1


def test_corrupt_image_returns_judge_error():
    client = FakeClient(FakeResponses())
    vp = VisionPerception(client=client)
    bad = base64.b64encode(b"not-an-image").decode("ascii")
    v = vp.judge(criterion="x", image_b64=bad)
    assert v.verdict == "judge_error"
    assert v.judge_error == "bad_image"
    assert vp.calls_used == 0  # cap counter NOT incremented for bad payload


def test_upstream_exception_returns_judge_error():
    client = FakeClient(FakeResponses(raise_with=RuntimeError("boom")))
    vp = VisionPerception(client=client)
    v = vp.judge(criterion="x", image_b64=_png_b64())
    assert v.verdict == "judge_error"
    assert v.judge_error is not None
    assert "RuntimeError" in v.judge_error
    # The cap counter SHOULD increment because we actually issued the
    # request (the failure happened upstream).
    assert vp.calls_used == 1


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
