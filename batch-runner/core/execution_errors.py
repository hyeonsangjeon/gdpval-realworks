"""Stable error categories shared by the execution backends.

Written for the generated-code backends, whose failure text is a traceback;
the Codex agent backend uses it too, for the sentence a provider returns when
it refuses a turn. Both need the same thing from it -- a fixed word for why,
carrying none of the message, so a failure can be counted and published
without the endpoint or the wording travelling with it.
"""

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
    "ratelimiterror": "rate_limited",
    "syntaxerror": "syntax_error",
    "timeouterror": "timeout",
    "timeoutexpired": "timeout",
    "typeerror": "type_error",
    "unicodedecodeerror": "binary_decode_error",
    "valueerror": "value_error",
}

#: What a provider says when it refused the request for rate rather than for
#: content. Deliberately no bare ``429``: a traceback's ``line 429`` would
#: match it, and mistaking a real defect for a transient one is how a
#: deterministic failure gets attempted three times.
_RATE_LIMIT_MARKERS = (
    "rate limit",
    "ratelimit",
    "too many requests",
    "error code: 429",
    "status code: 429",
    "http 429",
)


def _message_category(message: str) -> Optional[str]:
    lowered = message.lower()
    # First, because it is the one marker set that reliably co-occurs with
    # another: a client that keeps retrying a refused request reports its own
    # deadline, so the text says both "rate limit" and "timed out". The
    # refusal is the cause; the deadline is what the cause looked like.
    if any(marker in lowered for marker in _RATE_LIMIT_MARKERS):
        return "rate_limited"
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

    # No ``rate_limited`` row below. Every rate-limit text is already decided
    # by one of the two `_message_category` calls above -- as the exception's
    # message, or as the whole text -- so a row here could never be reached,
    # and an unreachable row is a second place to keep the answer in.
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
