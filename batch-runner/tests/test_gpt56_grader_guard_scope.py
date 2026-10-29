"""Financial admission is not a rubric verdict; all providers/prices are fake."""
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.usefixtures("native_hosted_runner")

import gpt56_pilot_usd_budget as usd
import step8_grade as step8
from core.cost_metering import CostRecorder
from core.cost_receipts import CostReceiptLedger, STAGE_GRADING
from core.grader import Grader
from core import runner_environment
from core.rubric_loader import RubricItem
from . import test_grader as grading_fixture
from . import test_step8_grade as step8_fixture
from .test_gpt56_pilot_shared_usd import CONFIG, MODEL, PRICE_FIXTURE, TASKS, _kwargs, _ledger
from .test_step8_grade import _typed_azure_ai_route


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def refused(*args, **kwargs):
        raise AssertionError("network forbidden in grader guard tests")
    monkeypatch.setattr(socket.socket, "connect", refused)
    monkeypatch.setattr(socket, "create_connection", refused)
    monkeypatch.setattr(socket, "getaddrinfo", refused)


@pytest.fixture
def admission(tmp_path, monkeypatch):
    monkeypatch.setattr(usd, "price_document", lambda: deepcopy(PRICE_FIXTURE))
    ledger = _ledger(tmp_path, create=True)
    audit = CostReceiptLedger(tmp_path / "audit.sqlite3", run_id="synthetic-scope")
    guard = usd.GradingUsdAdmission(ledger, CONFIG)
    try:
        yield ledger, CostRecorder(audit, usd_admission=guard)
    finally:
        audit.close()
        ledger.close()


class Client:
    max_retries = 0

    def __init__(self, usage=True):
        self.usage = usage
        self.responses = self
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(model=MODEL, status="completed", output=[],
                               output_text='{"verdict":"pass","partial_score":1.0,"evidence":"ok","confidence":0.8,"reasoning":"ok"}',
                               usage=SimpleNamespace(input_tokens=10, output_tokens=5,
                                                     input_tokens_details=SimpleNamespace(cached_tokens=0)) if self.usage else None)


def make_grader(tmp_path, recorder, client):
    fixture = tmp_path / "fixture"
    fixture.mkdir()
    config = grading_fixture._config(fixture)
    config["judge"].update(model=MODEL, deployment=MODEL, reasoning={"effort": "max"})
    grader = Grader(config=config, rubric_loader=grading_fixture._Loader(), client=client, cost_recorder=recorder)
    deliverable = fixture / "d.txt"
    deliverable.write_text("fixed synthetic deliverable", encoding="utf-8")
    item = RubricItem("r1", "evaluate quality", 10, None)
    task = replace(grading_fixture._task(item), task_id=TASKS[0])
    return grader, task, item, deliverable


def test_real_tool_schema_does_not_change_verdict_or_denominator(admission, tmp_path):
    ledger, recorder = admission
    client = Client()
    grader, task, item, deliverable = make_grader(tmp_path, recorder, client)
    try:
        with recorder.attributed(task_id=task.task_id, stage=STAGE_GRADING):
            judged, _, _ = grader._judge(task, item, [deliverable])
        grade = Grader._aggregate([judged], task)
        assert judged.verdict == "pass" and judged.score_excluded is False
        assert (grade.total_awarded, grade.total_max, grade.pct) == (10, 10, 100)
        assert len(client.calls) == 1
        assert client.calls[0]["tools"][0]["parameters"]["properties"]["scope"]["type"] == ["object", "null"]
        assert ledger.snapshot()["pending_requests"] == 0 and ledger.snapshot()["stop_reason"] is None
    finally:
        grader.close()


@pytest.mark.parametrize("stop", ["ceiling", "missing_usage"])
def test_money_stop_cannot_become_a_judge_error_or_excluded_score(admission, tmp_path, stop):
    ledger, recorder = admission
    client = Client(usage=stop != "missing_usage")
    if stop == "ceiling":
        ledger.observe(ledger.begin("inference", TASKS[1]), Decimal(200), Decimal(0))
    grader, task, item, deliverable = make_grader(tmp_path, recorder, client)
    try:
        with recorder.attributed(task_id=task.task_id, stage=STAGE_GRADING):
            with pytest.raises(usd.GradingUsdStopped, match=usd.CEILING if stop == "ceiling" else usd.UNKNOWN) as caught:
                grader._judge(task, item, [deliverable])
        assert not isinstance(caught.value, Exception)
        assert caught.value.source == "grading"
        assert len(client.calls) == int(stop == "missing_usage")
        assert ledger.snapshot()["stop_reason"] == (usd.CEILING if stop == "ceiling" else usd.UNKNOWN)
    finally:
        grader.close()


def schema_request(schema):
    return {**_kwargs(), "tools": [{"type": "function", "name": "fixture", "parameters": schema}]}


def test_schema_metadata_is_counted_but_not_treated_as_runtime_input():
    request = schema_request({"type": "object", "properties": {
        "type": {"type": ["object", "null"]}, "image_url": {"type": "string"}}, "additionalProperties": False})
    inputs, outputs = usd._request_allowance(request)
    assert inputs == len(json.dumps(request, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode())
    assert outputs == request["max_output_tokens"]


@pytest.mark.parametrize("schema", [[], True, {"type": []}, {"type": ["object", "image"]},
                                    {"type": "string", "minLength": -1}, {"$ref": "https://example.invalid/schema"}])
def test_invalid_or_external_tool_schema_remains_fail_closed(schema):
    with pytest.raises(usd.PilotUsdRefused, match=usd.UNKNOWN):
        usd._request_allowance(schema_request(schema))


@pytest.mark.parametrize("field", ["input_image", "file_data", "previous_response_id", "extra_body"])
def test_schema_exception_does_not_allow_opaque_inputs(field):
    request = schema_request({"type": "object", "properties": {"scope": {"type": ["object", "null"]}}})
    request[field] = "unknown"
    with pytest.raises(usd.PilotUsdRefused, match=usd.UNKNOWN):
        usd._request_allowance(request)


def test_schema_exception_is_not_available_in_message_payloads():
    request = {**_kwargs(), "input": [{"type": "function", "parameters": {"type": ["object", "null"]}}]}
    with pytest.raises(usd.PilotUsdRefused, match=usd.UNKNOWN):
        usd._request_allowance(request)


def test_guarded_output_matches_actual_frozen_source(approved_pilot_source, tmp_path):
    helper = Path(__file__).with_name("grader_guard_scope_probe.py")
    candidate = Path(step8.__file__).parent
    shared = tmp_path / "shared"
    env = {"PATH": os.defpath, "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1",
           "HF_HUB_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
           "TMPDIR": str(tmp_path)}
    outputs = []
    for batch, extra in ((approved_pilot_source / "batch-runner", []), (candidate, ["--guarded"])):
        completed = subprocess.run([sys.executable, "-B", str(helper), "--batch", str(batch),
                                    "--fixture", str(shared), *extra], cwd=tmp_path, env=env,
                                   capture_output=True, text=True, timeout=60)
        assert completed.returncode == 0, completed.stderr
        outputs.append(json.loads(completed.stdout))
    assert outputs[0] == outputs[1]
    assert outputs[1]["tasks"][0]["pct"] == 100


@pytest.mark.parametrize("completed_tasks,save_failure", [(0, False), (1, False), (1, True)])
def test_step8_stops_with_receipt_and_without_an_unscored_task(monkeypatch, tmp_path, capsys, completed_tasks, save_failure):
    step8_fixture._setup_workspace(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(step8, "RubricLoader", step8_fixture._FakeLoader)
    closed = []

    class StoppedGrader(step8_fixture._FakeGrader):
        def grade_task(self, task, deliverable_dir, *, resume_from=None):
            if self.calls == completed_tasks:
                raise usd.GradingUsdStopped(usd.CEILING)
            return super().grade_task(task, deliverable_dir, resume_from=resume_from)

        def close(self):
            closed.append(True)

    monkeypatch.setattr(step8, "Grader", StoppedGrader)
    monkeypatch.setattr(sys, "argv", ["step8_grade.py", "exp998_smoke_baseline_sample",
                                     "--config", "grading_configs/default.yaml", "--force"])
    if save_failure:
        def fail_save(*args, **kwargs):
            raise OSError("private-checkpoint-canary")
        monkeypatch.setattr(step8, "_save_json", fail_save)
    assert step8.main() == 4
    assert closed == [True]
    stderr = capsys.readouterr().err
    assert "private-checkpoint-canary" not in stderr
    if save_failure:
        assert "budget-stop checkpoint failed: OSError" in stderr
    report = [json.loads(line) for line in stderr.splitlines() if line.startswith('{"actual_billing_hard_limit_verified"')][-1]
    assert report == {"status": "refused", "source": "grading", "reason": usd.CEILING,
                      "actual_billing_hard_limit_verified": False,
                      "runner_evidence": runner_environment.receipt("grading")}
    grades = list((tmp_path / "data/grades").glob("*.json"))
    if completed_tasks and not save_failure:
        assert len(grades) == 1
        payload = json.loads(grades[0].read_text())
        assert payload["run_status"] == "partial"
        assert [row["task_id"] for row in payload["tasks"]] == ["task-001"]
        assert payload["tasks"][0]["pct"] == 100
    else:
        assert grades == []
