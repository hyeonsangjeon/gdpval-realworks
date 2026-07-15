"""Strict JSON output tests for Step 3 formatting."""

import json
import math

import pytest

from step3_format_results import _write_json_outputs


def test_write_json_outputs_rejects_nan_before_opening_destinations(tmp_path):
    result_path = tmp_path / "results" / "result.json"
    workspace_path = tmp_path / "workspace" / "result.json"

    with pytest.raises(ValueError, match="Out of range float values"):
        _write_json_outputs(
            {"observability": {"execution_metrics": {"task_wall_time_ms": math.nan}}},
            result_path,
            workspace_path,
        )

    assert not result_path.exists()
    assert not workspace_path.exists()


def test_write_json_outputs_writes_identical_standard_json(tmp_path):
    result_path = tmp_path / "results" / "result.json"
    workspace_path = tmp_path / "workspace" / "result.json"
    payload = {
        "observability": {
            "execution_metrics": {
                "schema_version": "1.0",
                "task_wall_time_ms": 123.45,
            }
        }
    }

    _write_json_outputs(payload, result_path, workspace_path)

    assert result_path.read_bytes() == workspace_path.read_bytes()
    assert json.loads(result_path.read_text(encoding="utf-8")) == payload
