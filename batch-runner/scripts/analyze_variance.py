#!/usr/bin/env python3
"""Read the same corpus graded more than once and say how far the score moved.

Why this exists
---------------
``tasks/rebuilding_grading_task/303-variance-and-error.md`` asks whether the v2
grader gives the same answer twice. Its acceptance is three numbers:

    - task-level pct 표준편차 <= 5pp (3 runs)
    - judge_error_rate < 2%
    - CI 95% 폭 < 10pp

All three are only meaningful if the repeats really are repeats, so most of
this file is the check that they are, and only a little of it is arithmetic.

What has to be identical, and what cannot be
--------------------------------------------
A spread measured across runs that differed in their inputs measures the
difference in the inputs. So the task list, the gold revision, the grader
source, the grading config, the judge settings, the prompt, the rubric and the
renderer are compared field-for-field across every run, and a disagreement is
refused rather than reported -- see ``FROZEN_FIELDS``.

The Azure route fingerprint is deliberately **not** in that list. It is not
constant even within one run: stage 1's own accepted run carries two distinct
grader fingerprints in ``azure_ai_routes``, and `step9_merge_shards.py` says
in as many words that this is expected ("Even a 4-task anchor run already
observed two distinct grader fingerprints"), which is why it merges routes as
a union instead of demanding equality. Freezing it here would reject the very
run stage 1 accepted. It is reported instead, so a reader can see which routes
served which repeat and judge for themselves whether a difference matters.

Two inputs that are the same run
--------------------------------
The failure this is most careful about is being handed one run twice. Every
gate would pass -- a task compared with itself has a standard deviation of
zero, and zero is comfortably under five -- and the report would announce
perfect stability having measured nothing at all. So the file digests and the
``graded_at`` stamps must all differ, and identical ones are an error.

Which repeat a payload is
-------------------------
Nothing inside a payload records it. ``--run-ordinal`` reaches the output path
and is never written into the file or the schema, so the directory is the only
place that knows, and the label here is read from the path for exactly that
reason.

The confidence interval
-----------------------
The interval is on the corpus mean, because that is the number stage 1
published and the number a shortfall would be argued against. Two things move
it and both are resampled: which thirty tasks happened to be drawn (tasks are
resampled with replacement) and how the grader happened to answer on the day
(one of each drawn task's run-scores is then drawn with replacement). Either
alone would understate the width, so both are reported separately as well --
if one dominates, that is worth knowing before adding runs or adding tasks.

The seed is fixed. The report quotes this tool's output inside a block that a
test re-runs and compares byte-for-byte, so an unseeded interval would fail
that test every time it was checked.

Why the *worst* task decides the standard-deviation gate
--------------------------------------------------------
"task-level pct 표준편차 <= 5pp" reads as a statement about tasks, not about
their average, so the gate is on the largest per-task deviation. Averaging
would let one wildly unstable task hide behind twenty-nine steady ones, which
is the case the check exists to catch. The mean and median are printed too,
because the shape of the spread is what says whether instability is general or
local.

Which corpus this reads
-----------------------
Stage 2 repeats stage 1's thirty pinned tasks, so every run is held to stage
1's own identity check -- same task count, same ordered-id digest, same number
graded. That is deliberately not configurable. A tool that would happily
compare any two corpora is a tool that can be pointed at the wrong pair, and
stage 3 grades a different corpus under a different specification, which will
want its own pin rather than this one loosened.

Usage
-----
    python batch-runner/scripts/analyze_variance.py RUN1.json RUN2.json RUN3.json
    python batch-runner/scripts/analyze_variance.py RUN*.json --json

Exit status is 0 when every gate is met and 1 when any is missed, so a repeat
that drifted cannot be reported as stable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
import statistics
import sys
from pathlib import Path
from typing import Any

# The package root, so `scripts` and `core` both import whether this is run as
# `python batch-runner/scripts/analyze_variance.py` from the repository root or
# imported as `scripts.analyze_variance` under pytest.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.grade_payload import canonical_rate  # noqa: E402
from scripts import analyze_gold_ceiling as gold  # noqa: E402

# The three numbers stage 2 is accepted or rejected on, from
# `tasks/rebuilding_grading_task/303-variance-and-error.md`. The error ceiling
# is imported rather than restated: stage 1 and stage 2 are quoting the same
# 2% from the same specification family, and two copies would let one be
# edited alone.
TASK_PCT_STDEV_CEILING = 5.0
CI95_WIDTH_CEILING_PCT = 10.0
JUDGE_ERROR_RATE_CEILING = gold.JUDGE_ERROR_RATE_CEILING

# "3회 채점" -- the acceptance names the number of runs, so a two-run
# comparison is a partial answer rather than a passing one.
EXPECTED_RUN_COUNT = 3

# Enough resamples that the interval is stable in its third decimal, few
# enough that the report regenerates in about a second.
BOOTSTRAP_RESAMPLES = 10_000

# Any fixed value would do; this one is the date stage 2 was measured. What
# matters is only that it never changes, because the report's quoted block is
# re-derived and compared byte-for-byte.
BOOTSTRAP_SEED = 20260828

# What every run must agree on for the spread between them to mean anything.
# Each is compared as a whole value, so a nested change -- a different
# reasoning effort inside `judge`, a different revision inside `rubric` --
# fails here rather than passing because the top-level key still exists.
FROZEN_FIELDS: tuple[tuple[str, str], ...] = (
    ("task list", "expected_ordered_task_ids_sha256"),
    ("task count", "expected_task_count"),
    ("grader source", "grader_source_hash"),
    ("judge and grading config", "judge"),
    ("judge prompt", "prompt"),
    ("rubric", "rubric"),
    ("renderer", "renderer_fingerprint"),
    ("gold revision", "source_inference_revision"),
    ("inference provenance", "source_azure_ai_provenance_status"),
    ("payload schema", "schema_version"),
)

# Read from the output path, because the payload does not carry it.
REPEAT_DIRECTORY = re.compile(r"^run-(?P<ordinal>\d{3})$")


class RunsAreNotComparable(SystemExit):
    """The payloads are readable but are not repeats of one another."""


# ── Loading ────────────────────────────────────────────────────────────────


def run_label(path: Path) -> str:
    """Which repeat this is, from the only place that records it.

    `step8_grade.py` forks `_repeats/run-NNN/` above the shard fork and leaves
    run 1 on the canonical path, so a payload with no `_repeats` ancestor is
    the original rather than an unlabelled repeat.
    """
    for part in path.parts:
        found = REPEAT_DIRECTORY.match(part)
        if found:
            return f"run {int(found.group('ordinal'))}"
    return "run 1"


def load_run(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {
        "path": path,
        "label": run_label(path),
        "digest": hashlib.sha256(raw).hexdigest(),
        "payload": json.loads(raw.decode("utf-8")),
    }


def load_runs(paths: list[Path]) -> list[dict[str, Any]]:
    """Load, order by repeat, and make sure no two runs answer to one name.

    Labels come from the path, so two payloads that are not repeats of each
    other -- an original and a superseded original, say -- both read as "run 1".
    Every refusal message is written in terms of these labels, so a collision
    turns the one report a reader needs into "run 1 differs from run 1". The
    digest is appended only when that would otherwise happen, which keeps the
    ordinary three-run report reading as run 1, run 2, run 3.
    """
    runs = [load_run(path) for path in paths]
    runs.sort(key=lambda run: (run["label"], str(run["path"])))

    seen: dict[str, int] = {}
    for run in runs:
        seen[run["label"]] = seen.get(run["label"], 0) + 1
    for position, run in enumerate(runs, start=1):
        if seen[run["label"]] > 1:
            # Byte-identical files share a digest too, so position is the last
            # resort. That case is separately refused as a duplicate payload.
            run["label"] = f"{run['label']} [{run['digest'][:8]}/#{position}]"
    return runs


# ── Are these really repeats of each other? ────────────────────────────────


def _graded_task_ids(payload: dict[str, Any]) -> list[str]:
    return [str(task.get("task_id")) for task in payload.get("tasks") or []]


def freeze_problems(runs: list[dict[str, Any]]) -> list[str]:
    """Everything that would make a measured spread mean something else."""
    problems: list[str] = []

    for run in runs:
        for problem in gold._identity_problems(run["payload"]):
            problems.append(f"{run['label']} ({run['path'].name}): {problem}")

    reference = runs[0]
    for description, field in FROZEN_FIELDS:
        expected = reference["payload"].get(field)
        for run in runs[1:]:
            actual = run["payload"].get(field)
            if actual != expected:
                problems.append(
                    f"{description} differs: {reference['label']} has "
                    f"{field}={json.dumps(expected, sort_keys=True, ensure_ascii=False)[:160]}, "
                    f"{run['label']} has "
                    f"{json.dumps(actual, sort_keys=True, ensure_ascii=False)[:160]}"
                )

    expected_ids = _graded_task_ids(reference["payload"])
    for run in runs[1:]:
        actual_ids = _graded_task_ids(run["payload"])
        if actual_ids != expected_ids:
            missing = sorted(set(expected_ids) - set(actual_ids))
            extra = sorted(set(actual_ids) - set(expected_ids))
            problems.append(
                f"{run['label']} graded a different corpus: "
                f"{len(missing)} task(s) missing, {len(extra)} unexpected"
                + (f" (first missing {missing[0]})" if missing else "")
            )

    # One missing score is not a missing task, so the corpus check above lets
    # it through -- and then that task's deviation would be taken over fewer
    # runs than every other task's, which is a different measurement wearing
    # the same name.
    scores = per_task_scores(runs)
    thin = sorted(
        task_id for task_id, values in scores.items() if len(values) != len(runs)
    )
    for task_id in thin[:5]:
        problems.append(
            f"{task_id} has {len(scores[task_id])} score(s) across "
            f"{len(runs)} run(s), so its deviation would be taken over a "
            "smaller sample than every other task's"
        )
    if len(thin) > 5:
        problems.append(f"... and {len(thin) - 5} more task(s) missing a score")

    # One run handed in twice would pass every gate while measuring nothing.
    by_digest: dict[str, list[str]] = {}
    by_stamp: dict[str, list[str]] = {}
    for run in runs:
        by_digest.setdefault(run["digest"], []).append(str(run["path"]))
        by_stamp.setdefault(
            str(run["payload"].get("graded_at")), []
        ).append(run["label"])
    for digest, paths in by_digest.items():
        if len(paths) > 1:
            problems.append(
                f"the same payload was passed more than once (sha256 "
                f"{digest[:16]}): {paths}. Comparing a run with itself "
                "reports perfect stability and measures nothing."
            )
    for stamp, labels in by_stamp.items():
        if len(labels) > 1:
            problems.append(
                f"more than one run claims graded_at={stamp}: {labels}. Two "
                "repeats cannot have finished at the same instant."
            )

    return problems


# ── How far did each task move? ────────────────────────────────────────────


def per_task_scores(runs: list[dict[str, Any]]) -> dict[str, list[float]]:
    """Each task's ``pct``, one entry per run, in the order the runs were given."""
    scores: dict[str, list[float]] = {}
    for run in runs:
        for task in run["payload"].get("tasks") or []:
            task_id = str(task.get("task_id"))
            pct = task.get("pct")
            if pct is None:
                continue
            scores.setdefault(task_id, []).append(float(pct))
    return scores


def task_stability(
    runs: list[dict[str, Any]], scores: dict[str, list[float]]
) -> list[dict[str, Any]]:
    """One row per task, least stable first.

    The deviation is the sample standard deviation (n-1). Three runs are a
    sample of the grader's behaviour, not the whole of it, and the population
    form would report a spread about 18% narrower than the evidence supports
    -- which is the wrong direction for a number that has to clear a ceiling.
    """
    by_task = {}
    for run in runs:
        for task in run["payload"].get("tasks") or []:
            by_task.setdefault(str(task.get("task_id")), task)

    rows: list[dict[str, Any]] = []
    for task_id, values in scores.items():
        task = by_task.get(task_id, {})
        rows.append(
            {
                "task_id": task_id,
                "occupation": task.get("occupation"),
                "sector": task.get("sector"),
                "pct_by_run": [round(value, 2) for value in values],
                "mean_pct": round(statistics.fmean(values), 4),
                "stdev_pct": (
                    None if len(values) < 2 else round(statistics.stdev(values), 4)
                ),
                "range_pct": round(max(values) - min(values), 4),
                "runs": len(values),
            }
        )
    rows.sort(
        key=lambda row: (
            -(row["stdev_pct"] if row["stdev_pct"] is not None else -1.0),
            row["task_id"],
        )
    )
    return rows


# ── How wide is the corpus mean? ───────────────────────────────────────────


def _percentile(sorted_values: list[float], q: float) -> float:
    """Linear-interpolated percentile of an already-sorted list."""
    if not sorted_values:
        raise ValueError("no values to take a percentile of")
    if len(sorted_values) == 1:
        return sorted_values[0]
    rank = (q / 100.0) * (len(sorted_values) - 1)
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return sorted_values[low]
    weight = rank - low
    return sorted_values[low] + (sorted_values[high] - sorted_values[low]) * weight


def bootstrap_mean_ci(
    scores: dict[str, list[float]],
    *,
    resamples: int,
    seed: int,
    resample_tasks: bool = True,
    resample_runs: bool = True,
) -> dict[str, Any]:
    """A 95% interval on the corpus mean, by resampling with replacement.

    ``resample_tasks`` and ``resample_runs`` are separable so the two sources
    of width can be reported apart from each other as well as together. With
    both off there is nothing to resample and the interval is a point, which
    is why the caller never asks for that.
    """
    task_ids = sorted(scores)
    count = len(task_ids)
    if count == 0:
        raise ValueError("no task scores to resample")

    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(resamples):
        total = 0.0
        for position in range(count):
            task_id = task_ids[rng.randrange(count)] if resample_tasks else task_ids[position]
            values = scores[task_id]
            if resample_runs:
                total += values[rng.randrange(len(values))]
            else:
                total += statistics.fmean(values)
        means.append(total / count)

    means.sort()
    low = _percentile(means, 2.5)
    high = _percentile(means, 97.5)
    return {
        "resamples": resamples,
        "seed": seed,
        "resampled": (
            ("tasks" if resample_tasks else "")
            + (" and runs" if resample_tasks and resample_runs else "")
            + ("runs" if resample_runs and not resample_tasks else "")
        ),
        "low_pct": round(low, 4),
        "high_pct": round(high, 4),
        "width_pct": round(high - low, 4),
    }


# ── How often did the judge fail to answer? ────────────────────────────────


def judge_errors(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Per-run and pooled error rates, recomputed rather than taken on trust.

    The published rate is checked against a recount from the items, because a
    rate that disagrees with its own payload is the one number in this report
    that nothing else would catch.
    """
    per_run: list[dict[str, Any]] = []
    pooled_errors = 0
    pooled_items = 0

    for run in runs:
        errors = 0
        items = 0
        for task in run["payload"].get("tasks") or []:
            for item in task.get("items") or []:
                if item.get("decided_by") != "judge":
                    continue
                items += 1
                if item.get("verdict") == "judge_error":
                    errors += 1
        recomputed = canonical_rate(errors, items)
        published = (
            (run["payload"].get("summary") or {}).get("wow") or {}
        ).get("judge_error_rate")
        pooled_errors += errors
        pooled_items += items
        per_run.append(
            {
                "label": run["label"],
                "judge_items": items,
                "judge_errors": errors,
                "recomputed_rate": recomputed,
                "published_rate": published,
                "agrees_with_payload": published == recomputed,
                "met": recomputed < JUDGE_ERROR_RATE_CEILING,
            }
        )

    return {
        "per_run": per_run,
        "pooled_judge_items": pooled_items,
        "pooled_judge_errors": pooled_errors,
        "pooled_rate": canonical_rate(pooled_errors, pooled_items),
        "disagreements": [
            row["label"] for row in per_run if not row["agrees_with_payload"]
        ],
    }


# ── What did each run cost and call? ───────────────────────────────────────


def usage_by_run(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for run in runs:
        summary = run["payload"].get("summary") or {}
        cost = summary.get("cost") or {}
        compat = summary.get("openai_compat") or {}
        rows.append(
            {
                "label": run["label"],
                "path": str(run["path"]),
                "graded_at": run["payload"].get("graded_at"),
                "grade_file_sha256": run["digest"],
                "mean_pct": compat.get("avg_score_pct"),
                "total_judge_calls": cost.get("total_judge_calls"),
                "total_main_judge_calls": cost.get("total_main_judge_calls"),
                "total_perception_calls": cost.get("total_perception_calls"),
                "perception_calls_by_modality": gold.perception_calls_by_modality(
                    run["payload"]
                ),
                "main_input_tokens": cost.get("main_input_tokens"),
                "main_output_tokens": cost.get("main_output_tokens"),
                "main_cached_tokens": cost.get("main_cached_tokens"),
                "perception_input_tokens": cost.get("perception_input_tokens"),
                "perception_output_tokens": cost.get("perception_output_tokens"),
                "total_judge_latency_sec": cost.get("total_judge_latency_sec"),
                "usage_complete": cost.get("usage_complete"),
                "estimated_cost_usd": cost.get("estimated_cost_usd"),
                "pricing_complete": cost.get("pricing_complete"),
                "unpriced_models": cost.get("unpriced_models"),
                # Where the money actually is. The three legacy fields above
                # are pinned by contract and cannot report a run's cost; see
                # `analyze_gold_ceiling._bill_receipt`.
                "receipt": gold._bill_receipt(summary),
                "azure_ai_routes": [
                    route.get("runtime_fingerprint")
                    for route in run["payload"].get("azure_ai_routes") or []
                ],
            }
        )
    return rows


# ── Putting it together ────────────────────────────────────────────────────


def analyze(
    runs: list[dict[str, Any]],
    *,
    resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, Any]:
    scores = per_task_scores(runs)
    stability = task_stability(runs, scores)
    deviations = [
        row["stdev_pct"] for row in stability if row["stdev_pct"] is not None
    ]
    errors = judge_errors(runs)

    both = bootstrap_mean_ci(scores, resamples=resamples, seed=seed)
    tasks_only = bootstrap_mean_ci(
        scores, resamples=resamples, seed=seed, resample_runs=False
    )
    runs_only = bootstrap_mean_ci(
        scores, resamples=resamples, seed=seed, resample_tasks=False
    )

    max_stdev = max(deviations) if deviations else None
    gates = {
        "runs_compared": {
            "value": len(runs),
            "floor": EXPECTED_RUN_COUNT,
            "met": len(runs) >= EXPECTED_RUN_COUNT,
        },
        "max_task_pct_stdev": {
            "value": max_stdev,
            "ceiling": TASK_PCT_STDEV_CEILING,
            "met": max_stdev is not None and max_stdev <= TASK_PCT_STDEV_CEILING,
        },
        "judge_error_rate": {
            "value": errors["pooled_rate"],
            "ceiling": JUDGE_ERROR_RATE_CEILING,
            "met": (
                errors["pooled_rate"] < JUDGE_ERROR_RATE_CEILING
                and all(row["met"] for row in errors["per_run"])
                and not errors["disagreements"]
            ),
        },
        "bootstrap_ci95_width_pct": {
            "value": both["width_pct"],
            "ceiling": CI95_WIDTH_CEILING_PCT,
            "met": both["width_pct"] < CI95_WIDTH_CEILING_PCT,
        },
    }

    reference = runs[0]["payload"]
    corpus_means = [
        statistics.fmean(
            [
                float(task["pct"])
                for task in run["payload"].get("tasks") or []
                if task.get("pct") is not None
            ]
        )
        for run in runs
    ]

    return {
        "frozen": {
            "runs": [
                {"label": run["label"], "path": str(run["path"])} for run in runs
            ],
            **{field: reference.get(field) for _, field in FROZEN_FIELDS},
        },
        "gates": gates,
        "all_gates_met": all(gate["met"] for gate in gates.values()),
        "corpus": {
            "tasks": len(scores),
            "mean_pct_by_run": [round(value, 4) for value in corpus_means],
            "mean_pct_across_runs": round(statistics.fmean(corpus_means), 4),
            "mean_pct_spread": round(max(corpus_means) - min(corpus_means), 4),
            "stdev_of_run_means": (
                None
                if len(corpus_means) < 2
                else round(statistics.stdev(corpus_means), 4)
            ),
        },
        "stability": {
            "max_stdev_pct": max_stdev,
            "mean_stdev_pct": (
                None if not deviations else round(statistics.fmean(deviations), 4)
            ),
            "median_stdev_pct": (
                None if not deviations else round(statistics.median(deviations), 4)
            ),
            "tasks_over_ceiling": [
                row["task_id"]
                for row in stability
                if row["stdev_pct"] is not None
                and row["stdev_pct"] > TASK_PCT_STDEV_CEILING
            ],
            "identical_across_runs": sum(
                1 for row in stability if row["range_pct"] == 0.0
            ),
            "per_task": stability,
        },
        "confidence_interval": {
            "tasks_and_runs": both,
            "tasks_only": tasks_only,
            "runs_only": runs_only,
        },
        "judge_errors": errors,
        "usage": usage_by_run(runs),
    }


# ── Rendering ──────────────────────────────────────────────────────────────


def _mark(met: bool) -> str:
    return "PASS" if met else "MISS"


def _render(report: dict[str, Any], *, mover_limit: int) -> str:
    lines: list[str] = []
    frozen = report["frozen"]
    lines.append("Repeat variance — stage 2")
    lines.append("=" * 68)
    for entry in frozen["runs"]:
        lines.append(f"  {entry['label']:<8} {entry['path']}")
    lines.append("")
    judge = frozen.get("judge") or {}
    lines.append(f"  task list       {frozen.get('expected_ordered_task_ids_sha256')}")
    lines.append(f"  grader source   {frozen.get('grader_source_hash')}")
    lines.append(
        f"  judge           {judge.get('model')} "
        f"(effort {judge.get('reasoning_effort')}, "
        f"temperature {judge.get('temperature')}, seed {judge.get('seed')})"
    )
    lines.append(f"  grading config  {judge.get('config_name')} / {judge.get('config_hash')}")
    prompt = frozen.get("prompt") or {}
    lines.append(f"  prompt          {prompt.get('template')} {prompt.get('version')}")
    lines.append(
        f"  renderer        "
        f"{gold._describe_renderer(frozen.get('renderer_fingerprint'))}"
    )
    lines.append(f"  gold revision   {frozen.get('source_inference_revision')}")
    lines.append("")

    lines.append("Thresholds")
    lines.append("-" * 68)
    gates = report["gates"]
    count = gates["runs_compared"]
    stdev = gates["max_task_pct_stdev"]
    err = gates["judge_error_rate"]
    width = gates["bootstrap_ci95_width_pct"]
    lines.append(
        f"  runs compared           {count['value']}   "
        f"(needs >= {count['floor']})   {_mark(count['met'])}"
    )
    lines.append(
        f"  worst task stdev        {stdev['value']}pp   "
        f"(needs <= {stdev['ceiling']}pp)   {_mark(stdev['met'])}"
    )
    lines.append(
        f"  judge error rate        {err['value']}   "
        f"(needs < {err['ceiling']})   {_mark(err['met'])}"
    )
    lines.append(
        f"  95% CI width            {width['value']}pp   "
        f"(needs < {width['ceiling']}pp)   {_mark(width['met'])}"
    )
    lines.append("")

    corpus = report["corpus"]
    lines.append("Corpus mean")
    lines.append("-" * 68)
    means = ", ".join(f"{value}%" for value in corpus["mean_pct_by_run"])
    lines.append(f"  per run                 {means}")
    lines.append(f"  across runs             {corpus['mean_pct_across_runs']}%")
    lines.append(
        f"  spread / stdev          {corpus['mean_pct_spread']}pp / "
        f"{corpus['stdev_of_run_means']}pp"
    )
    lines.append("")

    interval = report["confidence_interval"]
    lines.append("95% confidence interval on the corpus mean (bootstrap)")
    lines.append("-" * 68)
    for key, caption in (
        ("tasks_and_runs", "tasks and runs"),
        ("tasks_only", "tasks only"),
        ("runs_only", "runs only"),
    ):
        block = interval[key]
        lines.append(
            f"  {caption:<22} [{block['low_pct']}%, {block['high_pct']}%]   "
            f"width {block['width_pct']}pp"
        )
    both = interval["tasks_and_runs"]
    lines.append(
        f"  {both['resamples']} resamples, seed {both['seed']}, "
        "sampled with replacement"
    )
    lines.append("")

    stability = report["stability"]
    lines.append("Per-task stability")
    lines.append("-" * 68)
    lines.append(
        f"  stdev across {report['corpus']['tasks']} task(s): "
        f"worst {stability['max_stdev_pct']}pp, "
        f"mean {stability['mean_stdev_pct']}pp, "
        f"median {stability['median_stdev_pct']}pp"
    )
    lines.append(
        f"  scored identically in every run: "
        f"{stability['identical_across_runs']} task(s)"
    )
    if stability["tasks_over_ceiling"]:
        lines.append(
            f"  over the {TASK_PCT_STDEV_CEILING}pp ceiling: "
            f"{len(stability['tasks_over_ceiling'])} task(s)"
        )
        lines.extend(gold._wrapped_ids(stability["tasks_over_ceiling"]))
    else:
        lines.append(f"  over the {TASK_PCT_STDEV_CEILING}pp ceiling: none")
    lines.append("")

    lines.append("Least stable tasks")
    lines.append("-" * 68)
    for row in stability["per_task"][:mover_limit]:
        values = ", ".join(f"{value:.2f}%" for value in row["pct_by_run"])
        lines.append(
            f"  stdev {row['stdev_pct']:>7}pp  range {row['range_pct']:>6}pp  "
            f"{row['task_id']}"
        )
        lines.append(
            f"      {values}  ·  "
            f"{(row['occupation'] or 'occupation unrecorded')[:44]}"
        )
    remaining = len(stability["per_task"]) - mover_limit
    if remaining > 0:
        lines.append(f"  ... and {remaining} more (use --json for all of them)")
    lines.append("")

    errors = report["judge_errors"]
    lines.append("Judge errors")
    lines.append("-" * 68)
    for row in errors["per_run"]:
        note = "" if row["agrees_with_payload"] else "  DISAGREES WITH PAYLOAD"
        lines.append(
            f"  {row['label']:<8} {row['judge_errors']}/{row['judge_items']} "
            f"= {row['recomputed_rate']}   {_mark(row['met'])}{note}"
        )
    lines.append(
        f"  pooled   {errors['pooled_judge_errors']}/{errors['pooled_judge_items']} "
        f"= {errors['pooled_rate']}"
    )
    lines.append("")

    lines.append("Usage per run")
    lines.append("-" * 68)
    for row in report["usage"]:
        lines.append(f"  {row['label']}  graded at {row['graded_at']}")
        lines.append(
            f"      judge calls         {row['total_judge_calls']} "
            f"({row['total_main_judge_calls']} main, "
            f"{row['total_perception_calls']} perception)"
        )
        for modality, calls in (row["perception_calls_by_modality"] or {}).items():
            lines.append(f"        {modality:<18} {calls}")
        lines.append(
            f"      main tokens         in {row['main_input_tokens']}, "
            f"out {row['main_output_tokens']}, "
            f"cached {row['main_cached_tokens']}"
        )
        lines.append(
            f"      perception tokens   in {row['perception_input_tokens']}, "
            f"out {row['perception_output_tokens']}"
        )
        lines.append(
            f"      judge latency       {row['total_judge_latency_sec']}s, "
            f"usage complete {row['usage_complete']}"
        )
        # An unpriced run is never rendered as free, and a floor is never
        # rendered as a total. Unknown is not zero.
        receipt = row.get("receipt")
        status = receipt.get("status") if receipt else None
        floor = receipt.get("known_cost_usd") if receipt else None
        if status == gold.STATUS_COMPLETE:
            lines.append(
                f"      estimated cost      ${receipt['estimated_cost_usd']} "
                f"over {receipt['model_calls']} priced calls"
            )
        elif status == gold.STATUS_PARTIAL and floor:
            lines.append(
                f"      estimated cost      AT LEAST ${floor} — a floor, not "
                "a total"
            )
            lines.append(
                f"      unpriced because    "
                f"{', '.join(receipt['missing_reasons'])}"
            )
        elif status in (
            gold.STATUS_PARTIAL,
            gold.STATUS_UNAVAILABLE,
            gold.STATUS_NOT_RUN,
        ):
            # A partial receipt whose floor is zero has no floor to state.
            # "At least $0" would be true and useless, and reads as "free".
            lines.append(
                "      estimated cost      UNKNOWN — nothing in this run "
                "could be priced"
            )
            lines.append(
                f"      unpriced because    "
                f"{', '.join(receipt['missing_reasons'])}"
            )
        else:
            lines.append(
                "      estimated cost      UNKNOWN — this grade predates the "
                "cost receipt"
            )
            lines.append(f"      judge models        {row['unpriced_models']}")
        # Reported, never frozen: route drift is expected within a single run,
        # so a difference here is context rather than a fault.
        for fingerprint in row["azure_ai_routes"]:
            lines.append(f"      azure route         {fingerprint}")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "grade_files",
        type=Path,
        nargs="+",
        help="two or more merged grade payloads of the same corpus",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit the whole analysis as JSON instead of a readable report",
    )
    parser.add_argument(
        "--mover-limit",
        type=int,
        default=10,
        help="how many least-stable tasks to print in the readable report",
    )
    parser.add_argument(
        "--bootstrap-resamples",
        type=int,
        default=BOOTSTRAP_RESAMPLES,
        help="how many times to resample the corpus for the interval",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=BOOTSTRAP_SEED,
        help=(
            "the bootstrap seed. Fixed by default so the report's quoted "
            "output can be re-derived byte-for-byte"
        ),
    )
    args = parser.parse_args(argv)

    if len(args.grade_files) < 2:
        parser.error("variance needs at least two runs to compare")

    runs = load_runs(args.grade_files)

    problems = freeze_problems(runs)
    if problems:
        raise RunsAreNotComparable(
            "these payloads are not repeats of one another, so any spread "
            "between them would measure the difference rather than the "
            "grader:\n  - " + "\n  - ".join(problems)
        )

    report = analyze(
        runs, resamples=args.bootstrap_resamples, seed=args.seed
    )

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(_render(report, mover_limit=args.mover_limit))

    return 0 if report["all_gates_met"] else 1


if __name__ == "__main__":
    sys.exit(main())
