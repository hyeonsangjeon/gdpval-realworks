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
from core.agentic_v2_first_boot import (
    OUTCOME_STARTED_AND_NOT_IDENTIFIED,
    the_host_was_left_running,
)
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


class GuestThatIsStillRunningAfterwards(Guest):
    """``Guest``, plus the fields a machine that was left behind carries.

    ``first_boot`` reaches ``overran_and_was_left_alone`` and
    ``started_and_could_not_be_identified`` by breaking out of the watch loop
    before anything is signalled, so both come back with
    ``guest_confirmed_stopped`` still ``None``. That ``None`` is why the second
    half of ``the_host_was_left_running`` does not already cover them.
    ``overran_and_did_not_stop`` is the other shape: a signal did go out and
    ``_confirm_it_stopped`` answered ``False``.
    """

    def __init__(self, *, guest_confirmed_stopped=None, **rest):
        super().__init__(**rest)
        self.guest_confirmed_stopped = guest_confirmed_stopped

    def __call__(self, plan, **handed):
        booted = super().__call__(plan, **handed)
        booted["guest_confirmed_stopped"] = self.guest_confirmed_stopped
        booted["guest_last_seen_running"] = True
        return booted


LEFT_BEHIND_WITHOUT_A_SIGNAL = ["overran_and_was_left_alone", OUTCOME_STARTED_AND_NOT_IDENTIFIED]


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
class TestALeakedMachineIsStillLeakedWhenTheDiskDidNotComeBack:
    """Two faults, both true at once, and only one field was carrying each.

    A command can exit 0 in a guest that then refuses to go while the work disk
    also fails to come back. Rewriting ``outcome`` for the second fault throws
    away the only field that said the first one happened, and
    ``the_host_was_left_running`` reads exactly that field — so a host with a
    guest still on it gets recorded as a host that is free.

    The jail is not at risk here: ``first_boot`` decides removal from its own
    locals before this dictionary is ever handed on. What is at risk is what
    the model is told and what the run record keeps.
    """

    def _leaked_and_lost_the_disk(self, tmp_path, outcome, *, confirmed=None):
        guest = GuestThatIsStillRunningAfterwards(
            status=0,
            outcome=outcome,
            returns_a_disk=False,
            guest_confirmed_stopped=confirmed,
        )
        return _machine(tmp_path, guest)(
            command_sh=A_COMMAND, workspace=_workspace(tmp_path), deadline_seconds=45
        )

    @pytest.mark.parametrize("outcome", LEFT_BEHIND_WITHOUT_A_SIGNAL)
    def test_the_host_is_not_called_free_because_the_carriage_also_failed(
        self, tmp_path, outcome
    ):
        booted = self._leaked_and_lost_the_disk(tmp_path, outcome)
        assert the_host_was_left_running(booted) is True

    def test_the_route_that_did_signal_is_not_what_makes_this_work(self, tmp_path):
        # ``overran_and_did_not_stop`` carries ``guest_confirmed_stopped``
        # False out of ``_confirm_it_stopped``, so the second half of the
        # predicate already holds it up. Here to show that the two above are
        # not covered the same way and that the fix is not redundant.
        booted = self._leaked_and_lost_the_disk(
            tmp_path, "overran_and_did_not_stop", confirmed=False
        )
        assert booted["guest_confirmed_stopped"] is False
        assert the_host_was_left_running(booted) is True

    def test_a_carriage_fault_on_its_own_does_not_invent_a_leak(self, tmp_path):
        # The over-correction, and the reason the fix cannot just be "treat
        # this outcome as occupied": nothing was left running here, and saying
        # the host is busy would strand a host that is free.
        booted = _machine(tmp_path, Guest(status=0, returns_a_disk=False))(
            command_sh=A_COMMAND, workspace=_workspace(tmp_path), deadline_seconds=45
        )
        assert the_host_was_left_running(booted) is False

    @pytest.mark.parametrize("outcome", LEFT_BEHIND_WITHOUT_A_SIGNAL)
    def test_what_the_machine_really_ended_as_is_kept_not_discarded(
        self, tmp_path, outcome
    ):
        booted = self._leaked_and_lost_the_disk(tmp_path, outcome)
        assert booted["outcome_before_the_carriage_failed"] == outcome

    @pytest.mark.parametrize("outcome", LEFT_BEHIND_WITHOUT_A_SIGNAL)
    def test_the_carriage_fault_is_still_reported_as_the_carriage_fault(
        self, tmp_path, outcome
    ):
        # Restoring the outcome in place would make ``read_the_boot`` say the
        # workspace came back. Both faults are kept, in two different fields.
        booted = self._leaked_and_lost_the_disk(tmp_path, outcome)
        assert booted["outcome"] == WORKSPACE_DID_NOT_COME_BACK
        assert booted["command_exit_status"] is None
        assert booted["command_exit_status_before_the_carriage_failed"] == 0
        result = read_the_boot(booted, deadline={"applied_seconds": 45})["result"]
        assert result["ok"] is False
        assert result["error_type"] == "compute_backend_error"


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


class TestACarriageThatRaisesIsStillACarriageThatFailed:
    """The same fault, arriving as an exception instead of as a return value.

    Every step of ``carry_the_workspace_back`` can raise: it shells out to read
    the disk, removes and remakes the previous-contents directory, lists the
    workspace, moves the children, and re-raises after putting back a
    half-carriage. Before this, all of that left ``__call__`` uncaught — and by
    then the boot has already happened.

    What that costs is not the traceback. D2 catches a launcher error and reads
    it for a ``teardown`` to say what was left behind; an exception from here
    carries none, so the record becomes *nothing was ever launched*. The
    absence is read as proof and it is not proof, because the thing that raised
    is downstream of the launch. A guest still sitting on the host is then a
    guest nothing in the run record names.

    So the cases below are the ones already written for a carriage that returns
    empty, asked again of a carriage that throws. They are expected to give the
    same answers, which is the whole claim.
    """

    class Broke(OSError):
        """What the real function raises out of ``shutil`` — an ``OSError``."""

    def _carriage_that_raises(self, monkeypatch):
        def refuse(**_handed):
            raise self.Broke("previous: Not a directory")

        monkeypatch.setattr(
            "core.agentic_v2_one_call_machine.carry_the_workspace_back", refuse
        )

    def _call(self, tmp_path, monkeypatch, guest):
        self._carriage_that_raises(monkeypatch)
        workspace = _workspace(tmp_path)
        booted = _machine(tmp_path, guest)(
            command_sh=A_COMMAND, workspace=workspace, deadline_seconds=45
        )
        return workspace, booted

    def _leaked(self, tmp_path, monkeypatch, outcome, *, confirmed=None):
        return self._call(
            tmp_path,
            monkeypatch,
            GuestThatIsStillRunningAfterwards(
                status=0, outcome=outcome, guest_confirmed_stopped=confirmed
            ),
        )[1]

    def test_the_exception_does_not_leave_the_call(self, tmp_path, monkeypatch):
        _workspace_, booted = self._call(tmp_path, monkeypatch, Guest(status=0))
        assert booted["outcome"] == WORKSPACE_DID_NOT_COME_BACK

    def test_why_it_failed_is_kept_rather_than_thrown_away(
        self, tmp_path, monkeypatch
    ):
        # Swallowing the exception is only defensible if the reason survives it.
        _workspace_, booted = self._call(tmp_path, monkeypatch, Guest(status=0))
        assert booted["workspace_carriage"]["carriage_error"] == (
            "Broke: previous: Not a directory"
        )
        assert booted["workspace_carriage"]["replaced"] is False

    def test_the_returncode_is_withheld_and_the_real_one_kept(
        self, tmp_path, monkeypatch
    ):
        _workspace_, booted = self._call(tmp_path, monkeypatch, Guest(status=0))
        assert booted["command_exit_status"] is None
        assert booted["command_exit_status_before_the_carriage_failed"] == 0

    def test_the_model_is_told_the_backend_failed(self, tmp_path, monkeypatch):
        _workspace_, booted = self._call(tmp_path, monkeypatch, Guest(status=0))
        result = read_the_boot(booted, deadline={"applied_seconds": 45})["result"]
        assert result["ok"] is False
        assert result["error_type"] == "compute_backend_error"

    def test_the_session_keeps_the_files_it_already_had(self, tmp_path, monkeypatch):
        workspace, _booted = self._call(tmp_path, monkeypatch, Guest(status=0))
        assert (workspace / "job" / "started_with.txt").read_text() == "turn one\n"

    def test_there_is_no_fingerprint_for_a_disk_that_was_not_read(
        self, tmp_path, monkeypatch
    ):
        _workspace_, booted = self._call(tmp_path, monkeypatch, Guest(status=0))
        assert booted["work_disk"]["returned_sha256"] is None
        assert len(booted["work_disk"]["staged_sha256"]) == 64

    @pytest.mark.parametrize("outcome", LEFT_BEHIND_WITHOUT_A_SIGNAL)
    def test_the_host_is_not_called_free_because_the_carriage_threw(
        self, tmp_path, monkeypatch, outcome
    ):
        # The defect this is for. Before the fix the record that reached D2 was
        # a launcher error with no teardown, and a launcher error with no
        # teardown is classified as a launch that started nothing.
        booted = self._leaked(tmp_path, monkeypatch, outcome)
        assert the_host_was_left_running(booted) is True

    @pytest.mark.parametrize("outcome", LEFT_BEHIND_WITHOUT_A_SIGNAL)
    def test_what_the_machine_really_ended_as_is_kept(
        self, tmp_path, monkeypatch, outcome
    ):
        booted = self._leaked(tmp_path, monkeypatch, outcome)
        assert booted["outcome_before_the_carriage_failed"] == outcome
        assert booted["outcome"] == WORKSPACE_DID_NOT_COME_BACK

    def test_the_route_that_did_signal_is_covered_too(self, tmp_path, monkeypatch):
        booted = self._leaked(
            tmp_path, monkeypatch, "overran_and_did_not_stop", confirmed=False
        )
        assert the_host_was_left_running(booted) is True

    def test_a_carriage_that_threw_does_not_invent_a_leak(self, tmp_path, monkeypatch):
        # The over-correction: a thrown carriage is not evidence about the
        # machine, and reporting the host occupied would strand a free one.
        _workspace_, booted = self._call(tmp_path, monkeypatch, Guest(status=0))
        assert the_host_was_left_running(booted) is False

    def test_a_machine_that_never_started_keeps_its_own_outcome(
        self, tmp_path, monkeypatch
    ):
        _workspace_, booted = self._call(
            tmp_path, monkeypatch, Guest(status=None, outcome="never_started")
        )
        assert booted["outcome"] == "never_started"
        assert "command_exit_status_before_the_carriage_failed" not in booted

    def test_the_call_is_still_written_into_the_record(self, tmp_path, monkeypatch):
        self._carriage_that_raises(monkeypatch)
        machine = _machine(tmp_path, Guest(status=0))
        machine(
            command_sh=A_COMMAND, workspace=_workspace(tmp_path), deadline_seconds=45
        )
        assert machine.record[0]["outcome"] == WORKSPACE_DID_NOT_COME_BACK
        assert machine.record[0]["carriage"]["replaced"] is False

    def test_an_interrupt_is_not_turned_into_a_workspace_fault(
        self, tmp_path, monkeypatch
    ):
        # ``first_boot`` cleans up and re-raises KeyboardInterrupt and
        # SystemExit bare. If this caught BaseException it would be the place
        # that decided an interrupt was a carriage failure.
        def interrupt(**_handed):
            raise KeyboardInterrupt

        monkeypatch.setattr(
            "core.agentic_v2_one_call_machine.carry_the_workspace_back", interrupt
        )
        with pytest.raises(KeyboardInterrupt):
            _machine(tmp_path, Guest(status=0))(
                command_sh=A_COMMAND,
                workspace=_workspace(tmp_path),
                deadline_seconds=45,
            )


@needs_ext4_tools
class TestTheRealCarriageReallyDoesRaise:
    """The hypothesis above, asked of the real function rather than a stand-in.

    Without this the guard stands against an exception nobody has seen. The
    failure arranged here is an ordinary one — the scratch directory a carriage
    keeps the workspace's previous contents in is a file — and it reaches
    ``shutil.rmtree`` after the disk has been read and before anything is
    moved, so the workspace is left whole and the exception is the real
    function's own.
    """

    def test_the_machine_survives_a_failure_it_did_not_stage(self, tmp_path):
        # The per-call directory name is settled by the session and the counter,
        # so the first call of "task-abc" can have its scratch prepared for it.
        back = tmp_path / "scratch" / "task-abc-0000" / "back"
        back.mkdir(parents=True)
        (back / "previous").write_text("not a directory\n", encoding="utf-8")

        workspace = _workspace(tmp_path)
        booted = _machine(tmp_path, Guest(status=0, wrote={"job/a.txt": "a\n"}))(
            command_sh=A_COMMAND, workspace=workspace, deadline_seconds=45
        )

        # NotADirectoryError is a name no stand-in in this file produces, so it
        # is the real carriage that raised and the guard that caught it.
        assert booted["workspace_carriage"]["carriage_error"].startswith(
            "NotADirectoryError"
        )
        assert booted["outcome"] == WORKSPACE_DID_NOT_COME_BACK
        assert booted["command_exit_status_before_the_carriage_failed"] == 0
        assert (workspace / "job" / "started_with.txt").read_text() == "turn one\n"

