"""A halt is not always the halting shard's own business.

Three defects in the sharded path, and the tests below are grouped by which.

The matrix's ``fail-fast: false`` is correct for most of the eight stop rules
and wrong for five of them, and the difference is not severity: it is whether
the thing that tripped is shared by every shard. These check that the split is
argued rather than assumed, that a whole-run halt actually stops the next wave,
and that the stage-level check exists at all -- ``coverage_problems`` was
written, tested, named in the workflow comment as the thing that earns the
sentence "the stage ran", and called by nothing that runs.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

SCRIPTS = BATCH_RUNNER_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import check_agentic_v2_stage_coverage as checker  # noqa: E402
from core.agentic_v2_preregistration import (  # noqa: E402
    RULES_ABOUT_THE_WHOLE_RUN,
    RULES_THAT_ARE_ONE_SHARDS_OWN,
    STOP_RULES,
    cohorts,
)
from core.agentic_v2_shard_collection import (  # noqa: E402
    ShardRecordUnreadable,
    read_shard_records,
    siblings_that_stopped_the_run,
    stage_problems,
)

COHORT = cohorts()["trial_30"]


def _record(index: int, of: int, *, halt: dict | None = None) -> dict:
    """One shard's record, split the way the runner splits: by stride."""
    mine = tuple(COHORT[index - 1 :: of])
    return {
        "stage": "trial_30",
        "shard": {
            "index": index,
            "of": of,
            "task_count": len(mine),
            "cohort_size": len(COHORT),
            "task_ids": list(mine),
            "covers_whole_stage": of == 1,
        },
        "run": {
            "run_id": f"r{index}",
            "results": [],
            "summary": {},
            "stopped_early": halt,
            "skipped_on_resume": [],
        },
    }


def _halt(index: int, detail: str = "a detail") -> dict:
    return {
        "rule_index": index,
        "rule": STOP_RULES[index],
        "detail": detail,
        "after_task": COHORT[0],
    }


def _written(tmp_path: Path, records: list[dict]) -> Path:
    """Laid out the way actions/download-artifact leaves them."""
    root = tmp_path / "downloaded"
    for record in records:
        folder = root / f"agentic-v2-trial_30-shard-{record['shard']['index']}"
        folder.mkdir(parents=True)
        (folder / "run_record.json").write_text(
            json.dumps(record, indent=2), encoding="utf-8"
        )
    return root


# ── the split itself ──────────────────────────────────────────────────────


def test_every_stop_rule_is_on_exactly_one_side_of_the_split():
    """The guard that makes a ninth rule a decision rather than a default.

    Without it, a rule added to the tuple would be absent from both dicts and
    treated as the shard's own -- the permissive answer, arrived at by nobody.
    """
    whole = set(RULES_ABOUT_THE_WHOLE_RUN)
    own = set(RULES_THAT_ARE_ONE_SHARDS_OWN)

    assert whole | own == set(range(len(STOP_RULES)))
    assert not (whole & own)


def test_the_rule_about_the_model_that_answered_is_not_a_shards_own():
    """Rule 0 is the case the whole split exists for.

    One deployment answers every shard. A reply naming something the plan does
    not pin will name it again for the sixteen still to come.
    """
    assert 0 in RULES_ABOUT_THE_WHOLE_RUN
    assert 0 not in RULES_THAT_ARE_ONE_SHARDS_OWN


def test_the_budget_rule_is_shared_because_the_amount_is_for_the_cohort():
    """The approval prices a stage, never a job.

    Sixteen shards each individually "within budget" is exactly how an approved
    amount gets spent several times over.
    """
    assert 4 in RULES_ABOUT_THE_WHOLE_RUN
    assert "cohort" in RULES_ABOUT_THE_WHOLE_RUN[4]


def test_the_runner_defect_rule_stays_the_shards_own():
    """Where `fail-fast: false` is right, nothing here overrides it.

    Three consecutive runner defects is a fact about this code on this shard's
    tasks. The next shard's tasks are different ones, and stopping it would
    throw away work that was paid for -- which is the matrix comment's argument,
    and it is correct here.
    """
    assert 6 in RULES_THAT_ARE_ONE_SHARDS_OWN
    assert 6 not in RULES_ABOUT_THE_WHOLE_RUN


def test_each_side_says_why_rather_than_only_which():
    """A classification with no reason cannot be argued with, only obeyed."""
    for why in list(RULES_ABOUT_THE_WHOLE_RUN.values()) + list(
        RULES_THAT_ARE_ONE_SHARDS_OWN.values()
    ):
        assert len(why.split()) >= 8


# ── stopping the next wave ────────────────────────────────────────────────


def test_a_sibling_that_halted_on_the_model_name_stops_the_next_shard():
    reasons = siblings_that_stopped_the_run(
        [("shard-1", _record(1, 3, halt=_halt(0, "named gpt-4o")))]
    )

    assert len(reasons) == 1
    assert "rule 0" in reasons[0]
    assert "named gpt-4o" in reasons[0]


def test_a_sibling_that_halted_on_its_own_trouble_does_not():
    """The distinction the matrix comment gets right, kept."""
    assert (
        siblings_that_stopped_the_run(
            [("shard-1", _record(1, 3, halt=_halt(6)))]
        )
        == []
    )


def test_a_sibling_that_finished_cleanly_stops_nothing():
    assert siblings_that_stopped_the_run([("shard-1", _record(1, 3))]) == []


def test_a_halt_on_a_rule_this_code_cannot_place_stops_the_next_shard():
    """The unrecognised case resolves towards stopping, not towards spending.

    A record naming a rule this code cannot place is either a ninth rule added
    without revisiting the split or a record from something else entirely.
    Both are reasons to stop rather than to carry on paying.
    """
    reasons = siblings_that_stopped_the_run(
        [
            (
                "shard-1",
                _record(
                    1,
                    3,
                    halt={
                        "rule_index": 99,
                        "rule": "something nobody has written yet",
                        "detail": "",
                        "after_task": COHORT[0],
                    },
                ),
            )
        ]
    )

    assert len(reasons) == 1
    assert "cannot place" in reasons[0]


def test_a_halt_is_placed_by_its_text_when_the_index_is_unusable():
    """Records outlive the code that wrote them.

    The index is what the split is keyed on, but a record read by something
    holding a different version of this tuple still carries the sentence.
    """
    reasons = siblings_that_stopped_the_run(
        [
            (
                "shard-1",
                _record(
                    1,
                    3,
                    halt={
                        "rule_index": None,
                        "rule": STOP_RULES[0],
                        "detail": "",
                        "after_task": COHORT[0],
                    },
                ),
            )
        ]
    )

    assert len(reasons) == 1
    assert "cannot place" not in reasons[0]
    assert "rule 0" in reasons[0]


# ── whether the stage ran ─────────────────────────────────────────────────


def test_all_three_shards_covering_the_cohort_once_is_the_stage():
    assert (
        stage_problems(
            [(f"shard-{i}", _record(i, 3)) for i in (1, 2, 3)], task_ids=COHORT
        )
        == []
    )


def test_a_missing_shard_is_not_the_stage_however_green_the_others_are():
    problems = stage_problems(
        [(f"shard-{i}", _record(i, 3)) for i in (1, 2)], task_ids=COHORT
    )

    assert problems
    assert any("did not run" in problem for problem in problems)


def test_a_whole_run_halt_puts_the_other_shards_results_in_question():
    problems = stage_problems(
        [
            ("shard-1", _record(1, 3, halt=_halt(0))),
            ("shard-2", _record(2, 3)),
            ("shard-3", _record(3, 3)),
        ],
        task_ids=COHORT,
    )

    assert len(problems) == 1
    assert "not one shard's own" in problems[0]
    assert "other shards' results are in question" in problems[0]


def test_a_shards_own_halt_is_reported_without_condemning_the_others():
    """Both halves said, because only saying one of them misleads.

    The other shards' results do stand. This shard's tasks still did not all
    run, so the stage is still not the stage.
    """
    problems = stage_problems(
        [
            ("shard-1", _record(1, 3, halt=_halt(7))),
            ("shard-2", _record(2, 3)),
            ("shard-3", _record(3, 3)),
        ],
        task_ids=COHORT,
    )

    assert len(problems) == 1
    assert "other shards' results stand" in problems[0]
    assert "did not all run" in problems[0]


def test_coverage_is_checked_against_the_cohort_and_not_against_itself():
    """The check that only works with the real list.

    Every other coverage question can be answered from the shards alone. "Was
    anything missed" cannot: derive the expected set from what ran and the
    answer is no by construction. This is why the cohort comes from the
    committed catalogue rather than from the records.
    """
    shards = [(f"shard-{i}", _record(i, 3)) for i in (1, 2, 3)]

    problems = stage_problems(shards, task_ids=list(COHORT) + ["a-task-nobody-ran"])

    assert any("a-task-nobody-ran" in problem for problem in problems)


def test_no_records_at_all_is_a_problem_and_not_an_empty_pass():
    assert stage_problems([], task_ids=COHORT) == [
        "no shard record was found, so nothing here can say what ran"
    ]


# ── reading what the shards left behind ───────────────────────────────────


def test_records_are_found_wherever_the_download_action_put_them(tmp_path):
    root = _written(tmp_path, [_record(i, 3) for i in (1, 2, 3)])

    found = read_shard_records(root)

    assert len(found) == 3
    assert [name for name, _ in found] == [
        "agentic-v2-trial_30-shard-1",
        "agentic-v2-trial_30-shard-2",
        "agentic-v2-trial_30-shard-3",
    ]


def test_an_unreadable_record_raises_rather_than_being_reported_as_fine(tmp_path):
    """"Checked and clean" and "could not be checked" must not look alike."""
    root = tmp_path / "downloaded" / "shard-1"
    root.mkdir(parents=True)
    (root / "run_record.json").write_text("{not json", encoding="utf-8")

    with pytest.raises(ShardRecordUnreadable):
        read_shard_records(tmp_path / "downloaded")


def test_a_record_with_no_shard_object_cannot_be_counted_as_coverage(tmp_path):
    with pytest.raises(ShardRecordUnreadable):
        stage_problems([("shard-1", {"run": {}})], task_ids=COHORT)


# ── the script, end to end ────────────────────────────────────────────────


def test_the_collect_mode_passes_a_stage_that_actually_ran(tmp_path, capsys):
    root = _written(tmp_path, [_record(i, 3) for i in (1, 2, 3)])

    code = checker.main(
        ["--records", str(root), "--stage", "trial_30", "--collect"]
    )

    assert code == 0
    assert "trial_30 ran" in capsys.readouterr().out


def test_the_collect_mode_fails_a_stage_with_a_whole_run_halt(tmp_path, capsys):
    root = _written(
        tmp_path,
        [_record(1, 3, halt=_halt(0)), _record(2, 3), _record(3, 3)],
    )

    code = checker.main(
        ["--records", str(root), "--stage", "trial_30", "--collect"]
    )

    assert code == 1
    assert "has not run" in capsys.readouterr().err


def test_the_before_starting_mode_lets_the_first_wave_through(tmp_path, capsys):
    """No siblings have uploaded yet, which is the normal first case.

    A missing directory must not read as a problem here, or no stage could ever
    begin.
    """
    code = checker.main(
        [
            "--records",
            str(tmp_path / "nothing-here"),
            "--stage",
            "trial_30",
            "--before-starting",
        ]
    )

    assert code == 0
    assert "so it starts" in capsys.readouterr().out


def test_the_before_starting_mode_refuses_after_a_whole_run_halt(tmp_path, capsys):
    root = _written(tmp_path, [_record(1, 3, halt=_halt(0))])

    code = checker.main(
        ["--records", str(root), "--stage", "trial_30", "--before-starting"]
    )

    captured = capsys.readouterr()
    assert code == 1
    assert "will not start" in captured.err
    assert "already in flight are not stopped" in captured.err


def test_the_before_starting_mode_starts_after_a_shards_own_halt(tmp_path, capsys):
    root = _written(tmp_path, [_record(1, 3, halt=_halt(6))])

    code = checker.main(
        ["--records", str(root), "--stage", "trial_30", "--before-starting"]
    )

    assert code == 0
    assert "none halted" in capsys.readouterr().out


def test_a_missing_directory_is_a_failure_when_collecting(tmp_path, capsys):
    """The same absence, answered oppositely, because it means opposite things.

    Before starting it means nobody has finished yet. Collecting, it means the
    artifacts never arrived and there is nothing to speak for.
    """
    code = checker.main(
        [
            "--records",
            str(tmp_path / "nothing-here"),
            "--stage",
            "trial_30",
            "--collect",
        ]
    )

    assert code == 1
    assert "nothing here can say what ran" in capsys.readouterr().err


def test_an_unreadable_record_is_never_a_pass_in_either_mode(tmp_path, capsys):
    root = tmp_path / "downloaded" / "shard-1"
    root.mkdir(parents=True)
    (root / "run_record.json").write_text("{not json", encoding="utf-8")

    for mode in ("--before-starting", "--collect"):
        code = checker.main(
            [
                "--records",
                str(tmp_path / "downloaded"),
                "--stage",
                "trial_30",
                mode,
            ]
        )
        assert code == 1, mode
        assert "could not be read" in capsys.readouterr().err


def test_the_five_task_stage_is_one_shard_and_still_answerable(tmp_path, capsys):
    """The stage the next paid run is, checked rather than assumed.

    `advance_check_5` is a matrix of one, so none of the cross-shard trouble
    above can reach it. That is a reason it is safe to run first, not a reason
    the check should be skipped for it.
    """
    five = cohorts()["advance_check_5"]
    folder = tmp_path / "downloaded" / "agentic-v2-advance_check_5-shard-1"
    folder.mkdir(parents=True)
    (folder / "run_record.json").write_text(
        json.dumps(
            {
                "stage": "advance_check_5",
                "shard": {
                    "index": 1,
                    "of": 1,
                    "task_count": len(five),
                    "cohort_size": len(five),
                    "task_ids": list(five),
                    "covers_whole_stage": True,
                },
                "run": {"stopped_early": None},
            }
        ),
        encoding="utf-8",
    )

    code = checker.main(
        [
            "--records",
            str(tmp_path / "downloaded"),
            "--stage",
            "advance_check_5",
            "--collect",
        ]
    )

    assert code == 0
    assert "5 tasks" in capsys.readouterr().out


# ── the wiring, which is the whole point ──────────────────────────────────
#
# `coverage_problems` was correct, tested and called by nothing for as long as
# it existed. A test of the function would have stayed green through all of it.
# These read the workflow.

WORKFLOW = (
    BATCH_RUNNER_ROOT.parent / ".github" / "workflows" / "agentic-v2-stage-run.yml"
)


def _workflow() -> dict:
    import yaml

    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def test_the_stage_coverage_check_is_actually_invoked_by_the_workflow():
    assert "check_agentic_v2_stage_coverage.py" in WORKFLOW.read_text(
        encoding="utf-8"
    )


def test_a_shard_asks_before_starting_and_asks_before_it_runs():
    """Order matters more than presence.

    Asked after `Run` it would be a report. Asked before, it is a refusal, and
    everything ahead of it in the job is free.
    """
    steps = [step.get("name") or "" for step in _workflow()["jobs"]["paid"]["steps"]]
    refusal = steps.index("Refuse to start if one of them stopped the run")
    assert refusal < steps.index("Run")


def test_the_collect_job_runs_even_when_a_shard_failed():
    """The case it exists for is the one where something went wrong.

    `needs: paid` alone would skip it exactly then.
    """
    collect = _workflow()["jobs"]["collect"]
    assert collect["needs"] == "paid"
    assert "always()" in collect["if"]


def test_the_job_that_judges_the_run_cannot_reach_azure():
    """No `id-token`, so it cannot mint a session and cannot spend.

    A checker that could also run the thing it judges is a checker with
    something to protect.
    """
    assert "id-token" not in _workflow()["jobs"]["collect"]["permissions"]


def test_the_shards_can_read_this_runs_artifacts_and_nothing_more():
    """`actions: read` is what listing sibling artifacts needs.

    Pinned because the refusal silently becomes a no-op without it: the
    download fails, `continue-on-error` swallows it, the directory is missing,
    and a missing directory is how the first wave legitimately starts.
    """
    paid = _workflow()["jobs"]["paid"]["permissions"]
    assert paid["actions"] == "read"
    assert "write" not in str(paid.get("actions", ""))
