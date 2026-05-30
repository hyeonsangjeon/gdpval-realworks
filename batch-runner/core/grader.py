"""Rubric-based grading engine.

Routes rubric items to deterministic prechecks where possible, otherwise to an
Azure OpenAI Responses API judge. Evidence is mandatory for judge verdicts.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

import openpyxl
from PyPDF2 import PdfReader
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

from core.file_reader import read_reference_file
from core.rubric_loader import RubricItem, TaskRubric

logger = logging.getLogger(__name__)

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

PRECHECK_PATTERNS: list[tuple[str, str]] = [
    (
        r"\b(file|workbook|document|pdf|deliverable).*(named|basename|filename|extension|exists?|is a|is an|single|exactly one)\b",
        "file_exists_or_name",
    ),
    (
        r"\b(\.xlsx|\.xls|\.xlsm|\.pdf|\.docx?|\.pptx?|\.txt|\.csv|\.json|\.wav|\.mp3|\.mp4|\.png|\.jpg)\b",
        "file_extension",
    ),
    (r"\bworksheet\b.*(named|exactly|contains|present)", "worksheet_name"),
    (
        r"\b(at least|exactly|no more than|fewer than)\s+\d+\b.*(rows?|columns?|pages?|sheets?|sections?|items?|files?)\b",
        "count_check",
    ),
    (r"\bpage(s)?\b.*\b(at least|exactly)\s+\d+\b", "page_count"),
    (r"\bword(s)?\b.*\b(at least|exactly|approximately)\s+\d+\b", "word_count"),
]


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


class Grader:
    def __init__(self, config: dict, rubric_loader):
        self.config = config
        self.rubric_loader = rubric_loader

        provider = self.config.get("judge", {}).get("provider", "azure_openai")
        if provider != "azure_openai":
            raise NotImplementedError(f"Unsupported judge provider: {provider}")

        endpoint_env = self.config["judge"]["endpoint_env"]
        endpoint = os.getenv(endpoint_env)
        if not endpoint:
            raise ValueError(f"Missing Azure endpoint env var: {endpoint_env}")

        timeout = int(self.config.get("judge", {}).get("timeout_sec", 600))
        api_version = self.config.get("judge", {}).get(
            "api_version", "2025-04-01-preview"
        )
        self.model = self.config["judge"]["model"]

        # Auth: default is OIDC (DefaultAzureCredential). Opt-in API key
        # fallback is available ONLY when GRADER_ALLOW_API_KEY_FALLBACK=1
        # is set. This preserves the OIDC-only invariant for production
        # while letting the cost-optimization sweep recover from stale SP
        # secrets without an interactive credential rotation.
        allow_api_key_fallback = (
            os.getenv("GRADER_ALLOW_API_KEY_FALLBACK", "0") == "1"
        )
        api_key = os.getenv("AZURE_OPENAI_API_KEY") if allow_api_key_fallback else None

        client_kwargs: dict = {
            "azure_endpoint": endpoint,
            "api_version": api_version,
            "timeout": timeout,
        }
        try:
            credential = DefaultAzureCredential()
            token_provider = get_bearer_token_provider(
                credential, "https://cognitiveservices.azure.com/.default"
            )
            # Force a token fetch up front so we fail fast if OIDC is broken.
            if allow_api_key_fallback:
                try:
                    _ = token_provider()
                except Exception as oidc_err:  # noqa: BLE001
                    if not api_key:
                        raise
                    print(
                        f"   ⚠️  Grader OIDC failed ({type(oidc_err).__name__}); "
                        f"falling back to AZURE_OPENAI_API_KEY"
                    )
                    raise oidc_err
            client_kwargs["azure_ad_token_provider"] = token_provider
        except Exception:
            if api_key:
                client_kwargs["api_key"] = api_key
            else:
                raise

        self.client = AzureOpenAI(**client_kwargs)

        self.prompt_template = self._read_prompt_template(self.config["prompt"]["template"])
        self.prompt_version = self._extract_prompt_version(self.prompt_template)
        self._min_delay_seconds = (
            float(self.config.get("tpm_guard", {}).get("min_delay_ms_between_calls", 0))
            / 1000.0
        )
        self._last_judge_call_at: float | None = None

        # --- Optional: prompt-level batching + tiered judge routing ------
        # These are no-ops when the grading config does not set them; the
        # single-item path above is left untouched. See `core.grader_batch`
        # for the implementation. Note: `judge_call_count` becomes per-API-call
        # (not per-item) the moment batching is active.
        self.batch_size = int(self.config.get("grader", {}).get("batch_size", 1) or 1)
        self.judge_routing = self.config.get("judge_routing") or None
        self._use_batch = (self.batch_size > 1) or bool(self.judge_routing)
        self._tier_judges: dict[str, "object"] = {}
        if self._use_batch:
            self._build_tier_judges()

        # --- PR2 task 203: v2 tool-calling judge opt-in ------------------
        # Activated when the grading config sets `judge.tools.read_deliverable`
        # (a structure unique to v2 configs). When set we instantiate a
        # `ToolCallingJudge`; `_judge()` then dispatches to it instead of
        # the legacy text-extraction path. Tier batching + tool-calling
        # are mutually exclusive — v2 configs do not set judge_routing.
        self._tool_judge = None
        if self._is_tool_calling_config():
            self._tool_judge = self._build_tool_calling_judge()

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
                for k in ("model", "deployment", "reasoning_effort", "max_output_tokens"):
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
        for pattern, pid in PRECHECK_PATTERNS:
            if re.search(pattern, item.criterion, re.I):
                return "precheck", pid
        return "judge", None

    def grade_task(self, task: TaskRubric, deliverable_dir: str) -> TaskGrade:
        deliverable_path = Path(deliverable_dir)
        files = self._list_files(deliverable_path)

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
        if not deliverable_dir.exists() or not deliverable_dir.is_dir():
            return []
        return sorted([p for p in deliverable_dir.rglob("*") if p.is_file()])

    def _run_precheck(
        self,
        pattern_id: Optional[str],
        item: RubricItem,
        files: list[Path],
    ) -> Optional[tuple[Verdict, str]]:
        if not pattern_id:
            return None

        handlers = {
            "file_exists_or_name": self._precheck_file_exists_or_name,
            "file_extension": self._precheck_file_extension,
            "worksheet_name": self._precheck_worksheet_name,
            "count_check": self._precheck_count_check,
            "page_count": self._precheck_page_count,
            "word_count": self._precheck_word_count,
        }
        handler = handlers.get(pattern_id)
        if not handler:
            return None

        try:
            return handler(item, files)
        except Exception as exc:
            logger.warning(
                "Precheck failed for %s (%s): %s", item.rubric_item_id, pattern_id, exc
            )
            return None

    def _precheck_file_exists_or_name(
        self,
        item: RubricItem,
        files: list[Path],
    ) -> Optional[tuple[Verdict, str]]:
        criterion = item.criterion
        named_match = re.search(
            r"(?:basename|named|filename)\s*(?:is|=)?\s*['\"]([^'\"]+)['\"]",
            criterion,
            re.I,
        )
        if named_match:
            expected = named_match.group(1).strip().lower()
            for f in files:
                if f.stem.lower() == expected or f.name.lower() == expected:
                    return "pass", f"Filename observed: '{f.name}'"
            return "fail", f"Expected basename '{expected}' not found"

        if files:
            return "pass", f"Deliverable files present ({len(files)})"
        return "fail", "No deliverable files found"

    def _precheck_file_extension(
        self,
        item: RubricItem,
        files: list[Path],
    ) -> Optional[tuple[Verdict, str]]:
        exts = set(
            re.findall(
                r"\.(xlsx|xls|xlsm|pdf|docx?|pptx?|txt|csv|json|wav|mp3|mp4|png|jpg)",
                item.criterion,
                re.I,
            )
        )
        if not exts:
            return None
        expected_exts = {f".{x.lower()}" for x in exts}
        observed = {f.suffix.lower() for f in files}
        if observed.intersection(expected_exts):
            ext = sorted(observed.intersection(expected_exts))[0]
            return "pass", f"Observed required extension: '{ext}'"
        return "fail", f"Required extension not found: {sorted(expected_exts)}"

    def _precheck_worksheet_name(
        self,
        item: RubricItem,
        files: list[Path],
    ) -> Optional[tuple[Verdict, str]]:
        m = re.search(
            r"worksheet\s+(?:named|name)\s*['\"]([^'\"]+)['\"]",
            item.criterion,
            re.I,
        )
        if not m:
            return None
        target = m.group(1).strip().lower()
        xlsx_files = [f for f in files if f.suffix.lower() in {".xlsx", ".xlsm"}]
        if not xlsx_files:
            return "fail", "No Excel workbook found"

        for xf in xlsx_files:
            wb = openpyxl.load_workbook(str(xf), data_only=True)
            names = {n.lower() for n in wb.sheetnames}
            if target in names:
                return "pass", f"Worksheet '{m.group(1)}' present in {xf.name}"
        return "fail", f"Worksheet '{m.group(1)}' not found"

    def _precheck_count_check(
        self,
        item: RubricItem,
        files: list[Path],
    ) -> Optional[tuple[Verdict, str]]:
        m = re.search(
            r"(exactly|at least|no more than|fewer than)\s+(\d+)\s+files?",
            item.criterion,
            re.I,
        )
        if not m:
            return None
        mode = m.group(1).lower()
        expected = int(m.group(2))
        observed = len(files)
        ok = (
            (mode == "exactly" and observed == expected)
            or (mode == "at least" and observed >= expected)
            or (mode == "no more than" and observed <= expected)
            or (mode == "fewer than" and observed < expected)
        )
        if ok:
            return "pass", f"File count {observed} satisfies '{mode} {expected}'"
        return "fail", f"File count {observed} violates '{mode} {expected}'"

    def _precheck_page_count(
        self,
        item: RubricItem,
        files: list[Path],
    ) -> Optional[tuple[Verdict, str]]:
        m = re.search(r"page(?:s)?\b.*\b(at least|exactly)\s+(\d+)", item.criterion, re.I)
        if not m:
            return None
        mode = m.group(1).lower()
        expected = int(m.group(2))

        pdfs = [f for f in files if f.suffix.lower() == ".pdf"]
        if not pdfs:
            return None

        observed = len(PdfReader(str(pdfs[0])).pages)
        ok = (mode == "exactly" and observed == expected) or (
            mode == "at least" and observed >= expected
        )
        if ok:
            return "pass", f"PDF page count {observed} satisfies '{mode} {expected}'"
        return "fail", f"PDF page count {observed} violates '{mode} {expected}'"

    def _precheck_word_count(
        self,
        item: RubricItem,
        files: list[Path],
    ) -> Optional[tuple[Verdict, str]]:
        m = re.search(
            r"word(?:s)?\b.*\b(at least|exactly|approximately)\s+(\d+)",
            item.criterion,
            re.I,
        )
        if not m:
            return None
        mode = m.group(1).lower()
        expected = int(m.group(2))

        txt_candidates = [f for f in files if f.suffix.lower() in {".txt", ".docx"}]
        if not txt_candidates:
            return None

        text = read_reference_file(str(txt_candidates[0]))
        words = len(re.findall(r"\S+", text))
        if mode == "at least":
            ok = words >= expected
        elif mode == "exactly":
            ok = words == expected
        else:
            ok = abs(words - expected) <= max(10, int(expected * 0.1))

        if ok:
            return "pass", f"Word count {words} satisfies '{mode} {expected}'"
        return "fail", f"Word count {words} violates '{mode} {expected}'"

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
                logger.warning(
                    "Judge call failed for %s after retries: %s",
                    item.rubric_item_id,
                    exc,
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
                        judge_raw_response=str(exc) if self._save_raw() else None,
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
                it.model_did_right = False
            elif (it.max_score or 0) < 0:
                it.model_did_right = (it.verdict != "pass")
            else:
                it.model_did_right = (it.verdict == "pass")

        total_awarded = sum(it.awarded_score for it in items)
        total_max = task.max_score
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
            for it in items
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

        judge_cfg = self.config.get("judge", {})
        tool_prompt_path = (
            self.config.get("prompt", {}).get("tool_template")
            or str(Path(self.config["prompt"]["template"]).with_name(
                "grader_judge_v2.md"))
        )
        tool_prompt = self._read_prompt_template(tool_prompt_path)

        per_item_cap = int(
            (judge_cfg.get("tools", {}).get("read_deliverable", {})
             .get("per_item_call_cap", 8))
        )
        max_iter = int(
            (judge_cfg.get("tools", {}).get("read_deliverable", {})
             .get("max_iterations", 10))
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
        )

    def _judge_via_tool_calling(
        self, task: TaskRubric, item: RubricItem, files: list[Path]
    ) -> tuple[ItemGrade, int, int]:
        if not files:
            self._last_cached_tokens = 0
            return self._absent_judge_item(item), 0, 0
        deliverable_dir = str(files[0].parent)
        file_names = [f.name for f in files]
        self._apply_tpm_delay()
        result = self._tool_judge.judge_item(
            task=task, item=item,
            deliverable_dir=deliverable_dir,
            file_names=file_names,
        )
        # PR3 Step 0 — expose cached input tokens via instance side-channel.
        # Avoids changing the (ItemGrade, in_tok, out_tok) tuple shape used
        # by both v1 and v2 grader dispatch paths.
        self._last_cached_tokens = result.cached_tokens
        ig = ItemGrade(
            rubric_item_id=item.rubric_item_id,
            criterion=item.criterion,
            max_score=item.score,
            awarded_score=result.awarded_score,
            verdict=result.verdict,
            decided_by="judge",
            required=item.required,
            evidence=result.evidence or (result.judge_error or ""),
            judge_confidence=result.confidence,
            judge_latency_ms=round(result.latency_ms, 2),
            judge_raw_response=result.raw_text if self._save_raw() else None,
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
