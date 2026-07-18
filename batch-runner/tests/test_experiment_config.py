"""Tests for Experiment Configuration

Usage:
    pytest tests/test_experiment_config.py -v
"""

import hashlib
import json
import sys
import types
from types import SimpleNamespace

import pytest
from pathlib import Path
from core.experiment_config import (
    ExperimentConfig,
    ModelConfig,
    PromptConfig,
    ConditionConfig,
    DataFilterConfig,
    ControlConfig,
    OutputConfig,
)


def _valid_agentic_config():
    return {
        "compute_transport": "remote",
        "image": "task@sha256:" + "a" * 64,
        "verifier_image": "verifier@sha256:" + "b" * 64,
        "memory_gb": 8,
        "cpus": 2,
        "limits": {
            "max_api_attempts": 6,
            "max_model_iterations": 6,
            "max_tool_calls": 8,
        },
        "budget": {
            "paired_run_id": "paired-run",
            "condition": {
                "attempts": 30,
                "input_tokens": 1000000,
                "output_tokens": 100000,
                "cost_usd": "6.25",
            },
            "paired_run": {
                "attempts": 30,
                "input_tokens": 1500000,
                "output_tokens": 163840,
                "cost_usd": "6.25",
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
    }


@pytest.fixture
def sample_config_dict():
    """Create a sample configuration dictionary"""
    return {
        "experiment": {
            "id": "exp001",
            "name": "Test Experiment",
            "description": "Test description",
            "author": "Test Author",
            "created_at": "2025-02-09",
        },
        "control": {
            "fixed": ["model", "tasks"],
            "changed": ["prompt_strategy"],
        },
        "data": {
            "source": "openai/gdpval",
            "filter": {
                "sector": "Finance and Insurance",
                "occupation": None,
                "sample_size": 10,
            },
        },
        "condition_a": {
            "name": "Baseline",
            "model": {
                "provider": "azure",
                "deployment": "gpt-5.2-chat",
                "temperature": 0.0,
                "seed": 42,
            },
            "prompt": {
                "system": "You are helpful.",
                "prefix": None,
                "suffix": None,
            },
        },
        "condition_b": {
            "name": "Treatment",
            "model": {
                "provider": "azure",
                "deployment": "gpt-5.2-chat",
                "temperature": 0.0,
                "seed": 42,
            },
            "prompt": {
                "system": "You are helpful.",
                "prefix": None,
                "suffix": "Work carefully.",
            },
        },
        "output": {
            "publish_to_hf": False,
            "submit_to_evals": False,
            "save_path": "results/exp001",
        },
        "execution": {
            "mode": "subprocess",
            "score_type": "tool_assisted",
            "max_retries": 5,
            "resume_max_rounds": 1,
            "install_libreoffice": True,
            "tokens": {
                "code_generation": 12000,
                "qa_check": 3000,
                "json_render": 7000,
            },
        },
    }


@pytest.fixture
def sample_yaml_file(tmp_path, sample_config_dict):
    """Create a sample YAML file"""
    import yaml

    yaml_path = tmp_path / "test_config.yaml"
    with open(yaml_path, "w") as f:
        yaml.dump(sample_config_dict, f)
    return yaml_path


class TestModelConfig:
    """Test suite for ModelConfig"""

    def test_create_model_config(self):
        """Test creating ModelConfig"""
        config = ModelConfig(
            provider="azure",
            deployment="gpt-5.2-chat",
            temperature=0.5,
            seed=42,
        )

        assert config.provider == "azure"
        assert config.deployment == "gpt-5.2-chat"
        assert config.temperature == 0.5
        assert config.seed == 42


class TestPromptConfig:
    """Test suite for PromptConfig"""

    def test_create_prompt_config(self):
        """Test creating PromptConfig"""
        config = PromptConfig(
            system="You are helpful.",
            prefix="Start:",
            suffix="End.",
        )

        assert config.system == "You are helpful."
        assert config.prefix == "Start:"
        assert config.suffix == "End."


class TestExperimentConfigFromDict:
    """Test suite for ExperimentConfig.from_dict()"""

    def test_from_dict_basic(self, sample_config_dict):
        """Test loading config from dictionary"""
        config = ExperimentConfig.from_dict(sample_config_dict)

        assert config.experiment_id == "exp001"
        assert config.name == "Test Experiment"
        assert config.description == "Test description"
        assert config.author == "Test Author"

    def test_from_dict_control(self, sample_config_dict):
        """Test control configuration"""
        config = ExperimentConfig.from_dict(sample_config_dict)

        assert config.control.fixed == ["model", "tasks"]
        assert config.control.changed == ["prompt_strategy"]

    def test_from_dict_data_filter(self, sample_config_dict):
        """Test data filter configuration"""
        config = ExperimentConfig.from_dict(sample_config_dict)

        assert config.data_filter.source == "openai/gdpval"
        assert config.data_filter.sector == "Finance and Insurance"
        assert config.data_filter.occupation is None
        assert config.data_filter.sample_size == 10
        assert config.data_filter.task_ids is None

    def test_from_dict_conditions(self, sample_config_dict):
        """Test condition configurations (A/B test)"""
        config = ExperimentConfig.from_dict(sample_config_dict)

        # Condition A
        assert config.condition_a.name == "Baseline"
        assert config.condition_a.model.provider == "azure"
        assert config.condition_a.model.deployment == "gpt-5.2-chat"
        assert config.condition_a.prompt.system == "You are helpful."
        assert config.condition_a.prompt.suffix is None

        # Condition B
        assert config.condition_b is not None
        assert config.condition_b.name == "Treatment"
        assert config.condition_b.prompt.suffix == "Work carefully."

        # A/B test detection
        assert config.is_ab_test is True

    def test_from_dict_output(self, sample_config_dict):
        """Test output configuration"""
        config = ExperimentConfig.from_dict(sample_config_dict)

        assert config.output.publish_to_hf is False
        assert config.output.submit_to_evals is False
        assert config.output.save_path == "results/exp001"

    def test_from_dict_execution_tokens(self, sample_config_dict):
        """Test execution.tokens parsing"""
        config = ExperimentConfig.from_dict(sample_config_dict)
        assert config.execution.mode == "subprocess"
        assert config.execution.max_retries == 5
        assert config.execution.resume_max_rounds == 1
        assert config.execution.tokens["code_generation"] == 12000
        assert config.execution.tokens["qa_check"] == 3000
        assert config.execution.tokens["json_render"] == 7000
        assert config.execution.metrics is None
        assert "metrics" not in config.to_dict()["execution"]

    def test_from_dict_execution_metrics_opt_in(self, sample_config_dict):
        sample_config_dict["execution"]["metrics"] = {
            "enabled": True,
            "raw_output": "must-not-survive",
        }

        config = ExperimentConfig.from_dict(sample_config_dict)

        assert config.execution.metrics == {"enabled": True}
        assert config.to_dict()["execution"]["metrics"] == {"enabled": True}

    def test_from_dict_agentic_config_is_opt_in(self, sample_config_dict):
        config = ExperimentConfig.from_dict(sample_config_dict)
        assert config.execution.agentic is None
        assert "agentic" not in config.to_dict()["execution"]

        sample_config_dict["execution"]["mode"] = "agentic_sandbox"
        sample_config_dict["experiment"]["id"] = "exp028"
        sample_config_dict["execution"]["agentic"] = _valid_agentic_config()

        config = ExperimentConfig.from_dict(sample_config_dict)

        assert config.execution.agentic == _valid_agentic_config()
        assert config.to_dict()["execution"]["agentic"] == config.execution.agentic

    @pytest.mark.parametrize(
        "metrics",
        [{}, {"enabled": False}, {"enabled": "false"}, {"enabled": 1}, []],
    )
    def test_from_dict_execution_metrics_requires_literal_true(
        self, sample_config_dict, metrics
    ):
        sample_config_dict["execution"]["metrics"] = metrics

        config = ExperimentConfig.from_dict(sample_config_dict)

        assert config.execution.metrics is None
        assert "metrics" not in config.to_dict()["execution"]


class TestExperimentConfigFromYaml:
    """Test suite for ExperimentConfig.from_yaml()"""

    def test_from_yaml_success(self, sample_yaml_file):
        """Test loading config from YAML file"""
        config = ExperimentConfig.from_yaml(str(sample_yaml_file))

        assert config.experiment_id == "exp001"
        assert config.name == "Test Experiment"

    def test_from_yaml_file_not_found(self):
        """Test error when file doesn't exist"""
        with pytest.raises(FileNotFoundError):
            ExperimentConfig.from_yaml("nonexistent.yaml")

    def test_from_yaml_real_example(self):
        """Test loading real example YAML file"""
        yaml_path = Path(__file__).parent.parent / "experiments" / "exp_test_sample10.yaml"

        if yaml_path.exists():
            config = ExperimentConfig.from_yaml(str(yaml_path))

            assert config.experiment_id == "exp_test"
            assert config.name == "Test Run - Sample 10"
            assert config.data_filter.sample_size == 10


class TestExperimentConfigValidation:
    """Test suite for config validation"""

    def test_validate_valid_config(self, sample_config_dict):
        """Test validation with valid config (A/B test)"""
        config = ExperimentConfig.from_dict(sample_config_dict)
        errors = config.validate()

        assert len(errors) == 0

    def test_validate_valid_single_test(self, sample_config_dict):
        """Test validation with valid config (single test, no condition_b)"""
        del sample_config_dict["condition_b"]
        config = ExperimentConfig.from_dict(sample_config_dict)
        errors = config.validate()

        assert len(errors) == 0
        assert config.is_ab_test is False

    def test_validate_missing_experiment_id(self, sample_config_dict):
        """Test validation with missing experiment ID"""
        sample_config_dict["experiment"]["id"] = ""
        config = ExperimentConfig.from_dict(sample_config_dict)
        errors = config.validate()

        assert len(errors) > 0
        assert any("experiment.id" in e for e in errors)

    def test_validate_invalid_provider(self, sample_config_dict):
        """Test validation with invalid model provider"""
        sample_config_dict["condition_a"]["model"]["provider"] = "invalid"
        config = ExperimentConfig.from_dict(sample_config_dict)
        errors = config.validate()

        assert len(errors) > 0
        assert any("provider" in e for e in errors)

    def test_validate_agentic_sandbox_provider(self, sample_config_dict):
        sample_config_dict["execution"]["mode"] = "agentic_sandbox"
        sample_config_dict["experiment"]["id"] = "exp028"
        sample_config_dict["execution"]["agentic"] = _valid_agentic_config()
        del sample_config_dict["condition_b"]
        assert ExperimentConfig.from_dict(sample_config_dict).validate() == []

        sample_config_dict["condition_a"]["model"]["provider"] = "anthropic"
        errors = ExperimentConfig.from_dict(sample_config_dict).validate()

        assert errors == [
            "agentic_sandbox mode requires azure or openai provider for condition_a"
        ]

    def test_validate_agentic_sandbox_rejects_unsafe_config(
        self, sample_config_dict
    ):
        sample_config_dict["execution"]["mode"] = "agentic_sandbox"
        sample_config_dict["experiment"]["id"] = "exp028"
        config = _valid_agentic_config()
        config["image"] = "latest"
        config["unexpected"] = True
        sample_config_dict["execution"]["agentic"] = config

        errors = ExperimentConfig.from_dict(sample_config_dict).validate()

        assert any("image must be pinned" in error for error in errors)
        assert any("unknown fields" in error for error in errors)

    def test_validate_hardened_sandbox_rejects_self_qa(
        self, sample_config_dict
    ):
        sample_config_dict["execution"]["mode"] = "sandbox"
        sample_config_dict["experiment"]["id"] = "exp029"
        sample_config_dict["execution"]["sandbox"] = {
            "hardened_substrate": True
        }
        sample_config_dict["execution"]["agentic"] = _valid_agentic_config()
        sample_config_dict["condition_a"]["qa"] = {"enabled": True}

        errors = ExperimentConfig.from_dict(sample_config_dict).validate()

        assert any("condition_a.qa must be disabled" in error for error in errors)

    def test_validate_agentic_ids_are_reserved(self, sample_config_dict):
        sample_config_dict["execution"]["mode"] = "agentic_sandbox"
        sample_config_dict["execution"]["agentic"] = _valid_agentic_config()
        sample_config_dict["experiment"]["id"] = "exp031"

        errors = ExperimentConfig.from_dict(sample_config_dict).validate()

        assert any("must be exp028 or exp030" in error for error in errors)

    def test_validate_task_ids_rejects_duplicates_and_sampling(self, sample_config_dict):
        sample_config_dict["data"]["filter"]["task_ids"] = ["task-1", "task-1"]
        config = ExperimentConfig.from_dict(sample_config_dict)

        errors = config.validate()

        assert any("duplicates" in error for error in errors)
        assert any("mutually exclusive" in error for error in errors)

    def test_validate_task_ids_rejects_empty_list(self, sample_config_dict):
        sample_config_dict["data"]["filter"]["sample_size"] = None
        sample_config_dict["data"]["filter"]["task_ids"] = []

        errors = ExperimentConfig.from_dict(sample_config_dict).validate()

        assert any("non-empty list" in error for error in errors)


class TestExperimentConfigToDict:
    """Test suite for to_dict() method"""

    def test_to_dict_roundtrip(self, sample_config_dict):
        """Test converting to dict and back"""
        config1 = ExperimentConfig.from_dict(sample_config_dict)
        dict_output = config1.to_dict()
        config2 = ExperimentConfig.from_dict(dict_output)

        assert config1.experiment_id == config2.experiment_id
        assert config1.name == config2.name
        assert config1.condition_a.name == config2.condition_a.name
        assert config1.is_ab_test == config2.is_ab_test

    def test_to_dict_roundtrip_single_test(self, sample_config_dict):
        """Test roundtrip for single test (no condition_b)"""
        del sample_config_dict["condition_b"]
        config1 = ExperimentConfig.from_dict(sample_config_dict)
        dict_output = config1.to_dict()

        assert "condition_b" not in dict_output

        config2 = ExperimentConfig.from_dict(dict_output)
        assert config2.is_ab_test is False
        assert config2.condition_b is None


class TestExperimentConfigRepr:
    """Test suite for __repr__"""

    def test_repr(self, sample_config_dict):
        """Test string representation"""
        config = ExperimentConfig.from_dict(sample_config_dict)
        repr_str = repr(config)

        assert "ExperimentConfig" in repr_str
        assert "exp001" in repr_str
        assert "Test Experiment" in repr_str


class TestDataClasses:
    """Test suite for other dataclasses"""

    def test_data_filter_config(self):
        """Test DataFilterConfig"""
        config = DataFilterConfig(
            source="test",
            sector="Finance",
            occupation="Analyst",
            sample_size=5,
            task_ids=None,
        )

        assert config.source == "test"
        assert config.sector == "Finance"
        assert config.occupation == "Analyst"
        assert config.sample_size == 5
        assert config.task_ids is None

    def test_control_config(self):
        """Test ControlConfig"""
        config = ControlConfig(
            fixed=["a", "b"],
            changed=["c"],
        )

        assert config.fixed == ["a", "b"]
        assert config.changed == ["c"]

    def test_output_config(self):
        """Test OutputConfig"""
        config = OutputConfig(
            publish_to_hf=True,
            submit_to_evals=False,
            save_path="test/path",
        )

        assert config.publish_to_hf is True
        assert config.submit_to_evals is False
        assert config.save_path == "test/path"

    def test_condition_config(self):
        """Test ConditionConfig"""
        model = ModelConfig(provider="azure", deployment="gpt-4")
        prompt = PromptConfig(system="test")
        condition = ConditionConfig(name="Test", model=model, prompt=prompt)

        assert condition.name == "Test"
        assert condition.model.provider == "azure"
        assert condition.prompt.system == "test"


# ── Regression: execution.sandbox + timeout propagation (config drop bug) ──────
EXPERIMENTS_DIR = Path(__file__).resolve().parent.parent / "experiments"
EXP025_YAML = EXPERIMENTS_DIR / "exp025_GPT54_high_postfix.yaml"
EXP026_YAML = EXPERIMENTS_DIR / "exp026_sandbox_skills_multimodal.yaml"
EXP026S_YAML = EXPERIMENTS_DIR / "exp026s_sandbox_ci_smoke.yaml"
EXP027_YAML = EXPERIMENTS_DIR / "exp027_GPT54_default_subprocess_bridge50.yaml"
EXP027_SELECTION = (
    EXPERIMENTS_DIR.parent.parent
    / "tasks" / "0714_tuesday" / "exp027_bridge50_selection.json"
)


def _fake_task(task_id: str, occupation: str):
    """Minimal stand-in for a GDPValTask (no dataset snapshot required)."""
    return SimpleNamespace(
        task_id=task_id,
        sector="Finance and Insurance",
        occupation=occupation,
        prompt="Prepare a short financial summary document.",
        reference_files=[],
        reference_file_urls=[],
    )


class TestExecutionSandboxPropagation:
    """Guards the config-propagation fix.

    Bug: ExecutionConfig never parsed ``execution.sandbox`` and step1 dropped
    both ``timeout`` and ``sandbox`` from the prepared-tasks JSON, so a CI
    sandbox run silently fell back to defaults (timeout 570 / use_docker auto /
    memory 5GB) instead of the hardened 1200 / always / 8GB.
    """

    def test_execution_config_defaults_sandbox_to_none(self):
        """New field exists and defaults to None (no behaviour change by default)."""
        from core.experiment_config import ExecutionConfig

        assert ExecutionConfig().sandbox is None

    def test_from_dict_without_sandbox_is_none(self, sample_config_dict):
        """A config with no execution.sandbox block yields sandbox=None."""
        config = ExperimentConfig.from_dict(sample_config_dict)
        assert config.execution.sandbox is None

    def test_from_dict_parses_sandbox_block(self, sample_config_dict):
        """execution.sandbox + timeout survive from_dict parsing."""
        sample_config_dict["execution"]["mode"] = "sandbox"
        sample_config_dict["execution"]["timeout"] = 1200
        sample_config_dict["execution"]["sandbox"] = {
            "use_docker": "always",
            "memory_gb": 8,
        }
        config = ExperimentConfig.from_dict(sample_config_dict)

        assert config.execution.mode == "sandbox"
        assert config.execution.timeout == 1200
        assert config.execution.sandbox == {"use_docker": "always", "memory_gb": 8}

    def test_exp026_parses_sandbox_hardening(self):
        """(a) The real exp026 YAML exposes the sandbox hardening + timeout."""
        config = ExperimentConfig.from_yaml(str(EXP026_YAML))

        assert config.execution.mode == "sandbox"
        assert config.execution.timeout == 1200
        assert isinstance(config.execution.sandbox, dict)
        assert config.execution.sandbox["use_docker"] == "always"
        assert config.execution.sandbox["memory_gb"] == 8

    def test_exp026s_smoke_parses_bounded_scope(self):
        """(b) The new CI smoke YAML keeps the hardening but bounds the scope."""
        config = ExperimentConfig.from_yaml(str(EXP026S_YAML))

        assert config.execution.mode == "sandbox"
        assert config.execution.timeout == 1200
        assert config.execution.sandbox["use_docker"] == "always"
        assert config.execution.sandbox["memory_gb"] == 8
        assert config.data_filter.sample_size == 1
        assert config.data_filter.occupation == "Accountants and Auditors"

    def test_step1_prepares_execution_sandbox_and_timeout(self, tmp_path, monkeypatch):
        """(c) step1's prepared-tasks JSON now carries timeout + sandbox.

        Exercises the REAL step1 output construction with the dataset loader and
        needs-files manifest mocked out — no network, no model, no Docker, no
        local snapshot. ``core.data_loader`` imports the heavy ``prepare_dataset``
        (pyarrow) at module load, so in a minimal env we inject a lightweight
        stub; in CI (pyarrow present) the real module imports and the stub is
        never used.
        """
        try:
            import prepare_dataset  # noqa: F401
        except Exception:
            stub = types.ModuleType("prepare_dataset")
            stub.GDPValDataset = type("GDPValDataset", (), {})
            stub.GDPValTask = type("GDPValTask", (), {})
            monkeypatch.setitem(sys.modules, "prepare_dataset", stub)

        import step1_prepare_tasks as step1

        fake_tasks = [
            _fake_task("acct-001", "Accountants and Auditors"),
            _fake_task("dev-001", "Software Developers"),
        ]

        class _FakeLoader:
            def __init__(self, *args, **kwargs):
                pass

            def load(self):
                return fake_tasks

        class _FakeManifest:
            @staticmethod
            def load():
                raise FileNotFoundError

        monkeypatch.setattr(step1, "GDPValDataLoader", _FakeLoader)
        monkeypatch.setattr(step1, "NeedsFilesManifest", _FakeManifest)
        monkeypatch.setattr(step1, "WORKSPACE_DIR", tmp_path)

        output = step1.prepare_tasks(str(EXP026S_YAML))

        exec_block = output["execution"]
        assert "timeout" in exec_block, "step1 dropped execution.timeout"
        assert "sandbox" in exec_block, "step1 dropped execution.sandbox"
        assert exec_block["timeout"] == 1200
        assert exec_block["sandbox"]["use_docker"] == "always"
        assert exec_block["sandbox"]["memory_gb"] == 8
        # occupation filter + sample_size:1 -> exactly one task
        assert output["total_tasks"] == 1

        # The persisted JSON (what step2 actually reads) mirrors it.
        written = json.loads(
            (tmp_path / "step1_tasks_prepared.json").read_text(encoding="utf-8")
        )
        assert written["execution"]["timeout"] == 1200
        assert written["execution"]["sandbox"]["use_docker"] == "always"
        assert written["execution"]["sandbox"]["memory_gb"] == 8
        assert written["condition_a"]["model"]["reasoning_effort"] == "low"
        assert written["task_scope"]["mode"] == "filtered"
        assert written["task_scope"]["expected_count"] == 1
        assert written["total_tasks"] == 1

    def test_to_dict_preserves_sandbox_block(self):
        config = ExperimentConfig.from_yaml(str(EXP026_YAML))

        roundtrip = ExperimentConfig.from_dict(config.to_dict())

        assert roundtrip.execution.sandbox == config.execution.sandbox


class TestExplicitTaskIdFilter:
    def _prepare(self, tmp_path, monkeypatch, task_ids, sample_size=None):
        try:
            import prepare_dataset  # noqa: F401
        except Exception:
            stub = types.ModuleType("prepare_dataset")
            stub.GDPValDataset = type("GDPValDataset", (), {})
            stub.GDPValTask = type("GDPValTask", (), {})
            monkeypatch.setitem(sys.modules, "prepare_dataset", stub)

        import yaml
        import step1_prepare_tasks as step1

        config = {
            "experiment": {"id": "exp-filter", "name": "Filter test"},
            "data": {
                "source": "test/source",
                "filter": {"task_ids": task_ids, "sample_size": sample_size},
            },
            "condition_a": {
                "name": "A",
                "model": {
                    "provider": "azure",
                    "deployment": "gpt-5.4",
                    "reasoning_effort": "low",
                },
                "prompt": {"system": "test"},
            },
        }
        config_path = tmp_path / "filter.yaml"
        config_path.write_text(yaml.safe_dump(config), encoding="utf-8")

        fake_tasks = [
            _fake_task("task-1", "Analyst"),
            _fake_task("task-2", "Analyst"),
            _fake_task("task-3", "Analyst"),
        ]

        class _FakeLoader:
            def __init__(self, *args, **kwargs):
                pass

            def load(self):
                return fake_tasks

        class _FakeManifest:
            @staticmethod
            def load():
                raise FileNotFoundError

        monkeypatch.setattr(step1, "GDPValDataLoader", _FakeLoader)
        monkeypatch.setattr(step1, "NeedsFilesManifest", _FakeManifest)
        monkeypatch.setattr(step1, "WORKSPACE_DIR", tmp_path)
        return step1.prepare_tasks(str(config_path))

    def test_step1_preserves_explicit_order_and_reasoning(self, tmp_path, monkeypatch):
        output = self._prepare(tmp_path, monkeypatch, ["task-3", "task-1"])

        assert [task["task_id"] for task in output["tasks"]] == ["task-3", "task-1"]
        assert output["condition_a"]["model"]["reasoning_effort"] == "low"

    def test_step1_rejects_unknown_task_id(self, tmp_path, monkeypatch):
        with pytest.raises(ValueError, match="unknown task IDs: missing"):
            self._prepare(tmp_path, monkeypatch, ["task-1", "missing"])

    def test_step1_rejects_task_ids_with_sample_size(self, tmp_path, monkeypatch):
        with pytest.raises(ValueError, match="mutually exclusive"):
            self._prepare(tmp_path, monkeypatch, ["task-1"], sample_size=1)

    def test_exp027_bridge_task_set_and_controls_are_frozen(self):
        config = ExperimentConfig.from_yaml(str(EXP027_YAML))
        task_ids = config.data_filter.task_ids

        assert config.validate() == []
        assert task_ids is not None
        assert len(task_ids) == len(set(task_ids)) == 50
        assert task_ids == sorted(task_ids)
        digest = hashlib.sha256(("\n".join(task_ids) + "\n").encode("utf-8")).hexdigest()
        assert digest == "33b18c57f4a5227ebeccbdc68480b9b702df7927928ac086f63114bb5676a47a"
        assert config.execution.mode == "subprocess"
        assert config.execution.timeout == 1200
        assert config.execution.tokens["code_generation"] == 32768
        assert config.condition_a.model.reasoning_effort is None
        assert [
            preprocessor["type"] for preprocessor in config.condition_a.preprocessors or []
        ] == ["audio_analyzer", "video_analyzer"]

    def test_exp027_condition_policy_is_coherent_subprocess_control(self):
        import yaml

        exp025 = yaml.safe_load(EXP025_YAML.read_text(encoding="utf-8"))
        exp026 = yaml.safe_load(EXP026_YAML.read_text(encoding="utf-8"))
        exp027 = yaml.safe_load(EXP027_YAML.read_text(encoding="utf-8"))

        assert exp027["condition_a"]["prompt"] == exp025["condition_a"]["prompt"]
        assert exp027["condition_a"]["qa"] == exp025["condition_a"]["qa"]
        assert exp027["condition_a"]["preprocessors"] == [
            exp025["condition_a"]["preprocessors"][0],
            exp026["condition_a"]["preprocessors"][1],
        ]

    def test_exp027_selection_groups_match_yaml(self):
        selection = json.loads(EXP027_SELECTION.read_text(encoding="utf-8"))
        config = ExperimentConfig.from_yaml(str(EXP027_YAML))
        groups = selection["groups"]

        assert [len(groups[name]) for name in ("group_a", "group_b", "group_c")] == [42, 6, 2]
        grouped_ids = sorted(
            task_id for group in groups.values() for task_id in group
        )
        assert grouped_ids == config.data_filter.task_ids
        digest = hashlib.sha256(("\n".join(grouped_ids) + "\n").encode("utf-8")).hexdigest()
        assert digest == selection["task_ids_sha256"]
