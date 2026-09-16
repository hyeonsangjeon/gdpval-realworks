"""Running the plan C1 wrote, and the four different ways it can produce nothing.

The launcher's whole job is to add nothing. Every argument it runs comes out of
the plan, and the plan has already refused anything the policy does not permit —
so the interesting tests here are not "does it start a machine" but "does it
start *only* what it was handed", and "when no result comes back, does it say
which of the several reasons it was".

That last one matters more than it looks. With no network, no vsock and a
console pointed at ``/dev/null``, a guest that panicked on its second
instruction and a guest that ran happily and wrote nothing leave the host
exactly the same evidence: an empty work disk. Collapsing those into one
"failed" would make the next step guesswork, so the outcomes are separate and
each is reached by a different observation.

Nothing here boots anything. This box runs kernel 3.10 and cannot.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
from pathlib import Path

import pytest

from core import agentic_v2_first_boot
from core.agentic_v2_first_boot import (
    WORK_DISK_RESULTS,
    BootAbandoned,
    BootRefused,
    claim_the_jail,
    first_boot,
    place_the_images,
    unjailed_image_check,
)
from core.agentic_v2_microvm_launch import build_launch_plan


def _claimed(plan):
    """Take the jail the way ``first_boot`` does, for tests that call the steps.

    ``place_the_images`` no longer creates the directory and no longer accepts
    being called without the evidence that it is this run's, so a test that
    exercises it directly has to go through the same door the production path
    does.
    """
    return claim_the_jail(
        Path(plan["host_side"]["chroot_dir"]),
        vm_id=str(plan["vm_id"]),
        plan_sha256=str(plan["plan_sha256"]),
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
        vm_id="test-boot",
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


def _a_stand_in_guest_with_an_identity(monkeypatch, *pids: int) -> None:
    """Let the invented PIDs answer the question a real guest answers.

    The launcher will not signal a process it cannot show it started, and a
    number a test made up names nothing on the host — so a stand-in that only
    reports *alive* is half a guest. This supplies the other half: for the PIDs
    named here, "when did you start" answers with the host clock read the first
    time it is asked, which is necessarily at or after the floor the run
    recorded just before launching.

    **The answer is remembered per PID, and that is the point, not an
    optimisation.** A real process's start time never moves; answering with a
    fresh clock reading each time would make the guest look like a different
    process on every probe, and the launcher would correctly refuse to signal
    it. Getting this wrong makes a working guard look broken.

    Only the PIDs listed. Anything else keeps the host's real answer, so a test
    that wants a process the run *cannot* account for simply leaves it out.

    **Confinement is stood in for on the same terms.** The launcher's positive
    ground for "this is ours" is that the process's root is the jail this run
    made and holds, and no test process can be put behind a ``chroot`` without
    ``CAP_SYS_CHROOT``. So for the PIDs listed here — the ones the stand-in
    jailer claims to have started — that reading answers yes, and for every
    other PID the host's own ``/proc/<pid>/root`` answers. A refusal therefore
    still comes from the host rather than from this helper.
    """
    known = set(pids)
    real = agentic_v2_first_boot._when_that_process_started
    really_confined = agentic_v2_first_boot._confined_to_this_runs_jail
    really_pinned = agentic_v2_first_boot._a_proc_reference_pinned_to
    really_read = agentic_v2_first_boot._what_the_pinned_reference_still_says
    remembered: dict[int, int | None] = {}
    pinned_to: dict[int, int] = {}

    def started(pid: int) -> int | None:
        if pid not in known:
            return real(pid)
        if pid not in remembered:
            now = agentic_v2_first_boot._the_instant_this_run_launched()
            remembered[pid] = now["ticks_since_boot"]
        return remembered[pid]

    def confined(pid: int, chroot_dir, **named):
        if pid in known:
            return True, ""
        return really_confined(pid, chroot_dir, **named)

    def a_reference(pid: int) -> tuple[int | None, str, str]:
        """"Is there something to pin to you" — the third question a guest answers.

        Since 2026-09-16 the stop path opens ``/proc/<pid>`` before it asks for
        a handle, so that what it reads afterwards is a reading about one
        process rather than about a number. A number a test made up has no
        ``/proc`` entry; left real, that open answers ``ENOENT`` and a simulated
        live guest reads as a process that has already gone — true of this host,
        false of the guest the test is describing.

        The descriptor is a real one so that the close the code under test does
        is a real close, and a reference it forgets to release still shows up as
        a leak rather than as an error in the stand-in. Anything not named here
        is pinned for real.
        """
        if pid not in known:
            return really_pinned(pid)
        reference = os.open(os.devnull, os.O_RDONLY)
        pinned_to[reference] = pid
        return reference, "", ""

    def through_the_reference(pinned: int) -> tuple[str, int | None, str]:
        """What that reference still says: alive, and born when the guest was.

        Liveness for these PIDs is answered through ``os.kill``, which is where
        every test here drives it. This says *still running* so that the reading
        does not become a second, disagreeing source of the same fact.
        """
        pid = pinned_to.get(pinned)
        if pid is None:
            return really_read(pinned)
        return agentic_v2_first_boot.PINNED_STILL_RUNNING, started(pid), ""

    monkeypatch.setattr(
        "core.agentic_v2_first_boot._when_that_process_started", started
    )
    monkeypatch.setattr(
        "core.agentic_v2_first_boot._confined_to_this_runs_jail", confined
    )
    monkeypatch.setattr(
        "core.agentic_v2_first_boot._a_proc_reference_pinned_to", a_reference
    )
    monkeypatch.setattr(
        "core.agentic_v2_first_boot._what_the_pinned_reference_still_says",
        through_the_reference,
    )


def _records_every_signal(monkeypatch, into: list) -> list:
    """Record what was signalled, by whichever transport carried it.

    Patching ``os.kill`` alone was enough while ``os.kill`` was the only way a
    signal left this process. It is not any more: on a kernel that has
    ``pidfd_send_signal`` the launcher opens a handle to the PID it identified
    and signals through that, precisely so the signal cannot land on a reused
    number. A spy that watches one transport reads the other as silence.

    That is wrong in both directions and the harmless-looking direction is the
    dangerous one. A test asserting *that a signal was sent* fails loudly and
    gets looked at. A test asserting ``signalled == []`` — a refusal — passes
    while the process is being signalled behind it, which is the exact failure
    it was written to catch.

    ``into`` collects ``(pid, signal_number)`` in the order the kernel was
    asked, with no attempt to say which transport was used; that distinction
    belongs to the suites that are about the transport itself.
    """
    behind: dict[int, int] = {}

    def through_os_kill(pid, sig):
        into.append((pid, sig))

    def open_a_handle(pid, *rest):
        handle = os.open(os.devnull, os.O_RDONLY)
        behind[handle] = pid
        return handle

    def through_a_handle(handle, sig, *rest):
        into.append((behind[handle], sig))

    monkeypatch.setattr(os, "kill", through_os_kill)
    monkeypatch.setattr(os, "pidfd_open", open_a_handle, raising=False)
    monkeypatch.setattr(
        signal, "pidfd_send_signal", through_a_handle, raising=False
    )
    monkeypatch.setattr(
        agentic_v2_first_boot,
        "_the_process_a_handle_names",
        lambda handle: behind.get(handle),
    )
    return into


def _boot(plan, tmp_path, monkeypatch, *, jailer, running, results=None, reader=None):
    """Run :func:`first_boot` with the host replaced and the clock in hand.

    ``results`` hands back a fixed reading of the work disk; ``reader`` replaces
    the reading itself, for the cases where getting the files out is the thing
    that fails.
    """
    clock = _Clock()
    monkeypatch.setattr("core.agentic_v2_first_boot._run", jailer)
    monkeypatch.setattr("core.agentic_v2_first_boot._still_running", running)
    _a_stand_in_guest_with_an_identity(monkeypatch, 4242)
    monkeypatch.setattr(
        "core.agentic_v2_first_boot.files_out_of_work_disk",
        reader or (lambda image, names, **kw: dict(results or {})),
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


def _writes_the_pid_file(plan, pid=4242):
    def jailer(argv, timeout=300.0):
        Path(plan["host_side"]["pid_file"]).write_text(f"{pid}\n")
        return subprocess.CompletedProcess(argv, 0, "", "")

    return jailer


def _finished(*, exit_status="0"):
    results = {name: None for name in WORK_DISK_RESULTS}
    results["/out/stdout"] = "this ran inside the guest\n"
    results["/out/exit_status"] = exit_status
    results["/out/init_reached_the_end"] = "done\n"
    return results


# --------------------------------------------------------------------------
# the plan is the only source of arguments
# --------------------------------------------------------------------------


def test_something_that_is_not_a_plan_from_the_builder_is_not_run(tmp_path):
    with pytest.raises(BootRefused, match="not a launch plan"):
        first_boot(
            {"jailer": {"argv": ["--id", "anything"]}},
            kernel="k",
            rootfs="r",
            work_disk="w",
            uid=1,
            gid=1,
        )


def test_a_plan_edited_after_it_was_built_is_refused(plan):
    """Its hash is over its own contents, so an edit anywhere shows up here.

    The refusals live in the builder. A plan changed between being built and
    being run has been round the refusals rather than through them, and the
    arguments in it are ones nobody checked.
    """
    tampered = dict(plan)
    tampered["jailer"] = dict(plan["jailer"])
    tampered["jailer"]["argv"] = [
        arg for arg in plan["jailer"]["argv"] if arg != "--new-pid-ns"
    ]

    with pytest.raises(BootRefused, match="changed after it was built"):
        first_boot(tampered, kernel="k", rootfs="r", work_disk="w", uid=1, gid=1)


def test_the_launcher_passes_the_plans_arguments_and_adds_none(
    plan, tmp_path, monkeypatch
):
    """The one structural guarantee this module makes about itself.

    If a rule has to be applied differently, the change belongs in the builder
    where the refusals are. An argument appearing here instead would be one the
    policy never saw, and it would be invisible in the plan the artefact records.
    """
    seen: list[list[str]] = []

    def jailer(argv, timeout=300.0):
        seen.append(list(argv))
        Path(plan["host_side"]["pid_file"]).write_text("4242\n")
        return subprocess.CompletedProcess(argv, 0, "", "")

    _boot(
        plan,
        tmp_path,
        monkeypatch,
        jailer=jailer,
        running=lambda pid: False,
        results=_finished(),
    )

    assert seen == [["jailer", *plan["jailer"]["argv"]]]


# --------------------------------------------------------------------------
# the images go where the plan says, with the modes the plan implies
# --------------------------------------------------------------------------


def test_only_the_work_disk_is_writable_by_the_account_the_jailer_drops_to(
    plan, tmp_path, monkeypatch
):
    """``rootfs: read-only`` would otherwise hold only while the guest agreed.

    Firecracker's ``is_read_only`` and the kernel's ``ro`` both describe what
    the guest is told. The file mode is the part that does not depend on the
    guest, and it is the reason the two images the guest must not change are
    owned by root and the one it must change is not.
    """
    owners: dict[str, tuple[int, int]] = {}
    monkeypatch.setattr(
        os, "chown", lambda path, uid, gid: owners.__setitem__(str(path), (uid, gid))
    )

    placement = place_the_images(
        plan,
        claim=_claimed(plan),
        kernel=tmp_path / "vmlinux",
        rootfs=tmp_path / "rootfs.ext4",
        work_disk=tmp_path / "work.ext4",
        uid=997,
        gid=997,
    )

    by_path = {item["in_jail"]: item for item in placement["placed"]}
    assert by_path["/vmlinux"]["mode"] == "0o444"
    assert by_path["/rootfs.ext4"]["mode"] == "0o444"
    assert by_path["/work.ext4"]["mode"] == "0o644"
    assert by_path["/work.ext4"]["owned_by_the_jailed_user"] is True
    assert by_path["/rootfs.ext4"]["owned_by_the_jailed_user"] is False

    chroot = placement["chroot_dir"]
    assert owners[f"{chroot}/rootfs.ext4"] == (0, 0)
    assert owners[f"{chroot}/work.ext4"] == (997, 997)


def test_the_configuration_placed_in_the_jail_is_the_plans_own(
    plan, tmp_path, monkeypatch
):
    monkeypatch.setattr(os, "chown", lambda *a, **k: None)
    placement = place_the_images(
        plan,
        claim=_claimed(plan),
        kernel=tmp_path / "vmlinux",
        rootfs=tmp_path / "rootfs.ext4",
        work_disk=tmp_path / "work.ext4",
        uid=997,
        gid=997,
    )
    written = json.loads(
        (Path(placement["chroot_dir"]) / "vmconfig.json").read_text()
    )
    assert written == plan["firecracker"]["config"]
    assert written["network-interfaces"] == []
    assert "init=" in written["boot-source"]["boot_args"]


# --------------------------------------------------------------------------
# four ways to produce no result, told apart
# --------------------------------------------------------------------------


def test_a_machine_that_ran_and_answered_is_recorded_with_its_exit_status(
    plan, tmp_path, monkeypatch
):
    result = _boot(
        plan,
        tmp_path,
        monkeypatch,
        jailer=_writes_the_pid_file(plan),
        running=lambda pid: False,
        results=_finished(exit_status="0"),
    )

    assert result["outcome"] == "booted"
    assert result["command_exit_status"] == 0
    assert result["results"]["/out/stdout"] == "this ran inside the guest\n"
    assert result["stopped_by_the_deadline"] is False


def test_a_command_that_failed_inside_a_working_guest_is_still_a_boot(
    plan, tmp_path, monkeypatch
):
    """The command's exit status is not the machine's outcome.

    Conflating them is how an environment defect gets recorded as a model
    failure later, which is the distinction the whole stage is being built to
    keep.
    """
    result = _boot(
        plan,
        tmp_path,
        monkeypatch,
        jailer=_writes_the_pid_file(plan),
        running=lambda pid: False,
        results=_finished(exit_status="17"),
    )

    assert result["outcome"] == "booted"
    assert result["command_exit_status"] == 17


def test_a_jailer_that_wrote_no_pid_file_is_not_a_machine_that_never_started(
    plan, tmp_path, monkeypatch
):
    """A launcher that ran is not a launcher that put nothing on the host.

    This used to be recorded as ``never_started``, and that word is what the
    teardown gate reads, so the jail came down. A jailer that exits non-zero
    without publishing a pid file has not told this run whether it forked first,
    and the run has no other way to ask: the pid file is absent either way.

    So the answer is the one that says so, and the jail is left where it is with
    the refusal written down beside it.
    """

    def jailer(argv, timeout=300.0):
        return subprocess.CompletedProcess(argv, 1, "", "jailer: mknod failed\n")

    result = _boot(
        plan,
        tmp_path,
        monkeypatch,
        jailer=jailer,
        running=lambda pid: False,
        results={name: None for name in WORK_DISK_RESULTS},
    )

    assert result["outcome"] == "started_and_could_not_be_identified"
    assert result["pid_file"]["appeared"] is False
    assert "mknod failed" in result["jailer"]["stderr"]
    assert result["teardown"]["all_gone"] is False
    assert "never got a process it could name" in result["teardown"][
        "refused_because"
    ]
    assert Path(plan["host_side"]["chroot_dir"]).exists()


def test_a_guest_that_booted_and_wrote_nothing_is_its_own_outcome(
    plan, tmp_path, monkeypatch
):
    """Distinct from a machine that never started, and it has to be.

    One means the jail is wrong; the other means the image is. They are fixed in
    different places and the host gives the same silence for both, which is what
    the separate unjailed check exists to break.
    """
    result = _boot(
        plan,
        tmp_path,
        monkeypatch,
        jailer=_writes_the_pid_file(plan),
        running=lambda pid: False,
        results={name: None for name in WORK_DISK_RESULTS},
    )

    assert result["outcome"] == "booted_but_wrote_nothing"
    assert result["pid_file"]["appeared"] is True
    assert result["command_exit_status"] is None


def test_a_machine_that_overruns_is_killed_and_says_so(plan, tmp_path, monkeypatch):
    """The deadline is the only thing between a wedged guest and a host that waits.

    ``wall_clock_seconds`` is 1,200 in the policy and the fake clock reaches it
    without anybody waiting twenty minutes. What is being checked is that the
    launcher stops the machine and records *why* it stopped, rather than
    returning the same empty result a quiet guest returns.
    """
    signalled: list[tuple[int, int]] = []
    _records_every_signal(monkeypatch, signalled)

    result = _boot(
        plan,
        tmp_path,
        monkeypatch,
        jailer=_writes_the_pid_file(plan),
        # Alive until it is signalled, and gone afterwards. A stand-in that
        # reports alive forever is a guest that never stopped, which is a
        # different outcome with its own test; this one is about the machine
        # that does stop when the deadline says so.
        running=lambda pid: not signalled,
        results={name: None for name in WORK_DISK_RESULTS},
    )

    assert result["outcome"] == "stopped_by_the_deadline"
    assert result["stopped_by_the_deadline"] is True
    assert [pid for pid, _ in signalled] == [4242]
    assert result["ran_for_seconds"] >= result["deadline_seconds"]


# --------------------------------------------------------------------------
# what is left behind, and the check that is not the boundary
# --------------------------------------------------------------------------


def test_the_chroot_is_destroyed_and_the_result_says_whether_it_worked(
    plan, tmp_path, monkeypatch
):
    """Part of ``workdir: ephemeral-quota`` rather than tidiness.

    A chroot that survives holds the work disk, which holds whatever the guest
    wrote — so "removed" is reported per path instead of assumed from the fact
    that a removal was attempted.
    """
    result = _boot(
        plan,
        tmp_path,
        monkeypatch,
        jailer=_writes_the_pid_file(plan),
        running=lambda pid: False,
        results=_finished(),
    )

    assert result["teardown"]["all_gone"] is True
    assert not Path(plan["host_side"]["chroot_dir"]).exists()
    assert Path(str(tmp_path / "work.ext4") + ".returned").exists(), (
        "the work disk is the only channel, so it comes back before the jail goes"
    )


def test_the_result_names_the_single_channel_it_read_from(plan, tmp_path, monkeypatch):
    result = _boot(
        plan,
        tmp_path,
        monkeypatch,
        jailer=_writes_the_pid_file(plan),
        running=lambda pid: False,
        results=_finished(),
    )
    assert "work disk" in result["channel"]
    assert "/dev/null" in result["channel"]


def test_the_unjailed_check_says_it_is_not_the_contained_run(tmp_path, monkeypatch):
    """It applies none of the containment, and every field it returns says so.

    It exists only to tell a broken image from a broken jail. A caller that
    reads it as evidence of isolation is reading it wrong, and the wording is
    the only thing that stops that, so the wording is tested.
    """
    monkeypatch.setattr(
        "core.agentic_v2_first_boot._run",
        lambda argv, timeout=300.0: subprocess.CompletedProcess(
            argv, 0, "Guest-boot-time = 41 ms\n", ""
        ),
    )

    check = unjailed_image_check(
        firecracker_binary="firecracker",
        kernel=tmp_path / "vmlinux",
        rootfs=tmp_path / "rootfs.ext4",
        work_disk=tmp_path / "work.ext4",
        workdir=tmp_path / "scratch",
    )

    assert check["this_is_not_the_contained_run"] is True
    assert check["applied_containment"] is False
    assert "no rule was applied" in check["what_it_proves"]
    assert "Guest-boot-time" in check["console_tail"]


def test_the_unjailed_check_survives_a_guest_that_never_exits(tmp_path, monkeypatch):
    """A hung guest here is a normal outcome and must not take the run with it."""

    def hangs(argv, timeout=300.0):
        raise subprocess.TimeoutExpired(argv, timeout, output=b"[    0.0] Linux\n")

    monkeypatch.setattr("core.agentic_v2_first_boot._run", hangs)

    check = unjailed_image_check(
        firecracker_binary="firecracker",
        kernel=tmp_path / "vmlinux",
        rootfs=tmp_path / "rootfs.ext4",
        work_disk=tmp_path / "work.ext4",
        workdir=tmp_path / "scratch",
        seconds=1.0,
    )

    assert check["timed_out"] is True
    assert check["returncode"] is None
    assert "Linux" in check["console_tail"]


# --------------------------------------------------------------------------
# a failure after the images are placed takes this run's jail down with it —
# and only this run's
#
# Every case below fails at a different point *after* the chroot exists and
# the work disk is inside it. Before 2026-09-14 each of them raised straight
# out of first_boot and left the jail on the disk, which is where the guest's
# writes live. The control is the first test: without it, "the chroot is gone"
# would also be satisfied by a harness that never made one.
# --------------------------------------------------------------------------


def _raises(exception):
    def jailer(argv, timeout=300.0):
        raise exception

    return jailer


def _returned_copy(tmp_path):
    return Path(str(tmp_path / "work.ext4") + ".returned")


def test_a_run_that_does_not_fail_is_the_control_for_the_ones_that_do(
    plan, tmp_path, monkeypatch
):
    """The same four observations the failure cases make, on a normal run."""
    chroot = Path(plan["host_side"]["chroot_dir"])

    record = _boot(
        plan,
        tmp_path,
        monkeypatch,
        jailer=_writes_the_pid_file(plan),
        running=lambda pid: False,
        results=_finished(),
    )

    assert record["outcome"] == "booted"
    assert not chroot.exists()
    assert _returned_copy(tmp_path).exists()
    assert record["teardown"]["all_gone"] is True
    assert "after_a_failure" not in record["teardown"]


def test_a_launcher_that_times_out_leaves_the_jail_and_says_why(
    plan, tmp_path, monkeypatch
):
    """This test asserted the opposite until the independent review's F5.

    A timeout means the jailer was invoked and did not come back in time. It
    does not mean nothing started: ``--daemonize`` makes the jailer fork, so a
    Firecracker may already have been handed off and be holding this jail's work
    disk and socket open. No PID file turned up to name it, and an absent PID
    file is not a stopped machine.

    So the jail stays, with a reason attached, and the bytes still come out
    first. A directory left behind can be removed by hand once the host is known
    to be quiet; an ``rmtree`` over a live machine cannot be undone.
    """
    chroot = Path(plan["host_side"]["chroot_dir"])

    with pytest.raises(BootAbandoned) as caught:
        _boot(
            plan,
            tmp_path,
            monkeypatch,
            jailer=_raises(subprocess.TimeoutExpired(["jailer"], 120.0)),
            running=lambda pid: False,
            results=_finished(),
        )

    teardown = caught.value.teardown
    assert isinstance(caught.value.original, subprocess.TimeoutExpired)
    assert chroot.exists()
    assert teardown["all_gone"] is False
    assert "never saw a PID it could watch" in teardown["destroy_refused_because"]
    assert teardown["process"]["launch_was_attempted"] is True
    assert teardown["process"]["pid_file_appeared"] is False
    assert teardown["process"]["was_running"] is None
    # Refusing to remove is not a failure of the cleanup. It is the cleanup
    # doing what it decided to do, and the distinction is the whole of D21.
    assert teardown["clean"] is True
    assert _returned_copy(tmp_path).exists()


def test_a_jailer_that_was_never_execed_takes_its_jail_with_it(
    plan, tmp_path, monkeypatch
):
    """Not the same refusal as the timeout above, and the difference is real.

    Both reached the launch, so ``launch_was_attempted`` is ``True`` in both.
    What differs is what the call reported back. A timeout says the jailer was
    running and did not return; ``--daemonize`` means a Firecracker may already
    have been handed off, so the jail stays. A missing binary says the ``exec``
    never succeeded: ``subprocess`` learns that through the error pipe from the
    child, reaps the child, and re-raises it here with ``filename`` set to the
    executable. No jailer process ever existed, so there was nothing to hand a
    machine off to.

    That is still this run's own record of its own call and not a reading of the
    host — which is the line this module draws — and it is the narrow claim, not
    a general licence: an exception out of the launch does not mean nothing
    started, and the sibling test below holds that line.

    Refusing here is not the safe direction either way. ``vm_id`` is derived
    rather than drawn, so the jail left behind is the name this run's next
    attempt will claim, and the claim is ``exist_ok=False``. A host without the
    jailer installed — every host in this repository — would wedge the same run
    permanently on the first attempt.
    """
    chroot = Path(plan["host_side"]["chroot_dir"])

    with pytest.raises(BootAbandoned) as caught:
        _boot(
            plan,
            tmp_path,
            monkeypatch,
            jailer=_raises(FileNotFoundError(2, "No such file or directory", "jailer")),
            running=lambda pid: False,
            results=_finished(),
        )

    teardown = caught.value.teardown
    assert isinstance(caught.value.original, FileNotFoundError)
    assert teardown["process"]["launch_was_attempted"] is True
    assert teardown["process"]["launch_spawned_nothing"] is True
    assert teardown["process"]["pid_file_appeared"] is False
    assert teardown["all_gone"] is True
    assert teardown["destroy_refused_because"] is None
    assert teardown["clean"] is True
    assert not chroot.exists()
    # The bytes still came out before the jail did.
    assert _returned_copy(tmp_path).exists()


def test_an_error_that_is_not_about_the_binary_keeps_the_jail(
    plan, tmp_path, monkeypatch
):
    """The negative control for the carve-out above, and the reason it is narrow.

    ``subprocess`` can raise ``OSError`` from after the ``exec`` succeeded too —
    a read that fails while the child is already producing output. That one
    carries no ``filename``, because it is not about ``argv[0]``, and there is a
    process. Matching on the exception's *type* would collapse the two cases
    into one and authorise an ``rmtree`` over a machine that is running.
    """
    chroot = Path(plan["host_side"]["chroot_dir"])

    with pytest.raises(BootAbandoned) as caught:
        _boot(
            plan,
            tmp_path,
            monkeypatch,
            jailer=_raises(OSError(5, "Input/output error")),
            running=lambda pid: False,
            results=_finished(),
        )

    teardown = caught.value.teardown
    assert isinstance(caught.value.original, OSError)
    assert teardown["process"]["launch_was_attempted"] is True
    assert teardown["process"]["launch_spawned_nothing"] is False
    assert teardown["all_gone"] is False
    assert "never saw a PID it could watch" in teardown["destroy_refused_because"]
    assert teardown["clean"] is True
    assert chroot.exists()
    assert _returned_copy(tmp_path).exists()


def test_the_run_failure_and_the_cleanup_are_two_records_not_one(
    plan, tmp_path, monkeypatch
):
    """A launch that failed and a jail still on the disk is not one finding.

    Read as a single sentence, "the launcher timed out" is the same whether the
    chroot came down or not — and one of those is a policy breach while the
    other is a Tuesday. So the exception carries the two separately, and the
    cleanup's own verdict is a field rather than prose.
    """
    with pytest.raises(BootAbandoned) as caught:
        _boot(
            plan,
            tmp_path,
            monkeypatch,
            jailer=_raises(subprocess.TimeoutExpired(["jailer"], 120.0)),
            running=lambda pid: False,
            results=_finished(),
        )

    abandoned = caught.value
    assert isinstance(abandoned.original, subprocess.TimeoutExpired)
    assert abandoned.teardown["after_a_failure"] is True
    assert abandoned.teardown["clean"] is True
    assert abandoned.teardown["failures"] == []
    assert "TimeoutExpired" in str(abandoned)


def test_a_placement_that_fails_half_way_still_has_its_jail_removed(
    plan, tmp_path, monkeypatch
):
    """The chroot exists from the first image onwards, so half a placement leaks.

    The kernel goes in first and the rootfs second, so removing the rootfs from
    the host makes the second copy raise with one image already in the jail.
    """
    chroot = Path(plan["host_side"]["chroot_dir"])
    real_placement = place_the_images
    seen = {}

    def half_way(plan_arg, **kwargs):
        try:
            return real_placement(plan_arg, **kwargs)
        finally:
            seen["chroot_existed"] = chroot.exists()

    monkeypatch.setattr("core.agentic_v2_first_boot.place_the_images", half_way)
    (tmp_path / "rootfs.ext4").unlink()

    with pytest.raises(BootAbandoned) as caught:
        _boot(
            plan,
            tmp_path,
            monkeypatch,
            jailer=_writes_the_pid_file(plan),
            running=lambda pid: False,
            results=_finished(),
        )

    assert seen["chroot_existed"] is True
    assert isinstance(caught.value.original, FileNotFoundError)
    assert not chroot.exists()
    assert caught.value.teardown["all_gone"] is True
    # The work disk never reached the jail, so there is nothing to salvage and
    # the record says which of those two it is.
    assert caught.value.teardown["salvaged"]["returned_copy"] is None
    assert caught.value.teardown["salvaged"]["why_not"] == (
        "no work disk reached the jail"
    )


def test_a_read_that_fails_still_leaves_the_guests_bytes_beside_the_work_disk(
    plan, tmp_path, monkeypatch
):
    """Copy out first, read second — the other order loses the only copy.

    ``files_out_of_work_disk`` walks the image with ``debugfs``. An image this
    module cannot parse is exactly the case where the raw bytes are worth most,
    and reading before copying took them down with the jail.
    """
    chroot = Path(plan["host_side"]["chroot_dir"])

    def cannot_read(image, names, **kwargs):
        raise RuntimeError("debugfs could not make sense of this image")

    with pytest.raises(BootAbandoned) as caught:
        _boot(
            plan,
            tmp_path,
            monkeypatch,
            jailer=_writes_the_pid_file(plan),
            running=lambda pid: False,
            reader=cannot_read,
        )

    returned = _returned_copy(tmp_path)
    assert isinstance(caught.value.original, RuntimeError)
    assert returned.exists()
    assert returned.read_bytes() == (tmp_path / "work.ext4").read_bytes()
    assert not chroot.exists()
    salvaged = caught.value.teardown["salvaged"]
    assert salvaged["returned_copy"] == str(returned)
    assert salvaged["results_read"] is False


def test_a_read_that_takes_the_image_down_with_it_still_leaves_the_copy(
    plan, tmp_path, monkeypatch
):
    """The case the order above actually exists for, and the one that pins it.

    Added because a mutation pass found the test above passes under *either*
    order. A reader that merely raises loses nothing: the cleanup salvages the
    disk afterwards, so copy-first and read-first end in the same place. The
    order only shows when the read is what destroys the image -- which is the
    failure the production comment names, ``debugfs`` on an image it cannot
    parse -- because then there is nothing left for the cleanup to salvage and
    the copy had to have happened first or not at all.
    """
    chroot = Path(plan["host_side"]["chroot_dir"])

    def reads_it_to_pieces(image, names, **kwargs):
        Path(image).unlink()
        raise RuntimeError("debugfs could not make sense of this image")

    with pytest.raises(BootAbandoned) as caught:
        _boot(
            plan,
            tmp_path,
            monkeypatch,
            jailer=_writes_the_pid_file(plan),
            running=lambda pid: False,
            reader=reads_it_to_pieces,
        )

    returned = _returned_copy(tmp_path)
    salvaged = caught.value.teardown["salvaged"]
    assert returned.exists(), (
        "the guest's bytes are gone. The copy is the only place they existed "
        "once debugfs took the image apart, and it has to precede the read"
    )
    assert returned.read_bytes() == (tmp_path / "work.ext4").read_bytes()
    assert salvaged["returned_copy"] == str(returned)
    assert "why_not" not in salvaged
    assert not chroot.exists()


def test_a_salvage_that_cannot_be_written_says_so_and_the_jail_still_goes(
    plan, tmp_path, monkeypatch
):
    """Failing to keep the bytes is not a reason to keep the jail as well."""
    chroot = Path(plan["host_side"]["chroot_dir"])

    def jailer(argv, timeout=300.0):
        Path(plan["host_side"]["pid_file"]).write_text("4242\n")
        # The directory the copy has to write into stops accepting new entries
        # between the placement and the failure.
        os.chmod(tmp_path, 0o555)
        raise subprocess.TimeoutExpired(argv, 120.0)

    try:
        with pytest.raises(BootAbandoned) as caught:
            _boot(
                plan,
                tmp_path,
                monkeypatch,
                jailer=jailer,
                running=lambda pid: False,
                results=_finished(),
            )
    finally:
        os.chmod(tmp_path, 0o755)

    teardown = caught.value.teardown
    assert teardown["salvaged"]["returned_copy"] is None
    assert teardown["salvaged"]["why_not"] == "the work disk could not be copied out"
    assert [f["what"] for f in teardown["failures"]] == [
        "copy the work disk out of the jail"
    ]
    assert teardown["clean"] is False
    assert not chroot.exists()
    assert teardown["all_gone"] is True


def test_a_removal_that_fails_carries_its_reason_not_a_bare_false(
    plan, tmp_path, monkeypatch
):
    """"Still there" and "still there because" are one boolean and two findings."""
    chroot = Path(plan["host_side"]["chroot_dir"])

    def jailer(argv, timeout=300.0):
        # A PID this run can watch, and ``running`` below reports it already
        # gone. That is the evidence that authorises removal at all — without it
        # the cleanup refuses and this test would be asserting about a removal
        # that was never attempted, rather than about one that failed.
        Path(plan["host_side"]["pid_file"]).write_text("4242\n")
        # The jail's parent stops accepting removals after the images are in.
        os.chmod(chroot.parent, 0o555)
        raise subprocess.TimeoutExpired(argv, 120.0)

    try:
        with pytest.raises(BootAbandoned) as caught:
            _boot(
                plan,
                tmp_path,
                monkeypatch,
                jailer=jailer,
                running=lambda pid: False,
                results=_finished(),
            )
    finally:
        os.chmod(chroot.parent, 0o755)

    teardown = caught.value.teardown
    assert teardown["all_gone"] is False
    assert teardown["removed"][chroot.as_posix()] is False
    assert teardown["clean"] is False
    removal = [f for f in teardown["failures"] if f["what"] == "remove"]
    assert removal and "PermissionError" in removal[0]["error"]
    # The run's own failure is untouched by the cleanup's.
    assert isinstance(caught.value.original, subprocess.TimeoutExpired)
    # And the bytes came out before any of that was attempted.
    assert _returned_copy(tmp_path).exists()


def test_a_pid_file_that_was_already_there_is_not_this_runs_to_kill(
    plan, tmp_path, monkeypatch
):
    """Two of these can be on one host at once, and one must not stop the other.

    This used to reach the cleanup path and check the guard there. It no longer
    gets that far, and that is the fix rather than a regression: the plan puts
    the PID file *inside* the chroot, so a PID file that was already there means
    a jail that was already there, and a run that placed its images in it would
    have overwritten a live work disk and then removed the jail around it. The
    refusal happens before anything is written — the ``mkdir`` that takes the
    jail's name fails, because the name is already taken.

    The guard further down still exists and is still checked, directly, in
    ``test_v2_only_signals_what_it_started.py``.
    """
    pid_file = Path(plan["host_side"]["pid_file"])
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text("1\n")  # pid 1 is running on every host there is
    signalled: list[tuple[int, int]] = []
    _records_every_signal(monkeypatch, signalled)

    with pytest.raises(BootRefused) as caught:
        _boot(
            plan,
            tmp_path,
            monkeypatch,
            jailer=_raises(subprocess.TimeoutExpired(["jailer"], 120.0)),
            running=lambda pid: True,
            results=_finished(),
        )

    assert signalled == []
    assert "creates nothing and starts nothing" in str(caught.value)
    assert pid_file.read_text().strip() == "1"


def test_this_runs_own_machine_is_stopped_when_it_is_still_running(
    plan, tmp_path, monkeypatch
):
    """The other half of the rule: its own PID file, so its own process."""
    signalled: list[tuple[int, int]] = []
    _records_every_signal(monkeypatch, signalled)

    def jailer(argv, timeout=300.0):
        Path(plan["host_side"]["pid_file"]).write_text("4242\n")
        raise subprocess.TimeoutExpired(argv, 120.0)

    with pytest.raises(BootAbandoned) as caught:
        _boot(
            plan,
            tmp_path,
            monkeypatch,
            jailer=jailer,
            running=lambda pid: True,
            results=_finished(),
        )

    process = caught.value.teardown["process"]
    assert signalled == [(4242, signal.SIGKILL)]
    assert process["jail_held_by_this_run"] is True
    assert process["pid"] == 4242
    assert process["signalled"] is True


def test_only_the_path_the_plan_named_is_removed(plan, tmp_path, monkeypatch):
    """No glob, no parent, nothing derived from the naming convention.

    A cleanup by pattern cleans up after other runs too. The plan is hash-checked
    on the way in; a pattern invented during a failure is not.
    """
    chroot = Path(plan["host_side"]["chroot_dir"])
    somebody_elses = chroot.parent / "another-runs-jail"
    somebody_elses.mkdir(parents=True)
    (somebody_elses / "work.ext4").write_bytes(b"another guest wrote this")

    def jailer(argv, timeout=300.0):
        # Removal has to actually happen for "only the named path" to mean
        # anything, so this run leaves behind a PID it can watch and ``running``
        # reports it already stopped.
        Path(plan["host_side"]["pid_file"]).write_text("4242\n")
        raise subprocess.TimeoutExpired(argv, 120.0)

    with pytest.raises(BootAbandoned):
        _boot(
            plan,
            tmp_path,
            monkeypatch,
            jailer=jailer,
            running=lambda pid: False,
            results=_finished(),
        )

    assert not chroot.exists()
    assert somebody_elses.exists()
    assert (somebody_elses / "work.ext4").read_bytes() == b"another guest wrote this"

