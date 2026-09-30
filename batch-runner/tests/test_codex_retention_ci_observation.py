"""One non-authorizing locator observation, with real CLI and workflow routing."""

import json
import shlex

import yaml

import codex_retention_ci as adapter
from core.codex_task_deadline import CodexTaskDeadline, CodexTaskDeadlineStore
from .test_codex_budget_pilot import offline  # noqa: F401; unchanged live-boundary guards


def test_retention_locator_observation_is_closed_and_separate(monkeypatch, capsys):
    workflow = yaml.safe_load((adapter.ROOT / adapter.WORKFLOW).read_bytes())
    dispatch = workflow.get("on", workflow.get(True))["workflow_dispatch"]["inputs"]
    assert set(dispatch) == {"reviewed_source_sha", "cell_id", "prepare", "execute", "observe_locator", "read_result"}
    assert all(dispatch[name]["default"] is False for name in ("prepare", "execute", "observe_locator", "read_result"))
    assert dispatch["observe_locator"]["type"] == "boolean"
    assert dispatch["read_result"]["type"] == "boolean"
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
                           "READ_RESULT_ONLY": "${{ inputs.read_result }}"}
    assert gate["run"].splitlines() == [
        "set -euo pipefail",
        '[[ "$READ_RESULT_ONLY" != true || ( "$PREPARE_REQUESTED" == false && "$EXECUTE_REQUESTED" == false && "$OBSERVE_LOCATOR_ONLY" == false ) ]]',
        '[[ "$OBSERVE_LOCATOR_ONLY" != true || ( "$PREPARE_REQUESTED" == false && "$EXECUTE_REQUESTED" == false ) ]]',
        '[[ "$REVIEWED_SOURCE_SHA" =~ ^[0-9a-f]{40}$ ]]',
        '[[ "$REVIEWED_SOURCE_SHA" == "$GITHUB_SHA" && "$GITHUB_SHA" == "$RETENTION_WORKFLOW_SHA" ]]',
        '[[ "$GITHUB_EVENT_NAME" == workflow_dispatch && "$GITHUB_RUN_ATTEMPT" == 1 ]]',
        '[[ "$SELECTED_CELL" == ' + adapter.controller.FIRST_CELL_ID + ' ]]',
    ]
    modes = "(inputs.execute || inputs.observe_locator) && !inputs.read_result && !(inputs.observe_locator && (inputs.prepare || inputs.execute))"
    prepared = "needs.retention-prepare.result == 'success' && needs.retention-prepare.outputs.request_sha256 != ''"
    assert approve["needs"] == adapter.PREPARE_JOB and approve["if"] == modes + " && " + prepared
    assert execute["needs"] == [adapter.PREPARE_JOB, adapter.APPROVE_JOB]
    assert execute["if"] == modes + " && " + prepared + " && needs.retention-approve.result == 'success'"
    assert "this is not authenticated execution approval" in approve["steps"][0]["run"]
    assert len(prepare["steps"]) == 11
    assert execute["steps"][:9] == prepare["steps"][:9]
    assert prepare["steps"][4]["if"] == "inputs.read_result == false"
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
    assert "codex_retention_ci.py --execute" in live_steps[3]["run"]
    command = shlex.split(observation["run"])
    assert command[:7] == ["env", "-u", "ACTIONS_ID_TOKEN_REQUEST_TOKEN", "-u", "GITHUB_TOKEN",
                           "python3", "batch-runner/codex_retention_ci.py"]
    assert command[7:] == ["--observe-locator", "--reviewed-source-sha", "$REVIEWED_SOURCE_SHA", "--cell", "$SELECTED_CELL"]
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
