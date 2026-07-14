import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from core.rubric_loader import RubricLoader


RUBRIC_SHA = "11e7900cdcac61bc4daf59e65feb238acda98fbf"


def _make_loader(
    cache_dir: Path, rows: list[dict], monkeypatch
) -> RubricLoader:
    snapshot_root = cache_dir / RubricLoader.SNAPSHOT_DIRNAME / RUBRIC_SHA
    parquet_path = snapshot_root / "data" / "train-00000-of-00001.parquet"
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    payload = b"fake parquet bytes"
    parquet_path.write_bytes(payload)
    manifest = {
        "schema_version": 1,
        "repo_id": "openai/gdpval",
        "rubric_sha": RUBRIC_SHA,
        "parquet_files": [
            {
                "path": "data/train-00000-of-00001.parquet",
                "sha256": hashlib.sha256(payload).hexdigest(),
                "size": len(payload),
            }
        ],
    }
    (snapshot_root / RubricLoader.MANIFEST_FILENAME).write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    monkeypatch.setattr(
        "core.rubric_loader.pd.read_parquet", lambda path: pd.DataFrame(rows)
    )
    return RubricLoader(revision=RUBRIC_SHA, cache_dir=str(cache_dir))


def _fake_rows(n: int = 220) -> list[dict]:
    rows = []
    for i in range(n):
        rows.append(
            {
                "task_id": f"task-{i:03d}",
                "sector": "Sector",
                "occupation": "Occupation",
                "prompt": "Task prompt",
                "reference_files": [f"reference_files/x{i}.txt"],
                "deliverable_files": [],
                "rubric_pretty": "pretty",
                "rubric_json": [
                    {
                        "rubric_item_id": f"ri-{i}",
                        "criterion": "The submitted deliverable is a .xlsx file",
                        "score": 2,
                        "required": None,
                    }
                ],
            }
        )
    return rows


def test_load_all_returns_220_tasks(tmp_path, monkeypatch):
    loader = _make_loader(tmp_path, _fake_rows(), monkeypatch)
    tasks = loader.load_all()
    assert len(tasks) == 220


def test_all_have_rubric_items(tmp_path, monkeypatch):
    loader = _make_loader(tmp_path, _fake_rows(), monkeypatch)
    tasks = loader.load_all()
    assert all(len(t.rubric_items) > 0 for t in tasks)


def test_gold_is_empty_in_v2(tmp_path, monkeypatch):
    loader = _make_loader(tmp_path, _fake_rows(), monkeypatch)
    tasks = loader.load_all()
    assert sum(len(t.gold_deliverable_files) for t in tasks) == 0


def test_rubric_sha_is_stable(tmp_path):
    loader = RubricLoader(revision=RUBRIC_SHA, cache_dir=str(tmp_path))
    s1 = loader.rubric_sha
    s2 = loader.rubric_sha
    assert s1 == s2


def test_load_single_task(tmp_path, monkeypatch):
    loader = _make_loader(tmp_path, _fake_rows(), monkeypatch)
    task = loader.load("task-000")
    assert task.task_id == "task-000"


def test_load_unknown_task_raises(tmp_path, monkeypatch):
    loader = _make_loader(tmp_path, _fake_rows(), monkeypatch)
    with pytest.raises(KeyError):
        loader.load("unknown-task")


def test_rubric_json_string_parse(tmp_path, monkeypatch):
    rows = _fake_rows(1)
    rows[0]["rubric_json"] = json.dumps(rows[0]["rubric_json"])
    loader = _make_loader(tmp_path, rows, monkeypatch)
    task = loader.load("task-000")
    assert len(task.rubric_items) == 1
