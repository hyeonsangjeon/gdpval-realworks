import json
from pathlib import Path

import pytest
from jsonschema import ValidationError, validate


def _load_schema() -> dict:
    return json.loads(Path("schemas/grade.schema.json").read_text(encoding="utf-8"))


def _minimal_payload() -> dict:
    return {
        "schema_version": "1.0",
        "experiment_id": "exp998_smoke_baseline_sample",
        "experiment_yaml_name": "exp998_smoke_baseline_sample",
        "inference_model": "gpt-5.2-chat",
        "inference_completed_at": "2026-05-20T00:00:00Z",
        "judge": {
            "provider": "azure_openai",
            "api": "responses",
            "model": "gpt-5.4-pro",
            "deployment": "gpt-5.4-pro",
            "api_version": "2025-04-01-preview",
            "reasoning_effort": "high",
            "temperature": 0,
            "seed": 42,
            "config_name": "default_gpt5pro",
            "config_hash": "0123456789abcdef",
        },
        "rubric": {
            "source": "huggingface",
            "repo_id": "openai/gdpval",
            "revision": "main",
            "commit_sha": "11e7900cdcac61bc4daf59e65feb238acda98fbf",
            "short_sha": "11e7900",
        },
        "prompt": {"template": "prompts/grader_judge.md", "version": "v1"},
        "graded_at": "2026-05-20T00:00:00Z",
        "graded_by": "step8_grade.py",
        "graded_by_version": "0.1.0",
        "tasks": [
            {
                "task_id": "task-1",
                "sector": "s",
                "occupation": "o",
                "items": [
                    {
                        "rubric_item_id": "ri-1",
                        "criterion": "criterion",
                        "max_score": 2,
                        "awarded_score": 2,
                        "verdict": "pass",
                        "decided_by": "precheck",
                        "required": None,
                        "evidence": "evidence",
                        "judge_confidence": None,
                        "judge_latency_ms": None,
                        "precheck_pattern_id": "file_exists_or_name",
                        "judge_raw_response": None,
                    }
                ],
                "total_awarded": 2,
                "total_max": 2,
                "pct": 100,
                "critical_fail": False,
                "gold_referenced": False,
                "judge_call_count": 0,
                "precheck_count": 1,
                "judge_total_latency_ms": 0,
                "judge_input_tokens": 0,
                "judge_output_tokens": 0,
                "error": None,
                "graded_at": "2026-05-20T00:00:00Z",
            }
        ],
        "summary": {
            "total_tasks": 1,
            "graded_tasks": 1,
            "error_tasks": 0,
            "openai_compat": {
                "avg_score_pct": 100,
                "ci_pct": 0,
                "perfect_count": 1,
                "zero_count": 0,
                "partial_count": 0,
                "inconsistent_count": 0,
            },
            "wow": {
                "rubric_item_coverage_avg": 1,
                "critical_item_pass_rate": 1,
                "precheck_pass_rate": 1,
                "judge_pass_rate": 0,
                "judge_error_rate": 0,
                "by_sector": {},
                "by_rubric_category": {},
                "score_density_histogram": [],
                "rubric_severity_curve": [],
            },
            "cost": {
                "total_judge_calls": 0,
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "estimated_cost_usd": 0,
                "total_judge_latency_sec": 0,
            },
        },
    }


def test_minimal_valid_grade_passes_schema():
    validate(instance=_minimal_payload(), schema=_load_schema())


def test_missing_required_field_fails():
    payload = _minimal_payload()
    del payload["judge"]
    with pytest.raises(ValidationError):
        validate(instance=payload, schema=_load_schema())


def test_unknown_verdict_fails():
    payload = _minimal_payload()
    payload["tasks"][0]["items"][0]["verdict"] = "unknown"
    with pytest.raises(ValidationError):
        validate(instance=payload, schema=_load_schema())


def test_pct_must_be_0_to_100():
    payload = _minimal_payload()
    payload["tasks"][0]["pct"] = 101
    with pytest.raises(ValidationError):
        validate(instance=payload, schema=_load_schema())


def test_actual_smoke_output_passes_schema(tmp_path):
    payload = _minimal_payload()
    p = tmp_path / "grade.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    loaded = json.loads(p.read_text(encoding="utf-8"))
    validate(instance=loaded, schema=_load_schema())
