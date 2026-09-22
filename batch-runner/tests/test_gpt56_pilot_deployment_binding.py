"""One offline selector for local resource binding, not Azure fact verification."""

import hashlib
import json
import os
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

import pytest

import gpt56_foundry_evidence_intake as evidence
import gpt56_pilot_config_bundle as configs
import gpt56_pilot_deployment_binding as binding
import gpt56_pilot_identity_plan as identity
import gpt56_pilot_input_bundle as inputs
import gpt56_sol_codex_pilot_preflight as pilot
from core import codex_runner, codex_runtime_config
from core.experiment_config import ExperimentConfig
from .test_gpt56_foundry_evidence_intake import OPTIONS, _json, _offline, _parse_cache, _seed, _tree
from .test_gpt56_pilot_identity_plan import TASK_IDS, _field_names, _no_execution, source_seed
from .test_gpt56_pilot_input_bundle import _activate, _copy, input_seeds
from .test_gpt56_sol_codex_pilot_preflight import offline_only

ACCOUNT = b"/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/offline-fixture/providers/Microsoft.CognitiveServices/accounts/fixture-foundry"
RAW_IDS = (ACCOUNT, ACCOUNT + b"/projects/fixture-project", ACCOUNT + b"/deployments/reviewed-sol-deployment")
DEPLOYMENT_NAME = "reviewed-sol-deployment"
BLOCKER = "actual_pilot_deployment_not_prepared"
PRIVATE = "private-resource-path-MUST-NOT-APPEAR"


def _digest(data):
    return {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}


@pytest.fixture(autouse=True)
def no_runtime(_no_execution, monkeypatch, offline_only):
    def forbidden(*args, **kwargs):
        offline_only.append("deployment attempted runtime work")
        raise AssertionError("offline binding attempted runtime work")

    monkeypatch.setattr(codex_runner.CodexAgentRunner, "__init__", forbidden)
    for name in ("resolve_endpoint_setting", "discover_azure_cli_config_dir", "provider_config_overrides", "describe_provider"):
        monkeypatch.setattr(codex_runtime_config, name, forbidden)
    monkeypatch.setattr(codex_runtime_config.CodexProviderSettings, "auth_command", forbidden)


@pytest.fixture(scope="module")
def deployment_seeds(tmp_path_factory, input_seeds, _seed):
    """Real preparation once per byte variant; never share mutable trees."""
    @lru_cache(maxsize=2)
    def prepare(trailing=False):
        parent = tmp_path_factory.mktemp("pilot-deployment-seed")
        # Reuse only the immutable source/parquet/reference fixture inputs.
        # Each evidence-linked identity/config/input bundle is prepared for real.
        base = tuple((name, data) for name, data in input_seeds(False)
                     if name.startswith(("source/", "references/")) or name == "source.parquet")
        _copy(base, parent)
        raw_ids = tuple(value + (b"/" if trailing else b"") for value in RAW_IDS)
        _copy(tuple((PRIVATE + "/" + role + ".txt", data)
                    for role, data in zip(binding.RESOURCE_ROLES, raw_ids)), parent)
        with pytest.MonkeyPatch.context() as setup:
            _activate(setup, parent / "source")
            plan = pilot.load_plan(pilot.PLAN)
            raw = dict(_seed)
            intake = json.loads(raw[evidence.INTAKE_PATH])
            intake["plan_sha256"] = pilot.seal(plan)
            for claim in intake["claims"]:
                role = claim["role"]
                name = "artifacts/" + role + ".json"
                record = json.loads(raw[name])
                for resource, data in zip(binding.RESOURCE_ROLES, raw_ids):
                    record["subject"][resource]["resource_id_sha256"] = _digest(data)["sha256"]
                if role == "identity":
                    record["observed"] = deepcopy(record["subject"])
                raw[name] = _json(record)
                claim["artifact"] = {"path": name, **_digest(raw[name])}
            raw[evidence.INTAKE_PATH] = _json(intake)
            _copy(tuple(raw.items()), parent / "raw-evidence")
            evidence.publish_foundry_evidence(source=parent / "raw-evidence", destination=parent / "evidence", **OPTIONS)
            options = {"evidence_bundle": parent / "evidence", **OPTIONS}
            identity.publish_pilot_identity(plan, destination=parent / "identity", **options)
            configs.materialize_pilot_config_bundle(
                plan, identity_bundle=parent / "identity", destination=parent / "configs", **options,
            )
            inputs.materialize_pilot_input_bundle(
                plan, config_bundle=parent / "configs", identity_bundle=parent / "identity",
                dataset_parquet=parent / "source.parquet", reference_root=parent / "references",
                destination=parent / "inputs", **options,
            )
            binding.materialize_pilot_deployment_binding(plan, destination=parent / "deployment", **_options(parent))
        return _tree(parent)
    return prepare


def _options(parent):
    return {
        **OPTIONS, "evidence_bundle": parent / "evidence", "identity_bundle": parent / "identity",
        "config_bundle": parent / "configs", "input_bundle": parent / "inputs",
        **{role + "_resource_id_file": parent / PRIVATE / (role + ".txt") for role in binding.RESOURCE_ROLES},
    }


def _fresh(deployment_seeds, tmp_path, monkeypatch, *, published=False, trailing=False):
    files = deployment_seeds(trailing)
    if not published:
        files = tuple((name, data) for name, data in files
                      if not name.startswith("deployment/") and name != "deployment" + binding.RESERVATION_SUFFIX)
    _copy(files, tmp_path)
    _activate(monkeypatch, tmp_path / "source")
    return SimpleNamespace(parent=tmp_path, root=tmp_path / "deployment",
                           plan=pilot.load_plan(pilot.PLAN), options=_options(tmp_path))


@pytest.fixture
def fresh(deployment_seeds, tmp_path, monkeypatch):
    return _fresh(deployment_seeds, tmp_path, monkeypatch)


@pytest.fixture
def sealed(deployment_seeds, tmp_path, monkeypatch):
    return _fresh(deployment_seeds, tmp_path, monkeypatch, published=True)


def _reservation(case):
    return case.root.with_name(case.root.name + binding.RESERVATION_SUFFIX)


def _publish(case):
    return binding.materialize_pilot_deployment_binding(case.plan, destination=case.root, **case.options)


def _verify(case):
    return binding.verify_pilot_deployment_binding(case.plan, bundle_root=case.root, **case.options)


def _upstream_options(case):
    return {key: value for key, value in case.options.items() if not key.endswith("_resource_id_file")}


def _refused_before_write(case, match=None):
    before = _tree(case.parent)
    with pytest.raises(binding.PilotDeploymentBindingRefused, match=match) as failure:
        _publish(case)
    assert str(case.parent) not in str(failure.value) and PRIVATE not in str(failure.value)
    assert not os.path.lexists(case.root) and not os.path.lexists(_reservation(case))
    assert _tree(case.parent) == before


@pytest.mark.parametrize("trailing", [False, True])
def test_exact_hash_bound_candidate_uses_all_real_verifiers_and_parser(deployment_seeds, tmp_path, monkeypatch, capsys, trailing):
    case = _fresh(deployment_seeds, tmp_path, monkeypatch, trailing=trailing)
    before, calls, writes = dict(_tree(case.parent)), [], []
    for module, name in ((evidence, "verify_foundry_evidence"), (identity, "verify_pilot_identity"),
                         (configs, "verify_pilot_config_bundle"), (inputs, "verify_pilot_input_bundle")):
        original = getattr(module, name)

        def verify(*args, _original=original, _name=name, **kwargs):
            calls.append(_name)
            return _original(*args, **kwargs)

        monkeypatch.setattr(module, name, verify)
    real_validate, real_write = ExperimentConfig.validate, binding._write_no_clobber

    def validate(config):
        if config.experiment_id == pilot.RUN_ID:
            calls.append("real_runtime_validator")
        return real_validate(config)

    def write(path, data):
        assert not (case.root / binding.READY_PATH).exists()
        writes.append(path.relative_to(case.parent).as_posix())
        return real_write(path, data)

    monkeypatch.setattr(ExperimentConfig, "validate", validate)
    monkeypatch.setattr(binding, "_write_no_clobber", write)
    result = _publish(case)
    assert _verify(case) == result
    assert set(calls) == {"verify_foundry_evidence", "verify_pilot_identity", "verify_pilot_config_bundle",
                          "verify_pilot_input_bundle", "real_runtime_validator"}
    assert writes == ["deployment" + binding.RESERVATION_SUFFIX,
                      "deployment/" + binding.CANDIDATE_PATH, "deployment/" + binding.BINDING_PATH,
                      "deployment/" + binding.READY_PATH]
    document = result.as_dict()
    assert _json(document) == result.canonical_bytes()
    assert result.sha256 == _digest(result.canonical_bytes())["sha256"]
    assert _reservation(case).read_bytes() == binding._reservation(result)
    assert document["run_id"] == pilot.RUN_ID and document["condition"] == "codex_foundry" and document["repeat"] == 1
    assert document["task_ids"] == TASK_IDS and document["expected_task_count"] == 5
    assert document["source_pins"] == case.plan["source_pins"] and len(document["source_pins"]) == 58
    assert case.plan["deployment_binding"] == pilot.DEPLOYMENT_BINDING
    assert document["evidence_boundary"] == binding.BOUNDARY
    assert document["launch_allowed"] is document["full_220_allowed"] is False
    for role, data in zip(binding.RESOURCE_ROLES, RAW_IDS):
        raw = data + (b"/" if trailing else b"")
        assert document["resource_files"][role] == {"role": role + "_resource_id", "encoding": "utf-8", **_digest(raw)}
    assert document["files"] == {name: _digest(data) for name, data in result.files}
    bound = json.loads(dict(result.files)[binding.BINDING_PATH])
    candidate = json.loads(dict(result.files)[binding.CANDIDATE_PATH])
    parsed = ExperimentConfig.from_yaml(str(case.root / binding.CANDIDATE_PATH))
    assert parsed.validate() == []
    assert parsed.experiment_id == pilot.RUN_ID and parsed.data_filter.task_ids == TASK_IDS
    assert parsed.data_filter.sample_size is parsed.data_filter.sector is parsed.data_filter.occupation is None
    assert parsed.condition_b is None and parsed.condition_a.preprocessors is None
    assert parsed.condition_a.model.provider == "azure" and parsed.execution.mode == "codex_foundry"
    assert parsed.condition_a.model.deployment == parsed.execution.codex["model"] == DEPLOYMENT_NAME
    assert bound["dispatch"]["identity"]["model"] == "gpt-5.6-sol" != DEPLOYMENT_NAME
    assert bound["dispatch"]["identity"]["fast_mode"] is False
    assert parsed.condition_a.model.reasoning_effort == parsed.execution.codex["reasoning_effort"] == "max"
    assert parsed.execution.codex["model_context_window"] == 1_000_000
    assert parsed.execution.codex["provider_id"] == "gdpval-foundry"
    assert parsed.execution.codex["endpoint_from_route"] is True
    assert parsed.execution.codex["request_max_retries"] == parsed.execution.codex["stream_max_retries"] == 0
    assert parsed.execution.resume_max_rounds == 0 and parsed.condition_a.qa.enabled is False
    assert parsed.execution.max_retries == 3 and parsed.execution.timeout == 1800
    assert parsed.execution.tokens == case.plan["limits"]["inactive_generic_token_settings"]
    assert parsed.condition_a.prompt.system == case.plan["developer_instructions"]
    assert parsed.output.publish_to_hf is parsed.output.submit_to_evals is False
    assert bound["dispatch"]["logical_attempts_per_task"] == bound["dispatch"]["repeat"] == 1
    assert bound["dispatch"]["pilot_controls"]["fresh_session_per_attempt"] is True
    assert bound["dispatch"]["pilot_controls"]["relay_max_runs"] == 0
    assert bound["dispatch"]["pilot_controls"]["auto_escalation"] is False
    assert bound["dataset"] == case.plan["dataset"]
    manifest = json.loads((case.options["config_bundle"] / configs.PREPARED_PATH).read_bytes())
    assert bound["tasks"] == document["tasks"] == manifest["tasks"]
    assert candidate["data"]["filter"]["task_ids"] == manifest["task_ids"]
    assert not {"endpoint", "api_key", "credential", "token", "command", "argv", "auth_command"} & _field_names(candidate)
    all_output = result.canonical_bytes() + b"".join(data for _, data in result.files)
    for raw in RAW_IDS:
        assert raw not in all_output
    assert str(case.parent).encode() not in all_output and PRIVATE.encode() not in all_output
    for name, data in result.files:
        path = case.root / name
        assert path.read_bytes() == data and path.stat().st_nlink == 1 and not path.is_symlink()
    after = dict(_tree(case.parent))
    assert {name: after[name] for name in before} == before
    template = json.loads((case.options["config_bundle"] / configs.RUNTIME_PATH).read_bytes())
    assert template["deployment"] is template["execution"] is None and template["runnable"] is False
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""


def test_plan_only_and_null_binding_keep_the_eleven_default_blockers(sealed, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("legacy path consulted deployment binding")

    monkeypatch.setattr(binding, "verify_pilot_deployment_binding", forbidden)
    legacy = pilot._inspect_plan_with_input(sealed.plan)
    assert _json(pilot.inspect_plan(sealed.plan)) == _json(legacy)
    assert _json(pilot.inspect_plan(sealed.plan, deployment_binding=None, account_resource_id_file=None,
                                   project_resource_id_file=None, deployment_resource_id_file=None)) == _json(legacy)
    assert legacy["configuration_valid"] and legacy["launch_blockers"] == list(pilot.LAUNCH_BLOCKERS)
    assert len(legacy["launch_blockers"]) == 11 and BLOCKER in legacy["launch_blockers"]
    assert legacy["launch_allowed"] is legacy["full_220_allowed"] is False


def test_verified_explicit_consumption_clears_only_deployment_and_hides_ids(sealed):
    before = pilot.inspect_plan(sealed.plan, **_upstream_options(sealed))
    after = pilot.inspect_plan(sealed.plan, deployment_binding=sealed.root, **sealed.options)
    assert before["launch_blockers"] == ["native_call_and_token_limits_unresolved", "live_inference_identity_and_wire_unverified",
                                       "foundry_usage_and_tariff_mapping_unverified",
                                       "native_sandbox_and_result_bundle_host_unverified", BLOCKER,
                                       "prepared_request_capture_unverified"]
    assert after["launch_blockers"] == [name for name in before["launch_blockers"] if name != BLOCKER]
    gate = after["deployment_binding_gate"]
    verified = _verify(sealed)
    assert gate["deployment_binding_complete"] is True
    assert gate["cleared_blockers"] == list(pilot.DEPLOYMENT_BINDING_BLOCKERS) == [BLOCKER]
    assert gate["consumed_bundle_sha256"] == verified.sha256
    assert gate["candidate_config_sha256"] == verified.as_dict()["files"][binding.CANDIDATE_PATH]["sha256"]
    assert gate["evidence_linkage"] == verified.as_dict()["evidence_linkage"] and gate["evaluated_at"] == OPTIONS["as_of"]
    assert gate["remaining_work"] == list(binding.REMAINING_WORK)
    assert "actual_pilot_execution_and_runtime_receipts_unverified" in gate["remaining_work"]
    for name in ("evidence_gate", "identity_plan_gate", "input_bundle_gate", "deployment_binding_gate"):
        assert after[name]["remaining_blockers"] == after["launch_blockers"]
    assert after["launch_allowed"] is after["full_220_allowed"] is False
    assert not {"resource_files", "subject", "endpoint", "deployment", "command", "argv"} & _field_names(after)
    encoded = _json(after)
    assert PRIVATE.encode() not in encoded and str(sealed.parent).encode() not in encoded
    assert DEPLOYMENT_NAME.encode() not in encoded and all(raw not in encoded for raw in RAW_IDS)


@pytest.mark.parametrize("missing", ["evidence_bundle", "identity_bundle", "config_bundle", "input_bundle",
                                     "reviewed_source_sha", "as_of", "deployment_binding",
                                     "account_resource_id_file", "project_resource_id_file", "deployment_resource_id_file"])
def test_explicit_gate_requires_every_link_and_private_file(sealed, missing):
    options = {**sealed.options, "deployment_binding": sealed.root, missing: None}
    report = pilot.inspect_plan(sealed.plan, **options)
    gate = report["deployment_binding_gate"]
    assert gate["deployment_binding_complete"] is False and gate["cleared_blockers"] == []
    assert gate["refusal_code"] == pilot.DEPLOYMENT_REFUSAL and BLOCKER in report["launch_blockers"]
    assert report["launch_allowed"] is report["full_220_allowed"] is False
    assert PRIVATE.encode() not in _json(report)


@pytest.mark.parametrize("role", binding.RESOURCE_ROLES)
def test_hashing_never_strips_or_normalizes_resource_bytes(fresh, role):
    path = fresh.options[role + "_resource_id_file"]
    path.write_bytes(path.read_bytes() + b"/")
    _refused_before_write(fresh, "resource_digest_mismatch")


@pytest.mark.parametrize("value", [
    b"", b"not-an-arm-id", b"https://example.invalid/" + RAW_IDS[2], b"//" + RAW_IDS[2][1:],
    RAW_IDS[2] + b"?api-version=1", RAW_IDS[2] + b"#fragment", RAW_IDS[2] + b"\n",
    b" " + RAW_IDS[2], RAW_IDS[2] + b" ", RAW_IDS[2] + b"\t", RAW_IDS[2] + b"\x00",
    RAW_IDS[2] + b"\x1f", b"\xef\xbb\xbf" + RAW_IDS[2], RAW_IDS[2] + b"\xff",
    ACCOUNT + b"/deployments/../leaf", ACCOUNT + b"/deployments/%2e%2e",
    ACCOUNT + b"/deployments/leaf%0a", ACCOUNT + b"/deployments/leaf\\outside",
    ACCOUNT + b"/deployments/", ACCOUNT + b"/deployments/./leaf",
    ACCOUNT + b"/projects/p/deployments/leaf", ACCOUNT + b"/deployments/leaf/extra",
    ACCOUNT + b"/deployments/Authorization", ACCOUNT + b"/deployments/Bearer-private",
    ACCOUNT + b"/deployments/api-key-private", ACCOUNT + b"/deployments/sk-private",
    ACCOUNT + b"/deployments/github_pat_private", ACCOUNT + b"/deployments/access_token_private",
    ACCOUNT + b"/deployments/eyJhbGciOiJIUzI1NiJ9.payload.signature",
    ACCOUNT + b"/deployments/" + b"a" * 64,
])
def test_malformed_or_secret_like_id_is_refused_without_publication(fresh, value, capsys):
    fresh.options["deployment_resource_id_file"].write_bytes(value)
    _refused_before_write(fresh)
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""


@pytest.mark.parametrize("damage", ["hierarchy", "wrong-role", "duplicate-source", "parent-traversal", "oversize", "directory"])
def test_resource_identity_and_file_shape_are_closed(fresh, damage):
    key = "deployment_resource_id_file"
    path = fresh.options[key]
    if damage == "hierarchy":
        path.write_bytes(RAW_IDS[2].replace(b"fixture-foundry", b"another-foundry"))
    elif damage == "wrong-role":
        path.write_bytes(RAW_IDS[1])
    elif damage == "duplicate-source":
        fresh.options[key] = fresh.options["project_resource_id_file"]
    elif damage == "parent-traversal":
        fresh.options[key] = path.parent / ".." / path.parent.name / path.name
    elif damage == "oversize":
        path.write_bytes(b"x" * 4097)
    else:
        path.unlink()
        path.mkdir()
    _refused_before_write(fresh)


@pytest.mark.parametrize("role", binding.RESOURCE_ROLES)
@pytest.mark.parametrize("damage", ["missing", "symlink", "hardlink"])
def test_each_resource_source_must_be_a_regular_single_link_file(fresh, role, damage):
    path = fresh.options[role + "_resource_id_file"]
    backup = fresh.parent / "unchanged-private-backup"
    data = path.read_bytes()
    path.unlink()
    if damage != "missing":
        backup.write_bytes(data)
        path.symlink_to(backup) if damage == "symlink" else os.link(backup, path)
    _refused_before_write(fresh)
    if damage != "missing":
        assert backup.read_bytes() == data


@pytest.mark.parametrize("target", [
    "evidence/" + evidence.READY_PATH, "evidence.foundry-evidence-reservation.json",
    "evidence/artifacts/identity.json", "evidence/artifacts/native_caps.json",
    "identity/" + identity.PLAN_PATH, "identity/" + identity.READY_PATH,
    "identity" + identity.RESERVATION_SUFFIX, "configs/" + configs.READY_PATH,
    "configs/" + configs.RUNTIME_PATH, "configs/" + configs.PREPARED_PATH,
    "configs" + configs.RESERVATION_SUFFIX, "inputs/" + inputs.READY_PATH,
    "inputs" + inputs.RESERVATION_SUFFIX, "inputs/" + inputs.PARQUET_PATH,
    "source/" + pilot.ACTIVE_PLAN, "source/batch-runner/core/repository_identity.py",
])
def test_current_upstream_bytes_and_active_source_are_reverified(fresh, target):
    path = fresh.parent / target
    if target == "source/" + pilot.ACTIVE_PLAN:
        changed = json.loads(path.read_bytes())
        changed["pilot"]["run_id"] = "stale-run"
        path.write_bytes(_json(changed))
    else:
        path.write_bytes(path.read_bytes() + b"\n")
    _refused_before_write(fresh)


@pytest.mark.parametrize("target", ["evidence", "identity", "configs", "inputs"])
@pytest.mark.parametrize("damage", ["missing", "symlink", "hardlink"])
def test_each_upstream_ready_requires_current_regular_single_link_bytes(fresh, target, damage):
    names = {"evidence": evidence.READY_PATH, "identity": identity.READY_PATH,
             "configs": configs.READY_PATH, "inputs": inputs.READY_PATH}
    path = fresh.parent / target / names[target]
    data = path.read_bytes()
    path.unlink()
    if damage != "missing":
        copy = fresh.parent / "upstream-ready-copy"
        copy.write_bytes(data)
        path.symlink_to(copy) if damage == "symlink" else os.link(copy, path)
    _refused_before_write(fresh)


@pytest.mark.parametrize("mutation", ["run", "order", "fast-model", "effort", "context", "launch", "source-pin", "registration"])
def test_supplied_plan_cannot_drift_from_the_active_contract(fresh, mutation):
    if mutation == "run":
        fresh.plan["pilot"]["run_id"] = "stale-run"
    elif mutation == "order":
        fresh.plan["dataset"]["tasks"].reverse()
    elif mutation == "fast-model":
        fresh.plan["identity"]["model"] = "gpt-5.6-sol-fast"
    elif mutation == "effort":
        fresh.plan["codex_request"]["reasoning_effort"] = "high"
    elif mutation == "context":
        fresh.plan["codex_request"]["model_context_window"] = 272000
    elif mutation == "launch":
        fresh.plan["launch_enabled"] = True
    elif mutation == "source-pin":
        fresh.plan["source_pins"][pilot.DEPLOYMENT_BINDING["materializer"]] = "0" * 64
    else:
        fresh.plan["deployment_binding"]["source_base_sha"] = "d" * 40
    _refused_before_write(fresh)


@pytest.mark.parametrize("key,value", [
    ("reviewed_source_sha", "d" * 40), ("reviewed_source_sha", "main"),
    ("reviewed_source_sha", "c" * 39), ("as_of", "2026-10-02T00:00:00Z"),
    ("as_of", "2026-09-19T00:00:00Z"), ("as_of", "2026-09-20T03:00:00+00:00"),
])
def test_reviewed_sha_and_explicit_time_must_match_complete_evidence(fresh, key, value):
    fresh.options[key] = value
    _refused_before_write(fresh)


@pytest.mark.parametrize("target", [binding.CANDIDATE_PATH, binding.BINDING_PATH, binding.READY_PATH, "reservation"])
@pytest.mark.parametrize("damage", ["missing", "bytes", "symlink", "hardlink"])
def test_every_published_file_and_reservation_is_required(sealed, target, damage):
    path = _reservation(sealed) if target == "reservation" else sealed.root / target
    data = path.read_bytes()
    if damage == "bytes":
        path.write_bytes(data + b"\n")
    else:
        path.unlink()
        if damage != "missing":
            backup = sealed.parent / "published-backup"
            backup.write_bytes(data)
            path.symlink_to(backup) if damage == "symlink" else os.link(backup, path)
    with pytest.raises(binding.PilotDeploymentBindingRefused):
        _verify(sealed)
    report = pilot.inspect_plan(sealed.plan, deployment_binding=sealed.root, **sealed.options)
    assert BLOCKER in report["launch_blockers"] and not report["deployment_binding_gate"]["deployment_binding_complete"]
    assert report["launch_allowed"] is report["full_220_allowed"] is False


@pytest.mark.parametrize("mutation", ["model-label", "task-order", "extra-task", "max", "context", "endpoint", "resume", "relay", "launch"])
def test_matching_forged_output_hashes_cannot_replace_the_trusted_derivation(sealed, mutation):
    candidate = json.loads((sealed.root / binding.CANDIDATE_PATH).read_bytes())
    bound = json.loads((sealed.root / binding.BINDING_PATH).read_bytes())
    ready = json.loads((sealed.root / binding.READY_PATH).read_bytes())
    if mutation == "model-label":
        candidate["condition_a"]["model"]["deployment"] = candidate["execution"]["codex"]["model"] = "gpt-5.6-sol"
    elif mutation == "task-order":
        candidate["data"]["filter"]["task_ids"].reverse()
    elif mutation == "extra-task":
        candidate["data"]["filter"]["task_ids"].append("unregistered-task")
    elif mutation == "max":
        candidate["execution"]["codex"]["reasoning_effort"] = "high"
    elif mutation == "context":
        candidate["execution"]["codex"]["model_context_window"] = 272000
    elif mutation == "endpoint":
        candidate["execution"]["codex"]["endpoint"] = "https://private.invalid/openai/v1/"
    elif mutation == "resume":
        candidate["execution"]["resume_max_rounds"] = 1
    elif mutation == "relay":
        bound["dispatch"]["pilot_controls"]["relay_max_runs"] = 1
    else:
        bound["launch_allowed"] = ready["launch_allowed"] = True
    candidate_data = _json(candidate)
    bound["candidate"] = {"path": binding.CANDIDATE_PATH, **_digest(candidate_data)}
    files = ((binding.CANDIDATE_PATH, candidate_data), (binding.BINDING_PATH, _json(bound)))
    ready["files"] = {name: _digest(data) for name, data in files}
    forged = binding.PilotDeploymentBinding(binding._canonical_json(ready), files)
    for name, data in files:
        (sealed.root / name).write_bytes(data)
    (sealed.root / binding.READY_PATH).write_bytes(forged.canonical_bytes())
    _reservation(sealed).write_bytes(binding._reservation(forged))
    with pytest.raises(binding.PilotDeploymentBindingRefused):
        _verify(sealed)


@pytest.mark.parametrize("damage", ["directory", "file", "symlink", "reservation", "root-parent-symlink", "traversal", "source-overlap"])
def test_target_collision_and_unsafe_paths_never_overwrite(fresh, damage):
    if damage == "directory":
        fresh.root.mkdir()
    elif damage == "file":
        fresh.root.write_bytes(b"existing-user-bytes")
    elif damage == "symlink":
        fresh.root.symlink_to(fresh.options["input_bundle"], target_is_directory=True)
    elif damage == "reservation":
        _reservation(fresh).write_bytes(b"prior-reservation")
    elif damage == "root-parent-symlink":
        alias = fresh.parent / "parent-alias"
        alias.symlink_to(fresh.parent, target_is_directory=True)
        fresh.root = alias / "deployment"
    elif damage == "traversal":
        fresh.root = fresh.parent / "inputs" / ".." / "deployment"
    else:
        fresh.root = fresh.options["input_bundle"] / "deployment"
    before = _tree(fresh.parent)
    with pytest.raises(binding.PilotDeploymentBindingRefused):
        _publish(fresh)
    assert _tree(fresh.parent) == before


@pytest.mark.parametrize("extra", ["file", "directory"])
def test_extra_output_members_are_not_accepted(sealed, extra):
    path = sealed.root / "extra"
    path.write_bytes(b"unregistered") if extra == "file" else path.mkdir()
    with pytest.raises(binding.PilotDeploymentBindingRefused):
        _verify(sealed)


@pytest.mark.parametrize("failed_write", [1, 2, 3, 4])
def test_each_write_failure_retains_partial_state_without_ready_or_reuse(fresh, monkeypatch, failed_write):
    real, calls = binding._write_no_clobber, []

    def write(path, data):
        calls.append(path)
        if len(calls) == failed_write:
            raise OSError(PRIVATE)
        return real(path, data)

    monkeypatch.setattr(binding, "_write_no_clobber", write)
    with pytest.raises(binding.PilotDeploymentBindingRefused) as failure:
        _publish(fresh)
    assert PRIVATE not in str(failure.value)
    assert not (fresh.root / binding.READY_PATH).exists()
    assert _reservation(fresh).exists() is (failed_write > 1)
    assert fresh.root.exists() is (failed_write > 1)
    if failed_write > 1:
        before = _tree(fresh.parent)
        with pytest.raises(binding.PilotDeploymentBindingRefused):
            _publish(fresh)
        assert _tree(fresh.parent) == before
        with pytest.raises(binding.PilotDeploymentBindingRefused):
            _verify(fresh)


def test_directory_creation_failure_keeps_only_reservation(fresh, monkeypatch):
    real = os.mkdir

    def mkdir(path, *args, **kwargs):
        if path == fresh.root.name and "dir_fd" in kwargs:
            raise OSError(PRIVATE)
        return real(path, *args, **kwargs)

    monkeypatch.setattr(os, "mkdir", mkdir)
    with pytest.raises(binding.PilotDeploymentBindingRefused):
        _publish(fresh)
    assert _reservation(fresh).exists() and not fresh.root.exists()
    with pytest.raises(binding.PilotDeploymentBindingRefused):
        _publish(fresh)


@pytest.mark.parametrize("target", ["resource", "upstream", "installed", "reservation"])
def test_mid_publication_drift_cannot_receive_ready(fresh, monkeypatch, target):
    real = binding._write_no_clobber

    def write(path, data):
        result = real(path, data)
        if path == fresh.root / binding.BINDING_PATH:
            changed = {"resource": fresh.options["deployment_resource_id_file"],
                       "upstream": fresh.options["input_bundle"] / inputs.READY_PATH,
                       "installed": fresh.root / binding.CANDIDATE_PATH,
                       "reservation": _reservation(fresh)}[target]
            changed.write_bytes(changed.read_bytes() + b"\n")
        return result

    monkeypatch.setattr(binding, "_write_no_clobber", write)
    with pytest.raises(binding.PilotDeploymentBindingRefused):
        _publish(fresh)
    assert not (fresh.root / binding.READY_PATH).exists() and _reservation(fresh).exists()


@pytest.mark.parametrize("target", ["upstream", "resource"])
def test_drift_during_runtime_parsing_is_caught_by_read_only_reverification(sealed, monkeypatch, target):
    real = binding._runtime

    def runtime(*args):
        result = real(*args)
        path = (sealed.options["evidence_bundle"] / evidence.READY_PATH if target == "upstream"
                else sealed.options["deployment_resource_id_file"])
        path.write_bytes(path.read_bytes() + b"\n")
        return result

    monkeypatch.setattr(binding, "_runtime", runtime)
    with pytest.raises(binding.PilotDeploymentBindingRefused):
        _verify(sealed)


def test_late_gate_reporting_failure_does_not_clear_deployment(sealed, monkeypatch):
    real = binding.verify_pilot_deployment_binding

    def verify(*args, **kwargs):
        checked = real(*args, **kwargs)

        class BrokenReport:
            sha256 = checked.sha256

            def as_dict(self):
                value = checked.as_dict()
                del value["remaining_work"]
                return value

        return BrokenReport()

    monkeypatch.setattr(binding, "verify_pilot_deployment_binding", verify)
    report = pilot.inspect_plan(sealed.plan, deployment_binding=sealed.root, **sealed.options)
    assert BLOCKER in report["launch_blockers"]
    assert report["deployment_binding_gate"]["cleared_blockers"] == []
    assert report["launch_allowed"] is report["full_220_allowed"] is False


def test_source_parent_replacement_is_detected(fresh, monkeypatch):
    real, moved = binding._resource_bytes, fresh.parent / "moved-private"
    replaced = False

    def read(path):
        nonlocal replaced
        value = real(path)
        if not replaced:
            replaced = True
            parent = path.parent
            parent.rename(moved)
            _copy(tuple((item.name, item.read_bytes()) for item in moved.iterdir()), parent)
        return value

    monkeypatch.setattr(binding, "_resource_bytes", read)
    with pytest.raises(binding.PilotDeploymentBindingRefused):
        _publish(fresh)
    assert not fresh.root.exists() and not _reservation(fresh).exists()
    assert moved.exists()


def test_destination_parent_replacement_keeps_failure_unready(fresh, monkeypatch):
    parent = fresh.parent / "output-parent"
    parent.mkdir()
    fresh.root = parent / "deployment"
    real = binding._write_no_clobber

    def write(path, data):
        result = real(path, data)
        if path == _reservation(fresh):
            parent.rename(fresh.parent / "quarantined-parent")
            parent.mkdir()
        return result

    monkeypatch.setattr(binding, "_write_no_clobber", write)
    with pytest.raises(binding.PilotDeploymentBindingRefused):
        _publish(fresh)
    assert not (fresh.root / binding.READY_PATH).exists()
    assert (fresh.parent / "quarantined-parent" / ("deployment" + binding.RESERVATION_SUFFIX)).exists()


def _cli_options(case):
    return [item for key, value in case.options.items() for item in ("--" + key.replace("_", "-"), str(value))]


@pytest.mark.parametrize("mode", ["publish", "verify", "preflight", "malformed-option", "private-value", "missing-source"])
def test_cli_is_static_and_never_emits_raw_resource_bytes_or_paths(deployment_seeds, tmp_path, monkeypatch, capsys, mode):
    case = _fresh(deployment_seeds, tmp_path, monkeypatch, published=mode != "publish")
    options = _cli_options(case)
    if mode == "publish":
        code = binding.main(["--destination", str(case.root), *options])
    elif mode == "preflight":
        code = pilot.main(["--deployment-binding", str(case.root), *options])
    else:
        if mode == "malformed-option":
            options.extend(["--account-resource-id-file-typo", PRIVATE])
        elif mode == "private-value":
            case.options["deployment_resource_id_file"].write_bytes(b"Authorization: Bearer " + PRIVATE.encode())
        elif mode == "missing-source":
            case.options["account_resource_id_file"].unlink()
        code = binding.main(["--verify-bundle", str(case.root), *options])
    captured = capsys.readouterr()
    assert captured.err == ""
    assert PRIVATE not in captured.out and str(case.parent) not in captured.out
    assert DEPLOYMENT_NAME not in captured.out and all(raw.decode() not in captured.out for raw in RAW_IDS)
    report = json.loads(captured.out)
    assert report["launch_allowed"] is report["full_220_allowed"] is False
    if mode in ("publish", "verify"):
        assert code == 0 and report["deployment_binding_complete"] is True
    elif mode == "preflight":
        assert code == 2 and report["deployment_binding_gate"]["deployment_binding_complete"] is True
    else:
        assert code == 2 and report["deployment_binding_complete"] is False
        assert report["refusal_code"] == "pilot_deployment_binding_refused"


def test_later_as_of_checks_freshness_without_changing_sealed_bytes(sealed):
    expected = _verify(sealed)
    sealed.options["as_of"] = "2026-09-20T04:00:00Z"
    assert _verify(sealed) == expected
    sealed.options["as_of"] = "2026-10-02T00:00:00Z"
    with pytest.raises(binding.PilotDeploymentBindingRefused):
        _verify(sealed)


@pytest.mark.parametrize("option", ["--deployment-binding-typo", "--account-resource-id-file-typo"])
def test_malformed_preflight_options_cannot_echo_private_values(option, capsys):
    assert pilot.main([option, PRIVATE]) == 2
    captured = capsys.readouterr()
    assert PRIVATE not in captured.out and captured.err == ""
    report = json.loads(captured.out)
    assert report["launch_allowed"] is report["full_220_allowed"] is False
    assert BLOCKER in report["launch_blockers"]


def test_mutation_never_reaches_another_case_or_the_immutable_seed(deployment_seeds, tmp_path, monkeypatch):
    before = deployment_seeds(False)
    first = _fresh(deployment_seeds, tmp_path / "first", monkeypatch, published=True)
    second = _fresh(deployment_seeds, tmp_path / "second", monkeypatch, published=True)
    first.options["deployment_resource_id_file"].write_bytes(b"damaged private input")
    (first.root / binding.CANDIDATE_PATH).write_bytes(b"damaged candidate")
    assert second.options["deployment_resource_id_file"].read_bytes() == RAW_IDS[2]
    assert _verify(second).as_dict()["task_ids"] == TASK_IDS
    assert deployment_seeds(False) == before
    for path in second.parent.rglob("*"):
        if path.is_file():
            assert path.stat().st_nlink == 1 and not path.is_symlink()
