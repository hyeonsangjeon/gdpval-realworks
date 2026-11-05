"""Hash-bound patched-host load evidence; never paid or session admission.

The public probe entry remains locked pending the owner's patch decision. The
loader and artifact contracts can be tested using inert Node modules only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import tarfile
import uuid

from ghcp_ahp_errors import Refused

PIN = "2c33b50b16c472efe58357d1d2a8a5414bc23fbf"
PATCH_SHA256 = "a4e8d0fad6bc37b73b8dc2731be6914d07e0af6460ccb7bcf6749a48f8c3bceb"
SOURCE_SHA256 = "cb7fb5b3b219585a63ec8e3dbc66bab135d2fe900b0541e73862da5302c24206"
MANIFEST_SHA256 = "cd5ff8f2e1ad1f140892febdc75f288adfe8e3c96bd4d3b8e9a4078a90ef5049"
RUNTIME_RELATIVE = "out/vs/platform/agentHost/node/agentHostMain.js"
ENTRYPOINT = "vs/platform/agentHost/node/agentHostMain"
LOADER = Path(__file__).with_suffix(".cjs")
PATCH = Path(__file__).with_name("patches") / "vscode-2c33b50b-prewarm-config-ready.patch"
MANIFEST = Path(__file__).with_name("ghcp_ahp_probe_manifest.json")
PATCHED_SOURCES = {
    "src/vs/platform/agentHost/common/agent.ts": "a4741c2a83f02acb6c7fbb61ae9800a5b9ce71d837317cb15fe79f3a2fead817",
    "src/vs/platform/agentHost/node/codex/codexAgent.ts": "2adeb9ebfc066b728ca3f62e96853ce2cdc020a530c7b741ae0da6ddd9678ede",
    "src/vs/platform/agentHost/node/agentService.ts": "280f71720d83a4326a514c16cb1d08c6ca9e4430fdb58fc98c40afc33bebb682",
}
MAX_JSON = 64 * 1024
MAX_BUNDLE = 64 * 1024 * 1024
PROVENANCE_FIELDS = ("patched_ghcp", "patch_sha256", "build_receipt_sha256", "loaded_bundle_sha256",
                     "load_evidence_sha256", "runtime_contract_sha256", "runtime_load_status",
                     "runtime_evidence_synthetic", "execution_allowed")
ARTIFACTS = ("patched-build-receipt.json", "patched-runtime-contract.json", "patched-load-evidence.json")


def require_activation():
    # No environment flag or unreviewed receipt can unlock this decision.
    raise Refused("patched_runtime_activation_pending_owner")


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _hex(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _safe_path(path):
    path = Path(path)
    if not path.is_absolute() or path.resolve() != path or any(item.is_symlink() for item in (path, *path.parents)):
        raise Refused("patched_runtime_path_refused")
    return path


def _read(path, maximum=MAX_JSON):
    path = _safe_path(path)
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(descriptor, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= maximum:
                raise Refused("patched_runtime_file_refused")
            data = stream.read(maximum + 1)
        if len(data) > maximum or len(data) != info.st_size:
            raise Refused("patched_runtime_file_refused")
        return data
    except OSError:
        raise Refused("patched_runtime_file_unavailable") from None


def _json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise Refused("patched_runtime_duplicate_key")
            result[key] = value
        return result
    try:
        value = json.loads(data, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, UnicodeError):
        raise Refused("patched_runtime_json_refused") from None
    if type(value) is not dict:
        raise Refused("patched_runtime_json_refused")
    return value


def _encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()


def _write(path, data):
    path = _safe_path(path)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def _equal(left, right):
    return _encoded(left) == _encoded(right)


def validate_build_receipt(value):
    expected = {"schema": "ghcp-patched-host-build-candidate-v2", "patched_ghcp": True,
                "upstream_commit": PIN, "patch_sha256": PATCH_SHA256, "source_archive_sha256": SOURCE_SHA256,
                "base_manifest_sha256": MANIFEST_SHA256, "patched_source_sha256": PATCHED_SOURCES,
                "runtime_relative_path": RUNTIME_RELATIVE, "evidence_kind": "source-build-no-execution",
                "execution_allowed": False, "admission_allowed": False, "model_calls": 0,
                "load_evidence_sha256": None, "runtime_load_status": "not_executed"}
    if (type(value) is not dict or set(value) != {*expected, "runtime_bundle_sha256"}
            or any(not _equal(value[key], item) for key, item in expected.items())
            or not _hex(value["runtime_bundle_sha256"])):
        raise Refused("patched_build_receipt_refused")
    return value


def build_receipt(source, bundle, output):
    """Record actual build output without activating or installing any runtime."""
    if _sha(_read(PATCH)) != PATCH_SHA256 or _sha(_read(MANIFEST)) != MANIFEST_SHA256:
        raise Refused("patched_base_pin_refused")
    for relative, expected in PATCHED_SOURCES.items():
        if _sha(_read(Path(source) / relative, MAX_BUNDLE)) != expected:
            raise Refused("patched_source_hash_refused")
    data = _read(bundle, MAX_BUNDLE)
    if b"onChatConfigurationReady" not in data:
        raise Refused("patched_bundle_hook_missing")
    value = {"schema": "ghcp-patched-host-build-candidate-v2", "patched_ghcp": True,
             "upstream_commit": PIN, "patch_sha256": PATCH_SHA256, "source_archive_sha256": SOURCE_SHA256,
             "base_manifest_sha256": MANIFEST_SHA256, "patched_source_sha256": dict(PATCHED_SOURCES),
             "runtime_relative_path": RUNTIME_RELATIVE, "runtime_bundle_sha256": _sha(data),
             "evidence_kind": "source-build-no-execution", "execution_allowed": False,
             "admission_allowed": False, "model_calls": 0,
             "load_evidence_sha256": None, "runtime_load_status": "not_executed"}
    validate_build_receipt(value)
    _write(output, _encoded(value) + b"\n")
    return value


def _request(value):
    if type(value) is not dict or set(value) != {"path", "sha256"} or not _hex(value["sha256"]):
        raise Refused("patched_build_request_refused")
    return _safe_path(value["path"]), value["sha256"]


def _verified_base_bundle(prepared):
    """The unchanged archive, Node, bootstrap and parent remain authoritative."""
    if _sha(_read(MANIFEST)) != MANIFEST_SHA256:
        raise Refused("patched_base_pin_refused")
    manifest = _json(_read(MANIFEST))
    archive_path = _safe_path(Path(prepared) / "downloads/server.tgz")
    if _sha(_read(archive_path, 512 * 1024 * 1024)) != manifest["artifacts"]["server"]["sha256"]:
        raise Refused("patched_base_server_archive_refused")
    server = Path(prepared) / "cli-data/servers" / ("Stable-" + PIN) / "server"
    original = None
    with tarfile.open(archive_path, "r:gz") as archive:
        for relative in ("node", "out/bootstrap-fork.js", "out/server-main.js", RUNTIME_RELATIVE):
            member = archive.getmember("vscode-server-linux-x64/" + relative)
            if not member.isfile() or not 0 < member.size <= 256 * 1024 * 1024:
                raise Refused("patched_base_server_member_refused")
            with archive.extractfile(member) as stream:
                raw = stream.read(member.size + 1)
            if len(raw) != member.size or _sha(_read(server / relative, 256 * 1024 * 1024)) != _sha(raw):
                raise Refused("patched_base_server_drift")
            if relative == RUNTIME_RELATIVE:
                original = _sha(raw)
    return original


def stage_runtime(base, runtime, bundle, request):
    """Copy a verified base, then replace exactly one bundle in the NEW tree.

    This performs file preparation only. Neither staging nor its receipt can
    unlock the public probe entry or substitute for a Node load event.
    """
    base, runtime, bundle = _safe_path(base), _safe_path(runtime), _safe_path(bundle)
    if runtime.exists() or runtime.is_relative_to(base) or base.is_relative_to(runtime):
        raise Refused("patched_runtime_staging_target_refused")
    receipt_path, receipt_sha = _request(request)
    raw_receipt = _read(receipt_path)
    if _sha(raw_receipt) != receipt_sha:
        raise Refused("patched_build_receipt_hash_mismatch")
    receipt = validate_build_receipt(_json(raw_receipt))
    raw_bundle = _read(bundle, MAX_BUNDLE)
    if _sha(raw_bundle) != receipt["runtime_bundle_sha256"]:
        raise Refused("patched_runtime_bundle_mismatch")
    original = _verified_base_bundle(base)
    if original == receipt["runtime_bundle_sha256"]:
        raise Refused("patched_runtime_is_unmodified_vendor_bundle")
    for folder, directories, files in os.walk(base, followlinks=False):
        for name in (*directories, *files):
            entry = Path(folder) / name
            if entry.is_symlink() or not (entry.is_dir() or entry.is_file()):
                raise Refused("patched_runtime_staging_special_file")
    shutil.copytree(base, runtime, symlinks=True)
    relative = Path("cli-data/servers") / ("Stable-" + PIN) / "server" / RUNTIME_RELATIVE
    target = _safe_path(runtime / relative)
    temporary = target.with_suffix(".patched-tmp")
    _write(temporary, raw_bundle)
    os.replace(temporary, target)
    if _sha(_read(base / relative, MAX_BUNDLE)) != original or _sha(_read(target, MAX_BUNDLE)) != receipt["runtime_bundle_sha256"]:
        raise Refused("patched_runtime_staging_drift")
    report = {"schema": "ghcp-patched-runtime-staging-v1", "patched_ghcp": True, "patch_sha256": PATCH_SHA256,
              "build_receipt_sha256": receipt_sha, "runtime_bundle_sha256": receipt["runtime_bundle_sha256"],
              "original_bundle_sha256": original, "load_evidence_sha256": None,
              "runtime_load_status": "staged_not_loaded", "execution_allowed": False, "model_calls": 0}
    _write(runtime / "patched-staging.json", _encoded(report) + b"\n")
    return report


def prepare_binding(prepared, state, request, fork_contract, *, synthetic=False):
    """Bind a separately staged candidate; never copy over the original vendor tree."""
    receipt_path, receipt_sha = _request(request)
    raw = _read(receipt_path)
    if _sha(raw) != receipt_sha:
        raise Refused("patched_build_receipt_hash_mismatch")
    receipt = validate_build_receipt(_json(raw))
    server = Path(prepared) / "cli-data/servers" / ("Stable-" + PIN) / "server"
    bundle = server / RUNTIME_RELATIVE
    node = server / "node"
    if (type(synthetic) is not bool or fork_contract.get("vscode_commit") != PIN
            or fork_contract.get("entrypoint") != ENTRYPOINT
            or fork_contract.get("files", {}).get("node", {}).get("path") != str(node)):
        raise Refused("patched_runtime_fork_binding_refused")
    if _sha(_read(bundle, MAX_BUNDLE)) != receipt["runtime_bundle_sha256"]:
        raise Refused("patched_runtime_bundle_mismatch")
    node_sha = fork_contract["files"]["node"].get("sha256")
    if not _hex(node_sha) or _sha(_read(node, 256 * 1024 * 1024)) != node_sha:
        raise Refused("patched_runtime_node_mismatch")
    directory = _safe_path(Path(state) / "wire/patched-runtime")
    directory.mkdir(mode=0o700, exist_ok=False)
    contract = {"schema": "ghcp-patched-runtime-contract-v1", "patched_ghcp": True,
                "upstream_commit": PIN, "patch_sha256": PATCH_SHA256, "build_receipt_sha256": receipt_sha,
                "runtime_bundle_sha256": receipt["runtime_bundle_sha256"], "runtime_bundle_path": str(bundle),
                "runtime_relative_path": RUNTIME_RELATIVE, "node_path": str(node), "node_sha256": node_sha,
                "loader_sha256": _sha(_read(LOADER)), "proof_directory": str(directory),
                "challenge": uuid.uuid4().hex, "entrypoint": ENTRYPOINT, "synthetic": synthetic,
                "execution_allowed": False, "admission_allowed": False}
    encoded = _encoded(contract)
    _write(directory / "contract.json", encoded)
    _write(directory / "build-receipt.json", raw)
    return {"GHCP_AHP_PATCHED_RUNTIME_CONTRACT": encoded.decode(),
            "GHCP_AHP_PATCHED_RUNTIME_CONTRACT_SHA256": _sha(encoded)}


def _validate_contract(contract, build):
    expected = {"schema": "ghcp-patched-runtime-contract-v1", "patched_ghcp": True,
                "upstream_commit": PIN, "patch_sha256": PATCH_SHA256,
                "runtime_bundle_sha256": build["runtime_bundle_sha256"], "runtime_relative_path": RUNTIME_RELATIVE,
                "entrypoint": ENTRYPOINT, "execution_allowed": False, "admission_allowed": False}
    extra = {"build_receipt_sha256", "runtime_bundle_path", "node_path", "node_sha256", "loader_sha256",
             "proof_directory", "challenge", "synthetic"}
    if (set(contract) != {*expected, *extra} or any(not _equal(contract.get(key), value) for key, value in expected.items())
            or any(not _hex(contract.get(key)) for key in ("build_receipt_sha256", "node_sha256", "loader_sha256"))
            or type(contract.get("synthetic")) is not bool
            or type(contract.get("challenge")) is not str or re.fullmatch(r"[0-9a-f]{32}", contract["challenge"]) is None
            or any(type(contract.get(key)) is not str for key in ("runtime_bundle_path", "node_path", "proof_directory"))):
        raise Refused("patched_runtime_contract_refused")


def _validate_load(contract, contract_sha, proof, records):
    expected = {"schema": "ghcp-patched-runtime-load-v1", "patched_ghcp": True,
                "upstream_commit": PIN, "patch_sha256": PATCH_SHA256,
                "build_receipt_sha256": contract["build_receipt_sha256"], "runtime_contract_sha256": contract_sha,
                "loaded_relative_path": RUNTIME_RELATIVE, "loaded_source_sha256": contract["runtime_bundle_sha256"],
                "disk_before_sha256": contract["runtime_bundle_sha256"], "disk_after_sha256": contract["runtime_bundle_sha256"],
                "node_sha256": contract["node_sha256"], "loader_sha256": contract["loader_sha256"],
                "challenge_sha256": _sha(contract["challenge"].encode()), "synthetic": contract["synthetic"],
                "phase": "node_load_hook_before_evaluation", "execution_allowed": False}
    if (set(proof) != {*expected, "pid", "ppid"}
            or any(not _equal(proof.get(key), value) for key, value in expected.items())
            or any(type(proof.get(key)) is not int or proof[key] <= 0 for key in ("pid", "ppid"))):
        raise Refused("patched_runtime_load_evidence_refused")
    forks = [row for row in records if row.get("kind") == "patched_runtime_child"]
    installed = [row for row in records if row.get("kind") == "observer_installed"
                 and row.get("entrypoint") == ENTRYPOINT and row.get("process") == f"wire-{proof['pid']}.jsonl"]
    if (len(forks) != 1 or len(installed) != 1
            or type(forks[0].get("child_pid")) is not int or type(forks[0].get("parent_pid")) is not int
            or forks[0].get("child_pid") != proof["pid"] or forks[0].get("parent_pid") != proof["ppid"]
            or forks[0].get("runtime_contract_sha256") != contract_sha
            or forks[0].get("process") != f"wire-{proof['ppid']}.jsonl"
            or forks[0].get("synthetic") is not contract["synthetic"]
            or installed[0].get("synthetic") is not contract["synthetic"]
            or installed[0].get("model_free") is not True or installed[0].get("session_only") is not True):
        raise Refused("patched_runtime_process_binding_refused")


def collect(state, destination, records):
    """Require an actual child-loader event, not staged bytes or a source quote."""
    directory = Path(state) / "wire/patched-runtime"
    raw_contract, raw_build = _read(directory / "contract.json"), _read(directory / "build-receipt.json")
    contract, build = _json(raw_contract), validate_build_receipt(_json(raw_build))
    _validate_contract(contract, build)
    if _sha(raw_build) != contract["build_receipt_sha256"] or contract["loader_sha256"] != _sha(_read(LOADER)):
        raise Refused("patched_runtime_binding_drift")
    files = sorted(directory.glob("load-*.json"))
    if len(files) != 1:
        raise Refused("patched_runtime_load_unmeasured_or_duplicate")
    raw_proof = _read(files[0])
    proof = _json(raw_proof)
    if files[0].name != f"load-{proof.get('pid')}.json":
        raise Refused("patched_runtime_load_path_refused")
    _validate_load(contract, _sha(raw_contract), proof, records)
    if (_sha(_read(Path(contract["runtime_bundle_path"]), MAX_BUNDLE)) != build["runtime_bundle_sha256"]
            or _sha(_read(Path(contract["node_path"]), 256 * 1024 * 1024)) != contract["node_sha256"]):
        raise Refused("patched_runtime_post_load_drift")
    if destination is not None:
        for name, raw in zip(ARTIFACTS, (raw_build, raw_contract, raw_proof), strict=True):
            _write(Path(destination) / name, raw)
    return {"patched_ghcp": True, "patch_sha256": PATCH_SHA256, "build_receipt_sha256": _sha(raw_build),
            "loaded_bundle_sha256": build["runtime_bundle_sha256"], "load_evidence_sha256": _sha(raw_proof),
            "runtime_contract_sha256": _sha(raw_contract), "runtime_load_status": "measured",
            "runtime_evidence_synthetic": contract["synthetic"], "execution_allowed": False}


def verify_live_ready(state):
    """Extra boundary before authentication/session RPC; no artifact copying."""
    files = sorted((Path(state) / "wire").glob("wire-*.jsonl"))
    if len(files) > 16:
        raise Refused("patched_runtime_observer_limit")
    records, total = [], 0
    for file in files:
        if re.fullmatch(r"wire-[0-9]+\.jsonl", file.name) is None:
            raise Refused("patched_runtime_observer_path_refused")
        raw = _read(file, 2 * 1024 * 1024)
        total += len(raw)
        if total > 2 * 1024 * 1024:
            raise Refused("patched_runtime_observer_limit")
        for index, line in enumerate(raw.splitlines(keepends=True), 1):
            if not line.endswith(b"\n"):
                continue
            row = _json(line)
            if type(row.get("sequence")) is not int or row["sequence"] != index:
                raise Refused("patched_runtime_observer_sequence_refused")
            records.append({**row, "process": file.name})
    return collect(state, None, records)


def refusal_fields(request):
    digest = request.get("sha256") if type(request) is dict else None
    return {"patched_ghcp": True, "patch_sha256": PATCH_SHA256,
            "build_receipt_sha256": digest if _hex(digest) else None,
            "loaded_bundle_sha256": None, "load_evidence_sha256": None, "runtime_contract_sha256": None,
            "runtime_load_status": "unmeasured_refused", "runtime_evidence_synthetic": None, "execution_allowed": False}


def validate_provenance(value, *, measured=True):
    if (type(value) is not dict or any(key not in value for key in PROVENANCE_FIELDS)
            or value["patched_ghcp"] is not True or value["patch_sha256"] != PATCH_SHA256
            or value["execution_allowed"] is not False):
        raise Refused("patched_runtime_provenance_missing_or_invalid")
    hashes = ("build_receipt_sha256", "loaded_bundle_sha256", "load_evidence_sha256", "runtime_contract_sha256")
    if measured:
        if (value["runtime_load_status"] != "measured" or any(not _hex(value[key]) for key in hashes)
                or type(value["runtime_evidence_synthetic"]) is not bool):
            raise Refused("patched_runtime_provenance_unmeasured")
    elif (value["runtime_load_status"] != "unmeasured_refused" or any(value[key] is not None for key in hashes[1:])
          or value["runtime_evidence_synthetic"] is not None
          or value["build_receipt_sha256"] is not None and not _hex(value["build_receipt_sha256"])):
        raise Refused("patched_runtime_refusal_provenance_invalid")
    if measured and value["runtime_evidence_synthetic"] and "synthetic" in value and value["synthetic"] is not True:
        raise Refused("patched_runtime_fixture_cannot_be_live_evidence")
    for key in ("execution_allowed", "launch_allowed", "admission_allowed", "gate_ready", "connection_verified"):
        if key in value and value[key] is not False:
            raise Refused("patched_runtime_cannot_admit_execution")
    if "model_calls" in value and (type(value["model_calls"]) is not int or value["model_calls"] != 0):
        raise Refused("patched_runtime_cannot_admit_execution")
    return {key: value[key] for key in PROVENANCE_FIELDS}


def stamp(document, provenance):
    """Producer only. Consumers validate persisted keys; they never fill omissions."""
    measured = provenance.get("runtime_load_status") == "measured"
    validate_provenance(provenance, measured=measured)
    if any(key in document and not _equal(document[key], provenance[key]) for key in PROVENANCE_FIELDS):
        raise Refused("patched_runtime_provenance_conflict")
    result = {**document, **provenance}
    validate_provenance(result, measured=measured)
    return result


def verify_artifact_chain(directory, *, handshake=False, policy=False):
    """Reject dropped/changed labels in the result, receipt or stdout summary."""
    directory = Path(directory)
    names = (["wire-capture.json", "probe.json", "summary.json"]
             + (["handshake.json"] if handshake else []) + (["thread-policy.json"] if policy else []))
    documents = [_json(_read(directory / name, 16 * 1024 * 1024)) for name in names]
    metadata = [validate_provenance(value) for value in documents]
    if any(not _equal(value, metadata[0]) for value in metadata[1:]):
        raise Refused("patched_runtime_propagation_mismatch")
    raw_build, raw_contract, raw_proof = [_read(directory / name) for name in ARTIFACTS]
    build, contract, proof = validate_build_receipt(_json(raw_build)), _json(raw_contract), _json(raw_proof)
    _validate_contract(contract, build)
    observer_sha = _sha(_read(LOADER.with_name("ghcp_ahp_wire_preload.cjs")))
    if (contract["loader_sha256"] != _sha(_read(LOADER))
            or documents[0].get("bootstrap", {}).get("observer_sha256") != observer_sha
            or any(row.get("observer_sha256") != observer_sha for row in documents[0].get("records", [])
                   if row.get("kind") == "observer_installed")):
        raise Refused("patched_runtime_observer_identity_mismatch")
    _validate_load(contract, _sha(raw_contract), proof, documents[0].get("records", []))
    expected = {"build_receipt_sha256": _sha(raw_build), "runtime_contract_sha256": _sha(raw_contract),
                "load_evidence_sha256": _sha(raw_proof), "loaded_bundle_sha256": build["runtime_bundle_sha256"]}
    if (contract["build_receipt_sha256"] != expected["build_receipt_sha256"]
            or metadata[0]["runtime_evidence_synthetic"] is not contract["synthetic"]
            or any(metadata[0][key] != value for key, value in expected.items())):
        raise Refused("patched_runtime_artifact_hash_mismatch")
    return documents[2]


def render_summary(directory, *, handshake=False, policy=False):
    """Human summary consumes the same verified artifacts, never loose labels."""
    value = verify_artifact_chain(directory, handshake=handshake, policy=policy)
    lines = ["Patched GHCP — loader evidence only; execution remains disabled.", "",
             "This is not native-policy or served-model attestation.", ""]
    for key in PROVENANCE_FIELDS:
        lines.append(f"- {key}: `{json.dumps(value[key], ensure_ascii=True)}`")
    return "\n".join(lines) + "\n"


def write_summary(directory, *, handshake=False, policy=False):
    _write(Path(directory) / "summary.md", render_summary(directory, handshake=handshake, policy=policy).encode())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    build = modes.add_parser("build-receipt")
    build.add_argument("--source", type=Path, required=True)
    build.add_argument("--bundle", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    stage = modes.add_parser("stage-runtime")
    stage.add_argument("--base", type=Path, required=True)
    stage.add_argument("--runtime", type=Path, required=True)
    stage.add_argument("--bundle", type=Path, required=True)
    stage.add_argument("--build-receipt", type=Path, required=True)
    stage.add_argument("--build-receipt-sha256", required=True)
    args = parser.parse_args(argv)
    if args.mode == "stage-runtime":
        report = stage_runtime(args.base, args.runtime, args.bundle,
                               {"path": args.build_receipt, "sha256": args.build_receipt_sha256})
        print(json.dumps(report))
        return 0
    build_receipt(args.source, args.bundle, args.output)
    print(json.dumps({"patched_ghcp": True, "patch_sha256": PATCH_SHA256, "execution_allowed": False,
                      "load_evidence_sha256": None, "model_calls": 0, "status": "build_receipt_only_not_load_evidence"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
