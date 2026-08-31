"""Tests for ``core.perception.audio`` (PR2 task 206)."""

from __future__ import annotations

import struct
import typing
import wave
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import typing_extensions
from openai.types.responses.response_input_audio_param import (
    InputAudio,
    ResponseInputAudioParam,
)

from core.perception import AUDIO_CALL_CAP, AudioPerception, AudioVerdict
from core.perception.audio import SUPPORTED_AUDIO_FORMATS


def _sdk_keys(typed_dict: type) -> set[str]:
    """The keys an ``openai`` request TypedDict declares.

    Read through ``typing_extensions`` rather than ``__required_keys__``: the
    SDK writes its annotations as strings and marks them with
    ``typing_extensions.Required``, which the 3.10 stdlib does not resolve — it
    reports every key as optional and ``__required_keys__`` comes back empty,
    so a check built on it would pass against anything.
    """
    return set(typing_extensions.get_type_hints(typed_dict))


def _sdk_audio_formats() -> set[str]:
    """The container formats the SDK's ``InputAudio.format`` literal admits."""
    hints = typing_extensions.get_type_hints(InputAudio)
    return set(typing.get_args(hints["format"]))


# ── Fakes ────────────────────────────────────────────────────────────


#: Lets a test say "this reply carried no usage block at all" without that
#: being confused with "this test did not care about the usage block".
_UNSET = object()


def _default_usage() -> SimpleNamespace:
    return SimpleNamespace(
        input_tokens=70,
        output_tokens=12,
        input_tokens_details=SimpleNamespace(cached_tokens=5),
    )


class FakeResponses:
    def __init__(self, *, text: str = '{"verdict":"pass","partial_score":1.0,'
                 '"evidence":"voice clearly audible","confidence":0.8,'
                 '"reasoning":"no clipping"}',
                 raise_with: Exception | None = None,
                 usage: Any = _UNSET):
        self.text = text
        self.raise_with = raise_with
        self.usage = _default_usage() if usage is _UNSET else usage
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self.raise_with is not None:
            raise self.raise_with
        return SimpleNamespace(output_text=self.text, usage=self.usage)


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


def test_a_reply_with_no_cache_breakdown_is_still_counted(wav_file):
    """A reply without ``input_tokens_details`` is priced, not written off.

    Both counts that decide the bill are present; the missing breakdown only
    declines to say how much of the input came from cache. Cached input is a
    *part* of the input, never an addition to it, so counting the whole thing
    at the uncached rate can only overstate the bill -- and overstating is the
    safe direction for a number the run has to stand behind.

    What this test does **not** claim is that ``gpt-audio-1.5`` behaves this
    way. Nobody knows: until the content-part key was corrected, every audio
    call was rejected with a 400 before it reached the model, so no reply from
    it has ever been observed. The rule is pinned here because the three sites
    that keep running token totals share it, and a shared rule only stays
    shared if each site is held to it.
    """
    client = FakeClient(
        FakeResponses(usage=SimpleNamespace(input_tokens=70, output_tokens=12))
    )
    ap = AudioPerception(client=client)

    v = ap.judge(criterion="voice is clear", audio_path=str(wav_file))

    assert v.verdict == "pass"
    assert v.input_tokens == 70
    assert v.output_tokens == 12
    assert v.cached_tokens == 0
    assert v.usage_complete is True


def test_a_reply_that_reports_no_tokens_at_all_is_not_counted(wav_file):
    """The genuine unknown: a reply that says nothing about what it used."""
    client = FakeClient(FakeResponses(usage=None))
    ap = AudioPerception(client=client)

    v = ap.judge(criterion="voice is clear", audio_path=str(wav_file))

    assert v.verdict == "pass"
    assert v.usage_complete is False


def test_request_shape_matches_the_sdk_audio_content_part(wav_file):
    """The audio block is checked against the SDK type, not against belief.

    This assertion used to be written by hand, and it was wrong twice: it
    accepted the payload under the key ``audio`` (the API requires
    ``input_audio``) and it accepted ``flac``/``ogg``/``m4a``/``aac`` as
    formats (the API takes ``mp3`` and ``wav``). Both mistakes are invisible
    to a fake client, which accepts any keyword argument, so the suite stayed
    green while every real audio call was rejected with a 400 before reaching
    the model.

    So the shape is read off ``ResponseInputAudioParam`` — the same generated
    type the SDK serialises against — and a future change to the wire format
    fails here instead of failing in a paid run.

    ``temperature`` was the third mistake of that family, and the paid smoke
    on run ``33363059548`` is what exposed it: every audio request bounced
    with a 400 while the same run's 223 judge calls, on the same client and
    the same API version, went out without one and were answered. This module
    was the only place in the whole grading path that sent it — the main
    judge does not, and ``VisionPerception`` does not.

    The honest statement of what is pinned here: nothing in this repository
    can prove ``gpt-audio-1.5`` rejects ``temperature``, because reading a 400
    body costs a paid call. What is provable is that audio was the outlier,
    and this test now holds it to the convention the rest of the path already
    follows. If the next smoke returns a verdict, that was the cause.
    """
    client = FakeClient(FakeResponses())
    ap = AudioPerception(client=client, deployment="gpt-audio-1.5")
    ap.judge(criterion="x", audio_path=str(wav_file))
    sent = client.responses.calls[0]
    assert sent["model"] == "gpt-audio-1.5"
    assert "temperature" not in sent, (
        "audio is sending a sampling parameter no other call in the grading "
        "path sends; that asymmetry is the leading explanation for the 400s "
        "the paid smoke recorded"
    )
    assert "seed" not in sent
    content = sent["input"][0]["content"]
    kinds = {b["type"] for b in content}
    assert {"input_text", "input_audio"}.issubset(kinds)

    block = next(b for b in content if b["type"] == "input_audio")
    assert set(block) == _sdk_keys(ResponseInputAudioParam), (
        f"audio content part carries {sorted(block)}, but the SDK declares "
        f"{sorted(_sdk_keys(ResponseInputAudioParam))}"
    )
    payload = block["input_audio"]
    assert set(payload) == _sdk_keys(InputAudio)
    assert payload["format"] in _sdk_audio_formats()
    assert payload["data"]  # base64 non-empty


def test_the_module_offers_exactly_the_formats_the_sdk_accepts():
    """``SUPPORTED_AUDIO_FORMATS`` is the SDK's list, not a second opinion.

    The refusal in ``judge`` is only as good as this tuple. If the API grows a
    third format and this is not updated, clips it would have accepted get
    turned away for free; if it shrinks and this is not updated, we go back to
    paying for 400s.
    """
    assert set(SUPPORTED_AUDIO_FORMATS) == _sdk_audio_formats()


def test_an_unsupported_container_is_refused_without_spending_a_call(tmp_path):
    """A format the API will reject never becomes a request.

    The call cap is three per task. Spending one of them on a container the
    API refuses outright costs money and buys nothing, and — because the
    rejection arrives as an exception from a call that *was* sent — it also
    marks the item's usage incomplete, which is what aborts a Track 2 run.

    Refusing here keeps all three properties right at once: no charge, the cap
    intact, and usage that is complete at zero because nothing was sent.
    """
    clip = tmp_path / "stem.aiff"
    clip.write_bytes(b"FORM\x00\x00\x00\x04AIFF")  # not decodable; ext is what matters
    client = FakeClient(FakeResponses())
    ap = AudioPerception(client=client)

    verdict = ap.judge(criterion="x", audio_path=str(clip))

    assert client.responses.calls == []
    assert verdict.verdict == "judge_error"
    assert verdict.judge_error == "unsupported_audio_format"
    assert "aiff" in verdict.reasoning
    assert ap.calls_used == 0
    assert verdict.api_call_count == 0
    assert verdict.usage_complete is True


def test_the_rate_limit_guard_runs_before_every_request(wav_file):
    """Audio is paced by the same spacer as looking and as the main judge.

    All three go out over one client and draw on one token-per-minute
    allowance, so a guard only some of them call does not pace the run — it
    just moves where the 429s land. This reader had no guard at all until the
    content-part key was corrected, which hid the gap completely: every audio
    request was refused before it reached a model, so there was never any
    traffic to throttle.

    The guard runs *before* the call is counted, so a clip refused for its
    container (checked earlier) does not consume a spacing interval either.
    """
    guarded = []
    client = FakeClient(FakeResponses())
    ap = AudioPerception(
        client=client, before_upstream_call=lambda: guarded.append("guard")
    )

    ap.judge(criterion="voice is clear", audio_path=str(wav_file))
    ap.judge(criterion="no clipping", audio_path=str(wav_file))

    assert guarded == ["guard", "guard"]
    assert len(client.responses.calls) == 2


def test_a_refused_container_does_not_consume_a_spacing_interval(tmp_path):
    """No request, so nothing to pace."""
    guarded = []
    clip = tmp_path / "stem.aiff"
    clip.write_bytes(b"FORM\x00\x00\x00\x04AIFF")
    ap = AudioPerception(
        client=FakeClient(FakeResponses()),
        before_upstream_call=lambda: guarded.append("guard"),
    )

    ap.judge(criterion="x", audio_path=str(clip))

    assert guarded == []


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
