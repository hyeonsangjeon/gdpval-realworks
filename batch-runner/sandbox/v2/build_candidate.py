"""Build and verify a local-only Phase 1B candidate from a clean source tree."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path


BATCH_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = BATCH_ROOT.parent
if str(BATCH_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_ROOT))

from core.agentic_v2_oci import export_docker_archive_to_oci  # noqa: E402
from core.agentic_v2_substrate import AgenticV2SubstrateManifest  # noqa: E402


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
    "batch-runner/sandbox/v2/professional-work.Dockerfile",
    "batch-runner/sandbox/v2/python-extra.lock",
)
_VERIFIER_PATHS = (
    "batch-runner/core/agentic_v2_microvm.py",
    "batch-runner/core/agentic_v2_oci.py",
    "batch-runner/core/agentic_v2_substrate.py",
    "batch-runner/core/agentic_v2_supply_chain.py",
    "batch-runner/sandbox/v2/verify_candidate.py",
)


def build_candidate(output_root: Path) -> dict:
    _require_no_credentials()
    _require_tools()
    output_root = output_root.resolve()
    output_root.parent.mkdir(parents=True, exist_ok=True)
    if output_root.exists() or output_root.is_symlink():
        raise RuntimeError("candidate output root must not already exist")
    lock_path = Path("/tmp/.gdpval-agentic-v2-phase1b-build.lock")
    with _open_build_lock(lock_path) as lock_stream:
        fcntl.flock(lock_stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        source_revision = _git("rev-parse", "HEAD")
        if _SOURCE_SHA.fullmatch(source_revision) is None:
            raise RuntimeError("source revision is invalid")
        if _git("status", "--porcelain"):
            raise RuntimeError("candidate build requires a clean source tree")
        parent_lock = _load_parent_lock_from_git(source_revision)
        if _git_blob_sha256(source_revision, "batch-runner/sandbox/Dockerfile") != (
            parent_lock["v1_dockerfile_sha256"]
        ):
            raise RuntimeError("parent lock differs from committed V1 Dockerfile")
        manifest = AgenticV2SubstrateManifest.from_mapping(json.loads(
            _git_blob(source_revision, "batch-runner/sandbox/agentic_v2_capabilities.json")
        ))
        parent_inspect = _docker_json([
            "docker", "image", "inspect", parent_lock["reference"]
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
            "docker", "build", "--pull=false", "--network=default",
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
    image_id = _docker_json(["docker", "image", "inspect", image])[0]["Id"]
    _verify_disabled_entrypoint(image_id)
    temporary = Path(tempfile.mkdtemp(prefix=".phase1b-output-", dir=output_root.parent))
    archive = temporary / "candidate.docker.tar"
    try:
        subprocess.run(
            ["docker", "image", "save", "--output", str(archive), image_id],
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
            docker_config = Path(config_temporary)
            (docker_config / "config.json").write_text("{}\n", encoding="utf-8")
            verifier_environment = _docker_environment(docker_config)
            verifier_environment.update({
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONHASHSEED": "0",
                "PYTHONNOUSERSITE": "1",
            })
            completed = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    str(verifier),
                    "--image", image_id,
                    "--source-revision", source_revision,
                    "--repository-root", str(REPOSITORY_ROOT),
                    "--oci-layout", str(temporary / "oci"),
                    "--output-directory", str(temporary / "evidence"),
                ],
                cwd=staged_batch_root,
                env=verifier_environment,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=1800,
                check=False,
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
    for name in ("docker", "git"):
        if shutil.which(name) is None:
            raise RuntimeError(f"required local tool is missing: {name}")
    subprocess.run(
        ["docker", "info"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=30,
        check=True,
    )
    endpoint = subprocess.run(
        ["docker", "context", "inspect", "--format", "{{json .Endpoints.docker.Host}}"],
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
        or _DIGEST.fullmatch(str(value.get("manifest_digest", ""))) is None
        or _DIGEST.fullmatch(str(value.get("observed_local_image_id", ""))) is None
        or value.get("platform") != "linux/amd64"
        or _SOURCE_SHA.fullmatch(str(value.get("source_revision", ""))) is None
    ):
        raise RuntimeError("candidate parent lock is invalid")
    return value


def _git(*arguments: str) -> str:
    return subprocess.run(
        [
            "git", "--no-replace-objects",
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
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=60,
        check=True,
    ).stdout)


def _verify_disabled_entrypoint(image_id: str) -> None:
    container = f"gdpval-agentic-v2-disabled-{uuid.uuid4().hex}"
    try:
        disabled = subprocess.run(
            [
                "docker", "run", "--name", container,
                "--network", "none", image_id,
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
            check=False,
        )
    finally:
        _remove_container(container)
    if disabled.returncode != 78 or b"candidate_not_activated" not in disabled.stderr:
        raise RuntimeError("candidate default entrypoint is not fail-closed")


def _remove_container(container: str) -> None:
    try:
        subprocess.run(
            ["docker", "container", "rm", "--force", container],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        inspected = subprocess.run(
            ["docker", "container", "inspect", container],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(
            "candidate container cleanup could not be verified"
        ) from exc
    if inspected.returncode == 0:
        raise RuntimeError("candidate container cleanup did not remove container")
    if not _container_absence_confirmed(inspected.stderr, container):
        raise RuntimeError("candidate container cleanup could not be verified")


def _container_absence_confirmed(stderr: bytes, container: str) -> bool:
    message = stderr.decode("utf-8", errors="strict")
    if message.endswith("\n"):
        message = message[:-1]
    allowed = {
        f"Error: No such object: {container}",
        f"Error: No such container: {container}",
        f"Error response from daemon: No such object: {container}",
        f"Error response from daemon: No such container: {container}",
    }
    return message in allowed


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


def _git_blob(source_revision: str, repository_path: str) -> bytes:
    return subprocess.run(
        [
            "git", "--no-replace-objects",
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
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(config_directory.parent),
        "DOCKER_CONFIG": str(config_directory),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }
    if os.getenv("DOCKER_HOST"):
        environment["DOCKER_HOST"] = os.environ["DOCKER_HOST"]
    return environment


def _git_environment() -> dict[str, str]:
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", required=True, type=Path)
    arguments = parser.parse_args()
    report = build_candidate(arguments.output_root)
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()