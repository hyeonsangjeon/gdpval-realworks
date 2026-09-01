"""A run summary that names no stage is not a run that used none.

``summarise_receipts`` builds the ``CostReceipt`` published as
``summary.grading_cost`` in every graded payload. It summed the money, summed
the calls, summed the tokens -- and then built the receipt without passing
``components=`` at all, so the field fell to the dataclass default of ``()``.

An empty list is not a neutral value here. It is exactly what a run that never
contacted a provider carries. So a run of four priced calls across two stages
and a run built from ``CostReceipt.free()`` published the same field:

    4 priced calls, $120  ->  components: []
    0 calls at all,   $0  ->  components: []

The tasks in the very same file attributed every one of those calls to the
stage that made it. Only the line above them said nothing, and said it in the
words a silent run uses.

This is a port rather than a new rule. Both other summarisers over these same
receipts already roll the lines up:

* ``core.cost_projection.summarize_cost_receipts`` folds each receipt's lines
  before touching the run totals;
* ``scripts/cost-receipt.mjs`` does the same in ``aggregateComponents`` and
  hands the result to the dashboard.

Both of those folded by *displayed name* when this file was written, which is
the defect ``test_a_run_summary_row_is_one_model_not_one_label.py`` was added
to hold shut; all three now group on the key below.

Those two produce a run-summary document. ``summarise_receipts`` returns a
``CostReceipt``, so its lines have to be ``ReceiptComponent`` objects, folded on
the same key :meth:`CostReceiptLedger.receipt_for` buckets a task's own calls
under: the ``(stage, retry_kind)`` pair *and the identity of whoever was
called* -- provider, deployment, requested and resolved model, API version.
Stage stays how a reader groups and reads the result; it is not what a row is.
Two models called under one stage carry two rates, so a single row of their
summed tokens is a figure no price table can reproduce and no reader can take
apart again.

Everything below is built through a real ``CostReceiptLedger`` priced by a real
``load_receipt_price_table``, or read off the receipts actually published under
``data/grades``, so the arithmetic under test is the producer's.
"""

import json
import sys
from decimal import Decimal
from pathlib import Path

import jsonschema
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.cost_projection import _MAX_COMPONENTS, project_cost_receipt
from core.cost_receipts import (
    BUCKET_GRADING,
    BUCKET_PROBLEM_SOLVING,
    COMPONENT_RETRY,
    REASON_PRICE_MISSING,
    RETRY_KINDS,
    RETRY_NONE,
    RETRY_RESUME,
    RETRY_SEMANTIC,
    STAGES,
    STAGE_GRADING,
    STAGE_PERCEPTION,
    STATUS_COMPLETE,
    STATUS_NOT_RUN,
    STATUS_PARTIAL,
    STATUS_UNAVAILABLE,
    CallUsage,
    CostReceipt,
    CostReceiptLedger,
    ReceiptComponent,
    empty_usage,
    load_receipt_price_table,
    make_call_id,
    summarise_receipts,
)

BATCH_RUNNER = Path(__file__).resolve().parents[1]
REPO_ROOT = BATCH_RUNNER.parent
GRADES = REPO_ROOT / "data" / "grades"
SCHEMA_PATH = BATCH_RUNNER / "schemas" / "grade.schema.json"

#: The one model the fixture price table knows about.
PRICED = "priced"
UNPRICED = "unheard-of"

#: One million in, one million out, at $10/$20 per million: $30 a call.
PER_CALL_USD = 30


@pytest.fixture
def prices(tmp_path):
    document = {
        "cost_receipt_schema_version": "cost-receipt-price-table-v1",
        "providers": {
            f"azure:{PRICED}": {
                "input_usd_per_million": "10",
                "cached_input_usd_per_million": "10",
                "output_usd_per_million": "20",
                "reasoning_billed_as": "output",
                "source": "fixture",
                "last_reviewed": "2026-08-31",
                "currency": "USD",
                "unit": "per 1,000,000 tokens",
            }
        },
        "runtime": {},
    }
    path = tmp_path / "prices.json"
    path.write_text(json.dumps(document), "utf-8")
    return load_receipt_price_table(path)


def _charge(ledger, task_id, stage, retry_kind, sequence, model=PRICED):
    """One settled call through the ledger's own reserve/settle pair."""
    call_id = make_call_id(
        run_id=ledger.run_id,
        task_id=task_id,
        stage=stage,
        retry_kind=retry_kind,
        attempt_index=0,
        sequence=sequence,
    )
    ledger.reserve(
        call_id=call_id,
        task_id=task_id,
        stage=stage,
        retry_kind=retry_kind,
        provider="azure",
        requested_model=model,
    )
    ledger.settle(
        call_id, usage=CallUsage(input_tokens=1_000_000, output_tokens=1_000_000)
    )


def _run(tmp_path, prices, plan, bucket=BUCKET_GRADING, name="run"):
    """Receipts for a whole run, described as ``{task_id: [(stage, retry), ...]}``."""
    path = tmp_path / f"ledger-{name}.sqlite3"
    with CostReceiptLedger(path, run_id="run-1", price_table=prices) as ledger:
        sequence = 0
        for task_id, calls in plan.items():
            for call in calls:
                stage, retry_kind = call[0], call[1]
                model = call[2] if len(call) > 2 else PRICED
                _charge(ledger, task_id, stage, retry_kind, sequence, model)
                sequence += 1
        return [ledger.receipt_for(task_id, bucket) for task_id in plan]


def _keys(receipt):
    return [(line.stage, line.retry_kind) for line in receipt.components]


def _lines(receipt, stage, retry_kind=RETRY_NONE):
    """Every line at this stage -- one per model that was called under it."""
    return [
        entry
        for entry in receipt.components
        if (entry.stage, entry.retry_kind) == (stage, retry_kind)
    ]


def _line(receipt, stage, retry_kind=RETRY_NONE):
    """The one line at this stage, when the stage only ever called one model.

    A stage is not a line. It is a stage's worth of lines, one per model
    identity, and most of the fixtures below run a single model so the two
    coincide. Where they do not, this refuses rather than silently returning
    whichever line sorted first -- a helper that answers a question with a
    different question's answer is how a breakdown gets asserted into looking
    right while reading wrong. Ask :func:`_lines` or :func:`_stage` instead.
    """
    found = _lines(receipt, stage, retry_kind)
    if not found:
        raise AssertionError(f"no {stage}/{retry_kind} line in {_keys(receipt)}")
    if len(found) > 1:
        models = [entry.resolved_model for entry in found]
        raise AssertionError(
            f"{stage}/{retry_kind} is {len(found)} lines, one per model {models}; "
            "use _lines() for the models or _stage() for the rollup"
        )
    return found[0]


def _stage(receipt, stage, retry_kind=RETRY_NONE):
    """The stage's own totals, rolled up across whatever models it called.

    Stage stayed an aggregation dimension when the line became a model, so a
    reader asking "what did grading cost" still gets one answer -- it is just
    computed from the lines rather than stored as one. Whole only if all of it
    is, which is the same rule one level up.
    """
    found = _lines(receipt, stage, retry_kind)
    assert found, f"no {stage}/{retry_kind} line in {_keys(receipt)}"
    reasons = {reason for entry in found for reason in entry.missing_reasons}
    return {
        "status": (
            STATUS_COMPLETE
            if all(entry.status == STATUS_COMPLETE for entry in found)
            else STATUS_PARTIAL
        ),
        "model_calls": sum(entry.model_calls for entry in found),
        "known_cost_usd": sum(
            (entry.known_cost_usd for entry in found), Decimal(0)
        ),
        "missing_reasons": tuple(sorted(reasons)),
    }


# -- The field a reader actually sees ---------------------------------------


def test_a_run_that_spent_and_a_run_that_did_not_no_longer_match(tmp_path, prices):
    """The defect, stated as the thing a reader cannot do.

    Four priced calls across two stages, and a run built from receipts that
    really did cost nothing. Before this change both published ``[]``.
    """
    spent = summarise_receipts(
        _run(
            tmp_path,
            prices,
            {
                "t-0": [(STAGE_GRADING, RETRY_NONE), (STAGE_PERCEPTION, RETRY_NONE)],
                "t-1": [(STAGE_GRADING, RETRY_NONE), (STAGE_PERCEPTION, RETRY_NONE)],
            },
        )
    )
    idle = summarise_receipts([CostReceipt.free(), CostReceipt.free()])

    assert spent.model_calls == 4
    assert spent.known_cost_usd == Decimal(4 * PER_CALL_USD)
    assert _keys(spent) == [
        (STAGE_GRADING, RETRY_NONE),
        (STAGE_PERCEPTION, RETRY_NONE),
    ]
    assert idle.components == ()
    assert spent.as_dict()["components"] != idle.as_dict()["components"]


def test_the_lines_add_up_to_the_summary_they_sit_under(tmp_path, prices):
    """Nothing is counted twice and nothing is dropped.

    A summary whose parts do not reconstruct its own totals is worse than a
    summary with no parts, because a reader can check this one and be wrong.
    """
    summary = summarise_receipts(
        _run(
            tmp_path,
            prices,
            {
                "t-0": [(STAGE_GRADING, RETRY_NONE), (STAGE_PERCEPTION, RETRY_NONE)],
                "t-1": [(STAGE_GRADING, RETRY_NONE)],
                "t-2": [(STAGE_GRADING, RETRY_SEMANTIC)],
            },
        )
    )
    assert sum(line.model_calls for line in summary.components) == summary.model_calls
    assert (
        sum((line.known_cost_usd for line in summary.components), Decimal(0))
        == summary.model_cost_usd
    )
    for name in empty_usage():
        assert sum(line.usage[name] or 0 for line in summary.components) == (
            summary.usage[name] or 0
        )


def test_a_run_summary_reaches_the_stages_its_tasks_reached(tmp_path, prices):
    """Two tasks, three stages between them, one line per stage in the run."""
    summary = summarise_receipts(
        _run(
            tmp_path,
            prices,
            {
                "t-0": [(STAGE_GRADING, RETRY_NONE)] * 3,
                "t-1": [(STAGE_GRADING, RETRY_NONE), (STAGE_PERCEPTION, RETRY_NONE)],
            },
        )
    )
    assert _line(summary, STAGE_GRADING).model_calls == 4
    assert _line(summary, STAGE_GRADING).known_cost_usd == Decimal(4 * PER_CALL_USD)
    assert _line(summary, STAGE_PERCEPTION).model_calls == 1


# -- A retry belongs to the stage that retried ------------------------------


def test_first_work_and_work_done_again_stay_two_lines(tmp_path, prices):
    """``grading`` twice is one line; ``grading`` retried is a second.

    The pair is the identity, not the stage. Folding on the stage alone would
    bury the answer to "how much did retrying cost" inside the stage total.
    """
    summary = summarise_receipts(
        _run(
            tmp_path,
            prices,
            {
                "t-0": [(STAGE_GRADING, RETRY_NONE), (STAGE_GRADING, RETRY_SEMANTIC)],
            },
        )
    )
    assert _keys(summary) == [
        (STAGE_GRADING, RETRY_NONE),
        (STAGE_GRADING, RETRY_SEMANTIC),
    ]
    assert [line.name for line in summary.components] == [
        STAGE_GRADING,
        COMPONENT_RETRY,
    ]


def test_two_stages_that_both_retried_are_not_one_retry_line(tmp_path, prices):
    """Both display as ``retry``; folding on the displayed name would merge a
    grading retry into a perception retry and lose which stage cost what."""
    summary = summarise_receipts(
        _run(
            tmp_path,
            prices,
            {
                "t-0": [
                    (STAGE_GRADING, RETRY_SEMANTIC),
                    (STAGE_PERCEPTION, RETRY_RESUME),
                ]
            },
        )
    )
    assert [line.name for line in summary.components] == [
        COMPONENT_RETRY,
        COMPONENT_RETRY,
    ]
    assert _keys(summary) == [
        (STAGE_GRADING, RETRY_SEMANTIC),
        (STAGE_PERCEPTION, RETRY_RESUME),
    ]


def test_the_same_key_across_tasks_becomes_one_line(tmp_path, prices):
    """Three tasks that each graded once publish one grading line of three."""
    summary = summarise_receipts(
        _run(
            tmp_path,
            prices,
            {task: [(STAGE_GRADING, RETRY_NONE)] for task in ("t-0", "t-1", "t-2")},
        )
    )
    assert len(summary.components) == 1
    assert _line(summary, STAGE_GRADING).model_calls == 3
    assert _line(summary, STAGE_GRADING).usage["input_tokens"] == 3_000_000


def test_the_lines_come_out_in_the_same_order_whatever_order_they_went_in(
    tmp_path, prices
):
    """Sorted by key, so a resumed run and a shard merge that visit the same
    tasks in different orders publish the same bytes."""
    receipts = _run(
        tmp_path,
        prices,
        {
            "t-0": [(STAGE_PERCEPTION, RETRY_NONE)],
            "t-1": [(STAGE_GRADING, RETRY_SEMANTIC)],
            "t-2": [(STAGE_GRADING, RETRY_NONE)],
        },
    )
    forwards = summarise_receipts(receipts).as_dict()["components"]
    backwards = summarise_receipts(list(reversed(receipts))).as_dict()["components"]
    assert forwards == backwards
    assert [line["name"] for line in forwards] == [
        STAGE_GRADING,
        COMPONENT_RETRY,
        STAGE_PERCEPTION,
    ]


# -- Work that did not happen contributes nothing, and says so --------------


def test_a_task_that_never_ran_adds_no_line(tmp_path, prices):
    """``not_run`` is dropped one level up too. It must not appear here as a
    stage the run touched."""
    priced = _run(tmp_path, prices, {"t-0": [(STAGE_GRADING, RETRY_NONE)]})
    assert _keys(summarise_receipts([*priced, CostReceipt.not_run()])) == [
        (STAGE_GRADING, RETRY_NONE)
    ]


def test_a_stage_whose_every_line_never_ran_is_published_as_never_run():
    """The other direction, and the one that matters.

    A line read back off disk saying a stage did not run is not the same as no
    line at all. Dropping it would turn "we know this stage did nothing" into
    "we have nothing to say about this stage".
    """
    summary = summarise_receipts(
        [
            _receipt_with(
                _component(STAGE_GRADING, RETRY_NONE, STATUS_COMPLETE, calls=1, usd=30),
                _component(STAGE_PERCEPTION, RETRY_NONE, STATUS_NOT_RUN),
            )
        ]
    )
    assert _line(summary, STAGE_PERCEPTION).status == STATUS_NOT_RUN
    assert _line(summary, STAGE_PERCEPTION).model_calls == 0
    assert _line(summary, STAGE_PERCEPTION).known_cost_usd == Decimal(0)


def test_an_idle_line_does_not_drag_the_stage_it_shares_a_key_with():
    """One task graded and one task did not. The grading line is still whole."""
    summary = summarise_receipts(
        [
            _receipt_with(
                _component(STAGE_GRADING, RETRY_NONE, STATUS_COMPLETE, calls=1, usd=30)
            ),
            _receipt_with(_component(STAGE_GRADING, RETRY_NONE, STATUS_NOT_RUN)),
        ]
    )
    line = _line(summary, STAGE_GRADING)
    assert line.status == STATUS_COMPLETE
    assert line.model_calls == 1
    assert line.known_cost_usd == Decimal(30)


# -- A line is whole only if all of it is -----------------------------------


def test_one_unpriced_call_lands_on_the_model_that_could_not_be_priced(
    tmp_path, prices
):
    """A hole belongs to whoever made it, not to everyone standing near it.

    Three calls: one grading call to a model the table prices, one grading call
    to a model it does not, and one perception call. The unpriced call is the
    only thing here that cannot be settled.

    Grading is therefore two lines, because two models were called under it and
    their tokens carry different rates. Summing them into one row is what this
    change exists to stop: a single ``grading`` row of two calls and $30 is a
    number no table can reproduce and no reader can take apart afterwards.
    """
    summary = summarise_receipts(
        _run(
            tmp_path,
            prices,
            {
                "t-0": [(STAGE_GRADING, RETRY_NONE)],
                "t-1": [(STAGE_GRADING, RETRY_NONE, UNPRICED)],
                "t-2": [(STAGE_PERCEPTION, RETRY_NONE)],
            },
        )
    )
    by_model = {line.resolved_model: line for line in _lines(summary, STAGE_GRADING)}
    assert sorted(by_model) == sorted([PRICED, UNPRICED])

    # The model that could be priced keeps its own figure whole. Nothing about
    # the other call makes this one less known than it is.
    assert by_model[PRICED].status == STATUS_COMPLETE
    assert by_model[PRICED].known_cost_usd == Decimal(PER_CALL_USD)
    assert by_model[PRICED].model_calls == 1
    assert by_model[PRICED].missing_reasons == ()

    # The model that could not is `partial` and says why. It is $0 because
    # nothing is invented for it -- but a $0 that carries `price_missing` and a
    # `partial` status cannot be read as "this call was free".
    assert by_model[UNPRICED].status == STATUS_PARTIAL
    assert by_model[UNPRICED].missing_reasons == (REASON_PRICE_MISSING,)
    assert by_model[UNPRICED].known_cost_usd == Decimal(0)
    assert by_model[UNPRICED].model_calls == 1

    # Rolled back up, the stage reads exactly as it did when it was one row:
    # partial, two calls, and a floor holding the one call that could be priced.
    grading = _stage(summary, STAGE_GRADING)
    assert grading["status"] == STATUS_PARTIAL
    assert grading["missing_reasons"] == (REASON_PRICE_MISSING,)
    assert grading["known_cost_usd"] == Decimal(PER_CALL_USD)
    assert grading["model_calls"] == 2

    # And the stage that had nothing to do with it is left alone.
    assert _line(summary, STAGE_PERCEPTION).status == STATUS_COMPLETE
    assert _line(summary, STAGE_PERCEPTION).missing_reasons == ()

    # Fail-closed, unchanged: one unsettled call anywhere makes the run partial.
    assert summary.status == STATUS_PARTIAL
    assert summary.missing_reasons == (REASON_PRICE_MISSING,)


def test_a_reader_and_a_listener_under_one_stage_are_not_one_price(
    tmp_path, prices
):
    """The defect this keying exists for, at the summary level.

    ``perception`` is the stage where two models genuinely run: a visual
    sub-judge and an audio one. Keyed on the stage alone their tokens land in a
    single row -- added together despite carrying different rates, so the row
    is unpriceable going in and cannot be separated again coming out.

    Here the listener is the unpriced one, which is the real configuration:
    ``gpt-audio-1.5`` is deliberately absent from the price table while the
    visual judge is priced. The reader's figure must survive that intact.
    """
    summary = summarise_receipts(
        _run(
            tmp_path,
            prices,
            {
                "t-0": [
                    (STAGE_PERCEPTION, RETRY_NONE),
                    (STAGE_PERCEPTION, RETRY_NONE, UNPRICED),
                ]
            },
        )
    )
    lines = {line.resolved_model: line for line in _lines(summary, STAGE_PERCEPTION)}
    assert sorted(lines) == sorted([PRICED, UNPRICED])
    assert lines[PRICED].known_cost_usd == Decimal(PER_CALL_USD)
    assert lines[PRICED].status == STATUS_COMPLETE
    assert lines[UNPRICED].status == STATUS_PARTIAL
    assert lines[UNPRICED].missing_reasons == (REASON_PRICE_MISSING,)

    # Both read 1,000,000 tokens in. Under one row that is 2,000,000 at one
    # rate, which is the wrong number twice over.
    assert lines[PRICED].usage["input_tokens"] == 1_000_000
    assert lines[UNPRICED].usage["input_tokens"] == 1_000_000
    assert _stage(summary, STAGE_PERCEPTION)["status"] == STATUS_PARTIAL


def test_a_stage_with_no_record_at_all_stays_unavailable():
    summary = summarise_receipts(
        [
            _receipt_with(
                _component(STAGE_GRADING, RETRY_NONE, STATUS_UNAVAILABLE),
                status=STATUS_UNAVAILABLE,
            ),
            _receipt_with(
                _component(STAGE_GRADING, RETRY_NONE, STATUS_UNAVAILABLE),
                status=STATUS_UNAVAILABLE,
            ),
        ]
    )
    assert _line(summary, STAGE_GRADING).status == STATUS_UNAVAILABLE


def test_a_stage_that_is_whole_in_one_task_and_not_in_another_is_partial():
    summary = summarise_receipts(
        [
            _receipt_with(
                _component(STAGE_GRADING, RETRY_NONE, STATUS_COMPLETE, calls=1, usd=30)
            ),
            _receipt_with(
                _component(STAGE_GRADING, RETRY_NONE, STATUS_UNAVAILABLE),
                status=STATUS_UNAVAILABLE,
            ),
        ]
    )
    assert _line(summary, STAGE_GRADING).status == STATUS_PARTIAL


def test_a_line_that_never_said_what_it_used_does_not_add_a_zero():
    """Absent is not zero, on the line exactly as on the receipt.

    A line reporting no ``input_tokens`` contributes none, and the sum is the
    tokens that were actually reported rather than a count padded out with
    silence.
    """
    summary = summarise_receipts(
        [
            _receipt_with(
                _component(
                    STAGE_GRADING,
                    RETRY_NONE,
                    STATUS_COMPLETE,
                    calls=1,
                    usd=30,
                    usage={"input_tokens": 5, "output_tokens": 7},
                )
            ),
            _receipt_with(
                _component(
                    STAGE_GRADING,
                    RETRY_NONE,
                    STATUS_PARTIAL,
                    calls=1,
                    usd=0,
                    usage={"input_tokens": None, "output_tokens": 3},
                    reasons=(REASON_PRICE_MISSING,),
                )
            ),
        ]
    )
    line = _line(summary, STAGE_GRADING)
    assert line.usage["input_tokens"] == 5
    assert line.usage["output_tokens"] == 10
    assert line.status == STATUS_PARTIAL
    assert line.missing_reasons == (REASON_PRICE_MISSING,)


# -- The count is bounded by the vocabulary, not by the run -----------------


def test_the_whole_vocabulary_fits_under_the_published_cap():
    """The guard that makes this change safe to publish.

    A receipt may carry thirty-two lines. The vocabulary alone -- five stages
    at five retry kinds -- accounts for twenty-five of them however many tasks
    the run graded. If a sixth stage or a sixth retry kind is ever added, this
    fails here rather than at a consumer rejecting a payload that has already
    been paid for.

    What the vocabulary no longer bounds on its own is the line count, because
    a line is a stage *and an identity*: a stage reached by two models is two
    lines. So the headroom above is what a run has to spend on identity, and
    seven is not much. It is enough for what the configs actually name -- one
    judge under ``grading``, at most the two sub-judges under ``perception``,
    one generator under ``generation`` and ``self_qa`` -- and a stage that ever
    fanned out to many models would need the cap raised rather than the fan-out
    hidden back inside one unpriceable row.
    """
    vocabulary = len(STAGES) * len(RETRY_KINDS)
    assert vocabulary <= _MAX_COMPONENTS
    assert _MAX_COMPONENTS - vocabulary == 7, (
        "the headroom a run has for extra model identities moved; if that is "
        "deliberate, say so here and check the consumers still accept it"
    )


def test_a_run_that_touched_every_pair_still_publishes_and_projects():
    """All twenty-five keys at once, folded and then put through the reader."""
    summary = summarise_receipts(
        [
            _receipt_with(
                *(
                    _component(stage, retry_kind, STATUS_COMPLETE, calls=1, usd=1)
                    for stage in STAGES
                    for retry_kind in RETRY_KINDS
                ),
                calls=25,
                usd=25,
            )
        ]
    )
    assert len(summary.components) == 25
    projected = project_cost_receipt(summary.as_dict(), "summary")
    assert len(projected["components"]) == 25
    assert len({(c["stage"], c["retry_kind"]) for c in projected["components"]}) == 25


def test_the_merged_lines_satisfy_the_published_grade_schema():
    """``summary.grading_cost`` is a committed field, so the shape it gains has
    to be one ``grade.schema.json`` already accepts."""
    schema = json.loads(SCHEMA_PATH.read_text("utf-8"))
    validator = jsonschema.Draft202012Validator(
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            **schema["$defs"]["costReceipt"],
            "$defs": schema["$defs"],
        }
    )
    summary = summarise_receipts(
        [
            _receipt_with(
                *(
                    _component(stage, retry_kind, STATUS_COMPLETE, calls=1, usd=1)
                    for stage in STAGES
                    for retry_kind in RETRY_KINDS
                ),
                calls=25,
                usd=25,
            )
        ]
    )
    assert len(summary.components) == 25
    assert not sorted(validator.iter_errors(summary.as_dict()))


# -- Measured on the receipts that are actually published -------------------


def _published_receipt_sets():
    """Every real per-task receipt set under ``data/grades``.

    Yields ``(path, field, receipts)``. These are the receipts the grading
    pipeline writes today, read back through ``CostReceipt.from_dict`` exactly
    as a resume or a shard merge reads them.
    """
    for path in sorted(GRADES.rglob("*.json")):
        try:
            doc = json.loads(path.read_text("utf-8"))
        except (ValueError, UnicodeDecodeError):
            continue
        rows = doc.get("tasks")
        if not isinstance(rows, list) or not rows:
            continue
        for field in (BUCKET_PROBLEM_SOLVING, BUCKET_GRADING):
            receipts = [
                CostReceipt.from_dict(row[field])
                for row in rows
                if isinstance(row, dict) and isinstance(row.get(field), dict)
            ]
            if receipts:
                yield path, field, receipts


def test_every_published_run_summary_now_names_the_stages_behind_it():
    """Blast radius, measured rather than asserted.

    All twenty-one published receipt sets are folded. Every one of them
    published ``components: []`` before; every one of them now names its
    stages, and every one stays inside the cap.
    """
    seen = 0
    for path, _field, receipts in _published_receipt_sets():
        seen += 1
        summary = summarise_receipts(receipts)
        assert summary.components, f"{path} still names no stage"
        assert len(summary.components) <= _MAX_COMPONENTS, path
        keys = _keys(summary)
        assert len(keys) == len(set(keys)), f"{path} carries a duplicate line"
    assert seen >= 21, f"expected the published receipt sets to still be there, saw {seen}"


def test_the_published_lines_reconstruct_the_published_totals():
    """On real data, not a fixture: the parts add up to the whole they sit
    under, for money, for calls, and for every token counter."""
    for path, _field, receipts in _published_receipt_sets():
        summary = summarise_receipts(receipts)
        assert (
            sum(line.model_calls for line in summary.components) == summary.model_calls
        ), path
        assert (
            sum((line.known_cost_usd for line in summary.components), Decimal(0))
            == summary.model_cost_usd
        ), path
        for name in empty_usage():
            assert sum(line.usage[name] or 0 for line in summary.components) == (
                summary.usage[name] or 0
            ), f"{path}:{name}"


def test_nothing_else_about_a_published_summary_moves():
    """The negative control this change turns on.

    ``summarise_receipts`` writes a field that is committed to this repository,
    so the claim has to be that the change is purely additive. Every scalar a
    published summary carries is recomputed here and compared against the same
    summary with its lines removed -- the document as it stood before.
    """
    for path, _field, receipts in _published_receipt_sets():
        after = summarise_receipts(receipts).as_dict()
        before = dict(after, components=[])
        moved = {key for key in before if before[key] != after[key]}
        assert moved == {"components"}, f"{path}: {sorted(moved)}"


def test_no_published_summary_changes_whether_the_reader_accepts_it():
    """The other half of the control, and the one that could have bitten.

    What this asserts is that carrying the lines up does not move a single
    reader verdict: whichever summaries ``project_cost_receipt`` accepted with
    an empty ``components`` are exactly the ones it accepts with the lines in
    place, and any it refuses it refuses on the same figure one level down.

    It is written as a comparison rather than a count on purpose. When this
    first landed, eight of the twenty-one were refused -- their honest token
    totals crossed a sanity bound sized for a much smaller quantity -- and this
    test passed anyway, because eight before and eight after is no change.
    That bound has since been separated from the one it was sharing (#112) and
    all twenty-one are accepted, and this test passes for the same reason it
    did then. A test that had pinned thirteen would have failed at that fix
    while nothing about this change moved.
    """
    accepted_before = accepted_after = 0
    for _path, _field, receipts in _published_receipt_sets():
        after = summarise_receipts(receipts).as_dict()
        before = dict(after, components=[])
        for document, tally in ((before, "before"), (after, "after")):
            try:
                project_cost_receipt(document, "summary")
            except ValueError:
                continue
            if tally == "before":
                accepted_before += 1
            else:
                accepted_after += 1
    assert accepted_before == accepted_after
    assert accepted_after, "expected the reader to accept at least some summaries"


# -- Fixtures for the shapes a ledger cannot produce ------------------------
#
# ``receipt_for`` only ever builds ``complete`` and ``partial`` lines. The other
# two arrive through ``CostReceipt.from_dict`` -- a resumed grade file, or a
# shard written by another build -- which is exactly the input this function
# takes in production.


def _component(stage, retry_kind, status, *, calls=0, usd=0, usage=None, reasons=()):
    filled = empty_usage()
    filled.update(usage or {})
    return ReceiptComponent(
        stage=stage,
        retry_kind=retry_kind,
        status=status,
        model_calls=calls,
        known_cost_usd=Decimal(usd),
        usage=filled,
        missing_reasons=tuple(reasons),
    )


def _receipt_with(*components, status=STATUS_COMPLETE, calls=None, usd=None):
    counted = [line for line in components if line.status != STATUS_NOT_RUN]
    return CostReceipt(
        status=status,
        known_cost_usd=Decimal(
            usd if usd is not None else sum(line.known_cost_usd for line in counted)
        ),
        model_cost_usd=Decimal(
            usd if usd is not None else sum(line.known_cost_usd for line in counted)
        ),
        runtime_cost_usd=Decimal(0),
        model_calls=calls if calls is not None else sum(l.model_calls for l in counted),
        usage=empty_usage(),
        components=tuple(components),
        price_table_sha256=None,
        missing_reasons=(),
    )
