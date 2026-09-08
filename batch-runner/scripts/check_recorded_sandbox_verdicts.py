#!/usr/bin/env python3
"""Hold the repository's claims about each host to what the host actually does.

`diagnose_codex_sandbox_host.py` measures one machine. This compares that
measurement against what `docs/codex_sandbox_hosts.json` says about the same
machine, and fails when they disagree.

The reason for a checker rather than a plain "is it ready" gate: almost none of
these hosts are ready, that is a true and stable fact, and a job that goes red
every run for a fact nobody disputes gets muted within a week. What is worth
interrupting somebody for is *change* -- in either direction:

* A host that quietly became capable. GitHub re-images hosted runners
  continuously. The day `ubuntu-24.04` starts running a command under
  bubblewrap is the day this project gets a free execution host, and nobody
  would otherwise notice for months.
* A host that quietly stopped being capable, which would make a run place
  disappear underneath a scheduled experiment.
* A record that was written from an assumption. An unmeasured host is not
  recorded as anything here; the checker refuses a host key it has never seen
  rather than accepting whatever showed up, because "the file agrees with
  reality" has to mean somebody looked.

Usage:

    python scripts/check_recorded_sandbox_verdicts.py \
        --host-key ubuntu-24.04-host --observed /tmp/ubuntu-24.04-host.json

Exit status:

    0   the observation matches the record
    1   they disagree -- the message names both
    2   the observation could not be read
    3   this host key has no record yet; the message shows what to add
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
RECORD_PATH = BATCH_RUNNER_ROOT / "docs" / "codex_sandbox_hosts.json"


def load_record(path: Path) -> dict[str, Any]:
    """Read the record, failing closed.

    An unreadable or malformed record is not an empty record. Treating it as
    one would silently accept every observation, which is the failure mode this
    file was written to prevent.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SystemExit(f"the host record at {path} could not be read: {exc}")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"the host record at {path} is not valid JSON: {exc}")
    hosts = parsed.get("hosts")
    if not isinstance(hosts, dict):
        raise SystemExit(
            f"the host record at {path} has no 'hosts' object; refusing to "
            "treat that as 'nothing recorded'"
        )
    return hosts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare a measured sandbox verdict against the record."
    )
    parser.add_argument("--host-key", required=True)
    parser.add_argument("--observed", required=True, type=Path)
    parser.add_argument("--record", type=Path, default=RECORD_PATH)
    args = parser.parse_args(argv)

    try:
        observation = json.loads(args.observed.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(
            f"the measurement at {args.observed} could not be read: {exc}",
            file=sys.stderr,
        )
        return 2

    observed = observation.get("readiness")
    if not observed:
        print("the measurement names no verdict", file=sys.stderr)
        return 2

    hosts = load_record(args.record)
    recorded_entry = hosts.get(args.host_key)

    if recorded_entry is None:
        print(
            f"host {args.host_key!r} has no record yet.\n"
            f"It measured: {observed}\n"
            f"  {observation.get('explanation', '')}\n\n"
            f"Add it to {args.record.name} once a human has read the "
            f"measurement -- this tool will not write its own expectation.",
            file=sys.stderr,
        )
        return 3

    recorded = recorded_entry.get("readiness")
    if recorded == observed:
        print(f"{args.host_key}: {observed} -- matches the record")
        note = recorded_entry.get("note")
        if note:
            print(f"  {note}")
        return 0

    print(
        f"{args.host_key} changed.\n"
        f"  recorded: {recorded}\n"
        f"  measured: {observed} -- {observation.get('explanation', '')}\n\n"
        + (
            "This host now runs a command under the sandbox where it did not "
            "before. That is a new execution host: read the artifact, then "
            "update the record and the two skipped assertions in "
            "test_codex_runtime_end_to_end.py."
            if observed == "ready"
            else "Read the uploaded measurement before changing the record. A "
            "record edited to match a surprise is not a record."
        ),
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
