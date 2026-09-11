#!/usr/bin/env python3
"""Write the record a finished run is required to leave, from its artifact.

``core.execution_environment_readiness`` names nineteen things a run has to
write down and offers ``check_run_record_fields`` to verify they are there.
Until now nothing produced them, so the check was only ever handed a
dictionary built from the list it checks against. This script produces the
record from what a real run left on disk, and prints which fields it could
not fill.

Usage
-----

    python scripts/build_run_record.py <artifact-dir> [--code-version <sha>]
                                       [--output run_record.json]

``<artifact-dir>`` is an unpacked run artifact -- the thing a workflow run
uploads, holding ``workspace/`` and ``results/``. The four inputs are found
under it by name, shallowly first and then recursively, so an artifact whose
contents sit one directory deeper still works.

``--code-version`` supplies the commit the pipeline ran. No artifact records
it, and guessing it from whichever checkout this script happens to run in
would be a fabrication that looks exactly like a measurement. In CI the caller
passes ``$GITHUB_SHA``; run by hand on a downloaded artifact months later,
nobody can, and the record says so.

What the summary means
----------------------
``recorded`` counts the fields carrying a real measurement. It is a number
about *instrumentation*, not about how well the run went: a run where every
task failed can record all nineteen, and a run that scored well can record
few. The two must not be read as one.

The dollar figure is printed exactly as the run's receipt states it, including
``partial`` and a null estimate. A cost that is unknown is never printed as
zero.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.execution_environment_readiness import (  # noqa: E402
    REQUIRED_RUN_RECORD_FIELDS,
)
from core.run_record import (  # noqa: E402
    build_run_record,
    is_recorded,
    unrecorded_fields,
)

#: The four artifacts the record is built from, each with the names it has
#: been written under. The condition-suffixed ledger is listed before the bare
#: one because a multi-condition run has both and the suffixed file is the one
#: that belongs to the condition being recorded.
ARTIFACT_NAMES = {
    "results": ("step2_inference_results.json",),
    "prepared": ("step1_tasks_prepared.json",),
    "manifest": ("step0_needs_files_manifest.json",),
    "ledger": ("cost_ledger_condition_a.jsonl", "cost_ledger.jsonl"),
}


def _find(root: Path, *names: str) -> Path | None:
    """First of ``names`` present under ``root``; shallow before deep."""
    for name in names:
        candidate = root / name
        if candidate.is_file():
            return candidate
        nested = root / "workspace" / name
        if nested.is_file():
            return nested
    for name in names:
        hits = sorted(root.rglob(name))
        if hits:
            return hits[0]
    return None


def _load_json(path: Path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def record_from_artifact(artifact: Path, code_version: str | None = None) -> dict:
    """Locate the four inputs under ``artifact`` and build the record.

    A missing input raises rather than defaulting to an empty one. A record
    silently built from three files would be indistinguishable from one built
    from four, and every field the fourth fills would read as "the run did not
    record this" when the truth is that this script did not look hard enough.
    """
    found = {}
    for key, names in ARTIFACT_NAMES.items():
        path = _find(artifact, *names)
        if path is None:
            raise SystemExit(
                f"{artifact}: no {' or '.join(names)} found -- this does not "
                f"look like an unpacked run artifact"
            )
        found[key] = path

    return build_run_record(
        results=_load_json(found["results"]),
        prepared=_load_json(found["prepared"]),
        manifest=_load_json(found["manifest"]),
        ledger_rows=_load_jsonl(found["ledger"]),
        code_version=code_version,
    )


def summarise(record: dict) -> None:
    missing = unrecorded_fields(record)
    recorded = len(REQUIRED_RUN_RECORD_FIELDS) - len(missing)
    print(f"experiment      : {record.get('experiment_id')}")
    print(f"run             : {record.get('run_id')}")
    print(f"recorded fields : {recorded} / {len(REQUIRED_RUN_RECORD_FIELDS)}")
    for name in missing:
        print(f"  not recorded  : {name} -- {record[name]['reason']}")

    completed = record.get("task_completed")
    if is_recorded(completed):
        print(f"task status     : {completed['counts_by_status']}")
    calls = record.get("model_call_count")
    if is_recorded(calls) and not calls.get("agree"):
        print(
            f"  ! the cost receipt counts {calls['from_cost_receipt']} model "
            f"calls and the ledger holds {calls['from_cost_ledger']} rows; a "
            f"call was made and not receipted"
        )
    retries = record.get("retry_counts_by_reason")
    if is_recorded(retries):
        print(f"retries         : {retries}")

    cost = record.get("model_cost")
    if is_recorded(cost):
        status = cost.get("status")
        print(f"cost            : status={status} estimated_usd={cost.get('estimated_cost_usd')}")
        if status != "complete":
            print(
                f"  -> the run's dollar cost is UNDETERMINED"
                f"{': ' + ', '.join(cost.get('missing_reasons') or []) if cost.get('missing_reasons') else ''}."
                f" That is not zero."
            )
    print("\nThis record covers solving only. Grading is a separate run with a")
    print("separate cost, and the two are never added together.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "artifact",
        type=Path,
        help="directory holding an unpacked run artifact (workspace/ and results/)",
    )
    parser.add_argument(
        "--code-version",
        default=None,
        help="commit sha the pipeline ran; no artifact records it, so it is "
        "supplied or left explicitly unrecorded",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="where to write the record (default: <artifact>/run_record.json)",
    )
    args = parser.parse_args(argv)
    if not args.artifact.is_dir():
        raise SystemExit(f"not a directory: {args.artifact}")

    record = record_from_artifact(args.artifact, args.code_version)
    output = args.output or (args.artifact / "run_record.json")
    output.write_text(
        json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    summarise(record)
    print(f"\nwritten: {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
