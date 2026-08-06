"""Offline Python wheel broker candidate for Agentic Sandbox V2 Phase 1D-A.

This module is deliberately not connected to the model loop, ``TaskExecutor``,
Step 2, workflows, or publication. It proves that an exact local package
snapshot can be resolved without mutation and activated atomically without any
package-index or network access.
"""

from __future__ import annotations

import hashlib
import base64
import csv
import fcntl
import io
import itertools
import json
import os
import platform
import re
import stat
import sys
import tempfile
import threading
import zipfile
from dataclasses import dataclass
from contextlib import contextmanager
from email.parser import BytesParser
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.utils import canonicalize_name, parse_wheel_filename
from packaging.version import Version

from core.agentic_v2_contract import AgenticV2Profile
from core.agentic_v2_provenance import canonical_sha256


PACKAGE_SNAPSHOT_SCHEMA_VERSION = "1.0"
PACKAGE_BROKER_ID = "agentic-v2-offline-python-wheel-broker-v1"
PACKAGE_POLICY_ID = "agentic-v2-package-broker-candidate-v1"
MAX_REQUESTED_PACKAGES = 8
MAX_ARTIFACT_BYTES = 64 * 1024 * 1024
MAX_SNAPSHOT_ARTIFACT_BYTES = 64 * 1024 * 1024
MAX_ENVIRONMENT_BYTES = 256 * 1024 * 1024
MAX_ENVIRONMENT_ENTRIES = 4096
MAX_ACTIVE_ENVIRONMENTS = 8
MAX_ACTIVE_ENVIRONMENT_BYTES = 512 * 1024 * 1024
MAX_WHEEL_ENTRIES = 4096
MAX_WHEEL_PATH_BYTES = 240
MAX_WHEEL_METADATA_BYTES = 1024 * 1024
MAX_WHEEL_CONTROL_BYTES = 64 * 1024
MAX_WHEEL_RECORD_BYTES = 2 * 1024 * 1024
MAX_MANIFEST_BYTES = 1024 * 1024
MAX_RECEIPT_BYTES = 2 * 1024 * 1024
MAX_CLEANUP_ENTRIES = MAX_ENVIRONMENT_ENTRIES + 8
MAX_CLEANUP_DEPTH = 128
INSTALLER_OVERHEAD_BYTES_PER_WHEEL = 4096
INSTALLER_OVERHEAD_ENTRIES_PER_WHEEL = 4
STAGING_PREFIX = ".agentic-v2-staging-"
LEASE_PREFIX = ".agentic-v2-lease-"

_DIGEST = re.compile(r"[0-9a-f]{64}")
_EXACT_REQUIREMENT = re.compile(
    r"([a-z0-9](?:[a-z0-9._-]{0,126}[a-z0-9])?)"
    r"==([A-Za-z0-9](?:[A-Za-z0-9.!+_-]{0,126}[A-Za-z0-9])?)"
)


@dataclass(frozen=True)
class PackageArtifact:
    coordinate: str
    filename: str
    sha256: str
    size: int
    unpacked_size: int
    entry_count: int
    files: frozenset[str]
    directories: frozenset[str]


@dataclass(frozen=True)
class WheelInspection:
    unpacked_size: int
    entry_count: int
    files: frozenset[str]
    directories: frozenset[str]


@dataclass(frozen=True)
class PackageSnapshot:
    artifact_root: Path
    document: Mapping[str, Any]
    sha256: str
    artifacts: Mapping[str, PackageArtifact]

    @classmethod
    def load(
        cls,
        manifest_path: str | Path,
        *,
        artifact_root: str | Path,
    ) -> "PackageSnapshot":
        root = _directory_path(artifact_root, label="package artifact root")
        try:
            raw = _read_regular_bytes(
                manifest_path,
                label="package snapshot manifest",
                max_bytes=MAX_MANIFEST_BYTES,
            ).decode("utf-8")
            value = json.loads(raw)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("package snapshot manifest is invalid") from exc
        document, records = _validate_snapshot(value, root)
        return cls(
            artifact_root=root,
            document=_freeze_json(document),
            sha256=canonical_sha256(document),
            artifacts=MappingProxyType(records),
        )

    def artifact_path(self, coordinate: str) -> Path:
        artifact = self.artifacts.get(coordinate)
        if artifact is None:
            raise KeyError(coordinate)
        return self.artifact_root / artifact.filename

    def verify_artifact(self, coordinate: str) -> PackageArtifact:
        artifact = self.artifacts.get(coordinate)
        if artifact is None:
            raise ValueError("package is not in the approved snapshot")
        inspection = _verify_artifact(self.artifact_root, artifact)
        if inspection != WheelInspection(
            unpacked_size=artifact.unpacked_size,
            entry_count=artifact.entry_count,
            files=artifact.files,
            directories=artifact.directories,
        ):
            raise ValueError("package artifact inventory drifted")
        return artifact

    def verified_artifact_content(
        self,
        coordinate: str,
    ) -> tuple[PackageArtifact, bytes]:
        artifact = self.artifacts.get(coordinate)
        if artifact is None:
            raise ValueError("package is not in the approved snapshot")
        content, inspection = _verified_artifact_content(
            self.artifact_root, artifact
        )
        if inspection != WheelInspection(
            unpacked_size=artifact.unpacked_size,
            entry_count=artifact.entry_count,
            files=artifact.files,
            directories=artifact.directories,
        ):
            raise ValueError("package artifact inventory drifted")
        return artifact, content


class OfflinePythonWheelBroker:
    """Resolve and atomically activate approved local pure-Python wheels."""

    def __init__(
        self,
        *,
        snapshot: PackageSnapshot,
        environment_root: str | Path,
    ):
        self.snapshot = snapshot
        root = Path(environment_root)
        if root.is_symlink():
            raise ValueError("package environment root symlink is forbidden")
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.environment_root = root.resolve()
        root_metadata = self.environment_root.stat()
        if (
            root_metadata.st_uid != os.getuid()
            or stat.S_IMODE(root_metadata.st_mode) != 0o700
        ):
            raise ValueError("package environment root must be private and owned")
        self._root_fd: int | None = os.open(
            self.environment_root,
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
        )
        opened_root = os.fstat(self._root_fd)
        if (
            opened_root.st_dev != root_metadata.st_dev
            or opened_root.st_ino != root_metadata.st_ino
        ):
            os.close(self._root_fd)
            self._root_fd = None
            raise ValueError("package environment root identity changed")
        self.installer_identity = MappingProxyType(
            _deterministic_installer_identity()
        )
        self.policy_sha256 = _load_package_policy()
        self._active: dict[str, str] = {}
        self._leases: dict[str, int] = {}
        self._activation_lock = threading.RLock()
        self._closed = False

    def state_sha256(self) -> str:
        with self._activation_lock:
            root_fd = self._root_fd
            if root_fd is not None:
                fcntl.flock(root_fd, fcntl.LOCK_SH)
            try:
                environments: list[tuple[str, str]] = []
                payload_bytes = 0
                if root_fd is not None:
                    self._verify_root_identity(root_fd)
                    try:
                        environments, payload_bytes = self._global_root_state(
                            root_fd
                        )
                    except Exception as exc:
                        raise ValueError(
                            "package environment state drifted"
                        ) from exc
                return canonical_sha256({
                    "broker_id": PACKAGE_BROKER_ID,
                    "policy_sha256": self.policy_sha256,
                    "snapshot_sha256": self.snapshot.sha256,
                    "installer": dict(self.installer_identity),
                    "active_environments": environments,
                    "active_environment_payload_bytes": payload_bytes,
                })
            finally:
                if root_fd is not None:
                    fcntl.flock(root_fd, fcntl.LOCK_UN)

    def resolve(self, arguments: Mapping[str, Any]) -> dict[str, Any]:
        with self._activation_lock:
            if self._closed:
                return _error("compute_backend_error")
        ecosystem = arguments.get("ecosystem")
        if ecosystem != "python":
            return _error("capability_unavailable")
        raw_requirements = arguments.get("requirements")
        if (
            not isinstance(raw_requirements, list)
            or not 1 <= len(raw_requirements) <= MAX_REQUESTED_PACKAGES
            or any(not isinstance(value, str) for value in raw_requirements)
            or len(set(raw_requirements)) != len(raw_requirements)
        ):
            return _error("invalid_arguments")
        requirements = sorted(raw_requirements)
        try:
            coordinates = [
                _coordinate_from_requirement(requirement)
                for requirement in requirements
            ]
        except ValueError:
            return _error("invalid_arguments")
        if any(coordinate not in self.snapshot.artifacts for coordinate in coordinates):
            return _error("package_not_in_snapshot")
        lock = _package_lock(
            [self.snapshot.artifacts[coordinate] for coordinate in coordinates]
        )
        digest = canonical_sha256(lock)
        return {
            "ok": True,
            "data": {"lock_digest": digest, "lock": lock},
        }

    def activate(self, arguments: Mapping[str, Any]) -> dict[str, Any]:
        digest = arguments.get("lock_digest")
        if not isinstance(digest, str) or _DIGEST.fullmatch(digest) is None:
            return _error("invalid_arguments")
        try:
            lock = self._validated_lock(digest)
            for requirement in lock["requirements"]:
                self.snapshot.verify_artifact(
                    _coordinate_from_requirement(requirement)
                )
        except ValueError:
            return _error("unapproved_lock")

        with self._exclusive_root() as root_fd:
            if root_fd is None:
                return _error("compute_backend_error")
            try:
                self._remove_stale_entries(root_fd, preserve_digest=digest)
            except (OSError, ValueError):
                return _error("compute_backend_error")
            target = _root_entry_path(root_fd, digest)
            if _entry_exists(root_fd, digest):
                try:
                    receipt_sha256 = self._verify_environment(target, digest, lock)
                except ValueError:
                    return _error("unapproved_lock")
                if (
                    digest in self._active
                    and self._active[digest] != receipt_sha256
                ):
                    return _error("unapproved_lock")
                try:
                    self._acquire_environment_lease(root_fd, digest)
                except (OSError, ValueError):
                    return _error("compute_backend_error")
                self._active[digest] = receipt_sha256
                return _success_environment(digest)

            try:
                self._verify_root_quota(root_fd, lock)
            except ValueError:
                return _error("compute_backend_error")

            try:
                self._acquire_environment_lease(root_fd, digest)
            except (OSError, ValueError):
                return _error("compute_backend_error")

            staging: Path | None = None
            published = False
            try:
                staging = Path(tempfile.mkdtemp(
                    prefix=STAGING_PREFIX,
                    dir=_root_entry_path(root_fd, ""),
                ))
                site_packages = staging / "site-packages"
                site_packages.mkdir(mode=0o700)
                for requirement in lock["requirements"]:
                    coordinate = _coordinate_from_requirement(requirement)
                    artifact, content = self.snapshot.verified_artifact_content(
                        coordinate
                    )
                    _install_verified_wheel(content, site_packages, artifact)
                _make_tree_read_only(site_packages)
                receipt = _expected_environment_receipt(
                    self.snapshot,
                    lock,
                    lock_digest=digest,
                    snapshot_sha256=self.snapshot.sha256,
                    policy_sha256=self.policy_sha256,
                    installer_identity=self.installer_identity,
                    requirements=lock["requirements"],
                )
                receipt_path = staging / "environment.json"
                receipt_raw = json.dumps(
                    receipt,
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                ).encode("utf-8")
                if len(receipt_raw) > MAX_RECEIPT_BYTES:
                    raise ValueError("package environment receipt exceeds limit")
                _write_regular_exclusive(receipt_path, receipt_raw, mode=0o444)
                staging.chmod(0o555)
                receipt_sha256 = self._verify_environment(staging, digest, lock)
                os.replace(
                    staging.name,
                    digest,
                    src_dir_fd=root_fd,
                    dst_dir_fd=root_fd,
                )
                published = True
                _best_effort_fsync(root_fd)
                self._active[digest] = receipt_sha256
            except (OSError, ValueError, zipfile.BadZipFile):
                try:
                    self._release_environment_lease(root_fd, digest)
                except (OSError, ValueError):
                    if published:
                        try:
                            _remove_entry_at(root_fd, digest)
                        except (OSError, ValueError):
                            pass
                return _error("compute_backend_error")
            finally:
                if staging is not None and _entry_exists(root_fd, staging.name):
                    _remove_entry_at(root_fd, staging.name)
        return _success_environment(digest)

    def environment_path(self, lock_digest: str) -> Path:
        if not isinstance(lock_digest, str) or _DIGEST.fullmatch(lock_digest) is None:
            raise ValueError("package environment digest is invalid")
        return self.environment_root / lock_digest

    def close(self) -> None:
        with self._activation_lock:
            root_fd = self._root_fd
            if self._closed or root_fd is None:
                return
            fcntl.flock(root_fd, fcntl.LOCK_EX)
            close_error: Exception | None = None
            try:
                for digest in tuple(self._leases):
                    try:
                        self._release_environment_lease(
                            root_fd,
                            digest,
                            budget={"entries": 0},
                        )
                    except (OSError, ValueError) as exc:
                        if close_error is None:
                            close_error = exc
                try:
                    self._remove_stale_entries(root_fd)
                except (OSError, ValueError) as exc:
                    if close_error is None:
                        close_error = exc
            finally:
                for lease_fd in self._leases.values():
                    try:
                        fcntl.flock(lease_fd, fcntl.LOCK_UN)
                    finally:
                        os.close(lease_fd)
                self._leases.clear()
                self._active.clear()
                self._closed = True
                self._root_fd = None
                fcntl.flock(root_fd, fcntl.LOCK_UN)
                os.close(root_fd)
            if close_error is not None:
                raise ValueError("package environment cleanup failed") from close_error

    def _validated_lock(self, digest: str) -> dict[str, Any]:
        artifacts = tuple(self.snapshot.artifacts.values())
        for count in range(1, len(artifacts) + 1):
            for selected in itertools.combinations(artifacts, count):
                lock = _package_lock(selected)
                if canonical_sha256(lock) == digest:
                    return lock
        raise ValueError("package lock is not in the approved snapshot")

    def _verify_environment(
        self,
        target: Path,
        digest: str,
        lock: Mapping[str, Any],
    ) -> str:
        try:
            target_metadata = target.lstat()
        except OSError as exc:
            raise ValueError("package environment is unavailable") from exc
        if (
            target.is_symlink()
            or not stat.S_ISDIR(target_metadata.st_mode)
            or stat.S_IMODE(target_metadata.st_mode) != 0o555
            or target_metadata.st_uid != os.getuid()
        ):
            raise ValueError("package environment is unsafe")
        try:
            target_fd = os.open(
                target,
                os.O_RDONLY
                | getattr(os, "O_DIRECTORY", 0)
                | getattr(os, "O_NOFOLLOW", 0)
                | getattr(os, "O_CLOEXEC", 0),
            )
            try:
                opened = os.fstat(target_fd)
                children = set()
                for entry in os.scandir(target_fd):
                    children.add(entry.name)
                    if len(children) > 2:
                        raise ValueError(
                            "package environment has unexpected entries"
                        )
                if (
                    opened.st_dev != target_metadata.st_dev
                    or opened.st_ino != target_metadata.st_ino
                    or children != {"environment.json", "site-packages"}
                ):
                    raise ValueError("package environment identity is unsafe")
                receipt_raw = _read_regular_at(
                    "environment.json",
                    dir_fd=target_fd,
                    label="package environment receipt",
                    max_bytes=MAX_RECEIPT_BYTES,
                    required_mode=0o444,
                    required_uid=os.getuid(),
                )
                site_packages_fd = _open_directory_at(
                    target_fd,
                    "site-packages",
                    label="package environment site-packages",
                    required_mode=0o555,
                )
                try:
                    actual = _environment_receipt_from_fd(
                        site_packages_fd,
                        lock_digest=digest,
                        snapshot_sha256=self.snapshot.sha256,
                        policy_sha256=self.policy_sha256,
                        installer_identity=self.installer_identity,
                        requirements=lock["requirements"],
                    )
                finally:
                    os.close(site_packages_fd)
            finally:
                os.close(target_fd)
        except OSError as exc:
            raise ValueError("package environment identity changed") from exc
        expected = _expected_environment_receipt(
            self.snapshot,
            lock,
            lock_digest=digest,
            snapshot_sha256=self.snapshot.sha256,
            policy_sha256=self.policy_sha256,
            installer_identity=self.installer_identity,
            requirements=lock["requirements"],
        )
        expected_raw = _canonical_json_bytes(expected)
        if receipt_raw != expected_raw or actual != expected:
            raise ValueError("package environment receipt drifted")
        return hashlib.sha256(receipt_raw).hexdigest()

    def _verify_root_quota(
        self,
        root_fd: int,
        prospective_lock: Mapping[str, Any],
    ) -> None:
        environments, active_bytes = self._global_root_state(root_fd)
        prospective_bytes = _lock_unpacked_bytes(
            self.snapshot, prospective_lock
        )
        if (
            len(environments) + 1 > MAX_ACTIVE_ENVIRONMENTS
            or active_bytes + prospective_bytes
            > MAX_ACTIVE_ENVIRONMENT_BYTES
        ):
            raise ValueError("package environment root quota exceeded")

    def _global_root_state(
        self,
        root_fd: int,
    ) -> tuple[list[tuple[str, str]], int]:
        environment_digests: set[str] = set()
        lease_digests: set[str] = set()
        seen = 0
        for entry in os.scandir(root_fd):
            seen += 1
            if seen > MAX_ACTIVE_ENVIRONMENTS * 2:
                raise ValueError("package environment root entry limit exceeded")
            if _DIGEST.fullmatch(entry.name) is not None:
                environment_digests.add(entry.name)
                continue
            if entry.name.startswith(LEASE_PREFIX):
                digest = entry.name.removeprefix(LEASE_PREFIX)
                if _DIGEST.fullmatch(digest) is not None:
                    lease_digests.add(digest)
                    continue
            raise ValueError("package environment root entry is unaccounted")
        if (
            environment_digests != lease_digests
            or len(environment_digests) > MAX_ACTIVE_ENVIRONMENTS
            or set(self._active) != set(self._leases)
            or not set(self._active).issubset(environment_digests)
        ):
            raise ValueError("package environment root inventory is invalid")

        environments: list[tuple[str, str]] = []
        payload_bytes = 0
        for digest in sorted(environment_digests):
            _validate_live_lease(
                root_fd,
                digest,
                held_fd=self._leases.get(digest),
            )
            lock = self._validated_lock(digest)
            receipt_sha256 = self._verify_environment(
                _root_entry_path(root_fd, digest),
                digest,
                lock,
            )
            if (
                digest in self._active
                and receipt_sha256 != self._active[digest]
            ):
                raise ValueError(
                    "package environment receipt baseline drifted"
                )
            environments.append((digest, receipt_sha256))
            payload_bytes += _lock_unpacked_bytes(self.snapshot, lock)
        if payload_bytes > MAX_ACTIVE_ENVIRONMENT_BYTES:
            raise ValueError("package environment root byte limit exceeded")
        return environments, payload_bytes

    @contextmanager
    def _exclusive_root(self):
        with self._activation_lock:
            root_fd = self._root_fd
            if self._closed or root_fd is None:
                yield None
                return
            fcntl.flock(root_fd, fcntl.LOCK_EX)
            try:
                try:
                    self._verify_root_identity(root_fd)
                except ValueError:
                    yield None
                else:
                    yield root_fd
            finally:
                fcntl.flock(root_fd, fcntl.LOCK_UN)

    def _verify_root_identity(self, root_fd: int) -> None:
        try:
            path_metadata = self.environment_root.lstat()
            opened_metadata = os.fstat(root_fd)
        except OSError as exc:
            raise ValueError("package environment root is unavailable") from exc
        if (
            self.environment_root.is_symlink()
            or not stat.S_ISDIR(path_metadata.st_mode)
            or path_metadata.st_dev != opened_metadata.st_dev
            or path_metadata.st_ino != opened_metadata.st_ino
            or path_metadata.st_uid != os.getuid()
            or stat.S_IMODE(path_metadata.st_mode) != 0o700
        ):
            raise ValueError("package environment root identity changed")

    def _acquire_environment_lease(self, root_fd: int, digest: str) -> None:
        if digest in self._leases:
            _validate_held_lease(
                root_fd,
                digest,
                self._leases[digest],
            )
            return
        lease_fd = os.open(
            _lease_name(digest),
            os.O_RDWR
            | os.O_CREAT
            | getattr(os, "O_NONBLOCK", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
            0o600,
            dir_fd=root_fd,
        )
        try:
            _validate_held_lease(root_fd, digest, lease_fd)
        except Exception:
            os.close(lease_fd)
            raise
        self._leases[digest] = lease_fd

    def _release_environment_lease(
        self,
        root_fd: int,
        digest: str,
        *,
        budget: dict[str, int] | None = None,
    ) -> None:
        lease_fd = self._leases.pop(digest, None)
        if lease_fd is not None:
            fcntl.flock(lease_fd, fcntl.LOCK_UN)
            os.close(lease_fd)
        _cleanup_unleased_environment(root_fd, digest, budget=budget)

    def _remove_stale_entries(
        self,
        root_fd: int,
        *,
        preserve_digest: str | None = None,
    ) -> None:
        cleanup_budget = {"entries": 0}
        for entry in os.scandir(root_fd):
            _consume_cleanup_budget(cleanup_budget)
            if entry.name.startswith(LEASE_PREFIX):
                digest = entry.name.removeprefix(LEASE_PREFIX)
                if _DIGEST.fullmatch(digest) is None:
                    _remove_entry_at(
                        root_fd,
                        entry.name,
                        budget=cleanup_budget,
                    )
                elif not _entry_exists(root_fd, digest):
                    if digest in self._leases:
                        self._release_environment_lease(
                            root_fd,
                            digest,
                            budget=cleanup_budget,
                        )
                    else:
                        _cleanup_unleased_environment(
                            root_fd,
                            digest,
                            budget=cleanup_budget,
                        )
                elif digest in self._leases:
                    _validate_held_lease(
                        root_fd,
                        digest,
                        self._leases[digest],
                    )
                elif digest != preserve_digest and digest not in self._leases:
                    _cleanup_unleased_environment(
                        root_fd,
                        digest,
                        budget=cleanup_budget,
                    )
            elif entry.name.startswith(".agentic-v2-"):
                _remove_entry_at(
                    root_fd,
                    entry.name,
                    budget=cleanup_budget,
                )
            elif _DIGEST.fullmatch(entry.name) is not None:
                if entry.name == preserve_digest:
                    continue
                lease_name = _lease_name(entry.name)
                if not _entry_exists(root_fd, lease_name):
                    _remove_entry_at(
                        root_fd,
                        entry.name,
                        budget=cleanup_budget,
                    )
                elif entry.name not in self._leases:
                    _cleanup_unleased_environment(
                        root_fd,
                        entry.name,
                        budget=cleanup_budget,
                    )
            else:
                raise ValueError("package environment root entry is unaccounted")


class AgenticV2PackageBrokerCandidateBackend:
    """Tool-dispatch candidate with package activation and no execution plane."""

    def __init__(
        self,
        *,
        root: str | Path,
        profile: AgenticV2Profile,
        snapshot: PackageSnapshot,
        budget_caps: Mapping[str, Any] | None = None,
        **_: Any,
    ):
        if (
            profile.policy_profile_id != "package-broker-v1"
            or profile.foundation_only is not True
        ):
            raise ValueError("package broker candidate requires package-broker-v1")
        candidate_root = Path(root)
        if candidate_root.is_symlink():
            raise ValueError("package broker candidate root symlink is forbidden")
        candidate_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.root = candidate_root.resolve()
        self.profile = profile
        self.snapshot = snapshot
        self.budget_caps = dict(
            budget_caps or {"tool_calls": 32, "wall_seconds": 1200}
        )
        self.broker = OfflinePythonWheelBroker(
            snapshot=snapshot,
            environment_root=self.root / "environments",
        )
        self._closed = False

    def start(self, timeout_seconds: float) -> Mapping[str, Any]:
        del timeout_seconds
        capabilities = self.expected_capabilities()
        implementation_sha256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        return {
            "ok": True,
            "data": {
                "substrate_manifest": {
                    "schema_version": "1.0-candidate",
                    "sha256": canonical_sha256({
                        "broker_id": PACKAGE_BROKER_ID,
                        "exec_run": "blocked_pending_containment",
                        "policy_sha256": self.broker.policy_sha256,
                        "snapshot_sha256": self.snapshot.sha256,
                    }),
                },
                "backend_identity": {
                    "backend_id": PACKAGE_BROKER_ID,
                    "foundation_only": True,
                    "implementation_sha256": implementation_sha256,
                },
                "package_snapshot_sha256": self.snapshot.sha256,
                "package_policy_sha256": self.broker.policy_sha256,
                "browser_build_sha256": canonical_sha256({
                    "browser": "disabled"
                }),
                "capabilities": capabilities,
            },
        }

    def expected_capabilities(self) -> Mapping[str, Any]:
        return {
            "commands": [],
            "runtimes": [],
            "packages": sorted(self.snapshot.artifacts),
            "formats": [],
            "budgets": [
                f"tool_calls={self.budget_caps['tool_calls']}",
                f"wall_seconds={self.budget_caps['wall_seconds']}",
            ],
        }

    def state_sha256(self) -> str:
        return self.broker.state_sha256()

    def capabilities_query(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        kind = str(arguments["kind"])
        return {
            "ok": True,
            "data": {"kind": kind, "items": self.expected_capabilities()[kind]},
        }

    def workspace_apply(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        del arguments
        return _error("capability_unavailable")

    def exec_run(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        del arguments
        return _error("capability_unavailable")

    def environment_resolve(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        return self.broker.resolve(arguments)

    def environment_activate(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        return self.broker.activate(arguments)

    def browser_run(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        del arguments
        return _error("capability_unavailable")

    def verify_public(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        del arguments
        return _error("capability_unavailable")

    def finalize(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        del arguments
        return _error("capability_unavailable")

    def best_result(self) -> Mapping[str, Any] | None:
        return None

    def close(self) -> None:
        if self._closed:
            return
        self.broker.close()
        self._closed = True


def _validate_snapshot(
    value: Any,
    artifact_root: Path,
) -> tuple[dict[str, Any], dict[str, PackageArtifact]]:
    if not isinstance(value, dict) or set(value) != {
        "schema_version",
        "policy_id",
        "foundation_only",
        "production_activation",
        "platform",
        "artifacts",
    }:
        raise ValueError("package snapshot fields are invalid")
    if (
        value.get("schema_version") != PACKAGE_SNAPSHOT_SCHEMA_VERSION
        or value.get("policy_id") != PACKAGE_POLICY_ID
        or value.get("foundation_only") is not True
        or value.get("production_activation") != "disabled"
        or value.get("platform") != {
            "os": "linux",
            "architecture": "amd64",
            "python": f"{sys.version_info.major}.{sys.version_info.minor}",
        }
        or sys.platform != "linux"
        or platform.machine().lower() not in {"x86_64", "amd64"}
        or not isinstance(value.get("artifacts"), list)
        or not value["artifacts"]
        or len(value["artifacts"]) > MAX_REQUESTED_PACKAGES
    ):
        raise ValueError("package snapshot policy is invalid")
    document = json.loads(json.dumps(value, allow_nan=False))
    records: dict[str, PackageArtifact] = {}
    package_names: set[str] = set()
    filenames: set[str] = set()
    digests: set[str] = set()
    installed_files: set[str] = set()
    installed_directories: set[str] = set()
    total_artifact_bytes = 0
    total_unpacked_bytes = 0
    total_entries = 0
    for item in document["artifacts"]:
        if not isinstance(item, dict) or set(item) != {
            "coordinate",
            "filename",
            "sha256",
            "size",
            "dependencies",
        }:
            raise ValueError("package artifact fields are invalid")
        coordinate = item.get("coordinate")
        filename = item.get("filename")
        digest = item.get("sha256")
        size = item.get("size")
        if (
            not isinstance(coordinate, str)
            or not coordinate.startswith("python:")
            or not isinstance(filename, str)
            or filename != Path(filename).name
            or "/" in filename
            or "\\" in filename
            or not filename.endswith(".whl")
            or not isinstance(digest, str)
            or _DIGEST.fullmatch(digest) is None
            or type(size) is not int
            or not 0 < size <= MAX_ARTIFACT_BYTES
            or item.get("dependencies") != []
            or coordinate in records
            or filename in filenames
            or digest in digests
        ):
            raise ValueError("package artifact policy is invalid")
        requirement = coordinate.removeprefix("python:")
        name, version = _split_exact_requirement(requirement)
        if name in package_names:
            raise ValueError("package snapshot contains conflicting versions")
        wheel_name, wheel_version, wheel_build, wheel_tags = parse_wheel_filename(
            filename
        )
        if (
            canonicalize_name(str(wheel_name)) != name
            or str(wheel_version) != version
            or wheel_build != ()
            or {str(tag) for tag in wheel_tags} != {"py3-none-any"}
        ):
            raise ValueError("package wheel identity is invalid")
        provisional = PackageArtifact(
            coordinate=coordinate,
            filename=filename,
            sha256=digest,
            size=size,
            unpacked_size=0,
            entry_count=0,
            files=frozenset(),
            directories=frozenset(),
        )
        inspection = _verify_artifact(artifact_root, provisional)
        if (
            installed_files.intersection(inspection.files)
            or installed_files.intersection(inspection.directories)
            or installed_directories.intersection(inspection.files)
        ):
            raise ValueError("package wheel file collision is forbidden")
        artifact = PackageArtifact(
            coordinate=coordinate,
            filename=filename,
            sha256=digest,
            size=size,
            unpacked_size=inspection.unpacked_size,
            entry_count=inspection.entry_count,
            files=inspection.files,
            directories=inspection.directories,
        )
        records[coordinate] = artifact
        package_names.add(name)
        filenames.add(filename)
        digests.add(digest)
        installed_files.update(inspection.files)
        installed_directories.update(inspection.directories)
        total_artifact_bytes += size
        total_unpacked_bytes += (
            inspection.unpacked_size + INSTALLER_OVERHEAD_BYTES_PER_WHEEL
        )
        total_entries += (
            inspection.entry_count + INSTALLER_OVERHEAD_ENTRIES_PER_WHEEL
        )
        if (
            total_artifact_bytes > MAX_SNAPSHOT_ARTIFACT_BYTES
            or total_unpacked_bytes > MAX_ENVIRONMENT_BYTES
            or total_entries > MAX_ENVIRONMENT_ENTRIES
        ):
            raise ValueError("package snapshot aggregate limits exceeded")
    if document["artifacts"] != sorted(
        document["artifacts"], key=lambda item: item["coordinate"]
    ):
        raise ValueError("package artifacts must be canonically ordered")
    return document, records


def _coordinate_from_requirement(requirement: str) -> str:
    name, version = _split_exact_requirement(requirement)
    return f"python:{name}=={version}"


def _package_lock(artifacts: Iterable[PackageArtifact]) -> dict[str, Any]:
    ordered = sorted(
        artifacts,
        key=lambda artifact: artifact.coordinate,
    )
    requirements = [
        artifact.coordinate.removeprefix("python:") for artifact in ordered
    ]
    names = [_split_exact_requirement(requirement)[0] for requirement in requirements]
    if len(names) != len(set(names)):
        raise ValueError("package lock contains conflicting versions")
    return {
        "ecosystem": "python",
        "requirements": requirements,
        "blobs": [artifact.sha256 for artifact in ordered],
    }


def _lock_unpacked_bytes(
    snapshot: PackageSnapshot,
    lock: Mapping[str, Any],
) -> int:
    return sum(
        snapshot.artifacts[_coordinate_from_requirement(requirement)].unpacked_size
        for requirement in lock["requirements"]
    )


def _split_exact_requirement(requirement: str) -> tuple[str, str]:
    match = _EXACT_REQUIREMENT.fullmatch(requirement)
    if match is None:
        raise ValueError("package requirement must be exact name==version")
    name, version = match.groups()
    if canonicalize_name(name) != name:
        raise ValueError("package requirement name must be canonical")
    return name, version


def _verify_artifact(root: Path, artifact: PackageArtifact) -> WheelInspection:
    _, inspection = _verified_artifact_content(root, artifact)
    return inspection


def _verified_artifact_content(
    root: Path,
    artifact: PackageArtifact,
) -> tuple[bytes, WheelInspection]:
    root_fd = os.open(
        root,
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0),
    )
    try:
        descriptor = os.open(
            artifact.filename,
            os.O_RDONLY
            | getattr(os, "O_NONBLOCK", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
            dir_fd=root_fd,
        )
        try:
            metadata = os.fstat(descriptor)
            if (
                not stat.S_ISREG(metadata.st_mode)
                or metadata.st_nlink != 1
                or metadata.st_size != artifact.size
                or metadata.st_size > MAX_ARTIFACT_BYTES
            ):
                raise ValueError("package artifact size or type drifted")
            chunks = []
            remaining = artifact.size
            while remaining:
                chunk = os.read(descriptor, min(1024 * 1024, remaining))
                if not chunk:
                    raise ValueError("package artifact was truncated")
                chunks.append(chunk)
                remaining -= len(chunk)
            if os.read(descriptor, 1):
                raise ValueError("package artifact grew during verification")
            final_metadata = os.fstat(descriptor)
            if (
                final_metadata.st_dev != metadata.st_dev
                or final_metadata.st_ino != metadata.st_ino
                or final_metadata.st_size != metadata.st_size
                or final_metadata.st_mtime_ns != metadata.st_mtime_ns
                or final_metadata.st_ctime_ns != metadata.st_ctime_ns
            ):
                raise ValueError("package artifact changed during verification")
        finally:
            os.close(descriptor)
    except OSError as exc:
        raise ValueError("package artifact is unavailable or unsafe") from exc
    finally:
        os.close(root_fd)
    content = b"".join(chunks)
    if hashlib.sha256(content).hexdigest() != artifact.sha256:
        raise ValueError("package artifact digest drifted")
    return content, _validate_wheel_archive(content, artifact)


def _validate_wheel_archive(
    content: bytes,
    artifact: PackageArtifact,
) -> WheelInspection:
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except (OSError, zipfile.BadZipFile) as exc:
        raise ValueError("package wheel archive is invalid") from exc
    with archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        unpacked_size = sum(info.file_size for info in infos)
        if (
            not infos
            or len(infos) > MAX_WHEEL_ENTRIES
            or len(names) != len(set(names))
            or unpacked_size + INSTALLER_OVERHEAD_BYTES_PER_WHEEL
            > MAX_ENVIRONMENT_BYTES
        ):
            raise ValueError("package wheel archive limits are invalid")
        expanded_entries: set[str] = set()
        directory_entries: set[str] = set()
        file_entries: set[str] = set()
        for info in infos:
            path = info.filename
            normalized = path[:-1] if path.endswith("/") else path
            parts = normalized.split("/")
            lowered_parts = [part.casefold() for part in parts]
            mode = info.external_attr >> 16
            file_type = stat.S_IFMT(mode)
            try:
                path_bytes = path.encode("ascii")
            except UnicodeEncodeError:
                path_bytes = b""
            if (
                not normalized
                or not path_bytes
                or len(path_bytes) > MAX_WHEEL_PATH_BYTES
                or any(value < 0x20 or value == 0x7F for value in path_bytes)
                or path.startswith("/")
                or "\\" in path
                or any(part in {"", ".", ".."} for part in parts)
                or info.flag_bits & 0x1
                or (not info.is_dir() and mode & 0o111)
                or lowered_parts[0].endswith(".data")
                or any(
                    part.split(".", 1)[0]
                    in {"sitecustomize", "usercustomize"}
                    for part in lowered_parts
                )
                or any(
                    part.endswith((".pyc", ".pth", ".egg-link"))
                    for part in lowered_parts
                )
                or (
                    file_type
                    and file_type not in {stat.S_IFREG, stat.S_IFDIR}
                )
            ):
                raise ValueError("package wheel archive entry is unsafe")
            for depth in range(1, len(parts)):
                directory_entries.add("/".join(parts[:depth]))
            if info.is_dir():
                directory_entries.add(normalized)
            else:
                file_entries.add(normalized)
            expanded_entries.update(directory_entries)
            expanded_entries.update(file_entries)
        if file_entries.intersection(directory_entries):
            raise ValueError("package wheel path kind collision is forbidden")
        if (
            len(expanded_entries) + INSTALLER_OVERHEAD_ENTRIES_PER_WHEEL
            > MAX_ENVIRONMENT_ENTRIES
        ):
            raise ValueError("package wheel archive limits are invalid")
        metadata_names = [name for name in names if name.endswith(".dist-info/METADATA")]
        wheel_names = [name for name in names if name.endswith(".dist-info/WHEEL")]
        record_names = [name for name in names if name.endswith(".dist-info/RECORD")]
        expected_dist_info = (
            artifact.filename[:-4].rsplit("-", 3)[0] + ".dist-info"
        )
        if (
            metadata_names != [f"{expected_dist_info}/METADATA"]
            or wheel_names != [f"{expected_dist_info}/WHEEL"]
            or record_names != [f"{expected_dist_info}/RECORD"]
        ):
            raise ValueError("package wheel metadata set is invalid")
        metadata = BytesParser().parsebytes(_read_wheel_member(
            archive,
            metadata_names[0],
            max_bytes=MAX_WHEEL_METADATA_BYTES,
            label="METADATA",
        ))
        requirement = artifact.coordinate.removeprefix("python:")
        expected_name, expected_version = _split_exact_requirement(requirement)
        requires_python = metadata.get_all("Requires-Python", [])
        try:
            python_compatible = (
                not requires_python
                or (
                    len(requires_python) == 1
                    and Version(platform.python_version())
                    in SpecifierSet(requires_python[0])
                )
            )
        except InvalidSpecifier as exc:
            raise ValueError("package wheel Python requirement is invalid") from exc
        if (
            len(metadata.get_all("Name", [])) != 1
            or len(metadata.get_all("Version", [])) != 1
            or canonicalize_name(str(metadata.get("Name", ""))) != expected_name
            or str(metadata.get("Version", "")) != expected_version
            or metadata.get_all("Requires-Dist")
            or not python_compatible
        ):
            raise ValueError("package wheel metadata identity is invalid")
        _validate_wheel_headers(_read_wheel_member(
            archive,
            wheel_names[0],
            max_bytes=MAX_WHEEL_CONTROL_BYTES,
            label="WHEEL",
        ))
        _validate_wheel_record(archive, record_names[0])
        files = frozenset(file_entries)
        return WheelInspection(
            unpacked_size=unpacked_size,
            entry_count=len(expanded_entries),
            files=files,
            directories=frozenset(directory_entries),
        )


def _install_verified_wheel(
    content: bytes,
    site_packages: Path,
    artifact: PackageArtifact,
) -> None:
    inspection = _validate_wheel_archive(content, artifact)
    if inspection != WheelInspection(
        unpacked_size=artifact.unpacked_size,
        entry_count=artifact.entry_count,
        files=artifact.files,
        directories=artifact.directories,
    ):
        raise ValueError("package wheel inventory drifted")
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        for directory in sorted(
            inspection.directories,
            key=lambda value: (value.count("/"), value),
        ):
            (site_packages / directory).mkdir(mode=0o755, exist_ok=True)
        for name in sorted(inspection.files):
            _write_regular_exclusive(
                site_packages / name,
                archive.read(name),
                mode=0o644,
            )


def _validate_wheel_record(archive: zipfile.ZipFile, record_name: str) -> None:
    try:
        rows = list(csv.reader(io.StringIO(
            _read_wheel_member(
                archive,
                record_name,
                max_bytes=MAX_WHEEL_RECORD_BYTES,
                label="RECORD",
            ).decode("utf-8")
        )))
    except (UnicodeDecodeError, csv.Error, KeyError) as exc:
        raise ValueError("package wheel RECORD is invalid") from exc
    records: dict[str, tuple[str, str]] = {}
    for row in rows:
        if len(row) != 3 or row[0] in records:
            raise ValueError("package wheel RECORD is invalid")
        records[row[0]] = (row[1], row[2])
    file_names = {
        info.filename for info in archive.infolist() if not info.is_dir()
    }
    if set(records) != file_names or records.get(record_name) != ("", ""):
        raise ValueError("package wheel RECORD inventory mismatch")
    for name in sorted(file_names - {record_name}):
        encoded_hash, encoded_size = records[name]
        content = archive.read(name)
        expected_hash = "sha256=" + base64.urlsafe_b64encode(
            hashlib.sha256(content).digest()
        ).decode("ascii").rstrip("=")
        if encoded_hash != expected_hash or encoded_size != str(len(content)):
            raise ValueError("package wheel RECORD identity mismatch")


def _validate_wheel_headers(content: bytes) -> None:
    normalized = content.replace(b"\r\n", b"\n")
    if b"\r" in normalized or any(
        value < 0x20 and value != 0x0A or value == 0x7F
        for value in normalized
    ):
        raise ValueError("package wheel WHEEL is invalid")
    try:
        lines = normalized.decode("ascii").split("\n")
    except UnicodeDecodeError as exc:
        raise ValueError("package wheel WHEEL is invalid") from exc
    if lines and lines[-1] == "":
        lines.pop()
    if lines and lines[-1] == "":
        lines.pop()
    if not lines or any(not line for line in lines):
        raise ValueError("package wheel WHEEL is invalid")
    headers: dict[str, list[str]] = {}
    allowed = {"Wheel-Version", "Generator", "Root-Is-Purelib", "Tag"}
    for line in lines:
        if (
            not line
            or line[0].isspace()
            or ":" not in line
        ):
            raise ValueError("package wheel WHEEL is invalid")
        name, raw_value = line.split(":", 1)
        value = raw_value.strip()
        if (
            name not in allowed
            or not value
            or any(ord(character) < 0x20 or ord(character) == 0x7F for character in value)
        ):
            raise ValueError("package wheel WHEEL is invalid")
        headers.setdefault(name, []).append(value)
    if (
        headers.get("Wheel-Version") != ["1.0"]
        or headers.get("Root-Is-Purelib") != ["true"]
        or headers.get("Tag") != ["py3-none-any"]
        or len(headers.get("Generator", [])) > 1
        or any(len(value.encode("ascii")) > 256 for value in headers.get("Generator", []))
    ):
        raise ValueError("package wheel compatibility is invalid")


def _read_wheel_member(
    archive: zipfile.ZipFile,
    name: str,
    *,
    max_bytes: int,
    label: str,
) -> bytes:
    try:
        info = archive.getinfo(name)
        if info.file_size < 0 or info.file_size > max_bytes:
            raise ValueError(f"package wheel {label} exceeds its limit")
        content = archive.read(info)
    except (KeyError, OSError, zipfile.BadZipFile) as exc:
        raise ValueError(f"package wheel {label} is invalid") from exc
    if len(content) != info.file_size or len(content) > max_bytes:
        raise ValueError(f"package wheel {label} size drifted")
    return content


def _environment_receipt(
    site_packages: Path,
    *,
    lock_digest: str,
    snapshot_sha256: str,
    policy_sha256: str,
    installer_identity: Mapping[str, Any],
    requirements: list[str],
) -> dict[str, Any]:
    root_fd = _open_directory_path(
        site_packages,
        label="package environment site-packages",
        required_mode=0o555,
    )
    try:
        return _environment_receipt_from_fd(
            root_fd,
            lock_digest=lock_digest,
            snapshot_sha256=snapshot_sha256,
            policy_sha256=policy_sha256,
            installer_identity=installer_identity,
            requirements=requirements,
        )
    finally:
        os.close(root_fd)


def _environment_receipt_from_fd(
    root_fd: int,
    *,
    lock_digest: str,
    snapshot_sha256: str,
    policy_sha256: str,
    installer_identity: Mapping[str, Any],
    requirements: list[str],
) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    limits = {"entries": 0, "bytes": 0}
    _walk_environment_directory(root_fd, "", entries, limits)
    if not entries:
        raise ValueError("package environment is empty")
    entries.sort(key=lambda item: item["path"])
    return _receipt_document(
        entries,
        total_bytes=limits["bytes"],
        lock_digest=lock_digest,
        snapshot_sha256=snapshot_sha256,
        policy_sha256=policy_sha256,
        installer_identity=installer_identity,
        requirements=requirements,
    )


def _walk_environment_directory(
    directory_fd: int,
    prefix: str,
    entries: list[dict[str, Any]],
    limits: dict[str, int],
) -> None:
    for entry in os.scandir(directory_fd):
        limits["entries"] += 1
        if limits["entries"] > MAX_ENVIRONMENT_ENTRIES:
            raise ValueError("package environment entry limit exceeded")
        relative = f"{prefix}/{entry.name}" if prefix else entry.name
        try:
            encoded = relative.encode("ascii")
        except UnicodeEncodeError as exc:
            raise ValueError("package environment path is invalid") from exc
        if (
            not encoded
            or len(encoded) > MAX_WHEEL_PATH_BYTES
            or any(value < 0x20 or value == 0x7F for value in encoded)
            or entry.name in {"", ".", ".."}
            or "/" in entry.name
            or "\\" in entry.name
        ):
            raise ValueError("package environment path is invalid")
        metadata = entry.stat(follow_symlinks=False)
        if stat.S_ISDIR(metadata.st_mode):
            child_fd = _open_directory_at(
                directory_fd,
                entry.name,
                label="package environment directory",
                required_mode=0o555,
                expected=metadata,
            )
            try:
                entries.append({
                    "path": relative,
                    "kind": "directory",
                    "mode": 0o555,
                })
                _walk_environment_directory(
                    child_fd,
                    relative,
                    entries,
                    limits,
                )
            finally:
                os.close(child_fd)
        elif stat.S_ISREG(metadata.st_mode):
            if metadata.st_size < 0:
                raise ValueError("package environment file size is invalid")
            projected = limits["bytes"] + metadata.st_size
            if projected > MAX_ENVIRONMENT_BYTES:
                raise ValueError("package environment byte limit exceeded")
            content = _read_regular_at(
                entry.name,
                dir_fd=directory_fd,
                label="package environment file",
                max_bytes=MAX_ENVIRONMENT_BYTES - limits["bytes"],
                required_mode=0o444,
                required_uid=os.getuid(),
                expected=metadata,
            )
            limits["bytes"] += len(content)
            entries.append({
                "path": relative,
                "kind": "file",
                "mode": 0o444,
                "size": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            })
        else:
            raise ValueError("package environment entry type is forbidden")


def _expected_environment_receipt(
    snapshot: PackageSnapshot,
    lock: Mapping[str, Any],
    *,
    lock_digest: str,
    snapshot_sha256: str,
    policy_sha256: str,
    installer_identity: Mapping[str, Any],
    requirements: list[str],
) -> dict[str, Any]:
    entries_by_path: dict[str, dict[str, Any]] = {}
    total_bytes = 0
    for requirement in lock["requirements"]:
        artifact, content = snapshot.verified_artifact_content(
            _coordinate_from_requirement(requirement)
        )
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            for directory in artifact.directories:
                entries_by_path[directory] = {
                    "path": directory,
                    "kind": "directory",
                    "mode": 0o555,
                }
            for name in artifact.files:
                file_content = archive.read(name)
                total_bytes += len(file_content)
                entries_by_path[name] = {
                    "path": name,
                    "kind": "file",
                    "mode": 0o444,
                    "size": len(file_content),
                    "sha256": hashlib.sha256(file_content).hexdigest(),
                }
    entries = [entries_by_path[path] for path in sorted(entries_by_path)]
    return _receipt_document(
        entries,
        total_bytes=total_bytes,
        lock_digest=lock_digest,
        snapshot_sha256=snapshot_sha256,
        policy_sha256=policy_sha256,
        installer_identity=installer_identity,
        requirements=requirements,
    )


def _receipt_document(
    entries: list[dict[str, Any]],
    *,
    total_bytes: int,
    lock_digest: str,
    snapshot_sha256: str,
    policy_sha256: str,
    installer_identity: Mapping[str, Any],
    requirements: list[str],
) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "broker_id": PACKAGE_BROKER_ID,
        "foundation_only": True,
        "production_activation": "disabled",
        "lock_digest": lock_digest,
        "snapshot_sha256": snapshot_sha256,
        "policy_sha256": policy_sha256,
        "installer": dict(installer_identity),
        "requirements": list(requirements),
        "python": f"{sys.version_info.major}.{sys.version_info.minor}",
        "entries": entries,
        "entries_sha256": canonical_sha256(entries),
        "total_bytes": total_bytes,
    }


def _canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _read_regular_bytes(
    value: str | Path,
    *,
    label: str,
    max_bytes: int,
    required_mode: int | None = None,
) -> bytes:
    return _read_regular_at(
        value,
        dir_fd=None,
        label=label,
        max_bytes=max_bytes,
        required_mode=required_mode,
    )


def _read_regular_at(
    value: str | Path,
    *,
    dir_fd: int | None,
    label: str,
    max_bytes: int,
    required_mode: int | None = None,
    required_uid: int | None = None,
    expected: os.stat_result | None = None,
) -> bytes:
    try:
        descriptor = os.open(
            value,
            os.O_RDONLY
            | getattr(os, "O_NONBLOCK", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
            dir_fd=dir_fd,
        )
        try:
            metadata = os.fstat(descriptor)
            if (
                not stat.S_ISREG(metadata.st_mode)
                or metadata.st_nlink != 1
                or metadata.st_size < 0
                or metadata.st_size > max_bytes
                or (
                    required_mode is not None
                    and stat.S_IMODE(metadata.st_mode) != required_mode
                )
                or (
                    required_uid is not None
                    and metadata.st_uid != required_uid
                )
                or (
                    expected is not None
                    and (
                        metadata.st_dev != expected.st_dev
                        or metadata.st_ino != expected.st_ino
                        or metadata.st_size != expected.st_size
                        or metadata.st_mtime_ns != expected.st_mtime_ns
                        or metadata.st_ctime_ns != expected.st_ctime_ns
                    )
                )
            ):
                raise ValueError(f"{label} must be a bounded single-link file")
            chunks = []
            remaining = metadata.st_size
            while remaining:
                chunk = os.read(descriptor, min(1024 * 1024, remaining))
                if not chunk:
                    raise ValueError(f"{label} was truncated while reading")
                chunks.append(chunk)
                remaining -= len(chunk)
            if os.read(descriptor, 1):
                raise ValueError(f"{label} grew while reading")
            final_metadata = os.fstat(descriptor)
            if (
                final_metadata.st_dev != metadata.st_dev
                or final_metadata.st_ino != metadata.st_ino
                or final_metadata.st_size != metadata.st_size
                or final_metadata.st_mode != metadata.st_mode
                or final_metadata.st_nlink != metadata.st_nlink
                or final_metadata.st_mtime_ns != metadata.st_mtime_ns
                or final_metadata.st_ctime_ns != metadata.st_ctime_ns
            ):
                raise ValueError(f"{label} changed while reading")
        finally:
            os.close(descriptor)
    except OSError as exc:
        raise ValueError(f"{label} is unavailable") from exc
    return b"".join(chunks)


def _open_directory_path(
    value: str | Path,
    *,
    label: str,
    required_mode: int | None = None,
) -> int:
    path = Path(value)
    try:
        expected = path.lstat()
        if path.is_symlink() or not stat.S_ISDIR(expected.st_mode):
            raise ValueError(f"{label} must be a directory")
        descriptor = os.open(
            path,
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
        )
        metadata = os.fstat(descriptor)
        if (
            metadata.st_dev != expected.st_dev
            or metadata.st_ino != expected.st_ino
            or metadata.st_uid != os.getuid()
            or (
                required_mode is not None
                and stat.S_IMODE(metadata.st_mode) != required_mode
            )
        ):
            os.close(descriptor)
            raise ValueError(f"{label} identity is unsafe")
        return descriptor
    except OSError as exc:
        raise ValueError(f"{label} is unavailable") from exc


def _open_directory_at(
    parent_fd: int,
    name: str,
    *,
    label: str,
    required_mode: int | None = None,
    expected: os.stat_result | None = None,
) -> int:
    try:
        descriptor = os.open(
            name,
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
            dir_fd=parent_fd,
        )
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISDIR(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or (
                required_mode is not None
                and stat.S_IMODE(metadata.st_mode) != required_mode
            )
            or (
                expected is not None
                and (
                    metadata.st_dev != expected.st_dev
                    or metadata.st_ino != expected.st_ino
                    or metadata.st_mtime_ns != expected.st_mtime_ns
                    or metadata.st_ctime_ns != expected.st_ctime_ns
                )
            )
        ):
            os.close(descriptor)
            raise ValueError(f"{label} identity is unsafe")
        return descriptor
    except OSError as exc:
        raise ValueError(f"{label} is unavailable") from exc


def _freeze_json(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({
            key: _freeze_json(item) for key, item in value.items()
        })
    if isinstance(value, list):
        return tuple(_freeze_json(item) for item in value)
    return value


def _write_regular_exclusive(path: Path, content: bytes, *, mode: int) -> None:
    descriptor = os.open(
        path,
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0),
        0o600,
    )
    try:
        offset = 0
        while offset < len(content):
            offset += os.write(descriptor, content[offset:])
        os.fchmod(descriptor, mode)
    finally:
        os.close(descriptor)


def _directory_path(value: str | Path, *, label: str) -> Path:
    path = Path(value)
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise ValueError(f"{label} is unavailable") from exc
    if path.is_symlink() or not stat.S_ISDIR(metadata.st_mode):
        raise ValueError(f"{label} must be a directory")
    return path.resolve()


def _best_effort_fsync(descriptor: int) -> None:
    try:
        os.fsync(descriptor)
    except OSError:
        pass


def _deterministic_installer_identity() -> dict[str, str]:
    return {
        "installer_id": "agentic-v2-deterministic-wheel-extractor-v1",
        "implementation_sha256": hashlib.sha256(
            Path(__file__).read_bytes()
        ).hexdigest(),
        "python": f"{sys.version_info.major}.{sys.version_info.minor}",
    }


def _load_package_policy() -> str:
    policy_path = (
        Path(__file__).resolve().parents[2]
        / "security"
        / "agentic-v2-package-broker-policy.json"
    )
    try:
        document = json.loads(_read_regular_bytes(
            policy_path,
            label="package broker policy",
            max_bytes=MAX_MANIFEST_BYTES,
        ))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("package broker policy is invalid") from exc
    if document != _expected_package_policy():
        raise ValueError("package broker policy does not match implementation")
    return canonical_sha256(document)


def _expected_package_policy() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "policy_id": PACKAGE_POLICY_ID,
        "foundation_only": True,
        "production_activation": "disabled",
        "network": {
            "package_index": "disabled",
            "os_containment": "not_run",
        },
        "supported_ecosystems": ["python-wheel"],
        "exec_run": "blocked_pending_containment",
        "limits": {
            "requested_packages": MAX_REQUESTED_PACKAGES,
            "artifact_bytes": MAX_ARTIFACT_BYTES,
            "snapshot_artifact_bytes": MAX_SNAPSHOT_ARTIFACT_BYTES,
            "environment_bytes": MAX_ENVIRONMENT_BYTES,
            "environment_entries": MAX_ENVIRONMENT_ENTRIES,
            "active_environments": MAX_ACTIVE_ENVIRONMENTS,
            "active_environment_payload_bytes": MAX_ACTIVE_ENVIRONMENT_BYTES,
            "wheel_path_bytes": MAX_WHEEL_PATH_BYTES,
            "wheel_metadata_bytes": MAX_WHEEL_METADATA_BYTES,
            "wheel_control_bytes": MAX_WHEEL_CONTROL_BYTES,
            "wheel_record_bytes": MAX_WHEEL_RECORD_BYTES,
            "cleanup_entries": MAX_CLEANUP_ENTRIES,
            "cleanup_depth": MAX_CLEANUP_DEPTH,
        },
        "activation": {
            "concurrency": "linux-flock",
            "seal": "read-only-modes-with-drift-verification",
            "crash_durability": "not_claimed",
        },
        "admission_evidence": {
            "sbom": "not_run",
            "license": "not_run",
            "cve": "not_run",
            "provenance": "not_run",
            "signature": "not_run",
        },
        "python": {
            "requirements": "exact-name-version-only",
            "wheel_tags": ["py3-none-any"],
            "dependencies": "preclosed-none-only",
            "installer": "deterministic-stdlib-wheel-extractor-v1",
        },
        "denied": [
            "live-index",
            "url-requirement",
            "vcs-requirement",
            "sdist",
            "editable",
            "npm",
            "debian-apt",
            "shell-exec",
            "model-loop",
            "workflow",
            "publication",
        ],
    }


def _make_tree_read_only(root: Path) -> None:
    for path in sorted(root.rglob("*"), key=lambda item: len(item.parts), reverse=True):
        if path.is_symlink():
            raise ValueError("package environment symlink is forbidden")
        path.chmod(0o555 if path.is_dir() else 0o444)
    root.chmod(0o555)


def _lease_name(digest: str) -> str:
    if _DIGEST.fullmatch(digest) is None:
        raise ValueError("package environment lease digest is invalid")
    return f"{LEASE_PREFIX}{digest}"


def _validate_held_lease(root_fd: int, digest: str, lease_fd: int) -> None:
    lease_name = _lease_name(digest)
    try:
        path_metadata = os.stat(
            lease_name,
            dir_fd=root_fd,
            follow_symlinks=False,
        )
        opened_metadata = os.fstat(lease_fd)
    except OSError as exc:
        raise ValueError("package environment lease is unavailable") from exc
    if (
        not stat.S_ISREG(path_metadata.st_mode)
        or path_metadata.st_dev != opened_metadata.st_dev
        or path_metadata.st_ino != opened_metadata.st_ino
        or opened_metadata.st_nlink != 1
        or opened_metadata.st_uid != os.getuid()
        or stat.S_IMODE(opened_metadata.st_mode) != 0o600
        or opened_metadata.st_size != 0
    ):
        raise ValueError("package environment lease is unsafe")
    fcntl.flock(lease_fd, fcntl.LOCK_SH | fcntl.LOCK_NB)


def _validate_live_lease(
    root_fd: int,
    digest: str,
    *,
    held_fd: int | None,
) -> None:
    if held_fd is not None:
        _validate_held_lease(root_fd, digest, held_fd)
    lease_fd = os.open(
        _lease_name(digest),
        os.O_RDWR
        | getattr(os, "O_NONBLOCK", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0),
        dir_fd=root_fd,
    )
    try:
        _validate_held_lease(root_fd, digest, lease_fd)
        if held_fd is None:
            fcntl.flock(lease_fd, fcntl.LOCK_UN)
        try:
            fcntl.flock(lease_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        fcntl.flock(lease_fd, fcntl.LOCK_UN)
        raise ValueError("package environment lease is not held")
    finally:
        os.close(lease_fd)


def _root_entry_path(root_fd: int, name: str) -> Path:
    if name and (
        name in {".", ".."}
        or "/" in name
        or "\\" in name
    ):
        raise ValueError("package root entry name is invalid")
    return Path("/proc/self/fd") / str(root_fd) / name


def _cleanup_unleased_environment(
    root_fd: int,
    digest: str,
    *,
    budget: dict[str, int] | None = None,
) -> bool:
    lease_name = _lease_name(digest)
    try:
        lease_fd = os.open(
            lease_name,
            os.O_RDWR
            | getattr(os, "O_NONBLOCK", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0),
            dir_fd=root_fd,
        )
    except FileNotFoundError:
        _remove_entry_at(root_fd, digest, budget=budget)
        return True
    try:
        metadata = os.fstat(lease_fd)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_nlink != 1
            or metadata.st_uid != os.getuid()
            or stat.S_IMODE(metadata.st_mode) != 0o600
            or metadata.st_size != 0
        ):
            raise ValueError("package environment lease is unsafe")
        try:
            fcntl.flock(lease_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        _remove_entry_at(root_fd, digest, budget=budget)
        _remove_entry_at(root_fd, lease_name, budget=budget)
        return True
    finally:
        try:
            fcntl.flock(lease_fd, fcntl.LOCK_UN)
        finally:
            os.close(lease_fd)


def _remove_entry_at(
    parent_fd: int,
    name: str,
    *,
    budget: dict[str, int] | None = None,
) -> None:
    cleanup_budget = budget if budget is not None else {"entries": 0}
    _consume_cleanup_budget(cleanup_budget)
    try:
        metadata = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return
    if not stat.S_ISDIR(metadata.st_mode):
        os.unlink(name, dir_fd=parent_fd)
        return
    descriptor = _open_cleanup_directory(parent_fd, name, metadata)
    try:
        root_iterator = os.scandir(descriptor)
    except Exception:
        os.close(descriptor)
        raise
    stack: list[tuple[int, str, int, Any, int]] = [
        (parent_fd, name, descriptor, root_iterator, 0)
    ]
    try:
        while stack:
            entry_parent_fd, entry_name, directory_fd, iterator, depth = stack[-1]
            try:
                entry = next(iterator)
            except StopIteration:
                iterator.close()
                os.close(directory_fd)
                os.rmdir(entry_name, dir_fd=entry_parent_fd)
                stack.pop()
                continue
            _consume_cleanup_budget(cleanup_budget)
            child_metadata = entry.stat(follow_symlinks=False)
            if not stat.S_ISDIR(child_metadata.st_mode):
                os.unlink(entry.name, dir_fd=directory_fd)
                continue
            child_depth = depth + 1
            if child_depth > MAX_CLEANUP_DEPTH:
                raise ValueError("package cleanup depth limit exceeded")
            child_fd = _open_cleanup_directory(
                directory_fd,
                entry.name,
                child_metadata,
            )
            try:
                child_iterator = os.scandir(child_fd)
            except Exception:
                os.close(child_fd)
                raise
            stack.append((
                directory_fd,
                entry.name,
                child_fd,
                child_iterator,
                child_depth,
            ))
    finally:
        for _, _, open_fd, iterator, _ in reversed(stack):
            iterator.close()
            try:
                os.close(open_fd)
            except OSError:
                pass


def _open_cleanup_directory(
    parent_fd: int,
    name: str,
    expected: os.stat_result,
) -> int:
    descriptor = os.open(
        name,
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_CLOEXEC", 0),
        dir_fd=parent_fd,
    )
    metadata = os.fstat(descriptor)
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_dev != expected.st_dev
        or metadata.st_ino != expected.st_ino
        or metadata.st_uid != os.getuid()
    ):
        os.close(descriptor)
        raise ValueError("package cleanup directory identity is unsafe")
    try:
        os.fchmod(descriptor, 0o700)
    except Exception:
        os.close(descriptor)
        raise
    return descriptor


def _consume_cleanup_budget(budget: dict[str, int]) -> None:
    budget["entries"] += 1
    if budget["entries"] > MAX_CLEANUP_ENTRIES:
        raise ValueError("package cleanup entry limit exceeded")


def _entry_exists(parent_fd: int, name: str) -> bool:
    try:
        os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    return True


def _success_environment(digest: str) -> dict[str, Any]:
    return {"ok": True, "data": {"environment_id": digest}}


def _error(error_type: str) -> dict[str, Any]:
    return {"ok": False, "error_type": error_type}