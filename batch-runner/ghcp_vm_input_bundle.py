"""Publish and verify local GHCP pilot inputs, never VM/model consumption.

The whole reviewed parquet is copied unchanged. Only the fixed five-task
reference closure is read from the caller's reference root. This module does
not download inputs, prepare a runtime, authenticate, grade or launch anything.
Failed publications retain their reservation and partial destination; neither
can be repaired, adopted or overwritten by another invocation.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import stat
import sys
import tempfile
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterator

import ghcp_vm_gate_preflight as gate
from core.agentic_v2_oci import _read_regular_path, canonical_json, sha256_bytes
from core.reference_integrity import (
    _reject_symlink_components,
    validate_reference_record,
    validate_reference_relative_path,
)
from core.source_identity import (
    SOURCE_PROJECTION_FIELDS,
    ordered_source_projection_sha256,
    source_task_projection,
    source_task_projection_sha256,
)

PARQUET_PATH = "data/train-00000-of-00001.parquet"
INSTRUCTIONS_PATH = "developer-instructions.txt"
MANIFEST_PATH = "ghcp-vm-input-manifest.json"
READY_PATH = "ghcp-vm-input-bundle-ready.json"
RESERVATION_SUFFIX = ".ghcp-vm-input-bundle-reservation.json"
BOUNDARY = "local_input_materialization_not_vm_or_model_consumption"
REFUSAL = "ghcp_input_bundle_refused"
MAX_INPUT_BYTES = 1024 * 1024 * 1024
MAX_DOCUMENT_BYTES = 8 * 1024 * 1024


class GHCPInputBundleRefused(ValueError):
    """Expose one static code, never caller paths, input text or error details."""

    def __init__(self) -> None:
        super().__init__(REFUSAL)


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise GHCPInputBundleRefused()


@dataclass(frozen=True)
class GHCPInputBundle:
    """Immutable ready/manifest bytes and the exact files preceding ready."""

    document_json: str
    manifest_json: str
    files: tuple[tuple[str, bytes], ...]

    def canonical_bytes(self) -> bytes:
        return self.document_json.encode("utf-8")

    @property
    def sha256(self) -> str:
        return sha256_bytes(self.canonical_bytes())

    def as_dict(self) -> dict[str, Any]:
        return json.loads(self.document_json)


@dataclass(frozen=True)
class _ReviewedInputs:
    plan_json: str
    report_json: str
    sources: tuple[tuple[str, bytes], ...]
    instructions: bytes


@dataclass(frozen=True)
class _ReadFile:
    path: Path
    data: bytes
    stamp: tuple[int, ...]
    maximum: int


def _require(condition: bool) -> None:
    if not condition:
        raise GHCPInputBundleRefused()


def _identity(data: bytes) -> dict[str, Any]:
    return {"size": len(data), "sha256": sha256_bytes(data)}


def _false_flags() -> dict[str, bool]:
    return {name: False for name in gate.FALSE_FLAGS}


def _absolute(path: Path) -> Path:
    candidate = Path(path)
    _require(".." not in candidate.parts and "\x00" not in str(candidate))
    return Path(os.path.abspath(candidate))


def _path(root: Path, role: str) -> Path:
    _require(type(role) is str and "\\" not in role and "\x00" not in role)
    relative = PurePosixPath(role)
    _require(bool(relative.parts) and not relative.is_absolute()
             and relative.as_posix() == role and ".." not in relative.parts)
    return root.joinpath(*relative.parts)


def _root(path: Path) -> Path:
    root = _absolute(path)
    _reject_symlink_components(root)
    _require(stat.S_ISDIR(root.lstat().st_mode))
    return root


def _destination(path: Path) -> tuple[Path, Path]:
    root = _absolute(path)
    _require(bool(root.name))
    _root(root.parent)
    return root, root.with_name(root.name + RESERVATION_SUFFIX)


def _overlap(first: Path, second: Path) -> bool:
    return first.is_relative_to(second) or second.is_relative_to(first)


def _directory_flags() -> int:
    required = ("O_DIRECTORY", "O_NOFOLLOW", "O_CLOEXEC", "O_NONBLOCK")
    _require(all(type(getattr(os, name, None)) is int and getattr(os, name) > 0
                 for name in required))
    return os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK


@contextmanager
def _held_parents(root: Path, roles: tuple[str, ...]) -> Iterator[Callable[[], None]]:
    """Hold existing ancestors, without enumerating unrelated source members."""
    parents = {root, *root.parents}
    for role in roles:
        parent = _path(root, role).parent
        while parent != root:
            parents.add(parent)
            parent = parent.parent
    with ExitStack() as stack:
        opened = []
        for parent in sorted(parents, key=lambda item: (len(item.parts), str(item))):
            _reject_symlink_components(parent)
            descriptor = os.open(parent, _directory_flags())
            stack.callback(os.close, descriptor)
            metadata = os.fstat(descriptor)
            opened.append((parent, descriptor, metadata.st_dev, metadata.st_ino))

        def check() -> None:
            for parent, descriptor, device, inode in opened:
                _reject_symlink_components(parent)
                current, held = parent.lstat(), os.fstat(descriptor)
                _require(stat.S_ISDIR(current.st_mode)
                         and (current.st_dev, current.st_ino) == (device, inode)
                         and (held.st_dev, held.st_ino) == (device, inode))

        check()
        yield check


@contextmanager
def _publication_parents(root: Path) -> Iterator[
    tuple[Callable[[], None], Callable[[Path], None], Callable[[Path], int]]
]:
    """Hold each exclusively created output directory through ready publication."""
    with ExitStack() as stack:
        descriptors: dict[Path, int] = {}

        def hold(path: Path, parent: int | None = None) -> None:
            _reject_symlink_components(path)
            descriptor = os.open(path if parent is None else path.name,
                                 _directory_flags(), dir_fd=parent)
            stack.callback(os.close, descriptor)
            descriptors[path] = descriptor

        def check() -> None:
            for path, descriptor in descriptors.items():
                _reject_symlink_components(path)
                current, held = path.lstat(), os.fstat(descriptor)
                _require(stat.S_ISDIR(current.st_mode)
                         and (current.st_dev, current.st_ino) == (held.st_dev, held.st_ino))

        def mkdir(path: Path) -> None:
            check()
            parent = descriptors[path.parent]
            os.mkdir(path.name, mode=0o700, dir_fd=parent)
            hold(path, parent)
            check()

        def directory_fd(path: Path) -> int:
            check()
            _require(path in descriptors)
            return descriptors[path]

        hold(root)
        check()
        yield check, mkdir, directory_fd


def _write_no_clobber(path: Path, data: bytes, *, parent_fd: int) -> None:
    """Atomically publish through the caller-held parent, never reopen its path.

    Only the helper's private temporary link is removed. A published target,
    reservation or partial bundle is never removed, repaired or adopted.
    The descriptor remains owned by the caller on success and refusal.
    """
    _require(type(parent_fd) is int and parent_fd >= 0)
    opened = os.fstat(parent_fd)
    _require(stat.S_ISDIR(opened.st_mode))

    def check_parent() -> None:
        _reject_symlink_components(path.parent)
        current, held = path.parent.lstat(), os.fstat(parent_fd)
        _require(stat.S_ISDIR(current.st_mode) and stat.S_ISDIR(held.st_mode)
                 and (current.st_dev, current.st_ino) == (opened.st_dev, opened.st_ino)
                 and (held.st_dev, held.st_ino) == (opened.st_dev, opened.st_ino))

    temporary: str | None = None
    try:
        check_parent()
        handle, name = tempfile.mkstemp(prefix=".ghcp-input-", dir=f"/proc/self/fd/{parent_fd}")
        temporary = Path(name).name
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        check_parent()
        os.link(temporary, path.name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd, follow_symlinks=False)
        check_parent()
    finally:
        if temporary is not None:
            os.unlink(temporary, dir_fd=parent_fd)
    check_parent()


def _stamp(metadata: os.stat_result) -> tuple[int, ...]:
    _require(stat.S_ISREG(metadata.st_mode) and metadata.st_nlink == 1)
    return (metadata.st_dev, metadata.st_ino, metadata.st_size, metadata.st_mtime_ns,
            metadata.st_ctime_ns, metadata.st_nlink, metadata.st_mode)


def _read_file(path: Path, maximum: int, *, digest: str | None = None) -> _ReadFile:
    _reject_symlink_components(path)
    before = _stamp(path.lstat())
    data = _read_regular_path(path, maximum)
    _reject_symlink_components(path)
    _require(_stamp(path.lstat()) == before and len(data) == before[2])
    if digest is not None:
        validate_reference_record({"sha256": digest, "size": len(data)})
        _require(sha256_bytes(data) == digest)
    return _ReadFile(path, data, before, maximum)


def _check_reads(reads: tuple[_ReadFile, ...]) -> None:
    for read in reads:
        _require(_read_file(read.path, read.maximum) == read)


def _validated_plan(plan: dict[str, Any], reviewed_plan_sha256: str) -> _ReviewedInputs:
    """Re-read the real gate and all source pins, never an asserted verdict."""
    _require(type(plan) is dict and type(reviewed_plan_sha256) is str)
    validate_reference_record({"sha256": reviewed_plan_sha256, "size": 0})
    encoded = canonical_json(plan)
    _require(sha256_bytes(encoded) == reviewed_plan_sha256)
    frozen = json.loads(encoded)
    report = gate.inspect_plan(frozen)
    _require(report["configuration_valid"] is True
             and report["plan_sha256"] == reviewed_plan_sha256
             and report["condition_id"] == gate.CONDITION_ID
             and all(report[name] is False for name in gate.FALSE_FLAGS))
    sources = gate._sources(frozen)
    historical = gate._yaml(sources[gate.HISTORICAL_PLAN])
    instructions = historical["developer_instructions"]
    _require(type(instructions) is str and bool(instructions))
    data = instructions.encode("utf-8")
    _require(sha256_bytes(data) == report["developer_instructions_sha256"]
             and canonical_json(plan) == encoded)
    return _ReviewedInputs(encoded.decode("utf-8"), canonical_json(report).decode("utf-8"),
                           tuple(sorted(sources.items())), data)


def _reference_versions(reviewed: _ReviewedInputs) -> dict[str, str]:
    plan, report = json.loads(reviewed.plan_json), json.loads(reviewed.report_json)
    versions = dict(report["input_file_versions"])
    dataset = plan["dataset"]
    _require(versions.pop(dataset["repo_id"] + "@" + dataset["revision"]) == dataset["parquet_sha256"])
    roles = [role for task in report["tasks"] for role in task["reference_file_paths"]]
    _require(set(versions) == set(roles))
    for role, digest in versions.items():
        _require(len(validate_reference_relative_path(role).parts) > 1)
        validate_reference_record({"sha256": digest, "size": 0})
    return versions


def _json_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        _require(key not in result)
        result[key] = value
    return result


def _dataset_tasks(data: bytes, report: dict[str, Any], references: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Project selected rows from held bytes with the canonical source rules."""
    import pyarrow.parquet as parquet

    ids = report["task_ids"]
    _require(len(ids) == len(set(ids)) == 5
             and ids == [task["task_id"] for task in report["tasks"]])
    rows = parquet.read_table(
        io.BytesIO(data), columns=[*SOURCE_PROJECTION_FIELDS, "deliverable_files"],
        filters=[("task_id", "in", ids)], use_threads=False,
    ).to_pylist()
    _require(sorted(row["task_id"] for row in rows) == sorted(ids))
    by_id = {row["task_id"]: row for row in rows}
    tasks = []
    for registered in report["tasks"]:
        row = by_id[registered["task_id"]]
        projection = source_task_projection(**{key: row[key] for key in SOURCE_PROJECTION_FIELDS})
        canonical_json(json.loads(projection["rubric_json"], object_pairs_hook=_json_pairs))
        prompt_digest = sha256_bytes(projection["prompt"].encode("utf-8"))
        roles = projection["reference_files"]
        _require(prompt_digest == registered["prompt_sha256"]
                 and roles == registered["reference_file_paths"] and len(roles) == len(set(roles)))
        for role in roles:
            validate_reference_relative_path(role)
        deliverables = row["deliverable_files"]
        if deliverables is None:
            deliverables = []
        elif type(deliverables) is str:
            deliverables = [deliverables] if deliverables else []
        _require(type(deliverables) is list and all(type(name) is str for name in deliverables))
        extensions = sorted({os.path.splitext(name)[1].lower() for name in deliverables})
        _require(extensions == registered["deliverable_file_extensions"])
        tasks.append({
            "task_id": registered["task_id"], "prompt_sha256": prompt_digest,
            "source_projection_sha256": source_task_projection_sha256(**projection),
            "text_bytes": {key: _identity(projection[key].encode("utf-8"))
                           for key in ("prompt", "rubric_json", "rubric_pretty")},
            "reference_files": [{"path": role, **references[role]} for role in roles],
            "deliverable_file_extensions": registered["deliverable_file_extensions"],
            "deliverable_formats": registered["deliverable_formats"],
            "deliverable_file_count": len(deliverables),
            "deliverable_metadata_sha256": sha256_bytes(canonical_json(deliverables)),
        })
    return tasks


def _snapshot(reviewed: _ReviewedInputs, parquet: Path, references: Path) -> tuple[GHCPInputBundle, tuple[_ReadFile, ...]]:
    plan, report = json.loads(reviewed.plan_json), json.loads(reviewed.report_json)
    dataset = _read_file(parquet, MAX_INPUT_BYTES, digest=plan["dataset"]["parquet_sha256"])
    versions = _reference_versions(reviewed)
    read_references = {role: _read_file(_path(references, role), MAX_INPUT_BYTES, digest=digest)
                       for role, digest in sorted(versions.items())}
    identities = {role: _identity(read.data) for role, read in read_references.items()}
    tasks = _dataset_tasks(dataset.data, report, identities)
    manifest = {
        "manifest_version": "ghcp-vm-input-manifest-v1", "condition_id": gate.CONDITION_ID,
        "reviewed_plan_sha256": report["plan_sha256"], "evidence_boundary": BOUNDARY,
        "source_pins": plan["source_pins"],
        "source_identity": {role: _identity(data) for role, data in reviewed.sources},
        "dataset": {"revision": plan["dataset"]["revision"],
                    "catalog_sha256": plan["dataset"]["catalog_sha256"],
                    "parquet_sha256": plan["dataset"]["parquet_sha256"],
                    "parquet": {"path": PARQUET_PATH, **_identity(dataset.data)}},
        "task_ids": report["task_ids"], "task_count": 5, "tasks": tasks,
        "ordered_source_projection_sha256": ordered_source_projection_sha256(
            task["source_projection_sha256"] for task in tasks),
        "developer_instructions": {"path": INSTRUCTIONS_PATH, **_identity(reviewed.instructions)},
        "grading": plan["grading"], "results": plan["results"], **_false_flags(),
    }
    manifest_bytes = canonical_json(manifest)
    files = ((PARQUET_PATH, dataset.data),
             *((role, read.data) for role, read in read_references.items()),
             (INSTRUCTIONS_PATH, reviewed.instructions), (MANIFEST_PATH, manifest_bytes))
    ready = {
        "bundle_version": "ghcp-vm-input-bundle-v1", "condition_id": gate.CONDITION_ID,
        "reviewed_plan_sha256": report["plan_sha256"], "evidence_boundary": BOUNDARY,
        "input_bundle_complete": True, "task_ids": report["task_ids"],
        "manifest": {"path": MANIFEST_PATH, **_identity(manifest_bytes)},
        "files": {role: _identity(data) for role, data in files}, **_false_flags(),
    }
    bundle = GHCPInputBundle(canonical_json(ready).decode("utf-8"), manifest_bytes.decode("utf-8"), files)
    return bundle, (dataset, *read_references.values())


def _reservation(bundle: GHCPInputBundle) -> bytes:
    return canonical_json({
        "reservation_version": "ghcp-vm-input-reservation-v1", "condition_id": gate.CONDITION_ID,
        "reviewed_plan_sha256": bundle.as_dict()["reviewed_plan_sha256"],
        "ready_path": READY_PATH, "intended_ready": _identity(bundle.canonical_bytes()),
    })


def _directories(files: tuple[tuple[str, bytes], ...]) -> tuple[str, ...]:
    names = {parent.as_posix() for role, _ in files for parent in PurePosixPath(role).parents
             if parent != PurePosixPath(".")}
    return tuple(sorted(names, key=lambda role: (len(PurePosixPath(role).parts), role)))


def _members(root: Path, bundle: GHCPInputBundle, *, published: bool) -> None:
    """Check a closed output tree, without following unknown member directories."""
    files = dict(bundle.files)
    if published:
        files[READY_PATH] = bundle.canonical_bytes()
    children: dict[str, set[str]] = {".": set()}
    for role in _directories(bundle.files):
        path = PurePosixPath(role)
        children.setdefault(path.parent.as_posix(), set()).add(path.name)
        children.setdefault(role, set())
    for role in files:
        path = PurePosixPath(role)
        children[path.parent.as_posix()].add(path.name)
    for role, expected in children.items():
        directory = root if role == "." else _path(root, role)
        _root(directory)
        _require(set(os.listdir(directory)) == expected)
    for role, expected in files.items():
        maximum = MAX_INPUT_BYTES if role == PARQUET_PATH or role.startswith("reference_files/") else MAX_DOCUMENT_BYTES
        _require(_read_file(_path(root, role), maximum).data == expected)


def materialize_ghcp_input_bundle(
    plan: dict[str, Any], *, reviewed_plan_sha256: str,
    dataset_parquet: Path, reference_root: Path, destination: Path,
) -> GHCPInputBundle:
    """Publish approved local bytes to an absent destination, with ready last.

    Raises:
        GHCPInputBundleRefused: Any input, source pin, path or publication differs
            from the reviewed contract. Existing and partial files stay intact.
    """
    try:
        reviewed = _validated_plan(plan, reviewed_plan_sha256)
        root, reserved = _destination(destination)
        parquet, references = _absolute(dataset_parquet), _root(reference_root)
        source_root = _root(gate.ROOT)
        versions = _reference_versions(reviewed)
        _require(all(parquet != _path(references, role) for role in versions))
        for source in (source_root, parquet, references):
            _require(not _overlap(root, source) and not _overlap(reserved, source))
        with ExitStack() as stack:
            check_code = stack.enter_context(_held_parents(source_root, tuple(role for role, _ in reviewed.sources)))
            check_parquet = stack.enter_context(_held_parents(parquet.parent, (parquet.name,)))
            check_references = stack.enter_context(_held_parents(references, tuple(versions)))
            check_parent = stack.enter_context(_held_parents(root.parent, (root.name, reserved.name)))
            parent_fd = os.open(root.parent, _directory_flags())
            stack.callback(os.close, parent_fd)
            _require(not os.path.lexists(root) and not os.path.lexists(reserved))
            _require(_validated_plan(plan, reviewed_plan_sha256) == reviewed)
            bundle, reads = _snapshot(reviewed, parquet, references)
            for check in (check_code, check_parquet, check_references, check_parent):
                check()
            _write_no_clobber(reserved, _reservation(bundle), parent_fd=parent_fd)
            check_parent()
            os.mkdir(root.name, mode=0o700, dir_fd=parent_fd)
            check_parent()
            with _publication_parents(root) as (check_root, mkdir, directory_fd):
                for role in _directories(bundle.files):
                    check_parent()
                    mkdir(_path(root, role))
                for role, data in bundle.files:
                    check_parent()
                    check_root()
                    path = _path(root, role)
                    _write_no_clobber(path, data, parent_fd=directory_fd(path.parent))
                    check_root()
                    check_parent()
                _members(root, bundle, published=False)
                _check_reads(reads)
                _require(_validated_plan(plan, reviewed_plan_sha256) == reviewed)
                _members(root, bundle, published=False)
                _require(_read_file(reserved, MAX_DOCUMENT_BYTES).data == _reservation(bundle))
                for check in (check_code, check_parquet, check_references, check_root, check_parent):
                    check()
                # Ready is the last file written; a replaced directory still
                # refuses success, retaining any already published bytes.
                _write_no_clobber(root / READY_PATH, bundle.canonical_bytes(), parent_fd=directory_fd(root))
                check_root()
                check_parent()
                return bundle
    except Exception:
        raise GHCPInputBundleRefused() from None


def verify_ghcp_input_bundle(
    plan: dict[str, Any], *, reviewed_plan_sha256: str, bundle_root: Path,
) -> GHCPInputBundle:
    """Rebuild the closed manifest from published bytes and current source pins.

    Raises:
        GHCPInputBundleRefused: A byte, member, reservation, source pin or parent
            differs. Verification never adopts a manifest-only assertion.
    """
    try:
        reviewed = _validated_plan(plan, reviewed_plan_sha256)
        root, reserved = _destination(bundle_root)
        _root(root)
        source_root = _root(gate.ROOT)
        _require(not _overlap(root, source_root) and not _overlap(reserved, source_root))
        roles = (PARQUET_PATH, INSTRUCTIONS_PATH, MANIFEST_PATH, READY_PATH, *_reference_versions(reviewed))
        with _held_parents(source_root, tuple(role for role, _ in reviewed.sources)) as check_code:
            with _held_parents(root.parent, (root.name, reserved.name)) as check_parent:
                with _held_parents(root, roles) as check_root:
                    observed = _read_file(root / READY_PATH, MAX_DOCUMENT_BYTES)
                    reservation = _read_file(reserved, MAX_DOCUMENT_BYTES)
                    bundle, reads = _snapshot(reviewed, root / PARQUET_PATH, root)
                    _require(observed.data == bundle.canonical_bytes() and reservation.data == _reservation(bundle))
                    _members(root, bundle, published=True)
                    _require(_validated_plan(plan, reviewed_plan_sha256) == reviewed)
                    _check_reads((*reads, observed, reservation))
                    _members(root, bundle, published=True)
                    check_root()
                    check_parent()
                    check_code()
                    return bundle
    except Exception:
        raise GHCPInputBundleRefused() from None


def main(argv: list[str] | None = None) -> int:
    """Materialize or verify without printing private inputs or launching work."""
    parser = _ArgumentParser(prog="ghcp_vm_input_bundle", description=__doc__, allow_abbrev=False)
    parser.add_argument("--plan", type=Path, default=gate.PLAN, help="Reviewed local GHCP gate YAML.")
    parser.add_argument("--reviewed-plan-sha256", required=True,
                        help="Canonical plan SHA256 from the reviewed gate preflight report.")
    output = parser.add_mutually_exclusive_group(required=True)
    output.add_argument("--destination", type=Path,
                        help="Absent local directory outside the source roots; its parent must exist.")
    output.add_argument("--verify-bundle", type=Path, help="Published local bundle to reread and verify.")
    parser.add_argument("--dataset-parquet", type=Path, help="Local whole parquet with the pinned exact bytes.")
    parser.add_argument("--reference-root", type=Path,
                        help="Local directory containing the original reference_files/ layout.")
    try:
        arguments = sys.argv[1:] if argv is None else argv
        _require(type(arguments) is list and all(type(value) is str for value in arguments))
        args = parser.parse_args(arguments)
        plan_path = _absolute(args.plan)
        with _held_parents(plan_path.parent, (plan_path.name,)) as check_plan_parent:
            supplied = _read_file(plan_path, gate.MAX_PLAN_BYTES)
            plan = gate._yaml(supplied.data)
            _check_reads((supplied,))
            check_plan_parent()
        if args.destination is not None:
            _require(args.dataset_parquet is not None and args.reference_root is not None)
            bundle = materialize_ghcp_input_bundle(
                plan, reviewed_plan_sha256=args.reviewed_plan_sha256,
                dataset_parquet=args.dataset_parquet, reference_root=args.reference_root, destination=args.destination,
            )
        else:
            _require(args.dataset_parquet is None and args.reference_root is None)
            bundle = verify_ghcp_input_bundle(
                plan, reviewed_plan_sha256=args.reviewed_plan_sha256, bundle_root=args.verify_bundle,
            )
        report = {"input_bundle_complete": True, "bundle_sha256": bundle.sha256,
                  "evidence_boundary": BOUNDARY, **_false_flags()}
    except SystemExit as error:
        # argparse's help is deliberately usable; errors never reach its printer.
        if error.code == 0:
            return 0
        report = {"input_bundle_complete": False, "bundle_sha256": None,
                  "refusal_code": REFUSAL, "evidence_boundary": BOUNDARY, **_false_flags()}
    except Exception:
        report = {"input_bundle_complete": False, "bundle_sha256": None,
                  "refusal_code": REFUSAL, "evidence_boundary": BOUNDARY, **_false_flags()}
    sys.stdout.write(canonical_json(report).decode("utf-8") + "\n")
    return 0 if report["input_bundle_complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
