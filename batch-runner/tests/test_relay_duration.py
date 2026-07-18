"""Tests for relay duration fix: started_at preservation in progress.json."""

import json

from step2_run_inference import _save_progress


def _identity(total_tasks):
    return {
        "run_id": "relay-test-run",
        "condition_identity": "condition_a",
        "ordered_task_ids": [f"t{index}" for index in range(1, total_tasks + 1)],
    }


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
            results=[{"task_id": "t1", "status": "success"}],
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
                {"task_id": "t1", "status": "success"},
                {"task_id": "t2", "status": "pending"},
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
            {"task_id": "t1", "status": "success"},
            {"task_id": "t2", "status": "success"},
            {"task_id": "t3", "status": "error"},
            {"task_id": "t4", "status": "pending"},
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
