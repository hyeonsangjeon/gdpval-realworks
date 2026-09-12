"""Turning what a V2 task actually did into the row the report already reads.

Step 6 renders whatever step 3 wrote. It reads a per-task row with a ``status``,
a deliverable count, a cost receipt and an ``observability.agentic_metrics``
block, and it has read that shape since the V1 agentic runner. A V2 run that
produced results and no row would be a run whose report says nothing happened.

So this is the adapter, and it exists as its own module for the same reason
:mod:`core.agentic_v2_cost_binding` does: the report is shared with other work
and binding a backend to it should not mean editing it.

Three things it refuses to smooth over.

**A cost nobody priced is not ``$0``.** The report's ``conservative_cost_usd``
is summed as a plain float, so writing a zero there for an unpriced run would
put a wrong number in a headline. The receipt is where the truth lives —
``problem_solving_cost`` carries ``partial`` or ``unavailable`` with its reasons
— so ``conservative_cost_usd`` is written only when the receipt is
:data:`~core.cost_receipts.STATUS_COMPLETE` and is otherwise absent. An absent
key contributes nothing and claims nothing; a zero claims something false.

**The report's per-tool breakdown is V1's and will read zero for V2.** Its tool
names are ``inspect_workspace``, ``run_python`` and the rest. V2's are
``exec_run``, ``environment_resolve`` and the rest, and the two sets do not
overlap at all — :data:`TOOL_NAMES_THE_REPORT_KNOWS` is checked against the
contract's at import, so this cannot quietly become half-true. The honest
handling is to write the V2 counts under their own names, where a reader can
find them, and to state here that the report's ``tool_calls_by_name`` will show
zeros until the report itself learns V2's vocabulary. That is a change to a
shared file and it is not made from here.

**An attempt that vanished is part of the task's story.** The journal knows a
task was opened and never closed; nothing in the report's vocabulary does. The
count is carried through so that a task which cost money twice and succeeded
once is not reported as a task that cost money once.

Nothing here runs a model, prices a call, or decides whether a task succeeded.
It is handed facts that were established elsewhere and arranges them.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from core.agentic_v2_contract import TOOL_NAMES
from core.agentic_v2_cost_binding import describe_run_outcome
from core.agentic_v2_task_journal import (
    DECISION_SKIP_FINISHED,
    TaskStanding,
)
from core.cost_receipts import (
    STATUS_COMPLETE,
    STATUS_NOT_RUN,
    STATUS_PARTIAL,
    STATUS_UNAVAILABLE,
)


AGENTIC_V2_METRICS_SCHEMA_VERSION = "agentic-v2-report-row-v1"

STATUS_SUCCESS = "success"
STATUS_ERROR = "error"

#: The tool names ``step6_report._compute_agentic_metrics`` buckets calls under.
#:
#: V1's vocabulary, and for a long time the whole of what the report could
#: name. Kept as its own constant because the V1 names have to stay in the
#: breakdown and in that order -- a V1 run's report must not change shape
#: because V2 arrived.
TOOL_NAMES_THE_REPORT_KNOWS = (
    "inspect_workspace",
    "inspect_environment",
    "run_python",
    "run_ffmpeg",
    "inspect_artifacts",
    "finalize",
)

#: What V2 calls its tools, in the order the contract lists them.
TOOL_NAMES_V2_USES = TOOL_NAMES

#: The one name both vocabularies share.
#:
#: ``finalize`` means the same thing in both, so a count under it is a sum
#: across two different runners and cannot be attributed to either. Naming the
#: overlap is what makes that checkable instead of surprising.
SHARED_TOOL_NAMES = tuple(
    name for name in TOOL_NAMES_V2_USES if name in TOOL_NAMES_THE_REPORT_KNOWS
)

if set(SHARED_TOOL_NAMES) != {"finalize"}:  # pragma: no cover - import guard
    raise RuntimeError(
        "the report's tool vocabulary and V2's now overlap differently than "
        f"recorded: {sorted(SHARED_TOOL_NAMES)}"
    )

#: Every bucket the report's tool breakdown offers, both vocabularies.
#:
#: The report used to offer only the six above. A V2 row carries counts under
#: all eight of V2's names, seven of which were not in that list, so seven of
#: them were dropped on the way into the summary and the breakdown showed a
#: lone non-zero ``finalize`` beside five zeros -- which reads as a model that
#: used one tool, for a run in which it used several.
#:
#: ``browser_run`` is why this is worth the widening rather than a footnote.
#: Three of the five tasks in the first paid stage ended on it, and it was the
#: single most informative thing that run produced. It was also one of the
#: seven names with nowhere to land.
#:
#: V1's names come first and keep their order, so an existing report's
#: breakdown gains keys and does not reorder or lose any.
TOOL_NAMES_THE_REPORT_BUCKETS = TOOL_NAMES_THE_REPORT_KNOWS + tuple(
    name for name in TOOL_NAMES_V2_USES if name not in TOOL_NAMES_THE_REPORT_KNOWS
)


class ReportRowRefused(RuntimeError):
    """The row was not built, because building it would have stated something
    that is not known."""


def _tool_counts(calls: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts = {name: 0 for name in TOOL_NAMES_V2_USES}
    for call in calls:
        name = call.get("tool_name") if isinstance(call, Mapping) else None
        if name not in counts:
            raise ReportRowRefused(
                f"a recorded call names a tool the contract does not have: "
                f"{name!r}"
            )
        counts[name] += 1
    return counts


def _receipt_status(receipt: Mapping[str, Any] | None) -> str:
    if receipt is None:
        return STATUS_NOT_RUN
    status = receipt.get("status")
    if status not in (
        STATUS_COMPLETE,
        STATUS_PARTIAL,
        STATUS_UNAVAILABLE,
        STATUS_NOT_RUN,
    ):
        raise ReportRowRefused(f"{status!r} is not a receipt status")
    return str(status)


def build_agentic_v2_metrics(
    run_record: Mapping[str, Any],
    *,
    standing: TaskStanding,
    tool_calls: Sequence[Mapping[str, Any]] = (),
    model_api_calls: int = 0,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    task_wall_time_ms: float | None = None,
    receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """The ``observability.agentic_metrics`` block for one V2 task.

    ``task_wall_time_ms`` is what makes the report count this task as measured
    at all, so a run that did not time itself is refused rather than reported
    as a task nobody ran.
    """
    if task_wall_time_ms is None:
        raise ReportRowRefused(
            "a task with no measured wall time is invisible to the report's "
            "agentic metrics; record the time or do not claim the task ran"
        )
    outcome = describe_run_outcome(run_record)
    counts = _tool_counts(tool_calls)
    status = _receipt_status(receipt)
    cost_is_known = status == STATUS_COMPLETE and standing.cost_is_fully_accounted

    metrics: dict[str, Any] = {
        "schema_version": AGENTIC_V2_METRICS_SCHEMA_VERSION,
        "task_wall_time_ms": float(task_wall_time_ms),
        "model_api_calls": int(model_api_calls),
        "tool_calls": sum(counts.values()),
        "tool_errors": 0 if outcome["succeeded"] else 1,
        "tool_calls_by_name": counts,
        "terminal_error_category": outcome["error_type"] or "",
        "usage_complete": cost_is_known,
        # V2's own fields. The report does not read these yet; they are here so
        # that when it does, nothing has to be reconstructed from a log.
        "agentic_v2_disposition": outcome["disposition"],
        "agentic_v2_attributable_to": outcome["attributable_to"],
        "agentic_v2_attempts": standing.attempts,
        "agentic_v2_abandoned_attempts": standing.abandoned_attempts,
        "agentic_v2_cost_receipt_status": status,
    }
    if input_tokens is not None:
        metrics["input_tokens"] = int(input_tokens)
    if output_tokens is not None:
        metrics["output_tokens"] = int(output_tokens)
    if cost_is_known:
        # ``estimated_cost_usd`` rather than ``known_cost_usd``: the receipt
        # documents the first as the only field that claims to be a total, and
        # it is ``None`` on anything but a complete receipt, so reading it makes
        # the gate above belt-and-braces instead of the sole guard.
        amount = receipt.get("estimated_cost_usd") if receipt else None
        if isinstance(amount, (int, float)) and not isinstance(amount, bool):
            metrics["conservative_cost_usd"] = float(amount)
    # No else. A run whose cost is not fully known writes no amount at all,
    # because the report sums this field as a plain float and a zero there
    # would be read as "this task was free".
    return metrics


def build_result_row(
    run_record: Mapping[str, Any],
    *,
    task_id: str,
    standing: TaskStanding,
    sector: str = "",
    occupation: str = "",
    instruction: str = "",
    deliverable_files: Sequence[str] = (),
    latency_ms: float | None = None,
    metrics: Mapping[str, Any],
    receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """One V2 task as the row step 3 writes and step 6 renders.

    The deliverable paths are the ones
    :meth:`core.agentic_v2_deliverable_collection.Collection.submission_paths`
    returned — that is, paths that were written and read back — rather than the
    ones the model named. A row whose file list came from the model's own
    ``finalize`` would claim files that a failed collection never put on disk.
    """
    outcome = describe_run_outcome(run_record)
    files = list(deliverable_files)
    if outcome["succeeded"] and not files:
        raise ReportRowRefused(
            f"task {task_id!r} succeeded with no collected deliverables; a "
            "successful row with an empty file list reads as a model that "
            "produced nothing"
        )
    if not outcome["succeeded"] and files:
        raise ReportRowRefused(
            f"task {task_id!r} failed and yet carries {len(files)} deliverable "
            "paths; a failed task's partial files are not its answer"
        )

    row: dict[str, Any] = {
        "task_id": str(task_id),
        "sector": str(sector),
        "occupation": str(occupation),
        "status": STATUS_SUCCESS if outcome["succeeded"] else STATUS_ERROR,
        "retried": standing.attempts > 1,
        "instruction": str(instruction),
        "deliverable_text": str(run_record.get("deliverable_text") or ""),
        "deliverable_files": files,
        "deliverable_files_count": len(files),
        "latency_ms": latency_ms,
        "observability": {"agentic_metrics": dict(metrics)},
    }
    if not outcome["succeeded"]:
        row["error"] = outcome["error_type"]
    if receipt is not None:
        # Absent stays absent: a task with no receipt gains no key, so the
        # dashboard can tell "not recorded" from "recorded as nothing".
        row["problem_solving_cost"] = dict(receipt)
    return row


def summarise_v2_run(
    rows: Sequence[Mapping[str, Any]],
    *,
    manifest_size: int,
    receipt_ceiling: str,
) -> dict[str, Any]:
    """What the whole run did, with its three milestones kept apart.

    Environment readiness, execution and grading are separate claims and the
    summary says so in separate fields. A run that executed 220 tasks and graded
    none must not be readable as a run that graded 220, so ``graded`` is
    ``None`` with a stated reason rather than ``0`` — zero graded and grading
    not attempted look identical as a number and are not the same fact.

    ``receipt_ceiling`` is the journal's ceiling: what the run may claim given
    what was abandoned. It is a ceiling and not a verdict, and it was being
    read as the verdict. The journal knows about attempts that vanished; it
    knows nothing about a call the provider billed and did not count, because
    that is a fact about a ledger row. So a run could hand every task a
    ``partial`` receipt and still publish ``cost_is_fully_accounted: true`` —
    which is what the first paid stage did, for a bill that was 20% short.

    The rows are therefore asked as well, and the lower of the two answers
    wins. A run is fully accounted only where the journal lost nothing *and*
    every receipt written under it reads ``complete``.
    """
    dispositions: dict[str, int] = {}
    abandoned = 0
    succeeded = 0
    unsettled: dict[str, int] = {}
    for row in rows:
        metrics = (row.get("observability") or {}).get("agentic_metrics") or {}
        disposition = metrics.get("agentic_v2_disposition")
        if disposition:
            dispositions[disposition] = dispositions.get(disposition, 0) + 1
        abandoned += int(metrics.get("agentic_v2_abandoned_attempts") or 0)
        if row.get("status") == STATUS_SUCCESS:
            succeeded += 1
        # Read off the receipt the row carries rather than off the metrics
        # copy, because the receipt is the object the money is on and the
        # metrics field is derived from it. A row with no receipt says nothing
        # here: absent is not a complaint, and `receipt_ceiling` above already
        # covers a task the journal could not close.
        receipt = row.get("problem_solving_cost")
        if isinstance(receipt, Mapping):
            status = str(receipt.get("status") or "")
            if status and status != STATUS_COMPLETE:
                unsettled[status] = unsettled.get(status, 0) + 1

    ceiling = str(receipt_ceiling)
    every_receipt_settled = not unsettled
    accounted = ceiling == STATUS_COMPLETE and every_receipt_settled

    return {
        "schema_version": AGENTIC_V2_METRICS_SCHEMA_VERSION,
        "manifest_size": int(manifest_size),
        "rows_written": len(rows),
        "executed": len(rows),
        "succeeded": succeeded,
        "failed": len(rows) - succeeded,
        "not_reached": max(0, int(manifest_size) - len(rows)),
        "abandoned_attempts": abandoned,
        "dispositions": dict(sorted(dispositions.items())),
        "receipt_ceiling": ceiling,
        # How many tasks the run could not settle, and under which status.
        # Empty where every receipt read `complete`; a reader chasing a short
        # bill starts here rather than by opening 220 receipts.
        "unsettled_receipts": dict(sorted(unsettled.items())),
        "cost_is_fully_accounted": accounted,
        "graded": None,
        "graded_reason": "grading is a separate run and has not been made",
    }


def finished_tasks(standings: Sequence[TaskStanding]) -> tuple[str, ...]:
    """The task ids the journal considers done, in manifest order."""
    return tuple(
        standing.task_id
        for standing in standings
        if standing.decision == DECISION_SKIP_FINISHED
    )
