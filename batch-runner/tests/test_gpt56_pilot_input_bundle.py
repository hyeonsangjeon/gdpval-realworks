"""One offline selector for exact local inputs, publication and closed preflight."""

import hashlib
import io
import json
import os
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import yaml

import gpt56_foundry_evidence_intake as evidence
import gpt56_pilot_config_bundle as configs
import gpt56_pilot_identity_plan as identity
import gpt56_pilot_input_bundle as bundle
import gpt56_sol_codex_pilot_preflight as pilot
from core import execution_envelope_tasks as catalog_module
from core.experiment_config import ExperimentConfig
from core.source_identity import source_task_projection_sha256
from .test_gpt56_evidence_preflight_gate import _expected_legacy
from .test_gpt56_foundry_evidence_intake import OPTIONS, _json, _offline, _parse_cache, _seed, _tree
from .test_gpt56_pilot_identity_plan import TASK_IDS, _field_names, _no_execution, _set, source_seed
from .test_gpt56_sol_codex_pilot_preflight import offline_only

CATALOG = pilot.ENVELOPE + "gdpval_task_catalog.json"
ENVELOPE = pilot.ENVELOPE + "advance_check_plan.yaml"
PREPARED_BLOCKER = "prepared_input_bytes_unverified"
LIVE_BLOCKER = "live_inference_identity_and_wire_unverified"
SENTINEL = "private-input-MUST-NOT-APPEAR"


def _digest(data):
    return {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def _copy(files, root):
    for name, data in files:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(data)
        assert path.stat().st_nlink == 1 and not path.is_symlink()


def _activate(monkeypatch, root):
    monkeypatch.setattr(pilot, "ROOT", root)
    monkeypatch.setattr(pilot, "PLAN", root / pilot.ACTIVE_PLAN)
    monkeypatch.setattr(catalog_module, "CATALOG_PATH", root / CATALOG)


def _reservation(root):
    return root.with_name(root.name + bundle.RESERVATION_SUFFIX)


@pytest.fixture(scope="module")
def input_seeds(tmp_path_factory, source_seed, _seed):
    """Real full preparation once per variant; share only immutable bytes.

    The score-free catalog keeps all 220 metadata entries, but parquet content
    is five committed task prompts with tiny synthetic rubrics/references. No
    real 220-task dataset is read. Only synthetic data/catalog/envelope pins
    change; source hashing, selectors and upstream validators remain real.
    """
    source_files = dict(source_seed)
    production_plan = yaml.safe_load(source_files[pilot.ACTIVE_PLAN])
    catalog = json.loads(source_files[CATALOG])
    by_id = {row["task_id"]: row for row in catalog["tasks"]}
    prepared = json.loads((pilot.ROOT / "batch-runner/tests/fixtures/run_record/step1_tasks_prepared.json").read_bytes())
    assert [task["task_id"] for task in prepared["tasks"]] == TASK_IDS
    references, rows = {}, []
    for index, task in enumerate(prepared["tasks"]):
        for role in task["reference_files"]:
            references[role] = f"small offline reference {index}\n".encode()
        rows.append({
            "task_id": task["task_id"], "sector": task["sector"], "occupation": task["occupation"],
            "prompt": task["instruction"], "reference_files": task["reference_files"],
            "reference_file_urls": task["reference_file_urls"],
            "reference_file_hf_uris": [f"hf://datasets/openai/gdpval@{catalog['dataset_revision']}/{role}"
                                       for role in task["reference_files"]],
            "rubric_json": '[\n  {"criterion": "small fixture, not a grade"}\n]\n',
            "rubric_pretty": "Fixture rubric.\nPreserve bytes.\n",
            "deliverable_files": ["withheld-gold-answer"] if by_id[task["task_id"]]["deliverable_file_extensions"] else [],
        })

    @lru_cache(maxsize=12)
    def prepare(linked=False, variant="valid"):
        parent = tmp_path_factory.mktemp("pilot-input-seed")
        changed_rows = deepcopy(rows)
        if variant == "missing-task":
            changed_rows.pop()
        elif variant == "duplicate-task":
            changed_rows.append(deepcopy(changed_rows[0]))
        elif variant == "prompt":
            changed_rows[0]["prompt"] += " changed"
        elif variant == "empty-prompt":
            changed_rows[0]["prompt"] = ""
        elif variant == "rubric-json":
            changed_rows[0]["rubric_json"] = "not JSON"
        elif variant == "cross-task-reference":
            owner = next(row for row in changed_rows if row["reference_files"])
            other = next(row for row in changed_rows if not row["reference_files"])
            other["reference_files"], owner["reference_files"] = owner["reference_files"], []
        elif variant == "duplicate-reference":
            owner = next(row for row in changed_rows if row["reference_files"])
            owner["reference_files"] *= 2
        elif variant == "extra-reference":
            changed_rows[0]["reference_files"].append("reference_files/extra.txt")
        elif variant == "unsafe-reference":
            changed_rows[0]["reference_files"] = ["../outside.txt"]
        else:
            assert variant == "valid"
        stream = io.BytesIO()
        # Physical row order is not execution order. Preserve the original
        # parquet bytes while the real selector restores the five-task order.
        pq.write_table(pa.Table.from_pylist(list(reversed(changed_rows))), stream)
        parquet = stream.getvalue()
        local_catalog = deepcopy(catalog)
        local_catalog["dataset_file_sha256"] = _digest(parquet)["sha256"]
        dataset_key = catalog["dataset_repo_id"] + "@" + catalog["dataset_revision"]
        versions = {dataset_key: _digest(parquet)["sha256"],
                    **{role: _digest(data)["sha256"] for role, data in references.items()}}
        envelope = yaml.safe_load(source_files[ENVELOPE])
        envelope["model_run_conditions"]["shared"]["input_file_versions"] = versions
        files = {**source_files, CATALOG: _json(local_catalog), ENVELOPE: _json(envelope)}
        plan = deepcopy(production_plan)
        plan["dataset"].update(parquet_sha256=_digest(parquet)["sha256"],
                               catalog_sha256=_digest(files[CATALOG])["sha256"], input_file_versions=versions)
        for role in (CATALOG, ENVELOPE):
            plan["source_pins"][role] = _digest(files[role])["sha256"]
        files[pilot.ACTIVE_PLAN] = _json(plan)
        _copy(tuple(sorted(files.items())), parent / "source")
        _copy(tuple(references.items()), parent / "references")
        (parent / "source.parquet").write_bytes(parquet)
        options = {}
        with pytest.MonkeyPatch.context() as setup:
            _activate(setup, parent / "source")
            assert pilot.inspect_plan(plan)["configuration_valid"]
            if linked:
                raw = dict(_seed)
                intake = json.loads(raw[evidence.INTAKE_PATH])
                intake["plan_sha256"] = pilot.seal(plan)
                raw[evidence.INTAKE_PATH] = _json(intake)
                _copy(tuple(raw.items()), parent / "raw-evidence")
                evidence.publish_foundry_evidence(source=parent / "raw-evidence", destination=parent / "evidence", **OPTIONS)
                options = {"evidence_bundle": parent / "evidence", **OPTIONS}
            identity.publish_pilot_identity(plan, destination=parent / "identity", **options)
            configs.materialize_pilot_config_bundle(
                plan, identity_bundle=parent / "identity", destination=parent / "configs", **options,
            )
            if variant == "valid":
                result = bundle.materialize_pilot_input_bundle(
                    plan, config_bundle=parent / "configs", identity_bundle=parent / "identity",
                    dataset_parquet=parent / "source.parquet", reference_root=parent / "references",
                    destination=parent / "inputs", **options,
                )
                assert (parent / "inputs" / bundle.READY_PATH).read_bytes() == result.canonical_bytes()
        return _tree(parent)
    return prepare


def _fresh(input_seeds, tmp_path, monkeypatch, *, linked=False, published=False, variant="valid"):
    files = input_seeds(linked, variant)
    if not published:
        files = tuple((name, data) for name, data in files
                      if not name.startswith("inputs/") and name != "inputs" + bundle.RESERVATION_SUFFIX)
    _copy(files, tmp_path)
    _activate(monkeypatch, tmp_path / "source")
    return SimpleNamespace(
        parent=tmp_path, root=tmp_path / "inputs", plan=pilot.load_plan(pilot.PLAN),
        options={"config_bundle": tmp_path / "configs", "identity_bundle": tmp_path / "identity",
                 **({"evidence_bundle": tmp_path / "evidence", **OPTIONS} if linked else {})},
        parquet=tmp_path / "source.parquet", references=tmp_path / "references",
    )


@pytest.fixture
def unpublished(input_seeds, tmp_path, monkeypatch, _no_execution):
    return _fresh(input_seeds, tmp_path, monkeypatch)


@pytest.fixture
def installed(input_seeds, tmp_path, monkeypatch, _no_execution):
    return _fresh(input_seeds, tmp_path, monkeypatch, published=True)


def _publish(case):
    return bundle.materialize_pilot_input_bundle(
        case.plan, destination=case.root, dataset_parquet=case.parquet, reference_root=case.references, **case.options,
    )


def _verify(case):
    return bundle.verify_pilot_input_bundle(case.plan, bundle_root=case.root, **case.options)


def _refused_before_write(case):
    before = _tree(case.parent)
    with pytest.raises(bundle.PilotInputBundleRefused):
        _publish(case)
    assert not os.path.lexists(case.root) and not os.path.lexists(_reservation(case.root))
    assert _tree(case.parent) == before


@pytest.mark.parametrize("linked", [False, True])
def test_exact_local_bundle_uses_real_validators_and_ready_last(input_seeds, tmp_path, monkeypatch, linked):
    case = _fresh(input_seeds, tmp_path, monkeypatch, linked=linked)
    before, writes, checked, projected = dict(_tree(tmp_path)), [], [], []
    real_write, real_verify, real_project = bundle._write_no_clobber, configs.verify_pilot_config_bundle, bundle._dataset_tasks

    def write(path, data):
        assert not (case.root / bundle.READY_PATH).exists()
        writes.append(path.relative_to(tmp_path).as_posix())
        return real_write(path, data)

    def verify(*args, **kwargs):
        result = real_verify(*args, **kwargs)
        checked.append(result)
        return result

    def project(data, task_ids):
        projected.append(task_ids)
        return real_project(data, task_ids)

    monkeypatch.setattr(bundle, "_write_no_clobber", write)
    monkeypatch.setattr(configs, "verify_pilot_config_bundle", verify)
    monkeypatch.setattr(bundle, "_dataset_tasks", project)
    result = _publish(case)
    assert len(checked) == 2 and checked[0] == checked[1]
    assert projected == [tuple(TASK_IDS), tuple(TASK_IDS)]
    assert writes == ["inputs" + bundle.RESERVATION_SUFFIX,
                      *("inputs/" + name for name, _ in result.files), "inputs/" + bundle.READY_PATH]
    assert _verify(case) == result
    assert _json(result.as_dict()) == result.canonical_bytes()
    assert result.sha256 == _digest(result.canonical_bytes())["sha256"]
    assert _reservation(case.root).read_bytes() == bundle._reservation(result)
    for role, data in result.files:
        path = case.root / role
        assert path.read_bytes() == data and path.stat().st_nlink == 1 and not path.is_symlink()
    after = dict(_tree(tmp_path))
    assert {name: after[name] for name in before} == before
    document = result.as_dict()
    manifest = json.loads((case.options["config_bundle"] / configs.PREPARED_PATH).read_bytes())
    expected_refs = {role for row in manifest["tasks"] for role in (item["path"] for item in row["reference_files"])}
    assert set(dict(result.files)) == {bundle.PARQUET_PATH, *expected_refs}
    assert len(expected_refs) == 2 and dict(result.files)[bundle.PARQUET_PATH] == case.parquet.read_bytes()
    assert document["tasks"] == manifest["tasks"] and document["task_ids"] == TASK_IDS
    assert document["run_id"] == pilot.RUN_ID and document["condition"] == "codex_foundry" and document["repeat"] == 1
    assert document["expected_task_count"] == 5
    assert document["dataset"]["revision"] == case.plan["dataset"]["revision"]
    assert document["dataset"]["parquet"] == {"path": bundle.PARQUET_PATH, **_digest(case.parquet.read_bytes())}
    assert document["files"] == {name: _digest(data) for name, data in result.files}
    assert document["config_bundle"] == {"path": configs.READY_PATH, **_digest(checked[0].canonical_bytes())}
    assert document["source_pins"] == case.plan["source_pins"] and len(document["source_pins"]) == 56
    assert case.plan["input_bundle"] == pilot.INPUT_BUNDLE
    assert document["evidence_linkage"] == checked[0].as_dict()["evidence_linkage"]
    assert (document["evidence_linkage"] is not None) is linked
    projections, _ = real_project(case.parquet.read_bytes(), tuple(TASK_IDS))
    for row, recorded in zip(projections, document["source_tasks"]):
        assert recorded["source_projection_sha256"] == source_task_projection_sha256(**row)
        assert recorded["text_bytes"]["prompt"] == _digest(row["prompt"].encode())
        assert recorded["text_bytes"]["rubric_json"] == _digest(row["rubric_json"].encode())
    assert not {"command", "argv", "endpoint", "credential", "observed", "prompt", "rubric_json"} & _field_names({
        key: value for key, value in document.items() if key != "source_tasks"
    })
    assert str(tmp_path).encode() not in result.canonical_bytes()
    assert document["evidence_boundary"] == "local_prepared_input_consistency_not_model_consumption"
    assert document["launch_allowed"] is document["full_220_allowed"] is False
    runtime = json.loads((case.options["config_bundle"] / configs.RUNTIME_PATH).read_bytes())
    assert runtime["deployment"] is runtime["execution"] is None and runtime["runnable"] is False
    with pytest.raises((TypeError, ValueError, AttributeError)):
        ExperimentConfig.from_dict(runtime)


@pytest.mark.parametrize("explicit_null", [False, True])
def test_no_bundle_retains_both_parts_without_calling_new_verifier(unpublished, monkeypatch, explicit_null):
    def forbidden(*args, **kwargs):
        raise AssertionError("no-bundle path called input verification")

    monkeypatch.setattr(bundle, "verify_pilot_input_bundle", forbidden)
    options = {"input_bundle": None, "config_bundle": None} if explicit_null else {}
    report = pilot.inspect_plan(unpublished.plan, **options)
    assert _json(report) == _json(_expected_legacy(unpublished.plan))
    assert PREPARED_BLOCKER in report["launch_blockers"] and LIVE_BLOCKER in report["launch_blockers"]
    assert "live_identity_and_input_bytes_unverified" not in report["launch_blockers"]
    assert len(report["launch_blockers"]) == 11
    assert report["launch_allowed"] is report["full_220_allowed"] is False
    assert "input_bundle_gate" not in report


@pytest.mark.parametrize("linked", [False, True])
def test_explicit_verified_bundle_closes_only_prepared_input_requirement(input_seeds, tmp_path, monkeypatch, linked):
    case = _fresh(input_seeds, tmp_path, monkeypatch, linked=linked, published=True)
    prior_options = {key: value for key, value in case.options.items() if key != "config_bundle"}
    before = pilot.inspect_plan(case.plan, **prior_options)
    state = _tree(tmp_path)
    report = pilot.inspect_plan(case.plan, input_bundle=case.root, **case.options)
    expected = [name for name in before["launch_blockers"] if name != PREPARED_BLOCKER]
    assert report["launch_blockers"] == expected and len(expected) == len(before["launch_blockers"]) - 1
    assert {LIVE_BLOCKER, "native_sandbox_and_result_bundle_host_unverified", "actual_pilot_deployment_not_prepared"} <= set(expected)
    if linked:
        assert expected == [
            "native_call_and_token_limits_unresolved",
            LIVE_BLOCKER,
            "foundry_usage_and_tariff_mapping_unverified",
            "native_sandbox_and_result_bundle_host_unverified",
            "actual_pilot_deployment_not_prepared",
            "prepared_request_capture_unverified",
        ]
    gate = report["input_bundle_gate"]
    assert gate["input_bundle_complete"] is True and gate["cleared_blockers"] == [PREPARED_BLOCKER]
    assert gate["consumed_bundle_sha256"] == _digest((case.root / bundle.READY_PATH).read_bytes())["sha256"]
    assert gate["remaining_blockers"] == report["identity_plan_gate"]["remaining_blockers"] == expected
    assert gate["evidence_boundary"] == bundle.BOUNDARY
    assert report["launch_allowed"] is report["full_220_allowed"] is False
    assert not {"claims", "subject", "deployment", "account", "endpoint", "credential", "argv", "command"} & _field_names(report)
    assert str(tmp_path).encode() not in _json(report)
    assert _tree(tmp_path) == state


@pytest.mark.parametrize("missing", ["input_bundle", "config_bundle", "identity_bundle"])
def test_gate_requires_all_explicit_linkages(installed, missing):
    options = {"input_bundle": installed.root, **installed.options}
    options.pop(missing)
    report = pilot.inspect_plan(installed.plan, **options)
    assert report["input_bundle_gate"]["refusal_code"] == pilot.INPUT_REFUSAL
    assert PREPARED_BLOCKER in report["launch_blockers"] and LIVE_BLOCKER in report["launch_blockers"]


@pytest.mark.parametrize("damage", [
    "missing-parquet", "missing-reference", "parquet-bytes", "reference-bytes", "extra-file", "extra-directory",
    "symlink-parquet", "hardlink-parquet", "symlink-reference", "hardlink-reference", "symlink-reference-root",
    "parquet-parent-traversal", "reference-parent-traversal",
])
def test_original_inputs_fail_closed_before_any_publication(unpublished, damage):
    case = unpublished
    reference = next(path for path in case.references.rglob("*") if path.is_file())
    selected = case.parquet if "parquet" in damage else reference
    if damage.startswith("missing"):
        selected.unlink()
    elif damage.endswith("bytes"):
        selected.write_bytes(selected.read_bytes() + b"drift")
    elif damage == "extra-file":
        (case.references / "extra.txt").write_bytes(b"not selected")
    elif damage == "extra-directory":
        (case.references / "extra-empty").mkdir()
    elif damage == "symlink-reference-root":
        other = case.parent / "reference-alias"
        other.symlink_to(case.references, target_is_directory=True)
        case.references = other
    elif damage.endswith("parent-traversal"):
        (case.parent / "detour").mkdir()
        if "parquet" in damage:
            case.parquet = case.parent / "detour" / ".." / "source.parquet"
        else:
            case.references = case.parent / "detour" / ".." / "references"
    else:
        other = case.parent / "independent-copy"
        other.write_bytes(selected.read_bytes())
        selected.unlink()
        selected.symlink_to(other) if damage.startswith("symlink") else os.link(other, selected)
    _refused_before_write(case)


@pytest.mark.parametrize("variant", [
    "missing-task", "duplicate-task", "prompt", "empty-prompt", "rubric-json",
    "cross-task-reference", "duplicate-reference", "extra-reference", "unsafe-reference",
])
def test_real_parquet_projection_refuses_inconsistent_pinned_rows(input_seeds, tmp_path, monkeypatch, variant):
    case = _fresh(input_seeds, tmp_path, monkeypatch, variant=variant)
    assert configs.verify_pilot_config_bundle(case.plan, bundle_root=case.options["config_bundle"],
                                             identity_bundle=case.options["identity_bundle"])
    _refused_before_write(case)


@pytest.mark.parametrize("keys,value", [
    (("dataset", "revision"), "a" * 40), (("dataset", "parquet_sha256"), "a" * 64),
    (("dataset", "catalog_sha256"), "a" * 64), (("pilot", "run_id"), "other-run"),
    (("pilot", "repeats"), 2), (("launch_enabled",), True),
    (("pilot", "full_220_enabled"), True), (("input_bundle", "source_base_sha"), "a" * 40),
    (("source_pins", "batch-runner/gpt56_pilot_input_bundle.py"), "a" * 64),
])
def test_wrong_or_stale_contract_never_reserves(unpublished, keys, value):
    _set(unpublished.plan, keys, value)
    _refused_before_write(unpublished)


@pytest.mark.parametrize("damage", ["reordered", "missing", "duplicate", "extra", "unsafe-role", "overlapping-role"])
def test_task_and_role_contract_is_closed(unpublished, damage):
    tasks = unpublished.plan["dataset"]["tasks"]
    if damage == "reordered":
        tasks.reverse()
    elif damage == "missing":
        tasks.pop()
    elif damage == "duplicate":
        tasks[1] = deepcopy(tasks[0])
    elif damage == "extra":
        tasks.append({"task_id": "extra", "prompt_sha256": "a" * 64})
    else:
        versions = unpublished.plan["dataset"]["input_file_versions"]
        role = "../outside" if damage == "unsafe-role" else bundle.PARQUET_PATH
        versions[role] = "a" * 64
    _refused_before_write(unpublished)


@pytest.mark.parametrize("target", [
    "config-ready", "prepared", "runtime", "config-reservation", "identity-plan", "identity-ready",
    "identity-reservation", "source-pin", "source-plan",
])
def test_upstream_current_bytes_are_reverified(unpublished, target):
    root = unpublished.parent
    path = {
        "config-ready": root / "configs" / configs.READY_PATH,
        "prepared": root / "configs" / configs.PREPARED_PATH,
        "runtime": root / "configs" / configs.RUNTIME_PATH,
        "config-reservation": root / ("configs" + configs.RESERVATION_SUFFIX),
        "identity-plan": root / "identity" / identity.PLAN_PATH,
        "identity-ready": root / "identity" / identity.READY_PATH,
        "identity-reservation": root / ("identity" + identity.RESERVATION_SUFFIX),
        "source-pin": root / "source/batch-runner/core/source_identity.py",
        "source-plan": root / "source" / pilot.ACTIVE_PLAN,
    }[target]
    if target == "source-plan":
        # The active contract is canonical JSON, not the YAML's whitespace.
        changed = yaml.safe_load(path.read_bytes())
        changed["pilot"]["run_id"] = "stale-run"
        path.write_bytes(_json(changed))
    else:
        path.write_bytes(path.read_bytes() + b"\n")
    _refused_before_write(unpublished)


@pytest.mark.parametrize("damage", ["existing-root", "root-file", "reservation", "partial", "symlink-root", "symlink-parent", "traversal", "source-overlap", "config-overlap"])
def test_destination_cannot_adopt_existing_or_unsafe_paths(unpublished, damage):
    case = unpublished
    if damage == "existing-root":
        case.root.mkdir()
    elif damage == "root-file":
        case.root.write_bytes(b"existing")
    elif damage == "reservation":
        _reservation(case.root).write_bytes(b"previous attempt")
    elif damage == "partial":
        case.root.mkdir()
        (case.root / "partial").write_bytes(b"keep")
        _reservation(case.root).write_bytes(b"keep")
    elif damage == "symlink-root":
        case.root.symlink_to(case.references, target_is_directory=True)
    elif damage == "symlink-parent":
        alias = case.parent / "alias"
        alias.symlink_to(case.parent, target_is_directory=True)
        case.root = alias / "inputs"
    elif damage == "traversal":
        case.root = case.parent / "uncreated" / ".." / "inputs"
    elif damage == "source-overlap":
        case.root = case.references / "new-inputs"
    else:
        case.root = case.options["config_bundle"] / "new-inputs"
    before = _tree(case.parent)
    with pytest.raises(bundle.PilotInputBundleRefused):
        _publish(case)
    assert _tree(case.parent) == before


@pytest.mark.parametrize("role,damage", [
    (role, damage) for role in ("ready", "reservation", "parquet", "reference")
    for damage in ("missing", "bytes", "symlink", "hardlink")
] + [("extra-file", "extra"), ("extra-directory", "extra")])
def test_installed_byte_inventory_and_links_are_not_trusted(installed, role, damage):
    path = {"ready": installed.root / bundle.READY_PATH, "reservation": _reservation(installed.root),
            "parquet": installed.root / bundle.PARQUET_PATH,
            "reference": next(path for path in (installed.root / "reference_files").rglob("*") if path.is_file()),
            "extra-file": installed.root / "extra.txt", "extra-directory": installed.root / "extra-empty"}[role]
    if damage == "missing":
        path.unlink()
    elif damage == "bytes":
        path.write_bytes(path.read_bytes() + b" ")
    elif damage in ("symlink", "hardlink"):
        other = installed.parent / "other-bytes"
        other.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(other) if damage == "symlink" else os.link(other, path)
    elif role == "extra-file":
        path.write_bytes(b"unexpected")
    else:
        path.mkdir()
    before = _tree(installed.parent)
    with pytest.raises(bundle.PilotInputBundleRefused):
        _verify(installed)
    report = pilot.inspect_plan(installed.plan, input_bundle=installed.root, **installed.options)
    assert report["input_bundle_gate"]["input_bundle_complete"] is False
    assert PREPARED_BLOCKER in report["launch_blockers"] and LIVE_BLOCKER in report["launch_blockers"]
    assert report["launch_allowed"] is report["full_220_allowed"] is False
    assert _tree(installed.parent) == before


@pytest.mark.parametrize("keys,value", [
    (("run_id",), "other"), (("condition",), "sandbox_v2"), (("repeat",), 2),
    (("task_ids",), list(reversed(TASK_IDS))), (("task_ids",), TASK_IDS + ["extra"]),
    (("contract_sha256",), "a" * 64), (("dataset", "revision"), "a" * 40),
    (("config_bundle", "sha256"), "a" * 64), (("prepared_manifest", "sha256"), "a" * 64),
    (("evidence_linkage",), {"self_asserted": True}), (("launch_allowed",), True),
    (("full_220_allowed",), True), (("extra",), True),
])
def test_self_consistent_marker_forgery_cannot_replace_recomputation(installed, keys, value):
    path = installed.root / bundle.READY_PATH
    document = json.loads(path.read_bytes())
    _set(document, keys, value)
    path.write_bytes(_json(document))
    reservation = json.loads(_reservation(installed.root).read_bytes())
    reservation["intended_ready"] = _digest(path.read_bytes())
    _reservation(installed.root).write_bytes(_json(reservation))
    with pytest.raises(bundle.PilotInputBundleRefused):
        _verify(installed)


@pytest.mark.parametrize("failure_index", range(5))
def test_each_atomic_file_failure_retains_partial_state_without_ready(unpublished, monkeypatch, failure_index):
    original = dict(_tree(unpublished.parent))
    real, calls = bundle._write_no_clobber, []

    def fail(path, data):
        calls.append(path)
        if len(calls) - 1 == failure_index:
            raise OSError("fixture write failure")
        real(path, data)

    monkeypatch.setattr(bundle, "_write_no_clobber", fail)
    with pytest.raises(bundle.PilotInputBundleRefused):
        _publish(unpublished)
    assert len(calls) == failure_index + 1
    assert not (unpublished.root / bundle.READY_PATH).exists()
    after = dict(_tree(unpublished.parent))
    assert {name: after[name] for name in original} == original
    if failure_index:
        assert _reservation(unpublished.root).is_file()
        before = _tree(unpublished.parent)
        monkeypatch.setattr(bundle, "_write_no_clobber", real)
        with pytest.raises(bundle.PilotInputBundleRefused):
            _publish(unpublished)
        assert _tree(unpublished.parent) == before
    else:
        assert not unpublished.root.exists() and not _reservation(unpublished.root).exists()


@pytest.mark.parametrize("failure_index", range(5))
def test_exclusive_directory_failure_keeps_reservation(unpublished, monkeypatch, failure_index):
    real, calls = os.mkdir, []

    def fail(path, *args, **kwargs):
        calls.append(path)
        if len(calls) - 1 == failure_index:
            raise OSError("fixture mkdir failure")
        return real(path, *args, **kwargs)

    monkeypatch.setattr(os, "mkdir", fail)
    with pytest.raises(bundle.PilotInputBundleRefused):
        _publish(unpublished)
    assert len(calls) == failure_index + 1
    assert _reservation(unpublished.root).is_file()
    assert not (unpublished.root / bundle.READY_PATH).exists()


@pytest.mark.parametrize("damage", ["source-parquet", "source-reference", "config", "source-pin", "installed", "extra-file", "reservation"])
def test_drift_during_publication_leaves_no_ready(unpublished, monkeypatch, damage):
    real = bundle._write_no_clobber

    def mutate(path, data):
        real(path, data)
        if path != unpublished.root / bundle.PARQUET_PATH:
            return
        selected = {
            "source-parquet": unpublished.parquet,
            "source-reference": next(path for path in unpublished.references.rglob("*") if path.is_file()),
            "config": unpublished.options["config_bundle"] / configs.PREPARED_PATH,
            "source-pin": pilot.ROOT / "batch-runner/core/source_identity.py",
            "installed": path, "reservation": _reservation(unpublished.root),
            "extra-file": unpublished.root / "extra.txt",
        }[damage]
        selected.write_bytes((selected.read_bytes() if selected.exists() else b"") + b"drift")

    monkeypatch.setattr(bundle, "_write_no_clobber", mutate)
    with pytest.raises(bundle.PilotInputBundleRefused):
        _publish(unpublished)
    assert _reservation(unpublished.root).exists()
    assert not (unpublished.root / bundle.READY_PATH).exists()


@pytest.mark.parametrize("target", ["destination-parent", "destination-root", "source-reference-root"])
def test_held_parent_replacement_is_refused_even_with_equal_bytes(unpublished, monkeypatch, target):
    parent = unpublished.parent / "target-parent"
    parent.mkdir()
    unpublished.root = parent / "inputs"
    real = bundle._write_no_clobber
    displaced = unpublished.parent / "displaced"

    def replace_parent(path, data):
        real(path, data)
        if path != unpublished.root / bundle.PARQUET_PATH:
            return
        selected = {"destination-parent": parent, "destination-root": unpublished.root,
                    "source-reference-root": unpublished.references}[target]
        files = _tree(selected)
        selected.rename(displaced)
        selected.mkdir()
        _copy(files, selected)

    monkeypatch.setattr(bundle, "_write_no_clobber", replace_parent)
    with pytest.raises(bundle.PilotInputBundleRefused):
        _publish(unpublished)
    assert not (unpublished.root / bundle.READY_PATH).exists()
    assert not list(displaced.rglob(bundle.READY_PATH))


@pytest.mark.parametrize("damage", ["omitted", "wrong-sha", "stale", "artifact", "ready", "reservation"])
def test_optional_evidence_remains_verified_not_copied(input_seeds, tmp_path, monkeypatch, damage):
    case = _fresh(input_seeds, tmp_path, monkeypatch, linked=True, published=True)
    if damage == "omitted":
        case.options = {key: value for key, value in case.options.items()
                        if key in {"config_bundle", "identity_bundle"}}
    elif damage == "wrong-sha":
        case.options["reviewed_source_sha"] = "d" * 40
    elif damage == "stale":
        case.options["as_of"] = "2026-10-02T00:00:00Z"
    else:
        root = case.options["evidence_bundle"]
        path = {"artifact": root / "artifacts/context.json", "ready": root / evidence.READY_PATH,
                "reservation": root.with_name(root.name + ".foundry-evidence-reservation.json")}[damage]
        path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(bundle.PilotInputBundleRefused):
        _verify(case)
    report = pilot.inspect_plan(case.plan, input_bundle=case.root, **case.options)
    assert PREPARED_BLOCKER in report["launch_blockers"] and LIVE_BLOCKER in report["launch_blockers"]


@pytest.mark.parametrize("stage", ["sha256", "as_dict"])
def test_report_errors_after_real_verification_retain_the_blocker(installed, monkeypatch, stage):
    real = bundle.verify_pilot_input_bundle
    calls = []

    def broken(*args, **kwargs):
        verified = real(*args, **kwargs)
        calls.append(verified)

        class Broken:
            @property
            def sha256(self):
                raise ValueError(SENTINEL)

            def as_dict(self):
                if stage == "as_dict":
                    raise ValueError(SENTINEL)
                return verified.as_dict()
        return Broken()

    monkeypatch.setattr(bundle, "verify_pilot_input_bundle", broken)
    report = pilot.inspect_plan(installed.plan, input_bundle=installed.root, **installed.options)
    assert len(calls) == 1 and report["input_bundle_gate"]["cleared_blockers"] == []
    assert PREPARED_BLOCKER in report["launch_blockers"] and SENTINEL.encode() not in _json(report)


@pytest.mark.parametrize("mode", ["publish", "verify", "preflight"])
def test_cli_uses_the_real_offline_paths(unpublished, capsys, mode):
    case = unpublished
    arguments = ["--plan", str(pilot.PLAN), "--config-bundle", str(case.options["config_bundle"]),
                 "--identity-bundle", str(case.options["identity_bundle"])]
    if mode != "publish":
        _publish(case)
    if mode == "publish":
        status = bundle.main([*arguments, "--destination", str(case.root), "--dataset-parquet", str(case.parquet),
                              "--reference-root", str(case.references)])
    elif mode == "verify":
        status = bundle.main([*arguments, "--verify-bundle", str(case.root)])
    else:
        status = pilot.main([*arguments, "--input-bundle", str(case.root)])
    assert status == (2 if mode == "preflight" else 0)
    output = capsys.readouterr()
    report = json.loads(output.out)
    assert not output.err and str(case.parent) not in output.out
    assert report["launch_allowed"] is report["full_220_allowed"] is False
    assert _verify(case)


@pytest.mark.parametrize("entry,args", [
    (bundle.main, ["--unknown", SENTINEL]), (bundle.main, ["--config-bundle", SENTINEL]),
    (bundle.main, ["--plan", SENTINEL]), (pilot.main, ["--input-bundle", SENTINEL]),
    (pilot.main, ["--input-bundel", SENTINEL]), (pilot.main, ["--config-bundle", SENTINEL]),
])
def test_cli_refusals_do_not_echo_untrusted_paths(entry, args, capsys):
    assert entry(args) == 2
    output = capsys.readouterr()
    assert not output.err and SENTINEL not in output.out
    assert json.loads(output.out)["launch_allowed"] is False


def test_mutations_never_reach_another_copy_or_seed(installed, input_seeds):
    seed = input_seeds()
    second = installed.parent / "independent"
    _copy(seed, second)
    before = _tree(second)
    (installed.root / bundle.PARQUET_PATH).write_bytes(b"changed only here")
    assert _tree(second) == before == seed and input_seeds() == seed


def test_complete_destination_cannot_be_reused(installed):
    before = _tree(installed.parent)
    with pytest.raises(bundle.PilotInputBundleRefused):
        _publish(installed)
    assert _tree(installed.parent) == before


def test_production_pins_refuse_synthetic_parquet(unpublished, source_seed, monkeypatch):
    production = unpublished.parent / "production-source"
    _copy(source_seed, production)
    _activate(monkeypatch, production)
    plan = pilot.load_plan(pilot.PLAN)
    identity_root, config_root = unpublished.parent / "production-identity", unpublished.parent / "production-configs"
    identity.publish_pilot_identity(plan, destination=identity_root)
    configs.materialize_pilot_config_bundle(plan, identity_bundle=identity_root, destination=config_root)
    unpublished.plan = plan
    unpublished.options = {"identity_bundle": identity_root, "config_bundle": config_root}
    _refused_before_write(unpublished)
