"""Static workflow routing and real fixed-reader refusal, without credentials."""

import itertools
import json
import re
import shlex

import yaml

import codex_retention_fresh_r1_result_intake as fresh_reader
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
    assert set(inputs) == {"reviewed_source_sha", "cell_id", "prepare", "observe_locator", "execute", "read_result", "observe_terminal"}
    mode_names = ("prepare", "observe_locator", "execute", "read_result", "observe_terminal")
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
    assert len(steps) == 15 and execute["steps"][:9] == steps[:9]
    gate, checkout = steps[:2]
    assert not any("secret" in value or "token" in value for value in gate["env"].values())
    assert checkout["with"] == {"ref": "${{ inputs.reviewed_source_sha }}", "fetch-depth": 0, "persist-credentials": False}
    fresh_preflight, fresh_read, preflight, read, terminal_preflight, terminal_read = steps[9:]
    read_condition = "inputs.read_result && !inputs.observe_terminal && !inputs.prepare && !inputs.execute && !inputs.observe_locator"
    assert preflight["if"] == read["if"] == read_condition + " && inputs.cell_id == '" + reader.controller.FIRST_CELL_ID + "'"
    assert fresh_preflight["if"] == fresh_read["if"] == read_condition + " && inputs.cell_id == '" + fresh_reader.fresh.CELL_ID + "'"
    assert terminal_preflight["if"] == terminal_read["if"] == (
        "inputs.observe_terminal && !inputs.read_result && !inputs.prepare && !inputs.execute && !inputs.observe_locator"
        " && inputs.cell_id == '" + fresh_reader.fresh.CELL_ID + "'")
    assert set(preflight) == {"name", "if", "shell", "run"} and preflight["shell"] == "bash"
    assert read["env"] == {"HF_TOKEN": "${{ secrets.HF_TOKEN }}"}
    assert set(read) == {"name", "if", "timeout-minutes", "env", "shell", "run"}
    assert read["shell"] == "bash" and read["timeout-minutes"] == 4
    assert set(fresh_preflight) == set(preflight) and fresh_preflight["shell"] == "bash"
    assert set(fresh_read) == set(read) and fresh_read["env"] == read["env"]
    assert fresh_read["shell"] == "bash" and fresh_read["timeout-minutes"] == 4
    assert set(terminal_preflight) == set(preflight) and terminal_preflight["shell"] == "bash"
    assert set(terminal_read) == set(read) and terminal_read["env"] == read["env"]
    assert terminal_read["shell"] == "bash" and terminal_read["timeout-minutes"] == 4
    assert all(module not in step.get("run", "") for module in (
        "codex_retention_result_intake.py", "codex_retention_fresh_r1_result_intake.py")
        for job in (approve, execute) for step in job["steps"])
    assert all("upload-artifact" not in step.get("uses", "") for job in jobs.values() for step in job["steps"])

    # Three producer cells, two old result cells and unsupported selectors,
    # with all 32 mode combinations,
    # using the actual YAML and source-gate expressions.
    # Read exclusion must hold even if a request output is spuriously nonempty.
    cells = (reader.controller.FIRST_CELL_ID, fresh_reader.fresh.CELL_ID, reader.controller.FRESH_R2_CELL_ID)
    assert gate["run"].splitlines()[-4:] == [
        '[[ "$SELECTED_CELL" == ' + cells[0] + ' || "$SELECTED_CELL" == ' + cells[1] + ' || "$SELECTED_CELL" == ' + cells[2] + ' ]]',
        '[[ "$READ_RESULT_ONLY" != true || ( "$SELECTED_CELL" == ' + cells[0] + ' || "$SELECTED_CELL" == ' + cells[1] + ' ) ]]',
        '[[ "$OBSERVE_LOCATOR_ONLY" != true || "$SELECTED_CELL" == ' + cells[0] + ' ]]',
        '[[ "$OBSERVE_TERMINAL_ONLY" != true || "$SELECTED_CELL" == ' + cells[1] + ' ]]',
    ]
    for selected in (*cells, "unregistered", reader.registration.TASK4 + "_retention_bundle_v1_keep_r2"):
        for values in itertools.product((False, True), repeat=5):
            modes = dict(zip(mode_names, values))
            prepared, observed, executed, reading, terminal = values
            replacements = {"inputs." + name: value for name, value in modes.items()}
            replacements.update({"inputs.cell_id == '" + cell + "'": selected == cell for cell in cells})
            gate_values = {'"$' + name + '"': modes[value.removeprefix("${{ inputs.").removesuffix(" }}")]
                           for name, value in gate["env"].items()}
            gate_values.update({'"$SELECTED_CELL" == ' + cell: selected == cell for cell in cells})
            admitted_route = all(_boolean(line.removeprefix("[[ ").removesuffix(" ]]"), gate_values)
                for line in [*gate["run"].splitlines()[1:4], *gate["run"].splitlines()[-4:]])
            expected = (selected in cells and not (reading and (prepared or observed or executed or terminal))
                and not (terminal and (prepared or observed or executed or reading))
                and not (observed and (prepared or executed)) and (not observed or selected == cells[0])
                and (not terminal or selected == cells[1]) and (not reading or selected in cells[:2]))
            assert admitted_route is expected
            reachable = [index for index, step in enumerate(steps)
                         if admitted_route and _boolean(step.get("if", "true"), replacements)]
            if not expected:
                assert reachable == []  # First-step refusal precedes checkout and every secret.
            elif reading:
                assert reachable == [0, 1, 2, 3, *( (11, 12) if selected == cells[0] else (9, 10))]
                assert [steps[index].get("env") for index in reachable
                        if "HF_TOKEN" in steps[index].get("env", {})] == [read["env"]]
            elif terminal:
                assert reachable == [0, 1, 2, 3, 13, 14]
                assert [steps[index].get("env") for index in reachable
                        if "HF_TOKEN" in steps[index].get("env", {})] == [terminal_read["env"]]
            elif prepared or observed or executed:
                assert reachable == list(range(9))
            else:
                assert reachable == list(range(5))  # Unchanged inert plan default.
            ready = {**replacements, "needs.retention-prepare.result == 'success'": admitted_route,
                     "needs.retention-prepare.outputs.request_sha256 != ''": True,
                     "needs.retention-approve.result == 'success'": True}
            assert _boolean(approve["if"], ready) is (expected and not reading and not terminal and (executed or observed))
            assert _boolean(execute["if"], ready) is (expected and not reading and not terminal and (executed or observed))

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

    fresh_hash = fresh_reader.reader_identity()["module_sha256"]
    assert fresh_preflight["run"].splitlines() == [
        *preflight["run"].splitlines()[:5],
        "  '" + fresh_hash + "  batch-runner/codex_retention_fresh_r1_result_intake.py' \\",
        *["  '" + digest + "  batch-runner/" + name + "' \\" for name, digest in (
            ("codex_retention_result_intake.py", module_hash), ("codex_retention_ci.py", verifier_hash),
            ("codex_retention_task4_fresh_r1.py", "a0710039c33c17af85f226269ceeaccdb1c17bbc7238a46a15614226afed26e3"),
            ("codex_retention_first_cell.py", "a7c44ce7224b02f31865620e482d0ff6964f36d2b4c4753658e3ecfc72dcbc58"))],
        "  | sha256sum --check --status",
    ]
    fresh_script = read["run"].replace("codex_retention_result_intake.py", "codex_retention_fresh_r1_result_intake.py")
    for old, new in (("retention-result.XXXXXXXX", "retention-fresh-r1-result.XXXXXXXX"),
                     (reader.PRODUCER_SOURCE, fresh_reader.PRODUCER_SOURCE), (reader.REQUEST_SHA256, fresh_reader.REQUEST_SHA256),
                     (reader.controller.FIRST_CELL_ID, fresh_reader.fresh.CELL_ID), (module_hash, fresh_hash)):
        fresh_script = fresh_script.replace(old, new)
    assert fresh_read["run"] == fresh_script  # Same private destination, bounds, redaction and nonzero exits.
    assert terminal_preflight["run"] == fresh_preflight["run"]
    facade = "python3 batch-runner/codex_retention_task4_fresh_r2.py"
    assert steps[4]["run"].startswith(facade + " ")
    assert facade + " --prepare" in steps[8]["run"]
    assert execute["steps"][10]["run"].startswith(facade + " --verify-approval ")
    assert facade + " --execute" in execute["steps"][-1]["run"]
    for cell, namespace in zip(cells, ("retention-first-cell", "retention-task4-fresh-r1", "retention-task4-fresh-r2")):
        assert cell + ') retention_host="$RUNNER_TEMP/' + namespace + '-host" ;;' in execute["steps"][-1]["run"]
    terminal_script = fresh_script.replace("--read --discover-terminal", "--observe-terminal --discover-terminal")
    terminal_script = terminal_script.replace("retention-fresh-r1-result.XXXXXXXX", "retention-fresh-r1-terminal.XXXXXXXX")
    terminal_script = terminal_script.replace("retention_result_parent", "retention_terminal_parent").replace("/payload", "/evidence")
    assert terminal_read["run"] == terminal_script
    fresh_argv = argv.copy()
    for index, arg in enumerate(fresh_argv):
        fresh_argv[index] = {reader.PRODUCER_SOURCE: fresh_reader.PRODUCER_SOURCE,
            reader.REQUEST_SHA256: fresh_reader.REQUEST_SHA256, reader.controller.FIRST_CELL_ID: fresh_reader.fresh.CELL_ID,
            module_hash: fresh_hash}.get(arg, arg)

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
    fresh_destination = tmp_path / "fresh-result"
    with monkeypatch.context() as context:
        context.setattr(reader.os, "environ", {})
        assert fresh_reader.main([str(fresh_destination) if arg == "$retention_result_parent/payload"
                                  else arg for arg in fresh_argv]) == 2
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"intake_verified": False, "reason": "explicit_hf_token_required",
        "launch_authorized": False, "grading_launched": False, "admission_attempted": False, "replay_authorized": False,
        "grade": None, "invoice_complete": False, "commands": []}
    assert captured.err == "" and str(fresh_destination) not in captured.out
    assert not (fresh_destination / fresh_reader.MARKER).exists() and effects == []
    terminal_destination = tmp_path / "fresh-terminal"
    terminal_argv = ["--observe-terminal", *fresh_argv[1:]]
    with monkeypatch.context() as context:
        context.setattr(reader.os, "environ", {})
        assert fresh_reader.main([str(terminal_destination) if arg == "$retention_result_parent/payload"
                                  else arg for arg in terminal_argv]) == 2
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"terminal_verified": False, "reason": "explicit_hf_token_required",
        "launch_authorized": False, "grading_launched": False, "admission_attempted": False, "replay_authorized": False,
        "grade": None, "invoice_complete": False, "commands": []}
    assert captured.err == "" and str(terminal_destination) not in captured.out
    assert not (terminal_destination / fresh_reader.TERMINAL_MARKER).exists() and effects == []
