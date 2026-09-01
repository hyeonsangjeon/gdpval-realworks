#!/usr/bin/env python3
"""Create the preregistered agentic task subset from outcome-free JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core.agentic_selector import (  # noqa: E402
    assert_outcome_free_checkout,
    build_selection_manifest,
    select_agentic_tasks,
    resolve_outcome_free_file,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-json", required=True)
    parser.add_argument("--rubric-json", required=True)
    parser.add_argument("--dataset-repo", required=True)
    parser.add_argument("--dataset-sha", required=True)
    parser.add_argument("--rubric-repo", required=True)
    parser.add_argument("--rubric-sha", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--outcome-free-root", required=True)
    args = parser.parse_args()

    root = Path(args.outcome_free_root).resolve()
    source_commit = assert_outcome_free_checkout(root)
    dataset_path = resolve_outcome_free_file(
        root, args.dataset_json, "dataset JSON"
    )
    rubric_path = resolve_outcome_free_file(
        root, args.rubric_json, "rubric JSON"
    )
    selector_path = resolve_outcome_free_file(
        root,
        "batch-runner/core/agentic_selector.py",
        "selector source",
    )
    records = json.loads(dataset_path.read_text(encoding="utf-8"))
    rubrics = json.loads(rubric_path.read_text(encoding="utf-8"))
    selection = select_agentic_tasks(
        records, rubrics, dataset_sha=args.dataset_sha
    )
    manifest = build_selection_manifest(
        selection,
        dataset_repo=args.dataset_repo,
        dataset_sha=args.dataset_sha,
        rubric_repo=args.rubric_repo,
        rubric_sha=args.rubric_sha,
        dataset_path=dataset_path,
        rubric_path=rubric_path,
        selector_path=selector_path,
        repository_root=root,
        source_commit=source_commit,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()