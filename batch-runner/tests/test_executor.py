"""Tests for core/executor.py"""

import pytest
from unittest.mock import Mock, MagicMock, patch

from core.agentic_authorization import provider_endpoint_sha256
from core.executor import TaskExecutor, ExecutionMode


def test_executor_initialization_code_interpreter():
    """Test executor initializes code_interpreter mode"""
    from unittest.mock import patch
    with patch.dict("os.environ", {
        "AZURE_OPENAI_API_KEY": "test_key",
        "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com",
    }):
        executor = TaskExecutor(mode="code_interpreter")
        assert executor.mode == "code_interpreter"
        assert executor.runner is not None


def test_executor_initialization_subprocess():
    """Test executor initializes subprocess mode with llm_client"""
    mock_client = Mock()
    executor = TaskExecutor(mode="subprocess", llm_client=mock_client)
    assert executor.mode == "subprocess"
    assert executor.runner is not None


def test_executor_initialization_json_renderer():
    """Test executor initializes json_renderer mode with llm_client"""
    mock_client = Mock()
    executor = TaskExecutor(mode="json_renderer", llm_client=mock_client)
    assert executor.mode == "json_renderer"
    assert executor.runner is not None


def test_executor_subprocess_requires_llm_client():
    """Test subprocess mode raises error without llm_client"""
    with pytest.raises(ValueError, match="subprocess mode requires llm_client"):
        TaskExecutor(mode="subprocess")


def test_executor_json_renderer_requires_llm_client():
    """Test json_renderer mode raises error without llm_client"""
    with pytest.raises(ValueError, match="json_renderer mode requires llm_client"):
        TaskExecutor(mode="json_renderer")


def test_executor_invalid_mode():
    """Test executor raises error for invalid mode"""
    with pytest.raises(ValueError, match="Unknown execution mode"):
        TaskExecutor(mode="invalid_mode")


def test_executor_validate_mode_code_interpreter_openai():
    """Test code_interpreter mode validation with OpenAI provider"""
    valid, error = TaskExecutor.validate_mode("code_interpreter", "openai")
    assert valid is True
    assert error is None


def test_executor_validate_mode_code_interpreter_azure():
    """Test code_interpreter mode validation with Azure provider"""
    valid, error = TaskExecutor.validate_mode("code_interpreter", "azure")
    assert valid is True
    assert error is None


def test_executor_validate_mode_code_interpreter_anthropic():
    """Test code_interpreter mode validation fails with non-OpenAI provider"""
    valid, error = TaskExecutor.validate_mode("code_interpreter", "anthropic")
    assert valid is False
    assert "requires OpenAI/Azure OpenAI" in error


def test_executor_validate_mode_subprocess():
    """Test subprocess mode validation (works with all providers)"""
    valid, error = TaskExecutor.validate_mode("subprocess", "anthropic")
    assert valid is True
    assert error is None


def test_executor_recommend_mode_openai_tool_assisted():
    """Test mode recommendation for OpenAI with tool_assisted"""
    mode = TaskExecutor.recommend_mode("openai", "tool_assisted")
    assert mode == "code_interpreter"


def test_executor_recommend_mode_azure_tool_assisted():
    """Test mode recommendation for Azure with tool_assisted"""
    mode = TaskExecutor.recommend_mode("azure", "tool_assisted")
    assert mode == "code_interpreter"


def test_executor_recommend_mode_anthropic_tool_assisted():
    """Test mode recommendation for Anthropic with tool_assisted"""
    mode = TaskExecutor.recommend_mode("anthropic", "tool_assisted")
    assert mode == "subprocess"


def test_executor_recommend_mode_portable():
    """Test mode recommendation for portable score_type"""
    mode = TaskExecutor.recommend_mode("openai", "portable")
    assert mode == "json_renderer"

    mode = TaskExecutor.recommend_mode("anthropic", "portable")
    assert mode == "json_renderer"


def test_executor_execute_with_mock_runner():
    """Test executor.execute delegates to runner"""
    mock_client = Mock()
    executor = TaskExecutor(mode="subprocess", llm_client=mock_client)

    # Mock the runner's run method
    executor.runner.run = Mock(return_value={
        "success": True,
        "text": "Test response",
        "files": [],
    })

    result = executor.execute(
        task_prompt="Test task",
        model="gpt-4",
        reference_files=None
    )

    assert result["success"] is True
    assert result["text"] == "Test response"
    assert result["files"] == []
    executor.runner.run.assert_called_once()


def test_executor_execute_error_handling():
    """Test executor handles errors gracefully"""
    mock_client = Mock()
    executor = TaskExecutor(mode="subprocess", llm_client=mock_client)

    # Mock runner to raise exception
    executor.runner.run = Mock(side_effect=Exception("Test error"))

    result = executor.execute(
        task_prompt="Test task",
        model="gpt-4"
    )

    assert result["success"] is False
    assert "Test error" in result["error"]
    assert result["files"] == []


def test_executor_subprocess_passes_token_override():
    """TaskExecutor should pass code_generation token to SubprocessRunner"""
    mock_client = Mock()
    with patch("core.executor.SubprocessRunner") as mock_runner_cls:
        mock_runner = Mock()
        mock_runner_cls.return_value = mock_runner

        TaskExecutor(
            mode="subprocess",
            llm_client=mock_client,
            tokens={"code_generation": 12345},
        )

        kwargs = mock_runner_cls.call_args.kwargs
        assert kwargs["max_completion_tokens"] == 12345


def test_executor_json_renderer_passes_token_override():
    """TaskExecutor should pass json_render token to JsonRenderer"""
    mock_client = Mock()
    with patch("core.executor.JsonRenderer") as mock_runner_cls:
        mock_runner = Mock()
        mock_runner_cls.return_value = mock_runner

        TaskExecutor(
            mode="json_renderer",
            llm_client=mock_client,
            tokens={"json_render": 6789},
        )

        kwargs = mock_runner_cls.call_args.kwargs
        assert kwargs["max_completion_tokens"] == 6789


# ── Sandbox mode ───────────────────────────────────────────────────────────


def test_executor_initialization_sandbox():
    """Test executor initializes sandbox mode with llm_client"""
    mock_client = Mock()
    executor = TaskExecutor(mode="sandbox", llm_client=mock_client)
    assert executor.mode == "sandbox"
    assert executor.runner is not None


def test_executor_sandbox_requires_llm_client():
    """Test sandbox mode raises error without llm_client"""
    with pytest.raises(ValueError, match="sandbox mode requires llm_client"):
        TaskExecutor(mode="sandbox")


def test_executor_validate_mode_sandbox_all_providers():
    """Sandbox mode works with all providers (no provider restriction)"""
    for provider in ("azure", "openai", "anthropic"):
        valid, error = TaskExecutor.validate_mode("sandbox", provider)
        assert valid is True
        assert error is None


def test_executor_sandbox_passes_options_and_tokens():
    """TaskExecutor should forward sandbox_options + token override to SandboxRunner"""
    mock_client = Mock()
    with patch("core.executor.SandboxRunner") as mock_runner_cls:
        mock_runner_cls.return_value = Mock()

        TaskExecutor(
            mode="sandbox",
            llm_client=mock_client,
            tokens={"code_generation": 4242},
            metrics_options={"enabled": True},
            sandbox_options={
                "image": "custom-sandbox:1.0",
                "use_docker": "always",
                "memory_gb": 7,
                "cpus": 3.0,
                "max_skills": 4,
            },
        )

        kwargs = mock_runner_cls.call_args.kwargs
        assert kwargs["max_completion_tokens"] == 4242
        assert kwargs["image"] == "custom-sandbox:1.0"
        assert kwargs["use_docker"] == "always"
        assert kwargs["memory_gb"] == 7
        assert kwargs["cpus"] == 3.0
        assert kwargs["max_skills"] == 4
        assert kwargs["metrics"] == {"enabled": True}


# ── Agentic sandbox mode ──────────────────────────────────────────────────


def test_executor_validate_mode_agentic_openai_only():
    for provider in ("azure", "openai"):
        valid, error = TaskExecutor.validate_mode("agentic_sandbox", provider)
        assert valid is True
        assert error is None

    valid, error = TaskExecutor.validate_mode("agentic_sandbox", "anthropic")
    assert valid is False
    assert "agentic_sandbox mode requires OpenAI/Azure OpenAI" in error


def test_executor_agentic_nonpaid_requires_explicit_fakes():
    with pytest.raises(ValueError, match="explicit backend and authorization fakes"):
        TaskExecutor(
            mode="agentic_sandbox",
            llm_client=Mock(),
            provider="azure",
            non_paid_test_mode=True,
            agentic_options={"pricing": {}},
        )


def test_executor_agentic_forwards_scoped_identity():
    fake_client = Mock()
    backend_factory = Mock()
    authorizer = Mock()
    ledger = Mock()
    with patch("core.executor.AgenticSandboxRunner") as runner_cls:
        runner = Mock()
        runner.run.return_value = {"success": True, "text": "ok", "files": []}
        runner_cls.return_value = runner
        runner_cls.DEFAULT_PROMPT = "agentic_sandbox_solver"

        executor = TaskExecutor(
            mode="agentic_sandbox",
            llm_client=fake_client,
            provider="azure",
            non_paid_test_mode=True,
            agentic_backend_factory=backend_factory,
            agentic_authorize_request=authorizer,
            agentic_budget_ledger=ledger,
            agentic_options={
                "limits": {"max_model_iterations": 3},
                "pricing": {
                    "input_per_million": "0",
                    "output_per_million": "0",
                },
            },
        )
        result = executor.execute(
            task_prompt="task",
            model="deployment",
            task_id="task-1",
            run_id="run-1",
            condition_name="treatment",
        )

        assert result["success"] is True
        constructor = runner_cls.call_args.kwargs
        assert constructor["backend_factory"] is backend_factory
        assert constructor["authorize_request"] is authorizer
        assert constructor["limits"] == {"max_model_iterations": 3}
        run_kwargs = runner.run.call_args.kwargs
        assert run_kwargs["task_id"] == "task-1"
        assert run_kwargs["run_id"] == "run-1"
        assert run_kwargs["condition_name"] == "treatment"


def test_executor_hardened_sandbox_is_explicit_opt_in():
    fake_client = Mock()
    backend_factory = Mock()
    authorizer = Mock()
    ledger = Mock()
    with patch("core.executor.HardenedSandboxRunner") as runner_cls:
        runner = Mock()
        runner.run.return_value = {"success": True, "text": "ok", "files": []}
        runner_cls.return_value = runner

        executor = TaskExecutor(
            mode="sandbox",
            llm_client=fake_client,
            provider="azure",
            non_paid_test_mode=True,
            run_id="paired-run",
            condition_name="baseline",
            model_name="model",
            sandbox_options={"hardened_substrate": True},
            agentic_backend_factory=backend_factory,
            agentic_authorize_request=authorizer,
            agentic_budget_ledger=ledger,
            agentic_options={
                "limits": {"max_api_attempts": 2, "max_model_iterations": 2},
                "pricing": {
                    "input_per_million": "0",
                    "output_per_million": "0",
                },
                "budget": {
                    "paired_run_id": "paired-run",
                    "condition": {
                        "attempts": 40,
                        "input_tokens": 1000000,
                        "output_tokens": 100000,
                        "cost_usd": "25",
                    },
                    "paired_run": {
                        "attempts": 80,
                        "input_tokens": 2000000,
                        "output_tokens": 200000,
                        "cost_usd": "50",
                    },
                },
            },
        )
        result = executor.execute(
            task_prompt="task",
            model="model",
            task_id="task-1",
            run_id="paired-run",
            condition_name="baseline",
        )

        assert result["success"] is True
        assert executor.hardened_sandbox is True
        assert runner_cls.call_args.kwargs["backend_factory"] is backend_factory
        run_kwargs = runner.run.call_args.kwargs
        assert run_kwargs["task_id"] == "task-1"
        assert run_kwargs["run_id"] == "paired-run"
        assert run_kwargs["condition_name"] == "baseline"


def test_executor_production_agentic_refuses_local_compute_fallback(
    tmp_path, monkeypatch
):
    monkeypatch.setenv(
        "AGENTIC_SIGNED_APPROVAL_PATH", str(tmp_path / "approval.json")
    )
    monkeypatch.setenv(
        "AGENTIC_NONCE_LEDGER_PATH", str(tmp_path / "nonce.sqlite3")
    )
    monkeypatch.setenv(
        "AGENTIC_BUDGET_LEDGER_PATH", str(tmp_path / "budget.sqlite3")
    )
    endpoint = "https://fixture.openai.azure.com"
    task_ids = tuple(f"task-{index:02d}" for index in range(20))
    monkeypatch.setattr(
        "core.executor._load_live_approval_scope",
        lambda **kwargs: {
            "conditions": ("treatment",),
            "task_ids": task_ids,
            "input_merkle_roots": {
                task_id: "a" * 64 for task_id in task_ids
            },
            "provider_classifications": {
                task_id: "approved_public_gdpval" for task_id in task_ids
            },
            "approval_scope_sha256": "b" * 64,
            "official_scope_registry_sha256": "c" * 64,
        },
    )
    with pytest.raises(ValueError, match="remote authenticated compute backend"):
        TaskExecutor(
            mode="agentic_sandbox",
            provider="azure",
            client_factory=Mock(),
            run_id="run-1",
            condition_name="treatment",
            model_name="model",
            agentic_endpoint=endpoint,
            agentic_runtime_identity={
                "plan_sha": "b" * 40,
                "implementation_sha": "c" * 40,
                "workflow_sha": "d" * 64,
                "workflow_inputs_sha256": "e" * 64,
            },
            agentic_options={
                "image": "image@sha256:" + "a" * 64,
                "limits": {},
                "pricing": {
                    "input_per_million": "1",
                    "output_per_million": "2",
                },
                "budget": {
                    "paired_run_id": "run-1",
                    "condition": {
                        "attempts": 40,
                        "input_tokens": 1000000,
                        "output_tokens": 100000,
                        "cost_usd": "25",
                    },
                    "paired_run": {
                        "attempts": 80,
                        "input_tokens": 2000000,
                        "output_tokens": 200000,
                        "cost_usd": "50",
                    },
                },
                "authorization": {
                    "api_version": "version",
                    "provider_classification": "approved_public_gdpval",
                    "endpoint_sha256": provider_endpoint_sha256(
                        "azure", endpoint
                    ),
                },
            },
        )


def test_executor_sandbox_defaults_when_no_options():
    """Sandbox mode should use sane defaults when no sandbox_options given"""
    mock_client = Mock()
    with patch("core.executor.SandboxRunner") as mock_runner_cls:
        mock_runner_cls.return_value = Mock()

        TaskExecutor(mode="sandbox", llm_client=mock_client)

        kwargs = mock_runner_cls.call_args.kwargs
        assert kwargs["use_docker"] == "auto"
        assert kwargs["max_skills"] == 5


def test_executor_execute_sandbox_delegates():
    """Test executor.execute delegates to the sandbox runner"""
    mock_client = Mock()
    executor = TaskExecutor(mode="sandbox", llm_client=mock_client)
    executor.runner.run = Mock(return_value={
        "success": True,
        "text": "sandbox response",
        "files": [],
    })

    result = executor.execute(
        task_prompt="Test task",
        model="gpt-5.4",
        reference_files=["/data/clip.mp4"],
    )

    assert result["success"] is True
    assert result["text"] == "sandbox response"
    executor.runner.run.assert_called_once()
