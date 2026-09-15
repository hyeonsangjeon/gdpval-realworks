"""Signalling, stopping and cleaning up only what this run itself started.

Four things go wrong on the way to a real microVM, and all four have the same
shape: the launcher acts on a process or a directory without first establishing
that it is *this run's*. On a host with one machine that is invisible. On a host
with two — which is the whole point of per-call isolation — it means one run
SIGKILLs another run's guest, copies over its live work disk, and then removes
its jail.

The rule these tests pin is narrow and worth stating plainly: **absence of a PID
file is not proof of ownership.** The plan puts the PID file *inside* the chroot
(``<chroot>/firecracker.pid``) and names the chroot as the thing to remove
afterwards, so a jail that was already there carries both a stranger's PID and a
stranger's disk, and the damage from proceeding is not one signal but three
destructive operations.

Nothing here boots anything. ``os.kill`` is stood in for so the probes and the
signals are observable, and the jailer is stood in for because this box has no
``/dev/kvm``. Everything else — the plan builder, ``place_the_images``,
``first_boot``'s own control flow, the real ``OneCallMachine`` — is the
production code.

Pre-registration, written before the fix: ``docs/agentic_v2_ownership_and_teardown.md``.
"""

from __future__ import annotations

import errno
import functools
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from core.agentic_v2_contract import TOOL_CONTRACT_VERSION, AgenticV2Profile
from core.agentic_v2_first_boot import (
    WORK_DISK_RESULTS,
    BootAbandoned,
    BootRefused,
    _clean_up_after_a_failure,
    _the_instant_this_run_launched,
    first_boot,
    the_host_was_left_running,
)
from core import agentic_v2_first_boot
from core.agentic_v2_microvm_backend import (
    EXEC_RECORD_DIR,
    AgenticV2MicroVMBackend,
    GuestImage,
)
from core.agentic_v2_microvm_launch import build_launch_plan
from core.agentic_v2_one_call_machine import OneCallMachine
from core.agentic_v2_substrate import AgenticV2SubstrateManifest

STRANGER = 424242
"""A PID this run did not start. Never signalled, in any test here."""

OURS = 4242
"""The PID the stand-in jailer publishes, and the only one given an identity."""


def _a_stand_in_guest_with_an_identity(monkeypatch, *pids: int) -> None:
    """Let the invented PIDs answer the questions a real guest answers.

    The launcher will not signal a process it cannot show it started, and a
    number a test made up names nothing on the host — so a stand-in that only
    reports *alive* is half a guest. This supplies the other half: for the PIDs
    named here, "when did you start" answers with a host clock reading taken
    **while the run was launching**, which is where a real guest's start time
    falls.

    **When that reading is taken is the whole of this helper.** The run bounds
    ownership from both ends — a floor read immediately before the jailer runs,
    a ceiling read the moment it first holds a number — so a stand-in stamped
    outside that interval is not a guest this run could have started, and the
    launcher is right to refuse it. The two hooks below are exactly those two
    instants, and the stamp is taken *after* the floor is read and *before* the
    ceiling is, which is the order the real events happen in. Whichever of the
    two the code under test reaches first, the answer lands inside.

    This used to stamp the clock the first time the start time was *asked for*,
    which is after the run already holds the number — a process born after the
    run observed it, which cannot exist. Nothing caught it, because with one
    bound there was nothing an impossibly-late start time could fail.

    **The answer is remembered, and that is the point, not an optimisation.** A
    real process's start time never moves; answering with a fresh clock reading
    each time would make the guest look like a different process on every probe,
    and the launcher would correctly refuse to signal it. Getting this wrong
    makes a working guard look broken.

    Only the PIDs listed. :data:`STRANGER` is deliberately never among them —
    a process this run cannot account for is exactly what it stands for.
    """
    known = set(pids)
    real = agentic_v2_first_boot._when_that_process_started
    real_floor = agentic_v2_first_boot._the_instant_this_run_launched
    real_ceiling = agentic_v2_first_boot._the_instant_the_number_was_read
    real_confinement = agentic_v2_first_boot._confined_to_this_runs_jail
    born: dict[str, int | None] = {}

    def confined(pid: int, chroot_dir) -> tuple[bool, str]:
        """"Are you inside this run's jail" — the other half of being a guest.

        A real guest is put in the jail by the jailer, which needs privileges a
        test process does not have, so an invented PID cannot be made to answer
        this truthfully here. What the reading actually does against real
        processes is measured directly in
        ``test_v2_ownership_is_bound_to_the_launch``.

        Anything not named here is asked for real, so a stranger is refused on
        the host's own answer rather than on this helper's say-so.
        """
        if pid in known:
            return True, ""
        return real_confinement(pid, chroot_dir)

    def _born_now() -> None:
        if "ticks" not in born:
            reading = agentic_v2_first_boot._the_host_clock_in_ticks()
            born["ticks"] = reading["ticks_since_boot"]

    def floor() -> dict:
        reading = real_floor()
        _born_now()
        return reading

    def ceiling() -> dict:
        _born_now()
        return real_ceiling()

    def started(pid: int) -> int | None:
        if pid not in known:
            return real(pid)
        _born_now()
        return born["ticks"]

    monkeypatch.setattr(
        "core.agentic_v2_first_boot._when_that_process_started", started
    )
    monkeypatch.setattr(
        "core.agentic_v2_first_boot._the_instant_this_run_launched", floor
    )
    monkeypatch.setattr(
        "core.agentic_v2_first_boot._the_instant_the_number_was_read", ceiling
    )
    monkeypatch.setattr(
        "core.agentic_v2_first_boot._confined_to_this_runs_jail", confined
    )


def _as_if_the_jailer_had_chrooted(monkeypatch, in_the_jail) -> None:
    """Answer the confinement question for processes a stand-in jailer placed.

    The run's positive ground for ownership is that the process it is about to
    signal has this run's own jail as its root — a jail it created and holds a
    claim on. That is established by the *jailer*, which chroots the guest, and
    chrooting needs a privilege a test process does not have. So for the real
    processes a stand-in jailer starts, this answers the way the host would have
    answered if the jailer had been the real one.

    ``in_the_jail`` is a live container of PIDs, not a snapshot: the stand-in
    jailer adds to it as it starts each guest, which happens after this is
    installed.

    **Only what the stand-in jailer put there.** Every other number — a stranger
    in an old PID file, a real sleeper this run did not launch, an invented one —
    is asked for real, so it is refused on the host's own reading. That is what
    keeps this from being a way to make a refusal disappear.
    """
    real_confinement = agentic_v2_first_boot._confined_to_this_runs_jail

    def confined(pid: int, chroot_dir) -> tuple[bool, str]:
        if pid in in_the_jail:
            return True, ""
        return real_confinement(pid, chroot_dir)

    monkeypatch.setattr(
        "core.agentic_v2_first_boot._confined_to_this_runs_jail", confined
    )


@pytest.fixture
def plan(tmp_path, monkeypatch):
    """A real plan from the real builder, over files that exist."""
    for name in ("firecracker", "vmlinux", "rootfs.ext4", "work.ext4"):
        path = tmp_path / name
        path.write_bytes(b"not really an image, but a readable file")
        path.chmod(0o755)
    monkeypatch.setattr(os, "chown", lambda *a, **k: None)
    return build_launch_plan(
        vm_id="test-own",
        firecracker_binary=tmp_path / "firecracker",
        kernel_path=tmp_path / "vmlinux",
        rootfs_path=tmp_path / "rootfs.ext4",
        work_disk_path=tmp_path / "work.ext4",
        uid=997,
        gid=997,
        vcpu_count=1,
        cgroup_version=2,
        chroot_base=tmp_path / "jail",
    )


def _a_second_plan(plan, tmp_path, *, vm_id="test-own-2"):
    """The same host and images under a second name.

    Needed wherever one test boots twice. A boot that ends without a pid file no
    longer removes its jail, so the first attempt's ``vm_id`` stays claimed and a
    second attempt on it is refused before anything starts — which is the point
    of ``exist_ok=False`` and not something to work around by deleting the jail
    the run just declined to delete.
    """
    return build_launch_plan(
        vm_id=vm_id,
        firecracker_binary=tmp_path / "firecracker",
        kernel_path=tmp_path / "vmlinux",
        rootfs_path=tmp_path / "rootfs.ext4",
        work_disk_path=tmp_path / "work.ext4",
        uid=997,
        gid=997,
        vcpu_count=1,
        cgroup_version=2,
        chroot_base=tmp_path / "jail",
    )


class _Clock:
    def __init__(self):
        self.t = 0.0

    def now(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.t += seconds


class _Signals:
    """Stands in for the kernel's signalling, and records every call that reached it.

    Signal 0 is a liveness probe and never terminates anything; anything else is
    a real signal. Keeping the two apart in the record is the point — "a signal
    was sent" and "the process is gone" are different observations and the code
    under test is required to report them separately.

    ``dies_after`` is how many probes after the real signal still report the
    process alive. ``None`` means it never reports dead, which is the case the
    finite confirmation deadline exists for.

    **It stands in for the handle path too, and it has to.** This class is not a
    spy but a simulator: its liveness answer is gated on ``was_signalled``,
    which only the ``os.kill`` path used to set. On a kernel with ``pidfd`` the
    module signals through a pinned handle, ``os.kill`` is never reached, the
    simulated liveness never flips, and the confirmation deadline runs out
    against a machine the simulation was told to kill. That produced a
    ``guest_confirmed_stopped`` of ``False`` on CI for a stop that had in fact
    happened. The assertion was right; the simulation was a transport behind.
    """

    def __init__(self, *, starts_alive=True, dies_after=0, kill_raises=None):
        self.sent: list[tuple[int, int]] = []
        self.starts_alive = starts_alive
        self.dies_after = dies_after
        self.kill_raises = kill_raises
        self.was_signalled = False
        self.probes_after_the_signal = 0
        self.by_handle: list[tuple[int, int]] = []
        self._behind: dict[int, int] = {}

    def install(self, monkeypatch) -> "_Signals":
        """Replace every way the module has of signalling, not just the old one.

        ``os.pidfd_open`` is replaced as well. Left real, it would be asked for
        a handle on a number this simulation invented, answer
        ``ProcessLookupError``, and the module would correctly read that as "the
        process is gone" — turning a simulated live machine into an absent one
        for reasons that have nothing to do with what the test is asking.
        """
        monkeypatch.setattr(os, "kill", self)
        monkeypatch.setattr(os, "pidfd_open", self._open_a_handle, raising=False)
        monkeypatch.setattr(
            signal, "pidfd_send_signal", self._through_a_handle, raising=False
        )
        monkeypatch.setattr(
            agentic_v2_first_boot,
            "_the_process_a_handle_names",
            lambda handle: self._behind.get(handle),
        )
        return self

    def _open_a_handle(self, pid, *rest):
        """A real descriptor standing for a real one.

        Not an invented number: the code under test closes what it opens, and a
        number nothing opened fails that close with ``EBADF``. Handing back an
        actual descriptor keeps the close real, so a handle this run forgets to
        release still shows up as a leak rather than as an error in the
        stand-in.
        """
        if not self.starts_alive:
            raise ProcessLookupError(3, "No such process")
        handle = os.open(os.devnull, os.O_RDONLY)
        self._behind[handle] = pid
        return handle

    def _through_a_handle(self, handle, sig, *rest):
        pid = self._behind.get(handle)
        if pid is None:
            raise OSError(errno.EBADF, "not a handle this simulation opened")
        self.by_handle.append((pid, sig))
        return self(pid, sig)

    def __call__(self, pid, sig):
        self.sent.append((pid, sig))
        if sig == 0:
            if not self.starts_alive:
                raise ProcessLookupError(3, "No such process")
            if not self.was_signalled:
                return None
            self.probes_after_the_signal += 1
            if self.dies_after is None:
                return None
            if self.probes_after_the_signal > self.dies_after:
                raise ProcessLookupError(3, "No such process")
            return None
        if self.kill_raises is not None:
            raise self.kill_raises
        self.was_signalled = True
        return None

    @property
    def real_signals(self) -> list[tuple[int, int]]:
        return [(pid, sig) for pid, sig in self.sent if sig != 0]

    def anything_reached_kill_for(self, pid: int) -> bool:
        return any(sent_pid == pid for sent_pid, _ in self.sent)


def _jailer_writing(plan, pid=4242):
    def jailer(argv, timeout=300.0):
        Path(plan["host_side"]["pid_file"]).write_text(f"{pid}\n")
        return subprocess.CompletedProcess(argv, 0, "", "")

    return jailer


def _jailer_writing_that_then_fails(plan, pid=4242):
    """Starts a machine this run owns, then fails — so cleanup has work to do."""

    def jailer(argv, timeout=300.0):
        Path(plan["host_side"]["chroot_dir"]).mkdir(parents=True, exist_ok=True)
        Path(plan["host_side"]["pid_file"]).write_text(f"{pid}\n")
        raise subprocess.TimeoutExpired(argv, 120.0)

    return jailer


def _jailer_writing_nothing(argv, timeout=300.0):
    return subprocess.CompletedProcess(argv, 0, "", "")


def _jailer_writing_a_pid_nobody_may_signal(plan):
    """Start, write a PID this run is forbidden to signal, then fail.

    ``0`` is the value ``_a_pid_this_may_signal`` turns away first, because
    ``kill(0, …)`` signals the launcher's own process group. Cleanup therefore
    never looks at any process at all — ``was_running`` stays ``None`` — and yet
    it still copies the work disk out, because what blocks the copy is a jail
    that was already there and this jail was not. That combination is a row the
    cleanup predicate did not have.
    """

    def jailer(argv, timeout=300.0):
        Path(plan["host_side"]["chroot_dir"]).mkdir(parents=True, exist_ok=True)
        Path(plan["host_side"]["pid_file"]).write_text("0\n")
        raise subprocess.TimeoutExpired(argv, 120.0)

    return jailer


def _a_clock_that_swaps_the_pid_file(pid_file: Path) -> _Clock:
    """D4's clock, reused: the watched PID file is replaced mid-flight.

    The run reaches its deadline with the guest still visibly running and with
    no way to show the file still names what it started, so it declines to
    signal. Nothing is stopped and nothing is confirmed — which is the state the
    copy label used to read as "nothing was writing".
    """

    class _Replacing(_Clock):
        def sleep(self, seconds):
            super().sleep(seconds)
            if self.t > 1.0 and pid_file.exists():
                pid_file.write_text(f"{STRANGER}\n")

    return _Replacing()


def _finished(*, exit_status="0"):
    results = {name: None for name in WORK_DISK_RESULTS}
    results["/out/stdout"] = "this ran inside the guest\n"
    results["/out/exit_status"] = exit_status
    return results


def _boot(plan, tmp_path, monkeypatch, *, jailer, signals, reader=None, clock=None):
    """Run the real :func:`first_boot` with only the host's two edges stood in.

    ``_still_running`` is deliberately **not** replaced. It is the function that
    calls ``os.kill(pid, 0)``, and every question here is about which values
    reach that call — a test that stubs it out cannot see the thing it is for.
    """
    clock = clock or _Clock()
    monkeypatch.setattr("core.agentic_v2_first_boot._run", jailer)
    signals.install(monkeypatch)
    _a_stand_in_guest_with_an_identity(monkeypatch, OURS)
    monkeypatch.setattr(
        "core.agentic_v2_first_boot.files_out_of_work_disk",
        reader or (lambda image, names, **kw: _finished()),
    )
    return first_boot(
        plan,
        jailer_binary="jailer",
        kernel=tmp_path / "vmlinux",
        rootfs=tmp_path / "rootfs.ext4",
        work_disk=tmp_path / "work.ext4",
        uid=997,
        gid=997,
        now=clock.now,
        sleep=clock.sleep,
    )


def _a_jail_someone_else_is_using(plan) -> Path:
    """Lay down the jail a previous run with this same vm_id left behind."""
    chroot = Path(plan["host_side"]["chroot_dir"])
    chroot.mkdir(parents=True)
    (chroot / "work.ext4").write_bytes(b"another run is writing to this disk")
    Path(plan["host_side"]["pid_file"]).write_text(f"{STRANGER}\n")
    return chroot


# --------------------------------------------------------------------------
# the production call path, assembled the way the product assembles it
# --------------------------------------------------------------------------


def _a_real_machine(tmp_path, monkeypatch) -> tuple[OneCallMachine, Path, Path]:
    """A genuine :class:`OneCallMachine` over readable files in a temp tree.

    Nothing here is a stand-in for code under test. ``os.chown`` is replaced
    because the plan chowns placed images to the account the jailer drops to and
    that needs root, which this box is not; ``chroot_base`` is redirected through
    ``build_plan`` — the parameter that exists for it — so no test writes under
    /srv on a developer's machine.
    """
    host = tmp_path / "host"
    host.mkdir()
    for name in ("firecracker", "vmlinux", "rootfs.ext4"):
        image = host / name
        image.write_bytes(b"not really an image, but a readable file")
        image.chmod(0o755)
    jail_base = tmp_path / "jail"
    monkeypatch.setattr(os, "chown", lambda *a, **k: None)

    machine = OneCallMachine(
        kernel=host / "vmlinux",
        rootfs=host / "rootfs.ext4",
        firecracker_binary=host / "firecracker",
        uid=997,
        gid=997,
        vcpu_count=1,
        cgroup_version=2,
        scratch=tmp_path / "scratch",
        build_plan=functools.partial(build_launch_plan, chroot_base=jail_base),
    )
    return machine, jail_base, host


def _backend_over(tmp_path, machine) -> AgenticV2MicroVMBackend:
    return AgenticV2MicroVMBackend(
        root=tmp_path / "session",
        profile=AgenticV2Profile(
            tool_contract_version=TOOL_CONTRACT_VERSION,
            policy_profile_id="offline-full-v1",
            foundation_only=True,
        ),
        image=GuestImage(
            reference="ghcr.io/hyeonsangjeon/gdpval-sandbox",
            digest="sha256:" + "e" * 64,
            kernel_sha256="a" * 64,
            rootfs_sha256="b" * 64,
        ),
        boot_one_command=machine,
        substrate_manifest=AgenticV2SubstrateManifest.load(
            Path("sandbox/agentic_v2_capabilities.json")
        ),
    )


def _a_jailer_that_starts_then_dies(jail_base: Path, pid: int = 4242):
    """Write a PID file into the jail that was just placed, then fail.

    The machine name is decided by ``OneCallMachine`` at call time, so the jail
    is found rather than predicted. By the time this runs the images are in it,
    which is also what makes the "it was really placed" assertion meaningful.
    The file's name is the binary's own with ``.pid`` appended — the jailer's
    rule, not a convention chosen here.
    """

    def jailer(argv, timeout=300.0):
        _the_jail_just_placed(jail_base, pid)
        raise subprocess.TimeoutExpired(argv, 120.0)

    return jailer


def _a_jailer_that_boots_and_exits(jail_base: Path, pid: int = 4242):
    """The ordinary case: a machine starts, runs, and is gone by the first probe."""

    def jailer(argv, timeout=300.0):
        _the_jail_just_placed(jail_base, pid)
        return subprocess.CompletedProcess(argv, 0, "", "")

    return jailer


def _the_jail_just_placed(jail_base: Path, pid: int) -> Path:
    roots = sorted(jail_base.glob("firecracker/*/root"))
    assert roots, "nothing was placed, so there is no boot to stand in for"
    (roots[-1] / "firecracker.pid").write_text(f"{pid}\n")
    return roots[-1]


# --------------------------------------------------------------------------
# C1-C4 — the controls. If any of these is red, nothing below counts.
# --------------------------------------------------------------------------


def test_c1_a_normal_boot_in_a_fresh_jail_is_unchanged(plan, tmp_path, monkeypatch):
    """The guest exits on its own: no signal, no refusal, the jail comes down."""
    signals = _Signals(starts_alive=False)
    result = _boot(
        plan, tmp_path, monkeypatch, jailer=_jailer_writing(plan), signals=signals
    )

    assert result["outcome"] == "booted"
    assert result["command_exit_status"] == 0
    assert signals.real_signals == []
    assert result["teardown"]["all_gone"] is True
    assert not Path(plan["host_side"]["chroot_dir"]).exists()


def test_c2_an_owned_guest_that_overruns_is_still_stopped(plan, tmp_path, monkeypatch):
    """The deadline still works. Ownership is a gate on it, not a way out of it."""
    signals = _Signals(dies_after=0)
    result = _boot(
        plan, tmp_path, monkeypatch, jailer=_jailer_writing(plan), signals=signals
    )

    assert result["outcome"] == "stopped_by_the_deadline"
    assert result["stopped_by_the_deadline"] is True
    assert signals.real_signals == [(4242, signal.SIGKILL)]
    assert result["stop_signal_sent"] is True
    assert result["guest_confirmed_stopped"] is True


def test_c3_a_guest_that_never_reports_dead_is_not_called_confirmed(
    plan, tmp_path, monkeypatch
):
    """The false-success control.

    A checker that will say ``confirmed_stopped`` for a process it can still see
    would pass every other test in this file while proving nothing. This is the
    case that catches it, and it must end on a finite deadline rather than
    spinning.
    """
    signals = _Signals(dies_after=None)
    result = _boot(
        plan, tmp_path, monkeypatch, jailer=_jailer_writing(plan), signals=signals
    )

    assert result["stop_signal_sent"] is True
    assert result["guest_confirmed_stopped"] is False
    assert result["outcome"] != "stopped_by_the_deadline"
    assert result["stopped_by_the_deadline"] is False


def test_c4_a_usable_pid_does_reach_os_kill(plan, tmp_path, monkeypatch):
    """The reachability control.

    Every "no signal was sent" assertion below is worthless if the probe never
    gets near ``os.kill`` in the first place. A convertible PID must arrive.
    """
    signals = _Signals(dies_after=0)
    _boot(plan, tmp_path, monkeypatch, jailer=_jailer_writing(plan), signals=signals)

    assert signals.anything_reached_kill_for(4242)
    assert (4242, 0) in signals.sent


# --------------------------------------------------------------------------
# D1-D6 — ownership, on both paths
# --------------------------------------------------------------------------


def test_d1_a_pid_file_from_before_this_run_is_never_signalled(
    plan, tmp_path, monkeypatch
):
    """A's F1, the scenario verbatim: a stale PID file and a launcher that
    returns normally, so the *deadline* path is the one that decides.

    That path had no ownership check at all. ``pid_file_was_already_there`` was
    read in ``first_boot`` and then consumed only inside
    ``_clean_up_after_a_failure``, which a clean launch never reaches — so the
    deadline signalled ``(424242, 0)`` five times and then
    ``(424242, SIGKILL)``, and reported ``stopped_by_the_deadline`` about a
    machine it had never started.

    The outcome now is earlier and stronger than "it declines to signal": the
    PID file is *inside* the chroot, so a stale one means a jail that is already
    on disk, and the run refuses before it places anything. The stranger is not
    signalled, which is what F1 was about, and its disk is not touched either.
    """
    Path(plan["host_side"]["chroot_dir"]).mkdir(parents=True)
    Path(plan["host_side"]["pid_file"]).write_text(f"{STRANGER}\n")
    signals = _Signals(dies_after=None)

    with pytest.raises(BootRefused) as refused:
        _boot(
            plan, tmp_path, monkeypatch, jailer=_jailer_writing_nothing, signals=signals
        )

    assert not signals.anything_reached_kill_for(STRANGER)
    assert signals.sent == []
    assert "creates nothing and starts nothing" in str(refused.value)
    assert Path(plan["host_side"]["pid_file"]).read_text().strip() == str(STRANGER)


def test_d2_a_jail_that_is_already_there_is_refused_before_anything_is_written(
    plan, tmp_path, monkeypatch
):
    """The root of the resume collision, and the most destructive case.

    ``--run-id``'s own help says "Reuse it to resume", ``OneCallMachine.calls``
    restarts at zero, so a resumed run rebuilds the same ``vm_id`` and lands on
    the same chroot. Proceeding would ``copy2`` over a live work disk and then
    ``rmtree`` the jail it belongs to.
    """
    chroot = _a_jail_someone_else_is_using(plan)
    before = (chroot / "work.ext4").read_bytes()
    signals = _Signals()

    with pytest.raises(BootRefused, match="jail"):
        _boot(
            plan, tmp_path, monkeypatch, jailer=_jailer_writing(plan), signals=signals
        )

    assert (chroot / "work.ext4").read_bytes() == before
    assert Path(plan["host_side"]["pid_file"]).read_text().strip() == str(STRANGER)
    assert signals.sent == []


def test_d3_resuming_the_same_run_id_rebuilds_the_same_machine_name():
    """Why D2 is a workflow and not a corner case.

    No files and no boot — this is the arithmetic that makes two runs collide.
    """
    first = OneCallMachine(
        kernel="k",
        rootfs="r",
        firecracker_binary="f",
        uid=997,
        gid=997,
        vcpu_count=1,
        cgroup_version=2,
        scratch="/tmp/does-not-need-to-exist",
        session="agentic-v2-trial-30-1757800000",
    )
    resumed = OneCallMachine(
        kernel="k",
        rootfs="r",
        firecracker_binary="f",
        uid=997,
        gid=997,
        vcpu_count=1,
        cgroup_version=2,
        scratch="/tmp/does-not-need-to-exist",
        session="agentic-v2-trial-30-1757800000",
    )

    first.calls = 0
    assert resumed.calls == 0
    assert resumed.name_the_machine() == first.name_the_machine()


def test_d4_a_pid_file_replaced_after_it_was_watched_is_not_signalled(
    plan, tmp_path, monkeypatch
):
    """Appearing during this run is necessary but not sufficient.

    The file this run watched appear can be replaced before the deadline fires.
    What is signalled has to be what was read, re-checked at the moment of the
    signal rather than assumed to have stayed put.
    """
    pid_file = Path(plan["host_side"]["pid_file"])

    class _ReplacingClock(_Clock):
        def sleep(self, seconds):
            super().sleep(seconds)
            if self.t > 1.0 and pid_file.exists():
                pid_file.write_text(f"{STRANGER}\n")

    signals = _Signals(dies_after=None)
    result = _boot(
        plan,
        tmp_path,
        monkeypatch,
        jailer=_jailer_writing(plan),
        signals=signals,
        clock=_ReplacingClock(),
    )

    assert not signals.anything_reached_kill_for(STRANGER)
    assert result["stop_signal_sent"] is False
    assert result["pid_file"]["owned_by_this_run"] is False


def test_d5_cleanup_leaves_a_jail_this_run_did_not_create_alone(
    plan, tmp_path, monkeypatch
):
    """The same refusal on the exception path, for the chroot rather than the PID.

    ``first_boot`` now turns this case away before it places anything, so the
    guard below it is never reached through a boot. It is called directly here
    on purpose: the two paths are supposed to apply *one* ownership rule, and a
    guard that is only unreachable is not a guard that holds. All three
    destructive operations are checked — the stranger is not signalled, its disk
    is not copied out, and its jail is still there afterwards.

    The claim handed in is one this run holds for some *other* jail, which is
    the honest shape of this scenario: the jail on disk carries no ownership
    record of this run's, so every step has to read that as "not mine" rather
    than as "unclaimed, therefore free".
    """
    chroot = _a_jail_someone_else_is_using(plan)
    before = (chroot / "work.ext4").read_bytes()
    signals = _Signals(dies_after=None)
    signals.install(monkeypatch)
    salvage = {"returned_copy": None, "results_read": False, "copied_while_running": False}

    teardown = _clean_up_after_a_failure(
        host_side=plan["host_side"],
        pid_file=Path(plan["host_side"]["pid_file"]),
        claim={"nonce": "a-nonce-this-jail-has-never-carried", "vm_id": plan["vm_id"]},
        # False on purpose, and it is the weaker of the two values here. With
        # True the launch branch would also refuse, and this test would pass
        # even if ownership had stopped gating removal entirely. False leaves
        # ownership as the only thing that can produce the refusal below.
        launch_was_attempted=False,
        launch_spawned_nothing=False,
        # Read before the ownership check, so it never gets as far as mattering
        # here — but it is required and has no default, and passing the real
        # reading rather than ``None`` keeps ownership the only thing that can
        # produce the refusal below.
        launch_floor=_the_instant_this_run_launched(),
        # The other end of the same interval. Like the floor above it is
        # read before the ownership check can matter here, and ``None``
        # says only that nothing had read a PID yet — this path would take
        # its own reading if it got that far, which it does not.
        number_read_at=None,
        work_disk=tmp_path / "work.ext4",
        salvage=salvage,
    )

    assert signals.sent == []
    assert (chroot / "work.ext4").read_bytes() == before
    assert chroot.exists()
    assert teardown["process"]["signalled"] is False
    assert teardown["process"]["jail_held_by_this_run"] is False
    assert "another run's" in teardown["process"]["left_alone_because"]
    assert salvage["returned_copy"] is None
    assert teardown["removed"] == {}
    assert teardown["destroy_refused_because"]
    assert not Path(str(tmp_path / "work.ext4") + ".returned").exists()


def test_d6_ownership_is_recorded_as_evidence_both_when_it_holds_and_when_it_does_not(
    plan, tmp_path, monkeypatch
):
    """Ownership is evidence, not a boolean nobody can audit.

    The falsifier written into the pre-registration was "ownership was claimed
    and the only ground was that no PID file was there". So the record has to
    carry the individual grounds *and* what stays unprovable — on both answers.
    A run that is granted ownership still cannot rule out everything. What is
    left is narrower than it was: the process has to be inside the jail this run
    created and holds an exclusive claim on, so what the evidence cannot
    separate is a second jailer run against that same jail from outside this
    run. A number handed on to some unrelated process born after this run
    launched no longer reads the same from here, because that process is not in
    the jail.

    Four of the six grounds are about the *file*; the last two are about the
    *process*, and both are needed before the deadline path may signal
    anything. They are not interchangeable — the sixth, confinement to this
    run's jail, is what says the process is this run's, and the fifth can only
    turn a candidate away.
    """
    refused = _boot(
        plan,
        tmp_path,
        monkeypatch,
        jailer=_jailer_writing_nothing,
        signals=_Signals(dies_after=None),
    )

    evidence = refused["pid_file"]
    assert evidence["owned_by_this_run"] is False
    assert [g["held"] for g in evidence["ownership_grounds"]] == [
        True,
        True,
        False,
        False,
        # No PID file appeared, so there is no process to place in time and
        # none to find inside the jail either.
        False,
        False,
    ]
    assert "confined to this run's jail" in evidence["cannot_rule_out"]
    assert evidence["left_alone_because"]

    # Its own vm_id, and that is now a requirement rather than tidiness. The
    # refused boot above leaves its jail on the disk, because a launcher that ran
    # and published no pid file has not said the jail is empty. The name stays
    # claimed, and ``claim_the_jail`` is ``exist_ok=False``.
    second = _a_second_plan(plan, tmp_path)
    owned = _boot(
        second,
        tmp_path,
        monkeypatch,
        jailer=_jailer_writing(second),
        signals=_Signals(),
    )

    granted = owned["pid_file"]
    assert granted["owned_by_this_run"] is True
    assert len(granted["ownership_grounds"]) == 6
    assert all(g["held"] for g in granted["ownership_grounds"])
    # The fifth ground says *while*, not *after*. One bound would have read
    # "after this run launched", which is true of every process on the host that
    # is younger than the floor; what is recorded here is the interval.
    assert (
        "began while this run was launching"
        in granted["ownership_grounds"][4]["ground"]
    )
    # And the sixth is the one that makes the verdict a claim about this run's
    # own machine rather than about a window in time.
    assert (
        "confined to the jail this run made and holds"
        in granted["ownership_grounds"][5]["ground"]
    )
    assert granted["left_alone_because"] is None
    assert "confined to this run's jail" in granted["cannot_rule_out"]


# --------------------------------------------------------------------------
# D7-D10 — what may be handed to os.kill, on both paths
# --------------------------------------------------------------------------

NOT_A_PID_THIS_MAY_SIGNAL = [
    pytest.param("0", id="zero-is-this-whole-process-group"),
    pytest.param("-1", id="minus-one-is-everything-this-user-may-signal"),
    pytest.param("-12345", id="a-negative-number-is-a-process-group"),
    pytest.param("2147483648", id="one-past-what-this-platform-can-convert"),
    pytest.param("99999999999999999999", id="twenty-digits"),
    pytest.param("not-a-pid", id="not-a-number"),
    pytest.param("", id="empty"),
    pytest.param("  ", id="whitespace"),
]


@pytest.mark.parametrize("written", NOT_A_PID_THIS_MAY_SIGNAL)
def test_d7_d10_the_deadline_path_never_hands_a_bad_value_to_os_kill(
    plan, tmp_path, monkeypatch, written
):
    """``0`` is the one that matters most.

    ``if pid:`` rejected it as a reason to stop reading the file and then
    ``if pid is None:`` let it straight through, and ``kill(0, SIGKILL)`` is
    every process in this process group — the launcher's own included.
    """
    signals = _Signals(dies_after=None)

    def jailer(argv, timeout=300.0):
        Path(plan["host_side"]["pid_file"]).write_text(written)
        return subprocess.CompletedProcess(argv, 0, "", "")

    result = _boot(plan, tmp_path, monkeypatch, jailer=jailer, signals=signals)

    assert signals.sent == []
    assert result["stop_signal_sent"] is False
    assert result["pid_file"]["owned_by_this_run"] is False


@pytest.mark.parametrize("written", NOT_A_PID_THIS_MAY_SIGNAL)
def test_d7_d10_the_cleanup_path_never_hands_a_bad_value_to_os_kill(
    plan, tmp_path, monkeypatch, written
):
    """The same list, through the exception path, which has its own reader."""
    signals = _Signals(dies_after=None)

    def jailer(argv, timeout=300.0):
        Path(plan["host_side"]["pid_file"]).write_text(written)
        raise subprocess.TimeoutExpired(argv, 120.0)

    with pytest.raises(BootAbandoned) as raised:
        _boot(plan, tmp_path, monkeypatch, jailer=jailer, signals=signals)

    assert signals.sent == []
    process = raised.value.teardown["process"]
    assert process["signalled"] is False
    assert process["left_alone_because"]


# --------------------------------------------------------------------------
# D11-D13 — a cleanup failure does not replace the failure that caused it
# --------------------------------------------------------------------------


def test_d11_a_pid_too_large_to_convert_never_reaches_the_call_that_raised(
    plan, tmp_path, monkeypatch
):
    """A's F3, at the line it actually came from.

    The escape was ``_still_running(int(process["pid"]))`` — sitting between the
    ``except (OSError, ValueError)`` around the parse and the ``except OSError``
    around the signal, inside neither. ``2147483648`` converts to a Python int
    happily and then fails converting to a C long, and ``OverflowError`` is not
    an ``OSError``, so it went straight out through the ``except BaseException``
    that was mid-cleanup. ``BootAbandoned`` was therefore never constructed, and
    the original error, the salvaged disk's path and the teardown record went
    with it.

    The value is turned away before anything asks the kernel about it.
    """
    signals = _Signals(dies_after=None)

    def jailer(argv, timeout=300.0):
        Path(plan["host_side"]["chroot_dir"]).mkdir(parents=True, exist_ok=True)
        Path(plan["host_side"]["pid_file"]).write_text("2147483648\n")
        raise subprocess.TimeoutExpired(argv, 120.0)

    with pytest.raises(BootAbandoned) as raised:
        _boot(plan, tmp_path, monkeypatch, jailer=jailer, signals=signals)

    abandoned = raised.value
    assert signals.sent == []
    assert isinstance(abandoned.original, subprocess.TimeoutExpired)
    assert abandoned.teardown["salvaged"]["returned_copy"] is not None
    assert Path(abandoned.teardown["salvaged"]["returned_copy"]).exists()
    assert abandoned.teardown["process"]["signalled"] is False
    assert "cannot be handed to the operating system" in (
        abandoned.teardown["process"]["left_alone_because"]
    )


def test_d11_and_any_other_exception_from_cleanup_is_collected_not_raised(
    plan, tmp_path, monkeypatch
):
    """The general form, which is the part that has to keep holding.

    Turning away the one value A found is not the same promise as the one the
    docstring makes. Cleanup runs while another exception is already on its way
    out, so *anything* it raises replaces the reason the run failed with the
    reason the cleanup failed — and does it before ``BootAbandoned`` exists. So
    the failure is forced from inside the stop step rather than conjured by a
    PID value, and the same four things have to survive.
    """
    signals = _Signals(kill_raises=OverflowError("Python int too large"))

    with pytest.raises(BootAbandoned) as raised:
        _boot(
            plan,
            tmp_path,
            monkeypatch,
            jailer=_jailer_writing_that_then_fails(plan),
            signals=signals,
        )

    abandoned = raised.value
    assert isinstance(abandoned.original, subprocess.TimeoutExpired)
    assert abandoned.teardown["salvaged"]["returned_copy"] is not None
    assert abandoned.teardown["clean"] is False
    assert any(
        "OverflowError" in failure["error"]
        for failure in abandoned.teardown["failures"]
    )
    # And the removal step was still *reached*, which is what this test is
    # about: the failure above was collected rather than allowed to skip the
    # rest of the cleanup. It then declined, and said so, because `os.kill`
    # raising means nothing was ever signalled — the last this run saw of its
    # own machine, it was running. Taking the jail out from under it would be
    # the failure path doing what D21 stops the success path from doing.
    assert abandoned.teardown["all_gone"] is False
    assert "never confirmed stopped" in abandoned.teardown["destroy_refused_because"]


def test_d12_the_backend_record_still_carries_both_failures(tmp_path, monkeypatch):
    """The same case one layer up, where the loss was actually visible.

    ``AgenticV2MicroVMBackend.exec_run`` copies ``original_error`` and
    ``teardown`` off the exception only when both are there. An ``OverflowError``
    arriving in place of ``BootAbandoned`` is still an ``Exception``, so it was
    caught and reported — with both keys simply absent and nothing saying they
    had been lost. Read through the real backend rather than off the exception,
    because "the backend would have copied it" is the assumption under test.
    """
    machine, jail_base, host = _a_real_machine(tmp_path, monkeypatch)
    signals = _Signals(kill_raises=OverflowError("Python int too large"))
    signals.install(monkeypatch)
    _a_stand_in_guest_with_an_identity(monkeypatch, OURS)
    monkeypatch.setattr(
        "core.agentic_v2_first_boot._run", _a_jailer_that_starts_then_dies(jail_base)
    )

    backend = _backend_over(tmp_path, machine)
    try:
        result = backend.exec_run({"argv": ["true"], "cwd": ".", "timeout_seconds": 60})
        assert result == {"ok": False, "error_type": "compute_backend_error"}

        record = backend.boots[0]
        assert "TimeoutExpired" in record["original_error"]
        assert "BootAbandoned" in record["launcher_error"]
        teardown = record["teardown"]
        assert teardown["after_a_failure"] is True
        assert teardown["clean"] is False
        assert any("OverflowError" in f["error"] for f in teardown["failures"])
        assert teardown["salvaged"]["returned_copy"] is not None
    finally:
        backend.close()


def test_d13_a_keyboard_interrupt_is_still_a_keyboard_interrupt(
    plan, tmp_path, monkeypatch
):
    """Cleanup runs, and the stop is not turned into something else.

    Wrapping it would make Ctrl-C arrive as a ``RuntimeError`` nobody asked for;
    skipping cleanup would leak the jail. Both halves are pinned here because
    the guards added for D11 are exactly the kind of change that quietly
    swallows a ``BaseException``.
    """

    def jailer(argv, timeout=300.0):
        Path(plan["host_side"]["chroot_dir"]).mkdir(parents=True, exist_ok=True)
        Path(plan["host_side"]["pid_file"]).write_text("4242\n")
        raise KeyboardInterrupt()

    with pytest.raises(KeyboardInterrupt):
        _boot(
            plan,
            tmp_path,
            monkeypatch,
            jailer=jailer,
            signals=_Signals(dies_after=0),
        )

    assert not Path(plan["host_side"]["chroot_dir"]).exists()


# --------------------------------------------------------------------------
# D14-D16 — stop, confirm, salvage, remove; in that order
# --------------------------------------------------------------------------


def test_d14_the_machine_is_stopped_before_its_disk_is_copied(
    plan, tmp_path, monkeypatch
):
    """A's F4.

    The copy used to be taken first, before anything asked whether the guest was
    still running. On this box that is a file copy; on a host with ``/dev/kvm``
    it is a copy of a filesystem being written to, followed by an ``rmtree``
    racing a live Firecracker.
    """
    order: list[str] = []

    class _RecordingTheOrder(_Signals):
        """``_Signals``, noting when a real signal reached the kernel.

        This used to be a plain function wrapped around ``signals.__call__``,
        which meant it stood in for ``os.kill`` and nothing else. Once the
        production path reaches for a handle first, such a wrapper sees the
        signal only by accident. Subclassing keeps both transports installed
        and still puts the observation at the point where a signal lands.
        """

        def __call__(self, pid, sig):
            if sig != 0:
                order.append("signal")
            return super().__call__(pid, sig)

    signals = _RecordingTheOrder(dies_after=0)

    real_copy = __import__("shutil").copy2

    def watching_copy(src, dst, *a, **kw):
        if str(dst).endswith(".returned"):
            order.append("copy")
        return real_copy(src, dst, *a, **kw)

    monkeypatch.setattr("core.agentic_v2_first_boot.shutil.copy2", watching_copy)

    with pytest.raises(BootAbandoned):
        _boot(
            plan,
            tmp_path,
            monkeypatch,
            jailer=_jailer_writing_that_then_fails(plan),
            signals=signals,
        )

    assert order == ["signal", "copy"]


def test_d15_a_disk_copied_out_of_a_running_guest_is_not_called_clean(
    plan, tmp_path, monkeypatch
):
    """Never publish a copy taken while the guest was writing as an intact one.

    The copy is still taken — it is the only place the guest's writes exist — but
    it is labelled, it counts as a failure, and ``clean`` goes false. Ending on a
    finite deadline rather than waiting for a confirmation that is not coming is
    the other half of this.
    """
    with pytest.raises(BootAbandoned) as raised:
        _boot(
            plan,
            tmp_path,
            monkeypatch,
            jailer=_jailer_writing_that_then_fails(plan),
            signals=_Signals(dies_after=None),
        )

    teardown = raised.value.teardown
    assert teardown["process"]["signalled"] is True
    assert teardown["process"]["confirmed_stopped"] is False
    assert teardown["salvaged"]["copied_while_running"] is True
    assert teardown["clean"] is False


def test_d16_a_guest_that_stops_a_few_probes_later_is_confirmed_stopped(
    plan, tmp_path, monkeypatch
):
    """Sent and confirmed are two fields, and here both are true.

    SIGKILL is not instantaneous from the host's side; the process stays visible
    until the kernel reaps it. Reporting the signal as the stop would be a guess
    dressed as an observation.
    """
    with pytest.raises(BootAbandoned) as raised:
        _boot(
            plan,
            tmp_path,
            monkeypatch,
            jailer=_jailer_writing_that_then_fails(plan),
            signals=_Signals(dies_after=3),
        )

    process = raised.value.teardown["process"]
    assert process["signalled"] is True
    assert process["confirmed_stopped"] is True
    assert raised.value.teardown["salvaged"]["copied_while_running"] is False


# --------------------------------------------------------------------------
# P1 — the same evidence, through the call the product actually makes
# --------------------------------------------------------------------------


def test_p1_the_backend_record_carries_the_ownership_and_shutdown_evidence(
    tmp_path, monkeypatch
):
    """Everything above is worth nothing if the product path does not reach it.

    So this one assembles it the way the product does — a real
    ``AgenticV2MicroVMBackend`` over a real ``OneCallMachine``, ``exec_run``
    called with real arguments, the real plan builder, the real
    ``place_the_images`` and the real ``first_boot`` — and stands in for exactly
    two things: the jailer, because this box has no ``/dev/kvm``, and ``os.kill``,
    because the values reaching it are the whole question.

    Replacing ``boot_one_command`` instead would be the easy version of this test
    and would assert nothing: ``first_boot`` would never run. That trap was
    already walked into once in this module's history, so the seam is placed
    below the launcher on purpose.

    The guest here exits on its own, which is the ordinary case, and the record
    has to say so precisely: owned, on five grounds, with no signal sent and
    therefore nothing to confirm — and with the one thing that stays unprovable
    still written down rather than rounded off to "owned".
    """
    machine, jail_base, host = _a_real_machine(tmp_path, monkeypatch)
    signals = _Signals(starts_alive=False)
    signals.install(monkeypatch)
    _a_stand_in_guest_with_an_identity(monkeypatch, OURS)
    monkeypatch.setattr(
        "core.agentic_v2_first_boot._run", _a_jailer_that_boots_and_exits(jail_base)
    )
    monkeypatch.setattr(
        "core.agentic_v2_first_boot.files_out_of_work_disk",
        lambda image, names, **kw: _finished(),
    )

    backend = _backend_over(tmp_path, machine)
    try:
        result = backend.exec_run({"argv": ["true"], "cwd": ".", "timeout_seconds": 60})
        assert result["ok"] is True

        machine_record = backend.boots[0]["machine"]
        assert machine_record["outcome"] == "booted"
        assert machine_record["owned_by_this_run"] is True
        assert [g["held"] for g in machine_record["ownership_grounds"]] == [
            True,
            True,
            True,
            True,
            True,
            True,
        ]
        assert machine_record["left_alone_because"] is None
        assert "confined to this run's jail" in (
            machine_record["cannot_rule_out"]
        )

        # Nothing was signalled, so there is nothing to have confirmed. False and
        # None are different answers and the record keeps them apart.
        assert machine_record["stop_signal_sent"] is False
        assert machine_record["guest_confirmed_stopped"] is None
        assert signals.real_signals == []

        assert machine_record["teardown"]["all_gone"] is True
        assert sorted(jail_base.glob("firecracker/*/root")) == []
    finally:
        backend.close()


# --------------------------------------------------------------------------
# D17-D21 — what a returned copy is worth, and whose jail it is safe to remove
# --------------------------------------------------------------------------


def _reach(row: str, plan, pid_file: Path):
    """The jailer, the signals and the clock that take a real boot to ``row``.

    Every route here goes through ``first_boot`` itself. Nothing below stubs the
    thing being asked about: ``_still_running`` is left alone, the ownership
    re-check at the deadline is left alone, and the copy is taken by the module's
    own ``shutil.copy2``. Only the jailer and ``os.kill`` are stood in for, which
    are the host's two edges and not the logic under test.
    """
    if row == "no pid file ever appeared":
        return _jailer_writing_nothing, _Signals(), None
    if row == "the guest exited on its own":
        return _jailer_writing(plan), _Signals(starts_alive=False), None
    if row == "it went between the probe and the signal":
        return (
            _jailer_writing(plan),
            _Signals(
                dies_after=None,
                kill_raises=ProcessLookupError(3, "No such process"),
            ),
            None,
        )
    if row == "it overran and was left alone":
        return (
            _jailer_writing(plan),
            _Signals(dies_after=None),
            _a_clock_that_swaps_the_pid_file(pid_file),
        )
    if row == "it was signalled and did not stop":
        return _jailer_writing(plan), _Signals(dies_after=None), None
    if row == "it was signalled and was confirmed gone":
        return _jailer_writing(plan), _Signals(dies_after=0), None
    raise AssertionError(f"no route to {row!r}")


#: Every state a run can be in at the moment it copies the work disk out, and
#: what the copy is worth in each. The list is finite because the copy site is
#: reached from exactly six places in ``first_boot``, and it is written out in
#: full because the defect this replaces was a three-valued field read as a
#: boolean — the kind of thing a sampled table hides rather than shows.
#:
#: Columns: outcome, last observed running state, confirmed stopped,
#: ``copied_while_running``, ``copy_integrity``.
THE_COPY_TRUTH_TABLE = [
    (
        "no pid file ever appeared",
        "started_and_could_not_be_identified",
        None,
        None,
        None,
        "unverified",
    ),
    ("the guest exited on its own", "booted", False, None, False, "intact"),
    (
        "it went between the probe and the signal",
        "booted",
        False,
        None,
        False,
        "intact",
    ),
    (
        "it overran and was left alone",
        "overran_and_was_left_alone",
        True,
        None,
        True,
        "torn",
    ),
    (
        "it was signalled and did not stop",
        "overran_and_did_not_stop",
        True,
        False,
        True,
        "torn",
    ),
    (
        "it was signalled and was confirmed gone",
        "stopped_by_the_deadline",
        False,
        True,
        False,
        "intact",
    ),
]


@pytest.mark.parametrize(
    "row,outcome,last_seen,confirmed,copied,integrity",
    THE_COPY_TRUTH_TABLE,
    ids=[case[0].replace(" ", "-") for case in THE_COPY_TRUTH_TABLE],
)
def test_d17_every_path_that_copies_the_work_disk_says_what_the_copy_is_worth(
    plan, tmp_path, monkeypatch, row, outcome, last_seen, confirmed, copied, integrity
):
    """The whole table, through the ordinary call, one row at a time.

    ``guest_confirmed_stopped`` has three values and the copy label was derived
    from ``is False`` alone. ``None is False`` is ``False``, so four of these six
    rows arrived at the same answer — "not copied while running" — and two of
    them had no business being there. The rows that must *not* move are as much
    the point as the rows that must: calling an ordinary self-exiting boot torn
    would not be a fix, it would be a run nobody can use.
    """
    pid_file = Path(plan["host_side"]["pid_file"])
    jailer, signals, clock = _reach(row, plan, pid_file)

    result = _boot(
        plan, tmp_path, monkeypatch, jailer=jailer, signals=signals, clock=clock
    )

    assert result["outcome"] == outcome
    assert result["guest_last_seen_running"] is last_seen
    assert result["guest_confirmed_stopped"] is confirmed

    salvaged = result["salvaged"]
    assert salvaged["returned_copy"] is not None, (
        "this row is about what a copy is worth, so a copy has to have been taken"
    )
    assert Path(salvaged["returned_copy"]).exists()
    assert salvaged["copied_while_running"] is copied
    assert salvaged["copy_integrity"] == integrity
    assert salvaged["copy_integrity_because"].strip()


def test_d18_a_copy_is_only_called_intact_when_this_run_watched_the_writer_stop():
    """The rule the table above is an instance of, stated once.

    Read as a property rather than as six rows: ``intact`` is reachable only from
    a state where this run *observed* the guest gone. Not from a signal it sent,
    not from a deadline it reached, and not from never having looked.
    """
    for _, _, last_seen, confirmed, copied, integrity in THE_COPY_TRUTH_TABLE:
        if integrity == "intact":
            assert last_seen is False or confirmed is True
            assert copied is False
        if last_seen is True:
            assert integrity == "torn"
            assert copied is True
        if last_seen is None:
            assert integrity == "unverified"
            assert copied is None


def test_d19_a_guest_left_alone_because_it_could_not_be_claimed_is_still_a_live_writer(
    plan, tmp_path, monkeypatch
):
    """Row 4 on its own, because row 4 is the damage.

    A machine that overran, was still visibly running, and was deliberately not
    signalled — because the PID file had been replaced and this run will not kill
    a stranger — used to record its copy as "not taken while running". Nothing
    had stopped. Nothing had even been asked to stop. The field said the
    opposite of what happened, and it said it in the safe-looking direction.
    """
    pid_file = Path(plan["host_side"]["pid_file"])
    signals = _Signals(dies_after=None)

    result = _boot(
        plan,
        tmp_path,
        monkeypatch,
        jailer=_jailer_writing(plan),
        signals=signals,
        clock=_a_clock_that_swaps_the_pid_file(pid_file),
    )

    assert result["outcome"] == "overran_and_was_left_alone"
    assert result["stop_signal_sent"] is False
    assert result["guest_confirmed_stopped"] is None
    assert result["guest_last_seen_running"] is True
    assert result["salvaged"]["copied_while_running"] is True
    assert result["salvaged"]["copy_integrity"] == "torn"
    assert the_host_was_left_running(result) is True
    # And the reason it was left alone still holds: the stranger was never
    # signalled, which is what the whole ownership gate is for.
    assert not signals.anything_reached_kill_for(STRANGER)


def test_d20_a_copy_taken_without_ever_looking_at_a_process_is_unverified(
    plan, tmp_path, monkeypatch
):
    """The row the cleanup path did not have, on the cleanup path.

    The independent review called ``_clean_up_after_a_failure``'s predicate the
    correct form to copy onto the normal path. It is not: it reads
    ``was_running is True``, and there is a live branch where ``was_running`` is
    ``None`` — the PID file held a value this run is forbidden to signal, so no
    process was ever looked at — and a copy is taken anyway, because what blocks
    the copy is a jail that was already there and this jail was not.

    Copying that predicate over would have moved the defect rather than fixing
    it, and left the two paths saying different things about the same host. They
    now go through one judgement, and this is the row that proves it is not the
    old one.
    """
    with pytest.raises(BootAbandoned) as raised:
        _boot(
            plan,
            tmp_path,
            monkeypatch,
            jailer=_jailer_writing_a_pid_nobody_may_signal(plan),
            signals=_Signals(dies_after=None),
        )

    teardown = raised.value.teardown
    assert teardown["process"]["was_running"] is None
    assert teardown["process"]["confirmed_stopped"] is None
    assert teardown["process"]["signalled"] is False
    assert "whole group" in teardown["process"]["left_alone_because"]

    salvaged = teardown["salvaged"]
    assert salvaged["returned_copy"] is not None
    assert salvaged["copied_while_running"] is None
    assert salvaged["copy_integrity"] == "unverified"


def test_d21_a_jail_is_not_removed_out_from_under_a_machine_this_run_left_running(
    plan, tmp_path, monkeypatch
):
    """The teardown consequence of the two outcomes above.

    ``first_boot`` removed the jail as the last thing it did, unconditionally.
    On the two paths that end with a guest still on the host that is an
    ``rmtree`` of the rootfs, the work disk and the socket a live Firecracker
    holds open — and the record then said the jail was gone, which was true, and
    said nothing about what had been using it.

    A leaked directory is the worse-looking outcome and the better one: it can be
    removed by hand once the machine is gone. The refusal carries its reason,
    because "still there" and "still there because this run would not take it
    from a live machine" are one directory listing and two findings.
    """
    chroot = Path(plan["host_side"]["chroot_dir"])
    result = _boot(
        plan,
        tmp_path,
        monkeypatch,
        jailer=_jailer_writing(plan),
        signals=_Signals(dies_after=None),
    )

    assert result["outcome"] == "overran_and_did_not_stop"
    assert result["teardown"]["all_gone"] is False
    assert "still on the host" in result["teardown"]["refused_because"]
    assert result["teardown"]["left_behind"] == list(
        plan["host_side"]["destroy_after_the_run"]
    )
    assert chroot.exists()


def test_d22_an_ordinary_boot_still_takes_its_jail_down(plan, tmp_path, monkeypatch):
    """The negative control for D21, and the one that matters more.

    A rule that keeps jails around is only an improvement if it keeps around the
    ones that are dangerous to remove. Every ordinary run has to end with its
    jail gone, or the fix above is a disk-filling leak wearing a safety argument.
    """
    chroot = Path(plan["host_side"]["chroot_dir"])
    for signals in (_Signals(starts_alive=False), _Signals(dies_after=0)):
        result = _boot(
            plan, tmp_path, monkeypatch, jailer=_jailer_writing(plan), signals=signals
        )
        assert the_host_was_left_running(result) is False
        assert result["teardown"]["all_gone"] is True
        assert result["teardown"]["refused_because"] is None
        assert not chroot.exists()


def test_d23_a_live_writer_and_no_pid_file_is_not_an_empty_jail(
    plan, tmp_path, monkeypatch
):
    """The ordinary path's version of D21, with a real process holding the disk.

    D21 and D22 covered the two outcomes that *say* a machine is still there.
    This is the state that says nothing at all: the launcher exits 0, something
    is running, and no pid file ever appears. The run has no process to probe, so
    every host-side question returns the same silence a genuinely empty jail
    would — and the word written down for that silence used to be
    ``never_started``, which is not in the set the teardown gate reads. The jail
    came down on top of the writer and the record said ``all_gone: True``.

    The writer here is a real child of this test, opened on the work disk inside
    the jail, with the copy taken and the teardown reached while its descriptor
    is still open. Nothing is signalled by the code under test — there is no PID
    for it to signal — and the child is this test's to stop, which it does.

    This is a substitute launcher on a box with no ``/dev/kvm``, so it says
    nothing about how long a real jailer takes to publish a pid. What it pins is
    narrower and does not depend on that: whatever the reason the file is absent,
    a run that cannot name a process must not treat the jail as free.
    """
    real_kill = os.kill
    chroot = Path(plan["host_side"]["chroot_dir"])
    disk_in_jail = chroot / "work.ext4"
    opened = tmp_path / "the-writer-has-it-open"
    children: list[subprocess.Popen] = []

    def a_jailer_that_leaves_a_writer_and_no_pid_file(argv, timeout=300.0):
        child = subprocess.Popen(
            [
                sys.executable,
                "-c",
                "import pathlib, sys, time\n"
                "fd = open(sys.argv[1], 'ab')\n"
                "pathlib.Path(sys.argv[2]).write_text('open')\n"
                "time.sleep(30)\n",
                str(disk_in_jail),
                str(opened),
            ]
        )
        children.append(child)
        for _ in range(100):
            if opened.exists():
                break
            time.sleep(0.05)
        # Exit 0 and no pid file. This is the shape the ordinary path could not
        # tell apart from an empty host.
        return subprocess.CompletedProcess(argv, 0, "", "")

    try:
        signals = _Signals()
        result = _boot(
            plan,
            tmp_path,
            monkeypatch,
            jailer=a_jailer_that_leaves_a_writer_and_no_pid_file,
            signals=signals,
            reader=lambda image, names, **kw: {n: None for n in WORK_DISK_RESULTS},
        )

        assert opened.exists(), "the writer never got the disk open"
        assert children[0].poll() is None, (
            "the writer has to still be holding the disk at the moment teardown "
            "ran, or this test is not about the state it names"
        )

        # The destructive fact first, deliberately. If this test ever fails it
        # should say "the jail came down on a live writer", not "the outcome is
        # spelled differently"; the word is asserted below because it is how the
        # gate reaches this answer, not because it is the finding.
        assert result["teardown"]["all_gone"] is False
        assert chroot.exists()
        assert disk_in_jail.exists()
        assert "never got a process it could name" in result["teardown"][
            "refused_because"
        ]
        assert result["teardown"]["left_behind"] == list(
            plan["host_side"]["destroy_after_the_run"]
        )

        assert result["outcome"] == "started_and_could_not_be_identified"
        assert result["pid_file"]["appeared"] is False
        assert result["pid_file"]["pid_watched"] is None
        assert result["guest_confirmed_stopped"] is None
        assert the_host_was_left_running(result) is True
        # Nothing was signalled, because there was no PID to signal. The writer
        # is left running and left alone, which is the whole of the claim: this
        # run does not clean up what it cannot identify, in either direction.
        assert signals.sent == []
    finally:
        for child in children:
            if child.poll() is None:
                # This test's own child, by the pid this test was handed when it
                # created it. ``os.kill`` is stood in for inside the boot, so the
                # reference taken before it is the one used here.
                real_kill(child.pid, signal.SIGKILL)
            child.wait(timeout=10)


# --------------------------------------------------------------------------
# P2 — the same two outcomes, through the call the product actually makes
# --------------------------------------------------------------------------


def _a_jailer_that_boots_and_stays(jail_base: Path, pid: int = 4242):
    """A machine that starts and is still there when the deadline arrives."""

    def jailer(argv, timeout=300.0):
        _the_jail_just_placed(jail_base, pid)
        return subprocess.CompletedProcess(argv, 0, "", "")

    return jailer


class _SignalsThatSwapThePidFile(_Signals):
    """``_Signals``, with the PID file replaced under the watcher.

    D17 drives this row from the clock. That seam is not available here and its
    absence is the point: ``OneCallMachine`` calls ``first_boot`` with no ``now``
    or ``sleep``, so the product path runs on the real clock. The swap is driven
    from the liveness probe instead — already a stand-in, and already the thing
    that decides how long the loop runs — and the call asks for a one-second
    deadline so the real wait is a second rather than the policy's default.

    This is also why the row chosen here is the one that never signals. The
    signalled variant would add the ten-second confirmation window to the wall
    clock, and a ten-second unit test is a test people start skipping.
    """

    def __init__(self, jail_base: Path, **rest):
        super().__init__(**rest)
        self.jail_base = jail_base

    def __call__(self, pid, sig):
        answer = super().__call__(pid, sig)
        if sig == 0:
            roots = sorted(self.jail_base.glob("firecracker/*/root"))
            if roots:
                (roots[-1] / "firecracker.pid").write_text(f"{STRANGER}\n")
        return answer


def test_p2_a_command_that_finished_under_a_machine_nobody_stopped_says_both(
    tmp_path, monkeypatch
):
    """The command answered. The host is still occupied. Both are reported.

    ``exec_run`` returned ``{"ok": true, "returncode": 0}`` here and stopped
    there. Everything the run had learned — that a guest it started is still on
    the host, that the work disk those streams came off had a live writer
    attached — reached the end of ``first_boot`` and went no further. Two calls
    later the record was indistinguishable from a clean one.

    Discarding the returncode instead would be the opposite mistake and a worse
    one: the command really did finish, and throwing that away because the
    teardown was untidy loses a real answer. So the three axes stay separate.
    The returncode is the command's; ``host_left_running`` is the host's;
    ``copy_integrity`` is the bytes'. They are allowed to disagree, and here
    they do.
    """
    machine, jail_base, host = _a_real_machine(tmp_path, monkeypatch)
    signals = _SignalsThatSwapThePidFile(jail_base, dies_after=None)
    signals.install(monkeypatch)
    _a_stand_in_guest_with_an_identity(monkeypatch, OURS)
    monkeypatch.setattr(
        "core.agentic_v2_first_boot._run", _a_jailer_that_boots_and_stays(jail_base)
    )
    monkeypatch.setattr(
        "core.agentic_v2_first_boot.files_out_of_work_disk",
        lambda image, names, **kw: _finished(),
    )

    backend = _backend_over(tmp_path, machine)
    try:
        result = backend.exec_run({"argv": ["true"], "cwd": ".", "timeout_seconds": 1})

        # Axis one, unchanged: the command ran and this is what it returned.
        assert result["ok"] is True
        assert result["data"] == {"returncode": 0}
        assert result["error_type"] is None

        record = backend.boots[0]
        assert record["boot_outcome"] == "overran_and_was_left_alone"
        # Axis two and axis three, which used to stop at first_boot's return.
        assert record["machine"]["host_left_running"] is True
        assert record["machine"]["guest_confirmed_stopped"] is None
        assert record["machine"]["guest_last_seen_running"] is True
        assert record["machine"]["copied_while_running"] is True
        assert record["machine"]["copy_integrity"] == "torn"
        assert "overran_and_was_left_alone" in record["grounds"]
        assert "the host is not free" in record["grounds"]

        # And they are on disk beside the streams, for whoever reads the
        # transcript after this process is gone.
        meta = json.loads(
            (backend.work / EXEC_RECORD_DIR / "0000" / "meta.json").read_text()
        )
        assert meta["host_left_running"] is True
        assert meta["copy_integrity"] == "torn"
        assert meta["copy_integrity_because"].strip()
        assert meta["result"]["ok"] is True
        assert meta["result"]["data"] == {"returncode": 0}

        # The stranger was never signalled and the jail is still standing,
        # because something this run started is still inside it.
        assert signals.real_signals == []
        assert sorted(jail_base.glob("firecracker/*/root")) != []
    finally:
        backend.close()
