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
import os
import subprocess
import sys
from pathlib import Path

import pytest

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


class _Bound:
    """Just enough of a bound cohort to ask the guard about."""

    def __init__(self, task_ids):
        self._task_ids = tuple(task_ids)

    @property
    def task_ids(self):
        return self._task_ids


# ── The pricing guard ─────────────────────────────────────────────────────


def test_a_cohort_the_plan_priced_is_allowed_through():
    plan = {"task_ids": ["a", "b", "c"]}

    assert runner.check_the_plan_priced_this_stage(plan, _Bound(["a", "b", "c"])) == []


def test_a_cohort_larger_than_the_one_priced_is_refused_with_the_multiple():
    """The number is the point. "Not priced" invites someone to wave it through.

    Forty-four times an approved amount is a different conversation from a
    mismatch, and the person reading the refusal is the person who would have
    had it.
    """
    plan = {"task_ids": [f"t{n}" for n in range(5)]}

    problems = runner.check_the_plan_priced_this_stage(
        plan, _Bound([f"t{n}" for n in range(220)])
    )

    assert len(problems) == 1
    assert "roughly 44 times what was approved" in problems[0]
    assert "whole-run figures, not per-task ones" in problems[0]


def test_a_cohort_of_the_same_size_but_different_tasks_is_refused():
    """Same count, different work. Five tasks are not five tasks.

    The amounts were worked out over particular prompts with particular
    reference files. A cohort that merely matched on size would be a different
    run wearing the approved run's number.
    """
    plan = {"task_ids": ["a", "b"]}

    problems = runner.check_the_plan_priced_this_stage(plan, _Bound(["a", "c"]))

    assert len(problems) == 1
    assert "do not describe this run" in problems[0]


def test_a_plan_that_prices_nothing_does_not_divide_by_zero():
    """An empty plan is a refusal, not a crash inside the refusal."""
    problems = runner.check_the_plan_priced_this_stage({}, _Bound(["a"]))

    assert len(problems) == 1
    assert "roughly 1 times what was approved" in problems[0]


def test_the_guard_reads_the_cohort_rather_than_calling_it():
    """A regression test for a real one-character bug.

    ``BoundManifest.task_ids`` is a property. Calling it raised ``TypeError``
    from inside the guard — which is to say the guard that stops an unpriced run
    was itself broken, on every stage including the priced one. It failed loudly
    and cost nothing, but it would have failed the same way on the run that was
    allowed. Held here with an object that refuses to be called.
    """

    class RefusesToBeCalled:
        @property
        def task_ids(self):
            return ("a",)

    assert runner.check_the_plan_priced_this_stage({"task_ids": ["a"]}, RefusesToBeCalled()) == []


# ── The free path is free ─────────────────────────────────────────────────


def _run(*args, env=None):
    """Run the entry point as a subprocess, with no Azure environment at all."""
    clean = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("AZURE_", "FOUNDRY_", "OPENAI_"))
    }
    clean["PYTHONPATH"] = str(BATCH_RUNNER_ROOT)
    clean.update(env or {})
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
    """The whole path minus the network, with nothing configured to reach it."""
    finished = _run("--stage", "advance_check_5", "--dry-run")

    assert finished.returncode == 0, finished.stdout + finished.stderr
    assert "Every condition for the paid run is met" in finished.stdout
    assert "nothing was spent" in finished.stdout


@needs_dataset
@pytest.mark.parametrize("stage", ["trial_30", "full_220"])
def test_an_unpriced_stage_is_refused_before_anything_is_reached(stage):
    finished = _run("--stage", stage, "--dry-run")

    assert finished.returncode == 1, finished.stdout + finished.stderr
    assert "Refused before spending anything" in finished.stdout
    assert "this stage is not priced" in finished.stdout


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
    assert "against $2600.00 approved" in marking
    assert "not spent by this script" in marking


@needs_dataset
def test_the_dry_run_says_what_is_missing_rather_than_only_what_is_ready():
    """The handicap is printed on the way in, not discovered in the results."""
    printed = _run("--stage", "advance_check_5", "--dry-run").stdout

    assert "isolation      none — fixture backend, exec_run shut" in printed
    assert "reference files that are not in the workspace" in printed


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
