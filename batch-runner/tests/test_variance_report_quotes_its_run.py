"""The stage-2 report has to quote its three runs rather than restate them.

Stage 2 asks a narrow question: grade the same thirty gold answers three times
with everything frozen, and say how far the score moved. The answer is only
worth anything if two things hold -- the three runs really were the same run,
and the numbers in the report really came out of those files.

The first is the analysis tool's job and it refuses outright when a frozen
field differs. The second is this file's job: the report carries the tool's own
output inside a fenced block together with the command that produced it, and
this re-runs that command and demands the block still match, byte for byte.
That is also why the tool's bootstrap seed is a constant rather than a clock --
a resampled interval that moved every time nobody ran the tool would make this
check impossible, and a check that cannot be run is a check that is not done.

The rest holds the report to what no tool can generate. Which three payloads it
quotes, and that they are the three the repository actually holds. The freeze,
recorded from the payloads rather than from the plan. The one thing stage 2
deliberately did *not* freeze, and why gating on it would have failed stage 1's
own accepted run. The place where this stage departed from its written
specification. And an honest bill for models with no published price.
"""

import json
from pathlib import Path
import re
import shlex
import subprocess
import sys

import pytest

from scripts import analyze_gold_ceiling as gold
from scripts import analyze_variance as variance


REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = REPO_ROOT / "tasks/rebuilding_grading_task/PR3_VARIANCE.md"
SPEC_PATH = REPO_ROOT / "tasks/rebuilding_grading_task/303-variance-and-error.md"
DIAGNOSTIC_ROOT = REPO_ROOT / "data/grades/_diagnostic"
WORKFLOW_PATH = REPO_ROOT / ".github/workflows/grade-run.yml"
CONTAINER_IMAGE = re.compile(
    r"image:\s*(?P<image>ghcr\.io/\S+@sha256:(?P<digest>[0-9a-f]{64}))"
)

# How the report marks the block it generated and the command behind it.
GENERATED_MARKER = re.compile(
    r"<!--\s*generated:\s*(?P<command>.+?)\s*-->\s*\n```text\n(?P<body>.*?)\n```",
    re.DOTALL,
)


def _repeat_grade_files() -> list[Path]:
    """Every finished run against stage 1's pinned corpus, repeats included.

    This is the mirror image of the stage-1 helper. That one excludes
    ``_repeats/`` because a repeat would otherwise look like a second answer to
    stage 1's question; this one needs exactly those, because the repeats *are*
    stage 2's question.

    ``_superseded/`` stays excluded in both. It holds a run graded by a reading
    tool that has since been fixed, kept because stage 1's claim about what the
    fix recovered is only checkable against it. Comparing it to the three
    current runs would measure a code change, which is the one thing stage 2 is
    trying to hold still.

    Shards are excluded by ``run_status``: a shard declares the whole corpus in
    its identity fields while holding one slice of it, so nothing but its status
    distinguishes it from a finished run.
    """
    found = []
    for path in sorted(DIAGNOSTIC_ROOT.rglob("*.json")):
        if "_superseded" in path.parts:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        if (
            payload.get("expected_ordered_task_ids_sha256")
            == gold.EXPECTED_ORDERED_TASK_IDS_SHA256
            and payload.get("run_status") in gold.COMPLETE_RUN_STATUSES
        ):
            found.append(path)
    return found


@pytest.fixture(scope="module")
def repeat_grade_files() -> list[Path]:
    files = _repeat_grade_files()
    assert len(files) == variance.EXPECTED_RUN_COUNT, (
        f"stage 2 compares {variance.EXPECTED_RUN_COUNT} runs of the same "
        f"corpus, and the repository holds {len(files)}: "
        f"{[str(path.relative_to(REPO_ROOT)) for path in files]}. A repeat is "
        "committed under _repeats/run-NNN/ by the grading workflow's merge "
        "step; a run that is missing has not finished or has not been merged."
    )
    return files


@pytest.fixture(scope="module")
def runs(repeat_grade_files) -> list[dict]:
    return variance.load_runs(list(repeat_grade_files))


@pytest.fixture(scope="module")
def report_text() -> str:
    assert REPORT_PATH.is_file(), (
        f"{REPORT_PATH.relative_to(REPO_ROOT)} is missing. The specification's "
        "step 5 requires it."
    )
    return REPORT_PATH.read_text(encoding="utf-8")


# ── The three runs really are one run, repeated ────────────────────────────


def test_the_three_runs_are_comparable(runs):
    """If a frozen field moved, the whole measurement is void."""
    assert variance.freeze_problems(runs) == []


def test_each_run_is_a_finished_grading_of_the_pinned_corpus(runs):
    for run in runs:
        assert gold._identity_problems(run["payload"]) == [], run["label"]


def test_the_repeats_are_where_the_workflow_puts_them(repeat_grade_files):
    """One canonical run and two forked repeats, not three loose files.

    ``--run-ordinal`` forks the output path above the shard fork, so run 1
    keeps the canonical location and every later repeat lands under
    ``_repeats/run-NNN/``. Nothing inside a payload records which repeat it is,
    so if these files were moved or renamed the report would lose the only
    thing that tells them apart.
    """
    ordinals = sorted(variance.run_label(path) for path in repeat_grade_files)

    assert ordinals == ["run 1", "run 2", "run 3"], ordinals


def test_the_report_names_every_file_it_read(report_text, repeat_grade_files):
    """A reader has to be able to open all three runs for themselves."""
    for path in repeat_grade_files:
        assert str(path.relative_to(REPO_ROOT)) in report_text


# ── The freeze, read out of the runs rather than the plan ──────────────────


@pytest.mark.parametrize("description,field", variance.FROZEN_FIELDS)
def test_the_report_records_what_was_held_still(
    description, field, report_text, runs
):
    """Every field the tool refuses on has to be legible in the report.

    Parametrised over the tool's own list so that freezing something new
    without recording it fails here rather than passing quietly.

    Only scalar fields can be checked as text -- ``judge``, ``prompt`` and the
    rest are nested objects, and demanding their JSON appear verbatim would be
    asserting a formatting choice. For those it is enough that the report names
    the thing; the tool has already proved the values agree.
    """
    value = runs[0]["payload"].get(field)
    needle = str(value) if isinstance(value, str) else description.split()[0]

    assert needle in report_text, (
        f"the report does not record the {description} it froze "
        f"({field}={needle!r})"
    )


def test_the_report_records_the_container_all_three_ran_in(report_text):
    digests = {
        match.group("image")
        for match in CONTAINER_IMAGE.finditer(
            WORKFLOW_PATH.read_text(encoding="utf-8")
        )
    }

    assert len(digests) == 1, (
        f"grade-run.yml pins more than one grading image: {sorted(digests)}. "
        "There is no single container for the report to record."
    )
    assert digests.pop() in report_text


def test_the_report_records_the_office_suite_that_rendered(report_text, runs):
    for run in runs:
        renderer = run["payload"].get("renderer_fingerprint") or {}
        assert renderer["libreoffice_version"] in report_text, run["label"]


def test_the_report_says_the_azure_route_was_not_frozen(report_text, runs):
    """The one deliberate hole in the freeze has to be stated out loud.

    Grading is sharded across Azure endpoints and the merge step unions their
    fingerprints by design; even a four-task run has been seen to observe two.
    So route identity is reported and never gated -- gating it would fail
    closed on stage 1's own accepted run. A reader who is not told this would
    reasonably assume it was frozen along with everything else.
    """
    observed = {
        route.get("runtime_fingerprint")
        for run in runs
        for route in run["payload"].get("azure_ai_routes") or []
        if isinstance(route, dict)
    }
    observed.discard(None)

    assert "azure_ai_routes" in report_text, (
        "the report does not mention the routes, so it does not say which "
        "part of the environment was left free to vary"
    )
    for fingerprint in observed:
        assert fingerprint in report_text, fingerprint


# ── The numbers are the tool's, not a person's ─────────────────────────────


def test_every_generated_block_still_matches_its_command(report_text):
    """Re-run what the report says it ran, and demand the same output.

    This is the whole point of the file. A number edited by hand, a threshold
    moved, a payload replaced -- any of them changes this output and fails here
    rather than sitting in a document nobody re-derives.
    """
    blocks = list(GENERATED_MARKER.finditer(report_text))
    assert blocks, (
        "the report carries no generated block. It should quote "
        "analyze_variance.py rather than restate it, marked with "
        "<!-- generated: <command> --> above a ```text fence."
    )

    for block in blocks:
        command = shlex.split(block.group("command"))
        assert command[0] in {"python", "python3"}, command
        assert command[1] == "batch-runner/scripts/analyze_variance.py", command

        finished = subprocess.run(
            [sys.executable, *command[1:]],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        # Exit status 1 means a gate was missed, which is a legitimate thing
        # for the report to be quoting. Only a crash is a problem here.
        assert finished.returncode in (0, 1), finished.stderr

        assert finished.stdout.strip() == block.group("body").strip(), (
            f"the block generated by `{block.group('command')}` no longer "
            "matches what that command prints"
        )


def test_the_three_thresholds_are_stated_against_their_bars(report_text):
    """The acceptance criteria are three numbers; all three go in."""
    for bar in (
        str(variance.TASK_PCT_STDEV_CEILING),
        str(variance.CI95_WIDTH_CEILING_PCT),
        "2%",
    ):
        assert bar in report_text, bar


def test_a_verdict_is_recorded_against_the_thresholds(report_text, runs):
    """The report must say whether stage 2 passed, and agree with the tool."""
    passed = variance.analyze(runs)["all_gates_met"]

    lowered = report_text.lower()
    if passed:
        assert "pass" in lowered
    else:
        assert "miss" in lowered


def test_the_worst_moving_task_is_named(report_text, runs):
    """The gate is decided by one task, so the report has to name it.

    A stage that reports only an average hides the case the acceptance
    criterion is actually about.
    """
    stability = variance.task_stability(runs, variance.per_task_scores(runs))
    ranked = sorted(
        (row for row in stability if row["stdev_pct"] is not None),
        key=lambda row: row["stdev_pct"],
        reverse=True,
    )
    assert ranked, "no task had a deviation to report"

    assert str(ranked[0]["task_id"]) in report_text, (
        f"the task that decided the deviation gate ({ranked[0]['task_id']}, "
        f"{ranked[0]['stdev_pct']}pp) is not named in the report"
    )


# ── What the tool cannot say ───────────────────────────────────────────────


def test_the_departure_from_the_specification_is_disclosed(report_text):
    """The spec asked for an exp003 subset; this graded the gold corpus.

    Reusing stage 1's accepted run as run 1 is what makes the headline number
    of stage 1 the thing whose stability is being measured, and it saves a
    third paid run. Both are good reasons and neither excuses leaving the
    substitution out of the report.
    """
    assert "exp003" in report_text, (
        "the specification names an exp003 subset as the corpus. This stage "
        "graded stage 1's gold thirty instead, and a reader comparing the "
        "report to the spec has to be told why."
    )


def test_the_bill_is_honest_about_what_is_unpriced(report_text, runs):
    for run in runs:
        cost = (run["payload"]["summary"] or {}).get("cost") or {}
        if cost.get("pricing_complete"):
            assert str(cost["estimated_cost_usd"]) in report_text, run["label"]
            continue
        assert "pricing_complete" in report_text
        for model in cost.get("unpriced_models") or []:
            assert model in report_text, model

    assert not re.search(r"\$0(?![.\d])", report_text), (
        "the report writes $0 for a run whose models have no published price. "
        "Unknown is not free."
    )


# ── Both halves must survive a fresh clone ─────────────────────────────────


@pytest.mark.parametrize(
    "relative",
    [
        "tasks/rebuilding_grading_task/PR3_VARIANCE.md",
        "batch-runner/scripts/analyze_variance.py",
    ],
)
def test_the_report_and_its_tool_are_in_the_repository(relative):
    """``tasks/**`` and ``batch-runner/scripts/*`` are both ignored by default.

    Each needs an explicit allow-list line, and a missing one leaves the file
    working for whoever wrote it and absent for everyone else.
    """
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", relative],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert tracked.returncode == 0, (
        f"{relative} is not tracked, so a fresh clone would not have it. Add "
        "it to the allow list in .gitignore."
    )


def test_the_specification_points_at_the_report():
    """The spec names the file it expects; a rename must break here."""
    spec = SPEC_PATH.read_text(encoding="utf-8")

    assert "PR3_VARIANCE.md" in spec
