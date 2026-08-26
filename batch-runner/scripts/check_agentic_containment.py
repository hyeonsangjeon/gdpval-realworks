#!/usr/bin/env python3
"""The free check for whether Agentic Sandbox V2's containment exists anywhere.

Nothing here calls a model, signs in to a cloud account, runs a command,
installs anything, or spends money. It reads the machine it is running on, the
repository's own workflow files, and two findings recorded about machines that
cannot be read from here, and prints whether the containment the substrate
manifest requires is available on any of them.

Usage:

    cd batch-runner
    python scripts/check_agentic_containment.py
    python scripts/check_agentic_containment.py --json

The exit code is 0 only when the required containment is available on some
machine in play *and* every machine the workflows ask for has an answer
recorded. Today neither holds for the first reason: this machine cannot reach
hardware virtualisation and runs a kernel below the oldest Firecracker
validates, GitHub-hosted runners do not officially support running a virtual
machine inside them, and the self-hosted machine the one workflow asks for has
never been registered. Anything else exits 1, so this is safe to wire into an
automated check — including the case where somebody adds a workflow that runs
somewhere nobody has answered the question for.

Stage three of the specification — letting a model's chosen commands really run
— is what this answers a question for. It switches nothing on and removes no
refusal.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core.agentic_v2_containment_readiness import (  # noqa: E402
    containment_answer_everywhere,
    describe_containment,
)

DEFAULT_WORKFLOWS_DIRECTORY = BATCH_RUNNER_ROOT.parent / ".github" / "workflows"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Check for free whether the containment Agentic Sandbox V2 "
            "requires is available on any machine this repository runs on."
        )
    )
    parser.add_argument(
        "--workflows",
        type=Path,
        default=DEFAULT_WORKFLOWS_DIRECTORY,
        help="Where the workflow files are, to see which machines are asked for.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Print the report as JSON instead of readable text.",
    )
    args = parser.parse_args()

    report = containment_answer_everywhere(workflows_directory=args.workflows)

    if args.as_json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(
            "Agentic Sandbox V2 — is the containment it requires available "
            "anywhere?\n"
            "(nothing was called, nothing was run, nothing was spent)"
        )
        print("=" * 74)
        print()
        for line in describe_containment(report):
            print(line)

    return (
        0
        if report["available_on_any_machine_in_play"]
        and report["every_machine_in_play_has_an_answer"]
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
