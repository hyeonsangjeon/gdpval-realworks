"""A batch job that lands outside Azure stops at once and is sent again.

GitHub now places ubuntu-24.04 jobs on AWS as well as on Azure (changelog
2026-10-28). The Azure tenant's Conditional Access refuses an OIDC login from
outside Azure (AADSTS53003), so a leg placed on AWS stopped at Azure Login and
waited for a person: nothing spent, and nothing moving either.

Three properties are pinned here, each a way the fix could cost more than the
stall it replaces.

**Off Azure, nothing runs after the first step.** The verdict is read before
the checkout and before any credential reaches an environment, and every later
step is skipped -- including the three that would otherwise run under
``always()``.

**A misreading can only fall back to today.** The job stops, and is sent
go on only on an AWS answer (Amazon DMI, or an AWS kernel when DMI names
neither cloud); a runner that shows neither goes on and Azure Login decides
as before. An Azure VM never reports Amazon DMI, so it is never sent round
again, and the ceiling bounds even a misreading to twenty short runs that
spend nothing. grade-run.yml's grade job runs the same script.

**The re-send is the same dispatch.** A GitHub re-run is refused by Sol runs
(``GITHUB_RUN_ATTEMPT``), so it is a fresh ``workflow_dispatch`` that names
every input the workflow declares, each unchanged but ``placement_attempt``,
from a job whose token can dispatch and nothing else.
"""

import re
import subprocess
from pathlib import Path

import pytest
import yaml

from .test_a_relay_leg_runs_the_source_it_started_with import _contract


ROOT = Path(__file__).resolve().parents[2]
BATCH_WORKFLOW = ROOT / ".github" / "workflows" / "batch-run.yml"
GRADE_WORKFLOW = ROOT / ".github" / "workflows" / "grade-run.yml"
GUARD = "Refuse a runner outside Azure"
RESEND_JOB = "placement-reroll"
RESEND = "Send the same dispatch again"
CEILING = 20
#: What probe run 44359457502 read on each cloud's ubuntu-24.04 runners.
AZURE = {"vendor": "Microsoft Corporation", "asset_tag": "7783-7084-3265-9085-8269-3286-77",
         "kernel": "7.0.0-1017-azure"}
AWS = {"vendor": "Amazon EC2", "asset_tag": "Amazon EC2", "kernel": "7.0.0-1014-aws"}
GENERIC = "6.8.0-90-generic"


@pytest.fixture(scope="module")
def workflow():
    return yaml.safe_load(BATCH_WORKFLOW.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def dispatch_inputs(workflow):
    # `on` parses as the boolean True, which is why this is not workflow["on"].
    return workflow[True]["workflow_dispatch"]["inputs"]


def _batch_steps(workflow):
    return workflow["jobs"]["batch-run"]["steps"]


def _resend(workflow):
    (step,) = workflow["jobs"][RESEND_JOB]["steps"]
    assert step["name"] == RESEND
    return step


def _written(path):
    if not path.exists():
        return {}
    return dict(line.split("=", 1) for line in path.read_text().splitlines() if "=" in line)


def _guard(workflow, tmp_path, *, vendor, asset_tag, kernel, run_attempt=None):
    """The guard's own script, against a stand-in DMI directory and uname."""
    dmi = tmp_path / "dmi"
    dmi.mkdir()
    for name, value in (("sys_vendor", vendor), ("chassis_asset_tag", asset_tag)):
        if value is not None:
            (dmi / name).write_text(value + "\n")
    tools = tmp_path / "bin"
    tools.mkdir()
    uname = tools / "uname"
    uname.write_text(f"#!/bin/sh\necho '{kernel}'\n")
    uname.chmod(0o755)
    script = _batch_steps(workflow)[0]["run"]
    assert script.count("/sys/class/dmi/id/") == 2
    script = script.replace("/sys/class/dmi/id/", f"{dmi}/")
    output, summary = tmp_path / "output", tmp_path / "summary"
    env = {"PATH": f"{tools}:/usr/bin:/bin", "GITHUB_OUTPUT": str(output),
           "GITHUB_STEP_SUMMARY": str(summary)}
    if run_attempt is not None:
        env["GITHUB_RUN_ATTEMPT"] = run_attempt
    result = subprocess.run(["bash", "-c", script], capture_output=True, text=True, env=env)
    return result, _written(output)


def _send(workflow, tmp_path, *, attempt, run_attempt="1"):
    """The re-send script, with gh and sleep recorded instead of run."""
    tools = tmp_path / "bin"
    tools.mkdir()
    calls = tmp_path / "calls"
    for name in ("gh", "sleep"):
        tool = tools / name
        tool.write_text(f'#!/bin/sh\nprintf "%s\\n" "{name} $*" >> "{calls}"\n')
        tool.chmod(0o755)
    step = _resend(workflow)
    env = {name: value for name, value in step["env"].items() if not value.startswith("${{")}
    env.update({
        "PATH": f"{tools}:/usr/bin:/bin", "GITHUB_RUN_ATTEMPT": run_attempt,
        "GITHUB_REPOSITORY": "owner/repo", "GITHUB_STEP_SUMMARY": str(tmp_path / "summary"),
        "GH_TOKEN": "not-a-token", "EXPERIMENT_YAML_INPUT": "exp039_sol_next98",
        "EXPERIMENT_NAME_INPUT": "", "DRY_RUN_INPUT": "false", "RELAY_RUN_INPUT": "2",
        "RELAY_LINEAGE_ID_INPUT": "exp039:1:1", "SOURCE_SHA_INPUT": "a" * 40,
        "WALL_TIMEOUT_INPUT": "290", "SANDBOX_IMAGE_DIGEST_INPUT": "",
        "CODEX_FOUNDRY_CONFIRMED_INPUT": "true", "COMPARISON_REVIEWED_SOURCE_SHA_INPUT": "",
        "PLACEMENT_ATTEMPT_INPUT": attempt,
    })
    result = subprocess.run(["bash", "-c", step["run"]], capture_output=True, text=True, env=env)
    return result, calls.read_text().splitlines() if calls.exists() else []


# ── The guard ──────────────────────────────────────────────────────────────


def test_the_guard_is_the_first_step_and_holds_nothing(workflow):
    guard = _batch_steps(workflow)[0]
    assert guard["name"] == GUARD and guard["id"] == "placement"
    # No env, no action, no condition and no continue-on-error: it reads two
    # world-readable files and the kernel name, and its failure is final.
    assert set(guard) == {"name", "id", "run"}
    assert "${{" not in guard["run"] and "secrets." not in guard["run"]
    assert _batch_steps(workflow)[1]["name"] == "Checkout"


def test_the_verdict_leaves_the_job_even_when_the_job_fails(workflow):
    assert workflow["jobs"]["batch-run"]["outputs"]["placement"] == (
        "${{ steps.placement.outputs.verdict }}"
    )


def test_off_azure_no_later_step_runs(workflow):
    """A failed first step skips every step with an implicit success().

    The ones that say always() would still run, so each of them must also ask
    that the guard passed. Enumerated, so a status function added later
    without the guard fails here.
    """
    for step in _batch_steps(workflow)[1:]:
        condition = str(step.get("if", ""))
        if re.search(r"\b(always|failure|cancelled)\(\)", condition):
            assert "steps.placement.outcome == 'success'" in condition, step.get("name")


@pytest.mark.parametrize("signs,verdict", [
    (AZURE, "azure"),
    ({**AWS, "vendor": AZURE["vendor"]}, "azure"),
    ({**AWS, "asset_tag": AZURE["asset_tag"]}, "azure"),
    ({**AWS, "kernel": AZURE["kernel"]}, "off-azure"),  # DMI names the machine
    ({"vendor": None, "asset_tag": None, "kernel": AZURE["kernel"]}, "azure"),
    ({"vendor": "  Microsoft Corporation  ", "asset_tag": None, "kernel": GENERIC}, "azure"),
    ({"vendor": "Microsoft", "asset_tag": None, "kernel": AZURE["kernel"]}, "azure"),
    ({**AWS, "vendor": None, "asset_tag": None}, "off-azure"),
    ({**AWS, "kernel": GENERIC}, "off-azure"),
    ({"vendor": None, "asset_tag": None, "kernel": GENERIC}, "unknown"),
    ({"vendor": "Xen", "asset_tag": None, "kernel": GENERIC}, "unknown"),
    (AWS, "off-azure"),
])
def test_only_an_aws_runner_with_no_azure_sign_is_refused(workflow, tmp_path, signs, verdict):
    result, written = _guard(workflow, tmp_path, **signs)
    assert written == {"verdict": verdict}
    assert result.returncode == (1 if verdict == "off-azure" else 0), result.stderr
    if verdict == "off-azure":
        assert "::error::" in result.stdout
        assert "Runner outside Azure" in (tmp_path / "summary").read_text()


@pytest.mark.parametrize("signs", [AZURE, AWS], ids=["azure", "aws"])
def test_a_rerun_is_refused_before_any_verdict(workflow, tmp_path, signs):
    """A re-run of a refused placement would run beside the copy already sent.

    It stops with no verdict, so placement-reroll stays skipped, on either cloud.
    """
    result, written = _guard(workflow, tmp_path, **signs, run_attempt="2")
    assert result.returncode == 1, result.stderr
    assert written == {}
    assert "::error::This is a re-run" in result.stdout


def test_a_first_attempt_goes_on_to_the_verdict(workflow, tmp_path):
    result, written = _guard(workflow, tmp_path, **AZURE, run_attempt="1")
    assert result.returncode == 0, result.stderr
    assert written == {"verdict": "azure"}


# ── The dispatch input ─────────────────────────────────────────────────────


def test_the_count_starts_at_one_and_is_internal(dispatch_inputs):
    setting = dispatch_inputs["placement_attempt"]
    assert (setting["type"], setting["default"], setting["required"]) == ("number", 1, False)
    assert setting["description"].startswith("Internal, set by placement-reroll")
    assert len(dispatch_inputs) <= 25  # GitHub's ceiling for workflow_dispatch


@pytest.mark.parametrize("value,accepted", [
    ("1", True), ("2", True), (str(CEILING), True),
    (str(CEILING + 1), False), ("0", False), ("-1", False), ("01", False), ("", False), ("text", False),
])
def test_the_dispatch_contract_holds_the_count_to_its_ceiling(tmp_path, value, accepted):
    result = _contract(tmp_path, PLACEMENT_ATTEMPT=value)
    assert (result.returncode == 0) is accepted, result.stderr


def test_a_new_relay_leg_starts_counting_again(workflow):
    relay = next(step for step in _batch_steps(workflow) if step.get("name") == "Retrigger relay run")
    assert "-f placement_attempt=1\n" in relay["run"]


# ── The re-send ────────────────────────────────────────────────────────────


def test_the_resend_runs_only_after_a_refused_placement(workflow):
    job = workflow["jobs"][RESEND_JOB]
    assert job["needs"] == "batch-run"
    assert job["if"] == (
        "${{ !cancelled() && needs.batch-run.result == 'failure' && "
        "needs.batch-run.outputs.placement == 'off-azure' }}"
    )
    assert job["runs-on"] == "ubuntu-24.04"
    assert job["timeout-minutes"] * 60 >= 180 + 120  # the longest wait, then the call


def test_the_resend_token_can_dispatch_and_nothing_else(workflow):
    job = workflow["jobs"][RESEND_JOB]
    assert job["permissions"] == {"actions": "write"}
    text = yaml.safe_dump(job)
    assert re.findall(r"secrets\.\w+", text) == ["secrets.GITHUB_TOKEN"]
    assert all("uses" not in step for step in job["steps"])
    assert "azure/login" not in text and "HF_TOKEN" not in text


def test_the_resend_is_the_same_dispatch_with_one_more_attempt(workflow, dispatch_inputs):
    step = _resend(workflow)
    sent = dict(re.findall(r'-f ([a-z_]+)="\$([A-Z_]+)"', step["run"]))
    assert set(sent) == set(dispatch_inputs)
    assert sent.pop("placement_attempt") == "NEXT_ATTEMPT"
    for name, variable in sent.items():
        assert step["env"][variable] == f"${{{{ inputs.{name} }}}}", name
    assert 'gh workflow run batch-run.yml --repo "$GITHUB_REPOSITORY" --ref main' in step["run"]
    assert "${{ inputs." not in step["run"]


def test_both_sides_of_the_ceiling_agree(workflow):
    assert _resend(workflow)["env"]["MAX_PLACEMENTS"] == str(CEILING)
    contract = workflow["jobs"]["inspect-mode"]["steps"][0]
    assert f"(( 10#$PLACEMENT_ATTEMPT <= {CEILING} ))" in contract["run"]


@pytest.mark.parametrize("attempt,wait", [("1", 30), ("4", 120), ("5", 150), ("6", 180), (str(CEILING - 1), 180)])
def test_the_resend_waits_then_sends_the_next_attempt(workflow, tmp_path, attempt, wait):
    result, calls = _send(workflow, tmp_path, attempt=attempt)
    assert result.returncode == 0, result.stderr
    slept = int(calls[0].removeprefix("sleep "))
    assert wait <= slept <= wait + 14  # plus RANDOM % 15 of jitter
    (dispatch,) = calls[1:]
    assert dispatch.startswith("gh workflow run batch-run.yml --repo owner/repo --ref main ")
    assert dispatch.endswith(f" -f placement_attempt={int(attempt) + 1}")
    for forwarded in ("-f relay_run=2 ", "-f relay_lineage_id=exp039:1:1 ",
                      f"-f source_sha={'a' * 40} ", "-f codex_foundry_confirmed=true "):
        assert forwarded in dispatch


@pytest.mark.parametrize("attempt,run_attempt", [(str(CEILING), "1"), ("1", "2")])
def test_the_resend_refuses_past_the_ceiling_or_as_a_rerun(workflow, tmp_path, attempt, run_attempt):
    result, calls = _send(workflow, tmp_path, attempt=attempt, run_attempt=run_attempt)
    assert result.returncode == 1
    assert calls == []
    assert "::error::" in result.stdout


def test_the_grade_job_runs_the_same_guard(workflow):
    grade = yaml.safe_load(GRADE_WORKFLOW.read_text(encoding="utf-8"))
    (guard,) = [step for step in grade["jobs"]["grade"]["steps"] if step.get("id") == "placement"]
    assert guard["name"] == GUARD and guard["run"] == _batch_steps(workflow)[0]["run"]
    reroll = grade["jobs"][RESEND_JOB]["steps"][0]
    assert reroll["env"]["MAX_PLACEMENTS"] == str(CEILING)
