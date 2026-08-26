"""The complete free check that must pass before the comparison spends anything.

This is the last gate before money is involved. It ties together every check
that can be made without calling a model:

* the run places are graded from the code in this repository, and one that
  cannot run is never quietly replaced by one that can;
* the five tasks written into the plan are re-derived from the fixed rule and
  compared, so a task list cannot drift after results are seen;
* the fingerprints of every input file are checked against the dataset;
* each run place's experiment settings file is opened and compared against the
  shared conditions, so no run place can use a different model, a different
  deployment, different wording, a different task list, a different answer
  length, a different time limit, or a different number of attempts;
* the Docker run place is confirmed to be unable to fall back to the server's
  own operating system;
* the three Agentic Sandbox V2 guards are exercised and must still refuse;
* the largest possible bill is worked out and compared against the amount
  approved, and a missing amount is a refusal rather than a pass.

Nothing here calls a model, signs in to a cloud account, or spends anything.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

import yaml

from core.execution_envelope_cost import (
    CostCeiling,
    CostAssumptions,
    ModelPrice,
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
    TaskCatalog,
    check_catalog_carries_no_scores,
    check_input_file_versions,
    load_task_catalog,
    select_advance_check_tasks,
    selection_matches,
)
from core.execution_environment_readiness import (
    COMPARISON_SAME_GENERATED_CODE,
    ENVIRONMENT_AZURE_CODE_INTERPRETER,
    ENVIRONMENT_DOCKER_CONTAINER,
    ENVIRONMENT_HOST_PYTHON_PROCESS,
    EXECUTION_MODE_BY_ENVIRONMENT,
    ModelRunConditions,
    ReadinessReport,
    build_readiness_report,
)

PLAN_VERSION = "execution-envelope-advance-check-v1"

# The one container setting that stops a missing container from being replaced
# by the server's own operating system.
REQUIRED_CONTAINER_SETTING = "always"

# Which run places this plan is allowed to name. The two that are left out are
# left out because they cannot run, not because they were forgotten.
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
    azure: AzureConnectionDiagnosis | None = None
    grading_ceiling_problems: list[str] = field(default_factory=list)
    """Ways the marking half of the cost sum sits below what marking allows.

    Kept apart from the general problem list because these say something the
    other problems do not: the worked-out total printed above them is itself
    too low. A reader who sees only the total needs to be told that.
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
            "problems": self.all_problems,
            "grading_ceiling_problems": list(self.grading_ceiling_problems),
            "marking_half_is_a_ceiling": not self.grading_ceiling_problems,
            "azure_connection": (
                self.azure.as_dict() if self.azure is not None else None
            ),
        }


def load_plan(path: str | Path) -> dict:
    """Read the plan file that holds the conditions all run places share."""
    target = Path(path)
    loaded = yaml.safe_load(target.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("the plan file must hold a mapping at the top level")
    return loaded


def conditions_from_plan(plan: Mapping[str, Any]) -> dict[str, ModelRunConditions]:
    """Build each run place's conditions from the shared block plus its own."""
    raw = plan.get("model_run_conditions")
    if not isinstance(raw, Mapping):
        raise ValueError("the plan has no model_run_conditions block")
    shared = raw.get("shared") or {}
    per_environment = raw.get("by_environment")
    if not isinstance(per_environment, Mapping):
        raise ValueError("model_run_conditions.by_environment must be a mapping")
    resolved: dict[str, ModelRunConditions] = {}
    for environment, override in per_environment.items():
        merged = dict(shared)
        merged.update(dict(override or {}))
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
    return problems


# Settings that are not among the conditions written into the plan, but that
# would still change the answer if one run place had a different value. They
# are not given a fixed value here; they only have to be the same everywhere,
# because the comparison's whole claim is that nothing but the run place
# differs.
SETTINGS_THAT_MUST_SIMPLY_MATCH = (
    ("temperature", "how much the model varies its wording"),
    ("seed", "the number that makes a run repeatable"),
    ("reasoning_effort", "how hard the model is asked to think"),
)


def _check_settings_the_plan_does_not_name(
    settings_by_environment: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    """Confirm the run places agree on settings the plan never mentions.

    A setting the plan forgot to fix is still a setting. If one run place asks
    the model to think harder than another, the difference between their scores
    is not the run place.
    """
    problems: list[str] = []
    if len(settings_by_environment) < 2:
        return problems
    for name, description in SETTINGS_THAT_MUST_SIMPLY_MATCH:
        seen: dict[Any, list[str]] = {}
        for environment in sorted(settings_by_environment):
            condition_a = settings_by_environment[environment].get("condition_a")
            model = (
                condition_a.get("model")
                if isinstance(condition_a, Mapping)
                else None
            )
            value = model.get(name) if isinstance(model, Mapping) else None
            seen.setdefault(value, []).append(environment)
        if len(seen) > 1:
            groups = " | ".join(
                f"{value!r}: {', '.join(sorted(names))}"
                for value, names in sorted(seen.items(), key=lambda x: str(x[0]))
            )
            problems.append(
                f"the run places disagree on {description} ({name}), which the "
                "plan does not fix but which would change the answer: " + groups
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
) -> EnvelopePreflight:
    """Run every free check and return one answer listing every problem."""
    problems: list[str] = []

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
        selection = select_advance_check_tasks(loaded_catalog)
        for environment in sorted(conditions):
            problems.extend(
                f"{environment}: {note}"
                for note in selection_matches(
                    conditions[environment].task_ids, selection
                )
            )
            problems.extend(
                f"{environment}: {note}"
                for note in check_input_file_versions(
                    conditions[environment].input_file_versions,
                    conditions[environment].task_ids,
                    loaded_catalog,
                )
            )

    cost_block = plan.get("cost")
    cost_block = cost_block if isinstance(cost_block, Mapping) else {}
    ceiling: CostCeiling | None = None
    grading_ceiling_problems: list[str] = []
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
                _check_instruction_length(conditions, assumptions)
            )
            grading_ceiling_problems = (
                _check_grading_assumptions_match_the_settings(
                    plan, assumptions, root=root
                )
            )
            problems.extend(grading_ceiling_problems)
            try:
                ceiling = estimate_cost_ceiling(
                    conditions_by_environment=conditions,
                    tasks_by_id=loaded_catalog.by_task_id(),
                    assumptions=assumptions,
                )
            except ValueError as error:
                problems.append(str(error))
            else:
                problems.extend(
                    check_cost_ceiling(
                        ceiling, approved_maximum_usd=approved_raw
                    )
                )
                if approved_raw is not None:
                    try:
                        approved = Decimal(str(approved_raw))
                    except Exception:
                        approved = None

    readiness = build_readiness_report(
        conditions_by_environment=conditions or None,
        comparison=str(plan.get("comparison") or COMPARISON_SAME_GENERATED_CODE),
        run_size_plan=plan.get("run_sizes"),
        scoreboards=plan.get("scoreboards"),
        docker_daemon_available=docker_daemon_available,
        docker_image_available=docker_image_available,
        azure_route_profile=azure_route_profile,
        docker_run_setting=(plan.get("container") or {}).get("use_docker"),
        environ=environ,
    )

    azure = _diagnose_azure(plan, conditions, environ, problems)

    return EnvelopePreflight(
        readiness=readiness,
        cost=ceiling,
        problems=problems,
        approved_maximum_usd=approved,
        azure=azure,
        grading_ceiling_problems=grading_ceiling_problems,
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
    """
    if ENVIRONMENT_AZURE_CODE_INTERPRETER not in conditions:
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


def _check_instruction_length(
    conditions_by_environment: Mapping[str, ModelRunConditions],
    assumptions: CostAssumptions,
) -> list[str]:
    """Confirm the length used for the cost sum matches the real wording.

    If the two drift apart, the ceiling is worked out from wording that is not
    the wording being sent.
    """
    problems: list[str] = []
    for environment in sorted(conditions_by_environment):
        conditions = conditions_by_environment[environment]
        actual = len(conditions.system_instruction) + len(
            conditions.task_instruction
        )
        if actual != assumptions.instruction_character_count:
            problems.append(
                f"the cost sum assumes the standing and task instructions run "
                f"to {assumptions.instruction_character_count} characters, but "
                f"{environment} sends {actual}"
            )
    return problems


def _check_grading_assumptions_match_the_settings(
    plan: Mapping[str, Any],
    assumptions: CostAssumptions,
    *,
    root: Path,
) -> list[str]:
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
    """
    if not assumptions.grading_required:
        return []
    relative = plan.get("grading_config")
    if relative is None or not str(relative).strip():
        return [
            "the plan says the answers will be marked but names no marking "
            "settings file, so nothing checked whether the cost sum's marking "
            "numbers sit above the limits the marking would really apply"
        ]
    try:
        caps = read_grading_caps(root / str(relative))
    except ValueError as error:
        return [f"the marking settings could not be read: {error}"]
    # Report the file the way the plan names it. Where this check happens to be
    # running from is nobody's business but this machine's.
    caps = replace(caps, settings_path=str(relative))
    try:
        prices: Mapping[str, ModelPrice] | None = load_price_table()
    except ValueError:
        # The price list is checked properly elsewhere. Failing to read it here
        # must not turn into a claim that every model has a published price.
        prices = None
    return check_assumptions_cover_the_caps(assumptions, caps, prices=prices)


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
    if result.approved_maximum_usd is None:
        lines.append(
            "approved maximum: none on record, so nothing paid may start"
        )
    else:
        lines.append(
            f"approved maximum: {result.approved_maximum_usd} United States "
            "dollars"
        )
    return lines
