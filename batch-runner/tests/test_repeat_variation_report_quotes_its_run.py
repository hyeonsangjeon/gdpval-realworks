"""The stage-3 report has to re-run, not restate.

The report's headline is a disagreement rate, and a disagreement rate is easy
to write down wrong and impossible to spot wrong by reading. So the report
carries the tool's own output inside a fenced block, together with the command
that produced it, and this file re-runs that command and demands the block
still match byte for byte. That is also why the bootstrap seed is a constant
rather than a clock: an interval that moved on every run would make this check
impossible, and a check that cannot be run is a check that is not done.

The rest holds the report to what no tool can generate. Which three payloads it
quotes. Every fingerprint it claims to have frozen. The place where this stage
departed from its written specification, which is stated in the report rather
than left for a reader to find. That the free analysis met its target, so no
paid run follows from it. And an honest bill for models with no published
price.
"""

import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import analyze_repeat_variation as rv


REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = REPO_ROOT / "data/grades/_validation/PR3_REPEAT_VARIATION.md"
PREREG_PATH = REPO_ROOT / "tasks/rebuilding_grading_task/315-repeat-variation-prereg.md"
TOOL_PATH = Path("batch-runner/scripts/analyze_repeat_variation.py")

# How the report marks the block it generated and the command behind it. The
# same shape stage 2 uses, so a reader who has checked one has checked both.
GENERATED_MARKER = re.compile(
    r"<!--\s*generated:\s*(?P<command>.+?)\s*-->\s*\n```text\n(?P<body>.*?)\n```",
    re.DOTALL,
)


@pytest.fixture(scope="module")
def report_text() -> str:
    assert REPORT_PATH.is_file(), (
        f"{REPORT_PATH.relative_to(REPO_ROOT)} is missing. The "
        "preregistration's step 5 requires it."
    )
    return REPORT_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def generated_blocks(report_text) -> list[re.Match]:
    blocks = list(GENERATED_MARKER.finditer(report_text))
    assert blocks, (
        "the report carries no generated block, so nothing in it can be "
        "checked against the runs it claims to describe"
    )
    return blocks


def test_every_generated_block_still_reproduces(generated_blocks):
    """The one check that makes the rest of the report worth reading.

    Twenty seconds of bootstrap, and it is the whole point of the file. If the
    numbers in the report were edited by hand, or the tool changed under them,
    or a payload moved, this is where it shows.
    """
    for block in generated_blocks:
        command = shlex.split(block.group("command"))

        assert command[0] in {"python", "python3"}, command[0]
        assert command[1] == str(TOOL_PATH), command[1]

        finished = subprocess.run(
            [sys.executable, *command[1:]],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        # 1 is the tool's honest "the target was not met". It is not a crash,
        # and pinning 0 here would mean a report could only ever be published
        # about a run that passed.
        assert finished.returncode in (0, 1), finished.stderr[-2000:]
        assert finished.stdout.strip() == block.group("body").strip(), (
            "the report's generated block no longer matches what the command "
            "above it produces"
        )


def test_the_block_is_the_registered_run_not_a_cheap_one(generated_blocks):
    """A report generated at 200 resamples would reproduce just as neatly.

    It would also be a different analysis from the registered one, so the
    command is required to carry no settings overrides at all and take the
    constants from the tool.
    """
    for block in generated_blocks:
        command = shlex.split(block.group("command"))
        overrides = [
            argument for argument in command if argument.startswith("--")
        ]

        assert overrides == [], overrides
        assert len(command) == 2 + rv.EXPECTED_RUN_COUNT, command


def test_the_report_names_every_file_it_read(report_text, generated_blocks):
    """A reader has to be able to open all three runs for themselves."""
    for block in generated_blocks:
        for argument in shlex.split(block.group("command"))[2:]:
            assert (REPO_ROOT / argument).is_file(), argument
            assert argument in report_text


def test_the_report_quotes_three_distinct_runs(generated_blocks):
    """Two paths and a repeat would reproduce perfectly and mean nothing."""
    for block in generated_blocks:
        payloads = shlex.split(block.group("command"))[2:]

        assert len(set(payloads)) == rv.EXPECTED_RUN_COUNT, payloads


def _report_needle(expected):
    """What a reader would look for in the report to find this fingerprint.

    Three shapes, because the report is written to be read rather than to be
    grepped. A full sha256 is abbreviated in prose the way everyone abbreviates
    one, so the first eight characters are what identifies it. A nested object
    has no single rendering, so its longest string value stands for it -- for
    the renderer that is the LibreOffice build, which is the part that would
    actually change a rendered page. Everything else is checked whole.
    """
    if isinstance(expected, dict):
        strings = [value for value in expected.values() if isinstance(value, str)]
        return max(strings, key=len)
    if isinstance(expected, str) and len(expected) > 16:
        try:
            int(expected, 16)
        except ValueError:
            return expected
        return expected[:8]
    return str(expected)


@pytest.mark.parametrize(
    "label,path,expected",
    rv.PINNED_FINGERPRINTS,
    ids=[label.replace(" ", "-") for label, _, _ in rv.PINNED_FINGERPRINTS],
)
def test_the_report_records_what_was_held_still(
    label, path, expected, report_text
):
    """Every field the tool refuses on has to be legible in the report.

    Parametrised over the tool's own list, so pinning something new without
    recording it fails here rather than passing quietly.
    """
    needle = _report_needle(expected)

    assert needle in report_text, (
        f"the report does not record the {label} it pinned "
        f"({'.'.join(path)}={needle!r})"
    )


def test_the_report_states_where_it_left_the_preregistration(report_text):
    """The deviation is declared in the report, not left to be discovered.

    Section 14 asked for the report under ``tasks/rebuilding_grading_task/``
    and it was written under ``data/grades/_validation/`` instead, because
    ``tasks/**`` is closed by .gitignore and the documents already in there
    predate the rule. Small, and worth saying out loud rather than hoping
    nobody diffs it -- so the report has to name both the path it was asked
    for and the one it took.
    """
    assert "tasks/rebuilding_grading_task/PR3_REPEAT_VARIATION.md" in report_text
    assert str(REPORT_PATH.parent.relative_to(REPO_ROOT)) in report_text
    assert "315-repeat-variation-prereg" in report_text


def test_the_report_gives_both_answers_rather_than_the_comfortable_one(
    report_text
):
    """The corpus mean holds still and one item in twenty comes back
    differently. A report that printed only the first would be true and
    misleading."""
    assert "4.75" in report_text or "4.7453" in report_text
    assert "10.47" in report_text or "10.4676" in report_text
    assert "0.89" in report_text


def test_the_report_says_no_further_paid_run_is_required(report_text):
    """The preregistration's escalation clause did not fire, and the report
    is where that is recorded.

    Section 13 said that if the free analysis missed its half-width target, a
    minimum number of extra runs and a stopping rule had to be registered
    before anything was dispatched. It did not miss, so the report has to say
    the target and say that nothing follows from it.
    """
    assert f"{rv.HALF_WIDTH_TARGET_PP}pp" in report_text
    assert "추가 유료 실행" in report_text


def test_the_report_bills_the_models_it_could_not_price(report_text):
    """A run nobody could price is not a run that cost nothing."""
    assert "unregistered" in report_text
    assert "gpt-5.6-sol" in report_text


def test_the_preregistration_came_first_and_names_this_report():
    assert PREREG_PATH.is_file()
    text = PREREG_PATH.read_text(encoding="utf-8")

    assert "PR3_REPEAT_VARIATION.md" in text


def test_the_tool_is_tracked_where_the_command_says_it_is():
    """``batch-runner/scripts/`` is gitignored with per-file exceptions, so a
    tool can work locally and be absent from a fresh clone.

    Probed without ``--verbose`` on purpose. With it, git reports the last
    matching pattern *including negations* and exits 0 either way, so a
    verbose probe cannot tell "ignored" from "un-ignored by a later rule".
    Without it the exit code is the answer: 1 means no pattern ignores this.
    """
    assert (REPO_ROOT / TOOL_PATH).is_file()

    finished = subprocess.run(
        ["git", "check-ignore", str(TOOL_PATH)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert finished.returncode == 1, (
        f"{TOOL_PATH} is ignored, so the command in the report cannot run "
        f"from a fresh clone"
    )
