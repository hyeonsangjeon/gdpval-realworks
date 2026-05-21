from pathlib import Path

import openpyxl
import pytest

from core.grader import Grader
from core.rubric_loader import RubricItem, TaskRubric


class _FakeTokenProvider:
    def __call__(self):
        return "token"


class _FakeClient:
    def __init__(self, error=None):
        self.responses = self
        self.calls = 0
        self.last_kwargs = None
        self.error = error
        self._next_text = '{"verdict":"pass","partial_score":1.0,"evidence":"ok","confidence":0.8,"reasoning":"ok"}'

    def create(self, **kwargs):
        self.calls += 1
        self.last_kwargs = kwargs
        if self.error:
            raise self.error

        class _Usage:
            input_tokens = 10
            output_tokens = 5

        class _Resp:
            usage = _Usage()
            output_text = ""

        resp = _Resp()
        resp.output_text = self._next_text
        return resp


class _Loader:
    pass


def _config(tmp_path: Path) -> dict:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("""Evidence quote is mandatory\n{{#each deliverable_files}}{{/each}}\n<!-- prompt_version: v1 -->""", encoding="utf-8")
    return {
        "judge": {
            "provider": "azure_openai",
            "api": "responses",
            "model": "gpt-5.4-pro",
            "deployment": "gpt-5.4-pro",
            "api_version": "2025-04-01-preview",
            "endpoint_env": "AZURE_OPENAI_ENDPOINT",
            "generation": {"temperature": 0, "seed": 42, "max_output_tokens": 1024},
            "reasoning": {"effort": "high"},
        },
        "grader": {
            "judge_max_retries": 1,
            "evidence_max_chars": 200,
            "deliverable_extract_max_chars": 200,
            "task_prompt_truncate_chars": 200,
            "fail_on_missing_evidence": True,
            "save_raw_responses": False,
            "per_item_max_output_tokens": 200,
        },
        "prompt": {"template": str(prompt), "version": "v1"},
        "tpm_guard": {
            "min_delay_ms_between_calls": 0,
            "retry_on_429": {"enabled": True, "max_retries": 1, "initial_backoff_sec": 0.01, "exponential_factor": 2.0},
        },
    }


def _task(item: RubricItem) -> TaskRubric:
    return TaskRubric(
        task_id="t1",
        sector="s",
        occupation="o",
        prompt="prompt",
        rubric_items=[item],
        rubric_pretty="",
        reference_files=[],
        gold_deliverable_files=[],
    )


def _make_grader(monkeypatch, tmp_path: Path, fake_client: _FakeClient | None = None) -> Grader:
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setattr("core.grader.DefaultAzureCredential", lambda: object())
    monkeypatch.setattr("core.grader.get_bearer_token_provider", lambda *args, **kwargs: _FakeTokenProvider())
    fake = fake_client or _FakeClient()
    monkeypatch.setattr("core.grader.AzureOpenAI", lambda **kwargs: fake)
    g = Grader(config=_config(tmp_path), rubric_loader=_Loader())
    g._fake_client = fake
    return g


def test_classify_file_exists_pattern():
    item = RubricItem("r1", "The submitted file basename is 'Sample'", 2, None)
    mode, pid = Grader._classify(item)
    assert mode == "precheck"
    assert pid == "file_exists_or_name"


def test_classify_falls_back_to_judge():
    item = RubricItem("r1", "audit conclusion correctly identifies issue", 3, None)
    mode, pid = Grader._classify(item)
    assert mode == "judge"
    assert pid is None


def test_precheck_file_extension_pass(monkeypatch, tmp_path):
    grader = _make_grader(monkeypatch, tmp_path)
    f = tmp_path / "sample.xlsx"
    f.write_bytes(b"x")
    item = RubricItem("r1", "Deliverable must be .xlsx", 2, None)
    verdict = grader._precheck_file_extension(item, [f])
    assert verdict[0] == "pass"


def test_precheck_file_extension_fail(monkeypatch, tmp_path):
    grader = _make_grader(monkeypatch, tmp_path)
    f = tmp_path / "sample.pdf"
    f.write_bytes(b"x")
    item = RubricItem("r1", "Deliverable must be .xlsx", 2, None)
    verdict = grader._precheck_file_extension(item, [f])
    assert verdict[0] == "fail"


def test_precheck_worksheet_name_pass(monkeypatch, tmp_path):
    grader = _make_grader(monkeypatch, tmp_path)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Summary"
    xlsx = tmp_path / "book.xlsx"
    wb.save(xlsx)

    item = RubricItem("r1", "worksheet named 'Summary' must be present", 2, None)
    verdict = grader._precheck_worksheet_name(item, [xlsx])
    assert verdict[0] == "pass"


def test_judge_missing_evidence_marks_fail(monkeypatch, tmp_path):
    grader = _make_grader(monkeypatch, tmp_path)
    grader._fake_client._next_text = '{"verdict":"pass","partial_score":1.0,"evidence":"","confidence":0.9,"reasoning":"ok"}'

    deliverable = tmp_path / "d.txt"
    deliverable.write_text("content", encoding="utf-8")

    item = RubricItem("r1", "evaluate quality", 3, None)
    ig, _, _ = grader._judge(_task(item), item, [deliverable])
    assert ig.verdict == "fail"


def test_judge_parse_retry_then_judge_error(monkeypatch, tmp_path):
    grader = _make_grader(monkeypatch, tmp_path)
    grader._fake_client._next_text = "not-json"

    deliverable = tmp_path / "d.txt"
    deliverable.write_text("content", encoding="utf-8")

    item = RubricItem("r1", "evaluate quality", 3, None)
    ig, _, _ = grader._judge(_task(item), item, [deliverable])
    assert ig.verdict == "judge_error"


def test_judge_api_failure_becomes_judge_error(monkeypatch, tmp_path):
    class _RateLimit(Exception):
        status_code = 429

    grader = _make_grader(monkeypatch, tmp_path, _FakeClient(error=_RateLimit("rate limited")))
    deliverable = tmp_path / "d.txt"
    deliverable.write_text("content", encoding="utf-8")

    item = RubricItem("r1", "evaluate quality", 3, None)
    ig, input_tokens, output_tokens = grader._judge(_task(item), item, [deliverable])
    assert ig.verdict == "judge_error"
    assert ig.evidence == "judge_api_call_failed"
    assert input_tokens == 0
    assert output_tokens == 0


def test_tpm_delay_between_judge_calls(monkeypatch, tmp_path):
    sleeps = []
    now = [100.0]

    monkeypatch.setattr("core.grader.time.time", lambda: now[0])
    monkeypatch.setattr("core.grader.time.sleep", lambda seconds: sleeps.append(seconds))
    grader = _make_grader(monkeypatch, tmp_path)
    grader._min_delay_seconds = 0.5

    grader._apply_tpm_delay()
    now[0] = 100.1
    grader._apply_tpm_delay()

    assert sleeps == [pytest.approx(0.4)]


def test_call_judge_does_not_pass_seed_or_temperature(monkeypatch, tmp_path):
    """Azure Responses API for reasoning models rejects seed/temperature.

    Regression guard for run #26210354117 where every judge call failed with
    'Responses.create() got an unexpected keyword argument seed'.
    """
    grader = _make_grader(monkeypatch, tmp_path)
    deliverable = tmp_path / "d.txt"
    deliverable.write_text("content", encoding="utf-8")
    item = RubricItem("r1", "evaluate quality", 3, None)

    grader._judge(_task(item), item, [deliverable])

    kwargs = grader._fake_client.last_kwargs
    assert kwargs is not None
    assert "seed" not in kwargs
    assert "temperature" not in kwargs
    assert kwargs["model"] == "gpt-5.4-pro"
    assert kwargs["reasoning"] == {"effort": "high"}
    assert "max_output_tokens" in kwargs


def test_aggregate_pct_calculation(monkeypatch, tmp_path):
    grader = _make_grader(monkeypatch, tmp_path)
    item = RubricItem("r1", "x", 63, None)
    t = _task(item)

    from core.grader import ItemGrade

    tg = grader._aggregate(
        [
            ItemGrade(
                rubric_item_id="r1",
                criterion="x",
                max_score=63,
                awarded_score=42,
                verdict="partial",
                decided_by="judge",
                required=None,
                evidence="e",
            )
        ],
        t,
    )
    assert round(tg.pct, 2) == 66.67


def test_critical_fail_flag(monkeypatch, tmp_path):
    grader = _make_grader(monkeypatch, tmp_path)
    item = RubricItem("r1", "x", 10, True)
    t = _task(item)

    from core.grader import ItemGrade

    tg = grader._aggregate(
        [
            ItemGrade(
                rubric_item_id="r1",
                criterion="x",
                max_score=10,
                awarded_score=0,
                verdict="fail",
                decided_by="judge",
                required=True,
                evidence="e",
            )
        ],
        t,
    )
    assert tg.critical_fail is True


def test_grade_task_no_deliverables_graceful(monkeypatch, tmp_path):
    grader = _make_grader(monkeypatch, tmp_path)
    item = RubricItem("r1", "file basename is 'Sample'", 2, None)
    task = _task(item)
    tg = grader.grade_task(task, str(tmp_path / "not_found"))
    assert tg.error == "no_deliverables"
