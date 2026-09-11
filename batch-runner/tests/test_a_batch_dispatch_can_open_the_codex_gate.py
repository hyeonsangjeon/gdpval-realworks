"""The Codex run place has a gate, and this is the only thing that opens it.

``step2_run_inference._require_runnable_execution_mode`` refuses
``codex_foundry`` unless ``CODEX_FOUNDRY_CONNECTION_CONFIRMED`` is set, and
until this change ``batch-run.yml`` had no way to set it, so the mode ran only
through its own tests. The gate itself is not what changes here. What changes
is that a person dispatching the workflow can now open it, deliberately, by
ticking a box that defaults to off.

The distinction the gate is drawing is worth restating, because it is easy to
read it as being about the connection and it is not. The connection is
answered: run ``34465567349`` sent one turn to the Foundry deployment and the
reply matched the instruction it was given. "A request was answered" and "this
batch may spend" are different claims, and only the second one needs a person.

Three properties are pinned here, and each of them is a way the gate could be
opened by accident rather than on purpose.

**A dispatch that forgets the box fails; it does not quietly skip.** A skipped
job reads as "nothing to do". This is the same shape as ``reject-agentic``: a
job with no checkout, no credentials and ``exit 1``.

**The variable is derived from the box, never from the block.** ``codex_blocked``
is false in two unrelated situations -- the box was ticked, and the
credential-free parser did not think this was a Codex experiment at all. Only
one of those means somebody decided. Keying the variable off the second would
set it with nobody having ticked anything. Checked for every step that starts
the entrypoint, not for the one that was thought of first: naming ``step2a``
alone is how the checkpoint validation shipped without the variable and stayed
green, and the first run long enough to need a handover died on it.

**Every relay leg carries it.** The relay forwards inputs one at a time by
name, so an input that is added and not forwarded is a run that spends on leg 0
and is refused on leg 1. That is checked for every input rather than for this
one, because the next input added has the same problem.
"""

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
BATCH_WORKFLOW = ROOT / ".github" / "workflows" / "batch-run.yml"

#: An experiment that asks for the mode, and one that does not. Real files, so
#: that a rename or a mode change breaks this rather than leaving it testing a
#: string nothing reads.
CODEX_EXPERIMENT = "exp033_codex_foundry_fixed5"
OTHER_EXPERIMENT = "exp998_smoke_baseline_sample"


@pytest.fixture(scope="module")
def workflow():
    return yaml.safe_load(BATCH_WORKFLOW.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def dispatch_inputs(workflow):
    # `on` parses as the boolean True, which is why this is not workflow["on"].
    return workflow[True]["workflow_dispatch"]["inputs"]


def _batch_steps(workflow):
    return workflow["jobs"]["batch-run"]["steps"]


def _named_step(workflow, name):
    for step in _batch_steps(workflow):
        if step.get("name") == name:
            return step
    raise AssertionError(f"no step named {name!r} in the batch-run job")


def _steps_that_reach_the_gate(workflow):
    """Every step whose shell starts the entrypoint that holds the gate.

    Enumerated rather than listed by name, because the omission this checks
    for is precisely an author adding a place that runs it and not knowing
    there was a variable to carry. Both spellings count: ``step2a`` goes
    through ``step2_run_inference.sh``, which is four lines ending in
    ``python3 step2_run_inference.py``, and the checkpoint validation calls the
    module directly.

    Matching on the ``run`` body is safe here because YAML comments are gone by
    the time this sees the document -- the long note above step2a's variable
    names the module and is not a call.
    """
    return [
        step
        for step in _batch_steps(workflow)
        if re.search(r"step2_run_inference\.(py|sh)\b", str(step.get("run", "")))
    ]


def _mode_script(workflow):
    """The Ruby that decides, extracted from its heredoc."""
    step = next(
        step
        for step in workflow["jobs"]["inspect-mode"]["steps"]
        if step.get("id") == "mode"
    )
    body = step["run"].split("ruby <<'RUBY'\n", 1)[1]
    return body.rsplit("RUBY", 1)[0]


def _run_mode_script(workflow, experiment, confirmed):
    """Run the real decision on a real experiment file.

    Skipped where there is no Ruby, which is every development box here and no
    GitHub-hosted runner. The static checks below hold either way; this is the
    one that executes what CI will execute.

    The interpreter is resolved to an absolute path before the environment is
    replaced, because a runner may keep its Ruby somewhere the trimmed PATH
    below does not reach and a skip is a better outcome than a false failure.
    """
    ruby = shutil.which("ruby")
    if ruby is None:
        pytest.skip("no ruby interpreter on this host")
    with tempfile.TemporaryDirectory() as scratch:
        output = Path(scratch) / "github_output"
        output.touch()
        finished = subprocess.run(
            [ruby, "-e", _mode_script(workflow)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            env={
                "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                "GITHUB_OUTPUT": str(output),
                "EXPERIMENT_YAML": experiment,
                "CODEX_FOUNDRY_CONFIRMED": confirmed,
            },
        )
        written = dict(
            line.split("=", 1)
            for line in output.read_text(encoding="utf-8").splitlines()
            if "=" in line
        )
    return finished, written


# ── The box ────────────────────────────────────────────────────────────────


def test_the_box_exists_and_is_off_unless_somebody_ticks_it(dispatch_inputs):
    """A default of true would be no gate at all, only a longer form."""
    setting = dispatch_inputs["codex_foundry_confirmed"]
    assert setting["type"] == "boolean"
    assert setting["default"] is False
    assert setting["required"] is False
    # It says which mode it is for, because it is inert for every other one and
    # a description that did not say so would read as a general cost switch.
    assert "codex_foundry" in setting["description"]


# ── The decision, made where there are no credentials ──────────────────────


def test_the_decision_is_published_by_the_job_that_holds_nothing(workflow):
    """Same job as the agentic check, and for the same reason.

    It has no credentials and its checkout does not persist any, so whatever it
    decides is decided before anything could be spent.
    """
    inspect = workflow["jobs"]["inspect-mode"]
    assert inspect["permissions"] == {"contents": "read"}
    checkout = next(
        step
        for step in inspect["steps"]
        if step.get("name") == "Checkout config only"
    )
    assert checkout["with"]["persist-credentials"] is False
    for name in ("uses_codex_foundry", "codex_confirmed", "codex_blocked"):
        assert inspect["outputs"][name] == f"${{{{ steps.mode.outputs.{name} }}}}"


def test_the_box_is_read_through_the_environment_not_the_inputs_context(
    workflow,
):
    """A boolean compared against a string in a job `if` is a trap.

    ``inputs.x`` is a boolean for ``workflow_dispatch``; through an env var the
    same value arrives as the text "true" or "false". A job-level `if` that
    compares text to `true` casts the text to a number, gets NaN, and takes the
    wrong branch. Normalising once, here, means every consumer below compares
    text to text and none of them has to know which shape it started as.
    """
    step = next(
        step
        for step in workflow["jobs"]["inspect-mode"]["steps"]
        if step.get("id") == "mode"
    )
    assert step["env"]["CODEX_FOUNDRY_CONFIRMED"] == (
        "${{ inputs.codex_foundry_confirmed }}"
    )
    script = _mode_script(workflow)
    assert "ENV.fetch('CODEX_FOUNDRY_CONFIRMED'" in script
    assert "execution['mode'] == 'codex_foundry'" in script


@pytest.mark.parametrize(
    "experiment,confirmed,expected",
    [
        (CODEX_EXPERIMENT, "true", "false"),
        (CODEX_EXPERIMENT, "false", "true"),
        # An input that never arrives is an input that was not ticked.
        (CODEX_EXPERIMENT, "", "true"),
        # The box is inert everywhere else, ticked or not. Making it an error
        # would mean a relay leg could start failing halfway through a run for
        # carrying a flag it never used.
        (OTHER_EXPERIMENT, "true", "false"),
        (OTHER_EXPERIMENT, "false", "false"),
    ],
)
def test_the_decision_runs_out_the_way_it_reads(
    workflow, experiment, confirmed, expected
):
    """The truth table, executed rather than described."""
    finished, written = _run_mode_script(workflow, experiment, confirmed)
    assert finished.returncode == 0, finished.stderr
    assert written["codex_blocked"] == expected
    assert written["uses_codex_foundry"] == str(
        experiment == CODEX_EXPERIMENT
    ).lower()


def test_a_value_it_cannot_read_is_not_permission(workflow):
    """Fail closed. The safe reading of a value nobody understands is 'no'."""
    finished, written = _run_mode_script(workflow, CODEX_EXPERIMENT, "yes")
    assert finished.returncode != 0
    assert "codex_foundry_confirmed must be true or false" in finished.stderr
    assert written == {}


# ── What the decision stops ────────────────────────────────────────────────


def test_an_unconfirmed_dispatch_fails_rather_than_skipping(workflow):
    """A skipped job reads as 'nothing to do'. This has to read as 'refused'.

    Shaped exactly like ``reject-agentic``: no checkout, nothing fetched,
    nothing with credentials, and a non-zero exit so the run is red.
    """
    reject = workflow["jobs"]["reject-unconfirmed-codex"]
    assert reject["needs"] == "inspect-mode"
    assert reject["if"] == "needs.inspect-mode.outputs.codex_blocked == 'true'"
    assert reject["permissions"] == {"contents": "read"}
    assert all("uses" not in step for step in reject["steps"])
    assert any("exit 1" in step.get("run", "") for step in reject["steps"])


def test_the_credentialed_job_does_not_start_at_all(workflow):
    """The reject job going red does not stop this one; only its own `if` does.

    The two are siblings, not a sequence. Leaving this guard off would give a
    run that is red *and* has already spent.
    """
    assert workflow["jobs"]["batch-run"]["if"] == (
        "needs.inspect-mode.outputs.uses_agentic != 'true' && "
        "needs.inspect-mode.outputs.codex_blocked != 'true'"
    )


def test_the_second_parser_stops_the_job_before_a_credential_is_used(workflow):
    """For the one case the credential-free job cannot cover: disagreement.

    inspect-mode reads the experiment with Ruby's YAML; ``read_config`` reads it
    with ``ExperimentConfig``, the parser the run itself uses. If the second
    sees a Codex experiment the first missed, this job is already running, so
    the stop has to be inside it and ahead of everything it holds.
    """
    steps = _batch_steps(workflow)
    names = [step.get("name", "") for step in steps]
    block = names.index(
        "Block unconfirmed codex_foundry in credentialed general workflow"
    )
    assert steps[block]["if"] == (
        "steps.read_config.outputs.uses_codex_foundry == 'true' && "
        "needs.inspect-mode.outputs.codex_confirmed != 'true'"
    )
    assert "exit 1" in steps[block]["run"]
    credentialed = [
        index
        for index, step in enumerate(steps)
        if "azure/login" in str(step.get("uses", ""))
        or any(
            name.endswith(("_API_KEY", "_TOKEN", "_CLIENT_ID"))
            for name in (step.get("env") or {})
        )
    ]
    assert credentialed
    assert block < min(credentialed)


# ── What the decision opens ────────────────────────────────────────────────


def test_the_variable_is_set_from_the_box_and_never_from_the_block(workflow):
    """The whole point of the gate, and the one place it could leak.

    ``codex_blocked`` is false when the box was ticked *and* when the Ruby did
    not think this was Codex at all. Only the first means somebody decided, so
    the expression reads ``codex_confirmed``. If the two parsers ever disagree,
    this stays empty -- and empty is what
    ``_require_runnable_execution_mode`` refuses on.

    Asserted over every step that starts the entrypoint rather than over
    ``step2a`` alone. Pinning one step by name is what let the checkpoint
    validation ship without the variable for as long as it did: the assertion
    passed, because the step it named was correct.
    """
    reaching = _steps_that_reach_the_gate(workflow)
    assert len(reaching) >= 2, [step.get("name") for step in reaching]
    for step in reaching:
        where = step.get("name") or step.get("id")
        expression = (step.get("env") or {}).get(
            "CODEX_FOUNDRY_CONNECTION_CONFIRMED"
        )
        assert expression is not None, f"{where} can reach the gate and cannot open it"
        assert expression == (
            "${{ steps.read_config.outputs.uses_codex_foundry == 'true' && "
            "needs.inspect-mode.outputs.codex_confirmed == 'true' && '1' || '' }}"
        ), where
        assert "codex_blocked" not in expression, where
    # '1' is not decoration: the reader compares against exactly that.
    source = (ROOT / "batch-runner" / "step2_run_inference.py").read_text(
        encoding="utf-8"
    )
    assert (
        'os.getenv("CODEX_FOUNDRY_CONNECTION_CONFIRMED", "").strip() == "1"'
        in source
    )


def test_the_step_that_only_runs_on_a_handover_carries_it_too(workflow):
    """The omission above, named, because a generic assertion cannot explain it.

    ``Validate restored checkpoint identity`` is guarded by ``relay_run > 0``,
    so a run short enough to finish in one leg never executes it and a suite
    that only ever watched leg 0 never saw it. Run ``34596408490`` is what it
    costs: leg 1 of the 220 reached 45 tasks over five hours and uploaded its
    checkpoint, and leg 2 raised ``codex_foundry has not been shown to reach
    its Foundry deployment`` four minutes later, before reading a byte of it.
    Every retry fails identically, so that lineage cannot be resumed at all.

    At leg 1's rate -- 45 tasks in 301 minutes -- 220 tasks need roughly five
    legs. This step is therefore not on the path of a long run as an extra
    check on it; it is on the only path a long run has.
    """
    step = _named_step(workflow, "Validate restored checkpoint identity")
    assert step["if"] == "inputs.relay_run > 0"
    assert step in _steps_that_reach_the_gate(workflow)
    assert "--validate-checkpoint-only" in step["run"]
    assert "CODEX_FOUNDRY_CONNECTION_CONFIRMED" in step["env"]
    # It validates; it must not also run. A gate variable on a step that spends
    # is a different risk from one on a step that only reads.
    assert "--wall-timeout" not in step["run"]


def test_validating_a_checkpoint_goes_through_the_same_refusal_as_running_one(
    workflow,
):
    """Why the variable is needed there at all, checked in the code not the YAML.

    ``validate_restored_checkpoint`` is documented as running "without
    constructing a model client", which reads like a step that could not
    possibly need permission to spend. It calls the same guard the spending
    path calls, one line in. That is deliberate -- a leg that may not run
    should not be told its checkpoint is fine either -- and it is the reason
    the env block cannot be trimmed to what the step appears to touch.
    """
    source = (ROOT / "batch-runner" / "step2_run_inference.py").read_text(
        encoding="utf-8"
    )
    body = source.split("def validate_restored_checkpoint", 1)[1]
    body = body.split("\ndef ", 1)[0]
    assert "_require_runnable_execution_mode(execution_mode)" in body


def test_the_config_parser_publishes_the_mode_the_expression_reads(workflow):
    read_config = _named_step(workflow, "Read experiment config flags")
    assert '"uses_codex_foundry": str(mode == "codex_foundry").lower()' in (
        read_config["run"]
    )


# ── And every leg after the first ──────────────────────────────────────────


def test_the_relay_forwards_every_input_it_was_given(workflow, dispatch_inputs):
    """Checked for all of them, because the next one added has this bug too.

    A relay leg is the same run continuing. An input that is not forwarded is a
    run that spends on leg 0 and is refused on leg 1 -- worse than either
    outcome on its own, and invisible until it happens.
    """
    relay = _named_step(workflow, "Retrigger relay run")
    forwarded = set(re.findall(r"-f ([a-z_]+)=", relay["run"]))
    assert forwarded == set(dispatch_inputs)


def test_the_relay_forwards_it_through_the_environment(workflow):
    """No step in this workflow interpolates an input into a shell script.

    Pinned here as well as in ``test_agentic_workflows`` because this change
    adds a forwarded value, and a forwarded value is exactly the thing somebody
    would reach for ``${{ inputs. }}`` to write.
    """
    relay = _named_step(workflow, "Retrigger relay run")
    assert '-f codex_foundry_confirmed="$CODEX_FOUNDRY_CONFIRMED_INPUT"' in (
        relay["run"]
    )
    assert workflow["jobs"]["batch-run"]["env"][
        "CODEX_FOUNDRY_CONFIRMED_INPUT"
    ] == "${{ inputs.codex_foundry_confirmed }}"
    assert all(
        "${{ inputs." not in str(step.get("run", ""))
        for job in workflow["jobs"].values()
        for step in job.get("steps", [])
    )
