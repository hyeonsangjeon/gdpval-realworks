"""Experiment Configuration from YAML

Loads and validates experiment configurations from YAML files.

Usage:
    from core.experiment_config import ExperimentConfig

    # Load from file
    config = ExperimentConfig.from_yaml("experiments/exp001_baseline.yaml")

    # Access settings
    print(config.experiment_id)
    print(config.condition_a.model_deployment)
    print(config.data_filter.sector)
"""

import yaml
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Literal

from core.config import DEFAULT_TOKENS
from core.repository_identity import (
    validate_experiment_id,
    validate_hf_dataset_repo_id,
)
from core.agentic_experiments import (
    validate_agentic_budget_for_experiment,
    validate_agentic_experiment_identity,
)


@dataclass
class ModelConfig:
    """Model configuration"""
    provider: str  # "azure", "openai", "anthropic"
    deployment: str
    temperature: float = 0.0
    seed: Optional[int] = None
    reasoning_effort: Optional[str] = None  # "low", "medium", "high"
    max_tokens: Optional[int] = None


@dataclass
class PromptConfig:
    """Prompt configuration"""
    system: str
    prefix: Optional[str] = None
    body: Optional[str] = None
    suffix: Optional[str] = None


@dataclass
class QAConfig:
    """Self-QA configuration — LLM inspects its own output"""
    enabled: bool = False
    max_retries: int = 2           # Number of retries on QA failure
    model: Optional[str] = None    # None = same model as generation
    min_score: int = 6             # QA fails if score is below this (1-10)
    prompt: str = ""               # QA prompt template


@dataclass
class ConditionConfig:
    """Experimental condition configuration"""
    name: str
    model: ModelConfig
    prompt: PromptConfig
    qa: Optional[QAConfig] = None
    preprocessors: Optional[List[Dict[str, Any]]] = None


@dataclass
class DataFilterConfig:
    """Data filter configuration"""
    source: str
    sector: Optional[str] = None
    occupation: Optional[str] = None
    sample_size: Optional[int] = None
    task_ids: Optional[List[str]] = None


@dataclass
class ControlConfig:
    """Control variables configuration"""
    fixed: List[str]
    changed: List[str]


@dataclass
class OutputConfig:
    """Output configuration"""
    publish_to_hf: bool = False
    submit_to_evals: bool = False
    save_path: Optional[str] = None


@dataclass
class ExecutionConfig:
    """Execution mode configuration (Phase 5-3)"""
    mode: Literal[
        "code_interpreter", "subprocess", "json_renderer", "sandbox",
        "agentic_sandbox",
    ] = "subprocess"
    score_type: Literal["tool_assisted", "portable"] = "tool_assisted"
    max_retries: int = 3           # Infrastructure retries within task execution
    resume_max_rounds: int = 3     # Auto-retry rounds for error tasks in progress.json
    install_libreoffice: bool = False  # Install LibreOffice + Noto Sans (for Elicit)
    tokens: Dict[str, int] = field(default_factory=lambda: dict(DEFAULT_TOKENS))
    timeout: Optional[int] = None  # subprocess timeout override (seconds)
    sandbox: Optional[Dict[str, Any]] = None  # sandbox-mode settings (execution.sandbox block)
    agentic: Optional[Dict[str, Any]] = None  # agentic-mode settings (execution.agentic block)
    metrics: Optional[Dict[str, Any]] = None  # opt-in job metrics (execution.metrics block)


class ExperimentConfig:
    """Experiment configuration from YAML file

    Example:
        config = ExperimentConfig.from_yaml("experiments/exp001.yaml")
        print(config.experiment_id)
        print(config.condition_a.model.deployment)
    """

    def __init__(
        self,
        experiment_id: str,
        name: str,
        description: str,
        author: str,
        created_at: str,
        control: ControlConfig,
        data_filter: DataFilterConfig,
        condition_a: ConditionConfig,
        output: OutputConfig,
        condition_b: Optional[ConditionConfig] = None,
        execution: Optional[ExecutionConfig] = None,
    ):
        self.experiment_id = experiment_id
        self.name = name
        self.description = description
        self.author = author
        self.created_at = created_at
        self.control = control
        self.data_filter = data_filter
        self.condition_a = condition_a
        self.condition_b = condition_b
        self.output = output
        self.execution = execution or ExecutionConfig()  # Default if not provided

    @property
    def is_ab_test(self) -> bool:
        """True if this is an A/B test (condition_b is present)"""
        return self.condition_b is not None

    @classmethod
    def from_yaml(cls, filepath: str) -> "ExperimentConfig":
        """Load configuration from YAML file

        Args:
            filepath: Path to YAML file

        Returns:
            ExperimentConfig instance

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If YAML is invalid
        """
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {filepath}")

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExperimentConfig":
        """Create config from dictionary

        Args:
            data: Configuration dictionary

        Returns:
            ExperimentConfig instance
        """
        # Parse experiment metadata
        exp_data = data.get("experiment", {})

        # Parse control
        control_data = data.get("control", {})
        control = ControlConfig(
            fixed=control_data.get("fixed", []),
            changed=control_data.get("changed", []),
        )

        # Parse data filter
        data_config = data.get("data", {})
        filter_data = data_config.get("filter", {})
        data_filter = DataFilterConfig(
            source=data_config.get("source", "openai/gdpval"),
            sector=filter_data.get("sector"),
            occupation=filter_data.get("occupation"),
            sample_size=filter_data.get("sample_size"),
            task_ids=filter_data.get("task_ids"),
        )

        # Parse condition A
        cond_a_data = data.get("condition_a", {})
        condition_a = cls._parse_condition(cond_a_data)

        # Parse condition B (optional — absent means single test)
        cond_b_data = data.get("condition_b")
        condition_b = cls._parse_condition(cond_b_data) if cond_b_data else None

        # Parse output
        output_data = data.get("output", {})
        output = OutputConfig(
            publish_to_hf=output_data.get("publish_to_hf", False),
            submit_to_evals=output_data.get("submit_to_evals", False),
            save_path=output_data.get("save_path"),
        )

        # Parse execution (Phase 5-3)
        execution_data = data.get("execution", {})
        tokens_data = execution_data.get("tokens", {})
        execution_tokens = dict(DEFAULT_TOKENS)
        if isinstance(tokens_data, dict):
            for key in ("code_generation", "qa_check", "json_render"):
                value = tokens_data.get(key)
                if value is None:
                    continue
                try:
                    parsed = int(value)
                    if parsed > 0:
                        execution_tokens[key] = parsed
                except (TypeError, ValueError):
                    continue

        execution = ExecutionConfig(
            mode=execution_data.get("mode", "subprocess"),
            score_type=execution_data.get("score_type", "tool_assisted"),
            max_retries=execution_data.get("max_retries", 3),
            resume_max_rounds=execution_data.get("resume_max_rounds", 3),
            install_libreoffice=execution_data.get("install_libreoffice", False),
            tokens=execution_tokens,
            timeout=execution_data.get("timeout"),
            sandbox=execution_data.get("sandbox"),
            agentic=(
                dict(execution_data["agentic"])
                if isinstance(execution_data.get("agentic"), dict)
                else None
            ),
            metrics=(
                {"enabled": True}
                if isinstance(execution_data.get("metrics"), dict)
                and execution_data["metrics"].get("enabled") is True
                else None
            ),
        )

        return cls(
            experiment_id=exp_data.get("id", "unknown"),
            name=exp_data.get("name", "Unnamed Experiment"),
            description=exp_data.get("description", ""),
            author=exp_data.get("author", ""),
            created_at=exp_data.get("created_at", ""),
            control=control,
            data_filter=data_filter,
            condition_a=condition_a,
            output=output,
            condition_b=condition_b,
            execution=execution,
        )

    @staticmethod
    def _parse_condition(data: Dict[str, Any]) -> ConditionConfig:
        """Parse condition configuration"""
        model_data = data.get("model", {})
        prompt_data = data.get("prompt", {})

        model = ModelConfig(
            provider=model_data.get("provider", "azure"),
            deployment=model_data.get("deployment", "gpt-4"),
            temperature=model_data.get("temperature", 0.0),
            seed=model_data.get("seed"),
            reasoning_effort=model_data.get("reasoning_effort"),
            max_tokens=model_data.get("max_tokens"),
        )

        prompt = PromptConfig(
            system=prompt_data.get("system", "You are a helpful assistant."),
            prefix=prompt_data.get("prefix"),
            body=prompt_data.get("body"),
            suffix=prompt_data.get("suffix"),
        )

        # Parse QA config (optional)
        qa_data = data.get("qa", {})
        qa = None
        if qa_data:
            qa = QAConfig(
                enabled=qa_data.get("enabled", False),
                max_retries=qa_data.get("max_retries", 2),
                model=qa_data.get("model"),
                min_score=qa_data.get("min_score", 6),
                prompt=qa_data.get("prompt", ""),
            )

        # Parse preprocessors (optional — list of dicts, kept as raw YAML)
        preprocessors = data.get("preprocessors", None)

        return ConditionConfig(
            name=data.get("name", "Unnamed"),
            model=model,
            prompt=prompt,
            qa=qa,
            preprocessors=preprocessors,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert config back to dictionary

        Returns:
            Configuration as dictionary
        """
        return {
            "experiment": {
                "id": self.experiment_id,
                "name": self.name,
                "description": self.description,
                "author": self.author,
                "created_at": self.created_at,
            },
            "control": {
                "fixed": self.control.fixed,
                "changed": self.control.changed,
            },
            "data": {
                "source": self.data_filter.source,
                "filter": {
                    "sector": self.data_filter.sector,
                    "occupation": self.data_filter.occupation,
                    "sample_size": self.data_filter.sample_size,
                    "task_ids": self.data_filter.task_ids,
                },
            },
            "condition_a": self._condition_to_dict(self.condition_a),
            **({
                "condition_b": self._condition_to_dict(self.condition_b)
            } if self.condition_b else {}),
            "output": {
                "publish_to_hf": self.output.publish_to_hf,
                "submit_to_evals": self.output.submit_to_evals,
                "save_path": self.output.save_path,
            },
            "execution": {
                "mode": self.execution.mode,
                "score_type": self.execution.score_type,
                "max_retries": self.execution.max_retries,
                "resume_max_rounds": self.execution.resume_max_rounds,
                "install_libreoffice": self.execution.install_libreoffice,
                "tokens": dict(self.execution.tokens),
                "timeout": self.execution.timeout,
                "sandbox": self.execution.sandbox,
                **({"agentic": self.execution.agentic} if self.execution.agentic is not None else {}),
                **({"metrics": self.execution.metrics} if self.execution.metrics is not None else {}),
            },
        }

    @staticmethod
    def _condition_to_dict(condition: ConditionConfig) -> Dict[str, Any]:
        """Convert condition to dictionary"""
        d = {
            "name": condition.name,
            "model": {
                "provider": condition.model.provider,
                "deployment": condition.model.deployment,
                "temperature": condition.model.temperature,
                "seed": condition.model.seed,
                "reasoning_effort": condition.model.reasoning_effort,
                "max_tokens": condition.model.max_tokens,
            },
            "prompt": {
                "system": condition.prompt.system,
                "prefix": condition.prompt.prefix,
                "suffix": condition.prompt.suffix,
            },
        }
        if condition.qa:
            d["qa"] = {
                "enabled": condition.qa.enabled,
                "max_retries": condition.qa.max_retries,
                "model": condition.qa.model,
                "min_score": condition.qa.min_score,
                "prompt": condition.qa.prompt,
            }
        if condition.preprocessors:
            d["preprocessors"] = condition.preprocessors
        return d

    def validate(self) -> List[str]:
        """Validate configuration

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Check required fields
        if not self.experiment_id:
            errors.append("experiment.id is required")
        else:
            try:
                validate_experiment_id(self.experiment_id)
            except ValueError as exc:
                errors.append(str(exc))
        if not self.name:
            errors.append("experiment.name is required")
        try:
            validate_hf_dataset_repo_id(self.data_filter.source)
        except ValueError as exc:
            errors.append(str(exc))

        # Check conditions
        if not self.condition_a.name:
            errors.append("condition_a.name is required")

        # Check model providers
        valid_providers = ["azure", "openai", "anthropic"]
        if self.condition_a.model.provider not in valid_providers:
            errors.append(f"condition_a.model.provider must be one of {valid_providers}")

        # Validate condition_b only if present (A/B test)
        if self.condition_b is not None:
            if not self.condition_b.name:
                errors.append("condition_b.name is required")
            if self.condition_b.model.provider not in valid_providers:
                errors.append(f"condition_b.model.provider must be one of {valid_providers}")

        # Validate execution mode (Phase 5-3)
        valid_modes = [
            "code_interpreter", "subprocess", "sandbox", "agentic_sandbox",
            "json_renderer",
        ]
        if self.execution.mode not in valid_modes:
            errors.append(f"execution.mode must be one of {valid_modes}")

        task_ids = self.data_filter.task_ids
        if task_ids is not None:
            if not isinstance(task_ids, list) or not task_ids or not all(
                isinstance(task_id, str) and task_id.strip() for task_id in task_ids
            ):
                errors.append("data.filter.task_ids must be a non-empty list of non-empty strings")
            elif len(task_ids) != len(set(task_ids)):
                errors.append("data.filter.task_ids must not contain duplicates")
            if self.data_filter.sample_size is not None:
                errors.append("data.filter.task_ids and sample_size are mutually exclusive")

        # Validate code_interpreter mode requires OpenAI/Azure
        if self.execution.mode == "code_interpreter":
            if self.condition_a.model.provider not in ["azure", "openai"]:
                errors.append("code_interpreter mode requires azure or openai provider for condition_a")
            if self.condition_b and self.condition_b.model.provider not in ["azure", "openai"]:
                errors.append("code_interpreter mode requires azure or openai provider for condition_b")

        if self.execution.mode == "agentic_sandbox":
            if self.condition_a.model.provider not in ["azure", "openai"]:
                errors.append("agentic_sandbox mode requires azure or openai provider for condition_a")
            if self.condition_b and self.condition_b.model.provider not in ["azure", "openai"]:
                errors.append("agentic_sandbox mode requires azure or openai provider for condition_b")

        hardened = (
            self.execution.mode == "agentic_sandbox"
            or (
                self.execution.mode == "sandbox"
                and isinstance(self.execution.sandbox, dict)
                and self.execution.sandbox.get("hardened_substrate") is True
            )
        )
        if hardened:
            if self.condition_b is not None:
                errors.append(
                    "reserved hardened experiments require exactly condition_a"
                )
            try:
                validate_agentic_experiment_identity(
                    self.experiment_id,
                    self.execution.mode,
                    (
                        self.execution.mode == "sandbox"
                        and isinstance(self.execution.sandbox, dict)
                        and self.execution.sandbox.get("hardened_substrate") is True
                    ),
                )
            except ValueError as exc:
                errors.append(str(exc))
            errors.extend(_validate_agentic_config(self.execution.agentic))
            try:
                validate_agentic_budget_for_experiment(
                    self.experiment_id,
                    (self.execution.agentic or {}).get("budget"),
                )
            except ValueError as exc:
                errors.append(str(exc))
            for label, condition in (
                ("condition_a", self.condition_a),
                ("condition_b", self.condition_b),
            ):
                if condition is None:
                    continue
                if condition.qa and condition.qa.enabled:
                    errors.append(
                        f"{label}.qa must be disabled for hardened execution"
                    )
                if condition.preprocessors:
                    errors.append(
                        f"{label}.preprocessors must be empty for hardened execution"
                    )
                if condition.prompt.prefix or condition.prompt.body:
                    errors.append(
                        f"{label}.prompt prefix/body are unsupported for "
                        "hardened paired execution"
                    )

        # Warning: portable score_type should use json_renderer
        if self.execution.score_type == "portable" and self.execution.mode != "json_renderer":
            # This is a warning, not an error - don't block execution
            pass

        return errors

    def __repr__(self) -> str:
        return f"ExperimentConfig(id='{self.experiment_id}', name='{self.name}')"


def _validate_agentic_config(value: Any) -> List[str]:
    if not isinstance(value, dict):
        return ["execution.agentic is required for hardened execution"]
    allowed = {
        "compute_transport", "image", "verifier_image", "memory_gb", "cpus",
        "limits", "budget", "pricing_table", "authorization",
        "seccomp_profile", "apparmor_profile",
    }
    errors = []
    unknown = sorted(set(value) - allowed)
    if unknown:
        errors.append(f"execution.agentic contains unknown fields: {unknown}")
    if value.get("compute_transport") != "remote":
        errors.append("execution.agentic.compute_transport must be remote")
    digest_pattern = re.compile(r"^.+@sha256:[0-9a-f]{64}$")
    for field_name in ("image", "verifier_image"):
        image = value.get(field_name)
        if not isinstance(image, str) or digest_pattern.fullmatch(image) is None:
            errors.append(
                f"execution.agentic.{field_name} must be pinned by sha256 digest"
            )
    limits = value.get("limits")
    if not isinstance(limits, dict):
        errors.append("execution.agentic.limits is required")
    else:
        allowed_limits = {
            "max_api_attempts", "max_model_iterations", "max_output_tokens",
            "max_input_tokens", "max_cumulative_output_tokens",
            "max_task_seconds", "max_cost_usd", "max_tool_calls",
            "max_run_python", "max_run_ffmpeg", "max_inspect_artifacts",
            "max_finalize", "max_identical_errors",
        }
        if set(limits) - allowed_limits:
            errors.append("execution.agentic.limits contains unknown fields")
    budget = value.get("budget")
    if not isinstance(budget, dict) or set(budget) != {
        "paired_run_id", "condition", "paired_run"
    }:
        errors.append("execution.agentic.budget fields are invalid")
    pricing = value.get("pricing_table")
    if (
        not isinstance(pricing, dict)
        or set(pricing) != {"sha256"}
        or not isinstance(pricing.get("sha256"), str)
        or re.fullmatch(r"[0-9a-f]{64}", pricing["sha256"]) is None
    ):
        errors.append("execution.agentic.pricing_table must contain sha256")
    authorization = value.get("authorization")
    if not isinstance(authorization, dict) or set(authorization) != {
        "api_version", "provider_classification", "endpoint_sha256"
    }:
        errors.append("execution.agentic.authorization fields are invalid")
    return errors
