"""Tests for exact approved input identities built on compute storage."""

from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path

import pytest

from core.agentic_input_manifest import build_input_manifest
from core.agentic_compute import _open_regular_beneath_nofollow


def _selection(dataset_root):
    selected = []
    for index in range(25):
        relative = f"task-{index:02d}/input.txt"
        path = dataset_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"input-{index}", encoding="utf-8")
        selected.append({
            "task_id": f"task-{index:02d}",
            "sector": "Test",
            "occupation": "Analyst",
            "input_class": "document",
            "reference_paths": [relative],
            "reference_suffixes": ["txt"],
            "reference_sizes": [path.stat().st_size],
            "positive_rubric_max": 1,
        })
    task_ids = [task["task_id"] for task in selected]
    document = {
        "schema_version": "agentic-task-subset-v1",
        "seed": "20260717",
        "eligible_frame_count": 25,
        "strata": [{
            "sector": "Test",
            "input_class": "document",
            "eligible_count": 25,
            "selected_quota": 25,
            "canary_quota": 5,
        }],
        "canary_task_ids": task_ids[:5],
        "diagnostic_task_ids": task_ids[5:],
        "selected_tasks": selected,
        "selection_domains": {
            "select": "agentic-select-v1",
            "canary": "agentic-canary-v1",
            "order_canary": "agentic-order-canary-v1",
            "order_diagnostic": "agentic-order-diagnostic-v1",
        },
        "tie_break": "ascending UTF-8 bytes",
        "selected_before_outcomes": True,
        "dataset": {
            "repository": "owner/dataset",
            "revision": "a" * 40,
            "source_path": "dataset.json",
            "sha256": "b" * 64,
        },
        "rubric": {
            "repository": "owner/rubric",
            "revision": "c" * 40,
            "source_path": "rubric.json",
            "sha256": "d" * 64,
        },
        "selector": {
            "path": "core/agentic_selector.py",
            "source_commit": "e" * 40,
            "sha256": "f" * 64,
        },
        "inclusion_validation": "all structural checks passed",
        "exclusion_validation": (
            "outcome fields were not accepted by selector"
        ),
    }
    _rehash_selection(document)
    return document


def _rehash_selection(document):
    canonical = {
        key: value
        for key, value in document.items()
        if key != "recomputation_sha256"
    }
    document["recomputation_sha256"] = hashlib.sha256(
        json.dumps(
            canonical, sort_keys=True, separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


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
    assert first["selection_recomputation_sha256"] == selection[
        "recomputation_sha256"
    ]
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
    _rehash_selection(selection)

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


@pytest.mark.parametrize("task_id", ["../escaped", "/absolute", ".hidden", "a/b"])
def test_build_input_manifest_rejects_task_id_path_components(
    tmp_path, task_id
):
    dataset = tmp_path / "dataset"
    staging = tmp_path / "staging"
    dataset.mkdir()
    staging.mkdir()
    selection = _selection(dataset)
    selection["selected_tasks"][0]["task_id"] = task_id
    selection["canary_task_ids"][0] = task_id
    _rehash_selection(selection)

    with pytest.raises(ValueError, match="canonical component"):
        build_input_manifest(
            selection_manifest=selection,
            dataset_root=dataset,
            staging_parent=staging,
            provider_classification="approved_public_gdpval",
        )

    assert not (tmp_path / "escaped").exists()


def test_build_input_manifest_rejects_stale_selection_hash_before_staging(
    tmp_path
):
    dataset = tmp_path / "dataset"
    staging = tmp_path / "staging"
    dataset.mkdir()
    staging.mkdir()
    selection = _selection(dataset)
    selection["selected_tasks"][0]["reference_paths"][0] = (
        "task-01/input.txt"
    )

    with pytest.raises(ValueError, match="recomputation hash mismatch"):
        build_input_manifest(
            selection_manifest=selection,
            dataset_root=dataset,
            staging_parent=staging,
            provider_classification="approved_public_gdpval",
        )

    assert not any(staging.iterdir())


def test_build_input_manifest_rejects_5_20_order_drift(tmp_path):
    dataset = tmp_path / "dataset"
    staging = tmp_path / "staging"
    dataset.mkdir()
    staging.mkdir()
    selection = _selection(dataset)
    selection["canary_task_ids"][0], selection["canary_task_ids"][1] = (
        selection["canary_task_ids"][1],
        selection["canary_task_ids"][0],
    )
    _rehash_selection(selection)

    with pytest.raises(ValueError, match="task order differs"):
        build_input_manifest(
            selection_manifest=selection,
            dataset_root=dataset,
            staging_parent=staging,
            provider_classification="approved_public_gdpval",
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("repository", "https://example.test/dataset"),
        ("revision", "main"),
        ("source_path", "../dataset.json"),
        ("sha256", "not-a-sha256"),
    ],
)
def test_build_input_manifest_rejects_invalid_dataset_provenance(
    tmp_path, field, value
):
    dataset = tmp_path / "dataset"
    staging = tmp_path / "staging"
    dataset.mkdir()
    staging.mkdir()
    selection = _selection(dataset)
    selection["dataset"][field] = value
    _rehash_selection(selection)

    with pytest.raises(ValueError, match="dataset provenance"):
        build_input_manifest(
            selection_manifest=selection,
            dataset_root=dataset,
            staging_parent=staging,
            provider_classification="approved_public_gdpval",
        )


def test_approved_input_open_rejects_nested_mount_identity(
    tmp_path, monkeypatch
):
    root = tmp_path / "dataset"
    nested = root / "nested"
    nested.mkdir(parents=True)
    (nested / "input.txt").write_text("input", encoding="utf-8")
    mount_ids = iter([100, 200])
    monkeypatch.setattr(
        "core.agentic_compute._descriptor_mount_id",
        lambda descriptor: next(mount_ids),
    )

    with pytest.raises(OSError, match="mount boundary"):
        _open_regular_beneath_nofollow(
            root, Path("nested/input.txt")
        )