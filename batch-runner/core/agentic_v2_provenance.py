"""Deterministic provenance primitives for Agentic Sandbox V2."""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator

from core.agentic_v2_contract import (
    ERROR_TYPES,
    EVENT_SCHEMA,
    FOUNDATION_BACKEND_ID,
    POLICY_PROFILE_IDS,
    PUBLIC_RESULT_COMMITMENT_SCHEMA,
    TOOL_CONTRACT_VERSION,
    TOOL_RESULT_SCHEMA,
    TOOL_SCHEMAS,
    canonical_relative_path,
    contract_fingerprint,
    is_sha256,
    validate_tool_arguments,
    validate_tool_result_data,
)


_FOUNDATION_MODULES = (
    "agentic_v2_contract.py",
    "agentic_v2_fixture_backend.py",
    "agentic_v2_provenance.py",
    "agentic_v2_runner.py",
    "agentic_v2_tools.py",
)
_EVENT_KINDS = frozenset({
    "started", "tool_result", "tool_result_public", "failure"
})
_PUBLIC_COMMITMENT_FIELDS = (
    "call_id",
    "tool_name",
    "request_sha256",
    "result_sha256",
    "ok",
    "error_type",
    "usage_delta",
    "state_before_sha256",
    "state_after_sha256",
)
_FAILURE_STAGE_ERRORS = {
    "backend": frozenset({"compute_backend_error"}),
    "startup": frozenset({
        "compute_start_failed",
        "substrate_manifest_missing",
    }),
    "control": frozenset({
        "cancelled",
        "task_wall_time_exhausted",
    }),
    "cleanup": frozenset({"compute_cleanup_failed"}),
    "runtime": frozenset({
        "artifact_not_openable",
        "call_id_conflict",
        "capability_unavailable",
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
        "tool_budget_exhausted",
        "tool_not_allowed_in_state",
        "tool_result_too_large",
        "unapproved_lock",
        "unknown_tool",
    }),
}
_FOUNDATION_PACKAGE_RECORDS = (
    ("python:demo-pkg==1.0.0", "d" * 64),
)


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def validate_failure_stage(error_type: Any, stage: Any) -> tuple[str, str]:
    if (
        not isinstance(error_type, str)
        or not isinstance(stage, str)
        or stage not in _FAILURE_STAGE_ERRORS
        or error_type not in _FAILURE_STAGE_ERRORS[stage]
    ):
        raise ValueError("agentic v2 failure stage is invalid")
    return error_type, stage


def foundation_implementation_fingerprint() -> str:
    root = Path(__file__).resolve().parent
    return canonical_sha256({
        "schema_version": "2.0",
        "modules": {
            name: hashlib.sha256((root / name).read_bytes()).hexdigest()
            for name in _FOUNDATION_MODULES
        },
    })


def foundation_fixture_identity(
    policy_profile_id: str,
    budget_caps: Mapping[str, Any],
) -> dict:
    if policy_profile_id not in POLICY_PROFILE_IDS:
        raise ValueError("agentic v2 fixture profile is invalid")
    if not _valid_budget_capabilities(
        [
            f"tool_calls={budget_caps.get('tool_calls')}",
            f"wall_seconds={budget_caps.get('wall_seconds')}",
        ],
        budget_caps,
    ):
        raise ValueError("agentic v2 fixture budget is invalid")
    packages = (
        []
        if policy_profile_id == "offline-full-v1"
        else [coordinate for coordinate, _ in _FOUNDATION_PACKAGE_RECORDS]
    )
    capabilities = {
        "commands": ["fixture-upper"],
        "runtimes": ["fixture"],
        "packages": packages,
        "formats": ["html", "txt"],
        "budgets": [
            f"tool_calls={budget_caps['tool_calls']}",
            f"wall_seconds={budget_caps['wall_seconds']}",
        ],
    }
    return {
        "backend_identity": {
            "backend_id": FOUNDATION_BACKEND_ID,
            "foundation_only": True,
            "implementation_sha256": foundation_implementation_fingerprint(),
        },
        "substrate_manifest_sha256": canonical_sha256({
            "backend": FOUNDATION_BACKEND_ID,
            "profile": policy_profile_id,
        }),
        "package_snapshot_sha256": canonical_sha256(
            _FOUNDATION_PACKAGE_RECORDS
        ),
        "browser_build_sha256": canonical_sha256({
            "browser": "fixture-local-only-v1"
        }),
        "capabilities": capabilities,
        "package_records": _FOUNDATION_PACKAGE_RECORDS,
    }


def runtime_fingerprint(
    *,
    policy_profile_id: str,
    substrate_manifest_sha256: str,
    package_snapshot_sha256: str,
    browser_build_sha256: str,
    backend_implementation_sha256: str,
    capabilities_sha256: str,
    budget_caps: Mapping[str, Any],
) -> str:
    digests = (
        substrate_manifest_sha256,
        package_snapshot_sha256,
        browser_build_sha256,
        backend_implementation_sha256,
        capabilities_sha256,
    )
    if any(not is_sha256(value) for value in digests):
        raise ValueError("agentic v2 runtime component digest is invalid")
    return canonical_sha256({
        "schema_version": "2.0",
        "tool_contract_sha256": contract_fingerprint(),
        "policy_profile_id": policy_profile_id,
        "substrate_manifest_sha256": substrate_manifest_sha256,
        "package_snapshot_sha256": package_snapshot_sha256,
        "browser_build_sha256": browser_build_sha256,
        "backend_implementation_sha256": backend_implementation_sha256,
        "capabilities_sha256": capabilities_sha256,
        "budget_caps": dict(budget_caps),
    })


@dataclass
class AgenticV2EventChain:
    """Append-only hash chain used by private and public execution traces."""

    events: list[dict] = field(default_factory=list)
    _head: str = "0" * 64

    @property
    def head_sha256(self) -> str:
        return self._head

    def append(
        self,
        kind: str,
        payload: Mapping[str, Any],
        *,
        state_sha256: str,
    ) -> dict:
        if kind not in _EVENT_KINDS:
            raise ValueError("agentic v2 event kind is invalid")
        if not is_sha256(state_sha256):
            raise ValueError("agentic v2 event state digest is invalid")
        event = {
            "schema_version": "2.0",
            "sequence": len(self.events),
            "kind": kind,
            "payload": deepcopy(dict(payload)),
            "state_sha256": state_sha256,
            "previous_sha256": self._head,
        }
        event["event_sha256"] = canonical_sha256(event)
        self.events.append(event)
        self._head = event["event_sha256"]
        return deepcopy(event)


def verify_event_chain(events: Any, expected_head_sha256: str) -> None:
    if not isinstance(events, list) or not events:
        raise ValueError("agentic v2 event chain is missing")
    previous = "0" * 64
    previous_state = None
    tool_event_kind = None
    call_ledger: dict[str, dict] = {}
    semantic_ledger: dict[str, Any] = {}
    started_payload = None
    last_tool_result = None
    last_tool_name = None
    started_seen = False
    for sequence, event in enumerate(events):
        if not isinstance(event, dict):
            raise ValueError("agentic v2 event is invalid")
        if list(Draft202012Validator(EVENT_SCHEMA).iter_errors(event)):
            raise ValueError("agentic v2 event schema is invalid")
        if event.get("sequence") != sequence or event.get("previous_sha256") != previous:
            raise ValueError("agentic v2 event chain ordering is invalid")
        claimed = event.get("event_sha256")
        if not is_sha256(claimed):
            raise ValueError("agentic v2 event hash is invalid")
        unsigned = dict(event)
        del unsigned["event_sha256"]
        if canonical_sha256(unsigned) != claimed:
            raise ValueError("agentic v2 event hash mismatch")
        payload = event.get("payload")
        kind = event.get("kind")
        if sequence == 0 and kind == "started":
            if not _valid_started_payload(payload):
                raise ValueError("agentic v2 started event is invalid")
            started_payload = payload
            started_seen = True
            semantic_ledger = _new_fixture_semantic_ledger(payload)
            if event.get("state_sha256") != _fixture_state_sha256(
                semantic_ledger
            ):
                raise ValueError("agentic v2 initial fixture state mismatch")
        elif kind == "started" or kind not in _EVENT_KINDS:
            raise ValueError("agentic v2 event kind is invalid")
        elif kind == "failure":
            if sequence != len(events) - 1 or not _valid_failure_payload(payload):
                raise ValueError("agentic v2 failure event is invalid")
            expected_state = canonical_sha256({
                "schema_version": "2.0",
                "error_type": payload["error_type"],
                "lifecycle_state": payload["lifecycle_state"],
                "stage": payload["stage"],
            })
            if event.get("state_sha256") != expected_state:
                raise ValueError("agentic v2 failure state mismatch")
            _verify_failure_causality(
                payload,
                started_seen=started_seen,
                last_tool_name=last_tool_name,
                last_tool_result=last_tool_result,
            )
        elif tool_event_kind is None:
            tool_event_kind = kind
        elif kind != tool_event_kind:
            raise ValueError("agentic v2 event trace classification is mixed")
        if kind in {"tool_result", "tool_result_public"} and isinstance(
            last_tool_result, Mapping
        ) and (
            last_tool_result.get("ok") is False
            or (
                last_tool_name == "finalize"
                and last_tool_result.get("ok") is True
            )
        ):
            raise ValueError("agentic v2 tool event follows terminal result")
        if kind == "tool_result":
            if not isinstance(payload, dict) or set(payload) != {
                "request", "result", "replayed"
            } or not isinstance(payload.get("replayed"), bool):
                raise ValueError("agentic v2 private result payload is invalid")
            result = payload.get("result") if isinstance(payload, dict) else None
            if (
                not isinstance(result, dict)
                or list(Draft202012Validator(TOOL_RESULT_SCHEMA).iter_errors(result))
            ):
                raise ValueError("agentic v2 tool result commitment is invalid")
            claimed_result = result.get("result_sha256")
            unsigned_result = dict(result)
            del unsigned_result["result_sha256"]
            if canonical_sha256(unsigned_result) != claimed_result:
                raise ValueError("agentic v2 tool result hash mismatch")
            request = payload.get("request")
            _verify_private_result_semantics(
                request,
                result,
                replayed=payload["replayed"],
                previous_state=previous_state,
                event_state=event.get("state_sha256"),
                call_ledger=call_ledger,
                semantic_ledger=semantic_ledger,
                started_payload=started_payload,
            )
            last_tool_result = result
            last_tool_name = request.get("name") if isinstance(request, dict) else None
            if result.get("request_sha256") is not None:
                if not isinstance(request, dict) or set(request) != {
                    "call_id", "name", "arguments"
                }:
                    raise ValueError("agentic v2 tool request commitment is invalid")
                try:
                    arguments = validate_tool_arguments(
                        request.get("name"), request.get("arguments")
                    )
                except ValueError as exc:
                    raise ValueError(
                        "agentic v2 tool request commitment is invalid"
                    ) from exc
                request_sha256 = canonical_sha256({
                    "tool_contract_version": "2.0",
                    "call_id": request.get("call_id"),
                    "name": request.get("name"),
                    "arguments": arguments,
                })
                if request_sha256 != result.get("request_sha256"):
                    raise ValueError("agentic v2 tool request hash mismatch")
        if kind == "tool_result_public":
            if not isinstance(payload, dict) or set(payload) != {
                "result_commitment", "replayed"
            } or not isinstance(payload.get("replayed"), bool):
                raise ValueError("agentic v2 public result payload is invalid")
            commitment = payload.get("result_commitment") if isinstance(
                payload, dict
            ) else None
            if (
                not isinstance(commitment, dict)
                or list(Draft202012Validator(
                    PUBLIC_RESULT_COMMITMENT_SCHEMA
                ).iter_errors(commitment))
            ):
                raise ValueError("agentic v2 public result commitment is invalid")
            last_tool_result = commitment
            last_tool_name = commitment.get("tool_name")
        previous = claimed
        previous_state = event.get("state_sha256")
    if previous != expected_head_sha256:
        raise ValueError("agentic v2 event chain head mismatch")
    terminal_kind = events[-1].get("kind")
    if terminal_kind != "failure" and not (
        last_tool_name == "finalize"
        and isinstance(last_tool_result, Mapping)
        and last_tool_result.get("ok") is True
    ):
        raise ValueError("agentic v2 trace terminal state is invalid")


def verify_trace_pair(
    private_trace: Any,
    public_trace: Any,
    expected_pair_sha256: str,
) -> None:
    if (
        not isinstance(private_trace, dict)
        or set(private_trace) != {
            "classification", "event_chain_head_sha256", "events"
        }
        or private_trace.get("classification") != "private"
        or not isinstance(public_trace, dict)
        or set(public_trace) != {
            "classification", "event_chain_head_sha256", "events"
        }
        or public_trace.get("classification") != "public_redacted"
    ):
        raise ValueError("agentic v2 trace pair classification is invalid")
    verify_event_chain(
        private_trace["events"], private_trace["event_chain_head_sha256"]
    )
    verify_event_chain(
        public_trace["events"], public_trace["event_chain_head_sha256"]
    )
    private_events = private_trace["events"]
    public_events = public_trace["events"]
    if len(private_events) != len(public_events):
        raise ValueError("agentic v2 trace pair length mismatch")
    for sequence, (private_event, public_event) in enumerate(zip(
        private_events, public_events
    )):
        if (
            private_event.get("sequence") != sequence
            or public_event.get("sequence") != sequence
            or private_event.get("state_sha256") != public_event.get(
                "state_sha256"
            )
        ):
            raise ValueError("agentic v2 trace pair ordering mismatch")
        if sequence == 0:
            if (
                private_event.get("kind") != public_event.get("kind")
                or private_event.get("payload") != public_event.get("payload")
            ):
                raise ValueError("agentic v2 trace pair startup mismatch")
            continue
        if private_event.get("kind") == "failure":
            if (
                public_event.get("kind") != "failure"
                or private_event.get("payload") != public_event.get("payload")
            ):
                raise ValueError("agentic v2 trace pair failure mismatch")
            continue
        if (
            private_event.get("kind") != "tool_result"
            or public_event.get("kind") != "tool_result_public"
        ):
            raise ValueError("agentic v2 trace pair kind mismatch")
        private_payload = private_event["payload"]
        public_payload = public_event["payload"]
        expected_commitment = {
            field: deepcopy(private_payload["result"].get(field))
            for field in _PUBLIC_COMMITMENT_FIELDS
        }
        if (
            public_payload.get("result_commitment") != expected_commitment
            or public_payload.get("replayed") != private_payload.get("replayed")
        ):
            raise ValueError("agentic v2 trace pair commitment mismatch")
    actual_pair = trace_pair_fingerprint(private_trace, public_trace)
    if actual_pair != expected_pair_sha256:
        raise ValueError("agentic v2 trace pair hash mismatch")


def trace_pair_fingerprint(private_trace: Any, public_trace: Any) -> str:
    return canonical_sha256({
        "schema_version": "2.0",
        "private_head_sha256": private_trace.get("event_chain_head_sha256"),
        "public_head_sha256": public_trace.get("event_chain_head_sha256"),
        "event_count": len(private_trace.get("events", [])),
    })


def verify_agentic_v2_metadata(value: Any) -> None:
    expected_keys = {
        "schema_version",
        "tool_contract_version",
        "policy_profile_id",
        "foundation_only",
        "lifecycle_state",
        "backend_identity",
        "capabilities_sha256",
        "runtime_fingerprint",
        "private_audit",
        "public_trace",
        "trace_pair_sha256",
    }
    if (
        not isinstance(value, dict)
        or set(value) != expected_keys
        or value.get("schema_version") != TOOL_CONTRACT_VERSION
        or value.get("tool_contract_version") != TOOL_CONTRACT_VERSION
        or value.get("foundation_only") is not True
        or value.get("lifecycle_state") != "finalized"
    ):
        raise ValueError("agentic v2 metadata is invalid")
    verify_trace_pair(
        value["private_audit"],
        value["public_trace"],
        value["trace_pair_sha256"],
    )
    first = value["private_audit"]["events"][0]
    if first.get("kind") != "started":
        raise ValueError("agentic v2 metadata startup is missing")
    started = first["payload"]
    if (
        value.get("policy_profile_id") != started.get("policy_profile_id")
        or value.get("backend_identity") != started.get("backend_identity")
        or value.get("capabilities_sha256") != canonical_sha256(
            started.get("capabilities")
        )
    ):
        raise ValueError("agentic v2 metadata startup identity mismatch")
    runtime = started["runtime"]
    canonical = foundation_fixture_identity(
        started["policy_profile_id"], runtime["budget_caps"]
    )
    if (
        started["backend_identity"] != canonical["backend_identity"]
        or started["capabilities"] != canonical["capabilities"]
        or runtime["substrate_manifest_sha256"] != canonical[
            "substrate_manifest_sha256"
        ]
        or runtime["package_snapshot_sha256"] != canonical[
            "package_snapshot_sha256"
        ]
        or runtime["browser_build_sha256"] != canonical[
            "browser_build_sha256"
        ]
    ):
        raise ValueError("agentic v2 canonical fixture identity mismatch")
    actual_runtime = runtime_fingerprint(
        policy_profile_id=started["policy_profile_id"],
        substrate_manifest_sha256=runtime["substrate_manifest_sha256"],
        package_snapshot_sha256=runtime["package_snapshot_sha256"],
        browser_build_sha256=runtime["browser_build_sha256"],
        backend_implementation_sha256=started["backend_identity"][
            "implementation_sha256"
        ],
        capabilities_sha256=canonical_sha256(started["capabilities"]),
        budget_caps=runtime["budget_caps"],
    )
    if actual_runtime != value.get("runtime_fingerprint"):
        raise ValueError("agentic v2 runtime fingerprint mismatch")
    _terminal_finalize_event(value["private_audit"])


def verify_agentic_v2_result(value: Any) -> None:
    if not isinstance(value, Mapping) or set(value) != {
        "success", "text", "deliverable_text", "files", "agentic_v2"
    }:
        raise ValueError("agentic v2 success result is invalid")
    if (
        value.get("success") is not True
        or not isinstance(value.get("text"), str)
        or value.get("deliverable_text") != value.get("text")
        or not isinstance(value.get("files"), list)
    ):
        raise ValueError("agentic v2 success result is invalid")
    metadata = value.get("agentic_v2")
    verify_agentic_v2_metadata(metadata)
    terminal = _terminal_finalize_event(metadata["private_audit"])
    request = terminal["payload"]["request"]
    result = terminal["payload"]["result"]
    if (
        request["arguments"]["summary"] != value["text"]
        or terminal["payload"]["replayed"] is not False
        or result.get("ok") is not True
        or result.get("error_type") is not None
    ):
        raise ValueError("agentic v2 terminal summary is invalid")
    artifacts = result.get("data", {}).get("artifacts")
    files = value["files"]
    if not isinstance(artifacts, list) or len(artifacts) != len(files):
        raise ValueError("agentic v2 terminal artifact count mismatch")
    for artifact, file_value in zip(artifacts, files):
        if not isinstance(artifact, Mapping) or not isinstance(file_value, Mapping):
            raise ValueError("agentic v2 terminal artifact is invalid")
        content = file_value.get("content")
        if (
            file_value.get("filename") != artifact.get("path")
            or not isinstance(content, bytes)
            or len(content) != artifact.get("size")
            or hashlib.sha256(content).hexdigest() != artifact.get("sha256")
        ):
            raise ValueError("agentic v2 terminal artifact bytes mismatch")


def verify_agentic_v2_failure_result(value: Any) -> None:
    if not isinstance(value, Mapping) or set(value) != {
        "success",
        "text",
        "deliverable_text",
        "files",
        "error",
        "agentic_v2",
    }:
        raise ValueError("agentic v2 failure result is invalid")
    metadata = value.get("agentic_v2")
    if (
        value.get("success") is not False
        or value.get("text") != ""
        or value.get("deliverable_text") != ""
        or value.get("files") != []
        or value.get("error") not in ERROR_TYPES
        or not isinstance(metadata, dict)
        or set(metadata) != {
            "schema_version",
            "foundation_only",
            "lifecycle_state",
            "private_audit",
            "public_trace",
            "trace_pair_sha256",
        }
        or metadata.get("schema_version") != TOOL_CONTRACT_VERSION
        or metadata.get("foundation_only") is not True
        or metadata.get("lifecycle_state") not in {"failed", "cancelled"}
    ):
        raise ValueError("agentic v2 failure result is invalid")
    verify_trace_pair(
        metadata["private_audit"],
        metadata["public_trace"],
        metadata["trace_pair_sha256"],
    )
    terminal = metadata["private_audit"]["events"][-1]
    payload = terminal.get("payload") if isinstance(terminal, dict) else None
    if (
        terminal.get("kind") != "failure"
        or not isinstance(payload, dict)
        or payload.get("error_type") != value["error"]
        or payload.get("lifecycle_state") != metadata["lifecycle_state"]
    ):
        raise ValueError("agentic v2 failure result does not match trace")


def _terminal_finalize_event(private_trace: Mapping[str, Any]) -> dict:
    events = private_trace.get("events")
    if not isinstance(events, list) or not events:
        raise ValueError("agentic v2 terminal finalize is missing")
    terminal = events[-1]
    payload = terminal.get("payload") if isinstance(terminal, dict) else None
    request = payload.get("request") if isinstance(payload, dict) else None
    result = payload.get("result") if isinstance(payload, dict) else None
    if (
        terminal.get("kind") != "tool_result"
        or not isinstance(request, dict)
        or request.get("name") != "finalize"
        or not isinstance(result, dict)
        or result.get("tool_name") != "finalize"
        or result.get("ok") is not True
        or payload.get("replayed") is not False
    ):
        raise ValueError("agentic v2 terminal finalize is missing")
    return terminal


def _valid_started_payload(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != {
        "run_id", "condition", "task_id", "backend_identity", "capabilities",
        "policy_profile_id", "runtime",
    }:
        return False
    identity = value.get("backend_identity")
    capabilities = value.get("capabilities")
    runtime = value.get("runtime")
    budget_caps = runtime.get("budget_caps") if isinstance(runtime, dict) else None
    structurally_valid = (
        all(
            isinstance(value.get(name), str) and bool(value[name])
            for name in ("run_id", "condition", "task_id", "policy_profile_id")
        )
        and isinstance(identity, dict)
        and set(identity) == {
            "backend_id", "foundation_only", "implementation_sha256"
        }
        and identity.get("backend_id") == FOUNDATION_BACKEND_ID
        and identity.get("foundation_only") is True
        and identity.get("implementation_sha256") == (
            foundation_implementation_fingerprint()
        )
        and value.get("policy_profile_id") in POLICY_PROFILE_IDS
        and isinstance(capabilities, dict)
        and set(capabilities) == {
            "commands", "runtimes", "packages", "formats", "budgets"
        }
        and capabilities.get("commands") == ["fixture-upper"]
        and capabilities.get("runtimes") == ["fixture"]
        and capabilities.get("formats") == ["html", "txt"]
        and _valid_package_capabilities(
            capabilities.get("packages"), value.get("policy_profile_id")
        )
        and _valid_budget_capabilities(capabilities.get("budgets"), budget_caps)
        and isinstance(runtime, dict)
        and set(runtime) == {
            "substrate_manifest_sha256",
            "package_snapshot_sha256",
            "browser_build_sha256",
            "budget_caps",
        }
        and all(is_sha256(runtime.get(name)) for name in (
            "substrate_manifest_sha256",
            "package_snapshot_sha256",
            "browser_build_sha256",
        ))
    )
    if not structurally_valid:
        return False
    try:
        canonical = foundation_fixture_identity(
            value["policy_profile_id"], budget_caps
        )
    except ValueError:
        return False
    return (
        identity == canonical["backend_identity"]
        and capabilities == canonical["capabilities"]
        and runtime["substrate_manifest_sha256"] == canonical[
            "substrate_manifest_sha256"
        ]
        and runtime["package_snapshot_sha256"] == canonical[
            "package_snapshot_sha256"
        ]
        and runtime["browser_build_sha256"] == canonical[
            "browser_build_sha256"
        ]
    )


def _valid_failure_payload(value: Any) -> bool:
    if (
        not isinstance(value, dict)
        or set(value) != {"error_type", "lifecycle_state", "stage"}
        or value.get("lifecycle_state") not in {"failed", "cancelled"}
    ):
        return False
    try:
        validate_failure_stage(value.get("error_type"), value.get("stage"))
    except ValueError:
        return False
    return True


def _verify_private_result_semantics(
    request: Any,
    result: Mapping[str, Any],
    *,
    replayed: bool,
    previous_state: Any,
    event_state: Any,
    call_ledger: dict[str, dict],
    semantic_ledger: dict[str, Any],
    started_payload: Any,
) -> None:
    if not isinstance(request, dict) or set(request) != {
        "call_id", "name", "arguments"
    }:
        raise ValueError("agentic v2 tool request commitment is invalid")
    if result.get("ok") is True:
        if result.get("error_type") is not None:
            raise ValueError("agentic v2 result status mismatch")
    elif result.get("error_type") is None:
        raise ValueError("agentic v2 result status mismatch")
    request_call_id = request.get("call_id")
    request_name = request.get("name")
    request_error = _request_error_type(request)
    prior = call_ledger.get(request_call_id)
    expected_call_id = "invalid" if request_error == "invalid_call_id" else request_call_id
    expected_tool_name = (
        request_name
        if request_error not in {"invalid_call_id", "unknown_tool"}
        else None
    )
    if (
        result.get("call_id") != expected_call_id
        or result.get("tool_name") != expected_tool_name
    ):
        raise ValueError("agentic v2 result call identity mismatch")
    if prior is not None and request_error is not None:
        if (
            replayed
            or not _is_exact_unexecuted_error(result, "call_id_conflict")
            or event_state != previous_state
        ):
            raise ValueError("agentic v2 replay history mismatch")
        return
    if request_error is not None:
        if replayed or not _is_exact_unexecuted_error(result, request_error):
            raise ValueError("agentic v2 invalid request result mismatch")
        if event_state != previous_state:
            raise ValueError("agentic v2 result state continuity mismatch")
        return

    try:
        validated_arguments = validate_tool_arguments(
            request_name, request.get("arguments")
        )
    except ValueError as exc:
        raise ValueError("agentic v2 tool request commitment is invalid") from exc
    request_sha256 = canonical_sha256({
        "tool_contract_version": TOOL_CONTRACT_VERSION,
        "call_id": request_call_id,
        "name": request_name,
        "arguments": validated_arguments,
    })
    if prior is not None:
        same_request = prior["request_sha256"] == request_sha256
        same_state = prior["result"].get("state_after_sha256") == previous_state
        if same_request and same_state:
            if (
                not replayed
                or prior["result"] != result
                or event_state != previous_state
            ):
                raise ValueError("agentic v2 replay history mismatch")
        elif (
            replayed
            or not _is_exact_unexecuted_error(result, "call_id_conflict")
            or event_state != previous_state
        ):
            raise ValueError("agentic v2 replay history mismatch")
        return
    if replayed:
        raise ValueError("agentic v2 replay history mismatch")

    if result.get("request_sha256") is not None:
        if semantic_ledger["executed_calls"] >= started_payload["runtime"][
            "budget_caps"
        ]["tool_calls"]:
            raise ValueError("agentic v2 tool budget state mismatch")
        if result.get("request_sha256") != request_sha256:
            raise ValueError("agentic v2 tool request hash mismatch")
        try:
            validate_tool_result_data(
                request_name,
                validated_arguments,
                result.get("ok") is True,
                result.get("data"),
            )
        except ValueError as exc:
            raise ValueError("agentic v2 result data mismatch") from exc
        _verify_fixture_result_semantics(
            request_name,
            validated_arguments,
            result,
            previous_state=previous_state,
            semantic_ledger=semantic_ledger,
            started_payload=started_payload,
        )
    else:
        if not _is_exact_unexecuted_error(result, "tool_budget_exhausted"):
            raise ValueError("agentic v2 unexecuted result mismatch")
        if semantic_ledger["executed_calls"] < started_payload["runtime"][
            "budget_caps"
        ]["tool_calls"]:
            raise ValueError("agentic v2 tool budget state mismatch")

    usage = result.get("usage_delta") or {}
    executed = usage.get("tool_calls") == 1
    if executed and usage != {
        "tool_calls": 1,
        "wall_ms": 0,
        "output_bytes": len(json.dumps(
            result.get("data"),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")),
    }:
        raise ValueError("agentic v2 result usage mismatch")
    state_before = result.get("state_before_sha256")
    state_after = result.get("state_after_sha256")
    if executed:
        if (
            result.get("request_sha256") is None
            or not is_sha256(state_before)
            or not is_sha256(state_after)
            or event_state != state_after
            or previous_state is None
            or (
                replayed
                and state_after != previous_state
            )
            or (
                not replayed
                and state_before != previous_state
            )
        ):
            raise ValueError("agentic v2 result state continuity mismatch")
    elif (
        usage.get("tool_calls") != 0
        or result.get("request_sha256") is not None
        or state_before is not None
        or state_after is not None
        or event_state != previous_state
    ):
        raise ValueError("agentic v2 result state continuity mismatch")
    if executed:
        semantic_ledger["executed_calls"] += 1
        call_ledger[request_call_id] = {
            "request_sha256": request_sha256,
            "result": deepcopy(dict(result)),
        }


def _request_error_type(request: Mapping[str, Any]) -> str | None:
    call_id = request.get("call_id")
    if not isinstance(call_id, str) or re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", call_id
    ) is None:
        return "invalid_call_id"
    name = request.get("name")
    if name not in TOOL_SCHEMAS:
        return "unknown_tool"
    try:
        validate_tool_arguments(name, request.get("arguments"))
    except ValueError:
        return "invalid_arguments"
    return None


def _is_exact_unexecuted_error(
    result: Mapping[str, Any],
    error_types: str | set[str],
) -> bool:
    allowed = {error_types} if isinstance(error_types, str) else error_types
    return (
        result.get("ok") is False
        and result.get("error_type") in allowed
        and result.get("request_sha256") is None
        and result.get("data") == {}
        and result.get("usage_delta") == {
            "tool_calls": 0,
            "wall_ms": 0,
            "output_bytes": 0,
        }
        and result.get("state_before_sha256") is None
        and result.get("state_after_sha256") is None
    )


def _valid_package_capabilities(value: Any, profile_id: Any) -> bool:
    if not isinstance(value, list) or value != sorted(set(value)):
        return False
    expected = (
        []
        if profile_id == "offline-full-v1"
        else [coordinate for coordinate, _ in _FOUNDATION_PACKAGE_RECORDS]
    )
    return value == expected


def _valid_budget_capabilities(value: Any, budget_caps: Any) -> bool:
    if not isinstance(budget_caps, dict) or set(budget_caps) != {
        "tool_calls", "wall_seconds"
    }:
        return False
    if (
        type(budget_caps["tool_calls"]) is not int
        or not 1 <= budget_caps["tool_calls"] <= 256
        or type(budget_caps["wall_seconds"]) is not int
        or not 1 <= budget_caps["wall_seconds"] <= 3600
    ):
        return False
    return value == [
        f"tool_calls={budget_caps['tool_calls']}",
        f"wall_seconds={budget_caps['wall_seconds']}",
    ]


def _verify_fixture_result_semantics(
    name: str,
    arguments: Mapping[str, Any],
    result: Mapping[str, Any],
    *,
    previous_state: Any,
    semantic_ledger: dict[str, Any],
    started_payload: Any,
) -> None:
    if not isinstance(started_payload, dict):
        raise ValueError("agentic v2 fixture semantics lack startup identity")
    profile = started_payload["policy_profile_id"]
    runtime = started_payload["runtime"]
    canonical = foundation_fixture_identity(profile, runtime["budget_caps"])
    if previous_state != _fixture_state_sha256(semantic_ledger):
        raise ValueError("agentic v2 fixture state-before mismatch")
    ok = result.get("ok") is True
    error_type = result.get("error_type")
    data = result.get("data") or {}
    expected = _replay_fixture_tool(
        name,
        arguments,
        semantic_ledger,
        canonical=canonical,
    )
    expected_state_after = _fixture_state_sha256(semantic_ledger)
    expected_result = _fixture_result_envelope(
        name=name,
        arguments=arguments,
        call_id=result["call_id"],
        payload=expected,
        state_before=previous_state,
        state_after=expected_state_after,
    )
    encoded = json.dumps(
        expected_result,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    if len(encoded) > 65536:
        expected_result = _fixture_executed_error(
            expected_result, "tool_result_too_large"
        )
    elif error_type in {
        "tool_result_too_large",
        "finalize_result_mismatch",
        "invalid_result_envelope",
        "task_wall_time_exhausted",
    }:
        raise ValueError("agentic v2 fixture wrapper condition mismatch")
    if result != expected_result:
        raise ValueError("agentic v2 fixture tool result mismatch")


def _fixture_result_envelope(
    *,
    name: str,
    arguments: Mapping[str, Any],
    call_id: str,
    payload: Mapping[str, Any],
    state_before: str,
    state_after: str,
) -> dict:
    ok = payload.get("ok") is True
    error_type = None if ok else payload.get("error_type")
    data = deepcopy(payload.get("data", {})) if ok else {}
    request_sha256 = canonical_sha256({
        "tool_contract_version": TOOL_CONTRACT_VERSION,
        "call_id": call_id,
        "name": name,
        "arguments": dict(arguments),
    })
    value = {
        "schema_version": TOOL_CONTRACT_VERSION,
        "call_id": call_id,
        "tool_name": name,
        "request_sha256": request_sha256,
        "ok": ok,
        "error_type": error_type,
        "data": data,
        "usage_delta": {
            "tool_calls": 1,
            "wall_ms": 0,
            "output_bytes": len(json.dumps(
                data,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")),
        },
        "state_before_sha256": state_before,
        "state_after_sha256": state_after,
    }
    value["result_sha256"] = canonical_sha256(value)
    return value


def _fixture_executed_error(
    result: Mapping[str, Any],
    error_type: str,
) -> dict:
    value = deepcopy(dict(result))
    value.pop("result_sha256", None)
    value["ok"] = False
    value["error_type"] = error_type
    value["data"] = {}
    value["usage_delta"] = {**value["usage_delta"], "output_bytes": 2}
    value["result_sha256"] = canonical_sha256(value)
    return value


def _new_fixture_semantic_ledger(started_payload: Mapping[str, Any]) -> dict:
    runtime = started_payload["runtime"]
    canonical = foundation_fixture_identity(
        started_payload["policy_profile_id"], runtime["budget_caps"]
    )
    return {
        "profile": started_payload["policy_profile_id"],
        "budget_caps": deepcopy(runtime["budget_caps"]),
        "package_records": tuple(canonical["package_records"]),
        "directories": {"."},
        "files": {},
        "resolved_locks": set(),
        "active_locks": set(),
        "terminal_identity": None,
        "executed_calls": 0,
    }


def _verify_failure_causality(
    payload: Mapping[str, Any],
    *,
    started_seen: bool,
    last_tool_name: Any,
    last_tool_result: Any,
) -> None:
    error_type = payload["error_type"]
    lifecycle_state = payload["lifecycle_state"]
    stage = payload["stage"]
    if lifecycle_state == "cancelled" and error_type != "cancelled":
        raise ValueError("agentic v2 failure lifecycle mismatch")
    if lifecycle_state == "failed" and error_type == "cancelled":
        raise ValueError("agentic v2 failure lifecycle mismatch")
    if not started_seen:
        if stage not in {"backend", "startup", "control", "cleanup"}:
            raise ValueError("agentic v2 pre-start failure stage mismatch")
        return
    if stage not in {"runtime", "control", "cleanup"}:
        raise ValueError("agentic v2 runtime failure stage mismatch")
    if stage == "cleanup":
        if error_type != "compute_cleanup_failed":
            raise ValueError("agentic v2 cleanup failure mismatch")
        return
    if stage == "control":
        if isinstance(last_tool_result, Mapping) and (
            last_tool_result.get("ok") is False
            or (
                last_tool_name == "finalize"
                and error_type == "cancelled"
            )
        ):
            raise ValueError("agentic v2 control failure cause mismatch")
        return
    if isinstance(last_tool_result, Mapping):
        if last_tool_result.get("ok") is False:
            if error_type != last_tool_result.get("error_type"):
                raise ValueError("agentic v2 failure cause mismatch")
            return
        if last_tool_name == "finalize":
            if error_type not in {
                "compute_cleanup_failed",
                "runner_internal_error",
                "task_wall_time_exhausted",
            }:
                raise ValueError("agentic v2 post-finalize failure mismatch")
            return
        if error_type not in {
            "cancelled",
            "finalize_not_called",
            "runner_internal_error",
            "task_wall_time_exhausted",
        }:
            raise ValueError("agentic v2 failure cause mismatch")
        return
    if error_type not in {
        "cancelled",
        "finalize_not_called",
        "runner_internal_error",
        "task_wall_time_exhausted",
    }:
        raise ValueError("agentic v2 failure cause mismatch")


def _fixture_state_sha256(ledger: Mapping[str, Any]) -> str:
    entries = []

    def visit(directory: str) -> None:
        prefix = "" if directory == "." else f"{directory}/"
        children = set()
        for path in ledger["directories"]:
            if path == "." or not path.startswith(prefix):
                continue
            remainder = path[len(prefix):]
            if "/" not in remainder:
                children.add(remainder)
        for path in ledger["files"]:
            if not path.startswith(prefix):
                continue
            remainder = path[len(prefix):]
            if "/" not in remainder:
                children.add(remainder)
        for name in sorted(children):
            path = name if directory == "." else f"{directory}/{name}"
            if path in ledger["directories"]:
                entries.append({
                    "path": path,
                    "kind": "directory",
                    "mode": 0o700,
                })
                visit(path)
            else:
                content = ledger["files"][path]
                entries.append({
                    "path": path,
                    "kind": "file",
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "size": len(content),
                    "mode": 0o600,
                })

    visit(".")
    terminal = ledger["terminal_identity"]
    return canonical_sha256({
        "root_mode": 0o700,
        "profile": ledger["profile"],
        "package_catalog": ledger["package_records"],
        "budget_caps": ledger["budget_caps"],
        "entries": entries,
        "active_locks": sorted(ledger["active_locks"]),
        "terminal_result_sha256": (
            canonical_sha256(terminal) if terminal is not None else None
        ),
    })


def _replay_fixture_tool(
    name: str,
    arguments: Mapping[str, Any],
    ledger: dict[str, Any],
    *,
    canonical: Mapping[str, Any],
) -> dict:
    if name == "capabilities_query":
        kind = arguments["kind"]
        return {
            "ok": True,
            "data": {
                "kind": kind,
                "items": canonical["capabilities"][kind],
            },
        }
    if name == "workspace_apply":
        return _replay_workspace_apply(arguments, ledger)
    if name == "exec_run":
        return _replay_exec_run(arguments, ledger)
    if name == "environment_resolve":
        return _replay_environment_resolve(arguments, ledger, canonical)
    if name == "environment_activate":
        return _replay_environment_activate(arguments, ledger)
    if name == "browser_run":
        return _replay_browser_run(arguments, ledger)
    if name in {"verify_public", "finalize"}:
        return _replay_artifact_tool(name, arguments, ledger)
    raise ValueError("agentic v2 fixture tool is unsupported")


def _replay_workspace_apply(
    arguments: Mapping[str, Any],
    ledger: dict[str, Any],
) -> dict:
    operation = arguments["operation"]
    if operation == "copy":
        source = arguments["source"]
        if source == "." or arguments["destination"] == ".":
            return {"ok": False, "error_type": "fixture_backend_error"}
        content = ledger["files"].get(source)
        if content is None:
            return {"ok": False, "error_type": "fixture_backend_error"}
        error = _virtual_write(ledger, arguments["destination"], content)
        if error is not None:
            return {"ok": False, "error_type": error}
        return {"ok": True, "data": {"path": arguments["destination"]}}
    path = arguments["path"]
    if operation == "list":
        if path not in ledger["directories"]:
            return {"ok": False, "error_type": "path_not_directory"}
        return {
            "ok": True,
            "data": {"entries": _virtual_list(path, ledger)},
        }
    if operation == "read":
        if path == ".":
            return {"ok": False, "error_type": "fixture_backend_error"}
        content = ledger["files"].get(path)
        if content is None:
            return {"ok": False, "error_type": "fixture_backend_error"}
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            return {"ok": False, "error_type": "fixture_backend_error"}
        selected = text[
            int(arguments.get("offset", 0)):
            int(arguments.get("offset", 0))
            + int(arguments.get("limit", 1048576))
        ]
        return {"ok": True, "data": {
            "content": selected,
            "content_sha256": hashlib.sha256(
                selected.encode("utf-8")
            ).hexdigest(),
        }}
    if operation in {"write", "patch"}:
        if path == "." or path in ledger["directories"]:
            return {"ok": False, "error_type": "fixture_backend_error"}
        error = _virtual_write(
            ledger, path, str(arguments["content"]).encode("utf-8")
        )
        if error is not None:
            return {"ok": False, "error_type": error}
    elif operation == "delete":
        if path == ".":
            return {"ok": False, "error_type": "fixture_backend_error"}
        if path in ledger["files"]:
            del ledger["files"][path]
        elif path in ledger["directories"] and not _virtual_list(path, ledger):
            ledger["directories"].remove(path)
        else:
            return {"ok": False, "error_type": "fixture_backend_error"}
    else:
        error = _virtual_reserve_entries(
            ledger, path, temporary_leaf=False
        )
        if error is not None:
            return {"ok": False, "error_type": error}
        error = _virtual_mkdir(ledger, path)
        if error is not None:
            return {"ok": False, "error_type": error}
    return {"ok": True, "data": {"path": path}}


def _replay_exec_run(
    arguments: Mapping[str, Any],
    ledger: dict[str, Any],
) -> dict:
    argv = arguments.get("argv")
    if not isinstance(argv, list) or not argv:
        return {"ok": False, "error_type": "capability_unavailable"}
    if argv[0] != "fixture-upper" or len(argv) != 3:
        return {"ok": False, "error_type": "capability_unavailable"}
    cwd = arguments["cwd"]
    if cwd not in ledger["directories"]:
        return {"ok": False, "error_type": "path_not_directory"}
    source = _virtual_join(cwd, argv[1])
    destination = _virtual_join(cwd, argv[2])
    if (
        source is None
        or destination is None
        or source not in ledger["files"]
        or destination in ledger["directories"]
    ):
        return {"ok": False, "error_type": "fixture_backend_error"}
    error = _virtual_write(
        ledger, destination, ledger["files"][source].upper()
    )
    if error is not None:
        return {"ok": False, "error_type": error}
    return {"ok": True, "data": {"returncode": 0}}


def _replay_environment_resolve(
    arguments: Mapping[str, Any],
    ledger: dict[str, Any],
    canonical: Mapping[str, Any],
) -> dict:
    if ledger["profile"] == "offline-full-v1":
        return {"ok": False, "error_type": "capability_unavailable"}
    requirements = sorted(arguments["requirements"])
    coordinates = [
        f"{arguments['ecosystem']}:{requirement}"
        for requirement in requirements
    ]
    catalog = dict(canonical["package_records"])
    if any(coordinate not in catalog for coordinate in coordinates):
        return {"ok": False, "error_type": "package_not_in_snapshot"}
    lock = {
        "ecosystem": arguments["ecosystem"],
        "requirements": requirements,
        "blobs": [catalog[coordinate] for coordinate in coordinates],
    }
    digest = canonical_sha256(lock)
    ledger["resolved_locks"].add(digest)
    return {"ok": True, "data": {"lock_digest": digest, "lock": lock}}


def _replay_environment_activate(
    arguments: Mapping[str, Any],
    ledger: dict[str, Any],
) -> dict:
    if ledger["profile"] == "offline-full-v1":
        return {"ok": False, "error_type": "capability_unavailable"}
    digest = arguments["lock_digest"]
    if digest not in ledger["resolved_locks"]:
        return {"ok": False, "error_type": "unapproved_lock"}
    ledger["active_locks"].add(digest)
    return {"ok": True, "data": {"environment_id": digest}}


def _replay_browser_run(
    arguments: Mapping[str, Any],
    ledger: Mapping[str, Any],
) -> dict:
    operation = arguments["operation"]
    if operation in {"search", "open_url"}:
        return {"ok": False, "error_type": "capability_unavailable"}
    path = arguments["path"]
    content = ledger["files"].get(path)
    if content is None:
        return {"ok": False, "error_type": "fixture_backend_error"}
    return {"ok": True, "data": {
        "path": path,
        "sha256": hashlib.sha256(content).hexdigest(),
    }}


def _replay_artifact_tool(
    name: str,
    arguments: Mapping[str, Any],
    ledger: dict[str, Any],
) -> dict:
    artifacts = []
    terminal_files = []
    total = 0
    for path in arguments["deliverables"]:
        content = ledger["files"].get(path)
        if not content:
            return {"ok": False, "error_type": "artifact_not_openable"}
        total += len(content)
        if total > 64 * 1024 * 1024:
            return {"ok": False, "error_type": "artifact_not_openable"}
        artifacts.append({
            "path": path,
            "sha256": hashlib.sha256(content).hexdigest(),
            "size": len(content),
        })
        terminal_files.append({
            "filename": path,
            "sha256": hashlib.sha256(content).hexdigest(),
        })
    if name == "finalize":
        ledger["terminal_identity"] = {
            "success": True,
            "text": arguments["summary"],
            "files": terminal_files,
        }
    return {"ok": True, "data": {"artifacts": artifacts}}


def _virtual_write(ledger: dict[str, Any], path: str, content: bytes) -> str | None:
    if path == "." or path in ledger["directories"] or len(content) > 1048576:
        return "fixture_backend_error"
    error = _virtual_reserve_entries(ledger, path, temporary_leaf=True)
    if error is not None:
        return error
    if sum(len(value) for value in ledger["files"].values()) + len(content) > (
        64 * 1024 * 1024
    ):
        return "fixture_backend_error"
    error = _virtual_mkdir(ledger, _virtual_parent(path))
    if error is not None:
        return error
    ledger["files"][path] = content
    return None


def _virtual_mkdir(ledger: dict[str, Any], path: str) -> str | None:
    if path == ".":
        return None
    current = ""
    for part in path.split("/"):
        current = f"{current}/{part}" if current else part
        if current in ledger["files"]:
            return "fixture_backend_error"
        ledger["directories"].add(current)
    return None


def _virtual_reserve_entries(
    ledger: Mapping[str, Any],
    path: str,
    *,
    temporary_leaf: bool,
) -> str | None:
    if path == ".":
        return None
    existing = set(ledger["directories"]) - {"."} | set(ledger["files"])
    planned = []
    current = ""
    for part in path.split("/"):
        current = f"{current}/{part}" if current else part
        if current not in existing:
            planned.append(current)
    leaf_exists = path in existing
    peak_extra = len(planned) + int(temporary_leaf and leaf_exists)
    if len(existing) + peak_extra > 4096:
        return "fixture_backend_error"
    child_counts: dict[str, int] = {}
    for value in existing:
        parent = _virtual_parent(value)
        child_counts[parent] = child_counts.get(parent, 0) + 1
    for value in planned:
        parent = _virtual_parent(value)
        child_counts[parent] = child_counts.get(parent, 0) + 1
    if temporary_leaf and leaf_exists:
        parent = _virtual_parent(path)
        child_counts[parent] = child_counts.get(parent, 0) + 1
    if any(count > 1024 for count in child_counts.values()):
        return "fixture_backend_error"
    return None


def _virtual_list(path: str, ledger: Mapping[str, Any]) -> list[str]:
    prefix = "" if path == "." else f"{path}/"
    children = set()
    for value in set(ledger["directories"]) | set(ledger["files"]):
        if value == "." or not value.startswith(prefix):
            continue
        remainder = value[len(prefix):]
        if "/" not in remainder:
            children.add(remainder)
    return sorted(children)


def _virtual_parent(path: str) -> str:
    return path.rsplit("/", 1)[0] if "/" in path else "."


def _virtual_join(directory: str, child: Any) -> str | None:
    try:
        canonical_relative_path(directory)
        canonical_relative_path(child)
    except ValueError:
        return None
    if child == ".":
        return None
    combined = child if directory == "." else f"{directory}/{child}"
    try:
        return canonical_relative_path(combined)
    except ValueError:
        return None