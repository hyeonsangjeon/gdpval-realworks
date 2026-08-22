"""Tests for the stalled shard-relay sweep.

The sweep re-derives two things ``step8_grade`` already knows -- which shard
owns a canonical position, and how an ordered id list is hashed. Re-deriving
rather than importing keeps a monitoring script from dragging in the judging
stack, but it also means the two can drift. The tests that matter most here are
therefore the ones that check the sweep against the real implementation instead
of against a transcribed constant.
"""

import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import step8_grade
from scripts import sweep_stalled_shard_relays as sweep


NOW = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)
FRESH = NOW - timedelta(hours=1)
OLD = NOW - timedelta(hours=30)
STALE_AFTER = timedelta(hours=8)


def _ids(count: int) -> list[str]:
    return [f"task-{index:04d}" for index in range(count)]


def _payload(task_ids, *, total, ordered_sha):
    return {
        "run_status": "partial",
        "expected_task_count": total,
        "expected_ordered_task_ids_sha256": ordered_sha,
        "tasks": [{"task_id": task_id} for task_id in task_ids],
    }


def _write_relay(
    tmp_path: Path,
    *,
    stem: str = "run-stem",
    total: int = 12,
    shard_count: int = 3,
    present=None,
    drop=(),
    final: bool = False,
) -> Path:
    """Lay out a ``_shards/<stem>/`` tree sliced the way step8 slices it."""
    canonical = _ids(total)
    ordered_sha = sweep.ordered_task_ids_sha256(canonical)
    grades = tmp_path / "grades"
    stem_dir = grades / "_shards" / stem
    stem_dir.mkdir(parents=True)
    if final:
        (grades / f"{stem}.json").write_text("{}", encoding="utf-8")

    indices = range(shard_count) if present is None else present
    for index in indices:
        held = [
            task_id
            for task_id in canonical[index::shard_count]
            if task_id not in drop
        ]
        name = f"shard-{index:03d}-of-{shard_count:03d}.json"
        (stem_dir / name).write_text(
            json.dumps(_payload(held, total=total, ordered_sha=ordered_sha)),
            encoding="utf-8",
        )
    return grades


def _sweep(grades: Path, *, committed_at=FRESH, canonical=None):
    return sweep.sweep(
        grades,
        now=NOW,
        stale_after=STALE_AFTER,
        commit_time=lambda path: committed_at,
        canonical_lookup=lambda sha: canonical,
    )


def _git_init_with_old_commit(root: Path, *, when="2026-01-02T03:04:05+00:00"):
    """Commit everything under ``root`` at a fixed, long-past timestamp.

    ``GIT_COMMITTER_DATE`` rather than ``--date``: the sweep reads ``%cI``, the
    committer date, and ``--date`` only moves the author date.
    """
    env = {**os.environ, "GIT_COMMITTER_DATE": when, "GIT_AUTHOR_DATE": when}

    def git(*args):
        subprocess.run(
            ["git", "-c", "core.hooksPath=/dev/null", *args],
            cwd=root,
            check=True,
            capture_output=True,
            env=env,
        )

    git("init", "-q")
    git("config", "user.email", "sweep@example.invalid")
    git("config", "user.name", "sweep")
    git("add", "-A")
    git("commit", "-q", "-m", "shards")

    # The fixture checks its own contract. Without this, a git that cannot make
    # or read a commit here surfaces later as a bare `assert None == datetime`
    # in whichever test happened to run, with nothing saying why.
    def probe(*args):
        return subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )

    proof = probe("log", "-1", "--format=%cI")
    assert proof.returncode == 0 and proof.stdout.strip(), (
        "the fixture repo has no readable commit: "
        f"rc={proof.returncode} out={proof.stdout!r} err={proof.stderr!r}"
    )

    # And that the commit is reachable *through a pathspec*, which is how the
    # sweep asks. A repo can satisfy the check above and still answer nothing
    # here, and that difference is invisible from the failing assertion in the
    # test body.
    filtered = probe("log", "-1", "--format=%cI", "--", ".")
    assert filtered.returncode == 0 and filtered.stdout.strip(), (
        "the fixture repo has a commit but no pathspec-filtered history: "
        f"rc={filtered.returncode} out={filtered.stdout!r} "
        f"err={filtered.stderr!r} "
        f"version={probe('--version').stdout.strip()!r} "
        f"tracked={probe('ls-files').stdout.split()!r} "
        f"status={probe('status', '--porcelain').stdout!r}"
    )
    return root


def test_a_published_final_is_not_the_sweeps_business(tmp_path):
    grades = _write_relay(tmp_path, drop={"task-0004"}, final=True)
    (verdict,) = _sweep(grades, committed_at=OLD)
    assert verdict.state == "merged"
    assert verdict.failing is False


def test_shards_that_have_not_published_yet_are_reported_not_failed(tmp_path):
    # The canary procedure runs shard 0 alone for hours before the rest go out.
    # That is a deliberate operator choice, so it must never turn anything red.
    grades = _write_relay(tmp_path, present=[0])
    (verdict,) = _sweep(grades, committed_at=OLD)
    assert verdict.state == "fanning-out"
    assert verdict.failing is False
    assert "waiting on 1, 2" in verdict.detail


def test_a_short_union_that_is_still_moving_is_left_alone(tmp_path):
    grades = _write_relay(tmp_path, drop={"task-0004"})
    (verdict,) = _sweep(grades, committed_at=FRESH)
    assert verdict.state == "working"
    assert verdict.failing is False
    assert "11/12" in verdict.detail


def test_a_short_union_that_stopped_moving_names_the_owing_shard(tmp_path):
    # task-0004 is canonical position 4, so with 3 shards it belongs to shard 1.
    grades = _write_relay(tmp_path, drop={"task-0004"})
    (verdict,) = _sweep(grades, committed_at=OLD, canonical=_ids(12))
    assert verdict.state == "stalled"
    assert verdict.failing is True
    assert verdict.shortfall_by_shard == {1: 1}
    assert verdict.missing_by_shard == {1: ["task-0004"]}
    assert verdict.quiet_for_hours == pytest.approx(30.0)


def test_a_stalled_relay_still_reports_counts_without_the_canonical_order(
    tmp_path,
):
    # No config pins this corpus, so the ids cannot be recovered. The shard
    # index and the size of its debt still can, and those are what a re-dispatch
    # needs.
    grades = _write_relay(tmp_path, drop={"task-0004", "task-0007"})
    (verdict,) = _sweep(grades, committed_at=OLD, canonical=None)
    assert verdict.state == "stalled"
    assert verdict.shortfall_by_shard == {1: 2}
    assert verdict.missing_by_shard == {}


def test_a_complete_union_nobody_merged_is_the_hole_194_left_open(tmp_path):
    grades = _write_relay(tmp_path)
    (verdict,) = _sweep(grades, committed_at=OLD)
    assert verdict.state == "unmerged"
    assert verdict.failing is True
    assert "all 12 tasks are in" in verdict.detail


def test_a_complete_union_is_given_time_to_merge_before_being_called_stuck(
    tmp_path,
):
    # The last shard commits its slice and merges in the same run, so a
    # complete union with no final is normal for the minutes in between.
    grades = _write_relay(tmp_path)
    (verdict,) = _sweep(grades, committed_at=FRESH)
    assert verdict.state == "working"
    assert verdict.failing is False


def test_shard_files_disagreeing_on_the_shard_count_are_malformed(tmp_path):
    # A stem holding both a 3-way and a 4-way split has no single answer to
    # "how many shards should be here", so no completeness claim can be made.
    grades = _write_relay(tmp_path, shard_count=3)
    stem_dir = grades / "_shards" / "run-stem"
    (stem_dir / "shard-003-of-004.json").write_text("{}", encoding="utf-8")
    (verdict,) = _sweep(grades)
    assert verdict.state == "malformed"
    assert verdict.failing is True
    assert "disagree on the shard count" in verdict.detail


def test_one_shard_index_published_under_two_counts_is_malformed(tmp_path):
    # Two files can collide on an index only by declaring different counts.
    # Reported as the collision rather than as the count split, because the
    # collision is the more specific fact and names the shard to look at.
    grades = _write_relay(tmp_path, shard_count=3)
    stem_dir = grades / "_shards" / "run-stem"
    (stem_dir / "shard-001-of-004.json").write_text("{}", encoding="utf-8")
    (verdict,) = _sweep(grades)
    assert verdict.state == "malformed"
    assert verdict.failing is True
    assert verdict.detail == "shard index 1 appears more than once"


def test_liveness_it_cannot_read_is_never_reported_as_a_failure(tmp_path):
    # A shallow clone has no history for the path. Guessing from file mtimes
    # would call every stem brand new after a CI checkout, so the sweep says
    # so and stays quiet.
    grades = _write_relay(tmp_path, drop={"task-0004"})
    (verdict,) = _sweep(grades, committed_at=None)
    assert verdict.state == "unknown"
    assert verdict.failing is False


def test_a_relay_with_no_shard_files_is_ignored(tmp_path):
    grades = tmp_path / "grades"
    (grades / "_shards" / "run-stem").mkdir(parents=True)
    (verdict,) = _sweep(grades)
    assert verdict.state == "empty"
    assert verdict.failing is False


def test_a_missing_shards_tree_sweeps_nothing(tmp_path):
    assert _sweep(tmp_path / "grades") == []


@pytest.mark.parametrize("total,shard_count", [(220, 9), (12, 3), (7, 7), (5, 1)])
def test_shard_ownership_agrees_with_the_slicer_that_assigns_it(
    total, shard_count
):
    """The sweep's ownership maths must track ``step8_grade._shard_slice``.

    Derived from the real slicer rather than from a remembered rule: if the
    split ever stops being a stride, this fails instead of quietly blaming the
    wrong shard in a report someone acts on.
    """
    tasks = [{"task_id": task_id} for task_id in _ids(total)]
    for shard_index in range(shard_count):
        held = step8_grade._shard_slice(
            tasks, shard_index=shard_index, shard_count=shard_count
        )
        assert sweep.stride_size(shard_index, total, shard_count) == len(held)
        for row in held:
            position = int(row["task_id"].removeprefix("task-"))
            assert sweep.stride_owner(position, shard_count) == shard_index


def test_the_ordered_id_hash_matches_the_one_the_shards_recorded():
    """Same bytes as ``step8_grade._ordered_task_ids_sha256``.

    The config-to-corpus match is made by comparing this hash against the value
    in the shard payloads. A drift here would silently stop the sweep from ever
    naming missing ids, degrading it to counts with no error anywhere.
    """
    for total in (0, 1, 12, 220):
        ids = _ids(total)
        assert sweep.ordered_task_ids_sha256(ids) == (
            step8_grade._ordered_task_ids_sha256(ids)
        )


def test_the_canonical_order_is_found_by_hash_not_by_config_name(tmp_path):
    config_dir = tmp_path / "grading_configs"
    config_dir.mkdir()
    wanted = _ids(12)
    (config_dir / "zzz-unrelated.yaml").write_text(
        "rerun_identity:\n  task_ids: [other-a, other-b]\n", encoding="utf-8"
    )
    (config_dir / "aaa-match.yaml").write_text(
        "rerun_identity:\n  task_ids:\n"
        + "".join(f"    - {task_id}\n" for task_id in wanted),
        encoding="utf-8",
    )
    found = sweep.canonical_ids_from_configs(
        config_dir, sweep.ordered_task_ids_sha256(wanted)
    )
    assert found == wanted
    assert sweep.canonical_ids_from_configs(config_dir, "0" * 64) is None


def test_a_config_that_is_not_yaml_does_not_stop_the_search(tmp_path):
    config_dir = tmp_path / "grading_configs"
    config_dir.mkdir()
    (config_dir / "aaa-broken.yaml").write_text("{[not yaml", encoding="utf-8")
    wanted = _ids(4)
    (config_dir / "bbb-good.yaml").write_text(
        "rerun_identity:\n  task_ids:\n"
        + "".join(f"    - {task_id}\n" for task_id in wanted),
        encoding="utf-8",
    )
    assert sweep.canonical_ids_from_configs(
        config_dir, sweep.ordered_task_ids_sha256(wanted)
    ) == wanted


def test_the_shipped_config_pins_a_corpus_the_sweep_can_recover():
    """The 220-task re-grade is the run this sweep exists to watch."""
    config_dir = Path(__file__).resolve().parent.parent / "grading_configs"
    import yaml

    config = yaml.safe_load(
        (config_dir / "regrade_exp003_v2_sol_max_score_excluded.yaml").read_text(
            encoding="utf-8"
        )
    )
    pinned = config["rerun_identity"]["task_ids"]
    found = sweep.canonical_ids_from_configs(
        config_dir, sweep.ordered_task_ids_sha256(pinned)
    )
    assert found == pinned
    assert len(found) == 220


def _explain_liveness(repo_root: Path, path: Path) -> str:
    """Re-run what ``last_commit_at`` runs and report all of it.

    This function depends on the behaviour of an external tool, so when it
    disagrees with the host the bare `assert None == datetime(...)` says
    nothing about which step went wrong. Evaluated only on failure.
    """
    root = repo_root.resolve()
    relative = os.path.relpath(path.resolve(), root)
    argv = [
        "git", "-c", "log.showSignature=false",
        "log", "-1", "--format=%cI", "--", relative,
    ]

    def run(*args):
        return subprocess.run(
            list(args), cwd=root, capture_output=True, text=True, check=False
        )

    got = subprocess.run(argv, cwd=root, capture_output=True, text=True, check=False)
    return (
        f"argv={argv!r} cwd={str(root)!r} "
        f"raw_root={str(repo_root)!r} raw_path={str(path)!r} relative={relative!r} "
        f"rc={got.returncode} out={got.stdout!r} err={got.stderr!r} "
        f"tracked={run('git', 'ls-files').stdout.split()!r} "
        f"version={run('git', '--version').stdout.strip()!r}"
    )


def test_git_liveness_reads_the_newest_commit_touching_the_stem(tmp_path):
    stem_dir = tmp_path / "grades" / "_shards" / "run-stem"
    stem_dir.mkdir(parents=True)
    (stem_dir / "shard-000-of-001.json").write_text("{}", encoding="utf-8")
    _git_init_with_old_commit(tmp_path, when="2026-08-20T09:00:00+00:00")

    seen = sweep.last_commit_at(tmp_path, stem_dir)
    assert seen == datetime(2026, 8, 20, 9, 0, tzinfo=timezone.utc), (
        _explain_liveness(tmp_path, stem_dir)
    )
    assert sweep.last_commit_at(tmp_path, tmp_path / "nope") is None


def test_git_liveness_is_none_outside_a_repository(tmp_path):
    assert sweep.last_commit_at(tmp_path, tmp_path) is None


def test_liveness_survives_the_relative_roots_the_workflow_passes(
    tmp_path, monkeypatch
):
    """The shipped defaults are ``--repo-root ..`` and ``--grades-root
    ../data/grades``, both relative to ``batch-runner/``.

    Handed through unchanged, the stem pathspec begins with ``..`` and git
    refuses it as outside the work tree: every stem reports ``unknown`` and the
    sweep is silently useless in the one workflow it exists for. No other test
    here would catch that, and neither does running it against the real
    repository -- a published final short-circuits before liveness is ever
    read.
    """
    repo = tmp_path / "repo"
    (repo / "batch-runner").mkdir(parents=True)
    _write_relay(repo / "data", shard_count=1, total=4, drop={"task-0002"})
    _git_init_with_old_commit(repo)
    monkeypatch.chdir(repo / "batch-runner")

    rc = sweep.main(
        ["--grades-root", "../data/grades", "--repo-root", "..",
         "--config-dir", "grading_configs"]
    )
    assert rc == 1


def test_the_report_names_the_shard_and_annotates_only_failures():
    stalled = sweep.RelayVerdict(
        stem="s",
        state="stalled",
        detail="stopped",
        shortfall_by_shard={4: 2},
        missing_by_shard={4: ["a", "b"]},
    )
    healthy = sweep.RelayVerdict(stem="h", state="working", detail="moving")
    lines = sweep.render([stalled, healthy], annotate=True)
    assert "    shard 004 still owes 2 task(s): a, b" in lines
    assert sum(line.startswith("::error") for line in lines) == 1
    assert sweep.render([stalled], annotate=False) == [
        line for line in sweep.render([stalled], annotate=True)
        if not line.startswith("::error")
    ]


def test_the_cli_exits_one_when_a_relay_needs_attention(tmp_path, capsys):
    # End to end over a real git tree: a single-shard relay holding 3 of its 4
    # tasks, last committed long ago, is unambiguously stopped.
    grades = _write_relay(tmp_path, shard_count=1, total=4, drop={"task-0002"})
    _git_init_with_old_commit(tmp_path)

    rc = sweep.main(
        [
            "--grades-root",
            str(grades),
            "--config-dir",
            str(tmp_path / "absent"),
            "--repo-root",
            str(tmp_path),
        ]
    )
    captured = capsys.readouterr()
    assert rc == 1
    assert "[stalled] run-stem" in captured.out
    assert "shard 000 still owes 1 task(s)" in captured.out
    assert "need attention" in captured.err


def test_the_cli_exits_zero_when_every_relay_is_accounted_for(tmp_path, capsys):
    grades = _write_relay(tmp_path, shard_count=1, total=4)
    _git_init_with_old_commit(tmp_path)

    rc = sweep.main(
        [
            "--grades-root",
            str(grades),
            "--config-dir",
            str(tmp_path / "absent"),
            "--repo-root",
            str(tmp_path),
            "--stale-after-hours",
            "100000",
        ]
    )
    assert rc == 0
    assert "[working] run-stem" in capsys.readouterr().out


def test_a_non_positive_staleness_window_is_rejected(tmp_path, capsys):
    assert sweep.main(["--stale-after-hours", "0"]) == 2
    assert "must be positive" in capsys.readouterr().err
