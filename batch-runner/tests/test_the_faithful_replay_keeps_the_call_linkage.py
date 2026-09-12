"""The second replay format, held to the provider's contract.

``tests/test_the_model_is_shown_a_paraphrase_of_its_own_turns.py`` establishes
what the default does: every earlier tool call comes back as one line of prose,
the arguments are dropped, and the answer is replayed as JSON. That file pins
the defect. This one pins the alternative, which the model voice reaches only
when a plan asks for ``replay_format: "faithful"``.

Faithful means the Responses API's own two items per exchange -- a
``function_call`` carrying ``call_id``, ``name`` and ``arguments``, then a
``function_call_output`` carrying the same ``call_id`` and what came back. The
pairing stops being something the model infers from prose and becomes structure
the provider maintains.

Four things are checked here, and a fifth is deliberately not.

* **The default is untouched.** A voice built without asking gets the
  paraphrase, item for item. trial_30 ran under it and a comparison against
  trial_30 is only readable if it can still be reproduced exactly.
* **The linkage survives.** Names, ids, arguments and pairing all come back,
  in order, one output per call, checked by parsing the replay rather than by
  searching it for substrings.
* **Duplication, omission and a malformed argument are refused**, by name, with
  the refusal naming the call. A replay that silently paired one request with
  another's answer would teach the model something false about what it did.
* **Nothing widens.** The request half carries the four fields the contract
  names and no others; the output half is byte-identical to the paraphrase's;
  and ``ToolExchange`` still holds no field that a chain of thought could ride
  in on. The ledger row keeps no arguments either.

**Not checked here, because it is not known:** whether any of this reduces the
attempts that ended in text. That trial_30 saw nine such endings, that they are
in the shape of the paraphrase, and that none of them repeats an id the model
was shown are all facts; that the format *caused* them is a hypothesis, and the
nine cases it came from cannot also be its evidence. The experiment record in
``experiments/execution_envelope/agentic_corrected_harness_plan.yaml`` says the
same thing.

Offline. ``_input_for`` is a string builder and the client below is a stub that
returns a prepared object. Nothing here calls a model or costs anything.
"""
from __future__ import annotations

import json
from dataclasses import fields
from typing import Any

import pytest

from core.agentic_v2_conversation import ModelRequest, ToolExchange
from core.agentic_v2_model_voice import (
    REPLAY_FORMATS,
    AzureFoundryVoice,
    ReplayCannotBeFaithful,
)
from core.agentic_v2_stage_one_budget import StageOneBudget

#: Appears only inside the arguments of the call below. The paraphrase drops
#: it; the faithful replay has to carry it back.
ONLY_IN_THE_ARGUMENTS = "inputs/the-one-file-it-read.md"

#: The four keys the Responses API names on a ``function_call`` item, and the
#: two on its output. Asserted as an exact set rather than a subset: an extra
#: key here is something going to the model that nobody decided to send.
CALL_KEYS = {"type", "call_id", "name", "arguments"}
OUTPUT_KEYS = {"type", "call_id", "output"}


def _exchange(**changed: Any) -> ToolExchange:
    fields_: dict[str, Any] = {
        "call_id": "call_anEarlierOneTheModelWasShown",
        "tool_name": "workspace_apply",
        "arguments": {"operation": "read", "path": ONLY_IN_THE_ARGUMENTS},
        "ok": True,
        "error_type": None,
        "data": {"bytes": 12},
    }
    fields_.update(changed)
    return ToolExchange(**fields_)


def _voice(replay_format: str = "faithful") -> AzureFoundryVoice:
    return AzureFoundryVoice(
        client=object(),
        deployment="a-deployment",
        resource="a-resource",
        budget=StageOneBudget(
            max_model_calls=9, max_input_tokens=1_000_000, max_output_tokens=100_000
        ),
        instructions="do the task",
        max_output_tokens_per_turn=8192,
        replay_format=replay_format,
    )


@pytest.fixture
def faithful() -> AzureFoundryVoice:
    return _voice("faithful")


@pytest.fixture
def paraphrasing() -> AzureFoundryVoice:
    return _voice("paraphrase")


def _request(history: tuple[ToolExchange, ...], turn: int = 1) -> ModelRequest:
    return ModelRequest(
        turn=turn,
        task_prompt="the task",
        tools_available=("workspace_apply", "finalize"),
        history=history,
        turns_left=9 - turn,
    )


# ---------------------------------------------------------------------------
# The format that already ran does not move
# ---------------------------------------------------------------------------


def test_a_voice_that_does_not_ask_gets_the_paraphrase():
    """The default is the pinned condition, not the better of the two."""
    assert AzureFoundryVoice.replay_format == "paraphrase"
    assert REPLAY_FORMATS == ("paraphrase", "faithful")


def test_the_paraphrase_is_unchanged_item_for_item(paraphrasing):
    """What trial_30 sent, written out here so a change to it has to be seen."""
    assert paraphrasing._input_for(_request((_exchange(),))) == [
        {"role": "user", "content": "the task"},
        {
            "role": "assistant",
            "content": (
                "I asked for workspace_apply as call "
                "call_anEarlierOneTheModelWasShown."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "call_id": "call_anEarlierOneTheModelWasShown",
                    "tool": "workspace_apply",
                    "ok": True,
                    "error_type": None,
                    "result": {"bytes": 12},
                },
                sort_keys=True,
                default=str,
            ),
        },
    ]


def test_an_unknown_format_is_refused_when_the_voice_is_built():
    """Before the first task, not on turn one of thirty.

    A typo that fell back to the default would produce a run recorded as one
    format and sent as the other, which is unreadable afterwards.
    """
    with pytest.raises(ValueError, match="unknown replay_format"):
        _voice("faithfull")


# ---------------------------------------------------------------------------
# What the faithful replay sends
# ---------------------------------------------------------------------------


def test_each_exchange_becomes_the_providers_two_items(faithful):
    items = faithful._input_for(_request((_exchange(),)))

    assert items[0] == {"role": "user", "content": "the task"}
    call, output = items[1], items[2]

    assert set(call) == CALL_KEYS
    assert call["type"] == "function_call"
    assert call["call_id"] == "call_anEarlierOneTheModelWasShown"
    assert call["name"] == "workspace_apply"

    assert set(output) == OUTPUT_KEYS
    assert output["type"] == "function_call_output"
    assert output["call_id"] == call["call_id"]


def test_the_arguments_come_back_as_a_json_string_of_the_same_mapping(faithful):
    """The provider wants a string; what it decodes to is what the model sent.

    Parsed rather than compared as text, because the re-encoding is allowed to
    reorder keys -- and only that. Every name and every value is the same.
    """
    items = faithful._input_for(_request((_exchange(),)))
    arguments = items[1]["arguments"]

    assert isinstance(arguments, str)
    assert json.loads(arguments) == {
        "operation": "read",
        "path": ONLY_IN_THE_ARGUMENTS,
    }


def test_the_value_the_paraphrase_drops_is_the_value_that_returns(
    faithful, paraphrasing
):
    """The two formats put side by side on the one thing that differs."""
    request = _request((_exchange(),))
    assert ONLY_IN_THE_ARGUMENTS not in repr(paraphrasing._input_for(request))
    assert ONLY_IN_THE_ARGUMENTS in repr(faithful._input_for(request))


def test_the_answer_half_is_the_same_payload_in_both_formats(
    faithful, paraphrasing
):
    """So the axis between the two formats is exactly one thing.

    If the results were reworded too, a difference in outcome between the two
    would have two candidate causes and the comparison would say nothing about
    either.
    """
    request = _request((_exchange(ok=False, error_type="capability_unavailable"),))

    spoken = [
        message
        for message in paraphrasing._input_for(request)
        if message.get("role") == "user" and message["content"].startswith("{")
    ]
    replayed = [
        item
        for item in faithful._input_for(request)
        if item.get("type") == "function_call_output"
    ]

    assert len(spoken) == len(replayed) == 1
    assert json.loads(spoken[0]["content"]) == json.loads(replayed[0]["output"])


def test_the_first_turn_carries_no_replay_at_all(faithful):
    assert faithful._input_for(_request((), turn=0)) == [
        {"role": "user", "content": "the task"}
    ]


# ---------------------------------------------------------------------------
# Duplication, omission, ordering
# ---------------------------------------------------------------------------


def test_eight_exchanges_come_back_paired_and_in_order(faithful):
    """One output per call, each next to its own, oldest first.

    The ordering matters more than it looks: the provider ties an output to a
    call by id, but the model reads the sequence, and a replay that reordered
    them would describe a task done in an order it was not.
    """
    history = tuple(_exchange(call_id=f"call_number{index}") for index in range(8))
    items = faithful._input_for(_request(history, turn=8))

    assert len(items) == 1 + 2 * len(history)
    body = items[1:]

    assert [item["type"] for item in body] == [
        kind
        for _ in history
        for kind in ("function_call", "function_call_output")
    ]
    assert [item["call_id"] for item in body] == [
        f"call_number{index}" for index in range(8) for _ in (0, 1)
    ]


def test_a_call_id_seen_twice_is_refused_by_name(faithful):
    """A replay carrying it twice pairs one request with the wrong answer."""
    twice = (_exchange(call_id="call_same"), _exchange(call_id="call_same"))
    with pytest.raises(ReplayCannotBeFaithful, match="call_same"):
        faithful._input_for(_request(twice))


def test_an_exchange_with_no_call_id_is_refused(faithful):
    """Its answer cannot be tied back to it, so it is not replayed untied."""
    with pytest.raises(ReplayCannotBeFaithful, match="call_id"):
        faithful._input_for(_request((_exchange(call_id=""),)))


def test_arguments_that_cannot_be_written_back_are_refused_naming_the_call(
    faithful,
):
    """Rather than dropped, silently emptied, or sent as ``"null"``.

    ``{}`` would read to the model as a call it made with no arguments, which
    is a different call from the one it made.
    """
    unwritable = _exchange(arguments={("a", "tuple"): "keys are not JSON"})
    with pytest.raises(ReplayCannotBeFaithful) as refusal:
        faithful._input_for(_request((unwritable,)))
    assert "call_anEarlierOneTheModelWasShown" in str(refusal.value)


def test_the_paraphrase_survives_what_the_faithful_replay_refuses(paraphrasing):
    """Which is why the refusals are in the new format only.

    An empty call id is not well-formed either way, but the old format has
    already run thirty tasks and is not being made stricter after the fact.
    """
    assert paraphrasing._input_for(_request((_exchange(call_id=""),)))


# ---------------------------------------------------------------------------
# Nothing widens
# ---------------------------------------------------------------------------


def test_an_exchange_still_has_nowhere_to_carry_a_chain_of_thought():
    """The narrowness of ``ToolExchange`` is what keeps one out of the replay.

    ``core.agentic_v2_conversation._readable_request`` reads four fields off a
    reply and builds this from them. Widening it to carry, say, the model's
    stated reason would put that reason into every later request -- and into
    the record -- without anything else in the repository objecting.
    """
    assert {field.name for field in fields(ToolExchange)} == {
        "call_id",
        "tool_name",
        "arguments",
        "ok",
        "error_type",
        "data",
    }


def test_nothing_but_the_named_keys_reaches_the_model(faithful):
    history = tuple(_exchange(call_id=f"call_{index}") for index in range(3))
    for item in faithful._input_for(_request(history, turn=3))[1:]:
        assert set(item) in (CALL_KEYS, OUTPUT_KEYS)


# ---------------------------------------------------------------------------
# It is the request that is actually sent, and the ledger keeps none of it
# ---------------------------------------------------------------------------


class _Usage:
    input_tokens = 400
    output_tokens = 31


class _Response:
    output: list[Any] = []
    output_text = ""
    model = "a-deployment"
    usage = _Usage()


class _CapturingClient:
    """Stands in for the Azure client and keeps the payload it was handed."""

    def __init__(self) -> None:
        self.payloads: list[dict[str, Any]] = []
        outer = self

        class _Responses:
            @staticmethod
            def create(**payload: Any) -> Any:
                outer.payloads.append(payload)
                return _Response()

        self.responses = _Responses()


def test_the_faithful_items_are_what_the_client_is_handed(faithful):
    """Through ``next_turn``, not by calling the builder directly.

    The builder returning the right list would mean nothing if the call site
    sent something else.
    """
    faithful.client = _CapturingClient()
    faithful.next_turn(_request((_exchange(),)))

    sent = faithful.client.payloads[0]["input"]
    assert [item.get("type") for item in sent[1:]] == [
        "function_call",
        "function_call_output",
    ]
    assert json.loads(sent[1]["arguments"])["path"] == ONLY_IN_THE_ARGUMENTS
    assert faithful.client.payloads[0]["parallel_tool_calls"] is False


def test_the_same_call_through_the_default_sends_prose(paraphrasing):
    """The pair to the above: one voice, one flag, two requests."""
    paraphrasing.client = _CapturingClient()
    paraphrasing.next_turn(_request((_exchange(),)))

    sent = paraphrasing.client.payloads[0]["input"]
    assert all("type" not in item for item in sent)
    assert ONLY_IN_THE_ARGUMENTS not in repr(sent)


def test_the_ledger_row_keeps_no_arguments(faithful):
    """What is charged for is counted; what was in it is not kept here.

    The ledger is read by people reconciling a bill, and an arguments mapping
    in it would be task content sitting in a cost record.
    """
    faithful.client = _CapturingClient()
    faithful.next_turn(_request((_exchange(),)))

    row = faithful.calls[-1]
    assert ONLY_IN_THE_ARGUMENTS not in repr(row)
    assert row.history_entries_sent == 1
    assert row.input_tokens == 400
