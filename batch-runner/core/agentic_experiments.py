"""Reserved diagnostic experiment identities for Agentic Sandbox."""

from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

AGENTIC_CANARY_ID = "exp028"
AGENTIC_BASELINE_ID = "exp029"
AGENTIC_TREATMENT_ID = "exp030"
AGENTIC_EXPERIMENT_IDS = {
    AGENTIC_CANARY_ID,
    AGENTIC_BASELINE_ID,
    AGENTIC_TREATMENT_ID,
}
AGENTIC_CONDITIONS = {
    AGENTIC_CANARY_ID: "canary",
    AGENTIC_BASELINE_ID: "baseline",
    AGENTIC_TREATMENT_ID: "treatment",
}


def agentic_condition_identity(experiment_id: str) -> str:
    try:
        return AGENTIC_CONDITIONS[experiment_id]
    except KeyError as exc:
        raise ValueError("unknown agentic experiment ID") from exc


def validate_agentic_budget_for_experiment(
    experiment_id: str, budget: Any
) -> None:
    if not isinstance(budget, Mapping) or set(budget) != {
        "paired_run_id", "condition", "paired_run"
    }:
        raise ValueError("agentic budget fields are invalid")
    if experiment_id != AGENTIC_CANARY_ID:
        return
    count_maxima = {
        "attempts": 30,
        "input_tokens": 1_500_000,
        "output_tokens": 163_840,
    }
    cost_maximum = Decimal("6.25")
    for scope_name in ("condition", "paired_run"):
        scope = budget.get(scope_name)
        if not isinstance(scope, Mapping):
            raise ValueError(f"canary {scope_name} budget is invalid")
        for field in ("attempts", "input_tokens", "output_tokens"):
            value = scope.get(field)
            if type(value) is not int or not 0 < value <= count_maxima[field]:
                raise ValueError(f"canary {scope_name}.{field} exceeds hard cap")
        try:
            cost = Decimal(str(scope.get("cost_usd")))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise ValueError(f"canary {scope_name}.cost_usd is invalid") from exc
        if not cost.is_finite() or not 0 < cost <= cost_maximum:
            raise ValueError(f"canary {scope_name}.cost_usd exceeds hard cap")


def validate_agentic_experiment_identity(
    experiment_id: str,
    execution_mode: str,
    hardened_baseline: bool,
) -> None:
    if execution_mode == "agentic_sandbox":
        if experiment_id not in {AGENTIC_CANARY_ID, AGENTIC_TREATMENT_ID}:
            raise ValueError(
                "agentic_sandbox experiment ID must be exp028 or exp030"
            )
        return
    if execution_mode == "sandbox" and hardened_baseline:
        if experiment_id != AGENTIC_BASELINE_ID:
            raise ValueError("hardened sandbox baseline experiment ID must be exp029")