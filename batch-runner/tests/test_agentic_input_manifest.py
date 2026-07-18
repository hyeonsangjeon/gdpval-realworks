"""Tests for exact approved input identities built on compute storage."""

from __future__ import annotations

import json
import os

import pytest

from core.agentic_input_manifest import build_input_manifest


def _selection(dataset_root):
    selected = []
    for index in range(25):
        relative = f"task-{index:02d}/input.txt"
        path = dataset_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"input-{index}", encoding="utf-8")
        selected.append({
            "task_id": f"task-{index:02d}",
            "reference_paths": [relative],
            "reference_sizes": [path.stat().st_size],
        })
    return {"selected_tasks": selected}


def test_build_input_manifest_is_deterministic_and_complete(tmp_path):
    dataset = tmp_path / "dataset"
    staging = tmp_path / "staging"
    dataset.mkdir()
    staging.mkdir()
    selection = _selection(dataset)

    first = build_input_manifest(
        selection_manifest=selection,
        dataset_root=dataset,
        staging_parent=staging,
        provider_classification="approved_public_gdpval",
    )
    second = build_input_manifest(
        selection_manifest=selection,
        dataset_root=dataset,
        staging_parent=staging,
        provider_classification="approved_public_gdpval",
    )

    assert first == second
    assert first["schema_version"] == "agentic-input-manifest-v1"
    assert first["staging_filesystem_device"] == staging.stat().st_dev
    assert len(first["tasks"]) == 25
    assert len(first["sha256"]) == 64
    task = first["tasks"]["task-00"]
    assert task["reference_ids"] == ["task-00/input.txt"]
    assert len(task["input_merkle_root"]) == 64
    record = task["files"][0]
    assert record["source_path"] == "task-00/input.txt"
    assert record["relative_path"] == "task-00/input.txt"
    assert record["staged_allocated_bytes"] > 0
    assert len(record["sha256"]) == 64
    assert not any(staging.iterdir())
    json.dumps(first, allow_nan=False)


def test_build_input_manifest_rejects_selection_size_drift(tmp_path):
    dataset = tmp_path / "dataset"
    staging = tmp_path / "staging"
    dataset.mkdir()
    staging.mkdir()
    selection = _selection(dataset)
    selection["selected_tasks"][0]["reference_sizes"][0] += 1

    with pytest.raises(ValueError, match="size differs"):
        build_input_manifest(
            selection_manifest=selection,
            dataset_root=dataset,
            staging_parent=staging,
            provider_classification="approved_public_gdpval",
        )


@pytest.mark.parametrize("link_kind", ["file", "ancestor"])
def test_build_input_manifest_rejects_symlink_components(tmp_path, link_kind):
    dataset = tmp_path / "dataset"
    staging = tmp_path / "staging"
    dataset.mkdir()
    staging.mkdir()
    selection = _selection(dataset)
    source = dataset / "task-00" / "input.txt"

    if link_kind == "file":
        target = dataset / "target.txt"
        target.write_bytes(source.read_bytes())
        source.unlink()
        source.symlink_to(target)
    else:
        original_parent = source.parent
        target_parent = dataset / "target-parent"
        original_parent.rename(target_parent)
        original_parent.symlink_to(target_parent, target_is_directory=True)

    with pytest.raises(ValueError, match="contains a link"):
        build_input_manifest(
            selection_manifest=selection,
            dataset_root=dataset,
            staging_parent=staging,
            provider_classification="approved_public_gdpval",
        )


def test_build_input_manifest_rejects_fifo_without_blocking(tmp_path):
    dataset = tmp_path / "dataset"
    staging = tmp_path / "staging"
    dataset.mkdir()
    staging.mkdir()
    selection = _selection(dataset)
    source = dataset / "task-00" / "input.txt"
    source.unlink()
    os.mkfifo(source)

    with pytest.raises(ValueError, match="single-link regular file"):
        build_input_manifest(
            selection_manifest=selection,
            dataset_root=dataset,
            staging_parent=staging,
            provider_classification="approved_public_gdpval",
        )