"""Synthetic metadata and shell stubs only; no CLI, sandbox, credentials or model."""

from copy import deepcopy
import hashlib
from pathlib import Path
import subprocess

import pytest
import yaml

from core import runner_environment
import gpt54_time_budget_codex_ci as native
import gpt54_time_budget_result_readout as readout
import gpt54_time_budget_v2_ci as v2
import gpt54_time_budget_v2_observation as observation


ROOT = Path(__file__).resolve().parents[2]
SOURCE = "a" * 40


def test_original_registration_is_preserved_and_five_deltas_are_explicit():
    path = ROOT / "batch-runner/experiments/execution_envelope/gpt54_sandboxv2_codex_time_budget_v1.yaml"
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == "e1d16d350aeb21af34104cede0d3acc0f6dc8db134338708e70168fbd9642699"
    pins = yaml.safe_load(raw)["source_pins"]
    assert len(pins) == 42
    changed = {name for name, expected in pins.items()
               if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected}
    assert changed == {".github/workflows/batch-run.yml", "batch-runner/step8_grade.py",
                       "batch-runner/core/codex_runner.py", "batch-runner/step2_run_inference.py",
                       "batch-runner/gpt54_time_budget_comparison.py"}


@pytest.fixture
def synthetic_host(native_hosted_runner, monkeypatch):
    # The actual classifier still reads these synthetic OS/CI facts. Never
    # replace require_execution/observe with a successful verdict.
    for name, value in {
        "GITHUB_REPOSITORY": "synthetic/repository", "GITHUB_SHA": SOURCE,
        "GITHUB_JOB": "observation", "GITHUB_WORKFLOW_REF": "synthetic/workflow@refs/heads/main",
    }.items():
        monkeypatch.setenv(name, value)
    return observation.execution_host_identity(SOURCE)


def test_image_is_explicit_and_part_of_host_identity(synthetic_host, monkeypatch):
    original = deepcopy(synthetic_host)
    assert original["policy"] == observation.RUNNER_HOST_POLICY
    assert original["runner_image"] == {
        "runner": "ubuntu-24.04", "runner_environment": "github-hosted", "runner_os": "Linux",
        "runner_arch": "X64", "image_os": "ubuntu24", "image_version": "20261026.354.1",
        "os_id": "ubuntu", "os_version_id": "24.04",
    }
    assert original["ownership_confirmed"] is False
    monkeypatch.setenv("ImageVersion", "20261030.1.0")
    changed = observation.execution_host_identity(SOURCE)
    assert changed["runner_image"]["image_version"] == "20261030.1.0"
    assert changed["instance_sha256"] != original["instance_sha256"]
    assert changed["ci_instance_sha256"] == original["ci_instance_sha256"]


@pytest.mark.parametrize("name,value", [
    ("ImageOS", "ubuntu22"), ("ImageOS", "ubuntu-latest"), ("ImageVersion", None),
    ("ImageVersion", ""), ("ImageVersion", "unknown"), ("RUNNER_ENVIRONMENT", "self-hosted"),
    ("RUNNER_ENVIRONMENT", None), ("RUNNER_OS", "Windows"), ("RUNNER_ARCH", "ARM64"),
    ("GITHUB_ACTIONS", "false"),
])
def test_image_admission_refuses_unapproved_or_missing_metadata(synthetic_host, monkeypatch, name, value):
    if value is None:
        monkeypatch.delenv(name)
    else:
        monkeypatch.setenv(name, value)
    with pytest.raises((observation.FirstV2ObservationRefused, runner_environment.ExecutionEnvironmentRefused)):
        observation.execution_host_identity(SOURCE)


def test_ubuntu24_label_cannot_hide_actual_ubuntu22(synthetic_host, monkeypatch):
    monkeypatch.setattr(runner_environment.platform, "freedesktop_os_release",
                        lambda: {"ID": "ubuntu", "VERSION_ID": "22.04"})
    with pytest.raises(runner_environment.ExecutionEnvironmentRefused, match="execution_environment_refused"):
        observation.execution_host_identity(SOURCE)


def _envelope(host):
    context = {"host": host, "cell": dict(v2.CELL), "request": {"source": {"sha": SOURCE, "tree": "b" * 40}},
               "request_identity": {"sha256": "c" * 64},
               "ci": {"run_id": "123456789", "run_number": 1, "job": "observation", "attempt": 1}}
    return v2._envelope(context, {"returned_commit": "d" * 40}, None, commit=None, outcome="unresolved")


def test_new_and_historical_envelopes_have_disjoint_image_schemas(synthetic_host):
    fresh = _envelope(synthetic_host)
    assert fresh["format"] == v2.RUNNER_ENVELOPE_VERSION
    v2.validate_envelope(fresh, expected_cell=v2.CELL)
    readout._validate_captured_host(synthetic_host, fresh)
    old_host = {key: value for key, value in synthetic_host.items() if key != "runner_image"}
    old_host["policy"] = "linux-boot-namespace-user-ci-instance-v1"
    historical = _envelope(old_host)
    assert historical["format"] == v2.ENVELOPE_VERSION and "runner_image" not in historical
    v2.validate_envelope(historical, expected_cell=v2.CELL)
    readout._validate_captured_host(old_host, historical)
    with pytest.raises(ValueError, match="completion_schema"):
        v2.validate_envelope({**fresh, "format": v2.ENVELOPE_VERSION}, expected_cell=v2.CELL)
    with pytest.raises(ValueError, match="runner_image_schema"):
        v2.validate_envelope({**historical, "format": v2.RUNNER_ENVELOPE_VERSION}, expected_cell=v2.CELL)
    with pytest.raises(ValueError, match="captured_runner_image_version"):
        readout._validate_captured_host(synthetic_host, {**fresh, "format": v2.ENVELOPE_VERSION})
    with pytest.raises(ValueError, match="captured_runner_image_version"):
        readout._validate_captured_host(old_host, {**historical, "format": v2.RUNNER_ENVELOPE_VERSION})
    for captured, envelope in ((old_host, fresh), (synthetic_host, historical)):
        with pytest.raises(ValueError):
            readout._validate_captured_host(captured, envelope)
    tampered = deepcopy(synthetic_host)
    tampered["runner_image"]["image_version"] = "20261030.2.0"
    with pytest.raises(ValueError, match="captured runner image mismatch"):
        readout._validate_captured_host(tampered, fresh)


def test_native_envelope_cannot_erase_its_runner_version(synthetic_host):
    envelope = _envelope(synthetic_host)
    envelope.update(native.CELL, format=native.RUNNER_ENVELOPE_VERSION)
    native.validate_envelope(envelope)
    with pytest.raises(ValueError, match="completion_schema"):
        native.validate_envelope({**envelope, "format": native.ENVELOPE_VERSION})
    envelope.pop("runner_image")
    envelope["format"] = native.ENVELOPE_VERSION
    native.validate_envelope(envelope)  # Read-only historical compatibility.


def test_codex_workflow_proves_sandbox_before_every_credential_boundary():
    job = yaml.safe_load((ROOT / native.WORKFLOW).read_text())["jobs"][native.JOB]
    assert job["runs-on"] == "ubuntu-24.04" and job["timeout-minutes"] == 65
    steps = job["steps"]
    probe = next(step for step in steps if step.get("id") == "sandbox_check")
    assert "prepare_codex_sandbox_host.py" in probe["run"] and "set -euo pipefail" in probe["run"]
    assert "continue-on-error" not in probe and "secrets." not in str(probe)
    assert probe["timeout-minutes"] == 2
    assert "batch-runner/scripts/prepare_codex_sandbox_host.py" in native.SOURCE_ROLES
    for step in steps:
        if "secrets." in str(step) or " execute " in step.get("run", ""):
            assert steps.index(step) > steps.index(probe)
            assert "always()" not in step.get("if", "") or " retain " in step.get("run", "")
    artifact = next(step for step in steps if step.get("with", {}).get("name") == "time-budget-codex-sandbox-preflight")
    assert artifact["with"]["if-no-files-found"] == "error"
    assert artifact["if"] == "always() && steps.sandbox_check.outcome != 'skipped'"


@pytest.mark.parametrize("probe_exit", [0, 2])
def test_probe_shell_never_continues_after_failure(tmp_path, probe_exit):
    steps = yaml.safe_load((ROOT / native.WORKFLOW).read_text())["jobs"][native.JOB]["steps"]
    code = next(step["run"] for step in steps if step.get("id") == "sandbox_check")
    # The workflow's real shell fragment calls a shell function, not Python,
    # the CLI, sudo, AppArmor or any provider. Exercise set -e as well as YAML.
    stub = f"python3() {{ return {probe_exit}; }}\n" + code + "\nprintf 'NEXT_STAGE'\n"
    result = subprocess.run(["/bin/bash", "--noprofile", "--norc", "-c", stub],
                            env={"PATH": "/usr/bin:/bin", "RUNNER_TEMP": str(tmp_path)},
                            capture_output=True, text=True, timeout=5)
    assert result.returncode == probe_exit
    assert result.stdout == ("NEXT_STAGE" if probe_exit == 0 else "") and result.stderr == ""
