#!/usr/bin/env python3
"""Put the two programs that launch a guest on this machine, by pin.

Until now nothing in this repository installed firecracker or jailer. They were
put on ``gdpval-devhost-vm`` by hand, which is why nobody had to write down what
"install firecracker" means -- and why the obvious version of it is wrong. The
recipe that circulates fetches whatever release is newest, and every launcher
flag in :mod:`core.agentic_v2_microvm_launch` was read from **v1.13.1**,
including the pid filename the launcher waits on. A newer release is not a newer
version of the same thing; it is a set of assumptions nobody has checked.

So the tag is pinned, the digest upstream publishes is checked, and the digest
actually seen is written into the report. :mod:`core.agentic_v2_firecracker_release`
holds all three and says plainly which of them is provenance: none of them. The
checksum is served from the same release by the same host and upstream signs
nothing, so this catches a truncated download, not a substituted one.

**This deliberately does not need root.** It fetches and unpacks into a
directory the caller names, and stops. Putting the result somewhere on the
program search path is one privileged line the caller runs itself, where a
reader of the log can see it:

    sudo install -m 0755 -t /usr/local/bin <into>/firecracker <into>/jailer

and whether that worked is then answered by the reading that already exists --
``check_runner_can_host_a_guest.py --require-programs`` -- rather than by a
second claim made here.

Reaches the network. Boots nothing, calls no model, changes nothing outside the
directory it was given.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core.agentic_v2_firecracker_release import (  # noqa: E402
    PINNED_FIRECRACKER_RELEASE,
    PROGRAMS,
    ReleaseRefused,
    fetch_release,
    unpack_programs,
)


def install(into: Path, *, work: Path, opener: Callable[[str], Any] | None = None) -> dict:
    """Fetch the pinned release and lay both programs out in ``into``.

    ``opener`` is the seam the tests use. The alternative is a test suite that
    reaches GitHub, which would make a red build mean "upstream is slow" as
    often as it means anything about this code.
    """
    release = fetch_release(work, opener=opener)
    installed = unpack_programs(Path(release["path"]), into)
    return {
        "schema_version": "1.0",
        "release": release,
        "installed": installed,
        "into": into.as_posix(),
        "what_is_still_needed": (
            "these are on disk, not on the program search path. "
            "run_agentic_c2_first_boot.py finds them with shutil.which, so "
            f"until {into.as_posix()} is on PATH -- or the files are copied "
            "somewhere that already is -- the boot refuses for want of a jailer"
        ),
    }


def report(record: dict) -> None:
    release = record["release"]
    print("Firecracker, pinned rather than picked")
    print("=" * 74)
    print()
    print(f"  tag       {release['tag']}")
    print(f"  from      {release['url']}")
    print(f"  bytes     {release['size_bytes']:,}")
    print(f"  sha256    {release['sha256']}")
    print("            matches the digest published beside the asset")
    print(f"            -- {release['what_that_does_not_mean']}")
    print()
    for program in PROGRAMS:
        one = record["installed"][program]
        print(f"  {program}")
        print(f"    from    {one['came_from']}")
        print(f"    at      {one['installed_as']}")
        print(f"    sha256  {one['sha256']}")
    print()
    print(record["what_is_still_needed"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--into",
        type=Path,
        required=True,
        help=(
            "Where the two programs are written, under the names "
            "run_agentic_c2_first_boot.py looks for. Not required to be on "
            "PATH and not required to be writable only by root; this does not "
            "need privilege and does not take any."
        ),
    )
    parser.add_argument(
        "--work",
        type=Path,
        default=None,
        help=(
            "Where the tarball and its checksum are downloaded to. Defaults "
            "to a 'download' directory beside --into."
        ),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Write the record -- both digests and both programs -- as JSON.",
    )
    args = parser.parse_args(argv)

    work = args.work or (args.into.parent / "download")
    try:
        record = install(args.into, work=work)
    except ReleaseRefused as refusal:
        # Fail closed, loudly, and without leaving anything half-installed
        # where the next step would find it and believe it.
        print(f"refused: {refusal}", file=sys.stderr)
        print(
            f"nothing was installed into {args.into}. The pinned release is "
            f"{PINNED_FIRECRACKER_RELEASE['tag']} and it is pinned because the "
            "launcher was written against it.",
            file=sys.stderr,
        )
        return 1

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(record, indent=2, sort_keys=True), encoding="utf-8"
        )
    report(record)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
