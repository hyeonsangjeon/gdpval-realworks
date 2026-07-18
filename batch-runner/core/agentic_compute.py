"""Uncredentialed persistent Docker compute plane for agentic tasks."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import signal
import stat
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Mapping, Optional


MAX_INPUT_FILES = 256
MAX_INPUT_TOTAL = 2 * 1024 * 1024 * 1024
MAX_INPUT_SINGLE = 512 * 1024 * 1024
MAX_WORK_FILES = 64
MAX_WORK_TOTAL = 512 * 1024 * 1024
MAX_WORK_SINGLE = 256 * 1024 * 1024
MAX_TRANSFER_TOTAL = 256 * 1024 * 1024
MAX_DEPTH = 16
MAX_PATH_BYTES = 240
OUTPUT_LIMIT = 32768
FFMPEG_INPUT_SUFFIXES = {
    ".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aac",
    ".mp4", ".mov", ".avi", ".mkv", ".webm",
}


class AgenticDockerBackend:
    """One persistent task container plus disposable verifier containers."""

    def __init__(
        self,
        *,
        task_prompt: str,
        reference_files: list[Any],
        occupation: str,
        image: str,
        verifier_image: Optional[str] = None,
        seccomp_profile: Optional[str] = None,
        apparmor_profile: str = "docker-default",
        cpus: float = 2.0,
        memory_gb: int = 8,
        allow_unpinned_image: bool = False,
        require_rootless_or_userns: bool = True,
        enforce_cpu_limit: bool = True,
        enforce_pid_limit: bool = True,
        enforce_outer_seccomp: bool = True,
        enforce_procfs_policy: bool = True,
        provider_classification: str = "approved_public_gdpval",
        approved_input_manifest: Optional[Mapping[str, Mapping[str, Any]]] = None,
        require_approved_input_manifest: bool = True,
        expected_input_merkle_root: Optional[str] = None,
        selection_recomputation_sha256: Optional[str] = None,
        sbom_sha256: Optional[str] = None,
        require_supply_chain_identity: bool = True,
        require_dedicated_host: bool = True,
        local_root_parent: Optional[str] = None,
        docker_root_parent: Optional[str] = None,
        docker_binary: str = "docker",
    ):
        if not image or ("@sha256:" not in image and not allow_unpinned_image):
            raise ValueError("agentic image must be pinned by sha256 digest")
        if not isinstance(memory_gb, int) or memory_gb <= 0 or memory_gb > 8:
            raise ValueError("memory_gb must be in [1, 8]")
        if not isinstance(cpus, (int, float)) or cpus <= 0 or cpus > 2:
            raise ValueError("cpus must be in (0, 2]")
        self.task_prompt = task_prompt
        self.reference_files = list(reference_files)
        self.occupation = occupation
        self.image = image
        self.verifier_image = verifier_image or image
        self.seccomp_profile = Path(
            seccomp_profile
            or Path(__file__).resolve().parent.parent / "sandbox" / "agentic-seccomp.json"
        ).resolve()
        if not self.seccomp_profile.is_file():
            raise ValueError("agentic seccomp profile is missing")
        self.apparmor_profile = apparmor_profile
        if not apparmor_profile or apparmor_profile == "unconfined":
            raise ValueError("an enforcing AppArmor profile is required")
        self.cpus = float(cpus)
        self.memory_gb = memory_gb
        self.docker = docker_binary
        self.require_rootless_or_userns = require_rootless_or_userns
        self.enforce_cpu_limit = enforce_cpu_limit
        self.enforce_pid_limit = enforce_pid_limit
        self.enforce_outer_seccomp = enforce_outer_seccomp
        self.enforce_procfs_policy = enforce_procfs_policy
        if not provider_classification:
            raise ValueError("provider_classification is required")
        self.provider_classification = provider_classification
        self.approved_input_manifest = (
            dict(approved_input_manifest)
            if isinstance(approved_input_manifest, Mapping)
            else None
        )
        self.require_approved_input_manifest = require_approved_input_manifest
        self.expected_input_merkle_root = expected_input_merkle_root
        if (
            selection_recomputation_sha256 is not None
            and re.fullmatch(
                r"[0-9a-f]{64}", selection_recomputation_sha256
            ) is None
        ):
            raise ValueError("selection recomputation identity is invalid")
        self.selection_recomputation_sha256 = (
            selection_recomputation_sha256
        )
        if require_supply_chain_identity and (
            not isinstance(sbom_sha256, str)
            or len(sbom_sha256) != 64
        ):
            raise ValueError("pinned agentic SBOM hash is required")
        self.sbom_sha256 = sbom_sha256 or "nonpaid-unpinned"
        self.require_supply_chain_identity = require_supply_chain_identity
        self.require_dedicated_host = require_dedicated_host
        if docker_root_parent and not local_root_parent:
            raise ValueError("docker_root_parent requires local_root_parent")
        if local_root_parent:
            Path(local_root_parent).mkdir(mode=0o700, parents=True, exist_ok=True)
        self.root = Path(tempfile.mkdtemp(
            prefix="gdpval-agentic-compute-",
            dir=local_root_parent,
        ))
        self.docker_root = (
            Path(docker_root_parent) / self.root.name
            if docker_root_parent
            else self.root
        )
        self.inputs_dir = self.root / "inputs"
        self.snapshots_dir = self.root / "snapshots"
        self.inputs_dir.mkdir(mode=0o700)
        self.snapshots_dir.mkdir(mode=0o700)
        self.container_name = f"gdpval-agentic-{uuid.uuid4().hex[:16]}"
        self.work_volume_name = f"{self.container_name}-work"
        self.container_started = False
        self.work_volume_created = False
        self._may_exist_containers: set[str] = set()
        self._may_exist_volumes: set[str] = set()
        self.poisoned = False
        self.input_records: list[dict] = []
        self.input_hashes: set[str] = set()
        self.input_merkle_root = ""
        self.latest_snapshot: Optional[Path] = None
        self.latest_verification: Optional[dict] = None
        self._best_result: Optional[dict] = None
        self._verified_component_hashes: Optional[dict[str, str]] = None
        self.image_id = ""
        self.verifier_image_id = ""

    def start(self, timeout_seconds: float = 1200.0) -> Mapping[str, Any]:
        deadline = _operation_deadline(timeout_seconds)
        try:
            self._verify_host_runtime(deadline)
            _remaining_timeout(deadline, 1200.0)
            self._verify_verifier_image_components(deadline)
            _remaining_timeout(deadline, 1200.0)
            self._stage_inputs(deadline)
            _remaining_timeout(deadline, 1200.0)
            if (
                self.expected_input_merkle_root is not None
                and self.input_merkle_root != self.expected_input_merkle_root
            ):
                return _error("approved_input_merkle_mismatch")
            self._create_work_volume(deadline)
            command = self._task_container_command()
            self._may_exist_containers.add(self.container_name)
            result = self._run(
                command, timeout=_remaining_timeout(deadline, 120.0)
            )
            if result.returncode != 0:
                return _error("container_start_failed")
            container_id = result.stdout.decode("utf-8", errors="replace").strip()
            if not container_id:
                return _error("container_start_failed")
            self.container_started = True
            self._verify_runtime(deadline)
            self._assert_pid1_only(deadline)
            _remaining_timeout(deadline, 1200.0)
            return {
                "ok": True,
                "data": {
                    "inputs": [
                        {"path": record["model_path"], "size_bytes": record["size_bytes"]}
                        for record in self.input_records
                    ],
                    "input_count": len(self.input_records),
                    "input_merkle_root": self.input_merkle_root,
                    "selection_recomputation_sha256": (
                        self.selection_recomputation_sha256
                    ),
                    "provider_classification": self.provider_classification,
                    "substrate_manifest": self.substrate_manifest(),
                },
            }
        except Exception:
            self.poisoned = True
            self._remove_container()
            return _error("container_preflight_failed")

    def inspect_workspace(
        self, timeout_seconds: float = 1200.0
    ) -> Mapping[str, Any]:
        if not self._ready():
            return _error("compute_unavailable")
        try:
            deadline = _operation_deadline(timeout_seconds)
            snapshot, _ = self._snapshot(
                deadline=deadline
            )
            files = self._strict_snapshot_files(snapshot, deadline)
            return {
                "ok": True,
                "data": {
                    "inputs": [
                        {"path": item["model_path"], "size_bytes": item["size_bytes"]}
                        for item in self.input_records
                    ],
                    "work": [
                        {
                            "path": f"work/{path.relative_to(snapshot).as_posix()}",
                            "size_bytes": path.stat().st_size,
                        }
                        for path in files
                        if not _is_internal(path.relative_to(snapshot))
                    ],
                },
            }
        except Exception:
            self.poisoned = True
            return _error("workspace_inspection_failed")

    def inspect_environment(
        self, timeout_seconds: float = 1200.0
    ) -> Mapping[str, Any]:
        if not self._ready():
            return _error("compute_unavailable")
        command = [
            self.docker, "exec", "-i", "--user", "65532:65532",
            self.container_name, "python", "-I", "-B", "-c",
            "import pathlib,sys;print(pathlib.Path('/opt/gdpval/agentic-capabilities.json').read_text())",
        ]
        deadline = _operation_deadline(timeout_seconds)
        result = self._run(
            command, timeout=_remaining_timeout(deadline, 30.0)
        )
        try:
            payload = json.loads(result.stdout.decode("utf-8"))
        except Exception:
            return _error("capability_manifest_unavailable")
        return {"ok": True, "data": payload}

    def reset_work(self, timeout_seconds: float = 1200.0) -> Mapping[str, Any]:
        """Restore a fresh attempt workspace without replacing its quota mount."""
        if not self._ready():
            return _error("compute_unavailable")
        script = (
            "import pathlib,shutil;root=pathlib.Path('/work');"
            "hidden={'.home','.tmp','.cache','.config'};"
            "[(shutil.rmtree(p) if p.is_dir() else p.unlink()) "
            "for p in list(root.iterdir()) if p.name not in hidden];"
            "[(shutil.rmtree(p,ignore_errors=True),p.mkdir(mode=0o700,parents=True,exist_ok=True)) "
            "for p in [root/name for name in hidden]]"
        )
        deadline = _operation_deadline(timeout_seconds)
        result = self._run([
            self.docker, "exec", "-i", "--user", "65532:65532",
            self.container_name, "python", "-I", "-B", "-c", script,
        ], timeout=_remaining_timeout(deadline, 30.0))
        if result.returncode != 0:
            self.poisoned = True
            return _error("workspace_reset_failed")
        try:
            self._assert_pid1_only(deadline)
        except Exception:
            self.poisoned = True
            return _error("process_leak")
        self.latest_snapshot = None
        self.latest_verification = None
        self._best_result = None
        return {"ok": True, "data": {}}

    def substrate_manifest(self) -> dict:
        manifest = {
            "schema_version": "1.0",
            "task_image": self.image,
            "task_image_id": self.image_id,
            "verifier_image": self.verifier_image,
            "verifier_image_id": self.verifier_image_id,
            "component_sha256": (
                dict(self._verified_component_hashes)
                if self._verified_component_hashes is not None
                else self._component_hashes()
            ),
            "sbom_sha256": self.sbom_sha256,
            "uid": 65532,
            "gid": 65532,
            "network": "none",
            "ipc": "none",
            "pid_namespace": "private",
            "read_only_rootfs": True,
            "cap_drop": ["ALL"],
            "no_new_privileges": True,
            "work_tmpfs": {
                "size_bytes": 536870912,
                "nr_inodes": 1024,
                "nosuid": True,
                "nodev": True,
                "noexec": True,
            },
            "selected_transfer_bytes": MAX_TRANSFER_TOTAL,
            "memory_bytes": self.memory_gb * 1024 * 1024 * 1024,
            "memory_swap_bytes": self.memory_gb * 1024 * 1024 * 1024,
            "cpus": self.cpus,
            "pids": 128,
            "nofile": 256,
            "apparmor_profile": self.apparmor_profile,
        }
        manifest["sha256"] = hashlib.sha256(
            json.dumps(
                manifest, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest()
        return manifest

    def run_python(self, source: str, timeout_seconds: float) -> Mapping[str, Any]:
        if not self._ready():
            return _error("compute_unavailable")
        command = [
            self.docker, "exec", "-i", "--user", "65532:65532",
            "--env", "HOME=/work/.home", "--env", "TMPDIR=/work/.tmp",
            "--env", "XDG_CACHE_HOME=/work/.cache",
            "--env", "XDG_CONFIG_HOME=/work/.config",
            self.container_name, "python", "-I", "-B", "-u",
            "/opt/gdpval/core/agentic_python_launcher.py",
        ]
        deadline = _operation_deadline(timeout_seconds)
        try:
            result = self._run_tool(
                command,
                input_data=source.encode("utf-8"),
            timeout=_remaining_timeout(deadline, timeout_seconds),
            )
        except subprocess.TimeoutExpired:
            self.poisoned = True
            self._remove_container()
            return _error("python_timeout")
        if (
            len(result.stdout) >= OUTPUT_LIMIT
            or len(result.stderr) >= OUTPUT_LIMIT
            or result.returncode == -signal.SIGXFSZ
        ):
            self.poisoned = True
            self._remove_container()
            return _error("python_output_limit")
        try:
            self._assert_pid1_only(deadline)
        except Exception:
            self.poisoned = True
            self._remove_container()
            return _error("process_leak")
        return {
            "ok": result.returncode == 0,
            **({"error_type": "python_execution_failed", "retryable": True}
               if result.returncode != 0 else {}),
            "data": {
                "returncode": result.returncode,
                "stdout_tail": _bounded_text(result.stdout),
                "stderr_tail": _bounded_text(result.stderr),
            },
        }

    def run_ffmpeg(
        self, operation: Mapping[str, Any], timeout_seconds: float = 660.0
    ) -> Mapping[str, Any]:
        if not self._ready():
            return _error("compute_unavailable")
        deadline = _operation_deadline(timeout_seconds)
        try:
            command = self._ffmpeg_command(operation)
        except ValueError:
            return _error("ffmpeg_path_violation")
        try:
            operation_timeout = min(
                660.0,
                float(operation.get("duration_seconds", 1)) + 60.0,
                _remaining_timeout(deadline, timeout_seconds),
            )
            result = self._run_tool(command, timeout=operation_timeout)
        except subprocess.TimeoutExpired:
            self.poisoned = True
            self._remove_container()
            return _error("ffmpeg_timeout")
        if (
            len(result.stdout) >= OUTPUT_LIMIT
            or len(result.stderr) >= OUTPUT_LIMIT
            or result.returncode == -signal.SIGXFSZ
        ):
            self.poisoned = True
            self._remove_container()
            return _error("ffmpeg_output_limit")
        try:
            self._assert_pid1_only(deadline)
        except Exception:
            self.poisoned = True
            self._remove_container()
            return _error("process_leak")
        data: dict[str, Any] = {
            "returncode": result.returncode,
            "stderr_tail": _bounded_text(result.stderr),
        }
        if operation.get("operation") == "probe" and result.returncode == 0:
            try:
                data["metadata"] = _normalize_probe_metadata(result.stdout)
            except (TypeError, ValueError, json.JSONDecodeError):
                return _error("ffprobe_result_invalid")
        return {
            "ok": result.returncode == 0,
            **({"error_type": "ffmpeg_execution_failed", "retryable": True}
               if result.returncode != 0 else {}),
            "data": data,
        }

    def inspect_artifacts(
        self, timeout_seconds: float = 1200.0
    ) -> Mapping[str, Any]:
        if not self._ready():
            return _error("compute_unavailable")
        try:
            deadline = _operation_deadline(timeout_seconds)
            snapshot, verification = self._snapshot(
                verify=True,
                deadline=deadline,
            )
            self._strict_snapshot_files(snapshot, deadline)
            assert verification is not None
            if verification.get("ok") is True:
                if not self._verification_matches_snapshot(
                    verification, snapshot, deadline=deadline
                ):
                    return _error("snapshot_hash_mismatch")
                self.latest_snapshot = snapshot
                self.latest_verification = verification
                self._best_result = None
            return verification
        except Exception:
            return _error("artifact_inspection_failed")

    def finalize(
        self,
        deliverables: list[str],
        summary: str,
        timeout_seconds: float = 1200.0,
    ) -> Mapping[str, Any]:
        deadline = _operation_deadline(timeout_seconds)
        inspected = self.inspect_artifacts(
            _remaining_timeout(deadline, timeout_seconds)
        )
        if inspected.get("ok") is not True:
            return inspected
        assert self.latest_snapshot is not None
        data = inspected.get("data") or {}
        verified = {
            item.get("path"): item
            for item in data.get("artifacts", [])
            if isinstance(item, dict)
        }
        normalized: list[str] = []
        for raw in deliverables:
            relative = _normalize_model_path(raw, output=True)
            if relative not in verified:
                return _error("unverified_deliverable")
            if relative in normalized:
                return _error("duplicate_deliverable")
            normalized.append(relative)
        try:
            snapshot, selected_verification = self._snapshot(
                verify=True,
                selected_deliverables=normalized,
                deadline=deadline,
            )
            if (
                selected_verification is None
                or selected_verification.get("ok") is not True
                or not self._verification_matches_snapshot(
                    selected_verification,
                    snapshot,
                    selected_deliverables=normalized,
                    deadline=deadline,
                )
            ):
                return _error("selected_deliverable_verification_failed")
            self.latest_snapshot = snapshot
            self.latest_verification = selected_verification
            self._best_result = self._snapshot_result(
                snapshot,
                selected_verification,
                success=True,
                summary=summary,
                deadline=deadline,
            )
        except ValueError:
            return _error("snapshot_hash_mismatch")
        return {"ok": True, "data": {"artifact_count": len(normalized)}}

    def best_result(
        self, timeout_seconds: float = 1200.0
    ) -> Mapping[str, Any] | None:
        deadline = _operation_deadline(timeout_seconds)
        if self._best_result is not None:
            return self._best_result
        if self.latest_snapshot is None or self.latest_verification is None:
            return None
        try:
            return self._snapshot_result(
                self.latest_snapshot,
                self.latest_verification,
                success=False,
                summary="",
                deadline=deadline,
            )
        except ValueError:
            return None

    @staticmethod
    def _snapshot_result(
        snapshot: Path,
        verification: Mapping[str, Any],
        *,
        success: bool,
        summary: str,
        deadline: Optional[float] = None,
    ) -> dict:
        data = verification.get("data") or {}
        files = []
        total_bytes = 0
        for item in data.get("artifacts", []):
            if not isinstance(item, Mapping):
                raise ValueError("invalid artifact verification")
            relative = item.get("path")
            expected_hash = item.get("sha256")
            if not isinstance(relative, str) or not isinstance(expected_hash, str):
                raise ValueError("invalid artifact verification")
            path = snapshot / relative
            if deadline is not None:
                _remaining_timeout(deadline, 1200.0)
            total_bytes += path.stat().st_size
            if total_bytes > MAX_TRANSFER_TOTAL:
                raise ValueError("selected artifact transfer limit exceeded")
            content_parts = []
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                while True:
                    if deadline is not None:
                        _remaining_timeout(deadline, 1200.0)
                    chunk = stream.read(1024 * 1024)
                    if not chunk:
                        break
                    digest.update(chunk)
                    content_parts.append(chunk)
            content = b"".join(content_parts)
            if digest.hexdigest() != expected_hash:
                raise ValueError("snapshot hash mismatch")
            files.append({"filename": relative, "content": content})
        if not files:
            raise ValueError("verified snapshot is empty")
        return {
            "success": success,
            "text": summary,
            "deliverable_text": summary,
            "files": files,
        }

    def close(self) -> None:
        failures = []
        for name in sorted(self._may_exist_containers):
            try:
                self._remove_named_container(name)
            except Exception as exc:
                failures.append(str(exc))
        for name in sorted(self._may_exist_volumes):
            try:
                self._remove_named_volume(name)
            except Exception as exc:
                failures.append(str(exc))
        self.container_started = self.container_name in self._may_exist_containers
        self.work_volume_created = self.work_volume_name in self._may_exist_volumes
        if failures:
            raise RuntimeError("; ".join(failures))
        for directory in [
            self.inputs_dir,
            *(
                path for path in self.inputs_dir.rglob("*")
                if path.is_dir()
            ),
        ]:
            try:
                os.chmod(directory, 0o700, follow_symlinks=False)
            except OSError:
                pass
        if self.root.exists():
            shutil.rmtree(self.root)
        if self.root.exists():
            raise RuntimeError("compute host root cleanup failed")

    def _stage_inputs(self, deadline: Optional[float] = None) -> None:
        if self.require_approved_input_manifest and self.approved_input_manifest is None:
            raise ValueError("approved input manifest is required")
        if len(self.reference_files) > MAX_INPUT_FILES:
            raise ValueError("input_file_count_limit")
        total = 0
        relative_paths: set[str] = set()
        records: list[dict] = []
        for raw_reference in self.reference_files:
            if deadline is not None:
                _remaining_timeout(deadline, 1200.0)
            source_root_value = None
            if isinstance(raw_reference, Mapping):
                source_value = raw_reference.get("source_path")
                source_root_value = raw_reference.get("source_root")
                relative_value = raw_reference.get("relative_path")
                if not isinstance(source_value, str) or not isinstance(
                    relative_value, str
                ):
                    raise ValueError("input mapping requires source_path and relative_path")
                source = Path(source_value)
                relative = Path(relative_value)
            else:
                if self.require_approved_input_manifest:
                    raise ValueError(
                        "approved inputs require explicit canonical relative paths"
                    )
                source = Path(str(raw_reference))
                relative = Path(source.name)
            if (
                relative.is_absolute()
                or not relative.parts
                or ".." in relative.parts
                or any(part.startswith(".") for part in relative.parts)
                or len(relative.parts) > MAX_DEPTH
                or len(relative.as_posix().encode("utf-8")) > MAX_PATH_BYTES
            ):
                raise ValueError("input relative path violation")
            relative_path = relative.as_posix()
            if relative_path in relative_paths:
                raise ValueError("input_name_violation")
            relative_paths.add(relative_path)
            try:
                if source_root_value is not None:
                    if not isinstance(source_root_value, str):
                        raise OSError("input source root is invalid")
                    source_root = Path(source_root_value)
                    descriptor = _open_regular_beneath_nofollow(
                        source_root, source
                    )
                    source = source_root / source
                else:
                    descriptor = _open_regular_nofollow(source)
            except OSError as exc:
                raise ValueError("input_type_or_link_violation") from exc
            try:
                metadata = os.fstat(descriptor)
                if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                    raise ValueError("input_type_or_link_violation")
                if metadata.st_size > MAX_INPUT_SINGLE:
                    raise ValueError("input_file_size_limit")
                destination = self.inputs_dir / relative
                destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                digest = hashlib.sha256()
                copied = 0
                with os.fdopen(os.dup(descriptor), "rb") as input_stream, destination.open("xb") as output:
                    for chunk in iter(lambda: input_stream.read(65536), b""):
                        if deadline is not None:
                            _remaining_timeout(deadline, 1200.0)
                        copied += len(chunk)
                        if copied > MAX_INPUT_SINGLE:
                            raise ValueError("input_file_size_limit")
                        digest.update(chunk)
                        output.write(chunk)
                after = os.fstat(descriptor)
                source_digest = _sha256_descriptor(descriptor, deadline)
                if _source_identity(after) != _source_identity(metadata):
                    raise ValueError("input_source_race")
                if source_digest != digest.hexdigest() or copied != metadata.st_size:
                    raise ValueError("input_source_race")
            finally:
                os.close(descriptor)
            os.chmod(destination, 0o444)
            total += copied
            if total > MAX_INPUT_TOTAL:
                raise ValueError("input_total_size_limit")
            staged_digest = _sha256_file(destination, deadline)
            if staged_digest != digest.hexdigest():
                raise ValueError("staged input hash mismatch")
            staged = destination.lstat()
            if (
                not stat.S_ISREG(staged.st_mode)
                or staged.st_nlink != 1
                or staged.st_size != copied
            ):
                raise ValueError("staged input identity mismatch")
            record = {
                "path": relative_path,
                "model_path": f"inputs/{relative_path}",
                "type": "regular",
                "link_count": 1,
                "size_bytes": copied,
                "source_allocated_bytes": metadata.st_blocks * 512,
                "staged_allocated_bytes": staged.st_blocks * 512,
                "sha256": digest.hexdigest(),
                "provider_classification": (
                    (self.approved_input_manifest or {}).get(
                        relative_path, {}
                    ).get(
                        "provider_classification",
                        self.provider_classification,
                    )
                ),
            }
            expected = (self.approved_input_manifest or {}).get(relative_path)
            if expected is not None:
                if not isinstance(expected, Mapping):
                    raise ValueError("approved input record is invalid")
                approved_fields = {
                    "path", "type", "link_count", "size_bytes",
                    "source_allocated_bytes", "sha256",
                    "provider_classification",
                }
                if set(expected) != approved_fields:
                    raise ValueError("approved input record fields are invalid")
                comparable = {
                    key: record[key]
                    for key in approved_fields
                }
                if dict(expected) != comparable:
                    raise ValueError("approved input identity mismatch")
            records.append(record)
        if self.approved_input_manifest is not None and set(
            self.approved_input_manifest
        ) != {record["path"] for record in records}:
            raise ValueError("approved input manifest has missing or extra files")
        for directory in sorted(
            (path for path in self.inputs_dir.rglob("*") if path.is_dir()),
            key=lambda path: len(path.parts),
            reverse=True,
        ):
            os.chmod(directory, 0o555)
        os.chmod(self.inputs_dir, 0o555)
        self.input_records = sorted(records, key=lambda item: item["path"].encode("utf-8"))
        self.input_hashes = {record["sha256"] for record in records}
        self.input_merkle_root = hashlib.sha256(
            json.dumps(
                self.input_records, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest()

    def _task_container_command(self) -> list[str]:
        memory = f"{self.memory_gb}g"
        command = [
            self.docker, "run", "--detach", "--rm", "--name", self.container_name,
            "--network", "none", "--ipc", "none",
            "--read-only", "--cap-drop", "ALL",
            "--memory", memory, "--memory-swap", memory,
            "--ulimit", "nofile=256:256", "--user", "65532:65532",
            "--security-opt", "no-new-privileges",
            "--security-opt", f"apparmor={self.apparmor_profile}",
            "--env", "HOME=/verify-work/.home",
            "--env", "TMPDIR=/verify-work/.tmp",
            "--env", "XDG_CACHE_HOME=/verify-work/.cache",
            "--env", "XDG_CONFIG_HOME=/verify-work/.config",
            "--env", "MPLCONFIGDIR=/verify-work/.cache/matplotlib",
            "--mount", (
                f"type=volume,src={self.work_volume_name},dst=/work,"
                "volume-nocopy"
            ),
            "--mount", (
                f"type=bind,src={self._docker_path(self.inputs_dir)},"
                "dst=/inputs,readonly,bind-propagation=rprivate"
            ),
            "--env", "HOME=/work/.home", "--env", "TMPDIR=/work/.tmp",
            "--env", "XDG_CACHE_HOME=/work/.cache",
            "--env", "XDG_CONFIG_HOME=/work/.config",
        ]
        if self.enforce_pid_limit:
            command += ["--pids-limit", "128"]
        if self.enforce_outer_seccomp:
            command += ["--security-opt", f"seccomp={self.seccomp_profile}"]
        if self.enforce_cpu_limit:
            command += ["--cpus", str(self.cpus)]
        command.append(self.image)
        return command

    def _verify_runtime(self, deadline: Optional[float] = None) -> None:
        deadline = deadline or _operation_deadline(1200.0)
        inspected = self._run(
            [self.docker, "inspect", self.container_name],
            timeout=_remaining_timeout(deadline, 30.0),
        )
        documents = json.loads(inspected.stdout.decode("utf-8"))
        if len(documents) != 1:
            raise RuntimeError("unexpected inspect result")
        document = documents[0]
        config = document.get("Config") or {}
        host = document.get("HostConfig") or {}
        self.image_id = str(document.get("Image") or "")
        if not self.image_id or not self.verifier_image_id:
            raise RuntimeError("image identity missing")
        if config.get("User") != "65532:65532":
            raise RuntimeError("unexpected container user")
        if host.get("NetworkMode") != "none" or host.get("IpcMode") != "none":
            raise RuntimeError("network or IPC isolation missing")
        if host.get("PidMode") not in ("", "private"):
            raise RuntimeError("private PID namespace missing")
        if host.get("ReadonlyRootfs") is not True:
            raise RuntimeError("read-only rootfs missing")
        if "ALL" not in (host.get("CapDrop") or []):
            raise RuntimeError("capability drop missing")
        if self.enforce_pid_limit and int(host.get("PidsLimit") or 0) != 128:
            raise RuntimeError("PID limit missing")
        expected_memory = self.memory_gb * 1024 * 1024 * 1024
        if int(host.get("Memory") or 0) != expected_memory:
            raise RuntimeError("memory limit missing")
        if int(host.get("MemorySwap") or 0) != expected_memory:
            raise RuntimeError("swap limit missing")
        expected_nano_cpus = int(self.cpus * 1_000_000_000)
        if (
            self.enforce_cpu_limit
            and int(host.get("NanoCpus") or 0) != expected_nano_cpus
        ):
            raise RuntimeError("CPU limit missing")
        nofile = [
            item for item in host.get("Ulimits") or []
            if item.get("Name") == "nofile"
        ]
        if nofile != [{"Name": "nofile", "Hard": 256, "Soft": 256}]:
            raise RuntimeError("nofile limit missing")
        security = host.get("SecurityOpt") or []
        if not any("no-new-privileges" in item for item in security):
            raise RuntimeError("no-new-privileges missing")
        if (
            self.enforce_outer_seccomp
            and not any("seccomp=" in item for item in security)
        ):
            raise RuntimeError("seccomp profile missing")
        if document.get("AppArmorProfile") in (None, "", "unconfined"):
            raise RuntimeError("AppArmor enforcement missing")
        masked_paths = set(host.get("MaskedPaths") or [])
        readonly_paths = set(host.get("ReadonlyPaths") or [])
        if self.enforce_procfs_policy:
            if not {
                "/proc/acpi", "/proc/kcore", "/proc/keys", "/proc/latency_stats",
                "/proc/timer_list", "/proc/timer_stats", "/proc/sched_debug",
                "/sys/firmware",
            }.issubset(masked_paths):
                raise RuntimeError("procfs masked-path policy missing")
            if not {
                "/proc/asound", "/proc/bus", "/proc/fs", "/proc/irq",
                "/proc/sys", "/proc/sysrq-trigger",
            }.issubset(readonly_paths):
                raise RuntimeError("procfs read-only policy missing")
        work_mounts = [
            mount for mount in document.get("Mounts", [])
            if mount.get("Destination") == "/work"
            and mount.get("Type") == "volume"
            and mount.get("Name") == self.work_volume_name
            and mount.get("RW") is True
        ]
        if len(work_mounts) != 1:
            raise RuntimeError("work volume mount missing")
        volume_result = self._run(
            [self.docker, "volume", "inspect", self.work_volume_name],
            timeout=_remaining_timeout(deadline, 30.0),
            check=True,
        )
        volume_documents = json.loads(volume_result.stdout.decode("utf-8"))
        if len(volume_documents) != 1:
            raise RuntimeError("work volume inspection failed")
        volume = volume_documents[0]
        if volume.get("Driver") != "local":
            raise RuntimeError("work volume driver mismatch")
        options = volume.get("Options") or {}
        if options.get("type") != "tmpfs" or options.get("device") != "tmpfs":
            raise RuntimeError("work volume is not tmpfs")
        mount_options = set(str(options.get("o", "")).split(","))
        required_options = {
            "size=536870912", "nr_inodes=1024", "uid=65532", "gid=65532",
            "nosuid", "nodev", "noexec",
        }
        if not required_options.issubset(mount_options):
            raise RuntimeError("work tmpfs quota or mount options missing")
        readonly_inputs = [
            mount for mount in document.get("Mounts", [])
            if mount.get("Destination") == "/inputs" and mount.get("RW") is False
        ]
        if len(readonly_inputs) != 1:
            raise RuntimeError("read-only inputs mount missing")
        self._verify_runtime_components(deadline)
        self._verify_fds(deadline)

    def _verify_host_runtime(self, deadline: Optional[float] = None) -> None:
        deadline = deadline or _operation_deadline(1200.0)
        if self.require_dedicated_host:
            swaps = Path("/proc/swaps")
            if swaps.is_file() and len(swaps.read_text(encoding="utf-8").splitlines()) > 1:
                raise RuntimeError("compute runner swap must be disabled")
            prohibited = (
                "AZURE", "OPENAI", "ANTHROPIC", "HF_TOKEN", "HUGGINGFACE",
                "AWS_", "GOOGLE_", "GITHUB_TOKEN", "GH_TOKEN",
            )
            exposed = [
                name for name in os.environ
                if any(marker in name.upper() for marker in prohibited)
            ]
            if exposed:
                raise RuntimeError("compute runner contains credential environment")
            running = self._run(
                [self.docker, "ps", "--quiet"],
                timeout=_remaining_timeout(deadline, 30.0),
                check=True,
            )
            if running.stdout.strip():
                raise RuntimeError("compute runner has another running workload")
        result = self._run(
            [self.docker, "info", "--format", "{{json .SecurityOptions}}"],
            timeout=_remaining_timeout(deadline, 30.0),
            check=True,
        )
        try:
            options = json.loads(result.stdout.decode("utf-8"))
        except Exception as exc:
            raise RuntimeError("Docker security options unavailable") from exc
        normalized = " ".join(str(option).lower() for option in options or [])
        if "apparmor" not in normalized and "selinux" not in normalized:
            raise RuntimeError("mandatory access control is unavailable")
        if self.require_rootless_or_userns and not any(
            marker in normalized for marker in ("rootless", "userns")
        ):
            raise RuntimeError("rootless Docker or user namespaces are required")

    def _verify_fds(self, deadline: Optional[float] = None) -> None:
        deadline = deadline or _operation_deadline(1200.0)
        script = (
            "import json,os;"
            "scan=lambda root:{str(i):os.readlink(root+'/'+str(i)) "
            "for i in range(256) if os.path.lexists(root+'/'+str(i))};"
            "print(json.dumps({'uid':os.geteuid(),'gid':os.getegid(),"
            "'groups':os.getgroups(),'probe_fds':scan('/proc/self/fd'),"
            "'pid1_fds':scan('/proc/1/fd')},sort_keys=True))"
        )
        result = self._run([
            self.docker, "exec", "-i", "--user", "65532:65532",
            self.container_name, "python", "-I", "-B", "-c", script,
        ], timeout=_remaining_timeout(deadline, 30.0))
        identity = json.loads(result.stdout.decode("utf-8"))
        if identity.get("uid") != 65532 or identity.get("gid") != 65532:
            raise RuntimeError("runtime UID/GID mismatch")
        if identity.get("groups") not in ([], [65532]):
            raise RuntimeError("unexpected supplementary groups")
        for process in ("probe", "pid1"):
            fds = identity.get(f"{process}_fds") or {}
            if set(fds) != {"0", "1", "2"}:
                raise RuntimeError(
                    f"unexpected inherited file descriptor: {process}"
                )
            if any("socket:" in target for target in fds.values()):
                raise RuntimeError(f"inherited socket: {process}")

    def _verify_runtime_components(
        self, deadline: Optional[float] = None
    ) -> None:
        deadline = deadline or _operation_deadline(1200.0)
        script = _runtime_component_hash_script()
        result = self._run([
            self.docker, "exec", "-i", "--user", "65532:65532",
            self.container_name, "python", "-I", "-B", "-c", script,
        ], timeout=_remaining_timeout(deadline, 30.0))
        if result.returncode != 0:
            raise RuntimeError("runtime component hashing failed")
        observed = json.loads(result.stdout.decode("utf-8"))
        expected = (
            self._verified_component_hashes
            or self._component_hashes(deadline)
        )
        for name in (
            "python_launcher", "verifier", "capabilities", "core_tree"
        ):
            if observed.get(name) != expected.get(name):
                raise RuntimeError(f"runtime component identity mismatch: {name}")
        if (
            self.require_supply_chain_identity
            and observed.get("sbom") != self.sbom_sha256
        ):
            raise RuntimeError("runtime SBOM identity mismatch")

    def _verify_verifier_image_components(
        self, deadline: Optional[float] = None
    ) -> None:
        deadline = deadline or _operation_deadline(1200.0)
        inspected = self._run(
            [self.docker, "image", "inspect", self.verifier_image],
            timeout=_remaining_timeout(deadline, 30.0),
            check=True,
        )
        documents = json.loads(inspected.stdout.decode("utf-8"))
        if len(documents) != 1:
            raise RuntimeError("verifier image inspection failed")
        self.verifier_image_id = str(documents[0].get("Id") or "")
        if not self.verifier_image_id:
            raise RuntimeError("verifier image identity missing")
        script = _runtime_component_hash_script()
        probe_name = f"{self.container_name}-component-{uuid.uuid4().hex[:8]}"
        self._may_exist_containers.add(probe_name)
        command = [
            self.docker, "run", "--name", probe_name,
            "--network", "none", "--ipc", "none",
            "--read-only", "--cap-drop", "ALL", "--user", "65532:65532",
            "--security-opt", "no-new-privileges",
            "--security-opt", f"apparmor={self.apparmor_profile}",
            "--memory", "256m", "--memory-swap", "256m",
            "--ulimit", "nofile=64:64", "--entrypoint", "python",
        ]
        if self.enforce_pid_limit:
            command += ["--pids-limit", "16"]
        if self.enforce_outer_seccomp:
            command += ["--security-opt", f"seccomp={self.seccomp_profile}"]
        if self.enforce_cpu_limit:
            command += ["--cpus", "1"]
        command += [self.verifier_image_id, "-I", "-B", "-c", script]
        try:
            result = self._run(
                command, timeout=_remaining_timeout(deadline, 60.0)
            )
        finally:
            self._remove_named_container(probe_name)
        if result.returncode != 0 or len(result.stdout) > OUTPUT_LIMIT:
            raise RuntimeError("verifier component hashing failed")
        try:
            observed = json.loads(result.stdout.decode("utf-8"))
        except Exception as exc:
            raise RuntimeError("verifier component hashing failed") from exc
        expected = self._component_hashes(deadline)
        self._verified_component_hashes = dict(expected)
        for name in ("verifier", "capabilities", "core_tree"):
            if observed.get(name) != expected.get(name):
                raise RuntimeError(
                    f"verifier image component identity mismatch: {name}"
                )
        if (
            self.require_supply_chain_identity
            and observed.get("sbom") != self.sbom_sha256
        ):
            raise RuntimeError("verifier image SBOM identity mismatch")

    def _component_hashes(
        self, deadline: Optional[float] = None
    ) -> dict[str, str]:
        core_dir = Path(__file__).resolve().parent
        sandbox_dir = core_dir.parent / "sandbox"
        components = {
            "python_launcher": core_dir / "agentic_python_launcher.py",
            "ffmpeg_mapper": Path(__file__).resolve(),
            "verifier": core_dir / "agentic_verifier.py",
            "outer_seccomp": self.seccomp_profile,
            "capabilities": sandbox_dir / "agentic-capabilities.json",
        }
        hashes = {
            name: _sha256_file(path, deadline)
            for name, path in components.items()
        }
        hashes["core_tree"] = _sha256_python_tree(core_dir, deadline)
        return hashes

    def _snapshot(
        self,
        *,
        verify: bool = False,
        selected_deliverables: Optional[list[str]] = None,
        deadline: Optional[float] = None,
    ) -> tuple[Path, Optional[dict]]:
        deadline = deadline or _operation_deadline(1200.0)
        self._assert_pid1_only(deadline)
        destination = self.snapshots_dir / f"snapshot-{uuid.uuid4().hex}"
        helper_name = f"{self.container_name}-snapshot-{uuid.uuid4().hex[:8]}"
        verification = None
        pause_may_have_applied = False
        try:
            pause_timeout = _remaining_timeout(deadline, 30.0)
            pause_may_have_applied = True
            self._run(
                [self.docker, "pause", self.container_name],
                timeout=pause_timeout,
                check=True,
            )
            destination.mkdir(mode=0o700)
            if verify:
                verification = self._verify_work_volume(
                    selected_deliverables, deadline
                )
            self._may_exist_containers.add(helper_name)
            helper_command = [
                self.docker, "run", "--detach", "--rm", "--name", helper_name,
                "--network", "none", "--ipc", "none", "--read-only",
                "--cap-drop", "ALL", "--memory", "512m", "--memory-swap", "512m",
                "--ulimit", "nofile=128:128", "--user", "65532:65532",
                "--security-opt", "no-new-privileges",
                "--security-opt", f"apparmor={self.apparmor_profile}",
                "--mount", (
                    f"type=volume,src={self.work_volume_name},dst=/snapshot,"
                    "readonly,volume-nocopy"
                ),
            ]
            if self.enforce_pid_limit:
                helper_command += ["--pids-limit", "32"]
            if self.enforce_outer_seccomp:
                helper_command += [
                    "--security-opt", f"seccomp={self.seccomp_profile}"
                ]
            if self.enforce_cpu_limit:
                helper_command += ["--cpus", "0.5"]
            helper_command += [
                self.image, "-c", "import signal;signal.pause()"
            ]
            self._run(
                helper_command,
                timeout=_remaining_timeout(deadline, 60.0),
                check=True,
            )
            self._run(
                [self.docker, "cp", f"{helper_name}:/snapshot/.", str(destination)],
                timeout=_remaining_timeout(deadline, 120.0),
                check=True,
            )
        finally:
            if pause_may_have_applied:
                self._cleanup_snapshot_resources(helper_name)
        self._strict_snapshot_files(destination, deadline)
        return destination, verification

    def _cleanup_snapshot_resources(self, helper_name: str) -> None:
        failures = []
        if helper_name in self._may_exist_containers:
            try:
                self._remove_named_container(helper_name)
            except Exception as exc:
                failures.append(str(exc))
        try:
            unpaused = self._run(
                [self.docker, "unpause", self.container_name], timeout=30
            )
            if unpaused.returncode != 0:
                failures.append("task container unpause failed")
        except Exception:
            failures.append("task container unpause failed")
        if failures:
            self.poisoned = True
            try:
                self._remove_container()
            except Exception:
                pass
            raise RuntimeError("; ".join(failures))

    def _strict_snapshot_files(
        self, snapshot: Path, deadline: Optional[float] = None
    ) -> list[Path]:
        files: list[Path] = []
        total_logical = 0
        total_allocated = 0
        for path in sorted(snapshot.rglob("*")):
            if deadline is not None:
                _remaining_timeout(deadline, 1200.0)
            relative = path.relative_to(snapshot)
            if len(relative.parts) > MAX_DEPTH or len(relative.as_posix().encode("utf-8")) > MAX_PATH_BYTES:
                raise ValueError("workspace_path_limit")
            metadata = path.lstat()
            if stat.S_ISDIR(metadata.st_mode):
                continue
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                raise ValueError("workspace_type_or_link_violation")
            total_logical += metadata.st_size
            total_allocated += metadata.st_blocks * 512
            if metadata.st_size > MAX_WORK_SINGLE:
                raise ValueError("workspace_single_file_limit")
            if total_logical > MAX_WORK_TOTAL or total_allocated > MAX_WORK_TOTAL:
                raise ValueError("workspace_total_size_limit")
            files.append(path)
            if len(files) > MAX_WORK_FILES:
                raise ValueError("workspace_file_count_limit")
        return files

    def _verify_work_volume(
        self,
        selected_deliverables: Optional[list[str]] = None,
        deadline: Optional[float] = None,
    ) -> dict:
        request = {
            "task_prompt": self.task_prompt,
            "reference_hashes": sorted(self.input_hashes),
        }
        if selected_deliverables is not None:
            request["selected_deliverables"] = list(selected_deliverables)
        payload = json.dumps(request, separators=(",", ":")).encode("utf-8")
        verifier_name = f"{self.container_name}-verify-{uuid.uuid4().hex[:8]}"
        self._may_exist_containers.add(verifier_name)
        command = [
            self.docker, "run", "--name", verifier_name, "-i",
            "--network", "none", "--ipc", "none",
            "--read-only", "--cap-drop", "ALL",
            "--memory", "2g", "--memory-swap", "2g",
            "--ulimit", "nofile=128:128", "--user", "65532:65532",
            "--security-opt", "no-new-privileges",
            "--security-opt", f"apparmor={self.apparmor_profile}",
            "--env", "HOME=/verify-work/.home",
            "--env", "TMPDIR=/verify-work/.tmp",
            "--env", "XDG_CACHE_HOME=/verify-work/.cache",
            "--env", "XDG_CONFIG_HOME=/verify-work/.config",
            "--env", "MPLCONFIGDIR=/verify-work/.cache/matplotlib",
            "--mount", (
                f"type=volume,src={self.work_volume_name},dst=/snapshot,"
                "readonly,volume-nocopy"
            ),
            "--tmpfs", "/verify-work:rw,nosuid,nodev,noexec,size=134217728,nr_inodes=512,uid=65532,gid=65532,mode=700",
            "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,size=67108864,nr_inodes=256,uid=65532,gid=65532,mode=700",
        ]
        if self.enforce_pid_limit:
            command += ["--pids-limit", "64"]
        if self.enforce_outer_seccomp:
            command += ["--security-opt", f"seccomp={self.seccomp_profile}"]
        if self.enforce_cpu_limit:
            command += ["--cpus", "1"]
        command += [
            self.verifier_image_id,
            "-c",
            (
                "import runpy,sys;sys.path.insert(0,'/opt/gdpval');"
                "runpy.run_module('core.agentic_verifier',run_name='__main__')"
            ),
        ]
        deadline = deadline or _operation_deadline(1200.0)
        try:
            result = self._run(
                command,
                input_data=payload,
                timeout=_remaining_timeout(deadline, 180.0),
            )
        finally:
            try:
                self._remove_named_container(verifier_name)
            except Exception as exc:
                self.poisoned = True
                raise RuntimeError("verifier container cleanup failed") from exc
        if result.returncode != 0 or len(result.stdout) > OUTPUT_LIMIT:
            return _error("verifier_container_failed")
        try:
            verification = json.loads(result.stdout.decode("utf-8"))
        except Exception:
            return _error("verifier_result_invalid")
        if not isinstance(verification, dict) or verification.get("ok") not in (True, False):
            return _error("verifier_result_invalid")
        return verification

    def _verification_matches_snapshot(
        self,
        verification: Mapping[str, Any],
        snapshot: Path,
        selected_deliverables: Optional[list[str]] = None,
        deadline: Optional[float] = None,
    ) -> bool:
        data = verification.get("data")
        artifacts = data.get("artifacts") if isinstance(data, Mapping) else None
        if not isinstance(artifacts, list):
            return False
        expected = {
            item.get("path"): item.get("sha256")
            for item in artifacts
            if isinstance(item, Mapping)
            and isinstance(item.get("path"), str)
            and isinstance(item.get("sha256"), str)
        }
        actual = {}
        selected = (
            set(selected_deliverables)
            if selected_deliverables is not None
            else None
        )
        for path in self._strict_snapshot_files(snapshot, deadline):
            relative = path.relative_to(snapshot)
            if _is_internal(relative):
                continue
            if selected is not None and relative.as_posix() not in selected:
                continue
            actual[relative.as_posix()] = _sha256_file(path, deadline)
        return (
            expected == actual
            and bool(actual)
            and (selected is None or set(actual) == selected)
        )

    def _ffmpeg_command(self, operation: Mapping[str, Any]) -> list[str]:
        name = str(operation["operation"])
        input_suffix = Path(str(operation["input"])).suffix.lower()
        if input_suffix not in FFMPEG_INPUT_SUFFIXES:
            raise ValueError("unsupported ffmpeg input suffix")
        source = _container_path(str(operation["input"]), output=False)
        base = [
            self.docker, "exec", "-i", "--user", "65532:65532",
            self.container_name,
        ]
        if name == "probe":
            return base + [
                "/usr/bin/ffprobe", "-v", "error", "-show_format", "-show_streams",
                "-protocol_whitelist", "file", "-of", "json", source,
            ]
        output = _container_path(str(operation["output"]), output=True)
        output_suffix = Path(output).suffix.lower()
        expected_suffix = {
            "extract_audio": f".{operation.get('format')}",
            "transcode_audio": f".{operation.get('format')}",
            "transcode_video": f".{operation.get('container')}",
            "sample_frames": ".png",
        }.get(name)
        if output_suffix != expected_suffix:
            raise ValueError("ffmpeg output extension differs from declared format")
        timing = [
            "-ss", str(operation["start_seconds"]),
            "-t", str(operation["duration_seconds"]),
        ]
        command = base + [
            "/usr/bin/ffmpeg", "-nostdin", "-n", "-hide_banner", "-loglevel", "error",
            "-protocol_whitelist", "file", *timing, "-i", source,
        ]
        if name in {"extract_audio", "transcode_audio"}:
            codec = "pcm_s16le" if operation["format"] == "wav" else "flac"
            command += [
                "-vn", "-ac", str(operation["channels"]), "-ar",
                str(operation["sample_rate"]), "-c:a", codec, output,
            ]
        elif name == "transcode_video":
            video_codec = "libx264" if operation["video_codec"] == "h264" else "libvpx-vp9"
            audio_codec = "aac" if operation["audio_codec"] == "aac" else "libopus"
            command += [
                "-vf", f"scale={operation['width']}:{operation['height']}",
                "-r", str(operation["fps"]), "-c:v", video_codec,
                "-c:a", audio_codec, output,
            ]
        elif name == "sample_frames":
            columns = min(4, int(operation["frame_count"]))
            rows = math.ceil(int(operation["frame_count"]) / columns)
            rate = float(operation["frame_count"]) / float(operation["duration_seconds"])
            command += [
                "-vf", f"fps={rate:.8f},scale={operation['width']}:-2,tile={columns}x{rows}",
                "-frames:v", "1", output,
            ]
        else:
            raise ValueError("unknown ffmpeg operation")
        return command

    def _assert_pid1_only(self, deadline: Optional[float] = None) -> None:
        script = (
            "import os;"
            "pids={name for name in os.listdir('/proc') if name.isdigit()};"
            "expected={'1',str(os.getpid())};"
            "assert pids==expected,(pids,expected);print('ok')"
        )
        result = self._run([
            self.docker, "exec", "-i", "--user", "65532:65532",
            self.container_name, "python", "-I", "-B", "-c", script,
        ], timeout=_remaining_timeout(
            deadline or _operation_deadline(30.0), 30.0
        ))
        if result.returncode != 0 or result.stdout.strip() != b"ok":
            raise RuntimeError("task container has descendant processes")

    def _docker_path(self, local_path: Path) -> Path:
        relative = local_path.resolve().relative_to(self.root.resolve())
        return self.docker_root / relative

    def _ready(self) -> bool:
        return self.container_started and not self.poisoned

    def _remove_container(self) -> None:
        if (
            not self.container_started
            and self.container_name not in self._may_exist_containers
        ):
            return
        self._remove_named_container(self.container_name)
        self.container_started = False

    def _create_work_volume(self, deadline: Optional[float] = None) -> None:
        deadline = deadline or _operation_deadline(1200.0)
        self._may_exist_volumes.add(self.work_volume_name)
        result = self._run([
            self.docker, "volume", "create", "--driver", "local",
            "--opt", "type=tmpfs", "--opt", "device=tmpfs",
            "--opt", (
                "o=size=536870912,nr_inodes=1024,uid=65532,gid=65532,"
                "nosuid,nodev,noexec"
            ),
            self.work_volume_name,
        ], timeout=_remaining_timeout(deadline, 30.0))
        if result.returncode != 0:
            raise RuntimeError("work volume creation failed")
        created_name = result.stdout.decode("utf-8", errors="replace").strip()
        if created_name != self.work_volume_name:
            raise RuntimeError("unexpected work volume identity")
        self.work_volume_created = True

    def _remove_work_volume(self) -> None:
        if (
            not self.work_volume_created
            and self.work_volume_name not in self._may_exist_volumes
        ):
            return
        self._remove_named_volume(self.work_volume_name)
        self.work_volume_created = False

    def _remove_named_container(self, name: str) -> None:
        result = self._run(
            [self.docker, "rm", "-f", name], timeout=30
        )
        if result.returncode != 0:
            inspected = self._run(
                [self.docker, "inspect", name], timeout=30
            )
            if inspected.returncode == 0:
                self.poisoned = True
                raise RuntimeError(f"container cleanup failed: {name}")
            if not _docker_not_found(inspected.stderr, "container"):
                self.poisoned = True
                raise RuntimeError(
                    f"container cleanup could not be verified: {name}"
                )
        self._may_exist_containers.discard(name)

    def _remove_named_volume(self, name: str) -> None:
        result = self._run(
            [self.docker, "volume", "rm", "-f", name], timeout=30
        )
        if result.returncode != 0:
            inspected = self._run(
                [self.docker, "volume", "inspect", name], timeout=30
            )
            if inspected.returncode == 0:
                self.poisoned = True
                raise RuntimeError(f"volume cleanup failed: {name}")
            if not _docker_not_found(inspected.stderr, "volume"):
                self.poisoned = True
                raise RuntimeError(
                    f"volume cleanup could not be verified: {name}"
                )
        self._may_exist_volumes.discard(name)

    @staticmethod
    def _run(
        command: list[str],
        *,
        input_data: Optional[bytes] = None,
        timeout: float,
        check: bool = False,
    ) -> subprocess.CompletedProcess:
        result = subprocess.run(
            command,
            input=input_data,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
            env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "C.UTF-8"},
        )
        if check and result.returncode != 0:
            raise RuntimeError("compute command failed")
        return result

    @staticmethod
    def _run_tool(
        command: list[str],
        *,
        input_data: Optional[bytes] = None,
        timeout: float,
    ) -> subprocess.CompletedProcess:
        import resource

        def limit_output_files() -> None:
            resource.setrlimit(
                resource.RLIMIT_FSIZE,
                (OUTPUT_LIMIT, OUTPUT_LIMIT),
            )

        with tempfile.TemporaryFile() as stdout_file, tempfile.TemporaryFile() as stderr_file:
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE if input_data is not None else subprocess.DEVNULL,
                stdout=stdout_file,
                stderr=stderr_file,
                env={
                    "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                    "LANG": "C.UTF-8",
                },
                preexec_fn=limit_output_files,
            )
            try:
                process.communicate(input=input_data, timeout=max(0.001, timeout))
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()
                raise
            stdout_file.seek(0)
            stderr_file.seek(0)
            return subprocess.CompletedProcess(
                command,
                process.returncode,
                stdout_file.read(OUTPUT_LIMIT),
                stderr_file.read(OUTPUT_LIMIT),
            )


def _open_regular_nofollow(path: Path) -> int:
    absolute = path.absolute()
    if not absolute.is_absolute() or len(absolute.parts) < 2:
        raise OSError("input path must identify a file")
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    cloexec = getattr(os, "O_CLOEXEC", 0)
    nonblock = getattr(os, "O_NONBLOCK", 0)
    directory = os.open(absolute.anchor, directory_flags | cloexec)
    try:
        for part in absolute.parts[1:-1]:
            child = os.open(
                part,
                directory_flags | nofollow | cloexec,
                dir_fd=directory,
            )
            os.close(directory)
            directory = child
        return os.open(
            absolute.parts[-1],
            os.O_RDONLY | nofollow | cloexec | nonblock,
            dir_fd=directory,
        )
    finally:
        os.close(directory)


def _open_regular_beneath_nofollow(root: Path, relative: Path) -> int:
    if (
        relative.is_absolute()
        or not relative.parts
        or ".." in relative.parts
        or any(part in {"", "."} for part in relative.parts)
    ):
        raise OSError("input source path is invalid")
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    cloexec = getattr(os, "O_CLOEXEC", 0)
    nonblock = getattr(os, "O_NONBLOCK", 0)
    directory = os.open(
        root.absolute(), directory_flags | nofollow | cloexec
    )
    expected_mount = _descriptor_mount_id(directory)
    try:
        for part in relative.parts[:-1]:
            child = os.open(
                part,
                directory_flags | nofollow | cloexec,
                dir_fd=directory,
            )
            if _descriptor_mount_id(child) != expected_mount:
                os.close(child)
                raise OSError("input source crosses a mount boundary")
            os.close(directory)
            directory = child
        descriptor = os.open(
            relative.parts[-1],
            os.O_RDONLY | nofollow | cloexec | nonblock,
            dir_fd=directory,
        )
        if _descriptor_mount_id(descriptor) != expected_mount:
            os.close(descriptor)
            raise OSError("input source crosses a mount boundary")
        return descriptor
    finally:
        os.close(directory)


def _descriptor_mount_id(descriptor: int) -> int:
    path = Path(f"/proc/self/fdinfo/{descriptor}")
    try:
        lines = path.read_text(encoding="ascii").splitlines()
    except OSError as exc:
        raise OSError("input mount identity is unavailable") from exc
    for line in lines:
        if line.startswith("mnt_id:"):
            try:
                return int(line.split(":", 1)[1].strip())
            except ValueError as exc:
                raise OSError("input mount identity is invalid") from exc
    try:
        target_value = os.readlink(f"/proc/self/fd/{descriptor}")
        if target_value.endswith(" (deleted)"):
            raise OSError("input descriptor target was deleted")
        target = Path(target_value)
        if not target.is_absolute():
            raise OSError("input descriptor target is not absolute")
        mount_lines = Path("/proc/self/mountinfo").read_text(
            encoding="utf-8"
        ).splitlines()
    except OSError as exc:
        raise OSError("input mount identity is unavailable") from exc
    matches = []
    for line in mount_lines:
        fields = line.split()
        if len(fields) < 6:
            continue
        try:
            mount_id = int(fields[0])
        except ValueError:
            continue
        mount_value = re.sub(
            r"\\([0-7]{3})",
            lambda match: chr(int(match.group(1), 8)),
            fields[4],
        )
        mountpoint = Path(mount_value)
        try:
            target.relative_to(mountpoint)
        except ValueError:
            continue
        matches.append((len(mountpoint.parts), mount_id))
    if not matches:
        raise OSError("input mount identity is unavailable")
    return max(matches)[1]


def _operation_deadline(timeout_seconds: float) -> float:
    if (
        isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, (int, float))
        or not math.isfinite(float(timeout_seconds))
        or not 0 < float(timeout_seconds) <= 1200.0
    ):
        raise ValueError("operation timeout must be in (0, 1200]")
    return time.monotonic() + float(timeout_seconds)


def _source_identity(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_nlink,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _sha256_descriptor(
    descriptor: int, deadline: Optional[float] = None
) -> str:
    digest = hashlib.sha256()
    os.lseek(descriptor, 0, os.SEEK_SET)
    while True:
        if deadline is not None:
            _remaining_timeout(deadline, 1200.0)
        chunk = os.read(descriptor, 65536)
        if not chunk:
            break
        digest.update(chunk)
    return digest.hexdigest()


def _remaining_timeout(deadline: float, maximum: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("task wall time exhausted")
    return max(0.001, min(float(maximum), remaining))


def _normalize_probe_metadata(payload: bytes) -> dict[str, Any]:
    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite ffprobe value: {value}")

    parsed = json.loads(payload.decode("utf-8"), parse_constant=reject_constant)
    if not isinstance(parsed, dict):
        raise ValueError("ffprobe result must be an object")
    format_fields = {
        "format_name", "format_long_name", "start_time", "duration", "size",
        "bit_rate", "probe_score", "nb_streams", "nb_programs",
    }
    stream_fields = {
        "index", "codec_name", "codec_long_name", "profile", "codec_type",
        "codec_tag_string", "width", "height", "coded_width", "coded_height",
        "pix_fmt", "level", "color_range", "color_space", "color_transfer",
        "color_primaries", "chroma_location", "field_order", "refs",
        "r_frame_rate", "avg_frame_rate", "time_base", "start_pts",
        "start_time", "duration_ts", "duration", "bit_rate",
        "bits_per_raw_sample", "nb_frames", "sample_fmt", "sample_rate",
        "channels", "channel_layout", "bits_per_sample", "id",
    }

    def allowed(source: object, fields: set[str]) -> dict[str, Any]:
        if not isinstance(source, Mapping):
            return {}
        output: dict[str, Any] = {}
        for key in sorted(fields):
            value = source.get(key)
            if isinstance(value, bool):
                continue
            if isinstance(value, int):
                output[key] = value
            elif isinstance(value, str) and len(value) <= 256:
                output[key] = value
        return output

    raw_streams = parsed.get("streams")
    if raw_streams is None:
        raw_streams = []
    if not isinstance(raw_streams, list) or len(raw_streams) > 64:
        raise ValueError("ffprobe stream count is invalid")
    return {
        "format": allowed(parsed.get("format"), format_fields),
        "streams": [allowed(stream, stream_fields) for stream in raw_streams],
    }


def _normalize_model_path(raw: str, *, output: bool) -> str:
    path = Path(raw)
    if path.is_absolute() or ".." in path.parts or any(part.startswith(".") for part in path.parts):
        raise ValueError("unsafe path")
    parts = path.parts
    if output:
        if parts and parts[0] == "work":
            parts = parts[1:]
        if not parts or (parts and parts[0] == "inputs"):
            raise ValueError("output must resolve under work")
    else:
        if not parts or parts[0] not in {"inputs", "work"}:
            raise ValueError("input must start with inputs/ or work/")
    relative = Path(*parts).as_posix()
    if not relative or len(relative.encode("utf-8")) > MAX_PATH_BYTES:
        raise ValueError("unsafe path")
    return relative


def _container_path(raw: str, *, output: bool) -> str:
    relative = _normalize_model_path(raw, output=output)
    if output:
        return f"/work/{relative}"
    prefix = Path(raw).parts[0]
    return f"/{prefix}/{Path(*Path(raw).parts[1:]).as_posix()}"


def _is_internal(relative: Path) -> bool:
    return any(part.startswith(".") for part in relative.parts)


def _bounded_text(value: bytes) -> str:
    return value[-OUTPUT_LIMIT:].decode("utf-8", errors="replace")


def _error(error_type: str) -> dict:
    return {"ok": False, "error_type": error_type, "retryable": False}


def _sha256_file(
    path: Path, deadline: Optional[float] = None
) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            if deadline is not None:
                _remaining_timeout(deadline, 1200.0)
            digest.update(chunk)
    return digest.hexdigest()


def _docker_not_found(stderr: bytes, resource: str) -> bool:
    text = stderr.decode("utf-8", errors="replace").lower()
    markers = {
        "container": ("no such object", "no such container"),
        "volume": ("no such volume",),
    }
    return any(marker in text for marker in markers[resource])


def _sha256_python_tree(
    root: Path, deadline: Optional[float] = None
) -> str:
    digest = hashlib.sha256(b"gdpval-core-tree-v1\0")
    for path in sorted(root.rglob("*.py"), key=lambda item: item.as_posix()):
        if deadline is not None:
            _remaining_timeout(deadline, 1200.0)
        relative = path.relative_to(root).as_posix().encode("utf-8")
        content = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def _runtime_component_hash_script() -> str:
    return """
import hashlib
import json
import pathlib

core = pathlib.Path('/opt/gdpval/core')
paths = {
    'python_launcher': core / 'agentic_python_launcher.py',
    'verifier': core / 'agentic_verifier.py',
    'capabilities': pathlib.Path('/opt/gdpval/agentic-capabilities.json'),
    'sbom': pathlib.Path('/opt/gdpval/agentic-sbom.spdx.json'),
}
observed = {
    name: hashlib.sha256(path.read_bytes()).hexdigest()
    for name, path in paths.items()
}
tree = hashlib.sha256(b'gdpval-core-tree-v1\\0')
for path in sorted(core.rglob('*.py'), key=lambda item: item.as_posix()):
    relative = path.relative_to(core).as_posix().encode('utf-8')
    content = path.read_bytes()
    tree.update(len(relative).to_bytes(8, 'big'))
    tree.update(relative)
    tree.update(len(content).to_bytes(8, 'big'))
    tree.update(content)
observed['core_tree'] = tree.hexdigest()
print(json.dumps(observed, sort_keys=True))
"""