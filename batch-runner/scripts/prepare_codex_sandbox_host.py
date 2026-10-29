#!/usr/bin/env python3
"""Admit and prove the Ubuntu 24.04 sandbox before any authentication/model call.

Only a GitHub-hosted 24.04 job can load this binary-scoped AppArmor profile.
No sysctl or existing profile is changed; no setcap/cap-add or alternate
sandbox backend is used. The profile is added to the ephemeral runner's kernel,
not installed persistently.
NAS/local and Azure VM preparation are deliberately not implemented here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import runner_environment as runner
from core.codex_runtime_config import PINNED_CODEX_CLI_VERSION, require_pinned_runtime

REFUSED = "codex_sandbox_preflight_refused"
PROFILE_NAME = "gdpval_codex_bwrap"
PROFILE = f"""abi <abi/4.0>,
include <tunables/global>
profile {PROFILE_NAME} /usr/bin/bwrap flags=(unconfined) {{
  userns,
}}
"""
RESTRICTION = Path("/proc/sys/kernel/apparmor_restrict_unprivileged_userns")
COMMAND_TIMEOUT = 20
SANDBOX_MARKER = "CODEX_SANDBOX_PREFLIGHT_OK"


class SandboxRefused(RuntimeError):
    pass


def _run(argv, *, environment=None, input_text=None, cwd=None):
    # Never inherit credentials, user config, SDK hooks or an authentication
    # helper. All subprocesses are local probes or the fixed profile loader.
    return subprocess.run(
        argv, input=input_text, stdin=subprocess.DEVNULL if input_text is None else None,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
        timeout=COMMAND_TIMEOUT, cwd=cwd,
        env=environment or {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "LANG": "C.UTF-8"},
    )


def _system_bwrap():
    selected = shutil.which("bwrap")
    if not selected or Path(selected).resolve() != Path("/usr/bin/bwrap"):
        raise SandboxRefused("system_bwrap_selection_unverified")
    path = Path(selected).resolve()
    mode = path.stat()
    if (not stat.S_ISREG(mode.st_mode) or mode.st_uid != 0
            or mode.st_mode & (stat.S_IWGRP | stat.S_IWOTH | stat.S_ISUID | stat.S_ISGID)
            or not os.access(path, os.X_OK)):
        raise SandboxRefused("system_bwrap_permissions_unverified")
    return path


def _restriction():
    value = RESTRICTION.read_text(encoding="ascii").strip()
    if value not in {"0", "1"}:
        raise SandboxRefused("apparmor_restriction_unverified")
    return value


def _bwrap_probe(binary):
    # Same namespace geometry as diagnose_codex_sandbox_host.probe_bwrap and
    # the pinned runtime's support check. No legacy/no-net fallback can pass.
    return _run([str(binary), "--unshare-user", "--unshare-net", "--ro-bind", "/", "/", "/bin/true"])


def _cli_probe(binary, scratch):
    paths = {name: scratch / name for name in ("home", "codex", "config", "cache", "data", "state", "tmp")}
    for path in paths.values():
        path.mkdir(mode=0o700)
    environment = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "HOME": str(paths["home"]),
        "CODEX_HOME": str(paths["codex"]), "XDG_CONFIG_HOME": str(paths["config"]),
        "XDG_CACHE_HOME": str(paths["cache"]), "XDG_DATA_HOME": str(paths["data"]),
        "XDG_STATE_HOME": str(paths["state"]), "TMPDIR": str(paths["tmp"])}
    # sandbox is a local command runner, not `exec`, an app-server turn, or a
    # prompt. The command and empty state are fixed; no model request is used.
    # 0.147.0 selects the OS itself. A literal `linux` is treated as the
    # executable, not a subcommand, and panics with ENOENT on the hosted image.
    return _run([str(binary), "sandbox", "--", "/usr/bin/printf", SANDBOX_MARKER],
                environment=environment, cwd=paths["home"])


def _probe_failure_facts(completed):
    """Fixed vocabulary and public Rust basenames, never raw child output."""
    text = (completed.stderr or "")[:16_384].lower()
    vocabulary = {
        "rust_panic": ("panicked at",),
        "permission_denied": ("operation not permitted", "permission denied"),
        "permissions": ("permission",), "profile": ("profile",),
        "bubblewrap": ("bubblewrap", "bwrap"),
        "namespace": ("namespace", "unshare"),
        "working_directory": ("working directory", "cwd"),
        "configuration": ("configuration", "config"),
        "unimplemented": ("not yet implemented", "unimplemented"),
        "invalid_argument": ("invalid argument", "unexpected argument"),
        "missing_file": ("no such file", "not found"),
        "read_only": ("read-only", "read only"),
    }
    tags = sorted(key for key, words in vocabulary.items() if any(word in text for word in words))
    # Never retain arbitrary paths, filenames, tokens, URLs or exception prose.
    public_modules = {"main", "lib", "bwrap", "linux", "linux_sandbox", "sandbox",
                      "permissions", "permission_profile", "config", "spawn", "seccomp", "landlock"}
    locations = sorted({f"{name}.rs:{line}" for name, line in re.findall(
        r"(?:^|[/\s])([a-z_]{1,40})\.rs:([0-9]{1,6})(?::[0-9]+)?", text)
        if name in public_modules})
    return {"tags": tags, "rust_locations": locations[:8]}


def prepare():
    record = {"schema_version": "native-sandbox-preflight-v1", "status": "refused",
              "reason_code": REFUSED, "detail": None, "model_calls": 0,
              "runner_evidence": runner.receipt("diagnostic"),
              "apparmor_profile_added": False, "sysctl_changed": None,
              "sysctl_write_performed": False,
              "bwrap_probe_exit": None, "codex_probe_exit": None, "codex_probe_marker_verified": False}
    try:
        observation = runner.require_execution()
        record["runner_evidence"] = runner.receipt("diagnostic", observation)
        if not observation["github_hosted"] or observation["os_version_id"] != "24.04":
            raise SandboxRefused("profile_preparation_requires_hosted_ubuntu24")
        if os.geteuid() == 0:
            raise SandboxRefused("sandbox_probe_requires_unprivileged_runner")
        root = Path(os.environ.get("RUNNER_TEMP", ""))
        if not root.is_absolute() or not root.is_dir() or root.is_symlink():
            raise SandboxRefused("runner_temp_unverified")
        sdk, cli_version = require_pinned_runtime()
        record["runtime_versions"] = {"sdk": sdk, "cli": cli_version}
        from codex_cli_bin import bundled_codex_path
        binary = bundled_codex_path()
        version = _run([str(binary), "--version"])
        if version.returncode != 0 or version.stdout.strip() != f"codex-cli {PINNED_CODEX_CLI_VERSION}":
            raise SandboxRefused("pinned_cli_version_unverified")
        bwrap = _system_bwrap()
        record["bwrap_sha256"] = hashlib.sha256(bwrap.read_bytes()).hexdigest()
        before = _restriction()
        record["apparmor_restriction_before"] = before
        initial = _bwrap_probe(bwrap)
        record["bwrap_probe_exit_before"] = initial.returncode
        if initial.returncode != 0:
            if before != "1":
                raise SandboxRefused("namespace_failure_without_apparmor_restriction")
            # -a adds only this named profile; unlike -r it cannot replace an
            # existing profile. The path and profile text are not caller inputs.
            loaded = _run(["/usr/bin/sudo", "-n", "/usr/sbin/apparmor_parser", "-a"], input_text=PROFILE)
            if loaded.returncode != 0:
                raise SandboxRefused("apparmor_profile_add_failed")
            record["apparmor_profile_added"] = True
            record["apparmor_profile_sha256"] = hashlib.sha256(PROFILE.encode()).hexdigest()
        probe = _bwrap_probe(bwrap)
        record["bwrap_probe_exit"] = probe.returncode
        if probe.returncode != 0:
            raise SandboxRefused("bubblewrap_namespace_probe_failed")
        with tempfile.TemporaryDirectory(prefix="codex-sandbox-preflight-", dir=root) as scratch:
            completed = _cli_probe(binary, Path(scratch))
        record["codex_probe_exit"] = completed.returncode
        record["codex_probe_marker_verified"] = completed.returncode == 0 and completed.stdout == SANDBOX_MARKER
        if not record["codex_probe_marker_verified"]:
            record["codex_probe_failure_facts"] = _probe_failure_facts(completed)
            raise SandboxRefused("pinned_codex_sandbox_probe_failed")
        after = _restriction()
        record["apparmor_restriction_after"] = after
        record["sysctl_changed"] = after != before
        if after != before or _system_bwrap() != bwrap or hashlib.sha256(bwrap.read_bytes()).hexdigest() != record["bwrap_sha256"]:
            raise SandboxRefused("sandbox_host_changed_during_preflight")
        runner.require_execution(observation)
        record.update(status="ready", reason_code=None)
    except runner.ExecutionEnvironmentRefused as error:
        record["detail"] = error.code
        record["runner_evidence"] = runner.receipt("diagnostic", error.observation)
    except SandboxRefused as error:
        record["detail"] = str(error)
    except subprocess.TimeoutExpired:
        record["detail"] = "sandbox_preflight_command_timeout"
    except Exception:
        # Do not publish raw process output, configuration, or exception text.
        record["detail"] = "sandbox_preflight_dependency_or_io_failure"
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    record = prepare()
    try:
        if not args.out.is_absolute() or args.out.is_symlink():
            raise ValueError("unsafe report path")
        with args.out.open("x", encoding="utf-8") as stream:
            json.dump(record, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
    except Exception:
        print(f"{REFUSED}: sandbox_preflight_receipt_unwritable")
        return 2
    print(record["status"] if record["status"] == "ready" else f"{REFUSED}: {record['detail']}")
    return 0 if record["status"] == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
