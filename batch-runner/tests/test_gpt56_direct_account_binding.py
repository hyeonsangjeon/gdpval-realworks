"""One offline regression for direct-v1 project-null evidence and ID binding.

The existing frozen-source, synthetic input and runtime guards are reused.
Only the four candidate source digests are renewed inside test-owned fixtures;
the checked-in registration, frozen grader and real source checks stay intact.
"""

import hashlib
import json
import os
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

import gpt56_foundry_evidence_intake as evidence
import gpt56_pilot_config_bundle as configs
import gpt56_pilot_deployment_binding as binding
import gpt56_pilot_identity_plan as identity
import gpt56_pilot_input_bundle as inputs
import gpt56_pilot_input_capture as capture
import gpt56_sol_codex_pilot_preflight as pilot
import step1_prepare_tasks as step1
from .test_gpt56_foundry_evidence_intake import OPTIONS, _json, _offline, _parse_cache, _seed, _tree
from .test_gpt56_pilot_deployment_binding import (
    PRIVATE, RAW_IDS, _fresh, _options, _publish, deployment_seeds, no_runtime,
)
from .test_gpt56_pilot_identity_plan import (
    TASK_IDS, _no_execution, source_seed as legacy_source_seed,
)
from .test_gpt56_pilot_input_bundle import _activate, _copy, input_seeds
from .test_gpt56_pilot_input_capture import MANIFEST, _runtime_paths, runtime_guards
from .test_gpt56_sol_codex_pilot_preflight import offline_only

CODE = (
    "batch-runner/gpt56_foundry_evidence_intake.py",
    "batch-runner/gpt56_pilot_deployment_binding.py",
    "batch-runner/gpt56_pilot_input_capture.py",
    "batch-runner/gpt56_sol_codex_pilot_preflight.py",
)
CANARY = "Bearer private-canary-DO-NOT-PUBLISH"


def _digest(data):
    return {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}


@pytest.fixture(scope="module")
def source_seed(request):
    # In a Gitless candidate, the same approved 8ac891 fixture archive is
    # extracted once before pytest. Repository runs use the original fixture.
    locator = os.environ.get("P5_APPROVED_PILOT_FIXTURE")
    frozen = Path(locator) if locator else request.getfixturevalue("approved_pilot_source")
    assert frozen.is_dir() and not frozen.is_symlink()
    files = dict(legacy_source_seed.__wrapped__(frozen))
    plan = yaml.safe_load(files[pilot.ACTIVE_PLAN])
    assert all(_digest(files[name])["sha256"] == digest for name, digest in plan["source_pins"].items())
    candidate = Path(__file__).resolve().parents[2]
    for name in CODE:
        files[name] = (candidate / name).read_bytes()
        plan["source_pins"][name] = _digest(files[name])["sha256"]
    files[pilot.ACTIVE_PLAN] = _json(plan)
    return tuple(sorted(files.items()))


def _direct_case(parent, input_seeds, seed, monkeypatch):
    base = tuple((name, data) for name, data in input_seeds(False)
                 if name.startswith(("source/", "references/")) or name == "source.parquet")
    _copy(base, parent)
    for role, data in (("account", RAW_IDS[0]), ("deployment", RAW_IDS[2])):
        _copy(((PRIVATE + "/" + role + ".txt", data),), parent)
    _activate(monkeypatch, parent / "source")
    plan = pilot.load_plan(pilot.PLAN)
    raw = dict(seed)
    intake = json.loads(raw[evidence.INTAKE_PATH])
    intake["plan_sha256"] = pilot.seal(plan)
    for claim in intake["claims"]:
        name = "artifacts/" + claim["role"] + ".json"
        record = json.loads(raw[name])
        record["subject"]["account"]["resource_id_sha256"] = _digest(RAW_IDS[0])["sha256"]
        record["subject"]["deployment"]["resource_id_sha256"] = _digest(RAW_IDS[2])["sha256"]
        record["subject"]["project"] = None
        if claim["role"] == "identity":
            record["observed"] = deepcopy(record["subject"])
        raw[name] = _json(record)
        claim["artifact"] = {"path": name, **_digest(raw[name])}
    raw[evidence.INTAKE_PATH] = _json(intake)
    _copy(tuple(raw.items()), parent / "raw-evidence")
    evidence.publish_foundry_evidence(source=parent / "raw-evidence", destination=parent / "evidence", **OPTIONS)
    upstream = {"evidence_bundle": parent / "evidence", **OPTIONS}
    identity.publish_pilot_identity(plan, destination=parent / "identity", **upstream)
    configs.materialize_pilot_config_bundle(plan, identity_bundle=parent / "identity",
                                          destination=parent / "configs", **upstream)
    inputs.materialize_pilot_input_bundle(
        plan, config_bundle=parent / "configs", identity_bundle=parent / "identity",
        dataset_parquet=parent / "source.parquet", reference_root=parent / "references",
        destination=parent / "inputs", **upstream,
    )
    options = _options(parent)
    options.pop("project_resource_id_file")
    return SimpleNamespace(parent=parent, plan=plan, options=options, raw=raw)


def _changed_evidence(case, destination, change):
    raw = dict(case.raw)
    intake = json.loads(raw[evidence.INTAKE_PATH])
    for claim in intake["claims"]:
        name = "artifacts/" + claim["role"] + ".json"
        document = json.loads(raw[name])
        change(document)
        raw[name] = _json(document)
        claim["artifact"] = {"path": name, **_digest(raw[name])}
    raw[evidence.INTAKE_PATH] = _json(intake)
    _copy(tuple(raw.items()), destination)


def _before_write_refusal(case, destination, *, options=None, plan=None, match=None):
    with pytest.raises(binding.PilotDeploymentBindingRefused, match=match) as failure:
        binding.materialize_pilot_deployment_binding(
            case.plan if plan is None else plan, destination=destination,
            **(case.options if options is None else options),
        )
    assert CANARY not in str(failure.value) and PRIVATE not in str(failure.value)
    assert not destination.exists()
    assert not destination.with_name(destination.name + binding.RESERVATION_SUFFIX).exists()


def test_direct_v1_account_binding(
    tmp_path, monkeypatch, capsys, input_seeds, deployment_seeds, _seed, offline_only,
):
    with capsys.disabled():
        print("P5 direct-account: real synthetic upstream preparation", flush=True)
    current = Path(__file__).resolve().parents[2]
    fixed_plan = (current / pilot.ACTIVE_PLAN).read_bytes()
    case = _direct_case(tmp_path / "direct", input_seeds, _seed, monkeypatch)
    assert not (case.parent / PRIVATE / "project.txt").exists()
    before_source = _tree(case.parent / "source")
    result = binding.materialize_pilot_deployment_binding(
        case.plan, destination=case.parent / "deployment", **case.options,
    )
    assert binding.verify_pilot_deployment_binding(
        case.plan, bundle_root=case.parent / "deployment", **case.options,
    ) == result
    document = result.as_dict()
    assert set(document["resource_files"]) == {"account", "deployment"}
    assert document["resource_files"]["account"] == {"role": "account_resource_id", "encoding": "utf-8", **_digest(RAW_IDS[0])}
    assert document["resource_files"]["deployment"] == {"role": "deployment_resource_id", "encoding": "utf-8", **_digest(RAW_IDS[2])}
    assert document["launch_allowed"] is document["full_220_allowed"] is False
    observed = evidence.verify_foundry_evidence(bundle_root=case.parent / "evidence", **OPTIONS).as_dict()
    assert observed["evidence_complete"] is True
    assert all(claim["evidence"]["subject"]["project"] is None for claim in observed["claims"].values())
    assert observed["claims"]["identity"]["evidence"]["observed"]["project"] is None
    assert observed["launch_enabled"] is observed["full_220_enabled"] is False
    argv = [item for key, value in case.options.items() for item in ("--" + key.replace("_", "-"), str(value))]
    assert binding.main(["--verify-bundle", str(case.parent / "deployment"), *argv]) == 0

    with capsys.disabled():
        print("P5 direct-account: real local capture and preflight", flush=True)
    rows = json.loads((case.parent / "inputs" / inputs.READY_PATH).read_bytes())["source_tasks"]
    manifest = {"_schema_version": 4, "_summary": {"active_policy": "deliverable_only"},
                "tasks": {row["task_id"]: {key: row[key] for key in ("needs_files", "source_projection_sha256")}
                          for row in rows},
                "reference_files": {record["path"]: {key: record[key] for key in ("size", "sha256")}
                                    for row in rows for record in row["reference_files"]}}
    _copy(((MANIFEST, _json(manifest)),), case.parent / "workspace")
    context = replace(_runtime_paths(monkeypatch, case.parent), project_resource_id_file=None)
    candidate = case.parent / "deployment" / binding.CANDIDATE_PATH
    config, tasks = capture.prepare_pilot_inputs(context, dataset_root=context.input_bundle, config_path=candidate)
    assert [task.task_id for task in tasks] == TASK_IDS
    assert config.execution.codex["reasoning_effort"] == "max"
    assert config.execution.codex["model_context_window"] == 1_000_000
    step1.prepare_tasks(str(candidate), pilot_capture_sources=context)
    report = pilot.inspect_plan(case.plan, **vars(context), capture_workspace=case.parent / "workspace")
    assert report["configuration_valid"] is True
    assert report["deployment_binding_gate"]["deployment_binding_complete"] is True
    assert report["pre_execution_capture_gate"]["capture_complete"] is True
    assert "live_inference_identity_and_wire_unverified" in report["launch_blockers"]
    assert report["launch_allowed"] is report["full_220_allowed"] is False
    assert _tree(case.parent / "source") == before_source

    with capsys.disabled():
        print("P5 direct-account: required evidence, integrity and route refusals", flush=True)
    for field in ("account", "deployment", "served_model"):
        def absent(document, field=field):
            document["subject"][field] = None
            if document["role"] == "identity":
                document["observed"][field] = None
        root = tmp_path / ("missing-" + field)
        _changed_evidence(case, root, absent)
        refused = evidence.compile_foundry_evidence(source=root, **OPTIONS)
        assert "identity.subject." + field in refused.missing
        assert refused.as_dict()["evidence_complete"] is False
        with pytest.raises(evidence.EvidenceIntakeRefused):
            evidence.publish_foundry_evidence(source=root, destination=tmp_path / ("unready-" + field), **OPTIONS)

    for field in ("reasoning_effort", "accepted_input_tokens"):
        role = "reasoning" if field == "reasoning_effort" else "context"
        def absent_observation(document, field=field, role=role):
            if document["role"] == role:
                document["observed"][field] = None
        root = tmp_path / ("missing-" + field)
        _changed_evidence(case, root, absent_observation)
        assert role + ".observed." + field in evidence.compile_foundry_evidence(source=root, **OPTIONS).missing

    for damage in ("missing-project-key", "partial-project", "cross-record-project", "malformed-private"):
        def mutate(document, damage=damage):
            if damage == "missing-project-key":
                del document["subject"]["project"]
            elif damage == "partial-project":
                document["subject"]["project"] = {"resource_id_sha256": None}
            elif damage == "cross-record-project" and document["role"] == "reasoning":
                document["subject"]["project"] = {"resource_id_sha256": "d" * 64}
            elif damage == "malformed-private":
                document["subject"]["account"] = CANARY
        root = tmp_path / damage
        _changed_evidence(case, root, mutate)
        with pytest.raises(evidence.EvidenceIntakeRefused) as failure:
            evidence.compile_foundry_evidence(source=root, **OPTIONS)
        assert CANARY not in str(failure.value)

    for role in ("account", "deployment"):
        _before_write_refusal(case, tmp_path / ("no-" + role),
                              options={**case.options, role + "_resource_id_file": None})
    path = case.options["deployment_resource_id_file"]
    original = path.read_bytes()
    for name, data in (("wrong-hash", original + b"/"),
                       ("wrong-account", original.replace(b"fixture-foundry", b"other-foundry")),
                       ("private-id", CANARY.encode())):
        path.write_bytes(data)
        _before_write_refusal(case, tmp_path / name)
        path.write_bytes(original)
    for profile in ("project-ci", "unknown-route"):
        changed = deepcopy(case.plan)
        changed["foundry_route"]["route_profile"] = profile
        assert pilot._project_resource_required(changed)
        _before_write_refusal(case, tmp_path / profile, plan=changed)
    unknown = deepcopy(case.plan)
    unknown["foundry_route"]["route_profile"] = "unknown-route"
    assert pilot.inspect_plan(unknown)["configuration_valid"] is False

    with capsys.disabled():
        print("P5 direct-account: legacy binding and source-pin refusals", flush=True)
    legacy = _fresh(deployment_seeds, tmp_path / "legacy", monkeypatch)
    legacy_result = _publish(legacy)
    assert set(legacy_result.as_dict()["resource_files"]) == set(binding.RESOURCE_ROLES)
    _before_write_refusal(legacy, tmp_path / "missing-recorded-project",
                          options={**legacy.options, "project_resource_id_file": None},
                          match="project_evidence_requires_resource_file")
    legacy_report = pilot.inspect_plan(legacy.plan, deployment_binding=legacy.root,
                                      **{**legacy.options, "project_resource_id_file": None})
    assert legacy_report["deployment_binding_gate"]["deployment_binding_complete"] is False
    assert legacy_report["launch_allowed"] is False

    _activate(monkeypatch, case.parent / "source")
    changed_source = case.parent / "source" / CODE[1]
    changed_source.write_bytes(changed_source.read_bytes() + b"\n# synthetic source drift\n")
    _before_write_refusal(case, tmp_path / "source-drift")
    _activate(monkeypatch, current)
    unregistered = pilot.inspect_plan(pilot.load_plan(pilot.PLAN))
    assert unregistered["configuration_valid"] is False
    assert {"source_pin:" + name for name in CODE} <= set(unregistered["configuration_problems"])
    assert unregistered["launch_allowed"] is unregistered["full_220_allowed"] is False
    assert (current / pilot.ACTIVE_PLAN).read_bytes() == fixed_plan
    assert offline_only == []
    output = capsys.readouterr()
    assert CANARY not in output.out + output.err
    assert all(value.decode() not in output.out + output.err for value in RAW_IDS)
    with capsys.disabled():
        print("P5 direct-account: completed; no launch authority", flush=True)
