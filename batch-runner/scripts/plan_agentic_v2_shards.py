#!/usr/bin/env python3
"""How many jobs one stage has to be run across, and what to pass to each.

Printed as a JSON array of ``"index/total"`` strings, because that is what a
GitHub Actions matrix can be built from with ``fromJSON`` and what
``run_agentic_v2_stage.py --shard`` takes. One value, read by both.

The reason this is a script and not four lines of Python in a heredoc inside the
workflow is that the heredoc version cannot be run anywhere except a dispatch.
The number it produces decides whether a paid run finishes or is killed at the
six hour mark with the tasks it was in the middle of lost, and that is not a
number to find out about from a workflow log.

Both inputs are read rather than written here:

* the per-task ceiling comes from the plan, so the split cannot be sized against
  a timeout the run is not actually using;
* the cohort size comes from the committed catalogue by way of the
  pre-registration, so it cannot be sized against a stage that is a different
  size from the one that will run.

The job limit is the one thing written down here, because it belongs to GitHub
rather than to this project. It is six hours: the documented maximum for a job
on a GitHub-hosted runner. A job that asks for more is not refused at dispatch;
it is killed when it gets there.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core.agentic_v2_preregistration import ESCALATION, STAGE_SIZES  # noqa: E402
from core.agentic_v2_sharding import how_many_shards_fit  # noqa: E402
from core.agentic_v2_stage_one_budget import load_stage_one_plan  # noqa: E402

#: The documented ceiling on one job on a GitHub-hosted runner. Not configurable
#: and not negotiable: a job that runs past it is killed where it stands, and the
#: task it was in the middle of is the one a resume has to pay for twice.
GITHUB_JOB_LIMIT_SECONDS = 6 * 60 * 60


def shard_plan(stage: str) -> dict[str, object]:
    if stage not in STAGE_SIZES:
        raise SystemExit(
            f"{stage!r} is not a registered stage. The three are: "
            + ", ".join(ESCALATION)
        )

    per_task = float(load_stage_one_plan()["fixed_settings"]["per_task_timeout_seconds"])
    size = STAGE_SIZES[stage]
    pieces = how_many_shards_fit(
        cohort_size=size,
        per_task_timeout_seconds=per_task,
        job_limit_seconds=GITHUB_JOB_LIMIT_SECONDS,
    )
    biggest = -(-size // pieces)
    return {
        "stage": stage,
        "cohort_size": size,
        "shards": [f"{index}/{pieces}" for index in range(1, pieces + 1)],
        "per_task_timeout_seconds": per_task,
        "worst_case_hours_per_shard": round(biggest * per_task / 3600, 1),
        "worst_case_hours_if_run_as_one": round(size * per_task / 3600, 1),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True, choices=list(ESCALATION))
    parser.add_argument(
        "--explain",
        action="store_true",
        help="print the whole plan as an object instead of just the matrix list",
    )
    args = parser.parse_args(argv)

    plan = shard_plan(args.stage)
    if args.explain:
        print(json.dumps(plan, indent=2))
    else:
        # Compact and on one line: this is read by `$(...)` into a workflow
        # output, and an output with a newline in it is a parse error there.
        print(json.dumps(plan["shards"], separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
