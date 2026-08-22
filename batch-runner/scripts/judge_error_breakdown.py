#!/usr/bin/env python3
"""Break a grade run's judge errors down by cause, and compare two runs.

``judge_error_rate`` is already published in every grade file's
``summary.wow``, and every downstream card carries a ``< 2%`` gate on it. The
rate alone is not enough to decide anything, because the errors it counts come
from two unlike places:

* the harness could not put the deliverable in front of the judge -- the
  selector refused to choose between same-format files (``#190``), or a
  document had no render target (``#189``). These are our defects, and fixing
  them is what makes the number move.
* the model did not submit gradeable work -- wrong format, or nothing at all.
  These are findings about the model under test. They are supposed to be
  there, and driving them to zero would mean grading something the model never
  produced.

A run whose rate falls because we fixed the first kind has genuinely improved.
A run whose rate falls because the corpus happened to contain fewer of the
second kind has not. Reading only the headline rate cannot tell those apart,
so this prints the split.

The second reason to have this is that **a shard's rate is not the run's
rate**, and they differ by a lot. On the published sol-220 run the whole-run
rate is 3.19%, while its nine shards range from 0.40% to 9.71% -- the 243
selector failures sit almost entirely in four of them, and shard 0 has none at
all. Comparing a canary shard against a whole-run baseline would therefore
flatter or damn a fix for reasons that have nothing to do with the fix. Pass
``--baseline`` and the comparison is paired: shard 0 against shard 0, over the
same tasks.

Stdlib only, deliberately, as with ``sweep_stalled_shard_relays.py``: a tool
for reading how a paid run went should not need the stack that ran it.

Run it from ``batch-runner/``::

    # one run, or one shard directory
    python3 scripts/judge_error_breakdown.py ../data/grades/_shards/<stem>

    # paired against the published baseline, gated at 2%
    python3 scripts/judge_error_breakdown.py ../data/grades/_shards/<new> \\
        --baseline ../data/grades/_shards/<old> --max-rate 0.02
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence


# Ordered worst-first for display. The two ``harness`` buckets are ours to fix;
# the two ``model`` ones are results, not defects.
HARNESS_BUCKETS = ("selector_ambiguous", "render_target_missing")
MODEL_BUCKETS = ("wrong_format", "empty_output")
BUCKETS = HARNESS_BUCKETS + MODEL_BUCKETS + ("unclassified",)

BUCKET_HELP = {
    "selector_ambiguous": "harness: selector could not choose between candidates",
    "render_target_missing": "harness: nothing could be rendered for the judge to see",
    "wrong_format": "model: submitted files, none in a requested format",
    "empty_output": "model: submitted no gradeable text",
    "unclassified": "UNKNOWN -- a failure shape this tool does not recognise",
}


def canonical_rate(numerator: int, denominator: int) -> float:
    """Return a nonnegative ratio rounded half-up to four decimal places.

    Copied from ``core.grade_payload.canonical_rate`` rather than imported, to
    keep this script free of the grading stack. Held to the original by
    ``test_the_borrowed_rate_still_matches_grade_payload``. The copy matters
    because the rounding is half-up integer arithmetic, not Python's
    round-half-to-even -- a reimplementation using ``round()`` would disagree
    with the published field on exact ties and look like a data error.
    """
    if denominator <= 0:
        return 0.0
    scaled = (2 * numerator * 10_000 + denominator) // (2 * denominator)
    return scaled / 10_000


def classify_error(item: dict) -> str:
    """Return which bucket one ``judge_error`` item belongs to.

    Decided from the structured fields the grader already writes, not from the
    ``evidence`` prose. Prose was the obvious route -- the reason usually
    appears as the first token of the evidence string -- and it is wrong twice
    over: it scatters one cause across several spellings (the published run
    files the same render failure under three different prefixes), and it
    silently rebuckets everything the day someone rewords a message.

    Anything that matches no known shape returns ``unclassified`` rather than
    being folded into the nearest bucket. A new failure mode should be visible
    as a new failure mode, not absorbed into an existing count -- absorbing it
    is how a regression gets reported as an improvement.
    """
    status = item.get("selection_status")
    if status == "selection_error":
        return "selector_ambiguous"
    if status == "wrong_format_primary":
        return "wrong_format"
    if status != "ok":
        return "unclassified"

    # Selection succeeded, so the failure is downstream of it. What separates
    # the two remaining causes is what the judge was routed to look at.
    modality = item.get("routing_modality")
    provenance = item.get("visual_provenance")
    rendered = bool(provenance) if isinstance(provenance, list) else provenance is not None
    if modality in ("visual", "mixed") and not rendered:
        return "render_target_missing"
    if modality == "text":
        return "empty_output"
    return "unclassified"


@dataclass
class Breakdown:
    """Judge-error accounting for one grade file, or a set of them."""

    label: str
    judge_items: int = 0
    errors: int = 0
    buckets: dict = field(default_factory=lambda: {name: 0 for name in BUCKETS})
    tasks: int = 0
    # Rate as the file itself published it, where there is one to compare with.
    published_rate: float | None = None

    @property
    def rate(self) -> float:
        return canonical_rate(self.errors, self.judge_items)

    @property
    def harness_errors(self) -> int:
        return sum(self.buckets[name] for name in HARNESS_BUCKETS)

    @property
    def model_errors(self) -> int:
        return sum(self.buckets[name] for name in MODEL_BUCKETS)

    def merge(self, other: "Breakdown") -> None:
        self.judge_items += other.judge_items
        self.errors += other.errors
        self.tasks += other.tasks
        for name in BUCKETS:
            self.buckets[name] += other.buckets[name]


def breakdown_payload(payload: dict, label: str) -> Breakdown:
    """Account for one grade payload.

    ``judge_items`` counts items decided by the judge, matching the definition
    ``core.grade_payload`` validates the published rate against. Precheck-
    decided items are excluded there and are excluded here, so the denominator
    is the same one.
    """
    result = Breakdown(label=label)
    tasks = payload.get("tasks")
    if not isinstance(tasks, list):
        raise ValueError(f"{label} has no tasks array")
    result.tasks = len(tasks)
    for task in tasks:
        if not isinstance(task, dict):
            raise ValueError(f"{label} has a task that is not an object")
        for item in task.get("items") or []:
            if not isinstance(item, dict) or item.get("decided_by") != "judge":
                continue
            result.judge_items += 1
            if item.get("verdict") != "judge_error":
                continue
            result.errors += 1
            result.buckets[classify_error(item)] += 1

    summary = payload.get("summary")
    if isinstance(summary, dict):
        wow = summary.get("wow")
        if isinstance(wow, dict) and isinstance(
            wow.get("judge_error_rate"), (int, float)
        ):
            result.published_rate = float(wow["judge_error_rate"])
    return result


def grade_files(path: Path) -> list[Path]:
    """Return the grade files under ``path``, newest-format first.

    A directory is read as a shard stem: every ``shard-*.json`` in it, in shard
    order, plus any final merged file. A file is read as itself.
    """
    if path.is_file():
        return [path]
    if not path.is_dir():
        raise ValueError(f"not a grade file or directory: {path}")
    shards = sorted(path.glob("shard-*.json"))
    finals = sorted(p for p in path.glob("*.json") if not p.name.startswith("shard-"))
    found = shards + finals
    if not found:
        raise ValueError(f"no grade files under {path}")
    return found


def read_breakdowns(paths: Sequence[Path]) -> list[Breakdown]:
    out: list[Breakdown] = []
    for path in paths:
        for file_path in grade_files(path):
            payload = json.loads(file_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError(f"{file_path} top-level JSON must be an object")
            out.append(breakdown_payload(payload, file_path.name))
    return out


def total_of(parts: Iterable[Breakdown], label: str = "ALL") -> Breakdown:
    total = Breakdown(label=label)
    for part in parts:
        total.merge(part)
    return total


def _row(entry: Breakdown, width: int) -> str:
    return (
        f"{entry.label[:width]:<{width}} {entry.tasks:>5} {entry.judge_items:>7} "
        f"{entry.errors:>5} {entry.rate * 100:>6.2f}%"
        + "".join(f" {entry.buckets[name]:>5}" for name in BUCKETS)
    )


def render(parts: list[Breakdown], total: Breakdown, width: int) -> list[str]:
    header = (
        f"{'file':<{width}} {'tasks':>5} {'judged':>7} {'errs':>5} {'rate':>7}"
        + "".join(f" {name[:5]:>5}" for name in BUCKETS)
    )
    lines = [header, "-" * len(header)]
    lines += [_row(part, width) for part in parts]
    if len(parts) > 1:
        lines += ["-" * len(header), _row(total, width)]
    lines.append("")
    lines.append("buckets:")
    for name in BUCKETS:
        lines.append(f"  {name[:5]:<5}  {name:<22}  {BUCKET_HELP[name]}")
    return lines


def compare(new: Breakdown, old: Breakdown) -> list[str]:
    """Render a paired before/after, keeping the two causes apart."""
    lines = [
        "",
        f"paired comparison  ({old.label} -> {new.label})",
        "-" * 58,
        f"  judged items      {old.judge_items:>7} -> {new.judge_items:>7}",
        f"  judge errors      {old.errors:>7} -> {new.errors:>7}",
        f"  rate              {old.rate * 100:>6.2f}% -> {new.rate * 100:>6.2f}%",
        f"  harness-caused    {old.harness_errors:>7} -> {new.harness_errors:>7}"
        f"   <- ours to fix; this is the number a fix should move",
        f"  model-caused      {old.model_errors:>7} -> {new.model_errors:>7}"
        f"   <- a property of the submissions, not a defect",
    ]
    if old.judge_items != new.judge_items:
        lines.append(
            f"  NOTE: the denominators differ ({old.judge_items} vs "
            f"{new.judge_items}), so these are not the same items. Check that "
            "you are comparing the same shard index of the same corpus."
        )
    return lines


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Break a grade run's judge errors down by cause."
    )
    parser.add_argument(
        "paths", nargs="+", type=Path, help="grade file(s) or shard directory"
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=None,
        help="a second run to compare against, paired by totals",
    )
    parser.add_argument(
        "--max-rate",
        type=float,
        default=None,
        help="fail if the overall judge_error rate is above this (e.g. 0.02)",
    )
    args = parser.parse_args(argv)

    try:
        parts = read_breakdowns(args.paths)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    width = max([len(part.label) for part in parts] + [20])
    width = min(width, 46)
    total = total_of(parts)
    lines = render(parts, total, width)

    # A published rate that disagrees with the recomputed one means this tool
    # and the grader do not count the same things. Say so rather than quietly
    # reporting a number nobody else would get.
    for part in parts:
        if part.published_rate is not None and part.published_rate != part.rate:
            lines.append(
                f"  WARNING: {part.label} publishes judge_error_rate="
                f"{part.published_rate} but recomputes to {part.rate}"
            )

    exit_code = 0
    if args.baseline is not None:
        try:
            baseline = total_of(read_breakdowns([args.baseline]), label="baseline")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"error reading baseline: {exc}", file=sys.stderr)
            return 2
        lines += compare(total, baseline)

    if total.buckets["unclassified"]:
        lines.append("")
        lines.append(
            f"  {total.buckets['unclassified']} item(s) matched no known failure "
            "shape. Do not read the split as complete until they are explained."
        )
        exit_code = 1

    if args.max_rate is not None:
        verdict = "OK" if total.rate <= args.max_rate else "OVER"
        lines.append("")
        lines.append(
            f"  gate: {total.rate * 100:.2f}% vs {args.max_rate * 100:.2f}% -> {verdict}"
        )
        if total.rate > args.max_rate:
            exit_code = 1

    print("\n".join(lines))
    return exit_code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
