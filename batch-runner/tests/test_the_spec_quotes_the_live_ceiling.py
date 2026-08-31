"""The written specification must quote the ceiling this repository computes.

The cost ceiling has been re-measured six times now, and every time the
numbers moved, the specification kept the old ones for a while. A reader who
opens the document and reads a total is entitled to assume it is the total,
not a snapshot of some Thursday.

So the document carries one block, fenced by HTML comments, that is not prose:

    <!-- ENVELOPE-CEILING:BEGIN -->
    | `grading` | 8811 | 6011.20562625 |
    <!-- ENVELOPE-CEILING:END -->

This file runs the real advance check and compares it, line by line, against
what that block says. If someone changes an assumption and does not re-quote
the result, this fails before the document can mislead anyone. If someone
edits the block by hand to a number the code does not produce, this fails too.

Fail closed throughout. A specification that cannot be read, or that has lost
its markers, is not treated as agreeing — it is treated as broken. Silence is
the failure mode this whole file exists to prevent.
"""

from __future__ import annotations

import re
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BATCH_RUNNER_ROOT.parent
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

from core.execution_envelope_preflight import (  # noqa: E402
    load_plan,
    run_envelope_preflight,
)

PLAN_PATH = (
    BATCH_RUNNER_ROOT / "experiments" / "execution_envelope" / "advance_check_plan.yaml"
)
SPECIFICATION = "tasks/0822_saturday/TASK_GPT_EXECUTION_ENVELOPE_BENCHMARK.md"
SPECIFICATION_PATH = REPOSITORY_ROOT / SPECIFICATION

BEGIN = "<!-- ENVELOPE-CEILING:BEGIN -->"
END = "<!-- ENVELOPE-CEILING:END -->"

ROW = re.compile(r"^\|\s*`([a-z_]+)`\s*\|\s*([0-9]+)\s*\|\s*([0-9.]+)\s*\|\s*$")


# ── Reading the two sides ───────────────────────────────────────────────────


def read_specification() -> str:
    """The document, or a refusal — never an empty string standing in for it."""
    if not SPECIFICATION_PATH.is_file():
        raise AssertionError(
            f"{SPECIFICATION} is not here, so the figures it is supposed to "
            "quote cannot be checked. This is refused rather than skipped: an "
            "unreadable specification is not an agreeing one."
        )
    return SPECIFICATION_PATH.read_text(encoding="utf-8")


def quoted_rows(text: str) -> dict[str, tuple[int, Decimal]]:
    """Parse the fenced block, refusing anything that is not exactly one block."""
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        raise AssertionError(
            f"the specification must carry exactly one {BEGIN} … {END} block; "
            f"found {text.count(BEGIN)} opening and {text.count(END)} closing "
            "markers. Without the markers nothing pins the written figures to "
            "the measured ones."
        )
    start = text.index(BEGIN) + len(BEGIN)
    end = text.index(END)
    if end < start:
        raise AssertionError("the ceiling block is closed before it is opened")

    rows: dict[str, tuple[int, Decimal]] = {}
    for line in text[start:end].splitlines():
        match = ROW.match(line.strip())
        if match is None:
            continue
        name, calls, usd = match.groups()
        if name in rows:
            raise AssertionError(f"the block quotes `{name}` twice")
        rows[name] = (int(calls), Decimal(usd))

    if not rows:
        raise AssertionError(
            "the ceiling block is present but holds no readable rows, so it "
            "would pass no matter what the code computes"
        )
    return rows


def live_rows() -> dict[str, tuple[int, Decimal]]:
    """What the real advance check says today, through the production path."""
    cost = run_envelope_preflight(load_plan(PLAN_PATH), root=BATCH_RUNNER_ROOT).cost
    rows: dict[str, tuple[int, Decimal]] = {
        environment.environment: (environment.model_calls, environment.usd)
        for environment in cost.environments
    }
    rows["grading"] = (cost.grading_model_calls, cost.grading_usd)
    rows["perception"] = (cost.perception_model_calls, cost.perception_usd)
    rows["before_safety_multiplier"] = (
        cost.total_model_calls,
        cost.total_before_safety_usd,
    )
    rows["total"] = (cost.total_model_calls, cost.total_usd)
    return rows


def disagreements(
    quoted: dict[str, tuple[int, Decimal]],
    live: dict[str, tuple[int, Decimal]],
) -> list[str]:
    """Every way the written block and the measured ceiling differ."""
    notes: list[str] = []
    for name in sorted(set(quoted) | set(live)):
        if name not in quoted:
            notes.append(f"`{name}` is a line of the ceiling but is not quoted")
            continue
        if name not in live:
            notes.append(f"`{name}` is quoted but is not a line of the ceiling")
            continue
        written_calls, written_usd = quoted[name]
        real_calls, real_usd = live[name]
        if written_calls != real_calls:
            notes.append(
                f"`{name}` model calls: written {written_calls}, measured {real_calls}"
            )
        if written_usd != real_usd:
            notes.append(
                f"`{name}` United States dollars: written {written_usd}, "
                f"measured {real_usd}"
            )
    return notes


@pytest.fixture(scope="module")
def measured() -> dict[str, tuple[int, Decimal]]:
    return live_rows()


@pytest.fixture(scope="module")
def written() -> dict[str, tuple[int, Decimal]]:
    return quoted_rows(read_specification())


# ── The check itself ────────────────────────────────────────────────────────


def test_the_specification_is_present_and_tracked():
    """A document a fresh clone does not get cannot be the record of anything.

    ``tasks/`` is ignored with a per-file allow list, so a specification can
    exist on one machine and nowhere else. That failure is silent, which is
    why it is asserted rather than assumed.
    """
    assert SPECIFICATION_PATH.is_file(), f"{SPECIFICATION} is missing"
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", SPECIFICATION],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
    )
    assert tracked.returncode == 0, (
        f"{SPECIFICATION} exists here but git does not track it, so the "
        "figures pinned below would be invisible to anyone who clones the "
        "repository."
    )


def test_the_written_ceiling_is_the_measured_ceiling(written, measured):
    """Every line, both columns, exact — no rounding, no tolerance.

    Tolerance is what let ``364.00`` sit next to ``364.23468750`` for days.
    """
    assert disagreements(written, measured) == []


def test_the_block_quotes_every_line_and_invents_none(written, measured):
    """A ceiling with a line missing reads like a smaller ceiling."""
    assert sorted(written) == sorted(measured)


@pytest.mark.parametrize(
    "name",
    [
        "azure_code_interpreter",
        "docker_container",
        "host_python_process",
        "grading",
        "perception",
        "before_safety_multiplier",
        "total",
    ],
)
def test_each_line_is_quoted_by_name(name, written, measured):
    """Named one at a time so a failure says which line drifted."""
    assert name in written, f"the specification stopped quoting `{name}`"
    assert written[name] == measured[name]


def test_the_quoted_total_is_the_quoted_parts_times_the_safety_multiplier(written):
    """The block has to be self-consistent, not merely copied correctly.

    This one holds without running anything, so a reader can check the
    arithmetic with a calculator and get the same answer the code does.
    """
    parts = sum(
        written[name][1]
        for name in (
            "azure_code_interpreter",
            "docker_container",
            "host_python_process",
            "grading",
            "perception",
        )
    )
    assert parts == written["before_safety_multiplier"][1]
    assert (
        written["before_safety_multiplier"][1] * Decimal("1.25")
        == written["total"][1]
    )


def test_the_quoted_call_counts_add_up(written):
    calls = sum(
        written[name][0]
        for name in (
            "azure_code_interpreter",
            "docker_container",
            "host_python_process",
            "grading",
            "perception",
        )
    )
    assert calls == written["before_safety_multiplier"][0] == written["total"][0]


def test_the_multiplier_the_block_assumes_is_the_one_in_force(measured):
    """If the plan's safety multiplier changes, the block's arithmetic lies."""
    cost = run_envelope_preflight(load_plan(PLAN_PATH), root=BATCH_RUNNER_ROOT).cost
    assert cost.safety_multiplier == Decimal("1.25"), (
        "the safety multiplier moved; the specification block still explains "
        "itself as a 1.25 multiplication and must be rewritten"
    )


# ── Proof that the check can fail ───────────────────────────────────────────
#
# A comparison nobody has ever seen fail is indistinguishable from one that
# cannot. Each of these mutates the real document in memory — the file on disk
# is never written — and insists the failure is noticed.


def test_a_single_wrong_digit_is_caught(measured):
    text = read_specification()
    broken = text.replace("| `grading` | 8811 |", "| `grading` | 8812 |")
    assert broken != text, "the mutation did not apply, so it proves nothing"
    notes = disagreements(quoted_rows(broken), measured)
    assert any("`grading` model calls" in note for note in notes), notes


def test_a_wrong_amount_is_caught(measured):
    text = read_specification()
    broken = text.replace("6011.20562625", "6011.20562626")
    assert broken != text
    notes = disagreements(quoted_rows(broken), measured)
    assert any("`grading` United States dollars" in note for note in notes), notes


def test_the_figure_this_repository_used_to_carry_is_caught_if_it_returns(measured):
    """364.23468750 was the total while one marking call was priced at 10,000.

    It is the number most likely to be pasted back in by someone working from
    an older copy of the document.
    """
    text = read_specification()
    stale = text.replace("| `total` | 10136 | 7608.4048453125 |", "| `total` | 10136 | 364.23468750 |")
    assert stale != text
    notes = disagreements(quoted_rows(stale), measured)
    assert any("`total` United States dollars" in note for note in notes), notes


def test_a_dropped_line_is_caught_rather_than_read_as_a_cheaper_ceiling(measured):
    text = read_specification()
    thinner = text.replace("| `perception` | 1125 | 54.00 |\n", "")
    assert thinner != text
    notes = disagreements(quoted_rows(thinner), measured)
    assert any("`perception`" in note and "not quoted" in note for note in notes), notes


def test_moving_an_assumption_makes_the_written_block_wrong(written):
    """The other direction, and the one that matters.

    The mutations above prove the comparison notices a bad document. This
    proves it notices a stale one: put the old marking figure back into the
    plan and the block — untouched — stops matching. That is the exact event
    this file was written to catch, so it is exercised rather than assumed.
    """
    plan = load_plan(PLAN_PATH)
    plan["cost"]["assumptions"]["grading_input_tokens_per_call"] = 10_000
    cost = run_envelope_preflight(plan, root=BATCH_RUNNER_ROOT).cost

    rolled_back = {
        environment.environment: (environment.model_calls, environment.usd)
        for environment in cost.environments
    }
    rolled_back["grading"] = (cost.grading_model_calls, cost.grading_usd)
    rolled_back["perception"] = (cost.perception_model_calls, cost.perception_usd)
    rolled_back["before_safety_multiplier"] = (
        cost.total_model_calls,
        cost.total_before_safety_usd,
    )
    rolled_back["total"] = (cost.total_model_calls, cost.total_usd)

    notes = disagreements(written, rolled_back)
    assert any("`grading` United States dollars" in note for note in notes), notes
    assert any("`total` United States dollars" in note for note in notes), notes

    # and only the marking side moved — the three running lines are untouched
    assert not any(
        name in note
        for note in notes
        for name in ("azure_code_interpreter", "docker_container", "host_python_process")
    ), notes


def test_a_missing_specification_is_refused_not_treated_as_agreeing(monkeypatch, tmp_path):
    """Item three of the standing instruction, applied to this file itself."""
    monkeypatch.setattr(
        sys.modules[__name__], "SPECIFICATION_PATH", tmp_path / "gone.md"
    )
    with pytest.raises(AssertionError, match="is not here"):
        read_specification()


def test_a_block_with_no_markers_is_refused_not_skipped():
    with pytest.raises(AssertionError, match="exactly one"):
        quoted_rows("the ceiling is roughly seven thousand dollars\n")


def test_a_block_that_is_opened_twice_is_refused():
    text = read_specification()
    with pytest.raises(AssertionError, match="exactly one"):
        quoted_rows(text + "\n" + BEGIN + "\n" + END + "\n")


def test_an_empty_block_is_refused_rather_than_passing_vacuously():
    with pytest.raises(AssertionError, match="no readable rows"):
        quoted_rows(f"{BEGIN}\n\n(to be filled in later)\n\n{END}\n")


# ── The prose around the block has to point at this file ────────────────────


def test_the_document_tells_the_reader_the_block_is_checked():
    """Otherwise the next editor tidies the markers away as clutter."""
    text = read_specification()
    assert Path(__file__).name in text, (
        "the specification no longer names this test, so a reader has no way "
        "to know the block is machine-checked"
    )
    assert "손으로 고치지 마십시오" in text, (
        "the instruction not to hand-edit the block has gone missing"
    )
