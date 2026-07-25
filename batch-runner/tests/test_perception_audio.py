"""Tests for ``core.perception.audio`` (PR2 task 206)."""

from __future__ import annotations

import struct
import wave
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from core.perception import AUDIO_CALL_CAP, AudioPerception, AudioVerdict


# ── Fakes ────────────────────────────────────────────────────────────


class FakeResponses:
    def __init__(self, *, text: str = '{"verdict":"pass","partial_score":1.0,'
                 '"evidence":"voice clearly audible","confidence":0.8,'
                 '"reasoning":"no clipping"}',
                 raise_with: Exception | None = None):
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
                input_tokens=70,
                output_tokens=12,
                input_tokens_details=SimpleNamespace(cached_tokens=5),
            ),
        )


class FakeClient:
    def __init__(self, responses: FakeResponses):
        self.responses = responses


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def wav_file(tmp_path: Path) -> Path:
    """Generate a short 1s mono 8kHz WAV."""
    p = tmp_path / "clip.wav"
    framerate = 8000
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(framerate)
        samples = b"".join(struct.pack("<h", (i % 100) * 200) for i in range(framerate))
        w.writeframes(samples)
    return p


# ── Tests ────────────────────────────────────────────────────────────


def test_happy_path_parses_verdict(wav_file):
    client = FakeClient(FakeResponses())
    ap = AudioPerception(client=client)
    v = ap.judge(criterion="voice is clear", audio_path=str(wav_file))
    assert isinstance(v, AudioVerdict)
    assert v.verdict == "pass"
    assert v.partial_score == 1.0
    assert ap.calls_used == 1
    assert v.api_call_count == 1
    assert v.input_tokens == 70
    assert v.output_tokens == 12
    assert v.cached_tokens == 5
    assert v.usage_complete is True


def test_request_shape_includes_audio_block(wav_file):
    client = FakeClient(FakeResponses())
    ap = AudioPerception(client=client, deployment="gpt-audio-1.5")
    ap.judge(criterion="x", audio_path=str(wav_file))
    sent = client.responses.calls[0]
    assert sent["model"] == "gpt-audio-1.5"
    assert sent["temperature"] == 0
    assert "seed" not in sent
    content = sent["input"][0]["content"]
    kinds = {b["type"] for b in content}
    assert {"input_text", "input_audio"}.issubset(kinds)
    audio_block = next(b for b in content if b["type"] == "input_audio")
    assert audio_block["audio"]["format"] in ("wav", "mp3", "flac", "ogg", "m4a", "aac")
    assert audio_block["audio"]["data"]  # base64 non-empty


def test_call_cap_short_circuits(wav_file):
    client = FakeClient(FakeResponses())
    ap = AudioPerception(client=client, call_cap=1)
    ap.judge(criterion="a", audio_path=str(wav_file))
    over = ap.judge(criterion="b", audio_path=str(wav_file))
    assert over.verdict == "judge_error"
    assert over.judge_error == "cap_exceeded"
    assert over.api_call_count == 0
    assert len(client.responses.calls) == 1


def test_missing_file_returns_judge_error(tmp_path):
    client = FakeClient(FakeResponses())
    ap = AudioPerception(client=client)
    v = ap.judge(criterion="x", audio_path=str(tmp_path / "nope.wav"))
    assert v.verdict == "judge_error"
    assert v.judge_error == "task_execution_error:FileNotFoundError"
    assert v.api_call_count == 0
    assert ap.calls_used == 0


def test_upstream_exception_graceful(wav_file):
    sensitive = "https://private.services.ai.azure.com/ deployment=private"
    client = FakeClient(FakeResponses(raise_with=RuntimeError(sensitive)))
    ap = AudioPerception(client=client)
    v = ap.judge(criterion="x", audio_path=str(wav_file))
    assert v.verdict == "judge_error"
    assert v.judge_error == "provider_error:RuntimeError"
    assert sensitive not in v.judge_error
    assert v.api_call_count == 1
    assert v.usage_complete is False


def test_audio_preparation_oserror_is_class_only(monkeypatch, wav_file):
    sensitive = "https://private.local/path"
    monkeypatch.setattr(
        "core.perception.audio._trim_audio_bytes",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            OSError(sensitive)
        ),
    )

    verdict = AudioPerception(
        client=FakeClient(FakeResponses())
    ).judge(criterion="x", audio_path=str(wav_file))

    assert verdict.judge_error == "task_execution_error:OSError"
    assert verdict.reasoning == "audio preparation failed: OSError"
    assert sensitive not in str(verdict.to_dict())


def test_injected_client_runs_without_endpoint_env(monkeypatch, wav_file):
    monkeypatch.delenv("AZURE_AUDIO_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
    client = FakeClient(FakeResponses())
    ap = AudioPerception(client=client)
    v = ap.judge(criterion="x", audio_path=str(wav_file))
    assert v.verdict == "pass"
    assert v.api_call_count == 1
    assert len(client.responses.calls) == 1


def test_reset_clears_counter(wav_file):
    client = FakeClient(FakeResponses())
    ap = AudioPerception(client=client)
    ap.judge(criterion="x", audio_path=str(wav_file))
    assert ap.calls_used == 1
    ap.reset()
    assert ap.calls_used == 0


def test_default_call_cap_constant():
    assert AUDIO_CALL_CAP == 3
