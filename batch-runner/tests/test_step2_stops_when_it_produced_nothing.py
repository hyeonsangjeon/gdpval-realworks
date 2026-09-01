"""Step 2 stops when the run produced nothing, instead of leaving it to Step 4.

The five-task advance check on the Azure code-interpreter route failed on all
five tasks. Every row came back the same way::

    status="error"  deliverable_text=""  deliverable_files=[]
    error="task_execution_error:PermissionDeniedError"

Step 2 printed ``Success: 0/5``, wrote its files and **returned 0**. The
workflow read that as a pass, ran Step 3, and died in Step 4::

    ⚠️  Nothing was filled

So the run failed two steps away from the thing that broke, on a line that
names neither the tasks nor the refusal. Anyone reading the job summary sees a
parquet complaint and has to walk backwards to find five 403s.

**What makes this narrow.** The obvious guard — "fail if any task failed" — is
wrong here, and the same advance check proves it. On the host run two of five
tasks ended ``error`` and still wrote 1,981 and 2,145 characters of
deliverable text, because the model answered and only its *generated code*
blew up afterwards. Step 4 fills those rows and carries on; it counts a row as
filled on text or files and never consults ``status``. A status-based guard
would reject work the pipeline accepts today.

So the guard is not about failure. It is about emptiness: every row carrying
no text and no files. That is exactly the set Step 4 already rejects, moved
back to where the error strings still exist. ``test_the_guard_and_step_4_agree
_on_what_empty_means`` holds the two definitions together by running the real
``fill_parquet`` over the same rows.

**Including where that spelling is odd.** ``fill_parquet`` tests plain
truthiness, so ``"   "`` counts as a filled deliverable. The guard copies that
rather than correcting it. Correcting it here would make Step 2 stricter than
Step 4 and could stop a run the pipeline completes today — the one failure
mode this change must not introduce. Whether a whitespace-only deliverable
should count at all is a question for ``fill_parquet``, on its own change.

**Why exit 1 and not 42.** ``batch-run.yml`` runs Step 2a under
``continue-on-error``, hands the exit code to ``scripts/relay_checkpoint.py``,
and only 42 means "checkpoint saved, relay me". Anything else falls through to
``Verify Step 2a success``, which fails the job. An empty run is not a relay —
it has nothing pending and nothing to resume — so it must not borrow that code.

Nothing here calls a model, signs in, or spends anything. The parquet is three
rows built in a temp directory.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pandas as pd
import pytest

from core.inference_manifest import STEP2_PROGRESS_SCHEMA
from fill_parquet import fill_parquet
from scripts import relay_checkpoint as relay
from step2_run_inference import EXIT_CHECKPOINT, _nothing_to_submit_report

STEP2 = Path(__file__).resolve().parents[1] / "step2_run_inference.py"

# Terminal rows in a Step 2 checkpoint must carry all of these, or
# ``core.inference_manifest.validate_step2_progress_results`` refuses the file
# before the exit code is ever considered.
CHECKPOINT_FIELDS = {
    "content": None,
    "model": "test-model",
    "usage": None,
    "observability": {},
    "latency_ms": 1.0,
    "timestamp": "2026-08-30T00:00:00+00:00",
}

# The five rows the Azure code-interpreter advance check actually recorded
# (run 33468138329). Task IDs shortened to their published prefixes; nothing
# else is altered.
REFUSED_RUN = [
    {
        "task_id": task_id,
        "status": "error",
        "deliverable_text": "",
        "deliverable_files": [],
        "error": "task_execution_error:PermissionDeniedError",
    }
    for task_id in ("02aa1805", "0112fc9b", "2ea2e5b5", "3baa0009", "0818571f")
]

# The host run's two failures from the same advance check (run 33463492420).
# Both ended `error` and both left deliverable text behind.
ERRORED_BUT_ANSWERED = [
    {
        "task_id": "02aa1805",
        "status": "error",
        "deliverable_text": "x" * 1981,
        "deliverable_files": [],
        "error": "task_execution_error:ValueError",
    },
    {
        "task_id": "0818571f",
        "status": "error",
        "deliverable_text": "y" * 2145,
        "deliverable_files": [],
        "error": "task_execution_error:ValueError",
    },
]


@pytest.fixture(scope="module")
def step2_source() -> ast.Module:
    return ast.parse(STEP2.read_text(encoding="utf-8"))


def _top_level_function(source: ast.Module, name: str) -> ast.FunctionDef:
    for node in source.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"{name} is no longer a top-level function")


@pytest.fixture(scope="module")
def run_inference_body(step2_source) -> list[ast.stmt]:
    """The top-level statements of ``_run_inference_impl``, as syntax.

    ``run_inference`` itself is a twenty-line wrapper that opens
    ``_Step2RuntimeResources`` and delegates; the run lives in
    ``_run_inference_impl``, and that is where the guard has to sit.
    ``test_the_wrapper_lets_the_guard_out`` holds the two together.

    Parsed rather than grepped so the ordering assertions survive reformatting
    and rewritten comments, and fail only when the *placement* changes — which
    is the thing being held still.
    """
    return _top_level_function(step2_source, "_run_inference_impl").body


def _calls_named(node: ast.AST, name: str) -> list[ast.Call]:
    """Every call to *name*, whether plain or reached through an attribute."""
    found = []
    for inner in ast.walk(node):
        if not isinstance(inner, ast.Call):
            continue
        func = inner.func
        if isinstance(func, ast.Name) and func.id == name:
            found.append(inner)
        elif isinstance(func, ast.Attribute) and func.attr == name:
            found.append(inner)
    return found


def _calls_anywhere(body: list[ast.stmt], name: str) -> list[ast.Call]:
    """The same, across a whole list of statements."""
    return [call for statement in body for call in _calls_named(statement, name)]


def _reads_name(node: ast.AST, name: str) -> bool:
    return any(
        isinstance(inner, ast.Name) and inner.id == name for inner in ast.walk(node)
    )


# ── What the guard decides ────────────────────────────────────────────────


def test_the_refused_run_is_reported():
    report = _nothing_to_submit_report(REFUSED_RUN)

    assert report is not None
    text = "\n".join(report)
    assert "5 task(s) ran" in text
    # One line for the one reason, carrying its count — not five repetitions.
    assert "5× task_execution_error:PermissionDeniedError" in text
    assert text.count("task_execution_error:PermissionDeniedError") == 1


def test_a_failed_task_that_still_answered_is_not_reported():
    """The host run's shape. Every row failed; Step 4 fills both of them."""
    assert _nothing_to_submit_report(ERRORED_BUT_ANSWERED) is None


def test_one_survivor_among_refusals_is_enough():
    survivor = dict(REFUSED_RUN[0], deliverable_text="a plan, of sorts")
    assert _nothing_to_submit_report([survivor, *REFUSED_RUN[1:]]) is None


def test_a_file_with_no_text_is_enough():
    """Not every deliverable is prose. A spreadsheet with no summary counts."""
    survivor = dict(REFUSED_RUN[0], deliverable_files=["deliverable_files/t/a.xlsx"])
    assert _nothing_to_submit_report([survivor, *REFUSED_RUN[1:]]) is None


def test_whitespace_counts_because_step_4_counts_it():
    """The guard copies Step 4's spelling of "empty", including where it is odd.

    ``fill_parquet`` tests ``r.get("deliverable_text") or ""`` for truth, so
    ``"   "`` is a filled row to it. The guard therefore lets it through. It
    would be easy to call that a bug and strip here — but stripping would make
    Step 2 stricter than Step 4 and could stop a run this pipeline completes,
    which is the one thing this change must not do. The fix, if there is one,
    belongs in ``fill_parquet``.

    ``test_step_4_fills_the_whitespace_run_too`` checks the other half of that
    claim against the real function.
    """
    blank = [dict(row, deliverable_text="   \n\t ") for row in REFUSED_RUN]
    assert _nothing_to_submit_report(blank) is None


def test_an_empty_result_set_is_not_this_failure():
    """No rows at all is a different bug, caught upstream by the task-set check."""
    assert _nothing_to_submit_report([]) is None


def test_quality_failures_are_reported_too_when_they_left_nothing():
    """``qa_failed`` is not exempt — the question is what came back, not why.

    A run whose every answer was rejected by Self-QA and which wrote nothing
    is as unsubmittable as a run of refusals, and Step 4 rejects it for the
    same reason.
    """
    rejected = [
        dict(row, status="qa_failed", error="qa_failed:missing_deliverable")
        for row in REFUSED_RUN
    ]
    report = _nothing_to_submit_report(rejected)

    assert report is not None
    assert "5× qa_failed:missing_deliverable" in "\n".join(report)


def test_a_row_with_no_error_recorded_still_names_its_status():
    """Silence is a finding. The report must not print a bare blank line."""
    silent = [dict(row, error=None) for row in REFUSED_RUN]
    report = _nothing_to_submit_report(silent)

    assert report is not None
    assert "5× no error recorded (status: error)" in "\n".join(report)


def test_mixed_reasons_are_counted_and_ordered_by_weight():
    mixed = [
        dict(REFUSED_RUN[0], error="task_execution_error:PermissionDeniedError"),
        dict(REFUSED_RUN[1], error="task_execution_error:PermissionDeniedError"),
        dict(REFUSED_RUN[2], error="task_execution_error:PermissionDeniedError"),
        dict(REFUSED_RUN[3], error="task_execution_error:APITimeoutError"),
        dict(REFUSED_RUN[4], error="task_execution_error:APITimeoutError"),
    ]
    report = _nothing_to_submit_report(mixed)

    assert report is not None
    counted = [line.strip() for line in report if line.strip().startswith(("3×", "2×"))]
    assert counted == [
        "3× task_execution_error:PermissionDeniedError",
        "2× task_execution_error:APITimeoutError",
    ]


def test_the_report_adds_nothing_the_rows_did_not_carry():
    """The error strings are already public.

    ``_public_persisted_results`` collapses every error to
    ``task_execution_error:<ClassName>`` before this point, so reprinting them
    exposes nothing new. What the report must not do is reach past ``error``
    into the rest of the row — a prompt, a traceback, a path — and print that.
    """
    row = dict(
        REFUSED_RUN[0],
        prompt="the full task prompt, reference files and all",
        raw_response={"endpoint": "https://private.example/openai/v1"},
        traceback="File \"/home/runner/work/secret/path.py\", line 1",
    )
    report = _nothing_to_submit_report([row, *REFUSED_RUN[1:]])

    assert report is not None
    text = "\n".join(report)
    for leaked in ("prompt", "private.example", "/home/runner", "traceback"):
        assert leaked not in text


# ── That the guard and Step 4 mean the same thing by "empty" ──────────────


def _tiny_parquet(tmp_path: Path, task_ids: list[str]) -> Path:
    path = tmp_path / "source.parquet"
    pd.DataFrame({"task_id": task_ids, "sector": ["x"] * len(task_ids)}).to_parquet(
        path, index=False
    )
    return path


def _results_json(tmp_path: Path, results: list[dict]) -> Path:
    path = tmp_path / "results.json"
    path.write_text(
        json.dumps({"experiment_id": "exp032", "results": results}),
        encoding="utf-8",
    )
    return path


def test_the_guard_and_step_4_agree_on_what_empty_means(tmp_path):
    """Everything the guard reports on, Step 4 would have rejected anyway.

    This is the coupling that keeps the guard from being a second, stricter
    opinion. It runs the real ``fill_parquet`` — the same function Step 4
    calls — and checks that it filled nothing, which is what makes its
    ``main()`` return 1.
    """
    assert _nothing_to_submit_report(REFUSED_RUN) is not None

    stats = fill_parquet(
        parquet_path=str(
            _tiny_parquet(tmp_path, [r["task_id"] for r in REFUSED_RUN])
        ),
        json_path=str(_results_json(tmp_path, REFUSED_RUN)),
        overwrite_existing=True,
        dry_run=True,
    )

    assert stats["filled_text"] == 0
    assert stats["filled_files"] == 0


def test_step_4_fills_the_whitespace_run_too(tmp_path):
    """The other half of ``test_whitespace_counts_because_step_4_counts_it``.

    Five rows of ``"   "`` are five filled rows to ``fill_parquet``. Had the
    guard stripped, it would have stopped a run that Step 4 carries through —
    the exact over-reach this test exists to catch, should someone add the
    ``.strip()`` back.
    """
    blank = [dict(row, deliverable_text="   \n\t ") for row in REFUSED_RUN]

    stats = fill_parquet(
        parquet_path=str(_tiny_parquet(tmp_path, [r["task_id"] for r in blank])),
        json_path=str(_results_json(tmp_path, blank)),
        overwrite_existing=True,
        dry_run=True,
    )

    assert stats["filled_text"] == 5
    assert _nothing_to_submit_report(blank) is None


def test_step_4_accepts_the_run_the_guard_lets_through(tmp_path):
    """The other direction, and the reason the guard is not status-based.

    Both rows failed. Both still reach the parquet. A guard that fired here
    would reject a run this pipeline completes today.
    """
    assert _nothing_to_submit_report(ERRORED_BUT_ANSWERED) is None

    stats = fill_parquet(
        parquet_path=str(
            _tiny_parquet(tmp_path, [r["task_id"] for r in ERRORED_BUT_ANSWERED])
        ),
        json_path=str(_results_json(tmp_path, ERRORED_BUT_ANSWERED)),
        overwrite_existing=True,
        dry_run=True,
    )

    assert stats["filled_text"] == 2
    assert stats["errors_with_text"] == 2


# ── Where the guard sits, and what it exits with ─────────────────────────


def test_the_guard_runs_after_every_artifact_is_written(run_inference_body):
    """The evidence has to survive the failure.

    A run that stops before writing loses the results file, the cost ledger
    and the receipts — the only record of what was attempted and what it cost.
    So the guard is placed after all of them, and reads the same ``results``
    list they were built from.
    """
    guards = [
        node
        for node in run_inference_body
        if _calls_named(node, "_nothing_to_submit_report")
    ]
    assert len(guards) == 1, "the guard should be reached exactly once"

    results_written = _calls_anywhere(run_inference_body, "dump")
    ledger_exported = _calls_anywhere(run_inference_body, "export_jsonl")
    assert results_written and ledger_exported

    guard_line = guards[0].lineno
    assert guard_line > max(call.lineno for call in results_written)
    assert guard_line > max(call.lineno for call in ledger_exported)


def test_the_guard_exits_1_and_never_borrows_the_relay_code(run_inference_body):
    """42 means "checkpoint saved, relay me". An empty run has nothing to resume."""
    guarded = [
        node
        for node in run_inference_body
        if isinstance(node, ast.If) and _reads_name(node.test, "empty_run_report")
    ]
    assert len(guarded) == 1

    exits = _calls_named(guarded[0], "exit")
    assert len(exits) == 1
    (code,) = exits[0].args
    assert isinstance(code, ast.Constant)
    assert code.value == 1
    assert code.value != EXIT_CHECKPOINT


def test_the_wrapper_lets_the_guard_out(step2_source):
    """``sys.exit`` has to survive the layer between the guard and the process.

    ``run_inference`` is what ``main`` calls; it opens
    ``_Step2RuntimeResources`` and delegates to ``_run_inference_impl``. A
    context manager whose ``__exit__`` returned true would swallow the
    ``SystemExit`` and hand back a zero — the very bug being fixed, restored
    one layer up and much harder to see. So: the wrapper really does delegate,
    and the manager really does not suppress.
    """
    wrapper = _top_level_function(step2_source, "run_inference")
    assert _calls_named(wrapper, "_run_inference_impl"), (
        "run_inference should still delegate to the function holding the guard"
    )

    resources = next(
        node
        for node in step2_source.body
        if isinstance(node, ast.ClassDef) and node.name == "_Step2RuntimeResources"
    )
    dunder_exit = next(
        node
        for node in resources.body
        if isinstance(node, ast.FunctionDef) and node.name == "__exit__"
    )

    # A bare `return`, or none at all, yields None — falsy — and the exception
    # propagates. Anything returned with a value is the thing to catch here.
    returned = [
        node
        for node in ast.walk(dunder_exit)
        if isinstance(node, ast.Return) and node.value is not None
    ]
    assert not returned, "__exit__ must not return a value; a true one hides SystemExit"


def test_exit_1_is_not_read_as_a_relay(tmp_path):
    """The workflow's own reader, asked about the code the guard uses.

    ``batch-run.yml`` gives Step 2a's exit code to ``relay_checkpoint status``
    and relays only when it says so. This checks the answer for 1 against a
    progress file shaped like the refused run — every task finished, nothing
    pending — which is what the guard leaves behind.
    """
    task_ids = [row["task_id"] for row in REFUSED_RUN]
    progress = tmp_path / "progress.json"
    progress.write_text(
        json.dumps(
            {
                "schema_version": STEP2_PROGRESS_SCHEMA,
                "ordered_task_ids": task_ids,
                "total_tasks": len(task_ids),
                "results": [dict(CHECKPOINT_FIELDS, **row) for row in REFUSED_RUN],
            }
        ),
        encoding="utf-8",
    )

    pending_count, needs_relay = relay.resolve_relay_status(progress, "1")

    assert pending_count == 0
    assert needs_relay is False
