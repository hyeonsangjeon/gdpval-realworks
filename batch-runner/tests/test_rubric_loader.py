import json
from pathlib import Path

import pandas as pd
import pytest

from core.rubric_loader import RubricLoader


def _make_parquet(cache_dir: Path, rows: list[dict]) -> None:
    data_dir = cache_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(data_dir / "train-00000-of-00001.parquet", index=False)


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


def test_load_all_returns_220_tasks(tmp_path):
    _make_parquet(tmp_path, _fake_rows())
    loader = RubricLoader(cache_dir=str(tmp_path))
    tasks = loader.load_all()
    assert len(tasks) == 220


def test_all_have_rubric_items(tmp_path):
    _make_parquet(tmp_path, _fake_rows())
    loader = RubricLoader(cache_dir=str(tmp_path))
    tasks = loader.load_all()
    assert all(len(t.rubric_items) > 0 for t in tasks)


def test_gold_is_empty_in_v2(tmp_path):
    _make_parquet(tmp_path, _fake_rows())
    loader = RubricLoader(cache_dir=str(tmp_path))
    tasks = loader.load_all()
    assert sum(len(t.gold_deliverable_files) for t in tasks) == 0


def test_rubric_sha_is_stable(tmp_path, monkeypatch):
    _make_parquet(tmp_path, _fake_rows())

    class FakeInfo:
        sha = "11e7900cdcac61bc4daf59e65feb238acda98fbf"

    class FakeApi:
        def dataset_info(self, repo_id, revision):
            return FakeInfo()

    monkeypatch.setattr("core.rubric_loader.HfApi", lambda: FakeApi())

    loader = RubricLoader(cache_dir=str(tmp_path))
    s1 = loader.rubric_sha
    s2 = loader.rubric_sha
    assert s1 == s2


def test_load_single_task(tmp_path):
    _make_parquet(tmp_path, _fake_rows())
    loader = RubricLoader(cache_dir=str(tmp_path))
    task = loader.load("task-000")
    assert task.task_id == "task-000"


def test_load_unknown_task_raises(tmp_path):
    _make_parquet(tmp_path, _fake_rows())
    loader = RubricLoader(cache_dir=str(tmp_path))
    with pytest.raises(KeyError):
        loader.load("unknown-task")


def test_rubric_json_string_parse(tmp_path):
    rows = _fake_rows(1)
    rows[0]["rubric_json"] = json.dumps(rows[0]["rubric_json"])
    _make_parquet(tmp_path, rows)

    loader = RubricLoader(cache_dir=str(tmp_path))
    task = loader.load("task-000")
    assert len(task.rubric_items) == 1
