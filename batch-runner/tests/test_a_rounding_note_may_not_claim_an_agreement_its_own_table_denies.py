"""A record's rounding note has to agree with the table printed above it.

Every exp035 leg record carries a short section called `6자리 반올림에 대해`.
It exists because the lineage total can be computed two ways and they are not
bit-identical: `build_partial_run_record.py` rounds each task to six places
before storing it, then totals the *unrounded* values once, while
`roll_up_round.py` adds up the stored per-task figures. The section prints both
numbers and then says which one the document quotes at four places.

At leg 5 the two paths landed on the same four-decimal figure, and the section
said so:

    차이는 $0.000036이고 ... **소수 4자리에서는 두 값이 같으므로**($62.3328)
    이 문서는 4자리로 적습니다.

That sentence was true of $62.332810 and $62.332846. It was carried into the
leg 6 record unchanged, where it is false: $86.471018 rounds to $86.4710 and
$86.471063 rounds to $86.4711. The record asserted an agreement that the table
two lines above it denied, and `round_state.json` -- which stores the
adding-the-rows path -- has held $86.4711 the whole time while the record
printed $86.4710 in six places.

Nothing was mismeasured. `cost.per_lineage.A + cost.per_lineage.B` still equals
`cost.round_total_usd` exactly, and the round total's own four-decimal figure
($100.8576) is right under either path. What failed is the sentence, and it
failed by being inherited rather than recomputed -- which is why a test is
worth more here than a correction. Leg 7 will write the same section, and the
spread grows with the number of rows.

So this pins three things per record:

* the two figures in the table are recomputed at four places, and the prose may
  claim agreement only when they actually agree;
* when they disagree, both four-decimal figures have to appear, so a reader is
  never handed one of them as if it were the only one;
* whatever the record prints has to be one of the two paths. A third number
  would mean some other arithmetic produced it.

A fourth check keeps the round's two money halves apart. The cost of solving
the tasks and the cost of grading them are separate measurements with separate
ledgers, and one of them has not been spent yet -- the grading figure is a
projection. A single number equal to their sum would be neither, so no such
number may appear in a run record.

Nothing here contacts a provider.
"""

from __future__ import annotations

import json
import re
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pytest

RECORDS_DIR = Path(__file__).resolve().parents[1] / "docs" / "run_records"
ROUND_STATE = RECORDS_DIR / "round_state.json"

CENTS_4 = Decimal("0.0001")

#: `| 반올림 전 합계를 한 번 반올림 | $86.471018 |`
TOTALLED_ONCE = re.compile(
    r"^\|\s*반올림 전 합계를 한 번 반올림\s*\|\s*\$([0-9][0-9.]*)\s*\|", re.M
)
#: `| 반올림된 186줄을 더함 | $86.471063 |`
ADDED_THE_ROWS = re.compile(
    r"^\|\s*반올림된 [\d,]+줄을 더함\s*\|\s*\$([0-9][0-9.]*)\s*\|", re.M
)

#: Wordings that assert the two paths land on the same four-decimal figure.
#: Matched against text with emphasis stripped and soft wraps flattened -- the
#: sentence this file was written about wrapped between `두` and `값이`, so a
#: matcher that respected line breaks found nothing in the very record that
#: carried the false claim.
AGREEMENT_PHRASES = (
    "소수 4자리에서는 두 값이 같",
    "소수 4자리에서 두 값이 같",
    "4자리에서는 두 값이 같",
    "4자리에서 두 값이 같",
    "두 값이 같으므로",
)


def _records() -> list[Path]:
    if not RECORDS_DIR.is_dir():
        return []
    return sorted(p for p in RECORDS_DIR.glob("*/report.md"))


def _with_a_rounding_note() -> list[Path]:
    return [
        p
        for p in _records()
        if TOTALLED_ONCE.search(p.read_text(encoding="utf-8"))
    ]


def _four_places(value: str) -> Decimal:
    return Decimal(value).quantize(CENTS_4, rounding=ROUND_HALF_UP)


def _plain(text: str) -> str:
    """Emphasis removed and soft wraps flattened, so a claim is one string."""
    return re.sub(r"\s+", " ", text.replace("*", "").replace("`", ""))


def _ids(paths: list[Path]) -> list[str]:
    return [p.parent.name for p in paths]


NOTED = _with_a_rounding_note()


@pytest.mark.skipif(not NOTED, reason="no record carries a rounding note")
@pytest.mark.parametrize("report", NOTED, ids=_ids(NOTED))
def test_a_record_claims_the_two_paths_agree_only_when_they_do(report: Path):
    text = report.read_text(encoding="utf-8")
    once = _four_places(TOTALLED_ONCE.search(text).group(1))
    rows_match = ADDED_THE_ROWS.search(text)
    assert rows_match, f"{report.parent.name}: the note lost its second row"
    rows = _four_places(rows_match.group(1))

    plain = _plain(text)
    claimed = [phrase for phrase in AGREEMENT_PHRASES if phrase in plain]

    if once == rows:
        return

    assert not claimed, (
        f"{report.parent.name}: the note says the two paths agree at four "
        f"places ({claimed[0]!r}), but its own table gives ${once} and "
        f"${rows}. Leg 5's sentence was true and does not survive being "
        f"carried forward -- recompute it for this leg."
    )


@pytest.mark.skipif(not NOTED, reason="no record carries a rounding note")
@pytest.mark.parametrize("report", NOTED, ids=_ids(NOTED))
def test_a_split_note_shows_both_figures_rather_than_one_of_them(report: Path):
    text = report.read_text(encoding="utf-8")
    once = _four_places(TOTALLED_ONCE.search(text).group(1))
    rows = _four_places(ADDED_THE_ROWS.search(text).group(1))
    if once == rows:
        return

    for figure in (once, rows):
        assert f"${figure}" in text, (
            f"{report.parent.name}: the two paths differ at four places "
            f"(${once} vs ${rows}) and ${figure} is not written anywhere. A "
            f"reader handed only the other one cannot tell which they have."
        )


@pytest.mark.skipif(not ROUND_STATE.is_file(), reason="no round roll-up")
def test_the_roll_ups_lineage_figure_is_one_of_the_two_paths():
    """The roll-up adds the rows, so it may not hold some third number."""
    state = json.loads(ROUND_STATE.read_text(encoding="utf-8"))
    surviving = state["surviving_lineage"]
    lineage = state["cost"]["per_lineage"][surviving]
    rolled = _four_places(str(lineage["derived_cost_usd"]))

    latest = NOTED[-1] if NOTED else None
    assert latest is not None, "no leg record to compare the roll-up against"
    text = latest.read_text(encoding="utf-8")
    paths = {
        _four_places(TOTALLED_ONCE.search(text).group(1)),
        _four_places(ADDED_THE_ROWS.search(text).group(1)),
    }
    assert rolled in paths, (
        f"round_state.json reads lineage {surviving} as ${rolled}, which is "
        f"neither path in {latest.parent.name}'s note ({sorted(paths)}). One "
        f"of the two artifacts is totalling a different set of calls."
    )


@pytest.mark.skipif(not ROUND_STATE.is_file(), reason="no round roll-up")
def test_no_record_states_a_figure_that_adds_solving_to_grading():
    """Solving is measured and spent; grading is a projection. Never one number.

    The grading range is read out of the record that states it rather than
    hardcoded, so this keeps working when a further leg moves it.
    """
    state = json.loads(ROUND_STATE.read_text(encoding="utf-8"))
    solving = Decimal(str(state["cost"]["round_total_usd"]))

    grading_range = re.compile(r"\$([0-9][0-9.]*)\s*(?:–|-|~)\s*\$([0-9][0-9.]*)")
    endpoints: set[Decimal] = set()
    for report in _records():
        for low, high in grading_range.findall(report.read_text(encoding="utf-8")):
            if Decimal(low) > solving:  # a grading figure, not a solving one
                endpoints.update((Decimal(low), Decimal(high)))
    if not endpoints:
        pytest.skip("no record states a grading range yet")

    forbidden = {
        (solving + end).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        for end in endpoints
    }
    for report in _records():
        text = report.read_text(encoding="utf-8")
        for total in sorted(forbidden):
            assert f"${total}" not in text, (
                f"{report.parent.name} states ${total}, which is the solving "
                f"floor (${solving}) plus a grading estimate. Those are two "
                f"measurements and one of them has not been spent -- report "
                f"them side by side, never added."
            )
