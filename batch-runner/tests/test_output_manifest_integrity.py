import json
import hashlib
from pathlib import Path

import pandas as pd
import pytest

import core.repo_bootstrapper as bootstrapper
from core.repo_bootstrapper import validate_deliverable_tree
from fill_parquet import _build_deliverable_uris, fill_parquet
from step5_validate import _build_dummy_urls


def _source_frame():
    return pd.DataFrame({
        "task_id": ["task-1"],
        "sector": ["sector"],
        "occupation": ["occupation"],
        "prompt": ["prompt"],
        "reference_files": [[]],
        "reference_file_urls": [[]],
        "reference_file_hf_uris": [[]],
        "deliverable_files": [[]],
        "deliverable_file_urls": [[]],
        "deliverable_file_hf_uris": [[]],
        "rubric_pretty": ["rubric"],
        "rubric_json": ["{}"],
        "deliverable_text": [""],
    })


def _write_source_manifest(tmp_path, monkeypatch, frame):
    projection = bootstrapper.source_projection_hashes(frame)[0]
    manifest = {
        "_schema_version": 4,
        "_source": bootstrapper.DATASET_ID,
        "_source_revision": bootstrapper.SOURCE_REVISION,
        "tasks": {
            "task-1": {"source_projection_sha256": projection},
        },
    }
    encoded = json.dumps(manifest).encode("utf-8")
    monkeypatch.setattr(
        bootstrapper,
        "CANONICAL_MANIFEST_SHA256_BY_POLICY",
        {bootstrapper.NEEDS_FILES_POLICY: hashlib.sha256(encoded).hexdigest()},
    )
    path = tmp_path / bootstrapper.MANIFEST_FILENAME
    path.write_bytes(encoded)
    return path


def _base_frame():
    return pd.DataFrame({
        "task_id": ["task-1"],
        "reference_files": [[]],
        "reference_file_urls": [[]],
        "reference_file_hf_uris": [[]],
        "deliverable_text": ["stale text"],
        "deliverable_files": [["deliverable_files/task-1/stale.pdf"]],
        "deliverable_file_urls": [["https://example.invalid/stale.pdf"]],
        "deliverable_file_hf_uris": [["hf://invalid/stale.pdf"]],
    })


def test_failed_result_clears_stale_submitter_columns(tmp_path):
    source = tmp_path / "source.parquet"
    output = tmp_path / "output.parquet"
    result = tmp_path / "result.json"
    _base_frame().to_parquet(source, index=False)
    result.write_text(json.dumps({
        "experiment_id": "exp-test",
        "results": [{
            "task_id": "task-1",
            "status": "error",
            "deliverable_text": None,
            "deliverable_files": [],
        }],
    }), encoding="utf-8")

    fill_parquet(
        str(source),
        str(result),
        str(output),
        compact=True,
        overwrite_existing=True,
        selected_task_ids=["task-1"],
        submission_repo_id="owner/repository",
    )

    row = pd.read_parquet(output).iloc[0]
    assert row["deliverable_text"] == ""
    assert list(row["deliverable_files"]) == []
    assert list(row["deliverable_file_urls"]) == []
    assert list(row["deliverable_file_hf_uris"]) == []


def test_fill_rejects_source_semantic_drift_before_output(tmp_path, monkeypatch):
    frame = _source_frame()
    manifest = _write_source_manifest(tmp_path, monkeypatch, frame)
    frame.at[0, "rubric_json"] = '{"tampered":true}'
    source = tmp_path / "source.parquet"
    output = tmp_path / "output.parquet"
    result = tmp_path / "result.json"
    frame.to_parquet(source, index=False)
    result.write_text(json.dumps({
        "experiment_id": "exp-test",
        "results": [{
            "task_id": "task-1",
            "status": "success",
            "deliverable_text": "done",
            "deliverable_files": [],
        }],
    }), encoding="utf-8")

    with pytest.raises(ValueError, match="source projection differs"):
        fill_parquet(
            str(source),
            str(result),
            str(output),
            source_manifest_path=str(manifest),
        )

    assert not output.exists()


def test_fill_output_uses_exact_canonical_target_columns(tmp_path, monkeypatch):
    frame = _source_frame()
    manifest = _write_source_manifest(tmp_path, monkeypatch, frame)
    source = tmp_path / "source.parquet"
    output = tmp_path / "output.parquet"
    result = tmp_path / "result.json"
    frame.to_parquet(source, index=False)
    result.write_text(json.dumps({
        "experiment_id": "exp-test",
        "results": [{
            "task_id": "task-1",
            "status": "success",
            "deliverable_text": "done",
            "deliverable_files": [],
        }],
    }), encoding="utf-8")
    monkeypatch.setattr(
        bootstrapper,
        "validate_needs_files_manifest",
        lambda *_args, **_kwargs: [],
    )

    fill_parquet(
        str(source),
        str(result),
        str(output),
        compact=True,
        overwrite_existing=True,
        selected_task_ids=["task-1"],
        source_manifest_path=str(manifest),
    )

    published = pd.read_parquet(output)
    assert tuple(published.columns) == bootstrapper.CANONICAL_TARGET_COLUMNS
    assert bootstrapper.validate_source_projection_rows(published, manifest) == []


def test_pre_upload_requires_exact_parquet_and_file_tree(tmp_path):
    relative = "deliverable_files/task-1/report.pdf"
    urls, uris = _build_deliverable_uris([relative], "owner/repository")
    frame = pd.DataFrame({
        "task_id": ["task-1"],
        "deliverable_files": [[relative]],
        "deliverable_file_urls": [urls],
        "deliverable_file_hf_uris": [uris],
    })
    output = tmp_path / relative
    output.parent.mkdir(parents=True)
    output.write_bytes(b"pdf")

    assert validate_deliverable_tree(
        frame,
        tmp_path,
        submission_repo_id="owner/repository",
    ) == []

    frame.at[0, "deliverable_file_urls"] = ["https://example.invalid/report.pdf"]
    errors = validate_deliverable_tree(
        frame,
        tmp_path,
        submission_repo_id="owner/repository",
    )
    assert any("URL/URI identity mismatch" in error for error in errors)
    frame.at[0, "deliverable_file_urls"] = urls

    extra = tmp_path / "deliverable_files/task-1/extra.pdf"
    extra.write_bytes(b"extra")
    errors = validate_deliverable_tree(
        frame,
        tmp_path,
        submission_repo_id="owner/repository",
    )
    assert any("extra.pdf" in error for error in errors)

    extra.unlink()
    output.unlink()
    errors = validate_deliverable_tree(
        frame,
        tmp_path,
        submission_repo_id="owner/repository",
    )
    assert any("report.pdf" in error for error in errors)


def test_pre_upload_rejects_cross_task_deliverable_path(tmp_path):
    relative = "deliverable_files/task-2/report.pdf"
    urls, uris = _build_deliverable_uris([relative], "owner/repository")
    frame = pd.DataFrame({
        "task_id": ["task-1"],
        "deliverable_files": [[relative]],
        "deliverable_file_urls": [urls],
        "deliverable_file_hf_uris": [uris],
    })
    output = tmp_path / relative
    output.parent.mkdir(parents=True)
    output.write_bytes(b"pdf")

    errors = validate_deliverable_tree(
        frame,
        tmp_path,
        submission_repo_id="owner/repository",
    )

    assert any("deliverable_files/task-1/" in error for error in errors)


def test_pre_upload_rejects_stale_second_parquet_shard(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    frame = pd.DataFrame({
        "task_id": ["task-1"],
        "sector": ["sector"],
        "occupation": ["occupation"],
        "prompt": ["prompt"],
        "rubric_json": ["{}"],
        "rubric_pretty": ["rubric"],
        "deliverable_text": [""],
        "deliverable_files": [[]],
        "deliverable_file_urls": [[]],
        "deliverable_file_hf_uris": [[]],
    })
    frame.to_parquet(data / bootstrapper.CANONICAL_PARQUET_FILENAME, index=False)
    frame.to_parquet(data / "train-00001-of-00002.parquet", index=False)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / bootstrapper.MANIFEST_FILENAME).write_text(
        json.dumps({"tasks": {}}), encoding="utf-8"
    )
    monkeypatch.setattr(bootstrapper, "WORKSPACE_DIR", workspace)

    errors = bootstrapper.validate_pre_upload(
        local_path=str(tmp_path),
        submission_repo_id="owner/repository",
        expected_rows=1,
    )

    assert any("shard set must be exactly" in error for error in errors)


@pytest.mark.parametrize(
    ("parquet_ids", "prepared_ids"),
    [
        (["task-1"], ["task-1", "task-2"]),
        (["task-1", "task-3"], ["task-1", "task-2"]),
        (["task-2", "task-1"], ["task-1", "task-2"]),
    ],
)
def test_pre_upload_rejects_parquet_outside_exact_prepared_scope(
    tmp_path, monkeypatch, parquet_ids, prepared_ids
):
    data = tmp_path / "data"
    data.mkdir()
    frame = pd.concat(
        [
            _source_frame().assign(task_id=task_id)
            for task_id in parquet_ids
        ],
        ignore_index=True,
    )
    frame.to_parquet(data / bootstrapper.CANONICAL_PARQUET_FILENAME, index=False)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / bootstrapper.MANIFEST_FILENAME).write_text(
        json.dumps({
            "tasks": {
                task_id: {"needs_files": False}
                for task_id in prepared_ids
            }
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(bootstrapper, "WORKSPACE_DIR", workspace)
    monkeypatch.setattr(
        bootstrapper, "validate_source_projection_rows", lambda *_args: []
    )
    monkeypatch.setattr(bootstrapper, "validate_deliverable_tree", lambda *_args, **_kwargs: [])

    errors = bootstrapper.validate_pre_upload(
        local_path=str(tmp_path),
        submission_repo_id="owner/repository",
        expected_task_ids=prepared_ids,
    )

    assert any("must exactly match prepared order" in error for error in errors)


def test_pre_upload_accepts_exact_prepared_scope_order(tmp_path, monkeypatch):
    prepared_ids = ["task-1", "task-2"]
    data = tmp_path / "data"
    data.mkdir()
    frame = pd.concat(
        [_source_frame().assign(task_id=task_id) for task_id in prepared_ids],
        ignore_index=True,
    )
    frame.to_parquet(data / bootstrapper.CANONICAL_PARQUET_FILENAME, index=False)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / bootstrapper.MANIFEST_FILENAME).write_text(
        json.dumps({
            "tasks": {
                task_id: {"needs_files": False}
                for task_id in prepared_ids
            }
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(bootstrapper, "WORKSPACE_DIR", workspace)
    monkeypatch.setattr(
        bootstrapper, "validate_source_projection_rows", lambda *_args: []
    )
    monkeypatch.setattr(bootstrapper, "validate_deliverable_tree", lambda *_args, **_kwargs: [])

    errors = bootstrapper.validate_pre_upload(
        local_path=str(tmp_path),
        submission_repo_id="owner/repository",
        expected_task_ids=prepared_ids,
    )

    assert not any("prepared" in error.lower() for error in errors)


@pytest.mark.parametrize(
    ("column", "stale_value", "message"),
    [
        ("deliverable_text", "stale text", "deliverable_text differs"),
        (
            "deliverable_files",
            ["deliverable_files/task-1/stale.pdf"],
            "deliverable_files differs",
        ),
        (
            "deliverable_file_urls",
            ["https://example.invalid/stale.pdf"],
            "deliverable_file_urls differs",
        ),
        (
            "deliverable_file_hf_uris",
            ["hf://datasets/other/repo/stale.pdf"],
            "deliverable_file_hf_uris differs",
        ),
    ],
)
def test_pre_upload_rejects_same_scope_stale_result_projection(
    tmp_path, monkeypatch, column, stale_value, message
):
    data = tmp_path / "data"
    data.mkdir()
    frame = _source_frame()
    frame.at[0, column] = stale_value
    frame.to_parquet(data / bootstrapper.CANONICAL_PARQUET_FILENAME, index=False)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / bootstrapper.MANIFEST_FILENAME).write_text(
        json.dumps({"tasks": {"task-1": {"needs_files": False}}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(bootstrapper, "WORKSPACE_DIR", workspace)
    monkeypatch.setattr(
        bootstrapper, "validate_source_projection_rows", lambda *_args: []
    )
    monkeypatch.setattr(
        bootstrapper, "validate_deliverable_tree", lambda *_args, **_kwargs: []
    )
    expected = [{
        "task_id": "task-1",
        "deliverable_text": "",
        "deliverable_files": [],
        "deliverable_file_urls": [],
        "deliverable_file_hf_uris": [],
    }]

    errors = bootstrapper.validate_pre_upload(
        local_path=str(tmp_path),
        submission_repo_id="owner/repository",
        expected_task_ids=["task-1"],
        expected_submitter_rows=expected,
    )

    assert any(message in error for error in errors)


def test_pre_upload_accepts_current_result_projection(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    frame = _source_frame()
    frame.to_parquet(data / bootstrapper.CANONICAL_PARQUET_FILENAME, index=False)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / bootstrapper.MANIFEST_FILENAME).write_text(
        json.dumps({"tasks": {"task-1": {"needs_files": False}}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(bootstrapper, "WORKSPACE_DIR", workspace)
    monkeypatch.setattr(
        bootstrapper, "validate_source_projection_rows", lambda *_args: []
    )
    monkeypatch.setattr(
        bootstrapper, "validate_deliverable_tree", lambda *_args, **_kwargs: []
    )

    errors = bootstrapper.validate_pre_upload(
        local_path=str(tmp_path),
        submission_repo_id="owner/repository",
        expected_task_ids=["task-1"],
        expected_submitter_rows=[{
            "task_id": "task-1",
            "deliverable_text": "",
            "deliverable_files": [],
            "deliverable_file_urls": [],
            "deliverable_file_hf_uris": [],
        }],
    )

    assert not any("differs from Step 2" in error for error in errors)


def test_dummy_urls_use_canonical_main_revision_identity():
    expected_urls, expected_uris = _build_deliverable_uris(
        ["deliverable_files/task-1/failed_to_generate.txt"],
        "owner/repository",
    )

    result = _build_dummy_urls("task-1", "owner/repository")

    assert result["deliverable_file_urls"] == expected_urls
    assert result["deliverable_file_hf_uris"] == expected_uris


def test_step7_passes_repo_identity_to_pre_upload_validator():
    script = Path("step7_upload_hf.sh").read_text(encoding="utf-8")

    assert 'submission_repo_id=os.environ["REPO_ID"]' in script
    assert "sum(len(pd.read_parquet(path)) for path in parquets)" not in script
    assert "load_publication_identity(" in script
    assert "expected_task_ids=list(identity.ordered_task_ids)" in script
    assert "expected_submitter_rows=identity.submitter_rows()" in script
    assert 'os.environ.get("EXPECTED_TARGET_HEAD", "")' in script
    assert "load_target_head_identity(" in script
    assert "publication = publish_dataset(" in script
    assert "Verified revision: {publication.oid}" in script
    assert "Publication plan: {publication.plan_sha256}" in script
    assert "if publication.reconciled:" in script
    assert "identity=identity" in script