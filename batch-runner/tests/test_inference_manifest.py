"""Security tests for inference manifest and local deliverable confinement."""

from __future__ import annotations

import hashlib
import os

import pytest

from core.inference_manifest import (
    bind_deliverable_file_records,
    build_inference_provenance,
    canonical_deliverable_path,
    canonicalize_inference_payload,
    ensure_task_deliverable_dir,
    reset_task_deliverable_dir,
    validate_inference_provenance,
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


def test_final_result_binds_declared_deliverable_bytes(tmp_path):
    content = b"current-result-bytes"
    deliverable = tmp_path / "deliverable_files/task-1/out.txt"
    deliverable.parent.mkdir(parents=True)
    deliverable.write_bytes(content)

    bound = bind_deliverable_file_records([_row()], tmp_path)

    assert bound[0]["deliverable_file_records"] == [{
        "path": "deliverable_files/task-1/out.txt",
        "sha256": hashlib.sha256(content).hexdigest(),
        "size": len(content),
    }]


def test_final_result_rejects_hardlinked_deliverable(tmp_path):
    deliverable = tmp_path / "deliverable_files/task-1/out.txt"
    deliverable.parent.mkdir(parents=True)
    deliverable.write_bytes(b"shared")
    os.link(deliverable, tmp_path / "second-link.txt")

    with pytest.raises(ValueError, match="single-link regular file"):
        bind_deliverable_file_records([_row()], tmp_path)


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


def test_reset_task_deliverable_dir_replaces_only_owned_task(tmp_path):
    upload_root = tmp_path / "upload"
    target = ensure_task_deliverable_dir(upload_root, "task-1")
    (target / "stale.txt").write_text("stale", encoding="utf-8")
    sibling = ensure_task_deliverable_dir(upload_root, "task-2")
    sentinel = sibling / "keep.txt"
    sentinel.write_text("keep", encoding="utf-8")

    reset = reset_task_deliverable_dir(upload_root, "task-1")

    assert reset == target
    assert list(reset.iterdir()) == []
    assert sentinel.read_text(encoding="utf-8") == "keep"


@pytest.mark.parametrize("kind", ["task_symlink", "task_file", "root_symlink"])
def test_reset_task_deliverable_dir_rejects_non_regular_boundaries(tmp_path, kind):
    upload_root = tmp_path / "upload"
    deliverable_root = upload_root / "deliverable_files"
    deliverable_root.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    if kind == "root_symlink":
        deliverable_root.rmdir()
        deliverable_root.symlink_to(outside, target_is_directory=True)
    elif kind == "task_symlink":
        (deliverable_root / "task-1").symlink_to(outside, target_is_directory=True)
    else:
        (deliverable_root / "task-1").write_text(
            "not a directory", encoding="utf-8"
        )

    with pytest.raises(ValueError, match="not a regular directory"):
        reset_task_deliverable_dir(upload_root, "task-1")


def test_reset_task_deliverable_dir_propagates_delete_failure(tmp_path, monkeypatch):
    import core.inference_manifest as manifest

    upload_root = tmp_path / "upload"
    ensure_task_deliverable_dir(upload_root, "task-1")

    def fail_delete(_path):
        raise OSError("delete failed")

    monkeypatch.setattr(manifest.shutil, "rmtree", fail_delete)

    with pytest.raises(OSError, match="delete failed"):
        reset_task_deliverable_dir(upload_root, "task-1")


def test_inference_provenance_round_trip_binds_routes_and_task_order():
    route = {
        "endpoint_kind": "direct-v1",
        "profile": "direct-v1",
        "runtime_fingerprint": "f" * 64,
        "workload": "inference",
    }
    source = {
        "experiment_id": "exp",
        "source_repo_id": "owner/repo",
        "prepared_fingerprint": "e" * 64,
        "execution_mode": "subprocess",
        "azure_ai_routes": [route],
        "results": [
            {"task_id": "task-1", "deliverable_files": []},
            {"task_id": "task-2", "deliverable_files": []},
        ],
    }

    sidecar = build_inference_provenance(source)
    verified = validate_inference_provenance(
        sidecar,
        experiment_id="exp",
        source_repo_id="owner/repo",
        task_ids=["task-1", "task-2"],
        prepared_fingerprint="e" * 64,
        azure_ai_routes=[route],
    )

    assert verified["azure_ai_routes"] == [route]


@pytest.mark.parametrize("mutation", ["task_order", "route", "extra_field"])
def test_inference_provenance_rejects_drift(mutation):
    source = {
        "experiment_id": "exp",
        "source_repo_id": "owner/repo",
        "prepared_fingerprint": "e" * 64,
        "execution_mode": "subprocess",
        "azure_ai_routes": [{
            "endpoint_kind": "direct-v1",
            "profile": "direct-v1",
            "runtime_fingerprint": "f" * 64,
            "workload": "inference",
        }],
        "results": [
            {"task_id": "task-1", "deliverable_files": []},
            {"task_id": "task-2", "deliverable_files": []},
        ],
    }
    sidecar = build_inference_provenance(source)
    task_ids = ["task-1", "task-2"]
    if mutation == "task_order":
        task_ids.reverse()
    elif mutation == "route":
        sidecar["azure_ai_routes"][0]["runtime_fingerprint"] = "invalid"
    else:
        sidecar["unexpected"] = True

    with pytest.raises(ValueError):
        validate_inference_provenance(
            sidecar,
            experiment_id="exp",
            source_repo_id="owner/repo",
            task_ids=task_ids,
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("prepared_fingerprint", "d" * 64, "prepared fingerprint mismatch"),
        (
            "azure_ai_routes",
            [{
                "endpoint_kind": "direct-v1",
                "profile": "direct-v1",
                "runtime_fingerprint": "d" * 64,
                "workload": "inference",
            }],
            "Azure AI routes mismatch",
        ),
    ],
)
def test_inference_provenance_rejects_valid_wrong_identity(
    field, value, message
):
    route = {
        "endpoint_kind": "direct-v1",
        "profile": "direct-v1",
        "runtime_fingerprint": "f" * 64,
        "workload": "inference",
    }
    source = {
        "experiment_id": "exp",
        "source_repo_id": "owner/repo",
        "prepared_fingerprint": "e" * 64,
        "execution_mode": "subprocess",
        "azure_ai_routes": [route],
        "results": [{"task_id": "task-1", "deliverable_files": []}],
    }

    with pytest.raises(ValueError, match=message):
        validate_inference_provenance(
            build_inference_provenance(source),
            experiment_id="exp",
            source_repo_id="owner/repo",
            task_ids=["task-1"],
            prepared_fingerprint=(
                value if field == "prepared_fingerprint" else "e" * 64
            ),
            azure_ai_routes=(value if field == "azure_ai_routes" else [route]),
        )


@pytest.mark.parametrize(
    ("profile", "endpoint_kind", "workload"),
    [
        ("direct-v1", "project", "inference"),
        ("direct-v1", "direct-v1", "code-interpreter"),
        ("project-ci", "direct-v1", "code-interpreter"),
        ("project-ci", "project", "grader"),
        ("legacy-rollback", "direct-v1", "grader"),
        ("legacy-rollback", "legacy-dated", "code-interpreter"),
    ],
)
def test_inference_provenance_rejects_impossible_route_combinations(
    profile, endpoint_kind, workload
):
    source = {
        "experiment_id": "exp",
        "source_repo_id": "owner/repo",
        "prepared_fingerprint": "e" * 64,
        "execution_mode": "subprocess",
        "azure_ai_routes": [{
            "endpoint_kind": endpoint_kind,
            "profile": profile,
            "runtime_fingerprint": "f" * 64,
            "workload": workload,
        }],
        "results": [{"task_id": "task-1", "deliverable_files": []}],
    }

    with pytest.raises(ValueError, match="profile, endpoint, and workload"):
        build_inference_provenance(source)


def test_code_interpreter_provenance_requires_project_route_and_binds_mode():
    source = {
        "experiment_id": "exp",
        "source_repo_id": "owner/repo",
        "prepared_fingerprint": "e" * 64,
        "execution_mode": "code_interpreter",
        "azure_ai_routes": [],
        "results": [{"task_id": "task-1", "deliverable_files": []}],
    }

    with pytest.raises(ValueError, match="requires one project-ci route"):
        build_inference_provenance(source)

    source["azure_ai_routes"] = [
        {
            "endpoint_kind": "direct-v1",
            "profile": "project-ci",
            "runtime_fingerprint": "a" * 64,
            "workload": "inference",
        },
        {
            "endpoint_kind": "project",
            "profile": "project-ci",
            "runtime_fingerprint": "b" * 64,
            "workload": "code-interpreter",
        },
    ]
    sidecar = build_inference_provenance(source)

    assert sidecar["execution_mode"] == "code_interpreter"
    assert validate_inference_provenance(
        sidecar,
        experiment_id="exp",
        source_repo_id="owner/repo",
        task_ids=["task-1"],
        execution_mode="code_interpreter",
    )["azure_ai_routes"] == source["azure_ai_routes"]
