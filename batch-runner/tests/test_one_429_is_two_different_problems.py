"""One 429 is two different problems, and the run could not tell them apart.

Azure answers both of its rate refusals with the same status, and the runner
files both under the same category. That is correct about what to *do* -- both
are retried the same way -- and useless about what to *change*:

  * a **token** refusal says a turn reserved more than the deployment allows at
    once, and is answered by asking for less in a turn;
  * a **call** refusal says turns arrived faster than the deployment allows, and
    is answered by asking less often.

Doing the second thing about the first problem costs a run and fixes nothing.

The distinction exists in exactly one place: a sentence on ``TurnError.message``
that also names the deployment. ``core.public_error.public_task_error`` is
documented to return "an endpoint- and message-free public error identity", so
that sentence is destroyed on the way to the artifact -- deliberately. These
tests pin the way through: read the kind where the sentence still exists,
publish one word from a closed set, and let the allow-list in step 2 check
membership so no provider-chosen string can follow it out.

``exp034``'s eight failures carry ``{"items_seen": N}`` and nothing else, so
every ``rate_limited`` label this project holds was made by prose matching, and
none of it recorded which kind. That is the gap these tests close.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.codex_runner import (  # noqa: E402
    RATE_LIMIT_KINDS,
    CodexRunOutcome,
    _rate_limit_kind,
)
from core.execution_errors import classify_execution_error  # noqa: E402
from step2_run_inference import _bounded_codex_diagnostics  # noqa: E402


#: The two wordings the distinction turns on. Azure's own, with the deployment
#: name left in, because that is what the runner actually receives and because
#: a test that strips it first would not prove the name is withheld later.
TOKEN_REFUSAL = (
    "stream disconnected before completion: Requests to the "
    "ChatCompletions_Create Operation under Azure OpenAI API version "
    "2024-12-01-preview have exceeded token rate limit of your current "
    "OpenAI S0 pricing tier."
)
CALL_REFUSAL = (
    "stream disconnected before completion: Requests to the "
    "ChatCompletions_Create Operation under Azure OpenAI API version "
    "2024-12-01-preview have exceeded call rate limit of your current "
    "OpenAI S0 pricing tier."
)


# ── The two refusals stop being one refusal ─────────────────────────────────


def test_a_token_refusal_is_named_a_token_refusal():
    assert _rate_limit_kind(TOKEN_REFUSAL) == "token"


def test_a_call_refusal_is_named_a_call_refusal():
    assert _rate_limit_kind(CALL_REFUSAL) == "request"


def test_the_two_refusals_do_not_read_the_same():
    # The point of the field. If this ever passes with both equal, the field
    # has stopped earning its place.
    assert _rate_limit_kind(TOKEN_REFUSAL) != _rate_limit_kind(CALL_REFUSAL)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Rate limit reached: 60000 tokens per min", "token"),
        ("Rate limit reached: 60 requests per min", "request"),
        ("have exceeded token rate limit of your current tier", "token"),
        ("have exceeded call rate limit of your current tier", "request"),
    ],
)
def test_the_providers_other_wordings_reach_the_same_two_answers(text, expected):
    assert _rate_limit_kind(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "exceeded your tokens per minute limit",
        "exceeded your requests per minute limit",
    ],
)
def test_a_per_minute_phrase_alone_is_not_yet_a_rate_refusal(text):
    """The boundary belongs to ``classify_execution_error``, not to this.

    Neither sentence contains any of ``_RATE_LIMIT_MARKERS``, so the project's
    one rule for *was this a rate refusal* answers ``execution_error`` and this
    matcher is never consulted. Recorded rather than fixed: widening those
    markers widens what gets **retried**, and ``core.execution_errors`` is
    explicit that mistaking a real defect for a transient one is how a
    deterministic failure gets attempted three times. A diagnostic field is not
    a reason to change retry behaviour.

    If a deployment is ever seen refusing in exactly these words, the fix is in
    ``_RATE_LIMIT_MARKERS`` and this test is what will have to change with it.
    """
    assert classify_execution_error(text) == "execution_error"
    assert _rate_limit_kind(text) is None


# ── Not knowing is said out loud, and is not the same as not happening ──────


def test_a_refusal_that_names_neither_kind_is_unattributed():
    # What exp034 would have produced, had the field existed then: refused for
    # rate, in wording these markers do not cover. `unattributed` eight times
    # is a finding about the markers; `None` eight times would hide it.
    assert _rate_limit_kind("Error code: 429 - too many requests") == (
        "unattributed"
    )


def test_a_failure_that_is_not_a_rate_refusal_reads_as_none():
    assert _rate_limit_kind("the model produced no answer") is None


def test_a_content_filter_is_not_given_a_rate_limit_kind():
    # A filtered answer is a benchmark result. Attaching a rate-limit kind to
    # it would put an infrastructure explanation on a model outcome.
    assert _rate_limit_kind("finish_reason: content_filter") is None


def test_unattributed_and_none_are_different_answers():
    assert _rate_limit_kind("Error code: 429") != _rate_limit_kind("boom")


def test_naming_both_kinds_is_attributable_to_neither():
    both = "exceeded token rate limit and call rate limit"
    # Taking the first match would make the answer depend on tuple order.
    assert _rate_limit_kind(both) == "unattributed"


def test_a_429_status_with_silent_prose_is_still_read_for_a_kind():
    # The status settles *that* it was a rate refusal; the prose settles which.
    # A turn whose category comes from the status must still be asked.
    assert _rate_limit_kind("", http_status_code=429) == "unattributed"
    assert _rate_limit_kind(TOKEN_REFUSAL, http_status_code=429) == "token"


def test_prose_about_rate_limiting_is_already_a_refusal_before_this_field():
    """An inherited false positive, named so it is not re-discovered as new.

    ``core.execution_errors`` matches the bare substring ``rate limit``, so a
    sentence *about* rate limiting already classifies as ``rate_limited``
    today, with or without this field. Naming its kind does not create the
    mislabel; it does make it more confident-looking, which is the honest cost
    of the field and the reason it is pinned here.

    Reached only if such prose ever lands on ``TurnError.message`` -- this
    matcher is called on the turn's failure, never on a task's text. The
    filter side of the same risk is already pinned by
    ``test_a_task_about_filtering_is_not_a_filtered_task``; narrowing the rate
    markers to match would be a change to what gets retried, and belongs in its
    own change with its own evidence.
    """
    about = "Write a report on token rate limit design for an API gateway."
    assert classify_execution_error(about) == "rate_limited"  # pre-existing
    assert _rate_limit_kind(about) == "token"  # inherited, not introduced


# ── What may leave the runner is a word, never the sentence ─────────────────


def test_every_answer_is_from_the_closed_set_or_nothing():
    for text in (TOKEN_REFUSAL, CALL_REFUSAL, "Error code: 429", "boom", ""):
        answer = _rate_limit_kind(text)
        assert answer is None or answer in RATE_LIMIT_KINDS


def test_the_published_word_does_not_carry_the_deployment_name():
    # `public_task_error` exists because this sentence names an endpoint. A
    # field read out of it must not reintroduce what that projection removes.
    published = _bounded_codex_diagnostics(
        {"items_seen": 3, "rate_limit_kind": _rate_limit_kind(TOKEN_REFUSAL)}
    )
    assert published == {"items_seen": 3, "rate_limit_kind": "token"}
    assert "azure" not in repr(published).lower()
    assert "ChatCompletions_Create" not in repr(published)


def test_a_string_the_provider_chose_cannot_pass_the_allow_list():
    # The allow-list is the reason the closed set is closed. Anything else is
    # dropped, not truncated: a prefix of this sentence is still the sentence.
    leaked = _bounded_codex_diagnostics(
        {"items_seen": 3, "rate_limit_kind": TOKEN_REFUSAL}
    )
    assert leaked == {"items_seen": 3}


@pytest.mark.parametrize("bad", [429, True, None, ["token"], {"kind": "token"}])
def test_only_a_member_of_the_closed_set_is_published(bad):
    assert _bounded_codex_diagnostics(
        {"items_seen": 1, "rate_limit_kind": bad}
    ) == {"items_seen": 1}


def test_the_field_is_absent_rather_than_null_when_there_is_no_kind():
    # An explicit `null` beside `items_seen` reads as "asked and unanswered".
    # Absent reads as "not a rate refusal", which is what it is.
    published = _bounded_codex_diagnostics(
        {"items_seen": 7, "rate_limit_kind": None}
    )
    assert published == {"items_seen": 7}
    assert "rate_limit_kind" not in published


def test_the_numbers_already_published_are_undisturbed():
    assert _bounded_codex_diagnostics(
        {"items_seen": 41, "http_status_code": 429, "rate_limit_kind": "request"}
    ) == {
        "items_seen": 41,
        "http_status_code": 429,
        "rate_limit_kind": "request",
    }


# ── The outcome carries it, so the runner can hand it on ────────────────────


def test_an_outcome_that_was_not_refused_carries_no_kind():
    assert CodexRunOutcome(success=True, text="done").rate_limit_kind is None


def test_the_outcome_field_is_what_the_diagnostics_are_built_from():
    # Guards the wiring rather than the rule: a field added to the dataclass
    # and never read would pass every test above and publish nothing.
    outcome = CodexRunOutcome(
        success=False,
        text="",
        items_seen=2,
        http_status_code=429,
        rate_limit_kind=_rate_limit_kind(CALL_REFUSAL),
    )
    assert _bounded_codex_diagnostics(
        {
            "items_seen": outcome.items_seen,
            "http_status_code": outcome.http_status_code,
            "rate_limit_kind": outcome.rate_limit_kind,
        }
    ) == {
        "items_seen": 2,
        "http_status_code": 429,
        "rate_limit_kind": "request",
    }
