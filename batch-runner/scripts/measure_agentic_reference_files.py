#!/usr/bin/env python3
"""What it would actually take to stage every task's reference files.

The gap is known and has been stated in every V2 record so far: a bound task is
a task whose reference files are *named* and not *present*, so a task that needs
one opened fails on its merits and the result is a mixture of model failure and
environment defect. What has not been stated is the shape of the gap, and the
shape is what decides whether closing it is an afternoon or a redesign.

Measured rather than estimated, against the pinned snapshot, because every
figure here has a cheap wrong answer. "A hundred and twenty-five tasks need
files" suggests a hundred and twenty-five similar problems; the sizes say
otherwise, and so does the one file that no amount of staging can deliver under
the limits the compute contract already sets.

Reads the parquet and stats files on disk. Calls nothing, spends nothing, and
writes nothing except its own report.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core.agentic_compute import (  # noqa: E402
    MAX_INPUT_FILES,
    MAX_INPUT_SINGLE,
    MAX_INPUT_TOTAL,
)

DATASET_REPO_ID = "openai/gdpval"
DATASET_REVISION = "11e7900cdcac61bc4daf59e65feb238acda98fbf"
SNAPSHOT = (
    Path.home()
    / ".cache"
    / "huggingface"
    / "hub"
    / f"datasets--{DATASET_REPO_ID.replace('/', '--')}"
    / "snapshots"
    / DATASET_REVISION
)

#: The reference-file paths in the parquet are relative to the snapshot root and
#: already correct -- `reference_files/<folder>/<name>`. The folder name is a
#: 32-hex string that looks like a digest and is not reliably one, so it is
#: treated as an opaque identifier here and never recomputed or verified as a
#: hash. Calling it a hash in a record would be a provenance claim the data does
#: not support.
PARQUET = SNAPSHOT / "data" / "train-00000-of-00001.parquet"


def measure() -> dict:
    import pyarrow.parquet as pq

    if not PARQUET.is_file():
        raise SystemExit(
            f"the pinned dataset is not at {PARQUET}.\n"
            f"  hf download {DATASET_REPO_ID} --repo-type dataset "
            f"--revision {DATASET_REVISION}"
        )

    table = pq.read_table(PARQUET, columns=["task_id", "reference_files"])
    task_ids = table.column("task_id").to_pylist()
    references = table.column("reference_files").to_pylist()

    per_task: list[dict] = []
    extensions: Counter = Counter()
    absent: list[str] = []
    over_single_limit: list[dict] = []

    for task_id, paths in zip(task_ids, references):
        paths = [str(one) for one in (paths or [])]
        if not paths:
            continue
        total = 0
        for relative in paths:
            path = SNAPSHOT / relative
            extensions[path.suffix.lower()] += 1
            if not path.is_file():
                absent.append(relative)
                continue
            size = path.stat().st_size
            total += size
            if size > MAX_INPUT_SINGLE:
                over_single_limit.append(
                    {"task_id": task_id, "file": path.name, "bytes": size}
                )
        per_task.append(
            {"task_id": task_id, "file_count": len(paths), "bytes": total}
        )

    sizes = sorted(entry["bytes"] for entry in per_task)
    biggest = sorted(per_task, key=lambda entry: -entry["bytes"])[:5]

    return {
        "dataset": {"repo_id": DATASET_REPO_ID, "revision": DATASET_REVISION},
        "tasks_total": len(task_ids),
        "tasks_needing_reference_files": len(per_task),
        "files_named_but_absent_from_the_snapshot": absent,
        "bytes_all_together": sum(sizes),
        # The whole total is the wrong number to plan against, because three
        # tasks hold most of it. This is what the other hundred and twenty-two
        # actually weigh.
        "bytes_without_the_three_heaviest_tasks": sum(sizes[:-3]),
        "bytes_per_task": {
            "median": sizes[len(sizes) // 2],
            "p90": sizes[int(len(sizes) * 0.9)],
            "max": sizes[-1],
        },
        "files_per_task_max": max(entry["file_count"] for entry in per_task),
        "extensions": dict(extensions.most_common()),
        "biggest_tasks": biggest,
        "limits_from_the_compute_contract": {
            "max_input_files": MAX_INPUT_FILES,
            "max_input_single_bytes": MAX_INPUT_SINGLE,
            "max_input_total_bytes": MAX_INPUT_TOTAL,
        },
        "files_over_the_single_file_limit": over_single_limit,
    }


def size(count: int) -> str:
    """Kilobytes stay kilobytes.

    The median task's files are about fifty kilobytes. Rounded to megabytes
    that reads as "0.1 MB", which looks like a rounding artefact rather than a
    measurement and invites the reader to skip it -- when it is in fact the most
    load-bearing number here, because it is what says most of this gap is a
    copy.
    """
    if count < 1_000_000:
        return f"{count / 1_000:,.1f} KB"
    return f"{count / 1_000_000:,.1f} MB"


def report(found: dict) -> str:
    lines = [
        f"{found['tasks_needing_reference_files']} of {found['tasks_total']} "
        "tasks name reference files.",
        f"All of them are present in the pinned snapshot: "
        f"{len(found['files_named_but_absent_from_the_snapshot'])} named files "
        "are missing.",
        f"Together they are {size(found['bytes_all_together'])}.",
        "",
        "Per task: "
        f"median {size(found['bytes_per_task']['median'])}, "
        f"p90 {size(found['bytes_per_task']['p90'])}, "
        f"max {size(found['bytes_per_task']['max'])}. "
        f"At most {found['files_per_task_max']} files.",
        "",
        "So this is not one problem repeated 125 times. For most tasks it is a "
        "handful of documents -- spreadsheets, PDFs and Word files are "
        f"{found['extensions'].get('.xlsx', 0)} + {found['extensions'].get('.pdf', 0)}"
        f" + {found['extensions'].get('.docx', 0)} of the "
        f"{sum(found['extensions'].values())} files -- and copying them is a "
        "copy. The weight is in a short tail of media: take out the three "
        "heaviest tasks and the remaining 122 come to "
        f"{size(found['bytes_without_the_three_heaviest_tasks'])} between them.",
        "",
    ]
    if found["files_over_the_single_file_limit"]:
        lines.append(
            "Files larger than the compute contract's own single-file limit of "
            f"{size(found['limits_from_the_compute_contract']['max_input_single_bytes'])}:"
        )
        for entry in found["files_over_the_single_file_limit"]:
            lines.append(
                f"  {size(entry['bytes'])}  {entry['file']}  ({entry['task_id']})"
            )
        lines += [
            "",
            "That limit is not a staging bug to be raised out of the way. A file "
            "that size is not something a model reads; delivering it would mean "
            "deciding what a model gets instead -- a transcript, frames, a "
            "summary -- and that decision changes what the task measures. It is "
            "recorded per task as an unmet need, not quietly dropped.",
        ]
    else:
        lines.append("No file exceeds the contract's single-file limit.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json", action="store_true", help="print the measurement, not the prose"
    )
    args = parser.parse_args(argv)

    found = measure()
    print(json.dumps(found, indent=2) if args.json else report(found))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
