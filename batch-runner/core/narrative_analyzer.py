"""NarrativeAnalyzer — typed Responses API module for GPT-5.6 Sol 1M Max.

Generates rich narrative analysis (overview, quality_analysis, failure_patterns,
recommendations) for experiment reports using a 2-call sequential pattern.

The analyzer uses the shared typed direct-v1 Azure AI client and performs two
sequential Responses API calls. The 1.05M context window is a deployment
capability; ``reasoning={"effort": "max"}`` is sent explicitly per request.

Usage:
    from core.narrative_analyzer import create_narrative_analyzer

    analyzer = create_narrative_analyzer()
    result = analyzer.analyze(data, summary, sectors, task_results, error_tasks)
    print(result.overview)
"""

import json
import logging
import math
import threading
import time
from dataclasses import dataclass, field

from core.azure_ai_clients import (
    AzureAIClientFactory,
    AzureAIWorkload,
)
from core.grader import MAGNITUDE_THRESHOLD
from core.llm_client import ManagedAzureAIClient, create_typed_azure_client
from core.measurement_display import NOT_MEASURED, render_measured

logger = logging.getLogger(__name__)

#: The reference `critical_item_pass_rate` is read against, from
#: `tasks/rebuilding_grading_task/300-gold-ceiling.md`. It is a reference, not a
#: gate -- `scripts/analyze_gold_ceiling.py` stopped deciding on it by owner
#: decision. It is repeated here rather than imported because
#: `batch-runner/scripts/` is not a `compute_grader_source_hash` input, and a
#: file outside that set must not be able to change this prompt's text.
#: `test_the_report_prompt_retires_the_required_item_name.py` pins the two
#: copies together.
HIGH_MAGNITUDE_PASS_REFERENCE = 0.95

#: Below this many counted items the rate cannot carry the weight a reader puts
#: on it: one item moves it further than the whole distance from the reference
#: to a clean sweep. Derived, not chosen. The dashboard derives the same number
#: the same way in `src/components/wow/highMagnitudeReading.ts`.
MIN_READABLE_HIGH_MAGNITUDE_ITEMS = math.ceil(1 / (1 - HIGH_MAGNITUDE_PASS_REFERENCE))

#: What `critical_item_pass_rate` is called wherever a person reads it. The JSON
#: key keeps its published name -- renaming it would break every reader of every
#: payload written so far -- but the owner's ruling of 2026-09-03 retired
#: "critical" and "required" from the prose, because the GDPVal rubrics carry no
#: `required` field and the grader substitutes score magnitude for necessity.
#: See `data/grades/_validation/REQUIRED_ITEM_DEFINITION.md`.
HIGH_MAGNITUDE_RATE_LABEL = (
    f"High-magnitude item pass rate (|max score| >= {MAGNITUDE_THRESHOLD}, diagnostic)"
)

# ─── Result Dataclass ─────────────────────────────────────────────────────


@dataclass
class NarrativeResult:
    """Result of a 2-call narrative analysis."""

    overview: str = ""
    quality_analysis: str = ""
    failure_patterns: str = ""
    recommendations: str = ""
    narrative_model: str = ""
    narrative_reasoning_effort: str = ""
    call_1_latency_ms: float = 0.0
    call_2_latency_ms: float = 0.0
    total_tokens: dict = field(default_factory=lambda: {"input": 0, "output": 0})
    grading_referenced: bool = False
    grade_source: dict | None = None
    runtime_fingerprint: str | None = None


# ─── Grading Prompt Helpers ───────────────────────────────────────────────


def _get_nested(source: dict | None, path: list[str], default=None):
    """Read a nested dict key path without raising on malformed grade data."""
    current = source
    for key in path:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
    return default if current is None else current


def _format_pct(value, decimals: int = 1, scale_fraction: bool = True) -> str:
    """Format a percent-like value, accepting either 0-1 rates or 0-100 values."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "n/a"
    if scale_fraction and abs(number) <= 1:
        number *= 100
    return f"{number:.{decimals}f}%"


def _build_grade_source(grade: dict | None) -> dict | None:
    """Return compact grade provenance for report_data.json."""
    if grade is None:
        return None
    return {
        "model": _get_nested(grade, ["judge", "model"], ""),
        "rubric_sha": _get_nested(grade, ["rubric", "short_sha"], ""),
        "prompt_v": _get_nested(grade, ["prompt", "version"], ""),
        "graded_at": grade.get("graded_at", ""),
    }


def _build_grading_guard_clause(grade: dict | None) -> str:
    """Return narrative guard text for pre-grading vs grade-aware prompts."""
    if grade is None:
        return (
            "- Grading scores do NOT exist yet. Do NOT mention or predict "
            "grades. Focus only on execution metrics and Self-QA scores."
        )

    judge_model = _get_nested(grade, ["judge", "model"], "unknown judge")
    reasoning_effort = _get_nested(grade, ["judge", "reasoning_effort"], "unknown")
    rubric_repo = _get_nested(grade, ["rubric", "repo_id"], "openai/gdpval")
    rubric_sha = _get_nested(grade, ["rubric", "short_sha"], "unknown")
    wow = _get_nested(grade, ["summary", "wow"], {})
    # Asking for a breakdown that does not exist in this run is how an absence
    # becomes a paragraph. See `_failure_pattern_hint`.
    highlights = "weakest sector, strongest sector"
    if not isinstance(wow, dict) or _measured_over(wow, "precheck_items") != 0:
        highlights += ", precheck vs judge breakdown"

    return f"""- Grading scores ARE available (see GRADING RESULTS section below).
- Source: rubric-based LLM-judge ({judge_model}, reasoning_effort={reasoning_effort}).
- This is NOT human expert review; it is an automated LLM-judge score
  against open-sourced GDPval rubrics ({rubric_repo} @ {rubric_sha}).
- Refer to scores as "LLM-judge grade" or "rubric-based score"; avoid
  wording that implies human expert review or OpenAI-hosted official scoring.
- "{HIGH_MAGNITUDE_RATE_LABEL}"
  counts items whose score magnitude is large. The rubrics carry no
  required-item flag, so it is NOT a measure of required items and NOT a pass
  criterion. Report it as supporting detail only; do not call it critical,
  required or mandatory, and do not describe a run as passing or failing on it.
- Highlight: {highlights}."""


def _build_grading_disclosure_paragraph(grade: dict | None) -> str:
    """Disclosure paragraph the model must include in overview when grades exist."""
    judge_model = _get_nested(grade, ["judge", "model"], "unknown judge")
    rubric_sha = _get_nested(grade, ["rubric", "short_sha"], "unknown")
    return (
        f"The grading shown is automated via LLM-judge ({judge_model}) against "
        "open-sourced GDPval rubrics ([openai/gdpval]"
        "(https://huggingface.co/datasets/openai/gdpval), "
        f"commit `{rubric_sha}`). OpenAI ended hosted grading and open-sourced "
        "their rubrics for community self-evaluation."
    )


def _measured_over(metrics: dict, count_key: str) -> int | None:
    """How many items a ``wow`` rate was divided by, or ``None`` if unstated.

    ``summary.wow.item_counts`` (and its per-sector twin) was added by
    ``step8_grade._wow_item_counts``. Grades written before that carry no
    counts, and for those the honest answer is that we do not know the
    denominator -- not that it was zero.
    """
    counts = metrics.get("item_counts")
    if not isinstance(counts, dict):
        return None
    value = counts.get(count_key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _format_rate(metrics: dict, rate_key: str, count_key: str, decimals: int = 0) -> str:
    """A ``wow`` rate, or the reason there is no rate to give.

    ``step8_grade._rate`` returns ``0.0`` when its denominator is empty, which
    is also what "every item failed" looks like. This prompt is the sharpest
    consequence of that collision: the model is paid to read these numbers and
    write conclusions from them, and 0% invites exactly one conclusion.

    Twenty of this repository's thirty-three published grades report
    ``precheck_pass_rate: 0.0`` having prechecked nothing at all. Given
    ``pre=0%`` beside "Precheck failures dominate: deliverable structure
    issues", a model has been told, in effect, to write up a structural
    collapse in runs where structure was never checked.

    So a rate over an empty denominator is not rendered as a percentage here.
    """
    measured = _measured_over(metrics, count_key)
    if measured == 0:
        return "not measured (0 items)"
    formatted = _format_pct(metrics.get(rate_key), decimals=decimals)
    if measured is None:
        return formatted
    return f"{formatted} of {measured}"


def _format_high_magnitude_rate(metrics: dict) -> str:
    """``critical_item_pass_rate``, rendered as what it actually measures.

    The rate itself is untouched: same key, same value, same arithmetic. What
    is added is the two things the owner's ruling of 2026-09-03 requires a
    reader to be given with it, and which the paid prompt is the last surface
    not to give.

    **The denominator, or the fact that there isn't one.** Measured over the
    grade payloads committed here: 83 published sector rows carry the rate and
    13 report exactly ``0.0``. Recomputing the count settles all 13 -- four
    counted no high-magnitude item at all, nine counted between 1 and 19, none
    reached 20. The 61 shard payloads, whose rates are published nowhere, say
    the same thing at scale: 364 rows, 155 zeros, 41 over nothing and 114 over
    1-19, again none at 20. There is no ``0.0`` on this metric, in either
    population, that is a run where twenty or more high-magnitude items were
    scored and failed. A bare ``0%`` in front of a model paid to explain it
    produces the one paragraph the data does not support.

    **That it is too small to read.** Below
    ``MIN_READABLE_HIGH_MAGNITUDE_ITEMS`` a single item moves the rate further
    than the whole distance from the reference to a clean sweep, so the number
    is noise rather than a finding. The dashboard already says so; this is the
    same statement on the surface that feeds the report.

    Only this rate is treated this way. ``precheck_pass_rate`` and
    ``judge_pass_rate`` keep ``_format_rate``'s behaviour, because the ruling
    was about this metric and inventing a readability floor for the other two
    would be a new criterion applied to already-published runs.
    """
    measured = _measured_over(metrics, "critical_items")
    if measured == 0:
        return "not measured (0 items)"
    formatted = _format_pct(metrics.get("critical_item_pass_rate"), decimals=0)
    if measured is None:
        # 21 of the 83 published sector rows are in this state, and every one
        # of the 364 shard rows. Without the count, a 0% here and a 0% over
        # four hundred items are the same string.
        return f"{formatted} (denominator not recorded)"
    if measured < MIN_READABLE_HIGH_MAGNITUDE_ITEMS:
        return (
            f"{formatted} of {measured} -- too few to read "
            f"(< {MIN_READABLE_HIGH_MAGNITUDE_ITEMS} items)"
        )
    return f"{formatted} of {measured}"


def _format_sector_grade_line(sector: str, metrics: dict) -> str:
    """Format one sector line for the GRADING RESULTS prompt section."""
    return (
        f"  - {sector}: avg_pct={_format_pct(metrics.get('avg_pct'), decimals=1)}, "
        f"high_mag={_format_high_magnitude_rate(metrics)}, "
        f"pre={_format_rate(metrics, 'precheck_pass_rate', 'precheck_items')}, "
        f"judge={_format_rate(metrics, 'judge_pass_rate', 'judge_items')}"
    )


def _failure_pattern_hint(wow: dict) -> str:
    """How to read precheck against judge -- when there is a precheck to read.

    The hint asks the model to decide which of two failure modes dominates.
    That is a comparison, and it needs both sides. On a run with no precheck
    items there is no precheck side, and the old third branch pointed at
    ``by_rubric_category``, which ``step8_grade`` fills with ``{}`` on every
    run (the GDPVal rubrics carry no category taxonomy) and which this prompt
    has never included. A model asked to consult something absent does not
    report an absence; it reasons from what it can see, which here is 0%.
    """
    if _measured_over(wow, "precheck_items") == 0:
        return (
            "  - UNAVAILABLE for this run: no rubric item was decided by\n"
            "    precheck, so `precheck_pass_rate` is a rate over nothing and\n"
            "    its 0% is not a finding. Do NOT report weak deliverable\n"
            "    structure, and do NOT compare structure against reasoning."
        )
    return (
        "  - Precheck failures dominate: deliverable structure issues (file naming, format)\n"
        "  - Judge failures dominate: content quality / domain reasoning issues\n"
        "  - Neither dominates: say so; there is no finer breakdown to consult."
    )


def _rank_grade_sectors(grade: dict | None) -> tuple[list[str], list[str]]:
    """Return formatted weakest and strongest sector lines, ranked by avg_pct."""
    by_sector = _get_nested(grade, ["summary", "wow", "by_sector"], {})
    if not isinstance(by_sector, dict):
        return ["  - n/a"], ["  - n/a"]

    ranked = []
    for sector, metrics in by_sector.items():
        if not isinstance(metrics, dict):
            continue
        try:
            avg_pct = float(metrics.get("avg_pct"))
        except (TypeError, ValueError):
            avg_pct = float("-inf")
        ranked.append((avg_pct, sector, metrics))

    if not ranked:
        return ["  - n/a"], ["  - n/a"]

    weakest = [
        _format_sector_grade_line(sector, metrics)
        for _, sector, metrics in sorted(ranked, key=lambda item: item[0])[:3]
    ]
    strongest = [
        _format_sector_grade_line(sector, metrics)
        for _, sector, metrics in sorted(ranked, key=lambda item: item[0], reverse=True)[:3]
    ]
    return weakest, strongest


def _build_grading_results_section(grade: dict | None) -> str:
    """Build the optional GRADING RESULTS prompt section from schema v1 grade JSON."""
    if grade is None:
        return ""

    openai_compat = _get_nested(grade, ["summary", "openai_compat"], {})
    wow = _get_nested(grade, ["summary", "wow"], {})
    if not isinstance(openai_compat, dict):
        openai_compat = {}
    if not isinstance(wow, dict):
        wow = {}

    total_tasks = (
        openai_compat.get("total_tasks")
        or _get_nested(grade, ["summary", "total_tasks"], "")
        or ""
    )
    weakest, strongest = _rank_grade_sectors(grade)

    return f"""
## GRADING RESULTS (LLM-judge, rubric-based)

Judge: {_get_nested(grade, ["judge", "model"], "unknown")} (reasoning_effort={_get_nested(grade, ["judge", "reasoning_effort"], "unknown")}, temperature={_get_nested(grade, ["judge", "temperature"], "unknown")})
Rubric source: {_get_nested(grade, ["rubric", "repo_id"], "openai/gdpval")} @ {_get_nested(grade, ["rubric", "short_sha"], "unknown")}

Overall:
  - Average score: {_format_pct(openai_compat.get("avg_score_pct"), decimals=1)} (± {_format_pct(openai_compat.get("ci_pct"), decimals=1)})
  - Near-perfect tasks (>= 99%): {openai_compat.get("perfect_count", "n/a")}/{total_tasks or "n/a"}
  - Near-zero tasks (<= 1%): {openai_compat.get("zero_count", "n/a")}/{total_tasks or "n/a"}
  - {HIGH_MAGNITUDE_RATE_LABEL}: {_format_high_magnitude_rate(wow)}
  - Precheck pass rate: {_format_rate(wow, "precheck_pass_rate", "precheck_items")}
  - Judge pass rate: {_format_rate(wow, "judge_pass_rate", "judge_items")}

By sector (top 3 weakest):
{chr(10).join(weakest)}

By sector (top 3 strongest):
{chr(10).join(strongest)}

Failure pattern hint (precheck vs judge):
{_failure_pattern_hint(wow)}
"""


# ─── NarrativeAnalyzer ────────────────────────────────────────────────────


class NarrativeAnalyzer:
    """GPT-5.6 Sol Max narrative generator using Azure OpenAI Responses API.

    Architecture:
        Call 1: Sector-level analysis → overview + quality_analysis
        Call 2: Deep analysis (all 220 tasks) → failure_patterns + recommendations

    Args:
        endpoint:    Azure OpenAI endpoint URL
        api_version: API version (default: 2025-04-01-preview)
        timeout:     Client-level timeout in seconds (default: 10000)
        model:       Deployment name (default: gpt-5.6-sol)
        reasoning_effort: Responses API reasoning effort (default: max)
    """

    DEFAULT_MODEL = "gpt-5.6-sol"
    DEFAULT_REASONING_EFFORT = "max"
    DEFAULT_API_VERSION = "2025-04-01-preview"
    DEFAULT_TIMEOUT = 10000

    def __init__(
        self,
        endpoint: str | None = None,
        api_version: str = DEFAULT_API_VERSION,
        timeout: int = DEFAULT_TIMEOUT,
        model: str = DEFAULT_MODEL,
        reasoning_effort: str = DEFAULT_REASONING_EFFORT,
        client=None,
        client_factory: AzureAIClientFactory | None = None,
    ):
        if endpoint is not None:
            raise ValueError(
                "endpoint overrides are forbidden; configure a typed Azure AI endpoint"
            )
        self._managed_client: ManagedAzureAIClient | None = None
        if client is None:
            self._managed_client = create_typed_azure_client(
                AzureAIWorkload.NARRATIVE,
                model,
                factory=client_factory,
                timeout=timeout,
                legacy_api_version=api_version,
            )
            client = self._managed_client.client
        self.client = client
        self.model = model
        self.reasoning_effort = reasoning_effort
        self._heartbeat_active = False
        self._heartbeat_thread: threading.Thread | None = None

    @property
    def runtime_fingerprint(self) -> str | None:
        managed = getattr(self, "_managed_client", None)
        if managed is None:
            return None
        return managed.runtime_fingerprint

    def close(self) -> None:
        self._stop_heartbeat()
        if self._managed_client is not None:
            self._managed_client.close()
            self._managed_client = None

    def __enter__(self) -> "NarrativeAnalyzer":
        return self

    def __exit__(self, _exc_type, _exc, _traceback) -> None:
        self.close()

    # ── Public API ─────────────────────────────────────────────────────

    def analyze(
        self,
        data: dict,
        summary: dict,
        sector_breakdown: list[dict],
        task_results: list[dict],
        error_tasks: list[dict],
        grade: dict | None = None,
    ) -> NarrativeResult:
        """Run 2-call sequential analysis and return NarrativeResult.

        Args:
            data:             Experiment metadata dict (meta fields)
            summary:          Summary stats dict
            sector_breakdown: List of per-sector stat dicts
            task_results:     ALL task result dicts (full 220)
            error_tasks:      Error task dicts with error messages
            grade:            Optional schema v1.0 grade JSON dict

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
                data, summary, sector_breakdown, grade=grade
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
                call1_result, task_results, error_tasks, grade=grade
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
            narrative_model=self.model,
            narrative_reasoning_effort=self.reasoning_effort,
            call_1_latency_ms=call1_latency,
            call_2_latency_ms=call2_latency,
            total_tokens={"input": total_input, "output": total_output},
            grading_referenced=grade is not None,
            grade_source=_build_grade_source(grade),
            runtime_fingerprint=self.runtime_fingerprint,
        )

    # ── Call 1 ─────────────────────────────────────────────────────────

    def _call_1_sector_analysis(
        self,
        data: dict,
        summary: dict,
        sector_breakdown: list[dict],
        grade: dict | None = None,
    ) -> tuple[dict, float, int, int]:
        """Sector-level analysis → overview + quality_analysis."""

        meta = data.get("meta", data)  # support both report_data and raw data
        grading_guard = _build_grading_guard_clause(grade)
        grading_overview_instruction = ""
        overview_grading_clause = ""
        if grade is not None:
            disclosure = _build_grading_disclosure_paragraph(grade)
            grading_overview_instruction = (
                '\n- In the "overview" field, you MUST include exactly one paragraph '
                "explaining that grading is automated LLM-judge based, citing the "
                "judge model and the rubric source/commit. Use this verbatim "
                f"paragraph: {disclosure}"
            )
            overview_grading_clause = (
                f" Include this exact disclosure paragraph once: {disclosure}"
            )

        sector_lines = "\n".join(
            f"  - {s['sector']}: {s['success']}/{s['total']} success "
            f"(avg QA {render_measured(s['avg_qa_score'], '/10', '.1f')}, "
            f"avg latency {render_measured(s['avg_latency_ms'], 'ms')})"
            for s in sector_breakdown
        )

        # The dash is a table convention everywhere else in this report. Here it
        # is read by something that will turn it into published prose, so it is
        # spelled out: a narrator handed a bare dash for a score guesses, and
        # the guess it reaches for is zero -- which is the exact sentence this
        # whole change exists to keep out of the report.
        absent = [
            key
            for key in (
                "avg_qa_score",
                "min_qa_score",
                "max_qa_score",
                "avg_latency_ms",
                "max_latency_ms",
                "total_latency_ms",
            )
            if summary.get(key) is None
        ]
        absent += [
            f"{s['sector']}.{key}"
            for s in sector_breakdown
            for key in ("avg_qa_score", "avg_latency_ms")
            if s.get(key) is None
        ]
        unmeasured_note = ""
        if absent:
            unmeasured_note = (
                f'\nNote: "{NOT_MEASURED}" below means that figure was never '
                "measured, because no task produced one -- not that it came out "
                "at zero. Do not describe it as a low score, a fast run, or a "
                "poor result. Say the measurement is absent and why, if the "
                "errors above explain it.\n"
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
  - Avg QA score: {render_measured(summary['avg_qa_score'], '/10')} (min {render_measured(summary['min_qa_score'])}, max {render_measured(summary['max_qa_score'])})
  - Avg latency: {render_measured(summary['avg_latency_ms'], 'ms')}
{unmeasured_note}
Sector breakdown:
{sector_lines}

IMPORTANT CONSTRAINTS:
{grading_guard}
- Focus ONLY on: task completion, Self-QA scores, latency patterns, sector/occupation observations, deliverable file generation quality.
- Use "self-assessed confidence" / "LLM-evaluated quality" framing.
- Write as a technical evaluator, NOT a marketer.
- Be concise and factual.{grading_overview_instruction}

Return ONLY valid JSON (no markdown code fences) with these exact keys:
{{
  "overview": "3-4 paragraphs: what experiment was run, task execution outcomes based on Self-QA confidence scores, and key highlights. Use language like 'self-assessed confidence', 'task completion rate', 'LLM-evaluated quality'.{overview_grading_clause}",
  "quality_analysis": "3-4 paragraphs: QA score distribution patterns, notable sector-level differences, occupation-specific observations, latency correlations with quality."
}}"""

        system = "You are a precise technical evaluator reviewing an LLM experiment run. Return only valid JSON."

        text, latency_ms, in_tok, out_tok = self._call_responses_api(system, user_prompt)
        parsed = self._parse_response(text, expected_keys=["overview", "quality_analysis"])
        return parsed, latency_ms, in_tok, out_tok

    # ── Call 2 ─────────────────────────────────────────────────────────

    def _call_2_deep_analysis(
        self,
        call1_result: dict,
        task_results: list[dict],
        error_tasks: list[dict],
        grade: dict | None = None,
    ) -> tuple[dict, float, int, int]:
        """Deep analysis with ALL task results → failure_patterns + recommendations."""
        grading_guard = _build_grading_guard_clause(grade)
        grading_results_section = _build_grading_results_section(grade)

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

IMPORTANT CONSTRAINTS:
{grading_guard}

{grading_results_section}

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
            reasoning={"effort": self.reasoning_effort},
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
                        f"   💓 [{time.strftime('%H:%M:%S')}] waiting for narrative response...",
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
            Parsed narrative object with the exact expected string fields.
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
            raise ValueError("narrative response is not valid JSON") from None
        if not isinstance(result, dict):
            raise ValueError("narrative response must be a JSON object")

        if expected_keys:
            if set(result) != set(expected_keys):
                raise ValueError("narrative response fields are invalid")
            if any(not isinstance(result[key], str) for key in expected_keys):
                raise ValueError("narrative response values must be strings")
            if any(not result[key].strip() for key in expected_keys):
                raise ValueError(
                    "narrative response values must be nonempty strings"
                )

        return result


def expected_narrative_publication_identity() -> tuple[str, str, str]:
    """Return the model-free expected Sol Max publication identity."""
    from core import azure_ai_clients

    routes = azure_ai_clients.preflight_routes(
        azure_ai_clients.narrative_route_workloads(
            NarrativeAnalyzer.DEFAULT_MODEL
        ),
        timeout=NarrativeAnalyzer.DEFAULT_TIMEOUT,
        legacy_api_version=NarrativeAnalyzer.DEFAULT_API_VERSION,
    )
    if len(routes) != 1:
        raise ValueError("primary narrative route identity is ambiguous")
    fingerprint = routes[0].get("runtime_fingerprint")
    if not isinstance(fingerprint, str) or len(fingerprint) != 64:
        raise ValueError("primary narrative route fingerprint is invalid")
    return (
        NarrativeAnalyzer.DEFAULT_MODEL,
        NarrativeAnalyzer.DEFAULT_REASONING_EFFORT,
        fingerprint,
    )


# ─── Factory Function ─────────────────────────────────────────────────────


def create_narrative_analyzer(
    endpoint: str | None = None,
    timeout: int = 10000,
    model: str = NarrativeAnalyzer.DEFAULT_MODEL,
    reasoning_effort: str = NarrativeAnalyzer.DEFAULT_REASONING_EFFORT,
    client=None,
    client_factory: AzureAIClientFactory | None = None,
) -> NarrativeAnalyzer:
    """Create a NarrativeAnalyzer instance.

    Args:
        endpoint: Deprecated. Explicit endpoint overrides are rejected.
        timeout:  Client timeout in seconds (default: 10000).
        model:    Model deployment name (default: gpt-5.6-sol).
        reasoning_effort: Responses API reasoning effort (default: max).

    Returns:
        Configured NarrativeAnalyzer instance.
    """
    return NarrativeAnalyzer(
        endpoint=endpoint,
        timeout=timeout,
        model=model,
        reasoning_effort=reasoning_effort,
        client=client,
        client_factory=client_factory,
    )
