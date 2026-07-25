"""Current sandbox solver semantics on the common hardened compute substrate."""

from __future__ import annotations

import hashlib
import json
import time
from contextlib import nullcontext
from types import SimpleNamespace
from typing import Any, Callable, Mapping, Optional

from core.agentic_authorization import task_request_sha256
from core.agentic_budget import AgenticBudgetLedger, BudgetCaps
from core.agentic_sandbox_runner import (
    AgenticAggregateBudget,
    AgenticLimits,
    AgenticPricing,
    _elapsed_ms,
)
from core.agentic_tools import AgenticComputeBackend
from core.sandbox_runner import SandboxRunner


class _BudgetedChatCompletions:
    def __init__(self, owner: "HardenedSandboxRunner"):
        self.owner = owner

    def create(self, **kwargs):
        return self.owner._create_chat_completion(kwargs)


class _BudgetedChatClient:
    def __init__(self, owner: "HardenedSandboxRunner"):
        self.chat = SimpleNamespace(completions=_BudgetedChatCompletions(owner))


class HardenedSandboxRunner(SandboxRunner):
    """One initial generation plus at most one full hardened regeneration."""

    def __init__(
        self,
        *,
        client_factory: Callable[[], Any],
        backend_factory: Callable[..., AgenticComputeBackend],
        budget_ledger: AgenticBudgetLedger,
        authorize_request: Callable[[str, str, Mapping[str, Any]], None],
        run_id: str,
        condition_name: str,
        model_name: str,
        provider: str = "nonpaid-test",
        api_version: str = "nonpaid-test",
        endpoint_sha256: str = "nonpaid-test",
        approval_scope_sha256: str = "nonpaid-test",
        official_scope_registry_sha256: str = "nonpaid-test",
        limits: Mapping[str, Any],
        pricing: Mapping[str, Any],
        aggregate_budget: Mapping[str, Any],
        **sandbox_options: Any,
    ):
        if not all((run_id, condition_name, model_name)):
            raise ValueError("hardened baseline run identity is required")
        if not callable(client_factory) or not callable(backend_factory):
            raise ValueError("hardened baseline factories are required")
        if not callable(authorize_request):
            raise ValueError("hardened baseline authorization is required")
        self.client_factory = client_factory
        self.backend_factory = backend_factory
        self.budget_ledger = budget_ledger
        self.authorize_request = authorize_request
        self.run_id = run_id
        self.condition_name = condition_name
        self.model_name = model_name
        self.provider = provider
        self.api_version = api_version
        self.endpoint_sha256 = endpoint_sha256
        self.approval_scope_sha256 = approval_scope_sha256
        self.official_scope_registry_sha256 = official_scope_registry_sha256
        self.agentic_limits = AgenticLimits.from_options(limits)
        self.agentic_pricing = AgenticPricing.from_options(pricing)
        aggregate = AgenticAggregateBudget.from_options(aggregate_budget)
        if aggregate is None:
            raise ValueError("hardened baseline aggregate budget is required")
        self.aggregate_budget = aggregate
        self._provider_client = None
        self._closed = False
        self._backend: Optional[AgenticComputeBackend] = None
        self._startup: Optional[dict] = None
        self._task_id = ""
        self._task_request_sha256 = ""
        self._request_index = 0
        self._run_started = 0.0
        self._first_model_dispatch: Optional[float] = None
        self._budget_metrics = self._new_budget_metrics()
        proxy = _BudgetedChatClient(self)
        repair = {"enabled": True, "max_attempts": 1}
        repair.update(sandbox_options.pop("repair", {}) or {})
        if repair != {"enabled": True, "max_attempts": 1}:
            raise ValueError(
                "paired hardened baseline fixes repair.enabled=true and max_attempts=1"
            )
        super().__init__(
            proxy,
            repair=repair,
            use_docker="always",
            image=sandbox_options.pop("image", None),
            **sandbox_options,
        )

    def _release_provider_client(self) -> Optional[str]:
        client = self._provider_client
        self._provider_client = None
        if client is None:
            return None
        close = getattr(client, "close", None)
        if not callable(close):
            return None
        try:
            close()
        except BaseException as exc:
            return f"provider_cleanup_failed:{type(exc).__name__}"
        return None

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        cleanup_error = self._release_provider_client()
        if cleanup_error is not None:
            raise RuntimeError(cleanup_error) from None

    def run(
        self,
        task_prompt: str,
        model: str,
        reference_files: Optional[list] = None,
        occupation: str = "professional",
        experiment_prompt: Optional[dict] = None,
        perception_text: Optional[str] = None,
        *,
        run_id: Optional[str] = None,
        condition_name: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> dict:
        if self._closed:
            return self._terminal_failure("hardened_runner_closed")
        stale_cleanup_error = self._release_provider_client()
        if stale_cleanup_error is not None:
            return self._terminal_failure(stale_cleanup_error)
        if model != self.model_name:
            return self._terminal_failure("baseline_model_identity_mismatch")
        if run_id != self.run_id or condition_name != self.condition_name or not task_id:
            return self._terminal_failure("baseline_run_identity_mismatch")
        backend = self.backend_factory(
            task_prompt=task_prompt,
            reference_files=list(reference_files or []),
            occupation=occupation,
            run_id=run_id,
            condition_name=condition_name,
            task_id=task_id,
        )
        self._backend = backend
        self._task_id = task_id
        self._task_request_sha256 = task_request_sha256(
            task_prompt=task_prompt,
            occupation=occupation,
            experiment_prompt=experiment_prompt,
            perception_text=perception_text,
        )
        self._request_index = 0
        self._run_started = time.monotonic()
        self._first_model_dispatch = None
        self._budget_metrics = self._new_budget_metrics()
        task_scope = json.dumps(
            [self.run_id, self.condition_name, task_id], separators=(",", ":")
        )
        existing_usage = self.budget_ledger.usage(task_scope)
        self._budget_metrics.update({
            "model_api_calls": existing_usage.attempts,
            "input_tokens": existing_usage.input_tokens,
            "output_tokens": existing_usage.output_tokens,
            "conservative_cost_usd": str(existing_usage.cost_usd),
        })
        outcome: Optional[dict] = None

        def finish(result: Mapping[str, Any]) -> dict:
            nonlocal outcome
            outcome = dict(result)
            return outcome

        try:
            startup = dict(backend.start(self.agentic_limits.max_task_seconds))
            if startup.get("ok") is not True:
                return finish(self._terminal_failure(
                    str(startup.get("error_type") or "compute_start_failed")
                ))
            data = startup.get("data")
            if not isinstance(data, dict) or not isinstance(
                data.get("substrate_manifest"), dict
            ):
                return finish(self._terminal_failure(
                    "substrate_manifest_missing"
                ))
            self._startup = startup
            result = super().run(
                task_prompt=task_prompt,
                model=model,
                reference_files=reference_files,
                occupation=occupation,
                experiment_prompt=experiment_prompt,
                perception_text=perception_text,
            )
            result["substrate_manifest"] = data["substrate_manifest"]
            result["budget_metrics"] = dict(self._budget_metrics)
            return finish(result)
        except Exception:
            failure = self._terminal_failure("runner_internal_error")
            self._budget_metrics["usage_complete"] = False
            failure["budget_metrics"] = dict(self._budget_metrics)
            return finish(failure)
        finally:
            try:
                backend.close()
            except BaseException:
                if outcome is None:
                    outcome = self._terminal_failure("compute_cleanup_failed")
                prior_error = outcome.get("error")
                candidate = None
                if not outcome.get("files"):
                    try:
                        candidate = backend.best_result()
                    except Exception:
                        candidate = None
                if (
                    isinstance(candidate, Mapping)
                    and candidate.get("files")
                    and not outcome.get("files")
                ):
                    outcome["files"] = list(candidate["files"])
                    outcome["text"] = outcome.get("text") or candidate.get(
                        "text", ""
                    )
                outcome["success"] = False
                outcome["prior_error"] = prior_error
                outcome["error"] = "compute_cleanup_failed"
                self._budget_metrics["usage_complete"] = False
                outcome["budget_metrics"] = dict(self._budget_metrics)
            provider_cleanup_error = self._release_provider_client()
            if provider_cleanup_error is not None:
                if outcome is None:
                    outcome = self._terminal_failure(provider_cleanup_error)
                else:
                    prior_error = outcome.get("error")
                    outcome["success"] = False
                    outcome["prior_error"] = prior_error
                    outcome["error"] = provider_cleanup_error
                self._budget_metrics["usage_complete"] = False
                outcome["budget_metrics"] = dict(self._budget_metrics)
            self._backend = None
            self._startup = None
            self._task_id = ""
            self._task_request_sha256 = ""

    def _execute(self, code, reference_files, manifest):
        backend = self._backend
        if backend is None:
            return "docker", self._execution_failure("compute_unavailable")
        remaining = self.agentic_limits.max_task_seconds - (
            time.monotonic() - self._run_started
        )
        if remaining <= 0:
            return "docker", self._execution_failure(
                "baseline_task_wall_time_exhausted"
            )
        reset = dict(backend.reset_work(remaining))
        if reset.get("ok") is not True:
            return "docker", self._execution_failure(
                str(reset.get("error_type") or "workspace_reset_failed")
            )
        remaining = self.agentic_limits.max_task_seconds - (
            time.monotonic() - self._run_started
        )
        if remaining <= 0:
            return "docker", self._execution_failure(
                "baseline_task_wall_time_exhausted"
            )
        executed = dict(backend.run_python(
            code, min(float(self.timeout), remaining)
        ))
        stderr = str((executed.get("data") or {}).get("stderr_tail") or "")
        if executed.get("ok") is not True:
            compile_failed = stderr.startswith("compile_failed:")
            result = self._execution_failure(
                str(executed.get("error_type") or "python_execution_failed")
            )
            result["text"] = str((executed.get("data") or {}).get("stdout_tail") or "")
            result["error"] = stderr or result["error"]
            result["preflight"] = {
                "ok": not compile_failed,
                "stage": "compile" if compile_failed else "runtime",
                "error_type": "SyntaxError" if compile_failed else "RuntimeError",
                "line": None,
                "offset": None,
                "target_python": "3.11",
            }
            return "docker", result

        remaining = self.agentic_limits.max_task_seconds - (
            time.monotonic() - self._run_started
        )
        if remaining <= 0:
            return "docker", self._execution_failure(
                "baseline_task_wall_time_exhausted"
            )
        inspection = dict(backend.inspect_artifacts(remaining))
        data = inspection.get("data") if isinstance(inspection.get("data"), dict) else {}
        result = {
            "success": False,
            "text": str((executed.get("data") or {}).get("stdout_tail") or ""),
            "files": [],
            "preflight": {
                "ok": True,
                "stage": "compile",
                "error_type": None,
                "line": None,
                "offset": None,
                "target_python": "3.11",
            },
            "_hardened_verification": inspection,
        }
        if inspection.get("ok") is not True:
            result["error_category"] = "artifact_verification_failed"
            result["error"] = str(
                inspection.get("error_type") or "artifact_verification_failed"
            )
            return "docker", result
        candidate = backend.best_result()

        def preserve_candidate(failure: dict) -> dict:
            if (
                isinstance(candidate, Mapping)
                and candidate.get("files")
            ):
                failure["files"] = list(candidate["files"])
                failure["text"] = failure.get("text") or candidate.get(
                    "text", ""
                )
                failure["deliverable_text"] = candidate.get(
                    "deliverable_text", ""
                )
            return failure
        if (
            self._first_model_dispatch is not None
            and self._budget_metrics["time_to_valid_artifact_ms"] is None
        ):
            self._budget_metrics["time_to_valid_artifact_ms"] = _elapsed_ms(
                self._first_model_dispatch
            )
        deliverables = [
            item.get("path")
            for item in data.get("artifacts", [])
            if isinstance(item, dict) and isinstance(item.get("path"), str)
        ]
        remaining = self.agentic_limits.max_task_seconds - (
            time.monotonic() - self._run_started
        )
        if remaining <= 0:
            return "docker", preserve_candidate(self._execution_failure(
                "baseline_task_wall_time_exhausted"
            ))
        try:
            finalized = dict(backend.finalize(
                deliverables, "Hardened sandbox deliverables", remaining
            ))
        except Exception:
            finalized = {
                "ok": False,
                "error_type": "artifact_finalization_failed",
            }
        terminal = backend.best_result()
        if finalized.get("ok") is not True or terminal is None:
            result["error_category"] = "artifact_finalization_failed"
            result["error"] = str(
                finalized.get("error_type") or "artifact_finalization_failed"
            )
            return "docker", preserve_candidate(result)
        result.update(dict(terminal))
        result["preflight"] = {
            "ok": True,
            "stage": "compile",
            "error_type": None,
            "line": None,
            "offset": None,
            "target_python": "3.11",
        }
        result["_hardened_verification"] = inspection
        return "docker", result

    def _stage_reference_files(self, reference_files):
        return nullcontext(list(reference_files))

    def _host_reference_access(self) -> bool:
        return False

    def _analyze_output(
        self,
        result,
        ref_files,
        contract,
        task_prompt,
        executor_used,
        dep_manifest=None,
    ):
        verification = result.get("_hardened_verification") or {}
        data = verification.get("data") if isinstance(verification, dict) else {}
        data = data if isinstance(data, dict) else {}
        artifacts = [
            item for item in data.get("artifacts", []) if isinstance(item, dict)
        ]
        blocking = []
        if verification.get("ok") is not True:
            blocking.append(
                "hardened_verifier_failed:"
                + str(verification.get("error_type") or "unknown")
            )
        contract_report = data.get("contract")
        if not isinstance(contract_report, dict):
            contract_report = {
                "ok": not blocking,
                "blocking_errors": list(blocking),
                "warnings": [],
                "matched_primary": [],
                "generated_count": len(artifacts),
            }
        return {
            "artifact_names": [str(item.get("path")) for item in artifacts],
            "contract_validation": contract_report,
            "verification": {
                "ok": verification.get("ok") is True,
                "blocking_errors": list(blocking),
                "warnings": [],
                "artifacts": artifacts,
            },
            "output_qa": {
                "enabled": True,
                "ok": verification.get("ok") is True,
                "blocking_errors": list(blocking),
                "warnings": [],
                "render_reports": [],
                "vision_qa": None,
            },
            "import_probe": {
                "enabled": False,
                "environment": "common_hardened_image",
                "ok": True,
                "packages": [],
            },
            "blocking_errors": blocking,
            "warnings": [],
        }

    def _finalize(self, *args, **kwargs):
        result = super()._finalize(*args, **kwargs)
        result["files"] = [
            item
            for item in result.get("files", [])
            if item.get("filename") != self.manifest_cfg.get("filename", "manifest.json")
        ]
        result["success"] = bool(
            result.get("success")
            and result.get("final_status") in {"ok", "repaired_ok"}
        )
        return result

    def _create_chat_completion(self, kwargs: Mapping[str, Any]):
        if self._backend is None or self._startup is None or not self._task_id:
            raise RuntimeError("hardened baseline is not preflighted")
        self._request_index += 1
        task_scope = json.dumps(
            [self.run_id, self.condition_name, self._task_id],
            separators=(",", ":"),
        )
        request_id = hashlib.sha256(
            json.dumps(
                [task_scope, self._request_index, kwargs],
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            ).encode("utf-8")
        ).hexdigest()
        estimated_input = len(
            json.dumps(kwargs, sort_keys=True, separators=(",", ":"), default=str)
            .encode("utf-8")
        )
        output_tokens = int(
            kwargs.get("max_completion_tokens")
            or self.agentic_limits.max_output_tokens
        )
        output_tokens = min(output_tokens, self.agentic_limits.max_output_tokens)
        reserved_cost = self.agentic_pricing.worst_case(
            estimated_input, output_tokens
        )
        scopes = self._budget_scopes(task_scope)
        reserved_by_scope = self.budget_ledger.reserve_many(
            scopes=scopes,
            request_id=request_id,
            input_tokens=estimated_input,
            output_tokens=output_tokens,
            cost_usd=reserved_cost,
        )
        self._budget_metrics["conservative_cost_usd"] = str(
            reserved_by_scope[task_scope].cost_usd
        )
        startup_data = self._startup.get("data") or {}
        self.authorize_request(
            task_scope,
            request_id,
            {
                "runtime_preflight_passed": True,
                "input_merkle_root": startup_data.get("input_merkle_root"),
                "selection_recomputation_sha256": startup_data.get(
                    "selection_recomputation_sha256"
                ),
                "provider_classification": startup_data.get(
                    "provider_classification"
                ),
                "substrate_manifest_sha256": (
                    startup_data.get("substrate_manifest") or {}
                ).get("sha256"),
                "model": self.model_name,
                "provider": self.provider,
                "api_version": self.api_version,
                "endpoint_sha256": self.endpoint_sha256,
                "approval_scope_sha256": self.approval_scope_sha256,
                "official_scope_registry_sha256": (
                    self.official_scope_registry_sha256
                ),
                "run_id": self.run_id,
                "condition": self.condition_name,
                "task_id": self._task_id,
                "task_request_sha256": self._task_request_sha256,
                "caps": self._authorization_caps(),
                "price_table_sha256": self.agentic_pricing.price_table_sha256,
                "official_scope_excluded": True,
            },
        )
        if self._provider_client is None:
            self._provider_client = self.client_factory()
        provider_client = self._provider_client
        if provider_client is None:
            raise RuntimeError("baseline provider client unavailable")
        self._budget_metrics["model_api_calls"] += 1
        remaining = self.agentic_limits.max_task_seconds - (
            time.monotonic() - self._run_started
        )
        if remaining < 1.0:
            raise RuntimeError("baseline_task_wall_time_exhausted")
        request_kwargs = dict(kwargs)
        request_kwargs["max_completion_tokens"] = output_tokens
        request_kwargs["timeout"] = min(480.0, remaining)
        if self._first_model_dispatch is None:
            self._first_model_dispatch = time.monotonic()
        try:
            response = provider_client.chat.completions.create(
                **request_kwargs
            )
        except Exception:
            self._budget_metrics["usage_complete"] = False
            raise
        usage = getattr(response, "usage", None)
        input_tokens = getattr(usage, "prompt_tokens", None)
        output_tokens_actual = getattr(usage, "completion_tokens", None)
        if not _valid_count(input_tokens) or not _valid_count(output_tokens_actual):
            self._budget_metrics["usage_complete"] = False
            raise RuntimeError("baseline_usage_incomplete")
        input_count = int(input_tokens)
        output_count = int(output_tokens_actual)
        details = getattr(usage, "prompt_tokens_details", None)
        cached_tokens = getattr(details, "cached_tokens", 0) if details else 0
        if not _valid_count(cached_tokens) or int(cached_tokens) > input_count:
            self._budget_metrics["usage_complete"] = False
            raise RuntimeError("baseline_usage_incomplete")
        cached_count = int(cached_tokens)
        actual_cost = self.agentic_pricing.actual(
            input_count, output_count, cached_count
        )
        try:
            reconciled = self.budget_ledger.reconcile_many(
                scopes=scopes,
                request_id=request_id,
                actual_input_tokens=input_count,
                actual_output_tokens=output_count,
                actual_cost_usd=actual_cost,
            )
        except Exception:
            self._budget_metrics["usage_complete"] = False
            raise
        self._budget_metrics["input_tokens"] += input_count
        self._budget_metrics["output_tokens"] += output_count
        self._budget_metrics["cached_tokens"] += cached_count
        self._budget_metrics["conservative_cost_usd"] = str(
            reconciled[task_scope].cost_usd
        )
        return response

    def _budget_scopes(self, task_scope: str) -> dict[str, BudgetCaps]:
        task_caps = BudgetCaps(
            attempts=self.agentic_limits.max_api_attempts,
            input_tokens=self.agentic_limits.max_input_tokens,
            output_tokens=self.agentic_limits.max_cumulative_output_tokens,
            cost_usd=self.agentic_limits.max_cost_usd,
        )
        paired_id = self.aggregate_budget.paired_run_id
        return {
            task_scope: task_caps,
            json.dumps(
                ["condition", paired_id, self.condition_name],
                separators=(",", ":"),
            ): self.aggregate_budget.condition,
            json.dumps(
                ["paired_run", paired_id], separators=(",", ":")
            ): self.aggregate_budget.paired_run,
        }

    def _authorization_caps(self) -> dict:
        task = {
            "api_attempts": self.agentic_limits.max_api_attempts,
            "model_iterations": self.agentic_limits.max_model_iterations,
            "input_tokens": self.agentic_limits.max_input_tokens,
            "output_tokens": self.agentic_limits.max_cumulative_output_tokens,
            "max_output_tokens_per_response": self.agentic_limits.max_output_tokens,
            "cost_usd": str(self.agentic_limits.max_cost_usd),
            "wall_seconds": self.agentic_limits.max_task_seconds,
        }
        return {
            "task": task,
            "condition": _caps_dict(self.aggregate_budget.condition),
            "paired_run": _caps_dict(self.aggregate_budget.paired_run),
            "paired_run_id": self.aggregate_budget.paired_run_id,
        }

    @staticmethod
    def _execution_failure(category: str) -> dict:
        return {
            "success": False,
            "text": "",
            "files": [],
            "preflight": None,
            "error_category": category,
            "error": category,
        }

    @staticmethod
    def _terminal_failure(category: str) -> dict:
        return {
            "success": False,
            "text": "",
            "files": [],
            "error": category,
        }

    @staticmethod
    def _new_budget_metrics() -> dict:
        return {
            "schema_version": "1.0",
            "model_api_calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cached_tokens": 0,
            "conservative_cost_usd": "0",
            "usage_complete": True,
            "time_to_valid_artifact_ms": None,
        }


def _caps_dict(caps: BudgetCaps) -> dict:
    return {
        "attempts": caps.attempts,
        "input_tokens": caps.input_tokens,
        "output_tokens": caps.output_tokens,
        "cost_usd": str(caps.cost_usd),
    }


def _valid_count(value: Any) -> bool:
    return type(value) is int and value >= 0