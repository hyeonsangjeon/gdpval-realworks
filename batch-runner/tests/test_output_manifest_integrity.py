import json
from pathlib import Path

import pandas as pd

import core.repo_bootstrapper as bootstrapper
from core.repo_bootstrapper import validate_deliverable_tree
from fill_parquet import _build_deliverable_uris, fill_parquet
from step5_validate import _build_dummy_urls


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
    assert "sum(len(pd.read_parquet(path)) for path in parquets)" in script