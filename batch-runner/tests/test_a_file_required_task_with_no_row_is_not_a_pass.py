"""A file-required task the submission has no row for is not a pass.

``step5_validate`` cross-checks the needs_files manifest against the parquet it
is about to upload. For every file-required task it looked up the row, read
``deliverable_files``, and counted a success or a failure. A task the submission
carried no row for fell out of both counts — nothing was read for it, so it was
neither — and the summary line was printed from the failure list alone:

    if not needs_files_missing:
        warnings.append(f"All {needs_files_total} file-required tasks have deliverable files ✓")

That is a claim about all N, made from the failures of the ones that were looked
at. With one absent task it printed the same ✓ as a run where every file really
was there, and ``succeeded + failed`` quietly stopped equalling ``total``.

The manifest is not a wish list. ``core.repo_bootstrapper._generate_manifest_from_dir``
builds it from the source parquet and refuses to emit one whose ordered task IDs
do not hash to ``CANONICAL_ORDERED_TASK_IDS_SHA256``, so every key in it is one
of the canonical tasks the submission is required to carry — an absent one is an
integrity break, never a legitimate state. A subset run already failed this
arrangement, through the identity check in ``_task_scope_errors``. Full runs
carry no ``task_ids`` to check against, which is the only reason it could reach
an upload unremarked.

Pinned here:

* the absent task fails the gate, in its own words;
* the ✓ line is printed only when every file-required task was looked at;
* ``succeeded + failed + absent == needs_files_total`` in every arrangement;
* the two healthy arrangements keep their verdict, counts and wording exactly.
"""

import json
from pathlib import Path

import pandas as pd

import step5_validate as step5

_FULL_ROW_COUNT = 220
_TICK = "file-required tasks have deliverable files ✓"


def _canonical_ids() -> list[str]:
    return [f"task-{index:03d}" for index in range(_FULL_ROW_COUNT)]


def _write_parquet(upload: Path, task_ids: list[str], with_files: set[str]) -> None:
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
    pd.DataFrame({
        "task_id": task_ids,
        "sector": ["Information"] * len(task_ids),
        "occupation": ["Analyst"] * len(task_ids),
        "prompt": ["Create a file"] * len(task_ids),
        "reference_files": empty,
        "reference_file_urls": [[] for _ in task_ids],
        "reference_file_hf_uris": [[] for _ in task_ids],
        "deliverable_text": ["done"] * len(task_ids),
        "deliverable_files": files,
        "deliverable_file_urls": [[] for _ in task_ids],
        "deliverable_file_hf_uris": [[] for _ in task_ids],
    }).to_parquet(data_dir / "train-00000-of-00001.parquet", index=False)


def _prepare(
    tmp_path: Path,
    *,
    row_ids: list[str],
    manifest_needs: dict[str, bool],
    with_files: set[str],
    scope: dict,
) -> tuple[Path, Path]:
    workspace = tmp_path / "workspace"
    upload = workspace / "upload"
    workspace.mkdir(parents=True, exist_ok=True)
    _write_parquet(upload, row_ids, with_files)
    (workspace / "step1_tasks_prepared.json").write_text(
        json.dumps({"task_scope": scope}), encoding="utf-8"
    )
    (workspace / "step0_needs_files_manifest.json").write_text(
        json.dumps({
            "tasks": {
                task_id: {"needs_files": needed}
                for task_id, needed in manifest_needs.items()
            },
            "_summary": {"active_policy": "deliverable_only"},
        }),
        encoding="utf-8",
    )
    return workspace, upload


def _run(monkeypatch, workspace: Path, upload: Path) -> tuple[bool, dict]:
    monkeypatch.setattr(step5, "WORKSPACE_DIR", workspace)
    monkeypatch.setattr(step5, "UPLOAD_DIR", upload)
    passed = step5.validate(data_dir=str(upload))
    stats = json.loads(
        (workspace / "validate_stats.json").read_text(encoding="utf-8")
    )
    return passed, stats


# ── The three full-mode arrangements ──────────────────────────────────────
# All 220 canonical rows are present in every one of them; they differ only in
# which file-required task the submission actually carries. ``task-002`` is
# text-only in the manifest, so it must stay out of the file counts.


def _absent(tmp_path: Path) -> tuple[Path, Path]:
    """One canonical file-required task is missing; a substitute took its row."""
    row_ids = _canonical_ids()
    row_ids[1] = "substitute-task"
    return _prepare(
        tmp_path,
        row_ids=row_ids,
        manifest_needs={"task-000": True, "task-001": True, "task-002": False},
        with_files={"task-000"},
        scope={"mode": "full", "expected_count": _FULL_ROW_COUNT},
    )


def _all_present(tmp_path: Path) -> tuple[Path, Path]:
    return _prepare(
        tmp_path,
        row_ids=_canonical_ids(),
        manifest_needs={"task-000": True, "task-001": True, "task-002": False},
        with_files={"task-000", "task-001"},
        scope={"mode": "full", "expected_count": _FULL_ROW_COUNT},
    )


def _one_failed(tmp_path: Path) -> tuple[Path, Path]:
    return _prepare(
        tmp_path,
        row_ids=_canonical_ids(),
        manifest_needs={"task-000": True, "task-001": True, "task-002": False},
        with_files={"task-000"},
        scope={"mode": "full", "expected_count": _FULL_ROW_COUNT},
    )


# ── Tests ──────────────────────────────────────────────────────────────────


def test_a_file_required_task_with_no_row_fails_the_gate(tmp_path, monkeypatch, capsys):
    passed, stats = _run(monkeypatch, *_absent(tmp_path))
    out = capsys.readouterr().out

    assert passed is False
    assert "Validation FAILED" in out
    assert "1 file-required tasks are absent from the submission" in out
    assert "their deliverable files were never checked" in out
    assert "task-001" in out
    assert stats["files_absent"] == 1


def test_the_tick_is_printed_only_when_every_task_was_looked_at(
    tmp_path, monkeypatch, capsys
):
    """The exact defect: both arrangements used to print the same ✓ line."""
    _run(monkeypatch, *_absent(tmp_path / "absent"))
    absent_out = capsys.readouterr().out

    _run(monkeypatch, *_all_present(tmp_path / "all_present"))
    all_present_out = capsys.readouterr().out

    assert _TICK not in absent_out
    assert f"All 2 {_TICK}" in all_present_out


def test_the_parts_add_up_to_the_total_in_every_arrangement(tmp_path, monkeypatch):
    for name, build in (
        ("absent", _absent),
        ("all_present", _all_present),
        ("one_failed", _one_failed),
    ):
        _, stats = _run(monkeypatch, *build(tmp_path / name))
        parts = (
            stats["files_succeeded"] + stats["files_failed"] + stats["files_absent"]
        )
        assert parts == stats["needs_files_total"], name


def test_an_absent_task_is_neither_a_success_nor_a_failure(tmp_path, monkeypatch):
    _, stats = _run(monkeypatch, *_absent(tmp_path))

    assert stats["needs_files_total"] == 2
    assert stats["files_succeeded"] == 1
    assert stats["files_failed"] == 0
    assert stats["files_absent"] == 1
    assert stats["absent_task_ids"] == ["task-001"]


def test_a_run_where_every_task_was_looked_at_is_unchanged(
    tmp_path, monkeypatch, capsys
):
    """새로운 기준이 기존 실험에 영향을 미치면 안 된다 — verdict, counts and wording."""
    passed, stats = _run(monkeypatch, *_all_present(tmp_path / "all_present"))
    out = capsys.readouterr().out

    assert passed is True
    assert "Validation PASSED" in out
    assert f"All 2 {_TICK}" in out
    assert (stats["needs_files_total"], stats["files_succeeded"]) == (2, 2)
    assert (stats["files_failed"], stats["files_absent"]) == (0, 0)

    passed, stats = _run(monkeypatch, *_one_failed(tmp_path / "one_failed"))
    out = capsys.readouterr().out

    assert passed is True
    assert "Validation PASSED" in out
    assert (
        "1 file-required tasks had no files — preserved as failed rows with "
        "empty deliverable fields: ['task-001']"
    ) in out
    assert _TICK not in out
    assert (stats["needs_files_total"], stats["files_succeeded"]) == (2, 1)
    assert (stats["files_failed"], stats["files_absent"]) == (1, 0)


def test_a_subset_run_already_failed_this_arrangement(tmp_path, monkeypatch, capsys):
    """Why full mode was the outlier: subset mode checks the IDs themselves."""
    workspace, upload = _prepare(
        tmp_path,
        row_ids=["task-000", "substitute-task"],
        manifest_needs={"task-000": True, "task-001": True},
        with_files={"task-000"},
        scope={
            "mode": "explicit_ids",
            "expected_count": 2,
            "task_ids": ["task-000", "task-001"],
        },
    )
    passed, stats = _run(monkeypatch, workspace, upload)
    out = capsys.readouterr().out

    assert passed is False
    assert "Task scope mismatch: missing=1, unexpected=1" in out
    assert "1 file-required tasks are absent from the submission" in out
    assert stats["files_absent"] == 1
