"""Rubric-based grading engine.

Routes rubric items to an Azure OpenAI Responses API judge. Evidence is
mandatory for judge verdicts.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

from core.azure_ai_clients import (
    AzureAIClientFactory,
    AzureAIWorkload,
    canonical_deployment,
    grader_route_workloads,
)
from core.llm_client import ManagedAzureAIClient, create_typed_azure_client
from core.public_error import public_provider_error_text
from core.deliverable_selector import (
    CriterionTargetPlan,
    DeliverableSelection,
    plan_targets_for_criterion,
    select_deliverables,
)
from core.file_reader import read_reference_file
from core.grader_routing import (
    Modality,
    RoutingDecision,
    is_overall_style_criterion,
    resolve_runtime_routing,
)
from core.rubric_loader import RubricItem, TaskRubric

logger = logging.getLogger(__name__)

DEFAULT_GRADER_TIMEOUT = 600
DEFAULT_GRADER_API_VERSION = "2025-04-01-preview"


def grader_transport_options(config: dict) -> dict[str, object]:
    """Return the exact transport fields bound into grader route identity."""
    judge = config.get("judge") or {}
    timeout = int(judge.get("timeout_sec", DEFAULT_GRADER_TIMEOUT))
    api_version = judge.get("api_version", DEFAULT_GRADER_API_VERSION)
    if timeout <= 0:
        raise ValueError("judge.timeout_sec must be positive")
    if not isinstance(api_version, str) or not api_version.strip():
        raise ValueError("judge.api_version must be a nonempty string")
    return {
        "timeout": timeout,
        "legacy_api_version": api_version.strip(),
    }


def resolve_tool_prompt_path(config: dict) -> Path:
    """Return the exact tool prompt path used by the v2 judge."""
    prompt_config = config.get("prompt") or {}
    configured = prompt_config.get("tool_template")
    if configured:
        return Path(str(configured))
    template = prompt_config.get("template")
    if not template:
        raise ValueError("prompt.template is required")
    return Path(str(template)).with_name("grader_judge_v2.md")

Verdict = Literal["pass", "partial", "fail", "judge_error"]
DecidedBy = Literal["precheck", "judge"]

# ---------------------------------------------------------------------------
# PR1 task 101 — critical-item project convention.
#
# GDPVal v2 rubric exposes a `required` field on each item, but in practice
# it is `null` for every observed rubric (verified across 220 task / 10,453
# items in exp003; see data/grades/_validation/SCORE_MATH_AUDIT.md). With
# no authoritative criticality signal from the rubric authors we adopt a
# project-level convention: an item is critical iff its score magnitude
# meets MAGNITUDE_THRESHOLD. This covers both high-positive must-have
# criteria AND high-negative penalty criteria (the 94 negative-magnitude
# items previously excluded from the critical set under the legacy
# `score >= 4` rule).
#
# Threshold value is a heuristic. Re-evaluate (e.g. raise to 5) if a future
# rubric-author signal becomes available or if gold-ceiling validation
# (PR3 task 300) shows the boundary mis-classifies items.
MAGNITUDE_THRESHOLD = 4


def _is_critical_item(max_score: int | float | None) -> bool:
    try:
        return abs(max_score or 0) >= MAGNITUDE_THRESHOLD
    except Exception:
        return False


def _extract_finish_reason(response, max_output: int, output_tokens: int) -> str:
    """Best-effort finish_reason for Azure OpenAI Responses API.

    The Responses API exposes the reason variably across SDK versions —
    sometimes as `response.status`, sometimes nested under
    `response.incomplete_details.reason`, sometimes only inferable from
    `usage.output_tokens >= max_output`. We try in this order:
      1. response.incomplete_details.reason  (canonical)
      2. response.status                     (some SDK versions)
      3. heuristic: output_tokens >= max_output → "length"
      4. ""                                  (unknown)
    """
    incomplete = getattr(response, "incomplete_details", None)
    reason = getattr(incomplete, "reason", None) if incomplete is not None else None
    if isinstance(reason, str) and reason:
        return reason.lower()

    status = getattr(response, "status", None)
    if isinstance(status, str) and status in {"incomplete", "length", "max_tokens"}:
        return status.lower() if status != "max_tokens" else "length"

    if max_output > 0 and output_tokens >= max_output:
        return "length"
    return ""

@dataclass
class ItemGrade:
    rubric_item_id: str
    criterion: str
    max_score: int
    awarded_score: float
    verdict: Verdict
    decided_by: DecidedBy
    required: Optional[bool]
    evidence: str
    judge_confidence: Optional[float] = None
    judge_latency_ms: Optional[float] = None
    precheck_pattern_id: Optional[str] = None
    judge_raw_response: Optional[str] = None
    # PR1 task 100 — sign-aware normalization. Computed in _aggregate.
    # True iff the deliverable did the *right* thing for this item,
    # independent of item-score sign. For positive items right=pass;
    # for negative (penalty) items right=fail (i.e. the bad thing did
    # NOT happen). judge_error is conservatively right=False.
    model_did_right: bool = False
    # PR3 (0531) perception-wiring instrumentation (v2 tool-calling path
    # only; None/empty on v1 + precheck items). Proves at runtime which
    # modality an item routed to and whether a perception sub-judge fired.
    routing_modality: Optional[str] = None
    perception_called: bool = False
    tools_used: Optional[list[str]] = None
    visual_provenance: list[dict] = field(default_factory=list)
    target_scope: Optional[str] = None
    target_ids: Optional[list[str]] = None
    child_grades: Optional[list[dict]] = None
    aggregation_rule: Optional[str] = None
    selected_paths: Optional[list[str]] = None
    support_paths_visible: Optional[list[str]] = None
    selection_status: Optional[str] = None
    selection_error: Optional[str] = None
    score_excluded: bool = False
    judge_call_count: int = 0
    judge_input_tokens: int = 0
    judge_output_tokens: int = 0
    judge_cached_tokens: int = 0
    perception_call_count: int = 0
    perception_input_tokens: int = 0
    perception_output_tokens: int = 0
    perception_cached_tokens: int = 0
    perception_total_latency_ms: float = 0.0
    render_call_count: int = 0
    render_total_latency_ms: float = 0.0
    usage_complete: bool = True


@dataclass
class TaskGrade:
    task_id: str
    sector: str
    occupation: str
    items: list[ItemGrade]
    total_awarded: float
    total_max: int
    pct: float
    critical_fail: bool
    gold_referenced: bool
    judge_call_count: int
    precheck_count: int
    judge_total_latency_ms: float
    judge_input_tokens: int
    judge_output_tokens: int
    error: Optional[str] = None
    # PR1 task 102 — un-clamped pct for diagnostics. pct above is clamped
    # to [0, 100] for schema compatibility; pct_raw preserves the actual
    # ratio (can be < 0 when negative penalties dominate, can theoretically
    # exceed 100 if a judge over-awards). Used by analyzers / dashboard
    # to surface scoring anomalies that the clamp would otherwise hide.
    pct_raw: float = 0.0
    # PR3 Step 0 — cached input tokens (Azure Responses API automatic
    # prompt caching). 0 for legacy v1 path; populated by ToolCallingJudge
    # via side-channel _last_cached_tokens. Used for effective-cost math.
    judge_cached_tokens: int = 0
    selected_deliverables: Optional[dict] = None
    reference_files_excluded: list[str] = field(default_factory=list)
    selection_rule: Optional[str] = None
    selection_status: Optional[str] = None
    selection_error: Optional[str] = None
    perception_call_count: int = 0
    perception_input_tokens: int = 0
    perception_output_tokens: int = 0
    perception_cached_tokens: int = 0
    perception_total_latency_ms: float = 0.0
    render_call_count: int = 0
    render_total_latency_ms: float = 0.0
    usage_complete: bool = True


@dataclass(frozen=True)
class _RuntimeCriterionPlan:
    target_plan: CriterionTargetPlan
    item_decision: RoutingDecision
    target_decisions: dict[str, RoutingDecision]
    visual_paths: tuple[str, ...]
    visual_preflight_error: Optional[str]
    supported_visual_call_count: int
    requires_visual: bool


class Grader:
    def __init__(
        self,
        config: dict,
        rubric_loader,
        *,
        client=None,
        client_factory: AzureAIClientFactory | None = None,
    ):
        self.config = config
        self.rubric_loader = rubric_loader

        provider = self.config.get("judge", {}).get("provider", "azure_openai")
        if provider != "azure_openai":
            raise NotImplementedError(f"Unsupported judge provider: {provider}")

        endpoint_env = self.config["judge"].get("endpoint_env")
        if endpoint_env is not None:
            raise ValueError(
                "judge.endpoint_env is deprecated; use typed Azure AI runtime env"
            )

        transport = grader_transport_options(self.config)
        deployment = canonical_deployment(self.config["judge"], "judge")
        self.model = deployment
        grader_route_workloads(self.config)

        self._managed_client: ManagedAzureAIClient | None = None
        if client is None:
            self._managed_client = create_typed_azure_client(
                AzureAIWorkload.GRADER,
                deployment,
                factory=client_factory,
                **transport,
            )
            client = self._managed_client.client
        self.client = client

        try:
            self.prompt_template = self._read_prompt_template(
                self.config["prompt"]["template"]
            )
            self.prompt_version = self._extract_prompt_version(self.prompt_template)
            self._min_delay_seconds = (
                float(
                    self.config.get("tpm_guard", {}).get(
                        "min_delay_ms_between_calls", 0
                    )
                )
                / 1000.0
            )
            self._last_judge_call_at: float | None = None

            # --- Optional: prompt-level batching + tiered judge routing ---
            self.batch_size = int(
                self.config.get("grader", {}).get("batch_size", 1) or 1
            )
            self.judge_routing = self.config.get("judge_routing") or None
            self._use_batch = (self.batch_size > 1) or bool(self.judge_routing)
            self._tier_judges: dict[str, "object"] = {}
            if self._use_batch:
                self._build_tier_judges()

            self._tool_judge = None
            if self._is_tool_calling_config():
                self._tool_judge = self._build_tool_calling_judge()
        except BaseException:
            try:
                self.close()
            except BaseException:
                pass
            raise

    @property
    def runtime_fingerprint(self) -> str | None:
        if self._managed_client is None:
            return None
        return self._managed_client.runtime_fingerprint

    def close(self) -> None:
        managed_client = self._managed_client
        if managed_client is None:
            return
        try:
            managed_client.close()
        finally:
            self._managed_client = None
            self.client = None

    def __enter__(self) -> "Grader":
        return self

    def __exit__(self, _exc_type, _exc, _traceback) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Batch / tier routing (no-op unless config opts in)
    # ------------------------------------------------------------------

    def _build_tier_judges(self) -> None:
        """Instantiate one `BatchJudge` per active tier.

        Tier resolution order: pro > mini > standard. The 'standard' tier
        is always present and uses the top-level `judge` block as its
        defaults so that a plain `batch_size: 8` config (no routing)
        Just Works using the same model as single-item mode.
        """
        from core.grader_batch import BatchJudge  # local import; avoid cycle

        # Load the batch prompt template. Falls back to a sibling file next
        # to the configured single-item prompt template.
        batch_prompt_path = self._resolve_batch_prompt_path()
        batch_prompt_template = self._read_prompt_template(batch_prompt_path)

        base_judge_cfg = dict(self.config.get("judge", {}))
        base_judge_cfg.setdefault(
            "reasoning_effort", base_judge_cfg.get("reasoning", {}).get("effort", "high")
        )
        base_judge_cfg.setdefault(
            "max_output_tokens",
            base_judge_cfg.get("generation", {}).get(
                "max_output_tokens",
                self.config.get("grader", {}).get("per_item_max_output_tokens", 2400),
            ),
        )
        grader_cfg = self.config.get("grader", {})
        tpm_guard = self.config.get("tpm_guard", {})

        def _tier_cfg(tier_block: dict | None, defaults: dict) -> dict:
            cfg = dict(defaults)
            if tier_block:
                deployment = canonical_deployment(
                    tier_block,
                    "judge_routing.tier",
                    fallback=str(defaults.get("deployment") or defaults.get("model") or ""),
                )
                cfg["model"] = deployment
                cfg["deployment"] = deployment
                for k in ("reasoning_effort", "max_output_tokens"):
                    if k in tier_block and tier_block[k] is not None:
                        cfg[k] = tier_block[k]
            return cfg

        routing = self.judge_routing or {}
        tier_standard_block = routing.get("tier_standard") or {}
        tier_pro_block = routing.get("tier_pro") or {}
        tier_mini_block = routing.get("tier_mini") or {}

        standard_cfg = _tier_cfg(tier_standard_block, base_judge_cfg)
        self._tier_judges["standard"] = BatchJudge(
            client=self.client,
            judge_config=standard_cfg,
            tpm_guard=tpm_guard,
            prompt_template=batch_prompt_template,
            grader_config=grader_cfg,
        )

        if tier_pro_block:
            pro_cfg = _tier_cfg(tier_pro_block, base_judge_cfg)
            self._tier_judges["pro"] = BatchJudge(
                client=self.client,
                judge_config=pro_cfg,
                tpm_guard=tpm_guard,
                prompt_template=batch_prompt_template,
                grader_config=grader_cfg,
            )

        if tier_mini_block:
            mini_defaults = dict(base_judge_cfg)
            # NOTE: 'minimal' is NOT supported by gpt-5.4-mini (Azure rejects
            # with HTTP 400 'Unsupported value'). Valid effort levels for the
            # mini model are: none, low, medium, high, xhigh. We default to
            # 'low' (the lightest valid level) for the cost-efficient tier.
            mini_defaults["reasoning_effort"] = tier_mini_block.get("reasoning_effort", "low")
            mini_defaults["max_output_tokens"] = int(tier_mini_block.get("max_output_tokens", 400))
            mini_cfg = _tier_cfg(tier_mini_block, mini_defaults)
            self._tier_judges["mini"] = BatchJudge(
                client=self.client,
                judge_config=mini_cfg,
                tpm_guard=tpm_guard,
                prompt_template=batch_prompt_template,
                grader_config=grader_cfg,
            )

    def _resolve_batch_prompt_path(self) -> str:
        """Locate the batch-mode prompt template.

        Default rule: sibling file named `grader_judge_batch.md` next to the
        configured single-item prompt template. Caller can override via
        `prompt.batch_template` in the grading config.
        """
        override = self.config.get("prompt", {}).get("batch_template")
        if override:
            return str(override)
        single_path = Path(self.config["prompt"]["template"])
        candidate = single_path.with_name("grader_judge_batch.md")
        return str(candidate)

    def _route_to_tier(self, item: RubricItem) -> str:
        """Return the tier name for one judge item: 'pro' | 'mini' | 'standard'."""
        if not self.judge_routing:
            return "standard"

        pro = (self.judge_routing.get("tier_pro") or {}) if "pro" in self._tier_judges else {}
        route_when = pro.get("route_when") or {}
        weight_gte = route_when.get("weight_gte")
        if weight_gte is not None:
            try:
                if int(item.score) >= int(weight_gte):
                    return "pro"
            except (TypeError, ValueError):
                pass

        mini = (self.judge_routing.get("tier_mini") or {}) if "mini" in self._tier_judges else {}
        patterns = mini.get("criterion_pattern_match") or []
        if patterns:
            crit_lower = item.criterion.lower()
            for pat in patterns:
                if isinstance(pat, str) and pat.lower() in crit_lower:
                    return "mini"

        return "standard"

    @staticmethod
    def _classify(item: RubricItem) -> tuple[str, Optional[str]]:
        return "judge", None

    def grade_task(self, task: TaskRubric, deliverable_dir: str) -> TaskGrade:
        deliverable_path = Path(deliverable_dir)
        files = self._list_files(deliverable_path)

        # PR3 (0531) — reset per-task perception call caps before each task.
        if self._tool_judge is not None:
            self._tool_judge.reset_perception()
            return self._grade_task_with_selector(task, deliverable_path, files)

        if self._use_batch:
            return self._grade_task_batched(task, deliverable_path, files)

        no_deliverables = not deliverable_path.exists() or not files
        items: list[ItemGrade] = []
        judge_call_count = 0
        precheck_count = 0
        judge_total_latency_ms = 0.0
        judge_input_tokens = 0
        judge_output_tokens = 0
        # PR3 Step 0 — cached-tokens accumulator (v2 path only)
        judge_cached_tokens = 0

        for item in task.rubric_items:
            mode, pattern_id = self._classify(item)
            if no_deliverables:
                if mode == "judge":
                    ig = self._absent_judge_item(item)
                    judge_call_count += 1
                else:
                    ig = self._fail_precheck_item(item, pattern_id, "deliverable absent")
                    precheck_count += 1
                items.append(ig)
                continue

            if mode == "precheck":
                precheck_count += 1
                pre = self._run_precheck(pattern_id, item, files)
                if pre is None:
                    self._last_cached_tokens = 0
                    ig, in_tok, out_tok = self._judge(task, item, files)
                    judge_call_count += 1
                    judge_total_latency_ms += ig.judge_latency_ms or 0.0
                    judge_input_tokens += in_tok
                    judge_output_tokens += out_tok
                    judge_cached_tokens += getattr(self, '_last_cached_tokens', 0)
                else:
                    verdict, evidence = pre
                    ig = self._to_item_grade_from_precheck(
                        item, pattern_id, verdict, evidence
                    )
            else:
                self._last_cached_tokens = 0
                ig, in_tok, out_tok = self._judge(task, item, files)
                judge_call_count += 1
                judge_total_latency_ms += ig.judge_latency_ms or 0.0
                judge_input_tokens += in_tok
                judge_output_tokens += out_tok
                judge_cached_tokens += getattr(self, '_last_cached_tokens', 0)
            items.append(ig)

        grade = self._aggregate(items, task)
        grade.judge_call_count = judge_call_count
        grade.precheck_count = precheck_count
        grade.judge_total_latency_ms = round(judge_total_latency_ms, 2)
        grade.judge_input_tokens = judge_input_tokens
        grade.judge_output_tokens = judge_output_tokens
        grade.judge_cached_tokens = judge_cached_tokens
        if no_deliverables:
            grade.error = "no_deliverables"
        return grade

    def _grade_task_with_selector(
        self, task: TaskRubric, deliverable_path: Path, files: list[Path]
    ) -> TaskGrade:
        """Tool-calling path with deterministic deliverable selection.

        The selector only decides which files are visible to each item. The
        judge/precheck verdict logic stays on the existing code paths.
        """
        selection = self._select_deliverables(task, deliverable_path, files)
        file_map = self._relative_file_map(deliverable_path, files)
        reference_file_names = list(selection.reference_files_excluded)
        runtime_plans = [
            self._runtime_criterion_plan(
                selection,
                item,
                plan_targets_for_criterion(selection, item.criterion),
            )
            for item in task.rubric_items
        ]
        visual_budget_error = self._task_visual_budget_error(runtime_plans)

        items: list[ItemGrade] = []
        judge_call_count = 0
        precheck_count = 0
        judge_total_latency_ms = 0.0
        judge_input_tokens = 0
        judge_output_tokens = 0
        judge_cached_tokens = 0

        for item, runtime_plan in zip(task.rubric_items, runtime_plans):
            mode, pattern_id = self._classify(item)
            plan = runtime_plan.target_plan

            if selection.selection_status == "selection_error":
                ig = self._selection_ungraded_item(
                    item,
                    f"selection_error: {selection.selection_error or 'ambiguous candidate selection'}",
                    selection,
                    plan,
                )
                items.append(ig)
                continue

            if selection.selection_status == "no_generated_candidate":
                evidence = "no generated deliverable after reference set-diff"
                if mode == "precheck":
                    ig = self._fail_precheck_item(item, pattern_id, evidence)
                    precheck_count += 1
                else:
                    ig = self._fail_judge_item(item, evidence)
                self._attach_target_audit(ig, plan, selection)
                items.append(ig)
                continue

            if selection.selection_status == "wrong_format_primary":
                evidence = selection.selection_error or "wrong_format_primary"
                if is_overall_style_criterion(item.criterion):
                    ig = self._selection_ungraded_item(
                        item,
                        f"wrong_format_primary: {evidence}",
                        selection,
                        plan,
                    )
                elif mode == "precheck":
                    ig = self._fail_precheck_item(item, pattern_id, evidence)
                    precheck_count += 1
                    self._attach_target_audit(ig, plan, selection)
                else:
                    ig = self._fail_judge_item(item, evidence)
                    self._attach_target_audit(ig, plan, selection)
                items.append(ig)
                continue

            if runtime_plan.visual_preflight_error:
                if plan.target_scope == "split_children":
                    ig, in_tok, out_tok, calls, latency, cached = self._judge_split_children(
                        task,
                        item,
                        selection,
                        deliverable_path,
                        reference_file_names,
                        plan,
                        runtime_plan=runtime_plan,
                        preflight_error=runtime_plan.visual_preflight_error,
                    )
                    judge_call_count += calls
                    judge_total_latency_ms += latency
                    judge_input_tokens += in_tok
                    judge_output_tokens += out_tok
                    judge_cached_tokens += cached
                else:
                    ig = self._selection_ungraded_item(
                        item,
                        runtime_plan.visual_preflight_error,
                        selection,
                        plan,
                    )
                    ig.routing_modality = Modality.VISUAL.value
                    ig.tools_used = []
                items.append(ig)
                continue

            if visual_budget_error and runtime_plan.requires_visual:
                if plan.target_scope == "split_children":
                    ig, in_tok, out_tok, calls, latency, cached = self._judge_split_children(
                        task,
                        item,
                        selection,
                        deliverable_path,
                        reference_file_names,
                        plan,
                        runtime_plan=runtime_plan,
                        preflight_error=visual_budget_error,
                    )
                    judge_call_count += calls
                    judge_total_latency_ms += latency
                    judge_input_tokens += in_tok
                    judge_output_tokens += out_tok
                    judge_cached_tokens += cached
                else:
                    ig = self._selection_ungraded_item(
                        item,
                        visual_budget_error,
                        selection,
                        plan,
                    )
                    ig.routing_modality = Modality.VISUAL.value
                    ig.tools_used = []
                items.append(ig)
                continue

            if plan.target_scope == "split_children":
                ig, in_tok, out_tok, calls, latency, cached = self._judge_split_children(
                    task,
                    item,
                    selection,
                    deliverable_path,
                    reference_file_names,
                    plan,
                    runtime_plan=runtime_plan,
                )
                judge_call_count += calls
                judge_total_latency_ms += latency
                judge_input_tokens += in_tok
                judge_output_tokens += out_tok
                judge_cached_tokens += cached
                items.append(ig)
                continue

            selected_files = self._paths_for_selected(plan.selected_paths, file_map)
            if not selected_files:
                ig = self._selection_ungraded_item(
                    item,
                    "selection_error: no selected target files for criterion",
                    selection,
                    plan,
                )
                items.append(ig)
                continue

            if mode == "precheck":
                precheck_count += 1
                pre = self._run_precheck(pattern_id, item, selected_files)
                if pre is None:
                    self._last_cached_tokens = 0
                    ig, in_tok, out_tok = self._judge_via_tool_calling_selected(
                        task,
                        item,
                        deliverable_path,
                        plan.selected_paths,
                        reference_file_names,
                        routing_decision=runtime_plan.item_decision,
                    )
                    judge_call_count += 1
                    judge_total_latency_ms += ig.judge_latency_ms or 0.0
                    judge_input_tokens += in_tok
                    judge_output_tokens += out_tok
                    judge_cached_tokens += getattr(self, "_last_cached_tokens", 0)
                else:
                    verdict, evidence = pre
                    ig = self._to_item_grade_from_precheck(
                        item, pattern_id, verdict, evidence
                    )
            else:
                self._last_cached_tokens = 0
                ig, in_tok, out_tok = self._judge_via_tool_calling_selected(
                    task,
                    item,
                    deliverable_path,
                    plan.selected_paths,
                    reference_file_names,
                    routing_decision=runtime_plan.item_decision,
                )
                judge_call_count += 1
                judge_total_latency_ms += ig.judge_latency_ms or 0.0
                judge_input_tokens += in_tok
                judge_output_tokens += out_tok
                judge_cached_tokens += getattr(self, "_last_cached_tokens", 0)

            self._attach_target_audit(ig, plan, selection)
            items.append(ig)

        grade = self._aggregate(items, task)
        grade.judge_call_count = judge_call_count
        grade.precheck_count = precheck_count
        grade.judge_total_latency_ms = round(judge_total_latency_ms, 2)
        grade.judge_input_tokens = judge_input_tokens
        grade.judge_output_tokens = judge_output_tokens
        grade.judge_cached_tokens = judge_cached_tokens
        self._aggregate_tool_instrumentation(grade, items)
        self._attach_selection_audit(grade, selection)
        if selection.selection_status == "selection_error":
            grade.error = selection.selection_status
        return grade

    def _runtime_criterion_plan(
        self,
        selection: DeliverableSelection,
        item: RubricItem,
        plan: CriterionTargetPlan,
    ) -> _RuntimeCriterionPlan:
        item_decision = resolve_runtime_routing(
            item.criterion, plan.selected_paths
        )
        target_decisions: dict[str, RoutingDecision] = {}
        raw_visual_paths: list[str] = []
        supported_visual_paths: list[str] = []
        visual_preflight_error: str | None = None
        # One read for the three checks below -- the per-child cap, the
        # single-target cap, and the union cap are all the same bound.
        # ``grade_task`` only routes here once the tool-calling judge exists.
        visual_file_cap = self._tool_judge.visual_file_cap
        if plan.target_scope == "split_children":
            target_by_id = {
                target.target_id: target for target in selection.primary_targets
            }
            for target_id in plan.target_ids:
                target = target_by_id.get(target_id)
                if target is None:
                    continue
                decision = resolve_runtime_routing(item.criterion, target.paths)
                target_decisions[target_id] = decision
                if decision.modality is Modality.VISUAL:
                    raw_visual_paths.extend(target.paths)
                    planned_names, child_error = (
                        self._tool_judge.validate_planned_visual_names(
                            target.paths, visual_file_cap
                        )
                    )
                    supported_visual_paths.extend(planned_names)
                    if child_error is not None and visual_preflight_error is None:
                        visual_preflight_error = (
                            f"{target_id}: {child_error}"
                        )
        elif item_decision.modality is Modality.VISUAL:
            raw_visual_paths.extend(plan.selected_paths)
            supported_visual_paths, visual_preflight_error = (
                self._tool_judge.validate_planned_visual_names(
                    plan.selected_paths, visual_file_cap
                )
            )

        if (
            plan.target_scope == "split_children"
            and supported_visual_paths
            and visual_preflight_error is None
        ):
            # The union is one batched prepass: ``preflight_visual`` renders
            # and perceives every path in it, so the cap applies to the union
            # for the same reason it applies to a bundle. It is checked again
            # inside that call, but not redundantly -- failing here keeps an
            # over-cap item from booking its whole union into the task visual
            # budget and dragging the task's other items down with it.
            supported_visual_paths, visual_preflight_error = (
                self._tool_judge.validate_planned_visual_names(
                    supported_visual_paths, visual_file_cap
                )
            )
        visual_paths = tuple(supported_visual_paths)
        supported_visual_call_count = (
            len(visual_paths) if visual_preflight_error is None else 0
        )
        return _RuntimeCriterionPlan(
            target_plan=plan,
            item_decision=item_decision,
            target_decisions=target_decisions,
            visual_paths=visual_paths,
            visual_preflight_error=visual_preflight_error,
            supported_visual_call_count=supported_visual_call_count,
            requires_visual=bool(raw_visual_paths),
        )

    def _task_visual_budget_error(
        self, runtime_plans: list[_RuntimeCriterionPlan]
    ) -> str | None:
        vision = getattr(self._tool_judge, "vision_perception", None)
        if vision is None:
            return None
        cap = getattr(vision, "call_cap", None)
        if not isinstance(cap, int):
            cap = getattr(vision, "remaining_calls", None)
        if not isinstance(cap, int) or cap < 0:
            return None
        required = sum(
            plan.supported_visual_call_count for plan in runtime_plans
        )
        if required <= cap:
            return None
        return (
            "task_visual_budget_exceeded:"
            f"required_calls={required},cap={cap}"
        )

    @staticmethod
    def _aggregate_tool_instrumentation(
        grade: TaskGrade, items: list[ItemGrade]
    ) -> None:
        """Use per-item runtime instrumentation as the task-level truth."""
        grade.judge_call_count = sum(item.judge_call_count for item in items)
        grade.judge_total_latency_ms = round(sum(
            float(item.judge_latency_ms or 0.0) for item in items
        ), 2)
        grade.judge_input_tokens = sum(item.judge_input_tokens for item in items)
        grade.judge_output_tokens = sum(item.judge_output_tokens for item in items)
        grade.judge_cached_tokens = sum(item.judge_cached_tokens for item in items)
        grade.perception_call_count = sum(
            item.perception_call_count for item in items
        )
        grade.perception_input_tokens = sum(
            item.perception_input_tokens for item in items
        )
        grade.perception_output_tokens = sum(
            item.perception_output_tokens for item in items
        )
        grade.perception_cached_tokens = sum(
            item.perception_cached_tokens for item in items
        )
        grade.perception_total_latency_ms = round(sum(
            item.perception_total_latency_ms for item in items
        ), 2)
        grade.render_call_count = sum(item.render_call_count for item in items)
        grade.render_total_latency_ms = round(sum(
            item.render_total_latency_ms for item in items
        ), 2)
        grade.usage_complete = all(item.usage_complete for item in items)

    def _select_deliverables(
        self, task: TaskRubric, deliverable_path: Path, files: list[Path]
    ) -> DeliverableSelection:
        rel_files = [self._relative_file_name(deliverable_path, path) for path in files]
        return select_deliverables(
            task_id=task.task_id,
            deliverable_files=rel_files,
            reference_files=task.reference_files,
            instruction=task.prompt,
            rubric_items=task.rubric_items,
        )

    def _relative_file_map(self, deliverable_path: Path, files: list[Path]) -> dict[str, Path]:
        mapping: dict[str, Path] = {}
        for path in files:
            rel = self._relative_file_name(deliverable_path, path)
            mapping[rel] = path
            mapping[path.name] = path
        return mapping

    @staticmethod
    def _relative_file_name(deliverable_path: Path, path: Path) -> str:
        try:
            return path.relative_to(deliverable_path).as_posix()
        except ValueError:
            return path.name

    @staticmethod
    def _paths_for_selected(selected_paths: list[str], file_map: dict[str, Path]) -> list[Path]:
        paths: list[Path] = []
        for selected in selected_paths:
            path = file_map.get(selected) or file_map.get(Path(selected).name)
            if path is not None:
                paths.append(path)
        return paths

    def _judge_split_children(
        self,
        task: TaskRubric,
        item: RubricItem,
        selection: DeliverableSelection,
        deliverable_path: Path,
        reference_file_names: list[str],
        plan: CriterionTargetPlan,
        runtime_plan: _RuntimeCriterionPlan,
        preflight_error: str | None = None,
    ) -> tuple[ItemGrade, int, int, int, float, int]:
        child_items: list[ItemGrade] = []
        child_grades: list[dict] = []
        input_tokens = 0
        output_tokens = 0
        cached_tokens = 0
        latency_ms = 0.0
        calls = 0

        target_by_id = {target.target_id: target for target in selection.primary_targets}
        visual_prepass = None
        visual_target_ids = {
            target_id
            for target_id, decision in runtime_plan.target_decisions.items()
            if decision.modality is Modality.VISUAL
        }
        parent_modalities = {
            decision.modality.value
            for decision in runtime_plan.target_decisions.values()
        }
        parent_routing_modality = (
            next(iter(parent_modalities))
            if len(parent_modalities) == 1 else "mixed"
        )
        if preflight_error is not None:
            from core.tool_calling_judge import VisualPrepassResult

            visual_prepass = VisualPrepassResult(judge_error=preflight_error)
        elif runtime_plan.visual_paths:
            visual_prepass = self._tool_judge.preflight_visual(
                item=item,
                deliverable_dir=str(deliverable_path),
                file_names=list(runtime_plan.visual_paths),
            )
            entry_paths = {entry.path for entry in visual_prepass.entries}
            all_children_covered = all(
                bool(expected_paths)
                and set(expected_paths).issubset(entry_paths)
                for target_id in plan.target_ids
                if target_id in target_by_id and target_id in visual_target_ids
                for expected_paths in [
                    self._tool_judge.planned_supported_visual_names(
                        target_by_id[target_id].paths
                    )
                ]
            )
            if visual_prepass.judge_error is None and not all_children_covered:
                visual_prepass.judge_error = (
                    "required_visual_prepass_incomplete_for_split_children"
                )

        if visual_prepass is not None and visual_prepass.judge_error is not None:
            for target_id in plan.target_ids:
                target = target_by_id.get(target_id)
                if target is None:
                    continue
                child_decision = runtime_plan.target_decisions[target_id]
                child_prepass = (
                    visual_prepass.subset(list(target.paths))
                    if child_decision.modality is Modality.VISUAL else None
                )
                child_grades.append({
                    "target_id": target_id,
                    "selected_paths": list(target.paths),
                    "verdict": "judge_error",
                    "awarded_score": 0.0,
                    "evidence": visual_prepass.judge_error[:200],
                    "judge_confidence": None,
                    "routing_modality": child_decision.modality.value,
                    "perception_called": (
                        child_prepass is not None
                        and child_prepass.perception_call_count > 0
                    ),
                    "tools_used": (
                        list(child_prepass.tools_used)
                        if child_prepass is not None else []
                    ),
                    "visual_provenance": (
                        child_prepass.to_provenance()
                        if child_prepass is not None else []
                    ),
                    "score_excluded": True,
                    "judge_call_count": 0,
                    "judge_input_tokens": 0,
                    "judge_output_tokens": 0,
                    "judge_cached_tokens": 0,
                    "perception_call_count": (
                        child_prepass.perception_call_count
                        if child_prepass is not None else 0
                    ),
                    "perception_input_tokens": (
                        child_prepass.perception_input_tokens
                        if child_prepass is not None else 0
                    ),
                    "perception_output_tokens": (
                        child_prepass.perception_output_tokens
                        if child_prepass is not None else 0
                    ),
                    "perception_cached_tokens": (
                        child_prepass.perception_cached_tokens
                        if child_prepass is not None else 0
                    ),
                    "perception_total_latency_ms": round(
                        child_prepass.perception_total_latency_ms, 2
                    ) if child_prepass is not None else 0.0,
                    "render_call_count": (
                        child_prepass.render_call_count
                        if child_prepass is not None else 0
                    ),
                    "render_total_latency_ms": round(
                        child_prepass.render_total_latency_ms, 2
                    ) if child_prepass is not None else 0.0,
                    "usage_complete": (
                        child_prepass.usage_complete
                        if child_prepass is not None else True
                    ),
                })
            ig = ItemGrade(
                rubric_item_id=item.rubric_item_id,
                criterion=item.criterion,
                max_score=item.score,
                awarded_score=0.0,
                verdict="judge_error",
                decided_by="judge",
                required=item.required,
                evidence=visual_prepass.judge_error[:200],
                judge_confidence=None,
                judge_latency_ms=0.0,
                routing_modality=parent_routing_modality,
                perception_called=(visual_prepass.perception_call_count > 0),
                tools_used=list(visual_prepass.tools_used),
                visual_provenance=visual_prepass.to_provenance(),
                child_grades=child_grades,
                score_excluded=True,
                perception_call_count=visual_prepass.perception_call_count,
                perception_input_tokens=visual_prepass.perception_input_tokens,
                perception_output_tokens=visual_prepass.perception_output_tokens,
                perception_cached_tokens=visual_prepass.perception_cached_tokens,
                perception_total_latency_ms=round(
                    visual_prepass.perception_total_latency_ms, 2
                ),
                render_call_count=visual_prepass.render_call_count,
                render_total_latency_ms=round(
                    visual_prepass.render_total_latency_ms, 2
                ),
                usage_complete=visual_prepass.usage_complete,
            )
            self._attach_target_audit(ig, plan, selection)
            return ig, 0, 0, 0, 0.0, 0

        for target_id in plan.target_ids:
            target = target_by_id.get(target_id)
            if target is None:
                continue
            self._last_cached_tokens = 0
            child, in_tok, out_tok = self._judge_via_tool_calling_selected(
                task,
                item,
                deliverable_path,
                list(target.paths),
                reference_file_names,
                visual_prepass=(
                    visual_prepass.subset(list(target.paths))
                    if visual_prepass is not None
                    and target_id in visual_target_ids else None
                ),
                routing_decision=runtime_plan.target_decisions[target_id],
            )
            calls += child.judge_call_count
            input_tokens += in_tok
            output_tokens += out_tok
            cached_tokens += getattr(self, "_last_cached_tokens", 0)
            latency_ms += child.judge_latency_ms or 0.0
            child_items.append(child)
            child_grades.append(
                {
                    "target_id": target_id,
                    "selected_paths": list(target.paths),
                    "verdict": child.verdict,
                    "awarded_score": child.awarded_score,
                    "evidence": child.evidence,
                    "judge_confidence": child.judge_confidence,
                    "routing_modality": child.routing_modality,
                    "perception_called": child.perception_called,
                    "tools_used": list(child.tools_used or []),
                    "visual_provenance": list(child.visual_provenance),
                    "score_excluded": child.score_excluded,
                    "judge_call_count": child.judge_call_count,
                    "judge_input_tokens": child.judge_input_tokens,
                    "judge_output_tokens": child.judge_output_tokens,
                    "judge_cached_tokens": child.judge_cached_tokens,
                    "perception_call_count": child.perception_call_count,
                    "perception_input_tokens": child.perception_input_tokens,
                    "perception_output_tokens": child.perception_output_tokens,
                    "perception_cached_tokens": child.perception_cached_tokens,
                    "perception_total_latency_ms": (
                        child.perception_total_latency_ms
                    ),
                    "render_call_count": child.render_call_count,
                    "render_total_latency_ms": child.render_total_latency_ms,
                    "usage_complete": child.usage_complete,
                }
            )

        if not child_items:
            ig = self._selection_ungraded_item(
                item,
                "selection_error: split_children had no child targets",
                selection,
                plan,
            )
            return ig, input_tokens, output_tokens, calls, latency_ms, cached_tokens

        if any(child.verdict == "judge_error" for child in child_items):
            verdict: Verdict = "judge_error"
            partial = 0.0
        else:
            partials = [self._partial_from_item(child) for child in child_items]
            if any(child.verdict == "fail" for child in child_items):
                partial = min(partials)
            else:
                partial = sum(partials) / len(partials)
            verdict = self._verdict_from_partial(partial)

        evidence = (
            "split_children: see child_grades for "
            f"{len(child_grades)} per-target evidence entries"
        )
        awarded = float(item.score) * partial
        confidence_values = [
            child.judge_confidence for child in child_items if child.judge_confidence is not None
        ]
        confidence = (
            sum(confidence_values) / len(confidence_values)
            if confidence_values else None
        )
        child_modalities = {child.routing_modality for child in child_items}
        routing_modality = (
            child_items[0].routing_modality
            if len(child_modalities) == 1 else "mixed"
        )
        visual_children = [
            child for child in child_items
            if child.routing_modality == Modality.VISUAL.value
        ]
        if visual_children:
            perception_called = all(
                child.perception_called
                and child.verdict != "judge_error"
                and not child.score_excluded
                for child in visual_children
            )
        else:
            perception_called = False
        tools_used = [
            tool
            for child in child_items
            for tool in (child.tools_used or [])
        ]

        ig = ItemGrade(
            rubric_item_id=item.rubric_item_id,
            criterion=item.criterion,
            max_score=item.score,
            awarded_score=awarded,
            verdict=verdict,
            decided_by="judge",
            required=item.required,
            evidence=evidence or "split children produced no evidence",
            judge_confidence=confidence,
            judge_latency_ms=round(latency_ms, 2),
            routing_modality=routing_modality,
            perception_called=perception_called,
            tools_used=tools_used,
            visual_provenance=[
                provenance
                for child in child_items
                for provenance in child.visual_provenance
            ],
            child_grades=child_grades,
            score_excluded=(verdict == "judge_error"),
            judge_call_count=sum(child.judge_call_count for child in child_items),
            judge_input_tokens=sum(child.judge_input_tokens for child in child_items),
            judge_output_tokens=sum(child.judge_output_tokens for child in child_items),
            judge_cached_tokens=sum(child.judge_cached_tokens for child in child_items),
            perception_call_count=sum(
                child.perception_call_count for child in child_items
            ),
            perception_input_tokens=sum(
                child.perception_input_tokens for child in child_items
            ),
            perception_output_tokens=sum(
                child.perception_output_tokens for child in child_items
            ),
            perception_cached_tokens=sum(
                child.perception_cached_tokens for child in child_items
            ),
            perception_total_latency_ms=round(sum(
                child.perception_total_latency_ms for child in child_items
            ), 2),
            render_call_count=sum(child.render_call_count for child in child_items),
            render_total_latency_ms=round(sum(
                child.render_total_latency_ms for child in child_items
            ), 2),
            usage_complete=all(child.usage_complete for child in child_items),
        )
        self._attach_target_audit(ig, plan, selection)
        return ig, input_tokens, output_tokens, calls, latency_ms, cached_tokens

    @staticmethod
    def _partial_from_item(item: ItemGrade) -> float:
        if item.verdict == "pass":
            return 1.0
        if item.verdict == "fail":
            return 0.0
        if item.max_score:
            try:
                return max(0.0, min(1.0, float(item.awarded_score) / float(item.max_score)))
            except ZeroDivisionError:
                return 0.0
        return 0.0

    @staticmethod
    def _verdict_from_partial(partial: float) -> Verdict:
        if partial >= 1.0:
            return "pass"
        if partial <= 0.0:
            return "fail"
        return "partial"

    def _selection_ungraded_item(
        self,
        item: RubricItem,
        evidence: str,
        selection: DeliverableSelection,
        plan: CriterionTargetPlan,
    ) -> ItemGrade:
        ig = ItemGrade(
            rubric_item_id=item.rubric_item_id,
            criterion=item.criterion,
            max_score=item.score,
            awarded_score=0.0,
            verdict="judge_error",
            decided_by="judge",
            required=item.required,
            evidence=self._truncate(
                evidence,
                int(self.config.get("grader", {}).get("evidence_max_chars", 200)),
            ),
            judge_confidence=None,
            judge_latency_ms=0.0,
            score_excluded=True,
        )
        self._attach_target_audit(ig, plan, selection)
        return ig

    def _fail_judge_item(self, item: RubricItem, evidence: str) -> ItemGrade:
        return ItemGrade(
            rubric_item_id=item.rubric_item_id,
            criterion=item.criterion,
            max_score=item.score,
            awarded_score=0.0,
            verdict="fail",
            decided_by="judge",
            required=item.required,
            evidence=self._truncate(
                evidence,
                int(self.config.get("grader", {}).get("evidence_max_chars", 200)),
            ),
            judge_confidence=1.0,
            judge_latency_ms=0.0,
        )

    @staticmethod
    def _attach_target_audit(
        item_grade: ItemGrade,
        plan: CriterionTargetPlan,
        selection: DeliverableSelection,
    ) -> None:
        audit = plan.to_audit_dict(item_grade.rubric_item_id)
        item_grade.target_scope = audit["target_scope"]
        item_grade.target_ids = audit["target_ids"]
        if item_grade.child_grades is None:
            item_grade.child_grades = audit["child_grades"]
        item_grade.aggregation_rule = audit["aggregation_rule"]
        item_grade.selected_paths = audit["selected_paths"]
        item_grade.support_paths_visible = audit["support_paths_visible"]
        item_grade.selection_status = selection.selection_status
        item_grade.selection_error = selection.selection_error

    @staticmethod
    def _attach_selection_audit(
        grade: TaskGrade, selection: DeliverableSelection
    ) -> None:
        grade.selected_deliverables = selection.to_dict()
        grade.reference_files_excluded = list(selection.reference_files_excluded)
        grade.selection_rule = selection.selection_rule
        grade.selection_status = selection.selection_status
        grade.selection_error = selection.selection_error

    def _grade_task_batched(
        self, task: TaskRubric, deliverable_path: Path, files: list[Path]
    ) -> TaskGrade:
        """Batched + tier-routed grading path.

        Differences vs the single-item path:
        - `judge_call_count` counts Responses API invocations (one per batch),
          NOT one per rubric item. A batch of 8 items that succeeds in one
          call contributes 1 to `judge_call_count`. A batch that triggers
          the `chunk_size // 2` fallback contributes 2.
        - Item order in the output matches `task.rubric_items` order.
        - Prechecks still happen first and are NEVER sent to the judge,
          honoring the project's hard rule #2.
        """
        no_deliverables = not deliverable_path.exists() or not files

        # Pre-allocate per-index slots so output order matches input order.
        item_slots: list[Optional[ItemGrade]] = [None] * len(task.rubric_items)
        judge_buckets: dict[str, list[tuple[int, RubricItem]]] = {}

        precheck_count = 0
        judge_call_count = 0
        judge_total_latency_ms = 0.0
        judge_input_tokens = 0
        judge_output_tokens = 0

        # Pass 1 — prechecks (or forced fail when deliverable is absent).
        for idx, item in enumerate(task.rubric_items):
            mode, pattern_id = self._classify(item)
            if no_deliverables:
                if mode == "judge":
                    item_slots[idx] = self._absent_judge_item(item)
                    # absent-judge does not consume an API call
                else:
                    item_slots[idx] = self._fail_precheck_item(item, pattern_id, "deliverable absent")
                    precheck_count += 1
                continue

            if mode == "precheck":
                precheck_count += 1
                pre = self._run_precheck(pattern_id, item, files)
                if pre is None:
                    judge_buckets.setdefault(self._route_to_tier(item), []).append((idx, item))
                else:
                    verdict, evidence = pre
                    item_slots[idx] = self._to_item_grade_from_precheck(
                        item, pattern_id, verdict, evidence
                    )
            else:
                judge_buckets.setdefault(self._route_to_tier(item), []).append((idx, item))

        # Pass 2 — dispatch judge buckets in chunks of `batch_size`.
        for tier_name, entries in judge_buckets.items():
            judge = self._tier_judges.get(tier_name) or self._tier_judges["standard"]
            for chunk_start in range(0, len(entries), self.batch_size):
                chunk = entries[chunk_start : chunk_start + self.batch_size]
                chunk_items = [it for _, it in chunk]
                result = judge.judge_items_batch(task, chunk_items, files)
                judge_call_count += result.num_api_calls
                judge_total_latency_ms += result.total_latency_ms
                judge_input_tokens += result.input_tokens
                judge_output_tokens += result.output_tokens
                for (idx, _), graded_item in zip(chunk, result.items):
                    item_slots[idx] = graded_item

        items: list[ItemGrade] = [it for it in item_slots if it is not None]

        grade = self._aggregate(items, task)
        grade.judge_call_count = judge_call_count
        grade.precheck_count = precheck_count
        grade.judge_total_latency_ms = round(judge_total_latency_ms, 2)
        grade.judge_input_tokens = judge_input_tokens
        grade.judge_output_tokens = judge_output_tokens
        if no_deliverables:
            grade.error = "no_deliverables"
        return grade

    def _list_files(self, deliverable_dir: Path) -> list[Path]:
        absolute = Path(os.path.abspath(deliverable_dir))
        current = Path(absolute.anchor)
        for part in absolute.parts[1:]:
            current = current / part
            if current.is_symlink():
                raise ValueError(
                    f"deliverable path contains a symlink component: {current}"
                )
        if not absolute.exists() or not absolute.is_dir():
            return []
        base = absolute.resolve()
        files: list[Path] = []
        for path in absolute.rglob("*"):
            if path.is_symlink():
                raise ValueError(f"deliverable tree contains a symlink: {path}")
            if path.is_file():
                try:
                    path.resolve().relative_to(base)
                except ValueError as exc:
                    raise ValueError(
                        f"deliverable file escapes task directory: {path}"
                    ) from exc
                files.append(path)
        return sorted(files)

    def _run_precheck(
        self,
        pattern_id: Optional[str],
        item: RubricItem,
        files: list[Path],
    ) -> Optional[tuple[Verdict, str]]:
        return None

    def _judge(
        self, task: TaskRubric, item: RubricItem, files: list[Path]
    ) -> tuple[ItemGrade, int, int]:
        # PR2 task 203 — v2 tool-calling dispatch. Enabled by config
        # (judge.tools.read_deliverable present). Legacy text-extraction
        # path runs only when this dispatch is inactive.
        if self._tool_judge is not None:
            return self._judge_via_tool_calling(task, item, files)

        if not files:
            return self._absent_judge_item(item), 0, 0

        summary = self._summarize_deliverables(files)
        prompt = self._build_prompt(task, item, summary)

        retries = int(self.config.get("grader", {}).get("judge_max_retries", 1))
        for attempt in range(retries + 1):
            try:
                raw, latency_ms, input_tok, output_tok, finish_reason = self._call_judge(prompt)
            except Exception as exc:
                public_error = public_provider_error_text(exc)
                logger.warning(
                    "Judge call failed for %s after retries: %s",
                    item.rubric_item_id,
                    public_error,
                )
                return (
                    ItemGrade(
                        rubric_item_id=item.rubric_item_id,
                        criterion=item.criterion,
                        max_score=item.score,
                        awarded_score=0.0,
                        verdict="judge_error",
                        decided_by="judge",
                        required=item.required,
                        evidence="judge_api_call_failed",
                        judge_confidence=None,
                        judge_latency_ms=0.0,
                        precheck_pattern_id=None,
                        judge_raw_response=(
                            public_error if self._save_raw() else None
                        ),
                    ),
                    0,
                    0,
                )
            parsed = self._safe_parse_judge_json(raw)
            if parsed is None:
                if attempt < retries:
                    prompt += (
                        "\n\nYour last response failed to parse as JSON. "
                        "Return only valid JSON."
                    )
                    continue
                return (
                    ItemGrade(
                        rubric_item_id=item.rubric_item_id,
                        criterion=item.criterion,
                        max_score=item.score,
                        awarded_score=0.0,
                        verdict="judge_error",
                        decided_by="judge",
                        required=item.required,
                        evidence=(
                            "judge_json_parse_failed:truncated_at_max_tokens"
                            if finish_reason in {"length", "incomplete"}
                            else "judge_json_parse_failed"
                        ),
                        judge_confidence=None,
                        judge_latency_ms=latency_ms,
                        judge_raw_response=raw if self._save_raw() else None,
                    ),
                    input_tok,
                    output_tok,
                )

            verdict = str(parsed.get("verdict", "fail")).lower()
            if verdict not in {"pass", "partial", "fail"}:
                verdict = "fail"

            partial = float(parsed.get("partial_score", 0.0) or 0.0)
            partial = max(0.0, min(1.0, partial))
            if verdict == "pass":
                partial = 1.0
            elif verdict == "fail":
                partial = 0.0
            elif partial <= 0.0 or partial >= 1.0:
                verdict = "fail"
                partial = 0.0

            evidence = str(parsed.get("evidence") or "").strip()
            evidence_max = int(self.config.get("grader", {}).get("evidence_max_chars", 200))
            if len(evidence) > evidence_max:
                evidence = evidence[:evidence_max]
            if self.config.get("grader", {}).get("fail_on_missing_evidence", True) and not evidence:
                verdict = "fail"
                partial = 0.0
                evidence = "missing evidence"

            awarded = float(item.score) * partial
            confidence_f = None
            confidence = parsed.get("confidence")
            if confidence is not None:
                try:
                    confidence_f = max(0.0, min(1.0, float(confidence)))
                except (TypeError, ValueError):
                    confidence_f = None

            return (
                ItemGrade(
                    rubric_item_id=item.rubric_item_id,
                    criterion=item.criterion,
                    max_score=item.score,
                    awarded_score=awarded,
                    verdict=verdict,
                    decided_by="judge",
                    required=item.required,
                    evidence=evidence,
                    judge_confidence=confidence_f,
                    judge_latency_ms=latency_ms,
                    precheck_pattern_id=None,
                    judge_raw_response=raw if self._save_raw() else None,
                ),
                input_tok,
                output_tok,
            )

        raise RuntimeError("unreachable")

    def _call_judge(self, prompt: str) -> tuple[str, float, int, int, str]:
        """Call the Responses API judge.

        Returns (text, latency_ms, input_tokens, output_tokens, finish_reason).
        finish_reason is one of "stop", "length", "incomplete", "error", or
        "" when the SDK does not expose one. Used by the caller to tag
        parse failures so the evidence string distinguishes truncation
        from genuine JSON malformation.
        """
        gen = self.config.get("judge", {}).get("generation", {})
        reasoning = self.config.get("judge", {}).get("reasoning", {})
        per_item_max = int(self.config.get("grader", {}).get("per_item_max_output_tokens", 800))
        max_output = int(min(per_item_max, int(gen.get("max_output_tokens", 4096))))

        retry_cfg = self.config.get("tpm_guard", {}).get("retry_on_429", {})
        max_retries = int(retry_cfg.get("max_retries", 3)) if retry_cfg.get("enabled", True) else 0
        backoff = float(retry_cfg.get("initial_backoff_sec", 2))
        factor = float(retry_cfg.get("exponential_factor", 2.0))

        for attempt in range(max_retries + 1):
            self._apply_tpm_delay()
            start = time.time()
            try:
                # Azure OpenAI Responses API for reasoning models (e.g.,
                # gpt-5.4-pro) does NOT accept temperature/seed. These values
                # are kept in config as reproducibility metadata only and
                # stamped into the grade JSON, but are not passed to the SDK.
                response = self.client.responses.create(
                    model=self.model,
                    input=prompt,
                    max_output_tokens=max_output,
                    reasoning={"effort": reasoning.get("effort", "high")},
                )
                latency_ms = (time.time() - start) * 1000
                text = getattr(response, "output_text", "") or ""
                usage = getattr(response, "usage", None)
                input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
                output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
                finish_reason = _extract_finish_reason(response, max_output, output_tokens)
                return text, latency_ms, input_tokens, output_tokens, finish_reason
            except Exception as exc:
                status = getattr(exc, "status_code", None)
                if status in (429, 500, 502, 503, 504) and attempt < max_retries:
                    time.sleep(backoff)
                    backoff *= factor
                    continue
                raise

        raise RuntimeError("unreachable")

    def _apply_tpm_delay(self) -> None:
        if self._min_delay_seconds <= 0:
            return
        now = time.time()
        if self._last_judge_call_at is not None:
            elapsed = now - self._last_judge_call_at
            remaining = self._min_delay_seconds - elapsed
            if remaining > 0:
                time.sleep(remaining)
                now = time.time()
        self._last_judge_call_at = now

    def _summarize_deliverables(self, files: list[Path]) -> list[dict]:
        max_chars = int(self.config.get("grader", {}).get("deliverable_extract_max_chars", 4000))
        out: list[dict] = []
        for path in files:
            text = read_reference_file(str(path))
            if len(text) > max_chars:
                text = text[:max_chars] + "..."
            out.append(
                {
                    "filename": path.name,
                    "size_bytes": path.stat().st_size,
                    "mime_type": path.suffix.lower().lstrip(".") or "unknown",
                    "content": text,
                }
            )
        return out

    def _build_prompt(
        self,
        task: TaskRubric,
        item: RubricItem,
        deliverable_summaries: list[dict],
    ) -> str:
        task_prompt_max = int(self.config.get("grader", {}).get("task_prompt_truncate_chars", 500))
        prompt = self.prompt_template
        prompt = prompt.replace("{{sector}}", task.sector)
        prompt = prompt.replace("{{occupation}}", task.occupation)
        prompt = prompt.replace(
            "{{task_prompt_truncated_500}}", self._truncate(task.prompt, task_prompt_max)
        )
        prompt = prompt.replace("{{rubric_item_id}}", item.rubric_item_id)
        prompt = prompt.replace("{{max_score}}", str(item.score))
        prompt = prompt.replace("{{required}}", self._json_scalar(item.required))
        prompt = prompt.replace("{{criterion}}", item.criterion)

        block = ""
        for d in deliverable_summaries:
            block += (
                f"### File: {d['filename']} ({d['size_bytes']} bytes, {d['mime_type']})\n"
                f"```\n{d['content']}\n```\n"
            )

        prompt = re.sub(
            r"\{\{#each deliverable_files\}\}[\s\S]*?\{\{/each\}\}",
            block.strip(),
            prompt,
            flags=re.MULTILINE,
        )
        return prompt

    def _to_item_grade_from_precheck(
        self,
        item: RubricItem,
        pattern_id: Optional[str],
        verdict: Verdict,
        evidence: str,
    ) -> ItemGrade:
        evidence = self._truncate(
            evidence.strip(), int(self.config.get("grader", {}).get("evidence_max_chars", 200))
        )
        if verdict == "pass":
            awarded = float(item.score)
        elif verdict == "partial":
            awarded = float(item.score) * 0.5
        else:
            awarded = 0.0
        return ItemGrade(
            rubric_item_id=item.rubric_item_id,
            criterion=item.criterion,
            max_score=item.score,
            awarded_score=awarded,
            verdict=verdict,
            decided_by="precheck",
            required=item.required,
            evidence=evidence,
            precheck_pattern_id=pattern_id,
        )

    @staticmethod
    def _aggregate(items: list[ItemGrade], task: TaskRubric) -> TaskGrade:
        # PR1 task 100 — sign-aware model_did_right normalization.
        # GDPVal rubric items can carry negative max_score (penalty/anti-
        # criteria). For those, verdict='pass' means the bad thing HAPPENED,
        # not the model satisfied something good. Normalize to a unified
        # 'did right' flag so downstream metrics (critical_item_pass_rate
        # in PR1 task 101) treat positive and negative items consistently.
        for it in items:
            if it.verdict == "judge_error":
                it.score_excluded = True
                it.model_did_right = False
            elif it.score_excluded:
                it.model_did_right = True
            elif (it.max_score or 0) < 0:
                it.model_did_right = (it.verdict != "pass")
            else:
                it.model_did_right = (it.verdict == "pass")

        scored_items = [it for it in items if not it.score_excluded]
        total_awarded = sum(it.awarded_score for it in scored_items)
        total_max = sum(max(0, it.max_score) for it in scored_items)
        pct = (total_awarded / total_max * 100.0) if total_max else 0.0
        # PR1 task 102 — preserve un-clamped pct for diagnostics BEFORE the
        # [0,100] clamp below. pct_raw can be < 0 when negative penalties
        # dominate (catastrophic violation), or > 100 if a judge over-awards.
        # total_max now always >= 0 by virtue of rubric_loader's positive-only
        # sum (task 102 rubric_loader change), so the only edge case is
        # total_max == 0 (no positive items in rubric — degenerate task).
        pct_raw = pct
        if total_max == 0 and total_awarded != 0:
            # No positive denominator but the model still received some
            # (necessarily negative) score. Flag rather than silently zero.
            logger.warning(
                "task %s has total_max=0 (no positive rubric items) but "
                "total_awarded=%s; reporting pct=0 and pct_raw=%s",
                task.task_id, total_awarded, total_awarded,
            )
            pct_raw = float(total_awarded)

        # Clamp pct to [0, 100] for grade.schema.json v1.0 compatibility
        # (schema enforces minimum=0, maximum=100). Anomalies (e.g. rubric
        # items with negative max_score from penalty-style criteria, or
        # judge-awarded scores exceeding the listed max) remain visible
        # in the raw `total_awarded` / `total_max` fields; the clamp only
        # affects the headline pct. Without this clamp a single anomalous
        # task crashes the next partial_save schema validation and exits
        # the whole grading run silently (observed: exp003 task #44 = 108.9%,
        # task #45 = 229.3% → partial save #5 at task 50 fails).
        pct = max(0.0, min(100.0, pct))
        # PR1 task 101 — critical_fail uses magnitude + sign-aware did_right.
        # Was: `bool(it.required) and verdict in ('fail','judge_error')` — but
        # `it.required` is null across all observed GDPVal rubrics, so this
        # branch never fired and critical_fail was effectively always False.
        # Now: any critical-magnitude item where the model did NOT do the
        # right thing (covers both positive must-haves and negative penalties).
        critical_fail = any(
            _is_critical_item(it.max_score) and not it.model_did_right
            for it in scored_items
        )
        return TaskGrade(
            task_id=task.task_id,
            sector=task.sector,
            occupation=task.occupation,
            items=items,
            total_awarded=round(total_awarded, 4),
            total_max=total_max,
            pct=round(pct, 2),
            critical_fail=critical_fail,
            gold_referenced=bool(task.gold_deliverable_files),
            judge_call_count=0,
            precheck_count=0,
            judge_total_latency_ms=0.0,
            judge_input_tokens=0,
            judge_output_tokens=0,
            error=("all_items_score_excluded" if items and not scored_items else None),
            pct_raw=round(pct_raw, 2),
        )

    def _absent_judge_item(self, item: RubricItem) -> ItemGrade:
        return ItemGrade(
            rubric_item_id=item.rubric_item_id,
            criterion=item.criterion,
            max_score=item.score,
            awarded_score=0.0,
            verdict="fail",
            decided_by="judge",
            required=item.required,
            evidence="deliverable absent",
            judge_confidence=1.0,
            judge_latency_ms=0.0,
        )

    def _fail_precheck_item(
        self,
        item: RubricItem,
        pattern_id: Optional[str],
        evidence: str,
    ) -> ItemGrade:
        return ItemGrade(
            rubric_item_id=item.rubric_item_id,
            criterion=item.criterion,
            max_score=item.score,
            awarded_score=0.0,
            verdict="fail",
            decided_by="precheck",
            required=item.required,
            evidence=evidence,
            precheck_pattern_id=pattern_id,
        )

    @staticmethod
    def _safe_parse_judge_json(raw_text: str) -> Optional[dict]:
        text = raw_text.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            text = text[start : end + 1]
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _read_prompt_template(path: str) -> str:
        return Path(path).read_text(encoding="utf-8")

    # ------------------------------------------------------------------
    # PR2 task 203 — tool-calling judge helpers
    # ------------------------------------------------------------------

    def _is_tool_calling_config(self) -> bool:
        """True when the grading config opts into the v2 tool-calling path.

        Trigger: ``judge.tools.read_deliverable`` present. We look at the
        *presence* of the block, not its content, so the v2 default
        config and any user override both activate.
        """
        return bool(
            (self.config.get("judge") or {})
            .get("tools", {})
            .get("read_deliverable")
        )

    def _build_tool_calling_judge(self):
        """Instantiate a ``ToolCallingJudge`` from this Grader's config.

        Pulls the v2 prompt template path from ``prompt.tool_template``
        (falls back to the standard ``prompts/grader_judge_v2.md`` sibling
        of the configured v1 template).
        """
        from core.tool_calling_judge import ToolCallingJudge  # local; avoid cycle
        from core.tool_calling_judge import resolve_visual_file_cap

        judge_cfg = self.config.get("judge", {})
        tool_prompt_path = resolve_tool_prompt_path(self.config)
        tool_prompt = self._read_prompt_template(tool_prompt_path)
        tool_prompt_version = self._extract_prompt_version(tool_prompt)
        self.prompt_version = tool_prompt_version
        runtime = self.config.get("_runtime") or {}
        prompt_cache_key = json.dumps(
            (
                str(runtime.get("experiment_id") or "unknown_experiment"),
                str(self.model),
                str(
                    runtime.get("rubric_sha")
                    or self.config.get("rubric", {}).get("revision")
                    or "unknown_rubric"
                ),
                tool_prompt_version,
            ),
            separators=(",", ":"),
        )

        per_item_cap = int(
            (judge_cfg.get("tools", {}).get("read_deliverable", {})
             .get("per_item_call_cap", 8))
        )
        max_iter = int(
            (judge_cfg.get("tools", {}).get("read_deliverable", {})
             .get("max_iterations", 10))
        )
        model_read_ops = tuple(
            (judge_cfg.get("tools", {}).get("read_deliverable", {})
             .get("ops") or [])
        )

        # PR3 (0531) perception wiring. Read judge.perception.{visual,audio}
        # and instantiate the sub-judges, sharing this Grader's Azure client.
        # Previously these blocks were validated by step8 but never wired,
        # so visual/audio criteria were silently graded by the text judge.
        vision_perception = None
        audio_perception = None
        perception_cfg = judge_cfg.get("perception") or {}
        vis_cfg = perception_cfg.get("visual") or {}
        aud_cfg = perception_cfg.get("audio") or {}
        if vis_cfg.get("model") is not None or vis_cfg.get("deployment") is not None:
            from core.perception.vision import VisionPerception  # local import
            vision_deployment = canonical_deployment(
                vis_cfg, "judge.perception.visual"
            )
            vision_perception = VisionPerception(
                client=self.client,
                deployment=vision_deployment,
                call_cap=int(vis_cfg.get("call_cap_per_task", 5)),
                reasoning_effort=vis_cfg.get(
                    "reasoning_effort",
                    (judge_cfg.get("reasoning") or {}).get("effort", "medium"),
                ),
                before_upstream_call=self._apply_tpm_delay,
            )
        if aud_cfg.get("model") is not None or aud_cfg.get("deployment") is not None:
            from core.perception.audio import AudioPerception  # local import
            audio_deployment = canonical_deployment(
                aud_cfg, "judge.perception.audio"
            )
            audio_perception = AudioPerception(
                client=self.client,
                deployment=audio_deployment,
                call_cap=int(aud_cfg.get("call_cap_per_task", 3)),
                trim_seconds=int(aud_cfg.get("trim_seconds", 30)),
            )

        return ToolCallingJudge(
            client=self.client,
            model=self.model,
            prompt_template=tool_prompt,
            reasoning_effort=(judge_cfg.get("reasoning") or {})
                .get("effort", "medium"),
            max_output_tokens=int((judge_cfg.get("generation") or {})
                .get("max_output_tokens", 2400)),
            per_item_tool_call_cap=per_item_cap,
            max_iterations=max_iter,
            finalization_retries=int(
                self.config.get("grader", {}).get("judge_max_retries", 1)
            ),
            finalization_reasoning_effort=(judge_cfg.get("generation") or {})
                .get("finalization_reasoning_effort", "low"),
            model_read_ops=model_read_ops,
            vision_perception=vision_perception,
            audio_perception=audio_perception,
            prompt_cache_key=prompt_cache_key,
            before_upstream_call=self._apply_tpm_delay,
            visual_file_cap=resolve_visual_file_cap(judge_cfg),
        )

    def _judge_via_tool_calling(
        self, task: TaskRubric, item: RubricItem, files: list[Path]
    ) -> tuple[ItemGrade, int, int]:
        if not files:
            self._last_cached_tokens = 0
            return self._absent_judge_item(item), 0, 0
        deliverable_dir = str(files[0].parent)
        file_names = [f.name for f in files]
        return self._judge_via_tool_calling_selected(
            task,
            item,
            Path(deliverable_dir),
            file_names,
            reference_file_names=[],
        )

    def _judge_via_tool_calling_selected(
        self,
        task: TaskRubric,
        item: RubricItem,
        deliverable_dir: Path,
        file_names: list[str],
        reference_file_names: list[str],
        visual_prepass=None,
        routing_decision: RoutingDecision | None = None,
    ) -> tuple[ItemGrade, int, int]:
        if not file_names:
            self._last_cached_tokens = 0
            return self._absent_judge_item(item), 0, 0
        result = self._tool_judge.judge_item(
            task=task, item=item,
            deliverable_dir=str(deliverable_dir),
            file_names=file_names,
            reference_file_names=reference_file_names,
            visual_prepass=visual_prepass,
            routing_decision=routing_decision,
        )
        # PR3 Step 0 — expose cached input tokens via instance side-channel.
        # Avoids changing the (ItemGrade, in_tok, out_tok) tuple shape used
        # by both v1 and v2 grader dispatch paths.
        self._last_cached_tokens = result.cached_tokens
        # PR3 fix \u2014 judge_error strings can exceed the schema's 200-char
        # evidence cap (e.g. an Azure BadRequestError). Truncate so the
        # final grade JSON still validates.
        _ev_max = int(self.config.get("grader", {}).get("evidence_max_chars", 200))
        _ev = (result.evidence or (result.judge_error or ""))[:_ev_max]
        ig = ItemGrade(
            rubric_item_id=item.rubric_item_id,
            criterion=item.criterion,
            max_score=item.score,
            awarded_score=result.awarded_score,
            verdict=result.verdict,
            decided_by="judge",
            required=item.required,
            evidence=_ev,
            judge_confidence=result.confidence,
            judge_latency_ms=round(result.latency_ms, 2),
            judge_raw_response=result.raw_text if self._save_raw() else None,
            routing_modality=result.routing_modality,
            perception_called=result.perception_called,
            tools_used=list(result.tools_used),
            visual_provenance=list(result.visual_provenance),
            score_excluded=result.score_excluded,
            judge_call_count=result.main_api_call_count,
            judge_input_tokens=result.input_tokens,
            judge_output_tokens=result.output_tokens,
            judge_cached_tokens=result.cached_tokens,
            perception_call_count=result.perception_call_count,
            perception_input_tokens=result.perception_input_tokens,
            perception_output_tokens=result.perception_output_tokens,
            perception_cached_tokens=result.perception_cached_tokens,
            perception_total_latency_ms=round(
                result.perception_total_latency_ms, 2
            ),
            render_call_count=result.render_call_count,
            render_total_latency_ms=round(result.render_total_latency_ms, 2),
            usage_complete=result.usage_complete,
        )
        return ig, result.input_tokens, result.output_tokens


    @staticmethod
    def _extract_prompt_version(prompt_text: str) -> str:
        m = re.search(r"prompt_version:\s*([A-Za-z0-9_.-]+)", prompt_text)
        return m.group(1) if m else "v1"

    @staticmethod
    def _truncate(value: str, max_chars: int) -> str:
        if len(value) <= max_chars:
            return value
        return value[:max_chars] + "..."

    @staticmethod
    def _json_scalar(value: object) -> str:
        return json.dumps(value)

    def _save_raw(self) -> bool:
        return bool(self.config.get("grader", {}).get("save_raw_responses", False))
