"""Local, deterministic transport of four pinned originals; never a launch.

The archive contains only the original parquet, two declared references, the
canonical Step0 manifest and a small logical-role manifest. No network transfer
is implemented. An importer requires an externally supplied archive SHA256.
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import os
from pathlib import Path
import re
import stat
import sys
import tarfile
from typing import Any

import yaml

from codex_budget_pilot import InputSources, LocalTransport
from core.inference_manifest import _assert_no_symlink_ancestors
from core.reference_integrity import validate_reference_relative_path
from gpt54_codex_input_capture import DATASET_ROOT, _write_no_clobber
from gpt54_comparison_preflight import ROOT, _canonical_json, compile_grading_plan, load_plan
from gpt54_prepared_input_attestation import _identity, _json_object, _same
from gpt54_run_config_bundle import _held_parents, _path
from gpt54_run_input_bundle import PARQUET_PATH, STEP0_MANIFEST_PATH, _publication_parents
from gpt54_v2_grading_input import _read_bytes

MANIFEST = "input-bundle-manifest.json"
READY = "input-bundle-ready.json"
PARQUET = "original.parquet"
STEP0 = "step0-manifest.json"
REFERENCES = "reference-only"
PARQUET_PIN = {"size": 1913489, "sha256": "f8422fab9b21d90c0ee5f0659842ab666d418cb8940842918f9f4b0df7ae0202"}
STEP0_PIN = {"size": 218405, "sha256": "463fc119841dbe67e427c372da93ff55972139377aa03194764b57d87004c512"}
MAX_MANIFEST_BYTES = 8192
MAX_REFERENCE_BYTES = 16 * 1024 * 1024
MAX_BUNDLE_BYTES = 2 * MAX_REFERENCE_BYTES + PARQUET_PIN["size"] + STEP0_PIN["size"] + 65536
LOG = logging.getLogger(__name__)


class InputBundleRefused(ValueError):
    """A closed refusal code; partial reservations must not be adopted."""


def _registered() -> tuple[Any, str, dict[str, dict]]:
    """Read the genuine registered contract, without inputs, auth or execution."""
    from core.repo_bootstrapper import CANONICAL_MANIFEST_SHA256_BY_POLICY

    plan = compile_grading_plan(load_plan())
    dataset = json.loads(plan.dispatch.controls_json)["dataset"]
    _same("registered original parquet", dataset["parquet_sha256"], PARQUET_PIN["sha256"])
    _same("registered canonical Step0", CANONICAL_MANIFEST_SHA256_BY_POLICY["deliverable_only"], STEP0_PIN["sha256"])
    references = dict(dataset["input_file_versions"])
    _same("registered dataset version", references.pop(dataset["repo_id"] + "@" + dataset["revision"]), PARQUET_PIN["sha256"])
    if len(references) != 2:
        raise InputBundleRefused("exact_two_registered_references_required")
    specs = {PARQUET: {"role": "normalized_original_parquet", **PARQUET_PIN}}
    for name, digest in sorted(references.items()):
        validate_reference_relative_path(name)
        if not name.startswith("reference_files/"):
            raise InputBundleRefused("registered_reference_role_refused")
        specs[REFERENCES + "/" + name] = {"role": "declared_reference", "sha256": digest, "size": None}
    specs[STEP0] = {"role": "canonical_schema4_deliverable_only_step0", **STEP0_PIN}
    return plan, dataset["revision"], specs


def _safe_path(path: Path) -> Path:
    if ".." in path.parts:
        raise InputBundleRefused("parent_traversal_refused")
    return _assert_no_symlink_ancestors(Path(os.path.abspath(path)))


def _destination(path: Path, sources: tuple[Path, ...]) -> tuple[Path, Path]:
    path = _safe_path(path)
    if path.is_relative_to(ROOT) or ROOT.is_relative_to(path):
        raise InputBundleRefused("output_overlaps_source_checkout")
    for source in sources:
        source = _safe_path(source)
        if path.is_relative_to(source) or source.is_relative_to(path):
            raise InputBundleRefused("output_overlaps_input")
    reservation = path.with_name(path.name + ".input-bundle-reserved.json")
    if os.path.lexists(path) or os.path.lexists(reservation):
        raise InputBundleRefused("destination_or_partial_reservation_exists")
    if not path.parent.is_dir():
        raise InputBundleRefused("existing_output_parent_required")
    return path, reservation


def _read_originals(plan: Any, sources: InputSources, transport: LocalTransport) -> dict[str, bytes]:
    """Reuse source_snapshot, exact references and the real canonical Step0 reader."""
    verified = transport.inputs(plan, sources)
    expected = {PARQUET_PATH, STEP0_MANIFEST_PATH, *(
        DATASET_ROOT + "/" + name for name in verified.snapshot.references
    )}
    if set(verified.files) != expected or len(expected) != 4:
        raise InputBundleRefused("exact_four_original_files_required")
    return {PARQUET: verified.files[PARQUET_PATH], **{
        REFERENCES + "/" + name: verified.files[DATASET_ROOT + "/" + name]
        for name in sorted(verified.snapshot.references)
    }, STEP0: verified.files[STEP0_MANIFEST_PATH]}


def _manifest(revision: str, specs: dict[str, dict], files: dict[str, bytes]) -> dict:
    if list(files) != list(specs):
        raise InputBundleRefused("original_role_set_or_order_mismatch")
    members = []
    for name, spec in specs.items():
        data = files[name]
        identity = _identity(data)
        if (identity["sha256"] != spec["sha256"]
                or (spec["size"] is not None and identity["size"] != spec["size"])
                or (spec["size"] is None and identity["size"] > MAX_REFERENCE_BYTES)):
            raise InputBundleRefused("original_size_or_digest_mismatch")
        members.append({"path": name, "role": spec["role"], **identity})
    return {"dataset_revision": revision, "files": members}


def _header(name: str, size: int) -> tarfile.TarInfo:
    member = tarfile.TarInfo(name)
    member.size, member.mode = size, 0o600
    member.mtime = member.uid = member.gid = 0
    member.uname = member.gname = ""
    return member


def _archive(files: dict[str, bytes]) -> bytes:
    """Fixed USTAR headers, order and zero padding; no host metadata/compression."""
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w", format=tarfile.USTAR_FORMAT, encoding="utf-8") as archive:
        for name, data in files.items():
            archive.addfile(_header(name, len(data)), io.BytesIO(data))
    return stream.getvalue()


def _unpack(data: bytes, revision: str, specs: dict[str, dict]) -> tuple[dict, dict[str, bytes]]:
    """Inspect bounded headers before payloads; never extract or follow a link.

    Requiring the exact canonical serialization also refuses hidden PAX/GNU
    extensions, duplicate/extra members, nonzero padding and truncated trailers.
    """
    if len(data) > MAX_BUNDLE_BYTES:
        raise InputBundleRefused("bundle_size_limit_exceeded")
    files, offset = {}, 0
    for name in (MANIFEST, *specs):
        header = data[offset:offset + tarfile.BLOCKSIZE]
        member = tarfile.TarInfo.frombuf(header, encoding="utf-8", errors="strict")
        limit = MAX_MANIFEST_BYTES if name == MANIFEST else specs[name]["size"]
        limit = MAX_REFERENCE_BYTES if limit is None else limit
        if member.name != name or member.type != tarfile.REGTYPE or member.linkname:
            raise InputBundleRefused("archive_member_name_type_or_order_refused")
        if type(member.size) is not int or not 0 <= member.size <= limit:
            raise InputBundleRefused("archive_member_size_refused")
        if header != _header(name, member.size).tobuf(format=tarfile.USTAR_FORMAT, encoding="utf-8", errors="strict"):
            raise InputBundleRefused("noncanonical_archive_header")
        start, end = offset + tarfile.BLOCKSIZE, offset + tarfile.BLOCKSIZE + member.size
        payload = data[start:end]
        if len(payload) != member.size:
            raise InputBundleRefused("truncated_archive_member")
        files[name] = payload
        offset = start + ((member.size + tarfile.BLOCKSIZE - 1) // tarfile.BLOCKSIZE) * tarfile.BLOCKSIZE
    if data != _archive(files):
        raise InputBundleRefused("archive_padding_count_or_trailer_refused")
    manifest_bytes = files.pop(MANIFEST)
    manifest = _json_object(manifest_bytes)
    expected = _manifest(revision, specs, files)
    if manifest_bytes != _canonical_json(expected).encode("utf-8") or manifest != expected:
        raise InputBundleRefused("logical_manifest_mismatch")
    return manifest, files


def _sensitive_step0_metadata(data: bytes) -> bool:
    """Conservative structured-field/path screen, not a publication clearance."""
    def sensitive(value: Any) -> bool:
        if isinstance(value, dict):
            return any(re.search(r"(^|_)(password|credential|token|secret|tenant|subscription|endpoint|account)(_|$)", key, re.I)
                       or sensitive(item) for key, item in value.items())
        if isinstance(value, list):
            return any(sensitive(item) for item in value)
        return isinstance(value, str) and (value.startswith(("/", "~", "\\\\"))
                                           or re.match(r"^[A-Za-z]:[\\/]", value) is not None)
    return bool(sensitive(_json_object(data)))


def _report(archive: bytes, manifest: dict, files: dict[str, bytes]) -> dict:
    return {"bundle": _identity(archive), "members": [
        {"path": MANIFEST, "role": "logical_role_manifest", **_identity(_canonical_json(manifest).encode("utf-8"))},
        *manifest["files"],
    ], "canonical_step0_publication_sensitive_fields_found": _sensitive_step0_metadata(files[STEP0])}


def produce(*, sources: InputSources, output: Path, transport: LocalTransport) -> dict:
    """Verify approved originals, then reserve and publish one absent archive."""
    plan, revision, specs = _registered()
    inputs = (sources.parquet, sources.references, sources.manifest)
    output, reservation = _destination(output, inputs)
    files = _read_originals(plan, sources, transport)
    manifest = _manifest(revision, specs, files)
    manifest_bytes = _canonical_json(manifest).encode("utf-8")
    if len(manifest_bytes) > MAX_MANIFEST_BYTES:
        raise InputBundleRefused("logical_manifest_size_limit_exceeded")
    archive = _archive({MANIFEST: manifest_bytes, **files})
    _unpack(archive, revision, specs)
    with _held_parents(output.parent, (output.name, reservation.name)) as check:
        _destination(output, inputs)
        _write_no_clobber(reservation, _canonical_json({"operation": "produce", "bundle": _identity(archive)}).encode())
        check()
        _write_no_clobber(output, archive)
        check()
        _read_bytes(output, **_identity(archive))
    return _report(archive, manifest, files)


def import_bundle(*, bundle: Path, expected_sha256: str, output: Path, transport: LocalTransport) -> dict:
    """Validate an external trust anchor and all members before private publication."""
    if re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None:
        raise InputBundleRefused("external_bundle_sha256_required")
    bundle = _safe_path(bundle)
    metadata = bundle.lstat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > MAX_BUNDLE_BYTES:
        raise InputBundleRefused("bundle_type_or_size_refused")
    archive = _read_bytes(bundle, sha256=expected_sha256, size=metadata.st_size)
    plan, revision, specs = _registered()
    manifest, files = _unpack(archive, revision, specs)
    output, reservation = _destination(output, (bundle,))
    # A sibling reservation survives even failure of the first directory write.
    # No retry/resume flag adopts a partial tree; a new absent target is required.
    with _publication_parents(output.parent) as (check_parent, mkdir_root, _):
        _destination(output, (bundle,))
        _write_no_clobber(reservation, _canonical_json({"operation": "import", "bundle": _identity(archive)}).encode())
        check_parent()
        mkdir_root(output)
        with _publication_parents(output) as (check, mkdir, _):
            directories = {parent for name in files for parent in _path(output, name).parents if parent.is_relative_to(output) and parent != output}
            for directory in sorted(directories, key=lambda path: (len(path.parts), path.as_posix())):
                mkdir(directory)
            for name, payload in files.items():
                check_parent()
                check()
                _write_no_clobber(_path(output, name), payload)
            _write_no_clobber(output / MANIFEST, _canonical_json(manifest).encode("utf-8"))
            installed = _read_originals(plan, InputSources(output / PARQUET, output / REFERENCES, output / STEP0), transport)
            _same("installed original identities", _manifest(revision, specs, installed), manifest)
            check_parent()
            check()
            _write_no_clobber(output / READY, _canonical_json({"bundle": _identity(archive), "manifest": _identity(_canonical_json(manifest).encode())}).encode())
    return _report(archive, manifest, files)


def main(argv: list[str] | None = None, *, _test_transport: LocalTransport | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    producer = commands.add_parser("produce", help="Verify and package four local originals; no transfer")
    producer.add_argument("--dataset-parquet", required=True, type=Path)
    producer.add_argument("--reference-root", required=True, type=Path)
    producer.add_argument("--step0-manifest", required=True, type=Path)
    producer.add_argument("--out", required=True, type=Path)
    importer = commands.add_parser("import", help="Import an externally SHA-bound local bundle into a new private root")
    importer.add_argument("--bundle", required=True, type=Path)
    importer.add_argument("--expected-sha256", required=True)
    importer.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        transport = _test_transport or LocalTransport()
        if args.command == "produce":
            report = produce(sources=InputSources(args.dataset_parquet, args.reference_root, args.step0_manifest),
                             output=args.out, transport=transport)
        else:
            report = import_bundle(bundle=args.bundle, expected_sha256=args.expected_sha256, output=args.out, transport=transport)
        sys.stdout.write(_canonical_json(report) + "\n")
        return 0
    except (OSError, ValueError, TypeError, KeyError, AttributeError, StopIteration, tarfile.TarError, yaml.YAMLError) as error:
        LOG.error("Input bundle refused: %s", str(error) if isinstance(error, InputBundleRefused) else "original_or_archive_verification_failed")
        return 2


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    raise SystemExit(main())
