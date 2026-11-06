"""Offline data/adapter fixtures only; no vendor executable, login or model work."""

import copy
import io
import json
from pathlib import Path
import tarfile
from types import SimpleNamespace

import pytest

import ghcp_ahp_readiness_smoke as ready
import ghcp_ahp_patched_runtime as runtime
import ghcp_ahp_probe as probe
import ghcp_ahp_thread_policy as policy
import ghcp_ahp_wire_capture as wire
from ghcp_ahp_errors import Refused
from tests.test_ghcp_ahp_probe import synthetic_backend_signal, policy_transport
from tests.test_ghcp_ahp_patchset import bundle_fixture
from tests.test_ghcp_ahp_patched_runtime import BODY, fixture_tree, encode, sha

IDENTITY = {"github_run_id": "12345", "github_run_attempt": "1", "github_sha": "a" * 40}
ISOLATION = {"interfaces": ["lo"], "pid_one": True, "unprivileged": True, "no_new_privileges": True,
             "network_namespace": "net:[2]", "outside_network_namespace": "net:[1]",
             "pid_namespace": "pid:[2]", "outside_pid_namespace": "pid:[1]"}


@pytest.fixture(autouse=True)
def no_real_host_or_external_requests(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("readiness fixture crossed an actual process/provider boundary")
    monkeypatch.setattr(probe.subprocess, "Popen", forbidden)
    monkeypatch.setattr(probe.socket, "create_connection", forbidden)
    monkeypatch.setattr(probe, "download", forbidden)


def test_nas_is_refused_before_any_real_work(monkeypatch, tmp_path):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    with pytest.raises(Refused, match="execution_environment_refused"):
        ready.main(["run", "--prepared", str(tmp_path), "--evidence", str(tmp_path / "out"),
                    "--outside-netns", "net:[1]", "--outside-pidns", "pid:[1]"])
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("event,ref", [("workflow_dispatch", ready.BRANCH), ("push", "refs/heads/main"), ("", "")])
def test_readiness_is_only_the_authorized_branch_push(monkeypatch, event, ref):
    monkeypatch.setattr(ready.load, "ci_identity", lambda: IDENTITY)
    monkeypatch.setenv("GITHUB_EVENT_NAME", event)
    monkeypatch.setenv("GITHUB_REF", ref)
    with pytest.raises(Refused, match="readiness_branch_push_required"):
        ready.context()


def test_cli_flags_match_the_old_probe_not_the_one_second_import_parent(tmp_path):
    assert ready.host_command(tmp_path / "cli/code", tmp_path / "state", 43210) == [str(tmp_path / "cli/code"),
        "agent", "host", "--foreground", "--new-instance", "--without-connection-token", "--host", "127.0.0.1", "--port", "43210",
        "--server-data-dir", str(tmp_path / "state/server-data"), "--user-data-dir", str(tmp_path / "state/user-data"),
        "--disable-telemetry", "--log", "debug"]
    assert ready.WALL_SECONDS == probe.MAX_RUNTIME_SECONDS == 180
    with pytest.raises(Refused, match="patched_runtime_activation_pending_owner"):
        runtime.require_activation()


@pytest.mark.parametrize("damage", [None, "archive", "installed", "symlink", "not_executable", "special_member"])
def test_cli_bytes_are_bound_to_the_original_archive_before_launch(tmp_path, damage):
    (tmp_path / "downloads").mkdir()
    (tmp_path / "cli").mkdir()
    archive = tmp_path / "downloads/cli.tgz"
    with tarfile.open(archive, "w:gz") as output:
        info = tarfile.TarInfo("code")
        body = b"inert fake executable, never run"
        info.size = len(body)
        if damage == "special_member": info.type, info.size = tarfile.DIRTYPE, 0
        output.addfile(info, io.BytesIO(body) if info.isfile() else None)
    manifest = {"artifacts": {"cli": {"sha256": sha(archive.read_bytes())}}}
    executable = tmp_path / "cli/code"
    executable.write_bytes(body)
    executable.chmod(0o700)
    if damage == "archive": archive.write_bytes(archive.read_bytes() + b"changed")
    elif damage == "installed": executable.write_bytes(b"changed")
    elif damage == "symlink":
        executable.rename(tmp_path / "other")
        executable.symlink_to(tmp_path / "other")
    elif damage == "not_executable": executable.chmod(0o600)
    if damage:
        with pytest.raises(Refused): ready.cli_identity(tmp_path, manifest)
    else:
        assert ready.cli_identity(tmp_path, manifest) == sha(body)


@pytest.mark.parametrize("state", ["ready", "banner_only", "missing_socket", "missing_log", "wrong_socket", "conflict", "truncated", "timeout"])
def test_real_readiness_checker_requires_signal_and_socket_before_the_load_boundary(tmp_path, monkeypatch, state):
    bound = synthetic_backend_signal(tmp_path, state)
    calls = []
    transport = SimpleNamespace(close=lambda: calls.append("close"))
    process = SimpleNamespace(process=SimpleNamespace(poll=lambda: None), check=lambda: None)
    monkeypatch.setattr(probe, "WebSocket", lambda *args: transport)
    monkeypatch.setattr(runtime, "verify_live_ready", lambda *args: calls.append("load") or {"loaded_bundle_sha256": ready.load.BASELINE_SHA256})
    watchdog = SimpleNamespace(enforce=lambda: calls.append("guard"))
    try:
        if state == "ready":
            result = ready.connect_ready(process, tmp_path, 43210, ready.time.monotonic() + 5, watchdog)
            assert result[0] is transport and result[1]["ready"] is True
            assert calls == ["guard", "load", "guard"]
        else:
            with pytest.raises(Refused, match="readiness_backend_refused"):
                ready.connect_ready(process, tmp_path, 43210, ready.time.monotonic() + 5, watchdog)
            assert "load" not in calls and calls[-1] == "close"
    finally:
        if bound is not None: bound.close()


def auth_results():
    return {"initialize": {"result": {"protocolVersion": "1.1.0"}},
            "createSession": {"error": {"message": ready.AUTH_MESSAGE, "code": -32007},
                              "transport": "vscode-child-ipc", "method": "createSessionWithExtensions"}}


@pytest.mark.parametrize("damage", [None, "no_code", "other_message", "bad_code", "bool_code", "missing_creation", "bad_initialize", "success"])
def test_only_the_exact_pinned_auth_error_is_an_allowed_stop(damage):
    results = auth_results()
    if damage == "no_code": del results["createSession"]["error"]["code"]
    elif damage == "other_message": results["createSession"]["error"]["message"] = "timeout"
    elif damage == "bad_code": results["createSession"]["error"]["code"] = -1
    elif damage == "bool_code": results["createSession"]["error"]["code"] = True
    elif damage == "missing_creation": del results["createSession"]
    elif damage == "bad_initialize": results["initialize"] = {"error": {"code": -32007, "message": ready.AUTH_MESSAGE}}
    elif damage == "success": results["createSession"] = {"result": {}}
    if damage in (None, "no_code", "success"):
        outcome = ready.session_outcome(results)
        assert outcome["session_created"] is (damage == "success")
        if damage != "success":
            assert outcome["kind"] == "stopped_at_authentication_boundary"
            assert runtime.PIN in outcome["authentication_boundary"]["url"]
    else:
        with pytest.raises(Refused): ready.session_outcome(results)


@pytest.fixture
def receipt(bundle_fixture, tmp_path, monkeypatch):
    """Fabricated consumer DATA; not an actual host/proof observation or login."""
    import ghcp_ahp_bundle_manifest as bundle
    manifest = bundle.record_manifest(*bundle_fixture)
    tree = fixture_tree(tmp_path / "runtime-fixture")
    env = runtime.prepare_binding(tree["prepared"], tree["state"], tree["request"], tree["fork"], synthetic=False)
    contract = json.loads(env["GHCP_AHP_PATCHED_RUNTIME_CONTRACT"])
    parent, child = 400, 401
    rows = [{"kind": "patched_runtime_child", "child_pid": child, "parent_pid": parent,
             "runtime_contract_sha256": env["GHCP_AHP_PATCHED_RUNTIME_CONTRACT_SHA256"], "synthetic": False, "process": f"wire-{parent}.jsonl"},
            {"kind": "observer_installed", "entrypoint": runtime.ENTRYPOINT, "process": f"wire-{child}.jsonl",
             "model_free": True, "session_only": True, "synthetic": False},
            {"kind": "agent_fork_attempt", "mismatches": [], "expected": {"socket_path": "/fixture/tmp/agent"}},
            {"kind": "agent_fork_instrumented"}]
    proof = {"schema": "ghcp-patched-runtime-load-v2", "patched_ghcp": True, "upstream_commit": runtime.PIN,
             "patch_sha256": runtime.PATCH_SHA256, "build_receipt_sha256": contract["build_receipt_sha256"],
             "runtime_contract_sha256": env["GHCP_AHP_PATCHED_RUNTIME_CONTRACT_SHA256"], "loaded_relative_path": runtime.RUNTIME_RELATIVE,
             "loaded_source_sha256": sha(BODY), "disk_before_sha256": sha(BODY), "disk_after_sha256": sha(BODY),
             "node_sha256": contract["node_sha256"], "loader_sha256": contract["loader_sha256"], "challenge_sha256": sha(contract["challenge"].encode()),
             "synthetic": False, "phase": "node_load_hook_before_evaluation", "execution_allowed": False, "pid": child, "ppid": parent}
    (tree["state"] / f"wire/patched-runtime/load-{child}.json").write_bytes(encode(proof))
    evidence = tmp_path / "readiness-evidence"
    evidence.mkdir()
    provenance = runtime.collect(tree["state"], evidence, rows)
    capture = wire.analyze(rows, synthetic=False)
    capture.update(capture_status="captured", bootstrap={"session_policy": True, "authenticated_zero_turn": False, "metadata_reads": False})
    capture = runtime.stamp(capture, provenance)
    probe.save_json(evidence / "wire-capture.json", capture)
    results = auth_results()
    policy_pointer = policy.export(evidence, results)
    probe.save_json(evidence / "backend-startup.json", {"schema": "inert-readiness-test-fixture"})
    raw_manifest = encode(manifest) + b"\n"
    (evidence / "server-bundle-manifest.json").write_bytes(raw_manifest)
    monkeypatch.setattr(ready.load, "BASELINE_SHA256", sha(BODY))
    monkeypatch.setattr(ready.load, "BASELINE_BYTES", len(BODY))
    transfer = {"schema": "ghcp-load-smoke-transfer-v1", "identity": IDENTITY, "upstream_commit": runtime.PIN,
                "patch_sha256": runtime.PATCH_SHA256, "bundle_sha256": sha(BODY), "bundle_bytes": len(BODY),
                "server_archive_sha256": bundle.base_manifest()["artifacts"]["server"]["sha256"],
                "bundle_manifest_sha256": sha(raw_manifest), "build_receipt_sha256": manifest["build_receipt_sha256"],
                "payload_sha256": "f" * 64, "payload_bytes": 1, "synthetic": True, "model_free": True, "execution_allowed": False}
    probe.save_json(evidence / "transfer.json", transfer)
    assessment = policy.assess(capture, results)
    result = {"schema": "ghcp-patched-readiness-smoke-v1", "identity": IDENTITY, "isolation": copy.deepcopy(ISOLATION), "status": "success", "model_free": True,
              "synthetic": False, "authentication_supplied": False, "execution_allowed": False, "admission_allowed": False,
              "errors": [], "cleanup": "owned_process_group_stopped", "state_root": "/fixture", "session_create_requests": 1,
              "backend_readiness": {"ready": True, "reason": "bound_listener_signal_and_exact_socket", "socket_path": "tmp/agent"},
              "host_process": {"exit_code": -15, "output_limit_exceeded": False}, "rpc_results": results, "rpc_sent": [],
              "runtime_provenance": provenance, "live_runtime_provenance": provenance, "outcome": ready.session_outcome(results),
              "patch_sha256": runtime.PATCH_SHA256, "expected_bundle_sha256": sha(BODY), "bundle_manifest_sha256": sha(raw_manifest),
              "wire_capture": {"sha256": probe.digest(evidence / "wire-capture.json")}, "thread_policy": policy_pointer,
              "backend_startup": {"sha256": probe.digest(evidence / "backend-startup.json")},
              "sessions_created": 0, "native_thread_responses": 0, "turns_sent": 0, "capi_requests": 0, "model_calls": 0,
              "observed": assessment["observed"], "verdicts": assessment["verdicts"]}
    probe.save_json(evidence / "readiness-smoke.json", result)
    return evidence, result, capture, assessment, provenance


def test_consumer_checks_full_hash_chain_not_just_the_ready_boolean(receipt):
    evidence, result, *_ = receipt
    assert ready.verify_evidence(evidence, IDENTITY) == result
    assert set(result["observed"].values()) == {"not_reported"}


@pytest.mark.parametrize("damage", ["not_ready", "fake_banner", "wrong_socket", "fork_count", "observer_missing", "guard_mismatch", "killed",
    "auth_supplied", "admission", "execution", "synthetic", "model_call", "turn", "capi", "two_sessions", "bool_count", "missing_live_proof",
    "wrong_loaded_hash", "unauthorized_auth", "native_before_auth", "safety", "metadata", "capture_error", "policy_mismatch",
    "same_network", "same_pid", "root", "privileges"])
def test_negative_readiness_outcomes_never_become_success(receipt, damage):
    _, result, capture, assessment, provenance = receipt
    if damage == "not_ready": result["backend_readiness"]["ready"] = False
    elif damage == "fake_banner": result["backend_readiness"]["reason"] = "Server ready"
    elif damage == "wrong_socket": result["backend_readiness"]["socket_path"] = "tmp/other"
    elif damage == "fork_count": capture["records"].append(copy.deepcopy(capture["records"][2]))
    elif damage == "observer_missing": capture["records"] = [row for row in capture["records"] if row["kind"] != "observer_installed"]
    elif damage == "guard_mismatch": capture["records"][2]["mismatches"] = ["argv_exact"]
    elif damage == "killed": result["host_process"]["exit_code"] = -9
    elif damage == "auth_supplied": result["authentication_supplied"] = True
    elif damage == "admission": result["admission_allowed"] = True
    elif damage == "execution": result["execution_allowed"] = True
    elif damage == "synthetic": result["synthetic"] = True
    elif damage == "model_call": result["model_calls"] = 1
    elif damage == "turn": assessment["model_turn_start_requests"] = 1
    elif damage == "capi": capture["capi_requests"] = [{}]
    elif damage == "two_sessions": result["session_create_requests"] = 2
    elif damage == "bool_count": result["session_create_requests"] = True
    elif damage == "missing_live_proof": del result["live_runtime_provenance"]
    elif damage == "wrong_loaded_hash": provenance["loaded_bundle_sha256"] = "0" * 64
    elif damage == "unauthorized_auth": result["rpc_sent"] = [{"method": "authenticate"}]
    elif damage == "native_before_auth": capture["native_requests"] = [{}]
    elif damage == "safety": assessment["safety_violation"] = True
    elif damage == "metadata": capture["metadata_http"] = [{}]
    elif damage == "capture_error": capture["capture_errors"] = ["blocked"]
    elif damage == "policy_mismatch": assessment["verdicts"]["model"] = "mismatch"
    elif damage == "same_network": result["isolation"]["network_namespace"] = "net:[1]"
    elif damage == "same_pid": result["isolation"]["pid_namespace"] = "pid:[1]"
    elif damage == "root": result["isolation"]["unprivileged"] = False
    elif damage == "privileges": result["isolation"]["no_new_privileges"] = False
    with pytest.raises(Refused): ready.validate_observation(result, capture, assessment, provenance)


@pytest.mark.parametrize("damage", ["loaded_bytes", "load_pid", "patch_set", "manifest", "unmeasured", "result_hash", "policy_echo", "wrong_run"])
def test_receipt_tampering_and_request_echoes_cannot_substitute_for_applied_evidence(receipt, damage):
    evidence, result, *_ = receipt
    name = "readiness-smoke.json"
    value = result
    if damage in ("loaded_bytes", "load_pid", "patch_set"):
        name = "patched-load-evidence.json"
        value = json.loads((evidence / name).read_text())
        value[{"loaded_bytes": "loaded_source_sha256", "load_pid": "pid", "patch_set": "patch_sha256"}[damage]] = 123 if damage == "load_pid" else "0" * 64
    elif damage == "manifest":
        name = "server-bundle-manifest.json"
        value = json.loads((evidence / name).read_text()); value["entrypoint"]["sha256"] = "0" * 64
    elif damage == "unmeasured":
        (evidence / "patched-load-evidence.json").rename(evidence / "removed.json")
    elif damage == "result_hash": value["wire_capture"]["sha256"] = "0" * 64
    elif damage == "policy_echo": value["observed"]["model"] = "gpt-5.6-sol"
    elif damage == "wrong_run": value["identity"]["github_run_id"] = "99999"
    (evidence / name).write_bytes(encode(value))
    with pytest.raises(Refused): ready.verify_evidence(evidence, IDENTITY)


@pytest.mark.parametrize("case", ["auth_boundary", "bad_ready", "bad_load", "bad_readback", "other_error", "observer_violation"])
def test_runner_adapter_orders_ready_load_readback_and_one_creation_with_zero_turns(receipt, tmp_path, monkeypatch, case):
    seed, seed_result, capture, _, provenance = receipt
    output = tmp_path / "setup"
    (output / "inputs").mkdir(parents=True)
    (output / "inputs/server-bundle-manifest.json").write_bytes((seed / "server-bundle-manifest.json").read_bytes())
    transfer = json.loads((seed / "transfer.json").read_text())
    manifest = json.loads((seed / "server-bundle-manifest.json").read_text())
    request = {"path": seed / "patched-build-receipt.json", "sha256": transfer["build_receipt_sha256"]}
    calls, sockets = {"commands": [], "ipc": [], "stops": 0}, []
    monkeypatch.setattr(ready, "verify_prepared", lambda *args: (output, request, manifest, transfer))
    monkeypatch.setattr(probe, "require_isolation", lambda *args: copy.deepcopy(ISOLATION))

    def install(root, state, environment, **options):
        assert options == {"model_free": True, "session_policy": True, "patched_request": request}
        assert environment["VSCODE_AGENT_HOST_CODEX_APP_SERVER_ARGS"] == json.dumps(policy.NATIVE_ARGS)
        calls["state"] = state
        (state / "wire").mkdir()
        return environment

    monkeypatch.setattr(wire, "install", install)

    def stop():
        calls["stops"] += 1

    def process(command, environment, cwd=None):
        calls["commands"].append(command)
        if command[-1] in {"--version", "--help"}:
            pin = probe.load_manifest()
            text = (pin["vscode_version"] + " " + runtime.PIN if command[-1] == "--version" else
                    "--foreground --new-instance --without-connection-token --log")
            return SimpleNamespace(finish=lambda: {"exit_code": 0, "stdout": text})
        state = calls["state"]
        bound = synthetic_backend_signal(state, "banner_only" if case == "bad_ready" else "ready")
        if bound is not None: sockets.append(bound)
        if case == "observer_violation":
            (state / "wire/wire-400.jsonl").write_text('{"kind":"blocked","sequence":1,"reason":"session_policy_http_refused"}\n')
        return SimpleNamespace(process=SimpleNamespace(pid=999999999, poll=lambda: None), check=lambda: None, stop=stop,
            record=lambda: {"exit_code": -15 if calls["stops"] else None, "output_limit_exceeded": False, "stdout": "", "stderr": ""})

    monkeypatch.setattr(probe, "CapturedProcess", process)
    transport = policy_transport()
    transport.close = lambda: None
    monkeypatch.setattr(probe, "WebSocket", lambda *args: transport)

    def measured(state):
        calls["measured"] = True
        if case == "bad_load": raise Refused("patched_runtime_loaded_source_mismatch")
        return provenance

    monkeypatch.setattr(runtime, "verify_live_ready", measured)

    def exchange(client, request):
        assert calls.get("measured") is True  # No settings/session IPC before the load proof.
        calls["ipc"].append(request["op"])
        if request["op"] == "configure":
            client.fixture_settings = copy.deepcopy(request["params"])
            result = {"configured": True}
        elif request["op"] == "readback":
            result = {"settings": copy.deepcopy(client.fixture_settings), "resolved_policy": policy.POLICY,
                      "derived_permissions": "vscode-workspace" if case == "bad_readback" else "vscode-workspace-read-only",
                      "evidence": ready.management.EVIDENCE, "admission_allowed": False}
        else:
            result = {"error": {"message": "unrelated error" if case == "other_error" else ready.AUTH_MESSAGE, "code": -32007}}
        return {"id": request["id"], "ok": True, "result": result}

    monkeypatch.setattr(ready.management.ManagementBridge, "_exchange", exchange)
    monkeypatch.setattr(ready.backend, "snapshot", lambda *args: {"synthetic_test_fixture": True})

    def export(state, evidence, *, patched_request):
        assert patched_request == request
        value = copy.deepcopy(capture)
        value["records"][2]["expected"]["socket_path"] = str(state / "tmp/agent")
        probe.save_json(evidence / "wire-capture.json", value)
        for name in runtime.ARTIFACTS:
            (evidence / name).write_bytes((seed / name).read_bytes())
        return {"path": "wire-capture.json", "sha256": probe.digest(evidence / "wire-capture.json"),
                "capture_status": "captured", "synthetic": False, "admission_allowed": False, "patched_runtime": provenance}

    monkeypatch.setattr(wire, "export", export)
    evidence = tmp_path / "observed"
    try:
        if case == "auth_boundary":
            result = ready.run(output, evidence, IDENTITY, "net:[1]", "pid:[1]")
            assert result["status"] == "success" and result["outcome"]["kind"] == "stopped_at_authentication_boundary"
            assert result["sessions_created"] == result["native_thread_responses"] == result["turns_sent"] == result["capi_requests"] == result["model_calls"] == 0
            assert result["execution_allowed"] is False and result["admission_allowed"] is False
            assert calls["ipc"] == ["configure", "readback", "create"]
            assert [row["method"] for row in result["rpc_sent"]] == ["initialize", "resolveSessionConfig"]
            assert ready.verify_evidence(evidence, IDENTITY) == result
        else:
            with pytest.raises(Refused, match="readiness_smoke_refused"):
                ready.run(output, evidence, IDENTITY, "net:[1]", "pid:[1]")
            result = json.loads((evidence / "readiness-smoke.json").read_text())
            assert result["status"] == "failure" and result["errors"]
            if case in {"bad_ready", "bad_load", "observer_violation"}: assert calls["ipc"] == []
            if case == "bad_readback": assert calls["ipc"] == ["configure", "readback"]
            assert all(row["method"] not in {"authenticate", "turn/start", "dispatchAction"} for row in result.get("rpc_sent", []))
        assert calls["stops"] >= 1 and len(calls["commands"]) == 3
        assert not calls["state"].exists()
    finally:
        for bound in sockets: bound.close()
