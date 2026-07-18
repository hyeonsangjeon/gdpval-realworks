"""Tests for runtime-derived signed approval identities."""

import hashlib
import subprocess
from pathlib import Path

import pytest

from core.agentic_runtime_identity import (
    PLAN_MERGE_SHA,
    derive_runtime_identity,
    derive_runtime_identity_from_environment,
)


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = Path(".github/workflows/batch-run.yml")


def _clean_repository(tmp_path):
    repository = tmp_path / "repository"
    workflow = repository / WORKFLOW
    workflow.parent.mkdir(parents=True)
    workflow.write_text("name: Agentic fixture\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
    subprocess.run(["git", "add", "."], cwd=repository, check=True)
    subprocess.run(
        [
            "git", "-c", "user.name=Agentic Test",
            "-c", "user.email=agentic@example.invalid",
            "commit", "-qm", "fixture",
        ],
        cwd=repository,
        check=True,
    )
    return repository


def test_runtime_identity_uses_actual_git_and_workflow_bytes(tmp_path):
    repository = _clean_repository(tmp_path)
    first = derive_runtime_identity(
        repository_root=repository,
        workflow_path=WORKFLOW,
        workflow_inputs={"condition": "a", "tasks": 5},
    )
    second = derive_runtime_identity(
        repository_root=repository,
        workflow_path=WORKFLOW,
        workflow_inputs={"tasks": 5, "condition": "a"},
    )

    assert first == second
    assert first["plan_sha"] == PLAN_MERGE_SHA
    assert first["implementation_sha"] == subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert first["workflow_sha"] == hashlib.sha256(
        (repository / WORKFLOW).read_bytes()
    ).hexdigest()
    assert len(first["workflow_inputs_sha256"]) == 64


def test_runtime_identity_rejects_dirty_checkout(tmp_path):
    repository = _clean_repository(tmp_path)
    (repository / "untracked.py").write_text("print('changed')\n", encoding="utf-8")

    with pytest.raises(ValueError, match="clean checkout"):
        derive_runtime_identity(
            repository_root=repository,
            workflow_path=WORKFLOW,
            workflow_inputs={},
        )


def test_environment_identity_requires_object_inputs(monkeypatch):
    monkeypatch.setenv("AGENTIC_WORKFLOW_PATH", str(WORKFLOW))
    monkeypatch.setenv("AGENTIC_WORKFLOW_INPUTS_JSON", "[]")

    with pytest.raises(ValueError, match="JSON object"):
        derive_runtime_identity_from_environment(ROOT)


def test_workflow_path_cannot_escape_repository():
    with pytest.raises(ValueError, match="escapes repository"):
        derive_runtime_identity(
            repository_root=ROOT,
            workflow_path="../outside.yml",
            workflow_inputs={},
        )