"""Model-free directory semantics; no live observation or host-admission proof."""

from copy import deepcopy
import socket
import subprocess

import httpx
import huggingface_hub
import openai
import pytest

from core.agentic_v2_contract import validate_tool_arguments
from core.agentic_v2_fixture_backend import AgenticV2FixtureBackend
from core.agentic_v2_provenance import (
    verify_agentic_v2_failure_result,
    verify_agentic_v2_result,
)
from core.agentic_v2_runner import AgenticV2ScriptedRunner


@pytest.mark.parametrize("case", [
    "empty_then_written", "file_as_directory", "missing_directory",
    "traversal", "symlink",
])
def test_time_budget_v2_directory_root(case, tmp_path, monkeypatch, record_property):
    """Exercise the real dispatcher, descriptor-backed workspace and replay."""
    effects = []

    def forbidden(*_args, **_kwargs):
        effects.append("forbidden_external_effect")
        pytest.fail("directory regression attempted an external effect")

    for target, names in (
        (socket, ("create_connection", "getaddrinfo")),
        (socket.socket, ("connect", "connect_ex")),
        (subprocess, ("Popen",)),
        (httpx.Client, ("send",)),
        (httpx.AsyncClient, ("send",)),
        (openai, ("OpenAI", "AzureOpenAI", "AsyncOpenAI", "AsyncAzureOpenAI")),
        (huggingface_hub, ("HfApi", "hf_hub_download", "snapshot_download")),
    ):
        for name in names:
            monkeypatch.setattr(target, name, forbidden)

    # The declared contract permits the root as ".", not an absolute path
    # or an empty string. No provider or alternate path resolver is needed.
    root_arguments = {"operation": "list", "path": "."}
    assert validate_tool_arguments("workspace_apply", root_arguments) == root_arguments
    for invalid in ("", "/", "../outside"):
        with pytest.raises(ValueError):
            validate_tool_arguments("workspace_apply", {"operation": "list", "path": invalid})

    outside = tmp_path / "outside"
    outside.mkdir()
    protected = outside / "sentinel.txt"
    protected.write_bytes(b"synthetic outside bytes stay unchanged")
    created = []

    def backend_factory(**kwargs):
        backend = AgenticV2FixtureBackend(root=tmp_path / "owned", **kwargs)
        created.append(backend)
        assert list(backend.work.iterdir()) == []
        if case == "symlink":
            # A symlink is unsafe initial state, not a directory alias.
            (backend.work / "link").symlink_to(outside, target_is_directory=True)
        return backend

    content = "synthetic directory regression\n"
    calls = [
        {"call_id": "list-empty", "name": "workspace_apply", "arguments": root_arguments},
        {"call_id": "write-file", "name": "workspace_apply", "arguments": {
            "operation": "write", "path": "report.txt", "content": content,
        }},
        {"call_id": "list-written", "name": "workspace_apply", "arguments": root_arguments},
    ]
    refused_paths = {
        "file_as_directory": "report.txt", "missing_directory": "missing",
        "traversal": "../outside",
    }
    if case in refused_paths:
        calls.append({"call_id": "list-refused", "name": "workspace_apply", "arguments": {
            "operation": "list", "path": refused_paths[case],
        }})
    calls.append({"call_id": "finalize", "name": "finalize", "arguments": {
        "deliverables": ["report.txt"], "summary": "synthetic directory check",
    }})

    runner = AgenticV2ScriptedRunner(
        backend_factory=backend_factory,
        required_backend_type=AgenticV2FixtureBackend,
        scripted_calls=calls,
        profile={"tool_contract_version": "2.0", "policy_profile_id": "offline-full-v1", "foundation_only": True},
    )
    try:
        result = runner.run("synthetic directory check", task_id="synthetic-directory-task")
    finally:
        runner.close()
    events = result["agentic_v2"]["private_audit"]["events"]
    tools = [event["payload"] for event in events if event["kind"] == "tool_result"]
    record_property("directory_case", case)
    record_property("runner_error", result.get("error", "none"))
    record_property("tool_events", len(tools))
    assert len(created) == 1 and created[0].closed
    assert not created[0].work.exists()
    assert protected.read_bytes() == b"synthetic outside bytes stay unchanged"
    assert list(outside.iterdir()) == [protected]
    assert effects == []

    if case == "symlink":
        assert result["success"] is False and result["error"] == "compute_start_failed"
        assert tools == []
        assert events[-1]["payload"]["stage"] == "startup"
        verify_agentic_v2_failure_result(result)
        return

    assert len(tools) == 4
    assert tools[0]["request"]["arguments"] == root_arguments
    assert tools[0]["result"]["ok"] is True
    assert tools[0]["result"]["data"] == {"entries": []}
    assert tools[1]["result"]["ok"] is True
    assert tools[2]["request"]["arguments"] == root_arguments
    assert tools[2]["result"]["ok"] is True
    assert tools[2]["result"]["data"] == {"entries": ["report.txt"]}
    for index in (0, 2):
        assert tools[index]["result"]["state_before_sha256"] == tools[index]["result"]["state_after_sha256"]

    if case == "empty_then_written":
        assert result["success"] is True
        assert tools[-1]["request"]["name"] == "finalize"
        assert result["files"] == [{"filename": "report.txt", "content": content.encode()}]
        verifier = verify_agentic_v2_result
    else:
        expected_error = "invalid_arguments" if case == "traversal" else "path_not_directory"
        assert result["success"] is False and result["error"] == expected_error
        assert result["files"] == [] and result["text"] == result["deliverable_text"] == ""
        assert tools[-1]["request"]["call_id"] == "list-refused"
        assert tools[-1]["result"]["error_type"] == expected_error
        assert events[-1]["payload"]["stage"] == "runtime"
        # The trailing finalize must not turn a refused listing into a row.
        assert all(tool["request"]["name"] != "finalize" for tool in tools)
        verifier = verify_agentic_v2_failure_result
    verifier(result)
    forged = deepcopy(result)
    forged["agentic_v2"]["private_audit"]["events"][1]["payload"]["result"]["data"] = {"entries": ["invented"]}
    with pytest.raises(ValueError):
        verifier(forged)
