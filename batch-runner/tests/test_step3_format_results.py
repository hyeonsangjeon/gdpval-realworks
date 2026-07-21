"""Strict JSON output tests for Step 3 formatting."""

import json
import math

import pytest

from core.prepared_fingerprint import prepared_fingerprint
from step3_format_results import (
    _source_repo_id,
    _validate_input_identity,
    _write_json_outputs,
)


def test_source_repo_id_is_carried_from_prepared_tasks():
    assert _source_repo_id({"source": "student/exp998"}) == "student/exp998"


@pytest.mark.parametrize(
    "value",
    [None, "", "owner", "owner/repo/extra", "owner/foo..bar", "owner/repo.git"],
)
def test_source_repo_id_rejects_invalid_values(value):
    with pytest.raises(ValueError, match="source repository"):
        _source_repo_id({"source": value})


def _prepared_identity() -> dict:
    payload = {
        "experiment_id": "exp998",
        "source": "student/exp998",
        "task_scope": {"task_ids": ["task-a", "task-b"]},
        "tasks": [{"task_id": "task-a"}, {"task_id": "task-b"}],
    }
    payload["prepared_fingerprint"] = prepared_fingerprint(payload)
    return payload


def _inference_identity() -> dict:
    prepared = _prepared_identity()
    return {
        "experiment_id": "exp998",
        "source": "student/exp998",
        "prepared_fingerprint": prepared["prepared_fingerprint"],
        "ordered_task_ids": ["task-a", "task-b"],
        "results": [{"task_id": "task-a"}, {"task_id": "task-b"}],
    }


def test_input_identity_accepts_exact_step1_step2_match():
    _validate_input_identity(_prepared_identity(), _inference_identity())


@pytest.mark.parametrize(
    ("target", "field", "value", "message"),
    [
        ("prepared", "experiment_id", "other", "experiment"),
        ("prepared", "source", "other/repo", "source repository"),
        ("prepared", "experiment_id", "../outside", "experiment"),
        ("inference", "experiment_id", "../outside", "experiment"),
        ("inference", "ordered_task_ids", ["task-b", "task-a"], "task order"),
        ("inference", "results", [{"task_id": "task-a"}], "result task"),
        ("inference", "prepared_fingerprint", "b" * 64, "fingerprint"),
    ],
)
def test_input_identity_rejects_mixed_workspace(target, field, value, message):
    prepared = _prepared_identity()
    inference = _inference_identity()
    (prepared if target == "prepared" else inference)[field] = value

    with pytest.raises(ValueError, match=message):
        _validate_input_identity(prepared, inference)


def test_input_identity_rejects_mutated_prepared_payload_with_stale_fingerprint():
    prepared = _prepared_identity()
    inference = _inference_identity()
    prepared["tasks"][0]["instruction"] = "mutated prompt"

    with pytest.raises(ValueError, match="fingerprint does not match payload"):
        _validate_input_identity(prepared, inference)


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
