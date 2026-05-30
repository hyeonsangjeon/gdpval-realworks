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

    while not done and iterations < cap:
        response = client.responses.create(
            model=...,
            input=messages,
            tools=[READ_DELIVERABLE_TOOL_SCHEMA, ...],
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

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from core.grader_routing import classify_criterion
from core.rubric_loader import RubricItem, TaskRubric
from core.tools import (
    READ_DELIVERABLE_OPS,
    READ_DELIVERABLE_TOOL_SCHEMA,
    read_deliverable,
)

logger = logging.getLogger(__name__)


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


def _safe_json_loads(text: str) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(_strip_code_fence(text))
    except json.JSONDecodeError:
        # try to recover the first {...} block
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
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
        model:                   deployment name (e.g. ``"gpt-5.4"``).
        prompt_template:         contents of ``prompts/grader_judge_v2.md``
                                 — must contain a ``<!-- ===SPLIT=== -->``
                                 marker separating the stable scaffold
                                 (sent as ``instructions=``, cached server-
                                 side) from the per-item variable content.
        reasoning_effort:        ``"low" | "medium" | "high"``.
        max_output_tokens:       per-call output budget.
        per_item_tool_call_cap:  hard upper bound on tool dispatches for
                                 a single rubric item. Loop exits with
                                 ``judge_error="tool_cap_exceeded"`` past
                                 this number.
        max_iterations:          hard upper bound on response.create
                                 iterations (one tool round = one
                                 iteration).
        vision_perception:       optional ``VisionPerception`` instance
                                 (task 205). When provided AND the routing
                                 modality is VISUAL, the harness will
                                 expose a ``vision_judge`` tool to the
                                 model.
        audio_perception:        optional ``AudioPerception`` instance
                                 (task 206), same shape.
        task_prompt_truncate:    chars kept of the original task prompt.
        prompt_cache_key:        optional stable key passed to
                                 ``responses.create(prompt_cache_key=...)``.
                                 Default = ``"gdpval_v2_judge"``.
        compact_threshold:       optional Azure Responses API
                                 ``context_management.auto_compact_threshold``
                                 token count. Default = 60000 (only the
                                 long tool-loop tasks like the 49-call
                                 monster trip it; light/medium tasks stay
                                 fully cacheable).
    """

    client: Any
    model: str
    prompt_template: str
    reasoning_effort: str = "medium"
    max_output_tokens: int = 2400
    per_item_tool_call_cap: int = 8
    max_iterations: int = 10
    vision_perception: Any = None
    audio_perception: Any = None
    task_prompt_truncate: int = 500
    prompt_cache_key: str = "gdpval_v2_judge"
    compact_threshold: Optional[int] = 60000

    # Cached: split prompt template into stable + variable halves once at
    # construction (or first use). The stable half is the ``instructions=``
    # argument across every call — byte-identical → server-side cache hit.
    _stable_instructions: Optional[str] = field(default=None, init=False)
    _variable_template: Optional[str] = field(default=None, init=False)

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
    ) -> ToolCallingResult:
        """Grade one rubric item by letting the judge inspect files via tools."""
        decision = classify_criterion(item.criterion)
        # PR3 step 1a — split the prompt template into stable scaffold
        # (cached server-side via instructions=) and per-item variable.
        self._ensure_split()
        variable_prompt = self._render_variable(task, item, file_names, decision)
        tools = self._build_tools_for(decision.modality.value)

        messages: List[Dict[str, Any]] = [
            {"role": "user", "content": variable_prompt}
        ]
        tool_calls_made = 0
        iterations = 0
        input_tok_total = 0
        output_tok_total = 0
        cached_tok_total = 0
        wall_start = time.time()
        final_text = ""
        judge_error: Optional[str] = None

        while iterations < self.max_iterations:
            iterations += 1
            try:
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
                if self.compact_threshold:
                    create_kwargs["context_management"] = {
                        "auto_compact_threshold": int(self.compact_threshold),
                    }
                response = self.client.responses.create(**create_kwargs)
            except TypeError as exc:
                # SDK older than expected — fall back to the legacy call
                # shape (no instructions / cache_key / compaction). Log
                # once and keep going so the run isn't blocked.
                logger.warning(
                    "ToolCallingJudge SDK fallback (%s); using legacy call shape",
                    exc,
                )
                try:
                    response = self.client.responses.create(
                        model=self.model,
                        input=messages,
                        tools=tools,
                        reasoning={"effort": self.reasoning_effort},
                        max_output_tokens=self.max_output_tokens,
                    )
                except Exception as exc2:  # noqa: BLE001
                    judge_error = f"{type(exc2).__name__}: {exc2}"
                    break
            except Exception as exc:  # noqa: BLE001
                judge_error = f"{type(exc).__name__}: {exc}"
                logger.warning(
                    "ToolCallingJudge upstream call failed for %s: %s",
                    item.rubric_item_id, judge_error,
                )
                break

            usage = getattr(response, "usage", None)
            input_tok_total += int(getattr(usage, "input_tokens", 0) or 0)
            output_tok_total += int(getattr(usage, "output_tokens", 0) or 0)
            # PR3 Step 0 — cached_tokens (Azure Responses API automatic prompt
            # caching). Field path: usage.input_tokens_details.cached_tokens.
            # Older SDKs may not expose the details object; default 0.
            details = getattr(usage, "input_tokens_details", None)
            if details is not None:
                cached_tok_total += int(getattr(details, "cached_tokens", 0) or 0)

            output_items = list(getattr(response, "output", []) or [])
            function_calls = [o for o in output_items
                              if self._item_type(o) == "function_call"]
            messages_out = [o for o in output_items
                            if self._item_type(o) == "message"]

            if function_calls:
                # Echo every assistant function_call into the next input
                # batch, then append our tool outputs.
                for fc in function_calls:
                    messages.append(self._function_call_message(fc))
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
                    result = self._dispatch_tool(fc, deliverable_dir, decision)
                    messages.append(self._function_call_output_message(fc, result))
                # Loop again to let the model react to the tool outputs.
                continue

            # No tool calls — read the final message and stop.
            if messages_out:
                final_text = self._extract_text(messages_out[0])
            else:
                final_text = getattr(response, "output_text", "") or ""
            break
        else:
            judge_error = "max_iterations_exceeded"

        latency_ms = (time.time() - wall_start) * 1000.0
        return self._build_result(
            item=item,
            routing_modality=decision.modality.value,
            final_text=final_text,
            tool_calls_made=tool_calls_made,
            iterations=iterations,
            latency_ms=latency_ms,
            input_tokens=input_tok_total,
            output_tokens=output_tok_total,
            cached_tokens=cached_tok_total,
            judge_error=judge_error,
        )

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
        prompt = prompt.replace("{{routing_preferred_op}}", decision.preferred_op)
        block = "\n".join(
            f"- path: `{fn}`" for fn in file_names
        ) if file_names else ""
        prompt = re.sub(
            r"\{\{#each deliverable_files\}\}[\s\S]*?\{\{/each\}\}",
            block,
            prompt,
        )
        return prompt

    def _build_initial_prompt(
        self,
        task: TaskRubric,
        item: RubricItem,
        file_names: List[str],
        decision,
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
        prompt = prompt.replace("{{routing_preferred_op}}", decision.preferred_op)

        block = "\n".join(
            f"- path: `{fn}`" for fn in file_names
        ) if file_names else ""
        prompt = re.sub(
            r"\{\{#each deliverable_files\}\}[\s\S]*?\{\{/each\}\}",
            block,
            prompt,
        )
        return prompt

    def _build_tools_for(self, modality: str) -> List[Dict[str, Any]]:
        tools: List[Dict[str, Any]] = [READ_DELIVERABLE_TOOL_SCHEMA]
        if modality == "visual" and self.vision_perception is not None:
            tools.append(self._vision_tool_schema())
        if modality == "audio" and self.audio_perception is not None:
            tools.append(self._audio_tool_schema())
        return tools

    @staticmethod
    def _vision_tool_schema() -> Dict[str, Any]:
        return {
            "type": "function",
            "name": "vision_judge",
            "description": (
                "Ask the vision sub-judge to grade the criterion against "
                "a PNG image you got back from read_deliverable(op="
                "'render_to_image', ...). Use only for VISUAL items."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "criterion": {"type": "string"},
                    "image_b64": {"type": "string"},
                    "cache_key": {"type": ["string", "null"]},
                },
                "required": ["criterion", "image_b64"],
                "additionalProperties": False,
            },
        }

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
        decision,
    ) -> Dict[str, Any]:
        name = self._fc_name(function_call)
        raw_args = self._fc_arguments(function_call)
        try:
            args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args or {})
        except json.JSONDecodeError:
            return {"ok": False, "error": "invalid JSON arguments",
                    "error_type": "bad_args"}

        if name == "read_deliverable":
            op = args.get("op")
            path = args.get("path")
            scope = args.get("scope")
            if op not in READ_DELIVERABLE_OPS:
                return {"ok": False, "error": f"unknown op {op!r}",
                        "error_type": "bad_op"}
            return read_deliverable(op, path, base_dir=deliverable_dir, scope=scope)

        if name == "vision_judge":
            if self.vision_perception is None:
                return {"ok": False, "error": "vision sub-judge not configured",
                        "error_type": "no_perception"}
            v = self.vision_perception.judge(
                criterion=args.get("criterion", ""),
                image_b64=args.get("image_b64", ""),
                cache_key=args.get("cache_key"),
            )
            return {"ok": v.judge_error is None, "data": v.to_dict()}

        if name == "audio_judge":
            if self.audio_perception is None:
                return {"ok": False, "error": "audio sub-judge not configured",
                        "error_type": "no_perception"}
            v = self.audio_perception.judge(
                criterion=args.get("criterion", ""),
                audio_path=args.get("audio_path", ""),
            )
            return {"ok": v.judge_error is None, "data": v.to_dict()}

        return {"ok": False, "error": f"unknown function {name!r}",
                "error_type": "bad_function"}

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

    @classmethod
    def _function_call_message(cls, fc: Any) -> Dict[str, Any]:
        """Echo an assistant function_call back into the next input batch."""
        return {
            "type": "function_call",
            "call_id": cls._fc_call_id(fc),
            "name": cls._fc_name(fc),
            "arguments": cls._fc_arguments(fc),
        }

    @classmethod
    def _function_call_output_message(
        cls, fc: Any, result: Dict[str, Any]
    ) -> Dict[str, Any]:
        return {
            "type": "function_call_output",
            "call_id": cls._fc_call_id(fc),
            "output": json.dumps(result),
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
    ) -> ToolCallingResult:
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

        evidence = str(parsed.get("evidence") or "").strip()[:200]
        if not evidence:
            verdict = "fail"
            partial = 0.0
            evidence = "missing evidence"

        confidence: Optional[float] = None
        if parsed.get("confidence") is not None:
            try:
                confidence = max(0.0, min(1.0, float(parsed.get("confidence"))))
            except (TypeError, ValueError):
                confidence = None
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
        )
