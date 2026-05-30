#!/usr/bin/env python3
"""Analyze a grade JSON: wall-clock, latency, tokens, cost estimate, score quality.

Usage:
    python scripts/analyze_grade_run.py data/grades/<exp_id>__<judge>__<sha>__v1.json
    python scripts/analyze_grade_run.py <new.json> --compare <baseline.json>

The pricing table is a coarse estimate (Azure OpenAI list prices, 2025-Q2);
edit `PRICING_USD_PER_M_TOKENS` to keep current. `estimated_cost_usd` written
by step8 is always 0.0; this script computes a price-table-based estimate from
actual `judge_input_tokens` + `judge_output_tokens`.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime
from pathlib import Path

# input, output per 1M tokens (USD). Edit to keep current. These are
# Azure OpenAI list prices as of 2025-Q2 (best-effort). For internal/external
# tenant negotiated rates, override via OVERRIDE_PRICING below or fork.
# Source: https://azure.microsoft.com/pricing/details/cognitive-services/openai-service/
# Last reviewed: 2026-05-28 (best-effort; check before quoting numbers).
PRICING_USD_PER_M_TOKENS = {
    "gpt-5.4-pro":  (5.00, 15.00),
    "gpt-5.4":      (1.25,  5.00),
    "gpt-5.4-mini": (0.25,  1.00),
    "gpt-5.4-nano": (0.075, 0.30),
}

# PR3 Step 0 — cached input is billed at 50% of standard input rate
# (Azure Responses API automatic prompt caching, parity with OpenAI public
# pricing). Confirm against billing for negotiated tenant rates.
CACHED_INPUT_DISCOUNT = 0.50


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def _price_for(model: str) -> tuple[float, float]:
    return PRICING_USD_PER_M_TOKENS.get(model, (0.0, 0.0))


def _estimate_cost(in_tok: int, out_tok: int, model: str) -> dict:
    """Return cost as {input_usd, output_usd, total_usd} for transparency."""
    pi, po = _price_for(model)
    in_cost = (in_tok / 1_000_000.0) * pi
    out_cost = (out_tok / 1_000_000.0) * po
    return {
        "input_usd": round(in_cost, 4),
        "output_usd": round(out_cost, 4),
        "total_usd": round(in_cost + out_cost, 4),
    }


def _hybrid_cost_estimate(grade: dict, total_in: int, total_out: int) -> dict:
    """If config has judge.routing, blend prices across tiers.

    Without per-item model labels we cannot exactly split tokens; we use the
    fraction of judge items resolved at each tier as a proxy. precheck items
    contribute zero tokens.
    """
    routing = grade.get("judge", {}).get("routing")
    if not routing:
        m = grade["judge"]["model"]
        c = _estimate_cost(total_in, total_out, m)
        return {
            "mode": "single",
            "model": m,
            "cost_usd": c["total_usd"],
            "input_usd": c["input_usd"],
            "output_usd": c["output_usd"],
        }

    # tier proxy: count items decided_by != precheck and split by ... we have
    # no item-level model labels yet, so fall back to flat avg of active tier
    # blended prices. This is a ceiling/floor only — flag it.
    tier_models = []
    for t in ("tier_pro", "tier_standard", "tier_mini"):
        b = routing.get(t) or {}
        if b.get("model"):
            tier_models.append(b["model"])
    if not tier_models:
        return {"mode": "routing_no_tiers", "cost_usd": 0.0}

    per_model = []
    for m in tier_models:
        c = _estimate_cost(total_in, total_out, m)
        per_model.append({
            "model": m,
            "cost_at_100pct": c["total_usd"],
            "input_usd_at_100pct": c["input_usd"],
            "output_usd_at_100pct": c["output_usd"],
        })
    costs = [p["cost_at_100pct"] for p in per_model]
    return {
        "mode": "routing_blended_estimate",
        "tier_models": tier_models,
        "cost_usd_min": min(costs),
        "cost_usd_max": max(costs),
        "per_model_if_100pct": per_model,
        "note": "Token split per tier is not recorded; range = single-model bounds.",
    }


def analyze(path: Path) -> dict:
    grade = json.loads(path.read_text())
    tasks = grade.get("tasks", [])
    summary = grade.get("summary", {})

    graded_ats = [_parse_iso(t.get("graded_at")) for t in tasks if t.get("graded_at")]
    graded_ats = [d for d in graded_ats if d]
    wall_first = min(graded_ats) if graded_ats else None
    wall_last = max(graded_ats) if graded_ats else None
    wall_clock_sec = (wall_last - wall_first).total_seconds() if wall_first and wall_last else None

    latencies = [t.get("judge_total_latency_ms", 0) or 0 for t in tasks]
    judge_calls = [t.get("judge_call_count", 0) or 0 for t in tasks]
    precheck_counts = [t.get("precheck_count", 0) or 0 for t in tasks]
    in_tokens = [t.get("judge_input_tokens", 0) or 0 for t in tasks]
    out_tokens = [t.get("judge_output_tokens", 0) or 0 for t in tasks]
    cached_tokens = [t.get("judge_cached_tokens", 0) or 0 for t in tasks]

    total_in = sum(in_tokens)
    total_out = sum(out_tokens)
    total_cached = sum(cached_tokens)
    total_latency_sec = sum(latencies) / 1000.0
    total_calls = sum(judge_calls)
    total_precheck = sum(precheck_counts)

    # Top-5 slowest tasks
    enriched = sorted(
        [
            {
                "task_id": t.get("task_id"),
                "latency_sec": (t.get("judge_total_latency_ms", 0) or 0) / 1000.0,
                "calls": t.get("judge_call_count", 0),
                "tokens_io": (t.get("judge_input_tokens", 0), t.get("judge_output_tokens", 0)),
                "pct": t.get("pct"),
                "critical_fail": t.get("critical_fail"),
            }
            for t in tasks
        ],
        key=lambda r: r["latency_sec"],
        reverse=True,
    )

    cost = _hybrid_cost_estimate(grade, total_in, total_out)

    # PR3 Step 0 — effective (cache-discounted) cost. Skipped if the run
    # used the legacy v1 path (no cached_tokens captured).
    effective_cost = None
    cache_hit_ratio = None
    if total_in > 0:
        cache_hit_ratio = round(total_cached / total_in, 4)
        model = grade["judge"].get("model", "")
        pi, po = PRICING_USD_PER_M_TOKENS.get(model, (0.0, 0.0))
        eff_in_cost = ((total_in - total_cached) * pi
                       + total_cached * pi * CACHED_INPUT_DISCOUNT) / 1_000_000.0
        eff_out_cost = total_out * po / 1_000_000.0
        effective_cost = {
            "input_usd": round(eff_in_cost, 4),
            "output_usd": round(eff_out_cost, 4),
            "total_usd": round(eff_in_cost + eff_out_cost, 4),
            "cache_hit_ratio": cache_hit_ratio,
            "cached_tokens": total_cached,
        }

    return {
        "path": str(path),
        "exp_id": grade.get("experiment_yaml_name"),
        "config_name": grade["judge"].get("config_name"),
        "judge_model": grade["judge"].get("model"),
        "reasoning_effort": grade["judge"].get("reasoning_effort"),
        "total_tasks": summary.get("total_tasks"),
        "graded_tasks": summary.get("graded_tasks"),
        "error_tasks": summary.get("error_tasks"),
        "avg_score_pct": summary.get("openai_compat", {}).get("avg_score_pct"),
        "critical_item_pass_rate": summary.get("wow", {}).get("critical_item_pass_rate"),
        "judge_pass_rate": summary.get("wow", {}).get("judge_pass_rate"),
        "judge_error_rate": summary.get("wow", {}).get("judge_error_rate"),
        "precheck_pass_rate": summary.get("wow", {}).get("precheck_pass_rate"),

        "wall_first": wall_first.isoformat() if wall_first else None,
        "wall_last": wall_last.isoformat() if wall_last else None,
        "wall_clock_min": round(wall_clock_sec / 60.0, 1) if wall_clock_sec else None,
        "sum_judge_latency_min": round(total_latency_sec / 60.0, 1),
        "avg_latency_per_task_sec": round(statistics.mean(latencies) / 1000.0, 1) if latencies else 0,
        "median_latency_per_task_sec": round(statistics.median(latencies) / 1000.0, 1) if latencies else 0,
        "p95_latency_per_task_sec": round(sorted(latencies)[int(len(latencies)*0.95)] / 1000.0, 1) if latencies else 0,

        "total_judge_calls": total_calls,
        "total_precheck_decisions": total_precheck,
        "judge_call_share_pct": round(100.0 * total_calls / max(1, total_calls + total_precheck), 1),

        "total_input_tokens": total_in,
        "total_output_tokens": total_out,
        "total_cached_tokens": total_cached,
        "avg_tokens_per_task_io": (round(total_in / max(1, len(tasks))), round(total_out / max(1, len(tasks)))),

        "cost_estimate": cost,
        "effective_cost": effective_cost,    # cache-discounted, None if no cached_tokens captured
        "cache_hit_ratio": cache_hit_ratio,
        "top5_slowest": enriched[:5],
    }


def _fmt_cost(c: dict) -> str:
    if c["mode"] == "single":
        return (
            f"${c['cost_usd']:.2f}  (model={c['model']}; "
            f"in=${c.get('input_usd', 0):.2f}, out=${c.get('output_usd', 0):.2f})"
        )
    if c["mode"] == "routing_blended_estimate":
        return (
            f"${c['cost_usd_min']:.2f} ~ ${c['cost_usd_max']:.2f} "
            f"(tiers={','.join(c['tier_models'])}) [NOTE: per-tier token split not recorded]"
        )
    return "n/a"


def render_markdown(a: dict, base: dict | None = None) -> str:
    lines = []
    lines.append(f"# Grade Run Analysis — {a['exp_id']}\n")
    lines.append(f"- file: `{a['path']}`")
    lines.append(f"- config: `{a['config_name']}` (model={a['judge_model']}, effort={a['reasoning_effort']})")
    lines.append(f"- tasks: {a['graded_tasks']}/{a['total_tasks']} (errors={a['error_tasks']})")
    lines.append("")
    lines.append("## Quality")
    lines.append(f"- avg_score_pct: **{a['avg_score_pct']}**")
    lines.append(f"- critical_item_pass_rate: **{a['critical_item_pass_rate']}**")
    lines.append(f"- judge_pass_rate: {a['judge_pass_rate']}")
    lines.append(f"- judge_error_rate: {a['judge_error_rate']}")
    lines.append(f"- precheck_pass_rate: {a['precheck_pass_rate']}")
    lines.append("")
    lines.append("## Wall-clock & latency")
    lines.append(f"- first→last graded_at: {a['wall_first']} → {a['wall_last']}")
    lines.append(f"- **wall-clock**: {a['wall_clock_min']} min")
    lines.append(f"- sum judge latency: {a['sum_judge_latency_min']} min "
                 f"(concurrency factor ≈ {round((a['sum_judge_latency_min'] or 0) / max(0.1, (a['wall_clock_min'] or 0.1)), 2)}x)")
    lines.append(f"- per-task: avg={a['avg_latency_per_task_sec']}s, p50={a['median_latency_per_task_sec']}s, p95={a['p95_latency_per_task_sec']}s")
    lines.append("")
    lines.append("## Volume")
    lines.append(f"- judge calls: {a['total_judge_calls']}  |  precheck decisions: {a['total_precheck_decisions']}  "
                 f"(judge share {a['judge_call_share_pct']}%)")
    lines.append(f"- tokens: in={a['total_input_tokens']:,}  out={a['total_output_tokens']:,}")
    lines.append(f"- per-task avg (in,out): {a['avg_tokens_per_task_io']}")
    lines.append("")
    lines.append("## Cost estimate")
    lines.append(f"- raw: {_fmt_cost(a['cost_estimate'])}")
    ec = a.get("effective_cost")
    if ec is not None:
        lines.append(
            f"- effective (cached-discounted): ${ec['total_usd']:.2f}  "
            f"(cache_hit_ratio={ec['cache_hit_ratio']*100:.1f}%, "
            f"cached_tokens={ec['cached_tokens']:,})"
        )
    lines.append("")
    lines.append("## Top-5 slowest tasks")
    lines.append("| task_id | latency (s) | calls | tokens (in,out) | pct | critical_fail |")
    lines.append("|---|--:|--:|--|--:|---|")
    for r in a["top5_slowest"]:
        lines.append(f"| `{r['task_id']}` | {r['latency_sec']:.1f} | {r['calls']} | {r['tokens_io']} | {r['pct']} | {r['critical_fail']} |")

    if base:
        lines.append("")
        lines.append(f"## Δ vs baseline (`{base['config_name']}`)")
        lines.append("| metric | baseline | this | Δ |")
        lines.append("|---|--:|--:|--:|")
        for k in ("avg_score_pct", "critical_item_pass_rate", "judge_error_rate",
                  "wall_clock_min", "sum_judge_latency_min", "total_judge_calls",
                  "total_input_tokens", "total_output_tokens"):
            bv, tv = base.get(k), a.get(k)
            try:
                d = round(tv - bv, 3) if (isinstance(bv, (int, float)) and isinstance(tv, (int, float))) else "—"
            except Exception:
                d = "—"
            lines.append(f"| {k} | {bv} | {tv} | {d} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("grade_json", type=Path)
    ap.add_argument("--compare", type=Path, default=None, help="Baseline grade JSON for Δ table")
    ap.add_argument("--out", type=Path, default=None, help="Write markdown to this path (default: stdout)")
    ap.add_argument("--json", action="store_true", help="Emit machine-readable JSON instead of markdown")
    args = ap.parse_args()

    a = analyze(args.grade_json)
    base = analyze(args.compare) if args.compare else None

    if args.json:
        out = {"this": a, "baseline": base}
        text = json.dumps(out, indent=2, default=str)
    else:
        text = render_markdown(a, base)

    if args.out:
        args.out.write_text(text)
        print(f"wrote {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
