"""Tests for core/subprocess_runner.py"""

import platform
import pytest
from unittest.mock import Mock, patch

from core.config import DEFAULT_TOKENS
from core.subprocess_runner import (
    PREFLIGHT_MAX_LINE_BYTES,
    PREFLIGHT_PREFIX,
    SubprocessRunner,
    parse_execution_streams,
)


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def mock_llm_client():
    """Create mock LLM client"""
    client = Mock()
    return client


@pytest.fixture
def subprocess_runner(mock_llm_client):
    """Create SubprocessRunner with mock client"""
    return SubprocessRunner(mock_llm_client)


def test_subprocess_runner_initialization(subprocess_runner):
    """Test SubprocessRunner initializes with llm_client"""
    assert subprocess_runner.llm_client is not None
    assert subprocess_runner.max_completion_tokens == DEFAULT_TOKENS["code_generation"]


def test_subprocess_runner_token_override(mock_llm_client):
    """Custom max_completion_tokens should override default"""
    runner = SubprocessRunner(mock_llm_client, max_completion_tokens=2222)
    assert runner.max_completion_tokens == 2222


def test_extract_code_python_block(subprocess_runner):
    """Test code extraction from ```python blocks"""
    text = """Here's the code:
```python
print("Hello, World!")
```
"""
    code = subprocess_runner._extract_code(text)
    assert code == 'print("Hello, World!")'


def test_extract_code_multiple_blocks(subprocess_runner):
    """Test code extraction with multiple blocks (returns first)"""
    text = """Code 1:
```python
print("First")
```

Code 2:
```python
print("Second")
```
"""
    code = subprocess_runner._extract_code(text)
    assert "First" in code


def test_extract_code_generic_block(subprocess_runner):
    """Test code extraction from generic ``` blocks"""
    text = """```
import sys
print("Hello")
```"""
    code = subprocess_runner._extract_code(text)
    assert code is not None
    assert "import" in code or "print" in code


def test_extract_code_no_block(subprocess_runner):
    """Test code extraction returns None when no code block found"""
    text = "This is just plain text with no code blocks."
    code = subprocess_runner._extract_code(text)
    assert code is None


def test_preflight_protocol_uses_first_bounded_record():
    valid = (
        PREFLIGHT_PREFIX
        + '{"ok":true,"stage":"compile","target_python":"3.11.15"}\n'
    )
    spoofed = (
        PREFLIGHT_PREFIX
        + '{"ok":false,"stage":"compile","target_python":"9.9.9"}\n'
    )

    _, cleaned, preflight, decode_error = parse_execution_streams(
        b"",
        (valid + "user stderr\n" + spoofed).encode("utf-8"),
    )

    assert preflight["ok"] is True
    assert preflight["target_python"] == "3.11.15"
    assert "user stderr" in cleaned
    assert PREFLIGHT_PREFIX in cleaned  # later untrusted lookalikes are ordinary stderr
    assert decode_error is False


@pytest.mark.parametrize(
    "payload",
    [
        "[]",
        '"not-an-object"',
        '{"ok":"yes","stage":"compile","target_python":"3.11.15"}',
        '{"ok":true,"stage":"other","target_python":"3.11.15"}',
    ],
)
def test_preflight_protocol_rejects_invalid_schema(payload):
    line = f"{PREFLIGHT_PREFIX}{payload}\n"

    _, _, preflight, _ = parse_execution_streams(b"", line.encode("utf-8"))

    assert preflight is None


def test_preflight_protocol_rejects_oversized_first_record():
    oversized = PREFLIGHT_PREFIX + ("x" * PREFLIGHT_MAX_LINE_BYTES) + "\n"
    valid_later = (
        PREFLIGHT_PREFIX
        + '{"ok":true,"stage":"compile","target_python":"3.11.15"}\n'
    )

    _, _, preflight, _ = parse_execution_streams(
        b"",
        (oversized + valid_later).encode("utf-8"),
    )

    assert preflight is None


def test_execute_safely_simple_script(subprocess_runner):
    """Test safe execution of simple Python script"""
    code = """
print("Hello from subprocess!")
with open("output.txt", "w") as f:
    f.write("Test output")
"""
    result = subprocess_runner._execute_safely(code, reference_files=None)

    assert result["success"] is True
    assert "Hello from subprocess!" in result["text"]
    assert len(result["files"]) == 1
    assert result["files"][0]["filename"] == "output.txt"
    assert result["preflight"]["ok"] is True


def test_preflight_survives_chdir_and_protocol_spoof(subprocess_runner):
    code = (
        "import os\n"
        "import sys\n"
        "os.chdir('/')\n"
        f"sys.stderr.write({PREFLIGHT_PREFIX!r} + '[]\\n')\n"
        "print('done')\n"
    )

    result = subprocess_runner._execute_safely(code)

    assert result["success"] is True
    assert result["preflight"]["ok"] is True
    assert "done" in result["text"]


def test_preflight_survives_untrusted_os_exit(subprocess_runner):
    result = subprocess_runner._execute_safely("import os\nos._exit(7)\n")

    assert result["success"] is False
    assert result["preflight"]["ok"] is True
    assert result["error_category"] == "execution_error"


def test_binary_output_preserves_preflight(subprocess_runner):
    result = subprocess_runner._execute_safely("import os\nos.write(1, b'\\xff')\n")

    assert result["success"] is False
    assert result["preflight"]["ok"] is True
    assert result["error_category"] == "binary_decode_error"


def test_execute_safely_file_generation(subprocess_runner):
    """Test execution generates files correctly"""
    code = """
import json

# Create JSON file
data = {"test": "value"}
with open("data.json", "w") as f:
    json.dump(data, f)

# Create text file
with open("output.md", "w") as f:
    f.write("# Test Markdown")

print("Files created")
"""
    result = subprocess_runner._execute_safely(code)

    assert result["success"] is True
    assert len(result["files"]) == 2
    filenames = [f["filename"] for f in result["files"]]
    assert "data.json" in filenames
    assert "output.md" in filenames


def test_execute_safely_timeout(subprocess_runner):
    """Test execution timeout protection"""
    subprocess_runner.timeout = 3  # Short timeout for testing
    code = """
import time
time.sleep(200)  # Exceeds 3s test timeout
"""
    result = subprocess_runner._execute_safely(code)

    assert result["success"] is False
    assert "timeout" in result["error"].lower()
    assert result["error_category"] == "timeout"


def test_execute_safely_error_handling(subprocess_runner):
    """Test execution handles errors gracefully"""
    code = """
raise ValueError("Test error")
"""
    result = subprocess_runner._execute_safely(code)

    assert result["success"] is False
    assert "ValueError" in result["error"] or "Test error" in result["text"]
    assert result["error_category"] == "value_error"


def test_execute_safely_no_api_keys_in_env(subprocess_runner):
    """Test subprocess does not inherit API keys"""
    code = """
import os
api_key = os.environ.get("AZURE_OPENAI_API_KEY")
hf_token = os.environ.get("HF_TOKEN")
print(f"API_KEY: {api_key}")
print(f"HF_TOKEN: {hf_token}")
"""
    result = subprocess_runner._execute_safely(code)

    assert result["success"] is True
    assert "None" in result["text"]  # Keys should be None


@patch("core.subprocess_runner.complete")
def test_run_full_pipeline(mock_complete, subprocess_runner):
    """Test full run pipeline with mocked LLM response"""
    # Mock LLM response with code
    mock_response = Mock()
    mock_response.choices = [
        Mock(message=Mock(content="""```python
with open("test.txt", "w") as f:
    f.write("Generated by LLM")
print("Done")
```"""))
    ]
    mock_response.usage = Mock(total_tokens=100)

    mock_complete.return_value = (mock_response, 100)

    result = subprocess_runner.run(
        task_prompt="Create a test file",
        model="gpt-4"
    )

    assert result["success"] is True
    assert len(result["files"]) == 1
    assert result["files"][0]["filename"] == "test.txt"
    assert result["files"][0]["content"] == b"Generated by LLM"


@patch("core.subprocess_runner.complete")
def test_run_no_code_generated(mock_complete, subprocess_runner):
    """Test run handles case when LLM doesn't generate code"""
    mock_response = Mock()
    mock_response.choices = [
        Mock(message=Mock(content="I cannot generate code for this task."))
    ]

    mock_complete.return_value = (mock_response, 100)

    result = subprocess_runner.run(
        task_prompt="Test task",
        model="gpt-4"
    )

    assert result["success"] is False
    assert "No Python code found" in result["error"]


def test_code_gen_prompt_loaded_from_yaml(subprocess_runner):
    """Test prompt is loaded from external YAML file"""
    assert subprocess_runner.prompt_data is not None
    assert "user_prompt" in subprocess_runner.prompt_data
    assert "system_message" in subprocess_runner.prompt_data
    prompt = subprocess_runner.prompt_data["user_prompt"]
    assert "python-docx" in prompt
    assert "reportlab" in prompt
    assert "openpyxl" in prompt
    assert "Pillow" in prompt
    assert "matplotlib" in prompt


def test_run_with_reference_files(subprocess_runner, tmp_path):
    """Test execution with reference files"""
    # Create temporary reference file
    ref_file = tmp_path / "reference.txt"
    ref_file.write_text("Reference content")

    code = """
# Read reference file
with open("reference.txt", "r") as f:
    content = f.read()

# Create output
with open("output.txt", "w") as f:
    f.write(f"Processed: {content}")
"""
    result = subprocess_runner._execute_safely(
        code,
        reference_files=[str(ref_file)]
    )

    assert result["success"] is True
    output_file = next(f for f in result["files"] if f["filename"] == "output.txt")
    assert b"Processed: Reference content" in output_file["content"]


def test_reference_copy_failure_is_fatal_before_subprocess(
    subprocess_runner, tmp_path, monkeypatch
):
    ref_file = tmp_path / "reference.txt"
    ref_file.write_text("Reference content", encoding="utf-8")
    monkeypatch.setattr(
        "core.reference_integrity.shutil.copyfileobj",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("copy failed")),
    )
    started = []
    monkeypatch.setattr(
        "core.subprocess_runner.subprocess.run",
        lambda *_args, **_kwargs: started.append(True),
    )

    result = subprocess_runner._execute_safely(
        "print('should not run')",
        reference_files=[str(ref_file)],
    )

    assert result["success"] is False
    assert "copy failed" in result["error"]
    assert started == []


def test_reference_staging_failure_is_fatal_before_codegen(
    subprocess_runner, tmp_path, monkeypatch
):
    reference = tmp_path / "reference.txt"
    reference.write_text("reference", encoding="utf-8")
    model_calls = []
    monkeypatch.setattr(
        "core.reference_integrity.shutil.copyfileobj",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("copy failed")),
    )
    monkeypatch.setattr(
        "core.subprocess_runner.complete",
        lambda **_kwargs: model_calls.append(True),
    )

    result = subprocess_runner.run(
        task_prompt="Create a report",
        model="model",
        reference_files=[str(reference)],
    )

    assert result["success"] is False
    assert "copy failed" in result["error"]
    assert model_calls == []


# ── Memory limit / OOM detection tests ───────────────────────────────────


def test_memory_limit_config(monkeypatch):
    """SUBPROCESS_MEMORY_GB env override should propagate to config."""
    monkeypatch.setenv("SUBPROCESS_MEMORY_GB", "3")
    # Re-import to pick up the new env
    import importlib
    import core.config as cfg_mod
    importlib.reload(cfg_mod)
    assert cfg_mod.SUBPROCESS_MEMORY_GB == 3
    # Restore default
    monkeypatch.delenv("SUBPROCESS_MEMORY_GB")
    importlib.reload(cfg_mod)


def test_oom_exit_code_minus9(subprocess_runner):
    """Exit code -9 (SIGKILL) should return memory_error prefix."""
    mock_result = Mock()
    mock_result.returncode = -9
    mock_result.stdout = "partial output"
    mock_result.stderr = ""

    with patch("subprocess.run", return_value=mock_result):
        result = subprocess_runner._execute_safely("print('hi')")

    assert result["success"] is False
    assert result["error"].startswith("memory_error:")
    assert result["error_category"] == "out_of_memory"
    assert "-9" in result["error"]


@pytest.mark.skipif(platform.system() == "Windows", reason="POSIX signal required")
def test_real_sigkill_preserves_successful_preflight(subprocess_runner):
    code = (
        "import os\n"
        "import signal\n"
        "os.kill(os.getpid(), signal.SIGKILL)\n"
    )

    result = subprocess_runner._execute_safely(code)

    assert result["error_category"] == "out_of_memory"
    assert result["preflight"]["ok"] is True
    assert result["preflight"]["stage"] == "compile"


def test_oom_exit_code_137(subprocess_runner):
    """Exit code 137 (128+SIGKILL) should return memory_error prefix."""
    mock_result = Mock()
    mock_result.returncode = 137
    mock_result.stdout = ""
    mock_result.stderr = ""

    with patch("subprocess.run", return_value=mock_result):
        result = subprocess_runner._execute_safely("print('hi')")

    assert result["success"] is False
    assert result["error"].startswith("memory_error:")
    assert result["error_category"] == "out_of_memory"
    assert "137" in result["error"]


def test_oom_memory_error_in_stderr(subprocess_runner):
    """MemoryError in stderr should return memory_error prefix."""
    mock_result = Mock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    mock_result.stderr = "Traceback ...\nMemoryError: unable to allocate array"

    with patch("subprocess.run", return_value=mock_result):
        result = subprocess_runner._execute_safely("print('hi')")

    assert result["success"] is False
    assert result["error"].startswith("memory_error:")
    assert result["error_category"] == "out_of_memory"


def test_oom_cannot_allocate_in_stderr(subprocess_runner):
    """'Cannot allocate memory' in stderr should return memory_error prefix."""
    mock_result = Mock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    mock_result.stderr = "OSError: [Errno 12] Cannot allocate memory"

    with patch("subprocess.run", return_value=mock_result):
        result = subprocess_runner._execute_safely("print('hi')")

    assert result["success"] is False
    assert result["error"].startswith("memory_error:")
    assert result["error_category"] == "out_of_memory"


def test_binary_decode_error_has_structured_category(subprocess_runner):
    decode_error = UnicodeDecodeError("utf-8", b"\xa9", 0, 1, "invalid")

    with patch("subprocess.run", side_effect=decode_error):
        result = subprocess_runner._execute_safely("print('hi')")

    assert result["success"] is False
    assert result["error_category"] == "binary_decode_error"
    assert "not valid UTF-8" in result["error"]


def test_generic_error_not_tagged_as_oom(subprocess_runner):
    """Non-OOM failures should NOT have memory_error prefix."""
    mock_result = Mock()
    mock_result.returncode = 1
    mock_result.stdout = ""
    mock_result.stderr = "FileNotFoundError: No such file"

    with patch("subprocess.run", return_value=mock_result):
        result = subprocess_runner._execute_safely("print('hi')")

    assert result["success"] is False
    assert not result["error"].startswith("memory_error:")
    assert "Code execution failed" in result["error"]
    assert result["error_category"] == "file_not_found"


def test_memory_limit_graceful_on_unsupported_os(subprocess_runner):
    """_set_memory_limit should not raise on platforms without RLIMIT_AS (macOS)."""
    result = subprocess_runner._execute_safely("print('hello')")
    # preexec_fn should NOT cause failure on any platform
    if platform.system() == "Darwin":
        # macOS: RLIMIT_AS is a no-op, code executes normally
        assert result["success"] is True
        assert "preexec_fn" not in result.get("error", "")
    else:
        # Linux: RLIMIT_AS works, code also executes normally
        assert result["success"] is True


# ── Denylist file collection tests ───────────────────────────────────────


def test_collect_any_extension(subprocess_runner):
    """Denylist approach should collect files of any extension."""
    code = """
with open("output.wav", "wb") as f:
    f.write(b"RIFF" + b"\\x00" * 100)
with open("result.fodp", "w") as f:
    f.write("<xml>test</xml>")
with open("notes.txt", "w") as f:
    f.write("done")
with open("data.npy", "wb") as f:
    f.write(b"\\x93NUMPY" + b"\\x00" * 50)
"""
    result = subprocess_runner._execute_safely(code)
    assert result["success"] is True
    filenames = {f["filename"] for f in result["files"]}
    assert "output.wav" in filenames
    assert "result.fodp" in filenames
    assert "notes.txt" in filenames
    assert "data.npy" in filenames
    # solution.py should NOT be collected
    assert "solution.py" not in filenames


def test_skip_reference_files(subprocess_runner, tmp_path):
    """Reference input files should not appear in output."""
    ref_file = tmp_path / "input_data.xlsx"
    ref_file.write_bytes(b"fake excel")

    code = """
with open("report.pdf", "wb") as f:
    f.write(b"%PDF-1.4 fake")
"""
    result = subprocess_runner._execute_safely(code, reference_files=[str(ref_file)])
    assert result["success"] is True
    filenames = {f["filename"] for f in result["files"]}
    assert "report.pdf" in filenames
    # Reference file should be excluded
    assert "input_data.xlsx" not in filenames


def test_skip_pycache(subprocess_runner):
    """__pycache__ and .pyc files should not be collected."""
    code = """
import py_compile, os
with open("helper.py", "w") as f:
    f.write("x = 1")
py_compile.compile("helper.py")
with open("output.txt", "w") as f:
    f.write("done")
"""
    result = subprocess_runner._execute_safely(code)
    assert result["success"] is True
    filenames = {f["filename"] for f in result["files"]}
    assert "output.txt" in filenames
    # .pyc should not be collected (it's in __pycache__/ dir anyway)
    assert not any(f.endswith(".pyc") for f in filenames)
    # solution.py excluded, but helper.py IS a generated file → collected
    assert "helper.py" in filenames
