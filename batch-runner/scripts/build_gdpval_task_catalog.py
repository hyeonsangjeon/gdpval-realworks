#!/usr/bin/env python3
"""Write the committed task catalogue the run-place comparison selects from.

This reads the benchmark dataset at one pinned revision and writes down, for
every task, only what the fixed selection rule is allowed to look at: the task
number, the industry, the job, the file types of the human expert's own answer,
the reference files the task ships with, and a fingerprint of the task wording.

No score, grade, or verdict is read or written. No model is called and nothing
is spent. The dataset revision and the content fingerprint of its data file are
written into the catalogue so anyone can confirm which data produced it.

Usage:

    python scripts/build_gdpval_task_catalog.py
    python scripts/build_gdpval_task_catalog.py --parquet path/to/train.parquet
    python scripts/build_gdpval_task_catalog.py --check

``--check`` rebuilds the catalogue in memory and reports whether the committed
file still matches, without writing anything. Note what that does not cover: it
rebuilds using this same code, so if a column this script reads were renamed in
the dataset and this script went on quietly recording nothing in its place, both
sides of the comparison would carry the same missing value and ``--check``
would report a match. That is why the reading below refuses rather than
substitutes a value it could not read.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Iterable

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core.execution_envelope_tasks import (  # noqa: E402
    CATALOG_PATH,
    CATALOG_SCHEMA_VERSION,
    DATASET_REPO_ID,
    DATASET_REVISION,
    TaskCatalog,
    catalog_number_problems,
    catalog_score_problems,
)

HUGGING_FACE_CACHE_PARQUET = (
    Path.home()
    / ".cache"
    / "huggingface"
    / "hub"
    / "datasets--openai--gdpval"
    / "snapshots"
    / DATASET_REVISION
    / "data"
    / "train-00000-of-00001.parquet"
)

#: Every column this script reads out of the dataset. Kept in one place so the
#: reading below can say up front which of them a file does not hold, instead of
#: discovering it one row at a time and recording nothing in its place.
COLUMNS_THE_CATALOGUE_IS_BUILT_FROM = (
    "task_id",
    "sector",
    "occupation",
    "deliverable_files",
    "reference_files",
    "prompt",
    "rubric_json",
)


def missing_columns(column_names: Iterable[str]) -> list[str]:
    """Which columns this script needs that the dataset file does not hold."""
    return sorted(set(COLUMNS_THE_CATALOGUE_IS_BUILT_FROM) - set(column_names))


def _find_parquet(explicit: Path | None) -> Path:
    if explicit is not None:
        if not explicit.is_file():
            raise SystemExit(f"no dataset file at {explicit}")
        return explicit
    if HUGGING_FACE_CACHE_PARQUET.is_file():
        return HUGGING_FACE_CACHE_PARQUET
    raise SystemExit(
        "the pinned dataset file was not found. Download revision "
        f"{DATASET_REVISION} of {DATASET_REPO_ID} first, or pass --parquet."
    )


def build_catalog(parquet_path: Path) -> dict:
    """Read the pinned dataset and write down what the selection may look at.

    Nothing here substitutes a value it could not read. A missing column, a
    null, or a rubric that will not parse stops the build, because each of them
    used to become a count of zero, and a zero is read further on as work that
    costs nothing rather than as something nobody could find.
    """
    import pyarrow.parquet as pq

    raw = parquet_path.read_bytes()
    table = pq.read_table(parquet_path)

    absent = missing_columns(table.column_names)
    if absent:
        raise ValueError(
            "the dataset file does not hold: "
            + ", ".join(absent)
            + ". It holds: "
            + ", ".join(sorted(table.column_names))
            + ". Writing a catalogue now would record a count of "
            "zero for every task, and a zero is read further on as work that "
            "costs nothing rather than as a column nobody could find."
        )

    rows = table.to_pylist()

    tasks = []
    for row in rows:
        empty = sorted(
            name
            for name in COLUMNS_THE_CATALOGUE_IS_BUILT_FROM
            if row.get(name) is None
        )
        if empty:
            raise ValueError(
                f"task {row.get('task_id')!r} holds nothing at all under: "
                + ", ".join(empty)
                + ". Nothing is not the same as none, and recording it as none "
                "would price part of this task at zero."
            )

        deliverables = list(row["deliverable_files"])
        references = list(row["reference_files"])
        prompt = str(row["prompt"])
        try:
            rubric_items = json.loads(row["rubric_json"])
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"task {row['task_id']!r}: the marking rubric could not be "
                f"read ({error}). This used to be recorded as a task with no "
                "rubric, which prices marking it at nothing."
            ) from error
        if not isinstance(rubric_items, list):
            raise ValueError(
                f"task {row['task_id']!r}: the marking rubric is a "
                f"{type(rubric_items).__name__} rather than a list of scoring "
                "lines, so there is no number of scoring lines to record."
            )

        tasks.append(
            {
                "task_id": str(row["task_id"]),
                "sector": str(row["sector"]),
                "occupation": str(row["occupation"]),
                "deliverable_file_extensions": sorted(
                    {os.path.splitext(name)[1].lower() for name in deliverables}
                ),
                "reference_file_count": len(references),
                "reference_file_extensions": sorted(
                    {os.path.splitext(name)[1].lower() for name in references}
                ),
                "reference_file_paths": sorted(str(name) for name in references),
                "prompt_sha256": hashlib.sha256(
                    prompt.encode("utf-8")
                ).hexdigest(),
                "prompt_character_count": len(prompt),
                "rubric_item_count": len(rubric_items),
            }
        )
    tasks.sort(key=lambda entry: entry["task_id"])

    return {
        "schema_version": CATALOG_SCHEMA_VERSION,
        "dataset_repo_id": DATASET_REPO_ID,
        "dataset_revision": DATASET_REVISION,
        "dataset_file_sha256": hashlib.sha256(raw).hexdigest(),
        "written_by": "batch-runner/scripts/build_gdpval_task_catalog.py",
        "holds_no_scores": (
            "Only task numbers, industries, jobs, expert answer file types, "
            "reference file paths and types, and a fingerprint of the task "
            "wording are recorded. No score, grade, or verdict is present."
        ),
        "reference_file_path_note": (
            "In this dataset each reference file sits in a folder named after "
            "the first 32 hexadecimal characters of that file's SHA-256 "
            "fingerprint, so a fingerprint written into the plan can be "
            "checked against the path without downloading anything."
        ),
        "tasks": tasks,
    }


def render(catalog: dict) -> str:
    return json.dumps(catalog, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _counts_that_cannot_be_true(catalog: dict) -> list[str]:
    """The same question the advance check asks, asked of what is about to be written."""
    try:
        loaded = TaskCatalog.from_mapping(catalog)
    except ValueError as error:
        return [str(error)]
    return catalog_number_problems(loaded)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parquet", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=CATALOG_PATH)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Report whether the committed catalogue still matches the dataset.",
    )
    args = parser.parse_args()

    try:
        catalog = build_catalog(_find_parquet(args.parquet))
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1

    # Ask before writing, not after committing. Whoever next edits this script
    # to record one more useful-looking column will find out here, rather than
    # at the advance check that was supposed to be reading a clean file.
    problems = list(catalog_score_problems(catalog))
    # And ask whether the numbers about to be written could be true at all,
    # because the cost ceiling is worked out from these same numbers.
    problems.extend(_counts_that_cannot_be_true(catalog))
    if problems:
        for note in problems:
            print(note, file=sys.stderr)
        return 1

    rendered = render(catalog)

    if args.check:
        if not args.out.is_file():
            print(f"no catalogue at {args.out}", file=sys.stderr)
            return 1
        current = args.out.read_text(encoding="utf-8")
        if current == rendered:
            print(f"the committed catalogue matches revision {DATASET_REVISION}")
            return 0
        print(
            f"the committed catalogue does not match revision {DATASET_REVISION}",
            file=sys.stderr,
        )
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(rendered, encoding="utf-8")
    print(f"wrote {len(catalog['tasks'])} tasks to {args.out}")
    print("dataset file fingerprint: " + catalog["dataset_file_sha256"])
    print(
        "catalogue fingerprint:    "
        + hashlib.sha256(rendered.encode("utf-8")).hexdigest()
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
