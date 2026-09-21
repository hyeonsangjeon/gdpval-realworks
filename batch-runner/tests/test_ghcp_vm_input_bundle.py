"""Local file publication only; synthetic parquet/references are not live evidence."""

from __future__ import annotations

import io
import json
import os
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import yaml

from core.agentic_v2_oci import canonical_json, sha256_bytes
from core.source_identity import source_task_projection_sha256
from .test_ghcp_vm_gate_contract import EXPECTED_BLOCKERS, FALSE_FLAGS, offline_only

ROOT = Path(__file__).resolve().parents[2]
INPUT_BLOCKER = "original_task_input_materialization_unverified"
PRIVATE = "PRIVATE_INPUT_MUST_NOT_APPEAR"


def identity(data):
    return {"size": len(data), "sha256": sha256_bytes(data)}


def write_files(root, files):
    for role, data in files.items():
        path = root / role
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(data)


@pytest.fixture
def inputs(tmp_path, monkeypatch, offline_only):
    """Fresh source pins and files per case; never cache an owner or verdict.

    The existing fixed-five fixture supplies the original prompts and roles.
    Only the parquet/rubric/reference bytes and their fixture-local pins differ
    from the real dataset. The real catalog selector, plan checker, source
    projections, file readers, publication and verification remain in use.
    """
    import ghcp_vm_gate_preflight as gate
    import ghcp_vm_input_bundle as bundle

    production = gate.load_plan()
    originals = {role: (ROOT / role).read_bytes() for role in gate.REQUIRED_SOURCES}
    original_pins = dict(gate.PINNED_SOURCES)
    prepared = json.loads((ROOT / "batch-runner/tests/fixtures/run_record/step1_tasks_prepared.json").read_bytes())

    def make(variant="valid"):
        parent = tmp_path / variant
        parent.mkdir()
        source = parent / "reviewed-source"
        references = parent / "private-references"
        references.mkdir()
        files = dict(originals)
        plan = deepcopy(production)
        historical = yaml.safe_load(files[gate.HISTORICAL_PLAN])
        catalog = json.loads(files[gate.CATALOG])
        advance = yaml.safe_load(files[gate.ADVANCE_PLAN])
        by_id = {row["task_id"]: row for row in catalog["tasks"]}
        reference_bytes, rows = {}, []
        for index, task in enumerate(prepared["tasks"]):
            for role in task["reference_files"]:
                reference_bytes[role] = f"{PRIVATE} synthetic reference {index} {role}\n".encode()
            rows.append({
                "task_id": task["task_id"], "sector": task["sector"], "occupation": task["occupation"],
                "prompt": task["instruction"], "reference_files": list(task["reference_files"]),
                "reference_file_urls": task["reference_file_urls"],
                "reference_file_hf_uris": [
                    f"hf://datasets/openai/gdpval@{catalog['dataset_revision']}/{role}"
                    for role in task["reference_files"]
                ],
                "rubric_json": '[\n  {"criterion": "synthetic rubric, not a grade"}\n]\n',
                "rubric_pretty": f"{PRIVATE} synthetic rubric.\n",
                "deliverable_files": ["withheld-original" + suffix
                                      for suffix in by_id[task["task_id"]]["deliverable_file_extensions"]],
            })
        registered_rows = deepcopy(rows)
        if variant == "missing-task":
            rows.pop()
        elif variant == "duplicate-task":
            rows.append(deepcopy(rows[0]))
        elif variant == "wrong-prompt":
            rows[0]["prompt"] += " changed"
        elif variant == "empty-prompt":
            rows[0]["prompt"] = ""
        elif variant == "invalid-rubric":
            rows[0]["rubric_json"] = "not JSON " + PRIVATE
        elif variant == "duplicate-rubric-key":
            rows[0]["rubric_json"] = '{"criterion":"first","criterion":"second"}'
        elif variant == "duplicate-reference":
            next(row for row in rows if row["reference_files"])["reference_files"] *= 2
        elif variant == "foreign-reference":
            owner = next(row for row in rows if row["reference_files"])
            other = next(row for row in rows if not row["reference_files"])
            other["reference_files"], owner["reference_files"] = owner["reference_files"], []
        elif variant == "unsafe-reference":
            rows[0]["reference_files"] = ["../private/credential.json"]
        elif variant == "extra-reference":
            rows[0]["reference_files"].append("reference_files/private-extra.txt")
        else:
            assert variant == "valid"

        # Whole original bytes are staged, including rows outside the pilot.
        outside = deepcopy(registered_rows[0])
        outside.update(task_id="synthetic-outside-pilot", prompt=PRIVATE + " outside scope")
        stream = io.BytesIO()
        pq.write_table(pa.Table.from_pylist([outside, *reversed(rows)]), stream)
        parquet_bytes = stream.getvalue()
        parquet = parent / "private-source.parquet"
        parquet.write_bytes(parquet_bytes)
        write_files(references, reference_bytes)
        dataset_key = catalog["dataset_repo_id"] + "@" + catalog["dataset_revision"]
        versions = {dataset_key: sha256_bytes(parquet_bytes),
                    **{role: sha256_bytes(data) for role, data in reference_bytes.items()}}
        catalog["dataset_file_sha256"] = sha256_bytes(parquet_bytes)
        files[gate.CATALOG] = canonical_json(catalog)
        historical["dataset"].update(
            parquet_sha256=sha256_bytes(parquet_bytes), catalog_sha256=sha256_bytes(files[gate.CATALOG]),
            input_file_versions=versions,
        )
        advance["model_run_conditions"]["shared"]["input_file_versions"] = versions
        files[gate.HISTORICAL_PLAN] = canonical_json(historical)
        files[gate.ADVANCE_PLAN] = canonical_json(advance)
        pins = dict(original_pins)
        for role in (gate.CATALOG, gate.HISTORICAL_PLAN, gate.ADVANCE_PLAN):
            pins[role] = plan["source_pins"][role] = sha256_bytes(files[role])
        plan["dataset"].update(parquet_sha256=sha256_bytes(parquet_bytes),
                               catalog_sha256=sha256_bytes(files[gate.CATALOG]))
        write_files(source, {**files, gate.PLAN_PATH: canonical_json(plan)})
        monkeypatch.setattr(gate, "ROOT", source)
        monkeypatch.setattr(gate, "PLAN", source / gate.PLAN_PATH)
        monkeypatch.setattr(gate, "PINNED_SOURCES", pins)
        report = gate.inspect_plan(plan)
        assert report["configuration_valid"] is True
        assert report["task_ids"] == [row["task_id"] for row in registered_rows]
        return SimpleNamespace(
            gate=gate, bundle=bundle, parent=parent, source=source, plan=plan,
            plan_path=source / gate.PLAN_PATH, reviewed=report["plan_sha256"],
            report=report, parquet=parquet, parquet_bytes=parquet_bytes, references=references,
            reference_bytes=reference_bytes, rows=registered_rows, source_files=files,
            destination=parent / "local-bundle",
        )

    return make


def materialize(case, **overrides):
    options = {"reviewed_plan_sha256": case.reviewed, "dataset_parquet": case.parquet,
               "reference_root": case.references, "destination": case.destination}
    return case.bundle.materialize_ghcp_input_bundle(case.plan, **{**options, **overrides})


def verify(case, **overrides):
    options = {"reviewed_plan_sha256": case.reviewed, "bundle_root": case.destination}
    return case.bundle.verify_ghcp_input_bundle(case.plan, **{**options, **overrides})


def reservation(case):
    return case.destination.with_name(case.destination.name + case.bundle.RESERVATION_SUFFIX)


def assert_static_refusal(case, action):
    with pytest.raises(case.bundle.GHCPInputBundleRefused) as raised:
        action()
    text = str(raised.value)
    assert text and all(character.islower() or character == "_" for character in text)
    assert PRIVATE not in text and str(case.parent) not in text
    assert raised.value.__context__ is None or raised.value.__suppress_context__ is True


def assert_false_flags(record):
    assert all(record[name] is False for name in FALSE_FLAGS)


def assert_preflight_refused(case):
    report = case.gate.inspect_plan(
        case.plan, local_input_bundle=case.destination, reviewed_plan_sha256=case.reviewed,
    )
    assert report["configuration_valid"] is False
    assert report["launch_blockers"] == EXPECTED_BLOCKERS
    assert report["eligible_facts"] == report["cleared_blockers"] == []
    assert set(report["observed"].values()) == {None}
    assert_false_flags(report)
    assert PRIVATE not in canonical_json(report).decode()
    assert str(case.parent) not in canonical_json(report).decode()


def test_ghcp_vm_input_bundle_real_publication_exact_order_bytes_closure_and_ready_last(inputs, monkeypatch):
    case = inputs()
    ignored = case.references / "private-unselected-input.txt"
    ignored.write_text(PRIVATE, encoding="utf-8")
    written, opened = [], []
    original_write, original_open = case.bundle._write_no_clobber, os.open

    def track_open(path, *args, **kwargs):
        assert path != ignored and str(path) != str(ignored)
        opened.append(path)
        return original_open(path, *args, **kwargs)

    def track_write(path, data):
        if path == case.destination / case.bundle.READY_PATH:
            assert (case.destination / case.bundle.MANIFEST_PATH).is_file()
            assert (case.destination / case.bundle.PARQUET_PATH).read_bytes() == case.parquet_bytes
            assert reservation(case).is_file()
        original_write(path, data)
        written.append(path)

    monkeypatch.setattr(os, "open", track_open)
    monkeypatch.setattr(case.bundle, "_write_no_clobber", track_write)
    result = materialize(case)
    assert verify(case) == result
    assert opened
    assert written[0] == reservation(case)
    assert written[-1] == case.destination / case.bundle.READY_PATH
    assert len(written) == len(set(written))
    expected_files = {
        case.bundle.PARQUET_PATH, case.bundle.INSTRUCTIONS_PATH, case.bundle.MANIFEST_PATH,
        case.bundle.READY_PATH, *case.reference_bytes,
    }
    assert {path.relative_to(case.destination).as_posix()
            for path in case.destination.rglob("*") if path.is_file()} == expected_files
    for path in case.destination.rglob("*"):
        assert not path.is_symlink()
        if path.is_file():
            assert path.stat().st_nlink == 1
    assert case.parquet.read_bytes() == case.parquet_bytes
    for role, data in case.reference_bytes.items():
        assert (case.destination / role).read_bytes() == (case.references / role).read_bytes() == data
    for role, data in case.source_files.items():
        assert (case.source / role).read_bytes() == data
    historical = yaml.safe_load(case.source_files[case.gate.HISTORICAL_PLAN])
    instructions = historical["developer_instructions"].encode()
    assert (case.destination / case.bundle.INSTRUCTIONS_PATH).read_bytes() == instructions
    assert sha256_bytes(instructions) == case.report["developer_instructions_sha256"]
    manifest = json.loads(result.manifest_json)
    assert manifest["condition_id"] == case.gate.CONDITION_ID
    assert manifest["reviewed_plan_sha256"] == case.reviewed
    assert manifest["source_pins"] == case.plan["source_pins"]
    assert manifest["task_ids"] == case.report["task_ids"]
    assert len(manifest["task_ids"]) == len(set(manifest["task_ids"])) == 5
    assert manifest["grading"] == case.plan["grading"]
    for row, task, original in zip(manifest["tasks"], case.report["tasks"], case.rows, strict=True):
        assert row["task_id"] == task["task_id"]
        assert row["prompt_sha256"] == task["prompt_sha256"]
        assert row["source_projection_sha256"] == source_task_projection_sha256(
            **{key: value for key, value in original.items() if key != "deliverable_files"},
        )
        assert row["deliverable_file_extensions"] == task["deliverable_file_extensions"]
        assert row["deliverable_formats"] == task["deliverable_formats"]
        assert row["reference_files"] == [
            {"path": role, **identity(case.reference_bytes[role])} for role in task["reference_file_paths"]
        ]
    public = result.manifest_json + result.canonical_bytes().decode()
    for forbidden in (PRIVATE, str(case.parent), "https://", "hf://", case.rows[0]["prompt"]):
        assert forbidden not in public
    assert manifest["grading"]["reuse_baseline_rerun_identity"] is False
    assert manifest["grading"]["inference_revision"] is None
    assert_false_flags(result.as_dict())
    assert result.as_dict()["evidence_boundary"] == case.bundle.BOUNDARY


def test_ghcp_vm_input_bundle_default_preflight_is_unchanged_and_null(inputs):
    case = inputs()
    absent = case.gate.inspect_plan(case.plan)
    explicit_null = case.gate.inspect_plan(case.plan, local_input_bundle=None, reviewed_plan_sha256=None)
    assert canonical_json(absent) == canonical_json(explicit_null) == canonical_json(case.report)
    assert absent["launch_blockers"] == EXPECTED_BLOCKERS and len(EXPECTED_BLOCKERS) == 15
    assert absent["eligible_facts"] == absent["cleared_blockers"] == []
    assert "local_input_bundle" not in absent
    assert set(absent["observed"].values()) == {None}
    assert_false_flags(absent)


def test_ghcp_vm_input_bundle_verified_transition_satisfies_only_local_materialization(inputs):
    case = inputs()
    before = canonical_json(case.plan)
    result = materialize(case)
    report = case.gate.inspect_plan(
        case.plan, local_input_bundle=case.destination, reviewed_plan_sha256=case.reviewed,
    )
    assert report["configuration_valid"] is True
    assert report["launch_blockers"] == [blocker for blocker in EXPECTED_BLOCKERS if blocker != INPUT_BLOCKER]
    assert report["cleared_blockers"] == [INPUT_BLOCKER]
    assert report["eligible_facts"] == ["local_original_task_input_materialization"]
    assert report["local_input_bundle"] == {"sha256": result.sha256, "evidence_boundary": case.bundle.BOUNDARY}
    assert report["observed"] == case.report["observed"]
    assert_false_flags(report)
    assert canonical_json(case.plan) == before
    assert case.plan["cost"]["approved_maximum_usd"] is None
    assert case.plan["study"]["repeats"] is None
    assert case.plan["grading"]["inference_revision"] is None


@pytest.mark.parametrize("variant", [
    "missing-task", "duplicate-task", "wrong-prompt", "empty-prompt", "invalid-rubric",
    "duplicate-rubric-key", "duplicate-reference", "foreign-reference", "unsafe-reference", "extra-reference",
])
def test_ghcp_vm_input_bundle_real_parquet_selection_and_identity_refusals(inputs, variant):
    case = inputs(variant)
    assert_static_refusal(case, lambda: materialize(case))
    assert not (case.destination / case.bundle.READY_PATH).exists()
    assert_preflight_refused(case)


@pytest.mark.parametrize("which", ["parquet", "reference"])
@pytest.mark.parametrize("fault", ["missing", "bytes", "symlink", "hardlink", "directory", "fifo"])
def test_ghcp_vm_input_bundle_source_bytes_and_single_link_regular_files(inputs, which, fault):
    case = inputs()
    path = case.parquet if which == "parquet" else case.references / next(iter(case.reference_bytes))
    original = path.read_bytes()
    if fault == "bytes":
        path.write_bytes(original + PRIVATE.encode())
    elif fault == "hardlink":
        os.link(path, case.parent / "another-private-link")
    else:
        path.unlink()
        if fault == "symlink":
            target = case.parent / "private-link-target"
            target.write_bytes(original)
            path.symlink_to(target)
        elif fault == "directory":
            path.mkdir()
        elif fault == "fifo":
            os.mkfifo(path)
        else:
            assert fault == "missing"
    assert_static_refusal(case, lambda: materialize(case))
    assert not (case.destination / case.bundle.READY_PATH).exists()


@pytest.mark.parametrize("fault", ["source-parent-link", "source-traversal", "destination-traversal",
                                   "destination-parent-link", "reference-overlap", "parquet-overlap",
                                   "reviewed-source-overlap"])
def test_ghcp_vm_input_bundle_unsafe_paths_and_source_destination_overlap(inputs, fault):
    case = inputs()
    options = {}
    if fault == "source-parent-link":
        link = case.parent / "linked-reference-parent"
        link.symlink_to(case.references, target_is_directory=True)
        options["reference_root"] = link
    elif fault == "source-traversal":
        options["dataset_parquet"] = case.parent / "unvisited" / ".." / case.parquet.name
    elif fault == "destination-traversal":
        options["destination"] = case.parent / ".." / "escaped-destination"
    elif fault == "destination-parent-link":
        link = case.parent / "linked-destination-parent"
        link.symlink_to(case.parent, target_is_directory=True)
        options["destination"] = link / "new-bundle"
    elif fault == "reference-overlap":
        options["destination"] = case.references / "bundle"
    elif fault == "parquet-overlap":
        options["destination"] = case.parquet
    else:
        options["destination"] = case.source / "bundle"
    assert_static_refusal(case, lambda: materialize(case, **options))
    assert not (case.destination / case.bundle.READY_PATH).exists()


@pytest.mark.parametrize("value", [None, True, 1, "", "a" * 63, "A" * 64, "0" * 64])
def test_ghcp_vm_input_bundle_explicit_reviewed_identity_is_required(inputs, value):
    case = inputs()
    assert_static_refusal(case, lambda: materialize(case, reviewed_plan_sha256=value))
    assert not case.destination.exists() and not reservation(case).exists()


@pytest.mark.parametrize("fault", ["empty-directory", "file", "symlink", "reservation", "complete"])
def test_ghcp_vm_input_bundle_no_clobber_and_no_adoption(inputs, fault):
    case = inputs()
    if fault == "empty-directory":
        case.destination.mkdir()
    elif fault == "file":
        case.destination.write_bytes(PRIVATE.encode())
    elif fault == "symlink":
        case.destination.symlink_to(case.references, target_is_directory=True)
    elif fault == "reservation":
        reservation(case).write_bytes(PRIVATE.encode())
    else:
        materialize(case)
    before = {path: path.read_bytes() for path in (reservation(case), case.destination)
              if path.is_file() and not path.is_symlink()}
    assert_static_refusal(case, lambda: materialize(case))
    for path, data in before.items():
        assert path.read_bytes() == data
    if fault == "complete":
        assert verify(case).as_dict()["evidence_boundary"] == case.bundle.BOUNDARY


def test_ghcp_vm_input_bundle_failed_partial_is_retained_and_never_reused(inputs, monkeypatch):
    case = inputs()
    original = case.bundle._write_no_clobber

    def fail(path, data):
        if path == case.destination / case.bundle.PARQUET_PATH:
            raise OSError(PRIVATE + str(case.parent))
        original(path, data)

    with monkeypatch.context() as patch:
        patch.setattr(case.bundle, "_write_no_clobber", fail)
        assert_static_refusal(case, lambda: materialize(case))
    assert reservation(case).is_file() and case.destination.is_dir()
    before = reservation(case).read_bytes()
    assert not (case.destination / case.bundle.READY_PATH).exists()
    assert_static_refusal(case, lambda: materialize(case))
    assert_static_refusal(case, lambda: verify(case))
    assert reservation(case).read_bytes() == before
    assert_preflight_refused(case)


@pytest.mark.parametrize("fault", ["parquet", "reference", "source-pin", "installed-parquet", "manifest", "reservation"])
def test_ghcp_vm_input_bundle_mid_publication_drift_never_writes_ready(inputs, monkeypatch, fault):
    case = inputs()
    original = case.bundle._write_no_clobber
    fired = []

    def drift(path, data):
        original(path, data)
        if path == case.destination / case.bundle.MANIFEST_PATH:
            targets = {
                "parquet": case.parquet,
                "reference": case.references / next(iter(case.reference_bytes)),
                "source-pin": case.source / case.gate.HISTORICAL_PLAN,
                "installed-parquet": case.destination / case.bundle.PARQUET_PATH,
                "manifest": case.destination / case.bundle.MANIFEST_PATH,
                "reservation": reservation(case),
            }
            target = targets[fault]
            target.write_bytes(target.read_bytes() + PRIVATE.encode())
            fired.append(fault)

    monkeypatch.setattr(case.bundle, "_write_no_clobber", drift)
    assert_static_refusal(case, lambda: materialize(case))
    assert fired == [fault]
    assert reservation(case).exists() and case.destination.exists()
    assert not (case.destination / case.bundle.READY_PATH).exists()
    assert_preflight_refused(case)


@pytest.mark.parametrize("fault", [
    "parquet", "reference", "instructions", "missing-ready", "missing-manifest", "missing-reservation",
    "reservation", "extra-file", "extra-directory", "reference-symlink", "reference-hardlink",
    "source-pin", "manifest-task-order", "manifest-foreign-condition", "manifest-private-field", "ready-flag",
])
def test_ghcp_vm_input_bundle_verifier_rereads_bytes_pins_and_exact_members(inputs, fault):
    case = inputs()
    materialize(case)
    reference = case.destination / next(iter(case.reference_bytes))
    if fault in {"parquet", "reference", "instructions", "reservation", "source-pin"}:
        path = {"parquet": case.destination / case.bundle.PARQUET_PATH, "reference": reference,
                "instructions": case.destination / case.bundle.INSTRUCTIONS_PATH,
                "reservation": reservation(case), "source-pin": case.source / case.gate.HISTORICAL_PLAN}[fault]
        path.write_bytes(path.read_bytes() + PRIVATE.encode())
    elif fault.startswith("missing-"):
        path = {"missing-ready": case.destination / case.bundle.READY_PATH,
                "missing-manifest": case.destination / case.bundle.MANIFEST_PATH,
                "missing-reservation": reservation(case)}[fault]
        path.unlink()
    elif fault == "extra-file":
        (case.destination / ".env").write_text(PRIVATE, encoding="utf-8")
    elif fault == "extra-directory":
        (case.destination / "private-extra-directory").mkdir()
    elif fault == "reference-symlink":
        reference.unlink()
        reference.symlink_to(case.references / next(iter(case.reference_bytes)))
    elif fault == "reference-hardlink":
        os.link(reference, case.parent / "another-link")
    else:
        path = case.destination / (case.bundle.READY_PATH if fault == "ready-flag" else case.bundle.MANIFEST_PATH)
        document = json.loads(path.read_bytes())
        if fault == "ready-flag":
            document["launch_allowed"] = True
        elif fault == "manifest-task-order":
            document["task_ids"].reverse()
        elif fault == "manifest-foreign-condition":
            document["condition_id"] = "codex_foundry"
        else:
            document["private_path"] = str(case.parent / PRIVATE)
        path.write_bytes(canonical_json(document))
    assert_static_refusal(case, lambda: verify(case))
    assert_preflight_refused(case)


def test_ghcp_vm_input_bundle_cli_staging_verification_and_blocked_preflight(inputs, capsys):
    case = inputs()
    common = ["--plan", str(case.plan_path), "--reviewed-plan-sha256", case.reviewed]
    assert case.bundle.main([
        *common, "--dataset-parquet", str(case.parquet), "--reference-root", str(case.references),
        "--destination", str(case.destination),
    ]) == 0
    staged = capsys.readouterr()
    assert staged.err == ""
    assert_false_flags(json.loads(staged.out))
    assert case.bundle.main([*common, "--verify-bundle", str(case.destination)]) == 0
    checked = capsys.readouterr()
    assert checked.out == staged.out and checked.err == ""
    assert case.gate.main([*common, "--local-input-bundle", str(case.destination)]) == 2
    preflight = capsys.readouterr()
    report = json.loads(preflight.out)
    assert report["cleared_blockers"] == [INPUT_BLOCKER]
    assert_false_flags(report)
    for output in (staged.out, checked.out, preflight.out):
        for forbidden in (PRIVATE, str(case.parent), "https://", "hf://", "Traceback", "Authorization"):
            assert forbidden not in output


@pytest.mark.parametrize("fault", ["missing-input", "bad-pin", "private-option", "missing-plan", "partial", "bad-json"])
def test_ghcp_vm_input_bundle_cli_refusals_do_not_echo_inputs(inputs, capsys, fault):
    case = inputs()
    arguments = ["--plan", str(case.plan_path), "--reviewed-plan-sha256", case.reviewed]
    if fault == "missing-input":
        arguments += ["--destination", str(case.destination)]
    elif fault == "bad-pin":
        arguments[3] = "sk-" + PRIVATE
        arguments += ["--verify-bundle", str(case.destination)]
    elif fault == "private-option":
        arguments += ["--token", PRIVATE, "--endpoint", "https://private.invalid/" + PRIVATE]
    elif fault == "missing-plan":
        arguments[1] = str(case.parent / PRIVATE)
        arguments += ["--verify-bundle", str(case.destination)]
    elif fault == "partial":
        case.destination.mkdir()
        arguments += ["--verify-bundle", str(case.destination)]
    else:
        case.plan_path.write_bytes(b'{"private": "' + PRIVATE.encode() + b'",')
        arguments += ["--verify-bundle", str(case.destination)]
    assert case.bundle.main(arguments) == 2
    captured = capsys.readouterr()
    document = json.loads(captured.out)
    assert captured.err == ""
    assert document["input_bundle_complete"] is False
    assert_false_flags(document)
    for forbidden in (PRIVATE, str(case.parent), "sk-", "https://", "Traceback", "SyntaxError"):
        assert forbidden not in captured.out


def test_ghcp_vm_input_bundle_preflight_control_cannot_adopt_a_claim_or_unpaired_option(inputs, capsys):
    case = inputs()
    assert_preflight_refused(case)
    for options in (
        {"local_input_bundle": {"input_bundle_complete": True}, "reviewed_plan_sha256": case.reviewed},
        {"reviewed_plan_sha256": case.reviewed},
        {"local_input_bundle": case.destination},
    ):
        report = case.gate.inspect_plan(case.plan, **options)
        assert report["configuration_valid"] is False
        assert report["launch_blockers"] == EXPECTED_BLOCKERS
        assert_false_flags(report)
    for arguments in (
        ["--local-input-bundle", str(case.destination)],
        ["--reviewed-plan-sha256", case.reviewed],
        ["--local-input-bundle", str(case.destination), "--local-input-bundle", PRIVATE],
    ):
        assert case.gate.main(arguments) == 2
        captured = capsys.readouterr()
        assert captured.err == "" and PRIVATE not in captured.out and str(case.parent) not in captured.out
        assert json.loads(captured.out)["launch_blockers"] == EXPECTED_BLOCKERS
