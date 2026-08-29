"""The stage-3 contract: the gold ceiling over the whole gold corpus.

Stage 1 measured a ceiling on 30 tasks and got 82.87 per cent. That sample is
the first 30 gold-bearing rows in dataset order, and the dataset runs in sector
blocks -- `_shard_slice` in step8_grade.py names the same property when it
explains why shards stride rather than take contiguous blocks: "the corpus
carries whatever ordering bias the source dataset had (sector runs, difficulty
drift)". So stage 1's 30 cover 4 sectors and 7 occupations, and its number is a
ceiling measured on a sixth of the sectors.

Stage 3 is the question stage 1 deferred: does 82.87 survive the rest. These
tests pin what would have to stay still for the two numbers to be comparable --
which tasks, which settings, which dataset commit -- and the one thing that is
allowed to change, which is how many tasks there are.

Spec: tasks/rebuilding_grading_task/304-full-gold-corpus.md
"""

import importlib.util
import math
from pathlib import Path
import re
import subprocess

import pytest
import yaml

import step8_grade as s8


REPO_ROOT = Path(__file__).resolve().parents[2]
BATCH_RUNNER = REPO_ROOT / "batch-runner"
FULL_CONFIG_PATH = BATCH_RUNNER / "grading_configs/gold_ceiling_185_v2_sol_max.yaml"
SAMPLE_CONFIG_PATH = BATCH_RUNNER / "grading_configs/gold_ceiling_30_v2_sol_max.yaml"
PRODUCTION_CONFIG_PATH = BATCH_RUNNER / "grading_configs/default_v2_sol_max.yaml"
SPEC_PATH = REPO_ROOT / "tasks/rebuilding_grading_task/304-full-gold-corpus.md"

#: The dataset commit stages 1, 2 and 3 are all frozen to. Written out rather
#: than read from the config, so a test comparing the config to it is checking
#: something.
PINNED_DATASET_SHA = "11e7900cdcac61bc4daf59e65feb238acda98fbf"

#: The whole gold population, and stage 1's sample of it.
CORPUS_SIZE = 185
SAMPLE_SIZE = 30

#: What the dataset covers at the pinned revision, measured from the committed
#: manifest. The claim stage 3 rests on is that the first number is reached by
#: the gold corpus and the second is not reached by stage 1's sample.
SECTOR_COUNT = 9
OCCUPATION_COUNT = 44


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _manifest_module():
    """Import the manifest builder by path.

    It lives under scripts/ with no package, and it is the only place that
    knows how a task's row maps to its gold files -- re-deriving that rule here
    would be re-deriving the thing under test.
    """
    spec = importlib.util.spec_from_file_location(
        "_gold_manifest_builder",
        BATCH_RUNNER / "scripts/build_gold_deliverable_manifest.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _manifest():
    module = _manifest_module()
    return module, module.load_manifest()


def _pinned() -> list[str]:
    return _load_yaml(FULL_CONFIG_PATH)["rerun_identity"]["task_ids"]


# --------------------------------------------------------------------------
# Which 185, and why not 220
# --------------------------------------------------------------------------


def test_the_pinned_corpus_is_every_gold_bearing_task_not_a_sample_of_them():
    """This is a population, not a sample, so nothing may be left over.

    Stage 1 pinned a prefix and had to argue for the cut. Stage 3 pins the
    whole gold population and so has no cut to argue for -- but only if the
    list really is everything. A single dropped task would turn stage 3 back
    into a sample while still calling itself complete.
    """
    module, manifest = _manifest()
    derived = module.gold_bearing_task_ids(manifest)
    pinned = _pinned()

    assert pinned == derived
    assert len(pinned) == CORPUS_SIZE
    assert len(set(pinned)) == CORPUS_SIZE
    assert manifest["gold_bearing_task_count"] == CORPUS_SIZE


def test_the_thirty_five_left_out_are_exactly_the_ones_with_no_expert_answer():
    """The only ground for exclusion is having nothing to grade.

    A task the dataset ships no reference answer for cannot be graded against
    its reference answer. Any other reason for a task to be missing would be a
    choice, and a choice would need defending.
    """
    module, manifest = _manifest()
    pinned = set(_pinned())

    excluded = [task for task in manifest["tasks"] if task["task_id"] not in pinned]
    assert len(excluded) == manifest["task_count"] - CORPUS_SIZE == 35
    for task in excluded:
        assert not task["files"], (
            f"{task['task_id']} has an expert answer but is not pinned"
        )
    for task in manifest["tasks"]:
        if task["files"]:
            assert task["task_id"] in pinned, (
                f"{task['task_id']} has an expert answer and is not graded"
            )


def test_the_pinned_corpus_is_ordered_the_way_the_grader_demands():
    """`filter_tasks_for_config` refuses a pin that is not in source order.

    That refusal is the safety net; this is the tripwire in front of it. The
    manifest records each task's row position, so the pinned list is in source
    order exactly when those positions ascend.
    """
    module, manifest = _manifest()
    positions = {task["task_id"]: task["position"] for task in manifest["tasks"]}

    pinned_positions = [positions[task_id] for task_id in _pinned()]
    assert pinned_positions == sorted(pinned_positions)


def test_stage_one_graded_the_first_thirty_of_exactly_these_tasks():
    """The two stages have to be nested, or their numbers are not comparable.

    82.87 per cent came from 30 tasks. Stage 3 is only a widening of that
    measurement if those same 30 are inside it, in the same order, scored the
    same way. If the lists ever diverge, stage 3 stops being the continuation
    of stage 1 and becomes a separate measurement that happens to look similar.
    """
    pinned = _pinned()
    sample = _load_yaml(SAMPLE_CONFIG_PATH)["rerun_identity"]["task_ids"]

    assert sample == pinned[:SAMPLE_SIZE]


# --------------------------------------------------------------------------
# The breadth that is the whole reason to run this
# --------------------------------------------------------------------------


def test_dropping_the_thirty_five_costs_no_sector_and_no_occupation():
    """The gold corpus is the full breadth of the benchmark, not a slice of it.

    This is what makes 185 an acceptable answer to a question asked about 220.
    If the 35 unanswerable tasks had taken a sector or an occupation with them,
    stage 3 could only speak for what was left, and the gap would have to be
    stated every time the number was quoted. They do not: the sets are equal,
    not merely the same size.
    """
    _, manifest = _manifest()
    pinned = set(_pinned())

    everything = {(t["sector"], t["occupation"]) for t in manifest["tasks"]}
    gold = {
        (t["sector"], t["occupation"])
        for t in manifest["tasks"]
        if t["task_id"] in pinned
    }

    assert gold == everything
    assert len({sector for sector, _ in gold}) == SECTOR_COUNT
    assert len({occupation for _, occupation in gold}) == OCCUPATION_COUNT


def test_stage_ones_sample_reached_far_less_than_this():
    """The gap between the two is the finding stage 3 exists to close.

    Recorded as a test rather than as prose in the spec because it is the
    entire justification for spending on stage 3. If a future edit to the
    sample made it broad enough, this test fails and the spec's argument has to
    be rewritten rather than quietly falsified.
    """
    _, manifest = _manifest()
    by_task = {task["task_id"]: task for task in manifest["tasks"]}
    sample = _load_yaml(SAMPLE_CONFIG_PATH)["rerun_identity"]["task_ids"]

    sectors = {by_task[t]["sector"] for t in sample}
    occupations = {by_task[t]["occupation"] for t in sample}

    assert len(sectors) == 4
    assert len(occupations) == 7
    assert len(sectors) < SECTOR_COUNT
    assert len(occupations) < OCCUPATION_COUNT


# --------------------------------------------------------------------------
# Nothing but the corpus changed
# --------------------------------------------------------------------------


def test_the_full_run_grades_with_the_sample_runs_settings_unchanged():
    """Two ceilings measured under different settings cannot be compared.

    Stage 3's entire output is a number placed next to 82.87 per cent. That
    comparison is only meaningful if the judge, its reasoning effort, its tools
    and caps, its perception models, its prompts and its rate-limit guard are
    the ones stage 1 used. Only identity may differ, and identity is the corpus.
    """
    full = _load_yaml(FULL_CONFIG_PATH)
    sample = _load_yaml(SAMPLE_CONFIG_PATH)

    for block in ("judge", "grader", "tpm_guard", "prompt", "rubric", "output"):
        assert full[block] == sample[block], f"{block} diverged"

    differing = {
        key
        for key in set(full) | set(sample)
        if full.get(key) != sample.get(key)
    }
    assert differing == {"config_name", "description", "rerun_identity"}


def test_the_full_run_grades_with_production_settings_unchanged():
    """A ceiling is only the ceiling of the settings that produced it.

    Checked against production directly and not just transitively through the
    sample config, so that an edit landing in both gold configs at once still
    fails here.
    """
    full = _load_yaml(FULL_CONFIG_PATH)
    production = _load_yaml(PRODUCTION_CONFIG_PATH)

    for block in ("judge", "grader", "tpm_guard", "prompt", "output"):
        assert full[block] == production[block], f"{block} diverged"

    # The rubric block may differ in exactly one field: the revision, pinned to
    # a commit here where production follows `main`. Following a branch is what
    # a measurement meant to be repeated cannot tolerate.
    assert {k: v for k, v in full["rubric"].items() if k != "revision"} == {
        k: v for k, v in production["rubric"].items() if k != "revision"
    }
    assert production["rubric"]["revision"] == "main"
    assert full["rubric"]["revision"] == PINNED_DATASET_SHA


def test_the_full_run_pins_one_commit_for_both_rubric_and_corpus():
    """For a gold corpus the dataset IS the inference.

    No model ran, so the revision that supplied the answers has to be the
    revision that supplied the rubric being scored against them. It also has to
    be the commit stages 1 and 2 used, or stage 3 is grading a different corpus.
    """
    identity = _load_yaml(FULL_CONFIG_PATH)["rerun_identity"]

    assert identity["rubric_commit_sha"] == PINNED_DATASET_SHA
    assert identity["inference_revision"] == PINNED_DATASET_SHA
    assert identity["experiment_id"] == "exp_gold_baseline"
    assert identity["expected_task_count"] == CORPUS_SIZE


def test_the_full_run_does_not_forgive_missing_provenance():
    """`allow_legacy_missing_provenance` must stay absent.

    It forgives a submission whose Azure routes were never recorded. Here no
    inference ran, so there is no route that could be missing -- setting it
    would excuse a gap this corpus cannot have, on the one config whose size
    makes it the tempting place to loosen something.
    """
    identity = _load_yaml(FULL_CONFIG_PATH)["rerun_identity"]

    assert "allow_legacy_missing_provenance" not in identity


def test_the_full_run_passes_the_grader_validator():
    """185 also has to clear the validator's own bounds, which stop at 220."""
    s8.validate_grading_config(_load_yaml(FULL_CONFIG_PATH))


# --------------------------------------------------------------------------
# A ceiling must never be publishable as a competitor's result
# --------------------------------------------------------------------------


def test_pinning_every_gold_task_is_still_a_subset_of_the_graded_payload():
    """185 is the whole gold population and still a subset of the payload.

    That reads like a contradiction and is not. `gold_rows_from_parquet` keeps
    all 220 rows deliberately, the 35 answerless ones carrying
    `no_gold_deliverable`, and its docstring gives the reason: "Dropping them
    would make a pinned 30-task selection read as the *whole* corpus
    downstream, and a subset that calls itself complete is published as a final
    grade instead of a diagnostic one."

    So the scope stays `subset` at 185 exactly as it was at 30, and the output
    forks into `_diagnostic/` on that ground as well as on provenance. Pinned
    here because a later "tidy-up" that drops the empty rows would silently
    promote this run to a publishable grade.
    """
    inference = {
        "results": [{"task_id": f"task-{index:03d}"} for index in range(220)]
    }
    config = {
        "rerun_identity": {
            "task_ids": [f"task-{index:03d}" for index in range(CORPUS_SIZE)]
        }
    }

    tasks, scope = s8.filter_tasks_for_config(
        inference, config, tasks_csv=None, limit=0
    )

    assert len(tasks) == CORPUS_SIZE
    assert scope == "subset"


# --------------------------------------------------------------------------
# The run has to fit the machinery that will carry it
# --------------------------------------------------------------------------


@pytest.mark.parametrize("shard_count", [1, 5, 8, 10, 11])
def test_every_allowed_shard_count_covers_the_corpus_exactly_once(shard_count):
    """The union of the shards must be the corpus, in canonical order.

    A 60-hour serial run is only survivable in shards, and the identity fields
    keep describing the whole corpus while each shard grades a stride of it. So
    the arithmetic that reunites them is load-bearing: a gap loses a task
    silently, an overlap pays for one twice.
    """
    tasks = [{"task_id": task_id} for task_id in _pinned()]

    slices = [
        s8._shard_slice(tasks, shard_index=index, shard_count=shard_count)
        for index in range(shard_count)
    ]
    seen = [task["task_id"] for shard in slices for task in shard]

    assert sorted(seen) == sorted(task["task_id"] for task in tasks)
    assert len(seen) == CORPUS_SIZE
    for shard in slices:
        assert s8._is_ordered_subsequence(
            [task["task_id"] for task in shard], _pinned()
        )


#: Measured on the committed 220-task Sol Max run and recorded in
#: 300-gold-ceiling.md: 19.44 minutes a task on average, 32.7 at p90.
MEAN_TASK_MINUTES = 19.44
P90_TASK_MINUTES = 32.7


def _workflow_numbers() -> dict[str, int]:
    """Read the three timing limits out of grade-run.yml.

    Read rather than restated, so that changing one of them in the workflow
    breaks this test instead of quietly invalidating the arithmetic the run
    plan is built on.
    """
    text = (REPO_ROOT / ".github/workflows/grade-run.yml").read_text(encoding="utf-8")
    budget = re.search(r'GRADER_TIME_BUDGET_SEC:\s*"(\d+)"', text)
    timeout = re.search(r"^\s*timeout-minutes:\s*(\d+)", text, re.MULTILINE)
    resume_cap = re.search(r"NEXT_CHUNK -gt (\d+)", text)
    assert budget and timeout and resume_cap, "grade-run.yml no longer states its limits"
    return {
        "budget_min": int(budget.group(1)) // 60,
        "timeout_min": int(timeout.group(1)),
        "resume_cap": int(resume_cap.group(1)),
    }


def test_a_chunk_can_always_save_before_the_runner_kills_it():
    """The time budget must fire far enough ahead of the job timeout.

    The budget is a *pre-check*: step8_grade.py tests the clock before starting
    a task, never during one. So a chunk can begin its last task at one second
    under budget and then run for that task's full duration. The gap between
    budget and timeout therefore has to be wider than a task, or a shard is
    killed mid-judgement having saved nothing and having paid for everything.

    Checked at p90 rather than at the mean, because the mean is not the case
    that kills a job.
    """
    limits = _workflow_numbers()

    assert limits["budget_min"] < limits["timeout_min"]
    headroom = limits["timeout_min"] - limits["budget_min"]
    assert headroom > P90_TASK_MINUTES, (
        f"only {headroom} min between the {limits['budget_min']} min budget and "
        f"the {limits['timeout_min']} min timeout; a p90 task is "
        f"{P90_TASK_MINUTES} min"
    )


def test_the_widest_shard_finishes_inside_the_auto_resume_cap():
    """A shard is expected to outlast one chunk; it must not outlast ten.

    11 shards is the workflow's own cap, so the largest shard is 17 tasks, and
    at the measured mean that is about 5.5 hours against a 4 hour chunk. Going
    over is normal -- the auto-resume exists for it. What is not survivable is
    needing more chunks than the resume cap allows, because the run would then
    stop halfway with the money spent.
    """
    limits = _workflow_numbers()
    largest = max(len(_pinned()[index::11]) for index in range(11))
    assert largest == 17

    minutes = largest * MEAN_TASK_MINUTES
    chunks = math.ceil(minutes / limits["budget_min"])

    assert minutes > limits["budget_min"], (
        "a shard finishing inside one chunk would make this test vacuous"
    )
    assert chunks == 2
    assert chunks <= limits["resume_cap"]


# --------------------------------------------------------------------------
# The written record has to match what was actually frozen
# --------------------------------------------------------------------------


def test_the_spec_pins_the_same_corpus_the_config_does():
    """The spec is the document a reader trusts without opening the YAML."""
    spec = SPEC_PATH.read_text(encoding="utf-8")
    _, manifest = _manifest()

    assert PINNED_DATASET_SHA in spec
    assert f"`{manifest['dataset_file_sha256']}`" in spec
    assert str(CORPUS_SIZE) in spec
    assert s8._ordered_task_ids_sha256(_pinned()) in spec


def test_the_spec_states_its_thresholds_before_the_run():
    """Pass criteria written after seeing the result are not pass criteria.

    Stage 1 fixed three numbers in advance and then failed two of them, which
    is the only reason its report says anything. Stage 3 inherits the same
    three, so they have to be in the document before the spend, in a form that
    cannot be softened later without the diff showing it.
    """
    spec = SPEC_PATH.read_text(encoding="utf-8")

    for threshold in ("90", "0.95", "2%"):
        assert threshold in spec, f"pass criterion {threshold} is not stated"
    assert "82.87" in spec, "the number being compared against is not stated"


# --------------------------------------------------------------------------
# The contract must survive a fresh clone
# --------------------------------------------------------------------------


CONTRACT_FILES = (
    "batch-runner/grading_configs/gold_ceiling_185_v2_sol_max.yaml",
    "tasks/rebuilding_grading_task/304-full-gold-corpus.md",
)


@pytest.mark.parametrize("relative", CONTRACT_FILES)
def test_the_stage_three_contract_is_in_the_repository(relative):
    path = REPO_ROOT / relative
    assert path.is_file(), f"{relative} is missing"
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", relative],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert tracked.returncode == 0, (
        f"{relative} exists here but git does not track it, so a fresh clone "
        "would not have it."
    )
