"""Start what C1 wrote down, once, and take the result back off the work disk.

C1 turns :data:`REQUIRED_MICROVM_POLICY` into a document and starts nothing.
That was deliberate — the mapping can be checked anywhere, including on a
machine that cannot boot a virtual machine at all, and this box runs kernel 3.10
and cannot. This module is the other half, and it runs only where stage B
measured: it takes that document and does exactly what it says.

**It adds no argument of its own.** Everything it runs comes out of the plan:
``jailer.argv``, ``firecracker.config``, ``place_in_jail``, and the three
host-side facts under ``host_side``. If a rule is to be applied differently, the
change belongs in C1's builder where the refusals are, not here. That is why
:func:`first_boot` refuses a plan whose ``plan_sha256`` does not match its
contents — a plan edited between being built and being run is a set of arguments
nobody checked.

**Where the result comes from, and why there is only one place.** The policy
forbids a network, and the launcher pins ``vsock`` absent for the same reason.
``--daemonize`` points Firecracker's standard descriptors at ``/dev/null``, so
there is no console either. The work disk is the whole channel: the command goes
in at ``/in/command.sh`` and the answer comes back at ``/out/…``. It is read
with ``debugfs``, which walks the image without mounting it — no loop device, no
privilege, and the host kernel's ext4 driver never sees a filesystem the guest
was writing.

**What this is not.** Booting a guest and getting one command's output back is
not ``exec_run``, is not a model call, and is not a task. Nothing here changes
``foundation_only`` or ``production_activation``, and nothing here is wired into
the product path. That is stage D, and it gets its own change.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Mapping

from core.agentic_v2_guest_image import files_out_of_work_disk, sha256_file
from core.agentic_v2_substrate import canonical_sha256

WORK_DISK_INPUT = "/in/command.sh"
WORK_DISK_RESULTS = (
    "/out/stdout",
    "/out/stderr",
    "/out/exit_status",
    "/out/guest_kernel",
    "/out/guest_uid",
    "/out/init_reached_the_end",
)

POLL_SECONDS = 0.25
PID_FILE_GRACE_SECONDS = 20.0
"""How long the launcher waits for the jailer to write the PID file.

Not the same thing as the deadline. ``--daemonize`` makes the jailer fork and
return immediately, so the absence of a PID file for a moment is normal and its
absence after this long means the machine never started — which is a different
outcome from a machine that started and overran, and the artefact says which.
"""


class BootRefused(RuntimeError):
    """The plan was not run, and the reason is not a boot failure."""


def _run(argv: list[str], timeout: float = 300.0) -> subprocess.CompletedProcess:
    return subprocess.run(  # noqa: S603
        argv, check=False, capture_output=True, text=True, timeout=timeout
    )


def _still_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def place_the_images(
    plan: Mapping[str, Any],
    *,
    kernel: str | Path,
    rootfs: str | Path,
    work_disk: str | Path,
    uid: int,
    gid: int,
) -> dict[str, Any]:
    """Put each image where ``place_in_jail`` says, with the mode it says.

    The jailer will create this directory itself if it is absent; it is created
    here because the images have to be inside it before the machine starts and
    there is no later moment to put them there.

    Ownership follows the plan's ``writable_by_the_jailed_user`` rather than a
    convention: the two images the guest must not change are ``0444`` and owned
    by root, and only the work disk is writable by the account the jailer drops
    to. A rootfs the jailed user can write to would make ``rootfs: read-only``
    true only for as long as the guest chose to respect it.
    """
    chroot_dir = Path(plan["host_side"]["chroot_dir"])
    chroot_dir.mkdir(parents=True, exist_ok=True)
    sources = {"/vmlinux": Path(kernel), "/rootfs.ext4": Path(rootfs)}
    placed = []
    for item in plan["place_in_jail"]:
        target = chroot_dir / item["in_jail"].lstrip("/")
        if item["in_jail"] == "/vmconfig.json":
            target.write_text(
                json.dumps(plan["firecracker"]["config"], indent=2), encoding="utf-8"
            )
        elif item["how"] == "create-empty":
            shutil.copy2(work_disk, target)
        else:
            shutil.copy2(sources[item["in_jail"]], target)
        writable = bool(item["writable_by_the_jailed_user"])
        os.chmod(target, 0o644 if writable else 0o444)
        os.chown(target, uid if writable else 0, gid if writable else 0)
        placed.append(
            {
                "in_jail": item["in_jail"],
                "sha256": sha256_file(target),
                "bytes": target.stat().st_size,
                "mode": oct(target.stat().st_mode & 0o777),
                "owned_by_the_jailed_user": writable,
            }
        )
    os.chmod(chroot_dir, 0o755)
    return {"chroot_dir": chroot_dir.as_posix(), "placed": placed}


def first_boot(
    plan: Mapping[str, Any],
    *,
    jailer_binary: str = "jailer",
    kernel: str | Path,
    rootfs: str | Path,
    work_disk: str | Path,
    uid: int,
    gid: int,
    now: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Run one plan through to a result, or to a recorded reason it produced none.

    Returns rather than raises for every outcome that is about the machine —
    a guest that would not boot, one that overran its deadline, one that booted
    and wrote nothing. Those are findings. It raises only when the plan itself
    is unusable, which is not a finding about a machine.
    """
    if plan.get("starts_nothing") is not True:
        raise BootRefused("this is not a launch plan from the C1 builder")
    stated = plan.get("plan_sha256")
    recomputed = canonical_sha256({k: v for k, v in plan.items() if k != "plan_sha256"})
    if stated != recomputed:
        raise BootRefused(
            "the plan's contents do not hash to its own plan_sha256, so it was "
            "changed after it was built and these are arguments nobody checked"
        )

    host_side = plan["host_side"]
    pid_file = Path(host_side["pid_file"])
    deadline_seconds = float(host_side["deadline_seconds"])
    placement = place_the_images(
        plan, kernel=kernel, rootfs=rootfs, work_disk=work_disk, uid=uid, gid=gid
    )
    chroot_dir = Path(placement["chroot_dir"])

    started_at = now()
    launch = _run([jailer_binary, *plan["jailer"]["argv"]], timeout=120.0)

    pid: int | None = None
    while now() - started_at < PID_FILE_GRACE_SECONDS:
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
            except ValueError:
                pid = None
            if pid:
                break
        sleep(POLL_SECONDS)

    outcome = "booted"
    stopped_by_the_deadline = False
    if pid is None:
        outcome = "never_started"
    else:
        while _still_running(pid):
            if now() - started_at >= deadline_seconds:
                stopped_by_the_deadline = True
                outcome = "stopped_by_the_deadline"
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    stopped_by_the_deadline = False
                    outcome = "booted"
                break
            sleep(POLL_SECONDS)
    ran_for = round(now() - started_at, 3)

    disk_in_jail = chroot_dir / "work.ext4"
    results: dict[str, str | None] = {}
    if disk_in_jail.exists():
        results = files_out_of_work_disk(disk_in_jail, WORK_DISK_RESULTS)
        shutil.copy2(disk_in_jail, str(work_disk) + ".returned")

    exit_status = None
    raw_status = (results.get("/out/exit_status") or "").strip()
    if raw_status.isdigit():
        exit_status = int(raw_status)
    if outcome == "booted" and exit_status is None:
        outcome = "booted_but_wrote_nothing"

    destroyed = _destroy(host_side.get("destroy_after_the_run", []))

    return {
        "schema_version": "1.0",
        "outcome": outcome,
        "vm_id": plan["vm_id"],
        "plan_sha256": plan["plan_sha256"],
        "policy_sha256": plan["policy_sha256"],
        "jailer": {
            "argv": list(plan["jailer"]["argv"]),
            "returncode": launch.returncode,
            "stderr": launch.stderr[-4000:],
        },
        "pid_file": {
            "path": pid_file.as_posix(),
            "appeared": pid is not None,
            "pid_recorded": pid is not None,
        },
        "ran_for_seconds": ran_for,
        "deadline_seconds": deadline_seconds,
        "stopped_by_the_deadline": stopped_by_the_deadline,
        "command_exit_status": exit_status,
        "results": results,
        "placement": placement,
        "teardown": destroyed,
        "channel": (
            "the work disk only: no network by policy, vsock pinned absent, and "
            "--daemonize sends the console to /dev/null"
        ),
    }


def _destroy(paths: list[str]) -> dict[str, Any]:
    """Remove what the plan said to remove, and say whether it is gone.

    Reported rather than assumed. A chroot that survives holds the work disk,
    which holds whatever the guest wrote, and "destroyed after the run" is part
    of ``workdir: ephemeral-quota`` rather than tidiness.
    """
    gone = {}
    for path in paths:
        shutil.rmtree(path, ignore_errors=True)
        gone[path] = not Path(path).exists()
    return {"removed": gone, "all_gone": all(gone.values()) if gone else False}


def unjailed_image_check(
    *,
    firecracker_binary: str,
    kernel: str | Path,
    rootfs: str | Path,
    work_disk: str | Path,
    workdir: str | Path,
    seconds: float = 90.0,
) -> dict[str, Any]:
    """Boot the same two images with the console attached, outside the jail.

    **This is not the contained run and does not count towards C2's exit
    condition.** It exists because a jailed boot is nearly silent: with no
    console and no network, a guest that panics on its second instruction leaves
    exactly the evidence a guest that booted and wrote nothing leaves. Running
    the images once with the console readable separates "the images are wrong"
    from "the jail is wrong", which is the difference between a fixable result
    and a shrug.

    It applies none of the containment. Every field it returns is labelled with
    that, and a caller that treats it as the boundary is reading it wrong.
    """
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    config = {
        "boot-source": {
            "kernel_image_path": Path(kernel).as_posix(),
            "boot_args": "console=ttyS0 reboot=k panic=1 pci=off root=/dev/vda ro",
        },
        "drives": [
            {
                "drive_id": "rootfs",
                "path_on_host": Path(rootfs).as_posix(),
                "is_root_device": True,
                "is_read_only": True,
            },
            {
                "drive_id": "work",
                "path_on_host": Path(work_disk).as_posix(),
                "is_root_device": False,
                "is_read_only": False,
            },
        ],
        "machine-config": {"vcpu_count": 1, "mem_size_mib": 1024},
        "network-interfaces": [],
    }
    config_path = workdir / "unjailed-vmconfig.json"
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    timed_out = False
    try:
        finished = _run(
            [firecracker_binary, "--config-file", config_path.as_posix(), "--no-api"],
            timeout=seconds,
        )
        console, returncode = finished.stdout, finished.returncode
    except subprocess.TimeoutExpired as expired:
        timed_out = True
        console = (expired.stdout or b"").decode("utf-8", "replace") if isinstance(
            expired.stdout, bytes
        ) else (expired.stdout or "")
        returncode = None
    return {
        "this_is_not_the_contained_run": True,
        "what_it_proves": "only that these two images boot; no rule was applied",
        "applied_containment": False,
        "timed_out": timed_out,
        "returncode": returncode,
        "console_tail": console[-6000:],
    }
