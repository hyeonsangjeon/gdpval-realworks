from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
import yaml


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "preflight_track2_cohort.py"
)
SPEC = importlib.util.spec_from_file_location(
    "preflight_track2_cohort", SCRIPT_PATH
)
assert SPEC is not None and SPEC.loader is not None
preflight = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preflight)


def _argv(config: str, inference: Path, tmp_path: Path) -> list[str]:
    config_path = Path(__file__).resolve().parents[1] / config
    config_data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    return [
        "preflight_track2_cohort.py",
        "--config",
        config,
        "--inference",
        str(inference),
        "--upload-root",
        str(tmp_path / "upload"),
        "--limit",
        "3",
        "--expected-source-repo",
        "owner/repo",
        "--expected-source-revision",
        "a" * 40,
        "--expected-repository-commit",
        preflight._repository_commit(),
        "--expected-planner-source-hash",
        preflight._planner_source_hash(),
        "--expected-config-hash",
        preflight.hash_config(str(config_path)),
        "--expected-grader-source-hash",
        preflight.compute_grader_source_hash(config_path, config_data),
        "--expected-rubric-sha",
        "d" * 40,
        "--expected-task-id",
        "task-1",
        "--expected-task-id",
        "task-2",
        "--expected-task-id",
        "task-3",
        "--output",
        str(tmp_path / "plan.json"),
    ]


@pytest.fixture(autouse=True)
def _clean_worktree(monkeypatch):
    monkeypatch.setattr(preflight, "_worktree_status", lambda: "")


def test_planner_identity_helpers_are_stable():
    planner_hash = preflight._planner_source_hash()
    repository_commit = preflight._repository_commit()

    assert len(planner_hash) == 64
    assert len(repository_commit) == 40
    int(planner_hash, 16)
    int(repository_commit, 16)


def test_cli_rejects_v1_config_before_inference_load(monkeypatch, tmp_path):
    missing_inference = tmp_path / "missing.json"
    monkeypatch.setattr(
        "sys.argv",
        _argv(
            "grading_configs/default_gpt5pro.yaml",
            missing_inference,
            tmp_path,
        ),
    )

    with pytest.raises(
        SystemExit, match="cohort preflight requires schema_version 2.0"
    ):
        preflight.main()


def test_cli_rejects_inference_shorter_than_limit(monkeypatch, tmp_path):
    inference = tmp_path / "inference.json"
    inference.write_text(
        json.dumps({
            "source_repo_id": "owner/repo",
            "source_revision": "a" * 40,
            "results": [{
                "task_id": "task-1",
                "deliverable_files": [],
            }],
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "sys.argv",
        _argv(
            "grading_configs/validation_v2_mini_cohort3.yaml",
            inference,
            tmp_path,
        ),
    )

    with pytest.raises(SystemExit, match="inference has 1 rows, below limit 3"):
        preflight.main()


def test_cli_rejects_wrong_source_repo(monkeypatch, tmp_path):
    inference = tmp_path / "inference.json"
    inference.write_text(
        json.dumps({
            "source_repo_id": "other/repo",
            "source_revision": "a" * 40,
            "results": [],
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "sys.argv",
        _argv(
            "grading_configs/validation_v2_mini_cohort3.yaml",
            inference,
            tmp_path,
        ),
    )

    with pytest.raises(SystemExit, match="source repo mismatch"):
        preflight.main()


@pytest.mark.parametrize(
    ("option", "wrong_value", "message"),
    [
        ("--expected-repository-commit", "0" * 40, "repository commit mismatch"),
        ("--expected-planner-source-hash", "0" * 64, "planner source hash mismatch"),
        ("--expected-config-hash", "0" * 16, "config hash mismatch"),
        ("--expected-grader-source-hash", "0" * 64, "grader source hash mismatch"),
    ],
)
def test_cli_rejects_wrong_local_identity(
    monkeypatch, tmp_path, option, wrong_value, message
):
    inference = tmp_path / "inference.json"
    argv = _argv(
        "grading_configs/validation_v2_mini_cohort3.yaml",
        inference,
        tmp_path,
    )
    expected_index = argv.index(option) + 1
    argv[expected_index] = wrong_value
    monkeypatch.setattr("sys.argv", argv)

    with pytest.raises(SystemExit, match=message):
        preflight.main()


def test_cli_rejects_wrong_source_revision(monkeypatch, tmp_path):
    inference = tmp_path / "inference.json"
    inference.write_text(
        json.dumps({
            "source_repo_id": "owner/repo",
            "source_revision": "b" * 40,
            "results": [],
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "sys.argv",
        _argv(
            "grading_configs/validation_v2_mini_cohort3.yaml",
            inference,
            tmp_path,
        ),
    )

    with pytest.raises(SystemExit, match="source revision mismatch"):
        preflight.main()


def test_cli_rejects_dirty_worktree(monkeypatch, tmp_path):
    missing_inference = tmp_path / "missing.json"
    monkeypatch.setattr(preflight, "_worktree_status", lambda: " M core/grader.py")
    monkeypatch.setattr(
        "sys.argv",
        _argv(
            "grading_configs/validation_v2_mini_cohort3.yaml",
            missing_inference,
            tmp_path,
        ),
    )

    with pytest.raises(SystemExit, match="repository worktree must be clean"):
        preflight.main()


def test_repository_commit_rejects_github_sha_mismatch(monkeypatch):
    monkeypatch.setenv("GITHUB_SHA", "0" * 40)

    with pytest.raises(ValueError, match="GITHUB_SHA does not match HEAD"):
        preflight._repository_commit()


def test_cli_rejects_wrong_ordered_task_ids(monkeypatch, tmp_path):
    inference = tmp_path / "inference.json"
    inference.write_text(
        json.dumps({
            "source_repo_id": "owner/repo",
            "source_revision": "a" * 40,
            "results": [
                {"task_id": task_id, "deliverable_files": []}
                for task_id in ("task-3", "task-2", "task-1")
            ],
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "sys.argv",
        _argv(
            "grading_configs/validation_v2_mini_cohort3.yaml",
            inference,
            tmp_path,
        ),
    )

    with pytest.raises(SystemExit, match="ordered task IDs mismatch"):
        preflight.main()


def test_cli_rejects_wrong_rubric_sha(monkeypatch, tmp_path):
    inference = tmp_path / "inference.json"
    inference.write_text(
        json.dumps({
            "source_repo_id": "owner/repo",
            "source_revision": "a" * 40,
            "results": [
                {"task_id": task_id, "deliverable_files": []}
                for task_id in ("task-1", "task-2", "task-3")
            ],
        }),
        encoding="utf-8",
    )

    class _Loader:
        rubric_sha = "e" * 40

        def __init__(self, **kwargs):
            pass

    monkeypatch.setattr(preflight, "RubricLoader", _Loader)
    monkeypatch.setattr(
        "sys.argv",
        _argv(
            "grading_configs/validation_v2_mini_cohort3.yaml",
            inference,
            tmp_path,
        ),
    )

    with pytest.raises(SystemExit, match="rubric SHA mismatch"):
        preflight.main()


def test_planner_script_is_present_for_direct_entry():
    assert SCRIPT_PATH.is_file()
    assert SCRIPT_PATH.read_text(encoding="utf-8").startswith("#!/usr/bin/env python3")