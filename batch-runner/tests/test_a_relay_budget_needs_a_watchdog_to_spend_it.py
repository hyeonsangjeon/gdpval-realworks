"""A relay budget with no watchdog to spend it is refused at dispatch.

`batch-run.yml` validates `execution.wall_timeout` and
`execution.relay_max_runs` separately, and separately each is fine. A zero
watchdog is the documented way to turn the clock off; a relay budget is the
documented way to permit more legs. The combination is a trap, and because
nothing looks at the pair, it passes.

What the trap costs was measured rather than argued. The watchdog is what ends
a leg early enough to save its work and hand over. With it off, condition_a
runs until GitHub's 350 minute step cap kills the shell; `echo "exit_code=..."`
never runs, so the step output is empty; `relay_checkpoint.py status
--exit-code ''` exits non-zero on an empty value; `needs_relay` is therefore
never set; and the checkpoint upload step is gated on `needs_relay == 'true'`.
Every task the leg completed dies with the runner. The budget is unspendable
and the run is lost.

These tests **execute** the workflow step rather than reading it. The repo's
existing workflow tests -- `test_agentic_workflows.py`, and
`test_a_batch_dispatch_can_open_the_codex_gate.py` -- pull the `run:` string
out and assert that substrings appear in it, which proves a spelling and not a
behaviour: a guard that is present but inverted, or shadowed by an earlier
`raise`, passes every one of those assertions. Here the inline `python3`
heredoc is extracted, dedented, and run in a synthetic checkout with a
synthetic dispatch environment, and the assertion is on its exit status. The
script turns out to be entirely offline -- YAML, `ExperimentConfig`, a repo-id
validator, a route table, and a write to `GITHUB_OUTPUT` -- so this costs
nothing and reaches nothing.

That matters most for one line in particular. The guard restates step 2a's
resolution rule (a non-zero dispatch input wins, zero falls back to the YAML)
instead of importing it, because the two live in different languages. A
restatement can drift from the thing it restates. Executing both sides of the
matrix here means a drift fails an assertion instead of ageing quietly into a
comment.

What this does not test: whether the relay itself works. That is
`test_relay_duration.py` and the checkpoint tests. This is only about refusing
a dispatch that has asked for legs it could never take.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
BATCH_WORKFLOW = ROOT / ".github" / "workflows" / "batch-run.yml"
CORE = ROOT / "batch-runner" / "core"
# The documented minimal experiment, used as a known-valid base so the fixture
# below changes one thing at a time. Its mode is irrelevant: the watchdog and
# the relay budget are not mode-specific.
BASE_EXPERIMENT = (
    ROOT / "batch-runner" / "experiments" / "exp998_smoke_baseline_sample.yaml"
)


def _config_script() -> str:
    """The inline python from the `Read experiment config flags` step."""
    document = yaml.safe_load(BATCH_WORKFLOW.read_text(encoding="utf-8"))
    steps = document["jobs"]["batch-run"]["steps"]
    step = next(
        item
        for item in steps
        if item.get("name") == "Read experiment config flags"
    )
    lines = step["run"].splitlines()
    start = next(
        index
        for index, line in enumerate(lines)
        if line.strip().startswith("python3 <<")
    )
    end = next(
        index
        for index in range(len(lines) - 1, start, -1)
        if lines[index].strip() == "PY"
    )
    body = textwrap.dedent("\n".join(lines[start + 1 : end]))
    assert body.strip(), "the step's heredoc did not extract"
    return body


def dispatch(
    tmp_path: Path,
    *,
    wall_timeout_input: str,
    relay_max_runs: object = "absent",
    wall_timeout: object = "absent",
) -> subprocess.CompletedProcess:
    """Run the step against a synthetic checkout and dispatch environment.

    ``"absent"`` means the key is not written at all, which is a different
    input from writing a zero -- the whole point of the guard is that an
    explicit number and an unrequested default are treated differently.

    ``core`` is symlinked rather than copied so the script's
    ``sys.path.insert(0, "batch-runner")`` resolves, and so nothing is ever
    written inside the real tree.
    """
    (tmp_path / "batch-runner" / "experiments").mkdir(parents=True)
    os.symlink(CORE, tmp_path / "batch-runner" / "core")

    config = yaml.safe_load(BASE_EXPERIMENT.read_text(encoding="utf-8"))
    execution = config.setdefault("execution", {})
    for key, value in (
        ("relay_max_runs", relay_max_runs),
        ("wall_timeout", wall_timeout),
    ):
        if value == "absent":
            execution.pop(key, None)
        else:
            execution[key] = value
    (tmp_path / "batch-runner" / "experiments" / "fixture.yaml").write_text(
        yaml.safe_dump(config), encoding="utf-8"
    )

    script = tmp_path / "read_config.py"
    script.write_text(_config_script(), encoding="utf-8")
    github_output = tmp_path / "github_output"
    github_output.write_text("", encoding="utf-8")

    return subprocess.run(
        [sys.executable, script.name],
        cwd=tmp_path,
        env={
            **os.environ,
            "EXPERIMENT_YAML_INPUT": "fixture",
            "WALL_TIMEOUT_INPUT": wall_timeout_input,
            "GITHUB_OUTPUT": str(github_output),
        },
        capture_output=True,
        text=True,
    )


# --- the combination that is refused ------------------------------------


def test_an_explicit_budget_with_no_watchdog_either_side_is_refused(tmp_path):
    """The trap itself: six legs asked for, nothing able to end a leg."""
    result = dispatch(
        tmp_path, wall_timeout_input="0", relay_max_runs=6, wall_timeout=0
    )
    assert result.returncode != 0
    assert "execution.relay_max_runs is 6" in result.stderr
    assert "watchdog is 0 minutes" in result.stderr
    # The reader has to be told which of the two to change, because either
    # will do and the right one depends on what they meant.
    assert "wall_timeout dispatch input" in result.stderr
    assert "execution.relay_max_runs to 0" in result.stderr


def test_the_yaml_being_silent_is_not_a_watchdog(tmp_path):
    """Thirty-six of thirty-six experiments declare no `wall_timeout`.

    So the fallback the dispatch input falls back *to* is, in practice,
    always absent. An omitted key must read the same as a zero here.
    """
    result = dispatch(tmp_path, wall_timeout_input="0", relay_max_runs=6)
    assert result.returncode != 0
    assert "execution.wall_timeout 0" in result.stderr


# --- the combinations that are not ---------------------------------------


def test_the_dispatch_default_arms_the_watchdog_and_the_budget_stands(tmp_path):
    """290 is the input's declared default, so this is the ordinary case.

    exp034 carries `relay_max_runs: 6` and no `wall_timeout`, and it must keep
    dispatching. A guard that rejected this would block every real run.
    """
    result = dispatch(
        tmp_path, wall_timeout_input="290", relay_max_runs=6, wall_timeout=0
    )
    assert result.returncode == 0, result.stderr


def test_an_unrequested_default_budget_does_not_block_a_disabled_watchdog(
    tmp_path,
):
    """`relay_max_runs` defaults to three with nobody having typed it.

    Turning the watchdog off is documented -- the input's own description says
    "disabled only when both are 0". Firing on the default would make that
    documented path impossible for every experiment in the tree, which is a
    larger breakage than the one being prevented.
    """
    result = dispatch(tmp_path, wall_timeout_input="0", wall_timeout=0)
    assert result.returncode == 0, result.stderr


def test_a_yaml_watchdog_satisfies_the_guard_when_the_input_is_zero(tmp_path):
    """This is the fallback working as designed, and it must not be refused.

    It is also the case that pins the restated resolution rule: if the guard
    read the input alone it would refuse here, and step 2a would then have
    armed a watchdog for a run that was never allowed to start.
    """
    result = dispatch(
        tmp_path, wall_timeout_input="0", relay_max_runs=6, wall_timeout=120
    )
    assert result.returncode == 0, result.stderr


def test_declining_the_budget_outright_is_allowed_with_no_watchdog(tmp_path):
    """Zero legs and no clock is coherent: one leg, and it either finishes
    inside the step cap or it does not."""
    result = dispatch(
        tmp_path, wall_timeout_input="0", relay_max_runs=0, wall_timeout=0
    )
    assert result.returncode == 0, result.stderr


# --- the input itself -----------------------------------------------------


@pytest.mark.parametrize("value", ["", "29O", "290.0", "-1", " 290"])
def test_an_uninterpretable_input_is_refused_rather_than_read_as_zero(
    tmp_path, value
):
    """Reading an unparseable input as 0 would arm nothing and refuse nothing.

    Step 2a already applies exactly this test (`^[0-9]+$`) and exits 1 on a
    miss, so nothing new is rejected here -- the rejection just moves earlier,
    to before the job has installed anything or touched a credential, which is
    the direction it should move in.
    """
    result = dispatch(
        tmp_path, wall_timeout_input=value, relay_max_runs=6, wall_timeout=0
    )
    assert result.returncode != 0
    assert "not a decimal integer" in result.stderr


# --- the step still does its original job --------------------------------


def test_the_step_still_emits_the_outputs_the_rest_of_the_job_reads(tmp_path):
    """A guard inserted mid-script can truncate what follows it.

    Nothing downstream would notice immediately: the outputs would simply be
    empty strings, and several consumers treat empty as false.
    """
    (tmp_path / "batch-runner" / "experiments").mkdir(parents=True)
    os.symlink(CORE, tmp_path / "batch-runner" / "core")
    config = yaml.safe_load(BASE_EXPERIMENT.read_text(encoding="utf-8"))
    config.setdefault("execution", {})["relay_max_runs"] = 6
    (tmp_path / "batch-runner" / "experiments" / "fixture.yaml").write_text(
        yaml.safe_dump(config), encoding="utf-8"
    )
    script = tmp_path / "read_config.py"
    script.write_text(_config_script(), encoding="utf-8")
    github_output = tmp_path / "github_output"
    github_output.write_text("", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, script.name],
        cwd=tmp_path,
        env={
            **os.environ,
            "EXPERIMENT_YAML_INPUT": "fixture",
            "WALL_TIMEOUT_INPUT": "290",
            "GITHUB_OUTPUT": str(github_output),
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    emitted = dict(
        line.split("=", 1)
        for line in github_output.read_text(encoding="utf-8").splitlines()
        if "=" in line
    )
    for key in (
        "install_libreoffice",
        "wall_timeout",
        "relay_max_runs",
        "source_repo",
        "uses_sandbox",
        "sandbox_image",
        "uses_agentic",
        "uses_code_interpreter",
        "uses_codex_foundry",
        "azure_ai_workloads_json",
    ):
        assert key in emitted, f"{key} stopped being emitted"
    # `wall_timeout` is still the YAML's value, not the resolved one. Step 2a
    # resolves; this step reports what the file said, and changing that would
    # change the meaning of an output other steps already consume.
    assert emitted["relay_max_runs"] == "6"
    assert emitted["wall_timeout"] == "0"
