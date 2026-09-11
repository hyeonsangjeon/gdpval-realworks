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
import hashlib
import json
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

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
from core.agentic_v2_preregistration import STAGE_SIZES, STOP_RULES  # noqa: E402
from core.agentic_v2_reference_staging import (  # noqa: E402
    MODEL_INPUT_PREFIX,
    TaskStaging,
    snapshot_problem,
    stage_task_reference_files,
    staging_record,
)
from core.agentic_v2_route_check import (  # noqa: E402
    check_route_is_the_one_the_plan_fixed,
)
from core.agentic_v2_run_driver import (  # noqa: E402
    DriverRefused,
    StoppedEarly,
    run_manifest,
)
from core.agentic_v2_sharding import ShardRefused  # noqa: E402
from core.agentic_v2_sharding import parse as parse_shard  # noqa: E402
from core.agentic_v2_stage_one_budget import (  # noqa: E402
    STAGE_ONE_PLAN_PATH,
    load_stage_one_plan,
    price_one_stage,
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


def names_that_answered(voices: Iterable[Any]) -> tuple[str, ...]:
    """Every distinct model name that came back, in sorted order.

    A voice that never spoke holds ``None`` and is not a name. A voice that
    spoke to a reply which named nothing holds ``""`` -- also not a name, and
    deliberately not treated as one: see :func:`answered_by_something_else`.
    """
    return tuple(
        sorted(
            {
                str(voice.resolved_model)
                for voice in voices
                if voice is not None and voice.resolved_model
            }
        )
    )


def answered_by_something_else(
    voices: Iterable[Any], *, pinned_model: str
) -> tuple[str, ...]:
    """Names that came back and are not the one the plan pinned.

    The one computation behind both the halt and the record, so the run cannot
    stop for a reason its own record disagrees with.

    Three states, and only one of them is this:

    ``matched``
        the reply named the pinned model. Nothing to do.
    ``differed``
        the reply named something else. The plan's first stop condition, and
        the run must not continue: every result after it would belong to a
        model the pre-registration does not describe.
    ``not reported``
        the reply named nothing at all -- ``resolved_model`` is ``""``. Not
        counted here, so it does not halt the run. The rule is written about a
        name that *differs*, and a provider omitting a field is not a model
        switch; halting on it would end a paid stage over a missing header.
        It is a real gap in the evidence all the same, so it is counted in the
        record under ``attempts_that_reported_no_model`` rather than passed
        over. Recorded, not enforced -- and the record says which.

    An empty ``pinned_model`` returns nothing. A plan that pins no name has no
    claim to check, and inventing one here would make this function the thing
    that decided what the run was allowed to be.
    """
    if not pinned_model:
        return ()
    return tuple(
        name for name in names_that_answered(voices) if name != pinned_model
    )


def model_calls_record(
    voices: Mapping[tuple[str, int], Any], *, pinned_model: str
) -> dict:
    """Every paid call, as the voice that made it recorded it.

    The sqlite ledger beside this is the bill. This is the evidence the bill
    was made from, and it is kept because the two are computed from different
    things and disagreement between them is worth being able to see: the
    ledger prices from the committed price list, and the voice prices from the
    same list keyed by the name the reply gave.

    ``resolved_model`` is the point of it. A deployment is an alias, and what
    answers behind it can change without the alias changing -- so "which model
    produced these 220 results" is not answered by the deployment name, and
    after the run there is nowhere else to look. Recorded per attempt rather
    than once for the run because a run that was answered by two different
    models is exactly the case worth catching, and a single field could not
    show it.

    ``spent_usd`` is ``None`` when any call in the attempt had no price, and
    that is deliberate: a total that quietly drops the calls it could not
    price reads as the whole bill and is not one. Missing is partial, never
    zero.

    No prompt and no reply text -- token counts, names and amounts only, the
    same rule the rest of this script follows.
    """
    per_attempt: list[dict[str, Any]] = []
    unpriced = 0
    unnamed = 0
    spoke = [voice for voice in voices.values() if voice is not None]
    for (task_id, attempt), voice in sorted(voices.items()):
        if voice is None:
            continue
        rows = voice.ledger()
        spent = voice.spent_usd()
        unpriced += sum(1 for row in rows if row.get("price_missing"))
        if voice.resolved_model == "":
            unnamed += 1
        per_attempt.append(
            {
                "task_id": task_id,
                "attempt": attempt,
                "resolved_model": voice.resolved_model,
                "calls": rows,
                "spent_usd": None if spent is None else str(spent),
            }
        )
    differed = answered_by_something_else(spoke, pinned_model=pinned_model)
    return {
        "what_this_is": (
            "one row per model call, as the voice that made it saw it. The "
            "bill is the ledger; this is what the bill was made from"
        ),
        "per_attempt": per_attempt,
        "pinned_model": pinned_model,
        "models_that_answered": list(names_that_answered(spoke)),
        "answered_by_something_else": list(differed),
        "attempts_that_reported_no_model": unnamed,
        "what_no_model_reported_means": (
            "the reply carried no model name. The call happened and was "
            "charged for; which model made it is not known and cannot be "
            "recovered afterwards. This does not stop the run -- the stop "
            "condition is written about a name that differs, and an omitted "
            "field is not a model switch -- so it is counted here instead of "
            "being passed over"
        ),
        "calls_with_no_price": unpriced,
        "what_no_price_means": (
            "the committed price list has no entry for the model the reply "
            "named. The call happened and cost something; the amount is not "
            "known here and is not zero. The tokens and the model name are "
            "kept above, so it can be worked out once the list covers it"
        ),
    }


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


def check_the_plan_priced_this_stage(plan: dict, stage: str, bound, catalog) -> list[str]:
    """Whether the amounts approved describe the run about to happen.

    The plan prices each stage by name, and the figures are per-run rather than
    per-task. So a thirty-task or two-hundred-and-twenty-task stage run under
    the five-task stage's approval would go out against a figure worked out for
    a run forty-four times smaller — and the printed line would say it was
    within budget, because the arithmetic it came from never saw the larger
    cohort.

    Caught by pricing the cohort that is actually bound, rather than by
    comparing counts. Counting was the earlier version of this check and it was
    weaker in both directions: it refused a correctly priced larger stage, and
    it would have waved through a same-sized cohort whose tasks had grown more
    expensive. Prices come from the plan; nothing here scales an approved
    amount on its own.
    """
    shared_plan_path = BATCH_RUNNER_ROOT / str(
        plan.get("cost", {}).get("assumptions_come_from")
        or "experiments/execution_envelope/advance_check_plan.yaml"
    )
    pricing = price_one_stage(
        plan,
        stage=stage,
        task_ids=bound.task_ids,
        tasks_by_id=catalog.by_task_id(),
        assumptions=CostAssumptions.from_mapping(
            load_plan(shared_plan_path)["cost"]["assumptions"]
        ),
    )
    return pricing, list(pricing.problems)


def open_the_ledger(into: Path, *, run_id: str):
    """Open the sqlite ledger the paid run settles every call into.

    One function rather than one call site, because the dry run opens it too --
    against a directory it throws away -- and the point of that is that the two
    cannot drift apart. The paid run reached this line for the first time ever
    on 2026-09-11 and died on it: the constructor had grown a required
    ``run_id`` keyword and this call had not, so the stage crashed after the
    identity check, the route check and the cohort binding had all passed.

    Nothing caught it earlier because nothing could. The dry run returned
    several hundred lines above, having printed that every condition for the
    paid run was met, and the paid branch it was speaking for had never been
    executed -- not in CI, not in a test. A ``TypeError`` on a keyword argument
    is the cheapest possible version of that gap. The expensive version is the
    same gap one line further down, after the model has been asked.
    """
    from core.cost_receipts import CostReceiptLedger

    return CostReceiptLedger(str(into / "cost_receipts.sqlite3"), run_id=run_id)


def the_paid_setup_a_dry_run_can_reach(stage: str) -> list[str]:
    """Run the paid path's setup against a throwaway directory.

    Returns what broke, empty when nothing did. Called from the dry run, so the
    free job pays for this class of mistake instead of the paid one.

    It is deliberately not much: the ledger is the only part of the paid setup
    that needs no Azure identity, and the free job holds none. The voice, the
    route, the deployment and the conversation cannot be reached from here and
    are not claimed to be. Saying which is the other half of the fix -- the
    sentence this used to print claimed all of them.
    """
    with tempfile.TemporaryDirectory(prefix=f"agentic-v2-{stage}-dry-") as scratch:
        try:
            ledger = open_the_ledger(Path(scratch), run_id="dry-run")
        except Exception as broke:  # noqa: BLE001 - reported, not handled
            return [f"the paid run's cost ledger cannot be opened: {broke!r}"]
        ledger.close()
    return []


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
        "--dataset-root",
        type=Path,
        default=None,
        help=(
            "Where the reference files are copied from. Defaults to the "
            "directory holding --parquet's own snapshot, so the prompts and "
            "the files a task opens always come from one revision. Must be a "
            "directory of real files: a huggingface_hub cache is a tree of "
            "symlinks into a blob store outside it, and nothing here will "
            "follow one. Fetch with `hf download ... --local-dir <dir>`."
        ),
    )
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
        "--shard",
        default=None,
        help=(
            "Run one piece of the stage, written index/total like 3/17. The "
            "cohort is dealt out one task at a time, so every shard holds a "
            "slice of the whole rather than a run of neighbours. Left out, or "
            "given as 1/1, the whole stage runs in this one process."
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
    parser.add_argument(
        "--rehearse",
        action="store_true",
        help=(
            "Run the whole stage with a stand-in instead of a model: real "
            "binding, real files, real workspace, real collection, no call and "
            "no cost. Writes rehearsal_record.json rather than "
            "run_record.json, because a rehearsal is not a result."
        ),
    )
    args = parser.parse_args()

    if args.dry_run and args.rehearse:
        print(
            "Refused: --dry-run and --rehearse ask for different things. The "
            "first stops before the work, the second does the work without a "
            "model. Pick one."
        )
        return 1

    try:
        plan, verdict, catalog = verdict_for(args.plan)
        bound = bind_stage(
            args.stage,
            dataset_tasks=read_pinned_dataset(args.parquet),
            catalog=catalog,
            catalog_digest=catalog_sha256(),
        )
        # The snapshot the prompts were read from, so a task cannot be given a
        # prompt from one revision and a file from another.
        dataset_root = (
            args.dataset_root
            if args.dataset_root is not None
            else args.parquet.parent.parent
        )
        # Asked once, here, rather than discovered 261 times during the run.
        # A cache of symlinks refuses every file individually and the run then
        # looks like 125 tasks that failed on their merits, which is the single
        # most expensive way to find out that a directory was wrong. Only asked
        # when this cohort actually opens something: a stage whose tasks name no
        # files is not blocked by a directory it will never read.
        if any(task.reference_files for task in bound.tasks):
            wrong_root = snapshot_problem(dataset_root)
            if wrong_root is not None:
                raise StageRefused(
                    "the reference files cannot be staged from "
                    f"{dataset_root}: {wrong_root}\n\n"
                    "Refused before spending, because running anyway would "
                    "hand every task an empty workspace and produce failures "
                    "that read as the model's."
                )
        # Priced over the whole stage, never over the shard. A shard is a way of
        # fitting the run into the place it has to happen, not a smaller
        # purchase — pricing each piece separately would let seventeen runs that
        # are each "within budget" spend seventeen times the approval.
        pricing, unpriced = check_the_plan_priced_this_stage(
            plan, args.stage, bound, catalog
        )
        if unpriced:
            raise StageRefused("\n  - ".join(["this stage is not priced:", *unpriced]))
        shard = parse_shard(args.shard, bound.task_ids)
    except (StageRefused, ManifestRefused, ShardRefused) as refusal:
        print(f"Refused before spending anything.\n\n{refusal}")
        return 1

    tasks_to_run = bound.tasks
    if shard is not None:
        wanted = set(shard.task_ids)
        tasks_to_run = tuple(
            task for task in bound.tasks if task.task_id in wanted
        )

    chosen = verdict.chosen
    ceilings = ceilings_from(plan, chosen)
    connection = plan.get("azure_connection") or {}
    deployment = str((plan.get("model") or {}).get("deployment") or "")
    # The name the plan says will answer, as opposed to the alias it will be
    # asked through. The plan pins both and they are not the same fact: the
    # deployment is the address, and this is the claim about who is behind it.
    # Read here so the stop condition below has something to compare against;
    # until now it was read only to print an estimate.
    pinned_model = str((plan.get("model") or {}).get("resolved_model") or "")
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
    if shard is not None:
        print(
            f"  shard          {shard.index} of {shard.of} — this run does "
            f"{len(tasks_to_run)} of them, and the stage has not run until "
            "every shard has"
        )
    print(f"  dataset        revision {DATASET_REVISION[:12]}")
    print(f"  deployment     {deployment} at {resource}")
    print(
        f"  settings       {chosen.tool_calls_per_attempt} tool calls, "
        f"{chosen.max_output_tokens_per_turn} tokens per turn"
    )
    # The stage's own figures, not the five-task plan's. Those two are the same
    # number only for advance_check_5, and printing the wrong one beside a
    # two-hundred-task run is how a stage gets described as affordable.
    money = pricing.as_dict()
    print(
        f"  running        at most ${money['most_running_could_cost_usd']} "
        f"against ${money['approved_running_usd']} approved for the whole stage"
    )
    if money["approved_grading_usd"] is not None:
        print(
            f"  marking        at most ${money['approved_grading_usd']} "
            "approved, and not spent by this script"
        )
    else:
        print("  marking        not approved for this stage, and not spent here")
        print(f"                 {money['grading_not_approved_because']}")
    print(f"  isolation      none — fixture backend, exec_run shut")
    # Was a flat count of tasks whose files "are not in the workspace", which
    # stopped being true the moment staging existed. What is still true, and is
    # what a reader needs, is where they come from and the one that cannot be
    # delivered at any setting.
    print(
        f"  inputs         {needs['tasks_needing_reference_files_count']} of "
        f"{len(bound.tasks)} tasks name reference files, staged from "
        f"{dataset_root}"
    )
    print()

    if args.dry_run:
        # Reach the paid setup before speaking for it. The sentence below used
        # to say every condition for the paid run was met, and on 2026-09-11 a
        # paid run that had just been told exactly that died on the next part
        # of the script the dry run never executes.
        broke = the_paid_setup_a_dry_run_can_reach(args.stage)
        if broke:
            print("Dry run. Nothing was asked and nothing was spent.\n")
            for problem in broke:
                print(f"  - {problem}")
            print(
                "\nThis is a paid-run condition and it is not met, so the paid "
                "run would have failed after its identity and route checks had "
                "passed. Failing here instead."
            )
            return 1
        print(
            "Dry run. Nothing was asked and nothing was spent. Every condition "
            "this job can reach is met: the plan, the seal, the cohort, the "
            "amounts, the staged inputs, and the ledger the paid run settles "
            "into.\n\n"
            "It cannot reach the model. This job holds no Azure identity, so "
            "the route, the deployment and the conversation itself are checked "
            "in the paid job and nowhere else. A green dry run is not a "
            "promise that the paid run will reach the model -- only that it "
            "will not be stopped by anything checkable without one."
        )
        return 0

    if args.rehearse:
        print(
            "Rehearsal. A stand-in works every task and no model is asked, so "
            "the amounts above are what the paid run would be allowed rather "
            "than what this one costs. Nothing here is a result."
        )
        print()

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
    from core.agentic_v2_rehearsal_voice import (
        RehearsalVoice,
        rehearsal_is_not_a_run,
    )

    # A rehearsal never builds a client. Not as an optimisation: a client that
    # exists is a client something can be sent through, and the one thing this
    # mode promises is that nothing was asked. There is no route to check for
    # the same reason -- there is no route.
    rehearsing = RehearsalVoice() if args.rehearse else None
    managed = None
    prices: Any = {}
    if rehearsing is None:
        settings = AzureAIRouteSettings.from_env()
        managed = create_typed_azure_client(
            AzureAIWorkload.INFERENCE,
            deployment,
            settings=settings,
            timeout=float(plan["fixed_settings"]["per_task_timeout_seconds"]),
        )
        prices = load_price_table()

    try:
        if rehearsing is None:
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

        # Kept, rather than built and dropped. Each voice reads the model name
        # out of every reply it gets, holds it, and refuses the run if a later
        # reply names a different one -- so the voice is the only thing in the
        # run that knows which model actually answered. It also prices each
        # call against that name as it goes. Both were being thrown away with
        # the voice at the end of the task, which left the receipt unable to
        # answer the one question it exists to answer: what was this a bill
        # for. Keyed by the budget's identity because that is the only handle
        # ``voice_for`` is given, and ``TaskConversations`` files the same
        # budget object under the task and attempt it belongs to.
        voices_by_budget: dict[int, Any] = {}

        # One voice per task, built on that task's own budget. A single voice
        # reused across the stage would hold task one's ceiling for all of
        # them, and the later tasks would be refused by an ceiling that had
        # nothing to do with them. See build_runner_factory's docstring.
        def voice_for(budget):
            voice = AzureFoundryVoice(
                client=managed.client,
                deployment=deployment,
                resource=resource,
                budget=budget,
                instructions=str(plan.get("instructions") or ""),
                max_output_tokens_per_turn=ceilings.max_written_tokens_per_turn,
                request_timeout_seconds=ceilings.max_seconds,
                prices=prices,
            )
            voices_by_budget[id(budget)] = voice
            return voice

        def voice_of(task_id: str, attempt: int):
            """The voice that spoke for one attempt, or ``None``.

            ``None`` for a rehearsal, and for an attempt refused before a voice
            was ever built. Both are states where no model answered, so there
            is no resolved model to report and saying so is correct.
            """
            budget = held.budgets.get((str(task_id), int(attempt)))
            if budget is None:
                return None
            return voices_by_budget.get(id(budget))

        # ── the plan's first stop condition ───────────────────────────────
        #
        # Rule 0: "the deployment or model reported back differs from the
        # pinned one", which the plan writes out as "Stop at once if the model
        # name or deployment name reported back differs from the one fixed
        # above."
        #
        # It was written into the plan and implemented nowhere. The driver's
        # own table of who enforces what attributed it to the model client,
        # which is built before any reply exists and can only see the name
        # being asked for -- so the half of the condition that says *reported
        # back* had no reader anywhere in the run.
        #
        # Not rule 1, which is the neighbouring and different claim that a run
        # switched on its own mid-conversation. The voice does hold that one:
        # it raises when two replies in one conversation name two different
        # models. What no part of the run held is the comparison against the
        # name the plan pinned.
        #
        # That comparison needs two things which meet in this function and
        # nowhere else: the name the plan pinned, and the names the replies
        # carried. The voice sees only its own replies, and its guard is per
        # conversation -- so two tasks answered by two different models pass
        # every check inside both and arrive here as one experiment reported
        # as one thing. This is the level the rule is written at, so this is
        # where it is enforced.
        #
        # Wired into both seams on purpose, because they stop different
        # amounts of spending:
        #
        #   cancel_requested  is read at the top of every model turn and
        #                     before every tool call, so the task that saw the
        #                     wrong name does not take another turn. This is
        #                     the one that saves money.
        #   stop_when         is read by the driver between tasks, so the run
        #                     ends with `stopped_early` naming the rule
        #                     instead of quietly finishing a manifest of
        #                     cancelled tasks. This is the one that saves the
        #                     record.
        #
        # Either alone is wrong in a way that matters. Cancelling without
        # stopping leaves a run that halted looking like a run that completed;
        # stopping without cancelling pays for the rest of the current task's
        # turns before anyone looks.
        def wrong_model_answered() -> tuple[str, ...]:
            return answered_by_something_else(
                voices_by_budget.values(), pinned_model=pinned_model
            )

        def cancel_requested() -> bool:
            return bool(wrong_model_answered())

        def stop_when(after_task: str):
            differed = wrong_model_answered()
            if not differed:
                return None
            return StoppedEarly(
                rule_index=0,
                rule=STOP_RULES[0],
                detail=(
                    f"the plan pins {pinned_model!r} and a reply came back "
                    f"named {', '.join(repr(name) for name in differed)}. "
                    "Every result after this point would belong to a model "
                    "the pre-registration does not describe"
                ),
                after_task=after_task,
            )

        workspaces = into / "workspaces"
        workspaces.mkdir(parents=True, exist_ok=True)
        stagings: list[TaskStaging] = []
        attempts_staged: dict[str, int] = {}

        def backend_factory(**kwargs):
            """One root per attempt, with that attempt's own copy of the inputs.

            Named by the task rather than by how many directories exist, which
            is what it counted before. A counter answers "how many have run",
            and the question here is "which task is this" — so a resumed run,
            or any run where a directory was made for something else, silently
            handed a task the workspace belonging to another one.

            Re-staged per attempt rather than shared, because the model writes
            its deliverables into this same tree: a second attempt handed the
            first attempt's directory starts with the first attempt's output
            already in it, which is not a retry of the task.
            """
            task_id = str(kwargs.get("task_id") or "unknown-task")
            attempt = attempts_staged[task_id] = attempts_staged.get(task_id, 0) + 1
            task_root = (
                workspaces
                / f"{hashlib.sha256(task_id.encode('utf-8')).hexdigest()[:16]}"
                f"-attempt-{attempt}"
            )
            task_root.mkdir(parents=True, exist_ok=True)
            # Beneath `work/`, because that is the directory the backend opens
            # and the only one the model can reach. Beneath `inputs/` within it,
            # so the path in the record -- `inputs/reference_files/...` -- is
            # where the file actually is rather than a label for where it
            # morally belongs.
            staged = stage_task_reference_files(
                task_id=task_id,
                reference_files=kwargs.get("reference_files") or (),
                snapshot_root=dataset_root,
                into=task_root / "work" / MODEL_INPUT_PREFIX,
                render_text=True,
            )
            stagings.append(staged)
            if staged.ran_without_its_inputs:
                print(
                    f"  {task_id}  staged {len(staged.delivered)} of "
                    f"{staged.named} files; a failure here is not the model's"
                )
            if staged.could_open_nothing:
                print(
                    f"  {task_id}  has files and can open none of them; a "
                    "failure here is not the model's either"
                )
            return AgenticV2FixtureBackend(root=task_root, **kwargs)
        factory = build_runner_factory(
            backend_factory=backend_factory,
            profile=profile,
            conversations=held,
            attempt_of=attempt_of,
            cancel_requested=cancel_requested,
            **(
                {"voice": rehearsing}
                if rehearsing is not None
                else {"voice_for": voice_for}
            ),
        )

        if rehearsing is not None:
            # Every task ends unaccounted, which is the true answer. A rehearsal
            # makes no call, and a ledger row saying $0 would be the one number
            # that reads as a measurement of a model that was never asked.
            receipt_for = lambda task, attempt: None  # noqa: E731
        else:
            # Through the same helper the dry run calls, so this line cannot
            # drift from the one that is supposed to be checking it.
            ledger = open_the_ledger(into, run_id=run_id)

            def receipt_for(task, attempt: int):
                outcome = held.outcome_of(task.task_id, attempt)
                if outcome is None:
                    return None
                spoke = voice_of(task.task_id, attempt)
                turns = model_turns_of(
                    outcome,
                    run_id=run_id,
                    task_id=task.task_id,
                    attempt=attempt,
                    provider="azure",
                    requested_model=deployment,
                    deployment=deployment,
                    # What the reply named, not what was asked for. Passing
                    # None left the ledger's own column empty and priced the
                    # call against the deployment alias instead -- which is
                    # the right amount only if the two strings happen to
                    # match, and the record kept nothing that would let anyone
                    # check whether they did.
                    #
                    # If they do not match, these calls settle as
                    # `price_missing`. That is the true state: the committed
                    # price list has no entry for the model that answered, and
                    # an amount worked out from a different model's rates is
                    # not a smaller error than a missing one. It is also the
                    # recoverable direction -- `model_calls` below keeps the
                    # tokens and the name, so the amount can be worked out
                    # later once the price list covers it, whereas a name
                    # thrown away at the end of the task is gone.
                    resolved_model=(
                        spoke.resolved_model if spoke is not None else None
                    ),
                )
                return bind_run_to_ledger(
                    ledger, task_id=task.task_id, model_turns=turns
                )

        outcome = run_manifest(
            tasks_to_run,
            run_id=run_id,
            runner_factory=factory,
            journal_path=into / "journal.jsonl",
            collect_into=into / "deliverables",
            receipt_for=receipt_for,
            stop_when=stop_when,
            on_task=lambda task_id, row: print(
                # `status`, not a `success` key -- the row is a report row and
                # has never carried one, so the old `row.get("success")` read
                # None for every task and printed "failed" beside five tasks
                # that had all succeeded.
                f"  {task_id}  {'ok' if row.get('status') == 'success' else 'failed'}"
            ),
        )
    except DriverRefused as refusal:
        print(f"\nThe run was refused.\n\n{refusal}")
        return 1
    finally:
        if managed is not None:
            managed.close()

    record = {
        "stage": args.stage,
        "run_id": run_id,
        "dataset_revision": DATASET_REVISION,
        "binding": binding_record(bound),
        # Present even when the run is not sharded, so that a reader never has
        # to infer from silence whether a record covers the whole stage.
        "shard": (
            shard.as_dict()
            if shard is not None
            else {
                "index": 1,
                "of": 1,
                "task_count": len(tasks_to_run),
                "cohort_size": len(bound.tasks),
                "task_ids": list(bound.task_ids),
                "covers_whole_stage": True,
                "what_this_run_is": "the whole stage, in one run",
            }
        ),
        "approved_amounts": pricing.as_dict(),
        # What each task was actually handed, per attempt, by name. The binding
        # record's `unmet_needs` says which tasks *want* files; this says which
        # got them. A result is read against this one.
        "reference_files": staging_record(stagings),
        # Which model answered, per attempt, and what each call is known to
        # have cost. The deployment name is in `chosen_settings` already; this
        # is what came back, which is not the same fact.
        "model_calls": model_calls_record(
            {
                key: voices_by_budget.get(id(budget))
                for key, budget in held.budgets.items()
            },
            pinned_model=pinned_model,
        ),
        "environment": environment_note(profile),
        "route_fingerprint": (
            rehearsal_is_not_a_run()
            if rehearsing is not None
            else managed.runtime_fingerprint
        ),
        "chosen_settings": chosen.as_dict(),
        "conversations": held.as_dict(),
        "run": outcome.as_dict(),
    }
    if rehearsing is not None:
        record["rehearsal"] = rehearsing.as_dict()
    written = json.dumps(record, indent=2, sort_keys=True, default=str)
    # A different name, so that nothing which reads a run's record can be handed
    # a rehearsal's by accident. The disclaimer inside it is for a person; the
    # filename is for everything else.
    name = "rehearsal_record.json" if rehearsing is not None else "run_record.json"
    (into / name).write_text(written + "\n", encoding="utf-8")

    summary = outcome.summary
    print()
    print(f"  record         {into / name}")
    print(f"  finished       {summary.get('succeeded', 0)} of {len(tasks_to_run)}")
    if rehearsing is not None:
        found = rehearsing.as_dict()
        print(
            f"  guide readable {found['guide_was_readable_in']} of "
            f"{found['tasks_worked']} tasks"
        )
        print(f"  wrote a file   {found['wrote_a_file_in']} of {found['tasks_worked']}")
        print("  spent          nothing — no model was asked")
    else:
        print(f"  spent          {held.spent}")
    if shard is not None:
        print(
            f"\nThis was shard {shard.index} of {shard.of}. The stage has not "
            "run until the others have and their coverage has been checked."
        )
    if outcome.stopped is not None:
        print(f"\nStopped early: {outcome.stopped.detail}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
