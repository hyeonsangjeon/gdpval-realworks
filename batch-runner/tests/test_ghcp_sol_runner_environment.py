"""Host-policy proofs with synthetic metadata; no installed CLI/model runs."""

import json
import os
import subprocess
import sys

import pytest

import ghcp_sol_actions_gate as gate
import ghcp_sol_execution_adapter as adapter
import ghcp_sol_runner_environment as environment


def test_hosted_2404_identity_is_complete(github_hosted_ubuntu_2404, capsys):
    record = environment.observe()
    assert record == github_hosted_ubuntu_2404
    assert record["eligible_for_execution"] is True
    assert record["runner_name"] == "GitHub Actions synthetic-only"
    assert record["runner_os"] == "Linux"
    assert record["os_version_id"] == "24.04"
    assert record["image_os"] == "ubuntu24"
    assert record["image_version"] == "20261029.1.0"
    assert record["local_use_policy"] == "dry_run_and_development_only"
    assert record["evidence_boundary"] == "observed_runner_metadata_not_cryptographic_attestation"
    assert environment.main() == 0
    assert json.loads(capsys.readouterr().out) == record


@pytest.mark.parametrize("field,value", [
    ("GITHUB_ACTIONS", None), ("GITHUB_ACTIONS", "false"), ("GITHUB_ACTIONS", "1"),
    ("RUNNER_ENVIRONMENT", None), ("RUNNER_ENVIRONMENT", "self-hosted"),
    ("RUNNER_OS", "Windows"), ("ImageOS", "ubuntu22"), ("ImageOS", None),
    ("ImageVersion", None), ("ImageVersion", "unknown"),
    ("RUNNER_NAME", ""), ("RUNNER_NAME", "unsafe\nmetadata"),
])
@pytest.mark.parametrize("task_id", [adapter.SMOKE_TASK_ID, *gate.TASK_IDS])
def test_all_execution_entries_refuse_host_before_auth_files_or_process(
    tmp_path, monkeypatch, github_hosted_ubuntu_2404, field, value, task_id,
):
    if value is None:
        monkeypatch.delenv(field)
    else:
        monkeypatch.setenv(field, value)

    def forbidden(*args, **kwargs):
        pytest.fail("unapproved host reached auth, catalogue, binary or subprocess")

    monkeypatch.setattr(adapter, "_selected_auth_environment", forbidden)
    monkeypatch.setattr(adapter, "_verify_copilot_binary", forbidden)
    monkeypatch.setattr(gate, "fixed_task_ids", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    state = tmp_path / "not-created"
    if task_id == adapter.SMOKE_TASK_ID:
        receipt = adapter.run_copilot_smoke(tmp_path / "not-read", state, execution_enabled=True)
        assert receipt["paid_smoke_authorized"] is False
    else:
        receipt = adapter.run_task(task_id, [sys.executable, "not-run"], state,
                                   execution_enabled=True, execution_config={"tool_calls_per_task": 32})
    assert receipt["reason_codes"] == [environment.REFUSAL]
    assert receipt["runner_identity"]["eligible_for_execution"] is False
    assert receipt["subprocess_started"] is False
    assert receipt["exit_status"] == 2
    assert not state.exists()


@pytest.mark.parametrize("release", [
    {}, {"ID": "ubuntu", "VERSION_ID": "22.04"},
    {"ID": "debian", "VERSION_ID": "24.04"},
    {"ID": "ubuntu", "VERSION_ID": "26.04"},
])
def test_environment_labels_cannot_replace_actual_os_release(monkeypatch, github_hosted_ubuntu_2404, release):
    monkeypatch.setattr(environment, "_os_release", lambda: release)
    assert environment.observe()["eligible_for_execution"] is False


def test_unreadable_os_metadata_is_not_permission(monkeypatch, github_hosted_ubuntu_2404, capsys):
    def unreadable():
        raise OSError("PRIVATE_ENVIRONMENT_CANARY")
    monkeypatch.setattr(environment, "_os_release", unreadable)
    assert environment.main() == 2
    output = capsys.readouterr().out
    assert "PRIVATE_ENVIRONMENT_CANARY" not in output
    assert json.loads(output)["eligible_for_execution"] is False


def test_environment_drift_before_spawn_stops_and_retains_receipt(tmp_path, monkeypatch, github_hosted_ubuntu_2404):
    original = adapter._smoke_environment
    def changed(*args, **kwargs):
        value = original(*args, **kwargs)
        monkeypatch.setenv("ImageVersion", "20261030.1.0")
        return value
    def forbidden(*args, **kwargs):
        pytest.fail("environment drift reached a subprocess")
    monkeypatch.setattr(adapter, "_smoke_environment", changed)
    monkeypatch.setattr(gate, "check_selection", lambda *a, **k: None)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    receipt = adapter.run_task(gate.TASK_IDS[0], [sys.executable, "not-run"], tmp_path / "state",
                               execution_enabled=True, execution_config={"tool_calls_per_task": 32})
    assert receipt["reason_codes"] == ["execution_environment_changed"]
    assert receipt["subprocess_started"] is False
    assert json.loads((tmp_path / "state" / gate.TASK_IDS[0] / "execution-receipt.json").read_text()) == receipt


def test_local_dry_capture_is_development_only(tmp_path, monkeypatch):
    for name in ("GITHUB_ACTIONS", "RUNNER_ENVIRONMENT", "RUNNER_NAME", "RUNNER_OS", "ImageOS", "ImageVersion"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(environment, "_os_release", lambda: {"ID": "ubuntu", "VERSION_ID": "22.04"})
    monkeypatch.setattr(gate, "check_selection", lambda *a, **k: None)
    def forbidden(*args, **kwargs):
        pytest.fail("local dry capture started a process")
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    assert gate.dry_capture(gate.TASK_IDS[0], tmp_path / "state") == 0
    capture = json.loads((tmp_path / "state" / gate.TASK_IDS[0] / "capture.json").read_text())
    assert capture["local_use_policy"] == "dry_run_and_development_only"
    assert capture["runner_identity"]["eligible_for_execution"] is False
    assert capture["paid_execution_allowed"] is False
    assert capture["model_calls"] == capture["grader_calls"] == 0


def test_unrelated_environment_values_are_never_read(monkeypatch, github_hosted_ubuntu_2404):
    allowed = {name: os.environ[name] for name in (
        "GITHUB_ACTIONS", "RUNNER_ENVIRONMENT", "RUNNER_NAME", "RUNNER_OS", "ImageOS", "ImageVersion",
    )}
    class OnlyMetadata(dict):
        def get(self, key, default=None):
            assert key in allowed
            return super().get(key, default)
    monkeypatch.setattr(os, "environ", OnlyMetadata(allowed))
    assert environment.observe()["eligible_for_execution"] is True
