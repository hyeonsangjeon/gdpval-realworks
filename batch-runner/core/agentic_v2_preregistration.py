"""What a V2 run promises before it starts, and what it may not claim at the end.

Stage F of ``tasks/0822_saturday/TASK_AGENTIC_SANDBOX_V2_ACTIVATION.md`` asks for
a fixed task manifest, the model, the prompt, the tools, the token, time and
retry conditions, and the technical stop rules -- **written down before anything
runs**, and then five tasks, then thirty, then two hundred and twenty.

A document could say all of that. The reason this is code is that three of the
promises are only worth something if something checks them.

**The manifest cannot quietly change.** The three cohorts are not typed out
here; they are derived from the committed score-free catalogue by the rules in
:mod:`core.execution_envelope_tasks`, which predate every run and read nothing
but the catalogue. What is recorded is a seal over the derived lists together
with the catalogue fingerprint and the dataset revision. A cohort that moves
after the fact breaks the seal rather than being noticed by a reader comparing
two long lists of identifiers.

**The escalation is not what it looks like.** "Five, then thirty, then two
hundred and twenty" reads as three nested circles. It is not one. Four of the
five are in the thirty and one is not, because the two selection rules answer
different questions and neither was allowed to look at a score. So a claim of
the form "the thirty confirmed the five" is false about one fifth of the five,
and :func:`escalation_shape` computes that rather than leaving it to whoever
writes the report. A's Codex configuration reached the same conclusion
independently, which is corroboration rather than agreement by construction:
the two were derived from the same rule but written down separately.

**A difference from A's run is not an environment effect.** The instruction is
explicit -- state whether the things being compared match, and if they differ,
do not claim the difference is the environment. That is easy to agree with and
hard to hold to six weeks later, so :func:`compare_with_codex_run` reads A's
committed experiment file and reports field by field, and
:func:`may_attribute_difference_to_environment` refuses while anything but the
environment differs. An unchecked field counts as differing, because a field
nobody compared is not a field that matched.

That refusal will return ``False`` for the foreseeable future, and it should.
Two of the differences are not settings anybody forgot to align: the two run
places offer different tools and therefore cannot be given the same
instructions. :func:`residual_after_alignment` says exactly which differences
would survive a maximum effort to match, so the comparison can be described
precisely instead of being either overclaimed or abandoned.

Nothing here runs a task, calls a model, boots a guest, opens a gate or spends.
It reads committed files and does arithmetic.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

from core.agentic_compute import (
    MAX_INPUT_FILES,
    MAX_INPUT_SINGLE,
    MAX_INPUT_TOTAL,
)
from core.agentic_v2_contract import TOOL_NAMES
from core.agentic_v2_reference_staging import (
    MODEL_INPUT_PREFIX,
    TOO_LARGE,
    TOO_LARGE_FOR_THE_WORKSPACE,
    WORKSPACE_FILE_LIMIT,
)
from core.execution_envelope_tasks import (
    ADVANCE_CHECK_TASK_COUNT,
    FULL_RUN_TASK_COUNT,
    TRIAL_RUN_TASK_COUNT,
    TaskCatalog,
    catalog_sha256,
    full_run_tasks,
    load_task_catalog,
    select_advance_check_tasks,
    select_trial_run_tasks,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
BATCH_RUNNER_ROOT = REPOSITORY_ROOT / "batch-runner"

#: A's Codex thirty-task run, read rather than restated. If this file moves or
#: is deleted every comparison becomes ``UNKNOWN``, which blocks attribution --
#: the safe direction for a missing source.
CODEX_TRIAL_PLAN = (
    BATCH_RUNNER_ROOT / "experiments" / "exp034_codex_foundry_trial30.yaml"
)

#: B's own settings, likewise read from the file that already holds them.
V2_STAGE_ONE_PLAN = (
    BATCH_RUNNER_ROOT
    / "experiments"
    / "execution_envelope"
    / "agentic_stage_one_plan.yaml"
)

#: Where the committed copy of the pre-registration lives. Named here rather
#: than in the script that writes it, so the writer and the test that holds it
#: cannot drift to two different files and both pass.
PREREGISTRATION_ARTEFACT = (
    REPOSITORY_ROOT / "tasks" / "0822_saturday" / "v2_run_preregistration.json"
)

STAGE_FIVE = "advance_check_5"
STAGE_THIRTY = "trial_30"
STAGE_TWO_TWENTY = "full_220"

#: The order stage F runs them in. Naming it here means a run that skipped
#: straight to the two hundred and twenty is a visible departure from the
#: record rather than an undocumented choice.
ESCALATION = (STAGE_FIVE, STAGE_THIRTY, STAGE_TWO_TWENTY)

STAGE_SIZES = {
    STAGE_FIVE: ADVANCE_CHECK_TASK_COUNT,
    STAGE_THIRTY: TRIAL_RUN_TASK_COUNT,
    STAGE_TWO_TWENTY: FULL_RUN_TASK_COUNT,
}

MATCHES = "matches"
DIFFERS = "differs"
UNKNOWN = "unknown"


def cohorts(catalog: TaskCatalog | None = None) -> dict[str, tuple[str, ...]]:
    """The three task lists, derived from the committed catalogue."""
    catalog = catalog or load_task_catalog()
    return {
        STAGE_FIVE: select_advance_check_tasks(catalog).task_ids,
        STAGE_THIRTY: select_trial_run_tasks(catalog),
        STAGE_TWO_TWENTY: full_run_tasks(catalog),
    }


def escalation_shape(
    catalog: TaskCatalog | None = None,
) -> dict[str, Any]:
    """How the three cohorts actually sit inside one another.

    Computed, because the answer is not the one the phrase "five, then thirty,
    then two hundred and twenty" suggests.
    """
    chosen = cohorts(catalog)
    five = set(chosen[STAGE_FIVE])
    thirty = set(chosen[STAGE_THIRTY])
    full = set(chosen[STAGE_TWO_TWENTY])

    carried = sorted(five & thirty)
    dropped = sorted(five - thirty)
    return {
        "sizes": {name: len(chosen[name]) for name in ESCALATION},
        "five_inside_thirty": not dropped,
        "thirty_inside_two_twenty": thirty <= full,
        "five_inside_two_twenty": five <= full,
        "carried_from_five_into_thirty": carried,
        "dropped_between_five_and_thirty": dropped,
        "comparable_across_the_first_two_stages": carried,
        "what_that_means": (
            "the escalation is not nested. A stage-over-stage statement holds "
            f"for the {len(carried)} tasks in both cohorts and says nothing "
            f"about the {len(dropped)} that only the first stage ran. Neither "
            "selection rule can see a score, so the gap is a property of two "
            "rules answering different questions and not of anything chosen "
            "after results arrived."
        )
        if dropped
        else (
            "the first two cohorts are nested, so a stage-over-stage statement "
            "covers every task of the earlier stage."
        ),
    }


def manifest(catalog: TaskCatalog | None = None) -> dict[str, Any]:
    """The fixed task manifest: what will be run, and what pins it."""
    catalog = catalog or load_task_catalog()
    chosen = cohorts(catalog)
    return {
        "catalog_sha256": catalog_sha256(),
        "dataset_repo_id": "openai/gdpval",
        "dataset_revision": catalog.dataset_revision,
        "dataset_file_sha256": catalog.dataset_file_sha256,
        "selection_rules": {
            STAGE_FIVE: "core.execution_envelope_tasks.select_advance_check_tasks",
            STAGE_THIRTY: "core.execution_envelope_tasks.select_trial_run_tasks",
            STAGE_TWO_TWENTY: "core.execution_envelope_tasks.full_run_tasks",
        },
        "task_ids": {name: list(chosen[name]) for name in ESCALATION},
        "escalation": escalation_shape(catalog),
    }


def seal(record: Mapping[str, Any]) -> str:
    """A fingerprint over a pre-registration, so a later edit is detectable."""
    canonical = json.dumps(
        record, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def verify_seal(record: Mapping[str, Any], expected: str) -> list[str]:
    """Everything wrong with a pre-registration against the seal it was given."""
    actual = seal(record)
    if actual == expected:
        return []
    return [
        "the pre-registration no longer matches the seal recorded before the "
        f"run: recorded {expected}, now {actual}. Something that was fixed in "
        "advance has moved, and a result produced under it cannot be described "
        "as pre-registered."
    ]


@dataclass(frozen=True)
class Comparison:
    """One field of B's run set beside A's, with what the difference costs."""

    field: str
    ours: Any
    theirs: Any
    verdict: str
    #: Whether B could make this field match by choosing differently. A
    #: removable difference is an alignment nobody has done yet; an irreducible
    #: one is a property of the two run places and will never go away.
    removable: bool
    why: str


def _read_yaml(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    return loaded if isinstance(loaded, dict) else None


def _digest_of(path: Path) -> str | None:
    """The fingerprint of a file the record depends on, or ``None`` if absent."""
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verdict(ours: Any, theirs: Any) -> str:
    if theirs is None:
        return UNKNOWN
    return MATCHES if ours == theirs else DIFFERS


def compare_with_codex_run(
    codex_plan: Path | None = None, v2_plan: Path | None = None
) -> tuple[Comparison, ...]:
    """Set B's settings beside A's, field by field, from the committed files.

    Read rather than restated so the comparison tracks A's file. A source that
    is missing yields ``UNKNOWN`` everywhere, which blocks attribution -- an
    unread field must never pass for an agreeing one.
    """
    codex = _read_yaml(codex_plan or CODEX_TRIAL_PLAN) or {}
    mine = _read_yaml(v2_plan or V2_STAGE_ONE_PLAN) or {}

    their_model = ((codex.get("condition_a") or {}).get("model") or {})
    their_exec = codex.get("execution") or {}
    their_qa = ((codex.get("condition_a") or {}).get("qa") or {})
    their_prompt = ((codex.get("condition_a") or {}).get("prompt") or {})
    their_tasks = ((codex.get("data") or {}).get("filter") or {}).get("task_ids")

    my_model = mine.get("model") or {}
    my_fixed = mine.get("fixed_settings") or {}

    their_attempts = their_exec.get("max_retries")
    if isinstance(their_attempts, int):
        # A counts retries; B counts attempts. Comparing the two numbers
        # directly would report a difference of one that does not exist, or
        # hide a real one.
        their_attempts = their_attempts + 1

    return (
        Comparison(
            field="deployment",
            ours=my_model.get("deployment"),
            theirs=their_model.get("deployment"),
            verdict=_verdict(my_model.get("deployment"), their_model.get("deployment")),
            removable=True,
            why="both runs must name the same deployment or nothing is comparable",
        ),
        Comparison(
            field="task_cohort_thirty",
            ours=list(cohorts()[STAGE_THIRTY]),
            theirs=list(their_tasks) if their_tasks else None,
            verdict=_verdict(
                list(cohorts()[STAGE_THIRTY]),
                list(their_tasks) if their_tasks else None,
            ),
            removable=True,
            why="the same fixed selection rule produced both lists",
        ),
        Comparison(
            field="attempts_per_task",
            ours=my_fixed.get("retry_max_attempts"),
            theirs=their_attempts,
            verdict=_verdict(my_fixed.get("retry_max_attempts"), their_attempts),
            removable=True,
            why=(
                "a run given four attempts and a run given one are not the same "
                "run. B can match A before the two-hundred-and-twenty stage"
            ),
        ),
        Comparison(
            field="per_task_wall_clock_seconds",
            ours=my_fixed.get("per_task_timeout_seconds"),
            theirs=their_exec.get("timeout"),
            verdict=_verdict(
                my_fixed.get("per_task_timeout_seconds"), their_exec.get("timeout")
            ),
            removable=True,
            why="a shorter clock produces timeouts the other run would not have",
        ),
        Comparison(
            field="self_review_enabled",
            ours=bool(my_fixed.get("self_review_enabled")),
            theirs=(
                bool(their_qa.get("enabled")) if "enabled" in their_qa else None
            ),
            verdict=_verdict(
                bool(my_fixed.get("self_review_enabled")),
                bool(their_qa.get("enabled")) if "enabled" in their_qa else None,
            ),
            removable=True,
            why="a second look at a finished answer changes the result",
        ),
        Comparison(
            field="resume_rounds",
            ours=0,
            theirs=their_exec.get("resume_max_rounds"),
            verdict=_verdict(0, their_exec.get("resume_max_rounds")),
            removable=True,
            why=(
                "resuming by status re-runs tasks stopped for content and "
                "raises a score by the difference; both runs hold it off"
            ),
        ),
        Comparison(
            field="tool_surface",
            ours=list(TOOL_NAMES),
            theirs="the Codex agent's own tools",
            verdict=DIFFERS,
            removable=False,
            why=(
                "this is what the comparison is *about*. A V2 task reaches a "
                "shell through a contract of eight named tools; a Codex task "
                "reaches one through the agent's own. Making these match would "
                "mean deleting the thing being measured"
            ),
        ),
        Comparison(
            field="standing_instructions",
            ours="describes the V2 tool contract",
            theirs=(their_prompt.get("system") or "").strip() or None,
            verdict=DIFFERS,
            removable=False,
            why=(
                "the wording has to describe the tools the model actually has. "
                "Two different tool surfaces cannot share one instruction, so "
                "this difference follows from the one above rather than being a "
                "second independent choice"
            ),
        ),
    )


def may_attribute_difference_to_environment(
    comparisons: Sequence[Comparison] | None = None,
) -> tuple[bool, list[str]]:
    """Whether a difference in results may be called an effect of the environment.

    ``True`` only when every field except the environment itself matches.
    ``UNKNOWN`` blocks, because a field nobody compared is not a field that
    agreed.
    """
    comparisons = comparisons if comparisons is not None else compare_with_codex_run()
    blockers = [
        f"{item.field}: {item.verdict} -- {item.why}"
        for item in comparisons
        if item.verdict != MATCHES
    ]
    return (not blockers), blockers


def residual_after_alignment(
    comparisons: Sequence[Comparison] | None = None,
) -> dict[str, Any]:
    """What would still differ if B aligned everything it is able to align.

    The useful question. "Not a pure environment effect" is true and nearly
    useless on its own; naming the irreducible remainder is what lets a report
    describe the comparison instead of retreating from it.
    """
    comparisons = comparisons if comparisons is not None else compare_with_codex_run()
    removable = [
        item for item in comparisons
        if item.verdict != MATCHES and item.removable
    ]
    irreducible = [item for item in comparisons if not item.removable]
    return {
        "alignable_now": [item.field for item in removable],
        "irreducible": [item.field for item in irreducible],
        "what_the_comparison_can_be": (
            "with the alignable fields matched, the two runs differ in the tool "
            "surface and the instruction that describes it, and in nothing "
            "else that was checked. A difference in results is then a joint "
            "effect of the run place and the tool contract it imposes, which is "
            "a narrower and defensible claim -- but it is still not an effect "
            "of the isolation alone, and must not be written as one."
        ),
        "already_matching": [
            item.field for item in comparisons if item.verdict == MATCHES
        ],
        "unchecked": [item.field for item in comparisons if item.verdict == UNKNOWN],
    }


#: Conditions under which the run stops for a technical reason.
#:
#: Every one of these says the run is no longer producing trustworthy records.
#: None of them is about how well the model did.
STOP_RULES: tuple[str, ...] = (
    "the deployment or model reported back differs from the pinned one",
    "a run switches model or deployment on its own",
    "the pre-registration seal no longer verifies against the recorded one",
    "a gate that this record says is shut reports itself open, without a "
    "reviewed change having opened it",
    "a paid call is about to happen with no recorded budget, or recorded "
    "spending passes the approved amount",
    "the cost ledger cannot be written, so spend would go unattributed",
    "the runner-defect disposition is returned for three consecutive tasks, "
    "which means this code and not the work under test is producing the record",
    "the guest cannot be cleaned up between tasks, so one task's state could "
    "reach the next",
)

#: Things that are results and are recorded as such. Written down beside the
#: stop rules because the temptation is to treat a bad number as a fault.
NOT_STOP_RULES: tuple[str, ...] = (
    "a task scoring badly, or scoring zero",
    "a task failing because the environment lacks a capability -- that is "
    "recorded with the capability named, and the six known absences are "
    "already explained in tasks/0822_saturday/"
    "guest_command_absences_explained.json",
    "the first five tasks not all succeeding; there is no target pass rate "
    "anywhere in this record, and a stage does not have to look good to "
    "proceed",
    "results disagreeing with A's Codex run",
)


def _what_this_is_not() -> list[str]:
    """The disclaimers, worked out rather than typed out.

    Both of the first two used to be sentences, and both went stale within a
    day of being written. One said the blocker was a role assignment in the
    subscription holding the model: that was the reading of a 401 which later
    turned out to have come from *past* the authentication gate, and stage A
    has since reached a real deployment and been charged for it. The other said
    the amount was the owner's to fill in, and on 2026-09-11 they filled in two.

    A disclaimer that outlives its fact is worse than no disclaimer, because it
    is read as current. The one about readiness names what is still not real
    rather than guessing at a cause, and the one about money asks
    :func:`~core.agentic_v2_stage_one_budget.stage_one_amount_note`, so it
    changes back by itself if the approval is ever withdrawn.

    Both feed the seal, so a change here is visible as a changed seal rather
    than as a quietly different record.
    """
    # Imported here rather than at module scope. The budget module reaches the
    # readiness report, which reaches back into this area of the code; the same
    # reason that module imports its own dependencies lazily.
    from core.agentic_v2_stage_one_budget import stage_one_amount_note

    unapproved = list(stage_one_amount_note())
    if unapproved:
        money = (
            "not an approval to spend. "
            + unapproved[0]
            + ". The amounts live in "
            "experiments/execution_envelope/agentic_stage_one_plan.yaml"
        )
    else:
        money = (
            "not an approval to spend more than the five-task cohort. Two "
            "amounts are approved in "
            "experiments/execution_envelope/agentic_stage_one_plan.yaml -- one "
            "for running the five tasks and one for marking their answers -- "
            "and they are whole-run figures for those five. The thirty and the "
            "two hundred and twenty are not priced, and "
            "scripts/run_agentic_v2_stage.py refuses them until they are"
        )

    return [
        # Named rather than diagnosed. What is missing is the isolation, which
        # this pre-registration itself fixes shut for stage one: a run that
        # opened exec_run would be a different experiment from the registered
        # one. Whether a guest could be booted at all is stage B's question and
        # is answered there.
        "not a statement that the environment is ready. No V2 task has run. "
        "What stage one registers is a run with exec_run shut and no guest "
        "booted, so the isolation is not exercised by it and no result from it "
        "is evidence that the sandbox contains anything",
        money,
        "not a prediction of how the run will go",
    ]


def _run_conditions() -> dict[str, Any]:
    """The conditions the run is held to, recorded before it starts.

    Model, deployment and resource; the prompt's source; the tools on offer;
    the token, time and retry ceilings. The point of pre-registering them is
    that a run which later turns out disappointing cannot be re-described as
    having been configured some other way.

    Almost none of it is written here. It is read out of
    ``agentic_stage_one_plan.yaml``, and that file is fingerprinted below, so a
    settings change after this record was sealed shows up as a mismatch rather
    than as a record quietly describing the wrong run. The one part the plan
    does not contain is the per-task ceilings, which are arithmetic on it — and
    those come from :func:`~core.agentic_v2_conversation_runner.ceilings_from`,
    the same function the runner enforces them with, for the same reason.

    What is deliberately *not* here: how the run is expected to go. That
    belongs to the results, and a pre-registration that carried a prediction
    would be an invitation to read the outcome against it.
    """
    # Lazily, like the money note above: the budget module reaches the
    # readiness report, which reaches back into this module.
    from core.agentic_v2_conversation_runner import ceilings_from
    from core.agentic_v2_stage_one_budget import (
        STAGE_ONE_PLAN_PATH,
        load_stage_one_plan,
    )

    plan = load_stage_one_plan()
    fixed = dict(plan.get("fixed_settings") or {})
    chosen_settings = dict(plan.get("cost", {}).get("chosen_settings") or {})

    class _Chosen:
        tool_calls_per_attempt = int(chosen_settings["tool_calls_per_attempt"])
        max_output_tokens_per_turn = int(
            chosen_settings["max_output_tokens_per_turn"]
        )

    ceilings = ceilings_from(plan, _Chosen)
    connection = dict(plan.get("azure_connection") or {})

    return {
        "read_from": str(STAGE_ONE_PLAN_PATH.relative_to(REPOSITORY_ROOT)),
        # The whole settings file, fingerprinted. Every field below is a copy
        # of something inside it, and this is what catches a copy going stale.
        "read_from_sha256": _digest_of(STAGE_ONE_PLAN_PATH),
        "model": {
            "deployment": plan["model"]["deployment"],
            "resolved_model": plan["model"]["resolved_model"],
            # A deployment name alone does not name a model. The same name in
            # another resource is another deployment, so the resource is part
            # of the condition rather than context for it.
            "account": connection.get("account"),
            "project": connection.get("project"),
            "route_profile": connection.get("route_profile"),
            "automatic_model_switch_allowed": fixed.get(
                "automatic_model_switch_allowed"
            ),
        },
        "prompt": {
            # Not reproduced. The wording is the benchmark's own, it is long,
            # and a copy here would be a second thing to keep in step. The
            # manifest above seals the dataset revision and the wording hash.
            "task_wording_comes_from": "the pinned dataset revision in `manifest`",
            "standing_instruction_length_assumed_from": (
                plan.get("cost", {}).get("assumptions_come_from")
            ),
            "self_review_enabled": fixed.get("self_review_enabled"),
        },
        "tools": {
            # All eight, which is what the model really sees: nothing in the
            # stage run narrows `tools_available`, and its default is the whole
            # contract. Listing seven here would have been a nicer-sounding
            # description of a run that does not happen.
            "offered": list(TOOL_NAMES),
            # Offered and shut are not the same thing, and the difference is
            # the point. exec_run is in the list above, the model may choose
            # it, and what comes back is `capability_unavailable`. How a model
            # reacts to a refused capability is a finding this run can collect;
            # a model that never saw the tool could produce no such finding.
            "offered_but_refuses_everything": ["exec_run"],
            "exec_run_open": fixed.get("exec_run_open"),
            "comes_from": "core/agentic_v2_contract.py TOOL_NAMES",
            "narrowed_by_the_run": False,
        },
        "per_task_ceilings": ceilings.as_dict(),
        "how_the_ceilings_were_derived": {
            "chosen_settings": chosen_settings,
            "turns": "one model call per tool call, plus the turn that finalises",
            "input_tokens": (
                "quadratic in the number of turns, because the loop re-sends "
                "the whole conversation every turn"
            ),
            "seconds": "per_task_timeout_seconds, straight from the plan",
            "comes_from": "core/agentic_v2_conversation_runner.py ceilings_from",
        },
        "retry": {
            "max_attempts": fixed.get("retry_max_attempts"),
            "reasons_allowed": list(fixed.get("retry_reasons_allowed") or []),
            # Three kinds, kept apart in the record. An infrastructure retry is
            # the environment's fault and a task that needed several says
            # something about the environment rather than about the model; a
            # semantic one is the model changing its mind, which is the thing
            # being measured; an internal one is the client library's own,
            # below the level either of those is about. Collapsed into one
            # count, a flaky endpoint reads as an indecisive model.
            "kinds_recorded_separately": [
                "infrastructure",
                "semantic",
                "internal",
            ],
            "max_repeats_of_one_request": ceilings.max_repeats_of_one_request,
        },
        "what_stops_a_task": (
            "any per-task ceiling above, or the per-task budget, whichever "
            "comes first. A task stopped by a ceiling is recorded as stopped "
            "by that ceiling and is not a model failure"
        ),
    }


#: The files in the pinned dataset that cannot be handed to the task that names
#: them, with the size that decides it.
#:
#: Recorded here rather than measured at generation time, because a
#: pre-registration has to derive on a machine that has not downloaded the
#: dataset -- the committed copy is checked against the code in CI, where the
#: files are absent. A written-down size is normally the thing that goes stale;
#: this one cannot, because the revision it was measured against is pinned in
#: the manifest beside it, and :func:`verify_input_disposition` turns it back
#: into a measurement anywhere the files are present.
UNDELIVERABLE_INPUTS: tuple[dict[str, Any], ...] = (
    {
        "task_id": "a941b6d8-4289-4500-b45a-f8e4fc94a724",
        "occupation": "Film and Video Editors",
        "path": "reference_files/67469cf2a7509f149c095cf4f6542f6d/TWT_A001_03.mp4",
        "size_bytes": 689_061_330,
        "reason": TOO_LARGE,
    },
)


#: How many of the files the 220 tasks name the model could open by itself, if
#: nothing were rendered for it.
#:
#: Measured by decoding every one of them as UTF-8 against the pinned revision,
#: because that is exactly what ``workspace_apply(read)`` does and the only way
#: the model can open anything while ``exec_run`` is shut. Three succeed: two
#: CAD ``.STEP`` files, which are plain text, and one ``.txt``. The other 258 do
#: not, and no amount of retrying changes that.
#:
#: This is the figure that decides whether a V2 result is about the model at
#: all, so it is recorded rather than described. Before the renderings existed,
#: a run of 220 tasks would have been 220 models writing from the prompt alone.
FILES_THE_MODEL_COULD_OPEN_UNAIDED = 3
FILES_NAMED_BY_THE_TASKS = 261


#: The files that fit the compute contract but not the fixture workspace, with
#: what a text rendering recovers from each.
#:
#: A second limit, found after the first and much worse behaved. The fixture
#: workspace applies a 1 MiB per-file limit during a walk over everything it
#: holds, and that walk runs on *write* -- so one oversized file staged anywhere
#: under the workspace does not cost the task that file, it costs the task every
#: deliverable it would ever write. The model is told only
#: ``fixture_backend_error``, so it retries until its call budget is gone, and
#: the record afterwards shows a model that produced nothing.
#:
#: Recorded by name for the same reason as the list above, and with the same
#: consequence if it is wrong: a cohort losing an input that nothing planned for
#: is indistinguishable from a model doing the work badly.
#:
#: ``rendered_characters`` is what :mod:`core.file_reader` reads out of the
#: original, measured against the same revision. Five of the twenty-four hold
#: real text -- a 14.5 MB spreadsheet comes back as 1,973 characters. Eighteen
#: are recordings, archives or images, where the reader returns a label and the
#: model is no worse off than before. One, a scanned PDF, renders to nothing.
OVER_THE_WORKSPACE_FILE_LIMIT: tuple[dict[str, Any], ...] = (
    {"task_id": "a941b6d8-4289-4500-b45a-f8e4fc94a724", "occupation": "Film and Video Editors", "path": "reference_files/67469cf2a7509f149c095cf4f6542f6d/TWT_A001_03.mp4", "size_bytes": 689_061_330, "rendered_characters": 129},
    {"task_id": "75401f7c-396d-406d-b08e-938874ad1045", "occupation": "Film and Video Editors", "path": "reference_files/04fe2846f45b476d5231b53beeae767a/reel footage.zip", "size_bytes": 333_716_426, "rendered_characters": 39},
    {"task_id": "a941b6d8-4289-4500-b45a-f8e4fc94a724", "occupation": "Film and Video Editors", "path": "reference_files/d88a33c7e63981a67e899cc8c1347ece/TWT_001_02.mp4", "size_bytes": 230_703_477, "rendered_characters": 127},
    {"task_id": "4b894ae3-1f23-4560-b13d-07ed1132074e", "occupation": "Audio and Video Technicians", "path": "reference_files/10844d4ba6b1f18120245109db76f403/State of Affairs_STEM_DRUMS.wav", "size_bytes": 58_752_102, "rendered_characters": 146},
    {"task_id": "4b894ae3-1f23-4560-b13d-07ed1132074e", "occupation": "Audio and Video Technicians", "path": "reference_files/2adacf89b84661aadd0c80d91a81fb73/State of Affairs_ROUGHMIX.wav", "size_bytes": 58_752_102, "rendered_characters": 144},
    {"task_id": "4b894ae3-1f23-4560-b13d-07ed1132074e", "occupation": "Audio and Video Technicians", "path": "reference_files/88944520f1ce15927dd5a6a08d3ee9b2/State of Affairs_STEM_ORGAN.wav", "size_bytes": 58_752_102, "rendered_characters": 146},
    {"task_id": "38889c3b-e3d4-49c8-816a-3cc8e5313aba", "occupation": "Audio and Video Technicians", "path": "reference_files/028fb83486152124cfecf2667c3cef37/DRUM REFERENCE TRACK.wav", "size_bytes": 33_554_432, "rendered_characters": 139},
    {"task_id": "4b894ae3-1f23-4560-b13d-07ed1132074e", "occupation": "Audio and Video Technicians", "path": "reference_files/073946a18125717bdad58178466039fd/State of Affairs_STEM_BASS.wav", "size_bytes": 33_554_432, "rendered_characters": 145},
    {"task_id": "4b894ae3-1f23-4560-b13d-07ed1132074e", "occupation": "Audio and Video Technicians", "path": "reference_files/48836e54ef271e8fd1a301d3e20ea470/State of Affairs_STEM_ACGTRS.wav", "size_bytes": 33_554_432, "rendered_characters": 147},
    {"task_id": "ff85ee58-bc9f-4aa2-806d-87edeabb1b81", "occupation": "Audio and Video Technicians", "path": "reference_files/ca53448cbec7b57b575d9d0e229f08c4/TAVARUA_MUSIC ONLY.wav", "size_bytes": 32_140_902, "rendered_characters": 137},
    {"task_id": "ff85ee58-bc9f-4aa2-806d-87edeabb1b81", "occupation": "Audio and Video Technicians", "path": "reference_files/758a72de9d221d7aa2707e554c20459d/TAVARUA_SAX RAW.wav", "size_bytes": 22_031_470, "rendered_characters": 133},
    {"task_id": "11593a50-734d-4449-b5b4-f8986a133fd8", "occupation": "Real Estate Sales Agents", "path": "reference_files/1e15759c2909d91e9cd6024813a1a1f7/Massabama active listings.xlsx", "size_bytes": 14_509_694, "rendered_characters": 1_973},
    {"task_id": "57b2cdf2-ad62-4591-aa91-aad489740320", "occupation": "Private Detectives and Investigators", "path": "reference_files/74e9b9b1de3156972930ebb7d4d5321a/Photographs.zip", "size_bytes": 9_507_893, "rendered_characters": 36},
    {"task_id": "45c6237b-f9c9-4526-9a8d-6a5c404624ec", "occupation": "First-Line Supervisors of Retail Sales Workers", "path": "reference_files/2c0a245a7c98c858b2ae975c7bbab3b6/ORDER LIST.pdf", "size_bytes": 6_984_257, "rendered_characters": 0},
    {"task_id": "75401f7c-396d-406d-b08e-938874ad1045", "occupation": "Film and Video Editors", "path": "reference_files/9f47a167476d2ff6ecc485f97e8341c9/action-energetic-rock-music-334316.mp3", "size_bytes": 5_302_229, "rendered_characters": 145},
    {"task_id": "a46d5cd2-55fe-48fa-a4c6-6aaf6b9991b5", "occupation": "Private Detectives and Investigators", "path": "reference_files/f4c7bfae38d21c8ad4f4b624d194aab4/Photographs.zip", "size_bytes": 4_415_094, "rendered_characters": 36},
    {"task_id": "3a4c347c-4aec-43c7-9a54-eb1f816ab1f9", "occupation": "Editors", "path": "reference_files/1389fc5af6430c02dd7bd93c7ce05cc7/Boilerplate.docx", "size_bytes": 2_898_134, "rendered_characters": 2_456},
    {"task_id": "46b34f78-6c06-4416-87e2-77b6d8b20ce9", "occupation": "Financial and Investment Analysts", "path": "reference_files/40407caad9b871b09e3a075bdd971b15/Research Material.docx", "size_bytes": 2_799_328, "rendered_characters": 105},
    {"task_id": "01d7e53e-0513-4109-a242-8ccaf442cd21", "occupation": "Recreation Workers", "path": "reference_files/21f10d79c065e77a3e36c952a0c3b3b8/Recreare Parks & Recreation Summer Fun Facilities.docx", "size_bytes": 2_315_023, "rendered_characters": 2_615},
    {"task_id": "5d0feb24-e8b6-4ace-b64f-d5cd1a8b563d", "occupation": "News Analysts, Reporters, and Journalists", "path": "reference_files/c575a5476fac2f921cfd192ca5c48622/TRAPPIST-1 Reporter Draft.docx", "size_bytes": 1_913_096, "rendered_characters": 4_446},
    {"task_id": "f2986c1f-2bbf-4b83-bc93-624a9d617f45", "occupation": "Pharmacists", "path": "reference_files/8860a54103b6edb9313d04c0f4434980/what are these.jpg", "size_bytes": 1_800_970, "rendered_characters": 49},
    {"task_id": "4d1a8410-e9c5-4be5-ab43-cc55563c594c", "occupation": "First-Line Supervisors of Office and Administrative Support Workers", "path": "reference_files/6940c7b0ba1ffdcbce4266eba053a9e4/Floor Layout for Interviews.png", "size_bytes": 1_675_294, "rendered_characters": 63},
    {"task_id": "3c19c6d1-672c-467a-8437-6fe21afb8eae", "occupation": "Project Management Specialists", "path": "reference_files/ca6c768fe272f61c00d001c884c42237/INPUT 4 BridgeMind AI POC deployment PROJECT LOG.docx", "size_bytes": 1_398_074, "rendered_characters": 8_794},
    {"task_id": "ff85ee58-bc9f-4aa2-806d-87edeabb1b81", "occupation": "Audio and Video Technicians", "path": "reference_files/7b740f4720fe70f8b445fd059e1912f5/TAVARUA_SAX REFERENCE MP3.mp3", "size_bytes": 1_094_950, "rendered_characters": 135},
)


def input_disposition(catalog: TaskCatalog | None = None) -> dict[str, Any]:
    """What each cohort is given to work from, and what it cannot be given.

    Written before the run because the alternative is writing it after, when
    the only task in the two hundred and twenty that loses a file has already
    produced a result -- and a shortfall explained afterwards reads as an
    excuse for it, whatever the record says.

    The shape of the problem is narrow enough to state exactly. Across the
    three cohorts one file is undeliverable: a 689 MB clip, over the compute
    contract's own per-file limit by 152 MB. It belongs to a Film and Video
    Editors task that names two clips, so the task is not left with nothing --
    it is left with half its footage, which is the more dangerous outcome,
    because an edit made from half the material looks like a bad edit rather
    than a missing input. Neither smaller stage contains that task, so the
    first two stages have nothing refused at all.

    No substitute is made. Subtitles, extracted frames or a summary would each
    be a different task from the one the dataset states, and swapping one in
    silently would mean reporting a score for work nobody set.

    Two later measurements sit underneath that and change what a result means.

    *Almost nothing here can be opened.* The model's only reader decodes UTF-8,
    and 258 of the 261 files fail to decode. Without help, a run of 220 tasks
    would be 220 models writing from the prompt alone while their inputs sat
    unopened beside them — and every one of those results would look like the
    model's work. A text rendering is therefore staged beside each file that has
    one. That is a compensation, it is lossy, and it is a difference from the
    Codex run, whose model has a shell and opens these files itself. It is
    recorded in all three of those terms rather than as a fix.

    *A second size limit costs a task everything, not one file.* Twenty-four
    files sit under the compute contract's per-file limit and over the fixture
    workspace's, and the workspace applies its limit while walking everything it
    holds — on write. One of them staged, and the task can write no deliverable
    at all. Nought of the five advance-check tasks are affected, three of the
    thirty, sixteen of the two hundred and twenty: stage one would have passed
    clean and stage two would have failed about a fifth of the time for no
    visible reason. They are refused by name instead, and the text inside them,
    where there is any, is rendered.
    """
    catalog = catalog or load_task_catalog()
    chosen = cohorts(catalog)
    by_id = catalog.by_task_id()
    by_task: dict[str, list[dict[str, Any]]] = {}
    for one in UNDELIVERABLE_INPUTS:
        by_task.setdefault(str(one["task_id"]), []).append(dict(one))
    over_limit_by_task: dict[str, list[dict[str, Any]]] = {}
    for one in OVER_THE_WORKSPACE_FILE_LIMIT:
        over_limit_by_task.setdefault(str(one["task_id"]), []).append(dict(one))

    per_stage: dict[str, Any] = {}
    for stage in ESCALATION:
        task_ids = chosen[stage]
        tasks = [by_id[one] for one in task_ids if one in by_id]
        naming = [one for one in tasks if one.reference_file_count]
        refused = [
            dict(entry, task_id=task_id)
            for task_id in task_ids
            for entry in by_task.get(str(task_id), ())
        ]
        over_limit = [
            dict(entry, task_id=task_id)
            for task_id in task_ids
            for entry in over_limit_by_task.get(str(task_id), ())
        ]
        per_stage[stage] = {
            "tasks": len(task_ids),
            "tasks_naming_reference_files": len(naming),
            "files_named": sum(one.reference_file_count for one in naming),
            "files_that_cannot_be_delivered": refused,
            "files_too_large_for_the_workspace": over_limit,
            "tasks_affected_by_the_workspace_limit": len(
                {str(one["task_id"]) for one in over_limit}
            ),
        }

    return {
        "staged_into": (
            f"{MODEL_INPUT_PREFIX}/ inside each task's own workspace, one "
            "workspace per attempt, copied from the same revision the prompt "
            "text comes from"
        ),
        "limits": {
            "max_files_per_task": MAX_INPUT_FILES,
            "max_bytes_per_file": MAX_INPUT_SINGLE,
            "max_bytes_per_task": MAX_INPUT_TOTAL,
            "come_from": "core/agentic_compute.py",
            "max_bytes_per_file_in_the_workspace": WORKSPACE_FILE_LIMIT,
            "the_workspace_limit_comes_from": (
                "core/agentic_v2_fixture_backend.py, and it is enforced while "
                "walking the whole workspace rather than on the file being "
                "touched. The walk runs on write, so one file over it stops the "
                "task writing anything at all and the model is told only "
                "fixture_backend_error"
            ),
        },
        "per_stage": per_stage,
        "what_the_model_can_open_by_itself": {
            "files_named_by_the_tasks": FILES_NAMED_BY_THE_TASKS,
            "files_that_decode_as_utf8": FILES_THE_MODEL_COULD_OPEN_UNAIDED,
            "how_that_was_measured": (
                "every one of them decoded as UTF-8 against the pinned "
                "revision, which is what workspace_apply(read) does. Two CAD "
                ".STEP files and one .txt succeed; the other 258 do not"
            ),
            "why_it_matters": (
                "with exec_run shut there is no shell, no pandas and no PDF "
                "library, so a read is the only way in. A model that cannot "
                "open its inputs and writes from the prompt alone produces a "
                "result that looks exactly like a model that did the work badly"
            ),
        },
        "text_renderings": {
            "what_they_are": (
                "a text extraction made by core.file_reader and staged beside "
                f"the file it came from, under {MODEL_INPUT_PREFIX}/extracted/. "
                "All 261 files extract without error; what comes out is text "
                "for spreadsheets, PDFs and documents, and a one-line label for "
                "images, recordings and archives"
            ),
            "never_a_replacement": (
                "the original stays where it is whenever it can be staged, and "
                "a rendering is never presented as the file. Layout, images, "
                "styling and anything a picture carries are lost, and a long "
                "one is cut to fit the workspace limit and says so at the cut"
            ),
            "this_is_a_difference_from_the_codex_run": (
                "A's model has a real shell and opens these files itself. A V2 "
                "result on a task whose work needed what a rendering loses is "
                "not comparable to A's result on the same task, and this is the "
                "record that says so before either is run"
            ),
            "how_to_check_this": (
                "core.agentic_v2_reference_staging.stage_task_reference_files "
                "with render_text=True, and the per-file outcomes it records"
            ),
        },
        "no_substitute_is_made": (
            "a file that cannot be delivered is recorded as not delivered. "
            "Nothing is put in its place -- subtitles, frames or a summary "
            "would each be a different task from the one the dataset sets, and "
            "a score reported against a task nobody set is worse than a gap"
        ),
        "what_a_failure_there_does_not_show": (
            "a task that ran without a file it named is not evidence about the "
            "model. It is recorded with the missing file's name so the two "
            "cannot be read as one. Nor is a task that was handed files it "
            "could not open: that one is recorded separately again, because a "
            "task holding only unreadable files has nothing refused and would "
            "otherwise be indistinguishable from a task given everything"
        ),
        "how_to_check_this": (
            "core.agentic_v2_preregistration.verify_input_disposition for the "
            "sizes and core.agentic_v2_preregistration.verify_reader_reach for "
            "what can be opened, both against a copy of the pinned revision"
        ),
    }


def _decodes_as_utf8(path: Path) -> bool:
    """Whether the model's reader could open this file at all.

    Streamed and abandoned at the first bad byte rather than read whole, because
    the largest file here is 689 MB and the answer for it is settled inside the
    first few. Incremental rather than chunk-by-chunk decoding, so a multi-byte
    character split across a chunk boundary is not mistaken for binary.
    """
    import codecs

    decoder = codecs.getincrementaldecoder("utf-8")()
    try:
        with path.open("rb") as handle:
            while chunk := handle.read(65536):
                decoder.decode(chunk)
            decoder.decode(b"", final=True)
    except (UnicodeDecodeError, OSError):
        return False
    return True


def verify_input_disposition(
    snapshot_root: Path, catalog: TaskCatalog | None = None
) -> list[str]:
    """Everything the recorded disposition gets wrong about the files on disk.

    Both directions, and the second is the one worth having. That a recorded
    size is still the file's size catches an edit; that no *other* file has
    grown past a limit catches the case nobody would look for -- a cohort
    quietly losing an input that no record mentions, which is indistinguishable
    from a model that did the work badly.

    Sizes are read through whatever the name points at, links included. That is
    the opposite of what staging does, and deliberately: this is measuring the
    dataset, not handing bytes to a model, and refusing to measure a cache
    would leave the check unrunnable on the machine most likely to run it.
    """
    catalog = catalog or load_task_catalog()
    by_id = catalog.by_task_id()
    recorded = {str(one["path"]): one for one in UNDELIVERABLE_INPUTS}
    over_workspace = {
        str(one["path"]): one for one in OVER_THE_WORKSPACE_FILE_LIMIT
    }
    wrong: list[str] = []

    for path, entry in recorded.items():
        full = snapshot_root / path
        if not full.exists():
            wrong.append(f"{path} is recorded as undeliverable but is not present")
            continue
        size = full.stat().st_size
        if size != entry["size_bytes"]:
            wrong.append(
                f"{path} is recorded as {entry['size_bytes']} bytes and is "
                f"{size}. The pinned revision is supposed to make that "
                "impossible, so either the root is a different revision or the "
                "record was edited"
            )
        elif size <= MAX_INPUT_SINGLE:
            wrong.append(
                f"{path} is recorded as undeliverable but {size} bytes is "
                f"within the {MAX_INPUT_SINGLE} byte limit"
            )

    for path, entry in over_workspace.items():
        full = snapshot_root / path
        if not full.exists():
            wrong.append(
                f"{path} is recorded as over the workspace file limit but is "
                "not present"
            )
            continue
        size = full.stat().st_size
        if size != entry["size_bytes"]:
            wrong.append(
                f"{path} is recorded as {entry['size_bytes']} bytes and is "
                f"{size}, so the workspace-limit record was measured against "
                "something other than this revision"
            )
        elif size <= WORKSPACE_FILE_LIMIT:
            wrong.append(
                f"{path} is recorded as over the workspace file limit but "
                f"{size} bytes is within the {WORKSPACE_FILE_LIMIT} byte limit"
            )

    for task_id in full_run_tasks(catalog):
        task = by_id.get(str(task_id))
        if task is None:
            continue
        running = 0
        for path in task.reference_file_paths:
            full = snapshot_root / path
            if not full.exists():
                wrong.append(f"{path}, named by {task_id}, is not in the snapshot")
                continue
            size = full.stat().st_size
            running += size
            if size > MAX_INPUT_SINGLE and path not in recorded:
                wrong.append(
                    f"{path}, named by {task_id}, is {size} bytes and over the "
                    f"{MAX_INPUT_SINGLE} byte limit, and no record says so. A "
                    "cohort would lose it without anything having planned for it"
                )
            if size > WORKSPACE_FILE_LIMIT and path not in over_workspace:
                # The one worth having. An unrecorded file in this band does not
                # cost its task that file, it costs the task every deliverable,
                # and the model is told nothing usable about why.
                wrong.append(
                    f"{path}, named by {task_id}, is {size} bytes and over the "
                    f"{WORKSPACE_FILE_LIMIT} byte workspace limit, and no "
                    "record says so. Staged, that task could write nothing at "
                    "all and would read afterwards as a model that produced "
                    "nothing"
                )
        if running > MAX_INPUT_TOTAL:
            wrong.append(
                f"{task_id} names {running} bytes in total, over the "
                f"{MAX_INPUT_TOTAL} byte limit, and no record says so"
            )
        if task.reference_file_count > MAX_INPUT_FILES:
            wrong.append(
                f"{task_id} names {task.reference_file_count} files, over the "
                f"{MAX_INPUT_FILES} file limit, and no record says so"
            )

    return wrong


def verify_reader_reach(
    snapshot_root: Path, catalog: TaskCatalog | None = None
) -> list[str]:
    """Whether the model could still open only three of its own input files.

    Kept apart from :func:`verify_input_disposition` because the two ask
    different questions of the same files. That one reads sizes, which a tree of
    empty files can answer; this one reads contents, which only the real bytes
    can. Merged, the size check would have to be run against real data to pass,
    and the machine most likely to run it has none.

    The figure matters more than its precision. If it moves upward, some file
    became readable and the renderings matter less; if it moves downward, a run
    is closer to 220 models writing from the prompt alone. Either way the
    pre-registration describes a different experiment from the one that ran.
    """
    catalog = catalog or load_task_catalog()
    by_id = catalog.by_task_id()
    missing: list[str] = []
    readable = 0
    seen = 0

    for task_id in full_run_tasks(catalog):
        task = by_id.get(str(task_id))
        if task is None:
            continue
        for path in task.reference_file_paths:
            full = snapshot_root / path
            if not full.exists():
                missing.append(f"{path}, named by {task_id}, is not in the snapshot")
                continue
            seen += 1
            if _decodes_as_utf8(full):
                readable += 1

    wrong = list(missing)
    if seen != FILES_NAMED_BY_THE_TASKS:
        wrong.append(
            f"{seen} files were measured and the record is written about "
            f"{FILES_NAMED_BY_THE_TASKS}"
        )
    if readable != FILES_THE_MODEL_COULD_OPEN_UNAIDED:
        wrong.append(
            f"{readable} of the named files decode as UTF-8, and the record "
            f"says {FILES_THE_MODEL_COULD_OPEN_UNAIDED}. That figure is what "
            "decides whether a result is about the model, so a record that has "
            "it wrong is worse than none"
        )
    return wrong


def record(catalog: TaskCatalog | None = None) -> dict[str, Any]:
    """The whole pre-registration, as it is committed before anything runs."""
    # Loaded once and handed down. Two sections derive from the catalogue and
    # each would otherwise load its own copy, which is slower and -- worse --
    # would let one section describe a catalogue the other had not read.
    catalog = catalog or load_task_catalog()
    comparisons = compare_with_codex_run()
    allowed, blockers = may_attribute_difference_to_environment(comparisons)
    body = {
        "what_this_is": (
            "what a V2 run is committed to before it starts. Committed ahead of "
            "execution so that a later result cannot be described as having "
            "been planned this way when it was not."
        ),
        "escalation": list(ESCALATION),
        "manifest": manifest(catalog),
        "run_conditions": _run_conditions(),
        "inputs": input_disposition(catalog),
        "comparison_with_codex": {
            "source": str(CODEX_TRIAL_PLAN.relative_to(REPOSITORY_ROOT)),
            # The basis of the comparison, fingerprinted. If A's file moves, the
            # comparison above describes a configuration that no longer exists,
            # and this is what says so rather than leaving the record quietly
            # stale.
            "source_sha256": _digest_of(CODEX_TRIAL_PLAN),
            "fields": [
                {
                    "field": item.field,
                    "verdict": item.verdict,
                    "removable": item.removable,
                    "why": item.why,
                }
                for item in comparisons
            ],
            "may_call_a_difference_an_environment_effect": allowed,
            "why_not": blockers,
            "residual_after_alignment": residual_after_alignment(comparisons),
        },
        "stop_rules": list(STOP_RULES),
        "not_stop_rules": list(NOT_STOP_RULES),
        "what_this_is_not": _what_this_is_not(),
    }
    body["seal"] = seal(body)
    return body
