"""Build and verify a local-only Phase 1B candidate from a clean source tree."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import signal
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path


_STAGED_ROOT_ENV = "GDPVAL_AGENTIC_V2_STAGED_BUILDER_ROOT"
_REPOSITORY_ROOT_ENV = "GDPVAL_AGENTIC_V2_REPOSITORY_ROOT"
_SOURCE_REVISION_ENV = "GDPVAL_AGENTIC_V2_SOURCE_REVISION"
_RUNTIME_ROOT_ENV = "GDPVAL_AGENTIC_V2_LICENSE_RUNTIME_ROOT"
_TRUSTED_PATH = "/usr/bin:/bin"
_TRUSTED_GIT = "/usr/bin/git"
_TRUSTED_DOCKER = "/usr/bin/docker"
_BOOTSTRAP_FORBIDDEN_ENV = (
    "AZURE_CLIENT_SECRET",
    "AZURE_OPENAI_API_KEY",
    "DOCKER_AUTH_CONFIG",
    "GITHUB_TOKEN",
    "HF_TOKEN",
    "OPENAI_API_KEY",
)
_BUILDER_SOURCE_PATHS = (
    "batch-runner/core/agentic_v2_license.py",
    "batch-runner/core/agentic_v2_oci.py",
    "batch-runner/core/agentic_v2_substrate.py",
    "batch-runner/sandbox/v2/build_candidate.py",
)
BATCH_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = (
    Path(os.environ[_REPOSITORY_ROOT_ENV]).resolve(strict=True)
    if __name__ == "__main__" and os.getenv(_STAGED_ROOT_ENV)
    else BATCH_ROOT.parent
)
_BOOTSTRAP_RUNTIME_FILES = {
    "packaging/__init__.py": (
        494,
        "42130474fbb65e882b2735774b42964bab7b97423d93c11e0d1265e1f9f0f3bb",
    ),
    "packaging/licenses/__init__.py": (
        7293,
        "fc9c745d1883ff9f296a5b169f22eb2ee879f59a4608f20f5cb29d668f4e26f4",
    ),
    "packaging/licenses/_spdx.py": (
        51122,
        "596ec35e2ca0ebcba9fd8343ff0a51625af548786257815f24b41f7e08613314",
    ),
}


def _bootstrap_file_identity(item) -> tuple[int, ...]:
    return (
        item.st_dev,
        item.st_ino,
        item.st_mode,
        item.st_nlink,
        item.st_size,
        item.st_mtime_ns,
    )


def _require_trusted_executable(path: str) -> None:
    executable = Path(path)
    if executable not in {Path(_TRUSTED_GIT), Path(_TRUSTED_DOCKER)}:
        raise RuntimeError("candidate builder executable is not allowlisted")
    for directory in (Path("/usr"), Path("/usr/bin")):
        metadata = directory.lstat()
        if (
            not stat.S_ISDIR(metadata.st_mode)
            or stat.S_ISLNK(metadata.st_mode)
            or metadata.st_uid != 0
            or metadata.st_mode & 0o022
        ):
            raise RuntimeError("candidate builder trusted tool directory is invalid")
    metadata = executable.lstat()
    if (
        not stat.S_ISREG(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or metadata.st_uid != 0
        or metadata.st_mode & 0o022
        or not metadata.st_mode & 0o111
    ):
        raise RuntimeError("candidate builder trusted executable is invalid")


def _bootstrap_runtime_matches(root: Path) -> bool:
    try:
        for directory in (root, root / "packaging", root / "packaging" / "licenses"):
            metadata = directory.lstat()
            if not stat.S_ISDIR(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
                return False
        for relative_path, (expected_size, expected_sha256) in (
            _BOOTSTRAP_RUNTIME_FILES.items()
        ):
            descriptor = os.open(
                root / relative_path,
                os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
            )
            try:
                before = os.fstat(descriptor)
                if (
                    not stat.S_ISREG(before.st_mode)
                    or before.st_nlink != 1
                    or before.st_size != expected_size
                ):
                    return False
                chunks = []
                while True:
                    chunk = os.read(descriptor, 64 * 1024)
                    if not chunk:
                        break
                    chunks.append(chunk)
                after = os.fstat(descriptor)
            finally:
                os.close(descriptor)
            value = b"".join(chunks)
            if (
                _bootstrap_file_identity(before) != _bootstrap_file_identity(after)
                or len(value) != expected_size
                or hashlib.sha256(value).hexdigest() != expected_sha256
            ):
                return False
    except OSError:
        return False
    return True


def _bootstrap_staged_runtime_matches(root: Path) -> bool:
    if not _bootstrap_runtime_matches(root):
        return False
    expected_files = set(_BOOTSTRAP_RUNTIME_FILES)
    actual_files = set()
    try:
        for path in root.rglob("*"):
            if path.is_symlink():
                return False
            if path.is_file():
                actual_files.add(str(path.relative_to(root)))
    except OSError:
        return False
    return actual_files == expected_files


def _bootstrap_git_environment() -> dict[str, str]:
    return {
        "PATH": _TRUSTED_PATH,
        "HOME": "/nonexistent",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_TERMINAL_PROMPT": "0",
    }


def _bootstrap_git(repository_root: Path, *arguments: str) -> bytes:
    _require_trusted_executable(_TRUSTED_GIT)
    return subprocess.run(
        [
            _TRUSTED_GIT, "--no-replace-objects",
            "-c", "core.fsmonitor=false",
            "-c", "core.hooksPath=/dev/null",
            "-C", str(repository_root),
            *arguments,
        ],
        env=_bootstrap_git_environment(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
        check=True,
    ).stdout


def _bootstrap_git_blob(
    repository_root: Path,
    source_revision: str,
    repository_path: str,
) -> bytes:
    return _bootstrap_git(
        repository_root,
        "show",
        f"{source_revision}:{repository_path}",
    )


def _bootstrap_stage_sources(
    repository_root: Path,
    source_revision: str,
    root: Path,
) -> None:
    for repository_path in _BUILDER_SOURCE_PATHS:
        destination = root / repository_path.removeprefix("batch-runner/")
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        destination.write_bytes(_bootstrap_git_blob(
            repository_root,
            source_revision,
            repository_path,
        ))


def _bootstrap_copy_runtime(source_root: Path, destination_root: Path) -> None:
    if not _bootstrap_runtime_matches(source_root):
        raise RuntimeError("candidate builder packaging runtime differs")
    for relative_path, (expected_size, expected_sha256) in (
        _BOOTSTRAP_RUNTIME_FILES.items()
    ):
        source = source_root / relative_path
        descriptor = os.open(
            source,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
        )
        try:
            before = os.fstat(descriptor)
            chunks = []
            while True:
                chunk = os.read(descriptor, 64 * 1024)
                if not chunk:
                    break
                chunks.append(chunk)
            after = os.fstat(descriptor)
        finally:
            os.close(descriptor)
        value = b"".join(chunks)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or _bootstrap_file_identity(before) != _bootstrap_file_identity(after)
            or len(value) != expected_size
            or hashlib.sha256(value).hexdigest() != expected_sha256
        ):
            raise RuntimeError("candidate builder runtime changed while staging")
        destination = destination_root / relative_path
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        destination.write_bytes(value)
    if not _bootstrap_staged_runtime_matches(destination_root):
        raise RuntimeError("staged candidate builder packaging runtime differs")


def _bootstrap_runtime_root() -> Path:
    executable = Path(sys.executable)
    if not executable.is_absolute() or ".." in executable.parts:
        raise RuntimeError("candidate builder Python executable path is invalid")
    executable_prefix = executable.parent.parent
    python_directory = f"python{sys.version_info.major}.{sys.version_info.minor}"
    candidates = [
        executable_prefix / "lib" / python_directory / name
        for name in ("site-packages", "dist-packages")
    ]
    runtime_roots = [path for path in candidates if _bootstrap_runtime_matches(path)]
    if len(runtime_roots) != 1:
        raise RuntimeError("candidate builder packaging runtime root is ambiguous")
    return runtime_roots[0]


def _bootstrap_validate_staged_sources(
    staged_root: Path,
    repository_root: Path,
    source_revision: str,
) -> None:
    if Path(__file__).resolve(strict=True) != (
        staged_root / "sandbox" / "v2" / "build_candidate.py"
    ):
        raise RuntimeError("candidate builder staged entrypoint identity differs")
    expected_files = {
        repository_path.removeprefix("batch-runner/")
        for repository_path in _BUILDER_SOURCE_PATHS
    }
    actual_files = set()
    for path in staged_root.rglob("*"):
        if path.is_symlink():
            raise RuntimeError("candidate builder staged source contains a symlink")
        if path.is_file():
            actual_files.add(str(path.relative_to(staged_root)))
    if actual_files != expected_files:
        raise RuntimeError("candidate builder staged source inventory differs")
    for repository_path in _BUILDER_SOURCE_PATHS:
        staged_path = staged_root / repository_path.removeprefix("batch-runner/")
        expected = _bootstrap_git_blob(
            repository_root,
            source_revision,
            repository_path,
        )
        descriptor = os.open(
            staged_path,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
        )
        try:
            before = os.fstat(descriptor)
            chunks = []
            while True:
                chunk = os.read(descriptor, 64 * 1024)
                if not chunk:
                    break
                chunks.append(chunk)
            after = os.fstat(descriptor)
        finally:
            os.close(descriptor)
        value = b"".join(chunks)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or _bootstrap_file_identity(before) != _bootstrap_file_identity(after)
            or len(value) != before.st_size
            or value != expected
        ):
            raise RuntimeError("candidate builder staged source differs from Git")


def _bootstrap_builder_imports() -> Path:
    if (
        sys.flags.isolated != 1
        or sys.flags.no_site != 1
        or not sys.dont_write_bytecode
    ):
        raise RuntimeError(
            "candidate builder requires isolated no-site no-bytecode startup"
        )
    staged_root = Path(os.environ[_STAGED_ROOT_ENV]).resolve(strict=True)
    runtime_root = Path(os.environ[_RUNTIME_ROOT_ENV]).resolve(strict=True)
    source_revision = os.environ[_SOURCE_REVISION_ENV]
    if not re.fullmatch(r"[0-9a-f]{40}", source_revision):
        raise RuntimeError("candidate builder staged revision is invalid")
    if not _bootstrap_staged_runtime_matches(runtime_root):
        raise RuntimeError("candidate builder staged runtime differs")
    _bootstrap_validate_staged_sources(
        staged_root,
        REPOSITORY_ROOT,
        source_revision,
    )
    existing = [
        item
        for item in sys.path
        if item and Path(item).resolve() not in {Path.cwd().resolve(), BATCH_ROOT}
    ]
    sys.path[:] = [str(runtime_root), str(staged_root), *existing]
    return runtime_root


def _launch_staged_builder() -> int:
    if any(os.getenv(name) for name in _BOOTSTRAP_FORBIDDEN_ENV):
        raise RuntimeError("candidate builder refuses credential-bearing environment")
    repository_root = BATCH_ROOT.parent.resolve(strict=True)
    source_revision = _bootstrap_git(
        repository_root,
        "rev-parse",
        "HEAD",
    ).decode("ascii").strip()
    if re.fullmatch(r"[0-9a-f]{40}", source_revision) is None:
        raise RuntimeError("candidate builder source revision is invalid")
    if _bootstrap_git(
        repository_root,
        "status",
        "--porcelain",
        "--untracked-files=all",
    ):
        raise RuntimeError("candidate builder requires a clean source tree")
    runtime_source = _bootstrap_runtime_root()
    with tempfile.TemporaryDirectory(
        prefix="agentic-v2-staged-builder-"
    ) as temporary:
        temporary_root = Path(temporary)
        staged_root = temporary_root / "batch-runner"
        runtime_root = temporary_root / "license-runtime"
        _bootstrap_stage_sources(repository_root, source_revision, staged_root)
        _bootstrap_copy_runtime(runtime_source, runtime_root)
        environment = {
            "PATH": _TRUSTED_PATH,
            "HOME": "/nonexistent",
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",
            _STAGED_ROOT_ENV: str(staged_root),
            _RUNTIME_ROOT_ENV: str(runtime_root),
            _REPOSITORY_ROOT_ENV: str(repository_root),
            _SOURCE_REVISION_ENV: source_revision,
        }
        if os.getenv("DOCKER_HOST"):
            environment["DOCKER_HOST"] = os.environ["DOCKER_HOST"]
        completed = subprocess.run(
            [
                sys.executable,
                "-I",
                "-S",
                "-B",
                str(staged_root / "sandbox" / "v2" / "build_candidate.py"),
                *sys.argv[1:],
            ],
            cwd=staged_root,
            env=environment,
            stdin=subprocess.DEVNULL,
            check=False,
        )
        return completed.returncode


if __name__ == "__main__" and not os.getenv(_STAGED_ROOT_ENV):
    if (
        sys.flags.isolated != 1
        or sys.flags.no_site != 1
        or not sys.dont_write_bytecode
    ):
        raise RuntimeError(
            "candidate builder requires isolated no-site no-bytecode startup"
        )
    raise SystemExit(_launch_staged_builder())

_BOOTSTRAPPED_RUNTIME_ROOT = (
    _bootstrap_builder_imports() if __name__ == "__main__" else None
)
if _BOOTSTRAPPED_RUNTIME_ROOT is None and str(BATCH_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_ROOT))

import packaging  # noqa: E402

from core.agentic_v2_oci import export_docker_archive_to_oci  # noqa: E402
from core.agentic_v2_license import (  # noqa: E402
    LICENSE_EVALUATOR_RUNTIME_GRAPH_SHA256,
    license_evaluator_runtime_identity,
)
from core.agentic_v2_substrate import AgenticV2SubstrateManifest  # noqa: E402
from core.agentic_v2_substrate import (  # noqa: E402
    AGENTIC_V2_IMAGE_PROBE_COUNT,
    AGENTIC_V2_IMAGE_PROBE_TIMEOUT_SECONDS,
    AGENTIC_V2_VERIFICATION_SESSION_INVENTORY_TIMEOUT_SECONDS,
    AGENTIC_V2_VERIFICATION_SESSION_MAX_CONTAINERS,
    AGENTIC_V2_VERIFICATION_SESSION_REMOVE_TIMEOUT_SECONDS,
    AGENTIC_V2_VERIFICATION_SESSION_SWEEP_LIMIT,
    AGENTIC_V2_VERIFIER_OVERHEAD_SECONDS,
)
AGENTIC_V2_VERIFIER_TIMEOUT_SECONDS = (
    AGENTIC_V2_IMAGE_PROBE_COUNT * AGENTIC_V2_IMAGE_PROBE_TIMEOUT_SECONDS
    + AGENTIC_V2_VERIFIER_OVERHEAD_SECONDS
)


_SOURCE_SHA = re.compile(r"[0-9a-f]{40}")
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_FORBIDDEN_ENV = (
    "AZURE_CLIENT_SECRET",
    "AZURE_OPENAI_API_KEY",
    "DOCKER_AUTH_CONFIG",
    "GITHUB_TOKEN",
    "HF_TOKEN",
    "OPENAI_API_KEY",
)
_BUILD_CONTEXT_PATHS = (
    "batch-runner/core/agentic_v2_substrate.py",
    "batch-runner/sandbox/agentic_v2_capabilities.json",
    "batch-runner/sandbox/v2/debian-extra.lock",
    "batch-runner/sandbox/v2/disabled_entrypoint.py",
    "batch-runner/sandbox/v2/effective_sbom.py",
    "batch-runner/sandbox/v2/image_probe.py",
    "batch-runner/sandbox/v2/license_evidence.py",
    "batch-runner/sandbox/v2/professional-work.Dockerfile",
    "batch-runner/sandbox/v2/python-extra.lock",
)
_VERIFIER_PATHS = (
    "batch-runner/core/agentic_v2_license.py",
    "batch-runner/core/agentic_v2_microvm.py",
    "batch-runner/core/agentic_v2_oci.py",
    "batch-runner/core/agentic_v2_substrate.py",
    "batch-runner/core/agentic_v2_supply_chain.py",
    "batch-runner/sandbox/v2/verify_candidate.py",
)
_LICENSE_RUNTIME_PATHS = (
    "packaging/__init__.py",
    "packaging/licenses/__init__.py",
    "packaging/licenses/_spdx.py",
)
_VERIFIER_BOOTSTRAP = (
    "import runpy,sys;"
    "runtime_root=sys.argv[1];verifier=sys.argv[2];"
    "sys.path.insert(0,runtime_root);sys.argv=sys.argv[2:];"
    "runpy.run_path(verifier,run_name='__main__')"
)
_VERIFICATION_SESSION_LABEL = "io.gdpval.agentic-v2.verification-session"
_SESSION_ID = re.compile(r"[0-9a-f]{32}")
_CONTAINER_ID = re.compile(r"[0-9a-f]{64}")


class VerificationLifecycleError(RuntimeError):
    def __init__(self, message: str, failures: list[BaseException]):
        self.failures = tuple(failures)
        super().__init__(
            f"{message}: "
            + "; ".join(
                f"{type(item).__name__}: {item}" for item in self.failures
            )
        )


def build_candidate(output_root: Path, *, source_revision: str) -> dict:
    _require_no_credentials()
    license_evaluator_runtime_identity()
    if _SOURCE_SHA.fullmatch(source_revision) is None:
        raise RuntimeError("source revision is invalid")
    output_root = output_root.resolve()
    output_root.parent.mkdir(parents=True, exist_ok=True)
    if output_root.exists() or output_root.is_symlink():
        raise RuntimeError("candidate output root must not already exist")
    lock_path = Path("/tmp/.gdpval-agentic-v2-phase1b-build.lock")
    with _open_build_lock(lock_path) as lock_stream:
        fcntl.flock(lock_stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if _git("rev-parse", "HEAD") != source_revision:
            raise RuntimeError("candidate builder HEAD moved after source staging")
        if _git("status", "--porcelain"):
            raise RuntimeError("candidate build requires a clean source tree")
        _require_tools()
        parent_lock = _load_parent_lock_from_git(source_revision)
        if _git_blob_sha256(source_revision, "batch-runner/sandbox/Dockerfile") != (
            parent_lock["v1_dockerfile_sha256"]
        ):
            raise RuntimeError("parent lock differs from committed V1 Dockerfile")
        manifest = AgenticV2SubstrateManifest.from_mapping(json.loads(
            _git_blob(source_revision, "batch-runner/sandbox/agentic_v2_capabilities.json")
        ))
        parent_inspect = _docker_json([
            _TRUSTED_DOCKER, "image", "inspect", parent_lock["reference"]
        ])
        if (
            not isinstance(parent_inspect, list)
            or len(parent_inspect) != 1
            or parent_inspect[0].get("Id") != parent_lock["observed_local_image_id"]
            or parent_inspect[0].get("Architecture") != "amd64"
            or parent_inspect[0].get("Os") != "linux"
            or parent_lock["reference"] not in (parent_inspect[0].get("RepoDigests") or [])
        ):
            raise RuntimeError("local parent image differs from exact lock")
        return _build_locked(
            output_root,
            source_revision=source_revision,
            parent_lock=parent_lock,
            manifest=manifest,
        )


def _build_locked(
    output_root: Path,
    *,
    source_revision: str,
    parent_lock: dict,
    manifest: AgenticV2SubstrateManifest,
) -> dict:
    image = (
        f"gdpval-agentic-v2-candidate:{source_revision[:12]}-"
        f"{uuid.uuid4().hex[:12]}"
    )
    with (
        tempfile.TemporaryDirectory(prefix="agentic-v2-build-context-") as temporary,
        tempfile.TemporaryDirectory(prefix="agentic-v2-docker-config-") as config_temporary,
    ):
        context = Path(temporary)
        _stage_git_context(source_revision, context)
        docker_config = Path(config_temporary)
        (docker_config / "config.json").write_text("{}\n", encoding="utf-8")
        build_command = [
            _TRUSTED_DOCKER, "build", "--pull=false", "--network=default",
            "--build-arg", f"BASE_IMAGE={parent_lock['reference']}",
            "--build-arg", f"SOURCE_REVISION={source_revision}",
            "--build-arg", f"CAPABILITY_MANIFEST_SHA256={manifest.sha256}",
            "--build-arg", f"PARENT_MANIFEST_DIGEST={parent_lock['manifest_digest']}",
            "--file", str(context / "sandbox" / "v2" / "professional-work.Dockerfile"),
            "--tag", image, str(context),
        ]
        subprocess.run(
            build_command,
            cwd=context,
            env=_docker_environment(docker_config),
            check=True,
        )
    image_id = _docker_json([_TRUSTED_DOCKER, "image", "inspect", image])[0]["Id"]
    temporary = Path(tempfile.mkdtemp(prefix=".phase1b-output-", dir=output_root.parent))
    archive = temporary / "candidate.docker.tar"
    try:
        subprocess.run(
            [_TRUSTED_DOCKER, "image", "save", "--output", str(archive), image_id],
            env=_docker_cli_environment(),
            stdin=subprocess.DEVNULL,
            check=True,
        )
        oci_report = export_docker_archive_to_oci(archive, temporary / "oci")
        archive.unlink()
        with (
            tempfile.TemporaryDirectory(prefix="agentic-v2-verifier-") as verifier_temporary,
            tempfile.TemporaryDirectory(prefix="agentic-v2-verifier-config-") as config_temporary,
        ):
            staged_batch_root = Path(verifier_temporary) / "batch-runner"
            _stage_git_files(source_revision, staged_batch_root, _VERIFIER_PATHS)
            verifier = staged_batch_root / "sandbox" / "v2" / "verify_candidate.py"
            runtime_root = Path(verifier_temporary) / "license-runtime"
            _stage_license_evaluator_runtime(runtime_root)
            docker_config = Path(config_temporary)
            (docker_config / "config.json").write_text("{}\n", encoding="utf-8")
            verifier_environment = _docker_environment(docker_config)
            verifier_environment.update({
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONHASHSEED": "0",
                "PYTHONNOUSERSITE": "1",
            })
            verification_session = uuid.uuid4().hex
            completed = _run_verifier(
                _verifier_command(
                    runtime_root=runtime_root,
                    verifier=verifier,
                    image_id=image_id,
                    source_revision=source_revision,
                    oci_layout=temporary / "oci",
                    output_directory=temporary / "evidence",
                    session_id=verification_session,
                ),
                cwd=staged_batch_root,
                environment=verifier_environment,
                session_id=verification_session,
            )
        if completed.returncode != 0:
            raise RuntimeError(
                "candidate host verification failed: "
                + completed.stderr.decode("utf-8", errors="replace")[-2000:]
            )
        gate = json.loads(completed.stdout)
        build_report = {
            "schema_version": "1.0",
            "foundation_only": True,
            "production_activation": "disabled",
            "source_revision": source_revision,
            "local_image": image,
            "image_id": image_id,
            "parent_manifest_digest": parent_lock["manifest_digest"],
            "oci_manifest_digest": oci_report["manifest_digest"],
            "gate_status": gate["gate_status"],
            "blocking_evidence": gate["blocking_evidence"],
        }
        build_report["report_sha256"] = _canonical_sha256(build_report)
        (temporary / "build-report.json").write_text(
            json.dumps(build_report, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, output_root)
        return build_report
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def _require_tools() -> None:
    _require_trusted_executable(_TRUSTED_GIT)
    _require_trusted_executable(_TRUSTED_DOCKER)
    subprocess.run(
        [_TRUSTED_DOCKER, "info"],
        env=_docker_cli_environment(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=30,
        check=True,
    )
    endpoint = subprocess.run(
        [_TRUSTED_DOCKER, "context", "inspect", "--format", "{{json .Endpoints.docker.Host}}"],
        env=_docker_cli_environment(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
        check=True,
        text=True,
    ).stdout.strip()
    try:
        endpoint = json.loads(endpoint)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Docker endpoint identity is invalid") from exc
    if not isinstance(endpoint, str) or not endpoint.startswith("unix://"):
        raise RuntimeError("candidate build requires a local Unix Docker daemon")
    docker_host = os.getenv("DOCKER_HOST")
    if docker_host and docker_host != endpoint:
        raise RuntimeError("DOCKER_HOST differs from verified local endpoint")


def _require_no_credentials() -> None:
    if any(os.getenv(name) for name in _FORBIDDEN_ENV):
        raise RuntimeError("candidate build refuses credential-bearing environment")


def _load_parent_lock_from_git(source_revision: str) -> dict:
    value = json.loads(_git_blob(
        source_revision, "batch-runner/sandbox/v2/parent.lock.json"
    ))
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != "1.0"
        or value.get("reference") != (
            "ghcr.io/hyeonsangjeon/gdpval-sandbox@" + str(value.get("manifest_digest"))
        )
        or not isinstance(value.get("manifest_digest"), str)
        or _DIGEST.fullmatch(value["manifest_digest"]) is None
        or not isinstance(value.get("observed_local_image_id"), str)
        or _DIGEST.fullmatch(value["observed_local_image_id"]) is None
        or value.get("platform") != "linux/amd64"
        or not isinstance(value.get("source_revision"), str)
        or _SOURCE_SHA.fullmatch(value["source_revision"]) is None
    ):
        raise RuntimeError("candidate parent lock is invalid")
    return value


def _git(*arguments: str) -> str:
    _require_trusted_executable(_TRUSTED_GIT)
    return subprocess.run(
        [
            _TRUSTED_GIT, "--no-replace-objects",
            "-c", "core.fsmonitor=false",
            "-c", "core.hooksPath=/dev/null",
            "-C", str(REPOSITORY_ROOT), *arguments,
        ],
        env=_git_environment(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
        check=True,
        text=True,
    ).stdout.strip()


def _docker_json(command: list[str]):
    return json.loads(subprocess.run(
        command,
        env=_docker_cli_environment(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=60,
        check=True,
    ).stdout)


def _stage_git_context(source_revision: str, root: Path) -> None:
    _stage_git_files(source_revision, root, _BUILD_CONTEXT_PATHS)


def _stage_git_files(
    source_revision: str,
    root: Path,
    repository_paths: tuple[str, ...],
) -> None:
    for repository_path in repository_paths:
        relative = repository_path.removeprefix("batch-runner/")
        destination = root / relative
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        destination.write_bytes(_git_blob(source_revision, repository_path))


def _stage_license_evaluator_runtime(root: Path) -> dict[str, str]:
    identity = license_evaluator_runtime_identity()
    package_root = Path(str(packaging.__file__)).parent
    graph = []
    for relative_path in _LICENSE_RUNTIME_PATHS:
        source = package_root.parent / relative_path
        descriptor = os.open(
            source,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
        )
        try:
            before = os.fstat(descriptor)
            if (
                not stat.S_ISREG(before.st_mode)
                or before.st_nlink != 1
                or before.st_size > 1024 * 1024
            ):
                raise RuntimeError("license evaluator runtime source is invalid")
            chunks = []
            while True:
                chunk = os.read(descriptor, 64 * 1024)
                if not chunk:
                    break
                chunks.append(chunk)
            after = os.fstat(descriptor)
        finally:
            os.close(descriptor)
        value = b"".join(chunks)
        def file_identity(metadata):
            return (
                metadata.st_dev,
                metadata.st_ino,
                metadata.st_mode,
                metadata.st_nlink,
                metadata.st_size,
                metadata.st_mtime_ns,
            )
        if file_identity(before) != file_identity(after) or len(value) != before.st_size:
            raise RuntimeError("license evaluator runtime source changed while reading")
        graph.append({
            "path": relative_path,
            "sha256": hashlib.sha256(value).hexdigest(),
            "size": len(value),
        })
        destination = root / relative_path
        destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        destination.write_bytes(value)
    if _canonical_sha256(graph) != LICENSE_EVALUATOR_RUNTIME_GRAPH_SHA256:
        raise RuntimeError("license evaluator runtime graph differs")
    return identity


def _verifier_command(
    *,
    runtime_root: Path,
    verifier: Path,
    image_id: str,
    source_revision: str,
    oci_layout: Path,
    output_directory: Path,
    session_id: str,
) -> list[str]:
    return [
        sys.executable,
        "-I",
        "-S",
        "-B",
        "-c",
        _VERIFIER_BOOTSTRAP,
        str(runtime_root),
        str(verifier),
        "--image", image_id,
        "--source-revision", source_revision,
        "--repository-root", str(REPOSITORY_ROOT),
        "--oci-layout", str(oci_layout),
        "--output-directory", str(output_directory),
        "--session-id", session_id,
    ]


def _run_verifier(
    command: list[str],
    *,
    cwd: Path,
    environment: dict[str, str],
    session_id: str,
) -> subprocess.CompletedProcess:
    if _SESSION_ID.fullmatch(session_id) is None:
        raise ValueError("candidate verification session identity is invalid")
    process = None
    result = None
    failures = []
    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        stdout, stderr = process.communicate(
            timeout=AGENTIC_V2_VERIFIER_TIMEOUT_SECONDS
        )
        result = subprocess.CompletedProcess(
            command,
            process.returncode,
            stdout,
            stderr,
        )
    except BaseException as exc:
        failures.append(exc)
    finally:
        if process is not None:
            try:
                _terminate_verifier_process_group(process)
            except BaseException as exc:
                failures.append(exc)
        try:
            _cleanup_verification_session(session_id)
        except BaseException as exc:
            failures.append(exc)
    if failures:
        if len(failures) == 1:
            raise failures[0]
        raise VerificationLifecycleError(
            "candidate verifier lifecycle failed",
            failures,
        )
    if result is None:
        raise RuntimeError("candidate verifier produced no result")
    return result


def _terminate_verifier_process_group(process: subprocess.Popen) -> None:
    failures = []
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    except BaseException as exc:
        failures.append(exc)
    if process.poll() is None:
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass
        except BaseException as exc:
            failures.append(exc)
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except BaseException as exc:
        failures.append(exc)
    if process.poll() is None:
        try:
            process.wait(timeout=10)
        except BaseException as exc:
            failures.append(exc)
    if failures:
        raise VerificationLifecycleError(
            "candidate verifier process-group termination failed",
            failures,
        )


def _verification_session_containers(session_id: str) -> list[str]:
    if _SESSION_ID.fullmatch(session_id) is None:
        raise ValueError("candidate verification session identity is invalid")
    completed = subprocess.run(
        [
            _TRUSTED_DOCKER,
            "container",
            "ls",
            "--all",
            "--quiet",
            "--no-trunc",
            "--filter",
            f"label={_VERIFICATION_SESSION_LABEL}={session_id}",
        ],
        env=_docker_cli_environment(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=AGENTIC_V2_VERIFICATION_SESSION_INVENTORY_TIMEOUT_SECONDS,
        check=False,
    )
    if (
        completed.returncode != 0
        or completed.stderr
        or len(completed.stdout) > 64 * 1024
    ):
        raise RuntimeError("candidate verification session inventory failed")
    identifiers = completed.stdout.decode("ascii", errors="strict").splitlines()
    if (
        len(identifiers) > AGENTIC_V2_VERIFICATION_SESSION_MAX_CONTAINERS
        or len(identifiers) != len(set(identifiers))
        or any(_CONTAINER_ID.fullmatch(item) is None for item in identifiers)
    ):
        raise RuntimeError("candidate verification session inventory is invalid")
    return identifiers


def _cleanup_verification_session(session_id: str) -> None:
    failures = []
    for _attempt in range(AGENTIC_V2_VERIFICATION_SESSION_SWEEP_LIMIT):
        try:
            identifiers = _verification_session_containers(session_id)
        except BaseException as exc:
            failures.append(exc)
            continue
        if not identifiers:
            continue
        for identifier in identifiers:
            try:
                completed = subprocess.run(
                    [_TRUSTED_DOCKER, "container", "rm", "--force", identifier],
                    env=_docker_cli_environment(),
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=AGENTIC_V2_VERIFICATION_SESSION_REMOVE_TIMEOUT_SECONDS,
                    check=False,
                )
            except (OSError, subprocess.SubprocessError) as exc:
                failures.append(exc)
                continue
            if (
                completed.returncode != 0
                or len(completed.stdout) > 4096
                or len(completed.stderr) > 64 * 1024
            ):
                failures.append(RuntimeError(
                    "candidate verification session container removal failed"
                ))
    try:
        remaining = _verification_session_containers(session_id)
    except BaseException as exc:
        failures.append(exc)
        remaining = ["inventory-unavailable"]
    if failures or remaining:
        raise VerificationLifecycleError(
            "candidate verification session cleanup is incomplete",
            failures or [RuntimeError("candidate verification containers remain")],
        )


def _git_blob(source_revision: str, repository_path: str) -> bytes:
    _require_trusted_executable(_TRUSTED_GIT)
    return subprocess.run(
        [
            _TRUSTED_GIT, "--no-replace-objects",
            "-c", "core.fsmonitor=false",
            "-c", "core.hooksPath=/dev/null",
            "-C", str(REPOSITORY_ROOT),
            "show", f"{source_revision}:{repository_path}",
        ],
        env=_git_environment(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
        check=True,
    ).stdout


def _git_blob_sha256(source_revision: str, repository_path: str) -> str:
    return hashlib.sha256(_git_blob(source_revision, repository_path)).hexdigest()


def _docker_environment(config_directory: Path) -> dict[str, str]:
    environment = {
        "PATH": _TRUSTED_PATH,
        "HOME": str(config_directory.parent),
        "DOCKER_CONFIG": str(config_directory),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }
    if os.getenv("DOCKER_HOST"):
        if not os.environ["DOCKER_HOST"].startswith("unix://"):
            raise RuntimeError("candidate build requires a local Unix Docker daemon")
        environment["DOCKER_HOST"] = os.environ["DOCKER_HOST"]
    return environment


def _docker_cli_environment() -> dict[str, str]:
    environment = {
        "PATH": _TRUSTED_PATH,
        "HOME": "/nonexistent",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }
    if os.getenv("DOCKER_HOST"):
        if not os.environ["DOCKER_HOST"].startswith("unix://"):
            raise RuntimeError("candidate build requires a local Unix Docker daemon")
        environment["DOCKER_HOST"] = os.environ["DOCKER_HOST"]
    return environment


def _git_environment() -> dict[str, str]:
    return {
        "PATH": _TRUSTED_PATH,
        "HOME": "/nonexistent",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_TERMINAL_PROMPT": "0",
    }


def _open_build_lock(path: Path):
    descriptor = os.open(
        path,
        os.O_RDWR
        | os.O_CREAT
        | _secure_lock_flags(),
        0o600,
    )
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_nlink != 1
            or metadata.st_uid != os.geteuid()
        ):
            raise RuntimeError("candidate build lock identity is invalid")
        os.fchmod(descriptor, 0o600)
        return os.fdopen(descriptor, "a+", encoding="utf-8")
    except Exception:
        os.close(descriptor)
        raise


def _secure_lock_flags() -> int:
    required = ("O_NOFOLLOW", "O_CLOEXEC")
    if os.name != "posix" or any(
        not isinstance(getattr(os, name, None), int)
        or getattr(os, name) <= 0
        for name in required
    ):
        raise RuntimeError("candidate build lock requires secure Unix open flags")
    return os.O_NOFOLLOW | os.O_CLOEXEC


def _canonical_sha256(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def main() -> None:
    if _BOOTSTRAPPED_RUNTIME_ROOT is None:
        raise RuntimeError("candidate builder entrypoint was not isolated")
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", required=True, type=Path)
    arguments = parser.parse_args()
    source_revision = os.environ.get(_SOURCE_REVISION_ENV)
    if source_revision is None:
        raise RuntimeError("candidate builder staged revision is missing")
    report = build_candidate(
        arguments.output_root,
        source_revision=source_revision,
    )
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()