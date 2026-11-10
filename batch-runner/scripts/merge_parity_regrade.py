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

When the regrade covers only some tasks, the merged view mixes the two grades'
grader source hashes and renderer fingerprints (where they differ) and two
judge draws; when it covers every task, the merged view is the regrade itself.
``mixed_identity_caveat`` says which, from the two grades, and the record
names both grades' hashes and fingerprints next to the numbers.

Zeros are split by cause (``zero_cause_of``) when the inference's
self_report.json is given (``--self-report``, and ``--compare-self-report`` for
the ``--compare`` grade). A headline without one counts the grade rows' raw
errors instead, under its own key ``unjudged_by_grade_error``, so one key never
holds two vocabularies.
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


# -- why a task scored 0 ----------------------------------------------------
#
# The one cause table for a zero on a fixed denominator. scripts/
# sol_stage_readout.py loads this file for it, so a parity record and a Sol
# stage readout name the same zero the same way. The grade row's error is read
# first: a refusal or any other failure on the grader's side is the grader's,
# whatever the solve did. Otherwise the step 2 error_category of the task's
# published self_report.json row (observability.error_category) says why the
# judge had nothing to see.

#: Every cause zero_cause_of can return.
ZERO_CAUSES = ("grader_refusal", "grader_other", "content_filter", "usd_gate", "sol_gate", "turn_timeout",
               "infrastructure", "unclassified_failure", "model_other")
#: The grade-row error that means the solve left nothing to grade; the solve
#: side then says why.
NOTHING_TO_GRADE = frozenset({"no_deliverables"})
#: sol_batch_controls.USD_CEILING_REACHED: the solve gate refused the attempt
#: because the run's solve budget was spent.
USD_GATE = frozenset({"usd_ceiling_reached"})
#: sol_batch_controls.WINDOW_MISMATCH and GATE_UNVERIFIED: the Sol harness
#: refused the attempt before it started (the served context window was not
#: 1,000,000 earlier in the run, or the gate could not read the task's ledger
#: rows). Neither is the model's; both are counted with infrastructure.
SOL_GATE = frozenset({"sol_batch_context_window_mismatch", "sol_batch_gate_unverified"})
#: Causes whose last attempt never started: on a fixed denominator they are
#: 0, but they are no sample of what an attempt costs or takes.
NOT_ATTEMPTED = frozenset({"usd_gate", "sol_gate"})
#: The provider's or the runner's faults, not the model's (core/execution_errors.py
#: and core/codex_runner.py vocabularies).
INFRASTRUCTURE = frozenset({"rate_limited", "turn_start_failed", "runtime_unavailable", "runtime_start_failed",
                            "session_start_failed", "transport_error", "workspace_error", "out_of_memory"})
#: The runner's fallback when a failure names no cause: reported apart, never
#: counted for or against the model.
UNCLASSIFIED = frozenset({"turn_failed", "execution_error"})
#: A turn that ran past its wall clock. Either side's (a slow deployment or a
#: long answer), so it is neither infrastructure nor the model's and is
#: reported on its own.
TURN_TIMEOUT = frozenset({"timeout"})


def zero_cause_of(grade_error: Any, error_category: Any) -> str:
    """Why a task the judge did not mark scored 0, as one of :data:`ZERO_CAUSES`."""
    if grade_error == "selection_error":
        return "grader_refusal"
    if grade_error and grade_error not in NOTHING_TO_GRADE:
        return "grader_other"
    if error_category == "content_filtered":
        return "content_filter"
    if error_category in USD_GATE:
        return "usd_gate"
    if error_category in SOL_GATE:
        return "sol_gate"
    if error_category in TURN_TIMEOUT:
        return "turn_timeout"
    if error_category in INFRASTRUCTURE:
        return "infrastructure"
    if error_category in UNCLASSIFIED:
        return "unclassified_failure"
    # A success that left nothing, a model mismatch, or no category at all.
    return "model_other"


def zero_cause(row: dict[str, Any], categories: dict[str, str]) -> str:
    return zero_cause_of(row.get("error"), categories.get(row["task_id"]))


def headline(rows: list[dict[str, Any]], categories: dict[str, str] | None = None) -> dict[str, Any]:
    """The four means and the unjudged rows, counted by zero cause when ``categories`` is given.

    Without ``categories`` the unjudged rows are counted by the grade row's raw
    error, under ``unjudged_by_grade_error`` instead of ``unjudged_by_error``:
    the two vocabularies overlap in name only (``no_deliverables`` is not a cause).
    """
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
        "unjudged_by_error" if categories is not None else "unjudged_by_grade_error": dict(sorted(errors.items())),
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


def compare(rows: list[dict[str, Any]], other: dict[str, Any], categories: dict[str, str] | None = None,
            other_categories: dict[str, str] | None = None) -> dict[str, Any]:
    """Both grades on the other grade's task set (for example the fixed five).

    ``categories`` are this experiment's error categories, ``other_categories``
    the other grade's inference's; each side's zeros are split by its own.
    """
    ids = [row["task_id"] for row in other["tasks"]]
    mine = {row["task_id"]: row for row in rows}
    missing = [task_id for task_id in ids if task_id not in mine]
    if missing:
        raise SystemExit(f"the comparison grade holds tasks this one does not: {missing}")
    return {
        "task_ids": ids,
        "this": headline([mine[task_id] for task_id in ids], categories),
        "other": headline(list(other["tasks"]), other_categories),
        "other_experiment_id": other.get("experiment_id"),
        "other_grader_source_hash": other.get("grader_source_hash"),
        "per_task": [{"task_id": task_id, "this": _row_view(mine[task_id]),
                      "other": _row_view(next(row for row in other["tasks"] if row["task_id"] == task_id))}
                     for task_id in ids],
    }


_COUNT = {1: "one", 2: "two"}


def _counted(count: int, noun: str, plural: str) -> str:
    return f"{_COUNT[count]} {noun if count == 1 else plural}"


def identity_caveat(published: dict[str, Any], regrade: dict[str, Any]) -> str:
    """Where the merged rows come from, read from the two grades rather than assumed.

    A regrade of every published task leaves no published row, so the merged
    view is the regrade itself: one grader source hash, one renderer
    fingerprint and one judge draw. Otherwise the merged rows span both grades'
    judge draws, and their hashes and fingerprints are counted as they are.
    """
    regraded = {row["task_id"] for row in regrade["tasks"]}
    if all(row["task_id"] in regraded for row in published["tasks"]):
        renderer = "one renderer fingerprint" if regrade.get("renderer_fingerprint") else (
            "no recorded renderer fingerprint")
        return (f"the regrade replaces every published row, so the merged view is the regrade itself "
                f"(run_status {regrade.get('run_status')}): one grader source hash, {renderer} and one judge draw")
    hashes = len({published.get("grader_source_hash"), regrade.get("grader_source_hash")})
    fingerprints = [published.get("renderer_fingerprint"), regrade.get("renderer_fingerprint")]
    if any(fingerprints):
        renderer = _counted(len({json.dumps(fingerprint, sort_keys=True) for fingerprint in fingerprints}),
                            "renderer fingerprint", "renderer fingerprints")
    else:
        renderer = "no recorded renderer fingerprint"
    return (f"merged rows come from {_counted(hashes, 'grader source hash', 'grader source hashes')}, "
            f"{renderer} and two judge draws; it is a parity view, not a published grade")


#: self_report.json ``meta`` field -> the grade field that names the same inference.
SELF_REPORT_IDENTITY = (("experiment_id", "experiment_id"), ("source_repo_id", "source_inference_repo_id"))


def _categories(path: Path, grade: dict[str, Any], option: str) -> dict[str, str]:
    """task_id -> step 2 error_category from a published self_report.json (empty categories dropped).

    Refused unless the report names the inference ``grade`` was made from: a
    report of another run would relabel this grade's zeros without a sound.
    """
    report = json.loads(path.read_text(encoding="utf-8"))
    meta = report.get("meta") or {}
    for field, grade_field in SELF_REPORT_IDENTITY:
        if meta.get(field) != grade.get(grade_field):
            raise SystemExit(f"{option} is another inference's report: meta.{field} {meta.get(field)!r}, "
                             f"grade {grade_field} {grade.get(grade_field)!r}")
    categories = {row["task_id"]: str((row.get("observability") or {}).get("error_category") or "")
                  for row in report.get("task_results") or [] if isinstance(row, dict)}
    return {task_id: category for task_id, category in categories.items() if category}


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
    parser.add_argument("--compare-self-report", type=Path, default=None,
                        help="the --compare grade's inference self_report.json; splits its zeros by cause")
    parser.add_argument("--json-out", type=Path, required=True)
    args = parser.parse_args()
    if args.compare_self_report is not None and args.compare is None:
        raise SystemExit("--compare-self-report needs --compare")
    published, published_sha = _load(args.published)
    regrade, regrade_sha = _load(args.regrade)
    check_pair(published, regrade)
    other, other_sha = _load(args.compare) if args.compare is not None else (None, None)
    categories = (_categories(args.self_report, published, "--self-report")
                  if args.self_report is not None else None)
    other_categories = (_categories(args.compare_self_report, other, "--compare-self-report")
                        if args.compare_self_report is not None else None)
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
        "mixed_identity_caveat": identity_caveat(published, regrade),
    }
    if other is not None:
        record["compare"] = {"file": args.compare.name, "sha256": other_sha,
                             **compare(merged, other, categories, other_categories)}
    args.json_out.write_text(json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"published": record["published"]["headline"], "merged": record["merged_headline"]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
