"""Unit tests for `core.grader_batch.BatchJudge`.

All tests use a mocked Azure OpenAI Responses client. No real API calls.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.grader_batch import BatchJudge
from core.rubric_loader import RubricItem, TaskRubric


# ----------------------------------------------------------------------
# Fake Azure OpenAI client
# ----------------------------------------------------------------------


class _Usage:
    def __init__(self, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class _Resp:
    def __init__(self, text: str, input_tokens: int = 100, output_tokens: int = 50) -> None:
        self.output_text = text
        self.usage = _Usage(input_tokens, output_tokens)
        self.incomplete_details = None
        self.status = None


class _FakeResponses:
    def __init__(self):
        self.calls: list[dict] = []
        # `outputs` is a list of either str (raw text) or callable(prompt) -> str
        self.outputs: list = []
        self.latencies: list[float] = []  # injected wall-clock for each call

    def create(self, **kwargs):
        self.calls.append(kwargs)
        idx = len(self.calls) - 1
        out = self.outputs[idx] if idx < len(self.outputs) else self.outputs[-1]
        text = out(kwargs["input"]) if callable(out) else out
        return _Resp(text)


class _FakeClient:
    def __init__(self):
        self.responses = _FakeResponses()


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


_BATCH_PROMPT = """Batch prompt.
sector={{sector}}
occupation={{occupation}}
prompt={{task_prompt_truncated_500}}
batch_size={{batch_size}}
items:
{{rubric_items_block}}
files:
{{#each deliverable_files}}
- {{filename}}: {{extracted_content_or_summary_truncated_4000}}
{{/each}}
<!-- prompt_version: v1-batch -->
"""


def _make_judge(client=None, grader_overrides=None) -> BatchJudge:
    cfg = {
        "model": "gpt-test",
        "deployment": "gpt-test",
        "reasoning_effort": "medium",
        "max_output_tokens": 1024,
    }
    grader_cfg = {
        "evidence_max_chars": 200,
        "deliverable_extract_max_chars": 200,
        "task_prompt_truncate_chars": 200,
        "fail_on_missing_evidence": True,
        "save_raw_responses": False,
    }
    if grader_overrides:
        grader_cfg.update(grader_overrides)
    return BatchJudge(
        client=client or _FakeClient(),
        judge_config=cfg,
        tpm_guard={"min_delay_ms_between_calls": 0, "retry_on_429": {"enabled": False}},
        prompt_template=_BATCH_PROMPT,
        grader_config=grader_cfg,
    )


def _task(items: list[RubricItem]) -> TaskRubric:
    return TaskRubric(
        task_id="t1",
        sector="sec",
        occupation="occ",
        prompt="task prompt body",
        rubric_items=items,
        rubric_pretty="",
        reference_files=[],
        gold_deliverable_files=[],
    )


def _items(n: int) -> list[RubricItem]:
    return [RubricItem(f"r{i + 1}", f"criterion text {i + 1}", 2, None) for i in range(n)]


def _good_array(items: list[RubricItem]) -> str:
    return json.dumps(
        [
            {
                "rubric_item_id": it.rubric_item_id,
                "verdict": "pass",
                "partial_score": 1.0,
                "evidence": f"quote for {it.rubric_item_id}",
                "confidence": 0.9,
                "reasoning": "fine",
            }
            for it in items
        ]
    )


# ----------------------------------------------------------------------
# Tests
# ----------------------------------------------------------------------


def test_batch_of_three_succeeds(tmp_path: Path):
    deliverable = tmp_path / "deliverable.txt"
    deliverable.write_text("the deliverable contents", encoding="utf-8")

    items = _items(3)
    client = _FakeClient()
    client.responses.outputs = [_good_array(items)]

    judge = _make_judge(client=client)
    result = judge.judge_items_batch(_task(items), items, [deliverable])

    assert len(result.items) == 3
    assert result.num_api_calls == 1
    assert all(ig.verdict == "pass" for ig in result.items)
    assert all(ig.decided_by == "judge" for ig in result.items)
    assert all(ig.evidence for ig in result.items)
    # Each item carries shared input/output? No — totals live on BatchResult.
    assert result.input_tokens == 100
    assert result.output_tokens == 50


def test_parse_failure_triggers_chunk_split(tmp_path: Path):
    deliverable = tmp_path / "d.txt"
    deliverable.write_text("content", encoding="utf-8")

    items = _items(4)
    client = _FakeClient()
    # First call: garbage → triggers fallback split into two batches of 2.
    # Subsequent calls: well-formed arrays of length 2 each.
    client.responses.outputs = [
        "not-json-at-all",
        _good_array(items[:2]),
        _good_array(items[2:]),
    ]

    judge = _make_judge(client=client)
    result = judge.judge_items_batch(_task(items), items, [deliverable])

    # 1 failed batch + 2 successful sub-batches = 3 API calls total.
    assert result.num_api_calls == 3
    assert len(result.items) == 4
    # All items recovered to verdict=pass via the sub-batch responses.
    assert all(ig.verdict == "pass" for ig in result.items)


def test_parse_failure_at_chunk_size_one_yields_judge_error(tmp_path: Path):
    deliverable = tmp_path / "d.txt"
    deliverable.write_text("content", encoding="utf-8")

    items = _items(2)
    client = _FakeClient()
    # Always returns garbage → fallback splits to two single-item batches,
    # both still fail parse → judge_error for each.
    client.responses.outputs = ["garbage"] * 10

    judge = _make_judge(client=client)
    result = judge.judge_items_batch(_task(items), items, [deliverable])

    # 1 initial + 2 sub-batches = 3 calls.
    assert result.num_api_calls == 3
    assert len(result.items) == 2
    assert all(ig.verdict == "judge_error" for ig in result.items)


def test_missing_evidence_on_one_item_only_that_item_fails(tmp_path: Path):
    deliverable = tmp_path / "d.txt"
    deliverable.write_text("content", encoding="utf-8")

    items = _items(3)
    client = _FakeClient()
    payload = [
        {"rubric_item_id": "r1", "verdict": "pass", "partial_score": 1.0, "evidence": "quote 1", "confidence": 0.9},
        {"rubric_item_id": "r2", "verdict": "pass", "partial_score": 1.0, "evidence": "", "confidence": 0.9},
        {"rubric_item_id": "r3", "verdict": "pass", "partial_score": 1.0, "evidence": "quote 3", "confidence": 0.9},
    ]
    client.responses.outputs = [json.dumps(payload)]

    judge = _make_judge(client=client)
    result = judge.judge_items_batch(_task(items), items, [deliverable])

    assert result.num_api_calls == 1
    assert [ig.verdict for ig in result.items] == ["pass", "fail", "pass"]
    assert result.items[1].evidence == "missing evidence"
    assert result.items[1].awarded_score == 0.0
    assert result.items[0].awarded_score == 2.0
    assert result.items[2].awarded_score == 2.0


def test_latency_distribution_sums_to_total(tmp_path: Path, monkeypatch):
    deliverable = tmp_path / "d.txt"
    deliverable.write_text("content", encoding="utf-8")

    items = _items(4)
    client = _FakeClient()
    client.responses.outputs = [_good_array(items)]

    # Force a deterministic latency: time.time advances by 0.5s across the call.
    times = iter([1000.0, 1000.5])
    monkeypatch.setattr("core.grader_batch.time.time", lambda: next(times))

    judge = _make_judge(client=client)
    result = judge.judge_items_batch(_task(items), items, [deliverable])

    assert result.total_latency_ms == pytest.approx(500.0)
    per_item = [ig.judge_latency_ms for ig in result.items]
    assert all(v == pytest.approx(125.0) for v in per_item)
    # Per-item latencies sum back to total (within rounding).
    assert sum(per_item) == pytest.approx(result.total_latency_ms)


def test_empty_deliverable_short_circuits_to_fail(tmp_path: Path):
    items = _items(2)
    client = _FakeClient()
    judge = _make_judge(client=client)
    result = judge.judge_items_batch(_task(items), items, [])
    assert result.num_api_calls == 0
    assert len(result.items) == 2
    assert all(ig.verdict == "fail" for ig in result.items)
    assert all(ig.evidence == "deliverable absent" for ig in result.items)


def test_api_kwargs_omit_seed_and_temperature(tmp_path: Path):
    """Regression guard: Responses API rejects seed/temperature for reasoning models."""
    deliverable = tmp_path / "d.txt"
    deliverable.write_text("content", encoding="utf-8")

    items = _items(2)
    client = _FakeClient()
    client.responses.outputs = [_good_array(items)]

    judge = _make_judge(client=client)
    judge.judge_items_batch(_task(items), items, [deliverable])

    kwargs = client.responses.calls[0]
    assert "seed" not in kwargs
    assert "temperature" not in kwargs
    assert kwargs["model"] == "gpt-test"
    assert kwargs["reasoning"] == {"effort": "medium"}
    assert kwargs["max_output_tokens"] == 1024


def test_api_failure_is_class_only_in_log_and_raw_response(
    tmp_path: Path, caplog
):
    sensitive = "https://private.services.ai.azure.com/ deployment=secret"

    class RateLimitError(Exception):
        status_code = 429

    client = _FakeClient()

    def fail(**_kwargs):
        raise RateLimitError(sensitive)

    client.responses.create = fail
    deliverable = tmp_path / "d.txt"
    deliverable.write_text("content", encoding="utf-8")
    items = _items(2)
    judge = _make_judge(
        client=client,
        grader_overrides={"save_raw_responses": True},
    )

    with caplog.at_level("WARNING", logger="core.grader_batch"):
        result = judge.judge_items_batch(
            _task(items), items, [deliverable]
        )

    assert all(item.verdict == "judge_error" for item in result.items)
    assert all(
        item.judge_raw_response == "provider_error:RateLimitError"
        for item in result.items
    )
    assert sensitive not in caplog.text
    assert sensitive not in str(result.items)
