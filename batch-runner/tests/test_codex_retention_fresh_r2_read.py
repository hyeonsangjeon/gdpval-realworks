"""The two fixed r2 read modes, with real validators and synthetic server bytes."""

import builtins
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
import json
from pathlib import Path

import pytest

import codex_retention_fresh_r1_result_intake as reader
import codex_retention_task4_fresh_r2 as r2
from core.codex_task_deadline import CodexTaskDeadline, CodexTaskDeadlineStore
from core.cost_receipts import CostReceipt
from .test_codex_budget_pilot_retention import TOKEN, offline  # noqa: F401
from .test_codex_retention_fresh_r1_result_intake import FreshResultHF
from .test_codex_retention_fresh_r1_terminal_observation import TerminalHF
from .test_codex_retention_result_intake import CLAIM_HEAD, OUTPUT_HEAD, TERMINAL_HEAD, FILE, PRIVATE

ci, retained, output, owned, intake = reader.ci, reader.retained, reader.output, reader.owned, reader.intake


def test_fresh_r2_reads_only_its_fixed_result_or_terminal(tmp_path, monkeypatch, capsys):
    effects = []

    def forbidden(*args, **kwargs):
        effects.append(True)
        raise AssertionError("fixed r2 read crossed a live, authority, payload or remote-write boundary")

    for owner, name in (
        (ci, "execute"), (ci, "verify_approval"), (ci, "verify_job_origin"), (ci, "verify_terminal"),
        (reader.fresh, "execute"), (reader.fresh, "_predecessor"), (reader.fresh, "verify_terminal"),
        (reader.fresh._FreshAdmission, "__init__"), (r2, "execute"), (r2, "verify_terminal"),
        (r2._FreshR2Admission, "__init__"), (ci._Admission, "__init__"),
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
    binding = reader.FRESH_R2
    assert binding.expectation == ci.TerminalExpectation(
        "4798c119ea2d06c7c902ae51638bdba25c5bfaf683a2223d286fd7e652d3b317",
        "5a9614ac04464c4e0a5e80297f54c3a5c9443bae",
        "3baa0009-5a60-4ae8-ae99-4955cb328ff3_retention_bundle_v1_fresh_r2")
    assert (binding.ordinal, binding.repetition, binding.run_id, binding.execution_job_id) == (2, 2, "36907894862", 110535767415)
    assert binding.original_input_bundle_sha256 == "757603585405da5d7f6817a6a0a23bd530d4b5e4e38b2fd4dc6f318053d240e3"
    assert binding.materialized_grader_source_sha256 == "4860a408791b7b313e2c06c2863b4a1ddbae467c8425365af8908be7a3c032d6"
    assert r2.PREDECESSOR["terminal_commit"] == "45f54eb0a24aee5d40dd41b276ff5df777f06d73"
    source = reader.reader_identity(binding=binding)
    assert source["producer_r2_sha256"] == "8b387ec5d172f74c4e6d2e1b93973c674e973f3cbba47b640184c126312ab00f"
    assert reader.reader_identity() == {key: value for key, value in source.items() if key != "producer_r2_sha256"}
    assert {key: source[key] for key in reader.FROZEN} == {key: pair[1] for key, pair in reader.FROZEN.items()}
    assert reader.FRESH_R1.expectation is reader.EXPECTATION
    assert (reader.RUN_ID, reader.EXPECTED_EXECUTION_JOB_ID) == ("36845127347", 110323708382)
    plan = intake.registration.compile_plan()
    transports = []

    def make(*, terminal=False, **options):
        api = (TerminalHF if terminal else FreshResultHF)(plan, binding=binding, **options)
        transports.append(api)
        return api

    def read(api, name, *, terminal=False, **changes):
        options = dict(expectation=binding.expectation, binding=binding, destination=tmp_path / name,
            expected_reader_sha256=source["module_sha256"], terminal_revision=TERMINAL_HEAD, _test_api=api)
        return (reader.observe_terminal if terminal else reader.read_result)(**{**options, **changes})

    def argv(name, terminal=False):
        return ["--observe-terminal" if terminal else "--read", "--discover-terminal",
            "--expected-producer-source", binding.expectation.source_sha,
            "--expected-request-sha256", binding.expectation.request_sha256,
            "--cell-id", binding.expectation.cell_id, "--expected-reader-sha256", source["module_sha256"],
            "--output", str(tmp_path / name)]

    def captured(api):
        text = capsys.readouterr()
        assert text.err == ""
        for secret in (str(tmp_path), api.repo, TOKEN, PRIVATE.decode().strip(), FILE, "SECRET-LIKE-ERROR"):
            assert secret not in text.out
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
            ({"expectation": object()}, "fresh_result_expectation_required"),
            ({"expectation": replace(binding.expectation, source_sha=reader.PRODUCER_SOURCE)}, "fresh_result_expected_producer_mismatch"),
            ({"expectation": replace(binding.expectation, request_sha256=reader.REQUEST_SHA256)}, "fresh_result_expected_request_mismatch"),
            ({"expectation": replace(binding.expectation, cell_id=reader.fresh.CELL_ID)}, "fresh_result_expected_cell_mismatch"),
            ({"expected_reader_sha256": "c19c970d0a0cd1c206a3f3a9286995f7c75e3237791f0220ccaf951c857bcdd9"}, "fresh_result_reader_bytes_mismatch"),
            ({"discover_terminal": True}, "one_terminal_revision_or_discovery_required"),
        )):
            for terminal in (False, True):
                name = "early-" + str(index) + str(terminal)
                with pytest.raises(output.OutputPublicationRefused) as refused:
                    read(api, name, terminal=terminal, **changes)
                assert refused.value.args == (reason,) and not (tmp_path / name).exists()
        assert api.calls == [] and effects == []
    # Simulate changed bytes at the fixed r2 path, not a changed expected pin or
    # successful validator. The real byte reader still checks its arguments.
    real_bytes, real_import = output._bytes, builtins.__import__

    def altered_source(path, *args, **kwargs):
        data = real_bytes(path, *args, **kwargs)
        return data + b"\n" if Path(path) == reader.R2_PRODUCER_PIN[0] else data

    def no_r2_import(name, *args, **kwargs):
        if name == "codex_retention_task4_fresh_r2":
            return forbidden()
        return real_import(name, *args, **kwargs)

    with monkeypatch.context() as altered:
        altered.setattr(output, "_bytes", altered_source)
        altered.setattr(builtins, "__import__", no_r2_import)
        altered.setattr(retained, "_session", forbidden)
        for operation in (lambda: read(api, "changed-source"), lambda: reader._producer(binding)):
            with pytest.raises(output.OutputPublicationRefused) as refused:
                operation()
            assert refused.value.args == ("fresh_result_reader_bytes_mismatch",)
    assert api.calls == [] and effects == [] and not (tmp_path / "changed-source").exists()
    monkeypatch.setenv("HF_TOKEN", TOKEN)  # Synthetic transport token, not a credential.
    receipt = ci.project_cost_receipt(CostReceipt(status="partial", model_calls=2,
        known_cost_usd=Decimal("0.01"), model_cost_usd=Decimal("0.01"),
        usage={"input_tokens": 12, "cached_input_tokens": 8, "output_tokens": 3, "reasoning_tokens": 2},
        missing_reasons=("synthetic_missing_cost",)).as_dict())
    success_api = make(receipt=receipt, with_ledger=True)
    code = reader.main(argv("result"), _test_api=success_api)
    success = captured(success_api)
    assert code == 0, {key: success.get(key) for key in ("reason", "intake_verified")}
    assert success["intake_verified"] is True and success["status"] == "succeeded"
    assert success["format"] == binding.result_format and "terminal_verified" not in success
    assert success["ordinal"] == 2 and success["cell_id"] == binding.expectation.cell_id
    assert success["producer_source_sha"] == binding.expectation.source_sha
    assert success["request_sha256"] == binding.expectation.request_sha256
    assert success["expected_execution_job_id"] == success["recorded_provider_job_id"] == 110535767415
    assert success["recorded_provider_run_id"] == success["expected_provider"]["run_id"] == "36907894862"
    assert success["expected_provider"]["attempt"] == 1 and success["expected_provider"]["workflow_id"] == 370228282
    assert success["result"]["registered_config_sha256"] == plan["cells"][2]["config_sha256"]
    assert output._hash(success["result"]["result_fingerprint"])
    assert success["receipt"] == receipt and success["http_request_count"] is None
    marker = tmp_path / "result" / binding.result_marker
    assert success["intake_sha256"] == owned._identity(marker.read_bytes())["sha256"]
    assert "intake_verified" not in json.loads(marker.read_bytes())
    assert (tmp_path / "result" / FILE).read_bytes() == PRIVATE
    assert success_api.path_reads[0] == (retained.BRANCH, (r2.TERMINAL,))
    assert sum(rev == retained.BRANCH for rev, _ in success_api.path_reads) == 1
    assert {name for _, name in success_api.downloads} == {r2.CLAIM, r2.TERMINAL,
        *(r2.OUTPUT + "/" + name for name in (*success_api.files, output.MANIFEST))}
    before = list(success_api.calls)
    with pytest.raises(output.OutputPublicationRefused) as refused:
        read(success_api, "result")
    assert refused.value.args == ("new_result_destination_required",) and success_api.calls == before

    controls = {r2.TERMINAL, r2.CLAIM, r2.OUTPUT + "/" + output.MANIFEST}
    for index, (status, declared, cost, exit_code) in enumerate((
        ("failed", "none", None, 1), ("stopped", "none", receipt, None),
        ("failed", "partial", receipt, 1), ("stopped", "result", None, -15),
    )):
        terminal_api = make(terminal=True, status=status, declared=declared, receipt=cost, exit_code=exit_code)
        with pytest.raises(output.OutputPublicationRefused) as refused:
            read(terminal_api, "not-success-" + str(index))
        assert refused.value.args == ("fresh_result_success_required",)
        with monkeypatch.context() as control_only:
            control_only.setattr(intake, "_payload", forbidden)
            control_only.setattr(intake.retained_reader, "_fetch", forbidden)
            code = reader.main(argv("terminal-" + str(index), True), _test_api=terminal_api)
        record = captured(terminal_api)
        assert code == 0, {key: record.get(key) for key in ("reason", "outcome")}
        assert record["outcome"] == "terminal_verified" and record["terminal_verified"] is True
        assert record["format"] == binding.terminal_format and record["ordinal"] == 2
        assert record["status"] == status and record["exit_code"] == exit_code and record["cleanup_confirmed"] is True
        assert record["expected_execution_job_id"] == record["recorded_provider_job_id"] == 110535767415
        assert record["terminal_commit"] == TERMINAL_HEAD != terminal_api.head
        assert record["terminal_identity"] == owned._identity(terminal_api.trees[TERMINAL_HEAD][r2.TERMINAL])
        assert record["claim_commit"] == CLAIM_HEAD and record["claim_identity"] == owned._identity(terminal_api.trees[CLAIM_HEAD][r2.CLAIM])
        assert record["output_commit"] == OUTPUT_HEAD
        assert record["output_manifest_identity"] == owned._identity(terminal_api.trees[OUTPUT_HEAD][r2.OUTPUT + "/" + output.MANIFEST])
        assert record["output_objects_sha256"] == owned._digest(terminal_api.terminal["output_objects"])
        assert record["predecessor"] == r2.PREDECESSOR and record["reader"] == source
        assert record["supplied_request_binding"] == {"original_input_bundle_sha256": binding.original_input_bundle_sha256,
            "materialized_grader_source_sha256": binding.materialized_grader_source_sha256}
        assert record["declared_payload_roles"] == {"inference_result": int(declared != "none"),
            "ledger": int(declared == "partial"), "deliverables": int(declared == "partial")}
        assert record["declared_output_object_count"] == len(terminal_api.files) + 1
        assert record["receipt"] == cost and record["missing"] == terminal_api.summary["missing"]
        assert record["unavailable"] == {field: {"status": "unavailable", "value": None,
            "reason": "not_recorded_in_terminal_controls"} for field in ("detailed_failure", "budget", "recovery_exposure")}
        assert record["payload_bodies_verified"] is record["grading_input_ready"] is False
        assert not {"intake_verified", "judge_ready", "result", "files"} & set(record)
        assert {name for _, name in terminal_api.downloads} == controls and terminal_api.commits == []
        assert sum(rev == retained.BRANCH for rev, _ in terminal_api.path_reads) == 1
        saved = (tmp_path / ("terminal-" + str(index)) / binding.terminal_marker).read_bytes()
        assert record["observation_sha256"] == owned._identity(saved)["sha256"]
        for evidence in (success, record):
            assert evidence["proof"] == "verified_publication_derived_not_independent_provider_authentication"
            assert evidence["writer_acknowledgment"] == "not_established" and evidence["recorded_publication_acknowledged"] is True
            for flag in ("fresh_origin_authentication", "prepared_input_independently_verified", "git_parent_cas_independently_verified",
                         "launch_authorized", "admission_attempted", "replay_authorized", "grading_launched", "invoice_complete"):
                assert evidence[flag] is False
            assert evidence["grade"] is evidence["http_request_count"] is None and evidence["commands"] == []

    # Exact job checks in both modes, retaining type checks before equality.
    for terminal in (False, True):
        for job in (reader.EXPECTED_EXECUTION_JOB_ID, True, float(binding.execution_job_id)):
            bad = make(terminal=terminal)
            for authority in (bad.claim["authority"], bad.terminal["authority"]):
                authority["provider_job_id"] = job
            bad.seed()
            with pytest.raises(output.OutputPublicationRefused) as refused:
                read(bad, "wrong-job-" + str(terminal) + str(job), terminal=terminal)
            reason = ("fresh_terminal_execution_job_mismatch" if terminal else "fresh_result_execution_job_mismatch")
            assert refused.value.args == ((reason if type(job) is int else "fresh_result_authority_binding_mismatch"),)

    reasons = {
        "source": "fresh_result_completion_mismatch", "cell": "fresh_result_completion_mismatch",
        "request": "fresh_result_terminal_binding_mismatch", "run": "fresh_result_authority_binding_mismatch",
        "claim": "fresh_result_terminal_claim_mismatch", "claim-type": "fresh_result_terminal_claim_mismatch",
        "predecessor": "fresh_result_predecessor_mismatch", "predecessor-type": "fresh_result_predecessor_mismatch",
        "parent": "fresh_result_predecessor_mismatch", "cleanup": "fresh_result_completion_mismatch",
        "grade": "fresh_result_completion_mismatch", "grading": "fresh_result_completion_mismatch",
        "invoice": "fresh_result_completion_mismatch", "status": "fresh_terminal_unsuccessful_required",
        "success": "fresh_terminal_unsuccessful_required",
        "exit-type": "fresh_terminal_unsuccessful_required", "missing": "fresh_result_missing_accounting_mismatch",
        "receipt-type": "fresh_result_accounting_mismatch", "private": "retention_result_private_state_refused",
        "claim-hash": "payload_identity_mismatch", "control-corruption": "retention_control_blob_mismatch",
        "object-history": "remote_output_history_mismatch", "claim-history": "retention_control_history_mismatch",
        "terminal-history": "retention_control_history_mismatch", "extra-object": "fresh_result_output_objects_mismatch",
        "object-body": "remote_output_blob_mismatch", "noncanonical": "noncanonical_retention_record",
        "control-bound": "retention_control_file_refused", "missing-claim": "terminal_or_claim_missing",
        "missing-manifest": "terminal_or_claim_missing", "missing-object": "remote_output_objects_missing",
    }
    for mode, reason in reasons.items():
        bad = make(terminal=True)
        if mode in {"source", "cell", "cleanup", "grade", "grading", "invoice", "status", "success", "exit-type", "missing"}:
            field, value = {"source": ("source_sha", reader.PRODUCER_SOURCE), "cell": ("cell_id", reader.fresh.CELL_ID),
                "cleanup": ("cleanup_confirmed", 1), "grade": ("grade", 0), "grading": ("grading_launched", 0),
                "invoice": ("invoice_complete", True), "status": ("status", "running"), "success": ("status", "succeeded"),
                "exit-type": ("exit_code", True), "missing": ("missing", [])}[mode]
            bad.summary[field] = value
        elif mode == "request":
            bad.terminal["request_sha256"] = reader.REQUEST_SHA256
        elif mode == "run":
            for authority in (bad.claim["authority"], bad.terminal["authority"]):
                authority["provider_run_id"] = reader.RUN_ID
        elif mode == "claim":
            bad.claim["request_sha256"] = reader.REQUEST_SHA256
        elif mode == "claim-type":
            bad.claim["authority"]["provider_job_id"] = float(binding.execution_job_id)
        elif mode == "predecessor":
            bad.claim["predecessor"] = deepcopy(reader.fresh.PREDECESSOR)
        elif mode == "predecessor-type":
            bad.claim["predecessor"]["terminal_identity"]["size"] = 4206.0
        elif mode == "parent":
            bad.claim["expected_parent"] = reader.fresh.PREDECESSOR["terminal_commit"]
        elif mode == "receipt-type":
            bad.summary.update(receipt=deepcopy(receipt), accounting="partial")
            bad.summary["receipt"]["known_cost_usd"] = 1
        elif mode == "private":
            bad.files[FILE.rsplit("/", 1)[0] + "/HOME/auth.json"] = PRIVATE
        elif mode == "control-corruption":
            bad.corrupt = r2.TERMINAL
        bad.seed()
        if mode == "claim-hash":
            bad.terminal["claim_identity"]["sha256"] = "0" * 64
        elif mode == "extra-object":
            bad.terminal["output_objects"].append(deepcopy(bad.terminal["output_objects"][0]))
        elif mode == "object-history":
            bad.writers[TERMINAL_HEAD][r2.OUTPUT + "/" + FILE] = TERMINAL_HEAD
        elif mode == "claim-history":
            bad.writers[CLAIM_HEAD][r2.CLAIM] = TERMINAL_HEAD
        elif mode == "terminal-history":
            bad.writers[TERMINAL_HEAD][r2.TERMINAL] = OUTPUT_HEAD
        elif mode == "object-body":
            bad.trees[TERMINAL_HEAD][r2.OUTPUT + "/" + FILE] = b"X" * len(PRIVATE)
        elif mode in {"missing-claim", "missing-manifest", "missing-object"}:
            bad.omit_metadata = {"missing-claim": (CLAIM_HEAD, r2.CLAIM),
                "missing-manifest": (OUTPUT_HEAD, r2.OUTPUT + "/" + output.MANIFEST),
                "missing-object": (TERMINAL_HEAD, r2.OUTPUT + "/" + FILE)}[mode]
        bad.trees[TERMINAL_HEAD][r2.TERMINAL] = retained._encoded(bad.terminal)
        if mode == "noncanonical":
            bad.trees[TERMINAL_HEAD][r2.TERMINAL] = json.dumps(bad.terminal, indent=2).encode()
        elif mode == "control-bound":
            bad.trees[TERMINAL_HEAD][r2.TERMINAL] = b"X" * (output.MAX_MANIFEST_BYTES + 1)
        with pytest.raises(output.OutputPublicationRefused) as refused:
            read(bad, "negative-" + mode, terminal=True)
        assert refused.value.args == (reason,), mode
        assert {name for _, name in bad.downloads} <= controls
        assert not (tmp_path / ("negative-" + mode) / binding.terminal_marker).exists()

    for terminal in (False, True):
        for state in ("missing", "ambiguous"):
            absent = make(terminal=True)
            if state == "missing":
                absent.omit_metadata = (retained.BRANCH, r2.TERMINAL)
            else:
                paths_info = absent.get_paths_info

                def ambiguous_paths(**kwargs):
                    found = paths_info(**kwargs)
                    return found * 2 if kwargs["revision"] == retained.BRANCH else found

                monkeypatch.setattr(absent, "get_paths_info", ambiguous_paths)
            code = reader.main(argv("not-ready-" + str(terminal) + state, terminal), _test_api=absent)
            public = captured(absent)
            assert code == 2 and public["reason"] == "fresh_result_terminal_not_ready"
            assert len(absent.path_reads) == 1 and absent.downloads == []
    for mode, reason in (("duplicate", "fresh_result_output_bounds_exceeded"),
                         ("total", "fresh_result_output_bounds_exceeded"),
                         ("size-type", "fresh_result_output_identity_refused"),
                         ("record", "retention_result_record_bounds_exceeded")):
        summary = deepcopy(terminal_api.summary)
        if mode == "duplicate":
            summary["files"].append(deepcopy(summary["files"][0]))
        elif mode == "total":
            summary["files"] = [{"path": f"deliverable_files/{intake.registration.TASK4}/{index}.txt",
                "size": output.MAX_FILE_BYTES, "sha256": "0" * 64} for index in range(3)]
        elif mode == "size-type":
            summary["files"][0]["size"] = True
        else:
            next(item for item in summary["files"] if item["path"] == intake.RESULT)["size"] = output.MAX_RECORD_BYTES + 1
        with pytest.raises(output.OutputPublicationRefused) as refused:
            reader._terminal_summary(summary, binding=binding)
        assert refused.value.args == (reason,)
    for path in ("unrelated.json", "../escape", FILE.replace(intake.registration.TASK4, "foreign-task")):
        summary = deepcopy(terminal_api.summary)
        summary["files"] = sorted([*summary["files"], {"path": path, "size": 1, "sha256": "0" * 64}], key=lambda item: item["path"])
        with pytest.raises(ValueError) as refused:
            reader._terminal_summary(summary, binding=binding)
        assert type(refused.value) is ValueError  # Never emit a raw path-bearing error.
    for mode in ("runtime", "payload-corruption", "fingerprint"):
        bad = make()
        if mode == "runtime":
            bad.payload["run_id"] = "wrong-run"
            bad.bind_payload()
        elif mode == "payload-corruption":
            bad.corrupt = r2.OUTPUT + "/" + intake.RESULT
        else:
            bad.payload["result_fingerprint"] = "0" * 64
            bad.files[intake.RESULT] = (json.dumps(bad.payload) + "\n").encode()
        bad.seed()
        with pytest.raises(ValueError) as refused:
            read(bad, "payload-" + mode)
        if mode == "fingerprint":
            assert type(refused.value) is ValueError
        else:
            assert type(refused.value) is output.OutputPublicationRefused
            assert refused.value.args == (("retention_result_runtime_identity_mismatch" if mode == "runtime"
                                            else "retained_file_identity_mismatch"),)
        assert not (tmp_path / ("payload-" + mode) / binding.result_marker).exists()
    arbitrary = make(terminal=True)
    arbitrary.read_error = ValueError("SECRET-LIKE-ERROR")
    assert reader.main(argv("redacted", True), _test_api=arbitrary) == 2
    assert captured(arbitrary)["reason"] == "fresh_terminal_observation_refused"

    # Small default-compatibility checks, not replay of the delivered suites.
    r1_success = FreshResultHF(plan)
    old = reader.read_result(expectation=reader.EXPECTATION, destination=tmp_path / "r1-default",
        expected_reader_sha256=source["module_sha256"], terminal_revision=TERMINAL_HEAD, _test_api=r1_success)
    assert old["format"] == reader.FORMAT and old["cell_id"] == reader.fresh.CELL_ID
    assert old["recorded_provider_job_id"] == 123456 and "expected_execution_job_id" not in old
    old_parent = r2.PREDECESSOR["terminal_commit"]
    r1_failed = TerminalHF(plan, terminal_head=old_parent)
    original_verify, verified_defaults = reader._verify_terminal, []

    def observed_default(*args, **kwargs):
        assert "binding" not in kwargs and kwargs == {"terminal_only": True}
        result = original_verify(*args, **kwargs)
        verified_defaults.append(result[0]["completion"]["cell_id"])
        return result

    cache = tmp_path / "r1-predecessor-controls"
    cache.mkdir()
    with monkeypatch.context() as defaults:
        defaults.setattr(reader, "_verify_terminal", observed_default)
        with retained._session(r1_failed) as (client, token, deadline):
            # Synthetic controls validate as r1. The frozen producer then rejects
            # their nonmatching real-world byte pins; no expected pin is changed.
            with pytest.raises(ci.RetentionCIRefused) as refused:
                r2._predecessor(client, r1_failed.repo, old_parent, cache, token, deadline)
            assert refused.value.args == ("fresh_r2_predecessor_identity_mismatch",)
    assert verified_defaults == [reader.fresh.CELL_ID]
    assert {name for _, name in r1_failed.downloads} == {reader.fresh.TERMINAL, reader.fresh.CLAIM,
        reader.fresh.OUTPUT + "/" + output.MANIFEST}
    assert all(transport.commits == [] for transport in [*transports, r1_success, r1_failed]) and effects == []
