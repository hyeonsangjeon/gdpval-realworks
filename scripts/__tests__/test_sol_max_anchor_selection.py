from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
PAYLOAD = (
    REPO_ROOT
    / "data/grades"
    / "exp003_GPT52Chat_baseline_runner_exec__judge_gpt-5_4-mini__rubric_v2_tools_mini.json"
)
CONFIG = (
    REPO_ROOT
    / "batch-runner/grading_configs/validation_exp003_v2_sol_max_anchor4.yaml"
)
# Whole-file, on purpose: every number below was read off this payload, so any
# edit to it invalidates the reasoning until a person re-checks it. That is the
# pin doing its job -- when it goes red, confirm the edit does not touch what
# this test reasons about, then move the pin in the same commit.
#
# Moved once. `b5cbb6a8...` was the content before #188 (2026-08-21) backfilled
# `summary.wow` analytics. That commit's only structural effect on this file was
# `summary.wow.score_density_histogram` going from `[]` to ten buckets -- no
# task, item, verdict, latency or routing field moved, which is why every
# assertion below still holds unchanged. The pin was red on `main` from that
# day until it was re-checked, and nobody saw it, because nothing ran this file
# (see the CI note in test_analyze_grade_run.py).
PAYLOAD_SHA256 = "eb046f77548779dcffdf100cff553fc3b365bbf899a9575a03abbdd7c8e01394"


def _error_type(item: dict) -> str:
    evidence = str(item.get("evidence") or "")
    for error_type in ("final_json_parse_failed", "empty_final_text"):
        if evidence.startswith(error_type):
            return error_type
    return "other"


def test_anchor_tasks_maximize_targetable_mini_errors():
    payload_bytes = PAYLOAD.read_bytes()
    assert hashlib.sha256(payload_bytes).hexdigest() == PAYLOAD_SHA256
    payload = json.loads(payload_bytes)
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    task_ids = config["rerun_identity"]["task_ids"]

    assert payload["schema_version"] == "1.0"
    assert payload.get("config_name") is None
    assert "grader_source_hash" not in payload
    assert all(
        (task.get("perception_call_count") or 0) == 0
        for task in payload["tasks"]
    )
    assert sum(
        item.get("routing_modality") == "visual"
        for task in payload["tasks"]
        for item in task.get("items", [])
    ) == 337
    assert sum(
        item.get("routing_modality") == "audio"
        for task in payload["tasks"]
        for item in task.get("items", [])
    ) == 58

    assert task_ids == [
        "99ac6944-4ec6-4848-959c-a460ac705c6f",
        "4c18ebae-dfaa-4b76-b10c-61fcdf26734c",
        "40a8c4b1-b169-4f92-a38b-7f79685037ec",
        "a73fbc98-90d4-4134-a54f-2b1d0c838791",
    ]
    source_indices = {
        task["task_id"]: index
        for index, task in enumerate(payload["tasks"])
    }
    assert [source_indices[task_id] for task_id in task_ids] == [10, 29, 78, 179]
    selected = [task for task in payload["tasks"] if task["task_id"] in task_ids]
    assert [task["task_id"] for task in selected] == task_ids

    expected_types = {
        "99ac6944-4ec6-4848-959c-a460ac705c6f": Counter({
            "final_json_parse_failed": 2,
            "empty_final_text": 1,
        }),
        "4c18ebae-dfaa-4b76-b10c-61fcdf26734c": Counter({
            "final_json_parse_failed": 5,
            "empty_final_text": 1,
        }),
        "40a8c4b1-b169-4f92-a38b-7f79685037ec": Counter({
            "empty_final_text": 5,
            "final_json_parse_failed": 3,
        }),
        "a73fbc98-90d4-4134-a54f-2b1d0c838791": Counter({
            "final_json_parse_failed": 3,
            "empty_final_text": 2,
        }),
    }
    observed_types = {}
    for task in selected:
        score_included_errors = [
            item
            for item in task["items"]
            if item.get("verdict") == "judge_error"
            and item.get("score_excluded") is not True
        ]
        types = Counter(_error_type(item) for item in score_included_errors)
        assert "other" not in types
        observed_types[task["task_id"]] = types

    assert observed_types == expected_types
    assert sum(sum(types.values()) for types in observed_types.values()) == 22
    assert sum(types["final_json_parse_failed"] for types in observed_types.values()) == 13
    assert sum(types["empty_final_text"] for types in observed_types.values()) == 9
    assert sum(
        item.get("routing_modality") == "visual"
        for task in selected
        for item in task.get("items", [])
    ) == 43
    assert sum(
        item.get("routing_modality") == "audio"
        for task in selected
        for item in task.get("items", [])
    ) == 13
    assert sum(task["judge_call_count"] for task in selected) == 234
    assert sum(task["judge_total_latency_ms"] for task in selected) / 1000 == (
        pytest.approx(2449.19944)
    )

    projection = config["anchor_projection"]
    assert projection["anchor_config_name"] == config["config_name"]
    assert projection["anchor_task_count"] == 4
    assert projection["anchor_ordered_task_ids_sha256"] == (
        "29d5623a5cec85eb38f21fb73a2f3b06c66ed6a5fd6fd95948b979cd70a70bc9"
    )
    assert projection["anchor_source_inference_repo_id"] == (
        "HyeonSang/exp003_GPT52Chat_baseline_runner_exec"
    )
    assert projection["baseline_main_calls"] == 234
    assert projection["baseline_main_latency_ms"] == pytest.approx(2449199.44)
    assert projection["baseline_final_json_parse_failed"] == 13
    assert projection["baseline_empty_final_text"] == 9
    assert projection["anchor_visual_criteria"] == 43
    assert projection["anchor_audio_criteria"] == 13
    assert projection["full_task_count"] == 220
    assert projection["full_visual_criteria"] == 337
    assert projection["full_audio_criteria"] == 58
    assert sum(
        task.get("judge_total_latency_ms", 0) or 0
        for task in payload["tasks"]
    ) == pytest.approx(56_473_083.72)