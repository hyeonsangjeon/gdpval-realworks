"""Model-free readiness report for a future Firecracker containment plane."""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
from pathlib import Path
from typing import Any, Callable, Mapping

from core.agentic_v2_substrate import canonical_sha256


def inspect_microvm_readiness(
    *,
    path_lookup: Callable[[str], str | None] = shutil.which,
    kvm_path: str | Path = "/dev/kvm",
    asset_paths: Mapping[str, str | Path] | None = None,
    kvm_probe: Callable[[Path], bool] | None = None,
) -> dict[str, Any]:
    tools = {}
    for name in ("firecracker", "jailer"):
        raw_path = path_lookup(name)
        path = Path(raw_path) if raw_path else None
        tools[name] = (
            {"status": "present", "sha256": _sha256(path), "size": path.stat().st_size}
            if path is not None and path.is_file() and not path.is_symlink()
            else {"status": "missing", "sha256": None, "size": None}
        )
    assets = {}
    for name, raw_path in sorted((asset_paths or {}).items()):
        path = Path(raw_path)
        assets[name] = (
            {"status": "present", "sha256": _sha256(path), "size": path.stat().st_size}
            if path.is_file() and not path.is_symlink()
            else {"status": "missing", "sha256": None, "size": None}
        )
    kvm = Path(kvm_path)
    kvm_available = (kvm_probe or _is_kvm_device)(kvm)
    checks = {
        "firecracker": tools["firecracker"]["status"] == "present",
        "jailer": tools["jailer"]["status"] == "present",
        "kvm": kvm_available,
        "kernel": assets.get("kernel", {}).get("status") == "present",
        "rootfs": assets.get("rootfs", {}).get("status") == "present",
    }
    ready = all(checks.values())
    report = {
        "schema_version": "1.0",
        "foundation_only": True,
        "production_activation": "disabled",
        "runtime": "firecracker",
        "status": "ready_for_boot_test" if ready else "not_run",
        "checks": checks,
        "tools": tools,
        "assets": assets,
        "network": "none",
        "rootfs_mode": "read-only",
        "workdir": "ephemeral-quota",
    }
    report["report_sha256"] = canonical_sha256(report)
    return report


def validate_microvm_readiness_report(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {
        "schema_version",
        "foundation_only",
        "production_activation",
        "runtime",
        "status",
        "checks",
        "tools",
        "assets",
        "network",
        "rootfs_mode",
        "workdir",
        "report_sha256",
    }:
        raise ValueError("agentic v2 microvm readiness fields are invalid")
    document = dict(value)
    claimed = document.pop("report_sha256")
    if (
        document["schema_version"] != "1.0"
        or document["foundation_only"] is not True
        or document["production_activation"] != "disabled"
        or document["runtime"] != "firecracker"
        or document["network"] != "none"
        or document["rootfs_mode"] != "read-only"
        or document["workdir"] != "ephemeral-quota"
        or set(document["checks"]) != {"firecracker", "jailer", "kvm", "kernel", "rootfs"}
        or any(type(item) is not bool for item in document["checks"].values())
        or set(document["tools"]) != {"firecracker", "jailer"}
        or any(
            not isinstance(item, dict)
            or set(item) != {"status", "sha256", "size"}
            or item["status"] not in {"present", "missing"}
            or (
                item["status"] == "present"
                and (
                    not isinstance(item["sha256"], str)
                    or len(item["sha256"]) != 64
                    or type(item["size"]) is not int
                    or item["size"] <= 0
                )
            )
            for item in document["tools"].values()
        )
        or document["status"] != (
            "ready_for_boot_test" if all(document["checks"].values()) else "not_run"
        )
        or claimed != canonical_sha256(document)
    ):
        raise ValueError("agentic v2 microvm readiness identity is invalid")
    return dict(value)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_kvm_device(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except OSError:
        return False
    return (
        stat.S_ISCHR(metadata.st_mode)
        and not path.is_symlink()
        and os.access(path, os.R_OK | os.W_OK)
    )