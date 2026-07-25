"""Prompt-level batching helper for the rubric judge.

`BatchJudge` evaluates N rubric items against a single deliverable in one
Azure OpenAI Responses API call. It is a sibling helper to
`core.grader.Grader` — the single-item code path in `core.grader` is left
untouched and remains the default behaviour. `Grader` delegates to
`BatchJudge` only when `grader.batch_size > 1` OR a `judge_routing` block
is present in the grading config.

Design choices (documented for reproducibility):

1. **Per-batch call accounting.** `num_api_calls` in `BatchResult` counts
   actual Responses API invocations, not items. When the caller
   aggregates this into `TaskGrade.judge_call_count`, a successful batch
   of 8 items counts as 1 call (not 8). A fallback split of an 8-item
   batch into two 4-item batches counts as 2 calls. Tests assert this.

2. **Latency distribution.** `judge_total_latency_ms` for a batch is the
   wall-clock latency of the underlying API call(s). Each per-item
   `ItemGrade.judge_latency_ms` is the batch latency divided evenly
   across items in that batch (`latency_ms / len(items)`), so that
   summing `judge_latency_ms` across items in a batch reconstructs the
   total wall-clock cost. This is a reporting convenience only.

3. **Token accounting.** `input_tokens` / `output_tokens` reported by the
   API for a batched call are returned as shared totals on `BatchResult`.
   The caller is responsible for adding them to the task-level
   aggregates (we do NOT split per-item to avoid double-counting if the
   caller also wanted per-item attribution).

4. **Evidence enforcement is per-item.** Each element in the JSON array
   response is checked independently. A missing evidence quote on one
   item flips ONLY that item to `verdict=fail`; other items in the same
   batch are unaffected.

5. **Parse failure / truncation fallback.** If the response cannot be
   parsed as a JSON array, or if the array length does not match the
   request, the batch is retried ONCE by splitting it in half
   (`chunk_size // 2`). The two sub-batches are dispatched as separate
   API calls (counted toward `num_api_calls`). If a sub-batch still
   fails, the items in that sub-batch are marked
   `verdict="judge_error"`. We do not recurse further to keep cost
   bounded.

6. **Reproducibility preserved.** `temperature`/`seed` are NOT passed to
   the Responses API (reasoning models reject them). The reproducibility
   contract is the 4-tuple cache key
   `(exp_id, judge_model, rubric_sha, prompt_v)` which is computed by
   the caller — `BatchJudge` itself is stateless beyond the bound client
   and tier config.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from core.file_reader import read_reference_file
from core.public_error import public_provider_error_text
from core.rubric_loader import RubricItem, TaskRubric

logger = logging.getLogger(__name__)

# Imported lazily inside BatchJudge to avoid circular import with grader.py
# (grader.py is the consumer; grader_batch.py should not import grader.py)


@dataclass
class BatchResult:
    """Outcome of a single `judge_items_batch` call (possibly fanned out)."""

    items: list  # list[ItemGrade]; typed as list to avoid grader.py import cycle
    input_tokens: int
    output_tokens: int
    num_api_calls: int
    total_latency_ms: float


class BatchJudge:
    """Evaluate N rubric items per Responses API call.

    Parameters
    ----------
    client : AzureOpenAI
        A pre-built Azure OpenAI client (shared with the parent Grader to
        avoid duplicate auth / token-provider construction).
    judge_config : dict
        Tier-resolved judge config. Required keys: ``model``. Optional:
        ``reasoning_effort`` (default "high"), ``max_output_tokens``
        (default 4096), ``deployment`` (metadata only).
    tpm_guard : dict
        Forwarded from the grading config. Honors ``min_delay_ms_between_calls``
        and ``retry_on_429``.
    prompt_template : str
        Raw text of the batch prompt (loaded from
        ``prompts/grader_judge_batch.md``).
    grader_config : dict
        Forwarded ``grader`` section of the grading config. Honors
        ``evidence_max_chars``, ``deliverable_extract_max_chars``,
        ``task_prompt_truncate_chars``, ``fail_on_missing_evidence``,
        ``save_raw_responses``.
    """

    def __init__(
        self,
        client,
        judge_config: dict,
        tpm_guard: dict,
        prompt_template: str,
        grader_config: Optional[dict] = None,
    ) -> None:
        self.client = client
        self.judge_config = dict(judge_config or {})
        self.tpm_guard = dict(tpm_guard or {})
        self.prompt_template = prompt_template
        self.grader_config = dict(grader_config or {})

        self.model = self.judge_config.get("model")
        if not self.model:
            raise ValueError("BatchJudge.judge_config requires 'model'")
        self.reasoning_effort = self.judge_config.get("reasoning_effort", "high")
        self.max_output_tokens = int(self.judge_config.get("max_output_tokens", 4096))

        self._min_delay_seconds = (
            float(self.tpm_guard.get("min_delay_ms_between_calls", 0)) / 1000.0
        )
        self._last_call_at: float | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def judge_items_batch(
        self,
        task: TaskRubric,
        items_chunk: list[RubricItem],
        deliverable_files: list[Path],
    ) -> BatchResult:
        """Judge a chunk of rubric items in one (or two, on fallback) API calls.

        See the module docstring for full semantics. Caller is responsible
        for ensuring `items_chunk` contains only items that need a judge
        (precheck-handled items must be filtered out beforehand).
        """
        if not items_chunk:
            return BatchResult(items=[], input_tokens=0, output_tokens=0, num_api_calls=0, total_latency_ms=0.0)

        if not deliverable_files:
            # No deliverable → every item is a forced fail, zero API calls.
            return BatchResult(
                items=[self._absent_item(it) for it in items_chunk],
                input_tokens=0,
                output_tokens=0,
                num_api_calls=0,
                total_latency_ms=0.0,
            )

        return self._dispatch(task, items_chunk, deliverable_files, allow_fallback=True)

    # ------------------------------------------------------------------
    # Internal dispatch with one-level fallback
    # ------------------------------------------------------------------

    def _dispatch(
        self,
        task: TaskRubric,
        items_chunk: list[RubricItem],
        deliverable_files: list[Path],
        allow_fallback: bool,
    ) -> BatchResult:
        prompt = self._build_batch_prompt(task, items_chunk, deliverable_files)
        try:
            raw, latency_ms, in_tok, out_tok, finish_reason = self._call_api(prompt)
        except Exception as exc:  # pragma: no cover - exercised via tests
            public_error = public_provider_error_text(exc)
            logger.warning("Batch judge API call failed: %s", public_error)
            return BatchResult(
                items=[
                    self._judge_error_item(
                        it,
                        "judge_api_call_failed",
                        public_error,
                    )
                    for it in items_chunk
                ],
                input_tokens=0,
                output_tokens=0,
                num_api_calls=1,
                total_latency_ms=0.0,
            )

        parsed = self._safe_parse_array(raw)
        size_ok = isinstance(parsed, list) and len(parsed) == len(items_chunk)

        if not size_ok:
            if allow_fallback and len(items_chunk) > 1:
                # Split in half; each half is one more API call.
                mid = len(items_chunk) // 2
                left = self._dispatch(task, items_chunk[:mid], deliverable_files, allow_fallback=False)
                right = self._dispatch(task, items_chunk[mid:], deliverable_files, allow_fallback=False)
                return BatchResult(
                    items=left.items + right.items,
                    input_tokens=in_tok + left.input_tokens + right.input_tokens,
                    output_tokens=out_tok + left.output_tokens + right.output_tokens,
                    num_api_calls=1 + left.num_api_calls + right.num_api_calls,
                    total_latency_ms=latency_ms + left.total_latency_ms + right.total_latency_ms,
                )
            # No fallback left or single item already → judge_error all items.
            reason = (
                "judge_json_parse_failed:truncated_at_max_tokens"
                if finish_reason in {"length", "incomplete", "max_output_tokens"}
                else "judge_json_parse_failed"
            )
            return BatchResult(
                items=[self._judge_error_item(it, reason, raw if self._save_raw() else None) for it in items_chunk],
                input_tokens=in_tok,
                output_tokens=out_tok,
                num_api_calls=1,
                total_latency_ms=latency_ms,
            )

        # Parse OK and length matches — convert each element to ItemGrade.
        per_item_latency = latency_ms / max(1, len(items_chunk))
        graded: list = []
        # Build an id -> element map for resilience against minor reordering.
        by_id = {str(el.get("rubric_item_id", "")): el for el in parsed if isinstance(el, dict)}
        for idx, item in enumerate(items_chunk):
            element = by_id.get(item.rubric_item_id)
            if element is None and idx < len(parsed) and isinstance(parsed[idx], dict):
                element = parsed[idx]  # positional fallback
            if not isinstance(element, dict):
                graded.append(self._judge_error_item(item, "judge_json_parse_failed:item_missing", None, per_item_latency))
                continue
            graded.append(self._element_to_item_grade(item, element, per_item_latency, raw if self._save_raw() else None))

        return BatchResult(
            items=graded,
            input_tokens=in_tok,
            output_tokens=out_tok,
            num_api_calls=1,
            total_latency_ms=latency_ms,
        )

    # ------------------------------------------------------------------
    # API call
    # ------------------------------------------------------------------

    def _call_api(self, prompt: str) -> tuple[str, float, int, int, str]:
        retry_cfg = self.tpm_guard.get("retry_on_429", {})
        max_retries = int(retry_cfg.get("max_retries", 3)) if retry_cfg.get("enabled", True) else 0
        backoff = float(retry_cfg.get("initial_backoff_sec", 2))
        factor = float(retry_cfg.get("exponential_factor", 2.0))

        for attempt in range(max_retries + 1):
            self._apply_tpm_delay()
            start = time.time()
            try:
                response = self.client.responses.create(
                    model=self.model,
                    input=prompt,
                    max_output_tokens=self.max_output_tokens,
                    reasoning={"effort": self.reasoning_effort},
                )
                latency_ms = (time.time() - start) * 1000
                text = getattr(response, "output_text", "") or ""
                usage = getattr(response, "usage", None)
                input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
                output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
                finish_reason = self._extract_finish_reason(response, self.max_output_tokens, output_tokens)
                return text, latency_ms, input_tokens, output_tokens, finish_reason
            except Exception as exc:
                status = getattr(exc, "status_code", None)
                if status in (429, 500, 502, 503, 504) and attempt < max_retries:
                    time.sleep(backoff)
                    backoff *= factor
                    continue
                raise

        raise RuntimeError("unreachable")  # pragma: no cover

    def _apply_tpm_delay(self) -> None:
        if self._min_delay_seconds <= 0:
            return
        now = time.time()
        if self._last_call_at is not None:
            elapsed = now - self._last_call_at
            remaining = self._min_delay_seconds - elapsed
            if remaining > 0:
                time.sleep(remaining)
                now = time.time()
        self._last_call_at = now

    # ------------------------------------------------------------------
    # Prompt building
    # ------------------------------------------------------------------

    def _build_batch_prompt(
        self,
        task: TaskRubric,
        items_chunk: list[RubricItem],
        deliverable_files: list[Path],
    ) -> str:
        task_prompt_max = int(self.grader_config.get("task_prompt_truncate_chars", 500))
        prompt = self.prompt_template
        prompt = prompt.replace("{{sector}}", task.sector)
        prompt = prompt.replace("{{occupation}}", task.occupation)
        prompt = prompt.replace(
            "{{task_prompt_truncated_500}}", self._truncate(task.prompt, task_prompt_max)
        )
        prompt = prompt.replace("{{batch_size}}", str(len(items_chunk)))

        items_block_lines: list[str] = []
        for it in items_chunk:
            items_block_lines.append(
                f"- rubric_item_id: {it.rubric_item_id}\n"
                f"  max_score: {it.score}\n"
                f"  required: {json.dumps(it.required)}\n"
                f"  criterion: {it.criterion}"
            )
        prompt = prompt.replace("{{rubric_items_block}}", "\n".join(items_block_lines))

        summaries = self._summarize_deliverables(deliverable_files)
        block = ""
        for d in summaries:
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

    def _summarize_deliverables(self, files: list[Path]) -> list[dict]:
        max_chars = int(self.grader_config.get("deliverable_extract_max_chars", 4000))
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

    # ------------------------------------------------------------------
    # Parsing & conversion
    # ------------------------------------------------------------------

    def _element_to_item_grade(
        self,
        item: RubricItem,
        element: dict,
        per_item_latency_ms: float,
        raw_for_debug: Optional[str],
    ):
        from core.grader import ItemGrade  # local import to avoid cycle

        verdict = str(element.get("verdict", "fail")).lower()
        if verdict not in {"pass", "partial", "fail"}:
            verdict = "fail"

        partial = float(element.get("partial_score", 0.0) or 0.0)
        partial = max(0.0, min(1.0, partial))
        if verdict == "pass":
            partial = 1.0
        elif verdict == "fail":
            partial = 0.0
        elif partial <= 0.0 or partial >= 1.0:
            verdict = "fail"
            partial = 0.0

        evidence = str(element.get("evidence") or "").strip()
        evidence_max = int(self.grader_config.get("evidence_max_chars", 200))
        if len(evidence) > evidence_max:
            evidence = evidence[:evidence_max]
        if self.grader_config.get("fail_on_missing_evidence", True) and not evidence:
            verdict = "fail"
            partial = 0.0
            evidence = "missing evidence"

        awarded = float(item.score) * partial
        confidence_f: Optional[float] = None
        confidence = element.get("confidence")
        if confidence is not None:
            try:
                confidence_f = max(0.0, min(1.0, float(confidence)))
            except (TypeError, ValueError):
                confidence_f = None

        return ItemGrade(
            rubric_item_id=item.rubric_item_id,
            criterion=item.criterion,
            max_score=item.score,
            awarded_score=awarded,
            verdict=verdict,
            decided_by="judge",
            required=item.required,
            evidence=evidence,
            judge_confidence=confidence_f,
            judge_latency_ms=per_item_latency_ms,
            precheck_pattern_id=None,
            judge_raw_response=raw_for_debug,
        )

    def _judge_error_item(
        self,
        item: RubricItem,
        evidence: str,
        raw_for_debug: Optional[str],
        per_item_latency_ms: float = 0.0,
    ):
        from core.grader import ItemGrade

        return ItemGrade(
            rubric_item_id=item.rubric_item_id,
            criterion=item.criterion,
            max_score=item.score,
            awarded_score=0.0,
            verdict="judge_error",
            decided_by="judge",
            required=item.required,
            evidence=evidence,
            judge_confidence=None,
            judge_latency_ms=per_item_latency_ms,
            precheck_pattern_id=None,
            judge_raw_response=raw_for_debug if self._save_raw() else None,
        )

    def _absent_item(self, item: RubricItem):
        from core.grader import ItemGrade

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

    @staticmethod
    def _safe_parse_array(raw_text: str):
        text = raw_text.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        # Try direct array parse first
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1 and end > start:
            candidate = text[start : end + 1]
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass
        # Sometimes models wrap an array in an object
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                obj = json.loads(text[start : end + 1])
                for v in obj.values() if isinstance(obj, dict) else []:
                    if isinstance(v, list):
                        return v
            except json.JSONDecodeError:
                pass
        return None

    @staticmethod
    def _extract_finish_reason(response, max_output: int, output_tokens: int) -> str:
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

    @staticmethod
    def _truncate(value: str, max_chars: int) -> str:
        if len(value) <= max_chars:
            return value
        return value[:max_chars] + "..."

    def _save_raw(self) -> bool:
        return bool(self.grader_config.get("save_raw_responses", False))
