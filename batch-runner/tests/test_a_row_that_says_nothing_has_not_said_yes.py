"""A task row that never answered has not answered yes.

``summary.cost.usage_complete`` is the run's statement that the token counts
behind its cost total all arrived. ``_track2_task_runtime_error`` says in as
many words what carries it -- "that is carried instead by the task's own
``usage_complete``, which the aggregate folds into
``summary.cost.usage_complete``, so the run still refuses to publish a cost
figure it cannot stand behind while the grades it *can* stand behind survive"
-- and sixty lines from the fold, ``step8_grade`` warns on exactly that field
read strictly: ``row.get("usage_complete") is not True`` prints "this run's cost
total is no longer complete", and its comment points at the fold as the thing
that will carry the doubt.

The fold defaulted the missing key to ``True``. So a row that said nothing got
the same treatment as a row that said yes, the warning above fired while the
summary underneath it published *complete*, and the counters in the same loop
had already defaulted that row's absent token counts to ``0`` -- a total made
smaller by a row whose silence then certified it whole.

Every other reader of this key in the repository already reads it the other
way: ``core.tool_calling_judge`` folds a nested one with ``get(..., False)``,
``step2_run_inference`` and ``step6_report`` compare ``is True``, and
``step9_merge_shards`` refuses a shard whose aggregate is not a boolean at all.

The rows below are real ones, off a published shard of a real graded run, so
the arithmetic under test is the producer's and the row shape is the
producer's.
"""

import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import step8_grade
import step9_merge_shards
from step8_grade import (
    _compute_summary,
    _validate_grade_task_set,
    _validate_schema,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GRADES = REPO_ROOT / "data" / "grades"


def _published_shard() -> tuple[dict, dict]:
    """A published shard payload and the merged run it is a shard of.

    Picked by shape rather than by name so a reorganised ``data/grades`` moves
    the fixture instead of breaking it: any shard whose rows all carry a real
    boolean ``usage_complete`` and whose merged parent sits beside ``_shards``.
    """
    for path in sorted(GRADES.rglob("_shards/*/shard-*.json")):
        merged_path = path.parent.parent.parent / f"{path.parent.name}.json"
        if not merged_path.is_file():
            continue
        shard = json.loads(path.read_text("utf-8"))
        rows = shard.get("tasks")
        if not rows or any(type(r.get("usage_complete")) is not bool for r in rows):
            continue
        if type(shard.get("summary", {}).get("cost", {}).get("usage_complete")) is not bool:
            continue
        return shard, json.loads(merged_path.read_text("utf-8"))
    raise AssertionError(
        f"no published shard payload with boolean per-row usage flags under {GRADES}"
    )


@pytest.fixture(scope="module")
def published() -> tuple[dict, dict]:
    return _published_shard()


@pytest.fixture
def shard(published) -> dict:
    return copy.deepcopy(published[0])


@pytest.fixture
def expected_tasks(published) -> list[dict]:
    """The full run's task ids. A shard is an ordered subsequence of these."""
    return [{"task_id": t["task_id"]} for t in published[1]["tasks"]]


def _fold(shard: dict) -> dict:
    return _compute_summary(
        shard["tasks"],
        unpriced_models=shard["summary"]["cost"]["unpriced_models"],
    )


def _say(shard: dict, value) -> dict:
    """Make the first row answer ``value``; ``...`` removes the key entirely."""
    if value is ...:
        shard["tasks"][0].pop("usage_complete", None)
    else:
        shard["tasks"][0]["usage_complete"] = value
    return shard


# ── The fold, over real published rows ────────────────────────────────────


def test_the_published_rows_all_answer_and_the_run_is_complete(shard):
    """The control. Nothing about an ordinary run changes."""
    assert all(r["usage_complete"] is True for r in shard["tasks"])
    assert _fold(shard)["cost"]["usage_complete"] is True


def test_a_row_that_answers_no_makes_the_total_incomplete(shard):
    """The second control: the field works when a row uses it."""
    assert _fold(_say(shard, False))["cost"]["usage_complete"] is False


def test_a_row_that_says_nothing_no_longer_certifies_the_total(shard):
    assert _fold(_say(shard, ...))["cost"]["usage_complete"] is False


def test_saying_nothing_and_saying_no_now_reach_the_same_answer(shard, published):
    """These two differed only in whether the row spoke, and the published
    claim flipped between them."""
    silent = _fold(_say(copy.deepcopy(published[0]), ...))["cost"]["usage_complete"]
    denied = _fold(_say(shard, False))["cost"]["usage_complete"]
    assert silent is denied is False


@pytest.mark.parametrize("value", [None, 1, "true", "false", 0, [], {"ok": True}])
def test_a_value_that_is_not_this_producers_boolean_is_not_a_yes(shard, value):
    """``bool(...)`` would have read 1, "true" and {"ok": True} as yes.

    Both doors into the fold run the payload past the schema first, and the
    schema does type this field where it appears, so these should not arrive.
    The fold is also called on rows straight out of ``_build_grade_payload``
    that no schema has seen yet, and it is the thing whose answer gets
    published -- so when it is handed a value no producer here writes, the one
    safe reading is that nobody confirmed anything.
    """
    assert _fold(_say(shard, value))["cost"]["usage_complete"] is False


def test_one_silent_row_among_many_is_enough(shard):
    """The claim is about the whole total, so it takes every row to support."""
    assert len(shard["tasks"]) > 1
    _say(shard, ...)
    assert all(r.get("usage_complete") is True for r in shard["tasks"][1:])
    assert _fold(shard)["cost"]["usage_complete"] is False


def test_a_run_with_no_tasks_at_all_still_says_complete(shard):
    """Nothing was graded, so nothing is unknown. Unchanged, and deliberately:
    an empty chunk must not manufacture a doubt out of having done nothing."""
    empty = _compute_summary(
        [], unpriced_models=shard["summary"]["cost"]["unpriced_models"]
    )
    assert empty["cost"]["usage_complete"] is True


# ── Negative control: only the claim moves, never a number ────────────────


def test_the_silent_row_changes_the_claim_and_nothing_else(shard, published):
    """Money, tokens, latency, scores, sector rates, every counter: identical.

    The row's absent token counts already summed as 0 before this change and
    still do. What is new is that the total now says so.
    """
    denied = _fold(_say(copy.deepcopy(published[0]), False))
    silent = _fold(_say(shard, ...))
    assert denied == silent


def test_the_untouched_run_folds_to_exactly_what_it_published(shard):
    """The strongest guard against a retro-downgrade: recomputing a published
    shard's summary from its own rows reproduces the summary it shipped with."""
    assert _fold(shard)["cost"] == shard["summary"]["cost"]


# ── The resume guard now checks the rows it is about to fold ──────────────


def _resumable(shard: dict) -> dict:
    doc = copy.deepcopy(shard)
    doc["run_status"] = "partial"
    doc["summary"] = _compute_summary(
        doc["tasks"], unpriced_models=doc["summary"]["cost"]["unpriced_models"]
    )
    return doc


def test_an_ordinary_partial_payload_still_resumes(shard, expected_tasks):
    """The control. A payload written by this producer passes untouched."""
    got = _validate_grade_task_set(
        _resumable(shard), expected_tasks, require_complete=False
    )
    assert got == {t["task_id"] for t in shard["tasks"]}


def test_a_partial_payload_whose_earlier_chunk_answered_no_still_resumes(
    shard, expected_tasks
):
    """An incomplete bill is not a reason to refuse the resume -- the whole
    point of the aggregate check's comment. Only silence is refused."""
    doc = _resumable(_say(shard, False))
    assert doc["summary"]["cost"]["usage_complete"] is False
    assert _validate_grade_task_set(doc, expected_tasks, require_complete=False)


def test_a_silent_row_is_refused_by_name(shard, expected_tasks):
    doc = _resumable(_say(shard, ...))
    with pytest.raises(ValueError) as caught:
        _validate_grade_task_set(doc, expected_tasks, require_complete=False)
    assert "task usage flag is missing or not a boolean" in str(caught.value)
    assert doc["tasks"][0]["task_id"] in str(caught.value)


def test_a_truthy_ish_row_is_refused_too(shard, expected_tasks):
    """A wrong-typed value never gets as far as the new check.

    ``_validate_grade_task_set`` validates against the schema first, and the
    schema does declare this field boolean where it appears -- so a ``1`` is
    refused by type, one line into the function. What the schema cannot refuse
    is the key not being there at all, which it permits on purpose. The two
    checks divide the space between them, and both come back as ``ValueError``
    from this one call, which is all the caller needs.
    """
    doc = _resumable(_say(shard, 1))
    with pytest.raises(ValueError, match="is not of type 'boolean'"):
        _validate_grade_task_set(doc, expected_tasks, require_complete=False)


def test_the_aggregate_check_is_still_there(shard, expected_tasks):
    """Unchanged behaviour, kept under test because the row check sits beside
    it and an edit to either must not silently retire the other."""
    doc = _resumable(shard)
    doc["summary"]["cost"].pop("usage_complete")
    with pytest.raises(ValueError, match="aggregate usage flag"):
        _validate_grade_task_set(doc, expected_tasks, require_complete=False)


def test_the_aggregate_is_checked_before_the_rows(shard, expected_tasks):
    """A payload wrong in both places names the aggregate first: that is the
    field a reader of the file can see without walking every row."""
    doc = _resumable(_say(shard, ...))
    doc["summary"]["cost"]["usage_complete"] = None
    with pytest.raises(ValueError, match="aggregate usage flag"):
        _validate_grade_task_set(doc, expected_tasks, require_complete=False)


# ── The schema is right; the reader was wrong ─────────────────────────────


def test_the_schema_still_accepts_a_payload_with_a_silent_row(shard):
    """``usage_complete`` is deliberately not required, and must stay that way:
    ``schema_version`` spans 1.0 through 1.4, and 1.0 predates the field. Real
    1.0 payloads with silent rows sit in ``data/grades`` today. Requiring it
    would retroactively invalidate them, which is why the fix belongs in the
    reader -- silence is legal to write and must not be read as a promise.
    """
    doc = copy.deepcopy(shard)
    _say(doc, ...)
    doc["summary"] = _compute_summary(
        doc["tasks"], unpriced_models=doc["summary"]["cost"]["unpriced_models"]
    )
    _validate_schema(doc)


def _fold_leniently(rows: list[dict]) -> bool:
    """The rule as it stood: a row that says nothing is taken for a yes."""
    answer = True
    for row in rows:
        answer = answer and bool(row.get("usage_complete", True))
    return answer


def _fold_strictly(rows: list[dict]) -> bool:
    answer = True
    for row in rows:
        answer = answer and (row.get("usage_complete") is True)
    return answer


def test_the_legacy_payloads_this_protects_cannot_reach_the_fold():
    """Blast radius, measured rather than asserted.

    Every payload under ``data/grades`` is folded both ways. Where the two
    rules give the same answer nothing can move. Where they differ, the payload
    must be one that neither door into the fold will accept: the resume guard
    and ``step9_merge_shards`` both demand a boolean
    ``summary.cost.usage_complete`` before a single row is read, and the
    payloads that differ are pre-1.2 files that have no such field at all.

    A row that says ``False`` is not silent -- it answered -- so a run whose
    bill is honestly incomplete is unaffected and shows up on the unchanged
    side. This is the check that has to keep passing: an existing run must not
    start claiming something different because a reader was corrected.
    """
    changed = 0
    for path in GRADES.rglob("*.json"):
        try:
            doc = json.loads(path.read_text("utf-8"))
        except (ValueError, UnicodeDecodeError):
            continue
        rows = doc.get("tasks")
        if not isinstance(rows, list) or not rows:
            continue
        if not all(isinstance(row, dict) for row in rows):
            continue
        if _fold_leniently(rows) == _fold_strictly(rows):
            continue
        changed += 1
        aggregate = doc.get("summary", {}).get("cost", {}).get("usage_complete")
        assert type(aggregate) is not bool, (
            f"{path} folds to a different answer under the corrected rule and "
            "carries an aggregate that would let it through -- a published run "
            "would change what it claims, and the blast radius is no longer zero"
        )
    assert changed, "expected the legacy silent-row payloads to still be on disk"


# ── The merge path folds through the same function ────────────────────────


def test_the_shard_merger_folds_through_this_very_function():
    """``step9_merge_shards`` imports ``_compute_summary`` and recomputes the
    merged summary with it, so a shard produced by another job gets the same
    reading of silence as a resumed chunk does."""
    assert step9_merge_shards._compute_summary is step8_grade._compute_summary


def test_a_merged_run_is_incomplete_if_any_shards_row_was_silent(shard, published):
    """Two shards' worth of rows, one row silent, folded as the merger folds
    them. The merger separately ANDs each shard's aggregate, so this is the
    half that only the rows can carry."""
    other = copy.deepcopy(published[0])
    merged_rows = shard["tasks"] + _say(other, ...)["tasks"]
    unpriced = shard["summary"]["cost"]["unpriced_models"]
    assert _compute_summary(merged_rows, unpriced_models=unpriced)["cost"][
        "usage_complete"
    ] is False
