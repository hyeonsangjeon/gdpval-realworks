"""One free selector for exact, no-clobber run bundles and their runtime gates."""

import json
import os
import socket
import subprocess
import sys
from dataclasses import replace

import pytest

import gpt54_codex_input_capture as writer
import gpt54_comparison_preflight as preflight
import gpt54_run_config_bundle as bundle
import step2_run_inference as step2
from core.codex_runtime_config import CodexProviderSettings
from scripts import run_agentic_v2_stage as runner
from .test_gpt54_codex_input_capture import (
    _runtime_fixture as _codex_fixture,
    test_codex_comparison_capture_gates_real_step1_and_step2 as _codex_regression,
)
from .test_gpt54_prepared_input_attestation import (
    _bundle_fixture, _identity, _json, _tree_snapshot,
)
from .test_gpt54_v2_input_capture import (
    _runtime_fixture as _v2_fixture,
    test_v2_comparison_capture_gates_stage_before_provider as _v2_regression,
)


def _files(plan, index):
    """Use public recipe fields, not the materializer's private inventory."""
    run, grading = plan.dispatch.runs[index], plan.runs[index]
    return {
        "comparison-plan.json": plan.canonical_bytes(),
        run.config_path: run.config_json.encode("utf-8"),
        grading.grader_config_path: grading.grader_config_json.encode("utf-8"),
        grading.experiment_config_path: grading.experiment_config_json.encode("utf-8"),
    }


def _guards(monkeypatch):
    calls = []

    def forbidden(*args, **kwargs):
        calls.append(True)
        pytest.fail("bundle attempted process/network/auth/provider/model/grader/VM execution")

    for module, name in (
        (subprocess, "Popen"), (subprocess, "run"),
        (socket.socket, "connect"), (socket, "create_connection"),
        (CodexProviderSettings, "auth_command"),
    ):
        monkeypatch.setattr(module, name, forbidden)
    for name in (
        "prepare_dataset.snapshot_download", "prepare_dataset.load_dataset",
        "core.codex_runtime_config.resolve_endpoint_setting",
        "core.codex_runner.CodexAgentRunner",
        "core.agentic_v2_model_voice.AzureFoundryVoice.__post_init__",
        "core.agentic_v2_conversation.ScriptedVoice.__init__",
        "core.agentic_v2_fixture_backend.AgenticV2FixtureBackend.__init__",
        "core.agentic_v2_microvm_backend.AgenticV2MicroVMBackend.__init__",
        "core.agentic_v2_rehearsal_voice.RehearsalVoice.__init__",
        "core.azure_ai_clients.AzureAIRouteSettings.from_env",
        "step8_grade.Grader.__init__", "step8_grade.RubricLoader.__init__",
    ):
        monkeypatch.setattr(name, forbidden)
    for name in (
        "create_provider_client", "create_typed_azure_client", "AzureAIClientFactory",
        "preflight_routes", "TaskExecutor", "open_cost_recorder",
        "_require_host_may_carry_a_benchmark_run",
    ):
        monkeypatch.setattr(step2, name, forbidden)
    for name in (
        "run_stage_one_preflight", "run_manifest", "open_the_ledger",
        "the_paid_setup_a_dry_run_can_reach",
    ):
        monkeypatch.setattr(runner, name, forbidden)
    return calls


def _assert_marker(root, marker, manifest, plan, index):
    run = plan.dispatch.runs[index]
    files = _files(plan, index)
    combined_sha = _identity(plan.canonical_bytes())["sha256"]
    expected = {
        "bundle_version": "gpt54-run-config-bundle-v1",
        "run_id": run.run_id, "condition": run.condition, "repeat": run.repeat,
        "abba_index": index, "task_ids": list(run.task_ids),
        "manifest_sha256": plan.dispatch.manifest_sha256,
        "combined_plan_sha256": combined_sha,
        "source_base_sha": plan.dispatch.source_base_sha,
        "source_pins": manifest["source_pins"],
        "manifest_file": {"path": bundle.MANIFEST_PATH,
                          **_identity((root / bundle.MANIFEST_PATH).read_bytes())},
        "source_files": {name: _identity((root / name).read_bytes())
                         for name in manifest["source_pins"]},
        "files": {name: _identity(data) for name, data in files.items()},
        "attestation_linkage": {
            "attestation_version": "gpt54-prepared-input-attestation-v1",
            "binding_version": "gpt54-pre-execution-input-v1",
            "run_id": run.run_id, "condition": run.condition, "repeat": run.repeat,
            "manifest_sha256": plan.dispatch.manifest_sha256,
            "combined_plan_sha256": combined_sha,
            "source_pins_sha256": _identity(plan.dispatch.source_pins_json.encode("utf-8"))["sha256"],
            "config_sha256": _identity(files[run.config_path])["sha256"],
            "capture_path": "batch-runner/workspace/pre-execution-input.json",
        },
        "evidence_boundary": "local_config_bundle_consistency",
    }
    assert marker == expected
    assert (root / bundle.READY_PATH).read_bytes() == _json(expected)
    assert str(root).encode() not in _json(expected)
    for name, data in files.items():
        path = root / name
        assert path.read_bytes() == data
        assert not path.is_symlink() and path.stat().st_nlink == 1
    assert (root / bundle.READY_PATH).stat().st_nlink == 1
    assert not (root / "batch-runner/workspace").exists()
    assert not (root / "data").exists() and not (root / ".git").exists()
    before = _tree_snapshot(root)
    assert bundle.verify_run_config_bundle(
        checkout=root, run_id=run.run_id, condition=run.condition,
    ) == expected
    assert _tree_snapshot(root) == before
    assert plan.as_dict()["launch_allowed"] is False
    assert plan.as_dict()["full_220_allowed"] is False
    inspection = preflight.inspect_plan(manifest, grading_plan=plan.as_dict())
    assert inspection["configuration_valid"] is True
    assert inspection["launch_allowed"] is inspection["full_220_allowed"] is False
    assert inspection["run_config_bundle"] == {
        "bundle_version": "gpt54-run-config-bundle-v1",
        "materializer": "gpt54_run_config_bundle.materialize_run_config_bundle",
        "ready_marker": "comparison-bundle-ready.json",
        "required_runs": [row.run_id for row in plan.dispatch.runs],
        "checkout_creation": False,
        "evidence_boundary": "local_config_bundle_consistency",
    }
    assert "comparison_materialization_and_workflow_gates_not_wired" in inspection["launch_blockers"]


def _forge_member(root, run):
    """An attacker updates both the member and all marker claims about it."""
    path = root / run.config_path
    config = json.loads(path.read_bytes())
    request = config["model"] if run.condition == "sandbox_v2" else config["execution"]["codex"]
    request["reasoning_effort"] = "high"
    changed = _json(config)
    path.write_bytes(changed)
    marker_path = root / bundle.READY_PATH
    marker = json.loads(marker_path.read_bytes())
    marker["files"][run.config_path] = _identity(changed)
    marker["attestation_linkage"]["config_sha256"] = _identity(changed)["sha256"]
    marker_path.write_bytes(_json(marker))


def _runtime_rejection(case, tmp_path, monkeypatch):
    condition, mutation = case.removeprefix("gate_").split("_", 1)
    if condition == "codex":
        root, run, _, _, _ = _codex_fixture(tmp_path, monkeypatch, 1)
    else:
        root, run, _, _, _ = _v2_fixture(tmp_path, monkeypatch, 1)
    ready = root / bundle.READY_PATH
    if mutation == "missing":
        ready.unlink()
    elif mutation == "forged":
        _forge_member(root, run)
    else:
        marker = json.loads(ready.read_bytes())
        marker["verified"] = True
        ready.write_bytes(_json(marker))
    before = _tree_snapshot(root)
    if condition == "codex":
        with pytest.raises((bundle.RunConfigBundleRefused, writer.CodexInputCaptureRefused)):
            step2.run_inference(
                comparison_run_id=run.run_id, resume=False, max_retries=0, resume_max_rounds=0,
            )
        with pytest.raises((bundle.RunConfigBundleRefused, writer.CodexInputCaptureRefused)):
            step2.validate_restored_checkpoint(comparison_run_id=run.run_id)
    else:
        monkeypatch.setattr(sys, "argv", [
            "run_agentic_v2_stage.py", "--stage", "advance_check_5",
            "--plan", str(root / writer.CONFIG_PATH), "--run-id", run.run_id,
            "--parquet", str(root / writer.DATASET_ROOT / "data" / writer.PARQUET_NAME),
            "--dataset-root", str(root / writer.DATASET_ROOT),
            "--into", str(root / "batch-runner/workspace"),
        ])
        assert runner.main() == 1
        assert not (root / writer.CAPTURE_PATH).exists()
    assert _tree_snapshot(root) == before


@pytest.mark.parametrize("case", [
    "v2_r1", "codex_r1", "codex_r2", "v2_r2", "relocated_v2", "relocated_codex",
    "dispatch_type", "grading_type", "dispatch_run", "dispatch_condition", "dispatch_model",
    "dispatch_repeat", "dispatch_repeat_bool", "dispatch_tasks", "dispatch_missing_task",
    "dispatch_extra_task", "dispatch_duplicate_task", "dispatch_config", "dispatch_command",
    "dispatch_path_escape", "dispatch_path_absolute", "grading_run", "grading_config",
    "grading_experiment", "grading_path_escape", "grading_path_absolute",
    "manifest_control", "source_pin_missing", "source_pin_changed", "source_pin_escape",
    "combined_plan", "combined_extra", "target_manifest", "source_changed", "source_missing",
    "source_symlink", "source_hardlink", "source_parent_symlink", "checkout_symlink",
    "checkout_escape", "checkout_missing",
    *[f"collision_{role}" for role in ("plan", "run", "grader", "experiment", "marker", "other_run")],
    "collision_symlink", "collision_hardlink", "collision_directory", "publication_race",
    *[f"write_failure_{index}" for index in range(1, 6)],
    *[f"file_{change}_{role}" for change in ("changed", "missing", "extra")
      for role in ("plan", "run", "grader", "experiment")],
    "marker_missing", "marker_extra", "marker_removed", "marker_null", "marker_noncanonical",
    "marker_identity", "marker_linkage", "marker_inventory_extra", "marker_inventory_missing",
    "marker_inventory_entry_extra", "marker_source_extra", "marker_symlink", "marker_hardlink",
    "member_symlink", "member_hardlink", "other_run_after_publication", "source_after_publication",
    "manifest_bytes_after_publication", "forged_member_and_marker", "verify_run", "verify_condition",
    *[f"gate_{condition}_{change}" for condition in ("v2", "codex")
      for change in ("missing", "extra", "forged")],
    "runtime_v2", "runtime_codex", "legacy_v2_absent_null", "legacy_codex_absent_null",
])
def test_run_config_bundle_is_exact_atomic_and_gates_execution(case, tmp_path, monkeypatch):
    forbidden_calls = _guards(monkeypatch)
    if case in {"runtime_v2", "runtime_codex", "legacy_v2_absent_null", "legacy_codex_absent_null"}:
        regression = _v2_regression if "v2" in case else _codex_regression
        regression("default_absent_and_null" if case.startswith("legacy_") else "r1", tmp_path, monkeypatch)
        assert forbidden_calls == []
        return
    if case.startswith("gate_"):
        _runtime_rejection(case, tmp_path, monkeypatch)
        assert forbidden_calls == []
        return

    manifest = preflight.load_plan()
    plan = preflight.compile_grading_plan(manifest)
    index = {"codex_r1": 1, "codex_r2": 2, "v2_r2": 3, "relocated_codex": 1}.get(case, 0)
    run, grading = plan.dispatch.runs[index], plan.runs[index]
    combined = plan.as_dict()
    root = tmp_path / "disposable-source"
    _bundle_fixture(root, manifest=manifest, combined_plan=combined, run=run, materialize=False)
    files = _files(plan, index)
    roles = dict(zip(("plan", "run", "grader", "experiment"), files))
    source_name = "batch-runner/core/experiment_config.py"
    source = root / source_name
    ready = root / bundle.READY_PATH
    original_sources = {name: (root / name).read_bytes() for name in manifest["source_pins"]}
    target = root

    def publish():
        return bundle.materialize_run_config_bundle(
            run, grading, manifest=manifest, combined_plan=combined, checkout=target,
        )

    if case in {"v2_r1", "codex_r1", "codex_r2", "v2_r2", "relocated_v2", "relocated_codex"}:
        before = _tree_snapshot(root)
        marker = publish()
        _assert_marker(root, marker, manifest, plan, index)
        after = _tree_snapshot(root)
        assert set(after) - set(before) == set(files) | {bundle.READY_PATH}
        assert all(after[name] == value for name, value in before.items())
        assert {name: (root / name).read_bytes() for name in original_sources} == original_sources
        if case.startswith("relocated_"):
            relocated = tmp_path / "different-host-location" / "same-source"
            other = _bundle_fixture(relocated, manifest=manifest, combined_plan=combined, run=run)
            _assert_marker(relocated, other, manifest, plan, index)
            assert marker == other
            assert {name: (relocated / name).read_bytes() for name in (*files, bundle.READY_PATH)} == {
                name: (root / name).read_bytes() for name in (*files, bundle.READY_PATH)
            }
        before_retry = _tree_snapshot(root)
        with pytest.raises(bundle.RunConfigBundleRefused):
            publish()
        assert _tree_snapshot(root) == before_retry
    elif case.startswith("write_failure_") or case == "publication_race":
        real_write, written = writer._write_no_clobber, []
        stop = int(case.rsplit("_", 1)[1]) if case.startswith("write_failure_") else None

        def interrupted_write(path, data):
            if case == "publication_race":
                path.write_bytes(b"another publisher's complete file")
                return real_write(path, data)
            if path == ready:
                assert stop == 5
                raise OSError("fixture marker publication failed")
            real_write(path, data)
            written.append(path)
            if len(written) == stop:
                raise OSError("fixture stopped after a complete member")

        with monkeypatch.context() as failure:
            failure.setattr(writer, "_write_no_clobber", interrupted_write)
            with pytest.raises(bundle.RunConfigBundleRefused):
                publish()
        assert not ready.exists()
        assert not list(root.rglob(".input-capture-*"))
        if stop is not None:
            assert len(written) == min(stop, 4)
            assert all(path.read_bytes() == files[path.relative_to(root).as_posix()] for path in written)
        else:
            assert (root / next(iter(files))).read_bytes() == b"another publisher's complete file"
        with pytest.raises(bundle.RunConfigBundleRefused):
            bundle.verify_run_config_bundle(checkout=root, run_id=run.run_id, condition=run.condition)
        before_retry = _tree_snapshot(root)
        with pytest.raises(bundle.RunConfigBundleRefused):
            publish()
        assert _tree_snapshot(root) == before_retry
    elif case.startswith(("file_", "marker_", "member_", "verify_")) or case in {
        "other_run_after_publication", "source_after_publication", "manifest_bytes_after_publication",
        "forged_member_and_marker",
    }:
        marker = publish()
        requested_run, requested_condition = run.run_id, run.condition
        if case.startswith("file_"):
            _, change, role = case.split("_")
            path = root / roles[role]
            if change == "missing":
                path.unlink()
            elif change == "changed":
                path.write_bytes(path.read_bytes() + b"\n")
            else:
                payload = json.loads(path.read_bytes())
                payload["unregistered"] = True
                path.write_bytes(_json(payload))
        elif case == "marker_missing":
            ready.unlink()
        elif case == "marker_noncanonical":
            ready.write_bytes(ready.read_bytes() + b"\n")
        elif case in {"marker_symlink", "marker_hardlink", "member_symlink", "member_hardlink"}:
            path = ready if case.startswith("marker_") else root / run.config_path
            moved = tmp_path / "untrusted-member"
            path.rename(moved)
            path.symlink_to(moved) if case.endswith("symlink") else os.link(moved, path)
        elif case == "other_run_after_publication":
            (root / plan.runs[1].experiment_config_path).write_bytes(plan.runs[1].experiment_config_json.encode())
        elif case == "source_after_publication":
            source.write_bytes(source.read_bytes() + b"\n")
        elif case == "manifest_bytes_after_publication":
            path = root / bundle.MANIFEST_PATH
            path.write_bytes(path.read_bytes() + b"\n")
        elif case == "forged_member_and_marker":
            _forge_member(root, run)
        elif case == "verify_run":
            requested_run = plan.dispatch.runs[3].run_id
        elif case == "verify_condition":
            requested_condition = "codex"
        else:
            if case == "marker_extra":
                marker["verified"] = True
            elif case == "marker_removed":
                marker.pop("source_base_sha")
            elif case == "marker_null":
                marker = None
            elif case == "marker_identity":
                marker["abba_index"] = 3
            elif case == "marker_linkage":
                marker["attestation_linkage"]["capture_path"] = "elsewhere.json"
            elif case == "marker_inventory_extra":
                marker["files"]["extra.json"] = _identity(b"{}")
            elif case == "marker_inventory_missing":
                marker["files"].pop(run.config_path)
            elif case == "marker_inventory_entry_extra":
                marker["files"][run.config_path]["verified"] = True
            else:
                assert case == "marker_source_extra"
                marker["source_files"][source_name]["verified"] = True
            ready.write_bytes(_json(marker))
        before = _tree_snapshot(tmp_path)
        with pytest.raises(bundle.RunConfigBundleRefused):
            bundle.verify_run_config_bundle(checkout=root, run_id=requested_run, condition=requested_condition)
        assert _tree_snapshot(tmp_path) == before
    else:
        if case == "dispatch_type":
            run = run.as_dict()
        elif case == "grading_type":
            grading = grading.as_dict()
        elif case.startswith("dispatch_"):
            changes = {
                "dispatch_run": {"run_id": "unregistered"},
                "dispatch_condition": {"condition": "codex"},
                "dispatch_model": {"model": "different-model"},
                "dispatch_repeat": {"repeat": 2},
                "dispatch_repeat_bool": {"repeat": True},
                "dispatch_tasks": {"task_ids": tuple(reversed(run.task_ids))},
                "dispatch_missing_task": {"task_ids": run.task_ids[:-1]},
                "dispatch_extra_task": {"task_ids": (*run.task_ids, "extra")},
                "dispatch_duplicate_task": {"task_ids": (run.task_ids[0], *run.task_ids[:-1])},
                "dispatch_config": {"config_json": run.config_json + "\n"},
                "dispatch_command": {"commands": ((*run.commands[0], "--dry-run"),)},
                "dispatch_path_escape": {"config_path": "../escape.json"},
                "dispatch_path_absolute": {"config_path": str(tmp_path / "escape.json")},
            }
            run = replace(run, **changes[case])
        elif case == "grading_run":
            grading = plan.runs[1]
        elif case.startswith("grading_"):
            grading = replace(grading, **{
                "grading_config": {"grader_config_json": grading.grader_config_json + "\n"},
                "grading_experiment": {"experiment_config_json": grading.experiment_config_json + "\n"},
                "grading_path_escape": {"grader_config_path": "../escape.json"},
                "grading_path_absolute": {"experiment_config_path": str(tmp_path / "escape.json")},
            }[case])
        elif case == "manifest_control":
            manifest["shared"]["model"]["reasoning_effort"] = "high"
        elif case.startswith("source_pin_"):
            if case == "source_pin_missing":
                manifest["source_pins"].pop(source_name)
            elif case == "source_pin_changed":
                manifest["source_pins"][source_name] = "0" * 64
            else:
                manifest["source_pins"]["../escape.py"] = manifest["source_pins"].pop(source_name)
        elif case == "combined_plan":
            combined["dispatch_plan"]["runs"][0]["task_ids"].reverse()
        elif case == "combined_extra":
            combined["approved"] = True
        elif case == "target_manifest":
            altered = json.loads(_json(manifest))
            altered["launch_enabled"] = True
            (root / bundle.MANIFEST_PATH).write_bytes(_json(altered))
        elif case == "source_changed":
            source.write_bytes(source.read_bytes() + b"\n")
        elif case == "source_missing":
            source.unlink()
        elif case in {"source_symlink", "source_hardlink", "source_parent_symlink", "checkout_symlink"}:
            path = root if case == "checkout_symlink" else source.parent if case == "source_parent_symlink" else source
            moved = tmp_path / "untrusted-source"
            path.rename(moved)
            if case == "source_hardlink":
                os.link(moved, path)
            else:
                path.symlink_to(moved, target_is_directory=moved.is_dir())
        elif case == "checkout_escape":
            target = root / "batch-runner" / ".."
        elif case == "checkout_missing":
            target = tmp_path / "must-not-be-created"
        elif case.startswith("collision_"):
            collision = case.removeprefix("collision_")
            name = roles.get(collision, bundle.READY_PATH if collision == "marker" else run.config_path)
            if collision == "other_run":
                name = plan.runs[1].experiment_config_path
            path = root / name
            if collision == "directory":
                path.mkdir()
            elif collision in {"symlink", "hardlink"}:
                existing = tmp_path / "untouched-collision"
                existing.write_bytes(b"do not overwrite")
                path.symlink_to(existing) if collision == "symlink" else os.link(existing, path)
            else:
                path.write_bytes(b"do not overwrite")
        else:
            raise AssertionError(f"unhandled bundle case: {case}")
        before = _tree_snapshot(tmp_path)

        def unexpected_write(*args, **kwargs):
            pytest.fail("invalid inputs or a collision reached the first bundle write")

        with monkeypatch.context() as no_publication:
            no_publication.setattr(writer, "_write_no_clobber", unexpected_write)
            with pytest.raises(bundle.RunConfigBundleRefused):
                publish()
        assert _tree_snapshot(tmp_path) == before
        if case != "collision_marker":
            assert not ready.exists()
    assert forbidden_calls == []
