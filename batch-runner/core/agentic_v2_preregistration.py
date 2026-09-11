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

from core.agentic_v2_contract import TOOL_NAMES
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


def record(catalog: TaskCatalog | None = None) -> dict[str, Any]:
    """The whole pre-registration, as it is committed before anything runs."""
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
        "what_this_is_not": [
            "not a statement that the environment is ready -- at the time of "
            "writing no V2 task has run, and the blocker is a role assignment "
            "in the subscription that holds the model",
            "not an approval to spend; the amount lives in "
            "experiments/execution_envelope/agentic_stage_one_plan.yaml and is "
            "the owner's to fill in",
            "not a prediction of how the run will go",
        ],
    }
    body["seal"] = seal(body)
    return body
