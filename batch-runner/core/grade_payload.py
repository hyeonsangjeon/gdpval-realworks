"""Shared validation for persisted grade payloads."""

from __future__ import annotations

import re
from typing import Any

from jsonschema import validate


FULL_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def canonical_rate(numerator: int, denominator: int) -> float:
    """Return a nonnegative ratio rounded half-up to four decimal places."""
    if denominator <= 0:
        return 0.0
    scaled = (2 * numerator * 10_000 + denominator) // (2 * denominator)
    return scaled / 10_000


def validate_grade_payload(payload: Any, schema: dict) -> None:
    """Validate one legacy or current grade payload before persistence."""
    validate(instance=payload, schema=schema)
    if not isinstance(payload, dict):
        return
    current_schema = payload.get("schema_version") in {"1.2", "1.3", "1.4"}
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
    if payload.get("schema_version") in {"1.3", "1.4"}:
        tasks = payload.get("tasks")
        if not isinstance(tasks, list):
            raise ValueError("current grade tasks are missing")
        judge_items = 0
        judge_errors = 0
        for task in tasks:
            if not isinstance(task, dict):
                raise ValueError("current grade task is invalid")
            items = task.get("items")
            if not isinstance(items, list):
                raise ValueError("current grade task items are invalid")
            for item in items:
                if not isinstance(item, dict):
                    raise ValueError("current grade item is invalid")
                if item.get("decided_by") == "judge":
                    judge_items += 1
                    if item.get("verdict") == "judge_error":
                        judge_errors += 1
                if (
                    item.get("verdict") == "judge_error"
                    and item.get("score_excluded") is not True
                ):
                    raise ValueError(
                        "schema 1.3 judge_error must be score_excluded"
                    )
            if items and all(
                item.get("score_excluded") is True for item in items
            ) and not task.get("error"):
                raise ValueError("all-excluded task must be unscored")

        summary = payload.get("summary")
        if not isinstance(summary, dict):
            raise ValueError("current grade summary is missing")
        graded_tasks = sum(1 for task in tasks if not task.get("error"))
        error_tasks = len(tasks) - graded_tasks
        if (
            summary.get("total_tasks") != len(tasks)
            or summary.get("graded_tasks") != graded_tasks
            or summary.get("error_tasks") != error_tasks
        ):
            raise ValueError("current grade task counts are inconsistent")
        openai_compat = summary.get("openai_compat")
        if not isinstance(openai_compat, dict):
            raise ValueError("current grade headline summary is missing")
        if graded_tasks == 0:
            if (
                openai_compat.get("avg_score_pct") is not None
                or openai_compat.get("ci_pct") is not None
                or openai_compat.get("perfect_count") != 0
                or openai_compat.get("zero_count") != 0
                or openai_compat.get("partial_count") != 0
                or openai_compat.get("inconsistent_count") != 0
            ):
                raise ValueError("unscored grade must not report headline scores")
        elif not isinstance(openai_compat.get("avg_score_pct"), (int, float)):
            raise ValueError("scored grade headline score is missing")
        wow = summary.get("wow")
        if not isinstance(wow, dict):
            raise ValueError("current grade health summary is missing")
        expected_error_rate = canonical_rate(judge_errors, judge_items)
        if wow.get("judge_error_rate") != expected_error_rate:
            raise ValueError("current grade judge_error_rate is inconsistent")
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
    if payload.get("schema_version") == "1.4":
        _validate_grading_cost_receipts(payload)


def _validate_grading_cost_receipts(payload: dict) -> None:
    """Check that the run total does not claim more certainty than its parts.

    The receipts' shape is the schema's business. The one thing the schema
    cannot say is how the summary relates to the rows it was summed from, and
    that relation is the whole guarantee: a total is only a total when every
    part behind it is known. A run holding one task whose usage never arrived
    may still report what it confirmed, but it reports it as a floor, not as
    the bill.

    Tasks that were never run are not parts of the total and do not count
    against it — a shard that graded ten of two hundred tasks has a complete
    bill for ten.
    """
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("grade summary is missing")
    run_receipt = summary.get("grading_cost")
    if not isinstance(run_receipt, dict):
        raise ValueError("schema 1.4 grade summary is missing its cost receipt")
    tasks = payload.get("tasks")
    if not isinstance(tasks, list):
        raise ValueError("grade tasks are missing")

    task_statuses = []
    for task in tasks:
        receipt = task.get("grading_cost") if isinstance(task, dict) else None
        if not isinstance(receipt, dict):
            raise ValueError("schema 1.4 grade task is missing its cost receipt")
        task_statuses.append(receipt.get("status"))

    if run_receipt.get("status") == "complete" and any(
        status not in {"complete", "not_run"} for status in task_statuses
    ):
        raise ValueError(
            "grade summary claims a complete cost over an incomplete task"
        )