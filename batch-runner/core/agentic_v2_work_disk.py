"""Carrying a workspace into one machine and back out again.

D1 builds the command and reads the boot. D2 is the backend that holds the
workspace on the host between calls. Between them sits the thing neither of them
is: the *carriage*. Each ``exec_run`` has to put the session's files onto a work
disk, boot, and take back whatever the command changed — and it has to do that
without a mount, without privilege, and without quietly altering a byte.

**Why this is its own module rather than three lines in the backend.** Every
failure here looks like something else. A workspace that did not arrive looks
like a model that wrote to the wrong path. A read-back that produced nothing
looks like a command that printed nothing. Bytes mangled in transit look like a
model that produced a corrupt spreadsheet. Across 220 tasks each of those reads
as a finding about the model, and none of them would be. So the carriage is
written where it can be tested on its own, on a box that cannot boot a machine
at all, using the same ``mke2fs`` and ``debugfs`` that will do the work in
production.

Four facts were measured with those tools rather than assumed, and each one
changed the code:

**``debugfs -R`` exits 0 when it fails.** A missing directory in the image, a
destination that does not exist, and a superblock that is not one all produce
the complaint on stderr and a returncode of zero. So the returncode is not
evidence of anything, and the read-back is judged by what actually landed on the
host. This is the same rule D1 reads boots by: *absent evidence is not a
result*, and the reason it matters more here is that the failure is silent and
the wrong conclusion is plausible.

**``rdump`` is byte-exact and ``cat`` is not.** ``debugfs -R "cat …"`` comes
back through a text pipe, which is fine for an exit status and destroys an
``.xlsx``. The workspace comes back with ``rdump``, which writes the files
directly and preserved a byte sequence containing NUL, ``0xff`` and ``0xfe``
unchanged in the measurement.

**Symlinks survive the round trip in both directions.** ``mke2fs -d`` copies a
symlink into the image as a symlink rather than following it, and ``rdump``
recreates one on the host — including an absolute one pointing at
``/etc/passwd``. Inside the guest that is harmless: the root filesystem is
read-only and it resolves to the guest's own file. On the *host* it is a link
into the host that a later step might follow. D2's inherited workspace code
opens everything with ``O_NOFOLLOW`` and would refuse it, but the carriage must
not depend on the other end being careful — a deliverable collector, a report
step or an operator's ``cp -r`` would all follow it. So a link that leaves the
workspace is not carried, and is recorded as having been refused.

**A renamed workspace is a broken workspace.** The obvious way to install what
came back is to rename the old directory aside and the new one into its place,
which is atomic. It also destroys the session: the backend holding the workspace
pins ``(st_dev, st_ino)`` at construction and keeps the descriptor, so after a
rename its own re-check refuses and a write through that descriptor raises
``FileNotFoundError``. Measured here, not reasoned about. The children are moved
instead and the directory keeps its identity; :func:`carry_the_workspace_back`
says what that costs. The failure this avoids would have appeared on the second
``exec_run`` of a session, after the first looked fine.

What is deliberately not here: booting. This module stages a disk and reads one
back. :func:`core.agentic_v2_first_boot.first_boot` is what runs in between, and
it is the caller's to supply, exactly as it was for stage C's attacks.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from core.agentic_v2_guest_image import build_ext4, sha256_file
from core.agentic_v2_substrate import REQUIRED_MICROVM_POLICY


SCRATCH_ON_DISK = "in"
RESULTS_ON_DISK = "out"
WORKSPACE_ON_DISK = "ws"
"""The three directories on the work disk, and the guest's view of them.

``GUEST_INIT`` mounts the disk at ``/work`` and runs ``/work/in/command.sh``, so
these are ``/work/in``, ``/work/out`` and ``/work/ws`` in the machine. The last
one is D1's :data:`~core.agentic_v2_exec_boot.WORKSPACE_IN_GUEST`, which is why
it is spelled here rather than derived: the two have to agree, and a test says
so out loud instead of leaving it to whoever edits one of them next.
"""

COMMAND_ON_DISK = f"{SCRATCH_ON_DISK}/command.sh"

BYTES_A_QUOTA_ACTUALLY_HOLDS = 234_557_440
"""How much content fits in the policy's 256 MiB disk, measured rather than guessed.

``mke2fs -q -F -t ext4 -b 4096`` on a 256 MiB image leaves 57,265 free 4 KiB
blocks — the rest goes to the journal, the inode tables and the reserved block
count. Sizing a refusal off the nominal 268,435,456 would let a workspace 32 MiB
too large through, and it would fail during ``mke2fs`` with a message about
blocks that reads like a broken toolchain rather than like a full disk.

The arithmetic is still not trusted. :func:`stage_the_work_disk` checks what
landed after building, because a formula that is right today is a formula that
is wrong the first time a filesystem option changes.
"""

INODES_A_QUOTA_ACTUALLY_HOLDS = 65_522
"""And how many files, which is the limit a directory of small outputs hits first."""

_QUOTA_MIB = int(REQUIRED_MICROVM_POLICY["workdir_quota_mib"])


class WorkDiskRefused(RuntimeError):
    """The workspace cannot be carried, so no disk was built and nothing booted.

    Distinct from a command that failed and from a machine that would not start.
    This is the host declining before either could happen, which is the cheapest
    place to decline and the only place where the reason is still legible.
    """


def _walk(root: Path) -> Iterable[tuple[Path, os.stat_result]]:
    for current, directories, files in os.walk(root, followlinks=False):
        here = Path(current)
        for name in list(directories) + files:
            path = here / name
            yield path, path.lstat()


def _leaves_the_tree(link: Path, root: Path) -> bool:
    """Whether a symlink points anywhere but inside ``root``.

    Resolved without touching the filesystem — ``os.path.realpath`` would follow
    the link, and following a link that points at something slow, absent or
    privileged is the thing being avoided. An absolute target is out by
    definition; a relative one is joined to the link's own directory and
    normalised.
    """
    target = os.readlink(link)
    if os.path.isabs(target):
        return True
    landing = os.path.normpath(os.path.join(link.parent, target))
    return not (landing == str(root) or landing.startswith(f"{root}{os.sep}"))


def what_would_be_carried_in(
    workspace: str | Path, *, quota_mib: int = _QUOTA_MIB
) -> dict[str, Any]:
    """Measure a host workspace against the disk it has to fit on.

    Returns a description and raises nothing; :func:`stage_the_work_disk` is
    what refuses. Separated so the measurement can be taken — and reported —
    without committing to building anything, which is what a caller sizing a
    task wants.
    """
    root = Path(workspace).resolve()
    files = 0
    directories = 0
    links_out: list[str] = []
    total = 0
    for path, stats in _walk(root):
        if os.path.islink(path):
            files += 1
            if _leaves_the_tree(path, root):
                links_out.append(path.relative_to(root).as_posix())
            continue
        if os.path.isdir(path):
            directories += 1
            continue
        files += 1
        total += stats.st_size
    room = min(BYTES_A_QUOTA_ACTUALLY_HOLDS, quota_mib * 1024 * 1024)
    return {
        "workspace": root.as_posix(),
        "files": files,
        "directories": directories,
        "bytes": total,
        "room_bytes": room,
        "fits": total <= room,
        "inode_room": INODES_A_QUOTA_ACTUALLY_HOLDS,
        "entries": files + directories,
        "symlinks_leaving_the_workspace": sorted(links_out),
    }


def stage_the_work_disk(
    *,
    workspace: str | Path,
    command_sh: str,
    into: str | Path,
    quota_mib: int = _QUOTA_MIB,
    build: Callable[..., Mapping[str, Any]] = build_ext4,
) -> dict[str, Any]:
    """Build one call's work disk: the command, an empty result tray, the workspace.

    The workspace is *copied* rather than moved. If the boot goes wrong, the
    host still holds what the session had before it, and a call that failed
    leaves the model exactly where it was rather than one directory poorer.

    Refuses before building when the workspace cannot fit or holds a link out of
    itself. Both are cheap to see here and expensive to see later: the first
    fails inside ``mke2fs`` with a message about blocks, and the second puts a
    path into the guest that means something different on each side of the wall.
    """
    measured = what_would_be_carried_in(workspace, quota_mib=quota_mib)
    if measured["symlinks_leaving_the_workspace"]:
        raise WorkDiskRefused(
            "the workspace holds symbolic links pointing out of itself — "
            f"{measured['symlinks_leaving_the_workspace']} — and a link means a "
            "different thing on each side of the wall, so none of it is carried"
        )
    payload = len(command_sh.encode("utf-8"))
    if measured["bytes"] + payload > measured["room_bytes"]:
        raise WorkDiskRefused(
            f"the workspace is {measured['bytes']} bytes and the command is "
            f"{payload}, against {measured['room_bytes']} a "
            f"{quota_mib} MiB disk actually holds. Building it would fail inside "
            "mke2fs with a message about blocks, which is not the reason"
        )
    if measured["entries"] >= measured["inode_room"]:
        raise WorkDiskRefused(
            f"the workspace has {measured['entries']} entries against "
            f"{measured['inode_room']} inodes on the disk"
        )

    into = Path(into)
    staging = into / "staging"
    if staging.exists():
        shutil.rmtree(staging)
    (staging / SCRATCH_ON_DISK).mkdir(parents=True)
    (staging / RESULTS_ON_DISK).mkdir(parents=True)
    # symlinks=True keeps a link a link. Following one would copy whatever it
    # points at into the guest, and the links that could do harm were refused
    # above -- this is about the ones that are ordinary and should survive.
    shutil.copytree(
        Path(workspace), staging / WORKSPACE_ON_DISK, symlinks=True, dirs_exist_ok=True
    )
    (staging / COMMAND_ON_DISK).write_text(command_sh, encoding="utf-8")

    image = into / "work.ext4"
    built = build(image, size_mib=quota_mib, populate_from=staging)

    landed = _what_the_image_holds(image)
    if landed.get("command_bytes") != payload:
        raise WorkDiskRefused(
            "the command did not land on the disk at the size it was written — "
            f"{landed.get('command_bytes')!r} against {payload}. The disk was "
            "built and is not usable, and booting it would run something else"
        )
    return {
        "image": image.as_posix(),
        "sha256": built.get("sha256"),
        "size_mib": quota_mib,
        "carried": measured,
        "staging": staging.as_posix(),
        "checked": landed,
    }


def _what_the_image_holds(
    image: str | Path, *, run: Callable[[Sequence[str]], Any] | None = None
) -> dict[str, Any]:
    """Read back the one fact that says the staging worked: the command's size.

    ``mke2fs -d`` reports a full disk on stderr and can still produce an image,
    so the arithmetic above is checked against the filesystem rather than
    believed. One ``stat`` is enough — if the command is whole, the disk was not
    truncated under it.
    """
    runner = run or _debugfs_runner
    result = runner(["debugfs", "-R", f"stat {COMMAND_ON_DISK}", Path(image).as_posix()])
    text = getattr(result, "stdout", "") or ""
    size: int | None = None
    for line in text.splitlines():
        # The size sits on the ownership line -- "User: 1026 Group: 100
        # Project: 0 Size: 18". Anchoring on "User:" rather than on "Size:"
        # alone matters: two lines below it there is a "Fragment: Address: 0
        # Number: 0 Size: 0", and reading that one would report every command
        # as empty.
        if "User:" not in line or "Size:" not in line:
            continue
        try:
            size = int(line.split("Size:")[1].split()[0])
        except (IndexError, ValueError):
            size = None
    return {"command_bytes": size, "said": (getattr(result, "stderr", "") or "").strip()}


def _debugfs_runner(command: Sequence[str]) -> Any:
    return subprocess.run(  # noqa: S603
        list(command), check=False, capture_output=True, text=True, timeout=300
    )


def rdump_arguments(
    image: str | Path, *, inside: str, destination: str | Path
) -> list[str]:
    """The ``debugfs`` call that takes a whole directory out of an image.

    Built where a test can read it, for the same reason
    :func:`core.agentic_v2_guest_image.ext4_image_arguments` is: these arguments
    decide whether the host mounts a filesystem the guest was writing, and that
    decision should be visible without running anything. ``rdump`` walks the
    structures in userspace — no loop device, no privilege, and the host
    kernel's ext4 driver never sees the image.
    """
    return [
        "debugfs",
        "-R",
        f"rdump {inside} {Path(destination).as_posix()}",
        Path(image).as_posix(),
    ]


def workspace_out_of_work_disk(
    *,
    image: str | Path,
    into: str | Path,
    run: Callable[[Sequence[str]], Any] | None = None,
) -> dict[str, Any]:
    """Take the workspace off a work disk, and say what came back.

    The returncode is ignored on purpose: ``debugfs -R`` exits 0 whether it
    dumped a tree, could not find one, could not write one, or could not read
    the superblock. What is trusted instead is the directory on the host
    afterwards — it either exists with something in it or it does not, and
    ``read_back`` is that answer rather than the tool's.

    Links pointing out of the workspace are **not** carried. They are deleted
    from what landed and named in ``refused_symlinks``, because a guest can
    create one and the host is where it would mean something.
    """
    runner = run or _debugfs_runner
    into = Path(into)
    into.mkdir(parents=True, exist_ok=True)
    result = runner(rdump_arguments(image, inside=f"/{WORKSPACE_ON_DISK}", destination=into))
    said = (getattr(result, "stderr", "") or "").strip()

    landed = into / WORKSPACE_ON_DISK
    if not landed.is_dir():
        return {
            "read_back": False,
            "root": None,
            "files": 0,
            "bytes": 0,
            "refused_symlinks": [],
            "said": said,
            "grounds": (
                "debugfs left no /ws directory on the host, so nothing came back "
                "off the disk. That is not the same as a command that wrote "
                "nothing, and it is never reported as one"
            ),
        }

    refused: list[str] = []
    files = 0
    total = 0
    for path, stats in list(_walk(landed)):
        if os.path.islink(path):
            if _leaves_the_tree(path, landed):
                refused.append(path.relative_to(landed).as_posix())
                path.unlink()
            else:
                files += 1
            continue
        if path.is_dir():
            continue
        files += 1
        total += stats.st_size
    return {
        "read_back": True,
        "root": landed.as_posix(),
        "files": files,
        "bytes": total,
        "refused_symlinks": sorted(refused),
        "said": said,
        "grounds": f"{files} files came back off the disk",
    }


def carry_the_workspace_back(
    *,
    image: str | Path,
    workspace: str | Path,
    scratch: str | Path,
    run: Callable[[Sequence[str]], Any] | None = None,
) -> dict[str, Any]:
    """Replace the *contents* of the host workspace with what the disk holds.

    **Only if something came back.** A read-back that produced nothing leaves
    the host workspace exactly as it was: the alternative is deleting a
    session's accumulated work because *this* call's carriage broke, which
    converts an infrastructure fault into the permanent loss of a model's
    output. The result says which happened, and the caller reports it as an
    infrastructure failure rather than as an empty answer.

    **The directory itself is never replaced, and that is not a style choice.**
    The obvious implementation renames the old workspace aside and renames the
    new one into its place, which is atomic and would be better in every way
    except the one that matters: the object holding this workspace opens it once
    and keeps the descriptor. ``AgenticV2FixtureBackend.__init__`` pins
    ``(st_dev, st_ino)`` and re-checks it before later work. Measured on this
    box, a rename-swap leaves that descriptor pointing at the renamed-away
    directory, so the backend's re-check refuses and a write through the pinned
    descriptor raises ``FileNotFoundError`` once the old directory is removed.
    The failure would arrive on the *second* ``exec_run`` of a session, after
    the first had already looked like it worked.

    So the children are moved instead and the directory stays the one it was.
    The cost is a window in which the workspace holds neither set whole; it is
    inside one synchronous call with no other reader, and it is a far smaller
    thing than losing the inode. If the move in fails partway, what was moved
    aside is put back, so a half-carriage does not become an empty workspace.

    ``shutil.move`` rather than ``rename`` because the read-back lands in the
    caller's scratch and the workspace need not be on the same filesystem.
    """
    read = workspace_out_of_work_disk(image=image, into=scratch, run=run)
    workspace = Path(workspace)
    if not read["read_back"]:
        return {**read, "replaced": False}

    landed = Path(read["root"])
    held = Path(scratch) / "previous"
    if held.exists():
        shutil.rmtree(held)
    held.mkdir(parents=True)

    moved_aside = []
    for child in sorted(workspace.iterdir()):
        shutil.move(str(child), str(held / child.name))
        moved_aside.append(child.name)
    try:
        for child in sorted(landed.iterdir()):
            shutil.move(str(child), str(workspace / child.name))
    except OSError:
        for name in moved_aside:
            if not (workspace / name).exists():
                shutil.move(str(held / name), str(workspace / name))
        raise
    shutil.rmtree(held, ignore_errors=True)
    return {**read, "replaced": True}


def work_disk_fingerprint(image: str | Path) -> str | None:
    """The disk as it stands, for a record that has to distinguish two calls."""
    path = Path(image)
    return sha256_file(path) if path.exists() else None
