#!/usr/bin/env python3
"""Decide whether a set of finished shards may be called the stage.

Two jobs, because they are asked at two different moments and the wrong one at
the wrong moment is useless.

``--before-starting`` is asked by a shard that has not run yet, against whatever
its siblings have already uploaded. It refuses only on the halts that are facts
about the whole run -- a wrong model name, a broken seal, an open gate, a budget
already past -- and exits 0 on everything else. It cannot stop a shard that is
already running; what it stops is the next wave. At ``max-parallel: 4`` that is
the difference between four shards' spend and seventeen.

``--collect`` is asked once, after every shard has reported. It is the check the
workflow comment has always said earns the sentence "the stage ran", and until
now nothing invoked it: every task covered exactly once, and no shard stopped on
a rule that puts the others in question.

Neither needs the dataset. The cohort comes from the committed catalogue, which
is the same list the run was bound to, so this can be answered in a bookkeeping
job with nothing fetched.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core.agentic_v2_preregistration import (  # noqa: E402
    ESCALATION,
    STAGE_SIZES,
    cohorts,
)
from core.agentic_v2_shard_collection import (  # noqa: E402
    ShardRecordUnreadable,
    read_shard_records,
    siblings_that_stopped_the_run,
    stage_problems,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--records",
        type=Path,
        required=True,
        help=(
            "directory holding one folder per shard, each with a "
            "run_record.json. Searched recursively, so the layout "
            "actions/download-artifact produces works unchanged."
        ),
    )
    parser.add_argument("--stage", required=True, choices=sorted(STAGE_SIZES))
    what = parser.add_mutually_exclusive_group(required=True)
    what.add_argument(
        "--before-starting",
        action="store_true",
        help=(
            "refuse to start this shard if a sibling already halted on "
            "something that is true of the whole run"
        ),
    )
    what.add_argument(
        "--collect",
        action="store_true",
        help="say whether the finished shards are the stage",
    )
    args = parser.parse_args(argv)

    if args.stage not in ESCALATION:  # pragma: no cover - argparse covers it
        print(f"{args.stage!r} is not a registered stage", file=sys.stderr)
        return 2

    # A missing directory is not the same as an empty one and the two must not
    # be answered alike. Before starting, no siblings have uploaded anything yet
    # on the first wave, and that is the normal case; collecting, a missing
    # directory means the artifacts did not arrive and the stage cannot be
    # spoken for at all.
    if not args.records.is_dir():
        if args.before_starting:
            print(
                f"No sibling records under {args.records}. Nothing has halted "
                "that this shard can see, so it starts."
            )
            return 0
        print(
            f"{args.records} does not exist, so no shard record was found and "
            "nothing here can say what ran.",
            file=sys.stderr,
        )
        return 1

    try:
        records = read_shard_records(args.records)
    except ShardRecordUnreadable as unreadable:
        # Never a pass. A record this code cannot read is a record nobody has
        # checked, and the cheapest wrong answer here is the reassuring one.
        print(f"A shard record could not be read: {unreadable}", file=sys.stderr)
        return 1

    if args.before_starting:
        reasons = siblings_that_stopped_the_run(records)
        if not reasons:
            print(
                f"{len(records)} sibling record(s) read, none halted on "
                "anything that is true of the whole run. Starting."
            )
            return 0
        print("This shard will not start.\n", file=sys.stderr)
        for reason in reasons:
            print(f"  - {reason}", file=sys.stderr)
        print(
            "\nThese are the stop rules whose trigger is shared by every "
            "shard, so running this one would add tasks to a record the run "
            "cannot support. Shards already in flight are not stopped by "
            "this: they were charged for their turns before it could be "
            "asked.",
            file=sys.stderr,
        )
        return 1

    problems = stage_problems(records, task_ids=cohorts()[args.stage])
    if problems:
        print(f"{args.stage} has not run.\n", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    covered = sum(len(record["shard"]["task_ids"]) for _, record in records)
    print(
        f"{args.stage} ran: {len(records)} shards covered {covered} tasks, "
        "each exactly once, and none stopped early."
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
