#!/usr/bin/env python3
"""Run one pre-registered Agentic Sandbox V2 stage against a real deployment.

Everything this needs has existed separately for a while. The conversation loop
asks a model and runs what it asks for; the runner admits a backend and writes a
verified record; the driver walks a fixed manifest, resumes, collects files and
stops when it should; the binding turns a sealed cohort into tasks and refuses a
prompt that drifted; the budget module decides whether anything may be spent at
all. This is the one place that puts them in a line and turns the handle.

    cd batch-runner
    python scripts/run_agentic_v2_stage.py --stage advance_check_5 --dry-run
    python scripts/run_agentic_v2_stage.py --stage advance_check_5

``--dry-run`` does everything except reach the network: the free check, the
binding, the ceilings, the workspace, the journal path. The only difference
between a free run and a paid one is the calls themselves, which is what makes
the free run worth anything.

**What this is, stated before anyone reads a number off it.** The backend is
:class:`~core.agentic_v2_fixture_backend.AgenticV2FixtureBackend`. The model is
real, the tool choices are real, the files it writes are real files on this
disk, and the deliverables collected at the end are the ones it wrote. What is
*not* real is the isolation: no guest boots, and ``exec_run`` answers
``capability_unavailable`` to everything. That is not a shortcut taken here —
the pre-registration fixes ``exec_run_open: false`` for stage one, so a run that
opened it would be a different experiment from the one that was registered. It
does mean a sentence like "Agentic Sandbox V2 completed the stage" would be
wrong, and :func:`environment_note` is written into the record so that the
weaker true sentence travels with the results instead of having to be
remembered.

**Three milestones, deliberately not merged.** *The environment is ready* is not
*the tasks ran* is not *the results are marked*. This script can only report the
middle one. It writes no grade, and the ledger it writes to buckets everything
as problem-solving cost, so marking cannot be paid for out of this even by
accident.

**What is written down.** The driver's own journal, one row per task, the
collected deliverables, and a cost receipt per task. Never a prompt, never a
reply, never a credential — same rule as the stage A probe, for the same reason.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core.agentic_v2_conversation_runner import (  # noqa: E402
    PerTaskCeilings,
    RunWideCeilings,
    TaskConversations,
    build_runner_factory,
    # Imported rather than worked out here. The pre-registration promises these
    # same ceilings before the run starts, so a second copy of the arithmetic
    # would let the promise and the enforcement drift apart silently.
    ceilings_from,
    model_turns_of,
)
from core.agentic_v2_cost_binding import bind_run_to_ledger  # noqa: E402
from core.agentic_v2_fixture_backend import AgenticV2FixtureBackend  # noqa: E402
from core.agentic_v2_manifest_binding import (  # noqa: E402
    ManifestRefused,
    bind_stage,
    binding_record,
)
from core.agentic_v2_preregistration import STAGE_SIZES  # noqa: E402
from core.agentic_v2_route_check import (  # noqa: E402
    check_route_is_the_one_the_plan_fixed,
)
from core.agentic_v2_run_driver import DriverRefused, run_manifest  # noqa: E402
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
    catalog_sha256,
    load_task_catalog,
)


class StageRefused(RuntimeError):
    """Raised for every reason the stage must not start."""


#: Where the pinned dataset lands once it has been downloaded.
#:
#: The same revision the catalogue was built from, read the same way the stage A
#: probe reads it. ``dataset_tasks_from_snapshot`` would read whatever revision
#: happens to be bootstrapped into ``data/gdpval-local``, and the whole point of
#: the binding is that the prompts are the ones the seal was computed over — so
#: the revision is pinned here rather than taken on trust and checked afterwards.
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


@dataclass(frozen=True)
class DatasetRow:
    """One row, carrying only what the binding is allowed to see.

    Built by hand rather than by handing the parquet frame over, because the
    frame also holds ``deliverable_text`` and ``deliverable_files`` — the
    expert's own answer. :data:`ANSWER_FIELDS_THAT_MUST_NOT_TRAVEL` keeps those
    out of ``TaskToRun``, and this keeps them out of what the binding is given
    in the first place.
    """

    task_id: str
    prompt: str
    sector: str
    occupation: str
    reference_files: tuple[str, ...]


def read_pinned_dataset(parquet: Path) -> list[DatasetRow]:
    """The pinned revision's rows, with the answer columns never read."""
    if not parquet.is_file():
        raise StageRefused(
            f"the pinned dataset is not at {parquet}. Download revision "
            f"{DATASET_REVISION} of {DATASET_REPO_ID} first, or pass --parquet"
        )
    import pandas

    frame = pandas.read_parquet(
        parquet,
        columns=["task_id", "prompt", "sector", "occupation", "reference_files"],
    )
    return [
        DatasetRow(
            task_id=str(row.task_id),
            prompt=str(row.prompt),
            sector=str(row.sector),
            occupation=str(row.occupation),
            # ``or ()`` would be wrong here: the column holds a numpy array, and
            # an array with more than one element raises rather than being
            # truthy. Asked whether it is None instead.
            reference_files=tuple(
                str(name)
                for name in (
                    () if row.reference_files is None else row.reference_files
                )
            ),
        )
        for row in frame.itertuples()
    ]


#: What the fixture backend is, in words that survive being quoted.
#:
#: Written into the run record rather than only into this file's docstring,
#: because the record is what a reader three months from now will have. A run
#: whose isolation was a fixture and whose record does not say so is a result
#: that will eventually be described as something it was not.
def environment_note(profile: dict) -> dict:
    return {
        "backend": "AgenticV2FixtureBackend",
        "guest_booted": False,
        "exec_run_open": False,
        "policy_profile_id": profile.get("policy_profile_id"),
        "what_was_real": [
            "the model, the deployment and the charge for every call",
            "the tool choices the model made, turn by turn",
            "the files workspace_apply wrote, and the deliverables collected",
            "the per-task ceilings, which stopped tasks that reached them",
        ],
        "what_was_not_real": [
            "the isolation: no guest booted and nothing ran in one",
            "exec_run, which answered capability_unavailable to everything",
        ],
        "so_the_honest_sentence_is": (
            "a real model drove a real tool loop and wrote real files, with "
            "the V2 tool contract enforced and its isolation not exercised. "
            "This is not evidence that the sandbox contains anything."
        ),
    }


def verdict_for(plan_path: Path):
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
        plan, tasks_by_id=catalog.by_task_id(), assumptions=assumptions
    )
    if not result.may_start:
        raise StageRefused(
            "the free check refuses this stage:\n  - "
            + "\n  - ".join(result.problems)
        )
    if result.chosen is None:
        raise StageRefused(
            "the free check passed but the plan names no chosen settings, so "
            "there is no ceiling to hold a task to. Fill cost.chosen_settings "
            "in the plan before running anything"
        )
    return plan, result, catalog


def check_the_plan_priced_this_stage(plan: dict, bound) -> list[str]:
    """Whether the amounts approved describe the run about to happen.

    The free check prices the tasks the plan pins, which is the five-task
    cohort. Its figures are per-run, not per-task, so a thirty-task or
    two-hundred-and-twenty-task stage run under them would go out against an
    approval worked out for a run forty-four times smaller — and the printed
    line would say it was within budget, because the arithmetic it came from
    never saw the larger cohort.

    Caught here rather than by scaling the figure, because scaling would be
    this script deciding what a bigger run costs. Prices come from the plan.
    When stage thirty and stage two-twenty are to be run, the plan gains their
    task ids and their two approved amounts, and this stops refusing them.
    """
    priced = {str(task_id) for task_id in (plan.get("task_ids") or ())}
    binding = set(bound.task_ids)
    if priced == binding:
        return []
    return [
        f"the plan prices {len(priced)} tasks and this stage binds "
        f"{len(binding)}, so the approved amounts do not describe this run. "
        "They are whole-run figures, not per-task ones, and running "
        f"{len(binding)} tasks under them would spend roughly "
        f"{len(binding) / max(len(priced), 1):.0f} times what was approved. "
        "Price this cohort in the plan first."
    ]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run one pre-registered Agentic Sandbox V2 stage."
    )
    parser.add_argument(
        "--stage",
        required=True,
        choices=sorted(STAGE_SIZES),
        help="Which pre-registered cohort to run.",
    )
    parser.add_argument("--plan", type=Path, default=STAGE_ONE_PLAN_PATH)
    parser.add_argument("--parquet", type=Path, default=PINNED_DATASET_PARQUET)
    parser.add_argument(
        "--run-id",
        default=None,
        help=(
            "Names the journal's run and namespaces every ledger call id. "
            "Reuse it to resume; a fresh one starts over."
        ),
    )
    parser.add_argument(
        "--into",
        type=Path,
        default=None,
        help=(
            "Where deliverables, the journal and the record are written. A "
            "fresh temporary directory is made if this is left out."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Do everything except reach the network. Exits 0 when the paid "
            "run would be allowed to go ahead."
        ),
    )
    args = parser.parse_args()

    try:
        plan, verdict, catalog = verdict_for(args.plan)
        bound = bind_stage(
            args.stage,
            dataset_tasks=read_pinned_dataset(args.parquet),
            catalog=catalog,
            catalog_digest=catalog_sha256(),
        )
        unpriced = check_the_plan_priced_this_stage(plan, bound)
        if unpriced:
            raise StageRefused("\n  - ".join(["this stage is not priced:", *unpriced]))
    except (StageRefused, ManifestRefused) as refusal:
        print(f"Refused before spending anything.\n\n{refusal}")
        return 1

    chosen = verdict.chosen
    ceilings = ceilings_from(plan, chosen)
    connection = plan.get("azure_connection") or {}
    deployment = str((plan.get("model") or {}).get("deployment") or "")
    resource = str(connection.get("account") or "")
    profile = {
        "tool_contract_version": "2.0",
        "policy_profile_id": str(
            plan.get("policy_profile_id") or "offline-full-v1"
        ),
        "foundation_only": True,
    }
    needs = binding_record(bound)["unmet_needs"]

    print(f"Agentic Sandbox V2 — stage {args.stage}")
    print("=" * 74)
    print(f"  tasks          {len(bound.tasks)}, sealed as {bound.binding_seal()[:16]}")
    print(f"  dataset        revision {DATASET_REVISION[:12]}")
    print(f"  deployment     {deployment} at {resource}")
    print(
        f"  settings       {chosen.tool_calls_per_attempt} tool calls, "
        f"{chosen.max_output_tokens_per_turn} tokens per turn"
    )
    priced = chosen.as_dict()
    print(
        f"  running        at most ${priced['most_running_could_cost_usd']} "
        f"against ${verdict.as_dict()['running_approved_maximum_usd']} approved"
    )
    print(
        f"  marking        at most ${priced['most_grading_could_cost_usd']} "
        f"against ${verdict.as_dict()['grading_approved_maximum_usd']} "
        "approved, and not spent by this script"
    )
    print(f"  isolation      none — fixture backend, exec_run shut")
    print(
        f"  handicap       {needs['tasks_needing_reference_files_count']} of "
        f"{len(bound.tasks)} tasks name reference files that are not in the "
        "workspace"
    )
    print()

    if args.dry_run:
        print(
            "Dry run. Nothing was asked and nothing was spent. Every condition "
            "for the paid run is met."
        )
        return 0

    into = (
        args.into
        if args.into is not None
        else Path(tempfile.mkdtemp(prefix=f"agentic-v2-{args.stage}-"))
    )
    into.mkdir(parents=True, exist_ok=True)
    run_id = args.run_id or f"agentic-v2-{args.stage}-{int(time.time())}"
    print(f"  run id         {run_id}")
    print(f"  writing to     {into}")
    print()

    from core.agentic_v2_model_voice import AzureFoundryVoice
    from core.azure_ai_clients import AzureAIRouteSettings, AzureAIWorkload
    from core.llm_client import create_typed_azure_client

    settings = AzureAIRouteSettings.from_env()
    managed = create_typed_azure_client(
        AzureAIWorkload.INFERENCE,
        deployment,
        settings=settings,
        timeout=float(plan["fixed_settings"]["per_task_timeout_seconds"]),
    )
    prices = load_price_table()

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

        held = TaskConversations(ceilings, RunWideCeilings())
        attempts: dict[str, int] = {}

        def attempt_of(task_id: str) -> int:
            attempts[task_id] = attempts.get(task_id, 0) + 1
            return attempts[task_id]

        # One voice per task, built on that task's own budget. A single voice
        # reused across the stage would hold task one's ceiling for all of
        # them, and the later tasks would be refused by an ceiling that had
        # nothing to do with them. See build_runner_factory's docstring.
        def voice_for(budget):
            return AzureFoundryVoice(
                client=managed.client,
                deployment=deployment,
                resource=resource,
                budget=budget,
                instructions=str(plan.get("instructions") or ""),
                max_output_tokens_per_turn=ceilings.max_written_tokens_per_turn,
                request_timeout_seconds=ceilings.max_seconds,
                prices=prices,
            )

        workspaces = into / "workspaces"

        def backend_factory(**kwargs):
            task_root = workspaces / f"task-{len(list(workspaces.glob('task-*')))}"
            task_root.mkdir(parents=True, exist_ok=True)
            return AgenticV2FixtureBackend(root=task_root, **kwargs)

        workspaces.mkdir(parents=True, exist_ok=True)
        factory = build_runner_factory(
            backend_factory=backend_factory,
            profile=profile,
            conversations=held,
            attempt_of=attempt_of,
            voice_for=voice_for,
        )

        from core.cost_receipts import CostReceiptLedger

        ledger = CostReceiptLedger(str(into / "cost_receipts.sqlite3"))

        def receipt_for(task, attempt: int):
            outcome = held.outcome_of(task.task_id, attempt)
            if outcome is None:
                return None
            turns = model_turns_of(
                outcome,
                run_id=run_id,
                task_id=task.task_id,
                attempt=attempt,
                provider="azure",
                requested_model=deployment,
                deployment=deployment,
                resolved_model=None,
            )
            return bind_run_to_ledger(
                ledger, task_id=task.task_id, model_turns=turns
            )

        outcome = run_manifest(
            bound.tasks,
            run_id=run_id,
            runner_factory=factory,
            journal_path=into / "journal.jsonl",
            collect_into=into / "deliverables",
            receipt_for=receipt_for,
            on_task=lambda task_id, row: print(
                f"  {task_id}  {'ok' if row.get('success') else 'failed'}"
            ),
        )
    except DriverRefused as refusal:
        print(f"\nThe run was refused.\n\n{refusal}")
        return 1
    finally:
        managed.close()

    record = {
        "stage": args.stage,
        "run_id": run_id,
        "dataset_revision": DATASET_REVISION,
        "binding": binding_record(bound),
        "environment": environment_note(profile),
        "route_fingerprint": managed.runtime_fingerprint,
        "chosen_settings": chosen.as_dict(),
        "conversations": held.as_dict(),
        "run": outcome.as_dict(),
    }
    written = json.dumps(record, indent=2, sort_keys=True, default=str)
    (into / "run_record.json").write_text(written + "\n", encoding="utf-8")

    summary = outcome.summary
    print()
    print(f"  record         {into / 'run_record.json'}")
    print(f"  finished       {summary.get('succeeded', 0)} of {len(bound.tasks)}")
    print(f"  spent          {held.spent}")
    if outcome.stopped is not None:
        print(f"\nStopped early: {outcome.stopped.detail}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
