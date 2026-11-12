"""Source-build input and hash/size manifests only; never install or execute a host."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import tarfile

import ghcp_ahp_patched_runtime as runtime
from ghcp_ahp_errors import Refused

ENTRY = "vs/platform/agentHost/node/agentHostMain.js"
COMMAND = ["node", "build/next/index.ts", "bundle", "--target", "server", "--minify", "--out", "out-patched"]
MAX_OUTPUT_FILE = 256 * 1024 * 1024
MAX_MANIFEST = 16 * 1024 * 1024


def base_manifest():
    raw = runtime._read(runtime.MANIFEST)
    if runtime._sha(raw) != runtime.MANIFEST_SHA256:
        raise Refused("patched_base_pin_refused")
    return runtime._json(raw)


def prepare_inputs(source, source_archive, server_archive, output):
    """Prepare vendor product metadata and a deterministic date; no SDK/CLI launch."""
    source = runtime._safe_path(source)
    manifest = base_manifest()
    runtime.verify_patch_set()
    if runtime._sha(runtime._read(source_archive, 100663296)) != runtime.SOURCE_SHA256:
        raise Refused("bundle_source_archive_refused")
    server_pin = manifest["artifacts"]["server"]
    if runtime._sha(runtime._read(server_archive, server_pin["maximum_bytes"])) != server_pin["sha256"]:
        raise Refused("bundle_server_archive_refused")
    with tarfile.open(server_archive, "r:gz") as archive:
        member = archive.getmember("vscode-server-linux-x64/product.json")
        if not member.isfile() or not 0 < member.size <= 4 * 1024 * 1024:
            raise Refused("bundle_product_member_refused")
        with archive.extractfile(member) as stream:
            product = stream.read(member.size + 1)
        if len(product) != member.size:
            raise Refused("bundle_product_member_refused")
    product_value = runtime._json(product)
    if product_value.get("commit") != runtime.PIN:
        raise Refused("bundle_product_commit_refused")
    with tarfile.open(source_archive, "r:gz") as archive:
        member = archive.getmember("vscode-" + runtime.PIN + "/package.json")
        if not member.isfile() or not isinstance(member.mtime, (int, float)) or member.mtime <= 0:
            raise Refused("bundle_source_date_refused")
        build_date = datetime.fromtimestamp(member.mtime, timezone.utc).isoformat()
    # Replace only product metadata in the new disposable source tree. Preserve its old hash.
    original_product = runtime._read(source / "product.json", 4 * 1024 * 1024)
    replacement = source / "product.bundle-input.json"
    runtime._write(replacement, product)
    os.replace(replacement, source / "product.json")
    date_dir = source / "out-build"
    date_dir.mkdir(exist_ok=False)
    runtime._write(date_dir / "date", build_date.encode())
    inputs = {"schema": "ghcp-server-bundle-inputs-v1", "upstream_commit": runtime.PIN,
              "patch_sha256": runtime.PATCH_SHA256, "source_archive_sha256": runtime.SOURCE_SHA256,
              "server_archive_sha256": server_pin["sha256"], "vendor_product_sha256": runtime._sha(product),
              "original_source_product_sha256": runtime._sha(original_product), "build_date": build_date,
              "command": COMMAND, "execution_allowed": False}
    runtime._write(output, runtime._encoded(inputs) + b"\n")
    return inputs


def validate_manifest(value):
    patch_set = runtime.verify_patch_set()
    if (type(value) is not dict or set(value) != {
            "schema", "evidence_kind", "upstream_commit", "patch_sha256", "patch_set", "build_inputs_sha256",
            "build_inputs", "build_receipt", "build_receipt_sha256", "files", "file_count", "total_bytes",
            "file_manifest_sha256", "entrypoint", "execution_allowed", "runtime_load_status", "model_calls"}
            or value["schema"] != "ghcp-server-bundle-manifest-v1"
            or value["evidence_kind"] != "source-build-no-execution"
            or value["upstream_commit"] != runtime.PIN or value["patch_sha256"] != runtime.PATCH_SHA256
            or value["patch_set"] != patch_set or value["execution_allowed"] is not False
            or value["runtime_load_status"] != "not_executed" or type(value["model_calls"]) is not int
            or value["model_calls"] != 0):
        raise Refused("bundle_manifest_contract_refused")
    receipt = runtime.validate_build_receipt(value["build_receipt"])
    if (value["build_receipt_sha256"] != runtime._sha(runtime._encoded(receipt) + b"\n")
            or value["build_inputs_sha256"] != runtime._sha(runtime._encoded(value["build_inputs"]) + b"\n")):
        raise Refused("bundle_manifest_evidence_hash_refused")
    inputs = value["build_inputs"]
    if (type(inputs) is not dict or set(inputs) != {"schema", "upstream_commit", "patch_sha256", "source_archive_sha256",
            "server_archive_sha256", "vendor_product_sha256", "original_source_product_sha256", "build_date", "command", "execution_allowed"}
            or inputs.get("schema") != "ghcp-server-bundle-inputs-v1"
            or not all(runtime._hex(inputs.get(key)) for key in ("vendor_product_sha256", "original_source_product_sha256"))
            or type(inputs.get("build_date")) is not str or not inputs["build_date"]
            or inputs.get("patch_sha256") != runtime.PATCH_SHA256 or inputs.get("upstream_commit") != runtime.PIN
            or inputs.get("source_archive_sha256") != runtime.SOURCE_SHA256
            or inputs.get("server_archive_sha256") != base_manifest()["artifacts"]["server"]["sha256"]
            or inputs.get("command") != COMMAND or inputs.get("execution_allowed") is not False):
        raise Refused("bundle_manifest_inputs_refused")
    files = value["files"]
    if type(files) is not list or not 1 <= len(files) <= 50000:
        raise Refused("bundle_manifest_files_refused")
    paths = []
    for row in files:
        if (type(row) is not dict or set(row) != {"path", "sha256", "bytes"}
                or type(row["path"]) is not str or not row["path"] or "\\" in row["path"]
                or any(part in ("", ".", "..") for part in row["path"].split("/"))
                or not runtime._hex(row["sha256"]) or type(row["bytes"]) is not int
                or not 0 <= row["bytes"] <= MAX_OUTPUT_FILE):
            raise Refused("bundle_manifest_files_refused")
        paths.append(row["path"])
    if (paths != sorted(set(paths)) or type(value["file_count"]) is not int or value["file_count"] != len(files)
            or type(value["total_bytes"]) is not int or value["total_bytes"] != sum(row["bytes"] for row in files)
            or value["file_manifest_sha256"] != runtime._sha(runtime._encoded(files))):
        raise Refused("bundle_manifest_totals_refused")
    entry = [row for row in files if row["path"] == ENTRY]
    if (len(entry) != 1 or entry[0] != value["entrypoint"] or entry[0]["bytes"] <= 0
            or entry[0]["sha256"] != receipt["runtime_bundle_sha256"]):
        raise Refused("bundle_manifest_entry_refused")
    return value


def record_manifest(source, bundle_directory, inputs_path, receipt_path, output):
    """Hash build files as data; neither import them nor create a staged runtime."""
    source, bundle_directory = runtime._safe_path(source), runtime._safe_path(bundle_directory)
    inputs = runtime._json(runtime._read(inputs_path))
    if (runtime._sha(runtime._read(source / "product.json", 4 * 1024 * 1024)) != inputs.get("vendor_product_sha256")
            or runtime._read(source / "out-build/date").decode() != inputs.get("build_date")
            or runtime._read(bundle_directory / "date").decode() != inputs.get("build_date")):
        raise Refused("bundle_build_inputs_drift")
    receipt = runtime.build_receipt(source, bundle_directory / ENTRY, receipt_path)
    rows = []
    for path in sorted(bundle_directory.rglob("*")):
        if path.is_symlink():
            raise Refused("bundle_output_symlink_refused")
        if path.is_dir():
            continue
        runtime._safe_path(path)
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not runtime.stat.S_ISREG(info.st_mode) or info.st_size > MAX_OUTPUT_FILE:
                raise Refused("bundle_output_file_refused")
            raw = stream.read(MAX_OUTPUT_FILE + 1)
        if len(raw) != info.st_size:
            raise Refused("bundle_output_file_refused")
        rows.append({"path": path.relative_to(bundle_directory).as_posix(), "sha256": runtime._sha(raw), "bytes": len(raw)})
    rows.sort(key=lambda row: row["path"])
    value = {"schema": "ghcp-server-bundle-manifest-v1", "evidence_kind": "source-build-no-execution",
             "upstream_commit": runtime.PIN, "patch_sha256": runtime.PATCH_SHA256,
             "patch_set": runtime.verify_patch_set(), "build_inputs": inputs,
             "build_inputs_sha256": runtime._sha(runtime._read(inputs_path)), "build_receipt": receipt,
             "build_receipt_sha256": runtime._sha(runtime._read(receipt_path)), "files": rows,
             "file_count": len(rows), "total_bytes": sum(row["bytes"] for row in rows),
             "file_manifest_sha256": runtime._sha(runtime._encoded(rows)),
             "entrypoint": next((row for row in rows if row["path"] == ENTRY), None),
             "execution_allowed": False, "runtime_load_status": "not_executed", "model_calls": 0}
    validate_manifest(value)
    runtime._write(output, runtime._encoded(value) + b"\n")
    validate_manifest(runtime._json(runtime._read(output, MAX_MANIFEST)))
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    prepare = modes.add_parser("prepare")
    prepare.add_argument("--source", type=Path, required=True)
    prepare.add_argument("--source-archive", type=Path, required=True)
    prepare.add_argument("--server-archive", type=Path, required=True)
    prepare.add_argument("--output", type=Path, required=True)
    record = modes.add_parser("record")
    record.add_argument("--source", type=Path, required=True)
    record.add_argument("--bundle-directory", type=Path, required=True)
    record.add_argument("--inputs", type=Path, required=True)
    record.add_argument("--receipt", type=Path, required=True)
    record.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.mode == "prepare":
        value = prepare_inputs(args.source, args.source_archive, args.server_archive, args.output)
    else:
        value = record_manifest(args.source, args.bundle_directory, args.inputs, args.receipt, args.output)
    print(runtime._encoded({key: value[key] for key in ("schema", "patch_sha256", "execution_allowed")}
                          | ({"entrypoint": value["entrypoint"], "file_count": value["file_count"],
                              "total_bytes": value["total_bytes"]} if args.mode == "record" else {})).decode())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
