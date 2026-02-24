#!/usr/bin/env python3
"""Step 3: Format Results — Convert inference results to final JSON + Markdown report.

Input:
  - workspace/step2_inference_results.json (from Step 2)
  - workspace/step1_tasks_prepared.json    (from Step 1)

Output:
  - results/<exp_id>/<exp_id>.json   (final experiment results)
  - results/<exp_id>/<exp_id>.md     (human-readable report)

Usage:
    python step3_format_results.py
"""

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from core.config import WORKSPACE_DIR, BATCH_RUNNER_ROOT


# ── Helpers ────────────────────────────────────────────────────────────────


def _duration_str(started_at: str, completed_at: str) -> str:
    """Return human-readable duration like '3m 24s'."""
    try:
        fmt = "%Y-%m-%dT%H:%M:%S.%f+00:00"
        start = datetime.strptime(started_at, fmt).replace(tzinfo=timezone.utc)
        end = datetime.strptime(completed_at, fmt).replace(tzinfo=timezone.utc)
        secs = int((end - start).total_seconds())
        return f"{secs // 60}m {secs % 60}s"
    except Exception:
        return "N/A"


def _build_qa_stats(results: list) -> dict:
    """Aggregate QA scores across all tasks."""
    scores = [r["qa_score"] for r in results if r["qa_score"] is not None]
    if not scores:
        return {"enabled": False}
    return {
        "enabled": True,
        "avg_score": round(sum(scores) / len(scores), 2),
        "min_score": min(scores),
        "max_score": max(scores),
        "passed_count": sum(1 for r in results if r.get("qa_passed") is True),
        "failed_count": sum(1 for r in results if r.get("qa_passed") is False),
        "undetermined_count": sum(1 for r in results if r.get("qa_undetermined") is True),
    }


def _build_timing_stats(results: list) -> dict:
    """Aggregate latency stats."""
    latencies = [r["latency_ms"] for r in results if r.get("latency_ms")]
    if not latencies:
        return {}
    return {
        "avg_ms": round(sum(latencies) / len(latencies)),
        "min_ms": round(min(latencies)),
        "max_ms": round(max(latencies)),
        "total_ms": round(sum(latencies)),
    }


def _build_sector_stats(results: list) -> dict:
    """Per-sector breakdown: success rate, avg QA score, avg latency."""
    buckets: dict = defaultdict(lambda: {"total": 0, "success": 0, "scores": [], "latencies": []})
    for r in results:
        sector = r["sector"] or "Unknown"
        buckets[sector]["total"] += 1
        if r["status"] == "success":
            buckets[sector]["success"] += 1
        if r["qa_score"] is not None:
            buckets[sector]["scores"].append(r["qa_score"])
        if r.get("latency_ms"):
            buckets[sector]["latencies"].append(r["latency_ms"])

    out = {}
    for sector, b in sorted(buckets.items()):
        out[sector] = {
            "total": b["total"],
            "success": b["success"],
            "success_rate_pct": round(b["success"] / b["total"] * 100),
            "avg_qa_score": round(sum(b["scores"]) / len(b["scores"]), 1) if b["scores"] else None,
            "avg_latency_ms": round(sum(b["latencies"]) / len(b["latencies"])) if b["latencies"] else None,
        }
    return out


# ── Main ───────────────────────────────────────────────────────────────────


def format_results():
    """Format inference results into final report."""

    # 1. Load inputs
    inference_path = WORKSPACE_DIR / "step2_inference_results.json"
    prepared_path = WORKSPACE_DIR / "step1_tasks_prepared.json"

    if not inference_path.exists():
        print(f"❌ {inference_path} not found. Run step2_run_inference.sh first.")
        sys.exit(1)
    if not prepared_path.exists():
        print(f"❌ {prepared_path} not found. Run step1_prepare_tasks.sh first.")
        sys.exit(1)

    with open(inference_path, "r", encoding="utf-8") as f:
        inference = json.load(f)

    with open(prepared_path, "r", encoding="utf-8") as f:
        prepared = json.load(f)

    experiment_id = inference["experiment_id"]
    condition_name = inference["condition"]
    summary = inference["summary"]

    print(f"📝 Formatting results: {experiment_id} / {condition_name}")

    # 2. Enrich per-task results
    task_map = {t["task_id"]: t for t in prepared["tasks"]}
    enriched_results = []

    for r in inference["results"]:
        task_id = r["task_id"]
        task_meta = task_map.get(task_id, {})
        qa = r.get("qa") or {}

        retried = r.get("resume_round") is not None
        enriched_results.append({
            # identity
            "task_id": task_id,
            "sector": task_meta.get("sector", ""),
            "occupation": task_meta.get("occupation", ""),
            "needs_files": task_meta.get("needs_files", False),
            # execution
            "status": r["status"],
            "retried": retried,
            "resume_round": r.get("resume_round"),
            # output
            "content": r.get("content"),
            "deliverable_text": r.get("deliverable_text", ""),
            "deliverable_files": r.get("deliverable_files", []),
            "deliverable_files_count": len(r.get("deliverable_files", [])),
            # model
            "model": r.get("model"),
            "usage": r.get("usage"),
            "latency_ms": r.get("latency_ms", 0),
            "timestamp": r.get("timestamp"),
            # qa
            "qa_passed": qa.get("passed"),
            "qa_score": qa.get("score"),
            "qa_llm_passed": qa.get("llm_passed"),
            "qa_issues": qa.get("issues", []),
            "qa_issues_count": len(qa.get("issues", [])),
            "qa_suggestion": qa.get("suggestion", ""),
            "qa_undetermined": qa.get("undetermined", False),
            # error
            "error": r.get("error"),
        })

    # 3. Aggregate stats
    retried_tasks = [r for r in enriched_results if r["retried"]]
    qa_stats = _build_qa_stats(enriched_results)
    timing_stats = _build_timing_stats(enriched_results)
    sector_stats = _build_sector_stats(enriched_results)
    duration = _duration_str(
        inference.get("started_at", ""),
        inference.get("completed_at", ""),
    )

    # 4. Build final JSON
    results_dir = BATCH_RUNNER_ROOT / "results" / experiment_id
    results_dir.mkdir(parents=True, exist_ok=True)

    final_json = {
        "experiment_id": experiment_id,
        "experiment_name": prepared.get("experiment_name", ""),
        "condition_name": condition_name,
        "execution_mode": inference.get("execution_mode", ""),
        "model": inference.get("model", ""),
        "started_at": inference.get("started_at"),
        "completed_at": inference.get("completed_at"),
        "duration": duration,
        "summary": {
            "total_tasks": summary["total"],
            "success_count": summary["success"],
            "error_count": summary["error"],
            "qa_failed_count": summary.get("qa_failed", 0),
            "retried_count": len(retried_tasks),
            "resume_rounds_used": inference.get("resume_rounds_used", 0),
        },
        "qa_stats": qa_stats,
        "timing_stats": timing_stats,
        "sector_stats": sector_stats,
        "results": enriched_results,
    }

    json_path = results_dir / f"{experiment_id}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(final_json, f, indent=2, ensure_ascii=False, default=str)

    # 5. Build Markdown report
    success_rate = round(summary["success"] / summary["total"] * 100) if summary["total"] else 0
    retried_count = len(retried_tasks)

    md_lines = [
        f"# {experiment_id}: {prepared.get('experiment_name', '')}",
        "",
        f"- **Condition**: {condition_name}",
        f"- **Model**: {inference.get('model', 'N/A')}",
        f"- **Mode**: {inference.get('execution_mode', 'N/A')}",
        f"- **Date**: {datetime.utcnow().strftime('%Y-%m-%d')}",
        f"- **Duration**: {duration}",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total tasks | {summary['total']} |",
        f"| Success | {summary['success']} ({success_rate}%) |",
        f"| Error | {summary['error']} |",
        f"| QA failed | {summary.get('qa_failed', 0)} |",
        f"| Retried tasks | {retried_count} |",
        f"| Resume rounds used | {inference.get('resume_rounds_used', 0)} |",
    ]

    # Timing stats
    if timing_stats:
        md_lines += [
            f"| Avg latency | {timing_stats['avg_ms']:,}ms |",
            f"| Max latency | {timing_stats['max_ms']:,}ms |",
            f"| Total LLM time | {timing_stats['total_ms'] // 1000}s |",
        ]

    # QA stats
    if qa_stats.get("enabled"):
        md_lines += [
            "",
            "## QA Statistics",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Avg score | {qa_stats['avg_score']} / 10 |",
            f"| Min score | {qa_stats['min_score']} / 10 |",
            f"| Max score | {qa_stats['max_score']} / 10 |",
            f"| Passed | {qa_stats['passed_count']} |",
            f"| Failed | {qa_stats['failed_count']} |",
        ]
        if qa_stats.get("undetermined_count"):
            md_lines.append(f"| Undetermined | {qa_stats['undetermined_count']} |")

    # Results by Task
    md_lines += [
        "",
        "## Results by Task",
        "",
        "| # | Task ID | Sector | Occupation | Status | Retry | Files | QA | Time |",
        "|---|---------|--------|------------|--------|-------|-------|----|------|",
    ]

    for i, r in enumerate(enriched_results, 1):
        status_icon = "✅" if r["status"] == "success" else ("⚠️" if r["status"] == "qa_failed" else "❌")
        retry_str = f"R{r['resume_round']}" if r["retried"] else "-"
        qa_str = f"{r['qa_score']}/10" if r["qa_score"] is not None else "-"
        latency = r.get("latency_ms") or 0
        sector_short = r["sector"][:20] if r["sector"] else ""
        occ_short = r["occupation"][:15] if r["occupation"] else ""
        md_lines.append(
            f"| {i} | `{r['task_id'][:8]}…` | {sector_short} | "
            f"{occ_short} | {status_icon} {r['status']} | "
            f"{retry_str} | {r['deliverable_files_count']} | {qa_str} | {latency:.0f}ms |"
        )

    # Sector breakdown
    if sector_stats:
        md_lines += [
            "",
            "## Sector Breakdown",
            "",
            "| Sector | Tasks | Success | Success% | Avg QA | Avg Latency |",
            "|--------|-------|---------|----------|--------|-------------|",
        ]
        for sector, s in sector_stats.items():
            qa_str = f"{s['avg_qa_score']}/10" if s["avg_qa_score"] is not None else "-"
            lat_str = f"{s['avg_latency_ms']:,}ms" if s["avg_latency_ms"] is not None else "-"
            md_lines.append(
                f"| {sector[:35]} | {s['total']} | {s['success']} | "
                f"{s['success_rate_pct']}% | {qa_str} | {lat_str} |"
            )

    # QA issues detail
    tasks_with_issues = [r for r in enriched_results if r.get("qa_issues")]
    if tasks_with_issues:
        md_lines += ["", "## QA Issues", ""]
        for r in tasks_with_issues:
            qa_icon = "✅" if r.get("qa_passed") else "❌"
            md_lines.append(
                f"### {qa_icon} `{r['task_id'][:8]}…` — score {r['qa_score']}/10"
                + (f" (retried R{r['resume_round']})" if r["retried"] else "")
            )
            for issue in r["qa_issues"]:
                md_lines.append(f"- {issue}")
            if r.get("qa_suggestion"):
                md_lines.append(f"  > 💡 {r['qa_suggestion']}")
            md_lines.append("")

    # Errors
    errors = [r for r in enriched_results if r.get("error")]
    if errors:
        md_lines += ["## Errors", ""]
        for r in errors:
            md_lines.append(f"- **`{r['task_id']}`** ({r['sector']}): {r['error']}")

    # Deliverable files
    files_tasks = [r for r in enriched_results if r.get("deliverable_files")]
    if files_tasks:
        md_lines += ["", "## Deliverable Files", ""]
        for r in files_tasks:
            for fp in r["deliverable_files"]:
                md_lines.append(f"- `{r['task_id']}`: {fp}")

    md_path = results_dir / f"{experiment_id}.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    print(f"\n✅ Step 3 complete:")
    print(f"   JSON: {json_path}")
    print(f"   MD:   {md_path}")
    print(f"   Duration: {duration}")
    if qa_stats.get("enabled"):
        print(f"   QA avg score: {qa_stats['avg_score']}/10 "
              f"(min={qa_stats['min_score']}, max={qa_stats['max_score']})")
    if retried_count:
        print(f"   Retried tasks: {retried_count} (resume rounds: {inference.get('resume_rounds_used', 0)})")

    return json_path, md_path


def main():
    format_results()


if __name__ == "__main__":
    main()
