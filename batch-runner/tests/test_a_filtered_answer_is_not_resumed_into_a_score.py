"""A task the provider stopped for content is not run again into a score.

Resume rounds are the outer of two retry mechanisms in ``step2_run_inference``.
The inner one — ``run_with_infra_retries`` — asks again inside a single task,
and it has always been careful about *why* the task failed:
``RETRYABLE_INFRA_ERROR_CATEGORIES`` holds two categories and the comment above
it says of ``content_filtered`` that it "is not here, and must never be".

The outer one did not read that rule. ``_get_failed_task_ids`` gathered every
result whose *status* was in ``RETRIABLE_STATUSES`` and ran it again, and a
filtered task's status is ``"error"`` — so it matched, every round.

That is not a hypothetical shape. It is the shape run ``34540053904`` wrote
down, and this file reads it from the committed excerpt of that run rather than
constructing it, so the test cannot drift away from what the provider actually
returned.

Why it matters more than an ordinary retry bug: the provider read the answer
and stopped it. That is a result the benchmark is asking for. Asking again
until something gets through does not recover a lost outcome, it replaces one
outcome with a different one — and the difference lands in the score.

``execution.resume_max_rounds`` defaults to ``3``. Before this, the only thing
standing between a filtered task and three more attempts was the experiment
author remembering to write ``resume_max_rounds: 0``. exp034 and exp035 both
remembered. A file that omits the key did not, and said nothing about it.

Nothing here contacts a provider.
"""

import json
from pathlib import Path

import pytest

from step2_run_inference import (
    NON_RESUMABLE_ERROR_CATEGORIES,
    RETRIABLE_STATUSES,
    RETRYABLE_INFRA_ERROR_CATEGORIES,
    _get_failed_task_ids,
    infra_retry_category,
)

RUN_RECORD = (
    Path(__file__).parent / "fixtures" / "run_record" / "exp034_observability_excerpt.json"
)


def _recorded_results() -> list:
    """The verbatim ``status``/``observability`` rows run 34540053904 wrote."""
    return json.loads(RUN_RECORD.read_text(encoding="utf-8"))["results"]


def _only(results, category):
    return [
        r for r in results
        if (r.get("observability") or {}).get("error_category") == category
    ]


# ── the real row, read from the run that produced it ─────────────────────────


def test_the_recorded_filtered_task_matches_a_retriable_status(tmp_path):
    """The premise. Without this the rest of the file is guarding nothing."""
    filtered = _only(_recorded_results(), "content_filtered")
    assert filtered, "the excerpt no longer carries a content_filtered row"
    for row in filtered:
        assert row["status"] in RETRIABLE_STATUSES, (
            "a filtered task used to be gathered by status alone; if its status "
            "is no longer retriable, this guard is being kept for a shape that "
            "cannot occur and the reason should be rewritten, not the test"
        )


def test_the_recorded_filtered_task_is_not_gathered_for_resume():
    filtered = {r["task_id"] for r in _only(_recorded_results(), "content_filtered")}

    gathered = {r["task_id"] for r in _get_failed_task_ids({"results": _recorded_results()})}

    assert filtered and not (filtered & gathered)


def test_the_recorded_rate_limited_task_is_still_gathered():
    """The guard is about one category, not about failures in general.

    ``rate_limited`` is the failure the retry machinery was written for. If
    this stops being gathered, the fix has taken the resume rounds down with
    it.
    """
    limited = {r["task_id"] for r in _only(_recorded_results(), "rate_limited")}

    gathered = {r["task_id"] for r in _get_failed_task_ids({"results": _recorded_results()})}

    assert limited and limited <= gathered


def test_the_recorded_success_is_not_gathered():
    results = _recorded_results()
    succeeded = {r["task_id"] for r in results if r["status"] == "success"}

    gathered = {r["task_id"] for r in _get_failed_task_ids({"results": results})}

    assert succeeded and not (succeeded & gathered)


# ── what still resumes ───────────────────────────────────────────────────────


@pytest.mark.parametrize("status", sorted(RETRIABLE_STATUSES))
def test_every_retriable_status_still_resumes_without_a_category(status):
    """A result that says nothing about why it failed is still recovered.

    ``classify_execution_error`` returns ``None`` for text it does not
    recognise, and a ``pending`` task never ran at all. Refusing on absence
    would quietly turn resume off for the ordinary failures it exists for.
    """
    gathered = _get_failed_task_ids(
        {"results": [{"task_id": "t", "status": status, "error": "boom"}]}
    )

    assert [r["task_id"] for r in gathered] == ["t"]


def test_an_unrecognised_category_still_resumes():
    gathered = _get_failed_task_ids({
        "results": [{
            "task_id": "t",
            "status": "error",
            "observability": {"error_category": "something_new"},
        }]
    })

    assert [r["task_id"] for r in gathered] == ["t"]


@pytest.mark.parametrize("observability", [None, "", [], 0, {"error_category": None}])
def test_a_result_with_no_usable_observability_still_resumes(observability):
    gathered = _get_failed_task_ids({
        "results": [{"task_id": "t", "status": "error", "observability": observability}]
    })

    assert [r["task_id"] for r in gathered] == ["t"]


def test_the_gathered_row_keeps_the_fields_the_resume_round_reads():
    gathered = _get_failed_task_ids(
        {"results": [{"task_id": "t", "status": "qa_failed", "error": "why"}]}
    )

    assert gathered == [{"task_id": "t", "status": "qa_failed", "error": "why"}]


# ── what is refused ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("status", sorted(RETRIABLE_STATUSES))
def test_a_filtered_task_is_refused_whatever_its_retriable_status(status):
    gathered = _get_failed_task_ids({
        "results": [{
            "task_id": "t",
            "status": status,
            "observability": {"error_category": "content_filtered"},
        }]
    })

    assert gathered == []


def test_the_skip_is_announced(capsys):
    """A task silently dropped from a resume round is its own kind of wrong.

    The count printed by the resume round is the only place a reader learns
    how many tasks it is about to run, so a task that vanishes from it without
    a word looks like it was never failing.
    """
    _get_failed_task_ids({
        "results": [{
            "task_id": "11e1b169",
            "status": "error",
            "observability": {"error_category": "content_filtered"},
        }]
    })

    printed = capsys.readouterr().out
    assert "11e1b169" in printed and "content_filtered" in printed


def test_refusing_one_task_does_not_drop_the_rest():
    gathered = _get_failed_task_ids({
        "results": [
            {"task_id": "before", "status": "error", "error": "boom"},
            {
                "task_id": "filtered",
                "status": "error",
                "observability": {"error_category": "content_filtered"},
            },
            {"task_id": "after", "status": "error", "error": "boom"},
        ]
    })

    assert [r["task_id"] for r in gathered] == ["before", "after"]


# ── the two mechanisms agree about the category, and only about that ─────────


def test_content_filtered_is_refused_by_both_mechanisms():
    """The inner one refuses by omission; the outer one now refuses by name."""
    filtered = {
        "task_id": "t",
        "status": "error",
        "observability": {"error_category": "content_filtered"},
    }

    assert infra_retry_category(filtered) is None
    assert _get_failed_task_ids({"results": [filtered]}) == []


def test_the_two_sets_do_not_overlap():
    """A category in both would mean the run disagrees with itself."""
    assert not (NON_RESUMABLE_ERROR_CATEGORIES & RETRYABLE_INFRA_ERROR_CATEGORIES)


def test_only_the_provider_s_own_decision_is_refused():
    """Deliberately one category.

    Every other failure is mechanical — the connection broke, the runtime
    died, the deadline passed — and asking again is another attempt at the
    same question. Widening this set would stop recovering results that were
    genuinely lost, which is the opposite mistake and just as quiet.
    """
    assert NON_RESUMABLE_ERROR_CATEGORIES == frozenset({"content_filtered"})


def test_the_set_cannot_be_widened_at_runtime():
    assert isinstance(NON_RESUMABLE_ERROR_CATEGORIES, frozenset)
