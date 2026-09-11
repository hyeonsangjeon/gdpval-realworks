#!/usr/bin/env python3
"""Ask stage A's one paid question of a real Microsoft Foundry deployment.

This is the only thing in the repository that spends money on Agentic Sandbox
V2, and it spends it once. It runs the free check first and refuses if that
check refuses, reads the task from the pinned dataset and checks the wording is
the one the plan was written against, builds a client through the repository's
one reviewed place for building clients, asks, and writes down what happened.

Usage:

    cd batch-runner
    python scripts/run_agentic_stage_a_probe.py --dry-run
    python scripts/run_agentic_stage_a_probe.py

``--dry-run`` does everything except reach the network: the gate, the dataset,
the wording check, the workspace. It exists so the whole path can be exercised
for free, including in a pull request, and so the only difference between a
free run and a paid one is the calls themselves.

**What is written down.** One row per model call — turn number, deployment
asked for, model that answered, token counts, how much earlier conversation the
call carried, and either a price or an explicit ``price_missing``. Nothing of
what was said: no request body, no reply body, no reasoning, no credential, and
not the benchmark wording the probe was given. The route is recorded as its
endpoint-free fingerprint.

**The exit code answers stage A's question, not "did it work".** Zero means a
real deployment was reached over at least two turns and a later call went out
holding an earlier tool's answer. A model that was reached and chose to do
nothing is a finding and is reported as one, but it does not meet the exit
condition, so it exits 1. Stage A records failures; it does not launder them.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core.agentic_v2_route_check import (  # noqa: E402
    check_route_is_the_one_the_plan_fixed as _check_route,
)
from core.agentic_v2_stage_a_probe import (  # noqa: E402
    PROBE_TOOLS,
    run_stage_a_probe,
)
from core.agentic_v2_stage_one_budget import (  # noqa: E402
    STAGE_ONE_PLAN_PATH,
    load_stage_one_plan,
    run_stage_one_preflight,
)
from core.execution_envelope_cost import (  # noqa: E402
    CostAssumptions,
    load_price_table,
)
from core.execution_envelope_preflight import load_plan  # noqa: E402
from core.execution_envelope_tasks import (  # noqa: E402
    DATASET_REPO_ID,
    DATASET_REVISION,
    load_task_catalog,
)

#: Where the pinned dataset lands once it has been downloaded.
#:
#: The same revision the catalogue was built from and the same one every other
#: figure in the comparison rests on. Reading the wording from a different
#: revision would mean the probe ran a task the plan was not written against,
#: which is why the hash is checked rather than the path trusted.
PINNED_DATASET_PARQUET = (
    Path.home()
    / ".cache"
    / "huggingface"
    / "hub"
    / f"datasets--{DATASET_REPO_ID.replace('/', '--')}"
    / "snapshots"
    / DATASET_REVISION
    / "data"
    / "train-00000-of-00001.parquet"
)


class ProbeRefused(RuntimeError):
    """Raised for every reason the probe must not spend anything."""


def read_task_prompt(task_id: str, *, parquet: Path, expected_sha256: str) -> str:
    """The task's real wording, checked against what the plan was priced on.

    The catalogue holds a hash and a length, never the wording — benchmark
    content is not committed here. So the wording is read from the pinned
    dataset at run time and hashed, and a mismatch stops the run rather than
    being reported afterwards. A prompt that changed is a different task, and a
    different task is not the one that was approved.
    """
    if not parquet.is_file():
        raise ProbeRefused(
            f"the pinned dataset is not at {parquet}. Download revision "
            f"{DATASET_REVISION} of {DATASET_REPO_ID} first, or pass --parquet"
        )

    import pandas

    frame = pandas.read_parquet(parquet, columns=["task_id", "prompt"])
    rows = frame[frame["task_id"] == task_id]
    if len(rows) != 1:
        raise ProbeRefused(
            f"the pinned dataset holds {len(rows)} rows for {task_id}, and the "
            "probe runs exactly one task"
        )

    prompt = str(rows.iloc[0]["prompt"])
    found = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    if found != expected_sha256:
        raise ProbeRefused(
            f"the wording of {task_id} in the dataset does not match what the "
            "catalogue recorded, so this is not the task the plan was priced "
            "against"
        )
    return prompt


def _verdict(plan_path: Path):
    """The same free check the gate runs, run again where the money is."""
    plan = load_stage_one_plan(plan_path)
    shared_plan_path = BATCH_RUNNER_ROOT / str(
        plan.get("cost", {}).get("assumptions_come_from")
        or "experiments/execution_envelope/advance_check_plan.yaml"
    )
    assumptions = CostAssumptions.from_mapping(
        load_plan(shared_plan_path)["cost"]["assumptions"]
    )
    catalog = load_task_catalog()
    result = run_stage_one_preflight(
        plan,
        tasks_by_id=catalog.by_task_id(),
        assumptions=assumptions,
    )
    if result.probe is None or not result.probe.may_start:
        problems = result.probe.problems if result.probe else ["no verdict"]
        raise ProbeRefused(
            "the free check refuses the stage A probe:\n  - "
            + "\n  - ".join(problems)
        )
    return plan, result.probe, catalog


def check_route_is_the_one_the_plan_fixed(route, connection, *, settings=None):
    """Every way the resolved route could differ from what was approved.

    The body moved to :mod:`core.agentic_v2_route_check` when the stage runner
    needed the same check; this stays as the name, because the tests that pin
    stage A's behaviour call it here and what they are pinning has not changed.
    """
    return _check_route(route, connection, settings=settings)


def exit_condition_met(outcome) -> bool:
    """Whether the run answered stage A's question.

    Three things together, because any one alone can be true of a run that
    proved nothing. Reaching a model is only a connection. Two turns could both
    have started from an empty history. Carrying could in principle be reported
    on a run that never got a second turn. Stage A asked whether a real model
    chooses a tool *and then works from what came back*, so all three.

    Deliberately not "did the model do well". A model that was reached, chose a
    tool, and produced something useless meets this; that is a finding about
    the model and stage A exists to collect findings.
    """
    return (
        bool(outcome.reached_a_model)
        and bool(outcome.carried_the_first_result)
        and outcome.turns_taken >= 2
    )


def build_record(*, verdict, said, outcome, fingerprint, workspace) -> dict:
    """What is kept about a paid run.

    Assembled in one named place so what is written down can be checked by a
    test rather than by reading. The task is named and its wording hashed; the
    wording itself is not here, and neither is anything the model said. The
    route appears as its endpoint-free fingerprint.
    """
    return {
        "stage": "agentic-v2-stage-a",
        "task_id": verdict.task_id,
        "dataset_revision": DATASET_REVISION,
        "prompt_sha256": said["prompt_sha256"],
        "route_fingerprint": fingerprint,
        "workspace": str(workspace),
        "approved_maximum_usd": said["approved_maximum_usd"],
        "most_it_could_cost_usd": said["most_it_could_cost_usd"],
        "exit_condition_met": exit_condition_met(outcome),
        "probe": outcome.as_dict(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ask stage A's one paid question of a real deployment."
    )
    parser.add_argument("--plan", type=Path, default=STAGE_ONE_PLAN_PATH)
    parser.add_argument("--parquet", type=Path, default=PINNED_DATASET_PARQUET)
    parser.add_argument(
        "--workspace",
        type=Path,
        default=None,
        help=(
            "An empty directory for the files the model writes. A fresh "
            "temporary one is made if this is left out; an existing one is "
            "never emptied."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Where to write the record. Printed to the screen either way.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Do everything except reach the network. Exits 0 when the paid run "
            "would be allowed to go ahead."
        ),
    )
    args = parser.parse_args()

    try:
        plan, verdict, catalog = _verdict(args.plan)
        task = catalog.by_task_id()[verdict.task_id]
        prompt = read_task_prompt(
            verdict.task_id,
            parquet=args.parquet,
            expected_sha256=task.prompt_sha256,
        )
    except ProbeRefused as refusal:
        print(f"Refused before spending anything.\n\n{refusal}")
        return 1

    deployment = str((plan.get("model") or {}).get("deployment") or "")
    connection = plan.get("azure_connection") or {}
    resource = str(connection.get("account") or "")

    # Money read back from the verdict's own report rather than formatted here,
    # so the figure printed before the spend is character-for-character the one
    # the gate published and not a second rounding of the same number.
    said = dict(verdict.as_dict())
    said["prompt_sha256"] = task.prompt_sha256

    print("Agentic Sandbox V2, stage A — one paid question")
    print("=" * 74)
    print(f"  task           {verdict.task_id}")
    print(f"  prompt         {len(prompt)} characters, wording checked against")
    print(f"                 the catalogue's hash for revision "
          f"{DATASET_REVISION[:12]}")
    print(f"  tools offered  {', '.join(verdict.tools_offered)}")
    print(
        f"  settings       {verdict.tool_calls_per_attempt} tool calls, "
        f"{verdict.max_output_tokens_per_turn} tokens per turn"
    )
    print(
        f"  at most        ${said['most_it_could_cost_usd']} "
        f"(${said['most_running_could_cost_usd']} running, "
        f"${said['most_marking_could_cost_usd']} marking) against the "
        f"${said['approved_maximum_usd']} approved"
    )
    print(f"  deployment     {deployment} at {resource}")
    print(
        f"  route          {connection.get('route_profile')} into project "
        f"{connection.get('project')}"
    )
    print()

    if args.dry_run:
        print(
            "Dry run. Nothing was asked and nothing was spent. Every condition "
            "for the paid run is met."
        )
        return 0

    workspace = (
        args.workspace
        if args.workspace is not None
        else Path(tempfile.mkdtemp(prefix="agentic-v2-stage-a-"))
    )
    print(f"  workspace      {workspace}")

    from core.azure_ai_clients import AzureAIRouteSettings, AzureAIWorkload
    from core.llm_client import create_typed_azure_client

    # Read from the environment the factory reads, so the project checked below
    # is the one the client was actually built from rather than a second
    # reading that could differ from it.
    settings = AzureAIRouteSettings.from_env()

    managed = create_typed_azure_client(
        AzureAIWorkload.INFERENCE,
        deployment,
        settings=settings,
        timeout=float(plan["fixed_settings"]["per_task_timeout_seconds"]),
    )
    try:
        wrong_route = check_route_is_the_one_the_plan_fixed(
            managed.route, connection, settings=settings
        )
        if wrong_route:
            print(
                "Refused after building a client and before asking it "
                "anything.\n\n  - " + "\n  - ".join(wrong_route)
            )
            return 1

        outcome = run_stage_a_probe(
            client=managed.client,
            deployment=deployment,
            resource=resource,
            budget=verdict.budget,
            task_prompt=prompt,
            workspace_root=workspace,
            max_output_tokens_per_turn=verdict.max_output_tokens_per_turn,
            max_tool_calls=verdict.tool_calls_per_attempt,
            max_seconds=float(plan["fixed_settings"]["per_task_timeout_seconds"]),
            prices=load_price_table(),
            tools=PROBE_TOOLS,
        )
        fingerprint = managed.runtime_fingerprint
    finally:
        managed.close()

    met = exit_condition_met(outcome)
    record = build_record(
        verdict=verdict,
        said=said,
        outcome=outcome,
        fingerprint=fingerprint,
        workspace=workspace,
    )
    written = json.dumps(record, indent=2, sort_keys=True)
    if args.output is not None:
        args.output.write_text(written + "\n", encoding="utf-8")
        print(f"  record         {args.output}")
    print()
    print(written)
    print()

    spent = outcome.spent_usd
    print(
        "  spent          "
        + (
            f"${spent}"
            if spent is not None
            else "not reportable — a model answered whose price is not committed"
        )
    )

    # Checked rather than asserted. An assertion disappears under ``-O`` and
    # would crash before the record was read out; going over the approved
    # amount is exactly the thing that must survive to be reported.
    if spent is not None and verdict.approved_maximum_usd is not None:
        if spent > verdict.approved_maximum_usd:
            print(
                f"\nOVERSPENT. ${spent} went out against ${said['approved_maximum_usd']} "
                "approved. The record above is written; read it before running "
                "anything else here."
            )
            return 1

    if met:
        print(
            "\nStage A's exit condition is met: a real deployment was reached, "
            "and a later\ncall went out holding an earlier tool's answer."
        )
        return 0
    print(
        f"\nStage A's exit condition is NOT met. Reached a model: "
        f"{outcome.reached_a_model}. Turns: {outcome.turns_taken}. Carried an "
        f"earlier answer: {outcome.carried_the_first_result}.\nEnded because: "
        f"{outcome.stop_reason}. This is a recorded result, not an error."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
