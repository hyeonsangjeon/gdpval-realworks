#!/usr/bin/env python3
"""Read a gold-ceiling grade payload and answer the questions the specs ask.

Why this exists
---------------
``tasks/rebuilding_grading_task/300-gold-ceiling.md`` asks for six things: the
mean score, the required-item pass rate, the grader error rate, the evidence
behind every item that fell short of full marks, the usage split by model, and
the actual bill. Every one of those is already in the grade payload. Copying
them into a report by hand is where a report stops matching its run -- so this
reads them out, and the report quotes this.

``304-full-gold-corpus.md`` asks the same six of a corpus six times the size,
and three more that only make sense once there is a bigger corpus to ask them
of: the mean per occupation, the mean of the same thirty tasks stage 1 graded
so the two runs can be compared like for like, and the mean with the five
known-limit tasks held out. Those three are the ``by_occupation`` and
``subsets`` blocks.

Two of the original six need work the payload does not do for you:

* **Image and audio call counts separately.** ``summary.cost`` carries one
  ``total_perception_calls``. Which of those looked at a picture and which
  listened to a recording is only recoverable per rubric item, from
  ``routing_modality``, so this regroups them.
* **Which shortfalls are the grader's fault.** Nothing can decide that
  automatically. What this does is surface every below-maximum item with the
  evidence the judge recorded, sorted so the largest losses come first, which
  is the input a person needs to classify them.

It also refuses a payload that is not one of the corpora pinned below, fully
graded. A number read out of the wrong file is worse than no number, and the
things it checks -- the ordered-id fingerprint, the task count, the graded
count and the run status -- are the ones that differ when somebody points this
at a single shard or at a corpus nobody pinned. The fingerprint decides *which*
corpus a payload is, so stage 1's thirty and stage 3's hundred and eighty-five
are both read without a flag, and neither can be mistaken for the other. A
stage 2 repeat passes too, and should: it is the same thirty tasks graded
again, which is exactly what stage 2 needs to read.

Usage
-----
    python batch-runner/scripts/analyze_gold_ceiling.py <grade.json>
    python batch-runner/scripts/analyze_gold_ceiling.py <grade.json> --json

Exit status is 0 when every threshold is met and 1 when any is missed, so a
run that quietly fell below the ceiling cannot be reported as passing.
"""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, NamedTuple

# The three numbers stage 1 is accepted or rejected on, from
# `tasks/rebuilding_grading_task/300-gold-ceiling.md` lines 17-19 and 24-26.
# `test_gold_ceiling_analysis.py` checks these against the specification text,
# so a threshold edited in one place and not the other fails rather than drifts.
MEAN_SCORE_PCT_FLOOR = 90.0
CRITICAL_ITEM_PASS_FLOOR = 0.95
JUDGE_ERROR_RATE_CEILING = 0.02

# Which items the second threshold counts. Imported rather than restated: the
# comment above `MAGNITUDE_THRESHOLD` names this very run as the thing that
# should decide whether 4 is the right boundary, so an analysis that counted
# through its own copy of the number could disagree with the grader about what
# it was measuring at exactly the moment the disagreement mattered.
#
# The report's generated blocks run this from the repository root, where
# `batch-runner/` is not importable, so the package root goes on the path here
# rather than relying on the caller's working directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.grader import MAGNITUDE_THRESHOLD as REQUIRED_ITEM_MIN_ABS_SCORE  # noqa: E402
from step8_grade import _ordered_task_ids_sha256  # noqa: E402

# What the specification pinned. A payload disagreeing with a known corpus is
# some other run, and reading a stage's numbers out of it would be a mistake no
# reader could detect afterwards.
#
# The digest is compared against `expected_ordered_task_ids_sha256` in the
# payload, and that field is written by `step8_grade._ordered_task_ids_sha256`,
# which hashes `json.dumps(ids, ensure_ascii=False, separators=(",", ":"))` --
# a compact JSON array. So each digest here has to be the compact-JSON digest
# of the same ids in the same order; any other encoding of the identical list
# produces a different digest and refuses the very run it was written for.
#
# That is not hypothetical. An earlier pass pinned the newline-joined digest
# of stage 1's exact ids, `09ce9245...`, and it refused stage 1's own run. Both
# digests cover the same thirty ids in the same order -- only the separator
# differs -- so the mismatch says nothing whatsoever about the corpus, which
# is what made it slow to read. `test_the_pinned_corpora_match_the_grading_
# configs` now recomputes both through the grader's own function rather than
# restating the formula, so they can no longer drift apart in silence.


class PinnedCorpus(NamedTuple):
    """A corpus this tool is allowed to report numbers for."""

    key: str
    label: str
    config_name: str
    task_count: int
    ordered_task_ids_sha256: str


STAGE_ONE_CORPUS = PinnedCorpus(
    key="stage1-30",
    label="stage 1 -- the 30-task sample",
    config_name="gold_ceiling_30_v2_sol_max",
    task_count=30,
    ordered_task_ids_sha256=(
        "82d14ac9bf9c3ad37920fb781ee961f5e20805c52618df0d0cdb9d5e677a7e8b"
    ),
)

STAGE_THREE_CORPUS = PinnedCorpus(
    key="stage3-185",
    label="stage 3 -- the whole 185-task gold population",
    config_name="gold_ceiling_185_v2_sol_max",
    task_count=185,
    ordered_task_ids_sha256=(
        "cef3a5b9f1305f19437d6ee337936a065965f979325b95a41d1001747e6bfa18"
    ),
)

#: Every corpus this tool will report on. Stage 3 is listed here rather than
#: read through `--allow-any-run` on purpose: that flag's own help says it is
#: never for a number a report will quote, so reaching for it to produce the
#: stage 3 report would have made the report's provenance exactly as weak as
#: the flag warns. A corpus a report quotes belongs in this tuple, where the
#: identity check still applies to it.
PINNED_CORPORA: tuple[PinnedCorpus, ...] = (STAGE_ONE_CORPUS, STAGE_THREE_CORPUS)

# Kept as module-level names because the payload identity check, the report's
# generated blocks and the tests all grew up around stage 1 being *the* corpus.
EXPECTED_TASK_COUNT = STAGE_ONE_CORPUS.task_count
EXPECTED_ORDERED_TASK_IDS_SHA256 = STAGE_ONE_CORPUS.ordered_task_ids_sha256

#: The five tasks `304-full-gold-corpus.md` declared as known input limits
#: *before* the paid run, so their effect on the mean is separated rather than
#: argued about afterwards. Four of them arrive with stage 3's widening; only
#: `38889c3b` was inside stage 1's sample.
KNOWN_LIMIT_TASK_IDS: tuple[str, ...] = (
    "38889c3b",
    "a73fbc98",
    "e222075d",
    "75401f7c",
    "7de33b48",
)

# What a finished run is allowed to call itself. Both spellings mean the same
# thing here -- every task was graded -- and which one a gold run gets is
# decided by whether it was sharded, not by anything about its completeness.
# `step8_grade.py` marks a gold-corpus run `diagnostic` so it forks away from
# the dashboard, but `step9_merge_shards.py` writes a flat `final` when it
# joins shards back together. Insisting on `final` would therefore refuse a
# perfectly complete single-shard repeat, which is precisely the run stage 2
# needs to read. `partial` is the one that must never be accepted: a shard
# declares the whole corpus in its identity fields while holding only its own
# slice, so its aggregates read exactly like the full run's.
COMPLETE_RUN_STATUSES = frozenset({"final", "diagnostic"})


class NotTheRunThatWasPinned(SystemExit):
    """The payload is readable but is not one of the pinned runs."""


def identify_corpus(payload: dict[str, Any]) -> PinnedCorpus | None:
    """Which pinned corpus this payload claims to be, or ``None``.

    Matched on the ordered-id digest rather than on the task count, because
    the digest names the exact ids in the exact order while the count is
    satisfied by any corpus of the same size. Stage 3 dropping one task and
    gaining another would keep 185 and change the digest, and it is the digest
    that has to refuse it.

    The count is then checked *against the matched corpus* rather than used to
    find it, so a payload carrying stage 3's digest and stage 1's count is a
    contradiction this reports instead of resolving.
    """
    digest = payload.get("expected_ordered_task_ids_sha256")
    for corpus in PINNED_CORPORA:
        if digest == corpus.ordered_task_ids_sha256:
            return corpus
    return None


def _identity_problems(payload: dict[str, Any]) -> list[str]:
    problems: list[str] = []

    status = payload.get("run_status")
    if status not in COMPLETE_RUN_STATUSES:
        problems.append(
            f"run_status is {status!r}, which is not a finished run "
            f"({', '.join(sorted(COMPLETE_RUN_STATUSES))}) -- a shard covers "
            "only its own slice while declaring the whole corpus"
        )

    corpus = identify_corpus(payload)
    if corpus is None:
        known = ", ".join(
            f"{item.key} ({item.task_count} tasks, "
            f"{item.ordered_task_ids_sha256[:12]}...)"
            for item in PINNED_CORPORA
        )
        problems.append(
            "expected_ordered_task_ids_sha256 is "
            f"{payload.get('expected_ordered_task_ids_sha256')!r}, which is "
            f"not a pinned corpus -- known: {known}"
        )
        return problems

    count = payload.get("expected_task_count")
    if count != corpus.task_count:
        problems.append(
            f"expected_task_count is {count!r}, but the ordered-id digest is "
            f"{corpus.key}'s, which pins {corpus.task_count}"
        )

    graded = (payload.get("summary") or {}).get("graded_tasks")
    if graded != corpus.task_count:
        problems.append(
            f"summary.graded_tasks is {graded!r}, so {corpus.task_count} "
            f"tasks were pinned by {corpus.key} but a different number was "
            "graded"
        )

    return problems


def perception_calls_by_modality(payload: dict[str, Any]) -> dict[str, int]:
    """How many perception calls each routing modality accounted for.

    ``summary.cost.total_perception_calls`` is one number. The specification
    asks for the image and audio counts separately, and only the rubric items
    know which was which.
    """
    by_modality: dict[str, int] = defaultdict(int)
    for task in payload.get("tasks") or []:
        for item in task.get("items") or []:
            calls = item.get("perception_call_count") or 0
            if calls:
                by_modality[item.get("routing_modality") or "unrecorded"] += calls
    return dict(sorted(by_modality.items()))


def items_below_full_marks(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Every rubric item that did not score its maximum, biggest loss first.

    This is the raw material for the specification's "library limit or genuine
    shortfall" call. It deliberately keeps items whose award is *above* the
    maximum out of the list but reports them separately as a fault, because a
    score over the maximum is a grader bug rather than a shortfall.
    """
    shortfalls: list[dict[str, Any]] = []
    for task in payload.get("tasks") or []:
        for item in task.get("items") or []:
            awarded = item.get("awarded_score")
            maximum = item.get("max_score")
            if awarded is None or maximum is None:
                continue
            if item.get("score_excluded"):
                continue
            if awarded >= maximum:
                continue
            shortfalls.append(
                {
                    "task_id": task.get("task_id"),
                    "sector": task.get("sector"),
                    "occupation": task.get("occupation"),
                    "rubric_item_id": item.get("rubric_item_id"),
                    "criterion": item.get("criterion"),
                    "awarded_score": awarded,
                    "max_score": maximum,
                    "lost": round(float(maximum) - float(awarded), 4),
                    "verdict": item.get("verdict"),
                    "required": item.get("required"),
                    "decided_by": item.get("decided_by"),
                    "routing_modality": item.get("routing_modality"),
                    "perception_called": item.get("perception_called"),
                    "selection_status": item.get("selection_status"),
                    "selection_error": item.get("selection_error"),
                    "selected_paths": item.get("selected_paths"),
                    "judge_confidence": item.get("judge_confidence"),
                    "evidence": item.get("evidence"),
                }
            )
    shortfalls.sort(key=lambda row: (-row["lost"], str(row["task_id"])))
    return shortfalls


def per_task(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """One row per graded task, worst score first.

    The specification asks for per-task evidence, and a report that lists only
    its biggest individual losses can leave a whole task unmentioned -- the
    forty largest item losses in stage 1's first run came from nine tasks, so
    twenty-one of the thirty were invisible in that view. Ranking by item loss
    answers "where did the points go"; this answers "how did each answer do",
    which is the question a per-task classification is written against.

    Scores are read from the fields the grader wrote (``pct``, ``total_awarded``,
    ``total_max``) rather than recomputed from the items, so this reports the
    run's own arithmetic instead of a second opinion about it.

    ``points_lost`` is that subtraction rather than a sum over the items below
    their maximum, and the two can differ. A rubric may carry penalty items with
    a *negative* maximum -- "reviews articles behind a paywall", "includes test
    questions beyond the two required" -- which `core/grader.py` deliberately
    keeps out of the denominator via ``max(0, it.max_score)``. Full marks on
    such an item is an award of zero, so a fired penalty leaves the award
    *below* zero but never below the maximum, and an item-wise sum would drop it
    while the task's own total counts it. Stage 1's first run had two of these
    and neither fired, so the two spellings happened to agree; relying on that
    would be relying on a coincidence.
    """
    rows: list[dict[str, Any]] = []
    for task in payload.get("tasks") or []:
        items = task.get("items") or []
        below = [
            item
            for item in items
            if not item.get("score_excluded")
            and item.get("awarded_score") is not None
            and item.get("max_score") is not None
            and item["awarded_score"] < item["max_score"]
        ]
        awarded = task.get("total_awarded")
        maximum = task.get("total_max")
        rows.append(
            {
                "task_id": task.get("task_id"),
                "sector": task.get("sector"),
                "occupation": task.get("occupation"),
                "pct": task.get("pct"),
                "total_awarded": awarded,
                "total_max": maximum,
                "items": len(items),
                "items_below_full_marks": len(below),
                "points_lost": (
                    None
                    if awarded is None or maximum is None
                    else round(float(maximum) - float(awarded), 4)
                ),
                "critical_fail": bool(task.get("critical_fail")),
                "selection_status": task.get("selection_status"),
                "error": task.get("error"),
            }
        )
    rows.sort(
        key=lambda row: (
            row["pct"] if row["pct"] is not None else -1.0,
            str(row["task_id"]),
        )
    )
    return rows


def _counts_toward_required_rate(item: dict[str, Any]) -> bool:
    """The run's own test for an item the second threshold counts.

    Both halves are `step8_grade.py`'s, at the line that fills
    ``critical_item_pass_rate``::

        if not score_excluded and _is_critical_item(item.get("max_score")):

    An excluded item is one the grader decided not to score at all, so counting
    it would put an item in the denominator that no answer could have moved.
    """
    if item.get("score_excluded"):
        return False
    maximum = item.get("max_score")
    return maximum is not None and abs(maximum) >= REQUIRED_ITEM_MIN_ABS_SCORE


def required_items(payload: dict[str, Any]) -> dict[str, Any]:
    """What the second threshold is actually counting.

    An item is required when ``|max_score| >= 4`` and the grader did not
    exclude it from scoring, and it passes when ``model_did_right`` is true --
    **not** when the verdict is ``pass``. That distinction is the whole reason
    this function was rewritten, and `step8_grade.py` states it at the point of
    use: the legacy spelling was *"both wrong-threshold and wrong-sign"*, and
    the sign is what bites here.

    A penalty item carries a negative maximum -- "reviews articles behind a
    paywall", "uses footage with identifiable faces". Its verdict answers *did
    the deliverable do this thing*, so a verdict of ``pass`` on a penalty means
    the penalty **fired** and the answer was marked down. Reading ``pass`` as
    success therefore inverts every penalty item: the answers that avoided the
    trap are counted as failures and the ones that fell in are counted as
    successes.

    Stage 1's thirty tasks contained no negative required items at all, so the
    two spellings returned the same 0.5714 and the defect was invisible. The
    185-task corpus contains 54 of them across 8 tasks -- 15% of the
    denominator -- and 38 sit in one task. So this reports both rates and the
    items they disagree on, rather than quietly swapping one number for the
    other in a report whose earlier edition quoted the old one.

    ``rate`` is the run's definition, because it is the number the gate is
    judged on and a report must not print a second opinion beside it under the
    same name.
    """
    rows: list[dict[str, Any]] = []
    for task in payload.get("tasks") or []:
        for item in task.get("items") or []:
            maximum = item.get("max_score")
            if maximum is None or abs(maximum) < REQUIRED_ITEM_MIN_ABS_SCORE:
                continue
            rows.append(
                {
                    "task_id": task.get("task_id"),
                    "criterion": (item.get("criterion") or "").strip(),
                    "max_score": maximum,
                    "awarded_score": item.get("awarded_score"),
                    "verdict": item.get("verdict"),
                    "score_excluded": bool(item.get("score_excluded")),
                    "model_did_right": item.get("model_did_right"),
                    "counted": _counts_toward_required_rate(item),
                }
            )

    counted = [row for row in rows if row["counted"]]
    passed = sum(1 for row in counted if bool(row["model_did_right"]))

    # The retired definition, over the denominator it used: no exclusion filter.
    legacy_passed = sum(1 for row in rows if row["verdict"] == "pass")

    disagreements = [
        row
        for row in counted
        if bool(row["model_did_right"]) != (row["verdict"] == "pass")
    ]

    # An item with no `model_did_right` cannot be scored by the run's rule, and
    # defaulting it to False the way the grader does would read a payload too
    # old to carry the field as a total failure. Counted and reported instead.
    unscorable = [row for row in counted if row["model_did_right"] is None]

    penalties = [row for row in counted if row["max_score"] < 0]

    by_verdict = Counter(str(row["verdict"]) for row in counted)
    by_criterion = Counter(row["criterion"] for row in counted)

    payload_rate = ((payload.get("summary") or {}).get("wow") or {}).get(
        "critical_item_pass_rate"
    )
    rate = None if not counted else round(passed / len(counted), 4)

    return {
        "total": len(counted),
        "passed": passed,
        "rate": rate,
        "by_verdict": dict(by_verdict.most_common()),
        "recurring_criteria": [
            {
                "criterion": criterion,
                "tasks": count,
                "passed": sum(
                    1
                    for row in counted
                    if row["criterion"] == criterion
                    and bool(row["model_did_right"])
                ),
            }
            for criterion, count in by_criterion.most_common()
            if count > 1
        ],
        "score_excluded": len(rows) - len(counted),
        "unscorable": len(unscorable),
        "penalty_items": len(penalties),
        "penalty_items_fired": sum(
            1 for row in penalties if not bool(row["model_did_right"])
        ),
        "legacy_verdict_pass": {
            "total": len(rows),
            "passed": legacy_passed,
            "rate": None if not rows else round(legacy_passed / len(rows), 4),
            "disagreements": len(disagreements),
            "disagreeing_items": sorted(
                (
                    {
                        "task_id": row["task_id"],
                        "criterion": row["criterion"],
                        "max_score": row["max_score"],
                        "verdict": row["verdict"],
                        "model_did_right": row["model_did_right"],
                    }
                    for row in disagreements
                ),
                key=lambda row: (str(row["task_id"]), str(row["criterion"])),
            ),
        },
        # The rate the gate is judged on is written by the grader, not by this
        # tool. If the two disagree, one of them is wrong and the report must
        # not pick a side silently.
        "payload_rate": payload_rate,
        "agrees_with_payload": (
            payload_rate is not None
            and rate is not None
            and abs(rate - float(payload_rate)) <= 0.0001
        ),
    }


def _aggregate(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    """Score a group of tasks the way the run scores the whole corpus.

    The two headline numbers are aggregated differently and a recomputation
    that picks one style for both is wrong twice:

    * ``avg_pct`` is a **macro** mean -- the mean of each task's ``pct``, over
      tasks that did not error. Every task weighs the same regardless of how
      many rubric items it carries. `step8_grade.py` computes it as
      ``sum(pcts) / len(pcts)`` over ``[t for t in tasks if not t["error"]]``.
    * ``critical_item_pass_rate`` is a **micro** rate -- required items passed
      over required items counted, pooled across tasks, so a task with forty
      required items pulls forty times as hard as a task with one.

    ``avg_pct_raw`` is the same macro mean over ``pct_raw``, which the grader
    writes before clamping ``pct`` into [0, 100]. The two differ only where
    penalties drove a task below zero, and there the clamped mean cannot tell a
    fired penalty from an answer that simply scored nothing. One task in the
    185 carries -380 points of penalties against a 50-point maximum, so this is
    a real distinction on this corpus rather than a defensive one.
    """
    scored = [task for task in tasks if not task.get("error")]

    pcts = [
        float(task["pct"]) for task in scored if task.get("pct") is not None
    ]
    raws = [
        float(task["pct_raw"])
        for task in scored
        if task.get("pct_raw") is not None
    ]

    counted = [
        item
        for task in tasks
        for item in (task.get("items") or [])
        if _counts_toward_required_rate(item)
    ]
    passed = sum(1 for item in counted if bool(item.get("model_did_right")))

    clamped = [
        str(task.get("task_id"))
        for task in scored
        if task.get("pct") is not None
        and task.get("pct_raw") is not None
        and abs(float(task["pct_raw"]) - float(task["pct"])) > 1e-9
    ]

    return {
        "task_count": len(tasks),
        "graded_tasks": len(scored),
        "error_tasks": len(tasks) - len(scored),
        "avg_pct": round(sum(pcts) / len(pcts), 2) if pcts else None,
        "avg_pct_raw": round(sum(raws) / len(raws), 2) if raws else None,
        "required_items": len(counted),
        "required_passed": passed,
        "critical_item_pass_rate": (
            round(passed / len(counted), 4) if counted else None
        ),
        "tasks_clamped_at_zero": clamped,
    }


def by_occupation(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Per-occupation means, the breakdown `304` asks for and the payload lacks.

    The payload carries ``wow.by_sector`` and nothing by occupation, yet
    occupation is where stage 3's widening actually happened: stage 1 reached 7
    of 44 occupations against all 9 sectors' worth of 4. A sector average over
    nine buckets cannot show which of the 37 newly-covered occupations moved
    the ceiling.
    """
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for task in payload.get("tasks") or []:
        groups[str(task.get("occupation") or "unrecorded")].append(task)
    return {name: _aggregate(tasks) for name, tasks in sorted(groups.items())}


def _match_task_ids(
    payload: dict[str, Any], wanted: tuple[str, ...] | list[str]
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    """Resolve id prefixes against the payload, refusing ambiguity.

    The specification names tasks by their first eight characters while the
    payload carries full UUIDs, so these have to be matched by prefix. A prefix
    that matches two tasks would silently double-count one and a prefix that
    matches none would silently shrink the subset, and either would move a mean
    the report quotes -- so both are returned rather than absorbed.
    """
    tasks = payload.get("tasks") or []
    matched: list[dict[str, Any]] = []
    missing: list[str] = []
    ambiguous: list[str] = []
    for prefix in wanted:
        hits = [
            task for task in tasks if str(task.get("task_id")).startswith(prefix)
        ]
        if not hits:
            missing.append(prefix)
        elif len(hits) > 1:
            ambiguous.append(prefix)
        else:
            matched.append(hits[0])
    return matched, missing, ambiguous


def subset_scores(
    payload: dict[str, Any],
    task_ids: tuple[str, ...] | list[str],
    *,
    exclude: bool = False,
) -> dict[str, Any]:
    """Re-score the corpus over a subset, or over everything but a subset.

    `304-full-gold-corpus.md` promises the mean *with and without* the five
    declared input limits, so that their share is separated rather than argued
    about after the fact. Recomputing it needs the run's own two aggregation
    styles, which is why this goes through `_aggregate` rather than averaging
    the per-task percentages a second way.
    """
    matched, missing, ambiguous = _match_task_ids(payload, task_ids)
    matched_ids = {id(task) for task in matched}

    if exclude:
        selected = [
            task
            for task in (payload.get("tasks") or [])
            if id(task) not in matched_ids
        ]
    else:
        selected = matched

    block = _aggregate(selected)
    block["requested"] = list(task_ids)
    block["matched"] = [str(task.get("task_id")) for task in matched]
    block["missing"] = missing
    block["ambiguous"] = ambiguous
    block["excluded"] = exclude
    return block


def stage_one_subset(payload: dict[str, Any]) -> dict[str, Any]:
    """How stage 1's thirty tasks scored inside this run.

    Stage 1's corpus is the first thirty of stage 3's in the same order, and
    `step9_merge_shards.py` normalises shards back into canonical corpus order
    before writing, so the first thirty entries of a merged payload *are* those
    tasks. That is an inference about ordering, though, and a report should not
    rest a comparison on one -- so it is checked: the thirty ids are hashed
    with the grader's own function and the digest has to be stage 1's pinned
    `82d14ac9...`.

    If it is not, ``verified`` is false and the numbers are withheld. A
    same-30 comparison drawn from the wrong thirty tasks is worse than no
    comparison, because nothing downstream could tell.
    """
    tasks = payload.get("tasks") or []
    corpus = STAGE_ONE_CORPUS

    if len(tasks) < corpus.task_count:
        return {
            "verified": False,
            "reason": (
                f"payload holds {len(tasks)} tasks, fewer than the "
                f"{corpus.task_count} stage 1 pinned"
            ),
        }

    first = tasks[: corpus.task_count]
    digest = _ordered_task_ids_sha256(
        [str(task.get("task_id")) for task in first]
    )
    if digest != corpus.ordered_task_ids_sha256:
        return {
            "verified": False,
            "reason": (
                f"the first {corpus.task_count} tasks hash to {digest}, not "
                f"stage 1's {corpus.ordered_task_ids_sha256} -- so they are "
                "not stage 1's corpus in stage 1's order"
            ),
            "ordered_task_ids_sha256": digest,
        }

    block = _aggregate(first)
    block["verified"] = True
    block["ordered_task_ids_sha256"] = digest
    return block


def _tasks_with_errors(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"task_id": task.get("task_id"), "error": task.get("error")}
        for task in payload.get("tasks") or []
        if task.get("error")
    ]


def _tasks_failing_a_required_item(payload: dict[str, Any]) -> list[str]:
    return [
        str(task.get("task_id"))
        for task in payload.get("tasks") or []
        if task.get("critical_fail")
    ]


def analyze(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary") or {}
    compat = summary.get("openai_compat") or {}
    wow = summary.get("wow") or {}
    cost = summary.get("cost") or {}

    mean_pct = compat.get("avg_score_pct")
    critical_pass = wow.get("critical_item_pass_rate")
    error_rate = wow.get("judge_error_rate")

    gates = {
        "mean_score_pct": {
            "value": mean_pct,
            "floor": MEAN_SCORE_PCT_FLOOR,
            "met": mean_pct is not None and mean_pct >= MEAN_SCORE_PCT_FLOOR,
        },
        "critical_item_pass_rate": {
            "value": critical_pass,
            "floor": CRITICAL_ITEM_PASS_FLOOR,
            "met": (
                critical_pass is not None
                and critical_pass >= CRITICAL_ITEM_PASS_FLOOR
            ),
        },
        "judge_error_rate": {
            "value": error_rate,
            "ceiling": JUDGE_ERROR_RATE_CEILING,
            "met": error_rate is not None and error_rate < JUDGE_ERROR_RATE_CEILING,
        },
    }

    shortfalls = items_below_full_marks(payload)
    graded_items = sum(len(task.get("items") or []) for task in payload.get("tasks") or [])
    corpus = identify_corpus(payload)

    return {
        "identity": {
            "corpus": None if corpus is None else corpus.key,
            "corpus_label": None if corpus is None else corpus.label,
            "experiment_id": payload.get("experiment_id"),
            "run_status": payload.get("run_status"),
            "graded_at": payload.get("graded_at"),
            "judge": payload.get("judge"),
            "grader_source_hash": payload.get("grader_source_hash"),
            "renderer_fingerprint": payload.get("renderer_fingerprint"),
            "source_inference_revision": payload.get("source_inference_revision"),
            "source_azure_ai_provenance_status": payload.get(
                "source_azure_ai_provenance_status"
            ),
            "expected_task_count": payload.get("expected_task_count"),
            "expected_ordered_task_ids_sha256": payload.get(
                "expected_ordered_task_ids_sha256"
            ),
            "shard_provenance": payload.get("shard_provenance"),
        },
        "gates": gates,
        "all_gates_met": all(gate["met"] for gate in gates.values()),
        "scores": {
            "graded_tasks": summary.get("graded_tasks"),
            "error_tasks": summary.get("error_tasks"),
            "perfect_count": compat.get("perfect_count"),
            "zero_count": compat.get("zero_count"),
            "partial_count": compat.get("partial_count"),
            "ci_pct": compat.get("ci_pct"),
            "rubric_item_coverage_avg": wow.get("rubric_item_coverage_avg"),
            "judge_pass_rate": wow.get("judge_pass_rate"),
            "precheck_pass_rate": wow.get("precheck_pass_rate"),
            "by_sector": wow.get("by_sector"),
            "by_occupation": by_occupation(payload),
            "score_density_histogram": wow.get("score_density_histogram"),
        },
        "usage": {
            "total_judge_calls": cost.get("total_judge_calls"),
            "total_main_judge_calls": cost.get("total_main_judge_calls"),
            "total_perception_calls": cost.get("total_perception_calls"),
            "total_render_calls": cost.get("total_render_calls"),
            "main_input_tokens": cost.get("main_input_tokens"),
            "main_output_tokens": cost.get("main_output_tokens"),
            "main_cached_tokens": cost.get("main_cached_tokens"),
            "perception_input_tokens": cost.get("perception_input_tokens"),
            "perception_output_tokens": cost.get("perception_output_tokens"),
            "perception_cached_tokens": cost.get("perception_cached_tokens"),
            "total_judge_latency_sec": cost.get("total_judge_latency_sec"),
            "usage_complete": cost.get("usage_complete"),
            "perception_calls_by_modality": perception_calls_by_modality(payload),
        },
        "bill": {
            "estimated_cost_usd": cost.get("estimated_cost_usd"),
            "pricing_complete": cost.get("pricing_complete"),
            "unpriced_models": cost.get("unpriced_models"),
        },
        "shortfalls": {
            "graded_items": graded_items,
            "below_full_marks": len(shortfalls),
            "total_points_lost": round(sum(row["lost"] for row in shortfalls), 4),
            "tasks_failing_a_required_item": _tasks_failing_a_required_item(payload),
            "tasks_with_errors": _tasks_with_errors(payload),
            "items": shortfalls,
        },
        "per_task": per_task(payload),
        "required_items": required_items(payload),
        "subsets": {
            # `304` asks for the mean with and without the five declared input
            # limits, and for the same thirty tasks stage 1 measured. All three
            # go through the run's own aggregation so they can sit in one table
            # beside the headline number without a footnote about arithmetic.
            "stage_one_same_thirty": stage_one_subset(payload),
            "known_limits_only": subset_scores(payload, KNOWN_LIMIT_TASK_IDS),
            "without_known_limits": subset_scores(
                payload, KNOWN_LIMIT_TASK_IDS, exclude=True
            ),
        },
    }


def _mark(met: bool) -> str:
    return "PASS" if met else "MISS"


def _describe_renderer(fingerprint: Any) -> str:
    """The renderer line, with the LibreOffice version where a reader looks.

    Stage 1 freezes the LibreOffice version by name, so it should not be
    something you find by reading a dictionary printed sideways.
    """
    if not isinstance(fingerprint, dict):
        return str(fingerprint)
    parts = [
        str(fingerprint.get("libreoffice_version") or "libreoffice version unrecorded")
    ]
    pymupdf = fingerprint.get("pymupdf_version")
    if pymupdf:
        parts.append(f"pymupdf {pymupdf}")
    return ", ".join(parts)


def _wrapped_ids(task_ids: list[str], *, per_line: int = 3, indent: str = " " * 6) -> list[str]:
    """Identifiers down the page rather than off the side of it."""
    return [
        indent + ", ".join(task_ids[start : start + per_line])
        for start in range(0, len(task_ids), per_line)
    ]


def _wrapped_prose(
    text: str,
    *,
    indent: str,
    width: int = 110,
    first_indent: str | None = None,
) -> list[str]:
    """A sentence down the page rather than off the side of it.

    The readable report is checked line by line for width, because a report
    somebody has to scroll sideways to read is one they stop reading.
    """
    return textwrap.wrap(
        text,
        width=width,
        initial_indent=indent if first_indent is None else first_indent,
        subsequent_indent=indent,
    ) or [(indent if first_indent is None else first_indent) + text]


def _labelled_prose(label: str, text: str | None, *, budget: int) -> list[str]:
    """A labelled sentence, wrapped under a hanging indent.

    The criterion and the judge's evidence are free text written by other
    people, so they arrive at any length and with newlines in them. They used
    to be cut with a bare slice, which both ran off the side of the page and
    stopped mid-word; this collapses the whitespace, cuts on a word boundary
    if it must cut at all, and lets the rest wrap underneath the label.
    """
    body = " ".join((text or "").split())
    if not body:
        return []
    if len(body) > budget:
        body = textwrap.shorten(body, width=budget, placeholder=" ...")
    return _wrapped_prose(
        body, indent=" " * 17, first_indent=f"      {label:<9}  "
    )


def _render_subset(label: str, block: dict[str, Any]) -> list[str]:
    """One subset's line, or the reason there isn't one.

    A withheld subset prints why it was withheld. Printing nothing would read
    the same as a subset that scored nothing. The reason carries two 64-character
    fingerprints, so it is wrapped rather than run off the side of the page.
    """
    if block.get("verified") is False:
        return [f"  {label}"] + _wrapped_prose(
            f"withheld — {block.get('reason')}", indent=" " * 6
        )

    pct = "n/a" if block["avg_pct"] is None else f"{block['avg_pct']}%"
    out = [
        f"  {pct:<8} n={block['task_count']:<4d} "
        f"required {block['required_passed']}/{block['required_items']}"
        f"  ·  {label}"
    ]

    if block.get("avg_pct_raw") is not None and block["avg_pct_raw"] != block["avg_pct"]:
        out.append(
            f"      before the floor at zero: {block['avg_pct_raw']}% "
            f"({len(block['tasks_clamped_at_zero'])} task(s) clamped)"
        )
    for field, note in (
        ("missing", "named but not in this payload"),
        ("ambiguous", "matched more than one task, so left out"),
    ):
        if block.get(field):
            out.append(f"      {note}:")
            out.extend(_wrapped_ids(block[field]))
    return out


def _render(report: dict[str, Any], *, shortfall_limit: int) -> str:
    lines: list[str] = []
    identity = report["identity"]
    lines.append(f"Gold ceiling — {identity['corpus_label'] or 'unpinned corpus'}")
    lines.append("=" * 60)
    lines.append(f"  experiment      {identity['experiment_id']}")
    lines.append(f"  graded at       {identity['graded_at']}")
    lines.append(f"  run status      {identity['run_status']}")
    lines.append(f"  grader source   {identity['grader_source_hash']}")
    lines.append(f"  renderer        {_describe_renderer(identity['renderer_fingerprint'])}")
    lines.append(f"  provenance      {identity['source_azure_ai_provenance_status']}")
    lines.append("")

    lines.append("Thresholds")
    lines.append("-" * 60)
    gates = report["gates"]
    mean = gates["mean_score_pct"]
    crit = gates["critical_item_pass_rate"]
    err = gates["judge_error_rate"]
    lines.append(
        f"  mean score              {mean['value']}%   "
        f"(needs >= {mean['floor']}%)   {_mark(mean['met'])}"
    )
    lines.append(
        f"  required-item pass      {crit['value']}   "
        f"(needs >= {crit['floor']})   {_mark(crit['met'])}"
    )
    lines.append(
        f"  grader error rate       {err['value']}   "
        f"(needs < {err['ceiling']})   {_mark(err['met'])}"
    )
    lines.append("")

    req = report["required_items"]
    lines.append(
        f"Required items (|max score| >= {REQUIRED_ITEM_MIN_ABS_SCORE})"
    )
    lines.append("-" * 60)
    lines.append(
        f"  {req['passed']} of {req['total']} passed"
        + ("" if req["rate"] is None else f"  ({req['rate']})")
    )
    if not req["agrees_with_payload"]:
        # Recomputed here and written by the grader there. If they part company
        # the report has two answers to one question, and saying so is the only
        # honest thing to print.
        lines.append(
            f"  !! recount disagrees with the run's own "
            f"{req['payload_rate']} — do not quote either until it is settled"
        )
    if req["score_excluded"]:
        lines.append(
            f"  not scored              {req['score_excluded']} item(s) the "
            "grader excluded, kept out of the denominator"
        )
    if req["unscorable"]:
        lines.append(
            f"  unscorable              {req['unscorable']} counted item(s) "
            "carry no model_did_right"
        )
    if req["penalty_items"]:
        lines.append(
            f"  penalties               {req['penalty_items']} item(s) with a "
            f"negative maximum, {req['penalty_items_fired']} of them fired"
        )
    legacy = req["legacy_verdict_pass"]
    if legacy["disagreements"]:
        lines.append(
            f"  retired 'verdict == pass' spelling would say "
            f"{legacy['passed']} of {legacy['total']} ({legacy['rate']}), "
            f"differing on {legacy['disagreements']} item(s)"
        )
    if req["by_verdict"]:
        verdicts = ", ".join(f"{n} {v}" for v, n in req["by_verdict"].items())
        lines.append(f"  verdicts                {verdicts}")
    for entry in req["recurring_criteria"]:
        lines.append(
            f"  {entry['passed']:3d}/{entry['tasks']:<3d} passed  ·  "
            f"{entry['criterion'][:66]}"
        )
    lines.append("")

    scores = report["scores"]
    lines.append("Scores")
    lines.append("-" * 60)
    lines.append(
        f"  graded {scores['graded_tasks']} task(s), "
        f"{scores['error_tasks']} in error; "
        f"{scores['perfect_count']} perfect, "
        f"{scores['partial_count']} partial, {scores['zero_count']} zero"
    )
    lines.append(f"  rubric item coverage    {scores['rubric_item_coverage_avg']}")
    lines.append(f"  judge pass rate         {scores['judge_pass_rate']}")
    for sector, block in (scores["by_sector"] or {}).items():
        lines.append(
            f"    {sector:<52} {block.get('avg_pct')}%  "
            f"n={block.get('task_count')}"
        )
    lines.append("")

    occupations = scores["by_occupation"] or {}
    if occupations:
        lines.append(f"By occupation ({len(occupations)})")
        lines.append("-" * 60)
        for name, block in sorted(
            occupations.items(),
            key=lambda pair: (
                pair[1]["avg_pct"] is None,
                pair[1]["avg_pct"],
                pair[0],
            ),
        ):
            pct = "  n/a" if block["avg_pct"] is None else f"{block['avg_pct']:6.2f}"
            lines.append(
                f"  {pct}%  n={block['task_count']:<3d}  "
                f"required {block['required_passed']}/{block['required_items']}"
                f"  ·  {name[:44]}"
            )
        lines.append("")

    subsets = report["subsets"]
    lines.append("Subsets")
    lines.append("-" * 60)
    lines.extend(_render_subset("the same thirty stage 1 graded", subsets["stage_one_same_thirty"]))
    lines.extend(_render_subset("the five declared input limits", subsets["known_limits_only"]))
    lines.extend(_render_subset("everything but those five", subsets["without_known_limits"]))
    lines.append("")

    usage = report["usage"]
    lines.append("Usage")
    lines.append("-" * 60)
    lines.append(
        f"  judge calls             {usage['total_judge_calls']} "
        f"({usage['total_main_judge_calls']} main, "
        f"{usage['total_perception_calls']} perception)"
    )
    for modality, calls in (usage["perception_calls_by_modality"] or {}).items():
        lines.append(f"    {modality:<20} {calls}")
    if not usage["perception_calls_by_modality"]:
        lines.append("    (no perception call was made)")
    lines.append(
        f"  main tokens             in {usage['main_input_tokens']}, "
        f"out {usage['main_output_tokens']}, "
        f"cached {usage['main_cached_tokens']}"
    )
    lines.append(
        f"  perception tokens       in {usage['perception_input_tokens']}, "
        f"out {usage['perception_output_tokens']}"
    )
    lines.append(f"  judge latency (total)   {usage['total_judge_latency_sec']}s")
    lines.append(f"  usage complete          {usage['usage_complete']}")
    lines.append("")

    bill = report["bill"]
    lines.append("Bill")
    lines.append("-" * 60)
    if bill["pricing_complete"]:
        lines.append(f"  estimated cost          ${bill['estimated_cost_usd']}")
    else:
        # Never render an unpriced run as zero. A model with no published price
        # makes the total unknown, and unknown is not free.
        lines.append(
            "  estimated cost          UNKNOWN — not every model used has a "
            "published price"
        )
        lines.append(f"  unpriced models         {bill['unpriced_models']}")
    lines.append("")

    lines.append("Per task (worst first)")
    lines.append("-" * 60)
    for row in report["per_task"]:
        pct = "  n/a" if row["pct"] is None else f"{row['pct']:6.2f}"
        awarded = "?" if row["total_awarded"] is None else f"{row['total_awarded']:.2f}"
        maximum = "?" if row["total_max"] is None else f"{row['total_max']:.0f}"
        lines.append(
            f"  {row['task_id']}  {pct}%  {awarded}/{maximum}"
            f"  ·  {(row['occupation'] or 'occupation unrecorded')[:44]}"
        )
        notes = [
            f"{row['items_below_full_marks']}/{row['items']} item(s) below max",
            "loss unrecorded"
            if row["points_lost"] is None
            else f"-{row['points_lost']} point(s)",
        ]
        if row["critical_fail"]:
            notes.append("required item failed")
        if row["selection_status"] and row["selection_status"] != "ok":
            notes.append(f"selection {row['selection_status']}")
        if row["error"]:
            notes.append(f"ERROR {str(row['error'])[:60]}")
        lines.append(f"      {', '.join(notes)}")
    lines.append("")

    short = report["shortfalls"]
    lines.append("Shortfalls")
    lines.append("-" * 60)
    lines.append(
        f"  {short['below_full_marks']} of {short['graded_items']} rubric item(s) "
        f"scored below their maximum, losing {short['total_points_lost']} point(s)"
    )
    if short["tasks_failing_a_required_item"]:
        failed = short["tasks_failing_a_required_item"]
        lines.append(f"  required item failed in {len(failed)} task(s):")
        lines.extend(_wrapped_ids(failed))
    if short["tasks_with_errors"]:
        lines.append(f"  tasks in error: {len(short['tasks_with_errors'])}")
        for row in short["tasks_with_errors"]:
            lines.append(f"      {row['task_id']}  {row['error']}")
    lines.append("")

    for row in short["items"][:shortfall_limit]:
        lines.append(
            f"  -{row['lost']} of {row['max_score']}  "
            f"[{row['verdict']}, {row['routing_modality']}, "
            f"decided by {row['decided_by']}]  {row['task_id']}"
        )
        lines.extend(_labelled_prose("criterion", row["criterion"], budget=300))
        lines.extend(_labelled_prose("evidence", row["evidence"], budget=400))
        if row["selection_status"] != "ok":
            lines.extend(
                _labelled_prose(
                    "selection",
                    f"{row['selection_status']}: {row['selection_error']}",
                    budget=300,
                )
            )
    remaining = len(short["items"]) - shortfall_limit
    if remaining > 0:
        lines.append(f"  ... and {remaining} more (use --json for all of them)")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("grade_file", type=Path, help="merged grade payload JSON")
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit the whole analysis as JSON instead of a readable report",
    )
    parser.add_argument(
        "--shortfall-limit",
        type=int,
        default=40,
        help="how many below-maximum items to print in the readable report",
    )
    parser.add_argument(
        "--allow-any-run",
        action="store_true",
        help=(
            "skip the check that this payload is one of the pinned corpora, "
            "fully graded. Use to look inside a single shard, never for a "
            "number a report will quote"
        ),
    )
    args = parser.parse_args(argv)

    payload = json.loads(args.grade_file.read_text(encoding="utf-8"))

    if not args.allow_any_run:
        problems = _identity_problems(payload)
        if problems:
            raise NotTheRunThatWasPinned(
                f"{args.grade_file} is not a pinned corpus, fully graded:\n  - "
                + "\n  - ".join(problems)
                + "\nPass --allow-any-run to read it anyway."
            )

    report = analyze(payload)

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(_render(report, shortfall_limit=args.shortfall_limit))

    return 0 if report["all_gates_met"] else 1


if __name__ == "__main__":
    sys.exit(main())
