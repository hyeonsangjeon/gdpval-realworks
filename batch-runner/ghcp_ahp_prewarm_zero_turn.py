"""Bind the tested prewarm-order build to one authenticated, zero-turn dispatch.

This preparation scope does not unlock require_activation(), paid execution or
model admission. The existing two patches, native guards and loaded-byte proof
remain authoritative. No credential, HTTP client or vendor process lives here.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import ghcp_ahp_load_smoke as load
import ghcp_ahp_patched_runtime as runtime
import ghcp_ahp_probe as probe
import ghcp_ahp_thread_policy as policy
import ghcp_ahp_zero_turn as zero
from ghcp_ahp_errors import Refused

REPOSITORY = "hyeonsangjeon/gdpval-realworks"
BRANCH = "leader/ghcp-patched-runtime-receipt-20261106"
WORKFLOW = ".github/workflows/agentic-v2-ghcp-sol-gate.yml"
BUILD_WORKFLOW = ".github/workflows/ghcp-ahp-patched-runtime-tests.yml"
IDENTITY_KEYS = ("github_run_id", "github_run_attempt", "github_sha")
BUILD_KEYS = ("id", "run_attempt", "head_sha", "head_branch", "path", "event", "status", "conclusion")


def require(condition, reason):
    if not condition:
        raise Refused(reason)


def context(*, running=False):
    runner = probe.require_runner()  # Hosted runner only, before any file/credential access.
    require(os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
            and os.environ.get("GITHUB_REPOSITORY") == REPOSITORY
            and os.environ.get("GITHUB_REF") == "refs/heads/" + BRANCH
            and os.environ.get("GITHUB_WORKFLOW_REF") == REPOSITORY + "/" + WORKFLOW + "@refs/heads/" + BRANCH
            and os.environ.get("GITHUB_WORKFLOW_SHA") == runner["github_sha"],
            "prewarm_zero_turn_dispatch_identity_refused")
    if running:
        zero.require_context()
    return {key: runner[key] for key in IDENTITY_KEYS}


def validate_build(value, identity):
    require(type(value) is dict and set(value) == {*BUILD_KEYS, "repository", "head_repository"},
            "prewarm_build_record_refused")
    expected = {"head_sha": identity["github_sha"], "head_branch": BRANCH,
                "path": BUILD_WORKFLOW, "event": "push", "status": "completed", "conclusion": "success",
                "repository": REPOSITORY, "head_repository": REPOSITORY}
    require(all(value.get(key) == item for key, item in expected.items())
            and type(value.get("id")) is int and value["id"] > 0
            and type(value.get("run_attempt")) is int and value["run_attempt"] == 1,
            "prewarm_successful_same_head_build_required")
    require(str(value["id"]) != identity["github_run_id"], "prewarm_producer_is_consumer_refused")
    return {"github_run_id": str(value["id"]), "github_run_attempt": "1", "github_sha": value["head_sha"]}


def select_build(response, identity):
    # No branch-latest, previous SHA, failed run, rerun or first-of-many fallback.
    require(type(response) is dict and type(response.get("total_count")) is int
            and response["total_count"] == 1 and type(response.get("workflow_runs")) is list
            and len(response["workflow_runs"]) == 1, "prewarm_unique_build_required")
    row = response["workflow_runs"][0]
    require(type(row) is dict, "prewarm_build_record_refused")
    value = {key: row.get(key) for key in BUILD_KEYS}
    for key in ("repository", "head_repository"):
        value[key] = row.get(key, {}).get("full_name") if type(row.get(key)) is dict else None
    validate_build(value, identity)
    return value


def preparation_record(identity, build, transfer):
    return {"schema": "ghcp-prewarm-zero-turn-preparation-v1", "scope": "authenticated-zero-turn-only",
            "consumer": identity, "producer": build, "patched_ghcp": True,
            "upstream_commit": runtime.PIN, "patch_sha256": runtime.PATCH_SHA256,
            "bundle_sha256": load.BASELINE_SHA256, "bundle_bytes": load.BASELINE_BYTES,
            "bundle_manifest_sha256": transfer["bundle_manifest_sha256"],
            "build_receipt_sha256": transfer["build_receipt_sha256"],
            "requested_policy": policy.POLICY, "requested_model": probe.DESIRED_MODEL,
            "requested_native_launch_args": policy.NATIVE_ARGS,
            "runtime_load_status": "staged_not_loaded", "applied_policy": "not_reported",
            "execution_allowed": False, "admission_allowed": False,
            "limits": {"sessions": 1, "native_threads": 1, "turns": 0, "capi_inference_requests": 0}}


def prepare(transfer_directory, build_path, base, output, evidence, identity):
    build = runtime._json(runtime._read(build_path))
    producer = validate_build(build, identity)
    output = runtime._safe_path(output)
    output.mkdir(exist_ok=False)
    # Existing transfer verification still binds the producer's exact run/SHA,
    # fixed bundle, both patches, source hashes and unchanged vendor archive.
    prepared = load.prepare_payload(transfer_directory, output / "payload", producer)
    transfer = prepared["transfer"]
    request = {"path": output / "payload/build-receipt.json", "sha256": transfer["build_receipt_sha256"]}
    runtime.stage_runtime(base, output / "runtime", output / "payload/inputs/agentHostMain.js", request)
    value = preparation_record(identity, build, transfer)
    raw = runtime._encoded(value) + b"\n"
    runtime._write(output / "preparation.json", raw)
    runtime._write(evidence / "prewarm-zero-turn-preparation.json", raw)
    verify_preparation(output / "preparation.json", output / "runtime", evidence, identity)
    return value


def verify_preparation(path, root, evidence, identity):
    path, root, evidence = (runtime._safe_path(item) for item in (path, root, evidence))
    require(path == root.parent / "preparation.json" and root.name == "runtime", "prewarm_runtime_path_refused")
    raw = runtime._read(path)
    value = runtime._json(raw)
    producer = validate_build(value.get("producer"), identity)
    payload = root.parent / "payload"
    staged = runtime._json(runtime._read(payload / "prepared.json"))
    transfer = load.validate_transfer(staged.get("transfer"), producer)
    require(runtime._equal(value, preparation_record(identity, value["producer"], transfer))
            and runtime._read(evidence / "prewarm-zero-turn-preparation.json") == raw,
            "prewarm_preparation_contract_refused")
    manifest_path = payload / "inputs/server-bundle-manifest.json"
    manifest = load.checked_manifest(manifest_path)
    receipt_path = payload / "build-receipt.json"
    receipt_raw = runtime._read(receipt_path)
    receipt = runtime.validate_build_receipt(runtime._json(receipt_raw))
    require(runtime._sha(runtime._read(manifest_path, load.bundle.MAX_MANIFEST)) == transfer["bundle_manifest_sha256"]
            and runtime._sha(receipt_raw) == transfer["build_receipt_sha256"]
            and runtime._equal(manifest["build_receipt"], receipt)
            and manifest["build_receipt_sha256"] == transfer["build_receipt_sha256"],
            "prewarm_build_chain_refused")
    server = root / "cli-data/servers" / ("Stable-" + runtime.PIN) / "server"
    bundle = runtime._read(server / runtime.RUNTIME_RELATIVE, runtime.MAX_BUNDLE)
    require(len(bundle) == load.BASELINE_BYTES and runtime._sha(bundle) == load.BASELINE_SHA256
            and receipt["runtime_bundle_sha256"] == load.BASELINE_SHA256, "prewarm_loaded_candidate_refused")
    # This is NOT a live load assertion. run_probe must still verify_live_ready()
    # in the actual observed process BEFORE authenticate/createSession.
    return {"path": receipt_path, "sha256": transfer["build_receipt_sha256"]}


def require_run(path, root, evidence, *, authenticated_zero_turn, session_policy, capability_only, metadata_socket):
    identity = context(running=True)
    require(authenticated_zero_turn is True and session_policy is True and capability_only is False
            and isinstance(metadata_socket, Path) and metadata_socket.is_absolute(),
            "prewarm_requires_brokered_zero_turn")
    return verify_preparation(path, root, evidence, identity)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    select = modes.add_parser("select")
    select.add_argument("--runs", type=Path, required=True)
    select.add_argument("--output", type=Path, required=True)
    stage = modes.add_parser("prepare")
    for name in ("transfer", "build", "base", "output", "evidence"):
        stage.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        identity = context()
        if args.mode == "select":
            value = select_build(runtime._json(runtime._read(args.runs)), identity)
            runtime._write(args.output, runtime._encoded(value) + b"\n")
            print(value["id"])
        else:
            prepare(args.transfer, args.build, args.base, args.output, args.evidence, identity)
            print(json.dumps({"status": "prepared_zero_turn_only", "execution_allowed": False, "model_calls": 0}))
        return 0
    except Exception as error:
        print(json.dumps({"status": "refused", "reason": str(error) if isinstance(error, Refused) else type(error).__name__,
                          "execution_allowed": False, "model_calls": 0}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
