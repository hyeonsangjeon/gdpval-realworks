#!/usr/bin/env python3
"""Whether the machine this runs on could host a Firecracker guest.

The isolated backend and the model route have never been on the same machine.
The model route needs the Actions OIDC identity, which exists only on a GitHub
runner; the isolated backend needs working hardware virtualisation, which so far
has existed only on ``gdpval-devhost-vm``. Carrying the first-boot artefact
between them is not a way round it and was never meant to be: admission compares
the recorded ``host.kernel_release`` against ``os.uname().release`` and re-hashes
the kernel and rootfs at their recorded paths, so an artefact is evidence about
the machine that produced it and about no other.

That leaves one arrangement in which both halves are true at once — produce the
artefact and spend the money on the same runner, in the same job. Whether that
arrangement exists at all is a fact about GitHub's runner image, and this script
is how it gets asked instead of assumed.

**Four of the five readings already existed.** ``read_this_machine`` and
``judge_containment`` in :mod:`core.agentic_v2_containment_readiness` take the
processor flags, the reach of the device, the kernel version and the two
programs, and judge them against Firecracker's own kernel policy. They are
called here rather than repeated, because reading one thing two ways is how two
answers to one question start to disagree.

**The fifth is new and is the one this was written for.** Every existing reading
of ``/dev/kvm`` in this repository stops at the filename:
``inspect_microvm_readiness`` asks whether the permission bits allow a read and
a write, ``read_the_host`` in ``scripts/run_agentic_c2_first_boot.py`` asks only
whether the path exists. A host where the device is present, the bits allow it,
and hardware virtualisation is nonetheless unavailable passes both and fails at
the first ``exec_run`` of a cohort that has already been paid for. So
:func:`core.agentic_v2_kvm_probe.probe_kvm` opens the device and asks it to make
one empty machine.

**What is a fact about the runner and what a job can install are kept apart.**
``firecracker`` and ``jailer`` being absent from a bare runner image is not a
finding about the runner — a step installs them. Hardware virtualisation being
unavailable is a finding about the runner, and no step fixes it. The exit code
follows that split: by default only the readings no install step can change are
gated on. ``--require-programs`` adds the two programs, which is what a job asks
after its install step has run rather than before it.

Usage::

    cd batch-runner
    python scripts/check_runner_can_host_a_guest.py
    python scripts/check_runner_can_host_a_guest.py --require-programs
    python scripts/check_runner_can_host_a_guest.py --report out.json

Exit 0 when every gated reading holds, 1 when one does not — a finding, not a
crash. Nothing here boots a guest, pulls an image, reaches the network, calls a
model or spends anything.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
from pathlib import Path
from typing import Any

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core.agentic_v2_containment_readiness import (  # noqa: E402
    NEEDS_THE_PROGRAMS_INSTALLED,
    judge_containment,
    read_this_machine,
)
from core.agentic_v2_kvm_probe import KvmProbe, probe_kvm  # noqa: E402

HARDWARE_ACTUALLY_WORKS = "hardware virtualisation actually works here"
"""The fifth claim, phrased like the four it joins."""

INSTALLABLE_CLAIMS = frozenset({NEEDS_THE_PROGRAMS_INSTALLED})
"""Claims a workflow step can satisfy, so absent ones are not host findings."""


def look(*, probe: KvmProbe | None = None, require_programs: bool = False) -> dict[str, Any]:
    """The four existing readings, the new one, and one verdict over them."""
    answer = judge_containment(read_this_machine(), machine=_what_this_machine_is())
    using_it = probe_kvm() if probe is None else probe

    claims: list[dict[str, Any]] = []
    for requirement in answer.requirements:
        if requirement.claim not in _READINGS_ABOUT_THE_MACHINE:
            continue
        claims.append(
            {
                **requirement.as_dict(),
                "gates": _gates(requirement.claim, require_programs=require_programs),
            }
        )
    claims.append(
        {
            "claim": HARDWARE_ACTUALLY_WORKS,
            "verdict": "met" if using_it.hardware_is_usable_here else "not met",
            "because": using_it.because,
            "gates": True,
        }
    )

    blocked = [one for one in claims if one["gates"] and one["verdict"] != "met"]
    return {
        "schema_version": "1.0",
        "what_this_is": (
            "a capability reading of the machine it ran on. It boots no guest, "
            "pulls no image, calls no model and spends nothing"
        ),
        "machine": _what_this_machine_is(),
        "kernel_release": platform.release(),
        "gated_on_programs_being_installed": require_programs,
        "claims": claims,
        "using_the_device": using_it.as_dict(),
        "notes": list(answer.notes),
        "could_host_a_guest": not blocked,
        "blocked_by": [
            {"claim": one["claim"], "because": one["because"]} for one in blocked
        ],
    }


_READINGS_ABOUT_THE_MACHINE = frozenset(
    {
        "the processor offers hardware virtualisation",
        "this machine can reach hardware virtualisation",
        "the kernel is one Firecracker validates against",
        NEEDS_THE_PROGRAMS_INSTALLED,
    }
)
"""The four claims judged per-machine.

The policy-setting claims :func:`judge_containment` also returns are left out
deliberately. They ask whether the containment rules are *applied* to a running
machine, which cannot be established without one and is not the question here.
Including them would make this refuse on every host, which is a true statement
about containment and a useless one about capability.
"""


def _gates(claim: str, *, require_programs: bool) -> bool:
    if claim in INSTALLABLE_CLAIMS:
        return require_programs
    return True


def _what_this_machine_is() -> str:
    import os

    if os.environ.get("GITHUB_ACTIONS") == "true":
        runner = os.environ.get("RUNNER_NAME", "an unnamed runner")
        image = os.environ.get("ImageOS", "an unrecorded image")
        return f"GitHub Actions runner {runner} ({image})"
    return platform.node() or "this machine"


def render(report: dict[str, Any]) -> list[str]:
    lines = [
        f"machine   {report['machine']}",
        f"kernel    {report['kernel_release']}",
        "",
    ]
    for one in report["claims"]:
        mark = {"met": "yes", "not met": "NO "}.get(one["verdict"], "?  ")
        gated = "" if one["gates"] else "   (not gated on: a step can install this)"
        lines.append(f"  {mark} {one['claim']}{gated}")
        lines.append(f"      {one['because']}")
    lines.append("")
    for note in report["notes"]:
        lines.append(f"  note: {note}")
    if report["notes"]:
        lines.append("")
    if report["could_host_a_guest"]:
        lines.append(
            "This runner could host a guest. The first-boot artefact can be "
            "produced here and consumed here, in one job, without moving "
            "anything between machines."
        )
    else:
        lines.append("This runner could not host a guest. What stopped it:")
        lines.extend(f"  - {one['claim']}: {one['because']}" for one in report["blocked_by"])
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Ask whether this machine could host a Firecracker guest, by "
            "reading it and by using the hardware virtualisation device once."
        )
    )
    parser.add_argument(
        "--require-programs",
        action="store_true",
        help=(
            "also gate on firecracker and jailer being installed. A job asks "
            "for this after its install step, not before it."
        ),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Write the reading as JSON here as well as printing it.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Print the reading as JSON instead of as text.",
    )
    args = parser.parse_args(argv)

    report = look(require_programs=args.require_programs)

    if args.as_json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("Could this machine host a small isolated virtual machine?")
        print("(nothing was booted, nothing was pulled, nothing was spent)")
        print("=" * 74)
        print()
        for line in render(report):
            print(line)

    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(f"\nwritten to {args.report}")

    return 0 if report["could_host_a_guest"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
