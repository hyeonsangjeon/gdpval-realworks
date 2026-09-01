"""Audio and images do not go to the same OpenAI endpoint, and never did.

The audio sub-judge spent its whole life calling ``client.responses.create``
with an ``input_audio`` content part. The Responses API does not accept one:
``ResponseInputContentParam`` is a union of text, image and file, and nothing
else. Every audio request this pipeline has ever sent was refused with a 400
before a model heard a second of it — across Stage 1, Stage 2, the 174-task
Stage 3 partial and the two-task audio smoke, there is not one successful
audio call in any committed grade payload.

It was invisible for three reasons at once, and each is worth naming because
each is the sort of thing that hides the next bug too:

* The fake client accepted any keyword argument, so ``responses.create`` and
  ``chat.completions.create`` were indistinguishable in the suite.
* The shape test read the audio block off ``ResponseInputAudioParam``. That
  type exists, it lives under ``openai.types.responses``, and it is *not* a
  member of the Responses content union — it belongs to the Evals graders.
  A same-named type in a same-looking namespace is not the same contract.
* An audio item that fails is scored ``judge_error``, which reads as "this
  task's audio could not be assessed" rather than "this request was malformed".

So this file does not check field names. It checks the one property all three
mistakes violated: **every content part the reader sends is a member of the
union belonging to the endpoint the reader calls.** A future move back to
Responses, or a new content type sent to the wrong one of the two, fails here
rather than in a paid run.

Nothing here calls a model or a network.
"""

from __future__ import annotations

import ast
import inspect
import typing

import typing_extensions
from openai.types.chat.completion_create_params import (
    CompletionCreateParamsNonStreaming,
)
from openai.types.chat.chat_completion_content_part_param import (
    ChatCompletionContentPartParam,
)
from openai.types.responses.response_input_content_param import (
    ResponseInputContentParam,
)

from core.perception import audio as audio_module


def _discriminators(union: object) -> set[str]:
    """The ``type`` literal each member of a content-part union declares."""
    kinds: set[str] = set()
    for member in typing.get_args(union):
        hints = typing_extensions.get_type_hints(member)
        kinds.update(typing.get_args(hints["type"]))
    return kinds


def _sent_content_kinds(source: str, *, call: str) -> set[str]:
    """The ``"type": "..."`` literals in the content list of a given call.

    Read out of the source rather than by invoking ``judge``, so that this
    holds for every branch of the reader at once — including any a fake
    client would have to be coaxed into reaching.
    """
    tree = ast.parse(source)
    wanted = call.split(".")
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        attrs: list[str] = []
        target = node.func
        while isinstance(target, ast.Attribute):
            attrs.append(target.attr)
            target = target.value
        if isinstance(target, ast.Name):
            attrs.append(target.id)
        if [a for a in reversed(attrs)][-len(wanted):] != wanted:
            continue
        kinds = {
            value.value
            for sub in ast.walk(node)
            if isinstance(sub, ast.Dict)
            for key, value in zip(sub.keys, sub.values)
            if isinstance(key, ast.Constant)
            and key.value == "type"
            and isinstance(value, ast.Constant)
        }
        if kinds:
            return kinds
    return set()


AUDIO_SOURCE = inspect.getsource(audio_module)


def test_the_responses_endpoint_has_no_audio_content_part():
    """The fact the whole bug rests on, asserted rather than remembered.

    If a future SDK adds audio to the Responses union, this fails — and that
    failure is the signal that the endpoint choice below can be revisited,
    rather than a reason to delete a test.
    """
    kinds = _discriminators(ResponseInputContentParam)

    assert "input_audio" not in kinds, (
        f"Responses content parts are now {sorted(kinds)}; if audio has been "
        "added, the reader may move back and this file should be rewritten "
        "rather than deleted"
    )
    assert kinds == {"input_text", "input_image", "input_file"}


def test_the_chat_completions_endpoint_does_have_one():
    """And the endpoint the reader now calls does accept it."""
    assert "input_audio" in _discriminators(ChatCompletionContentPartParam)


def test_the_audio_reader_calls_the_endpoint_that_accepts_audio():
    """Named at the call site, so a revert is a diff and not a mystery."""
    assert "self.client.chat.completions.create(" in AUDIO_SOURCE
    assert "self.client.responses.create(" not in AUDIO_SOURCE


def test_every_content_part_the_audio_reader_sends_is_in_that_endpoints_union():
    """The generalised guard: membership, not field names.

    This is the assertion that would have caught the original ``audio`` key,
    the wrong format list, *and* the wrong endpoint — all three failed it, and
    all three passed the field-shape test that was written instead.
    """
    sent = _sent_content_kinds(AUDIO_SOURCE, call="client.chat.completions.create")
    accepted = _discriminators(ChatCompletionContentPartParam)

    assert sent, "no content parts found at the audio call site"
    assert sent <= accepted, (
        f"the audio reader sends {sorted(sent - accepted)}, which Chat "
        f"Completions does not accept (it takes {sorted(accepted)})"
    )


def test_the_vision_reader_is_held_to_the_same_rule_on_its_own_endpoint():
    """The sibling that was right all along, so the rule is not audio-only.

    Vision calls Responses, and images *are* in the Responses union — which is
    exactly why looking worked while listening never did. Pinning it here
    means the rule is 'each reader matches its endpoint', not 'audio is
    special'.
    """
    from core.perception import vision as vision_module

    source = inspect.getsource(vision_module)
    sent = _sent_content_kinds(source, call="client.responses.create")
    accepted = _discriminators(ResponseInputContentParam)

    assert sent, "no content parts found at the vision call site"
    assert sent <= accepted, (
        f"the vision reader sends {sorted(sent - accepted)}, which Responses "
        f"does not accept (it takes {sorted(accepted)})"
    )


def test_modalities_is_a_real_chat_completions_parameter():
    """``modalities=["text"]`` is asked for; check it is not invented.

    An unknown keyword is dropped or rejected depending on the provider, and
    a dropped one would let an audio deployment answer in speech while this
    code believed it had asked for text.
    """
    hints = typing_extensions.get_type_hints(
        CompletionCreateParamsNonStreaming, include_extras=False
    )

    assert "modalities" in hints
    assert '"text"' in AUDIO_SOURCE.split("modalities=")[1][:40]
