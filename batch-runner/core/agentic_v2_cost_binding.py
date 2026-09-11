"""What a V2 run costs, and what it means to have failed, in the ledger's terms.

Two questions stage F has to answer per task and cannot answer from the run
record alone.

**What did it cost.** `core.cost_receipts` already holds the machinery -- a
reserve/settle ledger, a problem-solving bucket kept apart from grading, and a
rule that an unpriced thing is recorded as missing rather than as zero. What it
does not have is a V2 caller. This module is that caller, and it is deliberately
a separate module: the ledger is shared with other work, and binding a backend
to it should not mean editing it.

**Why did it fail, and whose fault is that.** The ledger records a `retry_kind`
per call and `execution_environment_readiness` reads those as three reasons --
infrastructure, model self-review, tool-loop internal recovery. A V2 run ends
with one of twenty-seven error types, and mapping them onto those three is where
the honesty of the whole 220-task report is decided. Get it wrong in one
direction and a bug in this runner reads as a flaky environment; get it wrong in
the other and a model that never called `finalize` reads as a broken sandbox.

So the map below is total and explicit, and two of its answers are neither the
model's fault nor the environment's:

- **runner defect** -- seven error types can only be produced by this code
  misbehaving. Filing them under "infrastructure" would inflate the infra retry
  count with our own bugs and make the sandbox look unreliable when it was fine.
- **ambiguous** -- `task_wall_time_exhausted` genuinely cannot be attributed
  from the error alone. A model looping and a host crawling produce the same
  symbol. It is recorded as undecidable rather than assigned to whichever side
  is convenient.

Nothing here contacts a provider, boots a guest, or prices anything it was not
given a price for.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping, Sequence

from core.agentic_v2_contract import ERROR_TYPES
from core.cost_receipts import (
    BUCKET_GRADING,
    BUCKET_PROBLEM_SOLVING,
    CallUsage,
    CostReceiptLedger,
    RETRY_INFRASTRUCTURE,
    RETRY_INTERNAL_RECOVERY,
    RETRY_NONE,
    RETRY_SEMANTIC,
    STAGE_GENERATION,
    STAGE_BUCKET,
)

#: The runtime kind a V2 guest is recorded under. It is not in the price table
#: today, and that is the point of naming it: the ledger will record the seconds
#: with no amount and a ``runtime_cost_unpriced`` reason, which holds the task's
#: receipt at ``partial``. A host whose bill this repository cannot read must not
#: be allowed to look free.
RUNTIME_KIND_MICROVM_GUEST = "agentic_v2_microvm_guest"

#: Dispositions that are not one of the ledger's retry kinds. They exist because
#: the ledger's three answer "what kind of retry is this", and some endings are
#: not a retry at all.
DISPOSITION_TERMINAL_BUDGET = "terminal_budget_exhausted"
DISPOSITION_TERMINAL_STOP = "terminal_deliberate_stop"
DISPOSITION_TERMINAL_CAPABILITY = "terminal_capability_absent"
DISPOSITION_RUNNER_DEFECT = "runner_defect"
DISPOSITION_AMBIGUOUS = "ambiguous_not_attributable"

TERMINAL_DISPOSITIONS = (
    DISPOSITION_TERMINAL_BUDGET,
    DISPOSITION_TERMINAL_STOP,
    DISPOSITION_TERMINAL_CAPABILITY,
    DISPOSITION_RUNNER_DEFECT,
    DISPOSITION_AMBIGUOUS,
)

DISPOSITIONS = (
    RETRY_INFRASTRUCTURE,
    RETRY_SEMANTIC,
    RETRY_INTERNAL_RECOVERY,
    *TERMINAL_DISPOSITIONS,
)

#: Every V2 error type, and what a next attempt would be if there were one.
#:
#: Total by construction -- the check below this table fails at import if
#: ``ERROR_TYPES`` grows a member that nobody classified. A new failure mode
#: should stop the build, not quietly default to somebody's fault.
ERROR_DISPOSITION: dict[str, str] = {
    # The environment did not come up, fell over, or could not be cleaned up.
    # A retry on a healthy host is a reasonable thing to do.
    "compute_start_failed": RETRY_INFRASTRUCTURE,
    "compute_backend_error": RETRY_INFRASTRUCTURE,
    "compute_cleanup_failed": RETRY_INFRASTRUCTURE,
    "fixture_backend_error": RETRY_INFRASTRUCTURE,
    "substrate_manifest_missing": RETRY_INFRASTRUCTURE,

    # The model asked for something the contract does not allow, or asked
    # wrongly. Feeding the error back and letting it try again is the point of
    # a self-review retry.
    "invalid_arguments": RETRY_SEMANTIC,
    "unknown_tool": RETRY_SEMANTIC,
    "tool_not_allowed_in_state": RETRY_SEMANTIC,
    "invalid_call_id": RETRY_SEMANTIC,
    "path_not_directory": RETRY_SEMANTIC,
    "artifact_not_openable": RETRY_SEMANTIC,
    "package_not_in_snapshot": RETRY_SEMANTIC,
    "unapproved_lock": RETRY_SEMANTIC,
    "tool_result_too_large": RETRY_SEMANTIC,
    "finalize_not_called": RETRY_SEMANTIC,

    # The loop handled it without the model or the host being at fault. A
    # replayed call id is the ordinary case: the tool loop resolves it.
    "call_id_conflict": RETRY_INTERNAL_RECOVERY,

    # Endings that are not retries.
    "tool_budget_exhausted": DISPOSITION_TERMINAL_BUDGET,
    "cancelled": DISPOSITION_TERMINAL_STOP,
    "capability_unavailable": DISPOSITION_TERMINAL_CAPABILITY,

    # Only this code can produce these. Retrying changes nothing until the code
    # changes, and filing them under infrastructure would hide our own bugs
    # inside the sandbox's reliability number.
    "runner_internal_error": DISPOSITION_RUNNER_DEFECT,
    "invalid_backend_result": DISPOSITION_RUNNER_DEFECT,
    "invalid_backend_state": DISPOSITION_RUNNER_DEFECT,
    "invalid_result_envelope": DISPOSITION_RUNNER_DEFECT,
    "invalid_lifecycle_transition": DISPOSITION_RUNNER_DEFECT,
    "finalize_result_mismatch": DISPOSITION_RUNNER_DEFECT,
    "finalize_result_missing": DISPOSITION_RUNNER_DEFECT,

    # A wall clock running out looks identical whether the model looped or the
    # host crawled. Deciding it from this symbol alone would be guessing, and a
    # guess recorded as a measurement is worse than an admitted gap.
    "task_wall_time_exhausted": DISPOSITION_AMBIGUOUS,
}

_UNCLASSIFIED = set(ERROR_TYPES) - set(ERROR_DISPOSITION)
_INVENTED = set(ERROR_DISPOSITION) - set(ERROR_TYPES)
if _UNCLASSIFIED or _INVENTED:  # pragma: no cover - import-time guard
    raise RuntimeError(
        "agentic v2 error dispositions are out of step with the contract: "
        f"unclassified={sorted(_UNCLASSIFIED)} invented={sorted(_INVENTED)}"
    )

#: Which dispositions describe a run that is worth attempting again at all.
RETRYABLE_DISPOSITIONS = (
    RETRY_INFRASTRUCTURE,
    RETRY_SEMANTIC,
    RETRY_INTERNAL_RECOVERY,
)


def disposition_for_error(error_type: Any) -> str:
    """What kind of thing the given V2 error was.

    Raises on anything unknown. There is no default, because a default is how a
    new failure mode ends up silently attributed to whichever party the default
    happened to name.
    """
    try:
        return ERROR_DISPOSITION[error_type]
    except (KeyError, TypeError):
        raise ValueError(
            f"agentic v2 error type has no recorded disposition: {error_type!r}"
        ) from None


def retry_kind_for_error(error_type: Any) -> str | None:
    """The ledger ``retry_kind`` a *next* attempt after this error would carry.

    ``None`` where there should be no next attempt. Callers must not substitute
    a retry kind of their own choosing for the ``None``; that is the whole
    distinction this module exists to keep.
    """
    disposition = disposition_for_error(error_type)
    return disposition if disposition in RETRYABLE_DISPOSITIONS else None


@dataclass(frozen=True)
class ModelTurn:
    """One model call inside a V2 run, as the provider reported it."""

    call_id: str
    usage: CallUsage
    provider: str
    requested_model: str
    deployment: str | None = None
    api_version: str | None = None
    resolved_model: str | None = None
    request_sha256: str | None = None
    #: ``RETRY_NONE`` for a first attempt. For a later one, pass what
    #: :func:`retry_kind_for_error` returned for the error that preceded it.
    retry_kind: str = RETRY_NONE
    note: str | None = None


@dataclass(frozen=True)
class GuestRuntime:
    """How long a V2 guest was up for one task, and what that is known to cost."""

    entry_id: str
    seconds: float | None
    #: Only ever a figure somebody measured. Left ``None`` when the host's bill
    #: is not readable from here, which is the present state: the ledger then
    #: records the seconds with no amount and says why.
    usd: Decimal | None = None
    runtime_kind: str = RUNTIME_KIND_MICROVM_GUEST


def bind_run_to_ledger(
    ledger: CostReceiptLedger,
    *,
    task_id: str,
    model_turns: Sequence[ModelTurn] = (),
    guest_runtime: GuestRuntime | None = None,
    stage: str = STAGE_GENERATION,
) -> dict[str, Any]:
    """Write one V2 task's calls and guest time into the shared ledger.

    Returns what was written, so a caller can record it without re-reading the
    database.

    The stage decides the bucket, and this refuses any stage that buckets as
    grading. Problem-solving cost and grading cost are kept apart on purpose,
    and a V2 task run is not grading -- a caller that passes a grading stage has
    made a mistake that would otherwise show up as a corrupted total months
    later.
    """
    bucket = STAGE_BUCKET.get(stage)
    if bucket != BUCKET_PROBLEM_SOLVING:
        raise ValueError(
            f"agentic v2 runs are problem-solving cost; stage {stage!r} buckets "
            f"as {bucket!r}"
        )

    settled: list[str] = []
    for turn in model_turns:
        ledger.reserve(
            call_id=turn.call_id,
            task_id=task_id,
            stage=stage,
            retry_kind=turn.retry_kind,
            provider=turn.provider,
            requested_model=turn.requested_model,
            deployment=turn.deployment,
            api_version=turn.api_version,
            request_sha256=turn.request_sha256,
            note=turn.note,
        )
        ledger.settle(
            turn.call_id,
            usage=turn.usage,
            resolved_model=turn.resolved_model,
        )
        settled.append(turn.call_id)

    runtime_entry: str | None = None
    if guest_runtime is not None:
        ledger.record_runtime_cost(
            entry_id=guest_runtime.entry_id,
            task_id=task_id,
            bucket=BUCKET_PROBLEM_SOLVING,
            runtime_kind=guest_runtime.runtime_kind,
            seconds=guest_runtime.seconds,
            usd=guest_runtime.usd,
        )
        runtime_entry = guest_runtime.entry_id

    return {
        "task_id": task_id,
        "bucket": bucket,
        "settled_call_ids": settled,
        "runtime_entry_id": runtime_entry,
        "grading_bucket_untouched": BUCKET_GRADING,
    }


def describe_run_outcome(run_record: Mapping[str, Any]) -> dict[str, Any]:
    """Read a V2 result envelope as a cost-and-blame statement.

    A successful run has no error and no disposition; saying so explicitly is
    better than an absent key that a reader has to interpret.
    """
    if run_record.get("success") is True:
        return {
            "succeeded": True,
            "error_type": None,
            "disposition": None,
            "retry_kind_for_next_attempt": None,
            "attributable_to": None,
        }
    error_type = run_record.get("error")
    disposition = disposition_for_error(error_type)
    return {
        "succeeded": False,
        "error_type": error_type,
        "disposition": disposition,
        "retry_kind_for_next_attempt": retry_kind_for_error(error_type),
        "attributable_to": _ATTRIBUTION[disposition],
    }


#: Who a disposition points at, in the words stage F has to report in.
_ATTRIBUTION: dict[str, str] = {
    RETRY_INFRASTRUCTURE: "environment",
    RETRY_SEMANTIC: "model",
    RETRY_INTERNAL_RECOVERY: "neither -- the tool loop absorbed it",
    DISPOSITION_TERMINAL_BUDGET: "neither -- a bound the run was given",
    DISPOSITION_TERMINAL_STOP: "neither -- stopped on purpose",
    DISPOSITION_TERMINAL_CAPABILITY: (
        "environment, but as a declared absence rather than a fault"
    ),
    DISPOSITION_RUNNER_DEFECT: "this runner",
    DISPOSITION_AMBIGUOUS: "undecidable from the error alone",
}
