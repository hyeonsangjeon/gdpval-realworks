from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import textwrap
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path

import step2_run_inference as step2
from core.agentic_sandbox_runner import AgenticLimits
from core.agentic_tools import responses_tool_definitions
from core.executor import TaskExecutor
from core.experiment_config import ExperimentConfig
from core.result_fingerprint import inference_result_fingerprint


V1_PROMPT_SHA256 = "58ad33a5cf7169a224dd973be2c6b5554933c8ee8232720be4edfd26ef28547c"
V1_TOOLS_SHA256 = "383c5f730237960cbfa7e0646d50e51f2468e7f6c63eac2b5225fe95ecad99c2"
V1_CHECKPOINT_SHA256 = "54eceac55422e151f08032ad70ff4ef451b90ec31b3d013216f5cee7b5bcff43"
V1_RESULT_FINGERPRINT = "b05aabba5ca21eb62de4a4bd6faf803425dec7650dd8a7e45f7faa0de5188718"


def test_v1_agentic_prompt_and_tool_contract_identity_is_frozen():
    prompt = Path("prompts/agentic_sandbox_solver.yaml").read_bytes()
    tools = json.dumps(
        responses_tool_definitions(),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    assert hashlib.sha256(prompt).hexdigest() == V1_PROMPT_SHA256
    assert hashlib.sha256(tools).hexdigest() == V1_TOOLS_SHA256


def test_v1_agentic_default_limits_are_frozen():
    assert asdict(AgenticLimits()) == {
        "max_api_attempts": 6,
        "max_model_iterations": 6,
        "max_output_tokens": 8192,
        "max_input_tokens": 300000,
        "max_cumulative_output_tokens": 32768,
        "max_task_seconds": 1200,
        "max_cost_usd": Decimal("1.25"),
        "max_tool_calls": 8,
        "max_run_python": 4,
        "max_run_ffmpeg": 2,
        "max_inspect_artifacts": 4,
        "max_finalize": 2,
        "max_identical_errors": 2,
    }


def test_v1_agentic_checkpoint_and_result_manifest_identity_is_frozen(tmp_path):
    result = _v1_result_fixture()
    checkpoint = tmp_path / "progress.json"
    step2._save_progress(
        "exp-v1-identity",
        "V1 Agentic",
        "agentic_sandbox",
        1,
        [result],
        "2026-07-27T12:00:00+00:00",
        checkpoint,
        run_id="run-v1-identity",
        condition_identity="condition_a",
        ordered_task_ids=["task-v1"],
        prepared_fingerprint="e" * 64,
        resume_round=0,
    )

    assert hashlib.sha256(checkpoint.read_bytes()).hexdigest() == (
        V1_CHECKPOINT_SHA256
    )
    restored = step2._load_and_validate_progress(
        checkpoint,
        experiment_id="exp-v1-identity",
        condition_name="V1 Agentic",
        condition_identity="condition_a",
        run_id="run-v1-identity",
        execution_mode="agentic_sandbox",
        ordered_task_ids=["task-v1"],
        prepared_fingerprint="e" * 64,
        allow_missing_results=False,
    )
    restored_checkpoint = tmp_path / "restored-progress.json"
    step2._save_progress(
        "exp-v1-identity",
        "V1 Agentic",
        "agentic_sandbox",
        1,
        restored["results"],
        restored["started_at"],
        restored_checkpoint,
        run_id="run-v1-identity",
        condition_identity="condition_a",
        ordered_task_ids=["task-v1"],
        prepared_fingerprint="e" * 64,
        resume_round=restored["resume_round"],
    )
    assert restored_checkpoint.read_bytes() == checkpoint.read_bytes()

    final_result = dict(result)
    final_result["deliverable_file_records"] = [{
        "path": "deliverable_files/task-v1/report.txt",
        "sha256": hashlib.sha256(b"fixed v1 report\n").hexdigest(),
        "size": 16,
    }]
    manifest = {
        "experiment_id": "exp-v1-identity",
        "publication_generation": "generation-v1",
        "experiment_name": "V1 identity fixture",
        "source": "fixture/gdpval",
        "condition": "V1 Agentic",
        "condition_identity": "condition_a",
        "run_id": "run-v1-identity",
        "execution_mode": "agentic_sandbox",
        "ordered_task_ids": ["task-v1"],
        "prepared_fingerprint": "e" * 64,
        "model": "v1-model",
        "started_at": "2026-07-27T12:00:00+00:00",
        "completed_at": "2026-07-27T12:01:00+00:00",
        "resume_rounds_used": 0,
        "summary": {"total": 1, "success": 1, "error": 0, "qa_failed": 0},
        "results": [final_result],
    }

    assert inference_result_fingerprint(manifest) == V1_RESULT_FINGERPRINT


def test_v1_import_and_default_config_do_not_require_v2_modules():
    script = textwrap.dedent("""
        import builtins
        original_import = builtins.__import__

        def guarded_import(name, *args, **kwargs):
            if name.startswith("core.agentic_v2"):
                raise ImportError("v2 intentionally unavailable")
            return original_import(name, *args, **kwargs)

        builtins.__import__ = guarded_import
        from core.executor import TaskExecutor
        from core.experiment_config import ExperimentConfig

        config = ExperimentConfig.from_dict({
            "experiment": {"id": "exp001", "name": "legacy"},
            "data": {"source": "openai/gdpval"},
            "condition_a": {
                "name": "legacy",
                "model": {"provider": "azure", "deployment": "model"},
                "prompt": {"system": "system"},
            },
        })
        assert config.execution.mode == "subprocess"
        assert TaskExecutor.recommend_mode("azure") == "code_interpreter"
    """)

    subprocess.run([sys.executable, "-c", script], check=True)


def test_v2_is_never_selected_by_legacy_defaults_or_recommendations():
    config = ExperimentConfig.from_dict({
        "experiment": {"id": "exp001", "name": "Legacy default"},
        "data": {"source": "openai/gdpval"},
        "condition_a": {
            "name": "Default",
            "model": {"provider": "azure", "deployment": "model"},
            "prompt": {"system": "system"},
        },
    })

    assert config.execution.mode == "subprocess"
    assert config.execution.agentic_v2 is None
    assert TaskExecutor.recommend_mode("azure", "tool_assisted") == "code_interpreter"
    assert TaskExecutor.recommend_mode("openai", "tool_assisted") == "subprocess"
    assert TaskExecutor.recommend_mode("anthropic", "portable") == "json_renderer"


def _v1_result_fixture() -> dict:
    components = {
        name: str(index) * 64
        for index, name in enumerate((
            "python_launcher",
            "ffmpeg_mapper",
            "verifier",
            "outer_seccomp",
            "capabilities",
            "core_tree",
        ), 1)
    }
    observability = step2._build_execution_observability({
        "agentic_metrics": {
            "ledger_cumulative": True,
            "model_api_calls": 2,
            "model_iterations": 2,
            "tool_calls": 2,
            "tool_errors": 0,
            "tool_calls_by_name": {"run_python": 1, "finalize": 1},
            "task_wall_time_ms": 250,
            "finalize_attempts": 1,
            "input_tokens": 1000,
            "output_tokens": 250,
            "cached_tokens": 100,
            "usage_complete": True,
            "terminal_error_category": None,
            "conservative_cost_usd": "0.125",
        },
        "substrate_manifest": {
            "sha256": "a" * 64,
            "task_image": f"task@sha256:{'b' * 64}",
            "task_image_id": f"sha256:{'b' * 64}",
            "verifier_image": f"verifier@sha256:{'c' * 64}",
            "verifier_image_id": f"sha256:{'c' * 64}",
            "component_sha256": components,
            "sbom_sha256": "d" * 64,
            "uid": 1000,
            "gid": 1000,
            "network": "none",
            "ipc": "private",
            "pid_namespace": "private",
            "read_only_rootfs": True,
            "cap_drop": ["ALL"],
            "no_new_privileges": True,
        },
    }, [])
    return {
        "task_id": "task-v1",
        "status": "success",
        "content": "completed",
        "deliverable_text": "report ready",
        "deliverable_files": ["deliverable_files/task-v1/report.txt"],
        "model": "v1-model",
        "usage": {"input_tokens": 1000, "output_tokens": 250},
        "observability": observability,
        "latency_ms": 250.0,
        "timestamp": "2026-07-27T12:00:00+00:00",
    }