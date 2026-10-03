"""Tests for stable generated-code and provider execution error categories."""

import os
import socket
import subprocess
import time

import pytest

# Pure consumers are imported before installing the test's live-effect guards.
import step2_run_inference as step2
from core import codex_runner
from core.codex_task_deadline import RECOVERY_FAILURE_CATEGORIES
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


def test_output_limit_is_explicit_diagnostic_only(monkeypatch):
    """One offline contract selector, not a diagnosis of retention outcomes."""
    effects = []

    def forbidden(*args, **kwargs):
        effects.append("forbidden")
        raise AssertionError("classifier selector crossed a live/recovery boundary")

    for owner, names in (
        (subprocess, ("Popen", "run", "check_call", "check_output")),
        (socket.socket, ("connect", "connect_ex")),
        (socket, ("create_connection", "getaddrinfo")),
        (os, ("system",)),
        (time, ("sleep",)),
        (step2, ("_execute_single_task", "run_with_infra_retries")),
        (step2.TaskExecutor, ("__init__",)),
        (codex_runner.CodexAgentRunner, ("__init__", "_run_one_turn")),
    ):
        for name in names:
            monkeypatch.setattr(owner, name, forbidden)
    for name in ("OPENAI_API_KEY", "AZURE_OPENAI_API_KEY", "HF_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"):
        monkeypatch.delenv(name, raising=False)

    reason = "Incomplete response returned, reason: max_output_tokens"
    # Exact existing message at docs/run_records/
    # exp035_run34685779030_partial/outcomes.json:6145 (also :6187).
    # All other cases below are synthetic contracts, not newly observed errors.
    recorded = (
        "the Codex turn failed: stream disconnected before completion: "
        "Incomplete response returned, reason: max_output_tokens, mem=187MB"
    )
    positives = (
        recorded,
        reason,
        f"stream disconnected before completion: {reason}",
        f"RuntimeError: {reason}",
        f"openai_codex.errors.CodexError: {reason}",
        f"{reason}, mem=188MB",
        f"{reason} \t",
        reason.upper(),
    )
    for index, text in enumerate(positives):
        assert classify_execution_error(text) == "output_limit_exceeded", ("positive", index)
        assert codex_runner._turn_failure_category(text) == "output_limit_exceeded", ("turn", index)
    print(f"BOUNDARY explicit output-limit reason: {len(positives)} positive shapes")

    negatives = (
        (None, None),
        ("", None),
        ("the stream ended", "execution_error"),
        ("tokens max_tokens output length", "execution_error"),
        ('{"max_output_tokens": 2400}', "execution_error"),
        ("max_output_tokens", "execution_error"),
        ("reason: max_output_tokens", "execution_error"),
        ("ValueError: max_tokens must be positive", "value_error"),
        ("RuntimeError: report output length exceeds the requested width", "execution_error"),
        ('File "output_length.py", line 429, in max_tokens', "execution_error"),
        ('File "run.py", line 8192, in max_output_tokens\nTypeError: bad argument', "type_error"),
        # SDK0.147.0 names a context-window error, not an output-limit enum.
        ("contextWindowExceeded", "execution_error"),
        ("context_length_exceeded: input and max_output_tokens exceed the context window", "execution_error"),
        ("Incomplete response returned, reason: contextWindowExceeded", "execution_error"),
        ("Incomplete response returned, reason: max_input_tokens", "execution_error"),
        ("Incomplete response returned, reason: max_tokens", "execution_error"),
        ("sessionBudgetExceeded", "execution_error"),
        ("usageLimitExceeded", "execution_error"),
        (f"{reason}_per_turn", "execution_error"),
        (f"{reason}.per_turn", "execution_error"),
        (f"{reason}-per-turn", "execution_error"),
        (f"{reason}2", "execution_error"),
        (f"{reason}=2400", "execution_error"),
        (f"{reason} would be a configuration example", "execution_error"),
        (f"RuntimeError: {reason}\nRuntimeError: wrapper failed", "execution_error"),
    )
    for index, (text, expected) in enumerate(negatives):
        assert classify_execution_error(text) == expected, ("negative", index)
        turn_expected = "turn_failed" if expected in (None, "execution_error") else expected
        assert codex_runner._turn_failure_category(text) == turn_expected, ("fallback", index)
    print(f"BOUNDARY ordinary text, context/input limits and unknown fallbacks: {len(negatives)} shapes")

    # The new reason only replaces an unknown fallback. Even lower-priority
    # legacy markers (for example timeout exceeded) retain their old answer.
    precedence = (
        ("HTTP 429 returned by the provider", "rate_limited"),
        ("rate limit reached; timed out; reason: content_filter", "rate_limited"),
        ("reason: content_filter; Transport error: timed out", "content_filtered"),
        ("Transport error: network error; timed out", "transport_error"),
        ("error decoding response body", "transport_error"),
        ("the process timed out", "timeout"),
        ("execution timeout", "timeout"),
        ("timeout exceeded", "timeout"),
        ("out of memory", "out_of_memory"),
        ("not valid UTF-8", "binary_decode_error"),
        ("permission denied", "permission_error"),
        ("MemoryError: allocation failed", "out_of_memory"),
        ("TimeoutError: deadline reached", "timeout"),
        ("ValueError: bad literal", "value_error"),
        ("KeyError: missing field", "schema_error"),
        ("TypeError: wrong argument", "type_error"),
        ("SyntaxError: invalid syntax", "syntax_error"),
        ("FileNotFoundError: missing file", "file_not_found"),
    )
    for index, (text, expected) in enumerate(precedence):
        for variant in (text, f"{text} {reason}", f"{reason}\n{text}"):
            assert classify_execution_error(variant) == expected, ("precedence", index)
            assert codex_runner._turn_failure_category(variant) == expected, ("turn precedence", index)
    for text in (reason, "reason: content_filter", "Transport error: timed out", "unknown"):
        assert codex_runner._turn_failure_category(text, http_status_code=429) == "rate_limited"
    assert codex_runner._turn_failure_category(reason, http_status_code=500) == "output_limit_exceeded"
    print(f"BOUNDARY legacy precedence: {len(precedence)} existing-message cases x3; structured HTTP429 first")

    expected_retryable = frozenset({"rate_limited", "turn_start_failed"})
    assert RECOVERY_FAILURE_CATEGORIES == expected_retryable
    assert step2.RETRYABLE_INFRA_ERROR_CATEGORIES == expected_retryable
    assert step2.NON_RESUMABLE_ERROR_CATEGORIES == frozenset({"content_filtered"})
    for category in (*sorted(expected_retryable), "output_limit_exceeded", "content_filtered",
                     "transport_error", "timeout", "turn_failed", "execution_error"):
        result = {"status": "error", "observability": {"error_category": category}}
        assert step2.infra_retry_category(result) == (category if category in expected_retryable else None)
        result["status"] = "success"
        assert step2.infra_retry_category(result) is None
    assert step2._build_execution_observability(
        {"error_category": codex_runner._turn_failure_category(recorded)}, [],
    ) == {"preprocessors": [], "error_category": "output_limit_exceeded"}
    assert effects == []
    print("BOUNDARY fixed category reaches provenance; recovery/content-filter policy unchanged; zero live effects")
