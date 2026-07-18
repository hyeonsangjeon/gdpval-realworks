"""Fail-closed runtime audit for the hardened agentic image."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import stat
from pathlib import Path


EXECUTABLE_ROOTS = (
    Path("/bin"),
    Path("/sbin"),
    Path("/usr/bin"),
    Path("/usr/sbin"),
    Path("/usr/local/bin"),
    Path("/usr/local/sbin"),
)
FORBIDDEN_EXECUTABLES = {
    "pip", "pip3", "pip3.11", "apt", "apt-get", "apt-cache", "dpkg",
    "gcc", "g++", "cc", "c++", "cpp", "gfortran", "make", "cmake",
    "curl", "wget", "ssh", "scp", "sftp", "git", "nc", "ncat", "socat",
    "gdb", "strace", "ltrace", "sh", "bash", "dash",
}
TOOLCHAIN_PATTERN = re.compile(
    r"^(?:[A-Za-z0-9_.+]+-)*(?:gcc|g\+\+|cc|c\+\+|cpp|gfortran|"
    r"ld|as|ar|nm|objcopy|objdump|ranlib|readelf|size|strings|strip)"
    r"(?:-\d+(?:\.\d+)*)?(?:\.(?:bfd|gold))?$"
)


def audit() -> dict:
    if os.geteuid() != 65532 or os.getegid() != 65532:
        raise RuntimeError("agentic image UID/GID is not fixed at 65532")
    for module in ("pip", "ensurepip", "setuptools"):
        if importlib.util.find_spec(module) is not None:
            raise RuntimeError(f"forbidden Python module survived: {module}")

    violations: list[str] = []
    capabilities: list[str] = []
    for root in EXECUTABLE_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            try:
                metadata = path.lstat()
                if (
                    path.name in FORBIDDEN_EXECUTABLES
                    or TOOLCHAIN_PATTERN.fullmatch(path.name)
                ):
                    violations.append(path.as_posix())
                if stat.S_ISREG(metadata.st_mode) and metadata.st_mode & (
                    stat.S_ISUID | stat.S_ISGID | stat.S_IWOTH
                ):
                    violations.append(path.as_posix())
                if stat.S_ISREG(metadata.st_mode):
                    capability = os.getxattr(
                        path, "security.capability", follow_symlinks=False
                    )
                    if capability:
                        capabilities.append(path.as_posix())
            except (FileNotFoundError, PermissionError, OSError):
                continue
    if violations:
        raise RuntimeError(
            "forbidden or privileged executable survived: "
            + ", ".join(sorted(set(violations))[:20])
        )
    if capabilities:
        raise RuntimeError(
            "file capability survived: "
            + ", ".join(sorted(set(capabilities))[:20])
        )
    sbom = Path("/opt/gdpval/agentic-sbom.spdx.json")
    document = json.loads(sbom.read_text(encoding="utf-8"))
    if document.get("spdxVersion") != "SPDX-2.3" or not document.get("packages"):
        raise RuntimeError("runtime SPDX SBOM is missing or invalid")
    return {
        "audit": "pass",
        "uid": os.geteuid(),
        "gid": os.getegid(),
        "sbom_packages": len(document["packages"]),
    }


def main() -> None:
    print(json.dumps(audit(), sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
