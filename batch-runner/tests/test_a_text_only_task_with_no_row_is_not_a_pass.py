"""A task the submission has no row for is missing, even when it owed no file.

``step5_validate`` gained an absence check for file-required tasks, and that
check was deliberately scoped to them. This is the other half, declared as a
known gap when the first half merged: a task the manifest lists as text-only
never entered any count, so a full submission that dropped one and let a
substitute take its row passed every gate.

Nothing else notices. ``_task_scope_errors`` compares IDs only when the scope
carries them, and ``_load_expected_task_scope`` returns ``task_ids=None`` for a
full run — so full mode had a row count and nothing more, and a substitution
keeps the count at 220. The duplicate check sees one row per ID. The file counts
skip the task by definition.

The manifest is what makes the check possible.
``core.repo_bootstrapper._generate_manifest_from_dir`` writes one entry per
source parquet row and refuses to emit a manifest whose ordered task IDs do not
hash to ``CANONICAL_ORDERED_TASK_IDS_SHA256``. Every key in it is therefore a
canonical task the submission is required to carry, whether or not it owes a
file, so an absent one is an integrity break rather than a legitimate state.

Pinned here:

* a text-only task with no row fails the gate, in its own words;
* it does not disturb the file counts — the two checks stay independent;
* the row count alone never noticed, which is why the check had to be added;
* both kinds of absence are reported once each, not folded together;
* a subset run still passes with the unselected tasks absent, which is normal;
* a submission with no task_id column gets no stats file rather than zeros;
* a submission carrying every task keeps its verdict, counts and wording.
"""

import json
from pathlib import Path

import pandas as pd

import step5_validate as step5

_FULL_ROW_COUNT = 220
_TICK = "file-required tasks have deliverable files ✓"

# task-000 and task-001 owe files; task-002 owes none. The remaining 217 rows
# are padding that keeps the submission at the row count a full run expects.
_MANIFEST_NEEDS = {"task-000": True, "task-001": True, "task-002": False}


def _canonical_ids() -> list[str]:
    return [f"task-{index:03d}" for index in range(_FULL_ROW_COUNT)]


def _write_parquet(
    upload: Path,
    task_ids: list[str],
    with_files: set[str],
    *,
    include_task_id: bool = True,
) -> None:
    """Write a submission parquet, giving each ``with_files`` task one file."""
    data_dir = upload / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (upload / "deliverable_files").mkdir(exist_ok=True)

    files = []
    for task_id in task_ids:
        if task_id not in with_files:
            files.append([])
            continue
        relative = f"deliverable_files/{task_id}.docx"
        (upload / relative).write_bytes(b"deliverable")
        files.append([relative])

    empty = [[] for _ in task_ids]
    columns = {
        "task_id": task_ids,
        "sector": ["Information"] * len(task_ids),
        "occupation": ["Analyst"] * len(task_ids),
        "prompt": ["Write something"] * len(task_ids),
        "reference_files": empty,
        "reference_file_urls": [[] for _ in task_ids],
        "reference_file_hf_uris": [[] for _ in task_ids],
        "deliverable_text": ["done"] * len(task_ids),
        "deliverable_files": files,
        "deliverable_file_urls": [[] for _ in task_ids],
        "deliverable_file_hf_uris": [[] for _ in task_ids],
    }
    if not include_task_id:
        del columns["task_id"]
    pd.DataFrame(columns).to_parquet(
        data_dir / "train-00000-of-00001.parquet", index=False
    )


def _prepare(
    tmp_path: Path,
    *,
    row_ids: list[str],
    scope: dict,
    manifest_needs: dict[str, bool] = None,
    with_files: set[str] = frozenset({"task-000", "task-001"}),
    include_task_id: bool = True,
) -> tuple[Path, Path]:
    workspace = tmp_path / "workspace"
    upload = workspace / "upload"
    workspace.mkdir(parents=True, exist_ok=True)
    _write_parquet(
        upload, row_ids, set(with_files), include_task_id=include_task_id
    )
    (workspace / "step1_tasks_prepared.json").write_text(
        json.dumps({"task_scope": scope}), encoding="utf-8"
    )
    (workspace / "step0_needs_files_manifest.json").write_text(
        json.dumps({
            "tasks": {
                task_id: {"needs_files": needed}
                for task_id, needed in (manifest_needs or _MANIFEST_NEEDS).items()
            },
            "_summary": {"active_policy": "deliverable_only"},
        }),
        encoding="utf-8",
    )
    return workspace, upload


def _run(monkeypatch, workspace: Path, upload: Path) -> tuple[bool, dict | None]:
    monkeypatch.setattr(step5, "WORKSPACE_DIR", workspace)
    monkeypatch.setattr(step5, "UPLOAD_DIR", upload)
    passed = step5.validate(data_dir=str(upload))
    stats_path = workspace / "validate_stats.json"
    if not stats_path.exists():
        return passed, None
    return passed, json.loads(stats_path.read_text(encoding="utf-8"))


_FULL_SCOPE = {"mode": "full", "expected_count": _FULL_ROW_COUNT}


def _substituted(tmp_path: Path, index: int) -> tuple[Path, Path]:
    """A full submission where a substitute row took one canonical task's place."""
    row_ids = _canonical_ids()
    row_ids[index] = f"substitute-for-{row_ids[index]}"
    return _prepare(tmp_path, row_ids=row_ids, scope=_FULL_SCOPE)


def _all_present(tmp_path: Path) -> tuple[Path, Path]:
    return _prepare(tmp_path, row_ids=_canonical_ids(), scope=_FULL_SCOPE)


# ── Tests ──────────────────────────────────────────────────────────────────


def test_a_text_only_task_with_no_row_fails_the_gate(tmp_path, monkeypatch, capsys):
    passed, _ = _run(monkeypatch, *_substituted(tmp_path, 2))
    out = capsys.readouterr().out

    assert passed is False
    assert "Validation FAILED" in out
    assert "1 text-only tasks are absent from the submission" in out
    assert "the manifest lists them and no row carries them" in out
    assert "task-002" in out


def test_the_file_counts_are_untouched_by_a_text_only_absence(tmp_path, monkeypatch):
    """The two checks stay independent: a text-only absence is not a file event."""
    _, healthy = _run(monkeypatch, *_all_present(tmp_path / "healthy"))
    _, substituted = _run(monkeypatch, *_substituted(tmp_path / "substituted", 2))

    keys = ("needs_files_total", "files_succeeded", "files_failed", "files_absent")
    assert {k: substituted[k] for k in keys} == {k: healthy[k] for k in keys}
    assert substituted["files_absent"] == 0
    assert substituted["absent_task_ids"] == []


def test_the_row_count_alone_does_not_notice_the_substitution(
    tmp_path, monkeypatch, capsys
):
    """Why the check had to be added: every older gate is still satisfied."""
    _run(monkeypatch, *_substituted(tmp_path, 2))
    out = capsys.readouterr().out

    assert f"Rows: {_FULL_ROW_COUNT}" in out
    assert "Row count:" not in out          # the count check is satisfied
    assert "duplicate task_id" not in out   # so is the uniqueness check
    assert f"All 2 {_TICK}" in out          # and both file-required tasks are fine


def test_both_kinds_of_absence_are_reported_separately(tmp_path, monkeypatch, capsys):
    """One file-required and one text-only task gone — two errors, no overlap."""
    row_ids = _canonical_ids()
    row_ids[1] = "substitute-for-task-001"
    row_ids[2] = "substitute-for-task-002"
    passed, stats = _run(
        monkeypatch, *_prepare(tmp_path, row_ids=row_ids, scope=_FULL_SCOPE)
    )
    out = capsys.readouterr().out

    assert passed is False
    assert "1 file-required tasks are absent from the submission" in out
    assert "1 text-only tasks are absent from the submission" in out
    assert stats["files_absent"] == 1
    assert stats["absent_task_ids"] == ["task-001"]
    assert _TICK not in out


def test_a_subset_run_still_passes_with_the_unselected_tasks_absent(
    tmp_path, monkeypatch, capsys
):
    """A subset submission carries only its own rows; the manifest lists all 220."""
    selected = ["task-000", "task-001"]
    passed, stats = _run(monkeypatch, *_prepare(
        tmp_path,
        row_ids=selected,
        scope={
            "mode": "explicit_ids",
            "expected_count": len(selected),
            "task_ids": selected,
        },
    ))
    out = capsys.readouterr().out

    assert passed is True
    assert "Validation PASSED" in out
    assert "text-only tasks are absent" not in out
    assert (stats["needs_files_total"], stats["files_succeeded"]) == (2, 2)


def test_a_submission_with_no_task_ids_gets_no_stats_rather_than_zeros(
    tmp_path, monkeypatch, capsys
):
    """Nothing could be cross-checked, so nothing is recorded as having been."""
    passed, stats = _run(monkeypatch, *_prepare(
        tmp_path,
        row_ids=_canonical_ids(),
        scope=_FULL_SCOPE,
        include_task_id=False,
    ))
    out = capsys.readouterr().out

    assert passed is False
    assert "Missing required columns" in out
    assert stats is None
    assert _TICK not in out


def test_a_submission_carrying_every_task_is_unchanged(tmp_path, monkeypatch, capsys):
    """새로운 기준이 기존 실험에 영향을 미치면 안 된다 — verdict, counts and wording."""
    passed, stats = _run(monkeypatch, *_all_present(tmp_path))
    out = capsys.readouterr().out

    assert passed is True
    assert "Validation PASSED" in out
    assert f"All 2 {_TICK}" in out
    assert "absent from the submission" not in out
    assert (stats["needs_files_total"], stats["files_succeeded"]) == (2, 2)
    assert (stats["files_failed"], stats["files_absent"]) == (0, 0)
