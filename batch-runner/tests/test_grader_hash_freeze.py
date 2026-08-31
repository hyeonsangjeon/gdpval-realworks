"""Tests for the grader-hash merge freeze.

The interesting one is `TestThePredicateStillCoversWhatIsActuallyHashed`. The
predicate in `check_grader_hash_freeze` is a hand-written mirror of the path
set `compute_grader_source_hash` builds at runtime, and a hand-written mirror
of anything rots. So rather than asserting against a second hand-written list,
these tests watch the real hash function read files and require the predicate
to have classified every one of them as hash-moving. Add an input to the hash
and this test fails until the predicate learns about it.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

BATCH_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BATCH_ROOT.parent
SCRIPT_PATH = BATCH_ROOT / "scripts" / "check_grader_hash_freeze.py"

sys.path.insert(0, str(BATCH_ROOT))

_spec = importlib.util.spec_from_file_location("check_grader_hash_freeze", SCRIPT_PATH)
assert _spec and _spec.loader
freeze = importlib.util.module_from_spec(_spec)
# Register before executing: @dataclass resolves KW_ONLY by looking the
# defining module up in sys.modules, and raises AttributeError on None if the
# module was loaded by path and never registered.
sys.modules["check_grader_hash_freeze"] = freeze
_spec.loader.exec_module(freeze)

import step8_grade  # noqa: E402


def job(name: str, conclusion: str | None = None) -> dict:
    return {"name": name, "conclusion": conclusion}


def live(run_id: str = "1", *, jobs: list[dict] | None, status: str = "in_progress") -> dict:
    run = {"id": run_id, "status": status, "url": f"https://x/{run_id}"}
    if jobs is not None:
        run["jobs"] = jobs
    return run


# Copied verbatim off run 33381143279, the third audio smoke, which was paid.
# Two things about this list are the whole reason the classifier reads
# conclusions instead of names: `grade-dry-run` is present in a *paid* run,
# and approve-paid arrives under its rendered display name.
APPROVE_PAID_DISPLAY_NAME = (
    "Approve paid Sol Max grading (exp_gold_baseline, "
    "gold_smoke_audio_v2_sol_max.yaml, chunk 0, shard 0/1)"
)
REAL_PAID_JOBS = [
    job("validate-request", "success"),
    job(APPROVE_PAID_DISPLAY_NAME, "success"),
    job("grade-dry-run", "skipped"),
    job("grade", "success"),
]
REAL_DRY_JOBS = [
    job("validate-request", "success"),
    job(APPROVE_PAID_DISPLAY_NAME, "skipped"),
    job("grade-dry-run", "success"),
    job("grade", "skipped"),
]

PAID = live("33400000001", jobs=REAL_PAID_JOBS)
DRY = live("33400000002", jobs=REAL_DRY_JOBS)
# At the environment gate: approve-paid exists with no conclusion yet, and
# `grade` has not been created at all.
AT_THE_GATE = live(
    "33400000003",
    jobs=[job("validate-request", "success"), job(APPROVE_PAID_DISPLAY_NAME, None)],
    status="waiting",
)


class TestThePredicateStillCoversWhatIsActuallyHashed:
    """Coupling tests: drive the real hash function, watch what it reads."""

    @staticmethod
    def _paths_read_by_the_hash(monkeypatch, config_path: Path) -> list[str]:
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        seen: list[Path] = []
        real_read_bytes = Path.read_bytes

        def spy(self: Path) -> bytes:
            seen.append(self)
            return real_read_bytes(self)

        monkeypatch.chdir(BATCH_ROOT)
        monkeypatch.setattr(Path, "read_bytes", spy)
        step8_grade.compute_grader_source_hash(str(config_path), config)
        monkeypatch.undo()

        return sorted(
            {p.resolve().relative_to(REPO_ROOT).as_posix() for p in seen}
        )

    @pytest.mark.parametrize(
        "config_name",
        sorted(p.name for p in (BATCH_ROOT / "grading_configs").glob("*.yaml")),
    )
    def test_every_hashed_input_is_classified_as_hash_moving(
        self, monkeypatch, config_name: str
    ) -> None:
        config_path = BATCH_ROOT / "grading_configs" / config_name
        hashed = self._paths_read_by_the_hash(monkeypatch, config_path)

        assert hashed, "the hash function read nothing, so this proves nothing"

        missed = [p for p in hashed if not freeze.is_grader_source_path(p)]
        assert not missed, (
            "compute_grader_source_hash reads these files, but the freeze check "
            "would let a pull request touching them merge mid-run:\n  "
            + "\n  ".join(missed)
            + "\n\nAdd them to _EXACT_HASHED_FILES or _HASHED_TREES in "
            "batch-runner/scripts/check_grader_hash_freeze.py."
        )

    def test_the_hashed_set_is_large_enough_to_be_the_real_thing(
        self, monkeypatch
    ) -> None:
        """Guards the guard: a spy that silently caught nothing would make the
        test above vacuously green."""
        hashed = self._paths_read_by_the_hash(
            monkeypatch, BATCH_ROOT / "grading_configs" / "gold_ceiling_185_v2_sol_max.yaml"
        )
        assert len(hashed) > 20
        assert "batch-runner/step8_grade.py" in hashed
        assert "batch-runner/requirements.txt" in hashed
        assert "batch-runner/prompts/grader_judge.md" in hashed
        assert (
            "batch-runner/grading_configs/gold_ceiling_185_v2_sol_max.yaml" in hashed
        )
        assert any(p.startswith("batch-runner/core/") for p in hashed)


class TestWhichPathsMoveTheHash:
    @pytest.mark.parametrize(
        "path",
        [
            "batch-runner/step8_grade.py",
            "batch-runner/core/grader.py",
            "batch-runner/core/perception/audio.py",
            "batch-runner/core/tools/read_deliverable.py",
            "batch-runner/schemas/grade.schema.json",
            "batch-runner/requirements.txt",
            "batch-runner/scripts/download_inference_from_hf.py",
            "batch-runner/prompts/grader_judge.md",
            "batch-runner/prompts/grader_judge_v2.md",
            "batch-runner/grading_configs/gold_ceiling_185_v2_sol_max.yaml",
        ],
    )
    def test_hash_moving(self, path: str) -> None:
        assert freeze.is_grader_source_path(path)

    @pytest.mark.parametrize(
        "path",
        [
            # Negative controls. Each of these is a file somebody plausibly
            # edits during a 60-hour run, and freezing them would make the
            # guard something people route around instead of trusting.
            "batch-runner/tests/test_grader.py",
            "batch-runner/step2_run_inference.py",
            "batch-runner/experiments/exp_gold_baseline.yaml",
            "batch-runner/core/README.md",
            "batch-runner/core/fixtures/sample.json",
            ".github/workflows/grade-run.yml",
            ".github/workflows/grader-hash-freeze.yml",
            "src/pages/Grades.tsx",
            "scripts/aggregate-grades.mjs",
            "tasks/rebuilding_grading_task/311-third-audio-smoke-pass.md",
            "README.md",
            ".gitignore",
        ],
    )
    def test_hash_neutral(self, path: str) -> None:
        assert not freeze.is_grader_source_path(path)

    def test_the_guard_does_not_freeze_itself(self) -> None:
        """The check must be able to land, and to be fixed, during a paid run.
        A guard that its own repair cannot get past is a guard nobody keeps."""
        assert not freeze.is_grader_source_path(
            "batch-runner/scripts/check_grader_hash_freeze.py"
        )
        assert not freeze.is_grader_source_path(
            "batch-runner/tests/test_grader_hash_freeze.py"
        )

    def test_leading_dot_slash_is_tolerated(self) -> None:
        assert freeze.is_grader_source_path("./batch-runner/core/grader.py")

    def test_a_lookalike_outside_batch_runner_is_neutral(self) -> None:
        assert not freeze.is_grader_source_path("vendor/batch-runner/core/grader.py")
        assert not freeze.is_grader_source_path("batch-runner-old/core/grader.py")


class TestWhichRunsBlock:
    def test_a_real_paid_run_blocks(self) -> None:
        d = freeze.decide(["batch-runner/core/grader.py"], [PAID])
        assert d.frozen
        assert d.blocking_runs[0].run_id == "33400000001"

    def test_a_real_dry_run_does_not_block(self) -> None:
        assert not freeze.decide(["batch-runner/core/grader.py"], [DRY]).frozen

    def test_a_dry_run_is_not_paid_merely_for_listing_a_skipped_grade_job(self) -> None:
        """The bug this whole class exists to pin. Every dry run's job list
        contains an entry named `grade`; it just concluded `skipped`."""
        assert any(j["name"] == "grade" for j in REAL_DRY_JOBS)
        assert not freeze.classify_runs([DRY])[0].paid

    def test_a_paid_run_is_not_dry_merely_for_listing_a_skipped_dry_job(self) -> None:
        """And the mirror image: every paid run lists `grade-dry-run`."""
        assert any(j["name"] == "grade-dry-run" for j in REAL_PAID_JOBS)
        assert freeze.classify_runs([PAID])[0].paid

    def test_a_finished_run_does_not_block(self) -> None:
        done = live("9", jobs=REAL_PAID_JOBS, status="completed")
        assert not freeze.decide(["batch-runner/core/grader.py"], [done]).frozen

    @pytest.mark.parametrize(
        "status", ["queued", "in_progress", "waiting", "pending", "requested"]
    )
    def test_every_live_status_blocks(self, status: str) -> None:
        run = live("9", jobs=REAL_PAID_JOBS, status=status)
        assert freeze.decide(["batch-runner/core/grader.py"], [run]).frozen

    def test_waiting_at_the_approval_gate_blocks(self) -> None:
        """A run parked at the environment gate has spent nothing yet, but the
        approval is usually seconds away and the merge would land inside it.

        There is no `grade` job in its list at this point -- approve-paid is
        the job holding the gate open, and `grade` needs it. Classifying on
        `grade` alone would have opened the merge window at exactly the wrong
        moment."""
        assert freeze.decide(["batch-runner/core/grader.py"], [AT_THE_GATE]).frozen

    def test_a_paid_job_still_running_blocks(self) -> None:
        """A job in flight reports a null conclusion, which is not `skipped`."""
        run = live("9", jobs=[job("grade", None)])
        d = freeze.decide(["batch-runner/core/grader.py"], [run])
        assert d.frozen
        assert "not skipped" in d.blocking_runs[0].paid_reason

    def test_a_failed_paid_job_still_blocks(self) -> None:
        """Money was spent regardless, and a resume chunk may follow."""
        run = live("9", jobs=[job("grade", "failure")])
        assert freeze.decide(["batch-runner/core/grader.py"], [run]).frozen

    def test_the_approve_job_is_matched_by_prefix_not_by_key(self) -> None:
        """The jobs API never exposes the key `approve-paid`."""
        assert freeze.is_paid_path_job(APPROVE_PAID_DISPLAY_NAME)
        assert not freeze.is_paid_path_job("approve-paid")

    def test_a_run_too_early_to_have_branched_is_paid(self) -> None:
        """`validate-request` runs on both paths, so it says nothing."""
        run = live("9", jobs=[job("validate-request", None)])
        d = freeze.decide(["batch-runner/core/grader.py"], [run])
        assert d.frozen
        assert "too early" in d.blocking_runs[0].paid_reason

    def test_a_neutral_diff_is_green_even_during_a_paid_run(self) -> None:
        d = freeze.decide(["README.md", "src/pages/Grades.tsx"], [PAID])
        assert not d.frozen
        assert d.moving_paths == ()

    def test_a_hash_moving_diff_is_green_when_nothing_is_running(self) -> None:
        d = freeze.decide(["batch-runner/core/grader.py"], [])
        assert not d.frozen
        assert d.moving_paths == ("batch-runner/core/grader.py",)
        assert "fresh smoke" in freeze.render(d)

    def test_one_paid_run_among_several_dry_ones_still_freezes(self) -> None:
        runs = [DRY, live("3", jobs=REAL_DRY_JOBS), PAID]
        assert freeze.decide(["batch-runner/prompts/grader_judge.md"], runs).frozen


class TestFailClosed:
    def test_a_run_with_no_job_list_counts_as_paid(self) -> None:
        d = freeze.decide(["batch-runner/core/grader.py"], [live("9", jobs=None)])
        assert d.frozen
        assert "unavailable" in d.blocking_runs[0].paid_reason

    def test_a_run_with_an_empty_job_list_counts_as_paid(self) -> None:
        assert freeze.decide(["batch-runner/core/grader.py"], [live("9", jobs=[])]).frozen

    def test_a_run_with_a_non_list_jobs_field_counts_as_paid(self) -> None:
        run = {"id": "9", "status": "in_progress", "jobs": "grade-dry-run"}
        assert freeze.decide(["batch-runner/core/grader.py"], [run]).frozen

    def test_a_jobs_list_of_bare_strings_counts_as_paid(self) -> None:
        """An older collector shape, or a truncated one. Either way the
        conclusions are missing, so nothing can be proved skipped."""
        run = {"id": "9", "status": "in_progress", "jobs": ["grade-dry-run"]}
        assert freeze.decide(["batch-runner/core/grader.py"], [run]).frozen

    def test_an_unrecognised_conclusion_counts_as_paid(self) -> None:
        run = live("9", jobs=[job("grade", "some-new-github-conclusion")])
        assert freeze.decide(["batch-runner/core/grader.py"], [run]).frozen

    def test_an_unrecognised_status_is_treated_as_not_live(self) -> None:
        """Deliberately the one place that is not fail-closed: GitHub's
        terminal statuses are the ones we cannot enumerate exhaustively, and
        treating every unknown string as live would freeze the repository
        permanently the first time the API adds one."""
        run = live("9", jobs=REAL_PAID_JOBS, status="neutral")
        assert not freeze.decide(["batch-runner/core/grader.py"], [run]).frozen


class TestTheMessageExplainsItself:
    def test_the_frozen_message_names_the_file_the_run_and_the_cost(self) -> None:
        text = freeze.render(freeze.decide(["batch-runner/core/grader.py"], [PAID]))
        assert text.startswith("FROZEN:")
        assert "batch-runner/core/grader.py" in text
        assert "33400000001" in text
        assert "step9_merge_shards" in text
        assert "sixty hours" in text

    def test_the_passing_message_still_warns_about_the_fingerprint(self) -> None:
        text = freeze.render(freeze.decide(["batch-runner/core/grader.py"], [DRY]))
        assert text.startswith("PASS:")
        assert "fresh smoke" in text


class TestTheCommandLine:
    @staticmethod
    def _run(tmp_path: Path, changed: object, runs: object) -> subprocess.CompletedProcess:
        changed_file = tmp_path / "changed.json"
        runs_file = tmp_path / "runs.json"
        changed_file.write_text(json.dumps(changed), encoding="utf-8")
        runs_file.write_text(json.dumps(runs), encoding="utf-8")
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--changed-paths",
                str(changed_file),
                "--runs",
                str(runs_file),
            ],
            capture_output=True,
            text=True,
        )

    def test_exit_1_when_frozen(self, tmp_path: Path) -> None:
        r = self._run(tmp_path, ["batch-runner/core/grader.py"], [PAID])
        assert r.returncode == 1
        assert "FROZEN" in r.stdout

    def test_exit_0_when_clear(self, tmp_path: Path) -> None:
        r = self._run(tmp_path, ["README.md"], [PAID])
        assert r.returncode == 0
        assert "PASS" in r.stdout

    def test_malformed_input_is_frozen_not_crashed(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        good = tmp_path / "good.json"
        good.write_text("[]", encoding="utf-8")
        r = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--changed-paths",
                str(bad),
                "--runs",
                str(good),
            ],
            capture_output=True,
            text=True,
        )
        assert r.returncode == 1
        assert "FROZEN" in r.stderr

    def test_a_json_object_instead_of_an_array_is_frozen(self, tmp_path: Path) -> None:
        r = self._run(tmp_path, {"paths": []}, [])
        assert r.returncode == 1
        assert "FROZEN" in r.stderr


class TestTheJobNamesStillExistInGradeRun:
    """The other half of the mirror. The name literals are copied out of
    grade-run.yml, and a job rename there would turn this check permanently
    green without changing a line of it.

    These assert against the *display* name, because that is the only thing
    the jobs API returns -- it never exposes the job key.
    """

    @staticmethod
    def _jobs() -> dict:
        wf = yaml.safe_load(
            (REPO_ROOT / ".github" / "workflows" / "grade-run.yml").read_text(
                encoding="utf-8"
            )
        )
        return wf["jobs"]

    def test_the_grade_job_has_no_display_name_override(self) -> None:
        """Which is the only reason matching the bare string `grade` works."""
        jobs = self._jobs()
        assert "grade" in jobs
        assert "name" not in jobs["grade"], (
            "grade now has a `name:` override, so the jobs API will stop "
            "reporting it as 'grade' and the freeze check will stop seeing "
            "paid runs. Add its prefix to PAID_JOB_NAME_PREFIXES."
        )
        assert freeze.is_paid_path_job("grade")

    def test_the_approve_job_display_name_matches_a_known_prefix(self) -> None:
        rendered = str(self._jobs()["approve-paid"]["name"])
        assert freeze.is_paid_path_job(rendered), (
            f"approve-paid renders as {rendered!r}, which none of "
            f"{freeze.PAID_JOB_NAME_PREFIXES} matches."
        )
        # And the prefix must not depend on an unexpanded ${{ }} expression,
        # since the API returns the expanded string.
        for prefix in freeze.PAID_JOB_NAME_PREFIXES:
            if rendered.startswith(prefix):
                assert "${{" not in prefix
                break

    def test_both_paid_jobs_are_gated_on_dry_run_being_false(self) -> None:
        """Not just that the names exist -- that they are the money jobs."""
        jobs = self._jobs()
        for key in ("grade", "approve-paid"):
            condition = str(jobs[key].get("if", ""))
            assert "dry_run == false" in condition, (
                f"job {key!r} is treated as paid but its `if` does not require "
                f"dry_run == false: {condition!r}"
            )
        assert "dry_run == true" in str(jobs["grade-dry-run"].get("if", ""))

    def test_no_other_job_is_gated_on_dry_run_being_false(self) -> None:
        """Catches a *new* money job being added that the predicate cannot
        see, which is the same failure as a rename with a friendlier name."""
        jobs = self._jobs()
        paid_keys = {
            key
            for key, body in jobs.items()
            if "dry_run == false" in str(body.get("if", ""))
        }
        unmatched = {
            key
            for key in paid_keys
            if not freeze.is_paid_path_job(str(jobs[key].get("name", key)))
        }
        assert not unmatched, (
            f"these grade-run.yml jobs only run when dry_run is false, but the "
            f"freeze check would not recognise them: {sorted(unmatched)}"
        )

    def test_the_recorded_real_job_names_are_not_stale(self) -> None:
        """The fixture copied off run 33381143279 has to stay a plausible
        rendering of the current workflow, or the tests using it prove
        nothing about today's grade-run.yml."""
        template = str(self._jobs()["approve-paid"]["name"])
        literal_prefix = template.split("${{")[0].strip()
        assert literal_prefix
        assert APPROVE_PAID_DISPLAY_NAME.startswith(literal_prefix)


class TestTheWorkflowTriggersOnEverythingItJudges:
    """A predicate that classifies a path as hash-moving is useless if the
    workflow's own `paths:` filter never fires for it. Both mirrors have to
    move together, so this test drives the real hash function and requires
    every file it reads to match the trigger."""

    @staticmethod
    def _trigger_globs() -> list[str]:
        wf = yaml.safe_load(
            (REPO_ROOT / ".github" / "workflows" / "grader-hash-freeze.yml").read_text(
                encoding="utf-8"
            )
        )
        # PyYAML resolves the bare key `on` to the boolean True.
        triggers = wf.get("on", wf.get(True))
        return list(triggers["pull_request"]["paths"])

    @staticmethod
    def _matches(globs: list[str], path: str) -> bool:
        from fnmatch import fnmatch

        for pattern in globs:
            if pattern.endswith("/**"):
                if path.startswith(pattern[:-2]):
                    return True
            elif fnmatch(path, pattern):
                return True
        return False

    @pytest.mark.parametrize(
        "config_name",
        sorted(p.name for p in (BATCH_ROOT / "grading_configs").glob("*.yaml")),
    )
    def test_every_hashed_input_matches_the_paths_filter(
        self, monkeypatch, config_name: str
    ) -> None:
        hashed = TestThePredicateStillCoversWhatIsActuallyHashed._paths_read_by_the_hash(
            monkeypatch, BATCH_ROOT / "grading_configs" / config_name
        )
        globs = self._trigger_globs()
        missed = [p for p in hashed if not self._matches(globs, p)]
        assert not missed, (
            "these files move the grader source hash but would not trigger the "
            "freeze workflow at all:\n  "
            + "\n  ".join(missed)
            + "\n\nAdd them to `on.pull_request.paths` in "
            ".github/workflows/grader-hash-freeze.yml."
        )

    def test_the_workflow_watches_its_own_two_files(self) -> None:
        globs = self._trigger_globs()
        assert self._matches(
            globs, "batch-runner/scripts/check_grader_hash_freeze.py"
        )
        assert self._matches(globs, ".github/workflows/grader-hash-freeze.yml")


class TestTheWorkflowIsItselfHashNeutral:

    def test_the_workflow_file_exists_and_is_outside_batch_runner(self) -> None:
        wf = REPO_ROOT / ".github" / "workflows" / "grader-hash-freeze.yml"
        assert wf.is_file()
        assert not freeze.is_grader_source_path(
            wf.relative_to(REPO_ROOT).as_posix()
        )

    def test_the_workflow_calls_the_checked_in_script(self) -> None:
        wf = REPO_ROOT / ".github" / "workflows" / "grader-hash-freeze.yml"
        body = wf.read_text(encoding="utf-8")
        assert "batch-runner/scripts/check_grader_hash_freeze.py" in body

    def test_adding_this_guard_does_not_move_any_config_hash(self, monkeypatch) -> None:
        """Belt and braces: run the real hash function and confirm neither new
        file is among the bytes it reads."""
        config_path = BATCH_ROOT / "grading_configs" / "gold_ceiling_185_v2_sol_max.yaml"
        hashed = TestThePredicateStillCoversWhatIsActuallyHashed._paths_read_by_the_hash(
            monkeypatch, config_path
        )
        assert "batch-runner/scripts/check_grader_hash_freeze.py" not in hashed
        assert "batch-runner/tests/test_grader_hash_freeze.py" not in hashed
        assert ".github/workflows/grader-hash-freeze.yml" not in hashed
