"""Static workflow routing and real fixed-reader refusal, without credentials."""

import itertools
import json
import re
import shlex

import yaml

import codex_retention_result_intake as reader
from core.codex_task_deadline import CodexTaskDeadline, CodexTaskDeadlineStore
from .test_codex_budget_pilot import offline  # noqa: F401; unchanged live-boundary guards


def _boolean(expression, replacements):
    """Evaluate only the workflow's closed boolean routing, never shell code."""
    for name, value in sorted(replacements.items(), key=lambda item: -len(item[0])):
        expression = expression.replace(name, str(value))
    expression = re.sub(r"\btrue\b", "True", expression)
    expression = re.sub(r"\bfalse\b", "False", expression)
    assert re.fullmatch(r"(?:True|False|\s|[()=!&|])+", expression), expression
    expression = re.sub(r"!(?!=)", " not ", expression).replace("&&", " and ").replace("||", " or ")
    result = eval(expression.strip(), {"__builtins__": {}}, {})
    assert type(result) is bool
    return result


def test_retention_result_read_workflow_is_fixed_and_model_free(monkeypatch, tmp_path, capsys):
    workflow = yaml.safe_load((reader.ci.ROOT / reader.ci.WORKFLOW).read_bytes())
    inputs = workflow.get("on", workflow.get(True))["workflow_dispatch"]["inputs"]
    assert set(inputs) == {"reviewed_source_sha", "cell_id", "prepare", "observe_locator", "execute", "read_result"}
    mode_names = ("prepare", "observe_locator", "execute", "read_result")
    assert all(inputs[name]["type"] == "boolean" and inputs[name]["default"] is False for name in mode_names)
    assert inputs["cell_id"]["default"] == reader.controller.FIRST_CELL_ID
    assert inputs["reviewed_source_sha"]["required"] is True
    jobs = workflow["jobs"]
    assert set(jobs) == {reader.ci.PREPARE_JOB, reader.ci.APPROVE_JOB, reader.ci.EXECUTE_JOB}
    prepare, approve, execute = (jobs[name] for name in (reader.ci.PREPARE_JOB, reader.ci.APPROVE_JOB, reader.ci.EXECUTE_JOB))
    assert workflow["permissions"] == {"contents": "read"} and "permissions" not in prepare
    assert approve["permissions"] == {} and approve["environment"] == {"name": "grading"}
    assert execute["permissions"] == {"contents": "read", "actions": "read", "id-token": "write"}
    assert "environment" not in prepare and "environment" not in execute
    assert workflow["concurrency"] == {"group": "codex-budget-pilot-ci-20260923-01", "cancel-in-progress": False}
    assert all(job["runs-on"] == "ubuntu-22.04" for job in jobs.values())
    assert [job["timeout-minutes"] for job in (prepare, approve, execute)] == [20, 5, 240]
    assert workflow["env"]["HF_HUB_OFFLINE"] == workflow["env"]["HF_DATASETS_OFFLINE"] == "1"
    assert workflow["env"]["HF_HUB_DISABLE_IMPLICIT_TOKEN"] == "1"
    assert not any("TOKEN" in name for name in workflow["env"] if name != "HF_HUB_DISABLE_IMPLICIT_TOKEN")
    steps = prepare["steps"]
    assert len(steps) == 11 and execute["steps"][:9] == steps[:9]
    gate, checkout = steps[:2]
    assert not any("secret" in value or "token" in value for value in gate["env"].values())
    assert checkout["with"] == {"ref": "${{ inputs.reviewed_source_sha }}", "fetch-depth": 0, "persist-credentials": False}
    preflight, read = steps[9:]
    read_condition = "inputs.read_result && !inputs.prepare && !inputs.execute && !inputs.observe_locator"
    assert preflight["if"] == read["if"] == read_condition
    assert set(preflight) == {"name", "if", "shell", "run"} and preflight["shell"] == "bash"
    assert read["env"] == {"HF_TOKEN": "${{ secrets.HF_TOKEN }}"}
    assert set(read) == {"name", "if", "timeout-minutes", "env", "shell", "run"}
    assert read["shell"] == "bash" and read["timeout-minutes"] == 4
    assert all("codex_retention_result_intake.py" not in step.get("run", "")
               for job in (approve, execute) for step in job["steps"])
    assert all("upload-artifact" not in step.get("uses", "") for job in jobs.values() for step in job["steps"])

    # All 16 combinations, using the actual YAML and source-gate expressions.
    # Read exclusion must hold even if a request output is spuriously nonempty.
    for values in itertools.product((False, True), repeat=4):
        modes = dict(zip(mode_names, values))
        prepared, observed, executed, reading = values
        replacements = {"inputs." + name: value for name, value in modes.items()}
        gate_values = {'"$' + name + '"': modes[value.removeprefix("${{ inputs.").removesuffix(" }}")]
                       for name, value in gate["env"].items()}
        admitted_route = all(_boolean(line.removeprefix("[[ ").removesuffix(" ]]"), gate_values)
                             for line in gate["run"].splitlines()[1:3])
        expected = not (reading and (prepared or observed or executed)) and not (observed and (prepared or executed))
        assert admitted_route is expected
        reachable = [index for index, step in enumerate(steps)
                     if admitted_route and _boolean(step.get("if", "true"), replacements)]
        if not expected:
            assert reachable == []  # First-step refusal precedes checkout and every secret.
        elif reading:
            assert reachable == [0, 1, 2, 3, 9, 10]  # No closed plan or original-input preparation.
            assert [steps[index].get("env") for index in reachable if "HF_TOKEN" in steps[index].get("env", {})] == [read["env"]]
        elif prepared or observed or executed:
            assert reachable == list(range(9))
        else:
            assert reachable == list(range(5))  # Unchanged inert plan default.
        ready = {**replacements, "needs.retention-prepare.result == 'success'": True,
                 "needs.retention-prepare.outputs.request_sha256 != ''": True,
                 "needs.retention-approve.result == 'success'": True}
        assert _boolean(approve["if"], ready) is (expected and not reading and (executed or observed))
        assert _boolean(execute["if"], ready) is (expected and not reading and (executed or observed))

    module_hash = "df629ee1defde93347a6a6eb92d25ef8ad536e39e7a52b19ad3acb32deaa4196"
    verifier_hash = "8462ffd6be01c9bd9ef1ac8f6b878a92d8233a6d7b3f28b3a01d979b2df2982c"
    assert reader.reader_identity() == {"module_sha256": module_hash, "terminal_verifier_sha256": verifier_hash}
    assert preflight["run"].splitlines() == [
        "set -euo pipefail",
        '[[ "$(git rev-parse HEAD)" == "$REVIEWED_SOURCE_SHA" && "$REVIEWED_SOURCE_SHA" == "$GITHUB_SHA" && "$GITHUB_SHA" == "$RETENTION_WORKFLOW_SHA" ]]',
        'retention_checkout_status="$(git status --porcelain=v1 --untracked-files=all)"',
        '[[ -z "$retention_checkout_status" ]]',
        "printf '%s\\n' \\",
        "  '" + module_hash + "  batch-runner/codex_retention_result_intake.py' \\",
        "  '" + verifier_hash + "  batch-runner/codex_retention_ci.py' \\",
        "  | sha256sum --check --status",
    ]
    lines = read["run"].splitlines()
    assert lines[:8] == [
        "set -euo pipefail", "umask 077",
        '[[ -d "$RUNNER_TEMP" && ! -L "$RUNNER_TEMP" && -O "$RUNNER_TEMP" ]]',
        'retention_result_parent="$(mktemp -d "$RUNNER_TEMP/retention-result.XXXXXXXX")"',
        '[[ -d "$retention_result_parent" && ! -L "$retention_result_parent" && -O "$retention_result_parent" ]]',
        '[[ "$(stat -c \'%a\' "$retention_result_parent")" == 700 ]]',
        '[[ ! -e "$retention_result_parent/payload" && ! -L "$retention_result_parent/payload" ]]',
        "retention_read_status=0",
    ]
    assert len(lines) == 24
    assert lines[-7:] == [
        "# Only the reviewed reader's safe receipt is public. Partials stay private.",
        "retention_receipt_status=0",
        'tee -a "$GITHUB_STEP_SUMMARY" < "$retention_result_parent/receipt.json" || retention_receipt_status=$?',
        "if (( retention_read_status != 0 )); then",
        '  exit "$retention_read_status"',
        "fi",
        'exit "$retention_receipt_status"',
    ]
    command_line = next(line for line in read["run"].replace("\\\n", "").splitlines() if line.startswith("env -u "))
    command = shlex.split(command_line)
    stripped = ("GITHUB_TOKEN", "GH_TOKEN", "ACTIONS_ID_TOKEN_REQUEST_TOKEN", "ACTIONS_ID_TOKEN_REQUEST_URL", "ACTIONS_RUNTIME_TOKEN")
    prefix = ["env", *itertools.chain.from_iterable(("-u", name) for name in stripped),
              "timeout", "--signal=KILL", "180s", "python3", "batch-runner/codex_retention_result_intake.py"]
    assert command[:len(prefix)] == prefix
    argv = ["--read", "--discover-terminal", "--expected-producer-source", reader.PRODUCER_SOURCE,
            "--expected-request-sha256", reader.REQUEST_SHA256, "--cell-id", reader.controller.FIRST_CELL_ID,
            "--expected-reader-sha256", module_hash, "--output", "$retention_result_parent/payload"]
    assert command[len(prefix):] == [*argv, ">", "$retention_result_parent/receipt.json", "2>",
                                    "$retention_result_parent/stderr.log", "||", "retention_read_status=$?"]
    assert "HF_TOKEN" not in command_line and "stderr.log" not in "\n".join(lines[-7:])
    assert reader.output.PUBLICATION_SECONDS == 120 and reader.output.REQUEST_SECONDS == 30
    assert reader.output.MAX_TOTAL_BYTES == 128 * 1024 * 1024

    effects = []

    def forbidden(*args, **kwargs):
        effects.append(True)
        raise AssertionError("result-read workflow regression crossed a live boundary")

    for owner, name in ((reader.output, "_hf_client"), (reader.output, "_time_bound"),
                        (reader.retained, "_target"), (reader.ci, "execute"),
                        (reader.ci.LocalTransport, "__init__"), (reader.ci._Admission, "__init__"),
                        (CodexTaskDeadlineStore, "__init__"), (CodexTaskDeadline, "admit_attempt")):
        monkeypatch.setattr(owner, name, forbidden)
    # Real CLI parsing, fixed byte/registration bindings and the existing explicit
    # token prerequisite. No supplied credential, fake transport or success verdict.
    destination = tmp_path / "retained-result"
    with monkeypatch.context() as context:
        context.setattr(reader.os, "environ", {})
        assert reader.main([str(destination) if arg == "$retention_result_parent/payload" else arg for arg in argv]) == 2
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"intake_verified": False, "reason": "explicit_hf_token_required",
        "launch_authorized": False, "grading_launched": False, "admission_attempted": False,
        "grade": None, "invoice_complete": False, "commands": []}
    assert captured.err == "" and str(destination) not in captured.out
    assert not (destination / reader.MARKER).exists() and effects == []
