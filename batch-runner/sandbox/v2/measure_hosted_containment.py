"""Measure the Agentic V2 Docker containment controls on a hosted runner."""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any, Mapping


BATCH_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = BATCH_ROOT.parent
if str(BATCH_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_ROOT))

from core.agentic_v2_supply_chain import (  # noqa: E402
    canonical_sha256,
    validate_containment_report,
)
from sandbox.v2.verify_candidate import measure_docker_containment  # noqa: E402


_SOURCE_SHA = re.compile(r"[0-9a-f]{40}")
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_HEX_DIGEST = re.compile(r"[0-9a-f]{64}")
_CHECK_LABELS = {
    "network_none": "Network disabled",
    "read_only_rootfs": "Read-only root filesystem",
    "non_root_uid": "Non-root UID/GID",
    "cap_drop_all": "All capabilities dropped",
    "no_new_privileges": "No new privileges",
    "memory_limit": "Effective memory limit",
    "cpu_quota": "Effective CPU quota",
    "pids_limit": "PID limit",
}
_UNMEASURED_REQUIRED_EVIDENCE = (
    "capability_receipt",
    "cve",
    "license",
    "microvm",
    "oci_layout",
    "provenance",
    "sbom",
    "signature",
)
_GATE_REASON = (
    "Tier 1 measures containment only; production activation remains disabled "
    "until every required evidence item is verified."
)


def _read_parent_lock(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != "1.0"
        or value.get("reference")
        != "ghcr.io/hyeonsangjeon/gdpval-sandbox@" + str(
            value.get("manifest_digest")
        )
        or _DIGEST.fullmatch(str(value.get("manifest_digest"))) is None
        or _DIGEST.fullmatch(str(value.get("observed_local_image_id"))) is None
        or value.get("platform") != "linux/amd64"
    ):
        raise ValueError("hosted containment parent lock is invalid")
    return value


def _git(*arguments: str) -> str:
    return subprocess.run(
        ["/usr/bin/git", "-C", str(REPOSITORY_ROOT), *arguments],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
        text=True,
        timeout=30,
        env={
            "PATH": "/usr/bin:/bin",
            "HOME": "/nonexistent",
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_TERMINAL_PROMPT": "0",
        },
    ).stdout.strip()


def build_hosted_result(
    *,
    source_revision: str,
    parent_lock: Mapping[str, Any],
    measurement: Mapping[str, Any],
    runner: Mapping[str, Any],
) -> dict[str, Any]:
    if _SOURCE_SHA.fullmatch(source_revision) is None:
        raise ValueError("hosted containment source revision is invalid")
    report = validate_containment_report(measurement.get("containment"))
    if (
        measurement.get("image_id") != parent_lock.get("observed_local_image_id")
        or measurement.get("platform") != parent_lock.get("platform")
        or parent_lock.get("reference") not in measurement.get("repo_digests", [])
    ):
        raise ValueError("hosted containment image differs from parent lock")
    if (
        not isinstance(runner, Mapping)
        or runner.get("environment") != "github-hosted"
        or runner.get("os") != "Linux"
        or runner.get("architecture") != "X64"
        or not isinstance(runner.get("kernel_release"), str)
        or not runner["kernel_release"]
        or runner.get("cgroup") not in {"v1", "v2", "unknown"}
    ):
        raise ValueError("hosted containment runner identity is invalid")
    checks = {
        name: {
            "label": label,
            "status": "verified" if report["checks"][name] else "failed",
        }
        for name, label in _CHECK_LABELS.items()
    }
    result = {
        "schema_version": "1.0",
        "evidence_ladder": ["verified", "failed", "not_run"],
        "foundation_only": True,
        "production_activation": "disabled",
        "source_revision": source_revision,
        "parent_image": {
            "reference": parent_lock["reference"],
            "manifest_digest": parent_lock["manifest_digest"],
            "image_id": measurement["image_id"],
            "platform": measurement["platform"],
        },
        "runner": dict(runner),
        "containment": {
            "status": report["status"],
            "checks": checks,
            "report_sha256": report["report_sha256"],
            "host_scope": report["host_scope"],
        },
        "aggregate_gate": {
            "status": "blocked",
            "can_leave_blocked": False,
            "containment_is_blocking": report["status"] != "verified",
            "unmeasured_required_evidence": list(_UNMEASURED_REQUIRED_EVIDENCE),
            "reason": _GATE_REASON,
        },
    }
    result["result_sha256"] = canonical_sha256(result)
    validate_hosted_result(result)
    return result


def validate_hosted_result(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "schema_version",
        "evidence_ladder",
        "foundation_only",
        "production_activation",
        "source_revision",
        "parent_image",
        "runner",
        "containment",
        "aggregate_gate",
        "result_sha256",
    }:
        raise ValueError("hosted containment result fields are invalid")
    document = json.loads(json.dumps(value, allow_nan=False))
    claimed = document.pop("result_sha256")
    parent = document["parent_image"]
    runner = document["runner"]
    containment = document["containment"]
    checks = containment.get("checks")
    gate = document["aggregate_gate"]
    if (
        document["schema_version"] != "1.0"
        or document["evidence_ladder"] != ["verified", "failed", "not_run"]
        or document["foundation_only"] is not True
        or document["production_activation"] != "disabled"
        or _SOURCE_SHA.fullmatch(str(document["source_revision"])) is None
        or not isinstance(parent, dict)
        or set(parent) != {"reference", "manifest_digest", "image_id", "platform"}
        or parent.get("reference")
        != "ghcr.io/hyeonsangjeon/gdpval-sandbox@" + str(
            parent.get("manifest_digest")
        )
        or _DIGEST.fullmatch(str(parent.get("manifest_digest"))) is None
        or _DIGEST.fullmatch(str(parent.get("image_id"))) is None
        or parent.get("platform") != "linux/amd64"
        or not isinstance(runner, dict)
        or set(runner) != {
            "environment", "os", "architecture", "kernel_release", "cgroup",
            "github_run_id", "github_run_attempt",
        }
        or runner.get("environment") != "github-hosted"
        or runner.get("os") != "Linux"
        or runner.get("architecture") != "X64"
        or not isinstance(runner.get("kernel_release"), str)
        or not runner["kernel_release"]
        or runner.get("cgroup") not in {"v1", "v2", "unknown"}
        or any(
            value is not None and (
                not isinstance(value, str) or not value.isdigit()
            )
            for value in (
                runner.get("github_run_id"), runner.get("github_run_attempt")
            )
        )
        or not isinstance(containment, dict)
        or set(containment) != {
            "status", "checks", "report_sha256", "host_scope"
        }
        or not isinstance(checks, dict)
        or set(checks) != set(_CHECK_LABELS)
        or any(
            item != {
                "label": _CHECK_LABELS[name],
                "status": item.get("status"),
            }
            or item.get("status") not in {"verified", "failed", "not_run"}
            for name, item in checks.items()
        )
        or document["containment"]["status"]
        != (
            "verified"
            if all(item["status"] == "verified" for item in checks.values())
            else "failed"
        )
        or _HEX_DIGEST.fullmatch(str(containment.get("report_sha256"))) is None
        or containment.get("host_scope") != "exact-docker-daemon"
        or not isinstance(gate, dict)
        or set(gate) != {
            "status", "can_leave_blocked", "containment_is_blocking",
            "unmeasured_required_evidence", "reason",
        }
        or gate.get("status") != "blocked"
        or gate.get("can_leave_blocked") is not False
        or gate.get("containment_is_blocking")
        != (document["containment"]["status"] != "verified")
        or gate.get("unmeasured_required_evidence")
        != list(_UNMEASURED_REQUIRED_EVIDENCE)
        or gate.get("reason") != _GATE_REASON
        or _HEX_DIGEST.fullmatch(str(claimed)) is None
        or claimed != canonical_sha256(document)
    ):
        raise ValueError("hosted containment result identity is invalid")
    return value


def render_markdown(result: Mapping[str, Any]) -> str:
    validated = validate_hosted_result(dict(result))
    lines = [
        "# Agentic Sandbox V2 Hosted Containment",
        "",
        f"- Source: `{validated['source_revision']}`",
        f"- Image: `{validated['parent_image']['reference']}`",
        f"- Runner: `{validated['runner']['environment']}` / "
        f"`{validated['runner']['kernel_release']}` / "
        f"`cgroup {validated['runner']['cgroup']}`",
        f"- Containment: **{validated['containment']['status']}**",
        "",
        "| Check | Status |",
        "|---|---|",
    ]
    lines.extend(
        f"| {item['label']} | `{item['status']}` |"
        for item in validated["containment"]["checks"].values()
    )
    lines.extend([
        "",
        "## Aggregate gate",
        "",
        "- Status: `blocked`",
        "- Can leave blocked: `false`",
        "- Unmeasured required evidence: "
        + ", ".join(
            f"`{name}`"
            for name in validated["aggregate_gate"][
                "unmeasured_required_evidence"
            ]
        ),
        "- Decision: " + validated["aggregate_gate"]["reason"],
        "",
    ])
    return "\n".join(lines)


def _runner_identity() -> dict[str, Any]:
    return {
        "environment": os.environ.get("RUNNER_ENVIRONMENT", "unknown"),
        "os": os.environ.get("RUNNER_OS", "unknown"),
        "architecture": os.environ.get("RUNNER_ARCH", "unknown"),
        "kernel_release": platform.release(),
        "cgroup": (
            "v2"
            if Path("/sys/fs/cgroup/cgroup.controllers").is_file()
            else "v1"
            if Path("/sys/fs/cgroup").is_dir()
            else "unknown"
        ),
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
    }


def _write_outputs(output_directory: Path, result: dict[str, Any]) -> None:
    output_directory = output_directory.resolve()
    if output_directory.exists() or output_directory.is_symlink():
        raise ValueError("hosted containment output directory already exists")
    output_directory.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(
        prefix=f".{output_directory.name}.",
        dir=output_directory.parent,
    ))
    try:
        (temporary / "hosted-containment-result.json").write_text(
            json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        (temporary / "hosted-containment-result.md").write_text(
            render_markdown(result),
            encoding="utf-8",
        )
        os.replace(temporary, output_directory)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-directory", required=True, type=Path)
    arguments = parser.parse_args()
    source_revision = _git("rev-parse", "HEAD")
    if _git("status", "--porcelain", "--untracked-files=all"):
        raise RuntimeError("hosted containment measurement requires a clean tree")
    expected_revision = os.environ.get("MEASUREMENT_SOURCE_SHA")
    if expected_revision and source_revision != expected_revision:
        raise RuntimeError("hosted containment checkout differs from requested source")
    parent_lock = _read_parent_lock(
        BATCH_ROOT / "sandbox" / "v2" / "parent.lock.json"
    )
    measurement = measure_docker_containment(
        parent_lock["reference"],
        session_id=uuid.uuid4().hex,
    )
    result = build_hosted_result(
        source_revision=source_revision,
        parent_lock=parent_lock,
        measurement=measurement,
        runner=_runner_identity(),
    )
    _write_outputs(arguments.output_directory, result)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()