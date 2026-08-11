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
import hashlib
import json
import re
import statistics
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

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
REPO_ROOT = Path(__file__).resolve().parents[1]
GRADE_SCHEMA_PATH = REPO_ROOT / "batch-runner/schemas/grade.schema.json"
ANCHOR_CONFIG_DIR = REPO_ROOT / "batch-runner/grading_configs"


def _ordered_task_ids_sha256(task_ids: list[str]) -> str:
    encoded = json.dumps(
        task_ids,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _anchor_schema_blockers(grade: dict) -> list[str]:
    try:
        schema = json.loads(GRADE_SCHEMA_PATH.read_text(encoding="utf-8"))
        schema_errors = list(Draft202012Validator(schema).iter_errors(grade))
    except (OSError, json.JSONDecodeError):
        schema_errors = ["schema unavailable"]
    return ["anchor_schema_invalid"] if schema_errors else []


def _repository_anchor_contract(grade: dict) -> dict | None:
    judge = grade.get("judge") if isinstance(grade.get("judge"), dict) else {}
    config_name = judge.get("config_name")
    config_hash = judge.get("config_hash")
    candidate_paths = []
    if isinstance(config_name, str) and re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", config_name
    ):
        candidate_paths.append(ANCHOR_CONFIG_DIR / f"{config_name}.yaml")
    if isinstance(config_hash, str) and re.fullmatch(r"[0-9a-f]{16}", config_hash):
        candidate_paths.extend(ANCHOR_CONFIG_DIR.glob("*.yaml"))

    seen = set()
    for config_path in candidate_paths:
        if config_path in seen or not config_path.is_file():
            continue
        seen.add(config_path)
        try:
            config_bytes = config_path.read_bytes()
            source_config = yaml.safe_load(config_bytes)
        except (OSError, yaml.YAMLError):
            continue
        if not isinstance(source_config, dict):
            continue
        source_contract = source_config.get("anchor_projection")
        if not isinstance(source_contract, dict):
            continue
        source_name = source_config.get("config_name")
        source_hash = hashlib.sha256(config_bytes).hexdigest()[:16]
        if config_name == source_name or config_hash == source_hash:
            return source_contract
    return None


def _anchor_config_identity_blockers(
    grade: dict,
    contract: dict,
    task_ids: list[str],
) -> list[str]:
    blockers = []
    config_name = contract.get("anchor_config_name")
    if not isinstance(config_name, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", config_name
    ):
        blockers.append("anchor_source_config_unavailable")
        return blockers
    config_path = ANCHOR_CONFIG_DIR / f"{config_name}.yaml"
    try:
        config_bytes = config_path.read_bytes()
        source_config = yaml.safe_load(config_bytes)
    except (OSError, yaml.YAMLError):
        blockers.append("anchor_source_config_unavailable")
        return blockers
    if not isinstance(source_config, dict):
        blockers.append("anchor_source_config_unavailable")
        return blockers

    if source_config.get("anchor_projection") != contract:
        blockers.append("anchor_projection_contract_mismatch")
    source_identity = source_config.get("rerun_identity")
    source_task_ids = (
        source_identity.get("task_ids")
        if isinstance(source_identity, dict) else None
    )
    contract_task_hash = contract.get("anchor_ordered_task_ids_sha256")
    if (
        not isinstance(source_task_ids, list)
        or _ordered_task_ids_sha256(source_task_ids) != contract_task_hash
        or _ordered_task_ids_sha256(task_ids) != contract_task_hash
    ):
        blockers.append("anchor_ordered_task_identity_mismatch")

    judge = grade.get("judge") if isinstance(grade.get("judge"), dict) else {}
    expected_config_hash = hashlib.sha256(config_bytes).hexdigest()[:16]
    if (
        judge.get("config_name") != config_name
        or judge.get("config_hash") != expected_config_hash
    ):
        blockers.append("anchor_config_identity_mismatch")

    source_judge = (
        source_config.get("judge")
        if isinstance(source_config.get("judge"), dict) else {}
    )
    expected_judge = {
        "provider": source_judge.get("provider"),
        "api": source_judge.get("api"),
        "model": source_judge.get("model"),
        "deployment": source_judge.get("deployment"),
        "api_version": source_judge.get("api_version", ""),
        "reasoning_effort": (
            source_judge.get("reasoning", {}).get("effort", "high")
        ),
        "temperature": (
            source_judge.get("generation", {}).get("temperature", 0)
        ),
        "seed": source_judge.get("generation", {}).get("seed", 42),
        "perception": source_judge.get("perception", {}),
    }
    if any(judge.get(key) != value for key, value in expected_judge.items()):
        blockers.append("anchor_runtime_identity_mismatch")

    rubric = grade.get("rubric") if isinstance(grade.get("rubric"), dict) else {}
    prompt = grade.get("prompt") if isinstance(grade.get("prompt"), dict) else {}
    source_rubric = source_config.get("rubric", {})
    source_prompt = source_config.get("prompt", {})
    expected_experiment = (
        source_identity.get("experiment_id")
        if isinstance(source_identity, dict) else None
    )
    expected_rubric = (
        source_identity.get("rubric_commit_sha")
        if isinstance(source_identity, dict) else None
    )
    expected_inference = (
        source_identity.get("inference_revision")
        if isinstance(source_identity, dict) else None
    )
    if (
        grade.get("experiment_id") != expected_experiment
        or grade.get("experiment_yaml_name") != expected_experiment
        or grade.get("source_inference_experiment_id") != expected_experiment
        or grade.get("source_inference_repo_id")
        != contract.get("anchor_source_inference_repo_id")
        or grade.get("source_inference_revision") != expected_inference
        or rubric.get("source") != source_rubric.get("source")
        or rubric.get("repo_id") != source_rubric.get("repo_id")
        or rubric.get("revision") != source_rubric.get("revision")
        or rubric.get("commit_sha") != expected_rubric
        or prompt.get("template") != source_prompt.get("template")
        or prompt.get("version") != source_prompt.get("version")
    ):
        blockers.append("anchor_source_identity_mismatch")
    return blockers


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


def _blocked_modality_projection(
    contract: dict,
    task_anchors: list[dict],
    perception_usage: dict[str, dict[str, int | float]],
    total_main_latency_sec: float,
    judge_error_types: Counter,
    blockers: list[str],
) -> dict:
    visual_usage = perception_usage.get("visual") or {}
    audio_usage = perception_usage.get("audio") or {}
    unknown_usage = perception_usage.get("unknown") or {}
    visual_latency_sec = float(visual_usage.get("latency_ms", 0) or 0) / 1000
    audio_latency_sec = float(audio_usage.get("latency_ms", 0) or 0) / 1000
    unknown_latency_sec = float(unknown_usage.get("latency_ms", 0) or 0) / 1000
    unknown_volume = {
        "call_count": int(unknown_usage.get("call_count", 0) or 0),
        "input_tokens": int(unknown_usage.get("input_tokens", 0) or 0),
        "output_tokens": int(unknown_usage.get("output_tokens", 0) or 0),
        "cached_tokens": int(unknown_usage.get("cached_tokens", 0) or 0),
        "latency_sec": round(unknown_latency_sec, 5),
    }
    observed_targetable_errors = (
        judge_error_types.get("final_json_parse_failed", 0)
        + judge_error_types.get("empty_final_text", 0)
    )
    non_targetable_errors = {
        error_type: count
        for error_type, count in sorted(judge_error_types.items())
        if error_type not in {"final_json_parse_failed", "empty_final_text"}
        and count > 0
    }
    baseline_parse = contract.get("baseline_final_json_parse_failed")
    baseline_empty = contract.get("baseline_empty_final_text")
    baseline_targetable_errors = (
        baseline_parse + baseline_empty
        if type(baseline_parse) is int and type(baseline_empty) is int
        else None
    )
    baseline_latency = contract.get("baseline_main_latency_ms")
    baseline_latency_sec = (
        round(float(baseline_latency) / 1000, 5)
        if isinstance(baseline_latency, (int, float)) else None
    )
    audio_call_count = int(audio_usage.get("call_count", 0) or 0)
    visual_budget_errors = judge_error_types.get(
        "task_visual_budget_exceeded",
        0,
    )
    unique_blockers = list(dict.fromkeys(blockers))
    return {
        "method": contract.get("method"),
        "baseline_is_like_for_like": False,
        "baseline_caveat": (
            "schema 1.0 pre-perception payload; mini metrics are a "
            "main-judge-only reference, not a Sol Max multiplier"
        ),
        "anchor_task_count": len(task_anchors),
        "measured_anchor_wall_sec": None,
        "anchor_integrity": {
            "status": "failed",
            "blockers": unique_blockers,
        },
        "components": {
            "main": {
                "anchor_latency_sec": round(total_main_latency_sec, 5),
                "scale": None,
                "projected_hours": None,
                "normalization": "task_count",
                "measurement": "blocked_invalid_anchor_payload",
            },
            "visual": {
                "anchor_latency_sec": round(visual_latency_sec, 5),
                "scale": None,
                "projected_hours": None,
                "normalization": "visual_criteria",
            },
            "audio": {
                "anchor_latency_sec": round(audio_latency_sec, 5),
                "scale": None,
                "projected_hours": None,
                "normalization": "audio_criteria",
            },
        },
        "projected_220_hours": None,
        "chunk_envelope_hours": contract.get("chunk_envelope_hours"),
        "envelope_status": "incomplete_anchor_payload",
        "unknown_perception": unknown_volume,
        "diagnostic": {
            "baseline_targetable_errors": baseline_targetable_errors,
            "observed_targetable_errors": observed_targetable_errors,
            "targetable_status": "inconclusive_invalid_anchor_payload",
            "non_targetable_errors": non_targetable_errors,
            "status": "inconclusive_invalid_anchor_payload",
        },
        "audio_wiring": {
            "call_count": audio_call_count,
            "status": "passed" if audio_call_count > 0 else "failed_no_audio_calls",
        },
        "visual_budget": {
            "task_visual_budget_exceeded": visual_budget_errors,
            "status": "passed" if visual_budget_errors == 0 else "failed",
        },
        "full_run_gate": {
            "status": "blocked",
            "blockers": unique_blockers,
        },
        "main_reference": {
            "calls": contract.get("baseline_main_calls"),
            "latency_sec": baseline_latency_sec,
            "observed_calls": sum(
                anchor["main"]["call_count"] for anchor in task_anchors
            ),
            "observed_latency_sec": round(total_main_latency_sec, 5),
            "calls_ratio": None,
            "latency_ratio": None,
        },
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


def _modality_normalized_projection(
    grade: dict,
    task_anchors: list[dict],
    perception_usage: dict[str, dict[str, int | float]],
    total_main_latency_sec: float,
    judge_error_types: Counter,
) -> dict | None:
    contract = grade.get("anchor_projection")
    if contract is None:
        expected_contract = _repository_anchor_contract(grade)
        if expected_contract is None:
            return None
        task_ids = [anchor["task_id"] for anchor in task_anchors]
        blockers = ["anchor_projection_missing_or_null"]
        blockers.extend(
            _anchor_config_identity_blockers(
                grade,
                expected_contract,
                task_ids,
            )
        )
        return _blocked_modality_projection(
            expected_contract,
            task_anchors,
            perception_usage,
            total_main_latency_sec,
            judge_error_types,
            blockers,
        )
    if not isinstance(contract, dict):
        return _blocked_modality_projection(
            {},
            task_anchors,
            perception_usage,
            total_main_latency_sec,
            judge_error_types,
            ["anchor_schema_invalid"],
        )

    schema_blockers = _anchor_schema_blockers(grade)
    if schema_blockers:
        return _blocked_modality_projection(
            contract,
            task_anchors,
            perception_usage,
            total_main_latency_sec,
            judge_error_types,
            schema_blockers,
        )

    task_count = len(task_anchors)
    anchor_task_count = contract["anchor_task_count"]
    task_ids = [anchor["task_id"] for anchor in task_anchors]
    anchor_integrity_blockers = []
    if grade.get("schema_version") != "1.3":
        anchor_integrity_blockers.append("anchor_schema_not_1_3")
    if grade.get("run_status") != "diagnostic":
        anchor_integrity_blockers.append("anchor_run_not_complete_diagnostic")
    if grade.get("expected_task_count") != anchor_task_count:
        anchor_integrity_blockers.append("anchor_expected_task_count_mismatch")
    if task_count != anchor_task_count:
        anchor_integrity_blockers.append("anchor_task_count_incomplete")
    valid_task_ids = (
        all(isinstance(task_id, str) and task_id for task_id in task_ids)
        and len(task_ids) == len(set(task_ids))
    )
    expected_task_hash = grade.get("expected_ordered_task_ids_sha256")
    contract_task_hash = contract.get("anchor_ordered_task_ids_sha256")
    if (
        not valid_task_ids
        or not isinstance(expected_task_hash, str)
        or expected_task_hash != contract_task_hash
        or _ordered_task_ids_sha256(task_ids) != contract_task_hash
    ):
        anchor_integrity_blockers.append("anchor_ordered_task_identity_mismatch")
    tasks = grade.get("tasks") if isinstance(grade.get("tasks"), list) else []
    if any(task.get("usage_complete") is not True for task in tasks):
        anchor_integrity_blockers.append("anchor_usage_incomplete")
    if any(
        item.get("usage_complete") is not True
        for task in tasks
        for item in task.get("items", [])
        if isinstance(item, dict)
    ):
        anchor_integrity_blockers.append("anchor_item_usage_incomplete")
    summary = grade.get("summary") if isinstance(grade.get("summary"), dict) else {}
    summary_cost = (
        summary.get("cost") if isinstance(summary.get("cost"), dict) else {}
    )
    if summary_cost.get("usage_complete") is not True:
        anchor_integrity_blockers.append("anchor_summary_usage_incomplete")
    if any(task.get("error") for task in tasks):
        anchor_integrity_blockers.append("anchor_task_errors")
    if (
        summary.get("total_tasks") != anchor_task_count
        or summary.get("graded_tasks") != anchor_task_count
        or summary.get("error_tasks") != 0
    ):
        anchor_integrity_blockers.append("anchor_summary_task_counts_mismatch")
    anchor_integrity_blockers.extend(
        _anchor_config_identity_blockers(grade, contract, task_ids)
    )
    anchor_integrity_blockers = list(dict.fromkeys(anchor_integrity_blockers))

    measured_walls = [
        anchor["wall_clock_sec"]
        for anchor in task_anchors
        if anchor["wall_clock_sec"] is not None
    ]
    visual_usage = perception_usage.get("visual") or {}
    audio_usage = perception_usage.get("audio") or {}
    unknown_usage = perception_usage.get("unknown") or {}
    visual_latency_sec = float(visual_usage.get("latency_ms", 0) or 0) / 1000
    audio_latency_sec = float(audio_usage.get("latency_ms", 0) or 0) / 1000
    unknown_latency_sec = float(unknown_usage.get("latency_ms", 0) or 0) / 1000
    total_perception_latency_sec = (
        visual_latency_sec + audio_latency_sec + unknown_latency_sec
    )

    if len(measured_walls) == task_count and task_count > 0:
        measured_wall_sec = sum(measured_walls)
        main_anchor_sec = max(
            total_main_latency_sec,
            measured_wall_sec - total_perception_latency_sec,
        )
        main_measurement = "max(main_latency, measured_wall_minus_perception)"
    else:
        measured_wall_sec = None
        main_anchor_sec = total_main_latency_sec
        main_measurement = "main_latency_fallback_missing_task_wall"

    main_scale = contract["full_task_count"] / anchor_task_count
    visual_scale = (
        contract["full_visual_criteria"]
        / contract["anchor_visual_criteria"]
    )
    audio_scale = (
        contract["full_audio_criteria"]
        / contract["anchor_audio_criteria"]
    )
    projection_ready = not anchor_integrity_blockers and measured_wall_sec is not None
    components = {
        "main": {
            "anchor_latency_sec": round(main_anchor_sec, 5),
            "scale": round(main_scale, 6),
            "projected_hours": (
                round(main_anchor_sec * main_scale / 3600, 4)
                if projection_ready else None
            ),
            "normalization": "task_count",
            "measurement": main_measurement,
        },
        "visual": {
            "anchor_latency_sec": round(visual_latency_sec, 5),
            "scale": round(visual_scale, 6),
            "projected_hours": (
                round(visual_latency_sec * visual_scale / 3600, 4)
                if projection_ready else None
            ),
            "normalization": "visual_criteria",
        },
        "audio": {
            "anchor_latency_sec": round(audio_latency_sec, 5),
            "scale": round(audio_scale, 6),
            "projected_hours": (
                round(audio_latency_sec * audio_scale / 3600, 4)
                if projection_ready else None
            ),
            "normalization": "audio_criteria",
        },
    }
    projected_hours = (
        round(
            sum(
                component["projected_hours"]
                for component in components.values()
            ),
            4,
        )
        if projection_ready else None
    )

    unknown_volume = {
        "call_count": int(unknown_usage.get("call_count", 0) or 0),
        "input_tokens": int(unknown_usage.get("input_tokens", 0) or 0),
        "output_tokens": int(unknown_usage.get("output_tokens", 0) or 0),
        "cached_tokens": int(unknown_usage.get("cached_tokens", 0) or 0),
        "latency_sec": round(unknown_latency_sec, 5),
    }
    has_unknown = any(unknown_volume.values())
    envelope_hours = contract["chunk_envelope_hours"]
    if anchor_integrity_blockers:
        envelope_status = "incomplete_anchor_payload"
    elif has_unknown:
        envelope_status = "incomplete_unknown_perception"
    elif measured_wall_sec is None:
        envelope_status = "incomplete_missing_task_wall"
    elif projected_hours >= envelope_hours:
        envelope_status = "at_or_above_44h_envelope"
    else:
        envelope_status = "below_44h_envelope"

    targetable_errors = (
        judge_error_types.get("final_json_parse_failed", 0)
        + judge_error_types.get("empty_final_text", 0)
    )
    baseline_targetable_errors = (
        contract["baseline_final_json_parse_failed"]
        + contract["baseline_empty_final_text"]
    )
    non_targetable_errors = {
        error_type: count
        for error_type, count in sorted(judge_error_types.items())
        if error_type not in {"final_json_parse_failed", "empty_final_text"}
        and count > 0
    }
    if targetable_errors == 0:
        targetable_status = "eliminated"
    elif targetable_errors < baseline_targetable_errors:
        targetable_status = "improved"
    else:
        targetable_status = "no_improvement"
    if anchor_integrity_blockers:
        targetable_status = "inconclusive_invalid_anchor_payload"
    elif non_targetable_errors:
        targetable_status = "inconclusive_other_judge_errors"
    diagnostic_status = targetable_status

    audio_call_count = int(audio_usage.get("call_count", 0) or 0)
    visual_budget_errors = judge_error_types.get(
        "task_visual_budget_exceeded",
        0,
    )
    gate_blockers = list(anchor_integrity_blockers)
    if targetable_errors >= baseline_targetable_errors:
        gate_blockers.append("no_finalization_improvement")
    if non_targetable_errors:
        gate_blockers.append("non_targetable_judge_errors_present")
    if audio_call_count == 0:
        gate_blockers.append("audio_wiring_not_exercised")
    if visual_budget_errors > 0:
        gate_blockers.append("visual_budget_exceeded")
    if (
        envelope_status != "below_44h_envelope"
        and envelope_status != "incomplete_anchor_payload"
    ):
        gate_blockers.append(envelope_status)
    return {
        "method": contract["method"],
        "baseline_is_like_for_like": False,
        "baseline_caveat": (
            "schema 1.0 pre-perception payload; mini metrics are a "
            "main-judge-only reference, not a Sol Max multiplier"
        ),
        "anchor_task_count": task_count,
        "measured_anchor_wall_sec": (
            round(measured_wall_sec, 5)
            if measured_wall_sec is not None else None
        ),
        "anchor_integrity": {
            "status": "passed" if not anchor_integrity_blockers else "failed",
            "blockers": anchor_integrity_blockers,
        },
        "components": components,
        "projected_220_hours": projected_hours,
        "chunk_envelope_hours": envelope_hours,
        "envelope_status": envelope_status,
        "unknown_perception": unknown_volume,
        "diagnostic": {
            "baseline_targetable_errors": baseline_targetable_errors,
            "observed_targetable_errors": targetable_errors,
            "targetable_status": targetable_status,
            "non_targetable_errors": non_targetable_errors,
            "status": diagnostic_status,
        },
        "audio_wiring": {
            "call_count": audio_call_count,
            "status": "passed" if audio_call_count > 0 else "failed_no_audio_calls",
        },
        "visual_budget": {
            "task_visual_budget_exceeded": visual_budget_errors,
            "status": "passed" if visual_budget_errors == 0 else "failed",
        },
        "full_run_gate": {
            "status": (
                "blocked" if gate_blockers else "eligible_for_owner_review"
            ),
            "blockers": gate_blockers,
        },
        "main_reference": {
            "calls": contract["baseline_main_calls"],
            "latency_sec": round(
                contract["baseline_main_latency_ms"] / 1000,
                5,
            ),
            "observed_calls": sum(
                anchor["main"]["call_count"] for anchor in task_anchors
            ),
            "observed_latency_sec": round(total_main_latency_sec, 5),
            "calls_ratio": round(
                sum(anchor["main"]["call_count"] for anchor in task_anchors)
                / contract["baseline_main_calls"],
                6,
            ),
            "latency_ratio": round(
                total_main_latency_sec
                / (contract["baseline_main_latency_ms"] / 1000),
                6,
            ),
        },
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
    modality_projection = _modality_normalized_projection(
        grade,
        task_anchors,
        perception_usage,
        total_main_latency_sec,
        judge_error_types,
    )
    if modality_projection is not None:
        projected_220_wall_hours = modality_projection["projected_220_hours"]
        projection_status = modality_projection["envelope_status"]
        projection_method = modality_projection["method"]
    else:
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
        projection_method = "task_count_fallback"

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
        "projection_method": projection_method,
        "modality_projection": modality_projection,
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
        f"{a['projected_220_wall_hours']} ({a['projection_status']}; "
        f"method={a['projection_method']})"
    )
    projection = a.get("modality_projection")
    if projection is not None:
        lines.append("")
        lines.append("## Preregistered anchor decision")
        lines.append(f"- baseline caveat: {projection['baseline_caveat']}")
        lines.append(
            "- anchor integrity: "
            f"{projection['anchor_integrity']['status']} "
            f"(blockers={projection['anchor_integrity']['blockers']})"
        )
        diagnostic = projection["diagnostic"]
        lines.append(
            "- targetable finalization errors: "
            f"baseline={diagnostic['baseline_targetable_errors']}, "
            f"observed={diagnostic['observed_targetable_errors']}, "
            f"targetable_status={diagnostic['targetable_status']}, "
            f"other={diagnostic['non_targetable_errors']}, "
            f"status={diagnostic['status']}"
        )
        lines.append(
            "- audio wiring: "
            f"calls={projection['audio_wiring']['call_count']}, "
            f"status={projection['audio_wiring']['status']}"
        )
        lines.append(
            "- visual budget: "
            f"task_visual_budget_exceeded="
            f"{projection['visual_budget']['task_visual_budget_exceeded']}, "
            f"status={projection['visual_budget']['status']}"
        )
        lines.append(
            "- full-run gate: "
            f"{projection['full_run_gate']['status']} "
            f"(blockers={projection['full_run_gate']['blockers']})"
        )
        main_reference = projection["main_reference"]
        lines.append(
            "- mini main-judge-only reference: "
            f"calls={main_reference['calls']} → "
            f"{main_reference['observed_calls']} "
            f"(ratio={main_reference['calls_ratio']}), latency="
            f"{main_reference['latency_sec']}s → "
            f"{main_reference['observed_latency_sec']}s "
            f"(ratio={main_reference['latency_ratio']}); not a Sol Max multiplier"
        )
        lines.append("")
        lines.append("| component | anchor latency (s) | scale | projected hours | normalization |")
        lines.append("|---|--:|--:|--:|---|")
        for component_name in ("main", "visual", "audio"):
            component = projection["components"][component_name]
            lines.append(
                f"| {component_name} | {component['anchor_latency_sec']} | "
                f"{component['scale']} | {component['projected_hours']} | "
                f"{component['normalization']} |"
            )
        lines.append(
            f"- component total: {projection['projected_220_hours']}h; "
            f"44h gate={projection['envelope_status']}"
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
