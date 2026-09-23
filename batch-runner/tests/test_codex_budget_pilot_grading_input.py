"""One offline CLI family: real compiler/materializer, synthetic output provenance.

No original inputs or provider state are accessed. HF repository/revision and
prepared fingerprint values below are deliberately synthetic external claims;
selection, result/artifact/ledger checks and private staging are real. As in
the parent materializer's tests, successful copies use a single-threaded test
double only at renameat2; a separate native case observes success or refusal.
"""

import copy
import ctypes
import errno
import hashlib
import json
import os
import socket
import stat
import subprocess
from pathlib import Path

import pytest

import codex_budget_pilot as pilot
import codex_budget_pilot_ci as ci
import codex_budget_pilot_grading_input as adapter
import gpt54_codex_grading_input as parent_entry
import gpt54_v2_grading_input as primitives
import step8_grade as grading
from core.codex_runtime_config import CodexProviderSettings
from core.cost_receipts import build_receipt, ledger_reference
from core.inference_manifest import bind_deliverable_file_records, validate_local_deliverables
from core.result_fingerprint import inference_result_fingerprint, validate_inference_result_fingerprint
from gpt54_comparison_preflight import _canonical_json, load_plan

SOURCE = "ea5dcc61c2beaad3a287d3d8dd064533ce33ed41"


def _write_json(path, value):
    data = (_canonical_json(value) + "\n").encode()
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def _fixture(root, plan, run, *, status="success"):
    config = json.loads(plan.dispatch.runs[0].config_json)
    workspace = root / "source" / "workspace"
    upload = workspace / "upload"
    upload.mkdir(parents=True)
    partial = build_receipt([{"stage": "generation", "state": "reserved"}]).as_dict()
    rows = []
    for task_id in run.task_ids:
        files = [f"deliverable_files/{task_id}/nested/answer.txt"] if status == "success" else []
        for relative in files:
            path = upload / relative
            path.parent.mkdir(parents=True)
            path.write_bytes(b"synthetic answer\r\n\x00preserve bytes\n")
        rows.append({
            "task_id": task_id, "status": status, "deliverable_files": files,
            "content": "synthetic text" if files else None,
            "deliverable_text": "synthetic text" if files else None,
            "model": config["condition_a"]["model"]["deployment"],
            "usage": None, "problem_solving_cost": partial, "grading_cost": None,
            "observability": {"preprocessors": []}, "latency_ms": 1.0,
            "timestamp": "2026-09-23T00:00:00+00:00", "reflection_history": [],
            "reflection_attempts": 0, **({"error": "synthetic failure"} if not files else {}),
        })
    rows = bind_deliverable_file_records(rows, upload)
    ledger = workspace / "cost_ledger_condition_a.jsonl"
    ledger.write_bytes(b'{"stage":"generation","state":"reserved"}\n')
    reference = ledger_reference(ledger.name, hashlib.sha256(ledger.read_bytes()).hexdigest())
    payload = {
        "experiment_id": run.run_id, "experiment_name": config["experiment"]["name"],
        "source": config["data"]["source"], "condition": config["condition_a"]["name"],
        "condition_identity": "condition_a", "run_id": run.run_id,
        "publication_generation": run.run_id + ":local:" + "a" * 32,
        "execution_mode": config["execution"]["mode"], "ordered_task_ids": list(run.task_ids),
        "prepared_fingerprint": "b" * 64, "model": config["condition_a"]["model"]["deployment"],
        "started_at": "2026-09-23T00:00:00+00:00", "completed_at": "2026-09-23T00:01:00+00:00",
        "resume_rounds_used": 0, "summary": {"total": len(rows), "qa_failed": 0,
            "success": len(rows) if status == "success" else 0,
            "error": 0 if status == "success" else len(rows)},
        "results": rows, "cost_ledger": reference,
        "fixture_extension": {"preserve_absent_null_and_raw_fields": [None, False, 1]},
    }
    result = workspace / "step2_inference_results_condition_a.json"
    identity_path = root / "source" / "approved_identity.json"
    identity = {
        "source_repo_id": "synthetic-owner/synthetic-cell-outputs", "source_revision": "e" * 40,
        "run_id": run.run_id, "condition": run.condition, "repeat": run.repeat,
        "task_ids": list(run.task_ids), "producer_results_path": run.producer_results_path,
        "producer_rows_pointer": run.producer_rows_pointer,
        "manifest_sha256": plan.dispatch.manifest_sha256,
        "grading_plan_sha256": hashlib.sha256(plan.canonical_bytes()).hexdigest(),
        "config_sha256": hashlib.sha256(plan.dispatch.runs[0].config_json.encode()).hexdigest(),
        "source_pins_sha256": hashlib.sha256(plan.dispatch.source_pins_json.encode()).hexdigest(),
        "cost_ledger": {**reference, "size": ledger.stat().st_size},
    }
    inputs = {
        "inference_results": result, "source_upload": upload, "inference_identity": identity_path,
        "destination": root / "installed",
    }
    _seal(payload, identity, inputs)
    return payload, identity, inputs


def _seal(payload, identity, inputs):
    payload["result_fingerprint"] = inference_result_fingerprint(payload)
    identity.update(
        inference_results_sha256=_write_json(inputs["inference_results"], payload),
        result_fingerprint=payload["result_fingerprint"], producer_run_id=payload["run_id"],
        publication_generation=payload["publication_generation"], prepared_fingerprint=payload["prepared_fingerprint"],
        deliverables=[{"task_id": row["task_id"], "files": row["deliverable_file_records"]} for row in payload["results"]],
    )
    inputs["approved_identity_sha256"] = _write_json(inputs["inference_identity"], identity)


@pytest.fixture(scope="module")
def compiled():
    return pilot.compile_pilot(ci.CAMPAIGN, SOURCE)


@pytest.fixture(autouse=True)
def no_execution(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("offline preparation attempted network, credentials, a child or grading")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(CodexProviderSettings, "auth_command", forbidden)
    monkeypatch.setattr("core.codex_runtime_config.AzureAIRouteSettings.from_env", forbidden)
    monkeypatch.setattr("core.llm_client.create_typed_azure_client", forbidden)
    monkeypatch.setattr(grading.Grader, "__init__", forbidden)
    monkeypatch.setattr(grading.RubricLoader, "__init__", forbidden)
    monkeypatch.setattr(grading, "preflight_routes", forbidden)
    monkeypatch.setattr(grading, "open_cost_recorder", forbidden)


CASES = [
    "valid_a1", "valid_b1", "valid_c1", "valid_c2", "valid_b2", "valid_last_a2",
    "parent_compatibility", "parent_refuses_pilot", "native_rename_boundary",
    "terminal_error", "ledger_absent", "ledger_null", "missing_accounting",
    "foreign_cell", "wrong_campaign", "invalid_source", "source_binding", "config_binding",
    "approval_hash", "extra_identity", "input_repo_as_output", "input_revision_as_output",
    "git_revision_as_output", "mutable_revision", "wrong_run", "foreign_task", "duplicate_task",
    "wrong_input", "prepared_binding", "result_hash", "result_fingerprint", "pending_result",
    "missing_result", "missing_file", "changed_file", "unsafe_path", "symlink_file", "hardlink_file",
    "extra_file", "missing_ledger", "changed_ledger", "existing_destination", "partial_destination",
    "destination_traversal", "source_overlap", "missing_cli_identity",
]


@pytest.mark.parametrize("case", CASES)
def test_pilot_cell_grading_input(case, compiled, tmp_path, monkeypatch, capsys):
    pilot_plan, parent, _ = compiled
    index = {"valid_b1": 1, "valid_c1": 2, "valid_c2": 3, "valid_b2": 4, "valid_last_a2": 29}.get(case, 0)
    cell = pilot_plan["cells"][index]
    _, _, plan = adapter.compile_cell_grading_plan(ci.CAMPAIGN, cell["cell_id"], SOURCE)
    run = plan.runs[0]
    assert len(run.task_ids) == 1 and run.run_id == cell["run_id"]
    assert run.command[run.command.index("--limit") + 1] == "1"
    assert run.grader_config_json == parent.runs[0].grader_config_json
    assert run.grader_contract_json == parent.runs[0].grader_contract_json
    if case == "parent_compatibility":
        plan = parent
        run = next(row for row in parent.runs if row.condition == "codex")
        # The fixture addresses its dispatch run explicitly; parent order is ABBA.
        from dataclasses import replace
        fixture_plan = replace(plan, dispatch=replace(plan.dispatch, runs=(next(
            spec for spec in plan.dispatch.runs if spec.run_id == run.run_id),)))
    else:
        fixture_plan = plan
    payload, identity, inputs = _fixture(tmp_path, fixture_plan, run,
        status="error" if case == "terminal_error" else "pending" if case == "pending_result" else "success")
    # Grading-plan identity uses the full unchanged parent plan in compatibility mode.
    identity["grading_plan_sha256"] = hashlib.sha256(plan.canonical_bytes()).hexdigest()
    row = payload["results"][0]
    ledger = inputs["inference_results"].with_name("cost_ledger_condition_a.jsonl")
    campaign, selected, source = ci.CAMPAIGN, cell["cell_id"], SOURCE
    if case == "foreign_cell":
        selected = cell["cell_id"] + "_foreign"
    elif case == "wrong_campaign":
        campaign += "_other"
    elif case == "invalid_source":
        source = "main"
    elif case == "source_binding":
        source = "d" * 40
    elif case == "wrong_run":
        payload["run_id"] = cell["run_id"] + "-other"
    elif case == "foreign_task":
        row["task_id"] = "00000000-0000-0000-0000-000000000000"
    elif case == "duplicate_task":
        payload["results"].append(copy.deepcopy(row))
    elif case == "wrong_input":
        payload["source"] = "synthetic-owner/not-originals"
    elif case == "unsafe_path":
        row["deliverable_files"] = ["../private-fixture.txt"]
    elif case in {"ledger_absent", "ledger_null"}:
        payload.pop("cost_ledger")
        if case == "ledger_null":
            payload["cost_ledger"] = None
        identity["cost_ledger"] = None
    elif case == "missing_accounting":
        row.pop("problem_solving_cost")
    _seal(payload, identity, inputs)
    for name, field, value in (
        ("config_binding", "config_sha256", "0" * 64),
        ("prepared_binding", "prepared_fingerprint", "c" * 64),
        ("extra_identity", "unapproved_field", "private-fixture-marker"),
        ("input_repo_as_output", "source_repo_id", pilot_plan["dataset"]["repo_id"]),
        ("input_revision_as_output", "source_revision", pilot_plan["dataset"]["revision"]),
        ("git_revision_as_output", "source_revision", SOURCE),
        ("mutable_revision", "source_revision", "main"),
    ):
        if case == name:
            identity[field] = value
    if case == "result_fingerprint":
        payload["result_fingerprint"] = "0" * 64
        identity["inference_results_sha256"] = _write_json(inputs["inference_results"], payload)
    inputs["approved_identity_sha256"] = _write_json(inputs["inference_identity"], identity)
    if case == "approval_hash":
        inputs["approved_identity_sha256"] = "0" * 64
    elif case == "result_hash":
        inputs["inference_results"].write_bytes(b'{"private-fixture-marker":true}\n')
    elif case == "missing_result":
        inputs["inference_results"].unlink()
    elif case in {"missing_file", "changed_file", "symlink_file", "hardlink_file"}:
        artifact = inputs["source_upload"] / row["deliverable_files"][0]
        if case == "missing_file":
            artifact.unlink()
        elif case == "changed_file":
            artifact.write_bytes(b"changed fixture bytes")
        else:
            moved = tmp_path / "private-fixture-marker"
            artifact.rename(moved)
            if case == "symlink_file":
                artifact.symlink_to(moved)
            else:
                os.link(moved, artifact)
    elif case == "extra_file":
        (inputs["source_upload"] / "not-a-deliverable.txt").write_bytes(b"private-fixture-marker")
    elif case == "missing_ledger":
        ledger.unlink()
    elif case == "changed_ledger":
        ledger.write_bytes(b"changed ledger bytes")
    elif case in {"existing_destination", "partial_destination"}:
        inputs["destination"].mkdir()
        if case == "partial_destination":
            (inputs["destination"] / "reservation").write_bytes(b"do not adopt")
    elif case == "destination_traversal":
        inputs["destination"] = tmp_path / "unused" / ".." / "installed"
    elif case == "source_overlap":
        inputs["destination"] = inputs["source_upload"] / "installed"
    before = {path: path.read_bytes() for path in (tmp_path / "source").rglob("*")
              if path.is_file() and not path.is_symlink()}
    destination_before = (list(inputs["destination"].iterdir())
                          if inputs["destination"].is_dir() else None)
    accepted = case.startswith("valid_") or case in {
        "parent_compatibility", "native_rename_boundary", "terminal_error", "ledger_absent", "ledger_null", "missing_accounting",
    }
    native_outcomes = []
    if case == "native_rename_boundary":
        native_rename = primitives._no_replace_rename()

        def observed_rename(*args):
            result = native_rename(*args)
            native_outcomes.append((result, ctypes.get_errno()))
            return result

        monkeypatch.setattr(primitives, "_no_replace_rename", lambda: observed_rename)
    elif accepted:
        def fixture_rename(source_fd, source, target_fd, target, flags):
            # Existing parent-test pattern, not a production portability fallback
            # or evidence of race-safe atomic commit on this NAS kernel.
            assert source_fd == target_fd and flags == 1
            assert not os.path.isabs(source) and not os.path.isabs(target)
            try:
                os.stat(target, dir_fd=target_fd, follow_symlinks=False)
            except FileNotFoundError:
                os.rename(source, target, src_dir_fd=source_fd, dst_dir_fd=target_fd)
                return 0
            ctypes.set_errno(errno.EEXIST)
            return -1

        monkeypatch.setattr(primitives, "_no_replace_rename", lambda: fixture_rename)
    else:
        def unexpected_install(*args, **kwargs):
            pytest.fail("invalid input reached publication instead of refusing at validation")

        monkeypatch.setattr(primitives, "_install", unexpected_install)
    if case == "parent_compatibility":
        result = parent_entry.materialize_codex_grading_input(run, manifest=load_plan(), **inputs)
        assert run.command[run.command.index("--limit") + 1] == "5"
        assert len(run.task_ids) == 5
    elif case == "parent_refuses_pilot":
        with pytest.raises(parent_entry.CodexGradingInputRefused, match="unknown comparison run"):
            parent_entry.materialize_codex_grading_input(run, manifest=load_plan(), **inputs)
        assert not inputs["destination"].exists()
        assert all(path.read_bytes() == data for path, data in before.items())
        return
    else:
        argv = ["--campaign-id", campaign, "--cell", selected, "--reviewed-source-sha", source]
        for key, value in inputs.items():
            if case == "missing_cli_identity" and key == "inference_identity":
                continue
            argv.extend(("--" + key.replace("_", "-"), str(value)))
        code = adapter.main(argv)
        captured = capsys.readouterr()
        assert str(tmp_path) not in captured.out + captured.err
        assert "private-fixture-marker" not in captured.out + captured.err
        if case == "native_rename_boundary" and code == 2:
            assert len(native_outcomes) == 1 and native_outcomes[0][0] == -1
            assert native_outcomes[0][1] in {errno.EINVAL, errno.ENOSYS, errno.EOPNOTSUPP}
            assert captured.out == "" and not inputs["destination"].exists()
            assert not list(tmp_path.glob(".*.tmp-*"))
            assert all(path.read_bytes() == data for path, data in before.items())
            with capsys.disabled():
                print(f"\nNative RENAME_NOREPLACE refused without residue (errno {native_outcomes[0][1]}); no fallback.")
            return
        assert code == (0 if accepted else 2)
        if not accepted:
            assert captured.out == "" and captured.err.startswith("Pilot grading input refused: ")
            if destination_before is None:
                assert not inputs["destination"].exists()
            else:
                assert list(inputs["destination"].iterdir()) == destination_before
                if case == "partial_destination":
                    assert (inputs["destination"] / "reservation").read_bytes() == b"do not adopt"
            assert all(path.read_bytes() == data for path, data in before.items())
            return
        preparation = json.loads(captured.out)
        assert preparation["source_identity"] == identity
        assert preparation["grading"]["state"] == "UNRUN"
        assert preparation["grading"]["config_sha256"] == run.output.config_sha256
        assert preparation["proof_boundary"] == "caller_approved_identity_not_provider_authentication"
        assert preparation["declared_inputs_sha256"] == pilot._digest(pilot_plan["dataset"])
        assert len(captured.out.encode()) <= adapter.MAX_PREPARATION_BYTES
        assert "synthetic text" not in captured.out and "fixture_extension" not in captured.out
        assert preparation["task_status"] == row["status"]
        assert preparation["successful_deliverable_present"] == (row["status"] == "success")
        result = inputs["destination"] / preparation["materialized_result"]["path"]
        assert preparation["materialized_result"]["sha256"] == hashlib.sha256(result.read_bytes()).hexdigest()
    assert stat.S_IMODE(inputs["destination"].stat().st_mode) == 0o700
    expected = {**payload, "source_repo_id": identity["source_repo_id"], "source_revision": identity["source_revision"],
                "source_identity_document_sha256": inputs["approved_identity_sha256"]}
    expected["result_fingerprint"] = inference_result_fingerprint(expected)
    assert result.read_bytes() == (_canonical_json(expected) + "\n").encode()
    output = json.loads(result.read_bytes())
    validate_inference_result_fingerprint(output)
    assert output["results"] == payload["results"] and output["summary"] == payload["summary"]
    if case != "missing_accounting":
        assert output["results"][0]["problem_solving_cost"]["status"] == "partial"
        assert output["results"][0]["problem_solving_cost"]["estimated_cost_usd"] is None
    else:
        assert "problem_solving_cost" not in output["results"][0]
    assert output["results"][0]["usage"] is output["results"][0]["grading_cost"] is None
    installed_upload = inputs["destination"] / Path(run.staged_deliverables_directory).parent
    expected_files = {run.inference_results_path}
    for item in identity["deliverables"]:
        for file in item["files"]:
            assert (installed_upload / file["path"]).read_bytes() == (inputs["source_upload"] / file["path"]).read_bytes()
            expected_files.add((installed_upload / file["path"]).relative_to(inputs["destination"]).as_posix())
    if identity["cost_ledger"] is not None:
        assert result.with_name(ledger.name).read_bytes() == ledger.read_bytes()
        expected_files.add(result.with_name(ledger.name).relative_to(inputs["destination"]).as_posix())
    assert {path.relative_to(inputs["destination"]).as_posix() for path in inputs["destination"].rglob("*")
            if path.is_file()} == expected_files
    with monkeypatch.context() as context:
        context.chdir(inputs["destination"] / "batch-runner")
        loaded = grading.load_local_inference_results()
        assert loaded == output
        assert grading.resolve_source_inference_identity(loaded, "2.0") == (identity["source_repo_id"], identity["source_revision"])
        assert validate_local_deliverables(loaded["results"], installed_upload) == loaded["results"]
    assert all(path.read_bytes() == data for path, data in before.items())
