#!/usr/bin/env python3
"""How far the grader moves on *listening* criteria when it grades them again.

Why this exists
---------------
The repeat-variation card asks for a confidence interval on how often the
grader changes its mind about an audio criterion between two gradings of the
same answers. The figure quoted for that was 38%, and it was not usable: it was
a difference between two smokes at different grader fingerprints, so it
measured the code change at least as much as the grader.

``gold_audio_repeat_v2_sol_max`` was pinned to fix that -- every gold task the
grader actually listens to, three of them, the whole population rather than a
sample -- and three runs of it were bought at one fingerprint. This tool reads
those three and reports what they support.

Everything here is a read. No grade payload is rewritten and no model is
called, so running this costs nothing.

Why a second tool instead of an option on the first
---------------------------------------------------
``analyze_repeat_variation.py`` answers the same question for a thirty-task
cohort, and ``tests/test_repeat_variation_report_quotes_its_run.py`` re-runs
the command that file's result document records and compares the output byte
for byte. Adding a mode to it would have to keep that block identical while
changing the code that produces it, which is a promise rather than a check.

So this is a sibling. It imports that module's *arithmetic* -- the percentile,
the cluster bootstrap, the item index -- because two implementations of one
formula is how two answers quietly stop agreeing. It imports none of that
module's *constants*, because those are a different cohort's registration and
sharing them would silently move this cohort's numbers whenever that one was
re-registered. The one thing checked rather than shared is that the two
registrations still agree where they must: see ``shared_arithmetic_problems``.

The mirror image of the other tool's refusal
--------------------------------------------
``analyze_repeat_variation.py`` sets ``FORBIDDEN_MODALITY = "audio"`` and
refuses any run containing an audio item, because its cohort was graded before
audio routing existed and folding audio in would report a flip rate for a
modality it never exercised. This tool sets ``REQUIRED_MODALITY = "audio"`` and
refuses any run *without* one. The two are checked against each other, so the
two cohorts cannot be swapped by mistake in either direction: each tool's
input is exactly the other's refusal.

The interval that was asked for does not exist, and that is the finding
----------------------------------------------------------------------
The card asks for a task-unit interval. A task-unit interval on this cohort is
degenerate, and not because three runs is too few.

Resampling three tasks with replacement gives 3^3 = 27 equally likely draws. A
ratio of sums over a mixture of tasks is a weighted average of the per-task
rates, so every attainable value lies between the lowest and the highest
per-task rate -- and the three draws that pick one task three times attain
exactly those two endpoints. Each of those draws has probability 1/27 = 3.70%,
which is larger than the 2.5% the percentile method cuts off. So the 2.5th
percentile *is* the minimum and the 97.5th *is* the maximum, and the "95%
interval" is the range of the three per-task rates, arrived at by construction
rather than by measurement.

Buying more repeats does not fix that. More repeats sharpen each task's own
rate, so the endpoints converge -- to the true lowest and true highest of the
three task rates, which is a fixed non-zero width, not to a point. The interval
is computed and reported anyway, with ``is_informative`` false and the exact
probabilities that make it false, because "we could not bound it" is a claim
and the enumeration is the evidence for it. What would fix it is a fourth audio
task, and this corpus has exactly three: 31 of 8,816 items route audio and they
belong to those three. There is no fourth to buy.

What the runs do support
------------------------
The comparison that survives is inside each run rather than across the
resampled corpus: the same grader, on the same task, in the same run, flipping
far more often on the criteria it listened to than on the criteria it read.
That is a stratified permutation test with the task as the stratum, and it does
not resample tasks at all, so the degeneracy above does not touch it.

Honesty about the threshold below
---------------------------------
The thirty-task tool implements a document written before its runs were bought.
This one was written after these three were graded, so its numbers were known
when its threshold was chosen. Calling that a preregistration would be false.
The threshold is stated anyway and wired to the exit status, because a stated
threshold that a later re-run can fail is worth more than an unstated one, and
because the alternative is choosing it silently.

Usage
-----
    python batch-runner/scripts/analyze_audio_repeat_variation.py RUN1.json RUN2.json RUN3.json
    python batch-runner/scripts/analyze_audio_repeat_variation.py RUN*.json --json

Exit status is 0 when the reported contrast holds at the stated threshold and
1 when it does not, so a difference that could be chance cannot be reported as
if it had been established.
"""

from __future__ import annotations

import argparse
import collections
import itertools
import json
import random
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import analyze_repeat_variation as rv  # noqa: E402

# Arithmetic borrowed rather than rewritten. Two implementations of one formula
# is how two published answers quietly stop agreeing, and every name here is a
# pure function of its arguments -- none of them reads the other cohort's
# constants except the two bootstraps, which read its percentiles, which is
# exactly what ``shared_arithmetic_problems`` below refuses to leave unchecked.
_dig = rv._dig
_item_index = rv._item_index
_score_outcome = rv._score_outcome
cluster_bootstrap_ratio = rv.cluster_bootstrap_ratio
item_bootstrap_rate = rv.item_bootstrap_rate
load_runs = rv.load_runs
percentile = rv.percentile


# The resampling settings. Same values as the thirty-task cohort's, declared
# separately: they have to agree today, and they have to be able to disagree
# tomorrow without one cohort's re-registration moving the other's numbers.
BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 20260902
PERCENTILE_LOW = 2.5
PERCENTILE_HIGH = 97.5

# The stratified permutation test. Draws are cheap here -- 94 labels, three
# strata -- so the count is set by how fine a p-value is worth quoting rather
# than by runtime: 100,000 draws resolve to the fourth decimal.
PERMUTATION_DRAWS = 100_000
PERMUTATION_SEED = 20260902

# The threshold the exit status is wired to. One-sided, because the question is
# "does listening flip more than reading", and a contrast in the other
# direction would not support the card's claim either way. See the docstring
# for why this is not called a preregistration.
ALPHA = 0.01

# Three runs, three tasks, all three pairs. Picking one pair would be picking
# the answer.
EXPECTED_RUN_COUNT = 3
EXPECTED_TASK_COUNT = 3
PAIRS: tuple[tuple[int, int], ...] = ((0, 1), (0, 2), (1, 2))

# The mirror of the other tool's FORBIDDEN_MODALITY. A run with no audio item
# cannot answer this question, and the other tool refuses every run that can.
REQUIRED_MODALITY = "audio"

# What audio is measured against. Not "everything else": formatting and visual
# criteria reach the file by other routes with their own failure modes, and
# lumping them in would compare listening to an average of three unlike things.
# They are still censused, just not contrasted.
CONTRAST_MODALITY = "text"

# The whole audio population of this corpus, as the merged 185-task run
# measured it and ``tests/test_the_audio_repeat_cohort_is_every_audio_task.py``
# derives it. Pinned so a cohort that quietly graded a different three is
# caught here rather than absorbed into the rate.
EXPECTED_AUDIO_ITEMS = 31
EXPECTED_AUDIO_ITEMS_PER_TASK = {
    "38889c3b-e3d4-49c8-816a-3cc8e5313aba": 10,
    "e222075d-5d62-4757-ae3c-e34b0846583b": 7,
    "75401f7c-396d-406d-b08e-938874ad1045": 14,
}

# A verdict outside this vocabulary stops the run rather than being given a
# handling rule invented on the spot.
VERDICT_VOCABULARY: tuple[str, ...] = ("pass", "partial", "fail", "judge_error")

# The identity of the three runs, field by field. Checked twice over: every run
# must agree with every other, and every run must also match the literal below.
# Agreement alone would accept three runs of some other cohort that happened to
# agree with each other, and these numbers are about one cohort.
PINNED_FINGERPRINTS: tuple[tuple[str, tuple[str, ...], Any], ...] = (
    (
        "task list digest",
        ("expected_ordered_task_ids_sha256",),
        "b16d9b188a763fa9382d9b18df796b2f08cf284b47619195a2feba963149063c",
    ),
    ("task count", ("expected_task_count",), 3),
    (
        "grader source digest",
        ("grader_source_hash",),
        "29c3cfe7e94e488177b8bce5a2b4f1d952f172175db7ace2d3c929b34d1f3b49",
    ),
    ("grading config", ("judge", "config_name"), "gold_audio_repeat_v2_sol_max"),
    ("grading config hash", ("judge", "config_hash"), "ed9ac99c7332a184"),
    ("judge model", ("judge", "model"), "gpt-5.6-sol"),
    ("judge deployment", ("judge", "deployment"), "gpt-5.6-sol"),
    ("api version", ("judge", "api_version"), "2025-04-01-preview"),
    ("reasoning effort", ("judge", "reasoning_effort"), "max"),
    ("temperature", ("judge", "temperature"), 0),
    ("seed", ("judge", "seed"), 42),
    ("judge prompt version", ("prompt", "version"), "v2.2"),
    # The listening settings themselves. The thirty-task cohort has no
    # equivalent of these because it never listened; here they decide what the
    # grader was given to hear, so a repeat at a different trim or a different
    # audio model is not a repeat of this measurement.
    ("audio model", ("judge", "perception", "audio", "model"), "gpt-audio-1.5"),
    (
        "audio deployment",
        ("judge", "perception", "audio", "deployment"),
        "gpt-audio-1.5",
    ),
    ("audio clip seconds", ("judge", "perception", "audio", "trim_seconds"), 30),
    (
        "audio call cap per task",
        ("judge", "perception", "audio", "call_cap_per_task"),
        32,
    ),
    (
        "rubric revision",
        ("rubric", "revision"),
        "11e7900cdcac61bc4daf59e65feb238acda98fbf",
    ),
    (
        "gold revision",
        ("source_inference_revision",),
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
    ("payload schema", ("schema_version",), "1.4"),
    # A pinned proper subset is a diagnostic run by construction, and a payload
    # that called itself final here would be one that had escaped the fork and
    # could overwrite the published corpus.
    ("run status", ("run_status",), "diagnostic"),
)


class RepeatsAreNotComparable(SystemExit):
    """Raised when the inputs cannot answer the question that was asked.

    Every invalidation is this rather than a warning. A warning printed above a
    number is read as a caveat on the number; the point of these checks is that
    there is no number to caveat.
    """


# ── what the two cohorts must still agree about ──────────────────────────


def shared_arithmetic_problems() -> list[str]:
    """The coupling to the other module, made explicit and checkable.

    ``cluster_bootstrap_ratio`` and ``item_bootstrap_rate`` cut their intervals
    at *that* module's percentiles. If it were ever re-registered at different
    ones, this cohort's endpoints would move with it and nothing here would say
    so. Rather than copy the two functions to avoid the coupling, the coupling
    is asserted -- and the modality mirror is asserted with it, so the two
    tools cannot be pointed at each other's inputs.
    """
    problems: list[str] = []

    for name, mine in (
        ("PERCENTILE_LOW", PERCENTILE_LOW),
        ("PERCENTILE_HIGH", PERCENTILE_HIGH),
    ):
        theirs = getattr(rv, name)
        if theirs != mine:
            problems.append(
                f"analyze_repeat_variation.{name} is {theirs} and this "
                f"analysis is registered at {mine}. The bootstraps below are "
                "that module's and would cut at its value, so these two "
                "registrations have to be reconciled before either is quoted"
            )

    if rv.PAIRS != PAIRS:
        problems.append(
            f"analyze_repeat_variation.PAIRS is {rv.PAIRS} and this analysis "
            f"uses {PAIRS}; the two cohorts are no longer comparing runs the "
            "same way"
        )

    if rv.FORBIDDEN_MODALITY != REQUIRED_MODALITY:
        problems.append(
            "the modality this analysis requires "
            f"({REQUIRED_MODALITY!r}) is no longer the one "
            "analyze_repeat_variation refuses "
            f"({rv.FORBIDDEN_MODALITY!r}). Those two facts are what keep each "
            "cohort out of the other's intervals"
        )

    return problems


# ── is this the cohort, and is it three different gradings of it ─────────


def fingerprint_problems(runs: list[dict[str, Any]]) -> list[str]:
    """Identity, then non-identity: same cohort, different gradings."""
    problems: list[str] = []

    if len(runs) != EXPECTED_RUN_COUNT:
        problems.append(
            f"this analysis is registered for {EXPECTED_RUN_COUNT} runs and "
            f"was given {len(runs)}"
        )

    for label, path, expected in PINNED_FINGERPRINTS:
        observed = [_dig(run, path) for run in runs]
        field = ".".join(path)
        if len({json.dumps(value, sort_keys=True) for value in observed}) > 1:
            rendered = " | ".join(
                f"{run['_label']}={json.dumps(value, ensure_ascii=False)}"
                for run, value in zip(runs, observed)
            )
            problems.append(
                f"{label} ({field}) differs between runs: {rendered}. A flip "
                "rate measured across runs that differed here would measure "
                "that difference, not the grader"
            )
            continue
        if observed[0] != expected:
            problems.append(
                f"{label} ({field}) is "
                f"{json.dumps(observed[0], ensure_ascii=False)} and this "
                "analysis pinned "
                f"{json.dumps(expected, ensure_ascii=False)}. These are not "
                "the runs it was written for"
            )

    # Being handed one file twice is the failure that would pass every gate
    # having compared nothing: every difference comes out at zero, and zero
    # reads as perfect stability.
    for field in ("_source_digest", "graded_at"):
        seen: dict[Any, str] = {}
        for run in runs:
            value = run.get(field)
            if value in seen:
                problems.append(
                    f"{run['_label']} and {seen[value]} have the same "
                    f"{field.lstrip('_')}, so at least two of these inputs "
                    "are the same run. Comparing a run with itself reports "
                    "zero movement and proves nothing"
                )
            else:
                seen[value] = run["_label"]

    for run in runs:
        tasks = run.get("tasks") or []
        if len(tasks) != EXPECTED_TASK_COUNT:
            problems.append(
                f"{run['_label']} graded {len(tasks)} tasks and this analysis "
                f"is registered for {EXPECTED_TASK_COUNT}"
            )

    return problems


def _modality_counts(run: dict[str, Any]) -> collections.Counter[str]:
    return collections.Counter(
        str(item.get("routing_modality"))
        for task in run["tasks"]
        for item in task["items"]
    )


def shape_problems(runs: list[dict[str, Any]]) -> list[str]:
    """What the body of the payloads has to look like for any of this to mean
    what it says.

    Kept apart from the fingerprint checks because these read every item, and a
    caller asking only whether two files are the same run should not have to.
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
                    f"the others do not ({sample}). Pairing needs the same "
                    "items on both sides"
                )
        return problems

    for run, index in zip(runs, indexes):
        # The mirror of the other tool's refusal. A cohort with no audio in it
        # cannot report an audio flip rate, and reporting one anyway is the
        # exact mistake that made the 38% figure unusable.
        counts = _modality_counts(run)
        if not counts.get(REQUIRED_MODALITY):
            problems.append(
                f"{run['_label']} routed no {REQUIRED_MODALITY} item at all. "
                "This analysis is about criteria the grader listened to; a run "
                "that listened to nothing has no flip rate to report"
            )
        elif counts[REQUIRED_MODALITY] != EXPECTED_AUDIO_ITEMS:
            problems.append(
                f"{run['_label']} routed {counts[REQUIRED_MODALITY]} "
                f"{REQUIRED_MODALITY} items and this cohort is pinned at "
                f"{EXPECTED_AUDIO_ITEMS}. The population moved, so the rate "
                "below would be a rate for a different population"
            )

        per_task = {
            task["task_id"]: sum(
                1
                for item in task["items"]
                if item.get("routing_modality") == REQUIRED_MODALITY
            )
            for task in run["tasks"]
        }
        if per_task != EXPECTED_AUDIO_ITEMS_PER_TASK:
            problems.append(
                f"{run['_label']} listened to {json.dumps(per_task, sort_keys=True)} "
                f"and the pin says {json.dumps(EXPECTED_AUDIO_ITEMS_PER_TASK, sort_keys=True)}"
            )

        unknown = sorted(
            {
                str(item["verdict"])
                for item in index.values()
                if item.get("verdict") not in VERDICT_VOCABULARY
            }
        )
        if unknown:
            problems.append(
                f"{run['_label']} uses verdicts outside the vocabulary this "
                f"analysis counts: {', '.join(unknown)}"
            )

    # An item that was read in one run and listened to in another is not one
    # observation of one thing. The contrast below would be comparing the
    # router's decisions rather than the grader's.
    moved = sorted(
        f"{task}/{item}"
        for task, item in indexes[0]
        if len({index[(task, item)].get("routing_modality") for index in indexes}) > 1
    )
    if moved:
        problems.append(
            f"{len(moved)} item(s) changed routing modality between runs "
            f"({', '.join(moved[:3])}). A flip rate by modality needs the "
            "modality to be a property of the item, not of the run"
        )

    return problems


# ── the census ───────────────────────────────────────────────────────────


def _ordered_keys(run: dict[str, Any]) -> list[tuple[str, str]]:
    """Item keys in payload order.

    Not sorted. The resampling and the permutation both draw from lists built
    in this order, so it is part of the recipe that reproduces the numbers.
    """
    return [
        (task["task_id"], item["rubric_item_id"])
        for task in run["tasks"]
        for item in task["items"]
    ]


def census(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Verdict flips and score moves, per modality, over all three pairs.

    Both bases are reported. The verdict basis is what a person quotes -- "the
    grader said pass, then it said fail" -- and the score basis is what the
    scoreboard did, which can move while the label holds still.
    """
    indexes = [_item_index(run) for run in runs]
    keys = _ordered_keys(runs[0])
    modality = {key: str(indexes[0][key].get("routing_modality")) for key in keys}
    task_of = {key: key[0] for key in keys}

    verdict_flags: dict[tuple[str, str], list[int]] = {key: [] for key in keys}
    score_flags: dict[tuple[str, str], list[int]] = {key: [] for key in keys}
    transitions: dict[tuple[str, str, str], int] = {}

    for left, right in PAIRS:
        for key in keys:
            a = indexes[left][key]
            b = indexes[right][key]
            differs = a["verdict"] != b["verdict"]
            verdict_flags[key].append(int(differs))
            score_flags[key].append(int(_score_outcome(a) != _score_outcome(b)))
            if differs:
                cell = (modality[key], str(a["verdict"]), str(b["verdict"]))
                transitions[cell] = transitions.get(cell, 0) + 1

    by_modality: dict[str, dict[str, Any]] = {}
    for name in sorted(set(modality.values())):
        members = [key for key in keys if modality[key] == name]
        flips = sum(sum(verdict_flags[key]) for key in members)
        moves = sum(sum(score_flags[key]) for key in members)
        pairs = len(members) * len(PAIRS)
        by_modality[name] = {
            "items": len(members),
            "pairs": pairs,
            "verdict_flips": flips,
            "verdict_flip_rate_pct": 100.0 * flips / pairs if pairs else 0.0,
            "score_moves": moves,
            "score_move_rate_pct": 100.0 * moves / pairs if pairs else 0.0,
            "items_that_ever_flipped": sum(
                1 for key in members if any(verdict_flags[key])
            ),
        }

    total_flips = sum(sum(flags) for flags in verdict_flags.values())
    total_moves = sum(sum(flags) for flags in score_flags.values())
    total_pairs = len(keys) * len(PAIRS)

    return {
        "items": len(keys),
        "pairs": total_pairs,
        "verdict_flips": total_flips,
        "verdict_flip_rate_pct": 100.0 * total_flips / total_pairs,
        "score_moves": total_moves,
        "score_move_rate_pct": 100.0 * total_moves / total_pairs,
        "by_modality": by_modality,
        "transitions": {
            f"{mod}:{a}->{b}": n for (mod, a, b), n in sorted(transitions.items())
        },
        "_keys": keys,
        "_modality": modality,
        "_task_of": task_of,
        "_verdict_flags": verdict_flags,
    }


def denominator_stability(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Whether the set of items that count moved between the three gradings.

    The thirty-task analysis had to correct for a denominator that moved: an
    item excluded in one run and scored in another changes what the percentage
    is a percentage of. If that happened here it would contaminate the rates
    below, so it is measured rather than assumed away.
    """
    indexes = [_item_index(run) for run in runs]
    excluded = [
        {key for key, item in index.items() if item.get("score_excluded")}
        for index in indexes
    ]
    stable = len({frozenset(group) for group in excluded}) == 1
    always = set.intersection(*excluded) if excluded else set()
    ever = set.union(*excluded) if excluded else set()

    return {
        "excluded_per_run": [len(group) for group in excluded],
        "identical_across_runs": stable,
        "excluded_always": sorted(f"{task}/{item}" for task, item in always),
        "modalities_ever_excluded": dict(
            sorted(
                collections.Counter(
                    str(indexes[0][key].get("routing_modality")) for key in ever
                ).items()
            )
        ),
        f"{REQUIRED_MODALITY}_items_ever_excluded": sum(
            1
            for key in ever
            if indexes[0][key].get("routing_modality") == REQUIRED_MODALITY
        ),
    }


# ── the interval that was asked for, and why it is not one ───────────────


def attainable_distribution(
    task_ids: list[str],
    numerator: dict[str, int],
    denominator: dict[str, int],
) -> list[tuple[Fraction, int]]:
    """Every value a cluster resample can return, with how many draws return it.

    Exact rather than sampled. With k tasks there are k**k ordered draws, all
    equally likely, so at k=3 the whole bootstrap distribution is 27 outcomes
    and can be written down. Fractions rather than floats so that two draws
    landing on the same rate are recognised as the same value instead of being
    separated in the sixteenth decimal.
    """
    counts: dict[Fraction, int] = {}
    size = len(task_ids)
    for draw in itertools.product(task_ids, repeat=size):
        top = sum(numerator[task_id] for task_id in draw)
        bottom = sum(denominator[task_id] for task_id in draw)
        value = Fraction(top, bottom) if bottom else Fraction(0)
        counts[value] = counts.get(value, 0) + 1
    return sorted(counts.items())


def exact_quantile(
    distribution: list[tuple[Fraction, int]], total: int, q: float
) -> Fraction:
    """The smallest value whose cumulative probability reaches ``q``.

    This is the quantile the percentile bootstrap converges to as the resample
    count grows, so comparing it against the endpoints of an actual bootstrap
    is a check on that bootstrap rather than a second opinion about the data.
    """
    target = Fraction(q) / 100
    seen = 0
    for value, count in distribution:
        seen += count
        if Fraction(seen, total) >= target:
            return value
    return distribution[-1][0]


def task_unit_interval(
    task_ids: list[str],
    numerator: dict[str, int],
    denominator: dict[str, int],
    *,
    resamples: int,
    seed: int,
) -> dict[str, Any]:
    """The requested interval, plus the enumeration that says what it is worth.

    Both are reported. The bootstrap is what the card asked for and what a
    reader will look for; the enumeration is why the bootstrap's endpoints
    could not have come out anywhere else.
    """
    size = len(task_ids)
    total_draws = size**size
    distribution = attainable_distribution(task_ids, numerator, denominator)

    lowest = distribution[0][0]
    highest = distribution[-1][0]
    p_at_min = Fraction(distribution[0][1], total_draws)
    p_at_max = Fraction(distribution[-1][1], total_draws)

    exact_low = exact_quantile(distribution, total_draws, PERCENTILE_LOW)
    exact_high = exact_quantile(distribution, total_draws, PERCENTILE_HIGH)

    bootstrap = cluster_bootstrap_ratio(
        task_ids,
        {task_id: float(numerator[task_id]) for task_id in task_ids},
        {task_id: float(denominator[task_id]) for task_id in task_ids},
        resamples=resamples,
        seed=seed,
    )

    per_task = {
        task_id: (
            100.0 * numerator[task_id] / denominator[task_id]
            if denominator[task_id]
            else 0.0
        )
        for task_id in task_ids
    }

    # The endpoints are pinned to the extremes exactly when a single-task draw
    # is likelier than the tail being cut off. That is a property of how many
    # clusters there are, not of what they contain.
    informative = exact_low > lowest and exact_high < highest

    smallest_useful = size
    while Fraction(1, smallest_useful**smallest_useful) >= Fraction(
        PERCENTILE_LOW
    ) / 100:
        smallest_useful += 1

    return {
        "unit": "task",
        "clusters": size,
        "ordered_draws": total_draws,
        "per_task_rate_pct": {
            task_id: round(rate, 4) for task_id, rate in per_task.items()
        },
        "attainable_values_pct": [
            round(100.0 * float(value), 4) for value, _ in distribution
        ],
        "distinct_attainable_values": len(distribution),
        "bootstrap": {
            "resamples": resamples,
            "seed": seed,
            "low": bootstrap["low"],
            "high": bootstrap["high"],
            "width": bootstrap["width"],
            "half_width": bootstrap["half_width"],
        },
        "exact_quantiles_pct": {
            "low": round(100.0 * float(exact_low), 4),
            "high": round(100.0 * float(exact_high), 4),
        },
        "extremes_pct": {
            "min": round(100.0 * float(lowest), 4),
            "max": round(100.0 * float(highest), 4),
        },
        "probability_of_an_extreme_draw": {
            "at_min": round(float(p_at_min), 6),
            "at_max": round(float(p_at_max), 6),
            "tail_being_cut": PERCENTILE_LOW / 100.0,
        },
        "is_informative": informative,
        "width_floor_pp": round(max(per_task.values()) - min(per_task.values()), 4),
        "clusters_needed_for_a_cut_tail": smallest_useful,
        "why": (
            "a ratio of sums over resampled tasks is a weighted average of the "
            "per-task rates, so every draw lands between the lowest and the "
            "highest of them, and the draws that pick one task "
            f"{size} times attain exactly those two endpoints. Each of those "
            f"draws has probability {float(p_at_min):.4f}, which is not "
            f"smaller than the {PERCENTILE_LOW}% being cut off, so the "
            "endpoints are the extremes by construction. More repeats sharpen "
            "each task's own rate and the width converges to the spread "
            "between tasks, not to zero; only more tasks would cut a tail, "
            f"and {smallest_useful} would be the first count that could"
        )
        if not informative
        else (
            f"with {size} clusters a single-task draw is rarer than the "
            f"{PERCENTILE_LOW}% tail, so the endpoints are not pinned to the "
            "extremes"
        ),
    }


# ── the contrast that does not resample tasks ────────────────────────────


def _pooled_gap(
    labels: dict[tuple[str, str], str],
    flips: dict[tuple[str, str], int],
    pairs_per_item: int,
    members: list[tuple[str, str]],
) -> float:
    left_hits = left_n = right_hits = right_n = 0
    for key in members:
        if labels[key] == REQUIRED_MODALITY:
            left_hits += flips[key]
            left_n += pairs_per_item
        else:
            right_hits += flips[key]
            right_n += pairs_per_item
    left = 100.0 * left_hits / left_n if left_n else 0.0
    right = 100.0 * right_hits / right_n if right_n else 0.0
    return left - right


def modality_contrast(
    counted: dict[str, Any], *, draws: int, seed: int
) -> dict[str, Any]:
    """Does the grader flip more on what it listened to than on what it read?

    A stratified permutation: the label ``audio`` or ``text`` is shuffled among
    the items *inside* each task, so every draw keeps each task's own mix of
    labels and its own difficulty. Tasks are never resampled, which is why the
    degeneracy in the interval above does not reach this number.

    The item is the unit that has a modality, so an item's three pair-outcomes
    move together under the shuffle. Permuting the 282 pair-observations
    independently would treat one item's three comparisons as three separate
    items and make the test look far more certain than the data are.
    """
    keys = counted["_keys"]
    modality = counted["_modality"]
    task_of = counted["_task_of"]
    flag_lists = counted["_verdict_flags"]

    members = [
        key
        for key in keys
        if modality[key] in (REQUIRED_MODALITY, CONTRAST_MODALITY)
    ]
    flips = {key: sum(flag_lists[key]) for key in members}
    labels = {key: modality[key] for key in members}
    pairs_per_item = len(PAIRS)

    strata: dict[str, list[tuple[str, str]]] = {}
    for key in members:
        strata.setdefault(task_of[key], []).append(key)

    per_task = []
    holds_everywhere = True
    for task_id in sorted(strata):
        rows = strata[task_id]
        row: dict[str, Any] = {"task_id": task_id}
        for name in (REQUIRED_MODALITY, CONTRAST_MODALITY):
            group = [key for key in rows if labels[key] == name]
            hits = sum(flips[key] for key in group)
            total = len(group) * pairs_per_item
            row[name] = {
                "items": len(group),
                "pairs": total,
                "flips": hits,
                "rate_pct": round(100.0 * hits / total, 4) if total else None,
            }
        left = row[REQUIRED_MODALITY]["rate_pct"]
        right = row[CONTRAST_MODALITY]["rate_pct"]
        row["audio_at_least_text"] = (
            left is not None and right is not None and left >= right
        )
        holds_everywhere = holds_everywhere and bool(row["audio_at_least_text"])
        per_task.append(row)

    observed = _pooled_gap(labels, flips, pairs_per_item, members)

    rng = random.Random(seed)
    at_least = 0
    at_least_abs = 0
    shuffled = dict(labels)
    for _ in range(draws):
        for rows in strata.values():
            names = [labels[key] for key in rows]
            rng.shuffle(names)
            for key, name in zip(rows, names):
                shuffled[key] = name
        gap = _pooled_gap(shuffled, flips, pairs_per_item, members)
        if gap >= observed:
            at_least += 1
        if abs(gap) >= abs(observed):
            at_least_abs += 1

    # The (1 + c) / (1 + n) form rather than c / n. With a finite number of
    # draws the plain ratio can report exactly zero, and a permutation test
    # cannot establish that something is impossible.
    p_one_sided = (1 + at_least) / (1 + draws)
    p_two_sided = (1 + at_least_abs) / (1 + draws)

    left_group = [key for key in members if labels[key] == REQUIRED_MODALITY]
    right_group = [key for key in members if labels[key] == CONTRAST_MODALITY]

    return {
        "left": REQUIRED_MODALITY,
        "right": CONTRAST_MODALITY,
        "left_rate_pct": round(
            100.0
            * sum(flips[key] for key in left_group)
            / (len(left_group) * pairs_per_item),
            4,
        ),
        "right_rate_pct": round(
            100.0
            * sum(flips[key] for key in right_group)
            / (len(right_group) * pairs_per_item),
            4,
        ),
        "gap_pp": round(observed, 4),
        "per_task": per_task,
        "holds_in_every_task": holds_everywhere,
        "permutation": {
            "draws": draws,
            "seed": seed,
            "stratum": "task",
            "unit": "rubric item, with its three pair outcomes moved together",
            "at_least_observed": at_least,
            "at_least_observed_absolute": at_least_abs,
            "p_one_sided": p_one_sided,
            "p_two_sided": p_two_sided,
            "alpha": ALPHA,
        },
        "significant": p_one_sided < ALPHA,
    }


# ── assembly ─────────────────────────────────────────────────────────────


def analyze(
    runs: list[dict[str, Any]],
    *,
    resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
    permutation_draws: int = PERMUTATION_DRAWS,
    permutation_seed: int = PERMUTATION_SEED,
) -> dict[str, Any]:
    counted = census(runs)
    keys = counted["_keys"]
    modality = counted["_modality"]
    flag_lists = counted["_verdict_flags"]

    task_ids = [task["task_id"] for task in runs[0]["tasks"]]
    audio_keys = [key for key in keys if modality[key] == REQUIRED_MODALITY]
    numerator = {task_id: 0 for task_id in task_ids}
    denominator = {task_id: 0 for task_id in task_ids}
    for key in audio_keys:
        numerator[key[0]] += sum(flag_lists[key])
        denominator[key[0]] += len(PAIRS)

    interval = task_unit_interval(
        task_ids, numerator, denominator, resamples=resamples, seed=seed
    )

    # Computed so the choice of unit can be seen rather than asserted. Treating
    # each of the 93 audio pair-observations as an independent draw is the
    # method this analysis does not use, and the ratio of the two widths is
    # the evidence for not using it.
    #
    # On the thirty-task cohort that ratio comes out below 1: the item
    # bootstrap is the narrower, over-confident one, which is the usual reason
    # for preferring the task. Here it comes out above 1, and that inversion is
    # not a point in the task interval's favour -- it is the same degeneracy
    # seen from the other side. The task interval is clamped to the range of
    # three numbers, so it can be narrow while bounding nothing. The ratio is
    # reported rather than the conclusion, because the conclusion depends on
    # which way it fell.
    item_flags = [flag for key in audio_keys for flag in flag_lists[key]]
    not_the_interval = item_bootstrap_rate(
        item_flags, resamples=resamples, seed=seed
    )

    contrast = modality_contrast(
        counted, draws=permutation_draws, seed=permutation_seed
    )

    as_registered = (
        resamples == BOOTSTRAP_RESAMPLES
        and seed == BOOTSTRAP_SEED
        and permutation_draws == PERMUTATION_DRAWS
        and permutation_seed == PERMUTATION_SEED
    )

    public = {key: value for key, value in counted.items() if not key.startswith("_")}

    return {
        "settings": {
            "bootstrap_resamples": resamples,
            "bootstrap_seed": seed,
            "permutation_draws": permutation_draws,
            "permutation_seed": permutation_seed,
            "percentiles": [PERCENTILE_LOW, PERCENTILE_HIGH],
            "alpha": ALPHA,
            "as_registered": as_registered,
        },
        "inputs": [
            {
                "label": run["_label"],
                "path": run["_source_path"],
                "digest": run["_source_digest"],
                "graded_at": run.get("graded_at"),
                "pct": [
                    round(float(task["pct"]), 4)
                    for task in run["tasks"]
                    if task.get("pct") is not None
                ],
            }
            for run in runs
        ],
        "cohort": {
            "scope_digest": runs[0].get("expected_ordered_task_ids_sha256"),
            "grader_source_hash": runs[0].get("grader_source_hash"),
            "config": _dig(runs[0], ("judge", "config_name")),
            "config_hash": _dig(runs[0], ("judge", "config_hash")),
            "tasks": len(task_ids),
            "audio_items": len(audio_keys),
            "modality_census": dict(sorted(_modality_counts(runs[0]).items())),
        },
        "census": public,
        "denominator": denominator_stability(runs),
        "audio_flip_rate_pct": round(
            counted["by_modality"][REQUIRED_MODALITY]["verdict_flip_rate_pct"], 4
        ),
        "task_unit_interval": interval,
        "item_unit_interval_not_used": {
            "low": not_the_interval["low"],
            "high": not_the_interval["high"],
            "width": not_the_interval["width"],
            "half_width": not_the_interval["half_width"],
            "width_ratio_item_over_task": (
                round(not_the_interval["width"] / interval["bootstrap"]["width"], 4)
                if interval["bootstrap"]["width"]
                else None
            ),
            "note": (
                "reported so the choice of unit is visible. Items inside one "
                "task share an output, a clip and a grading context, so this "
                "is not the interval this analysis uses. A ratio above 1 means "
                "the task interval is the narrower of the two, which on this "
                "cohort is the degeneracy above rather than an argument for it"
            ),
        },
        "contrast": contrast,
        "verdict_ok": bool(
            as_registered
            and contrast["significant"]
            and contrast["holds_in_every_task"]
        ),
    }


def _mark(ok: bool) -> str:
    return "OK  " if ok else "FAIL"


def _render(report: dict[str, Any]) -> str:
    lines: list[str] = []
    add = lines.append

    cohort = report["cohort"]
    add("audio repeat variation")
    add("=" * 72)
    add(f"cohort          {cohort['config']} ({cohort['config_hash']})")
    add(f"scope digest    {cohort['scope_digest']}")
    add(f"grader source   {cohort['grader_source_hash']}")
    add(
        f"corpus          {cohort['tasks']} tasks, "
        f"{report['census']['items']} items, "
        f"{cohort['audio_items']} of them {REQUIRED_MODALITY}"
    )
    add("")

    add("the three gradings")
    add("-" * 72)
    for row in report["inputs"]:
        add(
            f"  {row['label']}  {row['digest'][:16]}  {row['graded_at']}  "
            f"pct {row['pct']}"
        )
    add("")

    add("verdict flips, by what the grader used to reach the file")
    add("-" * 72)
    add(
        f"  {'modality':<12}{'items':>7}{'pairs':>7}{'flips':>7}{'rate':>9}"
        f"{'score moves':>13}"
    )
    for name, row in report["census"]["by_modality"].items():
        add(
            f"  {name:<12}{row['items']:>7}{row['pairs']:>7}"
            f"{row['verdict_flips']:>7}{row['verdict_flip_rate_pct']:>8.2f}%"
            f"{row['score_moves']:>13}"
        )
    add(
        f"  {'ALL':<12}{report['census']['items']:>7}"
        f"{report['census']['pairs']:>7}{report['census']['verdict_flips']:>7}"
        f"{report['census']['verdict_flip_rate_pct']:>8.2f}%"
        f"{report['census']['score_moves']:>13}"
    )
    add("")
    for name, count in sorted(report["census"]["transitions"].items()):
        add(f"  {name:<40}{count:>6}")
    add("")

    denominator = report["denominator"]
    add("did the set of items that count move")
    add("-" * 72)
    add(
        f"  {_mark(denominator['identical_across_runs'])} excluded items per "
        f"run {denominator['excluded_per_run']}, identical across runs: "
        f"{denominator['identical_across_runs']}"
    )
    add(
        f"       modalities ever excluded: "
        f"{denominator['modalities_ever_excluded'] or 'none'}"
    )
    add(
        f"       {REQUIRED_MODALITY} items ever excluded: "
        f"{denominator[f'{REQUIRED_MODALITY}_items_ever_excluded']}"
    )
    add("")

    interval = report["task_unit_interval"]
    add("the task-unit interval that was asked for")
    add("-" * 72)
    add(
        f"  point estimate            {report['audio_flip_rate_pct']:.2f}% "
        f"of {report['census']['by_modality'][REQUIRED_MODALITY]['pairs']} "
        "item pairs"
    )
    add(
        f"  bootstrap 95%             "
        f"[{interval['bootstrap']['low']:.2f}, "
        f"{interval['bootstrap']['high']:.2f}]  "
        f"half-width {interval['bootstrap']['half_width']:.2f}pp"
    )
    add(
        f"  exact quantiles           "
        f"[{interval['exact_quantiles_pct']['low']:.2f}, "
        f"{interval['exact_quantiles_pct']['high']:.2f}]"
    )
    add(
        f"  attainable at all         "
        f"[{interval['extremes_pct']['min']:.2f}, "
        f"{interval['extremes_pct']['max']:.2f}]  "
        f"({interval['distinct_attainable_values']} distinct values over "
        f"{interval['ordered_draws']} draws)"
    )
    add(f"  --   is_informative: {interval['is_informative']}")
    add(f"       {interval['why']}")
    add(
        f"       per-task rates "
        f"{ {k[:8]: round(v, 2) for k, v in interval['per_task_rate_pct'].items()} }"
    )
    add(
        f"       width floor {interval['width_floor_pp']:.2f}pp -- what more "
        "repeats converge to, not zero"
    )
    add("")
    not_used = report["item_unit_interval_not_used"]
    add(
        f"  not the interval          "
        f"[{not_used['low']:.2f}, {not_used['high']:.2f}] if items were "
        "independent draws"
    )
    add(
        f"       {not_used['width_ratio_item_over_task']:.2f}x the width of "
        "the task interval; above 1 means the task interval is the narrower "
        "one here, which is the clamping above rather than an argument for it"
    )
    add("")

    contrast = report["contrast"]
    add("what the runs do support: listened-to vs read, inside each run")
    add("-" * 72)
    add(
        f"  {contrast['left']} {contrast['left_rate_pct']:.2f}%  vs  "
        f"{contrast['right']} {contrast['right_rate_pct']:.2f}%   "
        f"gap {contrast['gap_pp']:.2f}pp"
    )
    for row in contrast["per_task"]:
        left = row[contrast["left"]]
        right = row[contrast["right"]]
        add(
            f"    {row['task_id'][:8]}  {contrast['left']} "
            f"{left['flips']}/{left['pairs']} = {left['rate_pct']:.2f}%   "
            f"{contrast['right']} {right['flips']}/{right['pairs']} = "
            f"{right['rate_pct']:.2f}%"
        )
    permutation = contrast["permutation"]
    add(
        f"  stratified permutation    {permutation['draws']} draws, labels "
        f"shuffled within {permutation['stratum']}, seed {permutation['seed']}"
    )
    add(
        f"  p (one-sided)             {permutation['p_one_sided']:.5f}   "
        f"threshold {permutation['alpha']}"
    )
    add(
        f"  {_mark(contrast['holds_in_every_task'])} direction holds inside "
        f"every task: {contrast['holds_in_every_task']}"
    )
    add("")

    settings = report["settings"]
    add("verdict")
    add("-" * 72)
    add(f"  {_mark(settings['as_registered'])} run at the registered settings")
    add(
        f"  {_mark(contrast['significant'])} the contrast is not chance at "
        f"alpha {settings['alpha']}"
    )
    add(
        f"  {_mark(contrast['holds_in_every_task'])} the contrast holds inside "
        "every task"
    )
    add("")
    add(f"  {'PASS' if report['verdict_ok'] else 'FAIL'}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "grade_files",
        type=Path,
        nargs="+",
        help="the three repeat payloads of the pinned audio cohort",
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
            "the bootstrap seed. Registered value: 20260902. Any other value "
            "is a real interval for a different analysis, and this tool marks "
            "the run accordingly"
        ),
    )
    parser.add_argument(
        "--permutation-draws",
        type=int,
        default=PERMUTATION_DRAWS,
        help="how many label shuffles. Registered value: 100000",
    )
    parser.add_argument(
        "--permutation-seed",
        type=int,
        default=PERMUTATION_SEED,
        help="the permutation seed. Registered value: 20260902",
    )
    args = parser.parse_args(argv)

    runs = load_runs(args.grade_files)

    problems = (
        shared_arithmetic_problems()
        + fingerprint_problems(runs)
        + shape_problems(runs)
    )
    if problems:
        raise RepeatsAreNotComparable(
            "these payloads cannot answer the question this analysis asks:\n"
            "  - " + "\n  - ".join(problems)
        )

    report = analyze(
        runs,
        resamples=args.bootstrap_resamples,
        seed=args.seed,
        permutation_draws=args.permutation_draws,
        permutation_seed=args.permutation_seed,
    )

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(_render(report))

    return 0 if report["verdict_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
