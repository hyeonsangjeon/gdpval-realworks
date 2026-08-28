"""Shared projection from prepared metadata and raw Step 2 results."""

from __future__ import annotations

from core.cost_projection import project_cost_receipt


def project_result_row(task_meta: dict, result: dict) -> dict:
    if not isinstance(task_meta, dict) or not isinstance(result, dict):
        raise ValueError("result projection inputs must be objects")
    task_id = result.get("task_id")
    if not isinstance(task_id, str) or not task_id:
        raise ValueError("result projection task identity is invalid")
    qa = result.get("qa") or {}
    if not isinstance(qa, dict):
        raise ValueError("result projection QA payload is invalid")
    files = result.get("deliverable_files") or []
    if not isinstance(files, list):
        raise ValueError("result projection deliverable files are invalid")
    issues = qa.get("issues", [])
    if not isinstance(issues, list):
        raise ValueError("result projection QA issues are invalid")
    cost = project_cost_receipt(
        result.get("problem_solving_cost"),
        f"result projection problem_solving_cost for {task_id}",
    )

    row = {
        "task_id": task_id,
        "sector": task_meta.get("sector", ""),
        "occupation": task_meta.get("occupation", ""),
        "needs_files": task_meta.get("needs_files", False),
        "instruction": task_meta.get("instruction", ""),
        "reference_file_urls": task_meta.get("reference_file_urls", []),
        "status": result.get("status"),
        "retried": result.get("resume_round") is not None,
        "resume_round": result.get("resume_round"),
        "content": result.get("content"),
        "deliverable_text": result.get("deliverable_text", ""),
        "deliverable_files": files,
        "deliverable_files_count": len(files),
        "model": result.get("model"),
        "usage": result.get("usage"),
        "observability": result.get("observability", {}),
        "latency_ms": result.get("latency_ms", 0),
        "timestamp": result.get("timestamp"),
        "qa_passed": qa.get("passed"),
        "qa_score": qa.get("score"),
        "qa_llm_passed": qa.get("llm_passed"),
        "qa_issues": issues,
        "qa_issues_count": len(issues),
        "qa_suggestion": qa.get("suggestion", ""),
        "qa_undetermined": qa.get("undetermined", False),
        "error": result.get("error"),
    }
    # Absent stays absent. A run that predates cost instrumentation must not
    # gain a null field that reads like a recorded zero downstream.
    if cost is not None:
        row["problem_solving_cost"] = cost
    return row
