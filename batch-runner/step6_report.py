#!/usr/bin/env python3
"""Step 6: Generate Experiment Report

Reads workspace/result.json and generates two output files under workspace/report/:
  - report_data.json : structured JSON for dashboard rendering
  - report.md        : human-readable Markdown report

Narrative sections (overview, quality_analysis, failure_patterns, recommendations) are
generated via a single LLM call using the same model as the experiment.

Usage:
    python step6_report.py                          # default: workspace/result.json
    python step6_report.py --result-json path/to/result.json
    python step6_report.py --output-dir path/to/report/
    python step6_report.py --no-narrative           # skip LLM call
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Path setup ────────────────────────────────────────────────────────────

_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR))

from core.config import NEEDS_FILES_POLICIES_KNOWN, WORKSPACE_DIR
from core.execution_metrics import bounded_count, bounded_duration_ms
from core.narrative_analyzer import (
    _build_grade_source,
    _build_grading_guard_clause,
    _build_grading_results_section,
)


# ── Defaults ──────────────────────────────────────────────────────────────

DEFAULT_RESULT_JSON = WORKSPACE_DIR / "result.json"
DEFAULT_OUTPUT_DIR = WORKSPACE_DIR / "report"
GRADE_DIR = _SCRIPT_DIR.parent / "data" / "grades"


# ── V2 manifest helpers ───────────────────────────────────────────────────


def _load_manifest_safe():
    """Load the needs_files manifest if available; return None on any failure.

    Step 6 must keep working even when Step 0 has not been run (no manifest)
    or when the manifest is malformed.  Callers should treat ``None`` as
    "v2 fields unavailable" and fall back to the v1 schema (no new keys).
    """
    try:
        from core.needs_files import NeedsFilesManifest
        return NeedsFilesManifest.load()
    except Exception:
        return None


def _manifest_v2_available(manifest) -> bool:
    """True iff the manifest is a v2 manifest (has ``_summary.active_policy``).

    v1 manifests omit ``active_policy``; in that case we must NOT add any v2
    fields to the report so downstream consumers see exactly the v1 schema.
    """
    if manifest is None:
        return False
    return manifest.summary.get("active_policy") is not None


def _v2_summary_fields(manifest) -> dict:
    """Return the v2 summary fields from a manifest, or ``{}`` if v1/None."""
    if not _manifest_v2_available(manifest):
        return {}
    s = manifest.summary
    return {
        "active_policy": s.get("active_policy"),
        "policy_counts": s.get("policy_counts"),
        "confidence_distribution": s.get("confidence_distribution"),
    }


# ── Helpers ───────────────────────────────────────────────────────────────


def _find_result_json(default_path: Path) -> Path:
    """Return result JSON path; fail clearly if not found."""
    if default_path.exists():
        return default_path

    print(f"❌ Result JSON not found at {default_path}")
    print("   Run step3_format_results.sh first (it writes workspace/result.json),")
    print("   or specify --result-json path/to/result.json")
    sys.exit(1)


def _load_grade_for_experiment(exp_id: str) -> dict | None:
    """Load the most recent schema v1.0 grade JSON for an experiment."""
    candidates = sorted(
        GRADE_DIR.glob(f"{exp_id}__*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for path in candidates:
        try:
            with open(path, "r", encoding="utf-8") as f:
                grade = json.load(f)
        except Exception:
            continue
        if grade.get("_meta", {}).get("is_dummy") is True:
            continue
        if grade.get("schema_version") == "1.0":
            return grade
    return None


def _compute_summary(data: dict) -> dict:
    results = data.get("results", [])
    total = len(results)
    success_count = sum(1 for r in results if r.get("status") == "success")
    error_count = sum(1 for r in results if r.get("status") == "error")
    retried_count = sum(1 for r in results if r.get("retried", False))

    scores = [r["qa_score"] for r in results if r.get("qa_score") is not None]
    latencies = [r["latency_ms"] for r in results if r.get("latency_ms")]

    return {
        "total_tasks": total,
        "success_count": success_count,
        "success_rate_pct": round(success_count / total * 100, 1) if total else 0.0,
        "error_count": error_count,
        "retried_count": retried_count,
        "avg_qa_score": round(sum(scores) / len(scores), 2) if scores else 0.0,
        "min_qa_score": min(scores) if scores else 0,
        "max_qa_score": max(scores) if scores else 0,
        "avg_latency_ms": round(sum(latencies) / len(latencies)) if latencies else 0,
        "max_latency_ms": round(max(latencies)) if latencies else 0,
        "total_latency_ms": round(sum(latencies)) if latencies else 0,
    }


def _metric_number(value) -> float | None:
    return bounded_duration_ms(value)


def _percentile(values: list[float], percentile: float) -> float | None:
    """Return a linearly interpolated percentile for a non-empty sample."""
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 2)
    position = (len(ordered) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return round(ordered[lower] * (1 - weight) + ordered[upper] * weight, 2)


def _compute_execution_metrics(data: dict) -> dict | None:
    """Aggregate opt-in job metrics; return ``None`` for legacy experiments."""
    results = data.get("results", [])
    measured: list[tuple[dict, dict, float]] = []
    for result in results:
        raw = (result.get("observability") or {}).get("execution_metrics")
        if not isinstance(raw, dict):
            continue
        wall_time = _metric_number(raw.get("task_wall_time_ms"))
        if wall_time is not None:
            measured.append((result, raw, wall_time))

    if not measured:
        return None

    wall_times = [wall_time for _, _, wall_time in measured]
    successful_wall_times = [
        wall_time for result, _, wall_time in measured
        if result.get("status") == "success"
    ]
    failed_wall_times = [
        wall_time for result, _, wall_time in measured
        if result.get("status") != "success"
    ]
    valid_artifact_times = [
        value
        for _, raw, wall_time in measured
        if (value := _metric_number(raw.get("time_to_valid_artifact_ms"))) is not None
        and value <= wall_time
        and (bounded_count(raw.get("validated_artifact_count")) or 0) > 0
    ]

    def average(values: list[float]) -> float | None:
        return round(sum(values) / len(values), 2) if values else None

    def total(field: str) -> float:
        return round(sum(
            value
            for _, raw, _ in measured
            if (value := _metric_number(raw.get(field))) is not None
        ), 2)

    def count(field: str) -> int:
        return sum(
            value
            for _, raw, _ in measured
            if (value := bounded_count(raw.get(field))) is not None
        )

    return {
        "schema_version": "1.0",
        "measured_tasks": len(measured),
        "total_tasks": len(results),
        "coverage_pct": round(len(measured) / len(results) * 100, 1) if results else 0.0,
        "avg_task_wall_time_ms": average(wall_times),
        "p50_task_wall_time_ms": _percentile(wall_times, 0.50),
        "p95_task_wall_time_ms": _percentile(wall_times, 0.95),
        "max_task_wall_time_ms": round(max(wall_times), 2),
        "avg_successful_task_wall_time_ms": average(successful_wall_times),
        "avg_failed_task_wall_time_ms": average(failed_wall_times),
        "measured_time_to_valid_artifact_tasks": len(valid_artifact_times),
        "avg_time_to_valid_artifact_ms": average(valid_artifact_times),
        "p50_time_to_valid_artifact_ms": _percentile(valid_artifact_times, 0.50),
        "p95_time_to_valid_artifact_ms": _percentile(valid_artifact_times, 0.95),
        "total_model_time_ms": total("model_time_ms"),
        "total_tool_time_ms": total("tool_time_ms"),
        "total_verification_time_ms": total("verification_time_ms"),
        "total_dependency_time_ms": total("dependency_time_ms"),
        "total_self_qa_time_ms": total("self_qa_time_ms"),
        "total_orchestration_time_ms": total("orchestration_time_ms"),
        "total_execution_attempts": count("execution_attempt_count"),
        "total_sandbox_attempts": count("sandbox_attempt_count"),
        "total_tool_calls": count("tool_call_count"),
        "total_self_qa_calls": count("self_qa_call_count"),
        "total_job_runs": count("job_run_count"),
    }


def _compute_sector_breakdown(data: dict) -> list[dict]:
    buckets: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"total": 0, "success": 0, "scores": [], "latencies": []}
    )
    for r in data.get("results", []):
        sector = r.get("sector") or "Unknown"
        buckets[sector]["total"] += 1
        if r.get("status") == "success":
            buckets[sector]["success"] += 1
        if r.get("qa_score") is not None:
            buckets[sector]["scores"].append(r["qa_score"])
        if r.get("latency_ms"):
            buckets[sector]["latencies"].append(r["latency_ms"])

    breakdown = []
    for sector, b in sorted(buckets.items()):
        scores = b["scores"]
        latencies = b["latencies"]
        breakdown.append({
            "sector": sector,
            "total": b["total"],
            "success": b["success"],
            "success_rate_pct": round(b["success"] / b["total"] * 100, 1) if b["total"] else 0.0,
            "avg_qa_score": round(sum(scores) / len(scores), 2) if scores else 0.0,
            "avg_latency_ms": round(sum(latencies) / len(latencies)) if latencies else 0,
        })
    return breakdown


def _build_task_results(data: dict, manifest=None) -> tuple[list[dict], list[dict]]:
    task_results = []
    error_tasks = []
    is_v2 = _manifest_v2_available(manifest)
    for r in data.get("results", []):
        entry = {
            "task_id": r.get("task_id", ""),
            "sector": r.get("sector", ""),
            "occupation": r.get("occupation", ""),
            "status": r.get("status", ""),
            "retried": bool(r.get("retried", False)),
            "files_count": r.get("deliverable_files_count", len(r.get("deliverable_files", []))),
            "qa_score": r.get("qa_score"),
            "qa_passed": r.get("qa_passed"),
            "qa_issues": r.get("qa_issues", []),
            "qa_suggestion": r.get("qa_suggestion", ""),
            "latency_ms": r.get("latency_ms", 0),
            "observability": r.get("observability", {}),
            "deliverable_summary": (r.get("deliverable_text") or "")[:300],
            # task context fields (for detail modal)
            "instruction": (r.get("instruction") or "")[:2000],
            "reference_file_urls": r.get("reference_file_urls", []),
            "deliverable_files": r.get("deliverable_files", []),
        }
        if is_v2:
            task_id = r.get("task_id", "")
            entry["prompt_classification"] = manifest.prompt_classification(task_id)
            entry["policy_results"] = {
                p: manifest.policy_result(task_id, p)
                for p in NEEDS_FILES_POLICIES_KNOWN
            }
            entry["has_deliverable_files"] = manifest.has_deliverable_files(task_id)
        task_results.append(entry)
        if r.get("error"):
            error_tasks.append({
                "task_id": r.get("task_id", ""),
                "sector": r.get("sector", ""),
                "occupation": r.get("occupation", ""),
                "error": r.get("error", ""),
            })
    return task_results, error_tasks


# ── LLM Narrative ─────────────────────────────────────────────────────────


def _generate_narrative(
    data: dict,
    summary: dict,
    sector_breakdown: list[dict],
    grade: dict | None = None,
) -> dict:
    """Call Azure OpenAI once and return narrative dict. Never crashes."""
    empty = {
        "overview": "",
        "quality_analysis": "",
        "failure_patterns": "",
        "recommendations": "",
        "grading_referenced": grade is not None,
        "grade_source": _build_grade_source(grade),
    }

    try:
        from core.llm_client import create_client, complete

        model = data.get("model", "gpt-5.2-chat")
        client = create_client()

        sector_lines = "\n".join(
            f"  - {s['sector']}: {s['success']}/{s['total']} success "
            f"(avg QA {s['avg_qa_score']:.1f}/10, avg latency {s['avg_latency_ms']}ms)"
            for s in sector_breakdown
        )

        error_count = summary["error_count"]
        retried_count = summary["retried_count"]
        grading_guard = _build_grading_guard_clause(grade)
        grading_results_section = _build_grading_results_section(grade)

        prompt_content = f"""You are a technical evaluator reviewing an LLM experiment run.

Experiment: {data.get("experiment_name", "")} ({data.get("experiment_id", "")})
Condition: {data.get("condition_name", "")}
Model: {model}
Execution Mode: {data.get("execution_mode", "")}
Date: {data.get("started_at", "")}

Summary:
  - Total tasks: {summary["total_tasks"]}
  - Success: {summary["success_count"]} ({summary["success_rate_pct"]}%)
  - Errors: {error_count}
  - Retried tasks: {retried_count}
  - Avg QA score: {summary["avg_qa_score"]}/10 (min {summary["min_qa_score"]}, max {summary["max_qa_score"]})
  - Avg latency: {summary["avg_latency_ms"]}ms

Sector breakdown:
{sector_lines}

IMPORTANT CONSTRAINTS:
{grading_guard}
- Focus ONLY on: task completion, Self-QA scores, latency patterns, sector/occupation observations, deliverable file generation quality.
- Write as a technical evaluator, NOT a marketer.
- Be concise and factual.

{grading_results_section}

Return ONLY valid JSON with these exact keys (no markdown code fences):
{{
  "overview": "2-3 paragraphs describing: what experiment was run, the task execution outcomes based on Self-QA confidence scores, and key highlights. IMPORTANT: These are self-assessed scores from the LLM during execution, NOT external grading results. Frame accordingly — use language like 'self-assessed confidence', 'task completion rate', 'LLM-evaluated quality' rather than 'performance score' or 'grading result'.",
  "quality_analysis": "2-3 paragraphs: QA score patterns, notable issues, occupation/sector observations",
  "failure_patterns": "Analysis of errors and retries. Empty string if no failures.",
  "recommendations": "2-3 actionable suggestions for improving the next experiment run"
}}"""

        messages = [
            {"role": "system", "content": "You are a precise technical evaluator. Return only valid JSON."},
            {"role": "user", "content": prompt_content},
        ]

        response, _ = complete(client, model, messages)
        raw = response.choices[0].message.content.strip()

        # Strip accidental markdown code fences
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        narrative = json.loads(raw)
        for key in ("overview", "quality_analysis", "failure_patterns", "recommendations"):
            if key not in narrative:
                narrative[key] = ""
        narrative["grading_referenced"] = grade is not None
        narrative["grade_source"] = _build_grade_source(grade)
        return narrative

    except Exception as exc:
        print(f"⚠️  Narrative LLM call failed: {exc}")
        result = dict(empty)
        result["_narrative_error"] = str(exc)
        return result


# ── Report builders ───────────────────────────────────────────────────────


def _build_report_data(data: dict, narrative: dict, summary: dict,
                       sector_breakdown: list[dict], task_results: list[dict],
                       error_tasks: list[dict],
                       execution_metrics: dict | None = None) -> dict:
    meta_date = (data.get("started_at") or "")[:10]
    report = {
        "meta": {
            "experiment_id": data.get("experiment_id", ""),
            "experiment_name": data.get("experiment_name", ""),
            "condition_name": data.get("condition_name", ""),
            "model": data.get("model", ""),
            "execution_mode": data.get("execution_mode", ""),
            "date": meta_date,
            "duration": data.get("duration", ""),
            "report_scope": "self_assessed_pre_grading",
        },
        "summary": summary,
        "sector_breakdown": sector_breakdown,
        "task_results": task_results,
        "error_tasks": error_tasks,
        "narrative": {
            "overview": narrative.get("overview", ""),
            "quality_analysis": narrative.get("quality_analysis", ""),
            "failure_patterns": narrative.get("failure_patterns", ""),
            "recommendations": narrative.get("recommendations", ""),
            "grading_referenced": bool(narrative.get("grading_referenced", False)),
            "grade_source": narrative.get("grade_source"),
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    if "_narrative_error" in narrative:
        report["narrative_error"] = narrative["_narrative_error"]
    if execution_metrics:
        report["execution_metrics"] = execution_metrics
    return report


def _compute_recovery_stats(results: list) -> dict:
    """Compute reflection and resume-round recovery statistics from task results.

    Reads:
      result["reflection_history"]  — list of {attempt, score, passed, undetermined}
      result["resume_round"]        — int, which resume round recovered this task (0 = initial)

    Returns:
      {
        "reflection": {
          "tasks_with_reflection": int,
          "avg_attempts": float,
          "per_attempt_avg_score": {"attempt_1": 5.8, "attempt_2": 7.2, ...},
          "improved": int,
          "no_change": int,
          "degraded": int,
        },
        "resume_rounds": {
          "rounds_used": int,
          "per_round": {
              "1": { "attempted": 10, "recovered": 8, "still_failed": 2 },
              ...
          }
        }
      }
    """
    # ── Reflection stats ──────────────────────────────────────────────────
    tasks_with_reflection = 0
    total_attempts = 0
    improved = 0
    no_change = 0
    degraded = 0
    attempt_scores: dict[str, list] = defaultdict(list)

    for r in results:
        history = r.get("reflection_history", [])
        if len(history) <= 1:
            # Skip tasks that never retried — they have no reflection effect
            continue

        tasks_with_reflection += 1
        total_attempts += len(history)

        for entry in history:
            key = f"attempt_{entry['attempt']}"
            if entry.get("score") is not None:
                attempt_scores[key].append(entry["score"])

        first_score = history[0].get("score")
        last_score = history[-1].get("score")
        if first_score is not None and last_score is not None:
            if last_score > first_score:
                improved += 1
            elif last_score == first_score:
                no_change += 1
            else:
                degraded += 1

    avg_attempts = round(total_attempts / tasks_with_reflection, 2) if tasks_with_reflection else 0

    per_attempt_avg: dict[str, Any] = {}
    for key in sorted(attempt_scores.keys()):
        scores = [s for s in attempt_scores[key] if s is not None]
        per_attempt_avg[key] = round(sum(scores) / len(scores), 2) if scores else None

    reflection_stats = {
        "tasks_with_reflection": tasks_with_reflection,
        "avg_attempts": avg_attempts,
        "per_attempt_avg_score": per_attempt_avg,
        "improved": improved,
        "no_change": no_change,
        "degraded": degraded,
    }

    # ── Resume round stats ────────────────────────────────────────────────
    round_data: dict[str, dict] = defaultdict(lambda: {"attempted": 0, "recovered": 0, "still_failed": 0})
    max_round = 0

    for r in results:
        rnd = r.get("resume_round")
        if not rnd:
            continue
        max_round = max(max_round, rnd)
        round_data[str(rnd)]["attempted"] += 1
        if r.get("status") == "success":
            round_data[str(rnd)]["recovered"] += 1
        else:
            round_data[str(rnd)]["still_failed"] += 1

    resume_stats = {
        "rounds_used": max_round,
        "per_round": dict(round_data),
    }

    return {
        "reflection": reflection_stats,
        "resume_rounds": resume_stats,
    }


def _build_markdown(rd: dict) -> str:
    meta = rd["meta"]
    summary = rd["summary"]
    narrative = rd["narrative"]
    sector_breakdown = rd["sector_breakdown"]
    task_results = rd["task_results"]
    error_tasks = rd["error_tasks"]

    lines: list[str] = []

    # 1. Header
    hf_user = "HyeonSang"
    experiment_id = meta['experiment_id']
    hf_base = f"https://huggingface.co/datasets/{hf_user}/{experiment_id}"
    lines += [
        f"# Experiment Report: {meta['experiment_name']}",
        "",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| **Experiment ID** | `{experiment_id}` |",
        f"| **Condition** | {meta['condition_name']} |",
        f"| **Model** | {meta['model']} |",
        f"| **Execution Mode** | {meta['execution_mode']} |",
        f"| **Date** | {meta['date']} |",
        f"| **Duration** | {meta['duration']} |",
        f"| **Generated At** | {rd['generated_at']} |",
        f"| 🤗 HF Dataset | [{experiment_id}]({hf_base}) |",
        f"| 📊 Self-Report | [self_report.json]({hf_base}/blob/main/self_report.json) |",
        f"| 📊 Grading | ⏳ Awaiting (`scores.json`) |",
        "",
    ]

    execution_metrics = rd.get("execution_metrics")
    if execution_metrics:
        valid_time = execution_metrics.get("avg_time_to_valid_artifact_ms")
        lines += [
            "## Job Performance",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Measured tasks | {execution_metrics['measured_tasks']} / {execution_metrics['total_tasks']} ({execution_metrics['coverage_pct']}%) |",
            f"| Avg job time | {execution_metrics['avg_task_wall_time_ms']:,.0f}ms |",
            f"| P50 job time | {execution_metrics['p50_task_wall_time_ms']:,.0f}ms |",
            f"| P95 job time | {execution_metrics['p95_task_wall_time_ms']:,.0f}ms |",
            f"| Avg time to valid artifact | {valid_time:,.0f}ms |" if valid_time is not None else "| Avg time to valid artifact | N/A |",
            f"| Tool calls | {execution_metrics['total_tool_calls']} |",
            f"| Execution attempts | {execution_metrics['total_execution_attempts']} |",
            "",
        ]

    # 2. Execution Summary
    if narrative.get("overview"):
        lines += [
            "## Execution Summary *(Self-Assessed, Pre-Grading)*",
            "",
            "> **Note:** This summary is based on the LLM's self-assessed confidence scores (Self-QA)"
            " during task execution — not on external grading results."
            " Actual grading scores from evaluators are not yet available at this stage.",
            "",
            narrative["overview"],
            "",
        ]

    # 3. Key Metrics
    lines += [
        "## Key Metrics",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total Tasks | {summary['total_tasks']} |",
        f"| Success | {summary['success_count']} ({summary['success_rate_pct']}%) |",
        f"| Errors | {summary['error_count']} |",
        f"| Retried Tasks | {summary['retried_count']} |",
        f"| Avg QA Score | {summary['avg_qa_score']}/10 |",
        f"| Min QA Score | {summary['min_qa_score']}/10 |",
        f"| Max QA Score | {summary['max_qa_score']}/10 |",
        f"| Avg Latency | {summary['avg_latency_ms']:,}ms |",
        f"| Max Latency | {summary['max_latency_ms']:,}ms |",
        f"| Total LLM Time | {summary['total_latency_ms'] // 1000}s |",
        "",
    ]

    # 4. File Generation
    fg = rd.get("file_generation") or {}
    if fg.get("needs_files_total") is not None:
        total_fg = fg["needs_files_total"]
        succeeded = fg["files_succeeded"]
        failed = fg["files_failed"]
        pct = round(succeeded / total_fg * 100, 1) if total_fg else 0.0
        lines += [
            "## File Generation",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Tasks requiring files | {total_fg} |",
            f"| Successfully generated | {succeeded} ({pct}%) |",
            f"| Failed → dummy created | {failed} |",
            "",
        ]

    # 5. Recovery Stats
    rc = rd.get("recovery_stats") or {}
    rf = rc.get("reflection") or {}
    rr = rc.get("resume_rounds") or {}
    if rf.get("tasks_with_reflection", 0) > 0:
        per_attempt = rf.get("per_attempt_avg_score") or {}
        lines += [
            "## Recovery Stats",
            "",
            "### Reflection (Self-QA Retry)",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Tasks with reflection retry | {rf['tasks_with_reflection']} |",
            f"| Avg attempts per retried task | {rf['avg_attempts']} |",
            f"| Improved after retry | {rf['improved']} |",
            f"| No change | {rf['no_change']} |",
            "",
        ]
        if per_attempt:
            lines += [
                "**Average QA score by attempt:**",
                "",
                "| Attempt | Avg Score |",
                "|---------|-----------|",
            ]
            attempt_labels = {"attempt_1": "1st", "attempt_2": "2nd", "attempt_3": "3rd"}
            for key in sorted(per_attempt.keys()):
                label = attempt_labels.get(key, key)
                lines.append(f"| {label} | {per_attempt[key]} |")
            lines.append("")

    if rr.get("rounds_used", 0) > 0:
        per_round = rr.get("per_round") or {}
        lines += [
            "### Resume Rounds",
            "",
            "| Round | Attempted | Recovered | Still Failed |",
            "|-------|-----------|-----------|--------------|",
        ]
        for rnd_key in sorted(per_round.keys(), key=lambda x: int(x)):
            rd_row = per_round[rnd_key]
            lines.append(
                f"| {rnd_key} | {rd_row['attempted']} | {rd_row['recovered']} | {rd_row['still_failed']} |"
            )
        lines.append("")

    # 6. Quality Analysis
    if narrative.get("quality_analysis"):
        lines += ["## Quality Analysis", "", narrative["quality_analysis"], ""]

    # 7. Sector Breakdown
    if sector_breakdown:
        lines += [
            "## Sector Breakdown",
            "",
            "| Sector | Tasks | Success | Success% | Avg QA | Avg Latency |",
            "|--------|-------|---------|----------|--------|-------------|",
        ]
        for s in sector_breakdown:
            lines.append(
                f"| {s['sector'][:40]} | {s['total']} | {s['success']} | "
                f"{s['success_rate_pct']}% | {s['avg_qa_score']}/10 | {s['avg_latency_ms']:,}ms |"
            )
        lines.append("")

    # 7. Task Results
    lines += [
        "## Task Results",
        "",
        "| # | Task ID | Sector | Occupation | Status | Retry | Files | QA Score | Latency |",
        "|---|---------|--------|------------|--------|-------|-------|----------|---------|",
    ]
    for i, r in enumerate(task_results, 1):
        status_icon = "✅" if r["status"] == "success" else ("⚠️" if r["status"] == "qa_failed" else "❌")
        retry_str = "Yes" if r["retried"] else "-"
        qa_str = f"{r['qa_score']}/10" if r["qa_score"] is not None else "-"
        task_short = (r["task_id"] or "")[:8] + "…" if len(r.get("task_id", "")) > 8 else r.get("task_id", "")
        occ_short = (r["occupation"] or "")[:18]
        lines.append(
            f"| {i} | `{task_short}` | {r['sector'][:22]} | {occ_short} | "
            f"{status_icon} {r['status']} | {retry_str} | {r['files_count']} | "
            f"{qa_str} | {r['latency_ms']:.0f}ms |"
        )
    lines.append("")

    # 8. QA Issues
    tasks_with_issues = [r for r in task_results if r.get("qa_issues")]
    if tasks_with_issues:
        lines += ["## QA Issues", ""]
        for r in tasks_with_issues:
            icon = "✅" if r.get("qa_passed") else "❌"
            task_short = (r["task_id"] or "")[:8] + "…"
            lines.append(f"### {icon} `{task_short}` — score {r['qa_score']}/10")
            for issue in r["qa_issues"]:
                lines.append(f"- {issue}")
            if r.get("qa_suggestion"):
                lines.append(f"  > 💡 {r['qa_suggestion']}")
            lines.append("")

    # 9. Failure Analysis
    if error_tasks and narrative.get("failure_patterns"):
        lines += ["## Failure Analysis", "", narrative["failure_patterns"], ""]

    # 10. Recommendations
    if narrative.get("recommendations"):
        lines += ["## Recommendations", "", narrative["recommendations"], ""]

    # 11. Deliverable Files
    files_tasks = [r for r in task_results if r.get("files_count", 0) > 0]
    if files_tasks:
        lines += ["## Deliverable Files", ""]
        for r in files_tasks:
            task_short = (r["task_id"] or "")[:8] + "…"
            lines.append(f"- `{task_short}` ({r['sector']}): {r['files_count']} file(s)")
        lines.append("")

    return "\n".join(lines)


def _build_html(rd: dict) -> str:
    """Build a standalone HTML report with all CSS/JS inline."""
    meta = rd["meta"]
    summary = rd["summary"]
    narrative = rd["narrative"]
    sector_breakdown = rd["sector_breakdown"]
    task_results = rd["task_results"]
    error_tasks = rd["error_tasks"]

    def esc(s: str) -> str:
        return (str(s)
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;"))

    def nl2br(s: str) -> str:
        return esc(s).replace("\n\n", "</p><p>").replace("\n", "<br>")

    # Embed report_data as inline JS
    data_json = json.dumps(
        rd,
        ensure_ascii=False,
        indent=2,
        default=str,
        allow_nan=False,
    )

    # File generation metric card
    fg = rd.get("file_generation") or {}
    fg_total = fg.get("needs_files_total")
    fg_succeeded = fg.get("files_succeeded")
    if fg_total is not None and fg_total > 0:
        fg_pct = round(fg_succeeded / fg_total * 100, 1)
        fg_card = (
            f'<div class="card">'
            f'<div class="label">File Gen Rate</div>'
            f'<div class="value">{fg_pct}%</div>'
            f'<div class="sub">{fg_succeeded} / {fg_total} tasks</div>'
            f'</div>'
        )
    else:
        fg_card = ""

    # Reflection metric card
    rc = rd.get("recovery_stats") or {}
    rf = rc.get("reflection") or {}
    rr = rc.get("resume_rounds") or {}
    reflection_card = ""
    if rf.get("tasks_with_reflection", 0) > 0:
        per_attempt = rf.get("per_attempt_avg_score") or {}
        score_trend = " → ".join(
            str(per_attempt[k]) for k in sorted(per_attempt.keys()) if per_attempt[k] is not None
        )
        reflection_card = (
            f'<div class="card">'
            f'<div class="label">Reflection Retries</div>'
            f'<div class="value">{rf["tasks_with_reflection"]}</div>'
            f'<div class="sub">Score: {score_trend}</div>'
            f'</div>'
        )

    # Resume rounds metric card
    resume_card = ""
    if rr.get("rounds_used", 0) > 0:
        per_round = rr.get("per_round") or {}
        total_recovered = sum(v["recovered"] for v in per_round.values())
        total_attempted = sum(v["attempted"] for v in per_round.values())
        recovery_pct = round(total_recovered / total_attempted * 100, 1) if total_attempted else 0
        resume_card = (
            f'<div class="card">'
            f'<div class="label">Resume Rounds</div>'
            f'<div class="value">{rr["rounds_used"]}</div>'
            f'<div class="sub">{total_recovered}/{total_attempted} recovered ({recovery_pct}%)</div>'
            f'</div>'
        )

    # Sector rows
    sector_rows = ""
    for s in sector_breakdown:
        sector_rows += (
            f"<tr><td>{esc(s['sector'])}</td><td>{s['total']}</td>"
            f"<td>{s['success']}</td><td>{s['success_rate_pct']}%</td>"
            f"<td>{s['avg_qa_score']}/10</td><td>{s['avg_latency_ms']:,}ms</td></tr>\n"
        )

    # Task rows
    task_rows = ""
    for i, r in enumerate(task_results, 1):
        status_cls = "success" if r["status"] == "success" else ("warn" if r["status"] == "qa_failed" else "error")
        status_icon = "✅" if r["status"] == "success" else ("⚠️" if r["status"] == "qa_failed" else "❌"
        )
        qa_str = f"{r['qa_score']}/10" if r["qa_score"] is not None else "—"
        retry_str = "Yes" if r["retried"] else "—"
        task_short = (r["task_id"] or "")[:10]
        occ_short = (r["occupation"] or "")[:20]
        task_rows += (
            f"<tr class='{status_cls}'>"
            f"<td>{i}</td><td><code>{esc(task_short)}</code></td>"
            f"<td>{esc(r['sector'][:25])}</td><td>{esc(occ_short)}</td>"
            f"<td>{status_icon} {esc(r['status'])}</td>"
            f"<td>{retry_str}</td><td>{r['files_count']}</td>"
            f"<td>{qa_str}</td><td>{r['latency_ms']:.0f}ms</td></tr>\n"
        )

    # QA issues section
    qa_issues_html = ""
    for r in task_results:
        if r.get("qa_issues"):
            icon = "✅" if r.get("qa_passed") else "❌"
            task_short = (r["task_id"] or "")[:10]
            qa_issues_html += f"<div class='qa-issue'><h4>{icon} <code>{esc(task_short)}</code> — score {r['qa_score']}/10</h4><ul>"
            for issue in r["qa_issues"]:
                qa_issues_html += f"<li>{esc(issue)}</li>"
            qa_issues_html += "</ul>"
            if r.get("qa_suggestion"):
                qa_issues_html += f"<p class='suggestion'>💡 {esc(r['qa_suggestion'])}</p>"
            qa_issues_html += "</div>"

    failure_section = ""
    if error_tasks and narrative.get("failure_patterns"):
        failure_section = f"""
        <section>
            <h2>Failure Analysis</h2>
            <div class='narrative'><p>{nl2br(narrative['failure_patterns'])}</p></div>
        </section>"""

    recommendations_section = ""
    if narrative.get("recommendations"):
        recommendations_section = f"""
        <section>
            <h2>Recommendations</h2>
            <div class='narrative'><p>{nl2br(narrative['recommendations'])}</p></div>
        </section>"""

    qa_issues_section = ""
    if qa_issues_html:
        qa_issues_section = f"""
        <section>
            <h2>QA Issues</h2>
            {qa_issues_html}
        </section>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Experiment Report: {esc(meta['experiment_name'])}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         background: #f5f7fa; color: #1a1a2e; line-height: 1.6; }}
  header {{ background: #1a1a2e; color: #fff; padding: 24px 40px; }}
  header h1 {{ font-size: 1.6rem; font-weight: 700; }}
  header p {{ opacity: 0.75; font-size: 0.9rem; margin-top: 6px; }}
  .container {{ max-width: 1200px; margin: 0 auto; padding: 32px 24px; }}
  .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
            gap: 16px; margin-bottom: 32px; }}
  .card {{ background: #fff; border-radius: 10px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,.07); }}
  .card .label {{ font-size: 0.75rem; text-transform: uppercase; letter-spacing: .05em;
                  color: #888; margin-bottom: 4px; }}
  .card .value {{ font-size: 1.8rem; font-weight: 700; color: #1a1a2e; }}
  .card .sub {{ font-size: 0.8rem; color: #888; margin-top: 2px; }}
  section {{ background: #fff; border-radius: 10px; padding: 28px 32px;
             box-shadow: 0 2px 8px rgba(0,0,0,.07); margin-bottom: 24px; }}
  h2 {{ font-size: 1.2rem; font-weight: 700; margin-bottom: 16px;
        padding-bottom: 10px; border-bottom: 2px solid #eef0f4; color: #1a1a2e; }}
  h4 {{ font-size: 0.95rem; margin: 12px 0 6px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.875rem; }}
  th {{ background: #f0f2f8; padding: 10px 12px; text-align: left;
        font-weight: 600; color: #555; white-space: nowrap; }}
  td {{ padding: 8px 12px; border-bottom: 1px solid #eef0f4; vertical-align: middle; }}
  tr:last-child td {{ border-bottom: none; }}
  tr.success td {{ background: #f0faf4; }}
  tr.error td {{ background: #fff5f5; }}
  tr.warn td {{ background: #fffbf0; }}
  tr:hover td {{ filter: brightness(0.97); }}
  code {{ background: #f0f2f8; padding: 2px 6px; border-radius: 4px;
          font-family: 'SF Mono', Consolas, monospace; font-size: 0.85em; }}
  .narrative {{ color: #333; font-size: 0.93rem; }}
  .narrative p {{ margin-bottom: 12px; }}
  .qa-issue {{ border-left: 3px solid #e0a000; padding: 10px 16px; margin: 12px 0;
               background: #fffbf0; border-radius: 0 6px 6px 0; }}
  .qa-issue ul {{ margin: 6px 0 0 16px; }}
  .suggestion {{ color: #666; font-style: italic; margin-top: 6px; font-size: 0.9rem; }}
  .meta-table td {{ padding: 6px 12px; }}
  .meta-table td:first-child {{ font-weight: 600; width: 160px; color: #555; }}
  footer {{ text-align: center; padding: 24px; color: #aaa; font-size: 0.8rem; }}
</style>
</head>
<body>

<header>
  <h1>📊 {esc(meta['experiment_name'])}</h1>
  <p>{esc(meta['experiment_id'])} · {esc(meta['condition_name'])} · {esc(meta['model'])} · {esc(meta['execution_mode'])}</p>
</header>

<div class="container">

  <!-- Metric Cards -->
  <div class="cards">
    <div class="card">
      <div class="label">Total Tasks</div>
      <div class="value">{summary['total_tasks']}</div>
    </div>
    <div class="card">
      <div class="label">Success Rate</div>
      <div class="value">{summary['success_rate_pct']}%</div>
      <div class="sub">{summary['success_count']} / {summary['total_tasks']}</div>
    </div>
    <div class="card">
      <div class="label">Avg QA Score</div>
      <div class="value">{summary['avg_qa_score']}</div>
      <div class="sub">out of 10</div>
    </div>
    <div class="card">
      <div class="label">Errors</div>
      <div class="value">{summary['error_count']}</div>
    </div>
    <div class="card">
      <div class="label">Retried</div>
      <div class="value">{summary['retried_count']}</div>
    </div>
    {fg_card}
    {reflection_card}
    {resume_card}
    <div class="card">
      <div class="label">Avg Latency</div>
      <div class="value">{summary['avg_latency_ms']:,}</div>
      <div class="sub">ms</div>
    </div>
  </div>

  <!-- Experiment Meta -->
  <section>
    <h2>Experiment Details</h2>
    <table class="meta-table">
      <tr><td>Experiment ID</td><td><code>{esc(meta['experiment_id'])}</code></td></tr>
      <tr><td>Condition</td><td>{esc(meta['condition_name'])}</td></tr>
      <tr><td>Model</td><td>{esc(meta['model'])}</td></tr>
      <tr><td>Execution Mode</td><td>{esc(meta['execution_mode'])}</td></tr>
      <tr><td>Date</td><td>{esc(meta['date'])}</td></tr>
      <tr><td>Duration</td><td>{esc(meta['duration'])}</td></tr>
      <tr><td>Generated At</td><td>{esc(rd['generated_at'])}</td></tr>
    </table>
  </section>

  <!-- Execution Summary -->
  {f'''<section>
    <h2>Execution Summary (Self-Assessed)</h2>
    <p class="narrative" style="color:#888;font-size:0.85rem;margin-bottom:12px;">Based on LLM self-QA confidence scores · External grading scores not yet available</p>
    <div class="narrative"><p>{nl2br(narrative['overview'])}</p></div>
  </section>''' if narrative.get('overview') else ''}

  <!-- Quality Analysis -->
  {f'''<section>
    <h2>Quality Analysis</h2>
    <div class="narrative"><p>{nl2br(narrative['quality_analysis'])}</p></div>
  </section>''' if narrative.get('quality_analysis') else ''}

  <!-- Sector Breakdown -->
  <section>
    <h2>Sector Breakdown</h2>
    <table>
      <thead>
        <tr><th>Sector</th><th>Tasks</th><th>Success</th><th>Success%</th><th>Avg QA</th><th>Avg Latency</th></tr>
      </thead>
      <tbody>
        {sector_rows}
      </tbody>
    </table>
  </section>

  <!-- Task Results -->
  <section>
    <h2>Task Results</h2>
    <table>
      <thead>
        <tr><th>#</th><th>Task ID</th><th>Sector</th><th>Occupation</th><th>Status</th>
            <th>Retry</th><th>Files</th><th>QA Score</th><th>Latency</th></tr>
      </thead>
      <tbody>
        {task_rows}
      </tbody>
    </table>
  </section>

  {qa_issues_section}
  {failure_section}
  {recommendations_section}

</div>

<footer>Generated by step6_report.py · {esc(rd['generated_at'])}</footer>

<script>
// Embedded report data for dashboard consumption
const report_data = {data_json};
// Export for external scripts
if (typeof window !== 'undefined') {{ window.report_data = report_data; }}
</script>
</body>
</html>"""


# ── Output path resolution ────────────────────────────────────────────────


def _resolve_output_dir(explicit_output_dir: Path = None) -> Path:
    """Resolve the report output directory.

    Priority:
      1. CLI --output-dir argument (explicit override)
      2. results/<experiment_id>/report/  (experiment-scoped, preferred)
      3. workspace/report/  (fallback)

    Creates the directory if it does not exist.
    """
    if explicit_output_dir is not None:
        out = Path(explicit_output_dir)
        out.mkdir(parents=True, exist_ok=True)
        return out

    # Try to read experiment_id from workspace JSON files
    experiment_id = None
    for json_path in [
        WORKSPACE_DIR / "step2_inference_results.json",
        WORKSPACE_DIR / "step1_tasks_prepared.json",
    ]:
        if json_path.exists():
            try:
                data = json.loads(json_path.read_text())
                experiment_id = data.get("experiment_id", "").strip()
                if experiment_id:
                    break
            except Exception:
                pass

    if experiment_id:
        # batch-runner/results/<experiment_id>/report/
        out = _SCRIPT_DIR / "results" / experiment_id / "report"
    else:
        # fallback
        out = WORKSPACE_DIR / "report"

    out.mkdir(parents=True, exist_ok=True)
    return out


# ── Main ──────────────────────────────────────────────────────────────────


def generate_report(result_json_path: Path, output_dir: Path, no_narrative: bool = False) -> None:
    print("============================================================")
    print("📝 Step 6: Generate Experiment Report")
    print("============================================================")

    result_path = _find_result_json(result_json_path)
    print(f"   Input:  {result_path}")
    print(f"   Output: {output_dir}")

    with open(result_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Compute metrics
    summary = _compute_summary(data)
    execution_metrics = _compute_execution_metrics(data)
    sector_breakdown = _compute_sector_breakdown(data)
    manifest = _load_manifest_safe()
    task_results, error_tasks = _build_task_results(data, manifest=manifest)

    # Generate narrative
    if no_narrative:
        narrative: dict = {
            "overview": "",
            "quality_analysis": "",
            "failure_patterns": "",
            "recommendations": "",
            "grading_referenced": False,
            "grade_source": None,
        }
        print("   Skipping narrative (--no-narrative)")
    else:
        grade = _load_grade_for_experiment(data.get("experiment_id", ""))
        # Try GPT-5.4 Pro (Responses API) first, fallback to standard
        try:
            from core.narrative_analyzer import create_narrative_analyzer
            print("   Generating narrative via GPT-5.4 Pro (Responses API)…")
            analyzer = create_narrative_analyzer()
            result = analyzer.analyze(
                data, summary, sector_breakdown, task_results, error_tasks, grade=grade
            )
            narrative = {
                "overview": result.overview,
                "quality_analysis": result.quality_analysis,
                "failure_patterns": result.failure_patterns,
                "recommendations": result.recommendations,
                "grading_referenced": result.grading_referenced,
                "grade_source": result.grade_source,
            }
            total_ms = result.call_1_latency_ms + result.call_2_latency_ms
            print(f"   ✅ Pro narrative generated ({total_ms:,.0f}ms, "
                  f"{result.total_tokens['input']:,}+{result.total_tokens['output']:,} tokens)")
        except Exception as exc:
            print(f"   ⚠️ Pro narrative failed: {exc}")
            print(f"   Falling back to standard narrative…")
            narrative = _generate_narrative(data, summary, sector_breakdown, grade=grade)

    # Build report_data.json
    rd = _build_report_data(
        data,
        narrative,
        summary,
        sector_breakdown,
        task_results,
        error_tasks,
        execution_metrics=execution_metrics,
    )

    # Inject file generation stats from step5_validate.py
    validate_stats_path = WORKSPACE_DIR / "validate_stats.json"
    file_generation = None
    if validate_stats_path.exists():
        with open(validate_stats_path, "r", encoding="utf-8") as f:
            file_generation = json.load(f)
    rd["file_generation"] = file_generation or {
        "needs_files_total": None,
        "files_succeeded": None,
        "files_failed": None,
        "dummy_files_created": None,
        "dummy_task_ids": [],
    }

    # V2 manifest summary fields (append-only; absent for v1 / missing manifest)
    v2_fields = _v2_summary_fields(manifest)
    if v2_fields:
        rd["file_generation"].update(v2_fields)

    # Inject recovery stats — read from step2_inference_results.json (has reflection_history)
    inference_results_path = WORKSPACE_DIR / "step2_inference_results.json"
    if inference_results_path.exists():
        with open(inference_results_path, "r", encoding="utf-8") as f:
            inference_data = json.load(f)
        results_for_recovery = inference_data.get("results", [])
    else:
        results_for_recovery = data.get("results", [])
    rd["recovery_stats"] = _compute_recovery_stats(results_for_recovery)

    json_path = output_dir / "report_data.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(
            rd,
            f,
            indent=2,
            ensure_ascii=False,
            default=str,
            allow_nan=False,
        )

    # Build report.md
    md_path = output_dir / "report.md"
    md_path.write_text(_build_markdown(rd), encoding="utf-8")

    # NOTE: report.html generation disabled — large HTML files skew GitHub language stats.
    # html_path = output_dir / "report.html"
    # html_path.write_text(_build_html(rd), encoding="utf-8")

    # Copy report_data.json → workspace/upload/self_report.json (for step7 HF upload)
    upload_dir = WORKSPACE_DIR / "upload"
    if upload_dir.exists():
        self_report_path = upload_dir / "self_report.json"
        shutil.copy2(json_path, self_report_path)
        print(f"   ✓ Copied self_report.json → {self_report_path}")

    print(f"\n✅ Step 6 complete:")
    print(f"   {json_path}")
    print(f"   {md_path}")
    print(f"\n   Tasks: {summary['total_tasks']}  "
          f"Success: {summary['success_count']} ({summary['success_rate_pct']}%)  "
          f"Errors: {summary['error_count']}")
    print(f"   Avg QA: {summary['avg_qa_score']}/10  "
          f"Avg Latency: {summary['avg_latency_ms']:,}ms")
    if "narrative_error" in rd:
        print(f"\n   ⚠️  Narrative error: {rd['narrative_error']}")


def main():
    parser = argparse.ArgumentParser(description="Generate experiment report from result.json")
    parser.add_argument(
        "--result-json",
        type=Path,
        default=DEFAULT_RESULT_JSON,
        help=f"Path to result JSON (default: {DEFAULT_RESULT_JSON})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory for report files (default: results/<experiment_id>/report/)",
    )
    parser.add_argument(
        "--no-narrative",
        action="store_true",
        help="Skip LLM narrative generation (metrics only)",
    )
    args = parser.parse_args()

    output_dir = _resolve_output_dir(args.output_dir)

    generate_report(
        result_json_path=args.result_json,
        output_dir=output_dir,
        no_narrative=args.no_narrative,
    )


if __name__ == "__main__":
    main()
