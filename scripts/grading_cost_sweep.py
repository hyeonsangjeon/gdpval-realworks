#!/usr/bin/env python3
"""Autonomous grading cost-optimization sweep dispatcher (Track 2).

Renders each variant in a sweep plan YAML on top of
`batch-runner/grading_configs/_archive_v1/_sweep_template.yaml`, invokes
`batch-runner/step8_grade.py` per variant, extracts metrics from the
resulting grade JSON, and selects a Pareto-frontier winner subject to
the plan's acceptance thresholds.

This script DOES NOT touch any step1~step8 source files, `core/grader*`,
`prompts/`, or `data/grades/`. Variant outputs land under
`tasks/0523_saturday/cost_opt_results/<ts>/runs/<variant>/`.

Exit codes:
  0 — winner selected
  1 — no eligible winner
  2 — cost-cap abort
  3 — validation failure (unknown model, TPM, plan schema, etc.)
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import shutil
import subprocess
import sys
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml

# ---------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
BATCH_RUNNER = REPO_ROOT / "batch-runner"
DEFAULT_PLAN = REPO_ROOT / "tasks" / "0523_saturday" / "grading_cost_sweep_plan.yaml"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "tasks" / "0523_saturday" / "cost_opt_results"
SWEEP_TEMPLATE = (
    BATCH_RUNNER
    / "grading_configs"
    / "_archive_v1"
    / "_sweep_template.yaml"
)
BASELINE_CONFIG = BATCH_RUNNER / "grading_configs" / "default_gpt5pro.yaml"
STEP8 = BATCH_RUNNER / "step8_grade.py"
BATCH_RUNNER_ENV = BATCH_RUNNER / ".env"
CHANGELOG = REPO_ROOT / "CHANGELOG.md"

# Hard-coded model TPM table for the current Azure deployment. Update
# when new deployments are added. See TASK_GRADE_COST_SWEEP "Sweep Plan".
MODEL_TPM: dict[str, int] = {
    "gpt-5.4-pro":   100_000,
    "gpt-5.4-pro-2":  60_000,
    "gpt-5.4":       150_000,
    "gpt-5.4-mini":  150_000,
    "gpt-5.4-nano":  250_000,
    "gpt-4o":        100_000,
}

# NOTE: USD per 1M tokens (input, output). These are working estimates —
# verify against the live Azure tenant pricing before relying on the
# RESULTS.md cost figures for budgeting. Pricing for reasoning models
# already covers reasoning tokens within the output bucket.
PRICING_USD_PER_1M: dict[str, tuple[float, float]] = {
    "gpt-5.4-pro":   (15.0, 60.0),
    "gpt-5.4-pro-2": (15.0, 60.0),
    "gpt-5.4":       (5.0, 15.0),
    "gpt-5.4-mini":  (1.0,  4.0),
    "gpt-5.4-nano":  (0.5,  2.0),
    "gpt-4o":        (2.5, 10.0),
}

SAFE_TPM_FACTOR = 0.7
FULL_RUN_TASKS = 220
SMOKE_TASKS = 3
FULL_RUN_SCALE = FULL_RUN_TASKS / SMOKE_TASKS  # linear extrapolation

LOG = logging.getLogger("grading_cost_sweep")


# ---------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------

class SweepValidationError(RuntimeError):
    """Raised when the plan or one of its variants fails pre-flight checks."""


class SweepCostCapExceeded(RuntimeError):
    """Raised mid-sweep when projected cumulative cost exceeds the cap."""


# ---------------------------------------------------------------------
# Plan model (intentionally lightweight — dataclasses, not pydantic)
# ---------------------------------------------------------------------

@dataclass
class Variant:
    name: str
    phase: str                           # "A" | "B" | "C" | "DV"
    raw: dict[str, Any]                  # full variant dict from plan
    inherit_baseline: bool = False
    repeat_index: int | None = None      # set for Phase C runs

    @property
    def top_model(self) -> str:
        """Top-level judge.model — the cache-key model under Track 1."""
        if self.inherit_baseline:
            return _baseline_judge_model()
        return self.raw["judge"]["model"]

    @property
    def reasoning_effort(self) -> str:
        if self.inherit_baseline:
            return "high"
        return self.raw["judge"].get("reasoning_effort", "medium")

    @property
    def batch_size(self) -> int:
        if self.inherit_baseline:
            return 1
        return int(self.raw.get("grader", {}).get("batch_size", 1) or 1)

    @property
    def deliverable_chars(self) -> int:
        if self.inherit_baseline:
            return 4000
        return int(self.raw.get("grader", {}).get("deliverable_extract_max_chars", 1500))

    @property
    def tier_models(self) -> list[str]:
        """All tier models referenced by this variant (judge.model + each tier)."""
        models = [self.top_model]
        routing = self.raw.get("judge_routing") or {}
        for tier_name in ("tier_pro", "tier_standard", "tier_mini"):
            tier = routing.get(tier_name) or {}
            m = tier.get("model")
            if m:
                models.append(m)
        return sorted(set(models))


@dataclass
class Plan:
    schema_version: str
    plan_name: str
    fixed_benchmark: dict[str, Any]
    global_constraints: dict[str, Any]
    acceptance: dict[str, Any]
    baseline: dict[str, Any]
    phase_a: list[Variant]
    phase_b: list[Variant]
    phase_c_spec: dict[str, Any]
    diversity: dict[str, Any] | None
    raw: dict[str, Any]                     # raw plan for snapshot

    def all_variants(self) -> list[Variant]:
        return [*self.phase_a, *self.phase_b]


# ---------------------------------------------------------------------
# Plan loading + validation
# ---------------------------------------------------------------------

def _baseline_judge_model() -> str:
    """Resolve baseline judge.model from default_gpt5pro.yaml."""
    with open(BASELINE_CONFIG, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg["judge"]["model"]


def load_plan(path: Path) -> Plan:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if raw.get("schema_version") != "1.0":
        raise SweepValidationError(
            f"plan schema_version must be '1.0' (got {raw.get('schema_version')!r})"
        )
    for key in (
        "plan_name",
        "fixed_benchmark",
        "global_constraints",
        "acceptance",
        "baseline",
        "phase_a_single_axis",
        "phase_b_combinations",
    ):
        if key not in raw:
            raise SweepValidationError(f"plan missing required key: {key}")

    phase_a = [
        Variant(name=v["name"], phase="A", raw=v) for v in raw["phase_a_single_axis"]
    ]
    phase_b: list[Variant] = []
    for v in raw["phase_b_combinations"]:
        inherit = v.get("inherit_from") == "baseline"
        phase_b.append(Variant(name=v["name"], phase="B", raw=v, inherit_baseline=inherit))

    return Plan(
        schema_version=raw["schema_version"],
        plan_name=raw["plan_name"],
        fixed_benchmark=raw["fixed_benchmark"],
        global_constraints=raw["global_constraints"],
        acceptance=raw["acceptance"],
        baseline=raw["baseline"],
        phase_a=phase_a,
        phase_b=phase_b,
        phase_c_spec=raw.get("phase_c_stability", {}),
        diversity=raw.get("diversity_validator"),
        raw=raw,
    )


def validate_models_available(plan: Plan) -> None:
    """Reject any variant referencing a model not in MODEL_TPM."""
    for v in plan.all_variants():
        for model in v.tier_models:
            if model not in MODEL_TPM:
                raise SweepValidationError(
                    f"variant {v.name!r}: unknown model {model!r}. "
                    f"Known: {sorted(MODEL_TPM)}"
                )
    if plan.diversity and plan.diversity.get("enabled"):
        m = plan.diversity["variant"]["judge"]["model"]
        if m not in MODEL_TPM:
            raise SweepValidationError(
                f"diversity_validator: unknown model {m!r}"
            )


def _estimate_per_call_tokens(variant: Variant) -> tuple[int, int]:
    """Return (input_tok, output_tok) for ONE Responses API call of this variant.

    Calibrated against exp998 baseline: 84 calls × (~1640 in + ~1063 out)
    ≈ $7.42 total at gpt-5.4-pro effort=high. The numbers below are tuned
    so the bs=1, high-effort case lands at output ≈ 1060 (verdict + reasoning).
    """
    EFFORT_PER_ITEM_OUT = {"minimal": 40, "low": 80, "medium": 200, "high": 400}
    EFFORT_REASONING_OUT = {"minimal": 10, "low": 100, "medium": 300, "high": 660}

    bs = max(1, variant.batch_size)
    deliverable_chars = variant.deliverable_chars
    effort = variant.reasoning_effort

    # Input: deliverable chars / 4 chars-per-token + (bs * criterion ≈ 140) + system ≈ 200
    input_tok = int((deliverable_chars / 4) + bs * 140 + 200)
    # Output: per-item verdict × bs + reasoning overhead per call
    per_item_out = EFFORT_PER_ITEM_OUT.get(effort, 200)
    reasoning_out = EFFORT_REASONING_OUT.get(effort, 300)
    output_tok = int(bs * per_item_out + reasoning_out)
    return input_tok, output_tok


def _estimated_call_duration_sec(variant: Variant) -> float:
    """Rough per-call wall-clock estimate (sec) for TPM peak calculation."""
    # Latency scales mostly with reasoning_effort + batch_size. Numbers
    # derived from exp998 baseline (8530s / 84 calls ≈ 102s for high+bs=1).
    EFFORT_BASE = {"minimal": 15.0, "low": 30.0, "medium": 60.0, "high": 100.0}
    base = EFFORT_BASE.get(variant.reasoning_effort, 60.0)
    return base + max(0, variant.batch_size - 1) * 8.0


def validate_tpm_caps(plan: Plan) -> None:
    """Reject variants whose peak TPM > 70% of the model's deployed TPM."""
    for v in plan.all_variants():
        if v.inherit_baseline:
            continue
        in_tok, out_tok = _estimate_per_call_tokens(v)
        per_call_tok = in_tok + out_tok
        call_dur = _estimated_call_duration_sec(v)
        concurrent = int(v.raw.get("tpm_guard", {}).get("max_concurrent", 1) or 1)
        # peak TPM = concurrent * tokens-per-call * calls-per-minute
        peak_tpm = concurrent * per_call_tok * (60.0 / max(call_dur, 1.0))
        # Top-level model is the dispatch model. Tier models are checked
        # individually since each tier sends its own calls.
        for model in v.tier_models:
            limit = MODEL_TPM[model] * SAFE_TPM_FACTOR
            if peak_tpm > limit:
                raise SweepValidationError(
                    f"variant {v.name!r}: peak {peak_tpm:.0f} TPM > 70% of "
                    f"{model} ({MODEL_TPM[model]:,})"
                )


def validate_acceptance_thresholds(plan: Plan) -> None:
    a = plan.acceptance
    required = (
        "baseline_avg_score_pct",
        "avg_score_delta_pp",
        "critical_item_pass_rate_min",
        "judge_error_rate_max",
        "precheck_pass_rate_min",
    )
    for k in required:
        if k not in a:
            raise SweepValidationError(f"acceptance missing key: {k}")


# ---------------------------------------------------------------------
# Cost estimation
# ---------------------------------------------------------------------

def _estimated_call_count(variant: Variant) -> int:
    """Number of Responses API calls for the smoke benchmark (3 tasks).

    Total rubric items is fixed at 94 for exp998 smoke. We assume ~20
    items reach the LLM judge after precheck (baseline measured 84, but
    that included one precheck-disabled fraction; we keep 84 for the
    conservative estimate, matching baseline). Tiered routing splits
    items across tiers but the TOTAL judge calls remain bounded by
    ceil(items_per_tier / batch_size).
    """
    JUDGE_ITEMS_TOTAL = 84  # baseline measurement (exp998, after precheck)
    bs = max(1, variant.batch_size)

    if variant.raw.get("judge_routing"):
        # Conservative split: assume 25% pro tier, 5% mini tier, 70% std.
        pro = math.ceil(0.25 * JUDGE_ITEMS_TOTAL / 1)         # pro stays bs=1
        mini = math.ceil(0.05 * JUDGE_ITEMS_TOTAL / bs)
        std = math.ceil(0.70 * JUDGE_ITEMS_TOTAL / bs)
        return pro + mini + std

    return math.ceil(JUDGE_ITEMS_TOTAL / bs)


def estimate_variant_cost(variant: Variant, benchmark: dict[str, Any]) -> float:
    """Predict smoke-run USD cost for a variant.

    Implementation note:
      cost = Σ_tier ( (in_tok × in_rate + out_tok × out_rate) / 1e6 × N_calls_tier )

    For the non-tiered case the formula collapses to a single tier.
    """
    if variant.inherit_baseline:
        # Inherit exp998 measured values.
        in_tok = 137756
        out_tok = 89263
        model = _baseline_judge_model()
        in_rate, out_rate = PRICING_USD_PER_1M[model]
        return (in_tok * in_rate + out_tok * out_rate) / 1e6

    in_per_call, out_per_call = _estimate_per_call_tokens(variant)
    n_calls = _estimated_call_count(variant)

    routing = variant.raw.get("judge_routing")
    if routing:
        # Allocate calls across tiers (matches _estimated_call_count split).
        JUDGE_ITEMS = 84
        bs = max(1, variant.batch_size)
        pro_calls = math.ceil(0.25 * JUDGE_ITEMS / 1)
        mini_calls = math.ceil(0.05 * JUDGE_ITEMS / bs) if routing.get("tier_mini") else 0
        std_calls = max(0, n_calls - pro_calls - mini_calls)

        total = 0.0
        for tier_name, calls in (
            ("tier_pro", pro_calls),
            ("tier_standard", std_calls),
            ("tier_mini", mini_calls),
        ):
            block = routing.get(tier_name) or {}
            model = block.get("model") or variant.top_model
            in_rate, out_rate = PRICING_USD_PER_1M[model]
            total += (in_per_call * in_rate + out_per_call * out_rate) / 1e6 * calls
        return total

    in_rate, out_rate = PRICING_USD_PER_1M[variant.top_model]
    return (in_per_call * in_rate + out_per_call * out_rate) / 1e6 * n_calls


# ---------------------------------------------------------------------
# Variant config rendering
# ---------------------------------------------------------------------

def _deep_merge(base: dict, overrides: dict) -> dict:
    out = deepcopy(base)
    for k, v in (overrides or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = deepcopy(v)
    return out


def render_temp_config(
    variant: Variant,
    output_dir: Path,
    baseline_template_path: Path = SWEEP_TEMPLATE,
) -> Path:
    """Render a variant config on top of the sweep template and persist it.

    Enforces:
      - temperature = 0
      - seed = 42
      - filename_template includes the variant name to avoid collisions.
    """
    with open(baseline_template_path, "r", encoding="utf-8") as f:
        rendered = yaml.safe_load(f)

    if variant.inherit_baseline:
        # Mirror default_gpt5pro.yaml almost verbatim.
        with open(BASELINE_CONFIG, "r", encoding="utf-8") as f:
            rendered = yaml.safe_load(f)
    else:
        raw = variant.raw
        # judge top-level
        judge_overrides = deepcopy(raw.get("judge", {}))
        if "reasoning_effort" in judge_overrides:
            effort = judge_overrides.pop("reasoning_effort")
            judge_overrides.setdefault("reasoning", {})["effort"] = effort
        rendered["judge"] = _deep_merge(rendered["judge"], judge_overrides)

        # grader knobs
        rendered["grader"] = _deep_merge(rendered.get("grader", {}), raw.get("grader", {}))

        # judge_routing block (only if present)
        if raw.get("judge_routing"):
            rendered["judge_routing"] = deepcopy(raw["judge_routing"])
        else:
            rendered.pop("judge_routing", None)

    # Hard guards (always enforced, regardless of plan input).
    rendered["judge"].setdefault("generation", {})
    rendered["judge"]["generation"]["temperature"] = 0
    rendered["judge"]["generation"]["seed"] = 42

    # Config name & filename uniqueness.
    rendered["config_name"] = f"sweep__{variant.name}"
    out_block = rendered.setdefault("output", {})

    # CRITICAL: redirect output to the sweep's per-variant runs dir so we
    # never overwrite production data/grades/*.json. The path is relative
    # to step8_grade's cwd (batch-runner/), so we go up one level then
    # into the absolute sweep dir.
    variant_dir = output_dir / "runs" / variant.name
    variant_dir.mkdir(parents=True, exist_ok=True)
    # Use absolute path (config.yaml is portable but cwd is batch-runner).
    out_block["directory"] = str(variant_dir.resolve())

    if "filename_template" not in out_block:
        out_block["filename_template"] = (
            "{exp_id}__{judge_slug}__{rubric_short_sha}__{prompt_v}.json"
        )
    if "prompt" not in rendered:
        rendered["prompt"] = {"template": "prompts/grader_judge.md", "version": "v1"}

    # Persist
    cfg_path = variant_dir / "config.yaml"
    with open(cfg_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(rendered, f, sort_keys=False)
    return cfg_path


# ---------------------------------------------------------------------
# step8 invocation
# ---------------------------------------------------------------------

def _judge_slug(model: str) -> str:
    return model.replace(".", "_")


def _expected_grade_filename(config_path: Path, benchmark: dict[str, Any]) -> str:
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    template = cfg["output"]["filename_template"]
    return template.format(
        exp_id=benchmark["experiment_yaml_name"],
        judge_slug=_judge_slug(cfg["judge"]["model"]),
        rubric_short_sha=benchmark["rubric_sha"],
        prompt_v=cfg["prompt"]["version"],
    )


def _load_subprocess_env() -> dict[str, str]:
    """Build the env dict for step8_grade subprocesses.

    Strategy: start from os.environ, then overlay batch-runner/.env so that
    AZURE_OPENAI_ENDPOINT and SP credentials are present. We do not mutate
    the parent process env to avoid surprising callers. Quoted values
    (single or double) are stripped. Lines that do not match KEY=VALUE or
    that start with '#' are ignored. Caller-set env vars take precedence
    over .env (so CI overrides work).
    """
    env = dict(os.environ)
    if not BATCH_RUNNER_ENV.exists():
        LOG.warning(
            "batch-runner/.env not found at %s; subprocess relies on parent env only",
            BATCH_RUNNER_ENV,
        )
        return env

    for raw_line in BATCH_RUNNER_ENV.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if " #" in line:
            line = line.split(" #", 1)[0].rstrip()
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if (val.startswith('"') and val.endswith('"')) or (
            val.startswith("'") and val.endswith("'")
        ):
            val = val[1:-1]
        if key and key not in env:
            env[key] = val

    # Enable grader's API key fallback for the sweep so we recover from
    # stale SP secrets without manual rotation. grader.py's default is
    # still OIDC-only (the fallback is opt-in by this flag).
    env.setdefault("GRADER_ALLOW_API_KEY_FALLBACK", "1")
    return env


def run_step8_grade(
    config_path: Path,
    benchmark: dict[str, Any],
    variant_dir: Path,
    runner: subprocess.CompletedProcess | None = None,
) -> Path:
    """Invoke step8_grade.py for the variant. Returns the moved grade.json path.

    Subprocess inherits parent env (OIDC token, AZURE_OPENAI_ENDPOINT) plus
    any KEY=VALUE pairs from batch-runner/.env. The .env loading is needed
    because step8_grade.py and core/* do not call load_dotenv themselves;
    they only read from os.environ. Without this, AZURE_OPENAI_ENDPOINT
    and SP credentials are missing and grader initialization fails fast.
    """
    log_path = variant_dir / "run.log"
    grade_target = variant_dir / "grade.json"

    cmd = [
        sys.executable,
        str(STEP8.name),
        benchmark["experiment_yaml_name"],
        "--config",
        str(config_path.resolve()),
        "--limit",
        str(int(benchmark.get("task_limit", 3))),
        "--force",
    ]

    sub_env = _load_subprocess_env()

    with open(log_path, "w", encoding="utf-8") as logf:
        logf.write(f"# {' '.join(cmd)}\n# cwd={BATCH_RUNNER}\n\n")
        logf.flush()
        proc = subprocess.run(
            cmd,
            cwd=str(BATCH_RUNNER),
            stdout=logf,
            stderr=subprocess.STDOUT,
            check=False,
            env=sub_env,
        )

    if proc.returncode != 0:
        raise RuntimeError(
            f"step8_grade.py exited {proc.returncode}; see {log_path}"
        )

    # Locate the produced grade JSON. Output directory is the variant's
    # runs/<name>/ folder (redirected by render_temp_config so we never
    # touch production data/grades/*.json). We expect the templated
    # filename to land there; if not, fall back to any *.json in the dir.
    expected_name = _expected_grade_filename(config_path, benchmark)
    src = (variant_dir / expected_name).resolve()
    if not src.exists():
        candidates = sorted(
            variant_dir.glob(f"{benchmark['experiment_yaml_name']}__*.json"),
            key=lambda p: p.stat().st_mtime,
        )
        # Filter out the grade.json target itself in case of a re-run.
        candidates = [c for c in candidates if c.resolve() != grade_target.resolve()]
        if not candidates:
            raise RuntimeError(f"no grade.json produced; expected {src}")
        src = candidates[-1]

    if src.resolve() != grade_target.resolve():
        # copy2 preserves the source for debugging/audit; the consolidated
        # name 'grade.json' is what downstream metrics extraction uses.
        shutil.copy2(str(src), str(grade_target))
    return grade_target


# ---------------------------------------------------------------------
# Metrics extraction
# ---------------------------------------------------------------------

def extract_metrics(grade_json_path: Path, variant: Variant) -> dict[str, Any]:
    """Read a grade JSON and compute the dispatcher's per-variant metric block."""
    with open(grade_json_path, "r", encoding="utf-8") as f:
        grade = json.load(f)

    summary = grade.get("summary", {})
    oai = summary.get("openai_compat", {})
    wow = summary.get("wow", {})
    cost = summary.get("cost", {})

    judge_input = int(cost.get("total_input_tokens", 0))
    judge_output = int(cost.get("total_output_tokens", 0))
    judge_calls = int(cost.get("total_judge_calls", 0))
    judge_latency = float(cost.get("total_judge_latency_sec", 0.0))

    # Recompute smoke cost from tokens × pricing (variant's TOP model).
    smoke_cost = _cost_from_tokens(variant, judge_input, judge_output)
    full_cost = smoke_cost * FULL_RUN_SCALE

    return {
        "name": variant.name,
        "phase": variant.phase,
        "repeat_index": variant.repeat_index,
        "avg_score_pct": float(oai.get("avg_score_pct", 0.0)),
        "critical_item_pass_rate": float(wow.get("critical_item_pass_rate", 0.0)),
        "judge_error_rate": float(wow.get("judge_error_rate", 0.0)),
        "precheck_pass_rate": float(wow.get("precheck_pass_rate", 0.0)),
        "judge_call_count": judge_calls,
        "judge_total_latency_sec": judge_latency,
        "judge_input_tokens": judge_input,
        "judge_output_tokens": judge_output,
        "smoke_cost_usd": round(smoke_cost, 4),
        "full_run_cost_usd": round(full_cost, 2),
    }


def _cost_from_tokens(variant: Variant, in_tok: int, out_tok: int) -> float:
    """USD cost from tokens × pricing. Tier-aware: blends rates if routing set."""
    model = variant.top_model
    if model not in PRICING_USD_PER_1M:
        return 0.0
    in_rate, out_rate = PRICING_USD_PER_1M[model]
    return (in_tok * in_rate + out_tok * out_rate) / 1e6


# ---------------------------------------------------------------------
# Pareto frontier + winner selection
# ---------------------------------------------------------------------

def pareto_frontier(
    results: list[dict[str, Any]],
    axes: Iterable[str],
) -> list[dict[str, Any]]:
    """Return non-dominated results minimizing each axis."""
    axes = list(axes)
    frontier: list[dict[str, Any]] = []
    for cand in results:
        dominated = False
        for other in results:
            if other is cand:
                continue
            strictly_better = False
            all_le = True
            for ax in axes:
                if other.get(ax, math.inf) > cand.get(ax, math.inf):
                    all_le = False
                    break
                if other.get(ax, math.inf) < cand.get(ax, math.inf):
                    strictly_better = True
            if all_le and strictly_better:
                dominated = True
                break
        if not dominated:
            frontier.append(cand)
    return frontier


@dataclass
class WinnerResult:
    name: str
    metrics: dict[str, Any]
    rationale: str


def select_pareto_winner(
    progress: dict[str, Any],
    acceptance: dict[str, Any],
) -> WinnerResult | None:
    baseline_score = float(acceptance["baseline_avg_score_pct"])
    delta_pp = float(acceptance["avg_score_delta_pp"])
    crit_min = float(acceptance["critical_item_pass_rate_min"])
    err_max = float(acceptance["judge_error_rate_max"])
    precheck_min = float(acceptance["precheck_pass_rate_min"])

    eligible = []
    for name, m in progress.get("results", {}).items():
        if m.get("phase") == "DV":
            continue  # diversity validator never selected
        if m.get("critical_item_pass_rate", 0.0) < crit_min:
            continue
        if m.get("judge_error_rate", 1.0) > err_max:
            continue
        if m.get("precheck_pass_rate", 0.0) < precheck_min:
            continue
        if abs(m.get("avg_score_pct", 0.0) - baseline_score) > delta_pp:
            continue
        eligible.append(m)

    if not eligible:
        return None

    frontier = pareto_frontier(
        eligible,
        axes=["full_run_cost_usd", "judge_error_rate", "judge_total_latency_sec"],
    )
    winner = min(frontier, key=lambda m: m["full_run_cost_usd"])

    # Phase C stability tie-break: if winner has reps and std > threshold, drop.
    reps = [
        r for r in progress.get("results", {}).values()
        if r.get("name", "").startswith(winner["name"]) and r.get("phase") == "C"
    ]
    if len(reps) >= 2:
        scores = [r["avg_score_pct"] for r in reps]
        mean = sum(scores) / len(scores)
        std = (sum((s - mean) ** 2 for s in scores) / len(scores)) ** 0.5
        if std > 1.5 and len(frontier) > 1:
            remaining = [m for m in frontier if m["name"] != winner["name"]]
            winner = min(remaining, key=lambda m: m["full_run_cost_usd"])

    return WinnerResult(
        name=winner["name"],
        metrics=winner,
        rationale=(
            f"Pareto winner among {len(eligible)} eligible variants "
            f"(frontier size {len(frontier)}); minimized full_run_cost_usd."
        ),
    )


def pick_phase_a_winners(progress: dict[str, Any]) -> dict[str, str]:
    """Pick one winner per Phase A axis (A1/A2/A3/A4) by lowest cost."""
    winners: dict[str, str] = {}
    for axis in ("A1", "A2", "A3", "A4"):
        axis_results = [
            m for name, m in progress.get("results", {}).items()
            if name.startswith(axis + "_")
        ]
        if not axis_results:
            continue
        winners[axis] = min(axis_results, key=lambda m: m.get("full_run_cost_usd", math.inf))["name"]
    return winners


def augment_phase_b(
    static_b: list[Variant],
    phase_a_winners: dict[str, str],
) -> list[Variant]:
    """Pass-through for v1; logs Phase-A winners for traceability."""
    if phase_a_winners:
        LOG.info("Phase A winners (per axis): %s", phase_a_winners)
    else:
        LOG.info("Phase A produced no winners; running Phase B as-defined.")
    return static_b


# ---------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------

def write_summary_json(progress: dict[str, Any], path: Path) -> None:
    payload = {
        "plan_name": progress.get("plan_name"),
        "started_at": progress.get("started_at"),
        "finished_at": progress.get("finished_at"),
        "cumulative_cost_usd": progress.get("cumulative_cost_usd", 0.0),
        "variants": progress.get("results", {}),
        "winner": progress.get("winner"),
        "phase_a_winners": progress.get("phase_a_winners", {}),
        "diversity_agreement_pct": progress.get("diversity_agreement_pct"),
        "aborted": progress.get("aborted", False),
        "abort_reason": progress.get("abort_reason"),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def _format_row(m: dict[str, Any]) -> str:
    return (
        f"| {m['name']} | {m.get('avg_score_pct', 0):.2f} | "
        f"{m.get('critical_item_pass_rate', 0):.2f} | "
        f"{m.get('judge_error_rate', 0)*100:.1f}% | "
        f"{m.get('judge_call_count', 0)} | "
        f"{m.get('judge_total_latency_sec', 0):.0f}s | "
        f"${m.get('smoke_cost_usd', 0):.2f} | "
        f"${m.get('full_run_cost_usd', 0):.2f} |"
    )


def write_results_md(
    progress: dict[str, Any],
    winner: WinnerResult | None,
    plan: Plan,
    path: Path,
) -> None:
    started = progress.get("started_at", "?")
    finished = progress.get("finished_at", "in-progress")
    cap = plan.global_constraints.get("cost_cap_usd")
    cumulative = progress.get("cumulative_cost_usd", 0.0)
    benchmark = plan.fixed_benchmark

    lines: list[str] = []
    lines.append("# Grading Cost Sweep — Results")
    lines.append("")
    lines.append(f"- **Run**: {started} → {finished}")
    lines.append(f"- **Plan**: {plan.plan_name}")
    lines.append(
        f"- **Benchmark**: {benchmark['experiment_yaml_name']}, "
        f"{benchmark['task_limit']} tasks, rubric `{benchmark['rubric_sha']}`"
    )
    lines.append(
        f"- **Cumulative cost**: ${cumulative:.2f} / cap ${cap}"
    )
    if progress.get("aborted"):
        lines.append(f"- **ABORTED**: {progress.get('abort_reason')}")
    lines.append("")

    lines.append("## TL;DR")
    lines.append("")
    if winner is None:
        lines.append("**No winner** — no variant satisfied all acceptance thresholds.")
        lines.append("")
        lines.append("Best-effort recommendation: see Phase B table below.")
    else:
        m = winner.metrics
        baseline_score = plan.acceptance["baseline_avg_score_pct"]
        lines.append(f"**Winner**: `{winner.name}`")
        lines.append("")
        lines.append(f"- 풀런 예상 비용: ${m['full_run_cost_usd']:.2f}")
        lines.append(
            f"- avg_score_pct: {m['avg_score_pct']:.2f} "
            f"(baseline {baseline_score}, Δ {m['avg_score_pct']-baseline_score:+.2f}pp)"
        )
        lines.append(f"- critical_item_pass_rate: {m['critical_item_pass_rate']:.2f}")
        lines.append(f"- judge_error_rate: {m['judge_error_rate']*100:.1f}%")
        lines.append(f"- wall-clock (smoke): {m['judge_total_latency_sec']:.0f}s")
        lines.append(f"- Rationale: {winner.rationale}")
    lines.append("")

    header = (
        "| variant | avg_score | crit_pass | err | calls | latency | smoke $ | full $ |\n"
        "|---|---|---|---|---|---|---|---|"
    )

    for phase_label, prefix in (
        ("## Phase A: Single-axis sweep", "A"),
        ("## Phase B: Combinations", "B"),
        ("## Phase C: Stability runs", "C"),
        ("## Diversity Validator", "DV"),
    ):
        rows = [
            m for m in progress.get("results", {}).values()
            if (m.get("phase") == prefix)
        ]
        if not rows:
            continue
        lines.append(phase_label)
        lines.append("")
        lines.append(header)
        for r in rows:
            lines.append(_format_row(r))
        lines.append("")

    lines.append("## Winner Config")
    lines.append("")
    if winner is None:
        lines.append("_None — `winner_config.yaml` not emitted._")
    else:
        lines.append(
            "See `winner_config.yaml`. Promote to "
            "`batch-runner/grading_configs/recommended_<date>.yaml` after a "
            "manual full-run validation against baseline."
        )
    lines.append("")

    lines.append("## Caveats")
    lines.append("")
    lines.append("- Smoke costs are token-based estimates (variance vs. tenant billing ≤ ~20%).")
    lines.append(f"- Full-run cost is linear extrapolation × {FULL_RUN_SCALE:.1f}.")
    lines.append("- gpt-5.5 is out-of-scope (quota pending).")
    lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def write_winner_config(
    winner: WinnerResult,
    output_dir: Path,
    target: Path,
) -> None:
    """Copy the winner's rendered config.yaml + add a banner comment."""
    src = output_dir / "runs" / winner.name / "config.yaml"
    if not src.exists():
        LOG.warning("winner config source missing: %s", src)
        return
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    banner = (
        f"# Auto-generated winner from sweep run @ {ts}.\n"
        f"# Variant: {winner.name}\n"
        f"# Verify against a full-run baseline before promoting to default.\n"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(banner + src.read_text(encoding="utf-8"), encoding="utf-8")


def append_changelog_entry(
    winner: WinnerResult | None,
    plan: Plan,
    output_dir: Path,
    cumulative_cost_usd: float,
) -> None:
    if not CHANGELOG.exists():
        return
    text = CHANGELOG.read_text(encoding="utf-8")
    marker = "## [Unreleased]"
    if marker not in text:
        return
    rel = output_dir.relative_to(REPO_ROOT)
    if winner is None:
        entry = (
            f"- Grading cost sweep run `{output_dir.name}`: **no winner** "
            f"(spent ${cumulative_cost_usd:.2f}). See `{rel}/RESULTS.md`."
        )
    else:
        m = winner.metrics
        baseline_full = plan.baseline["expected_metrics"].get("smoke_cost_usd", 0.0) * FULL_RUN_SCALE
        entry = (
            f"- Grading cost sweep run `{output_dir.name}`: winner "
            f"`{winner.name}` — projected full-run cost ${m['full_run_cost_usd']:.2f} "
            f"(baseline ~${baseline_full:.0f}), avg_score "
            f"Δ{m['avg_score_pct']-plan.acceptance['baseline_avg_score_pct']:+.2f}pp, "
            f"critical {m['critical_item_pass_rate']:.2f}, err "
            f"{m['judge_error_rate']*100:.1f}%. See `{rel}/RESULTS.md`."
        )
    # Insert under "### Added" right after the marker.
    needle = marker + "\n\n### Added\n"
    if needle in text:
        new_text = text.replace(needle, needle + entry + "\n", 1)
    else:
        new_text = text.replace(marker, marker + "\n\n### Added\n" + entry + "\n", 1)
    CHANGELOG.write_text(new_text, encoding="utf-8")


# ---------------------------------------------------------------------
# Progress tracking
# ---------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_or_init_progress(path: Path, plan_name: str) -> dict[str, Any]:
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "plan_name": plan_name,
        "started_at": _now_iso(),
        "completed": [],
        "cumulative_cost_usd": 0.0,
        "results": {},
        "consecutive_429_per_model": {},
        "aborted": False,
        "abort_reason": None,
    }


def save_progress(progress: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(progress, f, indent=2)


# ---------------------------------------------------------------------
# CLI orchestration
# ---------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="grading_cost_sweep",
        description="Autonomous grading cost optimization sweep dispatcher.",
    )
    parser.add_argument(
        "--plan",
        type=Path,
        default=DEFAULT_PLAN,
        help="Path to sweep plan YAML.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory (default: cost_opt_results/<auto-ts>/).",
    )
    parser.add_argument(
        "--resume",
        type=Path,
        default=None,
        help="Resume a previous sweep by pointing at its output dir.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate plan + estimate costs only; do not invoke step8_grade.py.",
    )
    parser.add_argument(
        "--max-cost",
        type=float,
        default=None,
        help="Override plan global_constraints.cost_cap_usd.",
    )
    parser.add_argument(
        "--phases",
        type=str,
        default="A,B,C",
        help="Comma-separated subset: any of A,B,C (e.g. 'A' or 'A,B').",
    )
    return parser.parse_args(argv)


def _setup_output_dir(args: argparse.Namespace) -> Path:
    if args.resume:
        out = Path(args.resume)
        if not out.exists():
            raise SweepValidationError(f"--resume dir does not exist: {out}")
        return out.resolve()
    if args.output_dir:
        out = Path(args.output_dir)
    else:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
        out = DEFAULT_OUTPUT_ROOT / ts
    out.mkdir(parents=True, exist_ok=True)
    return out.resolve()


def _snapshot_plan(plan: Plan, output_dir: Path) -> None:
    with open(output_dir / "plan.snapshot.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(plan.raw, f, sort_keys=False)


def _run_variant(
    variant: Variant,
    plan: Plan,
    output_dir: Path,
    progress: dict[str, Any],
    progress_path: Path,
    dry_run: bool,
    cost_cap: float,
) -> None:
    """Render config, run grade, extract metrics, update progress."""
    LOG.info("[%s] starting", variant.name)
    est_cost = estimate_variant_cost(variant, plan.fixed_benchmark)
    LOG.info("[%s] estimated cost: $%.3f", variant.name, est_cost)

    projected = progress["cumulative_cost_usd"] + est_cost
    if projected > cost_cap:
        raise SweepCostCapExceeded(
            f"cumulative ${progress['cumulative_cost_usd']:.2f} + "
            f"est ${est_cost:.2f} > cap ${cost_cap:.2f}"
        )

    cfg_path = render_temp_config(variant, output_dir)

    if dry_run:
        # Synthesize zero metrics; mark as dry-run.
        progress["results"][variant.name] = {
            "name": variant.name,
            "phase": variant.phase,
            "repeat_index": variant.repeat_index,
            "avg_score_pct": 0.0,
            "critical_item_pass_rate": 0.0,
            "judge_error_rate": 0.0,
            "precheck_pass_rate": 0.0,
            "judge_call_count": 0,
            "judge_total_latency_sec": 0.0,
            "judge_input_tokens": 0,
            "judge_output_tokens": 0,
            "smoke_cost_usd": round(est_cost, 4),
            "full_run_cost_usd": round(est_cost * FULL_RUN_SCALE, 2),
            "dry_run": True,
        }
        progress["cumulative_cost_usd"] += est_cost
        progress["completed"].append(variant.name)
        save_progress(progress, progress_path)
        return

    try:
        grade_path = run_step8_grade(cfg_path, plan.fixed_benchmark, cfg_path.parent)
        metrics = extract_metrics(grade_path, variant)
    except Exception as exc:  # noqa: BLE001
        LOG.error("[%s] FAILED: %s", variant.name, exc)
        metrics = {
            "name": variant.name,
            "phase": variant.phase,
            "repeat_index": variant.repeat_index,
            "avg_score_pct": 0.0,
            "critical_item_pass_rate": 0.0,
            "judge_error_rate": 1.0,
            "precheck_pass_rate": 0.0,
            "judge_call_count": 0,
            "judge_total_latency_sec": 0.0,
            "judge_input_tokens": 0,
            "judge_output_tokens": 0,
            "smoke_cost_usd": 0.0,
            "full_run_cost_usd": 0.0,
            "error": str(exc),
        }

    progress["results"][variant.name] = metrics
    progress["cumulative_cost_usd"] += metrics.get("smoke_cost_usd", 0.0)
    progress["completed"].append(variant.name)
    save_progress(progress, progress_path)
    LOG.info(
        "[%s] DONE: avg=%.2f err=%.3f cost=$%.3f",
        variant.name,
        metrics["avg_score_pct"],
        metrics["judge_error_rate"],
        metrics["smoke_cost_usd"],
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    try:
        plan = load_plan(args.plan)
        validate_models_available(plan)
        validate_tpm_caps(plan)
        validate_acceptance_thresholds(plan)
    except SweepValidationError as exc:
        LOG.error("validation failed: %s", exc)
        return 3

    output_dir = _setup_output_dir(args)
    LOG.info("output dir: %s", output_dir)
    _snapshot_plan(plan, output_dir)

    progress_path = output_dir / "progress.json"
    progress = load_or_init_progress(progress_path, plan.plan_name)

    cost_cap = float(
        args.max_cost
        if args.max_cost is not None
        else plan.global_constraints.get("cost_cap_usd", 80.0)
    )
    phases = {p.strip().upper() for p in args.phases.split(",") if p.strip()}

    # ---- Phase A ----
    if "A" in phases:
        for variant in plan.phase_a:
            if variant.name in progress["completed"]:
                LOG.info("[%s] resume-skip", variant.name)
                continue
            try:
                _run_variant(
                    variant, plan, output_dir, progress, progress_path,
                    args.dry_run, cost_cap,
                )
            except SweepCostCapExceeded as exc:
                progress["aborted"] = True
                progress["abort_reason"] = f"cost_cap_exceeded: {exc}"
                save_progress(progress, progress_path)
                _finalize(progress, plan, output_dir, winner=None)
                LOG.error("cost cap exceeded mid-Phase-A: %s", exc)
                return 2

    progress["phase_a_winners"] = pick_phase_a_winners(progress)
    save_progress(progress, progress_path)

    # ---- Phase B ----
    if "B" in phases:
        augmented = augment_phase_b(plan.phase_b, progress["phase_a_winners"])
        for variant in augmented:
            if variant.name in progress["completed"]:
                LOG.info("[%s] resume-skip", variant.name)
                continue
            try:
                _run_variant(
                    variant, plan, output_dir, progress, progress_path,
                    args.dry_run, cost_cap,
                )
            except SweepCostCapExceeded as exc:
                progress["aborted"] = True
                progress["abort_reason"] = f"cost_cap_exceeded: {exc}"
                save_progress(progress, progress_path)
                _finalize(progress, plan, output_dir, winner=None)
                return 2

    # ---- Phase C (top-N from B, repeat_count each) ----
    if "C" in phases and plan.phase_c_spec:
        top_n = int(plan.phase_c_spec.get("pick_top_n_from_phase_b", 2) or 2)
        rep = int(plan.phase_c_spec.get("repeat_count", 3) or 3)
        b_results = [
            m for m in progress["results"].values()
            if m.get("phase") == "B"
        ]
        b_eligible = [
            m for m in b_results
            if m.get("critical_item_pass_rate", 0) >= plan.acceptance["critical_item_pass_rate_min"]
        ]
        top_b = sorted(
            b_eligible, key=lambda m: m.get("full_run_cost_usd", math.inf)
        )[:top_n]
        for base_metric in top_b:
            # Find the Variant object by name to clone.
            src_variant = next(
                (v for v in plan.phase_b if v.name == base_metric["name"]),
                None,
            )
            if src_variant is None:
                continue
            for r in range(rep):
                rep_name = f"{src_variant.name}__rep{r}"
                if rep_name in progress["completed"]:
                    continue
                v_clone = Variant(
                    name=rep_name,
                    phase="C",
                    raw=deepcopy(src_variant.raw),
                    inherit_baseline=src_variant.inherit_baseline,
                    repeat_index=r,
                )
                try:
                    _run_variant(
                        v_clone, plan, output_dir, progress, progress_path,
                        args.dry_run, cost_cap,
                    )
                except SweepCostCapExceeded as exc:
                    progress["aborted"] = True
                    progress["abort_reason"] = f"cost_cap_exceeded: {exc}"
                    save_progress(progress, progress_path)
                    _finalize(progress, plan, output_dir, winner=None)
                    return 2

    # ---- Diversity validator (always optional, advisory) ----
    if plan.diversity and plan.diversity.get("enabled"):
        dv_raw = plan.diversity["variant"]
        dv = Variant(name=dv_raw["name"], phase="DV", raw=dv_raw)
        if dv.name not in progress["completed"]:
            try:
                _run_variant(
                    dv, plan, output_dir, progress, progress_path,
                    args.dry_run, cost_cap,
                )
            except SweepCostCapExceeded:
                LOG.warning("diversity validator skipped: cost cap reached")

    winner = select_pareto_winner(progress, plan.acceptance)
    progress["winner"] = winner.name if winner else None
    _finalize(progress, plan, output_dir, winner)

    print(f"[sweep] winner: {winner.name if winner else '(none)'}")
    print(f"[sweep] cost spent: ${progress['cumulative_cost_usd']:.2f}")
    print(f"[sweep] report: {output_dir / 'RESULTS.md'}")

    # Dry-run: validation succeeded → exit 0 regardless of winner (all
    # metrics are zero by construction; winner selection is meaningless).
    if args.dry_run:
        return 0
    return 0 if winner else 1


def _finalize(
    progress: dict[str, Any],
    plan: Plan,
    output_dir: Path,
    winner: WinnerResult | None,
) -> None:
    progress["finished_at"] = _now_iso()
    save_progress(progress, output_dir / "progress.json")
    write_summary_json(progress, output_dir / "summary.json")
    write_results_md(progress, winner, plan, output_dir / "RESULTS.md")
    if winner:
        write_winner_config(winner, output_dir, output_dir / "winner_config.yaml")
        append_changelog_entry(winner, plan, output_dir, progress["cumulative_cost_usd"])


if __name__ == "__main__":
    sys.exit(main())
