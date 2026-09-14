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

import json
import multiprocessing as mp
import os
import subprocess
from pathlib import Path

import pytest

from core.agentic_v2_first_boot import (
    CANNOT_RULE_OUT,
    CLAIM_FILE_NAME,
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
