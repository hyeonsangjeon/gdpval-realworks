"""Tests for grade-aware narrative integration."""

import json
import os
from pathlib import Path

from core.narrative_analyzer import NarrativeAnalyzer
import step6_report


def _minimal_grade(model: str = "gpt-5.4-pro", avg: float = 67.4) -> dict:
    return {
        "schema_version": "1.0",
        "judge": {
            "model": model,
            "reasoning_effort": "high",
            "temperature": 0,
        },
        "rubric": {
            "repo_id": "openai/gdpval",
            "short_sha": "11e7900",
        },
        "prompt": {"version": "v1"},
        "graded_at": "2026-05-20T12:34:56Z",
        "summary": {
            "total_tasks": 5,
            "openai_compat": {
                "avg_score_pct": avg,
                "ci_pct": 4.2,
                "perfect_count": 1,
                "zero_count": 1,
                "total_tasks": 5,
            },
            "wow": {
                "critical_item_pass_rate": 0.71,
                "precheck_pass_rate": 0.92,
                "judge_pass_rate": 0.64,
                "by_sector": {
                    "Information": {
                        "avg_pct": 71.2,
                        "critical_item_pass_rate": 0.75,
                        "precheck_pass_rate": 0.91,
                        "judge_pass_rate": 0.68,
                        "task_count": 2,
                    },
                    "Finance": {
                        "avg_pct": 42.5,
                        "critical_item_pass_rate": 0.55,
                        "precheck_pass_rate": 0.87,
                        "judge_pass_rate": 0.43,
                        "task_count": 1,
                    },
                    "Healthcare": {
                        "avg_pct": 85.0,
                        "critical_item_pass_rate": 0.82,
                        "precheck_pass_rate": 0.96,
                        "judge_pass_rate": 0.77,
                        "task_count": 1,
                    },
                    "Retail": {
                        "avg_pct": 63.9,
                        "critical_item_pass_rate": 0.68,
                        "precheck_pass_rate": 0.89,
                        "judge_pass_rate": 0.59,
                        "task_count": 1,
                    },
                },
            },
        },
    }


def _make_analyzer() -> NarrativeAnalyzer:
    analyzer = NarrativeAnalyzer.__new__(NarrativeAnalyzer)
    analyzer.client = None
    analyzer.model = "gpt-5.4-pro"
    analyzer._heartbeat_active = False
    analyzer._heartbeat_thread = None
    analyzer._start_heartbeat = lambda: None
    analyzer._stop_heartbeat = lambda: None
    return analyzer


def _inputs() -> tuple[dict, dict, list[dict], list[dict], list[dict]]:
    data = {
        "meta": {
            "experiment_id": "exp_test",
            "experiment_name": "Test Experiment",
            "model": "gpt-5.4",
        }
    }
    summary = {
        "total_tasks": 2,
        "success_count": 2,
        "success_rate_pct": 100.0,
        "error_count": 0,
        "retried_count": 0,
        "avg_qa_score": 8.0,
        "min_qa_score": 7,
        "max_qa_score": 9,
        "avg_latency_ms": 1234,
    }
    sectors = [
        {
            "sector": "Information",
            "success": 2,
            "total": 2,
            "avg_qa_score": 8.0,
            "avg_latency_ms": 1234,
        }
    ]
    task_results = [
        {
            "task_id": "task-1",
            "sector": "Information",
            "occupation": "Analyst",
            "status": "success",
        }
    ]
    return data, summary, sectors, task_results, []


def _capture_analyze_prompts(grade: dict | None) -> list[tuple[str, str]]:
    analyzer = _make_analyzer()
    captured: list[tuple[str, str]] = []

    def fake_call(system_prompt: str, user_prompt: str, max_output_tokens: int = 4096):
        captured.append((system_prompt, user_prompt))
        if "CONTEXT FROM PRIOR ANALYSIS:" in user_prompt:
            return (
                json.dumps({
                    "failure_patterns": "No failures.",
                    "recommendations": "Keep configuration stable.",
                }),
                1.0,
                10,
                5,
            )
        return (
            json.dumps({
                "overview": "Overview.",
                "quality_analysis": "Quality.",
            }),
            1.0,
            10,
            5,
        )

    analyzer._call_responses_api = fake_call
    analyzer.analyze(*_inputs(), grade=grade)
    return captured


def test_analyze_without_grade_uses_legacy_guard():
    captured = _capture_analyze_prompts(grade=None)
    all_user_prompts = "\n".join(user for _, user in captured)

    assert "Grading scores do NOT exist yet" in all_user_prompts
    assert "Grading scores ARE available" not in all_user_prompts
    assert "GRADING RESULTS" not in all_user_prompts


def test_analyze_with_grade_includes_grading_results_section():
    grade = _minimal_grade()
    captured = _capture_analyze_prompts(grade=grade)
    all_user_prompts = "\n".join(user for _, user in captured)

    assert "GRADING RESULTS" in all_user_prompts
    assert grade["judge"]["model"] in all_user_prompts
    assert "Grading scores do NOT exist yet" not in all_user_prompts


def test_overview_mentions_judge_model_and_rubric_source():
    grade = _minimal_grade()
    captured = _capture_analyze_prompts(grade=grade)
    call1_prompt = "\n".join(captured[0])

    assert "automated LLM-judge" in call1_prompt
    assert "open-sourced GDPval rubrics" in call1_prompt
    assert grade["judge"]["model"] in call1_prompt
    assert grade["rubric"]["short_sha"] in call1_prompt


def test_overview_does_not_claim_human_evaluation():
    grade = _minimal_grade()
    captured = _capture_analyze_prompts(grade=grade)
    all_prompts = "\n".join(system + "\n" + user for system, user in captured)

    assert "human evaluation" not in all_prompts.lower()
    assert "official OpenAI grade" not in all_prompts
    assert "human-graded" not in all_prompts


def test_load_grade_skips_dummy_files(tmp_path, monkeypatch):
    exp_id = "exp_test"
    dummy = _minimal_grade(model="dummy-model")
    dummy["_meta"] = {"is_dummy": True}
    real = _minimal_grade(model="real-model")

    (tmp_path / f"{exp_id}__a__sha__v1.json").write_text(json.dumps(dummy))
    (tmp_path / f"{exp_id}__b__sha__v1.json").write_text(json.dumps(real))
    monkeypatch.setattr(step6_report, "GRADE_DIR", tmp_path)

    loaded = step6_report._load_grade_for_experiment(exp_id)
    assert loaded == real


def test_load_grade_returns_none_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(step6_report, "GRADE_DIR", tmp_path)

    assert step6_report._load_grade_for_experiment("exp_missing") is None


def test_load_grade_picks_most_recent(tmp_path, monkeypatch):
    exp_id = "exp_test"
    older = _minimal_grade(model="older-model", avg=50.0)
    newer = _minimal_grade(model="newer-model", avg=80.0)
    older_path = tmp_path / f"{exp_id}__older__sha__v1.json"
    newer_path = tmp_path / f"{exp_id}__newer__sha__v1.json"
    older_path.write_text(json.dumps(older))
    newer_path.write_text(json.dumps(newer))
    os.utime(older_path, (1000, 1000))
    os.utime(newer_path, (2000, 2000))
    monkeypatch.setattr(step6_report, "GRADE_DIR", tmp_path)

    loaded = step6_report._load_grade_for_experiment(exp_id)
    assert loaded == newer
