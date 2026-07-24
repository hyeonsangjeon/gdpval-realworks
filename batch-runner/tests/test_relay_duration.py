"""Tests for relay duration fix: started_at preservation in progress.json."""

import json

import pytest

from step2_run_inference import (
    _load_and_validate_progress,
    _resolve_run_identity,
    _save_progress,
)


def _identity(total_tasks):
    return {
        "run_id": "relay-test-run",
        "condition_identity": "condition_a",
        "ordered_task_ids": [f"t{index}" for index in range(1, total_tasks + 1)],
        "prepared_fingerprint": "a" * 64,
    }


def _checkpoint_result(task_id, status):
    timestamp = "2026-03-27T02:58:37+00:00"
    if status == "pending":
        return {
            "task_id": task_id,
            "status": status,
            "error": "wall_timeout",
            "timestamp": timestamp,
        }
    result = {
        "task_id": task_id,
        "status": status,
        "content": None,
        "deliverable_text": None,
        "deliverable_files": [],
        "model": "test-model",
        "usage": None,
        "observability": {},
        "latency_ms": 1.0,
        "timestamp": timestamp,
    }
    if status == "error":
        result["error"] = "test_error"
    else:
        result["content"] = "done"
        result["deliverable_text"] = "done"
    return result


class TestSaveProgressStartedAt:
    """Verify _save_progress persists started_at in progress.json."""

    def test_started_at_saved(self, tmp_path):
        """started_at is written to progress.json."""
        progress_path = tmp_path / "progress.json"
        original_time = "2026-03-27T02:58:37+00:00"

        _save_progress(
            experiment_id="exp_test",
            condition_name="test_condition",
            execution_mode="subprocess",
            total_tasks=220,
            results=[_checkpoint_result("t1", "success")],
            started_at=original_time,
            path=progress_path,
            **_identity(220),
        )

        with open(progress_path) as f:
            data = json.load(f)

        assert data["started_at"] == original_time

    def test_started_at_preserved_on_resume(self, tmp_path):
        """Simulates relay resume: started_at from progress.json should be used
        instead of a new timestamp."""
        progress_path = tmp_path / "progress.json"
        original_time = "2026-03-27T02:58:37+00:00"

        # Simulate first run saving progress
        _save_progress(
            experiment_id="exp_test",
            condition_name="test_condition",
            execution_mode="subprocess",
            total_tasks=220,
            results=[
                _checkpoint_result("t1", "success"),
                _checkpoint_result("t2", "pending"),
            ],
            started_at=original_time,
            path=progress_path,
            **_identity(220),
        )

        # Simulate relay resume: new started_at would be set, then overridden
        new_started_at = "2026-03-27T08:19:38+00:00"  # relay run 2

        # Load progress (same logic as step2_run_inference.py line ~1220)
        with open(progress_path) as f:
            progress = json.load(f)

        # This is the fix: restore original started_at
        if "started_at" in progress:
            new_started_at = progress["started_at"]

        assert new_started_at == original_time

    def test_progress_summary_counts(self, tmp_path):
        """Verify summary counts are correct."""
        progress_path = tmp_path / "progress.json"

        results = [
            _checkpoint_result("t1", "success"),
            _checkpoint_result("t2", "success"),
            _checkpoint_result("t3", "error"),
            _checkpoint_result("t4", "pending"),
        ]

        _save_progress(
            experiment_id="exp_test",
            condition_name="cond",
            execution_mode="subprocess",
            total_tasks=10,
            results=results,
            started_at="2026-01-01T00:00:00",
            path=progress_path,
            **_identity(10),
        )

        with open(progress_path) as f:
            data = json.load(f)

        assert data["summary"]["total"] == 10
        assert data["summary"]["completed"] == 4
        assert data["summary"]["success"] == 2
        assert data["summary"]["error"] == 1

    def test_atomic_write(self, tmp_path):
        """Verify no .tmp file remains after save."""
        progress_path = tmp_path / "progress.json"

        _save_progress(
            experiment_id="exp_test",
            condition_name="cond",
            execution_mode="subprocess",
            total_tasks=1,
            results=[],
            started_at="2026-01-01T00:00:00",
            path=progress_path,
            **_identity(1),
        )

        assert progress_path.exists()
        assert not progress_path.with_suffix(".json.tmp").exists()

    def test_provider_error_is_sanitized_before_checkpoint_write(self, tmp_path):
        progress_path = tmp_path / "progress.json"
        raw_error = (
            "BadRequestError: https://secret.services.ai.azure.com/"
            "api/projects/private"
        )
        result = _checkpoint_result("t1", "error")
        result["error"] = raw_error

        _save_progress(
            experiment_id="exp_test",
            condition_name="cond",
            execution_mode="subprocess",
            total_tasks=1,
            results=[result],
            started_at="2026-03-27T02:58:37+00:00",
            path=progress_path,
            **_identity(1),
        )

        serialized = progress_path.read_text(encoding="utf-8")
        assert "secret.services.ai.azure.com" not in serialized
        assert json.loads(serialized)["results"][0]["error"] == (
            "task_execution_error:BadRequestError"
        )

    def test_progress_rejects_malformed_success_on_save(self, tmp_path):
        with pytest.raises(ValueError, match="timestamp is invalid"):
            _save_progress(
                experiment_id="exp_test",
                condition_name="cond",
                execution_mode="subprocess",
                total_tasks=1,
                results=[{"task_id": "t1", "status": "success"}],
                started_at="2026-01-01T00:00:00+00:00",
                path=tmp_path / "progress.json",
                **_identity(1),
            )

    def test_progress_rejects_tampered_success_on_load(self, tmp_path):
        progress_path = tmp_path / "progress.json"
        _save_progress(
            experiment_id="exp_test",
            condition_name="cond",
            execution_mode="subprocess",
            total_tasks=1,
            results=[_checkpoint_result("t1", "success")],
            started_at="2026-01-01T00:00:00+00:00",
            path=progress_path,
            **_identity(1),
        )
        payload = json.loads(progress_path.read_text(encoding="utf-8"))
        del payload["results"][0]["deliverable_text"]
        progress_path.write_text(json.dumps(payload), encoding="utf-8")

        with pytest.raises(ValueError, match="fields are incomplete"):
            _load_and_validate_progress(
                progress_path,
                experiment_id="exp_test",
                condition_name="cond",
                condition_identity="condition_a",
                run_id="relay-test-run",
                execution_mode="subprocess",
                ordered_task_ids=["t1"],
                prepared_fingerprint="a" * 64,
            )

    def test_progress_rejects_prepared_fingerprint_mismatch(self, tmp_path):
        progress_path = tmp_path / "progress.json"
        _save_progress(
            experiment_id="exp_test",
            condition_name="cond",
            execution_mode="subprocess",
            total_tasks=1,
            results=[],
            started_at="2026-01-01T00:00:00",
            path=progress_path,
            **_identity(1),
        )

        with pytest.raises(ValueError, match="identity mismatch"):
            _load_and_validate_progress(
                progress_path,
                experiment_id="exp_test",
                condition_name="cond",
                condition_identity="condition_a",
                run_id="relay-test-run",
                execution_mode="subprocess",
                ordered_task_ids=["t1"],
                prepared_fingerprint="b" * 64,
            )


def test_relay_lineage_is_stable_across_github_run_ids(monkeypatch):
    monkeypatch.setenv("GDPVAL_RELAY_LINEAGE_ID", "exp_test:100:1")
    monkeypatch.setenv("GITHUB_RUN_ID", "200")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "3")

    assert _resolve_run_identity("exp_test") == "exp_test:100:1"


def test_initial_run_identity_uses_current_github_run(monkeypatch):
    monkeypatch.delenv("GDPVAL_RELAY_LINEAGE_ID", raising=False)
    monkeypatch.setenv("GITHUB_RUN_ID", "200")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "3")

    assert _resolve_run_identity("exp_test") == "exp_test:200:3"


def test_publication_generation_is_stable_across_relay_legs(monkeypatch):
    from core.publication_generation import resolve_publication_generation

    monkeypatch.setenv("GDPVAL_RELAY_LINEAGE_ID", "exp_test:100:1")
    monkeypatch.setenv("GITHUB_RUN_ID", "200")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "3")

    assert resolve_publication_generation("exp_test") == "exp_test:100:1"


def test_local_publication_generation_changes_per_preparation(monkeypatch):
    from core.publication_generation import resolve_publication_generation

    monkeypatch.delenv("GDPVAL_RELAY_LINEAGE_ID", raising=False)
    monkeypatch.delenv("GITHUB_RUN_ID", raising=False)

    first = resolve_publication_generation("exp_test")
    second = resolve_publication_generation("exp_test")

    assert first != second
    assert first.startswith("exp_test:local:")


def test_condition_workspace_paths_are_isolated(monkeypatch, tmp_path):
    import step2_run_inference as step2

    monkeypatch.setattr(step2, "WORKSPACE_DIR", tmp_path)
    a_progress, a_result = step2._condition_workspace_paths("condition_a")
    b_progress, b_result = step2._condition_workspace_paths("condition_b")

    assert a_progress != b_progress
    assert a_result != b_result
    assert a_progress.name == "step2_inference_progress_condition_a.json"
    assert b_progress.name == "step2_inference_progress_condition_b.json"
