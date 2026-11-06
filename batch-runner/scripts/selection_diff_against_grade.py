#!/usr/bin/env python3
"""Which tasks of a published grade would the current selector select differently?

Offline and model-free. For every task row of a committed grade payload it
rebuilds the file list the selector was handed (primary paths + support
artifacts + echoed reference files, as the row recorded them), calls
``core.deliverable_selector.select_deliverables`` with the five arguments
``Grader._select_deliverables`` passes (core/grader.py, no deliverable
summary), and compares the replay with the selection the grade recorded.

A task differs when its selection status, rule, ordered primary paths,
support set or echoed-reference set differs. Only those tasks are graded
differently by today's code; every other task would be shown to the judge
exactly as before. The ordered list of differing task ids, in the grade's own
task order, is what a parity regrade config pins in
``rerun_identity.task_ids``, and its step 8 ordered-task-ids SHA-256 is the
diagnostic directory the regrade will write under.

Usage
-----
    python scripts/selection_diff_against_grade.py \
        <committed grade>.json \
        --rubric-revision <40-hex openai/gdpval commit> \
        [--snapshot <dir holding data/*.parquet>] \
        [--json-out <file>]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.deliverable_selector import select_deliverables  # noqa: E402
from scripts.replay_deliverable_selection import load_tasks  # noqa: E402
from step8_grade import _ordered_task_ids_sha256  # noqa: E402

SELECTOR = Path(__file__).resolve().parent.parent / "core" / "deliverable_selector.py"


def recorded_files(row: dict[str, Any]) -> list[str]:
    """The relative file names the selector saw when this row was graded."""
    selection = row.get("selected_deliverables") or {}
    files: list[str] = []
    for target in selection.get("primary_targets") or []:
        files.extend(target.get("paths") or [])
    files.extend(selection.get("support_artifacts") or [])
    files.extend(selection.get("reference_files_excluded") or [])
    if len(files) != len(set(files)):
        raise ValueError(f"{row.get('task_id')}: a file is recorded twice")
    return files


def _key(status: Any, rule: Any, primaries: list[list[str]], support: list[str], echoed: list[str]) -> dict:
    return {
        "selection_status": status,
        "selection_rule": rule,
        "primary_paths": [list(paths) for paths in primaries],
        "support_artifacts": sorted(support),
        "reference_files_excluded": sorted(echoed),
    }


def recorded_key(row: dict[str, Any]) -> dict:
    selection = row.get("selected_deliverables") or {}
    return _key(
        selection.get("selection_status"),
        selection.get("selection_rule"),
        [target.get("paths") or [] for target in selection.get("primary_targets") or []],
        selection.get("support_artifacts") or [],
        selection.get("reference_files_excluded") or [],
    )


def replayed_key(selection: Any) -> dict:
    return _key(
        selection.selection_status,
        selection.selection_rule,
        [list(target.paths) for target in selection.primary_targets],
        list(selection.support_artifacts),
        list(selection.reference_files_excluded),
    )


def diff(grade: dict[str, Any], tasks: dict[str, Any], refused_both: list[dict[str, Any]] | None = None,
         ) -> list[dict[str, Any]]:
    """Tasks the judge would now be shown differently, in the grade's task order.

    A task refused both before and after is left out (and listed in
    ``refused_both`` when given): the judge sees nothing either way and the
    task keeps its zero, whatever detail of the refusal moved.
    """
    changed = []
    for row in grade["tasks"]:
        task = tasks[row["task_id"]]
        replay = select_deliverables(
            task_id=task.task_id,
            deliverable_files=recorded_files(row),
            reference_files=task.reference_files,
            instruction=task.prompt,
            rubric_items=task.rubric_items,
        )
        before, after = recorded_key(row), replayed_key(replay)
        if before == after:
            continue
        entry = {
            "task_id": row["task_id"],
            "rubric_items": len(row.get("items") or []),
            "recorded_error": row.get("error"),
            "recorded": before,
            "replayed": after,
        }
        if before["selection_status"] != "ok" and after["selection_status"] != "ok":
            if refused_both is not None:
                refused_both.append(entry)
            continue
        changed.append(entry)
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("grade", type=Path)
    parser.add_argument("--rubric-revision", required=True)
    parser.add_argument("--snapshot", type=Path, default=None)
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args()

    raw = args.grade.read_bytes()
    grade = json.loads(raw)
    if (grade.get("rubric") or {}).get("commit_sha") != args.rubric_revision:
        raise SystemExit("the grade was not graded against this rubric revision")
    tasks = load_tasks(args.rubric_revision, args.snapshot)
    refused_both: list[dict[str, Any]] = []
    changed = diff(grade, tasks, refused_both)
    ordered = [entry["task_id"] for entry in changed]
    record = {
        "schema": "selection-diff-v1",
        "grade_file": args.grade.name,
        "grade_sha256": hashlib.sha256(raw).hexdigest(),
        "grade_experiment_id": grade.get("experiment_id"),
        "grade_source_inference_revision": grade.get("source_inference_revision"),
        "grade_grader_source_hash": grade.get("grader_source_hash"),
        "rubric_revision": args.rubric_revision,
        "selector_sha256": hashlib.sha256(SELECTOR.read_bytes()).hexdigest(),
        "tasks_in_grade": len(grade["tasks"]),
        "changed": changed,
        "refused_before_and_after": refused_both,
        "ordered_task_ids": ordered,
        "ordered_task_ids_sha256": _ordered_task_ids_sha256(ordered) if ordered else None,
        "rubric_items": sum(entry["rubric_items"] for entry in changed),
    }
    for entry in changed:
        print(f"{entry['task_id']}  items={entry['rubric_items']:3d}  "
              f"{entry['recorded']['selection_status']}/{entry['recorded']['selection_rule']}"
              f" -> {entry['replayed']['selection_status']}/{entry['replayed']['selection_rule']}")
        print(f"    primaries {entry['recorded']['primary_paths']} -> {entry['replayed']['primary_paths']}")
    for entry in refused_both:
        print(f"{entry['task_id']}  refused before and after "
              f"({entry['recorded']['selection_rule']} -> {entry['replayed']['selection_rule']}); not regraded")
    print(f"changed {len(changed)} of {len(grade['tasks'])} tasks, {record['rubric_items']} rubric items; "
          f"ordered_task_ids_sha256={record['ordered_task_ids_sha256']}")
    if args.json_out:
        args.json_out.write_text(json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
