"""Push-only, no-auth readiness/session observation. Never authorizes a paid gate.

Use the original CLI -> server-main -> exact bootstrap-fork contract, not the
synthetic import parent's clock. Existing activation/admission guards stay intact.
"""

from __future__ import annotations

import argparse
import errno
import json
import os
from pathlib import Path
import re
import socket
import tarfile
import tempfile
import time
import uuid

import ghcp_ahp_backend_diagnostics as backend
import ghcp_ahp_load_smoke as load
import ghcp_ahp_management as management
import ghcp_ahp_patched_runtime as runtime
import ghcp_ahp_probe as probe
import ghcp_ahp_thread_policy as policy
import ghcp_ahp_wire_capture as wire
import ghcp_ahp_zero_turn as zero
from ghcp_ahp_errors import Refused

BRANCH = "refs/heads/leader/ghcp-patched-runtime-receipt-20261106"
AUTH_MESSAGE = "Authentication is required to use Codex"
AUTH_SOURCE = "src/vs/platform/agentHost/node/codex/codexAgent.ts:1842-1849"
WALL_SECONDS = 180
EXTRA_DOWNLOADS = ("cli", "codex_sdk", "source")


def context():
    identity = load.ci_identity()
    if os.environ.get("GITHUB_EVENT_NAME") != "push" or os.environ.get("GITHUB_REF") != BRANCH:
        raise Refused("readiness_branch_push_required")
    return identity


def cli_identity(prepared, manifest):
    archive_path, executable = prepared / "downloads/cli.tgz", prepared / "cli/code"
    if probe.digest(archive_path) != manifest["artifacts"]["cli"]["sha256"]:
        raise Refused("readiness_cli_archive_refused")
    with tarfile.open(archive_path, "r:gz") as archive:
        member = archive.getmember("code")
        if not member.isfile() or not 0 < member.size <= 256 * 1024 * 1024:
            raise Refused("readiness_cli_member_refused")
        with archive.extractfile(member) as stream:
            original = stream.read(member.size + 1)
    current = runtime._read(executable, 256 * 1024 * 1024)
    if len(original) != member.size or current != original or not os.access(executable, os.X_OK):
        raise Refused("readiness_cli_identity_refused")
    return runtime._sha(current)


def prepare(transfer, output, identity):
    # Only file preparation/public byte-pinned downloads here; no process launch.
    load.prepare_payload(transfer, output, identity)
    root = output / "positive"
    manifest = probe.load_manifest()
    downloads = {}
    for name in EXTRA_DOWNLOADS:
        target = root / "downloads" / (name + ".tgz")
        downloads[name] = probe.download(manifest["artifacts"][name], target)
    for name, directory in (("cli", root / "cli"), ("codex_sdk", root / "codex-sdk")):
        directory.mkdir(exist_ok=False)
        probe.extract_archive(root / "downloads" / (name + ".tgz"), directory)
    probe.save_json(root / "cli-data/servers/lru.json", ["Stable-" + runtime.PIN])
    value = {"schema": "ghcp-readiness-prepared-v1", "identity": identity,
             "downloads": downloads, "cli_sha256": cli_identity(root, manifest),
             "execution_allowed": False, "authentication_supplied": False}
    probe.save_json(output / "readiness-prepared.json", value)
    return value


def verify_prepared(output, identity):
    output = runtime._safe_path(output)
    prepared = runtime._json(runtime._read(output / "prepared.json"))
    transfer = load.validate_transfer(prepared["transfer"], identity)
    manifest = load.checked_manifest(output / "inputs/server-bundle-manifest.json")
    if runtime._sha(runtime._read(output / "inputs/server-bundle-manifest.json")) != transfer["bundle_manifest_sha256"]:
        raise Refused("readiness_bundle_manifest_refused")
    root = output / "positive"
    pin = probe.load_manifest()
    setup = runtime._json(runtime._read(output / "readiness-prepared.json"))
    if (setup.get("schema") != "ghcp-readiness-prepared-v1" or setup.get("identity") != identity
            or setup.get("execution_allowed") is not False or setup.get("authentication_supplied") is not False
            or set(setup.get("downloads", {})) != set(EXTRA_DOWNLOADS)
            or setup.get("cli_sha256") != cli_identity(root, pin)):
        raise Refused("readiness_prepared_refused")
    for name in EXTRA_DOWNLOADS:
        if (setup["downloads"][name].get("sha256") != pin["artifacts"][name]["sha256"]
                or probe.digest(root / "downloads" / (name + ".tgz")) != pin["artifacts"][name]["sha256"]):
            raise Refused("readiness_public_input_drift")
    # The existing wire installer verifies SDK binary, source, Node, bootstrap and
    # server parent against their original archives, and binds the patched bytes.
    request = {"path": output / "build-receipt.json", "sha256": transfer["build_receipt_sha256"]}
    return root, request, manifest, transfer


def host_command(cli, state, port):
    # Identical flags to ghcp_ahp_probe.py's proven model-free CLI entrypoint.
    return [str(cli), "agent", "host", "--foreground", "--new-instance", "--without-connection-token",
            "--host", "127.0.0.1", "--port", str(port), "--server-data-dir", str(state / "server-data"),
            "--user-data-dir", str(state / "user-data"), "--disable-telemetry", "--log", "debug"]


def connect_ready(process, state, port, deadline, watchdog):
    transport = None
    while time.monotonic() < deadline:
        watchdog.enforce()
        process.check()
        if process.process.poll() is not None:
            raise Refused("readiness_host_exited_before_handshake")
        try:
            transport = probe.WebSocket(port, deadline)
            break
        except OSError as error:
            if error.errno not in (errno.ECONNREFUSED, errno.ECONNRESET):
                raise
            time.sleep(0.1)
    if transport is None:
        raise Refused("readiness_startup_deadline")
    try:
        ready = backend.readiness(state)
        if ready.get("ready") is not True:
            raise Refused("readiness_backend_refused")
        provenance = runtime.verify_live_ready(state)
        if provenance["loaded_bundle_sha256"] != load.BASELINE_SHA256:
            raise Refused("readiness_loaded_bundle_refused")
        watchdog.enforce()
    except Exception:
        transport.close()
        raise
    return transport, ready, provenance


def session_outcome(results):
    initialized = results.get("initialize", {}).get("result", {})
    if initialized.get("protocolVersion") not in {"1.0.0", "1.1.0"}:
        raise Refused("readiness_protocol_initialization_refused")
    created = results.get("createSession", {})
    if "result" in created and "error" not in created:
        return {"kind": "session_created_zero_turns", "session_created": True, "authentication_boundary": None}
    error = created.get("error")
    # Only the exact pinned no-token refusal is an observed terminal boundary.
    # Other errors/timeouts never become a passing smoke or synthetic auth result.
    if (type(error) is not dict or error.get("message") != AUTH_MESSAGE
            or "code" in error and (type(error["code"]) is not int or error["code"] != -32007)):
        raise Refused("readiness_session_error_not_auth_boundary")
    return {"kind": "stopped_at_authentication_boundary", "session_created": False,
            "authentication_boundary": {"source": AUTH_SOURCE,
                "url": f"https://github.com/microsoft/vscode/blob/{runtime.PIN}/" + AUTH_SOURCE.replace(":1842-1849", "#L1842-L1849"),
                "error": probe.redact(error)}}


def validate_observation(result, capture, assessment, provenance):
    runtime.validate_provenance(provenance)
    isolation = result.get("isolation", {})
    if (isolation.get("interfaces") != ["lo"]
            or any(isolation.get(key) is not True for key in ("pid_one", "unprivileged", "no_new_privileges"))
            or any(type(isolation.get(key)) is not str or re.fullmatch(pattern, isolation[key]) is None
                   for key, pattern in (("network_namespace", r"net:\[[0-9]+\]"), ("outside_network_namespace", r"net:\[[0-9]+\]"),
                                        ("pid_namespace", r"pid:\[[0-9]+\]"), ("outside_pid_namespace", r"pid:\[[0-9]+\]")))
            or isolation["network_namespace"] == isolation["outside_network_namespace"]
            or isolation["pid_namespace"] == isolation["outside_pid_namespace"]):
        raise Refused("readiness_isolation_evidence_refused")
    if (result.get("schema") != "ghcp-patched-readiness-smoke-v1" or result.get("model_free") is not True
            or result.get("synthetic") is not False or result.get("authentication_supplied") is not False
            or result.get("execution_allowed") is not False or result.get("admission_allowed") is not False
            or result.get("errors") != [] or result.get("cleanup") != "owned_process_group_stopped"
            or result.get("backend_readiness", {}).get("ready") is not True
            or result["backend_readiness"].get("reason") != "bound_listener_signal_and_exact_socket"
            or type(result.get("host_process", {}).get("exit_code")) is not int or result["host_process"]["exit_code"] not in (0, -15)
            or result.get("host_process", {}).get("output_limit_exceeded") is not False
            or provenance.get("loaded_bundle_sha256") != load.BASELINE_SHA256
            or provenance.get("runtime_evidence_synthetic") is not False
            or result.get("live_runtime_provenance") != provenance
            or result.get("runtime_provenance") != provenance):
        raise Refused("readiness_observation_refused")
    records = capture.get("records", [])
    forks = [row for row in records if row.get("kind") == "agent_fork_attempt"]
    installed = [row for row in records if row.get("kind") == "observer_installed" and row.get("entrypoint") == runtime.ENTRYPOINT]
    if (len(forks) != 1 or forks[0].get("mismatches") != []
            or len(installed) != 1 or installed[0].get("model_free") is not True or installed[0].get("session_only") is not True
            or forks[0].get("expected", {}).get("socket_path") != result.get("state_root", "") + "/" + result["backend_readiness"]["socket_path"]
            or len([row for row in records if row.get("kind") == "agent_fork_instrumented"]) != 1):
        raise Refused("readiness_exact_fork_socket_refused")
    if (capture.get("synthetic") is not False or capture.get("capture_status") != "captured"
            or capture.get("bootstrap", {}).get("session_policy") is not True
            or capture.get("bootstrap", {}).get("authenticated_zero_turn") is not False
            or capture.get("bootstrap", {}).get("metadata_reads") is not False
            or capture.get("capture_errors") or capture.get("capi_requests") or capture.get("capi_response_reports") or capture.get("metadata_http")
            or assessment.get("safety_violation") is not False or assessment.get("admission_allowed") is not False
            or any(type(assessment.get(key)) is not int or assessment[key] != 0 for key in ("model_turn_start_requests", "model_turn_events", "capi_requests"))
            or any(row.get("method") == "authenticate" for row in result.get("rpc_sent", []))
            or any(value == "mismatch" for value in assessment.get("verdicts", {}).values())):
        raise Refused("readiness_zero_turn_or_policy_refused")
    outcome = session_outcome(result["rpc_results"])
    if (result.get("outcome") != outcome or type(result.get("session_create_requests")) is not int
            or result["session_create_requests"] != 1
            or any(type(result.get(key)) is not int or result[key] != 0 for key in ("turns_sent", "capi_requests", "model_calls"))
            or type(result.get("sessions_created")) is not int or result["sessions_created"] != int(outcome["session_created"])
            or type(result.get("native_thread_responses")) is not int or result["native_thread_responses"] != assessment["native_thread_responses"]):
        raise Refused("readiness_session_outcome_refused")
    if not outcome["session_created"] and (assessment["native_thread_responses"] != 0 or capture.get("native_requests")):
        raise Refused("readiness_native_before_auth_refused")
    return result


def run(output, evidence, identity, outside_netns, outside_pidns):
    isolation = probe.require_isolation(outside_netns, outside_pidns)
    isolation["outside_pid_namespace"] = outside_pidns
    root, request, manifest, transfer = verify_prepared(output, identity)
    evidence = runtime._safe_path(evidence)
    evidence.mkdir(exist_ok=False)
    result = {"schema": "ghcp-patched-readiness-smoke-v1", "identity": identity, "isolation": isolation,
              "model_free": True, "synthetic": False, "authentication_supplied": False,
              "execution_allowed": False, "admission_allowed": False, "status": "failure", "errors": [],
              "patch_sha256": runtime.PATCH_SHA256, "expected_bundle_sha256": load.BASELINE_SHA256,
              "bundle_manifest_sha256": transfer["bundle_manifest_sha256"], "requested_policy": policy.POLICY,
              "requested_model": probe.DESIRED_MODEL, "requested_native_launch_args": policy.NATIVE_ARGS}
    process = transport = watchdog = rpc = None
    with tempfile.TemporaryDirectory(prefix="ahp-") as temporary:
        state = Path(temporary)
        result["state_root"] = str(state)
        deadline = time.monotonic() + WALL_SECONDS
        environment = probe.child_environment(root, state)
        workspace = state / "workspace"
        workspace.mkdir()
        try:
            cli = root / "cli/code"
            version = probe.CapturedProcess([str(cli), "--version"], environment, cwd=state).finish()
            help_result = probe.CapturedProcess([str(cli), "agent", "host", "--help"], environment, cwd=state).finish()
            pin = probe.load_manifest()
            if (version["exit_code"] != 0 or pin["vscode_version"] not in version["stdout"] or runtime.PIN not in version["stdout"]
                    or help_result["exit_code"] != 0 or any(flag not in help_result["stdout"] for flag in
                        ("--foreground", "--new-instance", "--without-connection-token", "--log"))):
                raise Refused("readiness_cli_contract_refused")
            environment["VSCODE_AGENT_HOST_CODEX_APP_SERVER_ARGS"] = json.dumps(policy.NATIVE_ARGS)
            environment = wire.install(root, state, environment, model_free=True, session_policy=True, patched_request=request)
            with socket.socket() as reservation:
                reservation.bind(("127.0.0.1", 0))
                port = reservation.getsockname()[1]
            process = probe.CapturedProcess(host_command(cli, state, port), environment, cwd=workspace)
            watchdog = zero.Watchdog(state, process.stop)
            watchdog.start()
            transport, ready, provenance = connect_ready(process, state, port, deadline, watchdog)
            result.update(backend_readiness=ready, live_runtime_provenance=provenance)
            rpc = probe.Rpc(transport, "ahp-session:/" + str(uuid.uuid4()), workspace.as_uri(),
                            session_policy=True, boundary_check=watchdog.enforce)
            rpc.management = management.ManagementBridge(state, deadline, owned_pid=process.process.pid, boundary_check=watchdog.enforce)
            results = policy.exercise(rpc, lambda: policy.await_native_thread(state, deadline))
            result.update(rpc_results=results, outcome=session_outcome(results))
            watchdog.enforce()
        except Exception as error:
            result["errors"].append(str(error) if isinstance(error, Refused) else type(error).__name__)
        finally:
            def retain(action):
                try:
                    return action()
                except Exception as error:
                    result["errors"].append(str(error) if isinstance(error, Refused) else type(error).__name__)
                    return None

            if watchdog is not None:
                retain(watchdog.enforce)
                retain(watchdog.close)
            if "backend_readiness" not in result:
                result["backend_readiness"] = retain(lambda: backend.readiness(state))
            before = retain(lambda: backend.snapshot(state, process))
            if transport is not None:
                retain(transport.close)
            if process is not None:
                previous = len(result["errors"])
                retain(process.stop)
                result["cleanup"] = "owned_process_group_stopped" if len(result["errors"]) == previous else "stop_unconfirmed"
                result["host_process"] = retain(process.record)
            after = retain(lambda: backend.snapshot(state, process))
            result["backend_startup"] = retain(lambda: backend.export(evidence, before=before, after=after,
                primary_error_code=result["errors"][0] if result["errors"] else None, environment=environment, vscode_commit=runtime.PIN,
                session_create_requests=probe.session_create_requests(rpc)))
            if rpc is not None:
                result.update(rpc_results=rpc.policy_results, rpc_sent=rpc.sent, rpc_received=rpc.received,
                              management_sent=rpc.management.sent, management_received=rpc.management.received,
                              session_create_requests=probe.session_create_requests(rpc))
            result["wire_capture"] = retain(lambda: wire.export(state, evidence, patched_request=request))
            result["thread_policy"] = retain(lambda: policy.export(evidence, result.get("rpc_results", {})))
    if result.get("wire_capture"):
        result["runtime_provenance"] = result["wire_capture"].get("patched_runtime")
    if result.get("thread_policy"):
        observed = runtime._json(runtime._read(evidence / "thread-policy.json", 4 * 1024 * 1024))
        result.update(sessions_created=int(observed["session_created"]), native_thread_responses=observed["native_thread_responses"],
                      turns_sent=observed["model_turn_start_requests"], capi_requests=observed["capi_requests"], model_calls=0,
                      observed=observed["observed"], verdicts=observed["verdicts"])
    probe.save_json(evidence / "readiness-smoke.json", result)
    runtime._write(evidence / "server-bundle-manifest.json", runtime._read(output / "inputs/server-bundle-manifest.json"))
    probe.save_json(evidence / "transfer.json", transfer)
    if result["errors"]:
        raise Refused("readiness_smoke_refused")
    # Validate the actual exported evidence before marking this observation complete.
    verify_evidence(evidence, identity, completed=False)
    result["status"] = "success"
    probe.save_json(evidence / "readiness-smoke.completed.json", result)
    os.replace(evidence / "readiness-smoke.completed.json", evidence / "readiness-smoke.json")
    return verify_evidence(evidence, identity)


def verify_evidence(evidence, identity, *, completed=True):
    result = runtime._json(runtime._read(evidence / "readiness-smoke.json", 4 * 1024 * 1024))
    manifest = load.checked_manifest(evidence / "server-bundle-manifest.json")
    transfer = load.validate_transfer(runtime._json(runtime._read(evidence / "transfer.json")), identity)
    if (result.get("identity") != identity or result.get("status") != ("success" if completed else "failure")
            or result.get("patch_sha256") != runtime.PATCH_SHA256 or result.get("expected_bundle_sha256") != load.BASELINE_SHA256
            or result.get("bundle_manifest_sha256") != transfer["bundle_manifest_sha256"]
            or runtime._sha(runtime._read(evidence / "server-bundle-manifest.json")) != transfer["bundle_manifest_sha256"]):
        raise Refused("readiness_receipt_identity_refused")
    capture = runtime._json(runtime._read(evidence / "wire-capture.json", wire.MAX_BYTES))
    assessment = policy.assess(capture, result["rpc_results"])
    stored = runtime._json(runtime._read(evidence / "thread-policy.json", 4 * 1024 * 1024))
    provenance = runtime.validate_provenance(capture)
    if (stored != runtime.stamp(assessment, provenance) or result.get("observed") != assessment["observed"]
            or result.get("verdicts") != assessment["verdicts"]):
        raise Refused("readiness_policy_evidence_refused")
    raw_build, raw_contract, raw_proof = [runtime._read(evidence / name) for name in runtime.ARTIFACTS]
    build = runtime.validate_build_receipt(runtime._json(raw_build))
    contract = runtime._json(raw_contract)
    runtime._validate_contract(contract, build)
    runtime._validate_load(contract, runtime._sha(raw_contract), runtime._json(raw_proof), capture["records"])
    if (build != manifest["build_receipt"] or provenance["build_receipt_sha256"] != runtime._sha(raw_build)
            or provenance["runtime_contract_sha256"] != runtime._sha(raw_contract)
            or provenance["load_evidence_sha256"] != runtime._sha(raw_proof)
            or contract["loader_sha256"] != probe.digest(runtime.LOADER)):
        raise Refused("readiness_runtime_chain_refused")
    for key, file in (("wire_capture", "wire-capture.json"), ("thread_policy", "thread-policy.json"), ("backend_startup", "backend-startup.json")):
        if result.get(key, {}).get("sha256") != probe.digest(evidence / file):
            raise Refused("readiness_evidence_hash_refused")
    return validate_observation(result, capture, assessment, provenance)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    setup = modes.add_parser("prepare")
    setup.add_argument("--transfer", type=Path, required=True)
    setup.add_argument("--output", type=Path, required=True)
    execute = modes.add_parser("run")
    execute.add_argument("--prepared", type=Path, required=True)
    execute.add_argument("--evidence", type=Path, required=True)
    execute.add_argument("--outside-netns", required=True)
    execute.add_argument("--outside-pidns", required=True)
    args = parser.parse_args(argv)
    identity = context()  # Before downloads, preparation or real GHCP processes on NAS.
    value = (prepare(args.transfer, args.output, identity) if args.mode == "prepare" else
             run(args.prepared, args.evidence, identity, args.outside_netns, args.outside_pidns))
    print(json.dumps({"schema": value["schema"], "status": value.get("status", "prepared_without_execution"),
                      "execution_allowed": False, "outcome": value.get("outcome", {}).get("kind")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
