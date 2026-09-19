"""One offline selector for the V2 producer-to-step8 materialization boundary."""

import ctypes
import errno
import hashlib
import json
import os
import socket
import subprocess
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

import gpt54_v2_grading_input as materializer
import step8_grade as grading
from core.agentic_v2_manifest_binding import bind_stage, binding_record
from core.agentic_v2_run_driver import RunOutcome
from core.agentic_v2_run_report import (
    build_agentic_v2_metrics,
    build_result_row,
    summarise_v2_run,
)
from core.agentic_v2_task_journal import TaskStanding
from core.codex_runtime_config import CodexProviderSettings
from core.cost_receipts import build_receipt
from core.inference_manifest import bind_deliverable_file_records, validate_local_deliverables
from core.result_fingerprint import validate_inference_result_fingerprint
from core.result_projection import project_result_row
from gpt54_comparison_preflight import (
    REQUIRED_SOURCES,
    ROOT,
    _canonical_json,
    compile_grading_plan,
    inspect_plan,
    load_plan,
)


def _write_json(path, value):
    data = (_canonical_json(value) + "\n").encode("utf-8")
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def _fixture(tmp_path, manifest, plan, run, *, failures=0):
    """Use real producer/binding helpers and committed prompt bytes; no runtime."""
    prepared = json.loads((ROOT / "batch-runner/tests/fixtures/run_record/step1_tasks_prepared.json").read_text())
    bound = bind_stage("advance_check_5", dataset_tasks=[
        SimpleNamespace(prompt=task["instruction"], **task) for task in prepared["tasks"]
    ])
    dispatch = next(row for row in plan.dispatch.runs if row.run_id == run.run_id)
    config = json.loads(dispatch.config_json)
    source = tmp_path / "source"
    source.mkdir()
    deliverables = source / "deliverables"
    deliverables.mkdir()
    rows = []
    for index, task in enumerate(bound.tasks):
        failed = index < failures
        outcome = {"success": not failed, "deliverable_text": f"fixture answer {index}"}
        if failed:
            outcome["error"] = "capability_unavailable"
        standing = TaskStanding(task.task_id, 1, 0, None, "fixture", "offline fixture")
        receipt = build_receipt([{"stage": "generation", "state": "reserved"}]).as_dict() if index == 2 else None
        metrics = build_agentic_v2_metrics(outcome, standing=standing, task_wall_time_ms=10.0, receipt=receipt)
        files = [] if failed else [f"deliverable_files/{task.task_id}/nested/answer.txt"]
        for relative in files:
            path = deliverables / relative
            path.parent.mkdir(parents=True)
            path.write_bytes(f"offline fixture for {task.task_id}\n".encode())
        row = build_result_row(
            outcome, task_id=task.task_id, standing=standing,
            sector=task.sector, occupation=task.occupation, instruction=task.prompt,
            deliverable_files=files, latency_ms=10.0, metrics=metrics, receipt=receipt,
        )
        if index == 1:
            row["problem_solving_cost"] = None
            row["grading_cost"] = None
        rows.append(row)
    summary = summarise_v2_run(rows, manifest_size=5, receipt_ceiling="partial")
    summary.update(skipped_on_resume=0, stopped_early=None, unaccounted_tasks=list(run.task_ids))
    record = {
        "stage": "advance_check_5", "run_id": run.run_id,
        "dataset_revision": manifest["shared"]["dataset"]["revision"],
        "binding": binding_record(bound),
        "shard": {
            "index": 1, "of": 1, "task_count": 5, "cohort_size": 5,
            "task_ids": list(run.task_ids), "covers_whole_stage": True,
            "what_this_run_is": "the whole stage, in one run",
        },
        "chosen_settings": config["cost"]["chosen_settings"],
        "request_conditions": {
            "plan_file": {"path": "comparison-run.json", "sha256": hashlib.sha256(dispatch.config_json.encode()).hexdigest()},
            "replay_format": "faithful",
        },
        "run": RunOutcome(run_id=run.run_id, rows=rows, summary=summary).as_dict(),
    }
    record_path = source / "run_record.json"
    record_hash = _write_json(record_path, record)
    file_rows = bind_deliverable_file_records(rows, deliverables)
    identity = {
        # Deliberately fake offline publication identity; never live evidence.
        "source_repo_id": "fixture-owner/inference-results", "source_revision": "e" * 40,
        "run_id": run.run_id, "condition": run.condition, "repeat": run.repeat,
        "task_ids": list(run.task_ids),
        "producer_results_path": run.producer_results_path,
        "producer_rows_pointer": run.producer_rows_pointer,
        "manifest_sha256": plan.dispatch.manifest_sha256,
        "grading_plan_sha256": hashlib.sha256(plan.canonical_bytes()).hexdigest(),
        "config_sha256": record["request_conditions"]["plan_file"]["sha256"],
        "source_pins_sha256": hashlib.sha256(plan.dispatch.source_pins_json.encode()).hexdigest(),
        "run_record_sha256": record_hash,
        "deliverables": [{"task_id": row["task_id"], "files": row["deliverable_file_records"]} for row in file_rows],
    }
    identity_path = source / "inference-identity.json"
    approval = _write_json(identity_path, identity)
    return record, identity, {
        "manifest": manifest, "run_record": record_path,
        "source_deliverables": deliverables, "inference_identity": identity_path,
        "approved_identity_sha256": approval, "destination": tmp_path / "installed",
    }


@pytest.mark.parametrize("case", [
    "valid_r1", "valid_r2", "terminal_error", "all_terminal_errors", "native_rename_boundary",
    "missing_identity", "null_identity", "unapproved_identity", "approval_mismatch", "duplicate_json_key",
    "identity_repo", "identity_revision", "identity_whitespace", "dataset_repo",
    "dataset_revision", "git_revision", "identity_binding", "identity_files",
    "missing_pin", "changed_pin", "control_drift", "combined_plan_drift",
    "codex_spec", "untyped_spec", "spec_drift",
    "record_hash", "record_symlink", "identity_symlink", "record_run", "outcome_run", "producer_binding", "shard",
    "config_digest", "config_path", "chosen_limit", "replay", "rehearsal", "stopped", "resumed",
    "missing_task", "null_results", "duplicate_task", "task_order", "extra_task", "prompt_drift",
    "partial_row", "contradictory_success", "failure_with_files", "success_without_files",
    "retried", "attempts", "summary", "invalid_receipt", "file_count", "producer_file_hash",
    "file_bytes", "file_missing", "extra_file", "extra_task_tree", "extra_source_file",
    "cross_task_file", "path_escape", "file_symlink", "root_symlink", "ancestor_symlink",
    "hardlink", "nonregular_file", "empty_file",
    "destination_directory", "destination_file", "destination_symlink", "destination_parent_symlink", "destination_overlap",
    "write_failure", "rename_failure", "rename_collision", "unsupported_atomic_rename",
    "parent_replaced_at_staging", "parent_replaced_during_write",
])
def test_v2_grading_input_is_bound_atomic_and_offline(case, tmp_path, monkeypatch, capsys):
    forbidden_calls = []

    def forbidden(*args, **kwargs):
        forbidden_calls.append(True)
        pytest.fail("materializer attempted execution, network, provider auth, or client construction")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(CodexProviderSettings, "auth_command", forbidden)
    monkeypatch.setattr("core.codex_runtime_config.AzureAIRouteSettings.from_env", forbidden)
    monkeypatch.setattr("core.agentic_v2_model_voice.AzureFoundryVoice.__post_init__", forbidden)
    monkeypatch.setattr("core.llm_client.create_typed_azure_client", forbidden)
    monkeypatch.setattr(grading.Grader, "__init__", forbidden)
    monkeypatch.setattr(grading.RubricLoader, "__init__", forbidden)
    monkeypatch.setattr(grading, "preflight_routes", forbidden)
    monkeypatch.setattr(grading, "open_cost_recorder", forbidden)

    native_rename = materializer._no_replace_rename

    def fixture_rename(source_fd, source, target_fd, target, flags):
        # A single-threaded filesystem double, not proof of native atomicity.
        # Production has no fallback to this check-then-rename operation.
        assert source_fd == target_fd and flags == 1
        assert not os.path.isabs(source) and not os.path.isabs(target)
        try:
            os.stat(target, dir_fd=target_fd, follow_symlinks=False)
        except FileNotFoundError:
            os.rename(source, target, src_dir_fd=source_fd, dst_dir_fd=target_fd)
            return 0
        ctypes.set_errno(errno.EEXIST)
        return -1

    monkeypatch.setattr(materializer, "_no_replace_rename", lambda: fixture_rename)
    if case == "native_rename_boundary":
        monkeypatch.setattr(materializer, "_no_replace_rename", native_rename)

    manifest = json.loads(json.dumps(load_plan()))
    plan = compile_grading_plan(manifest)
    run = plan.runs[3 if case == "valid_r2" else 0]
    record, identity, inputs = _fixture(
        tmp_path, manifest, plan, run,
        failures=5 if case == "all_terminal_errors" else 1 if case == "terminal_error" else 0,
    )
    rows = record["run"]["results"]
    destination = inputs["destination"]
    first_file = inputs["source_deliverables"] / f"deliverable_files/{run.task_ids[0]}/nested/answer.txt"
    stage_calls = []
    mkdtemp = materializer.tempfile.mkdtemp

    def track_staging(*args, **kwargs):
        stage_calls.append(True)
        return mkdtemp(*args, **kwargs)

    monkeypatch.setattr(materializer.tempfile, "mkdtemp", track_staging)

    def check_refusal(spec=run, **overrides):
        with pytest.raises(materializer.V2GradingInputRefused):
            materializer.materialize_v2_grading_input(spec, **{**inputs, **overrides})
        assert forbidden_calls == []
        assert list(tmp_path.glob(".installed.tmp-*")) == []

    if case == "identity_binding":
        # Reapprove malformed documents in the fixture to reach every semantic
        # check. The caller still supplies the digest separately each time.
        mutations = {
            "run_id": "other-run", "condition": "codex", "repeat": True,
            "task_ids": list(reversed(run.task_ids)),
            "producer_results_path": "other.json", "producer_rows_pointer": "/results",
            "manifest_sha256": "0" * 64, "grading_plan_sha256": "0" * 64,
            "config_sha256": "0" * 64, "source_pins_sha256": "0" * 64,
        }
        for key, value in mutations.items():
            approval = _write_json(inputs["inference_identity"], {**identity, key: value})
            check_refusal(approved_identity_sha256=approval)
        missing = dict(identity)
        missing.pop("source_revision")
        check_refusal(approved_identity_sha256=_write_json(inputs["inference_identity"], missing))
        assert not stage_calls and not destination.exists()
        return
    if case == "spec_drift":
        for key, value in {
            "repeat": True, "task_ids": tuple(reversed(run.task_ids)),
            "producer_rows_pointer": "/results", "inference_results_path": "../escape.json",
            "staged_deliverables_directory": "other-tree",
            "grader_contract_json": "{}", "command": ("not-step8",),
        }.items():
            check_refusal(replace(run, **{key: value}))
        assert not stage_calls and not destination.exists()
        return
    if case == "combined_plan_drift":
        altered = plan.as_dict()
        altered["grading_runs"][0]["input_materialization"] = "unbound"
        result = inspect_plan(manifest, grading_plan=altered)
        assert result["configuration_problems"] == ["grading_plan_mismatch"]
        assert result["grading_plan"] is None
        assert result["launch_allowed"] is result["full_220_allowed"] is False
        assert not stage_calls and not destination.exists() and not forbidden_calls
        return

    if case == "identity_repo":
        identity["source_repo_id"] = "https://example.invalid/inference"
    elif case == "identity_revision":
        identity["source_revision"] = "main"
    elif case == "identity_whitespace":
        identity["source_revision"] += " "
    elif case == "dataset_repo":
        identity["source_repo_id"] = manifest["shared"]["dataset"]["repo_id"]
    elif case == "dataset_revision":
        identity["source_revision"] = manifest["shared"]["dataset"]["revision"]
    elif case == "git_revision":
        identity["source_revision"] = manifest["base_sha"]
    elif case == "identity_files":
        identity["deliverables"][0]["files"][0]["size"] = True
    elif case == "missing_pin":
        manifest["source_pins"].pop("batch-runner/gpt54_v2_grading_input.py")
    elif case == "changed_pin":
        manifest["source_pins"]["batch-runner/gpt54_v2_grading_input.py"] = "0" * 64
    elif case == "control_drift":
        manifest["shared"]["results"]["receipt_schema"] = "another-schema"
    elif case == "codex_spec":
        run = plan.runs[1]
    elif case == "untyped_spec":
        run = run.as_dict()
    elif case == "record_run":
        record["run_id"] = "wrong-repeat"
    elif case == "outcome_run":
        record["run"]["run_id"] = "wrong-condition"
    elif case == "producer_binding":
        record["binding"]["binding_seal"] = "0" * 64
    elif case == "shard":
        record["shard"]["covers_whole_stage"] = False
    elif case == "config_digest":
        record["request_conditions"]["plan_file"]["sha256"] = "0" * 64
    elif case == "config_path":
        record["request_conditions"]["plan_file"]["path"] = "unreviewed-plan.json"
    elif case == "chosen_limit":
        record["chosen_settings"]["tool_calls_per_attempt"] += 1
    elif case == "replay":
        record["request_conditions"]["replay_format"] = "other"
    elif case == "rehearsal":
        record["rehearsal"] = {"not_a_run": True}
    elif case == "stopped":
        record["run"]["stopped_early"] = {"rule": "stopped"}
    elif case == "resumed":
        record["run"]["skipped_on_resume"] = [run.task_ids[0]]
    elif case == "missing_task":
        rows.pop()
    elif case == "null_results":
        record["run"]["results"] = None
    elif case == "duplicate_task":
        rows[-1] = rows[0]
    elif case == "task_order":
        rows.reverse()
    elif case == "extra_task":
        rows.append({**rows[0], "task_id": "extra-task", "deliverable_files": []})
    elif case == "prompt_drift":
        rows[0]["instruction"] += " "
    elif case == "partial_row":
        rows[0]["status"] = "partial"
    elif case == "contradictory_success":
        rows[0]["observability"]["agentic_metrics"]["terminal_error_category"] = "capability_unavailable"
    elif case == "failure_with_files":
        rows[0]["status"] = "error"
    elif case == "success_without_files":
        rows[0]["deliverable_files"] = []
        rows[0]["deliverable_files_count"] = 0
    elif case == "retried":
        rows[0]["retried"] = True
    elif case == "attempts":
        rows[0]["observability"]["agentic_metrics"]["agentic_v2_attempts"] = True
    elif case == "summary":
        record["run"]["summary"]["executed"] = 4
    elif case == "invalid_receipt":
        rows[0]["problem_solving_cost"] = {"status": "complete"}
    elif case == "file_count":
        rows[0]["deliverable_files_count"] = True
    elif case == "producer_file_hash":
        rows[0]["deliverable_file_records"] = [{"path": rows[0]["deliverable_files"][0], "size": 1, "sha256": "0" * 64}]
    elif case == "file_bytes":
        first_file.write_bytes(b"replaced bytes")
    elif case == "file_missing":
        first_file.unlink()
    elif case == "extra_file":
        (first_file.parent / "extra.txt").write_bytes(b"unlisted")
    elif case == "extra_task_tree":
        (inputs["source_deliverables"] / "deliverable_files/extra-task").mkdir()
    elif case == "extra_source_file":
        (inputs["source_deliverables"] / "unowned.txt").write_bytes(b"unowned")
    elif case == "cross_task_file":
        rows[0]["deliverable_files"] = rows[1]["deliverable_files"]
    elif case == "path_escape":
        rows[0]["deliverable_files"] = [f"deliverable_files/{run.task_ids[0]}/../escape"]
    elif case == "file_symlink":
        first_file.unlink()
        first_file.symlink_to(inputs["run_record"])
    elif case == "root_symlink":
        linked = tmp_path / "linked-root"
        linked.symlink_to(inputs["source_deliverables"], target_is_directory=True)
        inputs["source_deliverables"] = linked
    elif case == "ancestor_symlink":
        linked = tmp_path / "linked-parent"
        linked.symlink_to(inputs["run_record"].parent, target_is_directory=True)
        inputs["source_deliverables"] = linked / "deliverables"
    elif case == "hardlink":
        os.link(first_file, tmp_path / "another-link")
    elif case == "nonregular_file":
        first_file.unlink()
        os.mkfifo(first_file)
    elif case == "empty_file":
        first_file.write_bytes(b"")
    elif case == "destination_directory":
        destination.mkdir()
    elif case == "destination_file":
        destination.write_bytes(b"preserve this file")
    elif case == "destination_symlink":
        destination.symlink_to(tmp_path / "missing-target", target_is_directory=True)
    elif case == "destination_parent_symlink":
        actual_parent = tmp_path / "actual-parent"
        actual_parent.mkdir()
        linked_parent = tmp_path / "linked-destination-parent"
        linked_parent.symlink_to(actual_parent, target_is_directory=True)
        inputs["destination"] = linked_parent / "installed"
    elif case == "destination_overlap":
        inputs["destination"] = inputs["source_deliverables"] / "nested-destination"
    elif case == "write_failure":
        write = materializer._write_file

        def fail_after_write(*args):
            write(*args)
            raise OSError("injected write failure")

        monkeypatch.setattr(materializer, "_write_file", fail_after_write)
    elif case == "rename_failure":
        def fail_rename(*args):
            ctypes.set_errno(5)
            return -1

        monkeypatch.setattr(materializer, "_no_replace_rename", lambda: fail_rename)
    elif case == "rename_collision":
        rename = materializer._no_replace_rename()

        def create_collision(*args):
            destination.mkdir()  # Even an empty directory must not be replaced.
            return rename(*args)

        monkeypatch.setattr(materializer, "_no_replace_rename", lambda: create_collision)
    elif case == "unsupported_atomic_rename":
        def unsupported():
            raise materializer.V2GradingInputRefused("no atomic no-clobber primitive")

        monkeypatch.setattr(materializer, "_no_replace_rename", unsupported)
    elif case in {"parent_replaced_at_staging", "parent_replaced_during_write"}:
        parent = tmp_path / "output-parent"
        parent.mkdir()
        inputs["destination"] = parent / "installed"
        displaced_parent = tmp_path / "original-parent"

        def replace_parent():
            parent.rename(displaced_parent)
            parent.mkdir()
            (parent / "preserve.txt").write_bytes(b"replacement belongs to someone else")

        if case == "parent_replaced_at_staging":
            def change_parent_after_staging(*args, **kwargs):
                staged = track_staging(*args, **kwargs)
                replace_parent()
                return staged

            monkeypatch.setattr(materializer.tempfile, "mkdtemp", change_parent_after_staging)
        else:
            write = materializer._write_file
            writes = []

            def change_parent_during_write(*args):
                write(*args)
                writes.append(True)
                if len(writes) == 1:
                    replace_parent()

            monkeypatch.setattr(materializer, "_write_file", change_parent_during_write)

    # Binding hashes are separately approved fixture inputs, never read from a
    # self-asserted "verified" flag. Reseal malformed records to test semantics.
    identity["run_record_sha256"] = _write_json(inputs["run_record"], record)
    inputs["approved_identity_sha256"] = _write_json(inputs["inference_identity"], identity)
    if case == "missing_identity":
        inputs["inference_identity"] = tmp_path / "absent.json"
    elif case == "null_identity":
        inputs["approved_identity_sha256"] = _write_json(inputs["inference_identity"], None)
    elif case == "unapproved_identity":
        inputs["approved_identity_sha256"] = None
    elif case == "approval_mismatch":
        inputs["approved_identity_sha256"] = "0" * 64
    elif case in {"record_symlink", "identity_symlink"}:
        key = "run_record" if case == "record_symlink" else "inference_identity"
        linked = tmp_path / "linked-document.json"
        linked.symlink_to(inputs[key])
        inputs[key] = linked
    elif case == "record_hash":
        inputs["run_record"].write_bytes(inputs["run_record"].read_bytes() + b" ")
    elif case == "duplicate_json_key":
        duplicate = inputs["inference_identity"].read_bytes().replace(b'{', b'{"repeat":1,', 1)
        inputs["inference_identity"].write_bytes(duplicate)
        inputs["approved_identity_sha256"] = hashlib.sha256(duplicate).hexdigest()

    if case not in {"valid_r1", "valid_r2", "terminal_error", "all_terminal_errors", "native_rename_boundary"}:
        with pytest.raises(materializer.V2GradingInputRefused):
            materializer.materialize_v2_grading_input(run, **inputs)
        assert forbidden_calls == []
        assert list(tmp_path.glob(".installed.tmp-*")) == []
        if case in {"destination_directory", "rename_collision"}:
            assert destination.is_dir() and list(destination.iterdir()) == []
        elif case == "destination_file":
            assert destination.read_bytes() == b"preserve this file"
        elif case == "destination_symlink":
            assert destination.is_symlink() and not destination.exists()
        else:
            assert not os.path.lexists(destination)
            assert not os.path.lexists(inputs["destination"])
        if case in {"parent_replaced_at_staging", "parent_replaced_during_write"}:
            assert list(displaced_parent.iterdir()) == []
            assert list(parent.iterdir()) == [parent / "preserve.txt"]
            assert (parent / "preserve.txt").read_bytes() == b"replacement belongs to someone else"
        elif case not in {"write_failure", "rename_failure", "rename_collision"}:
            assert stage_calls == []  # All input validation precedes any write.
        return

    before_record = inputs["run_record"].read_bytes()
    before_identity = inputs["inference_identity"].read_bytes()
    try:
        result_path = materializer.materialize_v2_grading_input(run, **inputs)
    except materializer.V2GradingInputRefused as error:
        if case != "native_rename_boundary":
            raise
        cause = error.__cause__
        assert isinstance(cause, OSError) and cause.errno in {errno.EINVAL, errno.ENOSYS, errno.EOPNOTSUPP}
        assert not destination.exists()
        assert list(tmp_path.glob(".installed.tmp-*")) == []
        assert before_record == inputs["run_record"].read_bytes()
        assert before_identity == inputs["inference_identity"].read_bytes()
        assert not forbidden_calls
        with capsys.disabled():
            print(f"\nNative RENAME_NOREPLACE unavailable (errno {cause.errno}); refused with no destination or staging residue.")
        return
    if case == "native_rename_boundary":
        with capsys.disabled():
            print("\nNative RENAME_NOREPLACE installed the validated fixture successfully.")
    assert result_path == destination / run.inference_results_path
    with monkeypatch.context() as context:
        context.chdir(destination / "batch-runner")
        payload = grading.load_local_inference_results()
        assert grading.resolve_source_inference_identity(payload, "2.0") == (
            identity["source_repo_id"], identity["source_revision"],
        )
        selected = grading.filter_tasks(payload, ",".join(run.task_ids), 5)
    assert [row["task_id"] for row in selected] == list(run.task_ids)
    validate_inference_result_fingerprint(payload)
    upload = destination / Path(run.staged_deliverables_directory).parent
    assert validate_local_deliverables(selected, upload) == selected
    assert bind_deliverable_file_records(selected, upload) == selected
    for original, projected in zip(rows, selected, strict=True):
        for key, value in original.items():
            if key not in {"problem_solving_cost", "grading_cost"}:
                assert projected[key] == value
        for key in ("problem_solving_cost", "grading_cost"):
            assert (key in original) == (key in projected)
            if original.get(key) is None and key in original:
                assert projected[key] is None
            elif key in original:
                assert projected[key] == project_result_row(original, original)[key]
    assert "problem_solving_cost" not in selected[0]
    assert selected[1]["problem_solving_cost"] is None
    assert selected[2]["problem_solving_cost"]["status"] == "partial"
    assert selected[2]["problem_solving_cost"]["estimated_cost_usd"] is None
    assert selected[2]["problem_solving_cost"]["known_cost_usd"] is None
    assert "call_reachability_unknown" in selected[2]["problem_solving_cost"]["missing_reasons"]
    again = materializer.materialize_v2_grading_input(run, **{**inputs, "destination": tmp_path / "second"})
    assert again.read_bytes() == result_path.read_bytes()
    assert before_record == inputs["run_record"].read_bytes()
    assert before_identity == inputs["inference_identity"].read_bytes()
    for relative in (item for row in identity["deliverables"] for item in row["files"]):
        assert (upload / relative["path"]).read_bytes() == (inputs["source_deliverables"] / relative["path"]).read_bytes()
    assert sorted(path.relative_to(destination).as_posix() for path in destination.rglob("*") if path.is_file()) == sorted([
        run.inference_results_path,
        *(str(Path(run.staged_deliverables_directory).parent / item["path"]) for row in identity["deliverables"] for item in row["files"]),
    ])
    inspection = inspect_plan(manifest, grading_plan=plan.as_dict())
    assert inspection["configuration_valid"] is True
    assert inspection["launch_allowed"] is inspection["full_220_allowed"] is False
    assert "comparison_materialization_and_workflow_gates_not_wired" in inspection["launch_blockers"]
    assert [(row.condition, row.repeat) for row in plan.runs] == [
        ("sandbox_v2", 1), ("codex", 1), ("codex", 2), ("sandbox_v2", 2),
    ]
    assert run.input_materialization == "gpt54_v2_grading_input.materialize_v2_grading_input"
    assert len(REQUIRED_SOURCES) == 29
    sol = load_plan(ROOT / "batch-runner/experiments/execution_envelope/gpt56_sol_copilot_codex_pilot.yaml")
    parser = "batch-runner/gpt54_comparison_preflight.py"
    assert sol["source_pins"][parser] == hashlib.sha256((ROOT / parser).read_bytes()).hexdigest()
    assert not forbidden_calls
    assert list(tmp_path.glob(".*.tmp-*")) == []
