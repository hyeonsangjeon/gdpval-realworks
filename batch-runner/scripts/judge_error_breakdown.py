#!/usr/bin/env python3
"""Break a grade run's judge errors down by cause, and compare two runs.

``judge_error_rate`` is already published in every grade file's
``summary.wow``, and every downstream card carries a ``< 2%`` gate on it. The
rate alone is not enough to decide anything, because the errors it counts come
from three unlike places:

* the harness could not put the deliverable in front of the judge -- the
  selector refused to choose between same-format files (``#190``), or a
  document had no render target (``#189``). These are our defects, and fixing
  them is what makes the number move.
* the judge was shown the work and did not answer -- empty final text, output
  that would not parse, an envelope that would not validate. That is the
  grading model misbehaving, usually against a token cap. It is noise: it
  varies run to run over identical input, so a change in it is not a result.
* the model under test did not submit gradeable work -- it wrote files but
  none in a requested format, or it produced nothing at all and the pipeline
  left a ``failed_to_generate.txt`` placeholder where the deliverable should
  have been. This is a finding about the model. It is supposed to be there,
  and driving it to zero would mean grading something the model never
  produced.

A run whose rate falls because we fixed the first kind has genuinely improved.
A run whose rate moves because the judge flaked a different number of times,
or because the corpus happened to contain fewer of the third kind, has not.
Reading only the headline rate cannot tell those apart, so this prints the
split.

The second reason to have this is that **a shard's rate is not the run's
rate**, and they differ by a lot. On the published sol-220 run the whole-run
rate is 3.19%, while its nine shards range from 0.40% to 9.71% -- the 243
selector failures sit almost entirely in four of them, and shard 0 has none at
all. Comparing a canary shard against a whole-run baseline would therefore
flatter or damn a fix for reasons that have nothing to do with the fix.

``--baseline`` closes that off by construction: both sides are cut down to the
task ids they share before anything is counted. That also makes it usable
while a run is still in flight, when the new side has published thirteen tasks
and the baseline has all two hundred and twenty.

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
from pathlib import Path, PurePosixPath
from typing import Iterable, Sequence


# Ordered worst-first for display. The ``harness`` buckets are ours to fix; the
# ``judge`` one is the grading LLM failing to answer; the ``model`` one is a
# result, not a defect.
HARNESS_BUCKETS = ("selector_ambiguous", "render_target_missing")
JUDGE_BUCKETS = ("judge_no_verdict",)
MODEL_BUCKETS = ("wrong_format", "nothing_submitted")
BUCKETS = HARNESS_BUCKETS + JUDGE_BUCKETS + MODEL_BUCKETS + ("unclassified",)

BUCKET_HELP = {
    "selector_ambiguous": "harness: selector could not choose between candidates",
    "render_target_missing": "harness: nothing could be rendered for the judge to see",
    "judge_no_verdict": "judge: the grading model returned no usable verdict",
    "wrong_format": "model: submitted files, none in a requested format",
    "nothing_submitted": "model: produced nothing; a placeholder stands in",
    "unclassified": "UNKNOWN -- a failure shape this tool does not recognise",
}

# What the pipeline writes in place of a deliverable when inference produced no
# file at all. Named here rather than matched loosely, because the string also
# appears as a ``target_id`` and both spellings have to mean the same thing.
PLACEHOLDER_TARGET = "failed_to_generate"


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


def _is_placeholder_name(name: str) -> bool:
    """True for a target or path that names the no-output placeholder.

    One predicate covers both spellings: the selector names the target
    ``failed_to_generate`` and the path ``.../failed_to_generate.txt``.
    """
    return PurePosixPath(str(name)).name.lower().startswith(PLACEHOLDER_TARGET)


def _submitted_nothing(item: dict) -> bool:
    """True when *everything* selected for grading is the no-output placeholder.

    Every name has to be a placeholder, not merely one of them. A task graded
    with ``target_scope: split_children`` puts each child in this list, so a
    two-child task that produced one real file and one placeholder would, under
    an any-match rule, be reported as having submitted nothing -- when in fact
    half of it arrived and deserves to be judged. ``scripts/selection-outcome.mjs``
    settled on the same all-match rule for the dashboard's task-level split; the
    two answers to "was anything submitted?" should not be allowed to disagree.

    Read across ``target_ids`` and ``selected_paths`` together, since an item
    may carry either list alone. No names at all is not a blank submission --
    it is an item we cannot speak for, and it falls through to the other rules.
    """
    names = [
        name
        for key in ("target_ids", "selected_paths")
        if isinstance(item.get(key), list)
        for name in item[key]
    ]
    return bool(names) and all(_is_placeholder_name(name) for name in names)


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

    # Before asking what the judge was shown, ask whether there was anything to
    # show. When inference produces no file, the pipeline leaves a
    # ``failed_to_generate.txt`` placeholder, and the selector passes some of
    # those through as ``ok`` -- 8 of the published 220 tasks are placeholders,
    # 2 of them selected cleanly. A visual rubric item then finds a text stub
    # where a document should be and reports no render target, which reads as a
    # renderer defect. It is not: nothing was submitted. Blaming the harness for
    # a file the model never wrote is the same mistake as the old
    # ``empty_output`` bucket, one step earlier in the pipeline.
    if _submitted_nothing(item):
        return "nothing_submitted"

    # Selection succeeded, so the failure is downstream of it. What separates
    # the two remaining causes is what the judge was routed to look at.
    modality = item.get("routing_modality")
    provenance = item.get("visual_provenance")
    rendered = bool(provenance) if isinstance(provenance, list) else provenance is not None
    if modality in ("visual", "mixed") and not rendered:
        return "render_target_missing"
    if modality == "text":
        # Selection succeeded and the text was put in front of the judge, so
        # what failed is the judge's own answer: it returned empty text, or
        # text that would not parse, or an envelope that did not validate
        # (``core.tool_calling_judge._finalization_retry_reason``). Every
        # instance in both the published run and the rerun is one of those.
        # This was originally called ``empty_output`` and filed under the
        # model, which read as a finding about the submission when it is
        # really grading-side flakiness -- mostly a token cap.
        return "judge_no_verdict"
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
    # The same accounting, per task, so a partial run can be paired against the
    # same tasks in a complete one. Kept from the single parse rather than
    # re-read, because a nine-shard corpus is tens of megabytes.
    per_task: dict = field(default_factory=dict)

    @property
    def rate(self) -> float:
        return canonical_rate(self.errors, self.judge_items)

    @property
    def harness_errors(self) -> int:
        return sum(self.buckets[name] for name in HARNESS_BUCKETS)

    @property
    def judge_side_errors(self) -> int:
        return sum(self.buckets[name] for name in JUDGE_BUCKETS)

    @property
    def model_errors(self) -> int:
        return sum(self.buckets[name] for name in MODEL_BUCKETS)

    def merge(self, other: "Breakdown") -> None:
        self.judge_items += other.judge_items
        self.errors += other.errors
        self.tasks += other.tasks
        for name in BUCKETS:
            self.buckets[name] += other.buckets[name]
        # A task claimed by two files is not a merge, it is a double count.
        # Shard slices are disjoint by construction, so this means either the
        # slicing broke or a merged final was read alongside the shards it was
        # merged from -- and silently adding those together would report every
        # number at twice its true value.
        clashes = sorted(set(self.per_task) & set(other.per_task))
        if clashes:
            raise ValueError(
                f"{other.label} repeats {len(clashes)} task(s) already counted, "
                f"first {clashes[0]!r}. Read the shards or the merged final, "
                "not both."
            )
        self.per_task.update(other.per_task)

    def restrict(self, task_ids, label: str | None = None) -> "Breakdown":
        """Return the same accounting over only ``task_ids``.

        ``published_rate`` is dropped: the file published a rate for all of its
        tasks, and it is not the rate of a subset of them.
        """
        out = Breakdown(label=self.label if label is None else label)
        for task_id, part in self.per_task.items():
            if task_id in task_ids:
                out.merge(part)
        return out


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
    for index, task in enumerate(tasks):
        if not isinstance(task, dict):
            raise ValueError(f"{label} has a task that is not an object")
        task_id = task.get("task_id")
        if not isinstance(task_id, str) or not task_id.strip():
            # Legacy files predate the field. Give it a key that cannot
            # collide and cannot pair, rather than refusing to read the file:
            # an unpairable task is honest, a crash here is not.
            task_id = f"{label}#{index}"

        one = Breakdown(label=task_id, tasks=1)
        for item in task.get("items") or []:
            if not isinstance(item, dict) or item.get("decided_by") != "judge":
                continue
            one.judge_items += 1
            if item.get("verdict") != "judge_error":
                continue
            one.errors += 1
            one.buckets[classify_error(item)] += 1
        if task_id in result.per_task:
            raise ValueError(f"{label} lists task {task_id!r} more than once")
        result.per_task[task_id] = one
        result.merge(one)

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
        f"  tasks in both     {old.tasks:>7}",
        f"  judged items      {old.judge_items:>7} -> {new.judge_items:>7}",
        f"  judge errors      {old.errors:>7} -> {new.errors:>7}",
        f"  rate              {old.rate * 100:>6.2f}% -> {new.rate * 100:>6.2f}%",
        f"  harness-caused    {old.harness_errors:>7} -> {new.harness_errors:>7}"
        f"   <- ours to fix; this is the number a fix should move",
        f"  judge-side        {old.judge_side_errors:>7} -> {new.judge_side_errors:>7}"
        f"   <- the grading model not answering; noise, not signal",
        f"  model-caused      {old.model_errors:>7} -> {new.model_errors:>7}"
        f"   <- a property of the submissions, not a defect",
    ]
    if old.judge_items != new.judge_items:
        lines.append(
            f"  NOTE: the denominators differ ({old.judge_items} vs "
            f"{new.judge_items}) across the same tasks, so the rubric itself "
            "moved. A rate change here is not only about judge errors."
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
        help="a second run to compare against, cut to the task ids both share",
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

    baseline = None
    pairing: list[str] = []
    if args.baseline is not None:
        try:
            baseline = total_of(read_breakdowns([args.baseline]), label="baseline")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"error reading baseline: {exc}", file=sys.stderr)
            return 2

        # Pair on task_id. A run in flight has published some of its tasks and
        # not others, and the baseline has all of them; comparing those totals
        # measures how far along the new run is, not whether it is better.
        # Restricting both sides to the tasks they share is the only reading
        # that says anything about the fix.
        new_ids = set().union(*(set(part.per_task) for part in parts)) if parts else set()
        shared = new_ids & set(baseline.per_task)
        only_new = len(new_ids - shared)
        only_old = len(set(baseline.per_task) - shared)
        if not shared:
            print(
                f"error: the two runs share no task ids ({len(new_ids)} here, "
                f"{len(baseline.per_task)} in the baseline), so there is "
                "nothing to compare. Check that both point at the same corpus.",
                file=sys.stderr,
            )
            return 2

        parts = [part.restrict(shared) for part in parts]
        baseline = baseline.restrict(shared, label="baseline")
        if only_new or only_old:
            pairing = [
                "",
                f"paired on the {len(shared)} task(s) both runs have published."
                f" Set aside: {only_new} here, {only_old} in the baseline.",
                "The table above is restricted to those shared tasks, so it"
                " will not match either run's own published totals.",
            ]

    width = max([len(part.label) for part in parts] + [20])
    width = min(width, 46)
    total = total_of(parts)
    lines = render(parts, total, width)
    lines += pairing

    # A published rate that disagrees with the recomputed one means this tool
    # and the grader do not count the same things. Say so rather than quietly
    # reporting a number nobody else would get. Restricted parts have no
    # published rate to check against, so this only fires on a whole file.
    for part in parts:
        if part.published_rate is not None and part.published_rate != part.rate:
            lines.append(
                f"  WARNING: {part.label} publishes judge_error_rate="
                f"{part.published_rate} but recomputes to {part.rate}"
            )

    exit_code = 0
    if baseline is not None:
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
