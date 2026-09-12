"""The reporting rules, tested against a draft with an invented number in it.

The rule is "fill nothing with predicted results", and the way that rule fails
is specific and easy to do by accident: a draft written while the run is still
going, with the figures the writer expects to see. It reads like a report. Every
sentence is well-formed. One number in it was never measured.

So the cases here are drafts, built by hand, put through the check before
anything is published. A draft quoting the run record. The same draft with one
figure changed to a number nobody measured. A draft with a percentage in it,
which is a figure that is legitimately not in the record. A draft written before
the run, which has no record to check against at all.

The last two tests are about the check's own reach, stated as tests so that
passing it is never read as the report being right.

Offline, and free.
"""
from __future__ import annotations

import pytest

from core.agentic_v2_reporting_rules import (
    THE_EN_CHAIN,
    THE_KO_CHAIN,
    THE_OUTLINE_EN,
    THE_OUTLINE_KO,
    blank_outline,
    check_every_figure,
    describe,
    figures_in,
    is_short_enough,
    the_outline,
    the_rules,
)

#: Shaped like the run record a V2 stage writes, with only the parts a report
#: quotes. The figures are trial_30's, because they are figures that exist.
A_RUN_RECORD = {
    "run": {
        "run_id": "34671538199",
        "results": [
            {"task_id": "a", "problem_solving_cost": {"model_calls": 305}},
        ],
        "totals": {"tasks": 30, "finished": 11, "did_not": 19},
    },
    "cost": {"charged_usd": 6.131815, "ceiling_usd": 141.61},
}


def test_the_two_outlines_are_the_same_outline():
    """A reader of one can find the matching paragraph in the other."""
    assert len(THE_OUTLINE_KO) == len(THE_OUTLINE_EN) == 6
    assert the_outline("ko") == THE_OUTLINE_KO
    assert the_outline("en") == THE_OUTLINE_EN


def test_a_third_language_is_refused_rather_than_guessed():
    with pytest.raises(ValueError, match="ko and en"):
        the_outline("ja")


def test_the_chains_are_in_order_and_the_structure_skill_is_first():
    """The editors run over a report that already has its claims placed.

    Reversed, the copy-editor smooths prose that the structure skill then
    rewrites, and the de-mechanised sentences are lost.
    """
    assert THE_KO_CHAIN[0] == "experiment-report-ko"
    assert THE_KO_CHAIN[-1] == "humanize-korean:strict"
    assert THE_EN_CHAIN[0] == "experiment-report-en"
    assert THE_EN_CHAIN[-1] == "im-not-ai-en"
    assert "humanize-english" in THE_EN_CHAIN


# ---------------------------------------------------------------------------
# Before the run
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("language", ["ko", "en"])
def test_the_thing_that_exists_before_the_run_has_no_numbers_in_it(language):
    """Not even as an example. A placeholder reads like a result."""
    outline = blank_outline(language)
    for heading in the_outline(language):
        assert heading in outline
    assert figures_in(outline) == ()


def test_the_blank_outline_is_not_ready_to_publish():
    verdict = check_every_figure(blank_outline("en"), A_RUN_RECORD)
    assert verdict["ready"] is False
    assert "quotes no figure" in verdict["not_ready_because"]


# ---------------------------------------------------------------------------
# After the run
# ---------------------------------------------------------------------------


def test_a_draft_quoting_the_record_is_ready():
    draft = (
        "## What happened\n\n"
        "Run 34671538199 put 30 tasks through the harness. 11 finished and "
        "19 did not. $6.131815 was charged against a ceiling of $141.61.\n"
    )
    verdict = check_every_figure(draft, A_RUN_RECORD)
    assert verdict["ready"] is True, describe(verdict)
    assert verdict["unsourced"] == 0
    assert verdict["found"] >= 5


def test_one_invented_figure_is_enough_to_hold_the_draft():
    """The case the rule is about: a number the writer expected to see.

    Everything else in this draft is real. ``14`` is not, and nothing about
    the sentence it sits in gives that away.
    """
    draft = (
        "Run 34671538199 put 30 tasks through the harness. 14 finished and "
        "19 did not.\n"
    )
    verdict = check_every_figure(draft, A_RUN_RECORD)

    assert verdict["ready"] is False
    assert verdict["unsourced"] == 1
    unsourced = [row for row in verdict["rows"] if row["status"] == "unsourced"]
    assert unsourced[0]["text"] == "14"
    assert "14 finished" in unsourced[0]["context"]
    assert "14" in describe(verdict)


def test_a_percentage_is_allowed_and_the_pair_behind_it_is_named():
    """Because a report says "a third of them" as a number, legitimately.

    Naming the pair is the point: 36.7% of 30 is 11, and a reader who is told
    the derivation can see whether 11 was the right numerator.
    """
    draft = "36.7% of the 30 tasks finished.\n"
    verdict = check_every_figure(draft, A_RUN_RECORD)

    assert verdict["ready"] is True
    derived = [row for row in verdict["rows"] if row["status"] == "derived"]
    assert derived and derived[0]["value"] == pytest.approx(36.7)
    assert derived[0]["because"] == "11/30 as a percentage"


def test_a_percentage_of_the_wrong_pair_still_reads_as_derived():
    """Stated so the allowance is never mistaken for a correctness check.

    63.3% is 19/30, which is the tasks that did *not* finish. A draft that
    calls it the finished share passes this check and is wrong.
    """
    verdict = check_every_figure("63.3% of the tasks finished.\n", A_RUN_RECORD)
    derived = [row for row in verdict["rows"] if row["status"] == "derived"]
    assert verdict["ready"] is True
    assert derived[0]["because"] == "19/30 as a percentage"
    assert "a true figure in a false sentence" in verdict["what_this_cannot_catch"]


def test_a_date_is_not_read_as_a_finding():
    draft = "The run finished on 2026-09-11 with 11 of 30 done.\n"
    verdict = check_every_figure(draft, A_RUN_RECORD)
    assert verdict["ready"] is True
    assert "2026" not in [row["text"] for row in verdict["rows"]]


def test_a_small_number_written_as_a_digit_is_a_figure_like_any_other():
    """No allowance for small integers, because that is where findings live.

    "2 tasks hit the wall clock" is a measurement. An exemption for 0-3 would
    have let the most common small finding through unchecked, which is the hole
    this whole module is against. A count that really is just prose gets
    spelled as a word, and a word is never scanned.
    """
    verdict = check_every_figure("2 tasks hit the wall clock.\n", A_RUN_RECORD)
    assert verdict["ready"] is False
    assert [row["text"] for row in verdict["rows"] if row["status"] == "unsourced"] == [
        "2"
    ]

    spelled = check_every_figure(
        "The two defects were fixed together, and 11 of 30 tasks finished.\n",
        A_RUN_RECORD,
    )
    assert figures_in("The two defects were fixed together.\n") == ()
    assert spelled["ready"] is True


def test_a_thousands_separator_is_the_same_number():
    record = {"totals": {"input_tokens": 1234567}}
    verdict = check_every_figure("It sent 1,234,567 input tokens.\n", record)
    assert verdict["ready"] is True
    assert verdict["found"] == 1


def test_a_figure_quoted_from_a_string_in_the_record_counts():
    """Run ids and status lines live in strings, and reports quote them."""
    record = {"run": {"note": "shard 3 of 4 resumed from run 34671538199"}}
    verdict = check_every_figure("Shard 3 of 4 was resumed.\n", record)
    assert verdict["unsourced"] == 0


def test_an_empty_record_makes_every_figure_unsourced():
    """A draft written against a run that produced nothing to quote."""
    verdict = check_every_figure("11 of 30 tasks finished.\n", {})
    assert verdict["ready"] is False
    assert verdict["unsourced"] == 2


# ---------------------------------------------------------------------------
# Short is a rule, not a preference
# ---------------------------------------------------------------------------


def test_short_is_measured_in_the_unit_each_language_is_written_in():
    korean = is_short_enough("가" * 100, "ko")
    english = is_short_enough("word " * 100, "en")
    assert korean["unit"] == "characters" and korean["within"] is True
    assert english["unit"] == "words" and english["within"] is True


def test_a_long_draft_fails_the_ceiling():
    assert is_short_enough("가" * 5000, "ko")["within"] is False
    assert is_short_enough("word " * 1000, "en")["within"] is False


def test_the_derivation_allowance_is_only_offered_to_figures_that_claim_it():
    """A bare integer is not quietly rescued by some pair that fits it.

    ``2`` is 6.131815/305 to one decimal place, and this record has seven
    numbers in it, so it has more than forty pairs. Offering the percentage
    allowance to every figure means almost any small integer finds a pair and
    the check stops refusing anything. It is offered only where the draft
    writes the figure as a percentage.
    """
    bare = check_every_figure("2 tasks hit the wall clock.\n", A_RUN_RECORD)
    assert bare["derived"] == 0
    assert bare["unsourced"] == 1

    written_as_one = check_every_figure("2.0% of the budget went on it.\n", A_RUN_RECORD)
    assert written_as_one["derived"] == 1
    assert written_as_one["ready"] is True


def test_the_rules_state_both_halves_and_can_be_quoted_whole():
    rules = the_rules()
    assert rules["outline_ko"] == list(THE_OUTLINE_KO)
    assert rules["chain_en"] == list(THE_EN_CHAIN)
    assert "before it has been measured" in rules["before_the_run"]
    assert "check_every_figure" in rules["after_the_run"]
    assert "not a claim" in rules["the_two_reports_say_the_same_thing"]
