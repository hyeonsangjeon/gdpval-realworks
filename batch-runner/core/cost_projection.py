"""Read side of the per-task cost receipt contract (``cost-receipt-v1``).

Instrumentation writes receipts while a task runs and while it is graded.
This module never prices anything: it normalises what reaches Step 3, refuses
to publish a receipt it cannot vouch for, and aggregates the run-level
summaries the report and the dashboard show.

Two properties matter more than the arithmetic:

* A run that carries no receipts projects to ``None``. Experiments that
  predate the instrumentation keep rendering as "no record" — never as ``$0``.
* ``unavailable`` (nothing was recorded), ``not_run`` (the step never ran),
  ``partial`` (some components priced, some not) and a real ``$0`` under
  ``complete`` are four different findings, so they stay four different
  states all the way to the screen.

Every amount is a usage-based estimate. ``ESTIMATE_BASIS`` travels with each
summary so no consumer can present one of these figures as a cloud invoice.
"""

from __future__ import annotations

import hashlib
import math
import re
import shutil
from pathlib import Path

COST_RECEIPT_SCHEMA_VERSION = "cost-receipt-v1"
COST_CURRENCY = "USD"

#: The one name the audit sidecar is published under.
#:
#: The producer names its export after the condition it recorded, which is
#: right for a workspace that may hold several. A published repository holds
#: one, and both its readers and the publication allowlist need a name that
#: can be stated before the run exists. The rename happens once, on the way
#: into the upload directory, and the digest is checked across it.
COST_LEDGER_PUBLICATION_PATH = "cost_ledger.jsonl"

#: Amounts are usage estimates, not billed figures. Carried in every summary
#: so the disclaimer cannot be lost between the report and the dashboard.
ESTIMATE_BASIS = "usage_estimate_not_azure_invoice"

#: ``complete`` — a figure we stand behind, including a genuine ``$0``.
#: ``partial`` — priced in part; ``known_cost_usd`` is a lower bound.
#: ``unavailable`` — the step ran and recorded nothing.
#: ``not_run`` — the step never ran, so there is nothing to record.
COST_STATUSES = ("complete", "partial", "unavailable", "not_run")

#: Statuses that contribute a number to the run-level totals.
_MEASURED_STATUSES = ("complete", "partial")

COST_FIELDS = ("problem_solving_cost", "grading_cost")

#: The closed vocabulary the producer publishes for ``components[].name``
#: (``core/cost_receipts.py``: ``COMPONENT_NAMES``). Recorded here for readers,
#: not enforced here: the grade schema is the gate, and a second copy that
#: disagreed would reject a receipt the producer considers valid.
#:
#: There is deliberately no ``runtime`` entry. Runtime fees are not model calls
#: and arrive as ``runtime_cost_usd``; a component line carrying them would be
#: counted twice by any reader that sums the lines and then adds the runtime
#: total.
COST_COMPONENT_NAMES = (
    "preprocessing",
    "generation",
    "self_qa",
    "grading",
    "perception",
    "retry",
)

#: What a component line carries when it was not a first attempt.
_RETRY_NONE = "none"

# Slugs, not prose. Reason codes and component names are published, and a free
# text field on a published payload is a prompt-leak waiting to happen.
_SLUG = re.compile(r"[a-z][a-z0-9_]{0,47}")
_REASON_CODE = re.compile(r"[a-z][a-z0-9_.:-]{0,63}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_LEDGER_PATH = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}(/[A-Za-z0-9][A-Za-z0-9._-]{0,127})*")

_MAX_COMPONENTS = 32
_MAX_USAGE_KEYS = 32
_MAX_MISSING_REASONS = 32
_LEDGER_CHUNK_BYTES = 1024 * 1024

# Micro-dollars. Fine enough for a single cheap call, coarse enough that
# float noise never reaches the screen.
_MONEY_DIGITS = 6
_MAX_COST_USD = 1_000_000.0

#: How many times a run called a model. Thousands, by construction — tasks
#: times stages times the retries a run is allowed. The largest published to
#: date is 2,346, which is 0.02% of this.
_MAX_MODEL_CALLS = 10_000_000

#: How many tokens those calls carried, which is neither the same quantity nor
#: the same scale: the 2,346 calls above carried 21,688,749 input tokens
#: between them, and an ordinary marking call is nine thousand tokens of rubric
#: and deliverable.
#:
#: Bounded where a count stops meaning one thing to every reader of this
#: contract, rather than at a size someone guessed a run would not reach. The
#: guessed kind of bound is what this constant used to be, and a real shard
#: crossed it. Above ``2**53 - 1`` a JSON integer no longer survives
#: ``JSON.parse``: ``scripts/cost-receipt.mjs`` and the dashboard would read a
#: different number than the file holds, and ``Number.isInteger`` would still
#: say yes to it. So this is a bound on being read back correctly, not on being
#: plausible — the module cannot know how large an honest run is, and the last
#: time it assumed, it was wrong.
_MAX_TOKENS = 2**53 - 1


def _fail(field: str, detail: str) -> None:
    raise ValueError(f"{field} {detail}")


def _cost_amount(value, field: str):
    """Return a non-negative finite amount, or ``None`` when absent."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(field, "must be a number")
    amount = float(value)
    if not math.isfinite(amount):
        _fail(field, "must be finite")
    if amount < 0 or amount > _MAX_COST_USD:
        _fail(field, "is out of range")
    return round(amount, _MONEY_DIGITS)


def _cost_count(value, field: str, limit: int):
    """Return a non-negative integer within ``limit``, or ``None`` when absent.

    The bound arrives as an argument rather than being fixed here, because the
    two kinds of field that reach this function are not one quantity. A run's
    calls and the tokens those calls carried differ by four orders of magnitude
    on real runs, so a single bound covering both is really the smaller one
    wearing a general name — which is how an honest 21,688,749-token shard came
    to be refused as out of range while the 2,337 calls behind it used two
    hundredths of a percent of the same allowance.

    Naming the bound at each call site is the part that keeps that from coming
    back: a reader can see which quantity is being bounded without having to
    know that ``usage`` and ``model_calls`` share a helper.
    """
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        _fail(field, "must be an integer")
    if value < 0 or value > limit:
        _fail(field, "is out of range")
    return value


def _cost_usage(value, field: str) -> dict:
    if value is None:
        return {}
    if not isinstance(value, dict):
        _fail(field, "must be an object")
    if len(value) > _MAX_USAGE_KEYS:
        _fail(field, "carries too many keys")
    usage = {}
    for key, raw in value.items():
        if not isinstance(key, str) or _SLUG.fullmatch(key) is None:
            _fail(field, "carries an invalid key")
        usage[key] = _cost_count(raw, f"{field}.{key}", _MAX_TOKENS)
    return dict(sorted(usage.items()))


def _missing_reasons(value, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        _fail(field, "must be a list")
    if len(value) > _MAX_MISSING_REASONS:
        _fail(field, "carries too many entries")
    reasons = []
    for raw in value:
        if not isinstance(raw, str) or _REASON_CODE.fullmatch(raw) is None:
            _fail(field, "must contain reason codes only")
        reasons.append(raw)
    return sorted(set(reasons))


def _price_table_sha256(value, field: str):
    if value is None:
        return None
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        _fail(field, "must be a sha256 digest")
    return value


def _cost_status(value, field: str) -> str:
    if value not in COST_STATUSES:
        _fail(field, "must be one of " + ", ".join(COST_STATUSES))
    return value


def _measured_amount(amount, status: str, field: str):
    """Drop the zero a non-``complete`` line carries as a placeholder.

    The producer fills every money field on every status, so an ``unavailable``
    receipt — one that recorded nothing at all — still reaches here as
    ``known_cost_usd: 0.0``. Passed through, that zero renders as ``$0.0000``,
    which is the exact reading the four statuses exist to prevent: "no record"
    turning into "it was free".

    So a zero is a measurement under ``complete`` and nowhere else. That is not
    a convention chosen here; it is the one real ``$0`` the contract admits — a
    rule-based path that never called a model. Under ``partial`` a zero means
    nothing was confirmed yet, which is absence, not a floor of zero.

    A *non-zero* amount under ``unavailable`` or ``not_run`` is neither: the
    receipt claims to know an amount and to have recorded nothing, and a
    receipt that contradicts itself is not one this module will publish.
    """
    if status == "complete" or amount is None:
        return amount
    if amount == 0:
        return None
    if status == "partial":
        return amount
    _fail(field, f"is {status} but carries an amount")


def _project_component(value, field: str) -> dict:
    """Normalise one receipt line.

    The producer's line is ``(stage, retry_kind)`` — a retry belongs to the
    stage that retried — with ``name`` derived from the pair for readers that
    show one label per row. All three travel: the derived name is what a reader
    displays, and the pair is what identifies the row, because two stages that
    each had to retry both derive the name ``retry`` and are not the same line.
    """
    if not isinstance(value, dict):
        _fail(field, "must be an object")
    name = value.get("name")
    if not isinstance(name, str) or _SLUG.fullmatch(name) is None:
        _fail(field, "requires a slug name")
    # Defaulted the way the producer defaults them when reading a receipt back,
    # so a line written by an older build still identifies itself.
    stage = value.get("stage") or name
    if not isinstance(stage, str) or _SLUG.fullmatch(stage) is None:
        _fail(field, "requires a slug stage")
    retry_kind = value.get("retry_kind") or _RETRY_NONE
    if not isinstance(retry_kind, str) or _SLUG.fullmatch(retry_kind) is None:
        _fail(field, "requires a slug retry_kind")
    status = _cost_status(value.get("status"), f"{field}.status")
    known = _measured_amount(
        _cost_amount(value.get("known_cost_usd"), f"{field}.known_cost_usd"),
        status,
        f"{field}.known_cost_usd",
    )
    return {
        "name": name,
        "stage": stage,
        "retry_kind": retry_kind,
        "status": status,
        "known_cost_usd": known,
        "model_calls": _cost_count(
            value.get("model_calls"), f"{field}.model_calls", _MAX_MODEL_CALLS
        ),
        "usage": _cost_usage(value.get("usage"), f"{field}.usage"),
        "missing_reasons": _missing_reasons(
            value.get("missing_reasons"), f"{field}.missing_reasons"
        ),
    }


def project_cost_receipt(value, field: str = "cost receipt"):
    """Normalise one ``cost-receipt-v1`` receipt.

    ``None`` in, ``None`` out — an absent receipt is a legitimate state and
    stays absent rather than becoming a zero. Anything present but malformed
    raises: a receipt the consumer cannot read must not be published as if it
    were sound.
    """
    if value is None:
        return None
    if not isinstance(value, dict):
        _fail(field, "must be an object")
    if value.get("schema_version") != COST_RECEIPT_SCHEMA_VERSION:
        _fail(field, f"must declare schema_version {COST_RECEIPT_SCHEMA_VERSION}")
    if value.get("currency") != COST_CURRENCY:
        _fail(field, f"must be denominated in {COST_CURRENCY}")

    status = _cost_status(value.get("status"), f"{field}.status")
    estimated = _cost_amount(value.get("estimated_cost_usd"), f"{field}.estimated_cost_usd")
    known = _measured_amount(
        _cost_amount(value.get("known_cost_usd"), f"{field}.known_cost_usd"),
        status,
        f"{field}.known_cost_usd",
    )
    model_cost = _measured_amount(
        _cost_amount(value.get("model_cost_usd"), f"{field}.model_cost_usd"),
        status,
        f"{field}.model_cost_usd",
    )
    runtime_cost = _measured_amount(
        _cost_amount(value.get("runtime_cost_usd"), f"{field}.runtime_cost_usd"),
        status,
        f"{field}.runtime_cost_usd",
    )
    reasons = _missing_reasons(value.get("missing_reasons"), f"{field}.missing_reasons")

    raw_components = value.get("components")
    if raw_components is None:
        raw_components = []
    if not isinstance(raw_components, list):
        _fail(field, "components must be a list")
    if len(raw_components) > _MAX_COMPONENTS:
        _fail(field, "carries too many components")
    components = [
        _project_component(item, f"{field}.components[{index}]")
        for index, item in enumerate(raw_components)
    ]
    # A line is identified by the pair, not by its label. Generation that had to
    # be redone and Self-QA that had to be redone both display as 재시도, and
    # rejecting the second as a duplicate would throw away a real charge.
    keys = [(component["stage"], component["retry_kind"]) for component in components]
    if len(keys) != len(set(keys)):
        _fail(field, "carries duplicate component keys")

    if status == "complete":
        if estimated is None:
            _fail(field, "is complete without an amount")
        if known is None:
            known = estimated
        if known != estimated:
            _fail(field, "is complete but its known amount differs")
        if reasons:
            _fail(field, "is complete but reports missing components")
    else:
        # Only a complete receipt names a figure. Anything else offers at most
        # a floor, and an estimate riding on it would be the floor promoted to
        # a total by whoever reads it next.
        if estimated is not None:
            _fail(field, f"is {status} but carries an estimate")
        if status in ("partial", "unavailable") and not reasons:
            _fail(field, f"is {status} without a reason code")
    # ``model_cost_usd + runtime_cost_usd == known_cost_usd`` holds at the
    # producer, which sums in Decimal; each field is rounded independently on
    # the way out, so it is checked as a bound rather than an identity.
    for amount, part in ((model_cost, "model_cost_usd"), (runtime_cost, "runtime_cost_usd")):
        if amount is not None and known is not None and amount > known:
            _fail(f"{field}.{part}", "exceeds the known amount")

    return {
        "schema_version": COST_RECEIPT_SCHEMA_VERSION,
        "currency": COST_CURRENCY,
        "status": status,
        "estimated_cost_usd": estimated,
        "known_cost_usd": known,
        "model_cost_usd": model_cost,
        "runtime_cost_usd": runtime_cost,
        "model_calls": _cost_count(
            value.get("model_calls"), f"{field}.model_calls", _MAX_MODEL_CALLS
        ),
        "usage": _cost_usage(value.get("usage"), f"{field}.usage"),
        "components": components,
        "price_table_sha256": _price_table_sha256(
            value.get("price_table_sha256"), f"{field}.price_table_sha256"
        ),
        "missing_reasons": reasons,
    }


def project_cost_ledger_reference(value, field: str = "cost_ledger"):
    """Normalise the ``{path, sha256}`` pointer to the audit JSONL sidecar."""
    if value is None:
        return None
    if not isinstance(value, dict):
        _fail(field, "must be an object")
    path = value.get("path")
    if not isinstance(path, str) or _LEDGER_PATH.fullmatch(path) is None:
        _fail(field, "path must be a relative repository path")
    if ".." in path.split("/"):
        _fail(field, "path must not traverse parents")
    digest = value.get("sha256")
    if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
        _fail(field, "sha256 must be a sha256 digest")
    return {"path": path, "sha256": digest}


def verify_cost_ledger(reference: dict | None, ledger_path: Path) -> dict | None:
    """Re-hash the audit sidecar and confirm it matches the recorded digest.

    A missing file is not an error: the pointer legitimately reaches consumers
    that do not hold the sidecar. A file that is present and hashes to
    something else is — and it raises. A mismatch caught before upload costs
    nothing; the same mismatch caught after upload costs a retraction.
    """
    if reference is None:
        return None
    if not ledger_path.is_file():
        return reference
    digest = hashlib.sha256()
    with ledger_path.open("rb") as stream:
        while chunk := stream.read(_LEDGER_CHUNK_BYTES):
            digest.update(chunk)
    if digest.hexdigest() != reference["sha256"]:
        raise ValueError("cost ledger digest does not match the recorded sha256")
    return reference


def stage_cost_ledger(
    reference: dict | None,
    source_dir: Path,
    upload_dir: Path,
) -> dict | None:
    """Copy the audit sidecar into the upload area under its published name.

    Returns the pointer a published result should carry, or ``None``.

    ``None`` when the export is not on this machine, which is the honest
    answer rather than a convenient one: the pointer would name a file that
    is not going to be uploaded, and publication refuses that — correctly,
    because it sends a reader after a receipt nobody published. Dropping the
    pointer loses a cross-reference; keeping it loses the upload.

    The digest is re-checked against the bytes being copied, so a ledger
    edited between the run and the upload stops here instead of being
    published under a digest that no longer describes it.
    """
    if reference is None:
        return None
    source = Path(source_dir) / reference["path"]
    if not source.is_file():
        return None
    verify_cost_ledger(reference, source)
    destination = Path(upload_dir)
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination / COST_LEDGER_PUBLICATION_PATH)
    return {
        "path": COST_LEDGER_PUBLICATION_PATH,
        "sha256": reference["sha256"],
    }


def _percentile(values: list[float], percentile: float):
    """Linearly interpolated percentile over a non-empty sample."""
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], _MONEY_DIGITS)
    position = (len(ordered) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return round(ordered[lower] * (1 - weight) + ordered[upper] * weight, _MONEY_DIGITS)


def _receipt_amount(receipt: dict):
    """The number this receipt contributes to a total, or ``None``."""
    if receipt["status"] not in _MEASURED_STATUSES:
        return None
    amount = receipt["known_cost_usd"]
    return amount if amount is not None else receipt["estimated_cost_usd"]


def summarize_cost_receipts(
    rows: list[dict],
    field: str,
    *,
    successful_deliverables: int | None = None,
) -> dict | None:
    """Aggregate one cost field across a run.

    Returns ``None`` when not a single row carries a receipt, which is what
    keeps pre-instrumentation experiments reading as "no record".
    """
    receipts = []
    failed_amount = 0.0
    failed_count = 0
    failed_measured = 0
    rows_without_a_receipt = 0
    for row in rows:
        failed = row.get("status") != "success"
        receipt = row.get(field)
        if not isinstance(receipt, dict):
            # No receipt at all is a hole in the record, not a task that cost
            # nothing -- and if that task also failed, it is still a failure.
            # Skipping the row outright counted it in `total_tasks` and in the
            # coverage denominator while subtracting it from the failure count,
            # so the same table could read "1 / 2 tasks (50.0%)" beside
            # "Failed tasks | 0" and disagree with itself about whether a
            # second task existed.
            rows_without_a_receipt += 1
            if failed:
                failed_count += 1
            continue
        receipts.append(receipt)
        if failed:
            failed_count += 1
            amount = _receipt_amount(receipt)
            if amount is not None:
                # Counted, not just added. Two failures against a model the
                # price table has no entry for contribute nothing here, and the
                # sum they leave behind is 0.0 -- the same number a failure that
                # genuinely made no model call leaves behind. The amount alone
                # cannot tell those apart, so the count of failures that could
                # be priced is published beside it.
                failed_measured += 1
                failed_amount += amount
    if not receipts:
        return None

    counts = {status: 0 for status in COST_STATUSES}
    for receipt in receipts:
        counts[receipt["status"]] += 1

    amounts = [
        amount
        for receipt in receipts
        if (amount := _receipt_amount(receipt)) is not None
    ]
    known_total = round(sum(amounts), _MONEY_DIGITS) if amounts else 0.0

    # The run's state comes from the receipts' own states, not from whether a
    # number fell out of them. `amounts` is empty whenever every measurable
    # receipt sits at a $0 floor — which `_measured_amount` above nulls on
    # purpose, and which is the ordinary case when the model that was called is
    # absent from the price table. Reading the state off `amounts` made such a
    # run fall past `partial` all the way to `not_run`: two tasks, two paid
    # calls, real tokens on both, published as work that never happened.
    #
    # Work that genuinely never ran is not a hole in the run. It contributed
    # nothing, so it neither drags the state down nor stops a total being a
    # total — where `counts["complete"] == len(receipts)` counted it against the
    # run and withheld a figure every receipt underneath it supported.
    #
    # A total is still only a total when every receipt that ran is complete. One
    # partial or unavailable receipt makes it a floor, and it is labelled as one
    # rather than quietly rounded up into a headline number.
    #
    # This is the rule `core.cost_receipts._summary_status` and
    # `scripts/cost-receipt.mjs` already apply to the same receipts. Three
    # summarisers read one set of receipts; they must not give three answers
    # about it.
    contributing = [
        receipt for receipt in receipts if receipt["status"] != "not_run"
    ]
    if not contributing:
        status = "not_run"
    elif all(receipt["status"] == "complete" for receipt in contributing):
        status = "complete"
    elif all(receipt["status"] == "unavailable" for receipt in contributing):
        status = "unavailable"
    else:
        status = "partial"
    complete_run = status == "complete"
    if rows_without_a_receipt and status == "complete":
        # Every receipt the run does carry is whole, but the run is not: some
        # task's cost was never recorded at all. Judging completeness against
        # `len(receipts)` asks only "is what I kept consistent?", which the
        # rows that were dropped can never answer. So a two-task run holding
        # one $0.42 receipt announced "Receipt status: complete" and headed the
        # table "Total | $0.4200" -- a total over half a run.
        #
        # Only `complete` moves. A run already reading partial, unavailable or
        # not_run is already not claiming to be whole, and a run where every
        # row carries a receipt reaches none of this, so no fully-recorded
        # experiment changes what it says.
        status = "partial"
        complete_run = False

    reasons = sorted({
        reason
        for receipt in receipts
        for reason in receipt["missing_reasons"]
    })
    price_tables = sorted({
        receipt["price_table_sha256"]
        for receipt in receipts
        if receipt["price_table_sha256"]
    })
    component_totals: dict[str, dict] = {}
    for receipt in receipts:
        # Roll one receipt's lines up by displayed name before touching the run
        # totals. A task whose generation and Self-QA both had to be redone
        # carries two 재시도 lines but is still one task, and counting it twice
        # would make the coverage figure beside the row a fiction.
        rolled: dict[str, dict] = {}
        for component in receipt["components"]:
            entry = rolled.setdefault(
                component["name"],
                {"known_cost_usd": 0.0, "model_calls": 0, "complete": True},
            )
            amount = component["known_cost_usd"]
            if amount is not None:
                entry["known_cost_usd"] += amount
            if component["model_calls"]:
                entry["model_calls"] += component["model_calls"]
            if component["status"] != "complete":
                entry["complete"] = False
        for name, entry in rolled.items():
            bucket = component_totals.setdefault(
                name,
                {
                    "name": name,
                    "tasks": 0,
                    "known_cost_usd": 0.0,
                    "complete_tasks": 0,
                    "model_calls": 0,
                },
            )
            bucket["tasks"] += 1
            if entry["complete"]:
                bucket["complete_tasks"] += 1
            bucket["known_cost_usd"] += entry["known_cost_usd"]
            bucket["model_calls"] += entry["model_calls"]
    components = []
    for bucket in sorted(component_totals.values(), key=lambda item: item["name"]):
        bucket["known_cost_usd"] = round(bucket["known_cost_usd"], _MONEY_DIGITS)
        bucket["status"] = (
            "complete" if bucket["complete_tasks"] == bucket["tasks"] else "partial"
        )
        components.append(bucket)

    per_deliverable = None
    if complete_run and successful_deliverables:
        per_deliverable = round(known_total / successful_deliverables, _MONEY_DIGITS)

    return {
        "schema_version": COST_RECEIPT_SCHEMA_VERSION,
        "currency": COST_CURRENCY,
        "estimate_basis": ESTIMATE_BASIS,
        "status": status,
        "total_tasks": len(rows),
        "receipt_tasks": len(receipts),
        "measured_tasks": len(amounts),
        "coverage_pct": round(len(receipts) / len(rows) * 100, 1) if rows else 0.0,
        "complete_tasks": counts["complete"],
        "partial_tasks": counts["partial"],
        "unavailable_tasks": counts["unavailable"],
        "not_run_tasks": counts["not_run"],
        "known_cost_usd": known_total,
        "estimated_cost_usd": known_total if complete_run else None,
        "avg_cost_usd": round(sum(amounts) / len(amounts), _MONEY_DIGITS) if amounts else None,
        "median_cost_usd": _percentile(amounts, 0.50),
        "p95_cost_usd": _percentile(amounts, 0.95),
        "max_cost_usd": round(max(amounts), _MONEY_DIGITS) if amounts else None,
        "successful_deliverables": successful_deliverables,
        "cost_per_successful_deliverable_usd": per_deliverable,
        # Failed work costs real money. It is reported beside the total, not
        # netted out of it.
        "failed_task_count": failed_count,
        # How many of those failures could be priced at all. Without it the
        # amount below is unreadable: $0 means "these failures were free" and
        # "these failures were never priced" at the same time.
        "failed_measured_tasks": failed_measured,
        "failed_task_cost_usd": round(failed_amount, _MONEY_DIGITS),
        "components": components,
        "price_table_sha256": price_tables[0] if len(price_tables) == 1 else None,
        "missing_reasons": reasons,
    }


def build_cost_summaries(
    rows: list[dict],
    *,
    successful_deliverables: int | None = None,
) -> dict:
    """Return the present cost summaries; absent fields stay absent."""
    summaries = {}
    for field in COST_FIELDS:
        summary = summarize_cost_receipts(
            rows,
            field,
            successful_deliverables=successful_deliverables,
        )
        if summary is not None:
            summaries[field] = summary
    return summaries


def successful_deliverable_count(rows: list[dict]) -> int:
    """Count tasks that finished successfully with something to grade.

    Both halves matter. A ``success`` row that produced neither a file nor any
    deliverable text is not a deliverable, and counting it would make the
    per-deliverable figure look cheaper than the run actually was.
    """
    count = 0
    for row in rows:
        if row.get("status") != "success":
            continue
        files = row.get("deliverable_files") or []
        text = row.get("deliverable_text") or ""
        if (isinstance(files, list) and files) or (isinstance(text, str) and text.strip()):
            count += 1
    return count
