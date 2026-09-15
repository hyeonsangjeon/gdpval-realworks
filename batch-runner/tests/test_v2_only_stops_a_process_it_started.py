"""Only stopping a process this run can show it started.

The jail nonce proved a *directory* was this run's. It never said anything about
the *process*, and both stop paths read a bare integer out of a file and handed
it to ``os.kill``. The claim record had carried the owner's PID, boot id and
start time since it was written, and its own docstring said "none of it is read
back by any code path here".

This module is about the number. A PID is the one piece of a process's identity
the kernel hands out again, and a run that signals on the strength of a number
alone is one recycled PID away from killing something it never started.

**What is actually established, and what is not.** This run reads the host clock
twice — immediately before it starts the jailer, and again the moment it first
holds a number out of the PID file — and compares both against the start time
the kernel reports for the process that number names. A process that was already
running at the first reading cannot be a machine this run launched, and a process
that began after the second cannot be what the number was published for. Both are
facts about time and need no guess about what the process is. What is left is a
process that began *while this run was launching*, which is weaker than identity
and is all that is claimed.

The first of those bounds was here on its own for a while, and on its own it
admitted every process on the host younger than it, for the whole remaining life
of the run — measured at forty clock ticks past the floor with no launcher
anywhere near the subject, in
``test_v2_ownership_is_bound_to_the_launch.py``. ``CANNOT_RULE_OUT`` now reads
reuse *inside the interval*, which is the width the second bound leaves, and no
further.

**The handle, and where it is not available.** ``pidfd_open(2)`` pins a process
so a descriptor cannot come to name its successor. It is taken *after* the
interval above has admitted the number — opening one first would pin whatever
holds the number, which is not provenance — and once it is held, the gap that
used to sit in front of every signal is closed for all of them. Measured on this
box: ``OSError(38, 'Function not implemented')``. Python exposes the name, this
kernel (release 3.10) does not implement the call, and it needs 5.3.

So there is a path that signals by number instead, with the start time re-read
immediately before, and that path keeps the two-operation gap. It is not a
silent fallback — ``stop_handle`` in the artefact says which of the two was
used, :func:`test_k1_the_fallback_is_declared_rather_than_silent` holds that,
and :func:`test_k1c_a_host_firecracker_validates_always_has_the_handle` holds
the reason it does not matter on the host the guests actually run on.

The process is not this process's child either — the jailer is run with
``--daemonize`` and Firecracker is reparented away from the launcher — so
``waitpid`` cannot hold the number either.

**Real processes, and only ones these tests start.** The arms that exercise the
gate use ``sleep`` children this module forks itself, double-forked so they are
orphans, which is also the shape of the real thing. Nothing on the host is
listed, scanned or signalled. ``os.kill`` is spied on rather than replaced in
those arms: the sleeper surviving is the assertion, and it only means something
if the signal would really have landed.

The over-safe direction is tested as hard as the unsafe one. A launcher that
refuses everything passes every "did not signal a stranger" test ever written,
so every refusal case here is paired with an owned control that must still be
signalled, still be confirmed stopped and still have its jail taken down.
"""

from __future__ import annotations

import os
import platform
import signal
import subprocess
import time
from pathlib import Path

import pytest

from core import agentic_v2_first_boot
from core.agentic_v2_first_boot import (
    BY_A_PINNED_HANDLE,
    BY_THE_NUMBER_RECHECKED,
    CANNOT_RULE_OUT,
    OUTCOME_STARTED_AND_NOT_IDENTIFIED,
    OUTCOMES_THAT_LEAVE_THE_HOST_RUNNING,
    PIDFD_OPEN_ARRIVED_IN,
    PIDFD_SEND_SIGNAL_ARRIVED_IN,
    WORK_DISK_RESULTS,
    BootAbandoned,
    _clean_up_after_a_failure,
    _ours_is_gone,
    _started_during_this_runs_launch,
    _still_the_same_process,
    _the_instant_the_number_was_read,
    _the_instant_this_run_launched,
    _when_that_process_started,
    claim_the_jail,
    first_boot,
    the_host_was_left_running,
)
from core.agentic_v2_containment_readiness import (
    OLDEST_HOST_KERNEL_FIRECRACKER_VALIDATES,
)
from core.agentic_v2_microvm_launch import REQUIRED_MICROVM_POLICY, build_launch_plan

HZ = _the_instant_this_run_launched()["clock_ticks_per_second"]


# --------------------------------------------------------------------------
# Harmless children, and the clock
# --------------------------------------------------------------------------


class _Sleepers:
    """Every process these tests create, and the only ones they ever signal."""

    def __init__(self) -> None:
        self.started: list[int] = []

    def one(self) -> int:
        """A ``sleep`` that is nobody's child, so nothing here has to reap it.

        The shell backgrounds it and exits; the kernel reparents the sleeper.
        That is what the launcher sees from a daemonised jailer, and it also
        means ``os.kill(pid, 0)`` stops answering once it is gone rather than
        answering for a zombie this module forgot to collect.
        """
        shell = subprocess.run(
            ["sh", "-c", "sleep 300 >/dev/null 2>&1 & echo $!"],
            capture_output=True,
            text=True,
            check=True,
        )
        pid = int(shell.stdout.strip())
        self.started.append(pid)
        for _ in range(300):
            if _when_that_process_started(pid) is not None:
                return pid
            time.sleep(0.01)
        raise RuntimeError(f"the sleeper {pid} never appeared in /proc")

    def stop(self, pid: int) -> None:
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass

    def wait_until_gone(self, pid: int) -> None:
        for _ in range(300):
            try:
                os.kill(pid, 0)
            except OSError:
                return
            time.sleep(0.01)
        raise RuntimeError(f"the sleeper {pid} would not go")

    def clean_up(self) -> None:
        for pid in self.started:
            self.stop(pid)


@pytest.fixture
def sleepers():
    made = _Sleepers()
    try:
        yield made
    finally:
        made.clean_up()


class _Clock:
    """Advances on demand so the deadline arrives without waiting for it.

    It does sleep a little for real, because the processes here are real: after
    a ``SIGKILL`` the kernel needs a moment before the number stops answering,
    and a clock that never yields would ask forty times inside one microsecond
    and conclude the machine would not die.
    """

    def __init__(self) -> None:
        self.t = 0.0

    def now(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.t += seconds
        time.sleep(0.005)


class _SpyOnRealSignals:
    """Records what reached ``os.kill`` and then lets it happen for real.

    A stub here would defeat the arms that matter: the pre-existing sleeper is
    alive at the end because the launcher declined to signal it, and that is
    only evidence if the signal would have landed.
    """

    def __init__(self) -> None:
        self.sent: list[tuple[int, int]] = []
        self._real = os.kill

    def __call__(self, pid, sig):
        self.sent.append((pid, sig))
        return self._real(pid, sig)

    @property
    def real_signals(self) -> list[tuple[int, int]]:
        return [(pid, sig) for pid, sig in self.sent if sig != 0]


# --------------------------------------------------------------------------
# A real plan, a real jail
# --------------------------------------------------------------------------


@pytest.fixture
def plan(tmp_path, monkeypatch):
    for name in ("firecracker", "vmlinux", "rootfs.ext4", "work.ext4"):
        path = tmp_path / name
        path.write_bytes(b"not really an image, but a readable file")
        path.chmod(0o755)
    monkeypatch.setattr(os, "chown", lambda *a, **k: None)
    return build_launch_plan(
        vm_id="test-identity",
        firecracker_binary=tmp_path / "firecracker",
        kernel_path=tmp_path / "vmlinux",
        rootfs_path=tmp_path / "rootfs.ext4",
        work_disk_path=tmp_path / "work.ext4",
        uid=997,
        gid=997,
        vcpu_count=1,
        cgroup_version=2,
        chroot_base=tmp_path / "jail",
        # A short budget, and the only rule that differs from the real policy.
        # The deadline is what these tests need to arrive, and the clock below
        # is virtual, so the wait costs nothing — but the *number* of polls is
        # real work, and the production 1200 s would spend four thousand of
        # them per test. Shortening it is a tightening, not a loosening: it is
        # the run's own budget for its own guest, and the codebase already
        # names it as the one rule a call is allowed to tighten
        # (``THE_ONE_RULE_A_CALL_MAY_TIGHTEN``). Every containment rule stays
        # exactly as the policy states it, which is what the directive's "not
        # by weakening isolation" is about; the plan's hash is computed after
        # this, so nothing downstream is comparing against a policy that was
        # never used.
        policy={**REQUIRED_MICROVM_POLICY, "wall_clock_seconds": 2},
    )


def _finished():
    results = {name: None for name in WORK_DISK_RESULTS}
    results["/out/stdout"] = "this ran inside the guest\n"
    results["/out/exit_status"] = "0"
    return results


def _boot(plan, tmp_path, monkeypatch, *, jailer, clock=None):
    """The real :func:`first_boot`, with only the jailer stood in.

    ``os.kill`` is **not** replaced here — the spy installed by each test wraps
    the real one. ``_still_running``, ``_when_that_process_started`` and the
    whole identity gate run against the host's own ``/proc``.
    """
    clock = clock or _Clock()
    monkeypatch.setattr("core.agentic_v2_first_boot._run", jailer)
    monkeypatch.setattr(
        "core.agentic_v2_first_boot.files_out_of_work_disk",
        lambda image, names, **kw: _finished(),
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


def _a_jailer_publishing(plan, pid: int):
    def jailer(argv, timeout=300.0):
        Path(plan["host_side"]["pid_file"]).write_text(f"{pid}\n")
        return subprocess.CompletedProcess(argv, 0, "", "")

    return jailer


def _a_jailer_that_starts_a_guest(plan, sleepers: _Sleepers):
    """Start a process *after* the run read its floor, then publish it.

    This is the owned control and it is the shape a real jailer has: the run
    records the instant, the jailer runs, and the thing it starts is necessarily
    younger than that instant.
    """

    def jailer(argv, timeout=300.0):
        pid = sleepers.one()
        Path(plan["host_side"]["pid_file"]).write_text(f"{pid}\n")
        return subprocess.CompletedProcess(argv, 0, "", "")

    return jailer


def _a_jailer_that_publishes_then_fails(plan, pid: int):
    def jailer(argv, timeout=300.0):
        Path(plan["host_side"]["chroot_dir"]).mkdir(parents=True, exist_ok=True)
        Path(plan["host_side"]["pid_file"]).write_text(f"{pid}\n")
        raise subprocess.TimeoutExpired(argv, 120.0)

    return jailer


def _a_jailer_that_starts_a_guest_then_fails(plan, sleepers: _Sleepers):
    def jailer(argv, timeout=300.0):
        pid = sleepers.one()
        Path(plan["host_side"]["chroot_dir"]).mkdir(parents=True, exist_ok=True)
        Path(plan["host_side"]["pid_file"]).write_text(f"{pid}\n")
        raise subprocess.TimeoutExpired(argv, 120.0)

    return jailer


def _a_claimed_jail(plan) -> dict:
    chroot = Path(plan["host_side"]["chroot_dir"])
    claim = claim_the_jail(
        chroot, vm_id=str(plan["vm_id"]), plan_sha256=str(plan["plan_sha256"])
    )
    (chroot / "work.ext4").write_bytes(b"whatever the guest was writing")
    return claim


def _teardown(
    plan, tmp_path, *, claim, launch_floor, attempted=True, number_read_at=None
):
    # ``number_read_at=None`` is the ordinary shape for these cases: the failure
    # they model lands before anything read a PID, so the teardown is the first
    # thing to hold the number and takes its own ceiling. The sleeper the
    # stand-in jailer starts is born inside that interval, which is where a real
    # guest is born. A case that wants the inherited ceiling passes one.
    return _clean_up_after_a_failure(
        host_side=plan["host_side"],
        pid_file=Path(plan["host_side"]["pid_file"]),
        claim=claim,
        launch_was_attempted=attempted,
        launch_spawned_nothing=False,
        launch_floor=launch_floor,
        number_read_at=number_read_at,
        work_disk=tmp_path / "work.ext4",
        salvage={"returned_copy": None, "results_read": False},
        now=_Clock().now,
        sleep=_Clock().sleep,
    )


# --------------------------------------------------------------------------
# G — the mechanism, against real processes and this host's real /proc
# --------------------------------------------------------------------------


def test_g1_a_process_older_than_the_launch_is_refused_and_the_gap_is_named(sleepers):
    """The defect, reduced to the one call that decides it.

    The sleeper is started first and the floor read afterwards, which is the
    stale-PID-file case: the number in the file names something that was already
    running when this run launched. No signal is involved — this is the function
    every signalling path asks first.
    """
    stranger = sleepers.one()
    started = _when_that_process_started(stranger)
    time.sleep(0.05)
    floor = _the_instant_this_run_launched()
    ceiling = _the_instant_the_number_was_read()

    assert started is not None and started < floor["ticks_since_boot"]

    identity, why_not = _started_during_this_runs_launch(stranger, floor, ceiling)

    assert identity is None
    assert "already running" in why_not
    assert str(stranger) in why_not
    assert "not a machine this run started" in why_not


def test_g2_a_process_younger_than_the_launch_is_admitted_with_its_start_time(
    sleepers,
):
    """The control that stops "refuse everything" from looking like a fix.

    A real guest falls inside the interval by construction: the floor is read
    immediately before the jailer runs, the process comes into existence during
    that call, and the ceiling is read afterwards when the number is first held.
    The order below is that order. If this arm does not pass, the launcher can
    no longer stop anything it started.
    """
    floor = _the_instant_this_run_launched()
    time.sleep(0.05)
    ours = sleepers.one()
    time.sleep(0.05)
    ceiling = _the_instant_the_number_was_read()

    identity, why_not = _started_during_this_runs_launch(ours, floor, ceiling)

    assert why_not == ""
    assert identity == _when_that_process_started(ours)
    assert floor["ticks_since_boot"] <= identity <= ceiling["ticks_since_boot"]


def test_g3_a_start_time_does_not_move_while_the_process_lives(sleepers):
    """Identity has to be a constant, or it is not identity.

    ``_still_the_same_process`` compares a value read at the deadline against
    one read at publication. If start times drifted, that comparison would call
    every guest an impostor — the over-safe failure, and it looks exactly like
    the guard working.
    """
    ours = sleepers.one()
    first = _when_that_process_started(ours)
    time.sleep(0.3)
    second = _when_that_process_started(ours)

    assert first is not None
    assert first == second
    assert _still_the_same_process(ours, first) is True
    assert _still_the_same_process(ours, first + 1) is False


def test_g4_a_process_that_has_gone_answers_nothing_and_is_not_the_same_one(sleepers):
    """What the host says about a number nobody holds.

    ``None`` here is *absence of evidence*, and the two readings above it are
    kept apart on purpose: ``_still_the_same_process`` says no, because there is
    nothing to be the same as, while ``_ours_is_gone`` says yes, because nothing
    is running under the number at all. Collapsing those two into one boolean is
    how a dead process and an unidentifiable one came to look alike.
    """
    short = sleepers.one()
    started = _when_that_process_started(short)
    sleepers.stop(short)
    sleepers.wait_until_gone(short)

    assert _when_that_process_started(short) is None
    assert _still_the_same_process(short, started) is False
    assert _ours_is_gone(short, started) is True
    assert _ours_is_gone(short, None) is True


def test_g5_an_unusable_interval_refuses_and_says_which_end_is_unusable(sleepers):
    """Six refusals, six different readings, none of them a fallback.

    Four are about the floor and two about the ceiling, and they are kept apart
    because a missing floor and a missing ceiling are different failures of this
    run's own record-keeping. The last floor case is the crash-and-resume one: a
    floor carried across a host restart counts ticks from a boot that is over.
    Every one of these returns ``None``, which every caller reads as *do not
    signal*; there is no value of either end that means "skip the check".
    """
    ours = sleepers.one()
    good = _the_instant_this_run_launched()
    ceiling = _the_instant_the_number_was_read()

    no_floor, why_none = _started_during_this_runs_launch(ours, None, ceiling)
    empty, why_empty = _started_during_this_runs_launch(ours, {}, ceiling)
    no_ticks, why_ticks = _started_during_this_runs_launch(
        ours, {"ticks_since_boot": None, "boot_id": good["boot_id"]}, ceiling
    )
    rebooted, why_reboot = _started_during_this_runs_launch(
        ours,
        {
            "ticks_since_boot": 0,
            "boot_id": "00000000-0000-0000-0000-000000000000",
        },
        ceiling,
    )
    no_ceiling, why_no_ceiling = _started_during_this_runs_launch(ours, good, None)
    unread_ceiling, why_unread = _started_during_this_runs_launch(
        ours, good, {"ticks_since_boot": None, "boot_id": good["boot_id"]}
    )

    assert (no_floor, empty, no_ticks, rebooted) == (None, None, None, None)
    assert (no_ceiling, unread_ceiling) == (None, None)
    assert "no record of when it launched" in why_none
    assert "no record of when it launched" in why_empty
    assert "could not read the host clock" in why_ticks
    assert "has restarted since this run launched" in why_reboot
    assert "no record of when it read that number" in why_no_ceiling
    assert "could not read the host clock when it took that number" in why_unread


def test_g6_the_residue_is_the_launch_interval_and_the_claim_is_no_wider(sleepers):
    """What this narrows and what it does not close.

    The floor alone separated *before this run's launch* from *after it*, and
    everything on the far side of that line was admitted — for as long as the
    run lived, not for a tick. The first two assertions are that measurement,
    made here against the same function every signalling path calls: a sleeper
    started a third of a second past the floor is thirty-odd ticks clear of it,
    which is not a granularity effect, and with a ceiling read before it was
    born the function turns it away.

    What is left is reuse inside the interval, and the constant that reports the
    limit has to say so — a run that quietly widened its claim to "this is
    definitely our process" would read identically from the outside.
    """
    floor = _the_instant_this_run_launched()
    ceiling_before_it_existed = _the_instant_the_number_was_read()
    time.sleep(0.3)
    later = sleepers.one()
    started = _when_that_process_started(later)

    assert started is not None
    assert started - floor["ticks_since_boot"] >= 20
    assert floor["clock_ticks_per_second"] == HZ

    identity, why_not = _started_during_this_runs_launch(
        later, floor, ceiling_before_it_existed
    )
    assert identity is None
    assert "after this run already had that number in hand" in why_not

    assert "reuse" in CANNOT_RULE_OUT.lower()
    assert "inside the interval" in CANNOT_RULE_OUT
    assert "did not fork" in CANNOT_RULE_OUT


# --------------------------------------------------------------------------
# H — the normal stop path, at the deadline
# --------------------------------------------------------------------------


def test_h1_an_owned_guest_that_overruns_is_still_signalled_and_confirmed(
    plan, tmp_path, monkeypatch, sleepers
):
    """The control, end to end, with a real process at the end of it.

    Everything below is about refusing. This is the arm that has to keep
    working, and it is checked at three depths: the signal really reached the
    sleeper, the sleeper really went, and the record says both — plus the fifth
    ownership ground, which is the only one about the process rather than the
    file.
    """
    spy = _SpyOnRealSignals()
    monkeypatch.setattr(os, "kill", spy)

    result = _boot(
        plan,
        tmp_path,
        monkeypatch,
        jailer=_a_jailer_that_starts_a_guest(plan, sleepers),
    )

    ours = sleepers.started[-1]
    assert result["outcome"] == "stopped_by_the_deadline"
    assert (ours, signal.SIGKILL) in spy.real_signals
    assert result["guest_confirmed_stopped"] is True
    assert result["guest_last_seen_running"] is False
    assert the_host_was_left_running(result) is False

    evidence = result["pid_file"]
    assert evidence["owned_by_this_run"] is True
    assert len(evidence["ownership_grounds"]) == 5
    assert all(g["held"] for g in evidence["ownership_grounds"])
    # The two readings that decided it are kept, and the order between them is
    # the whole of the argument: the guest started at or after the instant this
    # run launched. Read back from the record rather than from ``/proc``, which
    # by now has nothing to say — the process is gone, which is the point.
    assert evidence["launch_floor"]["ticks_since_boot"] is not None
    assert evidence["pid_started_at_ticks"] is not None
    assert (
        evidence["pid_started_at_ticks"] >= evidence["launch_floor"]["ticks_since_boot"]
    )

    # The jail of a machine that was confirmed stopped is this run's to remove.
    assert not Path(plan["host_side"]["chroot_dir"]).exists()


def test_h2_a_published_pid_older_than_the_launch_is_never_signalled(
    plan, tmp_path, monkeypatch, sleepers
):
    """The defect, through ``first_boot``, against a live bystander.

    The sleeper is started before the run, so the number in the PID file names
    something this run did not launch. ``os.kill`` is only spied on, so the
    sleeper being alive at the end is not an artefact of a stub — the signal
    would have reached it.

    The outcome is its own, not ``never_started``: something *was* launched, and
    reporting a start failure over a host that may have a guest on it would
    assert the one thing this case cannot establish. Its membership in
    ``OUTCOMES_THAT_LEAVE_THE_HOST_RUNNING`` is what keeps the jail standing,
    with no second rule anywhere to fall out of step with it.
    """
    stranger = sleepers.one()
    time.sleep(0.05)
    spy = _SpyOnRealSignals()
    monkeypatch.setattr(os, "kill", spy)

    result = _boot(
        plan, tmp_path, monkeypatch, jailer=_a_jailer_publishing(plan, stranger)
    )

    assert result["outcome"] == OUTCOME_STARTED_AND_NOT_IDENTIFIED
    assert result["outcome"] in OUTCOMES_THAT_LEAVE_THE_HOST_RUNNING
    assert spy.real_signals == []
    assert os.kill(stranger, 0) is None, "the bystander is still running"

    assert result["pid_file"]["owned_by_this_run"] is False
    assert result["pid_file"]["pid_started_at_ticks"] is None
    assert "already running" in result["pid_file"]["left_alone_because"]
    assert result["pid_file"]["ownership_grounds"][4]["held"] is False

    # Not a start failure, and the recoverable artefact is kept rather than
    # cleaned up under a host whose state is unknown.
    assert result["outcome"] != "never_started"
    assert the_host_was_left_running(result) is True
    assert Path(plan["host_side"]["chroot_dir"]).exists()


def test_h3_a_number_handed_on_between_the_check_and_the_signal_is_not_signalled(
    plan, tmp_path, monkeypatch, sleepers
):
    """Identity is re-asked at the moment of use, not inherited from publication.

    The guest is genuinely this run's when the PID file appears. By the time the
    deadline arrives the kernel has handed its number to something else, which
    from here looks exactly like the guest still running. The PID file is
    untouched and the jail is untouched, so every check except the start time
    still says yes — which is what makes this the arm that would pass on a
    number alone.

    The guest has to be started *by the jailer*, not in the test body. A sleeper
    made before ``_boot`` is older than the floor the run reads, so the floor
    rejects it at publication and the run never reaches the re-read this test
    exists for. Written that way it passed only while both landed inside the
    same clock tick, which on this box was 17 times in 20.
    """
    spy = _SpyOnRealSignals()
    monkeypatch.setattr(os, "kill", spy)

    real_reader = agentic_v2_first_boot._when_that_process_started
    asked: list[int] = []
    at_publication: list[int] = []

    def a_number_that_gets_recycled(pid: int):
        if not sleepers.started or pid != sleepers.started[-1]:
            return real_reader(pid)
        asked.append(pid)
        if len(asked) == 1:
            # The first answer is the real one, taken when the run identified
            # it, and it is at or after the floor because the jailer started it.
            at_publication.append(real_reader(pid))
            return at_publication[0]
        # Every answer after that is a different process holding the number.
        return at_publication[0] + 5

    monkeypatch.setattr(
        "core.agentic_v2_first_boot._when_that_process_started",
        a_number_that_gets_recycled,
    )

    result = _boot(
        plan,
        tmp_path,
        monkeypatch,
        jailer=_a_jailer_that_starts_a_guest(plan, sleepers),
    )
    ours = sleepers.started[-1]

    assert len(asked) > 1, "the start time has to be re-read, or this proves nothing"
    assert spy.real_signals == []
    assert result["outcome"] == "overran_and_was_left_alone"

    why = result["pid_file"]["left_alone_because"]
    assert "no longer the one this run identified" in why
    assert "never started" in why
    assert result["pid_file"]["owned_by_this_run"] is False
    assert the_host_was_left_running(result) is True
    assert Path(plan["host_side"]["chroot_dir"]).exists()
    assert os.kill(ours, 0) is None, "the process holding the number is untouched"


def test_h4_a_guest_that_exits_before_the_deadline_is_never_asked_for_its_identity(
    plan, tmp_path, monkeypatch, sleepers
):
    """Liveness first, identity second — and the order is load-bearing.

    Nothing holding the number means nothing of this run's is running under it,
    and that is true without establishing anything. Asking identity first turns
    every machine that ended on its own — the ordinary, successful boot — into
    an unidentified one and keeps its jail forever. This arm is the one that
    catches that, and it caught it: the first cut of the gate asked at dispatch
    and failed here.
    """
    short = sleepers.one()
    sleepers.stop(short)
    sleepers.wait_until_gone(short)

    spy = _SpyOnRealSignals()
    monkeypatch.setattr(os, "kill", spy)

    result = _boot(
        plan, tmp_path, monkeypatch, jailer=_a_jailer_publishing(plan, short)
    )

    assert result["outcome"] == "booted"
    assert spy.real_signals == []
    assert result["guest_last_seen_running"] is False
    assert result["guest_confirmed_stopped"] is None
    assert the_host_was_left_running(result) is False
    assert not Path(plan["host_side"]["chroot_dir"]).exists()


def test_h5_nothing_published_is_not_a_start_failure(plan, tmp_path, monkeypatch):
    """The vocabulary boundary, from the other side — and it is not where I put it.

    An earlier version of this test asserted ``never_started`` here, on the
    reasoning that an absent pid file means the jailer wrote nothing and so no
    machine existed to run in. That reasoning was wrong and PR #591 reversed it:
    ``never_started`` is reported downstream as ``compute_start_failed``, which
    is a *finding* that nothing was put on the host, and the only evidence for
    it is this run's own account of its control flow — the launch was never
    reached, or the launch reported that its ``exec`` never happened. An absent
    pid file is neither. The launcher ran; the host declined to answer.

    So the boundary is the launcher, not the pid file. Nothing published means
    this run cannot name what it left behind, the jail stays standing and the
    host may not be treated as free. The genuine start failure — where ``exec``
    really did not happen — keeps its own word and is covered at
    ``test_agentic_v2_first_boot.py`` by the ``launch_spawned_nothing`` pair.
    """
    spy = _SpyOnRealSignals()
    monkeypatch.setattr(os, "kill", spy)

    def a_jailer_publishing_nothing(argv, timeout=300.0):
        return subprocess.CompletedProcess(argv, 0, "", "")

    result = _boot(plan, tmp_path, monkeypatch, jailer=a_jailer_publishing_nothing)

    assert result["outcome"] == OUTCOME_STARTED_AND_NOT_IDENTIFIED
    assert result["outcome"] in OUTCOMES_THAT_LEAVE_THE_HOST_RUNNING
    # Still nothing is signalled — an unnamed process is not a target.
    assert spy.sent == []
    assert result["pid_file"]["pid_started_at_ticks"] is None
    assert the_host_was_left_running(result) is True


# --------------------------------------------------------------------------
# J — the exception path, where the run is already failing
# --------------------------------------------------------------------------


def test_j1_teardown_stops_a_process_this_run_started(
    plan, tmp_path, monkeypatch, sleepers
):
    """The owned control on the path that runs when everything else went wrong.

    The two stop paths were written at different times and only one of them was
    repaired first. This is the second one, and it has the same obligation: a
    guest this run started must still be stopped, and the failure it was
    cleaning up after must still be the failure that is raised.
    """
    spy = _SpyOnRealSignals()
    monkeypatch.setattr(os, "kill", spy)

    with pytest.raises(BootAbandoned) as abandoned:
        _boot(
            plan,
            tmp_path,
            monkeypatch,
            jailer=_a_jailer_that_starts_a_guest_then_fails(plan, sleepers),
        )

    ours = sleepers.started[-1]
    assert "TimeoutExpired" in str(abandoned.value)

    process = abandoned.value.teardown["process"]
    assert process["pid"] == ours
    assert process["was_running"] is True
    assert process["signalled"] is True
    assert process["confirmed_stopped"] is True
    assert process["pid_started_at_ticks"] is not None
    assert process["launch_floor"]["ticks_since_boot"] is not None
    assert (ours, signal.SIGKILL) in spy.real_signals


def test_j2_teardown_refuses_a_process_older_than_the_launch_and_keeps_the_artefact(
    plan, tmp_path, monkeypatch, sleepers
):
    """A failing run is the worst moment to widen what may be killed.

    The bystander is alive before the run and alive after it. What the run keeps
    instead of a signal is the structured reason and the recoverable copy — the
    directive's rule, which is that an unestablished owner buys a refusal and an
    artefact, never a signal and never a deletion.
    """
    stranger = sleepers.one()
    time.sleep(0.05)
    spy = _SpyOnRealSignals()
    monkeypatch.setattr(os, "kill", spy)

    with pytest.raises(BootAbandoned) as abandoned:
        _boot(
            plan,
            tmp_path,
            monkeypatch,
            jailer=_a_jailer_that_publishes_then_fails(plan, stranger),
        )

    assert "TimeoutExpired" in str(abandoned.value)
    teardown = abandoned.value.teardown
    process = teardown["process"]

    assert process["pid"] == stranger
    assert process["was_running"] is True
    assert process["signalled"] is False
    assert process["pid_started_at_ticks"] is None
    assert "already running" in process["left_alone_because"]
    assert "does not stop what it cannot show it started" in process[
        "left_alone_because"
    ]
    assert spy.real_signals == []
    assert os.kill(stranger, 0) is None, "the bystander is still running"

    assert teardown["salvaged"]["returned_copy"] is not None
    assert Path(teardown["salvaged"]["returned_copy"]).exists()
    assert Path(plan["host_side"]["chroot_dir"]).exists()
    assert teardown["destroy_refused_because"]


def test_j3_teardown_of_a_process_that_already_went_confirms_without_signalling(
    plan, tmp_path, sleepers
):
    """Already gone is an answer, and it does not need an identity.

    Same ordering as the deadline path, for the same reason: nothing holds the
    number, so nothing of this run's is running under it. Requiring identity
    here would leave a jail behind every time a guest crashed on its own, which
    is precisely when this path runs.
    """
    short = sleepers.one()
    sleepers.stop(short)
    sleepers.wait_until_gone(short)

    claim = _a_claimed_jail(plan)
    Path(plan["host_side"]["pid_file"]).write_text(f"{short}\n")

    record = _teardown(
        plan, tmp_path, claim=claim, launch_floor=_the_instant_this_run_launched()
    )
    process = record["process"]

    assert process["pid"] == short
    assert process["was_running"] is False
    assert process["signalled"] is False
    assert process["confirmed_stopped"] is True
    assert process["left_alone_because"] == "it had already stopped"
    assert process["pid_started_at_ticks"] is None


def test_j4_teardown_with_no_floor_refuses_rather_than_falling_back(
    plan, tmp_path, monkeypatch, sleepers
):
    """There is no implicit unsafe fallback, and no argument that asks for one.

    ``launch_floor=None`` is what a caller that lost track of its own launch
    hands over. The tempting reading is "no floor, so no constraint"; the one
    implemented is "no floor, so no evidence". The process here is one this run
    genuinely would have been entitled to stop, which is what makes the refusal
    a real cost rather than a free one.
    """
    ours = sleepers.one()
    spy = _SpyOnRealSignals()
    monkeypatch.setattr(os, "kill", spy)

    claim = _a_claimed_jail(plan)
    Path(plan["host_side"]["pid_file"]).write_text(f"{ours}\n")

    record = _teardown(plan, tmp_path, claim=claim, launch_floor=None)
    process = record["process"]

    assert process["was_running"] is True
    assert process["signalled"] is False
    assert spy.real_signals == []
    assert "no record of when it launched" in process["left_alone_because"]
    assert os.kill(ours, 0) is None
    assert Path(plan["host_side"]["chroot_dir"]).exists()


def test_j5_a_floor_from_before_a_restart_refuses_on_the_reboot_reading(
    plan, tmp_path, monkeypatch, sleepers
):
    """Crash and resume: a floor that outlived the boot it was read in.

    Tick counts restart with the host, so a resumed run holding a floor from
    before a reboot would be comparing against a number that means nothing — and
    the comparison would *succeed* for almost anything, because the new boot's
    ticks start at zero. The boot id is what makes that detectable, and the
    reading has to name the restart rather than the process.
    """
    ours = sleepers.one()
    spy = _SpyOnRealSignals()
    monkeypatch.setattr(os, "kill", spy)

    claim = _a_claimed_jail(plan)
    Path(plan["host_side"]["pid_file"]).write_text(f"{ours}\n")

    a_previous_boot = {
        "ticks_since_boot": 0,
        "boot_id": "00000000-0000-0000-0000-000000000000",
        "clock_ticks_per_second": HZ,
    }
    record = _teardown(plan, tmp_path, claim=claim, launch_floor=a_previous_boot)
    process = record["process"]

    assert process["signalled"] is False
    assert spy.real_signals == []
    assert "has restarted since this run launched" in process["left_alone_because"]
    assert os.kill(ours, 0) is None
    assert Path(plan["host_side"]["chroot_dir"]).exists()


# --------------------------------------------------------------------------
# K — the capability that is not there
# --------------------------------------------------------------------------


def test_k1_the_fallback_is_declared_rather_than_silent(
    plan, tmp_path, monkeypatch, sleepers
):
    """Without a handle the stop still happens, and it says so.

    This used to assert that ``pidfd_open`` was never called at all. The reason
    given was a good one — a silent fallback from a failed probe is the implicit
    unsafe path the design forbids — but the conclusion drawn from it was too
    strong. What has to be forbidden is the *silence*, not the probe: a run that
    stopped its machine by number and a run that stopped it through a pinned
    descriptor are carrying different evidence, and an artefact that reported
    both the same way would be hiding that from whoever reads it.

    So the fallback is exercised here by poisoning both halves of the interface,
    and what is asserted is that the machine still stops — the over-safe
    direction is a failure too — and that the record names which way it went.
    """

    def poisoned(*args, **kwargs):
        raise OSError(38, "Function not implemented")

    monkeypatch.setattr(os, "pidfd_open", poisoned, raising=False)
    monkeypatch.setattr(signal, "pidfd_send_signal", poisoned, raising=False)

    spy = _SpyOnRealSignals()
    monkeypatch.setattr(os, "kill", spy)

    result = _boot(
        plan,
        tmp_path,
        monkeypatch,
        jailer=_a_jailer_that_starts_a_guest(plan, sleepers),
    )

    assert result["outcome"] == "stopped_by_the_deadline"
    assert (sleepers.started[-1], signal.SIGKILL) in spy.real_signals
    assert result["stop_handle"] == BY_THE_NUMBER_RECHECKED


def test_k1b_with_a_handle_the_signal_does_not_go_by_number(
    plan, tmp_path, monkeypatch, sleepers
):
    """The path this kernel cannot run, run against stand-ins for the syscalls.

    This host answers ``ENOSYS`` — :func:`test_k2_this_kernel_really_does_refuse_the_stable_handle`
    is the measurement — so the branch that uses a descriptor is never taken by
    any other test here, and an untaken branch is an unwritten one. The two
    syscalls are stood in for; everything around them is real, including the
    sleeper, the start-time reads and the confirmation.

    What this does establish: when a handle is available the ``SIGKILL`` goes
    through it and *not* through the number, so there is no second lookup
    between deciding and acting. What it does not establish is anything about
    how ``pidfd_send_signal`` behaves on a kernel that implements it — that is
    not observable from here and is not claimed.
    """
    sent: list[tuple[int, int]] = []
    opened: list[int] = []

    def open_handle(pid, flags=0):
        opened.append(pid)
        # A real descriptor, so the ``os.close`` in the production path closes
        # something rather than raising on a made-up integer.
        return os.open(os.devnull, os.O_RDONLY)

    def send(handle, signum, *args, **kwargs):
        sent.append((opened[-1], signum))
        os.kill(opened[-1], signum)

    monkeypatch.setattr(os, "pidfd_open", open_handle, raising=False)
    monkeypatch.setattr(signal, "pidfd_send_signal", send, raising=False)

    spy = _SpyOnRealSignals()
    monkeypatch.setattr(os, "kill", spy)

    result = _boot(
        plan,
        tmp_path,
        monkeypatch,
        jailer=_a_jailer_that_starts_a_guest(plan, sleepers),
    )

    ours = sleepers.started[-1]
    assert result["outcome"] == "stopped_by_the_deadline"
    assert result["stop_handle"] == BY_A_PINNED_HANDLE
    assert (ours, signal.SIGKILL) in sent
    # The kill reached the sleeper through the stand-in, which calls the spied
    # ``os.kill`` itself — so the number appearing in the spy is that call and
    # not a second, independent lookup. What must not be there is a SIGKILL sent
    # before the handle was opened.
    assert opened and opened[0] == ours


def test_k1c_a_host_firecracker_validates_always_has_the_handle(sleepers):
    """Why the by-number fallback is not a hole in the supported target.

    The fallback runs where ``pidfd_open`` is missing. That is this box, and it
    is not the host the guests run on. ``pidfd_send_signal`` arrived in Linux
    5.1 and ``pidfd_open`` in 5.3, and the oldest kernel Firecracker's own policy
    lists is above both — so every host that clears the containment readiness
    check has the descriptor, and the weaker path is reachable only on hosts
    that check already reports as outside what Firecracker validates.

    Asserted rather than written down, because the floor is a constant someone
    can lower.
    """
    assert OLDEST_HOST_KERNEL_FIRECRACKER_VALIDATES >= PIDFD_OPEN_ARRIVED_IN
    assert OLDEST_HOST_KERNEL_FIRECRACKER_VALIDATES >= PIDFD_SEND_SIGNAL_ARRIVED_IN
    # And this box is below it, which is why the fallback is exercised at all.
    here = tuple(int(part) for part in platform.release().split(".")[:2] if part.isdigit())
    if here and here < PIDFD_OPEN_ARRIVED_IN:
        assert getattr(os, "pidfd_open", None) is not None, (
            "the name is expected to exist even where the syscall does not"
        )


def test_k2_this_kernel_really_does_refuse_the_stable_handle(sleepers):
    """What was measured, kept as a measurement rather than as a sentence.

    This is the observation the rejection above rests on. It is written as "if
    the call exists here, it must at least behave the way a handle would" rather
    than "it must fail", so the record stays honest on a host where the syscall
    is present — the rejection is about not depending on it, not about a claim
    that no host has it.
    """
    ours = sleepers.one()
    opener = getattr(os, "pidfd_open", None)
    if opener is None:
        pytest.skip("this Python does not expose pidfd_open at all")

    try:
        handle = opener(ours, 0)
    except OSError as refused:
        assert refused.errno == 38, (
            f"expected ENOSYS on this kernel, got {refused.errno}: {refused}"
        )
        return

    # A kernel that does implement it: the handle must stop naming the process
    # once it is gone, which is the property that would make it usable.
    try:
        sleepers.stop(ours)
        sleepers.wait_until_gone(ours)
        sender = getattr(signal, "pidfd_send_signal", None)
        if sender is not None:
            with pytest.raises(OSError):
                sender(handle, 0)
    finally:
        os.close(handle)


# --------------------------------------------------------------------------
# L — how the unknown is published
# --------------------------------------------------------------------------
#
# The launcher's new outcome does not stop at the launcher. ``read_the_boot``
# turns a boot into what the model is told, and it branches on *membership of*
# ``OUTCOMES_THAT_LEAVE_THE_HOST_RUNNING`` rather than on a list of names — so
# adding a member routes it correctly for free and silently gives it a sentence
# written about the other members. Routing together is right. Being described
# together is not: the two older members mean "this run's machine was left
# running", and this one means the number was still held by something this run
# could not show was its own guest.
#
# These are the "unknown publication" cases. They are here rather than in
# ``test_agentic_v2_exec_boot.py`` because what they are protecting is a
# property of the identity repair, not of the reader.


def _boot_that_could_not_be_identified(*, status=None) -> dict:
    return {
        "outcome": OUTCOME_STARTED_AND_NOT_IDENTIFIED,
        "command_exit_status": status,
        "results": {"/out/stdout": "", "/out/stderr": ""},
    }


_A_DEADLINE = {
    "requested_seconds": 60,
    "policy_seconds": 1200,
    "applied_seconds": 60,
    "capped_by_the_policy": False,
}

# Every way the grounds could claim the machine itself was ours or was running.
# Each is a real sentence from the sibling outcomes, which is exactly why a new
# member inheriting one of them would read as plausible.
_CLAIMS_THIS_OUTCOME_CANNOT_MAKE = (
    "was not stopped",
    "it was still running when this run let go of it",
    "was left alone",
    "did not stop",
)


def test_l1_the_unknown_is_a_backend_fault_not_a_start_failure():
    """``compute_start_failed`` would assert there was never a machine.

    That is the translation ``never_started`` gets, and folding this outcome
    into it is the mistake this whole repair exists to avoid: the jailer *did*
    write a pid file, so something started. What is unknown is whose process
    holds the number now.
    """
    from core.agentic_v2_exec_boot import read_the_boot

    read = read_the_boot(_boot_that_could_not_be_identified(), deadline=_A_DEADLINE)

    assert read["result"]["ok"] is False
    assert read["result"]["error_type"] == "compute_backend_error"
    assert read["result"]["data"] == {}
    assert read["result"]["error_type"] != "compute_start_failed"

    # And the host is still not free — the conservative direction. An unknown
    # owner is not an absent guest.
    assert read["host_left_running"] is True


def test_l2_a_finished_command_keeps_its_answer_and_the_host_stays_unfree():
    """The command's answer is the command's answer.

    Identity is a question about the machine, not about the work. Throwing a
    returncode away because the teardown could not be identified would lose a
    real result for a reason that happened after it.
    """
    from core.agentic_v2_exec_boot import read_the_boot

    read = read_the_boot(
        _boot_that_could_not_be_identified(status=0), deadline=_A_DEADLINE
    )

    assert read["result"]["ok"] is True
    assert read["result"]["data"] == {"returncode": 0}
    assert read["host_left_running"] is True


@pytest.mark.parametrize("status", [None, 0])
def test_l3_the_grounds_do_not_claim_the_machine_was_ours(status):
    """The sentence has to stop short of the one claim neither route supports.

    Two routes reach this outcome. On one the launcher ran and nothing was ever
    named; on the other something was seen holding the number the machine
    published and the interval that would have adopted it declined — liveness
    observed, ownership not. A grounds string that says *our* machine was left
    running asserts the very thing the identity check declined to assert, and
    it would do so in the one place a human reads afterwards. What both routes
    do support is weaker, and that is what has to be there instead.
    """
    from core.agentic_v2_exec_boot import read_the_boot

    grounds = read_the_boot(
        _boot_that_could_not_be_identified(status=status), deadline=_A_DEADLINE
    )["grounds"]

    for claim in _CLAIMS_THIS_OUTCOME_CANNOT_MAKE:
        assert claim not in grounds, f"grounds borrowed a sibling's claim: {claim!r}"

    # What it must say instead, in both directions.
    assert "never got a process it could name" in grounds
    assert "nothing here says the host is free" in grounds


@pytest.mark.parametrize("status", [None, 0])
def test_l4_the_grounds_name_the_outcome(status):
    """Every other row of that table names itself; this one has to as well.

    Not decoration. The run record keeps the grounds verbatim, and an outcome
    that is described but never named cannot be found again by the name the
    launcher used for it.
    """
    from core.agentic_v2_exec_boot import read_the_boot

    read = read_the_boot(
        _boot_that_could_not_be_identified(status=status), deadline=_A_DEADLINE
    )
    assert OUTCOME_STARTED_AND_NOT_IDENTIFIED in read["grounds"]


@pytest.mark.parametrize("outcome", sorted(OUTCOMES_THAT_LEAVE_THE_HOST_RUNNING))
def test_l5_every_member_of_the_set_names_itself_and_reports_a_live_host(outcome):
    """The guard is over the set, not over three names I happened to think of.

    A later member added to ``OUTCOMES_THAT_LEAVE_THE_HOST_RUNNING`` inherits
    the membership branch and therefore inherits a sentence written about
    somebody else. Parametrising over the set is what makes that arrive as a
    red test rather than as a plausible-sounding line in a run record.
    """
    from core.agentic_v2_exec_boot import read_the_boot

    boot = {
        "outcome": outcome,
        "command_exit_status": None,
        "results": {"/out/stdout": "", "/out/stderr": ""},
    }
    read = read_the_boot(boot, deadline=_A_DEADLINE)

    assert read["host_left_running"] is True
    assert outcome in read["grounds"]
    assert read["result"]["error_type"] == "compute_backend_error"


def test_l6_the_older_members_kept_their_own_wording():
    """The control for L3: I narrowed one member, not all of them.

    ``overran_and_was_left_alone`` really does mean this run's machine was left
    running, and its sentence should still say so. A repair that made every
    outcome hedge would be the over-safe direction — it would describe a known
    live guest as an unknown one.
    """
    from core.agentic_v2_exec_boot import read_the_boot

    boot = {
        "outcome": "overran_and_was_left_alone",
        "command_exit_status": 0,
        "results": {"/out/stdout": "", "/out/stderr": ""},
    }
    grounds = read_the_boot(boot, deadline=_A_DEADLINE)["grounds"]

    assert "was not stopped" in grounds
    assert "the host is not free" in grounds
    assert "never got a process it could name" not in grounds


# ---------------------------------------------------------------------------
# M — the outcome survives being overwritten
#
# ``OneCallMachine`` rewrites ``outcome`` when the work disk does not come back,
# and it was the only field carrying the leak for the two outcomes that are
# reached before any signal goes out. These are the predicate's side of that;
# the seam itself is exercised in ``test_agentic_v2_one_call_machine.py``.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("outcome", sorted(OUTCOMES_THAT_LEAVE_THE_HOST_RUNNING))
def test_m1_an_overwritten_outcome_still_reports_a_live_host(outcome):
    """Over the set for the same reason L5 is: a new member gets this free.

    A member added later is reached through the same overwrite, and a guard
    written against two names by hand would not cover it.
    """
    assert (
        the_host_was_left_running(
            {
                "outcome": "workspace_did_not_come_back",
                "outcome_before_the_carriage_failed": outcome,
                "guest_confirmed_stopped": None,
            }
        )
        is True
    )


def test_m2_an_overwritten_ordinary_boot_is_not_turned_into_a_leak():
    """The over-safe direction: the preserved field is read, not assumed.

    A call whose carriage failed after an ordinary boot left nothing on the
    host. Reporting it as occupied would strand a host that is free, which is
    the mirror-image failure of the one M1 covers.
    """
    assert (
        the_host_was_left_running(
            {
                "outcome": "workspace_did_not_come_back",
                "outcome_before_the_carriage_failed": "booted",
                "guest_confirmed_stopped": None,
            }
        )
        is False
    )


def test_m3_a_record_without_the_preserved_field_is_unchanged():
    """Every boot record written before this field existed still reads the same.

    ``.get`` answers ``None`` for them and ``None`` is not in the set, so the
    new clause cannot flip an old answer in either direction.
    """
    assert the_host_was_left_running({"outcome": "booted"}) is False
    assert the_host_was_left_running({"outcome": "overran_and_did_not_stop"}) is True
