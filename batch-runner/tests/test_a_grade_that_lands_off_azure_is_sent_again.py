"""A paid grade placed on a runner that is not an Azure VM stops and is sent again.

GitHub now places standard Linux jobs on AWS as well as Azure (changelog
2026-10-28). This repository's Azure login is refused there by Conditional
Access (AADSTS53003), so a paid grade that lands on AWS gets past its approval
and then sits failed at the login, before any spend. ``grade-run.yml`` now
reads the VM's DMI and kernel as the grade job's fourth step, stops only on
an AWS sign with no Azure sign, and ``placement-reroll`` sends the identical
request again, at most twenty placements in all.

What this file holds still:

* the check runs before anything that holds a credential, installs, logs in,
  calls a model or writes to main, and stops only on a positive answer;
* the re-sent body is every input exactly as dispatched, with only
  ``placement_attempt`` raised, and the twentieth placement sends nothing;
* the re-send is a fresh dispatch through the relay's own endpoint and token,
  so the approval rules treat it as they treat the relay: a later chunk
  inherits on the unchanged receipt, chunk 0 asks the environment again;
* one cap, stated in three places that agree.

The shipped scripts are run, sliced out of the workflow. Nothing here calls a
model or the network.
"""

from __future__ import annotations

import json
import os
import random
import re
import shutil
import subprocess
import time
from pathlib import Path

import pytest
import yaml

from tests.test_a_smoke_can_name_the_task_it_needs_to_prove import BASELINE
from tests.test_an_unsharded_chunk_inherits_only_its_own_lineage import (
    BOT,
    _decide,
    _grade,
    _partial,
    _step_script,
)
from tests.test_step8_grade import _auto_resume_dispatch

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github/workflows/grade-run.yml"

CHECK = "Refuse a runner outside Azure"
RESEND_JOB = "placement-reroll"
RELAY = "Auto-retrigger next chunk (time budget hit)"
CAP = 20
AZURE_TAG = "7783-7084-3265-9085-8269-3286-77"
GENERIC, AZURE_KERNEL, AWS_KERNEL = "6.8.0-90-generic", "7.0.0-1017-azure", "7.0.0-1014-aws"


def _workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _inputs() -> dict:
    workflow = _workflow()
    return (workflow.get("on") or workflow[True])["workflow_dispatch"]["inputs"]


def _grade_steps() -> list[dict]:
    return _workflow()["jobs"]["grade"]["steps"]


def _step(steps: list[dict], name: str) -> dict:
    (step,) = [step for step in steps if step.get("name") == name]
    return step


def _resend_step() -> dict:
    (step,) = _workflow()["jobs"][RESEND_JOB]["steps"]
    return step


# ── where the check sits ─────────────────────────────────────────────────


def test_the_check_runs_before_anything_that_holds_a_credential_or_spends():
    """Everything before it is container-local; everything after it may cost.

    The three steps ahead of it verify the image, trust the workspace and name
    a temp file. None reads a secret or uses an action. The first step after
    it is the credentialed checkout, and the install, the Azure login, the
    model calls and every push come later still.
    """
    steps = _grade_steps()
    names = [step.get("name") for step in steps]
    check = names.index(CHECK)
    assert names[:check] == [
        "Verify grading container",
        "Trust the checkout inside the container",
        "Name the file that records what this run publishes",
    ]
    for step in steps[:check + 1]:
        dumped = yaml.safe_dump(step)
        assert "uses" not in step and "secrets." not in dumped and "env" not in step, step["name"]
    assert names[check + 1] == "Checkout exact main revision"
    for index, step in enumerate(steps):
        dumped = yaml.safe_dump(step)
        costly = (
            "uses" in step or "secrets." in dumped or "pip install" in dumped
            or "git push" in dumped or "git commit" in dumped
            or "step8_grade.py" in dumped or "sol_batch_grading.py" in dumped
        )
        if costly:
            assert index > check, step.get("name")
    check_step = steps[check]
    assert check_step["id"] == "placement" and "if" not in check_step
    assert "continue-on-error" not in check_step


def _run_check(tmp_path: Path, vendor: str | None, tag: str | None,
               kernel: str = GENERIC, run_attempt: str | None = None) -> tuple[int, str, str]:
    """The shipped script, pointed at a fake DMI directory and a fake uname."""
    script = _step(_grade_steps(), CHECK)["run"]
    assert script.count('"/sys/class/dmi/id/$1"') == 2, "the check reads DMI somewhere new"
    dmi = tmp_path / "dmi"
    dmi.mkdir()
    for name, value in (("sys_vendor", vendor), ("chassis_asset_tag", tag)):
        if value is not None:
            (dmi / name).write_text(value + "\n", encoding="utf-8")
    tools = tmp_path / "bin"
    tools.mkdir()
    (tools / "uname").write_text(f"#!/bin/sh\necho '{kernel}'\n", encoding="utf-8")
    (tools / "uname").chmod(0o755)
    output = tmp_path / "github_output"
    output.write_text("", encoding="utf-8")
    env = {"PATH": f"{tools}:" + os.environ.get("PATH", "/usr/bin:/bin"), "GITHUB_OUTPUT": str(output),
           "GITHUB_STEP_SUMMARY": str(tmp_path / "summary")}
    if run_attempt is not None:
        env["GITHUB_RUN_ATTEMPT"] = run_attempt
    done = subprocess.run(
        [shutil.which("bash") or "bash", "-e", "-c", script.replace("/sys/class/dmi/id/", f"{dmi}/")],
        env=env, capture_output=True, text=True, timeout=30,
    )
    return done.returncode, output.read_text(encoding="utf-8"), done.stdout + done.stderr


@pytest.mark.parametrize(("vendor", "tag", "kernel", "verdict", "code"), [
    ("Microsoft Corporation", AZURE_TAG, AZURE_KERNEL, "azure", 0),
    ("  Microsoft Corporation  ", None, GENERIC, "azure", 0),      # padded firmware value
    ("Microsoft Corporation", "None", GENERIC, "azure", 0),        # Hyper-V without Azure's tag
    ("Microsoft", None, AZURE_KERNEL, "azure", 0),                 # the kernel is enough
    ("Amazon EC2", "Amazon EC2", AZURE_KERNEL, "off-azure", 1),      # DMI names the machine
    ("Amazon EC2", AZURE_TAG, AWS_KERNEL, "azure", 0),             # any Azure sign carries on
    ("Amazon EC2", "Amazon EC2", AWS_KERNEL, "off-azure", 1),
    ("Amazon EC2", None, GENERIC, "off-azure", 1),
    (None, None, AWS_KERNEL, "off-azure", 1),                       # DMI unreadable, AWS kernel
    ("", "Amazon EC2", GENERIC, "off-azure", 1),
    ("Xen", None, GENERIC, "unknown", 0),                          # neither cloud: the login decides
    (None, None, GENERIC, "unknown", 0),
    ("", AZURE_TAG, GENERIC, "azure", 0),
], ids=["azure", "padded", "hyper-v", "azure-kernel", "aws-dmi-azure-kernel", "tag-only", "aws", "aws-vendor", "aws-kernel",
        "aws-tag", "xen", "unreadable", "tag-no-vendor"])
def test_only_an_aws_sign_stops_the_job(tmp_path, vendor, tag, kernel, verdict, code):
    """A false "not Azure" sends a request again that may have run; a false
    "Azure" fails at the login exactly as it did before. So doubt carries on."""
    returncode, output, log = _run_check(tmp_path, vendor, tag, kernel)
    assert returncode == code, log
    assert output.splitlines() == [f"verdict={verdict}"], log
    if verdict == "off-azure":
        assert "::error::" in log and RESEND_JOB in log
    if verdict == "unknown":
        assert "::warning::" in log


@pytest.mark.parametrize(("vendor", "tag", "kernel"), [
    ("Microsoft Corporation", AZURE_TAG, AZURE_KERNEL),
    ("Amazon EC2", "Amazon EC2", AWS_KERNEL),
], ids=["azure", "aws"])
def test_a_rerun_is_refused_before_any_verdict(tmp_path, vendor, tag, kernel):
    """A re-run reuses the first attempt's approval and would run beside the
    copy placement-reroll sent; it stops with no verdict, so nothing is re-sent."""
    returncode, output, log = _run_check(tmp_path, vendor, tag, kernel, run_attempt="2")
    assert returncode == 1, log
    assert output == "", log
    assert "::error::This is a re-run" in log


def test_the_verdict_survives_the_failure_it_causes():
    """Written to GITHUB_OUTPUT before `exit 1`, and published as a job output."""
    grade = _workflow()["jobs"]["grade"]
    assert grade["outputs"]["placement"] == "${{ steps.placement.outputs.verdict }}"
    script = _step(grade["steps"], CHECK)["run"]
    off = script[script.index('echo "verdict=off-azure"'):]
    assert off.index('echo "verdict=off-azure"') < off.index("exit 1")


# ── the re-send ──────────────────────────────────────────────────────────


def test_the_resend_job_can_dispatch_and_nothing_else():
    job = _workflow()["jobs"][RESEND_JOB]
    assert job["needs"] == ["grade"]
    condition = " ".join(str(job["if"]).removeprefix("${{").removesuffix("}}").split())
    assert condition == (
        "!cancelled() && github.run_attempt == '1' && "
        "!startsWith(inputs.experiment_yaml, 'pilot/') && "
        "!startsWith(inputs.experiment_yaml, 'retention/') && "
        "needs.grade.result == 'failure' && "
        "needs.grade.outputs.placement == 'off-azure'"
    )
    # Not a money job: test_grader_hash_freeze refuses any job gated on
    # dry_run == false whose name the freeze check would not recognise.
    assert "dry_run" not in condition and "name" not in job
    assert job["permissions"] == {"contents": "read", "actions": "write"}
    assert job["runs-on"] == "ubuntu-24.04" and job["timeout-minutes"] == 10
    dumped = yaml.safe_dump(job)
    for forbidden in ("environment", "id-token", "azure/login", "actions/checkout", "continue-on-error",
                      "HF_TOKEN", "AZURE_", "FOUNDRY"):
        assert forbidden not in dumped, forbidden
    assert re.findall(r"secrets\.\w+", dumped) == ["secrets.GITHUB_TOKEN"]


def test_the_resend_posts_where_the_relay_posts_with_the_same_token():
    """Same endpoint, same token kind: so the new run's actor and triggering
    actor are github-actions[bot], which is what inheritance requires."""
    relay = _step(_grade_steps(), RELAY)
    resend = _resend_step()
    assert resend["env"]["GH_TOKEN"] == relay["env"]["GH_TOKEN"] == "${{ secrets.GITHUB_TOKEN }}"
    for fragment in (
        "curl --fail-with-body --silent --show-error",
        '--header "Authorization: Bearer $GH_TOKEN"',
        '"$GITHUB_API_URL/repos/$GITHUB_REPOSITORY/actions/workflows/grade-run.yml/dispatches"',
    ):
        assert fragment in relay["run"] and fragment in resend["run"], fragment
    assert "gh workflow run" not in resend["run"] and "rerun" not in resend["run"]


def _dispatched(**overrides) -> dict:
    """What toJSON(inputs) hands the job: every declared input, typed."""
    values = {}
    for name, declared in _inputs().items():
        default = declared.get("default")
        values[name] = default if default is not None else ""
    values.update(experiment_yaml="exp039_sol_next98", grading_config="exp039_v2_sol_max.yaml",
                  inference_revision="a" * 40, dry_run=False, paid_approval=True, resume=True,
                  resume_chunk=3, shard_count=1, shard_index=0)
    values.update(overrides)
    return values


def _builder() -> str:
    run = _resend_step()["run"]
    lines = run.splitlines()
    start = lines.index("python3 - <<'PY'")
    end = lines.index("PY", start)
    return "\n".join(lines[start + 1:end])


def _send(tmp_path, monkeypatch, dispatched: dict) -> tuple[dict | None, list[float]]:
    slept: list[float] = []
    monkeypatch.setattr(time, "sleep", slept.append)
    monkeypatch.setattr(random, "randrange", lambda stop: stop - 1)
    monkeypatch.setenv("DISPATCHED_INPUTS", json.dumps(dispatched))
    monkeypatch.setenv("MAX_PLACEMENTS", _resend_step()["env"]["MAX_PLACEMENTS"])
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path))
    monkeypatch.setenv("GITHUB_REF_NAME", "main")
    exec(compile(_builder(), f"{WORKFLOW.name}:{RESEND_JOB}", "exec"), {"__name__": "__main__"})
    body = tmp_path / "placement.json"
    return (json.loads(body.read_text(encoding="utf-8")) if body.exists() else None), slept


@pytest.mark.parametrize("attempt", range(1, CAP))
def test_the_resend_is_the_same_request_one_placement_later(tmp_path, monkeypatch, attempt):
    dispatched = _dispatched(placement_attempt=attempt)
    body, slept = _send(tmp_path, monkeypatch, dispatched)
    assert body["ref"] == "main"
    assert set(body["inputs"]) == set(_inputs()), "every declared input, and nothing else"
    assert all(isinstance(value, str) for value in body["inputs"].values())
    assert body["inputs"].pop("placement_attempt") == str(attempt + 1)
    expected = {
        name: ("true" if value else "false") if isinstance(value, bool) else str(value)
        for name, value in dispatched.items() if name != "placement_attempt"
    }
    assert body["inputs"] == expected
    assert slept == [min(30 * attempt, 180) + 14]


def test_the_resend_takes_github_numbers_however_they_are_spelled(tmp_path, monkeypatch):
    body, _ = _send(tmp_path, monkeypatch, _dispatched(resume_chunk=3.0, placement_attempt=2.0))
    assert body["inputs"]["resume_chunk"] == "3" and body["inputs"]["placement_attempt"] == "3"
    body, _ = _send(tmp_path, monkeypatch, _dispatched(resume_chunk="3", placement_attempt="2"))
    assert body["inputs"]["resume_chunk"] == "3" and body["inputs"]["placement_attempt"] == "3"


def test_the_resend_keeps_the_live_shape_of_the_context(tmp_path, monkeypatch):
    """The shape test_codex_budget_pilot_approval_inputs captured from a real
    run: numbers as strings, booleans as booleans, an empty `tasks` absent.
    What is absent stays absent, so the new run takes the same default."""
    live = {"experiment_yaml": "exp039_sol_next98", "inference_revision": "a" * 40,
            "grading_config": "exp039_v2_sol_max.yaml", "force": False, "tasks_limit": "0",
            "dry_run": False, "paid_approval": True, "resume": True, "resume_chunk": "3",
            "shard_count": "1", "shard_index": "0", "run_ordinal": "1"}
    body, _ = _send(tmp_path, monkeypatch, live)
    assert body["inputs"] == {**{name: ("true" if value is True else "false" if value is False else value)
                                 for name, value in live.items()}, "placement_attempt": "2"}
    assert "tasks" not in body["inputs"]


def test_a_context_without_the_counter_is_the_first_placement(tmp_path, monkeypatch):
    dispatched = _dispatched()
    del dispatched["placement_attempt"]
    body, slept = _send(tmp_path, monkeypatch, dispatched)
    assert body["inputs"]["placement_attempt"] == "2" and slept == [30 + 14]


@pytest.mark.parametrize("attempt", [CAP, CAP + 1, 0])
def test_the_last_placement_sends_nothing(tmp_path, monkeypatch, capsys, attempt):
    with pytest.raises(SystemExit) as stopped:
        _send(tmp_path, monkeypatch, _dispatched(placement_attempt=attempt))
    assert stopped.value.code == 1
    assert not (tmp_path / "placement.json").exists()
    assert "not sending again" in capsys.readouterr().out


def test_an_input_of_an_unknown_shape_sends_nothing(tmp_path, monkeypatch):
    with pytest.raises(SystemExit):
        _send(tmp_path, monkeypatch, _dispatched(tasks=["not", "a", "string"]))
    assert not (tmp_path / "placement.json").exists()


# ── what the approval rules make of it ───────────────────────────────────


def test_the_inheritance_check_cannot_tell_a_resend_from_the_relays_own_dispatch():
    """It reads neither the placement nor the run, only main and the actor."""
    script = _step_script()
    assert "PLACEMENT" not in script.upper()
    assert "GITHUB_RUN_ID" not in script and "GITHUB_RUN_ATTEMPT" not in script


def test_a_resent_later_chunk_inherits_on_the_receipt_the_stopped_run_left_alone(tmp_path):
    """The stopped run wrote nothing, so chunk N-1's partial is still last."""
    files = {_grade(): [BOT, _partial(0)]}
    decided, reason = _decide(tmp_path, files, GRADE_PLACEMENT_ATTEMPT="2")
    assert decided == "true", reason


def test_a_resent_chunk_zero_asks_the_environment_again(tmp_path):
    decided, reason = _decide(tmp_path, {}, GRADE_RESUME="false", GRADE_RESUME_CHUNK="0",
                              GRADE_PLACEMENT_ATTEMPT="2")
    assert decided == "false" and "chunk 0 is the click that authorizes the corpus" in reason


def test_the_approval_card_names_the_placement():
    """A re-sent chunk 0 asks again; the owner should see why."""
    name = _workflow()["jobs"]["approve-paid"]["name"]
    assert name.endswith(", placement ${{ inputs.placement_attempt }})")


def test_a_resent_request_queues_behind_the_run_that_sent_it():
    concurrency = _workflow()["concurrency"]
    assert "placement_attempt" not in concurrency["group"]
    assert concurrency["cancel-in-progress"] is False


def test_the_chunk_relay_starts_each_chunk_at_placement_one():
    assert _auto_resume_dispatch(_step(_grade_steps(), RELAY)["run"])["inputs"]["placement_attempt"] == "1"


def _pilot_digest(tmp_path, monkeypatch, inputs) -> str:
    """The current pilot-approve-paid binding, run on this file's bytes.

    test_codex_budget_pilot_approval_inputs runs the same script, but reads
    the workflow through pilot.ROOT, which conftest's historical_budget_source
    points at commit 8ac891e3's archive -- so it cannot see this change.
    """
    (bind,) = _workflow()["jobs"]["pilot-approve-paid"]["steps"]
    script = bind["run"].removeprefix("python3 - <<'PY'\n").removesuffix("PY\n")
    destination = tmp_path / "approval-output"
    destination.unlink(missing_ok=True)
    controller = "d" * 40
    for key, value in {
        "GITHUB_SHA": controller, "PILOT_WORKFLOW_SHA": controller,
        "GITHUB_REPOSITORY": "hyeonsangjeon/gdpval-realworks", "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REF": "refs/heads/main", "GITHUB_RUN_ATTEMPT": "1", "GITHUB_RUN_ID": "12345",
        "GITHUB_OUTPUT": str(destination), "PILOT_GRADE_INPUTS_JSON": json.dumps(inputs),
    }.items():
        monkeypatch.setenv(key, value)
    exec(compile(script, "<pilot-approve-paid>", "exec"), {})
    line = destination.read_text(encoding="utf-8").strip()
    assert re.fullmatch(r"request_sha256=[0-9a-f]{64}", line)
    return line.split("=", 1)[1]


def test_a_pilot_is_never_sent_again_and_its_approval_digest_ignores_the_counter(tmp_path, monkeypatch):
    """pilot-approve-paid binds toJSON(inputs), which now carries the counter
    on every dispatch. Only the default passes, and the digest pilot-live
    recomputes (codex_budget_pilot_grading._approval_request_sha256, which
    names thirteen inputs) is the one it was before."""
    import codex_budget_pilot_grading as connector

    condition = str(_workflow()["jobs"][RESEND_JOB]["if"])
    assert "!startsWith(inputs.experiment_yaml, 'pilot/')" in condition
    assert "!startsWith(inputs.experiment_yaml, 'retention/')" in condition
    # The captured live shape from test_codex_budget_pilot_approval_inputs.
    selector = "pilot/" + connector.RETAINED_CELL
    live = {"experiment_yaml": selector, "inference_revision": connector.RETAINED_TERMINAL,
            "grading_config": "default_v2_sol_max.yaml", "force": False, "tasks_limit": "0",
            "dry_run": False, "paid_approval": True, "resume": False, "resume_chunk": "0",
            "shard_count": "1", "shard_index": "0", "run_ordinal": "1"}
    expected = connector._approval_request_sha256(
        "d" * 40, selector, connector.RETAINED_TERMINAL, {"id": "12345", "attempt": 1},
        producer_source_sha=connector.RETAINED_PRODUCER_SOURCE)
    for placement in (None, "1", 1):
        inputs = dict(live) if placement is None else {**live, "placement_attempt": placement}
        assert _pilot_digest(tmp_path, monkeypatch, inputs) == expected, placement
    for placement in ("2", 2, True, 1.0, "01", None):
        inputs = {**live, "placement_attempt": placement}
        with pytest.raises(SystemExit) as refused:
            _pilot_digest(tmp_path, monkeypatch, inputs)
        assert refused.value.code == "pilot_grade_approval_inputs_refused", placement


# ── one cap ──────────────────────────────────────────────────────────────


def test_the_cap_is_twenty_everywhere_it_is_stated():
    declared = _inputs()["placement_attempt"]
    assert declared["type"] == "number" and declared["default"] == 1 and declared["required"] is False
    assert f"at most {CAP}" in declared["description"]
    assert _resend_step()["env"]["MAX_PLACEMENTS"] == str(CAP)
    validate = _workflow()["jobs"]["validate-request"]
    assert validate["env"]["GRADE_PLACEMENT_ATTEMPT"] == "${{ inputs.placement_attempt }}"
    (step,) = [step for step in validate["steps"] if step.get("name") == "Validate workflow context and inputs"]
    assert f"placement_attempt must be an integer between 1 and {CAP}" in step["run"]


@pytest.mark.parametrize(("value", "accepted"), [
    ("1", True), ("2", True), (str(CAP), True),
    ("0", False), (str(CAP + 1), False), ("01", False), ("-1", False), ("", False), ("1.5", False),
    ("19", True), ("10", True),
])
def test_validation_accepts_exactly_the_placements_the_job_can_send(value, accepted, tmp_path):
    validate = _workflow()["jobs"]["validate-request"]
    (step,) = [step for step in validate["steps"] if step.get("name") == "Validate workflow context and inputs"]
    done = subprocess.run(
        ["bash", "-c", step["run"]], capture_output=True, text=True,
        env={**BASELINE, "GRADE_PLACEMENT_ATTEMPT": value, "GITHUB_OUTPUT": str(tmp_path / "out")},
    )
    assert (done.returncode == 0) is accepted, done.stdout + done.stderr
    if not accepted:
        assert "placement_attempt must be an integer between 1 and" in done.stdout


def test_the_dispatch_form_has_room_for_the_input():
    """workflow_dispatch takes at most 25 inputs; this one is the fourteenth."""
    assert "placement_attempt" in _inputs() and len(_inputs()) <= 25
