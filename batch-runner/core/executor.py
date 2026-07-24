"""
Task Executor - Mode dispatcher for file generation.

Selects and delegates to appropriate runner based on execution mode:
- code_interpreter: Azure OpenAI Responses API (OpenAI models only)
- subprocess: LLM code generation + safe execution (all models)
- sandbox: LLM code generation + skill-aware containerized execution (all models)
- agentic_sandbox: bounded Responses tool loop (Azure/OpenAI only)
- json_renderer: JSON spec + fixed renderer (fair comparison mode)
"""

import os
from pathlib import Path
from typing import Callable, Literal, Mapping, Optional

from core.agentic_authorization import (
    ApprovalExpectation,
    ApprovalNonceLedger,
    SignedApprovalGate,
    load_approval_scope,
    provider_endpoint_sha256,
)
from core.agentic_budget import AgenticBudgetLedger
from core.agentic_sandbox_runner import AgenticSandboxRunner
from core.agentic_pricing import load_pinned_model_pricing
from core.agentic_runtime_identity import derive_runtime_identity_from_environment
from core.agentic_remote_compute import remote_backend_factory_from_environment
from core.code_interpreter import CodeInterpreterRunner
from core.config import DEFAULT_TOKENS
from core.subprocess_runner import SubprocessRunner
from core.sandbox_runner import SandboxRunner
from core.json_renderer import JsonRenderer
from core.hardened_sandbox_runner import HardenedSandboxRunner

# Execution modes
ExecutionMode = Literal[
    "code_interpreter", "subprocess", "sandbox", "agentic_sandbox",
    "json_renderer",
]


def _load_live_approval_scope(
    *,
    repository_root: Path,
    condition_name: str,
    classification: str,
    ordered_task_ids: Optional[list[str]],
    task_request_digests: Optional[Mapping[str, str]],
) -> dict:
    scope_path = os.getenv("AGENTIC_APPROVAL_SCOPE_PATH")
    if not scope_path:
        raise ValueError("agentic approval scope path is required")
    scope = load_approval_scope(
        repository_root=repository_root,
        scope_path=scope_path,
    )
    if scope["conditions"] != (condition_name,):
        raise ValueError("approval scope condition set is not exact")
    expected_count = 5 if condition_name == "canary" else 20
    if len(scope["task_ids"]) != expected_count:
        raise ValueError("approval scope task count differs from preregistration")
    if ordered_task_ids is None or tuple(ordered_task_ids) != scope["task_ids"]:
        raise ValueError("prepared ordered task IDs differ from approval scope")
    if task_request_digests is None or dict(task_request_digests) != scope[
        "task_request_sha256"
    ]:
        raise ValueError("prepared task requests differ from approval scope")
    if set(scope["provider_classifications"].values()) != {classification}:
        raise ValueError("approval scope provider classifications differ")
    return scope


class TaskExecutor:
    """Task executor that dispatches to appropriate runner based on mode"""

    def __init__(
        self,
        mode: ExecutionMode,
        llm_client=None,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        prompt_name: Optional[str] = None,
        tokens: Optional[dict] = None,
        timeout: Optional[int] = None,
        reasoning_effort: Optional[str] = None,
        sandbox_options: Optional[dict] = None,
        metrics_options: Optional[dict] = None,
        provider: Optional[str] = None,
        client_factory: Optional[Callable[[], object]] = None,
        agentic_options: Optional[dict] = None,
        run_id: Optional[str] = None,
        condition_name: Optional[str] = None,
        model_name: Optional[str] = None,
        agentic_backend_factory=None,
        agentic_authorize_request=None,
        agentic_budget_ledger=None,
        agentic_remote_backend_factory=None,
        agentic_runtime_identity: Optional[Mapping[str, str]] = None,
        agentic_price_table_path: Optional[str] = None,
        agentic_endpoint: Optional[str] = None,
        agentic_ordered_task_ids: Optional[list[str]] = None,
        agentic_task_request_sha256: Optional[Mapping[str, str]] = None,
        non_paid_test_mode: bool = False,
        code_interpreter_client=None,
        redact_provider_errors: bool = False,
    ):
        """
        Initialize executor with specified mode.

        Args:
            mode: Execution mode (code_interpreter, subprocess, sandbox, json_renderer)
            llm_client: AzureOpenAI client (required for subprocess, sandbox, json_renderer)
            api_key: Azure OpenAI API key (optional, for code_interpreter)
            endpoint: Azure OpenAI endpoint (optional, for code_interpreter)
            prompt_name: Prompt YAML name for subprocess/sandbox mode
            tokens: Optional token limit overrides
            timeout: Subprocess/sandbox timeout override in seconds (None = config default)
            reasoning_effort: Optional reasoning effort level ("low", "medium", "high")
            sandbox_options: Optional dict of sandbox-mode settings from the
                experiment YAML ``execution.sandbox`` block. Keys: image (str),
                use_docker ("auto"|"never"|"always"), memory_gb (int),
                cpus (float), skills_dir (str), max_skills (int).
            metrics_options: Optional opt-in ``execution.metrics`` settings.
            provider: Explicit model provider for provider-restricted modes.
            client_factory: Deferred provider client constructor used only after
                the agentic runtime and signed approval gate pass.
            agentic_options: Strict ``execution.agentic`` settings.

        Raises:
            ValueError: If required parameters are missing for the selected mode
        """
        self.mode = mode
        self._closed = False
        self.hardened_sandbox = False
        self.tokens = dict(DEFAULT_TOKENS)
        if isinstance(tokens, dict):
            self.tokens.update({k: v for k, v in tokens.items() if v is not None})

        if mode == "code_interpreter":
            # Code Interpreter uses its own client
            self.runner = CodeInterpreterRunner(
                api_key=api_key,
                endpoint=endpoint,
                prompt_name=prompt_name,
                max_completion_tokens=self.tokens.get("code_generation"),
                client=code_interpreter_client,
                redact_provider_errors=redact_provider_errors,
            )

        elif mode == "subprocess":
            if llm_client is None:
                raise ValueError("subprocess mode requires llm_client")
            self.runner = SubprocessRunner(
                llm_client,
                prompt_name=prompt_name or SubprocessRunner.DEFAULT_PROMPT,
                max_completion_tokens=self.tokens.get("code_generation"),
                timeout=timeout,
                reasoning_effort=reasoning_effort,
            )

        elif mode == "sandbox":
            opts = dict(sandbox_options or {})
            metric_opts = metrics_options if isinstance(metrics_options, dict) else None
            if opts.get("hardened_substrate") is True:
                normalized_provider = (
                    "azure" if provider == "azure_openai" else provider
                )
                valid, error = self.validate_mode(
                    "agentic_sandbox", normalized_provider or ""
                )
                if not valid:
                    raise ValueError(error)
                common = dict(agentic_options or {})
                pricing_config = common.get("pricing")
                if non_paid_test_mode:
                    if (
                        agentic_backend_factory is None
                        or agentic_authorize_request is None
                        or agentic_budget_ledger is None
                    ):
                        raise ValueError(
                            "non-paid hardened sandbox tests require explicit fakes"
                        )
                    factory = client_factory or (lambda: llm_client)
                    backend_factory = agentic_backend_factory
                    authorizer = agentic_authorize_request
                    ledger = agentic_budget_ledger
                else:
                    if llm_client is not None:
                        raise ValueError(
                            "hardened sandbox requires deferred client construction"
                        )
                    required_identity = (run_id, condition_name, model_name)
                    if any(not value for value in required_identity):
                        raise ValueError(
                            "hardened sandbox requires run, condition, and model identity"
                        )
                    authorization = common.get("authorization")
                    if not isinstance(authorization, dict):
                        raise ValueError("execution.agentic.authorization is required")
                    required_authorization = (
                        "api_version", "provider_classification", "endpoint_sha256",
                    )
                    missing = [
                        key for key in required_authorization
                        if not authorization.get(key)
                    ]
                    if missing:
                        raise ValueError(
                            f"missing agentic authorization setting(s): {missing}"
                        )
                    runtime_identity = dict(
                        agentic_runtime_identity
                        or derive_runtime_identity_from_environment(
                            Path(__file__).resolve().parents[2]
                        )
                    )
                    endpoint_sha256 = provider_endpoint_sha256(
                        normalized_provider or "", agentic_endpoint
                    )
                    if endpoint_sha256 != authorization["endpoint_sha256"]:
                        raise ValueError("agentic provider endpoint identity mismatch")
                    repository_root = Path(__file__).resolve().parents[2]
                    approval_scope = _load_live_approval_scope(
                        repository_root=repository_root,
                        condition_name=condition_name or "",
                        classification=authorization["provider_classification"],
                        ordered_task_ids=agentic_ordered_task_ids,
                        task_request_digests=agentic_task_request_sha256,
                    )
                    signed_envelope_path = os.getenv(
                        "AGENTIC_SIGNED_APPROVAL_PATH"
                    )
                    nonce_ledger_path = os.getenv("AGENTIC_NONCE_LEDGER_PATH")
                    owner_public_key_path = (
                        Path(__file__).resolve().parents[1]
                        / "security" / "agentic-owner-ed25519.pub"
                    )
                    if not signed_envelope_path or not nonce_ledger_path:
                        raise ValueError(
                            "agentic approval environment paths are required"
                        )
                    gate = SignedApprovalGate(
                        signed_envelope_path=signed_envelope_path,
                        owner_public_key_path=owner_public_key_path,
                        nonce_ledger=ApprovalNonceLedger(
                            nonce_ledger_path
                        ),
                        expectation=ApprovalExpectation(
                            plan_sha=runtime_identity["plan_sha"],
                            implementation_sha=runtime_identity[
                                "implementation_sha"
                            ],
                            run_id=run_id,
                            condition=condition_name,
                            provider=normalized_provider or "",
                            model=model_name,
                            api_version=authorization["api_version"],
                            endpoint_sha256=endpoint_sha256,
                            workflow_sha=runtime_identity["workflow_sha"],
                            workflow_inputs_sha256=runtime_identity[
                                "workflow_inputs_sha256"
                            ],
                            conditions=approval_scope["conditions"],
                            task_ids=approval_scope["task_ids"],
                            input_merkle_roots=approval_scope[
                                "input_merkle_roots"
                            ],
                            provider_classifications=approval_scope[
                                "provider_classifications"
                            ],
                            task_request_sha256=approval_scope[
                                "task_request_sha256"
                            ],
                            selection_recomputation_sha256=approval_scope[
                                "selection_recomputation_sha256"
                            ],
                            approval_scope_sha256=approval_scope[
                                "approval_scope_sha256"
                            ],
                            official_scope_registry_sha256=approval_scope[
                                "official_scope_registry_sha256"
                            ],
                        ),
                    )
                    ledger_path = os.getenv("AGENTIC_BUDGET_LEDGER_PATH")
                    image = common.get("image")
                    if not ledger_path or not image:
                        raise ValueError(
                            "hardened sandbox requires common image and budget ledger"
                        )
                    factory = client_factory
                    authorizer = gate.authorize_request
                    ledger = AgenticBudgetLedger(ledger_path)
                    if common.get("compute_transport") != "remote":
                        raise ValueError(
                            "production hardened sandbox requires a remote "
                            "authenticated compute backend"
                        )
                    backend_factory = (
                        agentic_remote_backend_factory
                        if callable(agentic_remote_backend_factory)
                        else remote_backend_factory_from_environment(
                            run_id=run_id,
                            condition_name=condition_name,
                        )
                    )
                    price_table = common.get("pricing_table")
                    if not isinstance(price_table, dict):
                        raise ValueError("execution.agentic.pricing_table is required")
                    pricing_config = load_pinned_model_pricing(
                        path=(
                            agentic_price_table_path
                            or Path(__file__).resolve().parents[1]
                            / "security" / "agentic-pricing.json"
                        ),
                        expected_sha256=price_table.get("sha256", ""),
                        provider=normalized_provider or "",
                        model=model_name,
                    )
                self.hardened_sandbox = True
                self.runner = HardenedSandboxRunner(
                    client_factory=factory,
                    backend_factory=backend_factory,
                    budget_ledger=ledger,
                    authorize_request=authorizer,
                    run_id=run_id or "local-nonpaid",
                    condition_name=condition_name or "condition_a",
                    model_name=model_name or "test-model",
                    provider=normalized_provider or "",
                    api_version=(
                        (common.get("authorization") or {}).get("api_version")
                        or "nonpaid-test"
                    ),
                    endpoint_sha256=(
                        (common.get("authorization") or {}).get("endpoint_sha256")
                        or "nonpaid-test"
                    ),
                    approval_scope_sha256=(
                        approval_scope["approval_scope_sha256"]
                        if not non_paid_test_mode else "nonpaid-test"
                    ),
                    official_scope_registry_sha256=(
                        approval_scope["official_scope_registry_sha256"]
                        if not non_paid_test_mode else "nonpaid-test"
                    ),
                    limits=common.get("limits"),
                    pricing=pricing_config,
                    aggregate_budget=common.get("budget"),
                    prompt_name=(
                        prompt_name
                        or opts.get("prompt_name")
                        or SandboxRunner.DEFAULT_PROMPT
                    ),
                    max_completion_tokens=self.tokens.get("code_generation"),
                    timeout=timeout,
                    reasoning_effort=reasoning_effort,
                    skills_dir=opts.get("skills_dir"),
                    image=common.get("image") or opts.get("image"),
                    memory_gb=common.get("memory_gb"),
                    cpus=common.get("cpus"),
                    max_skills=opts.get("max_skills", 5),
                    repair=opts.get("repair"),
                    output_qa=opts.get("output_qa"),
                    manifest=opts.get("manifest"),
                    cache=opts.get("cache"),
                    contract=opts.get("contract"),
                    metrics=metric_opts,
                )
            else:
                if llm_client is None:
                    raise ValueError("sandbox mode requires llm_client")
                self.runner = SandboxRunner(
                    llm_client,
                    prompt_name=prompt_name or opts.get("prompt_name") or SandboxRunner.DEFAULT_PROMPT,
                    max_completion_tokens=self.tokens.get("code_generation"),
                    timeout=timeout,
                    reasoning_effort=reasoning_effort,
                    skills_dir=opts.get("skills_dir"),
                    image=opts.get("image"),
                    use_docker=opts.get("use_docker", "auto"),
                    memory_gb=opts.get("memory_gb"),
                    cpus=opts.get("cpus"),
                    max_skills=opts.get("max_skills", 5),
                    repair=opts.get("repair"),
                    output_qa=opts.get("output_qa"),
                    manifest=opts.get("manifest"),
                    cache=opts.get("cache"),
                    contract=opts.get("contract"),
                    metrics=metric_opts,
                )

        elif mode == "agentic_sandbox":
            normalized_provider = "azure" if provider == "azure_openai" else provider
            valid, error = self.validate_mode(mode, normalized_provider or "")
            if not valid:
                raise ValueError(error)
            opts = dict(agentic_options or {})
            limits = opts.get("limits")
            pricing = opts.get("pricing")

            if non_paid_test_mode:
                if agentic_backend_factory is None or agentic_authorize_request is None:
                    raise ValueError(
                        "non-paid agentic tests require explicit backend and authorization fakes"
                    )
                ledger = agentic_budget_ledger
                if ledger is None:
                    raise ValueError("non-paid agentic tests require an explicit budget ledger")
                self.runner = AgenticSandboxRunner(
                    llm_client,
                    client_factory=client_factory,
                    non_paid_test_mode=llm_client is not None,
                    backend_factory=agentic_backend_factory,
                    budget_ledger=ledger,
                    authorize_request=agentic_authorize_request,
                    prompt_name=prompt_name or AgenticSandboxRunner.DEFAULT_PROMPT,
                    reasoning_effort=reasoning_effort,
                    limits=limits,
                    pricing=pricing,
                    aggregate_budget=opts.get("budget"),
                )
            else:
                required_identity = {
                    "run_id": run_id,
                    "condition_name": condition_name,
                    "model_name": model_name,
                }
                if any(not value for value in required_identity.values()):
                    raise ValueError(
                        "agentic_sandbox requires run_id, condition_name, and model_name"
                    )
                authorization = opts.get("authorization")
                if not isinstance(authorization, dict):
                    raise ValueError("execution.agentic.authorization is required")
                required_authorization = (
                    "api_version", "provider_classification", "endpoint_sha256",
                )
                missing = [
                    key for key in required_authorization if not authorization.get(key)
                ]
                if missing:
                    raise ValueError(
                        f"missing agentic authorization setting(s): {missing}"
                    )
                runtime_identity = dict(
                    agentic_runtime_identity
                    or derive_runtime_identity_from_environment(
                        Path(__file__).resolve().parents[2]
                    )
                )
                endpoint_sha256 = provider_endpoint_sha256(
                    normalized_provider or "", agentic_endpoint
                )
                if endpoint_sha256 != authorization["endpoint_sha256"]:
                    raise ValueError("agentic provider endpoint identity mismatch")
                repository_root = Path(__file__).resolve().parents[2]
                approval_scope = _load_live_approval_scope(
                    repository_root=repository_root,
                    condition_name=condition_name or "",
                    classification=authorization["provider_classification"],
                    ordered_task_ids=agentic_ordered_task_ids,
                    task_request_digests=agentic_task_request_sha256,
                )
                signed_envelope_path = os.getenv("AGENTIC_SIGNED_APPROVAL_PATH")
                nonce_ledger_path = os.getenv("AGENTIC_NONCE_LEDGER_PATH")
                owner_public_key_path = (
                    Path(__file__).resolve().parents[1]
                    / "security" / "agentic-owner-ed25519.pub"
                )
                if not signed_envelope_path or not nonce_ledger_path:
                    raise ValueError("agentic approval environment paths are required")
                gate = SignedApprovalGate(
                    signed_envelope_path=signed_envelope_path,
                    owner_public_key_path=owner_public_key_path,
                    nonce_ledger=ApprovalNonceLedger(nonce_ledger_path),
                    expectation=ApprovalExpectation(
                        plan_sha=runtime_identity["plan_sha"],
                        implementation_sha=runtime_identity[
                            "implementation_sha"
                        ],
                        run_id=run_id,
                        condition=condition_name,
                        provider=normalized_provider or "",
                        model=model_name,
                        api_version=authorization["api_version"],
                        endpoint_sha256=endpoint_sha256,
                        workflow_sha=runtime_identity["workflow_sha"],
                        workflow_inputs_sha256=runtime_identity[
                            "workflow_inputs_sha256"
                        ],
                        conditions=approval_scope["conditions"],
                        task_ids=approval_scope["task_ids"],
                        input_merkle_roots=approval_scope["input_merkle_roots"],
                        provider_classifications=approval_scope[
                            "provider_classifications"
                        ],
                        task_request_sha256=approval_scope[
                            "task_request_sha256"
                        ],
                        selection_recomputation_sha256=approval_scope[
                            "selection_recomputation_sha256"
                        ],
                        approval_scope_sha256=approval_scope[
                            "approval_scope_sha256"
                        ],
                        official_scope_registry_sha256=approval_scope[
                            "official_scope_registry_sha256"
                        ],
                    ),
                )
                ledger_path = os.getenv("AGENTIC_BUDGET_LEDGER_PATH")
                if not ledger_path:
                    raise ValueError("execution.agentic.budget_ledger_path is required")
                if not isinstance(opts.get("budget"), dict):
                    raise ValueError("execution.agentic.budget is required")
                image = opts.get("image")
                if not image:
                    raise ValueError("execution.agentic.image is required")
                if opts.get("compute_transport") != "remote":
                    raise ValueError(
                        "production agentic_sandbox requires a remote "
                        "authenticated compute backend"
                    )
                backend_factory = (
                    agentic_remote_backend_factory
                    if callable(agentic_remote_backend_factory)
                    else remote_backend_factory_from_environment(
                        run_id=run_id,
                        condition_name=condition_name,
                    )
                )
                price_table = opts.get("pricing_table")
                if not isinstance(price_table, dict):
                    raise ValueError("execution.agentic.pricing_table is required")
                pricing = load_pinned_model_pricing(
                    path=(
                        agentic_price_table_path
                        or Path(__file__).resolve().parents[1]
                        / "security" / "agentic-pricing.json"
                    ),
                    expected_sha256=price_table.get("sha256", ""),
                    provider=normalized_provider or "",
                    model=model_name,
                )
                self.runner = AgenticSandboxRunner(
                    client_factory=client_factory,
                    backend_factory=backend_factory,
                    budget_ledger=AgenticBudgetLedger(ledger_path),
                    authorize_request=gate.authorize_request,
                    prompt_name=prompt_name or AgenticSandboxRunner.DEFAULT_PROMPT,
                    reasoning_effort=reasoning_effort,
                    limits=limits,
                    pricing=pricing,
                    aggregate_budget=opts["budget"],
                    provider=normalized_provider or "",
                    api_version=authorization["api_version"],
                    endpoint_sha256=endpoint_sha256,
                    approval_scope_sha256=approval_scope[
                        "approval_scope_sha256"
                    ],
                    official_scope_registry_sha256=approval_scope[
                        "official_scope_registry_sha256"
                    ],
                )

        elif mode == "json_renderer":
            if llm_client is None:
                raise ValueError("json_renderer mode requires llm_client")
            self.runner = JsonRenderer(
                llm_client,
                max_completion_tokens=self.tokens.get("json_render"),
            )

        else:
            raise ValueError(f"Unknown execution mode: {mode}")

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        close = getattr(self.runner, "close", None)
        if callable(close):
            close()

    def __enter__(self) -> "TaskExecutor":
        if self._closed:
            raise RuntimeError("Task executor is closed")
        return self

    def __exit__(self, _exc_type, _exc, _traceback) -> None:
        self.close()

    def execute(
        self,
        task_prompt: str,
        model: str,
        reference_files: Optional[list] = None,
        occupation: str = "professional",
        experiment_prompt: Optional[dict] = None,
        verbose: bool = False,
        perception_text: Optional[str] = None,
        run_id: Optional[str] = None,
        condition_name: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> dict:
        """
        Execute task using selected runner.

        Args:
            task_prompt: The task instruction
            model: Model deployment name
            reference_files: Optional list of reference file paths
            occupation: Professional role from task data
            experiment_prompt: Optional prompt overrides from experiment YAML
                Keys: system (str), prefix (str|None), body (str|None), suffix (str|None)
            verbose: Print detailed debug info (code_interpreter mode only)
            perception_text: Optional host audio/video analysis block. Only the
                sandbox runner consumes it (it owns placement via the
                ``perception_analysis`` spec section); other modes ignore it since
                step2 still prepends perception to the task prompt for them.

        Returns:
            dict with standardized format:
                - success (bool): Whether execution succeeded
                - text (str): Text response
                - files (list): Generated files [{filename, content}]
                - error (str, optional): Error message if failed
        """
        try:
            if self._closed:
                raise RuntimeError("Task executor is closed")
            if self.mode == "code_interpreter":
                return self.runner.run(
                    task_prompt=task_prompt,
                    model=model,
                    reference_files=reference_files,
                    occupation=occupation,
                    experiment_prompt=experiment_prompt,
                    verbose=verbose,
                )

            elif self.mode == "subprocess":
                return self.runner.run(
                    task_prompt=task_prompt,
                    model=model,
                    reference_files=reference_files,
                    occupation=occupation,
                    experiment_prompt=experiment_prompt,
                )

            elif self.mode in {"sandbox", "agentic_sandbox"}:
                extra = {}
                if self.mode == "agentic_sandbox" or self.hardened_sandbox:
                    extra = {
                        "run_id": run_id or "local-nonpaid",
                        "condition_name": condition_name or "condition_a",
                        "task_id": task_id or "unknown-task",
                    }
                return self.runner.run(
                    task_prompt=task_prompt,
                    model=model,
                    reference_files=reference_files,
                    occupation=occupation,
                    experiment_prompt=experiment_prompt,
                    perception_text=perception_text,
                    **extra,
                )

            elif self.mode == "json_renderer":
                # JSON renderer doesn't use reference files (spec only)
                return self.runner.run(
                    task_prompt=task_prompt,
                    model=model
                )

        except Exception as exc:
            return {
                "success": False,
                "text": "",
                "files": [],
                "error": f"Executor error ({self.mode}): {str(exc)}",
            }

    @staticmethod
    def validate_mode(mode: str, model_provider: str) -> tuple[bool, Optional[str]]:
        """
        Validate if execution mode is compatible with model provider.

        Args:
            mode: Execution mode
            model_provider: Model provider (e.g., "azure", "openai", "anthropic")

        Returns:
            (is_valid, error_message) tuple
        """
        if mode == "code_interpreter":
            if model_provider not in ["azure", "azure_openai"]:
                return (
                    False,
                    "code_interpreter mode requires Azure, "
                    f"got {model_provider}"
                )
        if mode == "agentic_sandbox":
            if model_provider not in ["azure", "openai"]:
                return (
                    False,
                    "agentic_sandbox mode requires OpenAI/Azure OpenAI, "
                    f"got {model_provider}"
                )

        return (True, None)

    @staticmethod
    def recommend_mode(model_provider: str, score_type: str = "tool_assisted") -> ExecutionMode:
        """
        Recommend execution mode based on model provider and score type.

        Args:
            model_provider: Model provider (e.g., "azure", "openai", "anthropic")
            score_type: Score type ("tool_assisted" or "portable")

        Returns:
            Recommended ExecutionMode
        """
        # Fair comparison mode: always use JSON renderer
        if score_type == "portable":
            return "json_renderer"

        # Tool-assisted mode: use best available for each provider
        if model_provider in ["azure", "azure_openai"]:
            return "code_interpreter"
        else:
            return "subprocess"
