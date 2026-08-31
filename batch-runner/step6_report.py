#!/usr/bin/env python3
"""Step 6: Generate Experiment Report

Reads workspace/result.json and generates two output files under workspace/report/:
  - report_data.json : structured JSON for dashboard rendering
  - report.md        : human-readable Markdown report

Narrative sections use the two-call GPT-5.6 Sol 1M Max analyzer with a sanitized
model-free fallback. Step 6 always emits a pre-grading report; external grading
remains a separate pipeline.

Usage:
    python step6_report.py                          # default: workspace/result.json
    python step6_report.py --result-json path/to/result.json
    python step6_report.py --output-dir path/to/report/
    python step6_report.py --no-narrative           # skip LLM call
    python step6_report.py --dry-run                 # mark report unpublished
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Path setup ────────────────────────────────────────────────────────────

_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR))

from core.config import NEEDS_FILES_POLICIES_KNOWN, WORKSPACE_DIR  # noqa: E402
from core.cost_projection import (  # noqa: E402
    COST_FIELDS,
    build_cost_summaries,
    project_cost_ledger_reference,
    project_cost_receipt,
    stage_cost_ledger,
    successful_deliverable_count,
    verify_cost_ledger,
)
from core.execution_metrics import bounded_count, bounded_duration_ms  # noqa: E402
from core.prepared_fingerprint import FINGERPRINT_RE  # noqa: E402
from core.result_fingerprint import RESULT_FINGERPRINT_RE  # noqa: E402
from core.publication_generation import validate_publication_generation  # noqa: E402
from core.public_error import public_task_error  # noqa: E402
from core.repository_identity import (  # noqa: E402
    validate_experiment_id,
    validate_hf_dataset_repo_id,
)


# ── Defaults ──────────────────────────────────────────────────────────────

DEFAULT_RESULT_JSON = WORKSPACE_DIR / "result.json"
DEFAULT_OUTPUT_DIR = WORKSPACE_DIR / "report"


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


def _validated_source_repo_id(data: dict) -> str | None:
    """Return a safe HF repository ID, preserving old reports with no source."""
    source = data.get("source_repo_id")
    if source in (None, ""):
        return None
    try:
        return validate_hf_dataset_repo_id(source)
    except ValueError as exc:
        raise ValueError(
            "Result JSON contains an invalid source repository"
        ) from exc


def _validated_experiment_id(data: dict) -> str:
    try:
        return validate_experiment_id(data.get("experiment_id"))
    except ValueError as exc:
        raise ValueError(
            "Result JSON contains an invalid experiment identifier"
        ) from exc


def _validated_report_provenance(data: dict) -> dict:
    """Preserve current pipeline identity while allowing legacy reports."""
    fingerprint = data.get("prepared_fingerprint")
    result_fingerprint = data.get("result_fingerprint")
    publication_generation = data.get("publication_generation")
    ordered_task_ids = data.get("ordered_task_ids")
    if (
        fingerprint is None
        and result_fingerprint is None
        and publication_generation is None
        and ordered_task_ids is None
    ):
        return {}
    publication_generation = validate_publication_generation(
        publication_generation
    )
    if (
        not isinstance(fingerprint, str)
        or FINGERPRINT_RE.fullmatch(fingerprint) is None
    ):
        raise ValueError("Result JSON contains an invalid prepared fingerprint")
    if (
        not isinstance(result_fingerprint, str)
        or RESULT_FINGERPRINT_RE.fullmatch(result_fingerprint) is None
    ):
        raise ValueError("Result JSON contains an invalid result fingerprint")
    if (
        not isinstance(ordered_task_ids, list)
        or not ordered_task_ids
        or any(
            not isinstance(task_id, str) or not task_id
            for task_id in ordered_task_ids
        )
        or len(ordered_task_ids) != len(set(ordered_task_ids))
    ):
        raise ValueError("Result JSON contains an invalid ordered task identity")
    results = data.get("results")
    result_task_ids = [
        result.get("task_id") if isinstance(result, dict) else None
        for result in results
    ] if isinstance(results, list) else None
    if result_task_ids != ordered_task_ids:
        raise ValueError("Result JSON task set differs from ordered task identity")
    return {
        "publication_generation": publication_generation,
        "prepared_fingerprint": fingerprint,
        "result_fingerprint": result_fingerprint,
        "ordered_task_ids": list(ordered_task_ids),
    }


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


def _compute_agentic_metrics(data: dict) -> dict | None:
    """Aggregate privacy-bounded agentic metrics; omit for legacy runs."""
    results = data.get("results", [])
    measured: list[tuple[dict, dict, float]] = []
    for result in results:
        raw = (result.get("observability") or {}).get("agentic_metrics")
        if not isinstance(raw, dict):
            continue
        wall_time = _metric_number(raw.get("task_wall_time_ms"))
        if wall_time is not None:
            measured.append((result, raw, wall_time))
    if not measured:
        return None

    def count(field: str) -> int:
        return sum(
            value
            for _, raw, _ in measured
            if (value := bounded_count(raw.get(field))) is not None
        )

    tool_times = [
        value
        for _, raw, _ in measured
        if (value := _metric_number(raw.get("tool_time_ms"))) is not None
    ]
    total_tool_calls = count("tool_calls")
    total_tool_errors = count("tool_errors")
    tasks_with_tool_errors = sum(
        1
        for _, raw, _ in measured
        if (bounded_count(raw.get("tool_errors")) or 0) > 0
    )
    recovered_tasks = sum(
        1
        for result, raw, _ in measured
        if result.get("status") == "success"
        and raw.get("recovered_after_tool_error") is True
    )
    tool_names = (
        "inspect_workspace", "inspect_environment", "run_python",
        "run_ffmpeg", "inspect_artifacts", "finalize",
    )
    calls_by_name = {name: 0 for name in tool_names}
    terminal_categories: dict[str, int] = {}
    conservative_cost = 0.0
    for _, raw, _ in measured:
        raw_calls = raw.get("tool_calls_by_name")
        if isinstance(raw_calls, dict):
            for name in tool_names:
                calls_by_name[name] += bounded_count(raw_calls.get(name)) or 0
        category = raw.get("terminal_error_category")
        if isinstance(category, str) and category and len(category) <= 80:
            terminal_categories[category] = terminal_categories.get(category, 0) + 1
        value = raw.get("conservative_cost_usd")
        if (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
            and 0 <= value <= 1_000_000
        ):
            conservative_cost += float(value)

    usage_complete_tasks = sum(
        1 for _, raw, _ in measured if raw.get("usage_complete") is True
    )
    return {
        "schema_version": "1.0",
        "measured_tasks": len(measured),
        "total_tasks": len(results),
        "coverage_pct": round(len(measured) / len(results) * 100, 1)
        if results else 0.0,
        "total_model_api_calls": count("model_api_calls"),
        "total_model_iterations": count("model_iterations"),
        "total_tool_calls": total_tool_calls,
        "total_tool_errors": total_tool_errors,
        "tool_error_rate_pct": round(
            total_tool_errors / total_tool_calls * 100, 2
        ) if total_tool_calls else 0.0,
        "tasks_with_tool_errors": tasks_with_tool_errors,
        "recovered_tasks": recovered_tasks,
        "recovery_rate_pct": round(
            recovered_tasks / tasks_with_tool_errors * 100, 2
        ) if tasks_with_tool_errors else 0.0,
        "total_finalize_attempts": count("finalize_attempts"),
        "total_finalize_required_corrections": count(
            "finalize_required_corrections"
        ),
        "total_capability_misses": count("capability_misses"),
        "p50_tool_time_ms": _percentile(tool_times, 0.50),
        "p95_tool_time_ms": _percentile(tool_times, 0.95),
        "total_input_tokens": count("input_tokens"),
        "total_output_tokens": count("output_tokens"),
        "total_cached_tokens": count("cached_tokens"),
        "usage_complete_tasks": usage_complete_tasks,
        "usage_coverage_pct": round(
            usage_complete_tasks / len(measured) * 100, 1
        ),
        "conservative_cost_usd": round(conservative_cost, 8),
        "tool_calls_by_name": calls_by_name,
        "terminal_error_categories": dict(sorted(terminal_categories.items())),
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


def _task_cost_receipts(result: dict) -> dict:
    """Re-project the cost receipts carried on one result row.

    Step 6 can be pointed at any ``result.json`` via ``--result-json``, so the
    receipts are re-read through the contract rather than trusted. A receipt
    that no longer parses raises here instead of being quietly averaged into a
    headline figure.
    """
    label = result.get("task_id") or "unknown task"
    receipts = {}
    for field in COST_FIELDS:
        receipt = project_cost_receipt(result.get(field), f"report {field} for {label}")
        if receipt is not None:
            receipts[field] = receipt
    return receipts


def _compute_cost_summaries(data: dict) -> dict:
    """Aggregate the per-task cost receipts; empty for uninstrumented runs.

    An experiment that recorded nothing yields no summaries at all, so it
    renders as "no record" rather than as a run that cost nothing.
    """
    rows = [
        {**result, **_task_cost_receipts(result)}
        for result in data.get("results", [])
    ]
    return build_cost_summaries(
        rows,
        successful_deliverables=successful_deliverable_count(rows),
    )


def _report_cost_ledger(data: dict, *, publishing: bool) -> dict | None:
    """Resolve the audit-sidecar pointer, staging the file when publishing.

    Step 2 names its export after the condition it recorded; a published
    repository holds one ledger under one fixed name. When this run owns the
    workspace it is producing that repository, so the file is copied across
    under the published name and the pointer is rewritten to match — the two
    have to agree or publication refuses the upload.

    Otherwise — reporting over a result that came from somewhere else — the
    pointer is carried through as it stands, verified if the file happens to
    be here. Nothing is being published, so nothing needs renaming.
    """
    reference = project_cost_ledger_reference(data.get("cost_ledger"))
    if reference is None:
        return None
    if not publishing:
        return verify_cost_ledger(reference, WORKSPACE_DIR / reference["path"])
    staged = stage_cost_ledger(
        reference, WORKSPACE_DIR, WORKSPACE_DIR / "upload"
    )
    if staged is None:
        print(
            f"   ⚠️  Cost ledger {reference['path']} is not in the workspace; "
            "publishing no ledger pointer"
        )
    return staged


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
        # Absent stays absent, exactly as it does upstream: a task with no
        # receipt gains no key, so the dashboard can tell "not recorded" from
        # "recorded as nothing".
        entry.update(_task_cost_receipts(r))
        task_results.append(entry)
        if r.get("error"):
            error_tasks.append({
                "task_id": r.get("task_id", ""),
                "sector": r.get("sector", ""),
                "occupation": r.get("occupation", ""),
                **public_task_error(r.get("error")),
            })
    return task_results, error_tasks


# ── LLM Narrative ─────────────────────────────────────────────────────────


def _model_free_narrative(error: Exception | None = None) -> dict:
    narrative = {
        "overview": "",
        "quality_analysis": "",
        "failure_patterns": "",
        "recommendations": "",
        "grading_referenced": False,
        "grade_source": None,
        "model": None,
        "reasoning_effort": None,
        "runtime_fingerprint": None,
    }
    if error is not None:
        narrative["_narrative_error"] = type(error).__name__
    return narrative


# ── Report builders ───────────────────────────────────────────────────────


def _build_report_data(data: dict, narrative: dict, summary: dict,
                       sector_breakdown: list[dict], task_results: list[dict],
                       error_tasks: list[dict],
                       execution_metrics: dict | None = None,
                       agentic_metrics: dict | None = None,
                       cost_summaries: dict | None = None,
                       cost_ledger: dict | None = None,
                       dry_run: bool = False) -> dict:
    meta_date = (data.get("started_at") or "")[:10]
    grading_referenced = bool(narrative.get("grading_referenced", False))
    report_meta = {
        "experiment_id": _validated_experiment_id(data),
        "experiment_name": data.get("experiment_name", ""),
        "condition_name": data.get("condition_name", ""),
        "model": data.get("model", ""),
        "execution_mode": data.get("execution_mode", ""),
        "date": meta_date,
        "duration": data.get("duration", ""),
        "source_repo_id": _validated_source_repo_id(data),
        "publication_plan": (
            "dry_run_no_step7" if dry_run else "step7_upload_requested"
        ),
        "report_scope": (
            "graded"
            if grading_referenced
            else "self_assessed_pre_grading"
        ),
        "narrative_runtime_fingerprint": narrative.get(
            "runtime_fingerprint"
        ),
        "narrative_model": narrative.get("model"),
        "narrative_reasoning_effort": narrative.get("reasoning_effort"),
    }
    report_meta.update(_validated_report_provenance(data))
    report = {
        "meta": report_meta,
        "summary": summary,
        "sector_breakdown": sector_breakdown,
        "task_results": task_results,
        "error_tasks": error_tasks,
        "narrative": {
            "overview": narrative.get("overview", ""),
            "quality_analysis": narrative.get("quality_analysis", ""),
            "failure_patterns": narrative.get("failure_patterns", ""),
            "recommendations": narrative.get("recommendations", ""),
            "grading_referenced": grading_referenced,
            "grade_source": narrative.get("grade_source"),
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    if "_narrative_error" in narrative:
        report["narrative_error"] = narrative["_narrative_error"]
    if execution_metrics:
        report["execution_metrics"] = execution_metrics
    if agentic_metrics:
        report["agentic_metrics"] = agentic_metrics
    if cost_summaries:
        report["cost_summary"] = dict(cost_summaries)
    if cost_ledger:
        report["cost_ledger"] = cost_ledger
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


_COST_STATUS_LABELS = {
    "complete": "complete",
    "partial": "partial — the figures below are a floor",
    "unavailable": "unavailable — nothing was recorded",
    "not_run": "not run",
}


def _cost_money(value) -> str:
    """Render an amount, keeping "not recorded" visibly apart from ``$0``."""
    return "no record" if value is None else f"${value:,.4f}"


def _failed_task_cost(cost: dict) -> str:
    """``N (amount)`` for failed work, with the amount honestly qualified.

    The number on its own is ambiguous in the one direction that matters. A
    failure that asked no model really did cost nothing, and a failure billed
    against a model absent from the price table also arrives as nothing --
    `_receipt_amount` returns None and the sum it never joined stays 0.0. Both
    printed `($0.0000)`. Which one a reader is looking at is decided by the
    count of failures that could be priced, never by the amount.

    A run whose failures were all priced prints exactly what it printed before,
    and so does a run with no failures at all: zero failures did cost zero.
    """
    failed = cost["failed_task_count"]
    # Absent on reports published before this count existed. There the amount
    # is trustworthy only when the whole run was priced, since a fully priced
    # run cannot contain an unpriced failure.
    measured = cost.get("failed_measured_tasks")
    if measured is None:
        measured = failed if cost["measured_tasks"] == cost["receipt_tasks"] else 0
    if failed == 0 or measured == failed:
        return f"{failed} ({_cost_money(cost['failed_task_cost_usd'])})"
    if measured == 0:
        return f"{failed} (no record)"
    # Some priced, some not: what is shown is a floor, and the reader is told
    # how much of the row it covers -- the same disclosure the `Priced` row
    # above makes about the run.
    return (
        f"{failed} ({_cost_money(cost['failed_task_cost_usd'])}, "
        f"{measured} / {failed} priced)"
    )


def _build_markdown(rd: dict) -> str:
    meta = rd["meta"]
    summary = rd["summary"]
    narrative = rd["narrative"]
    sector_breakdown = rd["sector_breakdown"]
    task_results = rd["task_results"]
    error_tasks = rd["error_tasks"]

    lines: list[str] = []

    # 1. Header
    experiment_id = meta['experiment_id']
    lines += [
        f"# Experiment Report: {meta['experiment_name']}",
        "",
        "| Field | Value |",
        "|-------|-------|",
        f"| **Experiment ID** | `{experiment_id}` |",
        f"| **Condition** | {meta['condition_name']} |",
        f"| **Model** | {meta['model']} |",
        f"| **Execution Mode** | {meta['execution_mode']} |",
        f"| **Date** | {meta['date']} |",
        f"| **Duration** | {meta['duration']} |",
        f"| **Generated At** | {rd['generated_at']} |",
    ]
    source_repo_id = meta.get("source_repo_id")
    if source_repo_id:
        hf_base = f"https://huggingface.co/datasets/{source_repo_id}"
        if meta.get("publication_plan") == "dry_run_no_step7":
            lines.append(
                f"| 🤗 HF Target (bootstrap) | [{source_repo_id}]({hf_base}) |"
            )
            lines.append("| 📊 Self-Report | Local artifact only (dry run; not published) |")
        else:
            lines.append(f"| 🤗 HF Target | [{source_repo_id}]({hf_base}) |")
            lines.append(
                "| 📊 Self-Report | Prepared locally; Step 7 upload requested "
                "but not verified by this report |"
            )
    else:
        lines.append("| 🤗 HF Target | Not recorded in this legacy result |")
    if narrative.get("grading_referenced"):
        grade_source = narrative.get("grade_source") or {}
        lines.append(
            "| 📊 Grading | Automated LLM-judge: "
            f"{grade_source.get('model', 'unknown')} / rubric "
            f"{grade_source.get('rubric_sha', 'unknown')} |"
        )
    else:
        lines.append("| 📊 Grading | ⏳ Awaiting external grading |")
    lines.append("")

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

    cost_summary = rd.get("cost_summary") or {}
    for field, label in (
        ("problem_solving_cost", "Problem-Solving Cost"),
        ("grading_cost", "Grading Cost"),
    ):
        cost = cost_summary.get(field)
        if not cost:
            continue
        # Every other money row below arrives as None when nothing could be
        # priced, so each renders "no record". `known_cost_usd` alone is forced
        # to 0.0 by the producer -- it is a sum over an empty set -- which left
        # the one row a reader takes as *the* number as the one row reading as
        # free. The exp026c smoke (run 33302056462) made two paid model calls
        # against a model the price table had no entry for and printed
        # "$0.0000" here, directly beside "Not priced | price_missing".
        #
        # Decided off `measured_tasks`, not off the amount, because the amount
        # cannot tell "priced, and it was free" apart from "never priced". The
        # dashboard's summaryTotalCell already splits it on the same field; the
        # producer's number is not touched, only how this row reads it.
        recorded = cost["known_cost_usd"] if cost["measured_tasks"] else None
        lines += [
            f"## {label}",
            "",
            "> Usage-based estimate, not an Azure invoice amount.",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Coverage | {cost['receipt_tasks']} / {cost['total_tasks']} tasks ({cost['coverage_pct']}%) |",
        ]
        # Coverage counts receipts, not amounts, so a run can be at 100% with
        # nothing priced. Only shown when the two disagree, which leaves a
        # fully-priced report byte-identical to what it printed before.
        if cost["measured_tasks"] != cost["receipt_tasks"]:
            lines.append(
                f"| Priced | {cost['measured_tasks']} / {cost['receipt_tasks']} receipts |"
            )
        lines += [
            f"| Receipt status | {_COST_STATUS_LABELS[cost['status']]} |",
            f"| {'Total' if cost['status'] == 'complete' else 'Recorded so far'} | {_cost_money(recorded)} |",
            f"| Average per task | {_cost_money(cost['avg_cost_usd'])} |",
            f"| Median | {_cost_money(cost['median_cost_usd'])} |",
            f"| P95 | {_cost_money(cost['p95_cost_usd'])} |",
            f"| Max | {_cost_money(cost['max_cost_usd'])} |",
        ]
        if field == "problem_solving_cost":
            lines.append(
                "| Per successful deliverable | "
                f"{_cost_money(cost['cost_per_successful_deliverable_usd'])} |"
            )
        # Failed work is reported, never netted out of the total.
        lines.append(f"| Failed tasks | {_failed_task_cost(cost)} |")
        if cost["missing_reasons"]:
            lines.append(f"| Not priced | {', '.join(cost['missing_reasons'])} |")
        lines.append("")

    cost_ledger = rd.get("cost_ledger")
    if cost_ledger:
        lines += [
            f"- 🧾 Cost ledger: `{cost_ledger['path']}` "
            f"(sha256 `{cost_ledger['sha256'][:12]}…`)",
            "",
        ]

    agentic_metrics = rd.get("agentic_metrics")
    if agentic_metrics:
        lines += [
            "## Agentic Tool Loop",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Measured tasks | {agentic_metrics['measured_tasks']} / {agentic_metrics['total_tasks']} ({agentic_metrics['coverage_pct']}%) |",
            f"| Model API calls / iterations | {agentic_metrics['total_model_api_calls']} / {agentic_metrics['total_model_iterations']} |",
            f"| Tool calls / errors | {agentic_metrics['total_tool_calls']} / {agentic_metrics['total_tool_errors']} ({agentic_metrics['tool_error_rate_pct']}%) |",
            f"| Recovered tasks | {agentic_metrics['recovered_tasks']} / {agentic_metrics['tasks_with_tool_errors']} ({agentic_metrics['recovery_rate_pct']}%) |",
            f"| Finalize attempts | {agentic_metrics['total_finalize_attempts']} |",
            f"| P50 / P95 tool time | {agentic_metrics['p50_tool_time_ms']:,.0f}ms / {agentic_metrics['p95_tool_time_ms']:,.0f}ms |",
            f"| Conservative model cost | USD {agentic_metrics['conservative_cost_usd']:.4f} |",
            "",
        ]

    # 2. Execution Summary
    if narrative.get("overview"):
        if narrative.get("grading_referenced"):
            summary_heading = "## Execution Summary *(Self-QA + Automated LLM-Judge)*"
            summary_note = (
                "> **Evidence boundary:** Task execution and retry observations use "
                "same-model Self-QA. External quality signals come from the separately "
                "provided automated LLM-judge grade; neither is human expert review."
            )
        else:
            summary_heading = "## Execution Summary *(Self-Assessed, Pre-Grading)*"
            summary_note = (
                "> **Note:** This summary is based on the LLM's self-assessed "
                "confidence scores (Self-QA) during task execution — not on external "
                "grading results. Actual grading scores are not yet available."
            )
        lines += [
            summary_heading,
            "",
            summary_note,
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
            f"| Failed (empty outputs preserved) | {failed} |",
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

    if narrative.get("grading_referenced"):
        execution_summary_label = "Execution Summary (Self-QA + Automated LLM-Judge)"
        execution_summary_note = (
            "Execution signals use same-model Self-QA; external quality uses the "
            "separately provided automated LLM-judge grade. Neither is human review."
        )
    else:
        execution_summary_label = "Execution Summary (Self-Assessed)"
        execution_summary_note = (
            "Based on LLM Self-QA confidence scores; external grading is not yet available."
        )

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
    <h2>{execution_summary_label}</h2>
    <p class="narrative" style="color:#888;font-size:0.85rem;margin-bottom:12px;">{execution_summary_note}</p>
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


def _resolve_output_dir(
    explicit_output_dir: Path = None,
    result_json_path: Path = DEFAULT_RESULT_JSON,
) -> Path:
    """Resolve the report output directory.

    Priority:
      1. CLI --output-dir argument (explicit override)
    2. results/<experiment_id>/report/ from the selected result JSON

    Creates the directory if it does not exist.
    """
    if explicit_output_dir is not None:
        out = Path(explicit_output_dir)
        out.mkdir(parents=True, exist_ok=True)
        return out

    result_path = _find_result_json(Path(result_json_path))
    try:
        data = json.loads(result_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Result JSON is malformed: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("Result JSON root must be an object")
    experiment_id = _validated_experiment_id(data)
    out = _SCRIPT_DIR / "results" / experiment_id / "report"

    out.mkdir(parents=True, exist_ok=True)
    return out


# ── Main ──────────────────────────────────────────────────────────────────


def generate_report(
    result_json_path: Path,
    output_dir: Path,
    no_narrative: bool = False,
    dry_run: bool = False,
) -> None:
    print("============================================================")
    print("📝 Step 6: Generate Experiment Report")
    print("============================================================")

    result_path = _find_result_json(result_json_path)
    print(f"   Input:  {result_path}")
    print(f"   Output: {output_dir}")

    with open(result_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    workspace_owned = result_path.resolve() == (
        WORKSPACE_DIR / "result.json"
    ).resolve()
    # The same gate self_report.json is staged behind, and for the same
    # reason: the upload directory is created by the pipeline, so its absence
    # means no upload is being assembled and nothing should be staged into it.
    publishing = workspace_owned and (WORKSPACE_DIR / "upload").exists()

    output_dir.mkdir(parents=True, exist_ok=True)

    # Compute metrics
    summary = _compute_summary(data)
    execution_metrics = _compute_execution_metrics(data)
    agentic_metrics = _compute_agentic_metrics(data)
    cost_summaries = _compute_cost_summaries(data)
    cost_ledger = _report_cost_ledger(data, publishing=publishing)
    sector_breakdown = _compute_sector_breakdown(data)
    manifest = _load_manifest_safe() if workspace_owned else None
    task_results, error_tasks = _build_task_results(data, manifest=manifest)

    # Generate narrative
    if no_narrative:
        narrative = _model_free_narrative()
        print("   Skipping narrative (--no-narrative)")
    else:
        # Try GPT-5.6 Sol Max (Responses API) once, then fall back model-free.
        try:
            from core.narrative_analyzer import (
                create_narrative_analyzer,
                expected_narrative_publication_identity,
            )
            print("   Generating narrative via GPT-5.6 Sol Max (Responses API)…")
            expected_model, expected_effort, expected_fingerprint = (
                expected_narrative_publication_identity()
            )
            with create_narrative_analyzer() as analyzer:
                if (
                    analyzer.model != expected_model
                    or analyzer.reasoning_effort != expected_effort
                    or analyzer.runtime_fingerprint != expected_fingerprint
                ):
                    raise ValueError(
                        "primary narrative identity differs from preflight"
                    )
                result = analyzer.analyze(
                    data,
                    summary,
                    sector_breakdown,
                    task_results,
                    error_tasks,
                    grade=None,
                )
            narrative = {
                "overview": result.overview,
                "quality_analysis": result.quality_analysis,
                "failure_patterns": result.failure_patterns,
                "recommendations": result.recommendations,
                "grading_referenced": result.grading_referenced,
                "grade_source": result.grade_source,
                "model": result.narrative_model,
                "reasoning_effort": result.narrative_reasoning_effort,
                "runtime_fingerprint": result.runtime_fingerprint,
            }
            total_ms = result.call_1_latency_ms + result.call_2_latency_ms
            print(f"   ✅ Sol Max narrative generated ({total_ms:,.0f}ms, "
                  f"{result.total_tokens['input']:,}+{result.total_tokens['output']:,} tokens)")
        except Exception as exc:
            print(f"   ⚠️ Sol Max narrative failed: {type(exc).__name__}")
            print("   Using model-free narrative fallback.")
            narrative = _model_free_narrative(exc)

    # Build report_data.json
    rd = _build_report_data(
        data,
        narrative,
        summary,
        sector_breakdown,
        task_results,
        error_tasks,
        execution_metrics=execution_metrics,
        agentic_metrics=agentic_metrics,
        cost_summaries=cost_summaries,
        cost_ledger=cost_ledger,
        dry_run=dry_run,
    )

    # Inject file generation stats from step5_validate.py
    validate_stats_path = WORKSPACE_DIR / "validate_stats.json"
    file_generation = None
    if workspace_owned and validate_stats_path.exists():
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
    if workspace_owned and inference_results_path.exists():
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
    if workspace_owned and upload_dir.exists():
        self_report_path = upload_dir / "self_report.json"
        shutil.copy2(json_path, self_report_path)
        print(f"   ✓ Copied self_report.json → {self_report_path}")

    print("\n✅ Step 6 complete:")
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
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mark HF self-report publication as skipped",
    )
    args = parser.parse_args()

    output_dir = _resolve_output_dir(args.output_dir, args.result_json)

    generate_report(
        result_json_path=args.result_json,
        output_dir=output_dir,
        no_narrative=args.no_narrative,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
