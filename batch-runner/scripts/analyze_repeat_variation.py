#!/usr/bin/env python3
"""Measure how far the grader alone moves when the same answers are graded again.

Why this exists
---------------
``tasks/rebuilding_grading_task/315-repeat-variation-prereg.md`` separates two
things that a single published score has already mixed together:

    task difficulty   which thirty tasks were drawn
    grader wobble     what the grader says the second time about the same words

Stage 1 published 82.87%. That number is only worth arguing about if the second
component is small, and stage 2's own card says its confidence-interval gate
does not measure it -- resampling tasks gives 7.32pp, resampling runs gives
0.86pp, and the gate reports neither separately. So this tool does not re-score
that gate. It builds an estimator that targets the second component from the
start, by pairing: the same task's score in run A and in run B are drawn
together, so whether that task was hard or easy cancels inside the difference
and only the movement between the two gradings is left.

Everything here is a read. No grade payload is rewritten, and no model is
called, so running this costs nothing.

Why a second tool instead of an option on the first
---------------------------------------------------
``analyze_variance.py`` reproduces the three numbers stage 2 published. Changing
its method would stop those numbers reproducing, which is the one thing a
published result may not do. The preregistration says so in as many words, so
this is a separate file that shares no code with it.

What has to be identical, and what is refused
---------------------------------------------
Section 4 of the preregistration pins twelve fingerprints. They are checked
twice over: every run must agree with every other run, and every run must also
match the literal value written into the preregistration. Agreement alone would
accept three runs of some *other* cohort that happened to agree with each
other, and this document's numbers are about one cohort.

``azure_ai_routes`` is deliberately not among them. It is not constant even
inside a single run -- ``step9_merge_shards.py`` merges routes as a union for
exactly that reason -- so freezing it would reject the runs stage 1 accepted.
It is reported instead.

The schema version is pinned to ``1.3`` rather than to whatever the code says
today. ``step8_grade.py`` has since moved to ``1.4``; pinning to the current
value would make these three files reject themselves.

Two inputs that are the same run
--------------------------------
The most dangerous failure available here is being handed one file twice. Every
difference metric would come out at exactly zero, zero passes every gate with
room to spare, and the report would announce perfect stability having compared
nothing. So the three file digests and the three ``graded_at`` stamps must all
differ, and a repeat is an error rather than a warning.

Why the resampling unit is the task and never the item
-------------------------------------------------------
Treating 1,433 rubric items as 1,433 independent observations makes the sample
look large and is not true: items inside one task share an output, a set of
files and a grading context, and when a task moves its items move together. The
preregistration measured both ways on this data and recorded that the naive
item bootstrap reports an interval about 1.5x narrower. So the unit here is the
task, always, and drawing a task brings all of its items with it. The item
bootstrap is still computed, but only to report that ratio, and it is labelled
as not the official interval wherever it appears.

The seed and the resample count are fixed
------------------------------------------
The result document quotes this tool's output inside a block that a test
re-runs and compares byte for byte. An unseeded interval would fail that test
every time it was checked, and a check that cannot be run is a check that is
not done. Passing a different seed or a different resample count is allowed so
that a mutation test can show the checks notice, but it turns the run's own
verdict red: the analysis is only the registered analysis at the registered
settings.

Usage
-----
    python batch-runner/scripts/analyze_repeat_variation.py RUN1.json RUN2.json RUN3.json
    python batch-runner/scripts/analyze_repeat_variation.py RUN*.json --json

Exit status is 0 when the preregistered target is met and 1 when it is not, so
a spread that missed the target cannot be reported as if it had met it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import statistics
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


# Section 8. Fixed before the analysis was written, and quoted by the result
# document, so neither may be changed without changing both.
BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 20260901
PERCENTILE_LOW = 2.5
PERCENTILE_HIGH = 97.5

# Section 8's target: the 95% interval on how far one run's corpus mean moves
# when the same answers are graded again. 82.87% is 7.13pp short of 90%, so a
# half-width of 1.0pp decides that question with a factor of seven to spare.
HALF_WIDTH_TARGET_PP = 1.0

# Section 4. Three runs, thirty tasks, and all three pairs -- picking one pair
# would be picking the answer.
EXPECTED_RUN_COUNT = 3
EXPECTED_TASK_COUNT = 30
PAIRS: tuple[tuple[int, int], ...] = ((0, 1), (0, 2), (1, 2))

# Section 9. A verdict outside this vocabulary stops the run rather than being
# given a handling rule invented on the spot.
VERDICT_VOCABULARY: tuple[str, ...] = ("pass", "partial", "fail", "judge_error")

# pass/partial/fail sit on one axis and a move across it can be one step or
# two; judge_error is not on that axis at all, so it has no rank.
VERDICT_RANK: dict[str, int] = {"fail": 0, "partial": 1, "pass": 2}

# Section 11. This cohort has no audio items, which is why the audio flipping
# recorded in 307 and 310-312 cannot be inside these intervals. That is a
# checkable fact rather than a promise, so it is checked.
FORBIDDEN_MODALITY = "audio"

# Section 4's table, value for value. Each entry is a human label, a path into
# the payload, and the value the preregistration wrote down.
PINNED_FINGERPRINTS: tuple[tuple[str, tuple[str, ...], Any], ...] = (
    (
        "task list digest",
        ("expected_ordered_task_ids_sha256",),
        "82d14ac9bf9c3ad37920fb781ee961f5e20805c52618df0d0cdb9d5e677a7e8b",
    ),
    ("task count", ("expected_task_count",), 30),
    (
        "grader source digest",
        ("grader_source_hash",),
        "c33d9d55703fbf5de5f988d427e34efd44d7a73306412caac88a753bad16ff4e",
    ),
    ("grading config", ("judge", "config_name"), "gold_ceiling_30_v2_sol_max"),
    ("grading config hash", ("judge", "config_hash"), "d1bfc8217c9981d2"),
    ("judge model", ("judge", "model"), "gpt-5.6-sol"),
    ("judge deployment", ("judge", "deployment"), "gpt-5.6-sol"),
    ("api version", ("judge", "api_version"), "2025-04-01-preview"),
    ("reasoning effort", ("judge", "reasoning_effort"), "max"),
    ("temperature", ("judge", "temperature"), 0),
    ("seed", ("judge", "seed"), 42),
    ("judge prompt version", ("prompt", "version"), "v2.2"),
    (
        "rubric revision",
        ("rubric", "revision"),
        "11e7900cdcac61bc4daf59e65feb238acda98fbf",
    ),
    (
        "renderer",
        ("renderer_fingerprint",),
        {
            "libreoffice_binary": "soffice",
            "libreoffice_version": "LibreOffice 24.2.7.2 420(Build:2)",
            "pymupdf_version": "1.28.2",
        },
    ),
    (
        "gold revision",
        ("source_inference_revision",),
        "11e7900cdcac61bc4daf59e65feb238acda98fbf",
    ),
    # Read the note in the module docstring before touching this one.
    ("payload schema", ("schema_version",), "1.3"),
)


class RepeatsAreNotComparable(SystemExit):
    """Raised when the inputs cannot answer the question that was asked.

    Section 12 lists what invalidates the analysis. Every one of them is this
    exception rather than a warning, because a warning printed above a number
    is a number that gets quoted without the warning.
    """


def _dig(payload: dict[str, Any], path: tuple[str, ...]) -> Any:
    """Follow a key path, returning ``None`` rather than raising on a gap."""
    node: Any = payload
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    return node


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_runs(paths: list[Path]) -> list[dict[str, Any]]:
    """Read the payloads and remember which file each one came from.

    The file digest is carried on the payload under a private key. Nothing in a
    grade payload records which repeat it is or where it was read from, and the
    same-file-twice check needs both.
    """
    runs: list[dict[str, Any]] = []
    for ordinal, path in enumerate(paths, start=1):
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["_source_path"] = str(path)
        payload["_source_digest"] = _digest(path)
        payload["_label"] = f"run-{ordinal:03d}"
        runs.append(payload)
    return runs


def fingerprint_problems(runs: list[dict[str, Any]]) -> list[str]:
    """Section 12 checks 1, 2, 3 and 6, plus the literal match from section 4.

    Ordered so that the cheapest and most fundamental disagreement is reported
    first: three runs of different cohorts is a different fault from three runs
    of the same cohort that drifted.
    """
    problems: list[str] = []

    if len(runs) != EXPECTED_RUN_COUNT:
        problems.append(
            f"this analysis is registered for {EXPECTED_RUN_COUNT} runs and "
            f"was given {len(runs)}"
        )

    # Check 1 and section 4's literals, in one pass so a mismatch says both
    # what the runs disagreed about and what the document expected.
    for label, path, expected in PINNED_FINGERPRINTS:
        observed = [_dig(run, path) for run in runs]
        field = ".".join(path)
        if len(set(json.dumps(v, sort_keys=True) for v in observed)) > 1:
            rendered = " | ".join(
                f"{run['_label']}={json.dumps(value, ensure_ascii=False)}"
                for run, value in zip(runs, observed)
            )
            problems.append(
                f"{label} ({field}) differs between runs: {rendered}. A spread "
                "measured across runs that differed here would measure that "
                "difference, not the grader"
            )
            continue
        if observed[0] != expected:
            problems.append(
                f"{label} ({field}) is "
                f"{json.dumps(observed[0], ensure_ascii=False)}, and the "
                "preregistration pinned "
                f"{json.dumps(expected, ensure_ascii=False)}. These are not "
                "the runs this analysis was registered for"
            )

    # Check 2. Being handed one run twice is the failure that would pass every
    # gate having measured nothing.
    for field in ("_source_digest", "graded_at"):
        seen: dict[Any, str] = {}
        for run in runs:
            value = run.get(field)
            if value in seen:
                problems.append(
                    f"{run['_label']} and {seen[value]} have the same "
                    f"{field.lstrip('_')}, so at least two of these inputs are "
                    "the same run. Comparing a run with itself reports zero "
                    "movement and proves nothing"
                )
            else:
                seen[value] = run["_label"]

    # Check 6, and section 9's rule that a missing score stops the run rather
    # than being dropped -- dropping a task quietly moves the mean towards the
    # tasks that survived.
    for run in runs:
        tasks = run.get("tasks") or []
        if len(tasks) != EXPECTED_TASK_COUNT:
            problems.append(
                f"{run['_label']} graded {len(tasks)} tasks and this analysis "
                f"is registered for {EXPECTED_TASK_COUNT}"
            )
        unscored = [t["task_id"] for t in tasks if t.get("pct") is None]
        if unscored:
            problems.append(
                f"{run['_label']} has no score for {len(unscored)} task(s): "
                f"{', '.join(sorted(unscored)[:5])}. A task with no score is "
                "not quietly dropped"
            )

    return problems


def _item_index(run: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for task in run["tasks"]:
        for item in task["items"]:
            index[(task["task_id"], item["rubric_item_id"])] = item
    return index


def _document_order(run: dict[str, Any]) -> list[str]:
    """Task ids in the order the first payload lists them.

    Not sorted. The resampling draws from this list, so the order is part of
    the recipe that reproduces the preregistration's interval, and sorting it
    would move the endpoints by a few thousandths for no reason at all.
    """
    return [task["task_id"] for task in run["tasks"]]


def shape_problems(runs: list[dict[str, Any]]) -> list[str]:
    """Section 12 checks 4, 5 and 7.

    Kept apart from the fingerprint checks because these read the body of the
    payload rather than its header, and because a caller that wants to know
    whether two files are the same run should not have to load every item to
    find out.
    """
    problems: list[str] = []

    indexes = [_item_index(run) for run in runs]
    key_sets = [frozenset(index) for index in indexes]
    if len(set(key_sets)) > 1:
        shared = frozenset.intersection(*key_sets)
        for run, keys in zip(runs, key_sets):
            missing = keys - shared
            if missing:
                sample = ", ".join(
                    f"{task}/{item}" for task, item in sorted(missing)[:3]
                )
                problems.append(
                    f"{run['_label']} carries {len(missing)} rubric item(s) "
                    f"the other runs do not, for example {sample}. Items that "
                    "are not in every run cannot be paired"
                )

    for run, index in zip(runs, indexes):
        strange = sorted(
            {
                str(item.get("verdict"))
                for item in index.values()
                if item.get("verdict") not in VERDICT_VOCABULARY
            }
        )
        if strange:
            problems.append(
                f"{run['_label']} contains verdict value(s) outside the "
                f"registered vocabulary: {', '.join(strange)}. A handling rule "
                "is not invented while the numbers are being produced"
            )

        audio = [
            key
            for key, item in index.items()
            if item.get("routing_modality") == FORBIDDEN_MODALITY
        ]
        if audio:
            problems.append(
                f"{run['_label']} contains {len(audio)} {FORBIDDEN_MODALITY} "
                "item(s). Section 11 records this cohort as having none, and "
                "the audio flipping measured elsewhere must not be folded into "
                "these intervals"
            )

    return problems


def common_denominator_keys(runs: list[dict[str, Any]]) -> set[tuple[str, str]]:
    """Items that carry a score in every run.

    Section 5. A ``judge_error`` verdict takes its item out of the numerator
    *and* the denominator, so the corpus total moves between runs and a plain
    difference of two published percentages mixes "the verdict changed" with
    "the denominator changed". Task ``a328feea`` is the clear case: the same
    18.6 points is 84.55% out of 22 and 77.50% out of 24, so the run where the
    grader failed scores higher.
    """
    indexes = [_item_index(run) for run in runs]
    shared = frozenset.intersection(*(frozenset(index) for index in indexes))
    return {
        key
        for key in shared
        if not any(index[key].get("score_excluded") for index in indexes)
    }


def denominator_movement(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Report the moving denominator instead of absorbing it.

    Section 5 asks for this as a metric in its own right. Quietly correcting
    for it would be this document committing the fault it was written to point
    out.
    """
    per_task: list[dict[str, Any]] = []
    for task_id in _document_order(runs[0]):
        maxima = []
        for run in runs:
            task = next(t for t in run["tasks"] if t["task_id"] == task_id)
            maxima.append(task["total_max"])
        if len(set(maxima)) > 1:
            per_task.append({"task_id": task_id, "total_max": maxima})

    excluded = 0
    judge_errors = 0
    mismatched = 0
    for run in runs:
        index = _item_index(run)
        for item in index.values():
            is_excluded = bool(item.get("score_excluded"))
            is_error = item.get("verdict") == "judge_error"
            excluded += is_excluded
            judge_errors += is_error
            mismatched += is_excluded != is_error

    shared = frozenset.intersection(
        *(frozenset(_item_index(run)) for run in runs)
    )
    common = common_denominator_keys(runs)

    return {
        "tasks_whose_total_max_moved": per_task,
        "shared_items": len(shared),
        "items_in_common_denominator": len(common),
        "items_dropped_from_common_denominator": len(shared) - len(common),
        "score_excluded_events": excluded,
        "judge_error_events": judge_errors,
        # Section 5 says these are the same four events. If they ever stop
        # being the same events the denominator has a second cause and the
        # rule above stops being complete, so it is measured rather than
        # assumed.
        "excluded_and_error_disagree": mismatched,
    }


def per_task_percent(
    runs: list[dict[str, Any]], keys: set[tuple[str, str]] | None
) -> dict[str, list[float]]:
    """Each task's percentage in each run.

    ``keys`` restricts the arithmetic to the common denominator. Passing
    ``None`` reads the ``pct`` the payload published, which is the secondary
    baseline that joins these numbers to the ones stage 1 announced.
    """
    scores: dict[str, list[float]] = {}
    for task_id in _document_order(runs[0]):
        row: list[float] = []
        for run in runs:
            task = next(t for t in run["tasks"] if t["task_id"] == task_id)
            if keys is None:
                row.append(float(task["pct"]))
                continue
            awarded = 0.0
            maximum = 0.0
            for item in task["items"]:
                if (task_id, item["rubric_item_id"]) not in keys:
                    continue
                awarded += float(item["awarded_score"])
                maximum += float(item["max_score"])
            row.append(100.0 * awarded / maximum if maximum else 0.0)
        scores[task_id] = row
    return scores


def percentile(sorted_values: list[float], q: float) -> float:
    """Linear-interpolated percentile.

    Section 8 fixes the method as percentile rather than BCa: at n=30 with
    clustered draws the acceleration term is unstable, and an interval whose
    correction is noisier than the thing it corrects is not an improvement.
    """
    if len(sorted_values) == 1:
        return sorted_values[0]
    rank = (q / 100.0) * (len(sorted_values) - 1)
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return sorted_values[low]
    weight = rank - low
    return sorted_values[low] + (sorted_values[high] - sorted_values[low]) * weight


def _interval(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    low = percentile(ordered, PERCENTILE_LOW)
    high = percentile(ordered, PERCENTILE_HIGH)
    return {
        "low": low,
        "high": high,
        "width": high - low,
        "half_width": (high - low) / 2.0,
    }


def cluster_bootstrap_ratio(
    task_ids: list[str],
    numerator: dict[str, float],
    denominator: dict[str, float],
    *,
    resamples: int,
    seed: int,
) -> dict[str, float]:
    """Resample whole tasks and re-form a rate out of what was drawn.

    The statistic is a ratio of sums rather than a mean of per-task rates,
    because tasks hold different numbers of items and a mean of rates would
    quietly give a five-item task the same weight as a hundred-item one.

    A fresh generator every call. Sharing one stream between the bootstraps in
    a single run would make each interval depend on how many were computed
    before it, which is a reproducibility trap that costs nothing to avoid.
    """
    rng = random.Random(seed)
    size = len(task_ids)
    values: list[float] = []
    for _ in range(resamples):
        top = 0.0
        bottom = 0.0
        for _ in range(size):
            drawn = task_ids[rng.randrange(size)]
            top += numerator[drawn]
            bottom += denominator[drawn]
        values.append(100.0 * top / bottom if bottom else 0.0)
    return _interval(values)


def cluster_bootstrap_mean(
    task_ids: list[str],
    value_by_task: dict[str, float],
    *,
    resamples: int,
    seed: int,
) -> dict[str, float]:
    """Resample whole tasks and average a per-task quantity over the draw.

    Used for the differences, where every task contributes one number and the
    corpus figure really is their unweighted mean -- that is how the published
    headline was formed.
    """
    rng = random.Random(seed)
    size = len(task_ids)
    values: list[float] = []
    for _ in range(resamples):
        total = 0.0
        for _ in range(size):
            total += value_by_task[task_ids[rng.randrange(size)]]
        values.append(total / size)
    return _interval(values)


def item_bootstrap_rate(
    flags: list[int], *, resamples: int, seed: int
) -> dict[str, float]:
    """The interval this analysis does *not* use, computed so it can be shown.

    Section 6 rejects treating rubric items as independent observations. The
    number is still produced, because "we chose the wider method" is a claim
    and the ratio between the two widths is the evidence for it.
    """
    rng = random.Random(seed)
    size = len(flags)
    values: list[float] = []
    for _ in range(resamples):
        hits = 0
        for _ in range(size):
            hits += flags[rng.randrange(size)]
        values.append(100.0 * hits / size)
    return _interval(values)


def _binomial_cdf(n: int, k: int, p: float) -> float:
    """P(X <= k) for X ~ Binomial(n, p), summed in log space.

    ``math.comb(4299, 177)`` is a 400-digit integer and multiplying it by a
    float raises OverflowError, so the terms are built from log-gamma and
    exponentiated one at a time.

    A rate of exactly 0 or exactly 1 is answered without the sum. It is a
    legitimate observation -- a grader that never disagreed with itself would
    produce one, and so does feeding this tool the same file three times -- and
    ``math.log(0.0)`` raises rather than returning the negative infinity the
    formula wants.
    """
    if p <= 0.0:
        return 1.0 if k >= 0 else 0.0
    if p >= 1.0:
        return 1.0 if k >= n else 0.0

    total = 0.0
    for x in range(k + 1):
        log_term = (
            math.lgamma(n + 1)
            - math.lgamma(x + 1)
            - math.lgamma(n - x + 1)
            + x * math.log(p)
            + (n - x) * math.log1p(-p)
        )
        total += math.exp(log_term)
    return total


def naive_endpoint_bracket(flags: list[int]) -> dict[str, Any]:
    """Which two whole counts the naive interval's lower endpoint sits between.

    The preregistration recorded 4.094 for this endpoint and re-running it here
    gives 4.117. Eleven implementations were tried before the reason became
    clear, and the reason is not the implementation. Under item resampling the
    statistic is a count out of 4,299 divided by 4,299, so it can only land on
    multiples of 1/4299 = 0.0233pp. The exact binomial distribution puts
    P(X <= 176) just under 2.5% and P(X <= 177) just over it, which means the
    true 2.5th percentile falls strictly between two counts that no draw can
    return. Both figures are honest realisations of the same quantity and they
    differ by one item.

    This is arithmetic rather than a resampling result, so it is exact and a
    test can check it without running a bootstrap.
    """
    n = len(flags)
    hits = sum(flags)
    p = hits / n
    target = PERCENTILE_LOW / 100.0
    if hits in (0, n):
        # Every draw returns the same count, so the quantile lands on a count a
        # draw can actually return and there is nothing to bracket.
        counts = [hits]
    else:
        lower = next(
            k for k in range(n + 1) if _binomial_cdf(n, k, p) >= target
        ) - 1
        counts = [lower, lower + 1]
    return {
        "trials": n,
        "observed": hits,
        "rate_pct": 100.0 * p,
        "quantile": PERCENTILE_LOW,
        "bracketing_counts": [
            {
                "count": k,
                "rate_pct": 100.0 * k / n,
                "cdf": _binomial_cdf(n, k, p),
            }
            for k in counts
        ],
        "step_pct": 100.0 / n,
    }


def _score_outcome(item: dict[str, Any]) -> tuple[Any, bool]:
    """What a reader would call "the same result" for one item.

    The verdict alone is not enough. A ``partial`` that moved from 2.0 to 1.5
    keeps its label and changes the score, and section 3 counts 246 items that
    did exactly that.
    """
    return (item["awarded_score"], bool(item.get("score_excluded")))


def disagreement(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Metric 5, and the transition counts metric 2 asks for.

    Both bases are reported side by side. Reporting only the verdict basis
    hides how much the scoreboard moved; reporting only the score basis hides
    how often a sentence a person would quote came out the other way.
    """
    indexes = [_item_index(run) for run in runs]
    keys = _document_order(runs[0])
    ordered_keys = [
        (task["task_id"], item["rubric_item_id"])
        for task in runs[0]["tasks"]
        for item in task["items"]
    ]

    verdict_flags: list[int] = []
    score_flags: list[int] = []
    verdict_by_task: dict[str, float] = {task_id: 0.0 for task_id in keys}
    score_by_task: dict[str, float] = {task_id: 0.0 for task_id in keys}
    pairs_by_task: dict[str, float] = {task_id: 0.0 for task_id in keys}
    transitions: dict[tuple[str, str], int] = {}
    per_pair_verdict: list[int] = []
    per_pair_score: list[int] = []
    adjacent = 0
    two_step = 0
    same_verdict_moved_score = 0

    for left, right in PAIRS:
        pair_verdict = 0
        pair_score = 0
        for key in ordered_keys:
            a = indexes[left][key]
            b = indexes[right][key]
            task_id = key[0]
            pairs_by_task[task_id] += 1

            differs = a["verdict"] != b["verdict"]
            verdict_flags.append(int(differs))
            pair_verdict += differs
            verdict_by_task[task_id] += differs

            moved = _score_outcome(a) != _score_outcome(b)
            score_flags.append(int(moved))
            pair_score += moved
            score_by_task[task_id] += moved

            if differs:
                cell = (a["verdict"], b["verdict"])
                transitions[cell] = transitions.get(cell, 0) + 1
                left_rank = VERDICT_RANK.get(a["verdict"])
                right_rank = VERDICT_RANK.get(b["verdict"])
                if left_rank is not None and right_rank is not None:
                    if abs(left_rank - right_rank) == 2:
                        two_step += 1
                    else:
                        adjacent += 1
            elif moved:
                same_verdict_moved_score += 1

        per_pair_verdict.append(pair_verdict)
        per_pair_score.append(pair_score)

    total_pairs = len(ordered_keys) * len(PAIRS)
    return {
        "compared_items": len(ordered_keys),
        "compared_item_pairs": total_pairs,
        "verdict": {
            "differing": sum(verdict_flags),
            "rate_pct": 100.0 * sum(verdict_flags) / total_pairs,
            "per_pair": per_pair_verdict,
            "flags": verdict_flags,
            "by_task": verdict_by_task,
        },
        "score_outcome": {
            "differing": sum(score_flags),
            "rate_pct": 100.0 * sum(score_flags) / total_pairs,
            "per_pair": per_pair_score,
            "flags": score_flags,
            "by_task": score_by_task,
        },
        "pairs_by_task": pairs_by_task,
        "transitions": {f"{a}->{b}": n for (a, b), n in sorted(transitions.items())},
        "adjacent_moves": adjacent,
        "two_step_moves": two_step,
        "same_verdict_moved_score": same_verdict_moved_score,
    }


def differences(
    runs: list[dict[str, Any]],
    scores: dict[str, list[float]],
    *,
    resamples: int,
    seed: int,
) -> dict[str, Any]:
    """Metric 1 and the target in section 8.

    The signed mean answers "is one run consistently kinder"; the absolute mean
    answers "how big is the movement". They are different questions and a
    corpus whose movements cancel would answer the first with zero while the
    second stayed large, so both are reported.
    """
    task_ids = list(scores)
    per_pair: list[dict[str, Any]] = []
    for left, right in PAIRS:
        signed = {t: scores[t][left] - scores[t][right] for t in task_ids}
        values = list(signed.values())
        per_pair.append(
            {
                "pair": f"run-{left + 1:03d} vs run-{right + 1:03d}",
                "mean_signed_pp": statistics.fmean(values),
                "mean_absolute_pp": statistics.fmean(abs(v) for v in values),
                "max_absolute_pp": max(abs(v) for v in values),
                "corpus_mean_shift_ci": cluster_bootstrap_mean(
                    task_ids, signed, resamples=resamples, seed=seed
                ),
            }
        )

    # The combined figure uses absolute differences. Adding the three signed
    # pair differences telescopes -- run 1 appears twice with opposite signs --
    # so a signed pooled mean would say more about which pairs were listed than
    # about the grader.
    combined = {
        t: statistics.fmean(
            abs(scores[t][left] - scores[t][right]) for left, right in PAIRS
        )
        for t in task_ids
    }
    return {
        "per_pair": per_pair,
        "combined_absolute": {
            "mean_pp": statistics.fmean(combined.values()),
            "median_pp": statistics.median(combined.values()),
            "max_pp": max(combined.values()),
            "ci": cluster_bootstrap_mean(
                task_ids, combined, resamples=resamples, seed=seed
            ),
        },
        "worst_half_width_pp": max(
            row["corpus_mean_shift_ci"]["half_width"] for row in per_pair
        ),
    }


def corpus_summary(scores: dict[str, list[float]]) -> dict[str, Any]:
    """Metric 4, per run, on whichever baseline was handed in."""
    rows: list[dict[str, Any]] = []
    for ordinal in range(EXPECTED_RUN_COUNT):
        values = [row[ordinal] for row in scores.values()]
        rows.append(
            {
                "run": f"run-{ordinal + 1:03d}",
                "mean_pct": statistics.fmean(values),
                "median_pct": statistics.median(values),
                # Sample variance: three runs are a sample, not the population.
                "variance": statistics.variance(values),
                "stdev": statistics.stdev(values),
            }
        )
    return {
        "per_run": rows,
        "mean_spread_pp": max(r["mean_pct"] for r in rows)
        - min(r["mean_pct"] for r in rows),
    }


def observed_vocabulary(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Metric 3, with section 9's rule that absence is written as absence.

    There is no refusal and no tool-failure field in this schema. Reporting
    "refusal rate 0.0%" would read as a measurement, and it is not one: the
    vocabulary simply never contained the value. The ``read_deliverable``
    census is the nearest available signal and is labelled a proxy, tail and
    all -- the interesting end is the zero-call end, where a verdict was
    reached without opening the deliverable once.
    """
    counts: dict[str, int] = {v: 0 for v in VERDICT_VOCABULARY}
    modality: dict[str, int] = {}
    selection: dict[str, int] = {}
    decided_by: dict[str, int] = {}
    reads: dict[int, int] = {}
    for run in runs:
        for item in _item_index(run).values():
            counts[item["verdict"]] += 1
            key = str(item.get("routing_modality"))
            modality[key] = modality.get(key, 0) + 1
            status = str(item.get("selection_status"))
            selection[status] = selection.get(status, 0) + 1
            decider = str(item.get("decided_by"))
            decided_by[decider] = decided_by.get(decider, 0) + 1
            calls = sum(
                1
                for tool in (item.get("tools_used") or [])
                if tool == "read_deliverable"
            )
            reads[calls] = reads.get(calls, 0) + 1

    graded = sum(counts.values())
    return {
        "verdicts": counts,
        "judge_error_rate_pct": 100.0 * counts["judge_error"] / graded,
        "refusal": "not in this schema and not observed - absent, not measured",
        "tool_failure": "no field exists - the read census below is a proxy",
        "read_deliverable_calls": dict(sorted(reads.items())),
        "routing_modality": dict(sorted(modality.items())),
        "selection_status": dict(sorted(selection.items())),
        "decided_by": dict(sorted(decided_by.items())),
        "error_tasks": [
            {"run": run["_label"], "error_tasks": run["summary"]["error_tasks"]}
            for run in runs
        ],
    }


def usage(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Metric 6. The money column stays unregistered rather than becoming zero.

    ``gpt-5.6-sol`` is not in the price table. A run that could not be priced
    is not a free run, and writing $0.00 would turn a gap in the table into a
    claim about the bill.
    """
    rows: list[dict[str, Any]] = []
    for run in runs:
        cost = run["summary"]["cost"]
        tasks = run["tasks"]
        rows.append(
            {
                "run": run["_label"],
                "graded_at": run["graded_at"],
                "judge_calls": cost["total_judge_calls"],
                "main_judge_calls": cost["total_main_judge_calls"],
                "perception_calls": cost["total_perception_calls"],
                "input_tokens": cost["total_input_tokens"],
                "output_tokens": cost["total_output_tokens"],
                "cached_tokens": cost["total_cached_tokens"],
                "judge_latency_ms": sum(t["judge_total_latency_ms"] for t in tasks),
                "estimated_cost_usd": (
                    "unregistered - "
                    + ", ".join(cost.get("unpriced_models") or ["unknown model"])
                    + " is not in the price table"
                    if cost.get("estimated_cost_usd") is None
                    else cost["estimated_cost_usd"]
                ),
                "azure_routes": sorted(
                    {
                        f"{r['workload']}/{r['endpoint_kind']}"
                        for r in (run.get("azure_ai_routes") or [])
                    }
                ),
            }
        )
    return rows


def required_extra_runs(
    scores: dict[str, list[float]], *, target_pp: float
) -> dict[str, Any]:
    """Section 13. What would have to be bought if the free data falls short.

        half-width ~ 1.96 * sigma_d / sqrt(n * (R - 1))
        R = ceil( (1.96 * sigma_d / (target * sqrt(n)))^2 ) + 1

    sigma_d is taken from the widest pair, so the answer is the number of runs
    that satisfies the target for the pair that needed the most, not for the
    average pair.
    """
    task_ids = list(scores)
    sigmas = [
        statistics.stdev([scores[t][left] - scores[t][right] for t in task_ids])
        for left, right in PAIRS
    ]
    sigma = max(sigmas)
    n = len(task_ids)
    needed = math.ceil((1.96 * sigma / (target_pp * math.sqrt(n))) ** 2) + 1
    return {
        "pair_difference_stdev_pp": sigmas,
        "worst_pair_difference_stdev_pp": sigma,
        "runs_required_for_target": max(needed, EXPECTED_RUN_COUNT),
        "runs_held": EXPECTED_RUN_COUNT,
    }


def analyze(
    runs: list[dict[str, Any]],
    *,
    resamples: int,
    seed: int,
    resample_unit: str,
) -> dict[str, Any]:
    common = common_denominator_keys(runs)
    common_scores = per_task_percent(runs, common)
    published_scores = per_task_percent(runs, None)

    flips = disagreement(runs)
    task_ids = _document_order(runs[0])
    pairs_by_task = flips["pairs_by_task"]

    if resample_unit == "task":
        verdict_ci = cluster_bootstrap_ratio(
            task_ids,
            flips["verdict"]["by_task"],
            pairs_by_task,
            resamples=resamples,
            seed=seed,
        )
        score_ci = cluster_bootstrap_ratio(
            task_ids,
            flips["score_outcome"]["by_task"],
            pairs_by_task,
            resamples=resamples,
            seed=seed,
        )
    else:
        verdict_ci = item_bootstrap_rate(
            flips["verdict"]["flags"], resamples=resamples, seed=seed
        )
        score_ci = item_bootstrap_rate(
            flips["score_outcome"]["flags"], resamples=resamples, seed=seed
        )

    naive_verdict_ci = item_bootstrap_rate(
        flips["verdict"]["flags"], resamples=resamples, seed=seed
    )
    cluster_verdict_ci = cluster_bootstrap_ratio(
        task_ids,
        flips["verdict"]["by_task"],
        pairs_by_task,
        resamples=resamples,
        seed=seed,
    )

    common_diff = differences(
        runs, common_scores, resamples=resamples, seed=seed
    )
    published_diff = differences(
        runs, published_scores, resamples=resamples, seed=seed
    )

    # The gate takes the worse of the two baselines. The common denominator is
    # the primary one because it is the only basis on which a difference means
    # only what the grader did, but the figure a reader would quote is the
    # published one, and a gate that watched the primary basis alone could pass
    # while the numbers people actually cite moved further.
    worst_half_width = max(
        common_diff["worst_half_width_pp"], published_diff["worst_half_width_pp"]
    )
    target_met = worst_half_width <= HALF_WIDTH_TARGET_PP

    # The settings are part of the result. An interval computed at a different
    # seed, a different resample count or a different unit is a real number
    # about a different analysis, and this tool refuses to sign it as this one.
    settings_registered = (
        seed == BOOTSTRAP_SEED
        and resamples == BOOTSTRAP_RESAMPLES
        and resample_unit == "task"
    )

    return {
        "settings": {
            "resamples": resamples,
            "seed": seed,
            "resample_unit": resample_unit,
            "percentile": [PERCENTILE_LOW, PERCENTILE_HIGH],
            "target_half_width_pp": HALF_WIDTH_TARGET_PP,
            "as_registered": settings_registered,
        },
        "runs": [
            {
                "label": run["_label"],
                "path": run["_source_path"],
                "sha256": run["_source_digest"],
                "graded_at": run["graded_at"],
                "run_status": run["run_status"],
            }
            for run in runs
        ],
        "denominator": denominator_movement(runs),
        "difference_common_denominator": common_diff,
        "difference_as_published": published_diff,
        "corpus_common_denominator": corpus_summary(common_scores),
        "corpus_as_published": corpus_summary(published_scores),
        "flips": {
            "compared_items": flips["compared_items"],
            "compared_item_pairs": flips["compared_item_pairs"],
            "verdict": {
                "differing": flips["verdict"]["differing"],
                "rate_pct": flips["verdict"]["rate_pct"],
                "per_pair": flips["verdict"]["per_pair"],
                "ci": verdict_ci,
            },
            "score_outcome": {
                "differing": flips["score_outcome"]["differing"],
                "rate_pct": flips["score_outcome"]["rate_pct"],
                "per_pair": flips["score_outcome"]["per_pair"],
                "ci": score_ci,
            },
            "transitions": flips["transitions"],
            "adjacent_moves": flips["adjacent_moves"],
            "two_step_moves": flips["two_step_moves"],
            "same_verdict_moved_score": flips["same_verdict_moved_score"],
        },
        "design_effect": {
            "cluster_ci": cluster_verdict_ci,
            "naive_item_ci": naive_verdict_ci,
            "width_ratio": (
                cluster_verdict_ci["width"] / naive_verdict_ci["width"]
                if naive_verdict_ci["width"]
                else float("inf")
            ),
            "naive_endpoint_bracket": naive_endpoint_bracket(
                flips["verdict"]["flags"]
            ),
        },
        "vocabulary": observed_vocabulary(runs),
        "usage": usage(runs),
        "extra_runs": required_extra_runs(
            common_scores, target_pp=HALF_WIDTH_TARGET_PP
        ),
        "worst_half_width_pp": worst_half_width,
        "target_half_width_met": target_met,
        "verdict_ok": bool(target_met and settings_registered),
    }


def _mark(met: bool) -> str:
    return "MET" if met else "MISSED"


def _render(report: dict[str, Any]) -> str:
    settings = report["settings"]
    lines: list[str] = []
    lines.append("repeat variation - the same answers, graded three times")
    lines.append("=" * 62)
    lines.append("")
    for row in report["runs"]:
        lines.append(
            f"  {row['label']}  {row['graded_at']}  {row['run_status']}  "
            f"sha256 {row['sha256'][:16]}"
        )
    lines.append("")
    lines.append(
        f"  resamples {settings['resamples']}   seed {settings['seed']}   "
        f"unit {settings['resample_unit']}   "
        f"percentile {settings['percentile'][0]}/{settings['percentile'][1]}"
    )
    if not settings["as_registered"]:
        lines.append(
            "  WARNING these are not the registered settings, so what follows "
            "is a different analysis"
        )
    lines.append("")

    denominator = report["denominator"]
    lines.append("moving denominator (section 5)")
    lines.append(
        f"  shared items {denominator['shared_items']}   "
        f"common denominator {denominator['items_in_common_denominator']}   "
        f"dropped {denominator['items_dropped_from_common_denominator']}"
    )
    lines.append(
        f"  judge_error {denominator['judge_error_events']}   "
        f"score_excluded {denominator['score_excluded_events']}   "
        f"disagreeing {denominator['excluded_and_error_disagree']}"
    )
    for row in denominator["tasks_whose_total_max_moved"]:
        maxima = " / ".join(f"{m:g}" for m in row["total_max"])
        lines.append(f"  total_max moved  {row['task_id'][:8]}  {maxima}")
    lines.append("")

    for title, key in (
        ("common denominator (primary)", "corpus_common_denominator"),
        ("as published (secondary)", "corpus_as_published"),
    ):
        block = report[key]
        lines.append(f"corpus mean, {title}")
        for row in block["per_run"]:
            lines.append(
                f"  {row['run']}  mean {row['mean_pct']:.4f}%  "
                f"median {row['median_pct']:.4f}%  stdev {row['stdev']:.4f}"
            )
        lines.append(f"  spread across runs {block['mean_spread_pp']:.4f}pp")
        lines.append("")

    diff = report["difference_common_denominator"]
    lines.append("per-task movement, common denominator (metric 1)")
    for row in diff["per_pair"]:
        ci = row["corpus_mean_shift_ci"]
        lines.append(
            f"  {row['pair']}  signed {row['mean_signed_pp']:+.4f}pp  "
            f"absolute {row['mean_absolute_pp']:.4f}pp  "
            f"max {row['max_absolute_pp']:.4f}pp"
        )
        lines.append(
            f"            corpus mean shift 95% CI "
            f"[{ci['low']:+.4f}, {ci['high']:+.4f}]  "
            f"half-width {ci['half_width']:.4f}pp"
        )
    combined = diff["combined_absolute"]
    lines.append(
        f"  all pairs  absolute mean {combined['mean_pp']:.4f}pp  "
        f"median {combined['median_pp']:.4f}pp  max {combined['max_pp']:.4f}pp"
    )
    lines.append("")

    published = report["difference_as_published"]
    lines.append("per-task movement, as published (metric 1, secondary)")
    for row in published["per_pair"]:
        ci = row["corpus_mean_shift_ci"]
        lines.append(
            f"  {row['pair']}  signed {row['mean_signed_pp']:+.4f}pp  "
            f"absolute {row['mean_absolute_pp']:.4f}pp  "
            f"max {row['max_absolute_pp']:.4f}pp  "
            f"half-width {ci['half_width']:.4f}pp"
        )
    lines.append("")

    flips = report["flips"]
    lines.append(
        f"result changed on a second grading (metric 5), "
        f"{flips['compared_item_pairs']} item pairs"
    )
    for label, block in (
        ("verdict", flips["verdict"]),
        ("score outcome", flips["score_outcome"]),
    ):
        ci = block["ci"]
        per_pair = " / ".join(str(n) for n in block["per_pair"])
        lines.append(
            f"  {label:<13} {block['differing']} pairs  "
            f"{block['rate_pct']:.4f}%  ({per_pair})"
        )
        lines.append(
            f"                95% CI [{ci['low']:.4f}, {ci['high']:.4f}]  "
            f"width {ci['width']:.4f}pp"
        )
    lines.append(
        f"  adjacent moves {flips['adjacent_moves']}   "
        f"two-step pass/fail moves {flips['two_step_moves']}   "
        f"same verdict, moved score {flips['same_verdict_moved_score']}"
    )
    for cell, count in flips["transitions"].items():
        lines.append(f"  transition  {cell:<28} {count}")
    lines.append("")

    design = report["design_effect"]
    lines.append("why the unit is the task and not the item (section 6)")
    lines.append(
        f"  task cluster   [{design['cluster_ci']['low']:.4f}, "
        f"{design['cluster_ci']['high']:.4f}]  "
        f"width {design['cluster_ci']['width']:.4f}pp   OFFICIAL"
    )
    lines.append(
        f"  naive item     [{design['naive_item_ci']['low']:.4f}, "
        f"{design['naive_item_ci']['high']:.4f}]  "
        f"width {design['naive_item_ci']['width']:.4f}pp   not used"
    )
    lines.append(
        f"  the naive interval is {design['width_ratio']:.4f}x narrower than "
        "the one this analysis reports"
    )
    bracket = design["naive_endpoint_bracket"]
    counts = bracket["bracketing_counts"]
    if len(counts) == 1:
        lines.append(
            f"  every item pair agreed or every one differed, so the "
            f"{bracket['quantile']}th percentile lands exactly on"
        )
    else:
        lines.append(
            f"  the naive lower endpoint can only land on multiples of "
            f"{bracket['step_pct']:.4f}pp, and the exact binomial puts the "
            f"{bracket['quantile']}th percentile between"
        )
    for entry in counts:
        lines.append(
            f"    {entry['count']} of {bracket['trials']} "
            f"= {entry['rate_pct']:.4f}%  P(X <= k) = {entry['cdf']:.5f}"
        )
    lines.append("")

    vocabulary = report["vocabulary"]
    lines.append("what was actually observed (metric 3, section 9)")
    verdicts = "   ".join(
        f"{name} {count}" for name, count in vocabulary["verdicts"].items()
    )
    lines.append(f"  {verdicts}")
    lines.append(
        f"  judge_error rate {vocabulary['judge_error_rate_pct']:.4f}%"
    )
    lines.append(f"  refusal        {vocabulary['refusal']}")
    lines.append(f"  tool failure   {vocabulary['tool_failure']}")
    census = "   ".join(
        f"{calls}x {count}"
        for calls, count in vocabulary["read_deliverable_calls"].items()
    )
    lines.append(f"  read_deliverable per item  {census}")
    modality = "   ".join(
        f"{name} {count}" for name, count in vocabulary["routing_modality"].items()
    )
    lines.append(f"  routing modality  {modality}")
    lines.append("")

    lines.append("cost and latency per run (metric 6)")
    for row in report["usage"]:
        lines.append(
            f"  {row['run']}  judge calls {row['judge_calls']}  "
            f"in {row['input_tokens']}  out {row['output_tokens']}  "
            f"cached {row['cached_tokens']}"
        )
        lines.append(
            f"            latency {row['judge_latency_ms'] / 1000:.1f}s   "
            f"routes {', '.join(row['azure_routes'])}"
        )
        lines.append(f"            cost {row['estimated_cost_usd']}")
    lines.append("")

    extra = report["extra_runs"]
    lines.append("the target (section 8)")
    lines.append(
        f"  worst half-width {report['worst_half_width_pp']:.4f}pp   "
        f"target <= {HALF_WIDTH_TARGET_PP:.1f}pp   "
        f"{_mark(report['target_half_width_met'])}"
    )
    lines.append(
        f"  pair difference stdev worst case "
        f"{extra['worst_pair_difference_stdev_pp']:.4f}pp   "
        f"runs required {extra['runs_required_for_target']}   "
        f"held {extra['runs_held']}"
    )
    lines.append("")
    lines.append(f"VERDICT  {_mark(report['verdict_ok'])}")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "grade_files",
        type=Path,
        nargs="+",
        help="the three repeat payloads of the pinned thirty-task cohort",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit the whole analysis as JSON instead of a readable report",
    )
    parser.add_argument(
        "--bootstrap-resamples",
        type=int,
        default=BOOTSTRAP_RESAMPLES,
        help="how many times to resample. Registered value: 10000",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=BOOTSTRAP_SEED,
        help=(
            "the bootstrap seed. Registered value: 20260901. Any other value "
            "produces a real interval for a different analysis, and this tool "
            "marks the run accordingly"
        ),
    )
    parser.add_argument(
        "--resample-unit",
        choices=("task", "item"),
        default="task",
        help=(
            "what a draw picks up. Registered value: task. 'item' exists so a "
            "test can show what pretending items are independent would report"
        ),
    )
    args = parser.parse_args(argv)

    runs = load_runs(args.grade_files)

    problems = fingerprint_problems(runs) + shape_problems(runs)
    if problems:
        raise RepeatsAreNotComparable(
            "these payloads cannot answer the question this analysis asks:\n"
            "  - " + "\n  - ".join(problems)
        )

    report = analyze(
        runs,
        resamples=args.bootstrap_resamples,
        seed=args.seed,
        resample_unit=args.resample_unit,
    )

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(_render(report))

    return 0 if report["verdict_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
