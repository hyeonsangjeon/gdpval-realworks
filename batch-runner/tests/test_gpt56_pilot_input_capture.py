"""One offline selector: real Step 1 bytes, early Step 2 gate, no inference."""

import ast
import json
import os
from copy import deepcopy
from dataclasses import replace
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

import pytest

import gpt56_foundry_evidence_intake as evidence
import gpt56_pilot_config_bundle as configs
import gpt56_pilot_deployment_binding as deployment
import gpt56_pilot_identity_plan as identity
import gpt56_pilot_input_bundle as inputs
import gpt56_pilot_input_capture as capture
import gpt56_sol_codex_pilot_preflight as pilot
import step1_prepare_tasks as step1
import step2_run_inference as step2
from core import needs_files, repo_bootstrapper
from core.experiment_config import ExperimentConfig, PilotInputCapture
from core.prepared_fingerprint import prepared_fingerprint
from core.result_fingerprint import inference_result_fingerprint
from .test_gpt56_foundry_evidence_intake import OPTIONS, _json, _offline, _parse_cache, _seed, _tree
from .test_gpt56_pilot_deployment_binding import (
    PRIVATE, RAW_IDS, _options, deployment_seeds, no_runtime,
)
from .test_gpt56_pilot_identity_plan import TASK_IDS, _field_names, _no_execution, source_seed
from .test_gpt56_pilot_input_bundle import _activate, _copy, input_seeds
from .test_gpt56_sol_codex_pilot_preflight import offline_only

BLOCKER = "prepared_request_capture_unverified"
LIVE = "live_inference_identity_and_wire_unverified"
MANIFEST = "step0_needs_files_manifest.json"


class ProviderBoundary(BaseException):
    """Stop at the first route/auth seam without constructing anything."""


@pytest.fixture(autouse=True)
def runtime_guards(no_runtime, monkeypatch, offline_only):
    def forbidden(*args, **kwargs):
        offline_only.append("pilot crossed runtime boundary")
        raise AssertionError("offline capture attempted runtime work")

    for name in ("create_provider_client", "create_typed_azure_client", "AzureAIClientFactory", "TaskExecutor",
                 "complete", "preflight_routes", "open_cost_recorder"):
        monkeypatch.setattr(step2, name, forbidden)
    monkeypatch.setattr(step2.AzureAIRouteSettings, "from_env", forbidden)
    # Match the GPT-5.4 capture fixture: this unrelated existing mode boundary
    # is a stand-in, not evidence of a connection or permission to launch.
    # The real capture/upstream validators and all construction guards remain.
    monkeypatch.setattr(step2, "_codex_connection_confirmed", lambda: True)
    monkeypatch.delenv("GDPVAL_RELAY_LINEAGE_ID", raising=False)
    monkeypatch.setenv("NEEDS_FILES_POLICY", "deliverable_only")
    monkeypatch.setenv("AZURE_AI_ROUTE_PROFILE", "direct-v1")


def _runtime_paths(monkeypatch, parent):
    _activate(monkeypatch, parent / "source")
    workspace = parent / "workspace"
    for module in (step1, step2):
        monkeypatch.setattr(module, "WORKSPACE_DIR", workspace)
        monkeypatch.setattr(module, "DEFAULT_LOCAL_PATH", parent / "inputs")
    monkeypatch.setattr(needs_files, "WORKSPACE_DIR", workspace)
    # Only the fixture's canonical data digest differs. The real manifest
    # reader, source projection, reference validator and fingerprint still run.
    monkeypatch.setattr(repo_bootstrapper, "NEEDS_FILES_POLICY", "deliverable_only")
    monkeypatch.setattr(repo_bootstrapper, "CANONICAL_MANIFEST_SHA256_BY_POLICY", {
        "deliverable_only": capture._digest((workspace / MANIFEST).read_bytes())["sha256"],
    })
    monkeypatch.setattr(step1, "resolve_publication_generation", lambda _: pilot.RUN_ID + ":offline-fixture")
    return capture.PilotCaptureSources(deployment_binding=parent / "deployment", **_options(parent))


@pytest.fixture(scope="module")
def capture_seed(tmp_path_factory, deployment_seeds):
    """Prepare all five real upstreams and the real serializer once.

    Only immutable byte tuples are shared. Each case gets exclusive single-link
    files; no verifier verdicts or mutable trees are cached.
    """
    @lru_cache(maxsize=1)
    def prepare():
        parent = tmp_path_factory.mktemp("pilot-capture-seed")
        _copy(deployment_seeds(), parent)
        rows = json.loads((parent / "inputs" / inputs.READY_PATH).read_bytes())["source_tasks"]
        manifest = {"_schema_version": 4, "_summary": {"active_policy": "deliverable_only"},
                    "tasks": {row["task_id"]: {key: row[key] for key in ("needs_files", "source_projection_sha256")}
                              for row in rows},
                    "reference_files": {record["path"]: {key: record[key] for key in ("size", "sha256")}
                                        for row in rows for record in row["reference_files"]}}
        _copy(((MANIFEST, _json(manifest)),), parent / "workspace")
        with pytest.MonkeyPatch.context() as setup:
            context = _runtime_paths(setup, parent)
            step1.prepare_tasks(str(parent / "deployment" / deployment.CANDIDATE_PATH), pilot_capture_sources=context)
        return _tree(parent)
    return prepare


def _fresh(capture_seed, parent, monkeypatch, *, published=True):
    files = capture_seed()
    if not published:
        files = tuple((name, data) for name, data in files
                      if name not in ("workspace/" + capture.CAPTURE_PATH, "workspace/" + capture.PREPARED_PATH))
    _copy(files, parent)
    context = _runtime_paths(monkeypatch, parent)
    return SimpleNamespace(parent=parent, context=context, workspace=parent / "workspace",
                           candidate=parent / "deployment" / deployment.CANDIDATE_PATH,
                           plan=pilot.load_plan(pilot.PLAN))


@pytest.fixture
def sealed(capture_seed, tmp_path, monkeypatch):
    return _fresh(capture_seed, tmp_path, monkeypatch)


@pytest.fixture
def fresh(capture_seed, tmp_path, monkeypatch):
    return _fresh(capture_seed, tmp_path, monkeypatch, published=False)


def _publish(case):
    return step1.prepare_tasks(str(case.candidate), pilot_capture_sources=case.context)


def _verify(case, **kwargs):
    return capture.verify_pilot_input_capture(case.context, workspace=case.workspace,
                                              dataset_root=case.context.input_bundle, **kwargs)


def _preflight(case, **kwargs):
    return pilot.inspect_plan(case.plan, **vars(case.context), **kwargs)


def _before_provider(case, monkeypatch, *, kwargs=None, success=False):
    events = []
    real = capture.verify_pilot_input_capture

    def verify(*args, **options):
        events.append("verify")
        result = real(*args, **options)
        events.append("verified")
        return result

    def boundary(*args, **options):
        events.append("auth_boundary")
        raise ProviderBoundary

    monkeypatch.setattr(capture, "verify_pilot_input_capture", verify)
    monkeypatch.setattr(step2, "_require_host_may_carry_a_benchmark_run", lambda mode: events.append("host_boundary"))
    monkeypatch.setattr(step2.AzureAIRouteSettings, "from_env", boundary)
    options = {"resume": False, "pilot_capture_sources": case.context, **(kwargs or {})}
    with pytest.raises(ProviderBoundary if success else capture.PilotInputCaptureRefused) as failure:
        step2.run_inference(**options)
    if success:
        # The live host owner revalidates the capture before either boundary.
        assert events == ["verify", "verified", "verify", "verified", "host_boundary", "auth_boundary"]
    else:
        code = str(failure.value)
        assert code in ("pilot_prepared_read_refused", "pilot_capture_verification_refused")
        assert events == ([] if code == "pilot_prepared_read_refused" else ["verify"])
        assert failure.value.__suppress_context__
    return events


def test_real_step1_serializer_rechecks_every_upstream_and_publishes_capture_last(fresh, monkeypatch, capsys):
    upstream_before = _tree(fresh.parent)
    calls = []
    for module, name in ((evidence, "verify_foundry_evidence"), (identity, "verify_pilot_identity"),
                         (configs, "verify_pilot_config_bundle"), (inputs, "verify_pilot_input_bundle"),
                         (deployment, "verify_pilot_deployment_binding")):
        real = getattr(module, name)

        def watch(*args, _real=real, _name=name, **kwargs):
            calls.append(_name)
            return _real(*args, **kwargs)

        monkeypatch.setattr(module, name, watch)
    writer = capture._write_no_clobber

    def write(path, data):
        calls.append(path.name)
        if path.name == capture.CAPTURE_PATH:
            assert (fresh.workspace / capture.PREPARED_PATH).is_file()
        writer(path, data)

    monkeypatch.setattr(capture, "_write_no_clobber", write)
    payload = _publish(fresh)
    assert all(name in calls for name in ("verify_foundry_evidence", "verify_pilot_identity", "verify_pilot_config_bundle",
                                         "verify_pilot_input_bundle", "verify_pilot_deployment_binding"))
    assert calls[-1] == capture.CAPTURE_PATH and calls.index(capture.PREPARED_PATH) < len(calls) - 2
    assert dict(_tree(fresh.parent)) == {
        **dict(upstream_before),
        **{"workspace/" + name: (fresh.workspace / name).read_bytes()
           for name in (capture.PREPARED_PATH, capture.CAPTURE_PATH)},
    }
    data = (fresh.workspace / capture.CAPTURE_PATH).read_bytes()
    record = json.loads(data)
    assert data == _json(record) and record["task_ids"] == TASK_IDS
    assert [row["task_id"] for row in payload["tasks"]] == TASK_IDS
    assert record["requested"] == {"provider": "azure", "provider_id": "gdpval-foundry", "model": "gpt-5.6-sol",
                                    "deployment": "reviewed-sol-deployment", "reasoning_effort": "max", "context_tokens": 1000000}
    assert record["prepared"]["sha256"] == capture._digest((fresh.workspace / capture.PREPARED_PATH).read_bytes())["sha256"]
    assert record["prepared"]["fingerprint"] == prepared_fingerprint(payload)
    assert all(row["canonical_sha256"] == capture._digest(_json(task))["sha256"]
               for row, task in zip(record["tasks"], payload["tasks"]))
    assert set(record["upstream_bundles"]) == {"evidence", "identity", "config", "input", "deployment"}
    assert all("reservation" in entry for entry in record["upstream_bundles"].values())
    assert (fresh.workspace / capture.CAPTURE_PATH).stat().st_nlink == 1
    assert payload["config_path"] == deployment.CANDIDATE_PATH
    text = capsys.readouterr().out + data.decode()
    assert str(fresh.parent) not in text and PRIVATE not in text
    assert all(value.decode() not in text for value in RAW_IDS)
    assert not {"endpoint", "auth_module", "credential", "token", "authorization", "response", "resource_id"} & _field_names(record)


def test_step2_and_final_output_bind_verified_capture_before_provider(sealed, monkeypatch):
    linkage = _verify(sealed)
    _before_provider(sealed, monkeypatch, success=True)
    assert linkage["launch_allowed"] is linkage["full_220_allowed"] is False
    assert linkage["evidence_boundary"] == capture.BOUNDARY
    # Exercise only the existing output-linkage statements, not a fake run.
    tree = ast.parse(Path(step2.__file__).read_text())
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_run_inference_impl")
    attach = next(node for node in function.body if isinstance(node, ast.If)
                  and ast.unparse(node.test) == "verified_input_capture is not None")
    fingerprint = next(node for node in function.body if isinstance(node, ast.Assign)
                       and ast.unparse(node.targets[0]) == "final_output['result_fingerprint']")
    scope = {"final_output": {"results": []}, "verified_input_capture": linkage,
             "inference_result_fingerprint": inference_result_fingerprint}
    exec(compile(ast.Module(body=[attach, fingerprint], type_ignores=[]), step2.__file__, "exec"), scope)
    assert scope["final_output"]["pre_execution_input_capture"] == linkage
    assert scope["final_output"]["result_fingerprint"] == inference_result_fingerprint(scope["final_output"])


def test_preflight_only_explicit_verified_capture_clears_one_blocker(sealed):
    before = _preflight(sealed)
    assert _preflight(sealed, capture_workspace=None) == before
    assert BLOCKER in before["launch_blockers"] and LIVE in before["launch_blockers"]
    after = _preflight(sealed, capture_workspace=sealed.workspace)
    assert after["launch_blockers"] == [name for name in before["launch_blockers"] if name != BLOCKER]
    assert after["launch_blockers"] == ["native_call_and_token_limits_unresolved", LIVE,
                                       "foundry_usage_and_tariff_mapping_unverified",
                                       "native_sandbox_and_result_bundle_host_unverified"]
    gate = after["pre_execution_capture_gate"]
    assert gate["capture_complete"] and gate["cleared_blockers"] == [BLOCKER]
    assert gate["capture_sha256"] == _verify(sealed)["sha256"]
    assert after["launch_allowed"] is after["full_220_allowed"] is False
    assert gate["evidence_boundary"] == capture.BOUNDARY
    assert "actual_pilot_execution_and_runtime_receipts_unverified" in after["deployment_binding_gate"]["remaining_work"]
    report = _json(after)
    assert str(sealed.parent).encode() not in report and all(value not in report for value in RAW_IDS)


@pytest.mark.parametrize("change", ["missing", "null", "extra", "duplicate-key", "noncanonical", "digest", "secret"])
def test_capture_exact_bytes_and_closed_shape_fail_before_provider(sealed, monkeypatch, change, capsys):
    path = sealed.workspace / capture.CAPTURE_PATH
    data = path.read_bytes()
    value = json.loads(data)
    if change == "missing":
        path.unlink()
    elif change == "null":
        path.write_bytes(b"null")
    elif change == "duplicate-key":
        path.write_bytes(b'{"run_id":"other",' + data[1:])
    elif change == "noncanonical":
        path.write_bytes(data + b"\n")
    else:
        if change == "extra":
            value["verified"] = True
        elif change == "digest":
            value["prepared"]["sha256"] = "0" * 64
        else:
            value["Authorization"] = "Bearer DO-NOT-PRINT"
        path.write_bytes(_json(value))
    _before_provider(sealed, monkeypatch)
    assert "DO-NOT-PRINT" not in capsys.readouterr().out
    report = _preflight(sealed, capture_workspace=sealed.workspace)
    assert report["pre_execution_capture_gate"]["refusal_code"] == pilot.CAPTURE_REFUSAL
    assert BLOCKER in report["launch_blockers"] and LIVE in report["launch_blockers"]
    assert b"DO-NOT-PRINT" not in _json(report)


@pytest.mark.parametrize("change", [
    "prompt", "sector", "occupation", "reference", "source-projection", "fingerprint", "order", "missing-task",
    "extra-task", "duplicate-task", "control-missing", "control-null", "control-other", "control-extra", "run",
    "provider", "deployment", "reasoning", "context", "config-path", "generation", "timeout", "retry", "tokens",
    "resume", "mode", "condition-b", "extra", "task-count",
])
def test_prepared_drift_cannot_hide_behind_a_recomputed_fingerprint(sealed, monkeypatch, change):
    path = sealed.workspace / capture.PREPARED_PATH
    value = json.loads(path.read_bytes())
    task, execution = value["tasks"][0], value["execution"]
    if change in ("prompt", "sector", "occupation"):
        task["instruction" if change == "prompt" else change] += " changed"
    elif change == "reference":
        task["reference_files"] = ["../private-resource"]
    elif change == "source-projection":
        task["source_projection_sha256"] = "0" * 64
    elif change == "order":
        value["tasks"].reverse()
    elif change == "missing-task":
        value["tasks"].pop()
    elif change == "extra-task":
        value["tasks"].append({**task, "task_id": "unregistered"})
    elif change == "duplicate-task":
        value["tasks"][1] = deepcopy(task)
    elif change == "control-missing":
        execution.pop("pilot_input_capture")
    elif change == "control-null":
        execution["pilot_input_capture"] = None
    elif change == "control-other":
        execution["pilot_input_capture"]["run_id"] = "other"
    elif change == "control-extra":
        execution["pilot_input_capture"]["approved"] = True
    elif change == "run":
        value["experiment_id"] = "other"
    elif change in ("provider", "deployment", "reasoning"):
        value["condition_a"]["model"]["reasoning_effort" if change == "reasoning" else change] = "other"
    elif change == "context":
        execution["codex"]["model_context_window"] = 272000
    elif change == "config-path":
        value["config_path"] = "/private/path"
    elif change == "generation":
        value["publication_generation"] += ".other"
    elif change in ("timeout", "retry", "resume", "mode"):
        execution[{"timeout": "timeout", "retry": "max_retries", "resume": "resume_max_rounds", "mode": "mode"}[change]] = 99
    elif change == "tokens":
        execution["tokens"]["code_generation"] = 1
    elif change == "condition-b":
        value["condition_b"] = value["condition_a"]
    elif change == "task-count":
        value["total_tasks"] = 220
    elif change == "extra":
        value["credential"] = "DO-NOT-PRINT"
    value["prepared_fingerprint"] = "0" * 64 if change == "fingerprint" else prepared_fingerprint(value)
    path.write_bytes(json.dumps(value, indent=2, ensure_ascii=False).encode())
    _before_provider(sealed, monkeypatch)


@pytest.mark.parametrize("override", [
    {"resume": True}, {"resume": 0}, {"max_retries": 4}, {"max_retries": "3"}, {"max_retries": True},
    {"resume_max_rounds": 1}, {"resume_max_rounds": False}, {"wall_timeout": 1}, {"wall_timeout": 0},
    {"execution_mode": "subprocess"}, {"condition_key": "condition_b"}, {"pilot_capture_sources": None},
])
def test_raw_overrides_are_rejected_before_coercion_or_auth(sealed, monkeypatch, override):
    _before_provider(sealed, monkeypatch, kwargs=override)


@pytest.mark.parametrize("entry", ["step1", "step2", "checkpoint", "checkpoint-no-context"])
def test_relay_or_restored_checkpoint_cannot_create_a_fresh_capture(sealed, monkeypatch, entry):
    monkeypatch.setenv("GDPVAL_RELAY_LINEAGE_ID", "DO-NOT-PRINT")
    with pytest.raises(capture.PilotInputCaptureRefused):
        if entry == "step1":
            _publish(sealed)
        elif entry == "step2":
            step2.run_inference(resume=False, pilot_capture_sources=sealed.context)
        else:
            step2.validate_restored_checkpoint(**({"pilot_capture_sources": sealed.context}
                                                if entry == "checkpoint" else {}))


@pytest.mark.parametrize("role", [
    "evidence/foundry-pilot-evidence-ready.json", "evidence.foundry-evidence-reservation.json",
    "identity/foundry-pilot-identity-plan.json", "identity/foundry-pilot-identity-ready.json",
    "identity.foundry-pilot-identity-reservation.json", "configs/pilot-config-bundle-ready.json",
    "configs.pilot-config-bundle-reservation.json", "inputs/pilot-input-bundle-ready.json",
    "inputs.pilot-input-bundle-reservation.json", "deployment/pilot-deployment-binding-ready.json",
    "deployment.pilot-deployment-binding-reservation.json", "deployment/pilot-runtime-candidate.json",
    "deployment/pilot-deployment-binding.json", "inputs/data/train-00000-of-00001.parquet",
    "source/batch-runner/core/experiment_config.py", "source/" + pilot.ACTIVE_PLAN,
])
def test_every_upstream_ready_reservation_candidate_and_source_byte_is_rechecked(sealed, monkeypatch, role):
    path = sealed.parent / role
    assert path.is_file()
    path.write_bytes(path.read_bytes() + b"\n")
    _before_provider(sealed, monkeypatch)


@pytest.mark.parametrize("role", ["prepared", "capture", "candidate", "parquet", "reference", "reservation", "resource"])
@pytest.mark.parametrize("damage", ["missing", "symlink", "hardlink"])
def test_missing_or_linked_inputs_refuse_without_following_or_adopting(sealed, monkeypatch, role, damage):
    reference = next(record["path"] for row in json.loads((sealed.workspace / capture.CAPTURE_PATH).read_bytes())["tasks"]
                     for record in row["reference_files"])
    path = {"prepared": sealed.workspace / capture.PREPARED_PATH, "capture": sealed.workspace / capture.CAPTURE_PATH,
            "candidate": sealed.candidate, "parquet": sealed.context.input_bundle / inputs.PARQUET_PATH,
            "reference": sealed.context.input_bundle / reference,
            "reservation": sealed.parent / ("deployment" + deployment.RESERVATION_SUFFIX),
            "resource": sealed.context.account_resource_id_file}[role]
    other = sealed.parent / "private-link-target"
    before = path.read_bytes()
    other.write_bytes(before)
    path.unlink()
    if damage == "symlink":
        path.symlink_to(other)
    elif damage == "hardlink":
        os.link(other, path)
    _before_provider(sealed, monkeypatch)
    assert other.read_bytes() == before


@pytest.mark.parametrize("change", ["extra-ref", "ref-bytes", "extra-parquet", "wrong-sha", "stale-time", "wrong-input-root", "traversal", "symlink-parent"])
def test_closure_staleness_and_actual_consumer_role_are_enforced(sealed, monkeypatch, change):
    if change == "extra-ref":
        (sealed.context.input_bundle / "reference_files/extra.txt").write_bytes(b"extra")
    elif change == "ref-bytes":
        role = next(record["path"] for row in json.loads((sealed.workspace / capture.CAPTURE_PATH).read_bytes())["tasks"]
                    for record in row["reference_files"])
        path = sealed.context.input_bundle / role
        path.write_bytes(b"changed reference")
    elif change == "extra-parquet":
        (sealed.context.input_bundle / "data/extra.parquet").write_bytes(b"extra")
    elif change == "wrong-sha":
        sealed.context = replace(sealed.context, reviewed_source_sha="b" * 40)
    elif change == "stale-time":
        sealed.context = replace(sealed.context, as_of="2026-11-01T00:00:00Z")
    elif change == "wrong-input-root":
        monkeypatch.setattr(step2, "DEFAULT_LOCAL_PATH", sealed.parent / "references")
    elif change == "traversal":
        sealed.context = replace(sealed.context, input_bundle=sealed.context.input_bundle / "../inputs")
    else:
        link = sealed.parent / "linked-workspace"
        link.symlink_to(sealed.workspace, target_is_directory=True)
        monkeypatch.setattr(step2, "WORKSPACE_DIR", link)
    if change == "symlink-parent":
        with pytest.raises(capture.PilotInputCaptureRefused, match="pilot_prepared_read_refused"):
            step2.run_inference(resume=False, pilot_capture_sources=sealed.context)
    else:
        _before_provider(sealed, monkeypatch)


@pytest.mark.parametrize("failure", ["prepared-collision", "capture-collision", "prepared-only", "capture-only",
                                     "write-prepared", "write-capture", "upstream-after-prepared", "capture-race"])
def test_no_clobber_and_partial_pairs_are_never_overwritten_or_reused(fresh, monkeypatch, failure):
    prepared_path, capture_path = fresh.workspace / capture.PREPARED_PATH, fresh.workspace / capture.CAPTURE_PATH
    if failure in ("prepared-collision", "prepared-only"):
        prepared_path.write_bytes(b"existing prepared")
    elif failure in ("capture-collision", "capture-only"):
        capture_path.write_bytes(b"existing capture")
    real = capture._write_no_clobber

    def write(path, data):
        if failure == "write-prepared" and path.name == capture.PREPARED_PATH:
            raise OSError("private failure MUST-NOT-PRINT")
        if path.name == capture.CAPTURE_PATH:
            if failure == "write-capture":
                raise OSError("private failure MUST-NOT-PRINT")
            if failure == "capture-race":
                path.write_bytes(b"racing capture")
        real(path, data)
        if failure == "upstream-after-prepared" and path.name == capture.PREPARED_PATH:
            fresh.candidate.write_bytes(fresh.candidate.read_bytes() + b"\n")

    monkeypatch.setattr(capture, "_write_no_clobber", write)
    with pytest.raises(capture.PilotInputCaptureRefused, match="pilot_step1_refused"):
        _publish(fresh)
    if failure in ("prepared-collision", "prepared-only"):
        assert prepared_path.read_bytes() == b"existing prepared" and not capture_path.exists()
    elif failure in ("capture-collision", "capture-only"):
        assert capture_path.read_bytes() == b"existing capture" and not prepared_path.exists()
    elif failure == "capture-race":
        assert capture_path.read_bytes() == b"racing capture" and prepared_path.is_file()
    else:
        assert not capture_path.exists()
        assert prepared_path.exists() is (failure != "write-prepared")
    before = _tree(fresh.parent)
    with pytest.raises(capture.PilotInputCaptureRefused):
        _publish(fresh)
    assert _tree(fresh.parent) == before


@pytest.mark.parametrize("value", [{}, True, [], {"run_id": pilot.RUN_ID},
    {"run_id": "other", "binding_version": "gpt56-pre-execution-input-v1"},
    {"run_id": pilot.RUN_ID, "binding_version": "other"},
    {"run_id": pilot.RUN_ID, "binding_version": "gpt56-pre-execution-input-v1", "verified": True}])
def test_typed_control_has_no_extra_keys_or_alternate_run(value):
    with pytest.raises(ValueError):
        PilotInputCapture.from_dict(value)


def test_registered_missing_control_and_dual_controls_never_fall_back(fresh):
    raw = json.loads(fresh.candidate.read_bytes())
    for change in ("missing", "null", "dual", "other-run", "other-mode", "condition-b"):
        changed = deepcopy(raw)
        if change == "missing":
            changed["execution"].pop("pilot_input_capture")
        elif change == "null":
            changed["execution"]["pilot_input_capture"] = None
        elif change == "dual":
            changed["execution"]["comparison_input_capture"] = {
                "run_id": "gpt54_v2_codex_v1_codex_r1", "binding_version": "gpt54-pre-execution-input-v1"}
        elif change == "other-run":
            changed["experiment"]["id"] = "other"
        elif change == "other-mode":
            changed["execution"]["mode"] = "subprocess"
        else:
            changed["condition_b"] = changed["condition_a"]
        assert ExperimentConfig.from_dict(changed).validate()
    with pytest.raises(ValueError, match="pilot_capture_sources_required"):
        step1.prepare_tasks(str(fresh.candidate))
    assert not (fresh.workspace / capture.PREPARED_PATH).exists()


def test_legacy_absent_null_keep_serializer_bytes_and_runtime_order(fresh, monkeypatch):
    config = json.loads(fresh.candidate.read_bytes())
    config["experiment"]["id"] = "legacy-capture-noop"
    config["execution"].pop("pilot_input_capture")
    _, tasks = capture.prepare_pilot_inputs(fresh.context, dataset_root=fresh.context.input_bundle, config_path=fresh.candidate)
    monkeypatch.setattr(step1, "GDPValDataLoader", lambda **_: SimpleNamespace(load=lambda: tasks))
    events, snapshots, configs_seen = [], [], []

    def forbidden(*args, **kwargs):
        raise AssertionError("legacy path imported the pilot verifier")

    def boundary(*args, **kwargs):
        events.append("auth_boundary")
        raise ProviderBoundary

    monkeypatch.setattr(capture, "prepare_pilot_inputs", forbidden)
    monkeypatch.setattr(capture, "verify_pilot_input_capture", forbidden)
    monkeypatch.setattr(step2, "_require_host_may_carry_a_benchmark_run", lambda mode: events.append("host_boundary"))
    monkeypatch.setattr(step2.AzureAIRouteSettings, "from_env", boundary)
    path = fresh.parent / "legacy.json"
    for include_null in (False, True):
        if include_null:
            config["execution"]["pilot_input_capture"] = None
        path.write_bytes(_json(config))
        parsed = ExperimentConfig.from_dict(config)
        assert not parsed.validate()
        configs_seen.append(_json(parsed.to_dict()))
        output = step1.prepare_tasks(str(path))
        assert "pilot_input_capture" not in output["execution"]
        snapshots.append((fresh.workspace / capture.PREPARED_PATH).read_bytes())
        with pytest.raises(ProviderBoundary):
            step2.run_inference(resume=False)
        assert not (fresh.workspace / capture.CAPTURE_PATH).exists()
    assert configs_seen[0] == configs_seen[1] and snapshots[0] == snapshots[1]
    assert events == ["host_boundary", "auth_boundary"] * 2


def test_seed_and_fresh_copies_do_not_share_mutations(sealed, capture_seed, monkeypatch):
    second = _fresh(capture_seed, sealed.parent / "independent", monkeypatch)
    original = (second.workspace / capture.CAPTURE_PATH).read_bytes()
    (sealed.workspace / capture.CAPTURE_PATH).write_bytes(b"changed only in first case")
    assert (second.workspace / capture.CAPTURE_PATH).read_bytes() == original
    assert (sealed.workspace / capture.CAPTURE_PATH).stat().st_ino != (second.workspace / capture.CAPTURE_PATH).stat().st_ino
    assert _verify(second)["sha256"] == capture._digest(original)["sha256"]


@pytest.mark.parametrize("role", ["evidence/foundry-pilot-evidence-ready.json",
                                  "deployment/pilot-deployment-binding-ready.json",
                                  PRIVATE + "/account.txt", "source/" + pilot.ACTIVE_PLAN])
def test_upstream_drift_during_projection_is_rechecked_before_acceptance(sealed, monkeypatch, role):
    path = sealed.parent / role
    real = capture._prepared_condition

    def changed(condition):
        result = real(condition)
        path.write_bytes(path.read_bytes() + b"\n")
        return result

    monkeypatch.setattr(capture, "_prepared_condition", changed)
    _before_provider(sealed, monkeypatch)


def test_registered_id_still_requires_control_without_explicit_runtime_context(sealed):
    path = sealed.workspace / capture.PREPARED_PATH
    value = json.loads(path.read_bytes())
    value["execution"].pop("pilot_input_capture")
    value["prepared_fingerprint"] = prepared_fingerprint(value)
    path.write_bytes(json.dumps(value, indent=2, ensure_ascii=False).encode())
    with pytest.raises(capture.PilotInputCaptureRefused):
        step2.run_inference(resume=False)


def test_cli_capture_refusal_is_static_and_plan_only_keeps_both_blockers(sealed, capsys):
    plan_only = pilot.inspect_plan(sealed.plan)
    assert BLOCKER in plan_only["launch_blockers"] and LIVE in plan_only["launch_blockers"]
    assert "pre_execution_capture_gate" not in plan_only
    assert pilot.main(["--plan", str(pilot.PLAN), "--capture-workspace", "/private/DO-NOT-PRINT"]) == 2
    text = capsys.readouterr().out
    # Discard the fixture's ordinary Step 1 status lines, not any gate output.
    report = json.loads(text.splitlines()[-1])
    assert report["pre_execution_capture_gate"]["refusal_code"] == pilot.CAPTURE_REFUSAL
    assert "DO-NOT-PRINT" not in text
