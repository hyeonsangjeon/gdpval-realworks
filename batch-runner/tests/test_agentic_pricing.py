"""Tests for immutable agentic model pricing tables."""

import hashlib
import json

import pytest

from core.agentic_pricing import load_pinned_model_pricing


def _table(tmp_path):
    path = tmp_path / "pricing.json"
    path.write_text(json.dumps({
        "schema_version": "agentic-pricing-v1",
        "models": {
            "azure:deployment": {
                "input_per_million": "1.25",
                "output_per_million": "10.00",
                "cached_input_per_million": "0.125",
                "currency": "USD",
            }
        },
    }, sort_keys=True), encoding="utf-8")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return path, digest


def test_loads_only_exact_hash_and_model(tmp_path):
    path, digest = _table(tmp_path)

    result = load_pinned_model_pricing(
        path=path,
        expected_sha256=digest,
        provider="azure",
        model="deployment",
    )

    assert result == {
        "input_per_million": "1.25",
        "output_per_million": "10.00",
        "cached_input_per_million": "0.125",
        "price_table_sha256": digest,
    }


def test_rejects_hash_drift_and_unknown_model(tmp_path):
    path, digest = _table(tmp_path)
    with pytest.raises(ValueError, match="hash mismatch"):
        load_pinned_model_pricing(
            path=path,
            expected_sha256="0" * 64,
            provider="azure",
            model="deployment",
        )
    with pytest.raises(ValueError, match="no pinned price entry"):
        load_pinned_model_pricing(
            path=path,
            expected_sha256=digest,
            provider="openai",
            model="deployment",
        )