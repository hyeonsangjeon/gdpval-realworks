#!/usr/bin/env python3
"""Refuse a grader-source change while a paid grade run is in flight.

Merging one file under ``batch-runner/core/`` while eleven shards are grading
costs nothing for about sixty hours and then costs everything. Each shard
stamps its own ``grader_source_hash``; ``step9_merge_shards`` lists that field
among the ten identity invariants two shards must agree on, and step9 only
runs once every shard has finished. So the spend happens first and the union
is refused afterwards, leaving partials that no longer agree with each other
and nothing to salvage. ``--force`` does not override a short or mixed union,
by design -- see ``304-B-partial-blocked.md``.

The failure is silent at the moment it is caused. Nothing about merging a
one-line fix says "you have just written off two and a half days of grading";
the merge is green, the shards keep running, and the bill arrives before the
error does. This module is the cheap half of the answer: a pull request that
would move the hash gets a red check for as long as a paid run is alive, at
the moment the pull request is opened or updated rather than at merge time.

What it is not: a hard gate. A check is advisory unless the repository
requires it in branch protection, and a pull request that was green yesterday
can still be merged today. This turns an invisible trap into a visible one --
the difference between "we forgot" and "we decided" -- and does not pretend to
be more than that.

Fail-closed. If an in-flight run cannot be shown to be free, it counts as
paid. A false red costs one conversation; a false green costs the run.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Iterable, Sequence

#: Jobs on the paid path in ``grade-run.yml``, matched against what the jobs
#: API actually returns. Two traps live here, both found by checking the
#: classifier against real runs rather than against the workflow file:
#:
#: 1. The API reports a job's *display name*, and never its key. ``grade`` has
#:    no ``name:`` override so the two coincide, but ``approve-paid`` renders
#:    as "Approve paid Sol Max grading (exp_gold_baseline, ...)". Matching on
#:    the key would have missed it in every run.
#: 2. The API lists jobs that were *skipped*. A paid run therefore contains a
#:    ``grade-dry-run`` entry, and a dry run contains a ``grade`` entry. Job
#:    presence alone distinguishes nothing; only the conclusion does.
PAID_JOB_EXACT_NAMES = frozenset({"grade"})
PAID_JOB_NAME_PREFIXES = ("Approve paid ",)

#: The one conclusion that proves a job did not happen. Every other value --
#: success, failure, cancelled, and null for a job still running or queued --
#: means the paid path is live or has already spent.
SKIPPED = "skipped"

#: Run statuses that mean "still alive". GitHub reports ``waiting`` while a
#: run sits at an environment approval gate; that run has not spent anything
#: yet, but it is about to, and the approval is usually seconds away.
LIVE_STATUSES = frozenset({"queued", "in_progress", "waiting", "pending", "requested"})


def is_paid_path_job(name: str) -> bool:
    cleaned = name.strip()
    if cleaned in PAID_JOB_EXACT_NAMES:
        return True
    return any(cleaned.startswith(prefix) for prefix in PAID_JOB_NAME_PREFIXES)


#: Repo-relative paths whose bytes enter ``compute_grader_source_hash``.
#: Mirrored by hand because the hash function builds its list from a loaded
#: config and a filesystem walk, neither of which a pull-request check has.
#: ``test_grader_hash_freeze.py`` spies on the real function's reads and fails
#: if this set ever stops covering them, so the mirror cannot drift quietly.
_EXACT_HASHED_FILES = frozenset(
    {
        "batch-runner/step8_grade.py",
        "batch-runner/schemas/grade.schema.json",
        "batch-runner/requirements.txt",
        "batch-runner/scripts/download_inference_from_hf.py",
    }
)

#: ``(directory prefix, required suffix or None)``. ``core`` contributes only
#: its ``.py`` files -- the hash function walks ``core.rglob("*")`` and keeps
#: ``suffix == ".py"`` -- so a fixture or a README under core is not hashed
#: and must not freeze a merge.
_HASHED_TREES: tuple[tuple[str, str | None], ...] = (
    ("batch-runner/core/", ".py"),
    ("batch-runner/prompts/", None),
    ("batch-runner/grading_configs/", None),
)


def is_grader_source_path(path: str) -> bool:
    """True when changing ``path`` would move some config's grader source hash.

    Deliberately generous in two places. Every file under ``prompts/`` counts,
    though only the template a config names is hashed: which template that is
    depends on the config, and a check that has to load configs to answer a
    yes/no question is a check that fails for the wrong reasons. Same for
    ``grading_configs/`` -- the hash covers the one config being run, and the
    check does not know which run is in flight.
    """
    normalised = PurePosixPath(path.strip().lstrip("./")).as_posix()
    if normalised in _EXACT_HASHED_FILES:
        return True
    for prefix, suffix in _HASHED_TREES:
        if normalised.startswith(prefix):
            if suffix is None or normalised.endswith(suffix):
                return True
    return False


@dataclass(frozen=True)
class LiveRun:
    """One grade-run workflow run that has not finished."""

    run_id: str
    status: str
    url: str
    paid: bool
    #: Why ``paid`` holds the value it does, so a red check can explain itself
    #: without the reader opening the API by hand.
    paid_reason: str


def classify_runs(raw_runs: Iterable[dict[str, Any]]) -> list[LiveRun]:
    """Turn the workflow's JSON into runs, fail-closed on anything unclear.

    ``jobs`` is expected to be that run's job list, each entry carrying at
    least ``name`` and ``conclusion``. A run is called free only on positive
    evidence: at least one paid-path job is visible *and* every visible one
    concluded ``skipped``. Everything else is paid -- an absent list (the jobs
    API declined to answer), a list too early to contain either branch, and a
    paid job still running, which reports a null conclusion.
    """
    live: list[LiveRun] = []
    for raw in raw_runs:
        status = str(raw.get("status") or "").strip().lower()
        if status not in LIVE_STATUSES:
            continue
        run_id = str(raw.get("id") or raw.get("databaseId") or "?")
        url = str(raw.get("url") or raw.get("html_url") or "")
        jobs = raw.get("jobs")

        if not isinstance(jobs, list) or not jobs:
            paid, reason = True, "job list unavailable, assumed paid"
        else:
            paid_path = [
                j
                for j in jobs
                if isinstance(j, dict) and is_paid_path_job(str(j.get("name") or ""))
            ]
            if not paid_path:
                # `validate-request` runs on both paths, so it says nothing.
                # Silence is not evidence that this run is free.
                paid, reason = True, "too early to tell, assumed paid"
            else:
                alive = [
                    j
                    for j in paid_path
                    if str(j.get("conclusion") or "").strip().lower() != SKIPPED
                ]
                if alive:
                    names = ", ".join(
                        sorted({str(j.get("name") or "?").split(" (")[0] for j in alive})
                    )
                    paid, reason = True, f"paid job not skipped: {names}"
                else:
                    paid, reason = False, "every paid job skipped, dry run"

        live.append(
            LiveRun(run_id=run_id, status=status, url=url, paid=paid, paid_reason=reason)
        )
    return live


@dataclass(frozen=True)
class Decision:
    frozen: bool
    moving_paths: tuple[str, ...]
    blocking_runs: tuple[LiveRun, ...]
    summary: str


def decide(changed_paths: Sequence[str], raw_runs: Iterable[dict[str, Any]]) -> Decision:
    """Freeze only when both halves are true: the diff moves the hash *and*
    a paid run is alive. Either alone is ordinary and must stay green."""
    moving = tuple(sorted({p for p in changed_paths if is_grader_source_path(p)}))
    blocking = tuple(r for r in classify_runs(raw_runs) if r.paid)

    if not moving:
        return Decision(False, moving, blocking, "no grader-source file in this diff")
    if not blocking:
        return Decision(False, moving, blocking, "no paid grade run in flight")
    return Decision(
        True,
        moving,
        blocking,
        f"{len(moving)} grader-source file(s) changed while "
        f"{len(blocking)} paid grade run(s) are in flight",
    )


def render(decision: Decision) -> str:
    lines: list[str] = []
    if not decision.frozen:
        lines.append(f"PASS: {decision.summary}")
        if decision.moving_paths:
            lines.append("")
            lines.append(
                "This diff does move the grader source hash. That is fine right "
                "now, but it means the next paid run has to be preceded by a "
                "fresh smoke at the new fingerprint."
            )
            for path in decision.moving_paths:
                lines.append(f"  - {path}")
        return "\n".join(lines)

    lines.append(f"FROZEN: {decision.summary}")
    lines.append("")
    lines.append("Grader-source files in this diff:")
    for path in decision.moving_paths:
        lines.append(f"  - {path}")
    lines.append("")
    lines.append("Paid grade runs still alive:")
    for run in decision.blocking_runs:
        location = run.url or f"run {run.run_id}"
        lines.append(f"  - {run.run_id} [{run.status}] ({run.paid_reason}) {location}")
    lines.append("")
    lines.append(
        "Merging this would give the remaining shards a different "
        "grader_source_hash from the ones already graded. step9_merge_shards "
        "requires that field to be identical across shards and only runs after "
        "every shard finishes, so the union would be refused after the whole "
        "run had been paid for -- roughly sixty hours for the 185-task corpus. "
        "Wait for the run to finish, then merge."
    )
    return "\n".join(lines)


def _load(path: str) -> Any:
    if path == "-":
        return json.load(sys.stdin)
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--changed-paths",
        required=True,
        help="JSON array of repo-relative paths changed by the pull request, or - for stdin",
    )
    parser.add_argument(
        "--runs",
        required=True,
        help="JSON array of in-flight grade-run runs, or - for stdin",
    )
    args = parser.parse_args(argv)

    try:
        changed = _load(args.changed_paths)
        runs = _load(args.runs)
    except (OSError, ValueError) as exc:
        print(f"FROZEN: could not read the check's own inputs: {exc}", file=sys.stderr)
        return 1

    if not isinstance(changed, list) or not isinstance(runs, list):
        print("FROZEN: inputs must both be JSON arrays", file=sys.stderr)
        return 1

    decision = decide([str(p) for p in changed], runs)
    print(render(decision))
    return 1 if decision.frozen else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
