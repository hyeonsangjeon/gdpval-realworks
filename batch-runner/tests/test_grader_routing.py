"""Unit tests for tiered judge routing on `core.grader.Grader`.

Verifies that:
1. `batch_size > 1` alone activates batched dispatch without routing.
2. `judge_routing.tier_pro.route_when.weight_gte` routes correctly.
3. `judge_routing.tier_mini.criterion_pattern_match` routes correctly.
4. Items not matching pro/mini fall through to tier_standard.

Mocks the Azure OpenAI client; no real API calls.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.grader import Grader
from core.rubric_loader import RubricItem, TaskRubric


# ----------------------------------------------------------------------
# Fakes
# ----------------------------------------------------------------------


class _Usage:
    input_tokens = 10
    output_tokens = 5


class _Resp:
    def __init__(self, text: str):
        self.output_text = text
        self.usage = _Usage()
        self.incomplete_details = None
        self.status = None


class _FakeResponses:
    def __init__(self):
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        # Echo a well-formed verdict array for every rubric_item_id listed
        # in the prompt's items block. This makes the fake usable for any
        # batch_size without needing per-test scripting.
        prompt = kwargs["input"]
        ids = _extract_ids(prompt)
        payload = [
            {
                "rubric_item_id": rid,
                "verdict": "pass",
                "partial_score": 1.0,
                "evidence": f"q-{rid}",
                "confidence": 0.9,
                "reasoning": "ok",
            }
            for rid in ids
        ]
        return _Resp(json.dumps(payload))


class _FakeClient:
    def __init__(self):
        self.responses = _FakeResponses()


def _extract_ids(prompt: str) -> list[str]:
    ids: list[str] = []
    for line in prompt.splitlines():
        line = line.strip()
        if line.startswith("- rubric_item_id:"):
            ids.append(line.split(":", 1)[1].strip())
    return ids


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


_SINGLE_TPL = (
    "Single prompt {{sector}} {{occupation}} {{criterion}} {{rubric_item_id}} "
    "{{max_score}} {{required}} {{task_prompt_truncated_500}}\n"
    "{{#each deliverable_files}}{{filename}}{{/each}}\n<!-- prompt_version: v1 -->"
)


def _write_prompts(tmp_path: Path) -> Path:
    single = tmp_path / "grader_judge.md"
    single.write_text(_SINGLE_TPL, encoding="utf-8")
    batch = tmp_path / "grader_judge_batch.md"
    batch.write_text(
        "Batch prompt {{sector}} {{occupation}} {{task_prompt_truncated_500}} "
        "{{batch_size}}\nitems:\n{{rubric_items_block}}\n"
        "{{#each deliverable_files}}{{filename}}{{/each}}\n<!-- prompt_version: v1-batch -->",
        encoding="utf-8",
    )
    return single


def _config(prompt_path: Path, *, batch_size: int = 1, judge_routing: dict | None = None) -> dict:
    cfg = {
        "schema_version": "1.0",
        "config_name": "test",
        "judge": {
            "provider": "azure_openai",
            "api": "responses",
            "model": "gpt-std",
            "deployment": "gpt-std",
            "api_version": "2025-04-01-preview",
            "endpoint_env": "AZURE_OPENAI_ENDPOINT",
            "reasoning": {"effort": "medium"},
            "generation": {"max_output_tokens": 1024},
        },
        "rubric": {"repo_id": "openai/gdpval", "revision": "main", "cache_dir": "data/gdpval-local"},
        "grader": {
            "evidence_max_chars": 200,
            "deliverable_extract_max_chars": 200,
            "task_prompt_truncate_chars": 200,
            "fail_on_missing_evidence": True,
            "save_raw_responses": False,
            "batch_size": batch_size,
            "per_item_max_output_tokens": 800,
        },
        "tpm_guard": {
            "min_delay_ms_between_calls": 0,
            "retry_on_429": {"enabled": False},
        },
        "prompt": {"template": str(prompt_path), "version": "v1"},
        "output": {"directory": "data/grades", "filename_template": "x.json"},
    }
    if judge_routing is not None:
        cfg["judge_routing"] = judge_routing
    return cfg


def _make_grader(monkeypatch, tmp_path: Path, cfg: dict) -> Grader:
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setattr("core.grader.DefaultAzureCredential", lambda: object())
    monkeypatch.setattr("core.grader.get_bearer_token_provider", lambda *a, **k: (lambda: "tok"))
    client = _FakeClient()
    monkeypatch.setattr("core.grader.AzureOpenAI", lambda **kwargs: client)
    g = Grader(config=cfg, rubric_loader=object())
    g._fake_client = client  # type: ignore[attr-defined]
    return g


def _task(items: list[RubricItem]) -> TaskRubric:
    return TaskRubric(
        task_id="t1",
        sector="sec",
        occupation="occ",
        prompt="prompt body",
        rubric_items=items,
        rubric_pretty="",
        reference_files=[],
        gold_deliverable_files=[],
    )


# ----------------------------------------------------------------------
# _route_to_tier unit tests
# ----------------------------------------------------------------------


def test_no_routing_returns_standard(monkeypatch, tmp_path):
    single = _write_prompts(tmp_path)
    g = _make_grader(monkeypatch, tmp_path, _config(single, batch_size=4))
    it = RubricItem("r1", "evaluate overall quality of report", 3, None)
    assert g._route_to_tier(it) == "standard"


def test_weight_gte_routes_to_pro(monkeypatch, tmp_path):
    single = _write_prompts(tmp_path)
    routing = {
        "tier_pro": {
            "model": "gpt-pro",
            "deployment": "gpt-pro",
            "reasoning_effort": "high",
            "route_when": {"weight_gte": 4},
        },
        "tier_standard": {"model": "gpt-std", "deployment": "gpt-std", "reasoning_effort": "medium"},
    }
    g = _make_grader(monkeypatch, tmp_path, _config(single, batch_size=4, judge_routing=routing))

    heavy = RubricItem("r1", "complex reasoning required", 5, True)
    light = RubricItem("r2", "complex reasoning required", 2, None)
    assert g._route_to_tier(heavy) == "pro"
    assert g._route_to_tier(light) == "standard"


def test_criterion_pattern_match_routes_to_mini(monkeypatch, tmp_path):
    single = _write_prompts(tmp_path)
    routing = {
        "tier_standard": {"model": "gpt-std", "deployment": "gpt-std", "reasoning_effort": "medium"},
        "tier_mini": {
            "model": "gpt-mini",
            "deployment": "gpt-mini",
            "reasoning_effort": "minimal",
            "max_output_tokens": 400,
            "criterion_pattern_match": ["executive summary", "section titled"],
        },
    }
    g = _make_grader(monkeypatch, tmp_path, _config(single, batch_size=4, judge_routing=routing))

    mini_item = RubricItem("r1", "Contains an Executive Summary section.", 2, None)
    std_item = RubricItem("r2", "The narrative is coherent and accurate.", 3, None)
    assert g._route_to_tier(mini_item) == "mini"
    assert g._route_to_tier(std_item) == "standard"


def test_pro_takes_precedence_over_mini(monkeypatch, tmp_path):
    single = _write_prompts(tmp_path)
    routing = {
        "tier_pro": {
            "model": "gpt-pro",
            "deployment": "gpt-pro",
            "reasoning_effort": "high",
            "route_when": {"weight_gte": 4},
        },
        "tier_standard": {"model": "gpt-std", "deployment": "gpt-std"},
        "tier_mini": {
            "model": "gpt-mini",
            "deployment": "gpt-mini",
            "reasoning_effort": "minimal",
            "criterion_pattern_match": ["executive summary"],
        },
    }
    g = _make_grader(monkeypatch, tmp_path, _config(single, batch_size=4, judge_routing=routing))

    # Matches mini pattern AND weight>=4 → must route to pro.
    item = RubricItem("r1", "Contains an Executive Summary section.", 5, True)
    assert g._route_to_tier(item) == "pro"


# ----------------------------------------------------------------------
# End-to-end batched dispatch via grade_task
# ----------------------------------------------------------------------


def test_batched_grade_task_uses_correct_tier_models(monkeypatch, tmp_path):
    """Pro items and standard items should hit DIFFERENT models in API calls."""
    single = _write_prompts(tmp_path)
    routing = {
        "tier_pro": {
            "model": "gpt-pro",
            "deployment": "gpt-pro",
            "reasoning_effort": "high",
            "route_when": {"weight_gte": 4},
        },
        "tier_standard": {"model": "gpt-std", "deployment": "gpt-std", "reasoning_effort": "medium"},
    }
    g = _make_grader(monkeypatch, tmp_path, _config(single, batch_size=8, judge_routing=routing))

    deliverable_dir = tmp_path / "deliverable"
    deliverable_dir.mkdir()
    (deliverable_dir / "out.txt").write_text("deliverable content", encoding="utf-8")

    items = [
        RubricItem("r1", "free text quality", 5, True),   # → pro
        RubricItem("r2", "free text quality", 2, None),   # → standard
        RubricItem("r3", "free text quality", 5, None),   # → pro
        RubricItem("r4", "free text quality", 1, None),   # → standard
    ]
    task = _task(items)

    grade = g.grade_task(task, str(deliverable_dir))

    # Two API calls expected: one batch per tier.
    fake = g._fake_client  # type: ignore[attr-defined]
    assert grade.judge_call_count == 2
    models = sorted([c["model"] for c in fake.responses.calls])
    assert models == ["gpt-pro", "gpt-std"]
    # All items graded, order preserved.
    assert [it.rubric_item_id for it in grade.items] == ["r1", "r2", "r3", "r4"]
    assert all(it.verdict == "pass" for it in grade.items)


def test_batched_grade_task_chunks_within_tier(monkeypatch, tmp_path):
    """5 items at batch_size=2 → ceil(5/2) = 3 API calls."""
    single = _write_prompts(tmp_path)
    g = _make_grader(monkeypatch, tmp_path, _config(single, batch_size=2))

    deliverable_dir = tmp_path / "deliverable"
    deliverable_dir.mkdir()
    (deliverable_dir / "out.txt").write_text("hello", encoding="utf-8")

    items = [RubricItem(f"r{i+1}", "free text quality", 2, None) for i in range(5)]
    grade = g.grade_task(_task(items), str(deliverable_dir))
    assert grade.judge_call_count == 3
    assert len(grade.items) == 5


def test_legacy_single_item_path_unaffected(monkeypatch, tmp_path):
    """batch_size=1 and no routing → legacy per-item path, counter = N."""
    single = _write_prompts(tmp_path)
    g = _make_grader(monkeypatch, tmp_path, _config(single, batch_size=1))

    deliverable_dir = tmp_path / "deliverable"
    deliverable_dir.mkdir()
    (deliverable_dir / "out.txt").write_text("hello", encoding="utf-8")

    # Use a single-item JSON object response from the fake client. We
    # need to override the fake to emit a single-object schema for the
    # legacy path which expects `{"verdict":...}`.
    g._fake_client.responses.create = lambda **kw: _Resp(  # type: ignore[attr-defined]
        '{"verdict":"pass","partial_score":1.0,"evidence":"q","confidence":0.9,"reasoning":"ok"}'
    )

    items = [RubricItem(f"r{i+1}", "free text quality", 2, None) for i in range(3)]
    grade = g.grade_task(_task(items), str(deliverable_dir))
    # Legacy semantic: one call per item.
    assert grade.judge_call_count == 3
    assert all(it.verdict == "pass" for it in grade.items)
