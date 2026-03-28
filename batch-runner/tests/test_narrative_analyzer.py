"""Tests for core.narrative_analyzer — standalone Responses API module."""

import json
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from core.narrative_analyzer import NarrativeAnalyzer, NarrativeResult, create_narrative_analyzer


# ─── _parse_response tests ────────────────────────────────────────────────


class TestParseResponse:
    """Test NarrativeAnalyzer._parse_response static method."""

    def test_valid_json(self):
        raw = '{"overview": "test overview", "quality_analysis": "test qa"}'
        result = NarrativeAnalyzer._parse_response(raw, expected_keys=["overview", "quality_analysis"])
        assert result["overview"] == "test overview"
        assert result["quality_analysis"] == "test qa"

    def test_json_with_code_fence(self):
        raw = '```json\n{"overview": "fenced", "quality_analysis": "ok"}\n```'
        result = NarrativeAnalyzer._parse_response(raw, expected_keys=["overview", "quality_analysis"])
        assert result["overview"] == "fenced"
        assert result["quality_analysis"] == "ok"

    def test_json_with_code_fence_no_closing(self):
        raw = '```json\n{"overview": "no close"}\n'
        result = NarrativeAnalyzer._parse_response(raw, expected_keys=["overview"])
        assert result["overview"] == "no close"

    def test_invalid_json_returns_empty(self):
        raw = "This is not JSON at all"
        result = NarrativeAnalyzer._parse_response(raw, expected_keys=["overview", "quality_analysis"])
        assert result["overview"] == ""
        assert result["quality_analysis"] == ""

    def test_missing_expected_keys_filled(self):
        raw = '{"overview": "present"}'
        result = NarrativeAnalyzer._parse_response(raw, expected_keys=["overview", "quality_analysis"])
        assert result["overview"] == "present"
        assert result["quality_analysis"] == ""

    def test_no_expected_keys(self):
        raw = '{"foo": "bar"}'
        result = NarrativeAnalyzer._parse_response(raw)
        assert result["foo"] == "bar"

    def test_empty_string(self):
        result = NarrativeAnalyzer._parse_response("", expected_keys=["overview"])
        assert result["overview"] == ""

    def test_whitespace_json(self):
        raw = '  \n  {"overview": "trimmed"}  \n  '
        result = NarrativeAnalyzer._parse_response(raw, expected_keys=["overview"])
        assert result["overview"] == "trimmed"


# ─── NarrativeResult dataclass tests ──────────────────────────────────────


class TestNarrativeResult:
    """Test NarrativeResult dataclass construction."""

    def test_default_construction(self):
        r = NarrativeResult()
        assert r.overview == ""
        assert r.quality_analysis == ""
        assert r.failure_patterns == ""
        assert r.recommendations == ""
        assert r.call_1_latency_ms == 0.0
        assert r.call_2_latency_ms == 0.0
        assert r.total_tokens == {"input": 0, "output": 0}

    def test_full_construction(self):
        r = NarrativeResult(
            overview="test overview",
            quality_analysis="test qa",
            failure_patterns="test fp",
            recommendations="test rec",
            call_1_latency_ms=1000.0,
            call_2_latency_ms=2000.0,
            total_tokens={"input": 500, "output": 300},
        )
        assert r.overview == "test overview"
        assert r.call_1_latency_ms == 1000.0
        assert r.total_tokens["input"] == 500

    def test_tokens_not_shared_between_instances(self):
        """Ensure default_factory prevents shared mutable state."""
        r1 = NarrativeResult()
        r2 = NarrativeResult()
        r1.total_tokens["input"] = 999
        assert r2.total_tokens["input"] == 0


# ─── Heartbeat tests ──────────────────────────────────────────────────────


class TestHeartbeat:
    """Test heartbeat start/stop without hanging threads."""

    @patch("core.narrative_analyzer.DefaultAzureCredential", side_effect=Exception("no cred"))
    def test_heartbeat_lifecycle(self, _mock_cred):
        """Heartbeat starts and stops cleanly."""
        # Create analyzer with mocked client (bypass Azure auth)
        analyzer = NarrativeAnalyzer.__new__(NarrativeAnalyzer)
        analyzer.client = MagicMock()
        analyzer.model = "test-model"
        analyzer._heartbeat_active = False
        analyzer._heartbeat_thread = None

        # Start
        analyzer._start_heartbeat()
        assert analyzer._heartbeat_active is True
        assert analyzer._heartbeat_thread is not None
        assert analyzer._heartbeat_thread.daemon is True

        # Stop
        analyzer._stop_heartbeat()
        assert analyzer._heartbeat_active is False
        # Give daemon thread time to notice the flag
        time.sleep(0.1)


# ─── create_narrative_analyzer factory tests ──────────────────────────────


class TestFactory:
    """Test create_narrative_analyzer factory function."""

    def test_missing_endpoint_raises(self):
        with patch.dict("os.environ", {}, clear=True):
            # Remove AZURE_OPENAI_ENDPOINT if present
            import os
            os.environ.pop("AZURE_OPENAI_ENDPOINT", None)
            with pytest.raises(ValueError, match="Azure OpenAI endpoint required"):
                create_narrative_analyzer()

    @patch("core.narrative_analyzer.AzureOpenAI")
    @patch("core.narrative_analyzer.get_bearer_token_provider")
    @patch("core.narrative_analyzer.DefaultAzureCredential")
    def test_factory_with_endpoint(self, mock_cred, mock_token, mock_azure):
        analyzer = create_narrative_analyzer(endpoint="https://test.openai.azure.com/")
        assert analyzer.model == "gpt-5.4-pro"
        mock_azure.assert_called_once()

    @patch("core.narrative_analyzer.AzureOpenAI")
    @patch("core.narrative_analyzer.get_bearer_token_provider")
    @patch("core.narrative_analyzer.DefaultAzureCredential")
    def test_factory_reads_env(self, mock_cred, mock_token, mock_azure):
        with patch.dict("os.environ", {"AZURE_OPENAI_ENDPOINT": "https://env.openai.azure.com/"}):
            analyzer = create_narrative_analyzer()
            assert analyzer.model == "gpt-5.4-pro"


# ─── analyze() orchestration tests ────────────────────────────────────────


class TestAnalyze:
    """Test analyze() orchestration with mocked API calls."""

    def _make_analyzer(self):
        """Create analyzer with mocked client and fast heartbeat."""
        analyzer = NarrativeAnalyzer.__new__(NarrativeAnalyzer)
        analyzer.client = MagicMock()
        analyzer.model = "gpt-5.4-pro"
        analyzer._heartbeat_active = False
        analyzer._heartbeat_thread = None
        # Disable heartbeat in tests to avoid 30s sleeps
        analyzer._start_heartbeat = lambda: None
        analyzer._stop_heartbeat = lambda: None
        return analyzer

    def _mock_response(self, text: str, input_tokens: int = 100, output_tokens: int = 200):
        """Create a mock Responses API response object."""
        mock = MagicMock()
        mock.output_text = text
        mock.usage.input_tokens = input_tokens
        mock.usage.output_tokens = output_tokens
        return mock

    def test_analyze_success(self):
        analyzer = self._make_analyzer()

        call1_json = json.dumps({
            "overview": "Test overview",
            "quality_analysis": "Test QA",
        })
        call2_json = json.dumps({
            "failure_patterns": "Test FP",
            "recommendations": "Test rec",
        })

        analyzer.client.responses.create.side_effect = [
            self._mock_response(call1_json, 600, 1300),
            self._mock_response(call2_json, 9000, 2600),
        ]

        data = {"meta": {"experiment_id": "exp_test", "experiment_name": "Test"}}
        summary = {
            "total_tasks": 220, "success_count": 211, "success_rate_pct": 95.9,
            "error_count": 9, "retried_count": 54, "avg_qa_score": 6.07,
            "min_qa_score": 1, "max_qa_score": 9, "avg_latency_ms": 88425,
        }
        sectors = [{"sector": "Test", "success": 25, "total": 25, "avg_qa_score": 7.0, "avg_latency_ms": 50000}]
        task_results = [{"task_id": "t1", "sector": "Test", "occupation": "Tester", "status": "success"}]
        error_tasks = []

        result = analyzer.analyze(data, summary, sectors, task_results, error_tasks)

        assert result.overview == "Test overview"
        assert result.quality_analysis == "Test QA"
        assert result.failure_patterns == "Test FP"
        assert result.recommendations == "Test rec"
        assert result.total_tokens["input"] == 9600
        assert result.total_tokens["output"] == 3900
        assert analyzer.client.responses.create.call_count == 2

    def test_analyze_call1_invalid_json(self):
        analyzer = self._make_analyzer()

        analyzer.client.responses.create.side_effect = [
            self._mock_response("NOT JSON", 100, 50),
            self._mock_response('{"failure_patterns": "fp", "recommendations": "rec"}', 200, 100),
        ]

        data = {"meta": {"experiment_id": "test"}}
        summary = {
            "total_tasks": 1, "success_count": 1, "success_rate_pct": 100,
            "error_count": 0, "retried_count": 0, "avg_qa_score": 8,
            "min_qa_score": 8, "max_qa_score": 8, "avg_latency_ms": 1000,
        }

        result = analyzer.analyze(data, summary, [], [{"task_id": "t1", "sector": "S", "occupation": "O", "status": "success"}], [])

        # Call 1 failed to parse → overview/quality_analysis should be ""
        assert result.overview == ""
        assert result.quality_analysis == ""
        # Call 2 should still work
        assert result.failure_patterns == "fp"
        assert result.recommendations == "rec"
