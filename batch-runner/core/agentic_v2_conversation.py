"""The repeated conversation with a model that Agentic Sandbox V2 stage one is.

Every other run place in the comparison asks the model once. It writes one
block of Python, somebody runs it, and whatever that block produced is the
answer. If a library is missing or a file is not shaped the way the model
guessed, the task simply fails.

Stage one is the other thing: the model asks for one tool, is shown what came
back, and chooses again with that in front of it. This module is that loop, and
only that loop. It does not run commands, it does not pick a model, and it
cannot be reached from the paid pipeline.

Three properties are worth stating plainly, because they are the reason the
module is shaped the way it is.

**A loop with no limit is not a loop, it is a leak.** Four separate ceilings
bound it: how many times the model may be asked, how much one reply may run to,
how long the whole thing may take, and how much it may cost. A ceiling that is
*missing* is treated exactly like one that has been *passed* — the loop refuses
to start rather than run without it. The alternative, defaulting to something
sensible, means the one run where somebody forgot is the run with no limit at
all.

**A failure the model is shown is not a failure of the loop.** Being told
"that did not work" and choosing something else is the entire behaviour being
measured. So an ordinary tool refusal is handed back to the model and the loop
carries on. Only failures that make carrying on meaningless — a limit reached,
the tool desk itself broken — end the run.

**What the model reasons is not kept.** The record holds what was asked for,
the short stated grounds for asking, and what came back. It has no field for a
chain of thought, and the fields it does have are bounded, so there is nowhere
for one to be smuggled through.

What is deliberately *not* here: any way to reach a real model.
:func:`real_model_voice` refuses, because reaching one costs money that has not
been approved and the run place is still shut in three separate places. The
loop is proven against deterministic stand-ins instead, which is enough to show
the control flow is right and spends nothing doing it.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Mapping, Optional, Protocol, Sequence

from core.agentic_v2_contract import TOOL_NAMES
from core.agentic_v2_provenance import canonical_sha256
from core.agentic_v2_stage_one_budget import StageOneBudget, StageOneBudgetExceeded
from core.agentic_v2_tools import AgenticV2ToolDispatcher


MOST_CHARACTERS_IN_A_STATED_REASON = 200
"""How much of the model's stated grounds for a tool call is kept.

Short on purpose. A sentence saying why a tool was chosen is useful when
reading back what happened. A field with no ceiling is somewhere a whole chain
of thought ends up, one paragraph at a time, and nobody notices until the
records are large and full of things that were never meant to be stored.
"""


# ---------------------------------------------------------------------------
# What the model may say back
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AskForTool:
    """The model wants one tool run, and says briefly why."""

    call_id: str
    tool_name: str
    arguments: Mapping[str, Any]
    why: str = ""
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(frozen=True)
class GaveUp:
    """The model stopped without committing anything.

    Distinct from finishing. Finishing means the model called ``finalize`` and
    the tool desk accepted it, which is the only way a task produces an answer.
    This is the model walking away, and it is recorded as such rather than
    being dressed up as a quiet success.
    """

    note: str = ""
    input_tokens: int = 0
    output_tokens: int = 0


ModelReply = AskForTool | GaveUp


@dataclass(frozen=True)
class ToolExchange:
    """One tool call and its answer, as the model is shown it.

    Separate from :class:`TurnRecord` on purpose. The model has to see what
    actually came back or it cannot react to it, which is the whole point. The
    record that is kept afterwards holds fingerprints instead, so the two
    cannot be confused for each other.
    """

    call_id: str
    tool_name: str
    arguments: Mapping[str, Any]
    ok: bool
    error_type: Optional[str]
    data: Mapping[str, Any]


@dataclass(frozen=True)
class ModelRequest:
    """Everything the model is given before it chooses its next action."""

    turn: int
    task_prompt: str
    tools_available: tuple[str, ...]
    history: tuple[ToolExchange, ...]
    turns_left: int


class ModelVoice(Protocol):
    """Anything that can answer :class:`ModelRequest` with a next action.

    ``makes_paid_calls`` is asked for rather than assumed, and a voice that does
    not declare it at all is refused — silence is read as "nobody has looked at
    this", not as "free". A voice that declares itself paid runs only on a run
    that carries an approved amount to charge it against, so wiring a real
    client in cannot be done by accident: it takes a budget somebody wrote down,
    which is a change a reviewer will see.
    """

    makes_paid_calls: bool

    def next_turn(self, request: ModelRequest) -> ModelReply: ...


@dataclass
class ScriptedVoice:
    """A stand-in model that says the same thing every time it is run.

    This is what proves the loop works without spending anything. Each reply is
    written down in advance and handed back in order; running past the end is
    the model going quiet, which the loop must survive rather than hang on.
    """

    replies: Sequence[ModelReply]
    makes_paid_calls: bool = False
    requests_seen: list[ModelRequest] = field(default_factory=list)

    def next_turn(self, request: ModelRequest) -> ModelReply:
        self.requests_seen.append(request)
        index = len(self.requests_seen) - 1
        if index >= len(self.replies):
            return GaveUp(note="the stand-in model ran out of written replies")
        return self.replies[index]


class NoModelVoiceAvailable(RuntimeError):
    """Raised where a real model would be reached, because none can be."""


def real_model_voice(
    *,
    client: Any = None,
    deployment: str = "",
    resource: str = "",
    budget: Any = None,
    instructions: str = "",
    max_output_tokens_per_turn: int = 0,
    **extra: Any,
) -> ModelVoice:
    """The seam a real model is plugged into, which refuses without an amount.

    Kept as a function that can refuse rather than left absent, so the refusal
    can be *run* by the free check instead of inferred from a file not
    existing. Called with nothing — which is how the free check calls it — it
    still raises.

    **The reason it raises is not that nothing has been approved.** It was that
    once; stage A has since been approved, run and paid for, so leaving the old
    sentence here would make this docstring say something false. What is still
    true is narrower and does not expire: an approval is a number in a document,
    and a document cannot stop the next call. :class:`StageOneBudget` is the
    object that knows what has already gone out and refuses before the turn that
    would pass the ceiling. A caller holding an approval and no budget has
    permission to spend and no way to stop, which is the case this refusal is
    for.

    Given a client and a budget, it hands back a voice that really asks a
    Microsoft Foundry deployment. Building the client is somebody else's job:
    this repository already has one reviewed place that chooses an endpoint, a
    route profile and a credential, and a second place would be a second thing
    to keep right.
    """
    from core.agentic_v2_model_voice import AzureFoundryVoice
    from core.agentic_v2_stage_one_budget import StageOneBudget

    # The amount is asked about first, before the client is even looked at. A
    # caller who has somewhere to send the call and no approval to send it is
    # the case this refusal is for, and it should get the answer about money
    # rather than an answer about plumbing.
    if not isinstance(budget, StageOneBudget):
        raise NoModelVoiceAvailable(
            "Agentic Sandbox V2 was asked for a real model with no budget to "
            "charge it against. Asking a model in a loop costs money on every "
            "turn, so an amount has to be written down first: see "
            "experiments/execution_envelope/agentic_stage_one_plan.yaml and "
            "scripts/check_agentic_stage_one_ceiling.py."
        )
    if client is None:
        raise NoModelVoiceAvailable(
            "Agentic Sandbox V2 was asked for a real model without a client to "
            "reach one with. Build one through core.azure_ai_clients rather "
            "than here, or use ScriptedVoice, which spends nothing."
        )
    return AzureFoundryVoice(
        client=client,
        deployment=deployment,
        resource=resource,
        budget=budget,
        instructions=instructions,
        max_output_tokens_per_turn=max_output_tokens_per_turn,
        **extra,
    )


# ---------------------------------------------------------------------------
# Where tool calls go
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ToolOutcome:
    """What one tool call produced."""

    ok: bool
    error_type: Optional[str] = None
    data: Mapping[str, Any] = field(default_factory=dict)
    request_sha256: Optional[str] = None
    result_sha256: Optional[str] = None
    result_bytes: int = 0
    finished: bool = False
    final_result: Optional[Mapping[str, Any]] = None
    replayed: bool = False

    @classmethod
    def worked(cls, **data: Any) -> "ToolOutcome":
        return cls(ok=True, data=dict(data))

    @classmethod
    def refused(cls, error_type: str) -> "ToolOutcome":
        return cls(ok=False, error_type=error_type)

    @classmethod
    def committed(cls, final_result: Mapping[str, Any]) -> "ToolOutcome":
        return cls(ok=True, finished=True, final_result=dict(final_result))


class ToolDesk(Protocol):
    """Anything that can run one tool call and report what happened."""

    def run_one(
        self,
        *,
        call_id: str,
        tool_name: str,
        arguments: Mapping[str, Any],
    ) -> ToolOutcome: ...


@dataclass
class DispatcherToolDesk:
    """Send tool calls to the real Agentic Sandbox V2 dispatcher.

    Nothing is loosened on the way through. The dispatcher checks the arguments
    against the published contract, counts the call against its own ceiling,
    and refuses ``exec_run`` exactly as it does today. This adapter only
    reshapes what comes back into the form the loop reads.

    ``dispatch`` exists because a dispatcher inside a live run is not reached
    directly. :class:`core.agentic_v2_runner.AgenticV2ScriptedRunner` owes every
    tool call a cancel check, a deadline check, a state commitment and two
    chain appends, and a desk that called ``dispatcher.dispatch`` itself would
    skip all four and produce a run record that looks like the others and is
    not. So the runner hands in its own bookkeeping wrapper and this adapter
    calls that instead. It takes the same keyword arguments and returns the
    same dispatch, so nothing about the reshaping below changes.
    """

    dispatcher: Optional[AgenticV2ToolDispatcher] = None
    dispatch: Optional[Callable[..., Any]] = None

    def __post_init__(self) -> None:
        if self.dispatch is None and self.dispatcher is None:
            raise ValueError(
                "a tool desk needs somewhere to send calls: pass a dispatcher, "
                "or the dispatch function of a run that is already open"
            )

    def run_one(
        self,
        *,
        call_id: str,
        tool_name: str,
        arguments: Mapping[str, Any],
    ) -> ToolOutcome:
        send = self.dispatch
        if send is None:
            # __post_init__ has already established that one of the two is
            # present, so this is the dispatcher and not None.
            send = self.dispatcher.dispatch  # type: ignore[union-attr]
        dispatch = send(call_id=call_id, name=tool_name, arguments=arguments)
        result = dispatch.result
        usage = result.get("usage_delta") or {}
        return ToolOutcome(
            ok=result.get("ok") is True,
            error_type=result.get("error_type"),
            data=dict(result.get("data") or {}),
            request_sha256=result.get("request_sha256"),
            result_sha256=result.get("result_sha256"),
            result_bytes=int(usage.get("output_bytes") or 0),
            finished=dispatch.finalized,
            final_result=dispatch.terminal_result,
            replayed=dispatch.replayed,
        )


@dataclass
class ScriptedToolDesk:
    """A stand-in tool desk that answers from a list written in advance.

    Running past the end answers ``capability_unavailable`` rather than
    raising, because that is what a real desk does when asked for something it
    cannot do, and a loop that keeps asking should be stopped by one of its own
    ceilings rather than by the stand-in falling over.
    """

    answers: Sequence[ToolOutcome] = ()
    calls: list[tuple[str, str, Mapping[str, Any]]] = field(default_factory=list)

    def run_one(
        self,
        *,
        call_id: str,
        tool_name: str,
        arguments: Mapping[str, Any],
    ) -> ToolOutcome:
        index = len(self.calls)
        self.calls.append((call_id, tool_name, dict(arguments)))
        if index >= len(self.answers):
            return ToolOutcome.refused("capability_unavailable")
        return self.answers[index]


# ---------------------------------------------------------------------------
# The ceilings
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LoopLimits:
    """The four ceilings a run may not pass, plus a guard against going in
    circles.

    Each may be ``None``, which means nobody has said what it should be. The
    loop treats that as a reason to refuse rather than filling in a default,
    because a default is only ever consulted on the one run where somebody
    forgot, and that is precisely the run that should not be allowed to go
    unbounded.
    """

    max_model_turns: Optional[int] = None
    max_written_tokens_per_turn: Optional[int] = None
    max_seconds: Optional[float] = None
    budget: Optional[StageOneBudget] = None
    max_repeats_of_one_request: Optional[int] = None

    def whats_missing(self) -> list[str]:
        """Every ceiling nobody has set, said in full rather than one at a
        time."""
        missing: list[str] = []
        if not _is_a_positive_whole_number(self.max_model_turns):
            missing.append(
                "nobody has said how many times the model may be asked, so "
                "the loop could run until something else stopped it"
            )
        if not _is_a_positive_whole_number(self.max_written_tokens_per_turn):
            missing.append(
                "nobody has said how much one reply may run to, so a single "
                "turn could be charged for any length at all"
            )
        if self.max_seconds is None or isinstance(self.max_seconds, bool) or (
            not isinstance(self.max_seconds, (int, float))
        ) or self.max_seconds <= 0:
            missing.append(
                "nobody has said how long the whole run may take, so a slow "
                "or stuck turn could hold the run open indefinitely"
            )
        if not isinstance(self.budget, StageOneBudget):
            missing.append(
                "nobody has said what this run may cost, so it could spend "
                "past whatever was approved without anything noticing"
            )
        if not _is_a_positive_whole_number(self.max_repeats_of_one_request):
            missing.append(
                "nobody has said how often the same request may be repeated, "
                "so a model asking the same thing over and over would spend "
                "the whole budget making no progress"
            )
        return missing


def _is_a_positive_whole_number(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


# ---------------------------------------------------------------------------
# What state the loop is in, and why it stopped
# ---------------------------------------------------------------------------


class LoopStep(Enum):
    """The named points a run passes through, in order.

    Written down as states rather than left implicit in log lines, so that
    reading back a run means reading a sequence rather than reconstructing one.
    """

    MODEL_ASKED = "model_asked"
    MODEL_REPLIED = "model_replied"
    TOOL_REQUESTED = "tool_requested"
    TOOL_ANSWERED = "tool_answered"
    NEXT_TURN = "next_turn"
    STOPPED = "stopped"


class StopReason(Enum):
    """Every way a run can end. There is no unlabelled ending."""

    FINISHED_NORMALLY = "finished_normally"
    MODEL_STOPPED_WITHOUT_FINISHING = "model_stopped_without_finishing"
    TURN_LIMIT_REACHED = "turn_limit_reached"
    WRITING_LIMIT_REACHED = "writing_limit_reached"
    TIME_LIMIT_REACHED = "time_limit_reached"
    COST_LIMIT_REACHED = "cost_limit_reached"
    TOOL_CALL_LIMIT_REACHED = "tool_call_limit_reached"
    REPEATED_REQUEST = "repeated_request"
    LIMIT_MISSING = "limit_missing"
    CANCELLED = "cancelled"
    MODEL_REPLY_UNUSABLE = "model_reply_unusable"
    TOOL_DESK_BROKE = "tool_desk_broke"
    PAID_CALL_REFUSED = "paid_call_refused"

    @property
    def produced_an_answer(self) -> bool:
        """Only one ending produces a deliverable, and it is named."""
        return self is StopReason.FINISHED_NORMALLY

    @property
    def is_a_limit(self) -> bool:
        """Whether the run was stopped by a ceiling rather than by going
        wrong."""
        return self in _LIMIT_REASONS


_LIMIT_REASONS = frozenset({
    StopReason.TURN_LIMIT_REACHED,
    StopReason.WRITING_LIMIT_REACHED,
    StopReason.TIME_LIMIT_REACHED,
    StopReason.COST_LIMIT_REACHED,
    StopReason.TOOL_CALL_LIMIT_REACHED,
    StopReason.REPEATED_REQUEST,
    StopReason.LIMIT_MISSING,
})


_ENDS_THE_RUN: Mapping[str, StopReason] = {
    # Ceilings the tool desk enforces for itself.
    "cancelled": StopReason.CANCELLED,
    "task_wall_time_exhausted": StopReason.TIME_LIMIT_REACHED,
    "tool_budget_exhausted": StopReason.TOOL_CALL_LIMIT_REACHED,
    # The desk itself is not working. Asking the model to react to this would
    # be asking it to work around a broken tool, which is not the behaviour
    # being measured and is not safe to encourage.
    "compute_backend_error": StopReason.TOOL_DESK_BROKE,
    "compute_cleanup_failed": StopReason.TOOL_DESK_BROKE,
    "compute_start_failed": StopReason.TOOL_DESK_BROKE,
    "fixture_backend_error": StopReason.TOOL_DESK_BROKE,
    "invalid_backend_result": StopReason.TOOL_DESK_BROKE,
    "invalid_backend_state": StopReason.TOOL_DESK_BROKE,
    "invalid_lifecycle_transition": StopReason.TOOL_DESK_BROKE,
    "invalid_result_envelope": StopReason.TOOL_DESK_BROKE,
    "runner_internal_error": StopReason.TOOL_DESK_BROKE,
    "substrate_manifest_missing": StopReason.TOOL_DESK_BROKE,
}
"""Tool failures that end the run, and the ending each one gets.

Everything absent from this table — including ``capability_unavailable``, which
is what asking to run a command gets today — is handed back to the model
instead. That is not leniency. Reading a refusal and choosing something else is
the one behaviour stage one exists to measure, so a loop that gave up at the
first refusal would measure nothing.
"""


# ---------------------------------------------------------------------------
# What is kept afterwards
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TurnRecord:
    """One turn, in the form that is kept.

    Built field by field from a fixed list rather than by copying whatever the
    model handed over. That is what makes the no-reasoning-kept property hold:
    a voice can attach anything it likes to its reply and none of it reaches
    here, because nothing here is copied wholesale.
    """

    turn: int
    call_id: str
    tool_name: str
    argument_names: tuple[str, ...]
    stated_reason: str
    ok: bool
    error_type: Optional[str]
    request_sha256: Optional[str]
    result_sha256: Optional[str]
    result_bytes: int
    input_tokens: int
    output_tokens: int
    replayed: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "turn": self.turn,
            "call_id": self.call_id,
            "tool_name": self.tool_name,
            "argument_names": list(self.argument_names),
            "stated_reason": self.stated_reason,
            "ok": self.ok,
            "error_type": self.error_type,
            "request_sha256": self.request_sha256,
            "result_sha256": self.result_sha256,
            "result_bytes": self.result_bytes,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "replayed": self.replayed,
        }


@dataclass
class _BilledButUnanswered:
    """A model reply that has been charged for and has no tool result yet.

    The loop asks the model, is answered, and only builds a :class:`TurnRecord`
    once the tool it asked for has run. Everything the ledger later charges for
    is read out of those records, so every way the run can end in between --
    and there are ten of them -- used to drop a call the provider had already
    billed.

    Measured on the first V2 stage that reached the model: 24 calls made, 18 in
    the ledger. The six that vanished were the last turn of each conversation
    that ended on a tool failure, and the receipts still read ``complete`` with
    no missing reason, because a ledger cannot miss a row it was never offered.
    A bill that is confidently 20% short is worse than one that says it is
    short.

    The event log already got this right -- ``model_replied`` is appended
    before the run decides what to do about the reply, and the comment there
    says why. This is the same rule applied to the record that carries the
    money.

    Mutable, unlike everything else kept here, and it never leaves the module:
    it is filled in as the loop learns what the reply asked for, so that a run
    ending after the tool was chosen still records which tool that was.

    Built only for a reply that reported what it used. A reply that did not is
    left out of ``turns`` entirely and counted in
    :attr:`ConversationOutcome.model_calls_not_counted`; the comment at the
    construction site says why a zero would be the worse answer.
    """

    turn: int
    input_tokens: int
    output_tokens: int
    call_id: str = ""
    tool_name: str = ""
    argument_names: tuple[str, ...] = ()
    stated_reason: str = ""

    def as_turn(self, stop_reason: str) -> TurnRecord:
        """The charged call, said as a turn that got no result.

        ``ok`` is false and ``error_type`` is why the run stopped, so a reader
        cannot mistake this for a tool that answered. The three hashes and the
        byte count are the empty values because nothing came back -- a zero
        here is the absence of a result, not a measurement of one.
        """
        return TurnRecord(
            turn=self.turn,
            # Unique within the conversation either way: the model's own id
            # when it got far enough to name one, and the turn number when it
            # did not. `model_turns_of` namespaces both by run, task and
            # attempt before they reach the ledger.
            call_id=self.call_id or f"turn-{self.turn}-no-tool-result",
            tool_name=self.tool_name,
            argument_names=self.argument_names,
            stated_reason=self.stated_reason,
            ok=False,
            error_type=stop_reason,
            request_sha256=None,
            result_sha256=None,
            result_bytes=0,
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            replayed=False,
        )


@dataclass(frozen=True)
class LoopEvent:
    """One point the run passed through."""

    step: LoopStep
    turn: int
    detail: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "step": self.step.value,
            "turn": self.turn,
            "detail": dict(self.detail),
        }


@dataclass(frozen=True)
class ConversationOutcome:
    """How a run ended, and everything kept from it."""

    stop_reason: StopReason
    detail: str
    turns: tuple[TurnRecord, ...]
    events: tuple[LoopEvent, ...]
    final_result: Optional[Mapping[str, Any]] = None
    budget_after: Optional[Mapping[str, Any]] = None

    @property
    def produced_an_answer(self) -> bool:
        return self.stop_reason.produced_an_answer

    @property
    def model_turns_used(self) -> int:
        return sum(
            1 for event in self.events if event.step is LoopStep.MODEL_ASKED
        )

    @property
    def tools_asked_for(self) -> tuple[str, ...]:
        """Which tool each turn asked for, skipping the turns that asked none.

        Every turn is in ``turns`` now, including the charged ones that ended
        the run before a tool answered, and some of those stopped before the
        model had named a tool at all. Those carry an empty name, which is a
        true statement about the turn and a false entry in a list of tools —
        so they are left out here rather than reported as a tool called ``""``.
        A turn that *did* name a tool stays in whether or not the tool ran: the
        model asked for it, and that is what this list is.
        """
        return tuple(
            record.tool_name for record in self.turns if record.tool_name
        )

    @property
    def model_calls_not_counted(self) -> int:
        """Replies that arrived without usable token counts, so are unpriced.

        Not a cost and not a zero — a number *about* the account rather than in
        it. A reply the provider sent with no usage, or with a usage the voice
        could not read, was still charged for, and this is how many of those a
        run had. Anything above zero means ``turns`` is short by that much and
        the receipt built from it is a floor.

        Kept as a count rather than an estimate on purpose. Guessing what an
        uncounted call would have cost is the one arithmetic this codebase does
        not do.
        """
        return sum(
            1
            for event in self.events
            if event.step is LoopStep.MODEL_REPLIED
            and event.detail.get("counted") is False
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "stop_reason": self.stop_reason.value,
            "detail": self.detail,
            "produced_an_answer": self.produced_an_answer,
            "model_turns_used": self.model_turns_used,
            "model_calls_not_counted": self.model_calls_not_counted,
            "turns": [record.as_dict() for record in self.turns],
            "events": [event.as_dict() for event in self.events],
            "budget_after": (
                dict(self.budget_after) if self.budget_after is not None else None
            ),
        }


# ---------------------------------------------------------------------------
# The loop
# ---------------------------------------------------------------------------


def run_model_conversation(
    *,
    task_prompt: str,
    voice: ModelVoice,
    desk: ToolDesk,
    limits: LoopLimits,
    tools_available: Sequence[str] = TOOL_NAMES,
    cancel_requested: Optional[Callable[[], bool]] = None,
    clock: Callable[[], float] = time.monotonic,
) -> ConversationOutcome:
    """Ask the model, run what it asked for, show it the answer, repeat.

    Ends the moment any ceiling is reached, the model commits an answer, or the
    model walks away. It never reaches for a different tool, a different model,
    or a different run place on the model's behalf: a run that could not finish
    is reported as one, because a quiet substitution produces a result nobody
    can attribute to anything.
    """
    asked_to_stop = cancel_requested or (lambda: False)
    events: list[LoopEvent] = []
    turns: list[TurnRecord] = []
    history: list[ToolExchange] = []
    repeats: dict[str, int] = {}
    started_at = clock()
    turn = 0
    # Set the moment a reply's usage is known, cleared the moment that turn is
    # recorded. While it holds something, this run owes the ledger a call.
    billed: Optional[_BilledButUnanswered] = None

    def finish(reason: StopReason, detail: str, **extra: Any) -> ConversationOutcome:
        # Before the outcome is built, not after: a charged call that has no
        # tool result is still a charged call, and this is the last place it
        # can be written down. Ten paths between the reply arriving and the
        # turn being recorded end here, and every one of them used to lose it.
        nonlocal billed
        if billed is not None:
            turns.append(billed.as_turn(reason.value))
            billed = None
        events.append(LoopEvent(
            step=LoopStep.STOPPED,
            turn=turn,
            detail={"stop_reason": reason.value, "why": detail},
        ))
        return ConversationOutcome(
            stop_reason=reason,
            detail=detail,
            turns=tuple(turns),
            events=tuple(events),
            budget_after=(
                limits.budget.as_dict()
                if isinstance(limits.budget, StageOneBudget)
                else None
            ),
            **extra,
        )

    # Asked before anything else, in two steps, because "did not say" and "said
    # yes" are different problems with different answers.
    #
    # A voice that does not declare itself is refused outright, and no budget
    # lets it through. Silence is not a claim to be free, and it is not a claim
    # to be paid-and-budgeted either — it is a voice nobody has looked at, and
    # the whole point of the declaration is that somebody looked.
    declared_paid = getattr(voice, "makes_paid_calls", None)
    if declared_paid is None:
        return finish(
            StopReason.PAID_CALL_REFUSED,
            "this model did not say whether asking it costs anything, so it was "
            "treated as though it does. Nothing was asked",
        )

    # A voice that says yes is allowed through on one condition: this run
    # carries a budget. That is not a formality. A StageOneBudget cannot be
    # built without somebody having written down an amount, it is asked before
    # every call rather than after, and it refuses rather than reports. So
    # "paid and budgeted" is a different thing from "paid", and only the first
    # may run.
    #
    # Everything that was refused before is still refused. A stand-in that
    # merely declares itself paid, with no budget, stops here exactly as it did.
    if declared_paid and not isinstance(limits.budget, StageOneBudget):
        return finish(
            StopReason.PAID_CALL_REFUSED,
            "this model would be charged for, and this run carries no budget "
            "to charge it against. Nothing was asked",
        )

    missing = limits.whats_missing()
    if missing:
        return finish(
            StopReason.LIMIT_MISSING,
            "this run has no ceiling on something it needs one for, so it was "
            "refused before the model was asked anything: " + "; ".join(missing),
        )
    # Every ceiling is present from here on, so the loop may read them without
    # guarding each use.
    max_turns = int(limits.max_model_turns or 0)
    max_written = int(limits.max_written_tokens_per_turn or 0)
    max_seconds = float(limits.max_seconds or 0.0)
    max_repeats = int(limits.max_repeats_of_one_request or 0)
    budget: StageOneBudget = limits.budget  # type: ignore[assignment]

    while True:
        if asked_to_stop():
            return finish(
                StopReason.CANCELLED,
                "the run was asked to stop before the model was asked again",
            )
        if turn >= max_turns:
            return finish(
                StopReason.TURN_LIMIT_REACHED,
                f"the model has been asked {turn} times, which is all the "
                f"{max_turns} this run was allowed",
            )
        elapsed = clock() - started_at
        if elapsed >= max_seconds:
            return finish(
                StopReason.TIME_LIMIT_REACHED,
                f"this run has taken {elapsed:.3f} seconds, which is all the "
                f"{max_seconds:.3f} it was allowed",
            )
        refusal = budget.refusal_before_next_call()
        if refusal is not None:
            return finish(StopReason.COST_LIMIT_REACHED, refusal)

        turn += 1
        events.append(LoopEvent(
            step=LoopStep.MODEL_ASKED,
            turn=turn,
            detail={
                "tool_results_so_far": len(history),
                "turns_left": max_turns - turn,
            },
        ))
        request = ModelRequest(
            turn=turn,
            task_prompt=task_prompt,
            tools_available=tuple(str(name) for name in tools_available),
            history=tuple(history),
            turns_left=max_turns - turn,
        )
        try:
            reply = voice.next_turn(request)
        except Exception as error:  # noqa: BLE001 - any failure ends the run
            return finish(
                StopReason.MODEL_REPLY_UNUSABLE,
                f"asking the model failed: {type(error).__name__}",
            )

        usage = _usage_of(reply)
        if usage is None:
            return finish(
                StopReason.MODEL_REPLY_UNUSABLE,
                "the model's reply did not say how much it used, or said "
                "something that is not a count, so it cannot be charged for "
                "and the run cannot be allowed to continue",
            )
        input_tokens, output_tokens = usage
        # The provider has answered and will bill for it. From here until the
        # turn is recorded, this run owes the ledger a call, and `finish` is
        # what pays it if the run stops first.
        #
        # Unless the reply came back uncounted, which is what a zero input
        # count means. No call to a model costs nothing on the way in: the task
        # prompt alone is thousands of tokens, and every provider bills for it.
        # A reply carrying zero input tokens therefore did not report its
        # usage; something downstream filled the field in. The real voice does
        # exactly that — when a response arrives with no `usage`, it walks away
        # with a note saying so, and the walk-away's token fields default to
        # zero.
        #
        # Such a call is not recorded, and that is deliberate. Filing it would
        # put `0` in the ledger, and a zero settles to `$0.00` on a `complete`
        # receipt: a measured-looking figure for a call nobody measured. That
        # is worse than the gap it would paper over, because a gap can be seen.
        # It is counted in `model_calls_not_counted` instead, which is a number
        # about the account rather than in it.
        #
        # The same applies to the `usage is None` branch above, for the same
        # reason. Both are the honest edge of a record written after the fact;
        # closing them needs a reservation written *before* the call, which is
        # a different change to a different object.
        counted = input_tokens > 0
        billed = (
            _BilledButUnanswered(
                turn=turn, input_tokens=input_tokens, output_tokens=output_tokens
            )
            if counted
            else None
        )
        # What the charged call asked for, read here rather than after the
        # ceilings below, so a turn stopped by one of them still records which
        # tool the money was spent asking for. Three of the five tasks in the
        # first paid stage ended on a tool the backend refuses, and "which
        # tool" is the whole finding.
        #
        # Reading it decides nothing. `_readable_request` only looks at four
        # attributes and has no side effects, and the refusal for a reply that
        # is not a usable request stays exactly where it was — below the
        # walk-away and both ceilings — so which stop wins an argument between
        # them is unchanged.
        asked = _readable_request(reply) if isinstance(reply, AskForTool) else None
        if billed is not None and asked is not None:
            billed.call_id = asked[0]
            billed.tool_name = asked[1]
            billed.argument_names = tuple(sorted(asked[2]))
            billed.stated_reason = asked[3]
        # Recorded as having happened before the run decides what to do about
        # it, so that a trace read back afterwards shows the reply arriving
        # rather than seeming to vanish between the asking and the stopping.
        events.append(LoopEvent(
            step=LoopStep.MODEL_REPLIED,
            turn=turn,
            detail={
                "kind": type(reply).__name__,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                # False means this reply is missing from the account below,
                # and is the only place that says so.
                "counted": counted,
            },
        ))
        try:
            budget.record(input_tokens=input_tokens, output_tokens=output_tokens)
        except StageOneBudgetExceeded as error:
            return finish(StopReason.COST_LIMIT_REACHED, str(error))
        except ValueError as error:
            return finish(
                StopReason.MODEL_REPLY_UNUSABLE,
                f"the model's reply could not be charged for: {error}",
            )

        if output_tokens > max_written:
            return finish(
                StopReason.WRITING_LIMIT_REACHED,
                f"the model wrote {output_tokens} tokens in one turn, past the "
                f"{max_written} this run allows in one turn",
            )

        if isinstance(reply, GaveUp):
            return finish(
                StopReason.MODEL_STOPPED_WITHOUT_FINISHING,
                "the model stopped without committing an answer"
                + _appended_note(reply.note),
            )

        # `asked` was read above, before the ceilings, and this is where it is
        # acted on. A reply that walked away never reaches here.
        if asked is None:
            return finish(
                StopReason.MODEL_REPLY_UNUSABLE,
                "the model's reply was not a usable tool request, so there is "
                "nothing to run and nothing to show it next",
            )
        call_id, tool_name, arguments, why = asked

        fingerprint = canonical_sha256({"name": tool_name, "arguments": arguments})
        repeats[fingerprint] = repeats.get(fingerprint, 0) + 1
        if repeats[fingerprint] > max_repeats:
            return finish(
                StopReason.REPEATED_REQUEST,
                f"the model asked for {tool_name} with the same arguments "
                f"{repeats[fingerprint]} times, past the {max_repeats} this "
                "run allows. It is going in circles rather than making "
                "progress, and every further turn would be charged for",
            )

        if asked_to_stop():
            return finish(
                StopReason.CANCELLED,
                "the run was asked to stop before the tool was run",
            )
        elapsed = clock() - started_at
        if elapsed >= max_seconds:
            return finish(
                StopReason.TIME_LIMIT_REACHED,
                f"this run has taken {elapsed:.3f} seconds, which is all the "
                f"{max_seconds:.3f} it was allowed",
            )

        events.append(LoopEvent(
            step=LoopStep.TOOL_REQUESTED,
            turn=turn,
            detail={
                "call_id": call_id,
                "tool_name": tool_name,
                "argument_names": sorted(arguments),
            },
        ))
        try:
            outcome = desk.run_one(
                call_id=call_id, tool_name=tool_name, arguments=arguments
            )
        except Exception as error:  # noqa: BLE001 - any failure ends the run
            return finish(
                StopReason.TOOL_DESK_BROKE,
                f"running the tool failed: {type(error).__name__}",
            )
        if not isinstance(outcome, ToolOutcome):
            return finish(
                StopReason.TOOL_DESK_BROKE,
                "the tool desk answered with something that is not a tool "
                "outcome, so what happened to the task environment is unknown",
            )

        turns.append(TurnRecord(
            turn=turn,
            call_id=call_id,
            tool_name=tool_name,
            argument_names=tuple(sorted(arguments)),
            stated_reason=why,
            ok=outcome.ok,
            error_type=outcome.error_type,
            request_sha256=outcome.request_sha256,
            result_sha256=outcome.result_sha256,
            result_bytes=outcome.result_bytes,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            replayed=outcome.replayed,
        ))
        # Paid for and now recorded, so the debt `finish` would otherwise settle
        # is cleared. Left set, the next stop would write the same turn twice
        # and the ledger would be wrong in the other direction.
        billed = None
        history.append(ToolExchange(
            call_id=call_id,
            tool_name=tool_name,
            arguments=dict(arguments),
            ok=outcome.ok,
            error_type=outcome.error_type,
            data=dict(outcome.data),
        ))
        events.append(LoopEvent(
            step=LoopStep.TOOL_ANSWERED,
            turn=turn,
            detail={
                "call_id": call_id,
                "tool_name": tool_name,
                "ok": outcome.ok,
                "error_type": outcome.error_type,
                "replayed": outcome.replayed,
                "finished": outcome.finished,
            },
        ))

        if outcome.finished:
            if not isinstance(outcome.final_result, Mapping):
                return finish(
                    StopReason.TOOL_DESK_BROKE,
                    "the tool desk said the task was committed but handed back "
                    "no answer, so there is nothing to report as the result",
                )
            return finish(
                StopReason.FINISHED_NORMALLY,
                f"the model committed an answer on turn {turn}",
                final_result=dict(outcome.final_result),
            )

        ends_it = _ENDS_THE_RUN.get(str(outcome.error_type or ""))
        if ends_it is not None:
            return finish(
                ends_it,
                f"{tool_name} answered {outcome.error_type}, which the model "
                "cannot usefully be asked to work around",
            )

        events.append(LoopEvent(
            step=LoopStep.NEXT_TURN,
            turn=turn,
            detail={
                "showing_the_model": (
                    "a result" if outcome.ok else f"a refusal: {outcome.error_type}"
                ),
            },
        ))


def _usage_of(reply: Any) -> Optional[tuple[int, int]]:
    """How much a reply cost, or ``None`` if it did not say in plain counts."""
    if not isinstance(reply, (AskForTool, GaveUp)):
        return None
    values: list[int] = []
    for name in ("input_tokens", "output_tokens"):
        value = getattr(reply, name, None)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            return None
        values.append(value)
    return values[0], values[1]


def _readable_request(
    reply: AskForTool,
) -> Optional[tuple[str, str, dict[str, Any], str]]:
    """Pull the four things a tool call needs out of a reply, or refuse it.

    Only these four are read. Anything else attached to the reply is left where
    it is, which is what keeps a chain of thought out of the record even when
    the thing answering is trying to hand one over.
    """
    call_id = getattr(reply, "call_id", None)
    tool_name = getattr(reply, "tool_name", None)
    arguments = getattr(reply, "arguments", None)
    why = getattr(reply, "why", "")
    if not isinstance(call_id, str) or not call_id:
        return None
    if not isinstance(tool_name, str) or not tool_name:
        return None
    if not isinstance(arguments, Mapping):
        return None
    if any(not isinstance(key, str) for key in arguments):
        return None
    if not isinstance(why, str):
        why = ""
    return (
        call_id,
        tool_name,
        dict(arguments),
        why[:MOST_CHARACTERS_IN_A_STATED_REASON],
    )


def _appended_note(note: Any) -> str:
    if not isinstance(note, str) or not note.strip():
        return ""
    return ": " + note.strip()[:MOST_CHARACTERS_IN_A_STATED_REASON]
