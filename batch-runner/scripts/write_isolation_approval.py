#!/usr/bin/env python3
"""Write the document that admits a run onto a real guest -- after proving it.

The paid stage takes ``--isolated-approval``, and until now nothing produced
one. The artefact it names was written by hand on ``gdpval-devhost-vm``, which
is the arrangement this path exists to replace: the model route lives where the
federated session is, the guest lives where the hardware virtualisation is, and
those were two machines. Both now fit on one runner, so the proof can be made
and used in one job without anything being carried between hosts.

**Nothing is written until it has been proven.** The order here matters more
than it looks. The approval is assembled in memory, handed to the same
:func:`select_backend` the paid stage will call, and only written if that
returns the isolated backend. A file that exists is a file a later step will
pass along, and an approval that would be refused at task one -- after
``azure/login``, after the ledger is opened -- is worth refusing here, where the
cost of being wrong is a red step.

**The extra check this makes, and why it is here rather than in select_backend.**
``what_a_booted_host_left`` compares the artefact's recorded kernel release
against this host's, and its own docstring is careful to say that is not a host
identity: two machines provisioned from one image report the same string. That
is exactly what happens on GitHub's runners. Runs 35072131325 and 35072747069
were different machines and both reported ``6.17.0-1022-azure``, so kernel
equality would not notice an artefact carried from one runner to another. The
boot id would. It is read here rather than added to ``select_backend`` because
the existing callers legitimately consume an artefact written by an earlier
process on a long-lived host, and tightening their gate is a separate decision
from establishing this one.

Reads a file and hashes two images. Boots nothing, calls no model, spends
nothing.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Mapping

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core.agentic_v2_isolated_selection import (  # noqa: E402
    IsolatedBackendRefused,
    IsolationApproval,
    select_backend,
)

BOOT_ID = Path("/proc/sys/kernel/random/boot_id")

#: The manifest the foundation ships, and the only one this path admits.
SUBSTRATE_MANIFEST = BATCH_RUNNER_ROOT / "sandbox" / "agentic_v2_capabilities.json"


class ApprovalRefused(RuntimeError):
    """The approval was not written, and this is the reason."""


def this_boot() -> str | None:
    """The kernel's own name for this boot of this machine.

    A fresh UUID every time a machine starts, so two runners out of one image
    differ and the same runner an hour later does not. Absent on a kernel that
    does not publish it, which is answered by refusing rather than by assuming.
    """
    try:
        return BOOT_ID.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def the_artefact_was_written_here(
    artefact: Mapping[str, Any], *, boot_id: str | None
) -> dict[str, Any]:
    """Refuse an artefact that was produced on some other machine.

    The whole point of co-locating the guest with the model route is that the
    proof does not travel. An artefact that arrived by download is a claim about
    a machine this one has no way to check, and it would pass every other gate:
    the images it names would be absent (caught), or present because somebody
    copied those too (not caught by anything else here).
    """
    host = artefact.get("host")
    if not isinstance(host, Mapping):
        raise ApprovalRefused(
            "the artefact has no host block, so there is nothing in it that "
            "says which machine booted the guest"
        )
    recorded = str(host.get("boot_id") or "").strip()
    if not recorded:
        raise ApprovalRefused(
            "the artefact records no boot id. Either it predates this check or "
            "it was written somewhere that does not publish one -- and in both "
            "cases this host cannot tell whether the guest booted here. Re-run "
            "scripts/run_agentic_c2_first_boot.py on this machine"
        )
    if not boot_id:
        raise ApprovalRefused(
            f"this kernel does not publish {BOOT_ID}, so there is nothing to "
            "compare the artefact's boot id against. The same-host arrangement "
            "rests on being able to show the proof was made here"
        )
    if recorded != boot_id:
        raise ApprovalRefused(
            f"the artefact was written during boot {recorded} and this is boot "
            f"{boot_id}. That is a different machine, or the same machine "
            "restarted; either way the guest it describes is not one this host "
            "has been shown to be able to boot. Proof is not carried between "
            "hosts"
        )
    return {
        "boot_id": boot_id,
        "what_this_shows": (
            "the artefact was written by a process on this machine, during "
            "this boot of it -- which the kernel release cannot show, because "
            "two runners built from one image report the same release"
        ),
    }


def prove_and_write(
    *,
    artefact_path: Path,
    substrate_manifest: Path,
    scratch: Path,
    approved_by: str,
    session: str,
    vcpu_count: int,
    into: Path,
    boot_id: str | None,
) -> dict[str, Any]:
    """Assemble the approval, make the real selector accept it, then write it.

    ``boot_id`` is what this host said when asked, which is the caller's job to
    ask -- :func:`this_boot` -- and has no default on purpose. A default would
    have to spell "read it yourself" and "this kernel publishes none" with the
    same value, and those are different facts: the first is the ordinary case
    and the second is a refusal. A function whose whole purpose is declining
    ambiguous evidence should not begin by accepting an ambiguous argument.
    """
    if not artefact_path.is_file():
        raise ApprovalRefused(
            f"there is no first-boot artefact at {artefact_path}. Run "
            "scripts/run_agentic_c2_first_boot.py on this machine first"
        )
    artefact = json.loads(artefact_path.read_text(encoding="utf-8"))
    same_machine = the_artefact_was_written_here(artefact, boot_id=boot_id)

    document = {
        "approved_by": approved_by,
        "first_boot_artefact": artefact_path.as_posix(),
        "substrate_manifest": substrate_manifest.as_posix(),
        "scratch": scratch.as_posix(),
        "vcpu_count": vcpu_count,
    }
    try:
        approval = IsolationApproval.from_mapping(document)
        choice = select_backend(approval=approval, session=session)
    except IsolatedBackendRefused as refusal:
        raise ApprovalRefused(
            f"{refusal}\n\nNothing was written. The paid stage would have "
            "raised this on task one, after the ledger was open"
        ) from refusal

    if not choice.is_isolated:
        # Unreachable as the selector stands, and checked anyway. A fixture
        # returned from a call that was given an approval is the exact failure
        # this whole path exists to prevent: a run that looks isolated, costs
        # what an isolated run costs, and is not one.
        raise ApprovalRefused(
            f"select_backend was given an approval and answered "
            f"{choice.backend_class.__name__}. An approval that resolves to "
            "the fixture is a run that would report isolation it never had"
        )

    into.parent.mkdir(parents=True, exist_ok=True)
    into.write_text(json.dumps(document, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "approval": document,
        "written_to": into.as_posix(),
        "backend": choice.backend_class.__name__,
        "same_machine": same_machine,
        "grounds": {
            key: value
            for key, value in choice.grounds.items()
            if key != "images_rechecked"
        },
        "images_rechecked": choice.grounds.get("images_rechecked"),
    }


def report(record: dict[str, Any]) -> None:
    print("An approval onto a real guest, proved before it was written")
    print("=" * 74)
    print()
    print(f"  backend        {record['backend']}")
    print(f"  written to     {record['written_to']}")
    print(f"  boot id        {record['same_machine']['boot_id']}")
    print(f"                 {record['same_machine']['what_this_shows']}")
    print()
    for key, value in sorted(record["grounds"].items()):
        print(f"  {key:<14} {value}")
    print()
    rechecked = record.get("images_rechecked") or {}
    for which, detail in sorted(rechecked.items()):
        if isinstance(detail, Mapping):
            print(f"  {which:<14} {detail.get('sha256', detail)}")
    print()
    print(
        "The proof was made on this machine and is consumed on this machine. "
        "Nothing was carried between hosts."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--first-boot-artefact",
        type=Path,
        required=True,
        help="What scripts/run_agentic_c2_first_boot.py wrote, on this machine.",
    )
    parser.add_argument(
        "--substrate-manifest",
        type=Path,
        default=SUBSTRATE_MANIFEST,
        help=(
            "The foundation's capability manifest. Defaults to the one this "
            "repository ships; a manifest that is not foundation-only is "
            "refused by the selector, not by this."
        ),
    )
    parser.add_argument(
        "--scratch",
        type=Path,
        required=True,
        help="Where each call builds its own jail. One per call, never reused.",
    )
    parser.add_argument(
        "--approved-by",
        required=True,
        help=(
            "Who admitted this run. On a runner this is the dispatch -- the "
            "workflow, the run id, the attempt and the commit -- so the record "
            "names something a reader can go and look at."
        ),
    )
    parser.add_argument(
        "--session",
        required=True,
        help=(
            "The run id the launcher builds its jail names under. Given here "
            "only to prove the selector accepts the approval; the stage passes "
            "its own."
        ),
    )
    parser.add_argument("--vcpu-count", type=int, default=2)
    parser.add_argument(
        "--into",
        type=Path,
        required=True,
        help="Where the approval is written, once it has been proven.",
    )
    args = parser.parse_args(argv)

    try:
        record = prove_and_write(
            artefact_path=args.first_boot_artefact,
            substrate_manifest=args.substrate_manifest,
            scratch=args.scratch,
            approved_by=args.approved_by,
            session=args.session,
            vcpu_count=args.vcpu_count,
            into=args.into,
            boot_id=this_boot(),
        )
    except ApprovalRefused as refusal:
        print(f"refused: {refusal}", file=sys.stderr)
        print(
            f"\n{args.into} was not written, so nothing downstream can pass an "
            "approval this host would not stand behind.",
            file=sys.stderr,
        )
        return 1
    except (OSError, ValueError) as broken:
        print(
            f"refused: the first-boot artefact at {args.first_boot_artefact} "
            f"could not be read as one: {broken}",
            file=sys.stderr,
        )
        return 1

    report(record)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
