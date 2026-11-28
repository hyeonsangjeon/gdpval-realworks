"""Choice-3 contracts with fabricated evidence and inert Node fixtures only."""

import copy
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import tarfile
import time

import pytest
import yaml

import ghcp_ahp_default_policy as default
import ghcp_ahp_management as management
import ghcp_ahp_metadata_broker as broker
import ghcp_ahp_probe as probe
import ghcp_ahp_thread_policy as original
import ghcp_ahp_wire_capture as wire
import ghcp_ahp_zero_turn_admission as read_only
from ghcp_ahp_diagnostics import DiagnosticRedactor
from .test_ghcp_ahp_probe import backend_probe_fixture

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/agentic-v2-ghcp-sol-gate.yml"
NODE = shutil.which("node")
FIXTURE = Path(__file__).parent / "fixtures/ghcp_ahp_default_policy_fixture.cjs"
INPUT = """      default_policy_unpatched:
        description: Separate choice-3 zero-turn observation of unpatched defaults; never read-only or paid admission
        type: boolean
        default: false
        required: true
"""
BLOCK_HASHES = {
    "DEFAULT_POLICY_SELECTION_GUARD": "1a7c016b17506a97079a62db77864ebdd30d974488a00e247bbf8d2bce8709cf",
    "DEFAULT_POLICY_UNPATCHED_ZERO_TURN": "07b0321cd8a6f60417098f548b1991aede5ed76886b95b8315e40742a49dd4c0",
}


def restore_workflow(text):
    """Exact inverse of these additions; every historical hash stays intact."""
    assert text.count(INPUT) == 1
    text = text.replace(INPUT, "", 1)
    for marker, digest in BLOCK_HASHES.items():
        indent = "      " if marker == "DEFAULT_POLICY_SELECTION_GUARD" else "  "
        pattern = re.escape(indent + "# BEGIN " + marker + "\n") + r".*?" + re.escape(indent + "# END " + marker + "\n")
        blocks = re.findall(pattern, text, re.S)
        assert len(blocks) == 1 and hashlib.sha256(blocks[0].encode()).hexdigest() == digest
        block = blocks[0] + ("\n" if marker == "DEFAULT_POLICY_UNPATCHED_ZERO_TURN" else "")
        assert text.count(block) == 1
        text = text.replace(block, "", 1)
    suffix = " && inputs.default_policy_unpatched != true"
    assert text.count(suffix) == 6
    return text.replace(suffix, "")


@pytest.fixture(autouse=True)
def only_inert_node(monkeypatch):
    real = subprocess.Popen
    def popen(command, *args, **kwargs):
        assert type(command) is list and len(command) == 4 and command[:2] == [NODE, str(FIXTURE)]
        assert kwargs.get("shell", False) is False
        return real(command, *args, **kwargs)
    def forbidden(*args, **kwargs):
        pytest.fail("default-policy fixture attempted native execution or external authentication")
    monkeypatch.setattr(subprocess, "Popen", popen)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(os, "system", forbidden)


def identity(path, inode):
    return {"path": path, "realpath": path, "device": 77, "inode": inode, "uid": 1001}


def hashed_identity(value):
    return {"path_sha256": default.sha(value["path"].encode()), "realpath_sha256": default.sha(value["realpath"].encode()),
            **{key: value[key] for key in ("device", "inode", "uid")}}


def candidate():
    """Counterfactual live-shaped records to test the verifier, not live proof."""
    state = "/tmp/default-policy-fixture"
    workspace, temporary = identity(state + "/workspace", 101), identity(state + "/tmp/job-temp", 102)
    node = {"path": "/tmp/fixture-original-server/node", "sha256": "a" * 64}
    contract = {"schema": "ghcp-default-unpatched-load-contract-v1", "admission_profile": default.PROFILE,
        "vscode_commit": wire.PIN, "server_archive_sha256": probe.load_manifest()["artifacts"]["server"]["sha256"],
        "node": node, "entry": {"path": "/tmp/fixture-original-server/" + default.RELATIVE, "sha256": default.UNPATCHED_BUNDLE_SHA256},
        "loader_sha256": probe.digest(default.LOADER), "state_root": state, "challenge": "b" * 32,
        "patched_ghcp": False, "patches_applied": [], "synthetic": False, "execution_allowed": False}
    digest = default.sha(default.encoded(contract))
    shared = {"process": "wire-42.jsonl", "synthetic": False}
    response = {"thread": {"id": "fixture-thread"}, "model": "gpt-5.6-sol", "modelProvider": "vscode-proxy",
        "reasoningEffort": "max", "approvalPolicy": "on-request", "activePermissionProfile": {"id": "vscode-workspace"},
        "sandbox": {"type": "workspaceWrite", "networkAccess": False, "writableRoots": [workspace["path"], temporary["path"]],
                    "excludeSlashTmp": True, "excludeTmpdirEnvVar": True}}
    rows = [
        {"kind": "default_policy_child", "process": "wire-41.jsonl", "synthetic": False,
         "child_pid": 42, "parent_pid": 41, "contract_sha256": digest, "admission_profile": default.PROFILE},
        {**shared, "kind": "observer_installed", "entrypoint": default.ENTRYPOINT, "admission_profile": default.PROFILE,
         "model_free": True, "session_only": True, "observer_sha256": probe.digest(wire.PRELOAD)},
        {**shared, "kind": "default_policy_loaded", "schema": "ghcp-default-unpatched-load-v1", "admission_profile": default.PROFILE,
         "pid": 42, "ppid": 41, "contract_sha256": digest, "phase": "node_load_hook_before_evaluation",
         "patched_ghcp": False, "execution_allowed": False, **dict.fromkeys(
             ("loaded_source_sha256", "disk_before_sha256", "disk_after_sha256"), default.UNPATCHED_BUNDLE_SHA256)},
        {**shared, "kind": "ipc_request", "stream": "ipc-1", "value": {"id": 13, "method": "thread/start", "params": {
            "model": "gpt-5.6-sol", "modelProvider": "vscode-proxy", "approvalPolicy": "on-request",
            "permissions": "vscode-workspace", "cwd": workspace["path"], "runtimeWorkspaceRoots": [workspace["path"]]}}},
        {**shared, "kind": "default_policy_sandbox_scope", "stream": "ipc-1", "request_id": 13, "thread_id": "fixture-thread",
         "schema": "ghcp-default-unpatched-sandbox-scope-v1", "admission_profile": default.PROFILE, "status": "measured",
         "verdict": "default_workspace_policy_observed", "reported_sandbox": "workspaceWrite",
         "reported_writable_roots": copy.deepcopy(response["sandbox"]["writableRoots"]), "approval": "on-request",
         "network": False, "permission_profile": "vscode-workspace", "exclude_slash_tmp": True, "exclude_tmpdir_env_var": True,
         "binding": {"status": "measured", "state_root": state, "job_tmpdir": temporary}, "tmpdir_at_reply": copy.deepcopy(temporary),
         "workspace_identity": hashed_identity(workspace), "root_identities": [
             {"role": "job_workspace", **hashed_identity(workspace)}, {"role": "job_tmpdir", **hashed_identity(temporary)}]},
        {**shared, "kind": "ipc_response", "stream": "ipc-1", "value": {"id": 13, "result": response}},
        {**shared, "kind": "metadata_response", "method": "GET", "host": "api.github.com", "path": "/copilot_internal/user",
         "status": 200, "external_request": True},
        {**shared, "kind": "metadata_response", "method": "GET", "host": "api.enterprise.githubcopilot.com", "path": "/models",
         "status": 200, "external_request": True},
    ]
    capture = wire.analyze(rows, synthetic=False)
    capture.update(capture_status="captured", patched_ghcp=False, admission_profile=default.PROFILE, bootstrap={
        "admission_profile": default.PROFILE, "default_policy_runtime": contract, "model_free": True,
        "session_policy": True, "authenticated_zero_turn": True,
        "agent_host_fork": {"entrypoint": default.ENTRYPOINT, "state_root": state, "files": {"node": node}}})
    return capture, {"authenticate": {"result": {}}, "createSession": {"result": {}}}


def test_default_profile_is_separate_and_never_opens_read_only_or_paid_admission():
    capture, results = candidate()
    before = copy.deepcopy(original.POLICY)
    report = default.assess(capture, results)
    assert report["admission_allowed"] is True, report
    assert report["admission_profile"] == report["comparison_row"] == default.PROFILE
    assert report["admission_scope"] != read_only.SCOPE
    assert report["patched_ghcp"] is report["execution_allowed"] is report["read_only_requirement"] is False
    assert report["owner_selection"] == "not_made" and report["requested_policy"] == {}
    assert report["native_policy_report"]["sandbox"]["type"] == "workspaceWrite"
    assert report["observed"]["approval"] == "on-request" and report["observed"]["permission_profile"] == "vscode-workspace"
    assert report["observed"]["network"] is False and len(report["observed"]["writable_roots"]) == 2
    assert all(report["verdicts"][key] == "deferred_to_first_turn" for key in read_only.DEFERRED)
    assert report["settings_verified"] is False and report["first_turn_required"] is True
    with pytest.raises(probe.Refused, match="zero_turn_scope_contract_refused"):
        read_only.require_scoped_admission(report)
    assert original.assess(capture, results)["admission_allowed"] is False
    assert original.POLICY == before
    assert probe.select_thread_policy() is original and probe.select_thread_policy(default.PROFILE) is default


@pytest.mark.parametrize("field", list(default.EXPECTED))
@pytest.mark.parametrize("damage", ["missing", "wrong"])
def test_every_required_native_field_is_observed_not_defaulted(field, damage):
    capture, results = candidate()
    thread = capture["native_applied_snapshots"][0]
    owner, key = (thread["permission_profile"], "id") if field == "permission_profile" else (thread["values"], field)
    if damage == "missing": del owner[key]
    else: owner[key] = True if field == "network" else "not-the-default"
    report = default.assess(capture, results)
    assert report["admission_allowed"] is False
    assert "unreported_or_mismatched:" + field in report["reasons"]
    assert report["observed"][field] == ("not_reported" if damage == "missing" else owner[key])


@pytest.mark.parametrize("damage", ["profile", "patched", "load_missing", "load_hash", "pid", "loader_hash", "synthetic",
    "scope_missing", "scope_profile", "roots_missing", "root_changed", "root_identity", "duplicate_root",
    "tmpdir_changed", "workspace_changed", "network", "approval", "broad_tmp", "foreign_thread", "turn", "capi", "capture_error",
    "auth_missing", "session_error", "metadata401", "metadata403", "metadata_extra"])
def test_profile_runtime_policy_roots_and_zero_turn_boundaries_fail_closed(damage):
    capture, results = candidate()
    load = next(row for row in capture["records"] if row["kind"] == "default_policy_loaded")
    scope = next(row for row in capture["records"] if row["kind"] == "default_policy_sandbox_scope")
    thread = capture["native_applied_snapshots"][0]
    if damage == "profile": capture["bootstrap"]["admission_profile"] = "patched_read_only"
    if damage == "patched": capture["patched_ghcp"] = True
    if damage == "load_missing": capture["records"].remove(load)
    if damage == "load_hash": load["loaded_source_sha256"] = "0" * 64
    if damage == "pid": load["pid"] = 43
    if damage == "loader_hash": capture["bootstrap"]["default_policy_runtime"]["loader_sha256"] = "0" * 64
    if damage == "synthetic": capture["synthetic"] = True
    if damage == "scope_missing": capture["records"].remove(scope)
    if damage == "scope_profile": scope["admission_profile"] = "patched_read_only"
    if damage == "roots_missing": del thread["sandbox_report"]["writableRoots"]
    if damage == "root_changed": thread["sandbox_report"]["writableRoots"][0] = "/tmp"
    if damage == "root_identity": scope["root_identities"][0]["realpath_sha256"] = "0" * 64
    if damage == "duplicate_root": scope["root_identities"][1] = copy.deepcopy(scope["root_identities"][0])
    if damage == "tmpdir_changed": scope["tmpdir_at_reply"]["inode"] += 1
    if damage == "workspace_changed": scope["workspace_identity"]["path_sha256"] = "0" * 64
    if damage == "network": thread["sandbox_report"]["networkAccess"] = True
    if damage == "approval": thread["values"]["approval"] = "untrusted"
    if damage == "broad_tmp": thread["sandbox_report"]["excludeSlashTmp"] = False
    if damage == "foreign_thread": thread["process"] = "wire-99.jsonl"
    if damage == "turn": capture["native_requests"].append({"request": {"method": "turn/start"}})
    if damage == "capi": capture["capi_requests"].append({"model": "gpt-5.6-sol"})
    if damage == "capture_error": capture["capture_errors"].append("wire_model_free_rpc_refused")
    if damage == "auth_missing": results.pop("authenticate")
    if damage == "session_error": results["createSession"] = {"error": {"message": "fixture error"}}
    if damage in {"metadata401", "metadata403"}: capture["metadata_http"][0]["status"] = int(damage[-3:])
    if damage == "metadata_extra": capture["metadata_http"].append(copy.deepcopy(capture["metadata_http"][0]))
    report = default.assess(capture, results)
    assert report["admission_allowed"] is False and report["reasons"], report
    assert report["execution_allowed"] is False and report["patched_ghcp"] is False


def test_redacted_workspace_path_keeps_raw_report_and_hash_bound_identity():
    capture, results = candidate()
    path = capture["native_applied_snapshots"][0]["sandbox_report"]["writableRoots"][0]
    masked = DiagnosticRedactor("SYNTHETIC_TOKEN_NO_AUTH").clean(capture)
    assert path not in json.dumps(masked)
    report = default.assess(masked, results)
    assert report["admission_allowed"] is True, report
    assert report["observed"]["writable_roots"][0] == "[REDACTED]"
    assert report["sandbox_scope"]["workspace_identity"]["path_sha256"] == default.sha(path.encode())


def test_patched_bundle_cannot_be_relabelled_unpatched_even_with_consistent_hashes():
    capture, results = candidate()
    patched_sha = "5006baa5e4e032cf28f47de802b386ebed6b2c3616943943b3cfa06fce4a7c43"
    contract = capture["bootstrap"]["default_policy_runtime"]
    contract["entry"]["sha256"] = patched_sha
    changed = default.sha(default.encoded(contract))
    for row in capture["records"]:
        if row["kind"] in {"default_policy_loaded", "default_policy_child"}: row["contract_sha256"] = changed
        if row["kind"] == "default_policy_loaded":
            row.update(dict.fromkeys(("loaded_source_sha256", "disk_before_sha256", "disk_after_sha256"), patched_sha))
    report = default.assess(capture, results)
    assert report["admission_allowed"] is False and "default_policy_loaded_hash_refused" in report["reasons"]


@pytest.mark.parametrize("damage", ["unknown_field", "missing_field", "challenge", "entry_path", "entrypoint"])
def test_unpatched_loader_contract_has_no_alias_or_extensible_bypass(damage):
    capture, results = candidate()
    contract = capture["bootstrap"]["default_policy_runtime"]
    if damage == "unknown_field": contract["bypass"] = True
    if damage == "missing_field": del contract["challenge"]
    if damage == "challenge": contract["challenge"] = ""
    if damage == "entry_path": contract["entry"]["path"] = "/tmp/other/agentHostMain.js"
    if damage == "entrypoint": capture["bootstrap"]["agent_host_fork"]["entrypoint"] = "fixture"
    report = default.assess(capture, results)
    assert report["admission_allowed"] is False and "default_policy_unpatched_contract_refused" in report["reasons"]


def chain(tmp_path):
    root = tmp_path / default.PROFILE
    root.mkdir()
    capture, results = candidate()
    probe.save_json(root / "wire-capture.json", capture)
    probe.save_json(root / "probe.json", {**default.LABELS, "rpc_results": results})
    default.export(root, results)
    policy = json.loads((root / default.POLICY_FILE).read_text())
    handshake = {"schema": "ghcp-default-unpatched-handshake-v1", "status": "probe_completed", "reason_codes": [],
                 **{key: policy[key] for key in default.FIELDS}}
    probe.save_json(root / default.HANDSHAKE_FILE, handshake)
    default.write_summary(root, handshake)
    return root


def test_default_evidence_has_disjoint_names_and_cannot_overwrite_choice_one(tmp_path):
    root = chain(tmp_path)
    expected = {"probe.json", "wire-capture.json", default.POLICY_FILE, default.HANDSHAKE_FILE, default.SUMMARY_FILE, default.SUMMARY_MD}
    assert {path.name for path in root.iterdir()} == expected
    assert default.verify_chain(root)["admission_allowed"] is True
    before = {path.name: path.read_bytes() for path in root.iterdir()}
    with pytest.raises(FileExistsError):
        default.export(root, candidate()[1])
    assert {path.name: path.read_bytes() for path in root.iterdir()} == before
    other = tmp_path / "choice-one-evidence"
    other.mkdir()
    (other / "thread-policy.json").write_text("original choice-one bytes")
    with pytest.raises(probe.Refused, match="default_policy_evidence_namespace_refused"):
        default.export(other, {})
    assert (other / "thread-policy.json").read_text() == "original choice-one bytes"


@pytest.mark.parametrize("filename", [default.POLICY_FILE, default.HANDSHAKE_FILE, default.SUMMARY_FILE, default.SUMMARY_MD])
@pytest.mark.parametrize("field", ["admission_profile", "patched_ghcp", "execution_allowed"])
def test_profile_identity_and_false_execution_survive_the_whole_artifact_chain(tmp_path, filename, field):
    root = chain(tmp_path)
    target = root / filename
    if filename.endswith(".md"):
        target.write_text(target.read_text() + "\n" + field + "=wrong\n")
    else:
        value = json.loads(target.read_text())
        value[field] = "patched_read_only" if field == "admission_profile" else True
        target.write_text(json.dumps(value))
    with pytest.raises(probe.Refused):
        default.verify_chain(root)


@pytest.mark.parametrize("values", [ {}, {"codex.permissionsPreset": "full-access"},
    {"codex.permissionsPreset": "default", "codex.networkAccessEnabled": True},
    {"codex.permissionsPreset": "default", "codex.sandboxMode": "read-only"},
    {"codex.permissionsPreset": "default", "codex.approvalPolicy": "untrusted"} ])
def test_resolver_readback_cannot_substitute_other_policy(values):
    with pytest.raises(probe.Refused, match="management_default_policy_readback_refused"):
        default.validate_resolved(values)


def test_default_management_uses_empty_config_and_preserves_unreported_defaults(tmp_path, monkeypatch):
    managed = management.ManagementBridge(tmp_path, time.monotonic() + 30, admission_profile=default.PROFILE)
    session, workspace = "ahp-session:/12345678-1234-4234-8234-123456789abc", "file:///tmp/fixture/workspace"
    values = default.validate_resolved({"codex.permissionsPreset": "default"})
    settings = {"session": session, "workspace": workspace, "model": probe.DESIRED_MODEL, "config": {}}
    def exchange(request):
        if request["op"] == "configure": result = {"configured": True}
        elif request["op"] == "readback": result = {"settings": settings, "resolved_policy": values,
            "derived_permissions": "vscode-workspace", "evidence": management.EVIDENCE,
            "admission_allowed": False, "admission_profile": default.PROFILE}
        else: result = {"result": {"scheme": "ahp-session", "path": session.removeprefix("ahp-session:")}}
        return {"id": request["id"], "ok": True, "result": result}
    monkeypatch.setattr(managed, "_exchange", exchange)
    report = managed.prepare(session, workspace, {})
    assert report["resolved_policy"]["codex.approvalPolicy"] == "not_reported"
    assert managed.create()["transport"] == "vscode-child-ipc"
    assert [row["op"] for row in managed.sent] == ["configure", "readback", "create"]
    assert managed.sent[0]["params"]["config"] == {}
    with pytest.raises(probe.Refused): managed.create()
    original_managed = management.ManagementBridge(tmp_path, time.monotonic() + 30)
    with pytest.raises(probe.Refused, match="management_init_settings_refused"):
        original_managed.prepare(session, workspace, {})


@pytest.mark.parametrize("mode", ["valid", "old_profile", "read_only", "unsafe_network", "sandbox_off", "wrong_model", "wrong_effort",
    "mixed", "tampered", "after_binding", "loaded_mismatch", "rpc_turn", "rpc_hook", "rpc_exec", "rpc_resume", "rpc_write",
    "reply_network", "reply_global_tmp", "reply_duplicate", "reply_missing", "reply_symlink",
    "management_valid", "management_read_only", "management_network"])
def test_real_node_guards_on_inert_fixture_files_and_fake_stdio(tmp_path, mode):
    assert NODE is not None, "Node is required; no skipped guard test"
    result = subprocess.run([NODE, str(FIXTURE), mode, str(tmp_path)],
        env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"ok": True, "synthetic": True, "model_calls": 0, "native_processes": 0}


@pytest.mark.parametrize("profile", ["patched_read_only", "default_policy_unpatched*", "", True])
def test_unknown_or_alias_profile_cannot_select_an_alternative_guard(profile):
    with pytest.raises(probe.Refused): probe.select_thread_policy(profile)
    with pytest.raises(probe.Refused): broker.isolated_command(Path("/unused"), Path("/unused"), Path("/unused"), admission_profile=profile)


@pytest.mark.parametrize("key", ["GHCP_AHP_WIRE_ADMISSION_PROFILE", "GHCP_AHP_WIRE_DEFAULT_CONTRACT", "GHCP_AHP_WIRE_DEFAULT_CONTRACT_SHA256"])
def test_inherited_profile_environment_cannot_contaminate_the_original_path(tmp_path, key):
    with pytest.raises(probe.Refused, match="wire_inherited_default_profile_refused"):
        wire.install(tmp_path / "prepared", tmp_path / "state", {key: "injected"}, model_free=True)
    assert not (tmp_path / "state").exists()


def test_default_broker_preserves_namespace_and_turn_zero_flags_without_token_argv(tmp_path, monkeypatch):
    monkeypatch.setenv("COPILOT_GITHUB_TOKEN", "SYNTHETIC_NO_AUTH")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/leader/ghcp-patched-runtime-receipt-20261106")
    command, environment = broker.isolated_command(tmp_path / "prepared", tmp_path / default.PROFILE,
                                                  tmp_path / "broker.sock", admission_profile=default.PROFILE)
    assert command[-2:] == ["--admission-profile", default.PROFILE]
    assert "--authenticated-zero-turn" in command and "--net" in command and "--no-new-privs" in command
    assert environment["COPILOT_GITHUB_TOKEN"] == "SYNTHETIC_NO_AUTH"
    assert "SYNTHETIC_NO_AUTH" not in " ".join(command)
    with pytest.raises(probe.Refused, match="default_policy_mode_refused"):
        broker.isolated_command(tmp_path, tmp_path, tmp_path, admission_profile=default.PROFILE, prewarm_preparation=tmp_path)


def test_original_workflow_bytes_are_recovered_exactly():
    from .test_ghcp_ahp_prewarm_zero_turn import restore_workflow as restore_prewarm
    from .test_ghcp_ahp_patched_runtime_ci import ORIGINAL_WORKFLOWS
    text = restore_prewarm(WORKFLOW.read_text())
    assert hashlib.sha256(text.encode()).hexdigest() == ORIGINAL_WORKFLOWS[WORKFLOW.name]


@pytest.mark.parametrize("event", ["push", "pull_request", "workflow_dispatch"])
@pytest.mark.parametrize("auth,paid,dry,connection,capability,adapter", [
    (True, False, True, False, False, "ahp-draft"), (False, False, True, False, False, "ahp-draft"),
    (True, True, True, False, False, "ahp-draft"), (True, False, False, False, False, "ahp-draft"),
    (True, False, True, True, False, "ahp-draft"), (True, False, True, False, True, "ahp-draft"),
    (True, False, True, False, False, "copilot-cli"), (False, True, False, False, False, "copilot-cli"),
])
def test_default_selection_cannot_start_choice_one_first_turn_paid_or_grading(event, auth, paid, dry, connection, capability, adapter):
    from .test_ghcp_ahp_zero_turn import evaluate
    value = yaml.load(WORKFLOW.read_text(), Loader=yaml.BaseLoader)
    inputs = {"default_policy_unpatched": True, "authenticated_zero_turn": auth, "execute_paid": paid, "dry_run": dry,
              "connection_only": connection, "capability_only": capability, "execution_adapter": adapter}
    for name in ("ahp-zero-turn", "plan", "task", "paid-task", "ahp-connection", "grader-contract"):
        assert evaluate(value["jobs"][name]["if"], event, inputs) is False
    assert evaluate(value["jobs"]["ahp-default-policy-zero-turn"]["if"], event, inputs) is (
        event == "workflow_dispatch" and auth and not paid and dry and not connection and not capability and adapter == "ahp-draft")


def test_default_workflow_has_no_patch_overlay_or_paid_path_and_one_secret_step():
    value = yaml.load(WORKFLOW.read_text(), Loader=yaml.BaseLoader)
    assert value["on"]["workflow_dispatch"]["inputs"][default.PROFILE]["default"] == "false"
    job = value["jobs"]["ahp-default-policy-zero-turn"]
    assert job["environment"] == "ghcp-sol-gate" and job["runs-on"] == "ubuntu-24.04" and job["timeout-minutes"] == "10"
    assert job["permissions"] == {"contents": "read", "actions": "read"} and job["needs"] == "offline-ci"
    auth = [step for step in job["steps"] if "secrets." in json.dumps(step)]
    assert len(auth) == 1
    assert auth[0]["env"] == {"COPILOT_GITHUB_TOKEN": "${{ secrets.COPILOT_GITHUB_TOKEN }}",
        "GHCP_AUTHENTICATED_ZERO_TURN": "true", "GHCP_PAID_EXECUTION": "false", "GHCP_CONNECTION_ONLY": "false"}
    for forbidden in ("--prewarm-zero-turn-preparation", "--patched-build-receipt", "gh run download", "connection_only=true",
                      "--execute-paid", "continue-on-error", "|| true", "--retry", "$COPILOT_GITHUB_TOKEN", "danger-full-access"):
        assert forbidden not in json.dumps(job)
    assert "ghcp_ahp_runner_userns.py prepare" in json.dumps(job) and "ghcp_ahp_runner_userns.py restore" in json.dumps(job)
    upload = job["steps"][-1]
    assert upload["with"]["name"].startswith("ghcp-ahp-default-policy-unpatched-")
    assert "/default_policy_unpatched/" in upload["with"]["path"]
    assert upload["with"]["include-hidden-files"] == "false"


def test_full_default_probe_uses_its_own_management_guard_receipts_and_summary(backend_probe_fixture, tmp_path, monkeypatch):
    from .test_ghcp_ahp_zero_turn import Wire, CANARY
    for key, value in {"GITHUB_EVENT_NAME": "workflow_dispatch", "GHCP_AUTHENTICATED_ZERO_TURN": "true",
                       "GHCP_PAID_EXECUTION": "false", "GHCP_CONNECTION_ONLY": "false"}.items():
        monkeypatch.setenv(key, value)
    capture, _ = candidate()
    def context(evidence):
        assert evidence.name == default.PROFILE
        return {"synthetic": True}
    monkeypatch.setattr(default, "require_context", context)
    monkeypatch.setattr(default, "verify_live_ready", lambda state: default.verify_load(capture))
    monkeypatch.setattr(default, "await_native_thread", lambda *args: {"replies": 1, "error_replies": 0, "invalid_replies": 0})
    def export(state, evidence, **kwargs):
        probe.save_json(evidence / "wire-capture.json", capture)
        return {"capture_status": "captured", "path": "wire-capture.json", "sha256": probe.digest(evidence / "wire-capture.json")}
    monkeypatch.setattr(wire, "export", export)
    def exchange(self, request):
        assert self.admission_profile == default.PROFILE
        if request["op"] == "configure":
            self.fixture_settings = copy.deepcopy(request["params"])
            assert self.fixture_settings["config"] == {}
            result = {"configured": True}
        elif request["op"] == "readback":
            result = {"settings": self.fixture_settings, "resolved_policy": default.validate_resolved({"codex.permissionsPreset": "default"}),
                "admission_profile": default.PROFILE, "derived_permissions": "vscode-workspace", "evidence": management.EVIDENCE,
                "admission_allowed": False}
        else:
            result = {"result": {"scheme": "ahp-session", "path": self.fixture_settings["session"].removeprefix("ahp-session:")}}
        return {"id": request["id"], "ok": True, "result": result}
    monkeypatch.setattr(management.ManagementBridge, "_exchange", exchange)
    class DefaultWire(Wire):
        def receive(self):
            response = super().receive()
            if self.sent[-1]["method"] == "initialize":
                response["result"]["snapshots"][0]["state"]["config"] = {"values": {"githubMcpServerEnabled": False}}
            if self.sent[-1]["method"] == "resolveSessionConfig":
                response["result"]["values"] = {"codex.permissionsPreset": "default"}
            return response
    port = DefaultWire()
    record, calls, output = backend_probe_fixture(authenticated_zero_turn=True, transport_factory=lambda: port,
        output_name=default.PROFILE, extra_options={"admission_profile": default.PROFILE, "metadata_socket": tmp_path / "broker.sock"})
    assert calls["exit_code"] == 0, record
    assert calls["stops"] >= 1 and record["session_create_requests"] == 1
    assert record["admission_profile"] == default.PROFILE and record["admission_allowed"] is True
    assert record["patched_ghcp"] is record["execution_allowed"] is False
    assert [row["op"] for row in record["management_sent"]] == ["configure", "readback", "create"]
    assert [row["method"] for row in port.sent] == ["initialize", "authenticate", "resolveSessionConfig", "subscribe", "disposeSession"]
    summary = default.verify_chain(output)
    assert summary["admission_allowed"] is True and summary["first_turn_executed"] is False
    assert not any((output / name).exists() for name in ("handshake.json", "thread-policy.json", "summary.json", "summary.md"))
    assert CANARY not in "".join(path.read_text() for path in output.glob("*.json"))


@pytest.mark.parametrize("damage", ["none", "namespace", "old_report", "failed_ci", "wrong_sha", "consumer_is_producer"])
def test_default_context_needs_separate_namespace_and_same_head_green_push(tmp_path, monkeypatch, damage):
    import ghcp_ahp_prewarm_zero_turn as dispatch
    from .test_ghcp_ahp_prewarm_zero_turn import build, IDENTITY
    root = tmp_path / ("evidence" if damage == "namespace" else default.PROFILE)
    root.mkdir()
    selected = build()
    if damage == "failed_ci": selected["conclusion"] = "failure"
    if damage == "wrong_sha": selected["head_sha"] = "b" * 40
    if damage == "consumer_is_producer": selected["id"] = int(IDENTITY["github_run_id"])
    if damage == "old_report": (root / "handshake.json").write_text("do not overwrite choice one")
    probe.save_json(root / "green-ci.json", selected)
    monkeypatch.setattr(dispatch, "context", lambda **kwargs: copy.deepcopy(IDENTITY))
    if damage == "none": assert default.require_context(root) == IDENTITY
    else:
        with pytest.raises(probe.Refused): default.require_context(root)
    if damage == "old_report": assert (root / "handshake.json").read_text() == "do not overwrite choice one"


@pytest.mark.parametrize("damage", ["none", "changed_bundle", "changed_archive", "symlink"])
def test_original_archive_member_is_compared_before_node_or_authentication(tmp_path, monkeypatch, damage):
    # Counterfactual archive bytes only. No downloaded/native file is executed.
    data = b"export const inert_fixture = true;\n"
    prepared, state = tmp_path / "prepared", tmp_path / "state"
    server = prepared / "server"
    entry = server / default.RELATIVE
    entry.parent.mkdir(parents=True)
    entry.write_bytes(data)
    archive_path = prepared / "downloads/server.tgz"
    archive_path.parent.mkdir()
    with tarfile.open(archive_path, "w:gz") as archive:
        member = tarfile.TarInfo("vscode-server-linux-x64/" + default.RELATIVE)
        member.size = len(data)
        archive.addfile(member, io.BytesIO(data))
    manifest = copy.deepcopy(probe.load_manifest())
    manifest["artifacts"]["server"]["sha256"] = probe.digest(archive_path)
    monkeypatch.setattr(default, "UNPATCHED_BUNDLE_SHA256", default.sha(data))
    if damage == "changed_bundle": entry.write_bytes(data[:-2] + b"X\n")
    if damage == "changed_archive": archive_path.write_bytes(b"not the pinned archive")
    if damage == "symlink":
        entry.rename(entry.with_suffix(".original"))
        entry.symlink_to(entry.with_suffix(".original"))
    fork = {"files": {"node": {"path": str(server / "node"), "sha256": "a" * 64}}}
    if damage == "none":
        result = default.binding(prepared, state, manifest, fork)
        assert result["entry"]["sha256"] == default.sha(data)
        assert result["patches_applied"] == [] and result["patched_ghcp"] is result["execution_allowed"] is False
    else:
        with pytest.raises(probe.Refused): default.binding(prepared, state, manifest, fork)
