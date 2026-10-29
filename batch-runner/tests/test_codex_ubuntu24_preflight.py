"""Model-free fixtures: never run sudo, a real sandbox, or a Codex turn here."""

import json
import os
from pathlib import Path
import stat
import subprocess
from types import SimpleNamespace

import pytest
import yaml

from core import runner_environment as runner
from scripts import prepare_codex_sandbox_host as preflight

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def no_real_processes(monkeypatch):
    def refused(*args, **kwargs):
        pytest.fail("a sandbox fixture tried to start a real process")
    monkeypatch.setattr(subprocess, "run", refused)


@pytest.fixture
def fake_host(native_hosted_runner, monkeypatch, tmp_path):
    import codex_cli_bin

    calls = []
    state = {"initial": 1, "final": 0, "profile": 0, "cli": 0, "version": "codex-cli 0.147.0",
             "marker": preflight.SANDBOX_MARKER,
             "after_cli": lambda: None}
    bwrap = tmp_path / "bwrap"
    bwrap.write_bytes(b"synthetic executable, never run")
    monkeypatch.setattr(preflight, "_system_bwrap", lambda: bwrap)
    monkeypatch.setattr(preflight, "_restriction", lambda: "1")
    monkeypatch.setattr(preflight.os, "geteuid", lambda: 1001)
    monkeypatch.setattr(preflight, "require_pinned_runtime", lambda: ("0.147.0", "0.147.0"))
    monkeypatch.setattr(codex_cli_bin, "bundled_codex_path", lambda: Path("/synthetic/codex"))
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path))

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        output = "synthetic output"
        if argv[-1] == "--version":
            return SimpleNamespace(returncode=0, stdout=state["version"], stderr="")
        if argv[0] == "/usr/bin/sudo":
            assert argv == ["/usr/bin/sudo", "-n", "/usr/sbin/apparmor_parser", "-a"]
            assert kwargs["input_text"] == preflight.PROFILE
            code = state["profile"]
        elif "--unshare-user" in argv:
            number = sum("--unshare-user" in prior for prior, _ in calls)
            code = state["initial"] if number == 1 else state["final"]
        else:
            assert argv == ["/synthetic/codex", "sandbox", "linux", "--", "/usr/bin/printf", preflight.SANDBOX_MARKER]
            environment = kwargs["environment"]
            assert set(environment) == {"PATH", "LANG", "HOME", "CODEX_HOME", "XDG_CONFIG_HOME",
                "XDG_CACHE_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "TMPDIR"}
            assert Path(environment["HOME"]).is_dir() and Path(environment["CODEX_HOME"]).is_dir()
            assert not Path(environment["CODEX_HOME"]).is_relative_to(environment["TMPDIR"])
            state["after_cli"]()
            code = state["cli"]
            output = state["marker"]
        return SimpleNamespace(returncode=code, stdout=output, stderr="fixture-private-error")

    monkeypatch.setattr(preflight, "_run", run)
    return state, calls, tmp_path


@pytest.mark.parametrize("initial", [0, 1])
def test_ready_requires_both_real_paths_and_preserves_global_policy(fake_host, initial):
    state, calls, root = fake_host
    state["initial"] = initial
    record = preflight.prepare()
    assert record["status"] == "ready" and record["reason_code"] is None
    assert record["apparmor_profile_added"] is bool(initial)
    assert record["apparmor_restriction_before"] == record["apparmor_restriction_after"] == "1"
    assert record["sysctl_changed"] is False and record["sysctl_write_performed"] is False
    assert record["bwrap_probe_exit"] == record["codex_probe_exit"] == 0
    assert record["codex_probe_marker_verified"] is True
    assert record["model_calls"] == 0
    assert sum(argv[0] == "/usr/bin/sudo" for argv, _ in calls) == initial
    assert not list(root.glob("codex-sandbox-preflight-*"))
    runner.validate_receipt(record["runner_evidence"])


@pytest.mark.parametrize("failure,detail", [
    ("profile", "apparmor_profile_add_failed"),
    ("final", "bubblewrap_namespace_probe_failed"),
    ("cli", "pinned_codex_sandbox_probe_failed"),
    ("version", "pinned_cli_version_unverified"),
])
def test_each_required_probe_is_fail_closed_without_raw_output(fake_host, failure, detail):
    state, calls, _ = fake_host
    state[failure] = "wrong-version fixture-private-error" if failure == "version" else 1
    record = preflight.prepare()
    assert record["status"] == "refused" and record["reason_code"] == preflight.REFUSED
    assert record["detail"] == detail and record["model_calls"] == 0
    assert "fixture-private-error" not in json.dumps(record)
    if failure != "cli":
        assert not any("sandbox" in argv for argv, _ in calls)


@pytest.mark.parametrize("case", ["nas", "2204", "azure", "root"])
def test_unapproved_preparation_stops_before_runtime_or_sudo(fake_host, monkeypatch, case):
    _, calls, _ = fake_host
    if case == "nas":
        monkeypatch.setenv("RUNNER_ENVIRONMENT", "self-hosted")
    elif case == "2204":
        monkeypatch.setenv("ImageOS", "ubuntu22")
        monkeypatch.setattr(runner.platform, "freedesktop_os_release", lambda: {"ID": "ubuntu", "VERSION_ID": "22.04"})
    elif case == "azure":
        observed = runner.observe()
        observed.update(github_hosted=False, approved_azure_vm=True)
        monkeypatch.setattr(runner, "require_execution", lambda *args: observed)
    else:
        monkeypatch.setattr(preflight.os, "geteuid", lambda: 0)
    record = preflight.prepare()
    assert record["status"] == "refused" and calls == []


def test_unknown_non_policy_failure_never_loads_a_profile(fake_host, monkeypatch):
    _, calls, _ = fake_host
    monkeypatch.setattr(preflight, "_restriction", lambda: "0")
    record = preflight.prepare()
    assert record["detail"] == "namespace_failure_without_apparmor_restriction"
    assert not any(argv[0] == "/usr/bin/sudo" for argv, _ in calls)


@pytest.mark.parametrize("error", [FileNotFoundError, ProcessLookupError])
def test_disappearing_probe_state_cannot_become_ready(fake_host, monkeypatch, error):
    _, calls, _ = fake_host
    def gone():
        raise error("synthetic probe state disappeared")
    monkeypatch.setattr(preflight, "_restriction", gone)
    record = preflight.prepare()
    assert record["status"] == "refused"
    assert record["detail"] == "sandbox_preflight_dependency_or_io_failure"
    assert not any(argv[0] == "/usr/bin/sudo" or "sandbox" in argv for argv, _ in calls)


def test_zero_cli_exit_without_command_marker_is_not_a_sandbox_proof(fake_host):
    state, _, _ = fake_host
    state["marker"] = "usage help text, not the payload"
    record = preflight.prepare()
    assert record["codex_probe_exit"] == 0 and record["codex_probe_marker_verified"] is False
    assert record["status"] == "refused" and record["detail"] == "pinned_codex_sandbox_probe_failed"


@pytest.mark.parametrize("stage", ["version", "profile", "sandbox"])
def test_timeout_refuses_before_any_model_path(fake_host, monkeypatch, stage):
    run = preflight._run
    def timed(argv, **kwargs):
        if ((stage == "version" and argv[-1] == "--version")
                or (stage == "profile" and argv[0] == "/usr/bin/sudo")
                or (stage == "sandbox" and "sandbox" in argv)):
            raise subprocess.TimeoutExpired(argv, 20, stderr="fixture-private-error")
        return run(argv, **kwargs)
    monkeypatch.setattr(preflight, "_run", timed)
    record = preflight.prepare()
    assert record["status"] == "refused" and record["detail"] == "sandbox_preflight_command_timeout"
    assert "fixture-private-error" not in json.dumps(record)


@pytest.mark.parametrize("change", ["restriction", "binary", "runner"])
def test_mid_probe_drift_is_not_accepted(fake_host, monkeypatch, change):
    state, _, root = fake_host
    if change == "restriction":
        values = iter(("1", "0"))
        monkeypatch.setattr(preflight, "_restriction", lambda: next(values))
    elif change == "binary":
        state["after_cli"] = lambda: (root / "bwrap").write_bytes(b"changed")
    else:
        state["after_cli"] = lambda: monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")
    record = preflight.prepare()
    assert record["status"] == "refused"
    assert record["detail"] == (runner.CHANGED if change == "runner" else "sandbox_host_changed_during_preflight")


@pytest.mark.parametrize("failure", ["missing_runtime", "missing_temp", "missing_bwrap"])
def test_missing_dependency_or_state_never_claims_ready(fake_host, monkeypatch, failure):
    if failure == "missing_runtime":
        def missing():
            raise ImportError("fixture-private-error")
        monkeypatch.setattr(preflight, "require_pinned_runtime", missing)
    elif failure == "missing_temp":
        monkeypatch.delenv("RUNNER_TEMP")
    else:
        monkeypatch.setattr(preflight, "_system_bwrap", lambda: (_ for _ in ()).throw(
            preflight.SandboxRefused("system_bwrap_selection_unverified")))
    record = preflight.prepare()
    assert record["status"] == "refused" and "fixture-private-error" not in json.dumps(record)


def test_main_records_refusal_and_cannot_overwrite_a_report(fake_host, capsys):
    state, _, root = fake_host
    state["cli"] = 1
    output = root / "receipt.json"
    assert preflight.main(["--out", str(output)]) == 2
    original = output.read_bytes()
    assert json.loads(original)["detail"] == "pinned_codex_sandbox_probe_failed"
    assert preflight.main(["--out", str(output)]) == 2
    assert output.read_bytes() == original
    assert "fixture-private-error" not in capsys.readouterr().out


def test_receipt_write_failure_does_not_return_ready(fake_host, capsys):
    _, _, root = fake_host
    assert preflight.main(["--out", str(root / "absent" / "report.json")]) == 2
    assert "sandbox_preflight_receipt_unwritable" in capsys.readouterr().out


def test_subprocess_environment_is_an_allowlist(monkeypatch):
    received = []
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-not-a-key")
    monkeypatch.setenv("COPILOT_GITHUB_TOKEN", "synthetic-not-a-token")
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: received.append((a, kw)))
    preflight._run(["/bin/true"])
    args, options = received[0]
    assert args == (["/bin/true"],)
    assert options["env"] == {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "LANG": "C.UTF-8"}
    assert options["timeout"] == 20 and options["stdin"] == subprocess.DEVNULL


@pytest.mark.parametrize("selected", [None, "/tmp/bwrap", "/usr/local/bin/bwrap"])
def test_only_the_root_owned_system_bwrap_may_receive_the_profile(monkeypatch, selected):
    monkeypatch.setattr(preflight.shutil, "which", lambda name: selected)
    with pytest.raises(preflight.SandboxRefused, match="system_bwrap_selection_unverified"):
        preflight._system_bwrap()


@pytest.mark.parametrize("mode,uid", [(0o100777, 0), (0o104755, 0), (0o102755, 0), (0o100755, 1001)])
def test_writable_or_privileged_bwrap_is_refused(monkeypatch, mode, uid):
    monkeypatch.setattr(preflight.shutil, "which", lambda name: "/usr/bin/bwrap")
    original = Path.stat
    monkeypatch.setattr(Path, "stat", lambda path, **kw: SimpleNamespace(st_mode=mode, st_uid=uid)
                        if str(path) == "/usr/bin/bwrap" else original(path, **kw))
    with pytest.raises(preflight.SandboxRefused, match="system_bwrap_permissions_unverified"):
        preflight._system_bwrap()


def test_profile_is_scoped_to_one_binary_not_a_global_policy_change():
    assert preflight.PROFILE == (
        "abi <abi/4.0>,\ninclude <tunables/global>\n"
        "profile gdpval_codex_bwrap /usr/bin/bwrap flags=(unconfined) {\n  userns,\n}\n")
    assert "*" not in preflight.PROFILE and "capability" not in preflight.PROFILE


@pytest.mark.parametrize("filename,job,credential,condition", [
    ("codex-foundry-connection-diagnostic.yml", "diagnose", "Azure Login (OIDC)", None),
    ("batch-run.yml", "batch-run", "Validate Azure OIDC identity before remote access",
     "needs.inspect-mode.outputs.uses_codex_foundry == 'true'"),
])
def test_both_workflows_prove_sandbox_before_credentials(filename, job, credential, condition):
    workflow = yaml.safe_load((ROOT / ".github/workflows" / filename).read_text())
    selected = workflow["jobs"][job]
    assert "ubuntu-24.04" in selected["runs-on"] and "ubuntu-22.04" not in selected["runs-on"]
    steps = selected["steps"]
    index, step = next((i, s) for i, s in enumerate(steps) if "scripts/prepare_codex_sandbox_host.py" in s.get("run", ""))
    credential_index = next(i for i, s in enumerate(steps) if s.get("name") == credential)
    pin = next(i for i, s in enumerate(steps) if "require_pinned_runtime" in s.get("run", ""))
    assert pin < index < credential_index
    assert step.get("if") == condition and "continue-on-error" not in step
    assert "set -euo pipefail" in step["run"] and "|| true" not in step["run"]
    assert "--out" in step["run"] and "secrets." not in json.dumps(step)
    upload = next(s for s in steps if s.get("with", {}).get("path") == "${{ runner.temp }}/codex-sandbox-preflight.json")
    assert "always()" in upload["if"] and upload["with"]["if-no-files-found"] == "error"


def test_historical_survey_observations_are_not_relabelled_as_new_measurements():
    record = json.loads((ROOT / "batch-runner/docs/codex_sandbox_hosts.json").read_text())
    policy = record["execution_policy"]
    assert policy["github_hosted_runner"] == "ubuntu-24.04"
    assert policy["required_same_job_readiness"] == "ready"
    assert policy["prepared_host_observation"] == "not_yet_measured_on_Actions"
    assert policy["required_probes"] == ["bubblewrap_user_and_network_namespaces", "pinned_codex_sandbox_linux_marker"]
    assert record["hosts"]["ubuntu-24.04-host"]["apparmor_restrict_unprivileged_userns"] == "1"
    assert record["hosts"]["ubuntu-24.04-host"]["readiness"] == "user_namespaces_restricted_by_security_policy"
    assert set(runner.UBUNTU_IMAGES) == {"24.04"}
