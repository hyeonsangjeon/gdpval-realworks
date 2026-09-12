#!/usr/bin/env python3
"""Answer "where is this round, against the fixed 220?" as data, not prose.

A relay round leaves one run record per leg. Each record is complete about its
own leg and says nothing about the round: leg 3 reports 58/220 and leg 4 reports
102/220, and neither can say whether those are 160 tasks or 102. The answer has
lived in hand-reconciled prose in three ``report.md`` files, which is fine for a
reader and useless as a check -- nothing recomputes it when a leg lands.

Two facts make the round arithmetic non-obvious, and both are easy to get wrong
in the same direction:

**Coverage unions, money adds.** exp035 grew two lineages over the same fixed
220 (leg 3 started from scratch instead of resuming, so it re-solved leg 0's
45). Those 45 are one task each for coverage and two payments each for cost.
Adding coverage gives 147 of 220, which is false; deduplicating cost gives
$41.78 for a round that spent $56.17, which is also false.

**A resumed leg's record already contains its predecessors.** Leg 4's record was
built with leg 3's ledger, so it carries all 102 tasks and $41.7784 -- the whole
lineage, not leg 4's share. Summing the legs of one lineage double-counts
everything they share. Only the *final* leg of each lineage may be summed.

So the roll-up takes the final leg per lineage for the figures, uses every leg
for the inheritance checks, and refuses rather than guessing when the inputs
cannot support a single round state.

What it refuses
---------------
- Records disagreeing about the fixed task list (id set **or** order).
- Legs of one lineage where a later leg lost, or silently changed, a task an
  earlier leg had already settled. That is the resume defect this round was
  chasing; it must fail loudly, not average out.
- A surviving lineage that does not cover every task a superseded lineage
  reached. A single round state would quietly drop those tasks.
- Ledger-derived and record-derived totals that disagree by more than a cent.

What it will not do
-------------------
It never invents a cost. A task with no measured call keeps ``null``, and a
round total carrying any such task is reported as a floor. Without ``--ledger``
the cross-check is reported as not performed -- not as agreement.

Offline: reads committed JSON, plus sqlite ledgers when given. No network, no
model call.

    python scripts/roll_up_round.py \\
        --leg A:34571840967:docs/run_records/exp035_run34571840967_partial \\
        --leg B:34603033098:docs/run_records/exp035_run34603033098_partial \\
        --leg B:34631861765:docs/run_records/exp035_run34631861765_partial \\
        --surviving B \\
        --ledger /tmp/relay/34571840967/workspace/cost_ledger_condition_a.sqlite3 \\
        --ledger /tmp/relay/34603033098/workspace/cost_ledger_condition_a.sqlite3 \\
        --ledger /tmp/relay/34631861765/.../cost_ledger_condition_a.sqlite3 \\
        -o docs/run_records/round_state.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class RollUpRefused(RuntimeError):
    """The inputs cannot support a single round state. Say so; do not guess."""


#: Fields a later leg inherits verbatim. If a leg resumed correctly, every one
#: of these is byte-identical to what the predecessor recorded. Cost fields are
#: deliberately absent: a later leg is built with more ledgers than its
#: predecessor had, so an inherited task's cost may legitimately gain precision.
INHERITED_FIELDS = (
    "status",
    "outcome",
    "reason",
    "attempts",
    "deliverable_file_count",
    "deliverable_bytes",
)


class Leg:
    """One run record, with the lineage and run it belongs to."""

    def __init__(self, lineage: str, run_id: str, directory: Path) -> None:
        self.lineage = lineage
        self.run_id = run_id
        self.directory = directory
        outcomes = directory / "outcomes.json"
        if not outcomes.is_file():
            raise RollUpRefused(f"{outcomes} does not exist")
        self.rows: list[dict[str, Any]] = json.loads(outcomes.read_text())
        self.by_task = {row["task_id"]: row for row in self.rows}
        if len(self.by_task) != len(self.rows):
            raise RollUpRefused(f"{outcomes} repeats a task id")
        self.attempted = {
            row["task_id"] for row in self.rows if row.get("outcome") != "never_started"
        }

    @property
    def label(self) -> str:
        return f"lineage {self.lineage} run {self.run_id}"

    def task_list_digest(self) -> str:
        """Id **and** order. Two lists with the same ids in a different order
        are two different task lists: ``n`` is what every report counts by."""
        joined = "\n".join(f"{row['n']}\t{row['task_id']}" for row in self.rows)
        return hashlib.sha256(joined.encode()).hexdigest()


def _cost(row: dict[str, Any]) -> Decimal | None:
    amount = row.get("derived_cost_usd_from_measured_tokens")
    return None if amount is None else Decimal(str(amount))


def _outcome(row: dict[str, Any]) -> str:
    """What one leg concluded about one task, at failure-reason granularity.

    ``status`` alone collapses every failure into ``error``, which hides the
    thing worth seeing when two lineages solved the same task: a task can keep
    its status and still change *why* it ended.
    """
    if row["status"] == "success":
        return "success"
    return row.get("reason") or row["status"]


def _check_fixed_task_list(legs: list[Leg]) -> dict[str, Any]:
    digests = {leg.task_list_digest() for leg in legs}
    if len(digests) > 1:
        detail = ", ".join(f"{leg.label}={leg.task_list_digest()[:12]}" for leg in legs)
        raise RollUpRefused(
            "these records do not describe the same fixed task list "
            f"({detail}). Rolling them up would count two different "
            "benchmarks as one."
        )
    counts = {len(leg.rows) for leg in legs}
    if len(counts) > 1:  # pragma: no cover - a digest match implies this
        raise RollUpRefused(f"records hold different row counts: {sorted(counts)}")
    return {
        "task_count": len(legs[0].rows),
        "sha256_of_position_and_id": digests.pop(),
        "identical_across_every_record": True,
    }


def _check_inheritance(legs_in_order: list[Leg]) -> list[dict[str, Any]]:
    """Within one lineage, a later leg must keep everything an earlier one settled.

    Losing an inherited task means the resume dropped work that was paid for;
    changing one means two records disagree about the same attempt. Both are
    findings, not noise, so both stop the roll-up.
    """
    checks: list[dict[str, Any]] = []
    for earlier, later in zip(legs_in_order, legs_in_order[1:]):
        lost = sorted(earlier.attempted - later.attempted)
        if lost:
            raise RollUpRefused(
                f"{later.label} does not carry {len(lost)} task(s) that "
                f"{earlier.label} had already attempted (first: {lost[0]}). "
                "A resumed leg that loses settled work cannot be rolled up "
                "with the leg it lost it from."
            )
        changed = []
        for task_id in sorted(earlier.attempted):
            before, after = earlier.by_task[task_id], later.by_task[task_id]
            for field in INHERITED_FIELDS:
                if before.get(field) != after.get(field):
                    changed.append(
                        {
                            "task_id": task_id,
                            "field": field,
                            "earlier": before.get(field),
                            "later": after.get(field),
                        }
                    )
        if changed:
            raise RollUpRefused(
                f"{later.label} records {len(changed)} difference(s) from "
                f"{earlier.label} on tasks it inherited rather than re-ran "
                f"(first: {changed[0]}). Two records disagree about one attempt."
            )
        checks.append(
            {
                "earlier": earlier.label,
                "later": later.label,
                "tasks_inherited": len(earlier.attempted),
                "tasks_lost": 0,
                "inherited_rows_identical": True,
                "fields_compared": list(INHERITED_FIELDS),
                "tasks_added_by_the_later_leg": len(later.attempted - earlier.attempted),
            }
        )
    return checks


def _lineage_totals(final: Leg) -> dict[str, Any]:
    """Everything one lineage holds, read off its final leg alone."""
    priced = Decimal(0)
    unpriced_tasks = 0
    files = 0
    byte_total = 0
    outcomes: dict[str, int] = {}
    reasons: dict[str, int] = {}
    for row in final.rows:
        if row["task_id"] not in final.attempted:
            continue
        outcomes[row["status"]] = outcomes.get(row["status"], 0) + 1
        if row.get("reason"):
            reasons[row["reason"]] = reasons.get(row["reason"], 0) + 1
        files += row.get("deliverable_file_count") or 0
        byte_total += row.get("deliverable_bytes") or 0
        amount = _cost(row)
        if amount is None:
            unpriced_tasks += 1
        else:
            priced += amount
    return {
        "final_leg": final.label,
        "tasks_attempted": len(final.attempted),
        "status_counts": dict(sorted(outcomes.items())),
        "failure_reasons": dict(sorted(reasons.items())),
        "deliverable_files": files,
        "deliverable_bytes": byte_total,
        "derived_cost_usd": float(priced),
        "tasks_with_no_derivable_cost": unpriced_tasks,
        "derived_cost_is_a_floor": unpriced_tasks > 0,
    }


def _side(leg: Leg, task_ids: list[str]) -> dict[str, Any]:
    """What one lineage spent on a set of tasks, read off its final leg."""
    priced = Decimal(0)
    unpriced = 0
    turns = 0
    infra = 0
    for task_id in task_ids:
        row = leg.by_task[task_id]
        turns += row.get("calls") or 0
        infra += row.get("retries_infrastructure") or 0
        amount = _cost(row)
        if amount is None:
            unpriced += 1
        else:
            priced += amount
    return {
        "lineage": leg.lineage,
        "final_leg": leg.label,
        "turns": turns,
        "infrastructure_retries": infra,
        "derived_cost_usd": float(priced),
        "tasks_with_no_derivable_cost": unpriced,
        "derived_cost_is_a_floor": unpriced > 0,
    }


def _compare_second_attempts(
    survivor: Leg, superseded: list[Leg], duplicated: list[str]
) -> dict[str, Any]:
    """For every task two lineages both solved, what each one concluded.

    ``_check_inheritance`` already refuses when a later leg changes a result an
    earlier leg of the *same* lineage settled. It says nothing about a task two
    *different* lineages each solved from scratch, which is the only place this
    round holds the same task answered twice.
    """
    transitions: dict[str, int] = {}
    changed: list[dict[str, Any]] = []
    for other in superseded:
        for task_id in duplicated:
            if task_id not in other.attempted:
                continue
            before = other.by_task[task_id]
            after = survivor.by_task[task_id]
            step = f"{_outcome(before)} -> {_outcome(after)}"
            transitions[step] = transitions.get(step, 0) + 1
            if _outcome(before) != _outcome(after):
                changed.append(
                    {
                        "n": after["n"],
                        "task_id": task_id,
                        "superseded": {
                            "lineage": other.lineage,
                            "run_id": other.run_id,
                            "outcome": _outcome(before),
                        },
                        "surviving": {
                            "lineage": survivor.lineage,
                            "run_id": survivor.run_id,
                            "outcome": _outcome(after),
                        },
                    }
                )
    compared = sum(transitions.values())
    sides = [_side(leg, duplicated) for leg in [*superseded, survivor]]
    paid_twice = sum(
        (Decimal(str(side["derived_cost_usd"])) for side in sides), Decimal(0)
    )
    return {
        "what_this_is": (
            "the same task answered twice, once per lineage. Coverage counts "
            "it once; both answers are real and both were paid for."
        ),
        "what_this_is_not": (
            "a repeat experiment. These tasks were solved twice because a "
            "dispatch restarted the round, not because a repeat was designed. "
            "The lineages ran different source revisions of batch-runner; "
            "whether that changed the conditions of the model calls has to be "
            "established from those revisions, not assumed from this table."
        ),
        "tasks_compared": compared,
        "same_outcome": compared - len(changed),
        "changed_outcome": len(changed),
        "transitions": dict(sorted(transitions.items())),
        "changed": sorted(changed, key=lambda row: row["n"]),
        "what_a_turn_is": (
            "one ledger row. Codex opens its own model requests inside a turn "
            "and does not report how many, so these are turns, not requests."
        ),
        "spent_per_lineage_on_these_tasks": sides,
        "paid_twice_usd": float(paid_twice),
        "paid_twice_is_a_floor": any(side["derived_cost_is_a_floor"] for side in sides),
    }


def _ledger_cross_check(
    ledgers: list[Path], record_total: Decimal, covered: int
) -> dict[str, Any]:
    if not ledgers:
        return {
            "performed": False,
            "why": "no --ledger given; the record-derived total stands alone",
        }
    from derive_run_cost import derive  # imported late: only this path needs it

    derived = derive(ledgers)
    ledger_total = Decimal(str(derived["derived_total_usd"]))
    # The two paths round in different places -- the records carry a per-task
    # figure already quantized, the ledgers quantize once at the end -- so an
    # exact match would be luck. A cent is far below any figure either path
    # reports, and far above the rounding they can legitimately differ by.
    if abs(ledger_total - record_total) > Decimal("0.01"):
        raise RollUpRefused(
            f"the ledgers price this round at ${ledger_total} but the run "
            f"records sum to ${record_total}. One of them is describing a "
            "different set of calls; the roll-up will not pick a winner."
        )
    if derived["tasks_with_a_call"] != covered:
        raise RollUpRefused(
            f"the ledgers hold calls for {derived['tasks_with_a_call']} tasks "
            f"but the records cover {covered}. A task was paid for and is "
            "missing from the records, or the reverse."
        )
    return {
        "performed": True,
        "ledgers": [
            {
                "read_from": str(p),
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            }
            for p in ledgers
        ],
        "calls_total": derived["calls_total"],
        "calls_measured": derived["calls_measured"],
        "calls_unmeasured": derived["calls_unmeasured"],
        "tasks_with_a_call": derived["tasks_with_a_call"],
        "derived_total_usd": derived["derived_total_usd"],
        "derived_total_is_a_floor": derived["derived_total_is_a_floor"],
        "price_table_sha256": derived["price_table_sha256"],
        "agrees_with_the_run_records": True,
        "difference_from_the_records_usd": float(ledger_total - record_total),
        "why_they_differ_at_all": (
            "the records carry a per-task figure already rounded to the "
            "millionth; the ledgers round once over the whole round. The "
            "difference is that rounding, not a disagreement about calls."
        ),
    }


def roll_up(
    legs: list[Leg], surviving: str, ledgers: list[Path] | None = None
) -> dict[str, Any]:
    if not legs:
        raise RollUpRefused("no legs given")
    lineages: dict[str, list[Leg]] = {}
    for leg in legs:
        lineages.setdefault(leg.lineage, []).append(leg)
    if surviving not in lineages:
        raise RollUpRefused(
            f"--surviving {surviving} names a lineage that has no legs "
            f"(given: {sorted(lineages)})"
        )

    fixed = _check_fixed_task_list(legs)

    checks: list[dict[str, Any]] = []
    for lineage_legs in lineages.values():
        checks.extend(_check_inheritance(lineage_legs))

    finals = {name: group[-1] for name, group in lineages.items()}
    survivor = finals[surviving]

    orphans = sorted(
        {
            task_id
            for name, final in finals.items()
            if name != surviving
            for task_id in final.attempted
        }
        - survivor.attempted
    )
    if orphans:
        raise RollUpRefused(
            f"{len(orphans)} task(s) were reached only by a superseded lineage "
            f"(first: {orphans[0]}). Reporting {surviving} as the round state "
            "would drop them; they need their own record in the roll-up."
        )

    covered = sorted(survivor.attempted)
    duplicated = sorted(
        survivor.attempted.intersection(
            *[final.attempted for name, final in finals.items() if name != surviving]
        )
        if len(finals) > 1
        else []
    )

    per_lineage = {name: _lineage_totals(final) for name, final in finals.items()}
    record_total = sum(
        (Decimal(str(v["derived_cost_usd"])) for v in per_lineage.values()), Decimal(0)
    )
    floor = any(v["derived_cost_is_a_floor"] for v in per_lineage.values())

    survivor_totals = per_lineage[surviving]
    attempted = survivor_totals["tasks_attempted"]
    success = survivor_totals["status_counts"].get("success", 0)
    failed = survivor_totals["status_counts"].get("error", 0)

    per_task = []
    for row in survivor.rows:
        task_id = row["task_id"]
        touched_by = sorted(
            name for name, final in finals.items() if task_id in final.attempted
        )
        per_task.append(
            {
                "n": row["n"],
                "task_id": task_id,
                "sector": row.get("sector"),
                "occupation": row.get("occupation"),
                "round_state": (
                    "never_attempted" if not touched_by else row["status"]
                ),
                "reason": row.get("reason"),
                "deliverable_file_count": row.get("deliverable_file_count") or 0,
                "lineages_that_reached_it": touched_by,
                "solved_more_than_once": len(touched_by) > 1,
                "surviving_record": survivor.label if touched_by else None,
            }
        )

    return {
        "what_this_is": (
            "the state of one relay round against its fixed task list, "
            "rolled up from the committed run records. Coverage unions across "
            "lineages; cost adds. Not a score, not a bill, not a grade."
        ),
        "fixed_task_list": fixed,
        "legs_read": [
            {"lineage": leg.lineage, "run_id": leg.run_id, "record": str(leg.directory)}
            for leg in legs
        ],
        "surviving_lineage": surviving,
        "superseded_lineages": sorted(n for n in finals if n != surviving),
        "inheritance_checks": checks,
        "round_state": {
            "tasks_total": fixed["task_count"],
            "tasks_attempted": attempted,
            "tasks_succeeded": success,
            "tasks_failed": failed,
            "tasks_never_attempted": fixed["task_count"] - attempted,
            "coverage_percent": round(100 * attempted / fixed["task_count"], 1),
            "what_succeeded_means": (
                "produced deliverable files. Nothing here has been graded."
            ),
        },
        "failure_reasons": survivor_totals["failure_reasons"],
        "duplication": {
            "tasks_solved_by_more_than_one_lineage": len(duplicated),
            "tasks_reached_only_by_a_superseded_lineage": 0,
            "why_coverage_does_not_add": (
                "a task two lineages both solved is one task of coverage and "
                "two payments of cost"
            ),
            "outcome_when_solved_again": _compare_second_attempts(
                survivor,
                [final for name, final in finals.items() if name != surviving],
                duplicated,
            ),
        },
        "deliverables": {
            "files": survivor_totals["deliverable_files"],
            "bytes": survivor_totals["deliverable_bytes"],
        },
        "cost": {
            "per_lineage": per_lineage,
            "round_total_usd": float(record_total),
            "round_total_is_a_floor": floor,
            "is_provider_billed": False,
            "excludes": (
                "grading. This counts only the model calls that solved tasks."
            ),
            "spent_on_work_that_was_superseded_usd": float(
                sum(
                    (
                        Decimal(str(v["derived_cost_usd"]))
                        for n, v in per_lineage.items()
                        if n != surviving
                    ),
                    Decimal(0),
                )
            ),
            "ledger_cross_check": _ledger_cross_check(
                list(ledgers or []), record_total, len(covered)
            ),
        },
        "per_task": per_task,
    }


def _parse_leg(spec: str) -> Leg:
    parts = spec.split(":", 2)
    if len(parts) != 3 or not all(parts):
        raise argparse.ArgumentTypeError(
            f"--leg wants LINEAGE:RUN_ID:PATH, got {spec!r}"
        )
    lineage, run_id, path = parts
    return Leg(lineage, run_id, Path(path))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--leg",
        action="append",
        dest="legs",
        required=True,
        type=_parse_leg,
        metavar="LINEAGE:RUN_ID:PATH",
        help="one run record. Repeat; give each lineage's legs oldest first.",
    )
    parser.add_argument(
        "--surviving",
        required=True,
        help="the lineage the relay actually continued",
    )
    parser.add_argument(
        "--ledger",
        action="append",
        dest="ledgers",
        default=[],
        type=Path,
        help="a run's cost ledger, for the independent cost cross-check. The "
        "ledgers live in the run artifacts, not this repository, so the "
        "cross-check needs them downloaded; the coverage figures do not.",
    )
    parser.add_argument("-o", "--output", type=Path, required=True)
    args = parser.parse_args()

    try:
        document = roll_up(args.legs, args.surviving, args.ledgers)
    except RollUpRefused as refusal:
        print(f"REFUSED: {refusal}", file=sys.stderr)
        raise SystemExit(2)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n")

    state = document["round_state"]
    cost = document["cost"]
    print(f"wrote {args.output}")
    print(
        f"  {state['tasks_attempted']}/{state['tasks_total']} attempted "
        f"({state['coverage_percent']}%), {state['tasks_succeeded']} produced "
        f"files, {state['tasks_failed']} failed, "
        f"{state['tasks_never_attempted']} never reached"
    )
    floor = " (a floor)" if cost["round_total_is_a_floor"] else ""
    print(f"  ${cost['round_total_usd']}{floor}, solving only, ungraded")
    if not cost["ledger_cross_check"]["performed"]:
        print("  cost cross-check NOT performed: no --ledger given")


if __name__ == "__main__":
    main()
