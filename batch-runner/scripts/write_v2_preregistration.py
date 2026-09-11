#!/usr/bin/env python3
"""Write the V2 pre-registration to its committed file, or report that it moved.

The pre-registration in :mod:`core.agentic_v2_preregistration` is derived, not
typed: the cohorts come from the committed catalogue and the comparison comes
from A's committed experiment file. Deriving it is what makes it trustworthy --
nobody can adjust a task list after seeing a result without the seal changing --
but a derived record is only pre-registered if a *copy of it* is committed
before the run. Otherwise "what we planned" is whatever the code says today.

So this writes ``tasks/0822_saturday/v2_run_preregistration.json`` and a test
asserts the committed copy still equals what the code derives. The two ways
that test can fail say different things:

* **This repository's own inputs moved** -- a selection rule, a catalogue, a
  stop rule. The commit that moved them should carry the regenerated artefact,
  and a run under the old seal is no longer pre-registered.
* **A's experiment file moved.** The comparison describes a configuration that
  no longer exists. Regenerating is right, but so is re-reading whether the
  runs are still comparable, because that is the question the file answers.

Either way the fix is one command, printed in the failure. Run with ``--check``
to compare without writing.

This script calls no model, boots no guest, opens no gate and spends nothing.
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY_ROOT / "batch-runner"))

from core.agentic_v2_preregistration import (  # noqa: E402
    PREREGISTRATION_ARTEFACT as ARTEFACT,
    record,
)


def rendered() -> str:
    """The artefact exactly as it is written, so a diff is meaningful."""
    return json.dumps(record(), indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="report drift and exit non-zero instead of writing",
    )
    args = parser.parse_args(argv)

    current = rendered()
    committed = ARTEFACT.read_text(encoding="utf-8") if ARTEFACT.is_file() else None

    if args.check:
        if committed == current:
            print(f"up to date: {ARTEFACT.relative_to(REPOSITORY_ROOT)}")
            return 0
        print(
            "the committed pre-registration is not what the code now derives.\n"
            "A run under the committed seal can no longer be called "
            "pre-registered until this is resolved.\n",
            file=sys.stderr,
        )
        for line in difflib.unified_diff(
            (committed or "").splitlines(keepends=True),
            current.splitlines(keepends=True),
            fromfile="committed",
            tofile="derived",
            n=2,
        ):
            sys.stderr.write(line)
        print(
            "\nregenerate with: python batch-runner/scripts/"
            "write_v2_preregistration.py",
            file=sys.stderr,
        )
        return 1

    ARTEFACT.write_text(current, encoding="utf-8")
    verb = "unchanged" if committed == current else "written"
    print(f"{verb}: {ARTEFACT.relative_to(REPOSITORY_ROOT)}")
    print(f"seal: {record()['seal']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
