"""Tests for HuggingFace integration in main.py

Usage:
    pytest tests/test_main_hf_integration.py -v
"""

import pytest
from unittest.mock import patch, Mock, MagicMock
from pathlib import Path

# Skip if huggingface_hub not available
pytest.importorskip("huggingface_hub")

from main import run_experiment, run_experiment_from_config


class TestMainHuggingFaceIntegration:
    """Test suite for HuggingFace upload integration"""

    @patch("main._upload_to_huggingface")
    @patch("main.complete")
    @patch("main.create_client")
    @patch("main.GDPValDataLoader")
    @patch("main.PromptBuilder.from_preset")
    def test_run_experiment_with_publish_flag(
        self,
        mock_prompt_builder,
        mock_loader,
        mock_client_create,
        mock_complete,
        mock_hf_upload,
        tmp_path,
        monkeypatch,
    ):
        """Test run_experiment with publish_to_hf=True"""
        # Setup environment
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com")
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("HF_TOKEN", "hf_test_token")

        # Mock data loader
        mock_task = Mock()
        mock_task.task_id = "task_001"
        mock_task.sector = "Finance"
        mock_task.occupation = "Analyst"
        mock_task.task = "Test task"
        mock_task.reference_files = []
        mock_loader.return_value.load.return_value = [mock_task]

        # Mock prompt builder
        mock_builder = Mock()
        mock_builder.build.return_value = {
            "system": "You are helpful",
            "user": "Test prompt",
        }
        mock_prompt_builder.return_value = mock_builder

        # Mock LLM client
        mock_client = Mock()
        mock_client_create.return_value = mock_client

        # Mock completion
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Test response"))]
        mock_response.model = "gpt-4"
        mock_response.usage = Mock(prompt_tokens=10, completion_tokens=20, total_tokens=30)
        mock_complete.return_value = (mock_response, 1000.0)

        # Mock HF upload
        mock_hf_upload.return_value = "https://huggingface.co/datasets/gdpval-realwork/exp001-baseline"

        # Run experiment with publish flag
        output_path = tmp_path / "results" / "exp001.json"
        result = run_experiment(
            experiment_id="exp001",
            condition="baseline",
            model="gpt-4",
            output_path=str(output_path),
            publish_to_hf=True,
        )

        # Verify HF upload was called
        mock_hf_upload.assert_called_once()
        # Check arguments (can be positional or keyword)
        call_str = str(mock_hf_upload.call_args)
        assert "exp001" in call_str
        assert "baseline" in call_str

        # Verify HF URL in result
        assert "huggingface_url" in result
        assert result["huggingface_url"] == "https://huggingface.co/datasets/gdpval-realwork/exp001-baseline"

    @patch("main._upload_to_huggingface")
    @patch("main.complete")
    @patch("main.create_client")
    @patch("main.GDPValDataLoader")
    @patch("main.PromptBuilder.from_preset")
    def test_run_experiment_without_publish_flag(
        self,
        mock_prompt_builder,
        mock_loader,
        mock_client_create,
        mock_complete,
        mock_hf_upload,
        tmp_path,
        monkeypatch,
    ):
        """Test run_experiment with publish_to_hf=False (default)"""
        # Setup environment
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com")
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")

        # Mock data loader
        mock_task = Mock()
        mock_task.task_id = "task_001"
        mock_task.sector = "Finance"
        mock_task.occupation = "Analyst"
        mock_task.task = "Test task"
        mock_task.reference_files = []
        mock_loader.return_value.load.return_value = [mock_task]

        # Mock prompt builder
        mock_builder = Mock()
        mock_builder.build.return_value = {
            "system": "You are helpful",
            "user": "Test prompt",
        }
        mock_prompt_builder.return_value = mock_builder

        # Mock LLM client
        mock_client = Mock()
        mock_client_create.return_value = mock_client

        # Mock completion
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Test response"))]
        mock_response.model = "gpt-4"
        mock_response.usage = Mock(prompt_tokens=10, completion_tokens=20, total_tokens=30)
        mock_complete.return_value = (mock_response, 1000.0)

        # Run experiment without publish flag
        output_path = tmp_path / "results" / "exp001.json"
        result = run_experiment(
            experiment_id="exp001",
            condition="baseline",
            model="gpt-4",
            output_path=str(output_path),
            publish_to_hf=False,
        )

        # Verify HF upload was NOT called
        mock_hf_upload.assert_not_called()

        # Verify no HF URL in result
        assert "huggingface_url" not in result

    @patch("main._upload_to_huggingface")
    @patch("main.complete")
    @patch("main.create_client")
    @patch("main.GDPValDataLoader")
    @patch("main.ExperimentConfig.from_yaml")
    def test_run_experiment_from_config_with_publish(
        self,
        mock_config_from_yaml,
        mock_loader,
        mock_client_create,
        mock_complete,
        mock_hf_upload,
        tmp_path,
        monkeypatch,
    ):
        """Test run_experiment_from_config with publish_mode=True"""
        # Setup environment
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com")
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("HF_TOKEN", "hf_test_token")

        # Mock config
        mock_config = Mock()
        mock_config.name = "Test Experiment"
        mock_config.experiment_id = "exp001"
        mock_config.data_filter.sector = None
        mock_config.data_filter.sample_size = None
        mock_config.condition_a.name = "Baseline"
        mock_config.condition_a.model.deployment = "gpt-4"
        mock_config.condition_a.prompt.system = "You are helpful"
        mock_config.condition_a.prompt.prefix = None
        mock_config.condition_a.prompt.suffix = None
        mock_config.condition_b = None  # Single test (no A/B)
        mock_config.is_ab_test = False
        mock_config.output.save_path = str(tmp_path / "results")
        mock_config.output.publish_to_hf = True
        mock_config.validate.return_value = []
        mock_config_from_yaml.return_value = mock_config

        # Mock data loader
        mock_task = Mock()
        mock_task.task_id = "task_001"
        mock_task.sector = "Finance"
        mock_task.occupation = "Analyst"
        mock_task.task = "Test task"
        mock_task.reference_files = []
        mock_loader.return_value.load.return_value = [mock_task]

        # Mock LLM client
        mock_client = Mock()
        mock_client_create.return_value = mock_client

        # Mock completion
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="Test response"))]
        mock_response.model = "gpt-4"
        mock_response.usage = Mock(prompt_tokens=10, completion_tokens=20, total_tokens=30)
        mock_complete.return_value = (mock_response, 1000.0)

        # Mock HF upload
        mock_hf_upload.return_value = "https://huggingface.co/datasets/gdpval-realwork/exp001-baseline"

        # Run experiment from config with publish mode
        config_path = tmp_path / "config.yaml"
        config_path.write_text("test: config")

        result = run_experiment_from_config(
            config_path=str(config_path),
            publish_mode=True,
        )

        # Verify publish flag was set
        assert mock_config.output.publish_to_hf is True

        # Verify HF upload was called
        mock_hf_upload.assert_called_once()

        # Verify HF URL in result
        assert "huggingface_url" in result
        assert result["huggingface_url"] == "https://huggingface.co/datasets/gdpval-realwork/exp001-baseline"
