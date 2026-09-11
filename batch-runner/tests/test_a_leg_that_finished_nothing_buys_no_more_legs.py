"""A relay leg that completed no task does not get to order another one.

The relay decides whether to keep going by counting the tasks still marked
``pending`` in the checkpoint in front of it. That count is a property of one
file: it says how much work is left, and it says nothing at all about whether
this leg did any. So a leg that burns its whole wall-clock budget and finishes
nothing hands on a checkpoint identical to the one it was given, the count is
unchanged, and the answer is "relay" — again, and again, for as many legs as
the budget allows. Each one costs a full run and real model calls.

This is not hypothetical. It is the failure that made someone sit and watch
run 34571840967 by hand, because nothing in the pipeline would have caught it.

The fix is to give the leg something to be compared against. ``restore_checkpoint``
already writes one small file naming the checkpoint it restored; it now writes a
second beside it holding the pending count at that moment, and the step that
publishes ``needs_relay`` refuses to publish it when the count did not move.

Two things are deliberately *not* guarded:

**Slow is not stopped.** One task finished out of two hundred is progress, and
the leg is allowed to continue. Only zero is refused.

**Finishing is never guarded.** When the run is complete there is no relay to
refuse, and a missing or stale counter cannot turn a finished run into a
failure.

The first leg has no restore and therefore no counter, and that absence is read
as "nothing was done yet" — which is true, and which means a first leg that
finished nothing is refused on the same rule as any other. A counter missing
*next to a generation state* is a different thing entirely: the pair is written
together, so a broken pair is a broken restore, and it is refused rather than
mistaken for a first leg.

Nothing here contacts the hub or the network.
"""

import json

import pytest

from scripts import relay_checkpoint as relay


def _progress(path, statuses):
    """A Step 2 checkpoint with one result per status given."""
    task_ids = [f"task-{index}" for index in range(len(statuses))]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "step2-progress-v2",
                "ordered_task_ids": task_ids,
                "total_tasks": len(task_ids),
                "results": [
                    {
                        "task_id": task_id,
                        "status": status,
                        "error": "wall_timeout",
                        "timestamp": "2026-09-11T00:00:00+00:00",
                    }
                    if status == "pending"
                    else {
                        "task_id": task_id,
                        "status": status,
                        "content": "done",
                        "deliverable_text": "done",
                        "deliverable_files": [],
                        "model": "test-model",
                        "usage": None,
                        "observability": {},
                        "latency_ms": 1.0,
                        "timestamp": "2026-09-11T00:00:00+00:00",
                    }
                    for task_id, status in zip(task_ids, statuses, strict=True)
                ],
            }
        ),
        encoding="utf-8",
    )
    return path


def _leg(tmp_path, *, entry=None, generation=None):
    """The two local state files a leg finds when it starts."""
    generation_path = tmp_path / "workspace" / "relay_checkpoint_generation"
    generation_path.parent.mkdir(parents=True, exist_ok=True)
    if generation is not None:
        generation_path.write_bytes(generation.encode("ascii"))
    if entry is not None:
        relay._leg_entry_path(generation_path).write_bytes(entry.encode("ascii"))
    return generation_path


# ── the failure this exists for ──────────────────────────────────────────────


def test_a_leg_that_finished_nothing_is_refused(tmp_path):
    """Same pending count in and out. The relay chain stops here."""
    progress = _progress(tmp_path / "progress.json", ["success", "pending", "pending"])
    generation_path = _leg(tmp_path, entry="2", generation="a" * 64)
    github_output = tmp_path / "github-output"
    github_output.touch()

    with pytest.raises(ValueError, match="relay leg finished no task"):
        relay.write_relay_status(progress, "42", github_output, generation_path)

    assert github_output.read_text(encoding="utf-8") == "", (
        "needs_relay must never reach the workflow for a leg that did nothing"
    )


def test_the_refusal_says_both_numbers(tmp_path):
    """Whoever reads the failed step should not have to go digging."""
    progress = _progress(tmp_path / "progress.json", ["pending", "pending"])
    generation_path = _leg(tmp_path, entry="2", generation="a" * 64)

    with pytest.raises(ValueError) as refused:
        relay.write_relay_status(
            progress, "42", tmp_path / "github-output", generation_path
        )

    assert "2 pending on entry" in str(refused.value)
    assert "2 pending on exit" in str(refused.value)


def test_a_leg_that_went_backwards_is_refused_too(tmp_path):
    """A pending count that grew is not progress by another name."""
    progress = _progress(tmp_path / "progress.json", ["pending", "pending"])
    generation_path = _leg(tmp_path, entry="1", generation="a" * 64)

    with pytest.raises(ValueError, match="relay leg finished no task"):
        relay.write_relay_status(
            progress, "42", tmp_path / "github-output", generation_path
        )


# ── what stays allowed ───────────────────────────────────────────────────────


def test_one_finished_task_is_enough_to_earn_another_leg(tmp_path):
    """The guard is about zero, not about slow.

    A leg that finishes a single task out of two hundred is making progress,
    just not much of it. Deciding that is too slow is a judgement about the
    budget, and it is not this function's to make.
    """
    progress = _progress(
        tmp_path / "progress.json", ["success"] + ["pending"] * 199
    )
    generation_path = _leg(tmp_path, entry="200", generation="a" * 64)
    github_output = tmp_path / "github-output"

    assert relay.write_relay_status(
        progress, "42", github_output, generation_path
    ) == (199, True)
    assert github_output.read_text(encoding="utf-8") == (
        "pending_count=199\nneeds_relay=true\n"
    )


def test_a_finished_run_is_never_measured_against_a_counter(tmp_path):
    """No relay to refuse, so a missing or stale counter cannot fail the run.

    This matters on the last leg, which is the one that carries the whole run's
    results to the upload steps. A guard that could fail *there* would throw
    away a completed benchmark over a bookkeeping file.
    """
    progress = _progress(tmp_path / "progress.json", ["success", "success"])
    generation_path = _leg(tmp_path, entry="not-a-number", generation="a" * 64)
    github_output = tmp_path / "github-output"

    assert relay.write_relay_status(
        progress, "0", github_output, generation_path
    ) == (0, False)
    assert github_output.read_text(encoding="utf-8") == (
        "pending_count=0\nneeds_relay=false\n"
    )


# ── the first leg, which has no counter to be compared against ───────────────


def test_the_first_leg_is_judged_against_the_whole_task_set(tmp_path):
    """No restore ran, so nothing was done, so nothing moving is refused."""
    progress = _progress(tmp_path / "progress.json", ["pending", "pending"])
    generation_path = _leg(tmp_path)

    assert not generation_path.exists()
    assert not relay._leg_entry_path(generation_path).exists()
    with pytest.raises(ValueError, match="2 pending on entry, 2 pending on exit"):
        relay.write_relay_status(
            progress, "42", tmp_path / "github-output", generation_path
        )


def test_the_first_leg_relays_normally_once_it_has_finished_something(tmp_path):
    progress = _progress(tmp_path / "progress.json", ["success", "pending"])
    generation_path = _leg(tmp_path)
    github_output = tmp_path / "github-output"

    assert relay.write_relay_status(
        progress, "42", github_output, generation_path
    ) == (1, True)
    assert github_output.read_text(encoding="utf-8") == (
        "pending_count=1\nneeds_relay=true\n"
    )


# ── a broken pair is not a first leg ─────────────────────────────────────────


def test_a_generation_state_without_its_counter_is_refused(tmp_path):
    """Fail closed. Reading this as a first leg would unguard a real relay.

    The two files are written together by the restore. If the generation state
    survived and the counter did not, something removed one of them, and the
    honest response is to stop rather than to fall back on the reading that
    happens to let the run continue.
    """
    progress = _progress(tmp_path / "progress.json", ["pending", "pending"])
    generation_path = _leg(tmp_path, generation="a" * 64)

    with pytest.raises(ValueError, match="missing beside a restored checkpoint"):
        relay.write_relay_status(
            progress, "42", tmp_path / "github-output", generation_path
        )


@pytest.mark.parametrize("entry", ["", " ", "1 ", "+1", "-1", "01", "1.0", "one"])
def test_a_counter_that_is_not_a_plain_count_is_refused(tmp_path, entry):
    """Not parsed leniently into a number that would let the relay proceed."""
    progress = _progress(tmp_path / "progress.json", ["pending", "pending"])
    generation_path = _leg(tmp_path, entry=entry, generation="a" * 64)

    with pytest.raises(ValueError, match="relay leg entry counter is invalid"):
        relay.write_relay_status(
            progress, "42", tmp_path / "github-output", generation_path
        )


def test_a_counter_larger_than_the_task_set_is_refused(tmp_path):
    """It cannot have been left by a restore of this run."""
    progress = _progress(tmp_path / "progress.json", ["pending", "pending"])
    generation_path = _leg(tmp_path, entry="3", generation="a" * 64)

    with pytest.raises(ValueError, match="outside the task set"):
        relay.write_relay_status(
            progress, "42", tmp_path / "github-output", generation_path
        )


def test_a_counter_that_is_a_symlink_is_refused(tmp_path):
    """The same rule the generation state has held since it was introduced."""
    progress = _progress(tmp_path / "progress.json", ["pending", "pending"])
    generation_path = _leg(tmp_path, generation="a" * 64)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.write_bytes(b"2")
    relay._leg_entry_path(generation_path).symlink_to(elsewhere)

    with pytest.raises(ValueError, match="is a symlink"):
        relay.write_relay_status(
            progress, "42", tmp_path / "github-output", generation_path
        )


# ── the pairing itself ───────────────────────────────────────────────────────


def test_the_counter_cannot_be_pointed_somewhere_other_than_the_pair(tmp_path):
    """One path is derived from the other, so they move together or not at all.

    If these were two independent settings, a run could be configured with a
    counter in one place and a generation state in another, and the "missing
    beside a restored checkpoint" check above would fire on a healthy run —
    or, worse, never fire on a broken one.
    """
    generation_path = tmp_path / "some" / "where" / "relay_checkpoint_generation"
    entry_path = relay._leg_entry_path(generation_path)

    assert entry_path.parent == generation_path.parent
    assert entry_path.name == relay.LEG_ENTRY_NAME
    assert entry_path != generation_path


def test_the_production_pair_sits_in_the_workspace_the_workflow_reads(tmp_path):
    """The workflow passes no path for either file; both come from here."""
    assert relay.LOCAL_GENERATION.parts[0] == "workspace"
    assert relay._leg_entry_path(relay.LOCAL_GENERATION) == (
        relay.LOCAL_GENERATION.parent / relay.LEG_ENTRY_NAME
    )


def test_the_relay_decision_itself_is_left_alone(tmp_path):
    """``resolve_relay_status`` still answers only for the checkpoint it sees.

    The comparison against the previous leg belongs to the step that publishes
    ``needs_relay``, not to the function that reads a checkpoint. Keeping them
    apart is what lets every existing caller of ``resolve_relay_status`` — and
    the tests around it — go on meaning what they meant.
    """
    progress = _progress(tmp_path / "progress.json", ["pending", "pending"])
    _leg(tmp_path, entry="2", generation="a" * 64)

    assert relay.resolve_relay_status(progress, "42") == (2, True)
