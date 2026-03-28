"""NarrativeAnalyzer — Standalone Responses API module for GPT-5.4 Pro.

Generates rich narrative analysis (overview, quality_analysis, failure_patterns,
recommendations) for experiment reports using a 2-call sequential pattern.

This module is intentionally standalone — it does NOT import or depend on
core/llm_client.py (which uses Chat Completions API). GPT-5.4 Pro only
supports the Responses API, so this module creates its own AzureOpenAI client.

Usage:
    from core.narrative_analyzer import create_narrative_analyzer

    analyzer = create_narrative_analyzer()
    result = analyzer.analyze(data, summary, sectors, task_results, error_tasks)
    print(result.overview)
"""

import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field

from openai import AzureOpenAI

from azure.identity import DefaultAzureCredential, get_bearer_token_provider

logger = logging.getLogger(__name__)

# ─── Result Dataclass ─────────────────────────────────────────────────────


@dataclass
class NarrativeResult:
    """Result of a 2-call narrative analysis."""

    overview: str = ""
    quality_analysis: str = ""
    failure_patterns: str = ""
    recommendations: str = ""
    call_1_latency_ms: float = 0.0
    call_2_latency_ms: float = 0.0
    total_tokens: dict = field(default_factory=lambda: {"input": 0, "output": 0})


# ─── NarrativeAnalyzer ────────────────────────────────────────────────────


class NarrativeAnalyzer:
    """GPT-5.4 Pro narrative generator using Azure OpenAI Responses API.

    Architecture:
        Call 1: Sector-level analysis → overview + quality_analysis
        Call 2: Deep analysis (all 220 tasks) → failure_patterns + recommendations

    Args:
        endpoint:    Azure OpenAI endpoint URL
        api_version: API version (default: 2025-04-01-preview)
        timeout:     Client-level timeout in seconds (default: 10000)
        model:       Deployment name (default: gpt-5.4-pro)
    """

    DEFAULT_MODEL = "gpt-5.4-pro"
    DEFAULT_API_VERSION = "2025-04-01-preview"

    def __init__(
        self,
        endpoint: str,
        api_version: str = DEFAULT_API_VERSION,
        timeout: int = 10000,
        model: str = DEFAULT_MODEL,
    ):
        credential = DefaultAzureCredential()
        token_provider = get_bearer_token_provider(
            credential, "https://cognitiveservices.azure.com/.default"
        )
        self.client = AzureOpenAI(
            azure_endpoint=endpoint,
            azure_ad_token_provider=token_provider,
            api_version=api_version,
            timeout=timeout,
        )
        self.model = model
        self._heartbeat_active = False
        self._heartbeat_thread: threading.Thread | None = None

    # ── Public API ─────────────────────────────────────────────────────

    def analyze(
        self,
        data: dict,
        summary: dict,
        sector_breakdown: list[dict],
        task_results: list[dict],
        error_tasks: list[dict],
    ) -> NarrativeResult:
        """Run 2-call sequential analysis and return NarrativeResult.

        Args:
            data:             Experiment metadata dict (meta fields)
            summary:          Summary stats dict
            sector_breakdown: List of per-sector stat dicts
            task_results:     ALL task result dicts (full 220)
            error_tasks:      Error task dicts with error messages

        Returns:
            NarrativeResult with all four narrative sections + metrics
        """
        total_input = 0
        total_output = 0

        # ── Call 1: Sector Analysis ────────────────────────────────────
        print("   ── Call 1: Sector Analysis ──")
        self._start_heartbeat()
        try:
            call1_result, call1_latency, c1_in, c1_out = self._call_1_sector_analysis(
                data, summary, sector_breakdown
            )
        finally:
            self._stop_heartbeat()

        total_input += c1_in
        total_output += c1_out
        print(f"   ✅ Call 1 complete ({call1_latency:,.0f}ms, {c1_in:,}+{c1_out:,} tokens)")

        # ── Call 2: Deep Analysis (all tasks) ──────────────────────────
        print("   ── Call 2: Deep Analysis (all tasks) ──")
        self._start_heartbeat()
        try:
            call2_result, call2_latency, c2_in, c2_out = self._call_2_deep_analysis(
                call1_result, task_results, error_tasks
            )
        finally:
            self._stop_heartbeat()

        total_input += c2_in
        total_output += c2_out
        print(f"   ✅ Call 2 complete ({call2_latency:,.0f}ms, {c2_in:,}+{c2_out:,} tokens)")

        return NarrativeResult(
            overview=call1_result.get("overview", ""),
            quality_analysis=call1_result.get("quality_analysis", ""),
            failure_patterns=call2_result.get("failure_patterns", ""),
            recommendations=call2_result.get("recommendations", ""),
            call_1_latency_ms=call1_latency,
            call_2_latency_ms=call2_latency,
            total_tokens={"input": total_input, "output": total_output},
        )

    # ── Call 1 ─────────────────────────────────────────────────────────

    def _call_1_sector_analysis(
        self, data: dict, summary: dict, sector_breakdown: list[dict]
    ) -> tuple[dict, float, int, int]:
        """Sector-level analysis → overview + quality_analysis."""

        meta = data.get("meta", data)  # support both report_data and raw data

        sector_lines = "\n".join(
            f"  - {s['sector']}: {s['success']}/{s['total']} success "
            f"(avg QA {s['avg_qa_score']:.1f}/10, avg latency {s['avg_latency_ms']}ms)"
            for s in sector_breakdown
        )

        user_prompt = f"""You are a technical evaluator reviewing an LLM experiment run.

Experiment: {meta.get('experiment_name', '')} ({meta.get('experiment_id', '')})
Condition: {meta.get('condition_name', '')}
Model: {meta.get('model', '')}
Execution Mode: {meta.get('execution_mode', '')}
Date: {meta.get('date', meta.get('started_at', ''))}

Summary:
  - Total tasks: {summary['total_tasks']}
  - Success: {summary['success_count']} ({summary['success_rate_pct']}%)
  - Errors: {summary['error_count']}
  - Retried tasks: {summary['retried_count']}
  - Avg QA score: {summary['avg_qa_score']}/10 (min {summary['min_qa_score']}, max {summary['max_qa_score']})
  - Avg latency: {summary['avg_latency_ms']}ms

Sector breakdown:
{sector_lines}

IMPORTANT CONSTRAINTS:
- Grading scores do NOT exist yet. Do NOT mention or predict grades.
- Focus ONLY on: task completion, Self-QA scores, latency patterns, sector/occupation observations, deliverable file generation quality.
- Use "self-assessed confidence" / "LLM-evaluated quality" framing.
- Write as a technical evaluator, NOT a marketer.
- Be concise and factual.

Return ONLY valid JSON (no markdown code fences) with these exact keys:
{{
  "overview": "3-4 paragraphs: what experiment was run, task execution outcomes based on Self-QA confidence scores, and key highlights. Use language like 'self-assessed confidence', 'task completion rate', 'LLM-evaluated quality'.",
  "quality_analysis": "3-4 paragraphs: QA score distribution patterns, notable sector-level differences, occupation-specific observations, latency correlations with quality."
}}"""

        system = "You are a precise technical evaluator reviewing an LLM experiment run. Return only valid JSON."

        text, latency_ms, in_tok, out_tok = self._call_responses_api(system, user_prompt)
        parsed = self._parse_response(text, expected_keys=["overview", "quality_analysis"])
        return parsed, latency_ms, in_tok, out_tok

    # ── Call 2 ─────────────────────────────────────────────────────────

    def _call_2_deep_analysis(
        self, call1_result: dict, task_results: list[dict], error_tasks: list[dict]
    ) -> tuple[dict, float, int, int]:
        """Deep analysis with ALL task results → failure_patterns + recommendations."""

        # Build compact task details for ALL tasks
        task_details = []
        for t in task_results:
            task_details.append({
                "task_id": t["task_id"],
                "sector": t["sector"],
                "occupation": t["occupation"],
                "status": t["status"],
                "qa_score": t.get("qa_score"),
                "qa_issues": t.get("qa_issues", []),
                "qa_suggestion": t.get("qa_suggestion", ""),
                "latency_ms": t.get("latency_ms", 0),
                "retried": t.get("retried", False),
                "files_count": t.get("files_count", 0),
                "deliverable_summary": (t.get("deliverable_summary") or "")[:200],
            })

        task_json = json.dumps(task_details, ensure_ascii=False)
        error_json = json.dumps(error_tasks, ensure_ascii=False) if error_tasks else "[]"

        user_prompt = f"""CONTEXT FROM PRIOR ANALYSIS:

Overview:
{call1_result.get('overview', '')}

Quality Analysis:
{call1_result.get('quality_analysis', '')}

FULL TASK RESULTS ({len(task_results)} tasks):
{task_json}

ERROR TASKS ({len(error_tasks)} errors):
{error_json}

ANALYSIS INSTRUCTIONS:
1. Examine ALL {len(task_results)} tasks — not just failures.
2. Identify failure patterns by comparing failed/low-QA tasks against successful ones.
3. Look for: sector clusters, occupation patterns, retry effectiveness, latency correlations, deliverable type issues.
4. Provide concrete, actionable recommendations referencing specific patterns found.
5. Reference specific task_ids as evidence.

Return ONLY valid JSON (no markdown code fences) with these exact keys:
{{
  "failure_patterns": "3-4 paragraphs: categorize failures by type. Identify sector/occupation clusters. Discuss retried-but-not-improved tasks. Note correlations between task complexity and failure mode. Reference specific task_ids.",
  "recommendations": "3-4 actionable paragraphs: concrete suggestions for model config, prompt engineering, execution environment, and QA threshold tuning. Reference specific patterns found."
}}"""

        system = "You are a precise technical evaluator specializing in deep failure analysis and actionable recommendations. Return only valid JSON."

        text, latency_ms, in_tok, out_tok = self._call_responses_api(
            system, user_prompt, max_output_tokens=8192
        )
        parsed = self._parse_response(text, expected_keys=["failure_patterns", "recommendations"])
        return parsed, latency_ms, in_tok, out_tok

    # ── Responses API Call ─────────────────────────────────────────────

    def _call_responses_api(
        self, system_prompt: str, user_prompt: str, max_output_tokens: int = 4096
    ) -> tuple[str, float, int, int]:
        """Call Azure OpenAI Responses API.

        Returns:
            (text, latency_ms, input_tokens, output_tokens)
        """
        start = time.time()
        response = self.client.responses.create(
            model=self.model,
            instructions=system_prompt,
            input=user_prompt,
            max_output_tokens=max_output_tokens,
        )
        latency_ms = (time.time() - start) * 1000

        text = getattr(response, "output_text", "") or ""
        usage = getattr(response, "usage", None)
        input_tokens = getattr(usage, "input_tokens", 0) if usage else 0
        output_tokens = getattr(usage, "output_tokens", 0) if usage else 0

        return text, latency_ms, input_tokens, output_tokens

    # ── Heartbeat ──────────────────────────────────────────────────────

    def _start_heartbeat(self) -> None:
        """Start daemon heartbeat thread (30s interval stdout print)."""
        self._heartbeat_active = True

        def _beat():
            while self._heartbeat_active:
                time.sleep(30)
                if self._heartbeat_active:
                    print(
                        f"   💓 [{time.strftime('%H:%M:%S')}] waiting for Pro response...",
                        flush=True,
                    )

        self._heartbeat_thread = threading.Thread(target=_beat, daemon=True)
        self._heartbeat_thread.start()

    def _stop_heartbeat(self) -> None:
        """Stop heartbeat thread and wait for it to finish."""
        self._heartbeat_active = False
        if self._heartbeat_thread is not None:
            self._heartbeat_thread.join(timeout=35)
        self._heartbeat_thread = None

    # ── JSON Parsing ───────────────────────────────────────────────────

    @staticmethod
    def _parse_response(raw_text: str, expected_keys: list[str] | None = None) -> dict:
        """Parse JSON from LLM response, stripping markdown fences if present.

        Args:
            raw_text:      Raw response text from the API
            expected_keys: Keys to ensure exist in result (filled with "" if missing)

        Returns:
            Parsed dict. On parse failure, returns dict with expected_keys set to "".
        """
        text = raw_text.strip()

        # Strip markdown code fences
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[-1].strip() == "```":
                text = "\n".join(lines[1:-1])
            else:
                text = "\n".join(lines[1:])

        try:
            result = json.loads(text)
        except json.JSONDecodeError:
            logger.warning("JSON parse failed. Raw text: %s", text[:500])
            result = {}

        # Ensure expected keys exist
        if expected_keys:
            for key in expected_keys:
                if key not in result:
                    result[key] = ""

        return result


# ─── Factory Function ─────────────────────────────────────────────────────


def create_narrative_analyzer(
    endpoint: str | None = None,
    timeout: int = 10000,
    model: str = NarrativeAnalyzer.DEFAULT_MODEL,
) -> NarrativeAnalyzer:
    """Create a NarrativeAnalyzer instance.

    Args:
        endpoint: Azure OpenAI endpoint. Reads AZURE_OPENAI_ENDPOINT env if not provided.
        timeout:  Client timeout in seconds (default: 10000).
        model:    Model deployment name (default: gpt-5.4-pro).

    Returns:
        Configured NarrativeAnalyzer instance.
    """
    endpoint = endpoint or os.getenv("AZURE_OPENAI_ENDPOINT")
    if not endpoint:
        raise ValueError(
            "Azure OpenAI endpoint required. "
            "Set AZURE_OPENAI_ENDPOINT env var or pass endpoint= argument."
        )
    return NarrativeAnalyzer(endpoint=endpoint, timeout=timeout, model=model)
