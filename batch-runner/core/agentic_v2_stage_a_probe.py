"""Stage A's one question, asked once, of a real model.

Everything under it already works and has been proved for free. The loop runs
against a scripted voice, the tools against a fixture backend that really
touches files, the containment rules against tests that read the rules. What
none of that establishes is the one thing stage A exists to find out: whether a
real Microsoft Foundry deployment, shown these tools and this task, *chooses*
one of them, and whether the turn after that arrives with the first turn's
answer in front of it.

That question cannot be answered for free, so this module is written to ask it
as narrowly as a question can be asked.

**One task.** The first of the five the plan already fixed, chosen by position
rather than by name so the probe cannot be quietly pointed at whichever task
looks easiest. Which five was settled elsewhere, from a catalogue holding no
scores, and stage A does not re-open it.

**Two tools, and not the eighth.** ``finalize`` is what commits deliverables
and hands them to the grader, and marking is about $2,504 of stage one's
$2,543. A probe that could reach it would be the stage-one run wearing a
smaller name. It is left out of :data:`PROBE_TOOLS` rather than blocked
downstream, so the model is never taught to ask for something it will be
refused, and the preflight reads this tuple instead of taking a document's word
for it.

**Nothing is graded and nothing is kept from the model's own words.** The loop
keeps fingerprints and token counts; a stated reason is trimmed to a length fit
for a person to read. No request body, no reply body, no reasoning.

**Everything spent is recorded per call**, including how many earlier tool
results each call carried — which is what makes "the second turn saw the first
turn's answer" a fact about a request that was paid for, rather than something
inferred afterwards from its size.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from core.agentic_v2_contract import AgenticV2Lifecycle, AgenticV2Profile, LifecycleState
from core.agentic_v2_conversation import (
    ConversationOutcome,
    DispatcherToolDesk,
    LoopLimits,
    real_model_voice,
    run_model_conversation,
)
from core.agentic_v2_fixture_backend import AgenticV2FixtureBackend
from core.agentic_v2_stage_one_budget import StageOneBudget
from core.agentic_v2_tools import AgenticV2ToolDispatcher
from core.execution_envelope_cost import ModelPrice


#: The tools stage A's probe puts on offer, and the only ones.
#:
#: ``finalize`` is absent because stage A marks nothing: reaching it would turn
#: a question about tool-choosing into the graded run it is supposed to come
#: before. ``exec_run`` is absent because it is shut, and offering a shut tool
#: spends a paid turn to be told no. The rest — package resolution, activation,
#: the browser, the public verifier — reach package indexes, the network or the
#: verifier, none of which stage A is asking about.
#:
#: What is left is enough for the question to be real. ``capabilities_query``
#: answers with what the environment actually allows and what budget remains;
#: ``workspace_apply`` genuinely writes bytes and reports what it wrote. Either
#: answer changes what a sensible next turn would be, which is the whole point.
PROBE_TOOLS: tuple[str, ...] = (
    "capabilities_query",
    "workspace_apply",
)

#: What the model is told it is doing.
#:
#: Deliberately does not name a tool to call. A probe that instructs the model
#: to call ``capabilities_query`` and then reports that it called
#: ``capabilities_query`` has established nothing about whether a model chooses
#: tools; it has established that models follow instructions.
PROBE_INSTRUCTIONS = (
    "You are working inside an isolated task workspace with a small set of "
    "tools. Use them to make progress on the task you are given. Ask for one "
    "tool at a time and use what comes back before deciding what to do next. "
    "If a tool answers that something is unavailable, do not ask for it again."
)


class ProbeToolsAreWrong(RuntimeError):
    """Raised when the probe's tool list would let it do more than it should.

    A hard failure rather than a filter. If ``finalize`` ever appears in the
    offered list, something has changed the probe's purpose, and quietly
    removing it would hide that from whoever changed it.
    """


def check_probe_tools(tools: Sequence[str] = PROBE_TOOLS) -> list[str]:
    """Everything wrong with a probe tool list, read from the list itself."""
    problems: list[str] = []
    offered = tuple(tools)
    if not offered:
        problems.append(
            "the stage A probe offers no tools, so a model could not choose "
            "one and the run would answer nothing"
        )
    if "finalize" in offered:
        problems.append(
            "the stage A probe offers finalize, which commits deliverables and "
            "sends them to the grader. Stage A marks nothing, and marking is "
            "almost the whole of stage one's cost, so a probe that can reach "
            "it is the stage-one run under another name"
        )
    if "exec_run" in offered:
        problems.append(
            "the stage A probe offers exec_run, which is shut. Offering it "
            "spends a paid turn to be told the capability is unavailable"
        )
    unknown = [name for name in offered if name not in _KNOWN_TOOLS]
    if unknown:
        problems.append(
            f"the stage A probe offers {sorted(unknown)}, which the published "
            "tool contract does not define"
        )
    return problems


def _known_tools() -> frozenset[str]:
    from core.agentic_v2_contract import TOOL_NAMES

    return frozenset(TOOL_NAMES)


_KNOWN_TOOLS = _known_tools()


@dataclass(frozen=True)
class StageAProbeOutcome:
    """What the one paid question answered.

    ``reached_a_model`` is about the connection, not the result. A model that
    was asked, answered, and then declined to use a tool has been reached; that
    is a finding about the model, and stage A records findings rather than
    requiring successes.
    """

    reached_a_model: bool
    resolved_model: Optional[str]
    requested_deployment: str
    resource: str
    tools_offered: tuple[str, ...]
    tools_asked_for: tuple[str, ...]
    turns_taken: int
    stop_reason: str
    detail: str
    ledger: tuple[Mapping[str, Any], ...] = ()
    spent_usd: Optional[Decimal] = None
    conversation: Optional[ConversationOutcome] = field(
        default=None, repr=False, compare=False
    )

    @property
    def carried_the_first_result(self) -> bool:
        """Whether a later call went out holding an earlier tool's answer.

        Read from what each call reported carrying, so it is true only if a
        second request really was sent with the first exchange attached. Two
        turns that each started from nothing would leave this false, which is
        the failure this is here to catch.
        """
        return any(
            int(row.get("history_entries_sent") or 0) > 0 for row in self.ledger
        )

    @property
    def price_missing(self) -> bool:
        """Whether any call was made whose price nobody has committed."""
        return any(row.get("price_missing") for row in self.ledger)

    def as_dict(self) -> dict[str, Any]:
        return {
            "reached_a_model": self.reached_a_model,
            "resolved_model": self.resolved_model,
            "requested_deployment": self.requested_deployment,
            "resource": self.resource,
            "tools_offered": list(self.tools_offered),
            "tools_asked_for": list(self.tools_asked_for),
            "turns_taken": self.turns_taken,
            "carried_the_first_result": self.carried_the_first_result,
            "stop_reason": self.stop_reason,
            "detail": self.detail,
            "model_calls": [dict(row) for row in self.ledger],
            "spent_usd": (
                str(self.spent_usd) if self.spent_usd is not None else None
            ),
            "price_missing": self.price_missing,
        }


def run_stage_a_probe(
    *,
    client: Any,
    deployment: str,
    resource: str,
    budget: StageOneBudget,
    task_prompt: str,
    workspace_root: str | Path,
    max_output_tokens_per_turn: int,
    max_tool_calls: int,
    max_seconds: float,
    policy_profile_id: str = "offline-full-v1",
    prices: Mapping[str, ModelPrice] | None = None,
    tools: Sequence[str] = PROBE_TOOLS,
    request_timeout_seconds: float = 120.0,
) -> StageAProbeOutcome:
    """Ask a real deployment one task's worth of questions, and stop.

    The client is taken rather than built. Building one means choosing an
    endpoint, a route profile and a credential, and the repository already has
    one reviewed place that does all three; a second would be a second thing to
    keep right. Build it with :class:`core.azure_ai_clients.AzureAIClientFactory`
    and hand the lease's client in.

    Raises before spending anything if the tool list is wrong, because the
    cheapest moment to catch a probe that could reach the grader is before its
    first call.
    """
    wrong = check_probe_tools(tools)
    if wrong:
        raise ProbeToolsAreWrong("; ".join(wrong))

    voice = real_model_voice(
        client=client,
        deployment=deployment,
        resource=resource,
        budget=budget,
        instructions=PROBE_INSTRUCTIONS,
        max_output_tokens_per_turn=max_output_tokens_per_turn,
        prices=dict(prices or {}),
        request_timeout_seconds=request_timeout_seconds,
    )

    profile = AgenticV2Profile(
        tool_contract_version="2.0",
        policy_profile_id=policy_profile_id,
        foundation_only=True,
    )
    backend = AgenticV2FixtureBackend(root=workspace_root, profile=profile)
    lifecycle = AgenticV2Lifecycle()
    lifecycle.transition(LifecycleState.STARTED)
    lifecycle.transition(LifecycleState.ACTIVE)
    dispatcher = AgenticV2ToolDispatcher(
        backend=backend,
        lifecycle=lifecycle,
        max_total_calls=max_tool_calls,
    )

    outcome = run_model_conversation(
        task_prompt=task_prompt,
        voice=voice,
        desk=DispatcherToolDesk(dispatcher=dispatcher),
        limits=LoopLimits(
            max_model_turns=max_tool_calls,
            max_written_tokens_per_turn=max_output_tokens_per_turn,
            max_seconds=max_seconds,
            budget=budget,
            # Two identical requests in a row is a model going in circles, and
            # every circuit costs a full turn. Stage A is short enough that
            # allowing a third would be paying to watch it happen.
            max_repeats_of_one_request=2,
        ),
        tools_available=tuple(tools),
    )

    return StageAProbeOutcome(
        reached_a_model=bool(voice.calls),
        resolved_model=voice.resolved_model,
        requested_deployment=deployment,
        resource=resource,
        tools_offered=tuple(tools),
        tools_asked_for=outcome.tools_asked_for,
        turns_taken=len(voice.calls),
        stop_reason=outcome.stop_reason.value,
        detail=outcome.detail,
        ledger=tuple(voice.ledger()),
        spent_usd=voice.spent_usd(),
        conversation=outcome,
    )
