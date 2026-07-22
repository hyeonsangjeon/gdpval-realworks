"""Canonical source-task projections for Step 0 and Step 1 identity checks."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable


SOURCE_PROJECTION_FIELDS = (
    "task_id",
    "sector",
    "occupation",
    "prompt",
    "rubric_pretty",
    "rubric_json",
    "reference_files",
    "reference_file_urls",
    "reference_file_hf_uris",
)


def _required_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"source task {field} must be a nonempty string")
    return value


def _required_string_list(value: object, field: str) -> list[str]:
    if hasattr(value, "tolist"):
        value = value.tolist()
    if value is None:
        value = []
    if isinstance(value, (str, bytes)):
        raise ValueError(f"source task {field} must be a list of strings")
    try:
        items = list(value)
    except TypeError as exc:
        raise ValueError(
            f"source task {field} must be a list of strings"
        ) from exc
    if any(not isinstance(item, str) or not item for item in items):
        raise ValueError(
            f"source task {field} must contain nonempty strings"
        )
    return items


def source_task_projection(
    *,
    task_id: object,
    sector: object,
    occupation: object,
    prompt: object,
    rubric_pretty: object,
    rubric_json: object,
    reference_files: object,
    reference_file_urls: object,
    reference_file_hf_uris: object,
) -> dict[str, object]:
    """Return the exact immutable subset consumed by preparation/evaluation."""
    return {
        "task_id": _required_text(task_id, "task_id"),
        "sector": _required_text(sector, "sector"),
        "occupation": _required_text(occupation, "occupation"),
        "prompt": _required_text(prompt, "prompt"),
        "rubric_pretty": _required_text(rubric_pretty, "rubric_pretty"),
        "rubric_json": _required_text(rubric_json, "rubric_json"),
        "reference_files": _required_string_list(
            reference_files, "reference_files"
        ),
        "reference_file_urls": _required_string_list(
            reference_file_urls, "reference_file_urls"
        ),
        "reference_file_hf_uris": _required_string_list(
            reference_file_hf_uris, "reference_file_hf_uris"
        ),
    }


def source_task_projection_sha256(**values: object) -> str:
    encoded = json.dumps(
        source_task_projection(**values),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def ordered_source_projection_sha256(task_hashes: Iterable[str]) -> str:
    hashes = list(task_hashes)
    if any(
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
        for value in hashes
    ):
        raise ValueError("source task projection hash is invalid")
    encoded = json.dumps(hashes, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()