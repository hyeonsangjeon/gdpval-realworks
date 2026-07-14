"""Stable error categories shared by generated-code execution backends."""

from __future__ import annotations

import re
from typing import Optional


_EXCEPTION_CATEGORY = {
    "attributeerror": "api_compatibility",
    "filenotfounderror": "file_not_found",
    "importerror": "import_error",
    "indentationerror": "syntax_error",
    "keyerror": "schema_error",
    "memoryerror": "out_of_memory",
    "modulenotfounderror": "import_error",
    "outofmemoryerror": "out_of_memory",
    "permissionerror": "permission_error",
    "syntaxerror": "syntax_error",
    "timeouterror": "timeout",
    "timeoutexpired": "timeout",
    "typeerror": "type_error",
    "unicodedecodeerror": "binary_decode_error",
    "valueerror": "value_error",
}


def _message_category(message: str) -> Optional[str]:
    lowered = message.lower()
    oom_markers = (
        "out of memory",
        "insufficient memory",
        "cannot allocate memory",
        "failed to allocate",
    )
    if any(marker in lowered for marker in oom_markers):
        return "out_of_memory"
    if "not valid utf-8" in lowered:
        return "binary_decode_error"
    if any(marker in lowered for marker in ("timed out", "execution timeout")):
        return "timeout"
    return None


def _last_exception_category(text: str) -> Optional[str]:
    matches = re.findall(
        r"(?mi)^\s*(?:[\w.]+\.)?"
        r"([A-Za-z_][\w]*(?:Error|Exception|Expired))"
        r"(?:\s*:\s*(.*))?\s*$",
        text,
    )
    if not matches:
        return None
    exception_name, message = matches[-1]
    mapped = _EXCEPTION_CATEGORY.get(exception_name.lower())
    if mapped:
        return mapped
    return _message_category(message) or "execution_error"


def classify_execution_error(text: Optional[str]) -> Optional[str]:
    """Classify runtime text without retaining it in persisted provenance."""
    lowered = (text or "").lower()
    if not lowered:
        return None
    if lowered.startswith("memory_error:"):
        return "out_of_memory"
    exception_category = _last_exception_category(text or "")
    if exception_category:
        return exception_category

    direct_message_category = _message_category(text or "")
    if direct_message_category:
        return direct_message_category

    categories = (
        (
            "out_of_memory",
            (
                "out of memory",
                "memoryerror",
                "outofmemoryerror",
                "insufficient memory",
                "cannot allocate memory",
                "failed to allocate",
                "oom",
                "exit code 137",
                "exit 137",
            ),
        ),
        (
            "timeout",
            (
                "timed out",
                "execution timeout",
                "timeout exceeded",
            ),
        ),
        ("syntax_error", ("syntaxerror", "indentationerror")),
        ("binary_decode_error", ("unicodedecodeerror",)),
        ("schema_error", ("keyerror",)),
        ("api_compatibility", ("attributeerror",)),
        ("import_error", ("importerror", "modulenotfounderror")),
        ("permission_error", ("permissionerror", "permission denied")),
        ("file_not_found", ("filenotfounderror", "no such file")),
        ("type_error", ("typeerror",)),
        ("value_error", ("valueerror",)),
    )
    for category, markers in categories:
        if any(
            bool(re.search(r"\boom\b", lowered)) if marker == "oom"
            else marker in lowered
            for marker in markers
        ):
            return category
    return "execution_error"
