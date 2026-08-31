"""A smoke is only evidence about the run it is standing in for.

``gold_smoke_audio_v2_sol_max`` exists to spend two tasks' worth of Sol Max
proving that the audio path works before ``gold_ceiling_185_v2_sol_max``
spends a hundred and eighty five tasks' worth assuming it does. That argument
holds exactly as long as the two configs agree on every runtime setting, so
the first test here asserts that agreement rather than trusting the copy that
produced it.

The separate config is not a workaround. A config that pins
``rerun_identity.task_ids`` requires ``--tasks`` to equal that list and
``--limit`` to be zero or its full length -- the pin is what makes a re-run's
identity checkable, so neither flag can narrow it, and relaxing that to buy a
smoke would cost more than the smoke is worth. Pinning a smaller corpus in a
config of its own asks the question without touching the guard.

Which two tasks, and why they are not asserted here: the pin has to match the
defect the 174-task partial run actually measured, and that is a fact about
committed shard files rather than about this config. It is checked in
``test_the_audio_smoke_covers_what_the_defect_damaged.py``, against the
inventory. This file checks the parity claim; that one checks the coverage
claim.

Nothing here calls a model or a network.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from step8_grade import (  # noqa: E402
    compute_grader_source_hash,
    filter_tasks_for_config,
)

BATCH_ROOT = Path(__file__).resolve().parents[1]
CONFIGS = BATCH_ROOT / "grading_configs"

FULL = CONFIGS / "gold_ceiling_185_v2_sol_max.yaml"
SMOKE = CONFIGS / "gold_smoke_audio_v2_sol_max.yaml"

# The two tasks the container-probing defect scored deaf, in canonical corpus
# order -- ``e222075d`` at position 46, ``75401f7c`` at 47. Both are Film and
# Video Editors, which is why they are adjacent: consecutive rows share an
# occupation. step8_grade.py refuses a pin that is not in this order.
AUDIO_TASKS = [
    "e222075d-5d62-4757-ae3c-e34b0846583b",
    "75401f7c-396d-406d-b08e-938874ad1045",
]

# Everything that decides what a grading call costs and returns. Identity
# fields are deliberately absent: those are the two configs' only licensed
# difference.
RUNTIME_KEYS = (
    "schema_version",
    "judge",
    "rubric",
    "grader",
    "tpm_guard",
    "prompt",
    "output",
)


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def full() -> dict:
    return _load(FULL)


@pytest.fixture(scope="module")
def smoke() -> dict:
    return _load(SMOKE)


# ── the smoke has to be the same run, only smaller ───────────────────────


@pytest.mark.parametrize("key", RUNTIME_KEYS)
def test_the_smoke_and_the_full_run_share_every_runtime_setting(full, smoke, key):
    """The whole basis for treating one as evidence about the other.

    Checked per key so a failure names the block that drifted instead of
    dumping both configs. A cheaper judge or a laxer rate-limit guard here
    would still produce a green smoke -- and would prove nothing about the
    run that follows it.
    """
    assert smoke[key] == full[key], (
        f"{key} differs between the smoke and the full run; the smoke no "
        f"longer predicts what the full run will do"
    )


def test_the_two_configs_differ_only_in_identity(full, smoke):
    """Guards the keys ``RUNTIME_KEYS`` does not enumerate.

    Without this, a runtime setting added to both files later would sit
    outside the parametrised comparison and drift unnoticed.
    """
    assert sorted(smoke) == sorted(full)
    differing = {key for key in full if full[key] != smoke[key]}
    assert differing == {"config_name", "description", "rerun_identity"}, (
        f"unexpected difference in {differing - {'config_name', 'description', 'rerun_identity'}}"
    )


# ── and it has to be the task the smoke was built for ────────────────────


def test_the_smoke_grades_exactly_the_two_damaged_tasks(smoke):
    identity = smoke["rerun_identity"]
    assert identity["task_ids"] == AUDIO_TASKS
    assert identity["expected_task_count"] == 2, (
        "expected_task_count is checked against the graded count at runtime; "
        "a stale 1 here fails the run after it has already been paid for"
    )


def test_the_smoke_task_is_one_the_full_run_will_also_grade(full, smoke):
    """Otherwise the smoke exercises a task the full run never reaches.

    A proper subset, not merely an overlap: equality would mean the two
    configs pin the same corpus and the smoke is not a smoke.
    """
    smoke_ids = set(smoke["rerun_identity"]["task_ids"])
    full_ids = set(full["rerun_identity"]["task_ids"])
    assert smoke_ids < full_ids


def test_the_smoke_reads_the_same_corpus_revision(full, smoke):
    """A different revision would grade a different version of the answer."""
    for field in ("experiment_id", "rubric_commit_sha", "inference_revision"):
        assert smoke["rerun_identity"][field] == full["rerun_identity"][field]


def test_the_full_run_still_pins_the_whole_gold_corpus(full):
    """Anchors the subset test above.

    If the full run's pin were ever trimmed, the subset assertion could pass
    while both configs graded a handful of tasks.
    """
    identity = full["rerun_identity"]
    assert identity["expected_task_count"] == 185
    assert len(identity["task_ids"]) == 185


# ── the smoke must not be able to damage the full run ────────────────────


def _inference_results(task_ids: list[str]) -> dict:
    return {"results": [{"task_id": task_id} for task_id in task_ids]}


def test_the_smoke_forks_its_output_away_from_the_full_run(full, smoke):
    """``subset`` is what puts a run under ``_diagnostic/<scope_sha>/``.

    The full run's pin covers its whole source corpus, so it classes as
    ``complete`` and stays on the published path. The smoke pins two tasks out
    of the same corpus, so it classes as ``subset`` and forks. That is the
    only reason a failed smoke cannot land in, or overwrite, the directory the
    eleven shards merge from.
    """
    corpus = _inference_results(full["rerun_identity"]["task_ids"])

    full_tasks, full_scope = filter_tasks_for_config(
        corpus, full, tasks_csv=None, limit=0
    )
    smoke_tasks, smoke_scope = filter_tasks_for_config(
        corpus, smoke, tasks_csv=None, limit=0
    )

    assert full_scope == "complete"
    assert len(full_tasks) == 185
    assert smoke_scope == "subset", (
        "a smoke that did not class as a subset would write into the full "
        "run's output directory"
    )
    assert [task["task_id"] for task in smoke_tasks] == AUDIO_TASKS


def test_naming_the_smoke_tasks_on_the_command_line_agrees_with_the_pin(smoke, full):
    """``--tasks`` is redundant here, and redundant is the point.

    Passing it makes the dispatch assert what the config already pins, so a
    config edited to point somewhere else is a refusal at classification time
    rather than a surprise in the graded output.
    """
    corpus = _inference_results(full["rerun_identity"]["task_ids"])
    tasks, scope = filter_tasks_for_config(
        corpus, smoke, tasks_csv=",".join(AUDIO_TASKS), limit=0
    )
    assert scope == "subset"
    assert [task["task_id"] for task in tasks] == AUDIO_TASKS


def test_naming_only_half_the_pin_is_refused(smoke, full):
    """The guard that made this config necessary, exercised from the inside.

    Half is the interesting case rather than a wholly unrelated task: it is
    what someone would actually type when trying to halve the bill, and it is
    the one narrowing that would still produce a plausible-looking result --
    a smoke that proved the audio path for one of the two damaged tasks and
    said nothing about the other.
    """
    corpus = _inference_results(full["rerun_identity"]["task_ids"])

    for half in AUDIO_TASKS:
        with pytest.raises(
            ValueError, match="conflicts with config pinned task selection"
        ):
            filter_tasks_for_config(corpus, smoke, tasks_csv=half, limit=0)

    with pytest.raises(ValueError, match="--limit conflicts"):
        filter_tasks_for_config(corpus, smoke, tasks_csv=None, limit=1)


def test_naming_a_different_task_than_the_pin_is_refused(smoke, full):
    """And an unrelated task is refused for the same reason."""
    corpus = _inference_results(full["rerun_identity"]["task_ids"])
    other = full["rerun_identity"]["task_ids"][0]
    assert other not in AUDIO_TASKS

    with pytest.raises(ValueError, match="conflicts with config pinned task selection"):
        filter_tasks_for_config(corpus, smoke, tasks_csv=other, limit=0)


def test_adding_a_grading_config_cannot_move_the_full_runs_fingerprint(tmp_path, full):
    """Why this file could be added while eleven shards were being planned.

    ``compute_grader_source_hash`` takes the one config it was handed, not the
    directory it lives in -- so a new sibling config is invisible to it. If
    that ever stopped being true, every existing shard would stop merging the
    moment anyone added a config, and this test would say so.
    """
    before = compute_grader_source_hash(FULL, full)

    intruder = CONFIGS / "zz_fingerprint_probe.yaml"
    assert not intruder.exists()
    intruder.write_text("config_name: 'probe'\n", encoding="utf-8")
    try:
        after = compute_grader_source_hash(FULL, full)
    finally:
        intruder.unlink()

    assert before == after, (
        "the grader source hash moved because an unrelated config file "
        "existed; shards graded before it was added can no longer merge"
    )


def test_the_smoke_and_the_full_run_do_not_share_a_fingerprint(full, smoke):
    """They are different runs and must be stored as such.

    The config file is itself hashed, so this holds automatically -- the test
    is here because the consequence of it not holding is that a one-task smoke
    would look like a resumable partial of the full run.
    """
    assert compute_grader_source_hash(SMOKE, smoke) != compute_grader_source_hash(
        FULL, full
    )
