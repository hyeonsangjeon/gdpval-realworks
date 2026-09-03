#!/usr/bin/env python3
"""Price the ways of defining a "required" rubric item, from published data.

Why this exists
---------------
GDPVal v2 rubrics carry a ``required`` field and it is ``null`` on every item
of every task -- 10,453 of 10,453, recorded in
``data/grades/_validation/SCORE_MATH_AUDIT.md``. With no author signal to read,
the repository adopted a convention: an item is required when its weight is
large, ``abs(max_score) >= MAGNITUDE_THRESHOLD``, and ``MAGNITUDE_THRESHOLD``
is 4. The comment above it says plainly that 4 is a heuristic and names the
gold-ceiling work as the thing that should decide whether it is the right
boundary. That work is finished, so the deferral has run out.

Two published numbers depend on the answer and nothing else does:

* ``summary.wow.critical_item_pass_rate`` -- one rate per run and one per
  sector, and the second of the three thresholds a gold-ceiling run is
  accepted or rejected on (``>= 0.95``).
* ``tasks[].critical_fail`` -- a per-task boolean carried in every payload and
  printed in the per-task table of ``scripts/analyze_grade_run.py``.

Neither ``pct`` nor ``total_max`` nor any headline score moves with the
definition, which bounds how much is at stake and is worth knowing before
anyone weighs the options.

What this does
--------------
It prices the options against real graded runs. For each payload it reports
the effect of every candidate threshold on both published consequences, and it
separately measures how much of the metric is spent on rubric lines the author
repeats verbatim across tasks -- because if one boilerplate line dominates the
denominator, then the "required item pass rate" is substantially a rate about
that line, whatever threshold is chosen.

What it will not do
-------------------
* **It does not change the definition.** ``MAGNITUDE_THRESHOLD`` lives in
  ``core/grader.py``, which is an input to ``compute_grader_source_hash``, and
  the decision is the owner's. This file is under ``scripts/``, outside that
  hash, and imports the threshold rather than restating it: an analysis
  counting through its own copy could disagree with the grader about what it
  was measuring at exactly the moment the disagreement mattered.
* **It does not reimplement the metric.** Every rate here comes back out of
  ``step8_grade._compute_summary`` -- the same function that wrote the numbers
  on the dashboard -- with the threshold patched underneath it. A
  reimplementation would quietly answer a different question and then agree
  with itself.
* **It refuses to price a payload it cannot reproduce.** If today's summariser
  does not land on the stored rate, the stored rate came from a rule we no
  longer run, and pricing a change against it would compare two definitions
  while claiming to compare one. ``scripts/summary_wow_drift.py`` already
  names the two historical causes; this defers to it rather than guessing.
* **It refuses to report a rate its denominator cannot carry.** A threshold
  that leaves no items at all gets ``n/a`` and not ``0.0000``, in every cell
  of every table here -- dividing nothing by nothing is not a score of zero,
  and zero is the worst value this rate can take. A threshold that leaves a
  handful gets its real rate plus a note that it is too thin to decide on.
  The two are annotated differently because they are different answers; see
  ``MIN_USABLE_CRITICAL_ITEMS`` below.

Usage
-----
    python batch-runner/scripts/analyze_required_item_definition.py <grade.json>...
    python batch-runner/scripts/analyze_required_item_definition.py <dir>
    python batch-runner/scripts/analyze_required_item_definition.py <dir> --repeat-floor 0.05

Exit status is 0 when every input was priced and 1 when any was refused, so a
report generated over a payload this could not read cannot come out green.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter, defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

# The report's generated blocks run this from the repository root, where
# `batch-runner/` is not importable, so the package root goes on the path here
# rather than relying on the caller's working directory. Same reason as
# `analyze_gold_ceiling.py`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import core.grader as grader_module  # noqa: E402
from core.grader_routing import is_overall_style_criterion  # noqa: E402
from scripts.analyze_gold_ceiling import CRITICAL_ITEM_PASS_FLOOR  # noqa: E402
from scripts.summary_wow_drift import (  # noqa: E402
    CAUSE_MATCH,
    classify,
)
from step8_grade import _compute_summary  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ROOT = REPO_ROOT / "data" / "grades"

#: The shipped definition, read once before anything patches it. Imported, not
#: restated -- see the module docstring.
#:
#: ``int`` rather than ``float`` throughout, because the sweep rebinds this very
#: name inside a production module: a fractional candidate would change the type
#: of a shipped constant as well as its value, and any real change to the
#: definition would land as an integer.
SHIPPED_THRESHOLD: int = grader_module.MAGNITUDE_THRESHOLD

#: Candidate thresholds. 4 is what ships; 5 is the value the card names; the
#: rest bracket it so the shape of the curve is visible rather than two points
#: on it. Above 10 every corpus measured so far falls below the floor below.
THRESHOLD_SWEEP: tuple[int, ...] = (2, 3, 4, 5, 6, 8, 10)

#: Below this many critical items a rate is reported but refused as a basis for
#: any decision. The number is derived, not chosen: the gate this metric feeds
#: is `>= CRITICAL_ITEM_PASS_FLOOR`, so its whole margin is `1 - floor`. With
#: fewer than `1 / (1 - floor)` items a single failure costs more than that
#: entire margin, and the metric cannot express any value between the floor and
#: a clean sweep. A gold run that leaves one critical item reads 1.0000, which
#: is a real measurement of a set too small to decide on. A run that leaves
#: none is a separate state and reads `NOT_MEASURED`: there was no denominator,
#: so no rate was taken.
MIN_USABLE_CRITICAL_ITEMS: int = math.ceil(1.0 / (1.0 - CRITICAL_ITEM_PASS_FLOOR))

#: How much of a corpus a criterion has to appear in before it is reported as
#: repeated. The census itself is exhaustive; this only decides what is printed.
DEFAULT_REPEAT_TASK_SHARE = 0.10

#: Printed wherever a rate or a share has no denominator to stand on. One
#: marker for every such cell, so "no answer" never has to be inferred from a
#: number that looks like one. Not ``--``: this file already spells em-dashes
#: that way in prose.
NOT_MEASURED = "n/a"

_WHITESPACE = re.compile(r"\s+")


# ── reading the payload ──────────────────────────────────────────────


def _scored_items(task: dict) -> list[dict]:
    """The items a grade counts, matching ``core.grader._aggregate``.

    Both published consequences are defined over this set and not over every
    item: an item the judge never managed to score is excluded from the rate
    and cannot raise ``critical_fail``.
    """
    return [
        item
        for item in task.get("items", [])
        if isinstance(item, dict) and not item.get("score_excluded", False)
    ]


def _normalise(criterion: Any) -> str:
    """Fold a criterion string for the repetition census only.

    Case, surrounding space, internal runs of space and a trailing period are
    removed. Nothing else: this decides which strings are *the same line*, and
    a looser fold would merge lines the rubric author wrote differently. The
    real corpus needs exactly this much -- stage 3 carries the deliverable-wide
    style line 119 times bare and once with a full stop.
    """
    text = _WHITESPACE.sub(" ", str(criterion or "")).strip()
    return text.rstrip(".").lower()


@contextmanager
def _threshold(value: int) -> Iterator[None]:
    """Run the production summariser under a different definition.

    ``_is_critical_item`` reads ``MAGNITUDE_THRESHOLD`` from its own module at
    call time, and ``step8_grade`` imported the function rather than the
    number, so rebinding it here reprices through the real code path instead of
    a copy of it. Restored on the way out, including on an exception, because
    everything downstream of a leaked threshold would be silently wrong.
    """
    original = grader_module.MAGNITUDE_THRESHOLD
    grader_module.MAGNITUDE_THRESHOLD = value
    try:
        yield
    finally:
        grader_module.MAGNITUDE_THRESHOLD = original


# ── the measurements ─────────────────────────────────────────────────


@dataclass(frozen=True)
class ThresholdEffect:
    """What one candidate definition does to both published consequences."""

    threshold: int
    critical_items: int
    scored_items: int
    pass_rate: float | None
    critical_fail_tasks: int
    graded_tasks: int

    @property
    def item_share(self) -> float | None:
        return (self.critical_items / self.scored_items) if self.scored_items else None

    @property
    def task_share(self) -> float | None:
        return (
            (self.critical_fail_tasks / self.graded_tasks) if self.graded_tasks else None
        )

    @property
    def measured(self) -> bool:
        """Whether this threshold leaves anything to pass or fail at all.

        Separate from ``usable`` because they are different answers. A
        threshold that leaves four items produced a real rate that is too
        coarse to decide on; a threshold that leaves none produced no rate.
        Folding the second into the first reports a measurement nobody took.
        """
        return self.critical_items > 0

    @property
    def usable(self) -> bool:
        return self.critical_items >= MIN_USABLE_CRITICAL_ITEMS

    @property
    def is_shipped(self) -> bool:
        return self.threshold == SHIPPED_THRESHOLD


@dataclass(frozen=True)
class RepeatedCriterion:
    """One rubric line the author reuses, and what it costs the metric."""

    criterion: str
    variants: int
    items: int
    tasks: int
    magnitudes: tuple[float, ...]
    pass_rate: float | None

    def share_of(self, critical_items: int) -> float | None:
        return (self.items / critical_items) if critical_items else None


@dataclass
class Priced:
    """Everything measured about one grade payload."""

    path: Path
    task_count: int
    graded_tasks: int
    scored_items: int
    published_rate: float | None
    recomputed_rate: float | None
    sector_rates: int
    refusal: str | None = None
    effects: list[ThresholdEffect] = field(default_factory=list)
    repeated: list[RepeatedCriterion] = field(default_factory=list)
    repeat_floor: float = DEFAULT_REPEAT_TASK_SHARE
    text_rule_items: int = 0
    text_rule_tasks: int = 0
    text_rule_rate: float | None = None
    remainder_items: int = 0
    remainder_rate: float | None = None

    @property
    def priced(self) -> bool:
        return self.refusal is None

    def effect_at(self, threshold: int) -> ThresholdEffect | None:
        for effect in self.effects:
            if effect.threshold == threshold:
                return effect
        return None


def _rate_of(items: list[dict]) -> float | None:
    """Share of items the model did the right thing on, to 4 places.

    ``model_did_right`` rather than ``verdict == 'pass'``: GDPVal rubrics carry
    negative-weight anti-criteria where a pass verdict means the model *did*
    the prohibited thing, and the critical set spans both signs.

    ``None`` for an empty set rather than ``0.0``. ``0.0`` is the worst value
    this rate can take, so returning it for a partition nobody had anything to
    put in reports a total failure where there was no measurement -- and this
    function's output is printed beside real zeros from the same corpus.
    """
    if not items:
        return None
    right = sum(1 for item in items if bool(item.get("model_did_right", False)))
    return round(right / len(items), 4)


def _critical_fail_tasks(tasks: list[dict]) -> int:
    """Recount the published per-task boolean under the current threshold.

    Mirrors ``core.grader._aggregate``: any scored item of critical magnitude
    the model did not get right fails the task.
    """
    return sum(
        1
        for task in tasks
        if not task.get("error")
        and any(
            grader_module._is_critical_item(item.get("max_score"))
            and not bool(item.get("model_did_right", False))
            for item in _scored_items(task)
        )
    )


def _sweep(tasks: list[dict], scored_items: int, graded_tasks: int) -> list[ThresholdEffect]:
    effects: list[ThresholdEffect] = []
    for threshold in THRESHOLD_SWEEP:
        with _threshold(threshold):
            wow = _compute_summary(tasks)["wow"]
            critical = [
                item
                for task in tasks
                for item in _scored_items(task)
                if grader_module._is_critical_item(item.get("max_score"))
            ]
            effects.append(
                ThresholdEffect(
                    threshold=threshold,
                    critical_items=len(critical),
                    scored_items=scored_items,
                    pass_rate=_published_rate(wow, len(critical)),
                    critical_fail_tasks=_critical_fail_tasks(tasks),
                    graded_tasks=graded_tasks,
                )
            )
    return effects


def _published_rate(wow: dict, critical_items: int) -> float | None:
    """The summariser's rate, or ``None`` when it stands on nothing.

    ``step8_grade._rate`` returns ``0.0`` for an empty denominator and its own
    docstring calls that "a real hazard, not a formatting detail"; it is
    mitigated there by publishing ``item_counts`` beside the rates so the two
    cases can be told apart. Reading the rate out on its own discards that
    mitigation, so the count is re-applied here: at a threshold that leaves no
    critical items the summariser divided nothing by nothing, and the 0.0 it
    returned is not this corpus's answer.

    An absent or non-numeric key is ``None`` for the same reason and not
    ``0.0`` -- a payload that did not publish the rate did not publish a zero.
    """
    if critical_items <= 0:
        return None
    value = wow.get("critical_item_pass_rate")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _census(tasks: list[dict], floor: float) -> list[RepeatedCriterion]:
    """Which rubric lines the critical set is actually made of.

    Derived, not assumed. Nothing here knows what the repeated line says; it
    groups the critical items by their own text and reports whichever groups
    turn out to span a large share of the corpus. A hardcoded string would
    stop being true the first time the rubrics changed and would say nothing
    about a corpus nobody had looked at yet.
    """
    task_total = sum(1 for task in tasks if not task.get("error"))
    if not task_total:
        return []

    groups: dict[str, list[dict]] = defaultdict(list)
    owners: dict[str, set[str]] = defaultdict(set)
    variants: dict[str, Counter] = defaultdict(Counter)
    for task in tasks:
        if task.get("error"):
            continue
        task_id = str(task.get("task_id") or "")
        for item in _scored_items(task):
            if not grader_module._is_critical_item(item.get("max_score")):
                continue
            key = _normalise(item.get("criterion"))
            if not key:
                continue
            groups[key].append(item)
            owners[key].add(task_id)
            variants[key][str(item.get("criterion") or "").strip()] += 1

    out: list[RepeatedCriterion] = []
    for key, items in groups.items():
        # Two conditions, and only the second is a knob. A line has to appear
        # in more than one task before the word "repeated" means anything --
        # on a three-task smoke a single occurrence is 33% of the corpus, and
        # a share floor alone would report every criterion in the run as
        # repeated boilerplate.
        if len(owners[key]) < 2:
            continue
        if len(owners[key]) / task_total < floor:
            continue
        magnitudes = sorted(
            {
                abs(float(item.get("max_score") or 0))
                for item in items
                if isinstance(item.get("max_score"), (int, float))
            }
        )
        out.append(
            RepeatedCriterion(
                # The most common spelling, so the report quotes the rubric
                # rather than this file's folded key.
                criterion=variants[key].most_common(1)[0][0],
                variants=len(variants[key]),
                items=len(items),
                tasks=len(owners[key]),
                magnitudes=tuple(magnitudes),
                pass_rate=_rate_of(items),
            )
        )
    return sorted(out, key=lambda r: (-r.items, r.criterion))


def price(path: Path, payload: dict, *, repeat_floor: float) -> Priced | None:
    """Measure one grade payload, or refuse it and say why."""
    tasks = payload.get("tasks")
    summary = payload.get("summary")
    if not isinstance(tasks, list) or not isinstance(summary, dict):
        return None
    published = summary.get("wow")
    if not isinstance(published, dict) or "critical_item_pass_rate" not in published:
        return None

    graded = [task for task in tasks if not task.get("error")]
    scored_items = sum(len(_scored_items(task)) for task in graded)
    by_sector = published.get("by_sector")
    result = Priced(
        path=path,
        task_count=len(tasks),
        graded_tasks=len(graded),
        scored_items=scored_items,
        published_rate=published.get("critical_item_pass_rate"),
        recomputed_rate=None,
        sector_rates=len(by_sector) if isinstance(by_sector, dict) else 0,
        repeat_floor=repeat_floor,
    )

    with _threshold(SHIPPED_THRESHOLD):
        result.recomputed_rate = _compute_summary(tasks)["wow"].get(
            "critical_item_pass_rate"
        )

    # Refusal 1: the payload predates sign-aware verdicts, so the metric it
    # published was counting something this cannot reconstruct.
    if not any(
        "model_did_right" in item
        for task in tasks
        for item in task.get("items", [])
        if isinstance(item, dict)
    ):
        result.refusal = (
            "no model_did_right on any item -- pre-#100 payload, "
            "see scripts/summary_wow_drift.py"
        )
        return result

    # Refusal 2: today's summariser does not land on the stored number, so the
    # stored number came from a rule that is no longer running. Pricing a
    # change against it would compare two definitions and report one.
    finding = classify(path, payload)
    if finding is not None and finding.cause != CAUSE_MATCH:
        result.refusal = f"does not reproduce -- {finding.cause}"
        return result

    result.effects = _sweep(tasks, scored_items, len(graded))
    with _threshold(SHIPPED_THRESHOLD):
        result.repeated = _census(tasks, repeat_floor)
        critical = [
            item
            for task in graded
            for item in _scored_items(task)
            if grader_module._is_critical_item(item.get("max_score"))
        ]
    # The one concrete text rule the repository already ships and already
    # tests: `core.grader_routing.is_overall_style_criterion`, which the
    # grader uses to decide that a criterion is asking about deliverable-wide
    # polish rather than about the work. Using it here rather than inventing a
    # rule means the third option is priced against something real.
    #
    # Partitioned in one pass rather than by a second `not in` filter: rubric
    # items are plain dicts, `in` compares them by value, and two tasks
    # carrying the same boilerplate line at the same weight are equal. A
    # membership test would drop every copy of every repeated line from the
    # remainder -- which is precisely the set being measured here.
    styled: list[dict] = []
    remainder: list[dict] = []
    for item in critical:
        target = (
            styled
            if is_overall_style_criterion(str(item.get("criterion") or ""))
            else remainder
        )
        target.append(item)
    result.text_rule_items = len(styled)
    result.text_rule_tasks = len(
        {
            str(task.get("task_id") or "")
            for task in graded
            for item in _scored_items(task)
            if grader_module._is_critical_item(item.get("max_score"))
            and is_overall_style_criterion(str(item.get("criterion") or ""))
        }
    )
    result.text_rule_rate = _rate_of(styled)
    result.remainder_items = len(remainder)
    result.remainder_rate = _rate_of(remainder)
    return result


# ── reporting ────────────────────────────────────────────────────────


def _pct(value: float | None) -> str:
    return NOT_MEASURED if value is None else f"{value * 100:.1f}%"


def _rate(value: float | None, width: int = 8) -> str:
    """A rate cell. ``None`` prints the marker, never a number."""
    return f"{NOT_MEASURED:>{width}}" if value is None else f"{value:>{width}.4f}"


def _rate_phrase(value: float | None) -> str:
    """A rate in running text, where there is room to say why it is absent."""
    return "no rate (no items)" if value is None else f"rate {value:.4f}"


def render(results: list[Priced]) -> str:
    lines: list[str] = []
    lines.append(
        f"required-item definition, priced against {len(results)} payload(s)"
    )
    lines.append(
        f"shipped: abs(max_score) >= {SHIPPED_THRESHOLD:g}  "
        f"(core.grader.MAGNITUDE_THRESHOLD)"
    )
    lines.append(
        f"a rate needs >= {MIN_USABLE_CRITICAL_ITEMS} critical items to mean "
        f"anything against the {CRITICAL_ITEM_PASS_FLOOR:.2f} floor"
    )
    lines.append(
        f"{NOT_MEASURED} means there was no denominator, so no rate was taken. "
        f"It is not a zero."
    )
    lines.append("")

    for result in results:
        lines.append("=" * 72)
        lines.append(f"{result.path.name}")
        lines.append(
            f"  {result.task_count} task(s), {result.graded_tasks} graded, "
            f"{result.scored_items} scored item(s)"
        )
        if not result.priced:
            lines.append(f"  REFUSED: {result.refusal}")
            lines.append(
                f"  published critical_item_pass_rate="
                f"{result.published_rate} recomputed={result.recomputed_rate}"
            )
            lines.append("")
            continue

        lines.append(
            f"  reproduces: published={result.published_rate} "
            f"recomputed={result.recomputed_rate}"
        )
        lines.append("")
        lines.append(
            "  threshold   items    share     rate    critical_fail tasks"
        )
        for effect in result.effects:
            mark = " *" if effect.is_shipped else "  "
            # Three states, not two. A threshold that leaves a handful of items
            # measured something too coarse to decide on; a threshold that
            # leaves none measured nothing at all, and the second is not a
            # worse version of the first.
            if not effect.measured:
                note = "   [no critical items -- nothing to pass or fail]"
            elif not effect.usable:
                note = "   [denominator too thin to use]"
            else:
                note = ""
            lines.append(
                f"  {effect.threshold:>7g}{mark} {effect.critical_items:>6} "
                f"{_pct(effect.item_share):>8} {_rate(effect.pass_rate)} "
                f"{effect.critical_fail_tasks:>10} "
                f"({_pct(effect.task_share)}){note}"
            )
        lines.append("  * the shipped definition")
        lines.append("")

        if result.repeated:
            lines.append(
                f"  criteria repeated across >= {_pct(result.repeat_floor)} of "
                f"tasks, within the shipped critical set:"
            )
            shipped = result.effect_at(SHIPPED_THRESHOLD)
            total = shipped.critical_items if shipped else 0
            for repeat in result.repeated:
                variant = (
                    f", {repeat.variants} spellings" if repeat.variants > 1 else ""
                )
                mags = "/".join(f"{m:g}" for m in repeat.magnitudes)
                lines.append(
                    f"    {repeat.items:>4} item(s) in {repeat.tasks} task(s) "
                    f"({_pct(repeat.tasks / result.graded_tasks)}), "
                    f"{_pct(repeat.share_of(total))} of the critical set, "
                    f"|max|={mags}{variant}, {_rate_phrase(repeat.pass_rate)}"
                )
                lines.append(f"         {repeat.criterion!r}")
        else:
            lines.append("  no criterion repeats above the floor")
        lines.append("")

        lines.append(
            "  excluding deliverable-wide style lines "
            "(core.grader_routing.is_overall_style_criterion):"
        )
        lines.append(
            f"    excluded  {result.text_rule_items:>4} item(s) across "
            f"{result.text_rule_tasks} task(s), "
            f"{_rate_phrase(result.text_rule_rate)}"
        )
        lines.append(
            f"    remaining {result.remainder_items:>4} item(s), "
            f"{_rate_phrase(result.remainder_rate)}"
        )
        lines.append("")

        lines.append(
            f"  not publishing the metric would withdraw 1 run rate, "
            f"{result.sector_rates} sector rate(s) and "
            f"{result.graded_tasks} task boolean(s) from this payload"
        )
        lines.append("")

    refused = [r for r in results if not r.priced]
    lines.append(
        f"{len(results)} payload(s) read, {len(refused)} refused"
    )
    if refused:
        lines.append(
            "  A refused payload was not priced. Do not read a number for it "
            "off another payload's table."
        )
    return "\n".join(lines)


def collect(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_dir():
            files += [
                p
                for p in sorted(path.rglob("*.json"))
                if "_validation" not in p.parts
            ]
        elif path.is_file():
            files.append(path)
    return files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        default=[DEFAULT_ROOT],
        help="grade files or directories to price (default: data/grades)",
    )
    parser.add_argument(
        "--repeat-floor",
        type=float,
        default=DEFAULT_REPEAT_TASK_SHARE,
        help=(
            "report criteria repeated across at least this share of tasks "
            f"(default {DEFAULT_REPEAT_TASK_SHARE})"
        ),
    )
    args = parser.parse_args(argv)

    results: list[Priced] = []
    for path in collect(args.paths):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(payload, dict):
            continue
        priced = price(path, payload, repeat_floor=args.repeat_floor)
        if priced is not None:
            results.append(priced)

    if not results:
        print("no grade payloads with a critical_item_pass_rate found")
        return 0

    print(render(results))
    return 1 if any(not r.priced for r in results) else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
