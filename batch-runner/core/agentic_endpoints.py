"""Preregistered fixed-denominator endpoints for the 20-task paired diagnostic."""

from __future__ import annotations

import json
import math
from typing import Any, Mapping, Sequence

from core.agentic_budget import AgenticBudgetLedger


N_DIAGNOSTIC = 20
WALL_CAP_MS = 1_200_000.0
ITEM_STATES = ("missing", "judge_error", "score_excluded", "scored")


def compute_paired_endpoints(
    *,
    expected_task_ids: Sequence[str],
    baseline_results: Sequence[Mapping[str, Any]],
    treatment_results: Sequence[Mapping[str, Any]],
    rubric_maxima: Mapping[str, Sequence[Mapping[str, Any]]],
    baseline_grades: Mapping[str, Any],
    treatment_grades: Mapping[str, Any],
    budget_ledger: AgenticBudgetLedger,
    paired_run_id: str,
    baseline_task_scopes: Mapping[str, str],
    treatment_task_scopes: Mapping[str, str],
) -> dict:
    expected = list(expected_task_ids)
    if len(expected) != N_DIAGNOSTIC or len(set(expected)) != N_DIAGNOSTIC:
        raise ValueError("paired endpoint requires 20 unique frozen task IDs")
    baseline = _index_exact(baseline_results, expected, "baseline")
    treatment = _index_exact(treatment_results, expected, "treatment")
    maxima = _validate_maxima(rubric_maxima, expected)
    substrate_hashes = {
        _substrate_hash(result)
        for result in [*baseline.values(), *treatment.values()]
    }
    if len(substrate_hashes) != 1:
        raise ValueError(
            "baseline and treatment substrate manifests are not byte-identical"
        )
    substrate_sha256 = next(iter(substrate_hashes))

    baseline_complete = {
        task_id: _completed(baseline[task_id], treatment=False)
        for task_id in expected
    }
    treatment_complete = {
        task_id: _completed(treatment[task_id], treatment=True)
        for task_id in expected
    }
    completion_baseline = sum(baseline_complete.values()) / N_DIAGNOSTIC
    completion_treatment = sum(treatment_complete.values()) / N_DIAGNOSTIC

    baseline_quality = _quality(
        expected,
        maxima,
        _normalize_grade_document(baseline_grades, expected, "baseline"),
        baseline_complete,
    )
    treatment_quality = _quality(
        expected,
        maxima,
        _normalize_grade_document(treatment_grades, expected, "treatment"),
        treatment_complete,
    )
    baseline_times = [
        _time_to_valid(baseline[task_id], treatment=False)
        for task_id in expected
    ]
    treatment_times = [
        _time_to_valid(treatment[task_id], treatment=True)
        for task_id in expected
    ]
    baseline_p95 = _nearest_rank_p95(baseline_times)
    treatment_p95 = _nearest_rank_p95(treatment_times)
    baseline_cost_by_task = _ledger_costs(
        budget_ledger, paired_run_id, baseline_task_scopes, expected, "baseline"
    )
    treatment_cost_by_task = _ledger_costs(
        budget_ledger, paired_run_id, treatment_task_scopes, expected, "treatment"
    )
    _validate_aggregate_reservation_sets(
        budget_ledger,
        paired_run_id,
        baseline_task_scopes,
        treatment_task_scopes,
    )
    baseline_costs = [baseline_cost_by_task[task_id] for task_id in expected]
    treatment_costs = [treatment_cost_by_task[task_id] for task_id in expected]
    baseline_mean_cost = sum(baseline_costs) / N_DIAGNOSTIC
    treatment_mean_cost = sum(treatment_costs) / N_DIAGNOSTIC

    return {
        "schema_version": "agentic-paired-endpoints-v1",
        "denominator_tasks": N_DIAGNOSTIC,
        "ordered_task_ids": expected,
        "common_substrate_sha256": substrate_sha256,
        "completion": {
            "baseline": completion_baseline,
            "treatment": completion_treatment,
            "delta_percentage_points": round(
                100 * (completion_treatment - completion_baseline), 8
            ),
            "baseline_by_task": baseline_complete,
            "treatment_by_task": treatment_complete,
        },
        "quality": {
            "baseline": baseline_quality,
            "treatment": treatment_quality,
            "task_macro_delta": round(
                treatment_quality["task_macro"]
                - baseline_quality["task_macro"],
                8,
            ),
        },
        "timing": {
            "missing_artifact_value_ms": WALL_CAP_MS,
            "baseline_values_ms": baseline_times,
            "treatment_values_ms": treatment_times,
            "baseline_p95_ms": baseline_p95,
            "treatment_p95_ms": treatment_p95,
            "p95_ratio": _ratio(treatment_p95, baseline_p95),
        },
        "cost": {
            "baseline_values_usd": baseline_costs,
            "treatment_values_usd": treatment_costs,
            "baseline_mean_usd": round(baseline_mean_cost, 8),
            "treatment_mean_usd": round(treatment_mean_cost, 8),
            "ratio": _ratio(treatment_mean_cost, baseline_mean_cost),
            "basis": "settled finite usage plus unreconciled reservation",
        },
    }


def _index_exact(
    results: Sequence[Mapping[str, Any]], expected: list[str], label: str
) -> dict[str, Mapping[str, Any]]:
    indexed = {}
    for result in results:
        task_id = result.get("task_id")
        if not isinstance(task_id, str) or task_id in indexed:
            raise ValueError(f"{label} contains missing or duplicate task ID")
        indexed[task_id] = result
    if set(indexed) != set(expected):
        raise ValueError(f"{label} task IDs differ from frozen paired set")
    return indexed


def _validate_maxima(
    raw: Mapping[str, Sequence[Mapping[str, Any]]], expected: list[str]
) -> dict[str, list[tuple[str, float]]]:
    if set(raw) != set(expected):
        raise ValueError("rubric maxima task IDs differ from frozen paired set")
    output = {}
    for task_id in expected:
        raw_items = raw[task_id]
        if not isinstance(raw_items, Sequence) or isinstance(
            raw_items, (str, bytes)
        ):
            raise ValueError("rubric items must be a sequence")
        values: list[tuple[str, float]] = []
        seen = set()
        for item in raw_items:
            if not isinstance(item, Mapping) or set(item) != {
                "rubric_item_id", "max_score"
            }:
                raise ValueError("rubric item identity fields are invalid")
            item_id = item.get("rubric_item_id")
            maximum = item.get("max_score")
            if (
                not isinstance(item_id, str)
                or not item_id
                or item_id in seen
                or isinstance(maximum, bool)
                or not isinstance(maximum, (int, float))
                or not math.isfinite(float(maximum))
            ):
                raise ValueError("rubric item identity or maximum is invalid")
            seen.add(item_id)
            values.append((item_id, float(maximum)))
        if not any(maximum > 0 for _, maximum in values):
            raise ValueError(f"task has zero positive rubric denominator: {task_id}")
        output[task_id] = values
    return output


def _normalize_grade_document(
    raw: Mapping[str, Any], expected: list[str], label: str
) -> dict[str, dict[str, Any]]:
    if not isinstance(raw, Mapping) or not isinstance(raw.get("tasks"), list):
        raise ValueError(f"{label} grade must use the Step 8 tasks schema")
    output = {}
    expected_set = set(expected)
    for task in raw["tasks"]:
        if not isinstance(task, Mapping):
            raise ValueError(f"{label} grade task is invalid")
        task_id = task.get("task_id")
        if (
            not isinstance(task_id, str)
            or task_id not in expected_set
            or task_id in output
        ):
            raise ValueError(f"{label} grade has unknown or duplicate task ID")
        raw_items = task.get("items")
        if not isinstance(raw_items, list):
            raise ValueError(f"{label} grade task items are invalid")
        items = {}
        for item in raw_items:
            if not isinstance(item, Mapping):
                raise ValueError(f"{label} grade item is invalid")
            item_id = item.get("rubric_item_id")
            if not isinstance(item_id, str) or not item_id or item_id in items:
                raise ValueError(
                    f"{label} grade has missing or duplicate rubric item ID"
                )
            items[item_id] = item
        task_error = task.get("error")
        if task_error is not None and not isinstance(task_error, str):
            raise ValueError(f"{label} grade task error is invalid")
        output[task_id] = {"items": items, "error": task_error}
    return output


def _completed(result: Mapping[str, Any], *, treatment: bool) -> int:
    if result.get("status") != "success" or not result.get("deliverable_files"):
        return 0
    observability = result.get("observability") or {}
    if treatment:
        metrics = observability.get("agentic_metrics")
        return int(
            isinstance(metrics, Mapping)
            and metrics.get("usage_complete") is True
            and metrics.get("terminal_error_category") is None
            and (metrics.get("finalize_attempts") or 0) > 0
        )
    sandbox = observability.get("sandbox")
    budget = observability.get("budget_metrics")
    return int(
        isinstance(sandbox, Mapping)
        and sandbox.get("final_status") in {"ok", "repaired_ok"}
        and isinstance(budget, Mapping)
        and budget.get("usage_complete") is True
    )


def _quality(
    expected: list[str],
    maxima: Mapping[str, list[tuple[str, float]]],
    grades: Mapping[str, Mapping[str, Any]],
    completion: Mapping[str, int],
) -> dict:
    task_scores = []
    state_counts = {state: 0 for state in ITEM_STATES}
    total_awarded = 0.0
    total_maximum = sum(
        sum(maximum for _, maximum in maxima[task_id] if maximum > 0)
        for task_id in expected
    )
    expected_items = sum(len(maxima[task_id]) for task_id in expected)
    missing_task_grades = 0
    task_errors = {}
    for task_id in expected:
        grade = grades.get(task_id)
        if grade is None:
            missing_task_grades += 1
            items = {}
            task_error = None
        else:
            items = grade["items"]
            task_error = grade.get("error")
            if task_error:
                task_errors[task_id] = task_error[:200]
        expected_item_ids = {item_id for item_id, _ in maxima[task_id]}
        if not set(items) <= expected_item_ids:
            raise ValueError("grade contains rubric item outside frozen rubric")
        awarded = 0.0
        for item_id, maximum in maxima[task_id]:
            item = items.get(item_id)
            state = _grade_item_state(item, task_error)
            state_counts[state] += 1
            if state == "scored" and completion[task_id]:
                assert item is not None
                value = item.get("awarded_score")
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(float(value))
                ):
                    raise ValueError("scored grade item must have finite award")
                if maximum > 0:
                    awarded += min(max(float(value), 0.0), maximum)
                elif maximum < 0:
                    awarded += min(max(float(value), maximum), 0.0)
        awarded = awarded if completion[task_id] else 0.0
        total_awarded += awarded
        positive_maximum = sum(
            maximum for _, maximum in maxima[task_id] if maximum > 0
        )
        task_scores.append(
            100 * min(max(awarded / positive_maximum, 0.0), 1.0)
        )
    return {
        "task_macro": round(sum(task_scores) / N_DIAGNOSTIC, 8),
        "rubric_weighted": round(
            100 * min(max(total_awarded / total_maximum, 0.0), 1.0), 8
        ),
        "task_scores": task_scores,
        "expected_item_denominator": expected_items,
        "item_state_counts": state_counts,
        "item_state_rates": {
            state: round(count / expected_items, 8)
            for state, count in state_counts.items()
        },
        "missing_task_grade_count": missing_task_grades,
        "task_error_count": len(task_errors),
        "task_errors_by_task": task_errors,
    }


def _grade_item_state(
    item: Any, task_error: Any
) -> str:
    if item is None:
        return "missing"
    if not isinstance(item, Mapping):
        raise ValueError("grade item is invalid")
    verdict = item.get("verdict")
    if task_error or verdict == "judge_error":
        return "judge_error"
    if item.get("score_excluded") is True:
        return "score_excluded"
    if verdict not in {"pass", "partial", "fail"}:
        raise ValueError("grade item verdict is invalid")
    return "scored"


def _time_to_valid(
    result: Mapping[str, Any], *, treatment: bool
) -> float:
    observability = result.get("observability") or {}
    generic = (observability.get("execution_metrics") or {}).get(
        "time_to_valid_artifact_ms"
    )
    specialized_block = (
        observability.get("agentic_metrics")
        if treatment else observability.get("budget_metrics")
    ) or {}
    specialized = specialized_block.get("time_to_valid_artifact_ms")
    generic_value = _valid_time(generic)
    specialized_value = _valid_time(specialized)
    if (
        generic_value is not None
        and specialized_value is not None
        and generic_value != specialized_value
    ):
        raise ValueError("first-valid timing metrics disagree")
    value = specialized_value if specialized_value is not None else generic_value
    return WALL_CAP_MS if value is None else value


def _valid_time(value: Any) -> float | None:
    if (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and 0 <= value <= WALL_CAP_MS
    ):
        return float(value)
    return None


def _nearest_rank_p95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[math.ceil(0.95 * N_DIAGNOSTIC) - 1]


def _ledger_costs(
    ledger: AgenticBudgetLedger,
    paired_run_id: str,
    scopes: Mapping[str, str],
    expected: list[str],
    condition: str,
) -> dict[str, float]:
    if not isinstance(paired_run_id, str) or not paired_run_id:
        raise ValueError("paired run ID is required")
    if set(scopes) != set(expected):
        raise ValueError(f"{condition} ledger scopes differ from frozen paired set")
    if len(set(scopes.values())) != len(expected):
        raise ValueError(f"{condition} ledger scopes must be unique")
    costs = {}
    for task_id in expected:
        scope = scopes[task_id]
        try:
            parsed = json.loads(scope)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError(f"{condition} ledger scope is invalid") from exc
        if (
            not isinstance(parsed, list)
            or len(parsed) != 3
            or not isinstance(parsed[0], str)
            or not parsed[0]
            or parsed != [paired_run_id, condition, task_id]
            or json.dumps(parsed, separators=(",", ":")) != scope
        ):
            raise ValueError(f"{condition} ledger scope is invalid")
        value = float(ledger.usage(scope).cost_usd)
        if not math.isfinite(value) or value < 0:
            raise ValueError("ledger cost must be finite and non-negative")
        costs[task_id] = value
    return costs


def _validate_aggregate_reservation_sets(
    ledger: AgenticBudgetLedger,
    paired_run_id: str,
    baseline_scopes: Mapping[str, str],
    treatment_scopes: Mapping[str, str],
) -> None:
    unions = {}
    for condition, scopes in (
        ("baseline", baseline_scopes), ("treatment", treatment_scopes)
    ):
        task_requests = set().union(
            *(ledger.reservation_ids(scope) for scope in scopes.values())
        )
        condition_scope = json.dumps(
            ["condition", paired_run_id, condition], separators=(",", ":")
        )
        if ledger.reservation_ids(condition_scope) != task_requests:
            raise ValueError(
                f"{condition} aggregate reservations differ from task requests"
            )
        unions[condition] = task_requests
    paired_scope = json.dumps(
        ["paired_run", paired_run_id], separators=(",", ":")
    )
    if ledger.reservation_ids(paired_scope) != (
        unions["baseline"] | unions["treatment"]
    ):
        raise ValueError("paired aggregate reservations differ from task requests")


def _substrate_hash(result: Mapping[str, Any]) -> str:
    substrate = (result.get("observability") or {}).get("substrate") or {}
    value = substrate.get("sha256")
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError("paired task is missing substrate manifest identity")
    return value


def _ratio(numerator: float, denominator: float) -> float | str:
    if denominator == 0:
        return 1.0 if numerator == 0 else "infinity"
    return round(numerator / denominator, 8)