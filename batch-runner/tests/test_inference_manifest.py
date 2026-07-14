"""Security tests for inference manifest and local deliverable confinement."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.inference_manifest import (
    canonical_deliverable_path,
    canonicalize_inference_payload,
    validate_local_deliverables,
)


def _row(path: str = "deliverable_files/task-1/out.txt") -> dict:
    return {"task_id": "task-1", "deliverable_files": [path]}


@pytest.mark.parametrize(
    "path",
    [
        "/tmp/out.txt",
        "../out.txt",
        "C:/out.txt",
        "deliverable_files/other-task/out.txt",
        "deliverable_files/task-1/../out.txt",
        "deliverable_files/task-1//out.txt",
        "deliverable_files\\task-1\\out.txt",
        "deliverable_files/task-1",
    ],
)
def test_deliverable_path_must_be_canonical_and_task_confined(path):
    with pytest.raises(ValueError):
        canonical_deliverable_path("task-1", path)


@pytest.mark.parametrize(
    "payload",
    [
        {"results": [{"task_id": "../task", "deliverable_files": []}]},
        {"results": [_row(), _row()]},
        {"results": [{
            "task_id": "task-1",
            "deliverable_files": [
                "deliverable_files/task-1/out.txt",
                "deliverable_files/task-1/out.txt",
            ],
        }]},
    ],
)
def test_manifest_rejects_unsafe_or_duplicate_identity(payload):
    with pytest.raises(ValueError):
        canonicalize_inference_payload(payload)


def test_local_tree_accepts_exact_regular_manifest_files(tmp_path):
    deliverable = tmp_path / "deliverable_files/task-1/nested/out.txt"
    deliverable.parent.mkdir(parents=True)
    deliverable.write_text("ok", encoding="utf-8")
    rows = [{
        "task_id": "task-1",
        "deliverable_files": ["deliverable_files/task-1/nested/out.txt"],
    }]

    assert validate_local_deliverables(rows, tmp_path) == rows


@pytest.mark.parametrize("mutation", ["missing", "extra", "file_symlink", "dir_symlink"])
def test_local_tree_fails_closed_on_mismatch_or_symlink(tmp_path, mutation):
    task_root = tmp_path / "deliverable_files/task-1"
    task_root.mkdir(parents=True)
    expected = task_root / "out.txt"
    expected.write_text("ok", encoding="utf-8")
    rows = [_row()]

    if mutation == "missing":
        expected.unlink()
    elif mutation == "extra":
        (task_root / "extra.txt").write_text("extra", encoding="utf-8")
    elif mutation == "file_symlink":
        outside = tmp_path / "outside.txt"
        outside.write_text("secret", encoding="utf-8")
        expected.unlink()
        expected.symlink_to(outside)
    else:
        outside_dir = tmp_path / "outside-dir"
        outside_dir.mkdir()
        (outside_dir / "out.txt").write_text("secret", encoding="utf-8")
        expected.unlink()
        task_root.rmdir()
        task_root.symlink_to(outside_dir, target_is_directory=True)

    with pytest.raises(ValueError):
        validate_local_deliverables(rows, tmp_path)


def test_upload_root_ancestor_symlink_is_rejected(tmp_path):
    real_workspace = tmp_path / "real-workspace"
    upload_root = real_workspace / "upload"
    deliverable = upload_root / "deliverable_files/task-1/out.txt"
    deliverable.parent.mkdir(parents=True)
    deliverable.write_text("secret", encoding="utf-8")
    linked_workspace = tmp_path / "workspace"
    linked_workspace.symlink_to(real_workspace, target_is_directory=True)

    with pytest.raises(ValueError, match="symlink component"):
        validate_local_deliverables([_row()], linked_workspace / "upload")