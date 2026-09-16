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

import errno
import json
import math
import os
import shutil
import signal
import subprocess
import time
import uuid
from decimal import Decimal, InvalidOperation
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

try:
    CLOCK_TICKS_PER_SECOND = os.sysconf("SC_CLK_TCK") or 100
except (OSError, ValueError, AttributeError):  # pragma: no cover - POSIX only
    CLOCK_TICKS_PER_SECOND = 100
"""The unit ``/proc/<pid>/stat`` counts a process's start time in.

Asked of the host rather than written down as 100, because the two numbers this
module compares — a reading from ``/proc/uptime`` and a field from
``/proc/<pid>/stat`` — are only comparable when both are converted with the same
value, and a wrong one would silently shift every comparison in the same
direction. 100 on this host. The fallback is for a platform that has no
``sysconf``; there the whole ``/proc`` reading fails anyway and the identity
check refuses on its own terms rather than on a bad constant.
"""

CANNOT_RULE_OUT = (
    "A process that is confined to this run's jail but was placed there by "
    "something other than this run's own jailer. Ownership is established by "
    "asking where the process named in the PID file is rooted: the jail is a "
    "directory this run created and claims exclusively, so a process whose "
    "root is that directory was put there by this run. What that does not "
    "separate is a second jailer invoked against the same jail by something "
    "outside this run, which the exclusive claim is what stands against. A "
    "start-time interval is checked alongside it and can only turn candidates "
    "away; on its own it never established origin, because an unrelated "
    "process born inside the interval satisfies it."
)
"""What the ownership evidence below still does not establish.

Recorded in the artefact rather than left out of it. An ownership verdict with
no statement of its limit reads as proof, and this one is not proof.

This sentence has been narrowed twice, and each narrowing was exactly as wide
as the evidence behind it — no wider. It first said PID reuse outright, because
nothing compared the number against anything. A floor then excluded every
process that was already running at launch, which left *anything born after the
floor*, for the whole remaining life of the run: measured on this host, an
unrelated child forty clock ticks past the floor was admitted with no reason
against it. The second bound in :func:`_started_during_this_runs_launch` closes
that, and what is left is the sentence above.
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

The fields here are still read by nobody, and that is deliberate — they describe
the **launcher**, and a launcher that looks dead is not evidence about the guest.
The guest's identity is bound elsewhere, at launch, by
:func:`_the_instant_this_run_launched`, and it is bound for signalling only. No
path anywhere reclaims, removes or repurposes a jail on the strength of a
process looking stale.
"""

OUTCOME_STARTED_AND_NOT_IDENTIFIED = "started_and_could_not_be_identified"
"""The launcher ran, and this run never got a process it could name.

The word the ordinary path was missing. ``never_started`` is a finding — it says
nothing was put on the host — and the only evidence that supports it is this
run's own account of its own control flow: the launch was not reached, or it
raised the one error that proves the ``exec`` never happened. An absent PID file
is neither. It is the jailer's fork-to-publication window, or a file caught
mid-write, and the run cannot tell those from an empty host.

Recording that state as ``never_started`` is not a wording problem. The teardown
gate reads ``outcome``, so the word decides whether ``rmtree`` runs on a jail
whose work disk something may still have open.

Applying that rule leaves ``never_started`` with no producer. Nothing reaches the
ordinary return without having attempted a launch that did ``exec`` — the flag is
set on the line above the call, and the one error that proves nothing spawned is
re-raised — so the ordinary path's answer here is always this one. The two states
``never_started`` used to stand for both leave through the abandonment path,
which carries the two flags themselves rather than a word standing in for them.
:func:`core.agentic_v2_exec_boot.read_the_boot` keeps its ``never_started`` row
because records written before this change still say it.

**Two routes reach this word, and they are not the same observation.** One is
the absent PID file above. The other is a PID file that did appear, naming a
number this run cannot show belongs to it — the deadline arrives, something is
still running under that number, and the interval that would have adopted it
declined. The first says nothing could be named; the second says something is
there and its name proves nothing. Both leave the host in the state this word
exists for, so both answer with it, and in both the jail stays standing and
nothing is signalled.
"""

OUTCOMES_THAT_LEAVE_THE_HOST_RUNNING = frozenset(
    {
        "overran_and_was_left_alone",
        "overran_and_did_not_stop",
        OUTCOME_STARTED_AND_NOT_IDENTIFIED,
    }
)
"""Outcomes after which this run may not treat the host as free.

Named here, beside the code that produces them, because this vocabulary has
already grown once — from four outcomes to six — while the module that reads it
still knew four, and the two new ones fell through into the ordinary-success
branch. A consumer that imports this set finds out when it grows again; one that
spells the strings out for itself does not.

The first two are findings: a machine this run launched *is* still there. The
third is not, and the set is named for what it decides rather than for what the
first two have in common. Unknown belongs with occupied and not with free,
because the two are only interchangeable if the missing evidence is assumed to
be absence — which is the assumption that put an ``rmtree`` under a live writer.
Callers that need the difference read ``outcome`` itself; what this set answers
is the narrower question of whether anything may be taken away.
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
    """Whether this run must not treat the host as free afterwards.

    Separate from what the command did and from what the copy is worth. A
    command can finish with a returncode of 0 in a guest that then refuses to
    shut down, and all three of those are true at once; folding them into one
    answer is how a leaked machine reached the model as an ordinary success.

    ``guest_confirmed_stopped is False`` is included because it is the same
    state reached by a different route: a signal went out and the process was
    still there afterwards.

    **True covers two different findings and three callers read it.** For the
    two overran outcomes and for a signal that did not take, it says a machine
    this run launched is still there. For
    :data:`OUTCOME_STARTED_AND_NOT_IDENTIFIED` it says something weaker: the
    launcher ran, this run never got a process it could name, and nothing it can
    see distinguishes an empty host from an occupied one. Both answer the one
    question every caller here is actually asking — may anything be taken away,
    reused or reported as finished — and the answer to that is no either way.

    A caller that needs the difference reads ``outcome``, which is in the same
    mapping and says which of the three it was. Widening this to a three-valued
    answer was the alternative and it moves all three call sites at once; the
    one that matters is :func:`_destroy_unless_something_is_still_running`,
    where "still running" and "cannot say" take the same branch.

    **The second clause of the return reaches a state neither of those
    descriptions covers.** A later step rewrites ``outcome`` when the work disk
    does not come back, and two of the outcomes above are reached by breaking
    out of the watch loop before anything is signalled — so they arrive with
    ``guest_confirmed_stopped`` still ``None``, and once ``outcome`` has been
    rewritten there is no other field left holding the leak.
    ``outcome_before_the_carriage_failed`` is where it was put aside, and
    without reading it here a command that exits 0 in a guest that will not go,
    on a call whose disk also fails to return, reads back as a free host.
    """
    return (
        boot.get("outcome") in OUTCOMES_THAT_LEAVE_THE_HOST_RUNNING
        or boot.get("outcome_before_the_carriage_failed")
        in OUTCOMES_THAT_LEAVE_THE_HOST_RUNNING
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


def _ticks_from_uptime(text: str, *, round_up: bool = False) -> int:
    """``/proc/uptime``'s first field as a whole number of clock ticks.

    Parsed as a decimal rather than as a float, and that is not tidiness. The
    file prints hundredths of a second, so at 100 ticks a second the value it
    holds is already a whole number of ticks and the conversion should not be
    able to lose anything. Through a float it can: ``float("2454334.36") * 100``
    is not exactly ``245433436`` for every value, and truncating whatever comes
    out lands one tick low. Across two thousand uptime-shaped strings that was
    eighty-four of them — about one in twenty-five, silently, and always in the
    same direction.

    One tick low is harmless at the floor and not at the ceiling: it moves the
    upper bound below the start time of a process that really did begin before
    the number was read, so the launch this run performed itself is turned away.
    Measured before this was parsed exactly: twenty-nine of three hundred
    ordinary launches refused, every one by exactly one tick.

    ``round_up`` is for a host where a tick is not a hundredth of a second, so
    the printed value falls part-way through one. The instant the file stands
    for is then somewhere inside that tick, and an upper bound has to take the
    whole of it. Where the division is exact — this host, and any other at 100
    ticks a second — both settings give the same number, which is the tightest
    interval the clock can express.
    """
    seconds = Decimal(text.split()[0])
    exact = seconds * CLOCK_TICKS_PER_SECOND
    return math.ceil(exact) if round_up else int(exact)


def _the_host_clock_in_ticks(*, round_up: bool = False) -> dict[str, Any]:
    """The host clock, in the units a process's start time is expressed in.

    Two readings are taken from this during a launch and they bound opposite
    ends of the same interval, so they have to be the same reading taken twice
    rather than two different ways of asking. ``_the_instant_this_run_launched``
    is the first of them; the second is taken where the number is first read.

    ``/proc/<pid>/stat`` field 22 counts clock ticks since boot, so this counts
    the same ticks from ``/proc/uptime``. ``boot_id`` rides along because the
    tick count is meaningless across a reboot — after one, every number restarts
    and an old floor would admit anything.

    ``round_up`` says which end of the interval the caller is reading, which
    matters only where a tick is not a hundredth of a second;
    :func:`_ticks_from_uptime` carries that and the reason the conversion is not
    a float.

    Every field may be missing. A floor that could not be read is written down
    as ``None`` and read downstream as *no evidence*, which refuses; it is never
    filled in with a guess, and there is no value that means "skip the check".
    """
    ticks: int | None = None
    try:
        with open("/proc/uptime", encoding="utf-8") as uptime:
            ticks = _ticks_from_uptime(uptime.read(), round_up=round_up)
    except (OSError, ValueError, IndexError, InvalidOperation):
        pass
    boot_id: str | None = None
    try:
        boot_id = Path("/proc/sys/kernel/random/boot_id").read_text().strip() or None
    except OSError:
        pass
    return {
        "ticks_since_boot": ticks,
        "boot_id": boot_id,
        "clock_ticks_per_second": CLOCK_TICKS_PER_SECOND,
    }


def _the_instant_this_run_launched() -> dict[str, Any]:
    """The lower end of the interval, read immediately before the jailer runs.

    Read **before** the launch, and for the same reason ``launch_was_attempted``
    is set there: it is this run's record of its own control flow, not an
    inference drawn from the host afterwards. A floor read after the launch
    would be later than the guest's own start and would turn away the very
    process it exists to recognise.
    """
    return _the_host_clock_in_ticks()


def _the_instant_the_number_was_read() -> dict[str, Any]:
    """The upper end of the interval, read the moment a usable PID is in hand.

    A process cannot be older than the number that names it and cannot be
    younger than the moment that number was written down, so a reading taken
    *after* the number has been read off the file is an upper bound on the start
    time of whatever the jailer published. It is this run's own control flow
    again — no file timestamp is consulted, and nothing here depends on how the
    jailer orders its fork, its exec and its write.

    What this excludes is the thing the floor alone does not: a process that
    began **after** this run already held the number. That is where a recycled
    number lands, and it is the whole of the distance between "not older than
    the launch" and "born during it".

    Rounded up, because it is an upper bound. On this host that changes nothing
    — a tick is a hundredth of a second and the file prints hundredths — but the
    conversion it goes through has to be exact, and it was not: read through a
    float, this bound landed one tick low often enough to refuse about one
    ordinary launch in ten. :func:`_ticks_from_uptime` carries the measurement.
    """
    return _the_host_clock_in_ticks(round_up=True)


def _when_that_process_started(pid: int) -> int | None:
    """Clock ticks since boot at which ``pid`` began, or ``None``.

    Constant for the life of a process and gone the moment it is reaped, which
    is what makes it usable as identity: the pair ``(pid, start time)`` names one
    process and keeps naming it, where ``pid`` alone names whoever holds the
    number right now. Measured on this host — a start time read twice half a
    second apart returned the same value, and a reaped process's file was gone.

    Unreadable for any reason returns ``None``, and every caller reads that as
    *no evidence*. A process owned by another user is still readable here;
    ``/proc/<pid>/stat`` is world-readable on Linux, so a stranger's process is
    turned away by the comparison rather than by a permission error.
    """
    try:
        raw = Path(f"/proc/{pid}/stat").read_text()
        # Field 2 is the command name and may itself contain spaces and
        # brackets, so fields are counted from after the last ')' — where field
        # 3 begins, putting start time at index 19.
        return int(raw[raw.rindex(")") + 1:].split()[19])
    except (OSError, ValueError, IndexError):
        return None


def _the_jail_a_process_is_confined_to(pid: int) -> tuple[str | None, str]:
    """How ``/proc/<pid>/root`` *renders*, or why it could not be read.

    **A rendering is not an identity, and on the real jailer the two differ.**
    ``/proc/<pid>/root`` is a link to the root a process actually sees, but the
    kernel can only spell it as a path the *reader* could walk. The jailer does
    not merely ``chroot``: it unshares a mount namespace and ``pivot_root``s,
    so from the host the jail is the root of a tree that is not in the reader's
    namespace, and the link renders as ``/`` — the same string an ordinary
    unjailed process gives.

    Measured on the target host, kernel ``6.17.0-1022-azure``, against a real
    jailed ``firecracker`` (``c2-deadline``, 2026-09-15): the link read ``/``
    while ``/proc/<pid>/mountinfo`` named the jail and the process sat in its
    own mount namespace. An earlier version of this docstring recorded the
    opposite from a stand-in that ``chroot``ed without unsharing — a stand-in
    that did not have the property being relied on.

    So this is kept for the one thing it can still do: show a reader what was
    seen. The verdict is taken from
    :func:`_the_directory_a_process_has_as_its_root`, which compares the
    directory instead of the name of it.

    **The three answers are not one answer.** A process that has gone leaves
    nothing to read and that is ``ENOENT``; a reader without the privilege to
    look is ``EPERM``; anything else is unknown. None of them may be taken for
    a match, so each returns ``None`` with the reason it returns ``None``.
    """
    try:
        return os.readlink(f"/proc/{pid}/root"), ""
    except (FileNotFoundError, ProcessLookupError):
        return None, (
            f"the host has no process {pid} to read a root from, so there is "
            "nothing to confine"
        )
    except PermissionError:
        return None, (
            f"this run may not read what process {pid} has as its root, so it "
            "cannot tell whether that process is confined to its jail"
        )
    except OSError as unreadable:
        code = errno.errorcode.get(unreadable.errno or 0, str(unreadable.errno))
        return None, (
            f"the root of process {pid} could not be read ({code}), which is "
            "not evidence either way"
        )


def _the_directory_a_process_has_as_its_root(
    pid: int,
) -> tuple[tuple[int, int] | None, str]:
    """Which directory ``pid`` has as its root, as an identity rather than a name.

    ``/proc/<pid>/root`` cannot be *rendered* across a mount namespace, but it
    can still be *walked*: ``/proc/<pid>/root/.`` resolves through the link into
    whatever that process holds as its root, in that process's own tree, and
    lands on the directory itself. Two paths naming one directory agree on
    ``(st_dev, st_ino)`` however each of them is spelled, and no two directories
    share a pair.

    **This is a tightening as well as a repair.** A string could be satisfied by
    a different directory that happens to carry the same path in another
    namespace — which is precisely the namespace this question is asked across.
    A device and inode pair cannot be satisfied by anything except the one
    directory this run made.

    **The three answers are not one answer**, and they are the same three as
    above: gone is ``ENOENT``, unprivileged is ``EPERM``, anything else is
    unknown, and none of the three is a match.
    """
    try:
        seen = os.stat(f"/proc/{pid}/root/.")
    except (FileNotFoundError, ProcessLookupError):
        return None, (
            f"the host has no process {pid} to read a root from, so there is "
            "nothing to confine"
        )
    except PermissionError:
        return None, (
            f"this run may not walk into what process {pid} has as its root, "
            "so it cannot tell whether that process is confined to its jail"
        )
    except OSError as unreadable:
        code = errno.errorcode.get(unreadable.errno or 0, str(unreadable.errno))
        return None, (
            f"the root of process {pid} could not be read ({code}), which is "
            "not evidence either way"
        )
    return (seen.st_dev, seen.st_ino), ""


def _confined_to_this_runs_jail(pid: int, chroot_dir: Path) -> tuple[bool, str]:
    """Whether ``pid`` is confined to the jail this run made and holds.

    **This is the positive ground, and it is positive because of what the jail
    already is.** The jail is a directory this run created and claimed
    exclusively — no other run may occupy it, which
    ``test_v2_claims_the_jail_before_it_uses_it.py`` is there to keep true. A
    process whose root is that directory was therefore put there by this run's
    own jailer. Nothing else on the host can be confined to it.

    That is a different kind of statement from the interval below, which only
    ever said *when* something began. An unrelated process born at the right
    moment passes the interval; it cannot be confined to a jail it was never
    placed in. The measured negative control is exactly that process, and it is
    turned away here on a ground that has nothing to do with the clock.

    **Asked of the directory, not of its name.** The first version of this
    compared ``/proc/<pid>/root`` against ``str(chroot_dir)``, and on a real
    jailer that comparison can never hold: the jailer ``pivot_root``s into its
    own mount namespace, so the link renders as ``/`` for every jailed machine.
    Measured, that turned every overrunning guest into an unidentified one — the
    deadline could not fire, the jail could not be removed, and the two call
    sites that stop a machine were both dead. The directory is asked for
    instead, and a directory answers the same whichever namespace spells it.
    """
    here, why_not = _the_directory_a_process_has_as_its_root(pid)
    if here is None:
        return False, why_not
    try:
        jail = os.stat(chroot_dir)
    except OSError as unreadable:
        code = errno.errorcode.get(unreadable.errno or 0, str(unreadable.errno))
        return False, (
            f"the jail this run made and holds ({chroot_dir}) could not be "
            f"read ({code}), so nothing can be shown to be confined to it"
        )
    if here != (jail.st_dev, jail.st_ino):
        rendered, _unreadable = _the_jail_a_process_is_confined_to(pid)
        return False, (
            f"process {pid} has a root that is not the jail this run "
            f"made and holds ({chroot_dir}) — /proc/{pid}/root renders as "
            f"{rendered or 'nothing readable'} and resolves to a different "
            "directory, so it is not this run's machine"
        )
    return True, ""


def _started_during_this_runs_launch(
    pid: int,
    launch_floor: Mapping[str, Any] | None,
    number_read_at: Mapping[str, Any] | None,
) -> tuple[int | None, str]:
    """The start time of ``pid`` if it began during this run's launch, or why not.

    **This is a narrowing and not a proof of origin.** An earlier version of
    this docstring called the second bound "what makes this positive", and that
    was wrong: an unrelated process that begins inside the interval satisfies
    both bounds. What establishes origin is
    :func:`_confined_to_this_runs_jail`, which asks where the process is rather
    than when it started. This test runs alongside it and can only ever turn
    something away.

    **Two bounds.** The floor is
    read immediately before the jailer runs; the ceiling is read the moment this
    run has a usable number in hand. A process the jailer published began after
    the first and before the second, because the number could not have been
    written down for a process that did not exist yet and this run did not have
    the number before it read it. So the claim is *this process began inside the
    interval in which this run was launching*, which is a statement about this
    launch, rather than *this process is not older than this run*, which is a
    statement about every other process on the host.

    The difference is not decorative. One bound admits every process on the host
    that happens to be younger than the floor — an unrelated ``sleep`` started
    by anything at all, for the whole remaining life of the run. That was
    measured on this host: a child born 40 clock ticks past the floor, with no
    launcher and no jail anywhere near it, was admitted with no reason against
    it. Adding the ceiling turns that case away while leaving the launch the
    ceiling was read for untouched.

    What it refuses, in the order it refuses it:

    * no floor, or no ceiling — one end of the interval is missing, so there is
      no interval. Nothing is established and nothing is signalled. There is no
      value meaning "skip this end".
    * a different boot id — the host restarted since this run launched. Tick
      counts restart with it, so neither end means anything.
    * no start time — the number names nothing readable now. That is not
      evidence of anything, including of its being gone.
    * a start time below the floor — it was already there. Measured: a sleeper
      created two clock ticks before the reading fell below it 20 times out of
      20.
    * a start time above the ceiling — it began after this run was already
      holding the number, so it cannot be what the number was published for.

    **What is still not established.** A number reused *inside* the interval
    reads the same from here, and so does one that named a process which exited
    and was replaced within it. That residue is why this test is not the
    ownership verdict on its own: :func:`_confined_to_this_runs_jail` is asked
    as well, and a number handed to something else inside the interval is not
    confined to this run's jail and is turned away there.

    **What this leaves for the caller to carry.** The number is still only a
    number after this returns. ``pidfd_open(2)`` pins an identity from the
    moment it is opened, and opening one *after* both grounds admit the number
    is the right order — they decide whether the number may be adopted, and a
    handle taken on the strength of that decision carries it forward. Opening
    one first would pin whatever holds the number, which is not provenance. No
    handle is taken yet: every caller below re-reads the start time at the
    moment it acts, which closes the same gap only up to the instant of the
    re-read. The process is also not this process's child — the jailer
    daemonises and Firecracker is reparented — so ``waitpid`` cannot hold the
    number either, which is why confinement rather than parentage is what
    carries origin here.
    """
    if not launch_floor:
        return None, (
            "this run has no record of when it launched, so it has no instant "
            "to measure that process against"
        )
    floor = launch_floor.get("ticks_since_boot")
    if not isinstance(floor, int):
        return None, (
            "this run could not read the host clock when it launched, so it has "
            "no instant to measure that process against"
        )
    if not number_read_at:
        return None, (
            "this run has no record of when it read that number, so it has no "
            "interval to measure that process against"
        )
    ceiling = number_read_at.get("ticks_since_boot")
    if not isinstance(ceiling, int):
        return None, (
            "this run could not read the host clock when it took that number, "
            "so it has no interval to measure that process against"
        )
    boot_id = launch_floor.get("boot_id")
    now_booted = _the_host_clock_in_ticks().get("boot_id")
    if boot_id is not None and now_booted is not None and boot_id != now_booted:
        return None, (
            "the host has restarted since this run launched, so no process "
            "number from before it names anything of this run's"
        )
    started = _when_that_process_started(pid)
    if started is None:
        return None, (
            f"the host has nothing to say about when process {pid} started, so "
            "there is no evidence it is this run's"
        )
    if started < floor:
        return None, (
            f"process {pid} was already running {floor - started} clock ticks "
            "before this run launched, so it is not a machine this run started"
        )
    if started > ceiling:
        return None, (
            f"process {pid} began {started - ceiling} clock ticks after this run "
            "already had that number in hand, so it is not what the number was "
            "published for"
        )
    return started, ""


def _still_the_same_process(pid: int, started: int | None) -> bool:
    """Whether ``pid`` still names the process whose start time was ``started``.

    Asked again at the moment of use rather than inherited, because the number
    is the only thing the host keeps and the number is what gets recycled. A
    start time that has changed does not mean *something went wrong*; it means
    the process this run identified is gone and another holds its number.
    """
    if started is None:
        return False
    return _when_that_process_started(pid) == started


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


BY_A_PINNED_HANDLE = "pidfd"
"""The signal went through a descriptor pinned to one process."""

BY_THE_NUMBER_RECHECKED = "number_rechecked"
"""Historical only: a stop this code used to send by number.

Kept so a reader of a run recorded before 2026-09-15 still has the name for
what it is holding. **Nothing in this module writes it any more.** The by-number
path it named re-read the start time and then signalled — two operations, with
the number free to be handed on between them — and that gap was accepted on the
strength of :data:`HANDLE_UNSUPPORTED`, which says only that the *capability*
is missing. A missing capability is not permission to use a racier one.
"""


HANDLE_TAKEN = "taken"
"""A handle was taken and it names the process this run admitted."""

HANDLE_GONE = "gone"
"""No handle because the process had already ended. Not a failure."""

HANDLE_HANDED_ON = "handed_on"
"""No handle because the number now names a different process."""

HANDLE_UNSUPPORTED = "unsupported"
"""No handle because this kernel or interpreter does not have the interface.

``ENOSYS`` from the syscall, or the attribute missing from the interpreter.
Both mean the same thing and this is the change of 2026-09-15: *the safe way to
stop a process is unavailable here*. That is a statement about the host, and it
used to be read as permission to fall back to the number. It is not. The two
facts are unrelated — a host that cannot pin a process has not thereby shown
that a given number still names this run's process, which is the only thing
that would make signalling it safe.

So this verdict refuses like the rest, and the jail is kept.
:data:`OLDEST_HOST_KERNEL_FIRECRACKER_VALIDATES` sits above the releases that
added the interface, so a host that reaches here is already outside what
Firecracker validates and cannot be one a guest is booted on.
"""

HANDLE_DENIED = "denied"
"""No handle because the kernel refused this process the right to take one.

``EPERM``/``EACCES``. Distinct from :data:`HANDLE_UNSUPPORTED` and it is the
distinction this taxonomy exists for. A kernel new enough to have the call and
unwilling to let this run pin *that* process is saying something about the
relationship between the two, and "signal it by number instead" answers a
question nobody asked. Seccomp, a user namespace, and a process that is not
this run's all arrive here, and none of them is a reason to send a weaker
signal — so none of them does.
"""

HANDLE_UNKNOWN = "unknown"
"""No handle, or no way to tell what the handle names.

Two routes reach it. One is a reason the ``pidfd_open`` taxonomy cannot read —
descriptor exhaustion, an undocumented errno, an interpreter built against a
different libc. The other is a handle that opened while ``/proc`` would not say
when the process began, so whether the number moved between admission and the
open is unanswered.

Unknown is not permission to proceed; it is refused exactly like
:data:`HANDLE_DENIED`, because the thing that is unknown is whether the process
is this run's. It is also not :data:`HANDLE_HANDED_ON`: that verdict is a
positive finding that the number now names something else, and it lets the
caller treat this run's machine as stopped. Unknown does not.
"""

HANDLE_NOT_SHOWN_TO_BE_OURS = "not_shown_to_be_ours"
"""A handle was taken, and the process it names is not shown to be this run's.

The verdict that closes the gap this taxonomy used to leave open. Every verdict
above is about *acquiring* the handle; this one is about what the handle turned
out to be holding. Confinement to this run's jail was established once, at
admission, and from then until the signal the only thing re-read was a start
time in clock ticks — a number two processes can share, one having replaced the
other inside a single tick.

It is asked here and nowhere else because here is the only place it can be asked
and mean anything. ``pidfd_open`` makes the kernel hold a reference to the
process's ``struct pid``, so for as long as the descriptor is open the number
cannot be handed to anything new. A confinement read taken inside that interval
is therefore a reading *about the process the handle names*, not about whoever
holds a number by the time the answer comes back. Taken outside it — in
:func:`_may_signal_now`, say — the same read would be one more racy number.

**Two findings share it, and the sentence carries which.** A process positively
confined somewhere else, and a confinement this run could not read at all. They
are different evidence and they are not collapsed: ``refused_because`` holds the
message :func:`_confined_to_this_runs_jail` composed, which distinguishes gone,
not-permitted and unreadable-for-another-reason. What they have in common is the
only thing the verdict claims — that nothing here shows the process is this
run's — and neither of them is :data:`HANDLE_GONE`, which is asked first and
separately, and is the one answer that lets a caller treat the machine as
stopped.
"""

NO_VERDICT_MAY_SIGNAL_BY_NUMBER = True
"""There is no verdict that sends ``SIGKILL`` to a bare number. Declared.

This replaced a ``frozenset`` of the verdicts allowed to fall back, which held
exactly :data:`HANDLE_UNSUPPORTED`. A set with one member reads as a dial that
happens to be turned down; the fact is that the by-number path is gone from
this module, so the shape that says so is a flag and not a set. A test asserts
that the module's own source sends no ``SIGKILL`` to a bare number any more,
which is the claim this constant makes in prose.
"""


PIDFD_SEND_SIGNAL_ARRIVED_IN = (5, 1)
"""The Linux release that added ``pidfd_send_signal(2)``."""

PIDFD_OPEN_ARRIVED_IN = (5, 3)
"""The Linux release that added ``pidfd_open(2)``.

Both are here so the relationship between them and
``OLDEST_HOST_KERNEL_FIRECRACKER_VALIDATES`` can be asserted rather than
asserted-in-prose: the oldest kernel Firecracker's own policy lists is above
both, so a host that clears the containment readiness check has this interface.
A host that does not have it cannot be stopped safely by this module at all,
and since 2026-09-15 is refused rather than signalled by number. This host is
one of those.
"""


def _a_handle_pinned_to(
    pid: int, started: int, *, chroot_dir: Path
) -> tuple[int | None, str, str]:
    """A descriptor that names one process and cannot come to name another.

    ``pidfd_open(2)`` takes its argument by number, so the descriptor it hands
    back is pinned to whatever held the number *at that instant* — which is the
    right process if the number had not been handed on since this run admitted
    it, and the wrong one if it had. That is why the start time is read again
    here, while the descriptor is held: a reading that still matches says the
    number had not moved, and from that point the descriptor keeps it from
    moving. Every signal sent through it afterwards reaches that process or
    fails; none of them can reach a successor.

    This is not the same as the number being proof. It narrows a gap that used
    to sit in front of *every* signal down to one, at the moment of the open,
    and the residue there is a replacement that began inside the same clock tick
    as the process it replaced — a process that lived under ten milliseconds.

    **Where it is not available, and why every one of those answers refuses.**
    ``pidfd_open`` is a syscall, not a library call, and an old kernel answers
    ``ENOSYS`` no matter what the interpreter exposes. This host is one of
    those, so nothing in this repository's own test runs takes the handle path.

    That case — :data:`HANDLE_UNSUPPORTED` — used to be the one verdict that
    went on to signal by number, on the grounds that it is a fact about the host
    rather than about the process. The grounds were sound and the conclusion did
    not follow. "This kernel cannot pin a process" and "this number still names
    the process this run admitted" are unrelated statements, and only the second
    would make a bare ``kill`` safe. Since 2026-09-15 it refuses with the rest.

    ``EPERM`` from a kernel that *has* the call is a statement about this run's
    relationship to that particular process, and so is an errno this code cannot
    read, and so is a handle that opened over a ``/proc`` that would not say
    when the process began. All three refuse (:data:`HANDLE_DENIED`,
    :data:`HANDLE_UNKNOWN`) rather than reaching for a weaker way to send the
    same signal, because the question they leave open is whether the process is
    this run's — and "I could not check" has never been an answer to that. The
    earlier version of this function folded every ``OSError`` into "this kernel
    has no pidfd", which on a new kernel was a false statement that authorised
    the weaker path.

    **An unreadable start time is not a handover.** Reading it back is how the
    open is checked, and ``_when_that_process_started`` answers ``None`` for
    every way that reading can fail. Treating ``None`` as "different from what
    was admitted" put those failures in :data:`HANDLE_HANDED_ON`, whose meaning
    to the caller is *the machine is not there any more* — so a ``/proc`` this
    run could not read reported a stop that had not happened. They are split
    here: a value that reads back and differs is a handover, and no value at all
    is :data:`HANDLE_UNKNOWN`.

    **The start time was never enough on its own, and this is where the rest of
    it goes.** A start time is a count of clock ticks since boot, so two
    processes can share one; the residue named above — a replacement born inside
    the same tick — is a process the equality check cannot tell from the
    original. What can tell them apart is where they are: the jail is a
    directory this run created and claimed exclusively, so being confined to it
    is not something a stranger can arrive at by being born at the right moment.
    That question is asked once at admission and, until 2026-09-16, never again.

    ``chroot_dir`` is required and has no default, so a caller that has not
    thought about which jail it means gets a ``TypeError`` rather than a signal.
    Both the deadline and the cleanup after a failure reach this through
    :func:`_stop_the_process_this_run_identified`, which is why there is one
    contract here and not two.

    **Why here and not in :func:`_may_signal_now`.** Adding the same read there
    would add a third number to re-check in a place where the answer can go
    stale before it is used. Here the descriptor is already open, and an open
    descriptor is the kernel holding the process's ``struct pid``: the number
    cannot be handed on while it is held. The reading taken between the open and
    the signal is therefore about the process that will receive the signal.

    **The direction this can fail in.** The recheck can turn a signal into a
    refusal or into "already gone"; it cannot turn a refusal into a signal.
    Nothing reaches :data:`HANDLE_TAKEN` that would not have reached it before.
    So a host where the pinning guarantee is weaker than documented is no worse
    off than it was, and a host where it holds gets the guarantee.
    """
    try:
        handle = os.pidfd_open(pid)
    except ProcessLookupError:
        return (
            None,
            HANDLE_GONE,
            f"process {pid} was already gone when a handle was asked for",
        )
    except PermissionError as denied:
        return (
            None,
            HANDLE_DENIED,
            f"this kernel has the pidfd interface and refused this run a handle "
            f"on process {pid} ({type(denied).__name__}: {denied})",
        )
    except AttributeError as missing:
        return (
            None,
            HANDLE_UNSUPPORTED,
            f"this interpreter has no pidfd for process {pid} "
            f"({type(missing).__name__}: {missing})",
        )
    except OSError as failed:
        if failed.errno == errno.ENOSYS:
            return (
                None,
                HANDLE_UNSUPPORTED,
                f"this kernel has no pidfd for process {pid} (ENOSYS: {failed})",
            )
        named = errno.errorcode.get(failed.errno or 0, str(failed.errno))
        return (
            None,
            HANDLE_UNKNOWN,
            f"a handle on process {pid} could not be taken and the reason is not "
            f"one this code knows how to read ({named}: {failed})",
        )
    started_now = _when_that_process_started(pid)
    if started_now is None:
        # Not a finding. ``_when_that_process_started`` returns ``None`` for
        # every unreadable ``/proc`` — a process that ended, a ``/proc`` this
        # run may not read, a line it could not parse — and none of those says
        # the number was handed on. Folding them into HANDLE_HANDED_ON told the
        # caller "gone or someone else's", which is the one verdict that makes
        # the caller stop *without* keeping the jail. Unknown keeps the jail.
        os.close(handle)
        return (
            None,
            HANDLE_UNKNOWN,
            f"a handle on process {pid} was taken and its start time could not "
            "be read back, so whether it is still the process this run "
            "admitted is unknown",
        )
    if started_now != started:
        os.close(handle)
        return (
            None,
            HANDLE_HANDED_ON,
            f"process {pid} was handed on between this run identifying it and "
            "taking hold of it, so the handle does not name what was admitted",
        )
    # Liveness before identity, the same order both stop paths already use and
    # for the same reason: a machine that ended on its own is not an unidentified
    # one. Asked while the handle is held, so "nothing holds that number" cannot
    # mean "something else holds it now" — the kernel is keeping the number for
    # this descriptor. A guest that ends here is the ordinary ending, and a
    # confinement read cannot be taken for it at all — an uncollected process has
    # no root to walk into — so asking identity first would file every machine
    # that stopped on its own as a stranger.
    if not _still_running(pid) or _has_exited_but_not_been_reaped(pid):
        os.close(handle)
        return (
            None,
            HANDLE_GONE,
            f"process {pid} ended while this run held a handle on it, so there "
            "is nothing confined to the jail any more and nothing to stop",
        )
    # Identity, now that there is something to have an identity. This is the
    # reading that admission took once and nothing has retaken since; here it is
    # retaken inside the interval where the number cannot move.
    confined, why_not_confined = _confined_to_this_runs_jail(pid, chroot_dir)
    if not confined:
        os.close(handle)
        return (None, HANDLE_NOT_SHOWN_TO_BE_OURS, why_not_confined)
    return handle, HANDLE_TAKEN, ""


def _the_process_a_handle_names(handle: int) -> int | None:
    """The PID the kernel says a descriptor is pinned to, or ``None``.

    Read back out of ``/proc/self/fdinfo`` rather than remembered from the
    number that was passed in, because the two are different claims: one is
    what this run asked for and the other is what it got. Recording the second
    is what makes "the signal reached the process this run meant" checkable
    afterwards by someone who was not here.

    ``None`` is *unknown*, and it is written down as unknown. It never stands
    in for the number that was asked for, and no decision is taken on it — a
    host where ``/proc`` cannot be read is a host where this evidence is
    missing, which is not the same as the evidence saying yes.
    """
    try:
        for line in Path(f"/proc/self/fdinfo/{handle}").read_text().splitlines():
            if line.startswith("Pid:"):
                return int(line.split()[1])
    except (OSError, ValueError, IndexError):
        return None
    return None


def _stop_the_process_this_run_identified(
    pid: int, started: int, *, chroot_dir: Path
) -> dict[str, Any]:
    """Send ``SIGKILL`` to a process that has already been admitted as this run's.

    Admission is the caller's job and has happened before this is reached. What
    is left is the gap between deciding and acting, and there is now one way of
    closing it rather than two: through a pinned descriptor, the decision and
    the signal name the same object, so there is nothing to close.

    **The other way is gone.** Until 2026-09-15 a verdict of
    :data:`HANDLE_UNSUPPORTED` fell through to ``os.kill`` with the start time
    re-read immediately before. Two operations, and the number could be handed
    on between them. The justification was that "this kernel has no pidfd"
    describes the host, not the process — which is true, and does not help: it
    says the safe instrument is missing, not that the unsafe one is accurate
    here. Every verdict other than :data:`HANDLE_TAKEN` and the two that mean
    the process is not there now refuses, and the jail stays where it is.

    ``already_gone`` is its own answer rather than a failure. A process that
    ended between the decision and the signal is not an error and is not a
    refusal; it is the machine having stopped, which is what was wanted. It is
    reached only from a *positive* finding — ``ProcessLookupError`` from
    ``pidfd_open``, or a start time that reads back as a different value — never
    from a reading this run could not take.

    ``chroot_dir`` is this run's jail, and it is required because the identity
    question is asked again once the handle is held; see
    :func:`_a_handle_pinned_to`. Both callers — the deadline and the cleanup
    after a failed launch — come through here, which is how they end up with one
    contract rather than two that drift apart. The verdict that answer can
    produce, :data:`HANDLE_NOT_SHOWN_TO_BE_OURS`, is deliberately not in the
    ``already_gone`` pair below: nothing about it says the machine stopped.
    """
    handle, verdict, why_no_handle = _a_handle_pinned_to(
        pid, started, chroot_dir=chroot_dir
    )
    if handle is not None:
        # Read before the signal, so the evidence is what the descriptor named
        # while it was still open and not what it named after the process went.
        target = _the_process_a_handle_names(handle)
        try:
            signal.pidfd_send_signal(handle, signal.SIGKILL)
        except ProcessLookupError:
            return {
                "signalled": False,
                "how": None,
                "already_gone": True,
                "refused_because": "",
                "handle_verdict": verdict,
                "signal_target": target,
            }
        except OSError as refused:
            # A descriptor that opened and will not carry a signal. Nothing is
            # sent by number instead: the same kernel just declined this, and
            # asking it a weaker way is not a second opinion.
            named = errno.errorcode.get(refused.errno or 0, str(refused.errno))
            return {
                "signalled": False,
                "how": None,
                "already_gone": False,
                "refused_because": (
                    f"a handle on process {pid} was taken and the kernel would "
                    f"not send through it ({named}: {refused})"
                ),
                "handle_verdict": HANDLE_DENIED
                if isinstance(refused, PermissionError)
                else HANDLE_UNKNOWN,
                "signal_target": target,
            }
        finally:
            os.close(handle)
        return {
            "signalled": True,
            "how": BY_A_PINNED_HANDLE,
            "already_gone": False,
            "refused_because": "",
            "handle_verdict": verdict,
            "signal_target": target,
        }
    if verdict in (HANDLE_GONE, HANDLE_HANDED_ON):
        # Not a refusal to act on something that is there — the thing that was
        # there has gone, and the number either names nothing or names someone
        # else. Either way this run's machine is stopped and nothing is sent.
        return {
            "signalled": False,
            "how": None,
            "already_gone": True,
            "refused_because": "",
            "handle_verdict": verdict,
            "signal_target": None,
        }
    # Denied, unsupported, not shown to be ours, or a reason this code cannot
    # read. None of the four establishes that the number still names this run's
    # process, and that is the only fact a signal by number would have to stand
    # on. Unsupported used to be excepted here on the grounds that it describes
    # the host rather than the process — true, and beside the point: a host with
    # no way to pin a process has not thereby shown the number is still the right
    # one. The machine is left where it is and the jail is left with it, which is
    # what lets a later reader see that this run did not finish clearing up.
    return {
        "signalled": False,
        "how": None,
        "already_gone": False,
        "refused_because": why_no_handle,
        "handle_verdict": verdict,
        "signal_target": None,
    }


def _may_signal_now(
    pid_file: Path,
    watched: int,
    *,
    chroot_dir: Path,
    claim: Mapping[str, Any],
    started_at: int | None,
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

    So is the third one. ``started_at`` is the start time this run read off the
    watched process when it decided the process could be its own, and it is
    re-read here because the number outliving its process is the whole failure
    this guards: the file can hold the same integer while a different process
    holds the integer. An unestablished identity (``None``) refuses — there is
    no reading that would make an unidentified process safe to kill.

    **The fourth question is deliberately not asked here.** Whether the process
    is still *inside* the jail is a different question from whether the jail is
    still this run's, and it is answered in :func:`_a_handle_pinned_to` instead.
    Not because it does not belong at the moment of the signal — it does — but
    because this is not yet that moment. Every reading taken here is taken
    before the descriptor is opened, so each one can go stale in the gap between
    being read and being used; adding a fourth would add a fourth thing that can
    go stale, which is not the same as adding a fourth thing that is true. Once
    the handle is open the kernel is holding the process's ``struct pid`` and
    that gap closes, so that is where the confinement reading is taken and where
    it means what it says. Moving it here would make it look answered and leave
    it racy.
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
    if started_at is None:
        return False, (
            f"this run never established that process {watched} was its own, so "
            "there is nothing here it may signal"
        )
    if not _still_the_same_process(watched, started_at):
        return False, (
            f"process {watched} is no longer the one this run identified — the "
            "number has been handed on, and signalling it now would reach a "
            "process this run never started"
        )
    return True, ""


def _has_exited_but_not_been_reaped(pid: int) -> bool:
    """Whether ``pid`` names a process that has ended and not yet been collected.

    **Measured, because the obvious readings both get this wrong.** On the
    target host (kernel ``6.17.0-1022-azure``) a direct child killed through a
    pinned handle and then left uncollected read back as state ``Z``, with
    ``os.kill(pid, 0)`` still succeeding and its start time *unchanged*. Both
    of the readings :func:`_ours_is_gone` had would therefore have said "still
    running, and still ours" about a machine that was already dead — for as
    long as nobody collected it.

    A double-forked orphan, which is the shape ``--daemonize`` produces, was
    collected by init immediately and never showed this. That is why the defect
    was invisible until a direct child was measured, and why it is worth
    reading for rather than arguing about: which shape the launcher produces is
    a property of flags that can change.

    Unreadable is not "exited". Only the literal ``Z`` counts.
    """
    try:
        raw = Path(f"/proc/{pid}/stat").read_text()
        return raw[raw.rindex(")") + 1:].split()[0] == "Z"
    except (OSError, ValueError, IndexError):
        return False


def _ours_is_gone(pid: int, started_at: int | None) -> bool:
    """Whether the process this run identified has ended.

    Three readings say yes and they are not the same reading. Nothing holds the
    number at all — then nothing of this run's is running under it, which holds
    whether or not its identity was ever established. Or something holds it with
    a different start time — then the number was recycled, and the process that
    had it is gone. The second is only available when there is an identity to
    compare against, which is why it is not the only test. Or the number is held
    by a process that has exited and not been collected, which reads as alive
    to both of the others; see :func:`_has_exited_but_not_been_reaped`.

    A number still held by the same *running* process is not gone, and neither
    is one whose start time cannot be read while the number is still live: that
    is an absence of evidence, and this returns ``False`` for it rather than
    treating an unreadable host as a finished machine.
    """
    if not _still_running(pid):
        return True
    if _has_exited_but_not_been_reaped(pid):
        return True
    if started_at is None:
        return False
    return _when_that_process_started(pid) not in (None, started_at)


def _confirm_it_stopped(
    pid: int,
    *,
    started_at: int | None,
    now: Callable[[], float],
    sleep: Callable[[float], None],
) -> bool:
    """Whether the machine actually went, watched on a finite deadline.

    Separate from whether a signal was sent, because they are separate
    observations and only one of them is evidence that the host is free again.
    """
    started = now()
    while now() - started < STOP_CONFIRMATION_SECONDS:
        if _ours_is_gone(pid, started_at):
            return True
        sleep(CONFIRMATION_POLL_SECONDS)
    return _ours_is_gone(pid, started_at)


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
    # Whether this run reached the call that starts a machine. Read by the
    # teardown handler, which is the only place that has to tell "nothing of
    # this run's was ever started" apart from "something may be running and
    # this run cannot see it".
    #
    # It is this run's own record of its own control flow, and that is the point
    # of it. Every host-side substitute for this question is an inference:
    # the PID file may not have been published yet, the jailer's own process may
    # already have exited because it daemonised, and neither absence is a
    # finding. This flag has no such window — either the call below was reached
    # or it was not.
    launch_was_attempted = False
    # Narrower, and knowable for a different reason: this one says the jailer
    # process never came into being at all. It is still not a host reading — it
    # is what the launch call itself reported back. See the call site.
    launch_spawned_nothing = False
    # And the instant the launch happened, in the units a process's start time
    # is counted in. Same kind of thing as the flag above and read at the same
    # place for the same reason: this run recording its own control flow. It is
    # what lets a PID read out of a file be measured against something instead
    # of being taken on trust. ``None`` until the launch is reached, and ``None``
    # means no evidence — never "go ahead".
    launch_floor: dict[str, Any] | None = None

    # The other end of that interval. Declared out here beside the floor, and
    # not down beside the read that sets it, because the failure path below has
    # to be able to pass on whichever of the two this run got as far as taking.
    # A failure before the PID file is read leaves this ``None``, which is the
    # honest answer — *this run had not yet held a number* — and is not the same
    # statement as the floor's ``None``.
    number_read_at: dict[str, Any] | None = None

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
        # Set before the call and not after it, because "the call raised" is not
        # "nothing started". A timeout means the jailer is still running; an
        # exec that fails after the fork is reported to this process as an
        # exception too. Setting this afterwards would record exactly the window
        # it exists to close.
        launch_was_attempted = True
        # Read here and nowhere later. A floor taken after the launch would be
        # later than the guest's own start time and would turn away the one
        # process this run is entitled to stop.
        launch_floor = _the_instant_this_run_launched()
        try:
            launch = _run([jailer_binary, *plan["jailer"]["argv"]], timeout=120.0)
        except OSError as never_execed:
            # The one launch failure that really does mean nothing started, and
            # it is knowable here without reading the host. ``subprocess``
            # reports a child's failed ``exec`` back to this process through an
            # error pipe, reaps the child, and re-raises it with ``filename``
            # set to the executable it could not run. A child that *did* exec
            # cannot arrive in this handler at all: it returns a completed
            # process, or it times out, and a timeout is ``TimeoutExpired``,
            # which is not an ``OSError``.
            #
            # The test is deliberately the narrow one rather than the bare
            # ``except``. An ``OSError`` that is not about ``argv[0]`` — a pipe
            # that fails while reading output the child is already producing,
            # say — comes from after the exec succeeded, leaves this ``False``,
            # and is refused along with everything else this run cannot account
            # for.
            #
            # This branch is neither hypothetical nor rare. It is what a host
            # without the jailer installed does, which is every host that runs
            # this repository's tests — the CI runners and the development boxes
            # — though not the one host provisioned to boot on. Leaving it out
            # costs more than a leaked directory: ``vm_id`` is derived, not
            # drawn, so the jail left behind is the name the same run's next
            # attempt will claim, and the claim is ``exist_ok=False``.
            launch_spawned_nothing = never_execed.filename == jailer_binary
            raise

        # ``watched`` is the only value this run will ever signal, and it is set
        # once, here, from a file that did not exist a moment ago.
        watched: int | None = None
        why_not_this_pid = (
            "no PID file appeared within the grace window, so there is no PID "
            "this run may signal"
        )
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
                        # The other end of the interval, closed here because
                        # here is where this run first holds the number.
                        # Anything that begins after this reading began after
                        # the number was already taken, so it is not what the
                        # number was published for.
                        number_read_at = _the_instant_the_number_was_read()
                        break
            sleep(POLL_SECONDS)

        # Whose process that number names, asked once, here, against the instant
        # this run launched. Asked *here* and not later because this is the
        # closest this function ever stands to publication: the machine is
        # normally still running, so the reading exists. A start time read after
        # the guest has gone is not a later answer to the same question, it is
        # no answer at all.
        #
        # Nothing further down gets to reconsider it: ``watched_started_at``
        # stays ``None`` and every path that would signal reads ``None`` as no.
        # The name is deliberately not ``why_not_ours`` — that one is reused
        # further down for whose *jail* it is, and the two refusals are about
        # different objects.
        watched_started_at: int | None = None
        why_not_our_process = ""
        confined_to_our_jail = False
        why_not_confined = ""
        if watched is not None:
            confined_to_our_jail, why_not_confined = _confined_to_this_runs_jail(
                watched, chroot_dir
            )
            watched_started_at, why_not_our_process = _started_during_this_runs_launch(
                watched, launch_floor, number_read_at
            )
            # Both grounds, and the jail is the one that carries origin. A
            # start time inside the interval is not permission to signal on its
            # own — an unrelated process born in there reads the same — so a
            # number that fails confinement is put back to ``None`` here rather
            # than left for a later reader to weigh two verdicts against each
            # other.
            #
            # The interval keeps the reason when it is the one that refused.
            # Both findings are real and only one of them can be the headline;
            # the other is in the evidence list either way, so the one that is
            # reported is the one the reader can act on — a number that is too
            # old to be this run's says more than a root that is not the jail.
            if not confined_to_our_jail:
                watched_started_at = None
                why_not_our_process = why_not_our_process or why_not_confined

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
            {
                # The one ground about the process rather than about the file.
                # The four above establish that a jail this run holds published
                # a signallable number; none of them says the number still names
                # the machine that published it. This one is why the deadline
                # path may signal at all.
                "ground": (
                    "the process it names began while this run was launching the "
                    "jailer"
                ),
                "held": watched_started_at is not None,
                "reading": (
                    why_not_our_process
                    or (
                        f"started at {watched_started_at} clock ticks since boot, "
                        f"inside the {launch_floor.get('ticks_since_boot')}–"
                        f"{number_read_at.get('ticks_since_boot')} this run read "
                        "immediately before launching and on taking the number"
                        if launch_floor and number_read_at
                        else ""
                    )
                ),
            },
            {
                # The ground that carries origin. The one above says only when
                # something began, which an unrelated process can satisfy by
                # accident; this one says where it is, and the jail is a
                # directory this run made and claims exclusively.
                "ground": (
                    "the process it names is confined to the jail this run made "
                    "and holds"
                ),
                "held": confined_to_our_jail,
                "reading": (
                    why_not_confined
                    or f"process {watched} has {chroot_dir} as its root"
                ),
            },
        ]

        outcome = "booted"
        stopped_by_the_deadline = False
        stop_signal_sent = False
        # Which of the two ways the signal went, when one went. ``None`` while
        # nothing has been sent, and it stays ``None`` when nothing is: a run
        # that never had to stop anything did not choose a mechanism, which is a
        # different statement from having used the weaker one.
        stop_handle: str | None = None
        stop_handle_verdict: str | None = None
        stop_signal_target: int | None = None
        guest_confirmed_stopped: bool | None = None
        # What this run last *observed* about the writer, which is not the same
        # question as whether it sent a signal. None until something is looked
        # at; False once it has been seen gone; True while it is still there.
        guest_last_seen_running: bool | None = None
        left_alone_because: str | None = None

        if watched is None:
            # Not ``never_started``. That word is a finding — it says nothing was
            # put on the host — and only two things support it: that the launch
            # was never reached, and that the launch reported its own ``exec``
            # never happened. Both are this run's account of its own control
            # flow, and neither can arrive *here*. ``launch_was_attempted`` is
            # set on the line above the call, and the one error that proves
            # nothing spawned is re-raised out of its handler, so a run that
            # reaches this line has attempted a launch that did exec.
            #
            # What is left is the host declining to answer: the pid file may not
            # have been published yet, or was caught mid-write, and a host
            # declining to answer is not a host saying no. The cleanup path
            # already draws this line — it is the whole of
            # ``(launch_was_attempted and not launch_spawned_nothing)`` below.
            # The ordinary path had one word for all three arrivals, and that
            # word is what the teardown gate reads.
            outcome = OUTCOME_STARTED_AND_NOT_IDENTIFIED
            left_alone_because = why_not_this_pid
        else:
            while _still_running(watched):
                guest_last_seen_running = True
                if now() - started_at < deadline_seconds:
                    sleep(POLL_SECONDS)
                    continue
                # The deadline is here and something is still holding that
                # number. Only now does whose process it is start to matter,
                # and the order is not interchangeable: a guest that ended on
                # its own never reaches this line, so asking identity any
                # earlier would turn every ordinary boot into an unidentified
                # one and leave its jail standing.
                if watched_started_at is None:
                    # A machine was launched, it is still running, and the
                    # number it published cannot be shown to be its. That is
                    # not ``never_started`` — something did start, and saying
                    # otherwise would report ``compute_start_failed`` over a
                    # host that may well have a guest on it. Nothing is
                    # signalled and the jail stays put:
                    # ``OUTCOME_STARTED_AND_NOT_IDENTIFIED`` is in
                    # ``OUTCOMES_THAT_LEAVE_THE_HOST_RUNNING``, so the removal
                    # below refuses on its own without a second rule here.
                    outcome = OUTCOME_STARTED_AND_NOT_IDENTIFIED
                    left_alone_because = why_not_our_process
                    break
                may_signal, why_not_now = _may_signal_now(
                    pid_file,
                    watched,
                    chroot_dir=chroot_named,
                    claim=claim,
                    started_at=watched_started_at,
                )
                if not may_signal:
                    # The deadline is reached and the thing at the end of it is
                    # not demonstrably ours. Leaving a machine running is bad;
                    # killing a stranger's is worse and is not recoverable.
                    outcome = "overran_and_was_left_alone"
                    left_alone_because = why_not_now
                    break
                stop = _stop_the_process_this_run_identified(
                    watched, watched_started_at, chroot_dir=chroot_named
                )
                if stop["already_gone"]:
                    # It went on its own between the probe and the signal.
                    outcome = "booted"
                    guest_last_seen_running = False
                    break
                if not stop["signalled"]:
                    # A safe way to send it could not be had. The machine is
                    # left running and the jail is left standing, which is the
                    # same ending as a stranger — and for the same reason, that
                    # this run cannot show the thing it would signal is its own.
                    outcome = "overran_and_was_left_alone"
                    left_alone_because = stop["refused_because"]
                    stop_handle = None
                    # Which reading it refused on, carried out in the field that
                    # exists to be read rather than only inside the sentence
                    # above. A host with no ``pidfd`` at all and a host that had
                    # one and would not hand it over are different things to go
                    # and do something about, and after this path became the
                    # only ending a refusal has, leaving the field at ``None``
                    # would have made them the same record.
                    stop_handle_verdict = stop["handle_verdict"]
                    break
                stop_signal_sent = True
                stop_handle = stop["how"]
                stop_handle_verdict = stop["handle_verdict"]
                stop_signal_target = stop["signal_target"]
                guest_confirmed_stopped = _confirm_it_stopped(
                    watched,
                    started_at=watched_started_at,
                    now=now,
                    sleep=sleep,
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
            launch_was_attempted=launch_was_attempted,
            launch_spawned_nothing=launch_spawned_nothing,
            launch_floor=launch_floor,
            number_read_at=number_read_at,
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
            # The two readings the fifth ground was decided on, carried out so a
            # reader can redo the comparison instead of taking the verdict. The
            # interval is this run's, both ends of it; the start time is the
            # host's answer about the process the file named. ``None`` anywhere
            # is the refusal.
            "launch_floor": dict(launch_floor) if launch_floor else None,
            "number_read_at": dict(number_read_at) if number_read_at else None,
            "pid_started_at_ticks": watched_started_at,
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
        # And how it went, when it went. A stop through a pinned handle and a
        # stop by a re-read number are not the same evidence, and an artefact
        # that reported both as ``stop_signal_sent: true`` would be hiding the
        # difference from whoever reads it later.
        "stop_handle": stop_handle,
        "stop_handle_verdict": stop_handle_verdict,
        "stop_signal_target": stop_signal_target,
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

    The second is the direct consequence of the outcomes that mean this host may
    not be treated as free, and the reason they could not be added without
    coming here. Two of them are findings: a machine this run launched is still
    on the host. The line that followed removed the jail anyway, which is an
    ``rmtree`` of the rootfs, the work disk and the socket a live Firecracker is
    holding open. The run then returned a record saying the jail was gone, which
    it was, and saying nothing about what was using it.

    The third is not a finding but the absence of one: the launcher ran and this
    run never got a process it could name. That state used to arrive here
    wearing the word ``never_started`` and was removed like an empty jail, which
    is the same ``rmtree`` reached by assuming the missing evidence was absence.
    It is refused for the same reason and recorded differently, because "a guest
    is still running" and "nothing here can say whether one is" are different
    findings and a reader has to be able to tell them apart.

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
        if outcome == OUTCOME_STARTED_AND_NOT_IDENTIFIED:
            # Not the same sentence. The two overran outcomes know a machine is
            # there; this one knows that it does not know, and a record claiming
            # a live guest on this evidence would be the mirror image of the bug
            # being fixed — asserting the answer the run could not get.
            refused_because = (
                "the launcher ran and this run never got a process it could "
                "name, so nothing here says the jail is empty; removing it "
                "would take a work disk something may still have open"
            )
        else:
            refused_because = (
                f"the machine ended as {outcome!r}, so a guest this run started "
                "is still on the host; removing its jail would take the work "
                "disk and the socket it is using with it"
            )
        return {
            "removed": {},
            "all_gone": False,
            "failures": [],
            "refused_because": refused_because,
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
    launch_was_attempted: bool,
    launch_spawned_nothing: bool,
    launch_floor: Mapping[str, Any] | None,
    number_read_at: Mapping[str, Any] | None,
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
    was there before it launched, one appeared while it was watching, the value
    in it is one this platform can signal, and the process it names began while
    this run was launching the jailer. The jail is the strongest of those, because
    the plan puts the PID file *inside* the chroot — a jail this run does not hold
    contains another run's PID file and another run's work disk. The last is the
    only one about the process rather than about the file, and it is what stops a
    correct-looking jail whose PID file names a recycled number from producing a
    real ``SIGKILL`` against a stranger. ``launch_floor`` and ``number_read_at``
    carry it between them, and both are required and have no default for the
    third and fourth time in this signature: ``None`` is not a way to skip the
    check, and a caller that can forget either is a caller that will pass the
    launch and then silently stop checking who it is stopping.

    The two are not the same kind of argument, though, and the difference is
    worth stating because it is the opposite of what the pattern above suggests.
    ``launch_floor`` has exactly one correct value — the reading taken
    immediately before the jailer ran — and ``None`` refuses. ``number_read_at``
    is the other end of that interval, *the moment this run first held the
    number*, and this path may or may not be the thing that first held it. When
    the caller has one, it is used, because it is the earlier and therefore the
    stricter of the two available readings and because inheriting it keeps one
    interval per number rather than one per code path. When the caller has none —
    the failure landed before the watch loop ever read a PID — this path is the
    first reader and takes its own, which is honest but can be much wider if the
    failure came long after the launch. So ``None`` here means *I had not read
    it yet*, not *do not check*; the refusing value is the one handed to
    :func:`_started_during_this_runs_launch`, and it is never reached with
    nothing.

    That check is asked *after* liveness, not before. Nothing holding the number
    means nothing of this run's is running under it, which holds without any
    identity at all; asking the other way round would turn every machine that
    ended on its own into an unidentified one and keep its jail forever.

    None of that rules out PID reuse inside the interval this run was launching
    in, and this does not claim it does; see :data:`CANNOT_RULE_OUT`, which goes
    out with the record.

    Removal is gated on a second question, separate from ownership: is anything
    of this run's possibly still using this jail. Two readings answer it, and
    nothing else does.

    * ``launch_was_attempted`` is ``False`` — this run never reached the call
      that starts a machine, so there is no machine of this run's to be using
      anything. That is the case this step is *for*, and it must keep working,
      or a failure before the launch leaks a jail every time.
    * ``launch_spawned_nothing`` is ``True`` — the call was reached and reported
      back that the jailer was never executed. Same conclusion as the reading
      above, arrived at one step later, and it is what a host without the jailer
      installed produces on every call.
    * a PID this run watched was confirmed stopped.

    Everything else refuses, including the reading that looks most like an
    empty jail: the launch was reached and no usable PID ever turned up. That
    is not a finding that nothing is running. The jailer forks and execs before
    it publishes a PID file, so an absent file is consistent with a machine that
    started a moment ago, and a file holding bytes that are not a PID is a file
    something was in the middle of writing. ``pid_file.exists()`` is read here
    as evidence that something *did* start, never as evidence that nothing did;
    it has no window in the first direction and a real one in the second.

    ``launch_was_attempted`` is required and has no default for the same reason
    ``claim`` is. There is no value that is safe to assume: ``False`` permits
    removal, which is the unsafe direction, and ``True`` refuses the one case
    this step exists to handle.

    ``launch_spawned_nothing`` is required too, for a different reason. Its
    unsafe value is the one a default would have to pick — ``False`` here only
    ever refuses — but the two arguments are a pair and are only meaningful read
    together, and a default is how one of a pair silently stops tracking the
    other. It is also the narrower of the two claims and the easier to widen by
    accident, so a caller is made to say it.

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
    # Read once, here, before anything is signalled, and read again by step 3
    # from this variable rather than from the disk.
    #
    # This signal only points one way. A PID file being there at all does say
    # the jailer got far enough to write one, so something was started; whether
    # its contents are a PID this run may signal is a second question, and the
    # answer to it is not evidence about the first. The converse does *not*
    # follow. An absent PID file does not say nothing was started, because the
    # jailer forks and execs before it publishes, and a failure that lands in
    # this handler can land inside that window. So this variable is read as
    # "something is definitely running" and never as "nothing is".
    #
    # What nothing was started *does* follow from is ``launch_was_attempted``,
    # which is this run's own record of its own control flow rather than an
    # inference from the host.
    a_pid_file_appeared = holds_it and pid_file.exists()
    process: dict[str, Any] = {
        "pid_file": pid_file.as_posix(),
        "jail_held_by_this_run": holds_it,
        "jail_reading": why_not_ours,
        "launch_was_attempted": launch_was_attempted,
        "launch_spawned_nothing": launch_spawned_nothing,
        "launch_floor": dict(launch_floor) if launch_floor else None,
        "number_read_at": None,
        "number_read_at_inherited": None,
        "pid_file_appeared": a_pid_file_appeared,
        "pid": None,
        "pid_started_at_ticks": None,
        "signalled": False,
        # Which way a signal went, when one did. ``None`` covers both "nothing
        # was sent" and "nothing needed to be sent", because neither of those
        # chose a mechanism.
        "stop_handle": None,
        "stop_handle_verdict": None,
        "stop_signal_target": None,
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
        elif not a_pid_file_appeared:
            process["left_alone_because"] = (
                "no PID file is in this jail, so there is no PID this run may "
                "signal. That is a reason not to signal, and it is not a "
                "finding that nothing was started"
            )
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
                    # Inherited when the caller already held this number, taken
                    # here when it did not. Both are "the moment this run first
                    # held it"; the difference is only which code path that was.
                    #
                    # Inheriting is the stricter of the two. A reading taken
                    # here is later, and a later ceiling admits more — if the
                    # failure being cleaned up happened long after the launch,
                    # an interval ending here can be most of the run, which is
                    # the width the ordinary path was measured admitting a
                    # stranger through. Where an earlier reading exists it is
                    # therefore the right one, and it stays right even if the
                    # file has been rewritten since: a number published after
                    # that instant is refused, which is the safe direction.
                    held_at = number_read_at or _the_instant_the_number_was_read()
                    process["number_read_at"] = dict(held_at)
                    process["number_read_at_inherited"] = number_read_at is not None
                    running = _still_running(pid)
                    process["was_running"] = running
                    if not running:
                        # Asked before identity, and the order is load-bearing.
                        # Nothing holds that number, so nothing of this run's is
                        # running under it — true whether or not the process it
                        # once named was ever identified. Asking identity first
                        # would turn an ended machine into an unknown one, and
                        # an unknown one keeps its jail forever.
                        process["confirmed_stopped"] = True
                        process["left_alone_because"] = "it had already stopped"
                    else:
                        started_at, not_ours = _started_during_this_runs_launch(
                            pid, launch_floor, held_at
                        )
                        # Same two grounds as the ordinary path, in the same
                        # order of authority. Confinement is what says the
                        # process is this run's; the interval can only turn a
                        # candidate away. A failure being cleaned up is exactly
                        # where the interval is widest and least worth leaning
                        # on, so a number that is not in this run's jail is put
                        # back to ``None`` here too.
                        confined, why_not_confined = _confined_to_this_runs_jail(
                            pid, chroot_dir
                        )
                        process["confined_to_this_runs_jail"] = confined
                        if not confined:
                            started_at, not_ours = None, (not_ours or why_not_confined)
                        process["pid_started_at_ticks"] = started_at
                        if started_at is None:
                            # Something is alive on that number and this run
                            # cannot show it started it. No signal, no removal
                            # — ``confirmed_stopped`` stays ``None``, which the
                            # gate below reads as a refusal — and the jail stays
                            # on disk for a person to look at.
                            process["left_alone_because"] = (
                                f"{not_ours} — and this run does not stop what "
                                "it cannot show it started"
                            )
                        else:
                            stop = _stop_the_process_this_run_identified(
                                pid, started_at, chroot_dir=chroot_dir
                            )
                            process["signalled"] = stop["signalled"]
                            process["stop_handle"] = stop["how"]
                            process["stop_handle_verdict"] = stop["handle_verdict"]
                            process["stop_signal_target"] = stop["signal_target"]
                            if stop["already_gone"]:
                                # It ended between being identified and being
                                # taken hold of. Nothing was sent and nothing
                                # needed to be: the machine is stopped, which is
                                # an observation and not an assumption.
                                process["confirmed_stopped"] = True
                                process["left_alone_because"] = (
                                    "it stopped on its own between this run "
                                    "identifying it and taking hold of it"
                                )
                            elif not stop["signalled"]:
                                # No safe way to send it. Not confirmed stopped,
                                # because it was not stopped — and the deadline
                                # is not waited out, because there is nothing on
                                # the way that waiting could observe arriving.
                                process["confirmed_stopped"] = False
                                process["left_alone_because"] = stop[
                                    "refused_because"
                                ]
                                failures.append(
                                    {
                                        "what": "stop this run's machine",
                                        "path": pid_file.as_posix(),
                                        "error": stop["refused_because"],
                                    }
                                )
                            else:
                                stopped = _confirm_it_stopped(
                                    pid, started_at=started_at, now=now, sleep=sleep
                                )
                                process["confirmed_stopped"] = stopped
                                if not stopped:
                                    failures.append(
                                        {
                                            "what": (
                                                "confirm this run's machine stopped"
                                            ),
                                            "path": pid_file.as_posix(),
                                            "error": (
                                                "SIGKILL was sent and the process "
                                                "was still there "
                                                f"{STOP_CONFIRMATION_SECONDS}s "
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
        # Not the same rule the ordinary path applies, and the comment that used
        # to say it was is the thing the independent review caught. The ordinary
        # path asks ``outcome in OUTCOMES_THAT_LEAVE_THE_HOST_RUNNING or
        # guest_confirmed_stopped is False``; no ``outcome`` exists here, because
        # the run failed before one was assigned, so that vocabulary is not
        # available and this branch is written in the two readings that are.
        #
        # The claim that *is* true is narrower and worth having in its place:
        # this branch and the one below it together refuse a superset of what
        # the ordinary path refuses. Step 1 either declined to signal or sent one
        # and could not confirm it landed; either way the last thing this run
        # observed was a live process holding this jail's work disk and socket
        # open.
        refused_to_destroy = (
            "this run's own machine was last seen running and was never "
            "confirmed stopped, so removing its jail would take the disk and "
            "socket it is using with it"
        )
    elif (
        (launch_was_attempted and not launch_spawned_nothing) or a_pid_file_appeared
    ) and process["confirmed_stopped"] is not True:
        # The gap the review found, in the state that looks most like an empty
        # jail: this run reached the launch and never got a PID it could watch,
        # so ``was_running`` is still None and the branch above lets it through.
        #
        # None is not False. It says this run never looked at a process, and the
        # three ways of arriving here are a PID file that is absent, one that
        # could not be read, and one holding bytes that are not a PID. The last
        # two are a file something was in the middle of writing. The first is the
        # window between fork and publication. None of the three is a finding
        # that nothing is running, and the record said as much three steps ago —
        # ``copy_integrity`` is ``unverified`` on exactly this path, which is
        # this module's own words for "what was writing to that disk cannot be
        # named from here". Removing the jail would be the other half of the same
        # return value contradicting it.
        #
        # ``a_pid_file_appeared`` is in the condition as well as
        # ``launch_was_attempted`` because a PID file in a jail this run claimed
        # and never launched into is a state nothing here can explain, and an
        # unexplained writer is treated the same as a known one.
        #
        # ``launch_spawned_nothing`` is the one subtraction from that, and it is
        # subtracted from the reaching-the-launch half only. It does not soften
        # the rule; it names a case the rule was never about. "The call raised"
        # is not "nothing started" in general — that is why the flag above is set
        # before the call and not after — but one launch failure does carry its
        # own proof, because ``subprocess`` can only raise ``OSError`` about
        # ``argv[0]`` when the ``exec`` never succeeded. A PID file still refuses
        # even then: if something wrote one into this jail, this run's account of
        # its own launch does not explain it, and the unexplained writer wins.
        refused_to_destroy = (
            "this run started something and never saw a PID it could watch, so "
            "nothing here can say whether that machine is still writing to this "
            "jail; an absent or unreadable PID file is not a stopped machine"
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
