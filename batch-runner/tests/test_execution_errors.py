"""Tests for stable generated-code execution error categories."""

import pytest

from core.execution_errors import classify_execution_error


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        ("memory_error: process killed (exit code 137, limit 5GB)", "out_of_memory"),
        ("cv2.error: Insufficient memory; Failed to allocate 24883200 bytes", "out_of_memory"),
        ("Code execution output was not valid UTF-8 text", "binary_decode_error"),
        ("KeyError: 'Invoice Date'", "schema_error"),
        ("AttributeError: merged cell value is read-only", "api_compatibility"),
        ("RuntimeError: boom from solution", "execution_error"),
        (
            "File 'solution.py', line 8, in <module>\n"
            "subprocess.run(cmd, timeout=30)\n"
            "FileNotFoundError: No such file or directory: 'ffmpeg'",
            "file_not_found",
        ),
        ("Traceback ...\nMemoryError: unable to allocate array", "out_of_memory"),
        ("OSError: [Errno 12] Cannot allocate memory", "out_of_memory"),
        ("RuntimeError: CUDA out of memory", "out_of_memory"),
        ("Traceback (most recent call last):\nTimeoutError", "timeout"),
        (
            "TimeoutError: operation timed out\n"
            "The above exception was the direct cause of the following exception:\n"
            "RuntimeError: wrapper failed",
            "execution_error",
        ),
        ("subprocess.run(cmd, timeout=30)", "execution_error"),
    ],
)
def test_classify_actual_runner_error_shapes(error, expected):
    assert classify_execution_error(error) == expected
