"""Taking the jail's name atomically, before anything is placed in it.

The suite next door pins *absence of a PID file is not proof of ownership*. This
one pins the step underneath it: **absence of a directory a moment ago is not
proof of ownership now.** The check that read the directory and the call that
created it were two operations with a gap, and two runs of the same ``vm_id``
could both read *absent* inside that gap. Measured on this box before the
change, against the same production code these tests call: 19 of 20 unforced
concurrent pairs both got through, and both members of each pair then launched,
placed images into the one jail, copied the one work disk out, and removed the
one directory.

One ``mkdir(2)`` closes it. ``mkdir(parents=True, exist_ok=False)`` puts the
final component through a bare ``os.mkdir``, so the kernel decides who gets the
name, once, for everybody. The winner then writes a nonce into the jail and
every later step re-reads it instead of trusting a boolean carried down from the
top of the run — because a boolean answers *was it ours then* and the steps that
signal, copy and remove need *is it ours now*.

Two things these tests are careful **not** to claim:

* Nothing here says a jail is free. A directory with no ownership record, an
  unreadable one, and a malformed one are three different readings and all three
  are refusals. The case this code knows least about is the one that used to
  read as "go ahead".
* Nothing here addresses PID reuse. The claim writes down a PID, a boot id and a
  process start time, and **no code path reads any of them back**. A stale jail
  is never reclaimed by reasoning about whether its owner looks dead. See
  ``CLAIM_DOES_NOT_ESTABLISH``, which carries ``CANNOT_RULE_OUT`` out with the
  record rather than restating it.

Nothing here boots anything. ``os.kill`` and the jailer are stood in for; the
plan builder, ``place_the_images``, ``first_boot``'s control flow and the
cleanup path are the production code.
"""

from __future__ import annotations

import inspect
import json
import multiprocessing as mp
import os
import subprocess
from pathlib import Path

import pytest

from core.agentic_v2_first_boot import (
    CANNOT_RULE_OUT,
    CLAIM_FILE_NAME,
    COPY_UNVERIFIED,
    WORK_DISK_RESULTS,
    BootAbandoned,
    BootRefused,
    _clean_up_after_a_failure,
    claim_the_jail,
    first_boot,
    place_the_images,
)
from core.agentic_v2_microvm_launch import build_launch_plan

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
        vm_id="test-claim",
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
    """Stands in for ``os.kill``; signal 0 is a probe, anything else is real."""

    def __init__(self, *, starts_alive=True):
        self.sent: list[tuple[int, int]] = []
        self.starts_alive = starts_alive

    def __call__(self, pid, sig):
        self.sent.append((pid, sig))
        if sig == 0 and not self.starts_alive:
            raise ProcessLookupError(3, "No such process")
        return None

    @property
    def real_signals(self) -> list[tuple[int, int]]:
        return [(pid, sig) for pid, sig in self.sent if sig != 0]


def _finished():
    results = {name: None for name in WORK_DISK_RESULTS}
    results["/out/stdout"] = "this ran inside the guest\n"
    results["/out/exit_status"] = "0"
    return results


def _jailer_writing(plan, pid=4242):
    def jailer(argv, timeout=300.0):
        Path(plan["host_side"]["pid_file"]).write_text(f"{pid}\n")
        return subprocess.CompletedProcess(argv, 0, "", "")

    return jailer


def _a_jailer_that_starts_and_then_fails(plan, pid=4242):
    """A machine this run owns, started, and then a launch that failed."""

    def jailer(argv, timeout=300.0):
        Path(plan["host_side"]["pid_file"]).write_text(f"{pid}\n")
        raise subprocess.TimeoutExpired(argv, 120.0)

    return jailer


def _boot(plan, tmp_path, monkeypatch, *, jailer, signals):
    """Run the real :func:`first_boot` with only the host's two edges stood in."""
    clock = _Clock()
    monkeypatch.setattr("core.agentic_v2_first_boot._run", jailer)
    monkeypatch.setattr(os, "kill", signals)
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


def _a_jail_that_was_already_here(plan, *, ownership: str) -> tuple[Path, bytes]:
    """Lay down a jail this run did not create, and say what evidence it carries.

    The four readings are the four ``_read_the_claim`` keeps apart. They are
    written here as data rather than as four near-identical tests, because the
    thing being pinned is that they reach the *same* answer by *different*
    routes — and a reading that quietly joined the "go ahead" branch would be
    invisible in a test that only ever laid down one of them.
    """
    chroot = Path(plan["host_side"]["chroot_dir"])
    chroot.mkdir(parents=True)
    (chroot / "work.ext4").write_bytes(b"another run is writing to this disk")
    Path(plan["host_side"]["pid_file"]).write_text(f"{STRANGER}\n")
    record = chroot / CLAIM_FILE_NAME
    if ownership == "none":
        pass
    elif ownership == "malformed":
        record.write_text("{not json at all")
    elif ownership == "no_nonce":
        record.write_text(json.dumps({"vm_id": "somebody-else", "claimed_by": {}}))
    elif ownership == "unreadable":
        record.mkdir()
    elif ownership == "someone_elses":
        record.write_text(json.dumps({"nonce": "0" * 32, "vm_id": "somebody-else"}))
    else:  # pragma: no cover - a typo in a test is not a scenario
        raise AssertionError(f"no such ownership case: {ownership}")
    return chroot, _what_is_in_it(chroot)


def _what_is_in_it(chroot: Path) -> bytes:
    """Everything under the jail, as one comparable value."""
    entries = []
    for path in sorted(chroot.rglob("*")):
        if path.is_dir():
            entries.append(f"d {path.relative_to(chroot)}".encode())
        else:
            entries.append(
                f"f {path.relative_to(chroot)} ".encode() + path.read_bytes()
            )
    return b"\n".join(entries)


OWNERSHIP_READINGS = ["none", "malformed", "no_nonce", "unreadable", "someone_elses"]


# --------------------------------------------------------------------------
# E1-E5 — a jail that was already there, whatever it says about itself
# --------------------------------------------------------------------------


@pytest.mark.parametrize("ownership", OWNERSHIP_READINGS)
def test_e1_a_jail_that_is_already_there_is_refused_whatever_evidence_it_carries(
    plan, tmp_path, monkeypatch, ownership
):
    """Five ways a jail can answer "whose are you", one outcome.

    The fifth is the only one that names another owner. The other four are ways
    of saying *nothing legible*, and the whole point is that they do not become
    permission. Missing evidence is the least-known state, not the freest one.
    """
    chroot, before = _a_jail_that_was_already_here(plan, ownership=ownership)
    signals = _Signals()

    with pytest.raises(BootRefused) as refusal:
        _boot(plan, tmp_path, monkeypatch, jailer=_jailer_writing(plan), signals=signals)

    assert "creates nothing and starts nothing" in str(refusal.value)
    assert signals.sent == []
    assert _what_is_in_it(chroot) == before


@pytest.mark.parametrize("ownership", OWNERSHIP_READINGS)
def test_e2_the_refusal_removes_nothing_it_did_not_create(
    plan, tmp_path, monkeypatch, ownership
):
    """Clearing the obstacle is the failure this was meant to stop.

    Deleting a jail whose owner cannot be identified is the same act as the one
    the whole file is against, done in the name of tidying up. The stranger's
    disk, the stranger's PID file and the directory itself are all still there
    afterwards — byte for byte.
    """
    chroot, before = _a_jail_that_was_already_here(plan, ownership=ownership)

    with pytest.raises(BootRefused):
        _boot(plan, tmp_path, monkeypatch, jailer=_jailer_writing(plan), signals=_Signals())

    assert chroot.exists()
    assert (chroot / "work.ext4").read_bytes() == b"another run is writing to this disk"
    assert Path(plan["host_side"]["pid_file"]).read_text().strip() == str(STRANGER)
    assert _what_is_in_it(chroot) == before
    assert not Path(str(tmp_path / "work.ext4") + ".returned").exists()


def test_e3_the_refusal_quotes_what_the_other_claim_says_without_acting_on_it(
    plan, tmp_path, monkeypatch
):
    """A readable claim is quoted, because a person holding a stuck jail needs it.

    Quoting is as far as it goes. Nothing branches on the content: an owner that
    looks long dead gets the same refusal as one that looks alive, because this
    module cannot tell those apart and a guess in the permitting direction is
    how a run ends up killing a live guest.
    """
    _a_jail_that_was_already_here(plan, ownership="someone_elses")

    with pytest.raises(BootRefused) as refusal:
        _boot(plan, tmp_path, monkeypatch, jailer=_jailer_writing(plan), signals=_Signals())

    assert "somebody-else" in str(refusal.value)
    assert "00000000" in str(refusal.value)


@pytest.mark.parametrize("ownership", OWNERSHIP_READINGS)
def test_e4_cleanup_over_a_jail_that_is_not_this_runs_touches_none_of_it(
    plan, tmp_path, monkeypatch, ownership
):
    """The same rule, one layer down, reached directly.

    ``first_boot`` now turns these away before cleanup can ever see them, so
    this calls the cleanup path itself. Two paths applying one rule is the
    design; a guard that holds only because nothing reaches it is not a guard.
    """
    chroot, before = _a_jail_that_was_already_here(plan, ownership=ownership)
    signals = _Signals()
    monkeypatch.setattr(os, "kill", signals)
    salvage = {"returned_copy": None, "results_read": False, "copied_while_running": False}

    teardown = _clean_up_after_a_failure(
        host_side=plan["host_side"],
        pid_file=Path(plan["host_side"]["pid_file"]),
        claim={"nonce": "a-nonce-this-jail-has-never-carried", "vm_id": plan["vm_id"]},
        # False so that ownership is the only thing refusing. See the same
        # choice, and the same reason, in D5.
        launch_was_attempted=False,
        launch_spawned_nothing=False,
        work_disk=tmp_path / "work.ext4",
        salvage=salvage,
    )

    assert teardown["process"]["jail_held_by_this_run"] is False
    assert teardown["process"]["signalled"] is False
    assert "another run's" in teardown["process"]["left_alone_because"]
    assert teardown["process"]["cannot_rule_out"] == CANNOT_RULE_OUT
    assert salvage["returned_copy"] is None
    assert teardown["removed"] == {}
    assert teardown["destroy_refused_because"]
    assert signals.sent == []
    assert _what_is_in_it(chroot) == before


def test_e5_a_pid_file_already_at_the_path_hands_the_claimed_name_back(
    plan, tmp_path, monkeypatch
):
    """The one path that removes a jail it just made, and what bounds it.

    Under today's layout the PID file lives *inside* the chroot, so a jail this
    run just created cannot contain one and this branch is unreachable through a
    boot. It is reached directly here because the guard is about the file this
    run would signal, not about where the builder currently puts it — and
    because the handback is the only removal in the module that runs before
    anything has been placed. It is ``rmdir``, so if anything at all got into
    that directory the kernel refuses and it is left alone; and it re-reads the
    nonce first, so a name that stopped being this run's is not removed either.

    The refused case is checked for one more thing. The record has to be removed
    before the directory can be, so a handback that fails at the ``rmdir`` would
    otherwise leave a jail standing with no ownership record at all — the one
    state nothing downstream can say anything useful about. It is put back.
    """
    chroot = Path(plan["host_side"]["chroot_dir"])
    claim = claim_the_jail(
        chroot, vm_id=str(plan["vm_id"]), plan_sha256=str(plan["plan_sha256"])
    )
    assert chroot.exists()

    from core.agentic_v2_first_boot import _give_back_an_unused_claim

    assert "handed back empty" in _give_back_an_unused_claim(chroot, claim)
    assert not chroot.exists()

    # And the two ways it declines. Something got in:
    claim = claim_the_jail(
        chroot, vm_id=str(plan["vm_id"]), plan_sha256=str(plan["plan_sha256"])
    )
    (chroot / "somebody-put-this-here").write_bytes(b"work nobody has read yet")
    declined = _give_back_an_unused_claim(chroot, claim)
    assert "could not be handed back" in declined
    assert "back where it was" in declined
    assert (chroot / "somebody-put-this-here").exists()
    assert json.loads((chroot / CLAIM_FILE_NAME).read_text())["nonce"] == claim["nonce"]

    # The name stopped being this run's:
    (chroot / CLAIM_FILE_NAME).chmod(0o644)
    (chroot / CLAIM_FILE_NAME).write_text(json.dumps({"nonce": "1" * 32}))
    assert "left as it is" in _give_back_an_unused_claim(chroot, claim)
    assert chroot.exists()


# --------------------------------------------------------------------------
# E6-E8 — the run that wins: what it writes, and what still has to hold later
# --------------------------------------------------------------------------


def test_e6_the_winner_writes_evidence_before_a_single_image_is_placed(
    plan, tmp_path, monkeypatch
):
    """Ordering is the claim here, not the content.

    Evidence written after placement would leave a window in which the jail
    holds this run's kernel and work disk and says nothing about whose they are
    — and that window is exactly where a concurrent run used to land. So the
    record has to be on disk before ``place_the_images`` is allowed to run, and
    ``place_the_images`` refuses outright without it.
    """
    chroot = Path(plan["host_side"]["chroot_dir"])
    claim = claim_the_jail(
        chroot, vm_id=str(plan["vm_id"]), plan_sha256=str(plan["plan_sha256"])
    )

    on_disk = json.loads((chroot / CLAIM_FILE_NAME).read_text())
    assert on_disk["nonce"] == claim["nonce"]
    assert on_disk["vm_id"] == plan["vm_id"]
    assert on_disk["plan_sha256"] == plan["plan_sha256"]
    assert CANNOT_RULE_OUT in on_disk["does_not_establish"]
    assert list(chroot.iterdir()) == [chroot / CLAIM_FILE_NAME]

    # The PID, boot id and start time are written down and never read back.
    assert on_disk["claimed_by"]["pid"] == os.getpid()

    monkeypatch.setattr(os, "chown", lambda *a, **k: None)
    placement = place_the_images(
        plan,
        claim=claim,
        kernel=tmp_path / "vmlinux",
        rootfs=tmp_path / "rootfs.ext4",
        work_disk=tmp_path / "work.ext4",
        uid=997,
        gid=997,
    )
    assert Path(placement["chroot_dir"]) == chroot
    assert (chroot / CLAIM_FILE_NAME).exists()


def test_e7_placement_refuses_a_jail_whose_record_changed_under_it(
    plan, tmp_path, monkeypatch
):
    """Holding the claim is re-read at the step, not remembered from the top.

    This is the difference between the old boolean and the new record stated as
    a test: the run *did* win the name, legitimately, and is still refused,
    because between winning it and using it the jail stopped carrying this run's
    nonce. A flag set at the top of the run cannot express that.
    """
    chroot = Path(plan["host_side"]["chroot_dir"])
    claim = claim_the_jail(
        chroot, vm_id=str(plan["vm_id"]), plan_sha256=str(plan["plan_sha256"])
    )
    (chroot / CLAIM_FILE_NAME).chmod(0o644)
    (chroot / CLAIM_FILE_NAME).write_text(json.dumps({"nonce": "2" * 32}))

    with pytest.raises(BootRefused) as refusal:
        place_the_images(
            plan,
            claim=claim,
            kernel=tmp_path / "vmlinux",
            rootfs=tmp_path / "rootfs.ext4",
            work_disk=tmp_path / "work.ext4",
            uid=997,
            gid=997,
        )

    assert "an ownership record this run did not write" in str(refusal.value)
    assert not (chroot / "vmlinux").exists()
    assert not (chroot / "work.ext4").exists()


@pytest.mark.parametrize(
    "came_back",
    [
        pytest.param(None, id="the record was gone when it was read back"),
        pytest.param("different", id="the record held a nonce this run did not write"),
    ],
)
def test_e8_a_claim_that_cannot_be_read_back_is_not_a_claim(
    plan, tmp_path, monkeypatch, came_back
):
    """Winning the name is not enough; the evidence has to be *there*.

    Everything downstream — placing, signalling, copying, removing — decides by
    re-reading this record. If what is on disk is not what was just written,
    every one of those comparisons is against a value that was never there, and
    the first moment anyone finds out is the moment the jail is coming down. So
    it is checked once, immediately, while nothing has been placed yet.

    Nothing on this box produces that state on its own, which is why the read is
    stood in for here rather than provoked: a branch that only a lying
    filesystem can reach is still a branch, and one no test exercises is one
    nobody notices being deleted.

    The directory is **left standing**. Removing it would mean acting on an
    ownership claim in the same breath as reporting that the claim did not hold.
    """
    chroot = Path(plan["host_side"]["chroot_dir"])
    reading = (
        (None, "It carries no ownership record at all.")
        if came_back is None
        else ({"nonce": "3" * 32}, "It is claimed by somebody else.")
    )
    monkeypatch.setattr(
        "core.agentic_v2_first_boot._read_the_claim", lambda _chroot: reading
    )

    with pytest.raises(BootRefused) as refusal:
        claim_the_jail(
            chroot, vm_id=str(plan["vm_id"]), plan_sha256=str(plan["plan_sha256"])
        )

    assert "could not read its own" in str(refusal.value)
    assert "nothing is placed and nothing is started" in str(refusal.value)
    assert chroot.exists()
    assert (chroot / CLAIM_FILE_NAME).exists()
    assert not (chroot / "vmlinux").exists()


def test_e8b_the_boot_record_carries_the_claim_it_held(plan, tmp_path, monkeypatch):
    """What a person reading the record afterwards can check it against."""
    result = _boot(
        plan,
        tmp_path,
        monkeypatch,
        jailer=_jailer_writing(plan),
        signals=_Signals(starts_alive=False),
    )

    assert result["jail_claim"]["vm_id"] == plan["vm_id"]
    assert result["jail_claim"]["plan_sha256"] == plan["plan_sha256"]
    assert isinstance(result["jail_claim"]["nonce"], str)
    assert CANNOT_RULE_OUT in result["jail_claim"]["does_not_establish"]

    first = [
        ground
        for ground in result["pid_file"]["ownership_grounds"]
        if "ownership record" in ground["ground"]
    ]
    assert first and first[0]["held"] is True


# --------------------------------------------------------------------------
# E9-E10 — the two cases a stricter gate is most likely to break
# --------------------------------------------------------------------------


def test_e9_a_launch_that_fails_still_cleans_up_its_own_jail(
    plan, tmp_path, monkeypatch
):
    """The run owns this jail, so cleanup is obliged to act, not to refuse.

    A gate that made every teardown refuse would pass every test above and leak
    a jail on every failed launch. This is the negative control for all of them:
    the machine is stopped, the disk comes out, the directory goes.
    """
    signals = _Signals(starts_alive=False)
    chroot = Path(plan["host_side"]["chroot_dir"])

    with pytest.raises(BootAbandoned) as abandoned:
        _boot(
            plan,
            tmp_path,
            monkeypatch,
            jailer=_a_jailer_that_starts_and_then_fails(plan),
            signals=signals,
        )

    teardown = abandoned.value.teardown
    assert teardown["process"]["jail_held_by_this_run"] is True
    assert teardown["process"]["pid"] == 4242
    assert teardown["destroy_refused_because"] is None
    assert teardown["clean"] is True
    assert not chroot.exists()
    assert Path(str(tmp_path / "work.ext4") + ".returned").exists()


def test_e10_the_same_vm_id_boots_again_after_its_jail_came_down(
    plan, tmp_path, monkeypatch
):
    """Resuming a run id is the ordinary route to a repeated ``vm_id``.

    ``--run-id``'s own help says "Reuse it to resume", and the per-call counter
    restarts at zero on a fresh process, so the second run lands on the first
    one's jail *name* by design. What makes that safe is that the first run took
    its jail down; what would make this fix useless is refusing the second run
    anyway. Each boot takes the name fresh and gets a nonce of its own — the
    name is reusable, a live claim is not.
    """
    chroot = Path(plan["host_side"]["chroot_dir"])
    nonces = []
    for _ in range(3):
        result = _boot(
            plan,
            tmp_path,
            monkeypatch,
            jailer=_jailer_writing(plan),
            signals=_Signals(starts_alive=False),
        )
        assert result["outcome"] == "booted"
        assert result["teardown"]["all_gone"] is True
        assert not chroot.exists()
        nonces.append(result["jail_claim"]["nonce"])

    assert len(set(nonces)) == 3


# --------------------------------------------------------------------------
# E11 — two real processes, one name
# --------------------------------------------------------------------------


def _one_process_claiming(repo: str, chroot: str, barrier, out) -> None:
    """Runs after fork: reach the barrier, then race for the one name."""
    import sys

    sys.path.insert(0, repo)
    from core.agentic_v2_first_boot import BootRefused as Refused
    from core.agentic_v2_first_boot import claim_the_jail as claim

    try:
        barrier.wait(10.0)
    except Exception:  # pragma: no cover - a broken barrier is still a race
        pass
    try:
        won = claim(Path(chroot), vm_id="race", plan_sha256="0" * 64)
        out.put(("won", won["nonce"]))
    except Refused as refused:
        out.put(("refused", str(refused)[:120]))
    except BaseException as other:  # pragma: no cover - every outcome is data
        out.put(("error", f"{type(other).__name__}: {other}"))


@pytest.mark.skipif(
    "fork" not in mp.get_all_start_methods(), reason="needs fork to share the barrier"
)
def test_e11_two_processes_reaching_one_name_together_produce_one_winner(tmp_path):
    """The measurement, bounded, in the suite.

    Two forked processes released from one barrier onto one directory name.
    Before the change the equivalent race let both through in 19 of 20 unforced
    pairs; the kernel's answer to ``mkdir`` is what makes it one. This is
    deliberately small — two processes, four rounds — because its job is to fail
    if the atomic operation is ever replaced by a look followed by a leap, not
    to re-measure the width of a window that no longer exists.
    """
    ctx = mp.get_context("fork")
    repo = str(Path(__file__).resolve().parent.parent)

    for round_number in range(4):
        chroot = tmp_path / f"round{round_number}" / "jail" / "root"
        barrier = ctx.Barrier(2)
        out = ctx.Queue()
        procs = [
            ctx.Process(
                target=_one_process_claiming, args=(repo, str(chroot), barrier, out)
            )
            for _ in range(2)
        ]
        for proc in procs:
            proc.start()
        answers = [out.get(timeout=60) for _ in procs]
        for proc in procs:
            proc.join(timeout=30)
            if proc.is_alive():  # pragma: no cover - a hung child is a failure
                proc.terminate()
                pytest.fail("a claiming process never finished")

        verdicts = sorted(verdict for verdict, _ in answers)
        assert verdicts == ["refused", "won"], answers
        winner = next(detail for verdict, detail in answers if verdict == "won")
        assert json.loads((chroot / CLAIM_FILE_NAME).read_text())["nonce"] == winner


# --------------------------------------------------------------------------
# F1-F8 — what authorises removal on the failure path
#
# The independent review found the teardown removing the jail whenever
# ``was_running`` came back ``None``, and prescribed ``pid_file.exists()`` as the
# discriminator: no PID file, nothing was started, take it down. The first half
# of that is sound and the second half is the part these tests are about. A PID
# file that is *there* says the jailer got far enough to publish one. A PID file
# that is *absent* says nothing, because the jailer forks and execs before it
# publishes and a failure can land inside that window — so the same host-side
# reading covers both "nothing ever ran" and "something started half a second
# ago". F2 is that pair, run through the production code, with the host-side
# evidence held identical and only the control flow changed.
#
# What discriminates instead is ``launch_was_attempted``: this run's record of
# whether it reached the call, which has no window in either direction.
# --------------------------------------------------------------------------

_NO_PID_FILE = "no PID file at all"
_AN_UNREADABLE_PID_FILE = "a PID file that cannot be read"


def _a_launch_that_reached_the_host_and_failed(plan, publishes, *, seen=None):
    """A jailer that was called, left ``publishes`` behind, and then failed.

    Every value of ``publishes`` other than :data:`_NO_PID_FILE` is a state the
    host can really be in while a machine is running: a file the jailer is part
    way through writing, or one whose contents this run may not signal. The
    failure is raised *after* the file is in place, which is the ordering that
    matters — the run fails with a machine of its own possibly on the host.

    ``seen`` takes a snapshot of the jail at the instant of the failure, so a
    test can ask whether the teardown left it alone rather than whether it left
    behind something that merely looks similar.
    """
    chroot = Path(plan["host_side"]["chroot_dir"])
    pid_file = Path(plan["host_side"]["pid_file"])

    def jailer(argv, timeout=300.0):
        if publishes is _AN_UNREADABLE_PID_FILE:
            pid_file.mkdir()
        elif publishes is not _NO_PID_FILE:
            pid_file.write_text(publishes)
        if seen is not None:
            seen["jail_at_failure"] = _what_is_in_it(chroot)
        raise subprocess.TimeoutExpired(argv, 120.0)

    return jailer


def test_f1_a_failure_before_the_launch_removes_the_jail_it_claimed(
    plan, tmp_path, monkeypatch
):
    """The case the teardown step exists for, and it has to keep working.

    Placement fails with the jail claimed and nothing started, and the jail goes.
    The review was right about this row; the disagreement is only over *what
    makes it true*. It is true here because this run never reached the call that
    starts a machine, which it knows from its own control flow — not because no
    PID file turned up, which it would also know from a launch that had started
    something a moment earlier. F2 separates the two.
    """
    chroot = Path(plan["host_side"]["chroot_dir"])
    (tmp_path / "rootfs.ext4").unlink()

    with pytest.raises(BootAbandoned) as abandoned:
        _boot(
            plan,
            tmp_path,
            monkeypatch,
            jailer=_a_launch_that_reached_the_host_and_failed(plan, _NO_PID_FILE),
            signals=_Signals(starts_alive=False),
        )

    teardown = abandoned.value.teardown
    assert isinstance(abandoned.value.original, FileNotFoundError)
    assert teardown["process"]["launch_was_attempted"] is False
    assert teardown["process"]["jail_held_by_this_run"] is True
    assert teardown["destroy_refused_because"] is None
    assert teardown["all_gone"] is True
    assert not chroot.exists()


def test_f2_one_absent_pid_file_two_answers_and_the_difference_is_not_on_the_host(
    plan, tmp_path, monkeypatch
):
    """The measurement the prescribed discriminator cannot make.

    Two runs of the same production code over the same jail name. In both the
    PID file is absent at teardown, so ``pid_file.exists()`` returns the same
    value in both. One never reached the launch and its jail is removed; the
    other reached it and its jail is kept. A discriminator that reads the host
    has to give these two the same answer, and one of the two answers is wrong.

    The first run is the one that removes, so the name is free for the second —
    which is also :func:`test_e10`'s point arriving from the other direction.
    """
    chroot = Path(plan["host_side"]["chroot_dir"])
    rootfs = tmp_path / "rootfs.ext4"
    kept_bytes = rootfs.read_bytes()

    rootfs.unlink()
    with pytest.raises(BootAbandoned) as never_launched:
        _boot(
            plan,
            tmp_path,
            monkeypatch,
            jailer=_a_launch_that_reached_the_host_and_failed(plan, _NO_PID_FILE),
            signals=_Signals(starts_alive=False),
        )

    rootfs.write_bytes(kept_bytes)
    rootfs.chmod(0o755)
    with pytest.raises(BootAbandoned) as launched:
        _boot(
            plan,
            tmp_path,
            monkeypatch,
            jailer=_a_launch_that_reached_the_host_and_failed(plan, _NO_PID_FILE),
            signals=_Signals(starts_alive=False),
        )

    before = never_launched.value.teardown
    after = launched.value.teardown

    # Held identical: what the host had to say, and whose jail it was.
    assert before["process"]["pid_file_appeared"] is False
    assert after["process"]["pid_file_appeared"] is False
    assert before["process"]["jail_held_by_this_run"] is True
    assert after["process"]["jail_held_by_this_run"] is True
    assert before["process"]["was_running"] is None
    assert after["process"]["was_running"] is None

    # Changed: whether this run reached the call that starts a machine.
    assert before["process"]["launch_was_attempted"] is False
    assert after["process"]["launch_was_attempted"] is True

    # And that is the only thing the two answers can be coming from.
    assert before["all_gone"] is True
    assert before["destroy_refused_because"] is None
    assert after["all_gone"] is False
    assert "never saw a PID it could watch" in after["destroy_refused_because"]
    assert chroot.exists()


_NO_PID_TO_WATCH = "never saw a PID it could watch"
_LAST_SEEN_RUNNING = "last seen running and was never confirmed stopped"


@pytest.mark.parametrize(
    "publishes, refused_because",
    [
        pytest.param(_NO_PID_FILE, _NO_PID_TO_WATCH, id="absent"),
        pytest.param("", _NO_PID_TO_WATCH, id="empty"),
        pytest.param("\n", _NO_PID_TO_WATCH, id="a_newline_only"),
        pytest.param("not-a-pid", _NO_PID_TO_WATCH, id="not_a_number"),
        pytest.param("0", _NO_PID_TO_WATCH, id="zero"),
        pytest.param("-1", _NO_PID_TO_WATCH, id="negative"),
        pytest.param("42", _LAST_SEEN_RUNNING, id="half_a_pid_written"),
    ],
)
def test_f3_a_pid_this_run_cannot_watch_is_not_a_machine_that_stopped(
    plan, tmp_path, monkeypatch, publishes, refused_because
):
    """Seven readings, one answer, and none of them is a stopped machine.

    ``absent`` is the fork-to-publication window. ``empty`` and
    ``a_newline_only`` are a file being written right now. ``zero`` and
    ``negative`` parse as integers and are refused by
    :func:`_a_pid_this_may_signal` for the separate reason that signalling them
    reaches a process group; they arrive at the teardown as "no PID to watch"
    all the same.

    Six of the seven leave ``was_running`` at ``None``, which is the value the
    removal step used to read as permission. ``None`` is not ``False``: it says
    this run never looked at a process, not that it looked and found none.

    ``half_a_pid_written`` is the seventh and it is carried here because it is
    the row that does *not* use the new rule. A file caught mid-write can hold a
    prefix that parses, and ``42`` does; the teardown watches it, cannot confirm
    it stopped, and refuses through the rule that was already there. Which
    branch each row reaches is asserted rather than left open, so an edit that
    moved a row between the two would be visible here instead of being absorbed
    by a shared ``all_gone is False``.
    """
    seen: dict[str, bytes] = {}
    chroot = Path(plan["host_side"]["chroot_dir"])

    with pytest.raises(BootAbandoned) as abandoned:
        _boot(
            plan,
            tmp_path,
            monkeypatch,
            jailer=_a_launch_that_reached_the_host_and_failed(
                plan, publishes, seen=seen
            ),
            # Alive: a PID this run *can* watch must not accidentally be
            # confirmed stopped and take the jail down for the wrong reason.
            signals=_Signals(starts_alive=True),
        )

    teardown = abandoned.value.teardown
    assert teardown["process"]["launch_was_attempted"] is True
    assert teardown["process"]["confirmed_stopped"] is not True
    assert teardown["all_gone"] is False
    assert refused_because in teardown["destroy_refused_because"]
    assert chroot.exists()
    assert _what_is_in_it(chroot) == seen["jail_at_failure"]


def test_f4_a_pid_file_that_cannot_be_read_is_not_a_machine_that_stopped(
    plan, tmp_path, monkeypatch
):
    """An unreadable PID file is the one reading that also fails the teardown.

    A directory where the file should be makes ``read_text`` raise, which is
    filed as a teardown failure — so ``clean`` is ``False`` here while it is
    ``True`` everywhere else in this block. That is the point of separating it:
    the refusal has to come from the removal rule and not from the cleanup
    having given up part way through. The jail is untouched either way.
    """
    seen: dict[str, bytes] = {}
    chroot = Path(plan["host_side"]["chroot_dir"])

    with pytest.raises(BootAbandoned) as abandoned:
        _boot(
            plan,
            tmp_path,
            monkeypatch,
            jailer=_a_launch_that_reached_the_host_and_failed(
                plan, _AN_UNREADABLE_PID_FILE, seen=seen
            ),
            signals=_Signals(starts_alive=True),
        )

    teardown = abandoned.value.teardown
    assert teardown["process"]["pid_file_appeared"] is True
    assert teardown["process"]["left_alone_because"] == (
        "the PID file could not be read"
    )
    assert teardown["clean"] is False
    assert teardown["all_gone"] is False
    assert "not a stopped machine" in teardown["destroy_refused_because"]
    assert chroot.exists()
    assert _what_is_in_it(chroot) == seen["jail_at_failure"]


def test_f5_the_copy_and_the_jail_say_the_same_thing_in_one_record(
    plan, tmp_path, monkeypatch
):
    """One return value, two halves, and they used to contradict each other.

    On this path the salvage half already said ``unverified`` — this module's
    own words for *nothing here can name what was writing to that disk*. The
    removal half, in the same dictionary, took the jail down. Whichever of the
    two was right, they could not both be, and the one that acted was the one
    that was guessing.
    """
    with pytest.raises(BootAbandoned) as abandoned:
        _boot(
            plan,
            tmp_path,
            monkeypatch,
            jailer=_a_launch_that_reached_the_host_and_failed(plan, ""),
            signals=_Signals(starts_alive=True),
        )

    teardown = abandoned.value.teardown
    assert teardown["salvaged"]["copy_integrity"] == COPY_UNVERIFIED
    assert teardown["salvaged"]["copied_while_running"] is None
    assert teardown["all_gone"] is False
    # The copy is still taken, and it is still the only copy there will be.
    assert Path(teardown["salvaged"]["returned_copy"]).exists()
    assert teardown["process"]["cannot_rule_out"] == CANNOT_RULE_OUT


@pytest.mark.parametrize(
    "reaches_the_launch, alive, publishes, removed",
    [
        pytest.param(False, False, _NO_PID_FILE, True, id="never_launched"),
        pytest.param(True, False, "4242", True, id="confirmed_stopped"),
        pytest.param(True, True, "4242", False, id="still_running"),
        pytest.param(True, True, _NO_PID_FILE, False, id="no_pid_to_watch"),
    ],
)
def test_f6_the_whole_removal_decision_taken_through_the_real_call_path(
    plan, tmp_path, monkeypatch, reaches_the_launch, alive, publishes, removed
):
    """Every row of the removal rule, produced by running the code.

    The review's other finding was that the copy-integrity table's test iterated
    a module constant and so passed under both of its mutants without ever
    calling :func:`first_boot`. This table is the same shape and is deliberately
    not that: each row is a real boot whose outcome the production code decides.

    Two rows remove and two refuse, which is what makes the block say something.
    A change that refused everything would leak a jail on the two ``True`` rows;
    a change that removed everything would take a live machine's disk on the two
    ``False`` ones.
    """
    chroot = Path(plan["host_side"]["chroot_dir"])
    if not reaches_the_launch:
        (tmp_path / "rootfs.ext4").unlink()

    with pytest.raises(BootAbandoned) as abandoned:
        _boot(
            plan,
            tmp_path,
            monkeypatch,
            jailer=_a_launch_that_reached_the_host_and_failed(plan, publishes),
            signals=_Signals(starts_alive=alive),
        )

    teardown = abandoned.value.teardown
    assert teardown["process"]["launch_was_attempted"] is reaches_the_launch
    assert teardown["all_gone"] is removed
    assert chroot.exists() is not removed
    assert (teardown["destroy_refused_because"] is None) is removed


def test_f7_the_new_rule_never_gets_to_speak_for_a_jail_that_is_not_ours(
    plan, tmp_path, monkeypatch
):
    """Ownership answers first, and the new rule is not what is holding the line.

    Every refusal in F2-F6 is this run's own jail being kept because this run
    cannot account for its own machine. A jail that belongs to somebody else is
    a different question with a different answer, and it is settled before a
    launch is ever reached — so the launch counter below stays at zero and the
    stranger's PID file is still the stranger's.

    Without this, an edit that deleted the ownership gate would keep every
    ``all_gone is False`` assertion in this file green, because the new rule
    refuses in the same direction for an unrelated reason.
    """
    chroot = Path(plan["host_side"]["chroot_dir"])
    _a_jail_that_was_already_here(plan, ownership="someone_elses")
    before = _what_is_in_it(chroot)
    launches = []

    def counting_jailer(argv, timeout=300.0):  # pragma: no cover - must not run
        launches.append(argv)
        raise AssertionError("a launch was reached over another run's jail")

    with pytest.raises(BootRefused) as refused:
        _boot(
            plan,
            tmp_path,
            monkeypatch,
            jailer=counting_jailer,
            signals=_Signals(starts_alive=True),
        )

    assert launches == []
    assert "another run" in str(refused.value) or "did not create" in str(refused.value)
    assert _what_is_in_it(chroot) == before
    assert Path(plan["host_side"]["pid_file"]).read_text().strip() == str(STRANGER)


def test_f8_the_teardown_will_not_assume_whether_a_launch_happened(plan, tmp_path):
    """Neither value is safe to default to, so there is no default.

    ``False`` permits removal, which is the direction that takes a live
    machine's disk. ``True`` refuses the one case this step exists for and leaks
    a jail on every failure before the launch. The predecessor of this argument
    was ``chroot_was_already_there: bool = False`` and every caller that forgot
    it got the answer that permits acting; the lesson is written into the
    signature rather than into a comment.

    ``launch_spawned_nothing`` is held to the same rule for a reason of its own.
    Its unsafe value is not the one a default would pick — ``False`` only ever
    refuses — but it is half of a pair, and a default is how one half of a pair
    quietly stops tracking the other.
    """
    parameters = inspect.signature(_clean_up_after_a_failure).parameters
    for name in ("claim", "launch_was_attempted", "launch_spawned_nothing"):
        assert parameters[name].default is inspect.Parameter.empty, name
        assert parameters[name].kind is inspect.Parameter.KEYWORD_ONLY, name

    with pytest.raises(TypeError, match="launch_was_attempted"):
        _clean_up_after_a_failure(
            host_side=plan["host_side"],
            pid_file=Path(plan["host_side"]["pid_file"]),
            claim={"nonce": "0" * 32},
            work_disk=tmp_path / "work.ext4",
            salvage={},
        )



def test_f9_a_pid_file_in_a_jail_this_run_never_launched_into_is_unexplained(
    plan, tmp_path
):
    """Never having started something is not a blanket permission to remove.

    This is the one row of the removal table ``first_boot`` cannot reach on its
    own. Between claiming the name and reaching the launch there is exactly one
    step — placement — and it writes a kernel, a rootfs and a work disk, never a
    PID file. So "this run never launched and yet a PID file is sitting in its
    jail" has no route through ``first_boot``, and reaching it means calling the
    teardown directly. That is not a synthetic shape:
    ``_clean_up_after_a_failure`` has one call site and is handed exactly these
    arguments there.

    Both halves of the launch record say no machine of this run's exists, and
    the jail still stays, because something wrote a PID into it and nothing here
    can say what. An unexplained writer is treated the same as a known one.

    The PID planted is deliberately one this platform will not signal, so the
    branch is reached with nothing signalled and ``was_running`` still ``None`` —
    the reading that looks most like an empty jail, arrived at from the other
    side.
    """
    chroot = Path(plan["host_side"]["chroot_dir"])
    claim = claim_the_jail(
        chroot, vm_id=str(plan["vm_id"]), plan_sha256=str(plan["plan_sha256"])
    )
    (chroot / "work.ext4").write_bytes(b"whatever wrote that PID may be writing here")
    Path(plan["host_side"]["pid_file"]).write_text("not-a-pid\n")
    before = _what_is_in_it(chroot)

    record = _clean_up_after_a_failure(
        host_side=plan["host_side"],
        pid_file=Path(plan["host_side"]["pid_file"]),
        claim=claim,
        launch_was_attempted=False,
        launch_spawned_nothing=False,
        work_disk=tmp_path / "work.ext4",
        salvage={"returned_copy": None, "results_read": False},
    )

    process = record["process"]
    assert process["jail_held_by_this_run"] is True
    assert process["launch_was_attempted"] is False
    assert process["pid_file_appeared"] is True
    assert process["signalled"] is False
    assert process["was_running"] is None
    assert process["confirmed_stopped"] is None

    # The copy and the jail agree, the way they did not before this repair.
    assert record["salvaged"]["copy_integrity"] == COPY_UNVERIFIED
    assert record["all_gone"] is False
    assert "never saw a PID it could watch" in record["destroy_refused_because"]
    assert chroot.exists()
    assert _what_is_in_it(chroot) == before
