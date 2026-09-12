"""Nothing read the ledger the paid run spent all that care writing.

Every paid V2 shard writes ``cost_receipts.sqlite3`` — one row per call,
written before the request goes out and updated when the reply comes back —
and the collect job downloads all of them. No code opened them. So the stage
that the goal asks for a **per-task cost** from had a complete account of its
spending and no reader, which is the same as having none at the moment someone
asks what task 17 cost.

``scripts/roll_up_agentic_v2_cost.py`` is that reader. These tests hold the
four things it would be easy to get wrong and expensive to notice:

* **A task that never ran is not a free task.** It settles ``not_run`` with a
  null amount, and a stage that finished a third of its cohort must not read
  as cheap.
* **Two shards are added up once.** A re-uploaded artifact, or a task retried
  in a second shard, must not bill the run twice — and two shards that
  disagree about the same call must refuse to produce a total rather than
  pick one.
* **The fingerprint comes from the rows, not from today's price file.** The
  merged ledger is opened with no price table on purpose. Rows carry the
  fingerprint of the table they were settled under; handing the merge today's
  file would stamp today's fingerprint on older money.
* **A floor is not a total.** Anything short of ``complete`` leaves
  ``estimated_cost_usd`` null and says out loud that ``known_cost_usd`` is a
  floor.

Nothing here calls a model or reaches the network. The ledgers are real and
sqlite-backed in a temporary directory; the calls are fabricated.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core.cost_receipts import (  # noqa: E402
    STAGE_GENERATION,
    CallUsage,
    CostReceiptLedger,
    load_receipt_price_table,
)

ROLLUP_PATH = BATCH_RUNNER_ROOT / "scripts" / "roll_up_agentic_v2_cost.py"


def _load():
    """Import the script by path; ``scripts`` is not a package."""
    spec = importlib.util.spec_from_file_location("roll_up_agentic_v2_cost", ROLLUP_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


rollup = _load()

PINNED = "gpt-5.4"


def _shard(
    root: Path,
    name: str,
    *,
    calls: dict[str, list[tuple[str, int, int, str]]],
    assigned: list[str],
    cohort: list[str],
    run_id: str = "a-run",
) -> Path:
    """One downloaded shard artifact: a ledger and a record beside it.

    ``calls`` maps task id to ``(call_id, input, output, model)`` tuples. The
    ledger is opened **with** the committed price table, the way a real shard
    opens it, so the rows carry real amounts and a real fingerprint.
    """
    shard_dir = root / name
    shard_dir.mkdir(parents=True, exist_ok=True)

    ledger = CostReceiptLedger(
        shard_dir / "cost_receipts.sqlite3",
        run_id=run_id,
        price_table=load_receipt_price_table(),
    )
    try:
        for task_id, entries in calls.items():
            for call_id, tokens_in, tokens_out, model in entries:
                ledger.reserve(
                    call_id=call_id,
                    task_id=task_id,
                    stage=STAGE_GENERATION,
                    retry_kind="none",
                    provider="azure",
                    requested_model=model,
                    deployment="a-deployment",
                )
                ledger.settle(
                    call_id,
                    usage=CallUsage(input_tokens=tokens_in, output_tokens=tokens_out),
                    resolved_model=model,
                )
    finally:
        ledger.close()

    (shard_dir / "run_record.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "stage": "advance_check_5",
                "binding": {"task_ids": cohort},
                "shard": {"task_ids": assigned, "cohort_size": len(cohort)},
            }
        )
    )
    return shard_dir


def _roll(records: Path, tmp_path: Path) -> dict:
    return rollup.roll_up(
        records,
        stage="advance_check_5",
        merged_into=tmp_path / "merged.sqlite3",
    )


def _row(result: dict, task_id: str) -> dict:
    for entry in result["tasks"]:
        if entry["task_id"] == task_id:
            return entry
    raise AssertionError(f"{task_id} is not in the roll-up")


# ── the number the goal asks for ────────────────────────────────────────────


def test_each_task_gets_its_own_amount(tmp_path):
    """The whole point: money split by task, not one lump for the stage.

    Two tasks with deliberately different token counts, so a roll-up that
    accidentally reported the stage total per task would not survive.
    """
    records = tmp_path / "records"
    _shard(
        records,
        "shard-1",
        calls={
            "t1": [("a-run:t1:1:c1", 1_000_000, 1_000_000, PINNED)],
            "t2": [("a-run:t2:1:c1", 2_000_000, 2_000_000, PINNED)],
        },
        assigned=["t1", "t2"],
        cohort=["t1", "t2"],
    )

    result = _roll(records, tmp_path)

    # $2.50 in + $15.00 out per million.
    assert _row(result, "t1")["estimated_cost_usd"] == pytest.approx(17.50)
    assert _row(result, "t2")["estimated_cost_usd"] == pytest.approx(35.00)
    assert result["stage_total"]["estimated_cost_usd"] == pytest.approx(52.50)
    assert result["accounting"]["cost_is_fully_accounted"] is True


def test_two_shards_are_added_up(tmp_path):
    """A stage runs as up to 17 shards; the total has to cross them."""
    records = tmp_path / "records"
    _shard(
        records,
        "shard-1",
        calls={"t1": [("a-run:t1:1:c1", 1_000_000, 1_000_000, PINNED)]},
        assigned=["t1"],
        cohort=["t1", "t2"],
    )
    _shard(
        records,
        "shard-2",
        calls={"t2": [("a-run:t2:1:c1", 1_000_000, 1_000_000, PINNED)]},
        assigned=["t2"],
        cohort=["t1", "t2"],
    )

    result = _roll(records, tmp_path)

    assert result["population"]["in_the_ledger"] == 2
    assert result["stage_total"]["estimated_cost_usd"] == pytest.approx(35.00)
    assert result["problems"] == []


def test_a_shard_uploaded_twice_is_not_billed_twice(tmp_path):
    """The failure mode that would silently double a 220-task bill.

    Re-running a shard's upload, or re-downloading its artifact into a second
    directory, must not change the total. The ledger's primary key on
    ``call_id`` is what prevents it, which is why the merge goes through
    ``import_jsonl`` rather than reading the tables directly.
    """
    records = tmp_path / "records"
    for name in ("shard-1", "shard-1-again"):
        _shard(
            records,
            name,
            calls={"t1": [("a-run:t1:1:c1", 1_000_000, 1_000_000, PINNED)]},
            assigned=["t1"],
            cohort=["t1"],
        )

    result = _roll(records, tmp_path)

    assert len(result["read_from"]["ledgers"]) == 2
    assert _row(result, "t1")["model_calls"] == 1
    assert result["stage_total"]["estimated_cost_usd"] == pytest.approx(17.50)


def test_a_retried_task_pays_for_both_attempts(tmp_path):
    """The mirror of the test above, and the way over-eager dedup would show.

    Collapsing by task instead of by ``call_id`` would make this read $17.50
    and look like a fix for double billing. A task retried once cost both
    attempts, and the run is charged for both.
    """
    records = tmp_path / "records"
    _shard(
        records,
        "shard-1",
        calls={
            "t1": [
                ("a-run:t1:1:c1", 1_000_000, 1_000_000, PINNED),
                ("a-run:t1:2:c1", 1_000_000, 1_000_000, PINNED),
            ]
        },
        assigned=["t1"],
        cohort=["t1"],
    )

    result = _roll(records, tmp_path)

    assert _row(result, "t1")["model_calls"] == 2
    assert _row(result, "t1")["estimated_cost_usd"] == pytest.approx(35.00)


def test_shards_that_disagree_about_a_call_refuse_to_produce_a_total(tmp_path):
    """Two answers for one call means no answer, not the first one seen.

    The ledger already raises here. What this pins is that the roll-up lets it
    become a refusal instead of catching it and publishing one of the two.
    """
    records = tmp_path / "records"
    _shard(
        records,
        "shard-1",
        calls={"t1": [("a-run:t1:1:c1", 1_000_000, 1_000_000, PINNED)]},
        assigned=["t1"],
        cohort=["t1"],
    )
    _shard(
        records,
        "shard-2",
        calls={"t1": [("a-run:t1:1:c1", 9_000_000, 9_000_000, PINNED)]},
        assigned=["t1"],
        cohort=["t1"],
    )

    with pytest.raises(rollup.MergeRefused) as refused:
        _roll(records, tmp_path)

    assert "differently" in str(refused.value)


def test_a_refused_merge_exits_non_zero_and_writes_nothing(tmp_path):
    """The one case that is worth a red job: a total that cannot be trusted."""
    records = tmp_path / "records"
    for name, tokens in (("shard-1", 1_000_000), ("shard-2", 9_000_000)):
        _shard(
            records,
            name,
            calls={"t1": [("a-run:t1:1:c1", tokens, tokens, PINNED)]},
            assigned=["t1"],
            cohort=["t1"],
        )
    out = tmp_path / "cost_rollup.json"

    code = rollup.main(
        ["--records", str(records), "--stage", "advance_check_5", "--out", str(out)]
    )

    assert code == 1
    assert not out.exists()


# ── what a task that did not run is allowed to say ──────────────────────────


def test_a_task_that_never_reached_the_ledger_is_not_free(tmp_path):
    """The reading that would make a half-finished 220 look cheap.

    Run ``34651982737`` is exactly this shape: five tasks assigned, the first
    one killed the process, four never reached the ledger. Reporting those four
    at ``$0.00`` would turn "the stage did not finish" into "the stage was
    inexpensive".
    """
    records = tmp_path / "records"
    _shard(
        records,
        "shard-1",
        calls={"t1": [("a-run:t1:1:c1", 1_000_000, 1_000_000, PINNED)]},
        assigned=["t1", "t2", "t3", "t4", "t5"],
        cohort=["t1", "t2", "t3", "t4", "t5"],
    )

    result = _roll(records, tmp_path)

    assert result["population"]["assigned_but_never_reached_the_ledger"] == [
        "t2",
        "t3",
        "t4",
        "t5",
    ]
    for task_id in ("t2", "t3", "t4", "t5"):
        row = _row(result, task_id)
        assert row["status"] == "not_run"
        assert row["estimated_cost_usd"] is None
        assert row["model_calls"] == 0

    # And the tasks that did not happen do not drag the total off `complete`:
    # `not_run` is excluded from the summary, so the one task that ran still
    # has a real amount. What says the stage is unfinished is the population
    # block, not a poisoned total.
    assert result["stage_total"]["estimated_cost_usd"] == pytest.approx(17.50)
    assert result["accounting"]["tasks_with_a_complete_receipt"] == 1
    assert result["accounting"]["tasks_accounted_for"] == 5
    assert result["accounting"]["cost_is_fully_accounted"] is False


def test_a_cohort_task_no_shard_reported_is_a_named_hole(tmp_path):
    """A missing artifact must not shrink the denominator to fit."""
    records = tmp_path / "records"
    _shard(
        records,
        "shard-1",
        calls={"t1": [("a-run:t1:1:c1", 1_000, 100, PINNED)]},
        assigned=["t1"],
        cohort=["t1", "t2", "t3"],
    )

    result = _roll(records, tmp_path)

    assert result["population"]["cohort_size"] == 3
    assert result["population"]["never_assigned_to_any_shard"] == ["t2", "t3"]
    assert any("no shard record" in problem for problem in result["problems"])


def test_nothing_at_all_is_reported_as_no_account_not_as_no_spending(tmp_path):
    """An empty download is the loudest thing this tool can find.

    A paid stage that published no ledger did not necessarily spend nothing —
    if a shard reached the model it was billed, and the account is what is
    missing, not the money.
    """
    records = tmp_path / "records"
    records.mkdir()

    result = _roll(records, tmp_path)

    assert result["stage_total"]["status"] == "not_run"
    assert result["stage_total"]["estimated_cost_usd"] is None
    assert result["accounting"]["cost_is_fully_accounted"] is False
    assert any("spent nothing" in problem for problem in result["problems"])


# ── a floor is not a total ──────────────────────────────────────────────────


def test_an_unpriced_call_leaves_a_floor_and_says_so(tmp_path):
    """``known_cost_usd`` is real; it is just not the answer to "how much".

    One priced task and one unpriced one. The stage keeps a floor — what is
    confirmed — and refuses to present it as a total.
    """
    records = tmp_path / "records"
    _shard(
        records,
        "shard-1",
        calls={
            "t1": [("a-run:t1:1:c1", 1_000_000, 1_000_000, PINNED)],
            "t2": [("a-run:t2:1:c1", 1_000_000, 1_000_000, "a-model-nobody-priced")],
        },
        assigned=["t1", "t2"],
        cohort=["t1", "t2"],
    )

    result = _roll(records, tmp_path)

    unpriced = _row(result, "t2")
    assert unpriced["status"] == "partial"
    assert unpriced["estimated_cost_usd"] is None
    assert unpriced["known_cost_is_a_floor_not_a_total"] is True
    assert "price_missing" in unpriced["missing_reasons"]

    total = result["stage_total"]
    assert total["status"] == "partial"
    assert total["estimated_cost_usd"] is None
    assert total["known_cost_usd"] == pytest.approx(17.50)
    assert "floor" in result["accounting"]["what_the_total_is"]
    assert result["accounting"]["cost_is_fully_accounted"] is False


def test_a_complete_stage_is_allowed_to_call_its_total_a_total(tmp_path):
    """The rule cuts both ways, or it is just pessimism."""
    records = tmp_path / "records"
    _shard(
        records,
        "shard-1",
        calls={"t1": [("a-run:t1:1:c1", 1_000_000, 1_000_000, PINNED)]},
        assigned=["t1"],
        cohort=["t1"],
    )

    result = _roll(records, tmp_path)

    assert result["accounting"]["what_the_total_is"] == "a total"
    assert _row(result, "t1")["known_cost_is_a_floor_not_a_total"] is False


def test_a_call_that_left_and_never_came_back_holds_the_stage_partial(tmp_path):
    """A reservation with no settlement may still have been billed.

    This is the state a shard killed by its own ``timeout-minutes`` leaves
    behind, and it is not the same as the task not running.
    """
    records = tmp_path / "records"
    shard_dir = records / "shard-1"
    shard_dir.mkdir(parents=True)
    ledger = CostReceiptLedger(
        shard_dir / "cost_receipts.sqlite3",
        run_id="a-run",
        price_table=load_receipt_price_table(),
    )
    try:
        ledger.reserve(
            call_id="a-run:t1:1:c1",
            task_id="t1",
            stage=STAGE_GENERATION,
            retry_kind="none",
            provider="azure",
            requested_model=PINNED,
        )
    finally:
        ledger.close()
    (shard_dir / "run_record.json").write_text(
        json.dumps(
            {
                "run_id": "a-run",
                "binding": {"task_ids": ["t1"]},
                "shard": {"task_ids": ["t1"], "cohort_size": 1},
            }
        )
    )

    result = _roll(records, tmp_path)

    row = _row(result, "t1")
    assert row["status"] == "partial"
    assert row["estimated_cost_usd"] is None
    assert "call_reachability_unknown" in row["missing_reasons"]


# ── the fingerprint has to come from the rows ───────────────────────────────


def test_the_merge_keeps_the_table_the_calls_were_settled_under(tmp_path):
    """The merged ledger holds no price table, and must not need one.

    Rows carry the fingerprint of the table that priced them. If the roll-up
    opened the merge with today's committed file, a run settled last week would
    come back stamped with this week's fingerprint — a claim nobody could
    check and everybody would believe.
    """
    records = tmp_path / "records"
    _shard(
        records,
        "shard-1",
        calls={"t1": [("a-run:t1:1:c1", 1_000, 100, PINNED)]},
        assigned=["t1"],
        cohort=["t1"],
    )

    result = _roll(records, tmp_path)

    assert _row(result, "t1")["price_table_sha256"] == load_receipt_price_table().sha256
    assert result["stage_total"]["price_table_sha256"] is not None


def test_the_merged_ledger_is_opened_without_a_price_table(tmp_path):
    """Stated on the object, so a later "helpful" edit fails here.

    Passing the committed table would look like an improvement and would
    quietly re-stamp old money.
    """
    records = tmp_path / "records"
    _shard(
        records,
        "shard-1",
        calls={"t1": [("a-run:t1:1:c1", 1_000, 100, PINNED)]},
        assigned=["t1"],
        cohort=["t1"],
    )
    seen = {}

    original = rollup.CostReceiptLedger

    def watch(path, **kwargs):
        seen.setdefault("price_table", kwargs.get("price_table"))
        return original(path, **kwargs)

    rollup.CostReceiptLedger = watch
    try:
        _roll(records, tmp_path)
    finally:
        rollup.CostReceiptLedger = original

    assert seen["price_table"] is None


# ── the shape of the file, and the sentence in the job log ──────────────────


def test_main_writes_the_file_and_exits_zero_on_an_unfinished_stage(tmp_path):
    """A stage that went badly still produces its account.

    This tool is not a second gate. ``check_agentic_v2_stage_coverage.py`` owns
    pass/fail for a stage; a red mark here on an already-red run would only
    make the real reason harder to find.
    """
    records = tmp_path / "records"
    _shard(
        records,
        "shard-1",
        calls={"t1": [("a-run:t1:1:c1", 1_000, 100, "a-model-nobody-priced")]},
        assigned=["t1", "t2"],
        cohort=["t1", "t2"],
    )
    out = tmp_path / "cost_rollup.json"

    code = rollup.main(
        ["--records", str(records), "--stage", "advance_check_5", "--out", str(out)]
    )

    assert code == 0
    written = json.loads(out.read_text())
    assert written["schema_version"] == rollup.ROLLUP_SCHEMA_VERSION
    assert written["stage"] == "advance_check_5"
    assert written["run_id"] == "a-run"
    assert [row["task_id"] for row in written["tasks"]] == ["t1", "t2"]


def test_the_log_line_names_the_floor_rather_than_a_bare_number(tmp_path):
    """Whoever reads the job log reads this and nothing else."""
    records = tmp_path / "records"
    _shard(
        records,
        "shard-1",
        calls={"t1": [("a-run:t1:1:c1", 1_000, 100, "a-model-nobody-priced")]},
        assigned=["t1"],
        cohort=["t1"],
    )

    said = rollup.describe(_roll(records, tmp_path))

    assert "floor" in said
    assert "price_missing" in said


def test_shards_from_different_runs_are_named_as_such(tmp_path):
    """Two runs merged by accident would produce a real-looking wrong total.

    Call ids are namespaced by run, so nothing is double counted — but the
    result is not one run's bill and the file has to say so.
    """
    records = tmp_path / "records"
    _shard(
        records,
        "shard-1",
        calls={"t1": [("run-a:t1:1:c1", 1_000, 100, PINNED)]},
        assigned=["t1"],
        cohort=["t1"],
        run_id="run-a",
    )
    _shard(
        records,
        "shard-2",
        calls={"t2": [("run-b:t2:1:c1", 1_000, 100, PINNED)]},
        assigned=["t2"],
        cohort=["t2"],
        run_id="run-b",
    )

    result = _roll(records, tmp_path)

    assert any("different run ids" in problem for problem in result["problems"])


def test_nothing_in_the_roll_up_is_a_zero_that_was_not_measured(tmp_path):
    """The rule the whole file exists for, asserted across every row.

    Any row whose status is not ``complete`` must carry a null estimate. A
    ``0.0`` there would be the one number in the account that reads as a
    measurement.
    """
    records = tmp_path / "records"
    _shard(
        records,
        "shard-1",
        calls={
            "t1": [("a-run:t1:1:c1", 1_000, 100, PINNED)],
            "t2": [("a-run:t2:1:c1", 1_000, 100, "a-model-nobody-priced")],
        },
        assigned=["t1", "t2", "t3"],
        cohort=["t1", "t2", "t3"],
    )

    result = _roll(records, tmp_path)

    for row in result["tasks"]:
        if row["status"] != "complete":
            assert row["estimated_cost_usd"] is None, row["task_id"]


# ── a reader nothing calls is the defect this file was written about ────────


def _collect_steps() -> list[dict]:
    import yaml

    workflow = yaml.safe_load(
        (
            BATCH_RUNNER_ROOT.parent
            / ".github"
            / "workflows"
            / "agentic-v2-stage-run.yml"
        ).read_text()
    )
    return workflow["jobs"]["collect"]["steps"]


def test_the_collect_job_actually_calls_the_roll_up():
    """The whole point, and the thing that was missing before.

    A cost reader that no job runs is the same defect as the ledger nothing
    read: the capability exists, the tests pass, and no run produces the file.
    ``coverage_problems`` sat uncalled in this repository for days behind
    exactly this gap.
    """
    called = [
        step
        for step in _collect_steps()
        if "roll_up_agentic_v2_cost.py" in (step.get("run") or "")
    ]

    assert len(called) == 1
    assert "--stage" in called[0]["run"]
    assert "../shard-records" in called[0]["run"]


def test_the_bill_is_read_before_the_verdict_that_fails_the_job():
    """Order matters here, and it is the opposite of the obvious one.

    ``check_agentic_v2_stage_coverage.py`` is built to fail a stage that did
    not run. A stage that did not run is precisely the one whose bill has to
    be recoverable -- run 34651982737 spent money on two model calls and left
    no account at all. Reading after the verdict would lose the account on
    every run worth accounting for.
    """
    names = [
        step.get("name", "")
        for step in _collect_steps()
        if step.get("run") or step.get("uses")
    ]
    read = next(i for i, n in enumerate(names) if n == "Read what the stage spent")
    verdict = next(i for i, n in enumerate(names) if n == "Check coverage and halts")

    assert read < verdict


def test_the_coverage_verdict_survives_a_refused_roll_up():
    """The roll-up may fail the job; it may not replace the gate.

    ``MergeRefused`` exits non-zero, and a failing step normally skips every
    step after it. Without ``always()`` here, two shards disagreeing about one
    call would mean the stage's coverage was never checked -- a cost problem
    silently swallowing the answer to "did the stage run".
    """
    verdict = next(
        step
        for step in _collect_steps()
        if step.get("name") == "Check coverage and halts"
    )

    assert "always()" in str(verdict.get("if", ""))


def test_the_roll_up_is_kept_even_when_the_stage_is_judged_a_failure():
    """The artifact outlives the verdict, for the same reason."""
    keep = next(
        step for step in _collect_steps() if step.get("name") == "Keep the cost roll-up"
    )

    assert "always()" in str(keep.get("if", ""))
    assert keep["with"]["path"] == "cost-rollup/"
    # Its own artifact, not folded into the shard pattern the collect job
    # downloads -- that would make the next run's download recursive.
    assert "shard" not in keep["with"]["name"]


def test_the_free_job_runs_these_tests():
    """A test file no workflow names is a test file that rots.

    The stage workflow lists its tests one by one rather than running the
    suite, so a new file is invisible until it is added to that list.
    """
    import yaml

    workflow = (
        BATCH_RUNNER_ROOT.parent / ".github" / "workflows" / "agentic-v2-stage-run.yml"
    ).read_text()

    assert Path(__file__).name in workflow
    # And mypy sees the script, which is how the first paid dispatch's defect
    # was reported at its exact line.
    free = yaml.safe_load(workflow)["jobs"]["free"]["steps"]
    checked = [
        step for step in free if "roll_up_agentic_v2_cost.py" in (step.get("run") or "")
    ]
    assert len(checked) == 1
    assert "mypy" in checked[0]["run"]
