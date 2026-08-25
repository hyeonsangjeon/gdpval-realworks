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
file still matches, without writing anything.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core.execution_envelope_tasks import (  # noqa: E402
    CATALOG_PATH,
    CATALOG_SCHEMA_VERSION,
    DATASET_REPO_ID,
    DATASET_REVISION,
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
    import pyarrow.parquet as pq

    raw = parquet_path.read_bytes()
    rows = pq.read_table(parquet_path).to_pylist()

    tasks = []
    for row in rows:
        deliverables = list(row.get("deliverable_files") or [])
        references = list(row.get("reference_files") or [])
        prompt = str(row.get("prompt") or "")
        rubric_json = row.get("rubric_json")
        try:
            rubric_items = json.loads(rubric_json) if rubric_json else []
        except (TypeError, ValueError):
            rubric_items = []
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

    catalog = build_catalog(_find_parquet(args.parquet))
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
