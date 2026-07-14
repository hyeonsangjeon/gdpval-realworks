#!/usr/bin/env python3
"""Reproduce the pinned exp026/exp027 paired diagnostic metrics."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import statistics
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_EXP026 = (
    "https://huggingface.co/datasets/HyeonSang/"
    "exp026_sandbox_skills_multimodal/raw/"
    "47aed3c0b13eaa90eb02803bec9d5c75e559f416/self_report.json"
)
DEFAULT_EXP027 = (
    "https://huggingface.co/datasets/HyeonSang/"
    "exp027_GPT54_default_subprocess_bridge50/raw/"
    "830d476f24da9d842882ac69ed785c546b362a91/self_report.json"
)
EXPECTED_EXP026_SHA256 = "ec93ad9ae193734bfc7cb78c1879328ef8a1ff6777af80dcd57b38acc5a0fa3a"
EXPECTED_EXP027_SHA256 = "783183dbc9d8aae3811b164c40ee8681998c005ebc8b63a8fcd943c829f72a80"
DEFAULT_SELECTION = (
    Path(__file__).resolve().parent.parent
    / "tasks" / "0714_tuesday" / "exp027_bridge50_selection.json"
)
BOOTSTRAP_SEED = 20260714
BOOTSTRAP_RESAMPLES = 10_000
HTTP_TIMEOUT_SECONDS = 30
STATUSES = ("success", "qa_failed", "error")


def _read_bytes(source: str | Path) -> bytes:
    value = str(source)
    if value.startswith(("https://", "http://")):
        request = urllib.request.Request(value, headers={"User-Agent": "gdpval-analysis"})
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            return response.read()
    return Path(value).read_bytes()


def _load_json(
    source: str | Path,
    expected_sha256: str | None = None,
) -> tuple[dict[str, Any], str]:
    content = _read_bytes(source)
    digest = hashlib.sha256(content).hexdigest()
    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError(
            f"source SHA-256 mismatch: expected {expected_sha256}, got {digest}"
        )
    return json.loads(content), digest


def _index_tasks(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    tasks = report.get("task_results") or []
    indexed = {task["task_id"]: task for task in tasks}
    if len(indexed) != len(tasks):
        raise ValueError("task_results contains duplicate task IDs")
    return indexed


def _mean(values: list[float]) -> float | None:
    return statistics.fmean(values) if values else None


def _quantile(sorted_values: list[float], probability: float) -> float:
    if not sorted_values:
        raise ValueError("quantile requires at least one value")
    position = (len(sorted_values) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    weight = position - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def _bootstrap_mean_ci(
    deltas: list[float],
    *,
    seed: int = BOOTSTRAP_SEED,
    resamples: int = BOOTSTRAP_RESAMPLES,
) -> list[float] | None:
    if not deltas:
        return None
    rng = random.Random(seed)
    means = sorted(
        statistics.fmean(rng.choice(deltas) for _ in deltas)
        for _ in range(resamples)
    )
    return [_quantile(means, 0.025), _quantile(means, 0.975)]


def _paired_numeric(
    ids: list[str],
    left: dict[str, dict[str, Any]],
    right: dict[str, dict[str, Any]],
    field: str,
    *,
    both_success: bool = False,
) -> dict[str, Any]:
    pairs: list[tuple[float, float]] = []
    for task_id in ids:
        left_task = left[task_id]
        right_task = right[task_id]
        if both_success and (
            left_task.get("status") != "success"
            or right_task.get("status") != "success"
        ):
            continue
        left_value = left_task.get(field)
        right_value = right_task.get(field)
        if isinstance(left_value, (int, float)) and isinstance(right_value, (int, float)):
            pairs.append((float(left_value), float(right_value)))

    deltas = [right_value - left_value for left_value, right_value in pairs]
    return {
        "n": len(pairs),
        "exp026_mean": _mean([left_value for left_value, _ in pairs]),
        "exp027_mean": _mean([right_value for _, right_value in pairs]),
        "mean_delta": _mean(deltas),
        "median_delta": statistics.median(deltas) if deltas else None,
        "wins": sum(delta > 0 for delta in deltas),
        "ties": sum(delta == 0 for delta in deltas),
        "losses": sum(delta < 0 for delta in deltas),
        "bootstrap_mean_95_ci": _bootstrap_mean_ci(deltas),
    }


def _exact_two_sided_binomial(discordant_left: int, discordant_right: int) -> float:
    total = discordant_left + discordant_right
    if total == 0:
        return 1.0
    tail = min(discordant_left, discordant_right)
    probability = sum(math.comb(total, value) for value in range(tail + 1)) / (2 ** total)
    return min(1.0, 2 * probability)


def analyze(
    exp026: dict[str, Any],
    exp027: dict[str, Any],
    selection: dict[str, Any],
) -> dict[str, Any]:
    left = _index_tasks(exp026)
    right = _index_tasks(exp027)
    groups = selection["groups"]
    ids = sorted(task_id for group in groups.values() for task_id in group)
    if len(ids) != len(set(ids)):
        raise ValueError("selection groups contain duplicate task IDs")
    missing_left = set(ids) - set(left)
    missing_right = set(ids) - set(right)
    if missing_left or missing_right:
        raise ValueError(
            f"selected task IDs missing from reports: exp026={len(missing_left)}, "
            f"exp027={len(missing_right)}"
        )

    matrix = {
        left_status: {right_status: 0 for right_status in STATUSES}
        for left_status in STATUSES
    }
    order = {"error": 0, "qa_failed": 1, "success": 2}
    ordered = {"improved": 0, "unchanged": 0, "degraded": 0}
    for task_id in ids:
        left_status = left[task_id]["status"]
        right_status = right[task_id]["status"]
        matrix[left_status][right_status] += 1
        delta = order[right_status] - order[left_status]
        ordered["improved" if delta > 0 else "degraded" if delta < 0 else "unchanged"] += 1

    left_success_right_non = sum(matrix["success"][status] for status in ("qa_failed", "error"))
    left_non_right_success = sum(matrix[status]["success"] for status in ("qa_failed", "error"))

    group_metrics = {}
    for group_name, group_ids in groups.items():
        group_metrics[group_name] = {
            "task_count": len(group_ids),
            "exp026_status": {
                status: sum(left[task_id]["status"] == status for task_id in group_ids)
                for status in STATUSES
            },
            "exp027_status": {
                status: sum(right[task_id]["status"] == status for task_id in group_ids)
                for status in STATUSES
            },
            "qa": _paired_numeric(group_ids, left, right, "qa_score"),
            "latency_ms": _paired_numeric(group_ids, left, right, "latency_ms"),
        }

    return {
        "selection": {
            "task_count": len(ids),
            "group_counts": {name: len(group_ids) for name, group_ids in groups.items()},
            "task_ids_sha256": hashlib.sha256(
                ("\n".join(ids) + "\n").encode("utf-8")
            ).hexdigest(),
            "outcome_selected": True,
        },
        "status_transition_matrix": matrix,
        "status_totals": {
            "exp026": {
                status: sum(left[task_id]["status"] == status for task_id in ids)
                for status in STATUSES
            },
            "exp027": {
                status: sum(right[task_id]["status"] == status for task_id in ids)
                for status in STATUSES
            },
        },
        "ordered_outcome_change": ordered,
        "success_discordance": {
            "exp026_non_success_to_exp027_success": left_non_right_success,
            "exp026_success_to_exp027_non_success": left_success_right_non,
            "exact_two_sided_binomial_descriptive": _exact_two_sided_binomial(
                left_non_right_success, left_success_right_non
            ),
            "inferential_warning": (
                "Outcome-based task selection violates the independence needed "
                "for confirmatory significance interpretation."
            ),
        },
        "self_qa": {
            "both_scores": _paired_numeric(ids, left, right, "qa_score"),
            "both_success": _paired_numeric(
                ids, left, right, "qa_score", both_success=True
            ),
        },
        "latency_ms": {
            "all_tasks": _paired_numeric(ids, left, right, "latency_ms"),
            "both_success": _paired_numeric(
                ids, left, right, "latency_ms", both_success=True
            ),
        },
        "retried_tasks": {
            "exp026": sum(bool(left[task_id].get("retried")) for task_id in ids),
            "exp027": sum(bool(right[task_id].get("retried")) for task_id in ids),
        },
        "groups": group_metrics,
        "bootstrap": {
            "seed": BOOTSTRAP_SEED,
            "resamples": BOOTSTRAP_RESAMPLES,
            "interval": "percentile 95%",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exp026", default=DEFAULT_EXP026)
    parser.add_argument("--exp027", default=DEFAULT_EXP027)
    parser.add_argument("--selection", default=str(DEFAULT_SELECTION))
    parser.add_argument("--output")
    args = parser.parse_args()

    exp026, exp026_hash = _load_json(
        args.exp026,
        EXPECTED_EXP026_SHA256 if args.exp026 == DEFAULT_EXP026 else None,
    )
    exp027, exp027_hash = _load_json(
        args.exp027,
        EXPECTED_EXP027_SHA256 if args.exp027 == DEFAULT_EXP027 else None,
    )
    selection, selection_hash = _load_json(args.selection)
    result = analyze(exp026, exp027, selection)
    result["sources"] = {
        "exp026": {"location": args.exp026, "sha256": exp026_hash},
        "exp027": {"location": args.exp027, "sha256": exp027_hash},
        "selection": {"location": args.selection, "sha256": selection_hash},
    }
    payload = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
