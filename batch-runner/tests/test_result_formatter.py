"""Tests for Result Formatter

Usage:
    pytest tests/test_result_formatter.py -v
"""

import json
import pytest
from datetime import datetime, timedelta
from pathlib import Path

from core.result_formatter import ResultFormatter
from core.result_collector import TaskResult, ExperimentResult


@pytest.fixture
def sample_experiment_result():
    """Create a sample ExperimentResult with mixed success/error results"""
    started = datetime.utcnow()
    completed = started + timedelta(seconds=10)

    results = [
        # Success results
        TaskResult(
            task_id="task_001",
            prompt_config="baseline",
            content="The revenue is $1.5M",
            model="gpt-5.2-chat",
            usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            latency_ms=123.45,
            timestamp=started + timedelta(seconds=1)
        ),
        TaskResult(
            task_id="task_002",
            prompt_config="baseline",
            content="The profit margin is 15%",
            model="gpt-5.2-chat",
            usage={"prompt_tokens": 110, "completion_tokens": 55, "total_tokens": 165},
            latency_ms=156.78,
            timestamp=started + timedelta(seconds=3)
        ),
        # Error result
        TaskResult(
            task_id="task_003",
            prompt_config="baseline",
            error="API timeout",
            timestamp=started + timedelta(seconds=5)
        ),
    ]

    return ExperimentResult(
        experiment_id="exp001",
        condition_name="baseline",
        model="gpt-5.2-chat",
        results=results,
        started_at=started,
        completed_at=completed
    )


@pytest.fixture
def empty_experiment_result():
    """Create an ExperimentResult with no results"""
    started = datetime.utcnow()
    return ExperimentResult(
        experiment_id="exp_empty",
        condition_name="baseline",
        model="gpt-5.2-chat",
        results=[],
        started_at=started,
        completed_at=None
    )


class TestResultFormatterToDict:
    """Test suite for to_dict() method"""

    def test_to_dict_structure(self, sample_experiment_result):
        """Test that to_dict returns correct structure"""
        formatter = ResultFormatter()
        data = formatter.to_dict(sample_experiment_result)

        assert "experiment_id" in data
        assert "condition_name" in data
        assert "model" in data
        assert "summary" in data
        assert "started_at" in data
        assert "completed_at" in data
        assert "duration_seconds" in data
        assert "results" in data

    def test_to_dict_experiment_metadata(self, sample_experiment_result):
        """Test experiment metadata fields"""
        formatter = ResultFormatter()
        data = formatter.to_dict(sample_experiment_result)

        assert data["experiment_id"] == "exp001"
        assert data["condition_name"] == "baseline"
        assert data["model"] == "gpt-5.2-chat"

    def test_to_dict_summary(self, sample_experiment_result):
        """Test summary statistics"""
        formatter = ResultFormatter()
        data = formatter.to_dict(sample_experiment_result)

        summary = data["summary"]
        assert summary["total_tasks"] == 3
        assert summary["success_count"] == 2
        assert summary["error_count"] == 1
        assert summary["total_tokens"] == 315  # 150 + 165
        assert summary["avg_latency_ms"] > 0
        assert summary["success_rate"] == pytest.approx(66.67, abs=0.01)

    def test_to_dict_timestamps(self, sample_experiment_result):
        """Test timestamp formatting"""
        formatter = ResultFormatter()
        data = formatter.to_dict(sample_experiment_result)

        # Should be ISO format strings
        assert isinstance(data["started_at"], str)
        assert isinstance(data["completed_at"], str)
        assert "T" in data["started_at"]  # ISO format indicator

    def test_to_dict_duration(self, sample_experiment_result):
        """Test duration calculation"""
        formatter = ResultFormatter()
        data = formatter.to_dict(sample_experiment_result)

        # Sample has 10 second duration
        assert data["duration_seconds"] == pytest.approx(10.0, abs=0.1)

    def test_to_dict_duration_none_when_not_completed(self, empty_experiment_result):
        """Test duration is None when experiment not completed"""
        formatter = ResultFormatter()
        data = formatter.to_dict(empty_experiment_result)

        assert data["duration_seconds"] is None
        assert data["completed_at"] is None

    def test_to_dict_results_list(self, sample_experiment_result):
        """Test results list formatting"""
        formatter = ResultFormatter()
        data = formatter.to_dict(sample_experiment_result)

        assert len(data["results"]) == 3
        assert all(isinstance(r, dict) for r in data["results"])

    def test_to_dict_success_result_format(self, sample_experiment_result):
        """Test formatting of successful task result"""
        formatter = ResultFormatter()
        data = formatter.to_dict(sample_experiment_result)

        success_result = data["results"][0]
        assert success_result["status"] == "success"
        assert success_result["task_id"] == "task_001"
        assert success_result["prompt_config"] == "baseline"
        assert success_result["content"] == "The revenue is $1.5M"
        assert success_result["model"] == "gpt-5.2-chat"
        assert success_result["usage"]["total_tokens"] == 150
        assert success_result["latency_ms"] == pytest.approx(123.45)
        assert "timestamp" in success_result

    def test_to_dict_error_result_format(self, sample_experiment_result):
        """Test formatting of error task result"""
        formatter = ResultFormatter()
        data = formatter.to_dict(sample_experiment_result)

        error_result = data["results"][2]
        assert error_result["status"] == "error"
        assert error_result["task_id"] == "task_003"
        assert error_result["error"] == "API timeout"
        assert error_result["content"] is None
        assert error_result["model"] is None
        assert error_result["usage"] is None
        assert error_result["latency_ms"] is None

    def test_to_dict_empty_results(self, empty_experiment_result):
        """Test formatting with no results"""
        formatter = ResultFormatter()
        data = formatter.to_dict(empty_experiment_result)

        assert data["summary"]["total_tasks"] == 0
        assert data["summary"]["success_count"] == 0
        assert data["summary"]["error_count"] == 0
        assert data["summary"]["total_tokens"] == 0
        assert data["summary"]["success_rate"] == 0.0
        assert data["results"] == []


class TestResultFormatterToJson:
    """Test suite for to_json() method"""

    def test_to_json_returns_valid_json(self, sample_experiment_result):
        """Test that to_json returns valid JSON string"""
        formatter = ResultFormatter()
        json_str = formatter.to_json(sample_experiment_result)

        # Should be parseable
        data = json.loads(json_str)
        assert isinstance(data, dict)

    def test_to_json_contains_all_fields(self, sample_experiment_result):
        """Test that JSON contains all expected fields"""
        formatter = ResultFormatter()
        json_str = formatter.to_json(sample_experiment_result)
        data = json.loads(json_str)

        assert "experiment_id" in data
        assert "summary" in data
        assert "results" in data

    def test_to_json_custom_indent(self, sample_experiment_result):
        """Test custom indentation"""
        formatter = ResultFormatter()

        json_4_spaces = formatter.to_json(sample_experiment_result, indent=4)
        json_2_spaces = formatter.to_json(sample_experiment_result, indent=2)

        # 4-space should be longer due to indentation
        assert len(json_4_spaces) > len(json_2_spaces)


class TestResultFormatterToMarkdown:
    """Test suite for to_markdown() method"""

    def test_to_markdown_returns_string(self, sample_experiment_result):
        """Test that to_markdown returns a string"""
        formatter = ResultFormatter()
        md = formatter.to_markdown(sample_experiment_result)

        assert isinstance(md, str)
        assert len(md) > 0

    def test_to_markdown_has_header(self, sample_experiment_result):
        """Test that markdown has proper header"""
        formatter = ResultFormatter()
        md = formatter.to_markdown(sample_experiment_result)

        assert "# Experiment Report: exp001" in md
        assert "**Condition**: baseline" in md
        assert "**Model**: gpt-5.2-chat" in md

    def test_to_markdown_has_summary_section(self, sample_experiment_result):
        """Test that markdown has summary section"""
        formatter = ResultFormatter()
        md = formatter.to_markdown(sample_experiment_result)

        assert "## Summary" in md
        assert "Total Tasks" in md
        assert "Success" in md
        assert "Errors" in md
        assert "Total Tokens" in md
        assert "Avg Latency" in md

    def test_to_markdown_has_timeline(self, sample_experiment_result):
        """Test that markdown has timeline section"""
        formatter = ResultFormatter()
        md = formatter.to_markdown(sample_experiment_result)

        assert "## Timeline" in md
        assert "Started" in md
        assert "Completed" in md
        assert "Duration" in md

    def test_to_markdown_has_success_results(self, sample_experiment_result):
        """Test that markdown has success results section"""
        formatter = ResultFormatter()
        md = formatter.to_markdown(sample_experiment_result)

        assert "## Successful Results" in md
        assert "task_001" in md
        assert "task_002" in md

    def test_to_markdown_has_error_results(self, sample_experiment_result):
        """Test that markdown has error section"""
        formatter = ResultFormatter()
        md = formatter.to_markdown(sample_experiment_result)

        assert "## Errors" in md
        assert "task_003" in md
        assert "API timeout" in md

    def test_to_markdown_empty_results(self, empty_experiment_result):
        """Test markdown with no results"""
        formatter = ResultFormatter()
        md = formatter.to_markdown(empty_experiment_result)

        assert "# Experiment Report" in md
        assert "## Summary" in md
        # Should not have results sections
        assert "## Successful Results" not in md
        assert "## Errors" not in md


class TestResultFormatterFileSaving:
    """Test suite for file saving methods"""

    def test_save_json(self, sample_experiment_result, tmp_path):
        """Test saving to JSON file"""
        formatter = ResultFormatter()
        filepath = tmp_path / "results.json"

        formatter.save_json(sample_experiment_result, str(filepath))

        # File should exist
        assert filepath.exists()

        # Should be valid JSON
        with open(filepath, "r") as f:
            data = json.load(f)
        assert data["experiment_id"] == "exp001"

    def test_save_markdown(self, sample_experiment_result, tmp_path):
        """Test saving to Markdown file"""
        formatter = ResultFormatter()
        filepath = tmp_path / "results.md"

        formatter.save_markdown(sample_experiment_result, str(filepath))

        # File should exist
        assert filepath.exists()

        # Should contain markdown content
        with open(filepath, "r") as f:
            content = f.read()
        assert "# Experiment Report" in content
        assert "## Summary" in content


class TestResultFormatterHelperMethods:
    """Test suite for private helper methods"""

    def test_calculate_duration(self):
        """Test duration calculation"""
        formatter = ResultFormatter()

        start = datetime.utcnow()
        end = start + timedelta(seconds=5)

        duration = formatter._calculate_duration(start, end)
        assert duration == pytest.approx(5.0, abs=0.1)

    def test_calculate_duration_none(self):
        """Test duration with None end time"""
        formatter = ResultFormatter()

        start = datetime.utcnow()
        duration = formatter._calculate_duration(start, None)

        assert duration is None

    def test_format_task_result_success(self):
        """Test formatting successful task result"""
        formatter = ResultFormatter()

        task_result = TaskResult(
            task_id="task_001",
            prompt_config="baseline",
            content="Test content",
            model="gpt-5.2-chat",
            usage={"total_tokens": 100},
            latency_ms=123.45
        )

        formatted = formatter._format_task_result(task_result)

        assert formatted["status"] == "success"
        assert formatted["content"] == "Test content"
        assert formatted["latency_ms"] == pytest.approx(123.45)

    def test_format_task_result_error(self):
        """Test formatting error task result"""
        formatter = ResultFormatter()

        task_result = TaskResult(
            task_id="task_002",
            prompt_config="baseline",
            error="Test error"
        )

        formatted = formatter._format_task_result(task_result)

        assert formatted["status"] == "error"
        assert formatted["error"] == "Test error"
        assert formatted["content"] is None
        assert formatted["latency_ms"] is None


class TestResultFormatterIntegration:
    """Integration tests with realistic data"""

    def test_full_workflow(self, sample_experiment_result, tmp_path):
        """Test complete workflow: dict -> json -> file -> markdown"""
        formatter = ResultFormatter()

        # 1. To dict
        data = formatter.to_dict(sample_experiment_result)
        assert data["experiment_id"] == "exp001"

        # 2. To JSON
        json_str = formatter.to_json(sample_experiment_result)
        assert "exp001" in json_str

        # 3. Save JSON
        json_path = tmp_path / "result.json"
        formatter.save_json(sample_experiment_result, str(json_path))
        assert json_path.exists()

        # 4. To Markdown
        md_str = formatter.to_markdown(sample_experiment_result)
        assert "exp001" in md_str

        # 5. Save Markdown
        md_path = tmp_path / "result.md"
        formatter.save_markdown(sample_experiment_result, str(md_path))
        assert md_path.exists()

    def test_roundtrip_json(self, sample_experiment_result):
        """Test JSON serialization roundtrip"""
        formatter = ResultFormatter()

        # Serialize
        json_str = formatter.to_json(sample_experiment_result)

        # Deserialize
        data = json.loads(json_str)

        # Verify key fields preserved
        assert data["experiment_id"] == "exp001"
        assert data["summary"]["total_tasks"] == 3
        assert len(data["results"]) == 3
