"""One offline selector for the real Step 1 serializer and Step 2 entry gate."""

import ast
import errno
import json
import os
import shutil
import socket
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

import gpt54_codex_input_capture as capture
import gpt54_comparison_preflight as preflight
import gpt54_prepared_input_attestation as attester
import step1_prepare_tasks as step1
import step2_run_inference as step2
from core.codex_runtime_config import CodexProviderSettings
from core.experiment_config import CodexComparisonCapture, ExperimentConfig
from core.prepared_fingerprint import prepared_fingerprint
from core.result_fingerprint import inference_result_fingerprint
from .test_gpt54_prepared_input_attestation import (
    _bundle_fixture, _fixture, _identity, _input_bundle_fixture, _json, _tree_snapshot,
)


class ProviderBoundary(BaseException):
    """Stop at the first auth/provider seam, before constructing anything."""


def _runtime_fixture(tmp_path, monkeypatch, repeat):
    # This capture-unit fixture deliberately has no Git lineage. The dedicated
    # runtime-checkout selector exercises that outer gate with real temporary
    # Git; all capture/config/input/pin/fingerprint checks below remain real.
    def fixture_lineage(*, checkout, run_id, condition):
        assert condition == "codex" and run_id in CodexComparisonCapture.RUN_IDS
        return {"evidence_boundary": "capture_unit_fixture_no_git_lineage"}

    monkeypatch.setattr("gpt54_disposable_checkout.verify_runtime_checkout", fixture_lineage)
    oracle = tmp_path / "oracle"
    oracle.mkdir()
    inputs, bindings, _, _, records = _fixture(oracle, monkeypatch, "identical")
    index = repeat
    run = preflight.compile_grading_plan(inputs["manifest"]).dispatch.runs[index]
    root = tmp_path / run.run_id
    dataset_root = root / capture.DATASET_ROOT
    workspace = root / "batch-runner/workspace"
    config = root / capture.CONFIG_PATH
    _bundle_fixture(
        root, manifest=inputs["manifest"], combined_plan=inputs["combined_plan"], run=run,
    )
    _input_bundle_fixture(root, inputs=inputs, run=run)
    workspace.mkdir(parents=True)
    for module in (step1, step2):
        monkeypatch.setattr(module, "WORKSPACE_DIR", workspace)
        monkeypatch.setattr(module, "DEFAULT_LOCAL_PATH", dataset_root)
    payload = step1.prepare_tasks(str(config))
    capture_path = root / capture.CAPTURE_PATH
    # The independent #622 fixture constructs this oracle without the runtime
    # writer, while the call above uses the real serializer and atomic writer.
    assert capture_path.read_bytes() == _json(bindings[index])
    assert capture_path.stat().st_nlink == 1
    assert str(root).encode() not in capture_path.read_bytes()
    assert payload["config_path"] == "comparison-run.json"
    return root, run, payload, inputs, records


def _final_output_bytes(linkage):
    """Exercise the real final-output statements without a fake inference run."""
    tree = ast.parse(Path(step2.__file__).read_text())
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_run_inference_impl")
    attach = next(node for node in function.body if isinstance(node, ast.If)
                  and ast.unparse(node.test) == "verified_input_capture is not None")
    fingerprint = next(node for node in function.body if isinstance(node, ast.Assign)
                       and ast.unparse(node.targets[0]) == "final_output['result_fingerprint']")
    assert function.body.index(attach) < function.body.index(fingerprint)
    scope = {"final_output": {"results": []}, "verified_input_capture": linkage,
             "inference_result_fingerprint": inference_result_fingerprint}
    exec(compile(ast.Module(body=[attach, fingerprint], type_ignores=[]), step2.__file__, "exec"), scope)
    result = scope["final_output"]
    assert result["result_fingerprint"] == inference_result_fingerprint(result)
    return _json(result)


@pytest.mark.parametrize("case", [
    "r1", "r2", "default_absent_and_null", "relocated",
    "control_empty", "control_bool", "control_list", "control_extra", "control_version", "control_run",
    "capture_missing", "capture_extra", "capture_removed", "capture_null", "capture_duplicate_key",
    "capture_noncanonical", "capture_digest", "capture_symlink", "capture_hardlink",
    "config_bytes", "config_swap", "config_symlink", "config_hardlink",
    "prepared_fingerprint", "prepared_prompt_rehashed", "prepared_forged_capture", "prepared_task_order",
    "prepared_missing_task", "prepared_duplicate_task", "prepared_extra_task", "prepared_metadata",
    "prepared_reference", "prepared_effort", "prepared_capture_removed", "prepared_capture_null",
    "prepared_identity_removed", "prepared_config_path", "prepared_symlink", "prepared_hardlink",
    "parquet_bytes", "parquet_symlink", "parquet_hardlink", "parquet_extra_shard",
    "reference_bytes", "reference_missing", "reference_extra", "reference_symlink", "reference_hardlink",
    "reference_escape", "reference_root_symlink", "dataset_root_symlink",
    "manifest_control", "missing_source_pin", "changed_source_pin", "combined_plan",
    "cli_run", "cli_condition", "cli_mode", "cli_retries", "cli_retries_bool", "cli_rounds",
    "cli_resume", "cli_timeout", "checkpoint_only", "held_prepared_drift",
    "manifest_capture_removed", "manifest_capture_null", "prepared_duplicate_key", "prepared_extra_key",
    "step1_config_drift", "capture_collision", "prepared_collision", "prepared_collision_symlink",
    "capture_collision_race", "atomic_link_unavailable",
    "atomic_write_failure", "capture_parent_symlink",
])
def test_codex_comparison_capture_gates_real_step1_and_step2(case, tmp_path, monkeypatch):
    forbidden_calls, boundary_calls, events = [], [], []

    def forbidden(*args, **kwargs):
        forbidden_calls.append(True)
        pytest.fail("capture attempted network, subprocess, provider/auth/model/grader construction")

    def boundary(*args, **kwargs):
        boundary_calls.append("auth")
        events.append("auth_boundary")
        raise ProviderBoundary

    for module, name in ((subprocess, "Popen"), (subprocess, "run"), (socket.socket, "connect"),
                         (socket, "create_connection"), (CodexProviderSettings, "auth_command")):
        monkeypatch.setattr(module, name, forbidden)
    for name in ("create_provider_client", "create_typed_azure_client", "AzureAIClientFactory",
                 "preflight_routes", "TaskExecutor", "open_cost_recorder"):
        monkeypatch.setattr(step2, name, forbidden)
    for name in ("prepare_dataset.snapshot_download", "prepare_dataset.load_dataset",
                 "core.codex_runtime_config.resolve_endpoint_setting", "core.codex_runner.CodexAgentRunner",
                 "core.agentic_v2_model_voice.AzureFoundryVoice.__post_init__",
                 "step8_grade.Grader.__init__", "step8_grade.RubricLoader.__init__"):
        monkeypatch.setattr(name, forbidden)
    monkeypatch.setattr(step2.AzureAIRouteSettings, "from_env", boundary)
    monkeypatch.setenv("AZURE_AI_ROUTE_PROFILE", "offline-fixture")
    monkeypatch.setattr(step2, "_codex_connection_confirmed", lambda: True)
    monkeypatch.setattr(step2, "_require_host_may_carry_a_benchmark_run", lambda mode: events.append("host_gate"))

    root, run, payload, inputs, records = _runtime_fixture(tmp_path, monkeypatch, 2 if case == "r2" else 1)
    config_path, prepared_path = root / capture.CONFIG_PATH, root / capture.PREPARED_PATH
    capture_path, manifest_path = root / capture.CAPTURE_PATH, root / capture.MANIFEST_PATH
    dataset_root = root / capture.DATASET_ROOT
    parquet_path = dataset_root / "data" / capture.PARQUET_NAME
    reference_path = dataset_root / next(iter(records))
    kwargs = {"comparison_run_id": run.run_id, "resume": False, "max_retries": 0, "resume_max_rounds": 0}

    if case.startswith("control_"):
        config = json.loads(run.config_json)
        control = config["execution"]["comparison_input_capture"]
        invalid = {
            "control_empty": {}, "control_bool": True, "control_list": [],
            "control_extra": {**control, "verified": True},
            "control_version": {**control, "binding_version": "other"},
            "control_run": {**control, "run_id": "220"},
        }[case]
        config["execution"]["comparison_input_capture"] = invalid
        with pytest.raises(ValueError):
            ExperimentConfig.from_dict(config)
        assert forbidden_calls == boundary_calls == []
        return

    if case == "default_absent_and_null":
        config = preflight.load_plan(preflight.ROOT / preflight.CODEX_TEMPLATE)
        snapshots = []
        with monkeypatch.context() as legacy:
            legacy.setattr(capture, "write_codex_input_capture", forbidden)
            legacy.setattr(capture, "write_codex_prepared_and_capture", forbidden)
            legacy.setattr(capture, "verify_codex_input_capture", forbidden)
            for explicit_null in (False, True):
                if explicit_null:
                    config["execution"]["comparison_input_capture"] = None
                config_path.write_bytes(_json(config))
                parsed = ExperimentConfig.from_dict(config)
                assert parsed.execution.comparison_input_capture is None
                assert "comparison_input_capture" not in parsed.to_dict()["execution"]
                prepared = step1.prepare_tasks(str(config_path))
                assert "comparison_input_capture" not in prepared["execution"]
                snapshots.append(prepared_path.read_bytes())
                with pytest.raises(ProviderBoundary):
                    step2.run_inference(resume=False)
            assert snapshots[0] == snapshots[1]
        expected = {"results": []}
        expected["result_fingerprint"] = inference_result_fingerprint(expected)
        assert _final_output_bytes(None) == _json(expected)
        assert events == ["host_gate", "auth_boundary"] * 2
        assert forbidden_calls == []
        return

    if case in {"capture_collision", "prepared_collision", "prepared_collision_symlink", "capture_collision_race",
                "atomic_link_unavailable", "atomic_write_failure", "step1_config_drift"}:
        original_prepared = prepared_path.read_bytes()
        monkeypatch.setattr(step1, "resolve_publication_generation", lambda _: "different-generation")
        if case != "capture_collision":
            capture_path.unlink()
        if case not in {"capture_collision", "prepared_collision", "prepared_collision_symlink"}:
            prepared_path.unlink()
        if case == "prepared_collision_symlink":
            target = tmp_path / "untouched-prepared"
            prepared_path.rename(target)
            prepared_path.symlink_to(target)
        if case == "step1_config_drift":
            config = json.loads(config_path.read_bytes())
            config["execution"]["timeout"] += 1
            config_path.write_bytes(_json(config))
        elif case == "capture_collision_race":
            real_link = os.link

            def racing_link(*args, **kw):
                capture_path.write_bytes(b"someone else's capture")
                return real_link(*args, **kw)

            monkeypatch.setattr(capture.os, "link", racing_link)
        elif case in {"atomic_link_unavailable", "atomic_write_failure"}:
            def unsupported(*args, **kw):
                raise OSError(errno.ENOTSUP, "fixture unavailable")
            monkeypatch.setattr(capture.os, "link" if case == "atomic_link_unavailable" else "fsync", unsupported)
        original = capture_path.read_bytes() if capture_path.exists() else None
        with pytest.raises(capture.CodexInputCaptureRefused):
            step1.prepare_tasks(str(config_path))
        assert not list(prepared_path.parent.glob(".input-capture-*"))
        if case == "capture_collision":
            assert capture_path.read_bytes() == original
        elif case == "capture_collision_race":
            assert capture_path.read_bytes() == b"someone else's capture"
        else:
            assert not capture_path.exists()
        if case in {"capture_collision", "prepared_collision", "prepared_collision_symlink"}:
            assert prepared_path.read_bytes() == original_prepared
        assert forbidden_calls == boundary_calls == []
        return

    if case == "relocated":
        relocated = tmp_path / "another-host-role"
        shutil.copytree(root, relocated)
        root = relocated
        for module in (step1, step2):
            monkeypatch.setattr(module, "WORKSPACE_DIR", root / "batch-runner/workspace")
            monkeypatch.setattr(module, "DEFAULT_LOCAL_PATH", root / capture.DATASET_ROOT)
    elif case == "capture_missing":
        capture_path.unlink()
    elif case in {"capture_extra", "capture_removed", "capture_null", "capture_digest"}:
        value = json.loads(capture_path.read_bytes())
        if case == "capture_extra":
            value["verified"] = True
        elif case == "capture_removed":
            value.pop("consumer")
        elif case == "capture_null":
            value = None
        else:
            value["config_sha256"] = "0" * 64
        capture_path.write_bytes(_json(value))
    elif case == "capture_duplicate_key":
        capture_path.write_bytes(b'{"run_id":"duplicate",' + capture_path.read_bytes()[1:])
    elif case == "capture_noncanonical":
        capture_path.write_bytes(capture_path.read_bytes() + b"\n")
    elif case == "config_bytes":
        config_path.write_bytes(config_path.read_bytes() + b"\n")
    elif case == "config_swap":
        config_path.write_bytes(inputs["runs"][2].generated_config.read_bytes())
    elif case in {"manifest_control", "missing_source_pin", "changed_source_pin", "manifest_capture_removed", "manifest_capture_null"}:
        manifest = json.loads(manifest_path.read_bytes())
        source = "batch-runner/gpt54_codex_input_capture.py"
        if case == "manifest_control":
            manifest["shared"]["model"]["reasoning_effort"] = "high"
        elif case == "manifest_capture_removed":
            manifest["conditions"]["codex"].pop("input_capture")
        elif case == "manifest_capture_null":
            manifest["conditions"]["codex"]["input_capture"] = None
        elif case == "missing_source_pin":
            manifest["source_pins"].pop(source)
        else:
            manifest["source_pins"][source] = "0" * 64
        manifest_path.write_bytes(_json(manifest))
    elif case == "combined_plan":
        plan = dict(inputs["combined_plan"], launch_allowed=True)
        (root / capture.COMBINED_PLAN_PATH).write_bytes(_json(plan))
    elif case == "parquet_bytes":
        parquet_path.write_bytes(parquet_path.read_bytes() + b"drift")
    elif case == "parquet_extra_shard":
        (parquet_path.parent / "train-extra.parquet").write_bytes(parquet_path.read_bytes())
    elif case in {"reference_bytes", "reference_missing", "reference_extra"}:
        if case == "reference_bytes":
            reference_path.write_bytes(reference_path.read_bytes() + b"drift")
        elif case == "reference_missing":
            reference_path.unlink()
        else:
            (dataset_root / "reference_files/extra.txt").write_bytes(b"extra")
    elif case.endswith(("_symlink", "_hardlink")):
        name = case.rsplit("_", 1)[0]
        path = {"capture": capture_path, "prepared": prepared_path, "config": config_path,
                "parquet": parquet_path, "reference": reference_path,
                "reference_root": dataset_root / "reference_files", "dataset_root": dataset_root,
                "capture_parent": prepared_path.parent}[name]
        moved = tmp_path / "unsafe-target"
        path.rename(moved)
        if case.endswith("_symlink"):
            path.symlink_to(moved, target_is_directory=moved.is_dir())
        else:
            os.link(moved, path)
    elif case == "prepared_duplicate_key":
        prepared_path.write_bytes(b'{"experiment_id":"duplicate",' + prepared_path.read_bytes()[1:])
    elif case.startswith("prepared_") or case == "reference_escape":
        if case in {"prepared_prompt_rehashed", "prepared_forged_capture"}:
            payload["tasks"][0]["instruction"] += " modified"
        elif case == "prepared_metadata":
            payload["tasks"][0]["occupation"] += " modified"
        elif case == "prepared_task_order":
            payload["tasks"].reverse()
        elif case == "prepared_missing_task":
            payload["tasks"].pop()
        elif case == "prepared_duplicate_task":
            payload["tasks"][1] = payload["tasks"][0]
        elif case == "prepared_extra_task":
            payload["tasks"].append(dict(payload["tasks"][0], task_id="extra"))
        elif case == "prepared_reference":
            next(row for row in payload["tasks"] if row["reference_files"])["reference_file_records"][0]["sha256"] = "0" * 64
        elif case == "reference_escape":
            payload["tasks"][0]["reference_files"] = ["../escape"]
        elif case == "prepared_effort":
            payload["execution"]["codex"]["reasoning_effort"] = "high"
        elif case in {"prepared_capture_removed", "prepared_identity_removed"}:
            payload["execution"].pop("comparison_input_capture")
            if case == "prepared_identity_removed":
                payload["experiment_id"] = "exp_legacy"
            else:
                kwargs.pop("comparison_run_id")  # The reserved identity still requires capture.
        elif case == "prepared_capture_null":
            payload["execution"]["comparison_input_capture"] = None
        elif case == "prepared_config_path":
            payload["config_path"] = str(config_path)
        elif case == "prepared_extra_key":
            payload["verified"] = True
        payload["prepared_fingerprint"] = "0" * 64 if case == "prepared_fingerprint" else prepared_fingerprint(payload)
        prepared_path.write_bytes(_json(payload))
        if case == "prepared_forged_capture":
            forged = json.loads(capture_path.read_bytes())
            forged["consumer"].update(tasks=payload["tasks"], prepared_fingerprint=payload["prepared_fingerprint"],
                                      prepared_file=_identity(prepared_path.read_bytes()))
            capture_path.write_bytes(_json(forged))
    elif case.startswith("cli_"):
        key, value = {
            "cli_run": ("comparison_run_id", CodexComparisonCapture.RUN_IDS[1]),
            "cli_condition": ("condition_key", "condition_b"), "cli_mode": ("execution_mode", "subprocess"),
            "cli_retries": ("max_retries", 1), "cli_retries_bool": ("max_retries", False),
            "cli_rounds": ("resume_max_rounds", 1), "cli_resume": ("resume", True),
            "cli_timeout": ("wall_timeout", 1),
        }[case]
        kwargs[key] = value
    elif case == "held_prepared_drift":
        payload["tasks"][0]["instruction"] += " held object differs"
        with pytest.raises(capture.CodexInputCaptureRefused):
            step2._comparison_input_gate(payload, **kwargs)
        assert forbidden_calls == boundary_calls == []
        return

    before = _tree_snapshot(root)
    if case in {"r1", "r2", "relocated"}:
        linkage = step2._comparison_input_gate(payload, **kwargs)
        assert linkage["sha256"] == _identity(capture_path.read_bytes())["sha256"]
        assert linkage["attestation_linkage"]["run_id"] == run.run_id
        assert linkage["attestation_linkage"]["repeat"] == run.repeat
        supplied = list(inputs["runs"])
        supplied[run.repeat] = replace(supplied[run.repeat], input_binding=root / capture.CAPTURE_PATH,
                                      prepared_tasks=root / capture.PREPARED_PATH, generated_config=root / capture.CONFIG_PATH)
        attestation = attester.compile_prepared_input_attestation(**{**inputs, "runs": tuple(supplied)})
        assert attestation.as_dict()["runs"][run.repeat]["binding_file"] == {key: linkage[key] for key in ("size", "sha256")}
        output = json.loads(_final_output_bytes(linkage))
        assert output["pre_execution_input_capture"] == linkage
        assert _final_output_bytes({**linkage, "sha256": "0" * 64}) != _final_output_bytes(linkage)
        with pytest.raises(ProviderBoundary):
            step2.run_inference(**kwargs)
        assert events == ["host_gate", "auth_boundary"]
        assert boundary_calls == ["auth"]
        assert inputs["combined_plan"]["launch_allowed"] is inputs["combined_plan"]["full_220_allowed"] is False
        assert "comparison_materialization_and_workflow_gates_not_wired" in preflight.LAUNCH_BLOCKERS
        if case == "r1":
            inspection = preflight.inspect_plan(inputs["manifest"], grading_plan=inputs["combined_plan"])
            assert inspection["configuration_valid"] is True
            assert inspection["codex_pre_execution_capture"]["required_runs"] == list(CodexComparisonCapture.RUN_IDS)
            assert len(preflight.REQUIRED_SOURCES) == 34
            sol = preflight.load_plan(preflight.ROOT / preflight.ENVELOPE / "gpt56_sol_copilot_codex_pilot.yaml")
            for path in ("batch-runner/gpt54_comparison_preflight.py", "batch-runner/core/experiment_config.py",
                         "batch-runner/step1_prepare_tasks.py", "batch-runner/step2_run_inference.py"):
                assert sol["source_pins"][path] == _identity((preflight.ROOT / path).read_bytes())["sha256"]
    else:
        with pytest.raises(capture.CodexInputCaptureRefused):
            if case == "checkpoint_only":
                step2.validate_restored_checkpoint(comparison_run_id=run.run_id)
            else:
                step2.run_inference(**kwargs)
        assert boundary_calls == events == []
    assert _tree_snapshot(root) == before
    assert forbidden_calls == []
