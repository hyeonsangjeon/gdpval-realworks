"""Same-run, no-auth real-bundle load smoke. Actual execution is Actions-only."""

from __future__ import annotations

import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import tarfile

import ghcp_ahp_bundle_manifest as bundle
import ghcp_ahp_patched_runtime as runtime
import ghcp_ahp_probe as probe
from ghcp_ahp_errors import Refused

DRIVER = Path(__file__).with_suffix(".cjs")
BASELINE_SHA256 = "5006baa5e4e032cf28f47de802b386ebed6b2c3616943943b3cfa06fce4a7c43"
BASELINE_BYTES = 5193139
PAYLOAD_LIMIT = 512 * 1024 * 1024
FILES = {"agentHostMain.js": runtime.MAX_BUNDLE, "server-bundle-manifest.json": bundle.MAX_MANIFEST,
         "server.tgz": 335544320}
PROFILE_DATABASE = "User/globalStorage/agent-host.db"
# Pinned agentHostDatabase.ts:960,965,1440,1453 and agentHostCatalogProjection.ts:19.
# This is an explicitly synthetic empty smoke profile, NOT a measured migration
# receipt or a state input for readiness, authenticated sessions or the paid gate.
PROFILE_MARKER = "sessionsV2PayloadBackfilled:copilotcli:v2"
PROFILE_DISCOVERY_MARKER = "sessionRegistryBackfilled:copilotcli"
PROFILE_MARKERS = (PROFILE_DISCOVERY_MARKER, PROFILE_MARKER)
PROFILE_METADATA_SQL = "CREATE TABLE metadata (key TEXT PRIMARY KEY NOT NULL, value TEXT NOT NULL)"


def ci_identity():
    value = probe.require_runner()
    return {key: value[key] for key in ("github_run_id", "github_run_attempt", "github_sha")}


def checked_manifest(path):
    value = bundle.validate_manifest(runtime._json(runtime._read(path, bundle.MAX_MANIFEST)))
    if value["entrypoint"]["sha256"] != BASELINE_SHA256 or value["entrypoint"]["bytes"] != BASELINE_BYTES:
        raise Refused("load_smoke_baseline_bundle_refused")
    return value


def pack_payload(bundle_path, manifest_path, server_archive, output, identity):
    """Transfer exact producer bytes, never rebuild them in the consumer job."""
    manifest = checked_manifest(manifest_path)
    raw_bundle = runtime._read(bundle_path, runtime.MAX_BUNDLE)
    server_pin = bundle.base_manifest()["artifacts"]["server"]
    if runtime._sha(raw_bundle) != BASELINE_SHA256 or len(raw_bundle) != BASELINE_BYTES:
        raise Refused("load_smoke_producer_bundle_refused")
    if runtime._sha(runtime._read(server_archive, server_pin["maximum_bytes"])) != server_pin["sha256"]:
        raise Refused("load_smoke_server_archive_refused")
    output = runtime._safe_path(output)
    output.mkdir(exist_ok=False)
    payload = output / "payload.tar"
    with tarfile.open(payload, "w") as archive:
        for name, path in (("agentHostMain.js", bundle_path), ("server-bundle-manifest.json", manifest_path), ("server.tgz", server_archive)):
            info = archive.gettarinfo(str(path), arcname=name)
            if not info.isfile() or not 0 < info.size <= FILES[name]:
                raise Refused("load_smoke_transfer_member_refused")
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mode, info.mtime = 0o600, 0
            with Path(path).open("rb") as stream:
                archive.addfile(info, stream)
    raw = runtime._read(payload, PAYLOAD_LIMIT)
    receipt = {"schema": "ghcp-load-smoke-transfer-v1", "identity": identity,
               "upstream_commit": runtime.PIN, "patch_sha256": runtime.PATCH_SHA256,
               "bundle_sha256": BASELINE_SHA256, "bundle_bytes": BASELINE_BYTES,
               "bundle_manifest_sha256": runtime._sha(runtime._read(manifest_path, bundle.MAX_MANIFEST)),
               "build_receipt_sha256": manifest["build_receipt_sha256"], "server_archive_sha256": server_pin["sha256"],
               "payload_sha256": runtime._sha(raw), "payload_bytes": len(raw),
               "synthetic": True, "model_free": True, "execution_allowed": False}
    runtime._write(output / "transfer.json", runtime._encoded(receipt) + b"\n")
    return receipt


def validate_transfer(value, identity):
    if (type(identity) is not dict or set(identity) != {"github_run_id", "github_run_attempt", "github_sha"}
            or any(type(identity[key]) is not str or re.fullmatch(r"[1-9][0-9]*", identity[key]) is None
                   for key in ("github_run_id", "github_run_attempt"))
            or type(identity["github_sha"]) is not str or re.fullmatch(r"[a-f0-9]{40}", identity["github_sha"]) is None):
        raise Refused("load_smoke_run_identity_refused")
    expected = {"schema": "ghcp-load-smoke-transfer-v1", "identity": identity,
                "upstream_commit": runtime.PIN, "patch_sha256": runtime.PATCH_SHA256,
                "bundle_sha256": BASELINE_SHA256, "bundle_bytes": BASELINE_BYTES,
                "server_archive_sha256": bundle.base_manifest()["artifacts"]["server"]["sha256"],
                "synthetic": True, "model_free": True, "execution_allowed": False}
    if (type(value) is not dict or set(value) != {*expected, "bundle_manifest_sha256", "build_receipt_sha256", "payload_sha256", "payload_bytes"}
            or any(not runtime._equal(value.get(key), data) for key, data in expected.items())
            or any(not runtime._hex(value[key]) for key in ("bundle_manifest_sha256", "build_receipt_sha256", "payload_sha256"))
            or type(value["payload_bytes"]) is not int or not 0 < value["payload_bytes"] <= PAYLOAD_LIMIT):
        raise Refused("load_smoke_same_run_transfer_refused")
    runtime.verify_patch_set()
    return value


def prepare_payload(transfer_directory, output, identity):
    transfer_directory, output = runtime._safe_path(transfer_directory), runtime._safe_path(output)
    transfer = validate_transfer(runtime._json(runtime._read(transfer_directory / "transfer.json")), identity)
    raw = runtime._read(transfer_directory / "payload.tar", PAYLOAD_LIMIT)
    if len(raw) != transfer["payload_bytes"] or runtime._sha(raw) != transfer["payload_sha256"]:
        raise Refused("load_smoke_payload_hash_refused")
    output.mkdir(exist_ok=False)
    inputs = output / "inputs"
    inputs.mkdir()
    with tarfile.open(transfer_directory / "payload.tar", "r:") as archive:
        members = archive.getmembers()
        if len(members) != len(FILES) or {item.name for item in members} != set(FILES):
            raise Refused("load_smoke_payload_members_refused")
        for item in members:
            if not item.isfile() or not 0 < item.size <= FILES[item.name]:
                raise Refused("load_smoke_transfer_member_refused")
            with archive.extractfile(item) as stream:
                data = stream.read(item.size + 1)
            if len(data) != item.size:
                raise Refused("load_smoke_transfer_member_refused")
            runtime._write(inputs / item.name, data)
    manifest_path = inputs / "server-bundle-manifest.json"
    if runtime._sha(runtime._read(manifest_path, bundle.MAX_MANIFEST)) != transfer["bundle_manifest_sha256"]:
        raise Refused("load_smoke_manifest_hash_refused")
    manifest = checked_manifest(manifest_path)
    raw_bundle = runtime._read(inputs / "agentHostMain.js", runtime.MAX_BUNDLE)
    if len(raw_bundle) != BASELINE_BYTES or runtime._sha(raw_bundle) != BASELINE_SHA256:
        raise Refused("load_smoke_received_bundle_refused")
    if runtime._sha(runtime._read(inputs / "server.tgz", FILES["server.tgz"])) != transfer["server_archive_sha256"]:
        raise Refused("load_smoke_server_archive_refused")
    receipt_path = output / "build-receipt.json"
    runtime._write(receipt_path, runtime._encoded(manifest["build_receipt"]) + b"\n")
    if runtime._sha(runtime._read(receipt_path)) != transfer["build_receipt_sha256"]:
        raise Refused("load_smoke_build_receipt_refused")
    base = output / "base"
    (base / "downloads").mkdir(parents=True)
    shutil.copyfile(inputs / "server.tgz", base / "downloads/server.tgz")
    cache = base / "cli-data/servers" / ("Stable-" + runtime.PIN)
    cache.mkdir(parents=True)
    probe.extract_archive(inputs / "server.tgz", cache)
    (cache / "vscode-server-linux-x64").rename(cache / "server")
    request = {"path": receipt_path, "sha256": transfer["build_receipt_sha256"]}
    for name in ("positive", "negative"):
        runtime.stage_runtime(base, output / name, inputs / "agentHostMain.js", request)
    prepared = {"schema": "ghcp-load-smoke-prepared-v1", "transfer": transfer,
                "transfer_sha256": runtime._sha(runtime._read(transfer_directory / "transfer.json")),
                "bundle_manifest_sha256": transfer["bundle_manifest_sha256"], "execution_allowed": False}
    runtime._write(output / "prepared.json", runtime._encoded(prepared) + b"\n")
    return prepared


def validate_profile_seed(value):
    expected = {"schema": "ghcp-load-smoke-catalog-profile-v1", "upstream_commit": runtime.PIN,
                "database_relative_path": PROFILE_DATABASE, "initial_user_version": 0,
                "initial_tables": ["metadata"], "metadata": [[marker, "true"] for marker in PROFILE_MARKERS],
                "evidence_kind": "synthetic_empty_profile_not_measured_migration",
                "synthetic": True, "execution_allowed": False}
    if (type(value) is not dict or set(value) != {*expected, "database_sha256"}
            or any(not runtime._equal(value.get(key), data) for key, data in expected.items())
            or not runtime._hex(value["database_sha256"])):
        raise Refused("load_smoke_profile_receipt_refused")
    return value


def profile_seed_receipt(data):
    data = runtime._safe_path(data)
    path = runtime._safe_path(data / PROFILE_DATABASE)
    raw = runtime._read(path, 1024 * 1024)
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as database:
        version = database.execute("PRAGMA user_version").fetchone()[0]
        tables = [row[0] for row in database.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        rows = [list(row) for row in database.execute("SELECT key, value FROM metadata ORDER BY key")]
    return validate_profile_seed({"schema": "ghcp-load-smoke-catalog-profile-v1", "upstream_commit": runtime.PIN,
        "database_relative_path": PROFILE_DATABASE, "database_sha256": runtime._sha(raw),
        "initial_user_version": version, "initial_tables": tables, "metadata": rows,
        "evidence_kind": "synthetic_empty_profile_not_measured_migration", "synthetic": True, "execution_allowed": False})


def seed_smoke_profile(data):
    """Prepare one fresh case's empty user-data directory; never reuse user state.

    Pinned agentHostBootstrap.ts:120 + environmentService.ts:56 locate this DB.
    The native host still runs all real schema migrations from user_version=0
    (agentHostDatabase.ts:4331). Both Copilot catalog completion markers are
    required: payload migration (agentHostSessionsV2MigrationService.ts:90-92)
    and post-migration provider discovery (agentService.ts:4450-4451). The
    latter otherwise starts the SDK even after payload migration is complete.
    """
    data = runtime._safe_path(data)
    if not data.is_dir() or any(data.iterdir()):
        raise Refused("load_smoke_profile_not_empty")
    path = data / PROFILE_DATABASE
    path.parent.mkdir(parents=True, exist_ok=False, mode=0o700)
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    os.close(descriptor)
    with closing(sqlite3.connect(path)) as database:
        database.execute(PROFILE_METADATA_SQL)
        database.executemany("INSERT INTO metadata (key, value) VALUES (?, ?)",
                             ((marker, "true") for marker in PROFILE_MARKERS))
        database.commit()
    return profile_seed_receipt(data)


def case_config(root, name, receipt_path, receipt_sha):
    prepared = root / name
    server = prepared / "cli-data/servers" / ("Stable-" + runtime.PIN) / "server"
    node, bootstrap = server / "node", server / "out/bootstrap-fork.js"
    state = root / (name + "-state")
    for directory in (state / "wire", state / "logs", state / "data", state / "tmp"):
        directory.mkdir(parents=True, exist_ok=False, mode=0o700)
    profile = seed_smoke_profile(state / "data")
    fork = {"vscode_commit": runtime.PIN, "entrypoint": runtime.ENTRYPOINT,
            "files": {"node": {"path": str(node), "sha256": runtime._sha(runtime._read(node, 256 * 1024 * 1024))}}}
    environment = runtime.prepare_binding(prepared, state, {"path": receipt_path, "sha256": receipt_sha}, fork, synthetic=True)
    config_path = state / "driver-config.json"
    config = {"environment": environment, "config_path": str(config_path), "bootstrap": str(bootstrap),
              "bootstrap_sha256": runtime._sha(runtime._read(bootstrap, runtime.MAX_BUNDLE)),
              "logs": str(state / "logs"), "data": str(state / "data"), "socket": str(state / "tmp/agent.sock"),
              "process_report": str(state / "process.json"), "profile_seed": profile}
    runtime._write(config_path, runtime._encoded(config) + b"\n")
    return state, server, config


def check_process(value, *, negative=False):
    if (type(value) is not dict or value.get("schema") != "ghcp-load-smoke-process-v1" or value.get("synthetic") is not True
            or value.get("model_free") is not True or value.get("execution_allowed") is not False
            or value.get("timed_out") is not False or value.get("launch_error") is not None
            or any(type(value.get(key)) is not int or value[key] <= 0 for key in ("child_pid", "parent_pid"))
            or any(type(value.get(key)) is not int or value[key] != 0 for key in ("ipc_messages_sent", "sessions_created", "turns_sent"))
            or any(row.get("kind") in ("boundary_refused", "output_limit_refused") for row in value.get("events", []))):
        raise Refused("load_smoke_process_boundary_refused")
    forks = [row for row in value.get("records", []) if row.get("kind") == "patched_runtime_child"]
    if (len(forks) != 1 or forks[0].get("child_pid") != value["child_pid"]
            or forks[0].get("parent_pid") != value["parent_pid"]):
        raise Refused("load_smoke_process_identity_refused")
    errors = [row for row in value.get("events", []) if row.get("kind") == "import_error"]
    if negative:
        if (value.get("import_resolved") is not False or value.get("exit_code") != 2 or value.get("signal") is not None
                or len(errors) != 1 or errors[0].get("message") != "patched_runtime_hash_mismatch"):
            raise Refused("load_smoke_tamper_not_refused")
    elif (value.get("import_resolved") is not True or errors
            or not (value.get("stop_requested") is True and value.get("signal") == "SIGTERM" and value.get("exit_code") is None)):
        raise Refused("load_smoke_import_not_confirmed")
    return value


def one_byte_mutant(data):
    if not data:
        raise Refused("load_smoke_empty_mutant_source")
    return bytes([data[0] ^ 1]) + data[1:]


def verify_smoke_evidence(evidence, expected_identity=None):
    """Consumer validation: never substitute producer labels for the Node hook files."""
    result = runtime._json(runtime._read(evidence / "load-smoke.json", 4 * 1024 * 1024))
    fields = {"schema", "synthetic", "model_free", "execution_allowed", "admission_allowed", "model_calls",
              "sessions_created", "turns_sent", "authentication_supplied", "identity", "isolation", "patch_sha256",
              "bundle_manifest_sha256", "expected_bundle_sha256", "driver_sha256", "cases", "status", "failures",
              "runtime_provenance", "mutation", "negative_load_evidence_files", "profile_seeds"}
    if (type(result) is not dict or set(result) != fields or result["schema"] != "ghcp-real-bundle-load-smoke-v1"
            or type(result["cases"]) is not dict or set(result["cases"]) != {"positive", "negative"}):
        raise Refused("load_smoke_receipt_schema_refused")
    profiles = result["profile_seeds"]
    if type(profiles) is not dict or set(profiles) != {"positive", "negative"}:
        raise Refused("load_smoke_profile_receipt_refused")
    for profile in profiles.values():
        validate_profile_seed(profile)
    manifest = checked_manifest(evidence / "server-bundle-manifest.json")
    transfer = validate_transfer(runtime._json(runtime._read(evidence / "transfer.json")),
                                 expected_identity if expected_identity is not None else result.get("identity"))
    if (result.get("status") != "success" or result.get("failures") != []
            or result.get("synthetic") is not True or result.get("model_free") is not True
            or result.get("execution_allowed") is not False or result.get("admission_allowed") is not False
            or result.get("authentication_supplied") is not False
            or type(result.get("negative_load_evidence_files")) is not int or result["negative_load_evidence_files"] != 0
            or any(type(result.get(key)) is not int or result[key] != 0 for key in ("model_calls", "sessions_created", "turns_sent"))
            or result.get("patch_sha256") != runtime.PATCH_SHA256
            or result.get("expected_bundle_sha256") != BASELINE_SHA256
            or result.get("driver_sha256") != runtime._sha(runtime._read(DRIVER))
            or result.get("identity") != transfer["identity"]
            or result.get("bundle_manifest_sha256") != transfer["bundle_manifest_sha256"]
            or runtime._sha(runtime._read(evidence / "server-bundle-manifest.json", bundle.MAX_MANIFEST)) != transfer["bundle_manifest_sha256"]):
        raise Refused("load_smoke_receipt_refused")
    isolation = result.get("isolation", {})
    if (isolation.get("interfaces") != ["lo"]
            or any(isolation.get(key) is not True for key in ("pid_one", "unprivileged", "no_new_privileges"))
            or re.fullmatch(r"net:\[[0-9]+\]", isolation.get("network_namespace", "")) is None
            or re.fullmatch(r"net:\[[0-9]+\]", isolation.get("outside_network_namespace", "")) is None
            or isolation["network_namespace"] == isolation["outside_network_namespace"]
            or re.fullmatch(r"pid:\[[0-9]+\]", isolation.get("pid_namespace", "")) is None
            or re.fullmatch(r"pid:\[[0-9]+\]", isolation.get("outside_pid_namespace", "")) is None
            or isolation["pid_namespace"] == isolation["outside_pid_namespace"]):
        raise Refused("load_smoke_isolation_evidence_refused")
    check_process(result["cases"]["positive"])
    check_process(result["cases"]["negative"], negative=True)
    provenance = runtime.validate_provenance({**result["runtime_provenance"], "synthetic": True})
    raw_build, raw_contract, raw_proof = [runtime._read(evidence / name) for name in runtime.ARTIFACTS]
    build = runtime.validate_build_receipt(runtime._json(raw_build))
    contract, proof = runtime._json(raw_contract), runtime._json(raw_proof)
    runtime._validate_contract(contract, build)
    runtime._validate_load(contract, runtime._sha(raw_contract), proof, result["cases"]["positive"]["records"])
    if (build != manifest["build_receipt"] or provenance["patch_sha256"] != transfer["patch_sha256"]
            or provenance["build_receipt_sha256"] != runtime._sha(raw_build)
            or provenance["runtime_contract_sha256"] != runtime._sha(raw_contract)
            or provenance["load_evidence_sha256"] != runtime._sha(raw_proof)
            or provenance["loaded_bundle_sha256"] != manifest["entrypoint"]["sha256"]
            or provenance["runtime_evidence_synthetic"] is not True
            or contract["loader_sha256"] != runtime._sha(runtime._read(runtime.LOADER))):
        raise Refused("load_smoke_receipt_chain_refused")
    mutation = result.get("mutation", {})
    if (type(mutation) is not dict or set(mutation) != {"offset", "changed_bytes", "bytes", "original_sha256", "mutant_sha256"}
            or any(type(mutation[key]) is not int for key in ("offset", "changed_bytes", "bytes"))
            or mutation["offset"] != 0 or mutation["changed_bytes"] != 1 or mutation["bytes"] != BASELINE_BYTES
            or mutation.get("original_sha256") != BASELINE_SHA256
            or not runtime._hex(mutation.get("mutant_sha256")) or mutation["mutant_sha256"] == BASELINE_SHA256):
        raise Refused("load_smoke_mutation_receipt_refused")
    return result


def run_smoke(root, evidence, identity, outside_netns, outside_pidns):
    isolation = probe.require_isolation(outside_netns, outside_pidns)
    isolation["outside_pid_namespace"] = outside_pidns
    root, evidence = runtime._safe_path(root), runtime._safe_path(evidence)
    evidence.mkdir(exist_ok=False)
    prepared = runtime._json(runtime._read(root / "prepared.json"))
    transfer = validate_transfer(prepared["transfer"], identity)
    manifest = checked_manifest(root / "inputs/server-bundle-manifest.json")
    receipt_path, receipt_sha = root / "build-receipt.json", transfer["build_receipt_sha256"]
    result = {"schema": "ghcp-real-bundle-load-smoke-v1", "synthetic": True, "model_free": True,
              "execution_allowed": False, "admission_allowed": False, "model_calls": 0,
              "sessions_created": 0, "turns_sent": 0, "authentication_supplied": False,
              "identity": identity, "isolation": isolation, "patch_sha256": runtime.PATCH_SHA256,
              "bundle_manifest_sha256": transfer["bundle_manifest_sha256"], "expected_bundle_sha256": BASELINE_SHA256,
              "driver_sha256": runtime._sha(runtime._read(DRIVER)), "cases": {}, "profile_seeds": {}, "status": "failure"}
    failures = []
    for name in ("positive", "negative"):
        state, server, config = case_config(root, name, receipt_path, receipt_sha)
        profile = profile_seed_receipt(Path(config["data"]))
        if not runtime._equal(profile, config["profile_seed"]):
            raise Refused("load_smoke_profile_changed_before_launch")
        result["profile_seeds"][name] = profile
        if name == "negative":
            target = server / runtime.RUNTIME_RELATIVE
            original = runtime._read(target, runtime.MAX_BUNDLE)
            changed = one_byte_mutant(original)
            temporary = target.with_suffix(".one-byte-mutant")
            runtime._write(temporary, changed)
            os.replace(temporary, target)
            result["mutation"] = {"offset": 0, "changed_bytes": sum(a != b for a, b in zip(original, changed, strict=True)), "bytes": len(changed),
                                  "original_sha256": runtime._sha(original), "mutant_sha256": runtime._sha(changed)}
        child = subprocess.run([str(server / "node"), str(DRIVER), config["config_path"]],
                               env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}, cwd=server,
                               capture_output=True, text=True, timeout=30)
        process_path = Path(config["process_report"])
        if child.returncode != 0 or not process_path.is_file():
            failures.append(name + ":load_smoke_driver_failed")
            result["cases"][name] = {"driver_exit_code": child.returncode, "stderr": probe.redact(child.stderr)}
            continue
        process = runtime._json(runtime._read(process_path, 4 * 1024 * 1024))
        result["cases"][name] = process
        try:
            check_process(process, negative=name == "negative")
        except Refused as error:
            failures.append(name + ":" + str(error))
        if name == "positive":
            try:
                provenance = runtime.collect(state, evidence, process["records"])
                runtime.validate_provenance({**provenance, "synthetic": True})
                if provenance["loaded_bundle_sha256"] != manifest["entrypoint"]["sha256"]:
                    raise Refused("load_smoke_manifest_load_mismatch")
                result["runtime_provenance"] = provenance
            except Refused as error:
                failures.append(name + ":" + str(error))
        else:
            result["negative_load_evidence_files"] = len(list((state / "wire/patched-runtime").glob("load-*.json")))
            if result["negative_load_evidence_files"] != 0:
                failures.append("negative:load_smoke_tampered_load_evidence_present")
    result["failures"] = failures
    result["status"] = "failure" if failures else "success"
    runtime._write(evidence / "load-smoke.json", runtime._encoded(result) + b"\n")
    runtime._write(evidence / "server-bundle-manifest.json", runtime._read(root / "inputs/server-bundle-manifest.json", bundle.MAX_MANIFEST))
    runtime._write(evidence / "transfer.json", runtime._encoded(transfer) + b"\n")
    if failures:
        raise Refused("load_smoke_refused")  # Details stay in JSON; ':' is not a safe refusal-code character.
    return verify_smoke_evidence(evidence, identity)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    pack = modes.add_parser("pack")
    for name in ("bundle", "manifest", "server-archive", "output"):
        pack.add_argument("--" + name, type=Path, required=True)
    prepare = modes.add_parser("prepare")
    prepare.add_argument("--transfer", type=Path, required=True)
    prepare.add_argument("--output", type=Path, required=True)
    run = modes.add_parser("run")
    run.add_argument("--prepared", type=Path, required=True)
    run.add_argument("--evidence", type=Path, required=True)
    run.add_argument("--outside-netns", required=True)
    run.add_argument("--outside-pidns", required=True)
    args = parser.parse_args(argv)
    identity = ci_identity()  # Must fail before any real payload preparation or process launch on NAS.
    if args.mode == "pack":
        value = pack_payload(args.bundle, args.manifest, args.server_archive, args.output, identity)
    elif args.mode == "prepare":
        value = prepare_payload(args.transfer, args.output, identity)
    else:
        value = run_smoke(args.prepared, args.evidence, identity, args.outside_netns, args.outside_pidns)
    print(json.dumps({"schema": value["schema"], "execution_allowed": False, "model_calls": 0,
                      "status": value.get("status", "prepared_without_execution")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
