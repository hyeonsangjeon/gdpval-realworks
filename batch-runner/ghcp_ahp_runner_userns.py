"""Hosted zero-turn-only bwrap diagnostics, exact AppArmor grant and rollback.

No credentials, host, SDK launcher, model traffic or sandbox-policy change.
The namespace canary uses the broker's unchanged net/PID/capability boundary.
Preparation is not thread/application/admission evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile

import ghcp_ahp_metadata_broker as broker
import ghcp_ahp_prewarm_zero_turn as prewarm
import ghcp_ahp_probe as probe
import ghcp_ahp_wire_capture as wire
from ghcp_ahp_errors import Refused

RESTRICT = "kernel.apparmor_restrict_unprivileged_userns"
CLONE = "kernel.unprivileged_userns_clone"
MAX_NAMESPACES = "user.max_user_namespaces"
PROC_PATHS = {RESTRICT: Path("/proc/sys/kernel/apparmor_restrict_unprivileged_userns"),
              CLONE: Path("/proc/sys/kernel/unprivileged_userns_clone"),
              MAX_NAMESPACES: Path("/proc/sys/user/max_user_namespaces")}
SYSCTL_PATHS = (Path("/usr/sbin/sysctl"), Path("/sbin/sysctl"))
BWRAP_SHA256 = "77360cb751ccedc5971391444ac86a8a33c15b04d6b4a6fe45f5d25496e62c4c"
SCHEMA = "ghcp-runner-userns-v1"
ENVIRONMENT = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}
PROFILE_PREFIX = "ghcp-zero-turn-bwrap-"
SYSTEM_PATHS = (Path("/usr/bin/bwrap"), Path("/bin/bwrap"))

# Only /bin/true-equivalent measurement, inside an additional read-only root
# and new user/net/PID namespaces. No sockets, SDK, CLI, auth or workspace writes.
INNER_AUDIT = '''import json, os, socket, sys
from pathlib import Path
status = dict(line.split(":", 1) for line in Path("/proc/self/status").read_text().splitlines() if ":" in line)
mounts = [line.split() for line in Path("/proc/mounts").read_text().splitlines()]
value = {"netns_changed": os.readlink("/proc/self/ns/net") != sys.argv[1],
         "userns_changed": os.readlink("/proc/self/ns/user") != sys.argv[2],
         "pidns_changed": os.readlink("/proc/self/ns/pid") != sys.argv[3],
         "interfaces": sorted(name for _, name in socket.if_nameindex()),
         "no_new_privs": status.get("NoNewPrivs", "").strip(),
         "effective_capabilities": status.get("CapEff", "").strip(),
         "root_read_only": any(row[1] == "/" and "ro" in row[3].split(",") for row in mounts)}
print(json.dumps(value, sort_keys=True))
'''
PROOF = {"netns_changed": True, "userns_changed": True, "pidns_changed": True,
         "interfaces": ["lo"], "no_new_privs": "1", "effective_capabilities": "0000000000000000",
         "root_read_only": True}
EXEC_CANARY = '''import hashlib, os, sys
binary, expected, source, audit = sys.argv[1:]
fd = os.open(binary, os.O_RDONLY)
with os.fdopen(os.dup(fd), "rb") as stream:
    actual = hashlib.file_digest(stream, "sha256").hexdigest()
if actual != expected:
    raise SystemExit("runner_userns_bwrap_drift")
args = [binary, "--unshare-user", "--unshare-net", "--unshare-pid", "--die-with-parent", "--new-session",
        "--ro-bind", "/", "/", "--proc", "/proc", "--dev", "/dev", "--chdir", "/", "--",
        sys.executable, "-I", "-c", audit, os.readlink("/proc/self/ns/net"),
        os.readlink("/proc/self/ns/user"), os.readlink("/proc/self/ns/pid")]
# Pinned bundled_bwrap.rs:80-94 executes the digest-verified file through /proc.
os.execv("/proc/self/fd/" + str(fd) if source == "bundled" else binary, args)
'''


def require(condition, reason):
    if not condition:
        raise Refused(reason)


def safe_path(value):
    path = Path(value)
    require(path.is_absolute() and re.fullmatch(r"/[A-Za-z0-9_./@+\-]+", str(path))
            and ".." not in path.parts, "runner_userns_path_refused")
    require(not any(item.is_symlink() for item in (path, *path.parents)), "runner_userns_symlink_refused")
    return path


def profile_name(identity):
    require(all(re.fullmatch(r"[1-9][0-9]*", identity.get(key, ""))
                for key in ("github_run_id", "github_run_attempt")), "runner_userns_identity_refused")
    return PROFILE_PREFIX + identity["github_run_id"] + "-" + identity["github_run_attempt"]


def profile_text(binary, identity):
    path = safe_path(binary)
    # Same AppArmor userns grant described in OpenAI's Ubuntu 24.04 guidance,
    # attached to ONE resolved executable (no globs, parent/profile exceptions).
    return ('abi <abi/4.0>,\ninclude <tunables/global>\n'
            f'profile {profile_name(identity)} "{path}" flags=(unconfined) {{\n  userns,\n}}\n')


def read_proc_value(path):
    """One direct file read; absent, read error and measured zero are distinct."""
    row = {"source": "procfs", "path": str(path), "status": "not_read",
           "value": "not_reported", "raw": None, "error": None}
    try:
        with path.open("r", encoding="ascii") as source:
            raw = source.read(129)
        row["raw"] = raw
        if len(raw) > 128 or not re.fullmatch(r"[0-9]+", raw.strip()):
            row["status"] = "invalid_value"
        else:
            row.update(status="measured", value=int(raw.strip()))
    except (OSError, UnicodeError) as error:
        row["error"] = {"type": type(error).__name__, "errno": getattr(error, "errno", None), "message": str(error)}
        if isinstance(error, FileNotFoundError):
            row.update(status="absent", value="absent")
        else:
            row["status"] = "read_error"
    return row


def sysctl_identity(candidate):
    # /sbin may be a distro-owned usrmerge symlink. Resolve it, then bind the
    # exact regular executable bytes. No PATH search or alternate command.
    require(candidate in SYSCTL_PATHS, "runner_userns_sysctl_path_refused")
    resolved = safe_path(candidate.resolve(strict=True))
    require(resolved in SYSCTL_PATHS, "runner_userns_sysctl_target_refused")
    info = resolved.stat()
    require(stat.S_ISREG(info.st_mode) and info.st_mode & 0o111 and os.access(resolved, os.X_OK)
            and not info.st_mode & (stat.S_ISUID | stat.S_ISGID), "runner_userns_sysctl_mode_refused")
    return {"candidate": str(candidate), "path": str(resolved), "sha256": probe.digest(resolved), "bytes": info.st_size}


class Runner:
    def __init__(self):
        prewarm.context()  # Refuse the NAS before any process or system access.

    def run(self, command):
        prewarm.context()
        try:
            value = subprocess.run(command, env=dict(ENVIRONMENT), capture_output=True, text=True, timeout=25,
                                   check=False)
            require(len(value.stdout) + len(value.stderr) <= 1024 * 1024, "runner_userns_output_limit")
            return {"returncode": value.returncode, "stdout": value.stdout, "stderr": value.stderr}
        except (OSError, subprocess.TimeoutExpired) as error:
            # Never include subprocess exceptions/environments, only the class.
            return {"returncode": -1, "stdout": "", "stderr": type(error).__name__}

    def sysctls(self):
        prewarm.context()  # No kernel reads on NAS, including direct callers.
        return {key: read_proc_value(path) for key, path in PROC_PATHS.items()}

    def sysctl_binary(self):
        prewarm.context()
        for candidate in SYSCTL_PATHS:
            try:
                candidate.stat()
            except FileNotFoundError:
                continue  # Only absence of /usr/sbin permits the /sbin choice.
            return sysctl_identity(candidate)
        raise Refused("runner_userns_sysctl_binary_not_found")

    def check_sysctl_binary(self, binary):
        prewarm.context()
        require(type(binary) is dict and type(binary.get("candidate")) is str,
                "runner_userns_sysctl_identity_missing")
        require(equal(binary, sysctl_identity(Path(binary["candidate"]))), "runner_userns_sysctl_binary_changed")

    def write_sysctl(self, binary, value):
        require(type(value) is int and value in (0, 1), "runner_userns_sysctl_write_refused")
        self.check_sysctl_binary(binary)  # Keep the SAME path/hash for cleanup.
        return self.run(["sudo", "-n", binary["path"], "-w", RESTRICT + "=" + str(value)])

    def aa_status(self):
        row = self.run(["sudo", "-n", "aa-status", "--json"])
        summary = {"returncode": row["returncode"], "stderr": row["stderr"][:2048],
                   "profiles": "not_reported", "processes": "not_reported"}
        try:
            value = probe.strict_json(row["stdout"])
            profiles, processes = value.get("profiles"), value.get("processes")
            if type(profiles) is dict:
                summary["profiles"] = {mode: list(profiles.values()).count(mode)
                                       for mode in sorted(set(profiles.values()))}
            if type(processes) is dict:
                summary["processes"] = len(processes)
        except (ValueError, TypeError, AttributeError, Refused):
            pass  # The diagnostic's nonzero code/unknown fields remain explicit.
        return summary

    def profile_loaded(self, name):
        row = self.run(["sudo", "-n", "cat", "/sys/kernel/security/apparmor/profiles"])
        require(row["returncode"] == 0, "runner_userns_profile_inventory_unavailable")
        return name + " (unconfined)" in row["stdout"].splitlines()

    def namespace_probe(self, binary):
        command = [*broker.isolation_prefix(), sys.executable, "-I", "-c", EXEC_CANARY,
                   binary["path"], binary["sha256"], binary["source"], INNER_AUDIT]
        row = self.run(command)
        try:
            proof = probe.strict_json(row["stdout"])
        except (ValueError, TypeError, Refused):
            proof = None
        return {**brief(row), "proof": proof, "passed": row["returncode"] == 0 and equal(proof, PROOF),
                "scope": "namespace_canary_not_native_thread_or_admission"}


def brief(row):
    return {"returncode": row["returncode"], "stdout": row["stdout"][:4096], "stderr": row["stderr"][:4096]}


def selected_bwrap(prepared, runner):
    # Pinned launcher.rs:135-218 prefers a PATH bwrap with --as-pid-1/--perms,
    # otherwise the SDK resource. Do not silently substitute /usr/bin/bwrap.
    native, _, _ = wire.discover_native_binary(prepared, probe.load_manifest())
    bundled = safe_path(native.parent.parent / "codex-resources/bwrap")
    require(bundled.is_file() and probe.digest(bundled) == BWRAP_SHA256, "runner_userns_bundled_bwrap_drift")
    candidates = []
    selected, source = bundled, "bundled"
    for candidate in SYSTEM_PATHS:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            actual = safe_path(candidate.resolve())
            row = runner.run([str(actual), "--help"])
            text = row["stdout"] + row["stderr"]
            accepted = "--as-pid-1" in text and "--perms" in text
            candidates.append({"path": str(actual), "help_returncode": row["returncode"], "selected": accepted})
            if accepted:
                selected, source = actual, "system"
            # PATH resolution picks the first executable, even when its help
            # is unsuitable; SDK then falls back to its bundled resource.
            break
    mode = selected.stat().st_mode
    require(stat.S_ISREG(mode) and mode & 0o111 and not mode & (stat.S_ISUID | stat.S_ISGID),
            "runner_userns_bwrap_mode_refused")
    version = runner.run([str(selected), "--version"])
    require(version["returncode"] == 0, "runner_userns_bwrap_version_failed")
    return {"path": str(selected), "sha256": probe.digest(selected), "bytes": selected.stat().st_size,
            "source": source, "version": version["stdout"].strip()[:256], "candidates": candidates,
            "sdk_bundled_path": str(bundled), "sdk_bundled_sha256": BWRAP_SHA256}


def values(snapshot):
    return {key: snapshot.get(key, {}).get("value", "not_reported") for key in PROC_PATHS}


def measured(snapshot):
    return all(type(snapshot.get(key)) is dict and snapshot[key].get("source") == "procfs"
               and snapshot[key].get("path") == str(path) and snapshot[key].get("status") == "measured"
               and type(snapshot[key].get("value")) is int and snapshot[key]["value"] >= 0
               and snapshot[key].get("error") is None for key, path in PROC_PATHS.items())


def usable(snapshot):
    value = values(snapshot)
    return (measured(snapshot) and value[RESTRICT] in (0, 1) and value[CLONE] == 1
            and value[MAX_NAMESPACES] > 0)


def equal(left, right):
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(right, sort_keys=True, allow_nan=False)


def write_receipt(evidence, record):
    # This one owned journal is atomically updated before/after each privileged
    # operation. All final receipts retain the existing exclusive-write API.
    destination = safe_path(evidence / "runner-userns.json")
    fd, temporary = tempfile.mkstemp(prefix=".userns-", dir=evidence)
    try:
        with os.fdopen(fd, "w") as output:
            output.write(json.dumps(probe.redact(record), sort_keys=True, indent=2, allow_nan=False) + "\n")
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def prepare(prepared, evidence, identity, runner):
    evidence = safe_path(evidence)
    evidence.mkdir(parents=True, exist_ok=True)
    require(not (evidence / "runner-userns.json").exists(), "runner_userns_no_repeat")
    record = {"schema": SCHEMA, "runner": dict(identity), "status": "preparing", "method": "not_selected",
              "synthetic": False, "execution_allowed": False, "admission_allowed": False,
              "model_calls": 0, "before": runner.sysctls(), "aa_status_before": runner.aa_status(),
              "profile": {"attempted": False, "loaded": False}, "sysctl_attempted": False,
              "isolation": {"codex_sandbox_changed": False, "netns_omitted": False, "network_allowed": False,
                            "privilege_boundary": "same_as_metadata_broker"}}
    write_receipt(evidence, record)
    try:
        binary = record["bwrap"] = selected_bwrap(prepared, runner)
        record["baseline"] = runner.namespace_probe(binary)
        before = values(record["before"])
        require(usable(record["before"]), "runner_userns_sysctls_not_usable")
        if record["baseline"]["passed"]:
            record.update(method="none_required", final_probe=record["baseline"])
        else:
            require(before[RESTRICT] == 1, "runner_userns_failure_without_apparmor_restriction")
            text = profile_text(binary["path"], identity)
            path = evidence / "runner-userns.apparmor"
            with path.open("x") as output:
                output.write(text)
            record["profile"] = {"attempted": True, "loaded": False, "name": profile_name(identity),
                                 "path": str(path), "text": text, "sha256": probe.digest(path)}
            write_receipt(evidence, record)  # Cleanup intent before privileged mutation.
            row = runner.run(["sudo", "-n", "apparmor_parser", "--add", str(path)])
            record["profile"]["load"] = brief(row)
            record["profile"]["loaded"] = row["returncode"] == 0
            write_receipt(evidence, record)
            if record["profile"]["loaded"]:
                require(runner.profile_loaded(profile_name(identity)), "runner_userns_profile_not_registered")
                record["profile_probe"] = runner.namespace_probe(binary)
            if record.get("profile_probe", {}).get("passed") is True:
                record.update(method="a_exact_bwrap_profile", final_probe=record["profile_probe"])
            else:
                # Only this job's scalar restriction is changed, and only after
                # the exact-binary profile failed. Leave clone/netns/caps alone.
                if record["profile"]["loaded"]:
                    removed = runner.run(["sudo", "-n", "apparmor_parser", "--remove", str(path)])
                    record["profile"]["remove_before_fallback"] = brief(removed)
                    require(removed["returncode"] == 0 and not runner.profile_loaded(profile_name(identity)),
                            "runner_userns_profile_remove_failed")
                    record["profile"]["loaded"] = False
                before_write = runner.sysctls()
                require(usable(before_write) and equal(values(before_write), before), "runner_userns_state_drift_before_fallback")
                record["sysctl_binary"] = runner.sysctl_binary()
                record["sysctl_attempted"] = True
                write_receipt(evidence, record)
                changed = runner.write_sysctl(record["sysctl_binary"], 0)
                record["sysctl_change"] = brief(changed)
                require(changed["returncode"] == 0, "runner_userns_sysctl_change_failed")
                record["after_sysctl_write"] = runner.sysctls()
                require(usable(record["after_sysctl_write"]) and equal(values(record["after_sysctl_write"]),
                        {**before, RESTRICT: 0}), "runner_userns_sysctl_readback_failed")
                record.update(method="b_job_scoped_sysctl", final_probe=runner.namespace_probe(binary))
        require(record["final_probe"]["passed"] is True, "runner_userns_namespace_probe_failed")
        record["after"] = runner.sysctls()
        expected = {**before, RESTRICT: 0} if record["method"] == "b_job_scoped_sysctl" else before
        require(usable(record["after"]) and equal(values(record["after"]), expected), "runner_userns_after_drift")
        record["aa_status_after"] = runner.aa_status()
        record["status"] = "ready"
    except Exception as error:
        record.update(status="refused", reason=str(error) if isinstance(error, Refused) else type(error).__name__)
        raise
    finally:
        write_receipt(evidence, record)
    return record


def read_receipt(path, evidence, identity):
    require(path is not None, "runner_userns_receipt_required")
    path, evidence = safe_path(path), safe_path(evidence)
    require(path == evidence / "runner-userns.json", "runner_userns_receipt_path_refused")
    record = probe.strict_json(path.read_text())
    require(record.get("schema") == SCHEMA and record.get("runner") == identity
            and record.get("synthetic") is False and record.get("execution_allowed") is False
            and record.get("admission_allowed") is False and type(record.get("model_calls")) is int
            and record["model_calls"] == 0, "runner_userns_receipt_contract_refused")
    return record


def verify_for_auth(path, prepared, evidence, identity, *, runner=None):
    record = read_receipt(path, evidence, identity)
    require(not (evidence / "runner-userns-cleanup.json").exists(), "runner_userns_already_restored")
    runner = runner if runner is not None else Runner()
    validate_ready(record)
    proof = record.get("final_probe", {})
    require(proof.get("passed") is True and type(proof.get("returncode")) is int and proof["returncode"] == 0
            and equal(proof.get("proof"), PROOF), "runner_userns_probe_evidence_refused")
    require(selected_bwrap(prepared, runner) == record.get("bwrap"), "runner_userns_bwrap_changed")
    current = runner.sysctls()
    require(usable(current) and equal(values(current), values(record.get("after", {}))), "runner_userns_state_changed")
    if record["method"] == "b_job_scoped_sysctl":
        runner.check_sysctl_binary(record.get("sysctl_binary"))
    if record.get("profile", {}).get("attempted") is True:
        check_profile(record, evidence, identity)
        require(runner.profile_loaded(profile_name(identity)) is (record["method"] == "a_exact_bwrap_profile"),
                "runner_userns_profile_state_changed")
    probe.save_json(evidence / "runner-userns-use.json", {"schema": "ghcp-runner-userns-use-v1", "runner": identity,
        "preparation_sha256": probe.digest(path), "bwrap_sha256": record["bwrap"]["sha256"],
        "method": record["method"], "verified_before_auth": True, "execution_allowed": False})


def validate_ready(record):
    method = record.get("method")
    require(record.get("status") == "ready" and method in {
        "none_required", "a_exact_bwrap_profile", "b_job_scoped_sysctl"}, "runner_userns_not_ready")
    before, after = values(record.get("before", {})), values(record.get("after", {}))
    require(usable(record.get("before", {})), "runner_userns_before_refused")
    expected = {**before, RESTRICT: 0} if method == "b_job_scoped_sysctl" else before
    require(usable(record.get("after", {})) and equal(after, expected), "runner_userns_after_refused")
    baseline, profile = record.get("baseline", {}), record.get("profile", {})
    if method == "none_required":
        require(baseline.get("passed") is True and equal(baseline, record.get("final_probe"))
                and profile.get("attempted") is False and record.get("sysctl_attempted") is False,
                "runner_userns_unnecessary_mutation")
    else:
        require(before[RESTRICT] == 1 and baseline.get("passed") is False and profile.get("attempted") is True,
                "runner_userns_profile_order_refused")
        if method == "a_exact_bwrap_profile":
            require(profile.get("loaded") is True and profile.get("load", {}).get("returncode") == 0
                    and record.get("sysctl_attempted") is False
                    and record.get("profile_probe", {}).get("passed") is True
                    and equal(record.get("profile_probe"), record.get("final_probe")), "runner_userns_profile_proof_refused")
        else:
            load_code = profile.get("load", {}).get("returncode")
            require(type(load_code) is int and (load_code != 0 or record.get("profile_probe", {}).get("passed") is False)
                    and profile.get("loaded") is False and record.get("sysctl_attempted") is True
                    and record.get("sysctl_change", {}).get("returncode") == 0,
                    "runner_userns_fallback_order_refused")
            require(usable(record.get("after_sysctl_write", {}))
                    and equal(values(record["after_sysctl_write"]), expected), "runner_userns_sysctl_readback_failed")


def check_profile(record, evidence, identity):
    profile = record.get("profile", {})
    path = safe_path(evidence / "runner-userns.apparmor")
    require(profile.get("path") == str(path) and profile.get("name") == profile_name(identity)
            and profile.get("text") == profile_text(record["bwrap"]["path"], identity)
            and path.read_text() == profile["text"] and probe.digest(path) == profile.get("sha256"),
            "runner_userns_profile_changed")
    return path


def restore(evidence, identity, runner):
    record = read_receipt(evidence / "runner-userns.json", evidence, identity)
    result = {"schema": "ghcp-runner-userns-cleanup-v1", "runner": identity, "status": "restoring",
              "preparation_sha256": probe.digest(evidence / "runner-userns.json"), "execution_allowed": False,
              "restoration_measured": False}
    try:
        if record.get("profile", {}).get("attempted"):
            path = check_profile(record, evidence, identity)
            if runner.profile_loaded(profile_name(identity)):
                removed = runner.run(["sudo", "-n", "apparmor_parser", "--remove", str(path)])
                result["profile_remove"] = brief(removed)
                require(removed["returncode"] == 0 and not runner.profile_loaded(profile_name(identity)),
                        "runner_userns_cleanup_profile_failed")
        before = values(record["before"])
        if record.get("sysctl_attempted") is True:
            require(usable(record["before"]) and before[RESTRICT] == 1, "runner_userns_cleanup_original_refused")
            changed = runner.write_sysctl(record.get("sysctl_binary"), 1)
            result["sysctl_restore"] = brief(changed)
            require(changed["returncode"] == 0, "runner_userns_cleanup_sysctl_failed")
        result["after_restore"] = runner.sysctls()
        attempted = record.get("profile", {}).get("attempted") is True or record.get("sysctl_attempted") is True
        if not attempted and not measured(record["before"]):
            # Unknown == unknown is NOT a numeric restoration measurement.
            result["status"] = "not_required_no_mutation"
        else:
            require(measured(record["before"]) and measured(result["after_restore"])
                    and equal(values(result["after_restore"]), before), "runner_userns_cleanup_readback_failed")
            result.update(status="restored" if attempted else "unchanged_verified", restoration_measured=True)
    except Exception as error:
        result.update(status="refused", reason=str(error) if isinstance(error, Refused) else type(error).__name__)
        raise
    finally:
        probe.save_json(evidence / "runner-userns-cleanup.json", result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "restore"))
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        identity = prewarm.context()  # Never read credentials or act on NAS.
        require(not any(key in os.environ for key in ("COPILOT_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN")),
                "runner_userns_credential_environment_refused")
        runner = Runner()
        value = (prepare(args.prepared, args.evidence, identity, runner) if args.mode == "prepare"
                 else restore(args.evidence, identity, runner))
        print(json.dumps({"status": value["status"], "model_calls": 0}))
        return 0
    except Exception as error:
        print(json.dumps({"status": "runner_userns_refused",
                          "reason": str(error) if isinstance(error, Refused) else type(error).__name__, "model_calls": 0}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
