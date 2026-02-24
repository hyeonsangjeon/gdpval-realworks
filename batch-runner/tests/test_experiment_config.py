"""Tests for Experiment Configuration

Usage:
    pytest tests/test_experiment_config.py -v
"""

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
        )

        assert config.source == "test"
        assert config.sector == "Finance"
        assert config.occupation == "Analyst"
        assert config.sample_size == 5

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
