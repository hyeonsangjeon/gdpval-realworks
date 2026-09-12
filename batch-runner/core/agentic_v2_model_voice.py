"""A way for Agentic Sandbox V2 to actually ask a model, and be charged for it.

Everything else in stage one has been provable for free. The loop is exercised
with :class:`core.agentic_v2_conversation.ScriptedVoice`, the tools with a
fixture backend, the containment rules with tests that read the rules rather
than run them. This module is the first piece that spends money, and it is
written so that the spending is bounded, counted, and attributed before the
first call rather than explained afterwards.

Three things it deliberately does not do.

**It does not remove the refusal.** The loop refuses any voice that says it
makes paid calls. That refusal is still there and still catches everything it
caught before, including a stand-in that merely claims to be paid. What changed
is that a voice may now also carry an approved amount, and a voice carrying one
is allowed through. A voice without one is refused exactly as before, so the
free check that proves the refusal keeps proving it.

**It does not decide what may be spent.** :class:`StageOneBudget` is handed in,
already built from an amount somebody wrote down, and it is asked before every
call rather than after. When it refuses, the turn ends with the model having
been asked nothing.

**It does not assume it got the model it asked for.** The deployment name and
the model that answers are recorded separately on every call. A deployment that
answers as something else is a different experiment, so the voice stops instead
of quietly producing a result no single model produced.

What it records per call: the deployment asked for, the model that answered,
input and output tokens as the service reported them, and either a price or an
explicit note that the model is not in the committed price list. Never a
request body, never a reply body, never a token or key, and never the model's
own reasoning.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Mapping, Optional, Sequence

from core.agentic_v2_contract import responses_tool_definitions
from core.agentic_v2_conversation import (
    AskForTool,
    GaveUp,
    ModelReply,
    ModelRequest,
)
from core.agentic_v2_stage_one_budget import StageOneBudget
from core.execution_envelope_cost import ModelPrice
from core.provider_refusal import classify_provider_refusal

# A stated reason is shown to a person, not parsed, and the loop trims what it
# keeps. Kept short here so the trimming never has to happen.
_SHORTEST_USEFUL_NOTE = 200


def _why_the_call_failed(error: BaseException) -> str:
    """The note left behind when the service would not take the request.

    The class name alone is what the first paid stage A dispatch recorded, and
    it was not enough to act on: ``BadRequestError`` says the request was
    refused and nothing whatever about which part of it was wrong. Diagnosing
    that meant reasoning about the payload instead of reading the answer, and
    the answer had already been given.

    So the status and the provider's own code are carried too, through
    :func:`classify_provider_refusal`, which takes those two facts and reads
    nothing else off the exception. The message, the body, the request and the
    response headers do not appear here — an endpoint, an account, a project
    or a deployment name cannot get through a code-shaped allow-list, and the
    same call that names *what* was refused must not name *who* refused it.
    """
    classification = classify_provider_refusal(error)
    detail = type(error).__name__
    if classification:
        detail = f"{detail} ({classification})"
    return f"asking the model failed: {detail}"[:_SHORTEST_USEFUL_NOTE]


class ResolvedModelDisagrees(RuntimeError):
    """Raised when the deployment answers as a model that was not asked for.

    Not returned as an ordinary stop, because it is not something the run can
    carry on from. Every turn after it would be a different experiment than
    every turn before it, and a result assembled from both would belong to
    neither.
    """


class ReplayCannotBeFaithful(RuntimeError):
    """Raised when ``replay_format="faithful"`` cannot keep its promise.

    Raised rather than returned, and for the same reason as the class above: a
    voice that quietly fell back to paraphrasing would produce a run whose
    record says one thing about its conditions and whose requests did another.
    The two ways it fires -- an empty ``call_id`` and the same ``call_id``
    twice -- are both provider errors as well as fidelity ones, so this stops
    the task a request earlier than the service would have.
    """


#: How earlier turns are put back into the request.
#:
#: ``paraphrase`` is what trial_30 ran: each prior call becomes one line of
#: prose, *"I asked for workspace_apply as call call_3."*, and the arguments are
#: dropped. Nine of that cohort's attempts ended with the model completing that
#: format as text instead of asking for a tool.
#:
#: ``faithful`` re-sends the provider's own shape -- a ``function_call`` item
#: carrying ``call_id``, ``name`` and ``arguments``, followed by the matching
#: ``function_call_output``. Opt-in, and named in the run record, because it
#: changes what every turn after the first is charged for: re-sending every
#: past argument was measured at roughly +29% on the input tokens.
REPLAY_FORMATS = ("paraphrase", "faithful")


@dataclass(frozen=True)
class ModelCallRecord:
    """One paid call, as it goes into the ledger.

    ``price_usd`` is ``None`` when the model that answered is not in the
    committed price list. That is recorded as a missing price rather than as
    zero: a call that happened and cost an unknown amount is not a free call,
    and writing zero would make a bill look settled when it is not.
    """

    turn: int
    requested_deployment: str
    resolved_model: str
    input_tokens: int
    output_tokens: int
    price_usd: Optional[Decimal]
    history_entries_sent: int = 0
    """How many earlier tool results this call carried with it.

    Zero on the first call and one more on each call after it, because every
    turn re-sends what came before. Recorded where the call is made rather
    than worked out afterwards from token counts, so "the second turn saw the
    first turn's answer" is a fact about the request that was charged for and
    not an inference from its size.
    """

    @property
    def price_missing(self) -> bool:
        return self.price_usd is None

    def as_dict(self) -> dict[str, Any]:
        return {
            "turn": self.turn,
            "requested_deployment": self.requested_deployment,
            "resolved_model": self.resolved_model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "history_entries_sent": self.history_entries_sent,
            "price_usd": (
                str(self.price_usd) if self.price_usd is not None else None
            ),
            "price_missing": self.price_missing,
        }


def _attribute(item: Any, name: str, default: Any = None) -> Any:
    """Read a field from an SDK object or from a plain mapping.

    The SDK hands back objects; tests hand back dictionaries. Reading both the
    same way is what lets this be exercised without a network.
    """
    if isinstance(item, Mapping):
        return item.get(name, default)
    return getattr(item, name, default)


def _usage_from(response: Any) -> Optional[tuple[int, int]]:
    """Input and output tokens as the service reported them, or nothing.

    Nothing is a refusal to guess. A call whose usage did not come back cannot
    be counted against a budget, and a budget that stops counting is not a
    budget, so the caller treats this as the end of the run.
    """
    usage = _attribute(response, "usage")
    if usage is None:
        return None
    input_tokens = _attribute(usage, "input_tokens")
    output_tokens = _attribute(usage, "output_tokens")
    if not isinstance(input_tokens, int) or not isinstance(output_tokens, int):
        return None
    if input_tokens < 0 or output_tokens < 0:
        return None
    return input_tokens, output_tokens


def _first_function_call(response: Any) -> Optional[Any]:
    for item in list(_attribute(response, "output", []) or []):
        if _attribute(item, "type") == "function_call":
            return item
    return None


def _spoken_text(response: Any) -> str:
    """What the model said when it did not ask for a tool.

    Only the plain text is read. If the reply carries the model's own working
    out, it is not read here and not written anywhere, because keeping it would
    put reasoning into a record that is meant to hold decisions.
    """
    text = _attribute(response, "output_text")
    if isinstance(text, str) and text.strip():
        return text.strip()[:_SHORTEST_USEFUL_NOTE]
    return ""


def _arguments_of(call: Any) -> Mapping[str, Any]:
    raw = _attribute(call, "arguments", "{}")
    if isinstance(raw, Mapping):
        return dict(raw)
    try:
        parsed = json.loads(raw or "{}")
    except (TypeError, ValueError):
        return {}
    return dict(parsed) if isinstance(parsed, Mapping) else {}


def _canonical_json(value: Any, *, what: str) -> str:
    """One JSON encoding, chosen once, so two runs encode the same thing alike.

    Sorted keys and no spaces. Not because the provider cares -- it parses
    either -- but because the digest of a request should not move when a
    dictionary is built in a different order.
    """
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    except (TypeError, ValueError, RecursionError) as error:
        raise ReplayCannotBeFaithful(
            f"{what} could not be written back as JSON: {type(error).__name__}"
        ) from None


@dataclass
class AzureFoundryVoice:
    """A model voice that really asks a Microsoft Foundry deployment.

    ``makes_paid_calls`` is true and is not a settable option: this asks a real
    deployment and a real deployment charges. ``approved_spend_is_on_record`` is
    what the loop looks at to decide whether that is allowed, and it is true
    only because a :class:`StageOneBudget` was handed in — which cannot be built
    without somebody having written an amount down.
    """

    client: Any
    """An OpenAI-compatible client, normally ``AzureAIClientLease.client``.

    Taken rather than built. Building one means choosing an endpoint, a route
    profile and a credential, and this repository already has one reviewed place
    that does all three. A second place would be a second thing to keep right.
    """

    deployment: str
    resource: str
    budget: StageOneBudget
    instructions: str
    max_output_tokens_per_turn: int
    request_timeout_seconds: float = 120.0
    prices: Mapping[str, ModelPrice] = field(default_factory=dict)
    replay_format: str = "paraphrase"
    """How earlier turns are put back into the request. :data:`REPLAY_FORMATS`.

    Defaults to the format trial_30 ran, so nothing that exists changes. A plan
    asks for the other one, and the run record writes down which was used.
    """

    makes_paid_calls: bool = field(default=True, init=False)
    approved_spend_is_on_record: bool = field(default=True, init=False)

    calls: list[ModelCallRecord] = field(default_factory=list)
    resolved_model: Optional[str] = field(default=None, init=False)

    def __post_init__(self) -> None:
        if not str(self.deployment).strip():
            raise ValueError("a deployment name is required to ask a model")
        if not str(self.resource).strip():
            raise ValueError(
                "the Foundry resource is required: the same deployment name in "
                "a different resource is a different deployment"
            )
        if self.max_output_tokens_per_turn < 1:
            raise ValueError(
                "a turn that may write nothing cannot ask for a tool"
            )
        if self.replay_format not in REPLAY_FORMATS:
            raise ValueError(
                f"unknown replay_format {self.replay_format!r}; it is one of "
                f"{', '.join(REPLAY_FORMATS)}. Refused here rather than "
                "defaulted, because a typo that fell back to the default would "
                "produce a run recorded as one format and sent as the other"
            )

    # ── what the model is shown ───────────────────────────────────────────

    def _input_for(self, request: ModelRequest) -> list[dict[str, Any]]:
        """Rebuild the whole conversation, because that is what is charged for.

        Every turn re-sends what came before it. That is not an inefficiency to
        be optimised away here — it is the thing that makes a tool loop cost
        roughly the square of its length, and the budget is worked out on the
        assumption that it happens. Hiding it here would make the bill disagree
        with the estimate.

        Which of the two shapes is used is :attr:`replay_format`.
        """
        if self.replay_format == "faithful":
            return self._faithful_input_for(request)
        return self._paraphrased_input_for(request)

    def _paraphrased_input_for(
        self, request: ModelRequest
    ) -> list[dict[str, Any]]:
        """What trial_30 sent. Kept byte for byte, and kept as the default.

        It has a known defect -- the request half of each exchange becomes a
        sentence and the arguments are discarded -- and it is still here
        unchanged, because it is the condition an already-run cohort ran under.
        A comparison against that cohort is only readable if this can still be
        reproduced exactly.
        """
        messages: list[dict[str, Any]] = [
            {"role": "user", "content": request.task_prompt}
        ]
        for exchange in request.history:
            messages.append(
                {
                    "role": "assistant",
                    "content": (
                        f"I asked for {exchange.tool_name} "
                        f"as call {exchange.call_id}."
                    ),
                }
            )
            messages.append(
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "call_id": exchange.call_id,
                            "tool": exchange.tool_name,
                            "ok": exchange.ok,
                            "error_type": exchange.error_type,
                            "result": exchange.data,
                        },
                        sort_keys=True,
                        default=str,
                    ),
                }
            )
        return messages

    def _faithful_input_for(self, request: ModelRequest) -> list[dict[str, Any]]:
        """Each earlier exchange as the provider's own two items.

        A ``function_call`` carrying the ``call_id``, the tool's name and its
        arguments, then the ``function_call_output`` carrying the same
        ``call_id`` and what came back. The linkage between a request and its
        answer stops being something the model has to infer from prose and
        becomes structure the provider maintains.

        **One fidelity caveat, stated rather than hidden.** The arguments are
        re-encoded from the parsed mapping, not replayed as the bytes the model
        emitted. :class:`core.agentic_v2_conversation.ToolExchange` holds a
        ``Mapping``, and the layer that built it reads four fields and nothing
        else on purpose -- that narrowness is what keeps a chain of thought out
        of the record. Carrying the raw string through would widen it. So key
        order and whitespace may differ from what the model wrote; every name,
        every value and every pairing is the same. Pinned by
        ``tests/test_the_faithful_replay_keeps_the_call_linkage.py``.

        What is not sent: the model's stated reason, its reasoning items, and
        any part of the reply this voice did not already read. The output half
        is deliberately identical to the paraphrased one, so the difference
        between the two formats is exactly one thing.
        """
        items: list[dict[str, Any]] = [
            {"role": "user", "content": request.task_prompt}
        ]
        seen: set[str] = set()
        for exchange in request.history:
            call_id = str(exchange.call_id or "")
            if not call_id:
                raise ReplayCannotBeFaithful(
                    f"an earlier {exchange.tool_name or 'call'} has no call_id, "
                    "so its answer cannot be tied back to it"
                )
            if call_id in seen:
                raise ReplayCannotBeFaithful(
                    f"call id {call_id!r} appears twice in this conversation; "
                    "a replay carrying it twice pairs one request with the "
                    "wrong answer"
                )
            seen.add(call_id)
            items.append(
                {
                    "type": "function_call",
                    "call_id": call_id,
                    "name": exchange.tool_name,
                    "arguments": _canonical_json(
                        dict(exchange.arguments),
                        what=f"the arguments of {call_id}",
                    ),
                }
            )
            items.append(
                {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": _canonical_json(
                        {
                            "call_id": call_id,
                            "tool": exchange.tool_name,
                            "ok": exchange.ok,
                            "error_type": exchange.error_type,
                            "result": exchange.data,
                        },
                        what=f"the result of {call_id}",
                    ),
                }
            )
        return items

    def _tools_for(self, available: Sequence[str]) -> list[dict]:
        """Only the tools the desk will actually accept this turn.

        Offering a tool the desk would refuse teaches the model to ask for it,
        which spends a turn to be told no.
        """
        offered = set(available)
        return [
            definition
            for definition in responses_tool_definitions()
            if definition.get("name") in offered
        ]

    # ── the call ──────────────────────────────────────────────────────────

    def next_turn(self, request: ModelRequest) -> ModelReply:
        refusal = self.budget.refusal_before_next_call()
        if refusal is not None:
            return GaveUp(note=f"the budget stopped this run: {refusal}"[:_SHORTEST_USEFUL_NOTE])

        tools = self._tools_for(request.tools_available)
        if not tools:
            return GaveUp(note="no tool was on offer, so there was nothing to choose")

        payload: dict[str, Any] = {
            "model": self.deployment,
            "instructions": self.instructions,
            "input": self._input_for(request),
            "tools": tools,
            "max_output_tokens": self.max_output_tokens_per_turn,
            # One tool per turn. The loop runs a tool, shows the model what came
            # back and asks again; two tools at once would leave the second
            # chosen without having seen the first one's answer.
            "parallel_tool_calls": False,
            "timeout": self.request_timeout_seconds,
        }

        try:
            response = self.client.responses.create(**payload)
        except Exception as error:  # the service, the network, or the route
            return GaveUp(note=_why_the_call_failed(error))

        usage = _usage_from(response)
        if usage is None:
            return GaveUp(
                note=(
                    "the model answered without saying what it used, so the "
                    "call cannot be counted and the run stops"
                )
            )
        input_tokens, output_tokens = usage

        answered_as = str(_attribute(response, "model", "") or "")
        self._record(
            turn=request.turn,
            resolved_model=answered_as,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            history_entries_sent=len(request.history),
        )
        # Not charged to the budget here. The loop charges every reply it gets,
        # from any voice, immediately after this returns — that is what makes a
        # voice which forgot to count still countable. Charging in both places
        # would spend each call's allowance twice, and a run would stop at half
        # the calls that were approved while looking like a model that gave up.
        # What is kept here is the ledger row, which the loop does not keep.

        if self.resolved_model is None:
            self.resolved_model = answered_as
        elif answered_as and answered_as != self.resolved_model:
            raise ResolvedModelDisagrees(
                f"deployment {self.deployment!r} in {self.resource!r} answered "
                f"as {self.resolved_model!r} and then as {answered_as!r}"
            )

        call = _first_function_call(response)
        if call is None:
            return GaveUp(
                note=_spoken_text(response) or "the model asked for no tool",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )

        call_id = str(_attribute(call, "call_id", "") or "")
        tool_name = str(_attribute(call, "name", "") or "")
        if not call_id or not tool_name:
            return GaveUp(
                note="the model asked for a tool without naming it",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )

        return AskForTool(
            call_id=call_id,
            tool_name=tool_name,
            arguments=_arguments_of(call),
            why=_spoken_text(response),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    # ── what is kept ──────────────────────────────────────────────────────

    def _record(
        self,
        *,
        turn: int,
        resolved_model: str,
        input_tokens: int,
        output_tokens: int,
        history_entries_sent: int = 0,
    ) -> None:
        price = self.prices.get(resolved_model) if resolved_model else None
        self.calls.append(
            ModelCallRecord(
                turn=turn,
                requested_deployment=self.deployment,
                resolved_model=resolved_model or "unreported",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                history_entries_sent=history_entries_sent,
                price_usd=(
                    price.cost_of(
                        input_tokens=input_tokens, output_tokens=output_tokens
                    )
                    if price is not None
                    else None
                ),
            )
        )

    def ledger(self) -> list[dict[str, Any]]:
        """One row per call, in the order the calls were made."""
        return [record.as_dict() for record in self.calls]

    def spent_usd(self) -> Optional[Decimal]:
        """What the calls cost, or ``None`` if any of them has no price.

        Deliberately all-or-nothing. A total that silently leaves out the calls
        it could not price reads as the whole bill, and is not.
        """
        if not self.calls:
            return Decimal("0")
        if any(record.price_missing for record in self.calls):
            return None
        return sum(
            (record.price_usd or Decimal("0") for record in self.calls),
            Decimal("0"),
        )
