"""Tests for HuggingFace Uploader

Usage:
    pytest tests/test_hf_uploader.py -v
"""

import pytest
import json
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from core.result_collector import ExperimentResult, TaskResult


# Skip all tests if huggingface_hub is not available
pytest.importorskip("huggingface_hub")

from core.hf_uploader import HuggingFaceUploader


@pytest.fixture
def sample_result():
    """Create sample experiment result"""
    # Create mock task objects
    mock_task1 = Mock()
    mock_task1.task_id = "task_001"
    mock_task1.sector = "Finance and Insurance"
    mock_task1.occupation = "Financial Analyst"
    mock_task1.task = "Analyze financial data"

    mock_task2 = Mock()
    mock_task2.task_id = "task_002"
    mock_task2.sector = "Healthcare"
    mock_task2.occupation = "Medical Doctor"
    mock_task2.task = "Review patient records"

    task_result1 = TaskResult(
        task_id="task_001",
        prompt_config="baseline",
        task=mock_task1,
        content="Here is my analysis...",
        model="gpt-4",
        usage={"prompt_tokens": 100, "completion_tokens": 150, "total_tokens": 250},
        latency_ms=1500.0,
    )

    task_result2 = TaskResult(
        task_id="task_002",
        prompt_config="baseline",
        task=mock_task2,
        content="Patient review complete...",
        model="gpt-4",
        usage={"prompt_tokens": 120, "completion_tokens": 180, "total_tokens": 300},
        latency_ms=2000.0,
    )

    result = ExperimentResult(
        experiment_id="exp001",
        condition_name="baseline",
        model="gpt-4",
        results=[task_result1, task_result2],
        started_at=datetime(2026, 2, 9, 10, 0, 0),
        completed_at=datetime(2026, 2, 9, 10, 5, 0),
    )

    return result


@pytest.fixture
def mock_hf_token():
    """Mock HuggingFace token"""
    return "hf_test_token_123"


class TestHuggingFaceUploaderInit:
    """Test suite for HuggingFaceUploader initialization"""

    def test_init_with_token(self, mock_hf_token):
        """Test initialization with token"""
        uploader = HuggingFaceUploader(token=mock_hf_token)
        assert uploader.token == mock_hf_token
        assert uploader.ORG == "gdpval-realwork"

    def test_init_with_env_token(self, monkeypatch, mock_hf_token):
        """Test initialization with environment variable"""
        monkeypatch.setenv("HF_TOKEN", mock_hf_token)
        uploader = HuggingFaceUploader()
        assert uploader.token == mock_hf_token

    def test_init_without_token(self, monkeypatch):
        """Test initialization fails without token"""
        monkeypatch.delenv("HF_TOKEN", raising=False)
        with pytest.raises(ValueError, match="HuggingFace token is required"):
            HuggingFaceUploader()


class TestHuggingFaceUploaderUploadCondition:
    """Test suite for upload_condition method"""

    @patch("core.hf_uploader.create_repo")
    @patch("core.hf_uploader.HfApi")
    def test_upload_condition_basic(
        self, mock_hf_api_class, mock_create_repo, sample_result, mock_hf_token, tmp_path
    ):
        """Test basic upload flow"""
        # Setup mocks
        mock_api = Mock()
        mock_hf_api_class.return_value = mock_api

        uploader = HuggingFaceUploader(token=mock_hf_token)
        uploader.api = mock_api

        # Execute
        output_dir = tmp_path / "results"
        output_dir.mkdir()

        url = uploader.upload_condition(
            experiment_id="exp001",
            condition_name="baseline",
            result=sample_result,
            output_dir=str(output_dir),
        )

        # Verify
        assert url == "https://huggingface.co/datasets/gdpval-realwork/exp001-baseline"

        # Check create_repo was called
        mock_create_repo.assert_called_once()
        # Verify repo_id is in the call (could be positional or keyword arg)
        call_str = str(mock_create_repo.call_args)
        assert "gdpval-realwork/exp001-baseline" in call_str
        assert "dataset" in call_str

        # Check upload_folder was called
        mock_api.upload_folder.assert_called_once()

        # Check upload_file (README) was called
        mock_api.upload_file.assert_called_once()

    @patch("core.hf_uploader.create_repo")
    @patch("core.hf_uploader.HfApi")
    def test_upload_condition_normalizes_name(
        self, mock_hf_api_class, mock_create_repo, sample_result, mock_hf_token, tmp_path
    ):
        """Test condition name normalization"""
        mock_api = Mock()
        mock_hf_api_class.return_value = mock_api

        uploader = HuggingFaceUploader(token=mock_hf_token)
        uploader.api = mock_api

        output_dir = tmp_path / "results"
        output_dir.mkdir()

        # Test with spaces and underscores
        url = uploader.upload_condition(
            experiment_id="exp002",
            condition_name="Visual Inspection",
            result=sample_result,
            output_dir=str(output_dir),
        )

        assert url == "https://huggingface.co/datasets/gdpval-realwork/exp002-visual-inspection"

        # Verify normalized repo name (spaces and underscores converted to hyphens)
        call_str = str(mock_create_repo.call_args)
        assert "gdpval-realwork/exp002-visual-inspection" in call_str

    @patch("core.hf_uploader.create_repo")
    @patch("core.hf_uploader.HfApi")
    def test_upload_condition_create_repo_fails(
        self, mock_hf_api_class, mock_create_repo, sample_result, mock_hf_token, tmp_path
    ):
        """Test handling of repository creation failure"""
        mock_api = Mock()
        mock_hf_api_class.return_value = mock_api
        mock_create_repo.side_effect = RuntimeError("API error")

        uploader = HuggingFaceUploader(token=mock_hf_token)

        output_dir = tmp_path / "results"
        output_dir.mkdir()

        with pytest.raises(RuntimeError, match="Failed to create repository"):
            uploader.upload_condition(
                experiment_id="exp001",
                condition_name="baseline",
                result=sample_result,
                output_dir=str(output_dir),
            )

    @patch("core.hf_uploader.create_repo")
    @patch("core.hf_uploader.HfApi")
    def test_upload_condition_upload_fails(
        self, mock_hf_api_class, mock_create_repo, sample_result, mock_hf_token, tmp_path
    ):
        """Test handling of upload failure"""
        mock_api = Mock()
        mock_api.upload_folder.side_effect = RuntimeError("Upload failed")
        mock_hf_api_class.return_value = mock_api

        uploader = HuggingFaceUploader(token=mock_hf_token)
        uploader.api = mock_api

        output_dir = tmp_path / "results"
        output_dir.mkdir()

        with pytest.raises(RuntimeError, match="Failed to upload data"):
            uploader.upload_condition(
                experiment_id="exp001",
                condition_name="baseline",
                result=sample_result,
                output_dir=str(output_dir),
            )


class TestHuggingFaceUploaderPrepareEvalsFormat:
    """Test suite for _prepare_evals_format method"""

    def test_prepare_evals_format_creates_structure(self, sample_result, mock_hf_token, tmp_path):
        """Test that evals format creates correct directory structure"""
        uploader = HuggingFaceUploader(token=mock_hf_token)

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        uploader._prepare_evals_format(sample_result, output_dir)

        # Check directories exist
        assert (output_dir / "data").exists()
        assert (output_dir / "deliverable_files").exists()
        assert (output_dir / "data" / "train.jsonl").exists()

    def test_prepare_evals_format_jsonl_content(self, sample_result, mock_hf_token, tmp_path):
        """Test JSONL content format"""
        uploader = HuggingFaceUploader(token=mock_hf_token)

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        uploader._prepare_evals_format(sample_result, output_dir)

        # Read JSONL
        jsonl_path = output_dir / "data" / "train.jsonl"
        with open(jsonl_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        assert len(lines) == 2

        # Check first record
        record1 = json.loads(lines[0])
        assert record1["task_id"] == "task_001"
        assert record1["sector"] == "Finance and Insurance"
        assert record1["deliverable_text"] == "Here is my analysis..."
        assert record1["deliverable_files"] == "deliverable_files/task_001/"

    def test_prepare_evals_format_creates_task_directories(
        self, sample_result, mock_hf_token, tmp_path
    ):
        """Test that task directories are created"""
        uploader = HuggingFaceUploader(token=mock_hf_token)

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        uploader._prepare_evals_format(sample_result, output_dir)

        # Check task directories
        assert (output_dir / "deliverable_files" / "task_001").exists()
        assert (output_dir / "deliverable_files" / "task_002").exists()

        # Check response files
        response1 = output_dir / "deliverable_files" / "task_001" / "response.txt"
        assert response1.exists()
        assert response1.read_text(encoding="utf-8") == "Here is my analysis..."


class TestHuggingFaceUploaderGenerateDatasetCard:
    """Test suite for _generate_dataset_card method"""

    def test_generate_dataset_card_contains_metadata(self, sample_result, mock_hf_token):
        """Test dataset card contains required metadata"""
        uploader = HuggingFaceUploader(token=mock_hf_token)

        readme = uploader._generate_dataset_card(
            experiment_id="exp001",
            condition_name="baseline",
            result=sample_result,
        )

        # Check YAML frontmatter
        assert "---" in readme
        assert "license: mit" in readme
        assert "task_categories:" in readme
        assert "tags:" in readme

        # Check content
        assert "exp001" in readme
        assert "baseline" in readme
        assert "gpt-4" in readme
        assert "**Total Tasks**: 2" in readme

    def test_generate_dataset_card_calculates_statistics(self, sample_result, mock_hf_token):
        """Test statistics calculation in dataset card"""
        uploader = HuggingFaceUploader(token=mock_hf_token)

        readme = uploader._generate_dataset_card(
            experiment_id="exp001",
            condition_name="baseline",
            result=sample_result,
        )

        # Check statistics (with markdown bold formatting)
        assert "**Success Rate**: 100.0%" in readme
        assert "**Total Tokens**: 550" in readme
        assert "**Duration**: 300.0s" in readme  # 5 minutes

    def test_generate_dataset_card_includes_links(self, sample_result, mock_hf_token):
        """Test dataset card includes relevant links"""
        uploader = HuggingFaceUploader(token=mock_hf_token)

        readme = uploader._generate_dataset_card(
            experiment_id="exp001",
            condition_name="baseline",
            result=sample_result,
        )

        assert "arxiv.org/abs/2510.04374" in readme
        assert "huggingface.co/datasets/openai/gdpval" in readme


class TestHuggingFaceUploaderIntegration:
    """Integration tests"""

    @patch("core.hf_uploader.create_repo")
    @patch("core.hf_uploader.HfApi")
    def test_full_upload_flow(
        self, mock_hf_api_class, mock_create_repo, sample_result, mock_hf_token, tmp_path
    ):
        """Test complete upload flow end-to-end"""
        mock_api = Mock()
        mock_hf_api_class.return_value = mock_api

        uploader = HuggingFaceUploader(token=mock_hf_token)
        uploader.api = mock_api

        output_dir = tmp_path / "results"
        output_dir.mkdir()

        url = uploader.upload_condition(
            experiment_id="exp001",
            condition_name="baseline",
            result=sample_result,
            output_dir=str(output_dir),
        )

        # Verify all steps completed
        assert url == "https://huggingface.co/datasets/gdpval-realwork/exp001-baseline"
        assert mock_create_repo.called
        assert mock_api.upload_folder.called
        assert mock_api.upload_file.called

        # Verify data was prepared
        hf_upload_dir = output_dir / "hf_upload"
        assert hf_upload_dir.exists()
        assert (hf_upload_dir / "data" / "train.jsonl").exists()
        assert (hf_upload_dir / "deliverable_files").exists()
