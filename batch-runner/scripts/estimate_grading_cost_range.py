#!/usr/bin/env python3
"""Bound what it will cost to grade a run record, in dollars, without guessing.

The judge `azure:gpt-5.6-sol` sits in `models_deliberately_not_priced`, so no
single figure can be written down. `tasks/rebuilding_grading_task/
PR3_COST_BUDGET.md` settled how to write a *range* instead:

    Azure's published `standard_global` meter, short-context rate as the
    lower bound and long-context rate as the upper bound, cache-write
    excluded (the meter exists but the write-token count is not recorded,
    so including it would be invention).

The rates are read from `azure_published_meters` in the price table, the same
place `tests/test_the_cost_budget_gate_measures_the_pipeline_that_runs.py`
reads them, not restated here. And the rule is checked against the published
run's own totals before it is applied to anything -- see `check_rule()`.

The estimate is then built from two disjoint groups, kept on separate rows
because they are not the same kind of number:

    measured   tasks the reference run actually metered, summed from their
               own per-item judge tokens
    converted  tasks that took 0 judge calls in the reference run and so
               contributed no tokens; priced at the per-rubric-item rate the
               measured group implies

Which tasks reach the judge at all is decided by the same selection replay
`replay_deliverable_selection.py` runs -- the grader's selection stage, called
directly. **The answer is bound to the record passed in.** When the relay adds
a leg the record grows, and every figure below moves with it. Re-run this per
leg rather than quoting an earlier leg's total.

Two known omissions, both of which push the real bill *up*:

    cache-write      write-token counts are recorded nowhere
    perception calls vision/audio usage lands in the payload summary but not
                     in the per-item judge fields, so the per-task sums here
                     exclude it (1.85%-3.49% of a full run, per PR3 section 5)

Usage
-----
    python scripts/estimate_grading_cost_range.py \
        docs/run_records/<record>/deliverable_manifest.json \
        --rubric-revision <40-hex HF commit sha> \
        --reference data/grades/<committed grade payload>.json \
        [--snapshot <already-downloaded snapshot dir>]

Makes no model calls and writes nothing.
"""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.deliverable_selector import select_deliverables  # noqa: E402

from replay_deliverable_selection import load_tasks  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
PRICE_TABLE = REPO / "experiments" / "execution_envelope" / "model_price_table.json"
JUDGE = "gpt-5.6-sol"
LOWER_TIER = "short_context_standard_global"
UPPER_TIER = "long_context_standard_global"
MILLION = Decimal(1_000_000)

# PR3_COST_BUDGET.md section 2, row `sol-220 발행본 src_1c967673eb8081a6`. The
# only two figures this file asserts; everything else is computed.
PUBLISHED_LOWER = "$411.80"
PUBLISHED_UPPER = "$714.14"


def usd(value: Decimal) -> str:
    return f"${value:,.2f}"


def meters() -> tuple[dict, dict]:
    """The published rates, from the table -- not restated in this file."""
    published = json.loads(PRICE_TABLE.read_text(encoding="utf-8"))
    tiers = published["azure_published_meters"][JUDGE]
    return tiers[LOWER_TIER], tiers[UPPER_TIER]


def price(input_tokens: int, cached_tokens: int, output_tokens: int, rate: dict) -> Decimal:
    """Bill a token triple at one published tier.

    Cache-write is excluded on purpose: `gpt-5.6-sol` does bill it, but the
    receipt records no write-token count, so any figure including it would be
    made up rather than measured.
    """
    uncached = Decimal(input_tokens - cached_tokens)
    return (
        uncached / MILLION * Decimal(rate["input"])
        + Decimal(cached_tokens) / MILLION * Decimal(rate["cached_input"])
        + Decimal(output_tokens) / MILLION * Decimal(rate["output"])
    )


def check_rule(reference: dict, low: dict, high: dict) -> None:
    """Reproduce the published bounds before pricing anything with the rule."""
    cost = reference["summary"]["cost"]
    triple = (
        cost["total_input_tokens"],
        cost["total_cached_tokens"],
        cost["total_output_tokens"],
    )
    reproduced = (usd(price(*triple, low)), usd(price(*triple, high)))
    print("=== rule check against the published run ===")
    print(f"  published  {PUBLISHED_LOWER} - {PUBLISHED_UPPER}")
    print(f"  reproduced {reproduced[0]} - {reproduced[1]}")
    if reproduced != (PUBLISHED_LOWER, PUBLISHED_UPPER):
        raise SystemExit(
            "REFUSED: the published meters no longer reproduce the bounds in "
            "PR3_COST_BUDGET.md. Either the meters or the reference payload "
            "changed; resolve that before pricing anything."
        )
    print("  -> the rule holds on this payload; applying it below.\n")


def reaching_tasks(manifest: dict, tasks: dict) -> list[str]:
    """The grader's own selection stage, called directly. No model calls."""
    reaching = []
    for task_id in sorted(manifest):
        selection = select_deliverables(
            task_id=task_id,
            deliverable_files=[f["name"] for f in manifest[task_id]],
            reference_files=tasks[task_id].reference_files,
            instruction=tasks[task_id].prompt,
            rubric_items=tasks[task_id].rubric_items,
        )
        if selection.selection_status == "ok":
            reaching.append(task_id)
    return reaching


def split_by_metering(reaching, reference: dict) -> tuple[dict, dict, list[str]]:
    """Sort the reaching tasks into three states that must not be merged.

    measured   the reference metered it; its own tokens are summed
    converted  the reference took 0 judge calls on it, so it has no tokens
    absent     it is not in the reference at all -- no token history, which is
               a different state from "metered at zero" and is priced in
               neither row rather than zero-filled into one
    """
    measured = {"tasks": 0, "items": 0, "input": 0, "cached": 0, "output": 0}
    converted = {"tasks": 0, "items": 0}
    absent: list[str] = []

    by_task = {row["task_id"]: row for row in reference["tasks"]}
    for task_id in sorted(reaching):
        row = by_task.get(task_id)
        if row is None:
            absent.append(task_id)
            continue
        items = row["items"]
        tokens = sum(item.get("judge_input_tokens", 0) or 0 for item in items)
        if tokens == 0:
            converted["tasks"] += 1
            converted["items"] += len(items)
            continue
        measured["tasks"] += 1
        measured["items"] += len(items)
        measured["input"] += tokens
        measured["cached"] += sum(i.get("judge_cached_tokens", 0) or 0 for i in items)
        measured["output"] += sum(i.get("judge_output_tokens", 0) or 0 for i in items)
    return measured, converted, absent


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="deliverable_manifest.json")
    parser.add_argument("--rubric-revision", required=True)
    parser.add_argument("--snapshot", type=Path, default=None)
    parser.add_argument(
        "--reference",
        type=Path,
        required=True,
        help="committed grade payload graded by the same judge",
    )
    args = parser.parse_args()

    low, high = meters()
    reference = json.loads(args.reference.read_text())
    check_rule(reference, low, high)

    manifest = json.loads(args.manifest.read_text())
    tasks = load_tasks(args.rubric_revision, args.snapshot)
    reaching = reaching_tasks(manifest, tasks)
    print(f"record: {args.manifest.parent.name}")
    print(f"  {len(manifest)} tasks produced deliverables, "
          f"{len(reaching)} of them reach the judge\n")

    measured, converted, absent = split_by_metering(reaching, reference)

    if absent:
        print(f"  !! {len(absent)} reaching task(s) are absent from the reference "
              f"payload and are priced in NEITHER row:")
        for task_id in absent:
            print(f"     {task_id}")
        print()

    triple = (measured["input"], measured["cached"], measured["output"])
    m_low, m_high = price(*triple, low), price(*triple, high)

    # The converted row has no tokens of its own. Priced at what the measured
    # row costs per rubric item -- an extrapolation, which is why it gets its
    # own line instead of being summed into the measured tokens.
    items = Decimal(measured["items"]) if measured["items"] else Decimal(1)
    per_item_low, per_item_high = m_low / items, m_high / items
    c_low = per_item_low * Decimal(converted["items"])
    c_high = per_item_high * Decimal(converted["items"])

    print("=== grading cost range ===")
    print(f"{'':46s} {'tasks':>6s} {'items':>7s}   range")
    print(f"{'metered in the reference, still reaching':46s} "
          f"{measured['tasks']:6d} {measured['items']:7,d}   "
          f"{usd(m_low)} - {usd(m_high)}")
    print(f"{'zero-call in the reference, now reaching':46s} "
          f"{converted['tasks']:6d} {converted['items']:7,d}   "
          f"+{usd(c_low)} - +{usd(c_high)}  (converted, not measured)")
    print(f"{'total':46s} "
          f"{measured['tasks'] + converted['tasks']:6d} "
          f"{measured['items'] + converted['items']:7,d}   "
          f"{usd(m_low + c_low)} - {usd(m_high + c_high)}")
    print(f"\n  per rubric item, measured group: "
          f"${per_item_low:,.4f} - ${per_item_high:,.4f}")
    print(f"  measured tokens: input {measured['input']:,} "
          f"(cached {measured['cached']:,}), output {measured['output']:,}")
    print("\n  Excludes cache-write and perception calls; both push the bill up.")
    print("  Bound to this record. Re-run when the relay adds a leg.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
