"""Strict model-visible tools for the task-solving agentic sandbox."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Protocol

from jsonschema import Draft202012Validator


TOOL_NAMES = (
    "inspect_workspace",
    "inspect_environment",
    "run_python",
    "run_ffmpeg",
    "inspect_artifacts",
    "finalize",
)

_EMPTY_SCHEMA = {
    "type": "object",
    "properties": {},
    "additionalProperties": False,
}

_PATH_SCHEMA = {
    "type": "string",
    "minLength": 1,
    "maxLength": 240,
    "pattern": r"^(?!/)(?!.*(?:^|/)\.\.(?:/|$))(?!.*[:\\\x00-\x1f]).+$",
}

_TIMING_PROPERTIES = {
    "start_seconds": {"type": "number", "minimum": 0, "maximum": 3600},
    "duration_seconds": {"type": "number", "minimum": 0.1, "maximum": 600},
}

_AUDIO_PROPERTIES = {
    "input": _PATH_SCHEMA,
    "output": _PATH_SCHEMA,
    "format": {"enum": ["wav", "flac"]},
    "sample_rate": {"enum": [8000, 16000, 22050, 44100, 48000]},
    "channels": {"enum": [1, 2]},
    **_TIMING_PROPERTIES,
}


def _operation_schema(operation: str, properties: dict, required: list[str]) -> dict:
    return {
        "type": "object",
        "properties": {
            "operation": {"const": operation},
            **properties,
        },
        "required": ["operation", *required],
        "additionalProperties": False,
    }


FFMPEG_SCHEMA = {
    "oneOf": [
        _operation_schema("probe", {"input": _PATH_SCHEMA}, ["input"]),
        _operation_schema(
            "extract_audio",
            _AUDIO_PROPERTIES,
            ["input", "output", "format", "sample_rate", "channels",
             "start_seconds", "duration_seconds"],
        ),
        _operation_schema(
            "transcode_audio",
            _AUDIO_PROPERTIES,
            ["input", "output", "format", "sample_rate", "channels",
             "start_seconds", "duration_seconds"],
        ),
        _operation_schema(
            "transcode_video",
            {
                "input": _PATH_SCHEMA,
                "output": _PATH_SCHEMA,
                "container": {"enum": ["mp4", "webm"]},
                "video_codec": {"enum": ["h264", "vp9"]},
                "audio_codec": {"enum": ["aac", "opus"]},
                "width": {"type": "integer", "minimum": 64, "maximum": 1920},
                "height": {"type": "integer", "minimum": 64, "maximum": 1920},
                "fps": {"enum": [1, 5, 10, 15, 24, 25, 30]},
                **_TIMING_PROPERTIES,
            },
            ["input", "output", "container", "video_codec", "audio_codec",
             "width", "height", "fps", "start_seconds", "duration_seconds"],
        ),
        _operation_schema(
            "sample_frames",
            {
                "input": _PATH_SCHEMA,
                "output": _PATH_SCHEMA,
                "frame_count": {"type": "integer", "minimum": 1, "maximum": 16},
                "width": {"type": "integer", "minimum": 64, "maximum": 1920},
                **_TIMING_PROPERTIES,
            },
            ["input", "output", "frame_count", "width", "start_seconds",
             "duration_seconds"],
        ),
    ]
}

TOOL_SCHEMAS: Dict[str, dict] = {
    "inspect_workspace": _EMPTY_SCHEMA,
    "inspect_environment": _EMPTY_SCHEMA,
    "run_python": {
        "type": "object",
        "properties": {
            "source": {"type": "string", "minLength": 1, "maxLength": 131072},
            "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": 1200},
        },
        "required": ["source", "timeout_seconds"],
        "additionalProperties": False,
    },
    "run_ffmpeg": FFMPEG_SCHEMA,
    "inspect_artifacts": _EMPTY_SCHEMA,
    "finalize": {
        "type": "object",
        "properties": {
            "deliverables": {
                "type": "array",
                "minItems": 1,
                "maxItems": 64,
                "uniqueItems": True,
                "items": _PATH_SCHEMA,
            },
            "summary": {"type": "string", "minLength": 1, "maxLength": 2048},
        },
        "required": ["deliverables", "summary"],
        "additionalProperties": False,
    },
}


def responses_tool_definitions() -> list[dict]:
    """Return Responses API function definitions in a stable order."""
    descriptions = {
        "inspect_workspace": "List bounded metadata for inputs and generated workspace files.",
        "inspect_environment": "Return the checked-in runtime capability manifest.",
        "run_python": "Run Python source in the isolated task workspace.",
        "run_ffmpeg": "Run one closed, validated local-media operation.",
        "inspect_artifacts": "Deterministically inspect generated deliverables.",
        "finalize": "Submit verified deliverables and finish the task.",
    }
    return [
        {
            "type": "function",
            "name": name,
            "description": descriptions[name],
            "parameters": TOOL_SCHEMAS[name],
            "strict": True,
        }
        for name in TOOL_NAMES
    ]


class AgenticComputeBackend(Protocol):
    """Uncredentialed compute-plane contract used by the solver loop."""

    def start(self, timeout_seconds: float = 1200.0) -> Mapping[str, Any]: ...
    def inspect_workspace(self, timeout_seconds: float = 1200.0) -> Mapping[str, Any]: ...
    def inspect_environment(self, timeout_seconds: float = 1200.0) -> Mapping[str, Any]: ...
    def reset_work(self, timeout_seconds: float = 1200.0) -> Mapping[str, Any]: ...
    def run_python(self, source: str, timeout_seconds: float) -> Mapping[str, Any]: ...
    def run_ffmpeg(
        self, operation: Mapping[str, Any], timeout_seconds: float
    ) -> Mapping[str, Any]: ...
    def inspect_artifacts(self, timeout_seconds: float = 1200.0) -> Mapping[str, Any]: ...
    def finalize(
        self, deliverables: list[str], summary: str,
        timeout_seconds: float = 1200.0,
    ) -> Mapping[str, Any]: ...
    def best_result(
        self, timeout_seconds: float = 1200.0
    ) -> Mapping[str, Any] | None: ...
    def close(self) -> None: ...


@dataclass(frozen=True)
class ToolDispatch:
    result: dict
    finalized: bool = False
    terminal_result: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class PreparedToolCall:
    name: str
    arguments: dict
    fingerprint: str


@dataclass
class AgenticToolDispatcher:
    """Validate, bound, and sequentially dispatch model tool calls."""

    backend: AgenticComputeBackend
    max_total_calls: int = 8
    per_tool_limits: Mapping[str, int] = field(default_factory=lambda: {
        "inspect_workspace": 4,
        "inspect_environment": 2,
        "run_python": 4,
        "run_ffmpeg": 2,
        "inspect_artifacts": 4,
        "finalize": 2,
    })
    max_result_bytes: int = 32768
    total_calls: int = 0
    calls_by_name: Dict[str, int] = field(default_factory=dict)
    seen_requests: set[str] = field(default_factory=set)
    mutation_epoch: int = 0

    def dispatch(self, name: str, raw_arguments: Any) -> ToolDispatch:
        prepared, error = self.prepare_batch([(name, raw_arguments)])
        if error is not None:
            return ToolDispatch(_error(error, retryable=False))
        return self.dispatch_prepared(prepared[0])

    def prepare_batch(
        self, calls: list[tuple[str, Any]]
    ) -> tuple[list[PreparedToolCall], str | None]:
        """Validate an entire ordered response before reserving tool budgets."""
        if not calls:
            return [], "empty_tool_batch"
        if any(name == "finalize" for name, _ in calls) and len(calls) != 1:
            return [], "invalid_finalize_batch"
        if self.total_calls + len(calls) > self.max_total_calls:
            return [], "tool_budget_exhausted"

        prospective = dict(self.calls_by_name)
        prospective_epoch = self.mutation_epoch
        prepared: list[PreparedToolCall] = []
        batch_fingerprints: set[str] = set()
        for name, raw_arguments in calls:
            if name not in TOOL_SCHEMAS:
                return [], "unknown_tool"
            prospective[name] = prospective.get(name, 0) + 1
            if prospective[name] > self.per_tool_limits.get(name, 0):
                return [], "tool_budget_exhausted"

            try:
                arguments = (
                    json.loads(raw_arguments)
                    if isinstance(raw_arguments, str)
                    else raw_arguments
                )
            except (TypeError, ValueError, json.JSONDecodeError):
                return [], "malformed_arguments"
            if not isinstance(arguments, dict):
                return [], "malformed_arguments"

            errors = sorted(
                Draft202012Validator(TOOL_SCHEMAS[name]).iter_errors(arguments),
                key=lambda error: list(error.path),
            )
            if errors:
                return [], "invalid_arguments"
            if not _within_utf8_limits(name, arguments):
                return [], "argument_byte_limit_exceeded"

            fingerprint = hashlib.sha256(
                json.dumps(
                    [
                        name,
                        arguments,
                        (
                            prospective_epoch
                            if name in {"inspect_workspace", "inspect_artifacts"}
                            else None
                        ),
                    ],
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
            if (
                fingerprint in self.seen_requests
                or fingerprint in batch_fingerprints
            ):
                return [], "duplicate_tool_request"
            batch_fingerprints.add(fingerprint)
            prepared.append(PreparedToolCall(name, dict(arguments), fingerprint))
            if name in {"run_python", "run_ffmpeg"}:
                prospective_epoch += 1

        self.total_calls += len(prepared)
        self.calls_by_name = prospective
        self.seen_requests.update(batch_fingerprints)
        self.mutation_epoch = prospective_epoch
        return prepared, None

    def dispatch_prepared(
        self,
        call: PreparedToolCall,
        *,
        remaining_seconds: float | None = None,
    ) -> ToolDispatch:
        name = call.name
        arguments = call.arguments
        timeout = remaining_seconds if remaining_seconds is not None else 1200.0
        if timeout <= 0:
            return ToolDispatch(
                _error("task_wall_time_exhausted", retryable=False)
            )
        try:
            if name == "inspect_workspace":
                payload = self.backend.inspect_workspace(timeout)
            elif name == "inspect_environment":
                payload = self.backend.inspect_environment(timeout)
            elif name == "run_python":
                timeout = float(arguments["timeout_seconds"])
                if remaining_seconds is not None:
                    timeout = min(timeout, remaining_seconds)
                if timeout <= 0:
                    return ToolDispatch(
                        _error("task_wall_time_exhausted", retryable=False)
                    )
                payload = self.backend.run_python(
                    arguments["source"], timeout
                )
            elif name == "run_ffmpeg":
                timeout = remaining_seconds if remaining_seconds is not None else 660.0
                if timeout <= 0:
                    return ToolDispatch(
                        _error("task_wall_time_exhausted", retryable=False)
                    )
                payload = self.backend.run_ffmpeg(arguments, timeout)
            elif name == "inspect_artifacts":
                payload = self.backend.inspect_artifacts(timeout)
            else:
                payload = self.backend.finalize(
                    arguments["deliverables"], arguments["summary"], timeout
                )
        except Exception:
            return ToolDispatch(_error("compute_backend_error", retryable=False))

        result = _bounded_envelope(payload, self.max_result_bytes)
        finalized = name == "finalize" and result.get("ok") is True
        terminal_result = self.backend.best_result() if finalized else None
        if finalized and terminal_result is None:
            return ToolDispatch(_error("finalize_result_missing", retryable=False))
        return ToolDispatch(result, finalized=finalized, terminal_result=terminal_result)


def _error(error_type: str, *, retryable: bool) -> dict:
    return {"ok": False, "error_type": error_type, "retryable": retryable}


def _within_utf8_limits(name: str, arguments: Mapping[str, Any]) -> bool:
    try:
        encoded = json.dumps(
            dict(arguments),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError):
        return False
    if len(encoded) > 131072:
        return False
    if name == "run_python" and len(arguments["source"].encode("utf-8")) > 131072:
        return False
    if name == "finalize" and len(arguments["summary"].encode("utf-8")) > 2048:
        return False
    path_values = []
    for field_name in ("input", "output"):
        value = arguments.get(field_name)
        if isinstance(value, str):
            path_values.append(value)
    deliverables = arguments.get("deliverables")
    if isinstance(deliverables, list):
        path_values.extend(
            value for value in deliverables if isinstance(value, str)
        )
    return all(len(value.encode("utf-8")) <= 240 for value in path_values)


def _bounded_envelope(payload: Mapping[str, Any], limit: int) -> dict:
    result = dict(payload)
    if result.get("ok") not in (True, False):
        result = _error("invalid_compute_result", retryable=False)
    try:
        encoded = json.dumps(
            result, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError):
        return _error("invalid_compute_result", retryable=False)
    if len(encoded) > limit:
        return _error("tool_result_too_large", retryable=False)
    return result