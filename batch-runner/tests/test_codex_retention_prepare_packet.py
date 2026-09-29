"""One offline, opt-in original-byte contract; never fetch private fixtures.

GDPVAL_RETENTION_PREPARED_HANDOFF explicitly names the retained local handoff.
Without it this private-original positive test is SKIPPED, not reported as
verified by a synthetic substitute. No fixture path or payload is committed.
"""

from copy import deepcopy
from dataclasses import replace
import json
import os
from pathlib import Path
import tempfile

import pytest

import codex_retention_diagnostic as registration
import codex_retention_prepare_packet as packet
from core.prepared_fingerprint import prepared_fingerprint
from gpt54_prepared_input_attestation import _identity, _json_object
from gpt54_v2_grading_input import _read_bytes
from step8_grade import compute_grader_source_hash
from .test_codex_budget_pilot import offline  # noqa: F401; real process/network/SDK guards


def test_retention_preparation_packet_is_verified_closed_and_no_launch(tmp_path, monkeypatch, capsys):
    locator = os.environ.get("GDPVAL_RETENTION_PREPARED_HANDOFF")
    if not locator:
        pytest.skip("explicit retained original-input handoff required; no fetch or synthetic pins")
    handoff = _json_object(packet._read(Path(locator), "private_fixture_handoff"))
    assert handoff["prepared_role"] == packet.PREPARED_PATH
    sources = packet.PreparedInputs(
        Path(handoff["destination"]), Path(handoff["original_parquet"]),
        Path(handoff["reference_root"]), Path(handoff["step0_manifest"]),
    )
    calls = []

    def forbidden(*args, **kwargs):
        calls.append(True)
        raise AssertionError("preparation crossed a runtime, model, HF or deadline boundary")

    for name in (
        "core.codex_runner.CodexAgentRunner.__init__",
        "core.codex_task_deadline.CodexTaskDeadlineStore.__init__",
        "core.codex_task_deadline.CodexTaskDeadline.admit_attempt",
        "core.executor.TaskExecutor.__init__",
        "prepare_dataset.snapshot_download", "prepare_dataset.load_dataset",
        "step8_grade.RubricLoader.__init__",
    ):
        monkeypatch.setattr(name, forbidden)
    plan = registration.compile_plan()
    original_plan = deepcopy(plan)
    identity = packet.source_identity()
    cell_id = "0818571f-5ff7-4d39-9d2c-ced5ae44299e_retention_bundle_v1_fresh_r1"
    cell = next(row for row in plan["cells"] if row["cell_id"] == cell_id)
    original_paths = [sources.dataset_parquet, sources.step0_manifest,
                      sources.prepared_root / packet.PREPARED_PATH, sources.prepared_root / packet.CONFIG_PATH]
    original_paths += [sources.reference_root / name for name in
                      registration.load_plan(registration.ROOT / registration.ORIGINAL_PROFILE)["shared"]["dataset"]["input_file_versions"]
                      if name.startswith("reference_files/")]
    original_bytes = {path: packet._read(path, "private_fixture_original") for path in original_paths}

    packet.OUTPUT_SCOPE.mkdir(mode=0o700, exist_ok=True)
    packet._path(packet.OUTPUT_SCOPE)
    # Retain this precisely owned private test tree for evidence. It is inside
    # the existing ignored workspace and never adopts an old output directory.
    owned = Path(tempfile.mkdtemp(prefix="retention-packet-test-", dir=packet.OUTPUT_SCOPE))
    output = owned / "valid"
    options = dict(cell_id=cell_id, sources=sources, expected_preparer_sha256=identity["sha256"], plan=plan)
    try:
        result = packet.prepare_packet(output=output, **options)
    except Exception as error:
        # A failed positive prints only the closed stage/type, not a private
        # pathname or an exception body from the original-byte parser.
        reason = (str(error) if isinstance(error, (packet.RetentionPreparationRefused, registration.RetentionRegistrationRefused))
                  else type(error).__name__)
        pytest.fail("original-byte preparation refused: " + reason, pytrace=False)
    assert packet.verify_packet(output=output, **options) == result
    assert plan == original_plan
    assert result["plan_sha256"] == registration.seal(plan)
    assert result["compiler_source"] == plan["source_pins"]["compiler"]
    assert result["preparer_source"] == identity and identity["reviewed"] is False
    assert result["launch_authorized"] is result["inference_slot_reserved"] is result["deadline_started"] is False
    assert result["runtime_inputs_staged"] is False and result["commands"] == []
    assert set(plan["launch_blockers"]).issubset(result["launch_blockers"])
    assert result["input_verification"]["original_input_roles_sha256"] == (
        "40d815317e1c0b00deccc30426dde9eb75a8e83a5c40acd449d8616e21566c38"
    )
    assert len(result["input_verification"]["task_ids"]) == 5
    prepared = _json_object(original_bytes[sources.prepared_root / packet.PREPARED_PATH])
    selected = next(row for row in prepared["tasks"] if row["task_id"] == cell["task_id"])
    selected_bytes_match = _json_object(_read_bytes(output / packet.TASK)) == selected
    assert selected_bytes_match, "selected_task_row_changed"
    assert selected["reference_file_records"] and "rubric_json" not in selected
    inference = _json_object(_read_bytes(output / packet.INFERENCE))
    grader = _json_object(_read_bytes(output / packet.GRADER))
    assert inference == cell["config"]
    assert inference["data"]["filter"]["task_ids"] == [cell["task_id"]]
    assert inference["execution"]["codex"]["task_deadline"] == cell["control"]
    assert grader == plan["grading"]["generated_config"]
    assert result["grading"]["materialized_grader_source_sha256"] == compute_grader_source_hash(
        output / packet.GRADER, grader, batch_root=packet.ROOT / "batch-runner",
    )
    assert result["grading"]["materialized_grader_source_sha256"] != plan["grading"]["template_source_sha256"]
    assert result["grading"]["grades_per_produced_result"] == 1
    assert result["grading"]["no_result_grade"] is None and result["grading"]["grading_done"] is False
    assert sorted(path.name for path in output.iterdir()) == sorted(packet.MEMBERS)
    for name, expected in result["files"].items():
        assert _identity(_read_bytes(output / name)) == expected
        assert (output / name).stat().st_nlink == 1

    def refused(label, expected, **changed):
        destination = owned / label
        with pytest.raises(packet.RetentionPreparationRefused, match=expected):
            packet.prepare_packet(output=destination, **{**options, **changed})
        assert not destination.exists()

    refused("wrong-cell", "^exact_registered_cell_required$", cell_id="unregistered")
    refused("wrong-source", "^preparer_source_mismatch$", expected_preparer_sha256="0" * 64)
    wrong_plan = deepcopy(plan)
    wrong_plan["cells"][4]["config_sha256"] = "0" * 64
    with pytest.raises(registration.RetentionRegistrationRefused, match="^compiled_plan_mismatch$"):
        packet.prepare_packet(output=owned / "wrong-plan", **{**options, "plan": wrong_plan})
    assert not (owned / "wrong-plan").exists()
    wrong_plan = deepcopy(plan)
    wrong_plan["source_pins"]["runtime"]["batch-runner/core/codex_runner.py"] = "0" * 64
    with pytest.raises(registration.RetentionRegistrationRefused, match="^compiled_plan_mismatch$"):
        packet.prepare_packet(output=owned / "wrong-runtime", **{**options, "plan": wrong_plan})
    assert not (owned / "wrong-runtime").exists()

    bad_parquet = owned / "altered-parquet"
    bad_parquet.write_bytes(original_bytes[sources.dataset_parquet] + b"altered")
    refused("bad-parquet", "^original_parquet_bytes_refused:", sources=replace(sources, dataset_parquet=bad_parquet))
    bad_manifest = owned / "altered-schema4.json"
    bad_manifest.write_bytes(original_bytes[sources.step0_manifest] + b"\n")
    refused("bad-schema4", "^original_schema4_refused:", sources=replace(sources, step0_manifest=bad_manifest))
    bad_references = owned / "altered-references"
    for path in original_paths:
        if path.is_relative_to(sources.reference_root):
            target = bad_references / path.relative_to(sources.reference_root)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(original_bytes[path] + (b"altered" if path.suffix == ".pdf" else b""))
    refused("bad-references", "^original_reference_bytes_refused:", sources=replace(sources, reference_root=bad_references))
    bad_prepared = owned / "altered-prepared"
    (bad_prepared / packet.PREPARED_PATH).parent.mkdir(parents=True)
    (bad_prepared / packet.CONFIG_PATH).write_bytes(original_bytes[sources.prepared_root / packet.CONFIG_PATH])
    altered = deepcopy(prepared)
    altered["tasks"][4]["instruction"] += " altered"
    altered["prepared_fingerprint"] = prepared_fingerprint(altered)
    (bad_prepared / packet.PREPARED_PATH).write_text(packet._canonical_json(altered))
    refused("bad-prepared", "^original_prepared_projection_refused:", sources=replace(sources, prepared_root=bad_prepared))

    with pytest.raises(packet.RetentionPreparationRefused, match="^output_collision_or_missing_parent$"):
        packet.prepare_packet(output=output, **options)
    link = owned / "linked-output"
    link.symlink_to(output, target_is_directory=True)
    with pytest.raises(packet.RetentionPreparationRefused, match="^unsafe_path:"):
        packet.prepare_packet(output=link, **options)
    with pytest.raises(packet.RetentionPreparationRefused, match="^parent_traversal_refused$"):
        packet.prepare_packet(output=owned / ".." / "escaped", **options)
    with pytest.raises(packet.RetentionPreparationRefused, match="^output_outside_source_workspace$"):
        packet.prepare_packet(output=tmp_path / "outside-source", **options)
    with pytest.raises(packet.RetentionPreparationRefused, match="^output_input_overlap$"):
        packet.prepare_packet(output=bad_prepared / "overlap", **{**options, "sources": replace(sources, prepared_root=bad_prepared)})

    held = {name: _read_bytes(output / name) for name in packet.MEMBERS}
    altered = deepcopy(inference)
    altered["execution"]["codex"]["task_deadline"]["retention_bundle"] = "keep"
    (output / packet.INFERENCE).write_text(packet._canonical_json(altered))
    forged = deepcopy(result)
    forged["files"][packet.INFERENCE] = _identity(_read_bytes(output / packet.INFERENCE))
    (output / packet.PACKET).write_text(packet._canonical_json(forged))
    with pytest.raises(packet.RetentionPreparationRefused, match="^emitted_config_or_task_bytes_mismatch$"):
        packet.verify_packet(output=output, **options)
    (output / packet.INFERENCE).write_bytes(held[packet.INFERENCE])
    forged = deepcopy(result)
    forged["preparer_source"]["sha256"] = "0" * 64
    (output / packet.PACKET).write_text(packet._canonical_json(forged))
    with pytest.raises(packet.RetentionPreparationRefused, match="^packet_readback_mismatch$"):
        packet.verify_packet(output=output, **options)
    (output / packet.PACKET).write_bytes(held[packet.PACKET])
    (output / packet.GRADER).unlink()
    (output / packet.GRADER).symlink_to(output / packet.INFERENCE)
    with pytest.raises(packet.RetentionPreparationRefused, match="^emitted_member_bytes_refused:"):
        packet.verify_packet(output=output, **options)
    (output / packet.GRADER).unlink()
    (output / packet.GRADER).write_bytes(held[packet.GRADER])

    write = packet._write_no_clobber
    with monkeypatch.context() as interruption:
        def fail_second(path, data):
            if path.name == packet.GRADER:
                raise OSError("synthetic_owned_write_interruption")
            return write(path, data)
        interruption.setattr(packet, "_write_no_clobber", fail_second)
        with pytest.raises(OSError, match="^synthetic_owned_write_interruption$"):
            packet.prepare_packet(output=owned / "partial", **options)
    assert not (owned / "partial" / packet.PACKET).exists()
    with pytest.raises(packet.RetentionPreparationRefused, match="^output_collision_or_missing_parent$"):
        packet.prepare_packet(output=owned / "partial", **options)
    assert packet.verify_packet(output=output, **options) == result
    assert all(packet._read(path, "private_fixture_original") == data for path, data in original_bytes.items()), "original_input_bytes_changed"
    assert calls == []

    # Exercise the actual CLI readback, without publishing the private locator
    # or selected task content. No dynamic namespace or execution flag exists.
    assert packet.main([
        "--verify", "--cell-id", cell_id, "--prepared-root", str(sources.prepared_root),
        "--dataset-parquet", str(sources.dataset_parquet), "--reference-root", str(sources.reference_root),
        "--step0-manifest", str(sources.step0_manifest), "--output", str(output),
        "--expected-preparer-sha256", identity["sha256"],
    ]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["prepared"] is True and summary["launch_authorized"] is False
    assert summary["packet_sha256"] == registration.seal(result) and summary["commands"] == []
    public_summary_only = str(output) not in json.dumps(summary) and selected["instruction"] not in json.dumps(summary)
    assert public_summary_only, "CLI_exposed_private_locator_or_task_content"
    # The optional receipt is session-private, not a repository record. Keep
    # paths there so another authorized task need not rediscover this packet.
    receipt = os.environ.get("GDPVAL_RETENTION_TEST_RECEIPT")
    if receipt:
        with Path(receipt).open("x", encoding="utf-8") as stream:
            json.dump({"output": str(output), "owned_test_root": str(owned), "summary": summary,
                       "preparer_source": identity, "input_roles": result["input_verification"]["original_files"]}, stream)
    print(json.dumps({"evidence": "offline_private_original_packet_test", **summary}, sort_keys=True))
