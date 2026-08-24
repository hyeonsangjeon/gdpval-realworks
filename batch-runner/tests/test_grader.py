from pathlib import Path
from unittest.mock import MagicMock

import pytest

from core.azure_ai_clients import AzureAIWorkload
from core.grader import Grader, grader_transport_options
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


# Task 207 — the v2 tool judge resolves `grader_judge_v2.md` as a sibling of
# the configured prompt template, so the fixture stages BOTH templates into
# tmp_path. Copying rather than pointing at prompts/ keeps the fixture
# self-contained and keeps a test from ever writing to a tracked file.
_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _config(tmp_path: Path) -> dict:
    prompt = tmp_path / "grader_judge.md"
    prompt.write_text(
        (_PROMPTS_DIR / "grader_judge.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (tmp_path / "grader_judge_v2.md").write_text(
        (_PROMPTS_DIR / "grader_judge_v2.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return {
        "judge": {
            "provider": "azure_openai",
            "api": "responses",
            "model": "gpt-5.4-pro",
            "deployment": "gpt-5.4-pro",
            "api_version": "2025-04-01-preview",
            "generation": {"temperature": 0, "seed": 42, "max_output_tokens": 1024},
            "reasoning": {"effort": "high"},
            # Task 207 — the tool-calling judge is the only grading path,
            # so every Grader config must opt in.
            "tools": {
                "read_deliverable": {
                    "ops": ["inspect_structure", "read_content",
                            "inspect_formatting"],
                    "per_item_call_cap": 8,
                    "max_iterations": 6,
                },
            },
        },
        "grader": {
            "judge_max_retries": 1,
            "evidence_max_chars": 200,
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
    fake = fake_client or _FakeClient()
    g = Grader(config=_config(tmp_path), rubric_loader=_Loader(), client=fake)
    g._fake_client = fake
    return g


def test_grader_transport_options_match_factory_defaults(tmp_path):
    config = _config(tmp_path)
    assert grader_transport_options(config) == {
        "timeout": 600,
        "legacy_api_version": "2025-04-01-preview",
    }

    config["judge"]["timeout_sec"] = 321
    config["judge"]["api_version"] = "custom-version"
    assert grader_transport_options(config) == {
        "timeout": 321,
        "legacy_api_version": "custom-version",
    }


def test_grader_routes_typed_workload_and_closes_lease(tmp_path):
    client = _FakeClient()
    lease = MagicMock(client=client, runtime_fingerprint="fingerprint")
    factory = MagicMock()
    factory.create.return_value = lease

    grader = Grader(
        config=_config(tmp_path),
        rubric_loader=_Loader(),
        client_factory=factory,
    )

    assert grader.client is client
    assert grader.runtime_fingerprint == "fingerprint"
    factory.create.assert_called_once_with(
        AzureAIWorkload.GRADER,
        deployment="gpt-5.4-pro",
        timeout=600,
        max_retries=None,
        legacy_api_version="2025-04-01-preview",
    )
    grader.close()
    lease.close.assert_called_once_with()


def test_grader_close_failure_clears_owned_client_references(tmp_path):
    sensitive = "https://private.services.ai.azure.com/"
    client = _FakeClient()
    lease = MagicMock(client=client, runtime_fingerprint="fingerprint")
    lease.close.side_effect = OSError(sensitive)
    factory = MagicMock()
    factory.create.return_value = lease
    grader = Grader(
        config=_config(tmp_path),
        rubric_loader=_Loader(),
        client_factory=factory,
    )

    with pytest.raises(OSError, match="private.services"):
        grader.close()

    assert grader._managed_client is None
    assert grader.client is None
    grader.close()
    lease.close.assert_called_once_with()


def test_owned_grader_factory_closes_after_managed_client(
    tmp_path, monkeypatch
):
    events = []
    lease = MagicMock(
        client=_FakeClient(),
        runtime_fingerprint="fingerprint",
    )
    lease.close.side_effect = lambda: events.append("lease")
    factory = MagicMock()
    factory.create.return_value = lease
    factory.close.side_effect = lambda: events.append("factory")
    monkeypatch.setattr(
        "core.llm_client.AzureAIClientFactory",
        MagicMock(return_value=factory),
    )

    grader = Grader(config=_config(tmp_path), rubric_loader=_Loader())
    grader.close()

    assert events == ["lease", "factory"]


def test_grader_constructor_failure_closes_acquired_lease(tmp_path):
    config = _config(tmp_path)
    Path(config["prompt"]["template"]).unlink()
    lease = MagicMock(client=_FakeClient(), runtime_fingerprint="fingerprint")
    factory = MagicMock()
    factory.create.return_value = lease

    with pytest.raises(FileNotFoundError):
        Grader(
            config=config,
            rubric_loader=_Loader(),
            client_factory=factory,
        )

    lease.close.assert_called_once_with()


def test_grader_rejects_deprecated_endpoint_env(tmp_path):
    config = _config(tmp_path)
    config["judge"]["endpoint_env"] = "AZURE_OPENAI_ENDPOINT"

    with pytest.raises(ValueError, match="judge.endpoint_env is deprecated"):
        Grader(config=config, rubric_loader=_Loader(), client=_FakeClient())


def test_grader_rejects_model_deployment_drift(tmp_path):
    config = _config(tmp_path)
    config["judge"]["deployment"] = "different-deployment"

    with pytest.raises(ValueError, match="judge.model and judge.deployment must match"):
        Grader(config=config, rubric_loader=_Loader(), client=_FakeClient())


def test_injected_grader_client_is_not_closed(tmp_path):
    client = MagicMock()
    grader = Grader(config=_config(tmp_path), rubric_loader=_Loader(), client=client)

    grader.close()

    client.close.assert_not_called()


@pytest.mark.parametrize(
    "criterion",
    [
        "Amounts match the source invoice in Reference.pdf.",
        "Expense accounts are consistent with COA.xlsx.",
        "Voiceover reads the lines written in Script.docx.",
        "The submitted file basename is 'Sample'.",
        "The file extension is .xlsx.",
        "The deliverable must be .xlsx, not .xlsm.",
        "The deliverable is a PDF document, not a DOCX.",
        "The deliverable file name must be Report.xlsx.",
        "The deliverable file name: Report.xlsx.",
        "The filename is exactly `Report.xlsx`.",
        "The submitted file named ‘Report.xlsx’ is present.",
        "Includes data from the reference file named 'Reference.xlsx'.",
        "The zip archive contains a top-level file named package.json.",
        "The output should be reconciled to Reference.pdf.",
        "Submit exactly 1 file named 'Report.xlsx'.",
        "The workbook contains a worksheet named exactly 'Summary'.",
        "The workbook must not contain a worksheet named 'Raw'.",
        "A worksheet named 'Raw' contains accurate totals.",
        "The first worksheet is named 'Sample'.",
        "The deliverable is exactly 2 pages.",
        "The document contains at least 500 words.",
        "The archive contains exactly 3 files including package.json.",
    ],
)
def test_all_natural_language_requirements_fall_back_to_judge(criterion):
    item = RubricItem("r1", criterion, 2, None)

    assert Grader._classify(item) == ("judge", None)


@pytest.mark.parametrize(
    "criterion",
    [
        "A single deliverable exists.",
        "The document is present.",
        "The workbook extension is acceptable.",
    ],
)
def test_unparsed_generic_file_requirements_fall_back_to_judge(criterion):
    item = RubricItem("r1", criterion, 2, None)

    assert Grader._classify(item) == ("judge", None)


def test_classify_falls_back_to_judge():
    item = RubricItem("r1", "audit conclusion correctly identifies issue", 3, None)
    mode, pid = Grader._classify(item)
    assert mode == "judge"
    assert pid is None


def test_stale_precheck_pattern_cannot_decide_verdict(monkeypatch, tmp_path):
    grader = _make_grader(monkeypatch, tmp_path)
    item = RubricItem("r1", "Submit exactly 1 file.", 2, None)
    submitted = tmp_path / "Report.xlsx"
    submitted.write_bytes(b"xlsx")

    assert grader._run_precheck("count_check", item, [submitted]) is None


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


def test_extract_finish_reason_from_incomplete_details():
    """Canonical path: response.incomplete_details.reason."""
    from core.grader import _extract_finish_reason

    class _Incomplete:
        reason = "max_output_tokens"

    class _Resp:
        incomplete_details = _Incomplete()
        status = None

    assert _extract_finish_reason(_Resp(), 1600, 1600) == "max_output_tokens"


def test_extract_finish_reason_falls_back_to_status():
    from core.grader import _extract_finish_reason

    class _Resp:
        incomplete_details = None
        status = "incomplete"

    assert _extract_finish_reason(_Resp(), 1600, 1500) == "incomplete"


def test_extract_finish_reason_normalizes_max_tokens_to_length():
    from core.grader import _extract_finish_reason

    class _Resp:
        incomplete_details = None
        status = "max_tokens"

    assert _extract_finish_reason(_Resp(), 1600, 1600) == "length"


def test_extract_finish_reason_heuristic_when_usage_at_ceiling():
    """When SDK exposes neither incomplete_details nor a useful status,
    infer truncation from usage.output_tokens >= max_output."""
    from core.grader import _extract_finish_reason

    class _Resp:
        incomplete_details = None
        status = "completed"

    assert _extract_finish_reason(_Resp(), 1600, 1600) == "length"
    assert _extract_finish_reason(_Resp(), 1600, 1500) == ""


# ---------------------------------------------------------------------------
# PR1 task 100 — sign-aware model_did_right normalization
# ---------------------------------------------------------------------------

def _aggregate_one(grader, max_score, verdict, awarded=0.0):
    """Build a one-item TaskRubric+_aggregate harness for a single (max_score, verdict)."""
    from core.grader import ItemGrade
    item = RubricItem("r1", "x", max_score, None)
    t = _task(item)
    tg = grader._aggregate(
        [
            ItemGrade(
                rubric_item_id="r1",
                criterion="x",
                max_score=max_score,
                awarded_score=awarded,
                verdict=verdict,
                decided_by="judge",
                required=None,
                evidence="e",
            )
        ],
        t,
    )
    return tg.items[0]


def test_model_did_right_positive_pass(monkeypatch, tmp_path):
    """Positive item, verdict='pass' → did_right=True."""
    grader = _make_grader(monkeypatch, tmp_path)
    it = _aggregate_one(grader, max_score=2, verdict="pass", awarded=2)
    assert it.model_did_right is True


def test_model_did_right_positive_fail(monkeypatch, tmp_path):
    """Positive item, verdict='fail' → did_right=False."""
    grader = _make_grader(monkeypatch, tmp_path)
    it = _aggregate_one(grader, max_score=2, verdict="fail")
    assert it.model_did_right is False


def test_model_did_right_positive_partial(monkeypatch, tmp_path):
    """Positive item, verdict='partial' is NOT 'pass' → did_right=False (strict)."""
    grader = _make_grader(monkeypatch, tmp_path)
    it = _aggregate_one(grader, max_score=4, verdict="partial", awarded=2)
    assert it.model_did_right is False


def test_model_did_right_negative_pass_means_violation(monkeypatch, tmp_path):
    """Negative item, verdict='pass' means the bad thing happened (penalty
    applied) → did_right=False."""
    grader = _make_grader(monkeypatch, tmp_path)
    it = _aggregate_one(grader, max_score=-85, verdict="pass", awarded=-85.0)
    assert it.model_did_right is False


def test_model_did_right_negative_fail_means_clean(monkeypatch, tmp_path):
    """Negative item, verdict='fail' means the bad thing did NOT happen
    (no penalty) → did_right=True."""
    grader = _make_grader(monkeypatch, tmp_path)
    it = _aggregate_one(grader, max_score=-60, verdict="fail", awarded=0)
    assert it.model_did_right is True


def test_model_did_right_judge_error_is_conservative(monkeypatch, tmp_path):
    """judge_error → did_right=False regardless of sign (conservative)."""
    grader = _make_grader(monkeypatch, tmp_path)
    pos = _aggregate_one(grader, max_score=4, verdict="judge_error")
    neg = _aggregate_one(grader, max_score=-20, verdict="judge_error")
    assert pos.model_did_right is False
    assert neg.model_did_right is False


def test_aggregate_excludes_judge_error_from_runtime_score_denominator(
    monkeypatch, tmp_path
):
    """A producer flag omission cannot turn judge failure into model score."""
    from core.grader import ItemGrade

    grader = _make_grader(monkeypatch, tmp_path)
    task = _task(RubricItem("pass", "correct", 10, None))
    grade = grader._aggregate(
        [
            ItemGrade(
                rubric_item_id="pass",
                criterion="correct",
                max_score=10,
                awarded_score=10,
                verdict="pass",
                decided_by="judge",
                required=None,
                evidence="verified",
            ),
            ItemGrade(
                rubric_item_id="error",
                criterion="unresolved",
                max_score=90,
                awarded_score=0,
                verdict="judge_error",
                decided_by="judge",
                required=None,
                evidence="final_json_parse_failed",
                score_excluded=False,
            ),
        ],
        task,
    )

    error_item = grade.items[1]
    assert error_item.score_excluded is True
    assert error_item.model_did_right is False
    assert grade.total_awarded == 10
    assert grade.total_max == 10
    assert grade.pct == 100
    assert grade.critical_fail is False


def test_aggregate_marks_all_judge_error_task_unscored(monkeypatch, tmp_path):
    from core.grader import ItemGrade

    grader = _make_grader(monkeypatch, tmp_path)
    task = _task(RubricItem("error", "unresolved", 10, None))
    grade = grader._aggregate(
        [
            ItemGrade(
                rubric_item_id="error",
                criterion="unresolved",
                max_score=10,
                awarded_score=0,
                verdict="judge_error",
                decided_by="judge",
                required=None,
                evidence="empty_final_text",
            )
        ],
        task,
    )

    assert grade.error == "all_items_score_excluded"
    assert grade.items[0].score_excluded is True
    assert grade.total_max == 0
    assert grade.pct == 0


def test_model_did_right_persisted_in_json(monkeypatch, tmp_path):
    """asdict() in step8_grade._task_to_dict should emit the new field."""
    from dataclasses import asdict
    grader = _make_grader(monkeypatch, tmp_path)
    from core.grader import ItemGrade
    item = RubricItem("r1", "x", -85, None)
    t = _task(item)
    tg = grader._aggregate(
        [
            ItemGrade(
                rubric_item_id="r1", criterion="x", max_score=-85,
                awarded_score=0.0, verdict="fail", decided_by="judge",
                required=None, evidence="e",
            )
        ],
        t,
    )
    serialized = asdict(tg)
    assert serialized["items"][0]["model_did_right"] is True


# ---------------------------------------------------------------------------
# PR1 task 101 — critical redefinition (magnitude + sign-aware)
# ---------------------------------------------------------------------------

def test_is_critical_item_magnitude_threshold():
    """|max_score| >= MAGNITUDE_THRESHOLD covers both positive must-haves
    and negative penalty items; below threshold (positive or negative) is
    not critical."""
    from core.grader import _is_critical_item, MAGNITUDE_THRESHOLD
    assert MAGNITUDE_THRESHOLD == 4, "Project convention; bump deliberately"
    # positive
    assert _is_critical_item(4) is True
    assert _is_critical_item(5) is True
    assert _is_critical_item(100) is True
    assert _is_critical_item(3) is False
    assert _is_critical_item(0) is False
    # negative
    assert _is_critical_item(-4) is True
    assert _is_critical_item(-85) is True
    assert _is_critical_item(-3) is False
    assert _is_critical_item(-1) is False
    # degenerate
    assert _is_critical_item(None) is False


def test_critical_fail_uses_sign_aware_did_right(monkeypatch, tmp_path):
    """critical_fail should fire when ANY critical-magnitude item has
    model_did_right=False. Should NOT depend on the (always-null) required
    field anymore."""
    from core.grader import ItemGrade
    grader = _make_grader(monkeypatch, tmp_path)

    # Case A: positive critical item, verdict=fail → did_right=False → critical_fail=True
    item_a = RubricItem("r1", "x", 5, None)
    tg = grader._aggregate(
        [ItemGrade(rubric_item_id="r1", criterion="x", max_score=5,
                   awarded_score=0, verdict="fail", decided_by="judge",
                   required=None, evidence="e")],
        _task(item_a),
    )
    assert tg.critical_fail is True

    # Case B: negative critical item, verdict=pass (penalty applied!) → did_right=False → critical_fail=True
    item_b = RubricItem("r1", "x", -85, None)
    tg = grader._aggregate(
        [ItemGrade(rubric_item_id="r1", criterion="x", max_score=-85,
                   awarded_score=-85.0, verdict="pass", decided_by="judge",
                   required=None, evidence="e")],
        _task(item_b),
    )
    assert tg.critical_fail is True

    # Case C: negative critical item, verdict=fail (no penalty) → did_right=True → critical_fail=False
    tg = grader._aggregate(
        [ItemGrade(rubric_item_id="r1", criterion="x", max_score=-85,
                   awarded_score=0.0, verdict="fail", decided_by="judge",
                   required=None, evidence="e")],
        _task(item_b),
    )
    assert tg.critical_fail is False

    # Case D: positive non-critical item (score=2), verdict=fail → critical_fail=False
    item_d = RubricItem("r1", "x", 2, None)
    tg = grader._aggregate(
        [ItemGrade(rubric_item_id="r1", criterion="x", max_score=2,
                   awarded_score=0, verdict="fail", decided_by="judge",
                   required=None, evidence="e")],
        _task(item_d),
    )
    assert tg.critical_fail is False


# ---------------------------------------------------------------------------
# PR1 task 102 — positive-only denominator + pct_raw diagnostics
# ---------------------------------------------------------------------------

def test_max_score_excludes_negative_items():
    """TaskRubric.max_score must sum positive item scores only.
    Negative penalty items still count in total_awarded (via judge output)
    but never as part of the maximum-achievable denominator."""
    from core.rubric_loader import RubricItem, TaskRubric
    task = TaskRubric(
        task_id="t", sector="s", occupation="o", prompt="p",
        rubric_items=[
            RubricItem("r1", "good thing", 5, None),     # +5
            RubricItem("r2", "good thing", 2, None),     # +2
            RubricItem("r3", "bad penalty", -85, None),  # -85 (excluded)
        ],
        rubric_pretty="", reference_files=[], gold_deliverable_files=[],
    )
    assert task.max_score == 7, "max_score must sum positive scores only"


def test_pct_raw_preserves_negative_value(monkeypatch, tmp_path):
    """When a task has more penalty than credit, pct_raw must reflect the
    true negative ratio while pct is clamped to 0."""
    from core.grader import ItemGrade
    from core.rubric_loader import RubricItem, TaskRubric
    grader = _make_grader(monkeypatch, tmp_path)
    task = TaskRubric(
        task_id="t", sector="s", occupation="o", prompt="p",
        rubric_items=[
            RubricItem("r1", "good", 10, None),
            RubricItem("r2", "bad penalty", -85, None),
        ],
        rubric_pretty="", reference_files=[], gold_deliverable_files=[],
    )
    tg = grader._aggregate(
        [
            # model satisfied the good criterion (full credit)
            ItemGrade(rubric_item_id="r1", criterion="good", max_score=10,
                      awarded_score=10, verdict="pass", decided_by="judge",
                      required=None, evidence="e"),
            # model violated the penalty criterion (pass on negative item = bad)
            ItemGrade(rubric_item_id="r2", criterion="bad", max_score=-85,
                      awarded_score=-85.0, verdict="pass", decided_by="judge",
                      required=None, evidence="e"),
        ],
        task,
    )
    # denominator = 10 (positive only)
    assert tg.total_max == 10
    # total_awarded = 10 + (-85) = -75
    assert tg.total_awarded == -75.0
    # raw pct = -75 / 10 * 100 = -750%
    assert tg.pct_raw == -750.0
    # clamped pct = 0 (schema-safe headline)
    assert tg.pct == 0.0
    # critical_fail = True (the -85 penalty was applied)
    assert tg.critical_fail is True


def test_pct_raw_emitted_in_json(monkeypatch, tmp_path):
    from dataclasses import asdict
    from core.grader import ItemGrade
    from core.rubric_loader import RubricItem, TaskRubric
    grader = _make_grader(monkeypatch, tmp_path)
    task = TaskRubric(
        task_id="t", sector="s", occupation="o", prompt="p",
        rubric_items=[RubricItem("r1", "x", 4, None)],
        rubric_pretty="", reference_files=[], gold_deliverable_files=[],
    )
    tg = grader._aggregate(
        [ItemGrade(rubric_item_id="r1", criterion="x", max_score=4,
                   awarded_score=4, verdict="pass", decided_by="judge",
                   required=None, evidence="e")],
        task,
    )
    serialized = asdict(tg)
    assert serialized["pct_raw"] == 100.0
    assert serialized["pct"] == 100.0


def test_zero_total_max_degenerate_task(monkeypatch, tmp_path):
    """Task with no positive items: total_max=0 — pct=0 (no crash), pct_raw
    surfaces the absolute awarded value as diagnostic signal."""
    from core.grader import ItemGrade
    from core.rubric_loader import RubricItem, TaskRubric
    grader = _make_grader(monkeypatch, tmp_path)
    task = TaskRubric(
        task_id="t", sector="s", occupation="o", prompt="p",
        rubric_items=[RubricItem("r1", "bad", -20, None)],
        rubric_pretty="", reference_files=[], gold_deliverable_files=[],
    )
    tg = grader._aggregate(
        [ItemGrade(rubric_item_id="r1", criterion="bad", max_score=-20,
                   awarded_score=-20.0, verdict="pass", decided_by="judge",
                   required=None, evidence="e")],
        task,
    )
    assert tg.total_max == 0
    assert tg.pct == 0.0
    assert tg.pct_raw == -20.0


def test_list_files_accepts_regular_nested_tree(tmp_path):
    grader = object.__new__(Grader)
    root = tmp_path / "deliverables"
    nested = root / "nested"
    nested.mkdir(parents=True)
    expected = nested / "out.txt"
    expected.write_text("ok", encoding="utf-8")

    assert grader._list_files(root) == [expected]


@pytest.mark.parametrize("symlink_kind", ["file", "directory", "parent"])
def test_list_files_rejects_symlink_layers(tmp_path, symlink_kind):
    grader = object.__new__(Grader)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("secret", encoding="utf-8")

    if symlink_kind == "parent":
        linked_parent = tmp_path / "linked-parent"
        linked_parent.symlink_to(outside, target_is_directory=True)
        deliverable_dir = linked_parent
    else:
        deliverable_dir = tmp_path / "deliverables"
        deliverable_dir.mkdir()
        if symlink_kind == "file":
            (deliverable_dir / "secret.txt").symlink_to(outside / "secret.txt")
        else:
            (deliverable_dir / "linked-dir").symlink_to(
                outside, target_is_directory=True
            )

    with pytest.raises(ValueError, match="symlink"):
        grader._list_files(deliverable_dir)


# ---------------------------------------------------------------------------
# Task 207 — legacy grader strip
# ---------------------------------------------------------------------------


def test_config_without_read_deliverable_tool_is_rejected(tmp_path):
    """A v1-shaped config must fail at construction, not grade differently.

    Before task 207 such a config silently took the text-extract path and
    produced grades that were not comparable with the tool-calling path.
    That path is gone, so the only safe response is to refuse the config.
    """
    config = _config(tmp_path)
    del config["judge"]["tools"]

    with pytest.raises(ValueError, match="judge.tools.read_deliverable"):
        Grader(config=config, rubric_loader=_Loader(), client=_FakeClient())


def test_legacy_batch_and_text_extract_surface_is_gone():
    """The task 207 acceptance grep, asserted in code.

    `core/grader_batch.py` and the batch / tier-routing / text-extract
    members of `Grader` must not come back by accident.
    """
    import core.grader as grader_mod

    assert not hasattr(grader_mod, "BatchJudge")
    for name in (
        "_use_batch",
        "_tier_judges",
        "_build_tier_judges",
        "_route_to_tier",
        "_resolve_batch_prompt_path",
        "_grade_task_batched",
        "_summarize_deliverables",
        "_build_prompt",
        "_call_judge",
        "_safe_parse_judge_json",
    ):
        assert not hasattr(Grader, name), f"legacy grader member survived: {name}"

    with pytest.raises(ModuleNotFoundError):
        __import__("core.grader_batch")


def test_no_active_grading_config_declares_legacy_knobs():
    """No shipped config may carry the removed knobs.

    Archived v1 configs under `_archive_v1/` are excluded: `grade-run.yml`
    validates `grading_config` against `^[A-Za-z0-9][A-Za-z0-9._-]*\\.ya?ml$`,
    which forbids a path separator, so they cannot be dispatched.
    """
    import yaml

    configs_dir = Path(__file__).resolve().parent.parent / "grading_configs"
    for path in sorted(configs_dir.glob("*.yaml")):
        config = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        grader_block = config.get("grader") or {}
        assert "deliverable_extract_max_chars" not in grader_block, path.name
        assert "batch_size" not in grader_block, path.name
        assert "judge_routing" not in config, path.name
        assert (config.get("judge") or {}).get("tools", {}).get(
            "read_deliverable"
        ), f"{path.name} does not opt into the tool-calling judge"
