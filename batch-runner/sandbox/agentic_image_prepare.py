"""Remove runtime installation, download, build, and debugging entrypoints."""

from pathlib import Path
import os
import re
import shutil


FORBIDDEN_EXECUTABLES = (
    "pip", "pip3", "pip3.11", "apt", "apt-get", "apt-cache", "dpkg",
    "gcc", "g++", "cc", "c++", "cpp", "gfortran", "make", "cmake",
    "curl", "wget", "ssh", "scp", "sftp", "git", "nc", "ncat", "socat",
    "gdb", "strace", "ltrace",
)
EXECUTABLE_ROOTS = (
    Path("/bin"), Path("/sbin"), Path("/usr/bin"), Path("/usr/sbin"),
    Path("/usr/local/bin"), Path("/usr/local/sbin"),
)
TOOLCHAIN_PATTERN = re.compile(
    r"^(?:[A-Za-z0-9_.+]+-)*(?:gcc|g\+\+|cc|c\+\+|cpp|gfortran|"
    r"ld|as|ar|nm|objcopy|objdump|ranlib|readelf|size|strings|strip)"
    r"(?:-\d+(?:\.\d+)*)?(?:\.(?:bfd|gold))?$"
)


def _is_forbidden_executable(name: str) -> bool:
    return name in FORBIDDEN_EXECUTABLES or TOOLCHAIN_PATTERN.fullmatch(name) is not None


def _matching_executables() -> list[Path]:
    matches = set()
    for root in EXECUTABLE_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            try:
                executable = path.is_symlink() or (
                    path.is_file() and os.access(path, os.X_OK)
                )
            except OSError:
                continue
            if executable and _is_forbidden_executable(path.name):
                matches.add(path)
    return sorted(matches, key=lambda path: path.as_posix())


def main() -> None:
    for executable in FORBIDDEN_EXECUTABLES:
        path = shutil.which(executable)
        if path:
            Path(path).unlink(missing_ok=True)
    for path in _matching_executables():
        path.unlink(missing_ok=True)

    site_packages = Path("/usr/local/lib/python3.11/site-packages")
    for name in ("pip", "setuptools"):
        for candidate in site_packages.glob(f"{name}*"):
            if candidate.is_dir():
                shutil.rmtree(candidate)
            else:
                candidate.unlink(missing_ok=True)
    shutil.rmtree(Path("/usr/local/lib/python3.11/ensurepip"), ignore_errors=True)
    survivors = _matching_executables()
    if survivors:
        raise RuntimeError(
            "forbidden executable survived image preparation: "
            + ", ".join(path.as_posix() for path in survivors[:20])
        )


if __name__ == "__main__":
    main()