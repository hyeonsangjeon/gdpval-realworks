"""Confinement is a question about a directory, not about how it is spelled.

**Why this file exists.** ``_confined_to_this_runs_jail`` compared
``/proc/<pid>/root`` against ``str(chroot_dir)``. That comparison holds only
when the kernel can render the process's root as a path the *reader* can walk,
and against the real jailer it never can: the jailer unshares a mount namespace
and ``pivot_root``s, so the jail is the root of a tree the host is not in and
the link renders as ``/`` — the same string an ordinary unjailed process gives.

Measured on ``gdpval-devhost-vm``, kernel ``6.17.0-1022-azure``, 2026-09-15,
against a real jailed ``firecracker`` (``c2-deadline``, pid 5714):

* ``readlink /proc/5714/root`` → ``/``
* ``/proc/5714/mountinfo`` root field → ``/srv/jailer/firecracker/c2-deadline/root``
* ``stat /proc/5714/root/.`` → ``2065:5242893``
* ``stat /srv/jailer/firecracker/c2-deadline/root`` → ``2065:5242893``
* the process's mount namespace ``mnt:[4026532154]``, the host's ``mnt:[4026531832]``

So the process was in the jail, exactly, and the string said it was not. The
consequence was not cosmetic: both places that stop a machine put the number
back to ``None`` when confinement fails, so the deadline could not fire and the
jail could not be removed. The measured run ended ``booted`` with a guest still
running on the host forty-five seconds after its deadline.

**What this file can and cannot do.** No test here boots a machine or enters a
mount namespace — that needs ``CAP_SYS_CHROOT`` and ``CLONE_NEWNS``, which this
suite does not have and must not acquire. What it does have is the property that
actually broke: *one directory reached by two different spellings*. The
process's own root is reached as ``/`` and named as ``/proc/..``, and those two
must agree. That is the same comparison the jailer's case turns on, asked
without privilege, and it fails on the code as it stood.
"""

from __future__ import annotations

import errno
import os
from pathlib import Path

import pytest

from core import agentic_v2_first_boot
from core.agentic_v2_first_boot import (
    _confined_to_this_runs_jail,
    _the_directory_a_process_has_as_its_root,
)

# Above /proc/sys/kernel/pid_max on any host this suite runs on, so it names
# nothing and can never be reused mid-test. A spawned-and-reaped child would
# leave a window in which the number is handed on.
A_NUMBER_NOBODY_HOLDS = 1 << 22


def test_c1_the_same_directory_spelled_differently_is_still_this_runs_jail():
    """The regression, asked without privilege.

    This process's root is ``/``. ``/proc/..`` is also ``/`` — a different
    string, the same directory, no namespace required to arrange it. The old
    comparison refuses this; the directory does not.
    """
    ours, why_not = _confined_to_this_runs_jail(os.getpid(), Path("/proc/.."))
    assert ours is True, (
        "a jail reached by a second spelling is the same jail; if this refuses, "
        "so does every pivot_root'ed machine the jailer produces"
    )
    assert why_not == ""

    plainly, why_not = _confined_to_this_runs_jail(os.getpid(), Path("/"))
    assert plainly is True, "the spelling that always worked must keep working"
    assert why_not == ""


def test_c2_the_rendering_cannot_overturn_the_identity(monkeypatch):
    """What ``/proc/<pid>/root`` *says* is not allowed to decide anything.

    Both directions are checked, because a rendering that can be trusted to
    admit can also be trusted to refuse, and neither is wanted. The reading is
    kept only so a refusal can show a reader what was seen.
    """
    monkeypatch.setattr(
        agentic_v2_first_boot,
        "_the_jail_a_process_is_confined_to",
        lambda pid: ("/srv/jailer/firecracker/pretend/root", ""),
    )
    still_ours, why_not = _confined_to_this_runs_jail(os.getpid(), Path("/proc/.."))
    assert still_ours is True, (
        "a rendering naming some other jail must not turn this run's own "
        "directory into a stranger's"
    )
    assert why_not == ""

    monkeypatch.setattr(
        agentic_v2_first_boot,
        "_the_jail_a_process_is_confined_to",
        lambda pid: (None, "the rendering could not be read at all"),
    )
    unchanged, why_not = _confined_to_this_runs_jail(os.getpid(), Path("/"))
    assert unchanged is True, (
        "an unreadable rendering is not evidence against a directory that has "
        "already been matched"
    )
    assert why_not == ""


def test_c3_a_directory_the_process_is_not_in_is_still_refused(tmp_path):
    """The negative control the repair is not allowed to cost.

    A directory that exists, is readable, and is not this process's root. The
    old code turned it away on the string; the new code turns it away on the
    inode, which is the stronger of the two — a stranger's jail could carry the
    same path in another namespace and could never carry the same inode.
    """
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
    assert "resolves to a different directory" in why_not, (
        "and it has to say the directory was the thing compared, so the next "
        "reader does not go looking at the rendered path for the answer"
    )


def test_c4_a_jail_that_cannot_be_read_refuses_rather_than_admits(tmp_path):
    """A missing jail is not an admission.

    The second reading this function takes is of the jail itself, and it can
    fail on its own — most plainly when teardown has already removed it. Nothing
    is confined to a directory that is not there, and the refusal has to say so
    rather than fall through to a match.
    """
    never_made = tmp_path / "a" / "jail" / "that" / "was" / "never" / "made"

    refused, why_not = _confined_to_this_runs_jail(os.getpid(), never_made)
    assert refused is False
    assert str(never_made) in why_not
    assert "could not be" in why_not
    assert "nothing can be shown to be confined to it" in why_not


def test_c5_the_three_unreadable_answers_stay_three(monkeypatch):
    """Gone, not permitted, and unknown are three findings, not one.

    The reader walks ``/proc/<pid>/root/.`` now instead of reading the link, so
    the three failures arrive from ``os.stat`` rather than ``os.readlink``. They
    have to stay told apart: a reader who cannot look is not a host saying no.
    """
    real_stat = os.stat

    def only_proc_fails(which_error):
        def fake(path, *rest, **named):
            if str(path).startswith("/proc/"):
                raise which_error
            return real_stat(path, *rest, **named)

        return fake

    monkeypatch.setattr(
        agentic_v2_first_boot.os, "stat", only_proc_fails(PermissionError())
    )
    denied, why_not = _the_directory_a_process_has_as_its_root(os.getpid())
    assert denied is None
    assert "may not walk into" in why_not
    assert "cannot tell" in why_not

    monkeypatch.setattr(
        agentic_v2_first_boot.os,
        "stat",
        only_proc_fails(OSError(errno.EIO, "I/O error")),
    )
    unknown, why_not = _the_directory_a_process_has_as_its_root(os.getpid())
    assert unknown is None
    assert "EIO" in why_not
    assert "not evidence either way" in why_not

    for raised in (PermissionError(), OSError(errno.EIO, "I/O error")):
        monkeypatch.setattr(
            agentic_v2_first_boot.os, "stat", only_proc_fails(raised)
        )
        verdict, _reason = _confined_to_this_runs_jail(os.getpid(), Path("/"))
        assert verdict is False, (
            "none of the three unreadable answers may be taken for a match"
        )


def test_c6_a_number_nobody_holds_is_not_confined_to_anything():
    """A pid that names nothing reads as gone, and gone is not confined."""
    nothing, why_not = _the_directory_a_process_has_as_its_root(
        A_NUMBER_NOBODY_HOLDS
    )
    assert nothing is None
    assert "nothing to confine" in why_not

    refused, why_not = _confined_to_this_runs_jail(A_NUMBER_NOBODY_HOLDS, Path("/"))
    assert refused is False
    assert "nothing to confine" in why_not


def test_c7_the_identity_is_a_pair_and_matches_the_directory_it_names():
    """What the reader returns is the jail's own ``(st_dev, st_ino)``.

    Stated as its own test because everything above rests on it: if this ever
    returns something other than the pair the plain path gives, every verdict in
    this file is answering a different question than it claims to.
    """
    pair, why_not = _the_directory_a_process_has_as_its_root(os.getpid())
    assert why_not == ""
    assert pair is not None
    assert isinstance(pair, tuple) and len(pair) == 2

    root = os.stat("/")
    assert pair == (root.st_dev, root.st_ino), (
        "this process's root is /, so the pair read through /proc must be the "
        "pair / gives directly"
    )


@pytest.mark.parametrize("spelling", ["/", "/proc/..", "/../", "/./"])
def test_c8_every_spelling_of_this_processs_root_agrees(spelling):
    """Four names for one directory, one verdict.

    The jailer's case is a fifth name this suite cannot produce. The point of
    the parametrisation is that the count of names is not what decides — the
    directory is.
    """
    ours, why_not = _confined_to_this_runs_jail(os.getpid(), Path(spelling))
    assert ours is True, f"{spelling} is this process's root under another name"
    assert why_not == ""
