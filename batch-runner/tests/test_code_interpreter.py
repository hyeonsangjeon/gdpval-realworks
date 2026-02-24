"""Tests for core/code_interpreter.py

Note: These are primarily mock tests since actual Code Interpreter
requires Azure OpenAI Responses API access.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch

from core.code_interpreter import CodeInterpreterRunner


def test_code_interpreter_initialization():
    """Test CodeInterpreterRunner initializes with credentials"""
    with patch.dict("os.environ", {
        "AZURE_OPENAI_API_KEY": "test_key",
        "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com"
    }):
        runner = CodeInterpreterRunner()
        assert runner.client is not None


def test_code_interpreter_initialization_with_params():
    """Test CodeInterpreterRunner initializes with explicit params"""
    runner = CodeInterpreterRunner(
        api_key="explicit_key",
        endpoint="https://explicit.openai.azure.com"
    )
    assert runner.client is not None


@patch("core.code_interpreter.AzureOpenAI")
def test_run_mock_success_via_outputs(mock_azure_openai):
    """Test run method with mocked successful response using outputs field"""
    mock_client = MagicMock()
    mock_azure_openai.return_value = mock_client

    # Mock file inside outputs
    mock_output_file = Mock()
    mock_output_file.file_id = "file_123"
    mock_output_file.filename = "output.xlsx"

    mock_files_output = Mock()
    mock_files_output.type = "files"
    mock_files_output.files = [mock_output_file]

    # Mock code_interpreter_call output item with outputs
    mock_ci_call = Mock()
    mock_ci_call.type = "code_interpreter_call"
    mock_ci_call.container_id = "cntr_abc123"
    mock_ci_call.outputs = [mock_files_output]

    mock_response = Mock()
    mock_response.output = [mock_ci_call]
    mock_response.output_text = "Task completed successfully"

    mock_client.responses.create.return_value = mock_response

    # Mock file content download via container API
    mock_content = Mock()
    mock_content.read.return_value = b"fake excel content"
    mock_client.containers.files.content.retrieve.return_value = mock_content

    runner = CodeInterpreterRunner(
        api_key="test_key",
        endpoint="https://test.openai.azure.com",
    )

    result = runner.run(
        task_prompt="Create a spreadsheet",
        model="gpt-5.2-chat",
    )

    assert result["success"] is True
    assert result["text"] == "Task completed successfully"
    assert len(result["files"]) == 1
    assert result["files"][0]["filename"] == "output.xlsx"
    assert result["files"][0]["content"] == b"fake excel content"


@patch("core.code_interpreter.AzureOpenAI")
def test_run_mock_success_via_container_scan(mock_azure_openai):
    """Test run method falls back to container scan when outputs is empty"""
    mock_client = MagicMock()
    mock_azure_openai.return_value = mock_client

    # Mock code_interpreter_call with no outputs (empty list)
    mock_ci_call = Mock()
    mock_ci_call.type = "code_interpreter_call"
    mock_ci_call.container_id = "cntr_abc123"
    mock_ci_call.outputs = []  # No direct file refs → triggers container scan

    mock_response = Mock()
    mock_response.output = [mock_ci_call]
    mock_response.output_text = "Task completed successfully"

    mock_client.responses.create.return_value = mock_response

    # Mock container file listing (fallback)
    mock_file = Mock()
    mock_file.id = "file_456"
    mock_file.path = "/mnt/output/output.xlsx"
    mock_file.source = "assistant"

    mock_files_page = Mock()
    mock_files_page.data = [mock_file]
    mock_client.containers.files.list.return_value = mock_files_page

    # Mock file content download
    mock_content = Mock()
    mock_content.read.return_value = b"fake excel content"
    mock_client.containers.files.content.retrieve.return_value = mock_content

    runner = CodeInterpreterRunner(
        api_key="test_key",
        endpoint="https://test.openai.azure.com",
    )

    result = runner.run(
        task_prompt="Create a spreadsheet",
        model="gpt-5.2-chat",
    )

    assert result["success"] is True
    assert len(result["files"]) == 1
    assert result["files"][0]["filename"] == "output.xlsx"


@patch("core.code_interpreter.AzureOpenAI")
def test_run_no_fallback_on_missing_responses(mock_azure_openai):
    """Test that missing responses API raises error (no silent fallback)"""
    mock_client = MagicMock()
    mock_azure_openai.return_value = mock_client

    # Simulate responses.create raising an exception
    mock_client.responses.create.side_effect = TypeError("Unexpected arg")

    runner = CodeInterpreterRunner(
        api_key="test_key",
        endpoint="https://test.openai.azure.com",
    )

    result = runner.run(task_prompt="Test task", model="gpt-4")

    # Should fail — no silent fallback to chat completions
    assert result["success"] is False
    assert "error" in result


@patch("core.code_interpreter.AzureOpenAI")
def test_run_with_reference_files(mock_azure_openai, tmp_path):
    """Test run with reference files upload and _uploaded_file_ids tracking"""
    mock_client = MagicMock()
    mock_azure_openai.return_value = mock_client

    # Create temporary reference file
    ref_file = tmp_path / "reference.pdf"
    ref_file.write_bytes(b"PDF content")

    # Mock file upload
    mock_uploaded_file = Mock()
    mock_uploaded_file.id = "uploaded_file_123"
    mock_client.files.create.return_value = mock_uploaded_file

    # Mock response (with responses API)
    mock_response = Mock()
    mock_response.output = []
    mock_response.output_text = "Processed reference file"

    mock_client.responses.create.return_value = mock_response

    runner = CodeInterpreterRunner(
        api_key="test_key",
        endpoint="https://test.openai.azure.com"
    )

    result = runner.run(
        task_prompt="Process the file",
        model="gpt-4",
        reference_files=[str(ref_file)]
    )

    # Verify file upload was called
    mock_client.files.create.assert_called_once()
    assert result["success"] is True
    # Verify uploaded file IDs are tracked
    assert "uploaded_file_123" in runner._uploaded_file_ids


@patch("core.code_interpreter.AzureOpenAI")
def test_run_error_handling(mock_azure_openai):
    """Test run handles errors gracefully"""
    mock_client = MagicMock()
    mock_azure_openai.return_value = mock_client

    # Mock error
    mock_client.responses.create.side_effect = Exception("API error")

    runner = CodeInterpreterRunner(
        api_key="test_key",
        endpoint="https://test.openai.azure.com"
    )

    result = runner.run(
        task_prompt="Test task",
        model="gpt-4"
    )

    assert result["success"] is False
    assert "error" in result
    assert result["files"] == []


@patch("core.code_interpreter.AzureOpenAI")
def test_run_file_download_error(mock_azure_openai):
    """Test handles file download errors gracefully"""
    mock_client = MagicMock()
    mock_azure_openai.return_value = mock_client

    # Mock code_interpreter_call with container (no outputs → container scan)
    mock_ci_call = Mock()
    mock_ci_call.type = "code_interpreter_call"
    mock_ci_call.container_id = "cntr_xyz"
    mock_ci_call.outputs = []

    mock_response = Mock()
    mock_response.output = [mock_ci_call]
    mock_response.output_text = "Response text"

    mock_client.responses.create.return_value = mock_response

    # Mock file listing ok but download fails (both container & files API)
    mock_file = Mock()
    mock_file.id = "file_123"
    mock_file.path = "/mnt/output/output.pdf"
    mock_file.source = "assistant"

    mock_files_page = Mock()
    mock_files_page.data = [mock_file]
    mock_client.containers.files.list.return_value = mock_files_page

    mock_client.containers.files.content.retrieve.side_effect = Exception("Download failed")
    mock_client.files.content.side_effect = Exception("Files API also failed")

    runner = CodeInterpreterRunner(
        api_key="test_key",
        endpoint="https://test.openai.azure.com",
    )

    result = runner.run(task_prompt="Test", model="gpt-4")

    # Should succeed overall but with no files
    assert result["success"] is True
    assert result["files"] == []


@patch("core.code_interpreter.AzureOpenAI")
def test_run_uses_occupation_and_experiment_prompt(mock_azure_openai):
    """Test that run() uses occupation + experiment_prompt via prompt_loader"""
    mock_client = MagicMock()
    mock_azure_openai.return_value = mock_client

    # Mock successful response with no files
    mock_response = Mock()
    mock_response.output = []
    mock_response.output_text = "Done"
    mock_client.responses.create.return_value = mock_response

    runner = CodeInterpreterRunner(
        api_key="test_key",
        endpoint="https://test.openai.azure.com",
    )

    experiment_prompt = {
        "system": "You are a senior financial analyst.",
        "prefix": "IMPORTANT: Follow company guidelines.",
        "suffix": "Double-check all calculations.",
    }

    result = runner.run(
        task_prompt="Create Q3 report",
        model="gpt-5.2-chat",
        occupation="Financial Analyst",
        experiment_prompt=experiment_prompt,
    )

    assert result["success"] is True

    # Verify the rendered prompt was passed to response.create
    call_kwargs = mock_client.responses.create.call_args
    instructions = call_kwargs.kwargs.get("instructions") or call_kwargs[1].get("instructions")
    input_text = call_kwargs.kwargs.get("input") or call_kwargs[1].get("input")

    # System message should contain occupation from codegen YAML (not experiment system)
    assert "Financial Analyst" in instructions
    # Experiment system should NOT override codegen YAML system
    assert "senior financial analyst" not in instructions

    # User prompt should contain the task, prefix, and suffix
    assert "Create Q3 report" in input_text
    assert "IMPORTANT: Follow company guidelines" in input_text
    assert "Double-check all calculations" in input_text


@patch("core.code_interpreter.AzureOpenAI")
def test_run_default_occupation(mock_azure_openai):
    """Test that run() uses default occupation when none provided"""
    mock_client = MagicMock()
    mock_azure_openai.return_value = mock_client

    mock_response = Mock()
    mock_response.output = []
    mock_response.output_text = "Done"
    mock_client.responses.create.return_value = mock_response

    runner = CodeInterpreterRunner(
        api_key="test_key",
        endpoint="https://test.openai.azure.com",
    )

    result = runner.run(
        task_prompt="Test task",
        model="gpt-4",
    )

    assert result["success"] is True

    # Verify default occupation "professional" is used
    call_kwargs = mock_client.responses.create.call_args
    instructions = call_kwargs.kwargs.get("instructions") or call_kwargs[1].get("instructions")
    assert "professional" in instructions
