"""One call, one machine — everything about it except the machine.

The boot is injected, exactly as stage C injected it: this box runs kernel 3.10
and cannot start a microVM. What is real here is the rest, and the rest is what
would otherwise be discovered expensively on a booted host — that the plan a
call builds is the policy with one bound tightened and nothing else moved, that
the workspace is on the disk the boot is handed, that what the guest wrote gets
back to the host, and that a command whose files did not survive the trip is not
reported to the model as a command that succeeded.

The stand-in boot writes a *real ext4 image* where ``first_boot`` would leave
one, so the read-back is exercised rather than simulated.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from core.agentic_v2_exec_boot import read_the_boot
from core.agentic_v2_one_call_machine import (
    THE_ONE_RULE_A_CALL_MAY_TIGHTEN,
    WORKSPACE_DID_NOT_COME_BACK,
    MachineRefused,
    OneCallMachine,
    policy_for_this_call,
)
from core.agentic_v2_substrate import REQUIRED_MICROVM_POLICY
from core.agentic_v2_work_disk import SCRATCH_ON_DISK, WORKSPACE_ON_DISK


needs_ext4_tools = pytest.mark.skipif(
    shutil.which("mke2fs") is None or shutil.which("debugfs") is None,
    reason="e2fsprogs is what builds and reads the work disk",
)

A_COMMAND = "#!/bin/sh\ncd /work/ws/job\necho ran\n"


class Guest:
    """A stand-in for a booted machine, which really writes a work disk back.

    ``first_boot`` copies the disk out of the jail to ``<work_disk>.returned``
    before destroying the chroot, so that is where this leaves one too. What it
    puts on it is whatever the test asked for, which is how "the guest wrote a
    file" is expressed without a guest.
    """

    def __init__(self, *, wrote=None, status=0, outcome="booted", returns_a_disk=True):
        self.wrote = wrote or {}
        self.status = status
        self.outcome = outcome
        self.returns_a_disk = returns_a_disk
        self.plans: list[dict] = []
        self.disks: list[str] = []

    def __call__(self, plan, *, jailer_binary, kernel, rootfs, work_disk, uid, gid):
        self.plans.append(dict(plan))
        self.disks.append(str(work_disk))
        if self.returns_a_disk:
            self._leave_a_disk(Path(str(work_disk) + ".returned"))
        return {
            "outcome": self.outcome,
            "command_exit_status": self.status,
            "results": {"/out/stdout": "ran\n", "/out/stderr": ""},
            "teardown": {"all_gone": True},
            "vm_id": plan["vm_id"],
        }

    def _leave_a_disk(self, at: Path) -> None:
        staging = at.parent / f"{at.name}-staging"
        (staging / WORKSPACE_ON_DISK / "job").mkdir(parents=True, exist_ok=True)
        (staging / SCRATCH_ON_DISK).mkdir(parents=True, exist_ok=True)
        for name, text in self.wrote.items():
            target = staging / WORKSPACE_ON_DISK / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        subprocess.run(
            [
                "mke2fs", "-q", "-F", "-t", "ext4", "-b", "4096",
                "-d", staging.as_posix(), at.as_posix(), "4096",
            ],
            check=True,
            capture_output=True,
        )


def _workspace(root: Path) -> Path:
    work = root / "session" / "ws"
    (work / "job").mkdir(parents=True)
    (work / "job" / "started_with.txt").write_text("turn one\n", encoding="utf-8")
    return work


def _machine(tmp_path, guest) -> OneCallMachine:
    # The kernel and rootfs are real files with real bytes because
    # build_launch_plan reads and hashes both, and refuses a plan whose images
    # are not there. Stand-ins for the images, not for the check.
    images = tmp_path / "images"
    images.mkdir(exist_ok=True)
    (images / "vmlinux").write_bytes(b"not a kernel, but a file that is here\n")
    (images / "rootfs.ext4").write_bytes(b"not a rootfs, but a file that is here\n")
    return OneCallMachine(
        kernel=images / "vmlinux",
        rootfs=images / "rootfs.ext4",
        firecracker_binary=images / "firecracker",
        uid=1200,
        gid=1200,
        vcpu_count=2,
        cgroup_version=2,
        scratch=tmp_path / "scratch",
        session="task-abc",
        boot=guest,
    )


class TestOneBoundMovesAndTheRestDoNot:
    def test_exactly_one_rule_differs_from_the_policy(self):
        tightened = policy_for_this_call(60)
        differs = [
            name
            for name in REQUIRED_MICROVM_POLICY
            if tightened[name] != REQUIRED_MICROVM_POLICY[name]
        ]
        assert differs == [THE_ONE_RULE_A_CALL_MAY_TIGHTEN]

    def test_it_is_a_whole_policy_and_not_a_patch(self):
        # build_launch_plan refuses a policy missing a rule or holding an extra
        # one, which is what makes "nothing else moved" checkable.
        assert set(policy_for_this_call(60)) == set(REQUIRED_MICROVM_POLICY)

    def test_a_call_cannot_ask_for_longer_than_the_policy_allows(self):
        allowed = int(REQUIRED_MICROVM_POLICY[THE_ONE_RULE_A_CALL_MAY_TIGHTEN])
        with pytest.raises(MachineRefused) as refusal:
            policy_for_this_call(allowed + 1)
        assert "may not loosen" in str(refusal.value)

    @pytest.mark.parametrize("bad", [0, -5, None, True, 12.5, "60"])
    def test_a_deadline_that_is_not_a_bound_is_refused(self, bad):
        with pytest.raises(MachineRefused):
            policy_for_this_call(bad)


@needs_ext4_tools
class TestWhatOneCallHandsToTheBoot:
    def test_the_tightened_deadline_reaches_the_plan_the_boot_runs(self, tmp_path):
        guest = Guest()
        _machine(tmp_path, guest)(
            command_sh=A_COMMAND, workspace=_workspace(tmp_path), deadline_seconds=45
        )
        assert guest.plans[0]["host_side"]["deadline_seconds"] == 45

    def test_the_workspace_is_on_the_disk_the_boot_is_given(self, tmp_path):
        guest = Guest()
        _machine(tmp_path, guest)(
            command_sh=A_COMMAND, workspace=_workspace(tmp_path), deadline_seconds=45
        )
        listed = subprocess.run(
            ["debugfs", "-R", f"ls /{WORKSPACE_ON_DISK}/job", guest.disks[0]],
            capture_output=True,
            text=True,
            check=False,
        )
        assert "started_with.txt" in listed.stdout

    def test_the_command_is_on_the_disk_where_the_guest_init_looks(self, tmp_path):
        guest = Guest()
        _machine(tmp_path, guest)(
            command_sh=A_COMMAND, workspace=_workspace(tmp_path), deadline_seconds=45
        )
        read = subprocess.run(
            ["debugfs", "-R", f"cat {SCRATCH_ON_DISK}/command.sh", guest.disks[0]],
            capture_output=True,
            text=True,
            check=False,
        )
        assert "cd /work/ws/job" in read.stdout

    def test_two_calls_are_two_machines_with_different_names(self, tmp_path):
        guest = Guest()
        machine = _machine(tmp_path, guest)
        workspace = _workspace(tmp_path)
        machine(command_sh=A_COMMAND, workspace=workspace, deadline_seconds=45)
        machine(command_sh=A_COMMAND, workspace=workspace, deadline_seconds=45)
        names = [plan["vm_id"] for plan in guest.plans]
        assert names == ["task-abc-0000", "task-abc-0001"]

    def test_the_name_is_one_the_jailer_would_accept(self, tmp_path):
        machine = _machine(tmp_path, Guest())
        machine.session = "task/with bad..chars"
        name = machine.name_the_machine()
        assert len(name) <= 64 and name.isascii() and name[0].isalnum()
        assert all(part.isalnum() for part in name.split("-") if part)


@needs_ext4_tools
class TestWhatTheGuestWroteReachesTheHost:
    def test_a_file_the_guest_made_is_in_the_workspace_afterwards(self, tmp_path):
        workspace = _workspace(tmp_path)
        guest = Guest(wrote={"job/made_by_the_guest.txt": "from inside\n"})
        booted = _machine(tmp_path, guest)(
            command_sh=A_COMMAND, workspace=workspace, deadline_seconds=45
        )
        assert booted["workspace_carriage"]["replaced"] is True
        assert (workspace / "job" / "made_by_the_guest.txt").read_text() == "from inside\n"

    def test_the_workspace_is_what_came_back_and_not_what_went_in(self, tmp_path):
        # The guest's disk does not carry started_with.txt, so a workspace that
        # still has it was never replaced -- it was merged, which would let a
        # deleted file come back from the dead every call.
        workspace = _workspace(tmp_path)
        guest = Guest(wrote={"job/only_this.txt": "replaced\n"})
        _machine(tmp_path, guest)(
            command_sh=A_COMMAND, workspace=workspace, deadline_seconds=45
        )
        assert (workspace / "job" / "only_this.txt").exists()
        assert not (workspace / "job" / "started_with.txt").exists()

    def test_the_record_holds_one_row_per_call_with_what_it_carried(self, tmp_path):
        workspace = _workspace(tmp_path)
        machine = _machine(tmp_path, Guest(wrote={"job/a.txt": "a\n"}))
        machine(command_sh=A_COMMAND, workspace=workspace, deadline_seconds=45)
        machine(command_sh=A_COMMAND, workspace=workspace, deadline_seconds=45)
        assert [row["call"] for row in machine.record] == [0, 1]
        assert machine.record[0]["deadline_seconds"] == 45
        assert machine.record[0]["carriage"]["replaced"] is True


@needs_ext4_tools
class TestACommandWhoseFilesDidNotSurviveIsNotASuccess:
    def _call_with_no_disk_coming_back(self, tmp_path):
        workspace = _workspace(tmp_path)
        guest = Guest(status=0, returns_a_disk=False)
        booted = _machine(tmp_path, guest)(
            command_sh=A_COMMAND, workspace=workspace, deadline_seconds=45
        )
        return workspace, booted

    def test_the_returncode_is_withheld_rather_than_handed_over(self, tmp_path):
        _workspace_, booted = self._call_with_no_disk_coming_back(tmp_path)
        assert booted["command_exit_status"] is None
        assert booted["outcome"] == WORKSPACE_DID_NOT_COME_BACK

    def test_the_status_the_guest_really_wrote_is_kept_not_discarded(self, tmp_path):
        _workspace_, booted = self._call_with_no_disk_coming_back(tmp_path)
        assert booted["command_exit_status_before_the_carriage_failed"] == 0

    def test_the_model_is_told_the_backend_failed(self, tmp_path):
        # Read through D1, because what the model sees is read_the_boot's answer
        # and not this dictionary.
        _workspace_, booted = self._call_with_no_disk_coming_back(tmp_path)
        result = read_the_boot(booted, deadline={"applied_seconds": 45})["result"]
        assert result["ok"] is False
        assert result["error_type"] == "compute_backend_error"

    def test_the_session_keeps_the_files_it_already_had(self, tmp_path):
        # The failure this exists for: losing a session's accumulated work
        # because one call's carriage broke.
        workspace, _booted = self._call_with_no_disk_coming_back(tmp_path)
        assert (workspace / "job" / "started_with.txt").read_text() == "turn one\n"

    def test_a_machine_that_never_started_keeps_its_own_outcome(self, tmp_path):
        # No exit status, so there is nothing for the carriage to override, and
        # calling this a carriage fault would hide a launcher fault.
        guest = Guest(status=None, outcome="never_started", returns_a_disk=False)
        booted = _machine(tmp_path, guest)(
            command_sh=A_COMMAND, workspace=_workspace(tmp_path), deadline_seconds=45
        )
        assert booted["outcome"] == "never_started"
        result = read_the_boot(booted, deadline={"applied_seconds": 45})["result"]
        assert result["error_type"] == "compute_start_failed"


@needs_ext4_tools
class TestTheRecordSaysWhatWasBootedAndWhatWasLeft:
    def test_both_disks_are_fingerprinted(self, tmp_path):
        booted = _machine(tmp_path, Guest(wrote={"job/a.txt": "a\n"}))(
            command_sh=A_COMMAND, workspace=_workspace(tmp_path), deadline_seconds=45
        )
        disks = booted["work_disk"]
        assert len(disks["staged_sha256"]) == 64
        assert len(disks["returned_sha256"]) == 64
        assert disks["staged_sha256"] != disks["returned_sha256"]

    def test_the_teardown_the_boot_reported_is_carried_into_the_record(self, tmp_path):
        machine = _machine(tmp_path, Guest(wrote={"job/a.txt": "a\n"}))
        machine(
            command_sh=A_COMMAND, workspace=_workspace(tmp_path), deadline_seconds=45
        )
        assert machine.record[0]["teardown"] == {"all_gone": True}
