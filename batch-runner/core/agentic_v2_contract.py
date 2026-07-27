"""Versioned model-visible contract for Agentic Sandbox V2."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Any, Mapping
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator


TOOL_CONTRACT_VERSION = "2.0"
FOUNDATION_BACKEND_ID = "agentic-v2-fixture-v1"
POLICY_PROFILE_IDS = (
    "offline-full-v1",
    "package-broker-v1",
    "web-augmented-v1",
)

TOOL_NAMES = (
    "capabilities_query",
    "workspace_apply",
    "exec_run",
    "environment_resolve",
    "environment_activate",
    "browser_run",
    "verify_public",
    "finalize",
)

_PATH_PATTERN = (
    r"^(?!/)(?!.*(?:^|/)\.\.(?:/|$))"
    r"(?!.*[:\\\x00-\x1f\x7f-\x9f]).+$"
)
_DIGEST_PATTERN = r"^[0-9a-f]{64}$"
_PACKAGE_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}(?:==[A-Za-z0-9][A-Za-z0-9.!+_-]{0,127})?$"

ERROR_TYPES = (
    "artifact_not_openable",
    "call_id_conflict",
    "cancelled",
    "capability_unavailable",
    "compute_backend_error",
    "compute_cleanup_failed",
    "compute_start_failed",
    "finalize_not_called",
    "finalize_result_mismatch",
    "finalize_result_missing",
    "fixture_backend_error",
    "invalid_arguments",
    "invalid_backend_result",
    "invalid_backend_state",
    "invalid_call_id",
    "invalid_lifecycle_transition",
    "invalid_result_envelope",
    "package_not_in_snapshot",
    "path_not_directory",
    "runner_internal_error",
    "substrate_manifest_missing",
    "task_wall_time_exhausted",
    "tool_budget_exhausted",
    "tool_not_allowed_in_state",
    "tool_result_too_large",
    "unapproved_lock",
    "unknown_tool",
)

_PATH_SCHEMA = {
    "type": "string",
    "minLength": 1,
    "maxLength": 240,
    "pattern": _PATH_PATTERN,
}


def _strict_object(
    properties: Mapping[str, Any],
    required: tuple[str, ...] = (),
) -> dict:
    return {
        "type": "object",
        "properties": dict(properties),
        "required": list(required),
        "additionalProperties": False,
    }


TOOL_SCHEMAS: dict[str, dict] = {
    "capabilities_query": _strict_object({
        "kind": {
            "enum": ["commands", "runtimes", "packages", "formats", "budgets"]
        },
        "query": {"type": "string", "maxLength": 256},
        "cursor": {"type": "string", "maxLength": 128},
    }, ("kind",)),
    "workspace_apply": {
        "oneOf": [
            _strict_object({
                "operation": {"const": "list"},
                "path": _PATH_SCHEMA,
            }, ("operation", "path")),
            _strict_object({
                "operation": {"const": "read"},
                "path": _PATH_SCHEMA,
                "offset": {"type": "integer", "minimum": 0},
                "limit": {"type": "integer", "minimum": 1, "maximum": 1048576},
            }, ("operation", "path")),
            _strict_object({
                "operation": {"enum": ["write", "patch"]},
                "path": _PATH_SCHEMA,
                "content": {"type": "string", "maxLength": 1048576},
            }, ("operation", "path", "content")),
            _strict_object({
                "operation": {"enum": ["delete", "mkdir"]},
                "path": _PATH_SCHEMA,
            }, ("operation", "path")),
            _strict_object({
                "operation": {"const": "copy"},
                "source": _PATH_SCHEMA,
                "destination": _PATH_SCHEMA,
            }, ("operation", "source", "destination")),
        ]
    },
    "exec_run": {
        "oneOf": [
            _strict_object({
                "argv": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 128,
                    "items": {"type": "string", "maxLength": 4096},
                },
                "cwd": _PATH_SCHEMA,
                "stdin": {"type": "string", "maxLength": 1048576},
                "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": 2700},
            }, ("argv", "cwd", "timeout_seconds")),
            _strict_object({
                "interpreter": {"enum": ["python", "node", "r", "bash"]},
                "script": {"type": "string", "minLength": 1, "maxLength": 262144},
                "cwd": _PATH_SCHEMA,
                "stdin": {"type": "string", "maxLength": 1048576},
                "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": 2700},
            }, ("interpreter", "script", "cwd", "timeout_seconds")),
        ]
    },
    "environment_resolve": _strict_object({
        "ecosystem": {"enum": ["python", "npm", "debian"]},
        "requirements": {
            "type": "array",
            "minItems": 1,
            "maxItems": 64,
            "uniqueItems": True,
            "items": {
                "type": "string",
                "pattern": _PACKAGE_PATTERN,
                "maxLength": 256,
            },
        },
    }, ("ecosystem", "requirements")),
    "environment_activate": _strict_object({
        "lock_digest": {"type": "string", "pattern": _DIGEST_PATTERN},
    }, ("lock_digest",)),
    "browser_run": {
        "oneOf": [
            _strict_object({
                "operation": {"enum": ["open_local", "snapshot", "screenshot"]},
                "path": _PATH_SCHEMA,
            }, ("operation", "path")),
            _strict_object({
                "operation": {"const": "search"},
                "query": {"type": "string", "minLength": 1, "maxLength": 512},
            }, ("operation", "query")),
            _strict_object({
                "operation": {"const": "open_url"},
                "url": {"type": "string", "format": "uri", "maxLength": 2048},
            }, ("operation", "url")),
        ]
    },
    "verify_public": _strict_object({
        "deliverables": {
            "type": "array",
            "minItems": 1,
            "maxItems": 64,
            "uniqueItems": True,
            "items": _PATH_SCHEMA,
        },
    }, ("deliverables",)),
    "finalize": _strict_object({
        "deliverables": {
            "type": "array",
            "minItems": 1,
            "maxItems": 64,
            "uniqueItems": True,
            "items": _PATH_SCHEMA,
        },
        "summary": {"type": "string", "minLength": 1, "maxLength": 2048},
    }, ("deliverables", "summary")),
}

_ARTIFACT_SCHEMA = _strict_object({
    "path": _PATH_SCHEMA,
    "sha256": {"type": "string", "pattern": _DIGEST_PATTERN},
    "size": {"type": "integer", "minimum": 1, "maximum": 536870912},
}, ("path", "sha256", "size"))

_LOCK_SCHEMA = _strict_object({
    "ecosystem": {"enum": ["python", "npm", "debian"]},
    "requirements": {
        "type": "array",
        "minItems": 1,
        "maxItems": 64,
        "uniqueItems": True,
        "items": {"type": "string", "pattern": _PACKAGE_PATTERN},
    },
    "blobs": {
        "type": "array",
        "minItems": 1,
        "maxItems": 64,
        "items": {"type": "string", "pattern": _DIGEST_PATTERN},
    },
}, ("ecosystem", "requirements", "blobs"))

TOOL_DATA_SCHEMAS: dict[str, dict] = {
    "capabilities_query": _strict_object({
        "kind": {
            "enum": ["commands", "runtimes", "packages", "formats", "budgets"]
        },
        "items": {
            "type": "array",
            "maxItems": 512,
            "items": {"type": "string", "maxLength": 512},
        },
    }, ("kind", "items")),
    "workspace_apply": {
        "oneOf": [
            _strict_object({
                "entries": {
                    "type": "array",
                    "maxItems": 1024,
                    "items": {"type": "string", "maxLength": 240},
                },
            }, ("entries",)),
            _strict_object({
                "content": {"type": "string", "maxLength": 1048576},
                "content_sha256": {"type": "string", "pattern": _DIGEST_PATTERN},
            }, ("content", "content_sha256")),
            _strict_object({"path": _PATH_SCHEMA}, ("path",)),
        ]
    },
    "exec_run": _strict_object({
        "returncode": {"type": "integer", "minimum": 0, "maximum": 255},
    }, ("returncode",)),
    "environment_resolve": _strict_object({
        "lock_digest": {"type": "string", "pattern": _DIGEST_PATTERN},
        "lock": _LOCK_SCHEMA,
    }, ("lock_digest", "lock")),
    "environment_activate": _strict_object({
        "environment_id": {"type": "string", "pattern": _DIGEST_PATTERN},
    }, ("environment_id",)),
    "browser_run": _strict_object({
        "path": _PATH_SCHEMA,
        "sha256": {"type": "string", "pattern": _DIGEST_PATTERN},
    }, ("path", "sha256")),
    "verify_public": _strict_object({
        "artifacts": {
            "type": "array", "minItems": 1, "maxItems": 64,
            "items": _ARTIFACT_SCHEMA,
        },
    }, ("artifacts",)),
    "finalize": _strict_object({
        "artifacts": {
            "type": "array", "minItems": 1, "maxItems": 64,
            "items": _ARTIFACT_SCHEMA,
        },
    }, ("artifacts",)),
}

USAGE_DELTA_SCHEMA = _strict_object({
    "tool_calls": {"type": "integer", "minimum": 0, "maximum": 1},
    "wall_ms": {"type": "integer", "minimum": 0, "maximum": 3600000},
    "output_bytes": {"type": "integer", "minimum": 0, "maximum": 16777216},
}, ("tool_calls", "wall_ms", "output_bytes"))

TOOL_RESULT_SCHEMA = _strict_object({
    "schema_version": {"const": TOOL_CONTRACT_VERSION},
    "call_id": {"type": "string", "minLength": 1, "maxLength": 128},
    "tool_name": {"type": ["string", "null"], "enum": [*TOOL_NAMES, None]},
    "request_sha256": {"type": ["string", "null"], "pattern": _DIGEST_PATTERN},
    "result_sha256": {"type": "string", "pattern": _DIGEST_PATTERN},
    "ok": {"type": "boolean"},
    "error_type": {"type": ["string", "null"], "enum": [*ERROR_TYPES, None]},
    "data": {"type": "object"},
    "usage_delta": USAGE_DELTA_SCHEMA,
    "state_before_sha256": {
        "type": ["string", "null"], "pattern": _DIGEST_PATTERN
    },
    "state_after_sha256": {
        "type": ["string", "null"], "pattern": _DIGEST_PATTERN
    },
}, (
    "schema_version", "call_id", "tool_name", "request_sha256",
    "result_sha256", "ok", "error_type", "data", "usage_delta",
    "state_before_sha256", "state_after_sha256",
))

PUBLIC_RESULT_COMMITMENT_SCHEMA = _strict_object({
    "call_id": {"type": "string", "minLength": 1, "maxLength": 128},
    "tool_name": {"type": ["string", "null"], "enum": [*TOOL_NAMES, None]},
    "request_sha256": {"type": ["string", "null"], "pattern": _DIGEST_PATTERN},
    "result_sha256": {"type": "string", "pattern": _DIGEST_PATTERN},
    "ok": {"type": "boolean"},
    "error_type": {"type": ["string", "null"], "enum": [*ERROR_TYPES, None]},
    "usage_delta": USAGE_DELTA_SCHEMA,
    "state_before_sha256": {
        "type": ["string", "null"], "pattern": _DIGEST_PATTERN
    },
    "state_after_sha256": {
        "type": ["string", "null"], "pattern": _DIGEST_PATTERN
    },
}, (
    "call_id", "tool_name", "request_sha256", "result_sha256", "ok",
    "error_type", "usage_delta", "state_before_sha256", "state_after_sha256",
))

EVENT_SCHEMA = _strict_object({
    "schema_version": {"const": TOOL_CONTRACT_VERSION},
    "sequence": {"type": "integer", "minimum": 0},
    "kind": {"type": "string", "minLength": 1, "maxLength": 128},
    "payload": {"type": "object"},
    "state_sha256": {"type": "string", "pattern": _DIGEST_PATTERN},
    "previous_sha256": {"type": "string", "pattern": _DIGEST_PATTERN},
    "event_sha256": {"type": "string", "pattern": _DIGEST_PATTERN},
}, (
    "schema_version", "sequence", "kind", "payload", "state_sha256",
    "previous_sha256", "event_sha256",
))


class LifecycleState(str, Enum):
    CREATED = "created"
    STARTED = "started"
    ACTIVE = "active"
    FINALIZING = "finalizing"
    FINALIZED = "finalized"
    FAILED = "failed"
    CANCELLED = "cancelled"


_TRANSITIONS = {
    LifecycleState.CREATED: frozenset({LifecycleState.STARTED, LifecycleState.CANCELLED}),
    LifecycleState.STARTED: frozenset({LifecycleState.ACTIVE, LifecycleState.FAILED, LifecycleState.CANCELLED}),
    LifecycleState.ACTIVE: frozenset({LifecycleState.FINALIZING, LifecycleState.FAILED, LifecycleState.CANCELLED}),
    LifecycleState.FINALIZING: frozenset({LifecycleState.ACTIVE, LifecycleState.FINALIZED, LifecycleState.FAILED, LifecycleState.CANCELLED}),
    LifecycleState.FINALIZED: frozenset(),
    LifecycleState.FAILED: frozenset(),
    LifecycleState.CANCELLED: frozenset(),
}

_MUTATING_TOOLS = frozenset({
    "workspace_apply",
    "exec_run",
    "environment_activate",
    "browser_run",
})


@dataclass(frozen=True)
class AgenticV2Profile:
    tool_contract_version: str
    policy_profile_id: str
    foundation_only: bool

    @classmethod
    def from_mapping(cls, value: Any) -> "AgenticV2Profile":
        if not isinstance(value, Mapping):
            raise ValueError("execution.agentic_v2 must be an object")
        expected = {
            "tool_contract_version", "policy_profile_id", "foundation_only"
        }
        unknown = set(value) - expected
        if unknown:
            raise ValueError(f"unknown agentic v2 setting(s): {sorted(unknown)}")
        version = value.get("tool_contract_version")
        profile = value.get("policy_profile_id")
        foundation_only = value.get("foundation_only")
        if version != TOOL_CONTRACT_VERSION:
            raise ValueError("agentic v2 tool_contract_version must be '2.0'")
        if profile not in POLICY_PROFILE_IDS:
            raise ValueError("agentic v2 policy_profile_id is invalid")
        if foundation_only is not True:
            raise ValueError("agentic v2 foundation_only must be true")
        return cls(version, str(profile), True)


@dataclass
class AgenticV2Lifecycle:
    state: LifecycleState = LifecycleState.CREATED

    @property
    def terminal(self) -> bool:
        return not _TRANSITIONS[self.state]

    def transition(self, target: LifecycleState | str) -> LifecycleState:
        try:
            next_state = LifecycleState(target)
        except ValueError as exc:
            raise ValueError("unknown agentic v2 lifecycle state") from exc
        if next_state not in _TRANSITIONS[self.state]:
            raise ValueError(
                f"invalid agentic v2 transition: {self.state.value}->{next_state.value}"
            )
        self.state = next_state
        return self.state

    def require_tool_allowed(self, name: str) -> None:
        if name not in TOOL_SCHEMAS:
            raise ValueError("unknown agentic v2 tool")
        if self.terminal:
            raise ValueError("agentic v2 lifecycle is terminal")
        if self.state not in {LifecycleState.ACTIVE, LifecycleState.FINALIZING}:
            raise ValueError("agentic v2 tool call is not active")
        if self.state is LifecycleState.FINALIZING and name in _MUTATING_TOOLS:
            raise ValueError("agentic v2 mutation is forbidden while finalizing")


def responses_tool_definitions() -> list[dict]:
    descriptions = {
        "capabilities_query": "Discover actual task-environment capabilities and remaining budgets.",
        "workspace_apply": "Perform one bounded operation in the task-local workspace.",
        "exec_run": "Run one bounded argv command or interpreter script in the task workspace.",
        "environment_resolve": "Resolve package coordinates without mutating the task environment.",
        "environment_activate": "Atomically activate an approved content-addressed package lock.",
        "browser_run": "Inspect a local page or use a policy-gated web capability.",
        "verify_public": "Run public structural and openability checks on deliverables.",
        "finalize": "Commit declared deliverables and finish the task.",
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


def validate_tool_arguments(name: str, arguments: Any) -> dict:
    if name not in TOOL_SCHEMAS:
        raise ValueError("unknown agentic v2 tool")
    if not isinstance(arguments, dict):
        raise ValueError("agentic v2 tool arguments must be an object")
    errors = sorted(
        Draft202012Validator(TOOL_SCHEMAS[name]).iter_errors(arguments),
        key=lambda error: list(error.path),
    )
    if errors:
        raise ValueError("invalid agentic v2 tool arguments")
    result = dict(arguments)
    for field_name in ("path", "source", "destination", "cwd"):
        value = result.get(field_name)
        if isinstance(value, str):
            canonical_relative_path(value)
    deliverables = result.get("deliverables")
    if isinstance(deliverables, list):
        canonical = [canonical_relative_path(value) for value in deliverables]
        if len(canonical) != len(set(canonical)):
            raise ValueError("agentic v2 deliverable paths must be unique")
    if name == "browser_run" and result.get("operation") == "open_url":
        validate_public_https_url(result.get("url"))
    return result


def validate_tool_result_data(
    name: str,
    arguments: Mapping[str, Any],
    ok: bool,
    data: Any,
) -> dict:
    if not isinstance(data, dict):
        raise ValueError("agentic v2 tool result data must be an object")
    if not ok:
        if data:
            raise ValueError("agentic v2 failed result data must be empty")
        return {}
    schema = TOOL_DATA_SCHEMAS.get(name)
    if schema is None or list(Draft202012Validator(schema).iter_errors(data)):
        raise ValueError("agentic v2 tool result data is invalid")
    result = dict(data)
    if name == "capabilities_query" and result["kind"] != arguments["kind"]:
        raise ValueError("agentic v2 capability result kind mismatch")
    if name == "workspace_apply":
        operation = arguments["operation"]
        expected_shape = (
            "entries" if operation == "list"
            else "content" if operation == "read"
            else "path"
        )
        if expected_shape not in result:
            raise ValueError("agentic v2 workspace result operation mismatch")
        if expected_shape == "path":
            expected_path = (
                arguments["destination"]
                if operation == "copy"
                else arguments["path"]
            )
            if result["path"] != expected_path:
                raise ValueError("agentic v2 workspace result path mismatch")
        if expected_shape == "content" and result["content_sha256"] != (
            hashlib.sha256(result["content"].encode("utf-8")).hexdigest()
        ):
            raise ValueError("agentic v2 workspace content hash mismatch")
    if name == "environment_resolve":
        lock = result["lock"]
        if (
            lock["ecosystem"] != arguments["ecosystem"]
            or lock["requirements"] != sorted(arguments["requirements"])
            or result["lock_digest"] != hashlib.sha256(
                json.dumps(
                    lock, sort_keys=True, separators=(",", ":")
                ).encode("utf-8")
            ).hexdigest()
        ):
            raise ValueError("agentic v2 package lock result mismatch")
    if name == "environment_activate" and (
        result["environment_id"] != arguments["lock_digest"]
    ):
        raise ValueError("agentic v2 environment activation result mismatch")
    if name == "browser_run":
        canonical_relative_path(result["path"])
    if name == "browser_run" and arguments["operation"] in {
        "open_local", "snapshot", "screenshot"
    } and result["path"] != arguments["path"]:
        raise ValueError("agentic v2 browser result path mismatch")
    for artifact in result.get("artifacts", []):
        canonical_relative_path(artifact["path"])
    if name in {"verify_public", "finalize"} and [
        artifact["path"] for artifact in result["artifacts"]
    ] != arguments["deliverables"]:
        raise ValueError("agentic v2 artifact result scope mismatch")
    return result


def canonical_relative_path(value: Any) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value.encode("utf-8")) > 240
        or "\\" in value
        or ":" in value
        or any(
            ord(character) < 32 or 127 <= ord(character) <= 159
            for character in value
        )
    ):
        raise ValueError("agentic v2 path must be canonical relative POSIX")
    if value == ".":
        return value
    if any(
        part in {"", ".", ".."} or len(part.encode("utf-8")) > 255
        for part in value.split("/")
    ):
        raise ValueError("agentic v2 path must be canonical relative POSIX")
    path = PurePosixPath(value)
    if path.is_absolute() or path.as_posix() != value:
        raise ValueError("agentic v2 path must be canonical relative POSIX")
    return value


def validate_public_https_url(value: Any) -> str:
    if (
        not isinstance(value, str)
        or len(value) > 2048
        or any(character.isspace() or ord(character) < 32 or 127 <= ord(character) <= 159
               for character in value)
        or "\\" in value
        or "%" in value
    ):
        raise ValueError("agentic v2 URL is invalid")
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise ValueError("agentic v2 URL is invalid") from exc
    if (
        parsed.scheme != "https"
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
        or parsed.netloc.endswith(":")
        or hostname.endswith(".")
        or (port is not None and port < 1)
    ):
        raise ValueError("agentic v2 URL must be public HTTPS")
    hostname = hostname.lower()
    if hostname == "localhost" or hostname.endswith(".local"):
        raise ValueError("agentic v2 URL must be public HTTPS")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise ValueError("agentic v2 URL must be public HTTPS")
    if address is None and (
        len(hostname) > 253
        or re.fullmatch(
            r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
            r"(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*",
            hostname,
        ) is None
        or hostname.replace(".", "").isdigit()
        or any(
            re.fullmatch(r"0x[0-9a-f]+", label) is not None
            for label in hostname.split(".")
        )
    ):
        raise ValueError("agentic v2 URL must be public HTTPS")
    if any(segment in {".", ".."} for segment in parsed.path.split("/")):
        raise ValueError("agentic v2 URL must be canonical public HTTPS")
    return value


def contract_fingerprint() -> str:
    payload = {
        "tool_contract_version": TOOL_CONTRACT_VERSION,
        "profiles": list(POLICY_PROFILE_IDS),
        "error_types": list(ERROR_TYPES),
        "tools": responses_tool_definitions(),
        "tool_data_schemas": TOOL_DATA_SCHEMAS,
        "tool_result_schema": TOOL_RESULT_SCHEMA,
        "public_result_commitment_schema": PUBLIC_RESULT_COMMITMENT_SCHEMA,
        "event_schema": EVENT_SCHEMA,
        "lifecycle": {
            state.value: sorted(target.value for target in targets)
            for state, targets in _TRANSITIONS.items()
        },
        "semantic_validator_source_sha256": hashlib.sha256(
            Path(__file__).read_bytes()
        ).hexdigest(),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def is_sha256(value: str) -> bool:
    return bool(re.fullmatch(_DIGEST_PATTERN, value))