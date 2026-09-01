"""The re-run conditions, checked without buying anything.

PR #276 fixed a container probe that read a video deliverable as silent, so
audio criteria were demoted to TEXT and answered by a judge that could not
hear. The fix moves the grader source hash, which means it cannot repair the
174 tasks already graded -- only a re-run at the new fingerprint can. This file
checks that the re-run is set up to be worth dispatching, before anyone
dispatches it.

Three claims, in the order they can fail:

    the smoke covers the damage    its pin equals the tasks the inventory's
                                   defect block names, derived from the shards
                                   rather than copied into the config
    the new run is a new run       the moved fingerprint separates it from the
                                   174 in the output path, in the cost ledger
                                   run id, and at the merge
    the old evidence stays put     the inventory still names the old hash, so
                                   the 174's provenance does not follow the code

The second is the one worth stating plainly. A re-run that landed on the old
run's path, or merged with its shards, would not be a second measurement --
it would be a corrupted first one, and the corruption would be item-level and
undetectable afterwards.

Nothing here calls a model or a network, and nothing here dispatches. The
figures come from committed shard files and committed configs.

Spec: tasks/rebuilding_grading_task/306-rerun-conditions.md
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from step8_grade import (  # noqa: E402
    compute_grader_source_hash,
    hash_config,
    resolve_grade_output_path,
)
from scripts import stage3_partial_inventory as inventory  # noqa: E402

BATCH_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BATCH_ROOT.parent
CONFIGS = BATCH_ROOT / "grading_configs"

FULL = CONFIGS / "gold_ceiling_185_v2_sol_max.yaml"
SMOKE = CONFIGS / "gold_smoke_audio_v2_sol_max.yaml"
MANIFEST = BATCH_ROOT / "experiments/gold_corpus/gold_deliverable_manifest.json"
INVENTORY_PATH = (
    REPO_ROOT / "tasks/rebuilding_grading_task/stage3_partial_inventory.json"
)

#: What the 174 were graded by. A literal, matching the literal the inventory
#: pins, because the point of both is that they do not track the code.
OLD_SOURCE_HASH = (
    "955be41edc4aff191952123e37538266aa28508786aa82693055269538d8b67a"
)

#: Identity inputs shared by the old run and any re-run. The corpus, the
#: rubric and the prompt are held constant, which is what makes the two
#: comparable at all.
#:
#: The config is **not** constant any more, and that is why there are two
#: hashes here rather than one. Raising the audio task cap from three to 32
#: moved ``gold_ceiling_185_v2_sol_max.yaml``, so the re-run differs from the
#: 174 in two identity fields, not one: the config hash and the grader source
#: hash. Both are part of the same repair -- the cap was starving 11 tasks
#: while the endpoint was refusing every call -- but a comparison between the
#: two runs has to say so rather than imply the code alone moved.
#:
#: ``OLD_CONFIG_HASH`` stays a literal because it is what the 174's paths on
#: disk actually carry. ``NEW_CONFIG_HASH`` is derived, so that if the config
#: moves again this file notices instead of quietly comparing a real path
#: against an invented one.
OLD_CONFIG_HASH = "b3609ec13f8fa51e"
RUBRIC_SHA = "11e7900cdcac61bc4daf59e65feb238acda98fbf"
PROMPT_VERSION = "v2.2"
EXPERIMENT_ID = "exp_gold_baseline"


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def full() -> dict:
    return _load(FULL)


@pytest.fixture(scope="module")
def smoke() -> dict:
    return _load(SMOKE)


@pytest.fixture(scope="module")
def defect() -> dict:
    document = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    return document["known_grading_defects"][
        "audio_criteria_scored_without_listening"
    ]


# ── the smoke has to cover the damage it is smoking out ──────────────────


def test_the_smoke_pins_exactly_the_tasks_that_were_graded_deaf(smoke, defect):
    """The coverage claim, derived rather than asserted.

    The config could name any two tasks and look purposeful. What makes the
    pin evidence is that it equals the set the inventory measured from the
    committed shards -- so if the detector ever finds a third damaged task,
    this fails and the smoke is widened before it is bought, instead of
    quietly proving the fix for two thirds of the problem.
    """
    damaged = {task["task_id"] for task in defect["tasks"]}
    assert damaged, "the defect block names no task; the detector or the shards moved"

    pinned = set(smoke["rerun_identity"]["task_ids"])
    assert pinned == damaged, (
        f"the smoke pins {sorted(pinned)} but the defect damaged "
        f"{sorted(damaged)}; widen the pin rather than this assertion"
    )
    assert smoke["rerun_identity"]["expected_task_count"] == len(damaged)


def test_the_pin_follows_canonical_corpus_order(smoke):
    """A reordering is a refusal, so it may as well be caught for free.

    ``filter_tasks_for_config`` compares the pinned list to the selected list
    by equality and raises on a mismatch. That refusal arrives after the
    workflow has started; this one arrives in CI.
    """
    rows = json.loads(MANIFEST.read_text(encoding="utf-8"))
    rows = rows["tasks"] if isinstance(rows, dict) and "tasks" in rows else rows
    order = [row["task_id"] if isinstance(row, dict) else row for row in rows]

    pinned = smoke["rerun_identity"]["task_ids"]
    positions = [order.index(task_id) for task_id in pinned]
    assert positions == sorted(positions), (
        f"the pin is out of corpus order: positions {positions}"
    )


def test_the_smoke_is_cheap_relative_to_what_it_de_risks(smoke, full):
    """Why a smoke at all, stated as a ratio rather than as a habit.

    The full run is 185 tasks across eleven shards, most of a working day of
    Sol Max grading. The smoke is two tasks. If that ratio ever stopped being
    lopsided the smoke would have become a second full run and the argument
    for running it first would be gone.
    """
    smoke_size = len(smoke["rerun_identity"]["task_ids"])
    full_size = len(full["rerun_identity"]["task_ids"])
    assert smoke_size * 20 < full_size, (
        f"the smoke grades {smoke_size} of {full_size} tasks; it is no longer "
        "cheap enough to be a precondition for the full run"
    )


# ── the re-run must not be able to touch the 174 ─────────────────────────


def test_the_moved_fingerprint_puts_the_rerun_on_a_different_path(full):
    """The first of three separations, and the one a reader would notice.

    The output filename carries ``src_<grader_source_hash_short>``, so a run
    at the new fingerprint resolves to a different file than the 174 did. It
    cannot overwrite them and it cannot be mistaken for them in a directory
    listing.
    """
    new_hash = compute_grader_source_hash(FULL, full)
    assert new_hash != OLD_SOURCE_HASH, (
        "the full config's fingerprint equals the one the 174 were graded at; "
        "the audio fix is not on this branch and there is nothing to re-run for"
    )

    def path_for(source_hash: str) -> Path:
        return resolve_grade_output_path(
            full,
            experiment_id=EXPERIMENT_ID,
            judge_slug="gpt-5-6-sol",
            config_hash=(
                OLD_CONFIG_HASH
                if source_hash == OLD_SOURCE_HASH
                else hash_config(str(FULL))
            ),
            rubric_sha=RUBRIC_SHA,
            rubric_short_sha=RUBRIC_SHA[:7],
            prompt_version=PROMPT_VERSION,
            inference_sha=RUBRIC_SHA,
            grader_source_hash=source_hash,
            shard_index=4,
            shard_count=11,
        )

    old_path, new_path = path_for(OLD_SOURCE_HASH), path_for(new_hash)
    assert old_path != new_path, (
        "a re-run at the fixed grader resolves to the same file as the run it "
        "is replacing; dispatching it would overwrite paid evidence"
    )
    assert OLD_SOURCE_HASH[:16] in str(old_path)
    assert new_hash[:16] in str(new_path)


def test_the_rerun_needs_no_ordinal_bump_to_be_a_distinct_run(full):
    """Why the re-run is ordinal 1, not ordinal 2.

    ``--run-ordinal N`` exists to repeat a run at an *unchanged* identity, and
    forks into ``_repeats/run-00N/`` to say so. Here the identity already
    changed, so ordinal 1 at the new fingerprint is unused -- and claiming
    ordinal 2 would assert this is the second run at a fingerprint that has
    never been graded even once. The separation is doing its job when nothing
    has to be bumped by hand.
    """
    new_hash = compute_grader_source_hash(FULL, full)

    def path_for(source_hash: str, ordinal: int) -> Path:
        return resolve_grade_output_path(
            full,
            experiment_id=EXPERIMENT_ID,
            judge_slug="gpt-5-6-sol",
            config_hash=(
                OLD_CONFIG_HASH
                if source_hash == OLD_SOURCE_HASH
                else hash_config(str(FULL))
            ),
            rubric_sha=RUBRIC_SHA,
            rubric_short_sha=RUBRIC_SHA[:7],
            prompt_version=PROMPT_VERSION,
            inference_sha=RUBRIC_SHA,
            grader_source_hash=source_hash,
            run_ordinal=ordinal,
        )

    assert path_for(new_hash, 1) != path_for(OLD_SOURCE_HASH, 1)
    assert "_repeats" not in str(path_for(new_hash, 1)), (
        "ordinal 1 must stay on the canonical path; a re-run that forked into "
        "_repeats would be excluded from the dashboard glob it belongs in"
    )
    assert "_repeats/run-002" in str(path_for(new_hash, 2))


def test_the_cost_ledger_separates_the_two_runs_without_being_told(full):
    """The second separation: money.

    ``step8_grade.py`` builds its ledger run id as
    ``experiment|config_hash|grader_source_hash``, so the re-run's spend cannot
    be appended to the 174's ledger totals by an operator who forgot a flag.
    The formula is reproduced here rather than imported because it is a
    one-line f-string at a call site; if it moves, this test's own comment is
    the thing that tells the next reader where it went.

    Two of the three fields move, not one. This test used to build both ids
    from a single ``CONFIG_HASH`` literal and then assert that their first two
    fields matched -- which was true by construction and therefore checked
    nothing, while its comment claimed the runs "differ by more than the
    grader fix" would be caught. Raising the audio cap moved the config too,
    so the claim is now stated as what it is: both fields moved, both moved as
    part of the same repair, and either alone is enough to keep the ledgers
    apart.
    """
    new_hash = compute_grader_source_hash(FULL, full)
    new_config_hash = hash_config(str(FULL))
    old_run_id = f"{EXPERIMENT_ID}|{OLD_CONFIG_HASH}|{OLD_SOURCE_HASH}"
    new_run_id = f"{EXPERIMENT_ID}|{new_config_hash}|{new_hash}"

    assert old_run_id != new_run_id
    assert new_run_id.split("|")[0] == old_run_id.split("|")[0] == EXPERIMENT_ID

    # Either difference alone separates the ledgers, so neither is load-bearing
    # on its own -- which is what makes the separation robust to one of them
    # being reverted later.
    assert new_config_hash != OLD_CONFIG_HASH, (
        "the audio call cap is back at its old value; the 11 tasks that ask "
        "for more than three listening calls are starved again"
    )
    assert new_hash != OLD_SOURCE_HASH


def test_a_rerun_shard_cannot_merge_with_the_shards_it_replaces(full, tmp_path, capsys):
    """The third separation, and the only one that has to hold item by item.

    The other two keep the runs in different files. This one keeps them out of
    the same *result*: ``grader_source_hash`` is a contract identity field, so
    a shard from the re-run and a shard from the 174 are refused at the merge
    rather than averaged together. Without it, the cheapest way to reach 185
    would be to re-grade the missing eleven at the new fingerprint and merge
    them into the old 174 -- which reads as a complete corpus and is two
    graders deep.

    The refusal is exercised rather than inferred from the field list. A
    membership check would pass while the field sat in the contract unused,
    and the failure being guarded against is exactly the silent kind.
    """
    import step9_merge_shards as s9

    assert ("grader_source_hash", ("grader_source_hash",)) in (
        s9.CONTRACT_IDENTITY_FIELDS
    ), "the grader fingerprint left the merge contract"

    new_hash = compute_grader_source_hash(FULL, full)
    kept = inventory.SHARD_DIR / f"shard-000-of-{inventory.SHARD_COUNT:03d}.json"
    committed = json.loads(kept.read_text(encoding="utf-8"))
    assert committed["grader_source_hash"] == OLD_SOURCE_HASH, (
        "the committed shards no longer declare the fingerprint the report "
        "attributes them to"
    )
    assert new_hash != committed["grader_source_hash"]

    # A different shard index, so the union has no duplicate task and the hash
    # is the only thing the merge can object to.
    sibling = json.loads(
        (
            inventory.SHARD_DIR / f"shard-001-of-{inventory.SHARD_COUNT:03d}.json"
        ).read_text(encoding="utf-8")
    )
    sibling["grader_source_hash"] = new_hash
    regraded = tmp_path / "shard-001-regraded.json"
    regraded.write_text(json.dumps(sibling), encoding="utf-8")

    out = tmp_path / "two-graders.json"
    assert s9.main([str(kept), str(regraded), "-o", str(out)]) == 1
    assert "grader_source_hash" in capsys.readouterr().err, (
        "the mixed merge was refused for some other reason; the fingerprint "
        "may no longer be what keeps a re-run out of the run it replaces"
    )
    assert not out.exists()


# ── the smoke only predicts the run it was dispatched alongside ──────────


def test_a_shared_code_change_moves_both_fingerprints_together(full, smoke):
    """Why the smoke and the full run have to be dispatched from one commit.

    The two configs share every hashed input except their own file, so a change
    to ``core/`` moves both fingerprints at once. That is what makes the smoke
    transferable evidence: it ran against the same grader bytes the full run
    will.

    It is also the failure mode. Three of the four open PRs touch ``core/`` --
    merging one between the smoke and the full run moves the full run's
    fingerprint to something no smoke has ever exercised, and the first sign of
    it would be sixty hours into a paid run. The operational rule is in
    ``306-rerun-conditions.md``: record the full run's fingerprint when the
    smoke passes, recompute it before dispatching, and refuse if it moved.
    """
    shared = BATCH_ROOT / "core" / "grader_routing.py"
    before = (compute_grader_source_hash(FULL, full),
              compute_grader_source_hash(SMOKE, smoke))

    original = shared.read_bytes()
    try:
        shared.write_bytes(original + b"\n# fingerprint probe\n")
        after = (compute_grader_source_hash(FULL, full),
                 compute_grader_source_hash(SMOKE, smoke))
    finally:
        shared.write_bytes(original)

    assert shared.read_bytes() == original
    assert after[0] != before[0] and after[1] != before[1], (
        "a core/ edit left one of the two fingerprints alone; the smoke and "
        "the full run no longer share a grader and the smoke proves nothing "
        "about the run it precedes"
    )
    assert (compute_grader_source_hash(FULL, full),
            compute_grader_source_hash(SMOKE, smoke)) == before


# ── and the paid evidence must not follow the code ───────────────────────


def test_the_frozen_inventory_still_names_the_grader_that_made_it():
    """Why merging the audio fix did not invalidate the closeout report.

    ``PINNED_SOURCE_HASH`` is a literal. If it were computed live it would
    have followed the fix, and the 174 would have started claiming they were
    graded by code that had never seen them -- silently, with every digest in
    the inventory still matching.
    """
    assert inventory.PINNED_SOURCE_HASH == OLD_SOURCE_HASH

    document = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    assert document["status"] == "BLOCKED_PARTIAL", (
        "the closeout is no longer blocked; if the re-run happened, this file "
        "is measuring the wrong thing and the inventory needs regenerating"
    )
    for shard in document["shards"]:
        assert shard["identity"]["grader_source_hash"] == OLD_SOURCE_HASH


def test_the_defect_is_still_recorded_as_uncorrectable_here(defect):
    """The claim the whole re-run rests on.

    If this ever said ``True``, someone would have proposed repairing the two
    damaged tasks inside the existing measurement -- which means grading two
    of 174 tasks with different code and publishing the mean as one number.
    """
    assert defect["correctable_here"] is False
