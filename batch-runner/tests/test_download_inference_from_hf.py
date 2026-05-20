import importlib.util
import json
from pathlib import Path

import pandas as pd


def _load_module():
    path = Path("scripts/download_inference_from_hf.py")
    spec = importlib.util.spec_from_file_location("download_inference_from_hf", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build_inference_from_uploaded_parquet(tmp_path):
    module = _load_module()
    parquet = tmp_path / "train-00000-of-00001.parquet"
    pd.DataFrame(
        [
            {
                "task_id": "task-1",
                "deliverable_text": "hello",
                "deliverable_files": ["deliverable_files/task-1/out.txt"],
            },
            {
                "task_id": "task-2",
                "deliverable_text": "",
                "deliverable_files": [],
            },
        ]
    ).to_parquet(parquet, index=False)

    payload = module._build_inference_from_parquet(str(parquet), "exp", "owner/repo")

    assert payload["experiment_id"] == "exp"
    assert payload["source"] == "owner/repo"
    assert [row["task_id"] for row in payload["results"]] == ["task-1", "task-2"]
    assert payload["results"][0]["status"] == "success"
    assert payload["results"][0]["deliverable_files"] == ["deliverable_files/task-1/out.txt"]
    assert payload["results"][1]["status"] == "error"


def test_reconstruct_when_step2_json_missing(monkeypatch, tmp_path):
    module = _load_module()
    parquet = tmp_path / "train.parquet"
    pd.DataFrame(
        [{"task_id": "task-1", "deliverable_text": "hello", "deliverable_files": []}]
    ).to_parquet(parquet, index=False)

    def fake_hf_hub_download(repo_id, repo_type, filename):
        if filename == "step2_inference_results.json":
            raise FileNotFoundError(filename)
        assert filename == "data/train-00000-of-00001.parquet"
        return str(parquet)

    monkeypatch.setattr(module, "hf_hub_download", fake_hf_hub_download)
    out = tmp_path / "step2_inference_results.json"

    module._download_or_reconstruct_inference("exp", "owner/repo", out)

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["results"][0]["task_id"] == "task-1"
    assert payload["results"][0]["status"] == "success"