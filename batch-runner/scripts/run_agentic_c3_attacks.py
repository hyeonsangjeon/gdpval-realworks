"""Run the seven attacks against a machine the C2 plan built, and judge them.

Nothing here is new containment. Every rule being attacked is one C1 already
turned into an argument and C2 already booted under; this script's whole job is
to try to get past each of them and to read back something that says whether it
got past.

**It builds no new images.** The kernel and rootfs come from the C2 workdir, and
their hashes are compared against what C2 recorded before anything boots. An
attack run against a *different* guest than the one whose boot was recorded would
be seven verdicts about an unidentified machine, and rebuilding an 8.7 GiB rootfs
to get the same bytes is a slower way of being less sure.

**Two of the seven are read from the host while the guest is alive.** The uid the
jailer dropped to and the credentials the Firecracker process carries are facts
about a host process, not about anything the guest can see — inside the machine
PID 1 is root and is meant to be. So the probe boot holds itself open for a few
seconds and a watcher reads ``/proc/<pid>`` while it does. The watcher runs
beside :func:`first_boot` rather than inside it, because ``first_boot`` adds no
argument of its own and this would be one.

Usage on the host, as root, with C2's workdir already populated::

    python3 scripts/run_agentic_c3_attacks.py \\
        --images-from /var/tmp/gdpval-c2 \\
        --workdir /var/tmp/gdpval-c3 \\
        --artefact /var/tmp/gdpval-c3/c3-attacks.json
"""

from __future__ import annotations

import argparse
import json
import os
import threading
import time
from pathlib import Path
from typing import Any

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.agentic_v2_containment_attacks import (  # noqa: E402
    BOOT_MEMORY,
    BOOT_PROBES,
    BOOT_WALL_CLOCK,
    BOOT_WORKDIR,
    guest_commands,
    judge_all,
)
from core.agentic_v2_first_boot import WORK_DISK_INPUT, first_boot  # noqa: E402
from core.agentic_v2_guest_image import build_ext4, sha256_file  # noqa: E402
from core.agentic_v2_microvm_launch import build_launch_plan  # noqa: E402
from core.agentic_v2_substrate import REQUIRED_MICROVM_POLICY  # noqa: E402

from run_agentic_c2_first_boot import (  # noqa: E402
    account_to_jail_to,
    now,
    read_the_host,
)

CANARY_VARIABLE = "GDPVAL_C3_CANARY_TOKEN"
CANARY_VALUE = "if-this-reaches-the-guest-the-rule-did-not-hold"


class Watcher(threading.Thread):
    """Read ``/proc/<pid>`` once, while the machine it belongs to is still alive.

    Polls for the PID file the plan names rather than being handed a pid,
    because the launcher owns the process and this thread is deliberately not
    part of it. If the machine comes and goes before a single read lands, the
    watcher reports nothing — and nothing is a failed attack, not a passed one.
    """

    def __init__(self, pid_file: Path, canary_path: Path, expected_uid: int):
        super().__init__(daemon=True)
        self.pid_file = pid_file
        self.canary_path = canary_path.resolve().as_posix()
        self.expected_uid = expected_uid
        self.seen: dict[str, Any] | None = None
        self.stop = threading.Event()

    def run(self) -> None:
        while not self.stop.is_set():
            try:
                pid = int(self.pid_file.read_text().strip())
            except (OSError, ValueError):
                time.sleep(0.02)
                continue
            reading = self._read(pid)
            if reading is not None:
                self.seen = reading
                return
            time.sleep(0.02)

    def _read(self, pid: int) -> dict[str, Any] | None:
        proc = Path("/proc") / str(pid)
        try:
            status = (proc / "status").read_text()
            raw_environment = (proc / "environ").read_bytes()
        except OSError:
            return None

        real_uid = None
        groups: list[int] = []
        for line in status.splitlines():
            if line.startswith("Uid:"):
                real_uid = int(line.split()[1])
            elif line.startswith("Groups:"):
                groups = [int(g) for g in line.split()[1:]]

        entries = [e for e in raw_environment.decode("utf-8", "replace").split("\0") if e]
        canaries = [
            entry.split("=", 1)[0]
            for entry in entries
            if CANARY_VARIABLE in entry or CANARY_VALUE in entry
        ]

        descriptors: dict[str, str] = {}
        try:
            for handle in sorted((proc / "fd").iterdir(), key=lambda p: int(p.name)):
                try:
                    descriptors[handle.name] = os.readlink(handle)
                except OSError:
                    descriptors[handle.name] = "unreadable"
        except OSError:
            return None

        return {
            "pid": pid,
            "real_uid": real_uid,
            "expected_uid": self.expected_uid,
            "supplementary_groups": [g for g in groups if g != 0],
            "environment_seen": len(entries),
            "environment_names": sorted(entry.split("=", 1)[0] for entry in entries),
            "canaries_in_environment": canaries,
            "descriptors": descriptors,
            "descriptors_reaching_the_orchestrator": [
                f"{fd} -> {target}"
                for fd, target in descriptors.items()
                if target == self.canary_path or "c3-canary" in target
            ],
            "standard_descriptors": {
                fd: descriptors.get(fd) for fd in ("0", "1", "2")
            },
            "read_at": now(),
        }


def _work_disk(workdir: Path, name: str, command: str, size_mib: int) -> dict[str, Any]:
    staging = workdir / f"work-in-{name}"
    (staging / "in").mkdir(parents=True, exist_ok=True)
    (staging / "out").mkdir(parents=True, exist_ok=True)
    (staging / WORK_DISK_INPUT.lstrip("/")).write_text(command, encoding="utf-8")
    return build_ext4(
        workdir / f"work-{name}.ext4", size_mib=size_mib, populate_from=staging
    )


def _one_attack_boot(
    *,
    name: str,
    command: str,
    workdir: Path,
    host: dict[str, Any],
    account: dict[str, Any],
    kernel: Path,
    rootfs: Path,
    policy: dict[str, Any],
    canary_path: Path,
    watch: bool,
) -> dict[str, Any]:
    disk = _work_disk(
        workdir, name, command, int(policy["workdir_quota_mib"])
    )
    plan = build_launch_plan(
        vm_id=f"c3-{name}",
        firecracker_binary=host["firecracker"],
        kernel_path=kernel,
        rootfs_path=rootfs,
        work_disk_path=disk["path"],
        uid=account["uid"],
        gid=account["gid"],
        vcpu_count=1,
        cgroup_version=host["cgroup_version"],
        policy=policy,
    )

    watcher = None
    if watch:
        watcher = Watcher(
            Path(plan["host_side"]["pid_file"]), canary_path, account["uid"]
        )
        watcher.start()

    result = first_boot(
        plan,
        jailer_binary=host["jailer"],
        kernel=kernel,
        rootfs=rootfs,
        work_disk=disk["path"],
        uid=account["uid"],
        gid=account["gid"],
    )
    if watcher is not None:
        watcher.stop.set()
        watcher.join(timeout=2.0)
        result["watched"] = watcher.seen
        if watcher.seen is None:
            result["watched_failed_because"] = (
                "no /proc read landed while the machine was alive; the attacks "
                "that depend on it are recorded as not stopped"
            )
    result["work_disk"] = disk
    result["policy_used"] = policy
    result["policy_is_the_required_one"] = policy == dict(REQUIRED_MICROVM_POLICY)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", default="/var/tmp/gdpval-c3")
    parser.add_argument("--images-from", default="/var/tmp/gdpval-c2")
    parser.add_argument(
        "--c2-artefact", default="/var/tmp/gdpval-c2/c2-first-boot.json"
    )
    parser.add_argument("--artefact", default="/var/tmp/gdpval-c3/c3-attacks.json")
    parser.add_argument(
        "--wall-clock-seconds",
        type=int,
        default=45,
        help=(
            "the bound the hanging guest is run against. The real rule is 1200s; "
            "attack 3 uses a shorter one so the stop can be watched, and the "
            "artefact records that the policy was not the required one"
        ),
    )
    args = parser.parse_args()

    started = time.time()
    workdir = Path(args.workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    images_from = Path(args.images_from)
    kernel = images_from / "vmlinux"
    rootfs = images_from / "rootfs.ext4"

    host = read_the_host()
    artefact: dict[str, Any] = {
        "schema_version": "1.0",
        "stage": "C3",
        "started_at": now(),
        "host": host,
        "what_this_is_not": (
            "not exec_run, not a model call, not a task. No flag was changed, no "
            "rule was relaxed, and nothing here is wired into the product path."
        ),
    }

    try:
        for image in (kernel, rootfs):
            if not image.exists():
                artefact["outcome"] = "images_not_present"
                artefact["reason"] = f"{image} is not there; run C2 first"
                return _write(artefact, args.artefact, started)

        same = {"kernel_sha256": sha256_file(kernel), "rootfs_sha256": sha256_file(rootfs)}
        try:
            c2 = json.loads(Path(args.c2_artefact).read_text())
            recorded = {
                "kernel_sha256": c2["images"]["kernel"]["sha256"],
                "rootfs_sha256": c2["images"]["rootfs"]["sha256"],
            }
            same["matches_the_guest_c2_booted"] = same != {} and all(
                same[k] == recorded[k] for k in recorded
            )
            same["c2_recorded"] = recorded
        except (OSError, KeyError, ValueError) as unreadable:
            same["matches_the_guest_c2_booted"] = None
            same["c2_could_not_be_read"] = repr(unreadable)
        artefact["images"] = same

        if same.get("matches_the_guest_c2_booted") is False:
            artefact["outcome"] = "different_guest"
            artefact["reason"] = (
                "the images here are not the ones C2 booted, so seven verdicts "
                "would be about a machine whose boot nobody recorded"
            )
            return _write(artefact, args.artefact, started)

        account = account_to_jail_to()
        artefact["jail_account"] = account

        canary_path = workdir / "c3-canary-token.txt"
        canary_path.write_text(CANARY_VALUE, encoding="utf-8")
        os.environ[CANARY_VARIABLE] = CANARY_VALUE
        held_open = canary_path.open("rb")

        required = dict(REQUIRED_MICROVM_POLICY)
        shortened = required | {"wall_clock_seconds": int(args.wall_clock_seconds)}
        commands = guest_commands(required)
        groups = [
            (BOOT_PROBES, commands[BOOT_PROBES], required, True),
            (BOOT_WORKDIR, commands[BOOT_WORKDIR], required, False),
            (BOOT_MEMORY, commands[BOOT_MEMORY], required, False),
            (BOOT_WALL_CLOCK, commands[BOOT_WALL_CLOCK], shortened, False),
        ]

        boots: dict[str, Any] = {}
        for name, command, policy, watch in groups:
            boots[name] = _one_attack_boot(
                name=name,
                command=command,
                workdir=workdir,
                host=host,
                account=account,
                kernel=kernel,
                rootfs=rootfs,
                policy=policy,
                canary_path=canary_path,
                watch=watch,
            )
            boots[name]["command"] = command
        held_open.close()
        artefact["boots"] = boots

        artefact["judgement"] = judge_all(artefact)
        artefact["outcome"] = (
            "all_seven_stopped"
            if artefact["judgement"]["all_seven_stopped"]
            else "escaped"
        )
    except Exception as failure:  # noqa: BLE001 - the artefact records the failure
        artefact["outcome"] = "error"
        artefact["error"] = repr(failure)
    return _write(artefact, args.artefact, started)


def _write(artefact: dict[str, Any], path: str, started: float) -> int:
    artefact["finished_at"] = now()
    artefact["elapsed_seconds"] = round(time.time() - started, 1)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(artefact, indent=1, sort_keys=True), encoding="utf-8")
    print(f"artefact={target}")
    print(json.dumps(artefact.get("judgement", {"outcome": artefact["outcome"]}), indent=1))
    return 0 if artefact["outcome"] == "all_seven_stopped" else 1


if __name__ == "__main__":
    raise SystemExit(main())
