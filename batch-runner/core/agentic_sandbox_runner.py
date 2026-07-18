"""Bounded Responses API loop for model-directed sandbox task solving."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

import yaml

from core.agentic_budget import (
    AgenticBudgetLedger,
    BudgetCaps,
    BudgetExceeded,
)
from core.agentic_tools import (
    AgenticComputeBackend,
    AgenticToolDispatcher,
    responses_tool_definitions,
)


DEFAULT_PROMPT = "agentic_sandbox_solver"
PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


@dataclass(frozen=True)
class AgenticLimits:
    max_api_attempts: int = 6
    max_model_iterations: int = 6
    max_output_tokens: int = 8192
    max_input_tokens: int = 300000
    max_cumulative_output_tokens: int = 32768
    max_task_seconds: int = 1200
    max_cost_usd: Decimal = Decimal("1.25")
    max_tool_calls: int = 8
    max_run_python: int = 4
    max_run_ffmpeg: int = 2
    max_inspect_artifacts: int = 4
    max_finalize: int = 2
    max_identical_errors: int = 2

    @classmethod
    def from_options(cls, options: Optional[Mapping[str, Any]]) -> "AgenticLimits":
        values = dict(options or {})
        known = {
            "max_api_attempts", "max_model_iterations", "max_output_tokens",
            "max_input_tokens", "max_cumulative_output_tokens",
            "max_task_seconds", "max_cost_usd", "max_tool_calls",
            "max_run_python", "max_run_ffmpeg", "max_inspect_artifacts",
            "max_finalize", "max_identical_errors",
        }
        unknown = set(values) - known
        if unknown:
            raise ValueError(f"unknown agentic limit(s): {sorted(unknown)}")
        defaults = cls()
        absolute_counts = {
            "max_api_attempts": 6,
            "max_model_iterations": 6,
            "max_output_tokens": 8192,
            "max_input_tokens": 300000,
            "max_cumulative_output_tokens": 32768,
            "max_task_seconds": 1200,
            "max_tool_calls": 8,
            "max_run_python": 4,
            "max_run_ffmpeg": 2,
            "max_inspect_artifacts": 4,
            "max_finalize": 2,
            "max_identical_errors": 2,
        }
        parsed: dict[str, Any] = {}
        for name, maximum in absolute_counts.items():
            raw = values.get(name, getattr(defaults, name))
            if isinstance(raw, bool):
                raise ValueError(f"{name} must be a positive integer")
            try:
                value = int(raw)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{name} must be a positive integer") from exc
            if value <= 0 or value > maximum:
                raise ValueError(f"{name} must be in [1, {maximum}]")
            parsed[name] = value
        maximum_cost = Decimal("1.25")
        cost = Decimal(str(values.get("max_cost_usd", defaults.max_cost_usd)))
        if not cost.is_finite() or cost <= 0 or cost > maximum_cost:
            raise ValueError(f"max_cost_usd must be in (0, {maximum_cost}]")
        parsed["max_cost_usd"] = cost
        return cls(**parsed)


@dataclass(frozen=True)
class AgenticPricing:
    input_per_million: Decimal
    output_per_million: Decimal
    cached_input_per_million: Decimal
    price_table_sha256: str = "nonpaid-unpinned"

    @classmethod
    def from_options(cls, options: Optional[Mapping[str, Any]]) -> "AgenticPricing":
        if not isinstance(options, Mapping):
            raise ValueError("agentic pricing is required")
        result = cls(
            input_per_million=Decimal(str(options.get("input_per_million"))),
            output_per_million=Decimal(str(options.get("output_per_million"))),
            cached_input_per_million=Decimal(str(
                options.get("cached_input_per_million", options.get("input_per_million"))
            )),
            price_table_sha256=str(
                options.get("price_table_sha256", "nonpaid-unpinned")
            ),
        )
        for value in (
            result.input_per_million,
            result.output_per_million,
            result.cached_input_per_million,
        ):
            if not value.is_finite() or value < 0:
                raise ValueError("agentic prices must be finite non-negative decimals")
        if not result.price_table_sha256:
            raise ValueError("agentic price table identity is required")
        return result

    def worst_case(self, input_tokens: int, output_tokens: int) -> Decimal:
        million = Decimal(1000000)
        return (
            Decimal(input_tokens) * self.input_per_million
            + Decimal(output_tokens) * self.output_per_million
        ) / million

    def actual(self, input_tokens: int, output_tokens: int, cached_tokens: int) -> Decimal:
        uncached = max(0, input_tokens - cached_tokens)
        million = Decimal(1000000)
        return (
            Decimal(uncached) * self.input_per_million
            + Decimal(cached_tokens) * self.cached_input_per_million
            + Decimal(output_tokens) * self.output_per_million
        ) / million


@dataclass(frozen=True)
class AgenticAggregateBudget:
    paired_run_id: str
    condition: BudgetCaps
    paired_run: BudgetCaps

    @classmethod
    def from_options(
        cls, options: Optional[Mapping[str, Any]]
    ) -> Optional["AgenticAggregateBudget"]:
        if options is None:
            return None
        if not isinstance(options, Mapping):
            raise ValueError("agentic aggregate budget must be an object")
        if set(options) != {"paired_run_id", "condition", "paired_run"}:
            raise ValueError("agentic aggregate budget fields are invalid")
        paired_run_id = options.get("paired_run_id")
        if not isinstance(paired_run_id, str) or not paired_run_id:
            raise ValueError("paired_run_id is required")
        condition = _aggregate_caps(options.get("condition"), "condition", Decimal("25"))
        paired = _aggregate_caps(options.get("paired_run"), "paired_run", Decimal("50"))
        if (
            condition.attempts > paired.attempts
            or condition.input_tokens > paired.input_tokens
            or condition.output_tokens > paired.output_tokens
            or condition.cost_usd > paired.cost_usd
        ):
            raise ValueError("condition budget cannot exceed paired-run budget")
        return cls(paired_run_id, condition, paired)

class AgenticSandboxRunner:
    """Run one task through a strictly bounded model-directed tool loop."""

    DEFAULT_PROMPT = DEFAULT_PROMPT

    def __init__(
        self,
        llm_client: Any = None,
        *,
        client_factory: Optional[Callable[[], Any]] = None,
        non_paid_test_mode: bool = False,
        backend_factory: Callable[..., AgenticComputeBackend],
        budget_ledger: AgenticBudgetLedger,
        authorize_request: Callable[[str, str, Mapping[str, Any]], None],
        prompt_name: str = DEFAULT_PROMPT,
        reasoning_effort: Optional[str] = None,
        provider: str = "nonpaid-test",
        api_version: str = "nonpaid-test",
        endpoint_sha256: str = "nonpaid-test",
        approval_scope_sha256: str = "nonpaid-test",
        official_scope_registry_sha256: str = "nonpaid-test",
        limits: Optional[Mapping[str, Any]] = None,
        pricing: Optional[Mapping[str, Any]] = None,
        aggregate_budget: Optional[Mapping[str, Any]] = None,
    ):
        if not callable(backend_factory):
            raise ValueError("backend_factory is required")
        if not callable(authorize_request):
            raise ValueError("authorize_request is required")
        if llm_client is not None and not non_paid_test_mode:
            raise ValueError("direct agentic clients are allowed only in non-paid tests")
        if llm_client is None and not callable(client_factory):
            raise ValueError("agentic_sandbox requires a deferred client_factory")
        if llm_client is not None:
            self._validate_client(llm_client)
        self.client = llm_client
        self.client_factory = client_factory
        self.backend_factory = backend_factory
        self.ledger = budget_ledger
        self.authorize_request = authorize_request
        self.reasoning_effort = reasoning_effort or "medium"
        self.provider = provider
        self.api_version = api_version
        self.endpoint_sha256 = endpoint_sha256
        self.approval_scope_sha256 = approval_scope_sha256
        self.official_scope_registry_sha256 = official_scope_registry_sha256
        self.limits = AgenticLimits.from_options(limits)
        self.pricing = AgenticPricing.from_options(pricing)
        self.aggregate_budget = AgenticAggregateBudget.from_options(
            aggregate_budget
        )
        self.instructions = self._load_instructions(prompt_name)

    def run(
        self,
        task_prompt: str,
        model: str,
        reference_files: Optional[list] = None,
        occupation: str = "professional",
        experiment_prompt: Optional[dict] = None,
        perception_text: Optional[str] = None,
        *,
        run_id: str = "local-nonpaid",
        condition_name: str = "condition_a",
        task_id: str = "unknown-task",
    ) -> dict:
        started = time.monotonic()
        scope = self._scope(run_id, condition_name, task_id)
        backend = self.backend_factory(
            task_prompt=task_prompt,
            reference_files=list(reference_files or []),
            occupation=occupation,
            run_id=run_id,
            condition_name=condition_name,
            task_id=task_id,
        )
        dispatcher = AgenticToolDispatcher(
            backend,
            max_total_calls=self.limits.max_tool_calls,
            per_tool_limits={
                "inspect_workspace": 4,
                "inspect_environment": 2,
                "run_python": self.limits.max_run_python,
                "run_ffmpeg": self.limits.max_run_ffmpeg,
                "inspect_artifacts": self.limits.max_inspect_artifacts,
                "finalize": self.limits.max_finalize,
            },
        )
        metrics = self._new_metrics()
        first_model_dispatch: Optional[float] = None
        existing_usage = self.ledger.usage(scope)
        metrics.update({
            "model_api_calls": existing_usage.attempts,
            "input_tokens": existing_usage.input_tokens,
            "output_tokens": existing_usage.output_tokens,
            "conservative_cost_usd": str(existing_usage.cost_usd),
        })
        error_counts: dict[str, int] = {}
        terminal_error = "unknown_error"
        try:
            startup = dict(backend.start(self.limits.max_task_seconds))
            if startup.get("ok") is not True:
                terminal_error = str(startup.get("error_type") or "compute_start_failed")
                return self._failure(backend, metrics, terminal_error, started)
            substrate_manifest = (startup.get("data") or {}).get(
                "substrate_manifest"
            )
            if not isinstance(substrate_manifest, dict):
                return self._failure(
                    backend, metrics, "substrate_manifest_missing", started
                )

            messages: list[dict] = [{
                "role": "user",
                "content": self._initial_content(
                    task_prompt, occupation, startup, experiment_prompt, perception_text
                ),
            }]
            finalize_correction_used = False

            while metrics["model_iterations"] < self.limits.max_model_iterations:
                if time.monotonic() - started >= self.limits.max_task_seconds:
                    terminal_error = "task_wall_time_exhausted"
                    break
                metrics["model_iterations"] += 1
                request_id = self._request_id(scope, metrics["model_iterations"], messages)
                request_payload = {
                    "model": model,
                    "instructions": self.instructions,
                    "input": list(messages),
                    "tools": responses_tool_definitions(),
                    "reasoning": {"effort": self.reasoning_effort},
                    "max_output_tokens": self.limits.max_output_tokens,
                    "parallel_tool_calls": False,
                    "timeout": max(
                        1.0,
                        min(
                            480.0,
                            self.limits.max_task_seconds
                            - (time.monotonic() - started),
                        ),
                    ),
                }
                estimated_input = len(
                    json.dumps(
                        request_payload,
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8")
                )
                reserved_cost = self.pricing.worst_case(
                    estimated_input, self.limits.max_output_tokens
                )
                try:
                    budget_scopes = self._budget_scopes(
                        scope, condition_name
                    )
                    usage_by_scope = self.ledger.reserve_many(
                        scopes=budget_scopes,
                        request_id=request_id,
                        input_tokens=estimated_input,
                        output_tokens=self.limits.max_output_tokens,
                        cost_usd=reserved_cost,
                    )
                    metrics["conservative_cost_usd"] = str(
                        usage_by_scope[scope].cost_usd
                    )
                    self.authorize_request(
                        scope,
                        request_id,
                        {
                            "runtime_preflight_passed": True,
                            "input_merkle_root": (startup.get("data") or {}).get(
                                "input_merkle_root"
                            ),
                            "provider_classification": (startup.get("data") or {}).get(
                                "provider_classification"
                            ),
                            "model": model,
                            "provider": self.provider,
                            "api_version": self.api_version,
                            "endpoint_sha256": self.endpoint_sha256,
                            "approval_scope_sha256": self.approval_scope_sha256,
                            "official_scope_registry_sha256": (
                                self.official_scope_registry_sha256
                            ),
                            "run_id": run_id,
                            "condition": condition_name,
                            "task_id": task_id,
                            "caps": self._authorization_caps(),
                            "price_table_sha256": self.pricing.price_table_sha256,
                            "substrate_manifest_sha256": substrate_manifest.get(
                                "sha256"
                            ),
                            "official_scope_excluded": True,
                        },
                    )
                    if self.client is None:
                        assert self.client_factory is not None
                        client = self.client_factory()
                        self._validate_client(client)
                        self.client = client
                except BudgetExceeded as exc:
                    terminal_error = str(exc)
                    break
                except Exception:
                    terminal_error = "authorization_or_reservation_failed"
                    break

                metrics["model_api_calls"] += 1
                request_started = time.monotonic()
                if first_model_dispatch is None:
                    first_model_dispatch = request_started
                try:
                    assert self.client is not None
                    response = self.client.responses.create(**request_payload)
                except Exception:
                    metrics["model_time_ms"] += _elapsed_ms(request_started)
                    terminal_error = "model_api_error"
                    break
                metrics["model_time_ms"] += _elapsed_ms(request_started)

                extracted = self._usage(response)
                if extracted is None:
                    terminal_error = "usage_incomplete"
                    break
                input_tokens, output_tokens, cached_tokens = extracted
                actual_cost = self.pricing.actual(
                    input_tokens, output_tokens, cached_tokens
                )
                try:
                    reconciled_by_scope = self.ledger.reconcile_many(
                        scopes=budget_scopes,
                        request_id=request_id,
                        actual_input_tokens=input_tokens,
                        actual_output_tokens=output_tokens,
                        actual_cost_usd=actual_cost,
                    )
                except Exception:
                    terminal_error = "usage_reconciliation_failed"
                    break
                metrics["input_tokens"] += input_tokens
                metrics["output_tokens"] += output_tokens
                metrics["cached_tokens"] += cached_tokens
                metrics["conservative_cost_usd"] = str(
                    reconciled_by_scope[scope].cost_usd
                )

                output_items = list(_get(response, "output", []) or [])
                function_calls = [
                    item for item in output_items if _item_type(item) == "function_call"
                ]
                if function_calls:
                    call_ids = [str(_get(call, "call_id", "")) for call in function_calls]
                    if (
                        any(not call_id for call_id in call_ids)
                        or len(set(call_ids)) != len(call_ids)
                    ):
                        terminal_error = "invalid_function_call_id"
                        metrics["tool_errors"] += 1
                        break
                    prepared_calls, preflight_error = dispatcher.prepare_batch([
                        (
                            str(_get(call, "name", "")),
                            _get(call, "arguments", "{}"),
                        )
                        for call in function_calls
                    ])
                    if preflight_error is not None:
                        terminal_error = preflight_error
                        metrics["tool_errors"] += 1
                        break
                    messages.extend(_serialize_output_item(item) for item in output_items)
                    for call, prepared_call in zip(function_calls, prepared_calls):
                        tool_started = time.monotonic()
                        name = prepared_call.name
                        remaining_seconds = (
                            self.limits.max_task_seconds
                            - (time.monotonic() - started)
                        )
                        dispatch = dispatcher.dispatch_prepared(
                            prepared_call,
                            remaining_seconds=remaining_seconds,
                        )
                        duration = _elapsed_ms(tool_started)
                        metrics["tool_time_ms"] += duration
                        metrics["tool_calls"] += 1
                        metrics["tool_calls_by_name"][name] = (
                            metrics["tool_calls_by_name"].get(name, 0) + 1
                        )
                        if name == "finalize":
                            metrics["finalize_attempts"] += 1
                        if (
                            name in {"inspect_artifacts", "finalize"}
                            and dispatch.result.get("ok") is True
                            and first_model_dispatch is not None
                            and metrics["time_to_valid_artifact_ms"] is None
                        ):
                            metrics["time_to_valid_artifact_ms"] = _elapsed_ms(
                                first_model_dispatch
                            )
                        if dispatch.result.get("ok") is not True:
                            metrics["tool_errors"] += 1
                            category = str(
                                dispatch.result.get("error_type") or "unknown_tool_error"
                            )
                            error_counts[category] = error_counts.get(category, 0) + 1
                            if category == "capability_missing":
                                metrics["capability_misses"] += 1
                            if error_counts[category] > self.limits.max_identical_errors:
                                terminal_error = "repeated_error_limit"
                                return self._failure(
                                    backend, metrics, terminal_error, started
                                )
                            if category in {
                                "compute_backend_error",
                                "invalid_compute_result",
                                "tool_result_too_large",
                                "finalize_result_missing",
                                "task_wall_time_exhausted",
                            }:
                                terminal_error = category
                                return self._failure(
                                    backend, metrics, terminal_error, started
                                )
                        messages.append(_function_output(call, dispatch.result))
                        if dispatch.finalized:
                            result = dict(dispatch.terminal_result or {})
                            if result.get("success") is not True:
                                terminal_error = "invalid_finalize_result"
                                return self._failure(backend, metrics, terminal_error, started)
                            metrics["terminal_error_category"] = None
                            metrics["recovered_after_tool_error"] = (
                                metrics["tool_errors"] > 0
                            )
                            metrics["task_wall_time_ms"] = _elapsed_ms(started)
                            result["agentic_metrics"] = metrics
                            result["substrate_manifest"] = substrate_manifest
                            return result
                    continue

                messages.extend(_serialize_output_item(item) for item in output_items)
                if not finalize_correction_used:
                    messages.append({
                        "role": "user",
                        "content": (
                            "A task is complete only after a successful finalize tool call. "
                            "Inspect or repair artifacts, then call finalize."
                        ),
                    })
                    finalize_correction_used = True
                    metrics["finalize_required_corrections"] = 1
                    continue
                terminal_error = "finalize_not_called"
                break

            else:
                terminal_error = "model_iteration_cap"
            return self._failure(backend, metrics, terminal_error, started)
        except Exception:
            return self._failure(backend, metrics, "runner_internal_error", started)
        finally:
            try:
                backend.close()
            except Exception:
                pass

    @staticmethod
    def _validate_client(client: Any) -> None:
        responses = getattr(client, "responses", None)
        if not callable(getattr(responses, "create", None)):
            raise ValueError("agentic_sandbox requires a Responses API client")

    @staticmethod
    def _scope(run_id: str, condition_name: str, task_id: str) -> str:
        values = (run_id, condition_name, task_id)
        if any(not isinstance(value, str) or not value for value in values):
            raise ValueError("run, condition, and task identity are required")
        return json.dumps(values, separators=(",", ":"))

    def _budget_scopes(
        self, task_scope: str, condition_name: str
    ) -> dict[str, BudgetCaps]:
        scopes = {
            task_scope: BudgetCaps(
                attempts=self.limits.max_api_attempts,
                input_tokens=self.limits.max_input_tokens,
                output_tokens=self.limits.max_cumulative_output_tokens,
                cost_usd=self.limits.max_cost_usd,
            )
        }
        if self.aggregate_budget is not None:
            paired_id = self.aggregate_budget.paired_run_id
            scopes[json.dumps(
                ["condition", paired_id, condition_name], separators=(",", ":")
            )] = self.aggregate_budget.condition
            scopes[json.dumps(
                ["paired_run", paired_id], separators=(",", ":")
            )] = self.aggregate_budget.paired_run
        return scopes

    def _authorization_caps(self) -> dict:
        caps: dict[str, Any] = {
            "task": {
                "api_attempts": self.limits.max_api_attempts,
                "model_iterations": self.limits.max_model_iterations,
                "input_tokens": self.limits.max_input_tokens,
                "output_tokens": self.limits.max_cumulative_output_tokens,
                "max_output_tokens_per_response": self.limits.max_output_tokens,
                "cost_usd": str(self.limits.max_cost_usd),
                "wall_seconds": self.limits.max_task_seconds,
            }
        }
        if self.aggregate_budget is not None:
            caps["condition"] = _caps_dict(self.aggregate_budget.condition)
            caps["paired_run"] = _caps_dict(self.aggregate_budget.paired_run)
            caps["paired_run_id"] = self.aggregate_budget.paired_run_id
        return caps

    @staticmethod
    def _request_id(scope: str, iteration: int, messages: list[dict]) -> str:
        return hashlib.sha256(
            json.dumps(
                [scope, iteration, messages], sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _initial_content(
        task_prompt: str,
        occupation: str,
        startup: Mapping[str, Any],
        experiment_prompt: Optional[dict],
        perception_text: Optional[str],
    ) -> str:
        payload = {
            "task": task_prompt,
            "occupation": occupation,
            "workspace": startup.get("data", {}),
            "prompt_suffix": (experiment_prompt or {}).get("suffix"),
            "perception": perception_text,
        }
        return json.dumps(payload, ensure_ascii=True, separators=(",", ":"))

    @staticmethod
    def _usage(response: Any) -> Optional[tuple[int, int, int]]:
        usage = _get(response, "usage")
        if usage is None:
            return None
        raw_input = _get(usage, "input_tokens")
        raw_output = _get(usage, "output_tokens")
        if not _valid_count(raw_input) or not _valid_count(raw_output):
            return None
        details = _get(usage, "input_tokens_details")
        raw_cached = _get(details, "cached_tokens", 0) if details is not None else 0
        if not _valid_count(raw_cached) or int(raw_cached) > int(raw_input):
            return None
        return int(raw_input), int(raw_output), int(raw_cached)

    @staticmethod
    def _new_metrics() -> dict:
        return {
            "schema_version": "1.0",
            "ledger_cumulative": True,
            "model_api_calls": 0,
            "model_iterations": 0,
            "tool_calls": 0,
            "tool_errors": 0,
            "tool_calls_by_name": {},
            "model_time_ms": 0.0,
            "tool_time_ms": 0.0,
            "task_wall_time_ms": None,
            "time_to_valid_artifact_ms": None,
            "finalize_required_corrections": 0,
            "finalize_attempts": 0,
            "capability_misses": 0,
            "recovered_after_tool_error": False,
            "input_tokens": 0,
            "output_tokens": 0,
            "cached_tokens": 0,
            "conservative_cost_usd": "0",
            "usage_complete": True,
            "terminal_error_category": None,
        }

    @staticmethod
    def _failure(
        backend: AgenticComputeBackend,
        metrics: dict,
        category: str,
        started: float,
    ) -> dict:
        metrics["terminal_error_category"] = category
        metrics["task_wall_time_ms"] = _elapsed_ms(started)
        if category in {
            "usage_incomplete", "model_api_error", "usage_reconciliation_failed",
            "authorization_or_reservation_failed",
        }:
            metrics["usage_complete"] = False
        best = backend.best_result()
        result = dict(best or {})
        result.update({
            "success": False,
            "text": result.get("text", ""),
            "files": result.get("files", []),
            "error": category,
            "agentic_metrics": metrics,
        })
        return result

    @staticmethod
    def _load_instructions(prompt_name: str) -> str:
        path = PROMPTS_DIR / f"{prompt_name}.yaml"
        if not path.is_file():
            raise FileNotFoundError(f"Agentic prompt not found: {path}")
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        instructions = data.get("instructions") if isinstance(data, dict) else None
        if not isinstance(instructions, str) or not instructions.strip():
            raise ValueError("Agentic prompt must contain non-empty instructions")
        return instructions.strip()


def _get(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _item_type(item: Any) -> str:
    return str(_get(item, "type", ""))


def _serialize_output_item(item: Any) -> dict:
    if isinstance(item, Mapping):
        return dict(item)
    dump = getattr(item, "model_dump", None)
    if callable(dump):
        try:
            result = dump(mode="json", exclude_none=True)
        except TypeError:
            result = dump()
        if isinstance(result, Mapping):
            return dict(result)
    return {
        name: _get(item, name)
        for name in (
            "type", "id", "status", "role", "content", "summary",
            "call_id", "name", "arguments",
        )
        if _get(item, name) is not None
    }


def _function_output(call: Any, result: Mapping[str, Any]) -> dict:
    return {
        "type": "function_call_output",
        "call_id": str(_get(call, "call_id", "")),
        "output": json.dumps(
            dict(result), sort_keys=True, separators=(",", ":"), allow_nan=False
        ),
    }


def _valid_count(value: Any) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and value >= 0
    )


def _elapsed_ms(started: float) -> float:
    return round(max(0.0, (time.monotonic() - started) * 1000.0), 3)


def _aggregate_caps(
    value: Any, label: str, maximum_cost: Decimal
) -> BudgetCaps:
    if not isinstance(value, Mapping) or set(value) != {
        "attempts", "input_tokens", "output_tokens", "cost_usd"
    }:
        raise ValueError(f"{label} budget fields are invalid")
    absolute_counts = {
        "condition": {
            "attempts": 120,
            "input_tokens": 6_000_000,
            "output_tokens": 655_360,
        },
        "paired_run": {
            "attempts": 240,
            "input_tokens": 12_000_000,
            "output_tokens": 1_310_720,
        },
    }[label]
    counts = {}
    for field_name in ("attempts", "input_tokens", "output_tokens"):
        raw = value.get(field_name)
        if isinstance(raw, bool) or not isinstance(raw, int) or raw <= 0:
            raise ValueError(f"{label}.{field_name} must be a positive integer")
        if raw > absolute_counts[field_name]:
            raise ValueError(f"{label}.{field_name} exceeds its absolute maximum")
        counts[field_name] = raw
    cost = Decimal(str(value.get("cost_usd")))
    if not cost.is_finite() or cost <= 0 or cost > maximum_cost:
        raise ValueError(f"{label}.cost_usd must be in (0, {maximum_cost}]")
    return BudgetCaps(cost_usd=cost, **counts)


def _caps_dict(caps: BudgetCaps) -> dict:
    return {
        "attempts": caps.attempts,
        "input_tokens": caps.input_tokens,
        "output_tokens": caps.output_tokens,
        "cost_usd": str(caps.cost_usd),
    }