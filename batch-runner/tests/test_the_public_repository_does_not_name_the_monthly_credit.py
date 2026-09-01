"""The public repository must not restate the owner's monthly account credit.

The benchmark spec used to open by naming, to the dollar, how much Azure credit
the owner is given each month. So did a comment in the advance-check plan. That
figure is account information, not a benchmark result, and this repository is
public — so on 2026-08-31 all four lines were reworded to say that a monthly
credit exists and was approved, without saying how large it is.

The wording that replaced them is deliberately load-bearing: it says the amount
is kept in the owner's private records. Without that sentence the next person to
read the spec sees a gap where a number used to be and helpfully fills it in.
This file is the mechanical half of the same defence.

**What the rule is.** A line of prose that names the *monthly* credit may not
also carry a money amount. Both halves matter, and the second half is the reason
this file is not simply a search for a number:

* Only the recurring, account-level sense is in scope. "Partial credit allowed"
  in a judge prompt, "image credits" in a report, "credit reporting" in a rubric
  — those are a different word doing a different job, and forty-odd of them live
  in ``results/`` and ``prompts/`` today. They are not caught, because a
  recurrence word has to appear as well.
* Ordinary cost receipts stay legal. Estimated and actual run costs are the
  point of this benchmark's cost work, and they are quoted in dollars all over
  the spec, the changelog and every ``report.md``. A rule that merely banned
  money would ban those too. That was tried, on the real corpus, and it flagged
  roughly fifteen legitimate receipts — which is exactly the over-reach this
  file is written to avoid.

**Scope.** Prose that a person wrote and a stranger can read: every tracked
``.md``, plus comment lines in tracked ``.yaml``, ``.yml`` and ``.py``. Machine
output under ``data/`` is excluded — grading evidence quotes spreadsheet
figures, and any four-digit run of a task's own numbers would collide by
coincidence rather than by disclosure.

**What this file does not cover.** ``advance_check_plan.yaml`` still carries the
amount in ``cost.owner_approval.available_monthly_credit_usd``, and six test
assertions still duplicate it as a constant. That is a data field, not prose,
and it cannot be removed here: ``core/execution_envelope_preflight.py`` requires
a positive number there whenever the cost policy is record-only, so dropping it
needs a change under ``core/`` — and every ``.py`` under ``core/`` is inside
``compute_grader_source_hash``, which is frozen until the paid run in flight has
pinned its evidence. It is queued as separate work. Widening this rule to reach
that field today would only make the suite fail on the repository's own file.

No amount appears anywhere below. The tests that prove the rule bites use a
stand-in number, because the rule keys on the *shape* of a disclosure rather
than on any particular value — writing the real figure into the guard that
exists to keep it out would be self-defeating.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# The recurring, account-level sense of "credit" — in either language.
CREDIT = re.compile(r"크레딧|credits?", re.IGNORECASE)

# ...said of something that arrives every month, which is what separates an
# account balance from partial credit on a rubric item.
RECURRING = re.compile(
    r"매월|달마다|월\s|월별|monthly|each month|per month|a month",
    re.IGNORECASE,
)

# A money amount, in the four shapes this repository actually writes them in.
# The last two alternatives catch a bare number with no currency word next to
# it; both require either digit grouping or a two-place decimal, so a date such
# as 2026-08-28 and a section number such as 13.27 are left alone.
AMOUNT = re.compile(
    r"(?:\$\s*\d)"
    r"|(?:\d[\d,]*(?:\.\d+)?(?:\s+\w+){0,3}\s*(?:달러|원\b|USD|dollars?))"
    r"|(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?)"
    r"|(?:\d{3,}\.\d{2}\b)",
    re.IGNORECASE,
)

PROSE_SUFFIXES = {".md", ".yaml", ".yml", ".py"}


def states_an_amount(line: str) -> str | None:
    """The money amount this line puts next to the monthly credit, if any."""
    if not CREDIT.search(line) or not RECURRING.search(line):
        return None
    found = AMOUNT.search(line)
    return found.group(0) if found else None


def _tracked_prose_files() -> list[Path]:
    listed = subprocess.run(
        [
            "git", "ls-files", "-z", "--",
            "*.md", "*.yaml", "*.yml", "*.py", ":!data/",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [REPO_ROOT / name for name in listed.split("\0") if name]


def _prose_lines(path: Path):
    """Line numbers and text for the parts of *path* a person reads as prose."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return
    everything_is_prose = path.suffix == ".md"
    for number, line in enumerate(text.splitlines(), start=1):
        if everything_is_prose or line.lstrip().startswith("#"):
            yield number, line


def test_no_public_prose_line_states_the_monthly_credit_amount() -> None:
    files = _tracked_prose_files()
    assert files, "no tracked prose found; the scan would pass vacuously"

    disclosures = [
        f"{path.relative_to(REPO_ROOT)}:{number} puts {amount!r} next to the "
        f"monthly credit"
        for path in files
        for number, line in _prose_lines(path)
        if (amount := states_an_amount(line))
    ]

    assert not disclosures, (
        "A public line names how much credit the owner's account is given each "
        "month:\n  " + "\n  ".join(disclosures) + "\n\n"
        "The amount is account information and this repository is public. Say "
        "that a monthly credit exists and was approved, and leave the figure in "
        "the owner's private records — as "
        "tasks/0822_saturday/TASK_GPT_EXECUTION_ENVELOPE_BENCHMARK.md does. If "
        "you meant to record what a run cost, that is welcome and this check "
        "does not touch it; keep it on a line that is not about the monthly "
        "credit."
    )


@pytest.mark.parametrize(
    "line",
    [
        # The four lines this rule was written for, with the figure replaced by
        # a stand-in. Shapes are otherwise exactly as they were committed.
        "  2026-08-28 소유자가 월 1,234달러 Azure 크레딧 사용과 미확정 소리 채점 비용의",
        "저장소 소유자는 매월 제공되는 **1,234달러 Azure 크레딧을 이 벤치마크 작업에",
        "- 월 1,234달러 크레딧 기록",
        "  # The owner has 1,234 United States dollars of Azure credit each month",
        # Re-entry in shapes nobody has used yet but easily might.
        "monthly Azure credit: $1,234",
        "The account is given 1,234 USD of credit per month",
        "  # available_monthly_credit_usd is 1234.00 for this account",
        "매월 크레딧 1234.00 이 주어진다",
    ],
)
def test_the_rule_catches_the_wording_that_was_removed(line: str) -> None:
    assert states_an_amount(line) is not None, (
        f"{line!r} states a monthly credit amount, but the rule let it through"
    )


@pytest.mark.parametrize(
    "line",
    [
        # Cost receipts. These are the point of the benchmark's cost work and
        # must stay sayable.
        "| 총액 | 7,204.84 dollars |",
        "실제 비용은 7,568.42 달러였다.",
        "예산은 7,204달러입니다",
        "- Budget: $7,500 for the full run",
        "estimated cost for this experiment: 291.39 United States dollars",
        # "credit" in its other, unrelated senses.
        "3. **Partial credit allowed.** If the criterion is partially met,",
        "- Income, tax, and credit amounts are not calculated or shown.",
        "  > 💡 Add a clear month-by-month timeline, explicit NCIPC credit, and $500",
        "did not consume excess Azure credit ... Total ~$30 spent across both",
        # The replacement wording itself, and a date or section number sitting
        # on a line that genuinely is about the monthly credit.
        "  # paid benchmark work under the recorded monthly credit, but each stage",
        "  2026-08-28 소유자가 매월 제공되는 Azure 크레딧 사용과 미확정 소리 채점 비용의",
        "monthly credit approved on 2026-08-28, see §13.27 of this spec",
    ],
)
def test_the_rule_leaves_ordinary_cost_receipts_alone(line: str) -> None:
    assert states_an_amount(line) is None, (
        f"{line!r} is a legitimate line, but the rule flagged it; a rule that "
        f"bans ordinary cost receipts will be deleted rather than obeyed"
    )
