#!/usr/bin/env python3
"""Turn a finished V2 stage's shard ledgers into a per-task cost table.

Every paid shard writes ``cost_receipts.sqlite3`` beside its record, and the
collect job downloads all of them. Until this script, nothing read them. The
run therefore had a complete, per-call, append-only account of what it spent
and no way to answer the question the account exists for::

    what did each task cost, and what did the stage cost

That is the deliverable, not a nicety. A stage whose money cannot be split by
task has to be reported as one number or none, and "none" is where a 220-task
run ends up when the reading step was never written.

What this does
--------------

Merges the shards into one ledger and reads it. Nothing is recomputed: the
merge is :meth:`CostReceiptLedger.import_jsonl`, which is keyed on ``call_id``
and so is idempotent, and the amounts come from
:meth:`CostReceiptLedger.receipt_for` and :func:`summarise_receipts` — the same
functions the run itself used. A task that appears in two shards' ledgers is
one task here, and a shard re-uploaded twice changes nothing.

Three populations, kept apart
-----------------------------

A stage's tasks fall into three groups and collapsing them is how a cost
report starts lying:

``in the ledger``
    Something was reserved or settled against this task. Its receipt says what
    that is worth, or why it cannot be said.
``assigned but never reached``
    A shard was told to run it and the ledger has no row for it. It is
    ``not_run`` — not free. A shard killed by its own timeout leaves tasks
    here, and counting them as ``$0`` would make a half-finished stage look
    cheap rather than incomplete.
``never assigned to any shard``
    A shard's record is missing entirely. This is a coverage hole, reported
    here and decided by ``check_agentic_v2_stage_coverage.py``, which is the
    tool that owns pass/fail for a stage.

What the exit code means
------------------------

This tool produces the number; it is not a second gate on the run. It exits
non-zero only when the merge itself cannot be trusted — two shards claiming
different settlements for the same ``call_id``, which
:class:`LedgerIntegrityError` raises and which would make any total arbitrary.
A stage that ran badly, ran partly, or could not be priced still exits 0 and
says so in the file, because "the run went wrong" is the coverage check's
sentence to pass, not this one's.

What it will not do
-------------------

Write a zero it did not measure. ``estimated_cost_usd`` is populated only on a
``complete`` receipt; everywhere else it is null and ``known_cost_usd`` stands
beside it as a **floor**, which is a different claim and is labelled as one.
An unpriced call is ``partial``. A task that ran and made no call at all is
``unavailable``. A task that never ran is ``not_run``. Four different
sentences, none of them "$0.00".

Nothing here calls a model, reads a credential or touches the network.

    cd batch-runner
    python scripts/roll_up_agentic_v2_cost.py \
        --records ../shard-records --stage advance_check_5
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.cost_receipts import (  # noqa: E402
    BUCKET_PROBLEM_SOLVING,
    STATUS_COMPLETE,
    STATUS_UNAVAILABLE,
    CostReceipt,
    CostReceiptLedger,
    LedgerIntegrityError,
    summarise_receipts,
)

ROLLUP_SCHEMA_VERSION = 1

LEDGER_NAME = "cost_receipts.sqlite3"
RECORD_NAME = "run_record.json"


class MergeRefused(RuntimeError):
    """The shards cannot be added up, so no total may be published."""


def find_ledgers(records: Path) -> list[Path]:
    """Every shard ledger under a downloaded artifact tree, in a stable order.

    ``download-artifact`` with a pattern puts each shard in its own directory,
    so the ledgers sit one level down. Searched recursively rather than by a
    fixed depth, because a single-shard run and a re-downloaded tree nest
    differently and neither is wrong.
    """
    return sorted(records.rglob(LEDGER_NAME))


def read_records(records: Path) -> list[dict[str, Any]]:
    """Every shard's ``run_record.json``, skipping what will not parse.

    A record that cannot be read is reported rather than raised on: the
    ledgers are the source of the money, and losing a record costs us the
    cohort list for that shard, not the amounts.
    """
    found: list[dict[str, Any]] = []
    for path in sorted(records.rglob(RECORD_NAME)):
        try:
            payload = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if isinstance(payload, dict):
            payload["_source"] = str(path)
            found.append(payload)
    return found


def _ids(payload: Any, key: str) -> list[str]:
    section = payload if isinstance(payload, dict) else {}
    value = section.get(key)
    return [str(entry) for entry in value] if isinstance(value, list) else []


def cohort_and_assignment(
    records: list[dict[str, Any]]
) -> tuple[list[str], list[str], list[str]]:
    """The stage's whole cohort, what the shards were given, and disagreements.

    The binding is the stage; the shard is this process's slice of it. Both are
    in every record, so a single surviving record is enough to know the whole
    cohort — which is what lets a stage that lost a shard still report how many
    tasks are missing rather than shrinking its own denominator to fit.
    """
    cohorts: dict[str, list[str]] = {}
    assigned: list[str] = []
    for record in records:
        cohort = _ids(record.get("binding"), "task_ids")
        if cohort:
            cohorts[",".join(cohort)] = cohort
        assigned.extend(_ids(record.get("shard"), "task_ids"))

    problems: list[str] = []
    if len(cohorts) > 1:
        problems.append(
            f"the shards do not agree on the cohort: {len(cohorts)} different "
            "task lists are claimed, so the denominator below is the union"
        )
    union: list[str] = []
    for cohort in cohorts.values():
        for task_id in cohort:
            if task_id not in union:
                union.append(task_id)
    return union, sorted(set(assigned)), problems


def merge_ledgers(
    ledgers: list[Path], *, into: Path, run_id: str
) -> tuple[CostReceiptLedger, list[str]]:
    """Fold every shard's rows into one ledger and say what came from where.

    Uses the ledger's own export/import rather than touching SQL, because the
    import is where double-counting is prevented: ``call_id`` is the primary
    key, re-importing a row already present is a no-op, and re-importing it
    with *different* numbers raises rather than picking one.

    Opened deliberately **without** a price table, and this is not the
    oversight it looks like. ``settle`` prices a call when the reply arrives
    and stores the amount and the table's fingerprint on the row;
    :func:`build_receipt` reads the rows' own fingerprints and uses a caller's
    only as a fallback. Handing today's committed table to a ledger full of
    rows settled days ago would put today's fingerprint on money computed under
    another file — which is the one thing the fingerprint exists to make
    impossible. Nothing here re-prices anything.
    """
    merged = CostReceiptLedger(into, run_id=run_id)
    notes: list[str] = []
    with tempfile.TemporaryDirectory() as scratch:
        for index, path in enumerate(ledgers):
            shard = CostReceiptLedger(path, run_id=run_id)
            try:
                exported = Path(scratch) / f"shard-{index}.jsonl"
                digest = shard.export_jsonl(exported)
                calls = shard.call_count()
            finally:
                shard.close()
            try:
                new_rows = merged.import_jsonl(exported)
            except LedgerIntegrityError as clash:
                merged.close()
                raise MergeRefused(
                    f"{path}: two shards settle the same call differently "
                    f"({clash}). No total can be published from these."
                ) from clash
            notes.append(
                f"{path}: {calls} call(s), {new_rows} new to the merge, "
                f"sha256={digest[:16]}"
            )
    return merged, notes


def _task_row(task_id: str, receipt: CostReceipt) -> dict[str, Any]:
    payload = receipt.as_dict()
    return {
        "task_id": task_id,
        "status": payload["status"],
        # Null unless `complete`. `known_cost_usd` beside it is a floor.
        "estimated_cost_usd": payload["estimated_cost_usd"],
        "known_cost_usd": payload["known_cost_usd"],
        "known_cost_is_a_floor_not_a_total": payload["status"] != STATUS_COMPLETE,
        "model_cost_usd": payload["model_cost_usd"],
        "runtime_cost_usd": payload["runtime_cost_usd"],
        "model_calls": payload["model_calls"],
        "usage": payload["usage"],
        "missing_reasons": payload["missing_reasons"],
        "price_table_sha256": payload["price_table_sha256"],
    }


def roll_up(records_dir: Path, *, stage: str, merged_into: Path) -> dict[str, Any]:
    """Everything the collect job needs to state what this stage cost."""
    ledgers = find_ledgers(records_dir)
    records = read_records(records_dir)
    cohort, assigned, problems = cohort_and_assignment(records)

    run_ids = sorted({str(r.get("run_id")) for r in records if r.get("run_id")})
    if len(run_ids) > 1:
        problems.append(
            "the shards carry different run ids "
            f"({', '.join(run_ids)}); their call ids are namespaced by run, so "
            "nothing is double counted, but this is not one run"
        )
    run_id = run_ids[0] if run_ids else f"{stage}-rollup"

    if not ledgers:
        problems.append(
            f"no {LEDGER_NAME} under {records_dir}: this stage published no "
            "account of its spending. That is not the same as having spent "
            "nothing -- if any shard reached the model, it was billed"
        )

    rows: list[dict[str, Any]] = []
    receipts: list[CostReceipt] = []
    in_ledger: list[str] = []
    notes: list[str] = []

    if ledgers:
        merged, notes = merge_ledgers(ledgers, into=merged_into, run_id=run_id)
        try:
            in_ledger = merged.task_ids()
            for task_id in in_ledger:
                receipt = merged.receipt_for(
                    task_id,
                    BUCKET_PROBLEM_SOLVING,
                    # It is in the ledger, so it ran. An empty
                    # problem-solving bucket means nothing could be priced
                    # here, which is `unavailable` -- never `not_run`, and
                    # never a measured zero.
                    when_empty=STATUS_UNAVAILABLE,
                )
                receipts.append(receipt)
                rows.append(_task_row(task_id, receipt))
        finally:
            merged.close()

    never_reached = [task_id for task_id in assigned if task_id not in in_ledger]
    for task_id in never_reached:
        receipt = CostReceipt.not_run()
        receipts.append(receipt)
        rows.append(_task_row(task_id, receipt))

    never_assigned = [task_id for task_id in cohort if task_id not in assigned]
    if never_assigned:
        problems.append(
            f"{len(never_assigned)} task(s) of the {len(cohort)} in this stage "
            "are in no shard record at all; a shard's artifact is missing. "
            "check_agentic_v2_stage_coverage.py owns that verdict"
        )

    total = summarise_receipts(receipts)
    complete = [row for row in rows if row["status"] == STATUS_COMPLETE]

    return {
        "schema_version": ROLLUP_SCHEMA_VERSION,
        "stage": stage,
        "run_id": run_id,
        "read_from": {
            "records_dir": str(records_dir),
            "ledgers": notes,
            "shard_records": len(records),
        },
        "population": {
            "cohort_size": len(cohort),
            "assigned_to_a_shard": len(assigned),
            "in_the_ledger": len(in_ledger),
            "assigned_but_never_reached_the_ledger": never_reached,
            "never_assigned_to_any_shard": never_assigned,
        },
        "tasks": sorted(rows, key=lambda row: row["task_id"]),
        "stage_total": total.as_dict(),
        "accounting": {
            "tasks_with_a_complete_receipt": len(complete),
            "tasks_accounted_for": len(rows),
            "cost_is_fully_accounted": (
                bool(rows) and len(complete) == len(rows)
            ),
            "what_the_total_is": (
                "a total"
                if total.status == STATUS_COMPLETE
                else "a floor: known_cost_usd only, estimated_cost_usd is null"
            ),
        },
        "problems": problems,
    }


def describe(rollup: dict[str, Any]) -> str:
    """The same thing in sentences, for whoever is reading the job log."""
    population = rollup["population"]
    total = rollup["stage_total"]
    lines = [
        f"stage {rollup['stage']}, run {rollup['run_id']}",
        (
            f"  {population['in_the_ledger']} task(s) in the ledger, "
            f"{len(population['assigned_but_never_reached_the_ledger'])} "
            f"assigned and never reached, cohort {population['cohort_size']}"
        ),
        (
            f"  stage total: {total['status']}, "
            f"estimated {total['estimated_cost_usd']}, "
            f"known {total['known_cost_usd']} "
            f"({rollup['accounting']['what_the_total_is']})"
        ),
        (
            f"  {rollup['accounting']['tasks_with_a_complete_receipt']} of "
            f"{rollup['accounting']['tasks_accounted_for']} task(s) carry a "
            "complete receipt"
        ),
    ]
    if total["missing_reasons"]:
        lines.append(f"  why not complete: {', '.join(total['missing_reasons'])}")
    for problem in rollup["problems"]:
        lines.append(f"  ! {problem}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--records",
        required=True,
        type=Path,
        help="the directory every shard's artifact was downloaded into",
    )
    parser.add_argument("--stage", required=True)
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="where to write cost_rollup.json (default: beside --records)",
    )
    parser.add_argument(
        "--json", action="store_true", help="print the roll-up to stdout too"
    )
    args = parser.parse_args(argv)

    out = args.out or (args.records / "cost_rollup.json")
    out.parent.mkdir(parents=True, exist_ok=True)

    try:
        rollup = roll_up(
            args.records,
            stage=args.stage,
            merged_into=out.parent / "cost_receipts_merged.sqlite3",
        )
    except MergeRefused as refused:
        print(f"cost roll-up refused: {refused}", file=sys.stderr)
        return 1

    out.write_text(json.dumps(rollup, indent=2, sort_keys=True))
    print(describe(rollup))
    print(f"written: {out}")
    if args.json:
        print(json.dumps(rollup, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
