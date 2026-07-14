"""Regression tests for explicit task scope through Steps 4 and 5."""

import json
import sys
from types import ModuleType, SimpleNamespace

import pandas as pd
import pytest
import yaml

import fill_parquet as fill_module
import step4_fill_parquet as step4
import step5_validate as step5


def _task_ids(count: int) -> list[str]:
    return [f"task-{index:03d}" for index in range(count)]


def test_step4_detects_prepared_explicit_scope(tmp_path, monkeypatch):
    selected = _task_ids(50)
    prepared = tmp_path / "step1_tasks_prepared.json"
    prepared.write_text(json.dumps({
        "task_scope": {
            "mode": "explicit_ids",
            "expected_count": 50,
            "task_ids": selected,
        }
    }), encoding="utf-8")
    monkeypatch.setattr(step4, "_PREPARED_JSON", prepared)

    compact, source = step4._detect_compact("")

    assert compact is True
    assert "explicit_ids" in source
    assert step4._selected_task_ids(compact) == selected


@pytest.mark.parametrize(
    ("mode", "expected_compact"),
    [("full", False), ("filtered", True), ("explicit_ids", True)],
)
def test_step4_trusts_prepared_scope_without_config_file(
    tmp_path, monkeypatch, mode, expected_compact
):
    prepared = tmp_path / "step1_tasks_prepared.json"
    prepared.write_text(json.dumps({
        "config_path": "missing-relative-config.yaml",
        "task_scope": {
            "mode": mode,
            "expected_count": 220 if mode == "full" else 50,
            "task_ids": _task_ids(220 if mode == "full" else 50),
        },
    }), encoding="utf-8")
    monkeypatch.setattr(step4, "_PREPARED_JSON", prepared)

    compact, source = step4._detect_compact("")

    assert compact is expected_compact
    assert mode in source


@pytest.mark.parametrize(
    ("sample_size", "expected_compact"),
    [(None, False), (3, True)],
)
def test_step4_legacy_prepared_uses_source_yaml(
    tmp_path, monkeypatch, sample_size, expected_compact
):
    config_path = tmp_path / "legacy.yaml"
    config_path.write_text(yaml.safe_dump({
        "data": {"filter": {"sample_size": sample_size}},
    }), encoding="utf-8")
    prepared = tmp_path / "step1_tasks_prepared.json"
    prepared.write_text(json.dumps({
        "config_path": str(config_path),
    }), encoding="utf-8")
    monkeypatch.setattr(step4, "_PREPARED_JSON", prepared)

    compact, _ = step4._detect_compact("")

    assert compact is expected_compact


def test_fill_parquet_retains_all_50_selected_rows(tmp_path, monkeypatch):
    all_ids = _task_ids(220)
    selected = all_ids[10:60]
    base = pd.DataFrame({
        "task_id": all_ids,
        "reference_files": [[] for _ in all_ids],
        "reference_file_urls": [[] for _ in all_ids],
        "reference_file_hf_uris": [[] for _ in all_ids],
        "deliverable_files": [[] for _ in all_ids],
        "deliverable_file_urls": [[] for _ in all_ids],
        "deliverable_file_hf_uris": [[] for _ in all_ids],
    })
    results = [
        {
            "task_id": task_id,
            "status": "success" if index % 2 == 0 else "error",
            "deliverable_text": "done" if index % 2 == 0 else "",
            "deliverable_files": [],
        }
        for index, task_id in enumerate(selected)
    ]
    result_path = tmp_path / "result.json"
    result_path.write_text(json.dumps({
        "experiment_id": "exp027",
        "results": results,
    }), encoding="utf-8")
    captured = {}
    monkeypatch.setattr(fill_module.pd, "read_parquet", lambda path: base.copy())

    def _capture(frame, path, index=False):
        captured["df"] = frame.copy()

    monkeypatch.setattr(pd.DataFrame, "to_parquet", _capture)

    stats = fill_module.fill_parquet(
        parquet_path=str(tmp_path / "base.parquet"),
        json_path=str(result_path),
        output_path=str(tmp_path / "out.parquet"),
        compact=True,
        selected_task_ids=selected,
    )

    assert stats["output_rows"] == 50
    assert captured["df"]["task_id"].tolist() == selected
    assert set(captured["df"]["task_id"]) == set(selected)


def test_fill_parquet_rejects_result_scope_mismatch(tmp_path, monkeypatch):
    selected = _task_ids(2)
    base = pd.DataFrame({"task_id": _task_ids(3)})
    result_path = tmp_path / "result.json"
    result_path.write_text(json.dumps({
        "results": [{"task_id": selected[0], "status": "success"}],
    }), encoding="utf-8")
    monkeypatch.setattr(fill_module.pd, "read_parquet", lambda path: base.copy())

    try:
        fill_module.fill_parquet(
            parquet_path="base.parquet",
            json_path=str(result_path),
            dry_run=True,
            compact=True,
            selected_task_ids=selected,
        )
    except ValueError as exc:
        assert "results=1, selected=2" in str(exc)
    else:
        raise AssertionError("scope mismatch must fail")


def test_fill_parquet_rejects_duplicate_result_task_ids(tmp_path, monkeypatch):
    selected = _task_ids(2)
    base = pd.DataFrame({"task_id": selected})
    result_path = tmp_path / "result.json"
    result_path.write_text(json.dumps({
        "results": [
            {"task_id": selected[0], "status": "success"},
            {"task_id": selected[0], "status": "error"},
            {"task_id": selected[1], "status": "success"},
        ],
    }), encoding="utf-8")
    monkeypatch.setattr(fill_module.pd, "read_parquet", lambda path: base.copy())

    try:
        fill_module.fill_parquet(
            parquet_path="base.parquet",
            json_path=str(result_path),
            dry_run=True,
            compact=True,
            selected_task_ids=selected,
        )
    except ValueError as exc:
        assert str(exc) == "result task IDs must be unique"
    else:
        raise AssertionError("duplicate result task IDs must fail")


def test_step5_accepts_exact_50_row_scope_and_rejects_contamination():
    selected = _task_ids(50)
    scope = {
        "mode": "explicit_ids",
        "expected_count": 50,
        "task_ids": selected,
    }

    assert step5._task_scope_errors(selected, scope) == []

    contaminated = selected[:-1] + ["unselected-task"]
    assert step5._task_scope_errors(contaminated, scope) == [
        "Task scope mismatch: missing=1, unexpected=1"
    ]


def test_step5_validate_accepts_exact_50_row_subset(tmp_path, monkeypatch):
    selected = _task_ids(50)
    workspace = tmp_path / "workspace"
    upload = workspace / "upload"
    data_dir = upload / "data"
    deliverable_dir = upload / "deliverable_files"
    data_dir.mkdir(parents=True)
    deliverable_dir.mkdir(parents=True)
    (data_dir / "train-000.parquet").touch()
    (workspace / "step1_tasks_prepared.json").write_text(json.dumps({
        "task_scope": {
            "mode": "explicit_ids",
            "expected_count": 50,
            "task_ids": selected,
        }
    }), encoding="utf-8")

    frame = pd.DataFrame({
        "task_id": selected,
        "sector": ["Information"] * 50,
        "occupation": ["Analyst"] * 50,
        "prompt": ["task"] * 50,
        "reference_files": [[] for _ in selected],
        "reference_file_urls": [[] for _ in selected],
        "reference_file_hf_uris": [[] for _ in selected],
        "deliverable_text": ["done"] * 50,
        "deliverable_files": [[] for _ in selected],
        "deliverable_file_urls": [[] for _ in selected],
        "deliverable_file_hf_uris": [[] for _ in selected],
    })

    class _FakeTable:
        def to_pandas(self):
            return frame.copy()

    pyarrow = ModuleType("pyarrow")
    pyarrow.__path__ = []
    pyarrow.concat_tables = lambda tables: _FakeTable()
    pyarrow.Table = SimpleNamespace(from_pandas=lambda data, preserve_index=False: data)
    parquet = ModuleType("pyarrow.parquet")
    parquet.read_table = lambda path: _FakeTable()
    parquet.write_table = lambda table, path: None
    monkeypatch.setitem(sys.modules, "pyarrow", pyarrow)
    monkeypatch.setitem(sys.modules, "pyarrow.parquet", parquet)
    monkeypatch.setattr(step5, "WORKSPACE_DIR", workspace)
    monkeypatch.setattr(step5, "UPLOAD_DIR", upload)
    monkeypatch.setattr(step5, "DELIVERABLE_DIR", deliverable_dir)

    assert step5.validate(data_dir=str(upload)) is True