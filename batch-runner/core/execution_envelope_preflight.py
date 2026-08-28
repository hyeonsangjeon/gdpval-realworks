"""The complete free check that must pass before the comparison spends anything.

This is the last gate before money is involved. It ties together every check
that can be made without calling a model:

* the run places are graded from the code in this repository, and one that
  cannot run is never quietly replaced by one that can;
* the five tasks written into the plan are re-derived from the fixed rule and
  compared, so a task list cannot drift after results are seen;
* every input file is read off this machine and its fingerprint compared, all
  64 characters of it, against what the plan wrote down. A file no copy of
  which is reachable is reported as unchecked, never as correct;
* each run place's experiment settings file is opened and compared against the
  shared conditions, so no run place can use a different model, a different
  deployment, different wording in any part of the prompt, a different task
  list, a different answer length, a different time limit, or a different
  number of attempts. Which settings get compared is read out of the files
  rather than listed here, so a setting added later is compared too;
* the Docker run place is confirmed to be unable to fall back to the server's
  own operating system;
* the three Agentic Sandbox V2 guards are exercised and must still refuse;
* the largest possible bill is worked out and compared against the amount
  approved unless the plan records an explicit owner-approved measurement run.
  In that mode cost gaps remain visible findings but do not block. Where the
  number the bill rests on can be read off the settings instead of being taken
  on trust, it is: the container's own file says how many times one attempt
  asks a model, and the plan is refused if it prices fewer. Where that file
  lets the container ask twice, the repair prompt says how much of the run's
  own output comes back with the second question, and the plan is refused if it
  prices less than that. Whether one cap on answer length covers a whole
  attempt is read from the runner that sends the request, and a plan that
  claims one cap where the caller really opens a fresh request each turn is
  refused. What a reference file adds to the prompt is read from the module
  that assembles it, against the sections each run place says it fills, so the
  per-file figure cannot quietly fall below what a file really sends.

Nothing here calls a model, signs in to a cloud account, or spends anything.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from decimal import Decimal, ROUND_CEILING
from importlib import import_module
from pathlib import Path
from typing import Any, Mapping

import yaml

from core.execution_envelope_cost import (
    CostCeiling,
    CostAssumptions,
    ModelPrice,
    REFERENCE_FILE_CHARACTER_CAP,
    check_cost_ceiling,
    describe_cost_ceiling,
    estimate_cost_ceiling,
    load_price_table,
)
from core.execution_envelope_grading_cost import (
    check_assumptions_cover_the_caps,
    read_grading_caps,
)
from core.execution_envelope_azure import (
    AzureConnectionDiagnosis,
    AzureConnectionRequirement,
    diagnose_azure_connection,
)
from core.execution_envelope_tasks import (
    InputFileVerification,
    TaskCatalog,
    catalog_number_problems,
    check_catalog_carries_no_scores,
    load_task_catalog,
    select_advance_check_tasks,
    selection_matches,
    verify_input_file_versions,
    widest_occupation,
    widest_scoring_line_characters,
)
from core.execution_environment_readiness import (
    COMPARISON_SAME_GENERATED_CODE,
    ENVIRONMENT_AZURE_CODE_INTERPRETER,
    ENVIRONMENT_DOCKER_CONTAINER,
    ENVIRONMENT_HOST_PYTHON_PROCESS,
    EXECUTION_MODE_BY_ENVIRONMENT,
    PAID_RUN_APPROVAL_VARIABLE,
    RUNNER_CLASS_BY_ENVIRONMENT,
    SERVING_PATH_MICROSOFT_FOUNDRY_DEPLOYMENT,
    ModelRunConditions,
    ReadinessReport,
    build_readiness_report,
)
from core.file_preview import reference_file_prompt_budget
from core.prompt_loader import fixed_prompt_characters, load_prompt

PLAN_VERSION = "execution-envelope-advance-check-v1"
COST_POLICY_BLOCK = "block_on_cost_findings"
COST_POLICY_RECORD_ONLY = "record_cost_findings_only"
VALID_COST_POLICIES = {COST_POLICY_BLOCK, COST_POLICY_RECORD_ONLY}

# The one container setting that stops a missing container from being replaced
# by the server's own operating system.
REQUIRED_CONTAINER_SETTING = "always"

# Which run places this plan is allowed to name. The five that are left out
# are left out because they cannot run, not because they were forgotten: the
# agent sandbox is still a structure check, and the four whole-product places
# have no code here at all.
COMPARABLE_ENVIRONMENTS = (
    ENVIRONMENT_HOST_PYTHON_PROCESS,
    ENVIRONMENT_DOCKER_CONTAINER,
    ENVIRONMENT_AZURE_CODE_INTERPRETER,
)


@dataclass
class EnvelopePreflight:
    """Everything the free check found, and whether anything may start."""

    readiness: ReadinessReport
    cost: CostCeiling | None
    problems: list[str] = field(default_factory=list)
    approved_maximum_usd: Decimal | None = None
    cost_policy: str = COST_POLICY_BLOCK
    cost_findings: list[str] = field(default_factory=list)
    available_monthly_credit_usd: Decimal | None = None
    azure: AzureConnectionDiagnosis | None = None
    grading_ceiling_problems: list[str] = field(default_factory=list)
    """Ways the marking half of the cost sum sits below what marking allows.

    Kept apart from the general problem list because these say something the
    other problems do not: the worked-out total printed above them is itself
    too low. A reader who sees only the total needs to be told that.
    """
    input_files: dict[str, InputFileVerification] = field(default_factory=dict)
    """How thoroughly each run place's input fingerprints were checked.

    Kept even when nothing is wrong, because "checked against the real file"
    and "assumed correct" are different answers and the reader is entitled to
    know which one they got.
    """
    missing_input_file_problems: list[str] = field(default_factory=list)
    """Input files no copy of which is on the machine running this check.

    Kept apart from the general problem list for the same reason the marking
    notes are: it says something the others do not. Every other problem here
    reports a fault in the plan or the settings, and reports it identically
    wherever the check is run. This one reports a limit of *this machine* — a
    fingerprint that could not be compared because the bytes were not here to
    compare it against. It still stops a run, because an unchecked fingerprint
    is not evidence, and it clears for nothing by fetching the pinned revision.
    """

    @property
    def all_problems(self) -> list[str]:
        """Every problem found, wherever it was found.

        The readiness check keeps its own list. Merging them here means a
        reader is never told the comparison may not start without being told
        why.
        """
        merged = list(self.problems)
        for note in self.readiness.problems:
            if note not in merged:
                merged.append(note)
        return merged

    @property
    def may_start(self) -> bool:
        return not self.all_problems and self.readiness.ready

    def as_dict(self) -> dict[str, Any]:
        return {
            "may_start": self.may_start,
            "readiness": self.readiness.as_dict(),
            "cost_ceiling": self.cost.as_dict() if self.cost is not None else None,
            "approved_maximum_usd": (
                str(self.approved_maximum_usd)
                if self.approved_maximum_usd is not None
                else None
            ),
            "cost_policy": self.cost_policy,
            "cost_findings": list(self.cost_findings),
            "cost_findings_block_execution": self.cost_policy == COST_POLICY_BLOCK,
            "available_monthly_credit_usd": (
                str(self.available_monthly_credit_usd)
                if self.available_monthly_credit_usd is not None
                else None
            ),
            "problems": self.all_problems,
            "grading_ceiling_problems": list(self.grading_ceiling_problems),
            "marking_half_is_a_ceiling": not self.grading_ceiling_problems,
            "missing_input_file_problems": list(self.missing_input_file_problems),
            "every_input_file_was_read": not self.missing_input_file_problems,
            "azure_connection": (
                self.azure.as_dict() if self.azure is not None else None
            ),
            "input_files": {
                environment: verification.as_dict()
                for environment, verification in sorted(self.input_files.items())
            },
        }


@dataclass
class GradingCostInspection:
    """Separate broken configuration from incomplete cost knowledge."""

    structural_problems: list[str] = field(default_factory=list)
    cost_findings: list[str] = field(default_factory=list)

    @property
    def all_findings(self) -> list[str]:
        return [*self.structural_problems, *self.cost_findings]


def load_plan(path: str | Path) -> dict:
    """Read the plan file that holds the conditions all run places share."""
    target = Path(path)
    loaded = yaml.safe_load(target.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("the plan file must hold a mapping at the top level")
    return loaded


def conditions_from_plan(plan: Mapping[str, Any]) -> dict[str, ModelRunConditions]:
    """Build each run place's conditions from the shared block plus its own.

    One value is filled in rather than read: the Microsoft Foundry resource.
    The plan already names it once, in the ``azure_connection`` block the
    connection check reads, and a second copy could drift from the first with
    nothing to notice. Only run places whose model comes from that resource
    inherit it; a place served by somebody else's model has to say so itself,
    because there is nothing there to inherit.
    """
    raw = plan.get("model_run_conditions")
    if not isinstance(raw, Mapping):
        raise ValueError("the plan has no model_run_conditions block")
    shared = raw.get("shared") or {}
    per_environment = raw.get("by_environment")
    if not isinstance(per_environment, Mapping):
        raise ValueError("model_run_conditions.by_environment must be a mapping")
    account = str(
        (dict(plan.get("azure_connection") or {})).get("account") or ""
    )
    resolved: dict[str, ModelRunConditions] = {}
    for environment, override in per_environment.items():
        merged = dict(shared)
        merged.update(dict(override or {}))
        if "resource" not in merged:
            wants_foundry = merged.get("model_serving_path") == (
                SERVING_PATH_MICROSOFT_FOUNDRY_DEPLOYMENT
            )
            if wants_foundry and account:
                merged["resource"] = account
            elif wants_foundry:
                raise ValueError(
                    f"{environment} takes its model from a Microsoft Foundry "
                    "deployment, but the plan's azure_connection block names "
                    "no account, so the deployment name on its own does not "
                    "say which model would answer"
                )
            else:
                raise ValueError(
                    f"{environment} does not take its model from the "
                    "Microsoft Foundry resource this plan pins, so it has to "
                    "name the resource its model comes from itself; there is "
                    "nothing here for it to inherit"
                )
        resolved[str(environment)] = ModelRunConditions.from_mapping(merged)
    return resolved


def check_container_cannot_fall_back(plan: Mapping[str, Any]) -> list[str]:
    """Confirm a missing container stops the run instead of moving the work.

    Without this, the Docker run place's numbers could in fact be the server
    run place's numbers, and the result table would report two different places
    while measuring one.
    """
    container = plan.get("container")
    if not isinstance(container, Mapping):
        return [
            "the plan does not say whether the container is required, so a "
            "missing container could be replaced by the server's own operating "
            "system without anyone noticing"
        ]
    setting = container.get("use_docker")
    if setting != REQUIRED_CONTAINER_SETTING:
        return [
            f"the plan sets the container requirement to {setting!r}; it must "
            f"be {REQUIRED_CONTAINER_SETTING!r}, so that a missing Docker "
            "service or a missing image ends the task as a recorded failure "
            "rather than moving the work to the server's own operating system"
        ]
    return []


def _prompt_text(condition: Mapping[str, Any], key: str) -> str:
    prompt = condition.get("prompt")
    if not isinstance(prompt, Mapping):
        return ""
    return str(prompt.get(key) or "")


def check_experiment_files_match_conditions(
    plan: Mapping[str, Any],
    conditions_by_environment: Mapping[str, ModelRunConditions],
    *,
    root: Path,
) -> list[str]:
    """Open each run place's settings file and compare it with the plan.

    This is the check that stops a different model, a different deployment, a
    different task list, or different wording reaching one run place and not
    another. The settings file is what actually runs; the plan is only a
    promise until the two are compared.
    """
    problems: list[str] = []
    files = plan.get("experiment_files")
    if not isinstance(files, Mapping):
        return [
            "the plan does not name an experiment settings file for any run "
            "place, so there is nothing to check the shared conditions against"
        ]
    loaded_settings: dict[str, Mapping[str, Any]] = {}

    missing_places = sorted(set(conditions_by_environment) - set(files))
    if missing_places:
        problems.append(
            "these run places take part in the comparison but the plan names "
            "no experiment settings file for them: " + ", ".join(missing_places)
        )

    for environment in sorted(set(conditions_by_environment) & set(files)):
        conditions = conditions_by_environment[environment]
        relative = str(files[environment])
        path = root / relative
        if not path.is_file():
            problems.append(
                f"{environment} names the experiment settings file {relative}, "
                "which does not exist"
            )
            continue
        try:
            settings = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as error:
            problems.append(
                f"{environment}'s experiment settings file {relative} could "
                f"not be read: {error}"
            )
            continue
        if not isinstance(settings, Mapping):
            problems.append(
                f"{environment}'s experiment settings file {relative} does not "
                "hold a mapping at the top level"
            )
            continue
        problems.extend(
            _compare_one_experiment_file(
                environment=environment,
                relative=relative,
                settings=settings,
                conditions=conditions,
                plan=plan,
            )
        )
        loaded_settings[environment] = settings

    problems.extend(_check_settings_the_plan_does_not_name(loaded_settings))
    problems.extend(
        _check_the_container_calls_no_model_after_the_code_is_made(
            loaded_settings,
            str(plan.get("comparison") or COMPARISON_SAME_GENERATED_CODE),
        )
    )
    problems.extend(
        _check_the_container_is_told_no_more_than_the_others(loaded_settings)
    )
    problems.extend(
        _check_the_plan_counts_every_call_the_container_makes(
            loaded_settings, conditions_by_environment, plan
        )
    )
    problems.extend(
        _check_the_plan_counts_what_the_container_carries_forward(
            loaded_settings, plan
        )
    )
    problems.extend(_check_the_plan_knows_what_one_cap_covers(plan))
    problems.extend(
        _check_the_plan_prices_what_the_files_add_to_the_prompt(loaded_settings)
    )
    return problems


# The settings a run place is allowed to hold differently, and why each one.
#
# Read this as the *whole* list of exceptions. Every other setting found in the
# files is compared, whether or not anyone thought of it when this was written.
#
# It used to be the other way round: four blocks were named as the ones to
# compare, under a comment saying the blocks left out "are the ones that are
# meant to differ between run places". Measured against the three experiment
# files this plan actually names, that was not so. The files hold 44 settings;
# the four blocks covered 18.
#
# Seven of the 26 left out were caught anyway, by a different route:
# :func:`_compare_one_experiment_file` holds each file against the plan, and the
# plan happens to pin the time limit, the retry count, the resume count and the
# code length. That route answers a narrower question — does this file agree
# with the plan — so it covers only the settings somebody thought to write into
# the plan, and it stops covering one the moment the plan stops naming it.
#
# The other 19 were invisible to every rule. Measured the same way at the level
# of the whole check, this change takes it from 25 of 44 to 30. The five it
# newly sees are what the run claims it is holding still and varying, whether
# the results are published, whether they are entered for scoring, and the
# container's own repair loop — which calls the model again after the code is
# written, and which the comparison forbids in as many words.
#
# A list of what to check is only ever as complete as the last person to think
# about it. A list of what may differ has to be argued for, entry by entry, and
# anything nobody argued for is checked by default.
#
# That principle had a hole in it, because an exception here is matched by
# prefix: naming a block excuses every setting under it, including settings
# added long after the argument was made. Those were not argued for; they were
# inherited. ``execution.sandbox`` is the block where that mattered — an
# exception granted for the container's shape, its image and memory and
# processors, was also excusing ``max_skills``, which decides how much
# instruction goes into the container's prompt while all three files declare
# they are holding ``prompt_strategy`` still. It now has a rule of its own
# below, taking the whole check from 30 of 44 to 31, and every setting the two
# block-level exceptions let through is argued for one by one in
# tests/test_envelope_preflight_compares_every_setting.py, which fails until a
# new one is.
SETTINGS_ALLOWED_TO_DIFFER: Mapping[tuple[str, ...], str] = {
    ("experiment",): (
        "the experiment's own id, name, description, author and date, which "
        "name the run rather than shape its answer"
    ),
    ("condition_a", "name"): "the label this run place is given in the report",
    ("data", "source"): (
        "step0_bootstrap.sh duplicates the benchmark into one repository per "
        "experiment, so each file names its own; which tasks are read out of "
        "it is pinned separately by data.filter.task_ids and by the "
        "catalogue's dataset fingerprint"
    ),
    ("execution", "mode"): (
        "the run place itself — this is the one thing the comparison varies"
    ),
    ("execution", "sandbox"): (
        "settings that describe the container, which only the container run "
        "place has at all; a value here is not a disagreement with the run "
        "places that have no container. What the container may do *after the "
        "code is generated* is not left to this exception — see "
        ":func:`_check_the_container_calls_no_model_after_the_code_is_made`"
    ),
}

# Settings inside the container's own block that turn the model back on after
# the code has been generated. Named separately from the exception above
# because the comparison that re-runs one model's own code forbids exactly
# this, and the container is the second way to reach it — condition_a.qa is the
# first, and was the only one being watched.
#
# Each entry carries the value the runner uses when the setting is **absent**,
# because leaving a setting out is not the same as turning it off. The repair
# loop is the case that matters: core/sandbox_runner.py builds its settings as
# ``{"enabled": True, "max_attempts": 1, **(repair or {})}``, so deleting the
# block turns the loop on. The `enabled: false` written in the container's
# experiment file is load-bearing, and a check that read an absent setting as
# "off" would report a run clean at the moment it became least safe.
#
# Each entry also says what calling it does, because the reason has to survive
# the next person who reads the list and wonders whether it still applies.
CONTAINER_SETTINGS_THAT_CALL_THE_MODEL_AGAIN: Mapping[
    tuple[str, ...], tuple[Any, str]
] = {
    ("repair", "enabled"): (
        True,
        "the container's repair loop writes a reflection and asks the model "
        "for the code again, and core/sandbox_runner.py turns it on when the "
        "setting is left out",
    ),
    ("output_qa", "vision", "enabled"): (
        False,
        "the container's picture check sends rendered pages to a vision "
        "model; core/output_qa.py leaves it off when the setting is left out",
    ),
}

# Settings inside the container's own block that put wording into the prompt
# the other two run places never see. Kept apart from the settings that call the
# model again because the promise they break is a different one: all three
# experiment files declare ``control.fixed`` to include ``prompt_strategy``, and
# this is the block that can quietly make that untrue.
#
# Each entry carries the absent value for the same reason as above, and here the
# absent value is the worse one. core/executor.py reads the setting as
# ``opts.get("max_skills", 5)``, core/skills_registry.py defaults the same
# argument to 5, and this repository ships exactly five skill documents — so
# deleting the line hands the container every skill there is.
CONTAINER_SETTINGS_THAT_ADD_TO_THE_PROMPT: Mapping[
    tuple[str, ...], tuple[Any, str]
] = {
    ("max_skills",): (
        5,
        "each skill selected is written into the container's prompt ahead of "
        "the task itself, as a worked manual of up to 7000 characters that "
        "neither of the other two run places is given; core/executor.py reads "
        "the setting as 5 when it is left out",
    ),
}

# Plain words for the settings already known about, so the report reads as a
# sentence instead of a key path. A setting missing from here is still
# compared; it is only described by its own name.
WHAT_THE_SETTING_DOES: Mapping[str, str] = {
    "condition_a.model.provider": "whose model is called",
    "condition_a.model.deployment": "which model is called",
    "condition_a.model.temperature": "how much the model varies its wording",
    "condition_a.model.seed": "the number that makes a run repeatable",
    "condition_a.model.reasoning_effort": "how hard the model is asked to think",
    "condition_a.prompt.system": "the standing instruction",
    "condition_a.prompt.prefix": "the wording put in front of the task",
    "condition_a.prompt.body": "the wording put between that and the task",
    "condition_a.prompt.suffix": "the wording put after the task",
    "condition_a.qa.enabled": "whether the model reviews its own answer",
    "condition_a.qa.max_retries": "how many times it may answer again",
    "condition_a.qa.model": "which model reviews the answer",
    "condition_a.qa.min_score": "the mark the answer has to reach",
    "condition_a.qa.prompt": "the wording the reviewer is given",
    "data.filter.task_ids": "which tasks are run",
    "data.filter.sample_size": "how many tasks are drawn",
    "data.filter.sector": "which sector the tasks are narrowed to",
    "data.filter.occupation": "which occupation the tasks are narrowed to",
    "execution.timeout": "how long one task may run before it is given up on",
    "execution.max_retries": "how many times a failed task is started again",
    "execution.resume_max_rounds": "how many times a stopped run may pick up",
    "execution.tokens.code_generation": "how much code the model may write",
    "control.fixed": "what the run claims it is holding still",
    "control.changed": "what the run claims it is varying",
    "output.publish_to_hf": "whether the results are published",
    "output.submit_to_evals": "whether the results are entered for scoring",
}


def _dig(settings: Mapping[str, Any], path: tuple[str, ...]) -> Mapping[str, Any]:
    """Follow a key path and return the block found there, or an empty one."""
    node: Any = settings
    for key in path:
        if not isinstance(node, Mapping):
            return {}
        node = node.get(key)
    return node if isinstance(node, Mapping) else {}


def _settings_in(node: Any, prefix: tuple[str, ...] = ()) -> dict[tuple[str, ...], Any]:
    """Every setting in a file, as a flat map from key path to value.

    A setting is anything that is not itself a block of further settings, so
    the depth of the file does not decide what gets compared.
    """
    if not isinstance(node, Mapping):
        return {prefix: node}
    found: dict[tuple[str, ...], Any] = {}
    for key, value in node.items():
        found.update(_settings_in(value, prefix + (str(key),)))
    return found


def _may_differ(path: tuple[str, ...]) -> str | None:
    """The stated reason this setting may differ, or None if it may not."""
    for allowed, reason in SETTINGS_ALLOWED_TO_DIFFER.items():
        if path[: len(allowed)] == allowed:
            return reason
    return None


def _check_settings_the_plan_does_not_name(
    settings_by_environment: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    """Confirm the run places agree on every setting that shapes the answer.

    A setting the plan forgot to fix is still a setting. If one run place asks
    the model to think harder than another, gives it half the time, or lets it
    try again twice more, the difference between their scores is not the run
    place.

    Every setting in the files is compared. The only ones passed over are the
    ones :data:`SETTINGS_ALLOWED_TO_DIFFER` gives a reason for. This is the
    opposite way round from how it was written first, where four blocks were
    named as the ones to compare and everything outside them went unlooked at:
    against the three files this plan names, that covered 18 of 44 settings,
    and this covers 26.

    That is the count for this rule alone, not for the check as a whole. Four
    of the eight settings it newly reaches — the time limit, the retry count,
    the resume count and the code length — were caught elsewhere already, by
    :func:`_compare_one_experiment_file` holding each file against the plan.
    Reaching them here as well is still worth having: this rule asks whether
    the run places agree with *each other*, which stays true of a setting the
    plan never mentions and of one the plan stops mentioning later.
    """
    problems: list[str] = []
    if len(settings_by_environment) < 2:
        return problems

    found = {
        environment: _settings_in(settings)
        for environment, settings in settings_by_environment.items()
    }
    every_path = {path for settings in found.values() for path in settings}

    for path in sorted(every_path):
        if _may_differ(path) is not None:
            continue
        dotted = ".".join(path)
        seen: dict[str, list[str]] = {}
        for environment in sorted(found):
            # A setting one file leaves out while another sets it is a real
            # difference, so an absent one is grouped with an explicit null
            # rather than passed over. Values are grouped by how they print,
            # because a setting may hold a list.
            seen.setdefault(repr(found[environment].get(path)), []).append(
                environment
            )
        if len(seen) == 1:
            continue
        described = WHAT_THE_SETTING_DOES.get(dotted)
        subject = f"{described} ({dotted})" if described else dotted
        groups = " | ".join(
            f"{shown}: {', '.join(sorted(places))}"
            for shown, places in sorted(seen.items())
        )
        problems.append(
            f"the run places disagree on {subject}, so the difference "
            "between their answers would not only be the run place: " + groups
        )
    return problems


def _container_settings_left_on(
    settings_by_environment: Mapping[str, Mapping[str, Any]],
    watched: Mapping[tuple[str, ...], tuple[Any, str]],
) -> list[tuple[str, str, str]]:
    """Watched container settings that are on: (run place, what is written, why).

    Shared by the two checks below, because finding the container run places and
    reading a setting the way the runner really reads it is the same work either
    way. Only the rule being enforced differs, so only the sentence differs.

    Which run places get asked is decided by ``execution.mode``, the setting the
    runner itself dispatches on, and not by whether a sandbox block has anything
    in it. Those two answers differ in exactly the case that matters: a container
    run place with an empty sandbox block has none of these settings written
    anywhere, and that is the state where the absent values apply.
    """
    container_mode = EXECUTION_MODE_BY_ENVIRONMENT[ENVIRONMENT_DOCKER_CONTAINER]
    found: list[tuple[str, str, str]] = []
    for environment in sorted(settings_by_environment):
        execution = _dig(settings_by_environment[environment], ("execution",))
        if execution.get("mode") != container_mode:
            continue
        container = _dig(
            settings_by_environment[environment], ("execution", "sandbox")
        )
        for path, (when_absent, what_it_does) in sorted(watched.items()):
            node: Any = container
            written_down = True
            for key in path:
                if not isinstance(node, Mapping) or key not in node:
                    node = when_absent
                    written_down = False
                    break
                node = node[key]
            if not node:
                continue
            dotted = "execution.sandbox." + ".".join(path)
            # Tracked with its own flag rather than by comparing the value to
            # the default: `True is True` in Python, so an explicitly written
            # `true` would otherwise be reported as a setting nobody wrote.
            written = (
                f"sets {dotted} to {node!r}"
                if written_down
                else f"leaves {dotted} out, which the runner reads as "
                f"{when_absent!r}"
            )
            found.append((environment, written, what_it_does))
    return found


def _check_the_container_calls_no_model_after_the_code_is_made(
    settings_by_environment: Mapping[str, Mapping[str, Any]],
    comparison: str,
) -> list[str]:
    """Hold the container to the rule the comparison already states.

    The comparison that re-runs one model's own code fixes one thing above all
    others: the model is called once, to write the code, and not again. No
    self-review, no retry. That is what lets a difference in the answers be
    read as a difference in the run place.

    ``condition_a.qa`` is checked against that rule already. The container has
    its own way to reach the same thing, and nothing was looking at it. Worse,
    the setting that matters most is the one whose absence means *on*: leaving
    ``repair`` out of the container's file turns the repair loop on, so the
    check reads an absent setting as the value the runner would really use
    rather than as "off".

    The other comparison deliberately leaves each tool's own features running,
    so this rule is not applied there.
    """
    if comparison != COMPARISON_SAME_GENERATED_CODE:
        return []
    return [
        f"{environment} {written}, but the comparison that re-runs "
        "one model's own code calls the model once and not again: " + what_it_does
        for environment, written, what_it_does in _container_settings_left_on(
            settings_by_environment, CONTAINER_SETTINGS_THAT_CALL_THE_MODEL_AGAIN
        )
    ]


def _check_the_container_is_told_no_more_than_the_others(
    settings_by_environment: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    """Hold the container to the promise every experiment file already makes.

    All three files declare ``control.fixed`` to include ``prompt_strategy``.
    That is the run's own word that the wording put in front of the model is the
    same in all three places, and it is what lets a difference in the answers be
    read as a difference in the run place rather than as one run place having
    been briefed better than the others.

    The container is the only run place with a block of its own, and one of the
    settings in that block decides how much extra instruction goes into its
    prompt. Nothing was comparing it, because the whole ``execution.sandbox``
    subtree is exempt from the settings comparison — reasonably, since most of
    what is in there really is the run place being described. This is the part
    that is not.

    Unlike the rule above, this one holds whichever comparison is being run: a
    file that says it is holding the prompt still has said so either way.
    """
    return [
        f"{environment} {written}, but every experiment file names "
        "prompt_strategy among the things it is holding still: " + what_it_does
        for environment, written, what_it_does in _container_settings_left_on(
            settings_by_environment, CONTAINER_SETTINGS_THAT_ADD_TO_THE_PROMPT
        )
    ]


@dataclass(frozen=True)
class ContainerAttemptShape:
    """How many times one attempt in the container really asks a model.

    Worked out from the container's own settings, the way
    :mod:`core.sandbox_runner` works it out, rather than read off a number
    somebody wrote into the plan by hand.
    """

    code_turns: int
    """One go at writing the code, plus one more for each repair allowed."""

    picture_check_turns: int
    """The picture check asks once per go at the code, when it is switched on."""

    picture_check_model: str | None
    """The model the picture check would call. It need not be the run model, and
    it is None when the picture check is on but names nothing."""

    @property
    def model_turns(self) -> int:
        """Every call to a model inside one attempt, added up."""
        return self.code_turns + self.picture_check_turns

    def in_words(self) -> str:
        """The sum spelled out, so a reader can check it without the source."""
        if not self.picture_check_turns:
            return f"{self.code_turns} to write the code"
        named = self.picture_check_model or "a model it does not name"
        return (
            f"{self.code_turns} to write the code and "
            f"{self.picture_check_turns} to {named} for the picture check"
        )


def _container_loop_defaults() -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    """The container runner's own values for its two model-calling loops.

    Read off :class:`~core.sandbox_runner.SandboxRunner` rather than typed again
    here, the same way :mod:`core.execution_envelope_grading_cost` reads the
    judge's limits off the judge. Changing a value in the runner then moves this
    check with it, instead of leaving it quoting a number that stopped being
    true. Building one costs nothing and calls nothing: the constructor only
    fills settings in, and the client handed to it here is never used.

    Imported inside the function because the runner reaches for the container
    libraries at import time, and this module is meant to run on a machine with
    no container on it at all.
    """
    from core.sandbox_runner import SandboxRunner

    runner = SandboxRunner(llm_client=None)
    return runner.repair_cfg, runner.output_qa_cfg


def container_attempt_shape(
    container_settings: Mapping[str, Any],
) -> ContainerAttemptShape:
    """Count one attempt's model calls out of the container's own settings.

    This follows :meth:`core.sandbox_runner.SandboxRunner.run`. It goes at the
    code ``max_attempts + 1`` times, where ``max_attempts`` is the repair budget
    when repair is on and nothing at all when it is off. Inside each of those it
    calls ``_analyze_output`` once, which hands rendered pages to a vision model
    when the picture check is on.

    Anything the settings leave out takes the runner's own value, and for repair
    that value is *on*. That is the whole reason for reading the settings rather
    than a written number: a container file with an empty block is a container
    that asks a model twice per attempt, and nothing in the plan would say so.
    """
    repair_defaults, picture_defaults = _container_loop_defaults()

    repair = _dig(container_settings, ("repair",))
    repair_on = bool(repair.get("enabled", repair_defaults.get("enabled")))
    budget = int(
        repair.get("max_attempts", repair_defaults.get("max_attempts", 0)) or 0
    )
    code_turns = (1 + max(budget, 0)) if repair_on else 1

    picture = _dig(container_settings, ("output_qa",))
    vision = _dig(picture, ("vision",))
    # Three gates, each read the way the code reads it. run_output_qa returns at
    # once unless ``enabled``; it collects no pages to look at unless ``render``;
    # and it asks a model only when ``vision.enabled`` is written, which is read
    # with no default at all and so is off whenever it is left out.
    picture_on = (
        bool(picture.get("enabled", picture_defaults.get("enabled")))
        and bool(picture.get("render", picture_defaults.get("render")))
        and bool(vision.get("enabled"))
    )
    named = vision.get("deployment") or vision.get("model")
    return ContainerAttemptShape(
        code_turns=code_turns,
        picture_check_turns=code_turns if picture_on else 0,
        picture_check_model=str(named).strip() if named else None,
    )


def _check_the_plan_counts_every_call_the_container_makes(
    settings_by_environment: Mapping[str, Mapping[str, Any]],
    conditions_by_environment: Mapping[str, ModelRunConditions],
    plan: Mapping[str, Any],
) -> list[str]:
    """Hold the plan's turn limit against what the container's settings do.

    The cost sum prices one attempt as ``tool_loop_max_model_turns`` calls to a
    model, and that number is written into the plan by hand. For two of the
    three run places it has to be: a separate Python process on the server has
    no loop at all, and what Azure's own tool loop does inside itself is not
    readable from here. The container is the one place where the real number is
    sitting in a file in this repository, and nothing was reading it.

    Two settings move it. Repair asks the model for the code again, as many
    times as its budget allows. The picture check sends rendered pages to a
    vision model, once for each go at the code. The plan says 1, and 1 is true
    only while the committed file happens to say ``repair: enabled: false``.
    Delete those two lines and the container asks twice at the same price a
    call, with the plan still saying 1 and the sum still reporting the same
    ceiling.

    This refuses only when the plan's number sits *below* what the settings
    would really do. A plan is allowed to be more careful than the settings; it
    is not allowed to be less. That leaves the number a stated assumption where
    it has to be one and pins it where it does not.

    A second thing is said rather than folded in silently: the picture check
    calls whatever model ``output_qa.vision`` names, which need not be the model
    the run places are being compared on. Counting that call correctly and
    pricing it at the wrong rate is still a wrong sum, so where the two differ
    it is reported in its own sentence.

    Unlike :func:`_check_the_container_calls_no_model_after_the_code_is_made`,
    this holds whichever comparison is being run. A ceiling is a ceiling either
    way, and the comparison that leaves each tool's own features running is
    exactly the one where the container's loop is expected to be on.

    A run place the plan writes no number for is left alone here. The cost sum
    already refuses that on its own terms, and saying it twice helps nobody.
    """
    written = _dig(plan, ("cost", "assumptions", "tool_loop_max_model_turns"))
    container_mode = EXECUTION_MODE_BY_ENVIRONMENT[ENVIRONMENT_DOCKER_CONTAINER]
    problems: list[str] = []
    for environment in sorted(settings_by_environment):
        settings = settings_by_environment[environment]
        if _dig(settings, ("execution",)).get("mode") != container_mode:
            continue
        shape = container_attempt_shape(_dig(settings, ("execution", "sandbox")))

        claimed = written.get(environment)
        try:
            claimed_turns = int(claimed)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            # Absent, or not a number the sum could use either. Both are
            # refused where the assumptions are read; this rule adds nothing.
            claimed_turns = None
        if claimed_turns is not None and claimed_turns < shape.model_turns:
            problems.append(
                f"{environment}'s settings ask a model {shape.model_turns} "
                f"times inside one attempt ({shape.in_words()}), but the plan's "
                f"cost sum prices {claimed_turns}; that sum is what says the "
                "run fits inside the approved maximum"
            )

        if not shape.picture_check_turns:
            continue
        conditions = conditions_by_environment.get(environment)
        run_model = conditions.resolved_model if conditions is not None else None
        if shape.picture_check_model is None:
            problems.append(
                f"{environment} switches its picture check on but names no "
                "model for it, so what the cost sum should charge for that "
                "call cannot be read from the settings at all"
            )
        elif run_model and shape.picture_check_model != run_model:
            problems.append(
                f"{environment}'s picture check calls "
                f"{shape.picture_check_model}, but the cost sum prices every "
                f"call in an attempt at {run_model}, the model the run places "
                "are being compared on"
            )
    return problems


def _container_carried_forward_characters(
    container_settings: Mapping[str, Any],
) -> dict[str, int]:
    """What the container's repair prompt comes to, part by part.

    Measured by :mod:`core.sandbox_runner` rather than counted again here, for
    the same reason :func:`_container_loop_defaults` reads the loop settings off
    the runner: a figure worked out over there is worked out by building a real
    repair prompt through the very function a repair turn renders with, so a
    heading edited in the prompt file, a limit changed in the runner or a
    repair-guidance entry added moves this with it. A number typed here would
    stop being true the moment any of those changed, and nothing would say so.

    The prompt measured is the one this run place's settings name, not whichever
    one is the runner's default, because ``core/executor.py`` hands
    ``execution.sandbox.prompt_name`` straight to ``SandboxRunner``.

    Raises when that prompt cannot be read. The caller turns that into a
    refusal: a repair prompt nobody can read is a repair prompt nobody can
    price, and treating it as free would be the optimistic answer.

    Imported inside the function because the runner reaches for the container
    libraries at import time, and this module is meant to run on a machine with
    no container on it at all.
    """
    from core.sandbox_runner import widest_repair_prompt_characters

    named = _dig(container_settings, ("execution", "sandbox")).get("prompt_name")
    return widest_repair_prompt_characters(str(named) if named else None)


def _check_the_plan_counts_what_the_container_carries_forward(
    settings_by_environment: Mapping[str, Mapping[str, Any]],
    plan: Mapping[str, Any],
) -> list[str]:
    """Hold the plan's carried-forward figure against the repair prompt itself.

    ``max_tool_result_tokens_per_turn`` is what the cost sum charges for
    everything that is in front of the model on a later turn without being
    either the task or the model's own words.
    :func:`core.execution_envelope_cost.max_input_tokens_per_attempt` multiplies
    it by the number of earlier turn pairs, so at two turns it is charged once.

    The plan writes ``0`` for the container and says the model "is asked once
    and nothing is carried forward". That is true only while the committed file
    says ``repair: enabled: false``. Switch repair on — which nothing outside
    that one line prevents, and which the runner does by itself whenever the
    block is left out — and a whole repair prompt sits in front of the model on
    the second turn. At ``0`` the sum charges nothing for any of it.

    So this refuses only where the container would really loop, and only where
    the plan sits *below* what the loop is certain to carry. A plan more
    careful than the settings is left alone, exactly as in
    :func:`_check_the_plan_counts_every_call_the_container_makes`.

    **What the figure covers.** ``core.sandbox_runner`` builds the prompt at the
    widest its committed wording allows and reports what each part came to: the
    opening, instruction and close it always carries; twelve blocking-error
    lines under their heading, the first of them a full-width failure tail; every
    repair-guidance entry the committed prompt holds; six warning lines under
    their heading; the narrowest a deliverable contract section can render to;
    and both output tails under their headings. The only thing outside the count
    is the English the run writes onto those lines while it runs, which is
    settled by the task and the failure rather than by anything committed here.

    The model's own earlier code is left out on purpose, though the prompt
    carries up to four thousand characters of it — the words placed around it are
    counted, the code between them is not. That code is the model's earlier
    answer, and ``max_input_tokens_per_attempt`` already charges a full
    ``max_output_tokens`` for every earlier answer. Adding it here would bill the
    same words twice and make the ceiling look better founded than it is.
    """
    written = _dig(
        plan, ("cost", "assumptions", "max_tool_result_tokens_per_turn")
    )
    raw_ratio = _dig(plan, ("cost", "assumptions")).get("characters_per_token")
    try:
        characters_per_token = Decimal(str(raw_ratio))
    except (ArithmeticError, TypeError, ValueError):
        return []
    if characters_per_token <= 0:
        # Absent, or not a ratio the sum could use. Both are refused where the
        # assumptions are read; this rule adds nothing by saying it again.
        return []

    container_mode = EXECUTION_MODE_BY_ENVIRONMENT[ENVIRONMENT_DOCKER_CONTAINER]

    problems: list[str] = []
    for environment in sorted(settings_by_environment):
        settings = settings_by_environment[environment]
        if _dig(settings, ("execution",)).get("mode") != container_mode:
            continue
        shape = container_attempt_shape(_dig(settings, ("execution", "sandbox")))
        if shape.code_turns < 2:
            # One go at the code, so there is no second turn to carry anything
            # into and nothing here to price.
            continue

        try:
            widths = _container_carried_forward_characters(settings)
        except Exception as unreadable:  # noqa: BLE001 - anything here is a refusal
            # A missing prompt file, wording that will not parse, a spec that
            # fails its own required keys: every one of them leaves the repair
            # prompt unpriceable. Caught broadly and turned into a refusal
            # rather than allowed to pass this rule by falling through it.
            problems.append(
                f"{environment}'s settings let its repair loop ask for the code "
                f"{shape.code_turns} times, so a later turn carries the repair "
                "prompt core/sandbox_runner.py builds, but that prompt cannot be "
                f"read here and so cannot be priced: {unreadable}"
            )
            continue

        characters = sum(widths.values())
        least_tokens = int(
            (Decimal(characters) / characters_per_token).to_integral_value(
                rounding=ROUND_CEILING
            )
        )

        claimed = written.get(environment)
        try:
            claimed_tokens = int(claimed)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        if claimed_tokens >= least_tokens:
            continue
        made_of = ", ".join(
            f"{width} characters of {what}"
            for what, width in sorted(widths.items(), key=lambda pair: -pair[1])
        )
        problems.append(
            f"{environment}'s settings let its repair loop ask for the code "
            f"{shape.code_turns} times, and core/sandbox_runner.py builds the "
            f"next request out of the committed repair prompt and the run's own "
            f"output ({made_of}), but the plan's cost sum charges "
            f"{claimed_tokens} tokens for what a later turn carries; "
            f"{characters} characters is {least_tokens} tokens at this plan's "
            "ratio, and the only part of the prompt outside that figure is the "
            "English the run writes onto those lines while it runs"
        )
    return problems


def _runner_sends_a_fresh_request_per_turn(environment: str) -> bool | None:
    """Whether this run place opens a new request for each turn the model takes.

    Read off the runner class that actually does the work, named in
    ``RUNNER_CLASS_BY_ENVIRONMENT``, rather than decided here from the mode
    name. The two answers are structural and neither is a setting:

    * ``core.code_interpreter.CodeInterpreterRunner`` issues one
      ``responses.create`` per attempt with the code interpreter attached to it,
      so the whole reply — every tool turn the service takes inside it —
      happens under the one ``max_output_tokens`` sent with that call.
    * ``core.sandbox_runner.SandboxRunner`` repairs by going round an ordinary
      Python ``for`` loop, calling ``complete`` again each time with the full
      budget. No single cap covers the attempt because there is no single
      request.

    ``None`` means the runner does not say. That is not the same as ``False``,
    and the caller must not read it as permission: see
    :func:`_check_the_plan_knows_what_one_cap_covers`.

    Imported inside the function because these runners reach for container and
    provider libraries at import time, and this module is meant to run on a
    machine that has neither.
    """
    named = RUNNER_CLASS_BY_ENVIRONMENT.get(environment)
    if named is None:
        return None
    module_name, class_name = named
    try:
        module = import_module(module_name)
        runner = getattr(module, class_name)
        declared = getattr(runner, "SENDS_A_FRESH_REQUEST_PER_TURN")
    except (AttributeError, ImportError):
        return None
    return bool(declared)


def _check_the_plan_knows_what_one_cap_covers(
    plan: Mapping[str, Any],
) -> list[str]:
    """Hold ``output_tokens_capped_per_attempt`` against the request really sent.

    This is the largest single divisor in the cost sum, and until now it was
    three booleans typed into the plan with four lines of prose beside them and
    nothing checking any of it.
    :func:`core.execution_envelope_cost.max_attempt_counts` bills
    ``1 if capped else tool_loop_max_model_turns`` answers per attempt, and
    :func:`core.execution_envelope_cost.max_input_tokens_per_attempt` charges
    ``(turns - 1)`` earlier answers when it is set against
    ``turns * (turns - 1) / 2`` when it is not. At Azure's eight turns that is
    the difference between 14.06 and 54.20 United States dollars for one run
    place — more, by itself, than the whole amount the plan asks to be approved.

    What decides it is not a setting but the shape of the request: a run place
    that hands the model's whole reply to one API call is capped once for the
    attempt; a run place that opens a new request each turn is capped again
    each turn. So the answer is read from the runner
    (:func:`_runner_sends_a_fresh_request_per_turn`), not from the plan.

    Only the cheap direction is refused, as everywhere else here. Claiming one
    cap where the caller really sends a fresh one each turn divides the answer
    charge by the number of turns, so it is refused. Claiming a fresh cap where
    one would have covered the attempt over-charges, and a ceiling is allowed
    to be more careful than the thing it bounds.

    A ``true`` for a run place whose runner does not say is refused as well.
    Nothing looked, and nothing looking is not the same as the claim holding —
    the same rule :func:`_check_grading_assumptions_match_the_settings` applies
    to a plan that marks answers but names no marking settings.

    **One thing here cannot be checked from this repository at all**, and the
    refusal must not pretend otherwise. That the Azure request is a single call
    carrying a single cap is readable, and is read. Whether the service honours
    that cap across the tool turns it takes inside the call is Microsoft's
    behaviour, not this repository's, and stands with
    ``tool_loop_max_model_turns.azure_code_interpreter`` as something taken on
    the documentation's word. It is worth naming which way that one leans: if
    the service did not hold to it, the honest value would be ``false`` and the
    ceiling would rise by about 50 dollars.
    """
    capped = _dig(plan, ("cost", "assumptions", "output_tokens_capped_per_attempt"))
    turns = _dig(plan, ("cost", "assumptions", "tool_loop_max_model_turns"))

    problems: list[str] = []
    for environment in sorted(capped):
        if not bool(capped[environment]):
            continue
        fresh_each_turn = _runner_sends_a_fresh_request_per_turn(environment)
        if fresh_each_turn is False:
            continue

        try:
            claimed_turns = int(turns.get(environment))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            claimed_turns = 1
        cost_note = (
            f"at the {claimed_turns} turns this plan allows that divides the "
            f"answer charge by {claimed_turns}"
            if claimed_turns > 1
            else "at the 1 turn this plan allows it changes no figure today, "
            "but the turn count is read from the settings and rises the "
            "moment they do"
        )

        if fresh_each_turn is None:
            problems.append(
                f"the cost sum says one cap on answer length covers a whole "
                f"{environment} attempt, but nothing in this repository says "
                "so: no runner is registered for that run place, or the one "
                "that is does not declare SENDS_A_FRESH_REQUEST_PER_TURN. "
                f"{cost_note}, and a claim nothing checked is not a claim that "
                "holds"
            )
            continue

        module_name, class_name = RUNNER_CLASS_BY_ENVIRONMENT[environment]  # type: ignore[misc]
        problems.append(
            f"the cost sum says one cap on answer length covers a whole "
            f"{environment} attempt, but {module_name.replace('.', '/')}.py "
            f"declares that {class_name} opens a new request for every turn "
            "the model takes, and each one carries the whole budget again — "
            f"so no single cap covers the attempt. {cost_note}"
        )
    return problems


def _runner_reference_file_prompt_sections(
    environment: str,
) -> tuple[str, ...] | None:
    """Which prompt sections this run place fills from the reference files.

    Read off the runner class that actually does the work, named in
    ``RUNNER_CLASS_BY_ENVIRONMENT``, rather than decided here from the mode
    name. ``None`` means the runner does not say, which is not the same as
    "it sends none of them": see
    :func:`_check_the_plan_prices_what_the_files_add_to_the_prompt`.

    Imported inside the function for the reason given on
    :func:`_runner_sends_a_fresh_request_per_turn`.
    """
    named = RUNNER_CLASS_BY_ENVIRONMENT.get(environment)
    if named is None:
        return None
    module_name, class_name = named
    try:
        module = import_module(module_name)
        runner = getattr(module, class_name)
        declared = getattr(runner, "REFERENCE_FILE_PROMPT_SECTIONS")
    except (AttributeError, ImportError):
        return None
    return tuple(str(section) for section in declared)


def _check_the_plan_prices_what_the_files_add_to_the_prompt(
    loaded_settings: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    """Hold ``REFERENCE_FILE_CHARACTER_CAP`` against the module that really cuts.

    Every reference file a task ships with is billed at that constant, and for
    a long time the comment beside it said ``core/file_reader.py`` cuts files
    there before they reach the model. That is not what happens.
    ``read_all_references`` is reached only through ``PromptBuilder``, and
    ``PromptBuilder`` is not built anywhere the pipeline runs — the only place
    that constructs it is a test patching a ``main.py`` this repository does
    not contain. So the figure was carrying a justification that pointed at
    dead code, which is worse than carrying none: a reader who checked it would
    have found a real cap at a real number and stopped looking.

    What the model is really sent about a reference file is assembled in
    ``core/file_preview.py``, and how much of it depends on the run place. Each
    runner declares which prompt sections it fills — ``file_structure`` alone
    for Azure, all three for the host and the container — and
    :func:`core.file_preview.reference_file_prompt_budget` adds up what those
    sections can contribute for one file, from the caps beside the code that
    applies them rather than from anything copied here.

    Only the cheap direction is refused, as everywhere else in this module. The
    constant sits far above the readable caps, so today it over-charges by a
    wide margin, and a ceiling is allowed to be more careful than the thing it
    bounds. What is refused is the constant falling below what a file can
    readably add — raising ``MAX_PREVIEW_CHARS_PER_FILE`` past 50,000 would do
    it silently, and the bill would then be understated by however far past it
    went, on every reference file of every task in every run place.

    A run place whose runner does not declare is refused too, on the rule
    :func:`_check_the_plan_knows_what_one_cap_covers` already applies: nothing
    looked, and nothing looking is not the same as the claim holding.

    **Two things here are not bounded by any number in this repository**, and
    the refusal must not imply otherwise. ``build_file_structure_info`` prints
    every column header of every sheet with no character limit at all, and the
    preview headers put the file name outside the cut. The name is allowed for
    at :data:`core.file_preview.MAX_FILE_NAME_CHARACTERS`; the column headers
    are not, and cannot honestly be, because a workbook may carry any number of
    them. The headroom between the readable caps and this constant is what
    covers them, which is the whole reason the constant is not lowered to fit,
    and the reason this check guards that headroom from below.
    """
    problems: list[str] = []
    for environment in sorted(loaded_settings):
        sections = _runner_reference_file_prompt_sections(environment)
        if sections is None:
            problems.append(
                f"the cost sum bills every {environment} reference file at "
                f"{REFERENCE_FILE_CHARACTER_CAP:,} characters, but nothing in "
                "this repository says how much of a file that run place puts "
                "in the prompt: no runner is registered for it, or the one "
                "that is does not declare REFERENCE_FILE_PROMPT_SECTIONS. A "
                "figure nothing checked is not a figure that holds"
            )
            continue

        try:
            budget = reference_file_prompt_budget(sections)
        except KeyError as unknown_section:
            problems.append(
                f"{environment}'s runner says it fills the prompt section "
                f"{unknown_section} from each reference file, but "
                "core/file_preview.py knows no such section and so cannot say "
                "what it adds. Pricing it at nothing would lower the bill by "
                "whatever it really sends, so it is refused until the two "
                "agree"
            )
            continue

        if REFERENCE_FILE_CHARACTER_CAP >= budget.capped_characters:
            continue

        problems.append(
            f"the cost sum bills every {environment} reference file at "
            f"{REFERENCE_FILE_CHARACTER_CAP:,} characters, but "
            "core/file_preview.py lets one file add up to "
            f"{budget.capped_characters:,} through the sections that run place "
            f"fills ({', '.join(sections)}) — and that is only the part with a "
            "cap to read. The bill is understated on every reference file of "
            "every task there, so either the caps come back down or the "
            "constant goes up to cover them"
        )
    return problems


def _compare_one_experiment_file(
    *,
    environment: str,
    relative: str,
    settings: Mapping[str, Any],
    conditions: ModelRunConditions,
    plan: Mapping[str, Any],
) -> list[str]:
    problems: list[str] = []
    label = f"{environment}'s experiment settings file {relative}"

    condition_a = settings.get("condition_a")
    if not isinstance(condition_a, Mapping):
        return [f"{label} has no condition_a block"]

    model = condition_a.get("model")
    model = model if isinstance(model, Mapping) else {}

    if str(model.get("provider") or "") != conditions.provider:
        problems.append(
            f"{label} names the provider {model.get('provider')!r}, but the "
            f"shared conditions fix it at {conditions.provider!r}"
        )
    if str(model.get("deployment") or "") != conditions.deployment:
        problems.append(
            f"{label} names the deployment {model.get('deployment')!r}, but "
            f"the shared conditions fix it at {conditions.deployment!r}. Every "
            "run place must address the same deployment or the comparison is "
            "between models, not between run places."
        )

    for key, expected, description in (
        ("system", conditions.system_instruction, "standing instruction"),
        ("suffix", conditions.task_instruction, "task instruction"),
    ):
        actual = _prompt_text(condition_a, key)
        if actual != expected:
            problems.append(
                f"{label} has a {description} that differs from the shared "
                "conditions, so this run place would be given different "
                "wording from the others"
            )

    qa = condition_a.get("qa")
    qa = qa if isinstance(qa, Mapping) else {}
    enabled = bool(qa.get("enabled", False))
    if enabled != conditions.self_review_enabled:
        problems.append(
            f"{label} {'turns on' if enabled else 'turns off'} the model's "
            "review of its own answer, but the shared conditions "
            f"{'turn it on' if conditions.self_review_enabled else 'turn it off'}"
        )
    qa_attempts = int(qa.get("max_retries", 0) or 0)
    if qa_attempts != conditions.self_review_max_attempts:
        problems.append(
            f"{label} allows {qa_attempts} self-review attempts, but the "
            f"shared conditions allow {conditions.self_review_max_attempts}"
        )

    execution = settings.get("execution")
    execution = execution if isinstance(execution, Mapping) else {}
    expected_mode = EXECUTION_MODE_BY_ENVIRONMENT.get(environment)
    if expected_mode is not None and execution.get("mode") != expected_mode:
        problems.append(
            f"{label} runs in {execution.get('mode')!r} mode, but this run "
            f"place is reached through {expected_mode!r}"
        )
    timeout = execution.get("timeout")
    if int(timeout or 0) != conditions.per_task_timeout_seconds:
        problems.append(
            f"{label} allows one task {timeout!r} seconds, but the shared "
            f"conditions allow {conditions.per_task_timeout_seconds}"
        )
    retries = int(execution.get("max_retries", 0) or 0)
    if retries != conditions.retry_max_attempts:
        problems.append(
            f"{label} allows {retries} attempts after a network failure, a "
            "server error, or a timeout, but the shared conditions allow "
            f"{conditions.retry_max_attempts}"
        )
    resume_rounds = int(execution.get("resume_max_rounds", 0) or 0)
    if resume_rounds != 0:
        problems.append(
            f"{label} allows {resume_rounds} extra rounds of re-running failed "
            "tasks. That would give this run place more attempts than another "
            "depending on how its errors happened to fall, so it must be 0."
        )

    tokens = execution.get("tokens")
    tokens = tokens if isinstance(tokens, Mapping) else {}
    written_tokens = tokens.get("code_generation")
    if written_tokens is None:
        problems.append(
            f"{label} does not say how much the model may write, so it would "
            "fall back to a built-in default that differs from the "
            f"{conditions.max_output_tokens} the shared conditions fix"
        )
    elif int(written_tokens) != conditions.max_output_tokens:
        problems.append(
            f"{label} lets the model write up to {written_tokens} tokens, but "
            f"the shared conditions allow {conditions.max_output_tokens}"
        )

    data = settings.get("data")
    data = data if isinstance(data, Mapping) else {}
    task_filter = data.get("filter")
    task_filter = task_filter if isinstance(task_filter, Mapping) else {}
    written_tasks = task_filter.get("task_ids")
    if written_tasks is None:
        problems.append(
            f"{label} does not fix a task list, so it would run whatever the "
            "dataset happens to return"
        )
    elif tuple(str(value) for value in written_tasks) != conditions.task_ids:
        problems.append(
            f"{label} fixes a different task list from the shared conditions"
        )
    if task_filter.get("sample_size") is not None:
        problems.append(
            f"{label} sets a sample size as well as a fixed task list, which "
            "would let the tasks that actually run differ from the ones agreed"
        )

    if environment == ENVIRONMENT_DOCKER_CONTAINER:
        problems.extend(
            _check_docker_settings_block(label=label, execution=execution, plan=plan)
        )
    return problems


def _check_docker_settings_block(
    *, label: str, execution: Mapping[str, Any], plan: Mapping[str, Any]
) -> list[str]:
    sandbox = execution.get("sandbox")
    if not isinstance(sandbox, Mapping):
        return [
            f"{label} has no sandbox block, so nothing requires the container "
            "to be used and a missing container would be replaced by the "
            "server's own operating system"
        ]
    setting = sandbox.get("use_docker")
    problems: list[str] = []
    if setting != REQUIRED_CONTAINER_SETTING:
        problems.append(
            f"{label} sets the container requirement to {setting!r}. It must "
            f"be {REQUIRED_CONTAINER_SETTING!r}: any other value lets a "
            "missing Docker service or a missing image move the work to the "
            "server's own operating system, which would turn this run place's "
            "results into the other run place's results without saying so."
        )
    container = plan.get("container")
    container = container if isinstance(container, Mapping) else {}
    planned_image = container.get("image")
    if planned_image is not None and sandbox.get("image") != planned_image:
        problems.append(
            f"{label} uses the container image {sandbox.get('image')!r}, but "
            f"the plan fixes it at {planned_image!r}"
        )
    return problems


def check_plan_names_only_runnable_places(
    conditions_by_environment: Mapping[str, ModelRunConditions],
) -> list[str]:
    """Confirm the plan neither adds a place that cannot run nor drops one silently."""
    named = set(conditions_by_environment)
    unknown = sorted(named - set(COMPARABLE_ENVIRONMENTS))
    problems: list[str] = []
    if unknown:
        problems.append(
            "the plan asks these run places to take part, but this repository "
            "cannot run a scored comparison in them: " + ", ".join(unknown)
        )
    if not named:
        problems.append("the plan names no run place at all")
    return problems


def run_envelope_preflight(
    plan: Mapping[str, Any],
    *,
    root: Path,
    catalog: TaskCatalog | None = None,
    docker_daemon_available: bool | None = None,
    docker_image_available: bool | None = None,
    azure_route_profile: str | None = None,
    environ: Mapping[str, str] | None = None,
    dataset_root: Path | None = None,
) -> EnvelopePreflight:
    """Run every free check and return one answer listing every problem."""
    problems: list[str] = []
    input_files: dict[str, InputFileVerification] = {}
    missing_input_file_problems: list[str] = []

    if plan.get("plan_version") != PLAN_VERSION:
        problems.append(
            f"the plan says it is version {plan.get('plan_version')!r}, but "
            f"this check reads {PLAN_VERSION!r}"
        )

    try:
        conditions = conditions_from_plan(plan)
    except ValueError as error:
        conditions = {}
        problems.append(str(error))

    problems.extend(check_plan_names_only_runnable_places(conditions))
    problems.extend(check_container_cannot_fall_back(plan))
    problems.extend(
        check_experiment_files_match_conditions(plan, conditions, root=root)
    )

    try:
        loaded_catalog = catalog if catalog is not None else load_task_catalog()
    except ValueError as error:
        loaded_catalog = None
        problems.append(str(error))

    if loaded_catalog is not None:
        problems.extend(check_catalog_carries_no_scores())
        # Asked of the catalogue in play rather than of the file on disk, and
        # asked before the cost ceiling is worked out from these same numbers.
        problems.extend(catalog_number_problems(loaded_catalog))
        selection = select_advance_check_tasks(loaded_catalog)
        for environment in sorted(conditions):
            problems.extend(
                f"{environment}: {note}"
                for note in selection_matches(
                    conditions[environment].task_ids, selection
                )
            )
            verification = verify_input_file_versions(
                conditions[environment].input_file_versions,
                conditions[environment].task_ids,
                loaded_catalog,
                dataset_root,
            )
            input_files[environment] = verification
            problems.extend(
                f"{environment}: {note}" for note in verification.problems
            )
            missing_input_file_problems.extend(
                f"{environment}: {note}" for note in verification.missing_copies
            )
        # Named separately above, but still counted here. Being unable to check
        # a fingerprint is a reason not to start, not a reason to stay quiet.
        problems.extend(missing_input_file_problems)

    cost_block = plan.get("cost")
    cost_block = cost_block if isinstance(cost_block, Mapping) else {}
    cost_policy = str(cost_block.get("policy") or COST_POLICY_BLOCK)
    if cost_policy not in VALID_COST_POLICIES:
        problems.append(
            f"cost.policy is {cost_policy!r}; it must be one of "
            + ", ".join(sorted(VALID_COST_POLICIES))
        )
        cost_policy = COST_POLICY_BLOCK

    owner_approval = cost_block.get("owner_approval")
    owner_approval = owner_approval if isinstance(owner_approval, Mapping) else {}
    available_monthly_credit_usd: Decimal | None = None
    if cost_policy == COST_POLICY_RECORD_ONLY:
        if owner_approval.get("paid_model_calls") is not True:
            problems.append(
                "cost.policy records cost findings without blocking, but "
                "cost.owner_approval.paid_model_calls is not true"
            )
        if owner_approval.get("unpriced_audio_measurement") is not True:
            problems.append(
                "cost.policy records cost findings without blocking, but the "
                "owner did not approve measuring the unpriced audio model"
            )
        raw_credit = owner_approval.get("available_monthly_credit_usd")
        try:
            available_monthly_credit_usd = Decimal(str(raw_credit))
        except Exception:
            problems.append(
                "cost.owner_approval.available_monthly_credit_usd must be a "
                "number greater than zero"
            )
        else:
            if available_monthly_credit_usd <= 0:
                problems.append(
                    "cost.owner_approval.available_monthly_credit_usd must be "
                    "greater than zero"
                )

    ceiling: CostCeiling | None = None
    grading_ceiling_problems: list[str] = []
    cost_findings: list[str] = []
    approved_raw = cost_block.get("approved_maximum_usd")
    approved: Decimal | None = None
    if conditions and loaded_catalog is not None:
        try:
            assumptions = CostAssumptions.from_mapping(
                cost_block.get("assumptions") or {}
            )
        except ValueError as error:
            problems.append(str(error))
        else:
            problems.extend(
                _check_instruction_length(
                    conditions,
                    assumptions,
                    plan=plan,
                    root=root,
                    catalog=loaded_catalog,
                )
            )
            grading_inspection = _inspect_grading_assumptions_match_the_settings(
                plan, assumptions, root=root, catalog=loaded_catalog
            )
            grading_ceiling_problems = grading_inspection.all_findings
            problems.extend(grading_inspection.structural_problems)
            cost_findings.extend(grading_inspection.cost_findings)
            try:
                ceiling = estimate_cost_ceiling(
                    conditions_by_environment=conditions,
                    tasks_by_id=loaded_catalog.by_task_id(),
                    assumptions=assumptions,
                )
            except ValueError as error:
                problems.append(str(error))
            else:
                cost_findings.extend(
                    check_cost_ceiling(
                        ceiling,
                        approved_maximum_usd=approved_raw,
                        approved_maximum_required=(
                            cost_policy == COST_POLICY_BLOCK
                        ),
                    )
                )
                if approved_raw is not None:
                    try:
                        approved = Decimal(str(approved_raw))
                    except Exception:
                        approved = None

    if cost_policy == COST_POLICY_BLOCK:
        problems.extend(cost_findings)

    readiness_environ = environ
    if (
        cost_policy == COST_POLICY_RECORD_ONLY
        and owner_approval.get("paid_model_calls") is True
    ):
        import os

        readiness_environ = dict(os.environ if environ is None else environ)
        readiness_environ[PAID_RUN_APPROVAL_VARIABLE] = "yes"

    readiness = build_readiness_report(
        conditions_by_environment=conditions or None,
        comparison=str(plan.get("comparison") or COMPARISON_SAME_GENERATED_CODE),
        run_size_plan=plan.get("run_sizes"),
        scoreboards=plan.get("scoreboards"),
        docker_daemon_available=docker_daemon_available,
        docker_image_available=docker_image_available,
        azure_route_profile=azure_route_profile,
        docker_run_setting=(plan.get("container") or {}).get("use_docker"),
        environ=readiness_environ,
    )

    azure = _diagnose_azure(plan, conditions, environ, problems)

    return EnvelopePreflight(
        readiness=readiness,
        cost=ceiling,
        problems=problems,
        approved_maximum_usd=approved,
        cost_policy=cost_policy,
        cost_findings=cost_findings,
        available_monthly_credit_usd=available_monthly_credit_usd,
        azure=azure,
        grading_ceiling_problems=grading_ceiling_problems,
        input_files=input_files,
        missing_input_file_problems=missing_input_file_problems,
    )


def _diagnose_azure(
    plan: Mapping[str, Any],
    conditions: Mapping[str, ModelRunConditions],
    environ: Mapping[str, str] | None,
    problems: list[str],
) -> AzureConnectionDiagnosis | None:
    """Check the Azure run place points at the exact deployment that was pinned.

    Skipped when the Azure run place is not taking part, because then there is
    no Azure resource for the comparison to get wrong.

    Whether it takes part is read from the plan's own list of run places rather
    than from ``conditions``, which is empty whenever the conditions could not
    be assembled at all. A plan that leaves out ``azure_connection`` is one
    such plan — and it is exactly the plan this check exists to refuse, so
    reading the answer from ``conditions`` would switch the check off in the
    one case that needs it.
    """
    named = plan.get("model_run_conditions")
    named_places = (
        set(dict((named or {}).get("by_environment") or {}))
        if isinstance(named, Mapping)
        else set()
    )
    if ENVIRONMENT_AZURE_CODE_INTERPRETER not in (set(conditions) | named_places):
        return None

    raw = plan.get("azure_connection")
    if not isinstance(raw, Mapping):
        problems.append(
            "the plan asks the Azure run place to take part but does not say "
            "which Azure AI Foundry account and project must hold the "
            "deployment. A deployment name is not unique across accounts, so "
            "without this the comparison could run against a different "
            "deployment of the same name and never notice."
        )
        return None

    try:
        requirement = AzureConnectionRequirement.from_mapping(raw)
    except ValueError as error:
        problems.append(str(error))
        return None

    import os

    source = os.environ if environ is None else environ
    diagnosis = diagnose_azure_connection(requirement, source)
    problems.extend(diagnosis.problems)
    return diagnosis


def _runner_default_prompt_name(environment: str) -> str | None:
    """Which committed prompt file this run place falls back to.

    Read off the runner class that actually does the work, named in
    ``RUNNER_CLASS_BY_ENVIRONMENT``, rather than decided here from the mode
    name — the same reasoning as
    :func:`_runner_reference_file_prompt_sections`. ``None`` means this
    repository has no runner registered for the place, or the one it has does
    not declare a default; the caller turns either into a refusal rather than
    into a guess.

    Imported inside the function for the reason given on
    :func:`_runner_sends_a_fresh_request_per_turn`.
    """
    named = RUNNER_CLASS_BY_ENVIRONMENT.get(environment)
    if named is None:
        return None
    module_name, class_name = named
    try:
        module = import_module(module_name)
        runner = getattr(module, class_name)
        declared = getattr(runner, "DEFAULT_PROMPT")
    except (AttributeError, ImportError):
        return None
    return str(declared)


def _prompt_files_a_run_place_might_send(
    environment: str, settings: Mapping[str, Any]
) -> tuple[str, ...]:
    """Every committed prompt file this run place's settings could reach for.

    Two of them, where the two differ, and the caller prices the longer. That is
    not indecision, it is what ``core/executor.py`` does: the sandbox branch
    passes ``execution.sandbox.prompt_name`` on to the runner, while the
    subprocess branch reaches straight past it for ``SubprocessRunner``'s own
    ``DEFAULT_PROMPT``. So a ``prompt_name`` written into a settings file is
    followed in one place and ignored in another, and which of the two a run
    place takes is settled by wiring in ``executor.py`` that nothing here can
    read back.

    Rather than guess at that wiring, both candidates are returned. Charging the
    longer costs a plan nothing it would not have to hold anyway, and it leaves
    no arrangement of settings under which the prompt really sent is longer than
    the prompt priced. An empty tuple means this repository has no runner
    registered for the place, or the one it has declares no default: the caller
    turns that into a refusal rather than into a guess.
    """
    candidates: list[str] = []
    named = _dig(settings, ("execution", "sandbox")).get("prompt_name")
    if named:
        candidates.append(str(named))
    declared = _runner_default_prompt_name(environment)
    if declared and declared not in candidates:
        candidates.append(declared)
    return tuple(candidates)


def _check_instruction_length(
    conditions_by_environment: Mapping[str, ModelRunConditions],
    assumptions: CostAssumptions,
    *,
    plan: Mapping[str, Any],
    root: Path,
    catalog: TaskCatalog,
) -> list[str]:
    """Hold the cost sum's instruction length against the prompt really sent.

    ``instruction_character_count`` is the slot in
    :func:`core.execution_envelope_cost.max_input_tokens_per_call` that pays for
    everything a request carries besides the task's own words and its reference
    files. It is charged on every call every run place makes, so a figure below
    what is really sent understates the whole running half of the bill, once per
    call, for as long as the plan stands.

    This rule used to add up the two wording blocks the plan keeps in
    ``model_run_conditions`` and check the total matched. Both halves of that
    were wrong.

    * The ``system_instruction`` block it counted is never sent.
      :func:`core.prompt_loader.render_prompt` lets the committed prompt file's
      own ``system_message`` win whenever it has one, and all three committed
      files have one, so a run place's own ``system`` block is a fallback that
      never comes up. 345 characters were being charged for wording no model
      ever reads.
    * The committed prompt file itself was not counted at all — neither its
      standing instruction nor the several thousand characters of wording it
      wraps every task in. That is the great majority of what is sent.

    So the figure is now taken from the render rather than from the plan: each
    run place's prompt file is resolved the way ``core/executor.py`` resolves
    it, rendered through :func:`core.prompt_loader.fixed_prompt_characters` with
    that place's own ``condition_a.prompt`` block, and the sum charged is
    refused where it falls below what came back. Editing any of that wording
    moves the demand with it, and nothing here is a length somebody typed.

    Where the settings name a prompt file and the runner declares a different
    default, both are rendered and the longer is charged: see
    :func:`_prompt_files_a_run_place_might_send` for why the two can disagree
    and why guessing between them would leave a way to be under-charged.

    The occupation is written into every one of those templates, up to three
    times over, so the widest name in the committed catalogue is what they are
    rendered with. A plan running five tasks is then held to the widest of all
    220, which overstates slightly — the direction a ceiling may be wrong in.

    A plan more careful than its settings is left alone, exactly as in
    :func:`_check_the_plan_counts_every_call_the_container_makes`. Only the
    cheap direction is refused.

    **What the figure does not cover.** ``SandboxRunner._augment_prompt`` adds
    further sections to the container's first request — a deliverable contract
    section, a dependency hint, and a skills manual its committed settings
    currently switch off. Those are outside what ``render_prompt`` produces and
    outside this figure, and they are recorded as the next thing to price
    rather than left implied. What that means is a container demand smaller than
    the container's real first request, so this rule under-demands there; it
    never lets a plan claim more than the render proved.
    """
    problems: list[str] = []
    files = plan.get("experiment_files")
    files = files if isinstance(files, Mapping) else {}

    try:
        occupation = widest_occupation(catalog)
    except ValueError as unreadable:
        return [
            "the prompt every run place sends writes an occupation into it, "
            "but the widest one cannot be taken from the task catalogue, so "
            f"what the prompt comes to cannot be worked out: {unreadable}"
        ]

    for environment in sorted(conditions_by_environment):
        relative = files.get(environment)
        if not relative:
            problems.append(
                f"the plan names no experiment settings file for {environment}, "
                "so the prompt it sends cannot be read and the "
                "instruction_character_count charged for that prompt cannot be "
                "checked"
            )
            continue
        try:
            settings = yaml.safe_load(
                (root / str(relative)).read_text(encoding="utf-8")
            )
            if not isinstance(settings, Mapping):
                raise ValueError("it does not hold a mapping at the top level")
            candidates = _prompt_files_a_run_place_might_send(environment, settings)
            if not candidates:
                raise ValueError(
                    "no runner is registered for this run place, or the one "
                    "that is does not declare DEFAULT_PROMPT, so which prompt "
                    "file it sends is not written down anywhere here"
                )
            measured = {
                candidate: fixed_prompt_characters(
                    load_prompt(candidate),
                    experiment_prompt=_dig(settings, ("condition_a",)).get("prompt"),
                    occupation=occupation,
                )
                for candidate in candidates
            }
        except Exception as unreadable:  # noqa: BLE001 - anything here is a refusal
            # A missing settings file, a prompt file that is not there, wording
            # that will not render: every one of them leaves the request
            # unpriceable. Caught broadly and turned into a refusal rather than
            # allowed to pass this rule by falling through it.
            problems.append(
                f"{environment}'s cost is charged "
                f"{assumptions.instruction_character_count} characters for "
                "everything its request carries besides the task and its "
                "files, but that request cannot be built here and so cannot be "
                f"priced: {unreadable}"
            )
            continue

        name = max(measured, key=lambda candidate: sum(measured[candidate].values()))
        widths = measured[name]
        characters = sum(widths.values())
        if assumptions.instruction_character_count >= characters:
            continue
        short_by = characters - assumptions.instruction_character_count
        made_of = ", ".join(
            f"{width} characters of {what}"
            for what, width in sorted(widths.items(), key=lambda pair: -pair[1])
            if width
        )
        problems.append(
            f"{environment} sends prompts/{name}.yaml wrapped in its own "
            f"condition_a.prompt wording, which core/prompt_loader.py renders "
            f"to {characters} characters before the task's own words are added "
            f"({made_of}), but the plan's cost sum charges "
            f"{assumptions.instruction_character_count} characters for that "
            f"part of every request — {short_by} characters short, on every "
            "call this comparison makes"
        )
    return problems


def _inspect_grading_assumptions_match_the_settings(
    plan: Mapping[str, Any],
    assumptions: CostAssumptions,
    *,
    root: Path,
    catalog: TaskCatalog | None = None,
) -> GradingCostInspection:
    """Confirm the marking half of the cost sum is a ceiling, not a forecast.

    The half of the sum that prices running the tasks reads how far the
    settings let a run go and charges that. The half that prices marking rests
    on numbers written into the plan by hand, and this repository's own marking
    settings state limits that two of those numbers can be checked against —
    plus two whole models the sum never names. See
    :mod:`core.execution_envelope_grading_cost`.

    A plan that marks answers but names no marking settings file is a problem,
    not a pass. Nothing looked, and "nothing looked" is not "the numbers are
    high enough".

    One of the limits is not in the settings file at all. Every marking call
    carries the scoring line it is judging, and how wide that can be is a fact
    about the dataset, so it is read from ``catalog`` and passed down. When no
    catalogue reaches here the width goes down as *not measured*, and
    :func:`check_assumptions_cover_the_caps` refuses rather than working out an
    opening with a part of it missing.
    """
    if not assumptions.grading_required:
        return GradingCostInspection()
    relative = plan.get("grading_config")
    if relative is None or not str(relative).strip():
        return GradingCostInspection(
            structural_problems=[
                "the plan says the answers will be marked but names no marking "
                "settings file, so nothing checked whether the cost sum's "
                "marking numbers sit above the limits the marking would really "
                "apply"
            ]
        )
    widest_scoring_line: int | None = None
    if catalog is not None:
        try:
            widest_scoring_line = widest_scoring_line_characters(catalog)
        except ValueError:
            # An empty catalogue is reported elsewhere. Turning it into a
            # width of zero here would price the scoring line at nothing.
            widest_scoring_line = None
    try:
        caps = read_grading_caps(
            root / str(relative),
            widest_scoring_line_characters=widest_scoring_line,
        )
    except ValueError as error:
        return GradingCostInspection(
            structural_problems=[f"the marking settings could not be read: {error}"]
        )
    # Report the file the way the plan names it. Where this check happens to be
    # running from is nobody's business but this machine's.
    caps = replace(caps, settings_path=str(relative))
    try:
        prices: Mapping[str, ModelPrice] | None = load_price_table()
    except ValueError:
        # The price list is checked properly elsewhere. Failing to read it here
        # must not turn into a claim that every model has a published price.
        prices = None
    return GradingCostInspection(
        cost_findings=check_assumptions_cover_the_caps(
            assumptions, caps, prices=prices
        )
    )


def _check_grading_assumptions_match_the_settings(
    plan: Mapping[str, Any],
    assumptions: CostAssumptions,
    *,
    root: Path,
    catalog: TaskCatalog | None = None,
) -> list[str]:
    """Compatibility wrapper returning every grading-cost finding."""
    return _inspect_grading_assumptions_match_the_settings(
        plan, assumptions, root=root, catalog=catalog
    ).all_findings


def describe_input_file_checks(result: EnvelopePreflight) -> list[str]:
    """Readable lines saying how each input fingerprint was checked.

    Printed whether or not anything was wrong. A reader who is about to
    authorise a bill needs to see the difference between a fingerprint that was
    compared against the file and one that was taken on trust, and that
    difference is invisible in a list that only shows problems.
    """
    lines: list[str] = []
    for environment, verification in sorted(result.input_files.items()):
        if not verification.checks:
            lines.append(f"{environment}: no input fingerprint was written down")
            continue
        read = len(verification.fully_checked)
        lines.append(
            f"{environment}: {read} of {len(verification.checks)} input file(s) "
            "read off this machine and compared in full"
        )
        for check in verification.checks:
            lines.append(
                f"    [{check.state}] {check.path} "
                f"— {check.characters_compared} of 64 characters compared"
            )
    return lines


def describe_preflight(result: EnvelopePreflight) -> list[str]:
    """Readable lines summarising what was found."""
    lines: list[str] = []
    if result.cost is not None:
        lines.extend(describe_cost_ceiling(result.cost))
        if result.grading_ceiling_problems:
            # These totals are printed under a heading that calls them the
            # largest possible bill. Once the marking half is known to be too
            # low, saying so beside the number is the whole difference between
            # a reader quoting a ceiling and quoting a guess.
            lines.append(
                "WARNING: the marking figure above is not a ceiling — "
                f"{len(result.grading_ceiling_problems)} thing(s) the marking "
                "settings allow are not counted in it, so every total here is "
                "too low. See the problems below."
            )
    if result.cost_policy == COST_POLICY_RECORD_ONLY:
        lines.append(
            "cost policy: record findings only; cost estimates, missing prices, "
            "and missing measurements do not stop this owner-approved run"
        )
        if result.available_monthly_credit_usd is not None:
            lines.append(
                "available monthly credit recorded by the owner: "
                f"{result.available_monthly_credit_usd} United States dollars"
            )
        if result.cost_findings:
            lines.append(
                f"cost findings to measure and review after the run: "
                f"{len(result.cost_findings)}"
            )
    elif result.approved_maximum_usd is None:
        lines.append(
            "approved maximum: none on record, so nothing paid may start"
        )
    else:
        lines.append(
            f"approved maximum: {result.approved_maximum_usd} United States "
            "dollars"
        )
    return lines
