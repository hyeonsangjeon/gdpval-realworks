"""Tests for core/code_interpreter.py

Note: These are primarily mock tests since actual Code Interpreter
requires Azure OpenAI Responses API access.
"""

import gc
import json
import os
import warnings
from types import SimpleNamespace
from unittest.mock import Mock, MagicMock, patch

import pytest

from core.code_interpreter import (
    CodeInterpreterRunner,
    _CodeInterpreterProviderCallProxy,
    _close_sync_resources,
)


def _injected_client(response=None):
    if response is None:
        response = SimpleNamespace(output=[], output_text="injected result")
    return SimpleNamespace(
        responses=SimpleNamespace(create=Mock(return_value=response)),
        files=SimpleNamespace(
            create=Mock(),
            delete=Mock(),
            content=Mock(),
        ),
        containers=SimpleNamespace(
            create=Mock(),
            files=SimpleNamespace(
                list=Mock(),
                content=SimpleNamespace(retrieve=Mock()),
            ),
        ),
        close=Mock(),
    )


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


def test_injected_client_bypasses_environment_and_sdk_construction():
    client = _injected_client()
    original_getenv = os.getenv

    def guarded_getenv(name, *args):
        if name in {
            "AZURE_OPENAI_ENDPOINT",
            "AZURE_OPENAI_API_KEY",
            "AZURE_API_KEY",
        }:
            raise AssertionError(f"unexpected Azure environment read: {name}")
        return original_getenv(name, *args)

    with patch("core.code_interpreter.os.getenv", side_effect=guarded_getenv), patch(
        "core.code_interpreter.AzureOpenAI"
    ) as constructor:
        runner = CodeInterpreterRunner(client=client)

    assert runner.client is client
    constructor.assert_not_called()


@pytest.mark.parametrize(
    "legacy_kwargs",
    [
        {"api_key": "key"},
        {"endpoint": "https://example.invalid"},
    ],
)
def test_injected_client_rejects_conflicting_legacy_arguments(legacy_kwargs):
    with pytest.raises(ValueError, match="cannot be combined"):
        CodeInterpreterRunner(client=_injected_client(), **legacy_kwargs)


def test_injected_client_requires_exact_code_interpreter_capabilities():
    client = _injected_client()
    client.containers.files.content = SimpleNamespace()

    with pytest.raises(RuntimeError, match="containers.files.content.retrieve"):
        CodeInterpreterRunner(client=client)

    client.close.assert_not_called()


def test_injected_client_prompt_failure_preserves_caller_ownership():
    client = _injected_client()
    prompt_error = RuntimeError("prompt failed")

    with patch("core.code_interpreter.load_prompt", side_effect=prompt_error):
        with pytest.raises(RuntimeError) as caught:
            CodeInterpreterRunner(client=client)

    assert caught.value is prompt_error
    client.close.assert_not_called()


def test_injected_client_run_uses_caller_client():
    client = _injected_client()
    runner = CodeInterpreterRunner(client=client)

    result = runner.run(task_prompt="Create a file", model="deployment")

    assert result == {
        "success": True,
        "text": "injected result",
        "files": [],
    }
    client.responses.create.assert_called_once()


def test_redacted_injected_client_proxy_returns_raw_result_and_is_non_owning():
    response = SimpleNamespace(output=[], output_text="raw result")
    client = _injected_client(response)
    runner = CodeInterpreterRunner(
        client=client,
        redact_provider_errors=True,
    )

    assert isinstance(runner.client, _CodeInterpreterProviderCallProxy)
    assert runner.client._target is client
    assert runner.client.responses.create(model="deployment") is response

    runner.close()
    runner.close()

    client.close.assert_not_called()


@pytest.mark.parametrize("failure_mode", ["attribute", "invocation"])
def test_redacted_proxy_exception_has_no_raw_detail_or_exception_chain(
    failure_mode, capsys
):
    sensitive = (
        "https://private-account.invalid/openai/v1/ "
        "account=private deployment=leaked-only"
    )
    client = _injected_client()
    if failure_mode == "attribute":
        class _Responses:
            def __init__(self):
                self.access_count = 0

            @property
            def create(self):
                self.access_count += 1
                if self.access_count == 1:
                    return lambda **kwargs: object()
                raise OSError(sensitive)

        client.responses = _Responses()
    else:
        client.responses.create.side_effect = OSError(sensitive)
    runner = CodeInterpreterRunner(
        client=client,
        redact_provider_errors=True,
    )

    with pytest.raises(RuntimeError) as caught:
        runner.client.responses.create(model="deployment")

    captured = capsys.readouterr()
    assert str(caught.value) == "Code Interpreter provider error (OSError)"
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    assert sensitive not in str(caught.value)
    assert sensitive not in repr(caught.value)
    assert sensitive not in captured.out + captured.err
    client.close.assert_not_called()


def test_redacted_response_error_uses_class_only(capsys):
    sensitive = (
        "https://private-account.invalid/openai/v1/ "
        "account=private deployment=leaked-only"
    )
    client = _injected_client()
    client.responses.create.side_effect = OSError(sensitive)
    runner = CodeInterpreterRunner(
        client=client,
        redact_provider_errors=True,
    )

    result = runner.run(task_prompt="Create a file", model="deployment")

    captured = capsys.readouterr()
    assert result["error"] == "Code Interpreter provider error (OSError)"
    assert sensitive not in captured.out + captured.err + json.dumps(result)


def test_redacted_upload_error_uses_class_only(tmp_path, capsys):
    sensitive = (
        "https://private-account.invalid/openai/v1/ "
        "account=private deployment=leaked-only"
    )
    reference = tmp_path / "reference.txt"
    reference.write_text("reference", encoding="utf-8")
    client = _injected_client()
    client.files.create.side_effect = OSError(sensitive)
    runner = CodeInterpreterRunner(
        client=client,
        redact_provider_errors=True,
    )

    result = runner.run(
        task_prompt="Create a file",
        model="deployment",
        reference_files=[str(reference)],
    )

    captured = capsys.readouterr()
    assert result["error"] == "Code Interpreter provider error (OSError)"
    assert sensitive not in captured.out + captured.err + json.dumps(result)
    client.responses.create.assert_not_called()


def test_redacted_input_deletion_error_uses_class_only(capsys):
    sensitive = (
        "https://private-account.invalid/openai/v1/ "
        "account=private deployment=leaked-only"
    )
    client = _injected_client()
    client.files.delete.side_effect = OSError(sensitive)
    runner = CodeInterpreterRunner(
        client=client,
        redact_provider_errors=True,
    )
    runner._uploaded_file_ids.add("file-1")

    runner._delete_uploaded_reference_files()

    output = capsys.readouterr().out
    assert "Input file cleanup failed (file-1) (RuntimeError)" in output
    assert sensitive not in output
    assert runner._uploaded_file_ids == set()


def test_redacted_download_errors_use_class_only(capsys):
    sensitive = (
        "https://private-account.invalid/openai/v1/ "
        "account=private deployment=leaked-only"
    )
    client = _injected_client()
    client.containers.files.content.retrieve.side_effect = OSError(sensitive)
    client.files.content.side_effect = OSError(sensitive)
    runner = CodeInterpreterRunner(
        client=client,
        redact_provider_errors=True,
    )

    assert runner._download_file("file-1", "container-1") is None

    output = capsys.readouterr().out
    assert "trying files API (RuntimeError)" in output
    assert "Files API download also failed (file-1) (RuntimeError)" in output
    assert sensitive not in output


def test_redacted_container_scan_error_uses_class_only(capsys):
    sensitive = (
        "https://private-account.invalid/openai/v1/ "
        "account=private deployment=leaked-only"
    )
    client = _injected_client()
    client.containers.files.list.side_effect = OSError(sensitive)
    runner = CodeInterpreterRunner(
        client=client,
        redact_provider_errors=True,
    )
    response = SimpleNamespace(
        output=[SimpleNamespace(
            type="code_interpreter_call",
            container_id="container-1",
            outputs=[],
        )],
        output_text="done",
        container_id=None,
    )

    assert runner._collect_output(response) == []

    output = capsys.readouterr().out
    assert "Container scan failed (container-1) (RuntimeError)" in output
    assert sensitive not in output


def test_legacy_response_error_default_preserves_detail():
    sensitive = "legacy Code Interpreter provider detail"
    client = _injected_client()
    client.responses.create.side_effect = RuntimeError(sensitive)
    runner = CodeInterpreterRunner(client=client)

    result = runner.run(task_prompt="Create a file", model="deployment")

    assert result["error"] == sensitive


@pytest.mark.parametrize(
    ("target", "detail", "with_reference"),
    [
        (
            "build_file_structure_info",
            "local file structure detail: /tmp/private-reference.xlsx",
            False,
        ),
        (
            "render_prompt",
            "local prompt rendering detail: occupation mapping missing",
            False,
        ),
        (
            "open_verified_reference",
            "local verified reference detail: digest mismatch",
            True,
        ),
    ],
)
def test_redacted_local_run_errors_preserve_exact_detail(
    target, detail, with_reference, tmp_path
):
    client = _injected_client()
    runner = CodeInterpreterRunner(
        client=client,
        redact_provider_errors=True,
    )
    reference_files = None
    if with_reference:
        reference = tmp_path / "reference.txt"
        reference.write_text("reference", encoding="utf-8")
        reference_files = [str(reference)]

    with patch(
        f"core.code_interpreter.{target}",
        side_effect=RuntimeError(detail),
    ):
        result = runner.run(
            task_prompt="Create a file",
            model="deployment",
            reference_files=reference_files,
        )

    assert result["error"] == detail
    client.files.create.assert_not_called()
    client.responses.create.assert_not_called()


def test_injected_client_close_cleans_files_without_closing_client():
    client = _injected_client()
    runner = CodeInterpreterRunner(client=client)
    runner._uploaded_file_ids.update({"file-b", "file-a"})

    runner.close()
    runner.close()

    assert client.files.delete.call_args_list == [
        (("file-a",),),
        (("file-b",),),
    ]
    client.close.assert_not_called()
    assert runner._uploaded_file_ids == set()


def test_injected_client_run_after_close_never_calls_api():
    client = _injected_client()
    runner = CodeInterpreterRunner(client=client)
    runner.close()

    result = runner.run(task_prompt="Create a file", model="deployment")

    assert result["success"] is False
    assert result["error"] == "Code Interpreter runner is closed"
    client.responses.create.assert_not_called()


@patch("core.code_interpreter.AzureOpenAI")
def test_legacy_close_closes_owned_client_and_credential(mock_azure_openai):
    client = Mock()
    credential = Mock()
    mock_azure_openai.return_value = client
    identity = MagicMock()
    identity.DefaultAzureCredential.return_value = credential
    identity.get_bearer_token_provider.return_value = object()

    with patch.dict(
        "sys.modules",
        {"azure": MagicMock(), "azure.identity": identity},
    ):
        runner = CodeInterpreterRunner(endpoint="https://example.invalid")

    runner.close()
    runner.close()

    client.close.assert_called_once_with()
    credential.close.assert_called_once_with()


@patch("core.code_interpreter.AzureOpenAI")
def test_redacted_owned_close_closes_raw_client_once(mock_azure_openai):
    client = _injected_client()
    credential = Mock()
    mock_azure_openai.return_value = client
    identity = MagicMock()
    identity.DefaultAzureCredential.return_value = credential
    identity.get_bearer_token_provider.return_value = object()

    with patch.dict(
        "sys.modules",
        {"azure": MagicMock(), "azure.identity": identity},
    ):
        runner = CodeInterpreterRunner(
            endpoint="https://example.invalid",
            redact_provider_errors=True,
        )

    assert isinstance(runner.client, _CodeInterpreterProviderCallProxy)
    assert runner.client._target is client
    assert runner._raw_client is client

    runner.close()
    runner.close()

    client.close.assert_called_once_with()
    credential.close.assert_called_once_with()


@patch("core.code_interpreter.AzureOpenAI")
def test_internal_prompt_failure_closes_client_and_credential_once(
    mock_azure_openai,
):
    client = _injected_client()
    credential = Mock()
    prompt_error = RuntimeError("prompt failed")
    mock_azure_openai.return_value = client
    identity = MagicMock()
    identity.DefaultAzureCredential.return_value = credential
    identity.get_bearer_token_provider.return_value = object()

    with patch.dict(
        "sys.modules",
        {"azure": MagicMock(), "azure.identity": identity},
    ), patch("core.code_interpreter.load_prompt", side_effect=prompt_error):
        with pytest.raises(RuntimeError) as caught:
            CodeInterpreterRunner(endpoint="https://example.invalid")

    assert caught.value is prompt_error
    client.close.assert_called_once_with()
    credential.close.assert_called_once_with()


@patch("core.code_interpreter.AzureOpenAI")
def test_internal_token_assignment_failure_uses_same_cleanup_boundary(
    mock_azure_openai,
):
    class FailingTokens:
        def __getitem__(self, _name):
            raise token_error

    client = _injected_client()
    credential = Mock()
    token_error = RuntimeError("token lookup failed")
    mock_azure_openai.return_value = client
    identity = MagicMock()
    identity.DefaultAzureCredential.return_value = credential
    identity.get_bearer_token_provider.return_value = object()

    with patch.dict(
        "sys.modules",
        {"azure": MagicMock(), "azure.identity": identity},
    ), patch("core.code_interpreter.load_prompt", return_value={}), patch(
        "core.code_interpreter.DEFAULT_TOKENS", FailingTokens()
    ):
        with pytest.raises(RuntimeError) as caught:
            CodeInterpreterRunner(endpoint="https://example.invalid")

    assert caught.value is token_error
    client.close.assert_called_once_with()
    credential.close.assert_called_once_with()


@patch("core.code_interpreter.AzureOpenAI")
def test_internal_cleanup_failure_is_primary_and_retains_init_cause(
    mock_azure_openai,
):
    client = _injected_client()
    credential = Mock()
    initialization_error = RuntimeError("prompt failed")
    cleanup_error = OSError("client close failed")
    client.close.side_effect = cleanup_error
    mock_azure_openai.return_value = client
    identity = MagicMock()
    identity.DefaultAzureCredential.return_value = credential
    identity.get_bearer_token_provider.return_value = object()

    with patch.dict(
        "sys.modules",
        {"azure": MagicMock(), "azure.identity": identity},
    ), patch(
        "core.code_interpreter.load_prompt",
        side_effect=initialization_error,
    ):
        with pytest.raises(OSError) as caught:
            CodeInterpreterRunner(endpoint="https://example.invalid")

    assert caught.value is cleanup_error
    assert caught.value.__cause__ is initialization_error
    client.close.assert_called_once_with()
    credential.close.assert_called_once_with()


@patch("core.code_interpreter.AzureOpenAI")
def test_api_key_fallback_closes_failed_oidc_credential_before_construction(
    mock_azure_openai, capsys
):
    events = []
    oidc_error = RuntimeError("private OIDC detail")
    credential = Mock()
    credential.close.side_effect = lambda: events.append("credential-close")
    key_client = _injected_client()

    def construct(**kwargs):
        if "azure_ad_token_provider" in kwargs:
            events.append("oidc-client")
            raise oidc_error
        events.append("key-client")
        return key_client

    mock_azure_openai.side_effect = construct
    identity = MagicMock()
    identity.DefaultAzureCredential.return_value = credential
    identity.get_bearer_token_provider.return_value = object()

    with patch.dict(
        "sys.modules",
        {"azure": MagicMock(), "azure.identity": identity},
    ):
        runner = CodeInterpreterRunner(
            api_key="not-a-real-key",
            endpoint="https://example.invalid",
        )

    assert events == ["oidc-client", "credential-close", "key-client"]
    assert runner._credential is None
    assert "private OIDC detail" not in capsys.readouterr().out

    runner.close()

    credential.close.assert_called_once_with()
    key_client.close.assert_called_once_with()


@patch("core.code_interpreter.AzureOpenAI")
def test_api_key_fallback_credential_close_failure_is_primary(
    mock_azure_openai,
):
    oidc_error = RuntimeError("OIDC construction failed")
    close_error = OSError("credential close failed")
    credential = Mock()
    credential.close.side_effect = close_error
    mock_azure_openai.side_effect = oidc_error
    identity = MagicMock()
    identity.DefaultAzureCredential.return_value = credential
    identity.get_bearer_token_provider.return_value = object()

    with patch.dict(
        "sys.modules",
        {"azure": MagicMock(), "azure.identity": identity},
    ):
        with pytest.raises(OSError) as caught:
            CodeInterpreterRunner(
                api_key="not-a-real-key",
                endpoint="https://example.invalid",
            )

    assert caught.value is close_error
    assert caught.value.__cause__ is oidc_error
    credential.close.assert_called_once_with()
    assert mock_azure_openai.call_count == 1


def test_close_resources_rejects_async_close_and_attempts_next_owner():
    class AsyncResource:
        async def close(self):
            return None

    owner = Mock()

    with pytest.raises(RuntimeError, match="async client close"):
        _close_sync_resources(
            (("client", AsyncResource()), ("owner", owner))
        )

    owner.close.assert_called_once_with()


def test_close_resources_closes_returned_coroutine_without_warning():
    async def async_close():
        return None

    resource = Mock()
    resource.close.return_value = async_close()
    owner = Mock()

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with pytest.raises(RuntimeError, match="async client close"):
            _close_sync_resources(
                (("client", resource), ("owner", owner))
            )
        gc.collect()

    assert not [
        warning
        for warning in caught
        if "was never awaited" in str(warning.message)
    ]
    owner.close.assert_called_once_with()


def test_close_resources_retains_first_failure_after_later_attempts():
    first_error = RuntimeError("first close failed")
    later_error = OSError("later close failed")
    first = Mock()
    middle = Mock()
    last = Mock()
    first.close.side_effect = first_error
    last.close.side_effect = later_error

    with pytest.raises(RuntimeError) as caught:
        _close_sync_resources(
            (("first", first), ("middle", middle), ("last", last))
        )

    assert caught.value is first_error
    first.close.assert_called_once_with()
    middle.close.assert_called_once_with()
    last.close.assert_called_once_with()


def test_close_resources_deduplicates_same_resource():
    resource = Mock()

    _close_sync_resources((("client", resource), ("credential", resource)))

    resource.close.assert_called_once_with()


@patch("core.code_interpreter.AzureOpenAI")
def test_run_mock_success_via_outputs(mock_azure_openai):
    """Test run with image-type output (Strategy 1: code_interpreter_call.outputs)"""
    mock_client = MagicMock()
    mock_azure_openai.return_value = mock_client

    # Responses API outputs only contains "logs" and "image" types.
    # Non-image files are retrieved via container scan (Strategy 3).
    mock_image_output = Mock()
    mock_image_output.type = "image"
    mock_image_output.file_id = "file_123"
    mock_image_output.filename = "chart.png"

    # Mock code_interpreter_call output item with outputs
    mock_ci_call = Mock()
    mock_ci_call.type = "code_interpreter_call"
    mock_ci_call.container_id = "cntr_abc123"
    mock_ci_call.outputs = [mock_image_output]

    mock_response = Mock()
    mock_response.output = [mock_ci_call]
    mock_response.output_text = "Task completed successfully"
    mock_response.container_id = None  # no response-level container_id

    mock_client.responses.create.return_value = mock_response

    # Mock file content download via container API
    mock_content = Mock()
    mock_content.read.return_value = b"fake png content"
    mock_client.containers.files.content.retrieve.return_value = mock_content

    runner = CodeInterpreterRunner(
        api_key="test_key",
        endpoint="https://test.openai.azure.com",
    )

    result = runner.run(
        task_prompt="Create a chart",
        model="gpt-5.2-chat",
    )

    assert result["success"] is True
    assert result["text"] == "Task completed successfully"
    assert len(result["files"]) == 1
    assert result["files"][0]["filename"] == "chart.png"
    assert result["files"][0]["content"] == b"fake png content"


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
    uploaded_payloads = []

    def upload(*, file, purpose):
        uploaded_payloads.append((file[0], file[1].read(), purpose))
        return mock_uploaded_file

    mock_client.files.create.side_effect = upload

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
    assert uploaded_payloads == [
        ("reference.pdf", b"PDF content", "assistants"),
    ]
    assert result["success"] is True
    mock_client.files.delete.assert_called_once_with("uploaded_file_123")
    assert runner._uploaded_file_ids == set()


@patch("core.code_interpreter.AzureOpenAI")
def test_reference_upload_failure_aborts_before_response(
    mock_azure_openai, tmp_path
):
    mock_client = MagicMock()
    mock_azure_openai.return_value = mock_client
    first = tmp_path / "first.pdf"
    second = tmp_path / "second.pdf"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    uploaded = Mock(id="uploaded-first")
    mock_client.files.create.side_effect = [uploaded, RuntimeError("upload failed")]
    runner = CodeInterpreterRunner(
        api_key="test_key",
        endpoint="https://test.openai.azure.com",
    )

    result = runner.run(
        task_prompt="Process both files",
        model="gpt-4",
        reference_files=[str(first), str(second)],
    )

    assert result["success"] is False
    assert "upload failed" in result["error"]
    mock_client.responses.create.assert_not_called()
    mock_client.files.delete.assert_called_once_with("uploaded-first")
    assert runner._uploaded_file_ids == set()


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
