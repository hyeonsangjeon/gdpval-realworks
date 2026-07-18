"""Tests for strict agentic tool schemas and dispatch budgets."""

from __future__ import annotations

import json

import pytest

from core.agentic_tools import AgenticToolDispatcher, responses_tool_definitions


class FakeBackend:
    def __init__(self):
        self.calls = []
        self.result = None

    def start(self, timeout_seconds=1200.0):
        return {"ok": True, "data": {}}

    def inspect_workspace(self, timeout_seconds=1200.0):
        self.calls.append("inspect_workspace")
        return {"ok": True, "data": {"file_count": 0}}

    def inspect_environment(self, timeout_seconds=1200.0):
        self.calls.append("inspect_environment")
        return {"ok": True, "data": {"python": "3.11"}}

    def run_python(self, source, timeout_seconds):
        self.calls.append(("run_python", source, timeout_seconds))
        return {"ok": True, "data": {"returncode": 0}}

    def run_ffmpeg(self, operation, timeout_seconds):
        self.calls.append(("run_ffmpeg", operation["operation"]))
        return {"ok": True, "data": {"returncode": 0}}

    def inspect_artifacts(self, timeout_seconds=1200.0):
        self.calls.append("inspect_artifacts")
        return {"ok": True, "data": {"verified": 1}}

    def finalize(self, deliverables, summary, timeout_seconds=1200.0):
        self.calls.append(("finalize", deliverables, summary))
        self.result = {"success": True, "text": summary, "files": []}
        return {"ok": True, "data": {"artifact_count": len(deliverables)}}

    def best_result(self):
        return self.result

    def close(self):
        pass


def test_tool_definitions_are_strict_and_stable():
    tools = responses_tool_definitions()

    assert [tool["name"] for tool in tools] == [
        "inspect_workspace", "inspect_environment", "run_python",
        "run_ffmpeg", "inspect_artifacts", "finalize",
    ]
    assert all(tool["strict"] is True for tool in tools)


def test_dispatch_rejects_malformed_unknown_and_duplicate_calls():
    backend = FakeBackend()
    dispatcher = AgenticToolDispatcher(backend)

    assert dispatcher.dispatch("unknown", "{}").result["error_type"] == "unknown_tool"
    assert dispatcher.dispatch("run_python", "{").result["error_type"] == "malformed_arguments"
    assert dispatcher.dispatch("run_python", json.dumps({
        "source": "print('ok')",
        "timeout_seconds": 5,
        "extra": True,
    })).result["error_type"] == "invalid_arguments"

    arguments = json.dumps({"source": "print('ok')", "timeout_seconds": 5})
    assert dispatcher.dispatch("run_python", arguments).result["ok"] is True
    assert dispatcher.dispatch("run_python", arguments).result["error_type"] == "duplicate_tool_request"


def test_ffmpeg_is_closed_schema_with_one_new_output():
    backend = FakeBackend()
    dispatcher = AgenticToolDispatcher(backend)

    invalid = {
        "operation": "transcode_video",
        "input": "inputs/source.mov",
        "output": "out.mp4",
        "container": "mp4",
        "video_codec": "h264",
        "audio_codec": "aac",
        "width": 1920,
        "height": 1080,
        "fps": 30,
        "start_seconds": 0,
        "duration_seconds": 10,
        "arbitrary_ffmpeg_args": ["-f", "concat"],
    }
    assert dispatcher.dispatch("run_ffmpeg", invalid).result["error_type"] == "invalid_arguments"

    valid = dict(invalid)
    valid.pop("arbitrary_ffmpeg_args")
    assert dispatcher.dispatch("run_ffmpeg", valid).result["ok"] is True
    assert backend.calls == [("run_ffmpeg", "transcode_video")]


def test_finalize_requires_relative_unique_paths_and_terminal_result():
    backend = FakeBackend()
    dispatcher = AgenticToolDispatcher(backend)

    rejected = dispatcher.dispatch("finalize", {
        "deliverables": ["../escape.pdf"],
        "summary": "done",
    })
    assert rejected.result["error_type"] == "invalid_arguments"

    accepted = dispatcher.dispatch("finalize", {
        "deliverables": ["report.pdf"],
        "summary": "done",
    })
    assert accepted.finalized is True
    assert accepted.terminal_result["success"] is True


def test_batch_preflight_rejects_all_calls_before_any_dispatch():
    backend = FakeBackend()
    dispatcher = AgenticToolDispatcher(backend)

    prepared, error = dispatcher.prepare_batch([
        ("inspect_workspace", "{}"),
        ("unexpected_tool", "{}"),
    ])

    assert prepared == []
    assert error == "unknown_tool"
    assert backend.calls == []
    assert dispatcher.total_calls == 0


def test_finalize_must_be_the_only_call_in_a_response():
    backend = FakeBackend()
    dispatcher = AgenticToolDispatcher(backend)

    prepared, error = dispatcher.prepare_batch([
        ("inspect_artifacts", "{}"),
        ("finalize", json.dumps({
            "deliverables": ["report.pdf"], "summary": "done",
        })),
    ])

    assert prepared == []
    assert error == "invalid_finalize_batch"
    assert backend.calls == []


def test_run_python_timeout_is_clamped_to_remaining_task_time():
    backend = FakeBackend()
    dispatcher = AgenticToolDispatcher(backend)
    prepared, error = dispatcher.prepare_batch([(
        "run_python",
        json.dumps({"source": "print('ok')", "timeout_seconds": 100}),
    )])

    assert error is None
    result = dispatcher.dispatch_prepared(
        prepared[0], remaining_seconds=2.5
    )

    assert result.result["ok"] is True
    assert backend.calls == [("run_python", "print('ok')", 2.5)]


def test_same_inspection_is_allowed_after_workspace_mutation():
    backend = FakeBackend()
    dispatcher = AgenticToolDispatcher(backend)

    first = dispatcher.dispatch("inspect_workspace", {})
    duplicate = dispatcher.dispatch("inspect_workspace", {})
    mutated = dispatcher.dispatch("run_python", {
        "source": "print('changed')", "timeout_seconds": 5,
    })
    second = dispatcher.dispatch("inspect_workspace", {})

    assert first.result["ok"] is True
    assert duplicate.result["error_type"] == "duplicate_tool_request"
    assert mutated.result["ok"] is True
    assert second.result["ok"] is True
    assert backend.calls == [
        "inspect_workspace",
        ("run_python", "print('changed')", 5.0),
        "inspect_workspace",
    ]


@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        ("run_python", {"source": "가" * 50_000, "timeout_seconds": 5}),
        ("finalize", {"deliverables": ["report.txt"], "summary": "😀" * 600}),
        ("inspect_artifacts", {"unexpected": "x"}),
    ],
)
def test_tool_arguments_enforce_utf8_byte_limits(name, arguments):
    backend = FakeBackend()
    dispatcher = AgenticToolDispatcher(backend)

    result = dispatcher.dispatch(name, arguments)

    assert result.result["ok"] is False
    assert result.result["error_type"] in {
        "argument_byte_limit_exceeded", "invalid_arguments",
    }