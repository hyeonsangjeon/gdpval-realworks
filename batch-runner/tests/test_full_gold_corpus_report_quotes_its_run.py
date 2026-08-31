"""The stage-3 report has to quote its run rather than restate it.

Same contract as stage 1's report, for the same reason: a report that retypes
numbers can drift from the run it describes and nobody reading it afterwards
can tell. The report carries the analysis tool's own output inside a fenced
block together with the command that produced it, and this re-runs that command
against the committed grade file and demands the block still match.

Stage 3 adds one thing stage 1 did not have to worry about. There are now two
pinned corpora -- the 30-task sample and the 185-task population -- and a
payload from either satisfies `_identity_problems`. The module-level
`EXPECTED_ORDERED_TASK_IDS_SHA256` still aliases stage 1, so every check here
goes through `analysis.STAGE_THREE_CORPUS` explicitly. Reaching for the alias
would quote stage 1's run under stage 3's title and every assertion below would
still pass.

The rest holds the report to the seven things `304-full-gold-corpus.md` lists
under 「기록할 것」, each checked against the run rather than against a constant:
the three thresholds and what was scored against them, the same thirty rescored
so stage 1 and stage 3 are comparable, the sector and occupation breakdown, the
mean with and without the five declared limits, a classification of every
shortfall, the per-modality judging counts, and a bill that says unpriced
instead of free.

The last group goes the other way, holding the *specification* to the run. The
run turned up a sixth limit nobody predicted, and the value of the five that
were predicted rests entirely on their having been written down first -- so the
line between what was foreseen and what was found is checked as a line, not
left to whoever edits the table next.
"""

import collections
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
REPORT_PATH = REPO_ROOT / "tasks/rebuilding_grading_task/PR3_FULL_GOLD_CORPUS.md"
SPEC_PATH = REPO_ROOT / "tasks/rebuilding_grading_task/304-full-gold-corpus.md"
DIAGNOSTIC_ROOT = REPO_ROOT / "data/grades/_diagnostic"
WORKFLOW_PATH = REPO_ROOT / ".github/workflows/grade-run.yml"
CONFIG_PATH = (
    REPO_ROOT / "batch-runner/grading_configs/gold_ceiling_185_v2_sol_max.yaml"
)
MANIFEST_PATH = (
    REPO_ROOT
    / "batch-runner/experiments/gold_corpus/gold_deliverable_manifest.json"
)

#: The corpus this report is allowed to be about. Named rather than taken from
#: the module aliases, which still point at stage 1.
CORPUS = analysis.STAGE_THREE_CORPUS

CONTAINER_IMAGE = re.compile(
    r"image:\s*(?P<image>ghcr\.io/\S+@sha256:(?P<digest>[0-9a-f]{64}))"
)

# How the report marks the block it generated and the command behind it.
GENERATED_MARKER = re.compile(
    r"<!--\s*generated:\s*(?P<command>.+?)\s*-->\s*\n```text\n(?P<body>.*?)\n```",
    re.DOTALL,
)

# Names a Python traceback leaves in an evidence string when the judge could
# not open a file at all. Used to make the report account for a task that
# scored nothing in the run's own words rather than in words chosen here.
FAULT_NAME = re.compile(r"\b([A-Z][A-Za-z]*(?:Error|Exception|File))\b")


def _stage_three_grade_files() -> list[Path]:
    """The 185-task corpus, fully graded, by the grader that stands today.

    Shards are the thing this has to exclude, and they are the hardest to
    exclude by inspection: a shard writes the whole corpus's fingerprint and
    task count into its identity fields while holding a stride of it, so the
    only field that gives one away is ``run_status``. All 31 of stage 3's
    committed shard payloads are ``partial``; the merged run is the one
    ``final``.

    Repeats and superseded runs are skipped by directory for the reasons
    stage 1's equivalent sets out -- nothing inside a repeat's payload says
    which repeat it is, and a run graded by a since-fixed grader differs from
    the current one only by the source hash in its filename.
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
            == CORPUS.ordered_task_ids_sha256
            and payload.get("run_status") in analysis.COMPLETE_RUN_STATUSES
        ):
            found.append(path)
    return found


@pytest.fixture(scope="module")
def grade_file() -> Path:
    files = _stage_three_grade_files()
    assert files, (
        "no committed grade payload under data/grades/_diagnostic/ carries "
        f"{CORPUS.key}'s fingerprint {CORPUS.ordered_task_ids_sha256} as a "
        "finished run. Stage 3's report cannot quote a run that is not in the "
        "repository. Eleven shards that each say 'partial' are not one."
    )
    assert len(files) == 1, (
        "more than one committed payload claims to be stage 3's run, so the "
        f"report would be ambiguous about which it quotes: {files}. If one of "
        "them was graded by a grader that has since been fixed, move it under "
        "_superseded/ -- keeping it as evidence, but not as an answer."
    )
    return files[0]


@pytest.fixture(scope="module")
def payload(grade_file: Path) -> dict:
    return json.loads(grade_file.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def report(payload: dict) -> dict:
    return analysis.analyze(payload)


@pytest.fixture(scope="module")
def report_text() -> str:
    assert REPORT_PATH.is_file(), (
        f"{REPORT_PATH.relative_to(REPO_ROOT)} is missing. The specification's "
        "'기록할 것' section requires it."
    )
    return REPORT_PATH.read_text(encoding="utf-8")


# ── The run the report quotes is the run that was pinned ───────────────────


def test_the_quoted_run_is_the_pinned_one(payload):
    assert analysis._identity_problems(payload) == []


def test_the_quoted_run_is_stage_threes_corpus_and_not_stage_ones(payload):
    """Both corpora are pinned now, so 'a pinned run' is no longer enough.

    `_identity_problems` passes a stage 1 payload just as happily, and every
    other assertion in this file is a substring check that a 30-task report
    would also satisfy. This is the one place that says which of the two.
    """
    assert analysis.identify_corpus(payload) is CORPUS
    assert payload["summary"]["graded_tasks"] == CORPUS.task_count == 185


def test_the_report_names_the_file_it_read(report_text, grade_file):
    """A reader has to be able to open the run for themselves."""
    assert str(grade_file.relative_to(REPO_ROOT)) in report_text


def test_the_report_gives_the_digest_of_the_run_and_of_its_ledger(
    report_text, grade_file
):
    """The reproduction block's two hashes, recomputed from the bytes on disk.

    Everything else here is derived: the generated block comes out of the tool,
    the gate values come out of the payload. These two are typed, and a typed
    hash is the one thing in the report that can go stale without any other
    check noticing -- which is exactly what happened once. The report was
    written against a hand merge; the workflow then published its own file with
    one later `graded_at`, the scores identical and the digest not. Every other
    assertion in this module still passed.
    """
    ledger = grade_file.with_name(grade_file.stem + ".cost_ledger.jsonl")
    for path, label in ((grade_file, "grade file"), (ledger, "cost ledger")):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest in report_text, (
            f"the report does not carry the {label}'s digest ({digest}). "
            f"Recompute it from {path.relative_to(REPO_ROOT)} -- a stale hash "
            "sends a reader to verify against bytes that are not there."
        )


def test_the_report_records_what_was_frozen(report_text, payload):
    """Grader source and renderer are the freeze, read from the run itself.

    Both come out of the payload the run wrote rather than out of the plan --
    that is the difference between recording what ran and recording what was
    meant to run. The grader source hash matters more here than it did in
    stage 1: it changed between the two runs, so the report's split of 82.87
    into "the grader moved" and "the corpus widened" only means something
    against the hash it is splitting.
    """
    renderer = payload.get("renderer_fingerprint") or {}

    assert payload["grader_source_hash"] in report_text
    assert renderer["libreoffice_version"] in report_text


def test_the_report_records_the_container_it_ran_in(report_text):
    """The image digest lives in the workflow, so it is read from there.

    Both of the workflow's container declarations are checked to agree first --
    quoting one of two divergent pins would record a container that graded only
    part of the corpus.
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
        "later run cannot be proved to have run in the same one"
    )


def test_the_report_records_the_frozen_input_fingerprints(report_text):
    """Which 185 tasks, and which bytes of gold answer, both by fingerprint.

    Recomputed here from the committed config and manifest rather than compared
    to a constant, so the report is checked against the corpus itself and the
    623 MB of source files are not needed to do it.

    The two are not the same kind of number. The task-id digest is the
    *grader's*: `step8_grade` writes it into every payload and names the output
    directory after it. The gold-file digest has no counterpart in the payload
    -- nothing in the pipeline fingerprints the answer bytes as a set -- so it
    is defined by the specification, ``graded_path\\tsha256\\tsize`` per file in
    task order, newline-joined, and is only ever compared against itself.
    """
    from step8_grade import _ordered_task_ids_sha256

    pinned = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))[
        "rerun_identity"
    ]["task_ids"]
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    by_task = {task["task_id"]: task for task in manifest["tasks"]}

    assert len(pinned) == CORPUS.task_count

    ordered = _ordered_task_ids_sha256(pinned)
    gold_files = hashlib.sha256(
        "\n".join(
            f"{entry['graded_path']}\t{entry['sha256']}\t{entry['size']}"
            for task_id in pinned
            for entry in by_task[task_id]["files"]
        ).encode("utf-8")
    ).hexdigest()

    assert ordered == CORPUS.ordered_task_ids_sha256
    assert ordered in report_text, "the report does not say which 185 tasks these were"
    assert gold_files in report_text, (
        "the report does not fingerprint the gold answers it graded, so a "
        "later run cannot prove it graded the same bytes"
    )


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
        # for the report to be quoting -- and stage 3 missed two. Only a crash
        # is a problem here.
        assert finished.returncode in (0, 1), finished.stderr

        assert finished.stdout.strip() == block.group("body").strip(), (
            f"the block generated by `{block.group('command')}` no longer "
            "matches what that command prints"
        )


def test_the_three_thresholds_are_stated_against_their_bars(report_text):
    """The specification asks for each number *versus* its threshold."""
    for bar in ("90", "0.95", "2%"):
        assert bar in report_text


def test_each_gate_is_reported_with_the_value_the_tool_computed(report_text, report):
    """The prose has to carry the scores, not just the quoted block.

    The generated block already holds every one of these, so on its own this
    would be redundant. It is not redundant against the prose: a reader reads
    the sentences, and a sentence that rounds 79.53 to 'about 80' or leaves
    the required-item rate out entirely is the drift this whole file exists
    to catch.

    The error rate is allowed either spelling. The tool prints the ratio
    (0.0065) and the threshold is written as a percentage (2%), so a report
    that says 0.65% is being clearer than one that repeats the ratio, and
    demanding the ratio would push the prose the wrong way.
    """
    for name, gate in report["gates"].items():
        value = gate["value"]
        spellings = {str(value), str(round(value * 100, 2))}
        assert any(spelling in report_text for spelling in spellings), (
            f"the report never states the {name} the tool computed "
            f"({value}); looked for any of {sorted(spellings)}"
        )


# ── Stage 1 and stage 3 have to be comparable ──────────────────────────────


def test_the_same_thirty_are_rescored_so_the_two_stages_are_comparable(
    report_text, report
):
    """82.87 and 79.53 cannot be subtracted; the specification says so.

    The grader source changed between the runs, so the difference between the
    two headline numbers mixes "the grader moved" with "the corpus widened".
    Stage 1's thirty are the first thirty of these 185 in the same order, which
    is what makes the split possible at all -- so the report has to carry the
    rescored figure, and the subset has to be the verified one rather than a
    thirty that merely happens to be thirty.
    """
    subset = report["subsets"]["stage_one_same_thirty"]

    assert subset["verified"] is True, (
        "the tool could not confirm that stage 1's thirty sit inside this run "
        "in the same order, so the two stages cannot be placed side by side"
    )
    assert (
        subset["ordered_task_ids_sha256"]
        == analysis.STAGE_ONE_CORPUS.ordered_task_ids_sha256
    )
    assert str(subset["avg_pct"]) in report_text, (
        "the report never says what stage 1's thirty scored inside this run "
        f"({subset['avg_pct']}), so the reader is left subtracting two numbers "
        "produced by different graders"
    )


def test_the_mean_is_given_with_and_without_the_declared_limits(report_text, report):
    """Both sides of the subtraction, which is what the specification asks.

    Publishing only the held-out mean would be picking the flattering number;
    publishing only the whole-corpus mean would leave the pre-registered
    disclosure unanswered. The five-task mean goes in too -- it is the one that
    says how bad the declared limits actually were.
    """
    subsets = report["subsets"]

    for key in ("known_limits_only", "without_known_limits"):
        assert subsets[key]["missing"] == [], (
            f"{key} could not match every declared limit task: "
            f"{subsets[key]['missing']}"
        )
        assert subsets[key]["ambiguous"] == [], subsets[key]["ambiguous"]

    for value in (
        report["gates"]["mean_score_pct"]["value"],
        subsets["known_limits_only"]["avg_pct"],
        subsets["without_known_limits"]["avg_pct"],
    ):
        assert str(value) in report_text, (
            f"the report does not state {value}, so the effect of holding the "
            "declared limits out cannot be read off it"
        )


def test_every_declared_limit_task_is_answered(report_text):
    """Naming a task in advance and then not saying how it scored is worthless.

    The five were listed in `304-full-gold-corpus.md` before any money was
    spent, precisely so that their contribution could not be argued about
    afterwards. Each has to appear.
    """
    missing = [
        task_id
        for task_id in analysis.KNOWN_LIMIT_TASK_IDS
        if task_id not in report_text
    ]
    assert not missing, (
        f"declared before the run and unanswered after it: {missing}"
    )


# ── Where the ceiling is held down ─────────────────────────────────────────


def test_every_sector_and_occupation_has_its_mean_in_the_report(report_text, report):
    """The specification asks where the ceiling is dragged down, by both cuts.

    Occupation is the cut that stage 3 bought: stage 1 reached 7 of 44, and a
    nine-bucket sector average cannot show which of the 37 newly covered
    occupations moved the number. Every name has to be readable, which is also
    why the tool no longer clips them -- at 44 characters two of this corpus's
    occupations render as the same string.
    """
    for field in ("sector", "occupation"):
        names = sorted(
            {str(task[field]) for task in report["per_task"] if task.get(field)}
        )
        assert names, field
        missing = [name for name in names if name not in report_text]
        assert not missing, (
            f"{len(missing)} {field}(s) are graded in this run and named "
            f"nowhere in the report: {missing[:5]}"
        )


# ── Image and audio, counted apart ─────────────────────────────────────────


def test_the_perception_split_in_the_report_is_the_run_s_split(report_text, payload):
    """`summary.cost` only carries the sum; the split has to be derived."""
    by_modality = analysis.perception_calls_by_modality(payload)

    for modality, calls in by_modality.items():
        assert f"{modality}" in report_text, modality
        assert str(calls) in report_text, (modality, calls)

    total = (payload["summary"]["cost"] or {}).get("total_perception_calls")
    assert sum(by_modality.values()) == total, (
        "the per-modality counts do not add up to the run's own total, so one "
        "of the two is wrong and the report would publish the discrepancy"
    )


def test_every_model_that_was_billed_is_named(report_text, grade_file):
    """Read from the ledger, so a third model cannot bill in silence.

    The payload's `unpriced_models` is a list the grader assembled; the ledger
    is one row per call. If they ever disagree, the ledger is the one that
    charged money, and a report naming two models for a run that called three
    is understating what was spent.
    """
    ledger_path = grade_file.with_name(
        grade_file.stem + ".cost_ledger.jsonl"
    )
    assert ledger_path.is_file(), (
        f"{ledger_path.name} is not committed beside the grade file, so what "
        "the run actually called cannot be checked"
    )

    billed = collections.Counter()
    with ledger_path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("record_type") != "call":
                continue
            billed[row.get("resolved_model") or row.get("requested_model")] += 1

    assert billed, f"{ledger_path.name} records no calls"
    missing = sorted(model for model in billed if model and model not in report_text)
    assert not missing, (
        f"these models billed against the run and are named nowhere in the "
        f"report: {missing}"
    )


# ── Every shortfall is classified by a person ──────────────────────────────


def test_every_task_that_lost_points_is_named(report_text, payload):
    """A shortfall left out of the report is a shortfall nobody classified."""
    lost_points = {
        str(row["task_id"]) for row in analysis.items_below_full_marks(payload)
    }

    missing = sorted(task_id for task_id in lost_points if task_id not in report_text)
    assert not missing, (
        f"{len(missing)} task(s) scored below full marks and are not mentioned "
        f"anywhere in the report: {missing[:5]}"
    )


def test_a_task_that_scored_nothing_is_explained(report_text, payload, report):
    """Zero is the one score that cannot be left to the per-task listing.

    A task at 0.00 per cent is either the grader falling over or the input
    being broken, and those are opposite findings. The report has to name the
    task and carry the run's own account of why -- taken from the evidence the
    judge wrote, not from wording chosen here, so a different failure next time
    cannot be papered over with the same sentence.
    """
    by_task = {str(task.get("task_id")): task for task in payload.get("tasks") or []}

    for row in report["per_task"]:
        if row.get("pct") != 0:
            continue
        task_id = str(row["task_id"])
        assert task_id in report_text, (
            f"{task_id} scored nothing and is not named in the report"
        )

        evidence = " ".join(
            str(item.get("evidence") or "")
            for item in (by_task[task_id].get("items") or [])
        )
        faults = collections.Counter(FAULT_NAME.findall(evidence))
        if not faults:
            continue
        fault, _ = faults.most_common(1)[0]
        assert fault in report_text, (
            f"{task_id} scored nothing and the judge recorded {fault} against "
            "it, but the report does not say so -- a reader cannot tell an "
            "input defect from a grader defect"
        )


def test_a_verdict_is_recorded_against_the_thresholds(report_text, report):
    """The report must say whether stage 3 passed, and agree with the tool."""
    lowered = report_text.lower()

    if report["all_gates_met"]:
        assert "pass" in lowered or "통과" in report_text
        return

    # A missed gate has to be classified, per the specification: grader
    # defect, input defect, or tool defect.
    assert "미달" in report_text or "miss" in lowered
    assert any(
        word in report_text for word in ("채점기", "입력", "도구")
    ), "a missed threshold has to be classified as grader, input or tool"


# ── An unpriced run is never reported as free ──────────────────────────────


def test_the_bill_is_honest_about_what_is_unpriced(report_text, payload):
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
        "tasks/rebuilding_grading_task/PR3_FULL_GOLD_CORPUS.md",
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


def test_the_run_it_quotes_is_in_the_repository(grade_file):
    """The payload too -- the generated block is unreproducible without it."""
    relative = str(grade_file.relative_to(REPO_ROOT))
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", relative],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert tracked.returncode == 0, (
        f"{relative} is not tracked, so nobody else can re-run the command the "
        "report quotes"
    )


def test_the_specification_points_at_the_report():
    """The spec names the file it expects; a rename must break here."""
    spec = SPEC_PATH.read_text(encoding="utf-8")

    assert "PR3_FULL_GOLD_CORPUS.md" in spec


# ── The sixth limit was found, not foreseen ────────────────────────────────


#: Where the specification stops pre-registering and starts recording. Anything
#: above this line was written before money was spent; anything below it was
#: not.
POST_RUN_HEADING = "#### 실행 후 추가"


def test_the_sixth_limit_is_recorded_below_the_pre_registration_not_inside_it(
    payload,
):
    """A limit found afterwards must not be filed among the five foreseen.

    The 「알려진 입력 한계 (실행 전 공개)」 section says in its own first line
    why it exists: predicting a limit and explaining one after the fact are
    worth different amounts as evidence. Editing `0e386e32` into that table
    would quietly convert the second into the first, and every later reader
    would see six predictions where there were five.

    So the task is identified here the way the report identifies it -- as the
    corpus's only zero -- and the split is checked from both sides.
    """
    spec = SPEC_PATH.read_text(encoding="utf-8")

    zeros = [task for task in payload["tasks"] if task["pct"] == 0]
    assert len(zeros) == 1, (
        f"{len(zeros)} tasks scored zero; this check assumes the one the "
        "specification records. Re-read the run before editing the spec."
    )
    sixth = zeros[0]

    assert POST_RUN_HEADING in spec, (
        "the specification has no post-run section, so a limit discovered by "
        f"the run ({sixth['task_id']}) has nowhere to go that is not the "
        "pre-registered table"
    )
    foreseen, found = spec.split(POST_RUN_HEADING, 1)

    short = sixth["task_id"][:8]
    assert short not in foreseen, (
        f"{short} appears above {POST_RUN_HEADING!r}, among the limits "
        "declared before the run. It was not declared before the run -- the "
        "planner cannot open a file, which is the whole reason it was missed."
    )
    assert short in found, (
        f"{short} is the only task that scored nothing and the specification "
        "does not record it at all"
    )

    for value, label in (
        (len(sixth["items"] or []), "the number of rubric items it lost"),
        (sixth["total_max"], "the points it lost"),
    ):
        assert str(value) in found, (
            f"the post-run section does not state {label} ({value})"
        )


def test_the_specification_separates_the_five_from_the_six(payload, report):
    """Both subtractions, so the foreseen and the found stay distinguishable.

    Holding out the five answers the pre-registered disclosure. Holding out all
    six answers a different question -- how much of the shortfall is known
    limits of any kind -- and only the first was promised in advance. Publishing
    one without the other lets a reader mistake which is which.
    """
    spec = SPEC_PATH.read_text(encoding="utf-8")

    zeros = [task for task in payload["tasks"] if task["pct"] == 0]
    assert len(zeros) == 1
    held_out = tuple(analysis.KNOWN_LIMIT_TASK_IDS) + (zeros[0]["task_id"][:8],)

    remaining = [
        task
        for task in payload["tasks"]
        if not str(task["task_id"]).startswith(held_out)
    ]
    without_six = round(
        sum(task["pct"] for task in remaining) / len(remaining), 2
    )

    for value in (
        report["gates"]["mean_score_pct"]["value"],
        report["subsets"]["without_known_limits"]["avg_pct"],
        without_six,
    ):
        assert f"{value:.2f}" in spec, (
            f"the specification does not state {value:.2f}, so the effect of "
            "holding out the foreseen limits cannot be told apart from the "
            "effect of holding out the one that was not foreseen"
        )

    assert str(len(remaining)) in spec, (
        f"the specification does not say how many tasks are left ({len(remaining)}) "
        "once all six are held out"
    )


# ── The spec's claim about the READMEs has to be true of the READMEs ───────


def test_the_coverage_the_spec_quotes_is_the_coverage_the_readmes_publish():
    """The 「문서 정정」 section quotes both READMEs; both quotes must resolve.

    This paragraph used to assert the opposite -- that the READMEs said "11
    sectors, 55 occupations" and were wrong. They did not and were not; the
    correction had already landed. A claim about another file is worth no more
    than a check that reads that file, so this reads them.

    `README.md` wraps the phrase across two lines, so whitespace is collapsed
    before matching. A reflow must not be able to fail this.
    """
    spec = SPEC_PATH.read_text(encoding="utf-8")

    quotes = {
        "README.md": "220 tasks across 9 industry sectors and 44 occupations",
        "README_KR.md": "9개 산업, 44개 직종, 220개 태스크",
    }

    for name, phrase in quotes.items():
        assert phrase in spec, (
            f"the specification no longer quotes {name} as {phrase!r}; update "
            "this check together with the paragraph"
        )
        published = " ".join(
            (REPO_ROOT / name).read_text(encoding="utf-8").split()
        )
        assert phrase in published, (
            f"the specification attributes {phrase!r} to {name} and {name} "
            "does not say it. Either the README changed or the specification "
            "is describing a file it did not read."
        )


def test_the_file_the_spec_declines_to_correct_is_still_untracked():
    """`CLAUDE.md` is left alone because no reader of the repository sees it.

    That is the entire argument, and it stops holding the moment the file is
    committed. If it ever is, the paragraph has to change from "not ours to
    correct" to a correction.
    """
    tracked = subprocess.run(
        ["git", "ls-files", "--", "CLAUDE.md"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    assert not tracked.stdout.strip(), (
        "CLAUDE.md is tracked now, so the specification's reason for leaving "
        'its "11 sectors, 55 occupations" alone -- that nobody reading the '
        "repository can see it -- is no longer true"
    )
