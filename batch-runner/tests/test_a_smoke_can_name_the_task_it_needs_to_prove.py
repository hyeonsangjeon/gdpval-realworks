"""A smoke that cannot reach an audio task proves nothing about audio.

``step8_grade.py`` has taken ``--tasks`` since long before any of this, but
``grade-run.yml`` exposed only ``tasks_limit``, and ``--limit`` takes
``tasks[:n]`` in corpus order. The first task carrying real media sits at
corpus position 46, so the cheapest limit-based run that touches the audio
path grades forty-eight tasks at Sol Max rates — which is not a smoke, it is
a quarter of the corpus.

That is why the input exists. The rest of this file is about the two ways
adding it could go wrong:

* the value is spliced into an argv array *and* into the digest that names an
  output directory, so it is matched against the shape of a task_id rather
  than merely quoted;
* narrowing the corpus forks the output into ``_diagnostic/<scope_sha>/``, so
  a chunk that resumed without the narrowing would grade the whole corpus into
  a different path and abandon the partial it was dispatched to finish.

The last test generalises that second point past this one input, because the
bug it describes is not specific to ``tasks``: any dispatch input the
auto-resume forgets is silently dropped on every chunk after the first.

Nothing here calls a model or a network. The behavioural tests run the shipped
validation step, sliced out of the workflow.
"""

from __future__ import annotations

import ast
import subprocess
import tempfile
import textwrap
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github/workflows/grade-run.yml"

VALIDATE_STEP = "Validate workflow context and inputs"
RETRIGGER_STEP = "Auto-retrigger next chunk (time budget hit)"

# The one this smoke was built to reach: a task whose reference bundle carries
# .mp3, .mp4 and .wav, so it exercises the Responses API `input_audio` shape
# that run 33239148807 could not get past.
AUDIO_TASK = "75401f7c-396d-406d-b08e-938874ad1045"


# ── reading the workflow ─────────────────────────────────────────────────


def _workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _steps() -> list[dict]:
    return [
        step
        for job in _workflow()["jobs"].values()
        for step in job.get("steps", [])
    ]


def _step(name: str) -> dict:
    for step in _steps():
        if step.get("name") == name:
            return step
    raise AssertionError(f"grade-run.yml has no step named {name!r}")


def _dispatch_inputs() -> dict:
    workflow = _workflow()
    triggers = workflow[True] if True in workflow else workflow["on"]
    return triggers["workflow_dispatch"]["inputs"]


# ── running the shipped validation ───────────────────────────────────────


BASELINE = {
    "GITHUB_EVENT_NAME": "workflow_dispatch",
    "GITHUB_REF": "refs/heads/main",
    "GITHUB_REF_NAME": "main",
    "GITHUB_REPOSITORY": "hyeonsangjeon/gdpval-realworks",
    "GITHUB_SHA": "0" * 40,
    "GITHUB_WORKFLOW_SHA": "0" * 40,
    "GITHUB_WORKFLOW_REF": (
        "hyeonsangjeon/gdpval-realworks"
        "/.github/workflows/grade-run.yml@refs/heads/main"
    ),
    "GRADE_EXPERIMENT_YAML": "exp_gold_baseline",
    "GRADE_CONFIG": "gold_ceiling_185_v2_sol_max.yaml",
    "GRADE_INFERENCE_REVISION": "",
    "GRADE_FORCE": "false",
    "GRADE_DRY_RUN": "true",
    "GRADE_PAID_APPROVAL": "false",
    "GRADE_RESUME": "false",
    "GRADE_TASKS_LIMIT": "0",
    "GRADE_TASKS": "",
    "GRADE_RESUME_CHUNK": "0",
    "GRADE_SHARD_COUNT": "1",
    "GRADE_SHARD_INDEX": "0",
    "GRADE_RUN_ORDINAL": "1",
    "PATH": "/usr/bin:/bin",
}


def _validate(**overrides: str) -> subprocess.CompletedProcess:
    """The real step, run against a dispatch that differs in one field."""
    # Every step GitHub runs is handed a writable GITHUB_OUTPUT, and this one
    # writes the experiment name's single-component form to it. Run without
    # one, the script would die on the unbound variable under `set -u` --
    # before reaching the check any test below is actually about.
    with tempfile.TemporaryDirectory() as step_outputs:
        return subprocess.run(
            ["bash", "-c", _step(VALIDATE_STEP)["run"]],
            capture_output=True, text=True,
            env={
                **BASELINE,
                "GITHUB_OUTPUT": str(Path(step_outputs) / "step_output"),
                **overrides,
            },
        )


def test_the_baseline_dispatch_is_accepted():
    """Anchors every rejection below.

    Without this, a test asserting that some bad value is refused would pass
    just as happily if the baseline were refused too, and would then be
    measuring nothing.
    """
    result = _validate()
    assert result.returncode == 0, result.stdout + result.stderr


def test_a_smoke_may_name_the_one_task_it_needs():
    """The point of the input."""
    assert _validate(GRADE_TASKS=AUDIO_TASK).returncode == 0


def test_naming_several_tasks_is_accepted():
    assert _validate(
        GRADE_TASKS=f"{AUDIO_TASK},e222075d-5d62-4757-ae3c-e34b0846583b"
    ).returncode == 0


def test_the_empty_default_still_grades_the_whole_corpus():
    """Every existing dispatch omits this input; none of them may change."""
    assert _validate(GRADE_TASKS="").returncode == 0


@pytest.mark.parametrize(
    "value",
    [
        "--force",                                   # a flag, not a task
        f"{AUDIO_TASK} --force",                     # a flag smuggled after one
        f"{AUDIO_TASK};rm -rf /",                    # shell metacharacters
        f"{AUDIO_TASK},",                            # trailing comma: empty id
        f",{AUDIO_TASK}",
        f"{AUDIO_TASK},,{AUDIO_TASK}",
        f" {AUDIO_TASK}",                            # whitespace
        f"{AUDIO_TASK} ",
        "75401f7c-396d-406d-b08e",                   # truncated
        AUDIO_TASK.upper(),                          # step8 compares literally
        "../../etc/passwd",
        "*",
    ],
)
def test_anything_that_is_not_a_task_id_is_refused(value):
    """Checked for shape, not just quoted.

    Quoting would make these safe to *pass*; it would not make them safe to
    act on. ``--force`` reaching the argv array is a different run than the
    one that was approved, and a value containing a slash reaching the scope
    digest is a different output path. Both are cheaper as a refusal here than
    as a discovery afterwards.
    """
    result = _validate(GRADE_TASKS=value)
    assert result.returncode == 1, f"{value!r} was accepted"
    assert "tasks must be a comma-separated list of task_id UUIDs" in result.stdout


def test_naming_tasks_and_sharding_together_is_refused():
    """The same incompatibility ``tasks_limit`` already has.

    Both narrow the corpus, and narrowing forks the output into a diagnostic
    subtree that ``step9_merge_shards`` does not look in. Eleven shards
    scattered across it would each succeed and never merge.
    """
    result = _validate(GRADE_TASKS=AUDIO_TASK, GRADE_SHARD_COUNT="11",
                       GRADE_SHARD_INDEX="3")
    assert result.returncode == 1
    assert "shard_count > 1 cannot be combined with tasks" in result.stdout


# ── the value has to reach step8, and survive a resume ───────────────────


def test_both_grade_steps_pass_the_task_list_to_step8():
    """The dry run predicts the paid run only if both build the same argv."""
    passing = [
        step for step in _steps()
        if 'ARGS+=(--tasks "$GRADE_TASKS")' in (step.get("run") or "")
    ]
    assert len(passing) == 2, (
        "both the read-only and the paid grade step must forward --tasks; "
        f"found {len(passing)}"
    )
    for step in passing:
        run = step["run"]
        assert 'if [[ -n "$GRADE_TASKS" ]]; then' in run, (
            "an unguarded --tasks would pass an empty list on every ordinary "
            "dispatch, which step8 rejects outright"
        )


def _retrigger_inputs() -> set[str]:
    """The dispatch body the auto-resume actually sends, parsed as code."""
    run = _step(RETRIGGER_STEP)["run"]
    lines = run.splitlines()
    start = next(i for i, l in enumerate(lines)
                 if l.strip().startswith("python - <<'PY'"))
    end = next(i for i, l in enumerate(lines[start + 1:], start + 1)
               if l.strip() == "PY")
    body = ast.parse(textwrap.dedent("\n".join(lines[start + 1:end])))

    for node in ast.walk(body):
        if not isinstance(node, ast.Dict):
            continue
        for key, value in zip(node.keys, node.values):
            if (isinstance(key, ast.Constant) and key.value == "inputs"
                    and isinstance(value, ast.Dict)):
                return {
                    k.value for k in value.keys
                    if isinstance(k, ast.Constant)
                }
    raise AssertionError("the auto-resume dispatch has no inputs mapping")


def test_a_resumed_chunk_is_dispatched_with_every_input_it_was_given():
    """The general form of the bug, not just this input's version of it.

    A chunk that hits its four hours dispatches its own successor, and any
    dispatch input missing from that body silently reverts to its default for
    every chunk after the first. For ``tasks`` that means chunk two grading
    185 tasks into a different directory than the partial chunk one left. For
    ``run_ordinal`` it meant overwriting the run being compared against — a
    comment in the workflow records that one being found the hard way.

    Asserting equality rather than containment is deliberate: an input added
    later fails here, at no cost, instead of surfacing hours into a paid run.
    """
    assert _retrigger_inputs() == set(_dispatch_inputs()), (
        "the auto-resume must carry every dispatch input; missing ones revert "
        "to their defaults on chunk two and are not recoverable afterwards"
    )


def test_the_task_input_is_declared_the_way_the_shell_reads_it():
    """A ``number`` or ``boolean`` here would arrive as something else."""
    declared = _dispatch_inputs()["tasks"]
    assert declared["type"] == "string"
    assert declared["default"] == ""
    assert declared["required"] is False, (
        "every existing dispatch omits this input; making it required breaks "
        "all of them, including the eleven-shard full run"
    )
