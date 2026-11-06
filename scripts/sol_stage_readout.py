#!/usr/bin/env python3
"""Model-free readout of one Sol stage, or the union of several, for the next owner decision.

Joins three published records that no single file holds together: the grade
JSON (scores, selection outcomes, grading time), the stage's self_report.json
(solve status, error category, latency, booked solve USD, deliverable names)
and the committed combined USD journals (grading USD per task). It changes no
grade and no headline: judged-only is step 8's avg_score_pct rule (the tasks
whose grade row has no error), as aggregate-grades.mjs shows it.

    python scripts/sol_stage_readout.py \\
        --stage exp037_sol_first25 data/grades/<exp037 grade>.json <self_report.json> \\
        [--stage exp038_sol_rest195 ...] [--remaining-from exp038_sol_rest195] [--json out.json]

Every task counts once on the fixed denominator (the stage's task count, or
220 for the union); a task the judge never saw counts 0 and is labelled by
why, with the cause table in batch-runner/scripts/merge_parity_regrade.py.

A task the solve gate refused (``usd_gate``: usd_ceiling_reached, never
attempted) still counts 0 on its stage's denominator, but it is left out of
every per-task cost and time figure and of the projection's sample, and it is
listed as moved: it belongs on the next stage's list. In a union, a later
stage's row for that task replaces the refused one; any other repeat refuses.

``--remaining-from <id>`` projects the next stage from that experiment's
registered task list (batch-runner/experiments/<id>.yaml) plus the tasks the
gate moved, with rubric items from the committed task catalogue. Or pass
``--remaining-tasks`` and ``--remaining-items`` by hand.

Grading USD per task is read from every journal in
data/grades/_combined_usd/<id>/, which holds every grading process of that
experiment: the right set for a stage's own grade, including its resume
chunks. After a regrade of the same experiment, pass the journals of the grade
being read with ``--journals-dir <id> <dir>``. Each journal's total is
sol_batch_grading.journal_spend's, the figure the grade preflight counts; what
its lines do not place on a task is reported as unattributed. ``stages`` sets
each stage's solve spend, narrative allowance and grading against the ceiling
its two registry entries approve, as the grade preflight's "committed" line
does.

``one_grader`` holds when every stage was graded by this tree's grader source
closure with its own config (the grade's grader_source_hash equals step 8's
hash recomputed here for that stage's registered config), the stages' configs
carry the same template blocks, and their grades name the same judge, prompt
version, rubric commit and renderer fingerprint. grader_source_hash hashes the
config file too, so two stages' raw hashes always differ. A grade made before
the grader closure or its config last changed reads as another grader here;
to compare it, run the readout on a checkout of its grading commit
(``--repo-root``).
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.util
import json
import math
import random
import statistics
import sys
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
BATCH_RUNNER = REPO_ROOT / "batch-runner"


def _load_causes():
    spec = importlib.util.spec_from_file_location(
        "_sol_stage_readout_causes", BATCH_RUNNER / "scripts" / "merge_parity_regrade.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


#: The cause table this readout shares with merge_parity_regrade.py.
CAUSES = _load_causes()
INFRASTRUCTURE = CAUSES.INFRASTRUCTURE
UNCLASSIFIED = CAUSES.UNCLASSIFIED
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
TASK_CATALOG = Path("batch-runner/experiments/execution_envelope/gdpval_task_catalog.json")


def _batch_runner_module(name: str):
    """A batch-runner module; their own imports need batch-runner on sys.path."""
    path = str(BATCH_RUNNER)
    if path not in sys.path:
        sys.path.append(path)
    return importlib.import_module(name)


def _ext(name: str) -> str:
    dot = name.rfind(".")
    return name[dot:].lower() if dot > name.rfind("/") else ""


def _stem(name: str) -> str:
    base = name.rsplit("/", 1)[-1]
    return base[: base.rfind(".")] if "." in base else base


def journal_usd_by_task(directory: Path) -> dict[str, Decimal]:
    """Grading USD each task's lines account for, over every journal in ``directory``."""
    spent: dict[str, Decimal] = defaultdict(Decimal)
    for path in sorted(directory.glob("run-*.combined_usd.jsonl")):
        for task, amount in _journal_lines_by_task(path).items():
            spent[task] += amount
    return dict(spent)


def _journal_lines_by_task(path: Path) -> dict[str, Decimal]:
    spent: dict[str, Decimal] = defaultdict(Decimal)
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


def journal_usd(directory: Path) -> tuple[dict[str, Decimal], Decimal, list[str]]:
    """Per-task grading USD, the USD no task line holds, and the journals read.

    Each journal's total is sol_batch_grading.journal_spend's: settled,
    abandoned and never-concluded reserves, or the close line's in-memory
    total when a conclusion's own line failed to write. A journal that
    function refuses refuses the readout.
    """
    grading = _batch_runner_module("sol_batch_grading")
    by_task: dict[str, Decimal] = defaultdict(Decimal)
    unattributed = Decimal(0)
    names: list[str] = []
    for path in sorted(directory.glob("run-*.combined_usd.jsonl")):
        try:
            total = grading.journal_spend(path)
        except grading.CombinedUsdRefused as refused:
            raise SystemExit(f"{path}: {refused.detail}") from None
        lines = _journal_lines_by_task(path)
        placed = sum(lines.values(), Decimal(0))
        if placed > total:
            raise SystemExit(f"{path}: its task lines add to more than the journal spent")
        for task, amount in lines.items():
            by_task[task] += amount
        unattributed += total - placed
        names.append(path.name)
    return dict(by_task), unattributed, names


def grader_identity(experiment_id: str, grade: dict, batch_root: Path) -> dict[str, Any]:
    """What marked a stage, in terms two stages with different configs can share."""
    import yaml

    grading = _batch_runner_module("sol_batch_grading")
    configs = {approval.experiment_id: approval.config_name for approval in grading.APPROVALS
               if approval.solve_seed == grading.SOLVE_SEED_SOL_BATCH}
    judge = grade.get("judge") or {}
    identity: dict[str, Any] = {
        "stage": experiment_id,
        "config_name": configs.get(experiment_id),
        "grader_source_hash": grade.get("grader_source_hash"),
        "this_tree_source_hash": None,
        "graded_by_this_tree": False,
        "template_blocks_sha256": None,
        "judge": {"model": judge.get("model"), "reasoning_effort": judge.get("reasoning_effort"),
                  "prompt_version": (grade.get("prompt") or {}).get("version"),
                  "rubric_commit": (grade.get("rubric") or {}).get("commit_sha")},
        "renderer_fingerprint": grade.get("renderer_fingerprint"),
    }
    if identity["config_name"] is None:
        return identity
    relative = f"grading_configs/{identity['config_name']}.yaml"
    config = yaml.safe_load((batch_root / relative).read_text(encoding="utf-8"))
    blocks = {block: config.get(block) for block in grading.TEMPLATE_BLOCKS}
    identity["template_blocks_sha256"] = hashlib.sha256(
        json.dumps(blocks, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    step8 = _batch_runner_module("step8_grade")
    identity["this_tree_source_hash"] = step8.compute_grader_source_hash(relative, config, batch_root=batch_root)
    identity["graded_by_this_tree"] = identity["this_tree_source_hash"] == identity["grader_source_hash"]
    return identity


def registered_money(experiment_id: str) -> dict[str, Decimal | None]:
    """The stage's approved ceiling and narrative allowance, as the two registries hold them."""
    grading = _batch_runner_module("sol_batch_grading")
    controls = _batch_runner_module("sol_batch_controls")
    approval = next((entry for entry in grading.APPROVALS if entry.experiment_id == experiment_id), None)
    run = controls.registered_run(experiment_id)
    return {"ceiling_usd": None if approval is None else approval.ceiling_usd,
            "narrative_allowance_usd": None if run is None else run.narrative_allowance_usd}


def _stage_money(rows: list[dict]) -> list[dict[str, Any]]:
    """What each stage committed against its ceiling: solve, narrative allowance and grading."""
    records: dict[str, dict] = {}
    for row in rows:
        records.setdefault(row["stage"], row["stage_record"])
    money = []
    for stage, record in records.items():
        mine = [row for row in rows if row["stage"] == stage]
        solve = sum(Decimal(str(row["solve_usd"])) for row in mine)
        grading = sum(Decimal(str(row["grading_usd"])) for row in mine) + record["grading_unattributed_usd"]
        narrative = record["narrative_allowance_usd"] or Decimal(0)
        committed = solve + narrative + grading
        ceiling = record["ceiling_usd"]
        money.append({"stage": stage, "ceiling_usd": None if ceiling is None else float(ceiling),
                      "solve_usd": round(float(solve), 2), "narrative_allowance_usd": float(narrative),
                      "grading_usd": round(float(grading), 2), "committed_usd": round(float(committed), 2),
                      "left_under_ceiling_usd": None if ceiling is None else round(float(ceiling - committed), 2)})
    return money


def read_stage(experiment_id: str, grade_path: Path, report_path: Path, journals: Path,
               batch_root: Path | None = None) -> list[dict]:
    grade = json.loads(grade_path.read_text(encoding="utf-8"))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report["meta"]["experiment_id"] != experiment_id:
        raise SystemExit(f"{report_path} is not {experiment_id}'s self_report.json")
    graded = {task["task_id"]: task for task in grade["tasks"]}
    grading_usd, unattributed, journal_names = journal_usd(journals)
    # A line on no task of this stage (a request booked without a task id)
    # is still spend under the ceiling.
    listed = {solved["task_id"] for solved in report["task_results"]}
    unattributed += sum((amount for task, amount in grading_usd.items() if task not in listed), Decimal(0))
    stage = {
        "stage": experiment_id,
        "grader": grader_identity(experiment_id, grade, BATCH_RUNNER if batch_root is None else batch_root),
        "journals": journal_names,
        "grading_unattributed_usd": unattributed,
        **registered_money(experiment_id),
    }
    rows = []
    for solved in report["task_results"]:
        task_id = solved["task_id"]
        marked = graded.get(task_id)
        observability = solved.get("observability") or {}
        files = [str(name) for name in solved.get("deliverable_files") or []]
        category = observability.get("error_category")
        # Step 8's own rule for a judged task: a grade row with no error.
        judged = marked is not None and not marked.get("error")
        if judged:
            cause = "judged"
        else:
            cause = CAUSES.zero_cause_of("missing_from_grade" if marked is None else marked.get("error"), category)
        marked = marked or {}
        stems: dict[str, set[str]] = defaultdict(set)
        for name in files:
            if _ext(name) in DOCUMENT_EXTENSIONS:
                stems[_stem(name)].add(_ext(name))
        rows.append({
            "stage": experiment_id, "task_id": task_id, "status": solved.get("status"),
            "error_category": category, "grade_error": marked.get("error"), "cause": cause,
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
            # Shared by every row of the stage; summarise reads it once per stage.
            "stage_record": stage,
        })
    return rows


def union(rows: list[dict]) -> tuple[list[dict], list[str]]:
    """Every task once: a later stage's row replaces an earlier USD-gate refusal; any other repeat refuses."""
    kept: dict[str, dict] = {}
    rerun: list[str] = []
    for row in rows:
        earlier = kept.get(row["task_id"])
        if earlier is not None:
            if earlier["cause"] != "usd_gate" or earlier["stage"] == row["stage"]:
                raise SystemExit("a task appears in two stages; a union counts every task once (only a task "
                                 "the USD gate refused may reappear, in a later stage)")
            rerun.append(row["task_id"])
            del kept[row["task_id"]]
        kept[row["task_id"]] = row
    return list(kept.values()), rerun


def remaining_from(repo_root: Path, experiment_id: str, moved: list[str]) -> tuple[int, int, list[str]]:
    """The next stage's task and rubric-item counts: its registered list plus the tasks the gate moved."""
    import yaml

    experiment = yaml.safe_load((repo_root / "batch-runner/experiments" / f"{experiment_id}.yaml")
                                .read_text(encoding="utf-8"))
    tasks = list(experiment["data"]["filter"]["task_ids"])
    listed = set(tasks)
    tasks += [task for task in moved if task not in listed]
    catalog = json.loads((repo_root / TASK_CATALOG).read_text(encoding="utf-8"))
    items = {task["task_id"]: task["rubric_item_count"] for task in catalog["tasks"]}
    unknown = [task for task in tasks if task not in items]
    if unknown or len(set(tasks)) != len(tasks):
        raise SystemExit(f"{experiment_id}'s list is not a list of distinct catalogue tasks")
    return len(tasks), sum(items[task] for task in tasks), tasks


def _graders(rows: list[dict]) -> tuple[list[dict], list[str]]:
    stages: dict[str, dict] = {}
    for row in rows:
        stages.setdefault(row["stage"], row["stage_record"]["grader"])
    problems: list[str] = []
    for stage, identity in stages.items():
        if identity["config_name"] is None:
            problems.append(f"{stage}: not a registered Sol run, so its grading config is unknown")
        elif not identity["graded_by_this_tree"]:
            problems.append(
                f"{stage}: graded by grader source {str(identity['grader_source_hash'])[:16]}, not by this "
                f"tree's {str(identity['this_tree_source_hash'])[:16]} for {identity['config_name']}.yaml")
    for field in ("template_blocks_sha256", "judge", "renderer_fingerprint"):
        if len({json.dumps(identity[field], sort_keys=True) for identity in stages.values()}) > 1:
            problems.append(f"the stages differ in {field}")
    return list(stages.values()), problems


def summarise(rows: list[dict], denominator: int, remaining_tasks: int, remaining_items: int,
              rerun: list[str] | None = None) -> dict:
    judged = [row for row in rows if row["cause"] == "judged"]
    # Never attempted: on the fixed denominator at 0, but not a sample of what
    # an attempt costs or takes.
    attempted = [row for row in rows if row["cause"] != "usd_gate"]
    moved = [row["task_id"] for row in rows if row["cause"] == "usd_gate"]
    causes = Counter(row["cause"] for row in rows)
    solve = [row["solve_usd"] for row in attempted]
    judged_items = sum(row["items"] - row["excluded_items"] for row in judged) or 1
    unattributed = sum({id(row["stage_record"]): row["stage_record"]["grading_unattributed_usd"]
                        for row in rows}.values(), Decimal(0))
    grading_total = sum(row["grading_usd"] for row in rows) + float(unattributed)
    per_item = grading_total / judged_items
    rng = random.Random(20261106)
    boot = sorted(sum(rng.choice(solve) for _ in range(remaining_tasks)) for _ in range(2000)) if solve else [0]
    mean_minutes = statistics.mean(row["solve_seconds"] for row in attempted) / 60 if attempted else 0
    # Tasks that left files are the ones a grade has to mark; a refusal (R1) is
    # a selector defect to fix, not a saving to project.
    judged_share = sum(1 for row in attempted if row["files"]) / len(attempted) if attempted else 0
    grade_seconds_per_item = (sum(row["grading_seconds"] for row in judged) / judged_items) if judged else 0
    legs = math.ceil(remaining_tasks * mean_minutes / LEG_MINUTES) if remaining_tasks else 0
    chunks = math.ceil(remaining_items * judged_share * grade_seconds_per_item / CHUNK_SECONDS) if remaining_items else 0
    with_files = [row for row in rows if row["files"]]
    graders, grader_problems = _graders(rows)
    summary = {
        "tasks": len(rows), "denominator": denominator,
        "graders": graders,
        "one_grader": not grader_problems,
        "one_grader_problems": grader_problems,
        "score_fixed_denominator": round(sum(row["pct"] for row in rows) / denominator, 2),
        "score_judged_only": round(statistics.mean(row["pct"] for row in judged), 2) if judged else None,
        "score_full_item_denominator": round(sum(row["pct_full_denominator"] for row in rows) / denominator, 2),
        "zeros_by_cause": {cause: count for cause, count in sorted(causes.items()) if cause != "judged"},
        "moved_by_usd_gate": moved,
        "rerun_after_usd_gate": list(rerun or []),
        # Against each stage's approved ceiling, as the grade preflight counts it.
        "stages": _stage_money(rows),
        "file_habits": {
            "tasks_with_files": len(with_files),
            "email_files": sum(row["email_files"] for row in rows),
            "same_stem_multi_format_groups": sum(row["same_stem_formats"] for row in rows),
            "helper_files": sum(row["helper_files"] for row in rows),
            "image_files": sum(row["image_files"] for row in rows),
            "selection_rules": dict(Counter(row["selection_rule"] for row in with_files)),
        },
        "usd": {"solve": round(sum(solve), 2), "grading": round(grading_total, 2),
                "grading_unattributed": round(float(unattributed), 2),
                "solve_per_task_mean": round(statistics.mean(solve), 2) if solve else None,
                "solve_per_task_max": round(max(solve), 2) if solve else None,
                "grading_per_judged_item": round(per_item, 4)},
        "time": {"solve_minutes_per_task_mean": round(mean_minutes, 1),
                 "grading_seconds_per_judged_item": round(grade_seconds_per_item, 1)},
        "projection": {
            "attempted_sample": len(attempted),
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
    parser.add_argument("--remaining-from", default=None, metavar="EXPERIMENT_ID",
                        help="project the next stage from this experiment's registered task list, plus the "
                             "tasks the USD gate moved")
    parser.add_argument("--remaining-tasks", type=int, default=None)
    parser.add_argument("--remaining-items", type=int, default=None)
    parser.add_argument("--json", default=None)
    parser.add_argument("--journals-dir", nargs=2, action="append", default=[],
                        metavar=("EXPERIMENT_ID", "DIR"),
                        help="read this stage's grading journals from DIR instead of "
                             "data/grades/_combined_usd/EXPERIMENT_ID")
    args = parser.parse_args(argv)
    if args.remaining_from is not None and (args.remaining_tasks is not None or args.remaining_items is not None):
        parser.error("--remaining-from derives the remaining tasks and items; do not also pass them")
    repo_root = Path(args.repo_root)
    overrides = {experiment_id: Path(directory) for experiment_id, directory in args.journals_dir}
    rows: list[dict] = []
    for experiment_id, grade_path, report_path in args.stage:
        journals = overrides.get(experiment_id, repo_root / "data/grades/_combined_usd" / experiment_id)
        rows += read_stage(experiment_id, Path(grade_path), Path(report_path), journals,
                           batch_root=(repo_root / "batch-runner").resolve())
    rows, rerun = union(rows)
    remaining_tasks, remaining_items = args.remaining_tasks or 0, args.remaining_items or 0
    remaining: dict[str, Any] = {}
    if args.remaining_from is not None:
        moved = [row["task_id"] for row in rows if row["cause"] == "usd_gate"]
        remaining_tasks, remaining_items, task_ids = remaining_from(repo_root, args.remaining_from, moved)
        remaining = {"experiment_id": args.remaining_from, "task_ids": task_ids}
    summary = summarise(rows, args.denominator or len(rows), remaining_tasks, remaining_items, rerun)
    if remaining:
        summary["projection"]["remaining_from"] = remaining["experiment_id"]
    tasks = [{key: value for key, value in row.items() if key != "stage_record"} for row in rows]
    document = {"summary": summary, "tasks": tasks, "rules": RULES}
    if remaining:
        document["remaining_task_ids"] = remaining["task_ids"]
    if args.json:
        Path(args.json).write_text(json.dumps(document, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
