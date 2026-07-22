"""Canonical identity for one completed Step 2 inference payload."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any


RESULT_FINGERPRINT_RE = re.compile(r"[0-9a-f]{64}")


def inference_result_fingerprint(payload: dict[str, Any]) -> str:
    if not isinstance(payload, dict):
        raise ValueError("inference result payload must be an object")
    canonical = {
        key: value
        for key, value in payload.items()
        if key != "result_fingerprint"
    }
    serialized = json.dumps(
        canonical,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def validate_inference_result_fingerprint(payload: dict[str, Any]) -> str:
    claimed = payload.get("result_fingerprint")
    if (
        not isinstance(claimed, str)
        or RESULT_FINGERPRINT_RE.fullmatch(claimed) is None
    ):
        raise ValueError("inference result fingerprint is missing or invalid")
    actual = inference_result_fingerprint(payload)
    if claimed != actual:
        raise ValueError("inference result fingerprint does not match payload")
    return claimed