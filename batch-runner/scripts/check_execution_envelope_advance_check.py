#!/usr/bin/env python3
"""The free check that must pass before the run-place comparison spends anything.

Nothing here calls a model, signs in to a cloud account, publishes an image, or
spends money. It reads this repository's own code, the plan file, and the three
experiment settings files, and it prints every reason the comparison may not
start yet.

Usage:

    cd batch-runner
    python scripts/check_execution_envelope_advance_check.py
    python scripts/check_execution_envelope_advance_check.py --json
    python scripts/check_execution_envelope_advance_check.py --plan other.yaml

The exit code is 0 only when every run place being compared can start, no
problem was found, and an approved amount covers the largest possible bill.
Anything else exits 1, so this is safe to wire into an automated check.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core.execution_envelope_preflight import (  # noqa: E402
    describe_input_file_checks,
    describe_preflight,
    load_plan,
    run_envelope_preflight,
)
from core.execution_environment_readiness import (  # noqa: E402
    describe_environment,
    measure_docker_availability,
)

DEFAULT_PLAN = (
    BATCH_RUNNER_ROOT
    / "experiments"
    / "execution_envelope"
    / "advance_check_plan.yaml"
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Check for free whether the five-task advance check of the "
            "run-place comparison may start."
        )
    )
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument(
        "--skip-docker-probe",
        action="store_true",
        help=(
            "Do not look at this machine's Docker service. The container run "
            "place is then reported as not measured rather than as ready."
        ),
    )
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=None,
        help=(
            "A folder holding a copy of the benchmark's files, used to check "
            "the written input fingerprints by reading the files themselves. "
            "Only needed when the pinned revision is not already in the "
            "Hugging Face download cache; nothing is ever downloaded."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Print the report as JSON instead of readable text.",
    )
    args = parser.parse_args()

    plan = load_plan(args.plan)

    docker_daemon: bool | None = None
    docker_image: bool | None = None
    if not args.skip_docker_probe:
        try:
            docker_daemon, docker_image = measure_docker_availability()
        except Exception as error:  # pragma: no cover - machine dependent
            print(
                f"could not look at the Docker service on this machine: {error}",
                file=sys.stderr,
            )

    result = run_envelope_preflight(
        plan,
        root=BATCH_RUNNER_ROOT,
        docker_daemon_available=docker_daemon,
        docker_image_available=docker_image,
        azure_route_profile=os.getenv("AZURE_AI_ROUTE_PROFILE") or None,
        dataset_root=args.dataset_root,
    )

    if args.as_json:
        print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
        return 0 if result.may_start else 1

    print(
        "Run-place comparison, five-task advance check — free readiness check"
    )
    print("(no model was called, no account was signed in to, nothing was spent)")
    print("=" * 74)
    print(
        "Paid model calls approved: "
        + ("yes" if result.readiness.paid_model_calls_approved else "no")
    )
    print(
        "Run places being compared: "
        + ", ".join(result.readiness.compared_environments)
    )
    print()

    for entry in result.readiness.environments:
        taking_part = (
            entry.environment in result.readiness.compared_environments
        )
        marker = "" if taking_part else "  (not part of this comparison)"
        print(f"[{entry.status}] {entry.environment}{marker}")
        print(f"    what it is: {describe_environment(entry.environment)}")
        for note in entry.blockers:
            print(f"    blocked by: {note}")
        print()

    print("Largest possible bill")
    print("-" * 74)
    for line in describe_preflight(result):
        print(f"  {line}")
    print()

    input_file_lines = describe_input_file_checks(result)
    if input_file_lines:
        print("Input files the comparison will read")
        print("-" * 74)
        for line in input_file_lines:
            print(f"  {line}")
        print()

    if result.azure is not None:
        print("Azure resource the deployment must live in")
        print("-" * 74)
        print(
            "  settings name the intended resource: "
            + ("yes" if result.azure.reachable_intent else "no")
        )
        print(f"  account named by the settings: {result.azure.observed_account}")
        print(f"  project named by the settings: {result.azure.observed_project}")
        print()

    if result.all_problems:
        print("Problems that must be fixed before anything starts:")
        for problem in result.all_problems:
            print(f"  - {problem}")
        print()

    if result.readiness.blocked_environments:
        print(
            "These run places cannot start yet. Do not drop them and run the "
            "rest — the comparison is between all of them or it is not this "
            "comparison:"
        )
        for environment in result.readiness.blocked_environments:
            print(
                f"  - {environment} "
                f"({result.readiness.status_of(environment)})"
            )
        print()

    if result.may_start:
        print(
            "Every run place being compared can start, no problem was found, "
            "and an approved amount covers the largest possible bill."
        )
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
