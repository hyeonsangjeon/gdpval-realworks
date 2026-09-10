"""A task refused for rate was told it had three attempts, and got one.

Run `34485072751` attempted five tasks. Three of them ended here:

    [1/5] 02aa1805-...-02dec146063a (Financial Managers)... ✗
    the Codex turn failed: stream disconnected before completion: Your
    requests to gpt-5.4 for gpt-5.4 in eastus2 have exceeded rate limit.

The experiment file running them, `exp033_codex_foundry_fixed5.yaml`, sets
`execution.max_retries: 2` and says beside it:

    # Attempts after an infrastructure failure, per task. Three at most, each
    # a fresh session. The model's own judgement never causes one: Self-QA is
    # off.

and in its header:

    5 tasks x at most 3 turns each  = 15 turns, worst case

Neither was true. `max_retries` was resolved from the config, printed at
startup as "(per task, infra)", and then never read again -- the only place a
failed task left the loop was a `break`. The run sent five turns, not up to
fifteen, and three tasks were recorded as failures of the harness on the first
refusal a minute's wait would have cleared.

Two things had to be true before a retry could be right, and neither was:

* The run had to know *why* a turn failed. `CodexRunOutcome.error_category`
  existed and every failed turn got the same word, `turn_failed`, which is
  true of a rate limit and of a task the agent could not do.
* That word had to survive into the task result. It was set on the runner's
  dict and dropped by the step that builds the record.

So a retry is not the whole change. The change is that a failure now says
what kind it is, that the kind reaches the record, and that only the kinds
another attempt can fix cause one.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

import step2_run_inference as step2
from core.codex_runner import _turn_failure_category
from core.execution_errors import classify_execution_error
from step2_run_inference import (
    INFRA_RETRY_BACKOFF_SECONDS,
    INFRA_RETRY_MAX_TOTAL_WAIT_SECONDS,
    RETRYABLE_INFRA_ERROR_CATEGORIES,
    _build_execution_observability,
    infra_retry_category,
    infra_retry_pause_seconds,
    run_with_infra_retries,
)


#: What the deployment said, three times, on run 34485072751. The deployment
#: name is the one the run recorded; nothing here depends on it being that.
THE_REFUSAL = (
    "stream disconnected before completion: Your requests to gpt-5.4 for "
    "gpt-5.4 in eastus2 have exceeded rate limit."
)


def a_failure(category=None, status="error"):
    """A task result of the shape `_execute_single_task` returns."""
    observability = {"preprocessors": []}
    if category is not None:
        observability["error_category"] = category
    return {"task_id": "t", "status": status, "observability": observability}


# ── the word for what happened ───────────────────────────────────────────


def test_the_message_that_ended_three_tasks_is_named():
    assert classify_execution_error(THE_REFUSAL) == "rate_limited"


def test_the_codex_turn_now_records_why_it_failed():
    assert _turn_failure_category(THE_REFUSAL) == "rate_limited"


def test_a_failure_that_says_nothing_is_still_turn_failed():
    """The fallback is the old answer, not the classifier's.

    `classify_execution_error` ends at `execution_error`, which says less than
    `turn_failed` does -- a turn is not generated code, and "the turn failed"
    is at least true of where it happened.
    """
    assert _turn_failure_category("the stream ended") == "turn_failed"


@pytest.mark.parametrize(
    "text",
    [
        "Requests to the model deployment have exceeded rate limit",
        "Rate limit reached for this deployment",
        "429 - Too Many Requests",
        "Error code: 429 - {'error': {'code': 'RateLimitReached'}}",
        "HTTP 429 returned by the endpoint",
        "openai.RateLimitError: Requests to the model exceeded the limit",
    ],
)
def test_the_ways_a_provider_says_it(text):
    assert classify_execution_error(text) == "rate_limited"


def test_a_line_number_is_not_a_rate_limit():
    """Why bare `429` is not a marker.

    A traceback names lines. Reading `line 429` as a transient refusal would
    make a deterministic defect worth three paid attempts, which is the exact
    failure mode this change has to avoid introducing.
    """
    assert classify_execution_error(
        'File "run.py", line 429, in main\n    ValueError: bad column'
    ) == "value_error"


def test_a_bare_number_is_not_a_rate_limit():
    assert classify_execution_error("exited with 429 rows written") != "rate_limited"


@pytest.mark.parametrize(
    ("text", "category"),
    [
        ("MemoryError", "out_of_memory"),
        ("the process timed out", "timeout"),
        ("SyntaxError: invalid syntax", "syntax_error"),
        ("ModuleNotFoundError: No module named 'pandas'", "import_error"),
        ("KeyError: 'revenue'", "schema_error"),
        ("UnicodeDecodeError: not valid utf-8", "binary_decode_error"),
        ("PermissionError: denied", "permission_error"),
        ("FileNotFoundError: no such file", "file_not_found"),
        ("TypeError: unsupported operand", "type_error"),
        ("ValueError: bad literal", "value_error"),
        ("AttributeError: no attribute", "api_compatibility"),
        ("something else entirely", "execution_error"),
        ("", None),
    ],
)
def test_the_categories_that_were_there_before_are_unchanged(text, category):
    """A new word must not have taken any of the old ones' texts."""
    assert classify_execution_error(text) == category


def test_the_category_carries_none_of_the_message():
    """It is published, so it must be a word and not a sentence.

    `core/public_error.py` strips the endpoint and the wording out of every
    error before it is persisted. A category that quoted the message would put
    both back through a different field.
    """
    category = classify_execution_error(THE_REFUSAL)

    assert category == "rate_limited"
    for secret in ("gpt-5.4", "eastus2", "requests", "exceeded"):
        assert secret not in category


# ── the word reaching the record ─────────────────────────────────────────


def test_the_record_says_why_the_task_failed():
    observability = _build_execution_observability(
        {"error_category": "rate_limited"}, []
    )

    assert observability["error_category"] == "rate_limited"


def test_a_result_that_says_nothing_records_nothing():
    assert "error_category" not in _build_execution_observability({}, [])
    assert "error_category" not in _build_execution_observability(None, [])


@pytest.mark.parametrize("category", [None, "", 7, ["rate_limited"], {}])
def test_only_a_word_is_recorded(category):
    observability = _build_execution_observability(
        {"error_category": category}, []
    )

    assert "error_category" not in observability


def test_a_long_category_cannot_smuggle_a_message():
    observability = _build_execution_observability(
        {"error_category": "x" * 5000}, []
    )

    assert len(observability["error_category"]) == 80


# ── which failures are worth another attempt ─────────────────────────────


def test_a_rate_limited_task_is_retried():
    assert infra_retry_category(a_failure("rate_limited")) == "rate_limited"


def test_a_turn_that_never_started_is_retried():
    """`_run_one_turn` abandons the reservation here: nothing was billed."""
    assert infra_retry_category(a_failure("turn_start_failed")) == (
        "turn_start_failed"
    )


@pytest.mark.parametrize(
    "category",
    [
        # The turn was sent and may have been billed, and the runner keeps
        # the files the agent had written before it was interrupted. A retry
        # would pay twice and throw those away.
        "timeout",
        # The turn failed and the text did not say why -- which is exactly
        # when a second identical attempt fails identically.
        "turn_failed",
        # The local environment and its configuration. A minute's wait does
        # not change either.
        "runtime_unavailable",
        "runtime_start_failed",
        "session_start_failed",
        # Defects in what the model produced.
        "syntax_error",
        "value_error",
        "out_of_memory",
        "execution_error",
    ],
)
def test_a_failure_another_attempt_cannot_fix_is_not_retried(category):
    assert infra_retry_category(a_failure(category)) is None


def test_a_success_is_not_retried():
    assert infra_retry_category(a_failure("rate_limited", status="success")) is None


def test_a_failure_with_no_category_is_not_retried():
    """Silence is not permission. Most of the pipeline's failures are
    deterministic, and an unlabelled one is more likely to be one of those."""
    assert infra_retry_category(a_failure()) is None
    assert infra_retry_category({"status": "error"}) is None
    assert infra_retry_category({}) is None


def test_the_retryable_set_is_small_and_named():
    assert RETRYABLE_INFRA_ERROR_CATEGORIES == frozenset(
        {"rate_limited", "turn_start_failed"}
    )


# ── how long to wait ─────────────────────────────────────────────────────


def test_the_first_wait_clears_the_window_that_refused_it():
    """An Azure OpenAI rate limit is counted over sixty seconds.

    Retrying inside that window does not fail differently; it fails sooner and
    spends an attempt from a budget of three.
    """
    assert infra_retry_pause_seconds(0) >= 60.0


def test_each_wait_is_longer_than_the_one_before():
    waits = [infra_retry_pause_seconds(n) for n in range(len(INFRA_RETRY_BACKOFF_SECONDS))]

    assert waits == sorted(waits)
    assert len(set(waits)) == len(waits)


def test_a_further_attempt_waits_as_long_as_the_last_one():
    last = INFRA_RETRY_BACKOFF_SECONDS[-1]

    assert infra_retry_pause_seconds(len(INFRA_RETRY_BACKOFF_SECONDS)) == last
    assert infra_retry_pause_seconds(99) == last


def test_an_attempt_index_below_zero_is_refused():
    with pytest.raises(ValueError, match="infra attempt index is negative"):
        infra_retry_pause_seconds(-1)


# ── the loop ─────────────────────────────────────────────────────────────


def a_run(results, *, max_attempts, sleep=None):
    """Drive `run_with_infra_retries` over a fixed sequence of results."""
    attempts: list[int] = []
    slept: list[float] = []
    cleared: list[int] = []

    def attempt(index: int) -> dict:
        attempts.append(index)
        return results[min(index, len(results) - 1)]

    final = run_with_infra_retries(
        attempt,
        max_attempts=max_attempts,
        before_retry=lambda: cleared.append(len(attempts)),
        sleep=sleep if sleep is not None else slept.append,
    )
    return final, attempts, slept, cleared


def test_the_run_that_gave_up_would_now_try_three_times():
    """exp033's own numbers: `max_retries: 2`, so three attempts."""
    _, attempts, slept, _ = a_run(
        [a_failure("rate_limited")], max_attempts=3
    )

    assert attempts == [0, 1, 2]
    assert slept == [60.0, 120.0]


def test_a_task_that_succeeds_on_the_second_attempt_stops_there():
    final, attempts, slept, _ = a_run(
        [a_failure("rate_limited"), a_failure(status="success")],
        max_attempts=3,
    )

    assert final["status"] == "success"
    assert attempts == [0, 1]
    assert slept == [60.0]


def test_nothing_is_retried_when_the_first_attempt_succeeds():
    _, attempts, slept, cleared = a_run(
        [a_failure(status="success")], max_attempts=3
    )

    assert attempts == [0]
    assert slept == []
    assert cleared == []


def test_a_deterministic_failure_is_attempted_once():
    _, attempts, slept, _ = a_run([a_failure("value_error")], max_attempts=3)

    assert attempts == [0]
    assert slept == []


def test_max_retries_zero_means_one_attempt():
    """What hardened execution fixes, and what it must keep meaning."""
    _, attempts, slept, _ = a_run([a_failure("rate_limited")], max_attempts=1)

    assert attempts == [0]
    assert slept == []


@pytest.mark.parametrize("max_attempts", [0, -1])
def test_a_nonsense_ceiling_still_attempts_the_task_once(max_attempts):
    """A bad setting must not silently skip the task it configures."""
    _, attempts, _, _ = a_run([a_failure("rate_limited")], max_attempts=max_attempts)

    assert attempts == [0]


def test_the_files_of_a_failed_attempt_are_cleared_before_the_wait():
    """Cleared once per retry, and before the sleep rather than after it.

    A job cancelled during the wait should not leave a failed attempt's
    leftovers behind looking like the task's answer.
    """
    _, attempts, _, cleared = a_run(
        [a_failure("rate_limited")], max_attempts=3
    )

    # One clear per retry, each recorded when exactly that many attempts had
    # been made -- so the clear happened between attempts, not after the last.
    assert cleared == [1, 2]
    assert attempts == [0, 1, 2]


def test_the_wait_budget_ends_the_retries():
    """The stop condition. A provider refusing everything must not be able to
    make one task sleep through a job's whole time limit."""
    budget = INFRA_RETRY_MAX_TOTAL_WAIT_SECONDS
    _, attempts, slept, _ = a_run([a_failure("rate_limited")], max_attempts=99)

    assert sum(slept) <= budget
    # It stopped for the budget, not for the ceiling.
    assert len(attempts) < 99


def test_the_budget_is_reported_when_it_ends_the_retries(capsys):
    a_run([a_failure("rate_limited")], max_attempts=99)

    printed = capsys.readouterr().out
    assert "retry wait budget" in printed
    assert "rate_limited" in printed


def test_the_last_result_is_returned_even_when_every_attempt_failed():
    """This decides how many times to ask, not what to do with the answer."""
    final, _, _, _ = a_run([a_failure("rate_limited")], max_attempts=3)

    assert final["status"] == "error"


def test_a_sleep_that_is_not_called_is_a_retry_that_did_not_happen():
    """Guards the shape of the test above: the fake sleep really is the wait."""
    calls: list[float] = []

    def sleep(seconds: float) -> None:
        calls.append(seconds)

    a_run([a_failure("rate_limited")], max_attempts=2, sleep=sleep)

    assert calls == [60.0]


# ── the setting is actually read ─────────────────────────────────────────


def _run_task_with_qa_ast():
    """The body of the function that runs one task, as a tree.

    Everything above tests a helper in isolation, and the defect this change
    fixes was not in a helper: `max_retries` was resolved correctly, printed
    correctly, and then not used. A whole file of passing helper tests is
    exactly what that bug would have looked like from here, so the wiring is
    asserted too.
    """
    source = pathlib.Path(step2.__file__).read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.FunctionDef) and node.name == "_run_task_with_qa":
            return node
    raise AssertionError("_run_task_with_qa is gone; this test needs rewriting")


def _the_retry_call():
    for node in ast.walk(_run_task_with_qa_ast()):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "run_with_infra_retries"
        ):
            return node
    raise AssertionError(
        "_run_task_with_qa does not call run_with_infra_retries -- the retry "
        "budget is resolved and unread again, which is the original defect"
    )


def test_the_task_loop_asks_for_the_retries():
    assert _the_retry_call() is not None


def test_the_ceiling_comes_from_the_experiment_file():
    """Not a literal. `infra_max_attempts` is `execution.max_retries` + 1."""
    keywords = {kw.arg: kw.value for kw in _the_retry_call().keywords}
    ceiling = keywords["max_attempts"]

    assert isinstance(ceiling, ast.Name)
    assert ceiling.id == "infra_max_attempts"


def test_the_failed_attempt_is_cleaned_up_between_tries():
    keywords = {kw.arg: kw.value for kw in _the_retry_call().keywords}
    before_retry = keywords["before_retry"]

    assert isinstance(before_retry, ast.Name)
    assert before_retry.id == "_clear_task_files"


def test_the_ceiling_is_one_more_than_the_configured_retries():
    """`max_retries` counts retries; attempts are one more than that.

    exp033 says `execution.max_retries: 2` and "three at most". The expression
    is lifted out of the source and evaluated, rather than restated here --
    a copy of the formula would agree with itself no matter what the pipeline
    actually computes.
    """
    source = pathlib.Path(step2.__file__).read_text(encoding="utf-8")
    formula = None
    for node in ast.walk(ast.parse(source)):
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "infra_max_attempts"
        ):
            formula = node.value
    assert formula is not None, "infra_max_attempts is no longer computed"

    compiled = compile(ast.Expression(formula), "<step2>", "eval")
    for configured, attempts in ((2, 3), (0, 1), (None, 1), (-5, 1), (6, 7)):
        assert eval(compiled, {"max_retries": configured}) == attempts  # noqa: S307


# ── what the ledger is told ──────────────────────────────────────────────


def test_an_infrastructure_retry_is_its_own_kind_of_retry():
    """`RETRY_INFRASTRUCTURE` has been in the ledger's vocabulary since it was
    written, and until now nothing passed it -- so every receipt could say
    only "first attempt" or "the model tried again"."""
    from core.cost_receipts import RETRY_INFRASTRUCTURE, RETRY_KINDS

    assert RETRY_INFRASTRUCTURE in RETRY_KINDS
    assert step2.RETRY_INFRASTRUCTURE is RETRY_INFRASTRUCTURE
