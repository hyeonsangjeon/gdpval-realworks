"""Offline bootstrap routing: real workflow shell, fake package/probe processes."""

from __future__ import annotations

import itertools
import json
from pathlib import Path
import subprocess
import sys

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/codex-budget-pilot-ci-cell.yml"
INSTALL = "Install the existing native sandbox prerequisite"
REQUIRE = "Require the existing native sandbox prerequisite"
PROBE = "Require the existing native sandbox capability"
EXECUTE_GATE = (
    "success() && inputs.execute && !inputs.input_check && !inputs.output_target_check"
    " && !inputs.output_target_setup && steps.intake.outputs.verified == 'true'"
)
APT_OPTIONS = [
    "-o", "Acquire::Retries=3", "-o", "Acquire::http::Timeout=30",
    "-o", "Acquire::https::Timeout=30", "-o", "DPkg::Lock::Timeout=60",
]


@pytest.fixture
def workflow():
    return yaml.safe_load(WORKFLOW.read_text())


def named(workflow, name):
    return next(step for step in workflow["jobs"]["cell"]["steps"] if step["name"] == name)


def enabled(step, modes, *, success=True, verified="true", admitted=False):
    """Evaluate only the existing closed conjunctions, not a workflow emulator."""
    execute, input_check, target_check, target_setup = modes
    values = {
        "success()": success, "always()": True,
        "inputs.execute": execute, "!inputs.input_check": not input_check,
        "!inputs.output_target_check": not target_check,
        "!inputs.output_target_setup": not target_setup,
        "steps.intake.outputs.verified == 'true'": verified == "true",
        "steps.admission.outputs.admitted == 'true'": admitted,
    }
    return all(values[term] for term in step["if"].split(" && "))


def test_bootstrap_order_guards_and_credential_boundaries(workflow):
    job = workflow["jobs"]["cell"]
    steps = job["steps"]
    by_id = {step.get("id"): step for step in steps}
    install, require, probe = [named(workflow, name) for name in (INSTALL, REQUIRE, PROBE)]
    login = next(step for step in steps if step.get("uses", "").startswith("azure/login@"))
    ordered = [by_id["plan"], by_id["intake"], install, require, probe,
               by_id["admission"], login, by_id["execution"], by_id["retention"]]
    indices = [steps.index(step) for step in ordered]
    assert indices == sorted(indices)
    for step in (install, require, probe, by_id["admission"]):
        assert step["if"] == EXECUTE_GATE
    for step in (install, probe):
        assert step["shell"] == "bash" and step["run"].startswith("set -euo pipefail\n")
        assert "env" not in step and "continue-on-error" not in step
        assert "${{ secrets." not in step["run"]
    assert install["timeout-minutes"] == 12 and probe["timeout-minutes"] == 2
    assert probe["working-directory"] == "batch-runner"
    assert probe["run"] == "set -euo pipefail\npython3 scripts/diagnose_codex_sandbox_host.py\n"
    assert require["run"] == (
        'if ! command -v bwrap >/dev/null; then\n'
        '  echo "codex_bubblewrap_unavailable"\n  exit 1\nfi\n'
    )
    assert workflow["permissions"] == {"contents": "read", "id-token": "write"}
    assert workflow["concurrency"] == {
        "group": "codex-budget-pilot-ci-20260923-01", "cancel-in-progress": False,
    }
    assert job["runs-on"] == "ubuntu-22.04" and job["timeout-minutes"] == 240
    assert "secrets." not in json.dumps(workflow.get("env", {})) + json.dumps(job["env"])
    for forbidden in ("sleep", "for attempt", "|| true", "sysctl", "privileged", "landlock"):
        assert forbidden not in install["run"] + probe["run"]


def test_bootstrap_excludes_nonexecute_conflicting_and_unverified_routes(workflow):
    guarded = [named(workflow, name) for name in (INSTALL, REQUIRE, PROBE)]
    for modes in itertools.product((False, True), repeat=4):
        for success, verified in ((True, "true"), (False, "true"), (True, "false"), (True, "")):
            expected = modes == (True, False, False, False) and success and verified == "true"
            assert all(enabled(step, modes, success=success, verified=verified) == expected
                       for step in guarded)
    triggers = workflow.get("on", workflow.get(True))
    for trigger in triggers.values():
        for mode in ("execute", "input_check", "output_target_check", "output_target_setup"):
            assert trigger["inputs"][mode]["default"] is False


@pytest.mark.parametrize(
    "present,update_rc,install_rc,discover,probe_rc,expected_rc,expected_calls",
    [
        (True, 0, 0, True, 0, 0, ["probe"]),
        (False, 0, 0, True, 0, 0, ["update", "install", "probe"]),
        (False, 100, 0, True, 0, 100, ["update"]),
        (False, 124, 0, True, 0, 124, ["update"]),
        (False, 0, 100, True, 0, 100, ["update", "install"]),
        (False, 0, 124, True, 0, 124, ["update", "install"]),
        (False, 0, 0, False, 0, 1, ["update", "install"]),
        (False, 0, 0, True, 1, 1, ["update", "install", "probe"]),
        (False, 0, 0, True, 2, 2, ["update", "install", "probe"]),
    ],
    ids=["present", "installed", "update-failure", "update-timeout", "install-failure",
         "install-timeout", "binary-still-missing", "sandbox-refused", "probe-error"],
)
def test_bootstrap_shell_failure_gates(
    workflow, tmp_path, present, update_rc, install_rc, discover, probe_rc,
    expected_rc, expected_calls,
):
    # PATH contains only these synthetic executables. Neither sudo/apt nor the
    # real diagnostic can execute; the workflow's actual Bash remains under test.
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    calls_path = tmp_path / "calls.jsonl"
    fake_process = f"#!{sys.executable}\n" + '''\
import json
import os
from pathlib import Path
import sys

args = sys.argv[1:]
kind = "probe" if Path(sys.argv[0]).name == "python3" else ("update" if "update" in args else "install")
with open(os.environ["BOOTSTRAP_CALLS"], "a") as stream:
    stream.write(json.dumps({"kind": kind, "args": args, "cwd": os.getcwd()}) + "\\n")
rc = int(os.environ[kind.upper() + "_RC"])
if kind == "install" and rc == 0 and os.environ["DISCOVER"] == "1":
    binary = Path(os.environ["PATH"]) / "bwrap"
    binary.write_text("#!/bin/bash\\nexit 0\\n")
    binary.chmod(0o700)
raise SystemExit(rc)
'''
    for executable in ("sudo", "python3"):
        path = fake_bin / executable
        path.write_text(fake_process)
        path.chmod(0o700)
    if present:
        binary = fake_bin / "bwrap"
        binary.write_text("#!/bin/bash\nexit 0\n")
        binary.chmod(0o700)
    environment = {
        "PATH": str(fake_bin), "BOOTSTRAP_CALLS": str(calls_path),
        "UPDATE_RC": str(update_rc), "INSTALL_RC": str(install_rc),
        "PROBE_RC": str(probe_rc), "DISCOVER": str(int(discover)),
    }
    success, last_rc, stdout = True, 0, ""
    modes = (True, False, False, False)
    for name in (INSTALL, REQUIRE, PROBE):
        step = named(workflow, name)
        if enabled(step, modes, success=success):
            result = subprocess.run(
                ["/bin/bash", "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", step["run"]],
                cwd=ROOT / step.get("working-directory", "."), env=environment,
                capture_output=True, text=True, timeout=5, check=False,
            )
            last_rc = result.returncode
            success = last_rc == 0
            stdout += result.stdout
    assert last_rc == expected_rc
    calls = [json.loads(line) for line in calls_path.read_text().splitlines()]
    assert [call["kind"] for call in calls] == expected_calls
    for call in calls:
        if call["kind"] == "probe":
            assert call["args"] == ["scripts/diagnose_codex_sandbox_host.py"]
            assert call["cwd"] == str(ROOT / "batch-runner")
        elif call["kind"] == "update":
            assert call["args"] == ["timeout", "--kill-after=5s", "240s", "apt-get", *APT_OPTIONS, "update", "-qq"]
        else:
            assert call["args"] == ["DEBIAN_FRONTEND=noninteractive", "timeout", "--kill-after=5s", "420s",
                                    "apt-get", *APT_OPTIONS, "install", "-y", "--no-install-recommends", "bubblewrap"]
    if not discover:
        assert "codex_bubblewrap_unavailable" in stdout
    # Only evaluate downstream conditions: no claim, OIDC, model or retention
    # command is invoked. Failure cannot acquire admission, even for always().
    steps = workflow["jobs"]["cell"]["steps"]
    by_id = {step.get("id"): step for step in steps}
    admitted = enabled(by_id["admission"], modes, success=success)
    assert admitted is (expected_rc == 0)
    login = next(step for step in steps if step.get("uses", "").startswith("azure/login@"))
    for step in (login, by_id["execution"], by_id["retention"]):
        assert enabled(step, modes, success=success, admitted=admitted) is (expected_rc == 0)
