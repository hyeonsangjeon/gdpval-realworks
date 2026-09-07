"""The 5.6-sol entry says the grading ledger survives now. It has to be true.

``models_deliberately_not_priced["azure:gpt-5.6-sol"]`` used to name two things
that would settle the model's price, the first being *publish the grading-side
per-call cost ledger*, which it described as written next to the grade file and
then dying with the runner. That stopped being true when PRs #272 and #327 added
the two ``git add`` calls that stage a ledger beside its grade. The entry now
says so, and records what reading those ledgers bought.

Every figure it records is recomputed here from the ledgers themselves, because
a measurement written into a file by hand is exactly the kind of number that
goes quietly stale -- which is the failure this whole entry is about.

Five things this file is careful about.

**Committed means tracked, not present.** The claim is about what someone gets
from a clone. A directory walk would also pass on a ledger that exists only in
this working tree, so the ledgers are checked with ``git ls-files``.

**Calls are counted by call_id, not by row.** Both the eleven per-shard ledgers
and the merged ledger built from them are committed, so every call in the merged
run is on disk twice and a row count overstates the calls by half. Counting rows
here would report 68,338 sol calls where 45,203 identifiers are distinct.

**Duplication is decomposed, not totalled.** The duplicate rows used to be
checked against a single number -- the merged ledger's row count -- on the
reading that the merge was the only thing that could duplicate a call. A second
cause turned up: three runs of the audio-repeat corpus minted identical
identifiers, so 1,039 rows sit under 355 names and 684 separately billed calls
are invisible. That is not the merge re-stating a call it already holds, and it
must not be able to hide inside one total. Each duplicate is therefore classified
from the paths it appears under, the merge class still has to equal the merged
ledger exactly, and an unclassified duplicate fails.
``step8_grade.make_cost_run_id`` stops new collisions; the ones already committed
are checked to be pre-fix, which is a condition a regression of that fix would
break.

**The measurement bounds the tier; it does not settle it.** Azure publishes no
context threshold for 5.6-sol, so this file asserts the model is still *unpriced*
alongside asserting the numbers. A future change that used these figures to give
5.6-sol a rate would fail here, which is the point.

**It measures a corpus, not the repository.** The figures come from the 33
ledgers pinned in ``gpt56sol_ledger_corpus.json`` by path and sha256, and that
file's own digest is stated in the entry. Reading them from a live walk of
``data/grades`` instead conflated a snapshot with a census: the 2026-09-07 smoke
published a 33rd ledger and three recorded figures went red without one of them
being wrong, and #448 restored green by hand. The contract asks for a smoke
whenever the grader fingerprint moves, so that edit was owed again on the next
one. What the live walk is still read for is the thing a count cannot say --
that no pinned ledger has left the tree -- and the surplus is reported rather
than compared to a number.
"""

import hashlib
import json
import subprocess
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

import pytest

from core.cost_receipts import load_receipt_price_table
from step8_grade import REPEAT_RUN_ID_SUFFIX, make_cost_run_id


REPO_ROOT = Path(__file__).resolve().parents[2]
PRICE_TABLE_PATH = (
    REPO_ROOT / "batch-runner/experiments/execution_envelope/model_price_table.json"
)
GRADES = REPO_ROOT / "data" / "grades"

#: The ledgers the entry's figures were measured from, pinned by path and digest.
#: Named by the entry itself, so the two cannot drift apart silently.
CORPUS_PATH = (
    REPO_ROOT
    / "batch-runner/experiments/execution_envelope/gpt56sol_ledger_corpus.json"
)

#: The model this file is about. Unpriced, and expected to stay that way.
MODEL = "gpt-5.6-sol"

#: The split Azure publishes for the 5.4 sibling. 5.6-sol has no published
#: threshold; this is the only nearby figure any measurement can be held against,
#: and the entry's bound is stated in terms of it.
SIBLING_CONTEXT_SPLIT = 272_000

#: Directory a shard of a run sits under, and the directory a repeat past the
#: first is written to (``step8_grade`` forks the output root on ``run_ordinal``).
SHARD_DIR = "_shards"
REPEAT_DIR = "_repeats"

#: The grader source the 185-task gold-ceiling run was published at. The dollar
#: bound below is that run's arithmetic, so the ledger is named rather than
#: assumed unique -- a re-grade forks beside it, which is what the fork is for.
GOLD_CEILING_SOURCE = "src_79c2f5035c4aa826"

MILLION = Decimal(1_000_000)


def _restate(field, recorded, recomputed):
    """Say what to write, so a stale figure is a correction and not a hunt."""
    return (
        f"{field}: the entry records {recorded!r}; the pinned corpus says "
        f"{recomputed!r}. Publishing a grade run no longer moves these -- the "
        f"figures are measured from the {CORPUS_PATH.name} list, not from a walk "
        "of data/grades -- so a disagreement here means a pinned ledger's bytes "
        "changed or the list was regenerated without re-measuring. Recompute, "
        f"re-read the prose, then write {recomputed!r} into "
        f"models_deliberately_not_priced['azure:{MODEL}']"
        f"['measured_from_committed_ledgers']['{field}']."
    )


def _load_table():
    return json.loads(PRICE_TABLE_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def entry():
    return _load_table()["models_deliberately_not_priced"][f"azure:{MODEL}"]


@pytest.fixture(scope="module")
def measured(entry):
    return entry["measured_from_committed_ledgers"]


@pytest.fixture(scope="module")
def corpus(measured):
    """The pinned list of ledgers every figure in the entry was measured from.

    Read through its digest rather than merely opened. The list is what stops a
    new receipt from turning correct figures red; the digest is what stops the
    list itself from growing quietly, which would put the counts back to being
    unchecked in a way no assertion below could see.
    """
    text = CORPUS_PATH.read_text(encoding="utf-8")
    actual = hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert actual == measured["corpus_sha256"], (
        f"{CORPUS_PATH.name} has been edited: the entry states "
        f"{measured['corpus_sha256']}, the file hashes to {actual}. If ledgers "
        "were deliberately added to the snapshot, re-measure every figure in "
        "measured_from_committed_ledgers, re-read the prose around them, and "
        "restate corpus_sha256. If they were not, this file changed under a "
        "measurement that still claims to describe it."
    )
    document = json.loads(text)
    assert document["measured_for"].startswith(
        "models_deliberately_not_priced['azure:gpt-5.6-sol']"
    ), "the corpus file no longer says which entry it belongs to"
    assert measured["corpus_file"].endswith(CORPUS_PATH.name), (
        "the entry names a different corpus file than this test reads"
    )
    return document


def _resolve_pinned(document, root):
    """The pinned ledgers as paths, refusing any that left the tree.

    Taken out of the fixture so a synthetic corpus can be pushed through the
    same code. A regression test that re-implements the resolution it guards
    proves only that two copies agree.
    """
    paths = [root / item["path"] for item in document["ledgers"]]
    missing = [str(p.relative_to(root)) for p in paths if not p.is_file()]
    assert not missing, (
        "the snapshot rests on ledgers that are no longer in the tree: "
        f"{missing}. A published receipt is not deleted; find where they went "
        "before touching any figure that was measured from them."
    )
    return paths


def _surplus(document, root, grades_dir):
    """Ledgers on disk the snapshot was not measured from.

    Returned rather than counted. The direction is the whole point: extra
    ledgers are the contract being honoured, a missing one is a published
    receipt that left the tree, and only the second is a failure.
    """
    on_disk = {
        str(p.relative_to(root)) for p in grades_dir.rglob("*.cost_ledger.jsonl")
    }
    pinned = {item["path"] for item in document["ledgers"]}
    assert pinned <= on_disk, (
        "pinned ledgers are missing from the tree: " + str(sorted(pinned - on_disk))
    )
    return sorted(on_disk - pinned)


def _rewritten(document, root):
    """Pinned ledgers whose bytes no longer hash to what was measured."""
    return [
        f"{item['path']}: {item['sha256']} -> {actual}"
        for item in document["ledgers"]
        for actual in [hashlib.sha256((root / item["path"]).read_bytes()).hexdigest()]
        if actual != item["sha256"]
    ]


@pytest.fixture(scope="module")
def ledger_paths(corpus):
    """The pinned ledgers, resolved to paths.

    This used to be ``GRADES.rglob("*.cost_ledger.jsonl")``. That made a
    measurement of a corpus indistinguishable from a description of the
    repository: the 2026-09-07 smoke published a 33rd ledger and three recorded
    figures went red without a single recorded figure being wrong. #448 restored
    them by hand. The contract asks for a smoke whenever the grader fingerprint
    moves, so the same edit was owed again on the next one.
    """
    return _resolve_pinned(corpus, REPO_ROOT)


@pytest.fixture(scope="module")
def calls(ledger_paths):
    """Distinct calls across every committed ledger, keyed by call_id.

    ``where`` keeps every ledger a call_id was seen in, because a bare duplicate
    count cannot say what caused the duplication and that turned out to matter.
    Insertion order follows ``ledger_paths``, so ``where[cid][0]`` is the ledger
    whose row ``by_id`` retained and the rest are the ones it shadowed.
    """
    by_id: dict[str, dict] = {}
    where: dict[str, list[Path]] = defaultdict(list)
    duplicates = 0
    rows = 0
    for path in ledger_paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rows += 1
            record = json.loads(line)
            call_id = record["call_id"]
            where[call_id].append(path)
            if call_id in by_id:
                duplicates += 1
            else:
                by_id[call_id] = record
    return {"by_id": by_id, "rows": rows, "duplicates": duplicates, "where": where}


def test_the_ledgers_are_committed_and_not_merely_on_disk(ledger_paths):
    """A clone has to get these files, or the entry's first condition is unmet."""
    for path in ledger_paths:
        relative = str(path.relative_to(REPO_ROOT))
        result = subprocess.run(
            ["git", "ls-files", "--error-unmatch", relative],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"not tracked by git: {relative}"


def test_the_entry_no_longer_says_the_ledger_dies_with_the_runner(entry):
    """The sentence this change exists to retire must not come back.

    Checked against the live wording rather than a stored copy: the claim is
    stale for as long as the ledgers are committed, whoever rewrites the text.
    """
    settle = entry["what_would_settle_it"]
    assert "dies with the runner" not in settle.replace("described as dying", "")
    # It has to acknowledge the condition is met rather than silently dropping it.
    assert "now met" in settle


def test_the_recorded_counts_recompute_from_the_ledgers(measured, calls, ledger_paths):
    """Hand-written figures are checked against the files they came from."""
    assert measured["ledgers"] == len(ledger_paths), _restate(
        "ledgers", measured["ledgers"], len(ledger_paths)
    )
    assert measured["rows"] == calls["rows"], _restate(
        "rows", measured["rows"], calls["rows"]
    )
    assert measured["distinct_call_ids"] == len(calls["by_id"]), _restate(
        "distinct_call_ids", measured["distinct_call_ids"], len(calls["by_id"])
    )
    assert measured["duplicate_rows"] == calls["duplicates"], _restate(
        "duplicate_rows", measured["duplicate_rows"], calls["duplicates"]
    )


def test_every_pinned_ledger_still_holds_the_bytes_it_was_measured_from(corpus):
    """The digests are what the counts used to be standing in for.

    A row count is a weak proxy for "this file is intact": it moves when a
    ledger is deleted, but it also moves when an unrelated run publishes, and it
    does not move at all if a line is edited in place. The digest answers the
    question the count was being asked -- has anything this measurement rests on
    been rewritten -- and answers it per file, so a failure names the ledger
    rather than a delta.
    """
    changed = _rewritten(corpus, REPO_ROOT)
    assert not changed, (
        "a ledger under the measurement was rewritten after it was measured. "
        "A published receipt is append-only; nothing in the grading run edits "
        "one in place. Figures computed from these files are now describing "
        "bytes that no longer exist:\n  " + "\n  ".join(changed)
    )


def test_a_ledger_published_after_the_snapshot_does_not_move_these_figures(
    corpus, ledger_paths
):
    """The growth case, stated as the property rather than as a count.

    This is the failure #448 had to repair by hand and the reason the corpus is
    pinned at all. A grading run publishes a ledger; the tree now holds more
    than the snapshot does; nothing recorded here is wrong. So the live walk is
    read for one thing only -- that the snapshot is still a subset of what is on
    disk -- and the surplus is reported, never asserted against a number.

    The direction matters. Extra ledgers are the contract being honoured. A
    *missing* one is a published receipt that left the tree, which is not
    growth, and ``_resolve_pinned`` refuses that before this test is reached.
    """
    for relative in _surplus(corpus, REPO_ROOT, GRADES):
        # Not counted, but not unread either: a ledger nobody can parse is worth
        # failing on whether or not this snapshot was measured from it.
        for number, line in enumerate(
            (REPO_ROOT / relative).read_text(encoding="utf-8").splitlines(), 1
        ):
            if not line.strip():
                continue
            try:
                json.loads(line)
            except json.JSONDecodeError as exc:
                pytest.fail(f"{relative}:{number} is not JSON: {exc}")
    assert len(ledger_paths) == len(corpus["ledgers"])


def _plant(root, relative, body):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return {"path": relative, "sha256": hashlib.sha256(body.encode()).hexdigest()}


@pytest.fixture
def synthetic(tmp_path):
    """Two pinned ledgers in a throwaway tree, so the real ones stay untouched."""
    grades = tmp_path / "data" / "grades"
    ledgers = [
        _plant(
            tmp_path,
            f"data/grades/run-{n}/r.cost_ledger.jsonl",
            json.dumps({"call_id": f"c{n}", "resolved_model": MODEL}) + "\n",
        )
        for n in (1, 2)
    ]
    return tmp_path, grades, {"ledgers": ledgers}


def test_a_receipt_published_after_this_change_does_not_move_the_verdict(synthetic):
    """The #448 regression, run rather than asserted about.

    #448 spent three hand-edits restoring green after the 2026-09-07 smoke
    published one ledger, and every figure it corrected had been right. The live
    walk could not tell a new receipt from a defect. Here a third ledger is
    published into a pinned corpus of two: the resolution is unchanged, the
    digests are unchanged, and the newcomer is reported as surplus rather than
    counted.
    """
    root, grades, document = synthetic
    before = _resolve_pinned(document, root)
    assert _surplus(document, root, grades) == []

    _plant(
        root,
        "data/grades/run-3/r.cost_ledger.jsonl",
        json.dumps({"call_id": "c3", "resolved_model": MODEL}) + "\n",
    )

    assert _resolve_pinned(document, root) == before, "a new receipt moved the corpus"
    assert _rewritten(document, root) == [], "a new receipt disturbed a digest"
    assert _surplus(document, root, grades) == ["data/grades/run-3/r.cost_ledger.jsonl"]


def test_the_snapshot_still_bites_when_a_pinned_ledger_changes(synthetic):
    """The negative control the counts used to provide.

    Dropping a live count is only safe if what replaces it still fails on the
    thing the count could see. Both losses are exercised: a pinned ledger
    deleted, and a pinned ledger rewritten in place -- which no row count ever
    caught, because editing a line leaves the total alone.
    """
    root, grades, document = synthetic
    pinned = document["ledgers"][0]["path"]

    (root / pinned).write_text("{}\n", encoding="utf-8")
    assert _rewritten(document, root), "a rewritten ledger passed unnoticed"

    (root / pinned).unlink()
    with pytest.raises(AssertionError, match="no longer in the tree"):
        _resolve_pinned(document, root)
    with pytest.raises(AssertionError, match="missing from the tree"):
        _surplus(document, root, grades)


def test_the_sibling_receipt_check_still_names_the_run_it_checks():
    """#448's second fix, held against the file it was made in.

    ``test_both_cost_halves_recompute_from_their_ledgers.py`` located its grade
    by shape and asserted it was the only match. The ``_diagnostic`` fork exists
    so a re-run lands beside its predecessor, so that assertion was going to fail
    the first time the fingerprint contract was honoured -- and did. #448 gave it
    the grader source to select on. This is the same class of defect as the
    census above and reverts the same way: someone deletes the selector because
    "there is only one anyway", and it passes until the next smoke.
    """
    source = (
        REPO_ROOT
        / "batch-runner/tests/test_both_cost_halves_recompute_from_their_ledgers.py"
    ).read_text(encoding="utf-8")
    assert "GRADING_SOURCE" in source, (
        "the sibling receipt check stopped naming the run whose totals it "
        "verifies; a re-grade at a new fingerprint will pair its numbers with "
        "another run's ledger or fail at setup"
    )
    assert "src_" in source, "GRADING_SOURCE no longer pins a grader fingerprint"


def _run_dir(path):
    """The directory a ledger's run publishes into, shards and repeats folded in.

    A run writes its grade and ledger into one directory. A shard of that run
    goes to ``<run>/_shards/<name>/`` and a repeat past the first to
    ``<run>/_repeats/run-NNN/``, so both fold back to the same place. Two ledgers
    that do not fold back to one run directory have no business sharing a call
    identifier at all, whatever else looks similar about them.
    """
    for marker in (SHARD_DIR, REPEAT_DIR):
        if marker in path.parts:
            return path.parts[: path.parts.index(marker)]
    return path.parent.parts


def _duplicate_classes(calls):
    """Sort each duplicated call_id by what the paths say caused it.

    ``merge`` -- the call is in one shard of a run and in that run's own ledger.
    That is the merge re-stating a call it was built from. Stated structurally
    rather than by run name, so the next sharded publish classifies too.

    ``repeat`` -- one ledger file name appearing more than once in the same run,
    every copy but one beneath ``_repeats/``. That is several runs of one corpus
    minting one identifier for several different calls. Deliberately not capped
    at two: the corpus was repeated a third time while this was being written.

    Anything else is returned unclassified, and the caller fails on it. A cause
    nobody has looked at yet must not be absorbed into either bucket.
    """
    merge: dict[str, list[Path]] = {}
    repeat: dict[str, list[Path]] = {}
    unclassified: dict[str, list[Path]] = {}
    for call_id, files in calls["where"].items():
        if len(files) == 1:
            continue
        same_run = len({_run_dir(p) for p in files}) == 1
        shards = sum(1 for p in files if SHARD_DIR in p.parts)
        repeats = sum(1 for p in files if REPEAT_DIR in p.parts)
        if len(files) == 2 and same_run and shards == 1 and repeats == 0:
            merge[call_id] = files
        elif (
            same_run
            and shards == 0
            and repeats >= len(files) - 1
            and len({p.name for p in files}) == 1
        ):
            repeat[call_id] = files
        else:
            unclassified[call_id] = files
    return {"merge": merge, "repeat": repeat, "unclassified": unclassified}


def _extra_rows(classified):
    """Rows a class accounts for, which is one fewer than the files it spans.

    Counting classified identifiers would have worked while every duplicate was
    a pair. A three-deep repeat hides two rows under one identifier, so the two
    stopped being the same number.
    """
    return sum(len(files) - 1 for files in classified.values())


def test_the_duplication_decomposes_into_causes_that_are_all_accounted_for(
    measured, calls, ledger_paths
):
    """Every duplicated row is the merge or a known repeat collision.

    The merge half is the original assertion, unchanged: the merged ledger's row
    count is exactly how many duplicates it may account for, so a merge that
    invented a call or dropped one still fails. What is new is that it is stated
    as a share of the duplicates rather than as all of them, because a second
    cause exists and totalling the two would let either one drift unseen.
    """
    classes = _duplicate_classes(calls)
    assert not classes["unclassified"], (
        "duplicate call_ids whose cause is not the shard merge and not a repeat "
        "collision. Work out what duplicated them before recording any figure "
        "that counts by call_id: "
        + str(
            {
                call_id: [str(p.relative_to(REPO_ROOT)) for p in files]
                for call_id, files in list(classes["unclassified"].items())[:5]
            }
        )
    )

    merged_rows = 0
    for path in ledger_paths:
        if SHARD_DIR in path.parts or REPEAT_DIR in path.parts:
            continue
        if not (path.parent / SHARD_DIR).is_dir():
            continue
        merged_rows += sum(
            1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
        )
    assert merged_rows, (
        "no merged ledger found; the merge invariant has nothing to hold"
    )
    assert _extra_rows(classes["merge"]) == merged_rows
    assert measured["duplicate_rows_from_the_shard_merge"] == merged_rows, _restate(
        "duplicate_rows_from_the_shard_merge",
        measured["duplicate_rows_from_the_shard_merge"],
        merged_rows,
    )
    repeat_rows = _extra_rows(classes["repeat"])
    assert measured["duplicate_rows_from_the_repeat_collision"] == repeat_rows, _restate(
        "duplicate_rows_from_the_repeat_collision",
        measured["duplicate_rows_from_the_repeat_collision"],
        repeat_rows,
    )
    # The two causes have to add up, or a third one is hiding inside a class
    # whose own count still looks right about the part of it that it can see.
    assert _extra_rows(classes["merge"]) + repeat_rows == calls["duplicates"]


def test_no_repeat_collision_was_minted_after_the_fix_that_stops_them(calls):
    """The committed collisions are pre-fix, and a regression would show here.

    ``make_cost_run_id`` suffixes a repeat's run id, so a repeat graded after it
    landed cannot collide with run 1. Every collision on disk therefore has to
    carry an unsuffixed run id on both sides. A new one would arrive suffixed on
    one side, or not be a collision at all -- either way this fails rather than
    quietly growing the count the entry publishes.
    """
    classes = _duplicate_classes(calls)
    assert classes["repeat"], (
        "no repeat collisions found; the guard has nothing to hold"
    )
    for call_id, files in classes["repeat"].items():
        for path in files:
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                record = json.loads(line)
                if record["call_id"] != call_id:
                    continue
                run_id = record["run_id"]
                assert REPEAT_RUN_ID_SUFFIX not in run_id, (
                    "a repeat collision involves a run id minted after "
                    "make_cost_run_id started separating repeats, which should "
                    f"have made it impossible: {run_id} in "
                    f"{path.relative_to(REPO_ROOT)}"
                )


def test_the_hidden_repeat_is_the_one_the_entry_says_it_is(measured, calls):
    """Which of the colliding calls survives decides what the figures miss.

    ``by_id`` keeps the first row it sees, so the entry's claim about which runs
    are the invisible ones is a claim about sort order. Stated in prose and
    unchecked, it would silently invert the day a path changes.
    """
    classes = _duplicate_classes(calls)
    for call_id, files in classes["repeat"].items():
        retained = files[0]
        assert REPEAT_DIR in retained.parts, (
            "the retained row is no longer a later repeat, so the entry's "
            f"account of which calls are missing is backwards: {call_id}"
        )
    hidden = [
        json.loads(line)
        for call_id, files in classes["repeat"].items()
        for shadowed in files[1:]
        for line in shadowed.read_text(encoding="utf-8").splitlines()
        if line.strip() and json.loads(line)["call_id"] == call_id
    ]
    hidden_sol = sum(1 for r in hidden if r.get("resolved_model") == MODEL)
    assert f"low by {hidden_sol}" in measured["calls_lost_to_the_repeat_collision"], (
        f"the entry has to say how many {MODEL} calls the collision hides; the "
        f"ledgers say {hidden_sol}"
    )


def test_a_repeat_gets_its_own_ledger_namespace(calls):
    """The rule itself, asserted at the source rather than only in the data.

    Run 1 must keep the identifiers already published beside it -- renaming them
    would orphan every committed ledger -- and every repeat past it must differ,
    because the parts a run id is built from are held fixed by what a repeat is.
    """
    parts = dict(
        experiment_yaml_name="exp_gold_baseline",
        config_hash="ed9ac99c7332a184",
        grader_source_hash="29c3cfe7e94e4881",
    )
    canonical = make_cost_run_id(**parts)
    assert canonical == make_cost_run_id(**parts, run_ordinal=1)
    # The identifier committed ledgers were minted under, unchanged.
    assert canonical.count("|") == 2
    minted = {make_cost_run_id(**parts, run_ordinal=n) for n in range(1, 6)}
    assert len(minted) == 5, minted
    with pytest.raises(ValueError):
        make_cost_run_id(**parts, run_ordinal=0)


def test_the_per_call_figures_recompute(measured, calls):
    """The numbers that narrowed the tier question."""
    sol = [r for r in calls["by_id"].values() if r.get("resolved_model") == MODEL]
    assert measured["gpt_5_6_sol_calls"] == len(sol), _restate(
        "gpt_5_6_sol_calls", measured["gpt_5_6_sol_calls"], len(sol)
    )
    inputs = [r["input_tokens"] for r in sol]
    assert measured["max_single_request_input_tokens"] == max(inputs), _restate(
        "max_single_request_input_tokens",
        measured["max_single_request_input_tokens"],
        max(inputs),
    )
    for field, threshold in (
        ("calls_over_128k", 128_000),
        ("calls_over_200k", 200_000),
        ("calls_over_272k", 272_000),
    ):
        recomputed = sum(1 for v in inputs if v > threshold)
        assert measured[field] == recomputed, _restate(
            field, measured[field], recomputed
        )
    # The bound is stated in prose as a pair of counts. Both go stale together.
    under = len(sol) - measured["calls_over_128k"]
    assert f"{under:,} of {len(sol):,} calls are under 128,000" in (
        measured["what_it_bounds"]
    ), (
        "what_it_bounds names how many calls sit under 128,000; the ledgers say "
        f"{under:,} of {len(sol):,}"
    )


def test_no_committed_request_reaches_the_sibling_split(measured, calls):
    """The bound the entry states, held against the data rather than the prose.

    This is the assertion that would break first if a later run sent a request
    large enough to make the tier matter. Breaking is correct: the entry's
    ``what_it_bounds`` sentence would no longer be true.
    """
    sol = [r for r in calls["by_id"].values() if r.get("resolved_model") == MODEL]
    biggest = max(r["input_tokens"] for r in sol)
    assert biggest < SIBLING_CONTEXT_SPLIT
    assert measured["calls_over_272k"] == 0
    assert str(SIBLING_CONTEXT_SPLIT) in measured["what_it_bounds"].replace(",", "")


def test_the_stated_dollar_bound_recomputes_from_the_published_meters(measured):
    """$549.50 to $980.84 is arithmetic on the merged run, not an estimate.

    The run is named by its grader fingerprint rather than assumed to be the
    only gold-ceiling ledger on disk. It was the second: the glob matched one
    file and asserted so, which is the same assumption #448 had to remove from
    test_both_cost_halves_recompute_from_their_ledgers.py after the 2026-09-07
    re-run published a sibling. The bound below is this run's, and a re-grade at
    a new fingerprint lands beside it rather than replacing it -- so naming the
    run is what keeps the arithmetic attached to the numbers it came from.
    """
    raw = _load_table()
    meters = raw["azure_published_meters"][MODEL]
    merged = sorted(
        p
        for p in GRADES.rglob("*gold_ceiling_185*.cost_ledger.jsonl")
        if GOLD_CEILING_SOURCE in p.name and SHARD_DIR not in p.parts
    )
    assert len(merged) == 1, (
        f"expected exactly one merged ledger at {GOLD_CEILING_SOURCE}; found "
        f"{[p.name for p in merged]}"
    )
    rows = [
        json.loads(line)
        for line in merged[0].read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    sol = [r for r in rows if r.get("resolved_model") == MODEL]
    cached = sum(r["cached_input_tokens"] for r in sol)
    uncached = sum(r["input_tokens"] for r in sol) - cached
    output = sum(r["output_tokens"] for r in sol)

    def total(tier):
        rate = meters[tier]
        return (
            Decimal(uncached) / MILLION * Decimal(rate["input"])
            + Decimal(cached) / MILLION * Decimal(rate["cached_input"])
            + Decimal(output) / MILLION * Decimal(rate["output"])
        )

    low = total("short_context_standard_global")
    high = total("long_context_standard_global")
    assert f"${low:,.2f}" in measured["what_it_bounds"]
    assert f"${high:,.2f}" in measured["what_it_bounds"]
    # The bound is only a bound if the two ends really differ.
    assert low < high


def test_the_measurement_did_not_become_a_price():
    """Bounding the tier is not settling it. The model stays unpriced.

    The whole risk of writing these numbers down is that a later reader treats a
    narrow range as licence to pick a rate. ``ReceiptPriceTable`` is asked
    directly, so this fails on the behaviour and not on the JSON shape.
    """
    table = load_receipt_price_table(PRICE_TABLE_PATH)
    assert table.lookup("azure", MODEL) is None
    entry = _load_table()["models_deliberately_not_priced"][f"azure:{MODEL}"]
    assert "unpriced" in entry["measured_from_committed_ledgers"]["what_it_settles"]


def test_the_two_axes_the_measurement_cannot_touch_are_still_named(entry):
    """Zone and cache writes are untouched by any token count.

    The tier was the axis a measurement could speak to. These two are not, and
    an entry that quietly stopped naming them would read as though committing
    the ledgers had settled more than it did.
    """
    why = entry["why_unpriced"]
    assert "zone" in why
    assert "cache write" in why
    # The count is stated twice, opening and closing. Checking only one of them
    # let a negative control through: rewriting "Three axes are open." to "One
    # axis is open." left the closing "three open axes" intact and passed.
    assert "Three axes are open" in why
    assert "three open axes" in why
