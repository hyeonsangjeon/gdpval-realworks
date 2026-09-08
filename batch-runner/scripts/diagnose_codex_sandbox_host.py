#!/usr/bin/env python3
"""Say whether this host can run Codex's sandbox, and if not, name which wall.

`tests/test_codex_runtime_end_to_end.py` drives the pinned Codex runtime end to
end, and two of its assertions need the agent to *execute* a command. Those two
skip wherever the sandbox will not start. Skipping is right -- a machine that
cannot sandbox is a property of the machine, not a regression -- but a skip is
also silent, and "every `bwrap:` line means skip" would hide a real break behind
a machine problem. Worse, it makes every host look equally unready, when in fact
the hosts fail for reasons that are not equally fixable.

So this tool answers one question, out loud:

    can this host run a command under the same sandbox Codex would use?

and when the answer is no, it says which of the walls below it hit. The walls
are different problems with different fixes, and lumping them together as "no
sandbox here" is what made the last round of this work wrong.

The walls
---------

``kernel_lacks_user_namespaces``
    ``CONFIG_USER_NS`` is not in the kernel at all -- ``/proc/sys/user/`` does
    not exist. Nothing installable fixes it. This is the Xenology NAS: Linux
    3.10.102, where user namespaces landed as a sysctl only in 4.9.

``user_namespaces_disabled_by_sysctl``
    The kernel has them and an administrator turned them off
    (``user.max_user_namespaces=0``, or Debian's
    ``kernel.unprivileged_userns_clone=0``). One sysctl fixes it -- on a host
    whose owner agrees, which is not something this tool decides.

``user_namespaces_restricted_by_security_policy``
    The namespace is created and then the capabilities inside it are stripped,
    so the sandbox gets a namespace it cannot configure. Ubuntu 24.04 ships
    exactly this as ``kernel.apparmor_restrict_unprivileged_userns=1``. The fix
    is a profile that grants the one binary what it needs -- **not** flipping
    the sysctl, which turns the restriction off for everything on the host.

``capability_denied_inside_namespace``
    Same symptom, no LSM knob found to explain it: a container runtime's seccomp
    or capability set is the usual cause. Kept separate from the case above
    because "AppArmor said no" and "the container we are inside said no" need
    different conversations.

``sandbox_binary_missing``
    No ``bwrap`` on PATH and none bundled with the pinned Codex build.

``unclassified_sandbox_failure``
    bwrap refused for a reason this tool has no name for. Deliberately not
    folded into any of the above: an unnamed failure is a thing to go read, and
    calling it "restricted by policy" on a guess would be inventing evidence.

``ready``
    A command actually ran inside the sandbox. Only this one is readiness.

Why bubblewrap and not Landlock
-------------------------------

The pinned build carries two Linux backends. Read out of the binary itself:
``features.use_legacy_landlock`` is described as *"the legacy Linux sandbox
behavior"*, and the helper's own text says *"when not set, the helper uses the
default bubblewrap pipeline"*. Landlock also refuses outright when a permission
profile needs direct runtime enforcement.

So bubblewrap is the configuration a real run uses, and it is the one this tool
measures. The Landlock probe is still run and reported, because "the deprecated
backend would have worked here" is a useful thing to know about a host -- but it
is reported as an observation, never as readiness. Passing the suite by opting
into a deprecated backend would buy a green test about a sandbox no run uses,
which is the same trade this file exists to refuse.

Usage:

    python scripts/diagnose_codex_sandbox_host.py
    python scripts/diagnose_codex_sandbox_host.py --json
    python scripts/diagnose_codex_sandbox_host.py --out sandbox-host.json

Exit status:

    0   ready -- a command ran inside the sandbox
    1   not ready, and the wall is named in the report
    2   the probe itself could not run

It signs in to nothing, calls no model, writes nothing outside its own report,
and changes no host setting. Every probe is a read of /proc or one short
subprocess with a timeout.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]

#: Long enough for a namespace to be set up and `/bin/true` to run; short
#: enough that a wedged probe cannot hang a CI job. bwrap either fails in
#: milliseconds or succeeds in milliseconds.
PROBE_TIMEOUT_SECONDS = 20.0

# --- the walls, as literals other code can import ---------------------------

READY = "ready"
KERNEL_LACKS_USER_NAMESPACES = "kernel_lacks_user_namespaces"
USER_NAMESPACES_DISABLED_BY_SYSCTL = "user_namespaces_disabled_by_sysctl"
USER_NAMESPACES_RESTRICTED_BY_SECURITY_POLICY = (
    "user_namespaces_restricted_by_security_policy"
)
CAPABILITY_DENIED_INSIDE_NAMESPACE = "capability_denied_inside_namespace"
SANDBOX_BINARY_MISSING = "sandbox_binary_missing"
UNCLASSIFIED_SANDBOX_FAILURE = "unclassified_sandbox_failure"

#: Every value :func:`classify` can return. Ordered worst-understood last.
ALL_READINESS_VALUES: tuple[str, ...] = (
    READY,
    KERNEL_LACKS_USER_NAMESPACES,
    USER_NAMESPACES_DISABLED_BY_SYSCTL,
    USER_NAMESPACES_RESTRICTED_BY_SECURITY_POLICY,
    CAPABILITY_DENIED_INSIDE_NAMESPACE,
    SANDBOX_BINARY_MISSING,
    UNCLASSIFIED_SANDBOX_FAILURE,
)

#: Plain-language line printed for each wall. Keep these describing the *host*,
#: not the repository -- somebody reads this on a machine they are deciding
#: whether to keep.
WALL_EXPLANATIONS: dict[str, str] = {
    READY: "a command ran inside the sandbox; this host can host the run place",
    KERNEL_LACKS_USER_NAMESPACES: (
        "this kernel has no user namespaces at all (no /proc/sys/user), so no "
        "package or setting on it can make bubblewrap work"
    ),
    USER_NAMESPACES_DISABLED_BY_SYSCTL: (
        "the kernel supports user namespaces and they are switched off; the "
        "host's owner can switch them on"
    ),
    USER_NAMESPACES_RESTRICTED_BY_SECURITY_POLICY: (
        "a namespace is created and then stripped of the capabilities the "
        "sandbox needs inside it; grant the one binary a profile rather than "
        "turning the restriction off host-wide"
    ),
    CAPABILITY_DENIED_INSIDE_NAMESPACE: (
        "something denies the capability inside the namespace and no LSM knob "
        "explains it; a container runtime's seccomp or capability set is the "
        "usual cause"
    ),
    SANDBOX_BINARY_MISSING: (
        "no bwrap on PATH and none bundled with the pinned Codex build"
    ),
    UNCLASSIFIED_SANDBOX_FAILURE: (
        "bubblewrap refused for a reason this tool has no name for; read the "
        "recorded stderr rather than trusting a guess"
    ),
}


@dataclass
class Probe:
    """One measurement, kept whole so the report can be re-read later."""

    name: str
    ran: bool
    ok: bool | None = None
    detail: str = ""
    value: Any = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class HostReport:
    readiness: str
    explanation: str
    kernel: str
    machine: str
    in_container: bool | None
    container_evidence: str
    probes: list[dict[str, Any]] = field(default_factory=list)
    landlock_note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _read_text(path: str) -> str | None:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None


def _run(argv: list[str]) -> tuple[int | None, str]:
    """Run a probe command. ``None`` status means it could not be started."""
    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=PROBE_TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError:
        return None, f"{argv[0]}: not found"
    except subprocess.TimeoutExpired:
        return None, f"{argv[0]}: still running after {PROBE_TIMEOUT_SECONDS}s"
    except OSError as exc:  # pragma: no cover - depends on the host
        return None, f"{argv[0]}: {exc}"
    output = (completed.stderr or "") + (completed.stdout or "")
    return completed.returncode, output.strip()


def find_bwrap() -> str | None:
    """The bwrap Codex would use: PATH first, then the build's bundled copy.

    Mirrors the order in the pinned binary, whose failure text is *"no system
    bwrap was found on PATH and no bundled codex-resources/bwrap binary"*.
    """
    on_path = shutil.which("bwrap")
    if on_path:
        return on_path
    for parent in _codex_resource_roots():
        candidate = parent / "codex-resources" / "bwrap"
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def _codex_resource_roots() -> list[Path]:
    """Where a bundled bwrap could live, without importing the SDK.

    Importing ``codex_cli_bin`` would make this tool unusable on a host that
    has not installed the runtime yet, which is exactly the host most likely to
    be running a readiness check.
    """
    roots: list[Path] = []
    for entry in sys.path:
        if not entry:
            continue
        candidate = Path(entry) / "codex_cli_bin" / "bin"
        if candidate.is_dir():
            roots.append(candidate)
    return roots


def detect_container() -> tuple[bool | None, str]:
    """Whether we are inside a container, and what said so.

    ``None`` when nothing points either way. Reported rather than inferred: a
    container is not itself a problem, it is context for a denied capability.
    """
    if Path("/.dockerenv").exists():
        return True, "/.dockerenv exists"
    cgroup = _read_text("/proc/1/cgroup") or ""
    for marker in ("docker", "kubepods", "containerd", "lxc", "podman"):
        if marker in cgroup:
            return True, f"/proc/1/cgroup mentions {marker}"
    sched = _read_text("/proc/1/sched") or ""
    first_line = sched.splitlines()[0] if sched else ""
    if first_line and not first_line.startswith(("systemd", "init")):
        return None, f"pid 1 is {first_line.split()[0]!r}, which is inconclusive"
    return False, "no container marker found"


def probe_user_namespace_support() -> list[Probe]:
    """Read the kernel's own answers before running anything."""
    probes: list[Probe] = []

    max_ns = _read_text("/proc/sys/user/max_user_namespaces")
    probes.append(
        Probe(
            name="user.max_user_namespaces",
            ran=True,
            ok=max_ns is not None and max_ns.isdigit() and int(max_ns) > 0,
            detail=(
                "absent: the kernel was built without CONFIG_USER_NS"
                if max_ns is None
                else f"= {max_ns}"
            ),
            value=max_ns,
        )
    )

    clone = _read_text("/proc/sys/kernel/unprivileged_userns_clone")
    probes.append(
        Probe(
            name="kernel.unprivileged_userns_clone",
            ran=clone is not None,
            ok=None if clone is None else clone == "1",
            detail=(
                "absent (normal outside Debian-family kernels)"
                if clone is None
                else f"= {clone}"
            ),
            value=clone,
        )
    )

    apparmor = _read_text(
        "/proc/sys/kernel/apparmor_restrict_unprivileged_userns"
    )
    probes.append(
        Probe(
            name="kernel.apparmor_restrict_unprivileged_userns",
            ran=apparmor is not None,
            # ok=True means "not restricting". 1 is Ubuntu 24.04's default.
            ok=None if apparmor is None else apparmor == "0",
            detail=(
                "absent (no AppArmor userns restriction on this kernel)"
                if apparmor is None
                else f"= {apparmor}"
                + (" -- unprivileged user namespaces are restricted"
                   if apparmor == "1" else "")
            ),
            value=apparmor,
        )
    )
    return probes


def probe_unshare() -> Probe:
    """Can *anything* here make a user namespace, ignoring bwrap entirely?

    Separates "the namespace is refused" from "the namespace is granted and
    then hollowed out", which are the two walls that look alike from the
    outside and need opposite fixes.
    """
    status, output = _run(["unshare", "--user", "--map-root-user", "true"])
    if status is None:
        return Probe(
            name="unshare --user --map-root-user",
            ran=False,
            detail=output,
        )
    return Probe(
        name="unshare --user --map-root-user",
        ran=True,
        ok=status == 0,
        detail=output or ("succeeded" if status == 0 else f"exit {status}"),
        value=status,
    )


def probe_bwrap(bwrap: str) -> Probe:
    """Run a command the way Codex's default pipeline would.

    The flags are the ones the pinned binary's own support check uses --
    ``--unshare-user --unshare-net --ro-bind / /`` then a trivial command --
    so a pass here is a pass for the configuration a run would actually use,
    not for some easier sandbox invented to get a green light.
    """
    status, output = _run(
        [
            bwrap,
            "--unshare-user",
            "--unshare-net",
            "--ro-bind",
            "/",
            "/",
            "/bin/true",
        ]
    )
    if status is None:
        return Probe(name="bwrap --unshare-user --unshare-net", ran=False, detail=output)
    return Probe(
        name="bwrap --unshare-user --unshare-net",
        ran=True,
        ok=status == 0,
        detail=output or ("succeeded" if status == 0 else f"exit {status}"),
        value=status,
    )


def probe_bwrap_without_net(bwrap: str) -> Probe:
    """The same sandbox minus the network namespace.

    Not a fallback and never readiness -- a run that does not unshare the
    network is not the run place anyone configured. It is here to locate the
    failure: if this passes and the full probe does not, the wall is
    specifically the capability needed to configure the new network namespace.
    """
    status, output = _run(
        [bwrap, "--unshare-user", "--ro-bind", "/", "/", "/bin/true"]
    )
    if status is None:
        return Probe(name="bwrap --unshare-user (no netns)", ran=False, detail=output)
    return Probe(
        name="bwrap --unshare-user (no netns)",
        ran=True,
        ok=status == 0,
        detail=output or ("succeeded" if status == 0 else f"exit {status}"),
        value=status,
    )


def probe_landlock() -> Probe:
    """Is the deprecated backend's kernel feature present?

    Reported, never counted. See the module docstring: adopting the legacy
    backend to get a green test would describe a sandbox no run uses.
    """
    lsms = _read_text("/sys/kernel/security/lsm")
    if lsms is None:
        return Probe(
            name="landlock (legacy backend, observation only)",
            ran=False,
            detail="/sys/kernel/security/lsm is not readable here",
        )
    present = "landlock" in lsms.split(",")
    return Probe(
        name="landlock (legacy backend, observation only)",
        ran=True,
        ok=present,
        detail=(
            f"active LSMs: {lsms}"
            + ("" if present else " -- landlock is not among them")
        ),
        value=lsms,
    )


def classify(probes: dict[str, Probe], bwrap: str | None) -> str:
    """Name the wall, from measurements only.

    Ordered from "nothing can fix this" outwards, so the report always names
    the most fundamental cause rather than a symptom further down the chain.
    """
    if bwrap is None:
        return SANDBOX_BINARY_MISSING

    full = probes.get("bwrap_full")
    if full is not None and full.ran and full.ok:
        return READY

    max_ns = probes.get("max_user_namespaces")
    if max_ns is not None and max_ns.value is None:
        return KERNEL_LACKS_USER_NAMESPACES

    if max_ns is not None and str(max_ns.value or "").isdigit():
        if int(str(max_ns.value)) == 0:
            return USER_NAMESPACES_DISABLED_BY_SYSCTL
    clone = probes.get("unprivileged_userns_clone")
    if clone is not None and clone.value == "0":
        return USER_NAMESPACES_DISABLED_BY_SYSCTL

    apparmor = probes.get("apparmor_restrict_unprivileged_userns")
    restricted_by_lsm = apparmor is not None and apparmor.value == "1"

    unshare = probes.get("unshare")
    namespace_was_granted = unshare is not None and unshare.ran and bool(unshare.ok)

    if not namespace_was_granted and restricted_by_lsm:
        return USER_NAMESPACES_RESTRICTED_BY_SECURITY_POLICY

    if namespace_was_granted:
        # The namespace exists, so what failed is inside it.
        if restricted_by_lsm:
            return USER_NAMESPACES_RESTRICTED_BY_SECURITY_POLICY
        if full is not None and full.ran and _looks_like_denied_capability(full.detail):
            return CAPABILITY_DENIED_INSIDE_NAMESPACE

    return UNCLASSIFIED_SANDBOX_FAILURE


def _looks_like_denied_capability(stderr: str) -> bool:
    """Does bwrap's own text say a privileged operation was refused?

    Matched on the errno wording rather than on any one message, because the
    operation that trips first depends on the flags. The known real one is
    ``bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted`` from a
    hosted GitHub runner.
    """
    lowered = stderr.lower()
    return "operation not permitted" in lowered or "permission denied" in lowered


def collect() -> HostReport:
    bwrap = find_bwrap()
    support = probe_user_namespace_support()
    named = {
        "max_user_namespaces": support[0],
        "unprivileged_userns_clone": support[1],
        "apparmor_restrict_unprivileged_userns": support[2],
        "unshare": probe_unshare(),
        "landlock": probe_landlock(),
    }
    if bwrap is not None:
        named["bwrap_full"] = probe_bwrap(bwrap)
        named["bwrap_no_net"] = probe_bwrap_without_net(bwrap)

    readiness = classify(named, bwrap)
    in_container, container_evidence = detect_container()

    landlock = named["landlock"]
    if readiness != READY and landlock.ran and landlock.ok:
        landlock_note = (
            "This host has the Landlock LSM, so Codex's deprecated "
            "use_legacy_landlock backend might run a command here. That is "
            "recorded as an observation and is not readiness: it is a "
            "different sandbox from the one a real run uses."
        )
    else:
        landlock_note = ""

    ordered = [
        named["max_user_namespaces"],
        named["unprivileged_userns_clone"],
        named["apparmor_restrict_unprivileged_userns"],
        named["unshare"],
        named.get("bwrap_full"),
        named.get("bwrap_no_net"),
        named["landlock"],
    ]
    return HostReport(
        readiness=readiness,
        explanation=WALL_EXPLANATIONS[readiness],
        kernel=platform.release(),
        machine=platform.machine(),
        in_container=in_container,
        container_evidence=container_evidence,
        probes=[p.as_dict() for p in ordered if p is not None],
        landlock_note=landlock_note,
    )


def render(report: HostReport) -> str:
    lines: list[str] = []
    lines.append("Codex sandbox host check")
    lines.append("=" * 60)
    lines.append(f"kernel      : {report.kernel} ({report.machine})")
    lines.append(
        f"container   : {report.in_container} -- {report.container_evidence}"
    )
    lines.append("")
    lines.append("measurements")
    lines.append("-" * 60)
    for probe in report.probes:
        if not probe["ran"]:
            mark = "  ?"
        elif probe["ok"] is None:
            mark = "  -"
        else:
            mark = " ok" if probe["ok"] else "FAIL"
        lines.append(f"{mark}  {probe['name']}")
        if probe["detail"]:
            for detail_line in str(probe["detail"]).splitlines():
                lines.append(f"      {detail_line}")
    lines.append("")
    lines.append("verdict")
    lines.append("-" * 60)
    lines.append(f"{report.readiness}")
    lines.append(f"  {report.explanation}")
    if report.landlock_note:
        lines.append("")
        for note_line in report.landlock_note.split(". "):
            if note_line:
                lines.append(f"  note: {note_line.strip().rstrip('.')}.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Say whether this host can run Codex's sandbox, and name the wall "
            "if it cannot."
        )
    )
    parser.add_argument("--json", action="store_true", help="print JSON instead")
    parser.add_argument("--out", type=Path, help="also write the JSON report here")
    args = parser.parse_args(argv)

    try:
        report = collect()
    except Exception as exc:  # noqa: BLE001 - the probe itself broke
        message = f"the sandbox host check could not run: {exc}"
        if args.json:
            print(json.dumps({"error": message}, indent=2))
        else:
            print(message, file=sys.stderr)
        return 2

    payload = report.as_dict()
    if args.out:
        args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2) if args.json else render(report))
    return 0 if report.readiness == READY else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
