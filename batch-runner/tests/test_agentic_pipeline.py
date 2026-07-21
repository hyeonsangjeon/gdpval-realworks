"""Model-free pipeline wiring tests for execution.mode=agentic_sandbox."""

from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import step1_prepare_tasks as step1
import step2_run_inference as step2
from core.agentic_experiments import agentic_condition_identity
from core.experiment_config import ExperimentConfig
from core.prepared_fingerprint import prepared_fingerprint


def _config() -> ExperimentConfig:
    return ExperimentConfig.from_dict({
        "experiment": {"id": "exp028", "name": "Agentic fixture"},
        "data": {
            "source": "fixture/agentic",
            "filter": {"task_ids": ["task-1"]},
        },
        "condition_a": {
            "name": "Treatment",
            "model": {"provider": "azure", "deployment": "test-deployment"},
            "prompt": {"system": "system"},
        },
        "execution": {
            "mode": "agentic_sandbox",
            "agentic": {
                "compute_transport": "remote",
                "image": "image@sha256:" + "a" * 64,
                "verifier_image": "verifier@sha256:" + "b" * 64,
                "limits": {"max_model_iterations": 3},
                "budget": {
                    "paired_run_id": "paired-run",
                    "condition": {
                        "attempts": 30, "input_tokens": 1000000,
                        "output_tokens": 100000, "cost_usd": "6.25",
                    },
                    "paired_run": {
                        "attempts": 30, "input_tokens": 1500000,
                        "output_tokens": 163840, "cost_usd": "6.25",
                    },
                },
                "pricing_table": {
                    "sha256": "c" * 64,
                },
                "authorization": {
                    "api_version": "2025-04-01-preview",
                    "provider_classification": "approved_public_gdpval",
                    "endpoint_sha256": "d" * 64,
                },
            },
        },
    })


def _prepared(agentic: dict | None = None) -> dict:
    payload = {
        "experiment_id": "exp028",
        "experiment_name": "Agentic fixture",
        "source": "fixture/agentic",
        "execution": {
            "mode": "agentic_sandbox",
            "max_retries": 0,
            "resume_max_rounds": 0,
            "agentic": agentic or {
                "pricing": {},
                "budget": {
                    "paired_run_id": "paired-run",
                    "condition": {
                        "attempts": 30,
                        "input_tokens": 1_000_000,
                        "output_tokens": 100_000,
                        "cost_usd": "6.25",
                    },
                    "paired_run": {
                        "attempts": 30,
                        "input_tokens": 1_500_000,
                        "output_tokens": 163_840,
                        "cost_usd": "6.25",
                    },
                },
            },
        },
        "tasks": [{
            "task_id": "task-1",
            "sector": "test",
            "occupation": "Analyst",
            "instruction": "Create a report",
            "reference_files": [],
            "needs_files": False,
        }],
        "condition_a": {
            "name": "Treatment",
            "model": {"provider": "azure", "deployment": "test-deployment"},
            "prompt": {"system": "system"},
        },
    }
    payload["prepared_fingerprint"] = prepared_fingerprint(payload)
    return payload


def _patch_step2_workspace(tmp_path, monkeypatch, prepared):
    workspace = tmp_path / "workspace"
    upload = workspace / "upload"
    deliverables = upload / "deliverable_files"
    deliverables.mkdir(parents=True)
    (workspace / "step1_tasks_prepared.json").write_text(
        json.dumps(prepared), encoding="utf-8"
    )
    monkeypatch.setattr(step2, "WORKSPACE_DIR", workspace)
    monkeypatch.setattr(step2, "UPLOAD_DIR", upload)
    monkeypatch.setattr(step2, "DELIVERABLE_DIR", deliverables)
    monkeypatch.setattr(
        step2,
        "_load_private_agentic_config",
        lambda data: dict(data["execution"].get("agentic") or {}),
    )
    monkeypatch.setattr(
        step2.NeedsFilesManifest,
        "load",
        classmethod(lambda cls: (_ for _ in ()).throw(FileNotFoundError())),
    )
    return workspace


def test_step1_preserves_agentic_config_only_when_present(tmp_path, monkeypatch):
    config = _config()
    task = SimpleNamespace(
        task_id="task-1",
        sector="test",
        occupation="Analyst",
        prompt="Create a report",
        reference_files=[],
        reference_file_urls=[],
    )
    monkeypatch.setattr(step1, "WORKSPACE_DIR", tmp_path)
    monkeypatch.setattr(step1.ExperimentConfig, "from_yaml", lambda path: config)
    monkeypatch.setattr(
        step1,
        "GDPValDataLoader",
        lambda auto_download=False: SimpleNamespace(load=lambda: [task]),
    )
    monkeypatch.setattr(
        step1.NeedsFilesManifest,
        "load",
        classmethod(lambda cls: (_ for _ in ()).throw(FileNotFoundError())),
    )

    result = step1.prepare_tasks("fixture.yaml")

    assert result["execution"]["mode"] == "agentic_sandbox"
    assert result["execution"]["agentic"] == {
        "compute_transport": "remote",
        "image": "image@sha256:" + "a" * 64,
        "verifier_image": "verifier@sha256:" + "b" * 64,
        "limits": {"max_model_iterations": 3},
        "budget": config.execution.agentic["budget"],
        "pricing_table": {"sha256": "c" * 64},
    }


def test_step1_redacts_agentic_control_plane_paths(tmp_path, monkeypatch):
    config = _config()
    config.execution.agentic.update({
        "compute_transport": "remote",
        "pricing_table": {
            "sha256": "f" * 64,
        },
    })
    task = SimpleNamespace(
        task_id="task-1", sector="test", occupation="Analyst",
        prompt="Create a report", reference_files=[], reference_file_urls=[],
    )
    monkeypatch.setattr(step1, "WORKSPACE_DIR", tmp_path)
    monkeypatch.setattr(step1.ExperimentConfig, "from_yaml", lambda path: config)
    monkeypatch.setattr(
        step1, "GDPValDataLoader",
        lambda auto_download=False: SimpleNamespace(load=lambda: [task]),
    )
    monkeypatch.setattr(
        step1.NeedsFilesManifest, "load",
        classmethod(lambda cls: (_ for _ in ()).throw(FileNotFoundError())),
    )

    result = step1.prepare_tasks("fixture.yaml")
    serialized = json.dumps(result["execution"]["agentic"])

    assert result["execution"]["agentic"]["compute_transport"] == "remote"
    assert result["execution"]["agentic"]["pricing_table"] == {
        "sha256": "f" * 64
    }
    assert "/private/" not in serialized


def test_step2_defers_provider_client_and_passes_factory(tmp_path, monkeypatch):
    _patch_step2_workspace(tmp_path, monkeypatch, _prepared())
    provider_factory = MagicMock(side_effect=AssertionError("must stay deferred"))
    executor_instance = MagicMock()
    executor_class = MagicMock(return_value=executor_instance)
    monkeypatch.setattr(step2, "create_provider_client", provider_factory)
    monkeypatch.setattr(step2, "TaskExecutor", executor_class)
    monkeypatch.setattr(
        step2,
        "_execute_single_task",
        lambda *args, **kwargs: {
            "task_id": "task-1",
            "status": "success",
            "deliverable_text": "done",
            "deliverable_files": [],
            "latency_ms": 1,
        },
    )

    step2.run_inference(
        condition_key="condition_a", resume=False, resume_max_rounds=0
    )

    provider_factory.assert_not_called()
    kwargs = executor_class.call_args.kwargs
    assert kwargs["llm_client"] is None
    assert callable(kwargs["client_factory"])
    assert kwargs["provider"] == "azure"
    assert kwargs["run_id"] == "paired-run"
    assert kwargs["condition_name"] == "canary"
    assert kwargs["model_name"] == "test-deployment"


def test_reserved_experiments_have_distinct_condition_budget_identities():
    assert agentic_condition_identity("exp028") == "canary"
    assert agentic_condition_identity("exp029") == "baseline"
    assert agentic_condition_identity("exp030") == "treatment"
    with pytest.raises(ValueError, match="unknown agentic experiment ID"):
        agentic_condition_identity("exp027")


def test_step2_rejects_second_condition_for_reserved_experiment(
    tmp_path, monkeypatch
):
    prepared = _prepared()
    prepared["condition_b"] = dict(prepared["condition_a"])
    _patch_step2_workspace(tmp_path, monkeypatch, prepared)
    monkeypatch.setattr(step2, "create_provider_client", MagicMock())

    with pytest.raises(SystemExit):
        step2.run_inference(
            condition_key="condition_a", resume=False, resume_max_rounds=0
        )


def test_reserved_agentic_experiment_rejects_mode_downgrade_before_client(
    tmp_path, monkeypatch
):
    _patch_step2_workspace(tmp_path, monkeypatch, _prepared())
    provider_factory = MagicMock()
    monkeypatch.setattr(step2, "create_provider_client", provider_factory)

    with pytest.raises(SystemExit):
        step2.run_inference(
            execution_mode="subprocess",
            condition_key="condition_a",
            resume=False,
            resume_max_rounds=0,
        )

    provider_factory.assert_not_called()


def test_hardened_execution_rejects_task_resume_rounds_before_client(
    tmp_path, monkeypatch
):
    _patch_step2_workspace(tmp_path, monkeypatch, _prepared())
    provider_factory = MagicMock()
    monkeypatch.setattr(step2, "create_provider_client", provider_factory)

    with pytest.raises(SystemExit):
        step2.run_inference(
            condition_key="condition_a",
            resume=False,
            max_retries=0,
            resume_max_rounds=1,
        )

    provider_factory.assert_not_called()


@pytest.mark.parametrize("field", ["prefix", "body"])
def test_hardened_execution_rejects_unpaired_prompt_override_before_client(
    tmp_path, monkeypatch, field
):
    prepared = _prepared()
    prepared["condition_a"]["prompt"][field] = "unpaired override"
    _patch_step2_workspace(tmp_path, monkeypatch, prepared)
    provider_factory = MagicMock()
    monkeypatch.setattr(step2, "create_provider_client", provider_factory)

    with pytest.raises(SystemExit):
        step2.run_inference(
            condition_key="condition_a",
            resume=False,
            max_retries=0,
            resume_max_rounds=0,
        )

    provider_factory.assert_not_called()


@pytest.mark.parametrize("blocked_field", ["qa", "preprocessors"])
def test_step2_blocks_unledgered_agentic_auxiliary_calls(
    tmp_path, monkeypatch, blocked_field
):
    prepared = _prepared()
    if blocked_field == "qa":
        prepared["condition_a"]["qa"] = {"enabled": True}
    else:
        prepared["condition_a"]["preprocessors"] = [{"type": "audio_analyzer"}]
    _patch_step2_workspace(tmp_path, monkeypatch, prepared)
    provider_factory = MagicMock()
    monkeypatch.setattr(step2, "create_provider_client", provider_factory)

    with pytest.raises(SystemExit):
        step2.run_inference(
            condition_key="condition_a", resume=False, resume_max_rounds=0
        )

    provider_factory.assert_not_called()


def test_agentic_observability_drops_raw_model_and_compute_content():
    secret = "/private/client/raw-solution.py --dangerous-argv"
    observed = step2._build_execution_observability({
        "agentic_metrics": {
            "schema_version": "1.0",
            "model_api_calls": 2,
            "model_iterations": 2,
            "tool_calls": 3,
            "tool_errors": 1,
            "tool_calls_by_name": {"run_python": 1, secret: 99},
            "model_time_ms": 12.5,
            "tool_time_ms": 3.5,
            "task_wall_time_ms": 20,
            "input_tokens": 100,
            "output_tokens": 20,
            "cached_tokens": 5,
            "conservative_cost_usd": "0.0123456789",
            "usage_complete": True,
            "terminal_error_category": "verification_failed",
            "raw_code": secret,
            "raw_arguments": secret,
            "stdout": secret,
        }
    }, [])

    metrics = observed["agentic_metrics"]
    assert metrics["model_api_calls"] == 2
    assert metrics["tool_calls_by_name"] == {"run_python": 1}
    assert metrics["conservative_cost_usd"] == 0.01234568
    assert secret not in str(observed)


def test_resume_merge_does_not_double_count_ledger_cumulative_usage():
    previous = {
        "schema_version": "1.0",
        "ledger_cumulative": True,
        "model_api_calls": 1,
        "model_iterations": 1,
        "tool_calls": 2,
        "tool_errors": 0,
        "tool_calls_by_name": {"run_python": 1, "inspect_artifacts": 1},
        "model_time_ms": 10,
        "tool_time_ms": 5,
        "task_wall_time_ms": 20,
        "finalize_required_corrections": 0,
        "finalize_attempts": 0,
        "capability_misses": 0,
        "recovered_after_tool_error": False,
        "input_tokens": 100,
        "output_tokens": 20,
        "cached_tokens": 5,
        "conservative_cost_usd": 0.1,
        "usage_complete": True,
        "terminal_error_category": "model_api_error",
    }
    current = {
        **previous,
        "model_api_calls": 2,
        "model_iterations": 1,
        "tool_calls": 1,
        "tool_calls_by_name": {"finalize": 1},
        "input_tokens": 220,
        "output_tokens": 50,
        "cached_tokens": 7,
        "conservative_cost_usd": 0.25,
        "terminal_error_category": None,
    }

    merged = step2._merge_agentic_metrics(previous, current)

    assert merged["model_api_calls"] == 2
    assert merged["input_tokens"] == 220
    assert merged["output_tokens"] == 50
    assert merged["model_iterations"] == 2
    assert merged["tool_calls"] == 3
    assert merged["cached_tokens"] == 12
    assert merged["conservative_cost_usd"] == 0.25


def test_hardened_task_passes_relative_reference_ids_without_host_reads(
    tmp_path, monkeypatch
):
    executor = MagicMock()
    executor.execute.return_value = {
        "success": False,
        "error": "remote_compute_rejected_input",
        "text": "",
        "files": [],
    }
    monkeypatch.setattr(step2, "DEFAULT_LOCAL_PATH", tmp_path)
    task = {
        "task_id": "task-1",
        "instruction": "Create a report",
        "occupation": "Analyst",
        "reference_files": ["missing.xlsx"],
    }
    condition = {
        "prompt": {"system": "system"},
        "preprocessors": [],
    }

    result = step2._execute_single_task(
        task,
        condition,
        executor,
        "agentic_sandbox",
        None,
        "model",
        strict_inputs=True,
    )

    assert result["status"] == "error"
    assert result["error"] == "remote_compute_rejected_input"
    assert executor.execute.call_args.kwargs["reference_files"] == [
        "missing.xlsx"
    ]


def test_save_files_accepts_nested_canonical_deliverable(tmp_path, monkeypatch):
    upload = tmp_path / "upload"
    deliverables = upload / "deliverable_files"
    monkeypatch.setattr(step2, "UPLOAD_DIR", upload)
    monkeypatch.setattr(step2, "DELIVERABLE_DIR", deliverables)

    saved = step2._save_files(
        [{"filename": "reports/final.pdf", "content": b"pdf"}],
        "task-1",
    )

    assert saved == ["deliverable_files/task-1/reports/final.pdf"]
    assert (deliverables / "task-1" / "reports" / "final.pdf").read_bytes() == b"pdf"


@pytest.mark.parametrize(
    ("task_id", "filename"),
    [
        ("../other-task", "report.txt"),
        ("task-1", "../escape.txt"),
        ("task-1", "/tmp/escape.txt"),
        ("task-1", ".hidden.txt"),
    ],
)
def test_save_files_rejects_task_and_filename_traversal(
    tmp_path, monkeypatch, task_id, filename
):
    upload = tmp_path / "upload"
    monkeypatch.setattr(step2, "UPLOAD_DIR", upload)
    monkeypatch.setattr(step2, "DELIVERABLE_DIR", upload / "deliverable_files")

    with pytest.raises(ValueError, match="deliverable"):
        step2._save_files([{"filename": filename, "content": b"x"}], task_id)


def test_save_files_rejects_symlink_parent_and_duplicate_name(tmp_path, monkeypatch):
    upload = tmp_path / "upload"
    deliverables = upload / "deliverable_files"
    task_dir = deliverables / "task-1"
    task_dir.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    (task_dir / "reports").symlink_to(outside, target_is_directory=True)
    monkeypatch.setattr(step2, "UPLOAD_DIR", upload)
    monkeypatch.setattr(step2, "DELIVERABLE_DIR", deliverables)

    with pytest.raises(ValueError, match="parent"):
        step2._save_files(
            [{"filename": "reports/final.pdf", "content": b"x"}],
            "task-1",
        )
    with pytest.raises(ValueError, match="duplicated"):
        step2._save_files(
            [
                {"filename": "report.txt", "content": b"one"},
                {"filename": "report.txt", "content": b"two"},
            ],
            "task-2",
        )


def test_progress_checkpoint_requires_exact_identity_and_recovers_missing_tasks(
    tmp_path
):
    path = tmp_path / "progress.json"
    document = {
        "schema_version": "step2-progress-v2",
        "experiment_id": "exp030",
        "condition": "Treatment",
        "condition_identity": "treatment",
        "run_id": "paired-run",
        "execution_mode": "agentic_sandbox",
        "ordered_task_ids": ["task-1", "task-2"],
        "prepared_fingerprint": "a" * 64,
        "total_tasks": 2,
        "started_at": "2026-07-17T00:00:00+00:00",
        "resume_round": 0,
        "results": [{"task_id": "task-1", "status": "success"}],
    }
    path.write_text(json.dumps(document), encoding="utf-8")

    loaded = step2._load_and_validate_progress(
        path,
        experiment_id="exp030",
        condition_name="Treatment",
        condition_identity="treatment",
        run_id="paired-run",
        execution_mode="agentic_sandbox",
        ordered_task_ids=["task-1", "task-2"],
        prepared_fingerprint="a" * 64,
    )

    assert [result["task_id"] for result in loaded["results"]] == [
        "task-1", "task-2"
    ]
    assert loaded["results"][1]["status"] == "pending"
    assert loaded["results"][1]["error"] == "checkpoint_missing_task"

    with pytest.raises(ValueError, match="identity mismatch"):
        step2._load_and_validate_progress(
            path,
            experiment_id="exp030",
            condition_name="Treatment",
            condition_identity="treatment",
            run_id="other-run",
            execution_mode="agentic_sandbox",
            ordered_task_ids=["task-1", "task-2"],
            prepared_fingerprint="a" * 64,
        )


def test_progress_task_set_rejects_duplicate_extra_and_final_reordering():
    ordered = ["task-1", "task-2"]
    with pytest.raises(ValueError, match="duplicate"):
        step2._validate_result_task_set(
            [{"task_id": "task-1"}, {"task_id": "task-1"}],
            ordered,
            allow_missing=True,
        )
    with pytest.raises(ValueError, match="unexpected"):
        step2._validate_result_task_set(
            [{"task_id": "task-3"}], ordered, allow_missing=True
        )
    with pytest.raises(ValueError, match="differ from ordered"):
        step2._validate_result_task_set(
            [{"task_id": "task-2"}, {"task_id": "task-1"}],
            ordered,
            allow_missing=False,
        )


def test_failed_hardened_snapshot_is_saved_as_non_deliverable_evidence(
    tmp_path, monkeypatch
):
    evidence_root = tmp_path / "batch-output"
    monkeypatch.setattr(step2, "BATCH_OUTPUT_DIR", evidence_root)
    executor = MagicMock()
    executor.execute.return_value = {
        "success": False,
        "error": "model_api_error",
        "text": "",
        "deliverable_text": "",
        "files": [{"filename": "report.txt", "content": b"verified"}],
        "agentic_metrics": {
            "schema_version": "1.0",
            "ledger_cumulative": True,
            "model_api_calls": 2,
            "model_iterations": 2,
            "tool_calls": 1,
            "tool_errors": 0,
            "tool_calls_by_name": {"inspect_artifacts": 1},
            "model_time_ms": 1,
            "tool_time_ms": 1,
            "task_wall_time_ms": 2,
            "finalize_required_corrections": 0,
            "finalize_attempts": 0,
            "capability_misses": 0,
            "recovered_after_tool_error": False,
            "input_tokens": 1,
            "output_tokens": 1,
            "cached_tokens": 0,
            "conservative_cost_usd": "0.1",
            "usage_complete": False,
            "terminal_error_category": "model_api_error",
        },
    }
    task = {
        "task_id": "task-1",
        "instruction": "Create report.txt",
        "occupation": "Analyst",
        "reference_files": [],
        "needs_files": True,
    }
    condition = {
        "prompt": {
            "system": "system", "prefix": None, "body": None, "suffix": None,
        },
        "preprocessors": [],
    }

    result = step2._execute_single_task(
        task,
        condition,
        executor,
        "agentic_sandbox",
        None,
        "model",
        strict_inputs=True,
        experiment_id="exp030",
        run_id="paired-run",
        condition_name="treatment",
    )

    assert result["status"] == "error"
    assert result["deliverable_files"] == []
    assert result["failure_evidence"]["artifact_count"] == 1
    evidence_dir = evidence_root.parent / result["failure_evidence"]["root"]
    assert (evidence_dir / "artifacts" / "report.txt").read_bytes() == b"verified"
    manifest = json.loads(
        (evidence_dir / ".evidence" / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["sha256"] == result["failure_evidence"]["sha256"]


def test_failure_evidence_metadata_cannot_overwrite_same_named_artifact(
    tmp_path, monkeypatch
):
    evidence_root = tmp_path / "batch-output"
    monkeypatch.setattr(step2, "BATCH_OUTPUT_DIR", evidence_root)

    result = step2._save_hardened_failure_evidence(
        [{"filename": "evidence-manifest.json", "content": b"user artifact"}],
        experiment_id="exp030",
        run_id="paired-run-collision",
        condition_identity="treatment",
        task_id="task-collision",
    )

    evidence_dir = evidence_root.parent / result["root"]
    artifact = evidence_dir / "artifacts" / "evidence-manifest.json"
    metadata = evidence_dir / ".evidence" / "manifest.json"
    assert artifact.read_bytes() == b"user artifact"
    document = json.loads(metadata.read_text(encoding="utf-8"))
    assert document["artifacts"][0]["sha256"] == hashlib.sha256(
        b"user artifact"
    ).hexdigest()
    assert hashlib.sha256(artifact.read_bytes()).hexdigest() == document[
        "artifacts"
    ][0]["sha256"]


def test_baseline_budget_observability_uses_strict_allowlist():
    secret = "/private/ledger.sqlite3"
    observed = step2._build_execution_observability({
        "budget_metrics": {
            "schema_version": "1.0",
            "model_api_calls": 2,
            "input_tokens": 100,
            "output_tokens": 20,
            "cached_tokens": 5,
            "conservative_cost_usd": "0.5",
            "usage_complete": True,
            "ledger_path": secret,
        }
    }, [])

    assert observed["budget_metrics"] == {
        "schema_version": "1.0",
        "model_api_calls": 2,
        "input_tokens": 100,
        "output_tokens": 20,
        "cached_tokens": 5,
        "conservative_cost_usd": 0.5,
        "usage_complete": True,
    }
    assert secret not in str(observed)


def test_substrate_observability_keeps_hashes_and_drops_paths():
    secret = "/private/seccomp.json"
    manifest = {
        "schema_version": "1.0",
        "sha256": "a" * 64,
        "task_image": "image@sha256:" + "b" * 64,
        "task_image_id": "sha256:" + "c" * 64,
        "verifier_image": "image@sha256:" + "b" * 64,
        "verifier_image_id": "sha256:" + "c" * 64,
        "component_sha256": {
            "python_launcher": "d" * 64,
            "ffmpeg_mapper": "e" * 64,
            "verifier": "f" * 64,
            "outer_seccomp": "1" * 64,
            "capabilities": "2" * 64,
            "core_tree": "4" * 64,
        },
        "sbom_sha256": "3" * 64,
        "uid": 65532,
        "gid": 65532,
        "network": "none",
        "ipc": "none",
        "pid_namespace": "private",
        "read_only_rootfs": True,
        "cap_drop": ["ALL"],
        "no_new_privileges": True,
        "selected_transfer_bytes": 256 * 1024 * 1024,
        "memory_bytes": 8 * 1024 * 1024 * 1024,
        "memory_swap_bytes": 8 * 1024 * 1024 * 1024,
        "cpus": 2,
        "pids": 128,
        "nofile": 256,
        "apparmor_profile": "gdpval-agentic",
        "work_tmpfs": {
            "size_bytes": 512 * 1024 * 1024,
            "nr_inodes": 1024,
            "nosuid": True,
            "nodev": True,
            "noexec": True,
        },
        "seccomp_path": secret,
    }

    observed = step2._build_execution_observability(
        {"substrate_manifest": manifest}, []
    )

    assert observed["substrate"]["sha256"] == "a" * 64
    assert observed["substrate"]["memory_bytes"] == 8 * 1024 * 1024 * 1024
    assert secret not in str(observed)