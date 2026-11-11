"""Static workflow contracts only; no Actions operation, host or secret."""

import ast
from pathlib import Path
import re

import pytest
import yaml

import ghcp_ahp_auth_smoke as smoke
import ghcp_ahp_auth_publication as pub
import ghcp_ahp_patched_runtime as patched
from ghcp_ahp_errors import Refused

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/ghcp-ahp-auth-zero-turn-smoke.yml"


def document():
    return yaml.load(WORKFLOW.read_text(), Loader=yaml.BaseLoader)


def steps():
    return {step["id"]: step for step in document()["jobs"]["auth-zero-turn"]["steps"]}


def test_dispatch_is_the_only_trigger_with_a_false_by_default_explicit_confirmation():
    value = document()
    assert set(value["on"]) == {"workflow_dispatch"}
    inputs = value["on"]["workflow_dispatch"]["inputs"]
    assert set(inputs) == {"confirm_zero_turn_only"}
    assert inputs["confirm_zero_turn_only"]["type"] == "boolean"
    assert inputs["confirm_zero_turn_only"]["required"] == "true"
    assert inputs["confirm_zero_turn_only"]["default"] == "false"
    assert "env" not in value and "workflow_call" not in value["on"]


def test_protected_environment_standard_runner_and_minimal_permissions():
    value = document()
    assert value["permissions"] == {"contents": "read"}
    assert value["concurrency"] == {"group": "ghcp-auth-zero-turn-${{ github.ref }}", "cancel-in-progress": "false"}
    assert set(value["jobs"]) == {"auth-zero-turn"}
    job = value["jobs"]["auth-zero-turn"]
    assert job["environment"] == "ghcp-sol-gate" and job["runs-on"] == "ubuntu-24.04"
    assert 1 <= int(job["timeout-minutes"]) <= 10 and "env" not in job
    assert job["if"] == "${{ github.event_name == 'workflow_dispatch' && inputs.confirm_zero_turn_only == true && github.ref == '" + smoke.BRANCH + "' }}"
    assert "strategy" not in job and "continue-on-error" not in job


def test_secret_is_scoped_to_one_step_only_and_never_used_as_shell_text_or_file():
    selected = steps()
    assert list(selected) == ["checkout", "python", "dependencies", "offline-tests", "prepare", "smoke", "publication", "artifact"]
    assert [name for name, step in selected.items() if "secrets." in yaml.dump(step)] == ["smoke"]
    assert selected["smoke"]["env"] == {"COPILOT_GITHUB_TOKEN": "${{ secrets.COPILOT_GITHUB_TOKEN }}",
        "GHCP_AUTH_SMOKE_CONFIRM": "true", "GHCP_AUTHENTICATED_ZERO_TURN": "true", "GHCP_PAID_EXECUTION": "false",
        "GHCP_CONNECTION_ONLY": "false"}
    script = selected["smoke"]["run"]
    assert "ghcp_ahp_auth_smoke.py run" in script and script.count("ghcp_ahp_auth_smoke.py") == 1
    assert "COPILOT_GITHUB_TOKEN" not in script and "${{ inputs." not in script
    assert "--preparation" in script and "--published" in script
    assert selected["checkout"]["with"]["persist-credentials"] == "false"


def test_dependencies_and_prepare_have_no_authentication_or_vendor_execution():
    selected = steps()
    assert selected["dependencies"]["env"] == {"PIP_CONFIG_FILE": "/dev/null"}
    assert "requirements-ghcp-sol-gate.txt" in selected["dependencies"]["run"]
    assert "ghcp_ahp_probe.py prepare" in selected["prepare"]["run"]
    assert "--authenticated-zero-turn" not in selected["prepare"]["run"]
    assert selected["python"]["with"]["python-version"] == "3.12.11"
    for step in selected.values():
        if "uses" in step:
            assert re.fullmatch(r"actions/[a-z-]+@[0-9a-f]{40}", step["uses"])


def test_unit_suites_are_explicit_and_credentials_cannot_leak_into_them():
    test = steps()["offline-tests"]
    assert test["working-directory"] == "batch-runner"
    for name in ("test_ghcp_ahp_auth_smoke.py", "test_ghcp_ahp_auth_publication.py", "test_ghcp_ahp_auth_smoke_workflow.py"):
        assert "tests/" + name in test["run"]
    assert "env -i " in test["run"] and "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1" in test["run"]
    assert "env" not in test and "secrets." not in test["run"]


def test_publication_requires_the_secret_steps_digest_and_an_independent_recheck():
    selected = steps()
    check = selected["publication"]
    assert check["if"] == "${{ always() && steps.smoke.outputs.scan_sha256 != '' }}"
    assert check["env"] == {"EXPECTED_SCAN_SHA256": "${{ steps.smoke.outputs.scan_sha256 }}"}
    assert "ghcp_ahp_auth_smoke.py verify" in check["run"]
    assert '--scan-sha256 "$EXPECTED_SCAN_SHA256"' in check["run"]
    assert check["run"].index("ghcp_ahp_auth_smoke.py verify") < check["run"].index("safe=true")
    assert selected["artifact"]["if"] == "${{ always() && steps.publication.outputs.safe == 'true' }}"
    expected = {"${{ runner.temp }}/ghcp-auth-zero-turn/published/" + name for name in pub.FILES | {pub.SCAN}}
    assert set(selected["artifact"]["with"]["path"].splitlines()) == expected
    assert selected["artifact"]["with"]["include-hidden-files"] == "false"
    assert selected["artifact"]["with"]["if-no-files-found"] == "error"
    assert selected["artifact"]["with"]["retention-days"] == "7"


@pytest.mark.parametrize("forbidden", ["continue-on-error", "|| true", "pull_request_target", "gh workflow run",
    "copilot login", "gh auth token", "::add-mask::", "set -x", "printenv", "execute-paid", "ghcp_sol_paid_gate.py",
    "ghcp_ahp_connection.py", "ghcp_sol_grader_contract.py", "step2", "step8"])
def test_no_paid_work_auth_fallback_ignored_failure_or_secret_debugging(forbidden):
    assert forbidden not in WORKFLOW.read_text()


def test_pending_owner_activation_is_still_refused():
    with pytest.raises(Refused):
        patched.require_activation()


def test_native_read_only_methods_exactly_match_the_unchanged_preload():
    source = smoke.wire.PRELOAD.read_text()
    literal = source.split("const READ_ONLY_RPC = new Set(", 1)[1].split(");", 1)[0]
    assert smoke.READ_ONLY_NATIVE == frozenset(ast.literal_eval(literal))


def test_zero_turn_only_catalog_addition_is_one_exact_method_in_both_consumers():
    source = smoke.wire.PRELOAD.read_text()
    literal = source.split("const ZERO_TURN_CATALOG_RPC = new Set(", 1)[1].split(");", 1)[0]
    assert smoke.ZERO_TURN_CATALOG_NATIVE == frozenset(ast.literal_eval(literal)) == {"hooks/list"}


def test_no_fake_mode_or_patched_activation_switch_is_exposed():
    source = Path(smoke.__file__).read_text()
    tree = ast.parse(source)
    options = [call.args[0].value for call in ast.walk(tree) if isinstance(call, ast.Call)
               and isinstance(call.func, ast.Attribute) and call.func.attr == "add_argument"
               and call.args and isinstance(call.args[0], ast.Constant)]
    assert options == ["mode", "--prepared", "--preparation", "--published", "--scan-sha256"]
    assert "activate_patched" not in source and "require_activation =" not in source
