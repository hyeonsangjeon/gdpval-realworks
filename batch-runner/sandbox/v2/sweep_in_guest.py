"""Take the declared-command sweep again, inside the guest stage D will boot.

:mod:`sandbox.v2.probe_declared_commands` answers *what is in this image* by
running the probes in a container. It says, in its own artifact, that the
answer belongs to the place it was taken — and both sweeps it has produced so
far were taken with docker on a cgroup v1 host running a 3.10 kernel, which is
not where any task will run.

This module takes the same measurement in the place that matters: the rootfs
C2 booted, in a Firecracker microVM, under
:data:`core.agentic_v2_substrate.REQUIRED_MICROVM_POLICY`, on the host whose
kernel C2 recorded. Same probes, same framing, same reader — the only thing
that changes is the machine, which is the whole point.

**Two changes to the driver, both recorded in the artifact.**

The container sweep gives each probe ``/tmp`` to write to. In the guest the
rootfs is mounted read-only by policy and the work disk at ``/work`` is the only
writable mount, so the redirections move there and ``HOME`` and ``TMPDIR``
follow. That second one is not tidiness: a probe that fails because it had
nowhere to write exits non-zero exactly like a probe whose command is absent,
and the artifact would record the wrong reason.

**What a result here is still not.** Not a capability receipt — it carries no
SBOM, no licence classification, no package inventory — and
:func:`core.agentic_v2_substrate.validate_capability_receipt` rejects it, which
a test asserts. Not a signature or provenance check; those remain ``not_run``.
Not an isolation measurement; C3 made that one, separately, by attacking.

**On ``guest_uid``.** The artifact records ``0``, and that is not a containment
failure. Root inside the guest is the ordinary arrangement for a microVM: the
boundary is the virtual machine, not a uid, and the *host* side of it runs as
the unprivileged jail account C2 recorded. Both numbers are kept side by side
so no reader has to take that on trust.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

BATCH_ROOT = Path(__file__).resolve().parents[2]
if str(BATCH_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_ROOT))

from core.agentic_v2_first_boot import first_boot  # noqa: E402
from core.agentic_v2_guest_image import build_ext4, sha256_file  # noqa: E402
from core.agentic_v2_microvm_launch import build_launch_plan  # noqa: E402
from core.agentic_v2_substrate import REQUIRED_MICROVM_POLICY  # noqa: E402
from sandbox.v2.probe_declared_commands import (  # noqa: E402
    ALWAYS_ASKED,
    DEFAULT_MANIFEST,
    _canonical_sha256,
    _font_probes,
    _module_probes,
    _parse,
    _shell_driver,
)

#: Where C2 left its record, and where its images still are.
C2_ARTEFACT = Path("/var/tmp/gdpval-c2/c2-first-boot.json")

#: The guest's only writable mount, created by the init at ``/work``.
WRITABLE_MOUNT = "/work"

#: The input path the guest init reads its command from, and the two result
#: files this module needs back out of the work disk.
WORK_DISK_INPUT = "/in/command.sh"


class GuestSweepRefused(RuntimeError):
    """The sweep was not run, and the reason is not a fact about the image."""


def read_the_c2_record(path: Path = C2_ARTEFACT) -> dict[str, Any]:
    """C2's artefact, or a refusal that says which of four things to do.

    The same four questions the stage D runner asks, for the same reason and at
    a fraction of the cost: this sweep is free, so its refusals are about not
    producing a measurement that would be read as belonging to a machine it was
    not taken on.
    """
    path = Path(path)
    if not path.is_file():
        raise GuestSweepRefused(
            f"there is no C2 record at {path}. Run "
            "scripts/run_agentic_c2_first_boot.py first: without it there is no "
            "rootfs to sweep and no evidence this host can boot one"
        )
    record = json.loads(path.read_text(encoding="utf-8"))
    outcome = record.get("outcome")
    if outcome != "booted":
        raise GuestSweepRefused(
            f"C2 recorded {outcome!r} on this host"
            + (f": {record['reason']}" if record.get("reason") else "")
            + ". A sweep needs a guest that starts, so fix that first"
        )
    recorded_kernel = str(record["host"]["kernel_release"])
    running_kernel = platform.release()
    if recorded_kernel != running_kernel:
        raise GuestSweepRefused(
            f"C2 booted on kernel {recorded_kernel} and this is {running_kernel}, "
            "so the record was copied from a different machine. Run C2 here "
            "before sweeping here"
        )
    return record


def images_are_where_c2_left_them(
    record: Mapping[str, Any], *, rehash: bool = False, measure: Any = None
) -> dict[str, Any]:
    """Kernel and rootfs present, and optionally still the same bytes.

    Presence is always checked because a missing file produces a boot failure
    that reads like a broken image. Re-hashing is opt-in: it costs a full read
    of about nine gibibytes, which is nothing against a paid stage D run and is
    most of the wall clock of a free sweep.
    """
    hasher = measure or sha256_file
    checked: dict[str, Any] = {"rehashed": bool(rehash)}
    for which in ("kernel", "rootfs"):
        recorded = record["images"][which]
        where = Path(str(recorded["path"]))
        if not where.is_file():
            raise GuestSweepRefused(
                f"C2 booted {which} at {where} and it is not there now; the host "
                "has been reprovisioned or the file was removed"
            )
        entry: dict[str, Any] = {"path": where.as_posix()}
        if rehash:
            found = hasher(where)
            if found != str(recorded["sha256"]):
                raise GuestSweepRefused(
                    f"the {which} at {where} hashes {found} and C2 booted "
                    f"{recorded['sha256']}; these are different bytes"
                )
            entry["sha256"] = found
        else:
            entry["sha256_recorded_by_c2"] = str(recorded["sha256"])
        checked[which] = entry
    return checked


def build_probes(manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Every probe the container sweep would ask, in the same order.

    Built here rather than imported as a list because
    :func:`~sandbox.v2.probe_declared_commands.sweep` assembles them inline; the
    four helpers it assembles them from are shared, so the two sweeps cannot
    drift into asking different questions.
    """
    probes: list[dict[str, Any]] = [dict(p, kind="command") for p in ALWAYS_ASKED]
    probes += [dict(p, kind="command") for p in manifest["commands"]]
    probes += _module_probes(manifest["python_modules"], "python3")
    probes += _font_probes(manifest["font_families"])
    return probes


#: Prepended to the shared driver. Exported so the artifact can quote what it
#: actually ran rather than describe it.
GUEST_PREAMBLE = f"HOME={WRITABLE_MOUNT}\nTMPDIR={WRITABLE_MOUNT}\nexport HOME TMPDIR\n"


def guest_driver(probes: Sequence[Mapping[str, Any]]) -> str:
    """The shared driver with its scratch paths moved onto the work disk.

    A textual substitution on a generated string, which is worth being uneasy
    about — so it is checked rather than trusted. If the shared driver ever
    stops writing to ``/tmp/probe.``, or starts writing somewhere else as well,
    the assertion fails here instead of the sweep silently recording every probe
    as absent because the redirect hit a read-only filesystem.
    """
    driver = _shell_driver(probes)
    if "/tmp/probe." not in driver:
        raise GuestSweepRefused(
            "the shared driver no longer redirects to /tmp/probe., so this "
            "module's substitution has nothing to do and would leave the "
            "scratch paths pointing at a read-only rootfs. Update it together "
            "with probe_declared_commands._shell_driver"
        )
    moved = driver.replace("/tmp/probe.", f"{WRITABLE_MOUNT}/probe.")
    if "/tmp/probe." in moved:
        raise GuestSweepRefused("a /tmp scratch path survived the substitution")
    return GUEST_PREAMBLE + moved


def boot_one_guest(
    *,
    driver: str,
    record: Mapping[str, Any],
    workdir: Path,
    vcpu_count: int = 1,
    policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """One machine, one driver, and whatever it wrote on the way out.

    ``workdir`` is where the work disk is built, and it is deliberately not
    C2's directory: building one there would put a fresh ``work.ext4`` beside
    the rootfs whose hash C2 recorded, and the next person to read that
    directory would have to work out which files are evidence.
    """
    host = record["host"]
    account = record["jail_account"]
    in_force = dict(policy or REQUIRED_MICROVM_POLICY)

    staging = Path(workdir) / "work-in"
    (staging / "in").mkdir(parents=True, exist_ok=True)
    (staging / "out").mkdir(parents=True, exist_ok=True)
    (staging / WORK_DISK_INPUT.lstrip("/")).write_text(driver, encoding="utf-8")
    disk = build_ext4(
        Path(workdir) / "work-sweep.ext4",
        size_mib=int(in_force["workdir_quota_mib"]),
        populate_from=staging,
    )

    kernel = Path(str(record["images"]["kernel"]["path"]))
    rootfs = Path(str(record["images"]["rootfs"]["path"]))
    plan = build_launch_plan(
        vm_id="declared-sweep",
        firecracker_binary=host["firecracker"],
        kernel_path=kernel,
        rootfs_path=rootfs,
        work_disk_path=disk["path"],
        uid=account["uid"],
        gid=account["gid"],
        vcpu_count=vcpu_count,
        cgroup_version=host["cgroup_version"],
        policy=in_force,
    )
    result = first_boot(
        plan,
        jailer_binary=host["jailer"],
        kernel=kernel,
        rootfs=rootfs,
        work_disk=disk["path"],
        uid=account["uid"],
        gid=account["gid"],
    )
    result["policy_is_the_required_one"] = in_force == dict(REQUIRED_MICROVM_POLICY)
    result["work_disk"] = disk
    return result


def sweep_in_guest(
    *,
    record: Mapping[str, Any],
    workdir: Path,
    manifest_path: Path = DEFAULT_MANIFEST,
    vcpu_count: int = 1,
    images_checked: Mapping[str, Any] | None = None,
    boot: Callable[..., dict[str, Any]] | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    """Run every declared probe in one guest and say what came back."""
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    probes = build_probes(manifest)
    driver = guest_driver(probes)

    started = clock()
    booted = (boot or boot_one_guest)(
        driver=driver, record=record, workdir=Path(workdir), vcpu_count=vcpu_count
    )
    took = clock() - started

    results = booted.get("results") or {}
    transcript = results.get("/out/stdout") or ""
    records = _parse(transcript, probes)
    answered = [row for row in records if row["answered"]]

    return {
        "artifact": "agentic-v2-declared-command-sweep",
        "artifact_version": "1.0",
        "taken": (
            "inside a Firecracker guest, on the execution host, under the "
            "required microVM policy"
        ),
        "is_not": [
            "a capability receipt",
            "a signature or provenance verification",
            "a vulnerability scan",
            "an isolation or containment measurement",
        ],
        "supersedes_nothing": (
            "the container sweeps stand as what they are: measurements of the "
            "same image somewhere else. This one answers the question they "
            "recorded that they could not"
        ),
        "driver_changes": [
            f"probe scratch paths go to {WRITABLE_MOUNT} rather than /tmp, "
            "because the rootfs is mounted read-only by policy",
            f"HOME and TMPDIR are {WRITABLE_MOUNT}, because a probe with nowhere "
            "to write exits non-zero exactly like an absent command",
        ],
        "image": record["images"]["image"],
        "images_checked": dict(images_checked or {}),
        "manifest_sha256": _canonical_sha256(manifest),
        "manifest_path": Path(manifest_path).as_posix(),
        "declared": {
            "commands": len(manifest["commands"]),
            "python_modules": len(manifest["python_modules"]),
            "font_families": len(manifest["font_families"]),
            "platform": manifest["platform"],
        },
        "host": {
            "kernel": platform.release(),
            "machine": platform.machine(),
            "system": platform.system(),
            "cgroup_version": record["host"]["cgroup_version"],
            "firecracker_version": record["host"].get("firecracker_version"),
            "jailed_to_uid": record["jail_account"]["uid"],
        },
        "guest": {
            "vm_id": booted.get("vm_id"),
            "plan_sha256": booted.get("plan_sha256"),
            "policy_sha256": booted.get("policy_sha256"),
            "policy_is_the_required_one": booted.get("policy_is_the_required_one"),
            "outcome": booted.get("outcome"),
            "ran_for_seconds": booted.get("ran_for_seconds"),
            "deadline_seconds": booted.get("deadline_seconds"),
            "stopped_by_the_deadline": booted.get("stopped_by_the_deadline"),
            "command_exit_status": booted.get("command_exit_status"),
            "kernel": (results.get("/out/guest_kernel") or "").strip(),
            "uid": (results.get("/out/guest_uid") or "").strip(),
            "uid_note": (
                "root inside the guest is the ordinary arrangement for a "
                "microVM: the boundary is the machine, and the host-side "
                "process runs as host.jailed_to_uid"
            ),
            "init_reached_the_end": bool(
                (results.get("/out/init_reached_the_end") or "").strip()
            ),
            "teardown": booted.get("teardown"),
        },
        "transcript_bytes": len(transcript),
        "sweep_seconds": round(took, 2),
        "probes_declared": len(probes),
        "probes_answered": len(answered),
        "present": sum(1 for row in answered if row["present"]),
        "absent": sum(1 for row in answered if not row["present"]),
        "records": records,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--c2-artefact", default=str(C2_ARTEFACT))
    parser.add_argument("--workdir", default="/var/tmp/gdpval-sweep")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--vcpu-count", type=int, default=1)
    parser.add_argument(
        "--rehash-images",
        action="store_true",
        help="re-read the kernel and rootfs and compare to C2's hashes (~9 GiB)",
    )
    parser.add_argument("--out", default="")
    args = parser.parse_args(argv)

    try:
        record = read_the_c2_record(Path(args.c2_artefact))
        checked = images_are_where_c2_left_them(record, rehash=args.rehash_images)
    except GuestSweepRefused as refused:
        print(f"Refused before booting anything: {refused}")
        return 1

    workdir = Path(args.workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    result = sweep_in_guest(
        record=record,
        workdir=workdir,
        manifest_path=Path(args.manifest),
        vcpu_count=args.vcpu_count,
        images_checked=checked,
        clock=time.time,
    )

    out = Path(args.out) if args.out else workdir / "guest-declared-command-sweep.json"
    out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")

    guest = result["guest"]
    print(f"guest      {guest['outcome']}  ran {guest['ran_for_seconds']}s of "
          f"{guest['deadline_seconds']}s  exit {guest['command_exit_status']}")
    print(f"host       {result['host']['kernel']} {result['host']['machine']}  "
          f"cgroup v{result['host']['cgroup_version']}")
    print(f"answered   {result['probes_answered']}/{result['probes_declared']}"
          f"   present {result['present']}   absent {result['absent']}")
    for row in result["records"]:
        mark = "ok " if row["present"] else ("-- " if row["answered"] else "?? ")
        print(f"  {mark}{row['name']:<28} {row['first_line'][:70]}")
    print(f"written    {out.as_posix()}")
    # A sweep that ran is a success even when things are absent: absence is the
    # answer it was sent to get. A guest that never booted is not.
    return 0 if result["probes_answered"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
