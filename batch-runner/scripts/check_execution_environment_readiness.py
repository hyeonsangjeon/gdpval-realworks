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

import yaml

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core.execution_environment_readiness import (  # noqa: E402
    COMPARISON_SAME_GENERATED_CODE,
    ModelRunConditions,
    build_readiness_report,
    describe_environment,
    measure_docker_availability,
)


def _load_plan(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    loaded = yaml.safe_load(text)
    if not isinstance(loaded, dict):
        raise ValueError("the plan file must contain a mapping at the top level")
    return loaded


def _conditions_from_plan(plan: dict) -> dict[str, ModelRunConditions]:
    raw = plan.get("model_run_conditions")
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError("model_run_conditions must be a mapping")
    shared = raw.get("shared")
    per_environment = raw.get("by_environment")
    if not isinstance(per_environment, dict):
        raise ValueError("model_run_conditions.by_environment must be a mapping")
    resolved: dict[str, ModelRunConditions] = {}
    for environment, override in per_environment.items():
        merged = dict(shared or {})
        merged.update(dict(override or {}))
        resolved[str(environment)] = ModelRunConditions.from_mapping(merged)
    return resolved


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
        "--json",
        action="store_true",
        dest="as_json",
        help="Print the report as JSON instead of readable text.",
    )
    args = parser.parse_args()

    plan: dict = {}
    if args.plan is not None:
        plan = _load_plan(args.plan)

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
        _conditions_from_plan(plan) if "model_run_conditions" in plan else None
    )

    report = build_readiness_report(
        conditions_by_environment=conditions,
        comparison=plan.get("comparison", COMPARISON_SAME_GENERATED_CODE),
        run_size_plan=plan.get("run_sizes"),
        scoreboards=plan.get("scoreboards"),
        docker_daemon_available=docker_daemon,
        docker_image_available=docker_image,
        azure_route_profile=os.getenv("AZURE_AI_ROUTE_PROFILE") or None,
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
