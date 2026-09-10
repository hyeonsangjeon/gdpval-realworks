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
import subprocess
from pathlib import Path

import pytest

from core.agentic_v2_first_boot import (
    WORK_DISK_RESULTS,
    BootRefused,
    first_boot,
    place_the_images,
    unjailed_image_check,
)
from core.agentic_v2_microvm_launch import build_launch_plan


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


def _boot(plan, tmp_path, monkeypatch, *, jailer, running, results):
    """Run :func:`first_boot` with the host replaced and the clock in hand."""
    clock = _Clock()
    monkeypatch.setattr("core.agentic_v2_first_boot._run", jailer)
    monkeypatch.setattr("core.agentic_v2_first_boot._still_running", running)
    monkeypatch.setattr(
        "core.agentic_v2_first_boot.files_out_of_work_disk",
        lambda image, names, **kw: dict(results),
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


def test_a_jailer_that_never_wrote_a_pid_file_never_started(
    plan, tmp_path, monkeypatch
):
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

    assert result["outcome"] == "never_started"
    assert result["pid_file"]["appeared"] is False
    assert "mknod failed" in result["jailer"]["stderr"]


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
    killed: list[int] = []
    monkeypatch.setattr(
        os, "kill", lambda pid, signal_number: killed.append(pid)
    )

    result = _boot(
        plan,
        tmp_path,
        monkeypatch,
        jailer=_writes_the_pid_file(plan),
        running=lambda pid: True,
        results={name: None for name in WORK_DISK_RESULTS},
    )

    assert result["outcome"] == "stopped_by_the_deadline"
    assert result["stopped_by_the_deadline"] is True
    assert killed == [4242]
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
