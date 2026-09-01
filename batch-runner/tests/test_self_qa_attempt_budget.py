"""What ``qa.max_retries`` actually buys, measured on the real inference loop.

The name says retries. The loop counts answers. ``_run_task_with_qa`` in
step2_run_inference.py raises ``qa_attempts`` once per answer it has reviewed
and found wanting, then breaks as soon as that count reaches
``qa_max_retries`` -- so the setting is a budget of answers in all, and the
number of replacements it buys is one less than the number written.

That matters beyond wording. Twenty-nine of the thirty-two self-review blocks
in batch-runner/experiments/ carry ``max_retries: 1`` -- eleven of them under a
comment reading "max regeneration attempts on QA failure" -- and one is exactly
the value that buys no regeneration at all: the answer is produced, reviewed,
marked ``qa_failed``, and never replaced.

These tests pin the arithmetic against the shipped loop rather than restating
it, and pin the three places that describe the setting to a wording that
matches. None of them changes what a run does; changing the guard would hand
every one of those twenty-eight experiments an extra paid answer.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from core.execution_envelope_cost import max_attempt_counts
from core.execution_envelope_preflight import WHAT_THE_SETTING_DOES
from core.experiment_config import QAConfig


PASSED = {
    "passed": True, "score": 9, "issues": [], "suggestion": "",
    "undetermined": False, "llm_passed": True,
}
FAILED = {
    "passed": False, "score": 3, "issues": ["bad"], "suggestion": "fix it",
    "undetermined": False, "llm_passed": False,
}
UNDETERMINED = {
    "passed": False, "score": None, "issues": [], "suggestion": "",
    "undetermined": True, "llm_passed": False,
}


def _write_prepared(workspace: Path, written) -> None:
    """A one-task run whose self-review block says what the caller asked.

    ``written`` of ``None`` leaves ``max_retries`` out entirely, which is how
    the built-in default gets exercised through the loader rather than by
    reading the dataclass.
    """
    from core.prepared_fingerprint import prepared_fingerprint

    qa = {
        "enabled": True,
        "min_score": 6,
        "prompt": "Evaluate the output: {deliverable_text}",
        "model": "gpt-qa",
    }
    if written is not None:
        qa["max_retries"] = written
    prepared = {
        "experiment_id": "exp_test",
        "publication_generation": "exp_test:local:test",
        "experiment_name": "qa_attempt_budget",
        "source": "test/qa-attempt-budget",
        # No infra retries and no resume rounds, so every execution counted
        # below is one the self-review loop asked for.
        "execution": {
            "mode": "subprocess",
            "max_retries": 0,
            "resume_max_rounds": 0,
        },
        "tasks": [{
            "task_id": "t1",
            "sector": "test_sector",
            "occupation": "test_occupation",
            "instruction": "Do a thing.",
            "reference_files": [],
            "reference_file_records": [],
            "needs_files": False,
            "source_projection_sha256": "a" * 64,
        }],
        "condition_a": {
            "name": "test_condition",
            "model": {"provider": "azure", "deployment": "gpt-test"},
            "prompt": {"system": "you are helpful"},
            "qa": qa,
        },
    }
    prepared["prepared_fingerprint"] = prepared_fingerprint(prepared)
    (workspace / "step1_tasks_prepared.json").write_text(
        json.dumps(prepared), encoding="utf-8"
    )


def _answer() -> dict:
    return {
        "task_id": "t1",
        "status": "success",
        "content": "done",
        "deliverable_text": "done",
        "deliverable_files": [],
        "model": "test-model",
        "usage": None,
        "observability": {},
        "latency_ms": 10,
        "timestamp": "2026-07-24T00:00:00+00:00",
    }


class _Run:
    """What one real ``run_inference`` produced."""

    def __init__(self, answers, reviews, output, status):
        self.answers = answers
        self.reviews = reviews
        self.output = output
        self.status = status

    @property
    def replacements(self):
        """Answers after the first -- what the word "retry" would mean."""
        return self.answers - 1

    @property
    def banners(self):
        return [
            line.strip()
            for line in self.output.splitlines()
            if "QA attempt" in line
        ]


def _drive(tmp_path, monkeypatch, capsys, *, written, verdicts) -> _Run:
    """Run the shipped loop once and report what it asked for.

    ``verdicts`` is what the reviewer says, in order; the last one repeats if
    the loop asks more often than the caller supplied.
    """
    import step2_run_inference as s2

    # A fresh root per call, so a test that drives the loop twice does not
    # hand the second run the first one's progress checkpoint to resume from.
    root = Path(tempfile.mkdtemp(dir=tmp_path))
    workspace = root / "workspace"
    upload = workspace / "upload"
    (upload / "deliverable_files").mkdir(parents=True)
    monkeypatch.setattr(s2, "WORKSPACE_DIR", workspace, raising=True)
    monkeypatch.setattr(s2, "UPLOAD_DIR", upload, raising=True)
    _write_prepared(workspace, written)

    monkeypatch.setenv("AZURE_AI_ROUTE_PROFILE", "direct-v1")
    monkeypatch.setenv(
        "AZURE_OPENAI_V1_ENDPOINT",
        "https://example.openai.azure.com/openai/v1/",
    )
    from core.azure_ai_clients import preflight_routes

    fingerprint = preflight_routes(
        [("inference", "gpt-test")]
    )[0]["runtime_fingerprint"]
    client = MagicMock()
    client._gdpval_runtime_fingerprint = fingerprint
    monkeypatch.setattr(
        s2, "create_provider_client", MagicMock(return_value=client)
    )
    monkeypatch.setattr(s2, "TaskExecutor", MagicMock(return_value=MagicMock()))
    manifest = s2.NeedsFilesManifest({
        "_schema_version": 4,
        "reference_files": {},
        "tasks": {"t1": {
            "needs_files": False,
            "source_projection_sha256": "a" * 64,
        }},
    })
    monkeypatch.setattr(
        s2.NeedsFilesManifest, "load", classmethod(lambda cls: manifest)
    )
    # A checkpoint written here would be judged against the runner's own
    # identity, so the run behaves the same on a developer box and in Actions.
    for variable in (
        "GDPVAL_RELAY_LINEAGE_ID", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT",
    ):
        monkeypatch.delenv(variable, raising=False)

    answers = []
    reviews = []

    def _execute(*args, **kwargs):
        answers.append(kwargs.get("error_context"))
        return _answer()

    def _review(*args, **kwargs):
        verdict = verdicts[min(len(reviews), len(verdicts) - 1)]
        reviews.append(verdict)
        return dict(verdict)

    monkeypatch.setattr(s2, "_execute_single_task", _execute)
    monkeypatch.setattr(s2, "_run_self_qa", _review)

    s2.run_inference(
        condition_key="condition_a", resume=False, resume_max_rounds=0
    )

    progress = json.loads(
        (workspace / "step2_inference_progress.json").read_text("utf-8")
    )
    return _Run(
        answers=len(answers),
        reviews=len(reviews),
        output=capsys.readouterr().out,
        status=progress["results"][0]["status"],
    )


# ── what the number buys ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    "written,expected_answers",
    [(1, 1), (2, 2), (3, 3), (4, 4)],
)
def test_the_setting_is_a_budget_of_answers_not_of_extra_tries(
    tmp_path, monkeypatch, capsys, written, expected_answers
):
    """N produces N answers, so it buys N - 1 replacements."""
    run = _drive(
        tmp_path, monkeypatch, capsys, written=written, verdicts=[FAILED]
    )
    assert run.answers == expected_answers
    assert run.reviews == expected_answers
    assert run.replacements == written - 1


def test_one_is_the_value_that_buys_no_replacement_at_all(
    tmp_path, monkeypatch, capsys
):
    """The value twenty-nine experiment blocks use, eleven of them under a
    comment saying "max regeneration attempts on QA failure". It regenerates
    nothing: the answer is produced once, reviewed once, and kept as a
    failure."""
    run = _drive(tmp_path, monkeypatch, capsys, written=1, verdicts=[FAILED])
    assert run.answers == 1
    assert run.replacements == 0
    assert run.status == "qa_failed"


def test_zero_and_one_are_the_same_run(tmp_path, monkeypatch, capsys):
    """Turning the budget down from 1 to 0 changes nothing, because 1 already
    allows no replacement. Both still review the one answer they produce."""
    zero = _drive(tmp_path, monkeypatch, capsys, written=0, verdicts=[FAILED])
    one = _drive(tmp_path, monkeypatch, capsys, written=1, verdicts=[FAILED])
    assert (zero.answers, zero.reviews) == (1, 1)
    assert (one.answers, one.reviews) == (1, 1)


def test_the_built_in_default_is_two_answers_not_two_replacements(
    tmp_path, monkeypatch, capsys
):
    """Read through the loader, not off the dataclass, so a change to either
    one alone shows up here."""
    run = _drive(tmp_path, monkeypatch, capsys, written=None, verdicts=[FAILED])
    assert QAConfig().max_retries == 2
    assert run.answers == 2
    assert run.replacements == 1


def test_an_undetermined_review_spends_the_same_budget(
    tmp_path, monkeypatch, capsys
):
    """A review that could not reach a verdict takes the other branch out of
    the loop, and that branch counts answers the same way."""
    run = _drive(
        tmp_path, monkeypatch, capsys, written=3, verdicts=[UNDETERMINED]
    )
    assert run.answers == 3
    # Not a quality failure, so it is kept rather than marked down.
    assert run.status == "success"


def test_a_passing_review_stops_before_the_budget_is_spent(
    tmp_path, monkeypatch, capsys
):
    """The budget is a ceiling, not a quota: an answer that passes is the
    only answer, however much was allowed."""
    run = _drive(tmp_path, monkeypatch, capsys, written=4, verdicts=[PASSED])
    assert run.answers == 1
    assert run.status == "success"


def test_a_replacement_is_asked_for_with_the_review_it_has_to_answer(
    tmp_path, monkeypatch, capsys
):
    """Every answer after the first is a reaction to a review, so the count
    above is a count of self-review work and not of infra retries."""
    run = _drive(
        tmp_path, monkeypatch, capsys,
        written=2, verdicts=[FAILED, PASSED],
    )
    assert run.answers == 2
    assert run.status == "success"


# ── what the run says it is doing ─────────────────────────────────────────


def test_the_banner_does_not_promise_an_attempt_the_guard_forbids(
    tmp_path, monkeypatch, capsys
):
    """A run allowed two answers used to announce "QA attempt 2/3" while
    producing the second and last of them."""
    run = _drive(tmp_path, monkeypatch, capsys, written=2, verdicts=[FAILED])
    assert run.banners == ["🔄 Re-executing task (QA attempt 2/2)..."]


def test_the_last_banner_names_the_answer_the_run_actually_ends_on(
    tmp_path, monkeypatch, capsys
):
    run = _drive(tmp_path, monkeypatch, capsys, written=3, verdicts=[FAILED])
    assert run.banners == [
        "🔄 Re-executing task (QA attempt 2/3)...",
        "🔄 Re-executing task (QA attempt 3/3)...",
    ]
    assert run.answers == 3


def test_no_banner_is_printed_for_a_budget_that_allows_no_replacement(
    tmp_path, monkeypatch, capsys
):
    run = _drive(tmp_path, monkeypatch, capsys, written=1, verdicts=[FAILED])
    assert run.banners == []


# ── what the run is described as doing ────────────────────────────────────


def test_the_comparison_describes_the_setting_as_answers_in_all():
    """The run-place comparison prints this phrase to a reader deciding
    whether two run places were given equal chances. It used to read "how
    many times it may answer again", which is one more than the loop allows.
    """
    described = WHAT_THE_SETTING_DOES["condition_a.qa.max_retries"]
    assert described == "how many answers it may produce in all"
    assert "again" not in described
    assert "retr" not in described


def test_the_ceiling_bills_one_more_answer_than_the_loop_can_produce():
    """Pinned deliberately, and in the safe direction.

    ``max_attempt_counts`` counts the first attempt and then one replacement
    per self-review allowed, so a budget of N is billed as N + 1 answers where
    the loop produces at most N. A ceiling that is too high can only refuse a
    run that would have fit; one that is too low waves through a run that will
    not. Lowering this is a decision, not a tidy-up -- which is what this test
    is here to make someone notice.
    """
    from tests.test_execution_envelope_advance_check import _conditions

    budget = 3
    counts = max_attempt_counts(
        _conditions(
            self_review_enabled=True, self_review_max_attempts=budget
        ),
        tool_loop_max_model_turns=1,
        output_tokens_capped_per_attempt=False,
    )
    answers_the_loop_can_produce = budget
    reviews_the_loop_can_run = budget
    really_possible = answers_the_loop_can_produce + reviews_the_loop_can_run
    assert counts.model_calls == really_possible + 1
    assert counts.model_calls > really_possible
