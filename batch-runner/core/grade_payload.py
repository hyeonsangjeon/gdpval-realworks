"""Shared validation for persisted grade payloads."""

from __future__ import annotations

import re
from typing import Any

from jsonschema import validate


FULL_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def validate_grade_payload(payload: Any, schema: dict) -> None:
    """Validate one legacy or current grade payload before persistence."""
    validate(instance=payload, schema=schema)
    if not isinstance(payload, dict) or "run_status" not in payload:
        return

    status = payload.get("run_status")
    expected_count = payload.get("expected_task_count")
    expected_hash = payload.get("expected_ordered_task_ids_sha256")
    tasks = payload.get("tasks")
    routes = payload.get("azure_ai_routes")
    primary_fingerprint = payload.get("azure_ai_runtime_fingerprint")

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