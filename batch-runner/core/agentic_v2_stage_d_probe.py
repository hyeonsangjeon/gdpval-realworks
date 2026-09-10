"""Stage D's one question, asked once, of a real model and a real machine.

Stage A asked whether a Foundry deployment shown a set of tools *chooses* one,
and whether the turn after that arrives holding the first turn's answer. It was
answered: yes, on ``gpt-5.4``, over four turns, for $0.0063. It also produced a
finding that shapes this module — the model spent three of its four turns on
``capabilities_query``, asking what it was allowed to do, before doing anything.
A stage sized for four turns would spend all of them establishing the ground.

Stage D asks the next question, and it is a different kind of question because
the tool it turns on is not a tool that answers — it is a tool that *boots*:

    Does a real model, offered a command runner, use it; does the command run
    inside a machine that is destroyed afterwards; do the files it wrote come
    back; and does the turn after that build on them?

Every clause is separately falsifiable and all four have to hold. A model that
calls ``exec_run`` and gets nothing back has been reached and has learnt
nothing. A command that runs and whose files are lost is worse than one that
never ran, because the model is told its work exists.

**Why this can offer ``exec_run`` when stage A could not.** Stage A left it out
because it was shut: :class:`AgenticV2FixtureBackend` accepts one fixed argument
list and answers ``capability_unavailable`` to everything else, so offering it
would have spent a paid turn to be told no. It is not shut here. The backend is
:class:`AgenticV2MicroVMBackend`, whose ``exec_run`` boots one machine per call,
and the launcher under it really stages a disk, boots, and carries the workspace
back. Nothing was unblocked to make that true — this probe builds its own
dispatcher, exactly as stage A's did, and the runner's backend-identity check at
``core/agentic_v2_runner.py`` is untouched and still refuses this backend. That
guard is D4's to open, as its own reviewable change, and opening it from here
would make everything else in this file worthless.

**What is still left out, and why.** ``finalize`` commits deliverables to the
grader, and marking is nearly the whole of stage one's cost; a probe that could
reach it is the stage-one run wearing a smaller name. ``environment_resolve``,
``environment_activate`` and ``browser_run`` are refused by this backend by
design — the machine has no route off itself — and offering a tool that always
refuses spends a paid turn to be told no. Both exclusions are enforced by
:func:`check_probe_tools` rather than promised by this docstring.

**Nothing is graded, and nothing is kept from the model's own words.** As in
stage A: fingerprints, token counts, a trimmed stated reason. No request body,
no reply body, no reasoning. What is added here is the boot record — what ran,
under which machine name, for how long it was allowed, and whether the workspace
came back — because a run whose commands cannot be accounted for is not evidence
of anything.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Sequence

from core.agentic_v2_contract import AgenticV2Lifecycle, AgenticV2Profile, LifecycleState
from core.agentic_v2_conversation import (
    ConversationOutcome,
    DispatcherToolDesk,
    LoopLimits,
    real_model_voice,
    run_model_conversation,
)
from core.agentic_v2_microvm_backend import AgenticV2MicroVMBackend, GuestImage
from core.agentic_v2_one_call_machine import WORKSPACE_DID_NOT_COME_BACK
from core.agentic_v2_stage_one_budget import StageOneBudget
from core.agentic_v2_substrate import AgenticV2SubstrateManifest
from core.agentic_v2_tools import AgenticV2ToolDispatcher
from core.execution_envelope_cost import ModelPrice


#: The tools stage D puts on offer, and the only ones.
#:
#: ``exec_run`` is the one the stage exists for. The other two are what make a
#: sensible sequence possible: ``capabilities_query`` is how a model finds out
#: what it may do — measured in stage A as the first thing it wants — and
#: ``workspace_apply`` is how it writes a script to run and reads back what the
#: command printed, since ``exec_run``'s result carries a returncode and nothing
#: else.
PROBE_TOOLS: tuple[str, ...] = (
    "capabilities_query",
    "workspace_apply",
    "exec_run",
)

#: Tools this backend answers by refusing, whatever is asked of them.
#:
#: Not a policy decision taken here — the machine has no route off itself, which
#: is stage C's fourth attack, so there is no index to resolve a requirement
#: against and nothing to drive a browser with. Offering one would spend a paid
#: turn to be told no, and would teach the model to ask again.
TOOLS_THIS_BACKEND_REFUSES: tuple[str, ...] = (
    "environment_resolve",
    "environment_activate",
    "browser_run",
)

#: Turns to allow, sized off what stage A measured rather than off a round number.
#:
#: Stage A spent three of four turns on ``capabilities_query`` before doing any
#: work. A stage D run has strictly more to do — ask what it may do, write a
#: script, run it, read what it printed, act on that — and a limit that stops it
#: mid-sequence answers nothing while still costing what it spent. Eight is that
#: sequence with room for one wrong guess.
TURNS_STAGE_D_NEEDS = 8

#: What the model is told it is doing.
#:
#: Says a command runner exists and does not say to call it, for the same reason
#: stage A's did not name a tool: a probe that instructs the model to call
#: ``exec_run`` and then reports that it called ``exec_run`` has established that
#: models follow instructions.
PROBE_INSTRUCTIONS = (
    "You are working inside an isolated task workspace. You have a small set of "
    "tools, including one that runs a command in a sandbox and returns its exit "
    "status. Commands do not return their output directly — anything a command "
    "prints is written into the workspace for you to read back. Use the tools to "
    "make progress on the task you are given. Ask for one tool at a time and use "
    "what comes back before deciding what to do next. If a tool answers that "
    "something is unavailable, do not ask for it again."
)


class ProbeToolsAreWrong(RuntimeError):
    """The probe's tool list would make it something other than stage D.

    A hard failure rather than a filter, on the same reasoning as stage A's: a
    list that has gained ``finalize`` or lost ``exec_run`` means someone changed
    what this run is, and quietly correcting it would hide that from them.
    """


class ProbeCannotDescribeItself(RuntimeError):
    """The backend could not say what it is, so no model call is worth making.

    Raised before spending. A run whose substrate manifest is missing produces a
    record with no verified image behind it — the numbers would be real and
    would refer to nothing checkable, which is worse than not having them.
    """


def check_probe_tools(tools: Sequence[str] = PROBE_TOOLS) -> list[str]:
    """Everything wrong with a stage D tool list, read from the list itself."""
    problems: list[str] = []
    offered = tuple(tools)
    if "exec_run" not in offered:
        problems.append(
            "the stage D probe does not offer exec_run, which is the only thing "
            "it exists to find out about. Without it this is stage A again, at "
            "stage A's price and stage D's name"
        )
    if "finalize" in offered:
        problems.append(
            "the stage D probe offers finalize, which commits deliverables and "
            "sends them to the grader. Stage D marks nothing, and marking is "
            "almost the whole of stage one's cost, so a probe that can reach it "
            "is the stage-one run under another name"
        )
    refused = [name for name in offered if name in TOOLS_THIS_BACKEND_REFUSES]
    if refused:
        problems.append(
            f"the stage D probe offers {sorted(refused)}, which this backend "
            "refuses whatever is asked of them — the machine has no route off "
            "itself. Offering one spends a paid turn to be told no"
        )
    unknown = [name for name in offered if name not in _known_tools()]
    if unknown:
        problems.append(
            f"the stage D probe offers {sorted(unknown)}, which the published "
            "tool contract does not define"
        )
    return problems


def _known_tools() -> frozenset[str]:
    from core.agentic_v2_contract import TOOL_NAMES

    return frozenset(TOOL_NAMES)


@dataclass(frozen=True)
class StageDProbeOutcome:
    """What the one paid question answered, and what ran while it was asked.

    Kept deliberately parallel to :class:`StageAProbeOutcome` so the two can be
    read side by side, and extended with the boot record — which is the half
    stage A had no equivalent of.

    ``reached_a_model`` is about the connection, not the result, as in stage A. A
    model that was asked, answered, and chose never to run a command has been
    reached; that is a finding about the model, and this records findings rather
    than requiring successes.
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
    guest_image: Mapping[str, str]
    substrate_manifest_sha256: Optional[str] = None
    boots: tuple[Mapping[str, Any], ...] = ()
    machines: tuple[Mapping[str, Any], ...] = ()
    collected: Mapping[str, Any] = field(default_factory=dict)
    ledger: tuple[Mapping[str, Any], ...] = ()
    spent_usd: Optional[Decimal] = None
    conversation: Optional[ConversationOutcome] = field(
        default=None, repr=False, compare=False
    )

    @property
    def carried_the_first_result(self) -> bool:
        """Whether a later call went out holding an earlier tool's answer."""
        return any(
            int(row.get("history_entries_sent") or 0) > 0 for row in self.ledger
        )

    @property
    def asked_to_run_something(self) -> bool:
        """Whether the model chose the command runner at all.

        False is a real answer and not a failure of the harness: it says a model
        shown this tool did not reach for it, which is a finding about the model
        and about how the tool is described to it.
        """
        return "exec_run" in self.tools_asked_for

    @property
    def a_command_really_ran(self) -> bool:
        """Whether a machine came back carrying an exit status the guest wrote.

        Keyed on the returncode rather than on ``boot_outcome`` because those
        two answer different questions. A command that exits 37 ran; a machine
        that overran its shutdown after the command finished also ran; a machine
        that started cleanly and whose guest wrote no status did not. Only the
        returncode separates them, and it is the guest's own file.
        """
        return any(
            row.get("booted")
            and isinstance(
                (row.get("result") or {}).get("data", {}).get("returncode"), int
            )
            for row in self.boots
        )

    @property
    def worked_on_after_running_something(self) -> bool:
        """Whether the model did anything *after* its first command came back.

        This is stage D's version of stage A's carried-the-first-result: a run
        that boots a machine on its last turn has proved the machine and nothing
        about the loop closing. The turn afterwards is what closes it.
        """
        asked = list(self.tools_asked_for)
        if "exec_run" not in asked:
            return False
        return len(asked) > asked.index("exec_run") + 1

    @property
    def carriage_failures(self) -> int:
        """Boots whose command finished and whose files did not come back.

        Counted separately from every other failure because it is the one that
        would otherwise be read as a model that produced nothing.
        """
        return sum(
            1 for row in self.boots
            if row.get("boot_outcome") == WORKSPACE_DID_NOT_COME_BACK
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
            "asked_to_run_something": self.asked_to_run_something,
            "a_command_really_ran": self.a_command_really_ran,
            "worked_on_after_running_something": self.worked_on_after_running_something,
            "carriage_failures": self.carriage_failures,
            "stop_reason": self.stop_reason,
            "detail": self.detail,
            "guest_image": dict(self.guest_image),
            "substrate_manifest_sha256": self.substrate_manifest_sha256,
            "boots": [dict(row) for row in self.boots],
            "machines": [dict(row) for row in self.machines],
            "collected": dict(self.collected),
            "model_calls": [dict(row) for row in self.ledger],
            "spent_usd": (
                str(self.spent_usd) if self.spent_usd is not None else None
            ),
            "price_missing": self.price_missing,
        }


def run_stage_d_probe(
    *,
    client: Any,
    deployment: str,
    resource: str,
    budget: StageOneBudget,
    task_prompt: str,
    workspace_root: str | Path,
    image: GuestImage,
    boot_one_command: Callable[..., Mapping[str, Any]],
    substrate_manifest: Optional[AgenticV2SubstrateManifest],
    max_output_tokens_per_turn: int,
    max_seconds: float,
    max_tool_calls: int = TURNS_STAGE_D_NEEDS,
    collect_outputs_into: str | Path | None = None,
    policy_profile_id: str = "offline-full-v1",
    prices: Mapping[str, ModelPrice] | None = None,
    tools: Sequence[str] = PROBE_TOOLS,
    request_timeout_seconds: float = 120.0,
) -> StageDProbeOutcome:
    """Ask a real deployment one task's worth of questions, over a real machine.

    The client and the launcher are both taken rather than built, for the same
    reason: each involves choices — an endpoint and a credential on one side, a
    kernel, a rootfs and an account to jail to on the other — that the
    repository already has one reviewed place for. A second place to make them
    is a second place to keep right. Build them with
    :class:`core.azure_ai_clients.AzureAIClientFactory` and
    :class:`core.agentic_v2_one_call_machine.OneCallMachine`.

    Refuses before spending anything if the tool list is wrong or the backend
    cannot describe itself. Both are cheap to establish and neither is cheaper
    later: the first would let a probe reach the grader, and the second would
    produce a paid record with no verified image behind it.

    **The workspace is collected before it is destroyed.** ``close()`` purges
    the work directory, which is the ``workdir: ephemeral-quota`` rule doing its
    job — a task must not inherit the previous task's files. But the files are
    also the entire product of the run, so they are copied out first, to
    ``collect_outputs_into`` or to ``<workspace_root>/collected`` beside the
    work directory. Without that step a run that succeeded would leave a boot
    record describing deliverables that no longer exist.
    """
    wrong = check_probe_tools(tools)
    if wrong:
        raise ProbeToolsAreWrong("; ".join(wrong))

    profile = AgenticV2Profile(
        tool_contract_version="2.0",
        policy_profile_id=policy_profile_id,
        foundation_only=True,
    )
    backend = AgenticV2MicroVMBackend(
        root=workspace_root,
        profile=profile,
        image=image,
        boot_one_command=boot_one_command,
        substrate_manifest=substrate_manifest,
    )
    started = backend.start(request_timeout_seconds)
    if not started.get("ok"):
        backend.close()
        raise ProbeCannotDescribeItself(
            "the backend would not describe itself — "
            f"{started.get('error_type')!r} — so a model call made now would be "
            "paid for and would refer to an image nothing on disk corresponds to"
        )

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

    lifecycle = AgenticV2Lifecycle()
    lifecycle.transition(LifecycleState.STARTED)
    lifecycle.transition(LifecycleState.ACTIVE)
    dispatcher = AgenticV2ToolDispatcher(
        backend=backend,
        lifecycle=lifecycle,
        max_total_calls=max_tool_calls,
    )

    try:
        outcome = run_model_conversation(
            task_prompt=task_prompt,
            voice=voice,
            desk=DispatcherToolDesk(dispatcher=dispatcher),
            limits=LoopLimits(
                max_model_turns=max_tool_calls,
                max_written_tokens_per_turn=max_output_tokens_per_turn,
                max_seconds=max_seconds,
                budget=budget,
                # Same reasoning as stage A: two identical requests in a row is
                # a model going in circles, and here each circuit can also cost
                # a boot rather than only a turn.
                max_repeats_of_one_request=2,
            ),
            tools_available=tuple(tools),
        )
        kept = _collect_the_workspace(
            backend.work,
            into=collect_outputs_into or Path(workspace_root) / "collected",
        )
        return StageDProbeOutcome(
            reached_a_model=bool(voice.calls),
            resolved_model=voice.resolved_model,
            requested_deployment=deployment,
            resource=resource,
            tools_offered=tuple(tools),
            tools_asked_for=tuple(record.tool_name for record in outcome.turns),
            turns_taken=len(voice.calls),
            stop_reason=outcome.stop_reason.value,
            detail=outcome.detail,
            guest_image=image.as_record(),
            substrate_manifest_sha256=(
                substrate_manifest.sha256 if substrate_manifest is not None else None
            ),
            boots=tuple(dict(row) for row in backend.boots),
            machines=tuple(
                dict(row) for row in getattr(boot_one_command, "record", ())
            ),
            collected=kept,
            ledger=tuple(voice.ledger()),
            spent_usd=voice.spent_usd(),
            conversation=outcome,
        )
    finally:
        # The workspace is ephemeral by policy and the run's whole product at
        # the same time, so it is copied out above and destroyed here. Both, in
        # that order -- keeping it would let the next task inherit these files,
        # and destroying it without collecting would leave a record of
        # deliverables that no longer exist.
        backend.close()


def _collect_the_workspace(work: str | Path, *, into: str | Path) -> dict[str, Any]:
    """Copy the work directory somewhere the teardown will not reach.

    Links are copied as links rather than followed. The carriage already
    refuses one pointing out of the workspace on the way back off the disk, so
    what survives to here points inside it — but following even those would
    duplicate content and turn a self-referential tree into an infinite one.

    Never raises. A collection that failed is recorded as one; letting it throw
    would lose the model calls, the boot record and the price alongside the
    files, and those are still true and still worth having.
    """
    work = Path(work)
    into = Path(into)
    try:
        if into.exists():
            shutil.rmtree(into)
        shutil.copytree(work, into, symlinks=True)
    except OSError as failure:
        return {
            "kept": False,
            "root": None,
            "files": 0,
            "bytes": 0,
            "grounds": f"the workspace could not be copied out: {failure}",
        }
    files = 0
    total = 0
    for path in into.rglob("*"):
        if path.is_symlink() or path.is_file():
            files += 1
            if not path.is_symlink():
                total += path.stat().st_size
    return {
        "kept": True,
        "root": into.as_posix(),
        "files": files,
        "bytes": total,
        "grounds": f"{files} files were copied out before the workspace was purged",
    }
