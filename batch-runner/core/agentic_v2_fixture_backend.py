"""Deterministic, model-free backend for Agentic Sandbox V2 contract tests."""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import stat
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any, Mapping

from core.agentic_v2_contract import (
    FOUNDATION_BACKEND_ID,
    AgenticV2Profile,
    canonical_relative_path,
)
from core.agentic_v2_provenance import (
    canonical_sha256,
    foundation_fixture_identity,
)


_MAX_FILE_BYTES = 1048576
_MAX_WORKSPACE_BYTES = 64 * 1024 * 1024
_MAX_FINAL_BYTES = 64 * 1024 * 1024
_MAX_WORKSPACE_ENTRIES = 4096
_MAX_DIRECTORY_ENTRIES = 1024


class AgenticV2FixtureBackend:
    """A deliberately non-production backend with no shell or network access."""

    def __init__(
        self,
        *,
        root: str | Path,
        profile: AgenticV2Profile,
        package_catalog: Mapping[str, str] | None = None,
        budget_caps: Mapping[str, Any] | None = None,
        **_: Any,
    ):
        lexical_root = Path(root)
        if lexical_root.is_symlink():
            raise ValueError("fixture root symlink is forbidden")
        lexical_root.mkdir(parents=True, exist_ok=True)
        self.root = lexical_root.resolve()
        work = self.root / "work"
        if work.is_symlink():
            raise ValueError("fixture work root symlink is forbidden")
        work.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.work = work.resolve()
        self._root_fd = os.open(
            self.work,
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
        )
        opened = os.fstat(self._root_fd)
        lexical = self.work.lstat()
        if (opened.st_dev, opened.st_ino) != (lexical.st_dev, lexical.st_ino):
            os.close(self._root_fd)
            raise ValueError("fixture work root identity changed")
        self._root_identity = (opened.st_dev, opened.st_ino)
        self.profile = profile
        package_catalog_value = dict(
            {"python:demo-pkg==1.0.0": "d" * 64}
            if package_catalog is None
            else package_catalog
        )
        for coordinate, digest in package_catalog_value.items():
            if (
                not isinstance(coordinate, str)
                or re.fullmatch(
                    r"(?:python|npm|debian):[A-Za-z0-9][A-Za-z0-9._-]{0,127}"
                    r"(?:==[A-Za-z0-9][A-Za-z0-9.!+_-]{0,127})?",
                    coordinate,
                ) is None
                or not isinstance(digest, str)
                or re.fullmatch(r"[0-9a-f]{64}", digest) is None
            ):
                raise ValueError("fixture package catalog identity is invalid")
        canonical_identity = foundation_fixture_identity(
            profile.policy_profile_id,
            dict(budget_caps or {"tool_calls": 32, "wall_seconds": 1200}),
        )
        if tuple(sorted(package_catalog_value.items())) != tuple(
            canonical_identity["package_records"]
        ):
            raise ValueError("fixture package catalog must match canonical identity")
        self._package_records = tuple(sorted(package_catalog_value.items()))
        self.package_catalog = MappingProxyType(dict(self._package_records))
        self.budget_caps = dict(
            budget_caps or {"tool_calls": 32, "wall_seconds": 1200}
        )
        self._locks: dict[str, bytes] = {}
        self._active_locks: set[str] = set()
        self._result: dict | None = None
        self.closed = False

    def start(self, timeout_seconds: float) -> Mapping[str, Any]:
        del timeout_seconds
        identity = foundation_fixture_identity(
            self.profile.policy_profile_id,
            self.budget_caps,
        )
        return {
            "ok": True,
            "data": {
                "substrate_manifest": {
                    "schema_version": "2.0-fixture",
                    "sha256": identity["substrate_manifest_sha256"],
                },
                "backend_identity": identity["backend_identity"],
                "package_snapshot_sha256": identity[
                    "package_snapshot_sha256"
                ],
                "browser_build_sha256": identity["browser_build_sha256"],
                "capabilities": identity["capabilities"],
            },
        }

    def state_sha256(self) -> str:
        root_mode, entries, _ = self._workspace_snapshot()
        return canonical_sha256({
            "root_mode": root_mode,
            "profile": self.profile.policy_profile_id,
            "package_catalog": self._package_records,
            "budget_caps": self.budget_caps,
            "entries": entries,
            "active_locks": sorted(self._active_locks),
            "terminal_result_sha256": (
                canonical_sha256(_result_identity(self._result))
                if self._result is not None else None
            ),
        })

    def workspace_state_sha256(self) -> str:
        _, entries, _ = self._workspace_snapshot()
        return canonical_sha256(entries)

    def capabilities_query(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        kind = str(arguments["kind"])
        return {
            "ok": True,
            "data": {"kind": kind, "items": self._capabilities()[kind]},
        }

    def expected_capabilities(self) -> Mapping[str, Any]:
        return self._capabilities()

    def workspace_apply(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        operation = str(arguments["operation"])
        if operation == "copy":
            source = str(arguments["source"])
            destination = str(arguments["destination"])
            self._write_bytes(destination, self._read_bytes(source))
            return {"ok": True, "data": {"path": destination}}
        relative = str(arguments["path"])
        if operation == "list":
            try:
                descriptor = self._open_directory(relative)
            except (FileNotFoundError, NotADirectoryError, ValueError):
                return {"ok": False, "error_type": "path_not_directory"}
            try:
                entries = sorted(os.listdir(descriptor))
                if len(entries) > _MAX_DIRECTORY_ENTRIES:
                    raise ValueError("fixture directory entry limit exceeded")
                return {"ok": True, "data": {"entries": entries}}
            finally:
                os.close(descriptor)
        if operation == "read":
            content = self._read_bytes(relative).decode("utf-8")
            offset = int(arguments.get("offset", 0))
            limit = int(arguments.get("limit", 1048576))
            selected = content[offset:offset + limit]
            return {"ok": True, "data": {
                "content": selected,
                "content_sha256": hashlib.sha256(selected.encode("utf-8")).hexdigest(),
            }}
        if operation in {"write", "patch"}:
            content = str(arguments["content"]).encode("utf-8")
            if len(content) > 1048576:
                raise ValueError("fixture workspace write exceeds byte limit")
            self._write_bytes(relative, content)
        elif operation == "delete":
            self._delete(relative)
        else:
            self._reserve_entries(relative, temporary_leaf=False)
            descriptor = self._open_directory(relative, create=True)
            os.close(descriptor)
        return {"ok": True, "data": {"path": relative}}

    def exec_run(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        argv = arguments.get("argv")
        if not isinstance(argv, list) or not argv:
            return {"ok": False, "error_type": "capability_unavailable"}
        if argv[0] == "fixture-upper" and len(argv) == 3:
            cwd = str(arguments["cwd"])
            try:
                descriptor = self._open_directory(cwd)
            except (FileNotFoundError, NotADirectoryError, ValueError):
                return {"ok": False, "error_type": "path_not_directory"}
            else:
                os.close(descriptor)
            source = _join_relative(cwd, str(argv[1]))
            destination = _join_relative(cwd, str(argv[2]))
            self._write_bytes(destination, self._read_bytes(source).upper())
            return {"ok": True, "data": {"returncode": 0}}
        return {"ok": False, "error_type": "capability_unavailable"}

    def environment_resolve(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        if self.profile.policy_profile_id == "offline-full-v1":
            return {"ok": False, "error_type": "capability_unavailable"}
        ecosystem = str(arguments["ecosystem"])
        requirements = sorted(str(item) for item in arguments["requirements"])
        coordinates = [f"{ecosystem}:{item}" for item in requirements]
        if any(item not in self.package_catalog for item in coordinates):
            return {"ok": False, "error_type": "package_not_in_snapshot"}
        lock = {
            "ecosystem": ecosystem,
            "requirements": requirements,
            "blobs": [self.package_catalog[item] for item in coordinates],
        }
        digest = canonical_sha256(lock)
        self._locks[digest] = json.dumps(
            lock, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
        return {"ok": True, "data": {"lock_digest": digest, "lock": lock}}

    def environment_activate(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        if self.profile.policy_profile_id == "offline-full-v1":
            return {"ok": False, "error_type": "capability_unavailable"}
        digest = str(arguments["lock_digest"])
        lock_bytes = self._locks.get(digest)
        if lock_bytes is None:
            return {"ok": False, "error_type": "unapproved_lock"}
        try:
            lock = json.loads(lock_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {"ok": False, "error_type": "unapproved_lock"}
        coordinates = [
            f"{lock.get('ecosystem')}:{requirement}"
            for requirement in lock.get("requirements", [])
        ]
        if (
            canonical_sha256(lock) != digest
            or coordinates != [
                f"{lock['ecosystem']}:{value}"
                for value in sorted(lock.get("requirements", []))
            ]
            or any(value not in self.package_catalog for value in coordinates)
            or lock.get("blobs") != [
                self.package_catalog[value] for value in coordinates
            ]
        ):
            return {"ok": False, "error_type": "unapproved_lock"}
        self._active_locks.add(digest)
        return {"ok": True, "data": {"environment_id": digest}}

    def browser_run(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        operation = str(arguments["operation"])
        if operation in {"search", "open_url"}:
            return {"ok": False, "error_type": "capability_unavailable"}
        relative = str(arguments["path"])
        content = self._read_bytes(relative)
        return {
            "ok": True,
            "data": {
                "path": relative,
                "sha256": hashlib.sha256(content).hexdigest(),
            },
        }

    def verify_public(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        try:
            artifacts, _ = self._collect_artifacts(arguments["deliverables"])
        except (FileNotFoundError, OSError, ValueError):
            return {"ok": False, "error_type": "artifact_not_openable"}
        return {"ok": True, "data": {"artifacts": artifacts}}

    def finalize(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        try:
            artifacts, files = self._collect_artifacts(arguments["deliverables"])
        except (FileNotFoundError, OSError, ValueError):
            return {"ok": False, "error_type": "artifact_not_openable"}
        self._result = {
            "success": True,
            "text": str(arguments["summary"]),
            "deliverable_text": str(arguments["summary"]),
            "files": files,
        }
        return {"ok": True, "data": {"artifacts": artifacts}}

    def best_result(self) -> Mapping[str, Any] | None:
        return dict(self._result) if self._result is not None else None

    def close(self) -> None:
        if not self.closed:
            try:
                self._purge_directory(self._root_fd)
            finally:
                os.close(self._root_fd)
            try:
                metadata = self.work.lstat()
            except FileNotFoundError:
                pass
            else:
                if (
                    stat.S_ISDIR(metadata.st_mode)
                    and metadata.st_dev == self._root_identity[0]
                    and metadata.st_ino == self._root_identity[1]
                ):
                    self.work.rmdir()
        self.closed = True

    def _capabilities(self) -> dict:
        return foundation_fixture_identity(
            self.profile.policy_profile_id,
            self.budget_caps,
        )["capabilities"]

    def _read_bytes(self, relative: str) -> bytes:
        descriptor = self._open_regular(relative)
        try:
            return _read_regular_descriptor(descriptor)
        finally:
            os.close(descriptor)

    def _write_bytes(self, relative: str, content: bytes) -> None:
        if len(content) > _MAX_FILE_BYTES:
            raise ValueError("fixture workspace write exceeds byte limit")
        self._reserve_entries(relative, temporary_leaf=True)
        _, _, current_bytes = self._workspace_snapshot()
        try:
            existing = self._open_regular(relative)
        except FileNotFoundError:
            pass
        else:
            os.close(existing)
        if current_bytes + len(content) > _MAX_WORKSPACE_BYTES:
            raise ValueError("fixture workspace byte limit exceeded")
        parent_fd, name = self._open_parent(relative, create=True)
        temporary = None
        try:
            self._assert_directory_beneath_root(parent_fd)
            descriptor, temporary = self._open_owned_temporary(parent_fd, name)
            try:
                with os.fdopen(descriptor, "wb", closefd=False) as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
            finally:
                os.close(descriptor)
            self._assert_directory_beneath_root(parent_fd)
            os.replace(temporary, name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
            try:
                self._assert_directory_beneath_root(parent_fd)
            except Exception:
                os.unlink(name, dir_fd=parent_fd)
                raise
        finally:
            if temporary is not None:
                try:
                    os.unlink(temporary, dir_fd=parent_fd)
                except FileNotFoundError:
                    pass
            os.close(parent_fd)

    def _open_owned_temporary(
        self,
        parent_fd: int,
        destination_name: str,
    ) -> tuple[int, str]:
        flags = (
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0)
        )
        for _ in range(32):
            candidate = f".agentic-v2-{secrets.token_hex(8)}.tmp"
            try:
                descriptor = os.open(
                    candidate,
                    flags,
                    0o600,
                    dir_fd=parent_fd,
                )
            except FileExistsError:
                continue
            return descriptor, candidate
        raise ValueError("fixture temporary file allocation failed")

    def _open_directory(self, relative: str, *, create: bool = False) -> int:
        canonical_relative_path(relative)
        self._assert_root_identity()
        descriptor = os.dup(self._root_fd)
        if relative == ".":
            return descriptor
        try:
            for part in PurePosixPath(relative).parts:
                self._assert_directory_beneath_root(descriptor)
                if create:
                    try:
                        os.mkdir(part, mode=0o700, dir_fd=descriptor)
                    except FileExistsError:
                        pass
                child = os.open(
                    part,
                    os.O_RDONLY
                    | getattr(os, "O_DIRECTORY", 0)
                    | getattr(os, "O_NOFOLLOW", 0)
                    | getattr(os, "O_CLOEXEC", 0),
                    dir_fd=descriptor,
                )
                try:
                    self._assert_directory_beneath_root(descriptor)
                    self._assert_directory_beneath_root(child)
                except Exception:
                    os.close(child)
                    raise
                os.close(descriptor)
                descriptor = child
            return descriptor
        except Exception:
            os.close(descriptor)
            raise

    def _open_parent(self, relative: str, *, create: bool = False) -> tuple[int, str]:
        canonical_relative_path(relative)
        if relative == ".":
            raise ValueError("fixture file path must not be workspace root")
        path = PurePosixPath(relative)
        parent = path.parent.as_posix()
        return self._open_directory(parent, create=create), path.name

    def _open_regular(self, relative: str) -> int:
        parent_fd, name = self._open_parent(relative)
        descriptor = None
        try:
            self._assert_directory_beneath_root(parent_fd)
            descriptor = os.open(
                name,
                os.O_RDONLY
                | getattr(os, "O_NOFOLLOW", 0)
                | getattr(os, "O_NONBLOCK", 0)
                | getattr(os, "O_CLOEXEC", 0),
                dir_fd=parent_fd,
            )
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                raise ValueError(
                    "fixture workspace file must be single-link regular"
                )
            self._assert_directory_beneath_root(parent_fd)
            self._assert_descriptor_beneath_root(descriptor)
            return descriptor
        except Exception:
            if descriptor is not None:
                os.close(descriptor)
            raise
        finally:
            os.close(parent_fd)

    def _delete(self, relative: str) -> None:
        parent_fd, name = self._open_parent(relative)
        try:
            self._assert_directory_beneath_root(parent_fd)
            metadata = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
            if stat.S_ISDIR(metadata.st_mode):
                os.rmdir(name, dir_fd=parent_fd)
            elif stat.S_ISREG(metadata.st_mode) and metadata.st_nlink == 1:
                os.unlink(name, dir_fd=parent_fd)
            else:
                raise ValueError("fixture workspace entry is unsafe")
            self._assert_directory_beneath_root(parent_fd)
        finally:
            os.close(parent_fd)

    def _workspace_snapshot(self) -> tuple[int, list[dict], int]:
        self._assert_root_identity()
        entries: list[dict] = []
        total_bytes = 0

        def visit(directory_fd: int, prefix: str) -> None:
            nonlocal total_bytes
            self._assert_directory_beneath_root(directory_fd)
            names = sorted(os.listdir(directory_fd))
            if len(names) > _MAX_DIRECTORY_ENTRIES:
                raise ValueError("fixture directory entry limit exceeded")
            for name in names:
                self._assert_directory_beneath_root(directory_fd)
                if len(entries) >= _MAX_WORKSPACE_ENTRIES:
                    raise ValueError("fixture workspace entry limit exceeded")
                relative = f"{prefix}/{name}" if prefix else name
                metadata = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
                if stat.S_ISDIR(metadata.st_mode):
                    child = os.open(
                        name,
                        os.O_RDONLY
                        | getattr(os, "O_DIRECTORY", 0)
                        | getattr(os, "O_NOFOLLOW", 0)
                        | getattr(os, "O_CLOEXEC", 0),
                        dir_fd=directory_fd,
                    )
                    try:
                        self._assert_directory_beneath_root(directory_fd)
                        self._assert_directory_beneath_root(child)
                        opened = os.fstat(child)
                        entries.append({
                            "path": relative,
                            "kind": "directory",
                            "mode": stat.S_IMODE(opened.st_mode),
                        })
                        visit(child, relative)
                    finally:
                        os.close(child)
                elif stat.S_ISREG(metadata.st_mode):
                    descriptor = os.open(
                        name,
                        os.O_RDONLY
                        | getattr(os, "O_NOFOLLOW", 0)
                        | getattr(os, "O_NONBLOCK", 0)
                        | getattr(os, "O_CLOEXEC", 0),
                        dir_fd=directory_fd,
                    )
                    try:
                        self._assert_directory_beneath_root(directory_fd)
                        self._assert_descriptor_beneath_root(descriptor)
                        opened = os.fstat(descriptor)
                        if (
                            not stat.S_ISREG(opened.st_mode)
                            or opened.st_nlink != 1
                        ):
                            raise ValueError(
                                "fixture workspace contains unsafe entry"
                            )
                        content = _read_regular_descriptor(descriptor)
                        self._assert_directory_beneath_root(directory_fd)
                        self._assert_descriptor_beneath_root(descriptor)
                        total_bytes += len(content)
                        if total_bytes > _MAX_WORKSPACE_BYTES:
                            raise ValueError("fixture workspace byte limit exceeded")
                        entries.append({
                            "path": relative,
                            "kind": "file",
                            "sha256": hashlib.sha256(content).hexdigest(),
                            "size": len(content),
                            "mode": stat.S_IMODE(opened.st_mode),
                        })
                    finally:
                        os.close(descriptor)
                else:
                    raise ValueError("fixture workspace contains unsafe entry")

        root = os.dup(self._root_fd)
        try:
            root_mode = stat.S_IMODE(os.fstat(root).st_mode)
            visit(root, "")
        finally:
            os.close(root)
        return root_mode, entries, total_bytes

    def _reserve_entries(self, relative: str, *, temporary_leaf: bool) -> None:
        canonical_relative_path(relative)
        _, entries, _ = self._workspace_snapshot()
        existing = {entry["path"] for entry in entries}
        planned = []
        current = ""
        for part in PurePosixPath(relative).parts:
            current = f"{current}/{part}" if current else part
            if current not in existing:
                planned.append(current)
        leaf_exists = relative in existing
        peak_extra = len(planned) + int(temporary_leaf and leaf_exists)
        if len(entries) + peak_extra > _MAX_WORKSPACE_ENTRIES:
            raise ValueError("fixture workspace entry limit exceeded")
        child_counts: dict[str, int] = {}
        for path in existing:
            parent = PurePosixPath(path).parent.as_posix()
            child_counts[parent] = child_counts.get(parent, 0) + 1
        for path in planned:
            parent = PurePosixPath(path).parent.as_posix()
            child_counts[parent] = child_counts.get(parent, 0) + 1
        if temporary_leaf and leaf_exists:
            parent = PurePosixPath(relative).parent.as_posix()
            child_counts[parent] = child_counts.get(parent, 0) + 1
        if any(count > _MAX_DIRECTORY_ENTRIES for count in child_counts.values()):
            raise ValueError("fixture directory entry limit exceeded")

    def _assert_root_identity(self) -> None:
        try:
            lexical = self.work.lstat()
        except FileNotFoundError as exc:
            raise ValueError("fixture work root identity changed") from exc
        opened = os.fstat(self._root_fd)
        identity = (opened.st_dev, opened.st_ino)
        if (
            not stat.S_ISDIR(lexical.st_mode)
            or identity != self._root_identity
            or (lexical.st_dev, lexical.st_ino) != self._root_identity
        ):
            raise ValueError("fixture work root identity changed")

    def _assert_directory_beneath_root(self, descriptor: int) -> None:
        try:
            self._assert_descriptor_beneath_root(descriptor, require_directory=True)
        except Exception:
            self._purge_directory(descriptor)
            raise

    def _assert_descriptor_beneath_root(
        self,
        descriptor: int,
        *,
        require_directory: bool = False,
    ) -> None:
        self._assert_root_identity()
        target = Path(os.readlink(f"/proc/self/fd/{descriptor}"))
        try:
            target.relative_to(self.work)
        except ValueError as exc:
            raise ValueError("fixture descriptor moved outside work root") from exc
        lexical = target.lstat()
        opened = os.fstat(descriptor)
        if (
            (require_directory and not stat.S_ISDIR(opened.st_mode))
            or (lexical.st_dev, lexical.st_ino) != (opened.st_dev, opened.st_ino)
        ):
            raise ValueError("fixture descriptor identity changed")

    def _purge_directory(self, descriptor: int) -> None:
        for name in os.listdir(descriptor):
            metadata = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
            if stat.S_ISDIR(metadata.st_mode):
                child = os.open(
                    name,
                    os.O_RDONLY
                    | getattr(os, "O_DIRECTORY", 0)
                    | getattr(os, "O_NOFOLLOW", 0)
                    | getattr(os, "O_CLOEXEC", 0),
                    dir_fd=descriptor,
                )
                try:
                    self._purge_directory(child)
                finally:
                    os.close(child)
                os.rmdir(name, dir_fd=descriptor)
            else:
                os.unlink(name, dir_fd=descriptor)

    def _collect_artifacts(self, deliverables: Any) -> tuple[list[dict], list[dict]]:
        artifacts = []
        files = []
        total_bytes = 0
        for value in deliverables:
            relative = canonical_relative_path(str(value))
            descriptor = self._open_regular(relative)
            try:
                content = _read_regular_descriptor(descriptor)
            finally:
                os.close(descriptor)
            if not content:
                raise ValueError("fixture artifact is empty")
            total_bytes += len(content)
            if total_bytes > _MAX_FINAL_BYTES:
                raise ValueError("fixture final artifact byte limit exceeded")
            artifacts.append({
                "path": relative,
                "sha256": hashlib.sha256(content).hexdigest(),
                "size": len(content),
            })
            files.append({"filename": relative, "content": content})
        return artifacts, files


def _read_regular_descriptor(descriptor: int) -> bytes:
    os.lseek(descriptor, 0, os.SEEK_SET)
    chunks = []
    total = 0
    while True:
        chunk = os.read(descriptor, 65536)
        if not chunk:
            break
        total += len(chunk)
        if total > _MAX_FILE_BYTES:
            raise ValueError("fixture workspace file exceeds byte limit")
        chunks.append(chunk)
    return b"".join(chunks)


def _join_relative(directory: str, child: str) -> str:
    canonical_relative_path(directory)
    canonical_relative_path(child)
    if child == ".":
        raise ValueError("fixture file name must not be a directory")
    return child if directory == "." else f"{directory}/{child}"


def _result_identity(result: Mapping[str, Any] | None) -> dict | None:
    if result is None:
        return None
    return {
        "success": result.get("success"),
        "text": result.get("text"),
        "files": [
            {
                "filename": item.get("filename"),
                "sha256": hashlib.sha256(item.get("content", b"")).hexdigest(),
            }
            for item in result.get("files", [])
            if isinstance(item, Mapping)
            and isinstance(item.get("content"), bytes)
        ],
    }