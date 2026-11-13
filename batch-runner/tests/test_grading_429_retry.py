"""Offline provider scripts and real local ledgers; no credential or paid call."""

import copy
from decimal import Decimal
from http import HTTPStatus
import json
from pathlib import Path
import socket
from types import SimpleNamespace

import pytest
import yaml

import core.grading_retry as retry
from core.cost_receipts import STAGE_GRADING
from core.grader import Grader
from core.perception import AudioPerception, VisionPerception
from core.tool_calling_judge import ToolCallingJudge
import gpt56_pilot_usd_budget as usd
import sol_batch_grading as batch
import sol_batch_controls as controls
import step8_grade
from .test_grader import _config, _Loader
from .test_perception_audio import wav_file
from .test_perception_vision import _png_b64
from .test_sol_batch_grading import admitted, _seed, _records, _reserve_for
from .test_tool_calling_judge import PROMPT_TEMPLATE, _final, _response, task_and_item

pytestmark = pytest.mark.usefixtures("native_hosted_runner")


class RateLimitError(RuntimeError):
    def __init__(self, status=429, headers=None):
        super().__init__("synthetic provider refusal")
        self.status_code = status
        self.response = SimpleNamespace(headers=headers or {})


class ScriptedClient:
    def __init__(self, script):
        self.script = list(script)
        self.calls = []
        self.responses = self
        self.chat = SimpleNamespace(completions=self)
        self.max_retries = 0

    def create(self, **kwargs):
        self.calls.append(copy.deepcopy(kwargs))
        assert self.script, "unexpected extra provider attempt"
        item = self.script.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("retry unit test attempted an external connection")
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    waits = []
    monkeypatch.setattr(retry.time, "sleep", waits.append)
    return waits


def policy(**changes):
    return retry.Retry429Policy.from_config({
        "enabled": True, "max_retries": 3,
        "initial_backoff_sec": 2, "exponential_factor": 2, **changes,
    })


def final_response():
    return _response(output=[_final(json.dumps({
        "verdict": "pass", "partial_score": 1.0, "evidence": "alpha is present",
        "confidence": 0.9, "reasoning": "synthetic observation",
    }))])


@pytest.mark.parametrize("enabled,retries,attempts,waits", [
    (True, 0, 1, []), (True, 1, 2, [2]), (True, 3, 4, [2, 4, 8]),
    (False, 3, 1, []),
])
def test_enabled_and_retry_limit_are_exact(offline, enabled, retries, attempts, waits):
    error = RateLimitError()
    client = ScriptedClient([error] * 5)
    stats = retry.RetryCallStats()
    guards = []
    with pytest.raises(RateLimitError) as refused:
        retry.call_with_429_retry(client.create, policy=policy(enabled=enabled, max_retries=retries),
                                  stats=stats, before_attempt=lambda: guards.append("guard"))
    assert refused.value is error
    assert len(client.calls) == stats.attempts == stats.failed_attempts == len(guards) == attempts
    assert offline == waits


@pytest.mark.parametrize("status", [400, 401, 403, 404, 500, 503, None, "429", True])
def test_only_typed_429_is_retried(offline, status):
    client = ScriptedClient([RateLimitError(status), final_response()])
    with pytest.raises(RateLimitError):
        retry.call_with_429_retry(client.create, policy=policy(), stats=retry.RetryCallStats())
    assert len(client.calls) == 1 and offline == []


@pytest.mark.parametrize("raw,expected", [
    ("7", 7), ("0.5", 2), ("-8", 2), ("invalid", 2), ("nan", 2), ("inf", 2),
    ("Tue, 14 Nov 2023 22:13:27 GMT", 7), ("Tue, 14 Nov 2023 22:13:19 GMT", 2),
])
def test_retry_after_seconds_and_http_date_are_minimum_delays(offline, monkeypatch, raw, expected):
    monkeypatch.setattr(retry.time, "time", lambda: 1700000000)
    client = ScriptedClient([RateLimitError(headers={"rEtRy-AfTeR": raw}), "ok"])
    assert retry.call_with_429_retry(client.create, policy=policy(), stats=retry.RetryCallStats()) == "ok"
    assert len(client.calls) == 2 and offline == [expected]


@pytest.mark.parametrize("headers,expected", [
    ({"Retry-After-Ms": "2500"}, 2.5),
    ({"Retry-After": "3", "x-ms-retry-after-ms": "7000"}, 7),
    ({"x-ms-retry-after-ms": "1000"}, 2),
])
def test_azure_millisecond_hints_are_respected_without_sdk_hidden_retries(offline, headers, expected):
    client = ScriptedClient([RateLimitError(headers=headers), "ok"])
    assert retry.call_with_429_retry(client.create, policy=policy(), stats=retry.RetryCallStats()) == "ok"
    assert len(client.calls) == 2 and offline == [expected]


def test_typed_status_on_the_http_response_is_also_supported(offline):
    error = RateLimitError(status=None, headers={"Retry-After": "3"})
    error.response.status_code = HTTPStatus.TOO_MANY_REQUESTS
    client = ScriptedClient([error, "ok"])
    assert retry.call_with_429_retry(client.create, policy=policy(), stats=retry.RetryCallStats()) == "ok"
    assert len(client.calls) == 2 and offline == [3]


def test_exception_headers_are_used_without_parsing_error_text(offline):
    error = RateLimitError()
    error.response = None
    error.headers = {"Retry-After": "11"}
    client = ScriptedClient([error, "ok"])
    assert retry.call_with_429_retry(client.create, policy=policy(), stats=retry.RetryCallStats()) == "ok"
    assert offline == [11]
    client = ScriptedClient([RuntimeError("429 Retry-After: 999"), "not sent"])
    with pytest.raises(RuntimeError):
        retry.call_with_429_retry(client.create, policy=policy(), stats=retry.RetryCallStats())
    assert len(client.calls) == 1 and offline == [11]


@pytest.mark.parametrize("delay", ["601", "9" * 400, "Fri, 01 Jan 9999 00:00:00 GMT"])
def test_excessive_server_delay_is_refused_not_shortened_or_waited_forever(offline, delay):
    client = ScriptedClient([RateLimitError(headers={"Retry-After": delay}), "must not send"])
    with pytest.raises(RateLimitError):
        retry.call_with_429_retry(client.create, policy=policy(), stats=retry.RetryCallStats())
    assert len(client.calls) == 1 and offline == []


@pytest.mark.parametrize("invalid", [
    [], False, {"enabled": "true"}, {"max_retries": True}, {"max_retries": -1},
    {"max_retries": 1.5}, {"initial_backoff_sec": -1}, {"initial_backoff_sec": float("nan")},
    {"initial_backoff_sec": float("inf")}, {"exponential_factor": 0.5}, {"exponential_factor": True},
])
def test_bad_policy_is_rejected_before_provider_work(invalid):
    with pytest.raises(ValueError, match="retry_on_429"):
        retry.Retry429Policy.from_config(invalid)


def test_missing_policy_is_no_retry_and_step8_validates_the_real_config():
    assert retry.Retry429Policy.from_config(None).max_retries == 0
    root = Path(__file__).resolve().parents[1]
    config = yaml.safe_load((root / "grading_configs/exp037_v2_sol_max.yaml").read_text())
    step8_grade.validate_grading_config(config)
    assert retry.Retry429Policy.from_config(config["tpm_guard"]["retry_on_429"]).max_retries == 3
    config["tpm_guard"]["retry_on_429"]["max_retries"] = -1
    with pytest.raises(ValueError, match="retry_on_429"):
        step8_grade.validate_grading_config(config)


def test_main_retry_counts_attempts_without_consuming_tool_iterations(task_and_item, tmp_path, offline):
    task, item = task_and_item
    client = ScriptedClient([RateLimitError(), RateLimitError(), final_response()])
    guarded = []
    judge = ToolCallingJudge(client=client, model="gpt-5.6-sol", prompt_template=PROMPT_TEMPLATE,
                             max_iterations=1, retry_on_429=policy(),
                             before_upstream_call=lambda: guarded.append("call"))
    result = judge.judge_item(task=task, item=item, deliverable_dir=str(tmp_path), file_names=["report.txt"])
    assert result.verdict == "pass" and result.score_excluded is False
    assert result.main_api_call_count == len(client.calls) == len(guarded) == 3
    assert result.iterations == 1 and result.usage_complete is False
    assert client.calls[0] == client.calls[1] == client.calls[2]
    assert offline == [2, 4]


def test_legacy_sdk_shape_fallback_also_obeys_the_same_retry_policy(task_and_item, tmp_path, offline):
    task, item = task_and_item
    client = ScriptedClient([TypeError("synthetic old SDK"), RateLimitError(), final_response()])
    judge = ToolCallingJudge(client=client, model="gpt-5.6-sol", prompt_template=PROMPT_TEMPLATE,
                             retry_on_429=policy(max_retries=1))
    result = judge.judge_item(task=task, item=item, deliverable_dir=str(tmp_path), file_names=["report.txt"])
    assert result.verdict == "pass" and result.main_api_call_count == 3
    assert "instructions" in client.calls[0] and "instructions" not in client.calls[1]
    assert client.calls[1] == client.calls[2] and offline == [2]


def test_config_reaches_all_three_judges_and_exhaustion_remains_an_excluded_row(task_and_item, tmp_path, offline):
    task, item = task_and_item
    config = _config(tmp_path)
    config["tpm_guard"]["retry_on_429"] = {"enabled": True, "max_retries": 2,
        "initial_backoff_sec": 2, "exponential_factor": 2}
    config["judge"]["perception"] = {
        "visual": {"model": "gpt-5.6-sol", "deployment": "gpt-5.6-sol"},
        "audio": {"model": "gpt-audio-1.5", "deployment": "gpt-audio-1.5"},
    }
    client = ScriptedClient([RateLimitError()] * 3)
    grader = Grader(config=config, rubric_loader=_Loader(), client=client)
    report = tmp_path / "report.txt"
    report.write_text("alpha")
    try:
        judge = grader._tool_judge
        assert judge.retry_on_429 == judge.vision_perception.retry_on_429 == judge.audio_perception.retry_on_429 == policy(max_retries=2)
        row, _, _ = grader._judge(task, item, [report])
    finally:
        grader.close()
    assert row.verdict == "judge_error" and row.score_excluded is True
    assert row.evidence == "provider_error:RateLimitError"
    assert row.judge_call_count == len(client.calls) == 3 and row.usage_complete is False
    assert offline == [2, 4]


@pytest.mark.parametrize("cap,success,calls", [(1, False, 1), (2, True, 2)])
def test_vision_retries_do_not_bypass_the_perception_cap(offline, cap, success, calls):
    reply = SimpleNamespace(output_text=json.dumps({"verdict": "pass", "partial_score": 1.0,
        "evidence": "visible", "confidence": 0.9, "reasoning": "fixture"}),
        usage=SimpleNamespace(input_tokens=10, output_tokens=2))
    client = ScriptedClient([RateLimitError(), reply])
    perception = VisionPerception(client=client, call_cap=cap, retry_on_429=policy())
    result = perception.judge(criterion="chart", image_b64=_png_b64())
    assert (result.verdict == "pass") is success
    assert result.api_call_count == len(client.calls) == perception.calls_used == calls
    assert result.usage_complete is False
    assert offline == ([2] if success else [])


@pytest.mark.parametrize("budget,success,calls", [(1, False, 1), (3, True, 3)])
def test_audio_retries_retain_the_failure_budget_and_refund_rules(wav_file, offline, budget, success, calls):
    reply = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({
        "verdict": "pass", "partial_score": 1.0, "evidence": "heard",
        "confidence": 0.9, "reasoning": "fixture"})))],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=2))
    client = ScriptedClient([RateLimitError(), RateLimitError(), reply])
    perception = AudioPerception(client=client, failure_budget=budget, retry_on_429=policy())
    result = perception.judge(criterion="audio", audio_path=str(wav_file))
    assert (result.verdict == "pass") is success
    assert result.api_call_count == len(client.calls) == calls
    assert perception.calls_used == int(success) and perception.failures_used == (2 if success else 1)
    assert result.usage_complete is False and offline == ([2, 4] if success else [])


KWARGS = {"model": "gpt-5.6-sol", "input": "synthetic request", "max_output_tokens": 10}


def exp037_seed(*, floor):
    approval = next(row for row in batch.APPROVALS if row.experiment_id == "exp037_sol_first25")
    assert approval.ceiling_usd == Decimal("700")
    allowance = controls.RUNS[approval.experiment_id].narrative_allowance_usd
    return _seed(experiment_id=approval.experiment_id, config_name=approval.config_name,
                 ceiling_usd=approval.ceiling_usd,
                 narrative_allowance_usd=allowance,
                 solve_usd=floor - allowance)


def test_retries_each_reserve_and_settle_through_the_real_combined_usd_and_receipt_ledgers(admitted, offline):
    admission, recorder = admitted(exp037_seed(floor=Decimal("424.55")))
    reply = SimpleNamespace(model=KWARGS["model"], status="completed",
                            usage=SimpleNamespace(input_tokens=10, output_tokens=2))
    client = ScriptedClient([RateLimitError(), reply])
    metered = recorder.meter(client, provider="azure", model=KWARGS["model"])
    with recorder.attributed(task_id="fixture-task", stage=STAGE_GRADING):
        result = retry.call_with_429_retry(lambda: metered.responses.create(**KWARGS),
                                          policy=policy(), stats=retry.RetryCallStats())
    assert result is reply and len(client.calls) == 2
    records = _records(admission.journal_path)
    assert [row["event"] for row in records] == ["open", "reserve", "abandon", "reserve", "settle"]
    assert records[1]["ticket"] != records[3]["ticket"]
    reserve = _reserve_for(KWARGS)
    assert Decimal(records[1]["reserve_usd"]) == Decimal(records[3]["reserve_usd"]) == reserve
    assert Decimal(records[2]["spent_usd"]) == reserve  # Unknown failed usage is never booked as zero.
    assert admission.committed() == Decimal("424.55") + reserve + Decimal(records[4]["spent_usd"])
    rows = recorder.ledger.calls_for("fixture-task")
    assert len(rows) == 2 and rows[0]["call_id"] != rows[1]["call_id"]
    by_state = {row["state"]: row for row in rows}
    assert set(by_state) == {"refused", "settled"}
    assert by_state["settled"]["call_id"] == metered.last_call_id
    assert rows[0]["request_sha256"] == rows[1]["request_sha256"]
    assert offline == [2]


def test_the_actual_main_judge_reenters_both_ledgers_for_its_retry(admitted, task_and_item, tmp_path, offline):
    admission, recorder = admitted(exp037_seed(floor=Decimal("424.55")))
    task, item = task_and_item
    reply = final_response()
    reply.model, reply.status = "gpt-5.6-sol", "completed"
    client = ScriptedClient([RateLimitError(), reply])
    judge = ToolCallingJudge(
        client=recorder.meter(client, provider="azure", model=reply.model), model=reply.model,
        prompt_template=PROMPT_TEMPLATE, retry_on_429=policy(), max_iterations=1,
    )
    with recorder.attributed(task_id=task.task_id, stage=STAGE_GRADING):
        result = judge.judge_item(task=task, item=item, deliverable_dir=str(tmp_path), file_names=["report.txt"])
    assert result.verdict == "pass" and result.main_api_call_count == len(client.calls) == 2
    assert len(recorder.ledger.calls_for(task.task_id)) == 2
    assert [row["event"] for row in _records(admission.journal_path)] == [
        "open", "reserve", "abandon", "reserve", "settle"]
    assert admission.spent > 0 and admission.pending == {} and offline == [2]


@pytest.mark.parametrize("first_allowed", [False, True])
def test_the_700_usd_ceiling_stops_before_the_retry_is_sent(admitted, offline, first_allowed):
    reserve = _reserve_for(KWARGS)
    admission, recorder = admitted(exp037_seed(floor=Decimal("700") - (reserve if first_allowed else 0)))
    client = ScriptedClient([RateLimitError(), "must never be sent"])
    metered = recorder.meter(client, provider="azure", model=KWARGS["model"])
    with recorder.attributed(task_id="fixture-task", stage=STAGE_GRADING):
        with pytest.raises(usd.GradingUsdStopped, match=usd.CEILING):
            retry.call_with_429_retry(lambda: metered.responses.create(**KWARGS),
                                      policy=policy(), stats=retry.RetryCallStats())
    assert len(client.calls) == int(first_allowed)
    records = _records(admission.journal_path)
    assert [row["event"] for row in records] == (
        ["open", "reserve", "abandon", "stop"] if first_allowed else ["open", "stop"])
    assert admission.committed() == Decimal("700") and admission.pending == {}
    assert offline == ([2] if first_allowed else [])
