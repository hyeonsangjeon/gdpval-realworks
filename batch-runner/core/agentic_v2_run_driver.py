"""Walking a fixed manifest through the parts, and stopping when it should.

Every piece a 220-task run needs now exists and nothing drives them. The runner
does one task. The journal knows what to resume. The collector puts files on
disk. The report adapter makes a row. This is the loop that connects them, and
it is the last piece of step 4 that is not a single-task concern.

**Why the runner is rebuilt for every task rather than reused.** A backend's
``close()`` purges its workspace, and the runner closes the backend in a
``finally`` at the end of every ``run()`` — so the workspace is already gone by
the time the driver sees a result. What a reused *runner* would carry across
tasks is not files but settings and accumulated state, and the whole claim being
tested is that one task cannot reach the next. A factory called per task makes
that structural instead of a promise. It also costs nothing: the expensive part
is the guest, and the guest was always per-task.

**Why deliverables come out of the result rather than off the disk.** For the
same reason. By the time ``run()`` returns, the workspace is purged; the bytes
survive only in the result envelope, already checked against the digests the
guest declared. Anything not collected from there is unrecoverable.

**Why a collection failure is a runner defect and not a model failure.** The
contract already validates every deliverable path at ``finalize``. A path that
passes that and then fails the collector means the two disagree, which is this
code's problem and not the work under test's. Recording it as
``invalid_backend_result`` puts it in the ``runner_defect`` disposition, which
is what the stop rule below counts — so a systematic disagreement halts the run
instead of quietly failing 220 tasks in the same way.

**Which stop rules this can actually see.** The pre-registration writes eight,
in prose, and it would be easy to claim all eight by naming them. Four of them
are about the run's own record — the seal, a pinned deployment, a gate, an
approved amount — and are checked before anything starts, by code that is not
this. :data:`RULES_THIS_DRIVER_WATCHES` names by index the ones a loop can
observe while it runs, and :data:`RULES_THIS_DRIVER_CANNOT_SEE` names the rest.
Both are derived from :data:`~core.agentic_v2_preregistration.STOP_RULES` rather
than retyped, so a rule added there without a decision here fails a test.

Nothing here asks a model. The model is behind ``runner_factory``, which is the
seam the caller supplies and the one thing still blocked.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from core.agentic_v2_cost_binding import (
    DISPOSITION_RUNNER_DEFECT,
    describe_run_outcome,
)
from core.agentic_v2_deliverable_collection import (
    Collection,
    CollectionRefused,
    collect_deliverables,
)
from core.agentic_v2_preregistration import STOP_RULES
from core.agentic_v2_run_report import (
    build_agentic_v2_metrics,
    build_result_row,
    summarise_v2_run,
)
from core.agentic_v2_task_journal import (
    DECISION_RUN,
    MOST_ATTEMPTS_PER_TASK,
    OUTCOME_FAILED,
    OUTCOME_FINISHED,
    TaskJournal,
)
from core.cost_receipts import STATUS_COMPLETE


#: How many consecutive runner-defect tasks end the run.
#:
#: The figure is the pre-registration's, not a new one.
CONSECUTIVE_RUNNER_DEFECTS_THAT_STOP_A_RUN = 3

#: Indices into :data:`~core.agentic_v2_preregistration.STOP_RULES` that this
#: loop enforces itself, with what it watches for.
RULES_THIS_DRIVER_WATCHES: dict[int, str] = {
    6: "counts consecutive runner_defect dispositions and stops at three",
    7: "stops on compute_cleanup_failed, because the next task would inherit "
    "a guest that was not cleaned",
}

#: The rest, and who checks them.
#:
#: Written down because a driver that silently enforced two of eight would read
#: as a driver that enforced eight.
RULES_THIS_DRIVER_CANNOT_SEE: dict[int, str] = {
    0: "the deployment is pinned and compared where the model client is built",
    1: "a model or deployment switch is visible to the voice, not to this loop",
    2: "the seal is verified before a run starts",
    3: "gate state is checked by the gate's own free check",
    4: "budget and approved amount are enforced by the voice before a call",
    5: "the ledger's writability is the ledger's own refusal",
}

if set(RULES_THIS_DRIVER_WATCHES) | set(RULES_THIS_DRIVER_CANNOT_SEE) != set(
    range(len(STOP_RULES))
):  # pragma: no cover - import guard
    raise RuntimeError(
        "a stop rule was added or removed without deciding whether this driver "
        "can see it"
    )


class DriverRefused(RuntimeError):
    """The run was not started, because starting it would have been unsound."""


@dataclass(frozen=True)
class TaskToRun:
    """One task of the fixed manifest, as the driver needs it."""

    task_id: str
    prompt: str
    occupation: str = "professional"
    sector: str = ""
    reference_files: tuple[Any, ...] = ()


@dataclass(frozen=True)
class StoppedEarly:
    """Why the loop ended before the manifest did."""

    rule_index: int
    rule: str
    detail: str
    after_task: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "rule_index": self.rule_index,
            "rule": self.rule,
            "detail": self.detail,
            "after_task": self.after_task,
        }


@dataclass
class RunOutcome:
    """What the run did, and what is left of the manifest."""

    run_id: str
    rows: list[dict[str, Any]] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    stopped: StoppedEarly | None = None
    skipped_on_resume: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "results": list(self.rows),
            "summary": dict(self.summary),
            "stopped_early": None if self.stopped is None else self.stopped.as_dict(),
            "skipped_on_resume": list(self.skipped_on_resume),
        }


def _attempt_once(
    task: TaskToRun,
    *,
    runner_factory: Callable[[TaskToRun], Any],
    run_id: str,
    condition_name: str,
) -> dict[str, Any]:
    """One task, one fresh runner, closed whatever happens."""
    runner = runner_factory(task)
    try:
        result = runner.run(
            task.prompt,
            list(task.reference_files),
            task.occupation,
            run_id=run_id,
            condition_name=condition_name,
            task_id=task.task_id,
        )
    finally:
        close = getattr(runner, "close", None)
        if callable(close):
            try:
                close()
            except Exception:
                # A runner that cannot close has already returned its result;
                # losing it here would turn a recorded task into no task at all.
                pass
    if not isinstance(result, Mapping):
        raise DriverRefused(
            f"the runner returned {type(result).__name__} for {task.task_id!r}, "
            "which is not a result envelope"
        )
    return dict(result)


def _collect_or_fail(
    result: Mapping[str, Any],
    *,
    task: TaskToRun,
    into: Path,
    attempt_name: str,
) -> tuple[Collection | None, dict[str, Any]]:
    """Put a successful task's files on disk, or turn the task into a failure."""
    try:
        return collect_deliverables(
            result, task_id=task.task_id, into=into, attempt_name=attempt_name
        ), dict(result)
    except (CollectionRefused, OSError) as error:
        spoiled = dict(result)
        spoiled["success"] = False
        spoiled["error"] = "invalid_backend_result"
        spoiled["collection_error"] = str(error)
        spoiled["files"] = []
        return None, spoiled


def run_manifest(
    tasks: Iterable[TaskToRun],
    *,
    run_id: str,
    runner_factory: Callable[[TaskToRun], Any],
    journal_path: str | Path,
    collect_into: str | Path,
    receipt_for: Callable[[TaskToRun, int], Mapping[str, Any] | None] | None = None,
    condition_name: str = "condition_a",
    clock: Callable[[], float] = time.monotonic,
    on_task: Callable[[str, Mapping[str, Any]], None] | None = None,
) -> RunOutcome:
    """Run a fixed manifest, resuming what a previous run left.

    ``receipt_for`` is handed the task and the attempt count and returns that
    task's cost receipt, or ``None`` when this run kept no ledger. ``None`` is
    not free — it becomes a ``not_run`` receipt status and keeps the run's
    ceiling below ``complete``.
    """
    manifest = list(tasks)
    if not manifest:
        raise DriverRefused("a run needs a manifest; an empty one is not one")
    seen: set[str] = set()
    for task in manifest:
        if task.task_id in seen:
            raise DriverRefused(f"{task.task_id!r} appears twice in the manifest")
        seen.add(task.task_id)

    by_id = {task.task_id: task for task in manifest}
    into = Path(collect_into)
    journal = TaskJournal(
        journal_path, run_id=run_id, task_ids=[t.task_id for t in manifest]
    )
    opening_plan = journal.plan()
    to_run = opening_plan.to_run()
    skipped = tuple(
        task.task_id for task in manifest if task.task_id not in set(to_run)
    )

    outcome = RunOutcome(run_id=run_id, skipped_on_resume=skipped)
    consecutive_defects = 0

    for task_id in to_run:
        task = by_id[task_id]
        row: dict[str, Any] | None = None

        while (
            journal.standing(task_id).decision == DECISION_RUN
            and journal.standing(task_id).attempts < MOST_ATTEMPTS_PER_TASK
        ):
            opened = journal.open_task(task_id)
            began = clock()
            result = _attempt_once(
                task,
                runner_factory=runner_factory,
                run_id=run_id,
                condition_name=condition_name,
            )
            collection: Collection | None = None
            if result.get("success") is True:
                collection, result = _collect_or_fail(
                    result,
                    task=task,
                    into=into,
                    attempt_name=opened.workspace_name,
                )
            elapsed_ms = (clock() - began) * 1000.0

            receipt = (
                receipt_for(task, opened.attempt_index)
                if receipt_for is not None
                else None
            )
            outcome_now = describe_run_outcome(result)
            settled = (
                receipt is not None and receipt.get("status") == STATUS_COMPLETE
            )
            journal.close_task(
                outcome=(
                    OUTCOME_FINISHED if outcome_now["succeeded"] else OUTCOME_FAILED
                ),
                error_type=outcome_now["error_type"],
                deliverables=(
                    collection.journal_entries() if collection is not None else ()
                ),
                cost_settled=settled,
            )

            standing = journal.standing(task_id)
            metrics = build_agentic_v2_metrics(
                result,
                standing=standing,
                tool_calls=_tool_calls_of(result),
                model_api_calls=_model_calls_of(result),
                task_wall_time_ms=elapsed_ms,
                receipt=receipt,
            )
            row = build_result_row(
                result,
                task_id=task_id,
                standing=standing,
                sector=task.sector,
                occupation=task.occupation,
                instruction=task.prompt,
                deliverable_files=(
                    collection.submission_paths() if collection is not None else ()
                ),
                latency_ms=elapsed_ms,
                metrics=metrics,
                receipt=receipt,
            )

            if outcome_now["disposition"] == DISPOSITION_RUNNER_DEFECT:
                consecutive_defects += 1
            else:
                # Any other ending breaks the run of defects, including a
                # failure. The rule is about this code producing the record
                # three times over, not about three bad tasks.
                consecutive_defects = 0

            if outcome_now["error_type"] == "compute_cleanup_failed":
                outcome.rows.append(row)
                if on_task is not None:
                    on_task(task_id, row)
                outcome.stopped = StoppedEarly(
                    rule_index=7,
                    rule=STOP_RULES[7],
                    detail=(
                        "the guest was not cleaned after this task, so the next "
                        "task could inherit its state"
                    ),
                    after_task=task_id,
                )
                break

        if outcome.stopped is not None:
            break
        if row is not None:
            outcome.rows.append(row)
            if on_task is not None:
                on_task(task_id, row)

        if consecutive_defects >= CONSECUTIVE_RUNNER_DEFECTS_THAT_STOP_A_RUN:
            outcome.stopped = StoppedEarly(
                rule_index=6,
                rule=STOP_RULES[6],
                detail=(
                    f"{consecutive_defects} tasks running returned the "
                    "runner_defect disposition, so this code and not the work "
                    "under test is producing the record"
                ),
                after_task=task_id,
            )
            break

    outcome.summary = summarise_v2_run(
        outcome.rows,
        manifest_size=len(manifest),
        receipt_ceiling=journal.plan().receipt_ceiling(),
    )
    outcome.summary["skipped_on_resume"] = len(skipped)
    outcome.summary["stopped_early"] = (
        None if outcome.stopped is None else outcome.stopped.as_dict()
    )
    outcome.summary["unaccounted_tasks"] = list(journal.plan().unaccounted_tasks())
    return outcome


def _tool_calls_of(result: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
    """The public trace's calls, which are the ones a report may name.

    The private audit is not read here on purpose: a report is a public
    artefact and should be built from the trace that was redacted for one.
    """
    block = result.get("agentic_v2")
    if not isinstance(block, Mapping):
        return ()
    trace = block.get("public_trace")
    if not isinstance(trace, Mapping):
        return ()
    events = trace.get("events")
    if not isinstance(events, Sequence):
        return ()
    return [
        event
        for event in events
        if isinstance(event, Mapping) and event.get("tool_name")
    ]


def _model_calls_of(result: Mapping[str, Any]) -> int:
    block = result.get("agentic_v2")
    if not isinstance(block, Mapping):
        return 0
    count = block.get("model_api_calls")
    if type(count) is int and count >= 0:
        return count
    return 0
