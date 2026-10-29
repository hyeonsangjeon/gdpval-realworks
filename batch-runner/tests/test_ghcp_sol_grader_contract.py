"""Synthetic capture layouts through unchanged Step8 input validators only."""

import builtins
import hashlib
import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

import ghcp_sol_actions_gate as capture
import ghcp_sol_grader_contract as bridge

CANARY = "PRIVATE_SYNTHETIC_GRADER_INPUT_CANARY"


def test_source_only_successor_preserves_original_policy_and_refusal():
    gate = bridge.contract
    original = gate.load_plan()
    profile = gate.load_plan(gate.ROOT / gate.SOURCE_PROFILE_PATH)
    assert hashlib.sha256((gate.ROOT / gate.PLAN_PATH).read_bytes()).hexdigest() == gate.ORIGINAL_PLAN_SHA256
    assert {k: v for k, v in original.items() if k != "source_pins"} == {
        k: v for k, v in profile.items() if k != "source_pins"}
    assert {name for name, digest in profile["source_pins"].items()
            if digest != original["source_pins"][name]} == {
        gate.SELF, "batch-runner/step8_grade.py", "batch-runner/core/grader.py", "batch-runner/core/grade_payload.py"}
    assert gate.inspect_plan(original)["configuration_valid"] is False
    report = gate.inspect_plan(profile)
    assert report["configuration_valid"] is True
    assert all(report[flag] is False for flag in gate.FALSE_FLAGS)
    assert report["observed"]["grader_validation"] is None
    assert report["cleared_blockers"] == [] and report["launch_blockers"] == list(gate.LAUNCH_BLOCKERS)
    assert report["source_registration"]["scope"] == "source_consistency_only_not_grader_seal_or_launch_approval"


@pytest.mark.parametrize("change", ["model", "limit", "source", "missing-source", "extra-source"])
def test_source_only_successor_refuses_unreviewed_deltas(change):
    gate = bridge.contract
    profile = gate.load_plan(gate.ROOT / gate.SOURCE_PROFILE_PATH)
    if change == "model":
        profile["identity"]["model"] = "other"
    elif change == "limit":
        profile["execution"]["turns_per_task"] = 65
    elif change == "source":
        profile["source_pins"]["batch-runner/core/grader.py"] = "0" * 64
    elif change == "missing-source":
        del profile["source_pins"][gate.SELF]
    else:
        profile["source_pins"]["unreviewed.py"] = "0" * 64
    report = gate.inspect_plan(profile)
    assert report["configuration_valid"] is False
    assert all(report[flag] is False for flag in gate.FALSE_FLAGS)


@pytest.fixture
def bundle(tmp_path, github_hosted_ubuntu_2404):
    root = tmp_path / "captures"
    root.mkdir()
    for task_id in capture.TASK_IDS:
        folder = root / ("ghcp-sol-dry-capture-" + task_id)
        folder.mkdir()
        (folder / "capture.json").write_text(json.dumps(capture.capture_envelope(task_id)))
    return root


def _first(root):
    return root / ("ghcp-sol-dry-capture-" + capture.TASK_IDS[0]) / "capture.json"


def _run(bundle, tmp_path):
    result = bridge.convert_and_validate(bundle, tmp_path / "contract")
    stored = json.loads((tmp_path / "contract" / bridge.REPORT).read_text())
    assert result == stored
    assert CANARY not in json.dumps(result)
    assert str(tmp_path) not in json.dumps(result)
    assert result["model_calls"] == result["judge_calls"] == 0
    assert result["ready_for_grading"] is result["gate5_passed"] is False
    assert result["paid_execution_allowed"] is False and result["grade"] is None
    return result


def test_all_five_empty_captures_reach_real_step8_input_and_policy_checks(bundle, tmp_path):
    import step8_grade as step8
    with (
        patch.object(step8, "validate_grading_config", wraps=step8.validate_grading_config) as config,
        patch.object(step8, "load_local_inference_results", wraps=step8.load_local_inference_results) as reader,
    ):
        result = _run(bundle, tmp_path)
    assert result["exit_status"] == 0, result
    assert result["step8_layout_valid"] is result["grader_policy_valid"] is True
    assert result["status"] == "model_free_layout_verified"
    assert config.call_count == reader.call_count == 1
    assert len(result["capture_inputs"]) == result["task_count"] == 5
    assert result["contract_checks"]["live_refusals_observed"] == [
        "source_inference_identity_missing", "full220_rerun_identity_not_reusable",
    ]
    manifest = json.loads((tmp_path / "contract" / bridge.MANIFEST).read_text())
    assert result["manifest_sha256"] == hashlib.sha256((tmp_path / "contract" / bridge.MANIFEST).read_bytes()).hexdigest()
    assert manifest["source_repo_id"] is manifest["source_revision"] is None
    assert manifest["inference_performed"] is manifest["grading_allowed"] is False
    assert [row["task_id"] for row in manifest["results"]] == list(capture.TASK_IDS)
    assert all(row["status"] == "pending" and row["usage"] is None
               and row["deliverable_files"] == [] for row in manifest["results"])
    for task_id in capture.TASK_IDS:
        path = tmp_path / "contract/workspace/upload/deliverable_files" / task_id
        assert path.is_dir() and list(path.iterdir()) == []
    assert len(list((tmp_path / "contract").rglob("*.json"))) == 2


@pytest.mark.parametrize("case", [
    "missing_artifact", "missing_capture", "extra_artifact", "extra_file", "symlink", "hardlink",
    "malformed", "duplicate_key", "wrong_task", "wrong_schema", "model_called", "paid_allowed",
    "unknown_private_field", "private_inputs_read", "capture_files", "runner_self_hosted",
    "runner_wrong_os", "version_unavailable", "boolean_call_count",
])
def test_bad_or_missing_capture_is_fail_closed(bundle, tmp_path, case):
    path = _first(bundle)
    value = json.loads(path.read_text())
    if case == "missing_artifact":
        path.unlink()
        path.parent.rmdir()
    elif case == "missing_capture":
        path.unlink()
    elif case == "extra_artifact":
        (bundle / "extra").mkdir()
    elif case == "extra_file":
        (path.parent / "unexpected.txt").write_text(CANARY)
    elif case == "symlink":
        saved = tmp_path / "source.json"
        path.rename(saved)
        path.symlink_to(saved)
    elif case == "hardlink":
        os.link(path, tmp_path / "linked.json")
    elif case == "malformed":
        path.write_text(CANARY)
    elif case == "duplicate_key":
        path.write_text('{"schema_version":"x","schema_version":"y"}')
    else:
        if case == "wrong_task": value["task_id"] = capture.TASK_IDS[1]
        if case == "wrong_schema": value["schema_version"] = "unknown"
        if case == "model_called": value["model_calls"] = 1
        if case == "paid_allowed": value["paid_execution_allowed"] = True
        if case == "unknown_private_field": value["private"] = CANARY
        if case == "private_inputs_read": value["capture"]["private_inputs_read"] = True
        if case == "capture_files": value["capture"]["files_captured"] = 1
        if case == "runner_self_hosted": value["runner_identity"]["runner_environment"] = "self-hosted"
        if case == "runner_wrong_os": value["runner_identity"]["image_os"] = "ubuntu22"
        if case == "version_unavailable": value["versions"]["kernel"] = None
        if case == "boolean_call_count": value["model_calls"] = False
        path.write_text(json.dumps(value))
    result = _run(bundle, tmp_path)
    assert result["exit_status"] == 2 and result["reason_codes"]
    assert result["step8_layout_valid"] is False
    assert not (tmp_path / "contract" / bridge.MANIFEST).exists()


def test_cold_step8_import_stays_inside_effect_guard(tmp_path):
    code = "import ghcp_sol_grader_contract as b\nwith b._no_effects():\n import step8_grade\nprint('import_only_ok')\n"
    result = subprocess.run([sys.executable, "-c", code], cwd=tmp_path, capture_output=True, text=True,
                            env={"PATH": os.defpath, "PYTHONPATH": str(bridge.ROOT / "batch-runner"),
                                 "HF_HUB_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1",
                                 "PYTHONDONTWRITEBYTECODE": "1", "LANG": "C.UTF-8"}, timeout=30)
    assert result.returncode == 0, result.stderr
    assert result.stdout == "import_only_ok\n"


def test_existing_output_is_not_adopted_or_overwritten(bundle, tmp_path):
    output = tmp_path / "contract"
    output.mkdir()
    (output / "marker").write_text(CANARY)
    result = bridge.convert_and_validate(bundle, output)
    assert result["reason_codes"] == ["grader_output_reuse_refused"]
    assert (output / "marker").read_text() == CANARY and not (output / bridge.REPORT).exists()


def test_local_nonhosted_cli_is_refused_before_input_read(tmp_path, monkeypatch):
    for name in ("GITHUB_ACTIONS", "RUNNER_ENVIRONMENT", "ImageOS"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(bridge, "_captures", lambda *a: pytest.fail("unapproved host read inputs"))
    result = bridge.convert_and_validate(tmp_path / "not-read", tmp_path / "not-created")
    assert result["reason_codes"] == [bridge.environment.REFUSAL]
    assert not (tmp_path / "not-created").exists()


@pytest.mark.parametrize("which", ["input_hash", "policy", "source_acceptance", "full220_acceptance"])
def test_existing_grader_contract_cannot_be_bypassed(bundle, tmp_path, monkeypatch, which):
    import step8_grade as step8
    if which == "input_hash":
        monkeypatch.setattr(bridge, "INPUT_CONTRACT_SHA256", "0" * 64)
    elif which == "policy":
        monkeypatch.setattr(bridge.contract, "inspect_plan", lambda *a: {"configuration_valid": False})
    elif which == "source_acceptance":
        monkeypatch.setattr(step8, "resolve_source_inference_identity", lambda *a: ("fake/repo", "a" * 40))
    else:
        monkeypatch.setattr(step8, "_validate_pinned_rerun_identity", lambda *a, **k: None)
    result = _run(bundle, tmp_path)
    assert result["exit_status"] == 2
    assert result["step8_layout_valid"] is False and result["grader_policy_valid"] is False


@pytest.mark.parametrize("effect", ["network", "dns", "process", "provider_import", "credential_file"])
def test_validation_scope_forbids_effects_and_secret_reads(tmp_path, effect):
    auth = tmp_path / "auth.json"
    auth.write_text(CANARY)
    with pytest.raises(bridge.EffectsRefused):
        with bridge._no_effects():
            if effect == "network":
                with socket.socket() as sock:
                    sock.connect(("127.0.0.1", 9))
            elif effect == "dns": socket.getaddrinfo("example.invalid", 443)
            elif effect == "process": subprocess.Popen([sys.executable, "-c", "pass"])
            elif effect == "provider_import": builtins.__import__("openai")
            else: auth.read_text()
    assert bridge._ACTIVE == 0


def test_attempted_grader_effect_is_a_refusal(bundle, tmp_path, monkeypatch):
    def bad(*args):
        subprocess.Popen([sys.executable, "-c", "pass"])
    monkeypatch.setattr(bridge, "_step8_checks", bad)
    result = _run(bundle, tmp_path)
    assert result["reason_codes"] == ["model_free_grader_effect_refused"]


def test_capture_bytes_are_rechecked_after_validation(bundle, tmp_path, monkeypatch):
    original = bridge._step8_checks
    def changed(*args):
        result = original(*args)
        with _first(bundle).open("a") as stream:
            stream.write("\n")
        return result
    monkeypatch.setattr(bridge, "_step8_checks", changed)
    result = _run(bundle, tmp_path)
    assert result["reason_codes"] == ["dry_capture_changed"]
    assert result["step8_layout_valid"] is False


@pytest.mark.parametrize("case", ["declared_missing", "undeclared_extra", "traversal", "missing_task_dir"])
def test_step8_rejects_missing_or_inconsistent_deliverable_layout(bundle, tmp_path, monkeypatch, case):
    original = bridge._step8_checks
    def corrupt(output, payload):
        task_id = capture.TASK_IDS[0]
        directory = output / "workspace/upload/deliverable_files" / task_id
        if case == "missing_task_dir":
            directory.rmdir()
        elif case == "undeclared_extra":
            (directory / "unexpected.txt").write_text(CANARY)
        else:
            payload["results"][0]["deliverable_files"] = [
                "../../outside" if case == "traversal" else f"deliverable_files/{task_id}/missing.txt"
            ]
            (output / bridge.MANIFEST).write_bytes(bridge._bytes(payload) + b"\n")
        return original(output, payload)
    monkeypatch.setattr(bridge, "_step8_checks", corrupt)
    result = _run(bundle, tmp_path)
    assert result["exit_status"] == 2 and result["step8_layout_valid"] is False


def test_manifest_bytes_cannot_change_after_step8_checks(bundle, tmp_path, monkeypatch):
    original = bridge._step8_checks
    def changed(output, payload):
        result = original(output, payload)
        with (output / bridge.MANIFEST).open("a") as stream:
            stream.write("\n")
        return result
    monkeypatch.setattr(bridge, "_step8_checks", changed)
    result = _run(bundle, tmp_path)
    assert result["reason_codes"] == ["step8_manifest_changed"]
    assert result["step8_layout_valid"] is False
