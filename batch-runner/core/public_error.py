"""Stable public projection for task execution failures."""

from __future__ import annotations

import re


_ERROR_TYPE_RE = re.compile(
    r"\b([A-Za-z][A-Za-z0-9_]*(?:Error|Exception))\b"
)


def public_task_error(error: object) -> dict[str, str]:
    """Return an endpoint- and message-free public error identity."""
    if isinstance(error, BaseException):
        error_type = type(error).__name__
        if _ERROR_TYPE_RE.fullmatch(error_type) is None:
            error_type = "TaskExecutionError"
    else:
        match = _ERROR_TYPE_RE.search(str(error or ""))
        error_type = match.group(1) if match else "TaskExecutionError"
    return {
        "error_code": "task_execution_error",
        "error_type": error_type,
    }


def public_task_error_text(error: object) -> str:
    """Return a compact public error string for legacy result schemas."""
    projected = public_task_error(error)
    return f"{projected['error_code']}:{projected['error_type']}"


def public_provider_error_text(error: object) -> str:
    """Return an endpoint- and message-free provider failure identity."""
    projected = public_task_error(error)
    return f"provider_error:{projected['error_type']}"
