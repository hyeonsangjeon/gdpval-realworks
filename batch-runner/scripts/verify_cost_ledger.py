#!/usr/bin/env python3
"""Check that a published grade's cost receipt is backed by its own ledger.

A grade file states what a grading run cost. Beside it sits the ledger: one
line per model call, written before the request went out and updated when the
reply came back. This tool is the free, offline check that the two agree.

It answers the questions an owner actually asks of a bill:

  * Is the ledger the one the grade file points at, unchanged since?
  * Was any single call billed twice, and were retries kept as the separate
    calls they are rather than folded away?
  * Did every call that went out come back, or did some leave no reply?
  * Do the per-call tokens and dollars add up to the totals in the receipt,
    component by component and in the whole?
  * Where the receipt is not ``complete``, is that because a model has no
    published price -- which is honest -- or because usage went missing,
    which is a defect?
  * What did the tasks that failed cost? A failed task is not a free task.

Nothing here calls a model, reads a credential, or touches the network. It
reads two files that already exist. Run it on a finished run:

    cd batch-runner
    python scripts/verify_cost_ledger.py path/to/grade.json
    python scripts/verify_cost_ledger.py path/to/grade.json --json

The exit code is 0 only when every check passed. A failure exits 1 and names
the check, so this is safe to wire into an automated gate.

What this tool deliberately does NOT do is judge the grading. A run may score
badly and still have a perfect receipt, and a run may score well on a receipt
that does not add up. Scores are printed as context and never decide the exit
code. "The pipeline accounted for itself" and "the model did well" are two
different questions, and conflating them is how a billing defect gets
published under a good headline number.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable

# The token kinds a cost-receipt-v1 ``usage`` block is closed over. Audio was
# outside it until the published schema grew explicit ``audio_*_tokens``
# properties: the ledger measured those columns, the receipt had nowhere to put
# them, and check_usage_containment reported the gap. It is inside now, so it
# reconciles exactly like every other kind. See _extra_token_keys for what
# still happens to a kind the receipt cannot express.
RECEIPT_USAGE_KEYS = (
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "reasoning_tokens",
    "audio_input_tokens",
    "audio_output_tokens",
)

# The tuple a receipt component is keyed on. A component is one line of the
# bill, and two calls belong to the same line only when all of this matches.
COMPONENT_KEY = (
    "stage",
    "retry_kind",
    "provider",
    "deployment",
    "requested_model",
    "resolved_model",
    "api_version",
)

STATE_SETTLED = "settled"
STATE_RESERVED = "reserved"

# A missing_reason that names an absent price is an honest gap: the call
# happened, the tokens were kept, and no published rate covers the model. Any
# other reason for an unpriced call means the usage itself was lost.
PRICE_ABSENT_MARKERS = ("price", "unpriced", "no_rate", "rate_missing")


class Finding:
    """One check's verdict, with the evidence that produced it."""

    def __init__(self, check: str, ok: bool, detail: str, data: Any = None) -> None:
        self.check = check
        self.ok = ok
        self.detail = detail
        self.data = data

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"check": self.check, "ok": self.ok, "detail": self.detail}
        if self.data is not None:
            out["data"] = self.data
        return out


def _dec(value: Any) -> Decimal:
    """Read a money field without going through binary floating point.

    The ledger writes dollars as strings for this reason. Adding 84 of them as
    floats and comparing to a float total is how a reconciliation check comes
    out wrong by a cent and gets "fixed" with a tolerance.
    """
    if value is None:
        return Decimal(0)
    return Decimal(str(value))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{path}: line {number} is not JSON: {exc}") from exc
    return rows


def _tokens(row: dict[str, Any], keys: Iterable[str]) -> dict[str, int]:
    """A row's counts with absent read as zero. For predicates, not for sums.

    Fine where the question is "did this call use any of these", which is what
    the remaining callers ask. Wrong where the question is "how many", because
    it answers "none measured" and "measured none" with the same integer. Use
    ``_token_totals`` there.
    """
    return {key: int(row.get(key) or 0) for key in keys}


def _as_count(value: Any) -> int | None:
    """A token count, or ``None`` for a kind nobody stated.

    Anything else raises. A count that is negative, fractional, a string or a
    bool is not a measurement, and coercing it would publish a number the
    provider never reported. ``bool`` is rejected explicitly because it is an
    ``int`` in Python and ``True`` would otherwise be read as one token.
    """
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{value!r} is not an integer token count")
    if value < 0:
        raise ValueError(f"{value!r} is a negative token count")
    return value


def _token_totals(
    rows: Iterable[dict[str, Any]], keys: Iterable[str]
) -> dict[str, int | None]:
    """Sum the way the receipt builder sums: absent stays absent.

    A key holds ``None`` until some row states a count for it, and a row
    stating zero is such a row. That keeps "the ledger never measured this"
    distinct from "the ledger measured this and it was none" -- the same
    distinction ``core.cost_receipts.empty_usage`` seeds the receipt with, and
    the reason this check can be compared against it at all.

    Raises ValueError naming the call if the ledger carries a value that is not
    a non-negative integer, which is corruption of the durable evidence and
    louder than a silent coercion to zero.
    """
    keys = tuple(keys)
    totals: dict[str, int | None] = {key: None for key in keys}
    for row in rows:
        for key in keys:
            try:
                count = _as_count(row.get(key))
            except ValueError as exc:
                raise ValueError(f"call {row.get('call_id')!r}: {key} {exc}") from None
            if count is None:
                continue
            totals[key] = (totals[key] or 0) + count
    return totals


def _usage_agrees(stated: int | None, ledger: int | None) -> bool:
    """Does a stated count match what the ledger actually measured?

    Where the ledger measured nothing, a receipt may say so with ``null`` or
    with ``0``. Every receipt published before a column existed says ``0`` for
    it, and rejecting those would fail records that were honest under the
    contract they were published under -- the schema change is additive, and
    so is this. Where the ledger did measure, only the measured number agrees:
    silence is an omission and a different number is a misstatement, and both
    fail.
    """
    if ledger is None:
        return stated is None or stated == 0
    return stated == ledger


def _extra_token_keys(rows: Iterable[dict[str, Any]]) -> tuple[str, ...]:
    """Token columns in the ledger that the receipt's usage block cannot hold.

    Derived from the rows rather than listed here. A hardcoded list stops being
    a check the moment the receipt catches up with it -- which is what happened
    to audio -- and says nothing about whatever is metered next. Anything named
    ``*_tokens`` outside ``RECEIPT_USAGE_KEYS`` is reported whether or not this
    file has heard of it.
    """
    return tuple(
        sorted(
            {
                key
                for row in rows
                for key in row
                if key.endswith("_tokens") and key not in RECEIPT_USAGE_KEYS
            }
        )
    )


def _is_price_absent(reasons: Iterable[str]) -> bool:
    joined = " ".join(str(reason).lower() for reason in reasons)
    return any(marker in joined for marker in PRICE_ABSENT_MARKERS)


def check_sidecar(grade: dict[str, Any], grade_path: Path) -> tuple[Finding, Path | None]:
    """The ledger the grade points at must be there, and must be that ledger."""
    sidecar = grade.get("cost_ledger")
    if not isinstance(sidecar, dict):
        return Finding(
            "sidecar",
            False,
            "the grade file declares no cost_ledger sidecar, so nothing "
            "connects its stated cost to per-call evidence",
        ), None

    declared_path = sidecar.get("path")
    declared_sha = sidecar.get("sha256")
    if not declared_path or not declared_sha:
        return Finding(
            "sidecar", False, f"cost_ledger is missing path or sha256: {sidecar!r}"
        ), None

    ledger_path = grade_path.parent / Path(str(declared_path)).name
    if not ledger_path.exists():
        return Finding(
            "sidecar",
            False,
            f"the declared ledger {declared_path!r} is not beside the grade file",
        ), None

    actual = hashlib.sha256(ledger_path.read_bytes()).hexdigest()
    if actual != declared_sha:
        return Finding(
            "sidecar",
            False,
            "the ledger beside the grade file is not the one it was published "
            f"with: declared {declared_sha}, found {actual}",
            {"declared_sha256": declared_sha, "actual_sha256": actual},
        ), None

    return Finding(
        "sidecar",
        True,
        f"ledger present and unchanged since publication (sha256 {actual[:16]}...)",
        {"sha256": actual, "path": ledger_path.name},
    ), ledger_path


def check_identity(grade: dict[str, Any], calls: list[dict[str, Any]]) -> Finding:
    """Every row must belong to one run, and that run must be this grade."""
    run_ids = sorted({row.get("run_id") for row in calls})
    if len(run_ids) != 1:
        return Finding(
            "identity",
            False,
            f"the ledger mixes {len(run_ids)} run identities: {run_ids}",
            {"run_ids": run_ids},
        )

    run_id = run_ids[0]
    parts = str(run_id).split("|")
    source_hash = grade.get("grader_source_hash")
    if len(parts) == 3 and source_hash and parts[2] != source_hash:
        return Finding(
            "identity",
            False,
            "the ledger's grader fingerprint does not match the grade file: "
            f"ledger {parts[2][:16]}..., grade {str(source_hash)[:16]}...",
            {"ledger_run_id": run_id, "grade_grader_source_hash": source_hash},
        )

    return Finding(
        "identity", True, f"all {len(calls)} rows belong to one run: {run_id}",
        {"run_id": run_id},
    )


def check_no_double_billing(calls: list[dict[str, Any]]) -> Finding:
    """One call, one row -- and a retry is a different call, not a duplicate.

    ``call_id`` is the ledger table's primary key, so a duplicate here means
    the exported file was written from more than one ledger, or written twice.
    Retries are separate rows with their own identifiers and a non-``none``
    ``retry_kind``; folding them together would understate a bill that was
    really paid twice, so they are counted, not deduplicated.
    """
    seen: dict[str, int] = {}
    for row in calls:
        call_id = str(row.get("call_id"))
        seen[call_id] = seen.get(call_id, 0) + 1
    duplicates = {key: count for key, count in seen.items() if count > 1}
    if duplicates:
        return Finding(
            "no_double_billing",
            False,
            f"{len(duplicates)} call identifiers appear more than once, so the "
            "same call is counted twice in the totals",
            {"duplicate_call_ids": duplicates},
        )

    retries = [row for row in calls if (row.get("retry_kind") or "none") != "none"]
    by_kind: dict[str, int] = {}
    for row in retries:
        kind = str(row.get("retry_kind"))
        by_kind[kind] = by_kind.get(kind, 0) + 1
    return Finding(
        "no_double_billing",
        True,
        f"{len(seen)} distinct calls, none counted twice; "
        f"{len(retries)} of them are retries kept as separate billable calls",
        {"distinct_calls": len(seen), "retries_by_kind": by_kind},
    )


def check_all_calls_settled(calls: list[dict[str, Any]]) -> Finding:
    """A row still in 'reserved' is a call that went out and never came back.

    The ledger writes the row *before* the request, so this state is not
    bookkeeping noise: it is a request the provider may well have billed,
    whose reply was never recorded. It cannot appear in the totals, which is
    exactly why it has to be surfaced rather than subtracted.

    Only 'reserved' means that. A row is 'abandoned' when the call is known
    never to have left, and 'refused' when the provider answered and the answer
    was a rejection issued before any model ran. Neither is a reply that went
    missing, and reporting them here would bury the rows that are — which is
    the same mistake, one layer up, that ``call_refused_unpriced`` exists to
    stop the ledger making. They are counted in the evidence instead.
    """
    unsettled = [row for row in calls if row.get("state") == STATE_RESERVED]
    resolved_without_a_reply = sorted(
        {
            str(row.get("state") or "")
            for row in calls
            if row.get("state") not in (STATE_SETTLED, STATE_RESERVED)
        }
    )
    counts = {
        state: sum(1 for row in calls if row.get("state") == state)
        for state in resolved_without_a_reply
    }
    if unsettled:
        return Finding(
            "all_calls_settled",
            False,
            f"{len(unsettled)} calls were sent but never recorded a reply, so "
            "their cost is absent from the receipt without being zero",
            {
                "unsettled": [
                    {
                        "call_id": row.get("call_id"),
                        "task_id": row.get("task_id"),
                        "stage": row.get("stage"),
                        "state": row.get("state"),
                        "note": row.get("note"),
                    }
                    for row in unsettled[:20]
                ],
                "unsettled_count": len(unsettled),
                "other_states": counts,
            },
        )
    settled = sum(1 for row in calls if row.get("state") == STATE_SETTLED)
    detail = f"every one of the {len(calls)} calls recorded a reply"
    if counts:
        named = ", ".join(f"{count} {state}" for state, count in counts.items())
        detail = (
            f"{settled} of {len(calls)} calls recorded a reply and none is "
            f"still waiting for one ({named})"
        )
    return Finding(
        "all_calls_settled", True, detail, {"other_states": counts} if counts else None
    )


def check_usage_reconciles(receipt: dict[str, Any], settled: list[dict[str, Any]]) -> Finding:
    """The per-call tokens must add up to the receipt's totals, exactly.

    Exactly, and also faithfully: a kind the ledger never measured has to stay
    unmeasured in the receipt. Filling it with a zero would be the one failure
    this check cannot afterwards detect, because a zero reads as a measurement
    and there is nothing left to compare it against.
    """
    stated = receipt.get("usage") or {}
    try:
        summed = _token_totals(settled, RECEIPT_USAGE_KEYS)
    except ValueError as exc:
        return Finding(
            "usage_reconciles",
            False,
            f"the ledger cannot be summed: {exc}",
            {"ledger_error": str(exc)},
        )

    mismatches: dict[str, Any] = {}
    for key in RECEIPT_USAGE_KEYS:
        raw = stated.get(key)
        try:
            claimed = _as_count(raw)
        except ValueError as exc:
            mismatches[key] = {"receipt": raw, "ledger": summed[key], "problem": str(exc)}
            continue
        if not _usage_agrees(claimed, summed[key]):
            mismatches[key] = {"receipt": raw, "ledger": summed[key]}

    if mismatches:
        return Finding(
            "usage_reconciles",
            False,
            f"{len(mismatches)} token totals disagree between the receipt and "
            "the ledger it was built from",
            mismatches,
        )
    return Finding(
        "usage_reconciles", True, "every token total matches the ledger exactly", summed
    )


def check_usage_containment(settled: list[dict[str, Any]]) -> Finding:
    """Tokens the receipt's usage block cannot represent.

    ``cost-receipt-v1`` closes ``usage`` over a fixed set of kinds. Audio used
    to fall outside it -- metered in the ledger, unrepresentable in the
    receipt, so a reader adding the usage up would not reach what the run
    consumed. That gap is closed, and audio now reconciles like every other
    kind in check_usage_reconciles.

    This check does not retire with it. It asks the same question of whatever
    the ledger carries today, reading the kinds off the rows instead of a list
    kept here, so the next thing metered is caught the run it appears rather
    than the release someone remembers to widen this file. The dollars may
    still be right; the usage block is not a full statement of what was
    consumed, and that is reported, never passed.
    """
    extra_keys = _extra_token_keys(settled)
    if not extra_keys:
        return Finding(
            "usage_containment",
            True,
            "the receipt's usage block is closed over every token kind this "
            "ledger carries",
            {"receipt_keys": list(RECEIPT_USAGE_KEYS)},
        )

    carriers = []
    for row in settled:
        extra = _tokens(row, extra_keys)
        if any(extra.values()):
            carriers.append(
                {"call_id": row.get("call_id"), "stage": row.get("stage"), **extra}
            )
    if carriers:
        totals = {
            key: sum(int(item.get(key) or 0) for item in carriers) for key in extra_keys
        }
        return Finding(
            "usage_containment",
            False,
            f"{len(carriers)} calls consumed token kinds the receipt's usage "
            f"block cannot express ({totals}), so its usage understates the run",
            {
                "totals": totals,
                "unexpressible_keys": list(extra_keys),
                "calls": carriers[:20],
            },
        )
    return Finding(
        "usage_containment",
        True,
        f"the ledger carries {len(extra_keys)} token kinds the receipt cannot "
        "express, and no call used any of them",
        {"unexpressible_keys": list(extra_keys)},
    )


def check_cost_reconciles(receipt: dict[str, Any], settled: list[dict[str, Any]]) -> Finding:
    """Dollars must add up, and the status must match what is actually known."""
    problems = []

    ledger_total = sum((_dec(row.get("model_cost_usd")) for row in settled), Decimal(0))
    stated_model = _dec(receipt.get("model_cost_usd"))
    if ledger_total != stated_model:
        problems.append(
            f"model cost: receipt {stated_model}, ledger sums to {ledger_total}"
        )

    known = _dec(receipt.get("known_cost_usd"))
    runtime = _dec(receipt.get("runtime_cost_usd"))
    if stated_model + runtime != known:
        problems.append(
            f"model {stated_model} + runtime {runtime} != known {known}"
        )

    status = receipt.get("status")
    estimated = receipt.get("estimated_cost_usd")
    if status == "complete":
        if estimated is None:
            problems.append("status is complete but no total is stated")
        elif _dec(estimated) != known:
            problems.append(f"complete, but estimated {estimated} != known {known}")
    elif estimated is not None:
        problems.append(
            f"status is {status!r}, which cannot carry a total, yet states {estimated}"
        )

    calls = receipt.get("model_calls")
    if calls is not None and int(calls) != len(settled):
        problems.append(f"receipt counts {calls} calls, ledger settles {len(settled)}")

    if problems:
        return Finding("cost_reconciles", False, "; ".join(problems), {"problems": problems})
    return Finding(
        "cost_reconciles",
        True,
        f"{len(settled)} calls sum to {ledger_total} USD, matching the receipt "
        f"(status {status!r})",
        {"ledger_total_usd": str(ledger_total), "status": status},
    )


def check_components_reconcile(
    receipt: dict[str, Any], settled: list[dict[str, Any]]
) -> Finding:
    """Each line of the bill must be backed by the calls assigned to it.

    Per line, token kinds carry the same absent/measured distinction the
    receipt's own totals do, so a component that omits a kind its calls
    reported is caught here and not only in the grand total -- where one line
    over-stating and another under-stating would cancel out.
    """
    rows_by_key: dict[tuple, list[dict[str, Any]]] = {}
    for row in settled:
        key = tuple(row.get(field) for field in COMPONENT_KEY)
        rows_by_key.setdefault(key, []).append(row)

    problems = []
    grouped: dict[tuple, dict[str, Any]] = {}
    for key, rows in rows_by_key.items():
        try:
            usage = _token_totals(rows, RECEIPT_USAGE_KEYS)
        except ValueError as exc:
            problems.append(f"component {dict(zip(COMPONENT_KEY, key))}: {exc}")
            usage = {token_key: None for token_key in RECEIPT_USAGE_KEYS}
        grouped[key] = {
            "model_calls": len(rows),
            "cost": sum((_dec(row.get("model_cost_usd")) for row in rows), Decimal(0)),
            "usage": usage,
        }

    components = receipt.get("components") or []
    for component in components:
        key = tuple(component.get(field) for field in COMPONENT_KEY)
        bucket = grouped.pop(key, None)
        name = component.get("name") or component.get("stage")
        if bucket is None:
            problems.append(f"component {name!r} has no calls behind it in the ledger")
            continue
        if int(component.get("model_calls") or 0) != bucket["model_calls"]:
            problems.append(
                f"component {name!r}: receipt {component.get('model_calls')} calls, "
                f"ledger {bucket['model_calls']}"
            )
        if _dec(component.get("known_cost_usd")) != bucket["cost"]:
            problems.append(
                f"component {name!r}: receipt {component.get('known_cost_usd')} USD, "
                f"ledger {bucket['cost']}"
            )
        stated_usage = component.get("usage") or {}
        for token_key in RECEIPT_USAGE_KEYS:
            raw = stated_usage.get(token_key)
            try:
                claimed = _as_count(raw)
            except ValueError as exc:
                problems.append(f"component {name!r}: {token_key} {exc}")
                continue
            if not _usage_agrees(claimed, bucket["usage"][token_key]):
                problems.append(
                    f"component {name!r}: {token_key} receipt "
                    f"{raw}, ledger {bucket['usage'][token_key]}"
                )

    for key, bucket in grouped.items():
        problems.append(
            f"{bucket['model_calls']} calls ({dict(zip(COMPONENT_KEY, key))}) "
            "appear in the ledger but on no line of the receipt"
        )

    if problems:
        return Finding(
            "components_reconcile",
            False,
            f"{len(problems)} component disagreements",
            {"problems": problems},
        )
    return Finding(
        "components_reconcile",
        True,
        f"all {len(components)} receipt components are backed call-for-call",
    )


def check_price_table(receipt: dict[str, Any], settled: list[dict[str, Any]]) -> Finding:
    """One run, one price table -- otherwise the total mixes two rate cards."""
    tables = sorted({row.get("price_table_sha256") for row in settled if row.get("price_table_sha256")})
    stated = receipt.get("price_table_sha256")
    if len(tables) > 1:
        return Finding(
            "price_table",
            False,
            f"calls were priced against {len(tables)} different rate tables",
            {"price_tables": tables},
        )
    if tables and stated and tables[0] != stated:
        return Finding(
            "price_table",
            False,
            f"receipt names table {str(stated)[:16]}..., calls used {tables[0][:16]}...",
            {"receipt": stated, "ledger": tables[0]},
        )
    return Finding(
        "price_table",
        True,
        f"every priced call used one rate table ({(tables[0][:16] + '...') if tables else 'none recorded'})",
    )


def check_partial_cause(receipt: dict[str, Any], settled: list[dict[str, Any]]) -> Finding:
    """Separate an honest missing price from usage that was thrown away.

    These two produce the same word in the receipt -- ``partial`` -- and mean
    opposite things. A model with no published rate is a gap in the price
    table: the call is fully recorded, the tokens are all there, and the
    dollar figure is unknown rather than zero. Usage that vanished is a defect
    in the pipeline: the receipt cannot state a cost because it no longer
    knows what was consumed. Only the second is a bug in this repository.
    """
    honest = []
    defective = []
    for row in settled:
        if row.get("model_cost_usd") is not None:
            continue
        reasons = row.get("missing_reasons") or []
        tokens = _tokens(row, RECEIPT_USAGE_KEYS)
        record = {
            "call_id": row.get("call_id"),
            "task_id": row.get("task_id"),
            "stage": row.get("stage"),
            "requested_model": row.get("requested_model"),
            "resolved_model": row.get("resolved_model"),
            "missing_reasons": reasons,
            "usage": tokens,
        }
        if _is_price_absent(reasons) and any(tokens.values()):
            honest.append(record)
        else:
            defective.append(record)

    status = receipt.get("status")
    if defective:
        return Finding(
            "partial_cause",
            False,
            f"{len(defective)} unpriced calls are not explained by a missing "
            "rate: their usage was lost, which is a pipeline defect and not a "
            "gap in the price table",
            {"discarded_usage": defective[:20], "expected_price_missing": len(honest)},
        )

    if honest and status == "complete":
        return Finding(
            "partial_cause",
            False,
            f"the receipt claims complete while {len(honest)} calls have no "
            "price, so the stated total omits real spend",
            {"expected_price_missing": honest[:20]},
        )

    if honest:
        models = sorted({str(item["resolved_model"] or item["requested_model"]) for item in honest})
        return Finding(
            "partial_cause",
            True,
            f"{len(honest)} calls are unpriced only because {models} have no "
            "published rate; their usage is fully recorded, so the cost is "
            "unknown rather than zero",
            {"unpriced_models": models, "unpriced_calls": len(honest)},
        )

    return Finding(
        "partial_cause", True, "every call carries a price; nothing is unexplained"
    )


def _declared_consumption(item: dict[str, Any]) -> dict[str, Any] | None:
    """What a task row says it consumed, or ``None`` if it does not say.

    ``step8_grade.py`` writes the same number twice: once as call counters on
    the task, once as ``model_calls`` on that task's own receipt. Both are read
    here, because a disagreement between the two is itself a finding, and
    because an older payload may carry only one of them.

    ``render_call_count`` is deliberately left out. A render is not a model
    call and never reaches the ledger, so adding it would make every task that
    rendered anything look over-billed.
    """
    counters = ("judge_call_count", "perception_call_count")
    counted = (
        sum(int(item.get(name) or 0) for name in counters)
        if any(name in item for name in counters)
        else None
    )
    receipt = item.get("grading_cost")
    receipt = receipt if isinstance(receipt, dict) else {}
    claimed = (
        int(receipt.get("model_calls") or 0) if "model_calls" in receipt else None
    )
    if counted is None and claimed is None:
        return None
    return {
        "calls": counted if counted is not None else claimed,
        "counted_calls": counted,
        "receipt_calls": claimed,
        "cost_usd": _dec(
            _first_present(receipt, "estimated_cost_usd", "known_cost_usd")
        ),
    }


def check_task_coverage(grade: dict[str, Any], settled: list[dict[str, Any]]) -> Finding:
    """What every task cost -- including the ones that never reached the judge.

    A task that errored *during* grading still sent calls and still got billed
    for them, so a receipt that only accounts for successes understates the
    run. But a task can also stop before the first judge call -- nothing was
    produced to grade, or nothing could be chosen from what was -- and then
    zero calls really did cost zero dollars.

    Being named in the payload does not tell those two apart. The payload's own
    figures do: every task states its call counts, restates them on a per-task
    receipt, and leaves rows in the ledger. This reconciles all three, task by
    task. A disagreement in either direction is a finding -- a task claiming
    calls the ledger cannot show, and a task whose calls sit in the ledger
    behind a zero it declared for itself. A task that declares nothing at all
    still falls under the older rule below: no rows means graded for free.
    """
    per_task: dict[str, dict[str, Any]] = {}
    for row in settled:
        task_id = str(row.get("task_id"))
        bucket = per_task.setdefault(task_id, {"calls": 0, "cost": Decimal(0)})
        bucket["calls"] += 1
        bucket["cost"] += _dec(row.get("model_cost_usd"))

    results = grade.get("results") or grade.get("tasks") or []
    failed_ids, undeclared = set(), set()
    disputed: list[dict[str, Any]] = []
    never_graded: list[str] = []
    if isinstance(results, list):
        for item in results:
            if not isinstance(item, dict):
                continue
            task_id = str(item.get("task_id") or item.get("id") or "")
            if not task_id:
                continue
            status = str(item.get("status") or item.get("grade_status") or "").lower()
            if item.get("error") or status in {"error", "failed", "failure"}:
                failed_ids.add(task_id)

            declared = _declared_consumption(item)
            billed = int(per_task.get(task_id, {}).get("calls", 0))
            if declared is None:
                undeclared.add(task_id)
                continue
            counted, claimed = declared["counted_calls"], declared["receipt_calls"]
            if counted is not None and claimed is not None and counted != claimed:
                disputed.append(
                    {
                        "task_id": task_id,
                        "counted_calls": counted,
                        "receipt_calls": claimed,
                        "ledger_calls": billed,
                        "why": "the task and its own receipt disagree",
                    }
                )
            elif declared["calls"] != billed:
                disputed.append(
                    {
                        "task_id": task_id,
                        "declared_calls": declared["calls"],
                        "ledger_calls": billed,
                        "why": "the ledger does not hold the calls the task declares",
                    }
                )
            elif declared["calls"] == 0 and declared["cost_usd"] != 0:
                disputed.append(
                    {
                        "task_id": task_id,
                        "declared_calls": 0,
                        "declared_cost_usd": str(declared["cost_usd"]),
                        "why": "a task that made no call cannot have been billed",
                    }
                )
            elif declared["calls"] == 0:
                never_graded.append(task_id)

    uncosted = sorted(undeclared - set(per_task))
    if disputed or uncosted:
        parts = []
        if disputed:
            parts.append(
                f"{len(disputed)} tasks do not agree with the ledger about what "
                "they consumed"
            )
        if uncosted:
            parts.append(
                f"{len(uncosted)} graded tasks have no call in the ledger, so they "
                "appear to have been graded for free"
            )
        return Finding(
            "task_coverage",
            False,
            "; ".join(parts),
            {"disputed": disputed[:20], "tasks_without_cost": uncosted[:20]},
        )

    failed_cost = {
        task_id: str(per_task[task_id]["cost"])
        for task_id in sorted(failed_ids)
        if task_id in per_task
    }
    free = (
        f"; {len(never_graded)} never reached the judge and cost nothing"
        if never_graded
        else ""
    )
    return Finding(
        "task_coverage",
        True,
        f"{len(per_task)} tasks carry cost; {len(failed_ids)} failed tasks were "
        f"billed {sum((_dec(v) for v in failed_cost.values()), Decimal(0))} USD "
        f"and are accounted for, not treated as free{free}",
        {
            "per_task": {k: {"calls": v["calls"], "cost_usd": str(v["cost"])} for k, v in sorted(per_task.items())},
            "failed_task_cost_usd": failed_cost,
            "tasks_never_graded": sorted(never_graded),
        },
    )


def _first_present(mapping: dict[str, Any], *names: str) -> Any:
    """Return the first key that is actually there, not the first truthy one.

    ``a or b`` reads a real score of 0.0 as absent and reports it as unknown.
    A task that scored zero scored zero; saying "no score recorded" instead is
    how a genuine failure gets published as missing data.
    """
    for name in names:
        if name in mapping and mapping[name] is not None:
            return mapping[name]
    return None


def check_legacy_counters(grade: dict[str, Any], settled: list[dict[str, Any]]) -> Finding:
    """The older ``summary.cost`` block must still count the same calls.

    That block predates cost-receipt-v1 and answers a different question. Its
    price fields are pinned by ``core/grade_payload.py``, which *requires*
    ``estimated_cost_usd`` to be null, ``pricing_complete`` to be false, and
    ``unpriced_models`` to list the configured judge and every configured
    perception modality -- whether or not those models were ever called, and
    whether or not a rate exists for them. So a run can honestly carry a
    settled receipt of $0.75 beside a legacy block saying "unpriced". That is
    intentional and is not checked here.

    What the two blocks may never disagree on is arithmetic. The call and
    token counters are statements of fact about the same calls, so drift
    between them means one of the two stopped counting the run in front of it.
    """
    legacy = (grade.get("summary") or {}).get("cost")
    if not isinstance(legacy, dict):
        return Finding("legacy_counters", True, "no legacy summary.cost block to compare")

    grading = [row for row in settled if row.get("stage") == "grading"]
    perception = [row for row in settled if row.get("stage") == "perception"]
    expected = {
        "total_judge_calls": len(settled),
        "total_main_judge_calls": len(grading),
        "total_perception_calls": len(perception),
        "total_input_tokens": sum(int(r.get("input_tokens") or 0) for r in settled),
        "total_output_tokens": sum(int(r.get("output_tokens") or 0) for r in settled),
        "total_cached_tokens": sum(int(r.get("cached_input_tokens") or 0) for r in settled),
        "main_input_tokens": sum(int(r.get("input_tokens") or 0) for r in grading),
        "main_output_tokens": sum(int(r.get("output_tokens") or 0) for r in grading),
        "main_cached_tokens": sum(int(r.get("cached_input_tokens") or 0) for r in grading),
        "perception_input_tokens": sum(int(r.get("input_tokens") or 0) for r in perception),
        "perception_output_tokens": sum(int(r.get("output_tokens") or 0) for r in perception),
        "perception_cached_tokens": sum(int(r.get("cached_input_tokens") or 0) for r in perception),
    }
    mismatches = {
        key: {"legacy": legacy.get(key), "ledger": value}
        for key, value in expected.items()
        if key in legacy and int(legacy.get(key) or 0) != value
    }
    if mismatches:
        return Finding(
            "legacy_counters",
            False,
            f"{len(mismatches)} counters in the legacy summary.cost block no "
            "longer describe the calls in the ledger",
            mismatches,
        )
    return Finding(
        "legacy_counters",
        True,
        "the legacy summary.cost counters match the ledger call for call; its "
        "null price is a pinned contract, not a disagreement about this run",
        {"legacy_estimated_cost_usd": legacy.get("estimated_cost_usd"),
         "legacy_unpriced_models": legacy.get("unpriced_models"),
         "note": "these two fields are required to look this way by "
                 "core/grade_payload.py and are deliberately not compared"},
    )


def describe_quality(grade: dict[str, Any]) -> dict[str, Any]:
    """Score context. Never decides the exit code -- see the module docstring."""
    summary = grade.get("summary") or {}
    return {
        "note": "reported as context only; a low score is not a receipt failure",
        "run_status": grade.get("run_status"),
        "graded_at": grade.get("graded_at"),
        "task_count": _first_present(summary, "task_count", "total_tasks"),
        "mean_score": _first_present(summary, "mean_score", "average_score"),
    }


def verify(grade_path: Path) -> tuple[list[Finding], dict[str, Any]]:
    grade = json.loads(grade_path.read_text(encoding="utf-8"))
    receipt = (grade.get("summary") or {}).get("grading_cost") or {}

    findings: list[Finding] = []
    sidecar_finding, ledger_path = check_sidecar(grade, grade_path)
    findings.append(sidecar_finding)

    context: dict[str, Any] = {
        "grade_file": grade_path.name,
        "grader_source_hash": grade.get("grader_source_hash"),
        "receipt_status": receipt.get("status"),
        "receipt_estimated_cost_usd": receipt.get("estimated_cost_usd"),
        "quality": describe_quality(grade),
    }

    if ledger_path is None:
        return findings, context

    rows = _load_jsonl(ledger_path)
    calls = [row for row in rows if row.get("record_type", "call") == "call"]
    runtime = [row for row in rows if row.get("record_type") == "runtime"]
    settled = [row for row in calls if row.get("state") == STATE_SETTLED]
    context["ledger_rows"] = len(rows)
    context["call_rows"] = len(calls)
    context["runtime_rows"] = len(runtime)
    context["settled_rows"] = len(settled)

    findings.append(check_identity(grade, calls))
    findings.append(check_no_double_billing(calls))
    findings.append(check_all_calls_settled(calls))
    findings.append(check_usage_reconciles(receipt, settled))
    findings.append(check_usage_containment(settled))
    findings.append(check_cost_reconciles(receipt, settled))
    findings.append(check_components_reconcile(receipt, settled))
    findings.append(check_price_table(receipt, settled))
    findings.append(check_partial_cause(receipt, settled))
    findings.append(check_task_coverage(grade, settled))
    findings.append(check_legacy_counters(grade, settled))
    return findings, context


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("grade_json", type=Path, help="path to a published grade JSON")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    if not args.grade_json.exists():
        print(f"no such grade file: {args.grade_json}", file=sys.stderr)
        return 2

    findings, context = verify(args.grade_json)
    failed = [finding for finding in findings if not finding.ok]

    if args.json:
        print(
            json.dumps(
                {
                    "verdict": "pass" if not failed else "fail",
                    "context": context,
                    "findings": [finding.as_dict() for finding in findings],
                },
                indent=2,
                ensure_ascii=False,
                sort_keys=False,
            )
        )
    else:
        print(f"grade file : {context['grade_file']}")
        print(f"fingerprint: {context.get('grader_source_hash')}")
        print(f"receipt    : {context.get('receipt_status')} "
              f"({context.get('receipt_estimated_cost_usd')})")
        print(f"ledger     : {context.get('ledger_rows', 0)} rows "
              f"({context.get('settled_rows', 0)} settled calls, "
              f"{context.get('runtime_rows', 0)} runtime)")
        print()
        for finding in findings:
            mark = "PASS" if finding.ok else "FAIL"
            print(f"[{mark}] {finding.check}: {finding.detail}")
        print()
        print(f"score context (not a pass/fail input): {context['quality']}")
        print()
        print("VERDICT: pass" if not failed else f"VERDICT: fail ({len(failed)} checks)")

    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
