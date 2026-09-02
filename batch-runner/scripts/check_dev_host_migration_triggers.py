#!/usr/bin/env python3
"""Collect, in one command, the conditions that would justify a dev Azure VM.

The Xenology card decided *not* to build an Azure VM, and listed five trigger
conditions instead: build it when one of them reproduces. That decision is only
as good as somebody noticing a trigger, and until now nothing measured them. The
baseline in the card is a set of numbers a person read off this host by hand on
2026-09-01; it goes stale the moment the host changes, and nobody is watching.

This tool reads the host and reports each of the five conditions as one of:

    fired               measured here, and the condition holds
    not_fired           measured here, and it does not hold
    not_measurable_here this host cannot answer it, and here is what would

That third state is the point. A checker that answers "no trigger" to a question
it never asked is worse than no checker, because it converts silence into an
all-clear. Condition 2 needs a second machine to compare against and cannot be
answered from one host at all, so it is reported as unanswered every single run
rather than quietly counted as a pass.

It never creates a VM, never signs in to a cloud account, never calls a model
and never writes anything outside its own report. Every measurement is a read of
/proc, /sys, a `df`-equivalent, or one 0.2 s subprocess.

Usage:

    python scripts/check_dev_host_migration_triggers.py
    python scripts/check_dev_host_migration_triggers.py --json
    python scripts/check_dev_host_migration_triggers.py --out report.json

Exit status:

    0   nothing fired among the conditions this host can answer
    1   at least one condition fired -- read the report and decide
    2   the probe itself could not run

Exit 0 is deliberately *not* "no trigger exists". The unanswered conditions are
printed above the verdict, in both the human and the JSON output, so the two
readings cannot be confused.

Calibration
-----------

The default thresholds are pinned to the card's own recorded baseline. On
2026-09-01 the operator looked at 8 vCPU under load 5.34/3.43/2.10, ~21 GiB
available memory and ~199 GiB free disk and judged: not yet. Any threshold that
fires on those numbers would contradict a judgement that has already been made,
so `tests/test_the_dev_host_triggers_agree_with_the_card.py` asserts that the
card's baseline does not fire. A future edit that lowers a threshold past that
line fails a test that says why.

What it borrows rather than reimplements
----------------------------------------

The seccomp probe runs `core.agentic_python_launcher._install_filter` in a
subprocess and reads its stderr, which is exactly what
`test_generated_python_launcher_denies_exec_and_network` does to decide whether
to skip. Reimplementing the check would let the two drift, and then the tool
could report a capability the suite disagrees about. Reading a module does not
move the grader fingerprint; only editing one does, and this file edits nothing.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# Thresholds. See "Calibration" above before changing any of these.
# ---------------------------------------------------------------------------

# Condition 3 fires when the *fifteen minute* run-queue average is at or above
# the core count. The one-minute figure is not used: the card asks for
# saturation that is "지속적" (sustained), and a one-minute spike during a test
# run is the normal working state of this box, not a reason to move it.
DEFAULT_LOAD15_PER_CPU = 1.0

# Condition 4 fires on headroom this small that a test run can plausibly hit the
# wall. The card's baseline had ~21 GiB and ~199 GiB.
DEFAULT_MIN_AVAILABLE_MEMORY_GIB = 2.0
DEFAULT_MIN_FREE_DISK_GIB = 10.0

# Kernel floors, each the release that introduced the feature. These are facts
# about Linux, not preferences, which is why they are stated as versions rather
# than as a single "modern enough" number.
SECCOMP_TSYNC_SINCE = (3, 17)  # SECCOMP_FILTER_FLAG_TSYNC
USER_NAMESPACE_SYSCTL_SINCE = (4, 9)  # /proc/sys/user/max_user_namespaces
OOM_KILL_COUNTER_SINCE = (4, 13)  # the oom_kill line in /proc/vmstat
MEM_AVAILABLE_SINCE = (3, 14)  # MemAvailable in /proc/meminfo

# The Docker version the repository's own container work assumes. 20.10 reached
# end of life in December 2023; a host stuck below this floor cannot be given a
# current daemon without a kernel that supports one.
DOCKER_SERVER_FLOOR = (24, 0)

FIRED = "fired"
NOT_FIRED = "not_fired"
NOT_MEASURABLE = "not_measurable_here"

GIB = 1024.0 ** 3


# ---------------------------------------------------------------------------
# Facts
# ---------------------------------------------------------------------------


@dataclass
class HostFacts:
    """Everything read from the host, separated from every judgement about it.

    Gathering and evaluating are split so the rules can be tested on a machine
    that is nothing like the one they describe. The tests feed this dataclass
    directly: a Synology-like 3.10 host and an Azure-like 6.8 host both run in
    the same suite, on whichever of the two the suite happens to be running.

    Every field that can be unknown is either None or carries a sibling reason
    string. "Unknown" and "absent" are different answers and the report keeps
    them apart -- a kernel with no OOM counter has not told us the OOM killer
    stayed quiet, it has told us nothing.
    """

    kernel_release: str = ""
    kernel_version_tuple: tuple[int, ...] = ()
    os_pretty_name: str | None = None
    machine: str = ""

    cpu_count: int | None = None
    load1: float | None = None
    load5: float | None = None
    load15: float | None = None

    mem_total_bytes: int | None = None
    mem_available_bytes: int | None = None
    mem_available_is_estimated: bool = False

    root_free_bytes: int | None = None
    tmpdir_path: str | None = None
    tmpdir_free_bytes: int | None = None

    seccomp_tsync_available: bool | None = None
    seccomp_probe_detail: str | None = None

    cgroup_version: int | None = None
    user_namespaces_max: int | None = None
    user_namespace_sysctl_present: bool | None = None
    overlayfs_available: bool | None = None

    docker_client_present: bool = False
    docker_server_version: str | None = None
    docker_server_version_tuple: tuple[int, ...] = ()
    docker_detail: str | None = None

    oom_kill_count: int | None = None
    oom_counter_present: bool | None = None

    read_errors: list[str] = field(default_factory=list)


def _parse_version(text: str) -> tuple[int, ...]:
    """Take the leading dotted integers off a version string.

    '3.10.102' and '20.10.3' both parse; so does '6.8.0-51-generic', which stops
    at the dash. A component that is not an integer ends the tuple rather than
    raising, because a version this tool cannot parse must not stop it from
    reporting the eight measurements that did work.
    """
    parts: list[int] = []
    for chunk in text.strip().split("."):
        digits = ""
        for character in chunk:
            if character.isdigit():
                digits += character
            else:
                break
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts)


def _read_text(path: str) -> str | None:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def probe_seccomp_tsync(timeout_s: float = 30.0) -> tuple[bool | None, str]:
    """Ask the repository's own filter installer whether TSYNC works here.

    Returns (available, detail). None means the probe could not reach a verdict
    -- libseccomp missing, the module unimportable, the subprocess timing out --
    which is reported as unknown rather than as a failure, because "we could not
    check" and "the kernel cannot do it" call for different responses.

    The marker string is the one `_install_filter` raises and the one the
    security test greps for. If that message ever changes, this probe returns
    unknown instead of silently reporting success, and the detail says so.
    """
    harness = (
        "from core.agentic_python_launcher import _install_filter;"
        "_install_filter();"
        "print('tsync_ok')"
    )
    try:
        result = subprocess.run(
            [sys.executable, "-c", harness],
            capture_output=True,
            timeout=timeout_s,
            cwd=str(BATCH_RUNNER_ROOT),
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return None, f"probe could not run: {type(exc).__name__}: {exc}"

    stdout = result.stdout.decode("utf-8", errors="replace")
    stderr = result.stderr.decode("utf-8", errors="replace")

    if result.returncode == 0 and stdout.strip() == "tsync_ok":
        return True, "the launcher installed its filter with TSYNC"
    if "seccomp TSYNC unavailable" in stderr:
        return False, (
            "core.agentic_python_launcher raised 'seccomp TSYNC unavailable'; "
            "this is the same condition test_generated_python_launcher_denies_"
            "exec_and_network skips on"
        )
    tail = stderr.strip().splitlines()
    detail = tail[-1] if tail else f"exit {result.returncode} with no output"
    return None, f"probe reached no verdict: {detail}"


def gather_host_facts(*, run_seccomp_probe: bool = True) -> HostFacts:
    """Read the host. Judges nothing; every threshold lives in evaluate()."""
    facts = HostFacts()

    facts.kernel_release = platform.release()
    facts.kernel_version_tuple = _parse_version(facts.kernel_release)
    facts.machine = platform.machine()

    os_release = _read_text("/etc/os-release")
    if os_release:
        for line in os_release.splitlines():
            if line.startswith("PRETTY_NAME="):
                facts.os_pretty_name = line.split("=", 1)[1].strip().strip('"')
                break

    facts.cpu_count = os.cpu_count()

    loadavg = _read_text("/proc/loadavg")
    if loadavg:
        try:
            one, five, fifteen = loadavg.split()[:3]
            facts.load1, facts.load5, facts.load15 = (
                float(one), float(five), float(fifteen),
            )
        except (ValueError, IndexError):
            facts.read_errors.append("/proc/loadavg did not parse")
    else:
        facts.read_errors.append("/proc/loadavg is unreadable")

    meminfo = _read_text("/proc/meminfo")
    if meminfo:
        values: dict[str, int] = {}
        for line in meminfo.splitlines():
            name, _, rest = line.partition(":")
            number = rest.strip().split(" ")[0]
            if number.isdigit():
                values[name] = int(number) * 1024
        facts.mem_total_bytes = values.get("MemTotal")
        if "MemAvailable" in values:
            facts.mem_available_bytes = values["MemAvailable"]
        elif "MemFree" in values:
            # MemAvailable arrived in 3.14. Below that the honest substitute is
            # free plus reclaimable, and it is an over-estimate: not all of the
            # page cache can actually be handed back. The flag travels with the
            # number so the report can say which one it is showing.
            facts.mem_available_bytes = (
                values.get("MemFree", 0)
                + values.get("Cached", 0)
                + values.get("Buffers", 0)
            )
            facts.mem_available_is_estimated = True
    else:
        facts.read_errors.append("/proc/meminfo is unreadable")

    try:
        facts.root_free_bytes = shutil.disk_usage("/").free
    except OSError as exc:
        facts.read_errors.append(f"disk usage of / failed: {exc}")

    tmpdir = os.environ.get("TMPDIR") or "/tmp"
    facts.tmpdir_path = tmpdir
    try:
        facts.tmpdir_free_bytes = shutil.disk_usage(tmpdir).free
    except OSError as exc:
        facts.read_errors.append(f"disk usage of {tmpdir} failed: {exc}")

    if run_seccomp_probe:
        available, detail = probe_seccomp_tsync()
        facts.seccomp_tsync_available = available
        facts.seccomp_probe_detail = detail

    # cgroup v2 mounts a filesystem whose magic differs from the v1 tmpfs, so
    # the mount type is the reliable read; the controller list in
    # /proc/self/cgroup looks similar enough between the two to mislead.
    try:
        cgroup_root = Path("/sys/fs/cgroup")
        if cgroup_root.is_dir():
            probe = subprocess.run(
                ["stat", "-fc", "%T", str(cgroup_root)],
                capture_output=True, timeout=10, check=False,
            )
            kind = probe.stdout.decode("utf-8", errors="replace").strip()
            if kind == "cgroup2fs":
                facts.cgroup_version = 2
            elif kind:
                facts.cgroup_version = 1
    except (OSError, subprocess.SubprocessError) as exc:
        facts.read_errors.append(f"cgroup version read failed: {exc}")

    userns = _read_text("/proc/sys/user/max_user_namespaces")
    if userns is None:
        facts.user_namespace_sysctl_present = False
        facts.user_namespaces_max = None
    else:
        facts.user_namespace_sysctl_present = True
        try:
            facts.user_namespaces_max = int(userns.strip())
        except ValueError:
            facts.read_errors.append("max_user_namespaces did not parse")

    filesystems = _read_text("/proc/filesystems")
    if filesystems is not None:
        names = {line.split()[-1] for line in filesystems.splitlines() if line.split()}
        facts.overlayfs_available = "overlay" in names
    else:
        facts.read_errors.append("/proc/filesystems is unreadable")

    vmstat = _read_text("/proc/vmstat")
    if vmstat is not None:
        found = False
        for line in vmstat.splitlines():
            if line.startswith("oom_kill "):
                found = True
                try:
                    facts.oom_kill_count = int(line.split()[1])
                except (ValueError, IndexError):
                    facts.read_errors.append("oom_kill did not parse")
                break
        facts.oom_counter_present = found

    facts.docker_client_present = shutil.which("docker") is not None
    if facts.docker_client_present:
        try:
            probe = subprocess.run(
                ["docker", "version", "--format", "{{.Server.Version}}"],
                capture_output=True, timeout=30, check=False,
            )
            text = probe.stdout.decode("utf-8", errors="replace").strip()
            if probe.returncode == 0 and text:
                facts.docker_server_version = text
                facts.docker_server_version_tuple = _parse_version(text)
            else:
                facts.docker_detail = (
                    probe.stderr.decode("utf-8", errors="replace").strip()
                    or f"docker version exited {probe.returncode}"
                )
        except (OSError, subprocess.SubprocessError) as exc:
            facts.docker_detail = f"{type(exc).__name__}: {exc}"

    return facts


# ---------------------------------------------------------------------------
# Judgement
# ---------------------------------------------------------------------------


@dataclass
class Thresholds:
    load15_per_cpu: float = DEFAULT_LOAD15_PER_CPU
    min_available_memory_gib: float = DEFAULT_MIN_AVAILABLE_MEMORY_GIB
    min_free_disk_gib: float = DEFAULT_MIN_FREE_DISK_GIB


def _gib(value: int | None) -> float | None:
    return None if value is None else round(value / GIB, 2)


def _condition_1(facts: HostFacts) -> dict[str, Any]:
    """Kernel features whose absence makes the suite fail or skip."""
    evidence: list[dict[str, Any]] = []
    blocking: list[str] = []
    unknown: list[str] = []

    if facts.seccomp_tsync_available is False:
        blocking.append("seccomp TSYNC")
        evidence.append({
            "feature": "seccomp TSYNC",
            "state": "absent",
            "since_kernel": ".".join(str(n) for n in SECCOMP_TSYNC_SINCE),
            "detail": facts.seccomp_probe_detail,
            "test_that_skips":
                "tests/test_agentic_sandbox_security.py::"
                "test_generated_python_launcher_denies_exec_and_network",
        })
    elif facts.seccomp_tsync_available is True:
        evidence.append({"feature": "seccomp TSYNC", "state": "present"})
    else:
        unknown.append("seccomp TSYNC")
        evidence.append({
            "feature": "seccomp TSYNC",
            "state": "unknown",
            "detail": facts.seccomp_probe_detail,
        })

    if facts.cgroup_version == 1:
        blocking.append("cgroup v2")
        evidence.append({"feature": "cgroup", "state": "v1 only"})
    elif facts.cgroup_version == 2:
        evidence.append({"feature": "cgroup", "state": "v2"})
    else:
        unknown.append("cgroup version")

    if facts.user_namespace_sysctl_present is False:
        blocking.append("user namespaces")
        evidence.append({
            "feature": "user namespaces",
            "state": "no /proc/sys/user/max_user_namespaces",
            "since_kernel": ".".join(str(n) for n in USER_NAMESPACE_SYSCTL_SINCE),
        })
    elif facts.user_namespaces_max == 0:
        blocking.append("user namespaces")
        evidence.append({"feature": "user namespaces", "state": "disabled (max is 0)"})
    elif facts.user_namespaces_max:
        evidence.append({
            "feature": "user namespaces",
            "state": f"enabled (max {facts.user_namespaces_max})",
        })

    if facts.overlayfs_available is False:
        blocking.append("overlayfs")
        evidence.append({"feature": "overlayfs", "state": "absent from /proc/filesystems"})
    elif facts.overlayfs_available is True:
        evidence.append({"feature": "overlayfs", "state": "present"})
    else:
        unknown.append("overlayfs")

    if facts.docker_server_version_tuple:
        current = facts.docker_server_version_tuple
        floor_text = ".".join(str(n) for n in DOCKER_SERVER_FLOOR)
        if current < DOCKER_SERVER_FLOOR:
            blocking.append("current Docker")
            evidence.append({
                "feature": "docker server",
                "state": f"{facts.docker_server_version} is below {floor_text}",
            })
        else:
            evidence.append({
                "feature": "docker server", "state": facts.docker_server_version,
            })
    else:
        unknown.append("docker server version")
        evidence.append({
            "feature": "docker server",
            "state": "unknown",
            "detail": facts.docker_detail or "no docker client on PATH",
        })

    if blocking:
        status = FIRED
        summary = (
            "the kernel is missing " + ", ".join(blocking)
            + "; the suite skips rather than covering these paths"
        )
    elif unknown and not evidence:
        status = NOT_MEASURABLE
        summary = "no kernel feature could be read on this host"
    else:
        status = NOT_FIRED
        summary = "every kernel feature the suite depends on is present"

    return {
        "id": 1,
        "title": "kernel features make tests fail or skip",
        "title_ko": "커널 때문에 시험이 실패하거나 건너뛴다",
        "status": status,
        "summary": summary,
        "missing_features": blocking,
        "unknown_features": unknown,
        "evidence": evidence,
    }


def _condition_2() -> dict[str, Any]:
    """CI and local disagree because of the host kernel.

    Permanently unanswerable from one machine, and saying so every run is the
    whole reason this state exists. Comparing to a remembered CI result would be
    comparing two commits, not two hosts.
    """
    return {
        "id": 2,
        "title": "CI and local results differ because of the host kernel",
        "title_ko": "호스트 커널 때문에 CI와 로컬 결과가 다르다",
        "status": NOT_MEASURABLE,
        "summary": "one host cannot compare itself with another",
        "why": (
            "this asks whether two machines disagree; a single host has nothing "
            "to disagree with, and a remembered CI result would compare two "
            "commits rather than two kernels"
        ),
        "what_would_answer_it": (
            "two pytest reports for the same commit -- one from this host, one "
            "from a CI run -- diffed by test id, with any difference then "
            "checked against condition 1's feature list to tell a kernel cause "
            "from a dependency one"
        ),
        "evidence": [],
    }


def _condition_3(facts: HostFacts, thresholds: Thresholds) -> dict[str, Any]:
    """Sustained CPU saturation.

    Only half of this condition is a measurement. The card also asks whether the
    wait is "작업 흐름을 막는다" -- blocking the work -- and no reading of
    /proc/loadavg answers that. The measurable half decides the status; the
    other half is handed back to the operator by name.
    """
    if facts.load15 is None or not facts.cpu_count:
        return {
            "id": 3,
            "title": "CPU is saturated for long enough to block the work",
            "title_ko": "CPU가 지속적으로 포화되어 작업을 막는다",
            "status": NOT_MEASURABLE,
            "summary": "load average or cpu count is unreadable on this host",
            "evidence": [],
        }

    ratio = facts.load15 / facts.cpu_count
    fired = ratio >= thresholds.load15_per_cpu
    return {
        "id": 3,
        "title": "CPU is saturated for long enough to block the work",
        "title_ko": "CPU가 지속적으로 포화되어 작업을 막는다",
        "status": FIRED if fired else NOT_FIRED,
        "summary": (
            f"fifteen-minute run queue is {ratio:.2f} per core "
            f"(threshold {thresholds.load15_per_cpu:.2f})"
        ),
        "operator_judgement_still_required": fired,
        "unmeasured_half": (
            "whether the wait actually blocks the work is a judgement, not a "
            "reading; a saturated box that nobody is waiting on is not a "
            "reason to migrate"
        ),
        "evidence": [{
            "cpu_count": facts.cpu_count,
            "load1": facts.load1,
            "load5": facts.load5,
            "load15": facts.load15,
            "load15_per_cpu": round(ratio, 3),
        }],
    }


def _condition_4(facts: HostFacts, thresholds: Thresholds) -> dict[str, Any]:
    """Memory or temp-disk exhaustion.

    Two different questions live here and the report keeps them apart: how much
    headroom is left right now, and whether the OOM killer has already fired.
    The second is the one the card actually asks about ("테스트가 종료되거나"),
    and on a kernel with no oom_kill counter it cannot be answered at all.
    """
    evidence: list[dict[str, Any]] = []
    reasons: list[str] = []
    unanswered: list[str] = []

    available_gib = _gib(facts.mem_available_bytes)
    if available_gib is not None:
        evidence.append({
            "measure": "available memory (GiB)",
            "value": available_gib,
            "estimated": facts.mem_available_is_estimated,
            "note": (
                "MemAvailable is absent below kernel "
                + ".".join(str(n) for n in MEM_AVAILABLE_SINCE)
                + "; this is free+cached+buffers, which over-states what is "
                  "really reclaimable"
            ) if facts.mem_available_is_estimated else None,
        })
        if available_gib < thresholds.min_available_memory_gib:
            reasons.append(f"available memory {available_gib} GiB")
    else:
        unanswered.append("available memory")

    for label, value in (
        ("root filesystem", _gib(facts.root_free_bytes)),
        (f"tmpdir ({facts.tmpdir_path})", _gib(facts.tmpdir_free_bytes)),
    ):
        if value is None:
            unanswered.append(label)
            continue
        evidence.append({"measure": f"free space on {label} (GiB)", "value": value})
        if value < thresholds.min_free_disk_gib:
            reasons.append(f"{label} {value} GiB free")

    if facts.oom_counter_present:
        evidence.append({"measure": "oom_kill events since boot", "value": facts.oom_kill_count})
        if facts.oom_kill_count:
            reasons.append(f"the OOM killer has fired {facts.oom_kill_count} times")
    else:
        unanswered.append("whether the OOM killer has fired")
        evidence.append({
            "measure": "oom_kill events since boot",
            "value": None,
            "note": (
                "/proc/vmstat has no oom_kill counter below kernel "
                + ".".join(str(n) for n in OOM_KILL_COUNTER_SINCE)
                + "; headroom being fine now is not evidence that nothing was "
                  "killed earlier"
            ),
        })

    if reasons:
        status, summary = FIRED, "; ".join(reasons)
    elif len(unanswered) >= 3:
        status, summary = NOT_MEASURABLE, "nothing about memory or disk could be read"
    else:
        status, summary = NOT_FIRED, "memory and disk headroom are above the thresholds"

    return {
        "id": 4,
        "title": "memory or temp disk runs out and kills a run",
        "title_ko": "메모리나 임시 디스크가 부족해 실행이 죽는다",
        "status": status,
        "summary": summary,
        "unanswered_parts": unanswered,
        "evidence": evidence,
    }


def _condition_5(facts: HostFacts) -> dict[str, Any]:
    """Security verification that only reproduces on a modern kernel.

    Read as a question about this repository rather than about a future wish:
    does it already contain container-security verification that this host
    cannot execute? On a host without TSYNC the answer is yes and it has a name.
    """
    evidence: list[dict[str, Any]] = []
    unrunnable: list[str] = []

    if facts.seccomp_tsync_available is False:
        unrunnable.append("the in-process seccomp filter the agentic launcher installs")
        evidence.append({
            "verification":
                "tests/test_agentic_sandbox_security.py::"
                "test_generated_python_launcher_denies_exec_and_network",
            "state": "skipped on this host",
            "reason": "host runtime does not expose seccomp TSYNC",
            "consequence": (
                "the launcher's deny-exec and deny-socket behaviour is never "
                "actually exercised here, so a regression in it would pass"
            ),
        })
    elif facts.seccomp_tsync_available is True:
        evidence.append({
            "verification": "in-process seccomp filter",
            "state": "runs on this host",
        })
    else:
        return {
            "id": 5,
            "title": "security verification needs a modern kernel",
            "title_ko": "보안 검증에 최신 커널이 필요하다",
            "status": NOT_MEASURABLE,
            "summary": "the seccomp probe reached no verdict",
            "detail": facts.seccomp_probe_detail,
            "evidence": [],
        }

    if facts.user_namespace_sysctl_present is False:
        unrunnable.append("rootless and user-namespace container checks")
        evidence.append({
            "verification": "rootless / userns container isolation",
            "state": "cannot run",
            "reason": "this kernel has no user-namespace sysctl",
        })

    return {
        "id": 5,
        "title": "security verification needs a modern kernel",
        "title_ko": "보안 검증에 최신 커널이 필요하다",
        "status": FIRED if unrunnable else NOT_FIRED,
        "summary": (
            "this repository verifies " + " and ".join(unrunnable)
            + "; this host cannot run that verification"
        ) if unrunnable else (
            "every container-security check in this repository can run here"
        ),
        "evidence": evidence,
    }


def evaluate(facts: HostFacts, thresholds: Thresholds | None = None) -> dict[str, Any]:
    """Turn facts into the five condition verdicts. Pure; reads no host state."""
    thresholds = thresholds or Thresholds()
    conditions = [
        _condition_1(facts),
        _condition_2(),
        _condition_3(facts, thresholds),
        _condition_4(facts, thresholds),
        _condition_5(facts),
    ]

    fired = [c["id"] for c in conditions if c["status"] == FIRED]
    unanswered = [c["id"] for c in conditions if c["status"] == NOT_MEASURABLE]

    return {
        "what_this_is": (
            "the five VM trigger conditions from the Xenology card, measured. "
            "A condition this host cannot answer is reported as unanswered, "
            "never as a pass."
        ),
        "host": {
            "kernel": facts.kernel_release,
            "os": facts.os_pretty_name,
            "machine": facts.machine,
            "cpu_count": facts.cpu_count,
        },
        "thresholds": asdict(thresholds),
        "conditions": conditions,
        "fired": fired,
        "not_measurable_here": unanswered,
        "verdict": "migrate" if fired else "stay",
        "verdict_means": (
            f"conditions {fired} fired; the card says build the VM when one "
            f"reproduces" if fired else
            f"nothing fired among the {5 - len(unanswered)} conditions this "
            f"host can answer. Conditions {unanswered} were not answered and "
            f"are not evidence of anything"
        ),
        "read_errors": facts.read_errors,
    }


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def render_text(report: dict[str, Any]) -> str:
    lines: list[str] = []
    host = report["host"]
    lines.append("Dev-host migration triggers")
    lines.append("=" * 60)
    lines.append(
        f"host: {host['os'] or 'unknown os'} on kernel {host['kernel']}, "
        f"{host['cpu_count']} cpu"
    )
    lines.append("")

    # The unanswered list goes above the verdict on purpose: a reader who stops
    # after the first screen must not come away thinking everything was checked.
    unanswered = report["not_measurable_here"]
    if unanswered:
        lines.append(f"NOT ANSWERED HERE: conditions {unanswered}")
        for condition in report["conditions"]:
            if condition["status"] != NOT_MEASURABLE:
                continue
            lines.append(f"  [{condition['id']}] {condition['title']}")
            lines.append(f"      {condition['summary']}")
            if condition.get("what_would_answer_it"):
                lines.append(f"      would need: {condition['what_would_answer_it']}")
        lines.append("")

    marks = {FIRED: "FIRED   ", NOT_FIRED: "ok      ", NOT_MEASURABLE: "unknown "}
    for condition in report["conditions"]:
        lines.append(
            f"{marks[condition['status']]} [{condition['id']}] {condition['title']}"
        )
        lines.append(f"           {condition['summary']}")
        for item in condition["evidence"]:
            rendered = ", ".join(
                f"{key}={value}" for key, value in item.items() if value is not None
            )
            lines.append(f"           - {rendered}")
        if condition.get("unmeasured_half") and condition["status"] == FIRED:
            lines.append(f"           ! {condition['unmeasured_half']}")
        lines.append("")

    lines.append("-" * 60)
    lines.append(f"verdict: {report['verdict']}")
    lines.append(f"         {report['verdict_means']}")
    if report["read_errors"]:
        lines.append("")
        lines.append("read errors:")
        for error in report["read_errors"]:
            lines.append(f"  - {error}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Measure the five conditions the Xenology card gates a dev Azure VM "
            "on. Reads the host only; creates nothing and spends nothing."
        )
    )
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    parser.add_argument("--out", type=Path, default=None, help="also write JSON here")
    parser.add_argument(
        "--skip-seccomp-probe",
        action="store_true",
        help=(
            "do not run the launcher's filter in a subprocess; conditions 1 and "
            "5 then report the seccomp part as unknown rather than as passing"
        ),
    )
    parser.add_argument("--load15-per-cpu", type=float, default=DEFAULT_LOAD15_PER_CPU)
    parser.add_argument(
        "--min-available-memory-gib", type=float,
        default=DEFAULT_MIN_AVAILABLE_MEMORY_GIB,
    )
    parser.add_argument(
        "--min-free-disk-gib", type=float, default=DEFAULT_MIN_FREE_DISK_GIB,
    )
    args = parser.parse_args(argv)

    try:
        facts = gather_host_facts(run_seccomp_probe=not args.skip_seccomp_probe)
    except Exception as exc:  # noqa: BLE001 - the probe must report, not crash
        print(f"could not read this host: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    report = evaluate(facts, Thresholds(
        load15_per_cpu=args.load15_per_cpu,
        min_available_memory_gib=args.min_available_memory_gib,
        min_free_disk_gib=args.min_free_disk_gib,
    ))

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(json.dumps(report, indent=2) if args.json else render_text(report))
    return 1 if report["fired"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
