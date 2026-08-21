#!/usr/bin/env python3
"""Recompute ``summary.wow`` for grade JSONs written before it was emitted.

Every grade file on disk carries a ``summary.wow`` block whose four analytic
fields -- ``by_sector``, ``by_rubric_category``, ``score_density_histogram``
and ``rubric_severity_curve`` -- are empty, so the dashboard's sector heatmap,
severity curve and score histogram have nothing to draw. The five scalar rates
next to them are populated, which is why the gap is easy to miss.

Nothing needs re-grading. Each field is a pure function of the ``tasks`` array
already in the file, and ``step8_grade._compute_summary`` is that function.
This script calls it on the file's own tasks and copies the recomputed ``wow``
block back in.

Two fields will still come back empty, and that is correct:

``by_rubric_category``
    GDPVal rubric items have an id, a criterion string and a weight, and
    nothing that groups them into categories. ``step8_grade`` leaves this
    empty on purpose rather than inventing a taxonomy and presenting it as
    measurement. ``SectorHeatmap.tsx`` already falls back to the per-sector
    rates.

``rubric_severity_curve`` on pre-sign-aware files
    The curve counts ``model_did_right``, which grades written before PR1
    task 100 do not carry. Without it every point reads 0.0 and the chart
    asserts a total failure that never happened. A scalar rate can absorb a
    missing field; a curve cannot, because its shape is the claim.

The safety property this script enforces: **no published number changes.**

That is not automatic, and the first cut of this script got it wrong. Six of
the seventeen files on disk were graded under semantics the current
summariser no longer reproduces. Recomputing their whole ``wow`` block moves
published rates:

* the four pre-sign-aware ``__v1.json`` files carry no ``model_did_right``,
  so ``critical_item_pass_rate`` recomputes to ``0.0`` against a published
  ``0.42`` / ``0.52`` / ``1.0`` -- a total-failure claim that never happened;
* the two ``rubric_v2_tools`` files drift by roughly a point
  (``0.501 -> 0.485``, ``0.4232 -> 0.4338``).

So the rule is per-file, not global: **a file's semantics-dependent
breakdowns are written only when the current summariser reproduces that
file's five published scalar rates exactly.** Agreement is the evidence that
the same code understands the same file. Where it disagrees, only
``score_density_histogram`` is written -- it is a bucket count over the
per-task ``pct`` values already published in the file, so it carries no
semantic assumption at all.

Everything outside ``summary.wow``, and the five scalar rates inside it, are
compared before and after; the file is left untouched if any of it would
move. Keys already present in ``wow`` that ``_compute_summary`` does not
produce (``_v2sm_*``, written by ``backfill_sign_aware.py``) are preserved.

Dry-run by default. Pass ``--apply`` to write.
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "batch-runner"))

from step8_grade import _compute_summary  # noqa: E402

# Legacy demo data, not a real grading run. 103-backfill-existing-grades.md
# excludes it by name, and it carries no `wow` block at all to bring forward.
EXCLUDED = {"dummy_gpt5_baseline.json"}

ANALYTIC_FIELDS = (
    "by_sector",
    "by_rubric_category",
    "score_density_histogram",
    "rubric_severity_curve",
)

#: Published rates. These must be byte-identical before and after, always.
SCALAR_RATES = (
    "rubric_item_coverage_avg",
    "critical_item_pass_rate",
    "precheck_pass_rate",
    "judge_pass_rate",
    "judge_error_rate",
)

#: A bucket count over the per-task ``pct`` values already published in the
#: file. No sign-awareness, no item semantics, nothing that a change in
#: grading criteria could move. Safe to write even where the summariser and
#: the file disagree about everything else.
SEMANTICS_FREE_FIELDS = ("score_density_histogram",)


def _is_empty(value: object) -> bool:
    return value is None or (
        isinstance(value, (list, dict, str)) and len(value) == 0
    )


def _filled(wow: dict) -> int:
    return sum(1 for f in ANALYTIC_FIELDS if not _is_empty(wow.get(f)))


def backfill_one(path: Path, apply: bool) -> dict:
    """Return a report for one file; write it only when ``apply`` is set."""
    original_text = path.read_text()
    doc = json.loads(original_text)

    tasks = doc.get("tasks")
    summary = doc.get("summary")
    if not isinstance(tasks, list) or not isinstance(summary, dict):
        return {"path": path.name, "status": "skipped", "reason": "no tasks/summary"}
    old_wow = summary.get("wow")
    if not isinstance(old_wow, dict):
        return {"path": path.name, "status": "skipped", "reason": "no summary.wow"}

    before_filled = _filled(old_wow)

    # Recompute from the file's own tasks. `unpriced_models` only affects the
    # `cost` block, which this script never reads.
    recomputed = _compute_summary(copy.deepcopy(tasks))["wow"]

    # Does the current summariser still reproduce this file's published rates?
    # That agreement is the whole licence for writing its derived breakdowns:
    # by_sector and rubric_severity_curve are built from the same counters as
    # these scalars, so if the scalars disagree the breakdowns are describing
    # a grading semantics this file was never graded under.
    diverged = [k for k in SCALAR_RATES if old_wow.get(k) != recomputed.get(k)]
    writable = SEMANTICS_FREE_FIELDS if diverged else ANALYTIC_FIELDS

    new_wow = dict(old_wow)  # keep _v2sm_* and anything else non-standard
    for field in writable:
        new_wow[field] = recomputed[field]

    if new_wow == old_wow:
        return {
            "path": path.name,
            "status": "unchanged",
            "before_filled": before_filled,
            "after_filled": before_filled,
            "diverged": diverged,
        }

    candidate = copy.deepcopy(doc)
    candidate["summary"]["wow"] = new_wow

    # Guard 1: nothing outside summary.wow moved. Compared on the parsed
    # documents with `wow` excised from both, so key order and formatting can
    # neither mask a real change nor invent a false one.
    a, b = copy.deepcopy(doc), copy.deepcopy(candidate)
    a["summary"].pop("wow", None)
    b["summary"].pop("wow", None)
    if a != b:
        return {
            "path": path.name,
            "status": "ABORTED",
            "reason": "a field outside summary.wow would change",
        }

    # Guard 2: no published rate inside wow moved. The first cut of this
    # script lacked exactly this check and would have republished four files'
    # critical_item_pass_rate as 0.0.
    moved = [k for k in SCALAR_RATES if old_wow.get(k) != new_wow.get(k)]
    if moved:
        return {
            "path": path.name,
            "status": "ABORTED",
            "reason": f"published rate would change: {moved}",
        }

    changed = sorted(
        f for f in ANALYTIC_FIELDS if old_wow.get(f) != new_wow.get(f)
    )
    still_empty = sorted(f for f in ANALYTIC_FIELDS if _is_empty(new_wow.get(f)))

    if apply:
        # Match the trailing-newline convention of the file as found.
        text = json.dumps(candidate, indent=2, ensure_ascii=False)
        if original_text.endswith("\n"):
            text += "\n"
        path.write_text(text)

    return {
        "path": path.name,
        "status": "written" if apply else "would-write",
        "before_filled": before_filled,
        "after_filled": _filled(new_wow),
        "changed": changed,
        "still_empty": still_empty,
        "diverged": diverged,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "grades_dir",
        nargs="?",
        type=Path,
        default=REPO_ROOT / "data" / "grades",
    )
    ap.add_argument("--apply", action="store_true", help="write files (default: dry run)")
    args = ap.parse_args()

    files = sorted(p for p in args.grades_dir.glob("*.json") if p.name not in EXCLUDED)
    if not files:
        print(f"no grade JSONs under {args.grades_dir}", file=sys.stderr)
        return 1

    reports = [backfill_one(p, args.apply) for p in files]
    aborted = [r for r in reports if r["status"] == "ABORTED"]
    touched = [r for r in reports if r["status"] in ("written", "would-write")]

    for r in reports:
        if r["status"] in ("skipped", "unchanged"):
            print(f"  {r['status']:<12} {r['path'][:70]}"
                  f"{'  (' + r['reason'] + ')' if r.get('reason') else ''}")
            continue
        if r["status"] == "ABORTED":
            print(f"  ABORTED      {r['path'][:70]}  {r['reason']}")
            continue
        print(f"  {r['status']:<12} {r['path'][:70]}")
        print(f"      analytic fields filled: {r['before_filled']}/4 -> {r['after_filled']}/4")
        print(f"      changed: {r['changed']}")
        if r.get("diverged"):
            print(f"      SEMANTICS DIVERGED on {r['diverged']} -- "
                  f"restricted to {list(SEMANTICS_FREE_FIELDS)}")
        if r["still_empty"]:
            print(f"      still empty: {r['still_empty']}")

    print()
    diverged = [r for r in reports if r.get("diverged")]
    print(f"{len(files)} files considered, {len(EXCLUDED)} excluded by name")
    print(f"{len(touched)} {'written' if args.apply else 'would be written'}, "
          f"{len(aborted)} aborted")
    print(f"{len(diverged)} files where the current summariser no longer reproduces "
          f"the published rates (semantics-free fields only)")
    if not args.apply and touched:
        print("\ndry run -- re-run with --apply to write")
    return 1 if aborted else 0


if __name__ == "__main__":
    sys.exit(main())
