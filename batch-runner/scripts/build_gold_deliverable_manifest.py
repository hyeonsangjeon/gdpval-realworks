#!/usr/bin/env python3
"""Write down exactly which reference answers the gold-ceiling runs are graded on.

The benchmark ships one human expert answer for most of its tasks. The
gold-ceiling check grades those answers instead of a model's, so that the score
they earn can be read as the highest the grader is able to award. That only
means anything if the bytes being graded are pinned: this script records, for
every task in the benchmark, which expert answer files it ships, where the
dataset keeps them, where the grader reads them from, how large each one is, and
its SHA-256 fingerprint.

Nothing here calls a model and nothing is spent. The dataset revision and the
fingerprint of its data file are written into the manifest, so anyone can
confirm which release produced it.

The re-rooting rule -- the dataset files a task's expert answer under an opaque
folder, while the grader reads it from a folder named after the task -- is not
repeated here. It is imported from ``download_inference_from_hf`` so that the
run and the manifest cannot drift into two different answers about where a file
belongs.

Usage:

    python scripts/build_gold_deliverable_manifest.py --dataset-root DIR
    python scripts/build_gold_deliverable_manifest.py --dataset-root DIR --check

``--check`` rebuilds the manifest in memory and reports whether the committed
file still matches, without writing anything.

Getting the bytes, once and free:

    huggingface-cli download openai/gdpval --repo-type dataset \\
        --revision <sha> --include 'deliverable_files/*' --local-dir DIR
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path, PurePosixPath

SCRIPTS_ROOT = Path(__file__).resolve().parent
BATCH_RUNNER_ROOT = SCRIPTS_ROOT.parent
for _root in (str(BATCH_RUNNER_ROOT), str(SCRIPTS_ROOT)):
    if _root not in sys.path:
        sys.path.insert(0, _root)

from download_inference_from_hf import (  # noqa: E402
    gold_deliverable_path,
    gold_rows_from_parquet,
)

#: The dataset this benchmark's tasks and expert answers come from.
DATASET_REPO_ID = "openai/gdpval"
#: The one revision the gold-ceiling stages are frozen to. Every run in stages
#: 1 to 3 reads this same commit, so the three of them grade identical bytes.
DATASET_REVISION = "11e7900cdcac61bc4daf59e65feb238acda98fbf"
#: The one data file that revision ships its tasks in.
DATASET_DATA_FILE = "data/train-00000-of-00001.parquet"

MANIFEST_SCHEMA_VERSION = "gdpval-gold-deliverable-manifest-v1"
MANIFEST_PATH = (
    BATCH_RUNNER_ROOT / "experiments" / "gold_corpus" / "gold_deliverable_manifest.json"
)
WRITTEN_BY = "batch-runner/scripts/build_gold_deliverable_manifest.py"

#: Every column read out of the dataset. Named in one place so a file that does
#: not hold one of them can be refused up front, by name, rather than quietly
#: becoming a task with no expert answer.
COLUMNS_THE_MANIFEST_IS_BUILT_FROM = (
    "task_id",
    "sector",
    "occupation",
    "deliverable_files",
)


def sha256_of_file(path: Path) -> tuple[str, int]:
    """The SHA-256 fingerprint and byte count of one file, read in blocks."""
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
            size += len(block)
    return digest.hexdigest(), size


def _resolve_source_file(dataset_root: Path, source_path: str) -> Path:
    """Locate one downloaded expert answer, refusing anything but a real file.

    A symlink is refused rather than followed. The download cache keeps its
    real bytes elsewhere and links to them, and a fingerprint taken through a
    link records what the link pointed at today, not what the dataset ships.
    """
    candidate = dataset_root.joinpath(*PurePosixPath(source_path).parts)
    if candidate.is_symlink():
        raise SystemExit(
            f"{source_path} is a symlink under {dataset_root}. Download with "
            "--local-dir so the real bytes are on disk, and fingerprint those."
        )
    if not candidate.is_file():
        raise SystemExit(
            f"no copy of {source_path} under {dataset_root}. Download the "
            f"pinned revision first: huggingface-cli download {DATASET_REPO_ID} "
            f"--repo-type dataset --revision {DATASET_REVISION} "
            "--include 'deliverable_files/*' --local-dir <dir>"
        )
    return candidate


def build_manifest(
    parquet_path: Path,
    dataset_root: Path,
    *,
    repo_id: str,
    revision: str,
) -> dict:
    """Read the pinned dataset and fingerprint every expert answer it ships.

    Tasks the dataset ships no expert answer for are kept, with an empty file
    list. Dropping them would make the benchmark look 185 tasks long, and a
    30-task selection measured against a 185-task corpus is a different claim
    from one measured against 220.
    """
    import pyarrow.parquet as pq

    table = pq.read_table(parquet_path)
    absent = sorted(
        set(COLUMNS_THE_MANIFEST_IS_BUILT_FROM) - set(table.column_names)
    )
    if absent:
        raise SystemExit(
            "the dataset file does not hold: "
            + ", ".join(absent)
            + ". It holds: "
            + ", ".join(sorted(table.column_names))
            + ". Building a manifest now would record no expert answer for "
            "every task, which reads downstream as a benchmark with nothing to "
            "grade rather than as a column nobody could find."
        )

    labels = {
        str(row["task_id"]): (str(row["sector"]), str(row["occupation"]))
        for row in table.select(["task_id", "sector", "occupation"]).to_pylist()
    }

    tasks: list[dict] = []
    file_count = 0
    total_bytes = 0
    for position, row in enumerate(gold_rows_from_parquet(str(parquet_path))):
        task_id = row["task_id"]
        sector, occupation = labels[task_id]
        files = []
        for source_path, graded_path in zip(
            row["gold_source_files"], row["deliverable_files"]
        ):
            # Re-derived rather than trusted: the pairing above only holds if
            # the two lists were built from each other, and this says so.
            if gold_deliverable_path(task_id, source_path) != graded_path:
                raise SystemExit(
                    f"{source_path} does not re-root to {graded_path} for task "
                    f"{task_id}"
                )
            fingerprint, size = sha256_of_file(
                _resolve_source_file(dataset_root, source_path)
            )
            files.append(
                {
                    "source_path": source_path,
                    "graded_path": graded_path,
                    "sha256": fingerprint,
                    "size": size,
                }
            )
            file_count += 1
            total_bytes += size
        tasks.append(
            {
                "position": position,
                "task_id": task_id,
                "sector": sector,
                "occupation": occupation,
                "files": files,
            }
        )

    dataset_file_sha256, _ = sha256_of_file(parquet_path)
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "dataset_repo_id": repo_id,
        "dataset_revision": revision,
        "dataset_data_file": DATASET_DATA_FILE,
        "dataset_file_sha256": dataset_file_sha256,
        "written_by": WRITTEN_BY,
        "holds_no_scores": (
            "Only task numbers, industries, jobs, and the name, size and "
            "SHA-256 fingerprint of each expert answer file are recorded. No "
            "score, grade, verdict, or scoring line is present, and no file's "
            "contents are reproduced."
        ),
        "path_note": (
            "The dataset files each expert answer under an opaque 32-character "
            "folder that is not derived from the file's contents; source_path "
            "is where the dataset keeps it and graded_path is where the grader "
            "reads it from."
        ),
        "task_count": len(tasks),
        "gold_bearing_task_count": sum(1 for task in tasks if task["files"]),
        "file_count": file_count,
        "total_bytes": total_bytes,
        "tasks": tasks,
    }


def gold_bearing_task_ids(manifest: dict) -> list[str]:
    """Every task that ships an expert answer, in the dataset's own order."""
    return [task["task_id"] for task in manifest["tasks"] if task["files"]]


def load_manifest(path: Path = MANIFEST_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _serialize(manifest: dict) -> str:
    return json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset-root",
        required=True,
        help="Directory holding the downloaded deliverable_files/ tree",
    )
    parser.add_argument(
        "--parquet",
        default="",
        help=f"Path to {DATASET_DATA_FILE}; defaults to it under --dataset-root",
    )
    parser.add_argument("--repo-id", default=DATASET_REPO_ID)
    parser.add_argument("--revision", default=DATASET_REVISION)
    parser.add_argument("--output", default=str(MANIFEST_PATH))
    parser.add_argument(
        "--check",
        action="store_true",
        help="Rebuild in memory and report whether the committed file matches",
    )
    args = parser.parse_args()

    dataset_root = Path(args.dataset_root).resolve()
    parquet_path = (
        Path(args.parquet).resolve()
        if args.parquet
        else dataset_root.joinpath(*PurePosixPath(DATASET_DATA_FILE).parts)
    )
    if not parquet_path.is_file():
        raise SystemExit(f"no dataset file at {parquet_path}")

    manifest = build_manifest(
        parquet_path,
        dataset_root,
        repo_id=args.repo_id,
        revision=args.revision,
    )
    rendered = _serialize(manifest)
    output = Path(args.output)

    if args.check:
        if not output.is_file():
            print(f"no committed manifest at {output}", file=sys.stderr)
            return 1
        if output.read_text(encoding="utf-8") != rendered:
            print(
                f"the committed manifest at {output} no longer matches the "
                "dataset it says it was built from",
                file=sys.stderr,
            )
            return 1
        print(
            f"{output} matches {args.repo_id} at {args.revision}: "
            f"{manifest['file_count']} file(s) across "
            f"{manifest['gold_bearing_task_count']} of "
            f"{manifest['task_count']} task(s)"
        )
        return 0

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(
        f"Wrote {output}: {manifest['file_count']} file(s), "
        f"{manifest['total_bytes']} byte(s) across "
        f"{manifest['gold_bearing_task_count']} of {manifest['task_count']} task(s)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
