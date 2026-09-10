"""The carriage between a host workspace and a guest work disk.

These tests build **real ext4 images** with ``mke2fs`` and read them back with
``debugfs``, on a box that cannot boot a microVM at all. That is not a
compromise — the carriage is exactly the part a booted machine would not help
prove, and the two tools here are the same two that will do the work in
production. What a microVM adds is containment, and containment was measured in
stage C.

The tests that matter most are the ones about failure. ``debugfs -R`` exits 0
when it cannot find the directory, cannot write the destination and cannot read
the superblock, so every one of those has to be caught by looking at what landed
rather than at what the tool said. A carriage that fails silently reports 220
tasks' worth of models that wrote nothing.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from core.agentic_v2_exec_boot import WORKSPACE_IN_GUEST
from core.agentic_v2_work_disk import (
    BYTES_A_QUOTA_ACTUALLY_HOLDS,
    COMMAND_ON_DISK,
    RESULTS_ON_DISK,
    SCRATCH_ON_DISK,
    WORKSPACE_ON_DISK,
    WorkDiskRefused,
    carry_the_workspace_back,
    rdump_arguments,
    stage_the_work_disk,
    what_would_be_carried_in,
    workspace_out_of_work_disk,
)


needs_ext4_tools = pytest.mark.skipif(
    shutil.which("mke2fs") is None or shutil.which("debugfs") is None,
    reason="e2fsprogs is what builds and reads the work disk",
)

A_COMMAND = "#!/bin/sh\necho carried\n"

# Small enough to build quickly, large enough to hold what these tests carry.
A_SMALL_DISK = 16


def _workspace(root: Path) -> Path:
    work = root / "session" / "ws"
    (work / "job").mkdir(parents=True)
    (work / "job" / "plain.txt").write_text("hello\n", encoding="utf-8")
    return work


class TestTheTwoSidesAgreeOnWhereTheWorkspaceIs:
    def test_the_disk_directory_is_the_one_the_guest_command_cds_into(self):
        # D1 writes "cd /work/ws/<cwd>" into every command it builds. If these
        # two ever disagree the command runs in a directory that exists and is
        # empty, and the model is told its own files are not there.
        assert WORKSPACE_IN_GUEST == f"/work/{WORKSPACE_ON_DISK}"

    def test_the_command_lands_where_the_guest_init_runs_it_from(self):
        # GUEST_INIT runs `sh /work/in/command.sh`.
        assert COMMAND_ON_DISK == f"{SCRATCH_ON_DISK}/command.sh"
        assert RESULTS_ON_DISK == "out"


class TestMeasuringBeforeBuilding:
    def test_it_counts_what_is_there(self, tmp_path):
        work = _workspace(tmp_path)
        (work / "job" / "second.txt").write_text("x" * 100, encoding="utf-8")
        measured = what_would_be_carried_in(work)
        assert measured["files"] == 2
        assert measured["directories"] == 1
        assert measured["bytes"] == 106
        assert measured["fits"] is True

    def test_a_link_out_of_the_workspace_is_named_not_followed(self, tmp_path):
        work = _workspace(tmp_path)
        (work / "job" / "escape").symlink_to("/etc/passwd")
        measured = what_would_be_carried_in(work)
        assert measured["symlinks_leaving_the_workspace"] == ["job/escape"]
        # Named, and its target's size never read -- following it is the thing
        # being avoided, so the total is still only the real file's bytes.
        assert measured["bytes"] == 6

    def test_a_link_inside_the_workspace_is_not_a_problem(self, tmp_path):
        work = _workspace(tmp_path)
        (work / "job" / "local").symlink_to("plain.txt")
        assert what_would_be_carried_in(work)["symlinks_leaving_the_workspace"] == []

    def test_a_link_climbing_out_by_dots_is_caught_like_an_absolute_one(
        self, tmp_path
    ):
        work = _workspace(tmp_path)
        (work / "job" / "sneaky").symlink_to("../../../../etc/passwd")
        assert what_would_be_carried_in(work)["symlinks_leaving_the_workspace"] == [
            "job/sneaky"
        ]

    def test_the_room_is_what_a_disk_holds_and_not_what_it_is_called(self, tmp_path):
        # 256 MiB of image is 234,557,440 bytes of content. Sizing a refusal off
        # the nominal figure lets a workspace 32 MiB too large through, and it
        # then fails inside mke2fs with a message about blocks.
        assert BYTES_A_QUOTA_ACTUALLY_HOLDS < 256 * 1024 * 1024
        measured = what_would_be_carried_in(_workspace(tmp_path))
        assert measured["room_bytes"] <= BYTES_A_QUOTA_ACTUALLY_HOLDS


class TestRefusingBeforeADiskIsBuilt:
    def test_a_workspace_that_cannot_fit_is_refused_by_name(self, tmp_path):
        work = _workspace(tmp_path)
        (work / "job" / "big.bin").write_bytes(b"\0" * (2 * 1024 * 1024))
        with pytest.raises(WorkDiskRefused) as refusal:
            stage_the_work_disk(
                workspace=work,
                command_sh=A_COMMAND,
                into=tmp_path / "disk",
                quota_mib=1,
            )
        assert "mke2fs" in str(refusal.value)
        assert "2097158 bytes" in str(refusal.value)

    def test_a_link_out_of_the_workspace_stops_the_whole_carriage(self, tmp_path):
        work = _workspace(tmp_path)
        (work / "job" / "escape").symlink_to("/etc/shadow")
        with pytest.raises(WorkDiskRefused) as refusal:
            stage_the_work_disk(
                workspace=work, command_sh=A_COMMAND, into=tmp_path / "disk"
            )
        assert "job/escape" in str(refusal.value)

    def test_nothing_is_built_when_it_refuses(self, tmp_path):
        work = _workspace(tmp_path)
        (work / "job" / "escape").symlink_to("/etc/shadow")
        with pytest.raises(WorkDiskRefused):
            stage_the_work_disk(
                workspace=work, command_sh=A_COMMAND, into=tmp_path / "disk"
            )
        assert not (tmp_path / "disk" / "work.ext4").exists()


@needs_ext4_tools
class TestARealDiskWithARealWorkspaceOnIt:
    def test_it_builds_and_the_command_is_whole(self, tmp_path):
        work = _workspace(tmp_path)
        staged = stage_the_work_disk(
            workspace=work,
            command_sh=A_COMMAND,
            into=tmp_path / "disk",
            quota_mib=A_SMALL_DISK,
        )
        assert Path(staged["image"]).is_file()
        assert staged["checked"]["command_bytes"] == len(A_COMMAND.encode("utf-8"))
        assert staged["sha256"]

    def test_the_host_workspace_is_copied_not_moved(self, tmp_path):
        # A boot that goes wrong must leave the session where it was, not one
        # directory poorer.
        work = _workspace(tmp_path)
        stage_the_work_disk(
            workspace=work,
            command_sh=A_COMMAND,
            into=tmp_path / "disk",
            quota_mib=A_SMALL_DISK,
        )
        assert (work / "job" / "plain.txt").read_text() == "hello\n"

    def test_the_workspace_is_on_the_disk_where_the_command_will_look(self, tmp_path):
        work = _workspace(tmp_path)
        staged = stage_the_work_disk(
            workspace=work,
            command_sh=A_COMMAND,
            into=tmp_path / "disk",
            quota_mib=A_SMALL_DISK,
        )
        listed = subprocess.run(
            ["debugfs", "-R", f"ls -l /{WORKSPACE_ON_DISK}/job", staged["image"]],
            capture_output=True,
            text=True,
            check=False,
        )
        assert "plain.txt" in listed.stdout


@needs_ext4_tools
class TestWhatComesBackIsWhatWentIn:
    def _round_trip(self, tmp_path, populate) -> Path:
        work = _workspace(tmp_path)
        populate(work)
        staged = stage_the_work_disk(
            workspace=work,
            command_sh=A_COMMAND,
            into=tmp_path / "disk",
            quota_mib=A_SMALL_DISK,
        )
        read = workspace_out_of_work_disk(
            image=staged["image"], into=tmp_path / "back"
        )
        assert read["read_back"] is True, read["said"]
        return Path(read["root"])

    def test_bytes_that_are_not_text_survive_exactly(self, tmp_path):
        # debugfs's own "cat" comes back through a text pipe and would destroy
        # this. rdump writes the file, so it does not.
        awkward = bytes(range(256)) + b"\x00\xff\xfe" * 40
        landed = self._round_trip(
            tmp_path,
            lambda work: (work / "job" / "sheet.bin").write_bytes(awkward),
        )
        assert (landed / "job" / "sheet.bin").read_bytes() == awkward

    def test_a_nested_tree_comes_back_with_its_shape(self, tmp_path):
        def populate(work):
            deep = work / "job" / "a" / "b" / "c"
            deep.mkdir(parents=True)
            (deep / "deep.txt").write_text("down here\n", encoding="utf-8")

        landed = self._round_trip(tmp_path, populate)
        assert (landed / "job" / "a" / "b" / "c" / "deep.txt").read_text() == "down here\n"

    def test_an_empty_file_comes_back_empty_rather_than_absent(self, tmp_path):
        landed = self._round_trip(
            tmp_path, lambda work: (work / "job" / "nothing.txt").touch()
        )
        assert (landed / "job" / "nothing.txt").is_file()
        assert (landed / "job" / "nothing.txt").read_bytes() == b""

    def test_a_file_the_size_of_a_real_deliverable_survives(self, tmp_path):
        big = os.urandom(2 * 1024 * 1024)
        landed = self._round_trip(
            tmp_path, lambda work: (work / "job" / "report.bin").write_bytes(big)
        )
        assert (landed / "job" / "report.bin").read_bytes() == big


@needs_ext4_tools
class TestALinkTheGuestMadeDoesNotBecomeALinkOnTheHost:
    def _disk_holding(self, tmp_path, link_target: str) -> str:
        # Built directly rather than through stage_the_work_disk, because that
        # refuses this on the way in. The case being tested is the guest
        # creating one during the call, which no host-side refusal can prevent.
        staging = tmp_path / "staging"
        (staging / WORKSPACE_ON_DISK / "job").mkdir(parents=True)
        (staging / SCRATCH_ON_DISK).mkdir()
        (staging / WORKSPACE_ON_DISK / "job" / "real.txt").write_text("mine\n")
        (staging / WORKSPACE_ON_DISK / "job" / "made").symlink_to(link_target)
        image = tmp_path / "guest.ext4"
        subprocess.run(
            [
                "mke2fs", "-q", "-F", "-t", "ext4", "-b", "4096",
                "-d", staging.as_posix(), image.as_posix(), str(A_SMALL_DISK * 256),
            ],
            check=True,
            capture_output=True,
        )
        return image.as_posix()

    def test_a_link_pointing_into_the_host_is_dropped_and_recorded(self, tmp_path):
        image = self._disk_holding(tmp_path, "/etc/passwd")
        read = workspace_out_of_work_disk(image=image, into=tmp_path / "back")
        assert read["refused_symlinks"] == ["job/made"]
        assert not (Path(read["root"]) / "job" / "made").exists()
        # The real file it sat next to still came back. Refusing the link is not
        # refusing the call.
        assert (Path(read["root"]) / "job" / "real.txt").read_text() == "mine\n"

    def test_a_link_within_the_workspace_is_kept(self, tmp_path):
        image = self._disk_holding(tmp_path, "real.txt")
        read = workspace_out_of_work_disk(image=image, into=tmp_path / "back")
        assert read["refused_symlinks"] == []
        assert (Path(read["root"]) / "job" / "made").is_symlink()


@needs_ext4_tools
class TestFailuresThatDebugfsReportsAsSuccess:
    def test_a_disk_with_no_workspace_on_it_is_not_a_model_that_wrote_nothing(
        self, tmp_path
    ):
        empty = tmp_path / "empty.ext4"
        subprocess.run(
            ["mke2fs", "-q", "-F", "-t", "ext4", "-b", "4096", empty.as_posix(), "4096"],
            check=True,
            capture_output=True,
        )
        read = workspace_out_of_work_disk(image=empty, into=tmp_path / "back")
        assert read["read_back"] is False
        assert read["files"] == 0
        assert "not the same as a command that wrote nothing" in read["grounds"]

    def test_an_image_that_is_not_a_filesystem_reads_back_as_nothing(self, tmp_path):
        broken = tmp_path / "broken.ext4"
        broken.write_bytes(b"\0" * 8192)
        read = workspace_out_of_work_disk(image=broken, into=tmp_path / "back")
        # debugfs exits 0 here. If the returncode were trusted this would be a
        # successful read of an empty workspace.
        assert read["read_back"] is False
        assert "super-block" in read["said"] or "Filesystem not open" in read["said"]

    def test_an_image_that_is_not_there_at_all_reads_back_as_nothing(self, tmp_path):
        read = workspace_out_of_work_disk(
            image=tmp_path / "absent.ext4", into=tmp_path / "back"
        )
        assert read["read_back"] is False


@needs_ext4_tools
class TestReplacingTheHostWorkspace:
    def _staged(self, tmp_path, work):
        return stage_the_work_disk(
            workspace=work,
            command_sh=A_COMMAND,
            into=tmp_path / "disk",
            quota_mib=A_SMALL_DISK,
        )

    def test_what_the_machine_left_becomes_the_workspace(self, tmp_path):
        work = _workspace(tmp_path)
        staged = self._staged(tmp_path, work)
        # Stand in for the guest: change the disk's copy, not the host's.
        (work / "job" / "plain.txt").write_text("stale\n", encoding="utf-8")
        carried = carry_the_workspace_back(
            image=staged["image"], workspace=work, scratch=tmp_path / "scratch"
        )
        assert carried["replaced"] is True
        assert (work / "job" / "plain.txt").read_text() == "hello\n"

    def test_a_carriage_that_brought_nothing_leaves_the_session_alone(self, tmp_path):
        # The failure this exists for: deleting a session's accumulated work
        # because this one call's read-back broke would turn an infrastructure
        # fault into the permanent loss of the model's output.
        work = _workspace(tmp_path)
        (work / "job" / "earlier.txt").write_text("from turn one\n", encoding="utf-8")
        carried = carry_the_workspace_back(
            image=tmp_path / "never-built.ext4",
            workspace=work,
            scratch=tmp_path / "scratch",
        )
        assert carried["replaced"] is False
        assert carried["read_back"] is False
        assert (work / "job" / "earlier.txt").read_text() == "from turn one\n"

    def test_nothing_is_left_behind_beside_the_workspace(self, tmp_path):
        work = _workspace(tmp_path)
        staged = self._staged(tmp_path, work)
        carry_the_workspace_back(
            image=staged["image"], workspace=work, scratch=tmp_path / "scratch"
        )
        assert not work.with_name(work.name + ".previous").exists()


class TestTheArgumentsAreReadableWithoutRunningThem:
    def test_the_read_back_never_mounts_anything(self):
        argv = rdump_arguments("/tmp/x.ext4", inside="/ws", destination="/tmp/out")
        assert argv[0] == "debugfs"
        assert "mount" not in " ".join(argv)
        assert "-R" in argv

    def test_it_names_the_directory_and_the_destination(self):
        argv = rdump_arguments("/tmp/x.ext4", inside="/ws", destination="/tmp/out")
        assert argv[2] == "rdump /ws /tmp/out"
        assert argv[3] == "/tmp/x.ext4"
