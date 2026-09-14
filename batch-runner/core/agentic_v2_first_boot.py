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
import uuid
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

CLAIM_FILE_NAME = ".owned-by.json"
"""Where a run writes down that this jail's name is its own.

Inside the chroot rather than beside it, so the record and the thing it records
are one object with one lifetime. ``destroy_after_the_run`` already names the
chroot, so the record goes when the jail goes, and there is no state in which a
claim outlives the jail it claims or a jail exists with its claim swept out
from under it.

The guest never sees this. The jailer chroots Firecracker here, but the guest's
filesystem is ``rootfs.ext4`` — a separate image, attached as a block device —
so this file is visible to the jailed host process and to nothing inside the
machine.
"""

CLAIM_DOES_NOT_ESTABLISH = (
    "whether the process a claim names is still alive. The PID, the boot id and "
    "the process start time are written down so a person can look; nothing here "
    "reads them back, and no path reclaims a jail because its claim looks stale. "
    "A claim that is not this run's is a refusal, not a puzzle to solve. " +
    CANNOT_RULE_OUT
)
"""The limit of the claim, carried inside every claim.

Taking a name atomically settles who may write into it. It does not settle what
is happening inside it, and the distance between those two is exactly where a
convenient inference would go: *this claim is hours old, so surely nobody is
using it*. There is no evidence for the *surely*, so nothing acts on it.
"""

OUTCOMES_THAT_LEAVE_THE_HOST_RUNNING = frozenset(
    {"overran_and_was_left_alone", "overran_and_did_not_stop"}
)
"""Outcomes after which a machine this run launched is still on the host.

Named here, beside the code that produces them, because this vocabulary has
already grown once — from four outcomes to six — while the module that reads it
still knew four, and the two new ones fell through into the ordinary-success
branch. A consumer that imports this set finds out when it grows again; one that
spells the strings out for itself does not.
"""

COPY_INTACT = "intact"
COPY_TORN = "torn"
COPY_UNVERIFIED = "unverified"
COPY_ABSENT = "no_copy"
"""How far a returned work-disk copy may be trusted, as four named states.

A string rather than a boolean, and that is the point. ``copied_while_running``
is three-valued — the guest was seen running, seen gone, or never looked at —
and every boolean spelling of it rounds the third case into one of the first
two. ``None is False`` is ``False``, so "never checked" recorded itself as "not
copied while running", which is the safe-looking direction and the wrong one.
Nothing reads a missing key or a ``None`` as :data:`COPY_INTACT` by accident.
"""


def _how_intact_is_the_copy(
    *,
    a_copy_was_taken: bool,
    last_seen_running: bool | None,
    confirmed_stopped: bool | None,
) -> dict[str, Any]:
    """Say whether a returned copy may be read as an intact filesystem.

    Both call sites in this module go through here, because both had the same
    defect in different clothes and fixing one of them would have left the other
    saying the opposite thing about the same host.

    Three inputs, not one. Whether there is a copy at all; what this run last
    *observed* about the writer; and whether a stop was confirmed. The second is
    the one that was missing: a signal that was never sent is not evidence the
    guest was gone, and a guest that exited on its own was never signalled. Read
    only ``confirmed_stopped`` and those two cases are indistinguishable, which
    is how the ordinary boot and the machine nobody could stop came to be
    labelled the same way.

    ``last_seen_running=None`` means no process was ever looked at — the PID file
    never appeared, or it named something this run refused to claim. That is not
    "nothing was writing"; see :data:`CANNOT_RULE_OUT`. It is recorded as
    unverified, and unverified never reads as intact.
    """
    if not a_copy_was_taken:
        return {
            "copied_while_running": None,
            "copy_integrity": COPY_ABSENT,
            "copy_integrity_because": "no copy of the work disk was returned",
        }
    if confirmed_stopped is True:
        return {
            "copied_while_running": False,
            "copy_integrity": COPY_INTACT,
            "copy_integrity_because": (
                "the guest was signalled and confirmed gone before the copy was "
                "taken"
            ),
        }
    if last_seen_running is False:
        return {
            "copied_while_running": False,
            "copy_integrity": COPY_INTACT,
            "copy_integrity_because": (
                "the guest was observed to have stopped before the copy was "
                "taken, so nothing was writing to the disk"
            ),
        }
    if last_seen_running is True:
        return {
            "copied_while_running": True,
            "copy_integrity": COPY_TORN,
            "copy_integrity_because": (
                "the guest was still running when the copy was taken"
                if confirmed_stopped is None
                else "the guest was signalled and was still running "
                f"{STOP_CONFIRMATION_SECONDS:g}s later, so the copy was taken "
                "out from under a live writer"
            ),
        }
    return {
        "copied_while_running": None,
        "copy_integrity": COPY_UNVERIFIED,
        "copy_integrity_because": (
            "no process was ever observed for this run, so nothing here says "
            "whether anything was writing to the disk when it was copied"
        ),
    }


def the_host_was_left_running(boot: Mapping[str, Any]) -> bool:
    """Whether a machine this run launched is still on the host afterwards.

    Separate from what the command did and from what the copy is worth. A
    command can finish with a returncode of 0 in a guest that then refuses to
    shut down, and all three of those are true at once; folding them into one
    answer is how a leaked machine reached the model as an ordinary success.

    ``guest_confirmed_stopped is False`` is included because it is the same
    state reached by a different route: a signal went out and the process was
    still there afterwards.
    """
    return (
        boot.get("outcome") in OUTCOMES_THAT_LEAVE_THE_HOST_RUNNING
        or boot.get("guest_confirmed_stopped") is False
    )


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


def _may_signal_now(
    pid_file: Path, watched: int, *, chroot_dir: Path, claim: Mapping[str, Any]
) -> tuple[bool, str]:
    """Re-read the PID file at the moment of the signal, not before.

    The file this run watched appear can be replaced between then and the
    deadline — by a wrapper that re-execs, or by another run that found the same
    jail. What gets signalled has to be what was read, checked again now.

    The jail's ownership record is re-read here too, and for the same reason
    rather than a different one. A PID file that still holds the watched number
    says the number did not change; it does not say the jail around it is still
    this run's. Both questions are asked at the moment of the signal because
    that is the moment their answers are used.
    """
    held, why = _this_run_still_holds_it(chroot_dir, claim)
    if not held:
        return False, (
            f"{why}, so the process its PID file names is not this run's to stop"
        )
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


def _who_this_process_is() -> dict[str, Any]:
    """Enough about this process to tell it apart from one that reuses its number.

    Every field is allowed to be missing. This has to work where ``/proc`` is
    not what it is on Linux, and a field that could not be read is written down
    as ``None`` rather than guessed. None of it is read back by any code path
    here — see :data:`CLAIM_DOES_NOT_ESTABLISH`. It is written so a person
    holding a stuck jail has something to go on.
    """
    boot_id: str | None = None
    started_at: int | None = None
    try:
        boot_id = Path("/proc/sys/kernel/random/boot_id").read_text().strip() or None
    except OSError:
        pass
    try:
        stat = Path("/proc/self/stat").read_text()
        # Field 22 is starttime. Field 2 is the command name, which may itself
        # contain spaces and brackets, so the fields are counted from after the
        # last ')' — where field 3 begins, making starttime index 19.
        started_at = int(stat[stat.rindex(")") + 1:].split()[19])
    except (OSError, ValueError, IndexError):
        pass
    return {"pid": os.getpid(), "boot_id": boot_id, "process_started_at": started_at}


def _read_the_claim(chroot_dir: Path) -> tuple[dict[str, Any] | None, str]:
    """What a jail says about who owns it, and how that reads in a sentence.

    Four answers, kept apart rather than collapsed: a claim, no claim at all, a
    claim that could not be read, and a file that is there but is not a claim.
    Every one of them is a refusal upstream. **None of them is "unowned, help
    yourself."** A jail carrying no ownership record is the case this code knows
    *least* about — it may predate this file, or be a crashed run's wreckage, or
    hold a machine that is running right now — and reading least-known as free
    is the exact shape of the defect this replaces, wearing different clothes.
    """
    record = chroot_dir / CLAIM_FILE_NAME
    try:
        raw = record.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None, (
            "It carries no ownership record at all, which says nothing about "
            "whether it is free."
        )
    except OSError as unreadable:
        return None, (
            "Its ownership record could not be read "
            f"({type(unreadable).__name__}: {unreadable})."
        )
    try:
        claim = json.loads(raw)
    except json.JSONDecodeError as malformed:
        return None, f"Its ownership record is not readable JSON ({malformed})."
    if not isinstance(claim, dict) or not isinstance(claim.get("nonce"), str):
        return None, (
            "Its ownership record has no nonce, so there is nothing to match "
            "against it."
        )
    return claim, (
        f"It is claimed for vm_id {claim.get('vm_id')!r} by PID "
        f"{claim.get('claimed_by', {}).get('pid')}, nonce {claim['nonce'][:8]}."
    )


def claim_the_jail(
    chroot_dir: Path, *, vm_id: str, plan_sha256: str
) -> dict[str, Any]:
    """Take this jail's name for this run, atomically, before anything is in it.

    One ``mkdir(2)`` decides it. The directory either did not exist and now does
    and is this run's, or it existed and this run is told so — the kernel makes
    that choice once, for everybody, with no window between asking and taking.

    What this replaces was two operations with a gap: an ``exists()`` read near
    the top of :func:`first_boot`, and a ``mkdir(exist_ok=True)`` further down
    inside :func:`place_the_images`. Two runs of the same ``vm_id`` could both
    read *absent* in that gap and both go on, and ``exist_ok=True`` meant the
    second one succeeded too. That is not a theoretical width: on this host, 19
    of 20 unforced pairs got through together, and both members of each pair
    then launched, placed images into the one jail, copied the one work disk out
    and removed the one directory.

    **Winning is written down, not remembered.** ``nonce`` is a value only the
    winner holds, and every later step that would touch this jail re-reads the
    file and compares rather than trusting a boolean carried down from here. A
    boolean reports what was true when it was set; the file reports what is true
    at the moment of the question, and those differ in exactly the case that
    matters.

    Raises :class:`BootRefused` if the name is taken, and quotes what the other
    claim says if it can be read. It does not act on that content and does not
    remove anything: see :data:`CLAIM_DOES_NOT_ESTABLISH`.
    """
    try:
        chroot_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        _, how_it_reads = _read_the_claim(chroot_dir)
        raise BootRefused(
            f"the jail this plan names is already on disk ({chroot_dir}), so "
            "the name is not this run's to take. It holds another run's images, "
            "work disk and PID file: placing this run's images there would "
            "overwrite them, and removing it afterwards would take that jail "
            f"down while it is in use. {how_it_reads} This run creates nothing "
            "and starts nothing. Two runs reach one jail by sharing a vm_id, "
            "which is what resuming a run id does."
        ) from None

    claim = {
        "schema_version": "1.0",
        "vm_id": vm_id,
        "plan_sha256": plan_sha256,
        "nonce": uuid.uuid4().hex,
        "claimed_at_unix": time.time(),
        "claimed_by": _who_this_process_is(),
        "does_not_establish": CLAIM_DOES_NOT_ESTABLISH,
    }
    record = chroot_dir / CLAIM_FILE_NAME
    record.write_text(json.dumps(claim, indent=2, sort_keys=True), encoding="utf-8")
    os.chmod(record, 0o444)

    # Read it back before anything is placed. If what is on disk is not what was
    # just written, every ownership question downstream would be comparing
    # against a value that was never there, and the first moment anyone would
    # find out is the moment the jail is being torn down.
    written_back, how_it_reads = _read_the_claim(chroot_dir)
    if written_back is None or written_back.get("nonce") != claim["nonce"]:
        raise BootRefused(
            "this run created the jail and then could not read its own "
            f"ownership record back out of it. {how_it_reads} Nothing "
            "downstream could prove the jail is this run's, so nothing is "
            "placed and nothing is started. The directory is left exactly as "
            "it is rather than removed on the strength of an ownership claim "
            "that just failed to hold."
        )
    return claim


def _this_run_still_holds_it(
    chroot_dir: Path, claim: Mapping[str, Any]
) -> tuple[bool, str]:
    """Re-read the evidence now, instead of trusting a flag set earlier.

    Called again at every step that would act on the jail — placing images,
    signalling, copying the disk out, removing the directory — because what
    those steps need to know is whether the jail is this run's *now*, and a
    value read at the top of the run answers whether it was this run's *then*.
    """
    on_disk, how_it_reads = _read_the_claim(chroot_dir)
    if on_disk is None:
        return False, (
            f"the jail no longer carries this run's ownership record. {how_it_reads}"
        )
    if on_disk.get("nonce") != claim.get("nonce"):
        return False, (
            f"the jail carries an ownership record this run did not write. "
            f"{how_it_reads}"
        )
    return True, "the jail still carries the ownership record this run wrote"


def _give_back_an_unused_claim(chroot_dir: Path, claim: Mapping[str, Any]) -> str:
    """Hand back a name this run took and then decided not to use.

    Reachable only between taking the claim and putting the first thing in the
    jail, and guarded twice over. The record must still be this run's, and the
    removal is ``rmdir`` rather than ``rmtree`` — so if anything at all got in
    there, the kernel refuses and this reports that instead of deleting it. A
    shortcut here (*we made it a moment ago, so it must be empty*) would be the
    one removal in this module standing on an assumption rather than evidence.

    The record has to come out before the directory can, which opens a gap: a
    handback that gets as far as the ``rmdir`` and is refused there would leave
    the jail standing with its ownership record already gone. Nothing would then
    be able to say whose that jail is — not even the run that made it — so the
    record is put back. Everything downstream reads a jail with no record as a
    refusal, which is the safe direction, but it is also the *uninformative*
    one, and this is the one place where the informative answer is still known.
    """
    record = chroot_dir / CLAIM_FILE_NAME
    held, why = _this_run_still_holds_it(chroot_dir, claim)
    if not held:
        return f"left as it is, because {why}"
    written = record.read_text(encoding="utf-8")
    try:
        record.unlink()
        chroot_dir.rmdir()
    except OSError as failure:
        put_back = "and its ownership record is back where it was"
        try:
            record.write_text(written, encoding="utf-8")
            os.chmod(record, 0o444)
        except OSError as restore_failed:
            put_back = (
                "and its ownership record could not be put back "
                f"({type(restore_failed).__name__}: {restore_failed}), so nothing "
                "on disk now says whose jail this is"
            )
        return (
            "could not be handed back "
            f"({type(failure).__name__}: {failure}), so it is left as it is {put_back}"
        )
    return "handed back empty, for whoever asks for the name next"


def place_the_images(
    plan: Mapping[str, Any],
    *,
    claim: Mapping[str, Any],
    kernel: str | Path,
    rootfs: str | Path,
    work_disk: str | Path,
    uid: int,
    gid: int,
) -> dict[str, Any]:
    """Put each image where ``place_in_jail`` says, with the mode it says.

    The directory is not created here any more. :func:`claim_the_jail` created
    it exclusively before this was called, and this refuses unless the record
    that call wrote is still the one in it. Ordering used to be a property of
    where the lines sat in the file, which nothing checked; now the later step
    asks, so ``claim`` is required and has no default.

    Ownership follows the plan's ``writable_by_the_jailed_user`` rather than a
    convention: the two images the guest must not change are ``0444`` and owned
    by root, and only the work disk is writable by the account the jailer drops
    to. A rootfs the jailed user can write to would make ``rootfs: read-only``
    true only for as long as the guest chose to respect it.
    """
    chroot_dir = Path(plan["host_side"]["chroot_dir"])
    held, why = _this_run_still_holds_it(chroot_dir, claim)
    if not held:
        raise BootRefused(
            f"nothing is placed in this jail because {why}. Images written into "
            "a jail this run does not hold would land on another run's work "
            "disk and rootfs."
        )
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

    And one refusal is about neither the plan nor the machine: a jail whose name
    is already taken. That name is taken here, by :func:`claim_the_jail`, in one
    atomic step before anything is placed or launched, and a run that does not
    get it does not start. See the comment at the claim.
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

    # The name is taken before anything is placed and before any PID is looked
    # at, and taking it is one operation rather than a look followed by a leap.
    #
    # It has to come first because by the time the deadline fires it is already
    # too late for the two worse things. The plan puts the PID file *inside* the
    # chroot and names the chroot as the thing to remove afterwards. So a jail
    # that is already on disk holds another run's live work disk and another
    # run's PID, and carrying on would copy this run's images over that disk,
    # chown it, and then remove the whole jail out from under a running machine.
    # Signalling a stranger's process is the smallest of the three.
    #
    # Two runs arrive at one jail by an ordinary route, not an exotic one:
    # ``--run-id``'s own help says "Reuse it to resume", the per-call counter
    # restarts at zero on a fresh process, and the machine name is built from
    # the two. A resumed run therefore lands on call 0000's jail by design.
    #
    # Nothing about a directory that was already here says whose it is. It could
    # be this run's own wreckage from a crash, and it could be a live machine;
    # the host offers no way to tell those apart from here. So this refuses and
    # says so, rather than guessing in the direction that happens to let the run
    # continue — and it does not delete the thing in its way, because a run that
    # clears an obstacle it cannot identify is the failure it was meant to stop.
    claim = claim_the_jail(
        chroot_named, vm_id=str(plan["vm_id"]), plan_sha256=str(plan["plan_sha256"])
    )

    if pid_file.exists():
        # Unreachable for a plan that puts the PID file inside the chroot, since
        # that directory did not exist a moment ago. Kept because the check is
        # about the file this run will signal, not about where the builder
        # happens to put it, and a guard that holds only under today's layout is
        # one nobody notices breaking.
        handed_back = _give_back_an_unused_claim(chroot_named, claim)
        raise BootRefused(
            f"a PID file was already at {pid_file} before this run launched "
            "anything, so it names a process this run did not start and must "
            "not signal, and the deadline path has no way to tell it from one "
            f"this run started. Nothing was placed and nothing was started; the "
            f"jail this run had just claimed was {handed_back}."
        )

    salvage: dict[str, Any] = {
        "returned_copy": None,
        "results_read": False,
        **_how_intact_is_the_copy(
            a_copy_was_taken=False, last_seen_running=None, confirmed_stopped=None
        ),
    }
    grounds: list[dict[str, Any]] = []

    try:
        placement = place_the_images(
            plan,
            claim=claim,
            kernel=kernel,
            rootfs=rootfs,
            work_disk=work_disk,
            uid=uid,
            gid=gid,
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
        #
        # The first ground is the load-bearing one and it is a question asked
        # *now*, against the disk, rather than a flag set at the top of the run.
        # Its predecessor — "the jail did not exist before this run placed
        # anything" — was a boolean holding the result of one ``exists()`` call,
        # and two concurrent runs both got ``False`` from it and both recorded
        # the ground as held.
        still_ours, still_ours_why = _this_run_still_holds_it(chroot_named, claim)
        grounds = [
            {
                "ground": (
                    "the ownership record this run wrote is still the one in the jail"
                ),
                "held": still_ours,
                "reading": still_ours_why,
            },
            {
                "ground": "no PID file was there before this run launched",
                "held": True,
                "reading": (
                    "checked against the disk before anything was placed; a run "
                    "that found one there did not reach this point"
                ),
            },
            {
                "ground": "a PID file appeared while this run was watching",
                "held": watched is not None,
            },
            {
                "ground": "it held a value this platform can signal",
                # A different question from the one above, and it has to be
                # asked separately or the fourth ground is the third ground
                # written twice. ``watched`` is only ever set from
                # ``_a_pid_this_may_signal``, so re-checking the range here is
                # belt and braces — but a ground nobody can fail is not
                # evidence, and this list is offered as evidence.
                "held": watched is not None and 0 < watched <= PID_CEILING,
            },
        ]

        outcome = "booted"
        stopped_by_the_deadline = False
        stop_signal_sent = False
        guest_confirmed_stopped: bool | None = None
        # What this run last *observed* about the writer, which is not the same
        # question as whether it sent a signal. None until something is looked
        # at; False once it has been seen gone; True while it is still there.
        guest_last_seen_running: bool | None = None
        left_alone_because: str | None = None

        if watched is None:
            outcome = "never_started"
            left_alone_because = why_not_this_pid
        else:
            while _still_running(watched):
                guest_last_seen_running = True
                if now() - started_at < deadline_seconds:
                    sleep(POLL_SECONDS)
                    continue
                may_signal, why_not_now = _may_signal_now(
                    pid_file, watched, chroot_dir=chroot_named, claim=claim
                )
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
                    guest_last_seen_running = False
                    break
                stop_signal_sent = True
                guest_confirmed_stopped = _confirm_it_stopped(
                    watched, now=now, sleep=sleep
                )
                if guest_confirmed_stopped:
                    stopped_by_the_deadline = True
                    guest_last_seen_running = False
                    outcome = "stopped_by_the_deadline"
                else:
                    # A signal was sent and the machine is still there. Saying
                    # it was stopped by the deadline would be the artefact
                    # asserting something nobody observed.
                    outcome = "overran_and_did_not_stop"
                break
            else:
                # The loop condition went false, so the guest is gone. This is
                # the ordinary end of a boot and it is also the case that a
                # ``confirmed_stopped``-only reading cannot tell apart from a
                # machine nobody managed to stop: neither one was signalled.
                guest_last_seen_running = False
        ran_for = round(now() - started_at, 3)

        disk_in_jail = chroot_dir / "work.ext4"
        results: dict[str, str | None] = {}
        still_ours_at_the_copy, why_not_ours = _this_run_still_holds_it(
            chroot_named, claim
        )
        if not still_ours_at_the_copy:
            # Asked again here rather than inherited from the check above,
            # because a disk that is no longer in this run's jail is no longer
            # this run's to read. Copying it out would put another run's bytes
            # under this run's result path, which is worse than having no copy:
            # a missing copy is visibly missing, and a stranger's copy is not.
            salvage["why_not"] = (
                f"no copy was taken because {why_not_ours}, so the work disk in "
                "that jail is not this run's to read"
            )
        elif disk_in_jail.exists():
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
            salvage.update(
                _how_intact_is_the_copy(
                    a_copy_was_taken=True,
                    last_seen_running=guest_last_seen_running,
                    confirmed_stopped=guest_confirmed_stopped,
                )
            )
            results = files_out_of_work_disk(disk_in_jail, WORK_DISK_RESULTS)
            salvage["results_read"] = True
    except BaseException as failure:
        teardown = _clean_up_after_a_failure(
            host_side=host_side,
            pid_file=pid_file,
            claim=claim,
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

    destroyed = _destroy_unless_something_is_still_running(
        host_side.get("destroy_after_the_run", []),
        outcome=outcome,
        guest_confirmed_stopped=guest_confirmed_stopped,
        chroot_dir=chroot_named,
        claim=claim,
    )

    return {
        "schema_version": "1.0",
        "outcome": outcome,
        "vm_id": plan["vm_id"],
        "plan_sha256": plan["plan_sha256"],
        "policy_sha256": plan["policy_sha256"],
        # The evidence that this jail's name was this run's, carried out with
        # the record rather than left on a disk that the same record says to
        # remove. ``nonce`` is what every ownership question in here compared
        # against, so a reader can see what was being compared.
        "jail_claim": dict(claim),
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
        # is free again, and only the first one was ever being recorded. The
        # third is what this run last *saw*, which is the only one of the three
        # that distinguishes a guest that exited on its own — never signalled,
        # nothing to confirm — from one nobody ever looked at.
        "stop_signal_sent": stop_signal_sent,
        "guest_confirmed_stopped": guest_confirmed_stopped,
        "guest_last_seen_running": guest_last_seen_running,
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


def _destroy_unless_something_is_still_running(
    paths: list[str],
    *,
    outcome: str,
    guest_confirmed_stopped: bool | None,
    chroot_dir: Path,
    claim: Mapping[str, Any],
) -> dict[str, Any]:
    """Remove the jail, unless it is not this run's or something is still in it.

    Two refusals, and they are about different things. The first is ownership:
    the jail's record has to still be the one this run wrote, checked here at
    the moment of removal rather than inherited from a flag set before the boot.
    ``rmtree`` is the least recoverable thing this module does, so it is the
    place least willing to act on a stale answer. ``claim`` has no default for
    the same reason — a cleanup that can be called without evidence will be.

    The second is the direct consequence of the two overran outcomes, and the
    reason they could not be added without coming here. Both of them end with a
    machine this run launched still on the host; the line that followed removed
    the jail anyway, which is an ``rmtree`` of the rootfs, the work disk and the
    socket a live Firecracker is holding open. The run then returned a record
    saying the jail was gone, which it was, and saying nothing about what was
    using it.

    A leaked directory is a worse-looking outcome and a better one. It can be
    found, inspected and removed by hand once the machine is gone; a filesystem
    pulled out from under a running guest cannot be undone, and the guest is
    still running afterwards either way.

    The refusal is recorded rather than silent, because "the jail is still
    there" and "the jail is still there because this run would not take it from
    a live machine" are the same directory listing and different findings.
    """
    held, why = _this_run_still_holds_it(chroot_dir, claim)
    if not held:
        return {
            "removed": {},
            "all_gone": False,
            "failures": [],
            "refused_because": (
                f"nothing was removed because {why}. Whatever is in that jail "
                "now belongs to whoever holds it, and this run does not take "
                "down a jail on the strength of having once held the name"
            ),
            "left_behind": list(paths),
        }
    if the_host_was_left_running(
        {"outcome": outcome, "guest_confirmed_stopped": guest_confirmed_stopped}
    ):
        return {
            "removed": {},
            "all_gone": False,
            "failures": [],
            "refused_because": (
                f"the machine ended as {outcome!r}, so a guest this run started "
                "is still on the host; removing its jail would take the work "
                "disk and the socket it is using with it"
            ),
            "left_behind": list(paths),
        }
    destroyed = _destroy(paths)
    destroyed["refused_because"] = None
    return destroyed


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
    claim: Mapping[str, Any],
    work_disk: str | Path,
    salvage: dict[str, Any],
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
    to get wrong in the safe-looking direction. All three steps are gated on the
    same question — is the ownership record this run wrote still the one in this
    jail — and each of them **asks it again, against the disk**, rather than
    reading a value passed in from before the boot. That is why ``claim`` is
    required and has no default. Its predecessor was
    ``chroot_was_already_there: bool = False``, and every caller that forgot it
    got the answer that permits signalling, copying and removal; a default that
    can only be wrong in the unsafe direction is not a default.

    A process is signalled only when the jail is still this run's, no PID file
    was there before it launched, one appeared while it was watching, and the
    value in it is one this platform can signal. The jail is the strongest of
    those, because the plan puts the PID file *inside* the chroot — a jail this
    run does not hold contains another run's PID file and another run's work
    disk.

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
    holds_it, why_not_ours = _this_run_still_holds_it(chroot_dir, claim)
    process: dict[str, Any] = {
        "pid_file": pid_file.as_posix(),
        "jail_held_by_this_run": holds_it,
        "jail_reading": why_not_ours,
        "pid": None,
        "signalled": False,
        "was_running": None,
        "confirmed_stopped": None,
        "left_alone_because": None,
        "cannot_rule_out": CANNOT_RULE_OUT,
    }
    try:
        if not holds_it:
            process["left_alone_because"] = (
                f"{why_not_ours}, so the PID file inside it and the machine it "
                "names are another run's, and this run does not stop another "
                "run's machine"
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
        holds_it_now, why_not_ours_now = _this_run_still_holds_it(chroot_dir, claim)
        if not holds_it_now:
            salvage["why_not"] = (
                f"{why_not_ours_now}, so the disk inside it is another run's "
                "and this run does not copy it out"
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
    # was observed a moment ago rather than from whether a signal was sent, and
    # through the same judgement the ordinary path uses, because the two used to
    # disagree about the same host. The branches above that set
    # ``left_alone_because`` leave ``was_running`` at None — this run refused to
    # claim the process, so it never looked at it — and a copy taken in that
    # state is unverified rather than clean.
    salvage.update(
        _how_intact_is_the_copy(
            a_copy_was_taken=salvage.get("returned_copy") is not None,
            last_seen_running=process["was_running"],
            confirmed_stopped=process["confirmed_stopped"],
        )
    )

    # ---- 3. remove the jail, if it is this run's to remove ---------------
    destroyed: dict[str, Any] = {"removed": {}, "all_gone": False, "failures": []}
    refused_to_destroy: str | None = None
    holds_it_at_removal, why_not_at_removal = _this_run_still_holds_it(
        chroot_dir, claim
    )
    if not holds_it_at_removal:
        refused_to_destroy = (
            f"{why_not_at_removal}; removing it would take another run's work "
            "disk with it"
        )
    elif process["was_running"] is True and process["confirmed_stopped"] is not True:
        # The same rule the ordinary path applies, for the same reason. Step 1
        # above either declined to signal or sent one and could not confirm it
        # landed; either way the last thing this run observed was a live process
        # holding this jail's work disk and socket open. Removing it here would
        # be the failure path doing what the success path was just stopped from
        # doing.
        refused_to_destroy = (
            "this run's own machine was last seen running and was never "
            "confirmed stopped, so removing its jail would take the disk and "
            "socket it is using with it"
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
