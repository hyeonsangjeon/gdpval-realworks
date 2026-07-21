"""Canonical identity for the prepared Step 1 payload."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

FINGERPRINT_RE = re.compile(r"[0-9a-f]{64}")


def prepared_fingerprint(payload: dict[str, Any]) -> str:
    """Hash the public prepared payload, excluding path and fingerprint fields."""
    if not isinstance(payload, dict):
        raise ValueError("prepared payload must be an object")
    canonical = {
        key: value
        for key, value in payload.items()
        if key not in {"config_path", "prepared_fingerprint"}
    }
    serialized = json.dumps(
        canonical,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def validate_prepared_fingerprint(payload: dict[str, Any]) -> str:
    """Return the fingerprint only when it matches the current payload bytes."""
    claimed = payload.get("prepared_fingerprint")
    if not isinstance(claimed, str) or not FINGERPRINT_RE.fullmatch(claimed):
        raise ValueError("prepared task fingerprint is missing or invalid")
    actual = prepared_fingerprint(payload)
    if claimed != actual:
        raise ValueError("prepared task fingerprint does not match payload")
    return claimed
