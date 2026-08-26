#!/usr/bin/env python3
"""The free check that must pass before Agentic Sandbox V2 stage one spends anything.

Nothing here calls a model, signs in to a cloud account, runs a command, or
spends money. It reads this repository's own code and the stage-one plan file,
works out what each candidate setting could cost at most, and prints every
reason stage one may not start yet.

Usage:

    cd batch-runner
    python scripts/check_agentic_stage_one_ceiling.py
    python scripts/check_agentic_stage_one_ceiling.py --json
    python scripts/check_agentic_stage_one_ceiling.py --plan other.yaml

The exit code is 0 only when nothing is left to fix, which today it never is:
the model conversation stage one is about has not been built, and no amount has
been approved for it. Anything else exits 1, so this is safe to wire into an
automated check.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core.agentic_v2_stage_one_budget import (  # noqa: E402
    STAGE_ONE_PLAN_PATH,
    describe_stage_one_preflight,
    load_stage_one_plan,
    run_stage_one_preflight,
)
from core.execution_envelope_cost import CostAssumptions  # noqa: E402
from core.execution_envelope_preflight import load_plan  # noqa: E402
from core.execution_envelope_tasks import load_task_catalog  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Check for free what Agentic Sandbox V2 stage one could cost, and "
            "whether it may start."
        )
    )
    parser.add_argument("--plan", type=Path, default=STAGE_ONE_PLAN_PATH)
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Print the report as JSON instead of readable text.",
    )
    args = parser.parse_args()

    plan = load_stage_one_plan(args.plan)

    # The written guesses come from the three-place comparison's plan rather
    # than a second copy here, so the two cannot drift apart. Only the
    # tool-result size is different, and that is read from the dispatcher's own
    # code.
    shared_plan_path = BATCH_RUNNER_ROOT / str(
        plan.get("cost", {}).get("assumptions_come_from")
        or "experiments/execution_envelope/advance_check_plan.yaml"
    )
    shared_plan = load_plan(shared_plan_path)
    assumptions = CostAssumptions.from_mapping(
        shared_plan["cost"]["assumptions"]
    )

    result = run_stage_one_preflight(
        plan,
        tasks_by_id=load_task_catalog().by_task_id(),
        assumptions=assumptions,
    )

    if args.as_json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    else:
        print(
            "Agentic Sandbox V2, stage one — free readiness and cost check\n"
            "(no model was called, no command was run, nothing was spent)"
        )
        print("=" * 74)
        print(
            "Stage one is the step where the model chooses its own next action "
            "from\nthe safe tools, with the command-running tool exec_run "
            "still shut.\n"
        )
        for line in describe_stage_one_preflight(result):
            print(line)

    return 0 if result.may_start else 1


if __name__ == "__main__":
    raise SystemExit(main())
