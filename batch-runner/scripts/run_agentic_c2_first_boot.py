#!/usr/bin/env python3
"""C2: boot one guest under the jailer on the machine stage B measured.

Runs **on the execution host** and nowhere else. This box runs kernel 3.10 and
cannot boot a Firecracker machine at all, so C1's mapping is tested here and
this is tested only there, and the two are not allowed to be confused.

What it does, in the order it does it, because each step can fail differently:

1.  read the host — cgroup hierarchy version above all, since the jailer
    defaults to v1 and Ubuntu 24.04 runs v2, and a memory bound written to the
    wrong file reads as enforced and is not;
2.  make sure there is an account to jail to that cannot become root;
3.  fetch the pinned guest kernel, recording that upstream vouches for nothing;
4.  pull the parent image by digest, check every blob against its own name,
    unpack the layers in order, add exactly one file, build an ext4 from it;
5.  build the work disk with the command on it;
6.  ask C1's builder for the arguments — this script writes none of its own;
7.  boot the images once *without* the jail, console attached, purely to tell a
    broken image apart from a broken jail. Recorded as not the contained run;
8.  boot under the jailer, wait, read the result off the work disk, destroy the
    chroot;
9.  write one artefact with all of it, including every disclaimer.

It changes no flag and opens no gate. ``foundation_only`` and
``production_activation`` are untouched, and ``exec_run`` stays shut.
"""

from __future__ import annotations

import argparse
import json
import os
import pwd
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.agentic_v2_first_boot import (  # noqa: E402
    WORK_DISK_INPUT,
    first_boot,
    unjailed_image_check,
)
from core.agentic_v2_guest_image import (  # noqa: E402
    PINNED_GUEST_KERNEL,
    add_guest_init,
    build_ext4,
    fetch_pinned_kernel,
    pull_image_by_digest,
    rootfs_size_mib,
    unpack_layers,
)
from core.agentic_v2_microvm_launch import build_launch_plan  # noqa: E402
from core.agentic_v2_substrate import REQUIRED_MICROVM_POLICY  # noqa: E402

JAIL_ACCOUNT = "gdpvaljail"


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_the_host() -> dict[str, Any]:
    """The readings the plan depends on, taken rather than assumed."""
    unified = Path("/sys/fs/cgroup/cgroup.controllers").exists()
    kvm = Path("/dev/kvm")
    return {
        "read_at": now(),
        "cgroup_version": 2 if unified else 1,
        "cgroup_evidence": (
            "/sys/fs/cgroup/cgroup.controllers exists"
            if unified
            else "no /sys/fs/cgroup/cgroup.controllers, so the v1 hierarchy"
        ),
        "kernel_release": os.uname().release,
        "processors": os.cpu_count(),
        "kvm_present": kvm.exists(),
        "firecracker": shutil.which("firecracker"),
        "jailer": shutil.which("jailer"),
        "firecracker_version": _version("firecracker"),
        "jailer_version": _version("jailer"),
    }


def _version(binary: str) -> str | None:
    path = shutil.which(binary)
    if not path:
        return None
    result = subprocess.run(  # noqa: S603
        [path, "--version"], check=False, capture_output=True, text=True, timeout=60
    )
    return (result.stdout or result.stderr).strip().splitlines()[0] if result else None


def account_to_jail_to(name: str = JAIL_ACCOUNT) -> dict[str, Any]:
    """An account with no shell, no password and no group but its own.

    uid 1000 on this host is in ``sudo``. Jailing to it would leave the
    host-side process one command away from root if it ever got out, and the
    ``user: jailer-unprivileged`` rule would still have read as met. So a
    dedicated account is used, and if it turns out to have gained a group this
    refuses rather than jailing to it anyway.
    """
    try:
        entry = pwd.getpwnam(name)
    except KeyError:
        subprocess.run(  # noqa: S603
            [
                "useradd",
                "--system",
                "--no-create-home",
                "--shell",
                "/usr/sbin/nologin",
                name,
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
        entry = pwd.getpwnam(name)
    groups = subprocess.run(  # noqa: S603
        ["id", "-Gn", name], check=False, capture_output=True, text=True, timeout=60
    ).stdout.split()
    extra = sorted(set(groups) - {name})
    if extra:
        raise SystemExit(
            f"the jail account {name} is in {extra}, which is not the "
            "unprivileged account the user rule asks for"
        )
    if entry.pw_uid <= 0 or entry.pw_gid <= 0:
        raise SystemExit(f"{name} resolves to uid {entry.pw_uid}, which is not an account")
    return {
        "name": name,
        "uid": entry.pw_uid,
        "gid": entry.pw_gid,
        "shell": entry.pw_shell,
        "groups_beyond_its_own": extra,
    }


def build_guest_images(
    workdir: Path, repository: str, digest: str, command: str
) -> dict[str, Any]:
    kernel = fetch_pinned_kernel(workdir / "vmlinux")
    image = pull_image_by_digest(repository, digest, workdir / "oci")
    unpacked = unpack_layers(image["layers"], workdir / "root")
    init = add_guest_init(workdir / "root")
    size = rootfs_size_mib(workdir / "root")
    rootfs = build_ext4(workdir / "rootfs.ext4", size_mib=size, populate_from=workdir / "root")

    staging = workdir / "work-in"
    (staging / "in").mkdir(parents=True, exist_ok=True)
    (staging / "out").mkdir(parents=True, exist_ok=True)
    (staging / WORK_DISK_INPUT.lstrip("/")).write_text(command, encoding="utf-8")
    work = build_ext4(
        workdir / "work.ext4",
        size_mib=int(REQUIRED_MICROVM_POLICY["workdir_quota_mib"]),
        populate_from=staging,
    )
    return {
        "kernel": kernel,
        "image": image,
        "unpacked": unpacked,
        "guest_init": init,
        "rootfs": rootfs,
        "work_disk": work,
        "command": command,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", default="/var/tmp/gdpval-c2")
    parser.add_argument(
        "--repository", default="hyeonsangjeon/gdpval-sandbox"
    )
    parser.add_argument(
        "--digest",
        default=(
            "sha256:ee6ef798631d3c3aeaed28658c640e6f5d021677449852bf2e1f18be5"
            "bd24edb"
        ),
        help="the digest parent.lock.json pins; a multi-architecture index",
    )
    parser.add_argument("--vcpu-count", type=int, default=1)
    parser.add_argument("--artefact", default="/var/tmp/gdpval-c2/c2-first-boot.json")
    parser.add_argument(
        "--command",
        default=(
            "set -eu\n"
            "echo 'this ran inside the guest'\n"
            "python3 -c \"print('python answered', 2 + 2)\" 2>/dev/null || "
            "echo 'no python3 in the image'\n"
            "id -u\n"
            "mount | grep ' / ' || true\n"
            "( echo write-to-root > /root-write-probe.txt && "
            "echo 'ROOTFS WAS WRITABLE' ) 2>/dev/null || "
            "echo 'rootfs refused a write, as the rule says it must'\n"
        ),
    )
    parser.add_argument("--skip-unjailed-check", action="store_true")
    parser.add_argument("--also-fire-the-deadline", action="store_true")
    parser.add_argument("--deadline-test-seconds", type=int, default=45)
    args = parser.parse_args()

    started = time.time()
    workdir = Path(args.workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    host = read_the_host()
    artefact: dict[str, Any] = {
        "schema_version": "1.0",
        "stage": "C2",
        "started_at": now(),
        "host": host,
        "what_this_is_not": (
            "not exec_run, not a model call, not a task. No flag was changed "
            "and nothing here is wired into the product path."
        ),
    }

    try:
        if not host["kvm_present"] or not host["jailer"]:
            artefact["outcome"] = "host_cannot_boot"
            artefact["reason"] = (
                "no /dev/kvm or no jailer on this machine, so there is nothing "
                "to run the plan on"
            )
            return _write(artefact, args.artefact, started)

        account = account_to_jail_to()
        artefact["jail_account"] = account

        images = build_guest_images(
            workdir, args.repository, args.digest, args.command
        )
        artefact["images"] = images

        plan = build_launch_plan(
            vm_id="c2-first-boot",
            firecracker_binary=host["firecracker"],
            kernel_path=images["kernel"]["path"],
            rootfs_path=images["rootfs"]["path"],
            work_disk_path=images["work_disk"]["path"],
            uid=account["uid"],
            gid=account["gid"],
            vcpu_count=args.vcpu_count,
            cgroup_version=host["cgroup_version"],
        )
        artefact["plan"] = plan

        if not args.skip_unjailed_check:
            with tempfile.TemporaryDirectory(prefix="c2-unjailed-") as scratch:
                probe_disk = Path(scratch) / "work.ext4"
                shutil.copy2(images["work_disk"]["path"], probe_disk)
                artefact["unjailed_image_check"] = unjailed_image_check(
                    firecracker_binary=host["firecracker"],
                    kernel=images["kernel"]["path"],
                    rootfs=images["rootfs"]["path"],
                    work_disk=probe_disk,
                    workdir=scratch,
                )

        artefact["boot"] = first_boot(
            plan,
            jailer_binary=host["jailer"],
            kernel=images["kernel"]["path"],
            rootfs=images["rootfs"]["path"],
            work_disk=images["work_disk"]["path"],
            uid=account["uid"],
            gid=account["gid"],
        )
        artefact["outcome"] = artefact["boot"]["outcome"]

        if args.also_fire_the_deadline and artefact["outcome"] == "booted":
            artefact["deadline_test"] = _fire_the_deadline(
                workdir, host, account, args
            )
    except Exception as failure:  # noqa: BLE001 - the reason is the artefact
        artefact["outcome"] = "refused"
        artefact["reason"] = f"{type(failure).__name__}: {failure}"
    return _write(artefact, args.artefact, started)


def _fire_the_deadline(
    workdir: Path, host: dict[str, Any], account: dict[str, Any], args: Any
) -> dict[str, Any]:
    """Make ``wall_clock_seconds`` actually fire, without touching the policy.

    The real bound is 1,200 seconds, and waiting twenty minutes to watch a
    deadline work is not a test anybody runs twice. So a *different* policy is
    handed to the same builder — which is a supported argument, and which still
    refuses a policy with a rule missing, added or out of reach — carrying a
    short bound and a command that would never return. The builder is
    unchanged, :data:`REQUIRED_MICROVM_POLICY` is unchanged, and what is being
    checked is the launcher's ability to stop a machine that overruns.

    A deadline nobody has watched fire is a deadline nobody has tested, and this
    one is the only thing standing between a wedged guest and a host that waits
    forever.
    """
    seconds = int(args.deadline_test_seconds)
    policy = dict(REQUIRED_MICROVM_POLICY) | {"wall_clock_seconds": seconds}
    scratch = workdir / "deadline"
    staging = scratch / "work-in"
    (staging / "in").mkdir(parents=True, exist_ok=True)
    (staging / "out").mkdir(parents=True, exist_ok=True)
    (staging / WORK_DISK_INPUT.lstrip("/")).write_text(
        "echo 'about to hang on purpose'\nwhile true; do sleep 5; done\n",
        encoding="utf-8",
    )
    disk = build_ext4(
        scratch / "work.ext4",
        size_mib=int(policy["workdir_quota_mib"]),
        populate_from=staging,
    )
    plan = build_launch_plan(
        vm_id="c2-deadline",
        firecracker_binary=host["firecracker"],
        kernel_path=(workdir / "vmlinux").as_posix(),
        rootfs_path=(workdir / "rootfs.ext4").as_posix(),
        work_disk_path=disk["path"],
        uid=account["uid"],
        gid=account["gid"],
        vcpu_count=args.vcpu_count,
        cgroup_version=host["cgroup_version"],
        policy=policy,
    )
    result = first_boot(
        plan,
        jailer_binary=host["jailer"],
        kernel=(workdir / "vmlinux").as_posix(),
        rootfs=(workdir / "rootfs.ext4").as_posix(),
        work_disk=disk["path"],
        uid=account["uid"],
        gid=account["gid"],
    )
    return {
        "why": (
            "the real bound is 1200s; this run hands the same builder a "
            f"different policy with {seconds}s so the stop can be watched"
        ),
        "policy_used_is_not_the_required_one": True,
        "wall_clock_seconds": seconds,
        "outcome": result["outcome"],
        "stopped_by_the_deadline": result["stopped_by_the_deadline"],
        "ran_for_seconds": result["ran_for_seconds"],
        "chroot_destroyed": result["teardown"]["all_gone"],
    }


def _write(artefact: dict[str, Any], path: str, started: float) -> int:
    artefact["finished_at"] = now()
    artefact["elapsed_seconds"] = round(time.time() - started, 1)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(artefact, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"outcome": artefact["outcome"], "artefact": path}))
    return 0 if artefact["outcome"] == "booted" else 1


if __name__ == "__main__":
    raise SystemExit(main())
