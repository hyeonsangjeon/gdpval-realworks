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
        [--stage exp038_sol_rest195 ...] --remaining-from exp038_sol_rest195 [--json out.json]

Each stage is a run registered in sol_batch_controls.RUNS, read from its
final grade (run_status "final", the stage's own experiment id) and the
self_report.json of the revision that grade names; the two must list the
same tasks in the same order, and that list must be the registered one. A
grade that judged anything needs its journals: a journals directory holding
none refuses.

Every task counts once on the fixed denominator (the stage's task count, or
220 for the union); a task the judge never saw counts 0 and is labelled by
why, with the cause table in batch-runner/scripts/merge_parity_regrade.py.

A task whose last attempt the Sol harness refused before it started
(``usd_gate``: usd_ceiling_reached; ``sol_gate``: the context-window or
ledger check) still counts 0 on its stage's denominator, but it is left out
of every per-task cost and time figure and of the projection's sample. A
``usd_gate`` task is listed as moved: it belongs on the next stage's list. In
a union, a later stage's row for that task replaces the refused one; any
other repeat refuses. ``sol_gate`` tasks count with infrastructure for R2.

``--remaining-from <id>`` projects the next stage from that experiment's
registered task list (batch-runner/experiments/<id>.yaml) plus the tasks the
gate moved, with rubric items from the committed task catalogue. Or pass both
``--remaining-tasks`` and ``--remaining-items`` by hand. With neither, nothing
is projected and R3 and R4 print null: not evaluated.

Grading USD per task is read from every journal in
data/grades/_combined_usd/<id>/, which holds every grading process of that
experiment: the right set for a stage's own grade, including its resume
chunks. After a regrade of the same experiment, pass the journals of the grade
being read with ``--journals-dir <id> <dir>``. Each journal's total is
sol_batch_grading.journal_spend's, the figure the grade preflight counts, and
its open line must name the stage and its config; what its lines do not place
on a task is reported as unattributed. ``stages`` sets each stage's solve
spend, narrative allowance and grading against the ceiling its two registry
entries approve, as the grade preflight's "committed" line does: the solve
spend is sol_batch_controls.solve_spend_usd over the stage's published rows
(the run's prior-lineage spend, every booked row including those the gate
refused on a retry, and its lost bookings for the graded revision), and the
grading is every journal read. With the experiment's whole journal directory
that is the preflight's figure for the next grade of the stage.

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
    "R2": "infrastructure (sol_gate refusals included) plus unclassified losses at most 2 of 25 (8%)",
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


def journal_usd(directory: Path, owner: tuple[str, str] | None = None,
                ) -> tuple[dict[str, Decimal], Decimal, list[str]]:
    """Per-task grading USD, the USD no task line holds, and the journals read.

    Each journal's total is sol_batch_grading.journal_spend's: settled,
    abandoned and never-concluded reserves, or the close line's in-memory
    total when a conclusion's own line failed to write. A journal that
    function refuses refuses the readout, and so does one whose open line
    names another (experiment id, config name) than ``owner``.
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
        if owner is not None:
            opening = json.loads(path.read_text(encoding="utf-8").split("\n", 1)[0])
            opened_by = (opening.get("experiment_id"), opening.get("config_name"))
            if opened_by != owner:
                raise SystemExit(f"{path}: opened by {opened_by[0]} / {opened_by[1]}, not by {owner[0]} / {owner[1]}")
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


def _stage_money(stages: list[dict]) -> list[dict[str, Any]]:
    """What each stage committed against its ceiling: solve, narrative allowance and grading."""
    money = []
    for record in stages:
        solve, grading = record["solve_usd"], record["grading_usd"]
        narrative = record["narrative_allowance_usd"] or Decimal(0)
        committed = solve + narrative + grading
        ceiling = record["ceiling_usd"]
        money.append({"stage": record["stage"], "ceiling_usd": None if ceiling is None else float(ceiling),
                      "solve_usd": round(float(solve), 2),
                      "prior_lineage_spend_usd": round(float(record["prior_lineage_spend_usd"]), 2),
                      "lost_booking_usd": round(float(record["lost_booking_usd"]), 2),
                      "narrative_allowance_usd": float(narrative),
                      "grading_usd": round(float(grading), 2), "committed_usd": round(float(committed), 2),
                      "left_under_ceiling_usd": None if ceiling is None else round(float(ceiling - committed), 2)})
    return money


def _stage_solve(experiment_id: str, report: dict, revision: str) -> tuple[Decimal, Decimal, dict[str, Decimal]]:
    """The stage's solve spend as the grade preflight counts it, its prior lineages, and its lost bookings."""
    controls = _batch_runner_module("sol_batch_controls")
    run = controls.registered_run(experiment_id)
    try:
        lost = controls.lost_bookings_for(run, revision)
        solve = controls.solve_spend_usd(report["task_results"], revision, run)
    except controls.SolBatchControlsRefused as refused:
        raise SystemExit(f"{experiment_id}: the grade preflight would refuse this solve spend ({refused})") from None
    return solve, run.prior_lineage_spend_usd, lost


def _check_stage(experiment_id: str, grade: dict, report: dict, grade_path: Path, report_path: Path) -> None:
    """Refuse a grade or a self_report.json that is not this registered stage's whole, final result."""
    controls = _batch_runner_module("sol_batch_controls")
    run = controls.registered_run(experiment_id)
    if run is None:
        raise SystemExit(f"{experiment_id} is not a Sol run registered in sol_batch_controls.RUNS")
    meta = report.get("meta") or {}
    if meta.get("experiment_id") != experiment_id:
        raise SystemExit(f"{report_path} is not {experiment_id}'s self_report.json")
    if grade.get("experiment_id") != experiment_id:
        raise SystemExit(f"{grade_path} is not a grade of {experiment_id}")
    if grade.get("run_status") != "final":
        raise SystemExit(f"{grade_path} is not a final grade (run_status {grade.get('run_status')!r}); "
                         "read a stage once its last grading chunk has committed")
    revision = grade.get("source_inference_revision")
    if not isinstance(revision, str) or len(revision) != 40 or any(c not in "0123456789abcdef" for c in revision):
        raise SystemExit(f"{grade_path} names no 40-hex source_inference_revision")
    ordered = meta.get("ordered_task_ids")
    if (not isinstance(ordered, list) or len(ordered) != run.task_count
            or controls.ordered_task_ids_sha256(ordered) != run.ordered_task_ids_sha256):
        raise SystemExit(f"{report_path} does not list {experiment_id}'s registered tasks")
    if [solved.get("task_id") for solved in report.get("task_results") or []] != ordered:
        raise SystemExit(f"{report_path}'s task_results are not its ordered_task_ids")
    if [task.get("task_id") for task in grade.get("tasks") or []] != ordered:
        raise SystemExit(f"{grade_path} does not grade the tasks of {report_path}, in their order")


def read_stage(experiment_id: str, grade_path: Path, report_path: Path, journals: Path,
               batch_root: Path | None = None) -> list[dict]:
    grade = json.loads(grade_path.read_text(encoding="utf-8"))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    _check_stage(experiment_id, grade, report, grade_path, report_path)
    controls = _batch_runner_module("sol_batch_controls")
    run = controls.registered_run(experiment_id)
    graded = {task["task_id"]: task for task in grade["tasks"]}
    grading_usd, unattributed, journal_names = journal_usd(journals, (experiment_id, run.grading_config_name))
    if not journal_names and any(not task.get("error") or (task.get("judge_call_count") or 0) > 0
                                 for task in grade["tasks"]):
        raise SystemExit(f"{journals} holds no combined USD journal, yet {grade_path} judged tasks; "
                         "pass that grade's journals with --journals-dir")
    # Every journal read, whole: the preflight's prior-grading figure.
    grading_total = sum(grading_usd.values(), Decimal(0)) + unattributed
    # A line on no task of this stage (a request booked without a task id)
    # is still spend under the ceiling.
    listed = {solved["task_id"] for solved in report["task_results"]}
    unattributed += sum((amount for task, amount in grading_usd.items() if task not in listed), Decimal(0))
    revision = grade["source_inference_revision"]
    solve, prior_lineage, lost = _stage_solve(experiment_id, report, revision)
    stage = {
        "stage": experiment_id,
        "grader": grader_identity(experiment_id, grade, BATCH_RUNNER if batch_root is None else batch_root),
        "journals": journal_names,
        "solve_usd": solve,
        "prior_lineage_spend_usd": prior_lineage,
        "lost_booking_usd": sum(lost.values(), Decimal(0)),
        "grading_usd": grading_total,
        "grading_unattributed_usd": unattributed,
        **registered_money(experiment_id),
    }
    rows = []
    for solved in report["task_results"]:
        task_id = solved["task_id"]
        marked = graded[task_id]
        observability = solved.get("observability") or {}
        files = [str(name) for name in solved.get("deliverable_files") or []]
        category = observability.get("error_category")
        metrics = observability.get("budget_metrics") or {}
        # The row's booking, or the lost booking the preflight counts for it.
        booked = metrics.get("conservative_cost_usd") if "conservative_cost_usd" in metrics else lost.get(task_id, 0)
        # Step 8's own rule for a judged task: a grade row with no error.
        judged = not marked.get("error")
        cause = "judged" if judged else CAUSES.zero_cause_of(marked.get("error"), category)
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
            "solve_usd": float(booked or 0),
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


def _stage_records(rows: list[dict]) -> list[dict]:
    """Each stage's shared record, in the order its rows first appear."""
    records: dict[str, dict] = {}
    for row in rows:
        records.setdefault(row["stage"], row["stage_record"])
    return list(records.values())


def _graders(records: list[dict]) -> tuple[list[dict], list[str]]:
    stages = {record["stage"]: record["grader"] for record in records}
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


def summarise(rows: list[dict], denominator: int, remaining_tasks: int | None, remaining_items: int | None,
              rerun: list[str] | None = None, stages: list[dict] | None = None) -> dict:
    """The readout. ``remaining_tasks``/``remaining_items`` None: nothing is projected, R3 and R4 are None.

    ``stages`` are the stages' records, including a stage whose every row a
    later stage replaced; by default, those of ``rows``.
    """
    records = _stage_records(rows) if stages is None else stages
    projected = remaining_tasks is not None and remaining_items is not None
    judged = [row for row in rows if row["cause"] == "judged"]
    # Never attempted: on the fixed denominator at 0, but not a sample of what
    # an attempt costs or takes.
    attempted = [row for row in rows if row["cause"] not in CAUSES.NOT_ATTEMPTED]
    moved = [row["task_id"] for row in rows if row["cause"] == "usd_gate"]
    causes = Counter(row["cause"] for row in rows)
    solve = [row["solve_usd"] for row in attempted]
    judged_items = sum(row["items"] - row["excluded_items"] for row in judged) or 1
    unattributed = sum((record["grading_unattributed_usd"] for record in records), Decimal(0))
    grading_total = float(sum((record["grading_usd"] for record in records), Decimal(0)))
    per_item = grading_total / judged_items
    rng = random.Random(20261106)
    boot = (sorted(sum(rng.choice(solve) for _ in range(remaining_tasks)) for _ in range(2000))
            if solve and projected else [0])
    mean_minutes = statistics.mean(row["solve_seconds"] for row in attempted) / 60 if attempted else 0
    # Tasks that left files are the ones a grade has to mark; a refusal (R1) is
    # a selector defect to fix, not a saving to project.
    judged_share = sum(1 for row in attempted if row["files"]) / len(attempted) if attempted else 0
    grade_seconds_per_item = (sum(row["grading_seconds"] for row in judged) / judged_items) if judged else 0
    legs = chunks = None
    if projected:
        legs = math.ceil(remaining_tasks * mean_minutes / LEG_MINUTES) if remaining_tasks else 0
        chunks = (math.ceil(remaining_items * judged_share * grade_seconds_per_item / CHUNK_SECONDS)
                  if remaining_items else 0)
    with_files = [row for row in rows if row["files"]]
    graders, grader_problems = _graders(records)
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
        "stages": _stage_money(records),
        "file_habits": {
            "tasks_with_files": len(with_files),
            "email_files": sum(row["email_files"] for row in rows),
            "same_stem_multi_format_groups": sum(row["same_stem_formats"] for row in rows),
            "helper_files": sum(row["helper_files"] for row in rows),
            "image_files": sum(row["image_files"] for row in rows),
            "selection_rules": dict(Counter(str(row["selection_rule"]) for row in with_files)),
        },
        # Solve: what the stages committed (sol_batch_controls.solve_spend_usd).
        "usd": {"solve": round(float(sum((record["solve_usd"] for record in records), Decimal(0))), 2),
                "grading": round(grading_total, 2),
                "grading_unattributed": round(float(unattributed), 2),
                "solve_per_task_mean": round(statistics.mean(solve), 2) if solve else None,
                "solve_per_task_max": round(max(solve), 2) if solve else None,
                "grading_per_judged_item": round(per_item, 4)},
        "time": {"solve_minutes_per_task_mean": round(mean_minutes, 1),
                 "grading_seconds_per_judged_item": round(grade_seconds_per_item, 1)},
        "projection": {
            "attempted_sample": len(attempted),
            "remaining_tasks": remaining_tasks, "remaining_items": remaining_items,
            "solve_usd_mean": round(statistics.mean(solve) * remaining_tasks, 0) if solve and projected else None,
            "solve_usd_p90": round(boot[int(0.9 * len(boot))], 0) if projected else None,
            "grading_usd": round(per_item * remaining_items * judged_share, 0) if projected else None,
            "solve_legs": legs, "grading_chunks": chunks,
        },
    }
    # The harness's own refusals are not the model's: counted as infrastructure.
    infrastructure = sum(causes.get(cause, 0) for cause in ("infrastructure", "sol_gate", "unclassified_failure"))
    refusals = sum(1 for row in with_files if row["cause"] == "grader_refusal")
    summary["rules"] = {
        "R1": refusals == 0,
        "R2": infrastructure <= math.floor(0.08 * len(rows)),
        # None: not evaluated, because nothing was projected.
        "R3": None if legs is None else legs <= MAX_LEGS - 2,
        "R4": None if chunks is None else chunks <= MAX_CHUNKS - 2,
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
    parser.add_argument("--remaining-tasks", type=int, default=None, help="with --remaining-items")
    parser.add_argument("--remaining-items", type=int, default=None, help="with --remaining-tasks")
    parser.add_argument("--json", default=None)
    parser.add_argument("--journals-dir", nargs=2, action="append", default=[],
                        metavar=("EXPERIMENT_ID", "DIR"),
                        help="read this stage's grading journals from DIR instead of "
                             "data/grades/_combined_usd/EXPERIMENT_ID")
    args = parser.parse_args(argv)
    if args.remaining_from is not None and (args.remaining_tasks is not None or args.remaining_items is not None):
        parser.error("--remaining-from derives the remaining tasks and items; do not also pass them")
    if (args.remaining_tasks is None) != (args.remaining_items is None):
        parser.error("pass both --remaining-tasks and --remaining-items, or --remaining-from")
    repo_root = Path(args.repo_root)
    overrides = {experiment_id: Path(directory) for experiment_id, directory in args.journals_dir}
    rows: list[dict] = []
    stages: list[dict] = []
    for experiment_id, grade_path, report_path in args.stage:
        journals = overrides.get(experiment_id, repo_root / "data/grades/_combined_usd" / experiment_id)
        stage_rows = read_stage(experiment_id, Path(grade_path), Path(report_path), journals,
                                batch_root=(repo_root / "batch-runner").resolve())
        rows += stage_rows
        stages += _stage_records(stage_rows)
    if len({record["stage"] for record in stages}) != len(stages):
        raise SystemExit("a stage is passed twice; a union counts every task once")
    rows, rerun = union(rows)
    remaining_tasks, remaining_items = args.remaining_tasks, args.remaining_items
    remaining: dict[str, Any] = {}
    if args.remaining_from is not None:
        moved = [row["task_id"] for row in rows if row["cause"] == "usd_gate"]
        remaining_tasks, remaining_items, task_ids = remaining_from(repo_root, args.remaining_from, moved)
        remaining = {"experiment_id": args.remaining_from, "task_ids": task_ids}
    summary = summarise(rows, args.denominator or len(rows), remaining_tasks, remaining_items, rerun, stages)
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
