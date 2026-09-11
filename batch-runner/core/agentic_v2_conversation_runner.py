"""The join: a model conversation, a V2 run place, and a 220-task driver.

Three things existed and did not meet.
:func:`core.agentic_v2_conversation.run_model_conversation` asks a model and
runs what it asks for. :class:`core.agentic_v2_runner.AgenticV2ScriptedRunner`
admits a backend, enforces the tool contract and produces a verified record.
:func:`core.agentic_v2_run_driver.run_manifest` walks a fixed manifest, resumes,
collects files and stops when it should. This module is the wiring between them,
and it is the last structural piece of "model call → tool choice → isolated
``exec_run`` → result files → next model call" that was missing.

**Where the conversation's record goes, and why not in the result.**
:func:`core.agentic_v2_provenance.verify_agentic_v2_result` compares the
envelope's key set for exact equality, so an extra field would make every
successful run unverifiable. That is a good rule and this module does not bend
it: the conversation outcome is kept by :class:`TaskConversations`, beside the
run rather than inside it. A caller that wants the stop reason, the turns, or
the token counts asks that.

**Why a fresh budget per task and not one for the run.** A single
:class:`~core.agentic_v2_stage_one_budget.StageOneBudget` shared across 220
tasks would let the first tasks spend what the last ones needed, and the run
would report 180 honest results and 40 refusals that say nothing about the
model. So each task gets its own ceiling. The run-wide total is not thereby
abandoned — :attr:`TaskConversations.spent` sums what every task actually used,
and :meth:`TaskConversations.run_wide_refusal` is asked before each task, so an
overall cap still stops the run. Two different limits, both enforced, neither
pretending to be the other.

**On token counts.** Every :class:`~core.agentic_v2_conversation.TurnRecord`
that exists carries counts the provider really reported: the loop stops with
``model_reply_unusable`` rather than recording a reply whose usage it could not
read. So :func:`model_turns_of` may build :class:`~core.cost_receipts.CallUsage`
from them directly without a zero ever standing in for an unknown.

**Why this file is not in the foundation fingerprint.**
:data:`~core.agentic_v2_provenance._FOUNDATION_MODULES` covers the five files
that define and enforce the tool contract and write the record.
:mod:`core.agentic_v2_conversation` is already outside it and this file is too,
on the same reasoning: deciding *which* calls to make is not the same as
enforcing what a call may do, and every call this module causes still passes
through the fingerprinted ``dispatch_one``. Listing it here would make a change
to the wiring invalidate the attestation of runs that never used it.

**What this does not do.** It does not build a model client, name a deployment,
open :data:`exec_run`, change ``foundation_only`` or ``production_activation``,
or decide that something is affordable. The voice is a parameter. Passing a real
one is a separate, reviewable change, and the deployment it would reach is still
behind a role assignment nobody in this repository may grant.

It also does not pass an ``admitted_identity`` through to the runner, although
the runner accepts one. ``AgenticV2ScriptedRunner`` is the only file in ``core``
allowed to mention that argument, and
``test_nothing_in_this_repository_declares_a_non_default_identity`` enforces it
by reading every other module's source. That test is the standing evidence for
the claim that the guest is mapped and not run, and a wiring module that
forwarded the argument would retire the claim in exchange for a parameter no
caller uses today. When a run is admitted for real, adding it back is part of
that change, and that test is the line that changes with it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Optional, Sequence

from core.agentic_v2_conversation import (
    DispatcherToolDesk,
    LoopLimits,
    run_model_conversation,
)
from core.agentic_v2_contract import TOOL_NAMES
from core.agentic_v2_cost_binding import ModelTurn, retry_kind_for_error
from core.agentic_v2_runner import AgenticV2ScriptedRunner
from core.agentic_v2_stage_one_budget import StageOneBudget
from core.cost_receipts import CallUsage, RETRY_NONE


class ConversationRunnerRefused(RuntimeError):
    """The run was not wired up, because wiring it that way would be unsound."""


@dataclass(frozen=True)
class PerTaskCeilings:
    """What one task may spend before it is stopped.

    Every field is required. :class:`~core.agentic_v2_conversation.LoopLimits`
    already refuses a run with a ceiling nobody set, and this type exists so
    that the refusal happens once when the run is configured rather than 220
    times when it is too late to fix.
    """

    max_model_turns: int
    max_written_tokens_per_turn: int
    max_seconds: float
    max_model_calls: int
    max_input_tokens: int
    max_output_tokens: int
    max_repeats_of_one_request: int

    def fresh_limits(self) -> LoopLimits:
        """A new set of ceilings, with a budget that has spent nothing."""
        return LoopLimits(
            max_model_turns=self.max_model_turns,
            max_written_tokens_per_turn=self.max_written_tokens_per_turn,
            max_seconds=self.max_seconds,
            budget=StageOneBudget(
                max_model_calls=self.max_model_calls,
                max_input_tokens=self.max_input_tokens,
                max_output_tokens=self.max_output_tokens,
            ),
            max_repeats_of_one_request=self.max_repeats_of_one_request,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "max_model_turns": self.max_model_turns,
            "max_written_tokens_per_turn": self.max_written_tokens_per_turn,
            "max_seconds": self.max_seconds,
            "max_model_calls": self.max_model_calls,
            "max_input_tokens": self.max_input_tokens,
            "max_output_tokens": self.max_output_tokens,
            "max_repeats_of_one_request": self.max_repeats_of_one_request,
        }


def ceilings_from(plan: Mapping[str, Any], chosen: Any) -> PerTaskCeilings:
    """What one task may spend, read off the plan and the chosen settings row.

    Every field comes from something somebody wrote down. :class:`PerTaskCeilings`
    has no defaults for exactly that reason — a ceiling nobody set is not a
    ceiling — so a plan missing ``per_task_timeout_seconds`` raises here rather
    than running under an invented one.

    It lives beside the type rather than in the entry-point script because two
    things need the same answer and must not be able to give different ones: the
    runner, which enforces these ceilings, and the pre-registration, which
    promises them before the run starts. Written twice, a correction to one is a
    record describing a run that did not happen.

    ``chosen`` is anything carrying ``tool_calls_per_attempt`` and
    ``max_output_tokens_per_turn`` — the plan's chosen settings row, or the
    option the free check picked.
    """
    fixed = dict(plan.get("fixed_settings") or {})
    per_turn = int(chosen.max_output_tokens_per_turn)
    calls = int(chosen.tool_calls_per_attempt)
    return PerTaskCeilings(
        # One model call per tool call, plus the turn that finalises.
        max_model_turns=calls + 1,
        max_written_tokens_per_turn=per_turn,
        max_seconds=float(fixed["per_task_timeout_seconds"]),
        max_model_calls=calls + 1,
        # The loop re-sends the whole conversation every turn, so the input a
        # run may read is quadratic in its length. Priced that way in
        # price_the_options; bounded the same way here.
        max_input_tokens=per_turn * (calls + 1) * (calls + 2),
        max_output_tokens=per_turn * (calls + 1),
        max_repeats_of_one_request=2,
    )


@dataclass(frozen=True)
class RunWideCeilings:
    """What a whole run may spend, across every task and every attempt.
    questions. A per-task ceiling stops one task from running away; this stops
    the run. ``None`` on a field means nobody set that one, and — unlike the
    per-task case — that is allowed here, because a run may legitimately be
    bounded by turns and not by tokens.
    """

    max_model_calls: Optional[int] = None
    max_input_tokens: Optional[int] = None
    max_output_tokens: Optional[int] = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "max_model_calls": self.max_model_calls,
            "max_input_tokens": self.max_input_tokens,
            "max_output_tokens": self.max_output_tokens,
        }


@dataclass
class TaskConversations:
    """Every task's conversation, kept beside the runs rather than inside them.

    Keyed by ``(task_id, attempt)``, because a retried task holds two
    conversations and averaging them or keeping only the last would lose the
    first attempt's spend — which was charged for regardless of how the task
    ended.
    """

    per_task: PerTaskCeilings
    run_wide: RunWideCeilings = field(default_factory=RunWideCeilings)
    outcomes: dict[tuple[str, int], Any] = field(default_factory=dict)
    budgets: dict[tuple[str, int], StageOneBudget] = field(default_factory=dict)

    # -- what has been spent ------------------------------------------------

    @property
    def spent(self) -> dict[str, int]:
        """The run's totals, summed over every attempt of every task."""
        return {
            "model_calls": sum(b.model_calls_made for b in self.budgets.values()),
            "input_tokens": sum(b.input_tokens_used for b in self.budgets.values()),
            "output_tokens": sum(b.output_tokens_used for b in self.budgets.values()),
        }

    def run_wide_refusal(self) -> str | None:
        """Why the next task may not start, or ``None`` if it may.

        Asked before a task rather than after it, for the same reason
        :meth:`~core.agentic_v2_stage_one_budget.StageOneBudget.refusal_before_next_call`
        is: a ceiling checked afterwards is a report, not a limit.
        """
        spent = self.spent
        for name, used in (
            ("max_model_calls", spent["model_calls"]),
            ("max_input_tokens", spent["input_tokens"]),
            ("max_output_tokens", spent["output_tokens"]),
        ):
            cap = getattr(self.run_wide, name)
            if cap is not None and used >= cap:
                return (
                    f"this run has used {used} against a run-wide {name} of "
                    f"{cap}, so the next task was not started"
                )
        return None

    # -- recording ----------------------------------------------------------

    def limits_for(self, task_id: str, attempt: int) -> LoopLimits:
        limits = self.per_task.fresh_limits()
        assert limits.budget is not None  # fresh_limits always builds one
        self.budgets[(task_id, attempt)] = limits.budget
        return limits

    def record(self, task_id: str, attempt: int, outcome: Any) -> None:
        self.outcomes[(task_id, attempt)] = outcome

    def attempts_of(self, task_id: str) -> tuple[int, ...]:
        return tuple(
            sorted(attempt for (tid, attempt) in self.outcomes if tid == task_id)
        )

    def outcome_of(self, task_id: str, attempt: int) -> Any:
        return self.outcomes.get((task_id, attempt))

    def as_dict(self) -> dict[str, Any]:
        return {
            "per_task_ceilings": self.per_task.as_dict(),
            "run_wide_ceilings": self.run_wide.as_dict(),
            "spent": self.spent,
            "conversations": {
                f"{task_id}#{attempt}": outcome.as_dict()
                for (task_id, attempt), outcome in sorted(self.outcomes.items())
            },
        }


def conversation_seam(
    *,
    voice: Any,
    limits: LoopLimits,
    tools_available: Sequence[str] = TOOL_NAMES,
    cancel_requested: Optional[Callable[[], bool]] = None,
    on_outcome: Optional[Callable[[Any], None]] = None,
) -> Callable[[str, Callable[..., Any]], Any]:
    """A callable the runner can hand its dispatch function to.

    The desk is built around ``dispatch`` — the runner's own bookkeeping
    wrapper — and not around the dispatcher, so every call the model makes gets
    the cancel check, the deadline, the state commitment and the two chain
    appends that a scripted call gets. A desk that reached past it would produce
    a record that looks the same and proves less.
    """

    def converse(task_prompt: str, dispatch: Callable[..., Any]) -> Any:
        outcome = run_model_conversation(
            task_prompt=task_prompt,
            voice=voice,
            desk=DispatcherToolDesk(dispatch=dispatch),
            limits=limits,
            tools_available=tools_available,
            cancel_requested=cancel_requested,
        )
        if on_outcome is not None:
            on_outcome(outcome)
        return outcome

    return converse


def build_runner_factory(
    *,
    backend_factory: Callable[..., Any],
    profile: Mapping[str, Any],
    conversations: TaskConversations,
    attempt_of: Callable[[str], int],
    voice: Any = None,
    voice_for: Optional[Callable[[StageOneBudget], Any]] = None,
    budget_caps: Optional[Mapping[str, Any]] = None,
    required_backend_type: type | None = None,
    cancel_requested: Optional[Callable[[], bool]] = None,
    tools_available: Sequence[str] = TOOL_NAMES,
) -> Callable[[Any], AgenticV2ScriptedRunner]:
    """A ``runner_factory`` for :func:`core.agentic_v2_run_driver.run_manifest`.

    ``attempt_of`` is asked which attempt this is for a task, because the driver
    builds a runner before it knows how the attempt will end and the ledger
    needs the two kept apart. A caller with a journal in hand can answer from
    it; a caller without one can count.

    The run-wide ceiling is checked here rather than inside the runner. Refusing
    at the factory means the task is never started and no guest is booted for a
    run that has already spent what it had.

    **Give ``voice_for`` a real model, and ``voice`` only a scripted one.** The
    two are not interchangeable and the difference is money. A paid voice such
    as :class:`~core.agentic_v2_model_voice.AzureFoundryVoice` carries a
    :class:`~core.agentic_v2_stage_one_budget.StageOneBudget` of its own and
    refuses before the call that would pass it. This factory hands every task a
    *fresh* budget, so one paid voice built once and reused would hold the first
    task's budget for all 220: the early tasks would spend the whole run's
    allowance and every later task would be refused by a ceiling that has
    nothing to do with it. ``voice_for`` is handed each task's budget and builds
    a voice against it, so the two limits are one object and the arithmetic is
    the same one the ledger will settle.

    A scripted voice spends nothing and has no budget to get wrong, which is why
    ``voice`` still exists. Exactly one of the two is required — defaulting
    either way would mean guessing, and the wrong guess is the expensive one.
    """
    if (voice is None) == (voice_for is None):
        raise ConversationRunnerRefused(
            "a conversation needs exactly one of voice or voice_for: there is "
            "no default model, and choosing one here would be this module "
            "deciding what a run costs. Pass voice_for for a paid voice, so "
            "each task's voice is built against that task's own budget, and "
            "voice for a scripted one, which has no budget to share"
        )

    def build(task: Any) -> AgenticV2ScriptedRunner:
        refusal = conversations.run_wide_refusal()
        if refusal is not None:
            raise ConversationRunnerRefused(refusal)
        task_id = str(getattr(task, "task_id", "unknown-task"))
        attempt = int(attempt_of(task_id))
        limits = conversations.limits_for(task_id, attempt)
        if voice_for is not None:
            assert limits.budget is not None  # limits_for always builds one
            speaking = voice_for(limits.budget)
            if speaking is None:
                raise ConversationRunnerRefused(
                    f"voice_for returned nothing for {task_id!r}, so this task "
                    "would have run with no way to ask a model"
                )
        else:
            speaking = voice
        return AgenticV2ScriptedRunner(
            backend_factory=backend_factory,
            conversation=conversation_seam(
                voice=speaking,
                limits=limits,
                tools_available=tools_available,
                cancel_requested=cancel_requested,
                on_outcome=lambda outcome: conversations.record(
                    task_id, attempt, outcome
                ),
            ),
            profile=profile,
            budget_caps=budget_caps,
            cancel_requested=cancel_requested,
            required_backend_type=required_backend_type,
        )

    return build


def model_turns_of(
    outcome: Any,
    *,
    run_id: str,
    task_id: str,
    attempt: int,
    provider: str,
    requested_model: str,
    deployment: str | None = None,
    api_version: str | None = None,
    resolved_model: str | None = None,
    preceding_error: str | None = None,
) -> tuple[ModelTurn, ...]:
    """One task's conversation, as ledger entries.

    ``call_id`` is namespaced by run, task and attempt. The ids inside a
    conversation are the model's own and are only unique within it; writing them
    into a shared ledger unqualified would have task 200's third call settle
    against task 3's, and the corruption would show up as a total that is wrong
    by an unknowable amount months later.

    ``preceding_error`` is the error that caused this attempt to be made, or
    ``None`` for a first attempt. It decides the retry kind, via the same
    :func:`~core.agentic_v2_cost_binding.retry_kind_for_error` the rest of the
    accounting uses, so a retried call is not silently billed as a first one.

    That function returns ``None`` for an error after which there should be no
    next attempt, and its docstring forbids callers from putting a kind of their
    own choosing in that gap. So an attempt made after such an error is refused
    here rather than labelled ``retry_none`` — which would file a retry that
    should not exist as a first attempt and make the ledger's own retry counts
    the wrong shape. The attempt has already happened by the time this is
    called, so the refusal is loud on purpose: the caller's retry rule is wrong
    and the spend is real.

    ``resolved_model`` is what the provider said answered, which is not always
    what was asked for. Left ``None`` when the caller does not know — a receipt
    with no resolved model is incomplete, and incomplete is the honest state.
    """
    retry_kind = RETRY_NONE
    if preceding_error is not None:
        decided = retry_kind_for_error(preceding_error)
        if decided is None:
            raise ConversationRunnerRefused(
                f"this attempt followed {preceding_error!r}, after which there "
                "should have been no next attempt, so there is no honest retry "
                "kind to file it under; the retry rule that produced it is "
                "wrong and the calls it made were still charged for"
            )
        retry_kind = decided

    turns = getattr(outcome, "turns", ()) or ()
    entries: list[ModelTurn] = []
    for record in turns:
        entries.append(
            ModelTurn(
                call_id=f"{run_id}:{task_id}:{attempt}:{record.call_id}",
                usage=CallUsage(
                    input_tokens=record.input_tokens,
                    output_tokens=record.output_tokens,
                ),
                provider=provider,
                requested_model=requested_model,
                deployment=deployment,
                api_version=api_version,
                resolved_model=resolved_model,
                request_sha256=record.request_sha256,
                retry_kind=retry_kind,
            )
        )
    return tuple(entries)


__all__ = [
    "ConversationRunnerRefused",
    "PerTaskCeilings",
    "RunWideCeilings",
    "TaskConversations",
    "build_runner_factory",
    "conversation_seam",
    "model_turns_of",
]
