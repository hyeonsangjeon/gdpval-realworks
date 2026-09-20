"""One free selector for Codex inputs and the unchanged V2 default path."""

import ctypes
import errno
import hashlib
import json
import os
import socket
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

import gpt54_codex_grading_input as materializer
import gpt54_v2_grading_input as primitives
import step8_grade as grading
from core.codex_runtime_config import CodexProviderSettings
from core.cost_receipts import CostReceipt, build_receipt, ledger_reference, summarise_receipts
from core.inference_manifest import bind_deliverable_file_records, validate_local_deliverables
from core.prepared_fingerprint import prepared_fingerprint
from core.result_fingerprint import inference_result_fingerprint, validate_inference_result_fingerprint
from gpt54_comparison_preflight import REQUIRED_SOURCES, ROOT, _canonical_json, compile_grading_plan, inspect_plan, load_plan
from .test_gpt54_v2_grading_input import test_v2_grading_input_is_bound_atomic_and_offline as _check_v2


def _write_json(path, value):
    data = (_canonical_json(value) + "\n").encode("utf-8")
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def _fixture(tmp_path, manifest, plan, run, *, failures=0, runtime_lineage=None):
    """Real producer shape/helpers; publication identity is deliberately fake."""
    dispatch = next(row for row in plan.dispatch.runs if row.run_id == run.run_id)
    config = json.loads(dispatch.config_json)
    prepared = json.loads((ROOT / "batch-runner/tests/fixtures/run_record/step1_tasks_prepared.json").read_text())
    assert [task["task_id"] for task in prepared["tasks"]] == list(run.task_ids)
    generation = runtime_lineage or run.run_id + ":local:" + "a" * 32
    prepared.update(experiment_id=run.run_id, publication_generation=generation)
    source = tmp_path / "source"
    workspace = source / "workspace"
    upload = workspace / "upload"
    upload.mkdir(parents=True)
    partial = build_receipt([{"stage": "generation", "state": "reserved"}])
    rows = []
    for index, task_id in enumerate(run.task_ids):
        failed = index < failures
        files = [] if failed else [f"deliverable_files/{task_id}/nested/answer.txt"]
        for relative in files:
            path = upload / relative
            path.parent.mkdir(parents=True)
            path.write_bytes(f"offline Codex fixture for {task_id}\n".encode())
        row = {
            "task_id": task_id, "status": "error" if failed else "success",
            "content": "offline fixture", "deliverable_text": "offline fixture",
            "deliverable_files": files, "model": config["condition_a"]["model"]["deployment"],
            "usage": None, "observability": {"preprocessors": []},
            "latency_ms": 10.0, "timestamp": "2026-09-19T00:00:00+00:00",
            "reflection_history": [], "reflection_attempts": 0,
        }
        if failed:
            row.update(error="fixture execution error", content=None, deliverable_text=None, latency_ms=None)
        if index == 1:
            row.update(problem_solving_cost=None, grading_cost=None)
        elif index == 2:
            row.update(problem_solving_cost=partial.as_dict(), grading_cost=partial.as_dict())
        elif index == 3:
            row["problem_solving_cost"] = CostReceipt.unavailable().as_dict()
        rows.append(row)
    rows = bind_deliverable_file_records(rows, upload)
    ledger_bytes = b'{"stage":"generation","state":"reserved"}\n'
    ledger = workspace / "cost_ledger_condition_a.jsonl"
    ledger.write_bytes(ledger_bytes)
    reference = ledger_reference(ledger.name, hashlib.sha256(ledger_bytes).hexdigest())
    payload = {
        "experiment_id": run.run_id, "publication_generation": generation,
        "experiment_name": config["experiment"]["name"], "source": config["data"]["source"],
        "condition": config["condition_a"]["name"], "condition_identity": "condition_a",
        "run_id": runtime_lineage or run.run_id + ":local:1", "execution_mode": config["execution"]["mode"],
        "ordered_task_ids": list(run.task_ids), "prepared_fingerprint": prepared_fingerprint(prepared),
        "model": config["condition_a"]["model"]["deployment"],
        "started_at": "2026-09-19T00:00:00+00:00", "completed_at": "2026-09-19T00:01:00+00:00",
        "resume_rounds_used": 0,
        "summary": {"total": 5, "success": 5 - failures, "error": failures, "qa_failed": 0,
                    "problem_solving_cost": summarise_receipts([partial]).as_dict()},
        "results": rows, "cost_ledger": reference,
        "fixture_extension": {"preserve": [None, False, 3, "source fields are not report rows"]},
    }
    payload["result_fingerprint"] = inference_result_fingerprint(payload)
    result_path = workspace / "step2_inference_results.json"
    source_hash = _write_json(result_path, payload)
    identity = {
        "source_repo_id": "fixture-owner/codex-inference", "source_revision": "e" * 40,
        "run_id": run.run_id, "condition": run.condition, "repeat": run.repeat,
        "task_ids": list(run.task_ids), "producer_results_path": run.producer_results_path,
        "producer_rows_pointer": run.producer_rows_pointer,
        "manifest_sha256": plan.dispatch.manifest_sha256,
        "grading_plan_sha256": hashlib.sha256(plan.canonical_bytes()).hexdigest(),
        "config_sha256": hashlib.sha256(dispatch.config_json.encode()).hexdigest(),
        "source_pins_sha256": hashlib.sha256(plan.dispatch.source_pins_json.encode()).hexdigest(),
        "inference_results_sha256": source_hash, "result_fingerprint": payload["result_fingerprint"],
        "producer_run_id": payload["run_id"], "publication_generation": generation,
        "prepared_fingerprint": payload["prepared_fingerprint"],
        "deliverables": [{"task_id": row["task_id"], "files": row["deliverable_file_records"]} for row in rows],
        "cost_ledger": {**reference, "size": len(ledger_bytes)},
    }
    identity_path = source / "approved_identity.json"
    approval = _write_json(identity_path, identity)
    return payload, identity, {
        "manifest": manifest, "inference_results": result_path, "source_upload": upload,
        "inference_identity": identity_path, "approved_identity_sha256": approval,
        "destination": tmp_path / "installed",
    }


@pytest.mark.parametrize("case", [
    "valid_r1", "valid_r2", "terminal_error", "all_errors", "prebound_identity", "opaque_lineage",
    "ledger_absent", "ledger_null", "native_rename_boundary",
    "missing_identity", "null_identity", "missing_approval", "approval_mismatch", "duplicate_identity_key",
    "identity_binding", "identity_repo", "identity_revision", "identity_whitespace", "dataset_repo", "dataset_revision", "git_revision",
    "prebound_repo_drift", "prebound_revision_null", "prebound_approval_drift",
    "missing_pin", "changed_pin", "shared_pin_drift", "control_drift", "combined_plan_drift", "v2_spec", "untyped_spec", "spec_drift",
    "source_digest", "fingerprint_drift", "fingerprint_missing", "duplicate_source_key", "source_nan", "source_symlink", "identity_symlink",
    "experiment", "experiment_name", "condition", "condition_identity", "execution_mode", "model", "row_model", "runtime_run", "generation", "prepared_fingerprint", "resume_rounds", "completed_at",
    "missing_task", "extra_task", "duplicate_task", "task_order", "ordered_ids", "null_results",
    "partial_row", "pending_row", "qa_failed", "contradictory_success", "error_with_files", "success_without_files", "empty_error",
    "reflection_attempts", "reflection_history", "resume_row", "retried", "invalid_receipt", "receipt_drift", "summary_count", "missing_file_records", "producer_file_hash",
    "file_bytes", "file_missing", "extra_file", "extra_task_tree", "extra_root_file", "cross_task_file", "path_escape", "file_symlink", "root_symlink", "hardlink", "nonregular_file", "empty_file",
    "ledger_missing", "ledger_bytes", "ledger_symlink", "ledger_hardlink", "ledger_path", "ledger_digest", "ledger_approval", "ledger_write_failure",
    "destination_directory", "destination_file", "destination_symlink", "destination_parent_symlink", "destination_overlap", "destination_traversal", "destination_parent_missing", "rename_collision",
    *["v2:" + case for case in (
        "valid_r1", "valid_r2", "terminal_error", "all_terminal_errors", "native_rename_boundary",
        "file_bytes", "hardlink", "write_failure", "rename_failure", "rename_collision", "unsupported_atomic_rename",
        "parent_replaced_at_staging", "parent_replaced_during_write",
    )],
])
def test_codex_grading_input_preserves_source_and_v2_boundary(case, tmp_path, monkeypatch, capsys):
    if case.startswith("v2:"):
        # Keep the original V2 assertions: no rewritten or weakened regression.
        _check_v2(case.split(":", 1)[1], tmp_path, monkeypatch, capsys)
        return
    forbidden_calls = []

    def forbidden(*args, **kwargs):
        forbidden_calls.append(True)
        pytest.fail("materializer attempted subprocess, network, auth, or client construction")

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
    native_rename = primitives._no_replace_rename

    def fixture_rename(source_fd, source, target_fd, target, flags):
        # Test-only single-threaded double, never a production rename fallback.
        assert source_fd == target_fd and flags == 1
        assert not os.path.isabs(source) and not os.path.isabs(target)
        try:
            os.stat(target, dir_fd=target_fd, follow_symlinks=False)
        except FileNotFoundError:
            os.rename(source, target, src_dir_fd=source_fd, dst_dir_fd=target_fd)
            return 0
        ctypes.set_errno(errno.EEXIST)
        return -1

    monkeypatch.setattr(primitives, "_no_replace_rename", native_rename if case == "native_rename_boundary" else lambda: fixture_rename)
    manifest = json.loads(json.dumps(load_plan()))
    plan = compile_grading_plan(manifest)
    run = plan.runs[2 if case == "valid_r2" else 1]
    payload, identity, inputs = _fixture(
        tmp_path, manifest, plan, run, failures=5 if case == "all_errors" else 1 if case == "terminal_error" else 0,
        runtime_lineage="approved-relay-lineage.42" if case == "opaque_lineage" else None,
    )
    rows = payload["results"]
    destination = inputs["destination"]
    first_file = inputs["source_upload"] / f"deliverable_files/{run.task_ids[0]}/nested/answer.txt"
    ledger = inputs["inference_results"].with_name("cost_ledger_condition_a.jsonl")
    stage_calls = []
    mkdtemp = primitives.tempfile.mkdtemp

    def track_staging(*args, **kwargs):
        stage_calls.append(True)
        return mkdtemp(*args, **kwargs)

    monkeypatch.setattr(primitives.tempfile, "mkdtemp", track_staging)

    def refuse(spec=run, **overrides):
        with pytest.raises(materializer.CodexGradingInputRefused):
            materializer.materialize_codex_grading_input(spec, **{**inputs, **overrides})
        assert not forbidden_calls and not list(tmp_path.glob(".*.tmp-*"))

    if case == "identity_binding":
        for key, value in {
            "run_id": "another-run", "condition": "sandbox_v2", "repeat": True,
            "task_ids": list(reversed(run.task_ids)), "producer_results_path": "other.json",
            "producer_rows_pointer": "/run/results", "manifest_sha256": "0" * 64,
            "grading_plan_sha256": "0" * 64, "config_sha256": "0" * 64,
            "source_pins_sha256": "0" * 64, "result_fingerprint": "0" * 64,
            "producer_run_id": "unapproved-runtime", "publication_generation": "unapproved-generation",
            "prepared_fingerprint": "0" * 64, "deliverables": [], "extra_field": True,
        }.items():
            refuse(approved_identity_sha256=_write_json(inputs["inference_identity"], {**identity, key: value}))
        missing = dict(identity)
        missing.pop("source_revision")
        refuse(approved_identity_sha256=_write_json(inputs["inference_identity"], missing))
        assert not stage_calls and not destination.exists()
        return
    if case == "spec_drift":
        for key, value in {
            "repeat": True, "task_ids": tuple(reversed(run.task_ids)), "producer_rows_pointer": "/run/results",
            "inference_results_path": "../escape.json", "staged_deliverables_directory": "another-root",
            "grader_contract_json": "{}", "command": ("not-step8",),
        }.items():
            refuse(replace(run, **{key: value}))
        assert not stage_calls and not destination.exists()
        return
    if case == "combined_plan_drift":
        document = plan.as_dict()
        document["grading_runs"][1]["input_materialization"] = "unbound"
        inspection = inspect_plan(manifest, grading_plan=document)
        assert inspection["configuration_problems"] == ["grading_plan_mismatch"]
        assert inspection["grading_plan"] is None
        assert inspection["launch_allowed"] is inspection["full_220_allowed"] is False
        assert not stage_calls and not forbidden_calls
        return

    mutations = {
        "identity_repo": (identity, "source_repo_id", "https://example.invalid/repo"),
        "identity_revision": (identity, "source_revision", "main"),
        "identity_whitespace": (identity, "source_revision", "e" * 40 + " "),
        "dataset_repo": (identity, "source_repo_id", manifest["shared"]["dataset"]["repo_id"]),
        "dataset_revision": (identity, "source_revision", manifest["shared"]["dataset"]["revision"]),
        "git_revision": (identity, "source_revision", manifest["base_sha"]),
        "prebound_repo_drift": (payload, "source_repo_id", "wrong-owner/inference"),
        "prebound_revision_null": (payload, "source_revision", None),
        "prebound_approval_drift": (payload, "source_identity_document_sha256", "0" * 64),
        "experiment": (payload, "experiment_id", "another-repeat"),
        "experiment_name": (payload, "experiment_name", "another experiment"),
        "condition": (payload, "condition", "codex"),
        "condition_identity": (payload, "condition_identity", "condition_b"),
        "execution_mode": (payload, "execution_mode", "agentic_sandbox_v2"),
        "model": (payload, "model", "another-model"),
        "row_model": (rows[0], "model", "another-model"),
        "runtime_run": (payload, "run_id", run.run_id),
        "generation": (payload, "publication_generation", "unbound-generation"),
        "prepared_fingerprint": (payload, "prepared_fingerprint", "invalid"),
        "resume_rounds": (payload, "resume_rounds_used", True),
        "completed_at": (payload, "completed_at", None),
        "ordered_ids": (payload, "ordered_task_ids", list(reversed(run.task_ids))),
        "null_results": (payload, "results", None),
        "partial_row": (rows[0], "status", "partial"),
        "pending_row": (rows[0], "status", "pending"),
        "qa_failed": (rows[0], "status", "qa_failed"),
        "contradictory_success": (rows[0], "error", "execution failed"),
        "error_with_files": (rows[0], "status", "error"),
        "success_without_files": (rows[0], "deliverable_files", []),
        "reflection_attempts": (rows[0], "reflection_attempts", True),
        "reflection_history": (rows[0], "reflection_history", [{}]),
        "resume_row": (rows[0], "resume_round", 1),
        "retried": (rows[0], "retried", True),
        "invalid_receipt": (rows[2], "problem_solving_cost", {"status": "complete"}),
        "summary_count": (payload["summary"], "total", True),
        "ledger_path": (payload["cost_ledger"], "path", "../escape.jsonl"),
        "ledger_digest": (payload["cost_ledger"], "sha256", "0" * 64),
        "ledger_approval": (identity["cost_ledger"], "size", True),
    }
    if case in mutations:
        target, key, value = mutations[case]
        target[key] = value
    elif case == "prebound_identity":
        payload.update(source_repo_id=identity["source_repo_id"], source_revision=identity["source_revision"])
    elif case in {"ledger_absent", "ledger_null"}:
        payload.pop("cost_ledger")
        if case == "ledger_null":
            payload["cost_ledger"] = None
        identity["cost_ledger"] = None
    elif case == "missing_pin":
        manifest["source_pins"].pop("batch-runner/gpt54_codex_grading_input.py")
    elif case in {"changed_pin", "shared_pin_drift"}:
        name = "gpt54_v2_grading_input.py" if case == "shared_pin_drift" else "gpt54_codex_grading_input.py"
        manifest["source_pins"]["batch-runner/" + name] = "0" * 64
    elif case == "control_drift":
        manifest["shared"]["results"]["receipt_schema"] = "another-schema"
    elif case == "v2_spec":
        run = plan.runs[0]
    elif case == "untyped_spec":
        run = run.as_dict()
    elif case == "missing_task":
        rows.pop()
    elif case == "extra_task":
        rows.append({**rows[0], "task_id": "extra-task", "deliverable_files": []})
    elif case == "duplicate_task":
        rows[-1] = rows[0]
    elif case == "task_order":
        rows.reverse()
    elif case == "empty_error":
        rows[0].update(status="error", error="", deliverable_files=[])
    elif case == "missing_file_records":
        rows[0].pop("deliverable_file_records")
    elif case == "producer_file_hash":
        rows[0]["deliverable_file_records"][0]["sha256"] = "0" * 64
    elif case in {"file_bytes", "empty_file"}:
        first_file.write_bytes(b"changed" if case == "file_bytes" else b"")
    elif case == "file_missing":
        first_file.unlink()
    elif case == "extra_file":
        (first_file.parent / "extra.txt").write_bytes(b"unlisted")
    elif case == "extra_task_tree":
        (inputs["source_upload"] / "deliverable_files/extra-task").mkdir()
    elif case == "extra_root_file":
        (inputs["source_upload"] / "unowned.txt").write_bytes(b"unowned")
    elif case == "cross_task_file":
        rows[0]["deliverable_files"] = rows[1]["deliverable_files"]
    elif case == "path_escape":
        rows[0]["deliverable_files"] = [f"deliverable_files/{run.task_ids[0]}/../escape"]
    elif case == "file_symlink":
        first_file.unlink()
        first_file.symlink_to(inputs["inference_results"])
    elif case == "root_symlink":
        linked = tmp_path / "linked-upload"
        linked.symlink_to(inputs["source_upload"], target_is_directory=True)
        inputs["source_upload"] = linked
    elif case == "hardlink":
        os.link(first_file, tmp_path / "another-link")
    elif case == "nonregular_file":
        first_file.unlink()
        os.mkfifo(first_file)
    elif case == "ledger_missing":
        ledger.unlink()
    elif case == "ledger_bytes":
        ledger.write_bytes(b"replaced ledger\n")
    elif case == "ledger_symlink":
        ledger.unlink()
        ledger.symlink_to(first_file)
    elif case == "ledger_hardlink":
        os.link(ledger, tmp_path / "ledger-link")
    elif case == "ledger_write_failure":
        write = primitives._write_file

        def fail_ledger_write(path, data):
            write(path, data)
            if path.name == ledger.name:
                raise OSError("injected ledger write failure")

        monkeypatch.setattr(primitives, "_write_file", fail_ledger_write)
    elif case == "destination_directory":
        destination.mkdir()
    elif case == "destination_file":
        destination.write_bytes(b"preserve this file")
    elif case == "destination_symlink":
        destination.symlink_to(tmp_path / "missing-target", target_is_directory=True)
    elif case == "destination_parent_symlink":
        actual = tmp_path / "actual-parent"
        actual.mkdir()
        linked = tmp_path / "linked-parent"
        linked.symlink_to(actual, target_is_directory=True)
        inputs["destination"] = linked / "installed"
    elif case == "destination_overlap":
        inputs["destination"] = inputs["source_upload"] / "installed"
    elif case == "destination_traversal":
        inputs["destination"] = destination / ".." / "escaped"
    elif case == "destination_parent_missing":
        inputs["destination"] = tmp_path / "missing-parent" / "installed"
    elif case == "rename_collision":
        def collide(*args):
            destination.mkdir()
            return fixture_rename(*args)

        monkeypatch.setattr(primitives, "_no_replace_rename", lambda: collide)

    # Reapprove malformed fixtures to reach semantic checks, rather than merely
    # testing a digest mismatch. This never manufactures real approval evidence.
    payload["result_fingerprint"] = inference_result_fingerprint(payload)
    identity["result_fingerprint"] = payload["result_fingerprint"]
    if case == "fingerprint_drift":
        payload["result_fingerprint"] = "0" * 64
    elif case == "fingerprint_missing":
        payload.pop("result_fingerprint")
    elif case == "receipt_drift":
        rows[2]["problem_solving_cost"]["known_cost_usd"] = 0
    identity["inference_results_sha256"] = _write_json(inputs["inference_results"], payload)
    if case in {"duplicate_source_key", "source_nan"}:
        raw = inputs["inference_results"].read_bytes()
        raw = (b'{"model":"gpt-5.4",' + raw[1:]) if case == "duplicate_source_key" else raw.replace(b'"resume_rounds_used":0', b'"resume_rounds_used":NaN')
        inputs["inference_results"].write_bytes(raw)
        identity["inference_results_sha256"] = hashlib.sha256(raw).hexdigest()
    inputs["approved_identity_sha256"] = _write_json(inputs["inference_identity"], identity)
    if case == "missing_identity":
        inputs["inference_identity"] = tmp_path / "absent.json"
    elif case == "null_identity":
        inputs["approved_identity_sha256"] = _write_json(inputs["inference_identity"], None)
    elif case == "missing_approval":
        inputs["approved_identity_sha256"] = None
    elif case == "approval_mismatch":
        inputs["approved_identity_sha256"] = "0" * 64
    elif case == "duplicate_identity_key":
        raw = b'{"repeat":1,' + inputs["inference_identity"].read_bytes()[1:]
        inputs["inference_identity"].write_bytes(raw)
        inputs["approved_identity_sha256"] = hashlib.sha256(raw).hexdigest()
    elif case == "source_digest":
        inputs["inference_results"].write_bytes(inputs["inference_results"].read_bytes() + b" ")
    elif case in {"source_symlink", "identity_symlink"}:
        key = "inference_results" if case == "source_symlink" else "inference_identity"
        linked = tmp_path / "linked-document.json"
        linked.symlink_to(inputs[key])
        inputs[key] = linked

    if case not in {"valid_r1", "valid_r2", "terminal_error", "all_errors", "prebound_identity", "opaque_lineage", "ledger_absent", "ledger_null", "native_rename_boundary"}:
        refuse(run)
        if case in {"destination_directory", "rename_collision"}:
            assert destination.is_dir() and not list(destination.iterdir())
        elif case == "destination_file":
            assert destination.read_bytes() == b"preserve this file"
        elif case == "destination_symlink":
            assert destination.is_symlink() and not destination.exists()
        else:
            assert not os.path.lexists(destination) and not os.path.lexists(inputs["destination"])
        if case not in {"ledger_write_failure", "rename_collision"}:
            assert not stage_calls  # Refusal precedes all output writes.
        return

    before_source = inputs["inference_results"].read_bytes()
    before_identity = inputs["inference_identity"].read_bytes()
    before_ledger = ledger.read_bytes()
    try:
        result_path = materializer.materialize_codex_grading_input(run, **inputs)
    except materializer.CodexGradingInputRefused as error:
        if case != "native_rename_boundary":
            raise
        cause = error.__cause__
        assert isinstance(cause, OSError) and cause.errno in {errno.EINVAL, errno.ENOSYS, errno.EOPNOTSUPP}
        assert not destination.exists() and not list(tmp_path.glob(".*.tmp-*"))
        assert before_source == inputs["inference_results"].read_bytes()
        assert before_identity == inputs["inference_identity"].read_bytes()
        assert before_ledger == ledger.read_bytes() and not forbidden_calls
        with capsys.disabled():
            print(f"\nCodex native RENAME_NOREPLACE unavailable (errno {cause.errno}); refused without residue.")
        return
    if case == "native_rename_boundary":
        with capsys.disabled():
            print("\nCodex native RENAME_NOREPLACE installed the validated fixture.")
    assert result_path == destination / run.inference_results_path
    with monkeypatch.context() as context:
        context.chdir(destination / "batch-runner")
        output = grading.load_local_inference_results()
        assert grading.resolve_source_inference_identity(output, "2.0") == (identity["source_repo_id"], identity["source_revision"])
        selected = grading.filter_tasks(output, ",".join(run.task_ids), 5)
    validate_inference_result_fingerprint(output)
    validate_inference_result_fingerprint(payload)
    expected = {**payload, "source_repo_id": identity["source_repo_id"], "source_revision": identity["source_revision"],
                "source_identity_document_sha256": inputs["approved_identity_sha256"]}
    expected["result_fingerprint"] = inference_result_fingerprint(expected)
    assert result_path.read_bytes() == (_canonical_json(expected) + "\n").encode("utf-8")
    assert _canonical_json(output["results"]) == _canonical_json(payload["results"])
    assert [row["task_id"] for row in selected] == list(run.task_ids)
    upload = destination / Path(run.staged_deliverables_directory).parent
    assert validate_local_deliverables(selected, upload) == selected
    assert bind_deliverable_file_records(selected, upload) == selected
    assert "problem_solving_cost" not in selected[0]
    assert selected[1]["problem_solving_cost"] is selected[1]["grading_cost"] is None
    assert selected[2]["problem_solving_cost"]["status"] == "partial"
    assert selected[2]["problem_solving_cost"]["estimated_cost_usd"] is None
    # This is the existing confirmed floor, not a claim that the total is zero.
    assert selected[2]["problem_solving_cost"]["known_cost_usd"] == 0.0
    assert "call_reachability_unknown" in selected[2]["problem_solving_cost"]["missing_reasons"]
    output_files = [run.inference_results_path]
    if payload.get("cost_ledger") is not None:
        copied_ledger = result_path.with_name(ledger.name)
        assert copied_ledger.read_bytes() == before_ledger
        assert hashlib.sha256(copied_ledger.read_bytes()).hexdigest() == payload["cost_ledger"]["sha256"]
        output_files.append(copied_ledger.relative_to(destination).as_posix())
    else:
        assert ("cost_ledger" in payload) == ("cost_ledger" in output)
        assert not result_path.with_name(ledger.name).exists()
    for row in identity["deliverables"]:
        for item in row["files"]:
            assert (upload / item["path"]).read_bytes() == (inputs["source_upload"] / item["path"]).read_bytes()
            output_files.append((Path(run.staged_deliverables_directory).parent / item["path"]).as_posix())
    assert sorted(path.relative_to(destination).as_posix() for path in destination.rglob("*") if path.is_file()) == sorted(output_files)
    again = materializer.materialize_codex_grading_input(run, **{**inputs, "destination": tmp_path / "second"})
    assert again.read_bytes() == result_path.read_bytes()
    assert before_source == inputs["inference_results"].read_bytes()
    assert before_identity == inputs["inference_identity"].read_bytes() and before_ledger == ledger.read_bytes()
    inspection = inspect_plan(manifest, grading_plan=plan.as_dict())
    assert inspection["configuration_valid"] is True
    assert inspection["launch_allowed"] is inspection["full_220_allowed"] is False
    assert "comparison_materialization_and_workflow_gates_not_wired" in inspection["launch_blockers"]
    assert [(row.condition, row.repeat) for row in plan.runs] == [("sandbox_v2", 1), ("codex", 1), ("codex", 2), ("sandbox_v2", 2)]
    assert run.input_materialization == "gpt54_codex_grading_input.materialize_codex_grading_input"
    assert len(REQUIRED_SOURCES) == 34
    sol = load_plan(ROOT / "batch-runner/experiments/execution_envelope/gpt56_sol_copilot_codex_pilot.yaml")
    parser = "batch-runner/gpt54_comparison_preflight.py"
    assert sol["source_pins"][parser] == hashlib.sha256((ROOT / parser).read_bytes()).hexdigest()
    assert not forbidden_calls and not list(tmp_path.glob(".*.tmp-*"))
