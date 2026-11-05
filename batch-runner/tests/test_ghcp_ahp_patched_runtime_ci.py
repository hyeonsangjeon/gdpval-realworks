"""Branch-only offline CI registration; no host, source build, or model client."""

import ast
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/ghcp-ahp-patched-runtime-tests.yml"
BRANCH = "leader/ghcp-patched-runtime-receipt-20261106"
SUITE = [
    "tests/test_ghcp_ahp_patched_runtime.py",
    "tests/test_ghcp_ahp_patched_runtime_rejections.py",
    "tests/test_ghcp_sol_actions_gate.py", "tests/test_ghcp_sol_paid_gate.py",
    "tests/test_ghcp_ahp_probe.py", "tests/test_ghcp_ahp_client.py",
    "tests/test_ghcp_ahp_wire_capture.py", "tests/test_ghcp_ahp_zero_turn.py",
    "tests/test_ghcp_ahp_metadata_broker.py", "tests/test_ghcp_ahp_connection.py",
]
EXPECTED_COUNTS = {"contracts.xml": 1477, "workflow-guards.xml": 25}
ORIGINAL_WORKFLOWS = {
    "ghcp-ahp-model-free-probe.yml": "445773c48f96cc0e1eb435e4f9be504f8bbffb5d17671826a07c0af78e80d176",
    "backend-tests.yml": "a2e0e2fe0451b905ab7d2eddd163f9c87b25eede7a6f7e383cb42b3722687664",
    "agentic-v2-ghcp-sol-gate.yml": "bf862ff51934fbff926340b0b52fa30e75ce175357816199d8c3526730d92b1d",
    "ghcp-ahp-patched-host-build-draft.yml": "e6e16a01cff4a23c92db6b7194aec50eb639936222e3bbcb0a9c68569b767140",
}


def workflow():
    return yaml.load(WORKFLOW.read_text(), Loader=yaml.BaseLoader)


def steps():
    return {item["id"]: item for item in workflow()["jobs"]["contracts"]["steps"]}


def pytest_args(step):
    command = step["run"].replace("\\\n", " ")
    assert command.count(" -m pytest ") == 1
    return shlex.split(command.partition(" -m pytest ")[2])


def result_program():
    command = steps()["results"]["run"]
    assert command.count("<<'PY'\n") == 1
    source = command.split("<<'PY'\n", 1)[1]
    assert source.endswith("\nPY\n")
    source = source.removesuffix("PY\n")
    ast.parse(source)
    return source


def make_reports(tmp_path):
    directory = tmp_path / "ghcp-patched-ci"
    directory.mkdir()
    for name, count in EXPECTED_COUNTS.items():
        root = ET.Element("testsuites")
        suite = ET.SubElement(root, "testsuite", tests=str(count), failures="0", errors="0", skipped="0")
        for index in range(count):
            ET.SubElement(suite, "testcase", name=f"synthetic_{index}")
        ET.ElementTree(root).write(directory / name, encoding="utf-8", xml_declaration=True)
    return directory


def run_result_program(tmp_path):
    return subprocess.run([sys.executable, "-B", "-c", result_program()],
        env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "RUNNER_TEMP": str(tmp_path)},
        capture_output=True, text=True, timeout=15)


def test_workflow_runs_only_on_the_named_branch_push():
    value = workflow()
    assert set(value) == {"name", "on", "permissions", "concurrency", "jobs"}
    assert value["on"] == {"push": {"branches": [BRANCH]}}
    assert value["permissions"] == {"contents": "read"}
    assert value["concurrency"] == {"group": "ghcp-patched-runtime-tests-${{ github.ref }}", "cancel-in-progress": "false"}
    assert set(value["jobs"]) == {"contracts"}
    job = value["jobs"]["contracts"]
    assert set(job) == {"name", "if", "runs-on", "timeout-minutes", "steps"}
    assert job["if"] == f"github.event_name == 'push' && github.ref == 'refs/heads/{BRANCH}'"
    assert job["runs-on"] == "ubuntu-24.04" and job["timeout-minutes"] == "15"


def test_only_pinned_setup_actions_without_authentication_or_runtime_steps():
    selected = steps()
    assert list(selected) == ["checkout", "python", "node", "dependencies", "workflow_guards", "contracts", "results", "artifacts"]
    actions = {key: value["uses"] for key, value in selected.items() if "uses" in value}
    assert actions == {
        "checkout": "actions/checkout@fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09",
        "python": "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97",
        "node": "actions/setup-node@820762786026740c76f36085b0efc47a31fe5020",
        "artifacts": "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",
    }
    assert selected["checkout"]["with"] == {"persist-credentials": "false"}
    assert selected["python"]["with"] == {"python-version": "3.12.11"}
    assert selected["node"]["with"] == {"node-version": "22.23.2", "package-manager-cache": "false"}
    assert selected["dependencies"]["env"] == {"PIP_CONFIG_FILE": "/dev/null"}
    assert selected["dependencies"]["run"] == "python -m pip install --disable-pip-version-check pytest==9.1.1 PyYAML==6.0.3"
    text = WORKFLOW.read_text()
    for forbidden in ("secrets.", "GITHUB_TOKEN", "COPILOT_GITHUB_TOKEN", "workflow_dispatch", "workflow_call",
                      "continue-on-error", "|| true", "gh workflow", "gh run", "typecheck", "npm ",
                      "batch-runner/ghcp_ahp_probe.py", "--execute-paid", "--authenticated-zero-turn", "--session-policy-probe"):
        assert forbidden not in text
    assert not any("env" in value for key, value in selected.items() if key != "dependencies")


def test_workflow_selects_the_unchanged_1477_test_file_bundle():
    selected = steps()["contracts"]
    assert selected["working-directory"] == "batch-runner"
    args = pytest_args(selected)
    assert args[:6] == ["-q", "-o", "addopts=", "-p", "no:cacheprovider", "--basetemp=$ci_tmp/contracts"]
    assert args[6] == "--junitxml=$RUNNER_TEMP/ghcp-patched-ci/contracts.xml"
    assert args[7:] == SUITE
    assert len(SUITE) == len(set(SUITE)) == 10
    for step in (selected, steps()["workflow_guards"]):
        text = step["run"]
        assert text.startswith("set -euo pipefail\numask 077\n")
        assert 'ci_tmp="$(mktemp -d /tmp/ghcp-ci.XXXXXX)"' in text
        assert 'env -i PATH="$PATH" LANG=C.UTF-8' in text
        for item in ("PYTHONDONTWRITEBYTECODE=1", "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1", "HF_HUB_OFFLINE=1", "HF_DATASETS_OFFLINE=1"):
            assert item in text
        assert "'${{ steps.python.outputs.python-path }}' -B -m pytest" in text
        assert "GITHUB_" not in text and "--collect-only" not in text


def test_workflow_guards_have_their_own_step_and_report():
    selected = steps()["workflow_guards"]
    assert selected["working-directory"] == "batch-runner"
    assert pytest_args(selected) == ["-q", "-o", "addopts=", "-p", "no:cacheprovider",
        "--basetemp=$ci_tmp/guards", "--junitxml=$RUNNER_TEMP/ghcp-patched-ci/workflow-guards.xml",
        "tests/test_ghcp_ahp_patched_runtime_ci.py"]


def test_only_junit_and_counts_are_published_without_runtime_artifacts():
    selected = steps()["artifacts"]
    assert selected["if"] == "always()"
    assert selected["with"] == {
        "name": "ghcp-patched-runtime-tests-${{ github.run_id }}-${{ github.run_attempt }}",
        "path": "${{ runner.temp }}/ghcp-patched-ci/contracts.xml\n${{ runner.temp }}/ghcp-patched-ci/workflow-guards.xml\n${{ runner.temp }}/ghcp-patched-ci/test-counts.json\n",
        "if-no-files-found": "error", "retention-days": "7", "include-hidden-files": "false",
    }
    assert all("if" not in value for key, value in steps().items() if key != "artifacts")


def test_result_check_retains_exact_expected_counts():
    assignments = [node for node in ast.parse(result_program()).body if isinstance(node, ast.Assign)
                   and any(isinstance(target, ast.Name) and target.id == "expected" for target in node.targets)]
    assert len(assignments) == 1 and ast.literal_eval(assignments[0].value) == EXPECTED_COUNTS
    assert 'env -i PATH="$PATH" LANG=C.UTF-8 RUNNER_TEMP="$RUNNER_TEMP"' in steps()["results"]["run"]


def test_result_check_accepts_complete_zero_failure_counts(tmp_path):
    directory = make_reports(tmp_path)
    result = run_result_program(tmp_path)
    assert result.returncode == 0, result.stderr
    summary = json.loads((directory / "test-counts.json").read_text())
    assert json.loads(result.stdout) == summary
    assert summary == {"evidence_kind": "offline-tests-only", "execution_allowed": False,
        "counts": {name: {"passed": count, "failed": 0, "errors": 0, "skipped": 0} for name, count in EXPECTED_COUNTS.items()}}


@pytest.mark.parametrize("name", EXPECTED_COUNTS)
@pytest.mark.parametrize("damage", ["empty", "missing_case", "extra_case", "failure", "error", "skipped", "absent"])
def test_result_check_refuses_missing_reduced_extra_failed_or_skipped_cases(tmp_path, name, damage):
    directory = make_reports(tmp_path)
    target = directory / name
    tree = ET.parse(target)
    suite = tree.getroot().find("testsuite")
    if damage == "absent":
        target.rename(target.with_suffix(".removed"))
    else:
        if damage == "empty":
            suite.clear()
        elif damage == "missing_case":
            suite.remove(suite.find("testcase"))
        elif damage == "extra_case":
            ET.SubElement(suite, "testcase", name="unexpected_case")
        else:
            ET.SubElement(suite.find("testcase"), damage)
        # Deliberately leave header counts unchanged: inspect real testcase nodes.
        tree.write(target, encoding="utf-8", xml_declaration=True)
    result = run_result_program(tmp_path)
    assert result.returncode != 0
    assert not (directory / "test-counts.json").exists()


@pytest.mark.parametrize("name,expected", ORIGINAL_WORKFLOWS.items())
def test_original_workflow_bytes_and_historical_hashes_are_preserved(name, expected):
    assert re.fullmatch(r"[0-9a-f]{64}", expected)
    assert hashlib.sha256((ROOT / ".github/workflows" / name).read_bytes()).hexdigest() == expected
