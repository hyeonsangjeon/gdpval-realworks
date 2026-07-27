"""Strict dispatcher for the Agentic Sandbox V2 tool contract."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Protocol

from core.agentic_v2_contract import (
    ERROR_TYPES,
    TOOL_CONTRACT_VERSION,
    TOOL_SCHEMAS,
    TOOL_RESULT_SCHEMA,
    AgenticV2Lifecycle,
    LifecycleState,
    is_sha256,
    validate_tool_arguments,
    validate_tool_result_data,
)
from jsonschema import Draft202012Validator
from core.agentic_v2_provenance import canonical_sha256


class AgenticV2Backend(Protocol):
    def start(self, timeout_seconds: float) -> Mapping[str, Any]: ...
    def expected_capabilities(self) -> Mapping[str, Any]: ...
    def state_sha256(self) -> str: ...
    def capabilities_query(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]: ...
    def workspace_apply(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]: ...
    def exec_run(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]: ...
    def environment_resolve(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]: ...
    def environment_activate(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]: ...
    def browser_run(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]: ...
    def verify_public(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]: ...
    def finalize(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]: ...
    def best_result(self) -> Mapping[str, Any] | None: ...
    def close(self) -> None: ...


@dataclass(frozen=True)
class AgenticV2Dispatch:
    result: dict
    finalized: bool = False
    terminal_result: Mapping[str, Any] | None = None
    replayed: bool = False


@dataclass
class AgenticV2ToolDispatcher:
    backend: AgenticV2Backend
    lifecycle: AgenticV2Lifecycle
    max_total_calls: int = 32
    max_result_bytes: int = 65536
    deadline: float | None = None
    clock: Callable[[], float] = time.monotonic
    record_wall_time: bool = True
    total_calls: int = 0
    _call_fingerprints: dict[str, str] = field(default_factory=dict)
    _cached_results: dict[str, AgenticV2Dispatch] = field(default_factory=dict)

    def dispatch(
        self,
        *,
        call_id: str,
        name: str,
        arguments: Any,
    ) -> AgenticV2Dispatch:
        if not isinstance(call_id, str) or re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", call_id
        ) is None:
            return AgenticV2Dispatch(
                _error("invalid_call_id", call_id="invalid", tool_name=None)
            )
        prior = self._call_fingerprints.get(call_id)
        try:
            validated = validate_tool_arguments(name, arguments)
        except ValueError as exc:
            if prior is not None:
                return AgenticV2Dispatch(
                    _error("call_id_conflict", call_id=call_id, tool_name=name)
                )
            return AgenticV2Dispatch(
                _error(_public_error_type(exc), call_id=call_id, tool_name=name)
            )

        request_sha256 = canonical_sha256({
            "tool_contract_version": TOOL_CONTRACT_VERSION,
            "call_id": call_id,
            "name": name,
            "arguments": validated,
        })
        if prior is not None:
            if prior != request_sha256:
                return AgenticV2Dispatch(
                    _error("call_id_conflict", call_id=call_id, tool_name=name)
                )
            cached = self._cached_results[call_id]
            if not _valid_cached_dispatch(
                cached,
                call_id=call_id,
                name=name,
                request_sha256=request_sha256,
            ):
                return AgenticV2Dispatch(
                    _error(
                        "invalid_result_envelope",
                        call_id=call_id,
                        tool_name=name,
                    )
                )
            cached_state_after = cached.result.get("state_after_sha256")
            if cached_state_after is not None:
                try:
                    current_state = self.backend.state_sha256()
                except Exception:
                    current_state = None
                if current_state != cached_state_after:
                    return AgenticV2Dispatch(
                        _error(
                            "call_id_conflict",
                            call_id=call_id,
                            tool_name=name,
                        )
                    )
            return AgenticV2Dispatch(
                deepcopy(cached.result),
                finalized=cached.finalized,
                terminal_result=deepcopy(cached.terminal_result),
                replayed=True,
            )
        try:
            self.lifecycle.require_tool_allowed(name)
        except ValueError as exc:
            return AgenticV2Dispatch(
                _error(_public_error_type(exc), call_id=call_id, tool_name=name)
            )
        if self.total_calls >= self.max_total_calls:
            return AgenticV2Dispatch(
                _error("tool_budget_exhausted", call_id=call_id, tool_name=name)
            )
        dispatch_started = self.clock()
        if self.deadline is not None and dispatch_started >= self.deadline:
            return AgenticV2Dispatch(
                _error(
                    "task_wall_time_exhausted",
                    call_id=call_id,
                    tool_name=name,
                )
            )

        try:
            state_before = self.backend.state_sha256()
        except Exception:
            state_before = ""
        if not is_sha256(state_before):
            return AgenticV2Dispatch(
                _error("invalid_backend_state", call_id=call_id, tool_name=name)
            )

        finalizing = name == "finalize"
        if finalizing:
            try:
                self.lifecycle.transition(LifecycleState.FINALIZING)
            except ValueError:
                return AgenticV2Dispatch(_error(
                    "invalid_lifecycle_transition", call_id=call_id,
                    tool_name=name,
                ))

        self.total_calls += 1
        self._call_fingerprints[call_id] = request_sha256
        try:
            payload = self._invoke(name, validated)
        except Exception:
            payload = {"ok": False, "error_type": "fixture_backend_error"}

        if not isinstance(payload, Mapping) or payload.get("ok") not in (True, False):
            payload = {"ok": False, "error_type": "invalid_backend_result"}
        backend_claimed_success = payload.get("ok") is True
        try:
            state_after = self.backend.state_sha256()
        except Exception:
            state_after = ""
        dispatch_finished = self.clock()
        wall_ms = (
            min(
                3600000,
                max(0, int((dispatch_finished - dispatch_started) * 1000)),
            )
            if self.record_wall_time
            else 0
        )
        if not is_sha256(state_after):
            payload = {"ok": False, "error_type": "invalid_backend_state"}
            state_after = state_before
        if (
            self.record_wall_time
            and self.deadline is not None
            and dispatch_finished >= self.deadline
        ):
            payload = {"ok": False, "error_type": "task_wall_time_exhausted"}

        terminal_result = None
        terminal_valid = not finalizing
        if finalizing and backend_claimed_success:
            try:
                terminal_result = self.backend.best_result()
            except Exception:
                terminal_result = None

        result = _result_envelope(
            name=name,
            arguments=validated,
            call_id=call_id,
            request_sha256=request_sha256,
            payload=payload,
            state_before=state_before,
            state_after=state_after,
            wall_ms=wall_ms,
        )
        if finalizing and backend_claimed_success:
            terminal_valid = result.get("ok") is True and _valid_terminal_result(
                terminal_result,
                result.get("data", {}).get("artifacts"),
                summary=str(validated["summary"]),
            )
            if result.get("ok") is True and not terminal_valid:
                result = _executed_error(result, "finalize_result_mismatch")
        encoded = json.dumps(
            result, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
        if len(encoded) > self.max_result_bytes:
            result = _executed_error(result, "tool_result_too_large")
        elif list(Draft202012Validator(TOOL_RESULT_SCHEMA).iter_errors(result)):
            result = _executed_error(result, "invalid_result_envelope")

        finalized = (
            finalizing
            and backend_claimed_success
            and terminal_valid
            and result.get("ok") is True
        )
        if finalizing:
            transition_target = (
                LifecycleState.FINALIZED
                if finalized
                else LifecycleState.FAILED
                if backend_claimed_success
                else LifecycleState.ACTIVE
            )
            try:
                self.lifecycle.transition(transition_target)
            except ValueError:
                result = _error(
                    "invalid_lifecycle_transition",
                    call_id=call_id,
                    tool_name=name,
                )
                finalized = False
                terminal_result = None
        if not finalized:
            terminal_result = None
        dispatch = AgenticV2Dispatch(
            deepcopy(result),
            finalized=finalized,
            terminal_result=deepcopy(terminal_result),
        )
        self._cached_results[call_id] = AgenticV2Dispatch(
            deepcopy(result),
            finalized=finalized,
            terminal_result=deepcopy(terminal_result),
        )
        return dispatch

    def _invoke(self, name: str, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        method = getattr(self.backend, name)
        return method(arguments)


def _result_envelope(
    *,
    name: str,
    arguments: Mapping[str, Any],
    call_id: str,
    request_sha256: str,
    payload: Mapping[str, Any],
    state_before: str,
    state_after: str,
    wall_ms: int,
) -> dict:
    ok = payload.get("ok") is True
    error_type = None if ok else str(
        payload.get("error_type") or "invalid_backend_result"
    )
    if error_type is not None and error_type not in ERROR_TYPES:
        error_type = "invalid_backend_result"
        ok = False
    try:
        data = validate_tool_result_data(
            name, arguments, ok, payload.get("data", {})
        )
    except ValueError:
        ok = False
        error_type = "invalid_backend_result"
        data = {}
    usage_delta = {
        "tool_calls": 1,
        "wall_ms": wall_ms,
        "output_bytes": len(json.dumps(
            data, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")),
    }
    result = {
        "schema_version": TOOL_CONTRACT_VERSION,
        "call_id": call_id,
        "tool_name": name,
        "request_sha256": request_sha256,
        "ok": ok,
        "error_type": error_type,
        "data": data,
        "usage_delta": usage_delta,
        "state_before_sha256": state_before,
        "state_after_sha256": state_after,
    }
    result["result_sha256"] = canonical_sha256(result)
    return result


def _executed_error(result: Mapping[str, Any], error_type: str) -> dict:
    value = deepcopy(dict(result))
    value.pop("result_sha256", None)
    value["ok"] = False
    value["error_type"] = error_type
    value["data"] = {}
    value["usage_delta"] = {
        **value["usage_delta"],
        "output_bytes": 2,
    }
    value["result_sha256"] = canonical_sha256(value)
    return value


def _error(
    error_type: str,
    *,
    call_id: str,
    tool_name: str | None,
) -> dict:
    result = {
        "schema_version": TOOL_CONTRACT_VERSION,
        "call_id": call_id,
        "tool_name": tool_name if tool_name in TOOL_SCHEMAS else None,
        "request_sha256": None,
        "ok": False,
        "error_type": error_type,
        "data": {},
        "usage_delta": {"tool_calls": 0, "wall_ms": 0, "output_bytes": 0},
        "state_before_sha256": None,
        "state_after_sha256": None,
    }
    result["result_sha256"] = canonical_sha256(result)
    return result


def _valid_terminal_result(
    value: Any,
    artifacts: Any,
    *,
    summary: str,
) -> bool:
    if (
        not isinstance(value, Mapping)
        or value.get("success") is not True
        or value.get("text") != summary
        or value.get("deliverable_text") != summary
        or not isinstance(value.get("files"), list)
        or not isinstance(artifacts, list)
        or len(value["files"]) != len(artifacts)
    ):
        return False
    for file_value, artifact in zip(value["files"], artifacts):
        if not isinstance(file_value, Mapping) or not isinstance(artifact, Mapping):
            return False
        content = file_value.get("content")
        if (
            file_value.get("filename") != artifact.get("path")
            or not isinstance(content, bytes)
            or len(content) != artifact.get("size")
            or hashlib.sha256(content).hexdigest() != artifact.get("sha256")
        ):
            return False
    return True


def _valid_cached_dispatch(
    dispatch: AgenticV2Dispatch,
    *,
    call_id: str,
    name: str,
    request_sha256: str,
) -> bool:
    result = dispatch.result
    if (
        not isinstance(result, dict)
        or list(Draft202012Validator(TOOL_RESULT_SCHEMA).iter_errors(result))
        or result.get("call_id") != call_id
        or result.get("tool_name") != name
        or result.get("request_sha256") != request_sha256
    ):
        return False
    unsigned = dict(result)
    claimed = unsigned.pop("result_sha256", None)
    return is_sha256(claimed) and canonical_sha256(unsigned) == claimed


def _public_error_type(exc: ValueError) -> str:
    message = str(exc)
    if "unknown agentic v2 tool" in message:
        return "unknown_tool"
    if "terminal" in message or "not active" in message or "finalizing" in message:
        return "tool_not_allowed_in_state"
    return "invalid_arguments"