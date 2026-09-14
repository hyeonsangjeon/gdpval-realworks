"""Signalling, stopping and cleaning up only what this run itself started.

Four things go wrong on the way to a real microVM, and all four have the same
shape: the launcher acts on a process or a directory without first establishing
that it is *this run's*. On a host with one machine that is invisible. On a host
with two — which is the whole point of per-call isolation — it means one run
SIGKILLs another run's guest, copies over its live work disk, and then removes
its jail.

The rule these tests pin is narrow and worth stating plainly: **absence of a PID
file is not proof of ownership.** The plan puts the PID file *inside* the chroot
(``<chroot>/firecracker.pid``) and names the chroot as the thing to remove
afterwards, so a jail that was already there carries both a stranger's PID and a
stranger's disk, and the damage from proceeding is not one signal but three
destructive operations.

Nothing here boots anything. ``os.kill`` is stood in for so the probes and the
signals are observable, and the jailer is stood in for because this box has no
``/dev/kvm``. Everything else — the plan builder, ``place_the_images``,
``first_boot``'s own control flow, the real ``OneCallMachine`` — is the
production code.

Pre-registration, written before the fix: ``docs/agentic_v2_ownership_and_teardown.md``.
"""

from __future__ import annotations

import functools
import os
import shutil
import signal
import subprocess
from pathlib import Path

import pytest

from core.agentic_v2_contract import TOOL_CONTRACT_VERSION, AgenticV2Profile
from core.agentic_v2_first_boot import (
    WORK_DISK_RESULTS,
    BootAbandoned,
    BootRefused,
    _clean_up_after_a_failure,
    first_boot,
)
from core.agentic_v2_microvm_backend import AgenticV2MicroVMBackend, GuestImage
from core.agentic_v2_microvm_launch import build_launch_plan
from core.agentic_v2_one_call_machine import OneCallMachine
from core.agentic_v2_substrate import AgenticV2SubstrateManifest

STRANGER = 424242
"""A PID this run did not start. Never signalled, in any test here."""


@pytest.fixture
def plan(tmp_path, monkeypatch):
    """A real plan from the real builder, over files that exist."""
    for name in ("firecracker", "vmlinux", "rootfs.ext4", "work.ext4"):
        path = tmp_path / name
        path.write_bytes(b"not really an image, but a readable file")
        path.chmod(0o755)
    monkeypatch.setattr(os, "chown", lambda *a, **k: None)
    return build_launch_plan(
        vm_id="test-own",
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


class _Signals:
    """Stands in for ``os.kill`` and records every call that reached it.

    Signal 0 is a liveness probe and never terminates anything; anything else is
    a real signal. Keeping the two apart in the record is the point — "a signal
    was sent" and "the process is gone" are different observations and the code
    under test is required to report them separately.

    ``dies_after`` is how many probes after the real signal still report the
    process alive. ``None`` means it never reports dead, which is the case the
    finite confirmation deadline exists for.
    """

    def __init__(self, *, starts_alive=True, dies_after=0, kill_raises=None):
        self.sent: list[tuple[int, int]] = []
        self.starts_alive = starts_alive
        self.dies_after = dies_after
        self.kill_raises = kill_raises
        self.was_signalled = False
        self.probes_after_the_signal = 0

    def __call__(self, pid, sig):
        self.sent.append((pid, sig))
        if sig == 0:
            if not self.starts_alive:
                raise ProcessLookupError(3, "No such process")
            if not self.was_signalled:
                return None
            self.probes_after_the_signal += 1
            if self.dies_after is None:
                return None
            if self.probes_after_the_signal > self.dies_after:
                raise ProcessLookupError(3, "No such process")
            return None
        if self.kill_raises is not None:
            raise self.kill_raises
        self.was_signalled = True
        return None

    @property
    def real_signals(self) -> list[tuple[int, int]]:
        return [(pid, sig) for pid, sig in self.sent if sig != 0]

    def anything_reached_kill_for(self, pid: int) -> bool:
        return any(sent_pid == pid for sent_pid, _ in self.sent)


def _jailer_writing(plan, pid=4242):
    def jailer(argv, timeout=300.0):
        Path(plan["host_side"]["pid_file"]).write_text(f"{pid}\n")
        return subprocess.CompletedProcess(argv, 0, "", "")

    return jailer


def _jailer_writing_that_then_fails(plan, pid=4242):
    """Starts a machine this run owns, then fails — so cleanup has work to do."""

    def jailer(argv, timeout=300.0):
        Path(plan["host_side"]["chroot_dir"]).mkdir(parents=True, exist_ok=True)
        Path(plan["host_side"]["pid_file"]).write_text(f"{pid}\n")
        raise subprocess.TimeoutExpired(argv, 120.0)

    return jailer


def _jailer_writing_nothing(argv, timeout=300.0):
    return subprocess.CompletedProcess(argv, 0, "", "")


def _finished(*, exit_status="0"):
    results = {name: None for name in WORK_DISK_RESULTS}
    results["/out/stdout"] = "this ran inside the guest\n"
    results["/out/exit_status"] = exit_status
    return results


def _boot(plan, tmp_path, monkeypatch, *, jailer, signals, reader=None, clock=None):
    """Run the real :func:`first_boot` with only the host's two edges stood in.

    ``_still_running`` is deliberately **not** replaced. It is the function that
    calls ``os.kill(pid, 0)``, and every question here is about which values
    reach that call — a test that stubs it out cannot see the thing it is for.
    """
    clock = clock or _Clock()
    monkeypatch.setattr("core.agentic_v2_first_boot._run", jailer)
    monkeypatch.setattr(os, "kill", signals)
    monkeypatch.setattr(
        "core.agentic_v2_first_boot.files_out_of_work_disk",
        reader or (lambda image, names, **kw: _finished()),
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


def _a_jail_someone_else_is_using(plan) -> Path:
    """Lay down the jail a previous run with this same vm_id left behind."""
    chroot = Path(plan["host_side"]["chroot_dir"])
    chroot.mkdir(parents=True)
    (chroot / "work.ext4").write_bytes(b"another run is writing to this disk")
    Path(plan["host_side"]["pid_file"]).write_text(f"{STRANGER}\n")
    return chroot


# --------------------------------------------------------------------------
# the production call path, assembled the way the product assembles it
# --------------------------------------------------------------------------


def _a_real_machine(tmp_path, monkeypatch) -> tuple[OneCallMachine, Path, Path]:
    """A genuine :class:`OneCallMachine` over readable files in a temp tree.

    Nothing here is a stand-in for code under test. ``os.chown`` is replaced
    because the plan chowns placed images to the account the jailer drops to and
    that needs root, which this box is not; ``chroot_base`` is redirected through
    ``build_plan`` — the parameter that exists for it — so no test writes under
    /srv on a developer's machine.
    """
    host = tmp_path / "host"
    host.mkdir()
    for name in ("firecracker", "vmlinux", "rootfs.ext4"):
        image = host / name
        image.write_bytes(b"not really an image, but a readable file")
        image.chmod(0o755)
    jail_base = tmp_path / "jail"
    monkeypatch.setattr(os, "chown", lambda *a, **k: None)

    machine = OneCallMachine(
        kernel=host / "vmlinux",
        rootfs=host / "rootfs.ext4",
        firecracker_binary=host / "firecracker",
        uid=997,
        gid=997,
        vcpu_count=1,
        cgroup_version=2,
        scratch=tmp_path / "scratch",
        build_plan=functools.partial(build_launch_plan, chroot_base=jail_base),
    )
    return machine, jail_base, host


def _backend_over(tmp_path, machine) -> AgenticV2MicroVMBackend:
    return AgenticV2MicroVMBackend(
        root=tmp_path / "session",
        profile=AgenticV2Profile(
            tool_contract_version=TOOL_CONTRACT_VERSION,
            policy_profile_id="offline-full-v1",
            foundation_only=True,
        ),
        image=GuestImage(
            reference="ghcr.io/hyeonsangjeon/gdpval-sandbox",
            digest="sha256:" + "e" * 64,
            kernel_sha256="a" * 64,
            rootfs_sha256="b" * 64,
        ),
        boot_one_command=machine,
        substrate_manifest=AgenticV2SubstrateManifest.load(
            Path("sandbox/agentic_v2_capabilities.json")
        ),
    )


def _a_jailer_that_starts_then_dies(jail_base: Path, pid: int = 4242):
    """Write a PID file into the jail that was just placed, then fail.

    The machine name is decided by ``OneCallMachine`` at call time, so the jail
    is found rather than predicted. By the time this runs the images are in it,
    which is also what makes the "it was really placed" assertion meaningful.
    The file's name is the binary's own with ``.pid`` appended — the jailer's
    rule, not a convention chosen here.
    """

    def jailer(argv, timeout=300.0):
        _the_jail_just_placed(jail_base, pid)
        raise subprocess.TimeoutExpired(argv, 120.0)

    return jailer


def _a_jailer_that_boots_and_exits(jail_base: Path, pid: int = 4242):
    """The ordinary case: a machine starts, runs, and is gone by the first probe."""

    def jailer(argv, timeout=300.0):
        _the_jail_just_placed(jail_base, pid)
        return subprocess.CompletedProcess(argv, 0, "", "")

    return jailer


def _the_jail_just_placed(jail_base: Path, pid: int) -> Path:
    roots = sorted(jail_base.glob("firecracker/*/root"))
    assert roots, "nothing was placed, so there is no boot to stand in for"
    (roots[-1] / "firecracker.pid").write_text(f"{pid}\n")
    return roots[-1]


# --------------------------------------------------------------------------
# C1-C4 — the controls. If any of these is red, nothing below counts.
# --------------------------------------------------------------------------


def test_c1_a_normal_boot_in_a_fresh_jail_is_unchanged(plan, tmp_path, monkeypatch):
    """The guest exits on its own: no signal, no refusal, the jail comes down."""
    signals = _Signals(starts_alive=False)
    result = _boot(
        plan, tmp_path, monkeypatch, jailer=_jailer_writing(plan), signals=signals
    )

    assert result["outcome"] == "booted"
    assert result["command_exit_status"] == 0
    assert signals.real_signals == []
    assert result["teardown"]["all_gone"] is True
    assert not Path(plan["host_side"]["chroot_dir"]).exists()


def test_c2_an_owned_guest_that_overruns_is_still_stopped(plan, tmp_path, monkeypatch):
    """The deadline still works. Ownership is a gate on it, not a way out of it."""
    signals = _Signals(dies_after=0)
    result = _boot(
        plan, tmp_path, monkeypatch, jailer=_jailer_writing(plan), signals=signals
    )

    assert result["outcome"] == "stopped_by_the_deadline"
    assert result["stopped_by_the_deadline"] is True
    assert signals.real_signals == [(4242, signal.SIGKILL)]
    assert result["stop_signal_sent"] is True
    assert result["guest_confirmed_stopped"] is True


def test_c3_a_guest_that_never_reports_dead_is_not_called_confirmed(
    plan, tmp_path, monkeypatch
):
    """The false-success control.

    A checker that will say ``confirmed_stopped`` for a process it can still see
    would pass every other test in this file while proving nothing. This is the
    case that catches it, and it must end on a finite deadline rather than
    spinning.
    """
    signals = _Signals(dies_after=None)
    result = _boot(
        plan, tmp_path, monkeypatch, jailer=_jailer_writing(plan), signals=signals
    )

    assert result["stop_signal_sent"] is True
    assert result["guest_confirmed_stopped"] is False
    assert result["outcome"] != "stopped_by_the_deadline"
    assert result["stopped_by_the_deadline"] is False


def test_c4_a_usable_pid_does_reach_os_kill(plan, tmp_path, monkeypatch):
    """The reachability control.

    Every "no signal was sent" assertion below is worthless if the probe never
    gets near ``os.kill`` in the first place. A convertible PID must arrive.
    """
    signals = _Signals(dies_after=0)
    _boot(plan, tmp_path, monkeypatch, jailer=_jailer_writing(plan), signals=signals)

    assert signals.anything_reached_kill_for(4242)
    assert (4242, 0) in signals.sent


# --------------------------------------------------------------------------
# D1-D6 — ownership, on both paths
# --------------------------------------------------------------------------


def test_d1_a_pid_file_from_before_this_run_is_never_signalled(
    plan, tmp_path, monkeypatch
):
    """A's F1, the scenario verbatim: a stale PID file and a launcher that
    returns normally, so the *deadline* path is the one that decides.

    That path had no ownership check at all. ``pid_file_was_already_there`` was
    read in ``first_boot`` and then consumed only inside
    ``_clean_up_after_a_failure``, which a clean launch never reaches — so the
    deadline signalled ``(424242, 0)`` five times and then
    ``(424242, SIGKILL)``, and reported ``stopped_by_the_deadline`` about a
    machine it had never started.

    The outcome now is earlier and stronger than "it declines to signal": the
    PID file is *inside* the chroot, so a stale one means a jail that is already
    on disk, and the run refuses before it places anything. The stranger is not
    signalled, which is what F1 was about, and its disk is not touched either.
    """
    Path(plan["host_side"]["chroot_dir"]).mkdir(parents=True)
    Path(plan["host_side"]["pid_file"]).write_text(f"{STRANGER}\n")
    signals = _Signals(dies_after=None)

    with pytest.raises(BootRefused) as refused:
        _boot(
            plan, tmp_path, monkeypatch, jailer=_jailer_writing_nothing, signals=signals
        )

    assert not signals.anything_reached_kill_for(STRANGER)
    assert signals.sent == []
    assert "does not start" in str(refused.value)
    assert Path(plan["host_side"]["pid_file"]).read_text().strip() == str(STRANGER)


def test_d2_a_jail_that_is_already_there_is_refused_before_anything_is_written(
    plan, tmp_path, monkeypatch
):
    """The root of the resume collision, and the most destructive case.

    ``--run-id``'s own help says "Reuse it to resume", ``OneCallMachine.calls``
    restarts at zero, so a resumed run rebuilds the same ``vm_id`` and lands on
    the same chroot. Proceeding would ``copy2`` over a live work disk and then
    ``rmtree`` the jail it belongs to.
    """
    chroot = _a_jail_someone_else_is_using(plan)
    before = (chroot / "work.ext4").read_bytes()
    signals = _Signals()

    with pytest.raises(BootRefused, match="jail"):
        _boot(
            plan, tmp_path, monkeypatch, jailer=_jailer_writing(plan), signals=signals
        )

    assert (chroot / "work.ext4").read_bytes() == before
    assert Path(plan["host_side"]["pid_file"]).read_text().strip() == str(STRANGER)
    assert signals.sent == []


def test_d3_resuming_the_same_run_id_rebuilds_the_same_machine_name():
    """Why D2 is a workflow and not a corner case.

    No files and no boot — this is the arithmetic that makes two runs collide.
    """
    first = OneCallMachine(
        kernel="k",
        rootfs="r",
        firecracker_binary="f",
        uid=997,
        gid=997,
        vcpu_count=1,
        cgroup_version=2,
        scratch="/tmp/does-not-need-to-exist",
        session="agentic-v2-trial-30-1757800000",
    )
    resumed = OneCallMachine(
        kernel="k",
        rootfs="r",
        firecracker_binary="f",
        uid=997,
        gid=997,
        vcpu_count=1,
        cgroup_version=2,
        scratch="/tmp/does-not-need-to-exist",
        session="agentic-v2-trial-30-1757800000",
    )

    first.calls = 0
    assert resumed.calls == 0
    assert resumed.name_the_machine() == first.name_the_machine()


def test_d4_a_pid_file_replaced_after_it_was_watched_is_not_signalled(
    plan, tmp_path, monkeypatch
):
    """Appearing during this run is necessary but not sufficient.

    The file this run watched appear can be replaced before the deadline fires.
    What is signalled has to be what was read, re-checked at the moment of the
    signal rather than assumed to have stayed put.
    """
    pid_file = Path(plan["host_side"]["pid_file"])

    class _ReplacingClock(_Clock):
        def sleep(self, seconds):
            super().sleep(seconds)
            if self.t > 1.0 and pid_file.exists():
                pid_file.write_text(f"{STRANGER}\n")

    signals = _Signals(dies_after=None)
    result = _boot(
        plan,
        tmp_path,
        monkeypatch,
        jailer=_jailer_writing(plan),
        signals=signals,
        clock=_ReplacingClock(),
    )

    assert not signals.anything_reached_kill_for(STRANGER)
    assert result["stop_signal_sent"] is False
    assert result["pid_file"]["owned_by_this_run"] is False


def test_d5_cleanup_leaves_a_jail_this_run_did_not_create_alone(
    plan, tmp_path, monkeypatch
):
    """The same refusal on the exception path, for the chroot rather than the PID.

    ``first_boot`` now turns this case away before it places anything, so the
    guard below it is never reached through a boot. It is called directly here
    on purpose: the two paths are supposed to apply *one* ownership rule, and a
    guard that is only unreachable is not a guard that holds. All three
    destructive operations are checked — the stranger is not signalled, its disk
    is not copied out, and its jail is still there afterwards.
    """
    chroot = _a_jail_someone_else_is_using(plan)
    before = (chroot / "work.ext4").read_bytes()
    signals = _Signals(dies_after=None)
    monkeypatch.setattr(os, "kill", signals)
    salvage = {"returned_copy": None, "results_read": False, "copied_while_running": False}

    teardown = _clean_up_after_a_failure(
        host_side=plan["host_side"],
        pid_file=Path(plan["host_side"]["pid_file"]),
        pid_file_was_already_there=True,
        work_disk=tmp_path / "work.ext4",
        salvage=salvage,
        chroot_was_already_there=True,
    )

    assert signals.sent == []
    assert (chroot / "work.ext4").read_bytes() == before
    assert chroot.exists()
    assert teardown["process"]["signalled"] is False
    assert "another run's" in teardown["process"]["left_alone_because"]
    assert salvage["returned_copy"] is None
    assert teardown["removed"] == {}
    assert teardown["destroy_refused_because"]
    assert not Path(str(tmp_path / "work.ext4") + ".returned").exists()


def test_d6_ownership_is_recorded_as_evidence_both_when_it_holds_and_when_it_does_not(
    plan, tmp_path, monkeypatch
):
    """Ownership is evidence, not a boolean nobody can audit.

    The falsifier written into the pre-registration was "ownership was claimed
    and the only ground was that no PID file was there". So the record has to
    carry the individual grounds *and* what stays unprovable — on both answers.
    A run that is granted ownership still cannot rule out PID reuse: between the
    last probe and the signal the kernel may have handed that number to someone
    else, and nothing available here closes that window.
    """
    refused = _boot(
        plan,
        tmp_path,
        monkeypatch,
        jailer=_jailer_writing_nothing,
        signals=_Signals(dies_after=None),
    )

    evidence = refused["pid_file"]
    assert evidence["owned_by_this_run"] is False
    assert [g["held"] for g in evidence["ownership_grounds"]] == [
        True,
        True,
        False,
        False,
    ]
    assert "reuse" in evidence["cannot_rule_out"].lower()
    assert evidence["left_alone_because"]

    owned = _boot(
        plan, tmp_path, monkeypatch, jailer=_jailer_writing(plan), signals=_Signals()
    )

    granted = owned["pid_file"]
    assert granted["owned_by_this_run"] is True
    assert len(granted["ownership_grounds"]) == 4
    assert all(g["held"] for g in granted["ownership_grounds"])
    assert granted["left_alone_because"] is None
    assert "reuse" in granted["cannot_rule_out"].lower()


# --------------------------------------------------------------------------
# D7-D10 — what may be handed to os.kill, on both paths
# --------------------------------------------------------------------------

NOT_A_PID_THIS_MAY_SIGNAL = [
    pytest.param("0", id="zero-is-this-whole-process-group"),
    pytest.param("-1", id="minus-one-is-everything-this-user-may-signal"),
    pytest.param("-12345", id="a-negative-number-is-a-process-group"),
    pytest.param("2147483648", id="one-past-what-this-platform-can-convert"),
    pytest.param("99999999999999999999", id="twenty-digits"),
    pytest.param("not-a-pid", id="not-a-number"),
    pytest.param("", id="empty"),
    pytest.param("  ", id="whitespace"),
]


@pytest.mark.parametrize("written", NOT_A_PID_THIS_MAY_SIGNAL)
def test_d7_d10_the_deadline_path_never_hands_a_bad_value_to_os_kill(
    plan, tmp_path, monkeypatch, written
):
    """``0`` is the one that matters most.

    ``if pid:`` rejected it as a reason to stop reading the file and then
    ``if pid is None:`` let it straight through, and ``kill(0, SIGKILL)`` is
    every process in this process group — the launcher's own included.
    """
    signals = _Signals(dies_after=None)

    def jailer(argv, timeout=300.0):
        Path(plan["host_side"]["pid_file"]).write_text(written)
        return subprocess.CompletedProcess(argv, 0, "", "")

    result = _boot(plan, tmp_path, monkeypatch, jailer=jailer, signals=signals)

    assert signals.sent == []
    assert result["stop_signal_sent"] is False
    assert result["pid_file"]["owned_by_this_run"] is False


@pytest.mark.parametrize("written", NOT_A_PID_THIS_MAY_SIGNAL)
def test_d7_d10_the_cleanup_path_never_hands_a_bad_value_to_os_kill(
    plan, tmp_path, monkeypatch, written
):
    """The same list, through the exception path, which has its own reader."""
    signals = _Signals(dies_after=None)

    def jailer(argv, timeout=300.0):
        Path(plan["host_side"]["pid_file"]).write_text(written)
        raise subprocess.TimeoutExpired(argv, 120.0)

    with pytest.raises(BootAbandoned) as raised:
        _boot(plan, tmp_path, monkeypatch, jailer=jailer, signals=signals)

    assert signals.sent == []
    process = raised.value.teardown["process"]
    assert process["signalled"] is False
    assert process["left_alone_because"]


# --------------------------------------------------------------------------
# D11-D13 — a cleanup failure does not replace the failure that caused it
# --------------------------------------------------------------------------


def test_d11_a_pid_too_large_to_convert_never_reaches_the_call_that_raised(
    plan, tmp_path, monkeypatch
):
    """A's F3, at the line it actually came from.

    The escape was ``_still_running(int(process["pid"]))`` — sitting between the
    ``except (OSError, ValueError)`` around the parse and the ``except OSError``
    around the signal, inside neither. ``2147483648`` converts to a Python int
    happily and then fails converting to a C long, and ``OverflowError`` is not
    an ``OSError``, so it went straight out through the ``except BaseException``
    that was mid-cleanup. ``BootAbandoned`` was therefore never constructed, and
    the original error, the salvaged disk's path and the teardown record went
    with it.

    The value is turned away before anything asks the kernel about it.
    """
    signals = _Signals(dies_after=None)

    def jailer(argv, timeout=300.0):
        Path(plan["host_side"]["chroot_dir"]).mkdir(parents=True, exist_ok=True)
        Path(plan["host_side"]["pid_file"]).write_text("2147483648\n")
        raise subprocess.TimeoutExpired(argv, 120.0)

    with pytest.raises(BootAbandoned) as raised:
        _boot(plan, tmp_path, monkeypatch, jailer=jailer, signals=signals)

    abandoned = raised.value
    assert signals.sent == []
    assert isinstance(abandoned.original, subprocess.TimeoutExpired)
    assert abandoned.teardown["salvaged"]["returned_copy"] is not None
    assert Path(abandoned.teardown["salvaged"]["returned_copy"]).exists()
    assert abandoned.teardown["process"]["signalled"] is False
    assert "cannot be handed to the operating system" in (
        abandoned.teardown["process"]["left_alone_because"]
    )


def test_d11_and_any_other_exception_from_cleanup_is_collected_not_raised(
    plan, tmp_path, monkeypatch
):
    """The general form, which is the part that has to keep holding.

    Turning away the one value A found is not the same promise as the one the
    docstring makes. Cleanup runs while another exception is already on its way
    out, so *anything* it raises replaces the reason the run failed with the
    reason the cleanup failed — and does it before ``BootAbandoned`` exists. So
    the failure is forced from inside the stop step rather than conjured by a
    PID value, and the same four things have to survive.
    """
    signals = _Signals(kill_raises=OverflowError("Python int too large"))

    with pytest.raises(BootAbandoned) as raised:
        _boot(
            plan,
            tmp_path,
            monkeypatch,
            jailer=_jailer_writing_that_then_fails(plan),
            signals=signals,
        )

    abandoned = raised.value
    assert isinstance(abandoned.original, subprocess.TimeoutExpired)
    assert abandoned.teardown["salvaged"]["returned_copy"] is not None
    assert abandoned.teardown["clean"] is False
    assert any(
        "OverflowError" in failure["error"]
        for failure in abandoned.teardown["failures"]
    )
    # And the jail still came down, because the failure was collected rather
    # than allowed to skip the rest of the cleanup.
    assert abandoned.teardown["all_gone"] is True


def test_d12_the_backend_record_still_carries_both_failures(tmp_path, monkeypatch):
    """The same case one layer up, where the loss was actually visible.

    ``AgenticV2MicroVMBackend.exec_run`` copies ``original_error`` and
    ``teardown`` off the exception only when both are there. An ``OverflowError``
    arriving in place of ``BootAbandoned`` is still an ``Exception``, so it was
    caught and reported — with both keys simply absent and nothing saying they
    had been lost. Read through the real backend rather than off the exception,
    because "the backend would have copied it" is the assumption under test.
    """
    machine, jail_base, host = _a_real_machine(tmp_path, monkeypatch)
    signals = _Signals(kill_raises=OverflowError("Python int too large"))
    monkeypatch.setattr(os, "kill", signals)
    monkeypatch.setattr(
        "core.agentic_v2_first_boot._run", _a_jailer_that_starts_then_dies(jail_base)
    )

    backend = _backend_over(tmp_path, machine)
    try:
        result = backend.exec_run({"argv": ["true"], "cwd": ".", "timeout_seconds": 60})
        assert result == {"ok": False, "error_type": "compute_backend_error"}

        record = backend.boots[0]
        assert "TimeoutExpired" in record["original_error"]
        assert "BootAbandoned" in record["launcher_error"]
        teardown = record["teardown"]
        assert teardown["after_a_failure"] is True
        assert teardown["clean"] is False
        assert any("OverflowError" in f["error"] for f in teardown["failures"])
        assert teardown["salvaged"]["returned_copy"] is not None
    finally:
        backend.close()


def test_d13_a_keyboard_interrupt_is_still_a_keyboard_interrupt(
    plan, tmp_path, monkeypatch
):
    """Cleanup runs, and the stop is not turned into something else.

    Wrapping it would make Ctrl-C arrive as a ``RuntimeError`` nobody asked for;
    skipping cleanup would leak the jail. Both halves are pinned here because
    the guards added for D11 are exactly the kind of change that quietly
    swallows a ``BaseException``.
    """

    def jailer(argv, timeout=300.0):
        Path(plan["host_side"]["chroot_dir"]).mkdir(parents=True, exist_ok=True)
        Path(plan["host_side"]["pid_file"]).write_text("4242\n")
        raise KeyboardInterrupt()

    with pytest.raises(KeyboardInterrupt):
        _boot(
            plan,
            tmp_path,
            monkeypatch,
            jailer=jailer,
            signals=_Signals(dies_after=0),
        )

    assert not Path(plan["host_side"]["chroot_dir"]).exists()


# --------------------------------------------------------------------------
# D14-D16 — stop, confirm, salvage, remove; in that order
# --------------------------------------------------------------------------


def test_d14_the_machine_is_stopped_before_its_disk_is_copied(
    plan, tmp_path, monkeypatch
):
    """A's F4.

    The copy used to be taken first, before anything asked whether the guest was
    still running. On this box that is a file copy; on a host with ``/dev/kvm``
    it is a copy of a filesystem being written to, followed by an ``rmtree``
    racing a live Firecracker.
    """
    order: list[str] = []
    signals = _Signals(dies_after=0)
    real_kill = signals.__call__

    def watching_kill(pid, sig):
        if sig != 0:
            order.append("signal")
        return real_kill(pid, sig)

    real_copy = __import__("shutil").copy2

    def watching_copy(src, dst, *a, **kw):
        if str(dst).endswith(".returned"):
            order.append("copy")
        return real_copy(src, dst, *a, **kw)

    monkeypatch.setattr("core.agentic_v2_first_boot.shutil.copy2", watching_copy)

    with pytest.raises(BootAbandoned):
        _boot(
            plan,
            tmp_path,
            monkeypatch,
            jailer=_jailer_writing_that_then_fails(plan),
            signals=watching_kill,
        )

    assert order == ["signal", "copy"]


def test_d15_a_disk_copied_out_of_a_running_guest_is_not_called_clean(
    plan, tmp_path, monkeypatch
):
    """Never publish a copy taken while the guest was writing as an intact one.

    The copy is still taken — it is the only place the guest's writes exist — but
    it is labelled, it counts as a failure, and ``clean`` goes false. Ending on a
    finite deadline rather than waiting for a confirmation that is not coming is
    the other half of this.
    """
    with pytest.raises(BootAbandoned) as raised:
        _boot(
            plan,
            tmp_path,
            monkeypatch,
            jailer=_jailer_writing_that_then_fails(plan),
            signals=_Signals(dies_after=None),
        )

    teardown = raised.value.teardown
    assert teardown["process"]["signalled"] is True
    assert teardown["process"]["confirmed_stopped"] is False
    assert teardown["salvaged"]["copied_while_running"] is True
    assert teardown["clean"] is False


def test_d16_a_guest_that_stops_a_few_probes_later_is_confirmed_stopped(
    plan, tmp_path, monkeypatch
):
    """Sent and confirmed are two fields, and here both are true.

    SIGKILL is not instantaneous from the host's side; the process stays visible
    until the kernel reaps it. Reporting the signal as the stop would be a guess
    dressed as an observation.
    """
    with pytest.raises(BootAbandoned) as raised:
        _boot(
            plan,
            tmp_path,
            monkeypatch,
            jailer=_jailer_writing_that_then_fails(plan),
            signals=_Signals(dies_after=3),
        )

    process = raised.value.teardown["process"]
    assert process["signalled"] is True
    assert process["confirmed_stopped"] is True
    assert raised.value.teardown["salvaged"]["copied_while_running"] is False


# --------------------------------------------------------------------------
# P1 — the same evidence, through the call the product actually makes
# --------------------------------------------------------------------------


def test_p1_the_backend_record_carries_the_ownership_and_shutdown_evidence(
    tmp_path, monkeypatch
):
    """Everything above is worth nothing if the product path does not reach it.

    So this one assembles it the way the product does — a real
    ``AgenticV2MicroVMBackend`` over a real ``OneCallMachine``, ``exec_run``
    called with real arguments, the real plan builder, the real
    ``place_the_images`` and the real ``first_boot`` — and stands in for exactly
    two things: the jailer, because this box has no ``/dev/kvm``, and ``os.kill``,
    because the values reaching it are the whole question.

    Replacing ``boot_one_command`` instead would be the easy version of this test
    and would assert nothing: ``first_boot`` would never run. That trap was
    already walked into once in this module's history, so the seam is placed
    below the launcher on purpose.

    The guest here exits on its own, which is the ordinary case, and the record
    has to say so precisely: owned, on four grounds, with no signal sent and
    therefore nothing to confirm — and with the one thing that stays unprovable
    still written down rather than rounded off to "owned".
    """
    machine, jail_base, host = _a_real_machine(tmp_path, monkeypatch)
    signals = _Signals(starts_alive=False)
    monkeypatch.setattr(os, "kill", signals)
    monkeypatch.setattr(
        "core.agentic_v2_first_boot._run", _a_jailer_that_boots_and_exits(jail_base)
    )
    monkeypatch.setattr(
        "core.agentic_v2_first_boot.files_out_of_work_disk",
        lambda image, names, **kw: _finished(),
    )

    backend = _backend_over(tmp_path, machine)
    try:
        result = backend.exec_run({"argv": ["true"], "cwd": ".", "timeout_seconds": 60})
        assert result["ok"] is True

        machine_record = backend.boots[0]["machine"]
        assert machine_record["outcome"] == "booted"
        assert machine_record["owned_by_this_run"] is True
        assert [g["held"] for g in machine_record["ownership_grounds"]] == [
            True,
            True,
            True,
            True,
        ]
        assert machine_record["left_alone_because"] is None
        assert "reuse" in machine_record["cannot_rule_out"].lower()

        # Nothing was signalled, so there is nothing to have confirmed. False and
        # None are different answers and the record keeps them apart.
        assert machine_record["stop_signal_sent"] is False
        assert machine_record["guest_confirmed_stopped"] is None
        assert signals.real_signals == []

        assert machine_record["teardown"]["all_gone"] is True
        assert sorted(jail_base.glob("firecracker/*/root")) == []
    finally:
        backend.close()
