"""The entry point that spends stage one's money, exercised without spending it.

This is the only route by which an Agentic Sandbox V2 stage can run, so the
parts that decide whether it is *allowed* to run are worth more here than the
run itself. Four of them:

* **the pricing guard.** The plan's two approved amounts are whole-run figures
  worked out over the five tasks the plan pins. Nothing about them is per-task,
  so a thirty- or two-hundred-and-twenty-task cohort run under them would go out
  against an approval for a run forty-four times smaller — and the line printed
  beside it would say it was within budget, because the arithmetic it came from
  never saw the larger cohort. Refused instead, and the refusal says by how much.
* **the free path really being free.** ``--dry-run`` is the whole path minus the
  network. It is only worth anything if it genuinely cannot reach out, which is
  proved here by running it with no Azure environment at all rather than by
  asserting it.
* **the answer columns never being read.** The pinned parquet carries the
  expert's own deliverable next to the prompt. The binding is handed rows built
  by hand for that reason, and this holds the column list to it.
* **what the record admits.** A run whose isolation was a fixture and whose
  record does not say so is a result that will eventually be quoted as something
  it was not.

Nothing here calls a model, builds a client or spends anything.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

BATCH_RUNNER_ROOT = Path(__file__).resolve().parents[1]
if str(BATCH_RUNNER_ROOT) not in sys.path:
    sys.path.insert(0, str(BATCH_RUNNER_ROOT))

RUNNER_PATH = BATCH_RUNNER_ROOT / "scripts" / "run_agentic_v2_stage.py"


def _load_runner():
    """Import the script by path, the way a script without a package is loaded.

    Registered in ``sys.modules`` before it is executed, which the stage A
    probe's loader does not need to do. ``DatasetRow`` is a dataclass, and
    ``dataclasses`` resolves a field's type by looking the defining module up in
    ``sys.modules`` — from a module that is not there yet, that lookup returns
    ``None`` and the decorator fails at import.
    """
    spec = importlib.util.spec_from_file_location("run_agentic_v2_stage", RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


runner = _load_runner()

#: The dataset is fetched by the workflow and cached on a developer's machine,
#: but it is not in the repository. Skipped rather than failed when it is
#: absent: a missing download is not a broken runner, and a test that reported
#: one as the other would be noise in front of the real signal.
HAVE_DATASET = runner.PINNED_DATASET_PARQUET.is_file()
needs_dataset = pytest.mark.skipif(
    not HAVE_DATASET,
    reason=f"the pinned dataset is not at {runner.PINNED_DATASET_PARQUET}",
)

#: A directory the runner will agree to stage from.
#:
#: Made once for the module and left for the OS to clear, because it holds one
#: five-byte file and exists to satisfy a single check: that the root is a tree
#: of real files rather than a cache of symlinks. It deliberately does *not*
#: hold the dataset's reference files — the tests that use it are testing
#: pricing and sharding, and a dry run copies nothing.
STAGEABLE_ROOT = Path(tempfile.mkdtemp(prefix="stageable-root-"))
(STAGEABLE_ROOT / "reference_files" / "placeholder").mkdir(parents=True)
(STAGEABLE_ROOT / "reference_files" / "placeholder" / "a.txt").write_text("real")


# ── The pricing guard ─────────────────────────────────────────────────────
#
# The guard used to live here as arithmetic over two counts, and these tests
# pinned that arithmetic. It now prices the cohort that is really about to run
# against the amount the plan approved for that stage by name, which is a
# stronger check in both directions: it lets a correctly priced larger stage
# through, and it would catch a cohort of the approved size whose tasks had
# grown more expensive. The arithmetic moved to
# ``core.agentic_v2_stage_one_budget.price_one_stage`` and is tested there,
# against synthetic plans that need no dataset. What is left here is the thing
# only this script can be asked: that the guard is wired into the path a real
# run takes, with a real bound cohort and a real catalogue.


@needs_dataset
@pytest.mark.parametrize("stage", ["advance_check_5", "trial_30", "full_220"])
def test_every_registered_stage_is_priced_and_dry_runs_to_zero(stage):
    """All three, because an escalation with an unpriced rung cannot be climbed.

    This test used to assert the opposite for two of the three — that the thirty
    and the two hundred and twenty were *refused* as unpriced. They were, and
    the refusal was correct while it was true. Approving them is what changed,
    not the guard.
    """
    finished = _run("--stage", stage, "--dry-run")

    assert finished.returncode == 0, finished.stdout + finished.stderr
    assert "Every condition this job can reach is met" in finished.stdout
    assert "nothing was spent" in finished.stdout


@needs_dataset
def test_a_stage_the_plan_does_not_name_is_still_refused(tmp_path):
    """The guard is a guard, not a formality that happens to pass now.

    Checked by taking the entry away rather than by trusting that it would be
    caught if it were missing. A plan with the block deleted is the state the
    repository was in this morning.
    """
    plan = yaml.safe_load(runner.STAGE_ONE_PLAN_PATH.read_text(encoding="utf-8"))
    del plan["stages"]["full_220"]
    narrowed = tmp_path / "plan.yaml"
    narrowed.write_text(yaml.safe_dump(plan), encoding="utf-8")

    finished = _run("--stage", "full_220", "--plan", str(narrowed), "--dry-run")

    assert finished.returncode == 1, finished.stdout + finished.stderr
    assert "this stage is not priced" in finished.stdout
    assert "'full_220'" in finished.stdout
    assert "whole-run figure" in finished.stdout


@needs_dataset
def test_a_stage_priced_too_low_is_refused_with_the_shortfall(tmp_path):
    """The number is the point. "Not priced" invites someone to wave it through.

    A shortfall in dollars is a different conversation from a mismatch, and the
    person reading the refusal is the person who would have had it.
    """
    plan = yaml.safe_load(runner.STAGE_ONE_PLAN_PATH.read_text(encoding="utf-8"))
    plan["stages"]["full_220"]["running_approved_maximum_usd"] = 50.00
    narrowed = tmp_path / "plan.yaml"
    narrowed.write_text(yaml.safe_dump(plan), encoding="utf-8")

    finished = _run("--stage", "full_220", "--plan", str(narrowed), "--dry-run")

    assert finished.returncode == 1, finished.stdout + finished.stderr
    assert "short by $" in finished.stdout
    assert "nothing here may scale an approved amount on its own" in finished.stdout


# ── The free path is free ─────────────────────────────────────────────────


def _run(*args, env=None):
    """Run the entry point as a subprocess, with no Azure environment at all.

    ``--dataset-root`` is supplied unless the caller names one, because the
    runner now refuses a stage whose reference files cannot be staged and the
    tests below are about pricing, sharding and the dry run being free. The
    stand-in is a directory of real files, which is the one property the
    refusal checks; :func:`test_a_dry_run_refuses_a_snapshot_it_cannot_stage_from`
    covers the other side, and covers it against the shape a real fetch
    actually produces.
    """
    clean = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("AZURE_", "FOUNDRY_", "OPENAI_"))
    }
    clean["PYTHONPATH"] = str(BATCH_RUNNER_ROOT)
    clean.update(env or {})
    if "--dataset-root" not in args:
        args = (*args, "--dataset-root", str(STAGEABLE_ROOT))
    return subprocess.run(
        [sys.executable, str(RUNNER_PATH), *args],
        cwd=BATCH_RUNNER_ROOT,
        env=clean,
        capture_output=True,
        text=True,
        timeout=600,
    )


@needs_dataset
def test_the_priced_stage_dry_runs_to_zero_without_any_azure_environment():
    """The whole path minus the network, with nothing configured to reach it.

    The assertion below used to read "Every condition for the paid run is met",
    which is what the script printed and what this test therefore pinned. On
    2026-09-11 a paid run that had just been told exactly that crashed on a
    constructor keyword in a branch no dry run executes. The sentence was never
    checkable from here: this job holds no Azure identity, so the route, the
    deployment and the conversation are out of its reach by design.

    What it can reach it now reaches, so the narrower claim is worth more than
    the broad one was. It reached further again on 2026-09-11, after the next
    paid run died one line past the ledger -- handing the report a binding
    where a receipt was wanted -- so the rehearsal, and this assertion, now run
    a fabricated task all the way to a report row.
    """
    finished = _run("--stage", "advance_check_5", "--dry-run")

    assert finished.returncode == 0, finished.stdout + finished.stderr
    assert "Every condition this job can reach is met" in finished.stdout
    assert "ledger, binding, receipt, metrics, report row" in finished.stdout
    assert "It cannot reach the model" in finished.stdout
    assert "nothing was spent" in finished.stdout


@needs_dataset
def test_the_dry_run_reports_both_amounts_against_their_own_ceilings():
    """Running and marking are two purchases and print as two lines.

    While they shared one approved figure, the settings that were actually being
    chosen moved less than one percent of it. Two lines is what makes the choice
    visible to whoever signs for it.
    """
    printed = _run("--stage", "advance_check_5", "--dry-run").stdout

    running = next(line for line in printed.splitlines() if "running" in line)
    marking = next(line for line in printed.splitlines() if "marking" in line)

    assert "against $50.00 approved" in running
    assert "$2600.00 approved" in marking
    assert "not spent by this script" in marking


@needs_dataset
def test_a_stage_whose_marking_is_not_approved_prints_the_reason():
    """A blank is read as an oversight; a refusal with a reason is read as one.

    Running the two hundred and twenty is approved and marking them is not, and
    those are different facts about the same run. The dry run has to make the
    second one as visible as the first, or the milestone that has not been paid
    for is the one nobody notices is missing.
    """
    printed = _run("--stage", "full_220", "--dry-run").stdout

    assert "marking        not approved for this stage" in printed
    assert "six-figure amount" in printed
    assert "another" in printed  # running them is one milestone, marking another


@needs_dataset
def test_the_stage_figure_is_the_stage_s_own_and_not_the_five_task_one():
    """The two are the same number only for the smallest stage.

    Printing the five-task figure beside a two-hundred-task run is exactly how a
    stage gets described as affordable by a line that was never about it.
    """
    printed = _run("--stage", "full_220", "--dry-run").stdout
    running = next(line for line in printed.splitlines() if "running" in line)

    assert "$18.47" not in running
    assert "$884.62" in running
    assert "against $1400.00 approved for the whole stage" in running


# ── Shards ────────────────────────────────────────────────────────────────


@needs_dataset
def test_a_shard_runs_part_of_the_stage_and_says_so():
    printed = _run("--stage", "full_220", "--shard", "3/17", "--dry-run").stdout

    assert "tasks          220" in printed
    assert "shard          3 of 17" in printed
    assert "the stage has not run until every shard has" in printed


@needs_dataset
def test_a_shard_is_priced_against_the_whole_stage_and_not_against_itself():
    """Seventeen runs that are each "within budget" must not spend seventeen
    times the approval. A shard is where the work happens, not what was bought.
    """
    whole = _run("--stage", "full_220", "--dry-run").stdout
    piece = _run("--stage", "full_220", "--shard", "3/17", "--dry-run").stdout

    line_of = lambda text: next(
        one for one in text.splitlines() if "running        at most" in one
    )
    assert line_of(whole) == line_of(piece)


@needs_dataset
def test_a_shard_that_does_not_exist_is_refused_rather_than_run_empty():
    finished = _run("--stage", "full_220", "--shard", "25/17", "--dry-run")

    assert finished.returncode == 1, finished.stdout
    assert "does not exist; shards are numbered 1 to 17" in finished.stdout


@needs_dataset
def test_one_shard_of_one_is_the_unsharded_run():
    """So that a workflow may always pass --shard without changing behaviour."""
    plain = _run("--stage", "trial_30", "--dry-run").stdout
    trivial = _run("--stage", "trial_30", "--shard", "1/1", "--dry-run").stdout

    assert plain == trivial
    assert "shard" not in trivial



@needs_dataset
def test_the_dry_run_says_what_is_missing_rather_than_only_what_is_ready():
    """What is still not real is printed on the way in, not found in the results.

    This test used to pin the sentence "reference files that are not in the
    workspace", and it was right to: nothing copied them and the run had to say
    so. Staging them made that sentence false, and a test asserting a false
    sentence is worse than no test — it holds the claim in place after the fact
    it described has gone.

    So it now pins what is *still* missing. The isolation is the fixture
    backend and ``exec_run`` is shut, which is the thing most likely to be
    forgotten when a result gets quoted later.
    """
    printed = _run("--stage", "advance_check_5", "--dry-run").stdout

    assert "isolation      none — fixture backend, exec_run shut" in printed
    assert "reference files that are not in the workspace" not in printed


# ── The expert's answer never travels ─────────────────────────────────────


def test_only_the_five_columns_the_binding_may_see_are_read(monkeypatch, tmp_path):
    """The parquet holds the answer next to the question.

    ``deliverable_text`` and ``deliverable_files`` are the expert's own work. A
    run that read them into the same structure the prompt travels in would be
    one refactor away from showing the model the answer.
    """
    asked: dict = {}

    # Grabbed before the stand-in goes into sys.modules. Reaching for it from
    # inside the stand-in would resolve to the stand-in itself.
    import pandas as real_pandas

    class FakePandas:
        @staticmethod
        def read_parquet(path, columns=None):
            asked["columns"] = columns
            return real_pandas.DataFrame({name: [] for name in (columns or [])})

    parquet = tmp_path / "pinned.parquet"
    parquet.write_bytes(b"not read, only existence is checked")
    monkeypatch.setitem(sys.modules, "pandas", FakePandas)

    runner.read_pinned_dataset(parquet)

    assert asked["columns"] == [
        "task_id",
        "prompt",
        "sector",
        "occupation",
        "reference_files",
    ]
    assert "deliverable_text" not in asked["columns"]
    assert "deliverable_files" not in asked["columns"]


def test_a_missing_dataset_names_the_revision_to_fetch():
    with pytest.raises(runner.StageRefused) as refused:
        runner.read_pinned_dataset(Path("/nonexistent/pinned.parquet"))

    assert "11e7900cdcac61bc4daf59e65feb238acda98fbf" in str(refused.value)
    assert "openai/gdpval" in str(refused.value)


# ── Ceilings are read, never defaulted ────────────────────────────────────


class _Chosen:
    tool_calls_per_attempt = 8
    max_output_tokens_per_turn = 8192


def test_every_ceiling_comes_from_something_somebody_wrote_down():
    ceilings = runner.ceilings_from(
        {"fixed_settings": {"per_task_timeout_seconds": 1200}}, _Chosen()
    )

    assert ceilings.max_model_calls == 9
    assert ceilings.max_model_turns == 9
    assert ceilings.max_written_tokens_per_turn == 8192
    assert ceilings.max_seconds == 1200.0
    assert ceilings.max_output_tokens == 8192 * 9
    # Quadratic, because the loop re-sends the whole conversation every turn.
    # Priced that way, so bounded that way.
    assert ceilings.max_input_tokens == 8192 * 9 * 10


def test_a_plan_with_no_timeout_fails_rather_than_running_without_one():
    """A ceiling nobody set is not a ceiling. Better to stop than to invent 30s."""
    with pytest.raises(KeyError):
        runner.ceilings_from({"fixed_settings": {}}, _Chosen())


# ── What the record admits ────────────────────────────────────────────────


def test_the_record_says_the_isolation_was_not_exercised():
    note = runner.environment_note({"policy_profile_id": "offline-full-v1"})

    assert note["guest_booted"] is False
    assert note["exec_run_open"] is False
    assert "no guest booted" in " ".join(note["what_was_not_real"])
    assert "capability_unavailable" in " ".join(note["what_was_not_real"])


def test_the_record_carries_the_weaker_true_sentence_ready_to_be_quoted():
    """Written out in full, because a reader will quote one sentence and stop.

    If the only honest summary lives in a docstring, the sentence that travels
    is the flattering one somebody writes later from the numbers.
    """
    sentence = runner.environment_note({})["so_the_honest_sentence_is"]

    assert "real model drove a real tool loop" in sentence
    assert "its isolation not exercised" in sentence
    assert "not evidence that the sandbox contains anything" in sentence


def test_what_was_real_does_not_quietly_include_the_isolation():
    real = " ".join(runner.environment_note({})["what_was_real"])

    assert "isolation" not in real
    assert "exec_run" not in real
    assert "the charge for every call" in real


# ── The files a task is told to open ──────────────────────────────────────
#
# 125 of the 220 tasks name reference files. Until this window nothing copied
# them anywhere, so a task that needed one failed on its merits and the failure
# was indistinguishable from the model being unable to do the work. The runner
# now stages them, and the two tests below are about the moment before that:
# whether it can tell a directory it can stage from from one it cannot, and
# whether it says so before any money is spent rather than 261 times during the
# run.


@needs_dataset
def test_a_dry_run_refuses_a_snapshot_it_cannot_stage_from(tmp_path):
    """The shape a plain `hf download` really produces, and the real cost of it.

    A huggingface_hub cache is names, not bytes: every file under the snapshot
    is a symlink into a sibling ``blobs/`` directory outside it. Measured on
    this repository's own pinned revision, that is 301 of 301 reference files.
    Nothing that opens with ``O_NOFOLLOW`` will read one, so staging from such a
    root delivers nothing at all — and a paid stage run against it produces 125
    tasks that failed holding an empty workspace, which reads afterwards as a
    model that could not do the work.

    Refusing in the *dry* run is the point. That is the free path, so this
    particular mistake costs nothing to find.
    """
    link_farm = tmp_path / "cache-shaped"
    blobs = tmp_path / "blobs"
    blobs.mkdir()
    (blobs / "deadbeef").write_text("the bytes live here, outside the root")
    folder = link_farm / "reference_files" / "abc123"
    folder.mkdir(parents=True)
    (folder / "sheet.xlsx").symlink_to(os.path.relpath(blobs / "deadbeef", folder))

    finished = _run(
        "--stage", "advance_check_5", "--dry-run",
        "--dataset-root", str(link_farm),
    )

    assert finished.returncode == 1
    assert "Refused before spending anything" in finished.stdout
    assert "--local-dir" in finished.stdout
    # Named, so that the fix is the next thing the reader does rather than
    # something they work out from a generic "source is a link".
    assert "huggingface_hub cache" in finished.stdout
    assert "read as the model's" in finished.stdout


@needs_dataset
def test_a_stage_naming_no_reference_files_is_not_blocked_by_the_root(tmp_path):
    """A directory a cohort never opens must not be able to stop it.

    The refusal above is worth having because it is cheap and specific. It
    would stop being worth having if it also refused runs that were never going
    to read a file — a gate that fires on tasks it does not apply to teaches
    people to route around it.
    """
    empty_root = tmp_path / "nothing-here"
    empty_root.mkdir()

    printed = _run(
        "--stage", "advance_check_5", "--dry-run",
        "--dataset-root", str(empty_root),
    )

    # advance_check_5 does name files, so this one *is* refused -- and the
    # assertion worth making is that the refusal names the root rather than
    # failing somewhere further in.
    assert "the reference files cannot be staged from" in printed.stdout
    assert str(empty_root) in printed.stdout


@needs_dataset
def test_the_dry_run_says_where_the_files_would_come_from(tmp_path):
    """The printed line names the root, because the wrong root is the likely bug.

    It used to print a count of tasks whose files "are not in the workspace",
    which was true when nothing staged them and became false the moment
    something did. A line that states a fact outlives the fact; this one states
    where the bytes come from, which is checkable against the run.
    """
    printed = _run("--stage", "advance_check_5", "--dry-run").stdout

    assert "tasks name reference files, staged from" in printed
    assert str(STAGEABLE_ROOT) in printed
    assert "handicap" not in printed


# ── The workflow and the runner have to agree about the dataset ───────────

STAGE_WORKFLOW = (
    BATCH_RUNNER_ROOT.parent / ".github" / "workflows" / "agentic-v2-stage-run.yml"
)


def _jobs() -> dict:
    return yaml.safe_load(STAGE_WORKFLOW.read_text(encoding="utf-8"))["jobs"]


def _shell_blocks(job: dict) -> list[str]:
    return [str(step["run"]) for step in job["steps"] if "run" in step]


def _flag_value(script: str, flag: str) -> str | None:
    """What a `--flag value` in a shell block was given, quotes stripped."""
    found = re.search(rf"{re.escape(flag)}\s+[\"']?([^\"'\s\\]+)", script)
    return found.group(1) if found else None


#: A block that *runs* the stage, not one that merely says its name. The
#: difference matters as soon as a job runs the stage's own test file: the
#: earlier version of this matched on the bare filename, and adding
#: `tests/test_run_agentic_v2_stage.py` to the free job's pytest step made it
#: see a step that invoked the stage with no `--parquet`. The test failed
#: correctly, about the wrong step.
INVOKES_THE_STAGE = re.compile(r"python\s+scripts/run_agentic_v2_stage\.py")


def _stage_invocations(blocks: list[str]) -> list[str]:
    return [one for one in blocks if INVOKES_THE_STAGE.search(one)]


def test_every_job_that_runs_the_stage_fetches_a_dataset_it_can_stage_from():
    """The gate is in the runner; the only thing that can defeat it is here.

    ``run_agentic_v2_stage.py`` refuses a ``huggingface_hub`` cache, and that
    refusal is worth having only while the workflow feeding it does not hand it
    one. Nothing but this test connects them. A `hf download` line edited back
    to its default passes every other check in the repository, and then refuses
    a paid cohort on the runner -- after the job has queued, checked out,
    authenticated and been counted as an attempt.
    """
    checked = 0
    for name, job in _jobs().items():
        blocks = _shell_blocks(job)
        if not _stage_invocations(blocks):
            continue
        checked += 1

        fetches = [one for one in blocks if "hf download" in one]
        assert fetches, f"job {name!r} runs the stage but never fetches the dataset"
        for fetch in fetches:
            assert "--local-dir" in fetch, (
                f"job {name!r} fetches into the default cache, which is a tree "
                "of symlinks into a blob store outside it. Every reference file "
                "would be refused and every task would run without its inputs."
            )

    assert checked == 2, "expected the free job and the paid job to both run it"


def test_the_stage_is_pointed_at_the_directory_the_workflow_fetched():
    """Two places naming a path is two places for it to differ.

    Fetching correctly and then reading somewhere else is the same outcome as
    not fetching at all, and it is harder to see: the download step is green.
    """
    for name, job in _jobs().items():
        blocks = _shell_blocks(job)
        runs = _stage_invocations(blocks)
        if not runs:
            continue

        fetched_into = {
            _flag_value(one, "--local-dir") for one in blocks if "hf download" in one
        }
        assert len(fetched_into) == 1, f"job {name!r} fetches to more than one place"
        into = fetched_into.pop()

        for one in runs:
            parquet = _flag_value(one, "--parquet")
            assert parquet is not None, (
                f"job {name!r} runs the stage without saying which parquet, so "
                "it falls back to the cache path the fetch no longer fills"
            )
            assert parquet.startswith(f"{into}/"), (
                f"job {name!r} fetches into {into} and reads {parquet}"
            )


def test_the_reference_answers_are_not_fetched_onto_the_machine_that_runs():
    """595 MB of expert deliverables, beside a workspace, for no reason.

    They are the answers. No inference step opens one, and the only way they
    can affect a result is by being on the disk at all. Excluded at the fetch
    rather than ignored afterwards, because "nothing reads them" is a claim
    about every future version of the runner, and "they were never downloaded"
    is a claim about this job.
    """
    for name, job in _jobs().items():
        for fetch in (one for one in _shell_blocks(job) if "hf download" in one):
            assert "deliverable_files" in fetch and "--exclude" in fetch, (
                f"job {name!r} fetches the reference answers onto the runner"
            )


# ── The rehearsal ─────────────────────────────────────────────────────────
#
# ``--rehearse`` walks the entire production path -- real dataset rows, real
# staging, real backend, real trace verification, real deliverable collection
# -- with a scripted stand-in where the model goes. It exists because every
# defect found in that path so far was found after a task had been worked, and
# on the paid path that means after it had been charged for. Three of them
# would have looked like the model failing.


@needs_dataset
def test_a_rehearsal_works_every_task_without_any_azure_environment(tmp_path):
    """The five tasks, end to end, with nothing configured to reach a model.

    This is the check that would have caught all three: the missing guide that
    killed a task on turn one, the state digest that threw away a finished
    task, and the display that printed "failed" beside five tasks that had all
    succeeded.
    """
    into = tmp_path / "rehearsal"

    finished = _run(
        "--stage", "advance_check_5", "--rehearse", "--into", str(into)
    )

    assert finished.returncode == 0, finished.stdout + finished.stderr
    assert "finished       5 of 5" in finished.stdout
    assert "guide readable 5 of 5" in finished.stdout
    assert "wrote a file   5 of 5" in finished.stdout
    assert finished.stdout.count("  ok\n") == 5


@needs_dataset
def test_a_rehearsal_says_it_is_not_a_run_and_spent_nothing(tmp_path):
    """Both on the screen and in the file, and neither says $0.00.

    A record that reports a rehearsal as a zero-cost run is worse than one that
    reports nothing, because the zero is a number and will be averaged with
    real ones.
    """
    into = tmp_path / "rehearsal"

    finished = _run(
        "--stage", "advance_check_5", "--rehearse", "--into", str(into)
    )
    record = json.loads((into / "rehearsal_record.json").read_text("utf-8"))

    assert "Nothing here is a result" in finished.stdout
    assert "spent          nothing — no model was asked" in finished.stdout
    assert record["rehearsal"]["tasks_worked"] == 5
    # In the slot a real run's route fingerprint occupies, so anything reading
    # the record to find out which model answered gets the refusal rather than
    # a plausible-looking route.
    assert "no call was made" in record["route_fingerprint"]["cost"]
    assert "$0" not in finished.stdout.split("spent")[-1]


@needs_dataset
def test_a_rehearsal_collects_a_deliverable_for_every_task_onto_disk(tmp_path):
    """The backend purges its workspace on close, so the record is not enough.

    Every rehearsal before deliverable collection worked left five empty
    directories behind and a record that said files had been written. Both were
    true, and the files were gone.
    """
    into = tmp_path / "rehearsal"

    _run("--stage", "advance_check_5", "--rehearse", "--into", str(into))

    collected = sorted((into / "deliverables").rglob("*.md"))
    assert len(collected) == 5
    for one in collected:
        assert "must not be scored as one" in one.read_text("utf-8")


# ── Which model answered ──────────────────────────────────────────────────
#
# A deployment is an alias. What answers behind it carries its own name, the
# voice reads that name out of every reply, and the run used to drop it along
# with the voice at the end of each task. The receipt was then priced against
# the alias, which is the right amount only if the two strings agree -- and
# nothing kept was capable of showing whether they did.


class _Spoke:
    """A voice that has finished speaking, with only what the record reads.

    The method names are the real voice's, and
    :func:`test_the_stand_in_has_the_same_shape_as_the_voice_it_stands_in_for`
    is what holds them to it. The first draft of this class invented
    ``ledger_rows``; every test here passed, and the real
    :class:`~core.agentic_v2_model_voice.AzureFoundryVoice` has ``ledger``.
    The record would have raised ``AttributeError`` while being assembled --
    on the first paid run, after the money was spent, in the one place that
    writes down what it was spent on.
    """

    def __init__(self, resolved_model, rows, spent):
        self.resolved_model = resolved_model
        self._rows = rows
        self._spent = spent

    def ledger(self):
        return [dict(row) for row in self._rows]

    def spent_usd(self):
        return self._spent


def _call(*, price="0.40", model="gpt-5.4"):
    return {
        "turn": 1,
        "requested_deployment": "gpt-5.4",
        "resolved_model": model,
        "input_tokens": 1000,
        "output_tokens": 200,
        "history_entries_sent": 0,
        "price_usd": price,
        "price_missing": price is None,
    }


def test_the_stand_in_has_the_same_shape_as_the_voice_it_stands_in_for():
    """A stub shaped to the code proves the code agrees with the stub.

    Every test below builds ``_Spoke`` rather than a real voice, because
    reaching a real one needs a paid call. That trade is only safe while the
    two have the same surface, and nothing else in this file checks it: the
    stub is written by the same hand as the code it stands in for, so a
    misremembered method name is invisible from both sides.

    Checked against the real class rather than an instance, which needs no
    client, no budget and no network.
    """
    from core.agentic_v2_model_voice import AzureFoundryVoice

    for name in ("ledger", "spent_usd"):
        assert callable(getattr(AzureFoundryVoice, name, None)), (
            f"the record calls {name}() on a voice and the real voice has no "
            "such method"
        )
    assert "resolved_model" in AzureFoundryVoice.__dataclass_fields__

    invented = set(vars(_Spoke)) - {"__init__", "__module__", "__qualname__"}
    invented -= {"__doc__", "__dict__", "__weakref__"}
    for name in invented:
        assert hasattr(AzureFoundryVoice, name), (
            f"_Spoke exposes {name}(), which the real voice does not -- so a "
            "test using it is testing something that cannot happen"
        )


def test_the_record_names_the_model_that_answered_and_not_the_one_asked_for():
    """The whole point. The alias is already in chosen_settings."""
    written = runner.model_calls_record(
        {
            ("task-1", 1): _Spoke(
                "gpt-5.4-2026-08-01", [_call(model="gpt-5.4-2026-08-01")], None
            )
        },
        pinned_model="gpt-5.4",
    )

    assert written["models_that_answered"] == ["gpt-5.4-2026-08-01"]
    assert written["per_attempt"][0]["resolved_model"] == "gpt-5.4-2026-08-01"


def test_one_run_answered_by_two_models_is_visible_rather_than_averaged():
    """Recorded per attempt, because a single field could not show this.

    The voice refuses a run whose replies change model mid-conversation, but
    that guard is per voice and there is one voice per task. Two tasks in the
    same stage answered by different models would pass every check inside the
    conversation and still be two experiments reported as one.
    """
    written = runner.model_calls_record(
        {
            ("task-1", 1): _Spoke("gpt-5.4-2026-08-01", [_call()], None),
            ("task-2", 1): _Spoke("gpt-5.4-2026-09-01", [_call()], None),
        },
        pinned_model="gpt-5.4",
    )

    assert written["models_that_answered"] == [
        "gpt-5.4-2026-08-01",
        "gpt-5.4-2026-09-01",
    ]
    assert len(written["per_attempt"]) == 2


def test_an_attempt_with_an_unpriced_call_totals_nothing_rather_than_zero():
    """Missing is partial. A zero would be averaged with real amounts."""
    written = runner.model_calls_record(
        {("task-1", 1): _Spoke("something-new", [_call(price=None)], None)},
        pinned_model="gpt-5.4",
    )

    assert written["per_attempt"][0]["spent_usd"] is None
    assert written["calls_with_no_price"] == 1
    assert "is not zero" in written["what_no_price_means"]


def test_the_calls_that_could_not_be_priced_are_counted_not_left_to_be_noticed():
    """Across every attempt, so one bad call in 220 tasks is not buried."""
    written = runner.model_calls_record(
        {
            ("task-1", 1): _Spoke("m", [_call(), _call(price=None)], None),
            ("task-2", 1): _Spoke("m", [_call()], Decimal("0.40")),
        },
        pinned_model="gpt-5.4",
    )

    assert written["calls_with_no_price"] == 1
    assert written["per_attempt"][1]["spent_usd"] == "0.40"


def test_an_attempt_no_voice_spoke_for_is_left_out_rather_than_priced_at_zero():
    """A refused attempt made no call. An empty row would read as a free one."""
    written = runner.model_calls_record(
        {("task-1", 1): None}, pinned_model="gpt-5.4"
    )

    assert written["per_attempt"] == []
    assert written["models_that_answered"] == []


def test_it_keeps_no_prompt_and_no_reply():
    """Same rule as the rest of the script: names, counts and amounts only."""
    written = runner.model_calls_record(
        {("task-1", 1): _Spoke("gpt-5.4", [_call()], Decimal("0.40"))},
        pinned_model="gpt-5.4",
    )

    allowed = {
        "turn",
        "requested_deployment",
        "resolved_model",
        "input_tokens",
        "output_tokens",
        "history_entries_sent",
        "price_usd",
        "price_missing",
    }
    for row in written["per_attempt"][0]["calls"]:
        assert set(row) <= allowed, f"unexpected field: {set(row) - allowed}"


def test_the_receipt_is_settled_against_what_the_reply_named():
    """Read from the source, because reaching this needs a paid call.

    Checked as text rather than behaviour on purpose, and narrowly: the
    binding used to pass a literal ``resolved_model=None`` beside a deployment
    it had every reason to believe was the answer. The ledger then filled its
    own column from the alias and the receipt read as complete.
    """
    source = RUNNER_PATH.read_text("utf-8")
    binding = source.split("def receipt_for(")[1].split("def ")[0]

    assert "resolved_model=None" not in binding
    assert "spoke.resolved_model" in binding


def test_the_voice_that_spoke_for_an_attempt_is_still_reachable_afterwards():
    """The voices are kept. Dropping them is what lost the name."""
    source = RUNNER_PATH.read_text("utf-8")

    assert "voices_by_budget[id(budget)] = voice" in source
    assert "def voice_of(" in source


@needs_dataset
def test_a_rehearsal_names_no_model_because_none_answered(tmp_path):
    """The section is present and empty, rather than absent.

    Absent would have to be read as "not recorded"; empty says no model was
    asked, which is the true state of a rehearsal and the one thing it must
    never be mistaken for.
    """
    into = tmp_path / "rehearsal"

    _run("--stage", "advance_check_5", "--rehearse", "--into", str(into))
    record = json.loads((into / "rehearsal_record.json").read_text("utf-8"))

    assert record["model_calls"]["models_that_answered"] == []
    assert record["model_calls"]["per_attempt"] == []
    assert record["model_calls"]["calls_with_no_price"] == 0
    assert record["model_calls"]["answered_by_something_else"] == []
    assert record["model_calls"]["attempts_that_reported_no_model"] == 0
    # Present even here, so a reader of an empty section knows what the
    # comparison would have been against rather than having to infer that
    # there was one.
    assert record["model_calls"]["pinned_model"] == "gpt-5.4"


# ── The plan's first stop condition ───────────────────────────────────────
#
# "Stop at once if the model name or deployment name reported back differs
# from the one fixed above."
#
# Written into the plan and implemented nowhere. The plan's `resolved_model`
# was read in two places -- copied into the pre-registration record, and used
# to price the estimate -- and compared against a reply in neither. Because
# the estimate is priced from the same pinned name, an entirely different
# model answering every call would have produced an estimate and a receipt
# that agreed exactly: two numbers matching, neither touching the fact.


def _voices(*names):
    return [_Spoke(name, [_call()], Decimal("0.40")) for name in names]


def test_the_pinned_model_answering_is_not_a_mismatch():
    assert (
        runner.answered_by_something_else(
            _voices("gpt-5.4"), pinned_model="gpt-5.4"
        )
        == ()
    )


def test_a_different_name_coming_back_is_the_mismatch():
    assert runner.answered_by_something_else(
        _voices("gpt-5.4", "gpt-5.4-turbo"), pinned_model="gpt-5.4"
    ) == ("gpt-5.4-turbo",)


def test_a_reply_that_named_nothing_does_not_halt_the_run():
    """Three states, and only one of them is a switch.

    ``resolved_model`` is ``""`` when the reply carried no model field. The
    rule is written about a name that *differs*; a provider omitting a header
    is not a model switch, and ending a paid stage over one would be this code
    inventing a stop condition rather than enforcing the written one. Counted
    in the record instead — see the test below.
    """
    assert (
        runner.answered_by_something_else(_voices(""), pinned_model="gpt-5.4")
        == ()
    )


def test_a_voice_that_never_spoke_is_not_a_mismatch():
    assert (
        runner.answered_by_something_else([None], pinned_model="gpt-5.4")
        == ()
    )


def test_a_plan_that_pins_no_model_has_no_claim_to_check():
    """Deciding here what the run was allowed to be would be the wrong fix.

    A plan with no pinned name is a gap in the plan. Inventing a comparison
    against the deployment alias would hide it behind a check that passes.
    """
    assert (
        runner.answered_by_something_else(
            _voices("anything-at-all"), pinned_model=""
        )
        == ()
    )


def test_the_record_carries_the_pinned_name_beside_the_one_that_answered():
    written = runner.model_calls_record(
        {("task-1", 1): _Spoke("gpt-5.4-turbo", [_call()], Decimal("0.40"))},
        pinned_model="gpt-5.4",
    )

    assert written["pinned_model"] == "gpt-5.4"
    assert written["models_that_answered"] == ["gpt-5.4-turbo"]
    assert written["answered_by_something_else"] == ["gpt-5.4-turbo"]


def test_a_matching_run_says_so_rather_than_leaving_the_field_out():
    written = runner.model_calls_record(
        {("task-1", 1): _Spoke("gpt-5.4", [_call()], Decimal("0.40"))},
        pinned_model="gpt-5.4",
    )

    assert written["answered_by_something_else"] == []
    assert written["attempts_that_reported_no_model"] == 0


def test_replies_that_named_no_model_are_counted_even_though_they_do_not_halt():
    """Recorded, not enforced -- and the record says which.

    Not halting is a decision, and a decision that leaves no trace reads
    afterwards as a case nobody thought about.
    """
    written = runner.model_calls_record(
        {
            ("task-1", 1): _Spoke("", [_call()], Decimal("0.40")),
            ("task-2", 1): _Spoke("gpt-5.4", [_call()], Decimal("0.40")),
        },
        pinned_model="gpt-5.4",
    )

    assert written["attempts_that_reported_no_model"] == 1
    assert written["models_that_answered"] == ["gpt-5.4"]
    assert written["answered_by_something_else"] == []
    assert "not a model switch" in written["what_no_model_reported_means"]


def test_the_halt_and_the_record_are_the_same_computation():
    """So a run cannot stop for a reason its own record disagrees with.

    Both read ``answered_by_something_else``. Two implementations of "did the
    name differ" would be two chances to disagree, and the disagreement would
    only ever show up in a run that had already stopped.
    """
    source = RUNNER_PATH.read_text("utf-8")
    block = source.split("def wrong_model_answered(")[1].split("factory =")[0]

    assert block.count("answered_by_something_else") == 1
    assert "def cancel_requested()" in block
    assert "def stop_when(" in block
    assert "wrong_model_answered()" in block


def test_both_seams_are_wired_because_they_stop_different_things():
    """Read from the source: reaching either needs a paid call.

    ``cancel_requested`` is read before every model turn and every tool call,
    so the task that saw the wrong name does not take another turn -- that is
    the one that saves money. ``stop_when`` is read between tasks, so the run
    ends with the rule named instead of quietly finishing a manifest of
    cancelled tasks -- that is the one that saves the record. Either alone is
    wrong in a way that matters.
    """
    source = RUNNER_PATH.read_text("utf-8")
    factory = source.split("factory = build_runner_factory(")[1].split(")")[0]
    driving = source.split("outcome = run_manifest(")[1].split("except ")[0]

    assert "cancel_requested=cancel_requested" in factory
    assert "stop_when=stop_when" in driving


def test_the_stop_names_the_rule_the_plan_wrote_rather_than_a_new_one():
    """Rule 0 by index, out of STOP_RULES, not retyped.

    A halt that quoted its own sentence would be a rule this code invented,
    and the pre-registration would not contain it.
    """
    source = RUNNER_PATH.read_text("utf-8")
    block = source.split("def stop_when(")[1].split("\n\n")[0]

    assert "rule_index=0" in block
    assert "STOP_RULES[0]" in block


def test_it_enforces_the_reported_back_rule_and_not_its_neighbour():
    """Rule 0 and rule 1 are adjacent and different, and the first draft of
    this work implemented 0 while naming 1.

    Rule 0 compares a reply against the name the plan pinned, which nothing
    held. Rule 1 is a run switching on its own mid-conversation, which the
    voice does hold -- it raises when two replies in one conversation name two
    different models. Claiming 1 here would have moved a rule that already had
    an enforcer and left the one with none still uncovered, while every test
    went green.
    """
    from core.agentic_v2_preregistration import STOP_RULES

    assert "reported back" in STOP_RULES[0]
    assert "pinned" in STOP_RULES[0]
    assert "on its own" in STOP_RULES[1]


def test_the_plan_still_pins_a_model_for_the_comparison_to_use():
    """The check is only as good as the name it compares against.

    If the plan stopped pinning one, ``answered_by_something_else`` would
    return nothing for every run and the stop condition would silently become
    unenforced again -- passing, quietly, forever.
    """
    plan = yaml.safe_load(
        runner.STAGE_ONE_PLAN_PATH.read_text(encoding="utf-8")
    )

    assert str(plan["model"]["resolved_model"]).strip()


def test_the_written_rule_is_about_a_name_that_differs():
    """Pinned because the implementation reads it narrowly on purpose.

    An omitted name does not halt the run. That is defensible only while the
    rule says *differs*; if it is ever rewritten to cover a missing name, this
    fails and the narrow reading has to be revisited.
    """
    from core.agentic_v2_preregistration import STOP_RULES

    assert "differs" in STOP_RULES[0].lower()
