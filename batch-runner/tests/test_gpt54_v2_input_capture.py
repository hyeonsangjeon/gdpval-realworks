"""One offline selector for the real V2 CLI gate, plus minimal Codex regression."""

import ast
import errno
import json
import os
import socket
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

import gpt54_codex_input_capture as writer
import gpt54_comparison_preflight as preflight
import gpt54_prepared_input_attestation as attester
import gpt54_v2_input_capture as capture
from core.codex_runtime_config import CodexProviderSettings
from scripts import run_agentic_v2_stage as runner
from .test_gpt54_codex_input_capture import (
    ProviderBoundary, test_codex_comparison_capture_gates_real_step1_and_step2 as _codex_regression,
)
from .test_gpt54_prepared_input_attestation import (
    _bundle_fixture, _fixture, _identity, _input_bundle_fixture, _json, _tree_snapshot,
)


def _runtime_fixture(tmp_path, monkeypatch, repeat):
    # This capture-unit fixture deliberately has no Git lineage. The dedicated
    # runtime-checkout selector exercises that outer gate with real temporary
    # Git; all capture/config/input/pin/fingerprint checks below remain real.
    def fixture_lineage(*, checkout, run_id, condition):
        assert condition == "sandbox_v2" and run_id in capture.V2ComparisonCapture.RUN_IDS
        return {"evidence_boundary": "capture_unit_fixture_no_git_lineage"}

    monkeypatch.setattr("gpt54_disposable_checkout.verify_runtime_checkout", fixture_lineage)
    oracle = tmp_path / "oracle"
    oracle.mkdir()
    inputs, bindings, _, _, records = _fixture(oracle, monkeypatch, "identical")
    index = 0 if repeat == 1 else 3
    run = preflight.compile_grading_plan(inputs["manifest"]).dispatch.runs[index]
    root = tmp_path / run.run_id
    workspace = root / "batch-runner/workspace"
    _bundle_fixture(
        root, manifest=inputs["manifest"], combined_plan=inputs["combined_plan"], run=run,
    )
    _input_bundle_fixture(root, inputs=inputs, run=run)
    workspace.mkdir(parents=True)
    monkeypatch.setattr(runner, "load_task_catalog", preflight.load_task_catalog)
    monkeypatch.setattr(runner, "catalog_sha256", preflight.catalog_sha256)
    return root, run, inputs, bindings[index], records


def _record_conditions(linkage):
    """Execute the actual record-attachment statements without running tasks."""
    tree = ast.parse(Path(runner.__file__).read_text())
    main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main")
    attach = next(node for node in main.body if isinstance(node, ast.If)
                  and ast.unparse(node.test) == "verified_input_capture is not None")
    serialize = next(node for node in main.body if isinstance(node, ast.Assign)
                     and ast.unparse(node.targets[0]) == "written")
    assert main.body.index(attach) < main.body.index(serialize)
    original = {"request_conditions": {
        "plan_file": {"path": "legacy-plan.yaml", "sha256": "legacy-digest"},
        "instructions": {"sha256": "unchanged"}, "replay_format": "faithful",
    }}
    scope = {"record": json.loads(_json(original)), "verified_input_capture": linkage, "json": json}
    exec(compile(ast.Module(body=[attach, serialize], type_ignores=[]), runner.__file__, "exec"), scope)
    if linkage is None:
        assert scope["written"] == json.dumps(original, indent=2, sort_keys=True, default=str)
    return json.loads(scope["written"])["request_conditions"]


@pytest.mark.parametrize("case", [
    "r1", "r2", "relative_argv", "new_workspace", "default_absent_and_null",
    "control_empty", "control_bool", "control_list", "control_extra", "control_version",
    "control_removed", "control_null", "run_missing", "run_other", "run_codex", "run_whitespace",
    "stage", "shard", "dry_run", "rehearse", "isolated_approval", "workspace_missing", "dataset_missing",
    "plan_bytes", "plan_task_order", "plan_missing_task", "plan_extra_task", "plan_duplicate_task",
    "plan_effort", "plan_limit", "held_plan_drift", "held_task_drift", "held_task_order",
    "manifest_control", "manifest_capture_removed", "manifest_capture_null", "source_pin_missing",
    "source_pin_changed", "combined_plan", "parquet_bytes", "parquet_extra_shard",
    "reference_bytes", "reference_missing", "reference_extra", "path_escape",
    "plan_symlink", "plan_hardlink", "parquet_symlink", "parquet_hardlink",
    "reference_symlink", "reference_hardlink", "dataset_symlink", "workspace_symlink",
    "capture_collision", "capture_symlink_collision", "resume_journal", "resume_deliverables",
    "capture_race", "capture_extra", "capture_removed", "capture_null", "capture_digest",
    "capture_noncanonical", "capture_symlink", "capture_hardlink", "post_publish_plan_drift",
    "post_publish_parquet_drift", "post_publish_reference_drift", "atomic_link_unavailable", "atomic_write_failure",
    "codex_r1", "codex_r2", "codex_default_absent_and_null",
])
def test_v2_comparison_capture_gates_stage_before_provider(case, tmp_path, monkeypatch):
    if case.startswith("codex_"):
        _codex_regression(case.removeprefix("codex_"), tmp_path, monkeypatch)
        return

    forbidden_calls, events = [], []

    def forbidden(*args, **kwargs):
        forbidden_calls.append(True)
        pytest.fail("capture attempted network, subprocess, provider/auth/model/grader/VM construction")

    def auth_boundary(*args, **kwargs):
        events.append("auth_boundary")
        raise ProviderBoundary

    for module, name in ((subprocess, "Popen"), (subprocess, "run"), (socket.socket, "connect"),
                         (socket, "create_connection"), (CodexProviderSettings, "auth_command")):
        monkeypatch.setattr(module, name, forbidden)
    for name in ("prepare_dataset.snapshot_download", "prepare_dataset.load_dataset",
                 "core.llm_client.create_typed_azure_client", "core.codex_runtime_config.resolve_endpoint_setting",
                 "core.codex_runner.CodexAgentRunner", "core.agentic_v2_model_voice.AzureFoundryVoice.__post_init__",
                 "core.agentic_v2_rehearsal_voice.RehearsalVoice.__init__",
                 "step8_grade.Grader.__init__", "step8_grade.RubricLoader.__init__",
                 "core.agentic_v2_fixture_backend.AgenticV2FixtureBackend.__init__",
                 "core.agentic_v2_microvm_backend.AgenticV2MicroVMBackend.__init__"):
        monkeypatch.setattr(name, forbidden)
    for name in ("run_manifest", "the_paid_setup_a_dry_run_can_reach", "open_the_ledger"):
        monkeypatch.setattr(runner, name, forbidden)
    monkeypatch.setattr("core.azure_ai_clients.AzureAIRouteSettings.from_env", auth_boundary)

    root, run, inputs, oracle, records = _runtime_fixture(tmp_path, monkeypatch, 2 if case == "r2" else 1)
    config_path = root / writer.CONFIG_PATH
    capture_path = root / writer.CAPTURE_PATH
    workspace = capture_path.parent
    dataset_root = root / writer.DATASET_ROOT
    parquet_path = dataset_root / "data" / writer.PARQUET_NAME
    reference_path = dataset_root / next(iter(records))
    manifest_path = root / writer.MANIFEST_PATH
    options = {
        "--stage": "advance_check_5", "--plan": str(config_path),
        "--parquet": str(parquet_path), "--dataset-root": str(dataset_root),
        "--into": str(workspace), "--run-id": run.run_id,
    }
    flags = []
    real_binding, real_write = capture._binding, writer._write_no_clobber

    def observed_binding(*args, **kwargs):
        events.append("recompute" if kwargs.get("held_bound") is not None else "snapshot")
        return real_binding(*args, **kwargs)

    def observed_write(path, data):
        events.append("publish")
        return real_write(path, data)

    monkeypatch.setattr(capture, "_binding", observed_binding)
    monkeypatch.setattr(writer, "_write_no_clobber", observed_write)
    observed_linkage = []
    real_gate = runner.capture_v2_pre_execution_input

    def observed_gate(*args, **kwargs):
        result = real_gate(*args, **kwargs)
        if result is not None:
            observed_linkage.append(result[1])
        return result

    monkeypatch.setattr(runner, "capture_v2_pre_execution_input", observed_gate)
    # The existing free budget/voice-safety preflight is not under test and can
    # construct stand-in voices. Substitute its verdict, not the capture gate,
    # source/compiler/projection, instructions, binding or CLI. No authorization
    # is inferred from this fixture; the first real auth seam always stops.
    def free_preflight(plan, **kwargs):
        events.append("free_preflight")
        chosen = SimpleNamespace(**plan["cost"]["chosen_settings"])
        return SimpleNamespace(may_start=True, chosen=chosen, problems=[])

    monkeypatch.setattr(runner, "run_stage_one_preflight", free_preflight)
    select_backend = runner.select_backend

    def observed_backend_selection(*args, **kwargs):
        events.append("backend_selection")
        return select_backend(*args, **kwargs)

    monkeypatch.setattr(runner, "select_backend", observed_backend_selection)

    def invoke():
        argv = ["run_agentic_v2_stage.py"]
        for key, value in options.items():
            argv.extend((key, value))
        monkeypatch.setattr(sys, "argv", argv + flags)
        return runner.main()

    if case == "default_absent_and_null":
        plan = json.loads(run.config_json)
        plan.pop("comparison_input_capture")
        options["--run-id"] = "legacy-run"
        before = _tree_snapshot(workspace)
        snapshots = []
        with monkeypatch.context() as legacy:
            legacy.setattr(capture, "_binding", forbidden)
            legacy.setattr(writer, "_write_no_clobber", forbidden)
            for explicit_null in (False, True):
                if explicit_null:
                    plan["comparison_input_capture"] = None
                config_path.write_bytes(_json(plan))
                with pytest.raises(ProviderBoundary):
                    invoke()
                snapshots.append(runner.reasoning_request_fields(plan["model"]["reasoning_effort"]))
            assert snapshots[0] == snapshots[1] == {"reasoning": {"effort": "xhigh"}}
        assert events == ["free_preflight", "backend_selection", "auth_boundary"] * 2
        assert _tree_snapshot(workspace) == before
        assert "pre_execution_input_capture" not in _record_conditions(None)
        assert forbidden_calls == []
        return

    if case.startswith("control_"):
        plan = json.loads(run.config_json)
        control = plan["comparison_input_capture"]
        if case == "control_removed":
            plan.pop("comparison_input_capture")
        else:
            plan["comparison_input_capture"] = {
                "control_empty": {}, "control_bool": True, "control_list": [],
                "control_extra": {**control, "verified": True},
                "control_version": {"binding_version": "other"}, "control_null": None,
            }[case]
        config_path.write_bytes(_json(plan))
    elif case.startswith("run_"):
        if case == "run_missing":
            options.pop("--run-id")
        else:
            options["--run-id"] = {"run_other": "other", "run_codex": inputs["runs"][1].run_id,
                                   "run_whitespace": run.run_id + " "}[case]
    elif case in {"stage", "shard", "isolated_approval", "path_escape"}:
        key, value = {
            "stage": ("--stage", "trial_30"), "shard": ("--shard", "1/1"),
            "isolated_approval": ("--isolated-approval", str(tmp_path / "must-not-be-read")),
            "path_escape": ("--parquet", str(parquet_path.parent / ".." / "data" / parquet_path.name)),
        }[case]
        options[key] = value
    elif case in {"dry_run", "rehearse"}:
        flags.append("--dry-run" if case == "dry_run" else "--rehearse")
    elif case in {"workspace_missing", "dataset_missing"}:
        options.pop("--into" if case == "workspace_missing" else "--dataset-root")
    elif case in {"relative_argv", "new_workspace"}:
        if case == "new_workspace":
            workspace.rmdir()
        else:
            monkeypatch.chdir(root / "batch-runner")
            options.update({"--plan": "comparison-run.json", "--parquet": "../" + writer.DATASET_ROOT + "/data/" + writer.PARQUET_NAME,
                            "--dataset-root": "../" + writer.DATASET_ROOT, "--into": "workspace"})
    elif case.startswith("plan_") and case not in {"plan_symlink", "plan_hardlink"}:
        plan = json.loads(run.config_json)
        if case == "plan_bytes":
            config_path.write_bytes(config_path.read_bytes() + b"\n")
        else:
            if case == "plan_task_order":
                plan["task_ids"].reverse()
            elif case == "plan_missing_task":
                plan["task_ids"].pop()
            elif case == "plan_extra_task":
                plan["task_ids"].append("extra")
            elif case == "plan_duplicate_task":
                plan["task_ids"][1] = plan["task_ids"][0]
            elif case == "plan_effort":
                plan["model"]["reasoning_effort"] = "high"
            else:
                plan["fixed_settings"]["per_task_timeout_seconds"] += 1
            config_path.write_bytes(_json(plan))
    elif case == "held_plan_drift":
        load = runner.load_stage_one_plan

        def changed_held_plan(path):
            plan = load(path)
            plan["instructions"] += " held object drift"
            return plan

        monkeypatch.setattr(runner, "load_stage_one_plan", changed_held_plan)
    elif case in {"held_task_drift", "held_task_order"}:
        def changed_held_tasks(*args, **kwargs):
            bound, binding = observed_binding(*args, **kwargs)
            if kwargs.get("held_bound") is None:
                tasks = list(bound.tasks)
                if case == "held_task_drift":
                    tasks[0] = replace(tasks[0], prompt=tasks[0].prompt + " drift")
                else:
                    tasks.reverse()
                bound = replace(bound, tasks=tuple(tasks))
            return bound, binding

        monkeypatch.setattr(capture, "_binding", changed_held_tasks)
    elif case.startswith("manifest_") or case.startswith("source_pin_"):
        manifest = json.loads(manifest_path.read_bytes())
        if case == "manifest_control":
            manifest["shared"]["model"]["reasoning_effort"] = "high"
        elif case == "manifest_capture_removed":
            manifest["conditions"]["sandbox_v2"].pop("input_capture")
        elif case == "manifest_capture_null":
            manifest["conditions"]["sandbox_v2"]["input_capture"] = None
        elif case == "source_pin_missing":
            manifest["source_pins"].pop("batch-runner/gpt54_v2_input_capture.py")
        else:
            manifest["source_pins"]["batch-runner/gpt54_v2_input_capture.py"] = "0" * 64
        manifest_path.write_bytes(_json(manifest))
    elif case == "combined_plan":
        (root / writer.COMBINED_PLAN_PATH).write_bytes(_json(dict(inputs["combined_plan"], launch_allowed=True)))
    elif case == "parquet_bytes":
        parquet_path.write_bytes(parquet_path.read_bytes() + b"drift")
    elif case == "parquet_extra_shard":
        (parquet_path.parent / "extra.parquet").write_bytes(parquet_path.read_bytes())
    elif case == "reference_bytes":
        reference_path.write_bytes(reference_path.read_bytes() + b"drift")
    elif case == "reference_missing":
        reference_path.unlink()
    elif case == "reference_extra":
        (dataset_root / "reference_files/extra.txt").write_bytes(b"extra")
    elif case in {"capture_collision", "capture_symlink_collision", "resume_journal", "resume_deliverables"}:
        if case == "capture_collision":
            capture_path.write_bytes(b"existing capture must remain intact")
        elif case == "capture_symlink_collision":
            capture_path.symlink_to(config_path)
        elif case == "resume_journal":
            (workspace / "journal.jsonl").write_bytes(b"previous run")
        else:
            (workspace / "deliverables").mkdir()
    elif case.endswith(("_symlink", "_hardlink")) and not case.startswith("capture_"):
        path = {"plan": config_path, "parquet": parquet_path, "reference": reference_path,
                "dataset": dataset_root, "workspace": workspace}[case.rsplit("_", 1)[0]]
        moved = tmp_path / "unsafe-target"
        path.rename(moved)
        if case.endswith("_symlink"):
            path.symlink_to(moved, target_is_directory=moved.is_dir())
        else:
            os.link(moved, path)
    elif case in {"capture_race", "atomic_link_unavailable", "atomic_write_failure"}:
        real_link = os.link

        def atomic_failure(*args, **kwargs):
            if case == "capture_race":
                capture_path.write_bytes(b"concurrent capture")
                return real_link(*args, **kwargs)
            raise OSError(errno.ENOTSUP, "offline unavailable primitive")

        monkeypatch.setattr(writer.os, "fsync" if case == "atomic_write_failure" else "link", atomic_failure)
    elif case.startswith(("capture_", "post_publish_")):
        def tamper_after_publish(path, data):
            observed_write(path, data)
            if case.startswith("post_publish_"):
                changed = {"post_publish_plan_drift": config_path, "post_publish_parquet_drift": parquet_path,
                           "post_publish_reference_drift": reference_path}[case]
                changed.write_bytes(changed.read_bytes() + b" ")
            elif case in {"capture_symlink", "capture_hardlink"}:
                moved = tmp_path / "capture-target"
                path.rename(moved)
                path.symlink_to(moved) if case.endswith("_symlink") else os.link(moved, path)
            elif case == "capture_noncanonical":
                path.write_bytes(data + b"\n")
            else:
                changed = json.loads(data)
                if case == "capture_extra":
                    changed["verified"] = True
                elif case == "capture_removed":
                    changed.pop("consumer")
                elif case == "capture_null":
                    changed = None
                else:
                    changed["config_sha256"] = "0" * 64
                path.write_bytes(_json(changed))

        monkeypatch.setattr(writer, "_write_no_clobber", tamper_after_publish)

    before = _tree_snapshot(workspace) if workspace.exists() and not workspace.is_symlink() else None
    if case in {"r1", "r2", "relative_argv", "new_workspace"}:
        with pytest.raises(ProviderBoundary):
            invoke()
        assert events == ["snapshot", "publish", "recompute", "free_preflight", "backend_selection", "auth_boundary"]
        assert capture_path.read_bytes() == _json(oracle)
        assert capture_path.stat().st_nlink == 1
        assert str(root).encode() not in capture_path.read_bytes()
        index = 0 if run.repeat == 1 else 3
        supplied = list(inputs["runs"])
        supplied[index] = replace(supplied[index], generated_config=config_path, input_binding=capture_path)
        attestation = attester.compile_prepared_input_attestation(**{**inputs, "runs": tuple(supplied)})
        identity = _identity(capture_path.read_bytes())
        assert len(observed_linkage) == 1
        linkage = observed_linkage[0]
        assert {key: linkage[key] for key in ("size", "sha256")} == identity
        assert linkage["attestation_linkage"]["run_id"] == run.run_id
        assert linkage["attestation_linkage"]["repeat"] == run.repeat
        assert linkage["attestation_linkage"]["condition"] == "sandbox_v2"
        assert linkage["attestation_linkage"]["config_sha256"] == _identity(config_path.read_bytes())["sha256"]
        conditions = _record_conditions(linkage)
        assert conditions["pre_execution_input_capture"] == linkage
        # Existing V2 materialization reads plan_file relative to the dispatch
        # working directory, not the capture's checkout-relative namespace.
        assert conditions["plan_file"] == {
            "path": Path(run.config_path).relative_to(run.working_directory).as_posix(),
            "sha256": linkage["attestation_linkage"]["config_sha256"],
        }
        assert conditions["plan_file"]["path"] == "comparison-run.json"
        assert attestation.as_dict()["runs"][index]["binding_file"] == identity
        assert inputs["combined_plan"]["launch_allowed"] is inputs["combined_plan"]["full_220_allowed"] is False
        inspection = preflight.inspect_plan(inputs["manifest"], grading_plan=inputs["combined_plan"])
        assert inspection["configuration_valid"] is True
        assert inspection["v2_pre_execution_capture"]["required_runs"] == list(capture.V2ComparisonCapture.RUN_IDS)
        assert len(preflight.REQUIRED_SOURCES) == 37
        compiled = preflight.compile_dispatch_plan(inputs["manifest"])
        assert compiled.runs[0].config_json == compiled.runs[3].config_json
    else:
        assert invoke() == 1
        assert "auth_boundary" not in events and "free_preflight" not in events
        assert "backend_selection" not in events
        if before is not None and "publish" not in events:
            assert _tree_snapshot(workspace) == before
        if case == "capture_race":
            assert capture_path.read_bytes() == b"concurrent capture"
        elif case.startswith("atomic_"):
            assert not capture_path.exists()
    if workspace.is_dir() and not workspace.is_symlink():
        assert not list(workspace.glob(".input-capture-*"))
    assert forbidden_calls == []
