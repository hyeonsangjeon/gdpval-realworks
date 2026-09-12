#!/usr/bin/env python3
"""Replay a run record's deliverable-selection stage offline.

The grader picks which produced files to judge *before* it calls any model
(`Grader._select_deliverables` -> `select_deliverables`). That stage is
deterministic and free, so the question "how many of this run's tasks will
actually reach the judge?" is answerable without dispatching a paid grading
run -- and answerable *before* one, which is when a prediction is worth
anything.

This is not a proxy for the selector. It calls the same function with the
same five arguments the production path builds:

    task_id           the run record's manifest
    deliverable_files the run record's manifest (relative names, as
                      `Grader._relative_file_name` yields them)
    reference_files   the pinned rubric parquet
    instruction       the pinned rubric parquet's `prompt`
    rubric_items      the pinned rubric parquet's `rubric_json`

`deliverable_summary` is omitted, matching production, which leaves the
summary-named-candidate path disabled.

A task whose selection does not end `ok` takes exactly **zero** judge calls.
That is not an inference; `--check-reference` verifies it in both directions
against a committed grade payload.

Usage
-----
    python scripts/replay_deliverable_selection.py \
        docs/run_records/<record>/deliverable_manifest.json \
        --rubric-revision <40-hex HF commit sha> \
        [--snapshot <already-downloaded snapshot dir>] \
        [--check-reference <committed grade payload>.json]

Without `--snapshot` the pinned snapshot is fetched through the production
`RubricLoader` into `data/gdpval-local/rubric_snapshots/<sha>/`, which needs
network access on the first run. Pass `--snapshot` to reuse a copy that is
already on disk (for example under the standard `huggingface_hub` cache).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.deliverable_selector import select_deliverables  # noqa: E402
from core.rubric_loader import RubricLoader, TaskRubric  # noqa: E402


def load_tasks(revision: str, snapshot: Path | None) -> dict[str, TaskRubric]:
    loader = RubricLoader(revision=revision)
    if snapshot is None:
        return {task.task_id: task for task in loader.load_all()}
    # Same parquet, already on disk. `rubric_sha` is pinned rather than
    # resolved so that no network call is needed to read a local snapshot.
    loader._sha = revision.lower()
    return loader._load_tasks_from_parquet(snapshot)


def check_reference(payload: Path) -> None:
    """A non-ok selection means 0 judge calls -- verified, not assumed."""
    rows = json.loads(payload.read_text())["tasks"]
    not_ok = [r["judge_call_count"] for r in rows if r.get("selection_status") != "ok"]
    ok_at_zero = [
        r["task_id"]
        for r in rows
        if r.get("selection_status") == "ok" and r["judge_call_count"] == 0
    ]
    print(
        f"{payload.name}: {len(rows)} tasks, {len(not_ok)} non-ok selections, "
        f"max judge calls among them = {max(not_ok) if not_ok else 'n/a'}, "
        f"ok-selection tasks at 0 calls = {len(ok_at_zero)}"
    )
    if (not_ok and max(not_ok) != 0) or ok_at_zero:
        print("  -> selection status does NOT imply the judge-call count here.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="deliverable_manifest.json")
    parser.add_argument(
        "--rubric-revision",
        required=True,
        help="40-character HF commit sha of the pinned openai/gdpval revision",
    )
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=None,
        help="reuse an already-downloaded snapshot directory instead of fetching",
    )
    parser.add_argument(
        "--check-reference",
        type=Path,
        action="append",
        default=[],
        help="committed grade payload to verify selection-status vs judge calls",
    )
    args = parser.parse_args()

    for payload in args.check_reference:
        check_reference(payload)
    if args.check_reference:
        print()

    tasks = load_tasks(args.rubric_revision, args.snapshot)
    manifest = json.loads(args.manifest.read_text())
    print(f"pinned rubric snapshot: {len(tasks)} tasks")
    print(f"record tasks with deliverables: {len(manifest)}\n")

    blocked = []
    rules: dict[str, int] = {}
    for task_id in sorted(manifest):
        task = tasks[task_id]
        selection = select_deliverables(
            task_id=task_id,
            deliverable_files=[f["name"] for f in manifest[task_id]],
            reference_files=task.reference_files,
            instruction=task.prompt,
            rubric_items=task.rubric_items,
        )
        if selection.selection_status == "ok":
            rules[selection.selection_rule] = rules.get(selection.selection_rule, 0) + 1
        else:
            blocked.append((task_id, selection, len(manifest[task_id])))

    reaching = len(manifest) - len(blocked)
    print(f"=== {reaching} reach the judge / {len(blocked)} take 0 judge calls ===\n")
    for task_id, selection, file_count in blocked:
        items = len(tasks[task_id].rubric_items)
        print(f"  {task_id[:8]}  {selection.selection_status}  {selection.selection_rule}")
        print(f"      error: {selection.selection_error}")
        print(f"      files produced: {file_count}   rubric items forgone: {items}")

    if rules:
        print("\n=== selection rules used by the tasks that cleared ===")
        for rule, count in sorted(rules.items(), key=lambda kv: -kv[1]):
            print(f"  {count:3d}  {rule}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
