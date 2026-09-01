#!/usr/bin/env python3
"""Check, without spending any money, whether the run-place comparison may start.

This tool never calls a model, never signs in to a cloud account, and never
publishes a container image. It reads this repository's own code plus a plan
file the operator wrote, and it prints every reason the comparison cannot start
yet.

Usage:

    python scripts/check_execution_environment_readiness.py
    python scripts/check_execution_environment_readiness.py --plan plan.yaml
    python scripts/check_execution_environment_readiness.py --json

The exit code is 0 only when every run place being compared can start and no
problem was found. A blocked run place or any problem exits 1, so this is safe
to wire into an automated check.
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

from core.execution_environment_readiness import (  # noqa: E402
    COMPARISON_SAME_GENERATED_CODE,
    build_readiness_report,
    describe_environment,
    measure_docker_availability,
)

# Read the plan with the reader the rest of the repository reads it with.
#
# This file used to carry its own private pair of these two functions. They
# started as copies of the ones here, and then only one copy was maintained:
# f728b24 made `resource` a required run condition and taught
# core.execution_envelope_preflight.conditions_from_plan to fill it in from the
# azure_connection block, exactly as the plan asks in the comment standing
# where the field would otherwise be written. The copy in this file was left
# behind, so the documented command
#
#     python scripts/check_execution_environment_readiness.py \
#         --plan experiments/execution_envelope/advance_check_plan.yaml
#
# stopped on "model run conditions are missing required entries: resource"
# before a single readiness rule was reached. Thirteen test files kept driving
# the maintained copy against that same plan and stayed green, so the free gate
# standing in front of a paid run was broken for weeks with nothing to say so.
#
# Importing rather than re-fixing is the point: a third behaviour would be a
# third thing to keep in step. The maintained copy also knows something this
# one never did — a run place whose model does not come from the pinned
# Microsoft Foundry resource has to name its own, because there is nothing
# there for it to inherit.
from core.execution_envelope_preflight import (  # noqa: E402
    conditions_from_plan,
    load_plan,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Check for free whether one GPT model can be compared across the "
            "five run places."
        )
    )
    parser.add_argument(
        "--plan",
        type=Path,
        default=None,
        help=(
            "A YAML or JSON file holding the fixed model run conditions, the "
            "5/30/220 task stages, and the two separate scoreboards."
        ),
    )
    parser.add_argument(
        "--skip-docker-probe",
        action="store_true",
        help=(
            "Do not look at this machine's Docker service. The container run "
            "place is then reported as not measured rather than as ready."
        ),
    )
    parser.add_argument(
        "--azure-route-served",
        choices=("yes", "no"),
        default=None,
        help=(
            "Whether somebody asked the project-scoped Azure route and it "
            "answered this sign-in. There is no probe for this, so leaving it "
            "out reports the Azure run place as not measured rather than as "
            "ready. AZURE_AI_ROUTE_PROFILE is not an answer to this question: "
            "it names the route to use, and a real dispatch is required to set "
            "it before anything has been asked."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Print the report as JSON instead of readable text.",
    )
    args = parser.parse_args()

    plan: dict = {}
    if args.plan is not None:
        plan = load_plan(args.plan)

    azure_route_served: bool | None = None
    if args.azure_route_served is not None:
        azure_route_served = args.azure_route_served == "yes"

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

    # A plan that names the key but lists no run place is a mistake worth
    # reporting, so it is passed through rather than turned into "no plan".
    conditions = (
        conditions_from_plan(plan) if "model_run_conditions" in plan else None
    )

    report = build_readiness_report(
        conditions_by_environment=conditions,
        comparison=plan.get("comparison", COMPARISON_SAME_GENERATED_CODE),
        run_size_plan=plan.get("run_sizes"),
        scoreboards=plan.get("scoreboards"),
        docker_daemon_available=docker_daemon,
        docker_image_available=docker_image,
        azure_route_profile=os.getenv("AZURE_AI_ROUTE_PROFILE") or None,
        azure_route_served=azure_route_served,
        docker_run_setting=(plan.get("container") or {}).get("use_docker"),
    )

    if args.as_json:
        print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
        return 0 if report.ready else 1

    print("Run-place readiness check (no model was called, nothing was spent)")
    print("=" * 72)
    print(
        "Paid model calls approved: "
        + ("yes" if report.paid_model_calls_approved else "no")
    )
    print(
        "Run places being compared: " + ", ".join(report.compared_environments)
    )
    print()
    for entry in report.environments:
        print(f"[{entry.status}] {entry.environment}")
        print(f"    what it is: {describe_environment(entry.environment)}")
        for note in entry.evidence:
            print(f"    evidence:   {note}")
        for note in entry.blockers:
            print(f"    blocked by: {note}")
        print()

    if report.problems:
        print("Problems that must be fixed before the comparison starts:")
        for problem in report.problems:
            print(f"  - {problem}")
        print()

    if report.blocked_environments:
        print(
            "These run places cannot start yet, so the comparison must not "
            "begin. Do not drop them and run the rest:"
        )
        for environment in report.blocked_environments:
            print(f"  - {environment} ({report.status_of(environment)})")
        return 1

    if report.problems:
        return 1

    print("Every run place being compared can start, and no problem was found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
