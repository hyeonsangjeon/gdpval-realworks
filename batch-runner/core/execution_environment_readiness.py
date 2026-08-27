"""Readiness check for running one GPT model in eight different places.

This module answers one question without ever calling a paid model:
*may the execution-environment comparison start, and if not, what exactly is
missing?*

Nothing here contacts a provider, signs in to a cloud account, or spends money.
Every check either reads the repository's own code or reads a plan the operator
wrote by hand, so the whole check is free to run and safe to run in CI.

The eight places a task can be run are described by :data:`ENVIRONMENTS`. Each
one is graded into exactly one of the five states in :data:`STATUSES`, together
with the file, function, setting, or product-documentation page that justifies
the grade.

Three of the eight are whole products that drive the work themselves — Codex's
own command-line tool and the GitHub Copilot command-line tool, twice. Those
three raise a question the first five never did: *where does the answer
actually come from?* Five of the places send the task to one named deployment
in one named Microsoft Foundry resource. The last one lets a product choose
the model. That is not a difference in run place; it is a difference in
product. It is written down in :data:`MODEL_SERVING_PATHS`, kept out of the
two comparisons that hold the model still, and scored on a board of its own.
"""

from __future__ import annotations

import importlib
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence, get_args

# ── The five states an execution environment can be in ─────────────────────
# Written as plain sentences so a reader never needs a separate word list.

STATUS_CAN_RUN_REAL_EXPERIMENT = "can_run_real_experiment"
"""A real experiment can be started here today."""

STATUS_STRUCTURE_CHECK_ONLY = "structure_check_only"
"""Only the structure can be checked; the model is never called."""

STATUS_NOT_IMPLEMENTED_HERE = "not_implemented_in_this_repository"
"""This repository contains no code that runs GDPVal tasks this way."""

STATUS_BLOCKED_REQUIREMENT_UNMET = "blocked_requirement_unmet"
"""The code exists, but something it needs is missing, so it must not start."""

STATUS_EVIDENCE_INSUFFICIENT = "evidence_insufficient"
"""There is not enough evidence to grade this environment either way."""

STATUSES = (
    STATUS_CAN_RUN_REAL_EXPERIMENT,
    STATUS_STRUCTURE_CHECK_ONLY,
    STATUS_NOT_IMPLEMENTED_HERE,
    STATUS_BLOCKED_REQUIREMENT_UNMET,
    STATUS_EVIDENCE_INSUFFICIENT,
)

# ── The eight places a task can be run ─────────────────────────────────────

ENVIRONMENT_HOST_PYTHON_PROCESS = "host_python_process"
ENVIRONMENT_DOCKER_CONTAINER = "docker_container"
ENVIRONMENT_AZURE_CODE_INTERPRETER = "azure_code_interpreter"
ENVIRONMENT_AGENTIC_SANDBOX_V2 = "agentic_sandbox_v2"
ENVIRONMENT_CODEX_BUILT_IN_AGENT = "codex_built_in_agent"
ENVIRONMENT_CODEX_COMMAND_LINE_TOOL_FOUNDRY = "codex_command_line_tool_foundry"
ENVIRONMENT_COPILOT_COMMAND_LINE_TOOL_FOUNDRY = "copilot_command_line_tool_foundry"
ENVIRONMENT_COPILOT_COMMAND_LINE_TOOL_GITHUB_SERVED = "copilot_command_line_tool_github_served"

ENVIRONMENTS = (
    ENVIRONMENT_HOST_PYTHON_PROCESS,
    ENVIRONMENT_DOCKER_CONTAINER,
    ENVIRONMENT_AZURE_CODE_INTERPRETER,
    ENVIRONMENT_AGENTIC_SANDBOX_V2,
    ENVIRONMENT_CODEX_BUILT_IN_AGENT,
    ENVIRONMENT_CODEX_COMMAND_LINE_TOOL_FOUNDRY,
    ENVIRONMENT_COPILOT_COMMAND_LINE_TOOL_FOUNDRY,
    ENVIRONMENT_COPILOT_COMMAND_LINE_TOOL_GITHUB_SERVED,
)

# ── Where the answer comes from ────────────────────────────────────────────
# Two run places can share every setting in the plan and still not be running
# the same model, because one of them lets a product pick. Writing the source
# down turns that into something a check can refuse.

SERVING_PATH_MICROSOFT_FOUNDRY_DEPLOYMENT = "microsoft_foundry_deployment"
"""One named deployment, in one named Microsoft Foundry resource, chosen by
the plan and by nobody else."""

SERVING_PATH_GITHUB_SERVED_COPILOT = "github_served_copilot"
"""A model GitHub serves to Copilot subscribers. Which model answers is
GitHub's decision, not the plan's."""

MODEL_SERVING_PATHS = (
    SERVING_PATH_MICROSOFT_FOUNDRY_DEPLOYMENT,
    SERVING_PATH_GITHUB_SERVED_COPILOT,
)

# Some run places are named after where their model comes from, so the plan is
# not free to claim otherwise. ``None`` means the plan decides and the check
# takes it at its word after confirming it is one of the paths above.
SERVING_PATH_FIXED_BY_ENVIRONMENT: Mapping[str, str | None] = {
    ENVIRONMENT_HOST_PYTHON_PROCESS: None,
    ENVIRONMENT_DOCKER_CONTAINER: None,
    ENVIRONMENT_AZURE_CODE_INTERPRETER: SERVING_PATH_MICROSOFT_FOUNDRY_DEPLOYMENT,
    ENVIRONMENT_AGENTIC_SANDBOX_V2: None,
    ENVIRONMENT_CODEX_BUILT_IN_AGENT: None,
    ENVIRONMENT_CODEX_COMMAND_LINE_TOOL_FOUNDRY: (
        SERVING_PATH_MICROSOFT_FOUNDRY_DEPLOYMENT
    ),
    ENVIRONMENT_COPILOT_COMMAND_LINE_TOOL_FOUNDRY: (
        SERVING_PATH_MICROSOFT_FOUNDRY_DEPLOYMENT
    ),
    ENVIRONMENT_COPILOT_COMMAND_LINE_TOOL_GITHUB_SERVED: SERVING_PATH_GITHUB_SERVED_COPILOT,
}

PRODUCT_CHOOSES_THE_MODEL = tuple(
    environment
    for environment, path in SERVING_PATH_FIXED_BY_ENVIRONMENT.items()
    if path is not None and path != SERVING_PATH_MICROSOFT_FOUNDRY_DEPLOYMENT
)
"""The run places where which model answers is not the plan's decision.

Derived from the table above rather than written out again, so a place added
there cannot be forgotten here.
"""

# Each place is reached by an ``execution.mode`` value in an experiment YAML
# file. ``None`` means this repository has no such setting at all.
EXECUTION_MODE_BY_ENVIRONMENT: Mapping[str, str | None] = {
    ENVIRONMENT_HOST_PYTHON_PROCESS: "subprocess",
    ENVIRONMENT_DOCKER_CONTAINER: "sandbox",
    ENVIRONMENT_AZURE_CODE_INTERPRETER: "code_interpreter",
    ENVIRONMENT_AGENTIC_SANDBOX_V2: "agentic_sandbox_v2",
    ENVIRONMENT_CODEX_BUILT_IN_AGENT: None,
    ENVIRONMENT_CODEX_COMMAND_LINE_TOOL_FOUNDRY: None,
    ENVIRONMENT_COPILOT_COMMAND_LINE_TOOL_FOUNDRY: None,
    ENVIRONMENT_COPILOT_COMMAND_LINE_TOOL_GITHUB_SERVED: None,
}

# The class that actually runs a task in each place, so the check can confirm
# the code is really present rather than trusting the mode name alone.
RUNNER_CLASS_BY_ENVIRONMENT: Mapping[str, tuple[str, str] | None] = {
    ENVIRONMENT_HOST_PYTHON_PROCESS: ("core.subprocess_runner", "SubprocessRunner"),
    ENVIRONMENT_DOCKER_CONTAINER: ("core.sandbox_runner", "SandboxRunner"),
    ENVIRONMENT_AZURE_CODE_INTERPRETER: (
        "core.code_interpreter",
        "CodeInterpreterRunner",
    ),
    ENVIRONMENT_AGENTIC_SANDBOX_V2: (
        "core.agentic_v2_runner",
        "AgenticV2IsolatedFixtureRunner",
    ),
    ENVIRONMENT_CODEX_BUILT_IN_AGENT: None,
    ENVIRONMENT_CODEX_COMMAND_LINE_TOOL_FOUNDRY: None,
    ENVIRONMENT_COPILOT_COMMAND_LINE_TOOL_FOUNDRY: None,
    ENVIRONMENT_COPILOT_COMMAND_LINE_TOOL_GITHUB_SERVED: None,
}

# ── What each product's own documentation says stands in the way ───────────
# A place with no code here is already refused. These add the reason a reader
# would otherwise have to go and find, and they are quoted from the product's
# own published reference rather than guessed. Each one is a separate reason:
# clearing one of them does not clear the others.

DOCUMENTED_BLOCKERS_BY_ENVIRONMENT: Mapping[str, tuple[str, ...]] = {
    ENVIRONMENT_CODEX_COMMAND_LINE_TOOL_FOUNDRY: (
        "the Codex command-line configuration reference gives a provider its "
        "key through env_key, an environment variable holding a static API "
        "key, or through an auth command that prints a bearer token; this "
        "repository forbids every static Azure credential variable in "
        "core.azure_ai_clients.FORBIDDEN_STATIC_AZURE_CREDENTIAL_ENV and "
        "raises in _reject_static_azure_credential_env when one is set, so the "
        "two cannot both hold",
        "that same reference documents no Microsoft Entra sign-in for a "
        "provider and shows no Azure example, so there is no published route "
        "from Codex to a Foundry deployment under this repository's sign-in "
        "rule; absence of a documented route is not evidence that one works",
        "the reference gives no api-version setting for a provider, while a "
        "Foundry deployment is pinned by API version in this comparison's "
        "fixed conditions, so the version actually used could not be shown",
    ),
    ENVIRONMENT_COPILOT_COMMAND_LINE_TOOL_FOUNDRY: (
        "the GitHub Copilot command-line own-key documentation supplies the "
        "model's credential through COPILOT_PROVIDER_API_KEY, a static API "
        "key; this repository forbids every static Azure credential variable "
        "in core.azure_ai_clients.FORBIDDEN_STATIC_AZURE_CREDENTIAL_ENV, so "
        "the two cannot both hold",
        "that documentation's Azure example points COPILOT_PROVIDER_BASE_URL "
        "at /openai/deployments/<deployment>, which is none of the three "
        "endpoint shapes core.azure_ai_clients.classify_endpoint accepts; "
        "that function raises on any other shape, so this address would be "
        "refused here even if the credential rule were satisfied",
    ),
    ENVIRONMENT_COPILOT_COMMAND_LINE_TOOL_GITHUB_SERVED: (
        "GitHub's published Copilot documentation describes automatic model "
        "selection routing a task to whichever model it judges best from "
        "real-time availability and task complexity, which is a model change "
        "the plan did not make and cannot see",
        "that same documentation designates a base model that will be used "
        "when no other model is available, which is a fallback to a different "
        "model rather than a stop",
        "which model answered is therefore GitHub's decision, so this place "
        "cannot join a comparison that holds the model still; it belongs to "
        "the whole-product comparison and to no other",
    ),
}

# ── The three comparisons, which must never share a score ──────────────────

COMPARISON_SAME_GENERATED_CODE = "same_generated_code_rerun"
"""Re-run one model's already-written code in each place, changing nothing else.

This isolates what the run place itself does to the result.
"""

COMPARISON_TOOL_BUILT_IN_FEATURES = "tool_built_in_features"
"""Let each tool use everything it ships with: writing code, picking its own
tools, reviewing its own output, retrying, and checking the result.

This measures the whole tool, not just the run place.
"""

COMPARISON_NATIVE_PRODUCT_BUNDLE = "native_product_bundle"
"""Compare whole products, each answering from wherever it normally answers.

The other two comparisons pin one deployment and change only where the task
runs, so a difference in score is a difference the run place made. This one
does not pin the model: a product may be answering from a model its own vendor
chose. What it measures is the finished product — the program driving the
work, its tools, whichever model it decided to ask, and all — so its result
may never be read as a statement about a run place, and never added to either
of the other two scores.
"""

COMPARISONS = (
    COMPARISON_SAME_GENERATED_CODE,
    COMPARISON_TOOL_BUILT_IN_FEATURES,
    COMPARISON_NATIVE_PRODUCT_BUNDLE,
)

SAME_MODEL_COMPARISONS = (
    COMPARISON_SAME_GENERATED_CODE,
    COMPARISON_TOOL_BUILT_IN_FEATURES,
)
"""The two comparisons that hold one deployment still.

Everything in these two must answer from the same place. A run place that lets
a product choose the model is refused here rather than quietly averaged in.
"""

REQUIRED_SCOREBOARDS = SAME_MODEL_COMPARISONS
"""The whole-product comparison is optional; the other two are not.

An operator may decide the product comparison is not worth its money and run
neither of its places. That is a choice about scope. Leaving out one of the two
same-model boards is not a choice about scope — it is the comparison losing its
control — so those two are always required.
"""

# ── The three reasons a task may be attempted again ────────────────────────

RETRY_INFRASTRUCTURE_ERROR = "infrastructure_error"
"""A network failure, a server error, or a timeout. The model did not decide
this; the run simply did not get through."""

RETRY_MODEL_SELF_REVIEW = "model_self_review"
"""The model looked at its own finished output, judged it inadequate, and
produced a new answer."""

RETRY_TOOL_LOOP_INTERNAL_RECOVERY = "tool_loop_internal_recovery"
"""The model and its tools were still talking to each other, a step failed, and
the model corrected course before it ever declared the task finished."""

RETRY_REASONS = (
    RETRY_INFRASTRUCTURE_ERROR,
    RETRY_MODEL_SELF_REVIEW,
    RETRY_TOOL_LOOP_INTERNAL_RECOVERY,
)

# ── What every run must write down, whichever place it ran in ──────────────

REQUIRED_RUN_RECORD_FIELDS = (
    "model_and_deployment",
    "system_instruction",
    "task_instruction",
    "task_ids",
    "input_file_versions",
    "executed_code_version",
    "started_at",
    "finished_at",
    "total_seconds",
    "model_call_count",
    "tool_run_count",
    "retry_counts_by_reason",
    "produced_files",
    "produced_file_check_results",
    "task_completed",
    "external_grade",
    "model_cost",
    "isolation_and_security",
    "failure_stage_and_reason",
)

# ── The three run sizes, fixed before anything is spent ────────────────────

RUN_SIZE_TASK_COUNTS: Mapping[str, int] = {
    "advance_check": 5,
    "trial_run": 30,
    "full_run": 220,
}

REQUIRED_RUN_SIZE_FIELDS = (
    "task_ids",
    "task_selection_method",
    "success_criteria",
    "stop_conditions",
    "advance_conditions",
    "maximum_expected_cost",
    "allowed_retry_reasons",
    "allowed_self_review_attempts",
)

# The environment variable that must say "yes" before any paid model call.
PAID_RUN_APPROVAL_VARIABLE = "EXECUTION_COMPARISON_PAID_RUN_APPROVED"


@dataclass(frozen=True)
class ModelRunConditions:
    """Everything that must stay byte-for-byte identical in every run place.

    One instance describes one run. If two runs in the comparison disagree on
    any field except ``resolved_model`` reporting, the comparison is not a
    comparison of run places any more, and the check fails.
    """

    provider: str
    resource: str
    deployment: str
    resolved_model: str
    api_version: str
    model_serving_path: str
    system_instruction: str
    task_instruction: str
    task_ids: tuple[str, ...]
    input_file_versions: Mapping[str, str]
    max_output_tokens: int
    per_task_timeout_seconds: int
    self_review_enabled: bool
    self_review_max_attempts: int
    retry_reasons_allowed: tuple[str, ...]
    retry_max_attempts: int
    automatic_model_switch_allowed: bool
    automatic_fallback_allowed: bool
    unsupported_runner_substitution_allowed: bool

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "ModelRunConditions":
        missing = [name for name in cls.field_names() if name not in raw]
        if missing:
            raise ValueError(
                "model run conditions are missing required entries: "
                + ", ".join(sorted(missing))
            )
        return cls(
            provider=str(raw["provider"]),
            resource=str(raw["resource"]),
            deployment=str(raw["deployment"]),
            resolved_model=str(raw["resolved_model"]),
            api_version=str(raw["api_version"]),
            model_serving_path=str(raw["model_serving_path"]),
            system_instruction=str(raw["system_instruction"]),
            task_instruction=str(raw["task_instruction"]),
            task_ids=tuple(str(value) for value in raw["task_ids"]),
            input_file_versions={
                str(key): str(value)
                for key, value in dict(raw["input_file_versions"]).items()
            },
            max_output_tokens=int(raw["max_output_tokens"]),
            per_task_timeout_seconds=int(raw["per_task_timeout_seconds"]),
            self_review_enabled=bool(raw["self_review_enabled"]),
            self_review_max_attempts=int(raw["self_review_max_attempts"]),
            retry_reasons_allowed=tuple(
                str(value) for value in raw["retry_reasons_allowed"]
            ),
            retry_max_attempts=int(raw["retry_max_attempts"]),
            automatic_model_switch_allowed=bool(
                raw["automatic_model_switch_allowed"]
            ),
            automatic_fallback_allowed=bool(raw["automatic_fallback_allowed"]),
            unsupported_runner_substitution_allowed=bool(
                raw["unsupported_runner_substitution_allowed"]
            ),
        )

    @staticmethod
    def field_names() -> tuple[str, ...]:
        return (
            "provider",
            "resource",
            "deployment",
            "resolved_model",
            "api_version",
            "model_serving_path",
            "system_instruction",
            "task_instruction",
            "task_ids",
            "input_file_versions",
            "max_output_tokens",
            "per_task_timeout_seconds",
            "self_review_enabled",
            "self_review_max_attempts",
            "retry_reasons_allowed",
            "retry_max_attempts",
            "automatic_model_switch_allowed",
            "automatic_fallback_allowed",
            "unsupported_runner_substitution_allowed",
        )

    def model_route_identity(self) -> tuple:
        """Where the answer comes from.

        Two run places that disagree on any of this are not asking the same
        model, whatever else they share. The two same-model comparisons
        require this to match. The whole-product comparison deliberately does
        not, because a difference here is the thing it is measuring.
        """
        return (
            self.provider,
            self.resource,
            self.deployment,
            self.resolved_model,
            self.api_version,
            self.model_serving_path,
        )

    def prompt_and_task_identity(self) -> tuple:
        """What is asked, and of which tasks. Must match in all three."""
        return (
            self.system_instruction,
            self.task_instruction,
            self.task_ids,
            tuple(sorted(self.input_file_versions.items())),
        )

    def budget_and_refusal_identity(self) -> tuple:
        """What one task may spend, and what the run refuses to do on its own.

        Must match in all three comparisons. A product allowed to quietly swap
        model, fall back, or move the work elsewhere is not comparable to one
        that stops, even when the comparison is between whole products.
        """
        return (
            self.max_output_tokens,
            self.per_task_timeout_seconds,
            self.automatic_model_switch_allowed,
            self.automatic_fallback_allowed,
            self.unsupported_runner_substitution_allowed,
        )

    def model_and_input_identity(self) -> tuple:
        """The part that must match in **both** same-model comparisons.

        If any of this differs, the runs are not answering the same question at
        all, whichever of those two comparisons is being made.
        """
        return (
            self.model_route_identity()
            + self.prompt_and_task_identity()
            + self.budget_and_refusal_identity()
        )

    def review_and_retry_identity(self) -> tuple:
        """The part that must match only in the first comparison.

        Re-running one model's own code isolates the run place, so self-review
        and retries have to be switched off identically everywhere. The second
        comparison deliberately lets each tool use its own self-review and
        retry behaviour, because that behaviour is what it measures.
        """
        return (
            self.self_review_enabled,
            self.self_review_max_attempts,
            tuple(sorted(self.retry_reasons_allowed)),
            self.retry_max_attempts,
        )


@dataclass
class EnvironmentReadiness:
    """How one run place was graded, and why."""

    environment: str
    status: str
    evidence: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "environment": self.environment,
            "status": self.status,
            "evidence": list(self.evidence),
            "blockers": list(self.blockers),
        }


@dataclass
class ReadinessReport:
    """The whole answer: per-place grades plus every problem found."""

    environments: list[EnvironmentReadiness]
    problems: list[str] = field(default_factory=list)
    paid_model_calls_approved: bool = False
    compared_environments: tuple[str, ...] = ENVIRONMENTS

    @property
    def blocked_environments(self) -> list[str]:
        """The places that were asked to take part but cannot run today."""
        return [
            entry.environment
            for entry in self.environments
            if entry.environment in self.compared_environments
            and entry.status != STATUS_CAN_RUN_REAL_EXPERIMENT
        ]

    @property
    def ready(self) -> bool:
        """True only when every place being compared could start right now.

        A place that is merely described, or that is blocked for any reason,
        keeps this False. Callers are meant to stop on False rather than drop
        the blocked place and continue with the rest.
        """
        if self.problems:
            return False
        return not self.blocked_environments

    def status_of(self, environment: str) -> str:
        for entry in self.environments:
            if entry.environment == environment:
                return entry.status
        raise KeyError(environment)

    def as_dict(self) -> dict[str, Any]:
        return {
            "paid_model_calls_approved": self.paid_model_calls_approved,
            "ready": self.ready,
            "compared_environments": list(self.compared_environments),
            "blocked_environments": self.blocked_environments,
            "environments": [entry.as_dict() for entry in self.environments],
            "problems": list(self.problems),
        }


def _import_attribute(module_name: str, attribute: str) -> Any:
    module = importlib.import_module(module_name)
    return getattr(module, attribute)


def registered_execution_modes() -> tuple[str, ...]:
    """Read the execution modes the dispatcher actually accepts."""
    execution_mode = _import_attribute("core.executor", "ExecutionMode")
    return tuple(str(value) for value in get_args(execution_mode))


def _runner_class_present(environment: str) -> tuple[bool, str]:
    target = RUNNER_CLASS_BY_ENVIRONMENT.get(environment)
    if target is None:
        return False, "no runner class is registered for this environment"
    module_name, attribute = target
    try:
        _import_attribute(module_name, attribute)
    except (ImportError, AttributeError) as error:
        return False, f"{module_name}.{attribute} is unavailable: {error}"
    return True, f"{module_name}.{attribute}"


def check_agentic_sandbox_v2_blocks_are_intact() -> list[str]:
    """Confirm nobody quietly opened the Agentic Sandbox V2 safety blocks.

    Three separate blocks are checked by running them, not by reading text:

    1. ``step2_run_inference._require_runnable_execution_mode`` must refuse the
       ``agentic_sandbox_v2`` mode outright, so the paid inference pipeline can
       never select it.
    2. ``core.executor.TaskExecutor`` must refuse to build a V2 runner unless it
       is told the run makes no paid model calls.
    3. The command-running tool ``exec_run`` on the offline stand-in backend
       ``core.agentic_v2_fixture_backend.AgenticV2FixtureBackend`` must report
       that the capability is unavailable for any ordinary command.
    """
    problems: list[str] = []

    try:
        guard = _import_attribute(
            "step2_run_inference", "_require_runnable_execution_mode"
        )
    except (ImportError, AttributeError) as error:
        problems.append(
            "the inference pipeline's execution-mode guard could not be loaded, "
            f"so the Agentic Sandbox V2 block cannot be confirmed: {error}"
        )
    else:
        try:
            guard("agentic_sandbox_v2")
        except ValueError:
            pass
        else:
            problems.append(
                "the inference pipeline no longer refuses the agentic_sandbox_v2 "
                "mode, so a paid run could select an environment that only "
                "supports model-free structure checks"
            )

    try:
        task_executor = _import_attribute("core.executor", "TaskExecutor")
    except (ImportError, AttributeError) as error:
        problems.append(
            "the task dispatcher could not be loaded, so the Agentic Sandbox V2 "
            f"block cannot be confirmed: {error}"
        )
    else:
        problems.extend(_check_dispatcher_refuses_a_paid_v2_run(task_executor))

    try:
        backend_class = _import_attribute(
            "core.agentic_v2_fixture_backend", "AgenticV2FixtureBackend"
        )
    except (ImportError, AttributeError) as error:
        problems.append(
            "the offline stand-in backend could not be loaded, so the exec_run "
            f"block cannot be confirmed: {error}"
        )
    else:
        problems.extend(_check_exec_run_stays_unavailable(backend_class))

    return problems


def _check_dispatcher_refuses_a_paid_v2_run(task_executor: Any) -> list[str]:
    """Confirm the dispatcher refuses V2 *because the run is paid*.

    Every other argument is filled in with something the dispatcher accepts, so
    declaring the run paid is the only remaining reason to refuse. Without this
    care the check would pass on any complaint at all, and deleting the paid-run
    block would go unnoticed because a later missing-argument complaint would
    take its place.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as fixture_root:
        try:
            task_executor(
                mode="agentic_sandbox_v2",
                non_paid_test_mode=False,
                agentic_v2_fixture_root=fixture_root,
                agentic_v2_scripted_calls=[],
            )
        except ValueError as error:
            if "model-free" not in str(error):
                return [
                    "the task dispatcher refused an Agentic Sandbox V2 run for "
                    f"an unexpected reason: {error}. The block that refuses a "
                    "paid run may have been removed."
                ]
            return []
        except Exception as error:  # pragma: no cover - defensive
            return [
                "the task dispatcher failed in an unexpected way while refusing "
                f"agentic_sandbox_v2: {error!r}"
            ]
    return [
        "the task dispatcher built an Agentic Sandbox V2 runner for a run that "
        "was declared to make paid model calls"
    ]


STRUCTURE_CHECK_PROFILE: Mapping[str, Any] = {
    "tool_contract_version": "2.0",
    "policy_profile_id": "offline-full-v1",
    "foundation_only": True,
}


def _check_exec_run_stays_unavailable(backend_class: Any) -> list[str]:
    import tempfile

    try:
        profile_class = _import_attribute(
            "core.agentic_v2_contract", "AgenticV2Profile"
        )
        profile = profile_class.from_mapping(dict(STRUCTURE_CHECK_PROFILE))
    except Exception as error:  # pragma: no cover - defensive
        return [
            "the structure-check settings for Agentic Sandbox V2 could not be "
            f"built, so the exec_run block cannot be confirmed: {error!r}"
        ]

    with tempfile.TemporaryDirectory() as temporary_root:
        try:
            backend = backend_class(
                root=Path(temporary_root) / "fixture", profile=profile
            )
        except Exception as error:  # pragma: no cover - defensive
            return [
                "the offline stand-in backend could not be built, so the "
                f"exec_run block cannot be confirmed: {error!r}"
            ]
        try:
            answer = backend.exec_run(
                {"cwd": "", "argv": ["python", "-c", "print(1)"]}
            )
        except Exception as error:  # pragma: no cover - defensive
            return [
                "the exec_run command tool raised instead of reporting that the "
                f"capability is unavailable: {error!r}"
            ]
        finally:
            close = getattr(backend, "close", None)
            if callable(close):
                close()

    if answer.get("ok") is not False:
        return [
            "the exec_run command tool accepted an ordinary command, so the "
            "Agentic Sandbox V2 block on running commands is no longer closed"
        ]
    if answer.get("error_type") != "capability_unavailable":
        return [
            "the exec_run command tool refused an ordinary command for an "
            f"unexpected reason: {answer.get('error_type')!r}"
        ]
    return []


def _why_a_real_model_is_out_of_reach() -> list[str]:
    """Ask the one place that establishes this instead of restating it.

    ``core.agentic_v2_stage_one_budget.check_stage_one_cannot_reach_a_model``
    settles this by running the loop with a stand-in that declares itself paid
    and requiring it to stop before asking the stand-in anything. Saying the
    same thing again here in a sentence is exactly what let the two free checks
    print contradicting answers in the same run, so this asks rather than says.

    Looked up by name, in this module's usual way, so a missing module is
    reported as an unanswered question rather than crashing the whole report.
    """
    try:
        establish = _import_attribute(
            "core.agentic_v2_stage_one_budget",
            "check_stage_one_cannot_reach_a_model",
        )
    except (ImportError, AttributeError) as error:
        return [
            "whether a real model can be reached could not be established, so "
            f"it has to be treated as reachable until somebody checks: {error}"
        ]
    try:
        return list(establish())
    except Exception as error:  # pragma: no cover - defensive
        return [
            "establishing whether a real model can be reached failed, so it "
            "has to be treated as reachable until somebody checks: "
            f"{type(error).__name__}: {error}"
        ]


def _agentic_sandbox_v2_blockers() -> list[str]:
    """Work out what stops this run place by running it, not by describing it.

    Until 2026-08-26 this was one hand-written sentence that said three things
    at once: that the command-running tool was closed, that the model never saw
    a tool result and never chose a next action, and that nobody had approved
    using this environment for real work.

    The middle one stopped being true when the loop was built.
    ``core.agentic_v2_conversation.run_model_conversation`` shows the model what
    a tool returned and asks it again, and is proven doing so against stand-ins
    that spend nothing. The sentence carried on being printed, because a
    sentence is not checked against anything, while the other free check
    established the opposite by running the code and printed that in the same
    session. A reader had two answers and no way to tell which one had been
    looked up.

    They are also three separate blockers with three different ways out —
    opening the command tool, reaching a real model, and an approval — so
    bundling them meant that when one of the three moved, nothing in the report
    changed shape.
    """
    blockers: list[str] = []

    blocks_that_opened = check_agentic_sandbox_v2_blocks_are_intact()
    if blocks_that_opened:
        blockers.extend(blocks_that_opened)
    else:
        blockers.append(
            "the command-running tool exec_run is closed: called here with an "
            "ordinary command, it answers that the capability is unavailable"
        )

    blockers.extend(_why_a_real_model_is_out_of_reach())

    blockers.append(
        "no approval exists to use this environment in a real experiment"
    )
    return blockers


def inspect_environment_support(
    *,
    docker_daemon_available: bool | None = None,
    docker_image_available: bool | None = None,
    azure_route_profile: str | None = None,
    docker_run_setting: str | None = None,
) -> list[EnvironmentReadiness]:
    """Grade all five run places against the code in this repository.

    The optional arguments describe the machine the comparison would run on.
    Passing ``None`` means "this was not measured", which produces
    :data:`STATUS_EVIDENCE_INSUFFICIENT` rather than an optimistic guess.
    """
    modes = registered_execution_modes()
    results: list[EnvironmentReadiness] = []

    for environment in ENVIRONMENTS:
        mode = EXECUTION_MODE_BY_ENVIRONMENT[environment]
        evidence: list[str] = []
        blockers: list[str] = []

        if mode is None:
            results.append(
                EnvironmentReadiness(
                    environment=environment,
                    status=STATUS_NOT_IMPLEMENTED_HERE,
                    evidence=[
                        "core.executor.ExecutionMode registers no run mode for "
                        "this environment, and no module in batch-runner starts "
                        "GDPVal tasks this way",
                    ],
                    blockers=[
                        "there is no code path in this repository that runs a "
                        "GDPVal task in this environment",
                        *DOCUMENTED_BLOCKERS_BY_ENVIRONMENT.get(environment, ()),
                    ],
                )
            )
            continue

        if mode not in modes:
            results.append(
                EnvironmentReadiness(
                    environment=environment,
                    status=STATUS_NOT_IMPLEMENTED_HERE,
                    evidence=[
                        f"core.executor.ExecutionMode does not list {mode!r}",
                    ],
                    blockers=[f"the run mode {mode!r} is not registered"],
                )
            )
            continue

        evidence.append(f"core.executor.ExecutionMode lists {mode!r}")
        runner_present, runner_note = _runner_class_present(environment)
        if not runner_present:
            results.append(
                EnvironmentReadiness(
                    environment=environment,
                    status=STATUS_NOT_IMPLEMENTED_HERE,
                    evidence=evidence + [runner_note],
                    blockers=[
                        "the class that would run the task is missing: "
                        + runner_note
                    ],
                )
            )
            continue
        evidence.append(f"the task is run by {runner_note}")

        if environment == ENVIRONMENT_AGENTIC_SANDBOX_V2:
            evidence.append(
                "the three safety blocks were run rather than read: "
                "step2_run_inference._require_runnable_execution_mode, "
                "core.executor.TaskExecutor's refusal of a paid run, and "
                "core.agentic_v2_fixture_backend.AgenticV2FixtureBackend."
                "exec_run on an ordinary command"
            )
            evidence.append(
                "whether a real model can be reached was settled by "
                "core.agentic_v2_stage_one_budget."
                "check_stage_one_cannot_reach_a_model, which runs the loop "
                "with a stand-in instead of describing what it would do"
            )
            blockers.extend(_agentic_sandbox_v2_blockers())
            results.append(
                EnvironmentReadiness(
                    environment=environment,
                    status=STATUS_STRUCTURE_CHECK_ONLY,
                    evidence=evidence,
                    blockers=blockers,
                )
            )
            continue

        if environment == ENVIRONMENT_DOCKER_CONTAINER:
            status = _grade_docker_container(
                evidence=evidence,
                blockers=blockers,
                docker_daemon_available=docker_daemon_available,
                docker_image_available=docker_image_available,
                docker_run_setting=docker_run_setting,
            )
            results.append(
                EnvironmentReadiness(
                    environment=environment,
                    status=status,
                    evidence=evidence,
                    blockers=blockers,
                )
            )
            continue

        if environment == ENVIRONMENT_AZURE_CODE_INTERPRETER:
            status = _grade_azure_code_interpreter(
                evidence=evidence,
                blockers=blockers,
                azure_route_profile=azure_route_profile,
            )
            results.append(
                EnvironmentReadiness(
                    environment=environment,
                    status=status,
                    evidence=evidence,
                    blockers=blockers,
                )
            )
            continue

        results.append(
            EnvironmentReadiness(
                environment=environment,
                status=STATUS_CAN_RUN_REAL_EXPERIMENT,
                evidence=evidence,
                blockers=blockers,
            )
        )

    return results


def _grade_docker_container(
    *,
    evidence: list[str],
    blockers: list[str],
    docker_daemon_available: bool | None,
    docker_image_available: bool | None,
    docker_run_setting: str | None,
) -> str:
    evidence.append(
        "core.sandbox_runner.SandboxRunner picks its runner in _execute, which "
        "quietly runs the code on the host machine instead when the container "
        "setting is 'auto' and either Docker or the image is missing"
    )

    if docker_run_setting is None:
        blockers.append(
            "the plan does not say whether the container is required, so a "
            "missing container could be replaced by the host machine without "
            "anyone noticing"
        )
        return STATUS_EVIDENCE_INSUFFICIENT
    if docker_run_setting != "always":
        blockers.append(
            "the container setting is "
            f"{docker_run_setting!r}; the comparison requires 'always' so that "
            "a missing container stops the run instead of silently moving the "
            "work to the host machine"
        )
        return STATUS_BLOCKED_REQUIREMENT_UNMET
    evidence.append(
        "the container setting is 'always', so a missing container fails the "
        "task loudly instead of moving the work to the host machine"
    )

    if docker_daemon_available is None or docker_image_available is None:
        blockers.append(
            "the Docker service and the sandbox image were not checked on the "
            "machine that would run the comparison"
        )
        return STATUS_EVIDENCE_INSUFFICIENT
    if not docker_daemon_available:
        blockers.append("the Docker service is not running on this machine")
        return STATUS_BLOCKED_REQUIREMENT_UNMET
    if not docker_image_available:
        blockers.append(
            "the sandbox container image is not present on this machine"
        )
        return STATUS_BLOCKED_REQUIREMENT_UNMET
    return STATUS_CAN_RUN_REAL_EXPERIMENT


def _grade_azure_code_interpreter(
    *,
    evidence: list[str],
    blockers: list[str],
    azure_route_profile: str | None,
) -> str:
    evidence.append(
        "step2_run_inference._require_code_interpreter_route_profile refuses "
        "this mode unless the AZURE_AI_ROUTE_PROFILE setting names the "
        "project-ci route"
    )
    evidence.append(
        "Microsoft's Responses API documentation describes the code "
        "interpreter tool as running Python inside a container the service "
        "manages: learn.microsoft.com/en-us/azure/foundry/openai/how-to/responses"
    )

    try:
        route_profile = _import_attribute("core.azure_ai_clients", "RouteProfile")
        required = str(route_profile.PROJECT_CI.value)
    except (ImportError, AttributeError) as error:
        blockers.append(
            "the required Azure route profile name could not be read from "
            f"core.azure_ai_clients.RouteProfile: {error}"
        )
        return STATUS_EVIDENCE_INSUFFICIENT

    if azure_route_profile is None:
        blockers.append(
            "the Azure route profile was not measured, so it is unknown "
            "whether this environment could start"
        )
        return STATUS_EVIDENCE_INSUFFICIENT
    if azure_route_profile != required:
        blockers.append(
            f"the Azure route profile is {azure_route_profile!r} but this "
            f"environment requires {required!r}"
        )
        return STATUS_BLOCKED_REQUIREMENT_UNMET
    evidence.append(f"the Azure route profile is set to {required!r}")
    return STATUS_CAN_RUN_REAL_EXPERIMENT


def check_model_run_conditions(
    conditions_by_environment: Mapping[str, ModelRunConditions],
    *,
    comparison: str = COMPARISON_SAME_GENERATED_CODE,
) -> list[str]:
    """Confirm the run places would run under the conditions the plan fixed.

    ``comparison`` decides what is allowed to differ.

    The first comparison re-runs one model's own code, so self-review and
    retries must be switched off identically everywhere. The second measures
    what each tool does on its own, so those are allowed to differ there — but
    the model, the resource, the deployment, the instructions, and the inputs
    still may not. The third compares whole products, so where the answer comes
    from is allowed to differ as well; what is asked, and what one task may
    spend, still may not.

    In all three, a run place that may change model on its own, fall back to
    something else, or move the work to a different runner is refused. The plan
    has to say so in writing; leaving the answer out is refused too, because a
    silent default here would be a permission nobody granted.
    """
    problems: list[str] = []
    if comparison not in COMPARISONS:
        problems.append(f"{comparison!r} is not one of the three comparisons")
    if not conditions_by_environment:
        return problems + ["no run place was given fixed model run conditions"]

    unknown = sorted(set(conditions_by_environment) - set(ENVIRONMENTS))
    if unknown:
        problems.append(
            "these run places are not part of the comparison: "
            + ", ".join(unknown)
        )

    holds_the_model_still = comparison in SAME_MODEL_COMPARISONS
    if comparison == COMPARISON_NATIVE_PRODUCT_BUNDLE and (
        len(conditions_by_environment) < 2
    ):
        problems.append(
            "the whole-product comparison was given "
            f"{len(conditions_by_environment)} run place; comparing products "
            "needs at least two, and one product on its own is a measurement "
            "rather than a comparison"
        )

    identities: dict[tuple, list[str]] = {}
    review_settings: dict[tuple, list[str]] = {}
    for environment, conditions in sorted(conditions_by_environment.items()):
        if conditions.automatic_model_switch_allowed:
            problems.append(
                f"{environment} allows switching to another model or another "
                "deployment on its own; the comparison requires that a run stop "
                "instead of quietly changing model"
            )
        if conditions.automatic_fallback_allowed:
            problems.append(
                f"{environment} allows carrying on with a substitute when "
                "something it needs is unavailable; the comparison requires "
                "that the run stop and be recorded as a failure, because a "
                "score produced by the substitute would be read as the score "
                "of the thing it replaced"
            )
        if conditions.unsupported_runner_substitution_allowed:
            problems.append(
                f"{environment} allows the task to be run somewhere other than "
                "the run place named here when that place cannot be used; the "
                "whole comparison is between run places, so a run that moves "
                "would report one place while measuring another"
            )
        if conditions.model_serving_path not in MODEL_SERVING_PATHS:
            problems.append(
                f"{environment} says the model is served by "
                f"{conditions.model_serving_path!r}, which is not one of the "
                "ways this comparison knows how to account for: "
                + ", ".join(MODEL_SERVING_PATHS)
            )
        elif SERVING_PATH_FIXED_BY_ENVIRONMENT.get(environment) not in (
            None,
            conditions.model_serving_path,
        ):
            problems.append(
                f"{environment} is a run place whose model always comes from "
                f"{SERVING_PATH_FIXED_BY_ENVIRONMENT[environment]}, but the "
                f"plan says {conditions.model_serving_path}; the plan cannot "
                "change where a product gets its model by writing down a "
                "different answer"
            )
        elif holds_the_model_still and conditions.model_serving_path != (
            SERVING_PATH_MICROSOFT_FOUNDRY_DEPLOYMENT
        ):
            problems.append(
                f"{environment} lets its own product choose which model "
                f"answers ({conditions.model_serving_path}), so it cannot take "
                f"part in {comparison}, which reports differences as though "
                "the model had been held still; it belongs to "
                f"{COMPARISON_NATIVE_PRODUCT_BUNDLE}"
            )
        unknown_reasons = sorted(
            set(conditions.retry_reasons_allowed) - set(RETRY_REASONS)
        )
        if unknown_reasons:
            problems.append(
                f"{environment} allows retry reasons that are not one of the "
                "three the comparison counts separately: "
                + ", ".join(unknown_reasons)
            )
        if not conditions.task_ids:
            problems.append(f"{environment} has an empty fixed task list")
        if conditions.self_review_enabled and (
            conditions.self_review_max_attempts <= 0
        ):
            problems.append(
                f"{environment} turns self-review on but allows zero attempts"
            )
        if not conditions.self_review_enabled and (
            conditions.self_review_max_attempts != 0
        ):
            problems.append(
                f"{environment} turns self-review off but still allows "
                f"{conditions.self_review_max_attempts} attempts"
            )
        if conditions.max_output_tokens <= 0:
            problems.append(
                f"{environment} does not cap how much text the model may write"
            )
        if conditions.per_task_timeout_seconds <= 0:
            problems.append(
                f"{environment} does not cap how long one task may run"
            )
        if comparison == COMPARISON_SAME_GENERATED_CODE and (
            conditions.self_review_enabled
        ):
            problems.append(
                f"{environment} turns self-review on, but the comparison that "
                "re-runs one model's own code must leave it off so the only "
                "thing that changes is the run place"
            )
        shared_part = (
            conditions.model_and_input_identity()
            if holds_the_model_still
            else conditions.prompt_and_task_identity()
            + conditions.budget_and_refusal_identity()
        )
        identities.setdefault(shared_part, []).append(environment)
        review_settings.setdefault(
            conditions.review_and_retry_identity(), []
        ).append(environment)

    if len(identities) > 1:
        problems.append(
            (
                "the run places do not share one fixed set of model run "
                "conditions; they split into these groups: "
                if holds_the_model_still
                else "the run places are not being asked the same thing for "
                "the same money; the whole-product comparison still fixes the "
                "instructions, the task list, the input files, and the budget, "
                "and they split into these groups: "
            )
            + _describe_groups(identities)
        )
    if comparison == COMPARISON_SAME_GENERATED_CODE and len(review_settings) > 1:
        problems.append(
            "the run places do not share one self-review and retry setting; "
            "the comparison that re-runs one model's own code needs them "
            "identical, and they split into these groups: "
            + _describe_groups(review_settings)
        )

    return problems


def _describe_groups(grouped: Mapping[tuple, list[str]]) -> str:
    return " | ".join(
        sorted(", ".join(sorted(names)) for names in grouped.values())
    )


def check_run_size_plan(plan: Mapping[str, Mapping[str, Any]]) -> list[str]:
    """Confirm the 5, 30, and 220 task stages were settled before spending."""
    problems: list[str] = []
    for stage, expected_count in RUN_SIZE_TASK_COUNTS.items():
        stage_plan = plan.get(stage)
        if not isinstance(stage_plan, Mapping):
            problems.append(f"the {stage} stage has no plan")
            continue
        # An empty list and a zero are real answers: the first comparison turns
        # self-review and retries off. Only an absent or null entry is missing.
        missing = [
            name
            for name in REQUIRED_RUN_SIZE_FIELDS
            if name not in stage_plan or stage_plan[name] is None
        ]
        if missing:
            problems.append(
                f"the {stage} stage is missing: " + ", ".join(sorted(missing))
            )
        if "task_ids" not in missing:
            task_ids = list(stage_plan["task_ids"])
            if len(task_ids) != expected_count:
                problems.append(
                    f"the {stage} stage fixes {len(task_ids)} tasks but must "
                    f"fix {expected_count}"
                )
            if len(set(task_ids)) != len(task_ids):
                problems.append(f"the {stage} stage repeats a task")
        if "allowed_retry_reasons" not in missing:
            unknown_reasons = sorted(
                set(stage_plan["allowed_retry_reasons"]) - set(RETRY_REASONS)
            )
            if unknown_reasons:
                problems.append(
                    f"the {stage} stage allows retry reasons the comparison "
                    "does not count: " + ", ".join(unknown_reasons)
                )
        if "allowed_self_review_attempts" not in missing:
            attempts = stage_plan["allowed_self_review_attempts"]
            if not isinstance(attempts, int) or attempts < 0:
                problems.append(
                    f"the {stage} stage must give a whole number of allowed "
                    "self-review attempts, using 0 to mean none"
                )
    return problems


def check_run_record_fields(record: Mapping[str, Any]) -> list[str]:
    """Confirm one finished run wrote down everything needed to re-check it."""
    missing = [
        name for name in REQUIRED_RUN_RECORD_FIELDS if name not in record
    ]
    problems = []
    if missing:
        problems.append(
            "the run record is missing: " + ", ".join(sorted(missing))
        )
    counts = record.get("retry_counts_by_reason")
    if isinstance(counts, Mapping):
        missing_reasons = sorted(set(RETRY_REASONS) - set(counts))
        if missing_reasons:
            problems.append(
                "the run record does not count these retry reasons separately: "
                + ", ".join(missing_reasons)
            )
    elif "retry_counts_by_reason" not in missing:
        problems.append(
            "the run record must count retries separately for each of the "
            "three reasons"
        )
    return problems


def check_comparisons_are_scored_apart(
    scoreboards: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    """Confirm the three comparisons never end up inside one score.

    The two same-model boards are always required. The whole-product board is
    not: an operator may decide that comparison is not worth its money. But if
    it is present it must be labelled as itself, and neither same-model board
    may quietly contain a run place whose model its own product chose.
    """
    problems: list[str] = []
    missing = sorted(set(REQUIRED_SCOREBOARDS) - set(scoreboards))
    if missing:
        problems.append(
            "these comparisons have no scoreboard of their own: "
            + ", ".join(missing)
        )
    extra = sorted(set(scoreboards) - set(COMPARISONS))
    if extra:
        problems.append(
            "these scoreboards belong to no known comparison: "
            + ", ".join(extra)
        )
    for name in sorted(set(scoreboards) & set(COMPARISONS)):
        board = scoreboards[name]
        labelled = board.get("comparison")
        if labelled != name:
            problems.append(
                f"the {name} scoreboard is labelled {labelled!r}, so results "
                "from the three comparisons could be added together by mistake"
            )
        if name not in SAME_MODEL_COMPARISONS:
            continue
        listed = board.get("environments")
        if listed is None:
            continue
        product_chosen = sorted(
            str(environment)
            for environment in listed
            if str(environment) in PRODUCT_CHOOSES_THE_MODEL
        )
        if product_chosen:
            problems.append(
                f"the {name} scoreboard counts run places whose own product "
                "chooses which model answers, so a product's model routing "
                "would be reported as an effect of the run place: "
                + ", ".join(product_chosen)
            )
    return problems


def paid_model_calls_approved(environ: Mapping[str, str] | None = None) -> bool:
    """Report whether someone approved spending money on model calls."""
    source = os.environ if environ is None else environ
    return source.get(PAID_RUN_APPROVAL_VARIABLE, "").strip().lower() == "yes"


def build_readiness_report(
    *,
    conditions_by_environment: Mapping[str, ModelRunConditions] | None = None,
    comparison: str = COMPARISON_SAME_GENERATED_CODE,
    run_size_plan: Mapping[str, Mapping[str, Any]] | None = None,
    scoreboards: Mapping[str, Mapping[str, Any]] | None = None,
    docker_daemon_available: bool | None = None,
    docker_image_available: bool | None = None,
    azure_route_profile: str | None = None,
    docker_run_setting: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> ReadinessReport:
    """Run every free check and return one answer with every problem listed.

    Environments that are not ready are never swapped for a different one. A
    missing requirement becomes a written problem, and the caller is expected to
    stop.

    When ``conditions_by_environment`` names the places being compared, only
    those places decide whether the report is ready. Otherwise all eight must
    be able to run, which today they cannot.
    """
    environments = inspect_environment_support(
        docker_daemon_available=docker_daemon_available,
        docker_image_available=docker_image_available,
        azure_route_profile=azure_route_profile,
        docker_run_setting=docker_run_setting,
    )
    approved = paid_model_calls_approved(environ)

    problems: list[str] = []
    problems.extend(check_agentic_sandbox_v2_blocks_are_intact())

    if conditions_by_environment is not None:
        problems.extend(
            check_model_run_conditions(
                conditions_by_environment, comparison=comparison
            )
        )
        graded = {entry.environment: entry for entry in environments}
        for environment in sorted(conditions_by_environment):
            entry = graded.get(environment)
            if entry is None or entry.status != STATUS_NOT_IMPLEMENTED_HERE:
                continue
            problems.append(
                f"the plan asks {environment} to take part, but this "
                "repository has no code that runs a GDPVal task there; the "
                "run must stop rather than let a run place that does exist "
                "stand in for it, because the result would be filed under the "
                "name of the place that never ran. What is missing: "
                + "; ".join(entry.blockers)
            )
    if run_size_plan is not None:
        problems.extend(check_run_size_plan(run_size_plan))
    if scoreboards is not None:
        problems.extend(check_comparisons_are_scored_apart(scoreboards))

    for entry in environments:
        if entry.status != STATUS_CAN_RUN_REAL_EXPERIMENT:
            continue
        if approved:
            continue
        entry.status = STATUS_BLOCKED_REQUIREMENT_UNMET
        entry.blockers.append(
            "nobody has approved spending money on model calls, so this "
            f"environment must not start; set {PAID_RUN_APPROVAL_VARIABLE}=yes "
            "only after that approval exists"
        )

    for entry in environments:
        if entry.status not in STATUSES:  # pragma: no cover - defensive
            problems.append(
                f"{entry.environment} was graded {entry.status!r}, which is not "
                "one of the five states"
            )

    compared = (
        tuple(
            environment
            for environment in ENVIRONMENTS
            if environment in conditions_by_environment
        )
        if conditions_by_environment
        else ENVIRONMENTS
    )

    return ReadinessReport(
        environments=environments,
        problems=problems,
        paid_model_calls_approved=approved,
        compared_environments=compared,
    )


def measure_docker_availability(image: str | None = None) -> tuple[bool, bool]:
    """Look at this machine's Docker service and sandbox image, free of charge."""
    sandbox_runner = importlib.import_module("core.sandbox_runner")
    daemon = bool(sandbox_runner.docker_available())
    if not daemon:
        return False, False
    target = image or sandbox_runner.DEFAULT_SANDBOX_IMAGE
    return True, bool(sandbox_runner.docker_image_exists(target))


def describe_environment(environment: str) -> str:
    """Return a one-sentence plain description of a run place."""
    return {
        ENVIRONMENT_HOST_PYTHON_PROCESS: (
            "the model writes Python and the batch runner runs it as a separate "
            "process on the server's own operating system"
        ),
        ENVIRONMENT_DOCKER_CONTAINER: (
            "the model writes Python and the batch runner runs it inside a "
            "Docker container built from a fixed image"
        ),
        ENVIRONMENT_AZURE_CODE_INTERPRETER: (
            "Azure AI Foundry runs the model's Python for it, inside a container "
            "the service creates and manages"
        ),
        ENVIRONMENT_AGENTIC_SANDBOX_V2: (
            "the model would repeatedly pick a tool, read the result, and choose "
            "the next action inside a container this repository controls"
        ),
        ENVIRONMENT_CODEX_BUILT_IN_AGENT: (
            "Codex runs its own built-in agent: it picks its own tools, runs "
            "commands, reviews its work, and retries without this repository "
            "directing any of it"
        ),
        ENVIRONMENT_CODEX_COMMAND_LINE_TOOL_FOUNDRY: (
            "Codex's own command-line tool does the whole task, but the model "
            "it asks is the same named deployment in the same Microsoft "
            "Foundry resource the other run places use, so the only thing "
            "that changes is the program driving the work"
        ),
        ENVIRONMENT_COPILOT_COMMAND_LINE_TOOL_FOUNDRY: (
            "the GitHub Copilot command-line tool does the whole task using "
            "its own-key setting, pointed at the same named deployment in the "
            "same Microsoft Foundry resource, so again the only thing that "
            "changes is the program driving the work"
        ),
        ENVIRONMENT_COPILOT_COMMAND_LINE_TOOL_GITHUB_SERVED: (
            "the GitHub Copilot command-line tool does the whole task on a "
            "model GitHub serves, so the product chooses which model answers "
            "and this is a comparison of products rather than of run places"
        ),
    }[environment]
