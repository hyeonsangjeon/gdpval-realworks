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

The exit code is 0 only when every run place being compared can start and no
non-cost problem was found. The default policy also requires an approved amount
to cover the largest possible bill. A plan may instead record an explicit owner
decision to run a bounded measurement and review cost findings afterward.
Anything else exits 1, so this is safe to wire into an automated check.

That default is what a real, paid dispatch must pass, and it is deliberately
fail closed: a checkout with no cloud sign-in cannot satisfy it and must not.
``--exit-on-code-and-contract-problems-only`` changes nothing about what is
checked or printed. It changes which findings decide the exit code, so that a
pull request with no secrets can run this tool and go red for a fault in the
code or the plan rather than for the settings it was never given. What that
mode cannot settle is printed and written down as not checked, never as passed,
and it never reports that a run may start.
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
    COST_POLICY_RECORD_ONLY,
    describe_input_file_checks,
    describe_preflight,
    load_plan,
    run_envelope_preflight,
)
from core.execution_environment_readiness import (  # noqa: E402
    STATUS_CAN_RUN_REAL_EXPERIMENT,
    describe_environment,
    measure_docker_availability,
)

DEFAULT_PLAN = (
    BATCH_RUNNER_ROOT
    / "experiments"
    / "execution_envelope"
    / "advance_check_plan.yaml"
)

#: What the mode below reports as not checked rather than as passed.
#:
#: Both entries name a list the result already keeps apart from the rest, so
#: the split is made by *which check produced a line* and never by reading the
#: line's wording. Rewording a message moves nothing here; deleting one of
#: these lists breaks the arithmetic below rather than quietly widening what
#: counts as a pass.
STATUS_NOT_CHECKED = "not_checked"


def split_by_what_a_checkout_can_settle(
    result,
) -> tuple[list[str], list[dict]]:
    """Separate faults in the code and the plan from missing local evidence.

    A fault in the code or the plan reads the same on every machine. Whether
    ``FOUNDRY_PROJECT_ENDPOINT`` is set does not: it says what this machine was
    given, and a checkout that was deliberately given nothing is not entitled
    to a verdict on it either way. Reporting the second kind as a failure would
    make an automated check red on every pull request forever, and a check
    nobody can ever get green is a check nobody reads.

    The other direction is the one worth guarding, so it is guarded: every
    problem the check found comes back in exactly one of the two lists --
    the second is built as the complement of the first, so nothing can fall
    between them -- and "not checked" is written down as its own answer rather
    than folded into the pass. What that construction cannot promise is that
    the two lists being set aside are still the ones feeding the verdict, and
    that is checked below.

    Two findings inside the Azure diagnosis really are settleable offline — a
    plan pinning a route profile the run place does not know, and an identity
    setting the plan has nothing to compare against. They leave this job's exit
    code, and they are not thereby unguarded: the suite that runs on every pull
    request holds both, in
    ``tests/test_envelope_azure_applies_the_run_rules.py``
    (``test_a_plan_pinning_a_profile_the_run_does_not_know_is_refused`` and
    ``test_every_identity_the_run_requires_has_something_to_compare_against``).
    Splitting them out here instead would mean this script deciding which of
    that module's sentences came from the environment, by their wording — which
    is the fragile thing this function is written to avoid.
    """
    could_not_look_at_the_bytes = list(result.missing_input_file_problems)
    read_off_this_machine = (
        list(result.azure.problems) if result.azure is not None else []
    )

    set_aside = set(could_not_look_at_the_bytes) | set(read_off_this_machine)
    code_and_contract = [
        problem for problem in result.all_problems if problem not in set_aside
    ]

    # Every problem now appears in exactly one of the two lists, because the
    # second is defined as the complement of the first. What is *not*
    # guaranteed is that the two lists being set aside still feed the verdict
    # at all: if the aggregate stopped collecting one of them, this would go on
    # quietly reporting its contents as "not checked here" while the check no
    # longer counts them as problems, and the summary would describe a
    # diagnosis nothing is running. That is the direction that can break, so
    # that is the direction guarded.
    counted = set(result.all_problems)
    orphaned = sorted(problem for problem in set_aside if problem not in counted)
    if orphaned:
        raise AssertionError(
            "these are being set aside as not checked here, but the check does "
            "not count them among the problems it found, so this split is "
            "reading a list that no longer feeds the verdict: "
            + "; ".join(orphaned)
        )

    not_checked: list[dict] = []
    if result.azure is not None:
        not_checked.append(
            {
                "what": "the Azure sign-in settings, and the permission behind them",
                "status": STATUS_NOT_CHECKED,
                "why_this_machine_cannot_say": (
                    "this check never signs in, so it can only read the "
                    "settings this machine was handed. A machine handed none "
                    "has not disproved the settings; it has not seen them."
                ),
                "what_would_settle_it": (
                    "a real dispatch, where the settings are present and the "
                    "project-scoped route is actually asked. That path keeps "
                    "the fail-closed default policy of this same tool."
                ),
                "notes": read_off_this_machine,
            }
        )
    not_checked.append(
        {
            "what": "the bytes behind each written input fingerprint",
            "status": STATUS_NOT_CHECKED,
            "why_this_machine_cannot_say": (
                "a fingerprint can only be compared against a file that is "
                "here. Most of this dataset's folders are not named after "
                "their file's contents, so a written value that differs from "
                "a folder name is not evidence of anything."
            ),
            "what_would_settle_it": (
                "fetching the pinned revision, which costs nothing, and "
                "running this again"
            ),
            "notes": could_not_look_at_the_bytes,
        }
    )

    could_not_be_confirmed = [
        entry
        for entry in result.readiness.environments
        if entry.environment in result.readiness.compared_environments
        and entry.status != STATUS_CAN_RUN_REAL_EXPERIMENT
    ]
    if could_not_be_confirmed:
        not_checked.append(
            {
                "what": "whether each run place really answers",
                "status": STATUS_NOT_CHECKED,
                "why_this_machine_cannot_say": (
                    "nothing here calls a model, starts a container, or signs "
                    "in, so no run place has been seen to produce anything"
                ),
                "what_would_settle_it": (
                    "the paid run itself, which is what these states are the "
                    "precondition for"
                ),
                # Carried from the readiness grades rather than the problem
                # list, so these are extra reporting and take no part in the
                # arithmetic above.
                "notes": [
                    f"{entry.environment}: {entry.status}"
                    + ("" if not entry.blockers else " — " + "; ".join(entry.blockers))
                    for entry in could_not_be_confirmed
                ],
            }
        )

    return code_and_contract, not_checked


def _offline_verdict(
    code_and_contract: list[str],
    not_checked: list[dict],
    *,
    result,
) -> dict:
    """The block written beside the full report when the exit code is narrowed.

    ``run_may_start`` repeats the tool's real answer rather than restating the
    narrowed one, because the two are different questions and a reader of this
    file must not be able to mistake the second for the first.
    """
    return {
        "what_this_is": (
            "the part of the free check that a checkout with no cloud sign-in "
            "can settle. It decided this run's exit code."
        ),
        "problems": list(code_and_contract),
        "problem_count": len(code_and_contract),
        "not_checked_here": not_checked,
        "run_may_start": result.may_start,
        "no_problem_here_is_not_permission_to_start": True,
        "why_not": (
            "nothing here signed in, called a model, or started a container. "
            "The policy a real dispatch is held to is this same tool's "
            "default, which is fail closed and which this run did not pass."
        ),
        "nothing_was_spent": True,
    }


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
        "--exit-on-code-and-contract-problems-only",
        action="store_true",
        dest="code_and_contract_only",
        help=(
            "Decide the exit code from the faults that read the same on every "
            "machine, and report what this machine could not see as not "
            "checked. For an automated check on a branch that is given no "
            "secrets. It never reports that a run may start, and it is not "
            "the policy a real dispatch is held to."
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

    result = run_envelope_preflight(
        plan,
        root=BATCH_RUNNER_ROOT,
        docker_daemon_available=docker_daemon,
        docker_image_available=docker_image,
        azure_route_profile=os.getenv("AZURE_AI_ROUTE_PROFILE") or None,
        azure_route_served=azure_route_served,
        dataset_root=args.dataset_root,
    )

    if args.as_json:
        payload = result.as_dict()
        if args.code_and_contract_only:
            # Added beside the full report rather than replacing any of it. A
            # reader of this file still gets every run place's state, every
            # uncontrolled difference, and may_start unchanged; this block only
            # says which of those findings decided the exit code.
            payload["offline_verdict"] = _offline_verdict(
                *split_by_what_a_checkout_can_settle(result), result=result
            )
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        if args.code_and_contract_only:
            return 0 if not payload["offline_verdict"]["problems"] else 1
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

    print("Cost estimate and unresolved measurements")
    print("-" * 74)
    for line in describe_preflight(result):
        print(f"  {line}")
    print()

    if result.cost_findings:
        label = (
            "Cost findings recorded for review (they do not block this run):"
            if result.cost_policy == COST_POLICY_RECORD_ONLY
            else "Cost findings that must be fixed before anything starts:"
        )
        print(label)
        for finding in result.cost_findings:
            print(f"  - {finding}")
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

    if args.code_and_contract_only:
        code_and_contract, not_checked = split_by_what_a_checkout_can_settle(
            result
        )
        print("What a checkout with no cloud sign-in could settle")
        print("-" * 74)
        if code_and_contract:
            print(
                f"  {len(code_and_contract)} fault(s) in the code or the plan. "
                "These read the same on every machine:"
            )
            for problem in code_and_contract:
                print(f"    - {problem}")
        else:
            print("  No fault in the code or the plan was found.")
        print()
        print("  Not checked here (not the same as checked and passed):")
        for entry in not_checked:
            print(f"    - {entry['what']}")
            print(f"        {entry['why_this_machine_cannot_say']}")
            for note in entry["notes"]:
                print(f"        · {note}")
        print()
        print(
            "  This is not permission to start a paid run. Nothing here "
            "signed in, called a model, or started a container, and the "
            "policy a real dispatch is held to is this tool's default — "
            f"which this run did not pass (may_start={result.may_start})."
        )
        return 0 if not code_and_contract else 1

    if result.may_start:
        if result.cost_policy == COST_POLICY_RECORD_ONLY:
            print(
                "Every run place being compared can start and no non-cost "
                "problem was found. Cost findings were recorded for review."
            )
        else:
            print(
                "Every run place being compared can start, no problem was "
                "found, and an approved amount covers the largest possible "
                "bill."
            )
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
