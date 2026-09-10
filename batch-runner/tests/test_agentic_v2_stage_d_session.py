"""Where the two halves of stage D meet: the backend, and the disk under it.

Everything above this file has been proven on one side of a line. D2's tests
hand the backend a launcher that writes into the host workspace directly, which
proves the backend and says nothing about the disk. The carriage tests build and
read real images, which proves the disk and says nothing about the object that
holds the workspace between calls.

The failure that lives in the gap is not hypothetical, and this file exists
because it was found there. The carriage originally installed what came back by
renaming the new directory over the old one — atomic, and correct in isolation.
The backend pins ``(st_dev, st_ino)`` of its workspace once, in ``__init__``,
and keeps the descriptor. After a rename the two no longer describe the same
directory: the backend's re-check refuses, and a write through the pinned
descriptor raises. **The first ``exec_run`` of a session still looks fine.** It
is the second one that fails, and by then the model has been told the first
one's work is on disk.

So these tests run a *session* — several calls in a row, through the real
backend, over a real ext4 image that is torn down and rebuilt between them, with
only the boot itself injected. That is as close to a booted host as this box
gets, and it is the part a booted host would not have made any clearer.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from core.agentic_v2_contract import TOOL_CONTRACT_VERSION, AgenticV2Profile
from core.agentic_v2_exec_boot import EXEC_RECORD_DIR
from core.agentic_v2_microvm_backend import (
    AgenticV2MicroVMBackend,
    GuestImage,
)
from core.agentic_v2_one_call_machine import (
    WORKSPACE_DID_NOT_COME_BACK,
    OneCallMachine,
)
from core.agentic_v2_substrate import AgenticV2SubstrateManifest
from core.agentic_v2_work_disk import (
    SCRATCH_ON_DISK,
    WORKSPACE_ON_DISK,
    workspace_out_of_work_disk,
)


needs_ext4_tools = pytest.mark.skipif(
    shutil.which("mke2fs") is None or shutil.which("debugfs") is None,
    reason="e2fsprogs is what builds and reads the work disk",
)

AN_IMAGE = GuestImage(
    reference="ghcr.io/hyeonsangjeon/gdpval-sandbox",
    digest="sha256:ee6ef798631d3c3aeaed28658c640e6f5d021677449852bf2e1f18be5bd24edb",
    kernel_sha256="a" * 64,
    rootfs_sha256="b" * 64,
)


class AGuestThatReallyWritesADisk:
    """The injected boot, and the only injected thing in this file.

    It does what a booted machine does to the work disk and nothing else: reads
    the staged image, applies whatever the test said the command wrote, and
    leaves a rebuilt image at ``<work_disk>.returned`` — which is where
    ``first_boot`` leaves its copy, taken out of the jail immediately before the
    chroot is destroyed.

    ``writes`` are paths inside the workspace. ``deletes`` are too, because a
    guest deleting a file is a case the carriage has to carry as faithfully as a
    guest creating one.
    """

    def __init__(self, *, writes=None, deletes=(), status=0, outcome="booted",
                 returns_a_disk=True):
        self.writes = dict(writes or {})
        self.deletes = list(deletes)
        self.status = status
        self.outcome = outcome
        self.returns_a_disk = returns_a_disk
        self.commands: list[str] = []

    def __call__(self, plan, *, jailer_binary, kernel, rootfs, work_disk, uid, gid):
        staged = Path(work_disk)
        rebuilt = Path(str(staged) + ".returned")
        self.commands.append(self._command_off_the_disk(staged))
        if self.returns_a_disk:
            self._rebuild(staged, rebuilt)
        return {
            "outcome": self.outcome,
            "command_exit_status": self.status,
            "results": {"/out/stdout": "", "/out/stderr": ""},
            "teardown": {"all_gone": True},
        }

    def _command_off_the_disk(self, staged: Path) -> str:
        read = subprocess.run(
            ["debugfs", "-R", f"cat {SCRATCH_ON_DISK}/command.sh", staged.as_posix()],
            capture_output=True,
            text=True,
            check=False,
        )
        return read.stdout

    def _rebuild(self, staged: Path, rebuilt: Path) -> None:
        scratch = staged.parent / "guest"
        if scratch.exists():
            shutil.rmtree(scratch)
        read = workspace_out_of_work_disk(image=staged, into=scratch)
        assert read["read_back"], read["said"]

        tree = staged.parent / "guest-tree"
        if tree.exists():
            shutil.rmtree(tree)
        (tree / SCRATCH_ON_DISK).mkdir(parents=True)
        shutil.move(read["root"], str(tree / WORKSPACE_ON_DISK))

        for relative in self.deletes:
            (tree / WORKSPACE_ON_DISK / relative).unlink()
        for relative, content in self.writes.items():
            target = tree / WORKSPACE_ON_DISK / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

        subprocess.run(
            [
                "mke2fs", "-q", "-F", "-t", "ext4", "-b", "4096",
                "-d", tree.as_posix(), rebuilt.as_posix(), "8192",
            ],
            check=True,
            capture_output=True,
        )


def _machine(tmp_path, guest) -> OneCallMachine:
    images = tmp_path / "images"
    images.mkdir(exist_ok=True)
    (images / "vmlinux").write_bytes(b"stands in for a kernel\n")
    (images / "rootfs.ext4").write_bytes(b"stands in for a rootfs\n")
    return OneCallMachine(
        kernel=images / "vmlinux",
        rootfs=images / "rootfs.ext4",
        firecracker_binary=images / "firecracker",
        uid=1200,
        gid=1200,
        vcpu_count=2,
        cgroup_version=2,
        scratch=tmp_path / "scratch",
        session="gdpval-task",
        boot=guest,
    )


def _backend(tmp_path, machine) -> AgenticV2MicroVMBackend:
    return AgenticV2MicroVMBackend(
        root=tmp_path / "session",
        profile=AgenticV2Profile(
            tool_contract_version=TOOL_CONTRACT_VERSION,
            policy_profile_id="offline-full-v1",
            foundation_only=True,
        ),
        image=AN_IMAGE,
        boot_one_command=machine,
        substrate_manifest=AgenticV2SubstrateManifest.load(
            Path("sandbox/agentic_v2_capabilities.json")
        ),
    )


def _call(argv=("true",), cwd=".", timeout_seconds=60):
    return {"argv": list(argv), "cwd": cwd, "timeout_seconds": timeout_seconds}


@needs_ext4_tools
class TestASessionOfMoreThanOneCall:
    def test_a_second_call_works_after_a_first_one_replaced_the_workspace(
        self, tmp_path
    ):
        # The rename bug's exact signature: call one succeeds, call two fails
        # because the workspace the backend pinned is no longer the workspace on
        # disk. One call would never have shown it.
        backend = _backend(tmp_path, _machine(tmp_path, AGuestThatReallyWritesADisk(
            writes={"made_by_the_guest.txt": "here\n"}
        )))
        try:
            first = backend.exec_run(_call())
            second = backend.exec_run(_call())
            assert first["ok"] is True, first
            assert second["ok"] is True, second
            assert [b["boot_outcome"] for b in backend.boots] == ["booted", "booted"]
        finally:
            backend.close()

    def test_what_one_call_wrote_is_there_for_the_next_one(self, tmp_path):
        # The whole point of holding a workspace between calls: turn two's guest
        # has to see turn one's file, or the model cannot build on its own work.
        guest = AGuestThatReallyWritesADisk(writes={"job/step1.txt": "from turn one\n"})
        backend = _backend(tmp_path, _machine(tmp_path, guest))
        try:
            backend.exec_run(_call())
            guest.writes = {"job/step2.txt": "from turn two\n"}
            backend.exec_run(_call())
            work = Path(backend.work)
            assert (work / "job" / "step1.txt").read_text() == "from turn one\n"
            assert (work / "job" / "step2.txt").read_text() == "from turn two\n"
        finally:
            backend.close()

    def test_the_records_of_earlier_calls_survive_the_carriage(self, tmp_path):
        # exec_run writes each call's streams into the workspace for the model to
        # read back. A carriage that dropped them would leave the model unable to
        # see what its own earlier commands printed.
        guest = AGuestThatReallyWritesADisk()
        backend = _backend(tmp_path, _machine(tmp_path, guest))
        try:
            backend.exec_run(_call())
            backend.exec_run(_call())
            records = Path(backend.work) / EXEC_RECORD_DIR
            assert (records / "0000" / "meta.json").is_file()
            assert (records / "0001" / "meta.json").is_file()
        finally:
            backend.close()

    def test_a_file_the_guest_deleted_stays_deleted(self, tmp_path):
        guest = AGuestThatReallyWritesADisk(writes={"job/temp.txt": "scratch\n"})
        backend = _backend(tmp_path, _machine(tmp_path, guest))
        try:
            backend.exec_run(_call())
            assert (Path(backend.work) / "job" / "temp.txt").exists()
            guest.writes = {}
            guest.deletes = ["job/temp.txt"]
            backend.exec_run(_call())
            assert not (Path(backend.work) / "job" / "temp.txt").exists()
        finally:
            backend.close()

    def test_the_command_the_backend_built_is_the_one_on_the_disk(self, tmp_path):
        # D1 builds the wrapper, the carriage puts it on the disk, the guest init
        # runs it from there. Three modules, one string, checked once.
        guest = AGuestThatReallyWritesADisk()
        backend = _backend(tmp_path, _machine(tmp_path, guest))
        try:
            (Path(backend.work) / "job").mkdir()
            backend.exec_run(_call(argv=["echo", "hello"], cwd="job"))
            assert "/work/ws/job" in guest.commands[0]
        finally:
            backend.close()


@needs_ext4_tools
class TestWhenTheCarriageBreaksMidSession:
    def test_the_model_is_told_the_backend_failed_not_that_it_succeeded(
        self, tmp_path
    ):
        guest = AGuestThatReallyWritesADisk(status=0, returns_a_disk=False)
        backend = _backend(tmp_path, _machine(tmp_path, guest))
        try:
            result = backend.exec_run(_call())
            assert result["ok"] is False
            assert result["error_type"] == "compute_backend_error"
            assert backend.boots[0]["boot_outcome"] == WORKSPACE_DID_NOT_COME_BACK
        finally:
            backend.close()

    def test_the_session_survives_a_broken_call_and_keeps_going(self, tmp_path):
        # An infrastructure fault on one call must not cost the model the work it
        # had already done, and must not end the session.
        guest = AGuestThatReallyWritesADisk(writes={"job/kept.txt": "turn one\n"})
        backend = _backend(tmp_path, _machine(tmp_path, guest))
        try:
            backend.exec_run(_call())
            guest.returns_a_disk = False
            assert backend.exec_run(_call())["ok"] is False
            assert (Path(backend.work) / "job" / "kept.txt").read_text() == "turn one\n"

            guest.returns_a_disk = True
            guest.writes = {"job/after.txt": "turn three\n"}
            assert backend.exec_run(_call())["ok"] is True
            assert (Path(backend.work) / "job" / "after.txt").exists()
            assert (Path(backend.work) / "job" / "kept.txt").exists()
        finally:
            backend.close()


@needs_ext4_tools
class TestOneCallIsOneMachine:
    def test_each_call_gets_its_own_named_machine(self, tmp_path):
        machine = _machine(tmp_path, AGuestThatReallyWritesADisk())
        backend = _backend(tmp_path, machine)
        try:
            backend.exec_run(_call())
            backend.exec_run(_call())
            names = [row["vm_id"] for row in machine.record]
            assert names == ["gdpval-task-0000", "gdpval-task-0001"]
        finally:
            backend.close()

    def test_a_refused_call_never_reaches_the_machine(self, tmp_path):
        # A bad path is established on the host. Spending a boot to discover it
        # would be paying for an answer already in hand.
        machine = _machine(tmp_path, AGuestThatReallyWritesADisk())
        backend = _backend(tmp_path, machine)
        try:
            result = backend.exec_run(_call(cwd="does/not/exist"))
            assert result == {"ok": False, "error_type": "path_not_directory"}
            assert machine.record == []
            assert machine.calls == 0
        finally:
            backend.close()

    def test_nothing_of_a_finished_call_is_left_in_the_workspace(self, tmp_path):
        # The disks and the read-back scratch live under the machine's own
        # directory, never in the workspace the model reads.
        backend = _backend(tmp_path, _machine(tmp_path, AGuestThatReallyWritesADisk()))
        try:
            backend.exec_run(_call())
            present = {p.name for p in Path(backend.work).iterdir()}
            assert not {name for name in present if name.endswith(".ext4")}
            assert "staging" not in present and "previous" not in present
        finally:
            backend.close()

    def test_the_workspace_the_backend_pinned_is_never_swapped_under_it(
        self, tmp_path
    ):
        backend = _backend(tmp_path, _machine(tmp_path, AGuestThatReallyWritesADisk()))
        try:
            before = Path(backend.work).lstat()
            backend.exec_run(_call())
            backend.exec_run(_call())
            after = Path(backend.work).lstat()
            assert (after.st_dev, after.st_ino) == (before.st_dev, before.st_ino)
        finally:
            backend.close()
