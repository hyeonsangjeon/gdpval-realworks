"""Tool-calling judge — PR2 task 203.

A standalone class that grades **one rubric item at a time** using the
Azure OpenAI Responses API in function-calling mode. Replaces the v1
text-extraction-then-judge pattern of ``core.grader.Grader._judge``.

Why standalone (and not a method on ``Grader``):

* Easier to mock for tests (inject a fake client).
* Lets the legacy ``Judge`` / ``BatchJudge`` code in ``grader.py`` keep
  working unchanged during PR2. Task 207 will retire the legacy paths.
* Same return shape as ``Grader._judge`` so dispatch is a single ``if``
  branch in ``grade_task``.

Loop shape::

    visual_evidence = harness_render_and_perceive(selected_paths)
    while not done and iterations < cap:
        response = client.responses.create(
            model=...,
            input=messages,
            tools=[MODEL_READ_DELIVERABLE_TOOL_SCHEMA, ...],
            reasoning={"effort": ...},
        )
        for item in response.output:
            if item.type == 'function_call':
                args = json.loads(item.arguments)
                result = read_deliverable(args['op'], args['path'],
                                          base_dir=deliverable_dir,
                                          scope=args.get('scope'))
                messages.append({'type': 'function_call_output',
                                 'call_id': item.call_id,
                                 'output': json.dumps(result)})
            elif item.type == 'message':
                final_text = item.content[0].text
                done = True

The judge sees a routing hint injected into the prompt (chosen by
``core.grader_routing.classify_criterion``) so the cheapest first op
is suggested up front.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.grader_routing import (
    RoutingDecision,
    classify_criterion,
    is_overall_style_criterion,
)
from core.public_error import public_provider_error_text, public_task_error_text
from core.rubric_loader import RubricItem, TaskRubric
from core.tools import (
    MODEL_READ_DELIVERABLE_OPS,
    MODEL_READ_DELIVERABLE_TOOL_SCHEMA,
    read_deliverable,
)

logger = logging.getLogger(__name__)

_PROMPT_CACHE_KEY_MAX_CHARS = 64
_FINALIZATION_RETRY_PROMPT = (
    "Your previous response was missing or malformed. Do not call any more "
    "tools. Using the evidence already returned, respond now with only the "
    "required valid JSON verdict envelope."
)


def _bounded_prompt_cache_key(value: str) -> str:
    if len(value) <= _PROMPT_CACHE_KEY_MAX_CHARS:
        return value
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _response_finish_reason(
    response: Any, max_output_tokens: int, output_tokens: int
) -> str:
    incomplete = getattr(response, "incomplete_details", None)
    reason = getattr(incomplete, "reason", None) if incomplete is not None else None
    if isinstance(reason, str) and reason:
        return reason.lower()
    status = getattr(response, "status", None)
    if isinstance(status, str) and status:
        return status.lower()
    if max_output_tokens > 0 and output_tokens >= max_output_tokens:
        return "max_output_tokens"
    return "unknown"

_VISUAL_RENDER_SCOPES: Dict[str, Dict[str, int]] = {
    ".pdf": {"page": 1},
    ".xlsx": {"workbook_page": 1},
    ".xlsm": {"workbook_page": 1},
    ".pptx": {"slide": 1},
    # A .docx stores no pagination, so "page 1" is page 1 of the LibreOffice
    # conversion rather than a property of the file. That is fine at the only
    # index used here -- the first page is the first page under any engine.
    ".docx": {"page": 1},
    ".png": {},
    ".jpg": {},
    ".jpeg": {},
    ".gif": {},
    ".bmp": {},
    ".webp": {},
}
_VISUAL_FILE_CAP = 3
_RENDERER_METADATA_KEYS = (
    "kind",
    "source_kind",
    "source_page_count",
    "source_sheet_count",
    "source_slide_count",
    "converted_page_count",
    "renderer",
    "byte_size",
)


@dataclass
class VisualEvidenceEntry:
    path: str
    source_sha256: str
    scope: Dict[str, Any]
    renderer_metadata: Dict[str, Any]
    coverage_metadata: Dict[str, Any]
    vision: Dict[str, Any]
    render_latency_ms: float = 0.0

    def to_prompt_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "source_sha256": self.source_sha256,
            "scope": self.scope,
            "renderer_metadata": self.renderer_metadata,
            "coverage_metadata": self.coverage_metadata,
            "vision": {
                key: self.vision.get(key)
                for key in (
                    "verdict", "partial_score", "evidence", "confidence",
                    "reasoning", "judge_error",
                )
            },
        }

    def to_provenance_dict(self) -> Dict[str, Any]:
        path = Path(self.path)
        if (
            path.is_absolute()
            or ".." in path.parts
            or "\\" in self.path
            or any(char in self.path for char in ("\r", "\n"))
            or re.match(r"^[A-Za-z]:", self.path)
        ):
            raise ValueError("visual provenance path must be relative and confined")
        return {
            "path": path.as_posix(),
            "source_sha256": self.source_sha256,
            "scope": dict(self.scope),
            "renderer_metadata": dict(self.renderer_metadata),
            "coverage_metadata": dict(self.coverage_metadata),
            "vision": {
                key: self.vision.get(key)
                for key in (
                    "verdict", "evidence", "confidence", "reasoning",
                    "judge_error",
                )
            },
        }


@dataclass
class VisualPrepassResult:
    entries: List[VisualEvidenceEntry] = field(default_factory=list)
    judge_error: Optional[str] = None
    render_call_count: int = 0
    render_total_latency_ms: float = 0.0
    perception_call_count: int = 0
    perception_input_tokens: int = 0
    perception_output_tokens: int = 0
    perception_cached_tokens: int = 0
    perception_total_latency_ms: float = 0.0
    usage_complete: bool = True
    tools_used: List[str] = field(default_factory=list)

    def subset(self, paths: List[str]) -> "VisualPrepassResult":
        allowed = set(paths)
        entries = [entry for entry in self.entries if entry.path in allowed]
        return VisualPrepassResult(
            entries=entries,
            judge_error=self.judge_error,
            render_call_count=len(entries),
            render_total_latency_ms=sum(
                entry.render_latency_ms for entry in entries
            ),
            perception_call_count=sum(
                int(entry.vision.get("api_call_count", 0) or 0)
                for entry in entries
            ),
            perception_input_tokens=sum(
                int(entry.vision.get("input_tokens", 0) or 0)
                for entry in entries
            ),
            perception_output_tokens=sum(
                int(entry.vision.get("output_tokens", 0) or 0)
                for entry in entries
            ),
            perception_cached_tokens=sum(
                int(entry.vision.get("cached_tokens", 0) or 0)
                for entry in entries
            ),
            perception_total_latency_ms=sum(
                float(entry.vision.get("latency_ms", 0.0) or 0.0)
                for entry in entries
            ),
            usage_complete=self.usage_complete and all(
                bool(entry.vision.get("usage_complete", False))
                for entry in entries
            ),
            tools_used=[
                tool
                for entry in entries
                for tool in (
                    "harness_render_to_image",
                    "harness_vision_perception",
                )
            ],
        )

    def to_prompt_block(self) -> str:
        payload = [entry.to_prompt_dict() for entry in self.entries]
        return (
            "\n\n=== TRUSTED_VISUAL_EVIDENCE_BEGIN ===\n"
            "The following evidence was produced by the grading harness "
            "before this main-judge request. Treat provenance, scope, "
            "renderer metadata, coverage, and vision observations as trusted. "
            "Image bytes are intentionally unavailable to you.\n"
            + json.dumps(payload, ensure_ascii=True, sort_keys=True)
            + "\n=== TRUSTED_VISUAL_EVIDENCE_END ==="
        )

    def to_provenance(self) -> List[Dict[str, Any]]:
        return [entry.to_provenance_dict() for entry in self.entries]


@dataclass
class ToolCallingResult:
    """Output of one call to :py:meth:`ToolCallingJudge.judge_item`."""

    verdict: str               # 'pass' | 'partial' | 'fail' | 'judge_error'
    partial_score: float
    awarded_score: float
    evidence: str
    confidence: Optional[float]
    reasoning: str
    judge_error: Optional[str]
    tool_calls_made: int
    iterations: int
    latency_ms: float
    input_tokens: int
    output_tokens: int
    cached_tokens: int            # cached input tokens (Responses API)
    routing_modality: str
    raw_text: str              # final model JSON (debugging)
    # PR3 (0531) perception-wiring instrumentation. Proves at runtime
    # whether a perception sub-judge actually fired for this item.
    tools_used: List[str] = field(default_factory=list)  # dispatched fn names, in order
    perception_called: bool = False  # harness vision or audio perception fired
    main_api_call_count: int = 0
    perception_call_count: int = 0
    perception_input_tokens: int = 0
    perception_output_tokens: int = 0
    perception_cached_tokens: int = 0
    perception_total_latency_ms: float = 0.0
    render_call_count: int = 0
    render_total_latency_ms: float = 0.0
    usage_complete: bool = True
    score_excluded: bool = False
    visual_provenance: List[Dict[str, Any]] = field(default_factory=list)


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _strip_code_fence(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t.lower().startswith("json"):
            t = t[4:]
        t = t.strip()
    return t


def _bounded_json_int(value: str) -> int | str:
    """Avoid Python's global giant-int conversion limit escaping the parser."""
    if len(value.lstrip("-")) > 100:
        return value
    return int(value)


def _safe_json_loads(text: str) -> Optional[Dict[str, Any]]:
    try:
        parsed = json.loads(_strip_code_fence(text), parse_int=_bounded_json_int)
        return dict(parsed) if isinstance(parsed, Mapping) else None
    except (json.JSONDecodeError, TypeError, ValueError):
        # try to recover the first {...} block
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            return None
        try:
            parsed = json.loads(m.group(0), parse_int=_bounded_json_int)
            return dict(parsed) if isinstance(parsed, Mapping) else None
        except (json.JSONDecodeError, TypeError, ValueError):
            return None


def _validated_final_envelope(
    parsed: Mapping[str, Any],
) -> Optional[Tuple[str, float, float]]:
    verdict_raw = parsed.get("verdict")
    partial_raw = parsed.get("partial_score")
    confidence_raw = parsed.get("confidence")
    verdict = verdict_raw.lower() if isinstance(verdict_raw, str) else ""
    if verdict not in {"pass", "partial", "fail"}:
        return None
    if isinstance(partial_raw, bool) or not isinstance(
        partial_raw, (int, float)
    ):
        return None
    if isinstance(confidence_raw, bool) or not isinstance(
        confidence_raw, (int, float)
    ):
        return None
    try:
        partial = float(partial_raw)
        confidence = float(confidence_raw)
    except (OverflowError, TypeError, ValueError):
        return None
    if not math.isfinite(partial) or not 0.0 <= partial <= 1.0:
        return None
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        return None
    if (
        (verdict == "pass" and partial != 1.0)
        or (verdict == "fail" and partial != 0.0)
        or (verdict == "partial" and not 0.0 < partial < 1.0)
    ):
        return None
    return verdict, partial, confidence


def _finalization_retry_reason(
    final_text: str,
    response: Any,
    max_output_tokens: int,
    output_tokens: int,
) -> Optional[str]:
    if not final_text.strip():
        finish_reason = _response_finish_reason(
            response, max_output_tokens, output_tokens
        )
        return f"empty_final_text:{finish_reason}"
    parsed = _safe_json_loads(final_text)
    if parsed is None:
        return "final_json_parse_failed"
    if _validated_final_envelope(parsed) is None:
        return "invalid_final_envelope"
    return None


# ----------------------------------------------------------------------
# Judge
# ----------------------------------------------------------------------


@dataclass
class ToolCallingJudge:
    """Tool-calling rubric judge.

    Args:
        client:                  object with ``.responses.create(**kwargs)``
                                 (Azure OpenAI Responses client or a fake).
        model:                   deployment name (e.g. ``"gpt-5.6-sol"``).
        prompt_template:         contents of ``prompts/grader_judge_v2.md``
                                 — must contain a ``<!-- ===SPLIT=== -->``
                                 marker separating the stable scaffold
                                 (sent as ``instructions=``, cached server-
                                 side) from the per-item variable content.
        reasoning_effort:        ``"none" | "low" | "medium" | "high" |
                     "xhigh" | "max"``.
        max_output_tokens:       per-call output budget.
        per_item_tool_call_cap:  hard upper bound on tool dispatches for
                                 a single rubric item. Loop exits with
                                 ``judge_error="tool_cap_exceeded"`` past
                                 this number.
        max_iterations:          hard upper bound on response.create
                                 iterations (one tool round = one
                                 iteration).
        finalization_retries:    bounded retries when a final response is
                     missing or malformed after evidence is ready.
        finalization_reasoning_effort: reasoning effort used for the bounded
                 no-tools finalization retry. Defaults to ``"low"`` for
                 existing configs.
        vision_perception:       optional ``VisionPerception`` instance.
                     For VISUAL items the harness renders and
                     invokes it before the first main request;
                     it is never exposed as a model tool.
        audio_perception:        optional ``AudioPerception`` instance
                                 (task 206), same shape.
        task_prompt_truncate:    chars kept of the original task prompt.
        prompt_cache_key:        optional stable identity normalized to the
                     Azure 64-character limit before it is passed
                     to ``responses.create(prompt_cache_key=...)``.
        compact_threshold:       optional Azure Responses API
                                 ``context_management.auto_compact_threshold``
                                 token count. Default = 60000 (only the
                                 long tool-loop tasks like the 49-call
                                 monster trip it; light/medium tasks stay
                                 fully cacheable).
        before_upstream_call:     optional zero-argument TPM guard invoked
                     before each main-judge or vision API call.
    """

    client: Any
    model: str
    prompt_template: str
    reasoning_effort: str = "medium"
    max_output_tokens: int = 2400
    per_item_tool_call_cap: int = 8
    max_iterations: int = 10
    finalization_retries: int = 1
    finalization_reasoning_effort: str = "low"
    model_read_ops: Tuple[str, ...] = MODEL_READ_DELIVERABLE_OPS
    vision_perception: Any = None
    audio_perception: Any = None
    task_prompt_truncate: int = 500
    prompt_cache_key: Optional[str] = None
    compact_threshold: Optional[int] = None
    before_upstream_call: Optional[Callable[[], None]] = None

    # Cached: split prompt template into stable + variable halves once at
    # construction (or first use). The stable half is the ``instructions=``
    # argument across every call — byte-identical → server-side cache hit.
    _stable_instructions: Optional[str] = field(default=None, init=False)
    _variable_template: Optional[str] = field(default=None, init=False)

    def __post_init__(self) -> None:
        if not self.model_read_ops:
            raise ValueError("model_read_ops must contain at least one operation")
        if self.finalization_retries < 0:
            raise ValueError("finalization_retries must be non-negative")
        self.finalization_retries = min(self.finalization_retries, 1)
        if self.finalization_reasoning_effort not in {
            "none", "low", "medium", "high", "xhigh", "max"
        }:
            raise ValueError("finalization_reasoning_effort is invalid")
        invalid_ops = set(self.model_read_ops) - set(MODEL_READ_DELIVERABLE_OPS)
        if invalid_ops:
            raise ValueError(
                f"model_read_ops contains unsupported operations: "
                f"{sorted(invalid_ops)}"
            )
        cache_key = self.prompt_cache_key
        if cache_key is None:
            match = re.search(
                r"prompt_version:\s*([A-Za-z0-9_.-]+)", self.prompt_template
            )
            prompt_version = match.group(1) if match else "unknown_prompt"
            cache_key = json.dumps(
                (
                    "unknown_experiment",
                    self.model,
                    "unknown_rubric",
                    prompt_version,
                ),
                separators=(",", ":"),
            )
        self.prompt_cache_key = _bounded_prompt_cache_key(cache_key)

    # ------------------------------------------------------------------
    # Public surface
    # ------------------------------------------------------------------

    def judge_item(
        self,
        *,
        task: TaskRubric,
        item: RubricItem,
        deliverable_dir: str,
        file_names: List[str],
        reference_file_names: Optional[List[str]] = None,
        visual_prepass: Optional[VisualPrepassResult] = None,
        routing_decision: Optional[RoutingDecision] = None,
    ) -> ToolCallingResult:
        """Grade one rubric item by letting the judge inspect files via tools."""
        decision = routing_decision or classify_criterion(item.criterion)
        # PR3 step 1a — split the prompt template into stable scaffold
        # (cached server-side via instructions=) and per-item variable.
        self._ensure_split()
        variable_prompt = self._render_variable(
            task, item, file_names, decision, reference_file_names or []
        )
        prepass = visual_prepass or VisualPrepassResult()
        if decision.modality.value == "visual":
            if visual_prepass is None:
                prepass = self.preflight_visual(
                    item=item,
                    deliverable_dir=deliverable_dir,
                    file_names=file_names,
                )
            expected_paths = self.planned_supported_visual_names(file_names)
            observed_paths = [entry.path for entry in prepass.entries]
            if prepass.judge_error is None and observed_paths != expected_paths:
                prepass.judge_error = (
                    "required_visual_prepass_incomplete:"
                    f"expected={expected_paths},observed={observed_paths}"
                )
            if prepass.judge_error is not None:
                return self._build_result(
                    item=item,
                    routing_modality="visual",
                    final_text="",
                    tool_calls_made=0,
                    iterations=0,
                    latency_ms=0.0,
                    input_tokens=0,
                    output_tokens=0,
                    cached_tokens=0,
                    judge_error=prepass.judge_error,
                    tools_used=self._visual_tools_used(prepass),
                    main_api_call_count=0,
                    visual_prepass=prepass,
                    usage_complete=prepass.usage_complete,
                )
            variable_prompt += prepass.to_prompt_block()
        tools = self._build_tools_for(decision.modality.value)

        messages: List[Dict[str, Any]] = [
            {"role": "user", "content": variable_prompt}
        ]
        tool_calls_made = 0
        iterations = 0
        input_tok_total = 0
        output_tok_total = 0
        cached_tok_total = 0
        tools_used: List[str] = self._visual_tools_used(prepass)
        main_api_call_count = 0
        main_latency_ms = 0.0
        usage_complete = prepass.usage_complete
        final_text = ""
        judge_error: Optional[str] = None
        finalization_only = False
        finalization_retries_used = 0

        while iterations < self.max_iterations + (
            finalization_retries_used if finalization_only else 0
        ):
            iterations += 1
            call_started: Optional[float] = None
            try:
                self._guard_upstream_call()
                # PR3 step 1a — instructions + prompt_cache_key make the
                # stable scaffold cacheable. compact_threshold (1b) is
                # set high enough that only long tool loops trip it,
                # leaving light/medium tasks fully prefix-cacheable.
                # parallel_tool_calls=False (1d) on the loop avoids
                # interleaved out-of-order tool outputs that confuse the
                # final JSON envelope.
                create_kwargs = dict(
                    model=self.model,
                    instructions=self._stable_instructions,
                    input=messages,
                    tools=tools,
                    reasoning={"effort": self.reasoning_effort},
                    max_output_tokens=self.max_output_tokens,
                    prompt_cache_key=self.prompt_cache_key,
                    parallel_tool_calls=False,
                )
                if finalization_only:
                    create_kwargs.pop("tools")
                    create_kwargs.pop("parallel_tool_calls")
                    create_kwargs["reasoning"] = {
                        "effort": self.finalization_reasoning_effort
                    }
                # PR3 step 1b — context_management server-side compaction.
                # The SDK signature exposes a dict shape but Azure's
                # legacy gpt-5.4 validation rejected dict with HTTP 400
                # ('expected an array of objects'). Disabled by default
                # until the array contract is documented; set
                # compact_threshold=None to opt out (default).
                if self.compact_threshold:
                    create_kwargs["context_management"] = [
                        {"type": "auto_compact",
                         "threshold": int(self.compact_threshold)}
                    ]
                call_started = time.perf_counter()
                main_api_call_count += 1
                response = self.client.responses.create(**create_kwargs)
                main_latency_ms += (time.perf_counter() - call_started) * 1000.0
            except TypeError as exc:
                if call_started is not None:
                    main_latency_ms += (
                        time.perf_counter() - call_started
                    ) * 1000.0
                usage_complete = False
                # SDK older than expected — fall back to the legacy call
                # shape (no instructions / cache_key / compaction). Log
                # once and keep going so the run isn't blocked.
                logger.warning(
                    "ToolCallingJudge SDK fallback (%s); using legacy call shape",
                    type(exc).__name__,
                )
                try:
                    self._guard_upstream_call()
                    call_started = time.perf_counter()
                    main_api_call_count += 1
                    fallback_kwargs = dict(
                        model=self.model,
                        input=messages,
                        reasoning={
                            "effort": self.finalization_reasoning_effort
                            if finalization_only
                            else self.reasoning_effort
                        },
                        max_output_tokens=self.max_output_tokens,
                    )
                    if not finalization_only:
                        fallback_kwargs["tools"] = tools
                    response = self.client.responses.create(**fallback_kwargs)
                    main_latency_ms += (
                        time.perf_counter() - call_started
                    ) * 1000.0
                except Exception as exc2:  # noqa: BLE001
                    if call_started is not None:
                        main_latency_ms += (
                            time.perf_counter() - call_started
                        ) * 1000.0
                    judge_error = public_provider_error_text(exc2)
                    break
            except Exception as exc:  # noqa: BLE001
                if call_started is not None:
                    main_latency_ms += (
                        time.perf_counter() - call_started
                    ) * 1000.0
                usage_complete = False
                judge_error = public_provider_error_text(exc)
                logger.warning(
                    "ToolCallingJudge upstream call failed for %s: %s",
                    item.rubric_item_id, judge_error,
                )
                break

            usage = getattr(response, "usage", None)
            if usage is None or not all(
                hasattr(usage, field_name)
                for field_name in ("input_tokens", "output_tokens")
            ):
                usage_complete = False
            response_input_tokens = int(
                getattr(usage, "input_tokens", 0) or 0
            )
            response_output_tokens = int(
                getattr(usage, "output_tokens", 0) or 0
            )
            input_tok_total += response_input_tokens
            output_tok_total += response_output_tokens
            # PR3 Step 0 — cached_tokens (Azure Responses API automatic prompt
            # caching). Field path: usage.input_tokens_details.cached_tokens.
            # Older SDKs may not expose the details object; default 0.
            details = getattr(usage, "input_tokens_details", None)
            if details is not None:
                cached_tok_total += int(getattr(details, "cached_tokens", 0) or 0)
            else:
                usage_complete = False

            output_items = list(getattr(response, "output", []) or [])
            function_calls = [o for o in output_items
                              if self._item_type(o) == "function_call"]
            messages_out = [o for o in output_items
                            if self._item_type(o) == "message"]

            if function_calls:
                if finalization_only:
                    judge_error = "unexpected_tool_call_during_finalization"
                    logger.warning(
                        "ToolCallingJudge rejected tool call during finalization "
                        "for %s",
                        item.rubric_item_id,
                    )
                    break
                # Preserve all assistant output items (including reasoning)
                # in original order, then append function outputs.
                messages.extend(
                    self._serialize_output_item(output_item)
                    for output_item in output_items
                )
                for fc in function_calls:
                    if tool_calls_made >= self.per_item_tool_call_cap:
                        # Refuse to execute; tell the model so it can
                        # finalize on what it already has.
                        messages.append(self._function_call_output_message(
                            fc,
                            {"ok": False,
                             "error": "tool_cap_exceeded",
                             "error_type": "cap"},
                        ))
                        continue
                    tool_calls_made += 1
                    tool_name = self._fc_name(fc)
                    tools_used.append(tool_name)
                    result = self._dispatch_tool(
                        fc,
                        deliverable_dir,
                        allowed_paths=set(file_names).union(
                            reference_file_names or []
                        ),
                    )
                    if tool_name == "audio_judge":
                        self._accumulate_perception_result(prepass, result)
                    messages.append(self._function_call_output_message(fc, result))
                # Loop again to let the model react to the tool outputs.
                continue

            # No tool calls — read the final message and stop.
            if messages_out:
                final_text = self._extract_text(messages_out[0])
            else:
                final_text = getattr(response, "output_text", "") or ""
            retry_reason = _finalization_retry_reason(
                final_text,
                response,
                self.max_output_tokens,
                response_output_tokens,
            )
            if (
                retry_reason is not None
                and finalization_retries_used < self.finalization_retries
            ):
                logger.warning(
                    "ToolCallingJudge invalid final response for %s (%s); "
                    "retrying finalization without tools",
                    item.rubric_item_id,
                    retry_reason,
                )
                messages.extend(
                    self._serialize_output_item(output_item)
                    for output_item in output_items
                )
                messages.append({
                    "role": "user",
                    "content": _FINALIZATION_RETRY_PROMPT,
                })
                finalization_retries_used += 1
                finalization_only = True
                continue
            break
        else:
            judge_error = "max_iterations_exceeded"

        return self._build_result(
            item=item,
            routing_modality=decision.modality.value,
            final_text=final_text,
            tool_calls_made=tool_calls_made,
            iterations=iterations,
            latency_ms=main_latency_ms,
            input_tokens=input_tok_total,
            output_tokens=output_tok_total,
            cached_tokens=cached_tok_total,
            judge_error=judge_error,
            tools_used=tools_used,
            main_api_call_count=main_api_call_count,
            visual_prepass=prepass,
            usage_complete=usage_complete,
        )

    def reset_perception(self) -> None:
        """Reset per-task call counters/caches on the perception sub-judges.

        VisionPerception/AudioPerception enforce a per-task call cap, so the
        grader must reset them at each task boundary. No-op when a sub-judge
        is not wired.
        """
        for p in (self.vision_perception, self.audio_perception):
            if p is not None and hasattr(p, "reset"):
                p.reset()

    # ------------------------------------------------------------------
    # Prompt / tools
    # ------------------------------------------------------------------

    SPLIT_MARKER = "<!-- ===SPLIT=== -->"

    def _ensure_split(self) -> None:
        """Lazy split of ``self.prompt_template`` at ``SPLIT_MARKER``.

        If the marker is absent (legacy v2 prompt), the whole template
        becomes the variable half and instructions stays an empty
        string — caching benefit is lost but correctness preserved.
        """
        if self._stable_instructions is not None:
            return
        if self.SPLIT_MARKER in self.prompt_template:
            head, tail = self.prompt_template.split(self.SPLIT_MARKER, 1)
            self._stable_instructions = head.strip()
            self._variable_template = tail.strip()
        else:
            self._stable_instructions = ""
            self._variable_template = self.prompt_template

    def _render_variable(
        self,
        task: TaskRubric,
        item: RubricItem,
        file_names: List[str],
        decision,
        reference_file_names: Optional[List[str]] = None,
    ) -> str:
        """Fill per-item placeholders in the variable-half template."""
        prompt = self._variable_template or self.prompt_template
        prompt = prompt.replace("{{sector}}", task.sector or "")
        prompt = prompt.replace("{{occupation}}", task.occupation or "")
        prompt = prompt.replace(
            "{{task_prompt_truncated_500}}",
            (task.prompt or "")[:self.task_prompt_truncate],
        )
        prompt = prompt.replace("{{rubric_item_id}}", str(item.rubric_item_id))
        prompt = prompt.replace("{{max_score}}", str(item.score))
        prompt = prompt.replace(
            "{{required}}",
            "null" if item.required is None else json.dumps(item.required),
        )
        prompt = prompt.replace("{{criterion}}", item.criterion or "")
        prompt = prompt.replace("{{routing_modality}}", decision.modality.value)
        preferred_op = (
            "harness_trusted_visual_evidence"
            if decision.modality.value == "visual"
            else decision.preferred_op
        )
        prompt = prompt.replace("{{routing_preferred_op}}", preferred_op)
        block = "\n".join(
            f"- path: `{fn}`" for fn in file_names
        ) if file_names else ""
        prompt = re.sub(
            r"\{\{#each deliverable_files\}\}[\s\S]*?\{\{/each\}\}",
            block,
            prompt,
        )
        reference_block = "\n".join(
            f"- path: `{fn}`" for fn in (reference_file_names or [])
        )
        prompt = re.sub(
            r"\{\{#each reference_files\}\}[\s\S]*?\{\{/each\}\}",
            reference_block,
            prompt,
        )
        return prompt

    def _build_initial_prompt(
        self,
        task: TaskRubric,
        item: RubricItem,
        file_names: List[str],
        decision,
        reference_file_names: Optional[List[str]] = None,
    ) -> str:
        prompt = self.prompt_template
        prompt = prompt.replace("{{sector}}", task.sector or "")
        prompt = prompt.replace("{{occupation}}", task.occupation or "")
        prompt = prompt.replace(
            "{{task_prompt_truncated_500}}",
            (task.prompt or "")[:self.task_prompt_truncate],
        )
        prompt = prompt.replace("{{rubric_item_id}}", str(item.rubric_item_id))
        prompt = prompt.replace("{{max_score}}", str(item.score))
        prompt = prompt.replace(
            "{{required}}",
            "null" if item.required is None else json.dumps(item.required),
        )
        prompt = prompt.replace("{{criterion}}", item.criterion or "")
        prompt = prompt.replace("{{routing_modality}}", decision.modality.value)
        preferred_op = (
            "harness_trusted_visual_evidence"
            if decision.modality.value == "visual"
            else decision.preferred_op
        )
        prompt = prompt.replace("{{routing_preferred_op}}", preferred_op)

        block = "\n".join(
            f"- path: `{fn}`" for fn in file_names
        ) if file_names else ""
        prompt = re.sub(
            r"\{\{#each deliverable_files\}\}[\s\S]*?\{\{/each\}\}",
            block,
            prompt,
        )
        reference_block = "\n".join(
            f"- path: `{fn}`" for fn in (reference_file_names or [])
        )
        prompt = re.sub(
            r"\{\{#each reference_files\}\}[\s\S]*?\{\{/each\}\}",
            reference_block,
            prompt,
        )
        return prompt

    def _build_tools_for(self, modality: str) -> List[Dict[str, Any]]:
        read_schema = json.loads(json.dumps(MODEL_READ_DELIVERABLE_TOOL_SCHEMA))
        read_schema["parameters"]["properties"]["op"]["enum"] = list(
            self.model_read_ops
        )
        tools: List[Dict[str, Any]] = [read_schema]
        if modality == "audio" and self.audio_perception is not None:
            tools.append(self._audio_tool_schema())
        return tools

    @staticmethod
    def _audio_tool_schema() -> Dict[str, Any]:
        return {
            "type": "function",
            "name": "audio_judge",
            "description": (
                "Ask the audio sub-judge to grade the criterion against "
                "the head-30s slice of a deliverable audio file. Use "
                "only for AUDIO items."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "criterion": {"type": "string"},
                    "audio_path": {"type": "string"},
                },
                "required": ["criterion", "audio_path"],
                "additionalProperties": False,
            },
        }

    # ------------------------------------------------------------------
    # Tool dispatch
    # ------------------------------------------------------------------

    def _dispatch_tool(
        self,
        function_call: Any,
        deliverable_dir: str,
        allowed_paths: set[str],
    ) -> Dict[str, Any]:
        name = self._fc_name(function_call)
        raw_args = self._fc_arguments(function_call)
        try:
            parsed = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
        except (json.JSONDecodeError, TypeError, ValueError):
            return {"ok": False, "error": "arguments must be a JSON object",
                    "error_type": "bad_args"}
        if not isinstance(parsed, Mapping):
            return {"ok": False, "error": "arguments must be a JSON object",
                    "error_type": "bad_args"}
        args = dict(parsed)

        if name == "read_deliverable":
            op = args.get("op")
            path = args.get("path")
            scope = args.get("scope")
            if op not in self.model_read_ops:
                return {"ok": False, "error": f"unknown op {op!r}",
                        "error_type": "bad_op"}
            if not isinstance(path, str) or path not in allowed_paths:
                return {
                    "ok": False,
                    "error": "path is not in the selected/reference allowlist",
                    "error_type": "bad_path",
                }
            try:
                return read_deliverable(
                    op, path, base_dir=deliverable_dir, scope=scope
                )
            except Exception as exc:  # noqa: BLE001
                return {
                    "ok": False,
                    "error": public_task_error_text(exc),
                    "error_type": "tool_exception",
                }

        if name == "audio_judge":
            if self.audio_perception is None:
                return {"ok": False, "error": "audio sub-judge not configured",
                        "error_type": "no_perception"}
            audio_path = args.get("audio_path")
            if not isinstance(audio_path, str) or audio_path not in allowed_paths:
                return {
                    "ok": False,
                    "error": "audio_path is not in the selected/reference allowlist",
                    "error_type": "bad_path",
                }
            base = Path(deliverable_dir).resolve()
            resolved_audio_path = (base / audio_path).resolve()
            try:
                resolved_audio_path.relative_to(base)
            except ValueError:
                return {
                    "ok": False,
                    "error": "audio_path escapes deliverable_dir",
                    "error_type": "bad_path",
                }
            if not resolved_audio_path.is_file():
                return {
                    "ok": False,
                    "error": "audio_path does not resolve to a file",
                    "error_type": "bad_path",
                }
            try:
                v = self.audio_perception.judge(
                    criterion=args.get("criterion", ""),
                    audio_path=str(resolved_audio_path),
                )
                return {"ok": v.judge_error is None, "data": v.to_dict()}
            except Exception as exc:  # noqa: BLE001
                return {
                    "ok": False,
                    "error": public_provider_error_text(exc),
                    "error_type": "perception_exception",
                }

        return {"ok": False, "error": f"unknown function {name!r}",
                "error_type": "bad_function"}

    def _guard_upstream_call(self) -> None:
        if self.before_upstream_call is not None:
            self.before_upstream_call()

    @staticmethod
    def _accumulate_perception_result(
        instrumentation: VisualPrepassResult,
        result: Mapping[str, Any],
    ) -> None:
        data = result.get("data") or {}
        if not isinstance(data, Mapping):
            instrumentation.usage_complete = False
            return
        try:
            instrumentation.perception_call_count += int(
                data.get("api_call_count", 0) or 0
            )
            instrumentation.perception_input_tokens += int(
                data.get("input_tokens", 0) or 0
            )
            instrumentation.perception_output_tokens += int(
                data.get("output_tokens", 0) or 0
            )
            instrumentation.perception_cached_tokens += int(
                data.get("cached_tokens", 0) or 0
            )
            instrumentation.perception_total_latency_ms += float(
                data.get("latency_ms", 0.0) or 0.0
            )
        except (TypeError, ValueError):
            instrumentation.usage_complete = False
            return
        instrumentation.usage_complete = (
            instrumentation.usage_complete
            and bool(data.get("usage_complete", False))
        )

    def preflight_visual(
        self,
        *,
        item: RubricItem,
        deliverable_dir: str,
        file_names: List[str],
    ) -> VisualPrepassResult:
        """Render and perceive every bounded visual path before main judging."""
        result = VisualPrepassResult()
        if self.vision_perception is None:
            result.judge_error = "required_visual_perception_unconfigured"
            return result

        planned_names, planning_error = self.validate_planned_visual_names(
            file_names
        )
        if planning_error is not None:
            result.judge_error = planning_error
            return result

        planned: List[Tuple[str, Path, Dict[str, int]]] = []
        base = Path(deliverable_dir).resolve()
        for file_name in planned_names:
            scope = _VISUAL_RENDER_SCOPES[Path(file_name).suffix.lower()]
            source = (base / file_name).resolve()
            try:
                source.relative_to(base)
            except ValueError:
                result.judge_error = (
                    f"required_visual_bad_path:{file_name}:escapes deliverable_dir"
                )
                return result
            if not source.is_file():
                result.judge_error = (
                    f"required_visual_bad_path:{file_name}:file not found"
                )
                return result
            normalized_name = source.relative_to(base).as_posix()
            planned.append((normalized_name, source, dict(scope)))

        remaining = self._remaining_vision_calls()
        if remaining is not None and remaining < len(planned):
            result.judge_error = (
                "required_visual_cap_preflight_failed:"
                f"planned={len(planned)},remaining={remaining}"
            )
            return result

        for file_name, source, scope in planned:
            try:
                source_sha256 = self._sha256_file(source)
            except Exception as exc:  # noqa: BLE001
                result.judge_error = (
                    f"required_visual_hash_failed:{file_name}:"
                    f"{public_task_error_text(exc)}"
                )
                return result

            render_started = time.perf_counter()
            result.render_call_count += 1
            result.tools_used.append("harness_render_to_image")
            try:
                rendered = read_deliverable(
                    "render_to_image",
                    file_name,
                    base_dir=deliverable_dir,
                    scope=scope,
                )
            except Exception as exc:  # noqa: BLE001
                rendered = {
                    "ok": False,
                    "error_type": "render_exception",
                    "error": public_task_error_text(exc),
                }
            render_latency_ms = (
                time.perf_counter() - render_started
            ) * 1000.0
            result.render_total_latency_ms += render_latency_ms
            if not isinstance(rendered, Mapping) or not rendered.get("ok"):
                error_type = (
                    rendered.get("error_type", "render_error")
                    if isinstance(rendered, Mapping) else "bad_render_envelope"
                )
                error = (
                    rendered.get("error", "unknown_error")
                    if isinstance(rendered, Mapping) else "non-object render result"
                )
                result.judge_error = (
                    "required_visual_render_failed:"
                    f"{file_name}:{error_type}:{error}"
                )
                return result

            render_data = rendered.get("data") or {}
            if not isinstance(render_data, Mapping):
                result.judge_error = (
                    f"required_visual_render_failed:{file_name}:bad_render_data"
                )
                return result
            image_b64 = render_data.get("base64")
            if not isinstance(image_b64, str) or not image_b64:
                result.judge_error = (
                    f"required_visual_render_failed:{file_name}:missing_image_bytes"
                )
                return result

            result.tools_used.append("harness_vision_perception")
            try:
                verdict = self.vision_perception.judge(
                    criterion=item.criterion,
                    image_b64=image_b64,
                )
                verdict_data = verdict.to_dict()
            except Exception as exc:  # noqa: BLE001
                result.usage_complete = False
                result.judge_error = (
                    "required_visual_perception_failed:"
                    f"{file_name}:{public_provider_error_text(exc)}"
                )
                return result
            if not isinstance(verdict_data, Mapping):
                result.usage_complete = False
                result.judge_error = (
                    f"required_visual_perception_failed:{file_name}:bad_verdict"
                )
                return result
            verdict_payload = dict(verdict_data)
            try:
                api_calls = int(
                    verdict_payload.get("api_call_count", 1) or 0
                )
                result.perception_call_count += api_calls
                result.perception_input_tokens += int(
                    verdict_payload.get("input_tokens", 0) or 0
                )
                result.perception_output_tokens += int(
                    verdict_payload.get("output_tokens", 0) or 0
                )
                result.perception_cached_tokens += int(
                    verdict_payload.get("cached_tokens", 0) or 0
                )
                result.perception_total_latency_ms += float(
                    verdict_payload.get("latency_ms", 0.0) or 0.0
                )
            except (TypeError, ValueError):
                result.usage_complete = False
                result.judge_error = (
                    "required_visual_perception_failed:"
                    f"{file_name}:malformed_usage"
                )
                return result
            result.usage_complete = result.usage_complete and bool(
                verdict_payload.get("usage_complete", False)
            )
            vision_verdict = verdict_payload.get("verdict")
            vision_error = verdict_payload.get("judge_error")
            if vision_error or vision_verdict not in {"pass", "partial", "fail"}:
                result.judge_error = (
                    "required_visual_perception_failed:"
                    f"{file_name}:{vision_error or 'invalid_vision_envelope'}"
                )
                return result

            renderer_metadata = {
                key: render_data[key]
                for key in _RENDERER_METADATA_KEYS
                if key in render_data
            }
            result.entries.append(
                VisualEvidenceEntry(
                    path=file_name,
                    source_sha256=source_sha256,
                    scope=dict(render_data.get("scope") or scope),
                    renderer_metadata=renderer_metadata,
                    coverage_metadata=self._coverage_metadata(
                        item, render_data
                    ),
                    vision=verdict_payload,
                    render_latency_ms=render_latency_ms,
                )
            )
        return result

    def _remaining_vision_calls(self) -> Optional[int]:
        remaining = getattr(self.vision_perception, "remaining_calls", None)
        if isinstance(remaining, int):
            return max(0, remaining)
        call_cap = getattr(self.vision_perception, "call_cap", None)
        calls_used = getattr(self.vision_perception, "calls_used", None)
        if isinstance(call_cap, int) and isinstance(calls_used, int):
            return max(0, call_cap - calls_used)
        return None

    @staticmethod
    def _planned_visual_names(file_names: List[str]) -> List[str]:
        return sorted(
            dict.fromkeys(file_names), key=lambda name: (name.casefold(), name)
        )

    @classmethod
    def planned_supported_visual_names(cls, file_names: List[str]) -> List[str]:
        """Return the stable, bounded-call candidates for task budgeting."""
        return [
            name
            for name in cls._planned_visual_names(file_names)
            if Path(name).suffix.lower() in _VISUAL_RENDER_SCOPES
        ]

    @classmethod
    def validate_planned_visual_names(
        cls, file_names: List[str]
    ) -> Tuple[List[str], Optional[str]]:
        """Apply the exact runtime target, cap, and format checks."""
        planned_names = cls.planned_supported_visual_names(file_names)
        if not planned_names:
            return [], "required_visual_render_target_unavailable"
        if len(planned_names) > _VISUAL_FILE_CAP:
            return planned_names, (
                "required_visual_file_cap_exceeded:"
                f"planned={len(planned_names)},cap={_VISUAL_FILE_CAP}"
            )
        return planned_names, None

    @staticmethod
    def _sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _coverage_metadata(
        item: RubricItem, render_data: Mapping[str, Any]
    ) -> Dict[str, Any]:
        source_kind = str(render_data.get("source_kind") or "")
        total_key = {
            "pdf": "source_page_count",
            "pptx": "source_slide_count",
            "xlsx": "converted_page_count",
            "image": None,
        }.get(source_kind)
        total_surfaces = 1 if source_kind == "image" else (
            render_data.get(total_key) if total_key else None
        )
        return {
            "coverage_mode": "sampled_first_surface",
            "criterion_scope": (
                "overall_style"
                if is_overall_style_criterion(item.criterion)
                else "generic_visual_fallback"
            ),
            "sampled_surface_count": 1,
            "total_surface_count": total_surfaces,
        }

    @staticmethod
    def _visual_tools_used(prepass: VisualPrepassResult) -> List[str]:
        return list(prepass.tools_used)

    # ------------------------------------------------------------------
    # Response item shape adapters
    #
    # The Azure OpenAI Responses SDK returns ``response.output`` as a
    # list of pydantic-like objects. To keep this module testable
    # against simple namespaces / dicts we treat both shapes uniformly.
    # ------------------------------------------------------------------

    @staticmethod
    def _item_type(obj: Any) -> str:
        if isinstance(obj, dict):
            return str(obj.get("type", ""))
        return str(getattr(obj, "type", ""))

    @staticmethod
    def _fc_name(fc: Any) -> str:
        if isinstance(fc, dict):
            return str(fc.get("name", ""))
        return str(getattr(fc, "name", ""))

    @staticmethod
    def _fc_arguments(fc: Any) -> Any:
        if isinstance(fc, dict):
            return fc.get("arguments", "{}")
        return getattr(fc, "arguments", "{}")

    @staticmethod
    def _fc_call_id(fc: Any) -> str:
        if isinstance(fc, dict):
            return str(fc.get("call_id", ""))
        return str(getattr(fc, "call_id", ""))

    @staticmethod
    def _serialize_output_item(output_item: Any) -> Dict[str, Any]:
        """Serialize an SDK/dict response item for tool continuation."""
        if isinstance(output_item, Mapping):
            return dict(output_item)
        model_dump = getattr(output_item, "model_dump", None)
        if callable(model_dump):
            try:
                try:
                    dumped = model_dump(mode="json", exclude_none=True)
                except TypeError:
                    dumped = model_dump()
            except Exception:  # noqa: BLE001
                dumped = None
            if isinstance(dumped, Mapping):
                return dict(dumped)
        fields = (
            "type", "id", "status", "role", "content", "summary",
            "call_id", "name", "arguments",
        )
        return {
            field_name: getattr(output_item, field_name)
            for field_name in fields
            if hasattr(output_item, field_name)
            and getattr(output_item, field_name) is not None
        }

    @classmethod
    def _function_call_output_message(
        cls, fc: Any, result: Dict[str, Any]
    ) -> Dict[str, Any]:
        try:
            output = json.dumps(result)
        except (TypeError, ValueError) as exc:
            output = json.dumps({
                "ok": False,
                "error": f"tool output serialization failed: {type(exc).__name__}",
                "error_type": "tool_serialization_error",
            })
        return {
            "type": "function_call_output",
            "call_id": cls._fc_call_id(fc),
            "output": output,
        }

    @staticmethod
    def _extract_text(msg: Any) -> str:
        if isinstance(msg, dict):
            content = msg.get("content")
        else:
            content = getattr(msg, "content", None)
        if isinstance(content, str):
            return content
        if isinstance(content, list) and content:
            head = content[0]
            if isinstance(head, dict):
                return str(head.get("text", "") or "")
            return str(getattr(head, "text", "") or "")
        return ""

    # ------------------------------------------------------------------
    # Final verdict parsing
    # ------------------------------------------------------------------

    def _build_result(
        self,
        *,
        item: RubricItem,
        routing_modality: str,
        final_text: str,
        tool_calls_made: int,
        iterations: int,
        latency_ms: float,
        input_tokens: int,
        output_tokens: int,
        cached_tokens: int,
        judge_error: Optional[str],
        tools_used: Optional[List[str]] = None,
        main_api_call_count: int = 0,
        visual_prepass: Optional[VisualPrepassResult] = None,
        usage_complete: bool = True,
    ) -> ToolCallingResult:
        tools_used = list(tools_used or [])
        prepass = visual_prepass or VisualPrepassResult()
        perception_called = (
            prepass.perception_call_count > 0
            or any(t == "audio_judge" for t in tools_used)
        )
        instrumentation = {
            "main_api_call_count": main_api_call_count,
            "perception_call_count": prepass.perception_call_count,
            "perception_input_tokens": prepass.perception_input_tokens,
            "perception_output_tokens": prepass.perception_output_tokens,
            "perception_cached_tokens": prepass.perception_cached_tokens,
            "perception_total_latency_ms": prepass.perception_total_latency_ms,
            "render_call_count": prepass.render_call_count,
            "render_total_latency_ms": prepass.render_total_latency_ms,
            "usage_complete": usage_complete and prepass.usage_complete,
            "visual_provenance": prepass.to_provenance(),
        }
        if judge_error is not None or not final_text.strip():
            return ToolCallingResult(
                verdict="judge_error",
                partial_score=0.0,
                awarded_score=0.0,
                evidence="",
                confidence=None,
                reasoning="",
                judge_error=judge_error or "empty_final_text",
                tool_calls_made=tool_calls_made,
                iterations=iterations,
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cached_tokens=cached_tokens,
                routing_modality=routing_modality,
                raw_text=final_text,
                tools_used=tools_used,
                perception_called=perception_called,
                score_excluded=True,
                **instrumentation,
            )

        parsed = _safe_json_loads(final_text)
        if parsed is None:
            return ToolCallingResult(
                verdict="judge_error",
                partial_score=0.0,
                awarded_score=0.0,
                evidence="",
                confidence=None,
                reasoning="",
                judge_error="final_json_parse_failed",
                tool_calls_made=tool_calls_made,
                iterations=iterations,
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cached_tokens=cached_tokens,
                routing_modality=routing_modality,
                raw_text=final_text,
                tools_used=tools_used,
                perception_called=perception_called,
                score_excluded=True,
                **instrumentation,
            )

        validated_envelope = _validated_final_envelope(parsed)
        if validated_envelope is None:
            return ToolCallingResult(
                verdict="judge_error",
                partial_score=0.0,
                awarded_score=0.0,
                evidence="",
                confidence=None,
                reasoning="",
                judge_error="invalid_final_envelope",
                tool_calls_made=tool_calls_made,
                iterations=iterations,
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cached_tokens=cached_tokens,
                routing_modality=routing_modality,
                raw_text=final_text,
                tools_used=tools_used,
                perception_called=perception_called,
                score_excluded=True,
                **instrumentation,
            )

        verdict, partial, confidence = validated_envelope

        evidence = str(parsed.get("evidence") or "").strip()[:200]
        if not evidence:
            verdict = "fail"
            partial = 0.0
            evidence = "missing evidence"

        reasoning = str(parsed.get("reasoning") or "")[:300]

        awarded = float(item.score) * partial
        return ToolCallingResult(
            verdict=verdict,
            partial_score=partial,
            awarded_score=awarded,
            evidence=evidence,
            confidence=confidence,
            reasoning=reasoning,
            judge_error=None,
            tool_calls_made=tool_calls_made,
            iterations=iterations,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached_tokens,
            routing_modality=routing_modality,
            raw_text=final_text,
            tools_used=tools_used,
            perception_called=perception_called,
            score_excluded=False,
            **instrumentation,
        )
