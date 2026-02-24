"""Tests for Result Collector

Usage:
    pytest tests/test_result_collector.py -v
    pytest tests/test_result_collector.py -m integration -v   # 실제 Azure API
"""

import os
import pytest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from core.result_collector import TaskResult, ExperimentResult, ResultCollector
from core.data_loader import GDPValTask


@pytest.fixture
def sample_task():
    """Create a sample GDPValTask"""
    return GDPValTask(
        task_id="task_001",
        occupation="Engineer",
        sector="Finance",
        prompt="Calculate revenue",
        reference_files=[],
        reference_file_urls=[],
        reference_file_hf_uris=[],
        deliverable_text="",
        deliverable_files=[]
    )


@pytest.fixture
def mock_response():
    """Create a mock OpenAI ChatCompletion response"""
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = "The revenue is $1.5M"
    response.model = "gpt-5.2-chat-2025-12-11"
    response.usage = SimpleNamespace(
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150
    )
    response.model_dump.return_value = {
        "id": "chatcmpl-123",
        "model": "gpt-5.2-chat-2025-12-11",
        "choices": [{"message": {"content": "The revenue is $1.5M"}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
    }
    return response


class TestTaskResult:
    """Test suite for TaskResult dataclass"""

    def test_create_success_result(self):
        """Test creating a successful task result"""
        result = TaskResult(
            task_id="task_001",
            prompt_config="baseline",
            content="Hello",
            model="gpt-5.2-chat",
            usage={"total_tokens": 100},
            latency_ms=123.45
        )

        assert result.task_id == "task_001"
        assert result.prompt_config == "baseline"
        assert result.content == "Hello"
        assert result.model == "gpt-5.2-chat"
        assert result.usage["total_tokens"] == 100
        assert result.latency_ms == 123.45
        assert result.error is None
        assert isinstance(result.timestamp, datetime)

    def test_create_error_result(self):
        """Test creating an error result"""
        result = TaskResult(
            task_id="task_002",
            prompt_config="baseline",
            error="API timeout"
        )

        assert result.task_id == "task_002"
        assert result.error == "API timeout"
        assert result.content is None
        assert result.model is None
        assert result.usage is None
        assert result.latency_ms is None

    def test_timestamp_auto_generated(self):
        """Test that timestamp is automatically generated"""
        before = datetime.utcnow()
        result = TaskResult(
            task_id="task_003",
            prompt_config="baseline"
        )
        after = datetime.utcnow()

        assert before <= result.timestamp <= after

    def test_with_raw_response(self):
        """Test storing raw response"""
        raw = {"id": "chatcmpl-123", "model": "gpt-5.2-chat"}
        result = TaskResult(
            task_id="task_004",
            prompt_config="baseline",
            content="Hello",
            raw_response=raw
        )

        assert result.raw_response == raw
        assert result.raw_response["id"] == "chatcmpl-123"


class TestExperimentResult:
    """Test suite for ExperimentResult dataclass"""

    def test_create_experiment_result(self):
        """Test creating an experiment result"""
        started = datetime.utcnow()
        result = ExperimentResult(
            experiment_id="exp001",
            condition_name="baseline",
            model="gpt-5.2-chat",
            results=[],
            started_at=started
        )

        assert result.experiment_id == "exp001"
        assert result.condition_name == "baseline"
        assert result.model == "gpt-5.2-chat"
        assert result.results == []
        assert result.started_at == started
        assert result.completed_at is None

    def test_success_count(self):
        """Test success_count property"""
        result = ExperimentResult(
            experiment_id="exp001",
            condition_name="baseline",
            model="gpt-5.2-chat",
            results=[
                TaskResult(task_id="task_001", prompt_config="baseline", content="OK"),
                TaskResult(task_id="task_002", prompt_config="baseline", error="Failed"),
                TaskResult(task_id="task_003", prompt_config="baseline", content="OK"),
            ],
            started_at=datetime.utcnow()
        )

        assert result.success_count == 2

    def test_error_count(self):
        """Test error_count property"""
        result = ExperimentResult(
            experiment_id="exp001",
            condition_name="baseline",
            model="gpt-5.2-chat",
            results=[
                TaskResult(task_id="task_001", prompt_config="baseline", content="OK"),
                TaskResult(task_id="task_002", prompt_config="baseline", error="Failed"),
                TaskResult(task_id="task_003", prompt_config="baseline", error="Timeout"),
            ],
            started_at=datetime.utcnow()
        )

        assert result.error_count == 2

    def test_total_count(self):
        """Test total_count property"""
        result = ExperimentResult(
            experiment_id="exp001",
            condition_name="baseline",
            model="gpt-5.2-chat",
            results=[
                TaskResult(task_id="task_001", prompt_config="baseline", content="OK"),
                TaskResult(task_id="task_002", prompt_config="baseline", error="Failed"),
            ],
            started_at=datetime.utcnow()
        )

        assert result.total_count == 2

    def test_total_tokens(self):
        """Test total_tokens property"""
        result = ExperimentResult(
            experiment_id="exp001",
            condition_name="baseline",
            model="gpt-5.2-chat",
            results=[
                TaskResult(
                    task_id="task_001", prompt_config="baseline",
                    content="OK", usage={"total_tokens": 100}
                ),
                TaskResult(
                    task_id="task_002", prompt_config="baseline",
                    content="OK", usage={"total_tokens": 150}
                ),
                TaskResult(
                    task_id="task_003", prompt_config="baseline",
                    error="Failed"  # No usage for errors
                ),
            ],
            started_at=datetime.utcnow()
        )

        assert result.total_tokens == 250

    def test_avg_latency_ms(self):
        """Test avg_latency_ms property"""
        result = ExperimentResult(
            experiment_id="exp001",
            condition_name="baseline",
            model="gpt-5.2-chat",
            results=[
                TaskResult(
                    task_id="task_001", prompt_config="baseline",
                    content="OK", latency_ms=100.0
                ),
                TaskResult(
                    task_id="task_002", prompt_config="baseline",
                    content="OK", latency_ms=200.0
                ),
                TaskResult(
                    task_id="task_003", prompt_config="baseline",
                    error="Failed"  # No latency for errors
                ),
            ],
            started_at=datetime.utcnow()
        )

        assert result.avg_latency_ms == 150.0

    def test_avg_latency_with_no_results(self):
        """Test avg_latency_ms with no successful results"""
        result = ExperimentResult(
            experiment_id="exp001",
            condition_name="baseline",
            model="gpt-5.2-chat",
            results=[],
            started_at=datetime.utcnow()
        )

        assert result.avg_latency_ms == 0.0


class TestResultCollector:
    """Test suite for ResultCollector"""

    def test_initialization(self):
        """Test collector initialization"""
        collector = ResultCollector("exp001", "baseline", "gpt-5.2-chat")

        assert collector.experiment.experiment_id == "exp001"
        assert collector.experiment.condition_name == "baseline"
        assert collector.experiment.model == "gpt-5.2-chat"
        assert collector.experiment.results == []
        assert collector.experiment.completed_at is None
        assert isinstance(collector.experiment.started_at, datetime)

    def test_add_success_result(self, sample_task, mock_response):
        """Test adding a successful result"""
        collector = ResultCollector("exp001", "baseline", "gpt-5.2-chat")

        collector.add(sample_task, "baseline", mock_response, latency_ms=123.45)

        assert len(collector.experiment.results) == 1
        result = collector.experiment.results[0]
        assert result.task_id == "task_001"
        assert result.prompt_config == "baseline"
        assert result.content == "The revenue is $1.5M"
        assert result.model == "gpt-5.2-chat-2025-12-11"
        assert result.usage["total_tokens"] == 150
        assert result.latency_ms == 123.45
        assert result.error is None

    def test_add_with_raw_response(self, sample_task, mock_response):
        """Test adding result with raw response saved"""
        collector = ResultCollector("exp001", "baseline", "gpt-5.2-chat")

        collector.add(sample_task, "baseline", mock_response, latency_ms=100.0, save_raw=True)

        result = collector.experiment.results[0]
        assert result.raw_response is not None
        assert result.raw_response["id"] == "chatcmpl-123"
        assert result.raw_response["model"] == "gpt-5.2-chat-2025-12-11"

    def test_add_without_raw_response(self, sample_task, mock_response):
        """Test adding result without saving raw response (default)"""
        collector = ResultCollector("exp001", "baseline", "gpt-5.2-chat")

        collector.add(sample_task, "baseline", mock_response, latency_ms=100.0)

        result = collector.experiment.results[0]
        assert result.raw_response is None

    def test_add_error(self, sample_task):
        """Test adding an error result"""
        collector = ResultCollector("exp001", "baseline", "gpt-5.2-chat")

        collector.add_error(sample_task, "baseline", "API timeout")

        assert len(collector.experiment.results) == 1
        result = collector.experiment.results[0]
        assert result.task_id == "task_001"
        assert result.prompt_config == "baseline"
        assert result.error == "API timeout"
        assert result.content is None
        assert result.model is None

    def test_add_multiple_results(self, sample_task, mock_response):
        """Test adding multiple results"""
        collector = ResultCollector("exp001", "baseline", "gpt-5.2-chat")

        # Add 3 successful results
        for _ in range(3):
            collector.add(sample_task, "baseline", mock_response, latency_ms=100.0)

        # Add 2 errors
        for _ in range(2):
            collector.add_error(sample_task, "baseline", "Error")

        assert len(collector.experiment.results) == 5
        assert collector.experiment.success_count == 3
        assert collector.experiment.error_count == 2

    def test_finalize(self):
        """Test finalizing the experiment"""
        collector = ResultCollector("exp001", "baseline", "gpt-5.2-chat")

        # Initially completed_at is None
        assert collector.experiment.completed_at is None

        # Finalize
        result = collector.finalize()

        # Now completed_at is set
        assert result.completed_at is not None
        assert isinstance(result.completed_at, datetime)
        assert result.completed_at >= result.started_at

    def test_experiment_properties_after_collection(self, sample_task, mock_response):
        """Test experiment properties after collecting results"""
        collector = ResultCollector("exp001", "baseline", "gpt-5.2-chat")

        # Add 2 successful results
        collector.add(sample_task, "baseline", mock_response, latency_ms=100.0)
        collector.add(sample_task, "baseline", mock_response, latency_ms=200.0)

        # Add 1 error
        collector.add_error(sample_task, "baseline", "Error")

        result = collector.finalize()

        assert result.total_count == 3
        assert result.success_count == 2
        assert result.error_count == 1
        assert result.total_tokens == 300  # 150 * 2
        assert result.avg_latency_ms == 150.0  # (100 + 200) / 2

    def test_empty_experiment(self):
        """Test finalizing an experiment with no results"""
        collector = ResultCollector("exp001", "baseline", "gpt-5.2-chat")

        result = collector.finalize()

        assert result.total_count == 0
        assert result.success_count == 0
        assert result.error_count == 0
        assert result.total_tokens == 0
        assert result.avg_latency_ms == 0.0

    def test_different_prompt_configs(self, sample_task, mock_response):
        """Test collecting results with different prompt configs"""
        collector = ResultCollector("exp001", "baseline", "gpt-5.2-chat")

        collector.add(sample_task, "baseline", mock_response, latency_ms=100.0)
        collector.add(sample_task, "visual_inspection", mock_response, latency_ms=150.0)
        collector.add_error(sample_task, "reasoning_high", "Error")

        result = collector.finalize()

        assert result.total_count == 3
        configs = [r.prompt_config for r in result.results]
        assert "baseline" in configs
        assert "visual_inspection" in configs
        assert "reasoning_high" in configs


# ─── Integration Tests (실제 Azure API + ResultCollector) ─────────────────

@pytest.mark.integration
class TestResultCollectorIntegration:
    """실제 Azure OpenAI API를 사용하여 ResultCollector E2E 테스트

    실행 전 환경변수 필요:
        export AZURE_API_KEY="your-key"
        export AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com/"

    실행:
        pytest tests/test_result_collector.py -m integration -v
    """

    @pytest.fixture
    def client(self):
        from core.llm_client import create_client
        api_key = os.getenv("AZURE_OPENAI_API_KEY") or os.getenv("AZURE_API_KEY")
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT") or os.getenv("AZURE_ENDPOINT")

        if not api_key or not endpoint:
            pytest.skip("Azure credentials not set.")

        return create_client(endpoint=endpoint, api_key=api_key)

    @pytest.fixture
    def model(self):
        from core.config import DEFAULT_MODEL
        return os.getenv("AZURE_OPENAI_DEPLOYMENT") or DEFAULT_MODEL

    @pytest.fixture
    def real_task(self):
        return GDPValTask(
            task_id="integ_task_001",
            occupation="Data Analyst",
            sector="Finance and Insurance",
            prompt="Summarize the quarterly revenue trends.",
            reference_files=[],
            reference_file_urls=[],
            reference_file_hf_uris=[],
            deliverable_text="",
            deliverable_files=[]
        )

    def test_single_task_e2e(self, client, model, real_task):
        """실제 API 1건 호출 → ResultCollector 수집 → finalize"""
        from core.llm_client import complete

        collector = ResultCollector("integ_exp001", "baseline", model)

        response, latency_ms = complete(client, model, [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": real_task.prompt},
        ])
        collector.add(real_task, "baseline", response, latency_ms)

        result = collector.finalize()

        assert result.total_count == 1
        assert result.success_count == 1
        assert result.error_count == 0
        assert result.total_tokens > 0
        assert result.avg_latency_ms > 0
        assert result.completed_at is not None
        assert result.results[0].task_id == "integ_task_001"
        assert result.results[0].content is not None
        assert len(result.results[0].content) > 0

        print(f"\n  Content: {result.results[0].content[:80]}...")
        print(f"  Tokens: {result.total_tokens}, Latency: {result.avg_latency_ms:.1f}ms")

    def test_multi_task_e2e(self, client, model, real_task):
        """실제 API 다건 호출 + 에러 혼합 → 집계 확인"""
        from core.llm_client import complete

        collector = ResultCollector("integ_exp002", "baseline", model)

        # 성공 2건
        for i in range(2):
            response, latency_ms = complete(client, model, [
                {"role": "user", "content": f"Say the number {i+1}"},
            ])
            collector.add(real_task, "baseline", response, latency_ms)

        # 에러 1건 (수동)
        collector.add_error(real_task, "baseline", "Simulated timeout")

        result = collector.finalize()

        assert result.total_count == 3
        assert result.success_count == 2
        assert result.error_count == 1
        assert result.total_tokens > 0
        assert result.avg_latency_ms > 0

        print(f"\n  Success: {result.success_count}, Errors: {result.error_count}")
        print(f"  Total tokens: {result.total_tokens}")
        print(f"  Avg latency: {result.avg_latency_ms:.1f}ms")

    def test_with_raw_response(self, client, model, real_task):
        """save_raw=True로 raw_response 저장 확인"""
        from core.llm_client import complete

        collector = ResultCollector("integ_exp003", "baseline", model)

        response, latency_ms = complete(client, model, [
            {"role": "user", "content": "Say hello."},
        ])
        collector.add(real_task, "baseline", response, latency_ms, save_raw=True)

        result = collector.finalize()
        raw = result.results[0].raw_response

        assert raw is not None
        assert "id" in raw
        assert "model" in raw
        assert "choices" in raw
        assert "usage" in raw

        print(f"\n  Response ID: {raw['id']}")
        print(f"  Model: {raw['model']}")

    def test_different_prompt_configs_e2e(self, client, model, real_task):
        """다양한 prompt config로 수집"""
        from core.llm_client import complete

        collector = ResultCollector("integ_exp004", "mixed", model)

        for config in ["baseline", "visual_inspection"]:
            response, latency_ms = complete(client, model, [
                {"role": "system", "content": f"Config: {config}"},
                {"role": "user", "content": "Say OK."},
            ])
            collector.add(real_task, config, response, latency_ms)

        result = collector.finalize()

        assert result.total_count == 2
        configs = [r.prompt_config for r in result.results]
        assert "baseline" in configs
        assert "visual_inspection" in configs

        print(f"\n  Configs collected: {configs}")
