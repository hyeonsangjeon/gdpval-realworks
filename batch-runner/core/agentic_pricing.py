"""Immutable model pricing table loader for conservative reservations."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping


def load_pinned_model_pricing(
    *,
    path: str | Path,
    expected_sha256: str,
    provider: str,
    model: str,
) -> dict:
    price_path = Path(path)
    if not price_path.is_file():
        raise ValueError("agentic price table is missing")
    raw = price_path.read_bytes()
    actual_sha256 = hashlib.sha256(raw).hexdigest()
    if actual_sha256 != expected_sha256:
        raise ValueError("agentic price table hash mismatch")
    try:
        document = json.loads(raw)
    except Exception as exc:
        raise ValueError("agentic price table is invalid JSON") from exc
    if not isinstance(document, Mapping) or set(document) != {
        "schema_version", "models"
    }:
        raise ValueError("agentic price table fields are invalid")
    if document["schema_version"] != "agentic-pricing-v1":
        raise ValueError("unsupported agentic price table version")
    models = document["models"]
    key = f"{provider}:{model}"
    if not isinstance(models, Mapping) or key not in models:
        raise ValueError("agentic model has no pinned price entry")
    entry = models[key]
    required = {
        "input_per_million", "output_per_million",
        "cached_input_per_million", "currency",
    }
    if not isinstance(entry, Mapping) or set(entry) != required:
        raise ValueError("agentic model price fields are invalid")
    if entry["currency"] != "USD":
        raise ValueError("agentic price table currency must be USD")
    output = {"price_table_sha256": actual_sha256}
    for field in (
        "input_per_million", "output_per_million", "cached_input_per_million"
    ):
        value = _decimal(entry[field])
        output[field] = str(value)
    return output


def _decimal(value: Any) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("agentic price must be a finite non-negative decimal") from exc
    if not parsed.is_finite() or parsed < 0:
        raise ValueError("agentic price must be a finite non-negative decimal")
    return parsed