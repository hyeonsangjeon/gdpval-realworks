"""Tests for Evals Submitter

Usage:
    pytest tests/test_evals_submitter.py -v
"""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from core.evals_submitter import EvalsSubmitter


class TestEvalsSubmitterInit:
    """Test suite for EvalsSubmitter initialization"""

    def test_init_with_email(self):
        """Test initialization with email parameter"""
        submitter = EvalsSubmitter(email="test@example.com")
        assert submitter.email == "test@example.com"

    def test_init_with_env_email(self, monkeypatch):
        """Test initialization with environment variable"""
        monkeypatch.setenv("EMAIL", "env@example.com")
        submitter = EvalsSubmitter()
        assert submitter.email == "env@example.com"

    def test_init_without_email(self, monkeypatch):
        """Test initialization fails without email"""
        monkeypatch.delenv("EMAIL", raising=False)
        with pytest.raises(ValueError, match="Email is required"):
            EvalsSubmitter()


class TestEvalsSubmitterSubmit:
    """Test suite for submit method"""

    @patch("core.evals_submitter.EvalsSubmitter._save_submission_record")
    @patch("core.evals_submitter.EvalsSubmitter._try_api_submission")
    def test_submit_manual_mode(
        self, mock_try_api, mock_save_record, monkeypatch
    ):
        """Test submission in manual mode (API not available)"""
        monkeypatch.setenv("EMAIL", "test@example.com")

        # Mock API submission failure
        mock_try_api.return_value = {"success": False}

        submitter = EvalsSubmitter()
        result = submitter.submit(
            dataset_url="https://huggingface.co/datasets/gdpval-realwork/exp001-baseline",
            model_name="gpt-4",
            experiment_id="exp001",
            condition_name="baseline",
        )

        # Verify result
        assert result["status"] == "pending_manual"
        assert result["email"] == "test@example.com"
        assert result["dataset_url"] == "https://huggingface.co/datasets/gdpval-realwork/exp001-baseline"
        assert result["model_name"] == "gpt-4"
        assert "submission_id" in result
        assert "exp001_baseline" in result["submission_id"]

        # Verify submission record was saved
        mock_save_record.assert_called_once()

    @patch("core.evals_submitter.EvalsSubmitter._save_submission_record")
    @patch("core.evals_submitter.EvalsSubmitter._try_api_submission")
    def test_submit_api_mode(
        self, mock_try_api, mock_save_record, monkeypatch
    ):
        """Test submission via API (if available)"""
        monkeypatch.setenv("EMAIL", "test@example.com")

        # Mock successful API submission
        mock_try_api.return_value = {
            "success": True,
            "response": {"submission_id": "api_12345"},
        }

        submitter = EvalsSubmitter()
        result = submitter.submit(
            dataset_url="https://huggingface.co/datasets/gdpval-realwork/exp001-baseline",
            model_name="gpt-4",
            experiment_id="exp001",
            condition_name="baseline",
        )

        # Verify result
        assert result["status"] == "submitted"
        assert result["email"] == "test@example.com"
        assert "Successfully submitted" in result["message"]

        # Verify submission record was NOT saved (API handled it)
        mock_save_record.assert_not_called()


class TestEvalsSubmitterApiSubmission:
    """Test suite for API submission"""

    @patch("core.evals_submitter.requests.post")
    def test_try_api_submission_success(self, mock_post, monkeypatch):
        """Test successful API submission"""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")

        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"submission_id": "api_12345"}
        mock_post.return_value = mock_response

        submitter = EvalsSubmitter(email="test@example.com")
        result = submitter._try_api_submission(
            {"dataset_url": "https://test.com", "model_name": "gpt-4"},
            api_key="sk-test-key",
        )

        assert result["success"] is True
        assert "response" in result

    @patch("core.evals_submitter.requests.post")
    def test_try_api_submission_failure(self, mock_post, monkeypatch):
        """Test failed API submission"""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")

        # Mock failed response
        mock_response = Mock()
        mock_response.status_code = 400
        mock_post.return_value = mock_response

        submitter = EvalsSubmitter(email="test@example.com")
        result = submitter._try_api_submission(
            {"dataset_url": "https://test.com", "model_name": "gpt-4"},
            api_key="sk-test-key",
        )

        assert result["success"] is False
        assert "400" in result["message"]

    def test_try_api_submission_no_key(self, monkeypatch):
        """Test API submission without API key"""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        submitter = EvalsSubmitter(email="test@example.com")
        result = submitter._try_api_submission(
            {"dataset_url": "https://test.com", "model_name": "gpt-4"},
            api_key=None,
        )

        assert result["success"] is False
        assert "No API key" in result["message"]


class TestEvalsSubmitterSaveRecord:
    """Test suite for saving submission records"""

    def test_save_submission_record(self, tmp_path, monkeypatch):
        """Test saving submission record to file"""
        # Set home directory to tmp_path
        monkeypatch.setenv("HOME", str(tmp_path))

        submitter = EvalsSubmitter(email="test@example.com")
        submission_data = {
            "dataset_url": "https://test.com",
            "model_name": "gpt-4",
            "email": "test@example.com",
        }

        submitter._save_submission_record("test_submission", submission_data)

        # Verify file was created
        record_path = tmp_path / ".gdpval" / "submissions" / "test_submission.json"
        assert record_path.exists()

        # Verify content
        with open(record_path, "r") as f:
            saved_data = json.load(f)
        assert saved_data["dataset_url"] == "https://test.com"
        assert saved_data["model_name"] == "gpt-4"


class TestEvalsSubmitterGetStatus:
    """Test suite for getting submission status"""

    def test_get_submission_status_exists(self, tmp_path, monkeypatch):
        """Test getting status of existing submission"""
        # Set home directory to tmp_path
        monkeypatch.setenv("HOME", str(tmp_path))

        submitter = EvalsSubmitter(email="test@example.com")
        submission_data = {
            "dataset_url": "https://test.com",
            "model_name": "gpt-4",
            "email": "test@example.com",
        }

        # Save record
        submitter._save_submission_record("test_submission", submission_data)

        # Get status
        status = submitter.get_submission_status("test_submission")

        assert status is not None
        assert status["dataset_url"] == "https://test.com"
        assert status["model_name"] == "gpt-4"

    def test_get_submission_status_not_exists(self, tmp_path, monkeypatch):
        """Test getting status of non-existent submission"""
        monkeypatch.setenv("HOME", str(tmp_path))

        submitter = EvalsSubmitter(email="test@example.com")
        status = submitter.get_submission_status("nonexistent_submission")

        assert status is None
