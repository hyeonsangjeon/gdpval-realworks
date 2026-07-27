from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from core.agentic_v2_contract import (
    EVENT_SCHEMA,
    TOOL_CONTRACT_VERSION,
    TOOL_NAMES,
    TOOL_SCHEMAS,
    TOOL_RESULT_SCHEMA,
    AgenticV2Lifecycle,
    AgenticV2Profile,
    LifecycleState,
    contract_fingerprint,
    is_sha256,
    responses_tool_definitions,
    validate_tool_arguments,
    validate_tool_result_data,
)
import core.agentic_v2_contract as contract_module


def test_v2_tool_definitions_are_stable_strict_and_valid():
    definitions = responses_tool_definitions()

    assert tuple(item["name"] for item in definitions) == TOOL_NAMES
    assert all(item["strict"] is True for item in definitions)
    assert all(item["type"] == "function" for item in definitions)
    for schema in TOOL_SCHEMAS.values():
        Draft202012Validator.check_schema(schema)
    Draft202012Validator.check_schema(TOOL_RESULT_SCHEMA)
    Draft202012Validator.check_schema(EVENT_SCHEMA)


@pytest.mark.parametrize("name", TOOL_NAMES)
def test_v2_tool_schemas_reject_unknown_fields(name):
    schema = TOOL_SCHEMAS[name]
    candidate = _minimal_arguments(name)
    candidate["unexpected"] = True

    with pytest.raises(ValueError, match="invalid agentic v2 tool arguments"):
        validate_tool_arguments(name, candidate)


@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        ("workspace_apply", {"operation": "read", "path": "../secret"}),
        ("workspace_apply", {"operation": "copy", "source": "/etc/passwd", "destination": "copy"}),
        ("exec_run", {"argv": ["python"], "cwd": "/root", "timeout_seconds": 1}),
        ("environment_resolve", {"ecosystem": "python", "requirements": ["pkg @ https://example.com/pkg.whl"]}),
        ("environment_activate", {"lock_digest": "mutable-tag"}),
        ("finalize", {"deliverables": ["../output"], "summary": "done"}),
    ],
)
def test_v2_contract_rejects_escape_and_mutable_coordinates(name, arguments):
    with pytest.raises(ValueError, match="invalid agentic v2 tool arguments"):
        validate_tool_arguments(name, arguments)


@pytest.mark.parametrize(
    "path",
    ["./a", "a//b", "a/./b", "a/../b", "/a", "a\\b", "report\u0085.txt"],
)
def test_v2_contract_rejects_noncanonical_path_aliases(path):
    with pytest.raises(ValueError, match="invalid agentic v2 tool arguments|canonical"):
        validate_tool_arguments(
            "workspace_apply", {"operation": "read", "path": path}
        )


def test_v2_contract_enforces_utf8_byte_path_limit():
    ascii_boundary = "a" * 240
    multibyte_boundary = "é" * 120

    assert validate_tool_arguments(
        "workspace_apply",
        {"operation": "read", "path": ascii_boundary},
    )["path"] == ascii_boundary
    assert validate_tool_arguments(
        "workspace_apply",
        {"operation": "read", "path": multibyte_boundary},
    )["path"] == multibyte_boundary

    with pytest.raises(ValueError, match="canonical relative POSIX"):
        validate_tool_arguments(
            "workspace_apply",
            {"operation": "read", "path": "é" * 121},
        )


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com",
        "https://user:pass@example.com/path",
        "https://localhost/path",
        "https://127.0.0.1/path",
        "https://169.254.169.254/latest/meta-data",
        "https://example.com./path",
        "https://example.com:/path",
        "https://example.com:99999/path",
        "https://example.com/a/../secret",
        "https://example.com/%2e%2e/secret",
        "https://example.com/%252e%252e/secret",
        "https://example.com/a%2fb",
        "https://example.com/line\nbreak",
        "https://2130706433/",
        "https://0x7f000001/",
        "https://0x7f.0x0.0x0.0x1/",
        "https://example.com/%c0%80",
        "https://example.com/%E2%80%A8",
        "https://example.com/\u0080",
        "https://example.com/?value=\u009f",
        "file:///etc/passwd",
        "not-a-url",
    ],
)
def test_v2_contract_rejects_nonpublic_or_malformed_urls(url):
    with pytest.raises(
        ValueError,
        match="invalid agentic v2 tool arguments|public HTTPS|URL is invalid",
    ):
        validate_tool_arguments(
            "browser_run", {"operation": "open_url", "url": url}
        )


def test_v2_contract_accepts_canonical_public_https_url():
    arguments = {
        "operation": "open_url",
        "url": "https://example.com/report?id=42",
    }

    assert validate_tool_arguments("browser_run", arguments) == arguments


@pytest.mark.parametrize(
    "path",
    ["report\u0085.txt", "report\x7f.txt", "é" * 121],
)
def test_v2_contract_rejects_noncanonical_browser_result_path(path):
    with pytest.raises(ValueError, match="result data is invalid|canonical"):
        validate_tool_result_data(
            "browser_run",
            {"operation": "search", "query": "offline"},
            True,
            {"path": path, "sha256": "a" * 64},
        )


def test_v2_profile_requires_exact_version_and_known_profile():
    profile = AgenticV2Profile.from_mapping({
        "tool_contract_version": TOOL_CONTRACT_VERSION,
        "policy_profile_id": "offline-full-v1",
        "foundation_only": True,
    })

    assert profile.tool_contract_version == "2.0"
    assert profile.policy_profile_id == "offline-full-v1"

    with pytest.raises(ValueError, match="tool_contract_version"):
        AgenticV2Profile.from_mapping({
            "tool_contract_version": "1.0",
            "policy_profile_id": "offline-full-v1",
            "foundation_only": True,
        })
    with pytest.raises(ValueError, match="policy_profile_id"):
        AgenticV2Profile.from_mapping({
            "tool_contract_version": "2.0",
            "policy_profile_id": "unrestricted",
            "foundation_only": True,
        })
    with pytest.raises(ValueError, match="unknown agentic v2 setting"):
        AgenticV2Profile.from_mapping({
            "tool_contract_version": "2.0",
            "policy_profile_id": "offline-full-v1",
            "foundation_only": True,
            "fallback": "host",
        })
    with pytest.raises(ValueError, match="foundation_only"):
        AgenticV2Profile.from_mapping({
            "tool_contract_version": "2.0",
            "policy_profile_id": "offline-full-v1",
        })


def test_v2_lifecycle_accepts_legal_completion_path():
    lifecycle = AgenticV2Lifecycle()

    assert lifecycle.transition("started") is LifecycleState.STARTED
    assert lifecycle.transition("active") is LifecycleState.ACTIVE
    lifecycle.require_tool_allowed("exec_run")
    assert lifecycle.transition("finalizing") is LifecycleState.FINALIZING
    lifecycle.require_tool_allowed("verify_public")
    lifecycle.require_tool_allowed("finalize")
    assert lifecycle.transition("finalized") is LifecycleState.FINALIZED
    assert lifecycle.terminal is True


def test_v2_lifecycle_rejects_invalid_transition_and_terminal_tools():
    lifecycle = AgenticV2Lifecycle()

    with pytest.raises(ValueError, match="created->finalized"):
        lifecycle.transition("finalized")
    lifecycle.transition("started")
    lifecycle.transition("active")
    lifecycle.transition("failed")
    with pytest.raises(ValueError, match="lifecycle is terminal"):
        lifecycle.require_tool_allowed("capabilities_query")


def test_v2_lifecycle_forbids_mutation_while_finalizing():
    lifecycle = AgenticV2Lifecycle(LifecycleState.FINALIZING)

    for name in ("workspace_apply", "exec_run", "environment_activate", "browser_run"):
        with pytest.raises(ValueError, match="mutation is forbidden"):
            lifecycle.require_tool_allowed(name)


def test_v2_contract_fingerprint_is_deterministic_and_sensitive(monkeypatch):
    first = contract_fingerprint()
    second = contract_fingerprint()

    assert first == second
    assert is_sha256(first)

    changed = deepcopy(responses_tool_definitions())
    changed[0]["description"] += " changed"
    assert changed != responses_tool_definitions()

    source = Path(contract_module.__file__).read_bytes()

    class ChangedSourcePath:
        def __init__(self, _value):
            pass

        def read_bytes(self):
            return source + b"\n# changed"

    monkeypatch.setattr(contract_module, "Path", ChangedSourcePath)
    assert contract_fingerprint() != first


def _minimal_arguments(name):
    return {
        "capabilities_query": {"kind": "commands"},
        "workspace_apply": {"operation": "list", "path": "."},
        "exec_run": {"argv": ["python", "--version"], "cwd": ".", "timeout_seconds": 30},
        "environment_resolve": {"ecosystem": "python", "requirements": ["pandas==2.2.3"]},
        "environment_activate": {"lock_digest": "a" * 64},
        "browser_run": {"operation": "open_local", "path": "report.html"},
        "verify_public": {"deliverables": ["report.pdf"]},
        "finalize": {"deliverables": ["report.pdf"], "summary": "done"},
    }[name]