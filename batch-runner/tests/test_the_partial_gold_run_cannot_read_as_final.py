"""The 174 must never be readable as the 185, by any route that exists.

Stage 3 pinned 185 gold tasks. 174 are graded and 11 are not, because one task
in shard 4 cannot be graded inside a chunk the platform is willing to run (see
``test_a_task_longer_than_a_chunk_can_never_be_graded.py`` for why that is a
ceiling rather than a budget). The shards are staying on disk -- they are paid
evidence -- and the risk that creates is not that someone lies about them. It
is that a partial set of eleven shard files looks exactly like a complete one
in a directory listing, and every downstream reader has to be the thing that
notices.

So this file checks that none of them has to notice. Each test takes one route
by which 174 could be presented as a finished measurement and shows the route
is closed:

    the shards themselves    say ``partial``, not ``final``
    step9 merge              refuses a short union, and ``--force`` does not help
    step9 merge, deferring   exits 75 -- "wait", not "broken"
    step9 merge, cross-hash  refuses shards graded by superseded code
    the analyzer             refuses any payload that is not a finished run
    the frozen inventory     still says BLOCKED_PARTIAL and still counts 11
    the frozen inventory     still names the two tasks that were graded deaf

The guards are pre-existing; only the last two are new. That is deliberate. This
file's job is to make the existing behaviour expensive to remove by accident,
because the failure it prevents is silent -- a merged-looking payload with a
plausible mean, eleven tasks short, and nothing on its face to say so.

Nothing here calls a model or a network. The shard payloads are the real
committed ones, because the claim being pinned is about those files.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import step9_merge_shards as s9
from scripts import analyze_gold_ceiling as analysis
from scripts import stage3_partial_inventory as inventory

REPO_ROOT = Path(__file__).resolve().parents[2]
INVENTORY_PATH = (
    REPO_ROOT / "tasks/rebuilding_grading_task/stage3_partial_inventory.json"
)

EXPECTED_GRADED = 174
EXPECTED_MISSING = 11


def _shard_paths() -> list[Path]:
    paths = sorted(inventory.SHARD_DIR.glob("shard-*-of-011.json"))
    assert len(paths) == inventory.SHARD_COUNT, (
        f"expected {inventory.SHARD_COUNT} committed shards, found "
        f"{len(paths)} in {inventory.SHARD_DIR}"
    )
    return paths


def _superseded_shard_path() -> Path:
    """One shard from the earlier pass, whichever it is.

    The cost-receipt work touched ``core/`` and so moved the grader source
    hash, orphaning the shards graded before it. They were committed and are
    still on disk one directory across from the current run.
    """
    siblings = [
        entry
        for entry in inventory.SHARD_DIR.parent.iterdir()
        if entry.is_dir() and entry != inventory.SHARD_DIR
    ]
    if not siblings:
        pytest.skip("no superseded shard directory is committed any more")
    payloads = sorted(siblings[0].glob("shard-*.json"))
    assert payloads, f"{siblings[0]} holds no shard payloads"
    return payloads[0]


def test_every_committed_gold_shard_still_calls_itself_partial():
    """The first line of defence, and the cheapest one to lose.

    ``run_status`` is what the analyzer keys on. A shard that said ``final``
    would be accepted by every downstream reader on its own, without any merge
    happening at all -- so the honesty of the whole set rests on eleven files
    each describing themselves correctly.
    """
    for path in _shard_paths():
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["run_status"] == "partial", (
            f"{path.name} calls itself {payload['run_status']!r}; a shard is "
            "never a finished run, and the analyzer would now accept it alone"
        )


def test_the_short_union_is_refused_and_force_does_not_override(
    tmp_path, capsys
):
    """The route someone would actually take, and the one they would take next.

    Merging all eleven is the obvious move: the files are there, ten of them
    are complete, and the output would look like a result. It fails, because
    the union is 174 against an ``expected_task_count`` of 185.

    ``--force`` is checked in the same test because it is the natural second
    attempt and it means something else entirely -- permission to overwrite an
    existing ``--output``, not permission to publish a short corpus. Keeping
    both in one test keeps that distinction from being quietly narrowed.

    The failure text is asserted, not just the exit code. A merge that started
    failing for an unrelated reason -- a schema change, a missing ledger --
    would still exit 1 and this test would still pass while proving nothing.
    """
    out = tmp_path / "must-not-exist.json"

    assert s9.main([*map(str, _shard_paths()), "-o", str(out)]) == 1
    assert "incomplete" in capsys.readouterr().err, (
        "the merge failed for some reason other than coverage; this test no "
        "longer proves a short union is refused"
    )
    assert not out.exists(), "a refused merge still wrote its output file"

    assert s9.main([*map(str, _shard_paths()), "-o", str(out), "--force"]) == 1
    assert "incomplete" in capsys.readouterr().err
    assert not out.exists(), (
        "--force overrode the coverage check; it may only overwrite an "
        "existing output, never promote an incomplete union"
    )


def test_deferring_is_a_distinct_exit_from_a_broken_merge(tmp_path):
    """Why 75 has to stay different from 1.

    Eleven shards race to merge, so "the union is short because a sibling is
    still working" is a normal, expected outcome and the caller should stand
    down quietly. "The union is short because eleven tasks will never arrive"
    is not. Both produce the same short union, so the exit code is the only
    thing distinguishing wait-and-retry from stop-and-look -- and a workflow
    that treated 75 as success would publish nothing while reporting green.
    """
    out = tmp_path / "deferred.json"
    code = s9.main(
        [*map(str, _shard_paths()), "-o", str(out), "--defer-if-incomplete"]
    )

    assert code == s9.DEFER_EXIT_CODE == 75
    assert code != 0, "deferring must not read as success"
    assert not out.exists()


def test_a_shard_from_a_superseded_grader_cannot_join_this_run(
    tmp_path, capsys
):
    """The route that would have filled the gap with the wrong evidence.

    Nine shards from an earlier pass sit under the same corpus digest, one
    directory across, graded before the change that moved the grader source
    hash. They cover tasks this run also covers, so mixing them in would raise
    the union and could even reach 185 -- with items scored by two different
    graders and no way to tell which.

    ``grader_source_hash`` is a contract identity field precisely so that this
    fails at the merge rather than in the reading of the result. The field is
    named in the assertion because a cross-hash merge also has a short union,
    and this test is meant to prove the hash stopped it.
    """
    out = tmp_path / "cross-hash.json"
    current = _shard_paths()[0]

    assert (
        s9.main(
            [str(current), str(_superseded_shard_path()), "-o", str(out)]
        )
        == 1
    )
    assert "grader_source_hash" in capsys.readouterr().err, (
        "the cross-hash merge was refused for some other reason; mixing two "
        "graders may no longer be what stops it"
    )
    assert not out.exists()


def test_the_analyzer_refuses_a_payload_that_is_still_partial():
    """The last reader in the chain, checked directly.

    Even granting that a shard reached it -- hand-copied, renamed, whatever --
    ``analyze_gold_ceiling`` will not compute a ceiling from it. The check is
    on ``run_status`` rather than on task count, so it holds for a shard that
    happens to be internally complete.
    """
    payload = json.loads(_shard_paths()[0].read_text(encoding="utf-8"))
    assert payload["run_status"] not in analysis.COMPLETE_RUN_STATUSES

    problems = analysis._identity_problems(payload)
    assert any("run_status" in problem for problem in problems), (
        f"the analyzer accepted a partial shard; problems were {problems}"
    )


def test_the_frozen_inventory_still_describes_the_shards_on_disk():
    """Keeps the record from drifting away from what it records.

    The inventory is a committed snapshot, so it can rot: a shard could be
    regraded, replaced or removed and the JSON would go on asserting digests
    that no longer match. Rebuilding it here and diffing means the document is
    checked rather than trusted.

    ``committed_in`` is dropped before comparing. It comes from ``git log``,
    and CI checks out shallow, so it legitimately differs between a full clone
    and the runner -- it is provenance for a human, not part of the claim.
    """
    committed = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    rebuilt = inventory.build_inventory()

    for document in (committed, rebuilt):
        for shard in document["shards"]:
            shard.get("grade_file", {}).pop("committed_in", None)

    assert rebuilt == committed, (
        "the shards on disk no longer match the frozen inventory; regenerate "
        "it with scripts/stage3_partial_inventory.py and say in the commit "
        "message what moved"
    )


def test_the_inventory_refuses_to_read_as_a_finished_measurement():
    """The claims a reader is entitled to make from the document itself.

    Asserted against the committed file rather than a rebuild, because this is
    about what the artifact says to someone who opens it: that it is blocked,
    that it is 174 of 185, that eleven named tasks are absent, and that the
    absent set is not incidental -- ``a73fbc98`` was published before the run
    as a task expected to score badly, so a mean taken without it reads higher
    than the corpus would.
    """
    document = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))

    assert document["status"] == "BLOCKED_PARTIAL"
    assert document["coverage"]["graded"] == EXPECTED_GRADED
    assert document["coverage"]["expected"] == inventory.EXPECTED_TASK_COUNT
    assert document["coverage"]["missing"] == EXPECTED_MISSING
    assert len(document["coverage"]["missing_task_ids"]) == EXPECTED_MISSING

    withheld = {
        task["task_id"][:8]
        for task in document["coverage"]["missing_tasks"]
        if task["known_input_limit"]
    }
    assert withheld, (
        "no pre-registered input limit is among the missing tasks any more; "
        "the upward-bias caveat in the report needs re-deriving"
    )

    assert document["cost"]["known_usd"] is None, (
        "an unpriced judge must not settle to a number; $0 would read as free"
    )


def test_the_known_audio_defect_is_recorded_rather_than_absorbed():
    """The two tasks whose scores are floors, named in the artifact.

    A container-probing bug read a video deliverable as silent, so criteria
    about sound were demoted to TEXT and answered by a judge that cannot hear.
    Demotion is not exclusion -- ``score_excluded`` would have withheld those
    items, but these were scored, and scored by something deaf. Both tasks
    therefore read lower than they were measured to be.

    This is asserted because the tempting thing to do with a known defect of
    bounded size (at most +0.29pp on the corpus mean) is to note it in a commit
    message and move on. The two tasks are Film and Video Editors, and they sit
    in the sector that the report otherwise ranks last, so a reader drawing
    conclusions per-sector needs the defect attached to the number.

    ``correctable_here`` is the load-bearing claim: the fix moves the grader
    source hash, so it cannot be applied to this measurement. Only a re-run
    corrects these two, and anything asserting otherwise is proposing to mix
    two graders inside one corpus.
    """
    document = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    defect = document["known_grading_defects"][
        "audio_criteria_scored_without_listening"
    ]

    assert defect["correctable_here"] is False, (
        "a defect that moves the grader fingerprint cannot be corrected "
        "inside the measurement it damaged; only a re-run can"
    )
    assert defect["tasks"], (
        "the defect block no longer names any task; either the detector "
        "broke or the shards changed, and a silent zero here would erase a "
        "caveat the report depends on"
    )

    for task in defect["tasks"]:
        assert task["items_demoted"] > 0
        assert task["points_not_awarded"] > 0
        assert task["pct_as_recorded"] is not None
        assert task["total_max"] > 0

    affected = {task["task_id"][:8] for task in defect["tasks"]}
    assert affected == {"75401f7c", "e222075d"}, (
        f"the set of deaf-graded tasks moved to {sorted(affected)}; the "
        "report quotes these two by id, percentage and points, so it has to "
        "be re-derived rather than have the assertion widened"
    )


def test_the_audio_defect_cannot_overturn_the_headline_number():
    """Bounding the defect, so the caveat cannot be used to dismiss the run.

    The report states the ceiling is missed on two of three criteria. A known
    scoring defect is exactly the kind of thing that gets stretched into "so
    the measurement is worthless" -- so the bound is recomputed here from the
    shards rather than quoted from the prose: even crediting every demoted
    item in full, the mean moves by a third of a point and no verdict changes.

    The bound is pinned to the figure the report prints rather than to a loose
    ceiling. A loose one is nearly unfalsifiable -- two tasks out of 173 cannot
    move a mean by more than 1.16pp even going from zero to full marks -- so a
    threshold test would pass while the quoted number drifted away from it.

    Each task's withheld points are converted to that task's own percentage
    before averaging. Pooling them into one denominator is wrong whenever the
    two rubrics differ in size, which here understates the effect by half.
    """
    document = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    defect = document["known_grading_defects"][
        "audio_criteria_scored_without_listening"
    ]

    lost = {
        task["task_id"]: (task["points_not_awarded"], task["total_max"])
        for task in defect["tasks"]
    }
    assert lost, "no affected task to bound; see the defect test above"

    scores, gained_pct = [], 0.0
    for path in _shard_paths():
        for task in json.loads(path.read_text(encoding="utf-8"))["tasks"]:
            # The errored task records pct 0.0 over a total_max of 0 rather
            # than a null, so dropping it needs the error field; filtering on
            # pct would average a non-score into the mean.
            if task.get("error"):
                continue
            scores.append(task["pct"])
            points, maximum = lost.get(task["task_id"], (0.0, 0.0))
            if maximum:
                gained_pct += 100.0 * points / maximum

    assert len(scores) == EXPECTED_GRADED - 1, "one task carries a judge error"

    mean = sum(scores) / len(scores)
    best_case = mean + gained_pct / len(scores)

    assert round(mean, 2) == 80.19, f"the reported mean moved to {mean:.2f}"
    assert round(best_case, 2) == 80.48, (
        f"the defect's upper bound is now {best_case:.2f}%, not the 80.48% "
        "the report prints; re-derive the figure before changing this"
    )
    assert best_case < 90.0, (
        "even at its most generous the defect does not reach the 90% gold "
        "ceiling; if this fails the headline verdict has changed"
    )


def test_the_shards_agree_on_who_graded_them():
    """That the 174 are one measurement rather than several.

    Eleven jobs ran on eleven runners over two days. If any of them disagreed
    on the grader hash, the config hash or the corpus digest, the set would not
    be a single measurement no matter how complete it became -- and the fix
    would be a re-run, not a merge. The inventory derives this; asserting it
    keeps a disagreement from being recorded rather than raised.
    """
    document = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    agreement = document["identity_agreement"]

    assert agreement["all_shards_agree"], agreement["fields"]
    assert agreement["single_run_ordinal"], agreement["ledger_run_ids"]

    for shard in document["shards"]:
        ledger = shard["cost_ledger"]
        assert ledger["sha256_agrees"], (
            f"shard {shard['shard_index']} declares a cost ledger digest that "
            "does not match the file beside it"
        )
