"""Offline contracts only: never run the hosted probe/kernel/sandbox on NAS."""

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess

import pytest
import yaml

from core import runner_environment
from core import time_budget_observation_deadline as deadline
import gpt54_time_budget_resource_probe as probe
from .test_gpt54_time_budget_comparison import _Clock, observation_kernel

WORKFLOW = probe.ROOT / ".github/workflows/gpt54-time-budget-resource-cleanup.yml"
SOURCE = {"commit": "a" * 40, "tree": "b" * 40, "registration_sha256": probe.PLAN_SHA256}


def test_dispatch_only_workflow_has_no_credentials_or_live_mode():
    raw = WORKFLOW.read_text()
    document = yaml.safe_load(raw)
    trigger = document.get("on", document.get(True))
    assert set(trigger) == {"workflow_dispatch"}
    assert set(trigger["workflow_dispatch"]["inputs"]) == {"expected_source_sha"}
    assert document["permissions"] == {"contents": "read"}
    assert document["concurrency"]["cancel-in-progress"] is False
    assert set(document["jobs"]) == {"resource-cleanup"}
    job = document["jobs"]["resource-cleanup"]
    assert job["if"] == "github.event_name == 'workflow_dispatch' && github.repository == 'hyeonsangjeon/gdpval-realworks'"
    assert job["runs-on"] == "ubuntu-24.04" and 90 == job["timeout-minutes"] <= 360
    assert "environment" not in job
    for forbidden in ("secrets.", "id-token:", "azure/login", "continue-on-error", "workflow_call", "pull_request:", "push:"):
        assert forbidden not in raw
    steps = job["steps"]
    assert steps[1]["with"] == {"ref": "${{ inputs.expected_source_sha }}", "persist-credentials": False}
    assert '"$GITHUB_SHA" == "$EXPECTED_SOURCE_SHA"' in steps[0]["run"]
    assert '"$PROBE_WORKFLOW_SHA" == "$EXPECTED_SOURCE_SHA"' in steps[0]["run"]
    assert "gpt54_time_budget_resource_probe.py before" in steps[2]["run"]
    assert "pip install -r batch-runner/requirements.txt" in steps[3]["run"]
    assert "prepare_codex_sandbox_host.py" in steps[4]["run"]
    assert steps[5]["run"].endswith("gpt54_time_budget_resource_probe.py exercise")
    assert steps[6]["run"].endswith("gpt54_time_budget_resource_probe.py after")
    assert steps[6]["if"] == steps[7]["if"] == "always() && steps.baseline.outcome != 'skipped'"
    assert steps[7]["with"]["if-no-files-found"] == "error"
    assert steps[7]["with"]["path"].endswith("/artifacts/*.json")
    assert 60 * steps[5]["timeout-minutes"] >= 2 * 1250
    assert job["timeout-minutes"] >= sum(step.get("timeout-minutes", 0) for step in steps) + 10
    # The existing wildcard assigns this file to time-budget-contracts once.
    backend = yaml.safe_load((probe.ROOT / ".github/workflows/backend-tests.yml").read_text())
    assert "tests/test_time_budget_*.py" in str(backend["jobs"]["time-budget-contracts"])
    core_runs = "\n".join(step.get("run", "") for step in backend["jobs"]["pytest"]["steps"])
    assert "--ignore-glob='tests/test_time_budget_*.py'" in core_runs


def test_workflow_shell_syntax_only():
    # bash -n parses; it does not run checkout/install/sandbox or any probe.
    document = yaml.safe_load(WORKFLOW.read_text())
    for step in document["jobs"]["resource-cleanup"]["steps"]:
        if "run" in step:
            result = subprocess.run(["/bin/bash", "--noprofile", "--norc", "-n"], input=step["run"],
                                    capture_output=True, text=True, timeout=5,
                                    env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"})
            assert result.returncode == 0, step["name"]


def test_original_registration_and_source_successor_are_unchanged():
    plan = probe.load_plan()
    assert len(plan["source_pins"]) == 42
    assert plan["generation_budget"]["seconds_per_observation"] == 1200
    assert plan["generation_budget"]["local_cleanup_grace_seconds"] == 20
    for name, digest in (
        ("gpt54_sandboxv2_codex_comparison.yaml", "3d88bcb0c4eeeb9dad2c9ee7cb88db1b7ff49145f9264d9d284178f167a76ed1"),
        ("gpt54_time_budget_source_20261030_schedule.yaml", "1e316eecccad614eba24034849a3bebf7bff549a59d7f6e127ac597192334dae"),
    ):
        assert hashlib.sha256((probe.PLAN.parent / name).read_bytes()).hexdigest() == digest


@pytest.fixture
def hosted_labels(native_hosted_runner, monkeypatch):
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    monkeypatch.setenv("GITHUB_REPOSITORY", "hyeonsangjeon/gdpval-realworks")
    return probe.require_hosted()


@pytest.mark.parametrize("name,value", [
    ("GITHUB_ACTIONS", "false"), ("RUNNER_ENVIRONMENT", "self-hosted"),
    ("ImageOS", "ubuntu22"), ("ImageVersion", ""),
    ("GITHUB_EVENT_NAME", "push"), ("GITHUB_EVENT_NAME", "pull_request"),
    ("GITHUB_REPOSITORY", "other/repository"),
])
def test_wrong_host_or_event_refuses_before_any_work(hosted_labels, monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    monkeypatch.setattr(probe, "probe_root", lambda: pytest.fail("filesystem work before admission"))
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("process before admission"))
    assert probe.main(["exercise"]) == 2


def test_ubuntu22_os_cannot_impersonate_ubuntu24(hosted_labels, monkeypatch):
    monkeypatch.setattr(runner_environment.platform, "freedesktop_os_release", lambda: {"ID": "ubuntu", "VERSION_ID": "22.04"})
    with pytest.raises(runner_environment.ExecutionEnvironmentRefused):
        probe.require_hosted()


def test_environment_is_a_public_allowlist_not_a_secret_copy(hosted_labels, monkeypatch, tmp_path):
    monkeypatch.setenv("COPILOT_GITHUB_TOKEN", "synthetic-must-not-be-inherited")
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-must-not-be-inherited")
    monkeypatch.setenv("AZURE_CONFIG_DIR", "synthetic-private-config")
    monkeypatch.setenv("ACTIONS_RUNTIME_TOKEN", "synthetic-must-not-be-inherited")
    state = tmp_path / "codex"
    argv, env = probe.worker_command(state, SOURCE)
    assert not {"COPILOT_GITHUB_TOKEN", "OPENAI_API_KEY", "AZURE_CONFIG_DIR", "ACTIONS_RUNTIME_TOKEN"} & env.keys()
    assert "synthetic-must-not-be-inherited" not in json.dumps(env)
    assert env["GDPVAL_CODEX_RUN_ROOT"] == str(state / "temporary/native")
    assert env["TMPDIR"] == str(state / "temporary/tmp")
    assert argv[:5] == ["/usr/bin/bwrap", "--unshare-user", "--unshare-net", "--unshare-pid", "--die-with-parent"]
    assert ["--tmpfs", "/run"] == argv[argv.index("--tmpfs"):argv.index("--tmpfs") + 2]
    assert "--ro-bind" in argv and "--proc" in argv
    assert argv[-4:] == [str(probe.SCRIPT), "worker", "--condition", "codex"]


@pytest.mark.parametrize("kind", ["net", "pid"])
def test_worker_refuses_a_missing_namespace(kind, monkeypatch):
    for item in ("net", "pid"):
        value = Path(f"/proc/self/ns/{item}").stat().st_ino
        monkeypatch.setenv(f"PROBE_PARENT_{item.upper()}NS", str(value if item == kind else value + 1))
    with pytest.raises(probe.ProbeRefused, match="namespace_required"):
        probe.require_isolated()


@pytest.mark.parametrize("event,args", [
    ("socket.__new__", ()), ("socket.connect", ()), ("os.system", ("not-run",)),
    ("os.fork", ()), ("os.exec", ()), ("os.posix_spawn", ()),
    ("subprocess.Popen", ("codex", ["codex", "app-server"], None, {})),
])
def test_worker_audit_refuses_network_or_an_accidental_real_transport(event, args):
    counters = {"network_attempts": 0, "unexpected_process_attempts": 0}
    guard = probe.audit_guard(["fixed-sentinel"], counters)
    with pytest.raises(probe.ProbeRefused):
        guard(event, args)
    assert sum(counters.values()) == 1
    guard("subprocess.Popen", ("fixed-sentinel", ["fixed-sentinel"], None, {}))
    assert sum(counters.values()) == 1


@pytest.mark.parametrize("error", [FileNotFoundError, ProcessLookupError, PermissionError])
def test_proc_disappearance_is_safe_but_other_uncertainty_is_not_clean(monkeypatch, error):
    def failed(*args, **kwargs):
        raise error
    monkeypatch.setattr(Path, "read_text", failed)
    if error is PermissionError:
        with pytest.raises(PermissionError):
            probe.process_identity(123)
    else:
        assert probe.process_identity(123) is None


@pytest.fixture
def synthetic_worker(tmp_path, hosted_labels, observation_kernel, monkeypatch):
    """The real runner/cleanup code over a fake kernel, fake clock and fake I/O."""
    clock = _Clock()
    original_init = deadline.TimeBudgetObservation.__init__
    monkeypatch.setattr(deadline.TimeBudgetObservation, "__init__",
                        lambda self, directory, identity: original_init(self, directory, identity, clock=clock))
    monkeypatch.setattr(probe, "require_isolated", lambda: None)
    monkeypatch.setattr(probe, "install_worker_guard",
                        lambda _: {"network_attempts": 0, "unexpected_process_attempts": 0})

    def forbidden(*args, **kwargs):
        pytest.fail("offline fixture attempted a process, socket, sleep or sandbox")

    for owner, name in ((subprocess, "Popen"), (subprocess, "run"), (os, "fork"),
                        (socket.socket, "connect"), (socket, "create_connection"), (probe.time, "sleep")):
        monkeypatch.setattr(owner, name, forbidden)

    def orphan(state, control):
        assert control._claimed and control.first_start is not None
        parent = observation_kernel.spawn()
        child = observation_kernel.spawn(parent=parent.pid)
        observation_kernel.exit(parent)
        return {"pid": child.pid, "start_ticks": 1}

    monkeypatch.setattr(probe, "spawn_orphan", orphan)
    monkeypatch.setattr(probe, "process_identity", lambda pid:
                        {"pid": pid, "start_ticks": 1} if pid in observation_kernel.processes else None)

    def advance(control):
        clock.now = control.first_start + 1200
        control.check_generation()

    monkeypatch.setattr(probe, "stall_until_deadline", advance)

    def run(condition):
        state = tmp_path / condition
        state.mkdir(mode=0o700)
        for name in ("receipts", "temporary", "temporary/home", "temporary/tmp", "temporary/native"):
            (state / name).mkdir(mode=0o700)
        monkeypatch.setenv("GDPVAL_CODEX_RUN_ROOT", str(state / "temporary/native"))
        monkeypatch.setenv("TMPDIR", str(state / "temporary/tmp"))
        return probe.worker(state, SOURCE), probe.read_json(state / "result.json"), state

    return run, observation_kernel, clock


@pytest.mark.parametrize("condition", probe.CONDITIONS)
def test_both_real_runner_paths_expire_and_clean_with_fake_kernel_and_clock(synthetic_worker, condition):
    run, kernel, _ = synthetic_worker
    rc, record, state = run(condition)
    assert rc == 0, record
    assert record["passed"] and not record["observation_succeeded"]
    assert record["deadline"]["terminal_reason"] == deadline.TIMEOUT
    assert record["deadline"]["generation_elapsed_seconds"] == 1200
    assert record["deadline"]["cleanup_deadline_monotonic"] == 1320
    assert record["deadline"]["host_reusable"] and not record["lease_present"]
    assert record["process_residues"] == record["temporary_residues"] == []
    assert not list((state / "temporary").iterdir()) and kernel.processes == {}
    assert (record["fixture"]["orphan"]["pid"], signal.SIGKILL) in kernel.signals
    assert record["actual_provider_usage"] is record["actual_provider_cost_usd"] is None
    assert deadline.TimeBudgetObservation._process_owner is None


@pytest.mark.parametrize("condition", probe.CONDITIONS)
def test_a_runtime_directory_leak_is_retained_and_fails(synthetic_worker, monkeypatch, condition):
    original = probe.run_v2 if condition == "sandbox_v2" else probe.run_codex

    def leak(state, *args):
        result = original(state, *args)
        (state / "temporary/leaked-fixture.txt").write_text("synthetic residue")
        return result

    monkeypatch.setattr(probe, "run_v2" if condition == "sandbox_v2" else "run_codex", leak)
    rc, record, state = synthetic_worker[0](condition)
    assert rc == 2 and record["passed"] is False
    assert record["temporary_residues"] == ["leaked-fixture.txt"]
    assert (state / "temporary/leaked-fixture.txt").is_file()


@pytest.fixture
def good_worker_record():
    return {**probe.label(), "condition": "sandbox_v2", "error": None,
        "clock": "real_monotonic", "observation_succeeded": False,
        "generation_seconds": 1200, "cleanup_seconds": 20,
        "deadline": {"terminal_reason": deadline.TIMEOUT, "generation_elapsed_seconds": 1200,
                     "cleanup_complete": True, "host_reusable": True, "owned_processes_stopped": True,
                     "cleanup_expired": False, "cleanup_elapsed_seconds": 0,
                     "first_start_monotonic": 100, "cleanup_deadline_monotonic": 1320,
                     "cleanup_finished_monotonic": 1300},
        "fixture": {"orphan": {"pid": 10, "start_ticks": 1}, "synthetic_responses": 1,
                    "synthetic_artifact_sha256": hashlib.sha256(probe.PAYLOAD).hexdigest(),
                    "voice_closed": True, "stop_reason": "time_limit_reached"},
        "kernel_children_empty": True, "lease_present": False,
        "process_residues": [], "temporary_residues": [],
        "audit": {"network_attempts": 0, "unexpected_process_attempts": 0}}


@pytest.mark.parametrize("field,value", [
    ("generation_seconds", 1), ("cleanup_seconds", 1), ("clock", "fake"),
    ("kernel_children_empty", False), ("lease_present", True), ("process_residues", [{"pid": 10}]),
    ("temporary_residues", ["leak"]), ("model_calls", 1), ("study_observation", True),
    ("observation_succeeded", True), ("audit", {"network_attempts": 1, "unexpected_process_attempts": 0}),
])
def test_no_green_from_shortened_timer_or_missing_cleanup_proof(good_worker_record, field, value):
    assert probe.evaluate_worker(good_worker_record)
    good_worker_record[field] = value
    assert not probe.evaluate_worker(good_worker_record)


@pytest.mark.parametrize("field,value", [
    ("terminal_reason", "completed"), ("generation_elapsed_seconds", 1199),
    ("generation_elapsed_seconds", 1220), ("cleanup_complete", False),
    ("host_reusable", False), ("owned_processes_stopped", False), ("cleanup_expired", True),
    ("cleanup_elapsed_seconds", 20), ("cleanup_elapsed_seconds", None),
    ("cleanup_deadline_monotonic", 1340), ("cleanup_finished_monotonic", 1320),
])
def test_failed_or_unconfirmed_deadline_cannot_pass(good_worker_record, field, value):
    good_worker_record["deadline"][field] = value
    assert not probe.evaluate_worker(good_worker_record)


def test_inventory_failure_stays_unknown_and_other_snapshots_are_retained(hosted_labels, tmp_path, monkeypatch):
    def inventory(argv):
        if argv[0].endswith("docker"):
            raise OSError("synthetic failure, not retained")
        return "4\n" if argv[0].endswith("nproc") else "synthetic inventory\n"
    monkeypatch.setattr(probe, "command", inventory)
    record = probe.resource_snapshot(tmp_path)
    assert record["containers"] is None and record["inventory_errors"] == ["containers"]
    assert record["cpu_count"] == 4 and record["disk_df_bytes"] == record["memory_free_bytes"] == "synthetic inventory\n"
    summary = probe.summarize(tmp_path, record, record)
    assert not summary["passed"] and summary["new_container_residues"] is None
    assert "resource_or_container_inventory_unavailable" in summary["issues"]


def test_missing_worker_report_and_new_containers_fail_without_removal(tmp_path):
    before = {"containers": ["a" * 64], "inventory_errors": [], "sandbox_preflight_temp_directories": []}
    after = {"containers": ["a" * 64, "b" * 64], "inventory_errors": [], "sandbox_preflight_temp_directories": []}
    summary = probe.summarize(tmp_path, before, after)
    assert summary["new_container_residues"] == ["b" * 64]
    assert summary["issues"] == ["sandbox_v2_proof_missing_or_failed", "codex_proof_missing_or_failed", "new_container_residue"]


def test_sandbox_preparation_scratch_is_part_of_residue_inventory(tmp_path):
    before = {"containers": [], "inventory_errors": [], "sandbox_preflight_temp_directories": ["codex-sandbox-preflight-preexisting"]}
    after = {**before, "sandbox_preflight_temp_directories": [*before["sandbox_preflight_temp_directories"], "codex-sandbox-preflight-new"]}
    result = probe.summarize(tmp_path, before, after)
    assert result["sandbox_preflight_temporary_residues"] == ["codex-sandbox-preflight-new"]
    assert not result["passed"] and "sandbox_preflight_temporary_residue" in result["issues"]


def test_live_native_auth_still_refuses_before_runtime_start(hosted_labels, tmp_path, monkeypatch):
    from core.codex_runner import CodexAgentRunner, CodexWorkspace, CodexAuthCommandFailed
    from core.codex_runtime_config import CodexProviderSettings
    from openai_codex.client import CodexClient
    # No credential read or command: simulate exactly the empty-auth response.
    provider = CodexProviderSettings(endpoint="https://synthetic.services.ai.azure.com/openai/v1/", model="gpt-5.4")
    monkeypatch.setattr(subprocess, "run", lambda argv, **kw: subprocess.CompletedProcess(argv, 0, "", ""))
    monkeypatch.setattr(CodexClient, "start", lambda _: pytest.fail("empty auth reached runtime"))
    runner = CodexAgentRunner(provider)
    assert runner.preflight_auth is True
    workspace = CodexWorkspace.create(task_id="synthetic-auth-refusal")
    try:
        with pytest.raises(CodexAuthCommandFailed, match="produced no token"):
            runner.open_runtime(workspace)
    finally:
        workspace.cleanup()


@pytest.mark.parametrize("failure", ["exit", "missing", "deadline", "timeout"])
def test_no_second_worker_after_uncertain_first_cleanup(tmp_path, hosted_labels, monkeypatch, good_worker_record, failure):
    (tmp_path / "artifacts").mkdir()
    (tmp_path / "state").mkdir()
    probe.write_json(tmp_path / "artifacts/resources-before.json", {"inventory_errors": []})
    probe.write_json(tmp_path / "artifacts/sandbox-preflight.json", {
        "status": "ready", "model_calls": 0, "codex_probe_marker_verified": True, "runner_evidence": hosted_labels})
    monkeypatch.setattr(probe, "source_identity", lambda: SOURCE)
    calls = []

    def run(argv, **kwargs):
        calls.append(argv)
        assert kwargs["timeout"] == 1250 and argv[-1] == "sandbox_v2"
        if failure == "timeout":
            raise subprocess.TimeoutExpired(argv, 1250)
        report = deepcopy(good_worker_record)
        if failure == "deadline":
            report["deadline"]["cleanup_complete"] = False
        if failure != "missing":
            probe.write_json(tmp_path / "state/sandbox_v2/result.json", report)
        return subprocess.CompletedProcess(argv, 2 if failure == "exit" else 0)

    monkeypatch.setattr(subprocess, "run", run)
    assert probe.exercise(tmp_path) == 2
    assert len(calls) == 1 and not (tmp_path / "state/codex").exists()
