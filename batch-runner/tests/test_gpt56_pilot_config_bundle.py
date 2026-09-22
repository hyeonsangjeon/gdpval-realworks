"""One offline selector for exact inert pilot configs and ready-last publication."""

import hashlib
import json
import os
import sys
from functools import lru_cache

import pytest
import yaml

# Preserve the real class/static prompt-version reader before inherited guards.
import step8_grade as step8
import step1_prepare_tasks as step1
import gpt56_foundry_evidence_intake as evidence
import gpt56_pilot_config_bundle as bundle
import gpt56_pilot_identity_plan as identity
import gpt56_sol_codex_pilot_preflight as pilot
from core.experiment_config import ExperimentConfig
from .test_gpt56_evidence_preflight_gate import published_seed
from .test_gpt56_foundry_evidence_intake import (
    AS_OF, OPTIONS, REVIEWED, _json, _offline, _parse_cache, _seed, _tree,
)
from .test_gpt56_pilot_identity_plan import (
    TASK_IDS, _copy, _field_names, _no_execution, _set, identity_seeds, source_seed,
)
from .test_gpt56_sol_codex_pilot_preflight import offline_only

FILES = (bundle.RUNTIME_PATH, bundle.PREPARED_PATH, bundle.GRADING_PATH, bundle.LINKAGE_PATH)
SENTINEL = "private-input-MUST-NOT-APPEAR"


def _reservation(root):
    return root.with_name(root.name + bundle.RESERVATION_SUFFIX)


def _identity_reservation(root):
    return root.with_name(root.name + identity.RESERVATION_SUFFIX)


def _fresh(files, parent, linked=False):
    _copy(files, parent)
    options = {"evidence_bundle": parent / "bundle", **OPTIONS} if linked else {}
    return parent / "configs", parent / "identity", options


@pytest.fixture
def plan():
    return pilot.load_plan(pilot.PLAN)


@pytest.fixture(scope="module")
def config_seeds(tmp_path_factory, identity_seeds):
    """Real complete publication once per mode; share bytes, never verdicts/trees."""
    @lru_cache(maxsize=2)
    def prepare(linked=False):
        parent = tmp_path_factory.mktemp("pilot-config-seed")
        root, source, options = _fresh(identity_seeds(linked), parent, linked)
        result = bundle.materialize_pilot_config_bundle(
            pilot.load_plan(pilot.PLAN), identity_bundle=source, destination=root, **options,
        )
        assert (root / bundle.READY_PATH).read_bytes() == result.canonical_bytes()
        return _tree(parent)
    return prepare


@pytest.fixture
def installed(tmp_path, config_seeds, _no_execution):
    return _fresh(config_seeds(), tmp_path)


@pytest.mark.parametrize("linked", [False, True])
def test_real_validators_exact_pilot_scope_and_ready_last(plan, tmp_path, identity_seeds, linked, monkeypatch):
    root, source, options = _fresh(identity_seeds(linked), tmp_path, linked)
    before = _tree(tmp_path)
    writes, verifications, validated = [], [], []
    real_write, real_verify, real_validate = bundle._write_no_clobber, identity.verify_pilot_identity, step8.validate_grading_config

    def write(path, data):
        assert not (root / bundle.READY_PATH).exists()
        writes.append(path.name)
        return real_write(path, data)

    def verify(*args, **kwargs):
        result = real_verify(*args, **kwargs)
        verifications.append(result)
        return result

    def validate(config):
        validated.append(config["config_name"])
        return real_validate(config)

    monkeypatch.setattr(bundle, "_write_no_clobber", write)
    monkeypatch.setattr(identity, "verify_pilot_identity", verify)
    monkeypatch.setattr(step8, "validate_grading_config", validate)
    result = bundle.materialize_pilot_config_bundle(plan, identity_bundle=source, destination=root, **options)
    assert len(verifications) == 2 and verifications[0] == verifications[1]
    assert validated.count(pilot.RUN_ID + "_v2_sol_max") == 2
    assert writes == [root.name + bundle.RESERVATION_SUFFIX, *FILES, bundle.READY_PATH]
    assert bundle.verify_pilot_config_bundle(plan, identity_bundle=source, bundle_root=root, **options) == result
    assert _json(result.as_dict()) == result.canonical_bytes()
    assert result.sha256 == hashlib.sha256(result.canonical_bytes()).hexdigest()
    assert tuple(name for name, _ in result.files) == FILES
    for role, data in result.files:
        path = root / role
        assert path.read_bytes() == data == _json(json.loads(data))
        assert path.stat().st_nlink == 1 and not path.is_symlink()
    assert tuple((name, data) for name, data in _tree(tmp_path)
                 if name in {name for name, _ in before}) == before

    runtime = json.loads((root / bundle.RUNTIME_PATH).read_bytes())
    prepared = json.loads((root / bundle.PREPARED_PATH).read_bytes())
    grader = yaml.safe_load((root / bundle.GRADING_PATH).read_bytes())
    linkage = json.loads((root / bundle.LINKAGE_PATH).read_bytes())
    marker = result.as_dict()
    sealed = verifications[0].as_dict()
    assert runtime == {
        "template_version": "foundry-pilot-runtime-template-v1", "runnable": False,
        "deployment": None, "execution": None, "dispatch": sealed["dispatch"], "dataset": plan["dataset"],
        "developer_instructions": plan["developer_instructions"],
        "deployment_blocker": "actual_pilot_deployment_not_prepared",
        "launch_allowed": False, "full_220_allowed": False,
    }
    bundle._validate_runtime_template(runtime, plan, sealed["dispatch"])
    request = runtime["dispatch"]
    assert runtime["deployment"] is plan["foundry_identity"]["deployment"] is None
    assert request["identity"]["provider"] == "azure"
    assert request["identity"]["model"] == "gpt-5.6-sol" and request["identity"]["fast_mode"] is False
    assert request["identity"]["reasoning_effort"] == "max"
    assert request["foundry_route"] == plan["foundry_route"]
    assert request["foundry_route"]["endpoint_from_route"] is True
    assert request["foundry_route"]["provider_id"] == "gdpval-foundry"
    assert request["codex_request"] == {"reasoning_effort": "max", "model_context_window": 1000000}
    assert request["limits"]["timeout_seconds_per_attempt"] == 1800
    assert request["limits"]["infrastructure_retries_per_task"] == 3
    assert request["limits"]["self_qa_enabled"] is False
    assert request["limits"]["request_max_retries"] == request["limits"]["stream_max_retries"] == 0
    assert request["limits"]["resume_max_rounds"] == request["pilot_controls"]["relay_max_runs"] == 0
    assert request["limits"]["inactive_generic_token_settings"] == plan["limits"]["inactive_generic_token_settings"]
    assert request["results"]["publish_to_hf"] is request["results"]["submit_to_evals"] is False
    assert not {"experiment", "condition_a", "condition_b", "comparison_input_capture"} & set(runtime)

    for section in (request, prepared, linkage["dispatch"], linkage["grading"], marker):
        assert section["run_id"] == pilot.RUN_ID and section["condition"] == "codex_foundry"
        assert section["repeat"] == 1 and section["expected_task_count"] == 5
        assert section["task_ids"] == TASK_IDS
        assert section["ordered_task_ids_sha256"] == step8._ordered_task_ids_sha256(TASK_IDS)
        assert _json(section["tasks"]) == _json(sealed["dispatch"]["tasks"])
    assert prepared["dataset"] == plan["dataset"]
    assert prepared["developer_instructions"] == identity._identity(plan["developer_instructions"].encode())
    assert prepared["evidence_boundary"] == "registered_inputs_not_consumed_bytes"
    assert linkage["dispatch"] == sealed["dispatch"]
    assert linkage["grading"] == sealed["grading"]
    assert linkage["dispatch"]["limits"] == plan["limits"]
    assert linkage["dispatch"]["pilot_controls"] == plan["pilot"]
    assert linkage["dispatch"]["logical_attempts_per_task"] == 1
    assert linkage["dispatch"]["identity"]["fast_mode"] is False
    assert linkage["dispatch"]["cost"] == plan["cost"]
    assert linkage["grading"]["passes_per_task"] == 1
    assert linkage["grading"]["inference_revision"] is linkage["grading"]["inference_repo_id"] is None
    assert linkage["materialized_grader_source_hash"] is None
    assert linkage["grading_scope_binding"] == "inert_bundle_only_requires_future_inference_identity"

    template = pilot.load_plan(pilot.ROOT / pilot.GRADER)
    for key in ("schema_version", "judge", "rubric", "grader", "tpm_guard", "prompt"):
        assert _json(grader[key]) == _json(template[key])
    assert set(grader) == set(template) - {"rerun_identity"}
    assert grader["output"] == {**template["output"], "directory": "workspace/pilot-grades"}
    assert grader["config_name"] == pilot.RUN_ID + "_v2_sol_max"
    assert "rerun_identity" not in grader
    assert not {"task_ids", "pilot_scope", "inference_revision", "inference_repo_id"} & set(grader)
    # Validate the emitted config, not just the historical template.
    validation = json.loads(_json(grader))
    for key in ("template", "tool_template"):
        validation["prompt"][key] = str(pilot.ROOT / "batch-runner" / validation["prompt"][key])
    step8.validate_grading_config(validation)

    assert marker["files"] == {name: bundle._digest(data) for name, data in result.files}
    assert marker["identity_plan_sha256"] == verifications[0].sha256
    assert marker["contract_sha256"] == pilot.seal(plan)
    assert marker["source_pins"] == linkage["source_pins"] == plan["source_pins"]
    assert len(plan["source_pins"]) == 58 and set(plan["source_pins"]) == pilot.REQUIRED_SOURCES
    assert plan["config_bundle"] == pilot.CONFIG_BUNDLE
    assert marker["evidence_linkage"] == linkage["evidence_linkage"] == sealed["evidence_linkage"]
    if linked:
        assert set(marker["evidence_linkage"]) == {"ready_bundle_sha256", "reviewed_source_sha", "as_of"}
        assert marker["evidence_linkage"]["reviewed_source_sha"] == REVIEWED
        assert marker["evidence_linkage"]["as_of"] == AS_OF
        later = {**options, "as_of": "2026-09-20T04:00:00Z"}
        assert bundle.verify_pilot_config_bundle(plan, identity_bundle=source, bundle_root=root, **later) == result
    else:
        assert marker["evidence_linkage"] is None
    for document in (marker, linkage):
        assert document["launch_allowed"] is document["full_220_allowed"] is False
    assert plan["launch_enabled"] is plan["pilot"]["full_220_enabled"] is False
    all_bytes = result.canonical_bytes() + b"".join(data for _, data in result.files)
    assert not {"argv", "command", "endpoint", "claims", "observed", "account", "project", "credential"} & _field_names(
        [marker, linkage, runtime, prepared, grader])
    for private in (str(tmp_path).encode(), str(pilot.ROOT).encode(), b"dc36d6837a8f0899f8bfa4d32aae9a9f6805f3b0"):
        assert private not in all_bytes
    assert not (root / "workspace/step1_tasks_prepared.json").exists()
    report = pilot.inspect_plan(plan, identity_bundle=source, **options)
    expected = ["native_call_and_token_limits_unresolved", "prepared_input_bytes_unverified", "live_inference_identity_and_wire_unverified",
                "foundry_usage_and_tariff_mapping_unverified", "native_sandbox_and_result_bundle_host_unverified",
                "actual_pilot_deployment_not_prepared", "prepared_request_capture_unverified"] if linked else [
                    item for item in pilot.LAUNCH_BLOCKERS if item != identity.BLOCKER]
    assert report["launch_blockers"] == expected
    assert report["launch_allowed"] is report["full_220_allowed"] is False


@pytest.mark.parametrize("linked", [False, True])
def test_inert_template_is_refused_by_real_runtime_parser_and_entrypoint(
    plan, tmp_path, config_seeds, linked, monkeypatch, offline_only,
):
    from core import codex_runtime_config

    root, source, options = _fresh(config_seeds(linked), tmp_path, linked)
    result = bundle.verify_pilot_config_bundle(plan, identity_bundle=source, bundle_root=root, **options)
    path = root / bundle.RUNTIME_PATH
    runtime = json.loads(path.read_bytes())
    assert runtime["dispatch"]["identity"]["model"] == plan["identity"]["model"] == "gpt-5.6-sol"
    assert runtime["deployment"] is plan["foundry_identity"]["deployment"] is None
    assert runtime["runnable"] is False and runtime["execution"] is None
    assert runtime["deployment_blocker"] == "actual_pilot_deployment_not_prepared"
    before = _tree(root)

    def forbidden(*args, **kwargs):
        offline_only.append("runtime setup before inert-template refusal")
        raise AssertionError("inert runtime template reached execution setup")

    monkeypatch.setattr(step1, "GDPValDataLoader", forbidden)
    monkeypatch.setattr(step1, "resolve_publication_generation", forbidden)
    for name in ("CodexProviderSettings", "resolve_endpoint_setting", "provider_config_overrides"):
        monkeypatch.setattr(codex_runtime_config, name, forbidden)
    workspace = tmp_path / "workspace"
    monkeypatch.setattr(step1, "WORKSPACE_DIR", workspace)
    monkeypatch.setattr(sys, "argv", ["step1_prepare_tasks.py", "--config", str(path)])

    # Missing blocks would acquire runnable defaults. Explicit null execution
    # is rejected by the unchanged parser, before validation or any setup.
    for read in (lambda: ExperimentConfig.from_dict(runtime),
                 lambda: ExperimentConfig.from_yaml(str(path)), step1.main):
        with pytest.raises(AttributeError, match="'NoneType' object has no attribute 'get'"):
            read()
    assert not (workspace / "step1_tasks_prepared.json").exists()
    assert _tree(root) == before and offline_only == []
    assert not {"argv", "command", "endpoint", "credential"} & _field_names(
        [result.as_dict(), *(json.loads(data) for _, data in result.files)])


@pytest.mark.parametrize("keys,value", [
    (("deployment",), "gpt-5.6-sol"), (("deployment",), "pending-deployment"),
    (("deployment",), "a" * 64), (("runnable",), True), (("runnable",), 0),
    (("execution",), {}), (("execution",), {"mode": "codex_foundry"}),
    (("condition_a",), {"model": {"deployment": "gpt-5.6-sol"}}),
    (("dispatch", "identity", "model"), "gpt-5.6-sol-fast"),
    (("dataset", "revision"), "a" * 40), (("developer_instructions",), "changed"),
    (("deployment_blocker",), None),
])
def test_closed_runtime_template_rejects_deployment_or_request_drift(plan, installed, keys, value):
    root, _, _ = installed
    runtime = json.loads((root / bundle.RUNTIME_PATH).read_bytes())
    dispatch = json.loads((root / bundle.LINKAGE_PATH).read_bytes())["dispatch"]
    _set(runtime, keys, value)
    with pytest.raises(bundle.PilotConfigBundleRefused, match="runtime_template_"):
        bundle._validate_runtime_template(runtime, plan, dispatch)


@pytest.mark.parametrize("field", ["deployment", "execution", "runnable"])
def test_closed_runtime_template_cannot_omit_inert_controls(plan, installed, field):
    root, _, _ = installed
    runtime = json.loads((root / bundle.RUNTIME_PATH).read_bytes())
    dispatch = runtime["dispatch"]
    del runtime[field]
    with pytest.raises(bundle.PilotConfigBundleRefused, match="runtime_template_shape_invalid"):
        bundle._validate_runtime_template(runtime, plan, dispatch)


@pytest.mark.parametrize("mode", ["compile", "publish", "verify"])
def test_cli_determinism_and_read_only_verification(plan, installed, tmp_path, mode, capsys):
    root, source, options = installed
    expected = bundle.verify_pilot_config_bundle(plan, identity_bundle=source, bundle_root=root)
    before = _tree(tmp_path)
    args = ["--identity-bundle", str(source)]
    if mode == "publish":
        args += ["--destination", str(tmp_path / "relocated")]
    elif mode == "verify":
        args += ["--verify-bundle", str(root)]
    assert bundle.main(args) == 0
    assert json.loads(capsys.readouterr().out) == {
        "bundle_sha256": expected.sha256, "config_bundle_complete": True,
        "evidence_boundary": bundle.BOUNDARY, "launch_allowed": False, "full_220_allowed": False,
    }
    if mode == "publish":
        assert _tree(root) == _tree(tmp_path / "relocated")
        assert _reservation(root).read_bytes() == _reservation(tmp_path / "relocated").read_bytes()
    else:
        assert _tree(tmp_path) == before


@pytest.mark.parametrize("role", [*FILES, bundle.READY_PATH, "reservation"])
@pytest.mark.parametrize("damage", ["missing", "bytes", "noncanonical", "symlink", "hardlink"])
def test_each_member_and_reservation_is_exact_single_link_and_read_only(plan, installed, tmp_path, role, damage):
    root, source, _ = installed
    path = _reservation(root) if role == "reservation" else root / role
    data = path.read_bytes()
    if damage == "missing":
        path.unlink()
    elif damage in {"bytes", "noncanonical"}:
        path.write_bytes(b"{}" if damage == "bytes" else data + b"\n")
    else:
        other = tmp_path / "other"
        other.write_bytes(data)
        path.unlink()
        path.symlink_to(other) if damage == "symlink" else os.link(other, path)
    before = _tree(tmp_path)
    with pytest.raises(bundle.PilotConfigBundleRefused):
        bundle.verify_pilot_config_bundle(plan, identity_bundle=source, bundle_root=root)
    assert _tree(tmp_path) == before
    if damage == "hardlink":
        assert path.stat().st_nlink == 2
    if damage == "symlink":
        assert path.is_symlink()


@pytest.mark.parametrize("role,keys,value", [
    (bundle.RUNTIME_PATH, ("dispatch", "task_ids"), TASK_IDS[::-1]),
    (bundle.RUNTIME_PATH, ("dispatch", "identity", "model"), "gpt-5.6-sol-fast"),
    (bundle.RUNTIME_PATH, ("dispatch", "codex_request", "model_context_window"), 272000),
    (bundle.RUNTIME_PATH, ("dispatch", "limits", "infrastructure_retries_per_task"), 4),
    (bundle.RUNTIME_PATH, ("deployment",), "gpt-5.6-sol"),
    (bundle.RUNTIME_PATH, ("runnable",), True),
    (bundle.RUNTIME_PATH, ("execution",), {}),
    (bundle.GRADING_PATH, ("judge", "reasoning", "effort"), "low"),
    (bundle.GRADING_PATH, ("rubric", "revision"), "a" * 40),
    (bundle.PREPARED_PATH, ("tasks",), []),
    (bundle.PREPARED_PATH, ("dataset", "parquet_sha256"), "a" * 64),
    (bundle.LINKAGE_PATH, ("grading", "task_ids"), TASK_IDS + [TASK_IDS[0]]),
    (bundle.LINKAGE_PATH, ("grading", "inference_revision"), "a" * 40),
    (bundle.LINKAGE_PATH, ("dispatch", "condition"), "sandbox_v2"),
    (bundle.LINKAGE_PATH, ("dispatch", "repeat"), 2),
])
def test_self_consistent_forged_output_hashes_do_not_replace_real_derivation(plan, installed, role, keys, value):
    root, source, _ = installed
    payload = json.loads((root / role).read_bytes())
    _set(payload, keys, value)
    (root / role).write_bytes(_json(payload))
    marker = json.loads((root / bundle.READY_PATH).read_bytes())
    marker["files"][role] = bundle._digest((root / role).read_bytes())
    if role != bundle.LINKAGE_PATH:
        linkage = json.loads((root / bundle.LINKAGE_PATH).read_bytes())
        linkage["files"][role] = marker["files"][role]
        (root / bundle.LINKAGE_PATH).write_bytes(_json(linkage))
        marker["files"][bundle.LINKAGE_PATH] = bundle._digest(_json(linkage))
    forged = bundle.PilotConfigBundle(bundle._canonical_json(marker), ())
    (root / bundle.READY_PATH).write_bytes(forged.canonical_bytes())
    _reservation(root).write_bytes(bundle._reservation(forged))
    with pytest.raises(bundle.PilotConfigBundleRefused):
        bundle.verify_pilot_config_bundle(plan, identity_bundle=source, bundle_root=root)


@pytest.mark.parametrize("damage", ["missing-plan", "missing-ready", "missing-reservation", "forged-scope",
                                   "ready-drift", "reservation-drift", "symlink", "hardlink"])
def test_identity_bundle_is_reverified_before_any_write(plan, installed, tmp_path, damage, monkeypatch):
    _, source, _ = installed
    target = tmp_path / "refused"
    if damage.startswith("missing-"):
        {"missing-plan": source / identity.PLAN_PATH, "missing-ready": source / identity.READY_PATH,
         "missing-reservation": _identity_reservation(source)}[damage].unlink()
    elif damage == "forged-scope":
        document = json.loads((source / identity.PLAN_PATH).read_bytes())
        for key in ("dispatch", "grading"):
            document[key]["task_ids"] = TASK_IDS[::-1]
        forged = identity.PilotIdentityPlan(identity._canonical_json(document))
        (source / identity.PLAN_PATH).write_bytes(forged.canonical_bytes())
        (source / identity.READY_PATH).write_bytes(identity._ready(forged))
        _identity_reservation(source).write_bytes(identity._reservation(forged))
    elif damage.endswith("drift"):
        path = source / identity.READY_PATH if damage == "ready-drift" else _identity_reservation(source)
        path.write_bytes(path.read_bytes() + b"\n")
    else:
        path = source / identity.PLAN_PATH
        other = tmp_path / "other-identity"
        other.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(other) if damage == "symlink" else os.link(other, path)
    writes = []
    real = bundle._write_no_clobber

    def tracked(path, data):
        writes.append(path)
        return real(path, data)

    monkeypatch.setattr(bundle, "_write_no_clobber", tracked)
    before = _tree(tmp_path)
    with pytest.raises(bundle.PilotConfigBundleRefused):
        bundle.materialize_pilot_config_bundle(plan, identity_bundle=source, destination=target)
    assert writes == [] and _tree(tmp_path) == before
    assert not target.exists() and not _reservation(target).exists()


@pytest.mark.parametrize("keys,value", [
    (("base_sha",), "a" * 40), (("config_bundle", "source_base_sha"), "a" * 40),
    (("pilot", "run_id"), "wrong-run"), (("dataset", "tasks"), []),
    (("grading", "passes_per_task"), 2), (("launch_enabled",), True),
    (("pilot", "full_220_enabled"), True), (("source_pins",), {}),
    (("foundry_identity", "deployment"), "gpt-5.6-sol"),
])
def test_wrong_or_stale_active_contract_cannot_be_materialized(plan, installed, tmp_path, keys, value):
    _, source, _ = installed
    _set(plan, keys, value)
    target = tmp_path / "refused"
    with pytest.raises(bundle.PilotConfigBundleRefused):
        bundle.materialize_pilot_config_bundle(plan, identity_bundle=source, destination=target)
    assert not target.exists() and not _reservation(target).exists()


@pytest.mark.parametrize("role,damage", [
    (pilot.ACTIVE_PLAN, "bytes"), (pilot.GRADER, "bytes"),
    (pilot.CONFIG_BUNDLE["materializer"], "bytes"),
    ("batch-runner/prompts/grader_judge_v2.md", "bytes"),
    ("batch-runner/schemas/grade.schema.json", "missing"),
    ("batch-runner/core/grader.py", "hardlink"),
    ("batch-runner/core/grader.py", "symlink"),
    ("batch-runner/requirements-renderer.txt", "bytes"),
])
def test_real_source_pins_and_grader_closure_are_rechecked(plan, installed, tmp_path, source_seed, monkeypatch, role, damage):
    _, source, _ = installed
    checkout = tmp_path / "source"
    _copy(source_seed, checkout)
    monkeypatch.setattr(pilot, "ROOT", checkout)
    path = checkout / role
    if role == pilot.ACTIVE_PLAN:
        changed = yaml.safe_load(path.read_bytes())
        changed["pilot"]["run_id"] = "stale-run"
        path.write_bytes(_json(changed))
    elif damage == "missing":
        path.unlink()
    elif damage in {"hardlink", "symlink"}:
        other = tmp_path / "other-source"
        other.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(other) if damage == "symlink" else os.link(other, path)
    else:
        path.write_bytes(path.read_bytes() + b"\n# source drift\n")
    before = _tree(checkout)
    target = tmp_path / "refused"
    with pytest.raises(bundle.PilotConfigBundleRefused):
        bundle.materialize_pilot_config_bundle(plan, identity_bundle=source, destination=target)
    assert _tree(checkout) == before
    assert not target.exists() and not _reservation(target).exists()


@pytest.mark.parametrize("damage", ["omitted", "wrong-sha", "stale", "bad-time", "ready", "reservation",
                                   "artifact", "partial", "hardlink"])
def test_linked_evidence_is_reverified_not_copied_or_downgraded(plan, tmp_path, config_seeds, damage):
    root, source, options = _fresh(config_seeds(True), tmp_path, True)
    external = options["evidence_bundle"]
    if damage == "omitted":
        options = {}
    elif damage == "wrong-sha":
        options["reviewed_source_sha"] = "d" * 40
    elif damage in {"stale", "bad-time"}:
        options["as_of"] = "2026-10-02T00:00:00Z" if damage == "stale" else SENTINEL
    elif damage == "ready":
        (external / evidence.READY_PATH).unlink()
    elif damage == "reservation":
        external.with_name(external.name + ".foundry-evidence-reservation.json").unlink()
    elif damage == "partial":
        path = external / evidence.INTAKE_PATH
        intake = json.loads(path.read_bytes())
        intake["claims"][0]["artifact"] = None
        path.write_bytes(_json(intake))
    elif damage == "hardlink":
        os.link(external / "artifacts/identity.json", tmp_path / "linked-evidence")
    else:
        path = external / "artifacts/identity.json"
        path.write_bytes(path.read_bytes() + b"\n")
    before = _tree(root)
    with pytest.raises(bundle.PilotConfigBundleRefused):
        bundle.verify_pilot_config_bundle(plan, identity_bundle=source, bundle_root=root, **options)
    assert _tree(root) == before


@pytest.mark.parametrize("case", ["existing-directory", "existing-file", "reservation", "target-symlink",
                                 "parent-symlink", "traversal", "identity-overlap"])
def test_collisions_paths_and_partial_reuse_are_never_adopted(plan, installed, tmp_path, case):
    root, source, _ = installed
    target = tmp_path / "refused"
    if case == "existing-directory":
        target.mkdir()
    elif case == "existing-file":
        target.write_bytes(b"keep")
    elif case == "reservation":
        _reservation(target).write_bytes(b"partial reservation")
    elif case == "target-symlink":
        target.symlink_to(root, target_is_directory=True)
    elif case == "parent-symlink":
        alias = tmp_path / "alias"
        alias.symlink_to(tmp_path, target_is_directory=True)
        target = alias / "refused"
    elif case == "traversal":
        target = tmp_path / "unused" / ".." / "refused"
    else:
        target = source / "refused"
    before = _tree(tmp_path)
    with pytest.raises(bundle.PilotConfigBundleRefused):
        bundle.materialize_pilot_config_bundle(plan, identity_bundle=source, destination=target)
    assert _tree(tmp_path) == before
    # Even a complete existing bundle cannot be treated as an idempotent write.
    with pytest.raises(bundle.PilotConfigBundleRefused):
        bundle.materialize_pilot_config_bundle(plan, identity_bundle=source, destination=root)


@pytest.mark.parametrize("extra", ["file", "directory"])
def test_extra_bundle_members_refuse_verification(plan, installed, extra):
    root, source, _ = installed
    path = root / "unregistered"
    path.mkdir() if extra == "directory" else path.write_bytes(b"extra")
    with pytest.raises(bundle.PilotConfigBundleRefused):
        bundle.verify_pilot_config_bundle(plan, identity_bundle=source, bundle_root=root)


@pytest.mark.parametrize("fail_at", range(6))
def test_each_write_failure_leaves_no_ready_and_forbids_partial_reuse(plan, installed, tmp_path, monkeypatch, fail_at):
    _, source, _ = installed
    target, calls = tmp_path / "partial", []
    real = bundle._write_no_clobber

    def failing(path, data):
        calls.append(path.name)
        if len(calls) == fail_at + 1:
            raise OSError("injected publication failure")
        return real(path, data)

    monkeypatch.setattr(bundle, "_write_no_clobber", failing)
    with pytest.raises(bundle.PilotConfigBundleRefused):
        bundle.materialize_pilot_config_bundle(plan, identity_bundle=source, destination=target)
    assert len(calls) == fail_at + 1
    assert not (target / bundle.READY_PATH).exists()
    assert _reservation(target).exists() == (fail_at > 0)
    if target.exists():
        assert {path.name for path in target.iterdir()} == set(FILES[:max(0, fail_at - 1)])
    else:
        assert fail_at == 0
    if fail_at > 0:
        before = _tree(tmp_path)
        monkeypatch.setattr(bundle, "_write_no_clobber", real)
        with pytest.raises(bundle.PilotConfigBundleRefused):
            bundle.materialize_pilot_config_bundle(plan, identity_bundle=source, destination=target)
        with pytest.raises(bundle.PilotConfigBundleRefused):
            bundle.verify_pilot_config_bundle(plan, identity_bundle=source, bundle_root=target)
        assert _tree(tmp_path) == before


@pytest.mark.parametrize("damage", ["identity-ready", "identity-plan", "reservation", "runtime", "source-template"])
def test_mid_publication_drift_is_rechecked_before_ready(plan, installed, tmp_path, source_seed, monkeypatch, damage):
    _, source, _ = installed
    target = tmp_path / "partial"
    if damage == "source-template":
        checkout = tmp_path / "source"
        _copy(source_seed, checkout)
        monkeypatch.setattr(pilot, "ROOT", checkout)
    real = bundle._write_no_clobber

    def drifting(path, data):
        real(path, data)
        if path.name == bundle.LINKAGE_PATH:
            victim = {"identity-ready": source / identity.READY_PATH,
                      "identity-plan": source / identity.PLAN_PATH,
                      "reservation": _reservation(target), "runtime": target / bundle.RUNTIME_PATH,
                      "source-template": pilot.ROOT / pilot.GRADER}[damage]
            victim.write_bytes(victim.read_bytes() + b"\n")

    monkeypatch.setattr(bundle, "_write_no_clobber", drifting)
    with pytest.raises(bundle.PilotConfigBundleRefused):
        bundle.materialize_pilot_config_bundle(plan, identity_bundle=source, destination=target)
    assert _reservation(target).is_file()
    assert {path.name for path in target.iterdir()} == set(FILES)
    assert not (target / bundle.READY_PATH).exists()


@pytest.mark.parametrize("stage", ["parent", "root"])
def test_held_parent_replacement_cannot_redirect_publication(plan, installed, tmp_path, monkeypatch, stage):
    _, source, _ = installed
    parent = tmp_path / "destination-parent"
    parent.mkdir()
    target = parent / "configs"
    moved = tmp_path / "displaced"
    real = bundle._write_no_clobber

    def replaced(path, data):
        real(path, data)
        if stage == "parent" and path == _reservation(target):
            parent.rename(moved)
            parent.mkdir()
        elif stage == "root" and path.name == bundle.RUNTIME_PATH:
            target.rename(moved)
            target.symlink_to(source, target_is_directory=True)

    monkeypatch.setattr(bundle, "_write_no_clobber", replaced)
    before = _tree(source)
    with pytest.raises(bundle.PilotConfigBundleRefused):
        bundle.materialize_pilot_config_bundle(plan, identity_bundle=source, destination=target)
    assert _tree(source) == before
    assert not (target / bundle.READY_PATH).exists() and not (moved / bundle.READY_PATH).exists()
    assert (_reservation(moved / "configs") if stage == "parent" else _reservation(target)).is_file()


def test_fixture_copies_never_share_mutable_trees_or_hardlinks(tmp_path, config_seeds):
    seed = config_seeds()
    left, right = tmp_path / "left", tmp_path / "right"
    _copy(seed, left)
    _copy(seed, right)
    path = left / "configs" / bundle.RUNTIME_PATH
    path.write_bytes(b"mutated only on the left")
    assert _tree(right) == config_seeds() == seed
    assert _tree(left) != seed
    for name, _ in seed:
        a, b = left / name, right / name
        assert a.stat().st_nlink == b.stat().st_nlink == 1
        assert a.stat().st_ino != b.stat().st_ino


@pytest.mark.parametrize("args", [[], ["--identity-bundle"], ["--identity-bundle", SENTINEL],
                                  ["--unknown", SENTINEL], ["--as-of", SENTINEL]])
def test_cli_refuses_without_echoing_untrusted_values(args, capsys):
    assert bundle.main(args) == 2
    captured = capsys.readouterr()
    assert captured.err == "" and SENTINEL not in captured.out
    assert json.loads(captured.out) == {"refusal_code": "pilot_config_bundle_refused",
                                       "config_bundle_complete": False,
                                       "launch_allowed": False, "full_220_allowed": False}
