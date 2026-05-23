import json
from pathlib import Path

import pytest
import yaml

import step8_grade as s8


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


def _setup_workspace(tmp_path: Path):
    (tmp_path / "experiments").mkdir(parents=True, exist_ok=True)
    (tmp_path / "workspace").mkdir(parents=True, exist_ok=True)
    (tmp_path / "prompts").mkdir(parents=True, exist_ok=True)
    (tmp_path / "grading_configs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "schemas").mkdir(parents=True, exist_ok=True)

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
        "model": "gpt-5.2-chat",
        "completed_at": "2026-05-20T00:00:00Z",
        "results": [
            {"task_id": "task-001", "deliverable_files": ["deliverable_files/task-001/Sample.xlsx"]},
            {"task_id": "task-002", "deliverable_files": ["deliverable_files/task-002/Sample.xlsx"]},
            {"task_id": "task-003", "deliverable_files": ["deliverable_files/task-003/Sample.xlsx"]},
        ],
    }
    (tmp_path / "workspace" / "step2_inference_results.json").write_text(json.dumps(inf), encoding="utf-8")

    (tmp_path / "prompts" / "grader_judge.md").write_text("<!-- prompt_version: v1 -->\n{{#each deliverable_files}}{{/each}}", encoding="utf-8")
    cfg = {
        "schema_version": "1.0",
        "config_name": "default_gpt5pro",
        "judge": {"provider": "azure_openai", "api": "responses", "model": "gpt-5.4-pro", "deployment": "gpt-5.4-pro", "api_version": "2025-04-01-preview", "endpoint_env": "AZURE_OPENAI_ENDPOINT"},
        "rubric": {"source": "huggingface", "repo_id": "openai/gdpval", "revision": "main", "cache_dir": "data/gdpval-local"},
        "prompt": {"template": "prompts/grader_judge.md", "version": "v1"},
        "output": {"directory": "data/grades", "filename_template": "{exp_id}__{judge_slug}__{rubric_short_sha}__{prompt_v}.json", "partial_save_every_n_tasks": 10},
        "tpm_guard": {"max_concurrent": 1, "min_delay_ms_between_calls": 0, "retry_on_429": {"enabled": False}},
    }
    (tmp_path / "grading_configs" / "default.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")

    # Reuse repo schema
    schema_src = Path("schemas/grade.schema.json").read_text(encoding="utf-8")
    (tmp_path / "schemas" / "grade.schema.json").write_text(schema_src, encoding="utf-8")


def test_skip_when_grade_exists(monkeypatch, tmp_path):
    _setup_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s8, "RubricLoader", _FakeLoader)
    monkeypatch.setattr(s8, "Grader", _FakeGrader)

    out = tmp_path / "data/grades/exp998_smoke_baseline_sample__gpt-5_4-pro__11e7900__v1.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("{}", encoding="utf-8")

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
    assert payload["schema_version"] == "1.0"


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

    out = tmp_path / "data/grades/exp998_smoke_baseline_sample__gpt-5_4-pro__11e7900__v1.json"
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert len(payload["tasks"]) == 2


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

    out = tmp_path / "data/grades/exp998_smoke_baseline_sample__gpt-5_4-pro__11e7900__v1.json"
    payload = json.loads(out.read_text(encoding="utf-8"))
    ids = [t["task_id"] for t in payload["tasks"]]
    assert ids == ["task-002", "task-003"]


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
    # ExperimentConfig default deployment is "gpt-4" when empty — but the
    # important guarantee is: inference_model must NEVER equal judge.model
    # just because both sources were missing. Verify by reading the payload.
    assert s8.main() == 0
    out = tmp_path / "data/grades/exp998_smoke_baseline_sample__gpt-5_4-pro__11e7900__v1.json"
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["inference_model"] != "gpt-5.4-pro"  # judge model
