"""Owned fixture files only; real client/seal code, no runtime or model calls."""

import hashlib
import inspect
import json
import os
import shutil
import socket
import subprocess
import time

import pytest

import ghcp_ahp_client as client
import ghcp_ahp_offline_fixture as fixtures
import ghcp_ahp_output_collection as output
import ghcp_sol_offline_rehearsal as rehearsal

CANARY = "SYNTHETIC_OUTPUT_CREDENTIAL_0123456789"
TASK = fixtures.TASK_IDS[0]


def run_with_budget(*args, **kwargs):
    return rehearsal.run_rehearsal(*args, token_budget=fixtures.budget_config(), **kwargs)


@pytest.fixture(autouse=True)
def offline_only(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("output fixture attempted real process/network")
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "sendto", forbidden)


def bound(tmp_path, profile, *, credential=None):
    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    work = state / "workspace"
    work.mkdir(mode=0o700)
    (work / "input.txt").write_bytes(b"immutable fixture input\n")
    (state / "tmp").mkdir(mode=0o700)
    job = state / "tmp/vscode-agent-codex-sandbox-fixture"
    job.mkdir(mode=0o700)
    clock = fixtures.Clock()
    collection = output.OutputCollection(state, job, tmp_path / "sealed", profile=profile, synthetic=True, clock=clock)
    port = fixtures.Port(fixtures.first_turn_records(TASK), output_collection=collection)
    session = client.SessionClient(port, "ahp-session:/fixture", "ahp-chat:/fixture", authenticated=True,
                                   credential=credential, clock=clock, output_collection=collection)
    return collection, port, session


def begin(session):
    assert session.send_turn("turn1", "SYNTHETIC, memory-only input")
    assert session.accept({"jsonrpc": "2.0", "method": "action", "params": {
        "channel": session.chat, "serverSeq": 1, "origin": None,
        "action": {"type": "chat/turnStarted", "turnId": "turn1"}}})


def finish(session):
    session.accept({"jsonrpc": "2.0", "method": "action", "params": {
        "channel": session.chat, "serverSeq": 2, "origin": None,
        "action": {"type": "chat/turnComplete", "turnId": "turn1", "duration": 1}}})
    session.finish()


def write(port, name="nested/answer.txt", raw=b"synthetic deliverable\n"):
    port.write_output(name, raw, write=rehearsal.write)


def assert_refused(collection, session, tmp_path, code=None):
    assert session.status == "stopped" and collection.phase == "refused"
    assert collection.error
    if code:
        assert collection.error == code
    with pytest.raises(client.Refused):
        session.capture(tmp_path / "must-not-publish.json")
    assert not (tmp_path / "must-not-publish.json").exists()
    assert not session.send_turn("turn2", "MUST NOT BE SENT")
    receipt = json.loads((collection.spool / "output-lifecycle.json").read_text())
    assert receipt["status"] == "refused" and receipt["reason_codes"]
    assert receipt["execution_allowed"] is False and receipt["synthetic"] is True


@pytest.mark.parametrize("profile", output.PROFILES)
def test_real_client_collects_seals_then_disposes_and_deletes(tmp_path, monkeypatch, profile):
    collection, port, session = bound(tmp_path, profile)
    begin(session)
    write(port)
    write(port, "binary.dat", b"\x00\xff\x01")
    (collection.paths[collection.source] / "empty-directory").mkdir()
    original = port.send

    def send(message, timeout):
        if message.get("method") == "disposeSession":
            assert collection.phase == "sealed" and collection.events == output.EVENTS[:4]
            assert collection.workspace.is_dir() and collection.job_tmpdir.is_dir()
            snapshot = output.verify_seal(collection.spool, profile=profile, binding=collection.binding, seal_sha256=collection.seal_sha256)
            assert {row["path"] for row in snapshot["generated_files"]} == {"nested/answer.txt", "binary.dat"}
        return original(message, timeout)

    monkeypatch.setattr(port, "send", send)
    finish(session)
    assert session.status == "completed" and collection.events == output.EVENTS
    assert port.operations == ["write", "write", "hold", "dispose", "terminate"]
    assert not collection.workspace.exists() and not collection.job_tmpdir.exists()
    record = session.capture(tmp_path / "capture.json")
    assert record["status"] == "completed" and record["gate_ready"] is False
    assert record["output_collection"]["execution_allowed"] is False
    assert record["output_collection"]["profile"] == profile
    assert record["output_collection"]["synthetic"] is True
    assert record["counts"]["model_requests"] == record["counts"]["premium_requests"] == "not_reported"
    answer = next(row for row in record["generated_files"] if row["path"] == "nested/answer.txt")
    assert answer["content"] == "synthetic deliverable\n"
    assert answer["source_sha256"] == hashlib.sha256(answer["content"].encode()).hexdigest()
    for name in ("output-snapshot.json", "output-seal.json", "output-lifecycle.json"):
        assert (collection.spool / name).stat().st_mode & 0o777 == 0o600
    assert (tmp_path / "capture.json").stat().st_mode & 0o777 == 0o600
    with pytest.raises(client.Refused, match="output_fixture_write_after_hold"):
        write(port, "too-late", b"not admitted")


@pytest.mark.parametrize("profile", output.PROFILES)
@pytest.mark.parametrize("when", ["before_hold", "inside_hold"])
def test_deleted_source_before_collection_is_never_an_empty_success(tmp_path, monkeypatch, profile, when):
    collection, port, session = bound(tmp_path, profile)
    begin(session)
    write(port)
    source = collection.paths[collection.source]
    if when == "before_hold":
        shutil.rmtree(source)
    else:
        original = port.hold_outputs
        def deleted(**kwargs):
            result = original(**kwargs)
            shutil.rmtree(source)
            return result
        monkeypatch.setattr(port, "hold_outputs", deleted)
    finish(session)
    assert_refused(collection, session, tmp_path)
    assert "sealed" not in collection.events


@pytest.mark.parametrize("profile", output.PROFILES)
def test_partial_reader_is_checked_against_an_independent_inventory(tmp_path, monkeypatch, profile):
    collection, port, session = bound(tmp_path, profile)
    begin(session)
    write(port, "one.txt", b"one")
    write(port, "two.txt", b"two")
    original = output.read_snapshot
    def partial(path, expected, entries, check):
        files = original(path, expected, entries, check)
        if path == collection.paths[collection.source]:
            files.pop("two.txt")
        return files
    monkeypatch.setattr(output, "read_snapshot", partial)
    finish(session)
    assert_refused(collection, session, tmp_path, "output_partial_collection")


@pytest.mark.parametrize("profile", output.PROFILES)
@pytest.mark.parametrize("damage", ["file_symlink", "directory_symlink", "hardlink", "fifo", "root_symlink", "root_replaced"])
def test_alias_and_special_files_fail_without_touching_outside_data(tmp_path, profile, damage):
    collection, port, session = bound(tmp_path, profile)
    begin(session)
    write(port)
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel"
    sentinel.write_bytes(b"must survive")
    source = collection.paths[collection.source]
    if damage == "file_symlink": (source / "escape").symlink_to(sentinel)
    if damage == "directory_symlink": (source / "escape").symlink_to(outside, target_is_directory=True)
    if damage == "hardlink": os.link(sentinel, source / "escape")
    if damage == "fifo": os.mkfifo(source / "escape")
    if damage in {"root_symlink", "root_replaced"}:
        source.rename(tmp_path / "moved-source")
        if damage == "root_symlink": source.symlink_to(outside, target_is_directory=True)
        else: source.mkdir(mode=0o700)
    finish(session)
    assert session.status == "stopped" and collection.phase == "refused"
    assert sentinel.read_bytes() == b"must survive"
    with pytest.raises(client.Refused): session.capture(tmp_path / "must-not-publish.json")
    assert not (tmp_path / "must-not-publish.json").exists()


@pytest.mark.parametrize("profile", output.PROFILES)
@pytest.mark.parametrize("limit", ["file_bytes", "total_bytes", "file_count", "depth"])
def test_unchanged_size_and_count_caps_are_enforced_before_publication(tmp_path, profile, limit):
    collection, port, session = bound(tmp_path, profile)
    begin(session)
    source = collection.paths[collection.source]
    if limit in {"file_bytes", "total_bytes"}:
        sizes = [client.MAX_FILE_BYTES + 1] if limit == "file_bytes" else [client.MAX_FILE_BYTES] * 5
        for i, size in enumerate(sizes):
            with (source / f"sparse-{i}").open("wb") as stream:
                stream.truncate(size)  # Sparse fixture; not a benchmark/read of 80 MiB.
    if limit == "file_count":
        for i in range(client.MAX_FILES + 1): (source / f"file-{i}").touch()
    if limit == "depth":
        current = source
        for _ in range(66):
            current = current / "d"
            current.mkdir()
    finish(session)
    assert_refused(collection, session, tmp_path, "output_entry_limit" if limit == "depth" else "output_size_limit")


@pytest.mark.parametrize("profile", output.PROFILES)
@pytest.mark.parametrize("damage", ["changed", "removed", "new_file"])
def test_tree_change_during_collection_fails_closed(tmp_path, monkeypatch, profile, damage):
    collection, port, session = bound(tmp_path, profile)
    begin(session)
    write(port, "answer.txt", b"initial")
    original = output.read_snapshot
    def changed(path, expected, entries, check):
        files = original(path, expected, entries, check)
        if path == collection.paths[collection.source]:
            if damage == "changed": (path / "answer.txt").write_bytes(b"changed")
            if damage == "removed": (path / "answer.txt").unlink()
            if damage == "new_file": (path / "late.txt").write_bytes(b"late")
        return files
    monkeypatch.setattr(output, "read_snapshot", changed)
    finish(session)
    assert_refused(collection, session, tmp_path, "output_tree_changed")


@pytest.mark.parametrize("profile", output.PROFILES)
def test_same_size_writes_are_detected_even_when_stat_timestamps_are_coarse(tmp_path, monkeypatch, profile):
    collection, port, session = bound(tmp_path, profile)
    begin(session)
    write(port, "answer.txt", b"before!")
    original_identity, original_read = output.file_identity, output.read_snapshot
    def coarse(info):
        value = original_identity(info)
        return (*value[:3], 0, 0, *value[5:])
    def rewritten(path, expected, entries, check):
        data = original_read(path, expected, entries, check)
        if path == collection.paths[collection.source]:
            (path / "answer.txt").write_bytes(b"after!!")
        return data
    monkeypatch.setattr(output, "file_identity", coarse)
    monkeypatch.setattr(output, "read_snapshot", rewritten)
    finish(session)
    assert_refused(collection, session, tmp_path, "output_tree_changed")


@pytest.mark.parametrize("profile", output.PROFILES)
@pytest.mark.parametrize("damage", ["missing", "throws", "writers", "cleanup", "binding", "synthetic", "truthy", "extra"])
def test_missing_or_unproven_writer_and_cleanup_hold_refuses(tmp_path, monkeypatch, profile, damage):
    collection, port, session = bound(tmp_path, profile)
    begin(session)
    write(port)
    original = port.hold_outputs
    def bad(**kwargs):
        if damage == "throws": raise OSError(CANARY)
        result = original(**kwargs)
        if damage == "writers": result["writers_stopped"] = False
        if damage == "cleanup": result["cleanup_held"] = False
        if damage == "binding": result["binding"] = "foreign"
        if damage == "synthetic": result["synthetic"] = False
        if damage == "truthy": result["writers_stopped"] = 1
        if damage == "extra": result["ignored"] = True
        return result
    monkeypatch.setattr(port, "hold_outputs", None if damage == "missing" else bad)
    finish(session)
    assert_refused(collection, session, tmp_path)
    assert CANARY not in (collection.spool / "output-lifecycle.json").read_text()
    assert "collected" not in collection.events


@pytest.mark.parametrize("profile", output.PROFILES)
@pytest.mark.parametrize("filename", ["output-snapshot.json", "output-seal.json"])
@pytest.mark.parametrize("damage", ["partial", "write_error"])
def test_partial_or_failed_seal_write_is_not_a_success(tmp_path, monkeypatch, profile, filename, damage):
    collection, port, session = bound(tmp_path, profile)
    begin(session)
    write(port)
    original = collection._write
    def damaged(name, raw):
        if name == filename:
            if damage == "write_error": raise OSError(CANARY)
            raw = raw[:-3]
        return original(name, raw)
    monkeypatch.setattr(collection, "_write", damaged)
    finish(session)
    assert_refused(collection, session, tmp_path)
    assert "sealed" not in collection.events


@pytest.mark.parametrize("profile", output.PROFILES)
@pytest.mark.parametrize("filename", ["output-snapshot.json", "output-seal.json", "output-lifecycle.json"])
@pytest.mark.parametrize("damage", ["missing", "changed", "symlink"])
def test_seal_and_receipt_rechecked_after_runtime_deletion(tmp_path, profile, filename, damage):
    collection, port, session = bound(tmp_path, profile)
    begin(session)
    write(port)
    finish(session)
    assert collection.phase == "complete"
    target = collection.spool / filename
    raw = target.read_bytes()
    target.unlink()
    if damage == "changed": target.write_bytes(raw + b" ")
    if damage == "symlink":
        outside = tmp_path / "replacement"
        outside.write_bytes(raw)
        target.symlink_to(outside)
    with pytest.raises((client.Refused, OSError)):
        session.capture(tmp_path / "must-not-publish.json")
    assert not (tmp_path / "must-not-publish.json").exists()


@pytest.mark.parametrize("profile", output.PROFILES)
@pytest.mark.parametrize("damage", ["input_changed", "input_missing"])
def test_original_inputs_remain_immutable_in_both_profiles(tmp_path, profile, damage):
    collection, port, session = bound(tmp_path, profile)
    begin(session)
    write(port)
    source = collection.workspace / "input.txt"
    if damage == "input_changed": source.write_bytes(b"modified")
    else: source.unlink()
    finish(session)
    assert_refused(collection, session, tmp_path, "output_input_changed")


@pytest.mark.parametrize("profile", output.PROFILES)
def test_choice1_cannot_write_workspace_and_choice3_does_not_inherit_readonly_label(tmp_path, profile):
    collection, port, session = bound(tmp_path, profile)
    begin(session)
    write(port)
    (collection.workspace / "workspace-output.txt").write_bytes(b"workspace output")
    finish(session)
    if profile == output.PROFILES[0]:
        assert_refused(collection, session, tmp_path, "output_input_changed")
    else:
        capture = session.capture(tmp_path / "capture.json")
        assert capture["output_collection"]["profile"] == "default_policy_unpatched"
        assert {row["path"] for row in capture["generated_files"]} == {"nested/answer.txt", "workspace-output.txt"}


@pytest.mark.parametrize("profile", output.PROFILES)
@pytest.mark.parametrize("damage", ["not_stopped", "terminate_raises", "delete_failed"])
def test_failed_cleanup_cannot_publish_a_completed_gate(tmp_path, monkeypatch, profile, damage):
    collection, port, session = bound(tmp_path, profile)
    begin(session)
    write(port)
    if damage == "not_stopped": monkeypatch.setattr(port, "terminate", lambda timeout: False)
    if damage == "terminate_raises":
        def failed(timeout): raise OSError(CANARY)
        monkeypatch.setattr(port, "terminate", failed)
    if damage == "delete_failed":
        def failed(name): raise OSError(CANARY)
        monkeypatch.setattr(collection, "_delete", failed)
    finish(session)
    assert_refused(collection, session, tmp_path)


@pytest.mark.parametrize("profile", output.PROFILES)
def test_legacy_post_stop_workspace_capture_cannot_bypass_bound_collection(tmp_path, profile):
    collection, port, session = bound(tmp_path, profile)
    with pytest.raises(FileExistsError):
        output.OutputCollection(collection.state, collection.job_tmpdir, collection.spool, profile=profile, synthetic=True)
    begin(session)
    write(port)
    finish(session)
    replacement = tmp_path / "replacement"
    replacement.mkdir()
    with pytest.raises(client.Refused, match="output_legacy_fallback_refused"):
        session.capture(tmp_path / "must-not-publish.json", workspace=replacement)
    with pytest.raises(client.Refused, match="output_phase_refused"):
        collection.collect_and_seal(port, session._safe)


@pytest.mark.parametrize("profile", output.PROFILES)
@pytest.mark.parametrize("mode", ["text", "binary"])
def test_credential_masking_precedes_seal_or_binary_is_refused(tmp_path, profile, mode):
    collection, port, session = bound(tmp_path, profile, credential=CANARY)
    begin(session)
    write(port, "answer.dat", (b"\xff" if mode == "binary" else b"") + CANARY.encode())
    finish(session)
    if mode == "binary":
        assert_refused(collection, session, tmp_path, "binary_credential_exposure_refused")
    else:
        record = session.capture(tmp_path / "capture.json")
        assert record["generated_files"][0]["content"] == "[REDACTED]"
        for path in collection.spool.iterdir(): assert CANARY.encode() not in path.read_bytes()
        assert CANARY not in (tmp_path / "capture.json").read_text()


@pytest.mark.parametrize("profile", output.PROFILES)
def test_collection_deadline_is_finite_and_no_new_work_is_admitted(tmp_path, profile):
    collection, port, session = bound(tmp_path, profile)
    begin(session)
    write(port)
    ticks = iter([0.0, output.COLLECTION_SECONDS])
    collection.clock = lambda: next(ticks)
    finish(session)
    assert_refused(collection, session, tmp_path, "output_collection_timeout")


@pytest.mark.parametrize("profile", output.PROFILES)
def test_profile_identity_is_bound_and_cannot_be_substituted_after_seal(tmp_path, profile):
    collection, port, session = bound(tmp_path, profile)
    begin(session)
    write(port)
    finish(session)
    other = next(value for value in output.PROFILES if value != profile)
    with pytest.raises(client.Refused, match="output_seal_contract_refused"):
        output.verify_seal(collection.spool, profile=other, binding=collection.binding, seal_sha256=collection.seal_sha256)
    with pytest.raises(client.Refused, match="output_seal_contract_refused"):
        output.verify_seal(collection.spool, profile=profile, binding="0" * 64, seal_sha256=collection.seal_sha256)


@pytest.mark.parametrize("profile", output.PROFILES)
def test_delete_cannot_run_without_a_successful_seal(tmp_path, profile):
    collection, port, session = bound(tmp_path, profile)
    write(port)
    with pytest.raises(client.Refused, match="output_fixture_cleanup_before_seal"):
        port.terminate(timeout=4.0)
    assert collection.workspace.is_dir() and collection.job_tmpdir.is_dir()
    assert collection.after_termination(True) is False
    assert collection.error == "output_not_sealed" and collection.phase == "refused"
    assert collection.workspace.is_dir() and collection.job_tmpdir.is_dir()


@pytest.mark.parametrize("profile", [None, "", "choice1", "default", "workspace-write", "read-only", True])
def test_unknown_profiles_never_select_a_fallback_path(tmp_path, profile):
    report = run_with_budget(tmp_path / "invalid", output_profile=profile)
    assert report["exit_status"] == 2 and report["reason_codes"] == ["rehearsal_output_profile_refused"]
    assert report["tasks"] == [] and not (tmp_path / "invalid").exists()


@pytest.mark.parametrize("profile", output.PROFILES)
def test_both_profiles_run_all_five_through_sealed_output_and_existing_grader_contract(tmp_path, profile):
    report = run_with_budget(tmp_path / "five", output_profile=profile)
    assert report["exit_status"] == 0 and report["fixture_pipeline_passed"] is True, report
    assert report["output_profile"] == profile
    assert report["execution_allowed"] is report["grading_allowed"] is report["gate5_passed"] is False
    assert set(report["actual_calls"].values()) == {0}
    for task in report["tasks"]:
        assert task["capture_valid"] is True
        root = tmp_path / "five/tasks" / task["task_id"]
        capture = rehearsal.validate_capture(root, task["task_id"])
        assert capture["output_collection"]["profile"] == profile
        assert capture["output_collection"]["events"] == output.EVENTS
        assert not (root / "state/workspace").exists()
        assert not (root / "state/tmp/vscode-agent-codex-sandbox-fixture").exists()
        assert (root / "workspace/answer.txt").is_file()  # Sealed export, not runtime source.


@pytest.mark.parametrize("profile", output.PROFILES)
@pytest.mark.parametrize("field", ["output_collection", "receipt_sha256", "seal_sha256", "profile", "execution_allowed", "synthetic", "events"])
def test_rehashed_outer_capture_cannot_drop_or_relabel_output_proof(tmp_path, profile, field):
    root = tmp_path / "five"
    assert run_with_budget(root, output_profile=profile)["exit_status"] == 0
    task = root / "tasks" / TASK
    folder = task / "capture"
    capture = json.loads((folder / "client-capture.json").read_text())
    if field == "output_collection": capture.pop(field)
    elif field in {"receipt_sha256", "seal_sha256"}: capture["output_collection"].pop(field)
    elif field == "profile": capture["output_collection"][field] = next(p for p in output.PROFILES if p != profile)
    elif field in {"execution_allowed", "synthetic"}: capture["output_collection"][field] = not capture["output_collection"][field]
    else: capture["output_collection"][field] = list(reversed(output.EVENTS))
    raw = rehearsal.encoded(capture) + b"\n"
    (folder / "client-capture.json").write_bytes(raw)
    manifest = json.loads((folder / "capture.json").read_text())
    manifest["files"]["client-capture.json"] = rehearsal.identity(raw)
    (folder / "capture.json").write_text(json.dumps(manifest))
    with pytest.raises((client.Refused, rehearsal.Refused)):
        rehearsal.validate_capture(task, TASK)


@pytest.mark.parametrize("profile", output.PROFILES)
@pytest.mark.parametrize("damage", ["missing_source", "extra_source", "traversal", "content_changed", "bool_size",
                                   "execution_true", "synthetic_false", "unknown_field"])
def test_self_rehashed_snapshot_still_requires_exact_safe_semantics(tmp_path, profile, damage):
    collection, port, session = bound(tmp_path, profile)
    begin(session)
    write(port, "answer.txt", b"a")
    finish(session)
    snapshot_path, seal_path = collection.spool / "output-snapshot.json", collection.spool / "output-seal.json"
    snapshot, seal = json.loads(snapshot_path.read_text()), json.loads(seal_path.read_text())
    row = snapshot["generated_files"][0]
    if damage == "missing_source": snapshot["source_files"].pop("answer.txt")
    if damage == "extra_source": snapshot["source_files"]["uncaptured.txt"] = dict(snapshot["source_files"]["answer.txt"])
    if damage == "traversal":
        snapshot["source_files"]["../escape"] = snapshot["source_files"].pop("answer.txt")
        row["path"] = "../escape"
    if damage == "content_changed": row["content"] = "b"
    if damage == "bool_size": row["source_bytes"] = True
    if damage == "execution_true": snapshot["execution_allowed"] = True
    if damage == "synthetic_false": snapshot["synthetic"] = False
    if damage == "unknown_field": snapshot["launch_allowed"] = True
    raw = output.encoded(snapshot)
    snapshot_path.write_bytes(raw)
    seal["snapshot"] = {"sha256": output.digest(raw), "bytes": len(raw)}
    seal["source_inventory_sha256"] = output.digest(output.encoded(snapshot["source_files"]))
    seal_raw = output.encoded(seal)
    seal_path.write_bytes(seal_raw)
    with pytest.raises(client.Refused):
        output.verify_seal(collection.spool, profile=profile, binding=collection.binding, seal_sha256=output.digest(seal_raw))


@pytest.mark.parametrize("profile", output.PROFILES)
@pytest.mark.parametrize("damage", ["events", "host_terminated", "hold_scope", "deleted", "synthetic", "execution_allowed", "extra"])
def test_self_rehashed_lifecycle_cannot_claim_success_or_native_freeze(tmp_path, profile, damage):
    collection, port, session = bound(tmp_path, profile)
    begin(session)
    write(port)
    finish(session)
    path = collection.spool / "output-lifecycle.json"
    receipt = json.loads(path.read_text())
    if damage == "events": receipt["events"] = list(reversed(receipt["events"]))
    if damage == "host_terminated": receipt["host_terminated"] = 1
    if damage == "hold_scope": receipt["hold_scope"] = "independently_verified_native_freeze"
    if damage == "deleted": receipt["deleted"] = []
    if damage in {"synthetic", "execution_allowed"}: receipt[damage] = not receipt[damage]
    if damage == "extra": receipt["launch_allowed"] = True
    raw = output.encoded(receipt)
    path.write_bytes(raw)
    with pytest.raises(client.Refused, match="output_receipt_refused"):
        output.verify_seal(collection.spool, profile=profile, binding=collection.binding, seal_sha256=collection.seal_sha256,
                           receipt_sha256=output.digest(raw))


@pytest.mark.parametrize("profile", output.PROFILES)
def test_successful_output_collection_cannot_override_first_turn_refusal(tmp_path, profile):
    collection, port, session = bound(tmp_path, profile)
    begin(session)
    write(port)
    port.records[4]["value"]["response"].pop("model")
    finish(session)
    assert collection.phase == "complete" and session.status == "stopped"
    capture = session.capture(tmp_path / "capture.json")
    assert capture["first_turn_attestation"]["verified"] is False
    assert "first_turn_served_model_not_reported" in capture["first_turn_attestation"]["reason_codes"]
    assert capture["gate_ready"] is False and capture["output_collection"]["execution_allowed"] is False


@pytest.mark.parametrize("profile", output.PROFILES)
@pytest.mark.parametrize("damage", ["early_delete", "partial", "link_escape", "oversized"])
def test_collection_failure_fails_five_task_gate_without_grader_publication(tmp_path, monkeypatch, profile, damage):
    original = fixtures.Port.hold_outputs
    def injected(port, **kwargs):
        result = original(port, **kwargs)
        collection = port.output_collection
        source = collection.paths[collection.source]
        if damage == "early_delete": shutil.rmtree(source)
        if damage == "partial": (source / "second.txt").write_bytes(b"must be captured")
        if damage == "link_escape": (source / "escape").symlink_to(tmp_path / "outside")
        if damage == "oversized":
            with (source / "large").open("wb") as stream: stream.truncate(client.MAX_FILE_BYTES + 1)
        return result
    monkeypatch.setattr(fixtures.Port, "hold_outputs", injected)
    if damage == "partial":
        original_read = output.read_snapshot
        def partial(*args):
            data = original_read(*args)
            data.pop("second.txt", None)
            return data
        monkeypatch.setattr(output, "read_snapshot", partial)
    report = run_with_budget(tmp_path / "failed", output_profile=profile)
    assert report["exit_status"] == 2 and report["fixture_pipeline_passed"] is False
    assert report["reason_codes"] == ["rehearsal_capture_incomplete"]
    assert report["grader_contract"] is None and not (tmp_path / "failed/grader-input").exists()
    assert len(report["tasks"]) == 5 and all(row["capture_valid"] is False for row in report["tasks"])
    assert set(report["actual_calls"].values()) == {0}


def test_limits_and_old_live_locks_are_not_relaxed(tmp_path):
    import ghcp_ahp_patched_runtime as patched
    assert (output.MAX_FILE_BYTES, output.MAX_CAPTURE_BYTES, output.MAX_FILES) == (16 * 1024 * 1024, 64 * 1024 * 1024, 256)
    assert output.COLLECTION_SECONDS == 3.0
    assert inspect.signature(output.OutputCollection).parameters["clock"].default is time.monotonic
    collection, _port, _session = bound(tmp_path, output.PROFILES[0])
    with pytest.raises(client.Refused, match="output_clock_refused"):
        output.OutputCollection(collection.state, collection.job_tmpdir, tmp_path / "not-live",
                                profile=output.PROFILES[0], synthetic=False, clock=lambda: 0.0)
    assert not (tmp_path / "not-live").exists()
    assert client.draft_receipt()["reason_codes"] == ["ahp_paid_contract_unverified"]
    with pytest.raises(client.Refused, match="patched_runtime_activation_pending_owner"):
        patched.require_activation()
