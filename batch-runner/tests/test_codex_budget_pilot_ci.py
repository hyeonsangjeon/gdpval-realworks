"""One-cell CLI and workflow contract; only tiny synthetic pipeline children."""

from __future__ import annotations

import copy
from decimal import Decimal
import json
import os
from pathlib import Path
import subprocess

import pytest
import yaml

import codex_budget_pilot as pilot
import codex_budget_pilot_ci as ci
from core.cost_receipts import CostReceipt
from core.result_fingerprint import inference_result_fingerprint
from .test_codex_budget_pilot import FakeChildren, offline, read_plan, read_state, scenario  # noqa: F401


class CICellChildren(FakeChildren):
    """Existing fake pipeline, with concrete ownership/timeout forwarding checks."""

    def __init__(self, sources, task_ids):
        super().__init__(sources, task_ids)
        self.source_checks = []
        self.forwarded = []
        self.stop = None
        self.receipt_cell = None

    def require_source(self, plan, parent):
        self.source_checks.append(plan["reviewed_source_sha"])
        if not self.reviewed:
            raise pilot.PilotDispatchRefused("reviewed_clean_source_required")
        return {"tree_sha": "b" * 40, "common": "synthetic-source-boundary"}

    def process(self, command, **options):
        path, binding = options["ownership"]
        stage, key = binding["stage"], binding["cell_id"]
        assert path.name == "owned-child.json"
        assert options["timeout"] == (300 if stage == "prepare" else 10860) or stage == "infer"
        assert len(options["pass_fds"]) == 1
        self.forwarded.append((stage, key, options["timeout"], dict(binding)))
        owner = {**pilot._owner_state(binding["plan_sha256"]), **binding, "pid": 123,
                 "phase": "running", "tree_reaped": False, "owner_reaped": False}
        pilot._save(path, owner)
        try:
            result = super().process(command, **options)
            if stage == "infer" and key == self.receipt_cell:
                output = options["cwd"] / "workspace" / Path(pilot.RESULT).name
                payload = json.loads(output.read_text())
                receipt = CostReceipt(
                    status="partial", known_cost_usd=Decimal("0.01"), model_cost_usd=Decimal("0.01"),
                    model_calls=1, usage={"input_tokens": 12, "output_tokens": 3},
                    missing_reasons=("synthetic_missing_cost",),
                ).as_dict()
                # Valid private component identity fields must not be copied to
                # public output, even when a receipt carries them legitimately.
                receipt["components"] = [{
                    "name": "generation", "stage": "generation", "retry_kind": "none", "status": "partial",
                    "known_cost_usd": 0.01, "model_calls": 1, "usage": {"input_tokens": 12, "output_tokens": 3},
                    "missing_reasons": ["synthetic_missing_cost"],
                    "provider": "synthetic-private-account", "deployment": "/private/native/secret-name",
                }]
                payload["results"][0]["problem_solving_cost"] = receipt
                payload["result_fingerprint"] = inference_result_fingerprint(payload)
                output.write_text(json.dumps(payload))
            if stage == "infer" and self.stop == "timeout":
                raise subprocess.TimeoutExpired(command, options["timeout"])
            if stage == "infer" and self.stop == "unresolved":
                raise pilot.OwnedChildCleanupRefused("owned_child_cleanup_unconfirmed")
            return result
        finally:
            unresolved = stage == "infer" and self.stop == "unresolved"
            owner.update(phase="cleanup_unresolved" if unresolved else "reaped",
                         tree_reaped=not unresolved, owner_reaped=not unresolved,
                         reason="owned_child_cleanup_unconfirmed" if unresolved else "timeout" if self.stop == "timeout" else "exited",
                         exit_code=None if unresolved or self.stop == "timeout" else 0)
            pilot._save(path, owner)


@pytest.fixture
def ci_scenario(scenario, monkeypatch):
    for name, value in {
        "GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": ci.REPOSITORY,
        "GITHUB_REF": "refs/heads/main", "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_SHA": "1" * 40, "PILOT_WORKFLOW_SHA": "1" * 40, "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_WORKFLOW_REF": ci.REPOSITORY + "/" + ci.WORKFLOW + "@refs/heads/main",
        "RUNNER_OS": "Linux", "ImageOS": "ubuntu22", "GITHUB_RUN_ID": "1234",
        "GITHUB_JOB": "cell", "RUNNER_NAME": "synthetic-ci-host",
    }.items():
        monkeypatch.setenv(name, value)
    scenario.transport = CICellChildren(scenario.sources, scenario.ids)
    scenario.argv[0:2] = ["--campaign-id", ci.CAMPAIGN]
    scenario.selected = scenario.ids[0] + "_B_r1"  # The reference-bearing synthetic task.
    scenario.envelope = scenario.host / "completion.json"
    scenario.argv += ["--cell", scenario.selected, "--completion-out", str(scenario.envelope)]
    return scenario


def invoke(scenario, *options):
    return ci.main([*scenario.argv, *options], _test_transport=scenario.transport)


def assert_other_cells_unrun(scenario):
    plan = read_plan(scenario)
    for cell in plan["cells"]:
        if cell["cell_id"] != scenario.selected:
            assert read_state(scenario, cell["cell_id"]) == pilot._cell_state(plan, cell)
            assert not (scenario.root / cell["roles"]["checkout"]).exists()
            assert not (scenario.root / cell["roles"]["deadline"]).exists()
    assert len(plan["cells"]) == 30


def test_ci_registered_cell_plan_default_preserves_matrix(ci_scenario):
    s = ci_scenario
    assert invoke(s) == 0
    assert s.transport.calls == [] and s.transport.model_admissions == []
    plan = read_plan(s)
    assert plan["run_id"] == ci.CAMPAIGN
    assert plan["order"] == [f"{task}_{arm}_r{repeat}" for task in s.ids for arm, repeat in pilot.ORDER]
    assert plan["ci"]["selected_cell_id"] == s.selected
    assert plan["ci"]["host"]["policy"] == ci.HOST_POLICY
    assert plan["launch_authorized_by_plan"] is False and plan["grading_launched"] is False
    record = pilot._load(s.envelope)
    assert record["status"] == "pending" and record["verified_inputs_sha256"] is None
    assert record["receipt"] is None and record["http_request_count"] is None
    assert not (s.root / "ci-inputs.json").exists()
    assert_other_cells_unrun(s)


@pytest.mark.parametrize("arm,repeat", [("A", 1), ("B", 1), ("C", 2)])
def test_ci_registered_cell_only_selected_and_known_usage(ci_scenario, monkeypatch, arm, repeat):
    s = ci_scenario
    s.selected = f"{s.ids[0]}_{arm}_r{repeat}"
    s.argv[s.argv.index("--cell") + 1] = s.selected
    if arm == "C":
        s.transport.receipt_cell = s.selected
    assert invoke(s, "--check-inputs") == 0
    assert s.transport.calls == []
    assert invoke(s, "--execute", "--resume") == 0
    assert [(stage, key) for stage, key, _ in s.transport.calls] == [("prepare", s.selected), ("infer", s.selected)]
    assert s.transport.peak == 1
    assert s.transport.forwarded[0][2] == 300 and s.transport.forwarded[1][2] == 10860
    state = read_state(s, s.selected)
    deadline = pilot._load(s.root / "cells" / s.selected / "deadline/deadlines.json")["cells"][s.ids[0]]
    assert deadline["expires_unix"] - deadline["started_unix"] == 10800
    assert len(deadline["attempts"]) == 1
    config = json.loads((s.root / "cells" / s.selected / "config.json").read_text())
    assert config["execution"]["timeout"] == 1800 and config["execution"]["max_retries"] == 3
    assert config["condition_a"]["model"]["deployment"] == "gpt-5.4"
    assert config["condition_a"]["model"]["reasoning_effort"] == "xhigh"
    assert config["execution"]["codex"]["task_deadline"] == {"condition": arm, "repetition": repeat}
    record = pilot._load(s.envelope)
    assert record["status"] == "succeeded" and record["cleanup_confirmed"] is True
    assert record["exit_code"] == 0 and record["child_invocations"] == 1
    assert record["receipt"] is None if arm != "C" else record["receipt"]["status"] == "partial"
    if arm == "C":
        assert record["receipt"]["usage"]["input_tokens"] == 12
        assert record["receipt"]["usage"]["output_tokens"] == 3
        assert record["receipt"]["usage"]["cached_input_tokens"] is None
        assert record["receipt"]["estimated_cost_usd"] is None and record["receipt"]["known_cost_usd"] == 0.01
    before = list(s.transport.calls)
    assert invoke(s, "--execute", "--resume") == 0
    assert s.transport.calls == before and read_state(s, s.selected) == state
    assert pilot._load(s.envelope)["receipt"] == record["receipt"]
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")
    assert invoke(s, "--execute", "--resume") == 2
    assert s.transport.calls == before
    assert pilot._load(s.root / "cells" / s.selected / "deadline/deadlines.json")["cells"][s.ids[0]] == deadline
    assert_other_cells_unrun(s)


@pytest.mark.parametrize("expired", [False, True])
def test_ci_registered_cell_same_host_restore_keeps_clock_and_partials(ci_scenario, expired):
    s = ci_scenario
    s.transport.interrupt = (s.selected, "attempt")
    assert invoke(s, "--execute") == 130
    assert pilot._load(s.envelope)["status"] == "unresolved"
    deadline_path = s.root / "cells" / s.selected / "deadline/deadlines.json"
    before = pilot._load(deadline_path)["cells"][s.ids[0]]
    partial = s.root / "cells" / s.selected / "native-workspaces/attempt-0/partial.txt"
    assert partial.read_bytes() == b"synthetic partial; never a model result"
    replacement = CICellChildren(s.sources, s.ids)
    replacement.clock.now = s.transport.clock.now + (10801 if expired else 15)
    s.transport = replacement  # New client/process facade; the durable host state is real.
    assert invoke(s, "--execute", "--resume") == (1 if expired else 0)
    after = pilot._load(deadline_path)["cells"][s.ids[0]]
    assert (after["started_unix"], after["expires_unix"]) == (before["started_unix"], before["expires_unix"])
    assert len(after["attempts"]) == (1 if expired else 2)
    assert len(replacement.model_admissions) == (0 if expired else 1)
    assert [row[0] for row in replacement.calls] == ["infer"]
    assert replacement.forwarded[0][2] == (60 if expired else 10844)
    assert partial.read_bytes() == b"synthetic partial; never a model result"
    assert_other_cells_unrun(s)


@pytest.mark.parametrize("changed", ["campaign", "cell", "source"])
def test_ci_registered_cell_invalid_identity_refuses_before_child(ci_scenario, changed):
    s = ci_scenario
    option, value = {
        "campaign": ("--campaign-id", "budget_pilot_20260923_01"),
        "cell": ("--cell", s.ids[0] + "_C_r3"),
        "source": ("--reviewed-source-sha", "2" * 40),
    }[changed]
    s.argv[s.argv.index(option) + 1] = value
    assert invoke(s, "--execute") == 2
    assert not s.root.exists() and not s.envelope.exists()
    assert s.transport.calls == []


@pytest.mark.parametrize("changed", ["missing", "bytes"])
def test_ci_registered_cell_missing_or_changed_originals_refuse(ci_scenario, caplog, changed):
    s = ci_scenario
    if changed == "missing":
        for option in ("--dataset-parquet", "--reference-root", "--step0-manifest"):
            start = s.argv.index(option)
            del s.argv[start:start + 2]
    else:
        s.sources.parquet.write_bytes(s.sources.parquet.read_bytes() + b"changed synthetic input")
    assert invoke(s, "--execute") == 2
    assert s.transport.calls == [] and s.transport.model_admissions == []
    if changed == "missing":
        assert all(role in caplog.text for role in ci.INPUT_ROLES)
    record = pilot._load(s.envelope)
    assert record["reason"] == ("missing_original_inputs" if changed == "missing" else "canonical_original_inputs_refused")
    assert record["status"] == "unresolved" and record["receipt"] is None
    assert str(s.host) not in caplog.text
    assert_other_cells_unrun(s)


@pytest.mark.parametrize("changed", ["config", "host", "unselected"])
def test_ci_registered_cell_restore_cannot_adopt_changed_state(ci_scenario, monkeypatch, changed):
    s = ci_scenario
    assert invoke(s, "--check-inputs") == 0
    if changed == "config":
        path = s.root / "cells" / s.selected / "config.json"
        path.write_bytes(path.read_bytes() + b" ")
    elif changed == "host":
        monkeypatch.setenv("RUNNER_NAME", "different-live-host")
    else:
        key = read_plan(s)["order"][-1]
        state = read_state(s, key)
        state.update(status="running", phase="preparing")
        pilot._save(s.root / "cells" / key / "cell.json", state)
    assert invoke(s, "--execute", "--resume") == 2
    assert s.transport.calls == [] and s.transport.model_admissions == []


@pytest.mark.parametrize("stop", ["timeout", "unresolved"])
def test_ci_registered_cell_cleanup_and_timeout_forwarding(ci_scenario, stop):
    s = ci_scenario
    s.transport.stop = stop
    s.transport.outcomes[s.selected] = "missing_result"
    assert invoke(s, "--execute") == (1 if stop == "timeout" else 2)
    owner = pilot._load(s.root / "owned-child.json")
    record = pilot._load(s.envelope)
    assert owner["phase"] == ("reaped" if stop == "timeout" else "cleanup_unresolved")
    assert record["status"] == ("stopped" if stop == "timeout" else "unresolved")
    assert record["receipt"] is None and record["exit_code"] is None
    if stop == "timeout":
        assert record["timeout"] is True and record["cleanup_confirmed"] is True
    before = list(s.transport.calls)
    assert invoke(s, "--execute", "--resume") == (1 if stop == "timeout" else 2)
    assert s.transport.calls == before
    assert (s.root / "cells" / s.selected / "native-workspaces/attempt-0/partial.txt").exists()
    assert_other_cells_unrun(s)


def test_ci_registered_cell_publication_rejects_private_or_forged_fields(ci_scenario):
    s = ci_scenario
    s.transport.receipt_cell = s.selected
    assert invoke(s, "--execute") == 0
    safe = pilot._load(s.envelope)
    text = s.envelope.read_text()
    for forbidden in ("synthetic-private-account", "/private/native/secret-name", str(s.host),
                      "CODEX_HOME", "Bearer ", "components", "native-workspaces", "transcript"):
        assert forbidden not in text
    assert ci.main(["--verify-envelope", str(s.envelope)]) == 0
    corruptions = [
        lambda record: record.update(auth_store="/private/auth"),
        lambda record: record.update(reason="Bearer synthetic-token"),
        lambda record: record["receipt"]["usage"].update(private_token=7),
        lambda record: record["artifacts"].update(native_home="/private/home"),
        lambda record: record.update(cleanup_confirmed=False),
    ]
    for mutate in corruptions:
        record = copy.deepcopy(safe)
        mutate(record)
        pilot._save(s.envelope, record)
        assert ci.main(["--verify-envelope", str(s.envelope)]) == 2


def test_ci_registered_cell_reusable_source_contract(ci_scenario, monkeypatch):
    s = ci_scenario
    caller = ".github/workflows/synthetic-caller.yml"
    monkeypatch.setenv("GITHUB_WORKFLOW_REF", ci.REPOSITORY + "/" + caller + "@refs/heads/main")
    monkeypatch.setattr(pilot, "ROOT", s.host)
    path = s.host / caller
    path.parent.mkdir(parents=True)
    document = {"jobs": {"one": {"uses": "./" + ci.WORKFLOW}}}
    path.write_text(yaml.safe_dump(document))
    assert ci._require_ci_context("1" * 40)["workflow"] == caller
    document["jobs"]["one"]["uses"] = ci.REPOSITORY + "/" + ci.WORKFLOW + "@unreviewed"
    path.write_text(yaml.safe_dump(document))
    with pytest.raises(ci.CICellRefused, match="same_commit_single_cell"):
        ci._require_ci_context("1" * 40)


def test_ci_registered_cell_workflow_invocation_contract():
    text = (pilot.ROOT / ci.WORKFLOW).read_text()
    workflow = yaml.safe_load(text)
    triggers = workflow.get("on", workflow.get(True))
    assert set(triggers) == {"workflow_dispatch", "workflow_call"}
    for trigger in triggers.values():
        assert trigger["inputs"]["execute"]["default"] is False
        assert trigger["inputs"]["input_check"]["default"] is False
        assert trigger["inputs"]["reviewed_source_sha"]["required"] is True
        assert trigger["inputs"]["cell_id"]["required"] is True
        for key in ("input_release_id", "input_asset_id", "input_bundle_sha256"):
            assert trigger["inputs"][key]["type"] == "string" and trigger["inputs"][key]["required"] is False
    assert workflow["permissions"] == {"contents": "read", "id-token": "write"}
    assert workflow["concurrency"] == {"group": "codex-budget-pilot-ci-20260923-01", "cancel-in-progress": False}
    assert len(workflow["jobs"]) == 1
    job = workflow["jobs"]["cell"]
    assert job["runs-on"] == "ubuntu-22.04" and job["timeout-minutes"] == 240
    assert "strategy" not in job and "refs/heads/main" in job["if"]
    steps = job["steps"]
    boundary = steps[0]["run"]
    assert all(value in boundary for value in ("GITHUB_RUN_ATTEMPT", '"$GITHUB_SHA" == "$REVIEWED_SOURCE_SHA"',
                                              '"$PILOT_WORKFLOW_SHA" == "$REVIEWED_SOURCE_SHA"', "workflow_dispatch"))
    pins = {
        "actions/checkout": "fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09",
        "actions/setup-python": "5fda3b95a4ea91299a34e894583c3862153e4b97",
        "azure/login": "f5d393ae46f8fde4be8b75f32e3fc50e654ad0ca",
        "actions/upload-artifact": "043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",
    }
    for step in steps:
        if "uses" in step:
            name, sha = step["uses"].split("@")
            assert pins[name] == sha
    checkout = next(step for step in steps if step.get("uses", "").startswith("actions/checkout@"))
    assert checkout["with"] == {"ref": "${{ inputs.reviewed_source_sha }}", "persist-credentials": False}
    python = next(step for step in steps if step.get("uses", "").startswith("actions/setup-python@"))
    assert python["with"]["python-version"] == "3.10.12"
    plan = next(step for step in steps if step.get("id") == "plan")
    assert "--check-inputs" not in plan["run"] and "--execute" not in plan["run"]
    assert "codex_budget_pilot_ci.py" in plan["run"] and '--cell "$SELECTED_CELL"' in plan["run"]
    intake = next(step for step in steps if step.get("id") == "intake")
    assert intake["if"] == "(inputs.execute || inputs.input_check) && !inputs.output_target_check && !inputs.output_target_setup" and intake["timeout-minutes"] == 3
    assert intake["env"]["GITHUB_TOKEN"] == "${{ inputs.input_transport != 'hf_originals' && github.token || '' }}"
    assert intake["env"]["HF_TOKEN"] == "${{ inputs.input_transport == 'hf_originals' && secrets.HF_TOKEN || '' }}"
    assert all("GITHUB_TOKEN" not in step.get("env", {}) for step in steps if step != intake)
    assert "timeout --signal=TERM --kill-after=5s 120s" in intake["run"]
    assert "codex_ci_input_intake.py --input-check" in intake["run"]
    assert "--resume --check-inputs" in intake["run"] and "--execute" not in intake["run"]
    assert intake["run"].index("--input-check") < intake["run"].index("--resume --check-inputs") < intake["run"].index('echo "verified=true"')
    assert '"$INPUT_RELEASE_ID"' in intake["run"] and '"$INPUT_ASSET_ID"' in intake["run"] and '"$INPUT_BUNDLE_SHA256"' in intake["run"]
    login = next(step for step in steps if step.get("uses", "").startswith("azure/login@"))
    admission = "success() && inputs.execute && !inputs.input_check && !inputs.output_target_check && !inputs.output_target_setup && steps.intake.outputs.verified == 'true'"
    assert steps.index(plan) < steps.index(intake) < steps.index(login) and login["if"] == admission
    assert set(login["with"]) == {"client-id", "tenant-id", "subscription-id"}
    execution = next(step for step in steps if "--resume --execute" in step.get("run", ""))
    assert execution["if"] == admission and '--cell "$SELECTED_CELL"' in execution["run"]
    assert execution["env"]["CODEX_FOUNDRY_CONNECTION_CONFIRMED"] == "1"
    assert execution["env"]["AZURE_AI_ROUTE_PROFILE"] == "direct-v1"
    publication = next(step for step in steps if step.get("id") == "publication")
    assert "--verify-envelope" in publication["run"]
    upload = next(step for step in steps if step.get("uses", "").startswith("actions/upload-artifact@"))
    assert upload["if"] == "always() && steps.publication.outputs.safe == 'true'"
    assert upload["with"]["path"] == "${{ runner.temp }}/budget-pilot-ci-completion.json"
    assert not any(word in text for word in ("download-artifact", "CODEX_HOME", "relay_checkpoint.py", "step7_upload", "azure/login@main"))
