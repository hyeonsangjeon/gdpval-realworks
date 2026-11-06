#!/usr/bin/env python3
"""Report a published grade with a diagnostic parity regrade of some of its tasks.

Offline and model-free. Reads two committed grade payloads of ONE inference
run: the published grade (complete scope) and a diagnostic regrade that pinned
the tasks whose deliverable selection changed. It writes a run record, never a
grade file: the published grade stays the published result, and nothing here
is read by scripts/aggregate-grades.mjs.

Four headline numbers are printed for both the published and the merged view,
because none of them is the whole truth on its own:

* judged-only mean      -- step 8's ``avg_score_pct`` rule: tasks with no error
* fixed-denominator mean -- every task counts, a task never judged counts 0
  (the rule docs/run_records/exp035_grading_coverage_220.md fixes)
* both again on ``pct_full_denominator``, which keeps score-excluded rubric
  weight in the denominator

The merged view mixes two grader source hashes, two renderer fingerprints and
two judge draws; the record names all of them next to the numbers.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

IDENTITY_FIELDS = ("experiment_id", "source_inference_repo_id", "source_inference_revision")


def _load(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def _judge_identity(grade: dict[str, Any]) -> tuple:
    judge = grade.get("judge") or {}
    return (judge.get("model"), judge.get("reasoning_effort"), (grade.get("prompt") or {}).get("version"),
            (grade.get("rubric") or {}).get("commit_sha"))


def check_pair(published: dict[str, Any], regrade: dict[str, Any]) -> None:
    for field in IDENTITY_FIELDS:
        if published.get(field) != regrade.get(field):
            raise SystemExit(f"{field} differs: {published.get(field)!r} vs {regrade.get(field)!r}")
    if _judge_identity(published) != _judge_identity(regrade):
        raise SystemExit("judge model, effort, prompt version or rubric commit differs")
    if published.get("run_status") != "final":
        raise SystemExit("the published grade must be a final, complete-scope grade")
    if regrade.get("run_status") not in {"diagnostic", "final"}:
        raise SystemExit("the regrade must be a finished grade (diagnostic or final)")
    ids = [row["task_id"] for row in regrade["tasks"]]
    if regrade.get("expected_task_count") != len(ids):
        raise SystemExit("the regrade is not complete for its own pinned scope")
    order = [row["task_id"] for row in published["tasks"]]
    position = {task_id: index for index, task_id in enumerate(order)}
    if any(task_id not in position for task_id in ids):
        raise SystemExit("the regrade holds a task the published grade does not")
    if [position[task_id] for task_id in ids] != sorted(position[task_id] for task_id in ids):
        raise SystemExit("the regrade's tasks are not in the published task order")


#: Why a task never reached the judge, by the step 2 error_category its
#: published self_report.json row carries (observability.error_category).
INFRASTRUCTURE = {"rate_limited", "transport_error", "runtime_unavailable", "turn_start_failed", "timeout"}


def zero_cause(row: dict[str, Any], categories: dict[str, str]) -> str:
    if row.get("error") == "selection_error":
        return "grader_refusal"
    category = categories.get(row["task_id"])
    if category == "content_filtered":
        return "content_filter"
    if category in INFRASTRUCTURE:
        return "infrastructure"
    return "other_model_side" if category else "unknown"


def headline(rows: list[dict[str, Any]], categories: dict[str, str] | None = None) -> dict[str, Any]:
    judged = [row for row in rows if not row.get("error")]
    errors: dict[str, int] = {}
    for row in rows:
        if row.get("error"):
            key = str(row["error"]) if categories is None else zero_cause(row, categories)
            errors[key] = errors.get(key, 0) + 1

    def mean(values: list[float]) -> float | None:
        return round(sum(values) / len(values), 4) if values else None

    return {
        "tasks": len(rows),
        "judged_tasks": len(judged),
        "unjudged_by_error": dict(sorted(errors.items())),
        "judged_only_mean_pct": mean([float(row["pct"]) for row in judged]),
        "fixed_denominator_mean_pct": mean([float(row["pct"]) if not row.get("error") else 0.0 for row in rows]),
        "judged_only_mean_pct_full_denominator": mean([float(row["pct_full_denominator"]) for row in judged]),
        "fixed_denominator_mean_pct_full_denominator": mean(
            [float(row["pct_full_denominator"]) if not row.get("error") else 0.0 for row in rows]),
    }


def _row_view(row: dict[str, Any]) -> dict[str, Any]:
    selection = row.get("selected_deliverables") or {}
    return {
        "error": row.get("error"),
        "pct": row.get("pct"),
        "pct_full_denominator": row.get("pct_full_denominator"),
        "selection_rule": selection.get("selection_rule"),
        "primary_paths": [target.get("paths") for target in selection.get("primary_targets") or []],
        "score_excluded_items": row.get("score_excluded_items"),
        "judge_call_count": row.get("judge_call_count"),
    }


def merge(published: dict[str, Any], regrade: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    replaced = {row["task_id"]: row for row in regrade["tasks"]}
    merged = [replaced.get(row["task_id"], row) for row in published["tasks"]]
    per_task = [
        {"task_id": row["task_id"], "before": _row_view(row), "after": _row_view(replaced[row["task_id"]])}
        for row in published["tasks"] if row["task_id"] in replaced
    ]
    return merged, per_task


def compare(rows: list[dict[str, Any]], other: dict[str, Any]) -> dict[str, Any]:
    """Both grades on the other grade's task set (for example the fixed five)."""
    ids = [row["task_id"] for row in other["tasks"]]
    mine = {row["task_id"]: row for row in rows}
    missing = [task_id for task_id in ids if task_id not in mine]
    if missing:
        raise SystemExit(f"the comparison grade holds tasks this one does not: {missing}")
    return {
        "task_ids": ids,
        "this": headline([mine[task_id] for task_id in ids]),
        "other": headline(list(other["tasks"])),
        "other_experiment_id": other.get("experiment_id"),
        "other_grader_source_hash": other.get("grader_source_hash"),
        "per_task": [{"task_id": task_id, "this": _row_view(mine[task_id]),
                      "other": _row_view(next(row for row in other["tasks"] if row["task_id"] == task_id))}
                     for task_id in ids],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--published", type=Path, required=True)
    parser.add_argument("--regrade", type=Path, required=True)
    parser.add_argument("--selection-diff", type=Path, default=None,
                        help="selection_diff_against_grade.py output the regrade's scope must equal")
    parser.add_argument("--compare", type=Path, default=None,
                        help="another complete grade whose task set both are also reported on")
    parser.add_argument("--self-report", type=Path, default=None,
                        help="the inference's published self_report.json; splits the zeros by cause")
    parser.add_argument("--json-out", type=Path, required=True)
    args = parser.parse_args()
    categories: dict[str, str] | None = None
    if args.self_report is not None:
        report = json.loads(args.self_report.read_text(encoding="utf-8"))
        categories = {row["task_id"]: str((row.get("observability") or {}).get("error_category") or "")
                      for row in report.get("task_results") or [] if isinstance(row, dict)}
        categories = {task_id: category for task_id, category in categories.items() if category}

    published, published_sha = _load(args.published)
    regrade, regrade_sha = _load(args.regrade)
    check_pair(published, regrade)
    if args.selection_diff is not None:
        planned = json.loads(args.selection_diff.read_text(encoding="utf-8"))
        if planned.get("ordered_task_ids") != [row["task_id"] for row in regrade["tasks"]]:
            raise SystemExit("the regrade's scope is not the recorded selection diff")
        if planned.get("grade_sha256") != published_sha:
            raise SystemExit("the selection diff was computed against another published grade")
    merged, per_task = merge(published, regrade)
    record = {
        "schema": "parity-regrade-record-v1",
        "experiment_id": published["experiment_id"],
        "source_inference_revision": published["source_inference_revision"],
        "published": {"file": args.published.name, "sha256": published_sha,
                      "grader_source_hash": published.get("grader_source_hash"),
                      "renderer_fingerprint": published.get("renderer_fingerprint"),
                      "graded_at": published.get("graded_at"), "headline": headline(published["tasks"], categories)},
        "regrade": {"file": args.regrade.name, "sha256": regrade_sha,
                    "grader_source_hash": regrade.get("grader_source_hash"),
                    "renderer_fingerprint": regrade.get("renderer_fingerprint"),
                    "graded_at": regrade.get("graded_at"), "run_status": regrade.get("run_status"),
                    "task_ids": [row["task_id"] for row in regrade["tasks"]]},
        "merged_headline": headline(merged, categories),
        "per_task": per_task,
        "mixed_identity_caveat": (
            "merged rows come from two grader source hashes, two renderer fingerprints and two judge draws; "
            "it is a parity view, not a published grade"
        ),
    }
    if args.compare is not None:
        other, other_sha = _load(args.compare)
        record["compare"] = {"file": args.compare.name, "sha256": other_sha, **compare(merged, other)}
    args.json_out.write_text(json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"published": record["published"]["headline"], "merged": record["merged_headline"]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
