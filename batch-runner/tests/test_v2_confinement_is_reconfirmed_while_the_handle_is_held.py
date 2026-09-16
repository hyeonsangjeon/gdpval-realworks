"""Identity is re-asked where it cannot go stale: inside the pinned interval.

**The gap this closes.** Confinement to this run's jail was established once, at
admission, and never again. Everything after it re-read *numbers* — the claim
file, the PID file, a start time — and a number is exactly the thing that can be
handed to a different process. ``_a_handle_pinned_to`` re-read a coarse start
time after ``pidfd_open`` and called that identity. Two processes created in the
same clock tick share that value, so the recheck could pass for a process this
run never started.

**Why one more numeric check would not have fixed it.** Every reading taken
before the descriptor exists can go stale between being read and being used;
adding a fourth adds a fourth thing that can go stale. What changes the answer is
*where* the question is asked. ``pidfd_open`` makes the kernel hold the process's
``struct pid``, so for as long as the descriptor is open that PID number cannot
be given to anything else. A confinement reading taken after the handle is held
and verified is therefore a reading about the process the handle names — not
about whoever holds the number by the time the signal goes.

So the reading moved into ``_a_handle_pinned_to``, after the handle, and both
stop paths get it because both come through
``_stop_the_process_this_run_identified``.

**Liveness is still asked first,** and this file's ``d4`` is why. Measured here
while writing it: a child killed and not yet collected keeps its start time, is
still answered by ``os.kill(pid, 0)`` — and its ``/proc/<pid>/root`` cannot be
walked, so ``_confined_to_this_runs_jail`` returns *False* for it. An ordinary
guest that ended on its own reads exactly like a stranger. Had identity been
asked first, every such machine would have become "not shown to be ours", the
jail would have been kept, and the run would have refused every later task on a
host where nothing was wrong.

**What this file can and cannot do.** ``os.pidfd_open`` on this host raises
``ENOSYS`` (measured, kernel ``3.10.102``), so the real handle path never runs.
Every case below stands a descriptor in for it, which makes this evidence about
the *seam* — the order of the questions, which verdict each answer produces, and
what is or is not sent — and not about the kernel's behaviour. Two things are
therefore out of reach and are named rather than approximated: that the kernel
really does freeze the number while the descriptor is open, and that
``pidfd_send_signal`` reaches the process the descriptor names. Both belong to a
host that has the call, and are the delta handed to B's runner. No test here
signals a process it did not create.
"""

from __future__ import annotations

import errno
import inspect
import os
import signal
import subprocess
import time
from pathlib import Path

import pytest

from core import agentic_v2_first_boot
from core.agentic_v2_first_boot import (
    BY_A_PINNED_HANDLE,
    HANDLE_GONE,
    HANDLE_NOT_SHOWN_TO_BE_OURS,
    HANDLE_TAKEN,
    _a_handle_pinned_to,
    _confined_to_this_runs_jail,
    _has_exited_but_not_been_reaped,
    _stop_the_process_this_run_identified,
    _when_that_process_started,
)

A_CHILD_THAT_OUTLIVES_THE_TEST = ["sleep", "30"]
"""Long enough that no case below races its own subject into exiting."""

LONG_ENOUGH_TO_BE_COLLECTED = 2.0
"""Seconds to wait for a killed child to reach ``Z``, before giving up on it.

Not a timing assumption the verdict rests on — if the wait runs out the case
skips rather than asserting about a process in a state it did not arrange.
"""

_REALLY_SIGNAL = os.kill
"""The real ``os.kill``, taken at import, before any case stands one in.

The stand-in below refuses to deliver a signal, and ``Popen.terminate`` goes
through that same name. Reaping has to use this reference: the stand-in is undone
after the fixture that owns the children has already torn down.
"""


class _OwnChildren:
    """Children this file started, so that every one of them is collected.

    Nothing here signals a process it did not create and nothing scans for
    processes. The handles are held so the teardown has something exact to close
    over rather than a number it went looking for.
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


class _TheHandleStandsIn:
    """A descriptor where this host has no ``pidfd_open``, and a record of it.

    ``ENOSYS`` here means the production instrument is absent, not that the code
    that uses it is untestable. What is stood in is the *acquisition* and the
    *delivery*; the ordering and the verdicts under test are the real ones.

    The signal path is recorded and never delivered. ``os.kill`` is replaced too,
    and it is replaced by something that allows the liveness probe (signal ``0``
    sends nothing) and refuses everything else — so a regression that brought
    back signalling by number would fail here rather than reach a real process.
    """

    def __init__(self) -> None:
        self.opened: list[int] = []
        self.handles: list[int] = []
        self.sent: list[tuple[int, int]] = []
        self.by_number: list[tuple[int, int]] = []

    def install(self, monkeypatch) -> None:
        def open_handle(pid, flags=0):
            self.opened.append(pid)
            handle = os.open(os.devnull, os.O_RDONLY)
            self.handles.append(handle)
            return handle

        def send(handle, which, *rest, **named):
            self.sent.append((handle, which))

        real_kill = _REALLY_SIGNAL

        def kill(pid, which, *rest, **named):
            if which == 0:
                return real_kill(pid, 0)
            self.by_number.append((pid, which))
            raise AssertionError(
                f"this file does not signal by number; something tried to send "
                f"{which} to process {pid}"
            )

        monkeypatch.setattr(os, "pidfd_open", open_handle, raising=False)
        monkeypatch.setattr(
            signal, "pidfd_send_signal", send, raising=False
        )
        monkeypatch.setattr(os, "kill", kill)

    def every_handle_is_closed(self) -> bool:
        for handle in self.handles:
            try:
                os.fstat(handle)
            except OSError as closed:
                if closed.errno == errno.EBADF:
                    continue
                raise
            return False
        return True


@pytest.fixture
def the_handle(monkeypatch):
    standing_in = _TheHandleStandsIn()
    standing_in.install(monkeypatch)
    return standing_in


def _a_child_that_has_ended_and_not_been_collected(own_children):
    """A zombie of this file's own making, or a skip.

    Arranged rather than found: the child is one this file started, and it is
    collected by the fixture either way.
    """
    child = own_children.spawn()
    started = _when_that_process_started(child.pid)
    _REALLY_SIGNAL(child.pid, signal.SIGKILL)
    deadline = time.monotonic() + LONG_ENOUGH_TO_BE_COLLECTED
    while time.monotonic() < deadline:
        if _has_exited_but_not_been_reaped(child.pid):
            return child, started
        time.sleep(0.01)
    pytest.skip("this host did not leave the killed child uncollected")


def test_d1_an_owned_confined_live_process_is_still_stopped(
    own_children, the_handle
):
    """The positive control, and the expensive direction if it ever breaks.

    A machine that is running, is this run's, and is where this run put it must
    still be stopped. The recheck is only allowed to refuse things that were
    going to be refused on better grounds; turning an ordinary stop into a
    refusal leaves a guest on the host and stops the whole run behind it.
    """
    child = own_children.spawn()
    started = _when_that_process_started(child.pid)
    assert started is not None

    # This process and its child are both rooted at /, so / is the jail they are
    # confined to — the same relation a jailed machine has to its own root.
    stop = _stop_the_process_this_run_identified(
        child.pid, started, chroot_dir=Path("/")
    )

    assert stop["handle_verdict"] == HANDLE_TAKEN
    assert stop["signalled"] is True
    assert stop["how"] == BY_A_PINNED_HANDLE
    assert stop["already_gone"] is False
    assert stop["refused_because"] == ""

    assert the_handle.opened == [child.pid], "the handle is taken by number once"
    assert the_handle.sent == [
        (the_handle.handles[0], signal.SIGKILL)
    ], "one SIGKILL, through the descriptor that was pinned, and nothing else"
    assert the_handle.by_number == []
    assert the_handle.every_handle_is_closed()

    # signal_target is not asserted: it is read out of /proc/self/fdinfo, and a
    # stood-in descriptor has no Pid: line to read. What the kernel names is a
    # question for a host that has the call.


def test_d2_a_live_process_confined_somewhere_else_is_not_signalled(
    own_children, the_handle, tmp_path
):
    """A positive mismatch: the process is there, and it is not ours.

    This is the case the whole change is for. The number is live, the start time
    matches, and the old code would have sent ``SIGKILL`` through the handle on
    the strength of those two facts alone.

    It is ``d1``'s case with one input changed. Same child, same start time, same
    stood-in descriptor, and the handle is taken in both — only the jail differs,
    and the verdict flips from stopping the process to refusing to. That pair is
    what shows the new reading is load-bearing rather than decorative, without
    needing a second copy of the module to compare against.
    """
    child = own_children.spawn()
    started = _when_that_process_started(child.pid)
    assert started is not None

    someone_elses = tmp_path / "jail" / "firecracker" / "another-run" / "root"
    someone_elses.mkdir(parents=True)

    stop = _stop_the_process_this_run_identified(
        child.pid, started, chroot_dir=someone_elses
    )

    assert stop["handle_verdict"] == HANDLE_NOT_SHOWN_TO_BE_OURS
    assert stop["signalled"] is False
    assert stop["how"] is None
    assert stop["already_gone"] is False, (
        "a process that is plainly running has not gone; calling this "
        "already_gone would tell the caller the machine stopped"
    )
    assert str(someone_elses) in stop["refused_because"]
    assert "not the jail this run made and holds" in stop["refused_because"]

    assert the_handle.opened == [child.pid], (
        "the refusal has to come after the handle was taken — that is the only "
        "interval in which the reading means anything"
    )
    assert the_handle.sent == [], "nothing is sent to a process that is not ours"
    assert the_handle.by_number == []
    assert the_handle.every_handle_is_closed(), (
        "refusing on a new branch must not leak the descriptor it refused on"
    )

    assert child.poll() is None, "and the process is still there afterwards"


def test_d3_an_unreadable_confinement_refuses_and_says_something_else(
    own_children, the_handle, tmp_path
):
    """Unknown is not the same finding as mismatch, and the reason says which.

    Both produce one verdict, because the caller does the same thing with both:
    send nothing, keep the jail, do not claim the machine stopped. A reader needs
    them apart, and that distinction is carried in the reason rather than in a
    second verdict — nothing branches on the text.
    """
    child = own_children.spawn()
    started = _when_that_process_started(child.pid)
    assert started is not None

    never_made = tmp_path / "a" / "jail" / "that" / "was" / "never" / "made"

    stop = _stop_the_process_this_run_identified(
        child.pid, started, chroot_dir=never_made
    )

    assert stop["handle_verdict"] == HANDLE_NOT_SHOWN_TO_BE_OURS
    assert stop["signalled"] is False
    assert stop["already_gone"] is False, "unknown stays unresolved"
    assert str(never_made) in stop["refused_because"]
    assert "nothing can be shown to be confined to it" in stop["refused_because"]
    assert "not the jail this run made and holds" not in stop["refused_because"], (
        "an unreadable jail is not a finding that the process is in a different "
        "one, and the reason must not read as though it were"
    )

    assert the_handle.sent == []
    assert the_handle.by_number == []
    assert the_handle.every_handle_is_closed()
    assert child.poll() is None


def test_d4_a_process_that_ended_is_gone_even_though_it_reads_as_a_stranger(
    own_children, the_handle
):
    """Liveness first, measured rather than argued.

    A child killed and not yet collected keeps its start time and still answers
    ``os.kill(pid, 0)``. Its root cannot be walked, so the confinement reading
    says *not confined* — the same answer a stranger's process gives. The first
    assertion below is that this is really so on this host; the rest is that it
    does not matter, because the question is asked in the order that makes an
    ended machine an ending rather than an intruder.
    """
    child, started = _a_child_that_has_ended_and_not_been_collected(own_children)
    assert started is not None

    confined, why_not = _confined_to_this_runs_jail(child.pid, Path("/"))
    assert confined is False, (
        "the premise of this case: an ordinary ended guest reads as unconfined. "
        "If this ever becomes True the case is no longer testing anything, and "
        "the ordering it defends still has to be kept"
    )
    assert why_not != ""

    stop = _stop_the_process_this_run_identified(
        child.pid, started, chroot_dir=Path("/")
    )

    assert stop["handle_verdict"] == HANDLE_GONE
    assert stop["already_gone"] is True, (
        "this is the ordinary ending. Reported as a refusal it keeps the jail, "
        "raises host_left_running, and stops the run on a host where the machine "
        "did exactly what was wanted"
    )
    assert stop["signalled"] is False
    assert stop["refused_because"] == ""

    assert the_handle.sent == []
    assert the_handle.by_number == []
    assert the_handle.every_handle_is_closed()


def test_d5_the_jail_cannot_be_left_out_by_a_caller(own_children, the_handle):
    """Forgetting to pass the jail is a ``TypeError``, not a signal.

    There is no default, and that is the point: a default would let a call site
    that was never updated keep compiling and keep stopping processes against
    whatever the default named. The two functions are the two places a future
    caller arrives at, so both are asked.
    """
    for named in (_a_handle_pinned_to, _stop_the_process_this_run_identified):
        parameter = inspect.signature(named).parameters["chroot_dir"]
        assert parameter.kind is inspect.Parameter.KEYWORD_ONLY, (
            f"{named.__name__} must take the jail by name, so it cannot be "
            "supplied by accident from a positional argument that means "
            "something else"
        )
        assert parameter.default is inspect.Parameter.empty, (
            f"{named.__name__} must have no default jail to fall back to"
        )

    child = own_children.spawn()
    started = _when_that_process_started(child.pid)
    assert started is not None

    with pytest.raises(TypeError):
        _stop_the_process_this_run_identified(child.pid, started)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        _a_handle_pinned_to(child.pid, started)  # type: ignore[call-arg]

    assert the_handle.opened == [], "the refusal happens before anything is pinned"
    assert the_handle.sent == []
    assert the_handle.by_number == []
    assert child.poll() is None


def test_d6_the_reading_is_taken_after_the_handle_and_not_before(
    own_children, the_handle, monkeypatch, tmp_path
):
    """The ordering, asserted directly rather than inferred from a verdict.

    ``d2`` shows that a mismatch refuses. It does not by itself show that the
    reading was taken *inside* the pinned interval — a version that read
    confinement first and opened the handle afterwards would produce the same
    verdict and the same absence of a signal, and would be the racy arrangement
    this change exists to avoid.
    """
    order: list[str] = []
    real_open = os.pidfd_open
    real_read = agentic_v2_first_boot._confined_to_this_runs_jail

    def opening(pid, flags=0):
        order.append("handle")
        return real_open(pid, flags)

    def reading(pid, chroot_dir):
        order.append("confinement")
        return real_read(pid, chroot_dir)

    monkeypatch.setattr(os, "pidfd_open", opening, raising=False)
    monkeypatch.setattr(
        agentic_v2_first_boot, "_confined_to_this_runs_jail", reading
    )

    child = own_children.spawn()
    started = _when_that_process_started(child.pid)
    assert started is not None
    someone_elses = tmp_path / "another-run" / "root"
    someone_elses.mkdir(parents=True)

    _stop_the_process_this_run_identified(
        child.pid, started, chroot_dir=someone_elses
    )

    assert order == ["handle", "confinement"], (
        "the number has to be frozen before it is asked about; read first and "
        "the answer is about whoever held the number at the time of the read"
    )
    assert the_handle.sent == []
    assert the_handle.by_number == []
