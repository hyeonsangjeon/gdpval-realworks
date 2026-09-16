"""The Firecracker release this repository's launcher was written against.

Every flag in :mod:`core.agentic_v2_microvm_launch` was read from **v1.13.1** --
its source, its documentation and its own configuration fixture -- and the pid
filename the launcher waits on comes from behaviour in that version's
``src/jailer/src/env.rs``. A different release is not a newer version of the
same thing; it is a set of assumptions nobody has checked.

So the tag is pinned here in full, in the same shape as
:data:`core.agentic_v2_guest_image.PINNED_GUEST_KERNEL` and for the same
reason: discovery that picks the newest release would move the binaries under
the launcher without anything saying so.

**What the integrity check is and is not.** Upstream publishes a SHA-256 beside
each asset, and it is fetched and checked. That catches a truncated or
corrupted transfer. It is *not* provenance: the checksum is served from the
same release by the same host, so anyone able to replace one could replace the
other. There is no signature to check -- upstream publishes none for these
assets -- and this says so rather than using the word "verified" and leaving a
reader to assume otherwise. The digest that was actually seen is recorded, which
is the part a later run can be compared against.
"""

from __future__ import annotations

import hashlib
import tarfile
import urllib.request
from pathlib import Path
from typing import Any, Callable, Mapping

RELEASES = "https://github.com/firecracker-microvm/firecracker/releases/download"

PINNED_FIRECRACKER_RELEASE: dict[str, Any] = {
    "tag": "v1.13.1",
    "architecture": "x86_64",
    "asset": "firecracker-v1.13.1-x86_64.tgz",
    "url": f"{RELEASES}/v1.13.1/firecracker-v1.13.1-x86_64.tgz",
    "checksum_url": f"{RELEASES}/v1.13.1/firecracker-v1.13.1-x86_64.tgz.sha256.txt",
    "why_this_tag": (
        "every launcher flag in core/agentic_v2_microvm_launch.py was read "
        "from v1.13.1, including the pid filename the launcher waits on"
    ),
    "upstream_publishes_a_checksum": True,
    "checksum_comes_from_the_same_release": True,
    "upstream_publishes_a_signature": False,
}

#: The two programs the first boot needs, and the names it looks for.
#:
#: ``run_agentic_c2_first_boot.py`` finds them with :func:`shutil.which`, so the
#: names on the path have to be exactly these. The release ships them suffixed
#: with the tag and the architecture, which is a legal binary name as far as the
#: launcher is concerned -- it derives the pid file from the basename -- but is
#: not a name ``which`` would answer to.
PROGRAMS = ("firecracker", "jailer")


class ReleaseRefused(RuntimeError):
    """The release was fetched and it was not what was asked for."""


def _fetch(url: str, into: Path, opener: Callable[[str], Any] | None = None) -> Path:
    # The pinned constants are https and there is no reason for anything else to
    # reach this function. Refusing here rather than trusting the caller keeps a
    # mapping that came from somewhere else -- a config file, a future flag --
    # from redirecting the binaries the launcher will run to a local path or an
    # unencrypted one, which the digest check below would then happily confirm.
    if not url.startswith("https://"):
        raise ReleaseRefused(
            f"{url} is not https. The programs the guest is launched with are "
            "fetched over a channel that cannot be rewritten in transit, or "
            "they are not fetched"
        )
    open_it = opener or (lambda address: urllib.request.urlopen(address, timeout=300))
    into.parent.mkdir(parents=True, exist_ok=True)
    with open_it(url) as response, into.open("wb") as handle:
        while True:
            block = response.read(1 << 20)
            if not block:
                break
            handle.write(block)
    return into


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def fetch_release(
    into: Path,
    *,
    release: Mapping[str, Any] = PINNED_FIRECRACKER_RELEASE,
    opener: Callable[[str], Any] | None = None,
) -> dict[str, Any]:
    """Download the pinned tarball and check it against the published digest."""
    tarball = _fetch(str(release["url"]), into / str(release["asset"]), opener)
    published = _fetch(
        str(release["checksum_url"]), into / "published.sha256.txt", opener
    ).read_text(encoding="utf-8")

    # `sha256sum` format: the digest, whitespace, then the filename it was taken
    # over. Only the first field is of interest, and only if there is one.
    wanted = published.split()[0].strip().lower() if published.split() else ""
    seen = _sha256(tarball)
    if not wanted:
        raise ReleaseRefused(
            f"{release['checksum_url']} carried no digest, so there was "
            "nothing to check the download against"
        )
    if seen != wanted:
        raise ReleaseRefused(
            f"the tarball hashes to {seen} and the release says {wanted}. "
            "That is a different file from the one this launcher was written "
            "against, whatever the reason"
        )
    return {
        "tag": release["tag"],
        "url": release["url"],
        "path": tarball.as_posix(),
        "size_bytes": tarball.stat().st_size,
        "sha256": seen,
        "checksum_matched_the_published_one": True,
        "what_that_does_not_mean": (
            "the digest is served from the same release by the same host, so "
            "this is a transfer check and not provenance. Upstream publishes "
            "no signature for these assets"
        ),
    }


def unpack_programs(tarball: Path, into: Path) -> dict[str, dict[str, Any]]:
    """Extract the two programs, found by prefix rather than by assumed path.

    The archive lays the binaries out under a directory named for the release
    and suffixes each with the tag and the architecture. Both are upstream's to
    change, and a hard-coded member path would fail as a ``KeyError`` deep in a
    step rather than as a sentence. So each program is found by the prefix its
    name has always had, and it is an error for a prefix to match none or more
    than one.
    """
    into.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tarball, "r:gz") as archive:
        members = [
            member for member in archive.getmembers() if member.isfile()
        ]
        found: dict[str, dict[str, Any]] = {}
        for program in PROGRAMS:
            matches = [
                member
                for member in members
                if Path(member.name).name.startswith(f"{program}-")
            ]
            if len(matches) != 1:
                raise ReleaseRefused(
                    f"looking for one {program} in {tarball.name} found "
                    f"{[m.name for m in matches]}. The archive is not laid out "
                    "the way this release was"
                )
            member = matches[0]
            extracted = archive.extractfile(member)
            if extracted is None:
                raise ReleaseRefused(f"{member.name} would not open")
            destination = into / program
            with destination.open("wb") as handle:
                while True:
                    block = extracted.read(1 << 20)
                    if not block:
                        break
                    handle.write(block)
            destination.chmod(0o755)
            found[program] = {
                "came_from": member.name,
                "installed_as": destination.as_posix(),
                "size_bytes": destination.stat().st_size,
                "sha256": _sha256(destination),
            }
    return found
