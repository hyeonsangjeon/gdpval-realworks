"""Inert receipts and fake subprocesses only; never execute bwrap/sysctl on NAS."""

import copy
import json
import os
from pathlib import Path
import socket
import subprocess
from types import SimpleNamespace

import pytest
import yaml

import ghcp_ahp_metadata_broker as broker
import ghcp_ahp_probe as probe
import ghcp_ahp_runner_userns as userns
import ghcp_ahp_thread_policy as policy

ROOT = Path(__file__).resolve().parents[2]
IDENTITY = {"github_run_id": "9005", "github_run_attempt": "1", "github_sha": "a" * 40}


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("offline fixture attempted a process, kernel mutation or network")
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(os, "system", forbidden)


def observation(passed):
    return {"passed": passed, "returncode": 0 if passed else 1,
            "stdout": json.dumps(userns.PROOF) if passed else "",
            "stderr": "" if passed else "bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted",
            "proof": copy.deepcopy(userns.PROOF) if passed else None,
            "scope": "namespace_canary_not_native_thread_or_admission"}


class FakeRunner:
    def __init__(self, checks=(False, True), *, restrict=1, clone=1, load_code=0):
        self.checks = iter(checks)
        self.restrict, self.clone, self.load_code = restrict, clone, load_code
        self.loaded, self.commands, self.probes = False, [], []

    def sysctls(self):
        return {key: {"value": value, "returncode": 0, "stdout": str(value) + "\n", "stderr": ""}
                for key, value in ((userns.RESTRICT, self.restrict), (userns.CLONE, self.clone))}

    def aa_status(self):
        return {"returncode": 0, "profiles": {"enforce": 3, "unconfined": int(self.loaded)}, "processes": 0}

    def profile_loaded(self, name):
        assert name == userns.profile_name(IDENTITY)
        return self.loaded

    def namespace_probe(self, binary):
        self.probes.append(copy.deepcopy(binary))
        return observation(next(self.checks))

    def run(self, command):
        self.commands.append(command)
        if command[:4] == ["sudo", "-n", "apparmor_parser", "--add"]:
            self.loaded = self.load_code == 0
            code = self.load_code
        elif command[:4] == ["sudo", "-n", "apparmor_parser", "--remove"]:
            assert self.loaded
            self.loaded, code = False, 0
        elif command[:4] == ["sudo", "-n", "sysctl", "-w"]:
            assert command[-1] in (userns.RESTRICT + "=0", userns.RESTRICT + "=1")
            self.restrict, code = int(command[-1][-1]), 0
        else:
            pytest.fail("unexpected privileged command: " + repr(command))
        return {"returncode": code, "stdout": "", "stderr": "" if code == 0 else "synthetic parser failure"}


@pytest.fixture
def tree(tmp_path, monkeypatch):
    binary = tmp_path / "inert-bwrap"
    binary.write_bytes(b"not executable: fixture only")
    selected = {"path": str(binary), "sha256": probe.digest(binary), "bytes": binary.stat().st_size,
                "source": "bundled", "version": "synthetic", "candidates": []}
    monkeypatch.setattr(userns, "selected_bwrap", lambda prepared, runner: copy.deepcopy(selected))
    return tmp_path / "prepared", tmp_path / "evidence", selected


@pytest.mark.parametrize("checks,load_code,method", [((True,), 0, "none_required"),
    ((False, True), 0, "a_exact_bwrap_profile"), ((False, False, True), 0, "b_job_scoped_sysctl"),
    ((False, True), 1, "b_job_scoped_sysctl")])
def test_exact_profile_first_then_only_if_failed_job_scoped_fallback_and_restore(tree, checks, load_code, method):
    prepared, evidence, binary = tree
    runner = FakeRunner(checks, load_code=load_code)
    record = userns.prepare(prepared, evidence, IDENTITY, runner)
    assert record["status"] == "ready" and record["method"] == method
    assert record["execution_allowed"] is record["admission_allowed"] is False
    assert record["isolation"] == {"codex_sandbox_changed": False, "netns_omitted": False,
        "network_allowed": False, "privilege_boundary": "same_as_metadata_broker"}
    userns.verify_for_auth(evidence / "runner-userns.json", prepared, evidence, IDENTITY, runner=runner)
    use = json.loads((evidence / "runner-userns-use.json").read_text())
    assert use["verified_before_auth"] is True and use["preparation_sha256"] == probe.digest(evidence / "runner-userns.json")
    assert runner.probes == [binary] * len(checks)
    if method != "none_required":
        assert record["profile"]["text"] == userns.profile_text(binary["path"], IDENTITY)
        assert record["profile"]["sha256"] == probe.digest(evidence / "runner-userns.apparmor")
        assert runner.commands[0][:4] == ["sudo", "-n", "apparmor_parser", "--add"]
    if method == "b_job_scoped_sysctl":
        assert runner.commands[-1] == ["sudo", "-n", "sysctl", "-w", userns.RESTRICT + "=0"]
        assert userns.values(record["after"]) == {userns.RESTRICT: 0, userns.CLONE: 1}
        if load_code == 0:
            assert runner.commands[-2][:4] == ["sudo", "-n", "apparmor_parser", "--remove"]
    else:
        assert not any("sysctl" in command for command in runner.commands)
        assert record["after"] == record["before"]
    digest = probe.digest(evidence / "runner-userns.json")
    cleanup = userns.restore(evidence, IDENTITY, runner)
    assert cleanup["status"] == "restored" and not runner.loaded and runner.restrict == 1
    assert probe.digest(evidence / "runner-userns.json") == digest  # immutable final evidence
    with pytest.raises(probe.Refused, match="already_restored"):
        userns.verify_for_auth(evidence / "runner-userns.json", prepared, evidence, IDENTITY, runner=runner)


def test_failed_fallback_remains_failed_and_still_restores_original_sysctl(tree):
    prepared, evidence, _ = tree
    runner = FakeRunner((False, False, False))
    with pytest.raises(probe.Refused, match="namespace_probe_failed"):
        userns.prepare(prepared, evidence, IDENTITY, runner)
    record = json.loads((evidence / "runner-userns.json").read_text())
    assert record["status"] == "refused" and record["method"] == "b_job_scoped_sysctl"
    assert userns.restore(evidence, IDENTITY, runner)["status"] == "restored"
    assert runner.restrict == 1


@pytest.mark.parametrize("restrict,clone", [(0, 1), (1, 0), ("not_reported", 1), (1, "not_reported")])
def test_no_unsupported_kernel_or_clone_mutation(tree, restrict, clone):
    prepared, evidence, _ = tree
    runner = FakeRunner((False,), restrict=restrict, clone=clone)
    with pytest.raises(probe.Refused):
        userns.prepare(prepared, evidence, IDENTITY, runner)
    assert runner.commands == []


@pytest.mark.parametrize("mutation", ["status", "method", "identity", "missing", "synthetic", "execution", "admission",
    "baseline", "proof_missing", "proof_changed", "proof_wrong_type", "returncode", "binary", "after", "before",
    "profile_hash", "profile_text", "profile_file", "profile_absent", "sysctl_attempted"])
def test_missing_changed_or_forged_preparation_cannot_reach_auth(tree, mutation):
    prepared, evidence, _ = tree
    runner = FakeRunner()
    value = userns.prepare(prepared, evidence, IDENTITY, runner)
    if mutation == "status": value["status"] = "refused"
    elif mutation == "method": value["method"] = "sysctl_first"
    elif mutation == "identity": value["runner"]["github_sha"] = "b" * 40
    elif mutation == "missing": del value["final_probe"]
    elif mutation == "synthetic": value["synthetic"] = True
    elif mutation == "execution": value["execution_allowed"] = True
    elif mutation == "admission": value["admission_allowed"] = True
    elif mutation == "baseline": value["baseline"]["passed"] = True
    elif mutation == "proof_missing": value["final_probe"]["proof"] = None
    elif mutation == "proof_changed": value["final_probe"]["proof"]["interfaces"].append("eth0")
    elif mutation == "proof_wrong_type": value["final_probe"]["proof"]["root_read_only"] = 1
    elif mutation == "returncode": value["final_probe"]["returncode"] = 1
    elif mutation == "binary": value["bwrap"]["sha256"] = "b" * 64
    elif mutation == "after": value["after"][userns.RESTRICT]["value"] = 0
    elif mutation == "before": value["before"][userns.CLONE]["value"] = True
    elif mutation == "profile_hash": value["profile"]["sha256"] = "b" * 64
    elif mutation == "profile_text": value["profile"]["text"] += "network,\n"
    elif mutation == "profile_file": (evidence / "runner-userns.apparmor").write_text("altered")
    elif mutation == "profile_absent": runner.loaded = False
    elif mutation == "sysctl_attempted": value["sysctl_attempted"] = True
    userns.write_receipt(evidence, value)
    with pytest.raises(probe.Refused):
        userns.verify_for_auth(evidence / "runner-userns.json", prepared, evidence, IDENTITY, runner=runner)
    assert not (evidence / "runner-userns-use.json").exists()


@pytest.mark.parametrize("damage", ["no_profile_attempt", "profile_succeeded", "profile_still_loaded", "no_sysctl_attempt", "write_failed"])
def test_fallback_requires_real_failed_profile_and_verified_sysctl(tree, damage):
    prepared, evidence, _ = tree
    runner = FakeRunner((False, False, True))
    value = userns.prepare(prepared, evidence, IDENTITY, runner)
    if damage == "no_profile_attempt": value["profile"]["attempted"] = False
    elif damage == "profile_succeeded": value["profile_probe"]["passed"] = True
    elif damage == "profile_still_loaded": value["profile"]["loaded"] = True
    elif damage == "no_sysctl_attempt": value["sysctl_attempted"] = False
    elif damage == "write_failed": value["sysctl_change"]["returncode"] = 1
    userns.write_receipt(evidence, value)
    with pytest.raises(probe.Refused):
        userns.verify_for_auth(evidence / "runner-userns.json", prepared, evidence, IDENTITY, runner=runner)


@pytest.mark.parametrize("path", ["relative", "/tmp/bwrap*", "/tmp/bwrap?", "/tmp/[b]wrap", "/tmp/a\nbwrap",
                                '/tmp/a"bwrap', "/tmp/../bwrap", "/tmp/@{OTHER}"])
def test_profile_attachment_cannot_be_a_wildcard_or_injection(path):
    with pytest.raises(probe.Refused):
        userns.profile_text(path, IDENTITY)


def test_no_repeated_preparation_or_symlink_input(tree, tmp_path):
    prepared, evidence, _ = tree
    runner = FakeRunner((True,))
    userns.prepare(prepared, evidence, IDENTITY, runner)
    with pytest.raises(probe.Refused, match="no_repeat"):
        userns.prepare(prepared, evidence, IDENTITY, runner)
    link = tmp_path / "link"
    link.symlink_to(evidence)
    with pytest.raises(probe.Refused, match="symlink"):
        userns.profile_text(link / "bwrap", IDENTITY)


@pytest.mark.parametrize("mode", ["prepare", "restore"])
def test_nas_cli_refuses_before_files_commands_and_credential_access(monkeypatch, tmp_path, capsys, mode):
    def refuse(): raise probe.Refused("synthetic_not_actions")
    monkeypatch.setattr(userns.prewarm, "context", refuse)
    monkeypatch.setattr(userns, "Runner", lambda: pytest.fail("NAS constructed live runner"))
    assert userns.main([mode, "--prepared", str(tmp_path / "p"), "--evidence", str(tmp_path / "e")]) == 2
    assert "synthetic_not_actions" in capsys.readouterr().out
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("key", ["COPILOT_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"])
def test_no_secret_environment_on_prepare_or_restore(monkeypatch, tmp_path, capsys, key):
    monkeypatch.setattr(userns.prewarm, "context", lambda: IDENTITY)
    monkeypatch.setenv(key, "SYNTHETIC_DO_NOT_PRINT")
    assert userns.main(["prepare", "--prepared", str(tmp_path / "p"), "--evidence", str(tmp_path / "e")]) == 2
    text = capsys.readouterr().out
    assert "credential_environment_refused" in text and "SYNTHETIC_DO_NOT_PRINT" not in text
    assert not list(tmp_path.iterdir())


def test_real_command_builder_has_same_outer_isolation_and_stricter_inner_read_only_netns(monkeypatch):
    runner = object.__new__(userns.Runner)
    calls = []
    monkeypatch.setattr(runner, "run", lambda command: calls.append(command) or {
        "returncode": 0, "stdout": json.dumps(userns.PROOF), "stderr": ""})
    assert runner.namespace_probe({"path": "/tmp/bwrap", "sha256": "a" * 64, "source": "bundled"})["passed"] is True
    command, = calls
    prefix = broker.isolation_prefix()
    assert command[:len(prefix)] == prefix
    for arg in ("--net", "--pid", "--mount", "--no-new-privs", "--bounding-set=-all", "--inh-caps=-all", "--ambient-caps=-all"):
        assert arg in prefix
    assert command[-5:] == [userns.EXEC_CANARY, "/tmp/bwrap", "a" * 64, "bundled", userns.INNER_AUDIT]
    for arg in ("--unshare-user", "--unshare-net", "--unshare-pid", '"--ro-bind", "/", "/"'):
        assert arg in userns.EXEC_CANARY
    assert "socket.if_nameindex()" in userns.INNER_AUDIT  # netns, not inherited sysfs view
    for text in (userns.EXEC_CANARY, userns.INNER_AUDIT):
        assert "http" not in text and "connect(" not in text and "COPILOT" not in text


@pytest.mark.parametrize("bad", ["not-json", '{"root_read_only":true,"root_read_only":true}', 'null', '{}'])
def test_zero_exit_with_missing_or_invalid_isolation_proof_is_still_failure(monkeypatch, bad):
    runner = object.__new__(userns.Runner)
    monkeypatch.setattr(runner, "run", lambda command: {"returncode": 0, "stdout": bad, "stderr": ""})
    assert runner.namespace_probe({"path": "/tmp/bwrap", "sha256": "a" * 64, "source": "bundled"})["passed"] is False


def test_diagnostic_subprocess_has_no_inherited_secret_or_shell(monkeypatch):
    monkeypatch.setattr(userns.prewarm, "context", lambda: IDENTITY)
    monkeypatch.setenv("COPILOT_GITHUB_TOKEN", "SYNTHETIC_SECRET_MUST_NOT_LEAVE")
    calls = []
    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout="1\n", stderr="")
    monkeypatch.setattr(subprocess, "run", run)
    runner = userns.Runner()
    assert runner.sysctls()[userns.RESTRICT]["value"] == 1
    for command, options in calls:
        assert options == {"env": userns.ENVIRONMENT, "capture_output": True, "text": True, "timeout": 25, "check": False}
        assert command[:2] == ["sysctl", "-n"]


def test_workflow_prepares_before_secret_and_restores_before_unconditional_artifact_upload():
    workflow = yaml.load((ROOT / ".github/workflows/agentic-v2-ghcp-sol-gate.yml").read_text(), Loader=yaml.BaseLoader)
    job = workflow["jobs"]["ahp-zero-turn"]
    assert job["runs-on"] == "ubuntu-24.04" and job["environment"] == "ghcp-sol-gate"
    steps = job["steps"]
    prep = next(i for i, step in enumerate(steps) if step.get("id") == "runner-userns")
    auth = next(i for i, step in enumerate(steps) if "secrets.COPILOT_GITHUB_TOKEN" in str(step))
    cleanup = next(i for i, step in enumerate(steps) if "ghcp_ahp_runner_userns.py restore" in step.get("run", ""))
    assert prep < auth < cleanup < len(steps) - 1
    assert "if" not in steps[prep] and "env" not in steps[prep] and "env" not in steps[cleanup]
    assert "always()" in steps[cleanup]["if"]
    assert '--runner-userns-receipt "$RUNNER_TEMP/ghcp-zero-turn/evidence/runner-userns.json"' in steps[auth]["run"]
    assert steps[-1]["if"] == "always()" and "evidence/*.json" in steps[-1]["with"]["path"]
    for step in (steps[prep], steps[auth], steps[cleanup]):
        assert "continue-on-error" not in step and "|| true" not in step.get("run", "")


@pytest.mark.parametrize("help_text,help_code,expected", [
    ("--as-pid-1 --perms --argv0", 0, "system"),
    ("--as-pid-1 --perms", 1, "system"),  # Pinned code checks help, not exit.
    ("--as-pid-1", 0, "bundled"), ("--perms", 0, "bundled"), ("", 1, "bundled")])
def test_selects_actual_source_defined_system_or_sdk_bwrap_without_execution(tmp_path, monkeypatch, help_text, help_code, expected):
    native = tmp_path / "sdk/bin/codex"
    bundled = tmp_path / "sdk/codex-resources/bwrap"
    bundled.parent.mkdir(parents=True)
    bundled.write_bytes(b"inert sdk")
    bundled.chmod(0o700)
    system = tmp_path / "system-bwrap"
    system.write_bytes(b"inert system")
    system.chmod(0o700)
    monkeypatch.setattr(userns.wire, "discover_native_binary", lambda *args: (native, "", {}))
    monkeypatch.setattr(userns, "BWRAP_SHA256", probe.digest(bundled))
    monkeypatch.setattr(userns, "SYSTEM_PATHS", (system, tmp_path / "not-on-path"))
    calls = []
    def run(command):
        calls.append(command)
        return {"returncode": help_code if command[-1] == "--help" else 0,
                "stdout": help_text if command[-1] == "--help" else "bwrap synthetic", "stderr": ""}
    row = userns.selected_bwrap(tmp_path, SimpleNamespace(run=run))
    selected = system if expected == "system" else bundled
    assert row["source"] == expected and row["path"] == str(selected)
    assert row["sha256"] == probe.digest(selected) and row["version"] == "bwrap synthetic"
    assert calls == [[str(system), "--help"], [str(selected), "--version"]]


@pytest.mark.parametrize("damage", ["digest", "symlink", "setuid", "setgid", "not_executable", "version"])
def test_bwrap_drift_or_privileged_substitute_refuses_before_mutation(tmp_path, monkeypatch, damage):
    native = tmp_path / "sdk/bin/codex"
    bundled = tmp_path / "sdk/codex-resources/bwrap"
    bundled.parent.mkdir(parents=True)
    bundled.write_bytes(b"inert")
    bundled.chmod(0o700)
    monkeypatch.setattr(userns.wire, "discover_native_binary", lambda *args: (native, "", {}))
    monkeypatch.setattr(userns, "BWRAP_SHA256", probe.digest(bundled))
    monkeypatch.setattr(userns, "SYSTEM_PATHS", (tmp_path / "absent",))
    if damage == "digest": bundled.write_bytes(b"changed")
    elif damage == "symlink":
        original = bundled.with_name("original")
        bundled.rename(original)
        bundled.symlink_to(original)
    elif damage == "setuid": bundled.chmod(0o4700)
    elif damage == "setgid": bundled.chmod(0o2700)
    elif damage == "not_executable": bundled.chmod(0o600)
    runner = SimpleNamespace(run=lambda command: {"returncode": 1 if damage == "version" else 0, "stdout": "", "stderr": ""})
    with pytest.raises(probe.Refused):
        userns.selected_bwrap(tmp_path, runner)


def test_failed_cleanup_is_recorded_and_never_ignored(tree):
    prepared, evidence, _ = tree
    runner = FakeRunner((False, False, True))
    userns.prepare(prepared, evidence, IDENTITY, runner)
    runner.run = lambda command: {"returncode": 1, "stdout": "", "stderr": "synthetic restore failure"}
    with pytest.raises(probe.Refused, match="cleanup_sysctl_failed"):
        userns.restore(evidence, IDENTITY, runner)
    value = json.loads((evidence / "runner-userns-cleanup.json").read_text())
    assert value["status"] == "refused" and value["execution_allowed"] is False


@pytest.mark.parametrize("field,value", [("kernel.apparmor_restrict_unprivileged_userns", 0),
                                        ("kernel.unprivileged_userns_clone", 0)])
def test_between_stage_and_auth_kernel_drift_is_refused(tree, field, value):
    prepared, evidence, _ = tree
    runner = FakeRunner()
    userns.prepare(prepared, evidence, IDENTITY, runner)
    if field == userns.RESTRICT: runner.restrict = value
    else: runner.clone = value
    with pytest.raises(probe.Refused, match="state_changed"):
        userns.verify_for_auth(evidence / "runner-userns.json", prepared, evidence, IDENTITY, runner=runner)


def test_canary_programs_compile_but_are_never_executed_locally():
    compile(userns.EXEC_CANARY, "exec_canary", "exec")
    compile(userns.INNER_AUDIT, "inner_audit", "exec")
    assert userns.SYSTEM_PATHS == (Path("/usr/bin/bwrap"), Path("/bin/bwrap"))


@pytest.mark.parametrize("response,success,errors,invalid", [
    ({"result": {"thread": {"id": "fixture-thread"}}}, 1, 0, 0),
    ({"error": {"code": -32603, "message": "bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted"}}, 0, 1, 0),
    ({"result": {"thread": {"id": "fixture-thread"}}, "error": {"code": -32603}}, 0, 1, 0),
    ({"result": None}, 0, 0, 1), ({"result": {}}, 0, 0, 1),
    ({"result": {"thread": {"id": ""}}}, 0, 0, 1),
    ({"result": {"thread": {"id": "not_reported"}}}, 0, 0, 1),
    ({"result": {"thread": {"id": True}}}, 0, 0, 1), ({}, 0, 0, 1)])
def test_native_error_response_never_counts_as_successful_thread_reply(tmp_path, response, success, errors, invalid):
    directory = tmp_path / "wire"
    directory.mkdir()
    rows = [{"kind": "ipc_request", "stream": "ipc-1", "value": {"id": 13, "method": "thread/start"}},
            {"kind": "ipc_response", "stream": "ipc-1", "value": {"id": 13, **response}}]
    (directory / "wire-1.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
    result = policy.await_native_thread(tmp_path, 0)
    assert (result["replies"], result["error_replies"], result["invalid_replies"]) == (success, errors, invalid)
    if errors: assert result["status"] == "native_thread_error_observed"


@pytest.mark.parametrize("change", ["id", "stream", "process", "incomplete"])
def test_uncorrelated_or_partial_response_does_not_count_as_thread_success(tmp_path, change):
    directory = tmp_path / "wire"
    directory.mkdir()
    start = {"kind": "ipc_request", "stream": "ipc-1", "value": {"id": 13, "method": "thread/start"}}
    reply = {"kind": "ipc_response", "stream": "ipc-2" if change == "stream" else "ipc-1",
             "value": {"id": 14 if change == "id" else 13, "result": {"thread": {"id": "fixture-thread"}}}}
    path = directory / "wire-1.jsonl"
    path.write_text(json.dumps(start) + "\n")
    path = directory / "wire-2.jsonl" if change == "process" else path
    with path.open("a") as output:
        output.write(json.dumps(reply) + ("" if change == "incomplete" else "\n"))
    result = policy.await_native_thread(tmp_path, 0)
    assert result == {"status": "native_thread_not_reported_before_deadline", "replies": 0,
                      "error_replies": 0, "invalid_replies": 0}
