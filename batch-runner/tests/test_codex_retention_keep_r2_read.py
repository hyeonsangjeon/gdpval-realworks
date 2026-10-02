"""Fixed keep/r2 reads: real validators, synthetic records, no live effects."""

import builtins
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
import json
from pathlib import Path

import pytest

import codex_retention_fresh_r1_result_intake as reader
import codex_retention_task4_fresh_r2 as fresh_r2
import codex_retention_task4_keep_r2 as keep
from core.codex_task_deadline import CodexTaskDeadline, CodexTaskDeadlineStore
from core.cost_receipts import CostReceipt
from core.reference_integrity import ReferenceIntegrityError
from .test_codex_budget_pilot_retention import TOKEN, offline  # noqa: F401
from .test_codex_retention_fresh_r1_result_intake import FreshResultHF
from .test_codex_retention_fresh_r1_terminal_observation import TerminalHF
from .test_codex_retention_result_intake import CLAIM_HEAD, OUTPUT_HEAD, TERMINAL_HEAD, FILE, PRIVATE

ci, retained, output, owned, intake = reader.ci, reader.retained, reader.output, reader.owned, reader.intake


def test_keep_r2_reads_only_its_fixed_result_or_terminal(tmp_path, monkeypatch, capsys):
    effects, transports = [], []

    def forbidden(*args, **kwargs):
        effects.append(True)
        raise AssertionError("keep/r2 reader crossed a live, authority, payload or remote-write boundary")

    for owner, name in (
        (ci, "execute"), (ci, "verify_approval"), (ci, "verify_job_origin"), (ci, "verify_terminal"),
        (reader.fresh, "execute"), (reader.fresh, "_predecessor"), (reader.fresh, "verify_terminal"),
        (reader.fresh._FreshAdmission, "__init__"), (fresh_r2, "execute"), (fresh_r2, "verify_terminal"),
        (fresh_r2._FreshR2Admission, "__init__"), (keep, "execute"), (keep, "verify_terminal"),
        (keep._KeepR2Admission, "__init__"), (ci._Admission, "__init__"),
        (ci.LocalTransport, "github_job_token"), (ci.LocalTransport, "authority_opener"),
        (ci.LocalTransport, "github"), (ci.LocalTransport, "azure"), (owned.LocalTransport, "clock"),
        (owned.LocalTransport, "child"), (owned.LocalTransport, "process"),
        (ci.preparation, "prepare_packet"), (ci.preparation, "verify_packet"), (ci.historical, "observe"),
        (ci.controller, "execute_first_cell"), (ci.controller, "stage_runtime"), (ci.controller, "_deadline"),
        (CodexTaskDeadlineStore, "__init__"), (CodexTaskDeadline, "admit_attempt"),
        (intake.retained_reader, "prepare"), (intake.retained_reader, "main"), (output, "_hf_client"),
    ):
        monkeypatch.setattr(owner, name, forbidden)
    for key in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"):
        monkeypatch.delenv(key, raising=False)
    binding = reader.KEEP_R2
    assert binding.expectation == ci.TerminalExpectation(
        "8a06cc7df34cbf10896b635f6c8d9ad4e91313d3c685511f8fc5c159cb6ddec1",
        "b8351e561acb9675a4993419e819c12787b5b305",
        "3baa0009-5a60-4ae8-ae99-4955cb328ff3_retention_bundle_v1_keep_r2")
    assert (binding.ordinal, binding.repetition, binding.retention_bundle, binding.run_id,
            binding.execution_job_id) == (3, 2, "keep", "36947454688", 110660390316)
    assert binding.original_input_bundle_sha256 == "757603585405da5d7f6817a6a0a23bd530d4b5e4e38b2fd4dc6f318053d240e3"
    assert binding.materialized_grader_source_sha256 == "997c30a6b6b8ed8f53d75a6db180dca549df6d0ae31e549934b75eb27d1b0fc1"
    assert keep.PREDECESSOR["terminal_commit"] == "1d5133590911f3704fc2a65279d4b64bee77c1d6"
    source = reader.reader_identity(binding=binding)
    assert source["producer_keep_r2_sha256"] == "12106b5423e25ffefa1b04023e2e98742861762762966a04bf17fe3da1851450"
    assert source["producer_r2_sha256"] == "8b387ec5d172f74c4e6d2e1b93973c674e973f3cbba47b640184c126312ab00f"
    assert reader.reader_identity(binding=reader.FRESH_R2) == {
        key: value for key, value in source.items() if key != "producer_keep_r2_sha256"}
    assert reader.reader_identity() == {key: value for key, value in source.items()
        if key not in {"producer_keep_r2_sha256", "producer_r2_sha256"}}
    assert {key: source[key] for key in reader.FROZEN} == {key: pair[1] for key, pair in reader.FROZEN.items()}
    assert reader.FRESH_R1.expectation is reader.EXPECTATION
    assert reader.FRESH_R1.retention_bundle == reader.FRESH_R2.retention_bundle == "fresh"
    plan = intake.registration.compile_plan()

    def make(*, terminal=False, **options):
        api = (TerminalHF if terminal else FreshResultHF)(plan, binding=binding, **options)
        transports.append(api)
        return api

    def read(api, name, *, terminal=False, **changes):
        options = dict(expectation=binding.expectation, binding=binding, destination=tmp_path / name,
            expected_reader_sha256=source["module_sha256"], terminal_revision=TERMINAL_HEAD, _test_api=api)
        return (reader.observe_terminal if terminal else reader.read_result)(**{**options, **changes})

    def refuse(api, name, reason, *, terminal=False, **changes):
        with pytest.raises(output.OutputPublicationRefused) as refused:
            read(api, name, terminal=terminal, **changes)
        assert refused.value.args == (reason,), name
        assert not (tmp_path / name / (binding.terminal_marker if terminal else binding.result_marker)).exists()

    def argv(name, terminal=False):
        return ["--observe-terminal" if terminal else "--read", "--discover-terminal",
            "--expected-producer-source", binding.expectation.source_sha,
            "--expected-request-sha256", binding.expectation.request_sha256,
            "--cell-id", binding.expectation.cell_id, "--expected-reader-sha256", source["module_sha256"],
            "--output", str(tmp_path / name)]

    def captured(api):
        text = capsys.readouterr()
        assert text.err == ""
        for private in (str(tmp_path), api.repo, TOKEN, PRIVATE.decode().strip(), FILE, "SECRET-LIKE-ERROR"):
            assert private not in text.out
        return json.loads(text.out)

    api = make()
    with monkeypatch.context() as early:
        early.setattr(retained, "_session", forbidden)
        assert reader.main([], _test_api=api) == 0
        inert = captured(api)
        assert inert["cell_id"] == reader.fresh.CELL_ID and inert["read_attempted"] is False
        assert reader.main(["--read", "--observe-terminal"], _test_api=api) == 2
        assert captured(api)["reason"] == "invalid_arguments"
        for index, (changes, reason) in enumerate((
            ({"binding": object()}, "fixed_fresh_read_binding_required"),
            ({"binding": replace(binding)}, "fixed_fresh_read_binding_required"),
            ({"binding": replace(binding, retention_bundle="fresh")}, "fixed_fresh_read_binding_required"),
            ({"expectation": object()}, "fresh_result_expectation_required"),
            ({"expectation": replace(binding.expectation, source_sha=reader.PRODUCER_SOURCE)}, "fresh_result_expected_producer_mismatch"),
            ({"expectation": replace(binding.expectation, request_sha256=reader.REQUEST_SHA256)}, "fresh_result_expected_request_mismatch"),
            ({"expectation": replace(binding.expectation, cell_id="unknown")}, "fresh_result_expected_cell_mismatch"),
            ({"expected_reader_sha256": "cd88a768e573d57c82d8f14bcb266ae455187933fb8a5b70da0fadafe17bea46"}, "fresh_result_reader_bytes_mismatch"),
            ({"discover_terminal": 1, "terminal_revision": None}, "one_terminal_revision_or_discovery_required"),
        )):
            for terminal in (False, True):
                refuse(api, "early-" + str(index) + str(terminal), reason, terminal=terminal, **changes)
        # Adversarial registration input, not a successful validator substitute.
        # The real compiled plan is copied; the reader must reject the wrong control.
        wrong_treatment = deepcopy(plan)
        wrong_treatment["cells"][3]["control"]["retention_bundle"] = "fresh"
        early.setattr(intake.registration, "compile_plan", lambda: wrong_treatment)
        for terminal in (False, True):
            refuse(api, "wrong-treatment-" + str(terminal), "fresh_result_registered_cell_mismatch", terminal=terminal)
    assert api.calls == [] and effects == []

    # Corrupt actual bytes returned by the real file reader, never expected pins.
    # Both lazy dependencies must fail before import or any credential/session.
    real_bytes, real_import = output._bytes, builtins.__import__
    for changed_path, _ in (reader.R2_PRODUCER_PIN, reader.KEEP_R2_PRODUCER_PIN):
        def altered_source(path, *args, **kwargs):
            data = real_bytes(path, *args, **kwargs)
            return data + b"\n" if Path(path) == changed_path else data

        def no_producer_import(name, *args, **kwargs):
            if name in {"codex_retention_task4_fresh_r2", "codex_retention_task4_keep_r2"}:
                return forbidden()
            return real_import(name, *args, **kwargs)

        with monkeypatch.context() as altered:
            altered.setattr(output, "_bytes", altered_source)
            altered.setattr(builtins, "__import__", no_producer_import)
            altered.setattr(retained, "_session", forbidden)
            for terminal in (False, True):
                refuse(api, "changed-" + changed_path.stem + str(terminal), "fresh_result_reader_bytes_mismatch", terminal=terminal)
            with pytest.raises(output.OutputPublicationRefused) as refused:
                reader._producer(binding)
            assert refused.value.args == ("fresh_result_reader_bytes_mismatch",)
    assert api.calls == [] and effects == []
    monkeypatch.setenv("HF_TOKEN", TOKEN)  # Synthetic transport token only.
    receipt = ci.project_cost_receipt(CostReceipt(status="partial", model_calls=2,
        known_cost_usd=Decimal("0.01"), model_cost_usd=Decimal("0.01"),
        usage={"input_tokens": 12, "cached_input_tokens": 8, "output_tokens": 3, "reasoning_tokens": 2},
        missing_reasons=("synthetic_missing_cost",)).as_dict())
    success_api = make(receipt=receipt, with_ledger=True)
    code = reader.main(argv("result"), _test_api=success_api)
    success = captured(success_api)
    assert code == 0, {key: success.get(key) for key in ("reason", "intake_verified")}
    assert success["intake_verified"] is True and success["status"] == "succeeded"
    assert success["format"] == "retention-task4-keep-r2-result-intake-v1" and "terminal_verified" not in success
    assert success["result"]["registered_config_sha256"] == plan["cells"][3]["config_sha256"]
    assert output._hash(success["result"]["result_fingerprint"])
    assert success["receipt"] == receipt and success["accounting"] == "partial"
    marker = tmp_path / "result" / binding.result_marker
    assert success["intake_sha256"] == owned._identity(marker.read_bytes())["sha256"]
    assert "intake_verified" not in json.loads(marker.read_bytes())
    assert (tmp_path / "result" / FILE).read_bytes() == PRIVATE
    assert (tmp_path / "result").stat().st_mode & 0o777 == 0o700
    assert marker.stat().st_mode & 0o777 == 0o600
    assert {name for _, name in success_api.downloads} == {keep.CLAIM, keep.TERMINAL,
        *(keep.OUTPUT + "/" + name for name in (*success_api.files, output.MANIFEST))}
    controls = {keep.TERMINAL, keep.CLAIM, keep.OUTPUT + "/" + output.MANIFEST}
    evidence = [(success_api, success)]
    for index, (status, declared, cost, exit_code) in enumerate((
        ("failed", "none", None, 1), ("stopped", "none", receipt, None),
        ("failed", "partial", receipt, 1), ("stopped", "result", None, -15),
    )):
        terminal_api = make(terminal=True, status=status, declared=declared, receipt=cost, exit_code=exit_code)
        refuse(terminal_api, "not-success-" + str(index), "fresh_result_success_required")
        with monkeypatch.context() as control_only:
            for owner, name in ((intake, "_payload"), (intake, "validate_inference_result_fingerprint"),
                                (intake.retained_reader, "_fetch"), (output, "_ledger")):
                control_only.setattr(owner, name, forbidden)
            code = reader.main(argv("terminal-" + str(index), True), _test_api=terminal_api)
        record = captured(terminal_api)
        assert code == 0, {key: record.get(key) for key in ("reason", "outcome")}
        assert record["outcome"] == "terminal_verified" and record["terminal_verified"] is True
        assert record["format"] == "retention-task4-keep-r2-terminal-observation-v1"
        assert record["status"] == status and record["exit_code"] == exit_code
        assert record["declared_payload_roles"] == {"inference_result": int(declared != "none"),
            "ledger": int(declared == "partial"), "deliverables": int(declared == "partial")}
        assert record["declared_output_object_count"] == len(terminal_api.files) + 1
        assert record["receipt"] == cost and record["missing"] == terminal_api.summary["missing"]
        assert record["unavailable"] == {field: {"status": "unavailable", "value": None,
            "reason": "not_recorded_in_terminal_controls"} for field in ("detailed_failure", "budget", "recovery_exposure")}
        assert record["payload_bodies_verified"] is record["grading_input_ready"] is False
        assert not {"intake_verified", "judge_ready", "result", "files"} & set(record)
        assert {name for _, name in terminal_api.downloads} == controls
        saved = tmp_path / ("terminal-" + str(index)) / binding.terminal_marker
        assert record["observation_sha256"] == owned._identity(saved.read_bytes())["sha256"]
        assert saved.stat().st_mode & 0o777 == 0o600
        evidence.append((terminal_api, record))
    for transport, record in evidence:
        assert record["ordinal"] == 3 and record["cell_id"] == binding.expectation.cell_id
        assert record["producer_source_sha"] == binding.expectation.source_sha
        assert record["request_sha256"] == binding.expectation.request_sha256
        assert record["expected_execution_job_id"] == record["recorded_provider_job_id"] == 110660390316
        assert record["recorded_provider_run_id"] == record["expected_provider"]["run_id"] == "36947454688"
        assert record["expected_provider"]["attempt"] == 1 and record["expected_provider"]["workflow_id"] == 370228282
        assert record["terminal_commit"] == TERMINAL_HEAD != transport.head
        assert record["terminal_identity"] == owned._identity(transport.trees[TERMINAL_HEAD][keep.TERMINAL])
        assert record["claim_commit"] == CLAIM_HEAD and record["claim_identity"] == owned._identity(transport.trees[CLAIM_HEAD][keep.CLAIM])
        assert record["output_commit"] == OUTPUT_HEAD
        assert record["output_manifest_identity"] == owned._identity(transport.trees[OUTPUT_HEAD][keep.OUTPUT + "/" + output.MANIFEST])
        assert record["output_objects_sha256"] == owned._digest(transport.terminal["output_objects"])
        assert record["predecessor"] == keep.PREDECESSOR and record["reader"] == source
        assert record["supplied_request_binding"] == {"original_input_bundle_sha256": binding.original_input_bundle_sha256,
            "materialized_grader_source_sha256": binding.materialized_grader_source_sha256}
        assert record["proof"] == "verified_publication_derived_not_independent_provider_authentication"
        assert record["writer_acknowledgment"] == "not_established" and record["recorded_publication_acknowledged"] is True
        assert record["cleanup_confirmed"] is True
        for flag in ("fresh_origin_authentication", "prepared_input_independently_verified", "git_parent_cas_independently_verified",
                     "launch_authorized", "admission_attempted", "replay_authorized", "grading_launched", "invoice_complete"):
            assert record[flag] is False
        assert record["grade"] is record["http_request_count"] is None and record["commands"] == []
        assert [(rev, names) for rev, names in transport.path_reads if rev == retained.BRANCH] == [
            (retained.BRANCH, (keep.TERMINAL,))]

    # Exact authority checks in BOTH modes, including bool/int coercion refusals.
    for terminal in (False, True):
        for job in (reader.FRESH_R2.execution_job_id, True, float(binding.execution_job_id)):
            bad = make(terminal=terminal)
            for authority in (bad.claim["authority"], bad.terminal["authority"]):
                authority["provider_job_id"] = job
            bad.seed()
            reason = "fresh_terminal_execution_job_mismatch" if terminal else "fresh_result_execution_job_mismatch"
            refuse(bad, "job-" + str(terminal) + str(job), reason if type(job) is int else
                   "fresh_result_authority_binding_mismatch", terminal=terminal)
        for field, value, reason in (
            ("source_sha", reader.PRODUCER_SOURCE, "fresh_result_completion_mismatch"),
            ("cell_id", reader.FRESH_R2.expectation.cell_id, "fresh_result_completion_mismatch"),
            ("cleanup_confirmed", 1, "fresh_result_completion_mismatch"),
        ):
            bad = make(terminal=terminal)
            bad.summary[field] = value
            bad.seed()
            refuse(bad, field + str(terminal), reason, terminal=terminal)
        for change, reason in (("request", "fresh_result_terminal_binding_mismatch"),
                               ("run", "fresh_result_authority_binding_mismatch"),
                               ("predecessor", "fresh_result_predecessor_mismatch")):
            bad = make(terminal=terminal)
            if change == "request":
                bad.terminal["request_sha256"] = reader.FRESH_R2.expectation.request_sha256
            elif change == "run":
                for authority in (bad.claim["authority"], bad.terminal["authority"]):
                    authority["provider_run_id"] = reader.FRESH_R2.run_id
            else:
                bad.claim["predecessor"] = deepcopy(fresh_r2.PREDECESSOR)
                bad.claim["expected_parent"] = fresh_r2.PREDECESSOR["terminal_commit"]
            bad.seed()
            refuse(bad, change + str(terminal), reason, terminal=terminal)

    for change, reason in (
        ("claim-type", "fresh_result_terminal_claim_mismatch"), ("predecessor-type", "fresh_result_predecessor_mismatch"),
        ("grade", "fresh_result_completion_mismatch"), ("grading", "fresh_result_completion_mismatch"),
        ("success", "fresh_terminal_unsuccessful_required"), ("running", "fresh_terminal_unsuccessful_required"),
        ("exit-type", "fresh_terminal_unsuccessful_required"), ("missing", "fresh_result_missing_accounting_mismatch"),
        ("receipt-type", "fresh_result_accounting_mismatch"), ("private", "retention_result_private_state_refused"),
        ("corrupt", "retention_control_blob_mismatch"), ("claim-hash", "payload_identity_mismatch"),
        ("extra-object", "fresh_result_output_objects_mismatch"), ("object-history", "remote_output_history_mismatch"),
        ("claim-history", "retention_control_history_mismatch"), ("terminal-history", "retention_control_history_mismatch"),
        ("object-bytes", "remote_output_blob_mismatch"), ("noncanonical", "noncanonical_retention_record"),
        ("control-bound", "retention_control_file_refused"), ("missing-claim", "terminal_or_claim_missing"),
        ("missing-manifest", "terminal_or_claim_missing"), ("missing-object", "remote_output_objects_missing"),
    ):
        bad = make(terminal=True)
        if change == "claim-type":
            bad.claim["authority"]["provider_job_id"] = float(binding.execution_job_id)
        elif change == "predecessor-type":
            bad.claim["predecessor"]["terminal_identity"]["size"] = 4200.0
        elif change in {"grade", "grading", "success", "running", "exit-type", "missing"}:
            key, value = {"grade": ("grade", 0), "grading": ("grading_launched", 0), "success": ("status", "succeeded"),
                "running": ("status", "running"), "exit-type": ("exit_code", True), "missing": ("missing", [])}[change]
            bad.summary[key] = value
        elif change == "receipt-type":
            bad.summary.update(receipt=deepcopy(receipt), accounting="partial")
            bad.summary["receipt"]["known_cost_usd"] = 1
        elif change == "private":
            bad.files[FILE.rsplit("/", 1)[0] + "/HOME/auth.json"] = PRIVATE
        bad.seed()
        if change == "corrupt":
            bad.corrupt = keep.TERMINAL
        elif change == "claim-hash":
            bad.terminal["claim_identity"]["sha256"] = "0" * 64
        elif change == "extra-object":
            bad.terminal["output_objects"].append(deepcopy(bad.terminal["output_objects"][0]))
        elif change == "object-history":
            bad.writers[TERMINAL_HEAD][keep.OUTPUT + "/" + FILE] = TERMINAL_HEAD
        elif change == "claim-history":
            bad.writers[CLAIM_HEAD][keep.CLAIM] = TERMINAL_HEAD
        elif change == "terminal-history":
            bad.writers[TERMINAL_HEAD][keep.TERMINAL] = OUTPUT_HEAD
        elif change == "object-bytes":
            bad.trees[TERMINAL_HEAD][keep.OUTPUT + "/" + FILE] = b"X" * len(PRIVATE)
        elif change in {"missing-claim", "missing-manifest", "missing-object"}:
            bad.omit_metadata = {"missing-claim": (CLAIM_HEAD, keep.CLAIM),
                "missing-manifest": (OUTPUT_HEAD, keep.OUTPUT + "/" + output.MANIFEST),
                "missing-object": (TERMINAL_HEAD, keep.OUTPUT + "/" + FILE)}[change]
        bad.trees[TERMINAL_HEAD][keep.TERMINAL] = retained._encoded(bad.terminal)
        if change == "noncanonical":
            bad.trees[TERMINAL_HEAD][keep.TERMINAL] = json.dumps(bad.terminal, indent=2).encode()
        elif change == "control-bound":
            bad.trees[TERMINAL_HEAD][keep.TERMINAL] = b"X" * (output.MAX_MANIFEST_BYTES + 1)
        refuse(bad, "control-" + change, reason, terminal=True)
        assert {name for _, name in bad.downloads} <= controls

    for terminal in (False, True):
        for state in ("missing", "ambiguous"):
            absent = make(terminal=True)
            if state == "missing":
                absent.omit_metadata = (retained.BRANCH, keep.TERMINAL)
            else:
                paths_info = absent.get_paths_info

                def ambiguous_paths(**kwargs):
                    found = paths_info(**kwargs)
                    return found * 2 if kwargs["revision"] == retained.BRANCH else found

                monkeypatch.setattr(absent, "get_paths_info", ambiguous_paths)
            assert reader.main(argv("not-ready-" + str(terminal) + state, terminal), _test_api=absent) == 2
            assert captured(absent)["reason"] == "fresh_result_terminal_not_ready"
            assert len(absent.path_reads) == 1 and absent.downloads == []
        for change, reason in (("duplicate", "fresh_result_output_bounds_exceeded"),
            ("total", "fresh_result_output_bounds_exceeded"), ("size-type", "fresh_result_output_identity_refused"),
            ("record", "retention_result_record_bounds_exceeded")):
            summary = deepcopy(terminal_api.summary if terminal else success_api.summary)
            if change == "duplicate":
                summary["files"].append(deepcopy(summary["files"][0]))
            elif change == "total":
                summary["files"] = [{"path": f"deliverable_files/{intake.registration.TASK4}/{index}.txt",
                    "size": output.MAX_FILE_BYTES, "sha256": "0" * 64} for index in range(3)]
            elif change == "size-type":
                summary["files"][0]["size"] = True
            else:
                next(item for item in summary["files"] if item["path"] == intake.RESULT)["size"] = output.MAX_RECORD_BYTES + 1
            with pytest.raises(output.OutputPublicationRefused) as refused:
                (reader._terminal_summary if terminal else reader._summary)(summary, binding=binding)
            assert refused.value.args == (reason,)
        for path in ("unrelated.json", "../escape", FILE.replace(intake.registration.TASK4, "foreign-task")):
            summary = deepcopy(terminal_api.summary if terminal else success_api.summary)
            summary["files"] = sorted([*summary["files"], {"path": path, "size": 1, "sha256": "0" * 64}], key=lambda item: item["path"])
            with pytest.raises(ValueError) as refused:
                (reader._terminal_summary if terminal else reader._summary)(summary, binding=binding)
            assert type(refused.value) is ValueError  # Raw path-bearing errors never become public receipts.
        arbitrary = make(terminal=terminal)
        arbitrary.read_error = ValueError("SECRET-LIKE-ERROR")
        assert reader.main(argv("redacted-" + str(terminal), terminal), _test_api=arbitrary) == 2
        assert captured(arbitrary)["reason"] == ("fresh_terminal_observation_refused" if terminal else "fresh_result_intake_refused")

    for change in ("runtime", "payload-corruption", "fingerprint"):
        bad = make()
        if change == "runtime":
            bad.payload["run_id"] = "wrong-run"
            bad.bind_payload()
        elif change == "payload-corruption":
            bad.corrupt = keep.OUTPUT + "/" + intake.RESULT
        else:
            bad.payload["result_fingerprint"] = "0" * 64
            bad.files[intake.RESULT] = (json.dumps(bad.payload) + "\n").encode()
        bad.seed()
        with pytest.raises(ValueError) as refused:
            read(bad, "payload-" + change)
        if change == "fingerprint":
            assert type(refused.value) is ValueError
        else:
            assert type(refused.value) is output.OutputPublicationRefused
            assert refused.value.args == (("retention_result_runtime_identity_mismatch" if change == "runtime"
                                           else "retained_file_identity_mismatch"),)
        assert not (tmp_path / ("payload-" + change) / binding.result_marker).exists()

    # Private no-clobber and final-readback failures cannot authorize adoption.
    outside = tmp_path / "outside"
    outside.mkdir()
    link = tmp_path / "linked-parent"
    link.symlink_to(outside, target_is_directory=True)
    for terminal, transport, name in ((False, success_api, "result"), (True, terminal_api, "terminal-3")):
        before = list(transport.calls)
        with pytest.raises(output.OutputPublicationRefused) as refused:
            read(transport, name, terminal=terminal)
        assert refused.value.args == ("new_result_destination_required",) and transport.calls == before
        with pytest.raises(ReferenceIntegrityError):
            read(transport, "symlink", terminal=terminal, destination=link / "must-not-exist")
        assert transport.calls == before and not (outside / "must-not-exist").exists()
        real_write = reader._write_no_clobber
        marker_name = binding.terminal_marker if terminal else binding.result_marker

        def corrupt_marker(path, data, **kwargs):
            return real_write(path, data + b"\n" if path.name == marker_name else data, **kwargs)

        ambiguous = make(terminal=terminal)
        with monkeypatch.context() as ack:
            ack.setattr(reader, "_write_no_clobber", corrupt_marker)
            with pytest.raises(output.OutputPublicationRefused) as refused:
                read(ambiguous, "readback-" + str(terminal), terminal=terminal)
            assert refused.value.args == (("fresh_terminal_observation_unconfirmed" if terminal else
                                           "fresh_result_completion_acknowledgment_unconfirmed"),)
        before = list(ambiguous.calls)
        with pytest.raises(output.OutputPublicationRefused) as refused:
            read(ambiguous, "readback-" + str(terminal), terminal=terminal)
        assert refused.value.args == ("new_result_destination_required",) and ambiguous.calls == before

    # Small compatibility checks, not reruns of the delivered reader suites.
    for old_binding, options in ((reader.FRESH_R1, {}), (reader.FRESH_R2, {"binding": reader.FRESH_R2})):
        old_api = FreshResultHF(plan, binding=old_binding)
        transports.append(old_api)
        old = reader.read_result(expectation=old_binding.expectation, destination=tmp_path / ("old-" + str(old_binding.ordinal)),
            expected_reader_sha256=source["module_sha256"], terminal_revision=TERMINAL_HEAD, _test_api=old_api, **options)
        assert old["cell_id"] == old_binding.expectation.cell_id and old["format"] == old_binding.result_format
        if old_binding is reader.FRESH_R1:
            assert old["recorded_provider_job_id"] == 123456 and "expected_execution_job_id" not in old
        else:
            assert old["expected_execution_job_id"] == old["recorded_provider_job_id"] == old_binding.execution_job_id
    original_verify, verified_bindings = reader._verify_terminal, []
    for producer, old_binding, reason in ((fresh_r2, reader.FRESH_R1, "fresh_r2_predecessor_identity_mismatch"),
                                          (keep, reader.FRESH_R2, "keep_r2_predecessor_identity_mismatch")):
        predecessor = TerminalHF(plan, binding=old_binding, terminal_head=producer.PREDECESSOR["terminal_commit"])
        transports.append(predecessor)

        def observed_binding(*args, **kwargs):
            assert kwargs == ({"terminal_only": True} if old_binding is reader.FRESH_R1 else
                              {"terminal_only": True, "binding": reader.FRESH_R2})
            result = original_verify(*args, **kwargs)
            verified_bindings.append(result[0]["completion"]["cell_id"])
            return result

        cache = tmp_path / ("predecessor-" + str(old_binding.ordinal))
        cache.mkdir()
        with monkeypatch.context() as compatibility:
            compatibility.setattr(reader, "_verify_terminal", observed_binding)
            with retained._session(predecessor) as (client, token, deadline):
                # Reader validation succeeds; frozen independent historical byte
                # pins then reject these synthetic bytes. No historical pin changes.
                with pytest.raises(ci.RetentionCIRefused) as refused:
                    producer._predecessor(client, predecessor.repo, producer.PREDECESSOR["terminal_commit"], cache, token, deadline)
                assert refused.value.args == (reason,)
        old_producer = reader._producer(old_binding)
        assert {name for _, name in predecessor.downloads} == {
            old_producer.TERMINAL, old_producer.CLAIM, old_producer.OUTPUT + "/" + output.MANIFEST}
    assert verified_bindings == [reader.FRESH_R1.expectation.cell_id, reader.FRESH_R2.expectation.cell_id]
    assert all(transport.commits == [] for transport in transports) and effects == []
    print(json.dumps({"scope": "synthetic_keep_r2_reader_only", "success_payload_verified": True,
        "failed_stopped_controls_only": True, "exact_job_both_modes": True, "old_bindings_preserved": True,
        "private_no_clobber_readback": True, "live_effects": len(effects)}, sort_keys=True))
