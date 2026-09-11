"""The analyzer has to be able to say "I cannot tell you that".

`scripts/analyze_codex_run.py` answers three questions exp034 registered
before it was allowed to spend. The danger in a tool like that is not that it
computes a rate wrongly; it is that it computes a rate at all when the run did
not contain the evidence for one. Every failure mode below produces a number
that looks fine:

* a run where nothing failed, reporting "0% of failures were short" as though
  the association had been tested and found absent;
* a bucket with no tasks in it, reporting 0% instead of saying the bucket was
  empty;
* an artifact whose task statements did not load, quietly shrinking the
  denominator so the surviving tasks carry the whole conclusion;
* `items_seen` missing from every task, reported as zero rather than as never
  measured;
* a ledger whose dollar figures are all unknown, summed to `0`.

So the tests here are mostly *negative*: they build a run in which a question
is unanswerable and require the analyzer to decline. The two positive tests --
a fourth attempt that converted, and `items_seen` actually present -- exist
because a tool that only ever declines is also useless, and because neither
branch has ever run against real data: exp033 reached three attempts at most
and carried `items_seen` zero times.

One more is checked and it is not statistical. The registered null (36.7%,
eleven of exp034's thirty statements under 2,000 characters) belongs to a
specific population. Handed a different one, the analyzer must say so rather
than silently comparing against a null that was never about these tasks.

What none of this tests: whether any deliverable is any good. Success here
means the pipeline produced one. Grading is a separate run with a separate
cost and the analyzer never adds the two together.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import analyze_codex_run as analyzer  # noqa: E402


def build(root: Path, spec: list[tuple]) -> Path:
    """Write a minimal artifact.

    ``spec`` rows are ``(task_id, status, category, attempts, chars,
    items_seen)``. ``chars`` of 0 means the task carried no statement, which is
    the artifact-is-partly-unreadable case; ``items_seen`` of ``None`` means
    the key is absent rather than zero, which is how every run before the
    producer landed looks.

    ``items_seen`` is written where the pipeline writes it -- under
    ``observability.codex``, which is where ``_bounded_codex_diagnostics``
    puts it in ``step2_run_inference.py`` -- and not at the result's top
    level. A fixture that invents its own layout tests the fixture: this one
    said ``result["items_seen"]``, the analyzer read the same wrong place,
    and the pair agreed with each other while both disagreed with every real
    artifact. The measurement the run was dispatched to take would have been
    reported as never taken, and this suite would have stayed green.

    A row may carry a seventh element, the HTTP status the turn was refused
    with. Rows without one are unchanged, because a status is a thing most
    outcomes do not have. An eighth element is ``rate_limit_kind``; rows
    without one are how every run made before that field existed looks, which
    is every run this project has so far.
    """
    workspace = root / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)

    tasks, results, ledger = [], [], []
    for row in spec:
        task_id, status, category, attempts, chars, items_seen = row[:6]
        http_status = row[6] if len(row) > 6 else None
        rate_limit_kind = row[7] if len(row) > 7 else None
        task = {"task_id": task_id, "sector": "Finance"}
        if chars:
            task["instruction"] = "x" * chars
        tasks.append(task)

        result = {
            "task_id": task_id,
            "status": status,
            "observability": {"error_category": category},
            "problem_solving_cost": {"status": "partial", "known_cost_usd": None},
            "latency_ms": 1000,
        }
        if items_seen is not None:
            codex = {"items_seen": items_seen}
            if http_status is not None:
                codex["http_status_code"] = http_status
            if rate_limit_kind is not None:
                codex["rate_limit_kind"] = rate_limit_kind
            result["observability"]["codex"] = codex
        results.append(result)

        for index in range(attempts):
            ledger.append(
                {
                    "task_id": task_id,
                    "call_id": f"{task_id}-{index}",
                    "stage": "generation",
                    "state": "settled",
                    "retry_kind": "none" if index == 0 else "infrastructure",
                    "resolved_model": "gpt-5.4",
                    "model_cost_usd": None,
                    "missing_reasons": ["call_reachability_unknown"],
                }
            )

    (workspace / "step1_tasks_prepared.json").write_text(
        json.dumps({"tasks": tasks}), encoding="utf-8"
    )
    (workspace / "step2_inference_results.json").write_text(
        json.dumps(
            {
                "experiment_id": "fixture",
                "run_id": "FIXTURE",
                "model": "gpt-5.4",
                "execution_mode": "codex_foundry",
                "resume_rounds_used": 0,
                "results": results,
            }
        ),
        encoding="utf-8",
    )
    with (workspace / "cost_ledger_condition_a.jsonl").open("w", encoding="utf-8") as fh:
        for row in ledger:
            fh.write(json.dumps(row) + "\n")
    return root


def run(root: Path, capsys) -> str:
    analyzer.report(analyzer.collect(root))
    return capsys.readouterr().out


# --- declining, not answering -------------------------------------------


def test_a_run_with_no_failures_does_not_call_it_no_tasks(tmp_path, capsys):
    """Zero failures is a denominator of failures, not of tasks.

    Two tasks exist and both succeeded. "no tasks" would be a false statement
    about a set that is plainly non-empty, and the reader would reasonably
    conclude the artifact was broken.
    """
    build(tmp_path, [
        ("eeee5555", "success", None, 1, 900, 7),
        ("ffff6666", "success", None, 1, 3000, 9),
    ])
    out = run(tmp_path, capsys)
    assert "failures short  : no failures" in out
    assert "failures short  : no tasks" not in out


def test_an_empty_bucket_names_the_bucket_instead_of_reporting_zero(tmp_path, capsys):
    """No short tasks at all must not read as "short tasks never failed"."""
    build(tmp_path, [
        ("gggg7777", "error", "turn_failed", 2, 4000, None),
        ("hhhh8888", "success", None, 1, 5000, None),
    ])
    out = run(tmp_path, capsys)
    assert "failure rate short : no short tasks" in out
    assert "failure rate short : 0/0" not in out


def test_tasks_without_a_statement_are_named_not_silently_dropped(tmp_path, capsys):
    """A shrinking denominator has to announce itself.

    Two of four tasks carry no statement. Excluding them is correct -- their
    length is unknown, so they cannot be sorted into short or long -- but
    excluding them *quietly* turns a half-readable artifact into a confident
    2-of-2 result.
    """
    build(tmp_path, [
        ("aaaa1111", "success", None, 1, 900, 1),
        ("bbbb2222", "error", "turn_failed", 2, 3000, 1),
        ("cccc3333", "error", "turn_failed", 2, 0, 1),
        ("dddd4444", "success", None, 1, 0, 1),
    ])
    out = run(tmp_path, capsys)
    assert "NOT TESTED" in out
    assert "2/4 tasks carried no statement" in out
    assert "cccc3333" in out and "dddd4444" in out


def test_items_seen_absent_is_declined_rather_than_read_as_zero(tmp_path, capsys):
    """Every run before the producer landed looks exactly like this."""
    build(tmp_path, [
        ("gggg7777", "error", "turn_failed", 2, 4000, None),
        ("hhhh8888", "success", None, 1, 5000, None),
    ])
    out = run(tmp_path, capsys)
    assert "Not a measurement of zero" in out


def test_no_fourth_attempt_declines_instead_of_reporting_no_benefit(tmp_path, capsys):
    """An unexercised budget is not a budget that bought nothing.

    Those are different findings and only one of them justifies dropping the
    extra attempt in the next stage.
    """
    build(tmp_path, [
        ("eeee5555", "success", None, 1, 900, 7),
        ("ffff6666", "success", None, 1, 3000, 9),
    ])
    out = run(tmp_path, capsys)
    assert "does not answer the question either way" in out


# --- the registered population ------------------------------------------


def test_a_different_population_says_the_registered_null_is_not_its_null(tmp_path, capsys):
    """exp033's five tasks are 3 short of 5 -- 60%, not 36.7%.

    Comparing them against a null computed from exp034's thirty would be
    comparing against a number that was never about them.
    """
    build(tmp_path, [
        ("02aa1805", "error", "turn_failed", 2, 1589, None),
        ("0112fc9b", "success", None, 1, 2902, None),
        ("2ea2e5b5", "success", None, 1, 3632, None),
        ("3baa0009", "error", "turn_failed", 2, 996, None),
        ("0818571f", "error", "rate_limited", 3, 1548, None),
    ])
    out = run(tmp_path, capsys)
    assert "short tasks     : 3/5 = 60.0%" in out
    assert "not the population that prediction was written for" in out


def test_the_registered_population_raises_no_such_note(tmp_path, capsys):
    """Eleven short of thirty is 36.7%, which is the registered figure."""
    spec = []
    for index in range(11):
        spec.append((f"short{index:03d}", "error", "turn_failed", 2, 1500, 3))
    for index in range(19):
        spec.append((f"long{index:03d}", "success", None, 1, 2500, 3))
    build(tmp_path, spec)
    out = run(tmp_path, capsys)
    assert "short tasks     : 11/30 = 36.7%" in out
    assert "not the population that prediction was written for" not in out


# --- the two branches no real run has ever taken -------------------------


def test_a_fourth_attempt_that_converted_is_reported_as_such(tmp_path, capsys):
    """exp033 reached three attempts at most, so this path is unproven.

    exp034 raises `max_retries` to 3, which permits a fourth attempt. If one
    converts a task the first three did not, that is the finding that keeps
    the extra budget; the analyzer has to be able to see it.
    """
    build(tmp_path, [
        ("aaaa1111", "success", None, 4, 900, 12),
        ("bbbb2222", "error", "turn_failed", 4, 1200, 3),
        ("cccc3333", "success", None, 1, 3000, 41),
    ])
    out = run(tmp_path, capsys)
    assert "reached 4+ attempts : 2" in out
    assert "aaaa1111  attempts=4  -> success" in out
    assert "converted           : 1/2 = 50.0%" in out


def test_items_seen_present_is_measured(tmp_path, capsys):
    """The first run dispatched after the producer landed is the first reading.

    A value of zero on one task is a real zero and must be counted, not
    mistaken for the key being absent.
    """
    build(tmp_path, [
        ("aaaa1111", "success", None, 1, 900, 12),
        ("dddd4444", "error", "rate_limited", 3, 1500, 0),
    ])
    out = run(tmp_path, capsys)
    assert "carried on 2/2 tasks" in out
    assert "min 0" in out
    assert "Not a measurement of zero" not in out


def test_a_turn_that_never_started_is_not_a_count_of_zero(tmp_path, capsys):
    """The four pre-stream failures return ``items_seen`` at its default.

    ``core/codex_runner.py`` builds ``codex_diagnostics`` from the outcome
    unconditionally, so a task that died before the stream opened still
    arrives carrying ``items_seen: 0`` -- a field nobody set, indistinguishable
    in the JSON from a turn that opened and streamed nothing.

    Counting those zeros would answer the registered question with a dataclass
    default, and would do it in the direction that flatters the convenient
    reading: a median dragged toward zero is evidence that a turn is refused
    before it spends anything, which is exactly the claim this field exists to
    test rather than to assume.
    """
    build(tmp_path, [
        ("aaaa1111", "success", None, 1, 900, 40),
        ("bbbb2222", "error", "session_start_failed", 2, 1200, 0),
        ("cccc3333", "error", "runtime_unavailable", 1, 1500, 0),
    ])
    out = run(tmp_path, capsys)
    assert "NOT MEASURED    : 2/3 tasks failed before the turn started" in out
    assert "session_start_failed" in out
    assert "runtime_unavailable" in out
    # One task measured, and its 40 is not averaged against two unset zeros.
    assert "carried on 1/3 tasks" in out
    assert "min 40  max 40" in out


def test_where_a_refusal_lands_in_the_turn_is_reported_beside_the_count(
    tmp_path, capsys
):
    """The cross-tab priority 1 actually turns on.

    A 429 says the provider refused. How far the turn got before being
    refused is the part that distinguishes "this turn consumed too much" from
    "something was decided before this turn spent anything". The analyzer
    prints both numbers together and declines to name the limit from them,
    because a table of item counts cannot settle that on its own.
    """
    build(tmp_path, [
        ("aaaa1111", "success", None, 1, 900, 37),
        ("dddd4444", "error", "rate_limited", 3, 1500, 0, 429),
        ("eeee5555", "error", "rate_limited", 2, 2400, 22, 429),
    ])
    out = run(tmp_path, capsys)
    assert "refused for rate : 2" in out
    assert "dddd4444  items_seen=0" in out
    assert "eeee5555  items_seen=22" in out
    assert "refused before any item : 1/2 = 50.0%" in out


def test_a_refusal_that_recorded_no_status_is_still_a_refusal(tmp_path, capsys):
    """exp034's actual shape, and the one this section used to print as none.

    Selecting on ``http_status_code == 429`` alone was true and useless: all
    eight of exp034's failures carried ``items_seen`` and nothing else, so its
    five rate refusals were reported as "no task carried HTTP 429" -- a
    sentence nobody reads as "five tasks were refused for rate". The category
    is the other way in, and it is the way that works on every run so far.
    """
    build(tmp_path, [
        ("aaaa1111", "success", None, 1, 900, 37),
        ("dddd4444", "error", "rate_limited", 4, 1500, 30),
        ("eeee5555", "error", "rate_limited", 4, 2400, 42),
    ])
    out = run(tmp_path, capsys)
    assert "refused for rate : 2" in out
    assert "dddd4444  items_seen=30" in out
    assert "status=-" in out  # the status it does not have, said as absent
    assert "no task was refused for rate" not in out


def test_a_refusal_with_no_measured_count_is_listed_apart_not_dropped(
    tmp_path, capsys
):
    """Its position in the turn is the one thing it cannot report.

    Dropping it would undercount the refusals; folding its unset zero into the
    rest would answer "was it refused before spending anything?" with a
    dataclass default, in the direction that flatters the convenient reading.
    It is counted as a refusal and excluded from the position figure.
    """
    build(tmp_path, [
        ("aaaa1111", "success", None, 1, 900, 37),
        ("dddd4444", "error", "rate_limited", 3, 1500, 12, 429),
        ("ffff6666", "error", "rate_limited", 2, 2400, None, 429),
    ])
    out = run(tmp_path, capsys)
    assert "refused for rate : 2" in out
    assert "ffff6666  items_seen=NOT MEASURED" in out
    # One refusal has a count; the unmeasured one is not a zero in it.
    assert "refused before any item : 0/1 = 0.0%" in out


def test_which_of_the_two_limits_refused_is_named_when_the_run_recorded_it(
    tmp_path, capsys
):
    """``token`` and ``request`` have opposite fixes, so the count matters."""
    build(tmp_path, [
        ("aaaa1111", "success", None, 1, 900, 37),
        ("dddd4444", "error", "rate_limited", 3, 1500, 12, 429, "token"),
        ("eeee5555", "error", "rate_limited", 2, 2400, 30, 429, "token"),
        ("ffff6666", "error", "rate_limited", 2, 2400, 4, 429, "request"),
    ])
    out = run(tmp_path, capsys)
    assert "which limit : {'token': 2, 'request': 1}" in out
    # Narrowly worded: the cost section says UNDETERMINED about dollars, for
    # unrelated reasons, and a bare substring check passes on that instead.
    assert "which limit : UNDETERMINED" not in out


@pytest.mark.parametrize("kind", [None, "unattributed"])
def test_a_run_that_cannot_say_which_limit_says_that_rather_than_neither(
    tmp_path, capsys, kind
):
    """Absent and unattributed both mean undetermined, for different reasons.

    A run predating ``rate_limit_kind`` records nothing; ``unattributed`` means
    the refusal's wording escaped the markers in ``core/codex_runner.py``. Both
    must print as UNDETERMINED rather than as an empty breakdown, which reads
    as "neither limit was reached" -- the one thing that is certainly false
    about a task that was refused for rate.
    """
    build(tmp_path, [
        ("aaaa1111", "success", None, 1, 900, 37),
        ("dddd4444", "error", "rate_limited", 3, 1500, 12, 429, kind),
    ])
    out = run(tmp_path, capsys)
    assert "which limit : UNDETERMINED for 1 of 1" in out
    assert "Not evidence for either limit" in out
    assert "'token'" not in out


def test_a_run_with_no_refusals_says_so_rather_than_printing_an_empty_table(
    tmp_path, capsys
):
    """No refusal is a result. It must not read as a table that failed to print."""
    build(tmp_path, [
        ("aaaa1111", "success", None, 1, 900, 37),
        ("bbbb2222", "error", "turn_failed", 2, 1500, 9, 500),
    ])
    out = run(tmp_path, capsys)
    assert "no task was refused for rate" in out
    assert "statuses seen: 500" in out
    assert "refused before any item" not in out


# --- cost ----------------------------------------------------------------


def test_unknown_dollars_stay_undetermined_and_never_become_zero(tmp_path, capsys):
    """This deployment is absent from the price table, so USD is unknown.

    Every ledger row here carries `call_reachability_unknown`. The run's cost
    is undetermined; printing `0` would be a claim nobody measured.
    """
    build(tmp_path, [
        ("aaaa1111", "success", None, 1, 900, 12),
        ("dddd4444", "error", "rate_limited", 3, 1500, 0),
    ])
    out = run(tmp_path, capsys)
    assert "UNDETERMINED, which is not zero" in out
    assert "call_reachability_unknown" in out
    assert "model cost USD" not in out


def test_the_cost_section_says_grading_is_not_included(tmp_path, capsys):
    """Solving cost and grading cost are separate runs and separate money."""
    build(tmp_path, [("aaaa1111", "success", None, 1, 900, 12)])
    out = run(tmp_path, capsys)
    assert "task-solving only; grading is a separate run" in out


# --- the reader itself ---------------------------------------------------


def test_a_missing_results_file_fails_loudly(tmp_path):
    """An empty directory must not analyse as a run of zero tasks."""
    (tmp_path / "workspace").mkdir()
    with pytest.raises(SystemExit):
        analyzer.collect(tmp_path)


def test_the_statement_field_this_dataset_uses_is_the_one_read(tmp_path, capsys):
    """`instruction` is the key, and the figures registered came from it.

    A later revision renaming the field should degrade to "cannot test", not
    to a silent zero, which is why `_statement_of` tries alternatives and
    returns "" rather than raising.
    """
    assert analyzer._statement_of({"instruction": "abc"}) == "abc"
    assert analyzer._statement_of({"prompt": "abc"}) == "abc"
    assert analyzer._statement_of({"unrelated": "abc"}) == ""

    build(tmp_path, [("aaaa1111", "success", None, 1, 0, 1)])
    out = run(tmp_path, capsys)
    assert "cannot test" in out
