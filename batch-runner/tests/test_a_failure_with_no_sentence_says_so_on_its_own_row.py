"""A failure with no provider sentence must say so on its own row.

The checkpoint records ``error: "task_execution_error:TaskExecutionError"`` for
every failure alike. The sentence that says *why* -- the rate-limit refusal
naming the deployment, the transport error, the content stop -- exists only in
the job log. A row without one is an unexplained failure, and the record has a
field for saying that: ``message_source: "not_available"``.

It used to be set from the wrong thing. The flag went on when **no log at all**
was passed, which is correct for a single-leg run and wrong for every relayed
one. A leg writes only the tasks it ran, so a lineage's sentences are spread
across its legs' logs; hand the builder one leg's log and the tasks it
inherited come out with ``message: ""`` and nothing saying the record cannot
explain them. Run 34631861765's record was built that way once: 15 of its 28
failures silently blank, indistinguishable from a failure the provider had
nothing to say about.

So the flag belongs on the row, keyed off whether *that row* has a sentence,
and ``--log`` has to be repeatable for the rows to be fillable at all. Both
halves are pinned here, because either one alone leaves the gap: a repeatable
flag nobody passes twice still needs to admit what it is missing, and an honest
flag on an unfillable row is a permanent gap in a record that could be complete.

Nothing here contacts a provider.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from core.cost_receipts import (
    CallUsage,
    CostReceiptLedger,
    load_receipt_price_table,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from build_partial_run_record import build  # noqa: E402

MODEL = "gpt-5.4"

#: Task ids must be uuid-shaped: the log parser finds a task by matching one.
EARLIER_FAIL = "11111111-1111-4111-8111-111111111111"
OWN_FAIL = "22222222-2222-4222-8222-222222222222"
OWN_OK = "33333333-3333-4333-8333-333333333333"

#: Two different sentences, so a test that passes cannot be passing because one
#: log happened to explain everything.
EARLIER_SENTENCE = (
    "rate_limited, Your requests to gpt-5.4 for gpt-5.4 in eastus2 "
    "have exceeded rate limit., mem=1234MB"
)
OWN_SENTENCE = "transport_error, peer closed connection, mem=1234MB"


def _log(path: Path, entries: list[tuple[int, str, str]]) -> Path:
    """A job log in the shape the builder parses: a header, then an outcome."""
    lines = []
    for n, task_id, sentence in entries:
        lines.append(f"  [{n}/3] {task_id}  Sector / Occupation")
        lines.append(f"    ✗ {sentence}" if sentence else "    ✓ (1234ms, mem=1234MB)")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


@pytest.fixture()
def relay(tmp_path: Path) -> tuple[Path, Path, Path]:
    """A resumed leg, plus one log per leg -- each covering only its own tasks."""
    artifact = tmp_path / "batch-results-2"
    workspace = artifact / "workspace"
    workspace.mkdir(parents=True)

    ledger = CostReceiptLedger(
        workspace / "cost_ledger_condition_a.sqlite3",
        run_id="leg2",
        price_table=load_receipt_price_table(),
    )
    ledger.reserve(
        call_id="c1",
        task_id=OWN_FAIL,
        stage="generation",
        retry_kind="none",
        provider="azure",
        requested_model=MODEL,
        deployment=MODEL,
        api_version="v1",
        note="one Codex turn",
    )
    ledger.settle(
        call_id="c1",
        resolved_model=MODEL,
        usage=CallUsage(
            input_tokens=50_000,
            cached_input_tokens=0,
            output_tokens=2_000,
            reasoning_tokens=0,
            audio_input_tokens=0,
            audio_output_tokens=0,
        ),
        extra_reasons=["call_reachability_unknown"],
    )

    (workspace / "step1_tasks_prepared.json").write_text(
        json.dumps(
            {
                "tasks": [
                    {"task_id": t, "sector": "Sector", "occupation": "Occupation"}
                    for t in (EARLIER_FAIL, OWN_FAIL, OWN_OK)
                ]
            }
        ),
        encoding="utf-8",
    )
    (workspace / "step2_inference_progress_condition_a.json").write_text(
        json.dumps(
            {
                "ordered_task_ids": [EARLIER_FAIL, OWN_FAIL, OWN_OK],
                "results": [
                    {
                        "task_id": EARLIER_FAIL,
                        "status": "error",
                        "observability": {"error_category": "rate_limited"},
                    },
                    {
                        "task_id": OWN_FAIL,
                        "status": "error",
                        "observability": {"error_category": "transport_error"},
                    },
                    {"task_id": OWN_OK, "status": "success"},
                ],
            }
        ),
        encoding="utf-8",
    )

    earlier_log = _log(tmp_path / "leg1.log", [(1, EARLIER_FAIL, EARLIER_SENTENCE)])
    own_log = _log(
        tmp_path / "leg2.log", [(2, OWN_FAIL, OWN_SENTENCE), (3, OWN_OK, "")]
    )
    return artifact, earlier_log, own_log


def _by_task(rows: list[dict]) -> dict[str, dict]:
    return {row["task_id"]: row for row in rows}


def test_a_supplied_log_does_not_explain_the_rows_it_never_covered(relay) -> None:
    """The defect itself: one leg's log, and a failure it says nothing about.

    ``message: ""`` next to an unflagged row reads as "the provider gave no
    reason". The truth is that the reason is in a log this caller did not pass.
    """
    artifact, _, own_log = relay
    rows = _by_task(build(artifact, logs=[own_log])[0])

    inherited = rows[EARLIER_FAIL]
    assert inherited["message"] == ""
    assert inherited["message_source"] == "not_available", (
        "a failure no supplied log covers was left unflagged; a reader cannot "
        "tell it apart from a failure that genuinely had no message"
    )

    covered = rows[OWN_FAIL]
    assert covered["message"] == OWN_SENTENCE
    assert "message_source" not in covered


def test_every_legs_log_is_read_not_only_the_last(relay) -> None:
    """``--log`` is repeatable, and the sentences accumulate across legs."""
    artifact, earlier_log, own_log = relay
    rows = _by_task(build(artifact, logs=[earlier_log, own_log])[0])

    assert rows[EARLIER_FAIL]["message"] == EARLIER_SENTENCE
    assert rows[OWN_FAIL]["message"] == OWN_SENTENCE
    assert [row for row in rows.values() if "message_source" in row] == []


def test_with_no_log_at_all_every_failure_is_flagged(relay) -> None:
    """The case the old condition did handle must keep working."""
    artifact, _, _ = relay
    rows = _by_task(build(artifact)[0])
    flagged = {t for t, row in rows.items() if row.get("message_source")}
    assert flagged == {EARLIER_FAIL, OWN_FAIL}


def test_a_task_that_did_not_fail_is_never_flagged(relay) -> None:
    """The flag describes a missing failure sentence, so it needs a failure.

    Putting it on a success -- or on one of the 118 tasks a leg never reached --
    would turn "we cannot explain this failure" into noise on rows that have
    nothing to explain.
    """
    artifact, earlier_log, own_log = relay
    for logs in ([], [own_log], [earlier_log, own_log]):
        rows = _by_task(build(artifact, logs=logs)[0])
        assert "message_source" not in rows[OWN_OK]
        assert rows[OWN_OK]["outcome"] == "ok"
