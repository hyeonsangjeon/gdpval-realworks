import json
from types import SimpleNamespace

import pytest

import step1_prepare_tasks as step1
import step2_run_inference as step2
from core.needs_files import NeedsFilesManifest
from core.prepared_fingerprint import prepared_fingerprint
from core.source_identity import source_task_projection_sha256


SOURCE_HASH = source_task_projection_sha256(
    task_id="task-1",
    sector="sector",
    occupation="occupation",
    prompt="Create a file",
    rubric_pretty="rubric pretty",
    rubric_json="{}",
    reference_files=[],
    reference_file_urls=[],
    reference_file_hf_uris=[],
)


def _step1_config():
    return SimpleNamespace(
        experiment_id="exp-test",
        name="Manifest guard",
        description="test",
        validate=lambda: [],
        data_filter=SimpleNamespace(
            sector=None,
            occupation=None,
            task_ids=None,
            sample_size=None,
            source="owner/repository",
        ),
    )


def _task():
    return SimpleNamespace(
        task_id="task-1",
        sector="sector",
        occupation="occupation",
        prompt="Create a file",
        reference_files=[],
        reference_file_urls=[],
        reference_file_hf_uris=[],
        rubric_pretty="rubric pretty",
        rubric_json="{}",
    )


def test_step1_missing_manifest_fails_before_prepared_write(tmp_path, monkeypatch):
    monkeypatch.setattr(step1, "WORKSPACE_DIR", tmp_path)
    monkeypatch.setattr(
        step1.ExperimentConfig,
        "from_yaml",
        lambda _path: _step1_config(),
    )
    monkeypatch.setattr(
        step1,
        "GDPValDataLoader",
        lambda auto_download=False: SimpleNamespace(load=lambda: [_task()]),
    )
    monkeypatch.setattr(
        step1.NeedsFilesManifest,
        "load",
        lambda: (_ for _ in ()).throw(FileNotFoundError("manifest missing")),
    )

    with pytest.raises(FileNotFoundError, match="manifest missing"):
        step1.prepare_tasks("fixture.yaml")

    assert not (tmp_path / "step1_tasks_prepared.json").exists()


def test_step1_legacy_manifest_fails_before_prepared_write(tmp_path, monkeypatch):
    monkeypatch.setattr(step1, "WORKSPACE_DIR", tmp_path)
    monkeypatch.setattr(
        step1.ExperimentConfig,
        "from_yaml",
        lambda _path: _step1_config(),
    )
    monkeypatch.setattr(
        step1,
        "GDPValDataLoader",
        lambda auto_download=False: SimpleNamespace(load=lambda: [_task()]),
    )
    monkeypatch.setattr(
        step1.NeedsFilesManifest,
        "load",
        lambda: NeedsFilesManifest({"_schema_version": 2, "tasks": {}}),
    )

    with pytest.raises(ValueError, match="schema must be 4"):
        step1.prepare_tasks("fixture.yaml")

    assert not (tmp_path / "step1_tasks_prepared.json").exists()


def _write_prepared(workspace, *, reference_file_records=None):
    prepared = {
        "experiment_id": "exp-test",
        "experiment_name": "Manifest guard",
        "source": "owner/repository",
        "execution": {
            "mode": "subprocess",
            "max_retries": 0,
            "resume_max_rounds": 0,
        },
        "condition_a": {
            "name": "Baseline",
            "model": {"provider": "azure", "deployment": "model"},
            "prompt": {"system": "system"},
        },
        "condition_b": None,
        "tasks": [{
            "task_id": "task-1",
            "instruction": "Create a file",
            "occupation": "occupation",
            "reference_files": [],
            "reference_file_records": reference_file_records or [],
            "needs_files": True,
            "source_projection_sha256": SOURCE_HASH,
        }],
    }
    prepared["prepared_fingerprint"] = prepared_fingerprint(prepared)
    workspace.mkdir()
    (workspace / "step1_tasks_prepared.json").write_text(
        json.dumps(prepared),
        encoding="utf-8",
    )


def test_step2_missing_manifest_fails_before_provider_client(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    _write_prepared(workspace)
    monkeypatch.setattr(step2, "WORKSPACE_DIR", workspace)
    monkeypatch.setattr(
        step2.NeedsFilesManifest,
        "load",
        lambda: (_ for _ in ()).throw(FileNotFoundError("manifest missing")),
    )
    monkeypatch.setattr(
        step2,
        "create_provider_client",
        lambda *_args, **_kwargs: pytest.fail("provider client must not be created"),
    )
    monkeypatch.setattr(
        step2,
        "TaskExecutor",
        lambda *_args, **_kwargs: pytest.fail("executor must not be created"),
    )

    with pytest.raises(SystemExit):
        step2.run_inference(resume=False)


def test_step2_prepared_identity_drift_fails_before_provider_client(
    tmp_path, monkeypatch
):
    workspace = tmp_path / "workspace"
    _write_prepared(workspace)
    manifest = NeedsFilesManifest({
        "_schema_version": 4,
        "tasks": {
            "task-1": {
                "needs_files": False,
                "source_projection_sha256": SOURCE_HASH,
            },
        },
        "reference_files": {},
    })
    monkeypatch.setattr(step2, "WORKSPACE_DIR", workspace)
    monkeypatch.setattr(step2.NeedsFilesManifest, "load", lambda: manifest)
    monkeypatch.setattr(
        step2,
        "create_provider_client",
        lambda *_args, **_kwargs: pytest.fail("provider client must not be created"),
    )

    with pytest.raises(SystemExit):
        step2.run_inference(resume=False)