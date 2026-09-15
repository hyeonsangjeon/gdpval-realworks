"""What the launch interval establishes, asked of real processes.

Every other test of the ownership evidence invents a PID and then supplies the
answer the host would have given for it — ``_a_stand_in_guest_with_an_identity``
in ``test_v2_only_signals_what_it_started.py`` remembers a start time for the
numbers the stand-in jailer publishes. That harness is right for the questions
it was built for, and it is also why the question below was never asked: a
number the harness accounts for always answers like a machine this run started,
so nothing ever presented the check with a process that is genuinely not this
run's and still passes.

These tests present exactly that. ``_when_that_process_started`` is **not**
replaced anywhere in this file. The processes are real, they are this test's own
children, they are reaped in ``finally``, and ``os.kill`` is stood in wherever a
path could reach it so that nothing here signals anything.

**What is established and what is left.** A floor on its own — *this process is
not older than the moment I launched* — admits every process on the host that
happens to be younger than it, for the whole remaining life of the run. That was
not a tick-granularity residue, and ``test_x2`` is the measurement: forty clock
ticks, an unrelated ``sleep``, no launcher and no jail anywhere near it. A second
bound, read the moment this run first holds a number, turns that away. What it
does not turn away is a number that changed hands *inside* the interval, and
``test_x3`` holds that limit in place so it can neither widen nor be quietly
claimed closed.

**What this file is not.** The children are ``sleep``. There is no ``/dev/kvm``
on this host and no microVM is booted, so nothing here measures how a real
jailer behaves or when a real Firecracker publishes its PID. The subject is the
rule the authorisation applies, which is host-independent: it is a comparison
between integers, and it admits or refuses the same way wherever it runs.

**What it also does not do.** It does not force PID reuse. Making the kernel
hand a number back would mean churning the whole PID space, which is the kind
of broad, unbounded operation this work is not permitted to perform. The cases
below separate a process that existed *before* a number was published from one
that began *after* it was read, which are the two distinctions the rule can now
draw, and they substitute a rewritten PID file for a recycled number where the
end-to-end shape is wanted.
"""

from __future__ import annotations

import errno
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from core.agentic_v2_first_boot import (
    CANNOT_RULE_OUT,
    CLOCK_TICKS_PER_SECOND as HZ,
    HANDLE_DENIED,
    HANDLE_GONE,
    HANDLE_HANDED_ON,
    HANDLE_TAKEN,
    HANDLE_UNKNOWN,
    HANDLE_UNSUPPORTED,
    MAY_SIGNAL_BY_NUMBER_INSTEAD,
    _a_handle_pinned_to,
    _clean_up_after_a_failure,
    _confined_to_this_runs_jail,
    _has_exited_but_not_been_reaped,
    _ours_is_gone,
    _started_during_this_runs_launch,
    _the_instant_the_number_was_read,
    _the_instant_this_run_launched,
    _the_jail_a_process_is_confined_to,
    _the_process_a_handle_names,
    _ticks_from_uptime,
    _when_that_process_started,
    claim_the_jail,
    first_boot,
)
from core.agentic_v2_microvm_launch import build_launch_plan

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_v2_only_signals_what_it_started import (  # noqa: E402
    _as_if_the_jailer_had_chrooted,
    _Clock,
    _finished,
    _Signals,
)


A_CHILD_THAT_OUTLIVES_THE_TEST = ["sleep", "30"]
"""Long enough that no case below races its own subject into exiting."""

WELL_PAST_ONE_TICK = 0.3
"""Seconds between one reading and the next, so the two cannot share a tick.

The host counts start times in clock ticks — 100 a second here — so a child
created in the same tick as a reading compares *equal* to it, and a verdict
drawn from that comparison would be about tick granularity rather than about the
rule. This distance is 30 ticks, which is not a granularity effect.
"""


_REALLY_SIGNAL = os.kill
"""The real ``os.kill``, held before any test stands one in.

The cases below replace ``os.kill`` so that the code under test cannot signal
anything, and ``Popen.terminate`` goes through that same name. Reaping has to
use the real one or the children would outlive the run that promised to reap
them — and it has to be *this* reference, taken at import, because the stand-in
is undone after the fixture that owns the children has already torn down.
"""


class _OwnChildren:
    """Children this test started, so that every one of them is reaped.

    Nothing in this file signals a process it did not create, and nothing scans
    for processes. This holds the handles so the ``finally`` clauses have
    something exact to close over.
    """

    def __init__(self) -> None:
        self.started: list[subprocess.Popen] = []

    def spawn(self) -> subprocess.Popen:
        child = subprocess.Popen(A_CHILD_THAT_OUTLIVES_THE_TEST)
        self.started.append(child)
        return child

    def reap_all(self) -> None:
        for child in self.started:
            if child.poll() is None:
                try:
                    _REALLY_SIGNAL(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            child.wait(timeout=10)


@pytest.fixture
def own_children():
    children = _OwnChildren()
    try:
        yield children
    finally:
        children.reap_all()


@pytest.fixture
def plan(tmp_path, monkeypatch):
    """A real plan from the real builder, over files that exist."""
    for name in ("firecracker", "vmlinux", "rootfs.ext4", "work.ext4"):
        path = tmp_path / name
        path.write_bytes(b"not really an image, but a readable file")
        path.chmod(0o755)
    monkeypatch.setattr(os, "chown", lambda *a, **k: None)
    return build_launch_plan(
        vm_id="test-launch-bound",
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


def _boot_over_real_processes(
    plan, tmp_path, monkeypatch, *, jailer, signals, in_the_jail=None
):
    """``first_boot`` with the host's two edges stood in and identity left real.

    The start-time functions are deliberately untouched. Standing in for them is
    what every other suite does and it is what makes this question invisible
    there.

    Confinement is the one part that cannot be left real here: the run's
    positive ground is that the process has this run's jail as its root, a
    chroot only the real jailer can perform. ``in_the_jail`` is what the
    stand-in jailer says it placed there, and it is per-case rather than
    blanket — every case below that is about a refusal leaves it empty, so the
    refusal comes from the host's own reading of ``/proc/<pid>/root``.
    """
    clock = _Clock()
    monkeypatch.setattr("core.agentic_v2_first_boot._run", jailer)
    _as_if_the_jailer_had_chrooted(
        monkeypatch, set() if in_the_jail is None else in_the_jail
    )
    signals.install(monkeypatch)
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


def _a_claimed_jail_holding(plan, pid: int) -> dict:
    """A jail this run holds, with ``pid`` published in it.

    The teardown cases below start here rather than from a launch, because the
    state they are about — a PID file this run is reading for the first time
    during cleanup — is reached through the failure path and not through a boot.
    """
    chroot = Path(plan["host_side"]["chroot_dir"])
    claim = claim_the_jail(
        chroot, vm_id=str(plan["vm_id"]), plan_sha256=str(plan["plan_sha256"])
    )
    (chroot / "work.ext4").write_bytes(b"whatever the guest was writing")
    Path(plan["host_side"]["pid_file"]).write_text(f"{pid}\n")
    return claim


def _teardown_over_real_processes(
    plan,
    tmp_path,
    monkeypatch,
    *,
    claim,
    launch_floor,
    number_read_at,
    signals,
    in_the_jail=None,
):
    _as_if_the_jailer_had_chrooted(
        monkeypatch, set() if in_the_jail is None else in_the_jail
    )
    signals.install(monkeypatch)
    clock = _Clock()
    return _clean_up_after_a_failure(
        host_side=plan["host_side"],
        pid_file=Path(plan["host_side"]["pid_file"]),
        claim=claim,
        launch_was_attempted=True,
        launch_spawned_nothing=False,
        launch_floor=launch_floor,
        number_read_at=number_read_at,
        work_disk=tmp_path / "work.ext4",
        salvage={"returned_copy": None, "results_read": False},
        now=clock.now,
        sleep=clock.sleep,
    )


# --------------------------------------------------------------------------
# the two ends of the interval, against real processes
# --------------------------------------------------------------------------


def test_x1_a_process_older_than_the_floor_is_refused():
    """The lower bound does turn away everything that was already running.

    This is the control for the counterexample below, and it is not a formality:
    the rule has to keep doing this, because it is the only thing standing
    between a stale number in an old PID file and a real ``SIGKILL``. The test
    process is the subject because it is certainly older than a floor read now
    and because using it costs no process at all.
    """
    floor = _the_instant_this_run_launched()
    time.sleep(WELL_PAST_ONE_TICK)
    ceiling = _the_instant_the_number_was_read()

    started, why_not = _started_during_this_runs_launch(os.getpid(), floor, ceiling)

    assert started is None
    assert "was already running" in why_not
    assert "before this run launched" in why_not


def test_x2_an_unrelated_child_born_after_the_number_was_read_is_refused(own_children):
    """The case a floor alone admitted, and the measurement of how wide that was.

    The child here is spawned by the test, after both readings are taken, with
    no launcher and no jail anywhere in the picture. It is not a guest, not a
    jailer, not a descendant of anything the module called.

    Two things are asserted and they are separate claims. The first is the size
    of the opening the floor left: this child is at least twenty clock ticks
    past it, so admitting it was never a one-tick granularity effect — the
    opening was the remaining life of the run, which is what the module's
    ``CANNOT_RULE_OUT`` said and what the function's own docstring did not. The
    second is that the upper bound closes it, and closes it *for that reason* —
    the refusal has to name the number already being in hand, or a refusal for
    some unrelated reason would read as this one working.
    """
    floor = _the_instant_this_run_launched()
    ceiling = _the_instant_the_number_was_read()
    time.sleep(WELL_PAST_ONE_TICK)
    stranger = own_children.spawn()
    time.sleep(0.05)

    started, why_not = _started_during_this_runs_launch(stranger.pid, floor, ceiling)

    assert started is None
    assert "after this run already had that number in hand" in why_not

    admitted_by_the_floor_alone, no_reason = _started_during_this_runs_launch(
        stranger.pid, floor, _the_instant_the_number_was_read()
    )
    assert no_reason == ""
    assert admitted_by_the_floor_alone - floor["ticks_since_boot"] >= 20, (
        "the opening the floor left was never a one-tick granularity effect"
    )


def test_x3_a_number_that_changed_hands_inside_the_interval_is_still_adopted(
    plan, tmp_path, monkeypatch, own_children
):
    """The residue, end to end, asserted so that it cannot be claimed closed.

    The stand-in jailer publishes a PID file the ordinary way and then the
    number in it is replaced, before the run has read it even once, by the
    number of a child born afterwards. Both children are born between the floor
    and the moment the run first holds a number, so both ends of the interval
    are satisfied and the second child is adopted. There is no earlier reading
    to compare against — ``watched`` is that number from the start — so the
    re-read at the moment of the signal finds the file unchanged and agrees.

    This substitutes a rewrite for a reused number. The two arrive at the same
    place for the same reason: what the run holds is an integer that was not the
    integer published for the process the launcher started, and nothing in the
    evidence can tell it so. Forcing an actual reuse would mean exhausting the
    PID space, which is out of bounds here.

    **This is not a defect the bounds were expected to close, and it is not
    filed as one.** It is what :data:`CANNOT_RULE_OUT` says in the artefact, and
    the last assertion pins the two together: if the residue is ever narrowed
    further, this test and that sentence have to move at the same time.

    ``os.kill`` is stood in, so the signal this asserts is a recorded call and
    not a signal.
    """
    pid_file = Path(plan["host_side"]["pid_file"])
    published = own_children.spawn()
    # Both are in the jail, which is what makes this the residue rather than a
    # case the jail closes: the second process satisfies every ground the first
    # one does, including the positive one.
    in_the_jail = {published.pid}

    def jailer(argv, timeout=300.0):
        pid_file.write_text(f"{published.pid}\n")
        # Born inside the interval, exactly where a number that changes hands
        # before the run ever reads it lands. The file is rewritten before the
        # watch loop has looked at it once.
        later = own_children.spawn()
        in_the_jail.add(later.pid)
        time.sleep(0.05)
        pid_file.write_text(f"{later.pid}\n")
        return subprocess.CompletedProcess(argv, 0, "", "")

    signals = _Signals(dies_after=0)
    result = _boot_over_real_processes(
        plan,
        tmp_path,
        monkeypatch,
        jailer=jailer,
        signals=signals,
        in_the_jail=in_the_jail,
    )

    adopted = own_children.started[-1].pid
    assert result["pid_file"]["pid_watched"] == adopted
    assert result["pid_file"]["owned_by_this_run"] is True
    assert result["pid_file"]["pid_started_at_ticks"] is not None
    assert signals.anything_reached_kill_for(adopted)

    assert "inside the interval" in CANNOT_RULE_OUT
    assert result["pid_file"]["cannot_rule_out"] == CANNOT_RULE_OUT


# --------------------------------------------------------------------------
# the launch that really is this run's, which must keep working
# --------------------------------------------------------------------------


def test_x4_an_ordinary_launch_over_a_real_process_is_still_this_runs(
    plan, tmp_path, monkeypatch, own_children
):
    """The owned case, over a real process, with nothing stood in for identity.

    The stand-in jailer starts a child and publishes its number in the ordinary
    order — the process exists, then its PID is written down. This is the shape
    an implementation that refuses everything would break, so it is the control
    that keeps a blanket refusal from scoring as a repair.

    It asserts the whole ordinary ending, not just the admission: the run owns
    the process, stops it, watches it stop, and takes the jail down.
    """

    in_the_jail: set[int] = set()

    def jailer(argv, timeout=300.0):
        child = own_children.spawn()
        in_the_jail.add(child.pid)
        time.sleep(0.05)
        Path(plan["host_side"]["pid_file"]).write_text(f"{child.pid}\n")
        return subprocess.CompletedProcess(argv, 0, "", "")

    signals = _Signals(dies_after=0)
    result = _boot_over_real_processes(
        plan,
        tmp_path,
        monkeypatch,
        jailer=jailer,
        signals=signals,
        in_the_jail=in_the_jail,
    )

    ours = own_children.started[-1].pid
    assert result["pid_file"]["pid_watched"] == ours
    assert result["pid_file"]["owned_by_this_run"] is True
    assert result["guest_confirmed_stopped"] is True
    assert result["teardown"]["all_gone"] is True
    assert not Path(plan["host_side"]["chroot_dir"]).exists()

    # Both ends of the interval go out in the record, so a reader can redo the
    # comparison rather than take the verdict. A record carrying only one of
    # them is the state this whole delta is about.
    evidence = result["pid_file"]
    assert evidence["launch_floor"]["ticks_since_boot"] is not None
    assert evidence["number_read_at"]["ticks_since_boot"] is not None
    assert (
        evidence["launch_floor"]["ticks_since_boot"]
        <= evidence["pid_started_at_ticks"]
        <= evidence["number_read_at"]["ticks_since_boot"]
    )


# --------------------------------------------------------------------------
# the teardown path, where the ceiling can be inherited or taken
# --------------------------------------------------------------------------


def test_x5_the_teardown_inherits_the_ceiling_and_refuses_a_later_stranger(
    plan, tmp_path, monkeypatch, own_children
):
    """The interval belongs to the number, not to whichever path reads it.

    The run holds a number, and only later — after something else has taken that
    place in the PID file — does it fail and clean up. Handing the teardown the
    reading the run already took keeps the interval the one that number was
    published into, and the stranger is refused. Taking a fresh reading here
    instead would end the interval at cleanup time, which is the wide interval
    the next case measures.

    Nothing is signalled: ``os.kill`` is stood in, and the assertion is that it
    was never reached for a real signal at all.
    """
    floor = _the_instant_this_run_launched()
    time.sleep(0.05)
    held_at = _the_instant_the_number_was_read()
    time.sleep(WELL_PAST_ONE_TICK)
    stranger = own_children.spawn()
    time.sleep(0.05)

    claim = _a_claimed_jail_holding(plan, stranger.pid)
    signals = _Signals(dies_after=0)
    record = _teardown_over_real_processes(
        plan,
        tmp_path,
        monkeypatch,
        claim=claim,
        launch_floor=floor,
        number_read_at=held_at,
        signals=signals,
    )

    process = record["process"]
    assert process["number_read_at_inherited"] is True
    assert process["number_read_at"]["ticks_since_boot"] == held_at["ticks_since_boot"]
    assert process["signalled"] is False
    assert process["pid_started_at_ticks"] is None
    assert "after this run already had that number in hand" in (
        process["left_alone_because"]
    )
    assert signals.real_signals == []
    assert record["all_gone"] is False
    assert Path(plan["host_side"]["chroot_dir"]).exists()


def test_x6_a_teardown_that_reads_the_number_first_has_the_wider_interval(
    plan, tmp_path, monkeypatch, own_children
):
    """The limit of the other teardown shape, measured rather than assumed.

    When the failure lands before anything read a PID, the teardown is the first
    thing to hold the number and there is no earlier reading to inherit. Its
    interval therefore runs from the launch to now, and a process born anywhere
    in between satisfies both ends. The child here is born after the floor and
    before the teardown, and it is adopted.

    That is weaker evidence than the previous case, and it is recorded as such
    rather than hidden: ``number_read_at_inherited`` is ``False``, and the
    interval that was actually used goes out in the artefact beside the verdict.
    It is also the reason the caller is made to pass the argument at all — the
    difference between the two cases is entirely in which reading is available,
    and a default would have made every teardown look like this one.

    **The interval still admits this child, and this test still measures that.**
    What has changed is that the interval is no longer what decides. The child
    is not in this run's jail, so it is refused on that ground, and the two
    assertions are kept apart on purpose: the first shows the opening is real
    and as wide as it ever was, the second shows what now stands in it. Deleting
    the first would turn a closed hole into a hole nobody remembers.
    """
    floor = _the_instant_this_run_launched()
    time.sleep(WELL_PAST_ONE_TICK)
    stranger = own_children.spawn()
    time.sleep(0.05)

    claim = _a_claimed_jail_holding(plan, stranger.pid)
    signals = _Signals(dies_after=0)
    record = _teardown_over_real_processes(
        plan,
        tmp_path,
        monkeypatch,
        claim=claim,
        launch_floor=floor,
        number_read_at=None,
        signals=signals,
    )

    process = record["process"]
    assert process["number_read_at_inherited"] is False
    assert process["number_read_at"]["ticks_since_boot"] >= floor["ticks_since_boot"]

    admitted_by_the_interval, no_reason = _started_during_this_runs_launch(
        stranger.pid, floor, process["number_read_at"]
    )
    assert no_reason == ""
    assert admitted_by_the_interval is not None, (
        "the wide interval still admits an unrelated in-window process; "
        "if it stops, this case is no longer measuring what it was written for"
    )

    assert process["confined_to_this_runs_jail"] is False
    assert process["pid_started_at_ticks"] is None
    assert process["signalled"] is False
    assert process["confirmed_stopped"] is None
    assert "not the jail this run made and holds" in process["left_alone_because"]
    assert signals.real_signals == []
    assert record["all_gone"] is False
    assert Path(plan["host_side"]["chroot_dir"]).exists(), (
        "a jail this run cannot account for is left on disk, not removed"
    )
    assert stranger.poll() is None, "the stranger is still running"


# --------------------------------------------------------------------------
# the units the two ends are read in
# --------------------------------------------------------------------------


AN_UPTIME_THE_FLOAT_PATH_GETS_WRONG = "2509733.26"
"""An uptime-shaped reading the old conversion lost a tick on.

``float("2509733.26") * 100`` is ``250973325.99999997``, so truncating it gives
``250973325`` — one tick below the ``250973326`` the file actually holds. About
one uptime-shaped string in twenty-five does this, always downward. This one is
kept literal because the failure is in the arithmetic and needs no process, no
clock and no race to reproduce: the version of this test that went looking for
it through real launches missed it on forty tries.

Just under twenty-nine days of uptime, which is a value this host reaches.
"""


def test_x7_the_two_ends_are_converted_exactly_not_through_a_float():
    """The conversion, on its own, with nothing running.

    ``/proc/uptime`` prints hundredths of a second and a tick is a hundredth of
    a second here, so the number in that file is already a whole number of
    ticks. Nothing should be lost turning it into one. Through a float something
    is, about one reading in twenty-five, and always downward — which is
    harmless at the floor and is a refusal of the ordinary launch at the
    ceiling, because it puts the upper bound below the start time of a process
    that really did begin before the number was read.

    Both ends are asserted to agree here. Where a tick is a hundredth of a
    second the division is exact and an upper bound has nothing to round up to;
    a ceiling that differs from its floor on this host would mean slack was
    added where none is needed, which widens the interval a stranger has to fall
    inside.
    """
    exactly = 250973326

    assert int(float(AN_UPTIME_THE_FLOAT_PATH_GETS_WRONG) * HZ) == exactly - 1, (
        "this string no longer reproduces the fault the exact parse exists for"
    )
    assert _ticks_from_uptime(AN_UPTIME_THE_FLOAT_PATH_GETS_WRONG) == exactly
    assert _ticks_from_uptime(AN_UPTIME_THE_FLOAT_PATH_GETS_WRONG, round_up=True) == (
        exactly
    )

    # The real file's shape: two fields, the second of which is not ours.
    assert _ticks_from_uptime(f"{AN_UPTIME_THE_FLOAT_PATH_GETS_WRONG} 999999.99") == (
        exactly
    )


def test_x8_the_ceiling_is_never_below_an_uptime_read_just_before_it(own_children):
    """The same property once more, through the functions the launch calls.

    The previous case is the arithmetic. This is the pair of readings the
    authorisation is actually built from, checked against the file between them:
    a floor may not be above a reading taken after it, and a ceiling may not be
    below one taken before it. A conversion that loses a tick breaks the second
    of those, which is the end that refuses.

    The loop is short because the property is not probabilistic — it holds on
    every reading or the conversion is wrong. The children are spawned between
    the two readings so that the shape is the launch's, and they are reaped with
    the rest.
    """
    for _ in range(20):
        floor = _the_instant_this_run_launched()["ticks_since_boot"]
        between = _ticks_from_uptime(Path("/proc/uptime").read_text())
        child = own_children.spawn()
        ceiling = _the_instant_the_number_was_read()["ticks_since_boot"]
        started = _when_that_process_started(child.pid)

        assert floor <= between <= ceiling
        assert started is not None
        assert floor <= started <= ceiling, (
            "a process forked between the two readings fell outside them"
        )


def test_x9_confinement_reads_the_host_and_answers_three_different_ways(
    own_children, tmp_path
):
    """The ground the authorisation now rests on, asked of real processes.

    Three readings, and they are three because collapsing any two of them is
    how a refusal turns into a permission. A process that is running and is not
    in the jail must be refused; a process that has gone must be refused on a
    *different* reason, because "there is nothing there" and "there is
    something there and it is not ours" are fixed in different places; and a
    process that is in the jail must be admitted, or the rule would refuse the
    guest along with everything else.

    The admitted case is this test's own process against ``/``. No test can be
    put behind a ``chroot`` — that needs ``CAP_SYS_CHROOT``, which this suite
    does not have and must not acquire — so the jail stood in for here is the
    root this process genuinely has. The comparison being exercised is the real
    one: what ``/proc/<pid>/root`` says, against what the plan named.
    """
    ours, why_not = _confined_to_this_runs_jail(os.getpid(), Path("/"))
    assert ours is True
    assert why_not == ""

    a_jail_it_was_never_in = tmp_path / "jail" / "firecracker" / "root"
    a_jail_it_was_never_in.mkdir(parents=True)
    outside, why_not = _confined_to_this_runs_jail(
        os.getpid(), a_jail_it_was_never_in
    )
    assert outside is False
    assert "not the jail this run made and holds" in why_not
    assert str(a_jail_it_was_never_in) in why_not, (
        "the reason has to name the jail that was expected, or a reader cannot "
        "tell a wrong jail from an unreadable one"
    )

    stranger = own_children.spawn()
    root, no_reason = _the_jail_a_process_is_confined_to(stranger.pid)
    assert no_reason == ""
    assert root == "/", (
        "an unrelated process reads back the host's own root; if this ever "
        "reads as a jail, confinement has stopped meaning what it says"
    )

    own_children.reap_all()
    gone, why_not = _confined_to_this_runs_jail(stranger.pid, Path("/"))
    assert gone is False, (
        "a dead process must not be confined to anything — the strongest way "
        "this could fail is by answering '/' for a number nobody holds"
    )
    assert "nothing to confine" in why_not


def test_x10_a_killed_child_that_nobody_collected_is_read_as_gone(own_children):
    """The zombie, measured here rather than argued about.

    A direct child that has been signalled and not yet collected still answers
    ``os.kill(pid, 0)`` and still reports the same start time. Both of the
    readings that ``_ours_is_gone`` had before would therefore have said "still
    running, and still ours" about a machine that was already dead, and the
    launcher would have waited out its whole confirmation deadline for an exit
    that had already happened.

    The child is this test's own and is reaped in ``finally``. Nothing here
    scans for a process or signals one it did not start.
    """
    child = own_children.spawn()
    started = _when_that_process_started(child.pid)
    assert started is not None

    _REALLY_SIGNAL(child.pid, signal.SIGKILL)
    for _ in range(100):
        if _has_exited_but_not_been_reaped(child.pid):
            break
        time.sleep(0.02)

    assert _has_exited_but_not_been_reaped(child.pid) is True
    # The two older readings, taken while it is a zombie, to show why a third
    # was needed rather than asserting that it was.
    _REALLY_SIGNAL(child.pid, 0)
    assert _when_that_process_started(child.pid) == started, (
        "the start time of a zombie does not move, so a reading that compares "
        "it cannot notice the exit"
    )
    assert _ours_is_gone(child.pid, started) is True


def test_x11_every_way_of_not_getting_a_handle_keeps_its_own_name(monkeypatch):
    """Four refusals, and only one of them may be answered by number instead.

    ``unsupported`` is a statement about this kernel or this interpreter: the
    interface is not there for anybody, so the older route is the only route
    and taking it is not a downgrade. ``denied`` and ``unknown`` are statements
    about *this attempt* on a kernel that has the interface — answering those by
    number is precisely the silent weakening this taxonomy exists to stop, and
    the earlier version of the function did exactly that by folding every
    ``OSError`` into "this kernel has no pidfd".

    The refusals are induced rather than found, because a host cannot be asked
    to deny a handle on demand. What is being checked is the reading, which is
    the part that was wrong.
    """
    for raising, expected in (
        (OSError(errno.ENOSYS, "no such system call"), HANDLE_UNSUPPORTED),
        (
            AttributeError("module 'os' has no attribute 'pidfd_open'"),
            HANDLE_UNSUPPORTED,
        ),
        (PermissionError(errno.EPERM, "not permitted"), HANDLE_DENIED),
        (OSError(errno.EACCES, "permission denied"), HANDLE_DENIED),
        (OSError(errno.EMFILE, "too many open files"), HANDLE_UNKNOWN),
    ):

        def refuse(pid, *rest, _raising=raising):
            raise _raising

        monkeypatch.setattr(os, "pidfd_open", refuse, raising=False)
        none_taken, verdict, why_not = _a_handle_pinned_to(os.getpid(), 1)
        assert none_taken is None
        assert verdict == expected, f"{raising!r} was read as {verdict}"
        assert why_not != "", "a refusal that says nothing cannot be acted on"

    assert MAY_SIGNAL_BY_NUMBER_INSTEAD == frozenset({HANDLE_UNSUPPORTED}), (
        "denied and unknown must not join this set. A kernel that has the "
        "interface and refused this run a handle has not said the process may "
        "be signalled some other way; it has said this run could not establish "
        "what it was about to signal"
    )


def _this_kernel_hands_out_handles() -> bool:
    """Whether ``pidfd_open`` works here, asked of this process and nothing else.

    Python has had ``os.pidfd_open`` since 3.9 and will happily call a syscall
    the kernel does not implement, so the attribute is not the answer — this
    box answers ``ENOSYS`` and the target host answers with a descriptor. The
    probe opens a handle on the interpreter itself and closes it immediately.
    """
    try:
        handle = os.pidfd_open(os.getpid())
    except (OSError, AttributeError):
        return False
    os.close(handle)
    return True


@pytest.mark.skipif(
    not _this_kernel_hands_out_handles(),
    reason=(
        "this kernel has no pidfd_open, so a handle cannot be taken here. The "
        "production path falls back to signalling by number, which is what "
        "HANDLE_UNSUPPORTED authorises and test_x11 covers. Measured on the "
        "target host (6.17.0-1022-azure), where this test does run."
    ),
)
def test_x12_a_real_handle_names_one_process_and_is_dropped_when_it_would_not(
    own_children,
):
    """What a handle establishes, on a kernel that actually hands one out.

    The taken case is the reason the transport changed: the descriptor names
    that PID and cannot come to name another, so a number reused between
    identifying a process and signalling it can no longer redirect the signal.

    ``handed_on`` is the same function refusing, and the assertion that matters
    there is that the handle it opened is *closed* before it returns — a
    descriptor kept on a process this run has just decided is not its own is
    both a leak and a held reference to a stranger.
    """
    child = own_children.spawn()
    started = _when_that_process_started(child.pid)
    assert started is not None

    handle, verdict, no_reason = _a_handle_pinned_to(child.pid, started)
    try:
        assert verdict == HANDLE_TAKEN
        assert no_reason == ""
        assert _the_process_a_handle_names(handle) == child.pid, (
            "the kernel's own answer for what the descriptor is pinned to, not "
            "the number this run asked with"
        )
    finally:
        if handle is not None:
            os.close(handle)

    before = len(os.listdir(f"/proc/{os.getpid()}/fd"))
    handed_on, verdict, why_not = _a_handle_pinned_to(child.pid, started + 1)
    assert handed_on is None
    assert verdict == HANDLE_HANDED_ON
    assert "handed on between this run identifying it" in why_not
    assert len(os.listdir(f"/proc/{os.getpid()}/fd")) == before, (
        "the handle opened on a process that turned out not to be ours is "
        "closed before the refusal is returned"
    )

    own_children.reap_all()
    nothing, verdict, why_not = _a_handle_pinned_to(child.pid, started)
    assert nothing is None
    assert verdict == HANDLE_GONE
    assert "already gone when a handle was asked for" in why_not
