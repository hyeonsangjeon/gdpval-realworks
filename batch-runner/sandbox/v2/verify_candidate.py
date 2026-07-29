"""Host-owned verifier for one local Phase 1B candidate image."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path


BATCH_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = BATCH_ROOT.parent
if str(BATCH_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_ROOT))

from core.agentic_v2_microvm import (  # noqa: E402
    inspect_microvm_readiness,
    validate_microvm_readiness_report,
)
from core.agentic_v2_oci import verify_oci_layout  # noqa: E402
from core.agentic_v2_substrate import (  # noqa: E402
    AgenticV2SubstrateManifest,
    canonical_sha256,
    validate_capability_receipt,
)
from core.agentic_v2_supply_chain import (  # noqa: E402
    CandidateSubject,
    SupplyChainPolicy,
    build_candidate_receipt,
    build_evidence_report,
    evidence_collection_allowed,
    evidence_item,
    evaluate_license_policy,
    validate_effective_sbom,
    validate_evidence_directory,
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
_CONTAINMENT_CHECKS = frozenset({
    "cap_drop_all",
    "cpu_quota",
    "memory_limit",
    "network_none",
    "no_new_privileges",
    "non_root_uid",
    "pids_limit",
    "read_only_rootfs",
})
_CONTAINMENT_PROBE = r'''
import ctypes
import json
import os

def read_first(paths):
    for path in paths:
        try:
            with open(path, "r", encoding="utf-8") as stream:
                return stream.read().strip()
        except OSError:
            pass
    return None

def bounded_integer(value, maximum):
    try:
        return 0 < int(value) <= maximum
    except (TypeError, ValueError):
        return False

status = {}
with open("/proc/self/status", "r", encoding="utf-8") as stream:
    for line in stream:
        key, separator, value = line.partition(":")
        if separator:
            status[key] = value.strip()

libc = ctypes.CDLL(None, use_errno=True)
prctl = libc.prctl
prctl.argtypes = [
    ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong,
]
prctl.restype = ctypes.c_int
no_new_privileges = prctl(39, 0, 0, 0, 0) == 1

with open("/proc/net/route", "r", encoding="utf-8") as stream:
    ipv4_routes = [line for line in stream.read().splitlines()[1:] if line]
with open("/proc/net/ipv6_route", "r", encoding="utf-8") as stream:
    ipv6_routes = [line for line in stream.read().splitlines() if line]
network_none = (
    not ipv4_routes
    and all(line.split()[-1] == "lo" for line in ipv6_routes)
)

memory = read_first((
    "/sys/fs/cgroup/memory.max",
    "/sys/fs/cgroup/memory/memory.limit_in_bytes",
    "/sys/fs/cgroup/memory.limit_in_bytes",
))
pids = read_first((
    "/sys/fs/cgroup/pids.max",
    "/sys/fs/cgroup/pids/pids.max",
))
cpu_v2 = read_first(("/sys/fs/cgroup/cpu.max",))
if cpu_v2:
    quota_value, _, period_value = cpu_v2.partition(" ")
else:
    quota_value = read_first((
        "/sys/fs/cgroup/cpu/cpu.cfs_quota_us",
        "/sys/fs/cgroup/cpu.cfs_quota_us",
    ))
    period_value = read_first((
        "/sys/fs/cgroup/cpu/cpu.cfs_period_us",
        "/sys/fs/cgroup/cpu.cfs_period_us",
    ))
try:
    cpu_limited = (
        quota_value != "max"
        and 0 < int(quota_value)
        and 0 < int(period_value)
        and int(quota_value) / int(period_value) <= 0.25
    )
except (TypeError, ValueError):
    cpu_limited = False

checks = {
    "cap_drop_all": (
        all(
            name in status and int(status[name], 16) == 0
            for name in ("CapInh", "CapPrm", "CapEff", "CapBnd")
        )
        and ("CapAmb" not in status or int(status["CapAmb"], 16) == 0)
    ),
    "cpu_quota": cpu_limited,
    "memory_limit": bounded_integer(memory, 64 * 1024 * 1024),
    "network_none": network_none,
    "no_new_privileges": no_new_privileges,
    "non_root_uid": os.geteuid() == 65532 and os.getegid() == 65532,
    "pids_limit": bounded_integer(pids, 16),
    "read_only_rootfs": bool(os.statvfs("/").f_flag & os.ST_RDONLY),
}
print(json.dumps(checks, sort_keys=True, separators=(",", ":")))
'''.strip()


def verify_candidate(
    *,
    image: str,
    source_revision: str,
    oci_layout: Path,
    output_directory: Path,
    repository_root: Path | None = None,
) -> dict:
    _require_no_credentials()
    _require_local_docker()
    if _SOURCE_SHA.fullmatch(source_revision) is None:
        raise ValueError("candidate source revision is invalid")
    repository_root = _require_repository_root(
        repository_root or REPOSITORY_ROOT,
        source_revision,
    )
    if output_directory.exists() or output_directory.is_symlink():
        raise ValueError("candidate evidence directory must not already exist")
    manifest = AgenticV2SubstrateManifest.from_mapping(json.loads(_git_blob(
        source_revision, "batch-runner/sandbox/agentic_v2_capabilities.json",
        repository_root,
    )))
    policy = SupplyChainPolicy.from_mapping(json.loads(_git_blob(
        source_revision,
        "batch-runner/security/agentic-v2-supply-chain-policy.json",
        repository_root,
    )))
    parent_lock = _load_parent_lock_bytes(_git_blob(
        source_revision, "batch-runner/sandbox/v2/parent.lock.json", repository_root
    ))
    if _git_blob_sha256(
        source_revision, "batch-runner/sandbox/Dockerfile", repository_root
    ) != (
        parent_lock["v1_dockerfile_sha256"]
    ):
        raise ValueError("candidate parent lock differs from committed V1 Dockerfile")
    oci_report = verify_oci_layout(oci_layout)
    inspect = _docker_json(["docker", "image", "inspect", image])
    if not isinstance(inspect, list) or len(inspect) != 1:
        raise ValueError("candidate image inspect result is invalid")
    image_document = inspect[0]
    parent_inspect = _docker_json([
        "docker", "image", "inspect", parent_lock["reference"]
    ])
    if not isinstance(parent_inspect, list) or len(parent_inspect) != 1:
        raise ValueError("candidate parent image inspect result is invalid")
    parent_document = parent_inspect[0]
    parent_labels = ((parent_document.get("Config") or {}).get("Labels") or {})
    parent_layers = ((parent_document.get("RootFS") or {}).get("Layers") or [])
    candidate_layers = ((image_document.get("RootFS") or {}).get("Layers") or [])
    labels = ((image_document.get("Config") or {}).get("Labels") or {})
    entrypoint = ((image_document.get("Config") or {}).get("Entrypoint") or [])
    image_id = image_document.get("Id")
    if (
        image_id != oci_report["config_digest"]
        or image_document.get("Architecture") != "amd64"
        or image_document.get("Os") != "linux"
        or labels.get("org.opencontainers.image.revision") != source_revision
        or labels.get("org.opencontainers.image.base.digest") != parent_lock["manifest_digest"]
        or labels.get("io.gdpval.agentic-v2.substrate") != "professional-work-v1"
        or labels.get("io.gdpval.agentic-v2.foundation-only") != "true"
        or labels.get("io.gdpval.agentic-v2.production-activation") != "disabled"
        or labels.get("io.gdpval.agentic-v2.capability-manifest-sha256") != manifest.sha256
        or entrypoint != [
            "python", "-I", "-B", "/opt/gdpval/v2/disabled_entrypoint.py"
        ]
        or parent_document.get("Id") != parent_lock["observed_local_image_id"]
        or parent_lock["reference"] not in (parent_document.get("RepoDigests") or [])
        or parent_labels.get("org.opencontainers.image.revision") != parent_lock["source_revision"]
        or not isinstance(parent_layers, list)
        or not isinstance(candidate_layers, list)
        or len(candidate_layers) <= len(parent_layers)
        or candidate_layers[:len(parent_layers)] != parent_layers
    ):
        raise ValueError("candidate image identity or labels are invalid")
    embedded_source_sha256 = _verify_embedded_files(
        image_id, source_revision, repository_root
    )
    lock_set_sha256 = canonical_sha256([
        {
            "path": path,
            "sha256": _git_blob_sha256(source_revision, path, repository_root),
        }
        for path in (
            "batch-runner/sandbox/v2/parent.lock.json",
            "batch-runner/sandbox/v2/debian-extra.lock",
            "batch-runner/sandbox/v2/python-extra.lock",
        )
    ])
    subject = CandidateSubject.from_mapping({
        "schema_version": "1.0",
        "substrate_id": "professional-work-v1",
        "image_id": image_id,
        "oci_manifest_digest": oci_report["manifest_digest"],
        "parent_manifest_digest": parent_lock["manifest_digest"],
        "platform": "linux/amd64",
        "source_revision": source_revision,
        "dockerfile_sha256": _git_blob_sha256(
            source_revision,
            "batch-runner/sandbox/v2/professional-work.Dockerfile",
            repository_root,
        ),
        "manifest_sha256": manifest.sha256,
        "probe_sha256": _git_blob_sha256(
            source_revision, "batch-runner/sandbox/v2/image_probe.py", repository_root
        ),
        "embedded_source_sha256": embedded_source_sha256,
        "verifier_sha256": _git_blob_sha256(
            source_revision,
            "batch-runner/sandbox/v2/verify_candidate.py",
            repository_root,
        ),
        "oci_exporter_sha256": _git_blob_sha256(
            source_revision, "batch-runner/core/agentic_v2_oci.py", repository_root
        ),
        "sbom_generator_sha256": _git_blob_sha256(
            source_revision,
            "batch-runner/sandbox/v2/effective_sbom.py",
            repository_root,
        ),
        "lock_set_sha256": lock_set_sha256,
    })
    microvm_report = inspect_microvm_readiness(asset_paths={})
    validate_microvm_readiness_report(microvm_report)
    containment_report = _inspect_containment(parent_document["Id"])
    tool_sha = subject.document["verifier_sha256"]
    evidence = {
        name: evidence_item(subject, name=name, status="not_run")
        for name in (
            "capability_receipt", "cve", "license", "microvm", "oci_layout",
            "containment", "provenance", "sbom", "signature",
        )
    }
    evidence["oci_layout"] = evidence_item(
        subject,
        name="oci_layout",
        status="verified",
        tool_name="gdpval-agentic-v2-oci-exporter",
        tool_version="1.0",
        tool_sha256=subject.document["oci_exporter_sha256"],
        report_sha256=canonical_sha256(oci_report),
    )
    evidence["containment"] = evidence_item(
        subject,
        name="containment",
        status=containment_report["status"],
        tool_name="gdpval-agentic-v2-docker-containment",
        tool_version="1.0",
        tool_sha256=tool_sha,
        report_sha256=canonical_sha256(containment_report),
    )
    receipt = None
    sbom = None
    license_report = None
    if evidence_collection_allowed(containment_report):
        _verify_disabled_entrypoint(
            image_id,
            containment_checks=containment_report["checks"],
        )
        observation = _run_image_json(
            image_id,
            "/opt/gdpval/v2/image_probe.py",
            8 * 1024 * 1024,
            containment_checks=containment_report["checks"],
        )
        validate_capability_receipt(observation, manifest)
        sbom = _run_image_json(
            image_id,
            "/opt/gdpval/v2/effective_sbom.py",
            64 * 1024 * 1024,
            containment_checks=containment_report["checks"],
        )
        validate_effective_sbom(sbom, observation)
        license_report = evaluate_license_policy(sbom, policy)
        receipt = build_candidate_receipt(subject, observation, manifest)
        evidence["capability_receipt"] = evidence_item(
            subject,
            name="capability_receipt",
            status="verified",
            tool_name="gdpval-agentic-v2-host-verifier",
            tool_version="1.0",
            tool_sha256=tool_sha,
            report_sha256=canonical_sha256(receipt),
        )
        evidence["sbom"] = evidence_item(
            subject,
            name="sbom",
            status="verified",
            tool_name="gdpval-agentic-v2-effective-sbom",
            tool_version="1.0",
            tool_sha256=subject.document["sbom_generator_sha256"],
            report_sha256=canonical_sha256(sbom),
        )
        evidence["license"] = evidence_item(
            subject,
            name="license",
            status=license_report["status"],
            tool_name="gdpval-agentic-v2-license-policy",
            tool_version="1.0",
            tool_sha256=policy.sha256,
            report_sha256=canonical_sha256(license_report),
        )
    gate = build_evidence_report(subject, policy, evidence)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output_directory.name}.", dir=output_directory.parent))
    try:
        _write_json(temporary / "candidate-subject.json", subject.document)
        _write_json(temporary / "oci-report.json", oci_report)
        if receipt is not None:
            _write_json(temporary / "candidate-receipt.json", receipt)
        if sbom is not None:
            _write_json(temporary / "effective-sbom.spdx.json", sbom)
        if license_report is not None:
            _write_json(temporary / "license-report.json", license_report)
        _write_json(temporary / "containment-report.json", containment_report)
        _write_json(temporary / "microvm-readiness.json", microvm_report)
        _write_json(temporary / "gate-report.json", gate)
        validate_evidence_directory(
            temporary,
            subject=subject,
            policy=policy,
            manifest=manifest,
            oci_layout=oci_layout,
        )
        os.replace(temporary, output_directory)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return gate


def _run_image_json(
    image: str,
    script: str,
    maximum: int,
    *,
    containment_checks: dict[str, bool],
) -> dict:
    container = _container_name("evidence")
    optional_limits = []
    if containment_checks["pids_limit"]:
        optional_limits.extend(["--pids-limit", "512"])
    if containment_checks["cpu_quota"]:
        optional_limits.extend(["--cpus", "2"])
    command = [
        "docker", "run", "--pull=never", "--name", container,
        "--network", "none", "--read-only",
        "--user", "65532:65532", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges", "--memory", "6g",
        *optional_limits,
        "--tmpfs",
        "/work:rw,exec,nosuid,nodev,size=2147483648,uid=65532,gid=65532,mode=0700",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,nodev,size=268435456,uid=65532,gid=65532,mode=0700",
        "--entrypoint", "python",
        image, "-I", "-B", script,
    ]
    try:
        completed = subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=900,
            check=False,
        )
    finally:
        _remove_container(container)
    if completed.returncode != 0:
        raise RuntimeError(
            "candidate image probe failed: "
            + completed.stderr.decode("utf-8", errors="replace")[-1000:]
        )
    if not completed.stdout or len(completed.stdout) > maximum:
        raise RuntimeError("candidate image probe output size is invalid")
    value = json.loads(completed.stdout)
    if not isinstance(value, dict):
        raise RuntimeError("candidate image probe result is invalid")
    return value


def _inspect_containment(image: str) -> dict:
    checks, collection_checks = _docker_base_isolation_probe(image)
    checks["pids_limit"] = _docker_resource_limit_probe(
        image,
        name="pids_limit",
        arguments=["--pids-limit", "16"],
    )
    checks["cpu_quota"] = _docker_resource_limit_probe(
        image,
        name="cpu_quota",
        arguments=["--cpus", "0.25"],
    )
    report = {
        "schema_version": "1.1",
        "status": "verified" if all(checks.values()) else "failed",
        "checks": checks,
        "required": sorted(checks),
        "collection_status": (
            "verified" if all(collection_checks.values()) else "failed"
        ),
        "collection_checks": collection_checks,
        "host_scope": "exact-docker-daemon",
    }
    report["report_sha256"] = canonical_sha256(report)
    return report


def _docker_base_isolation_probe(
    image: str,
) -> tuple[dict[str, bool], dict[str, bool]]:
    failed = {name: False for name in _CONTAINMENT_CHECKS}
    collection_failed = {
        name: False
        for name in (
            "cap_drop_all", "memory_limit", "network_none",
            "no_new_privileges", "non_root_uid", "read_only_rootfs",
        )
    }
    container = _container_name("isolation")
    inspected = None
    try:
        completed = subprocess.run(
            [
                "docker", "run", "--pull=never", "--name", container,
                "--network", "none", "--read-only",
                "--user", "65532:65532", "--cap-drop", "ALL",
                "--security-opt", "no-new-privileges",
                "--memory", "64m",
                "--entrypoint", "python", image, "-I", "-B", "-c",
                _CONTAINMENT_PROBE,
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
            check=False,
        )
        if completed.returncode == 0:
            inspected = _docker_json(["docker", "container", "inspect", container])
    finally:
        _remove_container(container)
    if (
        completed.returncode != 0
        or not completed.stdout
        or len(completed.stdout) > 65536
        or len(completed.stderr) > 65536
    ):
        return failed, collection_failed
    try:
        checks = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return failed, collection_failed
    if (
        not isinstance(checks, dict)
        or set(checks) != _CONTAINMENT_CHECKS
        or any(type(value) is not bool for value in checks.values())
    ):
        return failed, collection_failed
    if completed.stderr:
        return failed, collection_failed
    return checks, _collection_checks_from_inspect(inspected, checks)


def _collection_checks_from_inspect(
    value,
    runtime_checks: dict[str, bool],
) -> dict[str, bool]:
    failed = {
        name: False
        for name in (
            "cap_drop_all", "memory_limit", "network_none",
            "no_new_privileges", "non_root_uid", "read_only_rootfs",
        )
    }
    if not isinstance(value, list) or len(value) != 1 or not isinstance(value[0], dict):
        return failed
    document = value[0]
    host = document.get("HostConfig")
    config = document.get("Config")
    network_settings = document.get("NetworkSettings")
    if (
        not isinstance(host, dict)
        or not isinstance(config, dict)
        or not isinstance(network_settings, dict)
    ):
        return failed
    networks = network_settings.get("Networks")
    network = networks.get("none") if isinstance(networks, dict) else None
    network_identity = (
        isinstance(networks, dict)
        and set(networks) == {"none"}
        and isinstance(network, dict)
        and network.get("IPAddress") in {None, ""}
        and network.get("GlobalIPv6Address") in {None, ""}
        and network.get("Gateway") in {None, ""}
        and network.get("IPv6Gateway") in {None, ""}
    )
    return {
        "cap_drop_all": (
            host.get("CapDrop") == ["ALL"] and runtime_checks["cap_drop_all"]
        ),
        "memory_limit": (
            host.get("Memory") == 64 * 1024 * 1024
            and runtime_checks["memory_limit"]
        ),
        "network_none": (
            host.get("NetworkMode") == "none"
            and network_identity
            and runtime_checks["network_none"]
        ),
        "no_new_privileges": (
            host.get("SecurityOpt") == ["no-new-privileges"]
            and runtime_checks["no_new_privileges"]
        ),
        "non_root_uid": (
            config.get("User") == "65532:65532"
            and runtime_checks["non_root_uid"]
        ),
        "read_only_rootfs": (
            host.get("ReadonlyRootfs") is True
            and runtime_checks["read_only_rootfs"]
        ),
    }


def _docker_resource_limit_probe(
    image: str,
    *,
    name: str,
    arguments: list[str],
) -> bool:
    container = _container_name(name)
    try:
        completed = subprocess.run(
            [
                "docker", "run", "--pull=never", "--name", container,
                "--network", "none", "--read-only",
                "--user", "65532:65532", "--cap-drop", "ALL",
                "--security-opt", "no-new-privileges", "--memory", "64m",
                *arguments,
                "--entrypoint", "python", image, "-I", "-B", "-c",
                _CONTAINMENT_PROBE,
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
            check=False,
        )
    finally:
        _remove_container(container)
    if (
        completed.returncode != 0
        or not completed.stdout
        or len(completed.stdout) > 65536
        or len(completed.stderr) > 65536
    ):
        return False
    try:
        checks = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return False
    if (
        not isinstance(checks, dict)
        or set(checks) != _CONTAINMENT_CHECKS
        or any(type(item) is not bool for item in checks.values())
    ):
        return False
    warning_checks = _resource_warning_checks(completed.stderr)
    return (
        warning_checks is not None
        and name not in warning_checks
        and checks[name] is True
    )


def _resource_warning_checks(stderr: bytes) -> set[str] | None:
    affected = set()
    patterns = {
        "pids_limit": re.compile(
            r"(?:warning:\s*)?(?:pids limit discarded|"
            r"(?:your )?kernel does not support pids limit capabilities or the "
            r"cgroup is not mounted\. pids limit discarded)\.?",
        ),
        "cpu_quota": re.compile(
            r"(?:warning:\s*)?(?:your )?kernel does not support cpu cfs scheduler "
            r"or the cgroup is not mounted\. period/quota discarded\.?",
        ),
    }
    for raw_line in stderr.decode("utf-8", errors="replace").splitlines():
        line = raw_line.strip().lower()
        if not line:
            continue
        matches = [name for name, pattern in patterns.items() if pattern.fullmatch(line)]
        if len(matches) != 1:
            return None
        affected.add(matches[0])
    return affected


def _docker_json(command: list[str]):
    completed = subprocess.run(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=60,
        check=True,
    )
    return json.loads(completed.stdout)


def _verify_disabled_entrypoint(
    image_id: str,
    *,
    containment_checks: dict[str, bool],
) -> None:
    container = _container_name("disabled")
    optional_limits = []
    if containment_checks["pids_limit"]:
        optional_limits.extend(["--pids-limit", "16"])
    if containment_checks["cpu_quota"]:
        optional_limits.extend(["--cpus", "0.25"])
    try:
        completed = subprocess.run(
            [
                "docker", "run", "--pull=never", "--name", container,
                "--network", "none", "--read-only",
                "--user", "65532:65532", "--cap-drop", "ALL",
                "--security-opt", "no-new-privileges", "--memory", "64m",
                *optional_limits,
                image_id,
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
            check=False,
        )
    finally:
        _remove_container(container)
    expected_stderr = (
        json.dumps({
            "error": "agentic_v2_phase1b_candidate_not_activated",
            "foundation_only": True,
            "production_activation": "disabled",
        }, sort_keys=True, separators=(",", ":")).encode("utf-8")
        + b"\n"
    )
    if (
        completed.returncode != 78
        or completed.stdout != b""
        or completed.stderr != expected_stderr
    ):
        raise RuntimeError("candidate default entrypoint is not fail-closed")


def _verify_embedded_files(
    image: str,
    source_revision: str,
    repository_root: Path,
) -> str:
    expected = {
        "/opt/gdpval/v2/agentic_v2_substrate.py": "batch-runner/core/agentic_v2_substrate.py",
        "/opt/gdpval/v2/capabilities.json": "batch-runner/sandbox/agentic_v2_capabilities.json",
        "/opt/gdpval/v2/debian-extra.lock": "batch-runner/sandbox/v2/debian-extra.lock",
        "/opt/gdpval/v2/disabled_entrypoint.py": "batch-runner/sandbox/v2/disabled_entrypoint.py",
        "/opt/gdpval/v2/effective_sbom.py": "batch-runner/sandbox/v2/effective_sbom.py",
        "/opt/gdpval/v2/image_probe.py": "batch-runner/sandbox/v2/image_probe.py",
        "/opt/gdpval/v2/python-extra.lock": "batch-runner/sandbox/v2/python-extra.lock",
    }
    container = _container_name("inspect")
    records = []
    try:
        created = subprocess.run(
            [
                "docker", "container", "create", "--name", container,
                "--network", "none", "--entrypoint", "/bin/true",
                image,
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
            check=True,
            text=True,
        ).stdout.strip()
        if not re.fullmatch(r"[0-9a-f]{64}", created):
            raise RuntimeError("candidate inspection container identity is invalid")
        with tempfile.TemporaryDirectory(prefix="phase1b-embedded-") as temporary:
            root = Path(temporary)
            for index, (container_path, repository_path) in enumerate(sorted(expected.items())):
                target = root / f"item-{index}"
                subprocess.run(
                    ["docker", "container", "cp", f"{container}:{container_path}", str(target)],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    timeout=60,
                    check=True,
                )
                if not target.is_file() or target.is_symlink():
                    raise RuntimeError("candidate embedded file is not regular")
                actual_sha = _sha256(target)
                expected_sha = _git_blob_sha256(
                    source_revision, repository_path, repository_root
                )
                if actual_sha != expected_sha:
                    raise RuntimeError(
                        f"candidate embedded file differs from source: {container_path}"
                    )
                records.append({
                    "path": container_path,
                    "sha256": actual_sha,
                    "size": target.stat().st_size,
                })
    finally:
        _remove_container(container)
    return canonical_sha256(records)


def _container_name(purpose: str) -> str:
    return f"gdpval-agentic-v2-{purpose}-{uuid.uuid4().hex}"


def _load_parent_lock(path: Path) -> dict:
    return _load_parent_lock_bytes(path.read_bytes())


def _load_parent_lock_bytes(raw: bytes) -> dict:
    value = json.loads(raw)
    if not isinstance(value, dict) or set(value) != {
        "schema_version", "reference", "manifest_digest", "observed_local_image_id",
        "source_revision", "platform", "v1_dockerfile_sha256",
    }:
        raise ValueError("candidate parent lock fields are invalid")
    if (
        value["schema_version"] != "1.0"
        or value["reference"] != (
            "ghcr.io/hyeonsangjeon/gdpval-sandbox@" + value["manifest_digest"]
        )
        or _DIGEST.fullmatch(value["manifest_digest"]) is None
        or _DIGEST.fullmatch(value["observed_local_image_id"]) is None
        or value["platform"] != "linux/amd64"
        or _SOURCE_SHA.fullmatch(value["source_revision"]) is None
        or len(value["v1_dockerfile_sha256"]) != 64
    ):
        raise ValueError("candidate parent lock identity is invalid")
    return value


def _require_no_credentials() -> None:
    present = [name for name in _FORBIDDEN_ENV if os.getenv(name)]
    if present:
        raise RuntimeError("candidate verifier refuses credential-bearing environment")


def _require_local_docker() -> None:
    completed = subprocess.run(
        ["docker", "context", "inspect", "--format", "{{json .Endpoints.docker.Host}}"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
        check=True,
        text=True,
    )
    endpoint = json.loads(completed.stdout)
    if not isinstance(endpoint, str) or not endpoint.startswith("unix://"):
        raise RuntimeError("candidate verifier requires a local Unix Docker daemon")
    if os.getenv("DOCKER_HOST") and os.environ["DOCKER_HOST"] != endpoint:
        raise RuntimeError("DOCKER_HOST differs from verified local endpoint")


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


def _git_blob(
    source_revision: str,
    repository_path: str,
    repository_root: Path = REPOSITORY_ROOT,
) -> bytes:
    return subprocess.run(
        [
            "git", "--no-replace-objects",
            "-c", "core.fsmonitor=false",
            "-c", "core.hooksPath=/dev/null",
            "-C", str(repository_root),
            "show", f"{source_revision}:{repository_path}",
        ],
        env=_git_environment(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
        check=True,
    ).stdout


def _git_blob_sha256(
    source_revision: str,
    repository_path: str,
    repository_root: Path = REPOSITORY_ROOT,
) -> str:
    return hashlib.sha256(
        _git_blob(source_revision, repository_path, repository_root)
    ).hexdigest()


def _require_repository_root(path: Path, source_revision: str) -> Path:
    root = path.resolve(strict=True)
    completed = subprocess.run(
        [
            "git", "--no-replace-objects",
            "-c", "core.fsmonitor=false",
            "-c", "core.hooksPath=/dev/null",
            "-C", str(root), "rev-parse", "--show-toplevel",
        ],
        env=_git_environment(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
        check=True,
        text=True,
    )
    if Path(completed.stdout.strip()).resolve(strict=True) != root:
        raise RuntimeError("candidate repository root identity is invalid")
    subprocess.run(
        [
            "git", "--no-replace-objects",
            "-c", "core.fsmonitor=false",
            "-c", "core.hooksPath=/dev/null",
            "-C", str(root),
            "cat-file", "-e", f"{source_revision}^{{commit}}",
        ],
        env=_git_environment(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        timeout=30,
        check=True,
    )
    return root


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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value) -> None:
    path.write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--repository-root", type=Path, default=REPOSITORY_ROOT)
    parser.add_argument("--oci-layout", required=True, type=Path)
    parser.add_argument("--output-directory", required=True, type=Path)
    arguments = parser.parse_args()
    gate = verify_candidate(
        image=arguments.image,
        source_revision=arguments.source_revision,
        repository_root=arguments.repository_root,
        oci_layout=arguments.oci_layout,
        output_directory=arguments.output_directory,
    )
    print(json.dumps(gate, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()