"""Branch-only offline CI, builds and isolated no-auth load smoke; no model request.

The compiler job's shell is parsed, not run, by these offline tests.
"""

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

import ghcp_ahp_patched_runtime as patched
import ghcp_ahp_bundle_manifest as bundle_manifest


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
EXTRA_SUITE = ["tests/test_ghcp_ahp_patchset.py", "tests/test_ghcp_ahp_load_smoke.py", "tests/test_ghcp_ahp_readiness_smoke.py",
               "tests/test_ghcp_ahp_permission_normalization.py",
               "tests/test_ghcp_ahp_prewarm_zero_turn.py", "tests/test_ghcp_ahp_prewarm_order.py",
               "tests/test_ghcp_ahp_server_only_staging.py", "tests/test_ghcp_ahp_runner_userns.py"]
EXPECTED_COUNTS = {"contracts.xml": 2191, "workflow-guards.xml": 74}
CORRECTION = ROOT / "batch-runner/patches/vscode-2c33b50b-prewarm-chat-context.patch"
CORRECTION_SHA256 = "555cdcfd54549796e558a0c7cb56155599d9522795c042465aaba7f8af46558a"
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


def typecheck_steps():
    return {item["id"]: item for item in workflow()["jobs"]["patched-codex-typecheck"]["steps"]}


def bundle_steps():
    return {item["id"]: item for item in workflow()["jobs"]["patched-codex-server-bundle"]["steps"]}


def smoke_steps():
    return {item["id"]: item for item in workflow()["jobs"]["patched-agent-host-load-smoke"]["steps"]}


def result_program(selected=None):
    command = (steps() if selected is None else selected)["results"]["run"]
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
    assert set(value["jobs"]) == {"contracts", "patched-codex-typecheck", "patched-codex-server-bundle", "patched-agent-host-load-smoke", "patched-agent-host-readiness-smoke"}
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
    assert selected["dependencies"]["run"] == "python -m pip install --disable-pip-version-check --only-binary=:all: -r batch-runner/requirements-ghcp-sol-gate.txt"
    requirements = (ROOT / "batch-runner/requirements-ghcp-sol-gate.txt").read_bytes()
    assert hashlib.sha256(requirements).hexdigest() == "6df2e82ae1f0e03835029ad122899c257d357fc71c8aa5bde100495d2d71dfaf"
    locked = {line.strip() for line in requirements.decode().splitlines() if line.strip() and not line.startswith("#")}
    assert {"pytest==9.1.1", "PyYAML==6.0.3", "jsonschema==4.26.0", "pandas==2.3.3", "huggingface_hub==1.24.0"} <= locked
    assert all(re.fullmatch(r"[A-Za-z0-9_.-]+==[A-Za-z0-9_.+-]+", line) for line in locked)
    assert not {"openai", "anthropic", "azure-ai-inference"} & {line.split("==")[0].lower() for line in locked}
    text = WORKFLOW.read_text()
    for forbidden in ("secrets.", "GITHUB_TOKEN", "COPILOT_GITHUB_TOKEN", "workflow_dispatch", "workflow_call",
                      "continue-on-error", "|| true", "gh workflow", "gh run",
                      "batch-runner/ghcp_ahp_probe.py", "--execute-paid", "--authenticated-zero-turn", "--session-policy-probe"):
        assert forbidden not in text
    # The newly authorized compiler job must not expand the offline test job.
    contracts_text = json.dumps(workflow()["jobs"]["contracts"])
    for forbidden in ("typecheck", "npm ", "electronTypes", "curl ", "git apply", "build/next/"):
        assert forbidden not in contracts_text
    assert not any("env" in value for key, value in selected.items() if key != "dependencies")


def test_workflow_selects_the_unchanged_1477_test_file_bundle():
    selected = steps()["contracts"]
    assert selected["working-directory"] == "batch-runner"
    args = pytest_args(selected)
    assert args[:6] == ["-q", "-o", "addopts=", "-p", "no:cacheprovider", "--basetemp=$ci_tmp/contracts"]
    assert args[6] == "--junitxml=$RUNNER_TEMP/ghcp-patched-ci/contracts.xml"
    assert args[7:7 + len(SUITE)] == SUITE
    assert args[7 + len(SUITE):] == EXTRA_SUITE
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
    data = (ROOT / ".github/workflows" / name).read_bytes()
    if name == "agentic-v2-ghcp-sol-gate.yml":
        from .test_ghcp_ahp_prewarm_zero_turn import restore_workflow
        # Reverse only the exact, separately tested zero-turn preparation overlay.
        # Hash all historical bytes; never update the historical expected SHA.
        data = restore_workflow(data.decode()).encode()
    assert hashlib.sha256(data).hexdigest() == expected


def test_typecheck_job_is_branch_only_unprivileged_ubuntu_24_and_time_bounded():
    job = workflow()["jobs"]["patched-codex-typecheck"]
    assert set(job) == {"name", "needs", "if", "runs-on", "timeout-minutes", "permissions", "steps"}
    assert job["name"] == "patched Codex module typecheck"
    assert job["needs"] == "contracts"
    assert job["if"] == f"github.event_name == 'push' && github.ref == 'refs/heads/{BRANCH}'"
    assert job["runs-on"] == "ubuntu-24.04"
    assert 1 <= int(job["timeout-minutes"]) <= 180
    assert job["permissions"] == {"contents": "read"}
    for step in job["steps"]:
        assert not {"environment", "continue-on-error"} & set(step)
        if "timeout-minutes" in step:
            assert 1 <= int(step["timeout-minutes"]) <= 180


def test_typecheck_uses_pinned_setup_actions_and_only_expected_steps():
    selected = typecheck_steps()
    assert list(selected) == ["checkout", "python", "node", "prepare", "dependencies", "electron_types",
                              "typecheck", "upstream_diagnostic", "results", "artifacts"]
    assert {key: value["uses"] for key, value in selected.items() if "uses" in value} == {
        key: value["uses"] for key, value in steps().items() if "uses" in value}
    assert selected["checkout"]["with"] == {"persist-credentials": "false"}
    assert selected["python"]["with"] == {"python-version": "3.12.11"}
    assert selected["node"]["with"] == {"node-version": "24.22.1", "package-manager-cache": "false"}
    assert all("env" not in step for name, step in selected.items() if name != "results")
    assert {name: step["if"] for name, step in selected.items() if "if" in step} == {
        "upstream_diagnostic": "failure() && steps.typecheck.outcome == 'failure'",
        "results": "always()", "artifacts": "always()"}


def test_typecheck_has_no_secret_model_endpoint_or_runtime_invocation():
    text = json.dumps(workflow()["jobs"]["patched-codex-typecheck"])
    for forbidden in ("secrets", "id-token", "api.github.com", "api.openai.com", "copilot_internal",
                      "chat/completions", "/responses", "execute_paid", "createSession", "thread/start",
                      "agentHostMain.js", "--agent-host", "ghcp_ahp_zero_turn.py", "ghcp_ahp_connection",
                      "npx ", "npm install", "npm update", "skipDefaultLibCheck", "noCheck", "listFilesOnly",
                      "@ts-ignore", "@ts-nocheck", "--noEmitOnError false"):
        assert forbidden not in text
    assert re.findall(r"https://[^\s]+", WORKFLOW.read_text()) == [
        "https://codeload.github.com/microsoft/vscode/tar.gz/2c33b50b16c472efe58357d1d2a8a5414bc23fbf",
        "https://vscode.download.prss.microsoft.com/dbazure/download/stable/2c33b50b16c472efe58357d1d2a8a5414bc23fbf/vscode-server-linux-x64.tar.gz"]
    assert "execution_allowed\": True" not in text


def test_source_preparation_requires_actions_and_exact_source_patch_pins():
    command = typecheck_steps()["prepare"]["run"]
    for check in ('test "$GITHUB_ACTIONS" = true', 'test "$RUNNER_OS" = Linux',
                  'test "$ID:$VERSION_ID" = ubuntu:24.04', 'test "$(env -i PATH="$PATH" node --version)" = v24.22.1'):
        assert check in command
    manifest_path = ROOT / "batch-runner/ghcp_ahp_probe_manifest.json"
    assert hashlib.sha256(manifest_path.read_bytes()).hexdigest() == "cd5ff8f2e1ad1f140892febdc75f288adfe8e3c96bd4d3b8e9a4078a90ef5049"
    manifest = json.loads(manifest_path.read_text())
    source = manifest["artifacts"]["source"]
    assert source["url"] in command and source["sha256"] in command
    assert f'--max-filesize {source["maximum_bytes"]}' in command
    assert "--proto '=https' --proto-redir '=https' --max-time 300" in command
    patch = ROOT / "batch-runner/patches/vscode-2c33b50b-prewarm-config-ready.patch"
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == "a4e8d0fad6bc37b73b8dc2731be6914d07e0af6460ccb7bcf6749a48f8c3bceb"
    assert "a4e8d0fad6bc37b73b8dc2731be6914d07e0af6460ccb7bcf6749a48f8c3bceb" in command
    ordered = ['sha256sum --check "$evidence/upstream-source.sha256"', 'git apply --check "$patch_file"',
               'git apply "$patch_file"', 'git apply --reverse --check "$patch_file"',
               'sha256sum --check "$evidence/patched-source.sha256"',
               'sha256sum --check "$evidence/source-invariants.sha256"']
    assert [command.index(item) for item in ordered] == sorted(command.index(item) for item in ordered)


def test_typecheck_reuses_the_locked_drafts_pre_and_post_patch_hashes():
    draft = (ROOT / ".github/workflows/ghcp-ahp-patched-host-build-draft.yml").read_text()
    command = typecheck_steps()["prepare"]["run"].split("# One-line compiler correction,", 1)[0]
    pairs = re.findall(r"([0-9a-f]{64}) (src/vs/platform/agentHost/\S+\.ts)", draft)
    assert len(pairs) == 6
    for digest, path in pairs:
        assert command.count(f"{digest} {path}") == 1


def test_install_preserves_both_lockfiles_configs_and_compiler_script():
    selected = typecheck_steps()
    pairs = dict((path, digest) for digest, path in re.findall(
        r"([0-9a-f]{64}) ([.\w/-]+)", selected["prepare"]["run"]))
    assert pairs["package-lock.json"] == "b2512f1e9f111f215168ef26d284e1aaa0da59e32fea13d134799cc74400b9ee"
    assert pairs["build/package-lock.json"] == "2975565119f8cb74d44eb74bd6a2c166027eafa953ddb863b125d3df7875d2a7"
    assert pairs["package.json"] == "6529eb9164da5d1c108edaab1210636affcaf19f5600980dfa46272323239679"
    assert pairs["src/tsconfig.json"] == "6c35a05a6798601b37cd28c535f4e7258ffdf34e271fbf6a4411d328f1db2332"
    assert pairs["src/tsconfig.base.json"] == "74359c514fb10624b9871279dd094fdd8034d4f3e37b154b5b98726db361c8c4"
    command = selected["dependencies"]["run"]
    assert command.count('env -i PATH="$PATH" LANG=C.UTF-8 npm_config_userconfig=/dev/null') == 2
    assert command.count('npm_config_globalconfig="$evidence/empty-global.npmrc" npm_config_cache="$evidence/npm-cache"') == 2
    assert 'npm ci --ignore-scripts --no-audit --no-fund 2>&1 | tee "$evidence/dependencies-root.log"' in command
    assert 'npm --prefix build ci --ignore-scripts --no-audit --no-fund 2>&1 | tee "$evidence/dependencies-build.log"' in command
    assert command.count('sha256sum --check "$evidence/source-invariants.sha256"') == 2


def test_electron_declarations_use_pinned_helper_and_verify_downloaded_checksum():
    selected = typecheck_steps()
    assert "c8ec14dbf6814a112522a83fefbca7e94d083712baf132079b39a2876f099b3a build/npm/electronTypes.ts" in selected["prepare"]["run"]
    assert "5f7dd4189640be2f627607f7ef899011116f89645b56ee830f1a2c8f96dd69d5 build/checksums/electron.txt" in selected["prepare"]["run"]
    command = selected["electron_types"]["run"]
    assert 'env -i PATH="$PATH" LANG=C.UTF-8 node build/npm/electronTypes.ts 2>&1 | tee "$evidence/electron-types.log"' in command
    assert 'test -s .build/typings/electron.d.ts' in command
    assert 'test "${#expected}" -eq 64' in command
    assert 'sha256sum --check "$evidence/electron-types.sha256"' in command
    assert "build/checksums/electron.txt" in command


def test_compiler_checks_whole_upstream_project_and_diagnostic_cannot_erase_failure():
    selected = typecheck_steps()
    for name, log_name in (("typecheck", "patched-typecheck"), ("upstream_diagnostic", "upstream-typecheck")):
        command = selected[name]["run"]
        assert command.count("npm run ") == 1
        assert f'npm run typecheck-client -- --pretty false --listFiles --extendedDiagnostics 2>&1 | tee "$evidence/{log_name}.log"' in command
        assert 'env -i PATH="$PATH" LANG=C.UTF-8 npm_config_userconfig=/dev/null' in command
        assert 'npm_config_globalconfig="$evidence/empty-global.npmrc" npm_config_ignore_scripts=true' in command
        assert "--project" not in command and "--skip" not in command
    diagnostic = selected["upstream_diagnostic"]
    assert diagnostic["if"] == "failure() && steps.typecheck.outcome == 'failure'"
    assert 'git apply --reverse "$patch_file"' in diagnostic["run"]
    assert diagnostic["run"].index('sha256sum --check "$evidence/upstream-source.sha256"') < diagnostic["run"].index("npm run ")
    assert 'git apply "$patch_file"' not in diagnostic["run"]  # no patched retry


@pytest.mark.parametrize("name", ["prepare", "dependencies", "electron_types", "typecheck", "upstream_diagnostic", "results"])
def test_typecheck_shell_syntax_and_failure_propagation_without_running_it(name):
    command = typecheck_steps()[name]["run"]
    assert command.startswith("set -euo pipefail\n")
    assert "|| true" not in command and "set +e" not in command and "exit 0" not in command
    result = subprocess.run(["/bin/bash", "-n"], input=command, capture_output=True, text=True, timeout=5)
    assert result.returncode == 0, result.stderr


def test_typecheck_artifacts_are_compiler_evidence_not_runtime_candidate():
    selected = typecheck_steps()
    assert selected["artifacts"]["with"] == {
        "name": "ghcp-patched-codex-typecheck-${{ github.run_id }}-${{ github.run_attempt }}",
        "path": "${{ runner.temp }}/ghcp-patched-typecheck/*.log\n${{ runner.temp }}/ghcp-patched-typecheck/*.sha256\n${{ runner.temp }}/ghcp-patched-typecheck/typecheck-result.json\n",
        "if-no-files-found": "error", "retention-days": "7", "include-hidden-files": "false"}
    assert selected["results"]["env"] == {
        phase.upper() + "_OUTCOME": "${{ steps." + phase + ".outcome }}"
        for phase in ("prepare", "dependencies", "electron_types", "typecheck", "upstream_diagnostic")}


def run_typecheck_result(tmp_path, failed_phase=None, missing_module=None):
    directory = tmp_path / "ghcp-patched-typecheck"
    directory.mkdir()
    modules = ("src/vs/platform/agentHost/common/agent.ts", "src/vs/platform/agentHost/node/codex/codexAgent.ts",
               "src/vs/platform/agentHost/node/agentService.ts")
    log = directory / "patched-typecheck.log"
    log.write_text("\n".join(str(directory / "source" / name) for name in modules if name != missing_module) + "\n")
    env = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "RUNNER_TEMP": str(tmp_path),
           "GITHUB_STEP_SUMMARY": str(tmp_path / "summary.md")}
    for phase in ("prepare", "dependencies", "electron_types", "typecheck", "upstream_diagnostic"):
        # A successful original-source diagnostic cannot override a patched compiler failure.
        env[phase.upper() + "_OUTCOME"] = "failure" if phase == failed_phase else "success"
    result = subprocess.run([sys.executable, "-B", "-c", result_program(typecheck_steps())],
                            env=env, capture_output=True, text=True, timeout=15)
    report = json.loads((directory / "typecheck-result.json").read_text())
    assert report["execution_allowed"] is False and report["runtime_load_status"] == "not_executed"
    assert report["patched_ghcp"] is True
    assert report["evidence_kind"] == "patched-source-typecheck-no-execution"
    assert report["patch_sha256"] == patched.PATCH_SHA256
    assert report["base_patch_sha256"] == "a4e8d0fad6bc37b73b8dc2731be6914d07e0af6460ccb7bcf6749a48f8c3bceb"
    assert report["typecheck_correction_sha256"] == CORRECTION_SHA256
    assert report["typechecked_source_status"] == "base-patch-plus-context-correction"
    assert report["runtime_receipt_schema"] == "ghcp-patched-host-build-candidate-v3"
    assert report["runtime_receipt_generated"] is False
    assert report["evidence_sha256"]["patched-typecheck.log"] == hashlib.sha256(log.read_bytes()).hexdigest()
    summary = (tmp_path / "summary.md").read_text()
    assert json.loads(summary.split("```json\n", 1)[1].split("\n```", 1)[0]) == report
    return result, report


def test_typecheck_result_requires_compiler_success_and_all_three_modules(tmp_path):
    result, report = run_typecheck_result(tmp_path)
    assert result.returncode == 0, result.stderr
    assert report["typecheck_passed"] is True
    assert all(report["patched_modules_in_compiler_input"].values())


@pytest.mark.parametrize("phase", ["prepare", "dependencies", "electron_types", "typecheck"])
def test_typecheck_result_does_not_hide_any_failed_phase_or_accept_baseline_instead(tmp_path, phase):
    result, report = run_typecheck_result(tmp_path, failed_phase=phase)
    assert result.returncode != 0 and "patched_source_typecheck_refused" in result.stderr
    assert report["typecheck_passed"] is False


@pytest.mark.parametrize("name", ["src/vs/platform/agentHost/common/agent.ts",
                                 "src/vs/platform/agentHost/node/codex/codexAgent.ts",
                                 "src/vs/platform/agentHost/node/agentService.ts"])
def test_typecheck_result_refuses_an_unchecked_patched_module(tmp_path, name):
    result, report = run_typecheck_result(tmp_path, missing_module=name)
    assert result.returncode != 0 and "patched_source_typecheck_refused" in result.stderr
    assert report["typecheck_passed"] is False
    assert report["patched_modules_in_compiler_input"][name] is False


def test_context_correction_is_separately_pinned_applied_once_and_reversed_before_base_patch():
    assert hashlib.sha256(CORRECTION.read_bytes()).hexdigest() == CORRECTION_SHA256
    selected = typecheck_steps()
    prepare = selected["prepare"]["run"]
    assert f'{CORRECTION_SHA256} "$correction_file" | sha256sum --check' in prepare
    order = ['sha256sum --check "$evidence/patched-source.sha256"',
             'git apply --check "$correction_file"', 'git apply "$correction_file"',
             'git apply --reverse --check "$correction_file"', 'sha256sum --check "$evidence/corrected-source.sha256"']
    assert [prepare.index(part) for part in order] == sorted(prepare.index(part) for part in order)
    assert prepare.count('git apply "$correction_file"') == 1
    assert '209a699ee4138a822a2aaa5a1146066d937d5526a826846106debb8b9d34a49c src/vs/platform/agentHost/node/agentService.ts' in prepare
    for name in ("dependencies", "typecheck", "upstream_diagnostic"):
        assert '"$evidence/corrected-source.sha256"' in selected[name]["run"]
    diagnostic = selected["upstream_diagnostic"]["run"]
    order = ['git apply --reverse "$correction_file"', 'sha256sum --check "$evidence/patched-source.sha256"',
             'git apply --reverse "$patch_file"', 'sha256sum --check "$evidence/upstream-source.sha256"', 'npm run typecheck-client']
    assert [diagnostic.index(part) for part in order] == sorted(diagnostic.index(part) for part in order)
    assert '"corrected-source.sha256"' in result_program(typecheck_steps())


@pytest.mark.parametrize("state", ["pinned_parent", "already_corrected", "unexpected_parent"])
def test_one_line_context_patch_uses_the_upstream_prewarm_storage_contract_only(tmp_path, state):
    """A patch-application fixture, never a source compile or host execution."""
    lines = CORRECTION.read_text().splitlines(keepends=True)
    assert sum(line.startswith("@@ ") for line in lines) == 1
    minus = [line[1:] for line in lines if line.startswith("-") and not line.startswith("---")]
    plus = [line[1:] for line in lines if line.startswith("+") and not line.startswith("+++")]
    assert minus == ['\t\t\tprovider.chats.onChatConfigurationReady?.(defaultChat, this._chatContext(session, defaultChat));\n']
    assert plus == ['\t\t\tprovider.chats.onChatConfigurationReady?.(defaultChat, this._chatContext(session, defaultChat, '
                    'this._knownDefaultChatStorageResource(session, defaultChat) ?? this._newDefaultChatStorageResource(session, defaultChat)));\n']
    body = lines[next(index for index, line in enumerate(lines) if line.startswith("@@ ")) + 1:]
    source = "// patch fixture only\n" * 6200 + "".join(line[1:] for line in body if line[0] in " -")
    if state == "already_corrected":
        source = source.replace(minus[0], plus[0])
    elif state == "unexpected_parent":
        source = source.replace("this._chatContext(session, defaultChat)", "this._chatContext(other, defaultChat)")
    target = tmp_path / "src/vs/platform/agentHost/node/agentService.ts"
    target.parent.mkdir(parents=True)
    target.write_text(source)
    result = subprocess.run(["git", "apply", "--check", str(CORRECTION)], cwd=tmp_path,
                            capture_output=True, text=True, timeout=10)
    assert (result.returncode == 0) is (state == "pinned_parent"), result.stderr
    if state == "pinned_parent":
        subprocess.run(["git", "apply", str(CORRECTION)], cwd=tmp_path, check=True, capture_output=True, timeout=10)
        assert target.read_text() == source.replace(minus[0], plus[0])
        subprocess.run(["git", "apply", "--reverse", str(CORRECTION)], cwd=tmp_path, check=True, capture_output=True, timeout=10)
        assert target.read_text() == source


def test_bundle_job_follows_typecheck_on_standard_runner_with_read_only_permissions():
    job = workflow()["jobs"]["patched-codex-server-bundle"]
    assert set(job) == {"name", "needs", "if", "runs-on", "timeout-minutes", "permissions", "steps", "outputs"}
    assert job["name"] == "patched Codex server bundle build"
    assert job["needs"] == "patched-codex-typecheck"
    assert job["if"] == f"github.event_name == 'push' && github.ref == 'refs/heads/{BRANCH}'"
    assert job["runs-on"] == "ubuntu-24.04" and 1 <= int(job["timeout-minutes"]) <= 240
    assert job["permissions"] == {"contents": "read"}
    assert job["outputs"] == {"payload_artifact_id": "${{ steps.payload_artifact.outputs.artifact-id }}"}
    assert all("env" not in step and "continue-on-error" not in step for step in job["steps"])
    assert {step["id"]: step["if"] for step in job["steps"] if "if" in step} == {"artifacts": "always()"}


def test_bundle_reuses_exact_typechecked_patch_chain_and_locked_dependency_preparation():
    selected = bundle_steps()
    assert list(selected) == ["checkout", "python", "node", "prepare", "dependencies", "electron_types",
                              "product_inputs", "bundle", "manifest", "payload", "payload_artifact", "artifacts"]
    for name in ("checkout", "python", "node", "prepare", "dependencies", "electron_types"):
        assert selected[name] == typecheck_steps()[name]
    assert '"$GITHUB_WORKSPACE/batch-runner/ghcp_ahp_patched_runtime.py" verify-patchset' in selected["prepare"]["run"]
    assert hashlib.sha256(patched.PATCH_SET.read_bytes()).hexdigest() == patched.PATCH_SHA256


def test_bundle_product_preparation_downloads_only_the_pinned_public_vendor_archive():
    command = bundle_steps()["product_inputs"]["run"]
    pin = json.loads(patched.MANIFEST.read_text())["artifacts"]["server"]
    assert pin["url"] in command and pin["sha256"] in command
    assert f'--max-filesize {pin["maximum_bytes"]}' in command
    assert "--proto '=https' --proto-redir '=https' --max-time 300" in command
    assert "ghcp_ahp_bundle_manifest.py prepare" in command
    assert command.count('env -i PATH="$PATH" LANG=C.UTF-8') == 2


def test_bundle_compiler_has_no_network_and_uses_exact_unweakened_upstream_command():
    command = bundle_steps()["bundle"]["run"]
    assert 'sudo -n unshare --net -- setpriv --reuid="$(id -u)" --regid="$(id -g)" --clear-groups' in command
    assert f'env -i PATH="$PATH" LANG=C.UTF-8 BUILD_SOURCEVERSION={patched.PIN}' in command
    assert ' '.join(bundle_manifest.COMMAND) + ' 2>&1 | tee "$evidence/server-bundle.log"' in command
    assert 'test -s out-patched/vs/platform/agentHost/node/agentHostMain.js' in command
    assert command.count('sha256sum --check "$evidence/source-invariants.sha256" "$evidence/corrected-source.sha256" "$evidence/electron-types.sha256"') == 2
    for text in (WORKFLOW.read_text(), (ROOT / "batch-runner/ghcp_ahp_bundle_manifest.py").read_text()):
        for forbidden in ("secrets.", "COPILOT_GITHUB_TOKEN", "GITHUB_TOKEN", "workflow_dispatch", "createSession",
                          "thread/start", "chat/completions", "api.openai.com", "api.github.com", "continue-on-error", "|| true"):
            assert forbidden not in text


def test_bundle_upload_contains_only_the_hash_size_manifest_not_binaries_or_logs():
    selected = bundle_steps()
    assert selected["artifacts"]["uses"] == steps()["artifacts"]["uses"]
    assert selected["artifacts"]["with"] == {
        "name": "ghcp-patched-codex-server-manifest-${{ github.run_id }}-${{ github.run_attempt }}",
        "path": "${{ runner.temp }}/ghcp-patched-typecheck/server-bundle-manifest.json",
        "if-no-files-found": "error", "retention-days": "7", "include-hidden-files": "false"}
    assert "ghcp_ahp_bundle_manifest.py record" in selected["manifest"]["run"]
    assert '--receipt "$evidence/build-receipt.json"' in selected["manifest"]["run"]


@pytest.mark.parametrize("name", ["product_inputs", "bundle", "manifest"])
def test_bundle_shell_is_parsed_only_on_nas_and_preserves_failures(name):
    command = bundle_steps()[name]["run"]
    assert command.startswith("set -euo pipefail\n")
    assert "|| true" not in command and "set +e" not in command and "exit 0" not in command
    result = subprocess.run(["/bin/bash", "-n"], input=command, capture_output=True, text=True, timeout=5)
    assert result.returncode == 0, result.stderr


def test_bundle_manifest_adapter_cannot_launch_runtime_or_network_clients():
    text = (ROOT / "batch-runner/ghcp_ahp_bundle_manifest.py").read_text()
    tree = ast.parse(text)
    imports = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    imports |= {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert imports <= {"__future__", "argparse", "datetime", "os", "pathlib", "tarfile",
                       "ghcp_ahp_patched_runtime", "ghcp_ahp_errors"}
    assert not any(word in text for word in ("os.system", "os.popen", "subprocess", "eval(", "exec("))
    assert bundle_manifest.COMMAND == ["node", "build/next/index.ts", "bundle", "--target", "server", "--minify", "--out", "out-patched"]


def test_payload_is_short_lived_and_produced_after_the_real_bundle_receipt():
    selected = bundle_steps()
    assert selected["payload_artifact"]["uses"] == steps()["artifacts"]["uses"]
    assert selected["payload_artifact"]["with"] == {
        "name": "ghcp-patched-load-payload-${{ github.run_id }}-${{ github.run_attempt }}",
        "path": "${{ runner.temp }}/ghcp-patched-typecheck/load-smoke-transfer/payload.tar\n${{ runner.temp }}/ghcp-patched-typecheck/load-smoke-transfer/transfer.json\n",
        "if-no-files-found": "error", "retention-days": "1", "include-hidden-files": "false"}
    assert list(selected).index("manifest") < list(selected).index("payload") < list(selected).index("payload_artifact")
    assert "ghcp_ahp_load_smoke.py pack" in selected["payload"]["run"]
    assert '--bundle "$evidence/source/out-patched/vs/platform/agentHost/node/agentHostMain.js"' in selected["payload"]["run"]


def test_load_smoke_is_separate_standard_runner_job_with_no_model_environment():
    job = workflow()["jobs"]["patched-agent-host-load-smoke"]
    assert set(job) == {"name", "needs", "if", "runs-on", "timeout-minutes", "permissions", "steps"}
    assert job["name"] == "patched agent host model-free load smoke"
    assert job["needs"] == "patched-codex-server-bundle"
    assert job["if"] == f"github.event_name == 'push' && github.ref == 'refs/heads/{BRANCH}'"
    assert job["runs-on"] == "ubuntu-24.04" and job["timeout-minutes"] == "15"
    assert job["permissions"] == {"contents": "read"}
    selected = smoke_steps()
    assert list(selected) == ["checkout", "python", "payload", "prepare", "smoke", "artifacts"]
    for name in ("checkout", "python"):
        assert selected[name] == typecheck_steps()[name]
    assert {name: step["if"] for name, step in selected.items() if "if" in step} == {"artifacts": "always()"}
    assert all("env" not in step and "continue-on-error" not in step for step in selected.values())


def test_load_smoke_download_is_bound_to_the_same_run_producer_artifact_id():
    selected = smoke_steps()["payload"]
    assert selected["uses"] == "actions/download-artifact@37930b1c2abaa49bbe596cd826c3c89aef350131"
    assert selected["with"] == {
        "artifact-ids": "${{ needs.patched-codex-server-bundle.outputs.payload_artifact_id }}",
        "merge-multiple": "true", "path": "${{ runner.temp }}/ghcp-load-transfer"}
    command = smoke_steps()["prepare"]["run"]
    assert "ghcp_ahp_load_smoke.py prepare" in command
    assert '--transfer "$RUNNER_TEMP/ghcp-load-transfer"' in command
    assert "curl" not in command and "npm" not in command


def test_actual_load_is_in_net_and_pid_namespaces_without_capabilities_or_inherited_credentials():
    command = smoke_steps()["smoke"]["run"]
    for required in ('smoke_netns="$(readlink /proc/self/ns/net)"', 'smoke_pidns="$(readlink /proc/self/ns/pid)"',
                     'timeout --signal=TERM --kill-after=10s 90s',
                     'sudo -n unshare --mount --net --pid --fork --mount-proc --kill-child=KILL',
                     '--bounding-set=-all --inh-caps=-all --ambient-caps=-all --no-new-privs',
                     '/usr/bin/env -i PATH=/usr/bin:/bin LANG=C.UTF-8 PYTHONDONTWRITEBYTECODE=1',
                     '"$GITHUB_WORKSPACE/batch-runner/ghcp_ahp_load_smoke.py" run',
                     '--outside-netns "$smoke_netns" --outside-pidns "$smoke_pidns"'):
        assert required in command
    assert command.count('ghcp_ahp_load_smoke.py" run') == 1
    for forbidden in ("secrets.", "GITHUB_TOKEN", "COPILOT_GITHUB_TOKEN", "workflow_dispatch", "createSession",
                      "--authenticated-zero-turn", "--connection-only", "--execute-paid", "HOME=", "CODEX_HOME="):
        assert forbidden not in command


def test_load_smoke_artifact_contains_only_receipts_not_runtime_data_or_token_stores():
    selected = smoke_steps()["artifacts"]
    assert selected["uses"] == steps()["artifacts"]["uses"]
    value = selected["with"]
    assert value["name"] == "ghcp-patched-load-smoke-${{ github.run_id }}-${{ github.run_attempt }}"
    expected = ["load-smoke.json", *patched.ARTIFACTS, "server-bundle-manifest.json", "transfer.json"]
    assert value["path"].splitlines() == ["${{ runner.temp }}/ghcp-load-smoke-evidence/" + name for name in expected]
    assert value["if-no-files-found"] == "error" and value["retention-days"] == "7" and value["include-hidden-files"] == "false"


@pytest.mark.parametrize("job,name", [("bundle", "payload"), ("smoke", "prepare"), ("smoke", "smoke")])
def test_load_smoke_shell_is_only_syntax_checked_on_nas_and_never_suppresses_errors(job, name):
    command = (bundle_steps() if job == "bundle" else smoke_steps())[name]["run"]
    assert command.startswith("set -euo pipefail\n")
    assert "|| true" not in command and "set +e" not in command and "exit 0" not in command
    result = subprocess.run(["/bin/bash", "-n"], input=command, capture_output=True, text=True, timeout=5)
    assert result.returncode == 0, result.stderr


def readiness_steps():
    return {row["id"]: row for row in workflow()["jobs"]["patched-agent-host-readiness-smoke"]["steps"]}


def test_readiness_and_import_are_independent_mandatory_checks_of_the_same_bundle():
    job = workflow()["jobs"]["patched-agent-host-readiness-smoke"]
    assert job["name"] == "patched agent host readiness smoke"
    assert job["needs"] == "patched-codex-server-bundle"
    original = workflow()["jobs"]["patched-agent-host-load-smoke"]
    assert original["needs"] == "patched-codex-server-bundle"
    assert "continue-on-error" not in original and "always()" not in job["if"]
    assert job["runs-on"] == "ubuntu-24.04" and job["timeout-minutes"] == "15"
    assert job["permissions"] == {"contents": "read"}
    assert job["if"] == f"github.event_name == 'push' && github.ref == 'refs/heads/{BRANCH}'"
    assert "environment" not in job and "continue-on-error" not in job
    selected = readiness_steps()
    assert list(selected) == ["checkout", "python", "payload", "prepare", "readiness", "artifacts"]
    for name in ("checkout", "python"):
        assert selected[name]["uses"] == smoke_steps()[name]["uses"]
        assert selected[name]["with"] == smoke_steps()[name]["with"]
    assert selected["payload"]["with"] == {"artifact-ids": "${{ needs.patched-codex-server-bundle.outputs.payload_artifact_id }}",
        "merge-multiple": "true", "path": "${{ runner.temp }}/ghcp-readiness-transfer"}


def test_readiness_namespace_and_no_credential_contract():
    command = readiness_steps()["readiness"]["run"]
    for required in ("sudo -n unshare --mount --net --pid --fork --mount-proc --kill-child=KILL",
        "ip link set lo up; exec", "--bounding-set=-all --inh-caps=-all --ambient-caps=-all --no-new-privs",
        "/usr/bin/env -i PATH=/usr/bin:/bin", 'GITHUB_EVENT_NAME="$GITHUB_EVENT_NAME" GITHUB_REF="$GITHUB_REF"',
        "timeout --signal=TERM --kill-after=10s 240s", 'ghcp_ahp_readiness_smoke.py" run'):
        assert required in command
    for forbidden in ("secrets.", "COPILOT_GITHUB_TOKEN", "GITHUB_TOKEN", "--authenticated-zero-turn", "--execute-paid", "--connection-only"):
        assert forbidden not in command
    assert "environment" not in workflow()["jobs"]["patched-agent-host-readiness-smoke"]


@pytest.mark.parametrize("step", ["prepare", "readiness"])
def test_readiness_shell_is_parsed_never_executed_on_nas(step):
    command = readiness_steps()[step]["run"]
    assert command.startswith("set -euo pipefail\n")
    assert "|| true" not in command and "set +e" not in command
    checked = subprocess.run(["/bin/bash", "-n"], input=command, capture_output=True, text=True, timeout=5)
    assert checked.returncode == 0, checked.stderr


def test_readiness_artifacts_are_an_exact_json_allowlist():
    selected = readiness_steps()["artifacts"]
    assert selected["if"] == "always()"
    assert selected["uses"] == steps()["artifacts"]["uses"]
    value = selected["with"]
    expected = ["readiness-smoke.json", "backend-startup.json", "wire-capture.json", "thread-policy.json", "management-init.json",
                *patched.ARTIFACTS, "server-bundle-manifest.json", "transfer.json"]
    assert value["path"].splitlines() == ["${{ runner.temp }}/ghcp-readiness-evidence/" + name for name in expected]
    assert value["name"] == "ghcp-patched-readiness-${{ github.run_id }}-${{ github.run_attempt }}"
    assert value["if-no-files-found"] == "error" and value["include-hidden-files"] == "false"
