"""The bill has to outlive the run, the chunk, and the runner.

Stage 3, shard 4 of 11 (run ``33239148807``) graded six tasks over five hours
and twenty minutes, was killed by the job's own ``timeout-minutes: 320`` inside
the seventh, and left ``{"total_count":0,"artifacts":[]}`` behind. Not a
partial grade, not a ledger, nothing. Every call it paid for is unrecorded, and
the only reason we know roughly what it spent is the workflow log.

Three separate things had to be true at once for that to happen, and each of
them was also quietly true of the *successful* shards:

* the ledger was exported only at a save, and this run never saved
  (``partial_save_every_n_tasks`` is 10, and it had six);
* the artifact upload was gated on ``steps.grade.outputs.grade_file``, an
  output written inside the save path — so a run that never saved could not
  even upload the sqlite3 it had been writing all along;
* nothing ever committed the ledger, so the copy on the runner was the only
  copy, and the runner is discarded between chunks.

The third one is the expensive one, because it is not about failure at all.
``step9_merge_shards.merge_shard_cost_ledgers`` looks for each shard's export
*beside that shard's JSON in the checkout*, and a resumed chunk rebuilds its
ledger by importing what the previous chunk left there. Both read from the
repository. Nothing wrote to it. So on every run so far the merge found no
ledger and dropped it, and every resumed chunk began counting from zero — the
per-call record was being lost on the runs that succeeded.

Nothing here calls a model or a network. The tests exercise the real ledger,
the real merge function, and the text of the real workflow.
"""

from __future__ import annotations

import ast
import json
import signal
from pathlib import Path

import pytest
import yaml

import step8_grade as s8
from core.cost_metering import Attribution, CostRecorder, open_cost_recorder
from core.cost_receipts import (
    RETRY_NONE,
    STAGE_GRADING,
    CallUsage,
    CostReceiptLedger,
)
from step9_merge_shards import merge_shard_cost_ledgers

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github/workflows/grade-run.yml"
STEP8 = Path(s8.__file__).resolve()


# ── helpers ──────────────────────────────────────────────────────────────


def _usage() -> CallUsage:
    return CallUsage(
        input_tokens=1000, cached_input_tokens=200,
        output_tokens=100, reasoning_tokens=0,
    )


def _spend(ledger: CostReceiptLedger, recorder: CostRecorder, task_id: str) -> str:
    """One settled grading call, identified the way the real recorder does."""
    call_id = recorder._next_call_id(
        Attribution(task_id=task_id, stage=STAGE_GRADING,
                    retry_kind=RETRY_NONE, attempt_index=0)
    )
    ledger.reserve(
        call_id=call_id, task_id=task_id, stage=STAGE_GRADING,
        retry_kind=RETRY_NONE, provider="azure", requested_model="a-deployment",
    )
    ledger.settle(call_id, usage=_usage(), resolved_model="test-model")
    return call_id


def _workflow_steps() -> list[dict]:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["grade"]["steps"]


def _step(name: str) -> dict:
    for step in _workflow_steps():
        if step.get("name") == name:
            return step
    raise AssertionError(f"grade-run.yml has no step named {name!r}")


def _main_body() -> list[ast.stmt]:
    """``main`` is where the Track 2 loop and its exit codes actually live."""
    tree = ast.parse(STEP8.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            return node.body
    raise AssertionError("step8_grade has no main")


# ── a fresh runner picking up where the last one stopped ─────────────────


def test_a_fresh_runner_rebuilds_its_ledger_from_the_committed_export(tmp_path):
    """The sequence step8 now performs before it opens the recorder.

    Chunk one writes a ledger and exports it; the runner is destroyed, taking
    the sqlite3 with it and leaving only the committed JSONL; chunk two starts
    on an empty workspace. What it must end up with is both chunks' calls, in
    one file, with no identifier reused.

    The import has to happen *before* ``open_cost_recorder``. ``continue_rounds``
    reads the round number off the ledger's size and the round is folded into
    every call identifier, so seeding afterwards would number chunk two's first
    call exactly as chunk one numbered its own.
    """
    export = tmp_path / "shard-004-of-011.cost_ledger.jsonl"
    first_db = tmp_path / "chunk1.sqlite3"
    with CostReceiptLedger(first_db, run_id="exp|cfg|src") as first:
        recorder = CostRecorder(first, round_index=0)
        _spend(first, recorder, "task-a")
        _spend(first, recorder, "task-b")
        first.export_jsonl(export)
    first_db.unlink()  # the runner goes away; the commit does not

    second_db = tmp_path / "chunk2.sqlite3"
    with CostReceiptLedger(second_db, run_id="exp|cfg|src") as seed:
        assert seed.import_jsonl(export) == 2

    recorder, note = open_cost_recorder(
        second_db, run_id="exp|cfg|src", continue_rounds=True
    )
    assert recorder is not None
    assert recorder.round_index == 2, (
        "the round must clear the calls already in the ledger, or chunk two "
        "re-issues chunk one's identifiers"
    )

    _spend(recorder.ledger, recorder, "task-c")
    digest = recorder.ledger.export_jsonl(export)
    recorder.ledger.close()

    records = [json.loads(line) for line in
               export.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert {r["task_id"] for r in records} == {"task-a", "task-b", "task-c"}
    assert len({r["call_id"] for r in records}) == 3
    assert len(digest) == 64


def test_importing_the_same_export_twice_adds_nothing(tmp_path):
    """A chunk that reruns after its commit landed must not double-bill.

    The retrigger can fire on a chunk whose grade and ledger were already
    pushed. Identifiers are derived from position rather than content, so the
    second import recognises every record as one it already holds.
    """
    export = tmp_path / "ledger.jsonl"
    with CostReceiptLedger(tmp_path / "a.sqlite3", run_id="r") as first:
        _spend(first, CostRecorder(first, round_index=0), "task-a")
        first.export_jsonl(export)

    with CostReceiptLedger(tmp_path / "b.sqlite3", run_id="r") as second:
        assert second.import_jsonl(export) == 1
        assert second.import_jsonl(export) == 0
        assert second.call_count() == 1


# ── the merge only works if the export was committed ─────────────────────


def _shard(tmp_path: Path, index: int, task_id: str) -> tuple[Path, dict]:
    shard_path = tmp_path / f"shard-{index:03d}-of-002.json"
    export = shard_path.with_name(shard_path.stem + ".cost_ledger.jsonl")
    with CostReceiptLedger(tmp_path / f"{index}.sqlite3", run_id="r") as ledger:
        _spend(ledger, CostRecorder(ledger, round_index=index), task_id)
        digest = ledger.export_jsonl(export)
    payload = {"cost_ledger": {"path": export.name, "sha256": digest}}
    shard_path.write_text(json.dumps(payload), encoding="utf-8")
    return shard_path, payload


def test_the_merge_finds_a_ledger_that_was_committed_beside_its_shard(tmp_path):
    """What the workflow's ``git add`` of the export buys.

    The pointer a shard publishes is a path from the repository root, and the
    merge resolves it against the root it is running in. Shards that were
    graded on separate runners and never moved into one checkout keep roots of
    their own, so each directory above the shard file is tried too -- which is
    also how the bare filenames written before this field was a path at all
    still resolve, since the shard's own directory is the first one tried.
    """
    warnings: list[str] = []
    first = _shard(tmp_path, 0, "task-a")
    second = _shard(tmp_path, 1, "task-b")
    out_path = tmp_path / "final.json"

    pointer = merge_shard_cost_ledgers(
        [first[0], second[0]], [first[1], second[1]], out_path,
        repo_root=tmp_path, warn=warnings.append,
    )

    assert warnings == []
    assert pointer is not None
    merged = out_path.with_name(out_path.stem + ".cost_ledger.jsonl")
    records = [json.loads(line) for line in
               merged.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert {r["task_id"] for r in records} == {"task-a", "task-b"}
    # Resolved from the root, not from beside the grade: that is the whole
    # contract, and here the two happen to name the same file.
    assert pointer["path"] == merged.name
    assert (tmp_path / pointer["path"]).is_file()


def test_a_merged_ledger_outside_the_repository_is_no_pointer_at_all(tmp_path):
    """The field is a repository path, so there is nothing honest to write.

    A local merge writing somewhere outside the checkout has no repository
    path to give, and a bare filename is not a smaller version of one -- it is
    what the field held for its whole life, and none of the thirty-eight grade
    files carrying it named a file anybody could find.
    """
    warnings: list[str] = []
    first = _shard(tmp_path, 0, "task-a")
    second = _shard(tmp_path, 1, "task-b")

    pointer = merge_shard_cost_ledgers(
        [first[0], second[0]], [first[1], second[1]], tmp_path / "final.json",
        repo_root=tmp_path / "elsewhere", warn=warnings.append,
    )

    assert pointer is None
    assert any("outside the repository" in message for message in warnings)


def test_a_shard_ledger_a_directory_down_is_named_from_the_root(tmp_path):
    """The shape every real published pointer has: a path, not a name.

    Shards land in ``data/grades/_shards/<stem>/``, several directories below
    the root, and the merged grade lands in ``data/grades/``. Nothing about
    either is reconstructible from a filename.
    """
    shards = tmp_path / "data" / "grades" / "_shards" / "stem"
    shards.mkdir(parents=True)
    first = _shard(shards, 0, "task-a")
    second = _shard(shards, 1, "task-b")
    for shard_path, payload in (first, second):
        payload["cost_ledger"]["path"] = (
            f"data/grades/_shards/stem/{shard_path.stem}.cost_ledger.jsonl"
        )
        shard_path.write_text(json.dumps(payload), encoding="utf-8")

    out_path = tmp_path / "data" / "grades" / "final.json"
    pointer = merge_shard_cost_ledgers(
        [first[0], second[0]], [first[1], second[1]], out_path,
        repo_root=tmp_path, warn=lambda message: pytest.fail(message),
    )

    assert pointer is not None
    assert pointer["path"] == "data/grades/final.cost_ledger.jsonl"
    assert (tmp_path / pointer["path"]).is_file()


def test_an_uncommitted_ledger_makes_the_merged_grade_claim_none(tmp_path):
    """The state every Stage 3 merge was in until the export was committed.

    Worth pinning as a test rather than left as a warning in a log: the merge
    does not fail, it just declines to publish a trail — which is why the
    omission survived nine shards without anyone noticing.
    """
    warnings: list[str] = []
    first = _shard(tmp_path, 0, "task-a")
    second = _shard(tmp_path, 1, "task-b")
    second[0].with_name(second[0].stem + ".cost_ledger.jsonl").unlink()

    pointer = merge_shard_cost_ledgers(
        [first[0], second[0]], [first[1], second[1]], tmp_path / "final.json",
        repo_root=tmp_path, warn=warnings.append,
    )

    assert pointer is None
    assert any("neither under" in message for message in warnings)


# ── being killed is not an excuse ────────────────────────────────────────


def test_a_termination_signal_unwinds_instead_of_killing_the_process():
    """SIGTERM has to become ``SystemExit`` or the exit handlers never run.

    This is the shard-4 case exactly: GitHub sends SIGTERM at
    ``timeout-minutes``, Python's default disposition ends the process on the
    spot, and ``atexit`` — where the final export lives — is skipped.
    """
    with pytest.raises(SystemExit) as raised:
        s8._exit_on_signal(signal.SIGTERM, None)
    assert raised.value.code == 128 + int(signal.SIGTERM) == 143

    with pytest.raises(SystemExit) as interrupted:
        s8._exit_on_signal(signal.SIGINT, None)
    assert interrupted.value.code == 130


def test_the_ledger_is_flushed_on_every_way_out_of_the_grading_run():
    """Wiring, asserted structurally, because the paths cannot all be run.

    The Track 2 loop lives in ``main`` and needs a graded corpus and a live
    endpoint to reach most of its returns, so what is checked here is that the
    flush is attached to the three exits that exist: the common ``finish``
    helper every ``return`` goes through, the interpreter's own shutdown, and
    the signal that arrives when the job is cancelled. If someone moves the
    export back to the save path, this fails and names the run that cost five
    hours.
    """
    body = _main_body()
    source = ast.unparse(ast.Module(body=body, type_ignores=[]))

    assert "atexit.register(flush_cost_ledger)" in source
    assert "signal.signal(_signum, _exit_on_signal)" in source
    assert "(signal.SIGTERM, signal.SIGINT)" in source

    finish = next(
        node for node in body
        if isinstance(node, ast.FunctionDef) and node.name == "finish"
    )
    assert "flush_cost_ledger()" in ast.unparse(finish), (
        "every return in the Track 2 loop goes through finish(); if it "
        "stops "
        "flushing, a failed run stops leaving a ledger behind"
    )

    flush = next(
        node for node in body
        if isinstance(node, ast.FunctionDef) and node.name == "flush_cost_ledger"
    )
    flushed = ast.unparse(flush)
    assert "export_jsonl(cost_export_path)" in flushed
    assert "cost_ledger_file" in flushed and "cost_ledger_sha256" in flushed


# ── ...but only while there is still a ledger to flush ───────────────────


def test_exporting_a_closed_ledger_raises_rather_than_returning_nothing(tmp_path):
    """The sqlite fact the whole ordering below rests on.

    Stated as a test because it is the part that is easy to forget: a ledger
    that has been closed does not export empty or export stale, it raises. So
    "flush somewhere near the end" is not good enough — the flush has to be
    strictly before the close, on every path, or it writes nothing at all.
    """
    ledger = CostReceiptLedger(tmp_path / "l.sqlite3", run_id="r")
    _spend(ledger, CostRecorder(ledger, round_index=0), "task-a")
    assert len(ledger.export_jsonl(tmp_path / "open.jsonl")) == 64
    ledger.close()

    with pytest.raises(Exception) as raised:
        ledger.export_jsonl(tmp_path / "closed.jsonl")
    assert type(raised.value).__name__ == "ProgrammingError"


def test_the_close_exports_before_it_shuts_the_ledger():
    """``atexit`` unwinds backwards, which inverts the order that was wanted.

    ``flush_cost_ledger`` is registered first and ``close_grader`` second, so
    on the paths that skip ``finish`` — the crash and the cancellation, which
    are the only paths any of this exists for — ``close_grader`` runs *first*
    and closes the database. The flush that follows then raises against a
    closed handle and writes nothing, which is precisely the shard-4 outcome
    this module was written to prevent, reintroduced one layer down.

    Registration order is not the fix, because a third handler added later
    would silently reorder it again. The fix is that the close performs the
    flush itself, so the two cannot be separated by anything.
    """
    body = _main_body()
    source = ast.unparse(ast.Module(body=body, type_ignores=[]))
    assert source.index("atexit.register(flush_cost_ledger)") < source.index(
        "atexit.register(close_grader)"
    ), "if this ever flips, read the docstring before 'fixing' it here"

    close = next(
        node for node in body
        if isinstance(node, ast.FunctionDef) and node.name == "close_grader"
    )
    closed = ast.unparse(close)
    assert "flush_cost_ledger()" in closed, (
        "the close is the last moment the ledger can still be read; a crash "
        "that never reaches finish() has no other chance to export it"
    )
    assert closed.index("flush_cost_ledger()") < closed.index(
        "cost_recorder.ledger.close()"
    ), "flushing after the close exports nothing and reports ProgrammingError"


def test_a_flush_after_the_close_says_nothing():
    """A false report of loss is its own failure, not a cosmetic one.

    The ``atexit`` flush still fires after ``close_grader`` has run. Left
    unguarded it prints ``final ledger export failed (ProgrammingError)`` as
    the last line of a *successful* run, over a ledger sitting safely on disk.
    Someone reading that during an incident would go looking for a bill that
    was never lost, which is the opposite of what a safety net is for.
    """
    flush = next(
        node for node in _main_body()
        if isinstance(node, ast.FunctionDef) and node.name == "flush_cost_ledger"
    )
    guard = ast.unparse(
        next(node for node in flush.body if isinstance(node, ast.If))
    )
    assert "ledger_closed" in guard, (
        "the post-close flush must be a no-op; see "
        "test_the_close_exports_before_it_shuts_the_ledger"
    )
    assert "return" in guard


# ── the workflow half ────────────────────────────────────────────────────


def test_the_workflow_commits_the_ledger_beside_its_grade():
    """The export is committed, verified against the digest step8 published.

    Committing is what makes the two readers above work: the merge resolves
    the pointer against the checkout, and a resumed chunk imports what its
    predecessor left there. Uploading an artifact does neither.
    """
    step = _step("Commit grade result")
    assert step["env"]["COST_LEDGER_FILE"] == (
        "${{ steps.grade.outputs.cost_ledger_file }}"
    )
    assert step["env"]["COST_LEDGER_SHA256"] == (
        "${{ steps.grade.outputs.cost_ledger_sha256 }}"
    )
    run = step["run"]
    assert 'git add -- "$COST_LEDGER_FILE"' in run
    assert "$COST_LEDGER_SHA256" in run, (
        "the committed file must be checked against the digest step8 "
        "published for it, or the grade points at something else"
    )
    assert "data/grades/*.cost_ledger.jsonl" in run


def test_the_ledger_upload_is_not_gated_on_a_grade_that_was_saved():
    """The gate that made a five-hour run leave zero artifacts.

    ``steps.grade.outputs.grade_file`` is written inside the save path. A run
    killed before its first save has no such output, so a condition naming it
    is false exactly when preservation matters most. This upload names neither
    that output nor the step's outcome.
    """
    condition = str(_step("Upload cost ledger")["if"])
    assert "always()" in condition
    assert "grade_file" not in condition
    assert "steps.grade" not in condition

    with_ = _step("Upload cost ledger")["with"]
    paths = str(with_["path"])
    assert "*.cost_ledger.jsonl" in paths
    assert "*.cost_ledger.sqlite3" in paths, (
        "the sqlite3 is the copy that exists even when the exporter never "
        "ran, so it is the one that survives a kill"
    )
    assert "${{" not in paths, (
        "a path built from a step output reintroduces the gate through the "
        "back door: it resolves to empty and uploads nothing"
    )


def test_the_grade_upload_still_carries_the_grade():
    """The change above adds an artifact; it must not have moved one."""
    with_ = _step("Upload grade artifact")["with"]
    assert "steps.grade.outputs.grade_file" in str(with_["path"])
