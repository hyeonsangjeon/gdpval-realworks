"""Shared validation for persisted grade payloads."""

from __future__ import annotations

import re
from typing import Any

from jsonschema import validate


FULL_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def validate_grade_payload(payload: Any, schema: dict) -> None:
    """Validate one legacy or current grade payload before persistence."""
    validate(instance=payload, schema=schema)
    if not isinstance(payload, dict):
        return
    current_schema = payload.get("schema_version") == "1.2"
    if current_schema and "run_status" not in payload:
        raise ValueError("current grade lifecycle identity is missing")
    if "run_status" not in payload:
        return

    status = payload.get("run_status")
    expected_count = payload.get("expected_task_count")
    expected_hash = payload.get("expected_ordered_task_ids_sha256")
    tasks = payload.get("tasks")
    routes = payload.get("azure_ai_routes")
    primary_fingerprint = payload.get("azure_ai_runtime_fingerprint")
    summary = payload.get("summary")

    if status not in {"partial", "final", "diagnostic"}:
        raise ValueError("grade run_status is invalid")
    if type(expected_count) is not int or expected_count < 1:
        raise ValueError("grade expected_task_count is invalid")
    if not isinstance(expected_hash, str) or not FULL_SHA256_RE.fullmatch(
        expected_hash
    ):
        raise ValueError("grade expected task identity is invalid")
    if not isinstance(tasks, list) or len(tasks) > expected_count:
        raise ValueError("grade task count exceeds expected task count")
    if status == "final" and len(tasks) != expected_count:
        raise ValueError("final grade task count is incomplete")
    if not isinstance(routes, list) or not routes:
        raise ValueError("grade Azure AI routes are missing")
    if (
        not isinstance(primary_fingerprint, str)
        or not FULL_SHA256_RE.fullmatch(primary_fingerprint)
    ):
        raise ValueError("primary grader runtime fingerprint is invalid")
    primary_route = routes[0]
    if (
        not isinstance(primary_route, dict)
        or primary_route.get("workload") != "grader"
        or primary_route.get("runtime_fingerprint") != primary_fingerprint
    ):
        raise ValueError("primary grader route fingerprint mismatch")
    if not current_schema:
        return
    cost = summary.get("cost") if isinstance(summary, dict) else None
    if not isinstance(cost, dict):
        raise ValueError("grade cost provenance is missing")
    required_cost_fields = {
        "estimated_cost_usd",
        "pricing_complete",
        "unpriced_models",
    }
    if not required_cost_fields.issubset(cost):
        raise ValueError("current grade cost provenance is incomplete")
    if cost["estimated_cost_usd"] is not None:
        raise ValueError("current grade estimated cost must remain unpriced")
    if cost["pricing_complete"] is not False:
        raise ValueError("current grade pricing must be incomplete")
    unpriced_models = cost["unpriced_models"]
    if (
        not isinstance(unpriced_models, list)
        or not unpriced_models
        or any(not isinstance(model, str) or not model for model in unpriced_models)
        or len(unpriced_models) != len(set(unpriced_models))
    ):
        raise ValueError("current grade unpriced model identity is invalid")
    judge = payload.get("judge")
    if not isinstance(judge, dict):
        raise ValueError("current grade judge identity is missing")
    expected_unpriced_models = {judge.get("model")}
    perception = judge.get("perception", {})
    if not isinstance(perception, dict):
        raise ValueError("current grade perception identity is invalid")
    for modality in perception.values():
        if not isinstance(modality, dict):
            raise ValueError("current grade perception identity is invalid")
        expected_unpriced_models.add(
            modality.get("model") or modality.get("deployment")
        )
    if (
        any(
            not isinstance(model, str) or not model
            for model in expected_unpriced_models
        )
        or set(unpriced_models) != expected_unpriced_models
    ):
        raise ValueError(
            "current grade unpriced models do not match persisted model identity"
        )