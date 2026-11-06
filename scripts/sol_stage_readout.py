#!/usr/bin/env python3
"""Model-free readout of one Sol stage, or the union of several, for the next owner decision.

Joins three published records that no single file holds together: the grade
JSON (scores, selection outcomes, grading time), the stage's self_report.json
(solve status, error category, latency, booked solve USD, deliverable names)
and the committed combined USD journals (grading USD per task). It changes no
grade and no headline: avg_score_pct stays what aggregate-grades.mjs shows.

    python scripts/sol_stage_readout.py \
        --stage exp037_sol_first25 data/grades/<exp037 grade>.json <self_report.json> \
        [--stage exp038_sol_rest195 ...] [--remaining-tasks 195 --remaining-items 9248] [--json out.json]

Every task counts once on the fixed denominator (the stage's task count, or
220 for the union); a task the judge never saw counts 0 and is labelled by why.

Grading USD is read from every journal in data/grades/_combined_usd/<id>/,
which holds every grading process of that experiment: the right set for a
stage's own grade, including its resume chunks. After a regrade of the same
experiment, pass the journals of the grade being read with
``--journals-dir <id> <dir>``.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

#: Solve error categories that are the provider's or the runner's, not the model's
#: (core/execution_errors.py and core/codex_runner.py vocabularies).
INFRASTRUCTURE = frozenset({"rate_limited", "turn_start_failed", "runtime_unavailable", "runtime_start_failed",
                            "session_start_failed", "transport_error", "workspace_error", "out_of_memory"})
#: The runner's fallback when a failure names no cause: reported apart, never
#: counted for or against the model.
UNCLASSIFIED = frozenset({"turn_failed", "execution_error"})
DOCUMENT_EXTENSIONS = frozenset({".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".csv", ".md", ".txt",
                                 ".html", ".htm", ".json", ".eml", ".msg", ".zip"})
EMAIL_EXTENSIONS = frozenset({".eml", ".msg"})
HELPER_EXTENSIONS = frozenset({".py", ".js", ".sh", ".ipynb", ".r", ".ts"})
IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"})
#: grade-run.yml's GRADER_TIME_BUDGET_SEC and step 2's per-leg watchdog.
CHUNK_SECONDS = 20280
LEG_MINUTES = 170
MAX_LEGS = MAX_CHUNKS = 11
#: Pre-registered before exp037 ran (spec2/first25.md); a readout prints which hold.
RULES = {
    "R1": "no grader refusal (selection_error) among tasks that left files",
    "R2": "infrastructure plus unclassified losses at most 2 of 25 (8%)",
    "R3": "projected solve legs for the remainder at most 9 of 11",
    "R4": "projected grading chunks for the remainder at most 9 of 11",
}


def _ext(name: str) -> str:
    dot = name.rfind(".")
    return name[dot:].lower() if dot > name.rfind("/") else ""


def _stem(name: str) -> str:
    base = name.rsplit("/", 1)[-1]
    return base[: base.rfind(".")] if "." in base else base


def journal_usd_by_task(directory: Path) -> dict[str, Decimal]:
    spent: dict[str, Decimal] = defaultdict(Decimal)
    for path in sorted(directory.glob("run-*.combined_usd.jsonl")):
        owner: dict[str, str] = {}
        reserved: dict[str, Decimal] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            if record.get("event") == "reserve":
                owner[record["ticket"]] = record.get("task_id") or "?"
                reserved[record["ticket"]] = Decimal(record["reserve_usd"])
            elif record.get("event") in ("settle", "abandon"):
                spent[owner.get(record.get("ticket"), "?")] += Decimal(record["spent_usd"])
                reserved.pop(record.get("ticket"), None)
        # Reservations that never concluded are spent too (sol_batch_grading._read_journal):
        # the request may have been served and billed after the process died.
        for ticket, amount in reserved.items():
            spent[owner.get(ticket, "?")] += amount
    return dict(spent)


def read_stage(experiment_id: str, grade_path: Path, report_path: Path, journals: Path) -> list[dict]:
    grade = json.loads(grade_path.read_text(encoding="utf-8"))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report["meta"]["experiment_id"] != experiment_id:
        raise SystemExit(f"{report_path} is not {experiment_id}'s self_report.json")
    graded = {task["task_id"]: task for task in grade["tasks"]}
    grading_usd = journal_usd_by_task(journals)
    rows = []
    for solved in report["task_results"]:
        task_id = solved["task_id"]
        marked = graded.get(task_id) or {}
        observability = solved.get("observability") or {}
        files = [str(name) for name in solved.get("deliverable_files") or []]
        judged = (marked.get("judge_call_count") or 0) > 0
        category = observability.get("error_category")
        if judged:
            cause = "judged"
        elif marked.get("error") == "selection_error":
            cause = "grader_refusal"
        elif category == "content_filtered":
            cause = "content_filter"
        elif category == "usd_ceiling_reached":
            cause = "usd_gate"
        elif category in INFRASTRUCTURE:
            cause = "infrastructure"
        elif category in UNCLASSIFIED:
            cause = "unclassified_failure"
        else:
            # A success that left nothing, a turn timeout, a model mismatch.
            cause = "model_other"
        stems: dict[str, set[str]] = defaultdict(set)
        for name in files:
            if _ext(name) in DOCUMENT_EXTENSIONS:
                stems[_stem(name)].add(_ext(name))
        rows.append({
            "stage": experiment_id, "task_id": task_id, "status": solved.get("status"),
            # What marked it: a union is like-for-like only if these agree.
            "grader_source_hash": grade.get("grader_source_hash"),
            "renderer_fingerprint": json.dumps(grade.get("renderer_fingerprint"), sort_keys=True),
            "error_category": category, "cause": cause,
            "pct": float(marked.get("pct") or 0.0) if judged else 0.0,
            "pct_full_denominator": float(marked.get("pct_full_denominator") or 0.0) if judged else 0.0,
            "selection_rule": marked.get("selection_rule"), "selection_error": marked.get("selection_error"),
            "items": len(marked.get("items") or []), "excluded_items": marked.get("score_excluded_items") or 0,
            "solve_seconds": (solved.get("latency_ms") or 0) / 1000,
            "solve_usd": float((observability.get("budget_metrics") or {}).get("conservative_cost_usd") or 0),
            "grading_seconds": (marked.get("grading_wall_time_ms") or 0) / 1000,
            "grading_usd": float(grading_usd.get(task_id, 0)),
            "files": [name.rsplit("/", 1)[-1] for name in files],
            "email_files": sum(_ext(name) in EMAIL_EXTENSIONS for name in files),
            "same_stem_formats": sum(1 for formats in stems.values() if len(formats) > 1),
            "helper_files": sum(_ext(name) in HELPER_EXTENSIONS for name in files),
            "image_files": sum(_ext(name) in IMAGE_EXTENSIONS for name in files),
        })
    return rows


def summarise(rows: list[dict], denominator: int, remaining_tasks: int, remaining_items: int) -> dict:
    judged = [row for row in rows if row["cause"] == "judged"]
    causes = Counter(row["cause"] for row in rows)
    solve = [row["solve_usd"] for row in rows]
    judged_items = sum(row["items"] - row["excluded_items"] for row in judged) or 1
    grading_total = sum(row["grading_usd"] for row in rows)
    per_item = grading_total / judged_items
    rng = random.Random(20261106)
    boot = sorted(sum(rng.choice(solve) for _ in range(remaining_tasks)) for _ in range(2000)) if solve else [0]
    mean_minutes = statistics.mean(row["solve_seconds"] for row in rows) / 60 if rows else 0
    # Tasks that left files are the ones a grade has to mark; a refusal (R1) is
    # a selector defect to fix, not a saving to project.
    judged_share = sum(1 for row in rows if row["files"]) / len(rows) if rows else 0
    grade_seconds_per_item = (sum(row["grading_seconds"] for row in judged) / judged_items) if judged else 0
    legs = math.ceil(remaining_tasks * mean_minutes / LEG_MINUTES) if remaining_tasks else 0
    chunks = math.ceil(remaining_items * judged_share * grade_seconds_per_item / CHUNK_SECONDS) if remaining_items else 0
    with_files = [row for row in rows if row["files"]]
    graders = sorted({(row["stage"], row["grader_source_hash"], row["renderer_fingerprint"]) for row in rows})
    summary = {
        "tasks": len(rows), "denominator": denominator,
        "graders": [{"stage": stage, "grader_source_hash": source, "renderer_fingerprint": json.loads(renderer)}
                    for stage, source, renderer in graders],
        "one_grader": len({source for _, source, _ in graders}) == 1
                      and len({renderer for _, _, renderer in graders}) == 1,
        "score_fixed_denominator": round(sum(row["pct"] for row in rows) / denominator, 2),
        "score_judged_only": round(statistics.mean(row["pct"] for row in judged), 2) if judged else None,
        "score_full_item_denominator": round(sum(row["pct_full_denominator"] for row in rows) / denominator, 2),
        "zeros_by_cause": {cause: count for cause, count in sorted(causes.items()) if cause != "judged"},
        "file_habits": {
            "tasks_with_files": len(with_files),
            "email_files": sum(row["email_files"] for row in rows),
            "same_stem_multi_format_groups": sum(row["same_stem_formats"] for row in rows),
            "helper_files": sum(row["helper_files"] for row in rows),
            "image_files": sum(row["image_files"] for row in rows),
            "selection_rules": dict(Counter(row["selection_rule"] for row in with_files)),
        },
        "usd": {"solve": round(sum(solve), 2), "grading": round(grading_total, 2),
                "solve_per_task_mean": round(statistics.mean(solve), 2) if solve else None,
                "solve_per_task_max": round(max(solve), 2) if solve else None,
                "grading_per_judged_item": round(per_item, 4)},
        "time": {"solve_minutes_per_task_mean": round(mean_minutes, 1),
                 "grading_seconds_per_judged_item": round(grade_seconds_per_item, 1)},
        "projection": {
            "remaining_tasks": remaining_tasks, "remaining_items": remaining_items,
            "solve_usd_mean": round(statistics.mean(solve) * remaining_tasks, 0) if solve else None,
            "solve_usd_p90": round(boot[int(0.9 * len(boot))], 0),
            "grading_usd": round(per_item * remaining_items * judged_share, 0),
            "solve_legs": legs, "grading_chunks": chunks,
        },
    }
    infrastructure = causes.get("infrastructure", 0) + causes.get("unclassified_failure", 0)
    refusals = sum(1 for row in with_files if row["cause"] == "grader_refusal")
    summary["rules"] = {
        "R1": refusals == 0,
        "R2": infrastructure <= math.floor(0.08 * len(rows)),
        "R3": legs <= MAX_LEGS - 2,
        "R4": chunks <= MAX_CHUNKS - 2,
    }
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--stage", nargs=3, action="append", required=True,
                        metavar=("EXPERIMENT_ID", "GRADE_JSON", "SELF_REPORT_JSON"))
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--denominator", type=int, default=None)
    parser.add_argument("--remaining-tasks", type=int, default=0)
    parser.add_argument("--remaining-items", type=int, default=0)
    parser.add_argument("--json", default=None)
    parser.add_argument("--journals-dir", nargs=2, action="append", default=[],
                        metavar=("EXPERIMENT_ID", "DIR"),
                        help="read this stage's grading journals from DIR instead of "
                             "data/grades/_combined_usd/EXPERIMENT_ID")
    args = parser.parse_args(argv)
    overrides = {experiment_id: Path(directory) for experiment_id, directory in args.journals_dir}
    rows: list[dict] = []
    for experiment_id, grade_path, report_path in args.stage:
        journals = overrides.get(experiment_id,
                                 Path(args.repo_root) / "data/grades/_combined_usd" / experiment_id)
        rows += read_stage(experiment_id, Path(grade_path), Path(report_path), journals)
    seen = Counter(row["task_id"] for row in rows)
    if any(count > 1 for count in seen.values()):
        raise SystemExit("a task appears in two stages; a union counts every task once")
    summary = summarise(rows, args.denominator or len(rows), args.remaining_tasks, args.remaining_items)
    document = {"summary": summary, "tasks": rows, "rules": RULES}
    if args.json:
        Path(args.json).write_text(json.dumps(document, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
