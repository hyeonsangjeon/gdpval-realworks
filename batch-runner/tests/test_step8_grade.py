import json
import os
from pathlib import Path
import subprocess

import pytest
import yaml

import step8_grade as s8


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

    def __init__(self, config, rubric_loader):
        self.calls = 0
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
    assert payload["schema_version"] == "1.3"
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
        def __init__(self, config, rubric_loader):
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
) -> Path:
    """Drop a valid partial grade JSON at the templated output path."""
    out = tmp_path / "data/grades/exp998_smoke_baseline_sample__gpt-5_4-pro__11e7900__v1.json"
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
        "schema_version": "1.3",
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
    selected, pinned = s8.filter_tasks_for_config(
        _selection_inference(),
        _pinned_task_config(),
        tasks_csv=None,
        limit=0,
    )

    assert [task["task_id"] for task in selected] == ["task-002", "task-003"]
    assert pinned is True


def test_matching_cli_tasks_are_accepted_in_canonical_source_order():
    selected, pinned = s8.filter_tasks_for_config(
        _selection_inference(),
        _pinned_task_config(),
        tasks_csv="task-003,task-002",
        limit=2,
    )

    assert [task["task_id"] for task in selected] == ["task-002", "task-003"]
    assert pinned is True


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
    assert payload["schema_version"] == "1.3"
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
    assert approval_job["if"] == (
        "inputs.dry_run == false && inputs.paid_approval == true"
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
    assert "inputs.dry_run == false" in grade_job["if"]
    assert "inputs.paid_approval == true" in grade_job["if"]
    assert "needs.validate-request.result == 'success'" in grade_job["if"]
    assert "needs.approve-paid.result == 'success'" in grade_job["if"]
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
        "actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683"
    )
    assert checkout["with"] == {
        "ref": "main",
        "persist-credentials": True,
    }
    assert setup_python["uses"] == (
        "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065"
    )
    assert azure_login["uses"] == (
        "azure/login@a457da9ea143d694b1b9c7c869ebb04ebe844ef5"
    )
    assert upload["uses"] == (
        "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02"
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
    assert '-f inference_revision="$RESOLVED_INFERENCE_REVISION"' in retrigger["run"]
    assert '-f tasks_limit="$GRADE_TASKS_LIMIT"' in retrigger["run"]
    assert '-f paid_approval="$GRADE_PAID_APPROVAL"' in retrigger["run"]

    assert workflow.index("- name: Validate workflow context and inputs") < workflow.index(
        "- name: Checkout exact main revision"
    )
    assert "resume_chunk must be between 0 and 10" in workflow
    assert "resume requires the pinned inference_revision" in workflow
    assert "force and resume are mutually exclusive" in workflow
    assert '-f experiment_yaml="$GRADE_EXPERIMENT_YAML"' in retrigger["run"]
    assert '-f grading_config="$GRADE_CONFIG"' in retrigger["run"]
    assert '--revision "${{ inputs.inference_revision }}"' not in workflow


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
