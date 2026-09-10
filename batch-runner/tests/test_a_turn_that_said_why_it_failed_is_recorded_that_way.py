"""Two of three failures said exactly why, and both were filed as "no reason".

Run `34528903950` ran the five pinned tasks and ended three of them. The log
says what ended each one:

    [1/5] 02aa1805-...-02dec146063a ... ⏳ rate_limited — attempt 2/3 in 60s...
    ✗ the Codex turn failed: stream disconnected before completion:
    Incomplete response returned, reason: content_filter

    [4/5] 3baa0009-...-4955cb328ff3 ... ⏳ rate_limited — attempt 2/3 in 60s...
    ✗ the Codex turn failed: stream disconnected before completion:
    Transport error: network error: error decoding response body

    [5/5] 0818571f-...-ced5ae44299e ... ⏳ rate_limited — attempt 3/3 in 120s...
    ✗ the Codex turn failed: stream disconnected before completion: Your
    requests to gpt-5.4 for gpt-5.4 in eastus2 have exceeded rate limit.

Only the third reached the record as what it was. The first two were both
written down as `turn_failed`, whose own definition beside
`RETRYABLE_INFRA_ERROR_CATEGORIES` is

    the turn failed and the text did not say why

and the text said why in both cases. One was the provider stopping the answer
over its content; the other was the connection dropping mid-answer. Those are
opposite kinds of thing -- one is the benchmark's result, one is the
environment's fault -- and the run published a single word covering both.

That is the same defect `rate_limited` was pulled out of, one release earlier,
for the same reason: a reader of the artifact could not tell a refusal from a
task the agent could not do.

Two things are deliberately *not* changed here.

`content_filtered` does not become retryable. It is not a failure of the run:
the model was asked a real question and what it wrote was refused. Attempting
it until something gets through would raise the score by changing the
question.

`transport_error` does not become retryable either -- not because it could not
be, but because the case for it is one observation wide. The turn was sent, so
it may have been billed and may have left files behind, which is why `timeout`
is excluded too. Naming it is what lets a later run count how often it happens
and decide on evidence.
"""

from __future__ import annotations

import pytest

from core.codex_runner import _turn_failure_category
from core.execution_errors import classify_execution_error
from step2_run_inference import RETRYABLE_INFRA_ERROR_CATEGORIES

#: The three sentences run `34528903950` actually ended tasks with, copied
#: from its job log rather than paraphrased.
THE_FILTERED_ANSWER = (
    "stream disconnected before completion: Incomplete response returned, "
    "reason: content_filter"
)
THE_DROPPED_CONNECTION = (
    "stream disconnected before completion: Transport error: network error: "
    "error decoding response body"
)
THE_REFUSAL = (
    "stream disconnected before completion: Your requests to gpt-5.4 for "
    "gpt-5.4 in eastus2 have exceeded rate limit."
)


# ── What the run's own sentences classify as ────────────────────────────────


def test_the_stopped_answer_is_recorded_as_the_filter_that_stopped_it():
    assert classify_execution_error(THE_FILTERED_ANSWER) == "content_filtered"
    assert _turn_failure_category(THE_FILTERED_ANSWER) == "content_filtered"


@pytest.mark.parametrize(
    "text",
    [
        # The other two shapes the same provider reports it in: the sentence
        # a filtered completion comes back with, and the structured field.
        "The response was filtered due to the prompt triggering Azure "
        "OpenAI's content management policy.",
        "{'content_filter_results': {'violence': {'filtered': True}}}",
    ],
)
def test_the_providers_other_wordings_are_the_same_finding(text):
    """Requiring exact punctuation must not cost the cases it was for."""
    assert classify_execution_error(text) == "content_filtered"


def test_the_dropped_connection_is_recorded_as_a_dropped_connection():
    assert classify_execution_error(THE_DROPPED_CONNECTION) == "transport_error"
    assert _turn_failure_category(THE_DROPPED_CONNECTION) == "transport_error"


def test_the_refusal_still_reads_as_a_refusal():
    """The category this file adds to must not disturb the one already there."""
    assert _turn_failure_category(THE_REFUSAL) == "rate_limited"


def test_neither_sentence_is_filed_under_no_reason_given():
    for sentence in (THE_FILTERED_ANSWER, THE_DROPPED_CONNECTION):
        assert _turn_failure_category(sentence) != "turn_failed"


def test_a_turn_that_really_did_not_say_why_still_says_so():
    """`turn_failed` keeps its meaning; it just stops covering these two."""
    assert _turn_failure_category("stream disconnected before completion") == (
        "turn_failed"
    )


# ── What must not follow from naming them ───────────────────────────────────


def test_a_filtered_answer_is_never_attempted_again():
    """Retrying this is not fixing a fault, it is asking a different question.

    The provider stopped the answer over what the answer said. A second
    attempt that gets through does not recover a lost result -- it replaces a
    benchmark outcome with a different one, and the success rate rises by the
    difference.
    """
    assert "content_filtered" not in RETRYABLE_INFRA_ERROR_CATEGORIES


def test_a_dropped_connection_is_not_attempted_again_yet():
    """One observation is not evidence, and the turn may already be paid for."""
    assert "transport_error" not in RETRYABLE_INFRA_ERROR_CATEGORIES


def test_only_the_two_categories_a_retry_can_fix_are_retryable():
    assert RETRYABLE_INFRA_ERROR_CATEGORIES == frozenset(
        {"rate_limited", "turn_start_failed"}
    )


# ── Not matching things that merely talk about filters ──────────────────────


@pytest.mark.parametrize(
    "text",
    [
        # A task whose subject is content filtering. The words are present;
        # the provider's phrasing is not.
        "ValueError: content filter threshold must be positive",
        "The deliverable describes the client's content filter policy.",
        "TypeError: unsupported operand type(s) for +: 'ContentFilter' and 'int'",
        # A perfectly ordinary professional deliverable to be asked for.
        "Draft a content management policy for the marketing team.",
    ],
)
def test_a_task_about_filtering_is_not_a_filtered_task(text):
    assert classify_execution_error(text) != "content_filtered"


@pytest.mark.parametrize(
    "text",
    [
        "ValueError: transport must be one of rail, road, sea",
        "The report compares transport error rates across three depots.",
    ],
)
def test_prose_about_transport_is_not_a_dropped_connection(text):
    """`transport error` as two ordinary English words is not the runtime's.

    The second case has no exception in it at all, so nothing narrows it
    before the markers are consulted -- which is exactly the shape a false
    positive would take, and it is the shape this test caught: the marker was
    written without its colon and this sentence classified as a dropped
    connection.
    """
    assert classify_execution_error(text) != "transport_error"


def test_a_refusal_that_also_mentions_a_filter_is_still_a_refusal():
    """Precedence is unchanged: rate is decided before anything else."""
    both = (
        "Your requests have exceeded rate limit. Incomplete response "
        "returned, reason: content_filter"
    )
    assert classify_execution_error(both) == "rate_limited"


# ── The categories that were already right stay right ───────────────────────


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("KeyError: 'Invoice Date'", "schema_error"),
        ("MemoryError: unable to allocate array", "out_of_memory"),
        ("TimeoutError: operation timed out", "timeout"),
        ("RuntimeError: boom from solution", "execution_error"),
        ("Code execution output was not valid UTF-8 text", "binary_decode_error"),
    ],
)
def test_the_existing_vocabulary_is_undisturbed(text, expected):
    assert classify_execution_error(text) == expected
