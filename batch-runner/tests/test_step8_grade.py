import json
import os
from pathlib import Path
import re
import subprocess
import sys

import pytest
import yaml

import step8_grade as s8
from core.cost_receipts import CostReceipt


INFERENCE_SHA = "a" * 40
_SENSITIVE_CLEANUP_DETAIL = (
    "https://private.services.ai.azure.com/ deployment=secret"
)


@pytest.fixture(autouse=True)
def _typed_azure_ai_route(monkeypatch):
    for name in (
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_API_KEY",
        "AZURE_API_KEY",
        "AZURE_OPENAI_AD_TOKEN",
        "AZURE_CLIENT_SECRET",
        "OPENAI_API_KEY",
        "FOUNDRY_PROJECT_ENDPOINT",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AZURE_AI_ROUTE_PROFILE", "direct-v1")
    monkeypatch.setenv(
        "AZURE_OPENAI_V1_ENDPOINT",
        "https://test-account.services.ai.azure.com/openai/v1/",
    )


class _FakeLoader:
    def __init__(self, *args, **kwargs):
        self.rubric_sha = "11e7900cdcac61bc4daf59e65feb238acda98fbf"
        self.rubric_short_sha = "11e7900"

    def load(self, task_id):
        from core.rubric_loader import RubricItem, TaskRubric

        return TaskRubric(
            task_id=task_id,
            sector="s",
            occupation="o",
            prompt="p",
            rubric_items=[RubricItem("ri-1", "file basename is 'Sample'", 2, None)],
            rubric_pretty="",
            reference_files=[],
            gold_deliverable_files=[],
        )


class _FakeGrader:
    prompt_version = "v1"

    def __init__(self, config, rubric_loader, cost_recorder=None):
        self.calls = 0
        self.cost_recorder = cost_recorder
        self.runtime_fingerprint = config["_runtime"][
            "azure_ai_runtime_fingerprint"
        ]

    def grade_task(self, task, deliverable_dir):
        from core.grader import ItemGrade, TaskGrade

        self.calls += 1
        return TaskGrade(
            task_id=task.task_id,
            sector=task.sector,
            occupation=task.occupation,
            items=[
                ItemGrade(
                    rubric_item_id="ri-1",
                    criterion="c",
                    max_score=2,
                    awarded_score=2,
                    verdict="pass",
                    decided_by="precheck",
                    required=None,
                    evidence="ok",
                    precheck_pattern_id="file_exists_or_name",
                )
            ],
            total_awarded=2,
            total_max=2,
            pct=100,
            critical_fail=False,
            gold_referenced=False,
            judge_call_count=0,
            precheck_count=1,
            judge_total_latency_ms=0,
            judge_input_tokens=0,
            judge_output_tokens=0,
            error=None,
        )


def test_task_serialization_persists_measured_wall_time():
    config = {"_runtime": {"azure_ai_runtime_fingerprint": "f" * 64}}
    grader = _FakeGrader(config, rubric_loader=None)
    grade = grader.grade_task(_FakeLoader().load("task-001"), "unused")

    row = s8._task_to_dict(grade, grading_wall_time_ms=1234.5)

    assert row["grading_wall_time_ms"] == 1234.5


def test_compute_summary_includes_perception_in_total_cost_volume():
    task = {
        "pct": 50.0,
        "error": None,
        "items": [],
        "judge_call_count": 2,
        "judge_input_tokens": 100,
        "judge_output_tokens": 20,
        "judge_cached_tokens": 10,
        "judge_total_latency_ms": 40.0,
        "perception_call_count": 3,
        "perception_input_tokens": 60,
        "perception_output_tokens": 15,
        "perception_cached_tokens": 6,
        "perception_total_latency_ms": 30.0,
        "render_call_count": 3,
        "render_total_latency_ms": 12.0,
        "usage_complete": True,
    }

    cost = s8._compute_summary(
        [task],
        unpriced_models=["gpt-5.6-sol", "gpt-audio-1.5"],
    )["cost"]

    assert cost["total_judge_calls"] == 5
    assert cost["total_main_judge_calls"] == 2
    assert cost["total_perception_calls"] == 3
    assert cost["total_input_tokens"] == 160
    assert cost["total_output_tokens"] == 35
    assert cost["total_cached_tokens"] == 16
    assert cost["main_input_tokens"] == 100
    assert cost["perception_input_tokens"] == 60
    assert cost["total_judge_latency_sec"] == 0.07
    assert cost["total_render_calls"] == 3
    assert cost["total_render_latency_sec"] == 0.01
    assert cost["usage_complete"] is True
    assert cost["estimated_cost_usd"] is None
    assert cost["pricing_complete"] is False
    assert cost["unpriced_models"] == ["gpt-5.6-sol", "gpt-audio-1.5"]


def _setup_workspace(tmp_path: Path):
    (tmp_path / "experiments").mkdir(parents=True, exist_ok=True)
    (tmp_path / "workspace").mkdir(parents=True, exist_ok=True)
    (tmp_path / "prompts").mkdir(parents=True, exist_ok=True)
    (tmp_path / "grading_configs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "schemas").mkdir(parents=True, exist_ok=True)
    (tmp_path / "core").mkdir(parents=True, exist_ok=True)
    (tmp_path / "scripts").mkdir(parents=True, exist_ok=True)
    (tmp_path / "step8_grade.py").write_text("# test step8\n", encoding="utf-8")
    (tmp_path / "core" / "grader.py").write_text("# test core\n", encoding="utf-8")
    (tmp_path / "requirements.txt").write_text("PyYAML\n", encoding="utf-8")
    (tmp_path / "scripts" / "download_inference_from_hf.py").write_text(
        "# test downloader\n", encoding="utf-8"
    )

    exp = {
        "experiment": {"id": "exp998_smoke_baseline_sample", "name": "x", "description": "", "author": "a", "created_at": "2026-01-01"},
        "control": {"fixed": [], "changed": []},
        "data": {"source": "owner/repo", "filter": {"sample_size": 3}},
        "condition_a": {
            "name": "A",
            "model": {"provider": "azure", "deployment": "gpt-5.2-chat"},
            "prompt": {"system": "x"},
        },
    }
    (tmp_path / "experiments" / "exp998_smoke_baseline_sample.yaml").write_text(yaml.safe_dump(exp), encoding="utf-8")

    inf = {
        "experiment_id": "exp998_smoke_baseline_sample",
        "source_repo_id": "owner/repo",
        "source_revision": INFERENCE_SHA,
        "model": "gpt-5.2-chat",
        "completed_at": "2026-05-20T00:00:00Z",
        "results": [
            {"task_id": "task-001", "deliverable_files": ["deliverable_files/task-001/Sample.xlsx"]},
            {"task_id": "task-002", "deliverable_files": ["deliverable_files/task-002/Sample.xlsx"]},
            {"task_id": "task-003", "deliverable_files": ["deliverable_files/task-003/Sample.xlsx"]},
        ],
    }
    (tmp_path / "workspace" / "step2_inference_results.json").write_text(json.dumps(inf), encoding="utf-8")
    for task in inf["results"]:
        for relative_path in task["deliverable_files"]:
            deliverable = tmp_path / "workspace" / "upload" / relative_path
            deliverable.parent.mkdir(parents=True, exist_ok=True)
            deliverable.write_bytes(b"test deliverable")

    (tmp_path / "prompts" / "grader_judge.md").write_text("<!-- prompt_version: v1 -->\n{{#each deliverable_files}}{{/each}}", encoding="utf-8")
    (tmp_path / "prompts" / "grader_judge_v2.md").write_text(
        "<!-- prompt_version: v2 -->\n{{#each deliverable_files}}{{/each}}",
        encoding="utf-8",
    )
    cfg = {
        "schema_version": "1.0",
        "config_name": "default_gpt5pro",
        "judge": {"provider": "azure_openai", "api": "responses", "model": "gpt-5.4-pro", "deployment": "gpt-5.4-pro", "api_version": "2025-04-01-preview"},
        "rubric": {"source": "huggingface", "repo_id": "openai/gdpval", "revision": "main", "cache_dir": "data/gdpval-local"},
        "prompt": {"template": "prompts/grader_judge.md", "version": "v1"},
        "output": {"directory": "data/grades", "filename_template": "{exp_id}__{judge_slug}__{rubric_short_sha}__{prompt_v}.json", "partial_save_every_n_tasks": 10},
        "tpm_guard": {"max_concurrent": 1, "min_delay_ms_between_calls": 0, "retry_on_429": {"enabled": False}},
    }
    (tmp_path / "grading_configs" / "default.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")

    # Reuse repo schema
    schema_src = Path("schemas/grade.schema.json").read_text(encoding="utf-8")
    (tmp_path / "schemas" / "grade.schema.json").write_text(schema_src, encoding="utf-8")


def _diagnostic_grade_path(tmp_path: Path, task_ids: list[str]) -> Path:
    return (
        tmp_path
        / "data/grades/_diagnostic"
        / s8._ordered_task_ids_sha256(task_ids)
        / "exp998_smoke_baseline_sample__gpt-5_4-pro__11e7900__v1.json"
    )


_RENDERER_FINGERPRINT = {
    "libreoffice_binary": "soffice",
    "libreoffice_version": "LibreOffice 24.2.7.2",
    "pymupdf_version": "1.26.3",
}


def _configure_track2(tmp_path: Path) -> None:
    config_path = tmp_path / "grading_configs" / "default.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["schema_version"] = "2.0"
    config["judge"]["tools"] = {
        "read_deliverable": {"ops": ["inspect_structure"]}
    }
    config["judge"]["perception"] = {
        "visual": {"model": "gpt-5.4", "vision": True}
    }
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")


def test_compute_grader_source_hash_is_deterministic_and_content_sensitive(
    monkeypatch, tmp_path
):
    _setup_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    config_path = tmp_path / "grading_configs" / "default.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    first = s8.compute_grader_source_hash(config_path, config)
    second = s8.compute_grader_source_hash(config_path, config)
    assert first == second
    assert len(first) == 64

    (tmp_path / "unrelated.txt").write_text("not grading source\n", encoding="utf-8")
    assert s8.compute_grader_source_hash(config_path, config) == first

    (tmp_path / "core" / "grader.py").write_text(
        "# changed test core\n", encoding="utf-8"
    )
    assert s8.compute_grader_source_hash(config_path, config) != first


def test_renderer_requirement_accepts_deployment_only_visual_config():
    config = {
        "schema_version": "2.0",
        "judge": {
            "tools": {"read_deliverable": {"ops": ["render_page"]}},
            "perception": {
                "visual": {"deployment": "vision-deployment"},
            },
        },
    }

    assert s8.requires_track2_office_renderer(config) is True


def test_compute_grader_source_hash_changes_when_source_path_changes(
    monkeypatch, tmp_path
):
    _setup_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    config_path = tmp_path / "grading_configs" / "default.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    first = s8.compute_grader_source_hash(config_path, config)

    renamed = tmp_path / "prompts" / "renamed.md"
    renamed.write_bytes((tmp_path / "prompts" / "grader_judge.md").read_bytes())
    config["prompt"]["template"] = "prompts/renamed.md"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")

    assert s8.compute_grader_source_hash(config_path, config) != first


def test_track2_fallback_tool_prompt_is_in_grader_source_hash(
    monkeypatch, tmp_path
):
    _setup_workspace(tmp_path)
    _configure_track2(tmp_path)
    monkeypatch.chdir(tmp_path)
    config_path = tmp_path / "grading_configs" / "default.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert "tool_template" not in config["prompt"]

    first = s8.compute_grader_source_hash(config_path, config)
    fallback = tmp_path / "prompts" / "grader_judge_v2.md"
    fallback.write_text("<!-- prompt_version: v2-changed -->\n", encoding="utf-8")

    assert s8.compute_grader_source_hash(config_path, config) != first


def test_compute_grader_source_hash_rejects_symlink(monkeypatch, tmp_path):
    _setup_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    config_path = tmp_path / "grading_configs" / "default.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    prompt_path = tmp_path / "prompts" / "grader_judge.md"
    target = tmp_path / "prompts" / "target.md"
    target.write_bytes(prompt_path.read_bytes())
    prompt_path.unlink()
    prompt_path.symlink_to(target)

    with pytest.raises(ValueError, match="symlink"):
        s8.compute_grader_source_hash(config_path, config)


def test_compute_grader_source_hash_accepts_repository_generated_config(
    monkeypatch, tmp_path
):
    _setup_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "grading_configs/default.yaml"
    config = yaml.safe_load(source.read_text(encoding="utf-8"))
    generated_dir = tmp_path.parent / f"{tmp_path.name}-generated-config"
    generated_dir.mkdir()
    generated = generated_dir / "config.yaml"
    generated.write_bytes(source.read_bytes())

    first = s8.compute_grader_source_hash(generated, config)
    config["description"] = "changed"
    generated.write_text(yaml.safe_dump(config), encoding="utf-8")
    second = s8.compute_grader_source_hash(generated, config)

    assert len(first) == 64
    assert second != first


def test_compute_grader_source_hash_rejects_symlinked_generated_config(
    monkeypatch, tmp_path
):
    _setup_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "grading_configs/default.yaml"
    config = yaml.safe_load(source.read_text(encoding="utf-8"))
    generated_dir = tmp_path.parent / f"{tmp_path.name}-symlinked-config"
    generated_dir.mkdir()
    target = generated_dir / "target.yaml"
    target.write_bytes(source.read_bytes())
    generated = generated_dir / "config.yaml"
    generated.symlink_to(target)

    with pytest.raises(ValueError, match="symlink"):
        s8.compute_grader_source_hash(generated, config)


def test_compute_grader_source_hash_rejects_outside_and_duplicate_paths(
    monkeypatch, tmp_path
):
    _setup_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    config_path = tmp_path / "grading_configs" / "default.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    outside = tmp_path.parent / f"{tmp_path.name}-outside-prompt.md"
    outside.write_text("outside\n", encoding="utf-8")
    config["prompt"]["template"] = str(outside)
    with pytest.raises(ValueError, match="outside batch-runner"):
        s8.compute_grader_source_hash(config_path, config)

    config["prompt"]["template"] = "prompts/grader_judge.md"
    config["prompt"]["tool_template"] = "prompts/grader_judge.md"
    with pytest.raises(ValueError, match="duplicate grader source path"):
        s8.compute_grader_source_hash(config_path, config)


def test_v1_source_repo_fallback_does_not_apply_to_track2():
    inference = {"source": "legacy/repo"}

    assert s8.source_inference_repo_id(inference, "1.0") == "legacy/repo"
    assert s8.source_inference_repo_id(inference, "2.0") is None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_repo_id", None),
        ("source_repo_id", "owner/repo/extra"),
        ("source_revision", None),
        ("source_revision", "A" * 40),
        ("source_revision", "a" * 39),
    ],
)
def test_track2_rejects_missing_or_invalid_inference_identity_before_grader(
    monkeypatch, tmp_path, field, value
):
    _setup_workspace(tmp_path)
    _configure_track2(tmp_path)
    inference_path = tmp_path / "workspace" / "step2_inference_results.json"
    inference = json.loads(inference_path.read_text(encoding="utf-8"))
    if value is None:
        inference.pop(field)
    else:
        inference[field] = value
    inference_path.write_text(json.dumps(inference), encoding="utf-8")
    experiment_path = (
        tmp_path / "experiments" / "exp998_smoke_baseline_sample.yaml"
    )
    experiment = yaml.safe_load(experiment_path.read_text(encoding="utf-8"))
    experiment["data"]["filter"]["sample_size"] = 10
    experiment_path.write_text(yaml.safe_dump(experiment), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)

    class _NeverConstruct:
        def __init__(self, *args, **kwargs):
            pytest.fail("Grader must not be constructed for invalid inference identity")

    monkeypatch.setattr(s8, "Grader", _NeverConstruct)
    monkeypatch.setattr("sys.argv", [
        "step8_grade.py", "exp998_smoke_baseline_sample",
        "--config", "grading_configs/default.yaml", "--force",
    ])

    assert s8.main() != 0


def test_skip_when_grade_exists(monkeypatch, tmp_path):
    _setup_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    monkeypatch.setattr(s8, "Grader", _FakeGrader)

    _seed_partial_grade(
        tmp_path,
        ["task-001", "task-002", "task-003"],
        run_status="final",
    )

    monkeypatch.setattr("sys.argv", ["step8_grade.py", "exp998_smoke_baseline_sample", "--config", "grading_configs/default.yaml"])
    code = s8.main()
    assert code == 0


def test_force_overwrites(monkeypatch, tmp_path):
    _setup_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    monkeypatch.setattr(s8, "Grader", _FakeGrader)

    out = tmp_path / "data/grades/exp998_smoke_baseline_sample__gpt-5_4-pro__11e7900__v1.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("{}", encoding="utf-8")

    monkeypatch.setattr("sys.argv", ["step8_grade.py", "exp998_smoke_baseline_sample", "--config", "grading_configs/default.yaml", "--force"])
    code = s8.main()
    assert code == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "1.4"
    assert all(
        isinstance(task["grading_wall_time_ms"], (int, float))
        and task["grading_wall_time_ms"] >= 0
        for task in payload["tasks"]
    )


def test_main_preflight_matches_grader_transport_before_calls(
    monkeypatch, tmp_path
):
    _setup_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    fingerprint = "f" * 64
    captured = {}

    class RouteBoundGrader(_FakeGrader):
        runtime_fingerprint = fingerprint

    def preflight(workloads, **kwargs):
        captured["workloads"] = workloads
        captured["options"] = kwargs
        return [{
            "endpoint_kind": "direct-v1",
            "profile": "direct-v1",
            "runtime_fingerprint": fingerprint,
            "workload": "grader",
        }]

    monkeypatch.setattr(s8, "Grader", RouteBoundGrader)
    monkeypatch.setattr(s8, "preflight_routes", preflight)
    monkeypatch.setattr("sys.argv", [
        "step8_grade.py",
        "exp998_smoke_baseline_sample",
        "--config",
        "grading_configs/default.yaml",
        "--force",
    ])

    assert s8.main() == 0
    assert captured["options"] == {
        "timeout": 600,
        "legacy_api_version": "2025-04-01-preview",
    }
    assert [
        (workload.value, deployment)
        for workload, deployment in captured["workloads"]
    ] == [("grader", "gpt-5.4-pro")]


@pytest.mark.parametrize("runtime_fingerprint", [None, "b" * 64])
def test_main_rejects_missing_or_secondary_grader_fingerprint(
    monkeypatch, tmp_path, runtime_fingerprint
):
    _setup_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    closed = []

    class UnboundGrader:
        def __init__(self, config, rubric_loader, cost_recorder=None):
            self.runtime_fingerprint = runtime_fingerprint

        def close(self):
            closed.append(True)

    monkeypatch.setattr(s8, "Grader", UnboundGrader)
    monkeypatch.setattr(s8, "preflight_routes", lambda *_args, **_kwargs: [
        {
            "endpoint_kind": "direct-v1",
            "profile": "direct-v1",
            "runtime_fingerprint": "a" * 64,
            "workload": "grader",
        },
        {
            "endpoint_kind": "direct-v1",
            "profile": "direct-v1",
            "runtime_fingerprint": "b" * 64,
            "workload": "grader",
        },
    ])
    monkeypatch.setattr("sys.argv", [
        "step8_grade.py",
        "exp998_smoke_baseline_sample",
        "--config",
        "grading_configs/default.yaml",
        "--force",
    ])

    assert s8.main() == 4
    assert closed == [True]


def test_judge_initialization_error_is_class_only(
    monkeypatch, tmp_path, capsys
):
    _setup_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)

    class FailingGrader:
        def __init__(self, *args, **kwargs):
            raise RuntimeError(_SENSITIVE_CLEANUP_DETAIL)

    monkeypatch.setattr(s8, "Grader", FailingGrader)
    monkeypatch.setattr("sys.argv", [
        "step8_grade.py",
        "exp998_smoke_baseline_sample",
        "--config",
        "grading_configs/default.yaml",
        "--force",
    ])

    assert s8.main() == 4
    stderr = capsys.readouterr().err
    assert "provider_error:RuntimeError" in stderr
    assert _SENSITIVE_CLEANUP_DETAIL not in stderr


def test_cleanup_failure_preserves_final_exit_and_payload(
    monkeypatch, tmp_path, capsys
):
    _setup_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)

    class CloseFailureGrader(_FakeGrader):
        def close(self):
            raise OSError(_SENSITIVE_CLEANUP_DETAIL)

    monkeypatch.setattr(s8, "Grader", CloseFailureGrader)
    monkeypatch.setattr("sys.argv", [
        "step8_grade.py",
        "exp998_smoke_baseline_sample",
        "--config",
        "grading_configs/default.yaml",
        "--force",
    ])

    assert s8.main() == 0
    out = (
        tmp_path
        / "data/grades/exp998_smoke_baseline_sample__gpt-5_4-pro__"
        "11e7900__v1.json"
    )
    assert out.is_file()
    stderr = capsys.readouterr().err
    assert "provider_error:OSError" in stderr
    assert _SENSITIVE_CLEANUP_DETAIL not in stderr


def test_dry_run_no_llm_calls(monkeypatch, tmp_path):
    _setup_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)

    class _NoInitGrader:
        @staticmethod
        def _classify(item):
            return "precheck", "file_exists_or_name"

    monkeypatch.setattr(s8, "Grader", _NoInitGrader)

    monkeypatch.setattr("sys.argv", ["step8_grade.py", "exp998_smoke_baseline_sample", "--config", "grading_configs/default.yaml", "--dry-run"])
    code = s8.main()
    assert code == 0


def test_limit_n_tasks(monkeypatch, tmp_path):
    _setup_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)

    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    monkeypatch.setattr(s8, "Grader", _FakeGrader)

    monkeypatch.setattr("sys.argv", ["step8_grade.py", "exp998_smoke_baseline_sample", "--config", "grading_configs/default.yaml", "--force", "--limit", "2"])
    code = s8.main()
    assert code == 0

    out = _diagnostic_grade_path(tmp_path, ["task-001", "task-002"])
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert len(payload["tasks"]) == 2
    assert payload["run_status"] == "diagnostic"


def test_legacy_missing_provenance_full_run_stays_diagnostic(
    monkeypatch, tmp_path
):
    _setup_workspace(tmp_path)
    inference_path = tmp_path / "workspace/step2_inference_results.json"
    inference = json.loads(inference_path.read_text(encoding="utf-8"))
    inference["azure_ai_provenance_status"] = "legacy-missing"
    inference_path.write_text(json.dumps(inference), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    monkeypatch.setattr(s8, "Grader", _FakeGrader)
    monkeypatch.setattr("sys.argv", [
        "step8_grade.py",
        "exp998_smoke_baseline_sample",
        "--config",
        "grading_configs/default.yaml",
        "--force",
    ])

    assert s8.main() == 0

    task_ids = ["task-001", "task-002", "task-003"]
    payload = json.loads(
        _diagnostic_grade_path(tmp_path, task_ids).read_text(encoding="utf-8")
    )
    assert payload["run_status"] == "diagnostic"
    assert payload["source_azure_ai_provenance_status"] == "legacy-missing"


def test_legacy_missing_provenance_publishes_when_corpus_is_pinned_complete(
    monkeypatch, tmp_path
):
    """A pre-sidecar inference is publishable once the whole corpus is pinned.

    The sidecar records how the inference was routed. The judge never reads it —
    only deliverables, rubric, and prompts reach the model — so losing it costs
    an audit trail, not a graded task. What the run still has to prove is that
    nothing was quietly dropped, and a complete pin in canonical order proves
    exactly that. The gap stays on the record either way.
    """
    _setup_workspace(tmp_path)
    inference_path = tmp_path / "workspace/step2_inference_results.json"
    inference = json.loads(inference_path.read_text(encoding="utf-8"))
    inference["azure_ai_provenance_status"] = "legacy-missing"
    inference_path.write_text(json.dumps(inference), encoding="utf-8")

    task_ids = ["task-001", "task-002", "task-003"]
    config_path = tmp_path / "grading_configs" / "default.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["schema_version"] = "2.0"
    config["rubric"]["revision"] = _FakeLoader().rubric_sha
    config["rerun_identity"] = {
        "experiment_id": "exp998_smoke_baseline_sample",
        "expected_task_count": len(task_ids),
        "rubric_commit_sha": _FakeLoader().rubric_sha,
        "inference_revision": INFERENCE_SHA,
        "task_ids": task_ids,
        "allow_legacy_missing_provenance": True,
    }
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    monkeypatch.setattr(s8, "Grader", _FakeGrader)
    monkeypatch.setattr("sys.argv", [
        "step8_grade.py",
        "exp998_smoke_baseline_sample",
        "--config",
        "grading_configs/default.yaml",
        "--force",
    ])

    assert s8.main() == 0

    assert not (tmp_path / "data/grades/_diagnostic").exists()
    written = sorted((tmp_path / "data/grades").glob("*.json"))
    assert len(written) == 1
    payload = json.loads(written[0].read_text(encoding="utf-8"))
    assert payload["run_status"] == "final"
    assert payload["source_azure_ai_provenance_status"] == "legacy-missing"
    assert [task["task_id"] for task in payload["tasks"]] == task_ids


def test_track2_limit_three_mock_smoke(monkeypatch, tmp_path):
    _setup_workspace(tmp_path)
    _configure_track2(tmp_path)
    config_path = tmp_path / "grading_configs" / "default.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["output"]["filename_template"] = (
        "{exp_id}__{judge_slug}__{rubric_sha}__{prompt_v}.json"
    )
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    monkeypatch.setattr(s8, "Grader", _FakeGrader)
    monkeypatch.setattr(
        s8, "get_renderer_fingerprint", lambda: dict(_RENDERER_FINGERPRINT)
    )
    monkeypatch.setattr("sys.argv", [
        "step8_grade.py", "exp998_smoke_baseline_sample",
        "--config", "grading_configs/default.yaml",
        "--force", "--limit", "3",
    ])

    assert s8.main() == 0
    out = (
        tmp_path
        / "data/grades/_diagnostic"
        / s8._ordered_task_ids_sha256([
            "task-001", "task-002", "task-003"
        ])
        / (
            "exp998_smoke_baseline_sample__gpt-5_4-pro__"
            f"{_FakeLoader().rubric_sha}__v1.json"
        )
    )
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert len(payload["tasks"]) == 3
    assert payload["run_status"] == "diagnostic"
    assert payload["rubric"]["commit_sha"] == _FakeLoader().rubric_sha
    assert payload["renderer_fingerprint"] == _RENDERER_FINGERPRINT


def test_track2_incomplete_judge_error_stops_and_persists_diagnostic(
    monkeypatch, tmp_path, capsys
):
    _setup_workspace(tmp_path)
    _configure_track2(tmp_path)
    config_path = tmp_path / "grading_configs" / "default.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["output"]["filename_template"] = (
        "{exp_id}__{judge_slug}__{rubric_sha}__{prompt_v}.json"
    )
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    grader_instance = {}

    class _RuntimeFailureGrader(_FakeGrader):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            grader_instance["grader"] = self

        def grade_task(self, task, deliverable_dir):
            grade = super().grade_task(task, deliverable_dir)
            item = grade.items[0]
            item.verdict = "judge_error"
            item.decided_by = "judge"
            item.awarded_score = 0.0
            item.evidence = "BadRequestError: invalid prompt_cache_key"
            item.score_excluded = True
            item.judge_call_count = 1
            item.usage_complete = False
            grade.total_awarded = 0.0
            grade.total_max = 0
            grade.pct = 0.0
            grade.pct_raw = 0.0
            grade.judge_call_count = 1
            grade.precheck_count = 0
            grade.usage_complete = False
            return grade

        def close(self):
            raise OSError(_SENSITIVE_CLEANUP_DETAIL)

    monkeypatch.setattr(s8, "Grader", _RuntimeFailureGrader)
    monkeypatch.setattr(
        s8, "get_renderer_fingerprint", lambda: dict(_RENDERER_FINGERPRINT)
    )
    monkeypatch.setattr("sys.argv", [
        "step8_grade.py", "exp998_smoke_baseline_sample",
        "--config", "grading_configs/default.yaml", "--force",
    ])

    assert s8.main() == 6
    assert grader_instance["grader"].calls == 1
    out = (
        tmp_path
        / "data/grades"
        / (
            "exp998_smoke_baseline_sample__gpt-5_4-pro__"
            f"{_FakeLoader().rubric_sha}__v1.json"
        )
    )
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["tasks"][0]["error"] == "usage_incomplete"
    assert payload["summary"]["graded_tasks"] == 0
    assert payload["summary"]["error_tasks"] == 1
    assert payload["summary"]["openai_compat"]["avg_score_pct"] is None
    assert payload["summary"]["openai_compat"]["ci_pct"] is None
    assert payload["summary"]["openai_compat"]["perfect_count"] == 0
    assert payload["summary"]["wow"]["judge_error_rate"] == 1.0
    assert payload["summary"]["cost"]["usage_complete"] is False
    stderr = capsys.readouterr().err
    assert "provider_error:OSError" in stderr
    assert _SENSITIVE_CLEANUP_DETAIL not in stderr


def test_track2_runtime_error_allows_call_free_unscorable_selection():
    task = {
        "task_id": "task-001",
        "error": "selection_error",
        "usage_complete": True,
        "items": [{
            "verdict": "judge_error",
            "score_excluded": True,
            "evidence": "wrong_format_primary: expected PDF",
            "judge_call_count": 0,
            "perception_call_count": 0,
            "render_call_count": 0,
            "usage_complete": True,
        }],
    }

    assert s8._track2_task_runtime_error(task) is None


@pytest.mark.parametrize(
    "task",
    [
        {
            "task_id": "task-mixed",
            "error": None,
            "usage_complete": True,
            "items": [
                {
                    "verdict": "pass",
                    "score_excluded": False,
                    "usage_complete": True,
                },
                {
                    "verdict": "judge_error",
                    "score_excluded": True,
                    "judge_call_count": 1,
                    "usage_complete": True,
                },
            ],
        },
        {
            "task_id": "task-unscored",
            "error": "all_items_score_excluded",
            "usage_complete": True,
            "items": [{
                "verdict": "judge_error",
                "score_excluded": True,
                "judge_call_count": 1,
                "usage_complete": True,
            }],
        },
    ],
)
def test_track2_allows_score_excluded_judge_errors(task):
    assert s8._track2_task_runtime_error(task) is None


def test_track2_rejects_unexcluded_judge_error():
    task = {
        "task_id": "task-invalid",
        "error": None,
        "usage_complete": True,
        "items": [{
            "verdict": "judge_error",
            "score_excluded": False,
            "usage_complete": True,
        }],
    }

    assert s8._track2_task_runtime_error(task) == "invalid_score_exclusion"


def test_runtime_score_exclusion_keeps_judge_error_rate_visible():
    from core.grader import Grader, ItemGrade
    from core.rubric_loader import TaskRubric

    task = TaskRubric(
        task_id="task-001",
        sector="s",
        occupation="o",
        prompt="p",
        rubric_items=[],
        rubric_pretty="",
        reference_files=[],
        gold_deliverable_files=[],
    )
    grade = Grader._aggregate(
        [
            ItemGrade(
                rubric_item_id="pass",
                criterion="correct",
                max_score=10,
                awarded_score=10,
                verdict="pass",
                decided_by="judge",
                required=None,
                evidence="verified",
            ),
            ItemGrade(
                rubric_item_id="error",
                criterion="unresolved",
                max_score=90,
                awarded_score=0,
                verdict="judge_error",
                decided_by="judge",
                required=None,
                evidence="final_json_parse_failed",
                score_excluded=False,
            ),
        ],
        task,
    )

    summary = s8._compute_summary([s8._task_to_dict(grade)])

    assert grade.pct == 100
    assert grade.items[1].score_excluded is True
    assert summary["openai_compat"]["avg_score_pct"] == 100
    assert summary["wow"]["rubric_item_coverage_avg"] == 1.0
    assert summary["wow"]["judge_error_rate"] == 0.5


def test_judge_error_rate_uses_canonical_half_up_rounding():
    items = [
        {
            "verdict": "judge_error" if index == 0 else "pass",
            "decided_by": "judge",
            "score_excluded": index == 0,
            "model_did_right": index != 0,
            "max_score": 1,
        }
        for index in range(32)
    ]
    task = {
        "pct": 100.0,
        "error": None,
        "items": items,
        "usage_complete": True,
    }

    summary = s8._compute_summary([task])

    assert summary["wow"]["judge_error_rate"] == 0.0313


def _analytics_task(pct, sector, items, error=None):
    """Minimal task dict shaped the way ``_task_to_dict`` emits one."""
    return {
        "pct": pct,
        "error": error,
        "sector": sector,
        "items": items,
        "usage_complete": True,
    }


def _item(max_score=1, verdict="pass", did_right=True, **overrides):
    item = {
        "max_score": max_score,
        "verdict": verdict,
        "decided_by": "judge",
        "score_excluded": False,
        "model_did_right": did_right,
    }
    item.update(overrides)
    return item


def test_by_sector_task_counts_sum_to_graded_tasks():
    """The sector breakdown must account for every graded task.

    A dashboard that shows per-sector counts under a `graded_tasks` header is
    making an arithmetic promise. An errored task carries no rubric items, so
    it is excluded from the breakdown and from `graded_tasks` alike.
    """
    summary = s8._compute_summary(
        [
            _analytics_task(90.0, "Government", [_item()]),
            _analytics_task(40.0, "Government", [_item(verdict="fail")]),
            _analytics_task(60.0, "Finance and Insurance", [_item()]),
            _analytics_task(0.0, "Government", [], error="boom"),
        ]
    )

    by_sector = summary["wow"]["by_sector"]
    assert summary["total_tasks"] == 4
    assert summary["graded_tasks"] == 3
    assert sum(m["task_count"] for m in by_sector.values()) == 3
    assert by_sector["Government"]["task_count"] == 2
    assert by_sector["Government"]["avg_pct"] == 65.0
    assert by_sector["Finance and Insurance"]["task_count"] == 1


def test_by_sector_rates_roll_up_to_the_run_wide_rates():
    """One sector means the sector rates and the header rates are the same
    numbers. They are computed by the same ``_tally_item``; this pins that."""
    summary = s8._compute_summary(
        [
            _analytics_task(
                50.0,
                "Government",
                [
                    _item(max_score=10, verdict="pass", did_right=True),
                    _item(max_score=10, verdict="fail", did_right=False),
                    _item(max_score=1, verdict="pass", decided_by="precheck"),
                ],
            )
        ]
    )

    wow = summary["wow"]
    sector = wow["by_sector"]["Government"]
    for key in (
        "critical_item_pass_rate",
        "precheck_pass_rate",
        "judge_pass_rate",
    ):
        assert sector[key] == wow[key], key
    assert sector["critical_item_pass_rate"] == 0.5


def test_blank_sector_is_bucketed_rather_than_dropped():
    summary = s8._compute_summary(
        [
            _analytics_task(80.0, "   ", [_item()]),
            _analytics_task(20.0, None, [_item(verdict="fail")]),
        ]
    )

    by_sector = summary["wow"]["by_sector"]
    assert set(by_sector) == {"Unknown"}
    assert by_sector["Unknown"]["task_count"] == 2


def test_score_density_histogram_emits_every_bucket_in_frontend_order():
    """The labels and their order are a contract with ``bucketFromPct`` in
    ``src/components/wow/ScoreDensityHistogram.tsx``."""
    summary = s8._compute_summary(
        [_analytics_task(55.0, "Government", [_item()])]
    )

    histogram = summary["wow"]["score_density_histogram"]
    assert [bar["bucket"] for bar in histogram] == [
        "0-10%",
        "10-20%",
        "20-30%",
        "30-40%",
        "40-50%",
        "50-60%",
        "60-70%",
        "70-80%",
        "80-90%",
        "90-100%",
    ]
    assert sum(bar["count"] for bar in histogram) == summary["graded_tasks"]
    assert histogram[5] == {"bucket": "50-60%", "count": 1}


@pytest.mark.parametrize(
    "pct,bucket",
    [
        (0.0, "0-10%"),
        (9.999, "0-10%"),
        (10.0, "10-20%"),
        (80.0, "80-90%"),
        (89.999, "80-90%"),
        (90.0, "90-100%"),
        # 100 is the one closed edge: it belongs to the last bar rather than
        # falling off the end into an eleventh bucket.
        (100.0, "90-100%"),
    ],
)
def test_score_bucket_edges(pct, bucket):
    assert s8._score_bucket(pct) == bucket


def test_rubric_severity_curve_counts_model_did_right_not_verdict():
    """GDPVal rubrics carry negative-weight anti-criteria where a 'pass'
    verdict means the model *did* the prohibited thing. Counting raw verdicts
    would invert exactly the points this curve exists to show."""
    summary = s8._compute_summary(
        [
            _analytics_task(
                50.0,
                "Government",
                [
                    _item(max_score=-10, verdict="pass", did_right=False),
                    _item(max_score=-10, verdict="fail", did_right=True),
                    _item(max_score=5, verdict="pass", did_right=True),
                ],
            )
        ]
    )

    curve = summary["wow"]["rubric_severity_curve"]
    assert curve == [
        {"weight": -10, "n_items": 2, "pass_rate": 0.5},
        {"weight": 5, "n_items": 1, "pass_rate": 1.0},
    ]


def test_rubric_severity_curve_skips_score_excluded_items():
    summary = s8._compute_summary(
        [
            _analytics_task(
                50.0,
                "Government",
                [
                    _item(max_score=3, score_excluded=True, did_right=False),
                    _item(max_score=3),
                ],
            )
        ]
    )

    assert summary["wow"]["rubric_severity_curve"] == [
        {"weight": 3, "n_items": 1, "pass_rate": 1.0}
    ]


def test_rubric_severity_curve_omitted_when_payload_predates_sign_awareness():
    """Grades written before ``model_did_right`` existed would otherwise plot a
    flat zero line across every weight — a chart asserting a total failure that
    never happened. Emit nothing instead."""
    legacy_item = {
        "max_score": 10,
        "verdict": "pass",
        "decided_by": "judge",
        "score_excluded": False,
    }
    summary = s8._compute_summary(
        [_analytics_task(100.0, "Government", [legacy_item])]
    )

    assert summary["wow"]["rubric_severity_curve"] == []
    # The rest of the analytics still populate for a legacy payload.
    assert summary["wow"]["by_sector"]["Government"]["task_count"] == 1
    assert len(summary["wow"]["score_density_histogram"]) == 10


def test_severity_curve_ignores_unusable_weights():
    summary = s8._compute_summary(
        [
            _analytics_task(
                50.0,
                "Government",
                [
                    _item(max_score=None),
                    _item(max_score="not-a-number"),
                    _item(max_score=float("nan")),
                    _item(max_score=2.5),
                ],
            )
        ]
    )

    assert summary["wow"]["rubric_severity_curve"] == [
        {"weight": 2.5, "n_items": 1, "pass_rate": 1.0}
    ]


def test_all_score_excluded_task_has_no_headline_score():
    from core.grader import Grader, ItemGrade
    from core.rubric_loader import TaskRubric

    task = TaskRubric(
        task_id="task-001",
        sector="s",
        occupation="o",
        prompt="p",
        rubric_items=[],
        rubric_pretty="",
        reference_files=[],
        gold_deliverable_files=[],
    )
    grade = Grader._aggregate(
        [
            ItemGrade(
                rubric_item_id="error",
                criterion="unresolved",
                max_score=10,
                awarded_score=0,
                verdict="judge_error",
                decided_by="judge",
                required=None,
                evidence="empty_final_text",
            )
        ],
        task,
    )

    summary = s8._compute_summary([s8._task_to_dict(grade)])

    assert summary["graded_tasks"] == 0
    assert summary["error_tasks"] == 1
    assert summary["openai_compat"]["avg_score_pct"] is None
    assert summary["openai_compat"]["ci_pct"] is None
    assert summary["openai_compat"]["zero_count"] == 0
    assert summary["wow"]["judge_error_rate"] == 1.0


def test_all_unscored_main_completes_without_formatting_null(
    monkeypatch, tmp_path, capsys
):
    _setup_workspace(tmp_path)
    _configure_track2(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    monkeypatch.setattr(
        s8,
        "get_renderer_fingerprint",
        lambda: dict(_RENDERER_FINGERPRINT),
    )

    class _AllUnscoredGrader(_FakeGrader):
        def grade_task(self, task, deliverable_dir):
            from core.grader import ItemGrade, TaskGrade

            self.calls += 1
            return TaskGrade(
                task_id=task.task_id,
                sector=task.sector,
                occupation=task.occupation,
                items=[ItemGrade(
                    rubric_item_id="ri-1",
                    criterion="unresolved",
                    max_score=2,
                    awarded_score=0,
                    verdict="judge_error",
                    decided_by="judge",
                    required=None,
                    evidence="empty_final_text",
                    score_excluded=True,
                )],
                total_awarded=0,
                total_max=0,
                pct=0,
                critical_fail=False,
                gold_referenced=False,
                judge_call_count=0,
                precheck_count=0,
                judge_total_latency_ms=0,
                judge_input_tokens=0,
                judge_output_tokens=0,
                error="all_items_score_excluded",
            )

    monkeypatch.setattr(s8, "Grader", _AllUnscoredGrader)
    monkeypatch.setattr("sys.argv", [
        "step8_grade.py",
        "exp998_smoke_baseline_sample",
        "--config",
        "grading_configs/default.yaml",
        "--force",
    ])

    assert s8.main() == 0
    assert "avg_pct=unscored" in capsys.readouterr().out


def test_track2_incomplete_usage_is_runtime_failure():
    task = {
        "task_id": "task-001",
        "error": None,
        "usage_complete": False,
        "items": [{
            "verdict": "pass",
            "evidence": "visible chart title",
            "judge_call_count": 0,
            "perception_call_count": 1,
            "render_call_count": 1,
            "usage_complete": False,
        }],
    }

    assert s8._track2_task_runtime_error(task) == "usage_incomplete"


def test_tasks_filter(monkeypatch, tmp_path):
    _setup_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)

    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    monkeypatch.setattr(s8, "Grader", _FakeGrader)

    monkeypatch.setattr("sys.argv", [
        "step8_grade.py",
        "exp998_smoke_baseline_sample",
        "--config",
        "grading_configs/default.yaml",
        "--force",
        "--tasks",
        "task-002,task-003",
    ])
    code = s8.main()
    assert code == 0

    out = _diagnostic_grade_path(tmp_path, ["task-002", "task-003"])
    payload = json.loads(out.read_text(encoding="utf-8"))
    ids = [t["task_id"] for t in payload["tasks"]]
    assert ids == ["task-002", "task-003"]
    assert payload["run_status"] == "diagnostic"


def test_all_task_selection_flag_still_uses_diagnostic_scope(
    monkeypatch, tmp_path
):
    _setup_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    monkeypatch.setattr(s8, "Grader", _FakeGrader)
    task_ids = ["task-001", "task-002", "task-003"]
    monkeypatch.setattr("sys.argv", [
        "step8_grade.py",
        "exp998_smoke_baseline_sample",
        "--config",
        "grading_configs/default.yaml",
        "--force",
        "--tasks",
        ",".join(task_ids),
    ])

    assert s8.main() == 0

    payload = json.loads(
        _diagnostic_grade_path(tmp_path, task_ids).read_text(encoding="utf-8")
    )
    assert payload["run_status"] == "diagnostic"


@pytest.mark.parametrize(
    "argv_suffix",
    [
        ["--tasks", "task-missing"],
        ["--tasks", "task-001,task-001"],
    ],
)
def test_new_run_rejects_invalid_requested_task_ids_before_grader(
    monkeypatch, tmp_path, argv_suffix
):
    _setup_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)

    class _NeverConstruct:
        def __init__(self, *args, **kwargs):
            pytest.fail("Grader must not be constructed for invalid --tasks")

    monkeypatch.setattr(s8, "Grader", _NeverConstruct)
    monkeypatch.setattr("sys.argv", [
        "step8_grade.py", "exp998_smoke_baseline_sample",
        "--config", "grading_configs/default.yaml", "--force",
        *argv_suffix,
    ])

    assert s8.main() != 0


def test_new_run_rejects_duplicate_inference_task_ids_before_grader(
    monkeypatch, tmp_path
):
    _setup_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    inference_path = tmp_path / "workspace" / "step2_inference_results.json"
    inference = json.loads(inference_path.read_text(encoding="utf-8"))
    inference["results"].append(dict(inference["results"][0]))
    inference_path.write_text(json.dumps(inference), encoding="utf-8")
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)

    class _NeverConstruct:
        def __init__(self, *args, **kwargs):
            pytest.fail("Grader must not be constructed for duplicate inference IDs")

    monkeypatch.setattr(s8, "Grader", _NeverConstruct)
    monkeypatch.setattr("sys.argv", [
        "step8_grade.py", "exp998_smoke_baseline_sample",
        "--config", "grading_configs/default.yaml", "--force",
    ])

    assert s8.main() != 0


@pytest.mark.parametrize(
    "bad_path",
    [
        "/tmp/secret.txt",
        "../secret.txt",
        "deliverable_files/task-002/other.txt",
        "deliverable_files/task-001/../secret.txt",
    ],
)
def test_new_run_rejects_unconfined_manifest_path_before_grader(
    monkeypatch, tmp_path, bad_path
):
    _setup_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    inference_path = tmp_path / "workspace" / "step2_inference_results.json"
    inference = json.loads(inference_path.read_text(encoding="utf-8"))
    inference["results"][0]["deliverable_files"] = [bad_path]
    inference_path.write_text(json.dumps(inference), encoding="utf-8")
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)

    class _NeverConstruct:
        def __init__(self, *args, **kwargs):
            pytest.fail("Grader must not be constructed for an unsafe manifest")

    monkeypatch.setattr(s8, "Grader", _NeverConstruct)
    monkeypatch.setattr("sys.argv", [
        "step8_grade.py", "exp998_smoke_baseline_sample",
        "--config", "grading_configs/default.yaml", "--force",
    ])

    assert s8.main() != 0


def test_new_run_rejects_symlinked_deliverable_before_grader(
    monkeypatch, tmp_path
):
    _setup_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    deliverable = (
        tmp_path / "workspace/upload/deliverable_files/task-001/Sample.xlsx"
    )
    outside = tmp_path / "secret.txt"
    outside.write_text("secret", encoding="utf-8")
    deliverable.unlink()
    deliverable.symlink_to(outside)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)

    class _NeverConstruct:
        def __init__(self, *args, **kwargs):
            pytest.fail("Grader must not be constructed for a symlinked deliverable")

    monkeypatch.setattr(s8, "Grader", _NeverConstruct)
    monkeypatch.setattr("sys.argv", [
        "step8_grade.py", "exp998_smoke_baseline_sample",
        "--config", "grading_configs/default.yaml", "--force",
    ])

    assert s8.main() != 0


def test_new_run_rejects_symlinked_workspace_ancestor_before_grader(
    monkeypatch, tmp_path
):
    _setup_workspace(tmp_path)
    real_workspace = tmp_path / "real-workspace"
    (tmp_path / "workspace").rename(real_workspace)
    (tmp_path / "workspace").symlink_to(real_workspace, target_is_directory=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)

    class _NeverConstruct:
        def __init__(self, *args, **kwargs):
            pytest.fail("Grader must not be constructed through workspace symlink")

    monkeypatch.setattr(s8, "Grader", _NeverConstruct)
    monkeypatch.setattr("sys.argv", [
        "step8_grade.py", "exp998_smoke_baseline_sample",
        "--config", "grading_configs/default.yaml", "--force",
    ])

    assert s8.main() != 0


def test_exit_2_when_no_inference_results(monkeypatch, tmp_path):
    _setup_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "workspace" / "step2_inference_results.json").unlink()

    monkeypatch.setattr("sys.argv", ["step8_grade.py", "exp998_smoke_baseline_sample", "--config", "grading_configs/default.yaml"])
    assert s8.main() == 2


def test_grade_file_records_the_visual_file_cap_it_graded_under(
    monkeypatch, tmp_path
):
    """The resolved cap, not the configured one.

    A config that omits ``file_cap_per_item`` still grades under a cap. If
    provenance only carried the perception block verbatim, a reader comparing
    two runs would have to infer the cap from whichever revision of the code
    happened to produce each grade file.
    """
    _setup_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    monkeypatch.setattr(s8, "Grader", _FakeGrader)

    monkeypatch.setattr("sys.argv", ["step8_grade.py", "exp998_smoke_baseline_sample", "--config", "grading_configs/default.yaml", "--force"])
    assert s8.main() == 0

    out = tmp_path / "data/grades/exp998_smoke_baseline_sample__gpt-5_4-pro__11e7900__v1.json"
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["judge"]["visual_file_cap"] == 10


def test_grade_file_records_a_configured_visual_file_cap(monkeypatch, tmp_path):
    _setup_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    config_path = tmp_path / "grading_configs" / "default.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["judge"]["perception"] = {
        "visual": {"model": "gpt-5.4", "file_cap_per_item": 4}
    }
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    monkeypatch.setattr(s8, "Grader", _FakeGrader)

    monkeypatch.setattr("sys.argv", ["step8_grade.py", "exp998_smoke_baseline_sample", "--config", "grading_configs/default.yaml", "--force"])
    assert s8.main() == 0

    out = tmp_path / "data/grades/exp998_smoke_baseline_sample__gpt-5_4-pro__11e7900__v1.json"
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["judge"]["visual_file_cap"] == 4


def test_inference_model_resolved_from_inf_results_when_present(monkeypatch, tmp_path):
    """inf_results['model'] takes priority when populated."""
    _setup_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    monkeypatch.setattr(s8, "Grader", _FakeGrader)

    monkeypatch.setattr("sys.argv", ["step8_grade.py", "exp998_smoke_baseline_sample", "--config", "grading_configs/default.yaml", "--force"])
    assert s8.main() == 0

    out = tmp_path / "data/grades/exp998_smoke_baseline_sample__gpt-5_4-pro__11e7900__v1.json"
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["inference_model"] == "gpt-5.2-chat"
    # never silently fall back to the judge model
    assert payload["inference_model"] != payload["judge"]["model"]


def test_inference_model_falls_back_to_experiment_yaml(monkeypatch, tmp_path):
    """When inf_results['model'] is blank, pull deployment from experiment yaml."""
    _setup_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    monkeypatch.setattr(s8, "Grader", _FakeGrader)

    # Simulate HF-reconstruct path that leaves model="" on the inference dict.
    inf_path = tmp_path / "workspace" / "step2_inference_results.json"
    inf = json.loads(inf_path.read_text(encoding="utf-8"))
    inf["model"] = ""
    inf_path.write_text(json.dumps(inf), encoding="utf-8")

    monkeypatch.setattr("sys.argv", ["step8_grade.py", "exp998_smoke_baseline_sample", "--config", "grading_configs/default.yaml", "--force"])
    assert s8.main() == 0

    out = tmp_path / "data/grades/exp998_smoke_baseline_sample__gpt-5_4-pro__11e7900__v1.json"
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["inference_model"] == "gpt-5.2-chat"  # from yaml.condition_a.model.deployment


def test_inference_model_never_falls_back_to_judge_model(monkeypatch, tmp_path):
    """Defensive: even with both inf model empty and a degenerate yaml, never
    leak judge model into inference_model."""
    _setup_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    monkeypatch.setattr(s8, "Grader", _FakeGrader)

    # Wipe model in both sources.
    inf_path = tmp_path / "workspace" / "step2_inference_results.json"
    inf = json.loads(inf_path.read_text(encoding="utf-8"))
    inf["model"] = ""
    inf_path.write_text(json.dumps(inf), encoding="utf-8")

    # Patch _resolve_inference_model's exp_config branch by giving an
    # experiment yaml with no deployment field.
    yaml_path = tmp_path / "experiments" / "exp998_smoke_baseline_sample.yaml"
    yaml_data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    yaml_data["condition_a"]["model"]["deployment"] = ""
    yaml_path.write_text(yaml.safe_dump(yaml_data), encoding="utf-8")

    monkeypatch.setattr("sys.argv", ["step8_grade.py", "exp998_smoke_baseline_sample", "--config", "grading_configs/default.yaml", "--force"])
    assert s8.main() == 0
    out = tmp_path / "data/grades/exp998_smoke_baseline_sample__gpt-5_4-pro__11e7900__v1.json"
    payload = json.loads(out.read_text(encoding="utf-8"))
    # Independent of the literal judge string: inference_model must
    # never equal whatever judge.model resolved to.
    assert payload["inference_model"] != payload["judge"]["model"], (
        "inference_model leaked judge model — _resolve_inference_model "
        "must never read config['judge']."
    )
    # And in this degraded case the resolver must surface an empty
    # string (defensive default).
    assert payload["inference_model"] == ""


# ── Phase 2: source_inference_experiment_id linkage ──────────────────────────
# Three tests verifying the explicit pointer from grade JSON to the
# inference run that produced the deliverables (spec:
# TASK_GRADE_SOURCE_LINKAGE_BACKEND.md). Keeps Phase 1 behavior unchanged
# when no override is supplied (default == experiment_yaml_name).

def test_T_A_source_inference_experiment_id_field_present(monkeypatch, tmp_path):
    """T-A. Grade JSON written by step8 contains source_inference_experiment_id."""
    _setup_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    monkeypatch.setattr(s8, "Grader", _FakeGrader)

    monkeypatch.setattr(
        "sys.argv",
        ["step8_grade.py", "exp998_smoke_baseline_sample", "--config", "grading_configs/default.yaml", "--force"],
    )
    assert s8.main() == 0

    out = tmp_path / "data/grades/exp998_smoke_baseline_sample__gpt-5_4-pro__11e7900__v1.json"
    payload = json.loads(out.read_text(encoding="utf-8"))

    assert "source_inference_experiment_id" in payload, (
        "Phase 2: source_inference_experiment_id must be emitted in every new grade"
    )
    assert isinstance(payload["source_inference_experiment_id"], str)
    assert payload["source_inference_experiment_id"], "must be non-empty by default"
    # source_inference_run_dir is optional; type must be str|None.
    assert "source_inference_run_dir" in payload
    assert payload["source_inference_run_dir"] is None or isinstance(
        payload["source_inference_run_dir"], str
    )


def test_T_B_default_source_id_equals_experiment_yaml_name(monkeypatch, tmp_path):
    """T-B. Default value equals args.experiment_yaml_name when no override."""
    _setup_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    monkeypatch.setattr(s8, "Grader", _FakeGrader)

    monkeypatch.setattr(
        "sys.argv",
        ["step8_grade.py", "exp998_smoke_baseline_sample", "--config", "grading_configs/default.yaml", "--force"],
    )
    assert s8.main() == 0

    out = tmp_path / "data/grades/exp998_smoke_baseline_sample__gpt-5_4-pro__11e7900__v1.json"
    payload = json.loads(out.read_text(encoding="utf-8"))

    # No --source-experiment-id given → mirror experiment_yaml_name.
    assert payload["source_inference_experiment_id"] == "exp998_smoke_baseline_sample"
    assert payload["source_inference_experiment_id"] == payload["experiment_yaml_name"]


def test_T_C_source_experiment_id_cli_override(monkeypatch, tmp_path):
    """T-C. --source-experiment-id <id> overrides the default."""
    _setup_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    monkeypatch.setattr(s8, "Grader", _FakeGrader)

    monkeypatch.setattr(
        "sys.argv",
        [
            "step8_grade.py",
            "exp998_smoke_baseline_sample",
            "--config",
            "grading_configs/default.yaml",
            "--force",
            "--source-experiment-id",
            "exp999_smoke_baseline_sample",
        ],
    )
    assert s8.main() == 0

    out = tmp_path / "data/grades/exp998_smoke_baseline_sample__gpt-5_4-pro__11e7900__v1.json"
    payload = json.loads(out.read_text(encoding="utf-8"))

    # The override must win and must not mutate experiment_id / yaml_name.
    assert payload["source_inference_experiment_id"] == "exp999_smoke_baseline_sample"
    assert payload["experiment_id"] == "exp998_smoke_baseline_sample"
    assert payload["experiment_yaml_name"] == "exp998_smoke_baseline_sample"


# ---------------------------------------------------------------------------
# --resume + time-budget (chunked auto-resume) tests
# ---------------------------------------------------------------------------

def _seed_partial_grade(
    tmp_path: Path,
    task_ids: list[str],
    renderer_fingerprint: dict[str, str] | None = None,
    run_status: str = "partial",
    out: Path | None = None,
) -> Path:
    """Drop a valid partial grade JSON at the templated output path.

    `out` overrides the destination for shard tests, whose payload lands under
    `data/grades/_shards/<stem>/` rather than on the canonical name.
    """
    out = out or (
        tmp_path
        / "data/grades/exp998_smoke_baseline_sample__gpt-5_4-pro__11e7900__v1.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    task_rows = [
        {
            "task_id": tid,
            "sector": "s",
            "occupation": "o",
            "items": [],
            "total_awarded": 2,
            "total_max": 2,
            "pct": 100.0,
            "critical_fail": False,
            "gold_referenced": False,
            "judge_call_count": 0,
            "precheck_count": 1,
            "judge_total_latency_ms": 0,
            "judge_input_tokens": 0,
            "judge_output_tokens": 0,
            "usage_complete": True,
            # Decided entirely by precheck above, so no judge call was made and
            # the receipt is the one honest zero. A fixture partial keeps no
            # ledger, hence the null pointer on the payload below.
            "grading_cost": CostReceipt.free().as_dict(),
            "graded_at": "2026-05-27T00:00:00Z",
            "error": None,
        }
        for tid in task_ids
    ]
    config = yaml.safe_load(
        (tmp_path / "grading_configs" / "default.yaml").read_text(
            encoding="utf-8"
        )
    )
    payload = {
        "schema_version": s8.SCHEMA_VERSION,
        "run_status": run_status,
        "expected_task_count": 3,
        "expected_ordered_task_ids_sha256": s8._ordered_task_ids_sha256(
            ["task-001", "task-002", "task-003"]
        ),
        "experiment_id": "exp998_smoke_baseline_sample",
        "experiment_yaml_name": "exp998_smoke_baseline_sample",
        "source_inference_repo_id": "owner/repo",
        "source_inference_revision": INFERENCE_SHA,
        "azure_ai_routes": s8.preflight_routes(
            s8.grader_route_workloads(config),
            **s8.grader_transport_options(config),
        ),
        "grader_source_hash": s8.compute_grader_source_hash(
            tmp_path / "grading_configs" / "default.yaml",
            config,
        ),
        "judge": {
            "provider": "azure_openai",
            "api": "responses",
            "model": "gpt-5.4-pro",
            "deployment": "gpt-5.4-pro",
            "api_version": "2025-04-01-preview",
            "reasoning_effort": "high",
            "temperature": 0,
            "seed": 42,
            "config_name": "default_gpt5pro",
            "config_hash": s8.hash_config(
                str(tmp_path / "grading_configs" / "default.yaml")
            ),
        },
        "rubric": {
            "source": "huggingface",
            "repo_id": "openai/gdpval",
            "revision": "main",
            "commit_sha": _FakeLoader().rubric_sha,
            "short_sha": _FakeLoader().rubric_short_sha,
        },
        "prompt": {"template": "prompts/grader_judge.md", "version": "v1"},
        "graded_at": "2026-05-27T00:00:00Z",
        "graded_by": "step8_grade.py",
        "cost_ledger": None,
        "tasks": task_rows,
        "summary": s8._compute_summary(
            task_rows,
            unpriced_models=["gpt-5.4-pro"],
        ),
    }
    payload["azure_ai_runtime_fingerprint"] = payload[
        "azure_ai_routes"
    ][0]["runtime_fingerprint"]
    if renderer_fingerprint is not None:
        payload["renderer_fingerprint"] = renderer_fingerprint
    out.write_text(json.dumps(payload), encoding="utf-8")
    return out


def test_resume_rejects_previous_score_semantics():
    with pytest.raises(ValueError, match="schema_version"):
        s8._validate_grade_resume_identity(
            {"schema_version": "1.2"},
            experiment_id="exp003",
            rubric_commit_sha="a" * 40,
            prompt_version="v2.2",
            config_hash="0123456789abcdef",
            source_inference_repo_id="owner/repo",
            source_inference_revision="b" * 40,
            grader_source_hash="c" * 64,
            renderer_fingerprint=None,
            anchor_projection=None,
        )


def _validate_resume_anchor_projection(
    existing: dict,
    expected: dict | None,
) -> None:
    s8._validate_grade_resume_identity(
        existing,
        experiment_id="exp003",
        rubric_commit_sha="a" * 40,
        prompt_version="v2.2",
        config_hash="0123456789abcdef",
        source_inference_repo_id="owner/repo",
        source_inference_revision="b" * 40,
        grader_source_hash="c" * 64,
        renderer_fingerprint=None,
        anchor_projection=expected,
    )


def _matching_resume_identity() -> dict:
    return {
        "schema_version": "1.4",
        "experiment_id": "exp003",
        "rubric": {"commit_sha": "a" * 40},
        "prompt": {"version": "v2.2"},
        "judge": {"config_hash": "0123456789abcdef"},
        "source_inference_repo_id": "owner/repo",
        "source_inference_revision": "b" * 40,
        "grader_source_hash": "c" * 64,
    }


def test_resume_accepts_exact_anchor_projection_contract():
    contract = {"method": "modality_normalized_v1"}
    existing = _matching_resume_identity()
    existing["anchor_projection"] = contract

    _validate_resume_anchor_projection(existing, contract)


@pytest.mark.parametrize("persisted", ["missing", None, {"method": "other"}])
def test_resume_rejects_anchor_projection_contract_drift(persisted):
    contract = {"method": "modality_normalized_v1"}
    existing = _matching_resume_identity()
    if persisted != "missing":
        existing["anchor_projection"] = persisted

    with pytest.raises(ValueError, match="anchor_projection"):
        _validate_resume_anchor_projection(existing, contract)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("experiment_id", "other-exp"),
        ("task_count", 53),
        ("rubric_commit_sha", "d" * 40),
        ("inference_revision", "e" * 40),
    ],
)
def test_pinned_rerun_identity_rejects_drift(field, value):
    config = {
        "rerun_identity": {
            "experiment_id": "exp003",
            "expected_task_count": 220,
            "rubric_commit_sha": "a" * 40,
            "inference_revision": "b" * 40,
        }
    }
    actual = {
        "experiment_id": "exp003",
        "task_count": 220,
        "rubric_commit_sha": "a" * 40,
        "inference_revision": "b" * 40,
    }
    actual[field] = value

    with pytest.raises(ValueError, match="pinned rerun identity"):
        s8._validate_pinned_rerun_identity(config, **actual)


def test_pinned_rerun_identity_accepts_exact_full_run():
    config = {
        "rerun_identity": {
            "experiment_id": "exp003",
            "expected_task_count": 220,
            "rubric_commit_sha": "a" * 40,
            "inference_revision": "b" * 40,
        }
    }

    s8._validate_pinned_rerun_identity(
        config,
        experiment_id="exp003",
        task_count=220,
        rubric_commit_sha="a" * 40,
        inference_revision="b" * 40,
    )


def _pinned_task_config() -> dict:
    return {
        "rerun_identity": {
            "experiment_id": "exp003",
            "expected_task_count": 2,
            "rubric_commit_sha": "a" * 40,
            "inference_revision": "b" * 40,
            "task_ids": ["task-002", "task-003"],
        }
    }


def _selection_inference() -> dict:
    return {
        "results": [
            {"task_id": "task-001"},
            {"task_id": "task-002"},
            {"task_id": "task-003"},
        ]
    }


def test_config_pinned_tasks_apply_without_cli_selection():
    selected, scope = s8.filter_tasks_for_config(
        _selection_inference(),
        _pinned_task_config(),
        tasks_csv=None,
        limit=0,
    )

    assert [task["task_id"] for task in selected] == ["task-002", "task-003"]
    assert scope == "subset"


def test_pinning_every_source_task_is_a_complete_scope():
    """Pinning the whole corpus asserts its identity; it narrows nothing."""
    config = _pinned_task_config()
    config["rerun_identity"]["task_ids"] = ["task-001", "task-002", "task-003"]
    config["rerun_identity"]["expected_task_count"] = 3

    selected, scope = s8.filter_tasks_for_config(
        _selection_inference(),
        config,
        tasks_csv=None,
        limit=0,
    )

    assert [task["task_id"] for task in selected] == [
        "task-001",
        "task-002",
        "task-003",
    ]
    assert scope == "complete"


def test_unpinned_config_has_no_scope():
    selected, scope = s8.filter_tasks_for_config(
        _selection_inference(),
        {},
        tasks_csv=None,
        limit=0,
    )

    assert len(selected) == 3
    assert scope is None


def test_matching_cli_tasks_are_accepted_in_canonical_source_order():
    selected, scope = s8.filter_tasks_for_config(
        _selection_inference(),
        _pinned_task_config(),
        tasks_csv="task-003,task-002",
        limit=2,
    )

    assert [task["task_id"] for task in selected] == ["task-002", "task-003"]
    assert scope == "subset"


@pytest.mark.parametrize(
    ("tasks_csv", "limit"),
    [
        ("task-001,task-002", 2),
        (None, 1),
        (None, 3),
    ],
)
def test_pinned_selection_rejects_cli_or_limit_mismatch(tasks_csv, limit):
    with pytest.raises(ValueError, match="pinned task selection"):
        s8.filter_tasks_for_config(
            _selection_inference(),
            _pinned_task_config(),
            tasks_csv=tasks_csv,
            limit=limit,
        )


def test_pinned_runtime_identity_requires_exact_ordered_task_ids():
    config = _pinned_task_config()

    s8._validate_pinned_rerun_identity(
        config,
        experiment_id="exp003",
        task_ids=["task-002", "task-003"],
        rubric_commit_sha="a" * 40,
        inference_revision="b" * 40,
    )
    with pytest.raises(ValueError, match="task_ids"):
        s8._validate_pinned_rerun_identity(
            config,
            experiment_id="exp003",
            task_ids=["task-003", "task-002"],
            rubric_commit_sha="a" * 40,
            inference_revision="b" * 40,
        )


def test_main_applies_config_pinned_tasks_as_diagnostic_without_cli(
    monkeypatch,
    tmp_path,
    capsys,
):
    _setup_workspace(tmp_path)
    config_path = tmp_path / "grading_configs" / "default.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["schema_version"] = "2.0"
    config["rubric"]["revision"] = _FakeLoader().rubric_sha
    config["rerun_identity"] = {
        "experiment_id": "exp998_smoke_baseline_sample",
        "expected_task_count": 2,
        "rubric_commit_sha": _FakeLoader().rubric_sha,
        "inference_revision": INFERENCE_SHA,
        "task_ids": ["task-002", "task-003"],
    }
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    github_output = tmp_path / "github-output.txt"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GITHUB_OUTPUT", str(github_output))
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    monkeypatch.setattr("sys.argv", [
        "step8_grade.py",
        "exp998_smoke_baseline_sample",
        "--config",
        "grading_configs/default.yaml",
        "--dry-run",
    ])

    assert s8.main() == 0
    assert "Dry-run tasks=2" in capsys.readouterr().out
    output = github_output.read_text(encoding="utf-8")
    assert "grade_status=diagnostic" in output


def test_grade_payload_binds_anchor_projection_contract(monkeypatch, tmp_path):
    _setup_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    config_path = tmp_path / "grading_configs" / "default.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["anchor_projection"] = {
        "method": "modality_normalized_v1",
        "anchor_config_name": config["config_name"],
        "anchor_task_count": 2,
        "anchor_ordered_task_ids_sha256": s8._ordered_task_ids_sha256(
            ["task-002", "task-003"]
        ),
        "anchor_source_inference_repo_id": "owner/repo",
        "baseline_payload_sha256": "b" * 64,
        "baseline_schema_version": "1.0",
        "baseline_perception_wired": False,
        "baseline_main_calls": 234,
        "baseline_main_latency_ms": 2_449_199.44,
        "baseline_final_json_parse_failed": 13,
        "baseline_empty_final_text": 9,
        "anchor_visual_criteria": 43,
        "anchor_audio_criteria": 13,
        "full_task_count": 220,
        "full_visual_criteria": 337,
        "full_audio_criteria": 58,
        "chunk_envelope_hours": 44,
    }
    routes = s8.preflight_routes(
        s8.grader_route_workloads(config),
        **s8.grader_transport_options(config),
    )

    payload = s8._build_grade_payload(
        "exp998_smoke_baseline_sample",
        {},
        config,
        "0123456789abcdef",
        _FakeLoader(),
        "v2.2",
        [],
        "c" * 64,
        "owner/repo",
        INFERENCE_SHA,
        azure_ai_runtime_fingerprint=routes[0]["runtime_fingerprint"],
        azure_ai_routes=routes,
        run_status="diagnostic",
        expected_task_ids=["task-002", "task-003"],
    )

    assert payload["anchor_projection"] == config["anchor_projection"]
    s8._validate_schema(payload)


def test_pinned_rerun_identity_fails_before_route_preflight(
    monkeypatch, tmp_path
):
    _setup_workspace(tmp_path)
    _configure_track2(tmp_path)
    config_path = tmp_path / "grading_configs" / "default.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["rubric"]["revision"] = _FakeLoader().rubric_sha
    config["rerun_identity"] = {
        "experiment_id": "exp998_smoke_baseline_sample",
        "expected_task_count": 220,
        "rubric_commit_sha": _FakeLoader().rubric_sha,
        "inference_revision": INFERENCE_SHA,
    }
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    route_calls = []

    def unexpected_preflight(*args, **kwargs):
        route_calls.append((args, kwargs))
        raise AssertionError("route preflight must not run")

    monkeypatch.setattr(s8, "preflight_routes", unexpected_preflight)
    monkeypatch.setattr("sys.argv", [
        "step8_grade.py",
        "exp998_smoke_baseline_sample",
        "--config",
        "grading_configs/default.yaml",
        "--dry-run",
    ])

    assert s8.main() == 1
    assert route_calls == []


def test_github_output_helper_writes_exact_repo_relative_grade_path(
    monkeypatch, tmp_path
):
    monkeypatch.chdir(tmp_path)
    github_output = tmp_path / "github-output.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(github_output))
    out_path = tmp_path / "data" / "grades" / "grade.json"

    grade_file = s8._repo_relative_grade_file(out_path)
    s8._write_github_output("grade_file", grade_file)

    assert grade_file == "data/grades/grade.json"
    assert github_output.read_text(encoding="utf-8") == (
        "grade_file=data/grades/grade.json\n"
    )


def test_github_output_helper_rejects_multiline_value(monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "github-output.txt"))

    with pytest.raises(ValueError, match="single line"):
        s8._write_github_output("grade_file", "data/grades/a.json\nother=value")


def test_resume_skips_already_completed_tasks(monkeypatch, tmp_path):
    """--resume must skip tasks whose task_id is in the existing grade JSON,
    so the underlying Grader is only called for the remaining ones."""
    _setup_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    grader_instance = {}

    class _TrackGrader(_FakeGrader):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            grader_instance["g"] = self

    monkeypatch.setattr(s8, "Grader", _TrackGrader)

    # Seed partial with task-001 and task-002 already graded.
    _seed_partial_grade(tmp_path, ["task-001", "task-002"])

    monkeypatch.setattr("sys.argv", [
        "step8_grade.py", "exp998_smoke_baseline_sample",
        "--config", "grading_configs/default.yaml",
        "--resume",
    ])
    rc = s8.main()
    assert rc == 0
    # Only task-003 should have hit the grader.
    assert grader_instance["g"].calls == 1
    out = tmp_path / "data/grades/exp998_smoke_baseline_sample__gpt-5_4-pro__11e7900__v1.json"
    payload = json.loads(out.read_text(encoding="utf-8"))
    ids = [task["task_id"] for task in payload["tasks"]]
    assert ids == ["task-001", "task-002", "task-003"]


@pytest.mark.parametrize("missing", [False, True])
def test_resume_rejects_azure_route_drift_before_grader(
    monkeypatch, tmp_path, missing
):
    _setup_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)

    class _NeverConstruct:
        def __init__(self, *args, **kwargs):
            pytest.fail("Grader must not be constructed after route drift")

    monkeypatch.setattr(s8, "Grader", _NeverConstruct)
    out = _seed_partial_grade(tmp_path, ["task-001"])
    payload = json.loads(out.read_text(encoding="utf-8"))
    if missing:
        del payload["azure_ai_routes"]
    else:
        payload["azure_ai_routes"][0]["runtime_fingerprint"] = "f" * 64
    out.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr("sys.argv", [
        "step8_grade.py", "exp998_smoke_baseline_sample",
        "--config", "grading_configs/default.yaml", "--resume",
    ])

    assert s8.main() != 0


@pytest.mark.parametrize("missing", [False, True])
def test_resume_rejects_primary_grader_fingerprint_drift_before_grader(
    monkeypatch, tmp_path, missing
):
    _setup_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)

    class _NeverConstruct:
        def __init__(self, *args, **kwargs):
            pytest.fail("Grader must not be constructed after fingerprint drift")

    monkeypatch.setattr(s8, "Grader", _NeverConstruct)
    out = _seed_partial_grade(tmp_path, ["task-001"])
    payload = json.loads(out.read_text(encoding="utf-8"))
    if missing:
        del payload["azure_ai_runtime_fingerprint"]
    else:
        payload["azure_ai_runtime_fingerprint"] = "f" * 64
    out.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr("sys.argv", [
        "step8_grade.py",
        "exp998_smoke_baseline_sample",
        "--config",
        "grading_configs/default.yaml",
        "--resume",
    ])

    assert s8.main() != 0


def test_grade_payload_records_judge_and_perception_routes(monkeypatch, tmp_path):
    _setup_workspace(tmp_path)
    config_path = tmp_path / "grading_configs" / "default.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["judge"]["perception"] = {
        "visual": {"model": "vision-deployment"},
        "audio": {"model": "audio-deployment"},
    }
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    monkeypatch.setattr(s8, "Grader", _FakeGrader)
    monkeypatch.setattr("sys.argv", [
        "step8_grade.py", "exp998_smoke_baseline_sample",
        "--config", "grading_configs/default.yaml", "--force",
    ])

    assert s8.main() == 0
    out = (
        tmp_path
        / "data/grades"
        / "exp998_smoke_baseline_sample__gpt-5_4-pro__11e7900__v1.json"
    )
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert len(payload["azure_ai_routes"]) == 3
    assert {record["workload"] for record in payload["azure_ai_routes"]} == {
        "grader"
    }


@pytest.mark.parametrize("track2", [False, True])
def test_periodic_partial_persists_complete_azure_routes(
    monkeypatch, tmp_path, track2
):
    _setup_workspace(tmp_path)
    if track2:
        _configure_track2(tmp_path)
        monkeypatch.setattr(
            s8, "get_renderer_fingerprint", lambda: dict(_RENDERER_FINGERPRINT)
        )
    inference_path = tmp_path / "workspace" / "step2_inference_results.json"
    inference = json.loads(inference_path.read_text(encoding="utf-8"))
    inference["results"] = []
    for index in range(1, 11):
        task_id = f"task-{index:03d}"
        relative = f"deliverable_files/{task_id}/Sample.xlsx"
        inference["results"].append(
            {"task_id": task_id, "deliverable_files": [relative]}
        )
        deliverable = tmp_path / "workspace" / "upload" / relative
        deliverable.parent.mkdir(parents=True, exist_ok=True)
        deliverable.write_bytes(b"test deliverable")
    inference_path.write_text(json.dumps(inference), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    monkeypatch.setattr(s8, "Grader", _FakeGrader)
    saved_payloads = []
    original_save = s8._save_json

    def capture_save(path, payload):
        saved_payloads.append(json.loads(json.dumps(payload)))
        original_save(path, payload)

    monkeypatch.setattr(s8, "_save_json", capture_save)
    monkeypatch.setattr("sys.argv", [
        "step8_grade.py", "exp998_smoke_baseline_sample",
        "--config", "grading_configs/default.yaml", "--force",
    ])

    assert s8.main() == 0
    assert len(saved_payloads) >= 2
    periodic = saved_payloads[-2]
    assert len(periodic["tasks"]) == 10
    assert periodic["azure_ai_routes"]
    s8._validate_schema(periodic)


def test_resume_without_existing_file_refuses_fresh_paid_run(monkeypatch, tmp_path):
    """--resume on a clean workspace must fail before grader construction."""
    _setup_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    grader_instance = {}

    class _TrackGrader(_FakeGrader):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            grader_instance["g"] = self

    monkeypatch.setattr(s8, "Grader", _TrackGrader)

    monkeypatch.setattr("sys.argv", [
        "step8_grade.py", "exp998_smoke_baseline_sample",
        "--config", "grading_configs/default.yaml",
        "--resume",
    ])
    rc = s8.main()
    assert rc != 0
    assert "g" not in grader_instance


def test_track2_resume_without_partial_fails_before_grader(monkeypatch, tmp_path):
    _setup_workspace(tmp_path)
    _configure_track2(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    monkeypatch.setattr(
        s8, "get_renderer_fingerprint", lambda: dict(_RENDERER_FINGERPRINT)
    )

    class _NeverConstruct:
        def __init__(self, *args, **kwargs):
            pytest.fail("Grader must not start a fresh Track 2 resume")

    monkeypatch.setattr(s8, "Grader", _NeverConstruct)
    monkeypatch.setattr("sys.argv", [
        "step8_grade.py", "exp998_smoke_baseline_sample",
        "--config", "grading_configs/default.yaml", "--resume",
    ])

    assert s8.main() != 0


def test_track2_resume_same_fingerprint_succeeds(monkeypatch, tmp_path):
    _setup_workspace(tmp_path)
    _configure_track2(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    monkeypatch.setattr(s8, "get_renderer_fingerprint", lambda: dict(_RENDERER_FINGERPRINT))
    grader_instance = {}

    class _TrackGrader(_FakeGrader):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            grader_instance["grader"] = self

    monkeypatch.setattr(s8, "Grader", _TrackGrader)
    _seed_partial_grade(
        tmp_path, ["task-001", "task-002"], dict(_RENDERER_FINGERPRINT)
    )
    monkeypatch.setattr("sys.argv", [
        "step8_grade.py", "exp998_smoke_baseline_sample",
        "--config", "grading_configs/default.yaml", "--resume",
    ])

    assert s8.main() == 0
    assert grader_instance["grader"].calls == 1
    out = tmp_path / "data/grades/exp998_smoke_baseline_sample__gpt-5_4-pro__11e7900__v1.json"
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["renderer_fingerprint"] == _RENDERER_FINGERPRINT


def test_track2_resume_rejects_runtime_failure_before_grader(
    monkeypatch, tmp_path, capsys
):
    _setup_workspace(tmp_path)
    _configure_track2(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    monkeypatch.setattr(
        s8, "get_renderer_fingerprint", lambda: dict(_RENDERER_FINGERPRINT)
    )

    class _NeverConstruct:
        def __init__(self, *args, **kwargs):
            pytest.fail("Grader must not resume a Track 2 runtime failure")

    monkeypatch.setattr(s8, "Grader", _NeverConstruct)
    out = _seed_partial_grade(
        tmp_path, ["task-001"], dict(_RENDERER_FINGERPRINT)
    )
    payload = json.loads(out.read_text(encoding="utf-8"))
    payload["tasks"][0]["error"] = "judge_error"
    payload["tasks"][0]["usage_complete"] = False
    payload["summary"] = s8._compute_summary(
        payload["tasks"],
        unpriced_models=["gpt-5.4-pro"],
    )
    out.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr("sys.argv", [
        "step8_grade.py", "exp998_smoke_baseline_sample",
        "--config", "grading_configs/default.yaml", "--resume",
    ])

    assert s8.main() != 0
    assert "runtime failures" in capsys.readouterr().err


def test_track2_valid_cache_hit_checks_fingerprint_and_skips(
    monkeypatch, tmp_path, capsys
):
    _setup_workspace(tmp_path)
    _configure_track2(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    fingerprint_calls = []

    def get_fingerprint():
        fingerprint_calls.append(True)
        return dict(_RENDERER_FINGERPRINT)

    monkeypatch.setattr(s8, "get_renderer_fingerprint", get_fingerprint)

    class _NeverConstruct:
        def __init__(self, *args, **kwargs):
            pytest.fail("Grader must not be constructed for a valid cache hit")

    monkeypatch.setattr(s8, "Grader", _NeverConstruct)
    _seed_partial_grade(
        tmp_path,
        ["task-001", "task-002", "task-003"],
        dict(_RENDERER_FINGERPRINT),
        run_status="final",
    )
    monkeypatch.setattr("sys.argv", [
        "step8_grade.py", "exp998_smoke_baseline_sample",
        "--config", "grading_configs/default.yaml",
    ])

    assert s8.main() == 0
    assert fingerprint_calls == [True]
    assert "SKIP - exists" in capsys.readouterr().out


@pytest.mark.parametrize(
    "task_ids",
    [
        ["task-001"],
        ["task-001", "task-002", "task-extra"],
        ["task-001", "task-001", "task-003"],
    ],
)
def test_track2_cache_hit_rejects_incomplete_extra_or_duplicate_task_set(
    monkeypatch, tmp_path, task_ids
):
    _setup_workspace(tmp_path)
    _configure_track2(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    monkeypatch.setattr(
        s8, "get_renderer_fingerprint", lambda: dict(_RENDERER_FINGERPRINT)
    )

    class _NeverConstruct:
        def __init__(self, *args, **kwargs):
            pytest.fail("Grader must not be constructed after task-set rejection")

    monkeypatch.setattr(s8, "Grader", _NeverConstruct)
    _seed_partial_grade(tmp_path, task_ids, dict(_RENDERER_FINGERPRINT))
    monkeypatch.setattr("sys.argv", [
        "step8_grade.py", "exp998_smoke_baseline_sample",
        "--config", "grading_configs/default.yaml",
    ])

    assert s8.main() != 0


@pytest.mark.parametrize(
    "task_ids",
    [
        ["task-001", "task-extra"],
        ["task-001", "task-001"],
    ],
)
def test_track2_resume_rejects_extra_or_duplicate_task_set_before_grader(
    monkeypatch, tmp_path, task_ids
):
    _setup_workspace(tmp_path)
    _configure_track2(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    monkeypatch.setattr(
        s8, "get_renderer_fingerprint", lambda: dict(_RENDERER_FINGERPRINT)
    )

    class _NeverConstruct:
        def __init__(self, *args, **kwargs):
            pytest.fail("Grader must not be constructed after task-set rejection")

    monkeypatch.setattr(s8, "Grader", _NeverConstruct)
    _seed_partial_grade(tmp_path, task_ids, dict(_RENDERER_FINGERPRINT))
    monkeypatch.setattr("sys.argv", [
        "step8_grade.py", "exp998_smoke_baseline_sample",
        "--config", "grading_configs/default.yaml", "--resume",
    ])

    assert s8.main() != 0


def test_track2_resume_rejects_schema_invalid_partial_before_grader(
    monkeypatch, tmp_path
):
    _setup_workspace(tmp_path)
    _configure_track2(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    monkeypatch.setattr(
        s8, "get_renderer_fingerprint", lambda: dict(_RENDERER_FINGERPRINT)
    )

    class _NeverConstruct:
        def __init__(self, *args, **kwargs):
            pytest.fail("Grader must not be constructed for schema-invalid partial")

    monkeypatch.setattr(s8, "Grader", _NeverConstruct)
    out = _seed_partial_grade(
        tmp_path, ["task-001"], dict(_RENDERER_FINGERPRINT)
    )
    payload = json.loads(out.read_text(encoding="utf-8"))
    del payload["summary"]
    out.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr("sys.argv", [
        "step8_grade.py", "exp998_smoke_baseline_sample",
        "--config", "grading_configs/default.yaml", "--resume",
    ])

    assert s8.main() != 0


@pytest.mark.parametrize("resume", [False, True])
def test_track2_cache_or_resume_rejects_missing_task_id_before_grader(
    monkeypatch, tmp_path, resume
):
    _setup_workspace(tmp_path)
    _configure_track2(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    monkeypatch.setattr(
        s8, "get_renderer_fingerprint", lambda: dict(_RENDERER_FINGERPRINT)
    )

    class _NeverConstruct:
        def __init__(self, *args, **kwargs):
            pytest.fail("Grader must not be constructed without task_id")

    monkeypatch.setattr(s8, "Grader", _NeverConstruct)
    task_ids = ["task-001"] if resume else [
        "task-001", "task-002", "task-003"
    ]
    out = _seed_partial_grade(
        tmp_path, task_ids, dict(_RENDERER_FINGERPRINT)
    )
    payload = json.loads(out.read_text(encoding="utf-8"))
    del payload["tasks"][0]["task_id"]
    out.write_text(json.dumps(payload), encoding="utf-8")
    argv = [
        "step8_grade.py", "exp998_smoke_baseline_sample",
        "--config", "grading_configs/default.yaml",
    ]
    if resume:
        argv.append("--resume")
    monkeypatch.setattr("sys.argv", argv)

    assert s8.main() != 0


@pytest.mark.parametrize(
    ("identity_path", "replacement"),
    [
        (("experiment_id",), "other-experiment"),
        (("rubric", "commit_sha"), "0" * 40),
        (("prompt", "version"), "v9"),
        (("judge", "config_hash"), "f" * 16),
        (("source_inference_repo_id",), "other/repo"),
        (("source_inference_revision",), "b" * 40),
        (("grader_source_hash",), "0" * 64),
        (("renderer_fingerprint",), {
            "libreoffice_binary": "soffice",
            "libreoffice_version": "LibreOffice 25.0",
            "pymupdf_version": "1.26.3",
        }),
    ],
)
@pytest.mark.parametrize("missing", [False, True])
def test_track2_cache_hit_rejects_each_missing_or_mismatched_identity_before_grader(
    monkeypatch, tmp_path, identity_path, replacement, missing
):
    _setup_workspace(tmp_path)
    _configure_track2(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    monkeypatch.setattr(
        s8, "get_renderer_fingerprint", lambda: dict(_RENDERER_FINGERPRINT)
    )

    class _NeverConstruct:
        def __init__(self, *args, **kwargs):
            pytest.fail("Grader must not be constructed after cache rejection")

    monkeypatch.setattr(s8, "Grader", _NeverConstruct)
    out = _seed_partial_grade(
        tmp_path, ["task-001"], dict(_RENDERER_FINGERPRINT)
    )
    payload = json.loads(out.read_text(encoding="utf-8"))
    parent = payload
    for key in identity_path[:-1]:
        parent = parent[key]
    if missing:
        del parent[identity_path[-1]]
    else:
        parent[identity_path[-1]] = replacement
    out.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr("sys.argv", [
        "step8_grade.py", "exp998_smoke_baseline_sample",
        "--config", "grading_configs/default.yaml",
    ])

    assert s8.main() != 0


def test_track2_cache_hit_rejects_malformed_json_before_grader(
    monkeypatch, tmp_path
):
    _setup_workspace(tmp_path)
    _configure_track2(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    monkeypatch.setattr(
        s8, "get_renderer_fingerprint", lambda: dict(_RENDERER_FINGERPRINT)
    )

    class _NeverConstruct:
        def __init__(self, *args, **kwargs):
            pytest.fail("Grader must not be constructed for malformed cache JSON")

    monkeypatch.setattr(s8, "Grader", _NeverConstruct)
    out = _seed_partial_grade(
        tmp_path, ["task-001"], dict(_RENDERER_FINGERPRINT)
    )
    out.write_text("{not-json", encoding="utf-8")
    monkeypatch.setattr("sys.argv", [
        "step8_grade.py", "exp998_smoke_baseline_sample",
        "--config", "grading_configs/default.yaml",
    ])

    assert s8.main() != 0


@pytest.mark.parametrize(
    ("identity_path", "replacement"),
    [
        (("experiment_id",), "other-experiment"),
        (("rubric", "commit_sha"), "0" * 40),
        (("prompt", "version"), "v9"),
        (("judge", "config_hash"), "f" * 16),
        (("source_inference_repo_id",), "other/repo"),
        (("source_inference_revision",), "b" * 40),
        (("grader_source_hash",), "0" * 64),
    ],
)
@pytest.mark.parametrize("missing", [False, True])
def test_track2_resume_rejects_each_missing_or_mismatched_identity_before_grader(
    monkeypatch, tmp_path, identity_path, replacement, missing
):
    _setup_workspace(tmp_path)
    _configure_track2(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    monkeypatch.setattr(
        s8, "get_renderer_fingerprint", lambda: dict(_RENDERER_FINGERPRINT)
    )

    class _NeverConstruct:
        def __init__(self, *args, **kwargs):
            pytest.fail("Grader must not be constructed after identity rejection")

    monkeypatch.setattr(s8, "Grader", _NeverConstruct)
    out = _seed_partial_grade(
        tmp_path, ["task-001"], dict(_RENDERER_FINGERPRINT)
    )
    payload = json.loads(out.read_text(encoding="utf-8"))
    parent = payload
    for key in identity_path[:-1]:
        parent = parent[key]
    if missing:
        del parent[identity_path[-1]]
    else:
        parent[identity_path[-1]] = replacement
    out.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr("sys.argv", [
        "step8_grade.py", "exp998_smoke_baseline_sample",
        "--config", "grading_configs/default.yaml", "--resume",
    ])

    assert s8.main() != 0


@pytest.mark.parametrize("existing_fingerprint", [None, {
    "libreoffice_binary": "soffice",
    "libreoffice_version": "LibreOffice 25.0",
    "pymupdf_version": "1.26.3",
}])
def test_track2_resume_rejects_missing_or_mismatched_fingerprint_before_grading(
    monkeypatch, tmp_path, existing_fingerprint
):
    _setup_workspace(tmp_path)
    _configure_track2(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    monkeypatch.setattr(s8, "get_renderer_fingerprint", lambda: dict(_RENDERER_FINGERPRINT))

    class _NeverConstruct:
        def __init__(self, *args, **kwargs):
            pytest.fail("Grader must not be constructed after fingerprint rejection")

    monkeypatch.setattr(s8, "Grader", _NeverConstruct)
    _seed_partial_grade(
        tmp_path, ["task-001"], existing_fingerprint
    )
    monkeypatch.setattr("sys.argv", [
        "step8_grade.py", "exp998_smoke_baseline_sample",
        "--config", "grading_configs/default.yaml", "--resume",
    ])

    assert s8.main() != 0


def test_resume_rejects_malformed_partial_before_grading(monkeypatch, tmp_path):
    _setup_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)

    class _NeverConstruct:
        def __init__(self, *args, **kwargs):
            pytest.fail("Grader must not be constructed for malformed resume JSON")

    monkeypatch.setattr(s8, "Grader", _NeverConstruct)
    out = tmp_path / "data/grades/exp998_smoke_baseline_sample__gpt-5_4-pro__11e7900__v1.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("{not-json", encoding="utf-8")
    monkeypatch.setattr("sys.argv", [
        "step8_grade.py", "exp998_smoke_baseline_sample",
        "--config", "grading_configs/default.yaml", "--resume",
    ])

    assert s8.main() != 0


def test_track2_fingerprint_failure_happens_before_grader_construction(
    monkeypatch, tmp_path
):
    _setup_workspace(tmp_path)
    _configure_track2(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)

    def fail_fingerprint():
        raise s8.ReadDeliverableError("LibreOffice unavailable")

    monkeypatch.setattr(s8, "get_renderer_fingerprint", fail_fingerprint)

    class _NeverConstruct:
        def __init__(self, *args, **kwargs):
            pytest.fail("Grader must not be constructed without a fingerprint")

    monkeypatch.setattr(s8, "Grader", _NeverConstruct)
    monkeypatch.setattr("sys.argv", [
        "step8_grade.py", "exp998_smoke_baseline_sample",
        "--config", "grading_configs/default.yaml", "--force",
    ])

    assert s8.main() != 0


def test_legacy_resume_never_probes_renderer(monkeypatch, tmp_path):
    _setup_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    monkeypatch.setattr(s8, "Grader", _FakeGrader)
    monkeypatch.setattr(
        s8,
        "get_renderer_fingerprint",
        lambda: pytest.fail("legacy resume must not probe LibreOffice"),
    )
    _seed_partial_grade(tmp_path, ["task-001", "task-002"])
    monkeypatch.setattr("sys.argv", [
        "step8_grade.py", "exp998_smoke_baseline_sample",
        "--config", "grading_configs/default.yaml", "--resume",
    ])

    assert s8.main() == 0


def test_track2_dry_run_does_not_probe_renderer(monkeypatch, tmp_path):
    _setup_workspace(tmp_path)
    _configure_track2(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    monkeypatch.setattr(
        s8,
        "get_renderer_fingerprint",
        lambda: pytest.fail("dry-run must not probe LibreOffice"),
    )

    class _NoInitGrader:
        @staticmethod
        def _classify(item):
            return "precheck", "file_exists_or_name"

    monkeypatch.setattr(s8, "Grader", _NoInitGrader)
    monkeypatch.setattr("sys.argv", [
        "step8_grade.py", "exp998_smoke_baseline_sample",
        "--config", "grading_configs/default.yaml", "--dry-run",
    ])

    assert s8.main() == 0


def test_time_budget_exit_7_writes_partial(monkeypatch, tmp_path, capsys):
    """When GRADER_TIME_BUDGET_SEC elapses before all tasks are graded, step8
    must (a) save a valid partial JSON and (b) return exit code 7 so the
    workflow's auto-retrigger step fires."""
    _setup_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    grader_instance = {}

    class _TrackGrader(_FakeGrader):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            grader_instance["g"] = self

        def close(self):
            raise OSError(_SENSITIVE_CLEANUP_DETAIL)

    monkeypatch.setattr(s8, "Grader", _TrackGrader)

    # Fake clock: loop start and first check are within budget; the second
    # check is past the deadline, after one task made durable progress.
    times = iter([0.0, 0.0] + [9999.0] * 50)
    monkeypatch.setattr(s8.time, "monotonic", lambda: next(times))
    monkeypatch.setenv("GRADER_TIME_BUDGET_SEC", "100")

    monkeypatch.setattr("sys.argv", [
        "step8_grade.py", "exp998_smoke_baseline_sample",
        "--config", "grading_configs/default.yaml",
        "--force",
    ])
    rc = s8.main()
    assert rc == 7
    assert grader_instance["g"].calls == 1
    # Partial grade JSON contains the newly completed task.
    out = tmp_path / "data/grades/exp998_smoke_baseline_sample__gpt-5_4-pro__11e7900__v1.json"
    assert out.exists()
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "1.4"
    assert [task["task_id"] for task in payload["tasks"]] == ["task-001"]
    stderr = capsys.readouterr().err
    assert "provider_error:OSError" in stderr
    assert _SENSITIVE_CLEANUP_DETAIL not in stderr


def test_time_budget_without_new_progress_never_requests_resume(
    monkeypatch, tmp_path
):
    _setup_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    grader_instance = {}

    class _TrackGrader(_FakeGrader):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            grader_instance["grader"] = self

    monkeypatch.setattr(s8, "Grader", _TrackGrader)
    times = iter([0.0] + [9999.0] * 20)
    monkeypatch.setattr(s8.time, "monotonic", lambda: next(times))
    monkeypatch.setenv("GRADER_TIME_BUDGET_SEC", "100")
    monkeypatch.setattr("sys.argv", [
        "step8_grade.py", "exp998_smoke_baseline_sample",
        "--config", "grading_configs/default.yaml", "--force",
    ])

    rc = s8.main()

    assert rc == 5
    assert rc != 7
    assert grader_instance["grader"].calls == 0
    out = tmp_path / "data/grades/exp998_smoke_baseline_sample__gpt-5_4-pro__11e7900__v1.json"
    assert not out.exists()


@pytest.mark.parametrize("failure_mode", ["raise", "corrupt"])
def test_time_budget_partial_persistence_failure_never_requests_resume(
    monkeypatch, tmp_path, failure_mode
):
    _setup_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    monkeypatch.setattr(s8, "Grader", _FakeGrader)
    times = iter([0.0, 0.0] + [9999.0] * 20)
    monkeypatch.setattr(s8.time, "monotonic", lambda: next(times))
    monkeypatch.setenv("GRADER_TIME_BUDGET_SEC", "100")

    def fail_save(path, payload):
        if failure_mode == "raise":
            raise OSError("disk full")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{corrupt-json", encoding="utf-8")

    monkeypatch.setattr(s8, "_save_json", fail_save)
    monkeypatch.setattr("sys.argv", [
        "step8_grade.py", "exp998_smoke_baseline_sample",
        "--config", "grading_configs/default.yaml", "--force",
    ])

    rc = s8.main()

    assert rc == 5
    assert rc != 7


def test_atomic_save_failure_preserves_existing_file(monkeypatch, tmp_path):
    output = tmp_path / "grade.json"
    output.write_text('{"old":true}', encoding="utf-8")

    def fail_replace(self, target):
        raise OSError("replace failed")

    monkeypatch.setattr(Path, "replace", fail_replace)

    with pytest.raises(OSError, match="replace failed"):
        s8._save_json(output, {"new": True})

    assert output.read_text(encoding="utf-8") == '{"old":true}'
    assert list(tmp_path.glob(".grade-*.tmp")) == []


def test_atomic_save_supports_stage_b_output_basename(tmp_path):
    output = tmp_path / (
        "exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_4-mini__"
        "validation_v2_mini_cohort10__cfg_b11acba425087d85__rubric_"
        "11e7900cdcac61bc4daf59e65feb238acda98fbf__inference_"
        "9c639f506b8dfd5c0bb8675cb1e0c2a938a3905f__src_"
        "ab8704b10f2e39a2__v2.2.json"
    )
    payload = {"tasks": 10, "usage_complete": True}

    assert len(os.fsencode(output.name)) == 242

    s8._save_json(output, payload)

    assert json.loads(output.read_text(encoding="utf-8")) == payload
    assert list(tmp_path.glob(".grade-*.tmp")) == []


def _gh_expr(raw):
    """Collapse a GitHub Actions `if:` to one comparable line.

    The conditions guarding paid grading are written as multi-line YAML block
    scalars for readability, so an exact string compare would break on a
    reflow that changed nothing. Normalizing whitespace keeps these assertions
    strict about the condition itself and indifferent to its formatting.
    """
    return " ".join(str(raw).strip().removeprefix("${{").removesuffix("}}").split())


def test_grade_workflow_rc7_requires_valid_committed_partial():
    workflow_path = Path("../.github/workflows/grade-run.yml")
    workflow = workflow_path.read_text(
        encoding="utf-8"
    )
    parsed = yaml.safe_load(workflow)
    assert list(parsed["jobs"]) == [
        "validate-request",
        "approve-paid",
        "grade-dry-run",
        "grade",
    ]
    assert parsed["permissions"] == {"contents": "read"}

    validate_job = parsed["jobs"]["validate-request"]
    approval_job = parsed["jobs"]["approve-paid"]
    dry_run_job = parsed["jobs"]["grade-dry-run"]
    grade_job = parsed["jobs"]["grade"]
    assert approval_job["needs"] == "validate-request"
    # A paid request goes to the protected environment unless validate-request
    # proved the run inherits the approval already given for this shard.
    assert _gh_expr(approval_job["if"]) == (
        "inputs.dry_run == false && "
        "inputs.paid_approval == true && "
        "needs.validate-request.outputs.approval_inherited != 'true'"
    )
    assert approval_job["environment"] == {"name": "grading"}
    assert "permissions" not in approval_job
    assert dry_run_job["needs"] == "validate-request"
    assert dry_run_job["if"] == "inputs.dry_run == true"
    assert dry_run_job["permissions"] == {"contents": "read"}
    assert "environment" not in dry_run_job
    dry_steps = dry_run_job["steps"]
    dry_by_name = {
        step.get("name"): step for step in dry_steps if step.get("name")
    }
    dry_download = dry_by_name["Download inference results anonymously"]
    assert dry_by_name["Checkout exact main revision (read-only)"]["with"] == {
        "ref": "main",
        "persist-credentials": False,
    }
    assert "repository credentials" in dry_by_name[
        "Verify read-only checkout and input files"
    ]["run"]
    assert "--dry-run" in dry_by_name["Classify grading work only"]["run"]
    assert "secrets." not in yaml.safe_dump(dry_run_job)
    assert "id-token" not in yaml.safe_dump(dry_run_job)
    assert "actions" not in dry_run_job["permissions"]
    assert grade_job["needs"] == ["validate-request", "approve-paid"]
    # Paid grading runs on a successful approval, or on a *skipped* approval
    # only when validate-request certified the inheritance. Pinned exactly:
    # any looser condition here (a bare `!= 'failure'`, dropping the
    # approval_inherited conjunct) would let a paid run start with neither a
    # click nor a proof, which is the whole thing this gate exists to prevent.
    assert _gh_expr(grade_job["if"]) == (
        "!cancelled() && "
        "inputs.dry_run == false && "
        "inputs.paid_approval == true && "
        "needs.validate-request.result == 'success' && "
        "( needs.approve-paid.result == 'success' || "
        "( needs.approve-paid.result == 'skipped' && "
        "needs.validate-request.outputs.approval_inherited == 'true' ) )"
    )
    assert "environment" not in grade_job
    assert grade_job["permissions"] == {
        "contents": "write",
        "id-token": "write",
        "actions": "write",
    }

    validate_steps = validate_job["steps"]
    validate_inputs = next(
        step
        for step in validate_steps
        if step.get("name") == "Validate workflow context and inputs"
    )
    steps = grade_job["steps"]
    by_name = {step.get("name"): step for step in steps if step.get("name")}
    checkout = by_name["Checkout exact main revision"]
    verify_checkout = by_name["Verify checked out main and input files"]
    download = by_name["Download inference results from HF"]
    commit = by_name["Commit grade result"]
    analysis = by_name["Auto-analyze (final chunk only)"]
    commit_analysis = by_name["Commit analysis"]
    retrigger = by_name["Auto-retrigger next chunk (time budget hit)"]
    setup_python = by_name["Setup Python"]
    azure_login = by_name["Azure Login (OIDC)"]
    upload = by_name["Upload grade artifact"]

    assert "inference_revision:" in workflow
    assert 'default: ""' in workflow
    assert checkout["uses"] == (
        "actions/checkout@fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09"
    )
    assert checkout["with"] == {
        "ref": "main",
        "persist-credentials": True,
    }
    assert setup_python["uses"] == (
        "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97"
    )
    assert azure_login["uses"] == (
        "azure/login@f5d393ae46f8fde4be8b75f32e3fc50e654ad0ca"
    )
    assert upload["uses"] == (
        "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
    )
    assert "GITHUB_WORKFLOW_SHA" in validate_inputs["run"]
    assert "refs/heads/main" in validate_inputs["run"]
    assert "GRADE_TASKS_LIMIT" in validate_inputs["run"]
    assert "git rev-parse HEAD" in verify_checkout["run"]
    assert "refs/remotes/origin/main" in verify_checkout["run"]
    assert "required input must be a regular non-symlink file" in verify_checkout["run"]
    assert all(
        "${{ inputs." not in step.get("run", "")
        for step in steps
    )
    assert download["id"] == "inference"
    assert '--revision "$GRADE_INFERENCE_REVISION"' in download["run"]
    config_argument = '--grading-config "grading_configs/$GRADE_CONFIG"'
    assert dry_download["run"].count(config_argument) == 1
    assert download["run"].count(config_argument) == 1
    assert workflow.count(config_argument) == 2
    assert "--allow-legacy-missing-provenance" not in workflow
    assert 'payload.get("source_revision")' in download["run"]
    assert 'output.write(f"revision={revision}\\n")' in download["run"]

    script = commit["run"]
    assert commit["id"] == "commit_grade"
    assert "steps.grade.conclusion == 'success'" in commit["if"]
    assert commit["env"]["EXPECTED_GRADE_STATUS"] == (
        "${{ steps.grade.outputs.rc == '7' && 'partial' || "
        "steps.grade.outputs.grade_status }}"
    )
    assert 'git add -- "$GRADE_FILE"' in script
    assert script.count("validate_grade_payload(payload, schema)") == 2
    assert script.count(
        "from core.grade_payload import validate_grade_payload"
    ) == 2
    assert "GRADE_BLOB_SHA=" in script
    assert "POST_REBASE_GRADE_BLOB_SHA=" in script
    assert '[[ "$POST_REBASE_GRADE_BLOB_SHA" != "$GRADE_BLOB_SHA" ]]' in script
    assert 'git pull --rebase origin "${GITHUB_REF_NAME}"' in script
    assert 'git pull --rebase origin "${GITHUB_REF_NAME}" || true' not in script
    assert "rc=7 requires a newly persisted partial grade diff" in script
    assert script.index('git pull --rebase origin "${GITHUB_REF_NAME}"') < script.rindex(
        "validate_grade_payload(payload, schema)"
    )
    assert script.rindex("validate_grade_payload(payload, schema)") < script.index(
        'echo "committed=true"'
    )

    assert analysis["id"] == "analysis"
    assert 'OUT="$(python scripts/analyze_grade_run.py ' in analysis["run"]
    assert '"$GRADE_FILE" --auto-out)"' in analysis["run"]
    assert '${GRADE_FILE%.json}.analysis.md' not in analysis["run"]
    assert 'echo "analysis_file=$OUT" >> "$GITHUB_OUTPUT"' in analysis["run"]
    assert "! -f \"$OUT\" || -L \"$OUT\"" in analysis["run"]
    assert commit_analysis["env"]["ANALYSIS_FILE"] == (
        "${{ steps.analysis.outputs.analysis_file }}"
    )
    assert 'git add -- "$ANALYSIS_FILE"' in commit_analysis["run"]
    assert "data/grades/*.analysis.md 2>/dev/null || true" not in (
        commit_analysis["run"]
    )
    assert "! -f \"$ANALYSIS_FILE\" || -L \"$ANALYSIS_FILE\"" in (
        commit_analysis["run"]
    )
    assert "${{ steps.analysis.outputs.analysis_file }}" in upload["with"]["path"]

    assert "steps.commit_grade.outputs.committed == 'true'" in retrigger["if"]
    assert "NEXT_CHUNK=$(( GRADE_RESUME_CHUNK + 1 ))" in retrigger["run"]
    assert "$NEXT_CHUNK -gt 10" in retrigger["run"]
    dispatch = _auto_resume_dispatch(retrigger["run"])
    assert dispatch["ref"] == "main"
    assert dispatch["inputs"]["inference_revision"] == "resolved-revision"
    assert dispatch["inputs"]["tasks_limit"] == "17"
    assert dispatch["inputs"]["paid_approval"] == "true"
    # A handoff that resumed as a fresh dry run would report success having
    # graded nothing, and one that did not resume would regrade from zero.
    assert dispatch["inputs"]["dry_run"] == "false"
    assert dispatch["inputs"]["force"] == "false"
    assert dispatch["inputs"]["resume"] == "true"
    assert dispatch["inputs"]["resume_chunk"] == "4"

    assert workflow.index("- name: Validate workflow context and inputs") < workflow.index(
        "- name: Checkout exact main revision"
    )
    assert "resume_chunk must be between 0 and 10" in workflow
    assert "resume requires the pinned inference_revision" in workflow
    assert "force and resume are mutually exclusive" in workflow
    assert dispatch["inputs"]["experiment_yaml"] == "exp-under-test"
    assert dispatch["inputs"]["grading_config"] == "config-under-test.yaml"
    assert '--revision "${{ inputs.inference_revision }}"' not in workflow


def _auto_resume_dispatch(script: str) -> dict:
    """Return the body the auto-resume step would POST, by running its builder.

    This used to be a ``gh workflow run`` invocation whose ``-f`` flags could
    be read straight out of the YAML. gh is not in the grading image, so it is
    a curl POST now and the readable artefact is the JSON rather than the
    command line. Executing the builder instead of grepping it is the point:
    grep cannot tell a misspelled environment variable from a correct one, and
    that misspelling would strand an rc=7 chunk with its budget already spent.
    """
    match = re.search(r"python - <<'PY'[^\n]*\n(.*?)\nPY\n", script, re.DOTALL)
    assert match is not None, "auto-resume payload builder not found"

    completed = subprocess.run(
        [sys.executable, "-c", match.group(1)],
        capture_output=True,
        text=True,
        check=True,
        env={
            "GITHUB_REF_NAME": "main",
            "GRADE_EXPERIMENT_YAML": "exp-under-test",
            "GRADE_CONFIG": "config-under-test.yaml",
            "RESOLVED_INFERENCE_REVISION": "resolved-revision",
            "GRADE_TASKS_LIMIT": "17",
            "GRADE_PAID_APPROVAL": "true",
            "NEXT_CHUNK": "4",
            "GRADE_SHARD_COUNT": "9",
            "GRADE_SHARD_INDEX": "6",
            "GRADE_RUN_ORDINAL": "3",
        },
    )
    payload = json.loads(completed.stdout)
    # The dispatch API takes booleans as strings, which is what gh sent. A
    # real bool here is a 422 on the paid path.
    assert all(isinstance(value, str) for value in payload["inputs"].values())
    return payload


def _retry_loop_body(script: str) -> str:
    """Return the text between ``for attempt ...; do`` and its matching ``done``.

    Slicing on the loop rather than searching the whole script is the point:
    a guard that sits above the loop runs once and then the job pushes up to
    six times against trees it never looked at.
    """
    header = "for attempt in 1 2 3 4 5 6; do"
    start = script.index(header)
    indent = " " * (start - script.rindex("\n", 0, start) - 1)
    return script[start : script.index(f"\n{indent}done\n", start)]


def test_every_grade_push_retries_instead_of_dying_on_a_shard_race():
    """Nine shards push to one branch on purpose, so a rejection is traffic.

    Before the loop, the first rejection ended the job -- after the grading
    was already paid for -- and the auto-resume step gates on committed=true,
    so a multi-chunk shard stopped handing off as well. A few seconds of
    contention could cost a slice.

    What the loop must not do is turn a genuine disagreement into a retry.
    Two shards writing different bytes into one grade file conflict on
    rebase, and that stays fatal: only the push is retried, and the rebase
    runs bare so ``set -e`` still ends the step.
    """
    text = Path("../.github/workflows/grade-run.yml").read_text(encoding="utf-8")
    steps = {
        step["name"]: step
        for step in yaml.safe_load(text)["jobs"]["grade"]["steps"]
        if step.get("name")
    }
    pull = 'git pull --rebase origin "${GITHUB_REF_NAME}"'
    sites = {
        "Commit grade result": "could not push the grade file",
        "Merge shards into the final grade": "could not push the merged grade",
        "Commit analysis": "could not push the analysis",
    }

    for name, exhausted in sites.items():
        script = steps[name]["run"]
        body = _retry_loop_body(script)

        # Rebase then push, both inside the loop. A pull left outside it
        # would retry the same rejected push six times.
        assert pull in body, name
        assert "if git push; then" in body, name
        assert body.index(pull) < body.index("if git push; then"), name

        # Bare, so a conflicting rebase still ends the step.
        assert f"{pull} ||" not in script, name
        assert "rebase --abort" not in script, name

        # Nine shards that collide once will collide again on the same
        # schedule unless the wait is jittered.
        assert "RANDOM" in body, name
        assert "::warning::" in body, name

        # Exhausting the attempts is a failure, not a quiet success.
        assert f"::error::{exhausted}" in script, name
        assert script.index("done\n") < script.index(f"::error::{exhausted}"), name

    # The grade file is the one that carries paid work, so its post-rebase
    # guards -- the blob it committed is still the blob it is pushing, and
    # that blob still satisfies the schema -- belong to each attempt.
    commit = _retry_loop_body(steps["Commit grade result"]["run"])
    assert '[[ "$POST_REBASE_GRADE_BLOB_SHA" != "$GRADE_BLOB_SHA" ]]' in commit
    assert "validate_grade_payload(payload, schema)" in commit
    assert commit.index(pull) < commit.index("$POST_REBASE_GRADE_BLOB_SHA")
    assert commit.index("validate_grade_payload(payload, schema)") < commit.index(
        "if git push; then"
    )

    # committed=true drives the auto-resume dispatch. Emitting it on a push
    # that never landed would hand the next chunk a branch without its
    # predecessor's partial on it.
    grade_script = steps["Commit grade result"]["run"]
    assert grade_script.index('if [[ "$PUSHED" != "true" ]]') < grade_script.index(
        'echo "committed=true"'
    )

    # Nothing here may overwrite a sibling's work to get its own push through.
    # Scoped to the push lines: bare --force is step8_grade.py's own CLI flag
    # and appears legitimately elsewhere in this file.
    push_lines = [line.strip() for line in text.splitlines() if "git push" in line]
    assert len(push_lines) == len(sites)
    for line in push_lines:
        assert "--force" not in line, line
        assert " -f " not in line, line
    for forbidden in ("--force-with-lease", "--no-verify"):
        assert forbidden not in text, forbidden


def test_grade_checkout_stays_on_the_major_that_writes_extraheader_to_git_config():
    """The credentialed checkout and the extraheader guard have to move together.

    checkout v6 persists credentials to a separate file that .git/config only
    references through an includeIf entry, and ``git config --local`` does not
    expand includes. The guard below would stop finding the credential and
    abort the grade job -- on the paid path, after dispatch, for a reason that
    looks nothing like an action bump. Nothing else in the repository couples
    a pin to a shell assertion, so nothing else would catch it.
    """
    text = Path("../.github/workflows/grade-run.yml").read_text(encoding="utf-8")
    parsed = yaml.safe_load(text)
    steps = {
        step["name"]: step
        for step in parsed["jobs"]["grade"]["steps"]
        if step.get("name")
    }
    name = "Checkout exact main revision"
    checkout = steps[name]
    guard = steps["Verify checked out main and input files"]["run"]

    assert checkout["with"]["persist-credentials"] is True

    # grade-run.yml checks out twice on the same pin, and only this one keeps
    # credentials, so the version comment has to be read from this step's own
    # block rather than from the first match in the file. The trailing newline
    # is load-bearing: the other step is named "<this> (read-only)", so an
    # unterminated anchor matches it first and reads the wrong pin.
    start = text.index(f"- name: {name}\n")
    block = text[start:text.index("- name:", start + 1)]
    pinned = re.search(
        rf"uses:\s*{re.escape(checkout['uses'])}\s*#\s*v(?P<major>\d+)\.\d+\.\d+",
        block,
    )
    assert pinned is not None, "the credentialed checkout pin needs a # vX.Y.Z comment"
    assert pinned.group("major") == "5"

    # The guard reads one file with includes off. If it ever gains --includes,
    # or reads the credentials config directly, this test has done its job and
    # the major above is free to move with it.
    assert "git config --local --name-only --get-regexp" in guard
    assert "extraheader" in guard
    assert "--includes" not in guard


def _run_grade_workflow_input_preflight(**overrides):
    workflow = yaml.safe_load(
        Path("../.github/workflows/grade-run.yml").read_text(encoding="utf-8")
    )
    validate_step = next(
        step
        for step in workflow["jobs"]["validate-request"]["steps"]
        if step.get("name") == "Validate workflow context and inputs"
    )
    sha = "a" * 40
    env = {
        **os.environ,
        "GITHUB_REPOSITORY": "owner/repository",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_REF_NAME": "main",
        "GITHUB_WORKFLOW_REF": (
            "owner/repository/.github/workflows/grade-run.yml@refs/heads/main"
        ),
        "GITHUB_SHA": sha,
        "GITHUB_WORKFLOW_SHA": sha,
        "GRADE_EXPERIMENT_YAML": "exp998_smoke_baseline_sample",
        "GRADE_CONFIG": "default_gpt5pro.yaml",
        "GRADE_INFERENCE_REVISION": "",
        "GRADE_FORCE": "false",
        "GRADE_TASKS_LIMIT": "0",
        "GRADE_DRY_RUN": "true",
        "GRADE_PAID_APPROVAL": "false",
        "GRADE_RESUME": "false",
        "GRADE_RESUME_CHUNK": "0",
        "GRADE_SHARD_COUNT": "1",
        "GRADE_SHARD_INDEX": "0",
        "GRADE_RUN_ORDINAL": "1",
        **overrides,
    }
    return subprocess.run(
        ["bash", "-c", validate_step["run"]],
        check=False,
        capture_output=True,
        env=env,
        text=True,
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {},
        {
            "GRADE_INFERENCE_REVISION": "b" * 40,
            "GRADE_DRY_RUN": "false",
            "GRADE_PAID_APPROVAL": "true",
            "GRADE_RESUME": "true",
            "GRADE_RESUME_CHUNK": "1",
        },
        # A shard at the top of the allowed range, mid-relay: the two features
        # have to compose, because an 11-way split still needs rc=7 chunking.
        {
            "GRADE_INFERENCE_REVISION": "b" * 40,
            "GRADE_DRY_RUN": "false",
            "GRADE_PAID_APPROVAL": "true",
            "GRADE_RESUME": "true",
            "GRADE_RESUME_CHUNK": "1",
            "GRADE_SHARD_COUNT": "11",
            "GRADE_SHARD_INDEX": "10",
        },
        # The top repeat, dry: previewing a repeat has to be as free as
        # previewing the run it repeats, or the only way to check the path is
        # to pay for it.
        {"GRADE_RUN_ORDINAL": "10"},
        # A repeat that is also sharded and mid-relay. All three forks stack in
        # the output path, so all three have to be dispatchable at once --
        # otherwise a repeat too long for one four-hour chunk cannot be run at
        # all, and stage 2 needs three of them.
        {
            "GRADE_INFERENCE_REVISION": "b" * 40,
            "GRADE_DRY_RUN": "false",
            "GRADE_PAID_APPROVAL": "true",
            "GRADE_RESUME": "true",
            "GRADE_RESUME_CHUNK": "2",
            "GRADE_SHARD_COUNT": "3",
            "GRADE_SHARD_INDEX": "2",
            "GRADE_RUN_ORDINAL": "3",
        },
    ],
)
def test_grade_workflow_input_preflight_accepts_valid_dispatch(overrides):
    result = _run_grade_workflow_input_preflight(**overrides)

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    ("overrides", "error"),
    [
        ({"GITHUB_REF": "refs/heads/feature"}, "dispatched from main"),
        ({"GITHUB_WORKFLOW_SHA": "b" * 40}, "workflow and event SHA"),
        ({"GRADE_EXPERIMENT_YAML": "../escape"}, "experiment_yaml"),
        ({"GRADE_EXPERIMENT_YAML": "exp.yaml"}, "experiment_yaml"),
        ({"GRADE_CONFIG": "../config.yaml"}, "grading_config"),
        ({"GRADE_INFERENCE_REVISION": "A" * 40}, "inference_revision"),
        ({"GRADE_FORCE": "yes"}, "GRADE_FORCE"),
        ({"GRADE_PAID_APPROVAL": "yes"}, "GRADE_PAID_APPROVAL"),
        ({"GRADE_DRY_RUN": "false"}, "requires paid_approval=true"),
        ({"GRADE_PAID_APPROVAL": "true"}, "must not request paid approval"),
        ({"GRADE_TASKS_LIMIT": "01"}, "tasks_limit"),
        ({"GRADE_TASKS_LIMIT": "221"}, "tasks_limit"),
        ({"GRADE_RESUME_CHUNK": "11"}, "resume_chunk"),
        (
            {
                "GRADE_FORCE": "true",
                "GRADE_RESUME": "true",
                "GRADE_INFERENCE_REVISION": "b" * 40,
            },
            "mutually exclusive",
        ),
        ({"GRADE_RESUME": "true"}, "resume requires"),
        ({"GRADE_RESUME_CHUNK": "1"}, "resume_chunk must be 0"),
        ({"GRADE_SHARD_COUNT": "0"}, "shard_count"),
        ({"GRADE_SHARD_COUNT": "12"}, "shard_count"),
        ({"GRADE_SHARD_COUNT": "01"}, "shard_count"),
        ({"GRADE_SHARD_INDEX": "11"}, "shard_index"),
        ({"GRADE_SHARD_INDEX": "-1"}, "shard_index"),
        # An index at or past the count would grade a slice nothing else covers,
        # or none at all -- either way the merged set is silently incomplete.
        ({"GRADE_SHARD_COUNT": "3", "GRADE_SHARD_INDEX": "3"}, "must be less than"),
        ({"GRADE_SHARD_INDEX": "1"}, "must be less than"),
        # Sharding splits the corpus; --limit narrows it into a _diagnostic/
        # subtree nothing merges. Combining them loses tasks with no error.
        (
            {"GRADE_SHARD_COUNT": "2", "GRADE_TASKS_LIMIT": "5"},
            "cannot be combined with tasks_limit",
        ),
        # step8 caps repeats at MAX_RUN_ORDINAL. An ordinal past it is refused
        # here rather than after the runner has been paid for and started, and
        # 0 is refused rather than silently meaning "the original".
        ({"GRADE_RUN_ORDINAL": "0"}, "run_ordinal"),
        ({"GRADE_RUN_ORDINAL": "11"}, "run_ordinal"),
        ({"GRADE_RUN_ORDINAL": "-1"}, "run_ordinal"),
        # "01" reads as 1 to a shell comparison and as a different directory
        # name to the grader, which is how two runs end up in one file.
        ({"GRADE_RUN_ORDINAL": "01"}, "run_ordinal"),
        ({"GRADE_RUN_ORDINAL": ""}, "run_ordinal"),
    ],
)
def test_grade_workflow_input_preflight_rejects_invalid_dispatch(overrides, error):
    result = _run_grade_workflow_input_preflight(**overrides)

    assert result.returncode != 0
    assert error in result.stdout


def test_completed_cost_sweep_workflow_is_archived():
    active_path = Path("../.github/workflows/grade-cost-sweep.yml")
    archive_dir = Path(
        "../tasks/0523_saturday/cost_opt_results/2026-05-24-grade-cost-sweep"
    )
    archive_path = archive_dir / "grade-cost-sweep.workflow.yml"
    status_path = archive_dir / "STATUS.md"

    assert not active_path.exists()
    assert archive_path.is_file()
    archived = yaml.safe_load(archive_path.read_text(encoding="utf-8"))
    assert archived["name"] == "Run Grading Cost Optimization Sweep"
    status = status_path.read_text(encoding="utf-8")
    assert status.startswith("# Sweep Orchestration Status (Archived)\n")
    assert "Archived 2026-07-22" in status
    assert "## Historical Inspection Commands" in status
    assert "## Historical Phase Decision Tree" in status
    assert "Historical Trigger Commands (Do Not Run)" in status
    assert "## Historical Cost and Limits" in status


def test_time_budget_zero_disables_guard(monkeypatch, tmp_path):
    """GRADER_TIME_BUDGET_SEC=0 must disable the deadline check entirely
    (escape hatch for self-hosted runners or debugging)."""
    _setup_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    monkeypatch.setattr(s8, "Grader", _FakeGrader)

    monkeypatch.setenv("GRADER_TIME_BUDGET_SEC", "0")
    monkeypatch.setattr("sys.argv", [
        "step8_grade.py", "exp998_smoke_baseline_sample",
        "--config", "grading_configs/default.yaml",
        "--force",
    ])
    rc = s8.main()
    assert rc == 0


# ---------------------------------------------------------------------------
# Sharded grading (--shard-count / --shard-index)
#
# The 220-task corpus projects to ~71.6h of serial judge latency against a 44h
# relay envelope. Sharding splits the *workload* across N workers while every
# shard keeps declaring the *full* corpus identity, so step9_merge_shards.py
# can fold the partials back into one final payload. The tests below pin the
# two halves of that contract: identity must never shrink to the slice, and
# the slice must never leak into the diagnostic-isolation decision.
# ---------------------------------------------------------------------------

_CORPUS = ["task-001", "task-002", "task-003"]
_CANONICAL_STEM = "exp998_smoke_baseline_sample__gpt-5_4-pro__11e7900__v1"
_CANONICAL_GRADE = f"data/grades/{_CANONICAL_STEM}.json"


def _shard_grade_path(root: Path, index: int, count: int) -> Path:
    """Where a shard's partial lands.

    Shards share every identity input, so they would all resolve to the same
    canonical filename. The path -- and only the path -- forks below it, so that
    N concurrent jobs can each commit their own file and so the dashboard's
    non-recursive `data/grades/*.json` glob never sees an unfinished slice.
    """
    return (
        root
        / "data"
        / "grades"
        / "_shards"
        / _CANONICAL_STEM
        / f"shard-{index:03d}-of-{count:03d}.json"
    )


def _shard_argv(index: int, count: int, *extra: str) -> list[str]:
    return [
        "step8_grade.py", "exp998_smoke_baseline_sample",
        "--config", "grading_configs/default.yaml",
        "--shard-index", str(index),
        "--shard-count", str(count),
        *extra,
    ]


@pytest.mark.parametrize(
    "candidate",
    [
        [],                                  # nothing graded yet
        ["task-001"],                        # prefix (serial resume)
        ["task-001", "task-002"],            # longer prefix
        ["task-001", "task-002", "task-003"],  # complete
        ["task-001", "task-003"],            # stride slice, shard 0 of 2
        ["task-002"],                        # stride slice, shard 1 of 2
        ["task-003"],                        # suffix
    ],
)
def test_is_ordered_subsequence_accepts_prefixes_and_stride_slices(candidate):
    """Serial resume produces a prefix; a shard produces a stride slice. Both
    are ordered subsequences, and widening prefix->subsequence must not
    regress any prefix that already validated."""
    assert s8._is_ordered_subsequence(candidate, _CORPUS) is True


@pytest.mark.parametrize(
    "candidate",
    [
        ["task-002", "task-001"],            # reordered
        ["task-003", "task-001"],            # reversed stride
        ["task-001", "task-004"],            # foreign id
        ["task-001", "task-001"],            # repeat beyond one occurrence
        ["task-001", "task-002", "task-003", "task-001"],  # wraparound
    ],
)
def test_is_ordered_subsequence_rejects_reordered_or_foreign(candidate):
    assert s8._is_ordered_subsequence(candidate, _CORPUS) is False


def test_shard_slice_partitions_the_corpus_without_loss_or_overlap():
    """Union of all shards == corpus, shards are disjoint, and each shard
    preserves canonical relative order (which is what makes each partial an
    ordered subsequence)."""
    tasks = [{"task_id": f"task-{i:03d}"} for i in range(220)]
    for count in (1, 2, 3, 7, 9, 11, 220):
        shards = [
            s8._shard_slice(tasks, shard_index=i, shard_count=count)
            for i in range(count)
        ]
        seen: list[dict] = []
        for shard in shards:
            positions = [tasks.index(task) for task in shard]
            assert positions == sorted(positions), "shard lost canonical order"
            seen.extend(shard)
        ids = [task["task_id"] for task in seen]
        assert sorted(ids) == sorted(t["task_id"] for t in tasks)
        assert len(ids) == len(set(ids)), "shards overlap"
        # Stride keeps sizes within one of each other; contiguous blocks would
        # not, which is the whole reason stride was chosen.
        sizes = [len(shard) for shard in shards]
        assert max(sizes) - min(sizes) <= 1


def test_shard_slice_unsharded_returns_a_copy_not_the_original():
    tasks = [{"task_id": "task-001"}]
    result = s8._shard_slice(tasks, shard_index=0, shard_count=1)
    assert result == tasks
    assert result is not tasks


@pytest.mark.parametrize(
    "flags",
    [
        ["--shard-count", "0"],
        ["--shard-count", "-1"],
        ["--shard-index", "-1"],
        ["--shard-index", "2", "--shard-count", "2"],
        ["--shard-index", "9", "--shard-count", "9"],
    ],
)
def test_parse_args_rejects_out_of_range_shard_flags(monkeypatch, flags):
    monkeypatch.setattr("sys.argv", [
        "step8_grade.py", "exp998_smoke_baseline_sample",
        "--config", "grading_configs/default.yaml", *flags,
    ])
    with pytest.raises(SystemExit) as excinfo:
        s8.parse_args()
    assert excinfo.value.code == 2


def test_parse_args_shard_defaults_are_serial(monkeypatch):
    monkeypatch.setattr("sys.argv", [
        "step8_grade.py", "exp998_smoke_baseline_sample",
        "--config", "grading_configs/default.yaml",
    ])
    args = s8.parse_args()
    assert args.shard_count == 1
    assert args.shard_index == 0


@pytest.mark.parametrize(
    "index,expected",
    [(0, ["task-001", "task-003"]), (1, ["task-002"])],
)
def test_shard_grades_only_its_stride_slice(monkeypatch, tmp_path, index, expected):
    _setup_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    monkeypatch.setattr(s8, "Grader", _FakeGrader)
    monkeypatch.setattr("sys.argv", _shard_argv(index, 2, "--force"))

    assert s8.main() == 0
    payload = json.loads(
        _shard_grade_path(tmp_path, index, 2).read_text(encoding="utf-8")
    )
    assert [task["task_id"] for task in payload["tasks"]] == expected


def test_shard_payload_declares_full_corpus_identity(monkeypatch, tmp_path):
    """The identity fields describe the corpus, not the slice -- this is what
    lets step9 verify it merged every shard, and what keeps all shards on one
    cache key."""
    _setup_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    monkeypatch.setattr(s8, "Grader", _FakeGrader)
    monkeypatch.setattr("sys.argv", _shard_argv(0, 2, "--force"))

    assert s8.main() == 0
    payload = json.loads(
        _shard_grade_path(tmp_path, 0, 2).read_text(encoding="utf-8")
    )
    assert payload["run_status"] == "partial"
    assert payload["expected_task_count"] == len(_CORPUS)
    assert payload["expected_ordered_task_ids_sha256"] == (
        s8._ordered_task_ids_sha256(_CORPUS)
    )
    assert len(payload["tasks"]) < payload["expected_task_count"]


def test_sharding_is_not_a_diagnostic_task_selection(monkeypatch, tmp_path):
    """--shard-* narrows who grades what, not what is in scope. It must never
    fork the output into _diagnostic/<scope_sha>/ the way --tasks/--limit do:
    that directory means "this run graded a narrowed corpus and its scores are
    not comparable", which is exactly the claim sharding must not make."""
    _setup_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    monkeypatch.setattr(s8, "Grader", _FakeGrader)
    monkeypatch.setattr("sys.argv", _shard_argv(0, 2, "--force"))

    assert s8.main() == 0
    assert _shard_grade_path(tmp_path, 0, 2).exists()
    assert not (tmp_path / "data/grades/_diagnostic").exists()
    assert not _diagnostic_grade_path(tmp_path, ["task-001", "task-003"]).exists()
    # The canonical name stays free -- it belongs to the merged final, and the
    # dashboard aggregator globs exactly that level.
    assert not (tmp_path / _CANONICAL_GRADE).exists()


def test_sharded_legacy_provenance_run_with_complete_pin_stays_publishable(
    monkeypatch, tmp_path
):
    """The exp003 production path: pre-sidecar source, complete pin, N shards.

    Three things have to hold at once here, and each one is a separate reason a
    run could get demoted to `_diagnostic/`: the missing sidecar, the pinned
    task list, and the shard slice. None of them narrowed the graded corpus, so
    the shards stay on the canonical `_shards/` path that step9 merges into a
    final grade.
    """
    _setup_workspace(tmp_path)
    inference_path = tmp_path / "workspace/step2_inference_results.json"
    inference = json.loads(inference_path.read_text(encoding="utf-8"))
    inference["azure_ai_provenance_status"] = "legacy-missing"
    inference_path.write_text(json.dumps(inference), encoding="utf-8")

    config_path = tmp_path / "grading_configs" / "default.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["schema_version"] = "2.0"
    config["rubric"]["revision"] = _FakeLoader().rubric_sha
    config["rerun_identity"] = {
        "experiment_id": "exp998_smoke_baseline_sample",
        "expected_task_count": len(_CORPUS),
        "rubric_commit_sha": _FakeLoader().rubric_sha,
        "inference_revision": INFERENCE_SHA,
        "task_ids": list(_CORPUS),
        "allow_legacy_missing_provenance": True,
    }
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    monkeypatch.setattr(s8, "Grader", _FakeGrader)

    for index in (0, 1):
        monkeypatch.setattr("sys.argv", _shard_argv(index, 2, "--force"))
        assert s8.main() == 0

    assert not (tmp_path / "data/grades/_diagnostic").exists()
    graded: list[str] = []
    for index in (0, 1):
        payload = json.loads(
            _shard_grade_path(tmp_path, index, 2).read_text(encoding="utf-8")
        )
        assert payload["run_status"] == "partial"
        assert payload["expected_task_count"] == len(_CORPUS)
        assert payload["source_azure_ai_provenance_status"] == "legacy-missing"
        graded.extend(task["task_id"] for task in payload["tasks"])

    assert sorted(graded) == sorted(_CORPUS)


def test_shard_path_forks_below_the_canonical_name(monkeypatch, tmp_path):
    """The shard filename must stay derivable from the canonical one. step9's
    output is named by the caller, but a human reading data/grades/_shards/ has
    to be able to tell which run these partials belong to."""
    _setup_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    monkeypatch.setattr(s8, "Grader", _FakeGrader)
    github_output = tmp_path / "github-output.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(github_output))
    monkeypatch.setattr("sys.argv", _shard_argv(2, 11, "--force"))

    assert s8.main() == 0
    out = _shard_grade_path(tmp_path, 2, 11)
    assert out.exists()
    assert out.parent.name == _CANONICAL_STEM
    assert out.name == "shard-002-of-011.json"
    # grade-run.yml commits whatever path this reports, so it has to be the
    # shard's file and repo-relative.
    assert (
        f"grade_file=data/grades/_shards/{_CANONICAL_STEM}/shard-002-of-011.json"
        in github_output.read_text(encoding="utf-8")
    )


def test_shard_paths_are_unique_per_index():
    """The collision this fork exists to prevent: N jobs, one file.

    Every shard shares its identity inputs by construction -- that sameness is
    what step9 verifies before merging -- so `resolve_grade_output_path` is the
    only place the paths can diverge.
    """
    config = {
        "config_name": "default_gpt5pro",
        "output": {
            "directory": "data/grades",
            "filename_template": "{exp_id}__{judge_slug}__{rubric_short_sha}__{prompt_v}.json",
        },
    }
    identity = dict(
        experiment_id="exp998_smoke_baseline_sample",
        judge_slug="gpt-5_4-pro",
        config_hash="c" * 64,
        rubric_sha="1" * 40,
        rubric_short_sha="11e7900",
        prompt_version="v1",
        inference_sha="2" * 40,
        grader_source_hash="3" * 64,
    )

    paths = [
        s8.resolve_grade_output_path(
            config, **identity, shard_index=index, shard_count=11
        )
        for index in range(11)
    ]
    assert len(set(paths)) == 11
    assert len({path.parent for path in paths}) == 1
    serial = s8.resolve_grade_output_path(config, **identity)
    assert serial not in paths
    assert paths[0].parent.parent.name == "_shards"
    # Zero-padded so `ls` sorts them in shard order rather than 0, 1, 10, 2.
    assert [path.name for path in paths][:3] == [
        "shard-000-of-011.json",
        "shard-001-of-011.json",
        "shard-002-of-011.json",
    ]


@pytest.mark.parametrize(
    "index,count",
    [(-1, 2), (2, 2), (5, 2), (0, 0), (0, -1)],
)
def test_resolve_grade_output_path_rejects_impossible_shards(index, count):
    """Defence in depth: parse_args already rejects these, but the path helper
    is public and a bad pair here would silently overwrite a sibling's file."""
    config = {
        "config_name": "default_gpt5pro",
        "output": {
            "directory": "data/grades",
            "filename_template": "{exp_id}__{judge_slug}__{rubric_short_sha}__{prompt_v}.json",
        },
    }
    with pytest.raises(ValueError, match="shard_index must satisfy"):
        s8.resolve_grade_output_path(
            config,
            experiment_id="exp998_smoke_baseline_sample",
            judge_slug="gpt-5_4-pro",
            config_hash="c" * 64,
            rubric_sha="1" * 40,
            rubric_short_sha="11e7900",
            prompt_version="v1",
            inference_sha="2" * 40,
            grader_source_hash="3" * 64,
            shard_index=index,
            shard_count=count,
        )


def test_shard_reports_partial_grade_status_to_github_output(monkeypatch, tmp_path):
    """grade-run.yml gates the committed artifact on this value; a shard's
    file is a partial even when the process exits 0."""
    _setup_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    github_output = tmp_path / "github-output.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(github_output))
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    monkeypatch.setattr(s8, "Grader", _FakeGrader)
    monkeypatch.setattr("sys.argv", _shard_argv(0, 2, "--force"))

    assert s8.main() == 0
    assert "grade_status=partial" in github_output.read_text(encoding="utf-8")


def test_unsharded_run_still_emits_final(monkeypatch, tmp_path):
    """Regression guard: the shard flags default to serial, and serial must be
    byte-for-byte the behaviour that existed before sharding."""
    _setup_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    github_output = tmp_path / "github-output.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(github_output))
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    monkeypatch.setattr(s8, "Grader", _FakeGrader)
    monkeypatch.setattr("sys.argv", [
        "step8_grade.py", "exp998_smoke_baseline_sample",
        "--config", "grading_configs/default.yaml", "--force",
    ])

    assert s8.main() == 0
    payload = json.loads((tmp_path / _CANONICAL_GRADE).read_text(encoding="utf-8"))
    assert payload["run_status"] == "final"
    assert [task["task_id"] for task in payload["tasks"]] == _CORPUS
    assert "grade_status=final" in github_output.read_text(encoding="utf-8")


def test_shard_dry_run_counts_only_its_slice(monkeypatch, tmp_path, capsys):
    _setup_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    monkeypatch.setattr("sys.argv", _shard_argv(0, 2, "--dry-run"))

    assert s8.main() == 0
    assert "Dry-run tasks=2" in capsys.readouterr().out


def test_shard_cache_hit_skips_when_partial_is_its_own_slice(monkeypatch, tmp_path, capsys):
    _setup_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    monkeypatch.setattr(s8, "Grader", _FakeGrader)
    _seed_partial_grade(
        tmp_path, ["task-001", "task-003"], out=_shard_grade_path(tmp_path, 0, 2)
    )
    monkeypatch.setattr("sys.argv", _shard_argv(0, 2))

    assert s8.main() == 0
    assert "SKIP - exists" in capsys.readouterr().out


def test_shard_cache_hit_refuses_a_sibling_shards_partial(monkeypatch, tmp_path, capsys):
    """Belt and braces. The `_shards/shard-i-of-n.json` fork should make this
    unreachable in practice, but a stale or hand-copied file at shard 0's path
    must never be mistaken for shard 0's own work -- that would silently drop
    1/N of the corpus while reporting success."""
    _setup_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    monkeypatch.setattr(s8, "Grader", _FakeGrader)
    # shard 1's slice, planted at shard 0's path
    _seed_partial_grade(
        tmp_path, ["task-002"], out=_shard_grade_path(tmp_path, 0, 2)
    )
    monkeypatch.setattr("sys.argv", _shard_argv(0, 2))

    assert s8.main() == 1
    assert "belongs to a different shard" in capsys.readouterr().err


def test_shard_resume_refuses_a_partial_holding_foreign_tasks(monkeypatch, tmp_path, capsys):
    """A short partial is normal when resuming; one containing tasks outside
    this shard's slice means we picked up the wrong file and would double-count
    on merge."""
    _setup_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    monkeypatch.setattr(s8, "Grader", _FakeGrader)
    _seed_partial_grade(
        tmp_path, ["task-001", "task-002"], out=_shard_grade_path(tmp_path, 0, 2)
    )
    monkeypatch.setattr("sys.argv", _shard_argv(0, 2, "--resume"))

    assert s8.main() == 1
    assert "outside --shard-index 0" in capsys.readouterr().err


def test_shard_resume_continues_from_its_own_short_partial(monkeypatch, tmp_path):
    _setup_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    grader_instance = {}

    class _TrackGrader(_FakeGrader):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            grader_instance["g"] = self

    monkeypatch.setattr(s8, "Grader", _TrackGrader)
    _seed_partial_grade(
        tmp_path, ["task-001"], out=_shard_grade_path(tmp_path, 0, 2)
    )
    monkeypatch.setattr("sys.argv", _shard_argv(0, 2, "--resume"))

    assert s8.main() == 0
    assert grader_instance["g"].calls == 1  # only task-003 remains for shard 0
    payload = json.loads(
        _shard_grade_path(tmp_path, 0, 2).read_text(encoding="utf-8")
    )
    assert [task["task_id"] for task in payload["tasks"]] == ["task-001", "task-003"]
    assert payload["run_status"] == "partial"


def test_all_shards_together_cover_the_corpus_exactly(monkeypatch, tmp_path):
    """End-to-end partition check through main(): run every shard of a 3-way
    split into its own directory and confirm the union is the whole corpus."""
    graded: list[str] = []
    for index in range(3):
        shard_dir = tmp_path / f"shard{index}"
        shard_dir.mkdir()
        _setup_workspace(shard_dir)
        monkeypatch.chdir(shard_dir)
        monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
        monkeypatch.setattr(s8, "Grader", _FakeGrader)
        monkeypatch.setattr("sys.argv", _shard_argv(index, 3, "--force"))

        assert s8.main() == 0
        payload = json.loads(
            _shard_grade_path(shard_dir, index, 3).read_text(encoding="utf-8")
        )
        assert payload["run_status"] == "partial"
        assert payload["expected_task_count"] == len(_CORPUS)
        graded.extend(task["task_id"] for task in payload["tasks"])

    assert sorted(graded) == _CORPUS
    assert len(graded) == len(set(graded))


def test_grade_workflow_wires_shards_end_to_end():
    """Pin the dispatch surface that turns step8's `--shard-*` flags into N
    parallel paid relays.

    step8 can slice and step9 can merge, but neither is reachable unless the
    workflow passes the flags through, keeps concurrent shards from serialising
    each other, and arranges for exactly one of them to assemble the final. This
    test guards that wiring, because every failure mode here is expensive: a
    dropped flag double-grades the corpus, a wrong concurrency key silently
    turns N shards back into a queue, and a mis-gated analysis publishes a
    reading of 1/N of the corpus as if it were the whole run.
    """
    workflow = Path("../.github/workflows/grade-run.yml").read_text(
        encoding="utf-8"
    )
    parsed = yaml.safe_load(workflow)
    # YAML 1.1 parses a bare `on:` key as the boolean True.
    trigger = parsed.get("on", parsed.get(True))
    inputs = trigger["workflow_dispatch"]["inputs"]

    assert inputs["shard_count"]["default"] == 1
    assert inputs["shard_index"]["default"] == 0
    assert inputs["shard_count"]["required"] is False
    assert inputs["shard_index"]["required"] is False

    # Chunks of the SAME shard must serialise -- they resume from one partial
    # file. Different shards must NOT, or sharding buys nothing. Hence the key
    # carries shard_index and deliberately not shard_count.
    concurrency = parsed["concurrency"]["group"]
    assert "inputs.shard_index" in concurrency
    assert "inputs.shard_count" not in concurrency
    assert parsed["concurrency"]["cancel-in-progress"] is False

    validate = next(
        step
        for step in parsed["jobs"]["validate-request"]["steps"]
        if step.get("name") == "Validate workflow context and inputs"
    )
    assert "shard_count must be an integer between 1 and 11" in validate["run"]
    assert "shard_index must be an integer between 0 and 10" in validate["run"]
    assert "must be less than shard_count" in validate["run"]
    # --limit forks the output into _diagnostic/<scope_sha>/, where nothing
    # merges. The two features must never combine.
    assert "shard_count > 1 cannot be combined with tasks_limit" in (
        validate["run"]
    )

    steps = parsed["jobs"]["grade"]["steps"]
    by_name = {step.get("name"): step for step in steps if step.get("name")}
    order = [step.get("name") for step in steps]

    shard_args = (
        'ARGS+=(--shard-count "$GRADE_SHARD_COUNT" '
        '--shard-index "$GRADE_SHARD_INDEX")'
    )
    grade_job = parsed["jobs"]["grade"]
    assert grade_job["env"]["GRADE_SHARD_COUNT"] == "${{ inputs.shard_count }}"
    assert grade_job["env"]["GRADE_SHARD_INDEX"] == "${{ inputs.shard_index }}"
    assert shard_args in by_name["Run grading"]["run"]
    # The dry run must preview this shard's slice too, or its task count says
    # nothing about the paid run it is meant to authorise.
    dry_classify = next(
        step
        for step in parsed["jobs"]["grade-dry-run"]["steps"]
        if step.get("name") == "Classify grading work only"
    )
    assert shard_args in dry_classify["run"]

    # An rc=7 chunk hands off to the next chunk OF THE SAME SHARD. Losing the
    # shard flags here would resume the remainder as an unsharded run.
    retrigger = by_name["Auto-retrigger next chunk (time budget hit)"]
    resume_inputs = _auto_resume_dispatch(retrigger["run"])["inputs"]
    assert resume_inputs["shard_count"] == "9"
    assert resume_inputs["shard_index"] == "6"
    # ...and OF THE SAME REPEAT. A repeat's partial lives under _repeats/, so
    # an ordinal dropped here resumes into run 1's path and either is refused
    # or overwrites the run this one exists to be compared against.
    assert resume_inputs["run_ordinal"] == "3"

    merge = by_name["Merge shards into the final grade"]
    assert merge["id"] == "merge_shards"
    assert "inputs.shard_count > 1" in merge["if"]
    assert "steps.grade.outputs.rc == '0'" in merge["if"]
    # Merge only after pulling, or "is every sibling published?" is answered
    # against a stale checkout and no shard ever sees a complete set.
    assert merge["run"].index(
        'git pull --rebase origin "${GITHUB_REF_NAME}"'
    ) < merge["run"].index("step9_merge_shards.py")
    assert "data/grades/" in merge["run"]
    assert "*/_shards/*" in merge["run"]
    assert "shard-%03d-of-%03d.json" in merge["run"]
    # Path guards: no traversal, no newline injection, no symlinked directory
    # or output. The shard path comes from step8, but the merge step is what
    # decides where a `final` grade gets written and committed.
    assert '== *..*' in merge["run"]
    assert "-L \"$SHARD_DIR\"" in merge["run"]
    assert '-L "$FINAL_FILE"' in merge["run"]
    assert '-L "$candidate"' in merge["run"]
    assert 'echo "merged=false"' in merge["run"]
    assert 'echo "merged=true"' in merge["run"]
    # A partial slice must never be published as a final grade.
    assert "from core.grade_payload import validate_grade_payload" in (
        merge["run"]
    )
    assert 'payload.get("run_status") != "final"' in merge["run"]
    assert 'payload.get("expected_task_count")' in merge["run"]
    # Two shards can reach the merge concurrently; step9 is deterministic, so
    # the loser rewrites an identical file and --force keeps it from erroring.
    assert "--force" in merge["run"]
    assert "git diff --staged --quiet" in merge["run"]
    # Shard files exist from the first resume chunk onward, so "all N files
    # present" does not mean "all N slices complete". Every shard that
    # finishes a chunk reaches this step and all but the last find a short
    # union -- a routine state that must not fail the job, or a healthy run
    # goes red and a genuine stall becomes indistinguishable from the noise.
    import step9_merge_shards

    assert "--defer-if-incomplete" in merge["run"]
    assert f'"$merge_rc" -eq {step9_merge_shards.DEFER_EXIT_CODE}' in (
        merge["run"]
    )
    # ...and the deferring shard must stand down without claiming it merged,
    # or the analysis step would run against a non-existent final grade.
    defer_branch = merge["run"].index(
        f'"$merge_rc" -eq {step9_merge_shards.DEFER_EXIT_CODE}'
    )
    assert merge["run"].index('echo "merged=false"', defer_branch) < merge[
        "run"
    ].index('echo "merged=true"')
    # Any other non-zero exit is still a failure. Deferral is the exception,
    # not a blanket softening of the merge guards.
    assert '"$merge_rc" -ne 0' in merge["run"]
    assert order.index("Commit grade result") < order.index(
        "Merge shards into the final grade"
    )

    analysis = by_name["Auto-analyze (final chunk only)"]
    assert order.index("Merge shards into the final grade") < order.index(
        "Auto-analyze (final chunk only)"
    )
    assert "steps.merge_shards.outputs.merged == 'true'" in analysis["if"]
    assert "inputs.shard_count == 1 && steps.grade.outputs.rc == '0'" in (
        analysis["if"]
    )
    assert analysis["env"]["ANALYSIS_GRADE_FILE"] == (
        "${{ steps.merge_shards.outputs.grade_file || "
        "steps.grade.outputs.grade_file }}"
    )
    # Committing has to follow the analyze step exactly. Gating on rc alone
    # would fire on a shard that produced no analysis, and the emptiness guard
    # would then fail the job for correctly declining to analyse a fragment.
    assert by_name["Commit analysis"]["if"] == (
        "steps.analysis.outcome == 'success' && inputs.dry_run == false"
    )

    upload = by_name["Upload grade artifact"]
    assert "inputs.shard_index" in upload["with"]["name"]
    assert "${{ steps.merge_shards.outputs.grade_file }}" in (
        upload["with"]["path"]
    )
