#!/usr/bin/env python3
"""Recompute every published ``summary.wow`` rate and account for what differs.

A grade file carries two things that are supposed to agree: the rubric items
the judge produced, and the five headline rates in ``summary.wow`` computed
from them. The rates are written once, by whatever the summariser was on the
day the run finished, and are never revisited afterwards -- ``#188`` backfilled
the by-sector, histogram and severity blocks into the older files deliberately
*without* republishing the rates, so that no number anyone had already cited
moved underneath them.

That is the right call, and it has a consequence: a grade file stops being
self-consistent the moment the summariser's counting rule changes. The stored
rate and a fresh recompute of the same frozen items then disagree, and neither
is wrong on its own terms -- one is what we published, the other is what the
rule says today. What is not acceptable is not knowing which rule produced a
given number, because then a rate cannot be compared with any other rate.

So this does not "fix" anything and never writes to a payload. It recomputes
each file with the production summariser, and where that disagrees with what
is stored it tries to reproduce the stored value with each summariser rule we
have actually shipped. A file that matches one of them is explained. A file
that matches none is the only interesting output here, and the only thing that
sets a nonzero exit code.

The two rules that are not the current one:

``pre-#69``
    Before ``6ad789a`` the item loop had no ``score_excluded`` gate at all.
    Judge errors -- items the judge never managed to score -- were counted in
    every denominator as though the model had failed them. ``#69`` added the
    gate, which shrinks ``all_items`` and ``critical_items`` and therefore
    moves ``rubric_item_coverage_avg`` *up* and, because the numerator loses
    items too, ``critical_item_pass_rate`` *down*.

``pre-#100``
    Before ``240b860`` there was no ``model_did_right`` on an item at all, so
    ``critical_item_pass_rate`` was taken from the raw verdict. Those files are
    the four ``__v1.json`` payloads and their drift is a separate story from
    the one above; they are reported under their own cause so the two never get
    added together.

Imports the real ``step8_grade._compute_summary`` rather than reimplementing
it. The question being asked is whether the *production* summariser reproduces
a published file, and a reimplementation would quietly answer a different
question -- it would agree with itself.

Run it from ``batch-runner/``::

    python3 scripts/summary_wow_drift.py                  # whole corpus
    python3 scripts/summary_wow_drift.py ../data/grades/<one file>.json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

BATCH_RUNNER_ROOT = Path(__file__).resolve().parent.parent
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core.grader import _is_critical_item  # noqa: E402
from step8_grade import _compute_summary  # noqa: E402

DEFAULT_ROOT = BATCH_RUNNER_ROOT.parent / "data" / "grades"

WOW_RATES = (
    "rubric_item_coverage_avg",
    "critical_item_pass_rate",
    "precheck_pass_rate",
    "judge_pass_rate",
    "judge_error_rate",
)

CAUSE_MATCH = "reproduces"
CAUSE_PRE_69 = "pre-#69 summariser (no score_excluded gate)"
CAUSE_PRE_100 = "pre-#100 payload (no model_did_right on items)"
CAUSE_UNKNOWN = "UNEXPLAINED"


def iter_items(tasks: list[dict]):
    for task in tasks:
        for item in task.get("items", []):
            if isinstance(item, dict):
                yield item


def pre_69_wow(tasks: list[dict]) -> dict[str, float]:
    """``_compute_summary``'s item loop as it stood before ``6ad789a`` (#69).

    Transcribed from that revision rather than derived: no ``score_excluded``
    anywhere, and ``round(x, 4)`` on every rate including ``judge_error_rate``,
    which only later moved to the half-up ``canonical_rate``.
    """
    all_items = all_pass = 0
    pre_items = pre_pass = 0
    judge_items = judge_pass = judge_errors = 0
    critical_items = critical_pass = 0

    for item in iter_items(tasks):
        verdict = item.get("verdict")
        all_items += 1
        if verdict == "pass":
            all_pass += 1
        if item.get("decided_by") == "precheck":
            pre_items += 1
            if verdict == "pass":
                pre_pass += 1
        if item.get("decided_by") == "judge":
            judge_items += 1
            if verdict == "pass":
                judge_pass += 1
            if verdict == "judge_error":
                judge_errors += 1
        if _is_critical_item(item.get("max_score")):
            critical_items += 1
            if bool(item.get("model_did_right", False)):
                critical_pass += 1

    def rate(numerator: int, denominator: int) -> float:
        return round((numerator / denominator) if denominator else 0.0, 4)

    return {
        "rubric_item_coverage_avg": rate(all_pass, all_items),
        "critical_item_pass_rate": rate(critical_pass, critical_items),
        "precheck_pass_rate": rate(pre_pass, pre_items),
        "judge_pass_rate": rate(judge_pass, judge_items),
        "judge_error_rate": rate(judge_errors, judge_items),
    }


@dataclass
class Finding:
    path: Path
    task_count: int
    drift: tuple[str, ...]
    cause: str
    notes: tuple[str, ...] = ()

    @property
    def explained(self) -> bool:
        return self.cause != CAUSE_UNKNOWN


def gate_delta(tasks: list[dict]) -> tuple[str, ...]:
    """Per-counter effect of the ``score_excluded`` gate, for the report.

    This is the minimal diff: which items the two rules disagree about, and
    what that does to each numerator and denominator.
    """
    excluded = [i for i in iter_items(tasks) if i.get("score_excluded")]
    if not excluded:
        return ()
    passing = sum(1 for i in excluded if i.get("verdict") == "pass")
    critical = [i for i in excluded if _is_critical_item(i.get("max_score"))]
    right = sum(1 for i in critical if bool(i.get("model_did_right", False)))
    verdicts = sorted({str(i.get("verdict")) for i in excluded})
    return (
        f"{len(excluded)} score_excluded item(s), verdict(s)={','.join(verdicts)}",
        f"coverage: denominator -{len(excluded)}, numerator -{passing}",
        f"critical: denominator -{len(critical)}, numerator -{right}",
    )


def classify(path: Path, payload: dict) -> Finding | None:
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        return None
    published = summary.get("wow")
    if not isinstance(published, dict) or not any(k in published for k in WOW_RATES):
        return None
    tasks = payload.get("tasks")
    if not isinstance(tasks, list):
        return None

    current = _compute_summary(tasks)["wow"]
    drift = tuple(k for k in WOW_RATES if published.get(k) != current.get(k))
    if not drift:
        return Finding(path, len(tasks), (), CAUSE_MATCH)

    if all(published.get(k) == pre_69_wow(tasks).get(k) for k in WOW_RATES):
        return Finding(path, len(tasks), drift, CAUSE_PRE_69, gate_delta(tasks))

    # Deliberately not reconstructed. These predate `model_did_right`, so the
    # metric that reads it is the only one that can move, and reproducing
    # their arithmetic would invite adding their drift to the gate's.
    has_flag = any("model_did_right" in i for i in iter_items(tasks))
    if not has_flag and drift == ("critical_item_pass_rate",):
        return Finding(path, len(tasks), drift, CAUSE_PRE_100)

    return Finding(
        path,
        len(tasks),
        drift,
        CAUSE_UNKNOWN,
        tuple(
            f"{k}: published={published.get(k)} recomputed={current.get(k)}"
            for k in drift
        ),
    )


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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        default=[DEFAULT_ROOT],
        help="grade files or directories to scan (default: data/grades)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="print only files whose drift is unexplained",
    )
    args = parser.parse_args()

    findings: list[Finding] = []
    for path in collect(args.paths):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(payload, dict):
            continue
        finding = classify(path, payload)
        if finding is not None:
            findings.append(finding)

    if not findings:
        print("no grade payloads with summary.wow rates found")
        return 0

    unexplained = [f for f in findings if not f.explained]
    order = [CAUSE_UNKNOWN, CAUSE_PRE_69, CAUSE_PRE_100, CAUSE_MATCH]
    lines: list[str] = []
    for cause in order:
        group = [f for f in findings if f.cause == cause]
        if not group:
            continue
        if args.quiet and cause != CAUSE_UNKNOWN:
            continue
        lines.append(f"{cause}: {len(group)} payload(s)")
        for finding in group:
            lines.append(f"  {finding.path.name}  ({finding.task_count} tasks)")
            if finding.drift:
                lines.append(f"    drifting: {', '.join(finding.drift)}")
            for note in finding.notes:
                lines.append(f"    {note}")
        lines.append("")

    lines.append(
        f"{len(findings)} payload(s) checked, "
        f"{len(unexplained)} with unexplained drift"
    )
    if unexplained:
        lines.append(
            "  An unexplained rate cannot be compared with any other rate. "
            "Find the summariser change before citing these."
        )
    print("\n".join(lines))
    return 1 if unexplained else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
