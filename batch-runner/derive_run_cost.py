#!/usr/bin/env python3
"""Derive per-task cost from the tokens a run measured, when the ledger left it null.

A Codex run uploads a cost ledger with one row per turn, and every dollar
column in it is empty. Not for want of a price. `CostReceiptLedger.settle`
prices the call and then keeps the figure only if nothing is missing:

    cost = None if reasons else priced.cost_usd

and the Codex path attaches `call_reachability_unknown` to every turn
unconditionally, because Codex will not say how many model requests it made
inside one turn. So the reason is always there, and the cost is always dropped
— including for turns whose token totals were reported in full.

Those two unknowns are not the same. Token billing is additive: a turn's total
prices to the same amount however many requests produced it. The request count
stays unknown, and the dollar figure does not have to.

This reads a run's ledger and prices what the run measured, using the
repository's own `price_call` and the committed price table — not a formula
written here — so the arithmetic cannot drift from the arithmetic the ledger
would have used.

What it will not do:

  * It will not write into `model_cost_usd`, in the ledger or anywhere else.
    That column answers "what was charged", and for a run nobody can see an
    invoice for, the only true answer is that it is undetermined. A number
    there reads as the provider's figure no matter how it got in. The derived
    amount travels in its own column, with `derived_cost_is_provider_billed`
    set false and the method that produced it attached to every row.
  * It will not touch the ledger at all; it is opened read-only.
  * It will not price an unmeasured send as zero. A turn whose stream reported
    nothing before it died leaves an open reservation on purpose (see
    `core/codex_runner.py`) — the request went out, and what it consumed is
    unknown. Calling that zero would turn "we don't know" into "it was free",
    so such a task is marked as carrying a floor, not a total.

The result is therefore a lower bound wherever sends went unmeasured, and
`derived_cost_basis` says which of four situations each task is in:

    all_calls_measured               every call reported usage; figure is whole
    floor_unmeasured_sends_excluded  some send unmeasured; figure is a floor
    no_measured_call                 nothing measured; no figure at all
    no_call_made                     never attempted; a true zero

Usage:
    python derive_run_cost.py --ledger workspace/cost_ledger_condition_a.sqlite3
    python derive_run_cost.py --ledger leg0.sqlite3 --ledger leg1.sqlite3 \
        --json derived_cost.json

Several ledgers may be given at once: a relayed run leaves one per leg, and a
task's calls can straddle a handover.
"""

from __future__ import annotations

import argparse
import collections
import json
import sqlite3
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.cost_receipts import (  # noqa: E402
    CallUsage,
    load_receipt_price_table,
    price_call,
)

CENT = Decimal("0.000001")

BASIS_WHOLE = "all_calls_measured"
BASIS_FLOOR = "floor_unmeasured_sends_excluded"
BASIS_NONE = "no_measured_call"
BASIS_UNCALLED = "no_call_made"


class DerivationRefused(RuntimeError):
    """Raised when the inputs cannot support an honest figure."""


def _open_read_only(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise DerivationRefused(f"no ledger at {path}")
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _usage(row: sqlite3.Row) -> CallUsage:
    return CallUsage(
        input_tokens=row["input_tokens"],
        cached_input_tokens=row["cached_input_tokens"],
        output_tokens=row["output_tokens"],
        reasoning_tokens=row["reasoning_tokens"],
        audio_input_tokens=row["audio_input_tokens"],
        audio_output_tokens=row["audio_output_tokens"],
    )


def derive(ledgers: list[Path]) -> dict:
    """Price every measured call in every given ledger, per task."""
    table = load_receipt_price_table()
    tasks: dict[str, dict] = collections.defaultdict(
        lambda: {"cost": Decimal(0), "measured": 0, "unmeasured": 0}
    )
    refused: collections.Counter = collections.Counter()
    fingerprints: set[str] = set()
    total_rows = 0

    for path in ledgers:
        conn = _open_read_only(path)
        try:
            rows = list(conn.execute("select * from cost_calls"))
        finally:
            conn.close()
        for row in rows:
            total_rows += 1
            entry = tasks[row["task_id"]]
            if row["price_table_sha256"]:
                fingerprints.add(row["price_table_sha256"])
            measured = row["state"] == "settled" and row["input_tokens"] is not None
            if not measured:
                # An open reservation, or a settled row with no usage. Either
                # way the tokens are unknown, and unknown is not zero.
                entry["unmeasured"] += 1
                continue
            priced = price_call(
                table.lookup(
                    str(row["provider"]),
                    str(row["resolved_model"] or row["requested_model"] or ""),
                ),
                _usage(row),
            )
            if priced.cost_usd is None:
                # The repository's own pricer declined. Do not second-guess it.
                refused[",".join(priced.missing_reasons)] += 1
                entry["unmeasured"] += 1
                continue
            entry["cost"] += priced.cost_usd
            entry["measured"] += 1

    if fingerprints and len(fingerprints) > 1:
        raise DerivationRefused(
            "these ledgers recorded different price tables "
            f"({sorted(fingerprints)}); pricing them together would mix rates"
        )

    method = (
        "core.cost_receipts.price_call over the run ledger cost_calls table, "
        f"priced with the committed receipt price table (sha256 {table.sha256})"
    )
    if fingerprints:
        recorded = fingerprints.pop()
        if recorded != table.sha256:
            raise DerivationRefused(
                f"the run recorded price table {recorded}, but the table "
                f"committed here is {table.sha256}. Pricing this run with a "
                "table it never saw would produce a figure for a different "
                "set of rates."
            )
        method += "; the same fingerprint the run itself recorded"

    per_task = {}
    total = Decimal(0)
    for task_id, entry in tasks.items():
        if entry["measured"] == 0:
            basis, amount = BASIS_NONE, None
        else:
            basis = BASIS_FLOOR if entry["unmeasured"] else BASIS_WHOLE
            amount = float(entry["cost"].quantize(CENT, rounding=ROUND_HALF_UP))
            total += entry["cost"]
        per_task[task_id] = {
            "derived_cost_usd_from_measured_tokens": amount,
            "derived_cost_basis": basis,
            "derived_cost_calls_measured": entry["measured"],
            "derived_cost_calls_unmeasured": entry["unmeasured"],
            "derived_cost_is_provider_billed": False,
            "derived_cost_method": method,
        }

    measured_calls = sum(e["measured"] for e in tasks.values())
    unmeasured_calls = sum(e["unmeasured"] for e in tasks.values())
    return {
        "per_task": per_task,
        "method": method,
        "price_table_sha256": table.sha256,
        "calls_total": total_rows,
        "calls_measured": measured_calls,
        "calls_unmeasured": unmeasured_calls,
        "tasks_with_a_call": len(tasks),
        "derived_total_usd": float(total.quantize(CENT, rounding=ROUND_HALF_UP)),
        "derived_total_is_a_floor": unmeasured_calls > 0,
        "derived_total_is_provider_billed": False,
        "pricer_refusals": dict(refused),
    }


def uncalled_row(method: str) -> dict:
    """The record for a task no call was ever made for: a true zero."""
    return {
        "derived_cost_usd_from_measured_tokens": 0.0,
        "derived_cost_basis": BASIS_UNCALLED,
        "derived_cost_calls_measured": 0,
        "derived_cost_calls_unmeasured": 0,
        "derived_cost_is_provider_billed": False,
        "derived_cost_method": method,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Price the tokens a run measured, per task, when its ledger left "
            "the dollar column null. Produces a derived figure, never a bill."
        )
    )
    parser.add_argument(
        "--ledger",
        action="append",
        required=True,
        type=Path,
        help="a run's cost_ledger_*.sqlite3 (repeatable: one per relay leg)",
    )
    parser.add_argument(
        "--json",
        type=Path,
        help="write the full per-task result here",
    )
    args = parser.parse_args()

    try:
        result = derive(args.ledger)
    except DerivationRefused as exc:
        print(f"refused: {exc}", file=sys.stderr)
        raise SystemExit(2)

    floor = " (a floor)" if result["derived_total_is_a_floor"] else ""
    print(f"ledgers            : {len(args.ledger)}")
    print(f"price table        : {result['price_table_sha256']}")
    print(
        f"calls              : {result['calls_total']} "
        f"({result['calls_measured']} measured, "
        f"{result['calls_unmeasured']} unmeasured)"
    )
    print(f"tasks with a call  : {result['tasks_with_a_call']}")
    print(f"derived total      : ${result['derived_total_usd']:.4f}{floor}")
    print("this is arithmetic over recorded tokens, not the provider's invoice")
    if result["pricer_refusals"]:
        print(f"pricer refused     : {result['pricer_refusals']}")

    if args.json:
        args.json.write_text(
            json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8"
        )
        print(f"wrote {args.json}")


if __name__ == "__main__":
    main()
