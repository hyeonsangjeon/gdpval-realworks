#!/usr/bin/env python3
"""Read a gold-ceiling grade payload and answer the questions stage 1 asks.

Why this exists
---------------
``tasks/rebuilding_grading_task/300-gold-ceiling.md`` asks for six things: the
mean score, the required-item pass rate, the grader error rate, the evidence
behind every item that fell short of full marks, the usage split by model, and
the actual bill. Every one of those is already in the grade payload. Copying
them into a report by hand is where a report stops matching its run -- so this
reads them out, and the report quotes this.

Two of the six need work the payload does not do for you:

* **Image and audio call counts separately.** ``summary.cost`` carries one
  ``total_perception_calls``. Which of those looked at a picture and which
  listened to a recording is only recoverable per rubric item, from
  ``routing_modality``, so this regroups them.
* **Which shortfalls are the grader's fault.** Nothing can decide that
  automatically. What this does is surface every below-maximum item with the
  evidence the judge recorded, sorted so the largest losses come first, which
  is the input a person needs to classify them.

It also refuses a payload that is not stage 1's corpus, fully graded. A number
read out of the wrong file is worse than no number, and the four things it
checks -- task count, ordered-id fingerprint, graded count and run status --
are the ones that differ when somebody points this at a shard or at a
different corpus. A stage 2 repeat passes them, and should: it is the same
thirty tasks graded again, which is exactly what stage 2 needs to read.

Usage
-----
    python batch-runner/scripts/analyze_gold_ceiling.py <grade.json>
    python batch-runner/scripts/analyze_gold_ceiling.py <grade.json> --json

Exit status is 0 when every threshold is met and 1 when any is missed, so a
run that quietly fell below the ceiling cannot be reported as passing.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

# The three numbers stage 1 is accepted or rejected on, from
# `tasks/rebuilding_grading_task/300-gold-ceiling.md` lines 17-19 and 24-26.
# `test_gold_ceiling_analysis.py` checks these against the specification text,
# so a threshold edited in one place and not the other fails rather than drifts.
MEAN_SCORE_PCT_FLOOR = 90.0
CRITICAL_ITEM_PASS_FLOOR = 0.95
JUDGE_ERROR_RATE_CEILING = 0.02

# Which items the second threshold counts. Imported rather than restated: the
# comment above `MAGNITUDE_THRESHOLD` names this very run as the thing that
# should decide whether 4 is the right boundary, so an analysis that counted
# through its own copy of the number could disagree with the grader about what
# it was measuring at exactly the moment the disagreement mattered.
#
# The report's generated blocks run this from the repository root, where
# `batch-runner/` is not importable, so the package root goes on the path here
# rather than relying on the caller's working directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.grader import MAGNITUDE_THRESHOLD as REQUIRED_ITEM_MIN_ABS_SCORE  # noqa: E402

# What the specification pinned. A payload disagreeing with either is some
# other run, and reading stage 1's numbers out of it would be a mistake no
# reader could detect afterwards.
EXPECTED_TASK_COUNT = 30

# The 30 pinned task ids, fingerprinted the way the grader fingerprints them.
#
# This is compared against `expected_ordered_task_ids_sha256` in the payload,
# and that field is written by `step8_grade._ordered_task_ids_sha256`, which
# hashes `json.dumps(ids, ensure_ascii=False, separators=(",", ":"))` -- a
# compact JSON array. So this constant has to be the compact-JSON digest of
# the same ids in the same order; any other encoding of the identical list
# produces a different digest and refuses the very run it was written for.
#
# That is not hypothetical. An earlier pass pinned the newline-joined digest
# of these exact ids, `09ce9245...`, and it refused stage 1's own run. Both
# digests cover the same thirty ids in the same order -- only the separator
# differs -- so the mismatch says nothing whatsoever about the corpus, which
# is what made it slow to read. `test_the_pinned_corpus_matches_the_grading_
# config` now recomputes this through the grader's own function rather than
# restating the formula, so the two can no longer drift apart in silence.
EXPECTED_ORDERED_TASK_IDS_SHA256 = (
    "82d14ac9bf9c3ad37920fb781ee961f5e20805c52618df0d0cdb9d5e677a7e8b"
)

# What a finished run is allowed to call itself. Both spellings mean the same
# thing here -- every task was graded -- and which one a gold run gets is
# decided by whether it was sharded, not by anything about its completeness.
# `step8_grade.py` marks a gold-corpus run `diagnostic` so it forks away from
# the dashboard, but `step9_merge_shards.py` writes a flat `final` when it
# joins shards back together. Insisting on `final` would therefore refuse a
# perfectly complete single-shard repeat, which is precisely the run stage 2
# needs to read. `partial` is the one that must never be accepted: a shard
# declares the whole corpus in its identity fields while holding only its own
# slice, so its aggregates read exactly like the full run's.
COMPLETE_RUN_STATUSES = frozenset({"final", "diagnostic"})


class NotTheRunThatWasPinned(SystemExit):
    """The payload is readable but is not stage 1's run."""


def _identity_problems(payload: dict[str, Any]) -> list[str]:
    problems: list[str] = []

    status = payload.get("run_status")
    if status not in COMPLETE_RUN_STATUSES:
        problems.append(
            f"run_status is {status!r}, which is not a finished run "
            f"({', '.join(sorted(COMPLETE_RUN_STATUSES))}) -- a shard covers "
            "only its own slice while declaring the whole corpus"
        )

    count = payload.get("expected_task_count")
    if count != EXPECTED_TASK_COUNT:
        problems.append(
            f"expected_task_count is {count!r}, not {EXPECTED_TASK_COUNT}"
        )

    ordered = payload.get("expected_ordered_task_ids_sha256")
    if ordered != EXPECTED_ORDERED_TASK_IDS_SHA256:
        problems.append(
            "expected_ordered_task_ids_sha256 is "
            f"{ordered!r}, not the pinned {EXPECTED_ORDERED_TASK_IDS_SHA256}"
        )

    graded = (payload.get("summary") or {}).get("graded_tasks")
    if graded != EXPECTED_TASK_COUNT:
        problems.append(
            f"summary.graded_tasks is {graded!r}, so {EXPECTED_TASK_COUNT} "
            "tasks were pinned but a different number was graded"
        )

    return problems


def perception_calls_by_modality(payload: dict[str, Any]) -> dict[str, int]:
    """How many perception calls each routing modality accounted for.

    ``summary.cost.total_perception_calls`` is one number. The specification
    asks for the image and audio counts separately, and only the rubric items
    know which was which.
    """
    by_modality: dict[str, int] = defaultdict(int)
    for task in payload.get("tasks") or []:
        for item in task.get("items") or []:
            calls = item.get("perception_call_count") or 0
            if calls:
                by_modality[item.get("routing_modality") or "unrecorded"] += calls
    return dict(sorted(by_modality.items()))


def items_below_full_marks(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Every rubric item that did not score its maximum, biggest loss first.

    This is the raw material for the specification's "library limit or genuine
    shortfall" call. It deliberately keeps items whose award is *above* the
    maximum out of the list but reports them separately as a fault, because a
    score over the maximum is a grader bug rather than a shortfall.
    """
    shortfalls: list[dict[str, Any]] = []
    for task in payload.get("tasks") or []:
        for item in task.get("items") or []:
            awarded = item.get("awarded_score")
            maximum = item.get("max_score")
            if awarded is None or maximum is None:
                continue
            if item.get("score_excluded"):
                continue
            if awarded >= maximum:
                continue
            shortfalls.append(
                {
                    "task_id": task.get("task_id"),
                    "sector": task.get("sector"),
                    "occupation": task.get("occupation"),
                    "rubric_item_id": item.get("rubric_item_id"),
                    "criterion": item.get("criterion"),
                    "awarded_score": awarded,
                    "max_score": maximum,
                    "lost": round(float(maximum) - float(awarded), 4),
                    "verdict": item.get("verdict"),
                    "required": item.get("required"),
                    "decided_by": item.get("decided_by"),
                    "routing_modality": item.get("routing_modality"),
                    "perception_called": item.get("perception_called"),
                    "selection_status": item.get("selection_status"),
                    "selection_error": item.get("selection_error"),
                    "selected_paths": item.get("selected_paths"),
                    "judge_confidence": item.get("judge_confidence"),
                    "evidence": item.get("evidence"),
                }
            )
    shortfalls.sort(key=lambda row: (-row["lost"], str(row["task_id"])))
    return shortfalls


def per_task(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """One row per graded task, worst score first.

    The specification asks for per-task evidence, and a report that lists only
    its biggest individual losses can leave a whole task unmentioned -- the
    forty largest item losses in stage 1's first run came from nine tasks, so
    twenty-one of the thirty were invisible in that view. Ranking by item loss
    answers "where did the points go"; this answers "how did each answer do",
    which is the question a per-task classification is written against.

    Scores are read from the fields the grader wrote (``pct``, ``total_awarded``,
    ``total_max``) rather than recomputed from the items, so this reports the
    run's own arithmetic instead of a second opinion about it.

    ``points_lost`` is that subtraction rather than a sum over the items below
    their maximum, and the two can differ. A rubric may carry penalty items with
    a *negative* maximum -- "reviews articles behind a paywall", "includes test
    questions beyond the two required" -- which `core/grader.py` deliberately
    keeps out of the denominator via ``max(0, it.max_score)``. Full marks on
    such an item is an award of zero, so a fired penalty leaves the award
    *below* zero but never below the maximum, and an item-wise sum would drop it
    while the task's own total counts it. Stage 1's first run had two of these
    and neither fired, so the two spellings happened to agree; relying on that
    would be relying on a coincidence.
    """
    rows: list[dict[str, Any]] = []
    for task in payload.get("tasks") or []:
        items = task.get("items") or []
        below = [
            item
            for item in items
            if not item.get("score_excluded")
            and item.get("awarded_score") is not None
            and item.get("max_score") is not None
            and item["awarded_score"] < item["max_score"]
        ]
        awarded = task.get("total_awarded")
        maximum = task.get("total_max")
        rows.append(
            {
                "task_id": task.get("task_id"),
                "sector": task.get("sector"),
                "occupation": task.get("occupation"),
                "pct": task.get("pct"),
                "total_awarded": awarded,
                "total_max": maximum,
                "items": len(items),
                "items_below_full_marks": len(below),
                "points_lost": (
                    None
                    if awarded is None or maximum is None
                    else round(float(maximum) - float(awarded), 4)
                ),
                "critical_fail": bool(task.get("critical_fail")),
                "selection_status": task.get("selection_status"),
                "error": task.get("error"),
            }
        )
    rows.sort(
        key=lambda row: (
            row["pct"] if row["pct"] is not None else -1.0,
            str(row["task_id"]),
        )
    )
    return rows


def required_items(payload: dict[str, Any]) -> dict[str, Any]:
    """What the second threshold is actually counting.

    `core/grader.py` calls an item required when ``|max_score| >= 4`` and marks
    it passed only on a ``pass`` verdict, so partial credit counts against the
    rate exactly as hard as a flat failure does. Whether 0.95 is a reachable
    bar therefore depends entirely on which items clear that width and how
    subjective they are -- neither of which the rate itself shows.

    So this reports the denominator: how many items, split by verdict, and the
    criteria that recur across tasks. A criterion appearing in most of the
    thirty rubrics is a criterion whose wording sets the threshold, and a
    reader deciding whether a missed gate is a grader defect or a metric
    artefact needs to see it rather than take the claim on trust.
    """
    rows: list[dict[str, Any]] = []
    for task in payload.get("tasks") or []:
        for item in task.get("items") or []:
            maximum = item.get("max_score")
            if maximum is None or abs(maximum) < REQUIRED_ITEM_MIN_ABS_SCORE:
                continue
            rows.append(
                {
                    "task_id": task.get("task_id"),
                    "criterion": (item.get("criterion") or "").strip(),
                    "max_score": maximum,
                    "awarded_score": item.get("awarded_score"),
                    "verdict": item.get("verdict"),
                }
            )

    by_verdict = Counter(str(row["verdict"]) for row in rows)
    by_criterion = Counter(row["criterion"] for row in rows)
    passed = by_verdict.get("pass", 0)
    return {
        "total": len(rows),
        "passed": passed,
        "rate": None if not rows else round(passed / len(rows), 4),
        "by_verdict": dict(by_verdict.most_common()),
        "recurring_criteria": [
            {
                "criterion": criterion,
                "tasks": count,
                "passed": sum(
                    1
                    for row in rows
                    if row["criterion"] == criterion and row["verdict"] == "pass"
                ),
            }
            for criterion, count in by_criterion.most_common()
            if count > 1
        ],
    }


def _tasks_with_errors(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"task_id": task.get("task_id"), "error": task.get("error")}
        for task in payload.get("tasks") or []
        if task.get("error")
    ]


def _tasks_failing_a_required_item(payload: dict[str, Any]) -> list[str]:
    return [
        str(task.get("task_id"))
        for task in payload.get("tasks") or []
        if task.get("critical_fail")
    ]


def analyze(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary") or {}
    compat = summary.get("openai_compat") or {}
    wow = summary.get("wow") or {}
    cost = summary.get("cost") or {}

    mean_pct = compat.get("avg_score_pct")
    critical_pass = wow.get("critical_item_pass_rate")
    error_rate = wow.get("judge_error_rate")

    gates = {
        "mean_score_pct": {
            "value": mean_pct,
            "floor": MEAN_SCORE_PCT_FLOOR,
            "met": mean_pct is not None and mean_pct >= MEAN_SCORE_PCT_FLOOR,
        },
        "critical_item_pass_rate": {
            "value": critical_pass,
            "floor": CRITICAL_ITEM_PASS_FLOOR,
            "met": (
                critical_pass is not None
                and critical_pass >= CRITICAL_ITEM_PASS_FLOOR
            ),
        },
        "judge_error_rate": {
            "value": error_rate,
            "ceiling": JUDGE_ERROR_RATE_CEILING,
            "met": error_rate is not None and error_rate < JUDGE_ERROR_RATE_CEILING,
        },
    }

    shortfalls = items_below_full_marks(payload)
    graded_items = sum(len(task.get("items") or []) for task in payload.get("tasks") or [])

    return {
        "identity": {
            "experiment_id": payload.get("experiment_id"),
            "run_status": payload.get("run_status"),
            "graded_at": payload.get("graded_at"),
            "judge": payload.get("judge"),
            "grader_source_hash": payload.get("grader_source_hash"),
            "renderer_fingerprint": payload.get("renderer_fingerprint"),
            "source_inference_revision": payload.get("source_inference_revision"),
            "source_azure_ai_provenance_status": payload.get(
                "source_azure_ai_provenance_status"
            ),
            "expected_task_count": payload.get("expected_task_count"),
            "expected_ordered_task_ids_sha256": payload.get(
                "expected_ordered_task_ids_sha256"
            ),
            "shard_provenance": payload.get("shard_provenance"),
        },
        "gates": gates,
        "all_gates_met": all(gate["met"] for gate in gates.values()),
        "scores": {
            "graded_tasks": summary.get("graded_tasks"),
            "error_tasks": summary.get("error_tasks"),
            "perfect_count": compat.get("perfect_count"),
            "zero_count": compat.get("zero_count"),
            "partial_count": compat.get("partial_count"),
            "ci_pct": compat.get("ci_pct"),
            "rubric_item_coverage_avg": wow.get("rubric_item_coverage_avg"),
            "judge_pass_rate": wow.get("judge_pass_rate"),
            "precheck_pass_rate": wow.get("precheck_pass_rate"),
            "by_sector": wow.get("by_sector"),
            "score_density_histogram": wow.get("score_density_histogram"),
        },
        "usage": {
            "total_judge_calls": cost.get("total_judge_calls"),
            "total_main_judge_calls": cost.get("total_main_judge_calls"),
            "total_perception_calls": cost.get("total_perception_calls"),
            "total_render_calls": cost.get("total_render_calls"),
            "main_input_tokens": cost.get("main_input_tokens"),
            "main_output_tokens": cost.get("main_output_tokens"),
            "main_cached_tokens": cost.get("main_cached_tokens"),
            "perception_input_tokens": cost.get("perception_input_tokens"),
            "perception_output_tokens": cost.get("perception_output_tokens"),
            "perception_cached_tokens": cost.get("perception_cached_tokens"),
            "total_judge_latency_sec": cost.get("total_judge_latency_sec"),
            "usage_complete": cost.get("usage_complete"),
            "perception_calls_by_modality": perception_calls_by_modality(payload),
        },
        "bill": {
            "estimated_cost_usd": cost.get("estimated_cost_usd"),
            "pricing_complete": cost.get("pricing_complete"),
            "unpriced_models": cost.get("unpriced_models"),
        },
        "shortfalls": {
            "graded_items": graded_items,
            "below_full_marks": len(shortfalls),
            "total_points_lost": round(sum(row["lost"] for row in shortfalls), 4),
            "tasks_failing_a_required_item": _tasks_failing_a_required_item(payload),
            "tasks_with_errors": _tasks_with_errors(payload),
            "items": shortfalls,
        },
        "per_task": per_task(payload),
        "required_items": required_items(payload),
    }


def _mark(met: bool) -> str:
    return "PASS" if met else "MISS"


def _describe_renderer(fingerprint: Any) -> str:
    """The renderer line, with the LibreOffice version where a reader looks.

    Stage 1 freezes the LibreOffice version by name, so it should not be
    something you find by reading a dictionary printed sideways.
    """
    if not isinstance(fingerprint, dict):
        return str(fingerprint)
    parts = [
        str(fingerprint.get("libreoffice_version") or "libreoffice version unrecorded")
    ]
    pymupdf = fingerprint.get("pymupdf_version")
    if pymupdf:
        parts.append(f"pymupdf {pymupdf}")
    return ", ".join(parts)


def _wrapped_ids(task_ids: list[str], *, per_line: int = 3, indent: str = " " * 6) -> list[str]:
    """Identifiers down the page rather than off the side of it."""
    return [
        indent + ", ".join(task_ids[start : start + per_line])
        for start in range(0, len(task_ids), per_line)
    ]


def _render(report: dict[str, Any], *, shortfall_limit: int) -> str:
    lines: list[str] = []
    identity = report["identity"]
    lines.append("Gold ceiling — stage 1")
    lines.append("=" * 60)
    lines.append(f"  experiment      {identity['experiment_id']}")
    lines.append(f"  graded at       {identity['graded_at']}")
    lines.append(f"  run status      {identity['run_status']}")
    lines.append(f"  grader source   {identity['grader_source_hash']}")
    lines.append(f"  renderer        {_describe_renderer(identity['renderer_fingerprint'])}")
    lines.append(f"  provenance      {identity['source_azure_ai_provenance_status']}")
    lines.append("")

    lines.append("Thresholds")
    lines.append("-" * 60)
    gates = report["gates"]
    mean = gates["mean_score_pct"]
    crit = gates["critical_item_pass_rate"]
    err = gates["judge_error_rate"]
    lines.append(
        f"  mean score              {mean['value']}%   "
        f"(needs >= {mean['floor']}%)   {_mark(mean['met'])}"
    )
    lines.append(
        f"  required-item pass      {crit['value']}   "
        f"(needs >= {crit['floor']})   {_mark(crit['met'])}"
    )
    lines.append(
        f"  grader error rate       {err['value']}   "
        f"(needs < {err['ceiling']})   {_mark(err['met'])}"
    )
    lines.append("")

    req = report["required_items"]
    lines.append(
        f"Required items (|max score| >= {REQUIRED_ITEM_MIN_ABS_SCORE})"
    )
    lines.append("-" * 60)
    lines.append(
        f"  {req['passed']} of {req['total']} passed"
        + ("" if req["rate"] is None else f"  ({req['rate']})")
    )
    if req["by_verdict"]:
        verdicts = ", ".join(f"{n} {v}" for v, n in req["by_verdict"].items())
        lines.append(f"  verdicts                {verdicts}")
    for entry in req["recurring_criteria"]:
        lines.append(
            f"  {entry['passed']:3d}/{entry['tasks']:<3d} passed  ·  "
            f"{entry['criterion'][:66]}"
        )
    lines.append("")

    scores = report["scores"]
    lines.append("Scores")
    lines.append("-" * 60)
    lines.append(
        f"  graded {scores['graded_tasks']} task(s), "
        f"{scores['error_tasks']} in error; "
        f"{scores['perfect_count']} perfect, "
        f"{scores['partial_count']} partial, {scores['zero_count']} zero"
    )
    lines.append(f"  rubric item coverage    {scores['rubric_item_coverage_avg']}")
    lines.append(f"  judge pass rate         {scores['judge_pass_rate']}")
    for sector, block in (scores["by_sector"] or {}).items():
        lines.append(
            f"    {sector:<52} {block.get('avg_pct')}%  "
            f"n={block.get('task_count')}"
        )
    lines.append("")

    usage = report["usage"]
    lines.append("Usage")
    lines.append("-" * 60)
    lines.append(
        f"  judge calls             {usage['total_judge_calls']} "
        f"({usage['total_main_judge_calls']} main, "
        f"{usage['total_perception_calls']} perception)"
    )
    for modality, calls in (usage["perception_calls_by_modality"] or {}).items():
        lines.append(f"    {modality:<20} {calls}")
    if not usage["perception_calls_by_modality"]:
        lines.append("    (no perception call was made)")
    lines.append(
        f"  main tokens             in {usage['main_input_tokens']}, "
        f"out {usage['main_output_tokens']}, "
        f"cached {usage['main_cached_tokens']}"
    )
    lines.append(
        f"  perception tokens       in {usage['perception_input_tokens']}, "
        f"out {usage['perception_output_tokens']}"
    )
    lines.append(f"  judge latency (total)   {usage['total_judge_latency_sec']}s")
    lines.append(f"  usage complete          {usage['usage_complete']}")
    lines.append("")

    bill = report["bill"]
    lines.append("Bill")
    lines.append("-" * 60)
    if bill["pricing_complete"]:
        lines.append(f"  estimated cost          ${bill['estimated_cost_usd']}")
    else:
        # Never render an unpriced run as zero. A model with no published price
        # makes the total unknown, and unknown is not free.
        lines.append(
            "  estimated cost          UNKNOWN — not every model used has a "
            "published price"
        )
        lines.append(f"  unpriced models         {bill['unpriced_models']}")
    lines.append("")

    lines.append("Per task (worst first)")
    lines.append("-" * 60)
    for row in report["per_task"]:
        pct = "  n/a" if row["pct"] is None else f"{row['pct']:6.2f}"
        awarded = "?" if row["total_awarded"] is None else f"{row['total_awarded']:.2f}"
        maximum = "?" if row["total_max"] is None else f"{row['total_max']:.0f}"
        lines.append(
            f"  {row['task_id']}  {pct}%  {awarded}/{maximum}"
            f"  ·  {(row['occupation'] or 'occupation unrecorded')[:44]}"
        )
        notes = [
            f"{row['items_below_full_marks']}/{row['items']} item(s) below max",
            "loss unrecorded"
            if row["points_lost"] is None
            else f"-{row['points_lost']} point(s)",
        ]
        if row["critical_fail"]:
            notes.append("required item failed")
        if row["selection_status"] and row["selection_status"] != "ok":
            notes.append(f"selection {row['selection_status']}")
        if row["error"]:
            notes.append(f"ERROR {str(row['error'])[:60]}")
        lines.append(f"      {', '.join(notes)}")
    lines.append("")

    short = report["shortfalls"]
    lines.append("Shortfalls")
    lines.append("-" * 60)
    lines.append(
        f"  {short['below_full_marks']} of {short['graded_items']} rubric item(s) "
        f"scored below their maximum, losing {short['total_points_lost']} point(s)"
    )
    if short["tasks_failing_a_required_item"]:
        failed = short["tasks_failing_a_required_item"]
        lines.append(f"  required item failed in {len(failed)} task(s):")
        lines.extend(_wrapped_ids(failed))
    if short["tasks_with_errors"]:
        lines.append(f"  tasks in error: {len(short['tasks_with_errors'])}")
        for row in short["tasks_with_errors"]:
            lines.append(f"      {row['task_id']}  {row['error']}")
    lines.append("")

    for row in short["items"][:shortfall_limit]:
        lines.append(
            f"  -{row['lost']} of {row['max_score']}  "
            f"[{row['verdict']}, {row['routing_modality']}, "
            f"decided by {row['decided_by']}]  {row['task_id']}"
        )
        lines.append(f"      criterion  {(row['criterion'] or '')[:150]}")
        lines.append(f"      evidence   {(row['evidence'] or '')[:220]}")
        if row["selection_status"] != "ok":
            lines.append(
                f"      selection  {row['selection_status']}: {row['selection_error']}"
            )
    remaining = len(short["items"]) - shortfall_limit
    if remaining > 0:
        lines.append(f"  ... and {remaining} more (use --json for all of them)")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("grade_file", type=Path, help="merged grade payload JSON")
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit the whole analysis as JSON instead of a readable report",
    )
    parser.add_argument(
        "--shortfall-limit",
        type=int,
        default=40,
        help="how many below-maximum items to print in the readable report",
    )
    parser.add_argument(
        "--allow-any-run",
        action="store_true",
        help=(
            "skip the check that this payload is stage 1's corpus, fully "
            "graded. Use to look inside a single shard or another corpus, "
            "never for a number a report will quote"
        ),
    )
    args = parser.parse_args(argv)

    payload = json.loads(args.grade_file.read_text(encoding="utf-8"))

    if not args.allow_any_run:
        problems = _identity_problems(payload)
        if problems:
            raise NotTheRunThatWasPinned(
                f"{args.grade_file} is not the run stage 1 pinned:\n  - "
                + "\n  - ".join(problems)
                + "\nPass --allow-any-run to read it anyway."
            )

    report = analyze(payload)

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(_render(report, shortfall_limit=args.shortfall_limit))

    return 0 if report["all_gates_met"] else 1


if __name__ == "__main__":
    sys.exit(main())
