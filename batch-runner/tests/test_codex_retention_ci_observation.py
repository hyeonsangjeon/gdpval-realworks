"""One non-authorizing locator observation, with real CLI and workflow routing."""

import json
import itertools
import shlex

import yaml

import codex_retention_ci as adapter
import codex_retention_fresh_r1_result_intake as reader
from core.codex_task_deadline import CodexTaskDeadline, CodexTaskDeadlineStore
from .test_codex_budget_pilot import offline  # noqa: F401; unchanged live-boundary guards
from .test_codex_retention_ci import _assert_retention_execution_workflow_contract
from .test_codex_retention_ci_read_result import _boolean


def test_retention_execution_workflow_contract_is_shared():
    _assert_retention_execution_workflow_contract()


def _assert_retention_mode_routes():
    """Shared pure YAML assertions; no locator, credential or private fixture."""
    workflow = yaml.safe_load((adapter.ROOT / adapter.WORKFLOW).read_bytes())
    dispatch = workflow.get("on", workflow.get(True))["workflow_dispatch"]["inputs"]
    assert set(dispatch) == {"reviewed_source_sha", "cell_id", "prepare", "execute", "observe_locator", "read_result", "observe_terminal", "observe_budget"}
    assert all(dispatch[name]["default"] is False for name in ("prepare", "execute", "observe_locator", "read_result", "observe_terminal", "observe_budget"))
    assert dispatch["observe_locator"]["type"] == "boolean"
    assert dispatch["read_result"]["type"] == "boolean"
    assert dispatch["observe_terminal"]["type"] == "boolean"
    assert dispatch["observe_budget"]["type"] == "boolean"
    jobs = workflow["jobs"]
    assert set(jobs) == {adapter.PREPARE_JOB, adapter.APPROVE_JOB, adapter.EXECUTE_JOB}
    prepare, approve, execute = (jobs[name] for name in (adapter.PREPARE_JOB, adapter.APPROVE_JOB, adapter.EXECUTE_JOB))
    assert workflow["permissions"] == {"contents": "read"}
    assert "permissions" not in prepare and approve["permissions"] == {}
    assert approve["environment"] == {"name": "grading"} and "environment" not in execute
    assert execute["permissions"] == {"contents": "read", "actions": "read", "id-token": "write"}
    assert all(job["runs-on"] == "ubuntu-22.04" for job in jobs.values())
    assert workflow["concurrency"] == {"group": "codex-budget-pilot-ci-20260923-01", "cancel-in-progress": False}
    assert prepare["if"] == "github.repository == 'hyeonsangjeon/gdpval-realworks' && github.ref == 'refs/heads/main'"
    gate = prepare["steps"][0]
    assert gate == execute["steps"][0]
    assert gate["env"] == {"OBSERVE_LOCATOR_ONLY": "${{ inputs.observe_locator }}",
                           "PREPARE_REQUESTED": "${{ inputs.prepare }}", "EXECUTE_REQUESTED": "${{ inputs.execute }}",
                           "READ_RESULT_ONLY": "${{ inputs.read_result }}", "OBSERVE_TERMINAL_ONLY": "${{ inputs.observe_terminal }}",
                           "OBSERVE_BUDGET_ONLY": "${{ inputs.observe_budget }}"}
    assert gate["run"].splitlines() == [
        "set -euo pipefail",
        '[[ "$READ_RESULT_ONLY" != true || ( "$PREPARE_REQUESTED" == false && "$EXECUTE_REQUESTED" == false && "$OBSERVE_LOCATOR_ONLY" == false && "$OBSERVE_TERMINAL_ONLY" == false ) ]]',
        '[[ "$OBSERVE_TERMINAL_ONLY" != true || ( "$PREPARE_REQUESTED" == false && "$EXECUTE_REQUESTED" == false && "$OBSERVE_LOCATOR_ONLY" == false && "$READ_RESULT_ONLY" == false ) ]]',
        '[[ "$OBSERVE_LOCATOR_ONLY" != true || ( "$PREPARE_REQUESTED" == false && "$EXECUTE_REQUESTED" == false ) ]]',
        '[[ "$OBSERVE_BUDGET_ONLY" != true || ( "$PREPARE_REQUESTED" == false && "$EXECUTE_REQUESTED" == false && "$OBSERVE_LOCATOR_ONLY" == false && "$READ_RESULT_ONLY" == false && "$OBSERVE_TERMINAL_ONLY" == false ) ]]',
        '[[ "$OBSERVE_BUDGET_ONLY" != true || "$SELECTED_CELL" == ' + adapter.controller.TASK5_FRESH_R2_CELL_ID + ' ]]',
        '[[ "$REVIEWED_SOURCE_SHA" =~ ^[0-9a-f]{40}$ ]]',
        '[[ "$REVIEWED_SOURCE_SHA" == "$GITHUB_SHA" && "$GITHUB_SHA" == "$RETENTION_WORKFLOW_SHA" ]]',
        '[[ "$GITHUB_EVENT_NAME" == workflow_dispatch && "$GITHUB_RUN_ATTEMPT" == 1 ]]',
        '[[ "$SELECTED_CELL" == ' + adapter.controller.FIRST_CELL_ID + ' || "$SELECTED_CELL" == ' + adapter.controller.FRESH_CELL_ID + ' || "$SELECTED_CELL" == ' + adapter.controller.FRESH_R2_CELL_ID + ' || "$SELECTED_CELL" == ' + adapter.controller.KEEP_R2_CELL_ID + ' || "$SELECTED_CELL" == ' + adapter.controller.TASK5_FRESH_R1_CELL_ID + ' || "$SELECTED_CELL" == ' + adapter.controller.TASK5_KEEP_R1_CELL_ID + ' || "$SELECTED_CELL" == ' + adapter.controller.TASK5_KEEP_R2_CELL_ID + ' || "$SELECTED_CELL" == ' + adapter.controller.TASK5_FRESH_R2_CELL_ID + ' ]]',
        '[[ "$READ_RESULT_ONLY" != true || ( "$SELECTED_CELL" == ' + adapter.controller.FIRST_CELL_ID + ' || "$SELECTED_CELL" == ' + adapter.controller.FRESH_CELL_ID + ' || "$SELECTED_CELL" == ' + adapter.controller.FRESH_R2_CELL_ID + ' || "$SELECTED_CELL" == ' + adapter.controller.KEEP_R2_CELL_ID + ' || "$SELECTED_CELL" == ' + adapter.controller.TASK5_FRESH_R1_CELL_ID + ' || "$SELECTED_CELL" == ' + adapter.controller.TASK5_KEEP_R1_CELL_ID + ' || "$SELECTED_CELL" == ' + adapter.controller.TASK5_KEEP_R2_CELL_ID + ' || "$SELECTED_CELL" == ' + adapter.controller.TASK5_FRESH_R2_CELL_ID + ' ) ]]',
        '[[ "$OBSERVE_LOCATOR_ONLY" != true || "$SELECTED_CELL" == ' + adapter.controller.FIRST_CELL_ID + ' ]]',
        '[[ "$OBSERVE_TERMINAL_ONLY" != true || ( "$SELECTED_CELL" == ' + adapter.controller.FRESH_CELL_ID + ' || "$SELECTED_CELL" == ' + adapter.controller.FRESH_R2_CELL_ID + ' || "$SELECTED_CELL" == ' + adapter.controller.KEEP_R2_CELL_ID + ' || "$SELECTED_CELL" == ' + adapter.controller.TASK5_FRESH_R1_CELL_ID + ' || "$SELECTED_CELL" == ' + adapter.controller.TASK5_KEEP_R1_CELL_ID + ' || "$SELECTED_CELL" == ' + adapter.controller.TASK5_KEEP_R2_CELL_ID + ' || "$SELECTED_CELL" == ' + adapter.controller.TASK5_FRESH_R2_CELL_ID + ' ) ]]',
    ]
    # Evaluate the exact changed cell/mode expressions, not a substring route.
    read_cells = (adapter.controller.FIRST_CELL_ID, adapter.controller.FRESH_CELL_ID, adapter.controller.FRESH_R2_CELL_ID,
             adapter.controller.KEEP_R2_CELL_ID, adapter.controller.TASK5_FRESH_R1_CELL_ID,
             adapter.controller.TASK5_KEEP_R1_CELL_ID, adapter.controller.TASK5_KEEP_R2_CELL_ID,
             adapter.controller.TASK5_FRESH_R2_CELL_ID)
    cells = read_cells
    for selected in (*cells, "unregistered"):
        for preparing, executing, observing, reading, terminal, budget in itertools.product((False, True), repeat=6):
            values = {'"$PREPARE_REQUESTED"': preparing, '"$EXECUTE_REQUESTED"': executing,
                '"$OBSERVE_LOCATOR_ONLY"': observing, '"$READ_RESULT_ONLY"': reading,
                '"$OBSERVE_TERMINAL_ONLY"': terminal, '"$OBSERVE_BUDGET_ONLY"': budget,
                '"$SELECTED_CELL" == ' + adapter.controller.FIRST_CELL_ID: selected == adapter.controller.FIRST_CELL_ID,
                '"$SELECTED_CELL" == ' + adapter.controller.FRESH_CELL_ID: selected == adapter.controller.FRESH_CELL_ID,
                '"$SELECTED_CELL" == ' + adapter.controller.FRESH_R2_CELL_ID: selected == adapter.controller.FRESH_R2_CELL_ID,
                '"$SELECTED_CELL" == ' + adapter.controller.KEEP_R2_CELL_ID: selected == adapter.controller.KEEP_R2_CELL_ID,
                '"$SELECTED_CELL" == ' + adapter.controller.TASK5_FRESH_R1_CELL_ID: selected == adapter.controller.TASK5_FRESH_R1_CELL_ID,
                '"$SELECTED_CELL" == ' + adapter.controller.TASK5_KEEP_R1_CELL_ID: selected == adapter.controller.TASK5_KEEP_R1_CELL_ID,
                '"$SELECTED_CELL" == ' + adapter.controller.TASK5_KEEP_R2_CELL_ID: selected == adapter.controller.TASK5_KEEP_R2_CELL_ID,
                '"$SELECTED_CELL" == ' + adapter.controller.TASK5_FRESH_R2_CELL_ID: selected == adapter.controller.TASK5_FRESH_R2_CELL_ID}
            allowed = all(_boolean(line.removeprefix("[[ ").removesuffix(" ]]"), values)
                for line in [*gate["run"].splitlines()[1:6], *gate["run"].splitlines()[-4:]])
            expected = (selected in cells
                and not (reading and (preparing or executing or observing or terminal))
                and not (terminal and (preparing or executing or observing or reading))
                and not (observing and (preparing or executing))
                and not (budget and (preparing or executing or observing or reading or terminal))
                and (not budget or selected == adapter.controller.TASK5_FRESH_R2_CELL_ID)
                and (selected == adapter.controller.FIRST_CELL_ID or not observing)
                and (selected in read_cells[1:] or not terminal)
                and (not reading or selected in read_cells))
            assert allowed is expected
            if reading or terminal or budget:
                # Even spuriously successful/nonempty request outputs cannot
                # route either read mode into protected approval or execution.
                ready = {"inputs.prepare": preparing, "inputs.execute": executing,
                    "inputs.observe_locator": observing, "inputs.read_result": reading,
                    "inputs.observe_terminal": terminal, "inputs.observe_budget": budget,
                    "needs.retention-prepare.result == 'success'": True,
                    "needs.retention-prepare.outputs.request_sha256 != ''": True,
                    "needs.retention-approve.result == 'success'": True}
                assert not _boolean(approve["if"], ready)
                assert not _boolean(execute["if"], ready)
    facade = "python3 batch-runner/codex_retention_task5_fresh_r2.py"
    assert prepare["steps"][4]["run"].startswith(facade + " ")
    assert facade + " --prepare" in prepare["steps"][8]["run"]
    assert execute["steps"][10]["run"].startswith(facade + " --verify-approval ")
    assert facade + " --execute" in execute["steps"][-1]["run"]
    assert "retention-task4-fresh-r1-host" in execute["steps"][-1]["run"]
    assert "retention-first-cell-host" in execute["steps"][-1]["run"]
    assert "retention-task4-fresh-r2-host" in execute["steps"][-1]["run"]
    assert "retention-task4-keep-r2-host" in execute["steps"][-1]["run"]
    assert "retention-task5-fresh-r1-host" in execute["steps"][-1]["run"]
    assert "retention-task5-keep-r1-host" in execute["steps"][-1]["run"]
    assert "retention-task5-keep-r2-host" in execute["steps"][-1]["run"]
    assert "retention-task5-fresh-r2-host" in execute["steps"][-1]["run"]
    assert "codex_retention_result_intake.py --read --discover-terminal" in prepare["steps"][12]["run"]
    modes = "(inputs.execute || inputs.observe_locator) && !inputs.read_result && !inputs.observe_terminal && !inputs.observe_budget && !(inputs.observe_locator && (inputs.prepare || inputs.execute))"
    prepared = "needs.retention-prepare.result == 'success' && needs.retention-prepare.outputs.request_sha256 != ''"
    assert approve["needs"] == adapter.PREPARE_JOB and approve["if"] == modes + " && " + prepared
    assert execute["needs"] == [adapter.PREPARE_JOB, adapter.APPROVE_JOB]
    assert execute["if"] == modes + " && " + prepared + " && needs.retention-approve.result == 'success'"
    assert "this is not authenticated execution approval" in approve["steps"][0]["run"]
    assert len(prepare["steps"]) == 15
    assert execute["steps"][:9] == prepare["steps"][:9]
    assert prepare["steps"][4]["if"] == "inputs.read_result == false && inputs.observe_terminal == false && inputs.observe_budget == false"
    for step in prepare["steps"][5:9]:
        assert step["if"] == "inputs.prepare || inputs.execute || inputs.observe_locator"
    assert "no token, signed approval verification or admission follows" in prepare["steps"][8]["run"]
    assert "approve-retention-first-cell sha256:" in prepare["steps"][8]["run"]

    observation, *live_steps = execute["steps"][9:]
    assert observation["if"] == "inputs.observe_locator && !inputs.prepare && !inputs.execute"
    assert set(observation) == {"name", "if", "run"}
    assert len(live_steps) == 4
    assert all(step["if"] == "inputs.execute && !inputs.observe_locator" for step in live_steps)
    assert "--verify-approval" in live_steps[0]["run"]
    assert "diagnose_codex_sandbox_host.py" in live_steps[1]["run"]
    assert live_steps[2]["uses"] == "azure/login@f5d393ae46f8fde4be8b75f32e3fc50e654ad0ca"
    assert "codex_retention_task5_fresh_r2.py --execute" in live_steps[3]["run"]
    command = shlex.split(observation["run"])
    assert command[:7] == ["env", "-u", "ACTIONS_ID_TOKEN_REQUEST_TOKEN", "-u", "GITHUB_TOKEN",
                           "python3", "batch-runner/codex_retention_ci.py"]
    assert command[7:] == ["--observe-locator", "--reviewed-source-sha", "$REVIEWED_SOURCE_SHA", "--cell", "$SELECTED_CELL"]
    return command


def test_retention_keep_r2_routes_preserve_read_and_authority_boundaries():
    _assert_retention_execution_workflow_contract()
    _assert_retention_mode_routes()
    workflow = yaml.safe_load((adapter.ROOT / adapter.WORKFLOW).read_bytes())
    steps = workflow["jobs"][adapter.PREPARE_JOB]["steps"]
    # Existing read routes stay closed; the fixed keep/r2 reader joins them.
    read_only = "inputs.read_result && !inputs.observe_terminal && !inputs.observe_budget && !inputs.prepare && !inputs.execute && !inputs.observe_locator"
    terminal_only = ("((inputs.observe_terminal && !inputs.observe_budget) || (inputs.observe_budget && !inputs.observe_terminal && inputs.cell_id == '"
        + reader.TASK5_FRESH_R2.expectation.cell_id + "')) && !inputs.read_result && !inputs.prepare && !inputs.execute && !inputs.observe_locator")
    fixed_fresh = " && (" + " || ".join("inputs.cell_id == '" + binding.expectation.cell_id + "'"
                                       for binding in (reader.FRESH_R1, reader.FRESH_R2, reader.KEEP_R2,
                                                       reader.TASK5_FRESH_R1, reader.TASK5_KEEP_R1,
                                                       reader.TASK5_KEEP_R2, reader.TASK5_FRESH_R2)) + ")"
    assert steps[9]["if"] == steps[10]["if"] == read_only + fixed_fresh
    assert steps[13]["if"] == steps[14]["if"] == terminal_only + fixed_fresh
    assert steps[11]["if"] == steps[12]["if"] == read_only + " && inputs.cell_id == '" + adapter.controller.FIRST_CELL_ID + "'"
    identity = reader.reader_identity(binding=reader.KEEP_R2)
    expected_hashes = {
        "codex_retention_fresh_r1_result_intake.py": identity["module_sha256"],
        "codex_retention_task4_fresh_r2.py": identity["producer_r2_sha256"],
        "codex_retention_task4_keep_r2.py": identity["producer_keep_r2_sha256"],
        **{path.rsplit("/", 1)[-1]: digest for path, digest in reader.FROZEN.values()},
    }
    for index in (9, 13):
        preflight, read = steps[index:index + 2]
        assert preflight.get("env", {}) == ({} if index == 9 else {"OBSERVE_BUDGET_ONLY": "${{ inputs.observe_budget }}"})
        assert "secrets." not in preflight["run"]
        assert preflight["run"].startswith("set -euo pipefail\n")
        assert '"$REVIEWED_SOURCE_SHA" == "$GITHUB_SHA"' in preflight["run"]
        assert '"$(git rev-parse HEAD)" == "$REVIEWED_SOURCE_SHA"' in preflight["run"]
        for filename, digest in expected_hashes.items():
            assert "'" + digest + "  batch-runner/" + filename + "'" in preflight["run"]
        assert preflight["run"].count("sha256sum --check --status") == (7 if index == 9 else 8)
        assert read["env"] == {"HF_TOKEN": "${{ secrets.HF_TOKEN }}", **({} if index == 9 else {
            "OBSERVE_BUDGET_ONLY": "${{ inputs.observe_budget }}"})}
        assert "--expected-reader-sha256 " + identity["module_sha256"] in read["run"]
        assert adapter.controller.KEEP_R2_CELL_ID + ")" in read["run"]
        assert "retention_read_source=" + reader.KEEP_R2.expectation.source_sha in read["run"]
        assert "retention_read_request=" + reader.KEEP_R2.expectation.request_sha256 in read["run"]
    assert steps[13]["run"] == steps[9]["run"] + (
        'if [[ "$OBSERVE_BUDGET_ONLY" == true ]]; then\n'
        "  printf '%s\\n' '" + reader.BUDGET_PROJECTOR_PIN[1] + "  batch-runner/codex_budget_pilot_grade_readout.py' | sha256sum --check --status\n"
        'fi\n')
    assert expected_hashes["codex_retention_task4_fresh_r2.py"] == "8b387ec5d172f74c4e6d2e1b93973c674e973f3cbba47b640184c126312ab00f"
    print(json.dumps({"scope": "synthetic_keep_r2_route_only", "mode_cases": 576,
        "old_routes_preserved": True, "keep_r2_reads_added": True, "three_jobs": True,
        "current_pins_before_credentials": True}, sort_keys=True))


def test_retention_locator_observation_is_closed_and_separate(monkeypatch, capsys):
    command = _assert_retention_mode_routes()
    source = "a" * 40  # Syntax only; observation never claims this is reviewed source.
    argv = [{"$REVIEWED_SOURCE_SHA": source, "$SELECTED_CELL": adapter.controller.FIRST_CELL_ID}.get(arg, arg)
            for arg in command[7:]]
    effects = []

    def forbidden(*args, **kwargs):
        effects.append(True)
        raise AssertionError("locator observation crossed a credential or effect boundary")

    # Existing guard owners, not replacement validators or a successful transport.
    for owner, name in (
            (adapter.LocalTransport, "__init__"), (adapter.LocalTransport, "github_job_token"),
            (adapter.LocalTransport, "authority_opener"), (adapter.LocalTransport, "github"),
            (adapter.LocalTransport, "azure"), (adapter.LocalTransport, "process"),
            (adapter.LocalTransport, "child"), (adapter.intake, "_response"),
            (adapter.registration, "compile_plan"), (adapter.preparation, "prepare_packet"),
            (adapter.controller, "stage_runtime"), (adapter.controller, "execute_first_cell"),
            (adapter, "_cli_request"), (adapter, "execute"), (adapter, "verify_approval"),
            (adapter, "verify_job_origin"), (adapter._Admission, "__init__"),
            (CodexTaskDeadlineStore, "__init__"), (CodexTaskDeadline, "admit_attempt"),
            (adapter.retained, "_session"), (adapter.retained, "_lock")):
        monkeypatch.setattr(owner, name, forbidden)

    url_key = "ACTIONS_ID_TOKEN_REQUEST_URL"
    token_key = "ACTIONS_ID_TOKEN_REQUEST_TOKEN"
    private = "PRIVATE_OBSERVATION_SENTINEL"
    reads = []

    class GuardedEnvironment(dict):
        def __getitem__(self, key):
            if key in {token_key, "GITHUB_TOKEN", "HF_TOKEN"}:
                forbidden()
            if key == url_key:
                reads.append(key)
            return super().__getitem__(key)

        def get(self, key, default=None):
            try:
                return self[key]
            except KeyError:
                return default

        def copy(self):
            forbidden()

    tenant, plan, job = (f"00000000-0000-4000-8000-00000000000{number}" for number in (1, 2, 3))
    origin = "https://pipelines.actions.githubusercontent.com"
    route = f"/{tenant}/_apis/distributedtask/hubs/build/plans/{plan}/jobs/{job}/idtoken"
    accepted = origin + route + "?api-version=2.0"
    cases = (
        (accepted, None),
        ("https://[" + private, "url_parsed"),
        ("https://" + private + ".example.invalid/" + private + "/98765432123456789?x=" + private, "allowed_host_pattern"),
        (accepted + "&" + private, "query_parsed"),
        (origin + "/" + private * 512, "length_within_limit"),
        (None, "https"),
    )
    for locator, failed in cases:
        environment = GuardedEnvironment({token_key: private, "GITHUB_TOKEN": private, "HF_TOKEN": private})
        if locator is not None:
            environment[url_key] = locator
        reads.clear()
        with monkeypatch.context() as context:
            context.setattr(adapter.os, "environ", environment)
            context.setattr(adapter, "require_source", forbidden)
            assert adapter.main(argv) == 0
        captured = capsys.readouterr()
        payload = json.loads(captured.out)
        assert set(payload) == {"reason", "launch_authorized", "grading_launched", "issuance_locator"}
        assert payload["reason"] == "github_job_issuance_locator_observation_only"
        assert payload["launch_authorized"] is False and payload["grading_launched"] is False
        diagnostic = payload["issuance_locator"]
        if failed is None:
            assert all(diagnostic["checks"].values()) and not diagnostic["truncated"]
        else:
            assert diagnostic["checks"][failed] is False
        if failed in {"url_parsed", "length_within_limit"}:
            assert diagnostic["route_skeleton"] == []
        refusal = adapter.RetentionCIRefused("github_job_issuance_locator_refused")
        refusal.issuance_locator = diagnostic
        assert adapter._closed_locator_diagnostic(refusal) == diagnostic
        assert {**adapter._refusal_payload(refusal), "reason": payload["reason"]} == payload
        assert len(captured.out) <= 2048 and captured.err == ""
        for secret in (private, tenant, plan, job, origin, "98765432123456789", source, "https://"):
            assert secret not in captured.out
        assert reads == [url_key] and effects == []

    invalid = [([mode], "retention_ci_verification_refused:OutputPublicationRefused")
               for mode in ("--prepare", "--verify-approval", "--execute")]
    invalid += [([option, private], "locator_observation_inputs_refused") for option in (
        "--historical-root", "--original-root", "--request-sha256", "--request-out", "--host-state")]
    invalid += [(["--cell", private], "only_registered_ordinal_zero_supported"),
                (["--reviewed-source-sha", private], "exact_reviewed_source_required")]
    for extra, reason in invalid:
        reads.clear()
        with monkeypatch.context() as context:
            context.setattr(adapter.os, "environ", GuardedEnvironment({url_key: accepted, token_key: private}))
            context.setattr(adapter, "require_source", forbidden)
            assert adapter.main([*argv, *extra]) == 2
        captured = capsys.readouterr()
        assert json.loads(captured.out) == {"reason": reason, "launch_authorized": False, "grading_launched": False}
        assert captured.err == "" and reads == [] and effects == []

    # Normal modes still enter the real source predicate, never the observer.
    for mode in ([], ["--prepare"], ["--verify-approval"], ["--execute"]):
        assert adapter.main(["--reviewed-source-sha", "not-a-source-sha", *mode]) == 2
        captured = capsys.readouterr()
        assert json.loads(captured.out) == {"reason": "exact_reviewed_source_required",
                                           "launch_authorized": False, "grading_launched": False}
        assert captured.err == "" and effects == []
