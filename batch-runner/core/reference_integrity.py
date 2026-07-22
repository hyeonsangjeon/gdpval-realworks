"""Fail-closed reference-file identity checks shared by batch executors."""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
from pathlib import Path, PurePosixPath
from typing import Iterable, Mapping


class ReferenceIntegrityError(ValueError):
    """A declared reference path or its bytes differ from the approved input."""


class VerifiedReferencePath(str):
    """String-compatible path carrying its approved content identity."""

    sha256: str
    size: int

    def __new__(cls, value: str, *, sha256: str, size: int):
        instance = super().__new__(cls, value)
        instance.sha256 = sha256
        instance.size = size
        return instance


def validate_reference_record(record: Mapping[str, object]) -> tuple[str, int]:
    if not isinstance(record, Mapping) or set(record) != {"sha256", "size"}:
        raise ReferenceIntegrityError("reference identity record is malformed")
    sha256 = record.get("sha256")
    size = record.get("size")
    if (
        not isinstance(sha256, str)
        or len(sha256) != 64
        or any(character not in "0123456789abcdef" for character in sha256)
        or type(size) is not int
        or size < 0
    ):
        raise ReferenceIntegrityError("reference identity record is invalid")
    return sha256, size


def validate_reference_relative_path(value: str) -> PurePosixPath:
    if not isinstance(value, str) or not value:
        raise ReferenceIntegrityError("reference path must be a nonempty string")
    path = PurePosixPath(value)
    if (
        "\\" in value
        or "\x00" in value
        or path.is_absolute()
        or path.as_posix() != value
        or not path.parts
        or path.parts[0] != "reference_files"
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ReferenceIntegrityError(f"reference path is unsafe: {value!r}")
    return path


def _reject_symlink_components(path: Path) -> None:
    absolute = path if path.is_absolute() else Path.cwd() / path
    current = Path(absolute.anchor)
    for index, component in enumerate(absolute.parts[1:]):
        current /= component
        try:
            metadata = current.lstat()
        except OSError as exc:
            raise ReferenceIntegrityError(
                f"unable to inspect reference path {path}: {exc}"
            ) from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise ReferenceIntegrityError(f"reference path is a symlink: {path}")
        if index < len(absolute.parts[1:]) - 1 and not stat.S_ISDIR(
            metadata.st_mode
        ):
            raise ReferenceIntegrityError(
                f"reference path ancestor is not a directory: {path}"
            )


def reference_file_identity(path: os.PathLike[str] | str) -> tuple[str, int]:
    """Read one regular non-symlink file and return SHA-256 plus byte size."""
    candidate = Path(path)
    _reject_symlink_components(candidate)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(candidate, flags)
    except OSError as exc:
        raise ReferenceIntegrityError(
            f"unable to open reference file {candidate}: {exc}"
        ) from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise ReferenceIntegrityError(
                f"reference path is not a regular file: {candidate}"
            )
        digest = hashlib.sha256()
        size = 0
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
        after = os.fstat(descriptor)
        if (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
        ) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        ) or size != after.st_size:
            raise ReferenceIntegrityError(
                f"reference file changed while being read: {candidate}"
            )
        return digest.hexdigest(), size
    finally:
        os.close(descriptor)


def verify_reference_path(
    path: os.PathLike[str] | str,
    *,
    expected_sha256: str | None = None,
    expected_size: int | None = None,
) -> VerifiedReferencePath:
    if isinstance(path, VerifiedReferencePath):
        expected_sha256 = path.sha256 if expected_sha256 is None else expected_sha256
        expected_size = path.size if expected_size is None else expected_size
    actual_sha256, actual_size = reference_file_identity(path)
    if expected_sha256 is not None and actual_sha256 != expected_sha256:
        raise ReferenceIntegrityError(f"reference file hash mismatch: {path}")
    if expected_size is not None and actual_size != expected_size:
        raise ReferenceIntegrityError(f"reference file size mismatch: {path}")
    return VerifiedReferencePath(
        str(path),
        sha256=actual_sha256,
        size=actual_size,
    )


def reference_manifest_record(
    root: Path,
    relative_path: str,
) -> dict[str, object]:
    relative = validate_reference_relative_path(relative_path)
    verified = verify_reference_path(root.joinpath(*relative.parts))
    return {"sha256": verified.sha256, "size": verified.size}


def resolve_verified_reference_paths(
    root: Path,
    relative_paths: Iterable[str],
    records: Iterable[Mapping[str, object]],
) -> list[VerifiedReferencePath]:
    paths = list(relative_paths)
    identities = list(records)
    if len(paths) != len(identities):
        raise ReferenceIntegrityError(
            "reference identity count differs from declared paths"
        )
    verified: list[VerifiedReferencePath] = []
    for value, identity in zip(paths, identities, strict=True):
        if not isinstance(identity, Mapping) or identity.get("path") != value:
            raise ReferenceIntegrityError(
                "reference identity order differs from declared paths"
            )
        relative = validate_reference_relative_path(value)
        sha256, size = validate_reference_record(
            {key: identity.get(key) for key in ("sha256", "size")}
        )
        verified.append(
            verify_reference_path(
                root.joinpath(*relative.parts),
                expected_sha256=sha256,
                expected_size=size,
            )
        )
    return verified


def copy_verified_reference(
    source: os.PathLike[str] | str,
    destination_directory: os.PathLike[str] | str,
) -> Path:
    verified = verify_reference_path(source)
    destination = Path(destination_directory) / Path(str(verified)).name
    if destination.exists() or destination.is_symlink():
        raise ReferenceIntegrityError(
            f"duplicate reference destination: {destination.name}"
        )
    try:
        shutil.copy2(verified, destination)
    except OSError as exc:
        raise ReferenceIntegrityError(
            f"unable to copy reference file {verified}: {exc}"
        ) from exc
    verify_reference_path(
        destination,
        expected_sha256=verified.sha256,
        expected_size=verified.size,
    )
    return destination