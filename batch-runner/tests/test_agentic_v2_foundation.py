from __future__ import annotations

from copy import deepcopy
import inspect
import json
import os
import socket
import subprocess
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import psutil
from jsonschema import Draft202012Validator

import step1_prepare_tasks as step1
import step2_run_inference as step2
import core.agentic_v2_provenance as agentic_v2_provenance
import core.agentic_v2_runner as agentic_v2_runner
from core.agentic_v2_contract import (
    EVENT_SCHEMA,
    TOOL_RESULT_SCHEMA,
    AgenticV2Lifecycle,
    AgenticV2Profile,
    LifecycleState,
)
from core.agentic_v2_fixture_backend import AgenticV2FixtureBackend
from core.agentic_v2_runner import (
    AgenticV2IsolatedFixtureRunner,
    AgenticV2ScriptedRunner,
)
from core.agentic_v2_provenance import (
    canonical_sha256,
    foundation_implementation_fingerprint,
    runtime_fingerprint,
    trace_pair_fingerprint,
    verify_agentic_v2_failure_result,
    verify_agentic_v2_metadata,
    verify_agentic_v2_result,
    verify_event_chain,
    verify_trace_pair,
)
from core.agentic_v2_tools import AgenticV2ToolDispatcher
from core.executor import TaskExecutor
from core.experiment_config import ExperimentConfig
from core.prepared_fingerprint import prepared_fingerprint
from core.source_identity import source_task_projection_sha256


PROFILE = {
    "tool_contract_version": "2.0",
    "policy_profile_id": "offline-full-v1",
    "foundation_only": True,
}


def _block_forever(*_args, **_kwargs):
    threading.Event().wait()


_DESCENDANT_PID_PATH = None


def _spawn_ignoring_descendant_and_block(*_args, **_kwargs):
    descendant = subprocess.Popen([
        sys.executable,
        "-c",
        (
            "import signal, threading; "
            "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
            "threading.Event().wait()"
        ),
    ])
    Path(_DESCENDANT_PID_PATH).write_text(
        str(descendant.pid), encoding="utf-8"
    )
    threading.Event().wait()


def _spawn_ignoring_descendant_and_return(_self, arguments):
    _spawn_ignoring_descendant()
    return {
        "ok": True,
        "data": {"kind": arguments["kind"], "items": ["fixture-upper"]},
    }


def _spawn_ignoring_descendant_and_crash(*_args, **_kwargs):
    _spawn_ignoring_descendant()
    os._exit(19)


def _spawn_ignoring_descendant():
    descendant = subprocess.Popen([
        sys.executable,
        "-c",
        (
            "import signal, threading; "
            "signal.signal(signal.SIGTERM, signal.SIG_IGN); "
            "threading.Event().wait()"
        ),
    ])
    Path(_DESCENDANT_PID_PATH).write_text(
        str(descendant.pid), encoding="utf-8"
    )
    return descendant


def _send_forged_success_and_wait(
    connection, _run_root, _calls, _profile, _budgets, _request
):
    os.setsid()
    connection.send({"kind": "ready", "process_group": os.getpgrp()})
    connection.send({"kind": "result", "result": {"success": True}})
    threading.Event().wait()


def _send_malformed_failure_and_exit(
    connection, _run_root, _calls, _profile, _budgets, _request
):
    os.setsid()
    connection.send({"kind": "ready", "process_group": os.getpgrp()})
    connection.send({"kind": "result", "result": {"success": False}})
    connection.close()


def _backend(tmp_path):
    return AgenticV2FixtureBackend(
        root=tmp_path,
        profile=AgenticV2Profile.from_mapping(PROFILE),
    )


def test_fixture_dispatcher_replays_identical_call_without_mutation(tmp_path):
    backend = _backend(tmp_path)
    lifecycle = AgenticV2Lifecycle(LifecycleState.ACTIVE)
    dispatcher = AgenticV2ToolDispatcher(backend, lifecycle)
    arguments = {
        "operation": "write",
        "path": "report.txt",
        "content": "hello",
    }

    first = dispatcher.dispatch(call_id="write-1", name="workspace_apply", arguments=arguments)
    state_after_first = backend.state_sha256()
    replay = dispatcher.dispatch(call_id="write-1", name="workspace_apply", arguments=arguments)

    assert first.result["ok"] is True
    assert replay.result == first.result
    assert replay.replayed is True
    assert backend.state_sha256() == state_after_first
    assert dispatcher.total_calls == 1


def test_fixture_dispatcher_replay_is_immutable_and_revalidated(tmp_path):
    backend = _backend(tmp_path)
    dispatcher = AgenticV2ToolDispatcher(
        backend, AgenticV2Lifecycle(LifecycleState.ACTIVE)
    )
    arguments = {"kind": "commands"}
    first = dispatcher.dispatch(
        call_id="cap-1", name="capabilities_query", arguments=arguments
    )
    expected = deepcopy(first.result)

    first.result["data"]["items"].append("caller-tamper")
    replay = dispatcher.dispatch(
        call_id="cap-1", name="capabilities_query", arguments=arguments
    )

    assert replay.result == expected
    dispatcher._cached_results["cap-1"].result["data"]["items"].append(
        "cache-tamper"
    )
    rejected = dispatcher.dispatch(
        call_id="cap-1", name="capabilities_query", arguments=arguments
    )
    assert rejected.result["error_type"] == "invalid_result_envelope"


def test_fixture_dispatcher_rejects_call_id_conflict(tmp_path):
    backend = _backend(tmp_path)
    dispatcher = AgenticV2ToolDispatcher(
        backend, AgenticV2Lifecycle(LifecycleState.ACTIVE)
    )
    dispatcher.dispatch(
        call_id="call-1",
        name="capabilities_query",
        arguments={"kind": "commands"},
    )

    conflict = dispatcher.dispatch(
        call_id="call-1",
        name="capabilities_query",
        arguments={"kind": "runtimes"},
    )

    assert conflict.result["error_type"] == "call_id_conflict"


@pytest.mark.parametrize(
    ("name", "arguments", "initial_error"),
    [
        ("unknown", {}, "unknown_tool"),
        ("capabilities_query", {"kind": "invalid"}, "invalid_arguments"),
    ],
)
def test_reused_call_id_prioritizes_exact_conflict_for_malformed_request(
    tmp_path, name, arguments, initial_error
):
    runner = AgenticV2ScriptedRunner(
        backend_factory=lambda **kwargs: AgenticV2FixtureBackend(
            root=tmp_path, **kwargs
        ),
        scripted_calls=[
            {
                "call_id": "call-1",
                "name": "capabilities_query",
                "arguments": {"kind": "commands"},
            },
            {"call_id": "call-1", "name": name, "arguments": arguments},
        ],
        profile=PROFILE,
    )

    result = runner.run("task", task_id="task-1")
    trace = result["agentic_v2"]["private_audit"]

    assert trace["events"][2]["payload"]["result"]["error_type"] == (
        "call_id_conflict"
    )
    verify_event_chain(trace["events"], trace["event_chain_head_sha256"])

    forged = deepcopy(trace["events"])
    envelope = forged[2]["payload"]["result"]
    envelope["error_type"] = initial_error
    _rehash_result(envelope)
    head = _rehash_events(forged)
    with pytest.raises(ValueError, match="replay history mismatch"):
        verify_event_chain(forged, head)


def test_fixture_dispatcher_rejects_replay_after_state_change(tmp_path):
    backend = _backend(tmp_path)
    dispatcher = AgenticV2ToolDispatcher(
        backend, AgenticV2Lifecycle(LifecycleState.ACTIVE)
    )
    first_arguments = {
        "operation": "write",
        "path": "report.txt",
        "content": "first",
    }
    dispatcher.dispatch(
        call_id="write-1",
        name="workspace_apply",
        arguments=first_arguments,
    )
    dispatcher.dispatch(
        call_id="write-2",
        name="workspace_apply",
        arguments={
            "operation": "write",
            "path": "report.txt",
            "content": "second",
        },
    )

    replay = dispatcher.dispatch(
        call_id="write-1",
        name="workspace_apply",
        arguments=first_arguments,
    )

    assert replay.replayed is False
    assert replay.result["error_type"] == "call_id_conflict"
    assert backend.workspace_apply({
        "operation": "read", "path": "report.txt"
    })["data"]["content"] == "second"


def test_fixture_package_resolution_is_pure_until_activation(tmp_path):
    backend = AgenticV2FixtureBackend(
        root=tmp_path,
        profile=AgenticV2Profile.from_mapping({
            "tool_contract_version": "2.0",
            "policy_profile_id": "package-broker-v1",
            "foundation_only": True,
        }),
    )
    dispatcher = AgenticV2ToolDispatcher(
        backend, AgenticV2Lifecycle(LifecycleState.ACTIVE)
    )
    before = backend.state_sha256()
    workspace_before = backend.workspace_state_sha256()

    resolved = dispatcher.dispatch(
        call_id="resolve-1",
        name="environment_resolve",
        arguments={"ecosystem": "python", "requirements": ["demo-pkg==1.0.0"]},
    )

    assert resolved.result["ok"] is True
    assert backend.state_sha256() == before
    lock_digest = resolved.result["data"]["lock_digest"]

    activated = dispatcher.dispatch(
        call_id="activate-1",
        name="environment_activate",
        arguments={"lock_digest": lock_digest},
    )

    assert activated.result["ok"] is True
    assert backend.workspace_state_sha256() == workspace_before
    assert activated.result["state_after_sha256"] != resolved.result[
        "state_after_sha256"
    ]


def test_fixture_package_lock_is_revalidated_at_activation(tmp_path):
    backend = AgenticV2FixtureBackend(
        root=tmp_path,
        profile=AgenticV2Profile.from_mapping({
            "tool_contract_version": "2.0",
            "policy_profile_id": "package-broker-v1",
            "foundation_only": True,
        }),
    )
    resolved = backend.environment_resolve({
        "ecosystem": "python", "requirements": ["demo-pkg==1.0.0"]
    })
    digest = resolved["data"]["lock_digest"]
    backend._locks[digest] = b'{"ecosystem":"python","requirements":[],"blobs":[]}'

    assert backend.environment_activate({"lock_digest": digest}) == {
        "ok": False,
        "error_type": "unapproved_lock",
    }
    with pytest.raises(TypeError):
        backend.package_catalog["python:other==1.0"] = "a" * 64


def test_offline_profile_rejects_package_resolution(tmp_path):
    backend = _backend(tmp_path)
    dispatcher = AgenticV2ToolDispatcher(
        backend, AgenticV2Lifecycle(LifecycleState.ACTIVE)
    )

    result = dispatcher.dispatch(
        call_id="resolve-1",
        name="environment_resolve",
        arguments={"ecosystem": "python", "requirements": ["demo-pkg==1.0.0"]},
    )

    assert result.result["ok"] is False
    assert result.result["error_type"] == "capability_unavailable"


def test_offline_fixture_browser_rejects_web_operations(tmp_path):
    backend = _backend(tmp_path)
    dispatcher = AgenticV2ToolDispatcher(
        backend, AgenticV2Lifecycle(LifecycleState.ACTIVE)
    )

    result = dispatcher.dispatch(
        call_id="web-1",
        name="browser_run",
        arguments={"operation": "search", "query": "benchmark answer"},
    )

    assert result.result["ok"] is False
    assert result.result["error_type"] == "capability_unavailable"


def test_fixture_rejects_symlink_and_hardlink_deliverables(tmp_path):
    backend = _backend(tmp_path)
    (backend.work / "real.txt").write_text("content", encoding="utf-8")
    (backend.work / "link.txt").symlink_to("real.txt")
    os.link(backend.work / "real.txt", backend.work / "hard.txt")

    for path in ("link.txt", "real.txt", "hard.txt"):
        result = backend.verify_public({"deliverables": [path]})
        assert result == {"ok": False, "error_type": "artifact_not_openable"}


@pytest.mark.parametrize("operation", ["read", "write", "copy", "exec", "browser"])
def test_fixture_rejects_hardlinks_across_all_io_paths(tmp_path, operation):
    backend = _backend(tmp_path)
    external = tmp_path / "external.txt"
    external.write_text("outside", encoding="utf-8")
    linked = backend.work / "linked.txt"
    os.link(external, linked)

    with pytest.raises(ValueError, match="single-link regular|unsafe entry"):
        if operation == "read":
            backend.workspace_apply({"operation": "read", "path": "linked.txt"})
        elif operation == "write":
            backend.workspace_apply({
                "operation": "write", "path": "linked.txt", "content": "changed"
            })
        elif operation == "copy":
            backend.workspace_apply({
                "operation": "copy",
                "source": "linked.txt",
                "destination": "copy.txt",
            })
        elif operation == "exec":
            backend.exec_run({
                "argv": ["fixture-upper", "linked.txt", "copy.txt"],
                "cwd": ".",
                "timeout_seconds": 30,
            })
        else:
            backend.browser_run({"operation": "open_local", "path": "linked.txt"})

    assert external.read_text(encoding="utf-8") == "outside"


def test_fixture_rejects_fifo_without_blocking(tmp_path):
    backend = _backend(tmp_path)
    fifo = backend.work / "pipe"
    os.mkfifo(fifo)

    with pytest.raises(ValueError, match="single-link regular"):
        backend.workspace_apply({"operation": "read", "path": "pipe"})


def test_fixture_rejects_socket_without_blocking(tmp_path):
    backend = _backend(tmp_path)
    socket_path = backend.work / "fixture.sock"
    fixture_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    fixture_socket.bind(str(socket_path))
    try:
        with pytest.raises((OSError, ValueError)):
            backend.workspace_apply({
                "operation": "read", "path": "fixture.sock"
            })
        with pytest.raises(ValueError, match="unsafe entry"):
            backend.state_sha256()
    finally:
        fixture_socket.close()


def test_fixture_parent_swap_cannot_redirect_read_outside_root(tmp_path):
    backend = _backend(tmp_path)
    inside = backend.work / "safe"
    inside.mkdir()
    (inside / "report.txt").write_text("inside", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "report.txt").write_text("outside", encoding="utf-8")
    original = backend._open_parent
    swapped = False

    def swap_after_open(relative, *, create=False):
        nonlocal swapped
        descriptor, name = original(relative, create=create)
        if not swapped:
            inside.rename(backend.work / "safe-detached")
            inside.symlink_to(outside, target_is_directory=True)
            swapped = True
        return descriptor, name

    backend._open_parent = swap_after_open

    assert backend.workspace_apply({
        "operation": "read", "path": "safe/report.txt"
    })["data"]["content"] == "inside"


def test_fixture_parent_move_outside_work_is_rejected_before_write(
    tmp_path, monkeypatch
):
    backend = _backend(tmp_path)
    parent = backend.work / "safe"
    parent.mkdir()
    (parent / "existing.txt").write_text("private", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    moved = outside / "moved-safe"
    original = backend._open_parent

    def move_after_open(relative, *, create=False):
        descriptor, name = original(relative, create=create)
        parent.rename(moved)
        return descriptor, name

    monkeypatch.setattr(backend, "_open_parent", move_after_open)

    with pytest.raises(ValueError, match="moved outside"):
        backend.workspace_apply({
            "operation": "write",
            "path": "safe/report.txt",
            "content": "must-not-escape",
        })

    assert list(moved.iterdir()) == []


def test_fixture_nested_ancestor_move_purges_siblings(tmp_path, monkeypatch):
    import core.agentic_v2_fixture_backend as fixture_backend

    backend = _backend(tmp_path)
    backend.workspace_apply({
        "operation": "write",
        "path": "outer/inner/report.txt",
        "content": "report",
    })
    backend.workspace_apply({
        "operation": "write",
        "path": "outer/sibling.txt",
        "content": "private",
    })
    outside = tmp_path / "outside"
    outside.mkdir()
    moved = outside / "moved-outer"
    original_open = fixture_backend.os.open
    raced = False

    def racing_open(path, flags, *args, **kwargs):
        nonlocal raced
        descriptor = original_open(path, flags, *args, **kwargs)
        if path == "inner" and not raced:
            (backend.work / "outer").rename(moved)
            raced = True
        return descriptor

    monkeypatch.setattr(fixture_backend.os, "open", racing_open)

    with pytest.raises(ValueError, match="moved outside"):
        backend.workspace_apply({
            "operation": "read", "path": "outer/inner/report.txt"
        })

    assert list(moved.iterdir()) == []


def test_fixture_snapshot_nested_move_purges_detached_ancestor(
    tmp_path, monkeypatch
):
    import core.agentic_v2_fixture_backend as fixture_backend

    backend = _backend(tmp_path)
    backend.workspace_apply({
        "operation": "write",
        "path": "outer/inner/report.txt",
        "content": "report",
    })
    backend.workspace_apply({
        "operation": "write",
        "path": "outer/sibling.txt",
        "content": "private",
    })
    outside = tmp_path / "outside-snapshot"
    outside.mkdir()
    moved = outside / "moved-outer"
    original_open = fixture_backend.os.open
    raced = False

    def racing_open(path, flags, *args, **kwargs):
        nonlocal raced
        descriptor = original_open(path, flags, *args, **kwargs)
        if path == "inner" and not raced:
            (backend.work / "outer").rename(moved)
            raced = True
        return descriptor

    monkeypatch.setattr(fixture_backend.os, "open", racing_open)

    with pytest.raises(ValueError, match="moved outside"):
        backend.state_sha256()

    assert list(moved.iterdir()) == []
    backend.close()
    assert list(moved.iterdir()) == []


def test_fixture_close_purges_pinned_root_after_lexical_move(tmp_path):
    backend = _backend(tmp_path)
    backend.workspace_apply({
        "operation": "write", "path": "report.txt", "content": "private"
    })
    moved = tmp_path / "moved-work"
    backend.work.rename(moved)

    backend.close()

    assert backend.closed is True
    assert moved.is_dir()
    assert list(moved.iterdir()) == []


def test_fixture_workspace_byte_limit_is_fail_closed(tmp_path, monkeypatch):
    import core.agentic_v2_fixture_backend as fixture_backend

    backend = _backend(tmp_path)
    monkeypatch.setattr(fixture_backend, "_MAX_WORKSPACE_BYTES", 4)

    with pytest.raises(ValueError, match="byte limit"):
        backend.workspace_apply({
            "operation": "write",
            "path": "report.txt",
            "content": "12345",
        })


def test_fixture_overwrite_reserves_peak_temporary_bytes(tmp_path, monkeypatch):
    import core.agentic_v2_fixture_backend as fixture_backend

    backend = _backend(tmp_path)
    monkeypatch.setattr(fixture_backend, "_MAX_WORKSPACE_BYTES", 6)
    backend.workspace_apply({
        "operation": "write", "path": "report.txt", "content": "1234"
    })
    backend.workspace_apply({
        "operation": "write", "path": "report.txt", "content": "12"
    })
    backend.workspace_apply({
        "operation": "write", "path": "report.txt", "content": "1234"
    })
    before = backend.state_sha256()

    with pytest.raises(ValueError, match="byte limit"):
        backend.workspace_apply({
            "operation": "write", "path": "report.txt", "content": "123"
        })

    assert backend.state_sha256() == before
    assert backend.workspace_apply({
        "operation": "read", "path": "report.txt"
    })["data"]["content"] == "1234"
    assert not any(path.name.endswith(".tmp") for path in backend.work.iterdir())


def test_fixture_individual_file_limit_rejects_without_mutation(
    tmp_path, monkeypatch
):
    import core.agentic_v2_fixture_backend as fixture_backend

    backend = _backend(tmp_path)
    monkeypatch.setattr(fixture_backend, "_MAX_FILE_BYTES", 4)
    before = backend.state_sha256()

    with pytest.raises(ValueError, match="write exceeds byte limit"):
        backend.workspace_apply({
            "operation": "write", "path": "report.txt", "content": "12345"
        })

    assert backend.state_sha256() == before
    assert list(backend.work.iterdir()) == []


def test_fixture_final_byte_limit_rejects_without_terminal_mutation(
    tmp_path, monkeypatch
):
    import core.agentic_v2_fixture_backend as fixture_backend

    backend = _backend(tmp_path)
    backend.workspace_apply({
        "operation": "write", "path": "one.txt", "content": "12"
    })
    backend.workspace_apply({
        "operation": "write", "path": "two.txt", "content": "34"
    })
    monkeypatch.setattr(fixture_backend, "_MAX_FINAL_BYTES", 3)
    before = backend.state_sha256()

    result = backend.finalize({
        "deliverables": ["one.txt", "two.txt"], "summary": "done"
    })

    assert result == {"ok": False, "error_type": "artifact_not_openable"}
    assert backend.best_result() is None
    assert backend.state_sha256() == before


def test_fixture_workspace_entry_limit_rejects_n_plus_one_without_mutation(
    tmp_path, monkeypatch
):
    import core.agentic_v2_fixture_backend as fixture_backend

    backend = _backend(tmp_path)
    monkeypatch.setattr(fixture_backend, "_MAX_WORKSPACE_ENTRIES", 1)
    backend.workspace_apply({
        "operation": "write", "path": "first.txt", "content": "1"
    })
    before = backend.state_sha256()

    with pytest.raises(ValueError, match="entry limit"):
        backend.workspace_apply({
            "operation": "write", "path": "second.txt", "content": "2"
        })

    assert backend.state_sha256() == before
    assert sorted(path.name for path in backend.work.iterdir()) == ["first.txt"]


def test_fixture_temporary_collision_retries_without_deleting_existing_file(
    tmp_path, monkeypatch
):
    import core.agentic_v2_fixture_backend as fixture_backend

    backend = _backend(tmp_path)
    collision = backend.work / ".agentic-v2-aaaaaaaaaaaaaaaa.tmp"
    collision.write_text("preserve", encoding="utf-8")
    tokens = iter(["a" * 16, "b" * 16])
    monkeypatch.setattr(
        fixture_backend.secrets,
        "token_hex",
        lambda _size: next(tokens),
    )

    backend.workspace_apply({
        "operation": "write", "path": "report.txt", "content": "done"
    })

    assert collision.read_text(encoding="utf-8") == "preserve"
    assert (backend.work / "report.txt").read_text(encoding="utf-8") == "done"


def test_fixture_temporary_collision_failure_preserves_state(
    tmp_path, monkeypatch
):
    import core.agentic_v2_fixture_backend as fixture_backend

    backend = _backend(tmp_path)
    collision = backend.work / ".agentic-v2-aaaaaaaaaaaaaaaa.tmp"
    collision.write_text("preserve", encoding="utf-8")
    monkeypatch.setattr(
        fixture_backend.secrets,
        "token_hex",
        lambda _size: "a" * 16,
    )
    before = backend.state_sha256()

    with pytest.raises(ValueError, match="temporary file allocation failed"):
        backend.workspace_apply({
            "operation": "write", "path": "report.txt", "content": "done"
        })

    assert backend.state_sha256() == before
    assert collision.read_text(encoding="utf-8") == "preserve"
    assert not (backend.work / "report.txt").exists()


def test_virtual_root_mkdir_reservation_is_noop_at_entry_limit():
    ledger = {
        "directories": {".", *{f"dir-{index}" for index in range(4096)}},
        "files": {},
    }

    assert agentic_v2_provenance._virtual_reserve_entries(
        ledger, ".", temporary_leaf=False
    ) is None


def test_fixture_directory_entry_limit_rejects_n_plus_one_without_mutation(
    tmp_path, monkeypatch
):
    import core.agentic_v2_fixture_backend as fixture_backend

    backend = _backend(tmp_path)
    monkeypatch.setattr(fixture_backend, "_MAX_DIRECTORY_ENTRIES", 1)
    backend.workspace_apply({
        "operation": "write", "path": "first.txt", "content": "1"
    })
    before = backend.state_sha256()

    with pytest.raises(ValueError, match="directory entry limit"):
        backend.workspace_apply({
            "operation": "write", "path": "second.txt", "content": "2"
        })

    assert backend.state_sha256() == before


def test_dispatcher_forbids_every_tool_after_finalize(tmp_path):
    backend = _backend(tmp_path)
    (backend.work / "report.txt").write_text("done", encoding="utf-8")
    lifecycle = AgenticV2Lifecycle(LifecycleState.ACTIVE)
    dispatcher = AgenticV2ToolDispatcher(backend, lifecycle)

    finalized = dispatcher.dispatch(
        call_id="final-1",
        name="finalize",
        arguments={"deliverables": ["report.txt"], "summary": "done"},
    )
    rejected = dispatcher.dispatch(
        call_id="read-after-final",
        name="capabilities_query",
        arguments={"kind": "commands"},
    )

    assert finalized.finalized is True
    assert lifecycle.state is LifecycleState.FINALIZED
    assert rejected.result["error_type"] == "tool_not_allowed_in_state"


def test_dispatcher_replays_finalize_after_terminal_state(tmp_path):
    backend = _backend(tmp_path)
    (backend.work / "report.txt").write_text("done", encoding="utf-8")
    dispatcher = AgenticV2ToolDispatcher(
        backend, AgenticV2Lifecycle(LifecycleState.ACTIVE)
    )
    arguments = {"deliverables": ["report.txt"], "summary": "done"}

    finalized = dispatcher.dispatch(
        call_id="final-1", name="finalize", arguments=arguments
    )
    replay = dispatcher.dispatch(
        call_id="final-1", name="finalize", arguments=arguments
    )

    assert finalized.finalized is True
    assert replay.finalized is True
    assert replay.replayed is True
    assert replay.result == finalized.result
    assert dispatcher.total_calls == 1


def test_finalize_envelope_failure_transitions_to_failed(tmp_path):
    backend = _backend(tmp_path)
    (backend.work / "report.txt").write_text("done", encoding="utf-8")
    lifecycle = AgenticV2Lifecycle(LifecycleState.ACTIVE)
    dispatcher = AgenticV2ToolDispatcher(
        backend, lifecycle, max_result_bytes=64
    )

    result = dispatcher.dispatch(
        call_id="final-1",
        name="finalize",
        arguments={"deliverables": ["report.txt"], "summary": "done"},
    )

    assert result.finalized is False
    assert result.result["error_type"] == "tool_result_too_large"
    assert result.result["request_sha256"] is not None
    assert result.result["usage_delta"]["tool_calls"] == 1
    assert result.result["usage_delta"]["output_bytes"] == 2
    assert result.result["state_before_sha256"] is not None
    assert result.result["state_after_sha256"] is not None
    assert lifecycle.state is LifecycleState.FAILED


def test_large_read_produces_verifiable_oversized_failure_trace(tmp_path):
    content = "x" * 70000
    result = AgenticV2ScriptedRunner(
        backend_factory=lambda **kwargs: AgenticV2FixtureBackend(
            root=tmp_path, **kwargs
        ),
        scripted_calls=[
            {
                "call_id": "write-1",
                "name": "workspace_apply",
                "arguments": {
                    "operation": "write",
                    "path": "large.txt",
                    "content": content,
                },
            },
            {
                "call_id": "read-1",
                "name": "workspace_apply",
                "arguments": {
                    "operation": "read",
                    "path": "large.txt",
                    "limit": len(content),
                },
            },
        ],
        profile=PROFILE,
    ).run("task", task_id="task-1")
    envelope = result["agentic_v2"]["private_audit"]["events"][2][
        "payload"
    ]["result"]

    assert result["success"] is False
    assert result["error"] == "tool_result_too_large"
    assert envelope["error_type"] == "tool_result_too_large"
    assert envelope["data"] == {}
    assert envelope["usage_delta"]["tool_calls"] == 1
    assert envelope["usage_delta"]["output_bytes"] == 2
    verify_agentic_v2_failure_result(result)


def test_trace_pair_rejects_oversized_wrapper_rewritten_as_success(tmp_path):
    content = "x" * 70000
    result = AgenticV2ScriptedRunner(
        backend_factory=lambda **kwargs: AgenticV2FixtureBackend(
            root=tmp_path, **kwargs
        ),
        scripted_calls=[
            {
                "call_id": "write-1",
                "name": "workspace_apply",
                "arguments": {
                    "operation": "write",
                    "path": "large.txt",
                    "content": content,
                },
            },
            {
                "call_id": "read-1",
                "name": "workspace_apply",
                "arguments": {
                    "operation": "read",
                    "path": "large.txt",
                    "limit": len(content),
                },
            },
        ],
        profile=PROFILE,
    ).run("task", task_id="task-1")
    metadata = deepcopy(result["agentic_v2"])
    data = {
        "content": content,
        "content_sha256": __import__("hashlib").sha256(
            content.encode("utf-8")
        ).hexdigest(),
    }
    _forge_success_event(
        metadata,
        2,
        call_id="read-1",
        tool_name="workspace_apply",
        arguments={
            "operation": "read",
            "path": "large.txt",
            "limit": len(content),
        },
        data=data,
    )
    _sync_failure_event(
        metadata,
        error_type="finalize_not_called",
        lifecycle_state="failed",
    )

    with pytest.raises(ValueError, match="fixture tool result mismatch"):
        verify_trace_pair(
            metadata["private_audit"],
            metadata["public_trace"],
            metadata["trace_pair_sha256"],
        )


def test_trace_pair_rejects_first_call_false_budget_exhaustion(tmp_path):
    result = _single_capability_run(tmp_path)
    metadata = deepcopy(result["agentic_v2"])
    envelope = metadata["private_audit"]["events"][1]["payload"]["result"]
    metadata["private_audit"]["events"][1]["payload"]["replayed"] = False
    metadata["private_audit"]["events"][1]["payload"]["result"] = (
        _unexecuted_error_from(envelope, "tool_budget_exhausted")
    )
    _sync_trace_pair_event(metadata, 1)
    _sync_failure_event(
        metadata,
        error_type="tool_budget_exhausted",
        lifecycle_state="failed",
    )

    with pytest.raises(ValueError, match="tool budget state mismatch"):
        verify_trace_pair(
            metadata["private_audit"],
            metadata["public_trace"],
            metadata["trace_pair_sha256"],
        )


def test_trace_pair_rejects_tool_after_exact_error(tmp_path):
    result = _successful_result(tmp_path)
    metadata = deepcopy(result["agentic_v2"])
    event = metadata["private_audit"]["events"][1]
    event["payload"]["request"] = {
        "call_id": "write-1",
        "name": "browser_run",
        "arguments": {"operation": "search", "query": "offline"},
    }
    envelope = event["payload"]["result"]
    envelope.update({
        "tool_name": "browser_run",
        "request_sha256": canonical_sha256({
            "tool_contract_version": "2.0",
            "call_id": "write-1",
            "name": "browser_run",
            "arguments": {"operation": "search", "query": "offline"},
        }),
        "ok": False,
        "error_type": "capability_unavailable",
        "data": {},
        "usage_delta": {"tool_calls": 1, "wall_ms": 0, "output_bytes": 2},
    })
    envelope["state_after_sha256"] = envelope["state_before_sha256"]
    event["state_sha256"] = envelope["state_after_sha256"]
    _rehash_result(envelope)
    _sync_trace_pair_event(metadata, 1)

    with pytest.raises(ValueError, match="tool event follows terminal result"):
        verify_trace_pair(
            metadata["private_audit"],
            metadata["public_trace"],
            metadata["trace_pair_sha256"],
        )


def test_trace_pair_rejects_tool_after_successful_finalize(tmp_path):
    result = _successful_result(tmp_path)
    metadata = deepcopy(result["agentic_v2"])
    final_state = metadata["private_audit"]["events"][-1]["state_sha256"]
    request = {
        "call_id": "after-final",
        "name": "capabilities_query",
        "arguments": {"kind": "commands"},
    }
    data = {"kind": "commands", "items": ["fixture-upper"]}
    envelope = _forged_result_envelope(
        request,
        data,
        state_before=final_state,
        state_after=final_state,
    )
    _append_trace_pair_tool_event(metadata, request, envelope)

    with pytest.raises(ValueError, match="tool event follows terminal result"):
        verify_trace_pair(
            metadata["private_audit"],
            metadata["public_trace"],
            metadata["trace_pair_sha256"],
        )


def test_trace_pair_rejects_failure_lifecycle_mismatch(tmp_path):
    result = _single_capability_run(tmp_path)
    metadata = deepcopy(result["agentic_v2"])
    _sync_failure_event(
        metadata,
        error_type="cancelled",
        lifecycle_state="failed",
        stage="control",
    )

    with pytest.raises(ValueError, match="failure lifecycle mismatch"):
        verify_trace_pair(
            metadata["private_audit"],
            metadata["public_trace"],
            metadata["trace_pair_sha256"],
        )


def test_failed_finalize_returns_to_active_before_retry(tmp_path):
    backend = _backend(tmp_path)
    lifecycle = AgenticV2Lifecycle(LifecycleState.ACTIVE)
    dispatcher = AgenticV2ToolDispatcher(backend, lifecycle)

    failed = dispatcher.dispatch(
        call_id="final-missing",
        name="finalize",
        arguments={"deliverables": ["report.txt"], "summary": "done"},
    )

    assert failed.result["error_type"] == "artifact_not_openable"
    assert lifecycle.state is LifecycleState.ACTIVE
    written = dispatcher.dispatch(
        call_id="write-1",
        name="workspace_apply",
        arguments={
            "operation": "write",
            "path": "report.txt",
            "content": "done",
        },
    )
    finalized = dispatcher.dispatch(
        call_id="final-valid",
        name="finalize",
        arguments={"deliverables": ["report.txt"], "summary": "done"},
    )
    assert written.result["ok"] is True
    assert finalized.finalized is True
    assert lifecycle.state is LifecycleState.FINALIZED


def test_finalize_rejects_terminal_bytes_that_do_not_match_artifacts(tmp_path):
    class MismatchedTerminalBackend(AgenticV2FixtureBackend):
        def best_result(self):
            result = dict(super().best_result())
            result["files"] = [{"filename": "report.txt", "content": b"tampered"}]
            return result

    backend = MismatchedTerminalBackend(
        root=tmp_path,
        profile=AgenticV2Profile.from_mapping(PROFILE),
    )
    backend.workspace_apply({
        "operation": "write", "path": "report.txt", "content": "done"
    })
    lifecycle = AgenticV2Lifecycle(LifecycleState.ACTIVE)
    result = AgenticV2ToolDispatcher(backend, lifecycle).dispatch(
        call_id="final-1",
        name="finalize",
        arguments={"deliverables": ["report.txt"], "summary": "done"},
    )

    assert result.finalized is False
    assert result.terminal_result is None
    assert result.result["error_type"] == "finalize_result_mismatch"
    assert lifecycle.state is LifecycleState.FAILED


def test_finalize_commit_followed_by_deadline_failure_is_terminal(tmp_path):
    clock = _ManualClock()

    class SlowFinalizeBackend(AgenticV2FixtureBackend):
        def finalize(self, arguments):
            result = super().finalize(arguments)
            clock.advance(2)
            return result

    backend = SlowFinalizeBackend(
        root=tmp_path,
        profile=AgenticV2Profile.from_mapping(PROFILE),
    )
    backend.workspace_apply({
        "operation": "write", "path": "report.txt", "content": "done"
    })
    lifecycle = AgenticV2Lifecycle(LifecycleState.ACTIVE)
    result = AgenticV2ToolDispatcher(
        backend,
        lifecycle,
        deadline=1,
        clock=clock,
    ).dispatch(
        call_id="final-1",
        name="finalize",
        arguments={"deliverables": ["report.txt"], "summary": "done"},
    )

    assert result.finalized is False
    assert result.terminal_result is None
    assert result.result["error_type"] == "task_wall_time_exhausted"
    assert lifecycle.state is LifecycleState.FAILED


def test_scripted_runner_completes_deterministically(tmp_path):
    calls = [
        {
            "call_id": "write-1",
            "name": "workspace_apply",
            "arguments": {
                "operation": "write",
                "path": "draft.txt",
                "content": "hello",
            },
        },
        {
            "call_id": "exec-1",
            "name": "exec_run",
            "arguments": {
                "argv": ["fixture-upper", "draft.txt", "report.txt"],
                "cwd": ".",
                "timeout_seconds": 30,
            },
        },
        {
            "call_id": "verify-1",
            "name": "verify_public",
            "arguments": {"deliverables": ["report.txt"]},
        },
        {
            "call_id": "final-1",
            "name": "finalize",
            "arguments": {"deliverables": ["report.txt"], "summary": "done"},
        },
    ]
    backends = []

    def factory(**kwargs):
        backend = AgenticV2FixtureBackend(root=tmp_path, **kwargs)
        backends.append(backend)
        return backend

    runner = AgenticV2ScriptedRunner(
        backend_factory=factory,
        scripted_calls=calls,
        profile=PROFILE,
    )

    result = runner.run("Create report", task_id="task-1")

    assert result["success"] is True
    assert result["files"][0]["content"] == b"HELLO"
    assert result["agentic_v2"]["schema_version"] == "2.0"
    assert result["agentic_v2"]["foundation_only"] is True
    for classification, key in (
        ("private", "private_audit"),
        ("public_redacted", "public_trace"),
    ):
        trace = result["agentic_v2"][key]
        assert trace["classification"] == classification
        assert len(trace["events"]) == 5
        assert all(
            not list(Draft202012Validator(EVENT_SCHEMA).iter_errors(event))
            for event in trace["events"]
        )
        verify_event_chain(
            trace["events"], trace["event_chain_head_sha256"]
        )
    verify_trace_pair(
        result["agentic_v2"]["private_audit"],
        result["agentic_v2"]["public_trace"],
        result["agentic_v2"]["trace_pair_sha256"],
    )
    assert backends[0].closed is True


def test_scripted_runner_public_trace_redacts_request_and_result_content(tmp_path):
    secret = "private-workspace-content"
    result = AgenticV2ScriptedRunner(
        backend_factory=lambda **kwargs: AgenticV2FixtureBackend(
            root=tmp_path, **kwargs
        ),
        scripted_calls=[
            {
                "call_id": "write-1",
                "name": "workspace_apply",
                "arguments": {
                    "operation": "write",
                    "path": "report.txt",
                    "content": secret,
                },
            },
            {
                "call_id": "read-1",
                "name": "workspace_apply",
                "arguments": {"operation": "read", "path": "report.txt"},
            },
            {
                "call_id": "final-1",
                "name": "finalize",
                "arguments": {
                    "deliverables": ["report.txt"],
                    "summary": "done",
                },
            },
        ],
        profile=PROFILE,
    ).run("task", task_id="task-1")

    assert secret not in str(result["agentic_v2"]["public_trace"])
    assert secret in str(result["agentic_v2"]["private_audit"])


def test_scripted_runner_rejects_advertised_capability_mismatch(tmp_path):
    class CapabilityMismatchBackend(AgenticV2FixtureBackend):
        def start(self, timeout_seconds):
            result = dict(super().start(timeout_seconds))
            result["data"] = deepcopy(result["data"])
            result["data"]["capabilities"]["commands"] = ["unexpected"]
            return result

    result = AgenticV2ScriptedRunner(
        backend_factory=lambda **kwargs: CapabilityMismatchBackend(
            root=tmp_path, **kwargs
        ),
        scripted_calls=[],
        profile=PROFILE,
    ).run("task", task_id="task-1")

    assert result["success"] is False
    assert result["error"] == "compute_start_failed"


def test_runtime_identity_is_sensitive_to_backend_and_capabilities():
    implementation = foundation_implementation_fingerprint()
    common = {
        "policy_profile_id": "offline-full-v1",
        "substrate_manifest_sha256": "1" * 64,
        "package_snapshot_sha256": "2" * 64,
        "browser_build_sha256": "3" * 64,
        "budget_caps": {"tool_calls": 32, "wall_seconds": 1200},
    }
    first = runtime_fingerprint(
        **common,
        backend_implementation_sha256=implementation,
        capabilities_sha256="4" * 64,
    )
    changed_backend = runtime_fingerprint(
        **common,
        backend_implementation_sha256="5" * 64,
        capabilities_sha256="4" * 64,
    )
    changed_capabilities = runtime_fingerprint(
        **common,
        backend_implementation_sha256=implementation,
        capabilities_sha256="6" * 64,
    )

    assert len({first, changed_backend, changed_capabilities}) == 3


def test_scripted_runner_two_cold_runs_have_same_public_identity(tmp_path):
    calls = [
        {
            "call_id": "write-1",
            "name": "workspace_apply",
            "arguments": {
                "operation": "write",
                "path": "report.txt",
                "content": "deterministic",
            },
        },
        {
            "call_id": "final-1",
            "name": "finalize",
            "arguments": {"deliverables": ["report.txt"], "summary": "done"},
        },
    ]

    def run(root):
        runner = AgenticV2ScriptedRunner(
            backend_factory=lambda **kwargs: AgenticV2FixtureBackend(
                root=root, **kwargs
            ),
            scripted_calls=calls,
            profile=PROFILE,
            clock=lambda: 0.0,
        )
        return runner.run("Create report", task_id="task-1")

    first = run(tmp_path / "first")
    second = run(tmp_path / "second")

    assert first["agentic_v2"]["runtime_fingerprint"] == second["agentic_v2"]["runtime_fingerprint"]
    assert first["agentic_v2"]["private_audit"][
        "event_chain_head_sha256"
    ] == second["agentic_v2"]["private_audit"]["event_chain_head_sha256"]
    assert first["agentic_v2"]["public_trace"][
        "event_chain_head_sha256"
    ] == second["agentic_v2"]["public_trace"]["event_chain_head_sha256"]
    assert first["files"] == second["files"]


def test_event_chain_detects_tool_result_tampering(tmp_path):
    runner = AgenticV2ScriptedRunner(
        backend_factory=lambda **kwargs: AgenticV2FixtureBackend(
            root=tmp_path, **kwargs
        ),
        scripted_calls=[
            {
                "call_id": "write-1",
                "name": "workspace_apply",
                "arguments": {
                    "operation": "write",
                    "path": "report.txt",
                    "content": "done",
                },
            },
            {
                "call_id": "final-1",
                "name": "finalize",
                "arguments": {"deliverables": ["report.txt"], "summary": "done"},
            },
        ],
        profile=PROFILE,
    )
    result = runner.run("task", task_id="task-1")
    trace = result["agentic_v2"]["private_audit"]
    events = deepcopy(trace["events"])
    events[1]["payload"]["result"]["usage_delta"]["wall_ms"] += 1
    head = _rehash_events(events)

    with pytest.raises(ValueError, match="tool result hash mismatch"):
        verify_event_chain(events, head)


def test_event_chain_detects_tool_request_tampering(tmp_path):
    result = AgenticV2ScriptedRunner(
        backend_factory=lambda **kwargs: AgenticV2FixtureBackend(
            root=tmp_path, **kwargs
        ),
        scripted_calls=[
            {
                "call_id": "write-1",
                "name": "workspace_apply",
                "arguments": {
                    "operation": "write",
                    "path": "report.txt",
                    "content": "original",
                },
            },
            {
                "call_id": "final-1",
                "name": "finalize",
                "arguments": {
                    "deliverables": ["report.txt"],
                    "summary": "done",
                },
            },
        ],
        profile=PROFILE,
    ).run("task", task_id="task-1")
    events = deepcopy(result["agentic_v2"]["private_audit"]["events"])
    events[1]["payload"]["request"]["arguments"]["content"] = "tampered"
    head = _rehash_events(events)

    with pytest.raises(ValueError, match="tool request hash mismatch"):
        verify_event_chain(events, head)


def test_trace_pair_detects_rehashed_public_commitment_tampering(tmp_path):
    result = AgenticV2ScriptedRunner(
        backend_factory=lambda **kwargs: AgenticV2FixtureBackend(
            root=tmp_path, **kwargs
        ),
        scripted_calls=[
            {
                "call_id": "write-1",
                "name": "workspace_apply",
                "arguments": {
                    "operation": "write",
                    "path": "report.txt",
                    "content": "done",
                },
            },
            {
                "call_id": "final-1",
                "name": "finalize",
                "arguments": {
                    "deliverables": ["report.txt"],
                    "summary": "done",
                },
            },
        ],
        profile=PROFILE,
    ).run("task", task_id="task-1")
    private_trace = result["agentic_v2"]["private_audit"]
    public_trace = deepcopy(result["agentic_v2"]["public_trace"])
    public_trace["events"][1]["payload"]["result_commitment"]["ok"] = False
    public_trace["event_chain_head_sha256"] = _rehash_events(
        public_trace["events"]
    )

    with pytest.raises(
        ValueError,
        match="trace pair commitment mismatch|tool event follows terminal result",
    ):
        verify_trace_pair(
            private_trace,
            public_trace,
            result["agentic_v2"]["trace_pair_sha256"],
        )


def test_event_chain_rejects_unknown_rehashed_kind(tmp_path):
    result = AgenticV2ScriptedRunner(
        backend_factory=lambda **kwargs: AgenticV2FixtureBackend(
            root=tmp_path, **kwargs
        ),
        scripted_calls=[
            {
                "call_id": "cap-1",
                "name": "capabilities_query",
                "arguments": {"kind": "commands"},
            },
        ],
        profile=PROFILE,
    ).run("task", task_id="task-1")
    events = deepcopy(result["agentic_v2"]["private_audit"]["events"])
    events[1]["kind"] = "unknown"
    head = _rehash_events(events)

    with pytest.raises(ValueError, match="event kind is invalid"):
        verify_event_chain(events, head)


def test_event_chain_rejects_first_call_replay_after_rehash(tmp_path):
    result = _single_capability_run(tmp_path)
    events = deepcopy(result["agentic_v2"]["private_audit"]["events"])
    events[1]["payload"]["replayed"] = True
    head = _rehash_events(events)

    with pytest.raises(ValueError, match="replay history mismatch"):
        verify_event_chain(events, head)


def test_event_chain_rejects_cleared_replay_bit_after_rehash(tmp_path):
    result = AgenticV2ScriptedRunner(
        backend_factory=lambda **kwargs: AgenticV2FixtureBackend(
            root=tmp_path, **kwargs
        ),
        scripted_calls=[
            {
                "call_id": "cap-1",
                "name": "capabilities_query",
                "arguments": {"kind": "commands"},
            },
            {
                "call_id": "cap-1",
                "name": "capabilities_query",
                "arguments": {"kind": "commands"},
            },
        ],
        profile=PROFILE,
    ).run("task", task_id="task-1")
    events = deepcopy(result["agentic_v2"]["private_audit"]["events"])
    events[2]["payload"]["replayed"] = False
    head = _rehash_events(events)

    with pytest.raises(ValueError, match="replay history mismatch"):
        verify_event_chain(events, head)


def test_event_chain_rejects_forged_conflict_for_exact_replay(tmp_path):
    result = AgenticV2ScriptedRunner(
        backend_factory=lambda **kwargs: AgenticV2FixtureBackend(
            root=tmp_path, **kwargs
        ),
        scripted_calls=[
            {
                "call_id": "cap-1",
                "name": "capabilities_query",
                "arguments": {"kind": "commands"},
            },
            {
                "call_id": "cap-1",
                "name": "capabilities_query",
                "arguments": {"kind": "commands"},
            },
        ],
        profile=PROFILE,
    ).run("task", task_id="task-1")
    events = deepcopy(result["agentic_v2"]["private_audit"]["events"])
    replay = events[2]["payload"]
    replay["replayed"] = False
    replay["result"] = _unexecuted_error_from(
        replay["result"], "call_id_conflict"
    )
    head = _rehash_events(events)

    with pytest.raises(ValueError, match="replay history mismatch"):
        verify_event_chain(events, head)


def test_event_chain_rejects_wrong_conflict_for_changed_request(tmp_path):
    result = AgenticV2ScriptedRunner(
        backend_factory=lambda **kwargs: AgenticV2FixtureBackend(
            root=tmp_path, **kwargs
        ),
        scripted_calls=[
            {
                "call_id": "cap-1",
                "name": "capabilities_query",
                "arguments": {"kind": "commands"},
            },
            {
                "call_id": "cap-1",
                "name": "capabilities_query",
                "arguments": {"kind": "runtimes"},
            },
        ],
        profile=PROFILE,
    ).run("task", task_id="task-1")
    events = deepcopy(result["agentic_v2"]["private_audit"]["events"])
    conflict = events[2]["payload"]["result"]
    conflict["error_type"] = "invalid_result_envelope"
    conflict.pop("result_sha256")
    conflict["result_sha256"] = canonical_sha256(conflict)
    head = _rehash_events(events)

    with pytest.raises(ValueError, match="replay history mismatch"):
        verify_event_chain(events, head)


def test_duplicate_call_state_drift_is_exact_conflict_and_verifies(tmp_path):
    result = AgenticV2ScriptedRunner(
        backend_factory=lambda **kwargs: AgenticV2FixtureBackend(
            root=tmp_path, **kwargs
        ),
        scripted_calls=[
            {
                "call_id": "cap-1",
                "name": "capabilities_query",
                "arguments": {"kind": "commands"},
            },
            {
                "call_id": "write-1",
                "name": "workspace_apply",
                "arguments": {
                    "operation": "write",
                    "path": "report.txt",
                    "content": "changed",
                },
            },
            {
                "call_id": "cap-1",
                "name": "capabilities_query",
                "arguments": {"kind": "commands"},
            },
        ],
        profile=PROFILE,
    ).run("task", task_id="task-1")
    trace = result["agentic_v2"]["private_audit"]

    assert trace["events"][3]["payload"]["result"]["error_type"] == (
        "call_id_conflict"
    )
    verify_event_chain(trace["events"], trace["event_chain_head_sha256"])


def test_event_chain_rejects_invalid_request_success_after_rehash(tmp_path):
    result = _single_capability_run(tmp_path)
    events = deepcopy(result["agentic_v2"]["private_audit"]["events"])
    event = events[1]
    event["payload"]["request"]["arguments"] = {"kind": "invalid"}
    envelope = event["payload"]["result"]
    envelope["request_sha256"] = None
    envelope.pop("result_sha256")
    envelope["result_sha256"] = canonical_sha256(envelope)
    head = _rehash_events(events)

    with pytest.raises(ValueError, match="invalid request result mismatch"):
        verify_event_chain(events, head)


@pytest.mark.parametrize(
    "tool_request",
    [
        {
            "call_id": "bad call",
            "name": "capabilities_query",
            "arguments": {"kind": "commands"},
        },
        {"call_id": "call-1", "name": "unknown", "arguments": {}},
        {
            "call_id": "call-1",
            "name": "capabilities_query",
            "arguments": {"kind": "invalid"},
        },
    ],
)
def test_event_chain_rejects_wrong_invalid_request_error_class(
    tmp_path, tool_request
):
    result = AgenticV2ScriptedRunner(
        backend_factory=lambda **kwargs: AgenticV2FixtureBackend(
            root=tmp_path, **kwargs
        ),
        scripted_calls=[tool_request],
        profile=PROFILE,
    ).run("task", task_id="task-1")
    events = deepcopy(result["agentic_v2"]["private_audit"]["events"])
    envelope = events[1]["payload"]["result"]
    envelope["error_type"] = "tool_budget_exhausted"
    envelope.pop("result_sha256")
    envelope["result_sha256"] = canonical_sha256(envelope)
    head = _rehash_events(events)

    with pytest.raises(ValueError, match="invalid request result mismatch"):
        verify_event_chain(events, head)


@pytest.mark.parametrize("mutation", ["backend", "profile", "capability"])
def test_event_chain_rejects_started_identity_tampering(tmp_path, mutation):
    result = _single_capability_run(tmp_path)
    events = deepcopy(result["agentic_v2"]["private_audit"]["events"])
    started = events[0]["payload"]
    if mutation == "backend":
        started["backend_identity"]["backend_id"] = "alternate"
    elif mutation == "profile":
        started["policy_profile_id"] = "unknown"
    else:
        started["capabilities"]["commands"] = ["unexpected"]
    head = _rehash_events(events)

    with pytest.raises(ValueError, match="started event is invalid"):
        verify_event_chain(events, head)


def test_success_metadata_recomputes_runtime_identity(tmp_path):
    result = AgenticV2ScriptedRunner(
        backend_factory=lambda **kwargs: AgenticV2FixtureBackend(
            root=tmp_path, **kwargs
        ),
        scripted_calls=[
            {
                "call_id": "write-1",
                "name": "workspace_apply",
                "arguments": {
                    "operation": "write",
                    "path": "report.txt",
                    "content": "done",
                },
            },
            {
                "call_id": "final-1",
                "name": "finalize",
                "arguments": {
                    "deliverables": ["report.txt"],
                    "summary": "done",
                },
            },
        ],
        profile=PROFILE,
    ).run("task", task_id="task-1")
    metadata = result["agentic_v2"]

    verify_agentic_v2_metadata(metadata)
    verify_agentic_v2_result(result)
    tampered = deepcopy(metadata)
    tampered["runtime_fingerprint"] = "f" * 64
    with pytest.raises(ValueError, match="runtime fingerprint mismatch"):
        verify_agentic_v2_metadata(tampered)


@pytest.mark.parametrize("mutation", ["substrate", "package_snapshot", "packages"])
def test_metadata_rejects_fully_rehashed_fixture_identity_tampering(
    tmp_path, mutation
):
    result = _successful_result(tmp_path)
    metadata = deepcopy(result["agentic_v2"])
    for trace_name in ("private_audit", "public_trace"):
        started = metadata[trace_name]["events"][0]["payload"]
        if mutation == "substrate":
            started["runtime"]["substrate_manifest_sha256"] = "f" * 64
        elif mutation == "package_snapshot":
            started["runtime"]["package_snapshot_sha256"] = "e" * 64
        else:
            started["capabilities"]["packages"] = ["python:other==1.0"]
        metadata[trace_name]["event_chain_head_sha256"] = _rehash_events(
            metadata[trace_name]["events"]
        )
    started = metadata["private_audit"]["events"][0]["payload"]
    metadata["capabilities_sha256"] = canonical_sha256(
        started["capabilities"]
    )
    runtime = started["runtime"]
    metadata["runtime_fingerprint"] = runtime_fingerprint(
        policy_profile_id=started["policy_profile_id"],
        substrate_manifest_sha256=runtime["substrate_manifest_sha256"],
        package_snapshot_sha256=runtime["package_snapshot_sha256"],
        browser_build_sha256=runtime["browser_build_sha256"],
        backend_implementation_sha256=started["backend_identity"][
            "implementation_sha256"
        ],
        capabilities_sha256=metadata["capabilities_sha256"],
        budget_caps=runtime["budget_caps"],
    )
    metadata["trace_pair_sha256"] = trace_pair_fingerprint(
        metadata["private_audit"], metadata["public_trace"]
    )

    with pytest.raises(
        ValueError,
        match="started event is invalid|canonical fixture identity mismatch",
    ):
        verify_agentic_v2_metadata(metadata)


def test_event_chain_rejects_forged_capability_inventory(tmp_path):
    result = _single_capability_run(tmp_path)
    events = deepcopy(result["agentic_v2"]["private_audit"]["events"])
    envelope = events[1]["payload"]["result"]
    envelope["data"]["items"] = ["unexpected"]
    _rehash_result(envelope)
    head = _rehash_events(events)

    with pytest.raises(
        ValueError,
        match="capability inventory mismatch|fixture tool result mismatch",
    ):
        verify_event_chain(events, head)


@pytest.mark.parametrize(
    ("tool_name", "arguments", "data"),
    [
        (
            "browser_run",
            {"operation": "search", "query": "must remain offline"},
            {"path": "forged.txt", "sha256": "f" * 64},
        ),
        (
            "exec_run",
            {
                "argv": ["unadvertised-command"],
                "cwd": ".",
                "timeout_seconds": 30,
            },
            {"returncode": 0},
        ),
    ],
)
def test_trace_pair_rejects_fully_rehashed_impossible_tool_success(
    tmp_path, tool_name, arguments, data
):
    result = _single_capability_run(tmp_path)
    metadata = deepcopy(result["agentic_v2"])
    event = metadata["private_audit"]["events"][1]
    event["payload"]["request"] = {
        "call_id": "cap-1",
        "name": tool_name,
        "arguments": arguments,
    }
    envelope = event["payload"]["result"]
    envelope.update({
        "tool_name": tool_name,
        "request_sha256": canonical_sha256({
            "tool_contract_version": "2.0",
            "call_id": "cap-1",
            "name": tool_name,
            "arguments": arguments,
        }),
        "ok": True,
        "error_type": None,
        "data": data,
    })
    _rehash_result(envelope)
    _sync_trace_pair_event(metadata, 1)

    with pytest.raises(ValueError, match="fixture tool result mismatch"):
        verify_trace_pair(
            metadata["private_audit"],
            metadata["public_trace"],
            metadata["trace_pair_sha256"],
        )


def test_trace_pair_rejects_fully_rehashed_forged_verification_artifact(
    tmp_path
):
    result = AgenticV2ScriptedRunner(
        backend_factory=lambda **kwargs: AgenticV2FixtureBackend(
            root=tmp_path, **kwargs
        ),
        scripted_calls=[
            {
                "call_id": "write-1",
                "name": "workspace_apply",
                "arguments": {
                    "operation": "write",
                    "path": "report.txt",
                    "content": "done",
                },
            },
            {
                "call_id": "verify-1",
                "name": "verify_public",
                "arguments": {"deliverables": ["report.txt"]},
            },
        ],
        profile=PROFILE,
    ).run("task", task_id="task-1")
    metadata = deepcopy(result["agentic_v2"])
    envelope = metadata["private_audit"]["events"][2]["payload"]["result"]
    envelope["data"]["artifacts"][0].update({
        "sha256": "f" * 64,
        "size": 999,
    })
    _rehash_result(envelope)
    _sync_trace_pair_event(metadata, 2)

    with pytest.raises(ValueError, match="fixture tool result mismatch"):
        verify_trace_pair(
            metadata["private_audit"],
            metadata["public_trace"],
            metadata["trace_pair_sha256"],
        )


@pytest.mark.parametrize(
    ("prefix_calls", "tool_name", "arguments", "data"),
    [
        (
            [],
            "workspace_apply",
            {"operation": "delete", "path": "."},
            {"path": "."},
        ),
        (
            [{
                "call_id": "mkdir-1",
                "name": "workspace_apply",
                "arguments": {"operation": "mkdir", "path": "target"},
            }],
            "workspace_apply",
            {"operation": "write", "path": "target", "content": "forged"},
            {"path": "target"},
        ),
        (
            [
                {
                    "call_id": "write-1",
                    "name": "workspace_apply",
                    "arguments": {
                        "operation": "write",
                        "path": "source.txt",
                        "content": "source",
                    },
                },
                {
                    "call_id": "mkdir-1",
                    "name": "workspace_apply",
                    "arguments": {"operation": "mkdir", "path": "target"},
                },
            ],
            "workspace_apply",
            {
                "operation": "copy",
                "source": "source.txt",
                "destination": "target",
            },
            {"path": "target"},
        ),
        (
            [
                {
                    "call_id": "write-1",
                    "name": "workspace_apply",
                    "arguments": {
                        "operation": "write",
                        "path": "source.txt",
                        "content": "source",
                    },
                },
                {
                    "call_id": "mkdir-1",
                    "name": "workspace_apply",
                    "arguments": {"operation": "mkdir", "path": "target"},
                },
            ],
            "exec_run",
            {
                "argv": ["fixture-upper", "source.txt", "target"],
                "cwd": ".",
                "timeout_seconds": 30,
            },
            {"returncode": 0},
        ),
    ],
)
def test_trace_pair_rejects_fully_rehashed_impossible_workspace_success(
    tmp_path, prefix_calls, tool_name, arguments, data
):
    calls = [
        *prefix_calls,
        {
            "call_id": "probe-1",
            "name": "capabilities_query",
            "arguments": {"kind": "commands"},
        },
    ]
    result = AgenticV2ScriptedRunner(
        backend_factory=lambda **kwargs: AgenticV2FixtureBackend(
            root=tmp_path, **kwargs
        ),
        scripted_calls=calls,
        profile=PROFILE,
    ).run("task", task_id="task-1")
    metadata = deepcopy(result["agentic_v2"])
    event_index = len(prefix_calls) + 1

    _forge_success_event(
        metadata,
        event_index,
        call_id="probe-1",
        tool_name=tool_name,
        arguments=arguments,
        data=data,
    )

    with pytest.raises(ValueError, match="fixture tool result mismatch"):
        verify_trace_pair(
            metadata["private_audit"],
            metadata["public_trace"],
            metadata["trace_pair_sha256"],
        )


@pytest.mark.parametrize("usage_field", ["output_bytes", "wall_ms"])
def test_trace_pair_rejects_fully_rehashed_usage_tampering(
    tmp_path, usage_field
):
    result = _single_capability_run(tmp_path)
    metadata = deepcopy(result["agentic_v2"])
    envelope = metadata["private_audit"]["events"][1]["payload"]["result"]
    envelope["usage_delta"][usage_field] += 1
    _rehash_result(envelope)
    _sync_trace_pair_event(metadata, 1)

    with pytest.raises(
        ValueError,
        match="result usage mismatch|fixture tool result mismatch",
    ):
        verify_trace_pair(
            metadata["private_audit"],
            metadata["public_trace"],
            metadata["trace_pair_sha256"],
        )


@pytest.mark.parametrize(
    "wrapper_error",
    [
        "tool_result_too_large",
        "invalid_result_envelope",
        "finalize_result_mismatch",
        "task_wall_time_exhausted",
    ],
)
def test_trace_pair_rejects_fully_rehashed_false_wrapper_error(
    tmp_path, wrapper_error
):
    result = _single_capability_run(tmp_path)
    metadata = deepcopy(result["agentic_v2"])
    envelope = metadata["private_audit"]["events"][1]["payload"]["result"]
    envelope["ok"] = False
    envelope["error_type"] = wrapper_error
    envelope["data"] = {}
    envelope["usage_delta"]["output_bytes"] = 2
    _rehash_result(envelope)
    _sync_trace_pair_event(metadata, 1)

    with pytest.raises(ValueError, match="wrapper condition mismatch"):
        verify_trace_pair(
            metadata["private_audit"],
            metadata["public_trace"],
            metadata["trace_pair_sha256"],
        )


def test_isolated_fixture_two_cold_runs_have_same_trace_identity(tmp_path):
    calls = [
        {
            "call_id": "write-1",
            "name": "workspace_apply",
            "arguments": {
                "operation": "write",
                "path": "report.txt",
                "content": "deterministic",
            },
        },
        {
            "call_id": "final-1",
            "name": "finalize",
            "arguments": {"deliverables": ["report.txt"], "summary": "done"},
        },
    ]

    def run(root):
        return AgenticV2IsolatedFixtureRunner(
            fixture_root=root,
            scripted_calls=calls,
            profile=PROFILE,
        ).run("task", task_id="task-1")

    first = run(tmp_path / "first")
    second = run(tmp_path / "second")

    assert first["success"] is True
    assert second["success"] is True
    assert first["files"] == second["files"]
    assert first["agentic_v2"] == second["agentic_v2"]


@pytest.mark.parametrize("filename", ["a" * 240, "é" * 120])
def test_isolated_fixture_accepts_exact_utf8_path_boundary(tmp_path, filename):
    result = AgenticV2IsolatedFixtureRunner(
        fixture_root=tmp_path,
        scripted_calls=[
            {
                "call_id": "write-1",
                "name": "workspace_apply",
                "arguments": {
                    "operation": "write",
                    "path": filename,
                    "content": "done",
                },
            },
            {
                "call_id": "final-1",
                "name": "finalize",
                "arguments": {"deliverables": [filename], "summary": "done"},
            },
        ],
        profile=PROFILE,
    ).run("task", task_id="task-1")

    assert result["success"] is True
    assert result["files"] == [{"filename": filename, "content": b"done"}]
    verify_agentic_v2_result(result)


@pytest.mark.parametrize(
    "destination",
    ["bad\x00name", "bad\u0085name", "x" * 241],
)
def test_isolated_fixture_rejects_noncanonical_exec_destination(
    tmp_path, destination
):
    result = AgenticV2IsolatedFixtureRunner(
        fixture_root=tmp_path,
        scripted_calls=[
            {
                "call_id": "write-1",
                "name": "workspace_apply",
                "arguments": {
                    "operation": "write",
                    "path": "source.txt",
                    "content": "source",
                },
            },
            {
                "call_id": "exec-1",
                "name": "exec_run",
                "arguments": {
                    "argv": ["fixture-upper", "source.txt", destination],
                    "cwd": ".",
                    "timeout_seconds": 30,
                },
            },
        ],
        profile=PROFILE,
    ).run("task", task_id="task-1")

    assert result["success"] is False
    assert result["error"] == "fixture_backend_error"
    verify_agentic_v2_failure_result(result)


def test_failure_verifier_rejects_rehashed_impossible_prestart_error(tmp_path):
    runner = AgenticV2ScriptedRunner(
        backend_factory=lambda **kwargs: (_ for _ in ()).throw(
            RuntimeError("private construction detail")
        ),
        scripted_calls=[],
        profile=PROFILE,
    )
    result = runner.run("task", task_id="task-1")
    tampered = deepcopy(result)
    tampered["error"] = "artifact_not_openable"
    metadata = tampered["agentic_v2"]
    _sync_failure_event(
        metadata,
        error_type="artifact_not_openable",
        lifecycle_state="failed",
        stage="runtime",
    )

    with pytest.raises(
        ValueError,
        match="pre-start failure stage mismatch|failure event is invalid",
    ):
        verify_agentic_v2_failure_result(tampered)


def test_event_chain_rejects_forged_workspace_content_hash(tmp_path):
    result = AgenticV2ScriptedRunner(
        backend_factory=lambda **kwargs: AgenticV2FixtureBackend(
            root=tmp_path, **kwargs
        ),
        scripted_calls=[
            {
                "call_id": "write-1",
                "name": "workspace_apply",
                "arguments": {
                    "operation": "write",
                    "path": "report.txt",
                    "content": "original",
                },
            },
            {
                "call_id": "read-1",
                "name": "workspace_apply",
                "arguments": {"operation": "read", "path": "report.txt"},
            },
        ],
        profile=PROFILE,
    ).run("task", task_id="task-1")
    events = deepcopy(result["agentic_v2"]["private_audit"]["events"])
    envelope = events[2]["payload"]["result"]
    envelope["data"]["content"] = "forged"
    _rehash_result(envelope)
    head = _rehash_events(events)

    with pytest.raises(ValueError, match="result data mismatch|content hash mismatch"):
        verify_event_chain(events, head)


def test_event_chain_rejects_forged_package_blob(tmp_path):
    profile = {
        "tool_contract_version": "2.0",
        "policy_profile_id": "package-broker-v1",
        "foundation_only": True,
    }
    result = AgenticV2ScriptedRunner(
        backend_factory=lambda **kwargs: AgenticV2FixtureBackend(
            root=tmp_path, **kwargs
        ),
        scripted_calls=[{
            "call_id": "resolve-1",
            "name": "environment_resolve",
            "arguments": {
                "ecosystem": "python",
                "requirements": ["demo-pkg==1.0.0"],
            },
        }],
        profile=profile,
    ).run("task", task_id="task-1")
    events = deepcopy(result["agentic_v2"]["private_audit"]["events"])
    envelope = events[1]["payload"]["result"]
    lock = envelope["data"]["lock"]
    lock["blobs"] = ["f" * 64]
    envelope["data"]["lock_digest"] = canonical_sha256(lock)
    _rehash_result(envelope)
    head = _rehash_events(events)

    with pytest.raises(
        ValueError,
        match="package lock mismatch|fixture tool result mismatch",
    ):
        verify_event_chain(events, head)


def test_event_chain_rejects_activation_without_prior_resolve(tmp_path):
    profile = {
        "tool_contract_version": "2.0",
        "policy_profile_id": "package-broker-v1",
        "foundation_only": True,
    }
    digest = canonical_sha256({
        "ecosystem": "python",
        "requirements": ["demo-pkg==1.0.0"],
        "blobs": ["d" * 64],
    })
    result = AgenticV2ScriptedRunner(
        backend_factory=lambda **kwargs: AgenticV2FixtureBackend(
            root=tmp_path, **kwargs
        ),
        scripted_calls=[{
            "call_id": "activate-1",
            "name": "environment_activate",
            "arguments": {"lock_digest": digest},
        }],
        profile=profile,
    ).run("task", task_id="task-1")
    events = deepcopy(result["agentic_v2"]["private_audit"]["events"])
    envelope = events[1]["payload"]["result"]
    envelope["ok"] = True
    envelope["error_type"] = None
    envelope["data"] = {"environment_id": digest}
    _rehash_result(envelope)
    head = _rehash_events(events)

    with pytest.raises(
        ValueError,
        match="package activation mismatch|fixture tool result mismatch",
    ):
        verify_event_chain(events, head)


def test_success_verifier_rejects_removed_finalize_pair(tmp_path):
    result = _successful_result(tmp_path)
    tampered = deepcopy(result)
    metadata = tampered["agentic_v2"]
    for trace_name in ("private_audit", "public_trace"):
        metadata[trace_name]["events"].pop()
        metadata[trace_name]["event_chain_head_sha256"] = _rehash_events(
            metadata[trace_name]["events"]
        )
    metadata["trace_pair_sha256"] = trace_pair_fingerprint(
        metadata["private_audit"], metadata["public_trace"]
    )

    with pytest.raises(
        ValueError,
        match="terminal finalize is missing|trace terminal state is invalid",
    ):
        verify_agentic_v2_result(tampered)


def test_success_verifier_rejects_terminal_file_byte_tampering(tmp_path):
    result = _successful_result(tmp_path)
    tampered = deepcopy(result)
    tampered["files"][0]["content"] = b"forged"

    with pytest.raises(ValueError, match="artifact bytes mismatch"):
        verify_agentic_v2_result(tampered)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("call_identity", "call identity mismatch"),
        ("status", "result status mismatch"),
        ("data", "result data mismatch"),
        ("state", "state continuity mismatch"),
    ],
)
def test_event_chain_rejects_rehashed_semantic_mismatch(
    tmp_path, mutation, message
):
    result = AgenticV2ScriptedRunner(
        backend_factory=lambda **kwargs: AgenticV2FixtureBackend(
            root=tmp_path, **kwargs
        ),
        scripted_calls=[
            {
                "call_id": "write-1",
                "name": "workspace_apply",
                "arguments": {
                    "operation": "write",
                    "path": "report.txt",
                    "content": "done",
                },
            },
            {
                "call_id": "final-1",
                "name": "finalize",
                "arguments": {
                    "deliverables": ["report.txt"],
                    "summary": "done",
                },
            },
        ],
        profile=PROFILE,
    ).run("task", task_id="task-1")
    events = deepcopy(result["agentic_v2"]["private_audit"]["events"])
    tool_event = events[1]
    envelope = tool_event["payload"]["result"]
    if mutation == "call_identity":
        envelope["call_id"] = "other-call"
    elif mutation == "status":
        envelope["error_type"] = "invalid_arguments"
    elif mutation == "data":
        envelope["data"]["path"] = "other.txt"
    else:
        tool_event["state_sha256"] = "f" * 64
    if mutation != "state":
        envelope.pop("result_sha256")
        envelope["result_sha256"] = canonical_sha256(envelope)
    head = _rehash_events(events)

    with pytest.raises(ValueError, match=message):
        verify_event_chain(events, head)


def test_backend_construction_and_startup_failures_have_verifiable_traces(
    tmp_path
):
    class StartFailureBackend(AgenticV2FixtureBackend):
        def start(self, timeout_seconds):
            del timeout_seconds
            raise RuntimeError("private startup detail")

    runners = [
        AgenticV2ScriptedRunner(
            backend_factory=lambda **kwargs: (_ for _ in ()).throw(
                RuntimeError("private construction detail")
            ),
            scripted_calls=[],
            profile=PROFILE,
        ),
        AgenticV2ScriptedRunner(
            backend_factory=lambda **kwargs: StartFailureBackend(
                root=tmp_path, **kwargs
            ),
            scripted_calls=[],
            profile=PROFILE,
        ),
    ]

    for runner in runners:
        result = runner.run("task", task_id="task-1")
        verify_trace_pair(
            result["agentic_v2"]["private_audit"],
            result["agentic_v2"]["public_trace"],
            result["agentic_v2"]["trace_pair_sha256"],
        )
        assert result["agentic_v2"]["private_audit"]["events"][-1][
            "kind"
        ] == "failure"


def test_startup_backend_error_is_normalized_to_canonical_stage(tmp_path):
    class RejectedStartBackend(AgenticV2FixtureBackend):
        def start(self, timeout_seconds):
            del timeout_seconds
            return {"ok": False, "error_type": "artifact_not_openable"}

    result = AgenticV2ScriptedRunner(
        backend_factory=lambda **kwargs: RejectedStartBackend(
            root=tmp_path, **kwargs
        ),
        scripted_calls=[],
        profile=PROFILE,
    ).run("task", task_id="task-1")
    failure = result["agentic_v2"]["private_audit"]["events"][-1]

    assert result["error"] == "compute_start_failed"
    assert failure["payload"] == {
        "error_type": "compute_start_failed",
        "lifecycle_state": "failed",
        "stage": "startup",
    }
    verify_agentic_v2_failure_result(result)


def test_failure_stage_error_map_is_disjoint_and_complete():
    stage_errors = agentic_v2_provenance._FAILURE_STAGE_ERRORS
    all_errors = set()
    for errors in stage_errors.values():
        assert all_errors.isdisjoint(errors)
        all_errors.update(errors)
    assert all_errors == set(agentic_v2_provenance.ERROR_TYPES)


def test_failure_verifier_rejects_backend_error_reclassified_as_control():
    result = agentic_v2_runner._failure(
        "compute_backend_error",
        AgenticV2Lifecycle(LifecycleState.FAILED),
        agentic_v2_provenance.AgenticV2EventChain(),
        agentic_v2_provenance.AgenticV2EventChain(),
        stage="backend",
    )
    tampered = deepcopy(result)
    _sync_failure_event(
        tampered["agentic_v2"],
        error_type="compute_backend_error",
        lifecycle_state="failed",
        stage="control",
    )

    with pytest.raises(ValueError, match="failure event is invalid"):
        verify_agentic_v2_failure_result(tampered)


def test_failure_verifier_rejects_cleanup_error_reclassified_as_runtime():
    result = agentic_v2_runner._failure(
        "compute_cleanup_failed",
        AgenticV2Lifecycle(LifecycleState.FAILED),
        agentic_v2_provenance.AgenticV2EventChain(),
        agentic_v2_provenance.AgenticV2EventChain(),
        stage="cleanup",
    )
    tampered = deepcopy(result)
    _sync_failure_event(
        tampered["agentic_v2"],
        error_type="compute_cleanup_failed",
        lifecycle_state="failed",
        stage="runtime",
    )

    with pytest.raises(ValueError, match="failure event is invalid"):
        verify_agentic_v2_failure_result(tampered)


def test_v2_config_requires_exact_profile_and_stays_nonpublishing():
    config = ExperimentConfig.from_dict({
        "experiment": {"id": "exp032_agentic_sandbox_v2_fixture", "name": "V2 fixture"},
        "data": {"source": "fixture/gdpval", "filter": {"task_ids": ["task-1"]}},
        "condition_a": {
            "name": "Fixture",
            "model": {"provider": "anthropic", "deployment": "unused-model"},
            "prompt": {"system": "system"},
        },
        "output": {"publish_to_hf": False, "submit_to_evals": False},
        "execution": {
            "mode": "agentic_sandbox_v2",
            "agentic_v2": PROFILE,
        },
    })

    assert config.validate() == []
    assert config.to_dict()["execution"]["agentic_v2"] == PROFILE

    config.execution.agentic_v2 = {"tool_contract_version": "1.0"}
    assert any("tool_contract_version" in error for error in config.validate())

    config.execution.mode = "subprocess"
    assert any("only valid" in error for error in config.validate())


def test_v2_executor_is_explicitly_model_free_and_dispatches_fixture(tmp_path):
    calls = [
        {
            "call_id": "write-1",
            "name": "workspace_apply",
            "arguments": {
                "operation": "write",
                "path": "report.txt",
                "content": "fixture",
            },
        },
        {
            "call_id": "final-1",
            "name": "finalize",
            "arguments": {"deliverables": ["report.txt"], "summary": "done"},
        },
    ]

    executor = TaskExecutor(
        mode="agentic_sandbox_v2",
        non_paid_test_mode=True,
        agentic_v2_options=PROFILE,
        agentic_v2_fixture_root=tmp_path,
        agentic_v2_scripted_calls=calls,
    )

    result = executor.execute(
        task_prompt="Create report",
        model="",
        run_id="fixture-run",
        condition_name="condition_a",
        task_id="task-1",
    )

    assert result["success"] is True
    assert result["files"][0]["content"] == b"fixture"

    rejected = executor.execute(
        task_prompt="Create report",
        model="real-model-name",
        task_id="task-1",
    )
    assert rejected["success"] is False
    assert "refuses model input" in rejected["error"]

    with pytest.raises(ValueError, match="model-free only"):
        TaskExecutor(
            mode="agentic_sandbox_v2",
            agentic_v2_options=PROFILE,
            agentic_v2_fixture_root=tmp_path,
            agentic_v2_scripted_calls=calls,
        )
    with pytest.raises(ValueError, match="rejects custom backend"):
        TaskExecutor(
            mode="agentic_sandbox_v2",
            non_paid_test_mode=True,
            agentic_v2_options=PROFILE,
            agentic_v2_fixture_root=tmp_path,
            agentic_v2_backend_factory=lambda **kwargs: object(),
            agentic_v2_scripted_calls=calls,
        )
    with pytest.raises(ValueError, match="refuses credential inputs"):
        TaskExecutor(
            mode="agentic_sandbox_v2",
            non_paid_test_mode=True,
            api_key="must-not-be-consumed",
            agentic_v2_options=PROFILE,
            agentic_v2_fixture_root=tmp_path,
            agentic_v2_scripted_calls=calls,
        )
    with pytest.raises(ValueError, match="refuses model inputs"):
        TaskExecutor(
            mode="agentic_sandbox_v2",
            non_paid_test_mode=True,
            model_name="must-not-be-consumed",
            agentic_v2_options=PROFILE,
            agentic_v2_fixture_root=tmp_path,
            agentic_v2_scripted_calls=calls,
        )


def test_step1_preserves_v2_public_profile(tmp_path, monkeypatch):
    config = ExperimentConfig.from_dict({
        "experiment": {"id": "exp032_agentic_sandbox_v2_fixture", "name": "V2 fixture"},
        "data": {"source": "fixture/gdpval", "filter": {"task_ids": ["task-1"]}},
        "condition_a": {
            "name": "Fixture",
            "model": {"provider": "azure", "deployment": "test-model"},
            "prompt": {"system": "system"},
        },
        "execution": {"mode": "agentic_sandbox_v2", "agentic_v2": PROFILE},
    })
    task = SimpleNamespace(
        task_id="task-1",
        sector="test",
        occupation="Analyst",
        prompt="Create report",
        rubric_pretty="rubric",
        rubric_json="{}",
        reference_files=[],
        reference_file_urls=[],
        reference_file_hf_uris=[],
    )
    projection = source_task_projection_sha256(
        task_id=task.task_id,
        sector=task.sector,
        occupation=task.occupation,
        prompt=task.prompt,
        rubric_pretty=task.rubric_pretty,
        rubric_json=task.rubric_json,
        reference_files=[],
        reference_file_urls=[],
        reference_file_hf_uris=[],
    )

    class Manifest:
        def require_schema(self, version):
            assert version == 4

        def source_projection_sha256(self, task_id):
            assert task_id == "task-1"
            return projection

        def reference_records(self, task_id, reference_files):
            return []

        def needs_files(self, task_id):
            return False

    monkeypatch.setattr(step1, "WORKSPACE_DIR", tmp_path)
    monkeypatch.setattr(step1.ExperimentConfig, "from_yaml", lambda path: config)
    monkeypatch.setattr(
        step1, "GDPValDataLoader", lambda auto_download=False: SimpleNamespace(
            load=lambda: [task]
        )
    )
    monkeypatch.setattr(
        step1.NeedsFilesManifest,
        "load",
        classmethod(lambda cls: Manifest()),
    )

    prepared = step1.prepare_tasks("fixture.yaml")

    assert prepared["execution"]["mode"] == "agentic_sandbox_v2"
    assert prepared["execution"]["agentic_v2"] == PROFILE


def test_step2_rejects_v2_before_provider_construction():
    with pytest.raises(ValueError, match="model-free.*scripted fixture"):
        step2._require_runnable_execution_mode("agentic_sandbox_v2")
    with pytest.raises(ValueError, match="model-free.*scripted fixture"):
        step2._resolve_runnable_execution_mode(
            "agentic_sandbox_v2", "subprocess"
        )
    with pytest.raises(ValueError, match="model-free.*scripted fixture"):
        step2._resolve_runnable_execution_mode(
            "subprocess", "agentic_sandbox_v2"
        )

    step2._require_runnable_execution_mode("agentic_sandbox")
    assert step2._resolve_runnable_execution_mode(
        "agentic_sandbox", None
    ) == "agentic_sandbox"

    source = inspect.getsource(step2._run_inference_impl)
    assert source.index("_resolve_runnable_execution_mode(") < (
        source.index("# 2. Create LLM client")
    )


def test_step2_configured_v2_override_constructs_no_provider_or_executor(
    tmp_path, monkeypatch
):
    task = {
        "task_id": "task-1",
        "reference_files": [],
        "reference_file_records": [],
        "needs_files": False,
        "source_projection_sha256": "a" * 64,
    }
    prepared = {
        "experiment_id": "exp-v2-fixture",
        "publication_generation": "generation-v2-fixture",
        "source": "fixture/gdpval",
        "execution": {"mode": "agentic_sandbox_v2"},
        "condition_a": {
            "name": "fixture",
            "model": {"provider": "azure", "deployment": "unused"},
            "prompt": {"system": "unused"},
        },
        "condition_b": None,
        "tasks": [task],
    }
    prepared["prepared_fingerprint"] = prepared_fingerprint(prepared)
    (tmp_path / "step1_tasks_prepared.json").write_text(
        json.dumps(prepared), encoding="utf-8"
    )

    class Manifest:
        def require_schema(self, version):
            assert version == 4

        def __contains__(self, task_id):
            return task_id == "task-1"

        def reference_records(self, task_id, reference_files):
            return []

        def needs_files(self, task_id):
            return False

        def source_projection_sha256(self, task_id):
            return "a" * 64

    provider = Mock()
    typed_factory = Mock()
    executor = Mock()
    monkeypatch.setattr(step2, "WORKSPACE_DIR", tmp_path)
    monkeypatch.setattr(
        step2.NeedsFilesManifest,
        "load",
        classmethod(lambda cls: Manifest()),
    )
    monkeypatch.setattr(step2, "resolve_verified_reference_paths", Mock())
    monkeypatch.setattr(step2, "create_provider_client", provider)
    monkeypatch.setattr(step2, "AzureAIClientFactory", typed_factory)
    monkeypatch.setattr(step2, "TaskExecutor", executor)

    with pytest.raises(SystemExit):
        step2._run_inference_impl(
            execution_mode="subprocess",
            runtime_resources=step2._Step2RuntimeResources(),
        )

    provider.assert_not_called()
    typed_factory.assert_not_called()
    executor.assert_not_called()


def test_dispatch_result_matches_strict_envelope(tmp_path):
    backend = _backend(tmp_path)
    dispatcher = AgenticV2ToolDispatcher(
        backend, AgenticV2Lifecycle(LifecycleState.ACTIVE)
    )

    dispatch = dispatcher.dispatch(
        call_id="cap-1",
        name="capabilities_query",
        arguments={"kind": "commands"},
    )

    assert not list(
        Draft202012Validator(TOOL_RESULT_SCHEMA).iter_errors(dispatch.result)
    )
    assert dispatch.result["result_sha256"]


def test_result_hash_commits_backend_data_even_when_state_is_equal(tmp_path):
    class AlternateCapabilitiesBackend(AgenticV2FixtureBackend):
        def capabilities_query(self, arguments):
            return {
                "ok": True,
                "data": {"kind": arguments["kind"], "items": ["alternate"]},
            }

    def dispatch(backend):
        return AgenticV2ToolDispatcher(
            backend, AgenticV2Lifecycle(LifecycleState.ACTIVE)
        ).dispatch(
            call_id="cap-1",
            name="capabilities_query",
            arguments={"kind": "commands"},
        )

    standard = dispatch(_backend(tmp_path / "standard"))
    alternate = dispatch(AlternateCapabilitiesBackend(
        root=tmp_path / "alternate",
        profile=AgenticV2Profile.from_mapping(PROFILE),
    ))

    assert standard.result["state_before_sha256"] == alternate.result[
        "state_before_sha256"
    ]
    assert standard.result["state_after_sha256"] == alternate.result[
        "state_after_sha256"
    ]
    assert standard.result["result_sha256"] != alternate.result["result_sha256"]


def test_scripted_runner_honors_control_plane_cancellation(tmp_path):
    backend = []

    def factory(**kwargs):
        value = AgenticV2FixtureBackend(root=tmp_path, **kwargs)
        backend.append(value)
        return value

    runner = AgenticV2ScriptedRunner(
        backend_factory=factory,
        scripted_calls=[{
            "call_id": "cap-1",
            "name": "capabilities_query",
            "arguments": {"kind": "commands"},
        }],
        profile=PROFILE,
        cancel_requested=lambda: True,
    )

    result = runner.run("task", task_id="task-1")

    assert result["success"] is False
    assert result["error"] == "cancelled"
    assert result["agentic_v2"]["lifecycle_state"] == "cancelled"
    assert backend[0].closed is True


def test_scripted_runner_honors_wall_time_before_tool_dispatch(tmp_path):
    ticks = iter([0.0, 2.0])
    runner = AgenticV2ScriptedRunner(
        backend_factory=lambda **kwargs: AgenticV2FixtureBackend(
            root=tmp_path, **kwargs
        ),
        scripted_calls=[{
            "call_id": "cap-1",
            "name": "capabilities_query",
            "arguments": {"kind": "commands"},
        }],
        profile=PROFILE,
        budget_caps={"tool_calls": 32, "wall_seconds": 1},
        clock=lambda: next(ticks),
    )

    result = runner.run("task", task_id="task-1")

    assert result["success"] is False
    assert result["error"] == "task_wall_time_exhausted"
    assert result["agentic_v2"]["lifecycle_state"] == "failed"


def test_scripted_runner_wall_expires_after_start_before_tool(tmp_path):
    ticks = iter([0.0, 0.0, 0.0, 2.0])
    runner = AgenticV2ScriptedRunner(
        backend_factory=lambda **kwargs: AgenticV2FixtureBackend(
            root=tmp_path, **kwargs
        ),
        scripted_calls=[{
            "call_id": "cap-1",
            "name": "capabilities_query",
            "arguments": {"kind": "commands"},
        }],
        profile=PROFILE,
        budget_caps={"tool_calls": 32, "wall_seconds": 1},
        clock=lambda: next(ticks),
    )

    result = runner.run("task", task_id="task-1")
    events = result["agentic_v2"]["private_audit"]["events"]

    assert result["error"] == "task_wall_time_exhausted"
    assert [event["kind"] for event in events] == ["started", "failure"]
    assert events[-1]["payload"]["stage"] == "control"
    verify_agentic_v2_failure_result(result)


def test_scripted_runner_wall_expires_inside_dispatch_boundary(tmp_path):
    ticks = iter([0.0, 0.0, 0.0, 0.0, 0.0, 2.0, 2.0])
    runner = AgenticV2ScriptedRunner(
        backend_factory=lambda **kwargs: AgenticV2FixtureBackend(
            root=tmp_path, **kwargs
        ),
        scripted_calls=[{
            "call_id": "cap-1",
            "name": "capabilities_query",
            "arguments": {"kind": "commands"},
        }],
        profile=PROFILE,
        budget_caps={"tool_calls": 32, "wall_seconds": 1},
        clock=lambda: next(ticks),
    )

    result = runner.run("task", task_id="task-1")
    events = result["agentic_v2"]["private_audit"]["events"]
    envelope = events[1]["payload"]["result"]

    assert result["error"] == "task_wall_time_exhausted"
    assert envelope["ok"] is True
    assert envelope["error_type"] is None
    assert events[-1]["payload"]["stage"] == "control"
    verify_agentic_v2_failure_result(result)


def test_dispatcher_records_real_wall_usage_for_executed_error(tmp_path):
    clock = _ManualClock()

    class TimedFailureBackend(AgenticV2FixtureBackend):
        def capabilities_query(self, arguments):
            del arguments
            clock.advance(0.125)
            raise RuntimeError("private backend detail")

    backend = TimedFailureBackend(
        root=tmp_path,
        profile=AgenticV2Profile.from_mapping(PROFILE),
    )
    result = AgenticV2ToolDispatcher(
        backend,
        AgenticV2Lifecycle(LifecycleState.ACTIVE),
        clock=clock,
    ).dispatch(
        call_id="cap-1",
        name="capabilities_query",
        arguments={"kind": "commands"},
    ).result

    assert result["error_type"] == "fixture_backend_error"
    assert result["usage_delta"] == {
        "tool_calls": 1,
        "wall_ms": 125,
        "output_bytes": 2,
    }
    assert result["request_sha256"] is not None
    assert result["state_before_sha256"] is not None
    assert result["state_after_sha256"] is not None


def test_scripted_runner_enforces_startup_deadline(tmp_path):
    clock = _ManualClock()
    backends = []

    class SlowStartBackend(AgenticV2FixtureBackend):
        def start(self, timeout_seconds):
            assert timeout_seconds == 1
            clock.advance(2)
            return super().start(timeout_seconds)

    def factory(**kwargs):
        backend = SlowStartBackend(root=tmp_path, **kwargs)
        backends.append(backend)
        return backend

    result = AgenticV2ScriptedRunner(
        backend_factory=factory,
        scripted_calls=[],
        profile=PROFILE,
        budget_caps={"tool_calls": 32, "wall_seconds": 1},
        clock=clock,
    ).run("task", task_id="task-1")

    assert result["error"] == "task_wall_time_exhausted"
    assert result["agentic_v2"]["lifecycle_state"] == "failed"
    assert backends[0].closed is True


def test_scripted_runner_enforces_tool_deadline_after_execution(tmp_path):
    clock = _ManualClock()

    class SlowToolBackend(AgenticV2FixtureBackend):
        def capabilities_query(self, arguments):
            clock.advance(2)
            return super().capabilities_query(arguments)

    result = AgenticV2ScriptedRunner(
        backend_factory=lambda **kwargs: SlowToolBackend(
            root=tmp_path, **kwargs
        ),
        scripted_calls=[{
            "call_id": "cap-1",
            "name": "capabilities_query",
            "arguments": {"kind": "commands"},
        }],
        profile=PROFILE,
        budget_caps={"tool_calls": 32, "wall_seconds": 1},
        clock=clock,
    ).run("task", task_id="task-1")

    envelope = result["agentic_v2"]["private_audit"]["events"][1][
        "payload"
    ]["result"]
    assert result["error"] == "task_wall_time_exhausted"
    assert result["agentic_v2"]["lifecycle_state"] == "failed"
    assert envelope["ok"] is True
    assert envelope["error_type"] is None
    assert envelope["usage_delta"]["wall_ms"] == 0
    assert envelope["usage_delta"]["tool_calls"] == 1
    verify_agentic_v2_failure_result(result)


@pytest.mark.parametrize("blocked_stage", ["start", "tool"])
def test_isolated_fixture_hard_deadline_kills_blocked_worker(
    tmp_path, monkeypatch, blocked_stage
):
    if blocked_stage == "start":
        monkeypatch.setattr(AgenticV2FixtureBackend, "start", _block_forever)
        calls = []
    else:
        monkeypatch.setattr(
            AgenticV2FixtureBackend, "capabilities_query", _block_forever
        )
        calls = [{
            "call_id": "cap-1",
            "name": "capabilities_query",
            "arguments": {"kind": "commands"},
        }]
    runner = AgenticV2IsolatedFixtureRunner(
        fixture_root=tmp_path,
        scripted_calls=calls,
        profile=PROFILE,
        budget_caps={"tool_calls": 32, "wall_seconds": 1},
    )

    result = runner.run("task", task_id="task-1")

    assert result["success"] is False
    assert result["error"] == "task_wall_time_exhausted"
    assert runner._last_process.exitcode is not None
    assert runner._last_process.is_alive() is False
    assert list(tmp_path.glob(".agentic-v2-run-*")) == []
    verify_trace_pair(
        result["agentic_v2"]["private_audit"],
        result["agentic_v2"]["public_trace"],
        result["agentic_v2"]["trace_pair_sha256"],
    )


def test_isolated_fixture_hard_deadline_kills_ignoring_descendant(
    tmp_path, monkeypatch
):
    global _DESCENDANT_PID_PATH
    _DESCENDANT_PID_PATH = tmp_path / "descendant.pid"
    monkeypatch.setattr(
        AgenticV2FixtureBackend,
        "capabilities_query",
        _spawn_ignoring_descendant_and_block,
    )
    runner = AgenticV2IsolatedFixtureRunner(
        fixture_root=tmp_path,
        scripted_calls=[{
            "call_id": "cap-1",
            "name": "capabilities_query",
            "arguments": {"kind": "commands"},
        }],
        profile=PROFILE,
        budget_caps={"tool_calls": 32, "wall_seconds": 1},
    )

    result = runner.run("task", task_id="task-1")
    descendant_pid = int(Path(_DESCENDANT_PID_PATH).read_text(encoding="utf-8"))

    assert result["error"] == "task_wall_time_exhausted"
    assert runner._last_process.is_alive() is False
    try:
        descendant = psutil.Process(descendant_pid)
    except psutil.NoSuchProcess:
        descendant = None
    if descendant is not None:
        gone, alive = psutil.wait_procs([descendant], timeout=1)
        assert gone
        assert alive == []
    assert list(tmp_path.glob(".agentic-v2-run-*")) == []


@pytest.mark.parametrize(
    ("backend_method", "expected_error"),
    [
        (_spawn_ignoring_descendant_and_return, "finalize_not_called"),
        (_spawn_ignoring_descendant_and_crash, "compute_backend_error"),
    ],
)
def test_isolated_fixture_always_kills_descendant_after_worker_exit(
    tmp_path, monkeypatch, backend_method, expected_error
):
    global _DESCENDANT_PID_PATH
    _DESCENDANT_PID_PATH = tmp_path / "descendant.pid"
    monkeypatch.setattr(
        AgenticV2FixtureBackend,
        "capabilities_query",
        backend_method,
    )
    runner = AgenticV2IsolatedFixtureRunner(
        fixture_root=tmp_path,
        scripted_calls=[{
            "call_id": "cap-1",
            "name": "capabilities_query",
            "arguments": {"kind": "commands"},
        }],
        profile=PROFILE,
        budget_caps={"tool_calls": 32, "wall_seconds": 3},
    )

    result = runner.run("task", task_id="task-1")
    descendant_pid = int(Path(_DESCENDANT_PID_PATH).read_text(encoding="utf-8"))

    assert result["error"] == expected_error
    assert runner._last_process.is_alive() is False
    try:
        descendant = psutil.Process(descendant_pid)
    except psutil.NoSuchProcess:
        descendant = None
    if descendant is not None:
        gone, alive = psutil.wait_procs([descendant], timeout=1)
        assert gone
        assert alive == []
    assert list(tmp_path.glob(".agentic-v2-run-*")) == []


def test_isolated_fixture_discards_success_when_parent_verifier_type_errors(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        agentic_v2_runner,
        "_run_fixture_worker",
        _send_forged_success_and_wait,
    )
    monkeypatch.setattr(
        agentic_v2_runner,
        "verify_agentic_v2_result",
        lambda _value: (_ for _ in ()).throw(TypeError("forged bytes")),
    )
    runner = AgenticV2IsolatedFixtureRunner(
        fixture_root=tmp_path,
        scripted_calls=[],
        profile=PROFILE,
        budget_caps={"tool_calls": 32, "wall_seconds": 3},
    )

    result = runner.run("task", task_id="task-1")

    assert result["success"] is False
    assert result["error"] == "compute_backend_error"
    assert runner._last_process.is_alive() is False
    verify_agentic_v2_failure_result(result)


def test_isolated_fixture_discards_malformed_failure_after_worker_exit(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        agentic_v2_runner,
        "_run_fixture_worker",
        _send_malformed_failure_and_exit,
    )
    runner = AgenticV2IsolatedFixtureRunner(
        fixture_root=tmp_path,
        scripted_calls=[],
        profile=PROFILE,
        budget_caps={"tool_calls": 32, "wall_seconds": 3},
    )

    result = runner.run("task", task_id="task-1")

    assert result["success"] is False
    assert result["error"] == "compute_backend_error"
    assert runner._last_process.is_alive() is False
    verify_agentic_v2_failure_result(result)


def test_scripted_runner_cleanup_failure_overrides_success(tmp_path):
    class CleanupFailureBackend(AgenticV2FixtureBackend):
        def close(self):
            raise RuntimeError("sensitive cleanup detail")

    runner = AgenticV2ScriptedRunner(
        backend_factory=lambda **kwargs: CleanupFailureBackend(
            root=tmp_path, **kwargs
        ),
        scripted_calls=[
            {
                "call_id": "write-1",
                "name": "workspace_apply",
                "arguments": {
                    "operation": "write",
                    "path": "report.txt",
                    "content": "done",
                },
            },
            {
                "call_id": "final-1",
                "name": "finalize",
                "arguments": {"deliverables": ["report.txt"], "summary": "done"},
            },
        ],
        profile=PROFILE,
    )

    result = runner.run("task", task_id="task-1")

    assert result["success"] is False
    assert result["error"] == "compute_cleanup_failed"
    assert "sensitive" not in str(result)


def test_scripted_runner_cleanup_failure_preserves_prior_error(tmp_path):
    class CleanupFailureBackend(AgenticV2FixtureBackend):
        def close(self):
            raise RuntimeError("sensitive cleanup detail")

    result = AgenticV2ScriptedRunner(
        backend_factory=lambda **kwargs: CleanupFailureBackend(
            root=tmp_path, **kwargs
        ),
        scripted_calls=[{
            "call_id": "resolve-1",
            "name": "environment_resolve",
            "arguments": {
                "ecosystem": "python",
                "requirements": ["demo-pkg==1.0.0"],
            },
        }],
        profile=PROFILE,
    ).run("task", task_id="task-1")

    assert result["error"] == "capability_unavailable"
    assert "cleanup" not in str(result)


@pytest.mark.parametrize(
    "budget_caps",
    [
        {"tool_calls": 0},
        {"wall_seconds": 0},
        {"tool_calls": True},
        {"unknown": 1},
    ],
)
def test_scripted_runner_rejects_invalid_budget_caps(tmp_path, budget_caps):
    with pytest.raises(ValueError, match="budget cap|tool_calls|wall_seconds"):
        AgenticV2ScriptedRunner(
            backend_factory=lambda **kwargs: AgenticV2FixtureBackend(
                root=tmp_path, **kwargs
            ),
            scripted_calls=[],
            profile=PROFILE,
            budget_caps=budget_caps,
        )


@pytest.mark.parametrize(
    ("profile_id", "package_ok", "web_ok"),
    [
        ("offline-full-v1", False, False),
        ("package-broker-v1", True, False),
        ("web-augmented-v1", True, False),
    ],
)
def test_fixture_profile_matrix(tmp_path, profile_id, package_ok, web_ok):
    backend = AgenticV2FixtureBackend(
        root=tmp_path / profile_id,
        profile=AgenticV2Profile.from_mapping({
            "tool_contract_version": "2.0",
            "policy_profile_id": profile_id,
            "foundation_only": True,
        }),
    )
    package = backend.environment_resolve({
        "ecosystem": "python", "requirements": ["demo-pkg==1.0.0"]
    })
    web = backend.browser_run({"operation": "search", "query": "query"})

    assert package["ok"] is package_ok
    assert web["ok"] is web_ok


class _ManualClock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


def _rehash_events(events):
    previous = "0" * 64
    for sequence, event in enumerate(events):
        event["sequence"] = sequence
        event["previous_sha256"] = previous
        event.pop("event_sha256", None)
        event["event_sha256"] = canonical_sha256(event)
        previous = event["event_sha256"]
    return previous


def _single_capability_run(tmp_path):
    return AgenticV2ScriptedRunner(
        backend_factory=lambda **kwargs: AgenticV2FixtureBackend(
            root=tmp_path, **kwargs
        ),
        scripted_calls=[{
            "call_id": "cap-1",
            "name": "capabilities_query",
            "arguments": {"kind": "commands"},
        }],
        profile=PROFILE,
    ).run("task", task_id="task-1")


def _successful_result(tmp_path):
    return AgenticV2ScriptedRunner(
        backend_factory=lambda **kwargs: AgenticV2FixtureBackend(
            root=tmp_path, **kwargs
        ),
        scripted_calls=[
            {
                "call_id": "write-1",
                "name": "workspace_apply",
                "arguments": {
                    "operation": "write",
                    "path": "report.txt",
                    "content": "done",
                },
            },
            {
                "call_id": "final-1",
                "name": "finalize",
                "arguments": {
                    "deliverables": ["report.txt"],
                    "summary": "done",
                },
            },
        ],
        profile=PROFILE,
    ).run("task", task_id="task-1")


def _rehash_result(envelope):
    envelope.pop("result_sha256", None)
    envelope["result_sha256"] = canonical_sha256(envelope)


def _unexecuted_error_from(envelope, error_type):
    value = {
        "schema_version": envelope["schema_version"],
        "call_id": envelope["call_id"],
        "tool_name": envelope["tool_name"],
        "request_sha256": None,
        "ok": False,
        "error_type": error_type,
        "data": {},
        "usage_delta": {"tool_calls": 0, "wall_ms": 0, "output_bytes": 0},
        "state_before_sha256": None,
        "state_after_sha256": None,
    }
    value["result_sha256"] = canonical_sha256(value)
    return value


def _sync_trace_pair_event(metadata, event_index):
    private_event = metadata["private_audit"]["events"][event_index]
    public_event = metadata["public_trace"]["events"][event_index]
    envelope = private_event["payload"]["result"]
    public_event["payload"] = {
        "result_commitment": {
            field: deepcopy(envelope.get(field))
            for field in (
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
        },
        "replayed": private_event["payload"]["replayed"],
    }
    public_event["state_sha256"] = private_event["state_sha256"]
    metadata["private_audit"]["event_chain_head_sha256"] = _rehash_events(
        metadata["private_audit"]["events"]
    )
    metadata["public_trace"]["event_chain_head_sha256"] = _rehash_events(
        metadata["public_trace"]["events"]
    )
    metadata["trace_pair_sha256"] = trace_pair_fingerprint(
        metadata["private_audit"], metadata["public_trace"]
    )


def _forge_success_event(
    metadata,
    event_index,
    *,
    call_id,
    tool_name,
    arguments,
    data,
):
    event = metadata["private_audit"]["events"][event_index]
    event["payload"]["request"] = {
        "call_id": call_id,
        "name": tool_name,
        "arguments": arguments,
    }
    envelope = event["payload"]["result"]
    envelope.update({
        "call_id": call_id,
        "tool_name": tool_name,
        "request_sha256": canonical_sha256({
            "tool_contract_version": "2.0",
            "call_id": call_id,
            "name": tool_name,
            "arguments": arguments,
        }),
        "ok": True,
        "error_type": None,
        "data": data,
    })
    envelope["usage_delta"] = {
        "tool_calls": 1,
        "wall_ms": 0,
        "output_bytes": len(json.dumps(
            data,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")),
    }
    _rehash_result(envelope)
    _sync_trace_pair_event(metadata, event_index)


def _sync_failure_event(
    metadata,
    *,
    error_type,
    lifecycle_state,
    stage="runtime",
):
    payload = {
        "error_type": error_type,
        "lifecycle_state": lifecycle_state,
        "stage": stage,
    }
    state = canonical_sha256({"schema_version": "2.0", **payload})
    for trace_name in ("private_audit", "public_trace"):
        event = metadata[trace_name]["events"][-1]
        assert event["kind"] == "failure"
        event["payload"] = deepcopy(payload)
        event["state_sha256"] = state
        metadata[trace_name]["event_chain_head_sha256"] = _rehash_events(
            metadata[trace_name]["events"]
        )
    metadata["trace_pair_sha256"] = trace_pair_fingerprint(
        metadata["private_audit"], metadata["public_trace"]
    )


def _forged_result_envelope(request, data, *, state_before, state_after):
    value = {
        "schema_version": "2.0",
        "call_id": request["call_id"],
        "tool_name": request["name"],
        "request_sha256": canonical_sha256({
            "tool_contract_version": "2.0",
            "call_id": request["call_id"],
            "name": request["name"],
            "arguments": request["arguments"],
        }),
        "ok": True,
        "error_type": None,
        "data": deepcopy(data),
        "usage_delta": {
            "tool_calls": 1,
            "wall_ms": 0,
            "output_bytes": len(json.dumps(
                data,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")),
        },
        "state_before_sha256": state_before,
        "state_after_sha256": state_after,
    }
    value["result_sha256"] = canonical_sha256(value)
    return value


def _append_trace_pair_tool_event(metadata, request, envelope):
    private_events = metadata["private_audit"]["events"]
    public_events = metadata["public_trace"]["events"]
    private_events.append({
        "schema_version": "2.0",
        "sequence": len(private_events),
        "kind": "tool_result",
        "payload": {
            "request": deepcopy(request),
            "result": deepcopy(envelope),
            "replayed": False,
        },
        "state_sha256": envelope["state_after_sha256"],
        "previous_sha256": private_events[-1]["event_sha256"],
        "event_sha256": "0" * 64,
    })
    public_events.append({
        "schema_version": "2.0",
        "sequence": len(public_events),
        "kind": "tool_result_public",
        "payload": {
            "result_commitment": {
                field: deepcopy(envelope.get(field))
                for field in (
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
            },
            "replayed": False,
        },
        "state_sha256": envelope["state_after_sha256"],
        "previous_sha256": public_events[-1]["event_sha256"],
        "event_sha256": "0" * 64,
    })
    metadata["private_audit"]["event_chain_head_sha256"] = _rehash_events(
        private_events
    )
    metadata["public_trace"]["event_chain_head_sha256"] = _rehash_events(
        public_events
    )
    metadata["trace_pair_sha256"] = trace_pair_fingerprint(
        metadata["private_audit"], metadata["public_trace"]
    )