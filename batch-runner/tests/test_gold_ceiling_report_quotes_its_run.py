"""The stage-1 report has to quote its run rather than restate it.

A report that retypes numbers is a report that can drift from the run it
describes, and nobody reading it afterwards can tell. So the report carries the
analysis tool's own output inside a fenced block, together with the command
that produced it, and this re-runs that command against the committed grade
file and demands the block still match.

That makes three separate things checkable at once: the grade file the report
names is really stage 1's pinned run, the numbers in the report are that run's
numbers, and the command a reader would type to reproduce them is the command
that was actually typed.

The rest of the file covers what the specification requires the report to say
in prose and no tool can generate: which shortfalls are the reading tool's
format gap rather than a grading defect, and an honest bill for a run whose
models have no published price.

It also holds the report to recording all six things stage 1 froze -- the task
list, the gold bytes, the grading config, the grader source, the container
image and the LibreOffice version. That is not bookkeeping. Stage 2 measures
how much a score moves across identical repeats, and "identical" is only
checkable against fingerprints this report wrote down; a repeat that cannot be
proved to match is a repeat that measures nothing.
"""

import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys

import pytest
import yaml

from scripts import analyze_gold_ceiling as analysis


REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = REPO_ROOT / "tasks/rebuilding_grading_task/PR3_GOLD_CEILING.md"
SPEC_PATH = REPO_ROOT / "tasks/rebuilding_grading_task/300-gold-ceiling.md"
DIAGNOSTIC_ROOT = REPO_ROOT / "data/grades/_diagnostic"
WORKFLOW_PATH = REPO_ROOT / ".github/workflows/grade-run.yml"
CONFIG_PATH = (
    REPO_ROOT / "batch-runner/grading_configs/gold_ceiling_30_v2_sol_max.yaml"
)
MANIFEST_PATH = (
    REPO_ROOT
    / "batch-runner/experiments/gold_corpus/gold_deliverable_manifest.json"
)
CONTAINER_IMAGE = re.compile(
    r"image:\s*(?P<image>ghcr\.io/\S+@sha256:(?P<digest>[0-9a-f]{64}))"
)

# The gold answer the specification named before the run as the one it expected
# to score badly: a 179.7 MB zip holding five WAV stems. The prediction held --
# 2.00 of 62 -- but its stated reason did not. The formats inside were all
# supported; the container was not, so nothing opened it. `read_deliverable.py`
# reads archives now, which is why this task is worth naming: the report has to
# say what it scored after the fix, and which of its items are still out of
# reach because routing and selection see one file with a `.zip` extension.
UNREADABLE_DELIVERABLE_TASK_ID = "38889c3b-e3d4-49c8-816a-3cc8e5313aba"

# How the report marks the block it generated and the command behind it.
GENERATED_MARKER = re.compile(
    r"<!--\s*generated:\s*(?P<command>.+?)\s*-->\s*\n```text\n(?P<body>.*?)\n```",
    re.DOTALL,
)


def _gold_grade_files() -> list[Path]:
    """Stage 1's corpus, fully graded, by the grader that stands today.

    Three things have to be filtered out, and each would otherwise look exactly
    like the run this report quotes.

    Shards, because a shard declares the whole corpus in its identity fields
    while holding one slice of it -- so it carries the pinned fingerprint too,
    and only its ``run_status`` gives it away.

    Repeats, because stage 3 of `303-variance-and-error.md` grades these same
    thirty tasks twice more to measure how far a score drifts. Those repeats are
    complete, they are the same corpus, and they are committed under
    ``_repeats/run-NNN/``. Nothing in the payload says which repeat it is --
    ``run_ordinal`` reaches the output path and is never written into the file
    or the schema -- so the directory is the only place that knows, and this has
    to read it there.

    Superseded runs, because the specification's closing instruction is to fix a
    defect, verify the fix and grade again -- so a corpus this size can end up
    with more than one finished run against it, differing only in the grader
    that produced them. Stage 1's first run graded through a reading tool that
    could not open a zip or see a PowerPoint table, chart or group; those are
    fixed, and the run that measured the broken tool is evidence of the defect
    rather than an answer to stage 1's question. It stays in the repository,
    under ``_superseded/``, because the report's claim about what the fix
    recovered is only checkable against it. But it is not a candidate, and the
    ``grader_source_hash`` in its filename is the only thing that distinguishes
    it from the current run -- which is a difference no reader would spot and no
    assertion here could describe. The directory is what says so out loud.
    """
    found = []
    for path in sorted(DIAGNOSTIC_ROOT.rglob("*.json")):
        if "_repeats" in path.parts or "_superseded" in path.parts:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        if (
            payload.get("expected_ordered_task_ids_sha256")
            == analysis.EXPECTED_ORDERED_TASK_IDS_SHA256
            and payload.get("run_status") in analysis.COMPLETE_RUN_STATUSES
        ):
            found.append(path)
    return found


@pytest.fixture(scope="module")
def gold_grade_file() -> Path:
    files = _gold_grade_files()
    assert files, (
        "no committed grade payload under data/grades/_diagnostic/ carries the "
        f"pinned fingerprint {analysis.EXPECTED_ORDERED_TASK_IDS_SHA256} as a "
        "finished run. Stage 1's report cannot quote a run that is not in the "
        "repository."
    )
    assert len(files) == 1, (
        "more than one committed payload claims to be stage 1's run, so the "
        f"report would be ambiguous about which it quotes: {files}. If one of "
        "them was graded by a grader that has since been fixed, move it under "
        "_superseded/ -- keeping it as evidence, but not as an answer."
    )
    return files[0]


@pytest.fixture(scope="module")
def report_text() -> str:
    assert REPORT_PATH.is_file(), (
        f"{REPORT_PATH.relative_to(REPO_ROOT)} is missing. The specification's "
        "'기록할 것' section requires it."
    )
    return REPORT_PATH.read_text(encoding="utf-8")


# ── The run the report quotes is the run that was pinned ───────────────────


def test_the_quoted_run_is_the_pinned_one(gold_grade_file):
    payload = json.loads(gold_grade_file.read_text(encoding="utf-8"))

    assert analysis._identity_problems(payload) == []


def test_the_report_names_the_file_it_read(report_text, gold_grade_file):
    """A reader has to be able to open the run for themselves."""
    assert str(gold_grade_file.relative_to(REPO_ROOT)) in report_text


def test_the_report_records_what_was_frozen(report_text, gold_grade_file):
    """Container, renderer and grader source are the freeze, so they go in.

    Each is read back out of the payload the run itself wrote, not out of the
    plan -- that is the difference between recording what ran and recording
    what was meant to run.
    """
    payload = json.loads(gold_grade_file.read_text(encoding="utf-8"))
    renderer = payload.get("renderer_fingerprint") or {}

    assert payload["grader_source_hash"] in report_text
    assert renderer["libreoffice_version"] in report_text


def test_the_report_records_the_container_it_ran_in(report_text):
    """The image digest lives in the workflow, so it is read from there.

    Stage 2 has to prove its repeats ran in the same container as this run, and
    it can only do that against a digest this report actually wrote down. Both
    of the workflow's container declarations are checked to agree first --
    quoting one of two divergent pins would record a container that graded only
    half the corpus.
    """
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
    image = digests.pop()
    assert image in report_text, (
        f"the report does not record the container it ran in ({image}), so a "
        "stage 2 repeat cannot be proved to have run in the same one"
    )


def test_the_report_records_the_frozen_input_fingerprints(report_text):
    """Which 30 tasks, and which bytes of gold answer, both by fingerprint.

    Both are recomputed here from the committed config and manifest rather than
    compared to a constant, so the report is checked against the corpus itself.

    The two are not the same kind of number, and the report should not imply
    they are. The task-id digest is the *grader's*: `step8_grade` writes it into
    every payload and names the output directory after it, so it is recomputed
    through that same function here and a stage 2 repeat can be compared to it
    field-for-field. The gold-file digest has no counterpart in the payload --
    nothing in the pipeline fingerprints the answer bytes as a set -- so it is
    defined by the specification, ``graded_path\\tsha256\\tsize`` per file in
    task order, newline-joined, and is only ever compared against itself.
    """
    from step8_grade import _ordered_task_ids_sha256

    pinned = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))[
        "rerun_identity"
    ]["task_ids"]
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    by_task = {task["task_id"]: task for task in manifest["tasks"]}

    ordered = _ordered_task_ids_sha256(pinned)
    gold_files = hashlib.sha256(
        "\n".join(
            f"{entry['graded_path']}\t{entry['sha256']}\t{entry['size']}"
            for task_id in pinned
            for entry in by_task[task_id]["files"]
        ).encode("utf-8")
    ).hexdigest()

    assert ordered in report_text, "the report does not say which 30 tasks these were"
    assert gold_files in report_text, (
        "the report does not fingerprint the gold answers it graded, so a "
        "stage 2 repeat cannot prove it graded the same bytes"
    )


# ── The numbers are the tool's, not a person's ─────────────────────────────


def test_every_generated_block_still_matches_its_command(report_text, gold_grade_file):
    """Re-run what the report says it ran, and demand the same output.

    This is the whole point of the file. A number edited by hand, a threshold
    moved, a payload replaced -- any of them changes this output and fails
    here rather than sitting in a document nobody re-derives.
    """
    blocks = list(GENERATED_MARKER.finditer(report_text))
    assert blocks, (
        "the report carries no generated block. It should quote "
        "analyze_gold_ceiling.py rather than restate it, marked with "
        "<!-- generated: <command> --> above a ```text fence."
    )

    for block in blocks:
        command = shlex.split(block.group("command"))
        assert command[0] in {"python", "python3"}, command
        assert command[1] == "batch-runner/scripts/analyze_gold_ceiling.py", command

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
    """The specification asks for each number *versus* its threshold."""
    for bar in ("90", "0.95", "2%"):
        assert bar in report_text


# ── Image and audio, counted apart ─────────────────────────────────────────


def test_the_perception_split_in_the_report_is_the_run_s_split(
    report_text, gold_grade_file
):
    """`summary.cost` only carries the sum; the split has to be derived."""
    payload = json.loads(gold_grade_file.read_text(encoding="utf-8"))
    by_modality = analysis.perception_calls_by_modality(payload)

    for modality, calls in by_modality.items():
        assert f"{modality}" in report_text, modality
        assert str(calls) in report_text, (modality, calls)

    total = (payload["summary"]["cost"] or {}).get("total_perception_calls")
    assert sum(by_modality.values()) == total, (
        "the per-modality counts do not add up to the run's own total, so one "
        "of the two is wrong and the report would publish the discrepancy"
    )


# ── Every shortfall is classified by a person ──────────────────────────────


def test_the_pre_disclosed_unreadable_answer_is_accounted_for(report_text):
    """The zip was called out before the run; the report has to close it.

    Saying in advance that a task cannot be read and then not saying how it
    scored is the one way that disclosure becomes worthless.
    """
    assert UNREADABLE_DELIVERABLE_TASK_ID in report_text
    assert "zip" in report_text.lower()


def test_every_task_that_lost_points_is_named(report_text, gold_grade_file):
    """A shortfall left out of the report is a shortfall nobody classified."""
    payload = json.loads(gold_grade_file.read_text(encoding="utf-8"))
    lost_points = {
        str(row["task_id"]) for row in analysis.items_below_full_marks(payload)
    }

    missing = sorted(task_id for task_id in lost_points if task_id not in report_text)
    assert not missing, (
        f"{len(missing)} task(s) scored below full marks and are not mentioned "
        f"anywhere in the report: {missing[:5]}"
    )


def test_a_verdict_is_recorded_against_the_thresholds(report_text, gold_grade_file):
    """The report must say whether stage 1 passed, and agree with the tool."""
    payload = json.loads(gold_grade_file.read_text(encoding="utf-8"))
    passed = analysis.analyze(payload)["all_gates_met"]

    lowered = report_text.lower()
    if passed:
        assert "pass" in lowered
    else:
        # A missed gate has to be classified, per the specification's last line:
        # grader defect, input defect, or tool defect.
        assert "miss" in lowered
        assert any(
            word in lowered for word in ("grader", "input", "tool")
        ), "a missed threshold has to be classified as grader, input or tool"


# ── An unpriced run is never reported as free ──────────────────────────────


def test_the_bill_is_honest_about_what_is_unpriced(report_text, gold_grade_file):
    payload = json.loads(gold_grade_file.read_text(encoding="utf-8"))
    cost = payload["summary"]["cost"] or {}

    if cost.get("pricing_complete"):
        assert str(cost["estimated_cost_usd"]) in report_text
        return

    assert "pricing_complete" in report_text
    assert "false" in report_text.lower()
    for model in cost.get("unpriced_models") or []:
        assert model in report_text, model
    assert not re.search(r"\$0(?![.\d])", report_text), (
        "the report writes $0 for a run whose models have no published price. "
        "Unknown is not free, and the specification forbids this spelling."
    )


# ── Both halves must survive a fresh clone ─────────────────────────────────


@pytest.mark.parametrize(
    "relative",
    [
        "tasks/rebuilding_grading_task/PR3_GOLD_CEILING.md",
        "batch-runner/scripts/analyze_gold_ceiling.py",
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

    assert "PR3_GOLD_CEILING.md" in spec
