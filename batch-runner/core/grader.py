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
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Callable, Iterable, Literal, Optional

from core.azure_ai_clients import (
    AzureAIClientFactory,
    AzureAIWorkload,
    canonical_deployment,
    grader_route_workloads,
)
from core.cost_receipts import STAGE_GRADING, STAGE_PERCEPTION
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
from core.task_checkpoint import (
    CheckpointRejected,
    TaskProgress,
    TaskProgressDraft,
)
from core.tools import has_audio_content, has_extractable_text

logger = logging.getLogger(__name__)

DEFAULT_GRADER_TIMEOUT = 600
DEFAULT_GRADER_API_VERSION = "2025-04-01-preview"


class GradingDeadlineExceeded(RuntimeError):
    """The run ran out of time part-way through a task.

    Raised out of ``grade_task`` rather than returned, because a half-marked
    task must not become a grade. Its remaining items would be missing, and a
    task missing items scores lower than one that was never attempted — a
    silent penalty for having been unlucky with the clock. The driver drops
    the task, keeps everything already finished, and lets the next chunk mark
    it from the beginning.

    The alternative — no check at all — is what shard 4 of the first Stage 3
    attempt did: one task held the loop for four hours past a four-hour
    budget, the job hit ``timeout-minutes`` at five hours twenty, and six
    finished tasks went down with it.

    ``progress`` carries what the task had finished when the clock ran out,
    for the one task where "mark it from the beginning" does not terminate:
    ``9e39df84`` is longer than a chunk, so four paid attempts each stopped
    around item 50 of 57 and each began again at item one. The driver decides
    whether to keep it — the exception's own contract is unchanged, and a
    driver that ignores ``progress`` behaves exactly as before.
    """

    def __init__(
        self, *args, progress: "TaskProgressDraft | None" = None
    ) -> None:
        super().__init__(*args)
        self.progress = progress


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
    #: Why a perception sub-judge could not answer, when that is what ended
    #: the item. ``evidence`` carries the kind of failure and this carries the
    #: cause, because a run that produced fifteen listening errors and two
    #: distinct strings between them cannot be acted on.
    perception_error_detail: Optional[str] = None
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
    #: This item wanted pictures, the task could not afford them all, and it
    #: was put back on the path it would have taken before the unreadable-file
    #: escalation existed. The verdict below is a real verdict, read off a
    #: readable file -- but it was read where a picture was preferred, and a
    #: reader comparing it against another run needs to know that.
    visual_budget_downgraded: bool = False


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
    #: The visual budget this task could not meet, when it was met by giving
    #: up pictures rather than by giving up the task. ``None`` on every task
    #: that never came near the cap. The string is the shortfall as it was
    #: originally measured, so the size of what was given up is on the record
    #: even though the items below carry real scores.
    visual_budget_fallback: Optional[str] = None
    #: How much of the rubric was never read, and what the task scores when
    #: that unread weight is counted against it rather than removed.
    #:
    #: ``pct`` above divides by ``total_max``, which is the weight of the
    #: items that *were* judged -- so an item the judge failed on leaves the
    #: denominator as well as the numerator, and the percentage goes up. The
    #: two fields below say by how much, and the third says what the task
    #: would have scored had it not. They are equal to ``pct`` and zero on
    #: every task the grader read all the way through, which is most of them;
    #: they exist for the ones it did not.
    #:
    #: ``pct_full_denominator`` is ``None`` only on a record graded before
    #: these existed, where the movement cannot be recovered from the field
    #: alone. It can still be recomputed from ``items``.
    score_excluded_items: int = 0
    score_excluded_max: float = 0.0
    pct_full_denominator: Optional[float] = None


@dataclass(frozen=True)
class _RuntimeCriterionPlan:
    target_plan: CriterionTargetPlan
    item_decision: RoutingDecision
    target_decisions: dict[str, RoutingDecision]
    visual_paths: tuple[str, ...]
    visual_preflight_error: Optional[str]
    supported_visual_call_count: int
    requires_visual: bool
    #: Set only on a plan that was rebuilt to fit inside the task visual
    #: budget, and only on the items the rebuild actually moved off the
    #: render path. Carried onto the item's grade so the payload says which
    #: verdicts were reached without the pictures they asked for.
    visual_budget_downgraded: bool = False


class Grader:
    def __init__(
        self,
        config: dict,
        rubric_loader,
        *,
        client=None,
        client_factory: AzureAIClientFactory | None = None,
        cost_recorder=None,
        should_stop: Optional[Callable[[], bool]] = None,
    ):
        self.config = config
        self.rubric_loader = rubric_loader

        # The driver's answer to "should I still be working?", consulted
        # between units of work inside a task rather than only between tasks.
        # See ``_check_should_stop``.
        self.should_stop = should_stop

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

        # Per-task cost receipts (task 0828). Metering is opt-in: with no
        # recorder the two attributes below are the bare client and nothing
        # is written, which is what keeps an unmetered run reporting an
        # absent ledger rather than a smaller bill.
        #
        # Two wrappers, one connection. The judge's own calls follow whatever
        # stage is in scope; the perception readers share this client but are
        # pinned to their own stage, so a visual read taken mid-grading lands
        # in its own component of the marking receipt instead of disappearing
        # into the judge's.
        self._cost_recorder = cost_recorder
        self._perception_client = client
        if cost_recorder is not None:
            self.client = cost_recorder.meter(
                client, provider="azure", model=deployment
            )
            self._perception_client = cost_recorder.meter(
                client, provider="azure", stage=STAGE_PERCEPTION
            )

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
            #: Per-task memos for the two routing probes, reset at the top of
            #: every ``grade_task``. ``grader_preflight`` builds a Grader
            #: through ``object.__new__`` and never runs this method, so it
            #: sets its own; there is no lazy default on purpose, because a
            #: missing memo should surface as an error rather than as a probe
            #: silently repeated once per rubric item.
            self._text_layer_cache: dict[str, bool | None] = {}
            self._audio_content_cache: dict[str, bool | None] = {}
            #: Set while a task is being marked, to a zero-argument callable
            #: returning what that task has finished so far. Read only by
            #: ``_check_should_stop``, on its way to raising. ``None`` outside
            #: a task, and read with a default because the ``object.__new__``
            #: path above never gets here — an absent supplier means "no
            #: checkpoint", which is the behaviour that predates it.
            self._progress_draft: Optional[Callable[[], TaskProgressDraft]] = None

            # Task 207 — the tool-calling judge is the only grading path.
            # The legacy text-extract / batch / tier-routing paths are gone,
            # so a config that does not opt in has no judge at all. Fail
            # here, loudly, rather than at the first graded item: a config
            # that silently took a different path is exactly how two runs
            # end up with incomparable grades.
            if not self._is_tool_calling_config():
                raise ValueError(
                    "grading config must define judge.tools.read_deliverable; "
                    "the legacy text-extract grader was removed in task 207. "
                    "Port the config to the v2 tool-calling shape (see "
                    "grading_configs/default_v2_sol_max.yaml)."
                )
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
            self._perception_client = None

    def __enter__(self) -> "Grader":
        return self

    def __exit__(self, _exc_type, _exc, _traceback) -> None:
        self.close()

    @staticmethod
    def _classify(item: RubricItem) -> tuple[str, Optional[str]]:
        return "judge", None

    def _check_should_stop(self, task_id: str, unit: str) -> None:
        """Give up on this task if the driver says the run is out of time.

        Called at the top of the two loops that can each run for hours: the
        rubric items of a task, and the split children of one item. Neither is
        bounded by anything but the deliverable — a task with forty children
        and twenty items makes eight hundred judge conversations, and each of
        those may retry — so a budget consulted only between tasks is a budget
        that a single unlucky task can ignore completely.

        The check sits *before* the work, so the unit that would have started
        is never charged for. What has already been spent on this task is
        spent; the loss is bounded at one task and the driver keeps the rest.
        """
        if self.should_stop is None or not self.should_stop():
            return
        draft = getattr(self, "_progress_draft", None)
        raise GradingDeadlineExceeded(
            f"grading deadline reached during {task_id} while starting {unit}",
            progress=draft() if callable(draft) else None,
        )

    @staticmethod
    def _restore_items(progress: TaskProgress, task: TaskRubric) -> list[ItemGrade]:
        """Rebuild the items an earlier chunk finished, as objects again.

        Reconstruction is strict on purpose. ``ItemGrade`` is inside the
        graded source fingerprint, so a checkpoint written against a different
        shape has already been refused by ``load_checkpoint``; if one ever
        reaches here anyway, it must announce itself rather than arrive as a
        ``TypeError`` from a dataclass constructor forty frames from anything
        that explains it.
        """
        restored: list[ItemGrade] = []
        for position, stored in enumerate(progress.completed_items):
            try:
                restored.append(ItemGrade(**stored))
            except TypeError as exc:
                raise CheckpointRejected(
                    f"{task.task_id} item {position} does not fit the current "
                    f"ItemGrade: {exc}"
                ) from exc
        return restored

    def grade_task(
        self,
        task: TaskRubric,
        deliverable_dir: str,
        *,
        resume_from: Optional[TaskProgress] = None,
    ) -> TaskGrade:
        deliverable_path = Path(deliverable_dir)
        files = self._list_files(deliverable_path)

        # PR3 (0531) — reset per-task perception call caps before each task.
        # __init__ guarantees _tool_judge exists, so this is the only path.
        self._tool_judge.reset_perception()
        if resume_from is not None:
            # The reset above still has to happen: the sub-judges cache images
            # and transcripts per task, and carrying the previous task's into
            # this one is a different bug. What must survive it is the spend.
            # Caps are per task; an unlucky task that took three chunks must
            # not get three times the looking its neighbour got.
            self._tool_judge.restore_perception_spend(
                resume_from.perception_spent
            )
        # Every rubric item of a task asks about the same files, so the
        # routing probes are answered once per file per task rather than
        # once per item. Cleared here for the same reason the caps are.
        #
        # Not restored on resume, unlike the caps: these two probes read local
        # bytes, cost nothing and answer the same way every time, so paying
        # them again changes the clock and not the marking.
        self._text_layer_cache = {}
        self._audio_content_cache = {}
        try:
            if self._cost_recorder is None:
                return self._grade_task_with_selector(
                    task, deliverable_path, files, resume_from=resume_from
                )

            # Everything this call spends — judge turns, retries inside the
            # judge, and the perception reads it delegates — belongs to one
            # task's marking bill.
            #
            # A task spanning chunks opens this window once per chunk and so
            # leaves more than one run of ledger rows. That is right and it
            # adds up: the ledger is keyed by grade file rather than by
            # process, a resumed chunk reopens it, and ``receipt_for`` sums
            # every row a task id has regardless of which round wrote it.
            with self._cost_recorder.attributed(
                task_id=task.task_id, stage=STAGE_GRADING
            ):
                return self._grade_task_with_selector(
                    task, deliverable_path, files, resume_from=resume_from
                )
        finally:
            # The draft closes over this task's items. Left installed, it
            # would hand the next task a stale one.
            self._progress_draft = None

    def _grade_task_with_selector(
        self,
        task: TaskRubric,
        deliverable_path: Path,
        files: list[Path],
        *,
        resume_from: Optional[TaskProgress] = None,
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
                deliverable_path,
            )
            for item in task.rubric_items
        ]
        visual_budget_error = self._task_visual_budget_error(runtime_plans)
        visual_budget_fallback: str | None = None
        if visual_budget_error:
            runtime_plans, visual_budget_error, visual_budget_fallback = (
                self._relax_to_fit_visual_budget(
                    selection,
                    task,
                    runtime_plans,
                    deliverable_path,
                    visual_budget_error,
                )
            )

        items: list[ItemGrade] = []
        judge_call_count = 0
        precheck_count = 0
        judge_total_latency_ms = 0.0
        judge_input_tokens = 0
        judge_output_tokens = 0
        judge_cached_tokens = 0
        resumed_at = 0

        if resume_from is not None:
            items = self._restore_items(resume_from, task)
            resumed_at = len(items)
            # Only the prechecks. The other five tallies here are handed to
            # ``_aggregate_tool_instrumentation`` below and then overwritten
            # by it, because per-item instrumentation is the task-level truth
            # — and those per-item fields are inside the restored ``items``,
            # so an earlier chunk's judge calls, tokens and latency come back
            # on their own. A precheck resolves an item without a judge call
            # and is counted nowhere per-item, so it is the one number that
            # would be lost.
            precheck_count = resume_from.precheck_count
            logger.info(
                "%s: resuming after %d/%d items from checkpoint",
                task.task_id,
                resumed_at,
                len(task.rubric_items),
            )

        def draft() -> TaskProgressDraft:
            """This task's progress, as of right now. Never a grade.

            Built only on the way out through ``GradingDeadlineExceeded``.
            ``items`` here is a prefix of the rubric in canonical order — the
            loop appends one per iteration and never skips — which is the
            shape ``load_checkpoint`` insists on before it will resume from
            one.
            """
            return TaskProgressDraft(
                completed_items=tuple(asdict(ig) for ig in items),
                perception_spent=self._tool_judge.perception_spend(),
                precheck_count=precheck_count,
            )

        # Positional, not by item id: ``load_checkpoint`` has already proved
        # the stored items are a prefix of this rubric in this order, and
        # slicing says so directly. Skipping by a set of ids would quietly do
        # the wrong thing for a rubric that repeats one.
        remaining = list(
            zip(task.rubric_items[resumed_at:], runtime_plans[resumed_at:])
        )

        # Installed rather than caught at the call sites. ``_check_should_stop``
        # is the only thing that raises the deadline, and it is called from
        # both this loop and the split-children loop several frames down;
        # attaching the draft where the exception is born covers both, and the
        # next one someone adds. ``grade_task`` clears it on the way out.
        self._progress_draft = draft

        for item, runtime_plan in remaining:
            self._check_should_stop(task.task_id, f"item {item.rubric_item_id}")
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
        grade.visual_budget_fallback = visual_budget_fallback
        for item_grade, runtime_plan in zip(items, runtime_plans):
            # Positional for the same reason the loop above is: ``items`` is a
            # prefix of the rubric in canonical order, restored chunks
            # included, and ``runtime_plans`` is built from the same list.
            if runtime_plan.visual_budget_downgraded:
                item_grade.visual_budget_downgraded = True
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
        elif not deliverable_path.exists() or not files:
            # Task 207 — carried over from the removed legacy paths, which
            # were the only place this was ever set. A task with nothing to
            # grade must stay distinguishable from one that graded to zero.
            grade.error = "no_deliverables"
        return grade

    def _any_selected_path(
        self,
        deliverable_path: Path,
        paths: Iterable[str],
        probe: Callable[[Path], "bool | None"],
        memo: dict[str, bool | None],
    ) -> bool | None:
        """Ask one yes/no question of a set of files, once per file per task.

        ``True`` as soon as one file answers yes, ``False`` only if every one
        was examined and none did, and ``None`` the moment a file cannot be
        answered for. Routing acts on the definite answers alone, so a file
        the probe cannot speak for must not be allowed to look like a no.

        The probes are I/O, which is why they live here and not in
        ``grader_routing``: that module is pure and stays that way.
        """
        seen_unknown = False
        seen_any = False
        for name in paths:
            if not isinstance(name, str) or not name:
                continue
            seen_any = True
            if name not in memo:
                memo[name] = probe(deliverable_path / name)
            answer = memo[name]
            if answer:
                return True
            if answer is None:
                seen_unknown = True
        if not seen_any or seen_unknown:
            return None
        return False

    def _selected_paths_have_text(
        self, deliverable_path: Path, paths: Iterable[str]
    ) -> bool | None:
        """Does any of these files yield a single character of text?"""
        return self._any_selected_path(
            deliverable_path, paths, has_extractable_text, self._text_layer_cache
        )

    def _some_selected_path_lacks_text(
        self, deliverable_path: Path, paths: Iterable[str]
    ) -> bool | None:
        """Is any one of these files unable to yield a character of text?

        The question above cannot answer this one. It stops at the first file
        that yields text and reports the whole set as readable, so a picture
        selected next to a readable document disappears behind it. Asking per
        file is what lets the picture be looked at.

        Same discipline as its sibling: a measured ``False`` from one file is
        enough to say ``True`` here, ``None`` when no file gave a definite no
        and at least one could not be answered for, and ``False`` only when
        every file was examined and every one of them had text. It shares the
        text-layer memo, so the extra question costs no extra reading.
        """
        seen_any = False
        seen_unknown = False
        for name in paths:
            if not isinstance(name, str) or not name:
                continue
            seen_any = True
            if name not in self._text_layer_cache:
                self._text_layer_cache[name] = has_extractable_text(
                    deliverable_path / name
                )
            answer = self._text_layer_cache[name]
            if answer is False:
                return True
            if answer is None:
                seen_unknown = True
        if not seen_any or seen_unknown:
            return None
        return False

    def _selected_paths_have_audio(
        self, deliverable_path: Path, paths: Iterable[str]
    ) -> bool | None:
        """Is any of these files audio, or an archive that holds audio?"""
        return self._any_selected_path(
            deliverable_path, paths, has_audio_content, self._audio_content_cache
        )

    def _paths_without_text(
        self, deliverable_path: Path, paths: Iterable[str]
    ) -> tuple[str, ...]:
        """Which of these files measurably yield no text at all.

        The question above answers *whether* one of them does; this answers
        *which*, because that is what decides where the pictures are spent. A
        file the probe cannot speak for is not in the answer, for the same
        reason it cannot escalate: rendering on a guess is what the ``None``
        rule exists to prevent. Order follows the selection so the render set
        reads the way the deliverable does, and shares the text-layer memo, so
        asking costs nothing a run was not already paying.
        """
        without: list[str] = []
        for name in paths:
            if not isinstance(name, str) or not name or name in without:
                continue
            if name not in self._text_layer_cache:
                self._text_layer_cache[name] = has_extractable_text(
                    deliverable_path / name
                )
            if self._text_layer_cache[name] is False:
                without.append(name)
        return tuple(without)

    def _runtime_criterion_plan(
        self,
        selection: DeliverableSelection,
        item: RubricItem,
        plan: CriterionTargetPlan,
        deliverable_path: Path,
        *,
        escalate_readable_siblings: bool = True,
    ) -> _RuntimeCriterionPlan:
        """Decide where one rubric item is judged, and what that will cost.

        ``escalate_readable_siblings=False`` withholds one signal and one
        only: "is any single selected file unreadable", the per-file question
        added so a picture delivered beside a readable memo is still looked
        at. Withholding it puts an item back on the path it took before that
        question existed -- read the sibling that can be read.

        It is the exact knob the budget fallback needs, because the two
        signals split on exactly the case that matters. A bundle where
        *something* can be read still has a text route to fall back to. A
        bundle where *nothing* can be read has none, and there
        ``selected_paths_have_text`` is still ``False`` and still escalates,
        so this cannot resurrect the defect task 64 fixed: reading zero
        characters and calling the content absent.
        """
        item_decision = resolve_runtime_routing(
            item.criterion,
            plan.selected_paths,
            selected_paths_have_text=self._selected_paths_have_text(
                deliverable_path, plan.selected_paths
            ),
            some_selected_path_lacks_text=(
                self._some_selected_path_lacks_text(
                    deliverable_path, plan.selected_paths
                )
                if escalate_readable_siblings
                else None
            ),
            selected_paths_have_audio=self._selected_paths_have_audio(
                deliverable_path, plan.selected_paths
            ),
            paths_without_text=self._paths_without_text(
                deliverable_path, plan.selected_paths
            ),
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
                decision = resolve_runtime_routing(
                    item.criterion,
                    target.paths,
                    selected_paths_have_text=self._selected_paths_have_text(
                        deliverable_path, target.paths
                    ),
                    some_selected_path_lacks_text=(
                        self._some_selected_path_lacks_text(
                            deliverable_path, target.paths
                        )
                        if escalate_readable_siblings
                        else None
                    ),
                    selected_paths_have_audio=self._selected_paths_have_audio(
                        deliverable_path, target.paths
                    ),
                    paths_without_text=self._paths_without_text(
                        deliverable_path, target.paths
                    ),
                )
                target_decisions[target_id] = decision
                if decision.modality is Modality.VISUAL:
                    child_render = decision.render_targets(target.paths)
                    raw_visual_paths.extend(child_render)
                    planned_names, child_error = (
                        self._tool_judge.validate_planned_visual_names(
                            child_render, visual_file_cap
                        )
                    )
                    supported_visual_paths.extend(planned_names)
                    if child_error is not None and visual_preflight_error is None:
                        visual_preflight_error = (
                            f"{target_id}: {child_error}"
                        )
        elif item_decision.modality is Modality.VISUAL:
            item_render = item_decision.render_targets(plan.selected_paths)
            raw_visual_paths.extend(item_render)
            supported_visual_paths, visual_preflight_error = (
                self._tool_judge.validate_planned_visual_names(
                    item_render, visual_file_cap
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

    def _relax_to_fit_visual_budget(
        self,
        selection: DeliverableSelection,
        task: TaskRubric,
        runtime_plans: list[_RuntimeCriterionPlan],
        deliverable_path: Path,
        visual_budget_error: str,
    ) -> tuple[list[_RuntimeCriterionPlan], str | None, str | None]:
        """Give up pictures before giving up the task.

        A task over its visual budget excludes every item that wanted a
        picture, and a task with nothing left to score is dropped from the
        corpus entirely -- not scored zero, *dropped*: ``_aggregate`` sets
        ``all_items_score_excluded`` and the analysers count only tasks
        without an error. Stage 3's task 43dc9778 asked for 134 renders
        against a cap of 72 and left a 67-item, 87%-scoring task out of a
        185-task corpus. Silently, because a corpus of 184 looks like a
        corpus.

        The item that escalated only because one of its files carries no
        text layer has somewhere else to go: the readable sibling it was
        selected beside. So when the budget cannot be met, ask what the task
        would have cost without that escalation, and if that fits, grade it.
        A partial verdict on a readable file beats no verdict at all, and it
        is exactly the verdict this benchmark produced before the escalation
        was added.

        Two properties make this safe to do automatically. It cannot invent a
        text verdict where there is no text -- an item whose files *all* lack
        a text layer still escalates, because that signal is left switched on
        (see ``_runtime_criterion_plan``). And it does not depend on rubric
        order: nothing here spends the budget on the first N items and starves
        the rest, which would make a task's score depend on how its rubric was
        written and is not a thing a fingerprinted benchmark may do.

        Returns the plans to grade with, the budget error that still applies
        to them, and the shortfall to record on the task.
        """
        relaxed = [
            self._runtime_criterion_plan(
                selection,
                item,
                strict.target_plan,
                deliverable_path,
                escalate_readable_siblings=False,
            )
            for item, strict in zip(task.rubric_items, runtime_plans)
        ]
        strict_demand = sum(
            plan.supported_visual_call_count for plan in runtime_plans
        )
        relaxed_demand = sum(plan.supported_visual_call_count for plan in relaxed)
        if relaxed_demand >= strict_demand:
            # Nothing to give up: every render this task wants is wanted by a
            # criterion that names something visual. Failing closed is right.
            return runtime_plans, visual_budget_error, None
        marked = [
            replace(plan, visual_budget_downgraded=True)
            if strict.requires_visual and not plan.requires_visual
            else plan
            for plan, strict in zip(relaxed, runtime_plans)
        ]
        logger.warning(
            "%s: %s; regrading %d item(s) without the unreadable-file "
            "escalation (%d renders -> %d)",
            task.task_id,
            visual_budget_error,
            sum(1 for plan in marked if plan.visual_budget_downgraded),
            strict_demand,
            relaxed_demand,
        )
        return (
            marked,
            self._task_visual_budget_error(marked),
            visual_budget_error,
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
                        runtime_plan.target_decisions[target_id].render_targets(
                            target_by_id[target_id].paths
                        )
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
                    visual_prepass.subset(
                        child_decision.render_targets(target.paths)
                    )
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
            self._check_should_stop(task.task_id, f"child {target_id}")
            self._last_cached_tokens = 0
            child, in_tok, out_tok = self._judge_via_tool_calling_selected(
                task,
                item,
                deliverable_path,
                list(target.paths),
                reference_file_names,
                visual_prepass=(
                    visual_prepass.subset(
                        runtime_plan.target_decisions[target_id].render_targets(
                            target.paths
                        )
                    )
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
                    "perception_error_detail": child.perception_error_detail,
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
            # The first child that failed on perception, so the parent row is
            # actionable without opening ``child_grades``. Every child keeps
            # its own; this is a pointer to the story, not a summary of all of
            # them.
            perception_error_detail=next(
                (
                    child.perception_error_detail
                    for child in child_items
                    if child.perception_error_detail
                ),
                None,
            ),
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
        """Grade one rubric item via the tool-calling judge.

        Task 207 — the legacy text-extraction path this used to fall back
        to is gone. ``_tool_judge`` is the only judge, so a config without
        ``judge.tools.read_deliverable`` is rejected at construction rather
        than silently graded a different way.
        """
        return self._judge_via_tool_calling(task, item, files)


    def _apply_tpm_delay(self) -> None:
        """TPM guard shared by the tool judge and both perception paths.

        Passed as ``before_upstream_call`` into ``ToolCallingJudge``,
        ``VisionPerception`` and ``AudioPerception``, so this is live v2
        infrastructure, not part of the legacy text-extract path removed in
        task 207.

        All three share one spacer on purpose: they share one connection and
        therefore one token-per-minute allowance, so a guard that only some
        of them honour paces nothing.
        """
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
        # An excluded item leaves the numerator and the denominator together,
        # so a rubric the grader could not finish reading is scored out of
        # less than the rubric is worth -- and the percentage rises. Two tasks
        # that earned the same points report different scores, the one whose
        # grading failed reporting the higher. On the published 30-task
        # cohort, a328feea earned 18.6 points and read 84.55% out of 22 after
        # two items were excluded; out of the rubric's full 24 the same 18.6
        # points is 77.50%. Fourteen tasks of the 185-task corpus were scored
        # against a denominator that had moved this way.
        #
        # Neither figure is wrong. They are the two ends of what is known.
        # ``pct`` divides by what was read, which assumes an unread item would
        # have scored like the items that were read. ``pct_full_denominator``
        # divides by the whole rubric, which assumes an unread item would have
        # scored nothing. The task's true percentage lies between them, and is
        # a single number only when nothing was excluded, where they are
        # equal. Which of the two is published is not decided here.
        excluded_items = [it for it in items if it.score_excluded]
        score_excluded_max = sum(max(0, it.max_score) for it in excluded_items)
        full_max = total_max + score_excluded_max
        pct_full_denominator = (
            max(0.0, min(100.0, total_awarded / full_max * 100.0))
            if full_max else 0.0
        )
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
            score_excluded_items=len(excluded_items),
            score_excluded_max=score_excluded_max,
            pct_full_denominator=round(pct_full_denominator, 2),
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
            from core.perception.vision import (  # local import
                VISION_CALL_CAP,
                VisionPerception,
            )
            vision_deployment = canonical_deployment(
                vis_cfg, "judge.perception.visual"
            )
            vision_perception = VisionPerception(
                client=self._perception_client,
                deployment=vision_deployment,
                call_cap=int(
                    vis_cfg.get("call_cap_per_task", VISION_CALL_CAP)
                ),
                reasoning_effort=vis_cfg.get(
                    "reasoning_effort",
                    (judge_cfg.get("reasoning") or {}).get("effort", "medium"),
                ),
                before_upstream_call=self._apply_tpm_delay,
            )
        if aud_cfg.get("model") is not None or aud_cfg.get("deployment") is not None:
            from core.perception.audio import (  # local import
                AUDIO_CALL_CAP,
                AUDIO_TRIM_SECONDS,
                AudioPerception,
            )
            audio_deployment = canonical_deployment(
                aud_cfg, "judge.perception.audio"
            )
            audio_perception = AudioPerception(
                client=self._perception_client,
                deployment=audio_deployment,
                call_cap=int(
                    aud_cfg.get("call_cap_per_task", AUDIO_CALL_CAP)
                ),
                trim_seconds=int(
                    aud_cfg.get("trim_seconds", AUDIO_TRIM_SECONDS)
                ),
                before_upstream_call=self._apply_tpm_delay,
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
            perception_error_detail=result.perception_error_detail,
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

    def _save_raw(self) -> bool:
        return bool(self.config.get("grader", {}).get("save_raw_responses", False))
