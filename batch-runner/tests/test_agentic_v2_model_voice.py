"""The one piece of Agentic Sandbox V2 that spends money, exercised for free.

Everything here runs against a stand-in client that records what it was handed
and answers what it was told to. Nothing in this file reaches a network, and a
test that needed one would be a test that could not run in a pull request.

What is checked is deliberately not "does it work". It is the four ways a paid
loop quietly goes wrong: spending past a limit, counting a call it did not
make, missing a call it did make, and carrying on after the thing answering
changed underneath it.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from core.agentic_v2_conversation import (
    AskForTool,
    GaveUp,
    ModelRequest,
    ToolExchange,
)
from core.agentic_v2_model_voice import (
    AzureFoundryVoice,
    ResolvedModelDisagrees,
)
from core.agentic_v2_stage_one_budget import StageOneBudget
from core.execution_envelope_cost import ModelPrice

MODEL = "gpt-5.4"


# ── stand-ins ─────────────────────────────────────────────────────────────


class FakeResponses:
    def __init__(self, answers):
        self.answers = list(answers)
        self.calls: list[dict] = []

    def create(self, **payload):
        self.calls.append(payload)
        if not self.answers:
            raise AssertionError("the voice asked more times than it was told to")
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


class FakeClient:
    def __init__(self, answers):
        self.responses = FakeResponses(answers)


def a_reply(
    *,
    model: str = MODEL,
    input_tokens: int | None = 100,
    output_tokens: int | None = 20,
    tool: tuple[str, str, str] | None = None,
    text: str = "",
) -> dict:
    """One Responses-API answer, shaped the way the SDK shapes them."""
    reply: dict = {"model": model, "output": [], "output_text": text}
    if input_tokens is not None and output_tokens is not None:
        reply["usage"] = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        }
    if tool is not None:
        call_id, name, arguments = tool
        reply["output"] = [
            {
                "type": "function_call",
                "call_id": call_id,
                "name": name,
                "arguments": arguments,
            }
        ]
    return reply


def a_budget(**changes) -> StageOneBudget:
    settings = {
        "max_model_calls": 8,
        "max_input_tokens": 100_000,
        "max_output_tokens": 20_000,
    }
    settings.update(changes)
    return StageOneBudget(**settings)


def a_voice(answers, *, budget=None, prices=None, **changes) -> AzureFoundryVoice:
    settings = {
        "client": FakeClient(answers),
        "deployment": "stage-one-deployment",
        "resource": "a-foundry-resource",
        "budget": budget if budget is not None else a_budget(),
        "instructions": "do the task with the tools you are given",
        "max_output_tokens_per_turn": 2_048,
    }
    settings.update(changes)
    if prices is not None:
        settings["prices"] = prices
    return AzureFoundryVoice(**settings)


def a_request(*, turn: int = 1, history=(), tools=("capabilities_query",)):
    return ModelRequest(
        turn=turn,
        task_prompt="write a short report",
        tools_available=tuple(tools),
        history=tuple(history),
        turns_left=4,
    )


def an_exchange(*, tool_name: str = "capabilities_query") -> ToolExchange:
    """One tool call and its answer, as an earlier turn would leave it."""
    return ToolExchange(
        call_id="call-1",
        tool_name=tool_name,
        arguments={"kind": "commands"},
        ok=True,
        error_type=None,
        data={"commands": []},
    )


def prices_for(model: str = MODEL) -> dict[str, ModelPrice]:
    return {
        model: ModelPrice(
            model=model,
            input_usd_per_million=Decimal("1.25"),
            output_usd_per_million=Decimal("10"),
        )
    }


# ── it declares itself, and cannot be talked out of it ────────────────────


def test_it_says_it_is_paid_and_that_cannot_be_turned_off():
    """The loop's refusal is only worth anything if this cannot lie."""
    voice = a_voice([a_reply()])

    assert voice.makes_paid_calls is True
    with pytest.raises(TypeError):
        a_voice([a_reply()], makes_paid_calls=False)


def test_it_will_not_be_built_without_the_things_that_identify_the_call():
    with pytest.raises(ValueError, match="deployment name"):
        a_voice([], deployment="  ")
    with pytest.raises(ValueError, match="Foundry resource"):
        a_voice([], resource="")
    with pytest.raises(ValueError, match="may write nothing"):
        a_voice([], max_output_tokens_per_turn=0)


# ── the ordinary turn ─────────────────────────────────────────────────────


def test_a_tool_choice_comes_back_as_a_tool_choice():
    voice = a_voice(
        [a_reply(tool=("call-1", "capabilities_query", '{"kind": "commands"}'))],
        prices=prices_for(),
    )

    reply = voice.next_turn(a_request())

    assert isinstance(reply, AskForTool)
    assert reply.call_id == "call-1"
    assert reply.tool_name == "capabilities_query"
    assert reply.arguments == {"kind": "commands"}
    assert reply.input_tokens == 100
    assert reply.output_tokens == 20


def test_only_the_tools_on_offer_this_turn_are_shown():
    """Offering a tool the desk would refuse spends a turn being told no."""
    voice = a_voice([a_reply()])

    voice.next_turn(a_request(tools=("capabilities_query", "finalize")))

    sent = voice.client.responses.calls[0]
    assert {tool["name"] for tool in sent["tools"]} == {
        "capabilities_query",
        "finalize",
    }


def test_a_turn_with_no_tools_on_offer_is_not_paid_for():
    voice = a_voice([])

    reply = voice.next_turn(a_request(tools=()))

    assert isinstance(reply, GaveUp)
    assert voice.client.responses.calls == []
    assert voice.calls == []


def test_every_key_the_voice_sends_is_one_the_sdk_accepts():
    """A key the SDK does not know goes into the body and is refused there.

    The fakes in this file accept anything, so a misspelled parameter looks
    identical to a correct one here and shows up for the first time as a
    ``400`` on a paid dispatch — which is exactly how the first stage A run
    ended, for a different reason. The real signature is free to check.

    ``timeout`` is deliberately in this list: it is a request option rather
    than part of the body, and it is only safe to pass because the method
    genuinely takes it.
    """
    import inspect

    from openai.resources.responses import Responses

    voice = a_voice([a_reply()])
    voice.next_turn(a_request())

    accepted = set(inspect.signature(Responses.create).parameters)
    unknown = sorted(set(voice.client.responses.calls[0]) - accepted)

    assert not unknown, (
        f"the voice sends {', '.join(unknown)}, which Responses.create does "
        f"not take; the service would refuse the request before the model saw it"
    )


def test_one_tool_at_a_time_and_a_ceiling_on_what_a_turn_may_write():
    voice = a_voice([a_reply()])

    voice.next_turn(a_request())

    sent = voice.client.responses.calls[0]
    assert sent["parallel_tool_calls"] is False
    assert sent["max_output_tokens"] == 2_048
    assert sent["model"] == "stage-one-deployment"


def test_every_turn_re_sends_the_whole_conversation():
    """The property the whole budget is worked out from.

    A tool loop costs roughly the square of its length because turn two pays to
    re-read turn one. If this ever stopped happening the bill would stop
    matching the estimate, and the estimate is what an amount was approved
    against.
    """
    voice = a_voice([a_reply(), a_reply()])

    voice.next_turn(a_request(turn=1))
    voice.next_turn(
        a_request(
            turn=2,
            history=[
                ToolExchange(
                    call_id="call-1",
                    tool_name="capabilities_query",
                    arguments={"kind": "commands"},
                    ok=False,
                    error_type="capability_unavailable",
                    data={},
                )
            ],
        )
    )

    first, second = voice.client.responses.calls
    assert len(second["input"]) > len(first["input"])
    everything_sent = str(second["input"])
    assert "write a short report" in everything_sent
    assert "capability_unavailable" in everything_sent


# ── the four ways a paid loop goes wrong ──────────────────────────────────


def test_the_budget_is_asked_before_the_call_not_after():
    """A refusal that arrives after the call is a receipt, not a limit."""
    spent = a_budget(max_model_calls=1)
    spent.record(input_tokens=10, output_tokens=5)
    voice = a_voice([a_reply()], budget=spent)

    reply = voice.next_turn(a_request())

    assert isinstance(reply, GaveUp)
    assert voice.client.responses.calls == []
    assert voice.calls == []


def test_a_call_whose_usage_did_not_come_back_stops_the_run():
    """A budget that stops counting is not a budget."""
    voice = a_voice([a_reply(input_tokens=None, output_tokens=None)])

    reply = voice.next_turn(a_request())

    assert isinstance(reply, GaveUp)
    assert "without saying what it used" in reply.note
    assert voice.calls == []


def test_a_call_is_counted_even_when_its_answer_is_useless():
    """The money is spent by the time the answer is read.

    The counting happens once, in the loop, for every voice alike — so a voice
    that forgot to count is still counted, and a voice that counted twice
    cannot halve its own allowance. What this asserts of the voice is the part
    only the voice can do: the ledger row for a call that bought nothing.
    """
    voice = a_voice([a_reply(text="I would rather not")])

    reply = voice.next_turn(a_request())

    assert isinstance(reply, GaveUp)
    assert len(voice.calls) == 1
    assert voice.calls[0].input_tokens == 100
    assert voice.calls[0].output_tokens == 20


def test_the_voice_does_not_charge_the_budget_the_loop_already_charges():
    """Counted once, or an approved run stops at half of what was approved."""
    voice = a_voice([a_reply(), a_reply()])

    voice.next_turn(a_request(turn=1))
    voice.next_turn(a_request(turn=2))

    assert len(voice.calls) == 2
    assert voice.budget.model_calls_made == 0
    assert voice.budget.input_tokens_used == 0
    assert voice.budget.output_tokens_used == 0


def test_every_call_records_how_much_of_the_conversation_it_carried():
    """What makes "the second turn saw the first turn's answer" a fact."""
    voice = a_voice([a_reply(), a_reply()])

    voice.next_turn(a_request(turn=1))
    voice.next_turn(a_request(turn=2, history=(an_exchange(),)))

    assert [record.history_entries_sent for record in voice.calls] == [0, 1]
    assert voice.ledger()[1]["history_entries_sent"] == 1


def test_a_deployment_that_answers_as_two_models_stops_the_run():
    """Two models' work assembled into one result belongs to neither."""
    voice = a_voice([a_reply(model=MODEL), a_reply(model="something-else")])

    voice.next_turn(a_request(turn=1))
    with pytest.raises(ResolvedModelDisagrees):
        voice.next_turn(a_request(turn=2))

    # The second call is still recorded: it happened, and it will be charged
    # for. The charging is the loop's, so what is checked here is the row.
    assert len(voice.calls) == 2
    assert voice.calls[1].resolved_model == "something-else"


def test_the_service_failing_is_a_stop_not_an_exception():
    voice = a_voice([RuntimeError("the route was refused")])

    reply = voice.next_turn(a_request())

    assert isinstance(reply, GaveUp)
    assert "asking the model failed" in reply.note
    assert voice.calls == []


# ── what is written down ──────────────────────────────────────────────────


def test_the_ledger_holds_one_row_per_call_with_what_answered():
    voice = a_voice(
        [a_reply(tool=("call-1", "capabilities_query", "{}")), a_reply()],
        prices=prices_for(),
    )

    voice.next_turn(a_request(turn=1))
    voice.next_turn(a_request(turn=2))

    rows = voice.ledger()
    assert len(rows) == 2
    assert [row["turn"] for row in rows] == [1, 2]
    for row in rows:
        assert row["requested_deployment"] == "stage-one-deployment"
        assert row["resolved_model"] == MODEL
        assert row["price_missing"] is False


def test_a_model_with_no_price_is_recorded_as_missing_not_as_free():
    """Zero would make an unsettled bill look settled."""
    voice = a_voice([a_reply(model="a-model-nobody-priced")])

    voice.next_turn(a_request())

    row = voice.ledger()[0]
    assert row["price_usd"] is None
    assert row["price_missing"] is True
    assert voice.spent_usd() is None


def test_a_total_that_cannot_include_every_call_is_not_reported():
    voice = a_voice(
        [a_reply(model=MODEL), a_reply(model=MODEL)], prices=prices_for()
    )
    voice.next_turn(a_request(turn=1))
    assert voice.spent_usd() == Decimal("100") * Decimal("1.25") / Decimal(
        1_000_000
    ) + Decimal("20") * Decimal("10") / Decimal(1_000_000)

    # One unpriced call is enough to make the total unreportable.
    voice.prices = {}
    voice.next_turn(a_request(turn=2))
    assert voice.spent_usd() is None


def test_nothing_of_what_was_said_reaches_the_ledger():
    """Tokens and identities, never bodies, keys or reasoning."""
    voice = a_voice(
        [
            a_reply(
                tool=("call-1", "workspace_apply", '{"path": "report.md"}'),
                text="my private working out",
            )
        ],
        prices=prices_for(),
    )

    voice.next_turn(a_request())

    row = voice.ledger()[0]
    assert set(row) == {
        "turn",
        "requested_deployment",
        "resolved_model",
        "input_tokens",
        "output_tokens",
        "history_entries_sent",
        "price_usd",
        "price_missing",
    }
    assert "working out" not in str(row)
    assert "report.md" not in str(row)


def test_a_tool_asked_for_without_a_name_is_not_guessed_at():
    voice = a_voice(
        [
            {
                "model": MODEL,
                "usage": {"input_tokens": 10, "output_tokens": 2},
                "output": [{"type": "function_call", "arguments": "{}"}],
                "output_text": "",
            }
        ]
    )

    reply = voice.next_turn(a_request())

    assert isinstance(reply, GaveUp)
    assert "without naming it" in reply.note


def test_arguments_that_are_not_readable_do_not_stop_the_loop():
    """The desk refuses bad arguments and the model is shown the refusal.

    That exchange is the loop working. Raising here would end the run instead.
    """
    voice = a_voice(
        [a_reply(tool=("call-1", "capabilities_query", "not json at all"))]
    )

    reply = voice.next_turn(a_request())

    assert isinstance(reply, AskForTool)
    assert reply.arguments == {}
