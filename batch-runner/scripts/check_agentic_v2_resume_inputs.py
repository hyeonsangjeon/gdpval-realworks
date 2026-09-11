#!/usr/bin/env python3
"""Refuse a resume that would quietly become a second full run.

Resuming a V2 stage takes two separate inputs, and either one on its own is
worse than neither.

``run_id`` names the journal. ``run_manifest`` builds
``TaskJournal(journal_path, run_id=run_id, task_ids=...)``, so a journal row is
only found again by a run carrying the same name. ``resume_from_github_run``
names the GitHub run whose artifact holds that journal, because nothing in a
dispatch can infer it: the ``run_id`` is a journal name chosen by whoever
dispatched, not a number GitHub assigns.

So:

* **Both given** -- the directory is restored and the journal inside it is
  read under the name it was written with. Completed tasks are skipped. This
  is a resume.
* **Neither given** -- a fresh journal under a fresh name. Everything runs,
  and that is what was asked for.
* **``run_id`` alone** -- nothing restores the directory, so the journal file
  does not exist. A journal that is not there has no completed tasks in it, so
  every task runs and every task is paid for a second time. The run looks like
  a resume in its own logs, because the run id it prints is the one it was
  given.
* **``resume_from_github_run`` alone** -- the directory is restored and the
  journal file is there, but it was written under a different name, so
  ``TaskJournal`` finds no rows belonging to this run. Same outcome, one step
  further along: the evidence is present on disk and unreadable.

Both failures cost the full cohort. Neither raises anything: the driver is
working correctly in both cases, and a correct driver reading an empty journal
runs everything. That is why this is checked before the paid job starts rather
than defended against inside it.

Nothing here reaches the network, the model or the ledger. It compares two
strings.
"""

from __future__ import annotations

import argparse
import sys

#: What a resume needs, named the way the dispatch form names them.
RUN_ID = "run_id"
RESUME_FROM = "resume_from_github_run"


def problems_with(run_id: str, resume_from: str) -> list[str]:
    """What is wrong with this pair, or an empty list.

    Empty strings are what an unfilled dispatch input arrives as, so they are
    the "not given" case rather than an error. Whitespace is stripped first:
    a value that is only spaces was not given either, and letting it through
    as "given" would turn a stray keystroke into a full re-pay.
    """
    run_id = run_id.strip()
    resume_from = resume_from.strip()

    if run_id and not resume_from:
        return [
            f"{RUN_ID} is set to {run_id!r} but {RESUME_FROM} is empty. "
            "Nothing would restore the journal that run id names, so the "
            "journal file would not exist, no task would be found complete, "
            "and the whole cohort would run and be paid for again. Give the "
            f"GitHub run id of the run being resumed in {RESUME_FROM}, or "
            f"clear {RUN_ID} to start a fresh run."
        ]

    if resume_from and not run_id:
        return [
            f"{RESUME_FROM} is set to {resume_from!r} but {RUN_ID} is empty. "
            "The journal would be restored and then read under a different "
            "run id, so none of its rows would be found, and the whole cohort "
            "would run and be paid for again. Give the same run id the "
            f"earlier run used in {RUN_ID}, or clear {RESUME_FROM} to start a "
            "fresh run."
        ]

    if resume_from and not resume_from.isdigit():
        return [
            f"{RESUME_FROM} is {resume_from!r}, which is not a GitHub run id. "
            "It is the number in the run's URL -- all digits. A value that is "
            "not one cannot download anything, and the refusal for that "
            "arrives after the job has started."
        ]

    return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default="", help="the journal's run name")
    parser.add_argument(
        "--resume-from-github-run",
        default="",
        help="the GitHub run id whose artifact holds that journal",
    )
    args = parser.parse_args(argv)

    found = problems_with(args.run_id, args.resume_from_github_run)
    if found:
        for problem in found:
            print(f"refusing: {problem}", file=sys.stderr)
        return 1

    if args.run_id.strip():
        print(
            f"Resuming journal {args.run_id.strip()!r} from GitHub run "
            f"{args.resume_from_github_run.strip()}. Tasks already recorded "
            "complete in that journal will be skipped and not paid for again."
        )
    else:
        print(
            "A fresh run. No journal is restored and every task in the cohort "
            "will run."
        )
    return 0


if __name__ == "__main__":  # pragma: no cover - entry point
    raise SystemExit(main())
