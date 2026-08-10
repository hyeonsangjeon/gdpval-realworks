#!/usr/bin/env python3
"""Analyze a grade JSON: wall-clock, latency, tokens, cost estimate, score quality.

Usage:
    python scripts/analyze_grade_run.py data/grades/<exp_id>__<judge>__<sha>__v1.json
    python scripts/analyze_grade_run.py <new.json> --compare <baseline.json>

The pricing table is a coarse estimate for historical runs; unregistered models
remain explicitly unpriced instead of being reported as zero. Step 8 records
current payload cost as null/incomplete; this script computes an estimate only
for models present in its reviewed price table.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
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
    if model not in PRICING_USD_PER_M_TOKENS:
        return {
            "input_usd": None,
            "output_usd": None,
            "total_usd": None,
            "pricing_available": False,
        }
    pi, po = _price_for(model)
    in_cost = (in_tok / 1_000_000.0) * pi
    out_cost = (out_tok / 1_000_000.0) * po
    return {
        "input_usd": round(in_cost, 4),
        "output_usd": round(out_cost, 4),
        "total_usd": round(in_cost + out_cost, 4),
        "pricing_available": True,
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
            "pricing_complete": c["pricing_available"],
            "unpriced_models": [] if c["pricing_available"] else [m],
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
    unpriced_models = sorted({
        entry["model"]
        for entry in per_model
        if entry["cost_at_100pct"] is None
    })
    costs = [
        entry["cost_at_100pct"]
        for entry in per_model
        if entry["cost_at_100pct"] is not None
    ]
    return {
        "mode": "routing_blended_estimate",
        "tier_models": tier_models,
        "cost_usd_min": min(costs) if costs and not unpriced_models else None,
        "cost_usd_max": max(costs) if costs and not unpriced_models else None,
        "per_model_if_100pct": per_model,
        "pricing_complete": not unpriced_models,
        "unpriced_models": unpriced_models,
        "note": "Token split per tier is not recorded; range = single-model bounds.",
    }


def _perception_usage_by_modality(
    grade: dict,
) -> dict[str, dict[str, int | float]]:
    usage: dict[str, dict[str, int | float]] = {}

    def add(
        modality: str,
        in_tok: int,
        out_tok: int,
        cached_tok: int,
        call_count: int,
        latency_ms: float,
    ) -> None:
        bucket = usage.setdefault(
            modality,
            {
                "input_tokens": 0,
                "output_tokens": 0,
                "cached_tokens": 0,
                "call_count": 0,
                "latency_ms": 0.0,
            },
        )
        bucket["input_tokens"] += in_tok
        bucket["output_tokens"] += out_tok
        bucket["cached_tokens"] += cached_tok
        bucket["call_count"] += call_count
        bucket["latency_ms"] += latency_ms

    task_total = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cached_tokens": 0,
        "call_count": 0,
        "latency_ms": 0.0,
    }
    item_total = dict(task_total)
    for task in grade.get("tasks", []):
        task_total["input_tokens"] += int(task.get("perception_input_tokens", 0) or 0)
        task_total["output_tokens"] += int(task.get("perception_output_tokens", 0) or 0)
        task_total["cached_tokens"] += int(task.get("perception_cached_tokens", 0) or 0)
        task_total["call_count"] += int(task.get("perception_call_count", 0) or 0)
        task_total["latency_ms"] += float(
            task.get("perception_total_latency_ms", 0) or 0
        )
        for item in task.get("items", []):
            in_tok = int(item.get("perception_input_tokens", 0) or 0)
            out_tok = int(item.get("perception_output_tokens", 0) or 0)
            cached_tok = int(item.get("perception_cached_tokens", 0) or 0)
            call_count = int(item.get("perception_call_count", 0) or 0)
            latency_ms = float(item.get("perception_total_latency_ms", 0) or 0)
            if not (in_tok or out_tok or cached_tok or call_count or latency_ms):
                continue
            modality = str(item.get("routing_modality") or "unknown")
            parent_usage = {
                "input_tokens": in_tok,
                "output_tokens": out_tok,
                "cached_tokens": cached_tok,
                "call_count": call_count,
                "latency_ms": latency_ms,
            }
            if modality == "mixed" and isinstance(item.get("child_grades"), list):
                child_usage = {key: 0 for key in parent_usage}
                child_buckets: list[
                    tuple[str, dict[str, int | float]]
                ] = []
                for child in item["child_grades"]:
                    if not isinstance(child, dict):
                        continue
                    child_values = {
                        "input_tokens": int(
                            child.get("perception_input_tokens", 0) or 0
                        ),
                        "output_tokens": int(
                            child.get("perception_output_tokens", 0) or 0
                        ),
                        "cached_tokens": int(
                            child.get("perception_cached_tokens", 0) or 0
                        ),
                        "call_count": int(
                            child.get("perception_call_count", 0) or 0
                        ),
                        "latency_ms": float(
                            child.get("perception_total_latency_ms", 0) or 0
                        ),
                    }
                    if not any(child_values.values()):
                        continue
                    child_modality = str(
                        child.get("routing_modality") or "unknown"
                    )
                    if child_modality not in {"visual", "audio"}:
                        child_modality = "unknown"
                    child_buckets.append((child_modality, child_values))
                    for key in child_usage:
                        child_usage[key] += child_values[key]
                if all(
                    child_usage[key] <= parent_usage[key]
                    for key in parent_usage
                ):
                    for child_modality, values in child_buckets:
                        add(
                            child_modality,
                            values["input_tokens"],
                            values["output_tokens"],
                            values["cached_tokens"],
                            values["call_count"],
                            values["latency_ms"],
                        )
                    residual = {
                        key: parent_usage[key] - child_usage[key]
                        for key in parent_usage
                    }
                    if any(residual.values()):
                        add(
                            "unknown",
                            residual["input_tokens"],
                            residual["output_tokens"],
                            residual["cached_tokens"],
                            residual["call_count"],
                            residual["latency_ms"],
                        )
                else:
                    add(
                        "unknown",
                        in_tok,
                        out_tok,
                        cached_tok,
                        call_count,
                        latency_ms,
                    )
            else:
                if modality not in {"visual", "audio"}:
                    modality = "unknown"
                add(
                    modality,
                    in_tok,
                    out_tok,
                    cached_tok,
                    call_count,
                    latency_ms,
                )
            for key, value in parent_usage.items():
                item_total[key] += value

    remainder = {
        key: max(0, task_total[key] - item_total[key])
        for key in task_total
    }
    if any(remainder.values()):
        add(
            "unknown",
            remainder["input_tokens"],
            remainder["output_tokens"],
            remainder["cached_tokens"],
            int(remainder["call_count"]),
            float(remainder["latency_ms"]),
        )
    return usage


def _judge_error_type(item: dict) -> str:
    evidence = str(item.get("evidence") or "").strip()
    for public_prefix in ("provider_error:", "task_execution_error:"):
        if evidence.startswith(public_prefix):
            subtype = evidence[len(public_prefix):].split(":", 1)[0].strip()
            return subtype or public_prefix.rstrip(":")
    for prefix in (
        "final_json_parse_failed",
        "empty_final_text",
        "invalid_final_envelope",
        "RateLimitError",
        "BadRequestError",
        "selection_error",
    ):
        if evidence.startswith(prefix):
            return prefix
    if evidence:
        return evidence.split(":", 1)[0][:80]
    return "unknown"


def _judge_error_types(item: dict) -> list[str]:
    child_types = [
        _judge_error_type(child)
        for child in (item.get("child_grades") or [])
        if isinstance(child, dict) and child.get("verdict") == "judge_error"
    ]
    return child_types or [_judge_error_type(item)]


def _anchor_usage(values: dict[str, int | float] | None) -> dict:
    values = values or {}
    return {
        "call_count": int(values.get("call_count", 0) or 0),
        "input_tokens": int(values.get("input_tokens", 0) or 0),
        "output_tokens": int(values.get("output_tokens", 0) or 0),
        "cached_tokens": int(values.get("cached_tokens", 0) or 0),
        "latency_sec": round(float(values.get("latency_ms", 0) or 0) / 1000, 2),
    }


def _task_anchor(task: dict) -> dict:
    modality_usage = _perception_usage_by_modality({"tasks": [task]})
    error_types = Counter(
        error_type
        for item in task.get("items", [])
        if item.get("verdict") == "judge_error"
        for error_type in _judge_error_types(item)
    )
    wall_time_ms = task.get("grading_wall_time_ms")
    return {
        "task_id": task.get("task_id"),
        "wall_clock_sec": (
            round(float(wall_time_ms) / 1000, 2)
            if isinstance(wall_time_ms, (int, float)) else None
        ),
        "main": {
            "call_count": int(task.get("judge_call_count", 0) or 0),
            "input_tokens": int(task.get("judge_input_tokens", 0) or 0),
            "output_tokens": int(task.get("judge_output_tokens", 0) or 0),
            "cached_tokens": int(task.get("judge_cached_tokens", 0) or 0),
            "latency_sec": round(
                float(task.get("judge_total_latency_ms", 0) or 0) / 1000,
                2,
            ),
        },
        "visual": _anchor_usage(modality_usage.get("visual")),
        "audio": _anchor_usage(modality_usage.get("audio")),
        "unknown_perception": _anchor_usage(modality_usage.get("unknown")),
        "render": {
            "call_count": int(task.get("render_call_count", 0) or 0),
            "latency_sec": round(
                float(task.get("render_total_latency_ms", 0) or 0) / 1000,
                2,
            ),
        },
        "judge_error_types": dict(sorted(error_types.items())),
        "usage_complete": bool(task.get("usage_complete", True)),
        "error": task.get("error"),
    }


def _combined_cost_estimate(
    grade: dict,
    main_in: int,
    main_out: int,
    perception_usage: dict[str, dict[str, int]],
) -> dict:
    main = _hybrid_cost_estimate(grade, main_in, main_out)
    if not perception_usage:
        return main

    main_model = grade.get("judge", {}).get("model", "")
    perception_cfg = grade.get("judge", {}).get("perception", {}) or {}
    components = []
    unpriced_models = list(main.get("unpriced_models", []))
    perception_total = 0.0
    for modality, token_usage in sorted(perception_usage.items()):
        if not any(
            int(token_usage.get(key, 0) or 0)
            for key in ("input_tokens", "output_tokens", "cached_tokens")
        ):
            continue
        model = (
            (perception_cfg.get(modality) or {}).get("model")
            if modality in {"visual", "audio"} else "unknown_perception_model"
        ) or main_model
        priced = model in PRICING_USD_PER_M_TOKENS
        estimate = _estimate_cost(
            token_usage["input_tokens"], token_usage["output_tokens"], model
        )
        if not priced:
            unpriced_models.append(model)
        if estimate["total_usd"] is not None:
            perception_total += estimate["total_usd"]
        components.append({
            "modality": modality,
            "model": model,
            **token_usage,
            **estimate,
            "pricing_available": priced,
        })

    out = {
        "mode": "main_plus_perception",
        "main": main,
        "perception": components,
        "pricing_complete": not unpriced_models,
        "unpriced_models": sorted(set(unpriced_models)),
    }
    if unpriced_models:
        if main.get("mode") == "single":
            out["cost_usd"] = None
        else:
            out["cost_usd_min"] = None
            out["cost_usd_max"] = None
    elif main.get("mode") == "single":
        out["cost_usd"] = round(main["cost_usd"] + perception_total, 4)
    else:
        out["cost_usd_min"] = round(
            main.get("cost_usd_min", 0.0) + perception_total, 4
        )
        out["cost_usd_max"] = round(
            main.get("cost_usd_max", 0.0) + perception_total, 4
        )
    return out


def _effective_component(
    in_tok: int, out_tok: int, cached_tok: int, model: str
) -> dict:
    if model not in PRICING_USD_PER_M_TOKENS:
        return {
            "model": model,
            "input_usd": None,
            "output_usd": None,
            "total_usd": None,
            "pricing_available": False,
        }
    pi, po = _price_for(model)
    input_usd = (
        (in_tok - cached_tok) * pi
        + cached_tok * pi * CACHED_INPUT_DISCOUNT
    ) / 1_000_000.0
    output_usd = out_tok * po / 1_000_000.0
    return {
        "model": model,
        "input_usd": input_usd,
        "output_usd": output_usd,
        "total_usd": input_usd + output_usd,
        "pricing_available": model in PRICING_USD_PER_M_TOKENS,
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

    main_latencies = [t.get("judge_total_latency_ms", 0) or 0 for t in tasks]
    perception_latencies = [
        t.get("perception_total_latency_ms", 0) or 0 for t in tasks
    ]
    latencies = [
        main + perception
        for main, perception in zip(main_latencies, perception_latencies)
    ]
    main_calls = [t.get("judge_call_count", 0) or 0 for t in tasks]
    perception_calls = [
        t.get("perception_call_count", 0) or 0 for t in tasks
    ]
    judge_calls = [
        main + perception
        for main, perception in zip(main_calls, perception_calls)
    ]
    precheck_counts = [t.get("precheck_count", 0) or 0 for t in tasks]
    main_in_tokens = [t.get("judge_input_tokens", 0) or 0 for t in tasks]
    main_out_tokens = [t.get("judge_output_tokens", 0) or 0 for t in tasks]
    main_cached_tokens = [t.get("judge_cached_tokens", 0) or 0 for t in tasks]
    perception_in_tokens = [
        t.get("perception_input_tokens", 0) or 0 for t in tasks
    ]
    perception_out_tokens = [
        t.get("perception_output_tokens", 0) or 0 for t in tasks
    ]
    perception_cached_tokens = [
        t.get("perception_cached_tokens", 0) or 0 for t in tasks
    ]
    in_tokens = [
        main + perception
        for main, perception in zip(main_in_tokens, perception_in_tokens)
    ]
    out_tokens = [
        main + perception
        for main, perception in zip(main_out_tokens, perception_out_tokens)
    ]
    cached_tokens = [
        main + perception
        for main, perception in zip(
            main_cached_tokens, perception_cached_tokens
        )
    ]

    total_in = sum(in_tokens)
    total_out = sum(out_tokens)
    total_cached = sum(cached_tokens)
    total_latency_sec = sum(latencies) / 1000.0
    total_calls = sum(judge_calls)
    total_main_calls = sum(main_calls)
    total_perception_calls = sum(perception_calls)
    total_precheck = sum(precheck_counts)
    total_main_in = sum(main_in_tokens)
    total_main_out = sum(main_out_tokens)
    total_main_cached = sum(main_cached_tokens)
    total_perception_in = sum(perception_in_tokens)
    total_perception_out = sum(perception_out_tokens)
    total_perception_cached = sum(perception_cached_tokens)
    total_main_latency_sec = sum(main_latencies) / 1000.0
    total_perception_latency_sec = sum(perception_latencies) / 1000.0
    total_render_calls = sum(t.get("render_call_count", 0) or 0 for t in tasks)
    total_render_latency_sec = sum(
        t.get("render_total_latency_ms", 0) or 0 for t in tasks
    ) / 1000.0
    usage_complete = all(t.get("usage_complete", True) for t in tasks)

    # Top-5 slowest tasks
    enriched = sorted(
        [
            {
                "task_id": t.get("task_id"),
                "latency_sec": (
                    (t.get("judge_total_latency_ms", 0) or 0)
                    + (t.get("perception_total_latency_ms", 0) or 0)
                ) / 1000.0,
                "calls": (
                    (t.get("judge_call_count", 0) or 0)
                    + (t.get("perception_call_count", 0) or 0)
                ),
                "tokens_io": (
                    (t.get("judge_input_tokens", 0) or 0)
                    + (t.get("perception_input_tokens", 0) or 0),
                    (t.get("judge_output_tokens", 0) or 0)
                    + (t.get("perception_output_tokens", 0) or 0),
                ),
                "pct": t.get("pct"),
                "critical_fail": t.get("critical_fail"),
            }
            for t in tasks
        ],
        key=lambda r: r["latency_sec"],
        reverse=True,
    )

    perception_usage = _perception_usage_by_modality(grade)
    cost = _combined_cost_estimate(
        grade, total_main_in, total_main_out, perception_usage
    )
    task_anchors = [_task_anchor(task) for task in tasks]
    judge_error_types = Counter()
    for anchor in task_anchors:
        judge_error_types.update(anchor["judge_error_types"])
    measured_task_wall_times = [
        anchor["wall_clock_sec"]
        for anchor in task_anchors
        if anchor["wall_clock_sec"] is not None
    ]
    projected_220_wall_hours = (
        round(statistics.mean(measured_task_wall_times) * 220 / 3600, 2)
        if measured_task_wall_times else None
    )
    if projected_220_wall_hours is None:
        projection_status = "unmeasured"
    elif projected_220_wall_hours >= 44:
        projection_status = "at_or_above_44h_envelope"
    else:
        projection_status = "below_44h_envelope"

    # PR3 Step 0 — effective (cache-discounted) cost. Skipped if the run
    # used the legacy v1 path (no cached_tokens captured).
    effective_cost = None
    cache_hit_ratio = None
    if total_in > 0:
        cache_hit_ratio = round(total_cached / total_in, 4)
        main_model = grade["judge"].get("model", "")
        components = [
            _effective_component(
                total_main_in, total_main_out, total_main_cached, main_model
            )
        ]
        perception_cfg = grade.get("judge", {}).get("perception", {}) or {}
        for modality, token_usage in sorted(perception_usage.items()):
            if not any(
                int(token_usage.get(key, 0) or 0)
                for key in ("input_tokens", "output_tokens", "cached_tokens")
            ):
                continue
            model = (
                (perception_cfg.get(modality) or {}).get("model")
                if modality in {"visual", "audio"}
                else "unknown_perception_model"
            ) or main_model
            components.append(_effective_component(
                token_usage["input_tokens"],
                token_usage["output_tokens"],
                token_usage["cached_tokens"],
                model,
            ))
        unpriced_models = sorted({
            component["model"] for component in components
            if not component["pricing_available"]
        })
        eff_in_cost = None if unpriced_models else sum(
            component["input_usd"] for component in components
        )
        eff_out_cost = None if unpriced_models else sum(
            component["output_usd"] for component in components
        )
        effective_cost = {
            "input_usd": round(eff_in_cost, 4) if eff_in_cost is not None else None,
            "output_usd": round(eff_out_cost, 4) if eff_out_cost is not None else None,
            "total_usd": (
                round(eff_in_cost + eff_out_cost, 4)
                if eff_in_cost is not None and eff_out_cost is not None
                else None
            ),
            "cache_hit_ratio": cache_hit_ratio,
            "cached_tokens": total_cached,
            "pricing_complete": not unpriced_models,
            "unpriced_models": unpriced_models,
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
        "total_main_judge_calls": total_main_calls,
        "total_perception_calls": total_perception_calls,
        "total_precheck_decisions": total_precheck,
        "judge_call_share_pct": round(100.0 * total_calls / max(1, total_calls + total_precheck), 1),

        "total_input_tokens": total_in,
        "total_output_tokens": total_out,
        "total_cached_tokens": total_cached,
        "main_input_tokens": total_main_in,
        "main_output_tokens": total_main_out,
        "main_cached_tokens": total_main_cached,
        "perception_input_tokens": total_perception_in,
        "perception_output_tokens": total_perception_out,
        "perception_cached_tokens": total_perception_cached,
        "sum_main_judge_latency_min": round(total_main_latency_sec / 60.0, 1),
        "sum_perception_latency_min": round(
            total_perception_latency_sec / 60.0, 1
        ),
        "total_render_calls": total_render_calls,
        "sum_render_latency_min": round(total_render_latency_sec / 60.0, 1),
        "usage_complete": usage_complete,
        "avg_tokens_per_task_io": (round(total_in / max(1, len(tasks))), round(total_out / max(1, len(tasks)))),

        "cost_estimate": cost,
        "effective_cost": effective_cost,    # cache-discounted, None if no cached_tokens captured
        "cache_hit_ratio": cache_hit_ratio,
        "top5_slowest": enriched[:5],
        "task_anchors": task_anchors,
        "judge_error_types": dict(sorted(judge_error_types.items())),
        "projected_220_wall_hours": projected_220_wall_hours,
        "projection_status": projection_status,
    }


def _fmt_cost(c: dict) -> str:
    if not c.get("pricing_complete", True):
        return f"unpriced ({','.join(c.get('unpriced_models', []))})"
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
    if c["mode"] == "main_plus_perception":
        if "cost_usd" in c:
            value = f"${c['cost_usd']:.2f}"
        else:
            value = f"${c['cost_usd_min']:.2f} ~ ${c['cost_usd_max']:.2f}"
        if not c.get("pricing_complete", False):
            value += f" [UNPRICED: {','.join(c.get('unpriced_models', []))}]"
        return value
    return "n/a"


def _fmt_headline_score(value) -> str:
    return "unscored" if value is None else str(value)


def render_markdown(a: dict, base: dict | None = None) -> str:
    lines = []
    lines.append(f"# Grade Run Analysis — {a['exp_id']}\n")
    lines.append(f"- file: `{a['path']}`")
    lines.append(f"- config: `{a['config_name']}` (model={a['judge_model']}, effort={a['reasoning_effort']})")
    lines.append(f"- tasks: {a['graded_tasks']}/{a['total_tasks']} (errors={a['error_tasks']})")
    lines.append("")
    lines.append("## Quality")
    lines.append(
        f"- avg_score_pct: **{_fmt_headline_score(a['avg_score_pct'])}**"
    )
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
    lines.append(f"- total API calls: {a['total_judge_calls']} "
                 f"(main={a['total_main_judge_calls']}, perception={a['total_perception_calls']})  |  "
                 f"precheck decisions: {a['total_precheck_decisions']}  "
                 f"(judge share {a['judge_call_share_pct']}%)")
    lines.append(f"- tokens: in={a['total_input_tokens']:,}  out={a['total_output_tokens']:,}")
    lines.append(
        f"- main tokens: in={a['main_input_tokens']:,} out={a['main_output_tokens']:,}; "
        f"perception tokens: in={a['perception_input_tokens']:,} "
        f"out={a['perception_output_tokens']:,}"
    )
    lines.append(
        f"- render: calls={a['total_render_calls']}, "
        f"latency={a['sum_render_latency_min']} min; "
        f"usage_complete={a['usage_complete']}"
    )
    lines.append(f"- per-task avg (in,out): {a['avg_tokens_per_task_io']}")
    lines.append("")
    lines.append("## Task anchors")
    lines.append(
        "| task_id | wall (s) | main calls/tokens/latency | "
        "visual calls/tokens/latency | audio calls/tokens/latency | "
        "unknown perception calls/tokens/latency | judge errors |"
    )
    lines.append("|---|--:|---|---|---|---|---|")
    for anchor in a["task_anchors"]:
        main = anchor["main"]
        visual = anchor["visual"]
        audio = anchor["audio"]
        unknown = anchor["unknown_perception"]
        errors = ", ".join(
            f"{name}:{count}"
            for name, count in anchor["judge_error_types"].items()
        ) or "none"
        wall = anchor["wall_clock_sec"]
        wall_text = "unmeasured" if wall is None else str(wall)
        lines.append(
            f"| `{anchor['task_id']}` | {wall_text} | "
            f"{main['call_count']} / "
            f"{main['input_tokens']},{main['output_tokens']},"
            f"{main['cached_tokens']} / {main['latency_sec']}s | "
            f"{visual['call_count']} / "
            f"{visual['input_tokens']},{visual['output_tokens']},"
            f"{visual['cached_tokens']} / {visual['latency_sec']}s | "
            f"{audio['call_count']} / "
            f"{audio['input_tokens']},{audio['output_tokens']},"
            f"{audio['cached_tokens']} / {audio['latency_sec']}s | "
            f"{unknown['call_count']} / "
            f"{unknown['input_tokens']},{unknown['output_tokens']},"
            f"{unknown['cached_tokens']} / {unknown['latency_sec']}s | "
            f"{errors} |"
        )
    lines.append("")
    lines.append(
        "- judge_error_types: "
        + (
            ", ".join(
                f"{name}:{count}"
                for name, count in a["judge_error_types"].items()
            )
            or "none"
        )
    )
    lines.append(
        "- projected_220_wall_hours: "
        f"{a['projected_220_wall_hours']} ({a['projection_status']})"
    )
    lines.append("")
    lines.append("## Cost estimate")
    lines.append(f"- raw: {_fmt_cost(a['cost_estimate'])}")
    ec = a.get("effective_cost")
    if ec is not None:
        if ec.get("pricing_complete", False):
            lines.append(
                f"- effective (cached-discounted): ${ec['total_usd']:.2f}  "
                f"(cache_hit_ratio={ec['cache_hit_ratio']*100:.1f}%, "
                f"cached_tokens={ec['cached_tokens']:,})"
            )
        else:
            lines.append(
                "- effective (cached-discounted): unpriced "
                f"({','.join(ec.get('unpriced_models', []))})"
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
            if k == "avg_score_pct":
                bv = _fmt_headline_score(bv)
                tv = _fmt_headline_score(tv)
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
