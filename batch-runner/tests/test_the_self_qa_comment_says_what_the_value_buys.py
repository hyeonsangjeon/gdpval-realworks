"""A self-review budget that can never regenerate must not claim it can.

``qa.max_retries`` is a budget of answers, not of extra tries: a value of N
produces N answers and therefore buys N - 1 replacements. One is the value
twenty-nine of the thirty-two self-review blocks use, and it buys none. That
arithmetic is pinned against the shipped loop in
``test_self_qa_attempt_budget.py``; this file is about what the config files
*say* next to it.

Eleven of them used to say ``# max regeneration attempts on QA failure`` beside
a value that regenerates nothing. The loop was never wrong -- the comment was,
and a comment is what a reader reaches for first.

Two things this file is careful about.

**The rule is derived, not asserted.** "A budget of one buys no replacement" is
not restated here as a constant; it is read from the shipped description of the
setting, so a change to the semantics breaks the premise rather than silently
leaving the rule pointing at the wrong values.

**Only the self-review setting is in scope.** These files also carry a
top-level ``max_retries``, and that one really is a count of retries -- infra
retries after an API error or a timeout. Sweeping it up in the same rename
would replace a true comment with a false one, so it is asserted to still say
retries.

Silence is left alone. Eighteen self-review blocks carry the value with no
comment at all, in files whose whole ``qa:`` block is comment-free. Saying
nothing is not a false claim, and adding a sentence to eighteen files to fix a
problem none of them has is churn.
"""

import re
from pathlib import Path

import pytest

from core.execution_envelope_preflight import WHAT_THE_SETTING_DOES


EXPERIMENTS = Path(__file__).resolve().parents[1] / "experiments"

#: ``qa.max_retries`` sits four spaces in, under ``qa:``. The top-level
#: ``max_retries`` sits two. The indent is what tells them apart.
QA_BUDGET = re.compile(r"^ {4}max_retries:\s*(\d+)\s*(#.*)?$")
INFRA_BUDGET = re.compile(r"^ {2}max_retries:\s*(\d+)\s*(#.*)?$")

#: A comment beside a budget that buys no replacement has to *say* so.
#:
#: Matching on banned words was the first attempt and does not work: the
#: corrected wording "1 regenerates nothing" contains "regenerat", so a list
#: that catches "max regeneration attempts on QA failure" catches the fix for
#: it too, and every one of the eleven corrected files failed. What separates
#: the false comment from the true one is the claim, not the vocabulary, so
#: the check is for the denial rather than against the word.
DENIES_REPLACEMENT = ("regenerates nothing", "replaces nothing", "buys no")

#: The top-level comment exists in English and Korean. Ten files say "infra
#: retries per task (API errors, ...)", one says just "infra retries per task",
#: three say the same thing in Korean. All fourteen are correct.
NAMES_INFRA_RETRIES = ("infra retries", "인프라 리트라이")


def _lines(pattern):
    """Every (file, line number, value, comment) the pattern matches."""
    found = []
    for path in sorted(EXPERIMENTS.glob("*.yaml")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            match = pattern.match(line)
            if match:
                found.append(
                    (path.name, number, int(match.group(1)), match.group(2) or "")
                )
    return found


@pytest.fixture(scope="module")
def qa_budgets():
    found = _lines(QA_BUDGET)
    assert found, "no qa.max_retries settings found under experiments/"
    return found


def test_the_setting_is_described_as_a_budget_of_answers():
    """The premise the rule below is derived from.

    If this ever stops holding, "a budget of one buys no replacement" stops
    being a consequence of the shipped description and becomes an assumption,
    and the rule has to be rewritten rather than left pointing at the wrong
    values.
    """
    described = WHAT_THE_SETTING_DOES["condition_a.qa.max_retries"]
    assert described == "how many answers it may produce in all"


def test_no_budget_that_buys_no_replacement_claims_one(qa_budgets):
    """The check this file exists for.

    Silence is not in scope: eighteen of these carry no comment, and saying
    nothing is not a false claim. The rule applies to what is written.
    """
    described = WHAT_THE_SETTING_DOES["condition_a.qa.max_retries"]
    assert "in all" in described  # answers in all, so replacements = value - 1

    offenders = []
    for name, number, value, comment in qa_budgets:
        replacements = value - 1
        if replacements > 0 or not comment.strip():
            continue
        lowered = comment.lower()
        if not any(phrase in lowered for phrase in DENIES_REPLACEMENT):
            offenders.append(f"{name}:{number} {comment}")
    assert offenders == [], (
        "these self-review budgets buy no replacement and their comment does "
        "not say so: " + "; ".join(offenders)
    )


def test_the_corrected_comment_says_what_the_value_buys(qa_budgets):
    """Removing the false claim is not enough if nothing true replaces it.

    The eleven that used to mislead now carry a comment; a change that quietly
    deleted them instead would pass the rule above and leave a reader with
    nothing but the misleading *name* of the setting.
    """
    explained = [c for _, _, v, c in qa_budgets if v <= 1 and c.strip()]
    assert len(explained) == 11
    for comment in explained:
        assert "answers in all" in comment
        assert "regenerates nothing" in comment


def test_the_silent_ones_are_still_silent(qa_budgets):
    """Eighteen say nothing, which is not a claim and so not a defect.

    Pinned so that a later sweep adding a comment to all of them is a visible
    decision rather than a side effect.
    """
    silent = [c for _, _, v, c in qa_budgets if v <= 1 and not c.strip()]
    assert len(silent) == 18


def test_the_infra_retry_comment_was_not_swept_up():
    """The top-level setting really does count retries. It must keep saying so.

    This is the guard against over-applying the correction: a rename that hit
    both would swap a true comment for a false one, and nothing else in the
    suite would notice.
    """
    infra = [(n, c) for n, _, _, c in _lines(INFRA_BUDGET) if c.strip()]
    assert infra, "no commented top-level max_retries found"
    for name, comment in infra:
        assert any(p in comment for p in NAMES_INFRA_RETRIES), f"{name}: {comment}"
