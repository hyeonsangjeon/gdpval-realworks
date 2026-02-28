"""Tests for core/executor.py"""

import pytest
from unittest.mock import Mock, MagicMock, patch

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
