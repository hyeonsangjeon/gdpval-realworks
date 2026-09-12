"""The model never sees its own tool calls, only a sentence describing them.

`AzureFoundryVoice._input_for` rebuilds the whole conversation before every
turn, which is right and is what the budget is worked out on. What it rebuilds
is not the conversation. Each of the model's prior turns comes back as one
line of prose --

    I asked for workspace_apply as call call_A1b2C3.

-- and the arguments of that call, which `ToolExchange` is carrying, are
dropped. The tool's *answer* is replayed in full as JSON. So the model can see
every result it got and cannot see any request it made.

Two consequences, and the second one is measured.

The first is information loss that grows with the turn count. By turn eight a
model has eight lines saying it asked for `workspace_apply` and no record of
which path it read or wrote. That bears directly on
`tasks/0822_saturday/TURN_LIMIT_COMPARISON_DESIGN.md`: raising the limit adds
turns whose history is this thin.

The second is a failure mode. In trial_30 (run 34671538199) nine attempts
across five tasks ended with `stop_reason: model_stopped_without_finishing`,
and every one of them carries a note of the same shape as the line above --
naming `workspace_apply`, naming a well-formed `call_...` id, 29-32 output
tokens, one sentence. **None of those ids appears anywhere earlier in its own
conversation.** The model did not repeat a call id it had been shown; it wrote
a new one inside prose, in the format the harness had been showing it, instead
of emitting a function call. `next_turn` finds no function call and returns
`GaveUp`, whose docstring calls that "the model walking away".

It is not a model giving up, and no give-up text exists to preserve. It is the
harness's own replay format being completed as text. The earliest it happens is
the third turn of a conversation and it never happens on the first, which is
what one would expect of imitation: there has to be something to imitate.

This file pins the mechanism, not the failure rate. Both halves are pure --
`_input_for` is a string builder and the reply branch is a `None` check -- so
nothing here calls a model or costs anything. Changing the replay format is an
intervention on a pinned run condition and needs its own run id; the count
above belongs to trial_30 and nothing here modifies it.
"""
from __future__ import annotations

from typing import Any

import pytest

from core.agentic_v2_conversation import (
    AskForTool,
    GaveUp,
    ModelRequest,
    ToolExchange,
)
from core.agentic_v2_model_voice import AzureFoundryVoice
from core.agentic_v2_stage_one_budget import StageOneBudget

#: A value that appears only in the arguments of the call below, so finding it
#: anywhere in the rebuilt conversation means the arguments survived.
ONLY_IN_THE_ARGUMENTS = "inputs/the-one-file-it-read.md"


def _exchange(**changed: Any) -> ToolExchange:
    fields: dict[str, Any] = {
        "call_id": "call_anEarlierOneTheModelWasShown",
        "tool_name": "workspace_apply",
        "arguments": {"operation": "read", "path": ONLY_IN_THE_ARGUMENTS},
        "ok": True,
        "error_type": None,
        "data": {"bytes": 12},
    }
    fields.update(changed)
    return ToolExchange(**fields)


@pytest.fixture
def voice() -> AzureFoundryVoice:
    """A real voice with a client that is never called.

    Only `_input_for` and the reply branch are exercised, and neither of them
    touches the client, so a stub is honest here rather than a shortcut.
    """
    return AzureFoundryVoice(
        client=object(),
        deployment="a-deployment",
        resource="a-resource",
        budget=StageOneBudget(
            max_model_calls=9, max_input_tokens=1_000_000, max_output_tokens=100_000
        ),
        instructions="do the task",
        max_output_tokens_per_turn=8192,
    )


def _request(history: tuple[ToolExchange, ...], turn: int = 1) -> ModelRequest:
    return ModelRequest(
        turn=turn,
        task_prompt="the task",
        tools_available=("workspace_apply", "finalize"),
        history=history,
        turns_left=9 - turn,
    )


def test_the_arguments_of_a_past_call_are_not_replayed(voice):
    """The one thing the model would need to know is the one thing dropped."""
    messages = voice._input_for(_request((_exchange(),)))

    whole = repr(messages)
    assert ONLY_IN_THE_ARGUMENTS not in whole
    assert "operation" not in whole
    # The answer, by contrast, comes back in full.
    assert '"bytes": 12' in whole


def test_a_past_call_comes_back_as_one_sentence_of_prose(voice):
    """And the sentence is the shape the give-up notes are in."""
    messages = voice._input_for(_request((_exchange(),)))

    spoken = [m for m in messages if m["role"] == "assistant"]
    assert spoken == [
        {
            "role": "assistant",
            "content": (
                "I asked for workspace_apply as call "
                "call_anEarlierOneTheModelWasShown."
            ),
        }
    ]


def test_the_first_turn_has_nothing_to_imitate(voice):
    """Which is why the failure never appears on it.

    With no history the model is shown the task and nothing else, so there is
    no assistant voice in the input at all. The earliest give-up in trial_30 is
    the third turn of its conversation.
    """
    messages = voice._input_for(_request((), turn=0))
    assert messages == [{"role": "user", "content": "the task"}]


def test_every_turn_adds_another_line_in_that_format(voice):
    """Eight turns in, eight lines, none of which says what was asked for."""
    history = tuple(
        _exchange(call_id=f"call_number{index}") for index in range(8)
    )
    messages = voice._input_for(_request(history, turn=8))

    spoken = [m["content"] for m in messages if m["role"] == "assistant"]
    assert len(spoken) == 8
    assert all(
        line == f"I asked for workspace_apply as call call_number{index}."
        for index, line in enumerate(spoken)
    )


# ---------------------------------------------------------------------------
# The other half of the join
# ---------------------------------------------------------------------------


class _Response:
    """The shape `next_turn` reads a reply out of."""

    def __init__(self, output: list[Any], text: str = "") -> None:
        self.output = output
        self.output_text = text
        self.model = "a-deployment"
        self.usage = type(
            "Usage", (), {"input_tokens": 400, "output_tokens": 31}
        )()


class _FunctionCall:
    type = "function_call"

    def __init__(self) -> None:
        self.call_id = "call_realOne"
        self.name = "workspace_apply"
        self.arguments = '{"operation": "read", "path": "a.md"}'


def test_a_reply_with_no_function_call_becomes_a_give_up_carrying_its_text(voice):
    """This is the branch the nine attempts went through.

    The text the model wrote becomes the note verbatim, which is how a sentence
    in the harness's own replay format ended up recorded as the reason a task
    stopped.
    """
    voice.client = _client_returning(
        _Response(output=[], text="I asked for workspace_apply as call call_MadeUp.")
    )
    reply = voice.next_turn(_request((_exchange(),)))

    assert isinstance(reply, GaveUp)
    assert reply.note == "I asked for workspace_apply as call call_MadeUp."
    assert reply.output_tokens == 31


def test_the_same_reply_with_a_real_function_call_is_a_tool_request(voice):
    """The contrast that makes the above a defect rather than a policy.

    Identical prose, but one carries a `function_call` item. The text becomes
    `why` and the run continues, so what separates a task that lives from one
    that dies here is whether the model emitted the call or described it.
    """
    voice.client = _client_returning(
        _Response(
            output=[_FunctionCall()],
            text="I asked for workspace_apply as call call_MadeUp.",
        )
    )
    reply = voice.next_turn(_request((_exchange(),)))

    assert isinstance(reply, AskForTool)
    assert reply.tool_name == "workspace_apply"
    assert reply.call_id == "call_realOne"
    assert reply.arguments == {"operation": "read", "path": "a.md"}


def _client_returning(response: Any) -> Any:
    """A client whose `responses.create` hands back one prepared reply."""

    class _Responses:
        @staticmethod
        def create(**_: Any) -> Any:
            return response

    return type("Client", (), {"responses": _Responses()})()
