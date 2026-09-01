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
from openai.types.chat.chat_completion_content_part_input_audio_param import (
    ChatCompletionContentPartInputAudioParam,
    InputAudio,
)

from core.perception import AUDIO_CALL_CAP, AudioPerception, AudioVerdict
from core.perception.audio import (
    AUDIO_LAYOUT,
    AUDIO_SAMPLE_RATE_HZ,
    SUPPORTED_AUDIO_FORMATS,
)


def _sdk_keys(typed_dict: type) -> set[str]:
    """The keys an ``openai`` request TypedDict declares.

    Read through ``typing_extensions`` rather than ``__required_keys__``: the
    SDK writes its annotations as strings and marks them with
    ``typing_extensions.Required``, which the 3.10 stdlib does not resolve — it
    reports every key as optional and ``__required_keys__`` comes back empty,
    so a check built on it would pass against anything.
    """
    return set(typing_extensions.get_type_hints(typed_dict))


def _sdk_required_keys(typed_dict: type) -> set[str]:
    """Of those, the ones the SDK marks ``Required``.

    ``__required_keys__`` is empty here for the reason above, but the marker
    itself survives ``include_extras=True``, so it can be read back. Needed
    because these content-part types carry optional keys we deliberately do
    not send — ``prompt_cache_breakpoint``, for one — and an equality check
    against the full key set would demand them.
    """
    hints = typing_extensions.get_type_hints(typed_dict, include_extras=True)
    return {
        key
        for key, annotation in hints.items()
        if typing_extensions.get_origin(annotation) is typing_extensions.Required
    }


def _sdk_audio_formats() -> set[str]:
    """The container formats the SDK's ``InputAudio.format`` literal admits."""
    hints = typing_extensions.get_type_hints(InputAudio)
    return set(typing.get_args(hints["format"]))


# ── Fakes ────────────────────────────────────────────────────────────


#: Lets a test say "this reply carried no usage block at all" without that
#: being confused with "this test did not care about the usage block".
_UNSET = object()


def _default_usage() -> SimpleNamespace:
    """The shape Chat Completions reports, which is what now arrives.

    ``prompt_tokens``/``completion_tokens``, not the Responses API's
    ``input_tokens``/``output_tokens``. ``core.cost_metering.extract_usage``
    reads both, and ``test_a_responses_shaped_usage_block_is_still_read``
    keeps that true, but the default fake mimics the endpoint the reader
    actually calls.
    """
    return SimpleNamespace(
        prompt_tokens=70,
        completion_tokens=12,
        prompt_tokens_details=SimpleNamespace(cached_tokens=5),
    )


class FakeCompletions:
    """Stands in for ``client.chat.completions``.

    Returns a Chat Completions-shaped reply — the text under
    ``choices[0].message.content`` — because that is what the reader now has
    to unpack. A fake still shaped like a Responses reply would let a
    regression to ``response.output_text`` pass.
    """

    def __init__(self, *, text: str = '{"verdict":"pass","partial_score":1.0,'
                 '"evidence":"voice clearly audible","confidence":0.8,'
                 '"reasoning":"no clipping"}',
                 raise_with: Exception | None = None,
                 usage: Any = _UNSET,
                 as_transcript: bool = False):
        self.text = text
        self.raise_with = raise_with
        self.usage = _default_usage() if usage is _UNSET else usage
        self.as_transcript = as_transcript
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self.raise_with is not None:
            raise self.raise_with
        if self.as_transcript:
            message = SimpleNamespace(
                content=None, audio=SimpleNamespace(transcript=self.text)
            )
        else:
            message = SimpleNamespace(content=self.text, audio=None)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=message)], usage=self.usage
        )


class FakeClient:
    """A client that offers Chat Completions and nothing else.

    Deliberately has no ``responses`` attribute. Audio sent to
    ``responses.create`` is refused by the real API with a 400 — see
    ``tests/test_audio_goes_to_the_endpoint_that_accepts_it.py`` — so a
    revert to that endpoint should fail here loudly rather than pass against
    an accommodating fake, which is how the endpoint stayed wrong for the
    whole life of this module.
    """

    def __init__(self, completions: FakeCompletions):
        self.chat = SimpleNamespace(completions=completions)

    @property
    def calls(self) -> list[dict[str, Any]]:
        return self.chat.completions.calls


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
    client = FakeClient(FakeCompletions())
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
    """A reply without ``prompt_tokens_details`` is priced, not written off.

    Both counts that decide the bill are present; the missing breakdown only
    declines to say how much of the input came from cache. Cached input is a
    *part* of the input, never an addition to it, so counting the whole thing
    at the uncached rate can only overstate the bill -- and overstating is the
    safe direction for a number the run has to stand behind.

    What this test does **not** claim is that ``gpt-audio-1.5`` behaves this
    way. Nobody knows: no reply from it has ever been observed, because until
    this change every audio call went to an endpoint that does not accept
    audio and came back a 400. The rule is pinned here because the three
    sites that keep running token totals share it, and a shared rule only
    stays shared if each site is held to it.
    """
    client = FakeClient(
        FakeCompletions(usage=SimpleNamespace(prompt_tokens=70, completion_tokens=12))
    )
    ap = AudioPerception(client=client)

    v = ap.judge(criterion="voice is clear", audio_path=str(wav_file))

    assert v.verdict == "pass"
    assert v.input_tokens == 70
    assert v.output_tokens == 12
    assert v.cached_tokens == 0
    assert v.usage_complete is True


def test_a_responses_shaped_usage_block_is_still_read(wav_file):
    """Moving endpoints must not quietly stop the tokens being counted.

    ``extract_usage`` accepts both namings, and this reader depends on that:
    nobody has seen what an Azure ``gpt-audio-1.5`` deployment reports, and a
    deployment that answered in the older naming would otherwise have every
    call recorded as costing nothing — which is the one direction a cost
    ledger must never fail in.
    """
    client = FakeClient(
        FakeCompletions(
            usage=SimpleNamespace(
                input_tokens=70,
                output_tokens=12,
                input_tokens_details=SimpleNamespace(cached_tokens=5),
            )
        )
    )

    v = AudioPerception(client=client).judge(
        criterion="voice is clear", audio_path=str(wav_file)
    )

    assert (v.input_tokens, v.output_tokens, v.cached_tokens) == (70, 12, 5)
    assert v.usage_complete is True


def test_a_reply_that_reports_no_tokens_at_all_is_not_counted(wav_file):
    """The genuine unknown: a reply that says nothing about what it used."""
    client = FakeClient(FakeCompletions(usage=None))
    ap = AudioPerception(client=client)

    v = ap.judge(criterion="voice is clear", audio_path=str(wav_file))

    assert v.verdict == "pass"
    assert v.usage_complete is False


def test_request_shape_matches_the_sdk_audio_content_part(wav_file):
    """The audio block is checked against the SDK type, not against belief.

    This assertion has been wrong three times. It accepted the payload under
    the key ``audio`` (the API requires ``input_audio``); it accepted
    ``flac``/``ogg``/``m4a``/``aac`` as formats (the API takes ``mp3`` and
    ``wav``); and then, once those were fixed, it went on passing while every
    call still failed — because it read the shape off
    ``ResponseInputAudioParam``, a type that belongs to the Evals graders and
    is *not* a member of the union the Responses endpoint accepts as message
    content. A same-named type is not the same contract.

    So the shape is now read off the content-part type of the endpoint the
    reader actually calls. The union membership itself — the thing all three
    mistakes had in common — is pinned separately in
    ``tests/test_audio_goes_to_the_endpoint_that_accepts_it.py``.

    ``temperature`` was suspected of being a fourth mistake of the same
    family, on the observation that audio was the only caller in the grading
    path that sent one and also the only caller whose every request bounced.
    It was not the cause — the endpoint was, and that is decidable offline —
    but the asymmetry was real and the parameter is gone anyway. Chat
    Completions would accept it; the main judge and ``VisionPerception`` do
    not send one, and a path with no successful call in its history should be
    sending the smallest request that can do the job. It is asserted absent
    here so the convention is checked rather than merely intended.
    """
    client = FakeClient(FakeCompletions())
    ap = AudioPerception(client=client, deployment="gpt-audio-1.5")
    ap.judge(criterion="x", audio_path=str(wav_file))
    sent = client.calls[0]
    assert sent["model"] == "gpt-audio-1.5"
    assert sent["modalities"] == ["text"]
    assert "temperature" not in sent, (
        "audio is sending a sampling parameter no other call in the grading "
        "path sends; the endpoint accepts it, but the convention here is the "
        "smallest request that can do the job"
    )
    assert "seed" not in sent
    content = sent["messages"][0]["content"]
    kinds = {b["type"] for b in content}
    assert {"text", "input_audio"} == kinds, (
        "Chat Completions names its text part ``text``; ``input_text`` is the "
        "Responses spelling and is refused here"
    )

    block = next(b for b in content if b["type"] == "input_audio")
    declared = _sdk_keys(ChatCompletionContentPartInputAudioParam)
    required = _sdk_required_keys(ChatCompletionContentPartInputAudioParam)
    assert required <= set(block) <= declared, (
        f"audio content part carries {sorted(block)}; the SDK requires "
        f"{sorted(required)} and allows {sorted(declared)}"
    )
    payload = block["input_audio"]
    assert _sdk_required_keys(InputAudio) <= set(payload) <= _sdk_keys(InputAudio)
    assert payload["format"] in _sdk_audio_formats()
    assert payload["data"]  # base64 non-empty


def test_a_spoken_reply_is_read_from_its_transcript(wav_file):
    """A deployment that answers in audio is parsed, not silently scored zero.

    ``modalities=["text"]`` is what we ask for, so ``message.content`` is what
    should arrive. But an audio deployment configured to speak puts its words
    under ``message.audio.transcript`` and leaves ``content`` null, and a
    reader that only looked at ``content`` would turn a perfectly good verdict
    into an unparseable empty string — a ``judge_error`` on a criterion the
    model actually answered.
    """
    client = FakeClient(FakeCompletions(as_transcript=True))

    v = AudioPerception(client=client).judge(
        criterion="voice is clear", audio_path=str(wav_file)
    )

    assert v.verdict == "pass"
    assert v.partial_score == 1.0


def test_the_clip_is_re_encoded_to_the_rate_and_layout_that_is_sent(wav_file):
    """What goes on the wire is 16 kHz mono, whatever the source carried.

    The two video deliverables in the gold corpus are 48 kHz stereo, and the
    encoder used to preserve that: 5.76 MB of PCM per call, 7.68 MB once
    base64'd. At a cap of 32 calls that is 246 MB for one task. This keeps
    the downmix wired to the constants rather than to a comment about them.
    """
    import base64
    import io
    import wave as wave_mod

    from core.perception.audio import _trim_audio_bytes

    # The fixture is 8 kHz mono, so a re-encode has to *upsample* to be
    # visible — which makes this a test of "the constants are applied", not
    # of "the file happened to already be small".
    stereo = wav_file.parent / "stereo48k.wav"
    with wave_mod.open(str(wav_file), "rb") as src:
        frames = src.readframes(src.getnframes())
    with wave_mod.open(str(stereo), "wb") as dst:
        dst.setnchannels(2)
        dst.setsampwidth(2)
        dst.setframerate(48_000)
        dst.writeframes(frames * 2)  # interleaved junk; only the header matters

    data, fmt = _trim_audio_bytes(str(stereo), max_seconds=1)

    assert fmt == "wav"
    with wave_mod.open(io.BytesIO(data), "rb") as out:
        assert out.getframerate() == AUDIO_SAMPLE_RATE_HZ
        assert out.getnchannels() == 1, f"AUDIO_LAYOUT is {AUDIO_LAYOUT!r}"
    assert base64.b64encode(data)


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

    Spending one of the task's calls on a container the API refuses outright
    costs money and buys nothing, and — because the rejection arrives as an
    exception from a call that *was* sent — it also marks the item's usage
    incomplete, which is what aborts a Track 2 run.

    Refusing here keeps all three properties right at once: no charge, the cap
    intact, and usage that is complete at zero because nothing was sent.
    """
    clip = tmp_path / "stem.aiff"
    clip.write_bytes(b"FORM\x00\x00\x00\x04AIFF")  # not decodable; ext is what matters
    client = FakeClient(FakeCompletions())
    ap = AudioPerception(client=client)

    verdict = ap.judge(criterion="x", audio_path=str(clip))

    assert client.calls == []
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
    client = FakeClient(FakeCompletions())
    ap = AudioPerception(
        client=client, before_upstream_call=lambda: guarded.append("guard")
    )

    ap.judge(criterion="voice is clear", audio_path=str(wav_file))
    ap.judge(criterion="no clipping", audio_path=str(wav_file))

    assert guarded == ["guard", "guard"]
    assert len(client.calls) == 2


def test_a_refused_container_does_not_consume_a_spacing_interval(tmp_path):
    """No request, so nothing to pace."""
    guarded = []
    clip = tmp_path / "stem.aiff"
    clip.write_bytes(b"FORM\x00\x00\x00\x04AIFF")
    ap = AudioPerception(
        client=FakeClient(FakeCompletions()),
        before_upstream_call=lambda: guarded.append("guard"),
    )

    ap.judge(criterion="x", audio_path=str(clip))

    assert guarded == []


def test_call_cap_short_circuits(wav_file):
    client = FakeClient(FakeCompletions())
    ap = AudioPerception(client=client, call_cap=1)
    ap.judge(criterion="a", audio_path=str(wav_file))
    over = ap.judge(criterion="b", audio_path=str(wav_file))
    assert over.verdict == "judge_error"
    assert over.judge_error == "cap_exceeded"
    assert over.api_call_count == 0
    assert len(client.calls) == 1


def test_missing_file_returns_judge_error(tmp_path):
    client = FakeClient(FakeCompletions())
    ap = AudioPerception(client=client)
    v = ap.judge(criterion="x", audio_path=str(tmp_path / "nope.wav"))
    assert v.verdict == "judge_error"
    assert v.judge_error == "task_execution_error:FileNotFoundError"
    assert v.api_call_count == 0
    assert ap.calls_used == 0


def test_upstream_exception_graceful(wav_file):
    sensitive = "https://private.services.ai.azure.com/ deployment=private"
    client = FakeClient(FakeCompletions(raise_with=RuntimeError(sensitive)))
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
        client=FakeClient(FakeCompletions())
    ).judge(criterion="x", audio_path=str(wav_file))

    assert verdict.judge_error == "task_execution_error:OSError"
    # The class name and the file's own suffix, and nothing else. The suffix
    # is this module's measurement of the path it was handed, not anything the
    # exception said, and it is here because a preparation failure is usually
    # about the container -- see the suffix-less case in
    # test_a_refused_listening_call_says_why.py.
    assert verdict.reasoning == "audio preparation failed: OSError (suffix=.wav)"
    assert verdict.failure_detail == verdict.reasoning
    assert sensitive not in str(verdict.to_dict())


def test_injected_client_runs_without_endpoint_env(monkeypatch, wav_file):
    monkeypatch.delenv("AZURE_AUDIO_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
    client = FakeClient(FakeCompletions())
    ap = AudioPerception(client=client)
    v = ap.judge(criterion="x", audio_path=str(wav_file))
    assert v.verdict == "pass"
    assert v.api_call_count == 1
    assert len(client.calls) == 1


def test_reset_clears_counter(wav_file):
    client = FakeClient(FakeCompletions())
    ap = AudioPerception(client=client)
    ap.judge(criterion="x", audio_path=str(wav_file))
    assert ap.calls_used == 1
    ap.reset()
    assert ap.calls_used == 0


def test_default_call_cap_constant():
    """32, because that is the most listening any one task in the corpus asks.

    It was 3, on the stated grounds that audio items are rarer than visual.
    They are rarer — 150 criteria across 29 of the 220 tasks — but rarity is
    not the same as evenness: the median audio task asks twice and the worst
    (``ff85ee58``) asks 32 times, so 3 starved 11 tasks outright. An item over
    the cap never places a call and is scored ``judge_error`` on a deliverable
    that may well satisfy it.
    """
    assert AUDIO_CALL_CAP == 32
