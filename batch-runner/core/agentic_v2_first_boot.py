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

from core.agentic_v2_guest_image import (
    GUEST_INIT_PATH,
    files_out_of_work_disk,
    sha256_file,
)
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

STOP_CONFIRMATION_SECONDS = 10.0
CONFIRMATION_POLL_SECONDS = 0.25
"""How long this waits to see a signalled machine actually go.

Finite on purpose. A process that has been SIGKILLed is normally gone within
milliseconds, but it stays visible while the kernel reaps it and it stays
visible indefinitely if it is stuck in uninterruptible sleep on a wedged device.
Waiting forever would hang the run; declaring it stopped because a signal was
sent would put a guess in the artefact. So it waits this long and then records
what it actually saw.
"""

PID_CEILING = 2**31 - 1
"""The largest value ``os.kill`` accepts on this interpreter.

Measured rather than assumed, on CPython 3.10 on this host: ``2147483647``
raises ``ProcessLookupError`` (it converted, and no such process exists),
``2147483648`` raises ``OverflowError``. That matters beyond tidiness, because
``OverflowError`` is **not** an ``OSError`` — every ``except OSError`` guard in
this module lets it through.
"""

CANNOT_RULE_OUT = (
    "PID reuse. Between the last moment this run looked at that number and the "
    "moment it signals, the kernel may have ended that process and handed the "
    "same number to another. POSIX offers this code no way to close that "
    "window; re-reading the file immediately before signalling narrows it."
)
"""What the ownership evidence below still does not establish.

Recorded in the artefact rather than left out of it. An ownership verdict with
no statement of its limit reads as proof, and this one is not proof.
"""


class BootRefused(RuntimeError):
    """The plan was not run, and the reason is not a boot failure."""


class BootAbandoned(RuntimeError):
    """Something failed after the images were placed, and the jail came down.

    Carries two failures rather than one, because they are two. ``original`` is
    what went wrong with the run. ``teardown`` is what happened when this module
    then took its own jail down, including any way that itself went wrong.

    Collapsing them into one string loses the case that matters most: a launch
    that failed *and* a chroot still sitting on the disk holding the work image.
    Read as a single sentence those are indistinguishable from a launch that
    failed and cleaned up after itself, and the second one is a policy breach
    while the first is a Tuesday.
    """

    def __init__(
        self, *, original: BaseException, teardown: Mapping[str, Any]
    ) -> None:
        self.original = original
        self.teardown = dict(teardown)
        finished = "finished" if self.teardown.get("clean") else "did not finish"
        super().__init__(
            f"the run failed after the images were placed "
            f"({type(original).__name__}: {original}), and the cleanup that "
            f"followed {finished}"
        )


def _run(argv: list[str], timeout: float = 300.0) -> subprocess.CompletedProcess:
    return subprocess.run(  # noqa: S603
        argv, check=False, capture_output=True, text=True, timeout=timeout
    )


def _a_pid_this_may_signal(raw: Any) -> tuple[int | None, str]:
    """The PID in ``raw`` if it is one this may signal, or why it is not.

    Four classes of value are turned away, and the first two are the reason this
    function exists at all rather than being an ``int()`` at the call site:

    ``0``
        ``kill(0, …)`` signals *this process's entire process group*, which
        includes the launcher. It is the one value that looks like a PID, passes
        every type check, and destroys the caller.
    negative
        ``kill(-n, …)`` signals process group ``n``; ``kill(-1, …)`` signals
        every process this user is permitted to signal. Both were measured on
        this host to return without raising, so nothing downstream notices.
    above :data:`PID_CEILING`
        the conversion to a C long fails before the kernel is reached, and it
        fails with ``OverflowError``, which is not an ``OSError``.
    unreadable
        a file the jailer was still writing, or one holding something that was
        never a number.
    """
    if raw is None or isinstance(raw, bool):
        return None, "the PID file held no readable PID"
    try:
        pid = int(str(raw).strip())
    except (TypeError, ValueError):
        return None, "the PID file held no readable PID"
    if pid == 0:
        return None, (
            "a PID of 0 means this process's whole group, which includes the "
            "launcher itself, so it is never signalled"
        )
    if pid < 0:
        return None, (
            "a negative PID names a process group rather than a process, and "
            "-1 is every process this user may signal"
        )
    if pid > PID_CEILING:
        return None, (
            f"a PID above {PID_CEILING} cannot be handed to the operating "
            "system on this platform, so nothing could be signalled by it"
        )
    return pid, ""


def _still_running(pid: int) -> bool:
    checked, why_not = _a_pid_this_may_signal(pid)
    if checked is None:
        # Unreachable from this module, which checks before it asks. Kept so
        # that it stays unreachable: a future caller gets an exception rather
        # than a probe of its own process group.
        raise ValueError(why_not)
    try:
        os.kill(checked, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _may_signal_now(pid_file: Path, watched: int) -> tuple[bool, str]:
    """Re-read the PID file at the moment of the signal, not before.

    The file this run watched appear can be replaced between then and the
    deadline — by a wrapper that re-execs, or by another run that found the same
    jail. What gets signalled has to be what was read, checked again now.
    """
    try:
        text = pid_file.read_text().strip()
    except OSError as failure:
        return False, (
            f"the PID file could not be re-read before signalling "
            f"({type(failure).__name__}: {failure}), so what it names now is "
            "unknown"
        )
    named_now, why_not = _a_pid_this_may_signal(text)
    if named_now is None:
        return False, f"the PID file no longer holds a usable PID: {why_not}"
    if named_now != watched:
        return False, (
            f"the PID file now names {named_now} rather than the {watched} this run "
            "watched appear, so it was replaced and this is not ours to stop"
        )
    return True, ""


def _confirm_it_stopped(
    pid: int,
    *,
    now: Callable[[], float],
    sleep: Callable[[float], None],
) -> bool:
    """Whether the machine actually went, watched on a finite deadline.

    Separate from whether a signal was sent, because they are separate
    observations and only one of them is evidence that the host is free again.
    """
    started = now()
    while now() - started < STOP_CONFIRMATION_SECONDS:
        if not _still_running(pid):
            return True
        sleep(CONFIRMATION_POLL_SECONDS)
    return not _still_running(pid)


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

    A third case sits between those two: the plan was fine and the machine never
    got far enough to produce a finding, because the jailer was not installed or
    took longer than its own cap or the image could not be read back. Those
    raise :class:`BootAbandoned` — but not before this run's own jail, and this
    run's own process, are taken down. Until 2026-09-14 they raised straight out
    of here and left the chroot behind, which is where the work disk lives.

    And one refusal is about neither the plan nor the machine: a jail that was
    already on disk under the name this plan uses. That is another run's, and
    this one does not start on top of it. See the comment at the check.
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
    chroot_named = Path(str(host_side["chroot_dir"]))
    deadline_seconds = float(host_side["deadline_seconds"])

    # Read before this run creates anything, and never read again.
    chroot_was_already_there = chroot_named.exists()
    pid_file_was_already_there = pid_file.exists()

    if chroot_was_already_there or pid_file_was_already_there:
        # Refused here, before anything is placed, because by the time the
        # deadline fires it is already too late for the two worse things.
        #
        # The plan puts the PID file *inside* the chroot and names the chroot as
        # the thing to remove afterwards. So a jail that was already on disk
        # holds another run's live work disk and another run's PID, and carrying
        # on would copy this run's images over that disk, chown it, and then
        # remove the whole jail out from under a running machine. Signalling a
        # stranger's process is the smallest of the three.
        #
        # Two runs arrive at one jail by an ordinary route, not an exotic one:
        # ``--run-id``'s own help says "Reuse it to resume", the per-call
        # counter restarts at zero on a fresh process, and the machine name is
        # built from the two. A resumed run therefore lands on call 0000's jail
        # by design.
        #
        # Nothing about a directory that was already here says whose it is. It
        # could be this run's own wreckage from a crash, and it could be a live
        # machine; the host offers no way to tell those apart from here. So this
        # refuses and says so, rather than guessing in the direction that
        # happens to let the run continue.
        raise BootRefused(
            "this plan's jail is already on disk "
            f"(chroot {'present' if chroot_was_already_there else 'absent'}, "
            f"PID file {'present' if pid_file_was_already_there else 'absent'}: "
            f"{chroot_named}), so it holds another run's work disk and PID file. "
            "Placing this run's images there would overwrite them and removing "
            "it afterwards would take that run's jail down while it is using "
            "it. Nothing here establishes that it is this run's, so this run "
            "does not start. Resuming a run id reuses the machine name, which "
            "is how two runs reach one jail."
        )

    salvage: dict[str, Any] = {
        "returned_copy": None,
        "results_read": False,
        "copied_while_running": False,
    }
    grounds: list[dict[str, Any]] = []

    try:
        placement = place_the_images(
            plan, kernel=kernel, rootfs=rootfs, work_disk=work_disk, uid=uid, gid=gid
        )
        chroot_dir = Path(placement["chroot_dir"])

        started_at = now()
        launch = _run([jailer_binary, *plan["jailer"]["argv"]], timeout=120.0)

        # ``watched`` is the only value this run will ever signal, and it is set
        # once, here, from a file that did not exist a moment ago.
        watched: int | None = None
        why_not_this_pid = "no PID file appeared, so nothing started"
        while now() - started_at < PID_FILE_GRACE_SECONDS:
            if pid_file.exists():
                try:
                    text = pid_file.read_text().strip()
                except OSError as unreadable:
                    why_not_this_pid = (
                        f"the PID file could not be read "
                        f"({type(unreadable).__name__}: {unreadable})"
                    )
                else:
                    watched, why_not_this_pid = _a_pid_this_may_signal(text)
                    if watched is not None:
                        break
            sleep(POLL_SECONDS)

        # What this run can actually say about whose process that is. Written
        # down as the separate things it checked rather than as one boolean,
        # because a verdict nobody can audit is how "the PID file was not there"
        # came to stand in for ownership in the first place.
        grounds = [
            {
                "ground": "the jail did not exist before this run placed anything",
                "held": not chroot_was_already_there,
            },
            {
                "ground": "no PID file was there before this run launched",
                "held": not pid_file_was_already_there,
            },
            {
                "ground": "a PID file appeared while this run was watching",
                "held": watched is not None,
            },
            {
                "ground": "it held a value this platform can signal",
                "held": watched is not None,
            },
        ]

        outcome = "booted"
        stopped_by_the_deadline = False
        stop_signal_sent = False
        guest_confirmed_stopped: bool | None = None
        left_alone_because: str | None = None

        if watched is None:
            outcome = "never_started"
            left_alone_because = why_not_this_pid
        else:
            while _still_running(watched):
                if now() - started_at < deadline_seconds:
                    sleep(POLL_SECONDS)
                    continue
                may_signal, why_not_now = _may_signal_now(pid_file, watched)
                if not may_signal:
                    # The deadline is reached and the thing at the end of it is
                    # not demonstrably ours. Leaving a machine running is bad;
                    # killing a stranger's is worse and is not recoverable.
                    outcome = "overran_and_was_left_alone"
                    left_alone_because = why_not_now
                    break
                try:
                    os.kill(watched, signal.SIGKILL)
                except ProcessLookupError:
                    # It went on its own between the probe and the signal.
                    outcome = "booted"
                    break
                stop_signal_sent = True
                guest_confirmed_stopped = _confirm_it_stopped(
                    watched, now=now, sleep=sleep
                )
                if guest_confirmed_stopped:
                    stopped_by_the_deadline = True
                    outcome = "stopped_by_the_deadline"
                else:
                    # A signal was sent and the machine is still there. Saying
                    # it was stopped by the deadline would be the artefact
                    # asserting something nobody observed.
                    outcome = "overran_and_did_not_stop"
                break
        ran_for = round(now() - started_at, 3)

        disk_in_jail = chroot_dir / "work.ext4"
        results: dict[str, str | None] = {}
        if disk_in_jail.exists():
            # The copy first, the reading second, and that order is not
            # interchangeable. This copy is the only place the guest's writes
            # still exist once the jail is gone; reading the files out of the
            # image is a convenience on top of it. Reading first meant an image
            # this module could not parse took the bytes down with it.
            #
            # Both of those come *after* the machine is stopped, because a
            # filesystem copied out from under a running guest is a torn one.
            # It is still taken — it is the only copy there will be — and it is
            # labelled, so that nothing downstream reads it as intact.
            returned = str(work_disk) + ".returned"
            shutil.copy2(disk_in_jail, returned)
            salvage["returned_copy"] = returned
            salvage["copied_while_running"] = guest_confirmed_stopped is False
            results = files_out_of_work_disk(disk_in_jail, WORK_DISK_RESULTS)
            salvage["results_read"] = True
    except BaseException as failure:
        teardown = _clean_up_after_a_failure(
            host_side=host_side,
            pid_file=pid_file,
            pid_file_was_already_there=pid_file_was_already_there,
            chroot_was_already_there=chroot_was_already_there,
            work_disk=work_disk,
            salvage=salvage,
            now=now,
            sleep=sleep,
        )
        # KeyboardInterrupt and SystemExit are cleaned up after and then left
        # alone. Wrapping them would turn a stop into a RuntimeError nobody
        # asked for; not cleaning up after them would leak the jail on Ctrl-C.
        if isinstance(failure, Exception):
            raise BootAbandoned(original=failure, teardown=teardown) from failure
        raise

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
            "appeared": watched is not None,
            "pid_recorded": watched is not None,
            "pid_watched": watched,
            "owned_by_this_run": watched is not None and left_alone_because is None,
            "ownership_grounds": grounds,
            "left_alone_because": left_alone_because,
            "cannot_rule_out": CANNOT_RULE_OUT,
        },
        "ran_for_seconds": ran_for,
        "deadline_seconds": deadline_seconds,
        "stopped_by_the_deadline": stopped_by_the_deadline,
        # Sent and gone are two observations. Only the second one says the host
        # is free again, and only the first one was ever being recorded.
        "stop_signal_sent": stop_signal_sent,
        "guest_confirmed_stopped": guest_confirmed_stopped,
        "command_exit_status": exit_status,
        "results": results,
        "salvaged": salvage,
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

    **Only the paths the plan named.** No glob, no parent directory, nothing
    derived from a naming convention. A run that cleans up by pattern cleans up
    after other runs too, and the plan is hash-checked on the way in while a
    pattern invented here is not.

    A removal that fails now carries its reason instead of leaving a reader to
    infer one from the path still being there. "Still there" and "still there
    because the directory is not writable" are the same boolean and different
    findings. ``onerror`` rather than ``onexc``: this runs on Python 3.10.
    """
    gone: dict[str, bool] = {}
    failures: list[dict[str, str]] = []

    def _note_it(_function: Any, path: Any, excinfo: Any) -> None:
        failures.append(
            {
                "what": "remove",
                "path": str(path),
                "error": f"{type(excinfo[1]).__name__}: {excinfo[1]}",
            }
        )

    for path in paths:
        # Absent already is not a failure, and was not one under ignore_errors
        # either. Handing rmtree a missing path would report one.
        if Path(path).exists():
            shutil.rmtree(path, onerror=_note_it)
        gone[path] = not Path(path).exists()
    return {
        "removed": gone,
        "all_gone": all(gone.values()) if gone else False,
        "failures": failures,
    }


def _clean_up_after_a_failure(
    *,
    host_side: Mapping[str, Any],
    pid_file: Path,
    pid_file_was_already_there: bool,
    work_disk: str | Path,
    salvage: dict[str, Any],
    chroot_was_already_there: bool = False,
    now: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Take down what this run started, in the order that keeps the results.

    Four obligations, and the order is the whole point:

    1. the machine is stopped, and stopping is followed by *asking whether it
       stopped*, because a signal that was sent is not a process that is gone;
    2. the work disk comes out of the jail, after the writer has stopped and
       before the jail is removed — the copy beside it is the only place the
       guest's writes still exist, and a filesystem copied out from under a
       running guest is a torn one;
    3. the jail is removed, because ``workdir: ephemeral-quota`` is a policy and
       not tidiness;
    4. nothing here touches a path or a process this run did not create.

    The fourth is the one worth stating as a rule, and the one that is easiest
    to get wrong in the safe-looking direction. A process is signalled only when
    every ground in ``ownership_grounds`` held: the jail was not on disk before
    this run placed anything, no PID file was there before it launched, one
    appeared while it was watching, and the value in it is one this platform can
    signal. The jail being there first is the strongest of those, because the
    plan puts the PID file *inside* the chroot — a jail that predates this run
    holds another run's PID file and another run's work disk.

    None of that rules out PID reuse, and this does not claim it does; see
    :data:`CANNOT_RULE_OUT`, which goes out with the record.

    Failures are collected, never raised, and now that means **every**
    ``Exception`` rather than the two that were anticipated. This runs while
    another exception is already on its way out; anything raised from in here
    would replace the reason the run failed with the reason the cleanup failed,
    and would do it before ``BootAbandoned`` was ever constructed — so the
    original error, the salvaged path and this record would all be lost at once.
    ``KeyboardInterrupt`` and ``SystemExit`` are not caught: a Ctrl-C during
    cleanup should stop, not be filed as a teardown failure.
    """
    failures: list[dict[str, str]] = []

    def _collect(what: str, path: str, failure: BaseException) -> None:
        failures.append(
            {
                "what": what,
                "path": path,
                "error": f"{type(failure).__name__}: {failure}",
            }
        )

    # Derived from the plan rather than from however far the caller got, so a
    # placement that failed half way through still has its jail found.
    chroot_dir = Path(str(host_side["chroot_dir"]))

    # ---- 1. stop it, if it is this run's to stop -------------------------
    process: dict[str, Any] = {
        "pid_file": pid_file.as_posix(),
        "existed_before_this_run": pid_file_was_already_there,
        "chroot_existed_before_this_run": chroot_was_already_there,
        "pid": None,
        "signalled": False,
        "was_running": None,
        "confirmed_stopped": None,
        "left_alone_because": None,
        "cannot_rule_out": CANNOT_RULE_OUT,
    }
    try:
        if chroot_was_already_there:
            process["left_alone_because"] = (
                "the jail was on disk before this run placed anything, so the "
                "PID file inside it and the machine it names are another run's, "
                "and this run does not stop another run's machine"
            )
        elif pid_file_was_already_there:
            process["left_alone_because"] = (
                "this PID file was there before this run launched anything, so "
                "whatever it names is not this run's to kill"
            )
        elif not pid_file.exists():
            process["left_alone_because"] = "no PID file appeared, so nothing started"
        else:
            try:
                text: Any = pid_file.read_text().strip()
            except OSError as unreadable:
                text = None
                process["left_alone_because"] = "the PID file could not be read"
                _collect("read this run's PID file", pid_file.as_posix(), unreadable)
            if text is not None:
                pid, why_not = _a_pid_this_may_signal(text)
                if pid is None:
                    process["left_alone_because"] = why_not
                else:
                    process["pid"] = pid
                    running = _still_running(pid)
                    process["was_running"] = running
                    if not running:
                        process["confirmed_stopped"] = True
                        process["left_alone_because"] = "it had already stopped"
                    else:
                        os.kill(pid, signal.SIGKILL)
                        process["signalled"] = True
                        stopped = _confirm_it_stopped(pid, now=now, sleep=sleep)
                        process["confirmed_stopped"] = stopped
                        if not stopped:
                            failures.append(
                                {
                                    "what": "confirm this run's machine stopped",
                                    "path": pid_file.as_posix(),
                                    "error": (
                                        "SIGKILL was sent and the process was "
                                        f"still there {STOP_CONFIRMATION_SECONDS}s "
                                        "later; sent is not stopped"
                                    ),
                                }
                            )
    except Exception as failure:  # noqa: BLE001 - the docstring is the contract
        _collect("stop this run's machine", pid_file.as_posix(), failure)

    # ---- 2. get the bytes out, now that the writer has stopped -----------
    try:
        if chroot_was_already_there:
            salvage["why_not"] = (
                "the jail was there before this run, so the disk inside it is "
                "another run's and this run does not copy it out"
            )
        elif salvage.get("returned_copy") is None:
            disk_in_jail = chroot_dir / "work.ext4"
            if not disk_in_jail.exists():
                salvage["why_not"] = "no work disk reached the jail"
            else:
                returned = str(work_disk) + ".returned"
                try:
                    shutil.copy2(disk_in_jail, returned)
                    salvage["returned_copy"] = returned
                except OSError as failure:
                    salvage["why_not"] = "the work disk could not be copied out"
                    _collect("copy the work disk out of the jail", returned, failure)
    except Exception as failure:  # noqa: BLE001 - the docstring is the contract
        _collect("copy the work disk out of the jail", chroot_dir.as_posix(), failure)

    # Whether anyone may read that copy as an intact filesystem. Taken from what
    # was observed a moment ago rather than from whether a signal was sent: the
    # guest was running when this looked, and nothing since has said it stopped.
    salvage["copied_while_running"] = bool(
        salvage.get("returned_copy") is not None
        and process["was_running"] is True
        and process["confirmed_stopped"] is not True
    )

    # ---- 3. remove the jail, if it is this run's to remove ---------------
    destroyed: dict[str, Any] = {"removed": {}, "all_gone": False, "failures": []}
    refused_to_destroy: str | None = None
    if chroot_was_already_there:
        refused_to_destroy = (
            "the jail was on disk before this run placed anything; removing it "
            "would take another run's work disk with it"
        )
    else:
        try:
            destroyed = _destroy(list(host_side.get("destroy_after_the_run", [])))
        except Exception as failure:  # noqa: BLE001 - the docstring is the contract
            _collect("remove", chroot_dir.as_posix(), failure)
    failures.extend(destroyed["failures"])

    return {
        "after_a_failure": True,
        "removed": destroyed["removed"],
        "all_gone": destroyed["all_gone"],
        "destroy_refused_because": refused_to_destroy,
        "failures": failures,
        "clean": not failures,
        "process": process,
        "salvaged": salvage,
    }


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
            "boot_args": (
                "console=ttyS0 reboot=k panic=1 pci=off root=/dev/vda ro "
                f"init={GUEST_INIT_PATH}"
            ),
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
