"""Check one preregistration offline. This module cannot launch an experiment.

Exit 2 means the study must not spend, even when its configuration is valid.
Both adapters can render the requested effort, but served capabilities and
native call limits remain unverified or unwired.
Keeping that refusal separate from configuration validity prevents a passing
fixture from being mistaken for a verified Foundry deployment or a launch gate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal

import yaml

from core.agentic_v2_conversation_runner import ceilings_from
from core.agentic_v2_model_voice import reasoning_request_fields
from core.agentic_v2_preregistration import seal
from core.codex_runtime_config import (
    DEFAULT_PROVIDER_ID,
    PINNED_CODEX_CLI_VERSION,
    PINNED_CODEX_SDK_VERSION,
    requested_model_config_overrides,
)
from core.execution_envelope_tasks import (
    catalog_sha256,
    load_task_catalog,
    select_advance_check_tasks,
)
from core.experiment_config import CodexComparisonCapture, ExperimentConfig

ROOT = Path(__file__).resolve().parents[1]
BASE_SHA = "a855c5a9604554499be9eed4e5eb5523e8ad95d5"
GRADER_SOURCE_SHA = BASE_SHA
ENVELOPE = "batch-runner/experiments/execution_envelope/"
PLAN = ROOT / ENVELOPE / "gpt54_sandboxv2_codex_comparison.yaml"
V2_TEMPLATE = ENVELOPE + "agentic_corrected_harness_plan.yaml"
CODEX_TEMPLATE = "batch-runner/experiments/exp033_codex_foundry_fixed5.yaml"
GRADER = "batch-runner/grading_configs/default_v2_sol_max.yaml"
REQUIRED_SOURCES = {
    "batch-runner/gpt54_comparison_preflight.py",
    "batch-runner/gpt54_v2_grading_input.py",
    "batch-runner/gpt54_codex_grading_input.py",
    "batch-runner/gpt54_prepared_input_attestation.py",
    "batch-runner/gpt54_codex_input_capture.py",
    "batch-runner/gpt54_v2_input_capture.py",
    "batch-runner/gpt54_run_config_bundle.py",
    "batch-runner/gpt54_run_input_bundle.py",
    "batch-runner/gpt54_disposable_checkout.py",
    "batch-runner/prepare_dataset.py",
    "batch-runner/step8_grade.py",
    "batch-runner/core/config.py",
    "batch-runner/core/agentic_v2_preregistration.py",
    "batch-runner/core/execution_envelope_tasks.py",
    ENVELOPE + "gdpval_task_catalog.json",
    ENVELOPE + "advance_check_plan.yaml",
    V2_TEMPLATE,
    CODEX_TEMPLATE,
    GRADER,
    "batch-runner/schemas/grade.schema.json",
    "batch-runner/core/result_projection.py",
    "batch-runner/core/agentic_v2_model_voice.py",
    "batch-runner/core/agentic_v2_conversation_runner.py",
    "batch-runner/core/agentic_v2_stage_one_budget.py",
    "batch-runner/scripts/run_agentic_v2_stage.py",
    "batch-runner/core/codex_runtime_config.py",
    "batch-runner/core/codex_runner.py",
    "batch-runner/core/experiment_config.py",
    "batch-runner/core/executor.py",
    "batch-runner/step1_prepare_tasks.py",
    "batch-runner/step2_run_inference.py",
}

# These are findings on BASE_SHA, not user-editable waivers. Removing a blocker
# requires a reviewed implementation and a new contract, not an enabled flag.
LAUNCH_BLOCKERS = (
    "v2_reasoning_effort_capability_unverified",
    "codex_reasoning_effort_capability_unverified",
    "codex_native_model_call_and_token_limits_unenforced",
    "live_deployment_identity_and_input_bytes_not_verified",
    "comparison_materialization_and_workflow_gates_not_wired",
    "comparison_usage_and_tariff_evidence_unverified",
)


def load_plan(path: Path = PLAN) -> dict[str, Any]:
    """Read the checked-in contract without reading credentials or the network."""
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("comparison plan must be an object")
    return value


def _configuration_problems(plan: dict[str, Any]) -> list[str]:
    """Check the sealed sources before deriving any entrypoint configuration."""
    if not isinstance(plan, dict):
        return ["manifest_not_object"]
    problems: list[str] = []

    pins = plan.get("source_pins")
    if not isinstance(pins, dict) or set(pins) != REQUIRED_SOURCES:
        return ["source_pin_set"]
    for name, digest in pins.items():
        path = ROOT / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            problems.append(f"source_pin:{name}")
    if problems:
        return problems

    def expect(name: str, actual: Any, expected: Any) -> None:
        # Preserve type as well as value: True is not the integer 1.
        if seal({"value": actual}) != seal({"value": expected}):
            problems.append(name)

    envelope = load_plan(ROOT / ENVELOPE / "advance_check_plan.yaml")
    v2 = load_plan(ROOT / V2_TEMPLATE)
    codex = load_plan(ROOT / CODEX_TEMPLATE)
    grader = load_plan(ROOT / GRADER)
    # This existing helper seals the entire grader closure, not just step8:
    # all core Python, requirements includes, schema, prompts and config bytes.
    # Import only after the directly required pins have passed.
    from step8_grade import SCHEMA_VERSION, compute_grader_source_hash

    grader_source_hash = compute_grader_source_hash(
        ROOT / GRADER, grader, batch_root=ROOT / "batch-runner",
    )
    catalog = load_task_catalog()
    selection = select_advance_check_tasks(catalog)
    by_id = {task.task_id: task for task in catalog.tasks}

    expect("plan_version", plan.get("plan_version"), "gpt54-sandboxv2-codex-comparison-v1")
    expect("base_sha", plan.get("base_sha"), BASE_SHA)
    expect("comparison", plan.get("comparison"), "configuration_bundle")
    expect("paid_comparison_approved", plan.get("paid_comparison_approved"), True)
    expect("launch_enabled", plan.get("launch_enabled"), False)
    expect(
        "template_model",
        codex["condition_a"]["model"]["deployment"],
        v2["model"]["deployment"],
    )
    limits = ceilings_from(v2, SimpleNamespace(**v2["cost"]["chosen_settings"])).as_dict()
    limits.update(
        attempts_per_task=v2["fixed_settings"]["retry_max_attempts"],
        request_max_retries=0,
        stream_max_retries=0,
        self_review_max_attempts=0,
        resume_max_rounds=0,
    )
    expected = {
        "model": {
            "provider": "azure",
            "account": v2["azure_connection"]["account"],
            "deployment": "gpt-5.4",
            "resolved_model": "gpt-5.4",
            "route_profile": "direct-v1",
            "reasoning_effort": "xhigh",
            "automatic_model_switch_allowed": False,
        },
        "dataset": {
            "repo_id": catalog.dataset_repo_id,
            "revision": catalog.dataset_revision,
            "parquet_sha256": catalog.dataset_file_sha256,
            "catalog_sha256": catalog_sha256(),
            "cohort": "advance_check_5",
            "tasks": [
                {"task_id": task_id, "prompt_sha256": by_id[task_id].prompt_sha256}
                for task_id in selection.task_ids
            ],
            "input_file_versions": envelope["model_run_conditions"]["shared"][
                "input_file_versions"
            ],
        },
        "limits": limits,
        "grading": {
            "config": GRADER,
            "source_sha": GRADER_SOURCE_SHA,
            "template_source_sha256": grader_source_hash,
            "rubric_revision": catalog.dataset_revision,
            "prompt_version": grader["prompt"]["version"],
            "judge_model": grader["judge"]["model"],
            "judge_effort": grader["judge"]["reasoning"]["effort"],
            "grades_per_task": 1,
        },
        "results": {
            "projector": "core.result_projection.project_result_row",
            "receipt_schema": "cost-receipt-v1",
            "grade_schema": "batch-runner/schemas/grade.schema.json",
            "grade_schema_version": SCHEMA_VERSION,
            "missing_or_unpriced_usage": "preserve_null_and_partial_reasons",
        },
        "cost": {
            "policy": envelope["cost"]["policy"],
            "approved_maximum_usd": None,
        },
    }
    expect("shared_controls", plan.get("shared"), expected)
    expect(
        "conditions",
        plan.get("conditions"),
        {
            "sandbox_v2": {
                "controls": expected,
                "template": V2_TEMPLATE,
                "workflow": ".github/workflows/agentic-v2-stage-run.yml",
                "isolation": "same-host",
                "replay_format": "faithful",
                "input_capture": "gpt54-pre-execution-input-v1",
                "request": {
                    "reasoning_effort": expected["model"]["reasoning_effort"],
                },
            },
            "codex": {
                "controls": expected,
                "template": CODEX_TEMPLATE,
                "workflow": ".github/workflows/batch-run.yml",
                "sdk_version": PINNED_CODEX_SDK_VERSION,
                "cli_version": PINNED_CODEX_CLI_VERSION,
                "input_capture": "gpt54-pre-execution-input-v1",
                "request": {
                    "reasoning_effort": expected["model"]["reasoning_effort"],
                    "model_context_window": None,
                },
            },
        },
    )
    expect(
        "repetition_matrix",
        plan.get("runs"),
        [
            {
                "run_id": f"gpt54_v2_codex_v1_{suffix}_r{repeat}",
                "condition": condition,
                "repeat": repeat,
                "task_count": 5,
            }
            for condition, suffix, repeat in (
                ("sandbox_v2", "v2", 1),
                ("codex", "codex", 1),
                ("codex", "codex", 2),
                ("sandbox_v2", "v2", 2),
            )
        ],
    )
    return problems


def _canonical_json(value: Any) -> str:
    """Use the existing seal's JSON representation, without host-specific data."""
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False,
    )


class DispatchPlanRefused(ValueError):
    """The manifest cannot produce a reviewed four-run dispatch plan."""


@dataclass(frozen=True)
class ComparisonRunSpec:
    """One inert recipe, relative to its own separately materialized checkout.

    Commands are data, never executed here. JSON config is accepted by the
    existing YAML readers. A separate checkout is required because the batch
    entrypoints derive their workspace from source location, not from cwd.
    """

    run_id: str
    condition: Literal["sandbox_v2", "codex"]
    repeat: int
    harness: Literal["agentic_sandbox_v2", "codex"]
    provider: str
    model: str
    reasoning_effort: str
    cohort: str
    task_ids: tuple[str, ...]
    checkout_directory: str
    working_directory: str
    config_path: str
    config_json: str
    commands: tuple[tuple[str, ...], ...]

    def as_dict(self) -> dict[str, Any]:
        """Return JSON-native values without exposing mutable internal state."""
        return json.loads(_canonical_json(asdict(self)))


@dataclass(frozen=True)
class ComparisonDispatchPlan:
    """A byte-stable offline plan, not an authorization or dispatch service."""

    manifest_sha256: str
    source_base_sha: str
    source_pins_json: str
    controls_json: str
    runs: tuple[ComparisonRunSpec, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "plan_version": "gpt54-offline-dispatch-v1",
            "manifest_sha256": self.manifest_sha256,
            "source_base_sha": self.source_base_sha,
            "source_pins": json.loads(self.source_pins_json),
            "shared_controls": json.loads(self.controls_json),
            "materialization": "separate_source_checkout_per_run",
            "input_directory": "data/gdpval-local",
            "launch_allowed": False,
            "full_220_allowed": False,
            "runs": [run.as_dict() for run in self.runs],
        }

    def canonical_bytes(self) -> bytes:
        """Return UTF-8 bytes whose digest uses the existing seal contract."""
        return _canonical_json(self.as_dict()).encode("utf-8")


def _compile_validated_plan(plan: dict[str, Any]) -> ComparisonDispatchPlan:
    shared = plan["shared"]
    model, dataset, limits = (shared[key] for key in ("model", "dataset", "limits"))
    task_ids = tuple(task["task_id"] for task in dataset["tasks"])
    runs = []
    for row in plan["runs"]:
        condition = row["condition"]
        target = plan["conditions"][condition]
        config = load_plan(ROOT / target["template"])
        if condition == "sandbox_v2":
            from gpt54_v2_input_capture import V2ComparisonCapture

            config["comparison_input_capture"] = V2ComparisonCapture(target["input_capture"]).as_dict()
            config["model"].update(
                deployment=model["deployment"], resolved_model=model["resolved_model"],
                **target["request"],
            )
            config["azure_connection"].update(
                account=model["account"], route_profile=model["route_profile"],
            )
            config["task_ids"] = list(task_ids)
            config["fixed_settings"].update(
                retry_max_attempts=limits["attempts_per_task"],
                self_review_max_attempts=limits["self_review_max_attempts"],
                per_task_timeout_seconds=limits["max_seconds"],
                replay_format=target["replay_format"],
            )
            commands = ((
                "python3", "scripts/run_agentic_v2_stage.py",
                "--stage", dataset["cohort"], "--plan", "comparison-run.json",
                "--parquet", "../data/gdpval-local/data/train-00000-of-00001.parquet",
                "--dataset-root", "../data/gdpval-local",
                "--run-id", row["run_id"], "--into", "workspace",
            ),)
            harness = "agentic_sandbox_v2"
        else:
            config["experiment"].update(
                id=row["run_id"], name=f"GPT-5.4 comparison: Codex repeat {row['repeat']}",
                description="Offline compiled comparison configuration; launch remains blocked.",
            )
            config["data"]["source"] = dataset["repo_id"]
            config["data"]["filter"]["task_ids"] = list(task_ids)
            config["condition_a"]["model"].update(
                provider=model["provider"], deployment=model["deployment"],
                reasoning_effort=model["reasoning_effort"],
            )
            config["execution"]["codex"].update(
                model=model["deployment"], provider_id=DEFAULT_PROVIDER_ID,
                **target["request"],
                request_max_retries=limits["request_max_retries"],
                stream_max_retries=limits["stream_max_retries"],
            )
            config["execution"].update(
                timeout=limits["max_seconds"], max_retries=limits["attempts_per_task"] - 1,
                resume_max_rounds=limits["resume_max_rounds"],
                comparison_input_capture=CodexComparisonCapture(row["run_id"], target["input_capture"]).as_dict(),
            )
            errors = ExperimentConfig.from_dict(config).validate()
            if errors:
                raise DispatchPlanRefused("compiled Codex configuration: " + "; ".join(errors))
            commands = (
                ("python3", "step1_prepare_tasks.py", "--config", "comparison-run.json"),
                ("python3", "step2_run_inference.py", "--condition", "condition_a",
                 "--max-retries", "0", "--resume-max-rounds", "0", "--no-resume",
                 "--comparison-run-id", row["run_id"]),
            )
            harness = "codex"
        runs.append(ComparisonRunSpec(
            run_id=row["run_id"], condition=condition, repeat=row["repeat"],
            harness=harness, provider=model["provider"], model=model["deployment"],
            reasoning_effort=model["reasoning_effort"], cohort=dataset["cohort"],
            task_ids=task_ids, checkout_directory=f"comparison-runs/{row['run_id']}",
            working_directory="batch-runner", config_path="batch-runner/comparison-run.json",
            config_json=_canonical_json(config), commands=commands,
        ))
    return ComparisonDispatchPlan(
        manifest_sha256=seal(plan), source_base_sha=plan["base_sha"],
        source_pins_json=_canonical_json(plan["source_pins"]),
        controls_json=_canonical_json(shared), runs=tuple(runs),
    )


def compile_dispatch_plan(plan: dict[str, Any]) -> ComparisonDispatchPlan:
    """Compile exactly four typed recipes or refuse; never materialize or run.

    Raises:
        DispatchPlanRefused: If a manifest, control, or source pin disagrees.
    """
    try:
        problems = _configuration_problems(plan)
        if problems:
            raise DispatchPlanRefused("comparison refused: " + ", ".join(problems))
        return _compile_validated_plan(plan)
    except DispatchPlanRefused:
        raise
    except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError) as error:
        raise DispatchPlanRefused("comparison inputs cannot be compiled") from error


@dataclass(frozen=True)
class GradingOutputSpec:
    """Checkout-relative templates, not filenames backed by a live run.

    Step8 needs the future inference publication revision and the source hash
    of the materialized config. Neither is the dataset SHA or this Git base.
    """

    grade_path_template: str
    ledger_sqlite_path_template: str
    ledger_jsonl_path_template: str
    ordered_task_ids_sha256: str
    config_sha256: str
    resolver: str = "step8_grade.resolve_grade_output_path"
    resolution: str = "blocked_until_verified_inference_source_and_materialized_config"
    inference_repo_id: None = None
    inference_revision: None = None
    materialized_grader_source_hash: None = None


@dataclass(frozen=True)
class ComparisonGradingRunSpec:
    """One offline grading recipe in the corresponding dispatch checkout."""

    run_id: str
    condition: Literal["sandbox_v2", "codex"]
    repeat: int
    task_ids: tuple[str, ...]
    checkout_directory: str
    working_directory: str
    producer_results_path: str
    producer_rows_pointer: str
    inference_results_path: str
    staged_deliverables_directory: str
    input_materialization: str
    experiment_config_path: str
    experiment_config_json: str
    grader_config_path: str
    grader_config_json: str
    grader_contract_json: str
    command: tuple[str, ...]
    output: GradingOutputSpec

    def as_dict(self) -> dict[str, Any]:
        return json.loads(_canonical_json(asdict(self)))


@dataclass(frozen=True)
class ComparisonGradingPlan:
    """Exact-bound dispatch and grading artifacts; no materialization or spend."""

    dispatch: ComparisonDispatchPlan
    runs: tuple[ComparisonGradingRunSpec, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "plan_version": "gpt54-offline-dispatch-grading-v1",
            "dispatch_plan": self.dispatch.as_dict(),
            "grading_runs": [run.as_dict() for run in self.runs],
            "launch_allowed": False,
            "full_220_allowed": False,
        }

    def canonical_bytes(self) -> bytes:
        return _canonical_json(self.as_dict()).encode("utf-8")


def _compile_grading_plan(dispatch: ComparisonDispatchPlan) -> ComparisonGradingPlan:
    # No client or RubricLoader is instantiated. These are step8's real config
    # validator and task-order hash, reached only after the source pins pass.
    from step8_grade import _ordered_task_ids_sha256, validate_grading_config

    shared = json.loads(dispatch.controls_json)
    contract = shared["grading"]
    config = load_plan(ROOT / contract["config"])
    config["rubric"].update(
        revision=contract["rubric_revision"], cache_dir="../data/gdpval-local",
    )
    config_json = _canonical_json(config)
    # The real validator checks prompt existence relative to cwd. Resolve only
    # this validation copy; emitted bytes stay relative to each run checkout.
    validation_copy = json.loads(config_json)
    for key in ("template", "tool_template"):
        if key in validation_copy["prompt"]:
            validation_copy["prompt"][key] = str(
                ROOT / "batch-runner" / validation_copy["prompt"][key]
            )
    validate_grading_config(validation_copy)
    output_root = (ROOT / "batch-runner" / config["output"]["directory"]).resolve()
    output_relative = output_root.relative_to(ROOT)
    runs = []
    for run in dispatch.runs:
        task_scope = _ordered_task_ids_sha256(list(run.task_ids))
        # Explicit --tasks/--limit is diagnostic under step8's existing policy.
        # Preserve its filename template: do not invent an inference revision.
        grade_path = (
            output_relative / "_diagnostic" / task_scope
            / config["output"]["filename_template"]
        )
        output = GradingOutputSpec(
            grade_path_template=grade_path.as_posix(),
            ledger_sqlite_path_template=grade_path.with_suffix(".cost_ledger.sqlite3").as_posix(),
            ledger_jsonl_path_template=grade_path.with_suffix(".cost_ledger.jsonl").as_posix(),
            ordered_task_ids_sha256=task_scope,
            config_sha256=hashlib.sha256(config_json.encode("utf-8")).hexdigest(),
        )
        if run.condition == "codex":
            experiment = json.loads(run.config_json)
            producer = "batch-runner/workspace/step2_inference_results.json"
            pointer = "/results"
            materialization = "gpt54_codex_grading_input.materialize_codex_grading_input"
        else:
            stage = json.loads(run.config_json)
            # Step8 consumes ExperimentConfig metadata, not a V2 stage plan.
            # This is not an alternate inference recipe; dispatch stays above.
            experiment = {
                "experiment": {
                    "id": run.run_id,
                    "name": f"GPT-5.4 comparison: V2 repeat {run.repeat}",
                    "description": "Grading metadata only; use the separate dispatch recipe.",
                },
                "data": {"source": shared["dataset"]["repo_id"],
                         "filter": {"task_ids": list(run.task_ids)}},
                "condition_a": {
                    "name": run.condition,
                    "model": {"provider": run.provider, "deployment": run.model,
                              "reasoning_effort": run.reasoning_effort},
                    "qa": {"enabled": False},
                },
                "execution": {
                    "mode": "agentic_sandbox_v2",
                    "agentic_v2": {
                        "tool_contract_version": "2.0",
                        "policy_profile_id": stage.get("policy_profile_id", "offline-full-v1"),
                        "foundation_only": True,
                    },
                },
                "output": {"publish_to_hf": False, "submit_to_evals": False},
            }
            producer = "batch-runner/workspace/run_record.json"
            pointer = "/run/results"
            materialization = "gpt54_v2_grading_input.materialize_v2_grading_input"
        errors = ExperimentConfig.from_dict(experiment).validate()
        if errors:
            raise DispatchPlanRefused("grading experiment metadata: " + "; ".join(errors))
        experiment_name = f"execution_envelope/{run.run_id}"
        runs.append(ComparisonGradingRunSpec(
            run_id=run.run_id, condition=run.condition, repeat=run.repeat,
            task_ids=run.task_ids, checkout_directory=run.checkout_directory,
            working_directory=run.working_directory,
            producer_results_path=producer, producer_rows_pointer=pointer,
            inference_results_path="batch-runner/workspace/step2_inference_results.json",
            staged_deliverables_directory="batch-runner/workspace/upload/deliverable_files",
            input_materialization=materialization,
            experiment_config_path=f"batch-runner/experiments/{experiment_name}.yaml",
            experiment_config_json=_canonical_json(experiment),
            grader_config_path="batch-runner/comparison-grading.json",
            grader_config_json=config_json,
            grader_contract_json=_canonical_json({**contract, "results": shared["results"]}),
            command=(
                "python3", "step8_grade.py", experiment_name,
                "--config", "comparison-grading.json", "--source", "local",
                "--tasks", ",".join(run.task_ids), "--limit", "5",
                "--shard-count", "1", "--shard-index", "0", "--run-ordinal", "1",
                "--source-experiment-id", run.run_id,
            ),
            output=output,
        ))
    return ComparisonGradingPlan(dispatch=dispatch, runs=tuple(runs))


def compile_grading_plan(
    plan: dict[str, Any], *, dispatch_plan: dict[str, Any] | None = None,
) -> ComparisonGradingPlan:
    """Reuse the four-run compiler and refuse mismatched dispatch input offline."""
    try:
        dispatch = compile_dispatch_plan(plan)
        if dispatch_plan is not None and _canonical_json(dispatch_plan).encode("utf-8") != dispatch.canonical_bytes():
            raise DispatchPlanRefused("dispatch_plan_mismatch")
        return _compile_grading_plan(dispatch)
    except DispatchPlanRefused:
        raise
    except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError) as error:
        raise DispatchPlanRefused("grading inputs cannot be compiled") from error


def inspect_plan(
    plan: dict[str, Any], *, dispatch_plan: dict[str, Any] | None = None,
    grading_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Bind supplied dispatch/combined grading documents; still refuse launch."""
    problems = _configuration_problems(plan)
    compiled = _compile_validated_plan(plan) if not problems else None
    if compiled is not None and dispatch_plan is not None:
        if _canonical_json(dispatch_plan).encode("utf-8") != compiled.canonical_bytes():
            problems.append("dispatch_plan_mismatch")
    grading = _compile_grading_plan(compiled) if compiled is not None and not problems else None
    if grading is not None and grading_plan is not None:
        if _canonical_json(grading_plan).encode("utf-8") != grading.canonical_bytes():
            problems.append("grading_plan_mismatch")
    if problems:
        compiled = None
        grading = None
    return {
        "configuration_valid": not problems,
        "configuration_problems": problems,
        "plan_sha256": seal(plan) if isinstance(plan, dict) else None,
        "dispatch_plan": compiled.as_dict() if compiled is not None else None,
        "dispatch_plan_sha256": seal(compiled.as_dict()) if compiled is not None else None,
        "grading_plan": grading.as_dict() if grading is not None else None,
        "grading_plan_sha256": seal(grading.as_dict()) if grading is not None else None,
        # Review evidence only: no provider or runtime is constructed here.
        "requested_v2_responses_fields": (
            reasoning_request_fields(**plan["conditions"]["sandbox_v2"]["request"])
            if not problems else None
        ),
        "requested_codex_config_overrides": (
            list(requested_model_config_overrides(
                **plan["conditions"]["codex"]["request"]
            ))
            if not problems else None
        ),
        "codex_pre_execution_capture": ({
            "binding_version": "gpt54-pre-execution-input-v1",
            "required_runs": [run.run_id for run in compiled.runs if run.condition == "codex"],
            "evidence_boundary": "local_pre_execution_snapshot_consistency",
        } if compiled is not None else None),
        "v2_pre_execution_capture": ({
            "binding_version": "gpt54-pre-execution-input-v1",
            "required_runs": [run.run_id for run in compiled.runs if run.condition == "sandbox_v2"],
            "evidence_boundary": "local_pre_execution_snapshot_consistency",
        } if compiled is not None else None),
        "run_config_bundle": ({
            "bundle_version": "gpt54-run-config-bundle-v1",
            "materializer": "gpt54_run_config_bundle.materialize_run_config_bundle",
            "ready_marker": "comparison-bundle-ready.json",
            "required_runs": [run.run_id for run in compiled.runs],
            "checkout_creation": False,
            "evidence_boundary": "local_config_bundle_consistency",
        } if compiled is not None else None),
        "run_input_bundle": ({
            "bundle_version": "gpt54-run-input-bundle-v1",
            "materializer": "gpt54_run_input_bundle.materialize_run_input_bundle",
            "ready_marker": "comparison-inputs-ready.json",
            "reservation": "comparison-inputs-reserved.json",
            "dataset_root": "data/gdpval-local",
            "reference_scope": "advance_check_5_only",
            "required_runs": [run.run_id for run in compiled.runs],
            "checkout_creation": False,
            "evidence_boundary": "local_input_bundle_consistency",
        } if compiled is not None else None),
        "disposable_checkout": ({
            "checkout_version": "gpt54-disposable-checkout-v1",
            "preparer": "gpt54_disposable_checkout.prepare_disposable_checkout",
            "ready_marker": "comparison-checkout-ready.json",
            "reviewed_source_sha": "required_external_full_commit_sha_not_source_base",
            "git_mutation": "worktree add --detach",
            "required_runs": [run.run_id for run in compiled.runs],
            "failure_policy": "retain_reservation_and_quarantine_no_reuse_or_cleanup",
            "evidence_boundary": "local_reviewed_checkout_and_bundles",
        } if compiled is not None else None),
        "launch_allowed": False,
        "full_220_allowed": False,
        "launch_blockers": list(LAUNCH_BLOCKERS),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=PLAN)
    parser.add_argument(
        "--dispatch-plan", type=Path,
        help="Compare an offline compiled document; never execute it",
    )
    parser.add_argument(
        "--grading-plan", type=Path,
        help="Compare the combined dispatch/grading document; never grade or execute",
    )
    args = parser.parse_args(argv)
    try:
        result = inspect_plan(
            load_plan(args.plan),
            dispatch_plan=load_plan(args.dispatch_plan) if args.dispatch_plan else None,
            grading_plan=load_plan(args.grading_plan) if args.grading_plan else None,
        )
    except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError) as error:
        result = {"configuration_valid": False, "launch_allowed": False, "error": str(error)}
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 2  # This config/spec PR cannot authorize or dispatch a paid run.


if __name__ == "__main__":
    raise SystemExit(main())
